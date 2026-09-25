"""How a command reports its result: formatted for a person, or JSON for a script.

Every command used to print prose only, so scripting meant regexing sentences
like "Column created with id=17" -- one reworded string broke every caller.
`emit()` is the fork: a command hands over the API payload plus a callable that
renders the human version, and the selected mode decides which one is printed.
"""

import json
import os
import sys

from rich import print as rprint


def configure_output_encoding():
    """Let the standard streams carry any character a board name can hold.

    On Windows the standard streams default to the console code page -- cp1252
    on most installs -- so one non-ASCII character in a board or card name
    raised UnicodeEncodeError partway through printing. The list stopped at
    that row, which read as a short board list rather than as a failure, and
    every board after it was simply missing.

    This is PYTHONIOENCODING=utf-8, the documented workaround, applied
    in-process so that nobody has to know to set it. It has to happen before
    anything constructs a rich Console, which reads its encoding from the
    stream it is given.

    An explicitly set PYTHONIOENCODING is left alone. Someone piping into a
    tool that demands a particular code page chose that on purpose, and this
    should be a better default rather than an override. Their stream still
    gets errors="replace", so the worst case there is a "?" in a board name
    instead of a traceback that loses every row after it.
    """
    chosen = bool(os.environ.get("PYTHONIOENCODING", "").strip())
    for stream in (sys.stdout, sys.stderr):
        # Not a TextIOWrapper: pytest's capture objects, and anything else
        # that has replaced the stream with its own file-like.
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is None:
            continue
        try:
            if chosen:
                reconfigure(errors="replace")
            else:
                reconfigure(encoding="utf-8", errors="replace")
        except (ValueError, OSError):
            # Detached or closed. Nothing to fix here, and a later write will
            # fail loudly on its own if it matters.
            pass


# None means "nobody chose", so fall back to the environment. Set by --json.
_json_output = None


def set_json_output(enabled):
    global _json_output
    _json_output = None if enabled is None else bool(enabled)


def json_output():
    """True when results should be printed as JSON.

    PKANBAN_OUTPUT is the fallback so a script can set the mode once for a whole
    run instead of threading --json through every invocation.
    """
    if _json_output is not None:
        return _json_output
    return os.environ.get("PKANBAN_OUTPUT", "").strip().lower() == "json"


def emit(payload, render):
    """Print the raw API `payload` as JSON, or call `render()` for a human."""
    if json_output():
        # Plain print, not rich's: rich reflows at the terminal width and
        # treats square brackets as markup, either of which corrupts JSON.
        print(json.dumps(payload, indent=2))
    else:
        render()


def emit_error(message, **extra):
    """Report a failure, as a JSON object on stderr when that's the mode.

    Errors stay off stdout in JSON mode so a script can parse stdout
    unconditionally, without first working out whether it holds a result.
    """
    if json_output():
        print(json.dumps({"error": message, **extra}, indent=2), file=sys.stderr)
    else:
        rprint(f"[red]{message}[/red]")
