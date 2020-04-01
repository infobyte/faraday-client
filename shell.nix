(import ./default.nix).overrideAttrs (x: {
  doCheck = true;
  checkPhase = "true";
  checkInputs = with (import ./pypi2nixpkgs/nixpkgs.nix { }).python3.pkgs; [
    # TODO fill this
  ];

  shellHook = ''
    setuptoolsShellHook
    # Without this, the import report dialog breaks inside nix-shell
    # Taken from https://github.com/NixOS/nixpkgs/pull/26614
    export XDG_DATA_DIRS=$GSETTINGS_SCHEMAS_PATH:$XDG_DATA_DIRS
  '';
})
