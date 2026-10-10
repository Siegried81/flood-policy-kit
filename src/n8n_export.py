"""Export every workflow of an n8n instance as diff-friendly JSON, and commit it to git.

    python -m src.n8n_export                          # export to n8n/workflows/, nothing committed
    python -m src.n8n_export --commit                 # + git add + git commit (a found secret blocks the file)
    python -m src.n8n_export --commit --push          # + git push, after a `git bundle` backup of the repo
    python -m src.n8n_export --tag flood-policy-kit   # only the workflows carrying that tag in n8n
    python -m src.n8n_export --from-dir ~/Downloads   # normalise JSON the n8n UI or CLI already exported
    python -m src.n8n_export --check                  # exit 1 if the instance differs from the files; writes nothing

Settings come from the environment, or from `.env`: N8N_URL and N8N_API_KEY (made
in the n8n UI under Settings > n8n API), and N8N_EXPORT_DIR for the output folder.

Why this exists. n8n keeps its workflows in its own database, so a workflow has no
history: the edit that broke a flow at 18:00 cannot be diffed against the version
that worked at 17:00, and a lost instance is a lost year of automation. Exporting
the JSON into git gives a workflow what code already has - a diff, a blame, a
revert, a pull request, a backup - and gives an LLM a plain-text view of the
automation it is asked to reason about.

Three decisions worth stating:

**The file is standalone on purpose.** Standard library plus `requests`, no import
from the rest of this package, so the same file can be copied into any repository,
or checked out by the reusable GitHub Action in `.github/workflows/n8n-export.yml`,
and run as `python n8n_export.py`. One file shared by every repo, not one copy per
repo that drifts.

**The JSON is normalised before it is written.** The API answer carries fields that
change on every save whether or not the workflow changed (`updatedAt`, `versionId`,
the poll state in `staticData`), its keys come in insertion order and its nodes in
the order they were added. Written as-is, every export is a diff, and a diff on
every export is no history at all. So the volatile fields are dropped, keys and
nodes are sorted, and a workflow nobody touched produces a byte-identical file.

**A secret never reaches the repository.** n8n keeps credentials out of the
workflow JSON (a node carries only the credential's id and name), but a key pasted
into an HTTP header field or a Code node travels with the workflow. Every string is
scanned before anything is written: a hit skips that workflow, is reported masked,
and makes the run exit 1. `--allow-secrets` is the explicit override.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

import requests

# `.env` is a convenience for a laptop; the GitHub Action passes real variables and
# needs no python-dotenv, which is why a missing package is not an error here.
try:
    from dotenv import load_dotenv

    load_dotenv(override=False)
except ImportError:  # pragma: no cover - only without python-dotenv installed
    pass

DEFAULT_OUT = "n8n/workflows"
INDEX_NAME = "INDEX.md"
#: The API's maximum page size; fewer round trips for an instance with hundreds of flows.
PAGE_SIZE = 250
TIMEOUT_S = 30
#: Written by n8n on every save or activation, whether or not the workflow changed.
#: `staticData` is the runtime state of polling triggers (last-seen ids and
#: timestamps): data about the last run, not the design of the workflow.
VOLATILE_KEYS = frozenset({
    "createdAt", "updatedAt", "versionId", "versionCounter", "triggerCount",
    "shared", "homeProject", "sharedWithProjects", "activeVersion", "staticData",
})
#: Files this module writes look like `<slug>__<id>.json`; prune() may delete only
#: those, so a README or a hand-written file beside them is never touched.
FILE_PATTERN = "*__*.json"

# --- Secret scanning ----------------------------------------------------------
#: Well-known key shapes. The label is what the report prints; the value never is.
_SECRET_PATTERNS = (
    ("OpenAI / Anthropic / Groq style key", re.compile(r"\b(?:sk|gsk|rk)[-_][A-Za-z0-9_-]{20,}")),
    ("GitHub token", re.compile(r"\b(?:gh[opsur]_[A-Za-z0-9]{36}|github_pat_[A-Za-z0-9_]{22,})")),
    ("Slack token", re.compile(r"\bxox[abprs]-[A-Za-z0-9-]{10,}")),
    ("AWS access key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("Google API key", re.compile(r"\bAIza[0-9A-Za-z_-]{35}")),
    ("private key block", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    ("bearer token", re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._~+/=-]{20,}")),
    ("JWT", re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}")),
)
#: A literal value sitting under a key *ending* in one of these words. Anchored at
#: the end so `tokenType: "accessToken"` is not a hit while `accessToken: "..."` is.
_SECRET_KEY = re.compile(r"(?i)(?:api[_-]?key|secret|password|passwd|token|authorization)$")
#: Shorter than this under a secret-looking key is a placeholder, not a credential.
MIN_SECRET_LEN = 8


@dataclass(frozen=True)
class Finding:
    """One string that looks like a secret. `preview` is masked: never the value."""

    workflow: str
    path: str  # e.g. nodes[3].parameters.headerParameters.parameters[0].value
    kind: str
    preview: str


def _mask(value: str) -> str:
    """ASCII only: a report piped to a log file on Windows is not UTF-8 by default."""
    return f"{value[:4]}...({len(value)} chars)"


def _walk(obj, path: str = "", key: str = "") -> Iterator[tuple[str, str, str]]:
    """Yield (json_path, key_name, value) for every string in a JSON tree.

    `key_name` is the key the string sits under - or, for n8n's `{"name": ...,
    "value": ...}` parameter pairs (headers, query fields), the sibling `name`, so a
    header called `x-api-key` is judged by that name rather than by the key `value`.
    """
    if isinstance(obj, str):
        yield path, key, obj
    elif isinstance(obj, dict):
        label = obj.get("name") if isinstance(obj.get("name"), str) else ""
        for k, v in obj.items():
            yield from _walk(v, f"{path}.{k}" if path else k, label if (k == "value" and label) else k)
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from _walk(v, f"{path}[{i}]", key)


def _is_literal(value: str) -> bool:
    """An n8n expression (`={{ $env.KEY }}`) is resolved at run time: nothing to leak."""
    v = value.strip()
    return len(v) >= MIN_SECRET_LEN and not v.startswith("=") and "{{" not in v


def find_secrets(workflow: dict) -> list[Finding]:
    """Every string in `workflow` that matches a known key shape or sits, as a
    literal, under a key named like a secret. Scan the *normalised* workflow, so
    what is judged is exactly what would be written."""
    found = []
    for path, key, value in _walk(workflow):
        kind = next((label for label, rx in _SECRET_PATTERNS if rx.search(value)), None)
        if kind is None and _SECRET_KEY.search(key) and _is_literal(value):
            kind = f"literal value under '{key}'"
        if kind:
            found.append(Finding(str(workflow.get("name", "?")), path, kind, _mask(value)))
    return found


# --- Normalisation -------------------------------------------------------------
def normalise(workflow: dict, keep_pindata: bool = False) -> dict:
    """The part of a workflow worth versioning, in a stable shape.

    - volatile fields dropped (see VOLATILE_KEYS);
    - `pinData` dropped unless asked: it is sample output pinned in the editor,
      often real records with personal data, and it bloats every diff;
    - tags reduced to `{"name": ...}` sorted by name - the shape `n8n
      import:workflow` reads - without their own ids and timestamps;
    - nodes sorted by name. The editor lists them in insertion order, and
      connections reference nodes by name, so this changes nothing n8n reads and
      stops a re-added node from reshuffling the whole file.
    """
    out = {k: v for k, v in workflow.items() if k not in VOLATILE_KEYS}
    if not keep_pindata:
        out.pop("pinData", None)
    if isinstance(out.get("tags"), list):
        names = sorted(t["name"] if isinstance(t, dict) else str(t) for t in out["tags"])
        out["tags"] = [{"name": n} for n in names]
    if isinstance(out.get("nodes"), list):
        out["nodes"] = sorted(out["nodes"], key=lambda n: str(n.get("name", "")))
    return out


def dump(workflow: dict) -> str:
    """Sorted keys, two-space indent, UTF-8 as written, one trailing newline: the
    same dict always gives the same bytes, which is what makes `git diff` honest."""
    return json.dumps(workflow, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


_NON_SLUG = re.compile(r"[^a-z0-9]+")


def slug(name: str, limit: int = 60) -> str:
    """`Récap journalier (v2)` -> `recap-journalier-v2`: accents folded, ASCII only."""
    ascii_name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    return _NON_SLUG.sub("-", ascii_name.lower()).strip("-")[:limit].rstrip("-") or "workflow"


def file_name(workflow: dict) -> str:
    """`<slug>__<id>.json`. The slug is for humans and LLMs, the id makes two
    workflows with the same name two files and survives a rename as a `git mv`."""
    wid = str(workflow.get("id") or "").strip()
    base = slug(str(workflow.get("name", "")))
    return f"{base}__{wid}.json" if wid else f"{base}.json"


# --- The n8n API ----------------------------------------------------------------
class N8nClient:
    """The two calls this needs from n8n's public REST API (`<url>/api/v1`)."""

    def __init__(self, url: str, api_key: str, timeout: float = TIMEOUT_S, session=None):
        if not url or not api_key:
            raise SystemExit("N8N_URL and N8N_API_KEY are required "
                             "(the key is made in the n8n UI: Settings > n8n API)")
        self.base = url.rstrip("/") + "/api/v1"
        self.timeout = timeout
        self.session = session or requests.Session()
        self.session.headers.update({"X-N8N-API-KEY": api_key, "Accept": "application/json"})

    def _get(self, path: str, **params) -> dict:
        response = self.session.get(f"{self.base}/{path}", params=params or None, timeout=self.timeout)
        if response.status_code == 401:
            # The one failure whose cause is not in the message n8n returns.
            raise SystemExit(f"{self.base}: HTTP 401 - N8N_API_KEY was refused "
                             "(expired, revoked, or made on another instance)")
        response.raise_for_status()
        return response.json()

    def workflows(self, tags: tuple[str, ...] | list[str] = (), active_only: bool = False) -> list[dict]:
        """Every workflow with its full definition, across all pages.

        Only `limit`, `cursor`, `tags` and `active` are sent: the API validates its
        query parameters against a schema, so an unknown one is a 400, not a no-op.
        """
        params: dict = {"limit": PAGE_SIZE}
        if tags:
            params["tags"] = ",".join(tags)
        if active_only:
            params["active"] = "true"
        out: list[dict] = []
        while True:
            page = self._get("workflows", **params)
            for item in page.get("data", []):
                # A version that lists summaries only is answered with one more call.
                out.append(item if "nodes" in item else self._get(f"workflows/{item['id']}"))
            params["cursor"] = page.get("nextCursor")
            if not params["cursor"]:
                return out


def load_local(path: Path) -> list[dict]:
    """Workflows from JSON the n8n CLI (`n8n export:workflow`) or the UI's Download
    button wrote: a file holds one workflow or a list, a directory is read file by file."""
    files = sorted(path.glob("*.json")) if path.is_dir() else [path]
    out: list[dict] = []
    for f in files:
        data = json.loads(f.read_text(encoding="utf-8"))
        out.extend(data if isinstance(data, list) else [data])
    return out


# --- Writing the export ---------------------------------------------------------
@dataclass
class Summary:
    """What one run did, file by file. `skipped` holds the secret findings."""

    added: list[str] = field(default_factory=list)
    modified: list[str] = field(default_factory=list)
    unchanged: list[str] = field(default_factory=list)
    deleted: list[str] = field(default_factory=list)
    skipped: list[Finding] = field(default_factory=list)

    @property
    def changed(self) -> bool:
        return bool(self.added or self.modified or self.deleted)

    def report(self) -> str:
        lines = [f"{len(self.added)} added, {len(self.modified)} modified, "
                 f"{len(self.unchanged)} unchanged, {len(self.deleted)} deleted"]
        lines += [f"  + {n}" for n in self.added] + [f"  ~ {n}" for n in self.modified]
        lines += [f"  - {n}" for n in self.deleted]
        lines += [f"  SECRET {f.workflow}: {f.path} [{f.kind}] {f.preview}" for f in self.skipped]
        return "\n".join(lines)


def render_index(workflows: list[dict]) -> str:
    """One Markdown table, no timestamp: a timestamp would make every run a diff."""
    rows = sorted(workflows, key=lambda w: str(w.get("name", "")).lower())
    active = sum(bool(w.get("active")) for w in rows)
    lines = [
        "# n8n workflows",
        "",
        f"Written by `n8n_export.py` - edit the workflows in n8n, not here. "
        f"{len(rows)} workflows, {active} active.",
        "",
        "| Workflow | Active | Nodes | Tags | File |",
        "|---|---|---|---|---|",
    ]
    for w in rows:
        name = file_name(w)
        tags = ", ".join(t.get("name", "") if isinstance(t, dict) else str(t) for t in w.get("tags") or [])
        lines.append(f"| {w.get('name', '')} | {'yes' if w.get('active') else 'no'} | "
                     f"{len(w.get('nodes') or [])} | {tags} | [`{name}`]({name}) |")
    return "\n".join(lines) + "\n"


def write_export(workflows: list[dict], out_dir: Path, *, keep_pindata: bool = False,
                 prune: bool = True, allow_secrets: bool = False, write: bool = True) -> Summary:
    """Normalise, scan, write one file per workflow, prune, index.

    `prune` deletes files matching FILE_PATTERN whose workflow was not in this
    export - the folder mirrors the instance. The caller turns it off for a
    filtered export (`--tag`, `--active-only`, `--from-dir`), which has not seen
    the whole instance and must not delete what it did not look at. A workflow
    skipped for a secret keeps its previous file: the last clean version stays.
    `write=False` computes the summary and touches nothing.
    """
    summary, kept, clean = Summary(), set(), []
    for raw in workflows:
        wf = normalise(raw, keep_pindata)
        name = file_name(wf)
        kept.add(name)
        findings = find_secrets(wf)
        if findings and not allow_secrets:
            summary.skipped.extend(findings)
            continue
        clean.append(wf)
        path, text = out_dir / name, dump(wf)
        if not path.exists():
            summary.added.append(name)
        elif path.read_text(encoding="utf-8") != text:
            summary.modified.append(name)
        else:
            summary.unchanged.append(name)
            continue
        if write:
            out_dir.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
    if prune and out_dir.is_dir():
        for stale in sorted(out_dir.glob(FILE_PATTERN)):
            if stale.name not in kept:
                summary.deleted.append(stale.name)
                if write:
                    stale.unlink()
    if write:
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / INDEX_NAME).write_text(render_index(clean), encoding="utf-8")
    return summary


# --- Git ----------------------------------------------------------------------
def _git(repo: Path, *args: str) -> str:
    try:
        proc = subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True)
    except FileNotFoundError:  # e.g. inside the python:3.12-slim image, which ships no git
        raise SystemExit("git is not installed here: export without --commit, or run on a machine with git")
    if proc.returncode:
        raise SystemExit(f"git {' '.join(args)} failed:\n{proc.stderr.strip()}")
    return proc.stdout


def repo_root(path: Path) -> Path | None:
    """The repository `path` sits in, or None - `--out` may point outside any repo.
    A folder that does not exist yet is judged by its nearest existing parent."""
    start = next((p for p in [path, *path.resolve().parents] if p.is_dir()), None)
    if start is None:
        return None
    proc = subprocess.run(["git", "rev-parse", "--show-toplevel"], cwd=start,
                          capture_output=True, text=True)
    return Path(proc.stdout.strip()) if proc.returncode == 0 else None


def default_message(summary: Summary) -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    return (f"n8n: export workflows (+{len(summary.added)} ~{len(summary.modified)} "
            f"-{len(summary.deleted)}) {stamp}")


def commit_export(repo: Path, out_dir: Path, summary: Summary, message: str | None = None) -> bool:
    """Stage the export folder only, show `git diff --cached --stat` as the last look
    before anything is committed, and commit. False when there was nothing to commit."""
    _git(repo, "add", "--all", "--", str(out_dir.resolve()))
    staged = _git(repo, "diff", "--cached", "--stat", "--", str(out_dir.resolve())).strip()
    if not staged:
        return False
    print(staged)
    _git(repo, "commit", "--quiet", "-m", message or default_message(summary))
    return True


def backup_bundle(repo: Path, into: Path | None = None) -> Path:
    """`git bundle` of every ref, written *outside* the repository before a push
    touches the remote. Restore with `git clone <file>.bundle`."""
    into = into or repo.parent / "_backups"
    into.mkdir(parents=True, exist_ok=True)
    target = into / f"{repo.name}-{datetime.now(timezone.utc):%Y%m%d-%H%M%S}.bundle"
    _git(repo, "bundle", "create", str(target), "--all")
    return target


def push(repo: Path) -> str:
    branch = _git(repo, "rev-parse", "--abbrev-ref", "HEAD").strip()
    _git(repo, "push", "-u", "origin", branch)
    return branch


# --- CLI ----------------------------------------------------------------------
def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__.split("\n\n")[0], formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--url", default=os.environ.get("N8N_URL"), help="n8n base URL (env N8N_URL)")
    parser.add_argument("--out", type=Path, default=Path(os.environ.get("N8N_EXPORT_DIR") or DEFAULT_OUT),
                        help=f"output folder (env N8N_EXPORT_DIR, default {DEFAULT_OUT})")
    parser.add_argument("--from-dir", type=Path, metavar="PATH",
                        help="read workflows from a local JSON file or folder instead of the API")
    parser.add_argument("--tag", action="append", default=[], help="only workflows with this n8n tag (repeatable)")
    parser.add_argument("--active-only", action="store_true", help="only active workflows")
    parser.add_argument("--keep-pindata", action="store_true", help="keep the sample data pinned in the editor")
    parser.add_argument("--allow-secrets", action="store_true", help="write a workflow even if a secret is found")
    parser.add_argument("--check", action="store_true", help="exit 1 if anything would change; writes nothing")
    parser.add_argument("--commit", action="store_true", help="git add + git commit the export folder")
    parser.add_argument("--push", action="store_true", help="implies --commit; a git bundle backup is written first")
    parser.add_argument("--backup-dir", type=Path, help="where the bundle goes (default: ../_backups)")
    parser.add_argument("--no-backup", action="store_true", help="push without the bundle (CI has the remote)")
    args = parser.parse_args(argv)

    if args.from_dir:
        workflows = load_local(args.from_dir)
    else:
        workflows = N8nClient(args.url or "", os.environ.get("N8N_API_KEY", "")).workflows(
            args.tag, args.active_only)
    # A partial view must not prune: see write_export.
    partial = bool(args.tag or args.active_only or args.from_dir)
    summary = write_export(workflows, args.out, keep_pindata=args.keep_pindata, prune=not partial,
                           allow_secrets=args.allow_secrets, write=not args.check)
    print(f"{len(workflows)} workflows -> {args.out}: {summary.report()}")

    if args.check:
        return 1 if summary.changed else 0
    if args.commit or args.push:
        repo = repo_root(args.out)
        if repo is None:
            raise SystemExit(f"{args.out} is not inside a git repository; drop --commit or move --out")
        print("committed" if commit_export(repo, args.out, summary) else "nothing to commit")
        if args.push:
            if not args.no_backup:
                print(f"backup: {backup_bundle(repo, args.backup_dir)}")
            print(f"pushed {push(repo)}")
    if summary.skipped:
        print(f"{len(summary.skipped)} secret(s) found: those workflows were NOT written. "
              "Move the value into an n8n credential, or re-run with --allow-secrets.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
