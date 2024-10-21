{
  description = "Niar development environment";

  inputs = {
    nixpkgs.url = github:NixOS/nixpkgs/nixos-unstable;
    flake-utils.url = github:numtide/flake-utils;
  };

  outputs = {
    self,
    nixpkgs,
    flake-utils,
  }:
    flake-utils.lib.eachDefaultSystem (system: let
      pkgs = import nixpkgs {inherit system;};

      pyproject-toml = pkgs.lib.importTOML ./pyproject.toml;

      python = let
        packageOverrides = final: prev: {
          amaranth = prev.amaranth.overridePythonAttrs {
            version = "0.6.0.dev52";
            src = pkgs.fetchFromGitHub {
              owner = "charlottia";
              repo = "amaranth";
              rev = "e5644486fdae47c1372ef2a672b0249857694d66";
              hash = "sha256-kg4rTBRSi+1oaxazRWnw7fhTvyQE96a6XjOgk0f2JQ0=";
            };
            doCheck = false; # uninit'd mem breaks lots of tests.
          };

          amaranth-boards = prev.amaranth-boards.overridePythonAttrs rec {
            version = "0.1.dev250";
            src = pkgs.fetchFromGitHub {
              owner = "amaranth-lang";
              repo = "amaranth-boards";
              rev = "19b97324ecf9111c5d16377af79f82aad761c476";
              postFetch = "rm -f $out/.git_archival.txt $out/.gitattributes";
              hash = "sha256-0uvn91i/yuIY75lL5Oxvozdw7Q2Uw83JWo7srgEYEpI=";
            };

            build-system = [python.pkgs.pdm-backend];
            dontCheckRuntimeDeps = 1; # amaranth 0.6.0.devX doesn't match anything.
          };
        };
      in
        pkgs.python3.override {
          inherit packageOverrides;
          self = python;
        };

      toolchain-pkgs = with pkgs; [
        yosys
        icestorm
        trellis
        nextpnr
        openfpgaloader
      ];
    in rec {
      formatter = pkgs.alejandra;

      packages.default = packages.niar;

      packages.python = python;
      packages.niar = python.pkgs.buildPythonPackage {
        name = "niar";
        version = pyproject-toml.project.version;
        src = ./.;
        pyproject = true;

        build-system = [python.pkgs.pdm-backend];

        propagatedBuildInputs =
          [
            python.pkgs.amaranth
            python.pkgs.amaranth-boards
          ]
          ++ toolchain-pkgs;

        doCheck = true;
        nativeCheckInputs = [python.pkgs.pytestCheckHook] ++ toolchain-pkgs;

        dontCheckRuntimeDeps = 1; # amaranth 0.6.0.devX doesn't match anything.
      };

      devShells.default = pkgs.mkShell {
        name = "niar";

        buildInputs = with python.pkgs; [
          python-lsp-server
          pyls-isort
          pylsp-rope
          pytest
        ];

        inputsFrom = [packages.default];
      };

      devShells.pdm = pkgs.mkShell {
        name = "niar-pdm";

        buildInputs =
          [
            pkgs.python3
            pkgs.pdm
          ]
          ++ toolchain-pkgs;
      };
    });
}
