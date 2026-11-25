"""Tests for scripts/generate_cli_docs.py.

CI runs the generator with --check, so anything that makes its output depend
on the environment rather than on the CLI turns into a spurious failure for
whoever happens to have a different library version installed.
"""

import os
import sys

import pytest

sys.path.insert(
    0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
)

from scripts.generate_cli_docs import type_name, is_bool  # noqa: E402


class _FakeType:
    def __init__(self, name):
        self.name = name


class _FakeParam:
    def __init__(self, name):
        self.type = _FakeType(name)


@pytest.mark.parametrize(
    "old,new",
    [
        # typer 0.15 reported the left name, 0.27 the right one. Both must
        # render identically or the docs churn on a library upgrade alone.
        ("text", "str"),
        ("integer", "int"),
        ("boolean", "bool"),
    ],
)
def test_type_label_is_the_same_across_typer_versions(old, new):
    assert type_name(_FakeParam(old)) == type_name(_FakeParam(new))


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("text", "str"),
        ("str", "str"),
        ("STRING", "str"),
        ("integer", "int"),
        ("int", "int"),
        ("boolean", "bool"),
        ("bool", "bool"),
        ("float", "float"),
    ],
)
def test_type_labels_normalise_to_stable_names(raw, expected):
    assert type_name(_FakeParam(raw)) == expected


def test_unknown_type_falls_back_to_its_own_name():
    """A type the map doesn't know should still render, just lowercased."""
    assert type_name(_FakeParam("DateTime")) == "datetime"


class _FakeDescriptor:
    def __init__(self, annotation, is_list=False, is_ranged=False):
        self.annotation = annotation
        self.is_list = is_list
        self.is_ranged = is_ranged


class _DescribedParam:
    """A typer 0.29+ parameter: no click `.type`, a `type_descriptor` instead."""

    def __init__(self, *args, **kwargs):
        self.type_descriptor = _FakeDescriptor(*args, **kwargs)


@pytest.mark.parametrize(
    "click_name,descriptor",
    [
        # Left, what click's type reported up to typer 0.28; right, what
        # 0.29 carries for the same parameter. The CI break of 2026-11-25.
        ("str", _DescribedParam(str)),
        ("int", _DescribedParam(int)),
        ("bool", _DescribedParam(bool)),
        ("float", _DescribedParam(float)),
        ("str", _DescribedParam(list[str], is_list=True)),
        ("int range", _DescribedParam(int, is_ranged=True)),
    ],
)
def test_typer_without_click_labels_types_the_same(click_name, descriptor):
    assert type_name(descriptor) == type_name(_FakeParam(click_name))


def test_typer_without_click_still_detects_flags():
    assert is_bool(_DescribedParam(bool)) is True
    assert is_bool(_DescribedParam(int)) is False


@pytest.mark.parametrize("raw", ["boolean", "bool"])
def test_flags_are_detected_under_either_spelling(raw):
    """usage_line() renders a flag without a value placeholder; missing this
    on a newer typer would print `[--json JSON]` for a boolean flag."""
    assert is_bool(_FakeParam(raw)) is True


@pytest.mark.parametrize("raw", ["text", "integer", "str", "int"])
def test_non_flags_are_not_detected_as_flags(raw):
    assert is_bool(_FakeParam(raw)) is False


def test_generated_docs_are_current():
    """Mirrors CI's `--check` step, so drift fails locally too."""
    from scripts.generate_cli_docs import build_pages, REPO_ROOT

    for path, content in build_pages().items():
        target = REPO_ROOT / path
        assert target.exists(), f"{path.as_posix()} has not been generated"
        assert target.read_text(encoding="utf-8") == content, (
            f"{path.as_posix()} is out of date -- run scripts/generate_cli_docs.py"
        )
