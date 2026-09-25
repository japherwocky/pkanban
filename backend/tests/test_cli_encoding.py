"""The CLI must survive a board name the console's code page cannot encode.

On Windows the standard streams default to the console code page, cp1252 on
most installs. A board named "sxswmi React -> Svelte Migration" with a real
U+2192 arrow crashed `pkanban board list` partway down the list: rich raised
UnicodeEncodeError mid-render, every board after the offending one was never
printed, and the result read as a short list rather than as a failure.
See issue #74.
"""

import io
import os
import sys
from unittest.mock import patch

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pkanban.output import configure_output_encoding

ARROW_NAME = "sxswmi React → Svelte Migration"


def legacy_stream():
    """A stdout like the one a stock Windows console hands Python."""
    buffer = io.BytesIO()
    return buffer, io.TextIOWrapper(buffer, encoding="cp1252", newline="")


def test_a_legacy_code_page_cannot_encode_the_name_at_all():
    """The failure this exists to prevent, so the fixture stays honest."""
    _, stream = legacy_stream()
    with pytest.raises(UnicodeEncodeError):
        stream.write(ARROW_NAME)
        stream.flush()


def test_configure_makes_the_name_printable():
    buffer, stream = legacy_stream()
    with patch.object(sys, "stdout", stream), patch.dict(os.environ, {}, clear=False):
        os.environ.pop("PYTHONIOENCODING", None)
        configure_output_encoding()
        print(ARROW_NAME, file=sys.stdout)
        sys.stdout.flush()

    assert "→" in buffer.getvalue().decode("utf-8")


def test_rich_inherits_the_reconfigured_encoding():
    """The real path: output goes through rich, which reads the stream."""
    from rich.console import Console

    buffer, stream = legacy_stream()
    with patch.object(sys, "stdout", stream), patch.dict(os.environ, {}, clear=False):
        os.environ.pop("PYTHONIOENCODING", None)
        configure_output_encoding()
        # Built after the reconfigure, exactly as the commands build theirs.
        console = Console(file=sys.stdout, width=200)
        console.print(ARROW_NAME)
        sys.stdout.flush()

    assert "→" in buffer.getvalue().decode("utf-8")


def test_everything_after_the_bad_name_still_prints():
    """The symptom was silent truncation, not a visible error."""
    buffer, stream = legacy_stream()
    with patch.object(sys, "stdout", stream), patch.dict(os.environ, {}, clear=False):
        os.environ.pop("PYTHONIOENCODING", None)
        configure_output_encoding()
        print(ARROW_NAME, file=sys.stdout)
        print("zzz-after-the-arrow", file=sys.stdout)
        sys.stdout.flush()

    assert "zzz-after-the-arrow" in buffer.getvalue().decode("utf-8")


def test_an_explicit_pythonioencoding_is_left_alone():
    """Someone piping into a code-page-bound tool chose that on purpose."""
    buffer, stream = legacy_stream()
    with patch.object(sys, "stdout", stream), patch.dict(
        os.environ, {"PYTHONIOENCODING": "cp1252"}
    ):
        configure_output_encoding()
        assert stream.encoding.lower().replace("-", "") == "cp1252"
        # Still must not raise: their encoding, but not their traceback.
        print(ARROW_NAME, file=sys.stdout)
        sys.stdout.flush()

    printed = buffer.getvalue().decode("cp1252")
    assert "?" in printed
    assert "Svelte Migration" in printed


def test_a_stream_that_cannot_be_reconfigured_is_skipped():
    """pytest's capture object, and anything else that is not a TextIOWrapper."""

    class Plain:
        encoding = "cp1252"

        def write(self, text):
            return len(text)

    with patch.object(sys, "stdout", Plain()), patch.object(sys, "stderr", Plain()):
        configure_output_encoding()  # must not raise


def test_a_detached_stream_is_survivable():
    _, stream = legacy_stream()
    stream.close()
    with patch.object(sys, "stdout", stream):
        configure_output_encoding()  # must not raise
