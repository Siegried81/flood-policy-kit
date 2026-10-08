"""Fetch one ensemble member from the Copernicus CDS, and prove it is the one asked for.

**Why this exists.** The CDS files already on disk were pulled by hand through the
web form, and the archive is one member short where it matters most: the
2071-2100 period has `E-HYPEgrid-EUR-11` and not `VIC-WUR-EUR-11`, while
2011-2040 and 2041-2070 have both. `src/climate.py` refuses to call a single
member agreement with itself, so `ensemble_agrees_on_sign_2071_2100` is False for
all 1,345 regions and the far-future figure - the one a reader is most likely to
quote - licenses no sentence about the direction of the change. One request fixes
that, and a request that lives in the repo is reproducible where a form filled in
on a Tuesday is not.

**Credentials.** The CDS needs an API key: register at
<https://cds.climate.copernicus.eu>, accept the dataset's licence on its download
page, then put the key in `~/.cdsapirc` or the `CDSAPI_KEY` environment variable.
Nothing here caches or prints the key.

**The cost cap is a PRODUCT, not a sum.** The form refuses a request whose
selections multiply past 1,000 - four variables x three periods x eight models is
96, which passes, but adding the percentile and statistic axes does not. So this
script requests ONE period and ONE model per run by default, which is also what
makes the result checkable: every file that comes back must describe exactly what
was asked for.

**It verifies rather than trusts.** The CDS returns a ZIP whose member filenames
carry the whole request, and `src/climate.py::describe` already parses that
grammar. Every extracted file is parsed and compared field by field against the
request, and a mismatch is an error - because the failure that matters is not an
empty download, it is a download of the *wrong member* landing in the directory
the ensemble is built from, where it would silently become a second opinion from
the same world.

Run:

    python scripts/fetch_cds_member.py                 # the missing VIC-WUR 2071-2100
    python scripts/fetch_cds_member.py --dry-run       # print the request, fetch nothing
"""

from __future__ import annotations

import argparse
import shutil
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src import climate  # noqa: E402

DATASET = "sis-hydrology-variables-derived-projections"
OUT_DIR = ROOT / "data" / "raw" / "download" / "cds_hydrology_projections"

#: Every value below was read off the live request form on 2026-10-07
#: (`links.form` on the collection), not recalled: the API spells the models
#: `vic_wur` and `e_hypegrid`, the periods `2071_2100`, and the relative change
#: `relative_change_from_reference_period`. Guessing any of them produces a
#: request the server rejects with no useful message.
MODELS = {"vic_wur": "VIC-WUR-EUR-11", "e_hypegrid": "E-HYPEgrid-EUR-11"}

#: The two return periods the existing VIC-WUR files cover, so the new member
#: matches its siblings. The 2 and 10 year variables exist and are deliberately
#: not requested: an ensemble varies the model chain, not the question, and a
#: member that covers different return periods than the one it is compared with
#: cannot be aggregated with it.
VARIABLES = [
    "flood_recurrence_5_years_return_period",
    "flood_recurrence_50_years_return_period",
]


def request(model: str, period: str) -> dict:
    """The CDS request for one model chain and one period."""
    return {
        "product_type": "climate_impact_indicators",
        "variable": VARIABLES,
        "variable_type": "relative_change_from_reference_period",
        "time_aggregation": "annual_mean",
        "experiment": ["rcp_8_5"],
        "hydrological_model": [model],
        "rcm": "cclm4_8_17",
        "gcm": "ec_earth",
        "ensemble_member": ["r12i1p1"],
        "period": [period],
    }


def check(path: Path, model: str, period: str) -> dict:
    """Parse one downloaded file's name and prove it is what was requested.

    The grammar is `src/climate.py`'s, not a second copy: a file this script
    accepts has to be a file the ensemble aggregation will also accept.
    """
    fields = climate.describe(path)
    expected = {
        "hydro_model": MODELS[model],
        "period": period.replace("_", "-"),
        "member": "r12i1p1",
        "kind": "rel",
    }
    wrong = {k: (fields[k], v) for k, v in expected.items() if fields[k] != v}
    if wrong:
        raise SystemExit(
            f"{path.name} is not what was requested: "
            + ", ".join(f"{k} is {got!r}, expected {want!r}" for k, (got, want) in wrong.items())
            + ". Nothing has been added to the ensemble directory."
        )
    return fields


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--model", default="vic_wur", choices=sorted(MODELS),
        help="Hydrological model chain. Default: the one missing from 2071-2100.",
    )
    parser.add_argument(
        "--period", default="2071_2100",
        choices=("2011_2040", "2041_2070", "2071_2100"),
        help="One period per run: the form's cost cap is the PRODUCT of the "
             "selections, and one period is what keeps the result checkable.",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Print the request and exit. Needs no credentials.",
    )
    args = parser.parse_args()

    body = request(args.model, args.period)
    print(f"dataset: {DATASET}")
    for key, value in body.items():
        print(f"  {key}: {value}")
    print(f"target : {MODELS[args.model]} {args.period.replace('_', '-')}")

    already = sorted(
        p.name for p in OUT_DIR.glob("*.nc")
        if climate.describe(p)["hydro_model"] == MODELS[args.model]
        and climate.describe(p)["period"] == args.period.replace("_", "-")
    ) if OUT_DIR.exists() else []
    if already:
        print(f"\nAlready on disk, nothing to do:")
        for name in already:
            print(f"  {name}")
        return 0

    if args.dry_run:
        print("\n--dry-run: nothing fetched.")
        return 0

    try:
        import cdsapi
    except ImportError:
        raise SystemExit(
            "cdsapi is not installed. `pip install cdsapi`, then put your key in "
            "~/.cdsapirc or CDSAPI_KEY - see <https://cds.climate.copernicus.eu>. "
            "The dataset's licence also has to be accepted once, on its download "
            "page, or every request comes back as a licence error."
        )

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    archive = OUT_DIR / f"cds_request_{args.model}_{args.period}.zip"
    print(f"\nrequesting... (the CDS queues this; minutes is normal)", flush=True)
    cdsapi.Client().retrieve(DATASET, body, str(archive))

    # Extracted to a staging directory first: a wrong member must never land in
    # the directory `scripts/build_context.py` globs for ensemble files, because
    # nothing downstream would question it.
    staging = OUT_DIR / f".staging_{args.model}_{args.period}"
    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir()
    with zipfile.ZipFile(archive) as zf:
        zf.extractall(staging)

    members = sorted(staging.glob("*.nc"))
    if not members:
        raise SystemExit(f"{archive.name} holds no .nc file. Nothing was added.")
    for path in members:
        fields = check(path, args.model, args.period)
        print(f"  verified {path.name} -> {fields['variable']} {fields['period']}")

    for path in members:
        shutil.move(str(path), OUT_DIR / path.name)
    shutil.rmtree(staging)

    print(f"\n{len(members)} file(s) added to {OUT_DIR.relative_to(ROOT)}")
    print("Rebuild the context table to pick them up:")
    print("  python scripts/build_context.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
