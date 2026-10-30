"""Citation validator for the investigator agent (architecture §5.5).

``validate(draft, known_ids)`` returns the offending statements.
The output validator on ``INVESTIGATOR_AGENT`` raises ``ModelRetry`` listing the offending
statements until retries are exhausted; on the last allowed attempt it drops uncited
findings, prefixes the verdict with ``"Partial:"``, and returns. Every remaining claim
is valid.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from reefcase.core.ids import FRAME, TOOL_RESULT
from reefcase.core.schemas import Cause, EvidenceRef, Finding, Hypothesis

if TYPE_CHECKING:
    from reefcase.agent.investigator import InvestigationDraft

__all__ = ["repair", "validate"]


def _cited(refs: list[EvidenceRef], known_ids: set[str]) -> bool:
    return all(ref.id in known_ids for ref in refs)


def validate(draft: InvestigationDraft, known_ids: set[str]) -> list[str]:
    """Return the statements that cite an ID not in ``known_ids``, in draft order.

    Core schemas already require at least one ref per finding and hypothesis.
    """
    offending = [f.statement for f in draft.findings if not _cited(f.evidence, known_ids)]
    offending += [
        h.rationale
        for h in draft.hypotheses
        if not _cited([*h.supporting, *h.contradicting], known_ids)
    ]
    return list(dict.fromkeys(offending))


def _fallback_ref(known_ids: set[str]) -> EvidenceRef:
    """A real ref for the placeholder claim when nothing in the draft survives."""
    frames = sorted(i for i in known_ids if i.startswith(f"{FRAME}_"))
    if frames:
        return EvidenceRef(kind="frame", id=frames[0])
    results = sorted(i for i in known_ids if i.startswith(f"{TOOL_RESULT}_"))
    if results:
        return EvidenceRef(kind="tool_result", id=results[0])
    raise ValueError("no frame or tool result to cite")


def repair(draft: InvestigationDraft, known_ids: set[str]) -> InvestigationDraft:
    """Drop uncited claims and prefix the verdict with ``Partial:``.

    A hypothesis survives if all its supporting refs are known; unknown contradicting
    refs are stripped. ``Investigation`` needs at least one finding and one hypothesis,
    so if none survive a placeholder citing a known frame (or tool result) takes its place.
    """
    findings = [f for f in draft.findings if _cited(f.evidence, known_ids)]
    hypotheses = [
        h.model_copy(update={"contradicting": [r for r in h.contradicting if r.id in known_ids]})
        for h in draft.hypotheses
        if _cited(h.supporting, known_ids)
    ]
    if not findings:
        findings = [
            Finding(
                statement="No finding could be tied to the evidence.",
                evidence=[_fallback_ref(known_ids)],
            )
        ]
    if not hypotheses:
        hypotheses = [
            Hypothesis(
                cause=Cause.UNKNOWN,
                confidence=0.0,
                supporting=[_fallback_ref(known_ids)],
                rationale="No hypothesis could be tied to the evidence.",
            )
        ]
    verdict = draft.verdict if draft.verdict.startswith("Partial:") else f"Partial: {draft.verdict}"
    return draft.model_copy(
        update={"findings": findings, "hypotheses": hypotheses, "verdict": verdict}
    )
