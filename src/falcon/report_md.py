"""Deterministic Markdown rendering of a ProcessReport for FDE / Deployment Strategist readers."""

from __future__ import annotations

import time
from collections.abc import Iterable

from falcon.models import ActionStep, Opportunity, ProcessPhase, ProcessReport

_AUDIENCE_NOTE = (
    "> **Destinatari:** Forward Deployed Engineer (FDE) e Deployment Strategist. "
    "Il report ricostruisce il processo aziendale osservato in una sessione di shadowing "
    "consensuale. Ogni affermazione cita gli step `S###` e, tramite l'appendice, gli eventi "
    "`E-######` del trace: nulla va considerato verificato senza evidenza."
)

_OPPORTUNITY_TYPE_LABEL = {
    "automation": "Automazione",
    "integration": "Integrazione",
    "ai_assist": "Assistenza AI",
    "process_redesign": "Ridisegno processo",
    "data_quality": "Qualità dati",
}

_EFFORT_LABEL = {"low": "Basso", "medium": "Medio", "high": "Alto"}

_ONTOLOGY_KIND_LABEL = {
    "object_type": "Object type",
    "link_type": "Link type",
    "property": "Property",
}


def _cell(text: str) -> str:
    return text.replace("|", "\\|").replace("\n", " ").strip() or "—"


def _join(items: Iterable[str], sep: str = ", ") -> str:
    joined = sep.join(i for i in items if i)
    return joined or "—"


def _bullets(items: list[str]) -> list[str]:
    return [f"- {i}" for i in items] if items else ["- —"]


def _step_refs(step_ids: list[str], evidence: dict[str, list[str]]) -> str:
    if not step_ids:
        return "—"
    parts = []
    for sid in step_ids:
        events = evidence.get(sid, [])
        parts.append(f"{sid} ({', '.join(events)})" if events else sid)
    return ", ".join(parts)


def _step_number(step_id: str) -> int:
    digits = step_id.lstrip("S")
    return int(digits) if digits.isdigit() else -1


def _contiguous_ranges(step_ids: list[str]) -> list[str]:
    ordered = sorted(set(step_ids), key=_step_number)
    ranges: list[str] = []
    start = prev = ordered[0]
    for sid in ordered[1:]:
        if _step_number(sid) == _step_number(prev) + 1:
            prev = sid
            continue
        ranges.append(start if start == prev else f"{start}–{prev}")
        start = prev = sid
    ranges.append(start if start == prev else f"{start}–{prev}")
    return ranges


def _step_range(step_ids: list[str]) -> str:
    if not step_ids:
        return "—"
    ranges = _contiguous_ranges(step_ids)
    count = len(set(step_ids))
    return ranges[0] if count == 1 else f"{', '.join(ranges)} ({count} step)"


def _header(report: ProcessReport, steps: list[ActionStep], session_id: str) -> list[str]:
    meta = [
        f"**Sessione:** {session_id or '—'}",
        f"**Generato:** {time.strftime('%Y-%m-%d %H:%M')}",
        f"**Step analizzati:** {len(steps)}",
        f"**Fasi:** {len(report.phases)}",
        f"**Opportunità:** {len(report.opportunities)}",
    ]
    return [
        f"# Report di processo — {report.process.name or 'Processo osservato'}",
        "",
        " · ".join(meta),
        "",
        _AUDIENCE_NOTE,
        "",
    ]


def _executive_summary(report: ProcessReport) -> list[str]:
    p = report.process
    return [
        "## 1. Executive summary",
        "",
        p.summary or "—",
        "",
        f"**Obiettivo di business:** {p.business_goal or '—'}",
        "",
        f"**Perimetro osservato:** {p.scope or '—'}",
        "",
    ]


def _actors(report: ProcessReport) -> list[str]:
    lines = ["## 2. Attori e ruoli", "", "| Ruolo | Responsabilità |", "| --- | --- |"]
    lines += [f"| {_cell(a.role)} | {_cell(a.responsibilities)} |" for a in report.process.actors]
    if not report.process.actors:
        lines.append("| — | — |")
    return [*lines, ""]


def _systems(report: ProcessReport, evidence: dict[str, list[str]]) -> list[str]:
    lines = [
        "## 3. Sistemi e applicazioni coinvolti",
        "",
        "| Sistema | Ruolo nel processo | Evidenze |",
        "| --- | --- | --- |",
    ]
    lines += [
        f"| {_cell(s.name)} | {_cell(s.purpose)} | "
        f"{_cell(_step_refs(s.evidence_steps, evidence))} |"
        for s in report.process.systems
    ]
    if not report.process.systems:
        lines.append("| — | — | — |")
    return [*lines, ""]


def _phase(index: int, phase: ProcessPhase, evidence: dict[str, list[str]]) -> list[str]:
    lines = [
        f"### 4.{index} Fase {phase.phase_id} — {phase.name}",
        "",
        f"**Obiettivo:** {phase.objective or '—'}",
        "",
        f"**Attore:** {phase.actor_role or '—'} · **Sistemi:** {_join(phase.systems)}",
        "",
        f"**Input:** {_join(phase.inputs, '; ')}",
        "",
        f"**Output:** {_join(phase.outputs, '; ')}",
        "",
        "**Descrizione**",
        "",
        phase.narrative or "—",
        "",
        "**Azioni osservate**",
        "",
    ]
    if phase.actions:
        lines += [
            f"{i}. {a.description} — *{_step_refs(a.step_ids, evidence)}*"
            for i, a in enumerate(phase.actions, 1)
        ]
    else:
        lines.append("1. —")
    lines += ["", "**Punti decisionali**", "", *_bullets(phase.decision_points)]
    lines += ["", "**Entità dati coinvolte**", "", *_bullets(phase.data_entities)]
    lines += ["", "**Criticità nella fase**", "", *_bullets(phase.pain_points)]
    lines += ["", f"*Evidenze fase: {_step_range(phase.evidence_steps)}*", ""]
    return lines


def _phases(report: ProcessReport, evidence: dict[str, list[str]]) -> list[str]:
    lines = ["## 4. Processo end-to-end per fasi", ""]
    if not report.phases:
        return [*lines, "—", ""]
    lines += ["| Fase | Nome | Attore | Sistemi | Step |", "| --- | --- | --- | --- | --- |"]
    lines += [
        f"| {p.phase_id} | {_cell(p.name)} | {_cell(p.actor_role)} | "
        f"{_cell(_join(p.systems))} | {_step_range(p.evidence_steps)} |"
        for p in report.phases
    ]
    lines.append("")
    for i, p in enumerate(report.phases, 1):
        lines += _phase(i, p, evidence)
    return lines


def _pain_points(report: ProcessReport, evidence: dict[str, list[str]]) -> list[str]:
    lines = ["## 5. Criticità e inefficienze", ""]
    if not report.pain_points:
        return [*lines, "—", ""]
    for i, pp in enumerate(report.pain_points, 1):
        lines += [
            f"### 5.{i} {pp.title}",
            "",
            pp.description or "—",
            "",
            f"**Impatto:** {pp.impact or '—'}",
            "",
            f"*Evidenze: {_step_refs(pp.evidence_steps, evidence)}*",
            "",
        ]
    return lines


def _opportunity_row(i: int, o: Opportunity, evidence: dict[str, list[str]]) -> str:
    return (
        f"| {i} | {_cell(o.title)} | {_OPPORTUNITY_TYPE_LABEL.get(o.type, o.type)} | "
        f"{_EFFORT_LABEL.get(o.effort, o.effort)} | {o.priority} | "
        f"{_cell(_step_refs(o.evidence_steps, evidence))} |"
    )


def _opportunities(report: ProcessReport, evidence: dict[str, list[str]]) -> list[str]:
    lines = ["## 6. Opportunità di deployment", ""]
    if not report.opportunities:
        return [*lines, "—", ""]
    lines += [
        "| # | Opportunità | Tipo | Effort | Priorità | Evidenze |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    lines += [_opportunity_row(i, o, evidence) for i, o in enumerate(report.opportunities, 1)]
    lines.append("")
    for i, o in enumerate(report.opportunities, 1):
        lines += [
            f"### 6.{i} {o.title}",
            "",
            o.description or "—",
            "",
            f"**Ipotesi di valore:** {o.value_hypothesis or '—'}",
            "",
        ]
    return lines


def _ontology(report: ProcessReport, evidence: dict[str, list[str]]) -> list[str]:
    lines = [
        "## 7. Proposte di ontologia",
        "",
        "| Tipo | Nome | Descrizione | Evidenze |",
        "| --- | --- | --- | --- |",
    ]
    lines += [
        f"| {_ONTOLOGY_KIND_LABEL.get(o.kind, o.kind)} | {_cell(o.name)} | "
        f"{_cell(o.description)} | {_cell(_step_refs(o.evidence, evidence))} |"
        for o in report.ontology_proposals
    ]
    if not report.ontology_proposals:
        lines.append("| — | — | — | — |")
    return [*lines, ""]


def _competency_questions(report: ProcessReport, evidence: dict[str, list[str]]) -> list[str]:
    lines = ["## 8. Competency questions", ""]
    if not report.competency_questions:
        return [*lines, "—", ""]
    for i, q in enumerate(report.competency_questions, 1):
        lines += [
            f"{i}. **{q.question}**",
            f"   - Razionale: {q.rationale or '—'}",
            f"   - Evidenze: {_step_refs(q.evidence_steps, evidence)}",
        ]
    return [*lines, ""]


def _open_questions(report: ProcessReport) -> list[str]:
    lines = [
        "## 9. Domande aperte per gli stakeholder",
        "",
        "| Domanda | Destinatario | Perché |",
        "| --- | --- | --- |",
    ]
    lines += [
        f"| {_cell(q.question)} | {_cell(q.audience)} | {_cell(q.why)} |"
        for q in report.open_questions
    ]
    if not report.open_questions:
        lines.append("| — | — | — |")
    return [*lines, ""]


def _assumptions(report: ProcessReport) -> list[str]:
    return ["## 10. Assunzioni e limiti dell'analisi", "", *_bullets(report.assumptions), ""]


def _appendix(steps: list[ActionStep]) -> list[str]:
    lines = [
        "## Appendice A — Tracciabilità step → eventi",
        "",
        "| Step | App | Azione osservata | Eventi |",
        "| --- | --- | --- | --- |",
    ]
    lines += [
        f"| {s.step_id} | {_cell(s.app)} | {_cell(s.description)} | "
        f"{_cell(', '.join(s.evidence_events))} |"
        for s in steps
    ]
    return [*lines, ""]


def render_report(report: ProcessReport, steps: list[ActionStep], session_id: str = "") -> str:
    evidence = {s.step_id: s.evidence_events for s in steps}
    sections = (
        _header(report, steps, session_id),
        _executive_summary(report),
        _actors(report),
        _systems(report, evidence),
        _phases(report, evidence),
        _pain_points(report, evidence),
        _opportunities(report, evidence),
        _ontology(report, evidence),
        _competency_questions(report, evidence),
        _open_questions(report),
        _assumptions(report),
        _appendix(steps),
    )
    return "\n".join(line for section in sections for line in section)
