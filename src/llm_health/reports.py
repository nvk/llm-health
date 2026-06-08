from __future__ import annotations

import math
import re
import textwrap
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Literal

from llm_health import __version__
from llm_health.assessment_v2.bridge import (
    canonical_observations_csv,
    observations_from_v2_rows,
    rows_from_wiki_csv,
)
from llm_health.core.models import (
    ContextNote,
    DiagnosticGap,
    EnrolledProfile,
    Observation,
    QuickReviewCard,
    ResearchJob,
    SpecialistNote,
)
from llm_health.core.privacy import assert_safe_payload, validate_profile_alias
from llm_health.family import FamilyHistoryEvent, FamilyRelationship, HereditaryRiskNote
from llm_health.source_vault import SourceVaultRecord, load_records
from llm_health.stores import LocalHealthStore

ReportAudience = Literal["doctor", "family"]
ReportRange = Literal["all", "30d", "90d", "ytd", "18mo"]

FLAG_NORMAL = {"", "normal", "none", "ok", "negative", "within range"}
BADGE_BLUE = (58, 115, 181)
BADGE_AMBER = (165, 105, 20)
BADGE_RED = (174, 74, 62)
BADGE_GREEN = (65, 137, 83)
INK = (28, 35, 50)
MUTED = (103, 116, 136)
PAPER = (252, 249, 241)
PAPER_ALT = (246, 241, 230)
LINE = (214, 204, 188)
BAND_GREEN = (225, 241, 228)
BAND_AMBER = (255, 242, 213)


@dataclass(frozen=True)
class GeneratedReport:
    profile_id: str
    audience: ReportAudience
    path: Path
    observation_count: int
    active_flag_count: int
    pending_count: int
    generated_at: str


@dataclass(frozen=True)
class ReportBundle:
    profile: EnrolledProfile
    observations: list[Observation]
    context_notes: list[ContextNote]
    quick_cards: list[QuickReviewCard]
    diagnostic_gaps: list[DiagnosticGap]
    research_jobs: list[ResearchJob]
    specialist_notes: list[SpecialistNote]
    relationships: list[FamilyRelationship]
    family_history: list[FamilyHistoryEvent]
    hereditary_risks: list[HereditaryRiskNote]
    source_records: list[SourceVaultRecord]


@dataclass(frozen=True)
class FlaggedObservation:
    observation: Observation
    status: Literal["active", "resolved"]
    resolved_by: Observation | None = None


@dataclass(frozen=True)
class PendingObservation:
    observation: Observation
    status: Literal["active", "superseded"]
    superseded_by: Observation | None = None


class SimplePdf:
    """Small dependency-free PDF writer for private, local report exports."""

    width = 612.0
    height = 792.0
    margin = 46.0

    def __init__(self, title: str, *, accent: tuple[int, int, int] = BADGE_BLUE) -> None:
        self.title = _safe_pdf_text(title)
        self.accent = accent
        self.pages: list[list[str]] = []
        self.cursor = self.height - self.margin
        self.page_no = 0
        self.add_page()

    def add_page(self) -> None:
        self.pages.append([])
        self.page_no += 1
        self.cursor = self.height - self.margin
        if self.page_no > 1:
            self.text(self.margin, self.height - 30, self.title, size=8, color=MUTED)
            self.line(
                self.margin,
                self.height - 38,
                self.width - self.margin,
                self.height - 38,
                color=LINE,
            )
            self.cursor = self.height - 58

    @property
    def ops(self) -> list[str]:
        return self.pages[-1]

    @property
    def content_width(self) -> float:
        return self.width - self.margin * 2

    def ensure(self, amount: float) -> None:
        if self.cursor - amount < self.margin + 30:
            self.add_page()

    def rgb(self, color: tuple[int, int, int]) -> str:
        return " ".join(f"{item / 255:.3f}" for item in color)

    def rect(
        self,
        x: float,
        y: float,
        w: float,
        h: float,
        *,
        fill: tuple[int, int, int] | None = None,
        stroke: tuple[int, int, int] | None = None,
        line_width: float = 1,
    ) -> None:
        op = ["q"]
        if fill:
            op.append(f"{self.rgb(fill)} rg")
        if stroke:
            op.append(f"{self.rgb(stroke)} RG {line_width:.2f} w")
        op.append(f"{x:.2f} {y:.2f} {w:.2f} {h:.2f} re")
        if fill and stroke:
            op.append("B")
        elif fill:
            op.append("f")
        elif stroke:
            op.append("S")
        op.append("Q")
        self.ops.append("\n".join(op))

    def line(
        self,
        x1: float,
        y1: float,
        x2: float,
        y2: float,
        *,
        color: tuple[int, int, int] = LINE,
        line_width: float = 1,
    ) -> None:
        self.ops.append(
            f"q {self.rgb(color)} RG {line_width:.2f} w "
            f"{x1:.2f} {y1:.2f} m {x2:.2f} {y2:.2f} l S Q"
        )

    def text(
        self,
        x: float,
        y: float,
        text: object,
        *,
        size: float = 10,
        font: str = "F1",
        color: tuple[int, int, int] = INK,
    ) -> None:
        safe = _pdf_escape(_safe_pdf_text(text))
        self.ops.append(
            f"BT /{font} {size:.2f} Tf {self.rgb(color)} rg "
            f"1 0 0 1 {x:.2f} {y:.2f} Tm ({safe}) Tj ET"
        )

    def paragraph(
        self,
        text: object,
        *,
        x: float | None = None,
        width: float | None = None,
        size: float = 9.5,
        leading: float | None = None,
        color: tuple[int, int, int] = INK,
        font: str = "F1",
        after: float = 8,
        max_lines: int | None = None,
    ) -> float:
        text = _safe_pdf_text(text)
        x = self.margin if x is None else x
        width = self.content_width if width is None else width
        leading = leading or size * 1.32
        lines = _wrap_pdf_lines(text, width, size)
        if max_lines is not None and len(lines) > max_lines:
            lines = lines[:max_lines]
            lines[-1] = lines[-1].rstrip(" .") + "..."
        self.ensure(len(lines) * leading + after)
        for line in lines:
            self.text(x, self.cursor, line, size=size, font=font, color=color)
            self.cursor -= leading
        self.cursor -= after
        return len(lines) * leading + after

    def heading(self, text: object, *, level: int = 2) -> None:
        if level == 1:
            self.ensure(54)
            self.text(self.margin, self.cursor, text, size=26, font="F2", color=INK)
            self.cursor -= 30
            return
        self.ensure(30)
        self.text(self.margin, self.cursor, text, size=14, font="F2", color=INK)
        self.cursor -= 18
        self.line(self.margin, self.cursor, self.width - self.margin, self.cursor, color=LINE)
        self.cursor -= 12

    def badge(self, x: float, y: float, text: object, *, color: tuple[int, int, int]) -> float:
        label = _safe_pdf_text(text).upper()
        width = max(38, len(label) * 5.3 + 14)
        self.rect(x, y - 4, width, 16, fill=_tint(color, 0.86), stroke=_tint(color, 0.55))
        self.text(x + 7, y, label, size=7.5, font="F2", color=color)
        return width

    def metric_card(
        self,
        x: float,
        y: float,
        w: float,
        h: float,
        title: object,
        value: object,
        note: object,
        *,
        color: tuple[int, int, int] = BADGE_BLUE,
    ) -> None:
        self.rect(x, y, w, h, fill=PAPER, stroke=LINE)
        self.text(x + 12, y + h - 20, title, size=7.2, font="F2", color=MUTED)
        self.text(x + 12, y + h - 46, value, size=22, font="F2", color=color)
        self.text(x + 12, y + 14, note, size=8, color=MUTED)

    def table(
        self,
        headers: list[str],
        rows: list[list[object]],
        widths: list[float],
        *,
        size: float = 7.6,
        max_rows: int | None = None,
    ) -> None:
        rows = rows[:max_rows] if max_rows is not None else rows
        row_h = 18.0
        header_h = 20.0
        self.ensure(header_h + row_h * max(1, len(rows)) + 12)
        x0 = self.margin
        y = self.cursor - header_h
        self.rect(x0, y, sum(widths), header_h, fill=PAPER_ALT, stroke=LINE)
        x = x0
        for header, width in zip(headers, widths, strict=True):
            self.text(x + 5, y + 7, header, size=size, font="F2", color=MUTED)
            x += width
        self.cursor = y
        if not rows:
            self.cursor -= 22
            self.text(
                x0 + 5,
                self.cursor + 7,
                "None recorded in this filter.",
                size=size,
                color=MUTED,
            )
            self.cursor -= 8
            return
        for index, row in enumerate(rows):
            self.ensure(row_h + 4)
            y = self.cursor - row_h
            fill = (255, 253, 248) if index % 2 == 0 else PAPER
            self.rect(x0, y, sum(widths), row_h, fill=fill, stroke=LINE, line_width=0.5)
            x = x0
            for value, width in zip(row, widths, strict=True):
                clipped = _clip(_safe_pdf_text(value), max(4, int(width / (size * 0.54))))
                self.text(x + 5, y + 6.2, clipped, size=size, color=INK)
                x += width
            self.cursor = y
        self.cursor -= 12

    def bullet_list(self, items: list[object], *, max_items: int = 8, size: float = 9) -> None:
        if not items:
            self.paragraph("None recorded.", size=size, color=MUTED)
            return
        for item in items[:max_items]:
            self.paragraph(f"- {_safe_pdf_text(item)}", size=size, after=2)
        if len(items) > max_items:
            self.paragraph(f"- ... {len(items) - max_items} more", size=size, color=MUTED, after=2)
        self.cursor -= 4

    def sparkline(
        self,
        title: object,
        points: list[Observation],
        *,
        width: float | None = None,
        height: float = 56,
        color: tuple[int, int, int] = BADGE_BLUE,
    ) -> None:
        numeric = [point for point in points if point.value is not None]
        if not numeric:
            return
        width = self.content_width if width is None else width
        self.ensure(height + 42)
        x = self.margin
        y = self.cursor - height - 18
        self.text(x, y + height + 10, title, size=9.2, font="F2", color=INK)
        self.rect(x, y, width, height, fill=(255, 255, 252), stroke=LINE, line_width=0.75)
        values = [float(point.value) for point in numeric]
        ref = _parse_reference_range(
            [point.reference_range for point in numeric if point.reference_range]
        )
        lo = min(values)
        hi = max(values)
        if ref:
            if ref[0] is not None:
                lo = min(lo, ref[0])
            if ref[1] is not None:
                hi = max(hi, ref[1])
        if math.isclose(lo, hi):
            pad = abs(lo or 1) * 0.2
            lo -= pad
            hi += pad
        pad = (hi - lo) * 0.15
        lo -= pad
        hi += pad
        if ref and (ref[0] is not None or ref[1] is not None):
            band_lo = ref[0] if ref[0] is not None else lo
            band_hi = ref[1] if ref[1] is not None else hi
            band_y1 = y + _scale(band_lo, lo, hi) * height
            band_y2 = y + _scale(band_hi, lo, hi) * height
            self.rect(x, band_y1, width, max(2, band_y2 - band_y1), fill=BAND_GREEN)
        if len(numeric) == 1:
            px = x + width - 12
            py = y + _scale(values[0], lo, hi) * height
            self.rect(px - 2, py - 2, 4, 4, fill=color)
        else:
            coords: list[tuple[float, float]] = []
            for index, point in enumerate(numeric):
                px = x + 10 + index * ((width - 20) / (len(numeric) - 1))
                py = y + _scale(float(point.value), lo, hi) * height
                coords.append((px, py))
            path = [f"q {self.rgb(color)} RG 1.8 w"]
            path.append(f"{coords[0][0]:.2f} {coords[0][1]:.2f} m")
            for px, py in coords[1:]:
                path.append(f"{px:.2f} {py:.2f} l")
            path.append("S Q")
            self.ops.append("\n".join(path))
            for point, (px, py) in zip(numeric, coords, strict=True):
                dot_color = BADGE_RED if _is_flagged(point) else color
                self.rect(px - 2.2, py - 2.2, 4.4, 4.4, fill=dot_color)
        latest = numeric[-1]
        self.text(x + 6, y + 5, numeric[0].observed_on, size=7, color=MUTED)
        self.text(x + width - 58, y + 5, latest.observed_on, size=7, color=MUTED)
        self.text(
            x + width - 160,
            y + height + 10,
            f"latest {_format_observation_value(latest)}",
            size=7.5,
            color=MUTED,
        )
        self.cursor = y - 16

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        for index, page in enumerate(self.pages, start=1):
            page.append(
                f"BT /F1 7.5 Tf {self.rgb(MUTED)} rg 1 0 0 1 "
                f"{self.margin:.2f} 24.00 Tm "
                f"(llm-health {__version__} - own-risk local report - page {index}) Tj ET"
            )
        objects: list[bytes] = []
        font_helv = len(objects) + 1
        objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
        font_bold = len(objects) + 1
        objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold >>")
        font_oblique = len(objects) + 1
        objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Oblique >>")
        page_ids: list[int] = []
        for page in self.pages:
            stream = "\n".join(page).encode("latin-1", "replace")
            content_id = len(objects) + 2
            page_id = len(objects) + 1
            page_ids.append(page_id)
            resources = (
                f"<< /Font << /F1 {font_helv} 0 R /F2 {font_bold} 0 R "
                f"/F3 {font_oblique} 0 R >> >>"
            )
            page_payload = (
                f"<< /Type /Page /Parent 0 0 R /MediaBox [0 0 {self.width:.0f} "
                f"{self.height:.0f}] /Resources {resources} /Contents {content_id} 0 R >>"
            ).encode("latin-1")
            objects.append(page_payload)
            objects.append(
                b"<< /Length "
                + str(len(stream)).encode()
                + b" >>\nstream\n"
                + stream
                + b"\nendstream"
            )
        pages_id = len(objects) + 1
        kids = " ".join(f"{page_id} 0 R" for page_id in page_ids)
        objects.append(f"<< /Type /Pages /Kids [{kids}] /Count {len(page_ids)} >>".encode())
        catalog_id = len(objects) + 1
        objects.append(f"<< /Type /Catalog /Pages {pages_id} 0 R >>".encode())
        patched: list[bytes] = []
        for obj in objects:
            patched.append(obj.replace(b"/Parent 0 0 R", f"/Parent {pages_id} 0 R".encode()))
        out = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
        offsets = [0]
        for obj_id, payload in enumerate(patched, start=1):
            offsets.append(len(out))
            out.extend(f"{obj_id} 0 obj\n".encode())
            out.extend(payload)
            out.extend(b"\nendobj\n")
        xref = len(out)
        out.extend(f"xref\n0 {len(patched) + 1}\n".encode())
        out.extend(b"0000000000 65535 f \n")
        for offset in offsets[1:]:
            out.extend(f"{offset:010d} 00000 n \n".encode())
        out.extend(
            f"trailer\n<< /Size {len(patched) + 1} /Root {catalog_id} 0 R >>\n"
            f"startxref\n{xref}\n%%EOF\n".encode()
        )
        path.write_bytes(bytes(out))


def generate_profile_report(
    store: LocalHealthStore,
    profile_id: str,
    *,
    audience: ReportAudience,
    output: Path | None = None,
    wiki_root: Path | None = None,
    date_range: ReportRange = "all",
    max_observations: int = 50,
) -> GeneratedReport:
    profile = _profile_record(store, profile_id)
    bundle = _bundle_for_profile(store, profile, date_range=date_range, wiki_root=wiki_root)
    active_flags = active_flagged_observations(bundle.observations)
    pending = active_pending_observations(bundle.observations)
    generated_at = _now_stamp()
    output_path = output or _default_report_path(
        store.root, profile.profile_id, audience, generated_at
    )
    title = "Clinician Brief" if audience == "doctor" else "Family Health Summary"
    pdf = SimplePdf(f"{title} - {profile.profile_id}", accent=BADGE_BLUE)
    if audience == "doctor":
        _render_doctor_report(pdf, bundle, active_flags, pending, generated_at, max_observations)
    else:
        _render_family_report(pdf, bundle, active_flags, pending, generated_at, max_observations)
    pdf.save(output_path)
    return GeneratedReport(
        profile_id=profile.profile_id,
        audience=audience,
        path=output_path,
        observation_count=len(bundle.observations),
        active_flag_count=len(active_flags),
        pending_count=len(pending),
        generated_at=generated_at,
    )


def generate_profile_reports(
    store: LocalHealthStore,
    profile_id: str,
    *,
    audience: Literal["doctor", "family", "both"] = "both",
    output_dir: Path | None = None,
    wiki_root: Path | None = None,
    date_range: ReportRange = "all",
    max_observations: int = 50,
) -> list[GeneratedReport]:
    audiences: list[ReportAudience] = ["doctor", "family"] if audience == "both" else [audience]
    reports: list[GeneratedReport] = []
    for item in audiences:
        output = None
        if output_dir is not None:
            stamp = _now_stamp()
            output = output_dir / f"{validate_profile_alias(profile_id)}-{item}-{stamp}.pdf"
        reports.append(
            generate_profile_report(
                store,
                profile_id,
                audience=item,
                output=output,
                wiki_root=wiki_root,
                date_range=date_range,
                max_observations=max_observations,
            )
        )
    return reports


def _render_doctor_report(
    pdf: SimplePdf,
    bundle: ReportBundle,
    active_flags: list[FlaggedObservation],
    pending: list[PendingObservation],
    generated_at: str,
    max_observations: int,
) -> None:
    profile = bundle.profile
    _hero(
        pdf,
        "Clinician Brief",
        profile,
        generated_at,
        (
            "De-identified patient-managed summary. Verify against original "
            "sources before clinical use."
        ),
    )
    _metric_row(
        pdf,
        [
            (
                "source rows",
                len(bundle.observations),
                _date_span(obs.observed_on for obs in bundle.observations),
                BADGE_BLUE,
            ),
            (
                "active flags",
                len(active_flags),
                "older resolved flags are demoted",
                BADGE_RED if active_flags else BADGE_GREEN,
            ),
            (
                "pending",
                len(pending),
                "not charted as numeric results",
                BADGE_AMBER if pending else BADGE_GREEN,
            ),
            ("context", _context_count(bundle), "notes, consults, family history", BADGE_AMBER),
        ],
    )
    pdf.heading("Priority review")
    pdf.paragraph(
        "This report is a local, own-risk synthesis. It is not a diagnosis, order, "
        "prescription, or replacement for source review. Numbers below use source-provided "
        "reference ranges when present."
    )
    pdf.table(
        ["date", "marker", "result", "source range", "flag"],
        [
            [
                item.observation.observed_on,
                item.observation.marker,
                _format_observation_value(item.observation),
                item.observation.reference_range or "not provided",
                item.observation.flag or "flagged",
            ]
            for item in active_flags[:12]
        ],
        [58, 168, 92, 92, 80],
        max_rows=12,
    )
    if pending:
        pdf.heading("Pending / nonnumeric source rows")
        pdf.table(
            ["date", "marker", "category", "status"],
            [
                [
                    item.observation.observed_on,
                    item.observation.marker,
                    item.observation.category,
                    item.observation.flag or "pending/nonnumeric",
                ]
                for item in pending[:10]
            ],
            [62, 180, 140, 108],
            max_rows=10,
        )
    pdf.heading("Trend snapshot")
    for title, points in _selected_series(bundle.observations, active_flags, limit=8):
        pdf.sparkline(title, points, color=BADGE_BLUE)
    pdf.heading("Diagnostic gaps and candidate tests")
    gap_rows = []
    for gap in sorted(bundle.diagnostic_gaps, key=lambda item: item.priority, reverse=True)[:8]:
        candidates = ", ".join(candidate.name for candidate in gap.candidates[:3])
        gap_rows.append(
            [f"{gap.priority:.2f}", gap.title, gap.gap_type, candidates or "context first"]
        )
    pdf.table(["priority", "gap", "type", "candidate checks"], gap_rows, [52, 178, 90, 170])
    pdf.heading("Context, family, and specialist notes")
    pdf.bullet_list(_doctor_context_lines(bundle), max_items=14)
    pdf.heading("Recent source rows appendix")
    recent = sorted(bundle.observations, key=lambda item: item.observed_on, reverse=True)
    pdf.table(
        ["date", "domain", "marker", "result", "range", "flag"],
        [
            [
                obs.observed_on,
                obs.category,
                obs.marker,
                _format_observation_value(obs),
                obs.reference_range or "-",
                obs.flag or "-",
            ]
            for obs in recent[:max_observations]
        ],
        [56, 78, 138, 78, 76, 64],
        size=7.1,
        max_rows=max_observations,
    )
    _source_footer_section(pdf, bundle)


def _render_family_report(
    pdf: SimplePdf,
    bundle: ReportBundle,
    active_flags: list[FlaggedObservation],
    pending: list[PendingObservation],
    generated_at: str,
    max_observations: int,
) -> None:
    profile = bundle.profile
    _hero(
        pdf,
        "Family Health Summary",
        profile,
        generated_at,
        (
            "Plain-language, de-identified overview for discussion and memory. "
            "Not medical advice."
        ),
    )
    _metric_row(
        pdf,
        [
            (
                "tracked results",
                len(bundle.observations),
                _date_span(obs.observed_on for obs in bundle.observations),
                BADGE_BLUE,
            ),
            (
                "watch items",
                len(active_flags),
                "things to ask about",
                BADGE_RED if active_flags else BADGE_GREEN,
            ),
            (
                "open questions",
                len(bundle.diagnostic_gaps) + len(pending),
                "gaps and pending rows",
                BADGE_AMBER,
            ),
            ("history notes", _context_count(bundle), "family/context/research notes", BADGE_AMBER),
        ],
    )
    pdf.heading("What to know first")
    lines = _family_headlines(bundle, active_flags, pending)
    pdf.bullet_list(lines, max_items=8, size=10)
    pdf.heading("Things to keep an eye on")
    watch_rows = [
        [
            item.observation.observed_on,
            item.observation.marker,
            _format_observation_value(item.observation),
            item.observation.reference_range or "range not shown",
        ]
        for item in active_flags[:8]
    ]
    pdf.table(
        ["date", "item", "result", "expected/source range"],
        watch_rows,
        [62, 172, 95, 161],
    )
    pdf.heading("Questions to ask next")
    questions = []
    for gap in sorted(bundle.diagnostic_gaps, key=lambda item: item.priority, reverse=True):
        questions.extend(gap.context_questions[:2])
        questions.extend(
            f"Ask whether {candidate.name} would close the gap."
            for candidate in gap.candidates[:1]
        )
    if pending:
        questions.append("Which pending/non-numeric rows have later completed results?")
    pdf.bullet_list(questions or ["No specific follow-up questions generated yet."], max_items=10)
    pdf.heading("Family and personal context")
    pdf.bullet_list(_family_context_lines(bundle), max_items=12)
    pdf.heading("Recent results in plain English")
    recent = sorted(bundle.observations, key=lambda item: item.observed_on, reverse=True)
    pdf.table(
        ["date", "area", "item", "result", "range/flag"],
        [
            [
                obs.observed_on,
                obs.category,
                obs.marker,
                _format_observation_value(obs),
                obs.flag or obs.reference_range or "-",
            ]
            for obs in recent[: min(max_observations, 30)]
        ],
        [58, 94, 138, 86, 114],
        size=7.3,
        max_rows=min(max_observations, 30),
    )
    pdf.heading("Mini-trends")
    for title, points in _selected_series(bundle.observations, active_flags, limit=5):
        pdf.sparkline(title, points, color=BADGE_AMBER)
    _source_footer_section(pdf, bundle)


def _hero(
    pdf: SimplePdf,
    title: str,
    profile: EnrolledProfile,
    generated_at: str,
    subtitle: str,
) -> None:
    pdf.rect(
        pdf.margin - 12,
        pdf.cursor - 86,
        pdf.content_width + 24,
        98,
        fill=PAPER,
        stroke=LINE,
    )
    pdf.badge(pdf.margin, pdf.cursor - 1, profile.profile_id, color=BADGE_BLUE)
    pdf.text(pdf.margin, pdf.cursor - 35, title, size=26, font="F2", color=INK)
    pdf.text(pdf.margin, pdf.cursor - 54, subtitle, size=9, color=MUTED)
    details = [f"generated {generated_at[:10]}", f"birth {profile.birth_label}"]
    age = _approx_age(profile)
    if age is not None:
        details.append(f"approx age {age}")
    if profile.role:
        details.append(profile.role)
    pdf.text(pdf.margin, pdf.cursor - 72, "  |  ".join(details), size=8.5, color=MUTED)
    pdf.cursor -= 108


def _metric_row(
    pdf: SimplePdf,
    cards: list[tuple[str, object, object, tuple[int, int, int]]],
) -> None:
    w = (pdf.content_width - 24) / 4
    y = pdf.cursor - 72
    pdf.ensure(86)
    for index, (title, value, note, color) in enumerate(cards[:4]):
        pdf.metric_card(
            pdf.margin + index * (w + 8), y, w, 64, title, value, note, color=color
        )
    pdf.cursor = y - 18


def _source_footer_section(pdf: SimplePdf, bundle: ReportBundle) -> None:
    pdf.heading("Source and privacy notes")
    source_count = len(bundle.source_records)
    copied = sum(1 for record in bundle.source_records if record.copied)
    matched = sum(1 for record in bundle.source_records if record.match_status == "matched")
    pdf.bullet_list(
        [
            "Report uses alias-only local llm-health data, not raw source filenames or paths.",
            (
                f"Private source-vault catalog: {source_count} record(s), "
                f"{copied} copied blob(s), {matched} matched source id(s)."
            ),
            "Pending rows are listed as questions, not plotted as numeric evidence.",
            (
                "Resolved older flags may be omitted from watch items when later "
                "comparable rows look normal."
            ),
        ],
        max_items=6,
    )


def _doctor_context_lines(bundle: ReportBundle) -> list[str]:
    lines: list[str] = []
    for note in sorted(bundle.specialist_notes, key=lambda item: item.created_at, reverse=True)[:5]:
        lines.append(f"Specialist note ({note.specialist_id}): {note.title} - {note.summary}")
    for note in sorted(bundle.context_notes, key=lambda item: item.observed_on, reverse=True)[:5]:
        lines.append(f"Context: {note.subject} - {note.status}; {note.note}")
    for event in bundle.family_history[:5]:
        lines.append(f"Family/history: {event.profile_id} - {event.condition} ({event.status})")
    for risk in sorted(bundle.hereditary_risks, key=lambda item: item.priority, reverse=True)[:4]:
        lines.append(f"Hereditary/context note: {risk.title} - {risk.summary}")
    for job in sorted(bundle.research_jobs, key=lambda item: item.priority, reverse=True)[:3]:
        lines.append(f"Queued research: {job.topic} ({job.status})")
    return lines


def _family_context_lines(bundle: ReportBundle) -> list[str]:
    lines: list[str] = []
    for relationship in bundle.relationships[:8]:
        lines.append(
            f"Family link: {relationship.profile_id} -> {relationship.relative_id} "
            f"({relationship.relation}, {relationship.lineage})"
        )
    for event in bundle.family_history[:6]:
        lines.append(
            f"History clue: {event.condition} is marked {event.status} "
            f"for {event.profile_id}."
        )
    for risk in sorted(bundle.hereditary_risks, key=lambda item: item.priority, reverse=True)[:4]:
        lines.append(f"Context clue: {risk.title}. {risk.summary}")
    for note in sorted(bundle.context_notes, key=lambda item: item.observed_on, reverse=True)[:4]:
        lines.append(f"Self/context note: {note.subject} is {note.status}.")
    return lines or ["No family/history context has been recorded yet."]


def _family_headlines(
    bundle: ReportBundle,
    active_flags: list[FlaggedObservation],
    pending: list[PendingObservation],
) -> list[str]:
    lines = []
    if active_flags:
        lines.append(
            f"There are {len(active_flags)} active source-flagged result(s); use these as "
            "conversation starters, not standalone conclusions."
        )
    else:
        lines.append("No active source-flagged results are showing in the current local dataset.")
    if pending:
        lines.append(f"There are {len(pending)} pending/non-numeric source row(s) to reconcile.")
    if bundle.diagnostic_gaps:
        top = sorted(bundle.diagnostic_gaps, key=lambda item: item.priority, reverse=True)[0]
        lines.append(f"Top open gap: {top.title}.")
    if bundle.family_history or bundle.hereditary_risks:
        lines.append(
            "Family/history context is present and should be considered when "
            "interpreting trends."
        )
    if bundle.specialist_notes:
        lines.append(
            f"There are {len(bundle.specialist_notes)} local specialist/category "
            "notes to review."
        )
    lines.append("Bring the clinician brief when discussing details with a doctor.")
    return lines


def _bundle_for_profile(
    store: LocalHealthStore,
    profile: EnrolledProfile,
    *,
    date_range: ReportRange,
    wiki_root: Path | None,
) -> ReportBundle:
    observations = _filter_observations_by_range(
        _observations_for_report(store, profile.profile_id, wiki_root=wiki_root), date_range
    )
    source_records = [
        record
        for record in _source_records_if_present(store.root)
        if record.profile_id in {None, profile.profile_id}
    ]
    bundle = ReportBundle(
        profile=profile,
        observations=observations,
        context_notes=store.context_notes(profile.profile_id),
        quick_cards=store.quick_review_cards(profile.profile_id),
        diagnostic_gaps=store.diagnostic_gaps(profile.profile_id),
        research_jobs=store.research_jobs(profile.profile_id),
        specialist_notes=store.specialist_notes(profile.profile_id),
        relationships=store.family_relationships(profile.profile_id),
        family_history=_family_history_for_report(store, profile.profile_id),
        hereditary_risks=store.hereditary_risk_notes(profile.profile_id),
        source_records=source_records,
    )
    assert_safe_payload(_bundle_payload_for_privacy(bundle), field_name="report")
    return bundle


def _observations_for_report(
    store: LocalHealthStore, profile_id: str, *, wiki_root: Path | None
) -> list[Observation]:
    profile = validate_profile_alias(profile_id)
    merged = {
        observation.observation_id: observation for observation in store.observations(profile)
    }
    if wiki_root is not None and canonical_observations_csv(wiki_root).exists():
        rows = [
            row
            for row in rows_from_wiki_csv(wiki_root)
            if row.get("profile_id", "").strip().lower() == profile
        ]
        for observation in observations_from_v2_rows(rows):
            merged.setdefault(observation.observation_id, observation)
    return sorted(merged.values(), key=lambda item: (item.observed_on, item.marker))


def _source_records_if_present(root: Path) -> list[SourceVaultRecord]:
    manifest = root / "source-vault" / "manifest.jsonl"
    if not manifest.exists():
        return []
    return load_records(root)


def _bundle_payload_for_privacy(bundle: ReportBundle) -> dict[str, object]:
    return {
        "profile": bundle.profile.to_dict(),
        "observations": [observation.to_dict() for observation in bundle.observations],
        "context": [note.to_dict() for note in bundle.context_notes],
        "quick_cards": [card.to_dict() for card in bundle.quick_cards],
        "gaps": [gap.to_dict() for gap in bundle.diagnostic_gaps],
        "research": [job.to_dict() for job in bundle.research_jobs],
        "specialists": [note.to_dict() for note in bundle.specialist_notes],
        "relationships": [relationship.to_dict() for relationship in bundle.relationships],
        "family_history": [event.to_dict() for event in bundle.family_history],
        "hereditary": [risk.to_dict() for risk in bundle.hereditary_risks],
        "source_records": [record.to_dict() for record in bundle.source_records],
    }


def _family_history_for_report(
    store: LocalHealthStore, profile_id: str
) -> list[FamilyHistoryEvent]:
    profile = validate_profile_alias(profile_id)
    relationships = store.family_relationships(profile)
    relatives = {profile}
    for relationship in relationships:
        relatives.add(relationship.profile_id)
        relatives.add(relationship.relative_id)
    return [event for event in store.family_history_events() if event.profile_id in relatives]


def _profile_record(store: LocalHealthStore, profile_id: str) -> EnrolledProfile:
    profile = validate_profile_alias(profile_id)
    for item in store.enrolled_profiles(include_defaults=True):
        if item.profile_id == profile:
            return item
    raise ValueError(f"profile alias {profile!r} is not enrolled")


def _filter_observations_by_range(
    observations: list[Observation], date_range: ReportRange
) -> list[Observation]:
    if date_range == "all":
        return sorted(observations, key=lambda item: (item.observed_on, item.marker))
    today = date.today()
    if date_range == "ytd":
        cutoff = date(today.year, 1, 1)
    else:
        days = {"30d": 30, "90d": 90, "18mo": 548}[date_range]
        cutoff = today - timedelta(days=days)
    return sorted(
        [obs for obs in observations if _date_value(obs.observed_on) >= cutoff],
        key=lambda item: (item.observed_on, item.marker),
    )


def active_flagged_observations(observations: list[Observation]) -> list[FlaggedObservation]:
    statuses = flagged_observations(observations)
    return [item for item in statuses if item.status == "active"]


def flagged_observations(observations: list[Observation]) -> list[FlaggedObservation]:
    by_key = _group_by_comparable_key(observations)
    statuses: list[FlaggedObservation] = []
    for rows in by_key.values():
        ordered = sorted(rows, key=lambda item: item.observed_on)
        for index, obs in enumerate(ordered):
            if not _is_flagged(obs):
                continue
            follow_up = next(
                (
                    later
                    for later in ordered[index + 1 :]
                    if later.value is not None and not _is_flagged(later)
                ),
                None,
            )
            statuses.append(
                FlaggedObservation(obs, "resolved" if follow_up else "active", follow_up)
            )
    return sorted(statuses, key=lambda item: item.observation.observed_on, reverse=True)


def active_pending_observations(observations: list[Observation]) -> list[PendingObservation]:
    statuses = pending_observations(observations)
    return [item for item in statuses if item.status == "active"]


def pending_observations(observations: list[Observation]) -> list[PendingObservation]:
    by_key = _group_by_comparable_key(observations)
    statuses: list[PendingObservation] = []
    for rows in by_key.values():
        ordered = sorted(rows, key=lambda item: item.observed_on)
        for index, obs in enumerate(ordered):
            if not _is_pending_source_row(obs):
                continue
            follow_up = next(
                (later for later in ordered[index + 1 :] if later.value is not None),
                None,
            )
            statuses.append(
                PendingObservation(obs, "superseded" if follow_up else "active", follow_up)
            )
    return sorted(statuses, key=lambda item: item.observation.observed_on, reverse=True)


def _is_pending_source_row(observation: Observation) -> bool:
    if observation.value is not None:
        return False
    text = " ".join(
        str(item or "").lower()
        for item in [observation.flag, observation.note, observation.interpretation]
    )
    return any(token in text for token in ["pending", "pendiente", "processing", "in progress"])


def _group_by_comparable_key(observations: list[Observation]) -> dict[str, list[Observation]]:
    groups: dict[str, list[Observation]] = {}
    for obs in observations:
        key = "::".join(
            [
                _norm_key(obs.category),
                _norm_key(obs.marker),
                _norm_key(obs.unit or ""),
                _specimen_key(obs),
            ]
        )
        groups.setdefault(key, []).append(obs)
    return groups


def _selected_series(
    observations: list[Observation],
    active_flags: list[FlaggedObservation],
    *,
    limit: int,
) -> list[tuple[str, list[Observation]]]:
    groups = _group_by_comparable_key([obs for obs in observations if obs.value is not None])
    selected_keys = []
    key_for_obs = {id(obs): key for key, rows in groups.items() for obs in rows}
    for item in active_flags:
        key = key_for_obs.get(id(item.observation))
        if key and key not in selected_keys:
            selected_keys.append(key)
    ranked = sorted(
        groups.items(),
        key=lambda pair: (
            -len(pair[1]),
            -max(_date_value(row.observed_on).toordinal() for row in pair[1]),
            pair[0],
        ),
    )
    for key, _ in ranked:
        if key not in selected_keys:
            selected_keys.append(key)
        if len(selected_keys) >= limit:
            break
    output = []
    for key in selected_keys[:limit]:
        rows = sorted(groups[key], key=lambda item: item.observed_on)
        first = rows[-1]
        unit = f" ({first.unit})" if first.unit else ""
        output.append((f"{first.category} - {first.marker}{unit}", rows))
    return output


def _format_observation_value(observation: Observation) -> str:
    if observation.value is None:
        return "pending/non-numeric"
    value = f"{observation.value:g}"
    comparator = (observation.comparator or "").strip()
    if comparator in {"<", ">", "<=", ">="}:
        value = f"{comparator}{value}"
    if observation.unit:
        value = f"{value} {observation.unit}"
    return value


def _is_flagged(observation: Observation) -> bool:
    if observation.value is None or observation.is_pending:
        return False
    flag = (observation.flag or "").strip().lower()
    return flag not in FLAG_NORMAL


def _norm_key(value: str) -> str:
    return re.sub(r"\s+", " ", value.lower().strip())


def _specimen_key(obs: Observation) -> str:
    text = f"{obs.specimen or ''} {obs.marker}".lower()
    if "urine" in text:
        return "urine"
    if "hair" in text:
        return "hair"
    if "saliva" in text:
        return "saliva"
    if any(token in text for token in ["blood", "serum", "plasma"]):
        return "blood"
    return ""


def _date_value(value: str) -> date:
    try:
        return date.fromisoformat((value or "")[:10])
    except ValueError:
        return date.min


def _date_span(values) -> str:
    safe = sorted(value for value in values if value)
    if not safe:
        return "no dated rows"
    first = safe[0][:10]
    last = safe[-1][:10]
    return first if first == last else f"{first} to {last}"


def _context_count(bundle: ReportBundle) -> int:
    return (
        len(bundle.context_notes)
        + len(bundle.quick_cards)
        + len(bundle.diagnostic_gaps)
        + len(bundle.research_jobs)
        + len(bundle.specialist_notes)
        + len(bundle.relationships)
        + len(bundle.family_history)
        + len(bundle.hereditary_risks)
    )


def _default_report_path(root: Path, profile_id: str, audience: ReportAudience, stamp: str) -> Path:
    return root / "reports" / f"{profile_id}-{audience}-{stamp}.pdf"


def _now_stamp() -> str:
    return datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")


def _approx_age(profile: EnrolledProfile) -> int | None:
    if profile.birth_year is None:
        return None
    today = date.today()
    age = today.year - profile.birth_year
    if profile.birth_month and today.month < profile.birth_month:
        age -= 1
    return age


def _parse_reference_range(values: list[str]) -> tuple[float | None, float | None] | None:
    for raw in values:
        text = (raw or "").replace(",", ".")
        between = re.search(r"(-?\d+(?:\.\d+)?)\s*(?:-|to|–)\s*(-?\d+(?:\.\d+)?)", text)
        if between:
            return float(between.group(1)), float(between.group(2))
        upper = re.search(r"(?:<=|≤|<|up to|less than)\s*(-?\d+(?:\.\d+)?)", text, re.I)
        if upper:
            return None, float(upper.group(1))
        lower = re.search(r"(?:>=|≥|>|more than)\s*(-?\d+(?:\.\d+)?)", text, re.I)
        if lower:
            return float(lower.group(1)), None
    return None


def _scale(value: float, lo: float, hi: float) -> float:
    if math.isclose(lo, hi):
        return 0.5
    return max(0.02, min(0.98, (value - lo) / (hi - lo)))


def _tint(color: tuple[int, int, int], amount: float) -> tuple[int, int, int]:
    return tuple(int(channel + (255 - channel) * amount) for channel in color)


def _safe_pdf_text(value: object) -> str:
    text = str(value if value is not None else "")
    replacements = {
        "≤": "<=",
        "≥": ">=",
        "–": "-",
        "—": "-",
        "→": "->",
        "·": "-",
        "µ": "u",
        "μ": "u",
        "×": "x",
        "’": "'",
        "“": '"',
        "”": '"',
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    text = re.sub(r"\s+", " ", text).strip()
    return text.encode("latin-1", "replace").decode("latin-1")


def _pdf_escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _wrap_pdf_lines(text: str, width: float, size: float) -> list[str]:
    max_chars = max(12, int(width / (size * 0.52)))
    lines: list[str] = []
    for paragraph in _safe_pdf_text(text).split("\n"):
        lines.extend(textwrap.wrap(paragraph, width=max_chars) or [""])
    return lines


def _clip(text: str, max_chars: int) -> str:
    safe = _safe_pdf_text(text)
    if len(safe) <= max_chars:
        return safe
    return safe[: max(1, max_chars - 3)].rstrip() + "..."
