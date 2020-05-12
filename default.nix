with (import ./pypi2nixpkgs/nixpkgs.nix) {};
python3.pkgs.faraday_client.overrideAttrs (attrs: {

  doCheck = true;
  checkPhase = ''
    # This sanity test was copy pasted from a full of Nix hacks version.
    # So if the test passes, this doesn't mean the client will work ok
    python -c "import gi;gi.require_version('Gtk', '3.0');gi.require_version('Vte', '2.91');from gi.repository import Gio, Gtk, GdkPixbuf, Vte, GLib, GObject, Gdk" # Test if GTK will work
  '';

  # Based on https://github.com/NixOS/nixpkgs/blob/master/pkgs/applications/editors/rednotebook/default.nix

  nativeBuildInputs = [ gobject-introspection ] ++
    attrs.nativeBuildInputs;

  # Until gobject-introspection in nativeBuildInputs is supported.
  # https://github.com/NixOS/nixpkgs/issues/56943#issuecomment-472568643
  strictDeps = false;

  propagatedBuildInputs = [
    gnome3.vte
    wrapGAppsHook
  ] ++ attrs.propagatedBuildInputs;
})
