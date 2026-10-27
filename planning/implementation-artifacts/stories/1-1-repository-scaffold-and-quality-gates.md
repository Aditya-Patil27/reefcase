# Story 1.1: Repository scaffold and quality gates

Owner: Opus (lead-b) · Priority: P0 · Depends on: none · Status: in-progress

## Story (verbatim from epics.md)

As a developer,
I want a repo where lint, types, import layering and tests run with one command,
So that every later story has an objective definition of done.

- Owner: Opus · Priority: P0 · Depends on: none
- Files: `pyproject.toml`, `.python-version`, `.gitignore`, `.env.example`, `src/reefcase/__init__.py`, `tests/test_smoke.py`, `.github/workflows/ci.yml`, `data/LICENSES.md` (`AGENTS.md` already exists and is frozen; don't edit it)
- Done when: `uv run poe gate` passes locally and in CI. `pyproject.toml` defines a poethepoet task `gate` that runs `ruff check`, `ruff format --check`, `pyright`, `lint-imports` and `pytest -m "not gpu and not live"`

### Acceptance Criteria (verbatim)

**Given** a fresh clone
**When** `uv sync` then the done-when command run
**Then** all four gates pass
**And** `lint-imports` contains the layer contract from architecture §3

**Given** `pyproject.toml`
**When** `uv run poe gate` runs
**Then** pytest registers the `gpu` and `live` markers, and the gate skips both

## Architecture sections this story touches

### §3 — Repository layout (directory skeleton to create)

```
reefcase/
├── pyproject.toml            # uv project, ruff, pyright, pytest, import-linter config
├── uv.lock
├── AGENTS.md                 # frozen, do not edit
├── .env.example
├── src/reefcase/{core,store,ingest,vision,llm,tools,agent,pipeline,api,bot}/
├── tests/                    # mirrors src/reefcase/; fixtures/ and cassettes/
├── ml/{kaggle,modal}/
├── web/
├── data/geo/, data/demo/, data/LICENSES.md
└── var/                      # runtime, git-ignored
```

### §3 — Layering (exact contract to encode in `lint-imports`)

```
api, bot ──► pipeline ──► agent ──► tools, llm ──► store ──► core
                     └──► vision, ingest ─────────► store ──► core
```

A module may import only from layers to its right. `core` imports only the standard library and pydantic.

Encode as **two** import-linter contracts:

1. `layers`, name `reefcase layering`, `containers = ["reefcase"]`, layers (high → low):
   `["api | bot", "pipeline", "agent", "tools | llm", "vision | ingest", "store", "core"]`
2. `forbidden`, name `core imports only stdlib and pydantic`,
   `source_modules = ["reefcase.core"]`,
   `forbidden_modules = ["reefcase.api", "reefcase.bot", "reefcase.pipeline", "reefcase.agent", "reefcase.tools", "reefcase.llm", "reefcase.vision", "reefcase.ingest", "reefcase.store"]`

Do **not** set `exhaustive = true`.

### §4.4 — Configuration (source of truth for `.env.example`)

`Settings(BaseSettings)` prefix `REEFCASE_`. Every variable below goes into `.env.example` with an **empty** value and a one-line comment on what it is; never a real value. Sorted as in the table:

`REEFCASE_DATA_DIR`, `REEFCASE_SEGMENTER`, `REEFCASE_SAM_MODEL_ID`, `REEFCASE_SAM_MODAL_URL`, `REEFCASE_STUDENT_WEIGHTS`, `REEFCASE_LLM_AGENT_BASE_URL`, `REEFCASE_LLM_AGENT_API_KEY`, `REEFCASE_LLM_AGENT_MODEL`, `REEFCASE_LLM_TEACHER_BASE_URL`, `REEFCASE_LLM_TEACHER_API_KEY`, `REEFCASE_LLM_TEACHER_MODEL`, `REEFCASE_LLM_STUDENT_BASE_URL`, `REEFCASE_LLM_STUDENT_API_KEY`, `REEFCASE_LLM_STUDENT_MODEL`, `REEFCASE_LLM_AGENT_REASONING_EFFORT`, `REEFCASE_LLM_TEACHER_REASONING_EFFORT`, `REEFCASE_GFW_TOKEN`, `REEFCASE_TELEGRAM_TOKEN`, `REEFCASE_KEEP_FRAMES`, `REEFCASE_MIN_FRAMES`.

This story creates only the example file — `config.py` is Story 1.3. `.env.example` is committed; `.env` is git-ignored (already in `.gitignore`).

### §9.9 — Licence summary (verbatim source for `data/LICENSES.md`)

| Source | Licence | Obligation |
|---|---|---|
| GFW | CC BY-NC 4.0 | "Powered by Global Fishing Watch"; non-commercial |
| NOAA CRW, NCRMP | US Gov | cite NOAA CRW / PIFSC ESD |
| Allen Coral Atlas | CC BY 4.0 | cite doi:10.5281/zenodo.3833242 |
| WDPA | non-commercial | cite UNEP-WCMC & IUCN |
| Coralscapes | Apache-2.0 | cite the paper |
| Ifremer clips | CC BY 4.0 | credit Ifremer |
| SAM 3 | SAM License | acknowledge SAM; include licence if redistributing |
| Muse Spark Open / Glimmer-Reef | Muse Model License | "Built with Muse Spark Open"; ship licence + Usage Policy |

`data/LICENSES.md` gets exactly this table, plus an empty "Local fixtures" section that Story 1.5 fills with one row per fixture (source URL + licence).

### §10 — Toolchain and versions (pin these, do not use `latest`)

Python **3.14** (`.python-version` contains `3.14`; `requires-python = ">=3.14,<3.15"`).
Python packages for this story: `ruff 0.17.2`, `pyright 1.1.414`, `import-linter` (latest, 2.15.x), `pytest 9.1.1`, `pytest-recording 0.14.0` + `vcrpy 9.2.0` (needed from Story 4.2 on, add now so 1.5 does not have to), `poethepoet` (latest).
`uv.lock` is committed. Runtime dependencies for later stories are added by those stories with `uv add`; this story adds none.

### §11 — Testing strategy (what this scaffold must make possible)

- `pytest` runs offline; `gpu` and `live` markers are registered and skipped by the gate.
- Definition of done: `uv run ruff check && uv run ruff format --check && uv run pyright && uv run lint-imports && uv run pytest` all pass.

## Tasks (tests first, then code)

1. Create `tests/test_smoke.py` (this is a test, write it before `pyproject.toml` exists; it will be collected once the config exists):
   1. `test_package_imports` — `import reefcase`; `reefcase.__version__ == "0.1.0"`.
   2. `test_layer_packages_importable` — parametrized over `api, bot, pipeline, agent, tools, llm, vision, ingest, store, core`, `importlib.import_module(f"reefcase.{name}")` succeeds (import-linter errors on a missing layer, so the contracts and the packages must agree).
   3. `test_pytest_markers_registered` — read `pyproject.toml` with `tomllib`, assert `[tool.pytest.ini_options].markers` contains one entry starting with `gpu:` and one starting with `live:`.
   4. `test_gate_task_runs_five_checks` — read `pyproject.toml`, find the `gate` task's `sequence`, flatten it to command strings, and assert it contains these five, in order: `ruff check`, `ruff format --check`, `pyright`, `lint-imports`, `pytest -m "not gpu and not live"`. Assert the pytest entry carries the `-m` expression.
   5. `test_import_linter_declares_architecture_layers` — assert `[tool.importlinter]` has `root_packages = ["reefcase"]` and a `layers` contract whose joined layer string contains `api`, `bot`, `pipeline`, `agent`, `tools`, `llm`, `vision`, `ingest`, `store`, `core` in the order of architecture §3, plus a `forbidden` contract for `reefcase.core`.
   6. One `@pytest.mark.gpu` test and one `@pytest.mark.live` test, each `assert True` with a comment that the gate deselects them (they exist so the markers are exercised, not so they test anything).
   Keep the file dependency-free apart from `pytest`, `tomllib` and `importlib`.
2. Write `pyproject.toml`: `[project]` (`name = "reefcase"`, `version = "0.1.0"`, `description`, `requires-python = ">=3.14,<3.15"`, no runtime deps), `[build-system]` = `uv_build` (so `uv sync` installs the package editable — import-linter and pyright both need an importable `reefcase`), `[dependency-groups] dev = [...]` with the pinned dev tools below, `[tool.poe.tasks]`, `[tool.ruff]`, `[tool.pyright]`, `[tool.pytest.ini_options]`, `[tool.importlinter]` + the two `[[tool.importlinter.contracts]]`.
3. Write `.python-version` containing `3.14`.
4. Write `.gitignore` — **it already exists and is correct** (secrets, python, web, runtime/scratch). Only add a line if something actually needs ignoring (e.g. `.coverage`, `htmlcov/`, `dist/`). Do not remove existing entries.
5. Write `.env.example` per §4.4 above: every variable, empty value, one comment line per group.
6. Write `src/reefcase/__init__.py` with `__version__ = "0.1.0"` and nothing else (docstring allowed).
7. Write empty `src/reefcase/<layer>/__init__.py` for the ten layers in §3 (`api bot pipeline agent tools llm vision ingest store core`). Empty packages now; later stories add modules. This is required by import-linter (a missing layer is a hard error) and is the only addition beyond the story's Files list.
8. Write `data/LICENSES.md` per §9.9, with a "Local fixtures" table header (empty) for Story 1.5.
9. Write `.github/workflows/ci.yml`: checkout, `astral-sh/setup-uv`, `uv python install 3.14`, `uv sync --locked`, `uv run poe gate`, on push and pull_request. Linux runner.
10. Run `uv lock` (commit `uv.lock`) then `uv run poe gate` until green. Then confirm `uv run lint-imports` fails if you temporarily add `from reefcase.store import db` to `src/reefcase/core/__init__.py` — remove it again afterwards (this proves the `core` contract bites; do not commit the probe).

## Required tool config (verified — paste, do not improvise)

```toml
[project]
name = "reefcase"
version = "0.1.0"
description = "Turn a diver's reef video into a cited investigation."
requires-python = ">=3.14,<3.15"
dependencies = []

[build-system]
requires = ["uv_build>=0.13,<0.14"]
build-backend = "uv_build"

[dependency-groups]
dev = [
  "import-linter>=2.15",
  "poethepoet>=0.49",
  "pyright>=1.1.414",
  "pytest>=9.1.1",
  "pytest-recording>=0.14.0",
  "ruff>=0.17.2",
]

[tool.poe.tasks.gate]
help = "Full Python gate: lint, format, types, layering, tests"
sequence = [
  { cmd = "ruff check ." },
  { cmd = "ruff format --check ." },
  { cmd = "pyright" },
  { cmd = "lint-imports" },
  { cmd = 'pytest -m "not gpu and not live"' },
]

[tool.ruff]
target-version = "py314"
line-length = 100
src = ["src", "tests"]
extend-exclude = ["web", "ml", "var", ".scratch"]

[tool.ruff.lint]
select = ["E", "F", "I", "UP", "B", "SIM", "RUF"]

[tool.ruff.lint.isort]
known-first-party = ["reefcase"]

[tool.pyright]
include = ["src", "tests"]
exclude = ["**/__pycache__", ".venv", "web", "ml", "var", ".scratch"]
pythonVersion = "3.14"
typeCheckingMode = "standard"
strict = ["src/reefcase"]
venvPath = "."
venv = ".venv"

[tool.pytest.ini_options]
minversion = "9.1"
testpaths = ["tests"]
addopts = "-ra"
pythonpath = ["src"]
markers = [
  "gpu: needs a GPU (skipped in the gate)",
  "live: hits a real external API or service (skipped in the gate)",
]

[tool.importlinter]
root_packages = ["reefcase"]

[[tool.importlinter.contracts]]
name = "reefcase layering"
type = "layers"
containers = ["reefcase"]
layers = [
  "api | bot",
  "pipeline",
  "agent",
  "tools | llm",
  "vision | ingest",
  "store",
  "core",
]

[[tool.importlinter.contracts]]
name = "core imports only stdlib and pydantic"
type = "forbidden"
source_modules = ["reefcase.core"]
forbidden_modules = [
  "reefcase.api", "reefcase.bot", "reefcase.pipeline", "reefcase.agent",
  "reefcase.tools", "reefcase.llm", "reefcase.vision", "reefcase.ingest",
  "reefcase.store",
]
```

Notes on the above:
- `addopts = "-ra"` deliberately omits `--strict-markers`: pytest 9 added the `strict_markers` ini option, and `gpu`/`live` are registered anyway. Registering the markers is what the AC asks for.
- `[tool.pyright] strict = ["src/reefcase"]` is the supported way to get strict on `src/reefcase` only; tests stay at `standard`.
- `pyright` resolves `reefcase` through the editable `uv_build` install (`path`-based `.pth`); `pythonpath` in pytest config is belt-and-braces.
- `ruff` selection lives under `[tool.ruff.lint]`; top-level `select` is deprecated.

## Lessons

No entries in any `ops/*/learnings.md` yet (all three are empty templates). Relevant standing rules from `AGENTS.md`:
- Python 3.14; `uv add <pkg>` for dependencies, always `uv run` for Python; `pip` never.
- Gate = `uv run poe gate`; every AC maps to a test, written first.
- `AGENTS.md`, `opencode.json`, `.opencode/**`, `docs/agents/**`, `scripts/**`, `planning/planning-artifacts/**` are frozen.
- Never read or print `.env`; secrets never enter a file.

## Library check (verified 2026-10-27 by the `researcher` subagent — reuse instead of re-asking)

**poethepoet 0.49** — a task may be `{ cmd = "..." }`; a multi-step task uses `sequence = [ { cmd = ... }, ... ]` or `{ ref = "task" }`. A bare array `gate = ["cmd1", "cmd2"]` is parsed as *task references*, not commands. `help` is valid on every task type. `cmd` is not run through a shell but parses quotes itself, so `cmd = 'pytest -m "not gpu and not live"'` passes the expression as one argument. First failure aborts the sequence (`ignore_fail` defaults false). Invoked as `uv run poe gate`.

**import-linter 2.15** — `[tool.importlinter]` takes `root_packages = ["reefcase"]` (plural is current); contracts are `[[tool.importlinter.contracts]]`. **A listed layer whose module does not exist is a hard error** (`ValueError: Missing layer ...`), unless the layer is parenthesised (`"(vision)"`). Hence the ten empty layer packages in Task 7. `containers` is an absolute package name and layer entries are relative tails; `|` means independent siblings. `type = "forbidden"` exists with `source_modules` / `forbidden_modules` / `as_packages` (default true) / `allow_indirect_imports` (default false). Do not enable `exhaustive` yet.

**pytest 9.1.1** — `[tool.pytest.ini_options]` is still supported (`[tool.pytest]` native TOML exists but the two tables cannot coexist). `markers = ["gpu: ...", "live: ..."]` linelist syntax unchanged; `-m "not gpu and not live"` unchanged. `--strict-markers` inside `addopts` was broken in 9.0.0 and fixed in 9.1.1; pytest 9 also offers `strict_markers = true`. `pythonpath` is builtin; with `src` layout + `build-system` + `uv sync` the package is installed editable, so it is not required.

**pyright 1.1.414** — per-path strictness in `[tool.pyright]` is the top-level `strict = ["src/reefcase"]` array (documented at 1.1.414); `executionEnvironments` does **not** accept `typeCheckingMode`. If `executionEnvironments` is ever added, `extraPaths = ["src"]` becomes mandatory. `pyrightconfig.json` overrides `[tool.pyright]` — do not add one. Editable install must be path-based `.pth` for pyright to resolve it (`uv_build` is).

**ruff 0.17.2** — selection under `[tool.ruff.lint]` (`select` / `ignore` / `per-file-ignores` at `[tool.ruff]` level is deprecated); `ruff format --check .` is current; `target-version = "py314"` is valid.

**uv 0.13.5** — `[dependency-groups] dev = [...]` (PEP 735) is the current way and `uv sync` installs it by default; CI should use `uv sync --locked` (`--frozen` silently accepts a stale lock). `.python-version` containing `3.14` is honoured as the default version request. Without `[build-system]` uv does not install the project at all.

## Done when

- `uv run poe gate` is green.
- `uv run lint-imports` shows both contracts (`reefcase layering`, `core imports only stdlib and pydantic`) as kept.
- `uv.lock` is committed; `.env.example` lists every §4.4 variable with an empty value.
- Report the files you changed and the last gate output.
