"""
Shared contract every section-agent follows: Profile -> Section.

Keeping this contract tiny is what makes the orchestrator pattern work —
`orchestrator.py` doesn't need to know anything about a given agent's
internals, only that it returns a Section it can hand to the PDF builder.
"""

from dataclasses import dataclass
from typing import List, Any

from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, Spacer, Table, TableStyle, PageBreak


@dataclass
class Section:
    title: str
    flowables: List[Any]  # reportlab flowables, already built by the agent


# --- Shared styles (one style sheet reused by every agent so the PDF is consistent) ---
_styles = getSampleStyleSheet()

STYLES = {
    "H1": ParagraphStyle("H1", parent=_styles["Heading1"], fontSize=20,
                          spaceAfter=14, textColor=colors.HexColor("#134E13")),
    "H2": ParagraphStyle("H2", parent=_styles["Heading2"], fontSize=14,
                          spaceBefore=10, spaceAfter=8, textColor=colors.HexColor("#1B5E20")),
    "H3": ParagraphStyle("H3", parent=_styles["Heading3"], fontSize=11.5,
                          spaceBefore=6, spaceAfter=4, textColor=colors.HexColor("#2E7D32")),
    "Body": ParagraphStyle("Body", parent=_styles["BodyText"], fontSize=10, leading=14),
    "Bullet": ParagraphStyle("Bullet", parent=_styles["BodyText"], fontSize=10,
                              leading=14, leftIndent=14, bulletIndent=4),
    "Small": ParagraphStyle("Small", parent=_styles["BodyText"], fontSize=8.5,
                             leading=11, textColor=colors.grey),
}

TABLE_HEADER_BG = colors.HexColor("#2E7D32")
TABLE_ALT_BG = colors.HexColor("#F1F8E9")


def styled_table(data, col_widths=None, header=True):
    t = Table(data, colWidths=col_widths, repeatRows=1 if header else 0)
    style = [
        ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
        ("FONTSIZE", (0, 0), (-1, -1), 8.5),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]
    if header:
        style += [
            ("BACKGROUND", (0, 0), (-1, 0), TABLE_HEADER_BG),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ]
        for row in range(1, len(data)):
            if row % 2 == 0:
                style.append(("BACKGROUND", (0, row), (-1, row), TABLE_ALT_BG))
    t.setStyle(TableStyle(style))
    return t


def bullets(items):
    return [Paragraph(f"&bull;&nbsp; {i}", STYLES["Bullet"]) for i in items]


def section_break():
    return PageBreak()


def spacer(h=0.4):
    return Spacer(1, h * cm)
