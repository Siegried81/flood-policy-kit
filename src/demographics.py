"""Eurostat indicators at NUTS3, so the vulnerability index has something to weigh.

**Why this module exists.** `config/sources.yaml` has declared
`eurostat_population_by_age`, `eurostat_poverty` and `eurostat_gdp_nuts3` since
the start, all three `access: api`, and nothing in the repo called them. The cost
of that was not a missing column: `api/main.py::vulnerability_indicators` offered
exactly one indicator, `exposed_pop`, so the composite index was a weighted mean
of one column - which is that column - and `sensitivity` certified all 1,338
measured regions "robust" at any perturbation, because rescaling one term never
reorders it. The ranking needs a second axis before it means anything.

**What belongs here and what does not.** These are properties of the PEOPLE in a
region, which is what a vulnerability indicator is. `exposed_pop` is a property of
the flood. Both belong in `exposure.parquet`, where the index can see them. GDP is
neither - it is a denominator, and a region is not vulnerable for being rich - so
`gdp_meur` goes to `context.parquet` with the other qualifiers.

**Vintage columns are strings on purpose.** `vulnerability_indicators` picks the
index's inputs by scanning for numeric columns, so a year stored as an integer
would silently become a vulnerability indicator meaning "a more recent census
makes residents more vulnerable". Stored as text it is excluded by construction
rather than by remembering to add it to a list.

**The responses are cached to disk**, under `data/processed/eurostat_cache/`, for
the same reason `src/rdh.py` caches: the build has to be repeatable on a venue
network that is not there, and an indicator that changes between two runs of the
same build breaks the freeze the whole kit rests on.
"""

from __future__ import annotations

import json
from typing import Any

import pandas as pd
import requests

from src.data_io import DATA

CACHE_DIR = DATA / "processed" / "eurostat_cache"
BASE = "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data"
TIMEOUT_S = 120

#: The 65-and-over age groups that do NOT overlap.
#:
#: `demo_r_pjangrp3` publishes `Y85-89`, `Y_GE85` and `Y_GE90` side by side, and
#: they are not disjoint. Measured on BE332 (arrondissement de Liège), 2025:
#: Y85-89 = 10,832 and Y_GE90 = 6,723, summing to exactly Y_GE85 = 17,555. So
#: "every code from 65 upwards" counts the over-85s twice and reports 22.76%
#: against a true 20.01% - 2.76 percentage points, in the direction that makes a
#: region look more vulnerable than it is.
#:
#: `Y_GE65` exists as a code and returns an EMPTY series at NUTS3, so there is no
#: ready-made bucket to use instead. Checked 2026-10-07.
AGES_65_PLUS = ("Y65-69", "Y70-74", "Y75-79", "Y80-84", "Y_GE85")


class EurostatUnavailable(RuntimeError):
    """Eurostat did not answer with data. Raised rather than returning empty.

    An empty frame here becomes a missing indicator, which becomes a vulnerability
    index built on fewer axes than the brief says it was - silently. The build
    stops instead.
    """


def _cache_path(dataset: str, params: dict[str, Any]):
    """One file per dataset and parameter set, named so a human can read it."""
    tag = "_".join(f"{k}-{v}" for k, v in sorted(params.items()))
    safe = "".join(c if c.isalnum() or c in "-_" else "." for c in tag)
    return CACHE_DIR / f"{dataset}{('__' + safe) if safe else ''}.json"


def fetch(dataset: str, *, use_cache: bool = True, **params: Any) -> dict:
    """One JSON-stat 2.0 payload from the Eurostat dissemination API, cached.

    Open API, no credentials. Raises `EurostatUnavailable` on anything that is
    not a parseable payload, so a build never continues on half an indicator.
    """
    cache = _cache_path(dataset, params)
    if use_cache and cache.exists():
        return json.loads(cache.read_text(encoding="utf-8"))

    query = {"format": "JSON", "lang": "EN", **params}
    try:
        response = requests.get(f"{BASE}/{dataset}", params=query, timeout=TIMEOUT_S)
    except Exception as exc:  # network, DNS, timeout
        raise EurostatUnavailable(f"{dataset}: {exc}") from exc
    if response.status_code >= 400:
        raise EurostatUnavailable(f"{dataset}: HTTP {response.status_code}")
    try:
        payload = response.json()
    except ValueError as exc:
        raise EurostatUnavailable(f"{dataset}: response was not JSON") from exc
    if "value" not in payload or "dimension" not in payload:
        raise EurostatUnavailable(f"{dataset}: payload carries no JSON-stat cube")

    if use_cache:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        cache.write_text(json.dumps(payload), encoding="utf-8")
    return payload


def tidy(payload: dict) -> pd.DataFrame:
    """A JSON-stat 2.0 cube as one row per cell: a column per dimension, plus `value`.

    JSON-stat stores values in a SPARSE dict keyed by the flat row-major offset
    into the cube, not by coordinates - `{"0": 620167, "11": 637220}` - and a
    missing key means "not published", which is why the result is built by
    decoding the keys present rather than by reshaping a dense array. Reading the
    values in order and zipping them against the geo list is the bug this
    function exists to make impossible: it silently shifts every figure onto the
    wrong region as soon as one cell is unpublished, and nothing downstream looks
    wrong.
    """
    ids = payload["id"]
    sizes = payload["size"]
    codes = [
        [code for code, _ in sorted(
            payload["dimension"][dim]["category"]["index"].items(),
            key=lambda item: item[1],
        )]
        for dim in ids
    ]

    rows = []
    for flat, value in payload["value"].items():
        remaining = int(flat)
        position = []
        # Row-major: the LAST dimension varies fastest, so it comes off first.
        for size in reversed(sizes):
            remaining, index = divmod(remaining, size)
            position.append(index)
        position.reverse()
        row = {dim: codes[i][position[i]] for i, dim in enumerate(ids)}
        row["value"] = value
        rows.append(row)
    return pd.DataFrame(rows)


def _latest(frame: pd.DataFrame) -> tuple[pd.DataFrame, str]:
    """The most recent year that actually carries values, and which one it was.

    Not `max(time)`: the cube advertises years that are entirely unpublished at
    NUTS3, and selecting one of those returns an empty indicator that reads as
    "nobody is old here".
    """
    if frame.empty:
        raise EurostatUnavailable("no values in the cube at all")
    counts = frame.groupby("time")["value"].count()
    year = str(counts[counts > 0].index.max())
    return frame[frame["time"] == year], year


def share_over_65(*, use_cache: bool = True) -> pd.DataFrame:
    """Share of residents aged 65 or over, per NUTS3 region.

    The equity lens the brief needs: who, not how many. Older residents are
    harder to evacuate and over-represented in flood mortality, which is why this
    is an indicator and `total_pop` is a denominator.

    Returns `share_over_65` in [0, 1] and `share_over_65_year` as TEXT - see the
    module docstring for why the vintage is not a number.
    """
    payload = fetch(
        "demo_r_pjangrp3", use_cache=use_cache, sex="T", unit="NR",
    )
    frame = tidy(payload)
    frame = frame[frame["geo"].str.len() == 5]  # NUTS3 only, not country or NUTS2
    frame, year = _latest(frame)

    total = frame[frame["age"] == "TOTAL"].set_index("geo")["value"]
    older = (
        frame[frame["age"].isin(AGES_65_PLUS)]
        .groupby("geo")["value"]
        .sum()
    )
    # A region that published a total but no age breakdown is NOT a region with
    # no older residents, so it stays NaN rather than becoming 0.0.
    counted = frame[frame["age"].isin(AGES_65_PLUS)].groupby("geo")["age"].nunique()
    older = older.where(counted == len(AGES_65_PLUS))

    out = pd.DataFrame({"share_over_65": older / total.where(total > 0)})
    out["share_over_65_year"] = year
    return out.dropna(subset=["share_over_65"])


def poverty_rate(*, use_cache: bool = True) -> pd.DataFrame:
    """At-risk-of-poverty rate, published at NUTS2 and applied to its NUTS3 children.

    `ilc_li41` is NUTS2. A vulnerability index that mixes levels has to SAY so -
    the assumption that an arrondissement carries its province's poverty rate is
    defensible, and hiding it is not. So the level travels with the figure in
    `poverty_rate_level`, as text, and the brief can print it.

    **The unit is a PERCENTAGE, 0 to 100, as Eurostat publishes it** - while its
    sibling indicator `share_over_65` is a fraction, 0 to 1. Measured on the real
    data: `poverty_rate` spans 1.4 to 50.7 and `share_over_65` 0.027 to 0.372, so
    a table printing both side by side shows 14.0 next to 0.19 for the same
    region and reads as a mistake. It is not converted here, because Eurostat's
    own figure is the percentage and a brief quoting "14%" must match the source.
    The composite index is unaffected either way - `vulnerability._min_max`
    rescales every indicator to [0, 1] from its own extremes, so a linear change
    of unit cannot reorder it - but anything that DISPLAYS the two columns has to
    label them, and nothing may average them raw.

    Returns a frame indexed by NUTS3 code, which is the kit's working unit: the
    mapping is the first four characters, because a NUTS3 code is its NUTS2
    parent plus one digit.
    """
    payload = fetch("ilc_li41", use_cache=use_cache)
    frame = tidy(payload)
    frame = frame[frame["geo"].str.len() == 4]  # NUTS2 only
    frame, year = _latest(frame)
    by_nuts2 = frame.groupby("geo")["value"].mean()

    out = by_nuts2.rename("poverty_rate").to_frame()
    out["poverty_rate_year"] = year
    out["poverty_rate_level"] = "NUTS2, applied to its NUTS3 children"
    return out


def gdp_meur(*, use_cache: bool = True) -> pd.DataFrame:
    """GDP at current market prices, million EUR, per NUTS3 region.

    A denominator, never an indicator: a region is not vulnerable for being rich.
    It belongs in `context.parquet`, where it turns an absolute loss into a share
    of regional wealth - the comparison a European brief needs, because the same
    100 MEUR means different things in Hainaut and in Oberbayern.

    `MIO_EUR`, `MIO_PPS` and `EUR_HAB` are three different numbers, so the unit is
    pinned here rather than left to the API's default.
    """
    payload = fetch("nama_10r_3gdp", use_cache=use_cache, unit="MIO_EUR")
    frame = tidy(payload)
    frame = frame[frame["geo"].str.len() == 5]
    frame, year = _latest(frame)
    out = frame.set_index("geo")[["value"]].rename(columns={"value": "gdp_meur"})
    out["gdp_meur_year"] = year
    return out


def vulnerability_indicators(
    nuts_ids: pd.Index | list[str], *, use_cache: bool = True
) -> pd.DataFrame:
    """The indicator columns for `exposure.parquet`, reindexed onto `nuts_ids`.

    Only the two that are properties of the people: the share of older residents
    and the at-risk-of-poverty rate. A region Eurostat does not publish comes back
    NaN, which `indicator_coverage` already reports as partial rather than
    treating as a zero.
    """
    index = pd.Index(nuts_ids, name="nuts_id")
    older = share_over_65(use_cache=use_cache)
    poverty = poverty_rate(use_cache=use_cache)

    out = older.reindex(index)
    # NUTS3 to its NUTS2 parent: the code is the parent plus one digit.
    parents = pd.Series(index.str[:4], index=index)
    for column in ("poverty_rate", "poverty_rate_year", "poverty_rate_level"):
        out[column] = parents.map(poverty[column])
    return out
