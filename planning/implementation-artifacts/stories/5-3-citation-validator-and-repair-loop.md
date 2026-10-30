---
status: done
---

# Story 5.3: Citation validator and repair loop

As a judge,
I want every claim backed by evidence,
So that the agent is verifiable (FR10).

- Owner: D · Priority: P0 · Depends on: 5.2
- Files: `src/reefcase/agent/citations.py`, `tests/agent/test_citations.py`
- Also wires into: `src/reefcase/agent/investigator.py` (register as output validator)
- Done when: gate passes

## Acceptance Criteria

**Given** a draft citing an unknown ID
**When** validated
**Then** `ModelRetry` is raised, listing the offending statements

**Given** the model fails to repair after 2 retries
**When** finalising
**Then** uncited findings are dropped, the verdict starts with "Partial:", and the remaining claims are all valid

## Architecture contract

- §5.5: An output validator runs `citations.validate(draft, known_ids)`. Unknown or missing
  evidence IDs raise `ModelRetry` with the list of offending claims. The maximum is 2 retries;
  after that, uncited claims are dropped and the verdict is prefixed with "Partial:".
- §4.2: `Finding.evidence: list[EvidenceRef] (min_length=1)` — each ref has `kind` ("frame" | "tool_result") and `id`.
  `Hypothesis.supporting: list[EvidenceRef] (min 1)`, `Hypothesis.contradicting: list[EvidenceRef]`.
- §11: Agent tests use `FunctionModel` scripts; tests cover citation repair and the partial-verdict fallback.

## Decisions

- `validate(draft, known_ids)` collects every `EvidenceRef.id` from findings and hypotheses,
  checks each against `known_ids`. Returns a list of offending statements for every claim that is
  not in `known_ids`.
- `known_ids` = the frame ids in this survey's frames list + the `tr_…` ids of tool results
  returned during this run (tracked from `tool_returned` events and `_agent_tool`).
- The output validator is registered on `INVESTIGATOR_AGENT` with `@INVESTIGATOR_AGENT.output_validator`.
  It receives `RunContext[_Deps]` and the `InvestigationDraft`.
- On retry exhaustion (`ctx.retry >= ctx.max_retries`), instead of raising ModelRetry (which
  would cause UnexpectedModelBehavior), the validator drops uncited findings, drops hypotheses
  with no valid supporting evidence, prefixes the verdict with "Partial:", and returns
  the cleaned draft. This prevents the exception from losing the draft entirely.
- The INVESTIGATOR_AGENT has `retries=2`, so `max_retries=2`, and `retry` goes 0, 1, 2.
  When `retry >= max_retries` (i.e. 2), this is the last chance — drop and return.

## Tasks

1. [x] Tests first: `test_citations.py` — (a) unknown id -> retry message names the statement,
   repaired draft accepted; (b) model never repairs -> Partial: verdict, only valid claims left,
   no exception.
2. [x] `agent/citations.py` — `validate` and `repair` functions.
3. [x] Wire into `investigator.py` — register output validator using the decorator.
4. [x] `uv run poe gate` & `pnpm -C web run gate`.
5. [x] Review against `.opencode/agents/reviewer.md`.

## Lessons

- [agent] (5-3) RULE: In pydantic-ai output validators, check `ctx.retry >= ctx.max_retries` before raising `ModelRetry` on invalid output to prevent `UnexpectedModelBehavior` on retry exhaustion. WHY: once max_retries is reached, `ModelRetry` terminates the run with an uncaught exception, losing the draft.
- [agent] (5-3) RULE: Use `TYPE_CHECKING` guards in citation modules to prevent circular import loops between `agent.citations` and `agent.investigator`.

## Library check

pydantic-ai 2.62.0: `@agent.output_validator` decorator; validator receives `RunContext[DepsT]`
and the output, can raise `ModelRetry` or return the (possibly modified) output.
`RunContext.retry: int` = retries so far, `RunContext.max_retries: int` = max allowed.
On exhaustion (retry > max_retries after the validator raises), pydantic-ai raises
`UnexpectedModelBehavior`. `FunctionModel` for tests.
