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
