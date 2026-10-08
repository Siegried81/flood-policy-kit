"""The map/dashboard deliverable, and the place the brief gets drafted.

Six tabs, in the order the two days actually run: look at the exposure, read what
qualifies it, find who is most vulnerable, draft a section against the evidence,
translate it, and keep the AI log as you go.

Two decisions worth stating, because a jury may ask:

**The numbers are frozen, visibly.** Thursday 17:30 is the freeze; after it,
every figure shown and every figure drafted comes from the same cached table. A
banner says which run it is. Teams lose these events because a number moves at
16:00 on Friday and the brief, the map and the pitch stop agreeing.

**Nothing drafted reaches the brief without a human pressing approve.** The draft
tab shows the grounding score and any invalid citation next to the text, so the
decision is informed rather than a rubber stamp.

**One scenario at a time, chosen above the tabs.** Return-period extents are
nested, so there is no figure that spans them. The region identifier and the
return period are therefore picked once for the whole page: the map and the
vulnerability ranking are then answers about the same flood, and both say which.

Run: `streamlit run app/streamlit_app.py`
"""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src import rag, svgmap, translate, usage_log  # noqa: E402
from src.toon_io import fit_rows, flatten, to_toon, token_report  # noqa: E402
from src.vulnerability import sensitivity  # noqa: E402

# Imported from the API rather than restated here. The vulnerability index is a
# weighted mean over whichever columns are selected, so the moment the two UIs
# offer different indicator lists they report different composite scores for the
# same region from the same frozen table. One list, one definition, no drift.
# It costs this app an import of fastapi, which is pure Python and already a hard
# requirement of the kit - unlike tiktoken, see the note in src/toon_io.py.
from api.main import climate_periods, vulnerability_indicators  # noqa: E402

st.set_page_config(page_title="Flood exposure, Europe", layout="wide")

EXPOSURE_CACHE = Path(__file__).resolve().parents[1] / "data" / "processed" / "exposure.parquet"
CONTEXT_CACHE = Path(__file__).resolve().parents[1] / "data" / "processed" / "context.parquet"
GEOMETRY_CACHE = Path(__file__).resolve().parents[1] / "data" / "processed" / "regions.geojson"


def _build_state(path: Path) -> float | None:
    """`None` when the artefact is absent, otherwise its mtime.

    The cache key for the three loaders below, and the reason they are written in
    two halves. `@st.cache_data` memoises the RETURN VALUE, so a loader that did
    its own `exists()` check cached the *absence* too: once the page had run
    while a table was missing, it kept answering "no exposure table yet" for the
    life of the process - after the build it tells the reader to run had finished
    and written the file. Measured 2026-10-08 while a test moved the tables aside
    for seventy seconds: a server that reran in that window never came back.
    The mtime is in the key for the other half of the same problem - a rebuilt
    table is a different table, and the banner above it claims to name the run on
    screen.
    """
    try:
        return path.stat().st_mtime
    except OSError:
        return None


def load_exposure() -> pd.DataFrame | None:
    """The frozen exposure table. Cached so every tab reads the same numbers.

    Parquet rather than CSV: it round-trips dtypes exactly, so a NUTS code never
    comes back as an integer with its leading zero gone - which would silently
    break every join and every citation back to a region.
    """
    state = _build_state(EXPOSURE_CACHE)
    return None if state is None else _load_exposure(state)


def load_context() -> pd.DataFrame | None:
    """The frozen per-region context table, or None when it was never built.

    A separate table behind a separate loader, deliberately never merged into the
    exposure frame: `vulnerability_indicators` picks the composite index's inputs
    by scanning numeric columns, so a climate percentage or a basin share joined
    onto `exposure` would become a min-max-scaled term in a weighted mean —
    "this region's rivers rise faster, therefore its residents are more
    vulnerable". Context qualifies an exposure figure; it is not an ingredient of
    one.

    Optional rather than required, because `scripts/build_exposure.py` and
    `scripts/build_context.py` are separate builds and the map must still open
    when only the first has run.
    """
    state = _build_state(CONTEXT_CACHE)
    return None if state is None else _load_context(state)


def load_geometry() -> list[dict] | None:
    """The polygons the choropleth draws, or None when they were never built.

    A third build, a third artefact: `scripts/build_geometry.py` is seconds over
    one boundary file while `build_exposure.py` is a multi-hour continental pass,
    and re-running the slow one to redraw a map would be absurd. Optional for the
    same reason the context table is - the page must open on a fresh clone and
    say what is missing rather than fail.
    """
    state = _build_state(GEOMETRY_CACHE)
    return None if state is None else _load_geometry(state)


# The cached halves. `_state` is the cache KEY and is deliberately unused in the
# body: it is the artefact's mtime, so a rebuilt file is a cache miss and a file
# that never moved is a hit.
@st.cache_data
def _load_exposure(_state: float) -> pd.DataFrame:
    return pd.read_parquet(EXPOSURE_CACHE)


@st.cache_data
def _load_context(_state: float) -> pd.DataFrame:
    return pd.read_parquet(CONTEXT_CACHE)


@st.cache_data
def _load_geometry(_state: float) -> list[dict]:
    return svgmap.load_features(GEOMETRY_CACHE)


def _freeze_banner(df: pd.DataFrame, key: str | None = None) -> None:
    """Say out loud which run is on screen. Half the failure mode is not knowing.

    The region identifier rides along here when there is only one of them. It
    used to have a selectbox of its own, which asked the reader to choose and
    then offered no choice; replacing that with a label just moved the dead
    control one step along. It is a property of the run, like the row count and
    the timestamp, so it belongs in the line that already states those.
    """
    stamp = datetime.fromtimestamp(EXPOSURE_CACHE.stat().st_mtime)
    keyed = f" · keyed on `{key}`" if key else ""
    st.caption(
        f"Frozen table · {len(df):,} rows · computed {stamp:%d %b %H:%M}{keyed} · "
        "every figure below and in the draft comes from this one run."
    )


def _directive_class(return_period: float) -> tuple[str, str]:
    """The Article 6(3) scenario a return period falls in, and whose reading it is.

    Directive 2007/60/EC, Article 6(3), names three scenarios for the flood
    hazard maps and fixes a number for exactly one of them: (b) "floods with a
    medium probability (likely return period ≥ 100 years)". It sets no return
    period for (a) "floods with a low probability, or extreme event scenarios"
    or (c) "floods with a high probability, where appropriate". So RP100 is the
    one period the Directive itself places; everything else is this kit's
    reading and has to be labelled as such, or a brief quotes a threshold the
    law never wrote. The kit reads below 100 years as the high-probability
    class and rarer than 100 years as the low/extreme one — while noting that
    by the letter of (b) every period of 100 years or more is "medium" too.
    """
    if return_period < 100:
        return (
            "high probability",
            "Art. 6(3)(c) — the kit's reading: the Directive fixes no return "
            "period for this class",
        )
    if return_period == 100:
        return (
            "medium probability",
            "Art. 6(3)(b), \"likely return period ≥ 100 years\" — the one class "
            "the Directive puts a number on",
        )
    return (
        "low probability / extreme",
        "Art. 6(3)(a) — the kit's reading: the Directive fixes no return period "
        "for this class, and by the letter of 6(3)(b) a period ≥ 100 years is "
        "also \"medium probability\"",
    )


exposure = load_exposure()
context = load_context()
st.title("Flood exposure across European regions")

if exposure is None:
    st.warning(
        f"No exposure table yet. Build one with `src.exposure.exposure_by_return_period` "
        f"and save it to `{EXPOSURE_CACHE.relative_to(Path.cwd()) if EXPOSURE_CACHE.is_relative_to(Path.cwd()) else EXPOSURE_CACHE}`. "
        "See docs/scope.md for the European setup."
    )
    st.stop()

# Both controls sit above the tabs, not inside the exposure tab, because every
# tab answers a question about ONE scenario. A ranking built on a different return
# period than the map on screen is a different answer to "who do we help first",
# and nothing on screen would say so. The React UI holds the same two values at
# app level for the same reason.
key_columns = [c for c in exposure.columns if c.lower() in {"nuts_id", "lau_id", "id"}]
if not key_columns:
    # Every figure here is per region, so without the identifier there is nothing
    # to show. Said plainly rather than left to fail on the first lookup.
    st.error(
        "No region identifier column in the frozen table — expected one of "
        f"`nuts_id`, `lau_id` or `id`, found `{'`, `'.join(map(str, exposure.columns))}`. "
        "Rebuild the table joined on the identifier the regions were fetched with."
    )
    st.stop()

# A selectbox with one option is a control that cannot be used: it asks the
# reader to choose and then offers no choice. A pan-European run carries only
# `nuts_id`, so the normal case is exactly one - and then the identifier is a
# property of the run, stated in the freeze banner beside the row count and the
# timestamp, and the return period gets the whole width. The selector comes back
# for a LAU zoom, where the table really does hold two.
one_identifier = len(key_columns) == 1
_freeze_banner(exposure, key_columns[0] if one_identifier else None)
if one_identifier:
    key = key_columns[0]
else:
    key = st.selectbox("Region identifier", key_columns)
periods = sorted(exposure["return_period"].unique()) if "return_period" in exposure else []
chosen = (
    st.select_slider("Return period (years)", periods, value=periods[-1])
    if periods
    else None
)
if chosen is not None:
    # The Directive's own vocabulary, beside the control that picks a period: a
    # brief that says "the 1-in-500 year flood" to an authority that maps "low
    # probability" scenarios has to say which of the two it means. The period
    # lists are read off the table on screen, not restated, so a run with other
    # periods still gets a true sentence.
    scenario, basis = _directive_class(chosen)
    frequent = [f"RP{int(p)}" for p in periods if p < 100]
    rare = [f"RP{int(p)}" for p in periods if p > 100]
    readings = []
    if frequent:
        readings.append(f"{', '.join(frequent)} as 'high probability' (6(3)(c))")
    if rare:
        readings.append(
            f"{', '.join(rare)} as 'low probability / extreme' (6(3)(a))"
        )
    kit_reading = (
        f" Reading {' and '.join(readings)} is this kit's, not the Directive's: "
        "it fixes no return period for either class, and by the letter of "
        "6(3)(b) every period of 100 years or more is also 'medium'."
        if readings
        else ""
    )
    st.caption(
        f"**RP{int(chosen)} is '{scenario}'** — {basis}. Directive 2007/60/EC, "
        "Article 6(3), names three scenarios for the flood hazard maps: (a) "
        "\"floods with a low probability, or extreme event scenarios\"; (b) "
        "\"floods with a medium probability (likely return period ≥ 100 "
        "years)\"; (c) \"floods with a high probability, where appropriate\". "
        "The Article fixes a number for (b) only, so RP100 and above is 'medium "
        f"probability' on the Directive's own words.{kit_reading}"
    )
# One period, everywhere. The extents are nested, so a figure taken over the whole
# table counts the core floodplain once per period.
view = exposure[exposure["return_period"] == chosen] if periods else exposure
# Defined beside `view` rather than inside a tab because two tabs read it.
# Streamlit re-runs the script top to bottom and `with` opens no scope, so every
# name a tab binds is a module-level name the next tab inherits. A flag set in
# one tab and read in another 440 lines down is a collision waiting for any
# intervening tab to bind the same name.
has_exposure = "exposed_pop" in view.columns
# Computed from the whole table, like /api/meta does, so the offered list does not
# depend on which period is selected.
indicators = vulnerability_indicators(exposure)

map_tab, context_tab, vuln_tab, draft_tab, translate_tab, log_tab = st.tabs(
    ["Exposure", "What qualifies it", "Who is most vulnerable",
     "Draft a brief section", "Translation", "AI usage log"]
)

# --- Exposure -------------------------------------------------------------------
with map_tab:
    st.info(
        "Return-period extents are **nested**: the 100-year zone contains the "
        "10-year one. Never add these together — compare them, or integrate over "
        "probability with `expected_annual_exposure`."
    )

    # A separate frame, not a rebinding of `view`: `view` is what the ranking tab
    # weights, and leaking a derived `exposed_share` column into it would make the
    # indicator list depend on which tab the reader opened first.
    shares = (
        view.assign(exposed_share=view["exposed_pop"] / view["total_pop"])
        if has_exposure and "total_pop" in view.columns
        else view
    )

    # --- the map, full width: a choropleth of Europe needs the room ------------
    st.subheader(f"Where the danger is — 1-in-{chosen} year flood")
    features = load_geometry()
    if features is None:
        st.warning(
            "No polygons to draw. Build them with "
            "`python scripts/build_geometry.py`, which writes "
            "`data/processed/regions.geojson` in seconds from one boundary file. "
            "`data/` is not committed, so a fresh clone has to build it."
        )
    elif key != "nuts_id":
        st.info(
            f"The geometry is keyed on `nuts_id` and the table is being read on "
            f"`{key}`, so there is nothing to join. Rebuild the geometry for this "
            "identifier, or switch the selector above back to `nuts_id`."
        )
    elif "exposed_share" not in shares.columns:
        st.warning(
            "No `exposed_share` to colour by — the frozen table is missing "
            "`exposed_pop` or `total_pop`."
        )
    else:
        # Two things can be mapped, and they are NOT the same quantity, so the
        # reader picks one and the legend says which. Exposure is people in the
        # way of water today; the climate layer is a change in river DISCHARGE,
        # which cannot be turned into a future headcount - a future flow in m3/s
        # does not index into the inundation maps the exposure figures come from.
        horizons = climate_periods(context) if context is not None else []
        layers = ["Exposed population, today"]
        if horizons:
            layers.append("Change in river discharge, by horizon")
        # Offered only when there are two. Without `context.parquet` there is no
        # horizon to colour, and a radio with one option is the dead control the
        # identifier selector used to be.
        layer = (
            st.radio("Colour the map by", layers, horizontal=True)
            if len(layers) > 1
            else layers[0]
        )

        if layer == layers[0]:
            # The share, not the headcount: an absolute choropleth of Europe is a
            # map of where the cities are, which nobody needs a model to draw.
            by_region = {
                str(code): (None if pd.isna(value) else float(value))
                for code, value in zip(shares[key], shares["exposed_share"])
            }
            palette, hatch, fmt = svgmap.PALETTE, (), None
            percent = True
            legend_note = (
                "**Classes are quantiles of the regions present, printed in the "
                "legend** — the distribution is far too skewed for a linear "
                "ramp, which would paint almost everything the palest colour."
            )
            label = f"share of residents exposed at RP{chosen}"
        else:
            names = [h["period"] for h in horizons]
            # A radio and not a `select_slider`: the slider's handle is a 12 px
            # dot with its value label 18 px ABOVE it, so a reader aiming at the
            # period they can see clicks the label and nothing moves. On a 639 px
            # viewport the handle also lands below the fold the moment this layer
            # is chosen, because the layer radio and the heading sit above it.
            # Measured in the browser: a full-width drag left the committed value
            # on the default while the keyboard arrows moved it fine. Three named
            # periods are three click targets, not a scale to drag along.
            horizon = st.radio(
                "Horizon", names, index=min(1, len(names) - 1), horizontal=True,
                help="Against the 1971-2000 reference. The default is the middle "
                     "horizon: the far one carries the largest number and the "
                     "least decision a planner can act on.",
            )
            summary = next(h for h in horizons if h["period"] == horizon)
            # `climate_periods` reports the period for a READER - "2041-2070" -
            # while `build_context.py` suffixes the columns "2041_2070". Using
            # the display form as a column key raised KeyError on the far
            # horizon, which is the one a jury asks about.
            suffix = horizon.replace("-", "_")
            indexed = context.set_index("nuts_id")
            median = indexed[f"change_pct_ensemble_median_{suffix}"]
            agrees = indexed[f"ensemble_agrees_on_sign_{suffix}"]
            by_region = {
                str(code): (None if pd.isna(value) else float(value))
                for code, value in median.items()
            }
            # Measured and the chains disagree about the DIRECTION is a third
            # state: not a colour to read flat, and not an absence either.
            hatch = [str(c) for c, ok in agrees.items() if ok is False or ok == 0]
            palette = svgmap.PALETTE_DIVERGING
            percent = False
            fmt = lambda v: f"{v:+.0f}%"  # noqa: E731 - one expression, read twice
            legend_note = (
                f"Median of the per-region ensemble medians over **{horizon}**, "
                f"from **{summary['members']} model chain(s)**, against the "
                "1971-2000 reference. A **change in discharge, not in depth or "
                "extent** — never a future headcount. Classes are quantiles, so "
                "the middle class is not centred on zero; read the legend. "
                f"**{summary['regions_agreeing_on_sign']:,} regions** have the "
                "chains agreeing on the sign; the rest are hatched."
            )
            label = f"change in river discharge, {horizon}"

        # An iframe, not `st.html`: `st.html` sanitises its body with DOMPurify
        # and the entire <svg> came back stripped — 1,345 paths enqueued, zero
        # `stHtml` nodes in the DOM, no console error, and a caption underneath
        # cheerfully reporting "1,338 regions coloured". Verified in the browser
        # on 2026-10-08. An iframe renders the markup as given.
        #
        # `st.iframe`, not `st.components.v1.html`: the old call logs "will be
        # removed after 2026-06-01", a date already behind us, and this is the
        # map's only rendering path. A string that matches no URL pattern is
        # embedded as raw HTML, which is what the SVG is.
        #
        # `height="content"`, never a fixed pixel count. The SVG carries
        # `width:100%;height:auto`, so its rendered height is the column width
        # times 620/900 - 739px in a 1,073px column, measured in the browser -
        # and a fixed 640 cut the whole legend off the bottom: all seven class
        # labels sat at y=718 with no scrollbar to reach them. A map whose
        # legend is off-screen is a map of unlabelled colours.
        st.iframe(
            svgmap.choropleth_svg(
                features, by_region, key="nuts_id", label=label,
                percent=percent, palette=palette, hatch=hatch, fmt=fmt,
            ),
            height="content",
        )
        drawn = sum(1 for v in by_region.values() if v is not None)
        off_map = svgmap.outermost(features)
        st.caption(
            f"{drawn:,} regions coloured, "
            f"{len(features) - drawn:,} grey. {legend_note} Grey is "
            "*not measured*, never a measured zero. Equal-area (EPSG:3035), so "
            "the north is not stretched. Hover a region for its figure."
        )
        if off_map:
            # Said, not dropped: a region missing from a picture with no note
            # reads as a region with nothing to report.
            st.caption(
                f"**{len(off_map)} regions are outside this viewport** and are "
                "in the table below, not on the map: French Guiana is in South "
                "America, Reunion and Mayotte in the Indian Ocean, the Azores, "
                "Madeira and the Canaries in the Atlantic, Svalbard and Jan "
                f"Mayen in the Arctic — {', '.join(off_map)}. Framing Europe "
                "around them would shrink the continent to a seventh of the "
                "picture (12,850 x 9,486 km against 4,680 x 4,029 km)."
            )

    # Outside the if/else, so it is said whether or not the polygons were
    # built: the claim it limits is the exposure figure, not the drawing.
    st.caption(
        "**A screening view at NUTS3, never the statutory map.** The flood "
        "hazard and flood risk maps that bind under Directive 2007/60/EC are "
        "the Member States' own, reported to the Commission and served by the "
        "EEA Flood Risk Areas Viewer — https://discomap.eea.europa.eu/floodsviewer/ "
        "— and WISE-Freshwater. Use those for a statutory hazard or risk map; "
        "use this page to decide where to look first."
    )

    left, right = st.columns([2, 1])
    with left:
        st.subheader(f"Ranked: exposed population, 1-in-{chosen} year flood")
        # Per inhabitant, not absolute: an absolute ranking just ranks by
        # population and tells a decision-maker nothing they did not know.
        if "exposed_share" in shares.columns:
            st.bar_chart(shares.nlargest(15, "exposed_share").set_index(key)["exposed_share"])
            st.caption("Share of residents exposed. Ranking by absolute count would just rank by size.")
        elif has_exposure:
            st.bar_chart(shares.nlargest(15, "exposed_pop").set_index(key)["exposed_pop"])
        else:
            st.warning("No `exposed_pop` column in the frozen table — nothing to chart.")
    with right:
        st.metric("Regions covered", f"{view[key].nunique():,}")
        # "—" rather than 0 when the column is absent: a figure the table does not
        # carry must not arrive looking like a figure that was measured as zero.
        st.metric(
            "Exposed, total",
            f"{view['exposed_pop'].sum():,.0f}" if has_exposure else "—",
        )
        # Surfaced rather than hidden: a region the raster does not cover is NOT a
        # region with nobody exposed, and presenting it as safe would be a lie.
        st.metric(
            "Not measured",
            int(view["exposed_pop"].isna().sum()) if has_exposure else "—",
            help="Regions with no raster coverage — not zeros.",
        )

    st.dataframe(
        shares.sort_values("exposed_pop", ascending=False) if has_exposure else shares,
        width="stretch",
    )

# --- Context --------------------------------------------------------------------
with context_tab:
    st.subheader("What qualifies the exposure figure")
    st.caption(
        "A second frozen table, built by `scripts/build_context.py`. Everything "
        "here describes the ground and the future around an exposure count "
        "without being one — which is exactly why it is not merged into the "
        "exposure table: the vulnerability index is a weighted mean over whatever "
        "numeric columns it finds."
    )

    if context is None:
        st.warning(
            "No context table yet. Build one with "
            "`python scripts/build_context.py` — it writes "
            "`data/processed/context.parquet` from the hazard rasters and the CDS "
            "NetCDFs. The map and the ranking do not need it, so the rest of this "
            "app works without it."
        )
    else:
        stamp = datetime.fromtimestamp(CONTEXT_CACHE.stat().st_mtime)
        st.caption(f"Context table · {len(context):,} regions · computed {stamp:%d %b %H:%M}")

        st.markdown("#### River discharge, against the 1971–2000 reference")
        st.info(
            "The only forward-looking layer in the kit, and it is **discharge, "
            "not depth**: a future flow in m³/s cannot be layered onto the "
            "inundation maps the exposure figures come from. What is defensible "
            "is the direction and size of the change, read beside today's "
            "exposure — never a future headcount quoted as if it had been "
            "measured."
        )

        # Imported from api/main.py rather than restated: the caveat a period
        # carries has to be the same sentence in both UIs, or the jury is shown
        # two different claims about one file.
        summaries = {entry["period"]: entry for entry in climate_periods(context)}
        if not summaries:
            st.warning(
                "The context table carries no climate columns — the build found "
                "no CDS NetCDF for any period."
            )
        else:
            period = st.selectbox("Period", list(summaries), index=len(summaries) - 1)
            summary = summaries[period]
            cells = st.columns(4)
            cells[0].metric(
                "Median change",
                f"{summary['median_change_pct']:+.1f}%"
                if summary["median_change_pct"] is not None
                else "—",
                help="Median of the per-region ensemble medians. A direction and a "
                     "size, not a projected discharge.",
            )
            cells[1].metric("Model chains", summary["members"])
            cells[2].metric("Regions measured", f"{summary['regions_measured']:,}")
            cells[3].metric(
                "Agreeing on sign",
                f"{summary['regions_agreeing_on_sign']:,}",
                help="Regions where every chain points the same way. Only these "
                     "license a sentence about the direction of the change.",
            )

            suffix = period.replace("-", "_")
            median_column = f"change_pct_ensemble_median_{suffix}"
            agrees_column = f"ensemble_agrees_on_sign_{suffix}"

            if summary["single_member"]:
                # The one caveat that cannot be dropped. Zero agreeing regions
                # from a single chain is not "the models disagree" — nothing was
                # ever compared. Said here because the metric above reads
                # identically in both cases.
                st.error(
                    f"**{period} has one model chain, so no region agrees with "
                    "anything.** One member is one plausible world, not a "
                    "projection: the median above is a real measurement and still "
                    "licenses no sentence about the direction of the change. Add a "
                    "second hydrological model for this period — the CDS archive "
                    "offers `VIC-WUR-EUR-11` beside `E-HYPEgrid-EUR-11` — and the "
                    "agreement count becomes readable."
                )
            elif agrees_column in context.columns and median_column in context.columns:
                agreeing = context[context[agrees_column].fillna(False)]
                st.markdown(
                    f"**Largest increases among the {len(agreeing):,} regions where "
                    f"every chain agrees on the direction.** The regions left out "
                    "are not regions with no change: they are regions where the "
                    "chains point different ways, which is a finding of its own."
                )
                columns = [c for c in (
                    "nuts_id",
                    median_column,
                    f"change_pct_ensemble_min_{suffix}",
                    f"change_pct_ensemble_max_{suffix}",
                ) if c in agreeing.columns]
                st.dataframe(
                    agreeing.nlargest(15, median_column)[columns],
                    width="stretch",
                )

        built_prefix = "built_share_exposed_rp"
        built_column = next(
            (c for c in context.columns if c.startswith(built_prefix)), None
        )
        if built_column:
            built_rp = built_column[len(built_prefix):]
            st.markdown(f"#### Exposed built-up surface, 1-in-{built_rp} year flood")
            st.caption(
                f"Measured at RP{built_rp} only, which is why the period is in the "
                "column name: read against a different scenario's headcount it is "
                "two floods in one sentence."
            )
            built = [c for c in ("nuts_id", f"exposed_built_m2_rp{built_rp}",
                                 "built_total_m2", built_column)
                     if c in context.columns]
            st.dataframe(
                context.nlargest(15, built_column)[built], width="stretch",
            )

        if "apsfr_share" in context.columns:
            st.markdown("#### Declared at risk by the Member State")
            st.caption(
                "Areas of Potential Significant Flood Risk, designated under "
                "Article 5 of the Floods Directive. Every other layer here "
                "measures what the water does; this one measures what a "
                "government said about it. **The share is comparable within a "
                "country, not between two**: the Directive sets what must be "
                "designated and leaves the geometry to the Member State, so the "
                "declared share of national territory runs from 99.9% (BE, one "
                "polygon over the whole country) to 0.004% (ES, CY, river "
                "reaches reported as ribbons). Read the column below as "
                "declared/undeclared, not as a ranking."
            )
            covered = context.get("apsfr_country_reported")
            if covered is not None:
                outside = context[~covered.fillna(False)]
                if len(outside):
                    # The caveat that stops a false accusation. Measured on the
                    # real service: the layer carries 26 country codes across both
                    # reporting cycles and Ireland is not one of them.
                    st.error(
                        f"**{len(outside):,} regions are in a country this dataset "
                        "never covered**, so their blank is not a finding about "
                        "that country. Ireland reports nothing here at all, for a "
                        "Member State that certainly designates areas. Their share "
                        "is left empty rather than set to zero."
                    )
            # The regions whose share exists at all, which is the denominator
            # the metric below is honest about: a blank share is a country the
            # layer never carried, not a State that declared nothing.
            with_share = context[context["apsfr_share"].notna()]
            undeclared = with_share[~with_share["apsfr_declared"].fillna(False)]
            st.metric(
                "Covered regions with no declared area",
                f"{len(undeclared):,} of {len(with_share):,}",
                help="A compliance question, not a verdict: a State may have "
                     "assessed the area and concluded the risk is not significant, "
                     "which the Directive allows.",
            )
            # The UNDECLARED regions, not the most-declared ones: ranking by
            # share descending fills the table with regions a State covered
            # entirely, which is the opposite of the question this section asks.
            columns = [c for c in ("nuts_id", "apsfr_share", "apsfr_declared",
                                   "apsfr_country_reported", "apsfr_cycle")
                       if c in context.columns]
            st.dataframe(undeclared[columns].head(15), width="stretch")

        if "shared_basin_share" in context.columns:
            st.markdown("#### Shared river basins")
            st.caption(
                "The share of a region's area in a basin that crosses a national "
                "border, off the 2016 River Basin Management Plans — a vintage, "
                "like NUTS. Where this is high, a measure taken alone upstream is "
                "a measure taken on someone else's territory."
            )
            basins_columns = [c for c in ("nuts_id", "shared_basin_share",
                                          "basin_area_share", "basin_countries_max",
                                          "shared_with")
                              if c in context.columns]
            st.dataframe(
                context.nlargest(15, "shared_basin_share")[basins_columns],
                width="stretch",
            )

# --- Vulnerability --------------------------------------------------------------
with vuln_tab:
    st.subheader("Composite vulnerability, with its own sensitivity")
    st.caption(
        "A composite index is a value judgement wearing a number: the weights "
        "decide who counts as vulnerable. So the ranking is re-run under perturbed "
        "weights and each row is labelled robust or indicative."
    )
    if chosen is not None:
        st.info(
            f"Ranked on the **1-in-{chosen} year** scenario — the return period "
            "selected above the tabs, shared with the map. The ranking is not the "
            "same for every period: `exposed_pop` is one of the weighted "
            "indicators and it is rescaled within the rows being ranked, so the "
            "period is part of the finding rather than a detail."
        )
    chosen_indicators = st.multiselect("Indicators", indicators, default=indicators[:3])
    perturbation = st.slider("Weight perturbation", 0.0, 0.9, 0.3, 0.1)
    top_n = st.number_input("Top N to test stability against", 3, 50, 10)

    if chosen_indicators:
        ranked = sensitivity(
            # `view` is already one row per region, because it is one return
            # period. drop_duplicates is a guard against a table that repeats a
            # region for some other reason; passing the whole table here instead
            # made it pick the first row per region, which is the rarest-last
            # concatenation order — so the ranking was always the shortest period.
            view.drop_duplicates(subset=[key]),
            {c: 1.0 for c in chosen_indicators},
            perturbation=perturbation,
            top_n=int(top_n),
        )
        robust = int((ranked["confidence"] == "robust").sum())
        st.metric("Robust rankings", f"{robust} / {len(ranked)}")
        st.dataframe(
            ranked[[c for c in (key, *chosen_indicators, "vulnerability", "top_n_frequency", "confidence") if c in ranked]],
            width="stretch",
        )
        st.caption(
            "Only the robust rows belong in the brief as findings. Quote an "
            "indicative one and the first methodological question sinks it."
        )

# --- Draft ----------------------------------------------------------------------
with draft_tab:
    st.subheader("Draft against the evidence")
    question = st.text_input(
        "The decision-maker's question",
        placeholder="Which regions should be prioritised for a flood warning system, and why?",
    )

    if question:
        passages = rag.search(question, k=5)
        if not passages:
            # The refusal path, shown as a result rather than an error: a corpus
            # that is silent is an answer, and it is the honest one.
            st.error(
                "**Refused.** No passage in the policy corpus supports an answer to "
                "this. That is the designed behaviour, not a failure — rephrase in "
                "the documents' own wording, or accept that the corpus is silent."
            )
        else:
            with st.expander(f"{len(passages)} passages retrieved", expanded=False):
                for i, p in enumerate(passages, 1):
                    st.markdown(f"**[S{i}]** `{p['source']}` · score {p['score']}")
                    st.caption(p["text"][:600])

            # flatten() first, because it is the only thing that drops `geometry`
            # — and the frozen table is saved from a GeoDataFrame, so the column is
            # there. A polygon is thousands of tokens of coordinates the model can
            # do nothing with, times every row, and it would dominate the prompt.
            #
            # `view`, not `exposure`: the whole table is nine nested scenarios, and
            # this tab used to send `exposure.head(200)` — which is file order, so
            # Albania through Germany at the 10-year period, whatever the reader
            # had selected above. The page's contract is one scenario everywhere.
            #
            # Ranked by share, because the rows have to be chosen by something and
            # "the first 200 alphabetically" is not a criterion a brief can quote.
            ranked = (
                view.assign(exposed_share=view["exposed_pop"] / view["total_pop"])
                .sort_values("exposed_share", ascending=False)
                if has_exposure and "total_pop" in view.columns
                else view
            )
            # The ceiling is the provider's PER-MINUTE budget, not its context
            # window. It is read from `rag` rather than restated here: the number
            # is a measured property of the provider and it has already moved
            # once, so the module that raises the 413 owns it.
            fenced = rag.fence(passages)
            budget = (
                rag.PROMPT_CHAR_BUDGET
                - len(fenced) - len(question) - len(rag.SYSTEM_PROMPT)
            )
            prompt_table = fit_rows(flatten(ranked), "exposure", max(budget, 0))
            table = to_toon(prompt_table, "exposure")
            report = token_report(prompt_table, "exposure")
            st.caption(
                f"Prompt table: the **{len(prompt_table)} most exposed of "
                f"{view[key].nunique():,} regions** at the 1-in-{chosen} year "
                "scenario, ranked by the share of their own population exposed. "
                "A ranked extract, and the prompt says so — a model handed forty "
                "rows with no label will quote a European total from them."
            )
            if report.get("available", True):
                st.caption(
                    f"Table encoded as TOON: {report['toon_tokens']:,} tokens against "
                    f"{report['json_tokens']:,} as JSON — {report['saving_pct']}% smaller. "
                    "Worth saying in the responsible-AI section."
                )
            else:
                # Said out loud rather than estimated: an unmeasured saving must not
                # reach the brief dressed as a measured one.
                st.caption(
                    "Table encoded as TOON. Token saving NOT measured here — "
                    f"{report['reason']}. Run the count where tiktoken loads "
                    "(WSL, or the container) before quoting a figure."
                )

            if st.button("Draft this section"):
                prompt = (
                    f"QUESTION: {question}\n\n"
                    f"TABLE — the {len(prompt_table)} most exposed of "
                    f"{view[key].nunique()} NUTS3 regions at the 1-in-{chosen} "
                    "year return period, ranked by the share of their own "
                    "population exposed. This is a ranked extract, not the whole "
                    "table: do not state a European total or a count of regions "
                    f"from it.\n{table}\n\n{fenced}"
                )
                try:
                    completion = rag.complete(prompt)
                except Exception as exc:
                    # A dead provider, a rate limit, a 5xx from the model. Named as
                    # an upstream failure, because an unhandled traceback in front
                    # of a jury reads as a broken deliverable rather than a broken
                    # network — and the retrieved passages above are still useful.
                    completion = None
                    st.error(f"No model reachable: {exc}")
                else:
                    if completion is None:
                        # The provider can answer with message.content: null, which
                        # `rag.complete` passes straight through. Verification runs
                        # regexes over the text, so storing None would resurface as
                        # a TypeError out of grounding_score, lines from the cause.
                        st.error(
                            "The model returned an empty completion. Nothing was "
                            "drafted, so there is nothing to verify — retry, or "
                            "check the provider."
                        )
                if completion is not None:
                    st.session_state["draft"] = completion
                    st.session_state["passages"] = passages

    # `.get`, not `in`: an earlier run may have stored nothing, and a None draft
    # must not reach the verification below.
    if st.session_state.get("draft"):
        draft, passages = st.session_state["draft"], st.session_state["passages"]
        score = rag.grounding_score(draft, passages)
        bad = rag.invalid_citations(draft, len(passages))

        verdict = st.columns(2)
        verdict[0].metric("Lexical grounding", f"{score:.0%}")
        verdict[1].metric("Invalid citations", len(bad) or "none")
        if bad:
            st.error(f"Citations pointing at no source: {', '.join(f'[S{n}]' for n in bad)}")
        st.caption(
            "Grounding counts shared words, not meaning: it catches drift away "
            "from the sources, not a subtle misreading that reuses their "
            "vocabulary. Read the passages before approving."
        )

        edited = st.text_area("Draft — edit freely", draft, height=260)
        if st.button("Approve for the brief", type="primary"):
            # The human edit wins as-is. It is deliberately not sent back to the
            # model to rewrite, because that hands the last word to the machine.
            approved = Path(__file__).resolve().parents[1] / "data" / "processed" / "approved.md"
            approved.parent.mkdir(parents=True, exist_ok=True)
            with approved.open("a", encoding="utf-8") as handle:
                handle.write(f"\n\n<!-- approved {datetime.now():%Y-%m-%d %H:%M} -->\n{edited}\n")
            st.success(f"Appended to {approved.name}. Nothing reaches the brief any other way.")

# --- Translation ----------------------------------------------------------------
with translate_tab:
    st.subheader("The brief in the language the authority works in")
    st.caption(
        "Everything in this kit is written in English — the corpus, the code, the "
        "interface and the draft. The authority that would act on it is Belgian, "
        "and a recommendation is read in French, Dutch or German. So the "
        "translation sits BESIDE the English section rather than replacing it: "
        "the English stays the record, because that is the text whose figures "
        "were checked against the table."
    )

    approved_path = (
        Path(__file__).resolve().parents[1] / "data" / "processed" / "approved.md"
    )
    # Pre-filled from what a human approved, not from the live draft: translating
    # an unapproved draft would route text around the gate in the tab next door,
    # which is the one thing this workflow is built to prevent. It stays editable,
    # so a section can still be pasted in by hand.
    default = approved_path.read_text(encoding="utf-8") if approved_path.exists() else ""
    if not default.strip():
        st.info(
            "Nothing approved yet. Draft a section in the tab before this one and "
            "approve it — then it appears here."
        )
    source = st.text_area(
        "English section", default, height=220,
        help="Approved text. Edit or paste another section before translating.",
    )

    language = st.radio(
        "Into", sorted(translate.LANGUAGES),
        format_func=lambda code: translate.LANGUAGES[code],
        horizontal=True,
    )
    if st.button("Translate", type="primary", disabled=not source.strip()):
        try:
            result = translate.translate(source, language)
        except translate.TranslationFailed as exc:
            # The failure this tab exists for. Shown as an error with the figure
            # named, never as a paragraph: a translation that moved a number reads
            # perfectly and is wrong, which is the worst thing a brief can be.
            st.error(f"Not shown — {exc}")
        except ValueError as exc:
            st.warning(str(exc))
        except Exception as exc:
            st.error(f"No model reachable: {exc}")
        else:
            st.session_state["translation"] = result

    result = st.session_state.get("translation")
    if result is not None and result.language == language:
        st.success(
            f"{result.numbers} figures and {result.citations} citations checked "
            f"against the English, digit by digit."
        )
        st.text_area(
            f"{translate.LANGUAGES[result.language]} — edit freely",
            result.text, height=220, key="translated_text",
        )
        st.caption(
            "The check compares digits, not formatting: 29,727,887 and "
            "29 727 887 are the same number, and 29.7 million is not. A "
            "translation that rounded a figure, spelled one out or moved a "
            "citation marker is refused rather than displayed."
        )

# --- AI log ---------------------------------------------------------------------
with log_tab:
    st.subheader("AI usage log")
    st.caption(
        "Annex A of the brief. Written as you work, not reconstructed at 17:00 — "
        "and include at least one rejection, because a log without one reads as a "
        "log nobody kept."
    )
    log_path = Path(__file__).resolve().parents[1] / "docs" / "ai_usage_log.md"
    with st.form("log"):
        columns = st.columns(4)
        tool = columns[0].text_input("Tool / model")
        task = columns[1].text_input("Task")
        checked = columns[2].text_input("What a human checked")
        outcome = columns[3].selectbox("Outcome", ["accepted", "accepted after fix", "rejected"])
        if st.form_submit_button("Add entry") and tool:
            row = f"| {datetime.now():%a %H:%M} | {tool} | {task} | {checked} | {outcome} |\n"
            usage_log.append_row(log_path, row)
            st.success("Logged.")
    if log_path.exists():
        st.markdown(
            usage_log.unlink_relative_docs(log_path.read_text(encoding="utf-8"))
        )
