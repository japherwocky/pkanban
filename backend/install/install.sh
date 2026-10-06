#!/bin/sh
# pkanban installer for macOS, Linux and WSL.
#
#   curl -fsSL __PKANBAN_SERVER__/install.sh | sh
#
# Installs the pkanban CLI as an isolated tool -- with uv if you have it, else
# pipx, else it installs uv first (uv brings its own Python, so none is needed
# beforehand) -- then points the CLI at the server this script came from.
#
# Everything lives inside main(), called on the last line, so a download cut
# off halfway runs nothing rather than half an install.

set -eu

PKANBAN_SERVER="${PKANBAN_SERVER:-__PKANBAN_SERVER__}"

say() { printf '%s\n' "$*"; }
die() { printf 'pkanban install: %s\n' "$*" >&2; exit 1; }
have() { command -v "$1" >/dev/null 2>&1; }

install_uv() {
    say "Installing uv (a Python tool installer, from astral.sh)..."
    if have curl; then
        curl -LsSf https://astral.sh/uv/install.sh | sh >/dev/null
    elif have wget; then
        wget -qO- https://astral.sh/uv/install.sh | sh >/dev/null
    else
        die "need curl or wget to download uv"
    fi
    # uv's installer edits shell profiles, which this shell has already read.
    PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"
    have uv || die "uv installed but is not on PATH; open a new terminal and rerun"
}

# Ask the installer where it put the binary rather than assume ~/.local/bin:
# UV_TOOL_BIN_DIR, PIPX_BIN_DIR or XDG_BIN_HOME can each move it.
find_pkanban() {
    for dir in \
        "$(uv tool dir --bin 2>/dev/null || true)" \
        "$(pipx environment --value PIPX_BIN_DIR 2>/dev/null || true)" \
        "$HOME/.local/bin"; do
        [ -n "$dir" ] || continue
        for exe in "$dir/pkanban" "$dir/pkanban.exe"; do
            if [ -x "$exe" ]; then printf '%s\n' "$exe"; return; fi
        done
    done
    command -v pkanban 2>/dev/null || true
}

main() {
    if have uv; then
        say "Installing pkanban with uv..."
        uv tool install --quiet --upgrade pkanban
    elif have pipx; then
        say "Installing pkanban with pipx..."
        pipx install --quiet --force pkanban
    else
        install_uv
        say "Installing pkanban with uv..."
        uv tool install --quiet --upgrade pkanban
    fi

    bin="$(find_pkanban)"
    [ -n "$bin" ] || die "pkanban installed but cannot be found; open a new terminal and run 'pkanban --version'"

    "$bin" config --url "$PKANBAN_SERVER" >/dev/null

    say ""
    say "Installed $("$bin" --version 2>/dev/null | head -n 1), using $PKANBAN_SERVER"
    if ! have pkanban; then
        say ""
        say "$(dirname "$bin") is not on your PATH yet. Open a new terminal, or run:"
        say "  export PATH=\"$(dirname "$bin"):\$PATH\""
    fi
    say ""
    say "Next, sign in:"
    say "  pkanban login <username>"
    say ""
    say "No account yet? Create one at $PKANBAN_SERVER/signup"
    say "Agents and scripts: make an API key at $PKANBAN_SERVER/settings/api-keys and run"
    say "  pkanban apikey save <key>"
}

main "$@"
