{ overlays ? [ ], ... }@args:
let
  pypi2nixOverlay = self: super: {
    python3 = super.python3.override { inherit packageOverrides; };
  };

  nixpkgs =

    builtins.fetchTarball {
      url =
        "https://github.com/infobyte/nixpkgs/archive/acd94facb9aaf3d463f985e57f89f5b397155153.tar.gz";
      sha256 = "1bz1blwqsnmcrrhb3rfpav6wczkr6jz4756ypf8xnw6ww4z9vk0v";
    };

  packageOverrides = self: super: {
    faraday-plugins = self.callPackage ./packages/faraday-plugins.nix { };

    faraday_client = self.callPackage ./packages/faraday_client.nix { };

    flask-restless = self.callPackage ./packages/flask-restless.nix { };

    mimerender = self.callPackage ./packages/mimerender.nix { };

    xlsxwriter = self.callPackage ./packages/xlsxwriter.nix { };

  };

in import nixpkgs (args // { overlays = [ pypi2nixOverlay ] ++ overlays; })
