---
status: done
---

# Story 5.2: Investigator agent

As a park manager,
I want an agent that calls tools and concludes with ranked hypotheses,
So that I get a cause, not just a number (FR8, FR9).

- Owner: B (taken by guide: Claude Code) · Priority: P0 · Depends on: 4.2, 4.3, 4.4, 4.5, 5.1
- Files: `src/reefcase/agent/investigator.py`, `src/reefcase/agent/prompts/investigator.md`, `tests/agent/test_investigator.py`
- Also: `src/reefcase/pipeline/stages.py` + `tests/llm/test_assess.py` (assess stage skips a frame on a model API error, promised after 5.1)
- Done when: gate passes

## Acceptance Criteria

**Given** a `FunctionModel` scripted to call `heat_stress` then `vessel_activity` then return a draft
**When** `investigate` runs
**Then** `tool_called` and `tool_returned` events are emitted for each call in order, and an `Investigation` is returned

**Given** the system prompt
**When** read
**Then** it tells the model to consider every `Cause`, to cite frame IDs and `tr_…` IDs only, and never to name vessels

## Architecture contract

- §5.5: `investigate(survey, frames, segs, assessments, ctx, emit) -> Investigation`;
  `Agent(output_type=InvestigationDraft, tools=[...])`; every tool call emits
  `tool_called` / `tool_returned`; the prompt lives in `agent/prompts/investigator.md`.
- §5.2: tool-call output only; `NativeOutput` is forbidden.
- §4.3: `tool_called(call_id, tool, params)`, `tool_returned(call_id, tool_result_id, summary)`.
- §5.4: tools go through `registry.call`, so each result is persisted, cached and has a `tr_…` id.

## Decisions

- `investigate` takes the chat model as a keyword-only `model` (as `assess_frame` takes
  it first): the 5.4 stage builds the `agent` role, tests pass a `FunctionModel`.
- Tools are built from the registry with `Tool.from_schema` (the params model's JSON
  schema), `sequential=True`, so calls run one at a time: events stay in call order,
  `next_seq` never races, and GFW's one-report limit holds.
- `call_id` is pydantic-ai's `tool_call_id`. Invalid params raise `ModelRetry` before any
  event. A tool that fails with `ReefCaseError` returns `{"error": ...}` to the model and
  emits `tool_returned` with an empty `tool_result_id`, so one dead upstream (no GFW
  token, ERDDAP down) doesn't fail the survey.
- The tool return the model sees is the `ToolResult` minus `params`; the event summary is
  the compact JSON of `data`, cut to 200 characters.
- Citation validation and repair (§5.5 output validator) is story 5.3, not here.
- The user prompt gives each frame's id, time, cover and assessment, plus the survey's
  dive date so the model can pick the tool windows.

## Tasks

1. [x] Tests: draft fields, tool-call output, scripted heat_stress → vessel_activity run
   with ordered events, invalid params retry, tool failure, prompt content, assess-stage
   API error skip.
2. [x] `agent/prompts/investigator.md`.
3. [x] `agent/investigator.py`.
4. [x] Assess stage: skip a frame on `ModelAPIError`.
5. [x] `uv run poe gate`.
6. [x] Review against `.opencode/agents/reviewer.md`.

## Lessons

- pydantic-ai 2.62 returns a tool's `ModelRetry` to the model as a `ToolReturnPart`
  carrying the message, not a `RetryPromptPart`.
- Seeding `store.tool_results` with the canonical key makes `registry.call` a cache hit,
  so agent tests run real tools with no HTTP and no tool fakes.

## Library check

pydantic-ai 2.62.0: `Tool.from_schema(function, name, description, json_schema,
takes_ctx=True, sequential=True)`, `RunContext.tool_call_id`, `ModelRetry`,
`FunctionModel` with `ToolCallPart`; `ModelHTTPError` / `ModelConnectionError` subclass
`ModelAPIError`.
