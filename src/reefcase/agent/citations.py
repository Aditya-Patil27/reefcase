"""Citation validator for the investigator agent (architecture §5.5).

``validate(draft, known_ids)`` returns the offending statements.
The output validator on ``INVESTIGATOR_AGENT`` raises ``ModelRetry`` listing the offending
statements until retries are exhausted; on the last allowed attempt it drops uncited
findings, prefixes the verdict with ``"Partial:"``, and returns. Every remaining claim
is valid.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from reefcase.core.schemas import Cause, EvidenceRef, Finding, Hypothesis

if TYPE_CHECKING:
    from reefcase.agent.investigator import InvestigationDraft

__all__ = ["repair", "validate"]


def validate(draft: InvestigationDraft, known_ids: set[str]) -> list[str]:
    """Return the list of statements with unknown or missing evidence citations."""
    offending: list[str] = []
    for finding in draft.findings:
        bad = not finding.evidence or any(ref.id not in known_ids for ref in finding.evidence)
        if bad and finding.statement not in offending:
            offending.append(finding.statement)
    for hyp in draft.hypotheses:
        bad = (
            not hyp.supporting
            or any(ref.id not in known_ids for ref in hyp.supporting)
            or any(ref.id not in known_ids for ref in hyp.contradicting)
        )
        if bad and hyp.rationale not in offending:
            offending.append(hyp.rationale)
    return offending


def repair(draft: InvestigationDraft, known_ids: set[str]) -> InvestigationDraft:
    """Drop uncited claims and prefix the verdict with ``Partial:``.

    - Findings: keep only those whose every evidence ref is known.
    - Hypotheses: keep only those whose every supporting ref is known; strip unknown
      contradicting refs.
    - If no findings or hypotheses survive, provide a valid fallback citing a known frame so
      the schema's ``min_length=1`` constraints hold.
    """
    valid_findings: list[Finding] = [
        f for f in draft.findings if f.evidence and all(r.id in known_ids for r in f.evidence)
    ]
    valid_hypotheses: list[Hypothesis] = []
    for hyp in draft.hypotheses:
        if hyp.supporting and all(r.id in known_ids for r in hyp.supporting):
            clean_contra = [r for r in hyp.contradicting if r.id in known_ids]
            valid_hypotheses.append(hyp.model_copy(update={"contradicting": clean_contra}))

    fallback_frame = next(
        (i for i in sorted(known_ids) if i.startswith("frm_")),
        next(iter(sorted(known_ids)), ""),
    )

    if not valid_findings:
        evidence = [EvidenceRef(kind="frame", id=fallback_frame)] if fallback_frame else []
        valid_findings = [
            Finding(
                statement="Insufficient evidence to make specific findings.",
                evidence=evidence if evidence else [EvidenceRef(kind="frame", id="frm_fallback")],
            )
        ]

    if not valid_hypotheses:
        evidence = [EvidenceRef(kind="frame", id=fallback_frame)] if fallback_frame else []
        valid_hypotheses = [
            Hypothesis(
                cause=Cause.UNKNOWN,
                confidence=0.0,
                supporting=evidence if evidence else [EvidenceRef(kind="frame", id="frm_fallback")],
                contradicting=[],
                rationale="All original hypotheses lacked valid citations.",
            )
        ]

    verdict = draft.verdict
    if not verdict.startswith("Partial:"):
        verdict = f"Partial: {verdict}"

    return draft.model_copy(
        update={
            "findings": valid_findings,
            "hypotheses": valid_hypotheses,
            "verdict": verdict,
        }
    )
