# n8n workflows in git

`src/n8n_export.py` pulls every workflow out of an n8n instance and writes it
into this repository as one JSON file per workflow, normalised so that `git
diff` shows what changed in the automation and nothing else. Written
2026-10-10; the module is standalone (standard library plus `requests`) so the
same file serves every repository, see [All your repos at once](#all-your-repos-at-once).

## What it is for

n8n keeps its workflows in its own database. That gives a workflow none of what
code takes for granted:

| Without the export | With it |
|---|---|
| The edit that broke a flow at 18:00 cannot be compared with the version that worked at 17:00 | `git diff` and `git log -p n8n/workflows/<file>` show the exact node and parameter |
| Undoing a change means remembering what it was | `git revert`, then re-import the file |
| A dead instance, a deleted workflow or a wiped Docker volume is a lost year of automation | `git clone`, then `n8n import:workflow` |
| A change goes live when the editor's Save is pressed, unreviewed | The nightly export lands as a commit; a pull request reviews it like code |
| An LLM asked to debug or document an automation has nothing to read | The JSON is plain text, sorted and stable, with an `INDEX.md` listing what exists |

It also answers two questions an authority or a jury asks of any automated
pipeline: *what exactly runs*, and *since when*. The commit history is that
record.

## Setup, once

1. In the n8n UI: **Settings > n8n API > Create an API key**. On the Community
   edition the API is on unless `N8N_PUBLIC_API_DISABLED=true` was set; on n8n
   Cloud it is on every paid plan.
2. Put the two values in `.env` (never in a tracked file; `.env` is ignored):

   ```ini
   N8N_URL=http://localhost:5678      # or https://<you>.app.n8n.cloud
   N8N_API_KEY=n8n_api_...
   N8N_EXPORT_DIR=n8n/workflows       # optional, this is the default
   ```

## Use

```bash
.venv/bin/python -m src.n8n_export                          # write n8n/workflows/, commit nothing
.venv/bin/python -m src.n8n_export --commit                 # + git add, git diff --cached --stat, git commit
.venv/bin/python -m src.n8n_export --commit --push          # + git bundle backup in ../_backups, then push
.venv/bin/python -m src.n8n_export --tag flood-policy-kit   # only the workflows carrying that tag in n8n
.venv/bin/python -m src.n8n_export --check                  # exit 1 if the instance differs from the files
.venv/bin/python -m src.n8n_export --from-dir ~/Downloads   # normalise files the UI's Download button wrote
```

Every run prints what it did, file by file:

```
7 workflows -> n8n/workflows: 1 added, 2 modified, 4 unchanged, 0 deleted
  + weekly-digest__kR2x9Lm0aQ1bC3dE.json
  ~ daily-recap__abc123DEF456ghi7.json
  ~ nuts3-refresh__Zz9Yy8Xx7Ww6Vv5U.json
```

`--commit` stages **only the export folder**, prints `git diff --cached --stat`
as the last look before the commit, and writes a message like
`n8n: export workflows (+1 ~2 -0) 2026-10-10 03:17 UTC`. Nothing new means no
commit, so a nightly run on an untouched instance leaves no trace. `--push`
first writes a `git bundle` of every ref **outside** the repository
(`../_backups/<repo>-<stamp>.bundle`, restorable with `git clone`), which is the
backup-before-push habit made automatic; `--no-backup` skips it where the
remote already is the backup, such as a CI runner.

## What is written

```
n8n/workflows/
├── INDEX.md                                  # name, active, node count, tags, file
├── daily-recap__abc123DEF456ghi7.json
└── weekly-digest__kR2x9Lm0aQ1bC3dE.json
```

The file name is `<slug>__<id>.json`: the slug for a human or an LLM scanning
the folder, the id so two workflows with the same name are two files and a
rename shows up as a `git mv` rather than a delete and an add.

Each file is the API's answer, **normalised**, because the raw answer changes
on every save whether or not the workflow did, and a diff on every export is no
history at all:

- dropped: `createdAt`, `updatedAt`, `versionId`, `versionCounter`,
  `triggerCount`, `shared`, `homeProject`, `activeVersion`, and `staticData`
  (the poll state of trigger nodes, which is data about the last run, not the
  design);
- dropped unless `--keep-pindata`: `pinData`, the sample output pinned in the
  editor, often real records with personal data in them;
- tags reduced to `[{"name": ...}]` sorted by name, the shape
  `n8n import:workflow` reads, without their own ids and timestamps;
- nodes sorted by name (connections reference nodes by name, so n8n reads the
  sorted file exactly as the original) and keys sorted, two-space indent, UTF-8.

A workflow nobody touched therefore produces a byte-identical file, and
`--check` can say whether the instance and the repository agree.

**Pruning.** A full export mirrors the instance: a workflow deleted in n8n has
its file deleted here, and the commit records it. A filtered export (`--tag`,
`--active-only`, `--from-dir`) has not seen the whole instance, so it never
deletes anything. Only files matching `*__*.json` are ever pruned; a README or
a hand-written file beside them is left alone.

## Secrets never reach the repository

n8n keeps credentials out of the workflow JSON: a node carries only the
credential's id and name (`"credentials": {"slackApi": {"id": "...", "name":
"Slack account"}}`). What does travel with a workflow is a key pasted into an
HTTP header field, a query parameter, a Code node or a Set node. So every
string of every workflow is scanned before anything is written, against known
key shapes (OpenAI / Anthropic / Groq `sk-`, `gsk_`; GitHub `ghp_`,
`github_pat_`; Slack `xox?-`; AWS `AKIA`; Google `AIza`; private key blocks;
`Bearer ...`; JWTs) and against a literal value sitting under a key or header
named like one (`apiKey`, `secret`, `password`, `token`, `authorization`).
n8n expressions such as `={{ $env.SLACK_TOKEN }}` are resolved at run time and
pass.

A hit **skips that workflow**, keeps its last clean file if one exists, prints
the path of the finding with a masked preview (`sk-Z...(43 chars)`, never the
value), and makes the run exit 1 so a CI job turns red. The fix is in n8n: move
the value into a credential and reference it. `--allow-secrets` is the explicit
override for a value that only looks like one.

## Automate it

**GitHub Actions**, for an instance GitHub's runners can reach (n8n Cloud, or
self-hosted with a public URL): [`.github/workflows/n8n-export.yml`](../.github/workflows/n8n-export.yml)
runs nightly at 03:17 UTC and on demand (*Actions > n8n export > Run
workflow*). It needs two repository secrets, **Settings > Secrets and variables
> Actions**: `N8N_URL` and `N8N_API_KEY`. Without them it ends green with a
notice, so the schedule costs nothing until an instance is configured.

**Locally**, for an n8n on this machine (a runner cannot reach
`localhost:5678`): the same command in a scheduler.

```bash
# WSL / Linux crontab -e: every night at 03:17
17 3 * * * cd ~/flood-policy-kit && .venv/bin/python -m src.n8n_export --commit --push >> ~/n8n-export.log 2>&1
```

On Windows, Task Scheduler running `wsl -d Ubuntu -- <the same command>` does
the same job.

## All your repos at once

n8n is one instance, so its workflows belong in **one** place; three ways to
pick, in order of preference.

**1. One repository for the instance (recommended).** Create `n8n-workflows`,
add the two secrets, and give it this single file as
`.github/workflows/n8n-export.yml`:

```yaml
name: n8n export
on:
  schedule:
    - cron: "17 3 * * *"
  workflow_dispatch:
permissions:
  contents: write
jobs:
  export:
    uses: Siegried81/flood-policy-kit/.github/workflows/n8n-export.yml@main
    secrets: inherit                  # N8N_URL and N8N_API_KEY from this repo's secrets
    # with:
    #   tag: flood-policy-kit         # only the workflows tagged for this repo
    #   out_dir: n8n/workflows
    #   exporter_ref: main            # pin a SHA for reproducible runs
```

The exporter itself is never copied: the reusable job checks out
`src/n8n_export.py` from this repository at `exporter_ref`. Fixing a bug here
fixes every caller on its next run, which is the DRY argument for a reusable
workflow over a file per repo.

**2. The workflows that belong to a project, in that project's repo.** Tag
each workflow in n8n with the repository name, then drop the same caller file
in each repo with `tag: <repo-name>` uncommented. The export then holds only
that project's automations beside its code, and a filtered export never deletes
what belongs to another project.

**3. Installing that caller file in every repo in one go.** With the GitHub CLI
authenticated, from a folder holding the file above as `n8n-export.yml`:

```bash
for r in $(gh repo list Siegried81 --limit 200 --json name --jq '.[].name'); do
  tmp=$(mktemp -d) && gh repo clone "Siegried81/$r" "$tmp" -- --depth 1 --quiet \
    && mkdir -p "$tmp/.github/workflows" && cp n8n-export.yml "$tmp/.github/workflows/" \
    && git -C "$tmp" add .github/workflows/n8n-export.yml \
    && git -C "$tmp" commit --quiet -m "ci: nightly n8n workflow export" \
    && git -C "$tmp" push --quiet && echo "ok  $r" || echo "SKIP $r"
  rm -rf "$tmp"
done
```

Then set the two secrets once per repo (`gh secret set N8N_URL --repo
Siegried81/$r`, same for `N8N_API_KEY`), or once at organisation level if the
repos sit in one. Read the loop before running it: it pushes a commit to the
default branch of **every** repository the account owns, which is the point,
and also why option 1 is recommended over it.

## Restoring, and moving between instances

```bash
n8n import:workflow --separate --input=n8n/workflows/     # the n8n CLI, all files
```

or, in the UI, **... > Import from File** on one workflow. Credentials are not
in the files, by design: the target instance must hold credentials with the
same names (same ids, on the same instance) or the imported nodes will ask for
them. `n8n export:credentials --decrypted` exists for a migration, and its
output must never enter git.

## Limitations

- The public API lists workflows and their definition; execution history,
  credentials, variables and users are out of scope, and `n8n export:workflow`
  (the CLI) is the only route when the API is disabled.
- The secret scan is a filter on known shapes and key names, not a proof: a
  token that looks like a word passes, and `--allow-secrets` passes everything.
  `git diff --cached` before the commit is still the habit; the exporter prints
  it for that reason.
- One export mirrors one instance. Two instances (staging, production) are two
  folders or two tags, never one folder written by both.
- `tests/test_n8n_export.py` holds the normalisation, the pruning rule, the
  secret guard and the commit path against a fake API and a real temporary git
  repository, offline. It does not test an n8n instance; `--check` against a
  real one is the test of that.
