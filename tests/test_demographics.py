"""Tests for the Eurostat indicator join.

The failure modes pinned here are the ones where a wrong number still looks like
a number: an age share inflated by overlapping buckets, a value silently landing
on the wrong region, a vintage that drifts into the vulnerability index, and a
missing breakdown reported as "nobody is old here".

No network: `requests.get` is never reached, because `fetch` is monkeypatched or
the cube is passed directly.
"""

from __future__ import annotations

import json

import pandas as pd
import pytest

from src import demographics


def _cube(ids, sizes, categories, values, label=None):
    """A JSON-stat 2.0 payload, shaped like Eurostat's real one.

    `values` is the sparse dict Eurostat actually sends: keys are flat row-major
    offsets as STRINGS, and an absent key means "not published".
    """
    return {
        "class": "dataset",
        "version": "2.0",
        "id": ids,
        "size": sizes,
        "value": values,
        "dimension": {
            dim: {"category": {"index": {code: i for i, code in enumerate(codes)}}}
            for dim, codes in zip(ids, categories)
        },
        "label": label or "",
    }


# --- the sparse cube ------------------------------------------------------------

def test_a_hole_in_the_cube_does_not_shift_every_later_value():
    """The bug this decoder exists to make impossible.

    Eurostat sends values keyed by flat offset, and a region it does not publish
    is simply absent. Reading `payload["value"].values()` in order and zipping
    them against the geo list moves every figure after the hole onto the wrong
    region - and nothing downstream looks wrong, because every number is a real
    number for some region.

    Here BE211 is unpublished. Zipping would put BE212's 20 on BE212's neighbour.
    """
    cube = _cube(
        ids=["geo", "time"],
        sizes=[3, 1],
        categories=[["BE211", "BE212", "BE213"], ["2025"]],
        # offset 0 (BE211) absent on purpose
        values={"1": 20, "2": 30},
    )
    frame = demographics.tidy(cube)
    by_geo = frame.set_index("geo")["value"]

    assert "BE211" not in by_geo.index
    assert by_geo["BE212"] == 20
    assert by_geo["BE213"] == 30


def test_the_last_dimension_varies_fastest():
    """Row-major, like Eurostat. Getting this backwards transposes the cube, which
    on a square one is invisible."""
    cube = _cube(
        ids=["geo", "time"],
        sizes=[2, 2],
        categories=[["BE211", "BE212"], ["2024", "2025"]],
        values={"0": 1, "1": 2, "2": 3, "3": 4},
    )
    frame = demographics.tidy(cube).set_index(["geo", "time"])["value"]
    assert frame[("BE211", "2024")] == 1
    assert frame[("BE211", "2025")] == 2
    assert frame[("BE212", "2024")] == 3
    assert frame[("BE212", "2025")] == 4


# --- the overlapping age buckets ------------------------------------------------

def test_the_65_plus_buckets_do_not_overlap():
    """`demo_r_pjangrp3` publishes Y85-89, Y_GE85 and Y_GE90 side by side, and
    Y_GE85 is the sum of the other two. Measured on BE332 in 2025: 10,832 +
    6,723 = 17,555 exactly. Summing "every code from 65 up" counts the over-85s
    twice and reports 22.76% against a true 20.01%.

    Pinned as a property of the constant, because the arithmetic below cannot
    detect the error - double counting produces a larger, entirely plausible
    share."""
    assert "Y_GE85" in demographics.AGES_65_PLUS
    assert "Y85-89" not in demographics.AGES_65_PLUS
    assert "Y_GE90" not in demographics.AGES_65_PLUS


def _age_cube(values_by_age, geo="BE332"):
    ages = ["TOTAL", "Y65-69", "Y70-74", "Y75-79", "Y80-84", "Y_GE85", "Y85-89"]
    return _cube(
        ids=["geo", "age", "time"],
        sizes=[1, len(ages), 1],
        categories=[[geo], ages, ["2025"]],
        values={
            str(i): values_by_age[age]
            for i, age in enumerate(ages)
            if age in values_by_age
        },
    )


def test_the_share_over_65_is_the_disjoint_sum(monkeypatch):
    """The real BE332 figures, so the test fails if the bucket set ever changes."""
    cube = _age_cube({
        "TOTAL": 637220, "Y65-69": 36702, "Y70-74": 31616, "Y75-79": 26367,
        "Y80-84": 15253, "Y_GE85": 17555,
        # Present in the cube and deliberately NOT summed: it is inside Y_GE85.
        "Y85-89": 10832,
    })
    monkeypatch.setattr(demographics, "fetch", lambda *a, **k: cube)

    out = demographics.share_over_65()
    assert out.loc["BE332", "share_over_65"] == pytest.approx(127493 / 637220)
    assert round(out.loc["BE332", "share_over_65"] * 100, 2) == 20.01


def test_a_region_with_no_age_breakdown_is_not_a_region_with_no_old_people(monkeypatch):
    """A published total and a missing breakdown is "not measured". Reported as
    0.0 it would rank the region as the least vulnerable in Europe."""
    cube = _age_cube({"TOTAL": 637220, "Y65-69": 36702})  # the rest absent
    monkeypatch.setattr(demographics, "fetch", lambda *a, **k: cube)

    out = demographics.share_over_65()
    assert "BE332" not in out.index, "a partial breakdown must not become a share"


# --- the vintage ----------------------------------------------------------------

def test_the_vintage_is_text_so_it_cannot_become_an_indicator(monkeypatch):
    """`vulnerability_indicators` scans for numeric columns. A year stored as an
    integer would be offered as an indicator meaning "a more recent census makes
    residents more vulnerable" - which is the `total_pop` trap again, and this
    time it is excluded by dtype rather than by remembering a list."""
    cube = _age_cube({
        "TOTAL": 100.0, "Y65-69": 10.0, "Y70-74": 5.0, "Y75-79": 3.0,
        "Y80-84": 1.0, "Y_GE85": 1.0,
    })
    monkeypatch.setattr(demographics, "fetch", lambda *a, **k: cube)

    out = demographics.share_over_65()
    # The contract is "not numeric", which is what `vulnerability_indicators`
    # tests, rather than a dtype name: pandas 3 stores text as StringDtype and
    # pandas 2 as object, and both satisfy it.
    assert out["share_over_65_year"].dtype.kind not in "if"
    assert out["share_over_65_year"].iloc[0] == "2025"

    from api.main import vulnerability_indicators
    offered = vulnerability_indicators(out.reset_index())
    assert offered == ["share_over_65"]


def test_the_latest_year_is_the_latest_one_with_values(monkeypatch):
    """Not `max(time)`: the cube advertises years that are entirely unpublished
    at NUTS3, and picking one returns an empty indicator."""
    ages = ["TOTAL", "Y65-69", "Y70-74", "Y75-79", "Y80-84", "Y_GE85"]
    times = ["2024", "2025", "2026"]
    values = {}
    for a, age in enumerate(ages):
        # 2026 (offset 2 within each age) left unpublished throughout.
        values[str(a * len(times) + 0)] = 10.0
        values[str(a * len(times) + 1)] = 20.0
    cube = _cube(
        ids=["geo", "age", "time"],
        sizes=[1, len(ages), len(times)],
        categories=[["BE332"], ages, times],
        values=values,
    )
    monkeypatch.setattr(demographics, "fetch", lambda *a, **k: cube)
    assert demographics.share_over_65()["share_over_65_year"].iloc[0] == "2025"


# --- the NUTS2 poverty rate -----------------------------------------------------

def test_the_poverty_rate_says_it_is_a_nuts2_figure(monkeypatch):
    """`ilc_li41` is published at NUTS2 and the kit works at NUTS3. Applying a
    province's rate to its arrondissements is defensible; doing it silently is
    not, so the level travels with the figure."""
    poverty = _cube(
        ids=["geo", "time"],
        sizes=[2, 1],
        categories=[["BE33", "BE21"], ["2025"]],
        values={"0": 14.6, "1": 7.2},
    )
    ages = _age_cube({
        "TOTAL": 100.0, "Y65-69": 10.0, "Y70-74": 5.0, "Y75-79": 3.0,
        "Y80-84": 1.0, "Y_GE85": 1.0,
    })
    # `vulnerability_indicators` pulls two datasets, so the stub dispatches on
    # which one was asked for: one cube for both would feed NUTS2 poverty rows
    # to the NUTS3 age filter and silently produce an empty indicator.
    cubes = {"demo_r_pjangrp3": ages, "ilc_li41": poverty}
    monkeypatch.setattr(demographics, "fetch", lambda dataset, **k: cubes[dataset])

    out = demographics.vulnerability_indicators(["BE332", "BE213", "FR101"])
    assert out.loc["BE332", "poverty_rate"] == pytest.approx(14.6)
    assert out.loc["BE213", "poverty_rate"] == pytest.approx(7.2)
    assert "NUTS2" in out.loc["BE332", "poverty_rate_level"]
    # A region Eurostat does not publish stays missing rather than inheriting
    # someone else's rate.
    assert pd.isna(out.loc["FR101", "poverty_rate"])


def test_the_two_indicators_keep_their_published_units(monkeypatch):
    """`poverty_rate` is a percentage and `share_over_65` a fraction, on purpose.

    Eurostat publishes the at-risk-of-poverty rate as 14.6, not 0.146, and a
    brief quoting "14.6%" has to match the source. The age share is computed here
    and is a ratio. So the two travel on different scales - 14.6 beside 0.19 for
    the same region - which looks like a defect and is not; the composite index
    min-max rescales each indicator from its own extremes, so the unit cannot
    reorder it. This test exists so that "normalising" one of them later is a
    deliberate act with a failing test in front of it, and not a tidy-up.
    """
    poverty = _cube(
        ids=["geo", "time"], sizes=[1, 1],
        categories=[["BE33"], ["2025"]], values={"0": 14.6},
    )
    ages = _age_cube({
        "TOTAL": 100.0, "Y65-69": 10.0, "Y70-74": 5.0, "Y75-79": 3.0,
        "Y80-84": 1.0, "Y_GE85": 1.0,
    })
    cubes = {"demo_r_pjangrp3": ages, "ilc_li41": poverty}
    monkeypatch.setattr(demographics, "fetch", lambda dataset, **k: cubes[dataset])

    out = demographics.vulnerability_indicators(["BE332"])
    assert out.loc["BE332", "poverty_rate"] == pytest.approx(14.6), (
        "a percentage, as Eurostat publishes it"
    )
    assert out.loc["BE332", "share_over_65"] == pytest.approx(0.20), (
        "a fraction, computed here from the disjoint age bands"
    )


# --- the refusal ----------------------------------------------------------------

def test_an_unreachable_eurostat_raises_rather_than_returning_nothing(monkeypatch, tmp_path):
    """An empty frame here becomes a missing indicator, which becomes a
    vulnerability index built on fewer axes than the brief claims - silently.
    The build has to stop."""
    monkeypatch.setattr(demographics, "CACHE_DIR", tmp_path)

    class _Boom:
        def get(self, *a, **k):
            raise OSError("connection refused")

    monkeypatch.setattr(demographics, "requests", _Boom())
    with pytest.raises(demographics.EurostatUnavailable, match="connection refused"):
        demographics.fetch("demo_r_pjangrp3")


def test_a_payload_without_a_cube_is_refused(monkeypatch, tmp_path):
    """A 200 from this host is not proof of data: an error page parses as JSON."""
    monkeypatch.setattr(demographics, "CACHE_DIR", tmp_path)

    class _Resp:
        status_code = 200

        def json(self):
            return {"error": "no data"}

    class _Session:
        def get(self, *a, **k):
            return _Resp()

    monkeypatch.setattr(demographics, "requests", _Session())
    with pytest.raises(demographics.EurostatUnavailable, match="no JSON-stat cube"):
        demographics.fetch("demo_r_pjangrp3")


def test_a_cached_answer_is_reused_without_a_request(monkeypatch, tmp_path):
    """The freeze the whole kit rests on: an indicator that changes between two
    runs of the same build breaks every figure quoted from the first."""
    monkeypatch.setattr(demographics, "CACHE_DIR", tmp_path)
    cube = _cube(["geo"], [1], [["BE332"]], {"0": 1})
    (tmp_path / "demo_r_pjangrp3.json").write_text(json.dumps(cube), encoding="utf-8")

    class _Boom:
        def get(self, *a, **k):
            raise AssertionError("a cached answer must not reach the network")

    monkeypatch.setattr(demographics, "requests", _Boom())
    assert demographics.fetch("demo_r_pjangrp3") == cube
