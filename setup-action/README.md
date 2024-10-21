# charlottia/niar/setup-action

Use after cloning your project repository. You'll need to specify Niar as a
dependency, and any HEAD versions of Amaranth et al. needed.

Usage:

```yaml
- uses: charlottia/niar/setup-action@main
  with:
    install-oss-cad-suite: true
    github-token: ${{ secrets.GITHUB_TOKEN }}
    install-zig: 0.13.0
```

* Installs Python and PDM.
* Runs `pdm install`.
* If `install-oss-cad-suite` is specified, installs OSS CAD Suite using `github-token`.
* If `install-zig` is specified, installs given version of Zig.
