import { useState, type FormEvent, type ReactElement } from "react";
import { api } from "../api/client";
import type { components } from "../api/schema";
import type { FrameView, ToolCallView } from "../live/reducer";
import { EvidenceChip, toolNamesByResultId } from "./CaseFile";
import TextShimmer from "./arc/text-shimmer/text-shimmer";
import { BUTTON_PRIMARY, BUTTON_SECONDARY, SECTION_HEADING } from "./strobe";
import { evidenceLabel } from "../format";

type EvidenceRef = components["schemas"]["EvidenceRef"];
type Answer = components["schemas"]["Answer"];

export interface AskCaseProps {
  surveyId: string;
  onOpenEvidence: (evidence: EvidenceRef) => void;
  frames?: FrameView[];
  toolCalls?: ToolCallView[];
}

const SUGGESTIONS = [
  "Why not heat stress?",
  "What changed since 2019?",
  "What should the park do first?",
];

export function AskCase({
  surveyId,
  onOpenEvidence,
  frames = [],
  toolCalls = [],
}: AskCaseProps): ReactElement {
  const [isOpen, setIsOpen] = useState(false);
  const [question, setQuestion] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [answer, setAnswer] = useState<Answer | null>(null);

  const frameIds = frames.map((f) => f.id);
  const toolByResultId = toolNamesByResultId(toolCalls);
  const label = (ev: EvidenceRef) => evidenceLabel(ev, frameIds, toolByResultId);

  async function askQuestion(q: string) {
    const trimmed = q.trim();
    if (!trimmed || loading) return;

    setLoading(true);
    setError(null);

    try {
      const res = await api.POST("/api/surveys/{survey_id}/ask", {
        params: { path: { survey_id: surveyId } },
        body: { question: trimmed },
      });

      if (res.data) {
        setAnswer(res.data);
      } else {
        setError("Could not answer this question. Try asking again.");
      }
    } catch {
      setError("Could not answer this question. Try asking again.");
    } finally {
      setLoading(false);
    }
  }

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    void askQuestion(question);
  }

  return (
    <section aria-label="Ask this case" className="border-t border-hairline pt-6">
      <button
        type="button"
        onClick={() => setIsOpen((prev) => !prev)}
        aria-expanded={isOpen}
        className="group flex w-full items-center justify-between text-left"
      >
        <span className={`${SECTION_HEADING} transition-colors group-hover:text-deep`}>
          Ask this case
        </span>
        <span className="text-ui font-bold text-secondary group-hover:text-fg">
          {isOpen ? "−" : "+"}
        </span>
      </button>

      {isOpen ? (
        <div className="mt-4 space-y-4">
          <div className="flex flex-wrap gap-2">
            {SUGGESTIONS.map((suggestion) => (
              <button
                key={suggestion}
                type="button"
                onClick={() => {
                  setQuestion(suggestion);
                  void askQuestion(suggestion);
                }}
                disabled={loading}
                className={`${BUTTON_SECONDARY} px-3 py-1.5 text-label`}
              >
                {suggestion}
              </button>
            ))}
          </div>

          <form onSubmit={handleSubmit} className="flex gap-2">
            <input
              type="text"
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              placeholder="Ask a question about this dive…"
              maxLength={500}
              disabled={loading}
              className="flex-1 border border-hairline bg-surface px-3 py-2 text-ui text-fg placeholder:text-muted focus:border-deep focus:outline-none"
            />
            <button
              type="submit"
              disabled={loading || !question.trim()}
              className={BUTTON_PRIMARY}
            >
              Ask
            </button>
          </form>

          {loading ? (
            <div className="py-2 text-ui font-semibold text-fg">
              <TextShimmer>Reading the case…</TextShimmer>
            </div>
          ) : null}

          {error ? (
            <p role="alert" className="text-ui text-secondary">
              {error}
            </p>
          ) : null}

          {answer ? (
            <div className="space-y-3 border-l-[3px] border-deep bg-surface py-2 pl-3.5">
              <p className="text-body text-fg">{answer.answer}</p>
              {answer.citations && answer.citations.length > 0 ? (
                <div className="flex flex-wrap items-center gap-1.5">
                  <span className="text-label font-semibold text-secondary">Evidence:</span>
                  {answer.citations.map((ev) => (
                    <EvidenceChip
                      key={`ask-${ev.kind}-${ev.id}`}
                      evidence={ev}
                      label={label(ev)}
                      onOpen={onOpenEvidence}
                    />
                  ))}
                </div>
              ) : null}
            </div>
          ) : null}
        </div>
      ) : null}
    </section>
  );
}
