# Story 1.2: Core schemas, IDs and events

Owner: Opus (lead-b) · Priority: P0 · Depends on: 1.1 · Status: in-progress

## Story (verbatim from epics.md)

As a developer,
I want every domain type and event defined once in `reefcase.core`,
So that API, pipeline, agent and web all share one contract.

- Owner: Opus · Priority: P0 · Depends on: 1.1
- Files: `src/reefcase/core/{ids,schemas,events,errors}.py`, `tests/core/test_schemas.py`, `tests/core/test_events.py`
- Done when: the 1.1 gate command passes

### Acceptance Criteria (verbatim)

**Given** the schemas in architecture §4.2
**When** each model is built from valid data and round-tripped through JSON
**Then** it is equal to the original

**Given** a `Finding` or `Hypothesis` with empty evidence
**When** it is validated
**Then** validation fails

**Given** a JSON event of any type in §4.3
**When** parsed with `EventAdapter`
**Then** the correct event class is returned

## Architecture sections this story touches

### §3 — Layering (constraint on this story)

```
api, bot ──► pipeline ──► agent ──► tools, llm ──► store ──► core
                     └──► vision, ingest ─────────► store ──► core
```

> A module may import only from layers to its right. **`core` imports only the standard library and pydantic.**

`reefcase.core` sits at the bottom: it imports stdlib + `pydantic` **only**. No third-party helper
library (in particular: no ULID package — see Task 2), and nothing from `reefcase.*`.

`src/reefcase/core/` is **frozen after this story**. Later stories may add modules only through a
blocker.

### §4.1 — Identifiers (`ids.py`) — exact contract

> All IDs are prefixed ULID strings: `site_…`, `srv_…` (survey), `frm_…` (frame), `seg_…`,
> `asm_…` (assessment), `tr_…` (tool result), `inv_…`. Helper: `new_id(prefix: str) -> str`.

```python
def new_id(prefix: str) -> str: ...
```

Prefixes (module constants, exactly these values): `site`, `srv`, `frm`, `seg`, `asm`, `tr`, `inv`.

ULID wire format (do not invent a format):
- 26 chars, uppercase Crockford base32, alphabet `0123456789ABCDEFGHJKMNPQRSTVWXYZ` (no `I`, `L`, `O`, `U`).
- First 10 chars = 48-bit big-endian millisecond timestamp, fixed width (so the first char is `0`–`7`).
- Last 16 chars = 80 bits of randomness (`os.urandom(10)`).
- Comparison is plain string comparison (`A` < `B` for IDs created in different milliseconds).

### §4.2 — Schemas (`schemas.py`) — copy verbatim

```python
class SegClass(StrEnum):
    LIVE_CORAL = "live_coral"; BLEACHED_CORAL = "bleached_coral"; ALGAE = "algae"
    RUBBLE = "rubble"; SAND = "sand"; OTHER = "other"
# class index in masks: OTHER=0, LIVE_CORAL=1, BLEACHED_CORAL=2, ALGAE=3, RUBBLE=4, SAND=5

class GeoPoint(BaseModel):   lat: float (−90..90); lon: float (−180..180)

class Site(BaseModel):       id; name; location: GeoPoint; mpa_id: str | None; created_at

class SurveyStatus(StrEnum): QUEUED, RUNNING, DONE, FAILED

class Survey(BaseModel):     id; site_id; dive_date: date; status; source: Literal["upload","bot","historical"]
                             video_path: str | None; cover: dict[SegClass, float] | None
                             failure_reason: str | None; created_at

class QualityScore(BaseModel): blur: float; color_cast: float; turbidity: float; passed: bool; reason: str | None

class Frame(BaseModel):      id; survey_id; t_sec: float; image_path: str; quality: QualityScore

class Segmentation(BaseModel): id; frame_id; backend: Literal["sam3","student","fake"]
                               mask_path: str; cover: dict[SegClass, float]; latency_ms: int

class FrameAssessment(BaseModel): id; frame_id; model: str
                                  bleaching_severity: int (0..4); morphology: list[str]
                                  damage: list[Literal["broken","overturned","anchor_scar","disease","none"]]
                                  notes: str (≤ 400 chars)

class EvidenceRef(BaseModel): kind: Literal["frame","tool_result"]; id: str

class ToolResult(BaseModel): id; tool: str; params: dict; data: dict; source_url: str; retrieved_at

class Finding(BaseModel):    statement: str; evidence: list[EvidenceRef] (min_length=1)

class Cause(StrEnum):        HEAT_STRESS, PHYSICAL_DAMAGE, FISHING_PRESSURE, DISEASE, UNKNOWN

class Hypothesis(BaseModel): cause: Cause; confidence: float (0..1)
                             supporting: list[EvidenceRef] (min 1); contradicting: list[EvidenceRef]
                             rationale: str

class Investigation(BaseModel): id; survey_id; findings: list[Finding] (min 1)
                                hypotheses: list[Hypothesis] (min 1); verdict: str
                                actions: list[str]; uncertain_frames: list[str]; model: str
```

Implementation notes (decided here, do not deviate):
- `StrEnum` values are **exactly** the lowercase strings above — they are JSON wire values.
  `SurveyStatus` values: `"queued"`, `"running"`, `"done"`, `"failed"`; `Cause` values:
  `"heat_stress"`, `"physical_damage"`, `"fishing_pressure"`, `"disease"`, `"unknown"`.
- `created_at`, `retrieved_at` are typed `AwareDatetime` (a pydantic refinement of `datetime`;
  no field is renamed). Timezone-aware is required so `model_dump_json()` → `model_validate_json()`
  is value-equal for every input, and so stored rows cannot mix naive and aware timestamps.
- `params: dict`, `data: dict` are free-form; annotate `dict[str, Any]` and **do not** set
  `extra="forbid"` on `ToolResult`.
- `| None` fields default to `None` (`mpa_id`, `video_path`, `cover` on `Survey`, `failure_reason`,
  `QualityScore.reason`). `contradicting` defaults to an empty list. Everything else is required.
- Numeric/string limits are `Field(...)` constraints: `lat` `ge=-90, le=90`; `lon` `ge=-180, le=180`;
  `bleaching_severity` `ge=0, le=4`; `notes` `max_length=400`; `confidence` `ge=0, le=1`;
  list minimums via `Field(min_length=1)` (v2 spelling — `min_items` no longer exists).
- Do **not** set `use_enum_values`; the enums must stay enums after validation (round-trip equality
  and `.name` in later stories). Do **not** set `populate_by_name`.

### §4.3 — Events (`events.py`) — copy verbatim

> A discriminated union on `type`. Every event has `survey_id`, `seq: int` (monotonic per survey,
> from 1) and `ts: datetime`.
>
> | type | payload |
> |---|---|
> | `survey_started` | `site_id` |
> | `frames_extracted` | `count` |
> | `frame_scored` | `frame_id`, `quality`, `thumb_url` |
> | `segmented` | `frame_id`, `backend`, `cover`, `mask_url` |
> | `assessed` | `assessment: FrameAssessment` |
> | `disagreement` | `frame_id`, `iou`, `chosen: "sam3"` |
> | `tool_called` | `call_id`, `tool`, `params` |
> | `tool_returned` | `call_id`, `tool_result_id`, `summary` |
> | `finding` | `finding: Finding` |
> | `report_ready` | `investigation_id` |
> | `survey_failed` | `reason` |
>
> `Event = Annotated[Union[...], Field(discriminator="type")]`, plus `EventAdapter = TypeAdapter(Event)`.

Class names (architecture names the wire values only; this is the fixed mapping):

| `type` value | class | fields beyond the base |
|---|---|---|
| `survey_started` | `SurveyStarted` | `site_id: str` |
| `frames_extracted` | `FramesExtracted` | `count: int` |
| `frame_scored` | `FrameScored` | `frame_id: str`, `quality: QualityScore`, `thumb_url: str` |
| `segmented` | `Segmented` | `frame_id: str`, `backend: Literal["sam3","student","fake"]`, `cover: dict[SegClass, float]`, `mask_url: str` |
| `assessed` | `Assessed` | `assessment: FrameAssessment` |
| `disagreement` | `Disagreement` | `frame_id: str`, `iou: float`, `chosen: Literal["sam3"]` |
| `tool_called` | `ToolCalled` | `call_id: str`, `tool: str`, `params: dict[str, Any]` |
| `tool_returned` | `ToolReturned` | `call_id: str`, `tool_result_id: str`, `summary: str` |
| `finding` | `FindingEvent` | `finding: Finding` (class is `FindingEvent` because `Finding` is the §4.2 schema name) |
| `report_ready` | `ReportReady` | `investigation_id: str` |
| `survey_failed` | `SurveyFailed` | `reason: str` |

Base class `_EventBase` (private) carries `survey_id: str`, `seq: int = Field(ge=1)`,
`ts: AwareDatetime`; each subclass adds `type: Literal["<value>"] = "<value>"`.

```python
Event: TypeAlias = Annotated[Union[SurveyStarted, FramesExtracted, ...], Field(discriminator="type")]
EventAdapter: TypeAdapter[Event] = TypeAdapter(Event)
```

`events.py` may import from `schemas.py` (`QualityScore`, `SegClass`, `FrameAssessment`, `Finding`).

### §4.4 — Configuration — not this story (1.3 owns `config.py`)

This story must **not** create `config.py`.

### §11 — Testing strategy

> | core | Schema round-trip and validation tests |

Gate: `uv run poe gate` (ruff, ruff format, pyright strict on `src/reefcase`, lint-imports, pytest
`-m "not gpu and not live"`).

## Tasks (tests first, then code)

1. `tests/core/test_schemas.py` — write first, before any `src/reefcase/core/schemas.py` exists:
   1. `test_seg_class_values_and_mask_order` — the six member values equal the §4.2 strings, and the
      mask class index is `OTHER=0, LIVE_CORAL=1, BLEACHED_CORAL=2, ALGAE=3, RUBBLE=4, SAND=5`
      (assert via an explicit `MASK_INDEX: dict[SegClass, int]` mapping exported from `schemas.py`;
      the mask legend lives in the contract, so the mapping must be in code, not only in a comment).
   2. `test_survey_status_values` / `test_cause_values` — exact lowercase wire values.
   3. `test_every_schema_round_trips` — a fixture table of one *valid* instance per model
      (`GeoPoint`, `Site`, `Survey`, `QualityScore`, `Frame`, `Segmentation`, `FrameAssessment`,
      `EvidenceRef`, `ToolResult`, `Finding`, `Hypothesis`, `Investigation`), parametrized:
      `type(m).model_validate_json(m.model_dump_json()) == m`, and the dumped JSON is `str`/`bytes`
      that parses with `json.loads`.
      Use a non-UTC `created_at` (`timezone(timedelta(hours=5, minutes=30))`) in the table so the
      round-trip proves offset handling, and an aware UTC `ts`/`retrieved_at` elsewhere.
   4. `test_cover_keys_round_trip_as_enum_members` — `Segmentation.model_dump_json()` writes
      `"live_coral"` as the key, and the re-parsed `cover` keys are `SegClass` members
      (`isinstance(key, SegClass)`, `.name == "LIVE_CORAL"`).
   5. `test_geopoint_rejects_out_of_range` — `lat=91` and `lon=-181` raise `ValidationError`.
   6. `test_frame_assessment_limits` — `bleaching_severity=5` and `notes="x"*401` raise
      `ValidationError`; `damage=["nonsense"]` raises `ValidationError`; `notes="x"*400` is accepted.
   7. `test_finding_requires_evidence` and `test_hypothesis_requires_supporting` — empty list raises
      `ValidationError`; check the error loc points at the field (`errors()[0]["loc"]` contains
      `"evidence"` / `"supporting"`).
   8. `test_hypothesis_confidence_bounds` — `1.01` and `-0.01` raise.
   9. `test_investigation_requires_findings_and_hypotheses` — empty list for either raises.
   10. `test_none_fields_default` — `Site(mpa_id=None)`, `Survey(video_path=None, cover=None,
       failure_reason=None)`, `QualityScore(reason=None)`, `Hypothesis(contradicting=[])` construct
       without passing those keywords.
   11. `test_model_json_schema_is_stable` — `Investigation.model_json_schema()` and
       `Site.model_json_schema()` are JSON-serialisable (`json.dumps`) and declare the field names
       from §4.2 (assert the `properties` keys of each model's `$defs` entry, sorted, equal the
       contract's field list). This is what Story 6.1 generates TS from.
2. `tests/core/test_ids.py` (add this file — the story's Files list names only two test modules, but
   every AC must map to a test and IDs are §4.1; keep it in `tests/core/`):
   1. `test_prefixes_are_the_contract` — the seven prefix constants equal
      `site, srv, frm, seg, asm, tr, inv`.
   2. `test_new_id_shape` — for each prefix: `f"{prefix}_"` prefix, total ULID tail length 26,
      every char in the Crockford alphabet, no `I`/`L`/`O`/`U`, first char in `"01234567"`.
   3. `test_new_id_unique` — 1000 `new_id("frm")` values are all distinct.
   4. `test_ulid_sorts_by_timestamp` — using the module's internal timestamp-taking helper
      (`_ulid_from_ms(ms)`; private, imported explicitly in the test), `_ulid_from_ms(1_700_000_000_000)
      < _ulid_from_ms(1_700_000_000_001)` and the ordering holds for three increasing milliseconds.
3. `tests/core/test_events.py` — write first:
   1. `test_every_event_type_round_trips` — a table of exactly 11 valid event instances (one per
      `type`), parametrized over `EventAdapter.dump_json(ev)` →
      `EventAdapter.validate_json(raw)`: returns an instance of **exactly** the same class and
      `== ev`.
   2. `test_event_type_tags_are_unique_and_complete` — the set of `type` literals in the union equals
      the 11 §4.3 tags; assert via `EventAdapter.json_schema()`: `discriminator.propertyName == "type"`
      and `set(discriminator.mapping) == the 11 tags` (pydantic silently drops unrepresentable
      members, so this must be asserted, not assumed).
   3. `test_unknown_event_type_rejected` — a JSON object with `"type": "not_an_event"` raises
      `pydantic.ValidationError` with `errors()[0]["type"] == "union_tag_invalid"`.
   4. `test_common_fields_required` — omitting `survey_id`, `seq` or `ts` raises `ValidationError`;
      `seq=0` raises; a naive `ts` (`datetime(2026, 10, 26)`) raises.
   5. `test_nested_schema_payloads` — `Assessed` carries a `FrameAssessment`,
      `FindingEvent` carries a `Finding`, `FrameScored` carries a `QualityScore`, and all three
      survive the round trip with nested types intact (`isinstance` checks).
   6. `test_event_json_schema_has_oneof_and_discriminator` — `json_schema()` has `oneOf` with 11
      entries and a `discriminator.mapping` whose values are `#/$defs/<Class>` refs (this shape is
      what becomes `/openapi.json` for Story 6.1).
4. `src/reefcase/core/errors.py` — architecture §4 names the file but does not specify its contents.
   Minimal hierarchy, additive only, never rename later:
   ```python
   class ReefCaseError(Exception): ...          # base for everything reefcase raises
   class ConfigError(ReefCaseError): ...        # bad/missing env configuration (1.3)
   class NotFoundError(ReefCaseError): ...      # unknown site/survey/frame/... id
   class StoreError(ReefCaseError): ...         # DuckDB/migration/blob failures (1.4)
   class ToolError(ReefCaseError): ...          # a context tool could not produce a result
   class ExternalServiceError(ToolError): ...   # upstream HTTP failure; carries status_code, url, retry_after
   class CitationError(ReefCaseError): ...      # unverifiable citation (5.3)
   ```
   `ExternalServiceError.__init__(self, message: str, *, status_code: int | None = None,
   url: str | None = None, retry_after: float | None = None)`. Add a test in `tests/core/test_errors.py`
   asserting the hierarchy (`issubclass` chain, `ExternalServiceError` is a `ToolError`), the message,
   and that the three attributes default to `None`. Keep `errors.py` import-free (stdlib only).
5. `src/reefcase/core/ids.py` — per §4.1 and the ULID format above. Stdlib only (`os`, `time`).
   Expose the seven constants as `SITE = "site"`, `SURVEY = "srv"`,
   `FRAME = "frm"`, `SEGMENTATION = "seg"`, `ASSESSMENT = "asm"`, `TOOL_RESULT = "tr"`,
   `INVESTIGATION = "inv"`, the helper `new_id(prefix: str) -> str`, and the private
   `_ulid_from_ms(ms: int) -> str`. `__all__` lists the public names.
6. `src/reefcase/core/schemas.py` — per §4.2, plus `MASK_INDEX: dict[SegClass, int]`. `__all__` lists
   every public name. Imports: `date`, `typing`, `enum`, `pydantic` only.
7. `src/reefcase/core/events.py` — per §4.3, plus `Event`, `EventAdapter`, and `__all__`. Import
   payload types from `reefcase.core.schemas`.
8. `src/reefcase/core/__init__.py` — re-export nothing heavy by default; keep it a docstring plus
   `__all__ = []`-style package marker (a module-level re-export of everything is fine only if it
   does not create an import cycle; simplest is to leave it as the package docstring). Do not
   create `config.py`.
9. Run `uv run poe gate` until green (ruff, format, pyright strict, import-linter, pytest).
10. Confirm the layering still bites: `uv run lint-imports` shows both contracts kept.

## Lessons (from `ops/*/learnings.md`, relevant to this story)

- [python] (1-1) RULE: When `ruff check .` fails only inside frozen vendored trees (`.claude/`,
  `scripts/`), widen `[tool.ruff] extend-exclude` — never narrow the gate command, and
  never edit the frozen files. WHY: 227 pre-existing errors there made `uv run poe gate` impossible
  to pass.
- [test] (1-1) RULE: Before writing any import-linter `layers` contract, create an empty
  `src/reefcase/<layer>/__init__.py` for every declared layer. WHY: import-linter 2.15 treats a
  declared layer whose module is missing as a hard error. (Already satisfied by 1.1 — do not touch
  the contract.)
- Standing rules from `AGENTS.md`: Python 3.14, always `uv run`, `uv add` for dependencies (this
  story needs **no** new dependency), every AC has a test written first, `core` is frozen after this
  story, never edit `planning/planning-artifacts/**` or `docs/agents/**`.

## Library check (verified 2026-10-27 by the `researcher` subagent — reuse instead of re-asking)

**pydantic 2.14.1 — discriminated union + `TypeAdapter`.** Current idiom, confirmed against the
2.14.1 docs/source:
```python
class _EventBase(BaseModel):
    survey_id: str
    seq: int
    ts: AwareDatetime

class SurveyStarted(_EventBase):
    type: Literal["survey_started"] = "survey_started"
    site_id: str

Event: TypeAlias = Annotated[Union[SurveyStarted, FramesExtracted, ...], Field(discriminator="type")]
EventAdapter: TypeAdapter[Event] = TypeAdapter(Event)

def parse_event(raw: str) -> Event:
    return EventAdapter.validate_json(raw)
```
- Every union member **must** carry the discriminator as a `Literal` field (or enum/RootModel of a
  Literal); a `str` field raises `PydanticUserError` `discriminator-needs-literal`; a missing field
  raises `discriminator-no-field`.
- `TypeAdapter[Event]` is the correct annotation, **no `# type: ignore`** needed with pyright 1.1.414
  (PEP 747 `TypeForm` support landed in 1.1.412/1.1.413; the pin is 1.1.414). If a version without
  TypeForm is ever used, fall back to `cast(TypeAdapter[Event], TypeAdapter(Event))`.
- Unknown tag → `pydantic.ValidationError` with `errors()[0]["type"] == "union_tag_invalid"`.
  Malformed JSON also surfaces as `ValidationError` (`json_invalid`), not `json.JSONDecodeError`.
  `validate_json` takes `data` positionally only.

**pydantic 2.14.1 — `Field` constraints.** `min_length`/`max_length` is the v2 spelling (`min_items`
was removed in v2 and is an unknown-argument error). Allowed on `str`, `bytes`, `list`, `tuple`,
`set`, `frozenset`, `deque`, `dict`, `Sequence`; **not** on `int`/`float`. `ge`/`le` work on numeric
and date/datetime types. So: `evidence: list[EvidenceRef] = Field(min_length=1)`,
`lat: float = Field(ge=-90, le=90)`, `bleaching_severity: int = Field(ge=0, le=4)`,
`notes: str = Field(max_length=400)`, `confidence: float = Field(ge=0, le=1)`.

**pydantic 2.14.1 — `AwareDatetime` and JSON round-trip.** `AwareDatetime` (from `pydantic`) rejects
naive datetimes and offset-less strings; this is what makes the round trip value-equal. Gotchas:
- UTC is serialised as `Z` (`"2032-01-01T01:01:00Z"`), not `+00:00`; non-UTC aware values keep their
  offset. Fractional seconds appear only when non-zero.
- The re-parsed `tzinfo` is a `datetime.timezone`, **not** the original `ZoneInfo`; `==` still holds
  (instant comparison). Do not assert `tzinfo` identity or `str(dt)` for non-UTC inputs.
- `date` dumps `"YYYY-MM-DD"` and re-parses equal. `date` also *accepts* Unix timestamps and
  midnight naive datetimes; add `Field(strict=True)` only if literal-date-string parsing is required
  (not required here).

**pydantic 2.14.1 — `StrEnum` as a dict key.** JSON mode serialises enum members by value, including
dict keys, so `{"cover": {"live_coral": 0.42}}`; validation accepts a member or its value, so string
keys rebuild `SegClass` members and `model_validate_json(model_dump_json()) == model` with the
**default** config. Gotcha: `use_enum_values=True` would put plain `str` in the field (and for
`StrEnum` the equality would still pass, hiding it) — leave it off. Compare round-trips via
`model_validate_json`, not a Python-mode dump.

**pydantic 2.14.1 — `model_json_schema()` for the union.** Emits `discriminator:
{propertyName: "type", mapping: {"survey_started": "#/$defs/SurveyStarted", ...}}` plus `oneOf` with
one `$ref` per member; single-value `Literal` fields become `{"const": ...}` on the member.
`TypeAdapter(Event).json_schema()` puts `oneOf` at the root (no `properties` wrapper). 2.14.1 emits
JSON Schema 2020-12 / OpenAPI 3.1. **A member that cannot be represented is silently dropped from
both `oneOf` and `mapping` (with a `skipped-choice` warning)** — so the test must assert all 11 tags
are present in `discriminator.mapping`.

**ULID — why stdlib, not `python-ulid`.** `python-ulid` 4.0.1 is current (`ULID()` ctor; `ULID.new()`
was removed in v3/v4; `str(ulid)` is 26 uppercase Crockford chars with monotonic randomness within a
ms). But architecture §3 freezes "`core` imports only the standard library and pydantic", so this
story implements the format directly, verified against `python-ulid`'s `ulid/base32.py`:
6-byte big-endian ms → 10 chars of 5 bits each (first char `0`–`7`), then 10 random bytes → 16 chars
(80 bits = 16×5 exactly). Fixed width MSB-first is what makes string order == time order. Within one
millisecond ordering is not strict; `Event.seq` is the contract's tiebreaker. `_ulid_from_ms(ms)` is
the injectable helper the ids test uses.

**`ConfigDict(extra="forbid")`.** Default is `ignore`; `forbid` raises `ValidationError`
(`extra_forbidden`) and adds `"additionalProperties": false` to the schema, but does not change
round-trip equality. Recommendation applied here: no `forbid` on `ToolResult.params/data`
(free-form, LLM/tool-fed); the leaf models stay at the default so additive schema evolution and
replayed event rows keep working.
