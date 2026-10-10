"""Tests for the n8n -> git exporter. No network: the API is a fake session.

What matters is not that a download works but the three guarantees the module
claims: an untouched workflow gives byte-identical output, a filtered export
never deletes what it did not see, and a secret never reaches the folder git
tracks. Git itself is real, in a temporary repository: the commit path is the
one that ends up on GitHub, so it is not mocked.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from src import n8n_export as X


# --- Fixtures -------------------------------------------------------------------
def _workflow(wid="abc123", name="Daily recap", active=True, **extra) -> dict:
    """The shape `GET /api/v1/workflows/{id}` returns, volatile fields included,
    nodes in editor (insertion) order, tags as full objects."""
    wf = {
        "id": wid,
        "name": name,
        "active": active,
        "createdAt": "2026-10-01T08:00:00.000Z",
        "updatedAt": "2026-10-10T11:59:00.000Z",
        "versionId": "9f8e7d",
        "triggerCount": 3,
        "staticData": {"lastPoll": 1760000000},
        "shared": [{"role": "workflow:owner"}],
        "tags": [
            {"id": "t2", "name": "ops", "createdAt": "x", "updatedAt": "y"},
            {"id": "t1", "name": "flood-policy-kit", "createdAt": "x", "updatedAt": "y"},
        ],
        "nodes": [
            {"name": "Zulu node", "type": "n8n-nodes-base.set", "position": [400, 0], "parameters": {}},
            {"name": "Alpha trigger", "type": "n8n-nodes-base.cron", "position": [0, 0], "parameters": {}},
        ],
        "connections": {"Alpha trigger": {"main": [[{"node": "Zulu node", "type": "main", "index": 0}]]}},
        "settings": {"executionOrder": "v1"},
        "pinData": {"Alpha trigger": [{"json": {"email": "someone@example.org"}}]},
    }
    wf.update(extra)
    return wf


class _FakeResponse:
    def __init__(self, payload, status=200):
        self._payload, self.status_code = payload, status

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


class _FakeSession:
    """Answers `GET <base>/workflows` page by page and `GET <base>/workflows/<id>`."""

    def __init__(self, pages, details=None, status=200):
        self.pages, self.details, self.status = list(pages), details or {}, status
        self.headers, self.calls = {}, []

    def get(self, url, params=None, timeout=None):
        self.calls.append((url, dict(params or {})))
        if self.status != 200:
            return _FakeResponse({}, self.status)
        if url.endswith("/workflows"):
            cursor = (params or {}).get("cursor")
            index = int(cursor) if cursor else 0
            page = self.pages[index]
            nxt = str(index + 1) if index + 1 < len(self.pages) else None
            return _FakeResponse({"data": page, "nextCursor": nxt})
        return _FakeResponse(self.details[url.rsplit("/", 1)[1]])


@pytest.fixture
def repo(tmp_path):
    """A real git repository with an identity, so `git commit` works on a bare runner."""
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.email", "t@example.org"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "tests"], cwd=tmp_path, check=True)
    return tmp_path


def _log(repo: Path) -> list[str]:
    out = subprocess.run(["git", "log", "--format=%s"], cwd=repo, capture_output=True, text=True)
    return out.stdout.strip().splitlines()


# --- Normalisation --------------------------------------------------------------
def test_normalise_drops_volatile_fields_and_pindata():
    out = X.normalise(_workflow())
    for key in X.VOLATILE_KEYS | {"pinData"}:
        assert key not in out
    # What the design is made of survives.
    assert {"id", "name", "active", "nodes", "connections", "settings", "tags"} <= out.keys()


def test_normalise_keeps_pindata_only_when_asked():
    assert "pinData" in X.normalise(_workflow(), keep_pindata=True)


def test_normalise_sorts_nodes_by_name_and_tags_to_names():
    out = X.normalise(_workflow())
    assert [n["name"] for n in out["nodes"]] == ["Alpha trigger", "Zulu node"]
    # Tags keep the `{"name": ...}` shape `n8n import:workflow` reads, nothing else.
    assert out["tags"] == [{"name": "flood-policy-kit"}, {"name": "ops"}]


def test_dump_is_byte_stable_whatever_the_key_order():
    """Same workflow, keys in another order, nodes re-added: identical bytes."""
    a = X.dump(X.normalise(_workflow()))
    shuffled = dict(reversed(list(_workflow().items())))
    shuffled["nodes"] = list(reversed(shuffled["nodes"]))
    shuffled["updatedAt"] = "2026-10-11T00:00:00.000Z"
    assert X.dump(X.normalise(shuffled)) == a
    assert a.endswith("\n") and "é" in X.dump({"n": "é"})  # ensure_ascii=False


# --- File names -------------------------------------------------------------------
@pytest.mark.parametrize("name, expected", [
    ("Daily recap", "daily-recap"),
    ("Récap journalier (v2)", "recap-journalier-v2"),
    ("  --weird__chars!!  ", "weird-chars"),
    ("", "workflow"),
    ("x" * 100, "x" * 60),
])
def test_slug(name, expected):
    assert X.slug(name) == expected


def test_file_name_uses_slug_and_id_and_falls_back_without_id():
    assert X.file_name({"id": "abc123", "name": "Daily recap"}) == "daily-recap__abc123.json"
    assert X.file_name({"name": "Daily recap"}) == "daily-recap.json"
    # Two workflows with one name are two files.
    assert X.file_name({"id": "1", "name": "Dup"}) != X.file_name({"id": "2", "name": "Dup"})


# --- Secret scanning --------------------------------------------------------------
@pytest.mark.parametrize("value, kind", [
    ("sk-ant-api03-" + "A" * 40, "OpenAI / Anthropic / Groq style key"),
    ("gsk_" + "b" * 40, "OpenAI / Anthropic / Groq style key"),
    ("ghp_" + "c" * 36, "GitHub token"),
    ("AKIA" + "Q" * 16, "AWS access key"),
    ("Bearer " + "d" * 30, "bearer token"),
    ("-----BEGIN RSA PRIVATE KEY-----\nMIIE...", "private key block"),
    ("eyJ" + "a" * 20 + ".eyJ" + "b" * 20 + "." + "c" * 20, "JWT"),
])
def test_find_secrets_detects_known_shapes(value, kind):
    wf = _workflow(nodes=[{"name": "Code", "parameters": {"jsCode": f"const k = '{value}';"}}])
    found = X.find_secrets(X.normalise(wf))
    assert [f.kind for f in found] == [kind]
    assert found[0].path == "nodes[0].parameters.jsCode"
    assert found[0].workflow == "Daily recap"


def test_find_secrets_preview_never_contains_the_value():
    secret = "sk-" + "Z" * 40
    wf = _workflow(nodes=[{"name": "n", "parameters": {"k": secret}}])
    found = X.find_secrets(X.normalise(wf))
    assert secret not in found[0].preview and found[0].preview == "sk-Z...(43 chars)"
    assert secret not in X.Summary(skipped=found).report()


def test_find_secrets_literal_under_a_secret_named_key_and_header_pairs():
    wf = _workflow(nodes=[{
        "name": "HTTP Request",
        "parameters": {
            "apiKey": "literal-key-value-123",                       # key rule
            "headerParameters": {"parameters": [
                {"name": "x-api-key", "value": "literal-header-value"},  # name/value pair rule
                {"name": "Accept", "value": "application/json"},          # harmless pair
            ]},
            "tokenType": "accessToken",                              # ends in Type, not token
        },
    }])
    paths = {f.path for f in X.find_secrets(X.normalise(wf))}
    assert paths == {"nodes[0].parameters.apiKey",
                     "nodes[0].parameters.headerParameters.parameters[0].value"}


def test_find_secrets_ignores_expressions_placeholders_and_credential_refs():
    wf = _workflow(nodes=[{
        "name": "Slack",
        "credentials": {"slackApi": {"id": "cred1", "name": "Slack account token"}},
        "parameters": {
            "token": "={{ $env.SLACK_TOKEN }}",   # n8n expression: resolved at run time
            "password": "{{ $json.password }}",
            "secret": "",                          # empty
            "apiKey": "short",                     # below MIN_SECRET_LEN
            "authentication": "predefinedCredentialType",
        },
    }])
    assert X.find_secrets(X.normalise(wf)) == []


# --- The API client -------------------------------------------------------------
def test_client_requires_url_and_key():
    with pytest.raises(SystemExit, match="N8N_URL and N8N_API_KEY"):
        X.N8nClient("", "")
    with pytest.raises(SystemExit):
        X.N8nClient("http://n8n", "")


def test_client_paginates_with_the_cursor_and_sends_the_key():
    session = _FakeSession(pages=[[_workflow("a")], [_workflow("b"), _workflow("c")]])
    got = X.N8nClient("http://n8n:5678/", "KEY", session=session).workflows()
    assert [w["id"] for w in got] == ["a", "b", "c"]
    assert session.headers["X-N8N-API-KEY"] == "KEY"
    urls = [u for u, _ in session.calls]
    assert urls == ["http://n8n:5678/api/v1/workflows"] * 2
    assert session.calls[0][1] == {"limit": X.PAGE_SIZE}
    assert session.calls[1][1]["cursor"] == "1"


def test_client_fetches_the_detail_when_the_list_has_no_nodes():
    """An older instance lists summaries; the full object costs one more call."""
    summary = {"id": "a", "name": "Daily recap", "active": True}
    session = _FakeSession(pages=[[summary]], details={"a": _workflow("a")})
    got = X.N8nClient("http://n8n", "KEY", session=session).workflows()
    assert got[0]["nodes"] and session.calls[-1][0].endswith("/workflows/a")


def test_client_filters_are_query_parameters():
    session = _FakeSession(pages=[[]])
    X.N8nClient("http://n8n", "KEY", session=session).workflows(tags=["ops", "x"], active_only=True)
    assert session.calls[0][1] == {"limit": X.PAGE_SIZE, "tags": "ops,x", "active": "true"}


def test_client_401_names_the_key():
    session = _FakeSession(pages=[[]], status=401)
    with pytest.raises(SystemExit, match="N8N_API_KEY was refused"):
        X.N8nClient("http://n8n", "KEY", session=session).workflows()


# --- Writing ----------------------------------------------------------------------
def test_write_export_adds_then_reports_unchanged_then_modifies_and_prunes(tmp_path):
    out = tmp_path / "wf"
    first = X.write_export([_workflow("a"), _workflow("b", "Other")], out)
    assert sorted(first.added) == ["daily-recap__a.json", "other__b.json"]
    assert (out / X.INDEX_NAME).exists()

    # Same instance, only volatile fields moved: nothing changes on disk.
    again = X.write_export([_workflow("a", updatedAt="later"), _workflow("b", "Other")], out)
    assert not again.changed and len(again.unchanged) == 2

    # One edited, one deleted in n8n: the folder follows.
    third = X.write_export([_workflow("a", active=False)], out)
    assert third.modified == ["daily-recap__a.json"] and third.deleted == ["other__b.json"]
    assert not (out / "other__b.json").exists()
    assert json.loads((out / "daily-recap__a.json").read_text())["active"] is False


def test_write_export_prune_touches_only_its_own_pattern(tmp_path):
    out = tmp_path / "wf"
    out.mkdir()
    (out / "README.md").write_text("mine")
    (out / "notes.json").write_text("{}")
    (out / "gone__zzz.json").write_text("{}")
    summary = X.write_export([_workflow("a")], out)
    assert summary.deleted == ["gone__zzz.json"]
    assert (out / "README.md").exists() and (out / "notes.json").exists()


def test_write_export_without_prune_keeps_everything(tmp_path):
    """A `--tag` export saw a subset: the rest of the folder must survive it."""
    out = tmp_path / "wf"
    X.write_export([_workflow("a"), _workflow("b", "Other")], out)
    summary = X.write_export([_workflow("a")], out, prune=False)
    assert summary.deleted == [] and (out / "other__b.json").exists()


def test_write_export_skips_a_workflow_with_a_secret_and_keeps_its_last_clean_file(tmp_path):
    out = tmp_path / "wf"
    X.write_export([_workflow("a")], out)
    leaky = _workflow("a", nodes=[{"name": "n", "parameters": {"apiKey": "sk-" + "q" * 40}}])
    summary = X.write_export([leaky], out)
    assert summary.skipped and summary.added == summary.modified == summary.deleted == []
    on_disk = (out / "daily-recap__a.json").read_text(encoding="utf-8")
    assert "sk-qqqq" not in on_disk            # the previous clean version is still there
    assert "daily-recap__a.json" not in (out / X.INDEX_NAME).read_text()  # and not advertised
    forced = X.write_export([leaky], out, allow_secrets=True)
    assert forced.modified == ["daily-recap__a.json"] and forced.skipped == []


def test_write_export_check_mode_writes_nothing(tmp_path):
    out = tmp_path / "wf"
    summary = X.write_export([_workflow("a")], out, write=False)
    assert summary.added == ["daily-recap__a.json"] and not out.exists()


def test_render_index_lists_every_workflow_without_a_timestamp():
    text = X.render_index([X.normalise(_workflow("a")), X.normalise(_workflow("b", "Other", active=False))])
    assert "| Daily recap | yes | 2 | flood-policy-kit, ops | [`daily-recap__a.json`](daily-recap__a.json) |" in text
    assert "| Other | no |" in text and "2 workflows, 1 active" in text
    assert "2026" not in text


def test_load_local_reads_a_file_a_list_and_a_folder(tmp_path):
    (tmp_path / "one.json").write_text(json.dumps(_workflow("a")))
    (tmp_path / "many.json").write_text(json.dumps([_workflow("b"), _workflow("c")]))
    assert [w["id"] for w in X.load_local(tmp_path)] == ["b", "c", "a"]   # sorted by file name
    assert [w["id"] for w in X.load_local(tmp_path / "one.json")] == ["a"]


# --- Git ------------------------------------------------------------------------
def test_commit_export_commits_only_the_export_folder(repo, capsys):
    out = repo / "n8n" / "workflows"
    (repo / "unrelated.txt").write_text("not staged")
    summary = X.write_export([_workflow("a")], out)
    assert X.commit_export(repo, out, summary) is True
    assert _log(repo)[0].startswith("n8n: export workflows (+1 ~0 -0) 2026-")
    assert "daily-recap__a.json" in capsys.readouterr().out     # the diff --cached --stat shown
    status = subprocess.run(["git", "status", "--porcelain"], cwd=repo, capture_output=True, text=True).stdout
    assert status.strip() == "?? unrelated.txt"
    # Nothing new: no empty commit.
    assert X.commit_export(repo, out, X.write_export([_workflow("a")], out)) is False
    assert len(_log(repo)) == 1


def test_backup_bundle_is_written_outside_the_repo_and_clones(repo, tmp_path):
    out = repo / "wf"
    X.commit_export(repo, out, X.write_export([_workflow("a")], out))
    bundle = X.backup_bundle(repo)
    assert bundle.parent == repo.parent / "_backups" and bundle.suffix == ".bundle"
    clone = tmp_path / "restored"
    subprocess.run(["git", "clone", "-q", str(bundle), str(clone)], check=True)
    assert (clone / "wf" / "daily-recap__a.json").exists()


def test_repo_root_finds_the_repo_even_for_a_folder_not_created_yet(repo, tmp_path):
    assert X.repo_root(repo / "n8n" / "workflows") == repo.resolve()
    # tmp_path may itself sit inside a repository on a developer machine, so
    # "outside" is asserted relative to what git says about the parent.
    outside = X.repo_root(tmp_path)
    assert X.repo_root(tmp_path / "nowhere" / "deeper") == outside


# --- main() ---------------------------------------------------------------------
def test_main_from_dir_exports_and_commits(repo, monkeypatch):
    src = repo / "downloads"
    src.mkdir()
    (src / "a.json").write_text(json.dumps(_workflow("a")))
    monkeypatch.chdir(repo)
    assert X.main(["--from-dir", "downloads", "--out", "n8n/workflows", "--commit"]) == 0
    assert (repo / "n8n" / "workflows" / "daily-recap__a.json").exists()
    assert len(_log(repo)) == 1


def test_main_uses_the_client_and_prunes_only_an_unfiltered_export(tmp_path, monkeypatch):
    seen = []

    def fake_workflows(self, tags=(), active_only=False):
        seen.append((tuple(tags), active_only))
        return [_workflow("a")]

    monkeypatch.setattr(X.N8nClient, "workflows", fake_workflows)
    monkeypatch.setenv("N8N_URL", "http://n8n")
    monkeypatch.setenv("N8N_API_KEY", "k")
    out = tmp_path / "wf"
    (out).mkdir()
    (out / "old__zzz.json").write_text("{}")
    assert X.main(["--out", str(out), "--tag", "ops"]) == 0
    assert (out / "old__zzz.json").exists()            # filtered: not pruned
    assert X.main(["--out", str(out)]) == 0
    assert not (out / "old__zzz.json").exists()        # unfiltered: pruned
    assert seen == [(("ops",), False), ((), False)]


def test_main_check_exits_1_when_the_instance_moved(tmp_path, monkeypatch):
    monkeypatch.setattr(X.N8nClient, "workflows", lambda self, tags=(), active_only=False: [_workflow("a")])
    monkeypatch.setenv("N8N_URL", "http://n8n")
    monkeypatch.setenv("N8N_API_KEY", "k")
    out = tmp_path / "wf"
    assert X.main(["--out", str(out), "--check"]) == 1 and not out.exists()
    assert X.main(["--out", str(out)]) == 0
    assert X.main(["--out", str(out), "--check"]) == 0


def test_main_exits_1_and_commits_nothing_leaky_when_a_secret_is_found(repo, monkeypatch, capsys):
    secret = "ghp_" + "x" * 36
    leaky = _workflow("a", nodes=[{"name": "n", "parameters": {"jsCode": secret}}])
    (repo / "in.json").write_text(json.dumps([leaky, _workflow("b", "Clean")]))
    monkeypatch.chdir(repo)
    assert X.main(["--from-dir", "in.json", "--out", "wf", "--commit"]) == 1
    tracked = subprocess.run(["git", "ls-files"], cwd=repo, capture_output=True, text=True).stdout
    assert "wf/clean__b.json" in tracked and "daily-recap" not in tracked
    out = capsys.readouterr().out
    assert "SECRET" in out and secret not in out


def test_main_refuses_commit_outside_a_repository(tmp_path, monkeypatch):
    (tmp_path / "in.json").write_text(json.dumps(_workflow("a")))
    lone = tmp_path / "lone"
    lone.mkdir()
    if X.repo_root(lone) is not None:
        pytest.skip("tmp_path sits inside a git repository on this machine")
    with pytest.raises(SystemExit, match="not inside a git repository"):
        X.main(["--from-dir", str(tmp_path / "in.json"), "--out", str(lone / "wf"), "--commit"])
