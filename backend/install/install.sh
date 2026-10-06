#!/bin/sh
# pkanban installer for macOS, Linux and WSL.
#
#   curl -fsSL __PKANBAN_SERVER__/install.sh | sh
#
# Installs the pkanban CLI as an isolated tool -- with uv if you have it, else
# pipx, else it installs uv first (uv brings its own Python, so none is needed
# beforehand) -- then points the CLI at the server this script came from, and
# puts it on your PATH for new terminals.
#
# Set PKANBAN_NO_MODIFY_PATH=1 to leave shell profiles alone.
#
# Everything lives inside main(), called on the last line, so a download cut
# off halfway runs nothing rather than half an install.

set -eu

PKANBAN_SERVER="${PKANBAN_SERVER:-__PKANBAN_SERVER__}"
# What PATH was before this script touched it: whether `pkanban` will be found
# in the user's next terminal depends on this, not on our own adjustments.
ORIGINAL_PATH="$PATH"

say() { printf '%s\n' "$*"; }
die() { printf 'pkanban install: %s\n' "$*" >&2; exit 1; }
have() { command -v "$1" >/dev/null 2>&1; }
on_original_path() {
    case ":$ORIGINAL_PATH:" in *":$1:"*) return 0 ;; esac
    return 1
}

install_uv() {
    say "Installing uv (a Python tool installer, from astral.sh)..."
    if [ -n "${PKANBAN_NO_MODIFY_PATH:-}" ]; then
        UV_NO_MODIFY_PATH=1
        export UV_NO_MODIFY_PATH
    fi
    if have curl; then
        curl -LsSf https://astral.sh/uv/install.sh | sh >/dev/null 2>&1
    elif have wget; then
        wget -qO- https://astral.sh/uv/install.sh | sh >/dev/null 2>&1
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

# Have the tool that installed pkanban add its bin directory to the shell
# profiles; each knows its own directory and which profiles to touch.
add_to_path() {
    [ -z "${PKANBAN_NO_MODIFY_PATH:-}" ] || return 1
    case "$1" in
        uv) uv tool update-shell >/dev/null 2>&1 ;;
        pipx) pipx ensurepath >/dev/null 2>&1 ;;
        *) return 1 ;;
    esac
}

main() {
    if have uv; then
        via=uv
    elif have pipx; then
        via=pipx
    else
        install_uv
        via=uv
    fi
    say "Installing pkanban with $via..."
    if [ "$via" = uv ]; then
        uv tool install --quiet --upgrade pkanban
    else
        pipx install --quiet --force pkanban >/dev/null
    fi

    bin="$(find_pkanban)"
    [ -n "$bin" ] || die "pkanban installed but cannot be found; open a new terminal and run 'pkanban --version'"
    dir="$(dirname "$bin")"

    "$bin" config --url "$PKANBAN_SERVER" >/dev/null

    say ""
    say "Installed $("$bin" --version 2>/dev/null | head -n 1), using $PKANBAN_SERVER"
    if ! on_original_path "$dir"; then
        say ""
        if add_to_path "$via"; then
            say "Added $dir to your PATH. Open a new terminal to use 'pkanban',"
            say "or use it in this one now with:"
        else
            say "$dir is not on your PATH. Add it, or for this terminal run:"
        fi
        say "  export PATH=\"$dir:\$PATH\""
    fi
    say ""
    say "Next, sign in (your browser opens to approve it):"
    say "  pkanban login"
    say ""
    say "Setting this up for an AI agent? Point it at $PKANBAN_SERVER/agents.md"
}

main "$@"
