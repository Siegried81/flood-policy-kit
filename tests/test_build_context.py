"""Tests for the context build script's own plumbing.

The measurements it assembles are tested in their modules; what is pinned here
is the script failing after the work is done.
"""

from __future__ import annotations

from pathlib import Path

from scripts import build_context


def test_a_relative_out_path_does_not_fail_after_the_table_is_written():
    """`--out data/processed/x.parquet` wrote the table, then raised in the
    summary line and exited 1 without printing a single note."""
    relative = Path("data/processed/context.test.parquet")
    assert build_context._shown(relative) == relative


def test_a_path_inside_the_repo_is_shown_relative_to_it():
    inside = build_context.ROOT / "data" / "processed" / "context.parquet"
    assert build_context._shown(inside) == Path("data/processed/context.parquet")
