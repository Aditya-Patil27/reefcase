# Story 1.3: Settings and model provider factory

Owner: Opus (lead-b) · Priority: P0 · Depends on: 1.2 · Status: in-progress

## Story (verbatim from epics.md)

As a developer,
I want providers configured only by environment variables,
So that we can switch between Baseten, Modal, Fireworks and Oxion without code changes (NFR3).

- Owner: Opus · Priority: P0 · Depends on: 1.2
- Files: `src/reefcase/core/config.py`, `src/reefcase/llm/providers.py`, `tests/llm/test_providers.py`
- Done when: gate passes

### Acceptance Criteria (verbatim)

**Given** `REEFCASE_LLM_AGENT_*` set
**When** `build_model("agent", settings)` is called
**Then** it returns an OpenAI-compatible pydantic-ai model pointing at that base URL and model name

**Given** no `REEFCASE_LLM_STUDENT_*` variables
**When** `build_model("student", settings)` is called
**Then** it returns `None`

## Architecture sections this story touches

### §4.4 — Configuration (`config.py`) — exact contract

> `Settings(BaseSettings)` loaded from env / `.env`, prefix `REEFCASE_`:

| Variable | Meaning |
|---|---|
| `REEFCASE_DATA_DIR` | default `var/` |
| `REEFCASE_SEGMENTER` | `fake` \| `sam3_local` \| `sam3_modal` \| `student` |
| `REEFCASE_SAM_MODEL_ID` | HF model id (default `facebook/sam3`, loaded through Transformers; see §9.6) |
| `REEFCASE_SAM_MODAL_URL` | URL of the Modal SAM endpoint |
| `REEFCASE_STUDENT_WEIGHTS` | path to ReefStudent weights |
| `REEFCASE_LLM_AGENT_{BASE_URL,API_KEY,MODEL}` | agent model (OpenAI-compatible) |
| `REEFCASE_LLM_TEACHER_{BASE_URL,API_KEY,MODEL}` | frame assessor teacher |
| `REEFCASE_LLM_STUDENT_{BASE_URL,API_KEY,MODEL}` | frame assessor student (Glimmer-Reef), optional |
| `REEFCASE_LLM_{AGENT,TEACHER}_REASONING_EFFORT` | `low` \| `medium` \| `high` \| `xhigh`; defaults `medium` (agent) and `low` (teacher), because Muse Spark Open defaults to `xhigh`, which would break NFR1 |
| `REEFCASE_GFW_TOKEN` | Global Fishing Watch API token |
| `REEFCASE_TELEGRAM_TOKEN` | bot token, optional |
| `REEFCASE_KEEP_FRAMES` | default 24 |
| `REEFCASE_MIN_FRAMES` | default 6 |

### §5.2 — Chat models (`llm/providers.py`) — exact contract

```python
def build_model(role: Literal["agent", "teacher", "student"], settings: Settings) -> pydantic_ai.models.Model
```

> Uses `OpenAIChatModel(model, provider=OpenAIProvider(base_url=..., api_key=...))` with the role's
> settings, and passes `reasoning_effort` through the model settings. Returns `None` for `student`
> when unconfigured.
>
> **Structured output rule:** Muse Spark Open on Baseten does not support JSON mode or structured
> outputs (§9.7). Every `Agent` therefore uses pydantic-ai's default tool-call output
> (`output_type=SomeModel`). `NativeOutput` is forbidden.

The contract's return annotation is `Model`; the prose adds "returns `None` for `student` when
unconfigured", so the implemented annotation is `OpenAIChatModel | None` (a `Model` subtype — more
precise, and it lets tests read `.client` / `.model_name` without casts).

### §3 — Layering (constraint on this story)

```
api, bot ──► pipeline ──► agent ──► tools, llm ──► store ──► core
                     └──► vision, ingest ─────────► store ──► core
```

- `core/config.py` sits at the bottom. It may import stdlib, `pydantic`, `pydantic_settings`, and
  other `reefcase.core` modules (`errors.py` for `ConfigError`) — never `reefcase.llm`.
- `llm/providers.py` imports `reefcase.core.config` (to the right of `llm`) — allowed.
- `src/reefcase/core/` is **frozen after Epic 1**. This story is the last Epic 1 story that adds a
  module there (`config.py`). Do not touch `ids.py`, `schemas.py`, `events.py`, `errors.py`.

### §9.7 — Muse Spark Open (context for the reasoning-effort default)

> **Spark Open capabilities:** … `reasoning_effort` defaults to `xhigh`. Recommended sampling:
> temperature 1.0, top_p 1.0.

That is why §4.4 defaults agent to `medium` and teacher to `low`: an unpinned `xhigh` breaks NFR1
(latency). Never send `xhigh` unless the env var says so.

### §10 — pinned toolchain

pydantic 2.14.1, pydantic-ai 2.61.0 (`OpenAIChatModel` + `OpenAIProvider`), pyright 1.1.414 strict on
`src/reefcase`. This story adds **`pydantic-settings` 2.16.1** (it owns `BaseSettings`, which §4.4
requires); add it with `uv add pydantic-settings`, never hand-edit `uv.lock`.

## Contract notes / decisions (do not deviate)

1. **`pydantic-settings` is required by §4.4.** pydantic 2 removed `BaseSettings`; it lives in
   `pydantic_settings`. Adding the dependency is additive and does not change §3–6: §4.4 explicitly
   says `Settings(BaseSettings)`, and import-linter's frozen contract only forbids `reefcase.*`
   modules from `reefcase.core`. No blocker needed — but say so in your final report.
2. **`reasoning_effort` → `openai_reasoning_effort`.** In pydantic-ai 2.61.0 there is no
   `ModelSettings["reasoning_effort"]` key; the OpenAI-specific model-settings field is
   `openai_reasoning_effort`, which is sent unchanged as the request's `reasoning_effort`. Implement
   the contract's intent with `OpenAIChatModelSettings(openai_reasoning_effort=...)` passed to
   `OpenAIChatModel(..., settings=...)`. Do **not** invent a plain-dict key; pyright rejects it and
   the runtime would silently drop it.
3. **Flat fields, no nested models/aliases.** `env_prefix="REEFCASE_"` maps field
   `llm_agent_base_url` to `REEFCASE_LLM_AGENT_BASE_URL` exactly. Do not use `env_nested_delimiter`
   (it would require `REEFCASE_LLM__AGENT__BASE_URL`, which is *not* the contract) and do not use
   `validation_alias` (it changes prefix behaviour). Field names mirror the table below.
4. **Secrets stay masked.** `api_key` and token fields are `SecretStr | None`; read them only via
   `.get_secret_value()` inside `build_model`. `ConfigError` messages name variables, never values.
5. **`.env.example` is copied by humans with empty values.** Set `env_ignore_empty=True` so
   `REEFCASE_LLM_AGENT_BASE_URL=` means "unset" and the default applies; without it the app fails to
   start from a copied `.env`. `extra="ignore"` too (default is `forbid`).
6. **No new env variables.** Every variable above already exists in `.env.example` (Story 1.1). If you
   think you need another one, stop and report — that is a blocker, not an edit.
7. **No network in tests.** Constructing `OpenAIChatModel`/`OpenAIProvider` does no I/O; never call
   `.run()`, `TestModel` or `FunctionModel` in this story's tests. Use `api_key="sk-test"` style
   values.

## Exact shape to implement

### `src/reefcase/core/config.py`

```python
LLMRole = Literal["agent", "teacher", "student"]
ReasoningEffort = Literal["low", "medium", "high", "xhigh"]
SegmenterName = Literal["fake", "sam3_local", "sam3_modal", "student"]

DEFAULT_DATA_DIR = Path("var")
DEFAULT_SAM_MODEL_ID = "facebook/sam3"
DEFAULT_AGENT_REASONING_EFFORT: ReasoningEffort = "medium"
DEFAULT_TEACHER_REASONING_EFFORT: ReasoningEffort = "low"
DEFAULT_KEEP_FRAMES = 24
DEFAULT_MIN_FRAMES = 6

@dataclass(frozen=True, slots=True)
class LLMRoleConfig:
    base_url: str
    api_key: str          # already unwrapped from SecretStr
    model: str
    reasoning_effort: ReasoningEffort | None   # None for "student" (§4.4 defines no student effort)

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="REEFCASE_",
        env_file=".env",
        env_file_encoding="utf-8",
        env_ignore_empty=True,
        extra="ignore",
        case_sensitive=False,
    )

    data_dir: Path = DEFAULT_DATA_DIR
    segmenter: SegmenterName = "fake"
    sam_model_id: str = DEFAULT_SAM_MODEL_ID
    sam_modal_url: str | None = None
    student_weights: Path | None = None

    llm_agent_base_url: str | None = None
    llm_agent_api_key: SecretStr | None = None
    llm_agent_model: str | None = None
    llm_teacher_base_url: str | None = None
    llm_teacher_api_key: SecretStr | None = None
    llm_teacher_model: str | None = None
    llm_student_base_url: str | None = None
    llm_student_api_key: SecretStr | None = None
    llm_student_model: str | None = None

    llm_agent_reasoning_effort: ReasoningEffort = DEFAULT_AGENT_REASONING_EFFORT
    llm_teacher_reasoning_effort: ReasoningEffort = DEFAULT_TEACHER_REASONING_EFFORT

    gfw_token: SecretStr | None = None
    telegram_token: SecretStr | None = None

    keep_frames: int = Field(default=DEFAULT_KEEP_FRAMES, ge=1)
    min_frames: int = Field(default=DEFAULT_MIN_FRAMES, ge=1)

    def llm_role(self, role: LLMRole) -> LLMRoleConfig | None:
        """Configured endpoint for `role`: None when the role has no variables at all.

        Raises ConfigError when the role is *partly* configured (some of base_url/api_key/model
        set), naming the missing REEFCASE_LLM_<ROLE>_* variables and never echoing values.
        """
```

Defaults are exactly the §4.4 ones (`var/`, `facebook/sam3`, 24, 6, medium/low). `segmenter`
defaults to `"fake"` so an unconfigured process is offline-safe (nothing in §4.4 contradicts it);
`fake` is a legal §4.4 value and a §5.1 backend name.

### `src/reefcase/llm/providers.py`

```python
from pydantic_ai.models.openai import OpenAIChatModel, OpenAIChatModelSettings
from pydantic_ai.providers.openai import OpenAIProvider

def build_model(role: LLMRole, settings: Settings) -> OpenAIChatModel | None:
    ...
```

- `cfg = settings.llm_role(role)`.
- `cfg is None`: return `None` for `"student"`; raise `reefcase.core.errors.ConfigError("REEFCASE_LLM_AGENT_* is not configured")`
  (resp. teacher) otherwise. AC 2 only covers student; silently returning `None` for agent/teacher
  would hide a production misconfiguration and break Epic 5 with a `None` model.
- Otherwise: `OpenAIProvider(base_url=cfg.base_url, api_key=cfg.api_key)`, and
  `OpenAIChatModel(cfg.model, provider=provider, settings=<settings or None>)` where
  `<settings>` is `OpenAIChatModelSettings(openai_reasoning_effort=cfg.reasoning_effort)` when the
  effort is not `None`, else `None` (so `model.settings is None` for student).
- One tiny private helper is fine (`_model_settings(cfg)`), no classes, no caching, no globals.
- `__all__ = ["build_model"]`.

## Tasks (tests first, then code)

1. `uv add pydantic-ai pydantic-settings` (pins `>=2.61.0` / `>=2.16.1`; commit `uv.lock`). Do this
   first so the test imports work.
2. `tests/core/test_config.py` (add this module — the story's Files list names one test file, but
   every AC and every §4.4 row must be tested; keep it in `tests/core/`, as Story 1.2 did with
   `test_ids.py`). Write **before** `config.py` exists.
   Local autouse fixture in the module (do **not** create `tests/conftest.py` — Story 1.5 owns it):
   ```python
   @pytest.fixture(autouse=True)
   def clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
       for key in [k for k in os.environ if k.startswith("REEFCASE_")]:
           monkeypatch.delenv(key, raising=False)
   ```
   and build settings with `Settings(_env_file=None)` so a developer's real `.env` is never read
   (AGENTS: never read `.env`; env vars are still read — clear them first as above).
   1. `test_defaults_match_architecture` — a `Settings(_env_file=None)` with no env has
      `data_dir == Path("var")`, `segmenter == "fake"`, `sam_model_id == "facebook/sam3"`,
      `keep_frames == 24`, `min_frames == 6`, `llm_agent_reasoning_effort == "medium"`,
      `llm_teacher_reasoning_effort == "low"`, and every `llm_*` endpoint field / token
      `is None`.
   2. `test_env_prefix_maps_flat_fields` — `monkeypatch.setenv("REEFCASE_LLM_AGENT_BASE_URL", …)` etc.;
      assert the matching `llm_agent_*` fields are populated (prefix + field name, no nesting).
   3. `test_every_4_4_variable_is_read` — parametrized table of all 20 variables in
      `.env.example` order, each with a sample value, asserting the field it feeds changes. This is
      the guard that a rename in `config.py` cannot drift from §4.4.
   4. `test_empty_env_value_means_unset` — `REEFCASE_LLM_AGENT_BASE_URL=""` and
      `REEFCASE_KEEP_FRAMES=""` leave the defaults intact (`env_ignore_empty=True`).
   5. `test_invalid_segmenter_and_effort_rejected` — `REEFCASE_SEGMENTER=nope` and
      `REEFCASE_LLM_TEACHER_REASONING_EFFORT=extreme` raise `pydantic.ValidationError`.
   6. `test_keep_frames_positive` — `REEFCASE_KEEP_FRAMES=0` raises.
   7. `test_secrets_are_masked` — with `REEFCASE_LLM_AGENT_API_KEY=sk-secret` and
      `REEFCASE_GFW_TOKEN=gfw-secret`: `isinstance(settings.llm_agent_api_key, SecretStr)`,
      `.get_secret_value() == "sk-secret"`, and neither `repr(settings)` nor
      `settings.model_dump_json()` contains `sk-secret`/`gfw-secret`.
   8. `test_llm_role_none_when_unconfigured` — `settings.llm_role("student") is None` and
      `settings.llm_role("agent") is None` for an empty environment (the *role accessor* is lenient;
      `build_model` is what raises).
   9. `test_llm_role_complete_config` — returns `LLMRoleConfig` with the plaintext key unwrapped,
      `reasoning_effort` from env, and `None` effort for `student`.
   10. `test_llm_role_partial_config_raises` — only `REEFCASE_LLM_AGENT_BASE_URL` +
      `REEFCASE_LLM_AGENT_MODEL` set raises `ConfigError` whose message names
      `REEFCASE_LLM_AGENT_API_KEY`, and does not contain the base URL's secret-ish value? (assert the
      message contains the *variable name* only).
3. `tests/llm/test_providers.py` — write before `providers.py` exists. Same autouse `clean_env`
   fixture, and `Settings(_env_file=None)`.
   1. `test_build_agent_model_uses_configured_endpoint` (AC 1) — set
      `REEFCASE_LLM_AGENT_BASE_URL=https://inference.baseten.co/v1`,
      `REEFCASE_LLM_AGENT_API_KEY=sk-test`,
      `REEFCASE_LLM_AGENT_MODEL=meta-models/muse-spark-open`; assert
      `isinstance(model, OpenAIChatModel)`, `model.model_name == "meta-models/muse-spark-open"`,
      `model.client.api_key == "sk-test"`, and
      `str(model.client.base_url).rstrip("/") == "https://inference.baseten.co/v1"`
      (OpenAI appends a trailing slash — compare with `rstrip("/")`).
   2. `test_agent_reasoning_effort_defaults_to_medium` — `model.settings == {"openai_reasoning_effort": "medium"}`.
   3. `test_agent_reasoning_effort_from_env` (AC 1 + §4.4) —
      `REEFCASE_LLM_AGENT_REASONING_EFFORT=xhigh` → `model.settings == {"openai_reasoning_effort": "xhigh"}`.
   4. `test_teacher_uses_teacher_variables_and_low_effort` —
      `model.settings == {"openai_reasoning_effort": "low"}`; the agent env vars are irrelevant to it
      (assert a distinct teacher base URL/model name come through).
   5. `test_student_is_none_when_unconfigured` (AC 2) — returns `None`; also with all three student
      vars deleted explicitly.
   6. `test_student_builds_when_configured` — set the three student vars; the model points at them and
      `model.settings is None` (no reasoning-effort contract for student).
   7. `test_agent_unconfigured_raises_config_error` — `ConfigError`, message mentions
      `REEFCASE_LLM_AGENT`; same for teacher.
   8. `test_two_roles_are_independent` — agent and teacher models built from one `Settings` have
      distinct `model_name`/`base_url`.
   9. `test_build_model_does_not_leak_secrets` — `"sk-test" not in repr(settings)` (the `providers`
      module must not stringify settings; model/client repr is out of scope).
   10. Optional but preferred: `test_build_model_is_offline` — assert no `httpx` client was used
       (e.g. no `.run()` called, model constructed only); keep it free of mocks of our own code.
4. `src/reefcase/core/config.py` — per the exact shape above. `__all__` lists
   `LLMRoleConfig`, `LLMRole`, `ReasoningEffort`, `SegmenterName`, `Settings` and the
   `DEFAULT_*` constants. Imports: `dataclasses`, `pathlib`, `typing`, `pydantic`,
   `pydantic_settings`, and `reefcase.core.errors.ConfigError`.
5. `src/reefcase/llm/providers.py` — per the exact shape above. Imports only
   `reefcase.core.config`, `reefcase.core.errors`, `pydantic_ai.models.openai`,
   `pydantic_ai.providers.openai`. No `pydantic_ai.Agent`, no prompts, no network.
6. Run `uv run poe gate` until green (ruff, ruff format, pyright strict, lint-imports, pytest).
   Note: `tests/core/test_config.py` and `tests/llm/test_providers.py` are **not** under pyright
   strict, but the gate type-checks them in `standard` mode — keep annotations explicit
   (`-> None` on every test, `Model`-typed locals as needed). If pyright rejects the private
   `_env_file=None` init kwarg (the pydantic plugin synthesises `__init__` from fields), pass it
   through a typed alias in the test module (a one-line `Settings(**{"_env_file": None})`-style helper
   or `# pyright: ignore[reportCallIssue]` on that line) — report which you needed.
7. Confirm layering still holds: `uv run lint-imports` reports both contracts kept.
8. Report the files you changed and the last gate output.

## Lessons (from `ops/*/learnings.md`, relevant to this story)

- [python] (1-1) RULE: When `ruff check .` fails only inside frozen vendored trees (`.claude/`,
  `scripts/`), widen `[tool.ruff] extend-exclude` — never narrow the gate command.
  (Already done in 1.1; do not touch it.)
- [test] (1-1) RULE: Every import-linter layer needs its package to exist; `llm/__init__.py` already
  does. Do not touch the contract in `pyproject.toml`.
- [python] (1-2) RULE: Add any new docs tree with ```python fences to `[tool.ruff] extend-exclude`
  rather than reformatting it. (`planning` is already excluded; this story writes a story file
  there, so no action.)
- [python] (1-2) RULE: On a pydantic model field, write `Field(default_factory=list[Foo])`, not
  `Field(default_factory=list)` — pyright strict infers `list[Unknown]`. (No default_factory fields
  here, but relevant if you add any.)
- Standing rules from `AGENTS.md`: Python 3.14, always `uv run`, dependencies via `uv add`,
  secrets only in `.env` (never read/print it), every AC has a test written first, never edit
  `planning/planning-artifacts/**` or `docs/agents/**`, scratch work in `.scratch/`.

## Library check (verified 2026-10-27 by the `researcher` subagent — reuse instead of re-asking)

**pydantic-settings 2.16.1** (added by this story; `uv add pydantic-settings` resolves `>=2.16.1`).
Requires `pydantic>=2.7` (fine with 2.14.1), `python-dotenv>=1.2.2`, ships Python 3.14 classifiers.
`BaseSettings` is **no longer in pydantic**; import it and `SettingsConfigDict` from
`pydantic_settings`. The idiom is unchanged:
```python
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="REEFCASE_", env_file=".env", env_ignore_empty=True, extra="ignore",
    )
    llm_agent_base_url: str | None = None   # reads REEFCASE_LLM_AGENT_BASE_URL
```
- `env_prefix` applies to **every** field automatically; matching is case-insensitive by default
  (`case_sensitive=False`), and on Windows env lookup is case-insensitive anyway.
- `extra` defaults to `"forbid"` — a copied `.env` with extra keys would raise, so set
  `extra="ignore"`.
- `env_ignore_empty=True` (default `False`) filters `v == ""` before validation, in both the env and
  dotenv sources, so `KEY=` in a copied `.env.example` behaves as unset and the field default applies.
  Whitespace (`KEY=   `) is *not* ignored. Required fields with no default still fail on empty.
- `_env_file` still exists: the default is `ENV_FILE_SENTINEL = Path("")`; passing `_env_file=None`
  disables dotenv loading. Process env vars are still read, so tests must also `delenv` the
  `REEFCASE_*` variables. Source order: init > env > dotenv > secrets > defaults.
- `Path` parses from the env string; a **relative** path resolves against the process CWD, not the
  `.env` directory. `Literal[...]` accepts an exact env string. `extra="ignore"` also means unrelated
  `REEFCASE_*` process vars are harmless (declared names are the only lookups).
- `SecretStr | None`: env strings go straight into `SecretStr`; `.get_secret_value()` is the only
  read path; `repr(settings)` / `str(...)` / `model_dump_json()` mask it. Do **not** write
  `SecretStr = ""` (defaults are not validated) — use `None`.

**pydantic-ai 2.61.0 — model construction.** Exact signatures:
```python
OpenAIChatModel(model_name, *, provider="openai", profile=None, settings=None)
OpenAIProvider(base_url=None, api_key=None, openai_client=None, http_client=None)
```
```python
from pydantic_ai.models.openai import OpenAIChatModel, OpenAIChatModelSettings
from pydantic_ai.providers.openai import OpenAIProvider

provider = OpenAIProvider(base_url="https://inference.baseten.co/v1", api_key="sk-test")
model = OpenAIChatModel(
    "meta-models/muse-spark-open",
    provider=provider,
    settings=OpenAIChatModelSettings(openai_reasoning_effort="medium"),
)
```
- `OpenAIChatModel` is current; `OpenAIModel` is the pre-2.0 name and has **no runtime alias** in
  2.61.0.
- Model-level `settings: ModelSettings | None` is stored verbatim and readable as `model.settings`;
  it merges with per-run `Agent(..., model_settings=...)` as `base | overrides` (per-run wins).
  Use `OpenAIChatModelSettings(...)`, not a bare dict literal (pyright rejects unknown TypedDict
  keys).
- **There is no `ModelSettings["reasoning_effort"]`.** The key is `openai_reasoning_effort`, typed
  `Optional[Literal["none","minimal","low","medium","high","xhigh","max"]]` from the OpenAI SDK
  (openai 3.39.0), and it is forwarded unchanged as the request's `reasoning_effort`. The unified
  alternative is `thinking: bool | Literal["minimal","low","medium","high","xhigh","max"]`. A bare
  `"reasoning_effort"` key is silently ignored at runtime — use the `openai_` field.
- Reading a model back in tests (no network): `model.model_name`, `model.base_url` (str),
  `str(model.client.base_url)` (an `httpx2.URL`; OpenAI always appends a trailing slash → compare
  with `rstrip("/")`), `model.client.api_key` (plain `str`), `model.settings`.
- `OpenAIProvider(base_url=..., api_key=None)` does not raise when a base URL is given (it installs
  the placeholder `"api-key-not-set"`); it raises `UserError` only when both are absent. Still pass
  `api_key="sk-test"` in tests for determinism.
- Return annotation: `Model` (`pydantic_ai.models.Model`) is `Generic[InterfaceClient]` with
  `InterfaceClient = TypeVar(..., default=Any)`, so bare `Model` passes pyright strict; prefer
  `OpenAIChatModel | None` here for precise attribute access in tests.
- Later stories: `from pydantic_ai.models.test import TestModel`,
  `from pydantic_ai.models.function import FunctionModel, AgentInfo`.
