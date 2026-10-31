---
status: done
---

# Story 8.6: Ask this case

As a park manager or judge reading a case file,
I want to ask follow-up questions and get cited answers,
So that the page can stay short and the detail is there on demand (Meta tooling 25%, Best
Agentic).

- Owner: D · Priority: P1 · Depends on: 5.4, 6.5
- Files: `src/reefcase/agent/ask.py` (new), `src/reefcase/api/routes/surveys.py` (the
  `/ask` route), `tests/agent/test_ask.py`, `tests/api/test_ask.py`,
  `web/src/components/AskCase.tsx` (new) and its test, `web/src/routes/surveys.$id.tsx` (mount
  the panel only), `web/src/api/openapi.snapshot.json`, `web/src/api/schema.d.ts`
- Done when: `uv run poe gate` and `pnpm -C web run gate` are green, and on the live app
  "Why not heat stress?" on the HAW-41 case file returns a cited answer whose chips open the
  evidence drawer

## Acceptance Criteria

**Given** a survey with an investigation
**When** `POST /api/surveys/{survey_id}/ask` is called with `{"question": "Why not heat stress?"}`
**Then** it returns `200 {"answer": str, "citations": EvidenceRef[]}`, and every citation is a
frame of that survey or a tool result that survey's agent actually received

**Given** the answer draft cites an ID outside that set
**Then** the model is asked once to fix it; if it still does, the bad citations are dropped and
the answer is returned without them

**Given** an unknown survey → `404`. A survey without an investigation yet → `409`. A question
that is empty or over 500 characters (after stripping) → `422`

**Given** the survey page's case-file view
**When** the reader opens "Ask this case"
**Then** they see three suggested questions ("Why not heat stress?", "What changed since
2019?", "What should the park do first?") and a text box; the answer renders with the same
`EvidenceChip`s as the case file, and a chip opens the `EvidenceDrawer`

## Architecture contract

- `core/` is frozen. `AskRequest` / `Answer` live in `agent/ask.py` (the route imports them).
  Use `core.schemas.EvidenceRef` for citations.
- Layering: `api` → `agent` → `llm`/`store` (see `pyproject.toml`). `agent/ask.py` must not
  import `api`.
- Muse Spark Open has no JSON mode: keep pydantic-ai's default tool-call output, never
  `NativeOutput` (`llm/providers.py`).

## Decisions

- **Grounded only.** The context is the stored `Investigation`, the per-frame cover and
  assessment lines (reuse `investigator._frame_line`, or move it to a shared helper in `agent/`),
  and the tool results the agent received. **No tools are registered on this agent and nothing
  is fetched live.**
- **Which tool results:** the `tool_result_id`s from that survey's `tool_returned` events
  (`store.events.list(survey_id)`), loaded with `store.tool_results.get`. Don't add a store
  method; `ToolResultRepo` is keyed by params, so results are shared between surveys.
- **Allowed citation IDs** = that survey's frame IDs ∪ those tool-result IDs. Use the same
  `output_validator` + `ModelRetry` pattern as `INVESTIGATOR_AGENT` with `retries=1`; on the last
  attempt, drop the unknown refs instead of raising (as `citations.repair` does).
- **Model:** `build_model("agent", request.app.state.settings)`, run with
  `model_settings=OpenAIChatModelSettings(openai_reasoning_effort="low")` and
  `UsageLimits(request_limit=3)` so one question can't loop or blow the latency budget.
  Muse Spark Open's reasoning tokens count against `max_tokens`; leave at least 1500.
- **Prompt:** a short `agent/prompts/ask.md`: answer in 2–4 plain sentences for a park manager,
  only from the context, cite every claim, and say "the evidence doesn't show that" when it
  doesn't.
- **Stateless.** Each question is answered on its own. No chat history, no store writes.
- **OpenAPI:** add the path and the `AskRequest` / `Answer` schemas to
  `web/src/api/openapi.snapshot.json`, matching what `create_app().openapi()` emits for the
  route, then `pnpm -C web run gen:api`. Never hand-write `schema.d.ts`.
- **Web:** a collapsible panel under the case file (closed by default, so the page doesn't get
  longer). Suggested questions are buttons that send immediately. While waiting, show the
  existing `text-shimmer` with "Reading the case…"; on error, a one-line retry message.

## Tests (write first)

- `tests/agent/test_ask.py` with pydantic-ai `FunctionModel` (see `tests/agent/test_investigator.py`):
  valid citations pass through; a bad citation triggers exactly one retry; a second bad draft
  returns the answer with the bad ref dropped; the context has no tools.
- `tests/api/test_ask.py`: 200 with a fake model, 404, 409, 422 for `""` and 501 characters.
- Web: the panel renders the three suggestions; clicking one posts the question (MSW); chips in
  the answer call the drawer opener.

## Tasks

1. [x] `git merge main` in `met-wt/lead-d`.
2. [x] Tests above, red.
3. [x] `agent/ask.py` + `prompts/ask.md`, then the route.
4. [x] Snapshot + `gen:api`, `AskCase.tsx`, mount it in `surveys.$id.tsx`.
5. [x] `uv run poe gate` and `pnpm -C web run gate`.
6. [x] Self-review against `.opencode/agents/reviewer.md`, then
   `python scripts/integrate.py 8-6-ask-this-case --status review`. Add a handoff entry for the
   live check (deploy is the guide's step).
