"""Prove the 29-30 October demo survives with the network unplugged - or fail loudly.

Run it the evening before, and again at the venue before the jury arrives:

    .venv/Scripts/python.exe scripts/check_offline_readiness.py   # Windows
    .venv/bin/python scripts/check_offline_readiness.py           # WSL / Linux
    docker compose --profile tools run --rm check                 # inside the image

Why this is a script and not another test. The suite mocks the network away,
which is exactly what hides a missing 300 MB raster: every test passes and the
first real zonal statistic of the day fails. `pytest` answers "is the code
right"; this answers the other question - "is everything this laptop needs
already on this laptop" - and it answers it with byte counts rather than with a
reassurance.

What it checks, and why each one earns its line:

**Declared files, through `src.fetch`.** Where a source lands on disk is defined
once, in `fetch._target_path`, and this script imports it instead of re-deriving
the rule. A readiness check that computes its own paths will eventually disagree
with the fetcher, and then it certifies a corpus that is not the one the pipeline
reads.

**`*.part` leftovers.** `fetch._fetch_one` streams to `<name>.part` and renames
only once the body has been accepted, so a `.part` is the signature of a
download that died mid-transfer. The missing file it would have become already
shows up in the table above; naming the `.part` separately is what tells you the
fetch was interrupted rather than never started - a distinction that decides
whether re-running `src.fetch` costs you one file or the whole 3.82 GiB.

**The manifest against the disk.** `data/raw/manifest.json` is the provenance
record that lets a figure in the brief be traced back to an exact file. It is
rewritten wholesale by every `fetch_all` run, so an interrupted run leaves a
manifest describing a fraction of the corpus. A thin manifest is not a broken
demo, but it is a broken audit trail, and the jury is the European Commission.

**The Risk Data Hub cache.** The RDH bearer token expires after 10 hours, so the
responses cached under `data/processed/rdh_cache/` are not an optimisation: they
are the only offline route to an observed loss figure. An empty cache means the
validation half of the brief has nothing behind it.

**Ollama, and the model the code actually defaults to.** `src/rag.py` falls back
to Ollama when no Groq key is set, with `llama3.1` as its default model name. A
reachable Ollama holding a *different* model is the trap worth checking for: the
request reaches the right port and is refused by the wrong name, which reads as a
dead model server rather than as a one-word configuration fix.

**Whether a generation key is set at all**, because `rag.complete` prefers Groq
whenever `GROQ_API_KEY` is present - and Groq is on the far side of the venue
Wi-Fi. A key left in `.env` silently turns the demo back into an online demo.

It makes no network request other than the Ollama probe, and that probe only
runs when `OLLAMA_URL` points at this machine or at the Compose service beside
it; any other host is reported as "not probed" rather than quietly dialled out.
The exit code is 0 when the demo would work offline and 1 when it would not.
"""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.data_io import DATA, sources  # noqa: E402
from src.fetch import _target_path, expand  # noqa: E402
from src.rdh import CACHE_DIR as RDH_CACHE_DIR  # noqa: E402
from src.rdh import COLLECTIONS as RDH_COLLECTIONS  # noqa: E402

# The default `src/rag.py` hands to Ollama when OLLAMA_MODEL is unset. Restated
# here rather than imported because rag.py reads it inline in `complete()` and
# exposes no constant to import; if that default ever moves, move this with it.
RAG_DEFAULT_OLLAMA_MODEL = "llama3.1"
# The only hosts the Ollama probe is allowed to touch: this machine, or the
# sibling container in docker-compose.yml. Anything else is a request leaving the
# venue, which is the thing this script exists to rule out.
LOCAL_HOSTS = frozenset(
    {"localhost", "127.0.0.1", "::1", "host.docker.internal", "ollama"}
)
OLLAMA_TIMEOUT_S = 4
# How recently a `*.part` must have been written to count as a transfer in
# flight rather than an abandoned one. Two minutes, because `fetch.CHUNK_BYTES`
# is 1 MiB and even a stalling connection writes a chunk more often than that;
# anything quieter has stopped.
LIVE_PART_WINDOW_S = 120
# Width of the id column in the per-file table. Two declared sources have names
# long enough to wrap a terminal (the Copernicus observed-depth scene is 120
# characters), and a wrapped table is harder to read than a truncated one.
ID_WIDTH = 58


@dataclass(frozen=True)
class Check:
    """One verdict. `fix` is the single actionable line printed when it is not OK.

    Frozen, and carrying its own remedy, because the output has to be usable by
    someone reading it at 08:40 on the day: a status with no next action only
    moves the panic earlier.
    """

    name: str
    status: str  # "OK", "WARN" or "FAIL"
    detail: str
    fix: str = ""


def _human(size: int) -> str:
    """Byte count as a readable size, in binary units so it matches `du -h`."""
    value = float(size)
    for unit in ("B", "KiB", "MiB", "GiB"):
        if value < 1024:
            return f"{value:,.0f} {unit}" if unit == "B" else f"{value:,.1f} {unit}"
        value /= 1024
    return f"{value:,.1f} TiB"


def declared_targets(data_dir: Path = DATA) -> list[tuple[str, str, Path]]:
    """Every file a complete `src.fetch` run would leave on disk: (id, access, path).

    `api` entries are skipped for the same reason `fetch_all` skips them: a query
    endpoint is called at run time with parameters, not mirrored wholesale.
    Multi-file entries go through `fetch.expand`, so the count is files and not
    declared sources.

    Paths come from `fetch._target_path` and are then re-rooted under `data_dir`.
    The re-rooting is what lets a test aim the whole check at a temporary tree
    without this module owning a second copy of the naming rule.
    """
    targets: list[tuple[str, str, Path]] = []
    for section in ("geodata", "policy_corpus", "context"):
        for entry in sources(section) or []:
            access = entry.get("access", "download")
            if access == "api":
                continue
            for job in expand(entry):
                path = _target_path(job["id"], job["url"], access)
                targets.append((job["id"], access, data_dir / path.relative_to(DATA)))
    return targets


def check_declared_files(data_dir: Path = DATA) -> tuple[list[dict], list[Check]]:
    """Presence and size of every declared file, plus the verdicts about them.

    Returns the per-file rows as well as the checks, because the sizes are the
    evidence: "28 of 46 present" is a number you have to trust, while a table
    with a 0 B raster in it is a number you can see.

    A zero-byte file counts as missing rather than present. `fetch._fetch_one`
    treats any non-empty file as already done, so an empty one is both useless
    and invisible to a re-run.
    """
    rows: list[dict] = []
    for source_id, access, path in declared_targets(data_dir):
        size = path.stat().st_size if path.is_file() else None
        rows.append({"id": source_id, "access": access, "path": path, "size": size})

    present = [r for r in rows if r["size"]]
    missing = [r for r in rows if r["size"] is None]
    empty = [r for r in rows if r["size"] == 0]
    total = sum(r["size"] for r in present)

    checks = [
        Check(
            "declared files on disk",
            "OK" if not missing and not empty else "FAIL",
            f"{len(present)}/{len(rows)} present, {_human(total)}"
            + (f"; {len(missing)} missing" if missing else "")
            + (f"; {len(empty)} empty" if empty else ""),
            fix="run `python -m src.fetch` while there is still a network that can "
            "hold a connection; absent: "
            + ", ".join(r["id"] for r in (missing + empty)[:3]),
        )
    ]

    # Two declared files that resolve to the same path are not two files on disk.
    # `hanze_flood_impacts` is the live case: its seven download URLs all end in
    # `/content`, and `expand` names a file from the URL stem, so all seven become
    # `content.bin` and six overwrite the first. Reported rather than worked
    # around, because the fix belongs in sources.yaml and not in a checker.
    seen: dict[Path, list[str]] = {}
    for row in rows:
        seen.setdefault(row["path"], []).append(row["id"])
    collisions = {p: ids for p, ids in seen.items() if len(ids) > 1}
    if collisions:
        shadowed = sum(len(ids) - 1 for ids in collisions.values())
        names = sorted(p.name for p in collisions)
        checks.append(
            Check(
                "declared path collisions",
                "WARN",
                f"{shadowed} declared file(s) overwrite another at the same path "
                f"({', '.join(names[:3])})",
                fix="give the colliding entries distinct filenames in "
                "config/sources.yaml; as declared, only the last one fetched survives",
            )
        )
    return rows, checks


def check_partial_downloads(data_dir: Path = DATA, now: float | None = None) -> Check:
    """Any `*.part` left under data/raw, split into "still growing" and "abandoned".

    The split matters because the two have opposite remedies. A `.part` whose
    mtime moved in the last `LIVE_PART_WINDOW_S` is a transfer in flight: the
    right action is to wait, and deleting it would throw away a partial 300 MB
    raster that `src.fetch` is in the middle of writing. A `.part` that has not
    been touched since is a connection that died, and the right action is to
    delete it and re-fetch. A checker that called both of them "incomplete" would
    hand out the destructive advice half the time.
    """
    raw = data_dir / "raw"
    parts = sorted(raw.rglob("*.part")) if raw.is_dir() else []
    if not parts:
        return Check("interrupted downloads", "OK", "no *.part files")

    now = time.time() if now is None else now
    live = [p for p in parts if now - p.stat().st_mtime < LIVE_PART_WINDOW_S]
    stale = [p for p in parts if p not in live]
    described = ", ".join(f"{p.name} ({_human(p.stat().st_size)})" for p in parts[:3])
    if stale:
        return Check(
            "interrupted downloads",
            "FAIL",
            f"{len(stale)} abandoned *.part file(s): {described}",
            fix="delete the stale *.part files and re-run `python -m src.fetch`; it "
            "only fetches what is missing, so this costs those files and nothing else",
        )
    return Check(
        "interrupted downloads",
        "WARN",
        f"{len(live)} *.part file(s) still growing: {described}",
        fix="a fetch is running right now - let it finish and re-run this check "
        "rather than deleting a file that is being written",
    )


def _relocate(recorded: str, data_dir: Path) -> Path | None:
    """A manifest path, re-rooted on the data directory this run is looking at.

    Needed because the manifest stores absolute paths, and the same `data/` tree
    is reached by three different absolute paths over this project's life: a
    Windows drive letter, the WSL `/mnt/d/...` mount that actually ran the
    download, and `/app/data` inside the container. Comparing the strings would
    report every file as absent from whichever of the three you are standing in,
    so only the tail from the last `data` segment onwards is compared.
    """
    parts = Path(recorded.replace("\\", "/")).parts
    if "data" not in parts:
        return None
    last = len(parts) - 1 - list(reversed(parts)).index("data")
    tail = parts[last + 1 :]
    return data_dir.joinpath(*tail) if tail else None


def check_manifest(data_dir: Path = DATA) -> Check:
    """`data/raw/manifest.json` exists, and its entries still describe the disk.

    Three different failures, worth keeping apart. A missing manifest means
    `fetch_all` never finished a run. An entry whose file is gone, or whose byte
    count moved, means the manifest and the corpus disagree and a figure traced
    through it would be traced to the wrong bytes - a FAIL. A manifest that is
    merely *thinner* than the corpus is a WARN: the demo runs, but the provenance
    record covers only part of what it shows.
    """
    path = data_dir / "raw" / "manifest.json"
    if not path.is_file():
        return Check(
            "manifest",
            "FAIL",
            "data/raw/manifest.json is absent",
            fix="run `python -m src.fetch`; it writes the manifest at the end of a run",
        )
    try:
        entries = json.loads(path.read_text(encoding="utf-8"))
    except ValueError as exc:
        return Check(
            "manifest",
            "FAIL",
            f"manifest.json is not readable JSON ({exc})",
            fix="delete data/raw/manifest.json and re-run `python -m src.fetch`",
        )

    recorded = [e for e in entries if not e.get("error") and e.get("path")]
    gone: list[str] = []
    resized: list[str] = []
    unresolved: list[str] = []
    for entry in recorded:
        target = _relocate(str(entry["path"]), data_dir)
        source_id = str(entry.get("source_id", "?"))
        if target is None:
            unresolved.append(source_id)
        elif not target.is_file():
            gone.append(source_id)
        elif entry.get("bytes") is not None and target.stat().st_size != entry["bytes"]:
            resized.append(source_id)

    on_disk = sum(1 for _, _, p in declared_targets(data_dir) if p.is_file())
    if gone or resized or unresolved:
        problems = (
            ([f"{len(gone)} recorded but absent"] if gone else [])
            + ([f"{len(resized)} size mismatch(es)"] if resized else [])
            + ([f"{len(unresolved)} unresolvable path(s)"] if unresolved else [])
        )
        return Check(
            "manifest",
            "FAIL",
            f"{len(entries)} entries; " + ", ".join(problems),
            fix="re-run `python -m src.fetch` so the manifest describes the files that "
            "are actually there: " + ", ".join((gone + resized + unresolved)[:3]),
        )
    if len(recorded) < on_disk:
        return Check(
            "manifest",
            "WARN",
            f"{len(recorded)} entries match disk, but {on_disk} declared files are present",
            fix="the manifest is from a partial run and under-reports the corpus; "
            "re-run `python -m src.fetch` (fetched files are not re-downloaded) to "
            "restore full provenance",
        )
    return Check("manifest", "OK", f"{len(recorded)} entries, all matching disk")


def check_rdh_cache(cache_dir: Path = RDH_CACHE_DIR) -> Check:
    """The Risk Data Hub cache is non-empty, and says which collections it holds.

    Named per collection, not merely counted, because a cache holding only
    `hazard` looks healthy while leaving the loss figures - the reason the RDH is
    in the kit at all - with no offline source. The collection is read off the
    filename, which `rdh._cache_path` builds as `<collection>__<params>.json`
    precisely so a human can read it.
    """
    files = sorted(cache_dir.glob("*.json")) if cache_dir.is_dir() else []
    if not files:
        return Check(
            "RDH cache",
            "FAIL",
            f"{cache_dir.as_posix()} is empty or absent",
            fix="with a FRESH bearer token in .env (it expires after 10 hours) run "
            "`python -c \"from src import rdh; rdh.flood_losses(country='BE')\"` the "
            "day before - there is no other offline route to a loss figure",
        )
    held: dict[str, int] = {}
    for path in files:
        collection = path.stem.split("__", 1)[0]
        try:
            rows = json.loads(path.read_text(encoding="utf-8"))
            held[collection] = held.get(collection, 0) + len(rows)
        except ValueError:
            held[collection] = -1
    detail = ", ".join(
        f"{name} ({count:,} rows)" if count >= 0 else f"{name} (UNREADABLE)"
        for name, count in sorted(held.items())
    )
    if any(count < 0 for count in held.values()):
        return Check(
            "RDH cache",
            "FAIL",
            f"{len(files)} file(s): {detail}",
            fix="delete the unreadable cache file and re-fetch that collection with a "
            "fresh token; a truncated cache fails at draft time, not at load time",
        )
    if "losses" not in held:
        return Check(
            "RDH cache",
            "WARN",
            f"{len(files)} file(s): {detail}; no `losses` collection",
            fix="cache the losses collection too - it is the observed-cost layer the "
            "brief validates against: rdh.flood_losses(country='BE')",
        )
    unknown = sorted(set(held) - set(RDH_COLLECTIONS))
    if unknown:
        detail += f"; unrecognised: {', '.join(unknown)}"
    return Check("RDH cache", "OK", f"{len(files)} file(s): {detail}")


def _ollama_tags(url: str) -> list[str]:
    """Model names a local Ollama reports. Raises if it cannot be reached.

    `urllib` rather than `requests`, so that "this script makes exactly one
    network call" stays checkable by reading the imports.
    """
    endpoint = f"{url.rstrip('/')}/api/tags"
    with urllib.request.urlopen(endpoint, timeout=OLLAMA_TIMEOUT_S) as response:
        payload = json.loads(response.read().decode("utf-8"))
    return [str(model["name"]) for model in payload.get("models", [])]


def check_ollama(url: str | None = None, model: str | None = None) -> Check:
    """Ollama answers, and the model the code would ask for is actually pulled.

    The model name is read from the environment using `src/rag.py`'s own default,
    so this checks what the demo will really request rather than what `.env`
    hopes for. A model pulled under a different tag is called out by name: the
    gap between `llama3.1` and `llama3.2:3b` is a one-word edit, but only for
    someone who is told which word.
    """
    url = url or os.getenv("OLLAMA_URL", "http://localhost:11434")
    wanted = model or os.getenv("OLLAMA_MODEL", RAG_DEFAULT_OLLAMA_MODEL)
    host = urlparse(url).hostname or ""
    if host not in LOCAL_HOSTS:
        return Check(
            "Ollama",
            "WARN",
            f"not probed: OLLAMA_URL points off-box ({host})",
            fix="an off-box model server is a network dependency; point OLLAMA_URL at "
            "http://localhost:11434 and pull the model locally",
        )
    try:
        tags = _ollama_tags(url)
    except Exception as exc:  # refused connection, DNS, timeout, malformed JSON
        return Check(
            "Ollama",
            "FAIL",
            f"{url} unreachable ({exc})",
            fix=f"start Ollama (`ollama serve`) and run `ollama pull {wanted}`",
        )

    if wanted in tags or (":" not in wanted and f"{wanted}:latest" in tags):
        caveat = (
            ""
            if wanted == RAG_DEFAULT_OLLAMA_MODEL
            else f" - note src/rag.py defaults to {RAG_DEFAULT_OLLAMA_MODEL}, so this "
            "only holds while OLLAMA_MODEL is set"
        )
        return Check("Ollama", "OK", f"{url}, {wanted} pulled{caveat}")

    family = wanted.split(":")[0]
    near = [tag for tag in tags if tag.split(":")[0] == family]
    return Check(
        "Ollama",
        "FAIL",
        f"{url} answers but {wanted} is not pulled; it has "
        f"{', '.join(tags) if tags else 'no models'}",
        fix=(
            f"set OLLAMA_MODEL={near[0]} in .env"
            if near
            else f"run `ollama pull {wanted}` now, while there is still a network - or "
            f"set OLLAMA_MODEL to one of: {', '.join(tags)}"
        ),
    )


def check_generation_key(env: dict[str, str] | None = None) -> Check:
    """Which provider `rag.complete` would use, and whether it survives offline.

    `complete()` prefers Groq whenever `GROQ_API_KEY` is set, and does not fall
    back when that call fails. So a key left in `.env` is not a safety net on the
    day: it is the thing that routes the demo through the venue Wi-Fi. A WARN
    rather than a FAIL, because it is the right setting on every day except this
    one, and only the owner knows which day it is.
    """
    env = os.environ if env is None else env
    ollama_model = env.get("OLLAMA_MODEL", RAG_DEFAULT_OLLAMA_MODEL)
    if env.get("GROQ_API_KEY", "").strip():
        return Check(
            "generation provider",
            "WARN",
            "GROQ_API_KEY is set, so rag.complete() calls Groq over the network "
            f"instead of local Ollama ({ollama_model})",
            fix="for an offline run, comment GROQ_API_KEY out of .env (or start the "
            "container without it) so the local model is the one that answers",
        )
    return Check(
        "generation provider",
        "OK",
        f"no GROQ_API_KEY: rag.complete() uses local Ollama ({ollama_model})",
    )


def run_checks(data_dir: Path = DATA) -> tuple[list[dict], list[Check]]:
    """Every check, in the order a reader wants them: data first, model last."""
    rows, checks = check_declared_files(data_dir)
    checks.append(check_partial_downloads(data_dir))
    checks.append(check_manifest(data_dir))
    checks.append(check_rdh_cache(data_dir / "processed" / "rdh_cache"))
    checks.append(check_ollama())
    checks.append(check_generation_key())
    return rows, checks


def _print_files(rows: list[dict]) -> None:
    """The per-file evidence table. Printed in full, because the sizes are the point."""
    print(f"{'':4}{'DECLARED FILE':{ID_WIDTH}} {'ACCESS':9} {'SIZE':>12}")
    for row in sorted(rows, key=lambda r: (r["size"] is not None, r["id"])):
        name = row["id"]
        if len(name) > ID_WIDTH:
            name = name[: ID_WIDTH - 3] + "..."
        size = "MISSING" if row["size"] is None else _human(row["size"])
        mark = "ok  " if row["size"] else "--  "
        print(f"{mark}{name:{ID_WIDTH}} {row['access']:9} {size:>12}")


def main() -> int:
    """Print the evidence, then one actionable line per problem. Non-zero on FAIL."""
    rows, checks = run_checks()

    print("\nOFFLINE READINESS\n")
    _print_files(rows)

    print(f"\n{'CHECK':26} {'STATUS':6} DETAIL")
    for check in checks:
        print(f"{check.name:26} {check.status:6} {check.detail}")

    problems = [c for c in checks if c.status != "OK"]
    if problems:
        print("\nWHAT TO DO")
        for check in problems:
            print(f"  [{check.status}] {check.name}: {check.fix}")

    failures = [c for c in checks if c.status == "FAIL"]
    verdict = (
        "The demo would NOT survive without a network."
        if failures
        else "The demo runs offline."
    )
    print(
        f"\n{len(checks) - len(problems)}/{len(checks)} checks clean, "
        f"{len(failures)} blocking. {verdict}"
    )
    return 1 if failures else 0


if __name__ == "__main__":  # pragma: no cover - a script entry point
    sys.exit(main())
