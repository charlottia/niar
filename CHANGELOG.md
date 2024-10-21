# niar

## 0.1.3 (unreleased)

New:

* project: `NIAR_WORKING_DIRECTORY` can be used to override the origin.
* project: `externals` can be specified to pull in Verilog/RTLIL to build and Verilog to CXXRTL.
* project: extension `commands` can be added.

Changed:

* cxxrtl: don't show a Python backtrace when a build step fails. 
* cxxrtl: don't show a Python backtrace when interrupting the running program.
* build/cxxrtl: show failing commands' exit statuses.

## 0.1.2

New:

* build: `platform_kwargs` defined on the platform will be included in the `platform.prepare()` call.
* build: timing information from place-and-route shown as part of post-build log.

Changed:

* template: build CXXRTL with optimisations by default in CI
  (cf. [amaranth-lang/amaranth-yosys#12](https://github.com/amaranth-lang/amaranth-yosys/pull/12)).
* **XXX** cxxrtl: disabled dependency tracking for now, as it's broken in the important case of
  source files which depend on the CXXRTL module itself (e.g. those which instantiate it!).

Fixed:

* python: use PDM and declare dependencies correctly.
* build: use generated IL to calculate digest, not what's on disk.
* build: synthesis depends on the yosys script too, not just IL.
* build: fix path used with cached synthesis when programming.

## 0.1.1

New:

* setup-action: GitHub Actions support for preparing.
* workflows: test in CI.
* template: getting started template.

Changed:

* python: move to src layout.
* project: define root where `pyproject.toml` found.
* cxxrtl: dependency tracking to avoid needless rebuilds.
* cxxrtl: fix distinction between optimising RTL and code.
* build: only resynthesise when RTLIL changes.
* build: `build` subdirectory per platform.

Fixed:

* cxxrtl: correctly disable when not used.

## 0.1.0

Initial release.
