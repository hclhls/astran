{
  description = "Astran dev shell: librelane EDA tools plus build and solver tools";

  inputs = {
    librelane.url = "github:librelane/librelane";
  };

  outputs = { self, librelane, ... }:
    let
      systems = builtins.attrNames librelane.devShells;
      nixpkgs = librelane.inputs.nix-eda.inputs.nixpkgs;
    in {
      devShells = nixpkgs.lib.genAttrs systems (system:
        let
          pkgs = nixpkgs.legacyPackages.${system};
          # librelane's shell already provides python3 with klayout.db, magic,
          # netgen and klayout; add only what it lacks.
          pytestEnv = pkgs.python3.withPackages (ps: [ ps.pytest ]);
          base = librelane.devShells.${system}.default;
        in {
          default = pkgs.mkShell {
            packages = base.config.devshell.packages ++ [ pkgs.highs pkgs.gnumake pkgs.gcc
              # run pytest with librelane's python so klayout.db is importable
              (pkgs.writeShellScriptBin "pytest" ''exec python3 -m pytest "$@"'')
            ];
            shellHook = ''
              export PYTHONPATH=${pytestEnv}/${pytestEnv.sitePackages}''${PYTHONPATH:+:$PYTHONPATH}
            '';
          };
        });
    };
}
