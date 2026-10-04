{ pkgs, ... }:

{
  packages = [
    pkgs.ruff
    pkgs.ty

    pkgs.bashInteractive
    pkgs.coreutils
    pkgs.git
    pkgs.openssh
  ];

  languages.python = {
    enable = true;
    package = pkgs.python314;
    venv.enable = true;
    uv = {
      enable = true;
      sync.enable = true;
    };
  };

  scripts.check.exec = ''
    set -e
    cd "$DEVENV_ROOT"
    ruff format --check .
    ruff check .
    ty check
    pytest
  '';

  enterShell = ''
    echo "golem-fleet  ·  python $(python --version | cut -d' ' -f2)  ·  uv $(uv --version | cut -d' ' -f2)"
    echo "check    : ruff format --check . · ruff check . · ty check · pytest"
  '';
}
