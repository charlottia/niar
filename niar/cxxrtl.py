import json
import logging
import os
import shutil
from enum import Enum
from functools import partial
from pathlib import Path
from typing import Any

from amaranth._toolchain.yosys import YosysBinary, find_yosys
from amaranth.back import rtlil

from .build import construct_top
from .cmdrunner import CommandRunner
from .logging import logtime
from .project import Project

__all__ = ["add_arguments"]

CXXFLAGS = [
    "-std=c++17",
    "-g",
    "-pedantic",
    "-Wall",
    "-Wextra",
    "-Wno-zero-length-array",
    "-Wno-unused-parameter",
]


class _Optimize(Enum):
    none = "none"
    rtl = "rtl"
    app = "app"
    both = "both"

    def __str__(self):
        return self.value

    @property
    def opt_rtl(self) -> bool:
        return self in (self.rtl, self.both)

    @property
    def opt_app(self) -> bool:
        return self in (self.app, self.both)


def add_arguments(np: Project, parser):
    parser.set_defaults(func=partial(main, np))
    match sorted(t.__name__ for t in np.cxxrtl_targets or []):
        case []:
            raise RuntimeError("no cxxrtl targets defined")
        case [first, *rest]:
            parser.add_argument(
                "-t",
                "--target",
                choices=[first, *rest],
                help="which CXXRTL target to build",
                required=bool(rest),
                **({"default": first} if not rest else {}),
            )
    parser.add_argument(
        "-c",
        "--compile",
        action="store_true",
        help="compile only; don't run",
    )
    parser.add_argument(
        "-O",
        "--optimize",
        type=_Optimize,
        choices=_Optimize,
        help="build with optimizations (default: rtl)",
        default=_Optimize.rtl,
    )
    parser.add_argument(
        "-d",
        "--debug",
        action="store_true",
        help="generate source-level debug information",
    )
    parser.add_argument(
        "-v",
        "--vcd",
        action="store",
        type=str,
        help="output a VCD file",
    )
    parser.add_argument(
        "-f",
        "--force",
        action="store_true",
        help="don't use cached compilations",
    )


def main(np: Project, args):
    yosys = find_yosys(lambda ver: ver >= (0, 10))

    os.makedirs(np.path.build(), exist_ok=True)

    platform = np.cxxrtl_target_by_name(args.target)
    design = construct_top(np, platform)
    cr = CommandRunner(force=args.force)

    with logtime(logging.DEBUG, "elaboration"):
        il_path = np.path.build(f"{np.name}.il")
        rtlil_text = rtlil.convert(design, name=np.name, platform=platform)
        with open(il_path, "w") as f:
            f.write(rtlil_text)

        cxxrtl_cc_path = np.path.build(f"{np.name}.cc")
        yosys_script_path = _make_absolute(np.path.build(f"{np.name}-cxxrtl.ys"))
        black_boxes = {}

        with open(yosys_script_path, "w") as f:
            for box_source in black_boxes.values():
                f.write(f"read_rtlil <<rtlil\n{box_source}\nrtlil\n")
            f.write(f"read_rtlil {_make_absolute(il_path)}\n")
            # TODO: do we want to call any opt passes here?
            f.write(f"write_cxxrtl -header {_make_absolute(cxxrtl_cc_path)}\n")

        def rtlil_to_cc():
            yosys.run(["-q", yosys_script_path])

        cr.add_process(rtlil_to_cc,
            infs=[il_path, yosys_script_path],
            outf=cxxrtl_cc_path)
        cr.run()

    with logtime(logging.DEBUG, "compilation"):
        cc_odep_paths = {cxxrtl_cc_path: (np.path.build(f"{np.name}.o"), [])}
        depfs = list(np.path("cxxrtl").glob("**/*.h"))
        for path in np.path("cxxrtl").glob("**/*.cc"):
            # XXX: we make no effort to distinguish cxxrtl/a.cc and cxxrtl/dir/a.cc.
            cc_odep_paths[path] = (np.path.build(f"{path.stem}.o"), depfs)

        cxxflags = CXXFLAGS + [
            f"-DCLOCK_HZ={int(platform.default_clk_frequency)}",
            *(["-O3"] if args.optimize.opt_rtl else ["-O0"]),
            *(["-g"] if args.debug else []),
        ]
        if platform.uses_zig:
            cxxflags += [
                "-DCXXRTL_INCLUDE_CAPI_IMPL",
                "-DCXXRTL_INCLUDE_VCD_CAPI_IMPL",
            ]

        for cc_path, (o_path, dep_paths) in cc_odep_paths.items():
            cmd = [
                "c++",
                *cxxflags,
                f"-I{np.path("build")}",
                f"-I{yosys.data_dir() / "include" / "backends" / "cxxrtl" / "runtime"}",
                "-c",
                cc_path,
                "-o",
                o_path,
            ]
            if platform.uses_zig:
                cmd = ["zig"] + cmd
            cr.add_process(cmd, infs=[cc_path] + dep_paths, outf=o_path)

        with open(np.path.build("compile_commands.json"), "w") as f:
            json.dump(
                [{
                    "directory": str(np.path()),
                    "file": file,
                    "arguments": arguments,
                } for file, arguments in cr.compile_commands.items()],
                f,
            )

        cr.run()

        exe_o_path = np.path.build("cxxrtl")
        cc_o_paths = [o_path for (o_path, _) in cc_odep_paths.values()]
        if platform.uses_zig:
            cmd = [
                "zig",
                "build",
                f"-Dclock_hz={int(platform.default_clk_frequency)}",
                f"-Dyosys_data_dir={yosys.data_dir()}",
            ] + [
                # Zig really wants relative paths.
                f"-Dcxxrtl_o_path=../{p.relative_to(np.path())}" for p in cc_o_paths
            ]
            if args.optimize.opt_app:
                cmd += ["-Doptimize=ReleaseFast"]
            outf = "cxxrtl/zig-out/bin/cxxrtl"
            cr.add_process(cmd,
                infs=cc_o_paths + list(np.path("cxxrtl").glob("**/*.zig")),
                outf=outf,
                chdir="cxxrtl")
            cr.run()
            shutil.copy(outf, exe_o_path)
        else:
            cmd = [
                "c++",
                *cxxflags,
                *cc_o_paths,
                "-o",
                exe_o_path,
            ]
            cr.add_process(cmd,
                infs=cc_o_paths,
                outf=exe_o_path)
            cr.run()

    if not args.compile:
        cmd = [exe_o_path]
        if args.vcd:
            cmd += ["--vcd", args.vcd]
        cr.run_cmd(cmd, step="run")


def _make_absolute(path):
    if path.is_absolute():
        try:
            path = path.relative_to(Path.cwd())
        except ValueError:
            raise AssertionError("path must be relative to cwd for builtin-yosys to access it")
    return path
