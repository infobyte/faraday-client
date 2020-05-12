{ overlays ? [ ], ...}@args:
    let
        pypi2nixOverlay = self: super: {
            python3 = super.python3.override { inherit packageOverrides; };
        };

        
            nixpkgs =
                builtins.fetchTarball {
                    url = https://github.com/cript0nauta/nixpkgs/archive/7002c9c8ab98917bd0f029a5a4dc822507939a77.tar.gz;
                    sha256 = "17534f9a9cz3plc2lqkk3i1l1idf5hsnayfikrp917r1cwvnnm2q";
                };
        

        packageOverrides = self: super: {
    

            faraday_client =
                self.callPackage ./packages/faraday_client.nix { };
        

            flask-restless =
                self.callPackage ./packages/flask-restless.nix { };
        

            mimerender =
                self.callPackage ./packages/mimerender.nix { };
        

            html2text =
                self.callPackage ./packages/html2text.nix { };
        

            future =
                self.callPackage ./packages/future.nix { };
        

            xlsxwriter =
                self.callPackage ./packages/xlsxwriter.nix { };
        

        };
    in import nixpkgs (args // { overlays = [ pypi2nixOverlay ] ++ overlays; })
    