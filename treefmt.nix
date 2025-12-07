{ ... }:
{
  projectRootFile = "flake.nix";

  # Nix
  programs.deadnix.enable = true;
  programs.nixfmt.enable = true;

  # Python
  programs.ruff-check.enable = true;
  programs.ruff-format.enable = true;

  # TOML
  programs.taplo.enable = true;
}
