"""How a command reports its result: formatted for a person, or JSON for a script.

Every command used to print prose only, so scripting meant regexing sentences
like "Column created with id=17" -- one reworded string broke every caller.
`emit()` is the fork: a command hands over the API payload plus a callable that
renders the human version, and the selected mode decides which one is printed.
"""

import errno
import json
import os
import sys

from rich import print as rprint
from rich.console import Console
from rich.markup import escape


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
        # To stderr, like the JSON form: `pkanban card get 9 > card.txt` must
        # not capture "Card not found" as though it were the card. Escaped,
        # because a message echoing user text ("[/x]") is not markup; and
        # soft-wrapped, because rich would otherwise break a long line at the
        # terminal width, in the middle of a command someone means to copy.
        Console(stderr=True, highlight=False).print(
            f"[red]{escape(message)}[/red]", soft_wrap=True
        )


def esc(value):
    """Text from the server or the user, made safe to put inside rich markup.

    rich reads square brackets as style tags: "[bug] login fails" printed as
    " login fails", and a title containing "[/x]" raised MarkupError and
    aborted the command. Everything that did not come from this file's own
    source belongs inside esc() on its way into an f-string passed to rprint
    or console.print.
    """
    return escape(str(value))


def reader_left(error):
    """Whether an OSError means whoever was reading our output has gone.

    POSIX says so with EPIPE. Windows says EINVAL when the far end of a pipe is
    closed.
    """
    if isinstance(error, BrokenPipeError):
        return True
    return os.name == "nt" and getattr(error, "errno", None) == errno.EINVAL


def _sever(stream):
    """Point a stream's file descriptor at nothing.

    After a failed write the stream still holds the bytes it could not send,
    and Python flushes it once more as it exits: the same error, printed as an
    "Exception ignored" traceback, and the exit status replaced with 120.
    """
    try:
        devnull = os.open(os.devnull, os.O_WRONLY)
        try:
            os.dup2(devnull, stream.fileno())
        finally:
            os.close(devnull)
    except (OSError, ValueError, AttributeError):
        pass


def _flush(stream):
    """Flush a stream. False when its reader has gone, which is then handled."""
    try:
        stream.flush()
        return True
    except OSError as error:
        if not reader_left(error):
            raise
        _sever(stream)
        return False
    except ValueError:  # already closed
        return True


def _status_of(exit_):
    code = exit_.code
    if code is None:
        return 0
    if isinstance(code, int):
        return code
    print(code, file=sys.stderr)
    return 1


def run_quietly(run):
    """Run a command and return its exit status. A reader that left is not a crash.

    `pkanban card get 9 | head -1`, `... 2>&1 | head`, a terminal closed under a
    long listing: the reader goes, and the next write raises. Left alone that
    is a traceback, and 120 as the exit status. It is not a failure of ours, so
    it ends the command quietly.

    Which stream the reader was on decides the status. Output cut short on
    stdout is the reader's choice, so 0. If it was stderr, the command had
    something to report, so the status it was going to exit with stands: Click's
    own for a usage error, 1 for the rest.

    The flushes at the end matter as much as the except: a short output sits in
    the buffer until exit, so the error often arrives there, outside any
    handler, and can only be met by flushing here, deliberately.
    """
    status = 0
    try:
        run()
    except SystemExit as exit_:
        status = _status_of(exit_)
    except OSError as error:
        if not reader_left(error):
            raise
        if _flush(sys.stdout):
            # stdout is fine, so it was stderr that went, mid-report.
            context = error.__context__
            status = getattr(context, "exit_code", None) or 1
        else:
            status = 0

    _flush(sys.stdout)
    _flush(sys.stderr)
    return status
