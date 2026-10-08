"""JSON API over the flood-exposure kit, consumed by the React UI in web/.

It serialises what `src/` already computes and decides nothing of its own: the
exposure figures, the vulnerability ranking with its sensitivity, and the
grounded retrieval. Keeping the decisions in `src/` means the Streamlit app and
this API cannot drift into disagreeing about a number — which matters, because
both are shown to the same jury. The three presentation decisions `src/` has no
opinion on — which columns may be weighted into the vulnerability index, which
return period a figure belongs to, and what a climate period's figures are
allowed to claim — live here as `vulnerability_indicators`, `_one_return_period`
and `climate_periods`, and `app/streamlit_app.py` imports the first and the
third rather than restating them.

Two things it deliberately does NOT do:

- **It does not approve anything.** `POST /api/draft` returns a draft together
  with its grounding score and any invalid citation. Approval is a separate call
  that a human triggers, and only that call writes to the brief.
- **It does not fetch map tiles.** The choropleth is served as GeoJSON and drawn
  as SVG in the browser. No tile provider, no API key, nothing to fail on a
  hackathon network — and the map still works with the Wi-Fi unplugged.

Run with `uvicorn api.main:app --port 8010`.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src import rag, translate  # noqa: E402
from src.toon_io import flatten, to_toon, token_report  # noqa: E402
from src.vulnerability import sensitivity  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
EXPOSURE = ROOT / "data" / "processed" / "exposure.parquet"
CONTEXT = ROOT / "data" / "processed" / "context.parquet"
GEOMETRY = ROOT / "data" / "processed" / "regions.geojson"
APPROVED = ROOT / "data" / "processed" / "approved.md"
WEB_DIST = ROOT / "web" / "dist"
DEV_ORIGINS = ["http://localhost:5190", "http://127.0.0.1:5190"]

# Numeric columns that describe the SCENARIO rather than the people living in it,
# and so are never offered as vulnerability indicators. `annual_probability` is
# the one that matters: picked as an indicator it reads as "a more frequent flood
# makes residents more vulnerable", which is not a claim about vulnerability at
# all. `app/streamlit_app.py` imports the helper below rather than restating this
# set, because the composite index is a weighted mean over whatever is selected -
# so one extra column in one UI gives the same region two different scores from
# the same frozen table.
#
# `cells_counted` and `hazard_coverage` are excluded for a second reason: they
# describe how well the rasters cover the unit, not the people in it. They sit
# before `exposed_pop` in the table, so leaving them in made them the first
# entries of this list - and the default selection is its first three, which
# would have built the index out of raster bookkeeping. `hazard_coverage`
# belongs next to a figure as its qualifier, never inside one.
#: Numeric columns of the exposure table that are NOT vulnerability indicators.
#:
#: The index is a weighted mean of min-max scaled columns, so anything numeric
#: left out of this set joins it silently. `total_pop` is the trap that proved
#: it: the 2026-10-06 rebuild added the column as a denominator, and the index
#: immediately offered it as an indicator - which ranks a region as vulnerable
#: for being populous, not for being flooded. Any column added to the parquet
#: has to be judged against this list in the same pass.
#:
#: Judged 2026-10-07, when the Eurostat join landed: `share_over_65` and
#: `poverty_rate` ARE indicators and stay out of this set - they are properties
#: of the people, which is what the index is supposed to weigh, and they are the
#: reason it has more than one axis at all. Their `_year` and `_level` companions
#: are stored as TEXT rather than numbers, so they are excluded by dtype and
#: cannot drift into the index if someone forgets this list. `gdp_meur` is a
#: denominator and never reaches this table: it is written to
#: `context.parquet` instead.
NON_INDICATOR_COLUMNS = frozenset({
    "return_period", "annual_probability", "cells_counted", "hazard_coverage",
    "total_pop",
})

app = FastAPI(title="Flood exposure API", version="1.0")
app.add_middleware(
    CORSMiddleware, allow_origins=DEV_ORIGINS, allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


def _table() -> pd.DataFrame:
    """The frozen exposure table, or a 404 explaining how to build one."""
    if not EXPOSURE.exists():
        raise HTTPException(
            status_code=404,
            detail="No exposure table. Build one with `python scripts/build_exposure.py`, "
                   "which writes data/processed/exposure.parquet. It needs the rasters "
                   "`python -m src.fetch` downloads; data/ is not committed.",
        )
    return pd.read_parquet(EXPOSURE)


def _region_key(df: pd.DataFrame) -> str:
    """Whichever identifier column this run used. NUTS3 for Europe, LAU for a zoom."""
    for candidate in ("nuts_id", "lau_id", "id"):
        if candidate in df.columns:
            return candidate
    raise HTTPException(status_code=500, detail="No region identifier column in the table.")


def vulnerability_indicators(df: pd.DataFrame) -> list[str]:
    """Numeric columns that may be weighted into the vulnerability index, in table order.

    Exported so `app/streamlit_app.py` can offer exactly this list: the index is a
    weighted mean of min-max scaled columns, so a UI that offers one column the
    other does not reports a different composite score for the same region.
    """
    return [
        c for c in df.columns
        if df[c].dtype.kind in "if" and c not in NON_INDICATOR_COLUMNS
    ]


def _return_periods(df: pd.DataFrame) -> list[int]:
    """Return periods present in the table, rarest last. Empty if unmodelled."""
    if "return_period" not in df.columns:
        return []
    return sorted(int(p) for p in df["return_period"].dropna().unique())


def _one_return_period(
    df: pd.DataFrame, requested: int | None
) -> tuple[pd.DataFrame, int | None, bool]:
    """Narrow the table to exactly one return period, and say which one.

    Return-period extents are NESTED - the 100-year zone contains the 10-year one
    - so there is no "all periods" reading of this table: any figure summed across
    periods counts the core floodplain once per period, and any ranking taken
    across them is really a ranking of whichever period the rows happened to be
    concatenated in first. Naming no period therefore selects the rarest one, the
    same default both UIs show, rather than quietly meaning "all of them".

    Returns the narrowed frame, the period it is for (None when the table carries
    no return period at all), and whether the server picked it.
    """
    periods = _return_periods(df)
    if not periods:
        # No return_period column: one row per region already, nothing to narrow.
        return df, None, False
    if requested is None:
        chosen = periods[-1]
        return df[df["return_period"] == chosen], chosen, True
    if requested not in periods:
        # An empty selection would otherwise report total_exposed 0.0, which reads
        # as "measured, nobody exposed" for a scenario that was never computed.
        raise HTTPException(
            status_code=400,
            detail=f"No return period {requested} in the table. Available: {periods}.",
        )
    return df[df["return_period"] == requested], requested, False


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/api/meta")
def meta() -> dict:
    """What run is on screen, so the UI can say it out loud.

    The freeze is the discipline that keeps the map, the brief and the pitch
    agreeing; naming the run is how a reader checks they are looking at it.
    """
    df = _table()
    key = _region_key(df)
    return {
        "key": key,
        "rows": len(df),
        "regions": int(df[key].nunique()),
        "return_periods": _return_periods(df),
        "indicators": vulnerability_indicators(df),
        "frozen_at": datetime.fromtimestamp(EXPOSURE.stat().st_mtime, timezone.utc).isoformat(),
        "has_geometry": GEOMETRY.exists(),
        "has_context": CONTEXT.exists(),
        "corpus_passages": len(rag.load_index().passages),
    }


@app.get("/api/exposure")
def exposure(return_period: int | None = None) -> dict:
    """Exposure per region for exactly ONE return period.

    `exposed_share` is computed here rather than client-side because it is the
    figure that should be ranked: an absolute count ranks by population and tells
    a decision-maker nothing they did not already know.

    Naming no return period does not mean "every period": the extents are nested,
    so `total_exposed` over several of them counts the core floodplain once per
    period. The server narrows to the rarest period instead and sets
    `defaulted_return_period`, so a caller that never chose can tell that the
    figures belong to one scenario the server picked.
    """
    df = _table()
    key = _region_key(df)
    df, period, defaulted = _one_return_period(df, return_period)
    if {"exposed_pop", "total_pop"} <= set(df.columns):
        df = df.assign(exposed_share=df["exposed_pop"] / df["total_pop"])

    records = json.loads(df.to_json(orient="records"))  # NaN -> null, which JSON can carry
    # null rather than 0 when the column is absent: "we did not measure this" and
    # "we measured nobody" must not arrive in the same shape.
    measured = "exposed_pop" in df.columns
    return {
        "key": key,
        "return_period": period,
        "defaulted_return_period": defaulted,
        "rows": records,
        # Surfaced, never folded into the totals: a region the raster does not
        # cover is not a region with nobody exposed.
        "unmeasured": int(df["exposed_pop"].isna().sum()) if measured else None,
        "total_exposed": float(df["exposed_pop"].sum(skipna=True)) if measured else None,
    }


@app.get("/api/geometry")
def geometry() -> dict:
    """Simplified region polygons for the choropleth.

    Served as GeoJSON and drawn as SVG in the browser: no tile provider, no key,
    and the map still renders with the network unplugged.
    """
    if not GEOMETRY.exists():
        raise HTTPException(
            status_code=404,
            detail="No regions.geojson. Build it with `python scripts/build_geometry.py`, "
                   "which simplifies the GISCO boundaries `python -m src.fetch` downloads. "
                   "Without it this endpoint 404s and the choropleth renders nothing.",
        )
    return json.loads(GEOMETRY.read_text(encoding="utf-8"))


# The per-region context table is loaded SEPARATELY from the exposure table, and
# the two are never merged server-side. `vulnerability_indicators` picks the
# index's inputs by scanning numeric columns, so a climate percentage or a
# built-up share joined onto the exposure frame would silently become a
# min-max-scaled term in a weighted mean - "this region's rivers rise faster,
# therefore its residents are more vulnerable". Context qualifies an exposure
# figure; it is not an ingredient of one.


def _context() -> pd.DataFrame:
    """The frozen context table, or a 404 explaining how to build one."""
    if not CONTEXT.exists():
        raise HTTPException(
            status_code=404,
            detail="No context table. Build one with `python scripts/build_context.py`, "
                   "which writes data/processed/context.parquet. It needs the hazard "
                   "rasters and the CDS NetCDFs `python -m src.fetch` downloads; data/ "
                   "is not committed.",
        )
    return pd.read_parquet(CONTEXT)


def climate_periods(df: pd.DataFrame) -> list[dict]:
    """One summary per CDS period present, with what licenses a sentence about it.

    `scripts/build_context.py` suffixes every climate column with its period, so
    the periods on offer are read off the column names rather than hardcoded: a
    period added to the build appears here without this file being touched.

    The figures travel together because none of them is readable alone:

    - `median_change_pct` is the median OF the per-region ensemble medians, so it
      is a direction and a size, never a projected discharge. A relative change
      against a near-zero reference discharge is unbounded, which is why this is
      a median and not a mean.
    - `members` is how many model chains the period actually has, read off the
      table rather than assumed. Measured on `data/processed/context.parquet`
      2026-10-08: all three periods carry **2** chains on the 1,198 regions that
      were measured at all, and 0 on the other 147. An earlier version of this
      docstring claimed one chain for 2071-2100; the built table does not say
      that, and the fixture in `tests/test_api.py` that uses one chain for that
      period is exercising the branch below, not describing the archive.
    - `regions_agreeing_on_sign` is the count a reader must see before writing
      "river discharge increases here". At one member it is 0 by construction -
      `src.climate.ensemble_change_by_region` refuses to call a single member
      agreement with itself - so `single_member` says WHY it is zero. Without it
      a one-member period reads as a period where the models disagree, which is
      a different and wrong claim.
    """
    periods: list[dict] = []
    prefix = "ensemble_members_"
    for column in df.columns:
        if not column.startswith(prefix):
            continue
        suffix = column[len(prefix):]
        median = df.get(f"change_pct_ensemble_median_{suffix}")
        agrees = df.get(f"ensemble_agrees_on_sign_{suffix}")
        measured = median.notna() if median is not None else pd.Series([], dtype=bool)
        members = int(df[column].max()) if len(df) else 0
        periods.append({
            "period": suffix.replace("_", "-"),
            "members": members,
            "single_member": members <= 1,
            "regions_measured": int(measured.sum()),
            "median_change_pct": (
                float(median[measured].median()) if bool(measured.any()) else None
            ),
            "regions_agreeing_on_sign": int(agrees.sum()) if agrees is not None else 0,
        })
    return sorted(periods, key=lambda entry: entry["period"])


@app.get("/api/context")
def context() -> dict:
    """Per-region context: future climate, exposed built-up surface, shared basins.

    Everything served here qualifies an exposure figure without being one - see
    the note above `_context` for why it is a separate table and not extra
    columns on the exposure frame.

    The climate block is the only forward-looking layer in the kit and the one a
    reader will over-read, so `climate_periods` travels with every response
    instead of being something a caller has to think to ask for.
    """
    df = _context()
    key = _region_key(df)
    records = json.loads(df.to_json(orient="records"))  # NaN -> null, which JSON can carry
    # The built-up figures are measured at ONE return period, which the column
    # names it in. Serving the number without the period invites it to be read
    # against a different scenario's exposure count.
    built_prefix = "built_share_exposed_rp"
    built_rp = next(
        (int(c[len(built_prefix):]) for c in df.columns if c.startswith(built_prefix)),
        None,
    )
    return {
        "key": key,
        "regions": int(df[key].nunique()),
        "rows": records,
        "climate_periods": climate_periods(df),
        "built_up_return_period": built_rp,
        "frozen_at": datetime.fromtimestamp(CONTEXT.stat().st_mtime, timezone.utc).isoformat(),
    }


class VulnerabilityRequest(BaseModel):
    indicators: list[str] = Field(min_length=1)
    perturbation: float = Field(default=0.3, ge=0.0, le=0.9)
    top_n: int = Field(default=10, ge=1, le=100)
    # Which scenario the ranking is built on. Omitted means "the server picks the
    # rarest period and says so", never "all of them" - see `_one_return_period`.
    return_period: int | None = None


@app.post("/api/vulnerability")
def vulnerability(req: VulnerabilityRequest) -> dict:
    """Composite index plus the sensitivity that says which ranks survive it.

    The sensitivity is not optional here. A composite index is a value judgement
    wearing a number, and a rank that moves when the weights move is an artefact,
    not a finding.

    The ranking is built on ONE return period, and the response names it. The
    table holds one row per region per period, so narrowing has to happen before
    the index is computed: `exposed_pop` is usually one of the weighted
    indicators, it is min-max scaled across the rows present, and the order of the
    top rows does change between periods. An unstated period is therefore a silent
    answer to "who do we help first".
    """
    df = _table()
    key = _region_key(df)
    missing = [c for c in req.indicators if c not in df.columns]
    if missing:
        raise HTTPException(status_code=400, detail=f"Unknown indicators: {missing}")
    scenario = [c for c in req.indicators if c in NON_INDICATOR_COLUMNS]
    if scenario:
        raise HTTPException(
            status_code=400,
            detail=f"Not vulnerability indicators: {scenario}. These describe the "
                   "flood scenario, not the people exposed to it.",
        )

    df, period, defaulted = _one_return_period(df, req.return_period)
    ranked = sensitivity(
        # Within one period the table already holds one row per region, so this is
        # a guard against a table that repeats a region for some other reason. It
        # can no longer decide which return period the ranking is built on, which
        # is what it silently did when the whole table was passed: it kept the
        # first row per region, and the periods are concatenated rarest-last.
        df.drop_duplicates(subset=[key]),
        {c: 1.0 for c in req.indicators},
        perturbation=req.perturbation,
        top_n=req.top_n,
    )
    columns = [c for c in (key, *req.indicators, "vulnerability", "top_n_frequency", "confidence")
               if c in ranked.columns]
    return {
        "key": key,
        "return_period": period,
        "defaulted_return_period": defaulted,
        "rows": json.loads(ranked[columns].to_json(orient="records")),
        "robust": int((ranked["confidence"] == "robust").sum()),
        "total": len(ranked),
    }


@app.get("/api/search")
def search(q: str, k: int = 5) -> dict:
    """Retrieve supporting passages, or report the refusal.

    An empty `passages` with `refused: true` is a result, not an error: the corpus
    being silent is the honest answer, and the UI shows it as such.
    """
    passages = rag.search(q, k=k)
    return {"question": q, "passages": passages, "refused": not passages}


class DraftRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    rows: int = Field(default=200, ge=1, le=2000)


@app.post("/api/draft")
def draft(req: DraftRequest) -> dict:
    """One LLM call over the frozen table and the retrieved passages.

    Returns the draft **with its verification**, never on its own: the grounding
    score and any invalid citation travel with the text so the human deciding
    whether to approve it is deciding informed.
    """
    passages = rag.search(req.question, k=5)
    if not passages:
        return {"refused": True, "draft": None, "passages": []}

    # flatten() before encoding, because it is the only thing that drops
    # `geometry` - and the frozen table is saved from a GeoDataFrame, so the
    # column is there. A polygon is thousands of tokens of coordinates the model
    # can do nothing with, times `rows`, and it would be the bulk of the prompt.
    df = flatten(_table().head(req.rows))
    table = to_toon(df, "exposure")
    prompt = f"QUESTION: {req.question}\n\nTABLE:\n{table}\n\n{rag.fence(passages)}"
    try:
        text = rag.complete(prompt)
    except Exception as exc:
        # 502, not 500: the failure is upstream, and the status code is the only
        # thing telling the client it is the model that is unreachable rather
        # than this service that is broken.
        raise HTTPException(status_code=502, detail=f"No model reachable: {exc}") from exc
    if text is None:
        # The provider can answer with message.content: null, which `rag.complete`
        # passes straight through. Verification below runs regexes over the text,
        # so a None would resurface as a TypeError out of grounding_score and
        # reach the client as a 500 - our bug, for the provider's empty turn.
        raise HTTPException(
            status_code=502,
            detail="The model returned an empty completion. Nothing was drafted, so "
                   "there is nothing to verify: retry, or check the provider.",
        )

    return {
        "refused": False,
        "draft": text,
        "passages": passages,
        "grounding": round(rag.grounding_score(text, passages), 4),
        "invalid_citations": rag.invalid_citations(text, len(passages)),
        "tokens": token_report(df, "exposure"),
    }


class TranslateRequest(BaseModel):
    text: str = Field(min_length=1)
    #: A key of `translate.LANGUAGES`, validated there rather than here so the
    #: refusal message names the languages that exist.
    language: str = Field(min_length=2, max_length=5)


@app.post("/api/translate")
def translate_section(req: TranslateRequest) -> dict:
    """One section into one language, with the figures checked against the source.

    The check is the reason this is a route rather than a prompt. A translation
    may change every word and may not change a single number, and a model asked
    for French will localise `29,727,887` to `29 727 887` - correct - as readily
    as it will write `29,7 millions`, round `16.9%` or move a `[S2]`. None of
    that looks wrong on the page.

    A translation that failed the check comes back as **422, not 200 with a
    warning**: the client must not be able to render it by ignoring a field. The
    English section is unaffected either way - it stays the record, because it is
    the text whose figures were checked against the table.
    """
    try:
        result = translate.translate(req.text, req.language)
    except ValueError as exc:
        # A language nobody offers, or nothing to translate. The client sent a bad
        # request; 400 rather than 422 so it is distinguishable from a translation
        # that was produced and rejected.
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except translate.TranslationFailed as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        # Upstream, like `/api/draft`: the model is unreachable, not this service.
        raise HTTPException(
            status_code=502, detail=f"No model reachable: {exc}"
        ) from exc
    return {
        "text": result.text,
        "language": result.language,
        "language_name": translate.LANGUAGES[result.language],
        "numbers_checked": result.numbers,
        "citations_checked": result.citations,
    }


@app.get("/api/languages")
def languages() -> dict:
    """The target languages, so the UI never hardcodes a list that can drift.

    English is absent on purpose: it is the source, and offering it invites a
    round trip, which is how a figure quietly changes.
    """
    return {"languages": [
        {"code": code, "name": name}
        for code, name in sorted(translate.LANGUAGES.items())
    ]}


class ApproveRequest(BaseModel):
    text: str = Field(min_length=1)


@app.post("/api/approve")
def approve(req: ApproveRequest) -> dict:
    """Append approved text to the brief. The only route that writes to it.

    The text is stored exactly as the human left it. It is deliberately not sent
    back to the model for polishing, because that hands the last word to the
    machine on a document a public authority may act on.
    """
    APPROVED.parent.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")
    with APPROVED.open("a", encoding="utf-8") as handle:
        handle.write(f"\n\n<!-- approved {stamp} -->\n{req.text}\n")
    return {"written_to": APPROVED.name, "approved_at": stamp}


# Single-process production mode, mounted last so /api/* always wins.
if WEB_DIST.is_dir():
    app.mount("/", StaticFiles(directory=WEB_DIST, html=True), name="web")
