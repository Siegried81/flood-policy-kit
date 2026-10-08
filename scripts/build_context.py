"""Freeze the per-region context table: data/processed/context.parquet.

One row per region, holding what `exposure.parquet` deliberately does not: the
built-up surface in the way of the water, how much of a region drains into a
basin it shares with another country, and how the flood discharge moves under a
climate scenario. `src/assets.py`, `src/basins.py` and `src/climate.py` compute
these; this script is what turns them into something both UIs and the brief can
read.

**A second table, not more columns on the first.** Two reasons, and the second
is the load-bearing one.

* **Different grain.** `exposure.parquet` is one row per region x return period.
  Basin sharing and climate change are per region: putting them in the long
  table repeats each value once per period and invites someone to average them.

* **`api/main.py` picks the vulnerability index's indicators by looking for
  numeric columns** (`vulnerability_indicators`, minus `NON_INDICATOR_COLUMNS`).
  A climate percentage or an area share landing in a min-max-scaled weighted
  mean by accident would be a wrong number nobody would see. Keeping them out of
  that table keeps it from happening by construction rather than by remembering.

The join key is the region identifier, the same one `/api/exposure` reports.

**What this table is NOT.** It is not comparable, column to column, with the
exposure table's `exposed_pop`:

* the built-up figures are measured at ONE return period, named in the output,
  not at every one;
* they are measured on the hazard raster **as masked**, the same way the
  exposure table is, so that at least is like for like;
* the climate columns are a change in river DISCHARGE, not in depth or extent -
  the direction and size of a change, never a future headcount.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import geopandas as gpd
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.build_exposure import (  # noqa: E402
    DEFAULT_MIN_DEPTH_M,
    DEFAULT_STRIPES,
    PERMANENT_WATER,
    SPURIOUS_AREAS,
    _exposure_one_period,
    boundaries,
    hazard_paths,
)
from src import apsfr, assets, basins, climate, demographics  # noqa: E402

OUT = ROOT / "data" / "processed" / "context.parquet"
CLIMATE_DIR = ROOT / "data" / "raw" / "download" / "cds_hydrology_projections"

#: The return period the built-up figures are measured at. 100 years because it
#: is the planning standard and the one every measured figure in this repo uses;
#: named in the output so a reader cannot mistake it for all of them.
DEFAULT_RETURN_PERIOD = 100


def _built(admin: gpd.GeoDataFrame, return_period: int, min_depth_m: float,
           stripes: int):
    """Built-up surface exposed at one return period, or a reason it is absent.

    Measured through `_exposure_one_period`, the same function that measures
    population, with the built-up raster in the population slot. That is not a
    trick: GHS-BUILT-S is on exactly the same 1 km Mollweide grid as GHS-POP and
    square metres are as summable as people. What it buys is parity - the same
    windowing, the same masking of permanent water and spurious areas, and the
    same extrapolation - so `exposed_built_m2` and `exposed_pop` can appear in
    one sentence. `assets.built_exposure` on a raw raster cannot, because it
    would count the river channel as flooded ground.

    Returns `(frame, note)`. A missing archive is not fatal: the basin and
    climate halves are independent of it, and a partial table that says what is
    missing is more useful on a hackathon morning than a traceback.
    """
    try:
        path = assets.built_path()
    except SystemExit as exc:
        return None, str(exc)
    periods = hazard_paths()
    if return_period not in periods:
        return None, (
            f"no hazard raster for RP{return_period}; have {sorted(periods)}"
        )
    measured = _exposure_one_period(
        periods[return_period], path, admin,
        stripes=stripes, min_depth_m=min_depth_m, mode="fraction",
        masks=[PERMANENT_WATER, SPURIOUS_AREAS],
    )
    total = assets.total_built_surface(path, admin)
    observed = pd.to_numeric(measured["exposed_pop"], errors="coerce")
    frame = pd.DataFrame(
        {
            f"exposed_built_m2_rp{return_period}": observed,
            "built_total_m2": pd.to_numeric(total, errors="coerce"),
        },
        index=admin.index,
    )
    denominator = frame["built_total_m2"]
    frame[f"built_share_exposed_rp{return_period}"] = observed.divide(
        denominator.where(denominator > 0)
    ).clip(upper=1.0)
    return frame, None


def _basins(admin: gpd.GeoDataFrame):
    """Shared-basin shares, or a reason they are absent.

    The districts come from a cached EEA service; an uncached miss takes about
    two minutes and needs the network, so a failure here is reported rather than
    raised - see `config/sources.yaml` for why it cannot be pre-fetched by
    `src.fetch`.
    """
    try:
        districts = basins.districts()
    except basins.BasinsUnavailable as exc:
        return None, str(exc)
    return basins.shared_basin_exposure(admin, districts), None


def _climate(admin: gpd.GeoDataFrame, variable: str, period: str):
    """Ensemble change for one variable and period, or a reason it is absent.

    Every file in `CLIMATE_DIR` matching the variable and period is treated as
    an ensemble member, which is the point: a single member's regional figure
    moves by hundreds of percent between periods and says nothing.
    """
    if not CLIMATE_DIR.exists():
        return None, f"{CLIMATE_DIR.relative_to(ROOT)} is absent"
    members = []
    for path in sorted(CLIMATE_DIR.glob("*.nc")):
        try:
            fields = climate.describe(path)
        except ValueError:
            continue
        if fields["variable"] == variable and fields["period"] == period:
            members.append(path)
    if not members:
        return None, (
            f"no {variable} file for {period} in "
            f"{CLIMATE_DIR.relative_to(ROOT)} - fetch it from the CDS form"
        )
    frame = climate.ensemble_change_by_region(admin, members)
    frame.columns = [f"{c}_{period.replace('-', '_')}" for c in frame.columns]
    return frame, f"{len(members)} member(s) for {period}"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--return-period", type=int, default=DEFAULT_RETURN_PERIOD,
        help=f"Return period for the built-up figures (default "
             f"{DEFAULT_RETURN_PERIOD}). One, not all nine: the columns are named "
             f"after it so the table cannot be read as covering every scenario.",
    )
    parser.add_argument(
        "--min-depth-m", type=float, default=DEFAULT_MIN_DEPTH_M,
        help=f"Depth above which a cell counts as flooded (default "
             f"{DEFAULT_MIN_DEPTH_M}). Keep it equal to the exposure table's, or "
             f"the two halves of a brief disagree about what flooded means.",
    )
    parser.add_argument(
        "--climate-variable", default="rdisreturnmax50",
        help="CDS variable to aggregate (default rdisreturnmax50, the 50-year "
             "return value of annual maximum river discharge).",
    )
    parser.add_argument(
        "--climate-period", action="append",
        help="CDS period, repeatable. Default: every period present on disk.",
    )
    parser.add_argument(
        "--stripes", type=int, default=DEFAULT_STRIPES,
        help=f"Population-grid row windows for the built-up pass (default "
             f"{DEFAULT_STRIPES}). Memory only; the result does not depend on it.",
    )
    parser.add_argument("--out", type=Path, default=OUT)
    args = parser.parse_args()

    admin = boundaries()
    # `boundaries()` renames GISCO's fields to `nuts_id`, `region`, `country`.
    key = "nuts_id"
    table = pd.DataFrame({key: admin[key].values}, index=admin.index)
    notes: list[str] = []

    built, why = _built(
        admin, args.return_period, args.min_depth_m, args.stripes
    )
    if built is None:
        notes.append(f"built-up: SKIPPED - {why}")
    else:
        table = table.join(built)
        notes.append(
            f"built-up: RP{args.return_period} at >= {args.min_depth_m} m, "
            f"masked like the exposure table "
            f"({PERMANENT_WATER}, {SPURIOUS_AREAS})"
        )

    shared, why = _basins(admin)
    if shared is None:
        notes.append(f"basins: SKIPPED - {why}")
    else:
        table = table.join(shared)
        notes.append("basins: WFD districts, area shares in EPSG:3035")

    # What the Member State itself declared under Article 5 of the Floods
    # Directive, as opposed to what the hazard model shows. The pair is the
    # point: a region with exposed residents and no declared area is a
    # compliance question, which is a different kind of finding from a high
    # exposure count. It is NOT proof the designation is wrong - a State may have
    # assessed the area and concluded the risk is not significant, which the
    # Directive allows - so the column says what was declared and leaves the
    # conclusion to a human.
    try:
        declared = apsfr.declared_by_region(admin)
        table = table.join(declared)
        notes.append(
            f"apsfr: cycle {declared['apsfr_cycle'].iloc[0]}, "
            f"{int(declared['apsfr_declared'].sum())} of {len(admin)} units "
            "intersect a declared area"
        )
    except apsfr.ApsfrUnavailable as exc:
        notes.append(f"apsfr: SKIPPED - {exc}")

    # GDP is a DENOMINATOR, not an indicator: a region is not vulnerable for
    # being rich, and `api/main.py::vulnerability_indicators` would weight it as
    # one the moment it appeared on an exposure row. So it lives here, where it
    # turns an absolute loss into a share of regional wealth - the comparison a
    # European brief needs, because 100 MEUR means different things in Hainaut
    # and in Oberbayern. Eurostat publishes it for fewer NUTS3 units than it
    # publishes population for, and a missing unit stays missing.
    try:
        gdp = demographics.gdp_meur().reindex(admin[key].values)
        gdp.index = admin.index
        table = table.join(gdp)
        measured = int(gdp["gdp_meur"].notna().sum())
        notes.append(
            f"gdp: {measured} of {len(admin)} units, "
            f"MIO_EUR {gdp['gdp_meur_year'].dropna().iloc[0]}"
        )
    except demographics.EurostatUnavailable as exc:
        notes.append(f"gdp: SKIPPED - {exc}")

    periods = args.climate_period
    if not periods:
        periods = sorted({
            climate.describe(p)["period"]
            for p in CLIMATE_DIR.glob("*.nc")
            if _parses(p)
        }) if CLIMATE_DIR.exists() else []
    if not periods:
        notes.append("climate: SKIPPED - no readable .nc files")
    for period in periods:
        frame, why = _climate(admin, args.climate_variable, period)
        if frame is None:
            notes.append(f"climate {period}: SKIPPED - {why}")
        else:
            table = table.join(frame)
            notes.append(f"climate {period}: {why}")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    table.to_parquet(args.out, index=False)
    print(f"{len(table)} rows -> {args.out.relative_to(ROOT)} "
          f"({args.out.stat().st_size:,} B), {len(table.columns)} columns")
    for note in notes:
        print(f"  {note}")
    return 0


def _parses(path: Path) -> bool:
    """Whether a filename is a CDS member name. Keeps the archive out."""
    try:
        climate.describe(path)
    except ValueError:
        return False
    return True


if __name__ == "__main__":
    raise SystemExit(main())
