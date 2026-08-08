"""
PDF assembly — takes the ordered list of Sections from the orchestrator and
builds the final PDF: cover page, auto-generated table of contents (real
page numbers, not hardcoded), section content, page numbers + running header
on every page.
"""

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib import colors
from reportlab.platypus import (
    BaseDocTemplate, PageTemplate, Frame, Paragraph, Spacer, PageBreak,
    NextPageTemplate,
)
from reportlab.platypus.tableofcontents import TableOfContents

from profile import UserProfile
from agents.base import Section, STYLES


class GuideDocTemplate(BaseDocTemplate):
    """Registers H1/H2 headings into the TOC automatically as it renders."""

    def afterFlowable(self, flowable):
        if hasattr(flowable, "style"):
            style_name = getattr(flowable.style, "name", "")
            text = getattr(flowable, "text", None)
            if text is None:
                return
            plain = text.replace("&mdash;", "-").replace("&amp;", "&").replace("&rarr;", "->")
            if style_name == "H1":
                self.notify("TOCEntry", (0, plain, self.page))
                self.canv.bookmarkPage(plain)
                self.canv.addOutlineEntry(plain, plain, level=0)


def _header_footer(canvas, doc):
    canvas.saveState()
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(colors.grey)
    canvas.drawString(2 * cm, 1.2 * cm, "Wedding Transformation Guide")
    canvas.drawRightString(A4[0] - 2 * cm, 1.2 * cm, f"Page {doc.page}")
    canvas.restoreState()


def build(sections: list, p: UserProfile, output_path: str):
    doc = GuideDocTemplate(output_path, pagesize=A4,
                            leftMargin=2 * cm, rightMargin=2 * cm,
                            topMargin=1.8 * cm, bottomMargin=1.8 * cm,
                            title="Wedding Transformation Guide",
                            author="Personal Fitness Agent")

    frame = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id="normal")
    doc.addPageTemplates([PageTemplate(id="body", frames=frame, onPage=_header_footer)])

    story = []

    # --- Cover page ---
    cover_title = ParagraphStyle("CoverTitle", parent=STYLES["H1"], fontSize=28,
                                  alignment=1, spaceAfter=18)
    cover_sub = ParagraphStyle("CoverSub", parent=STYLES["Body"], fontSize=13,
                                alignment=1, textColor=colors.grey)
    story += [
        Spacer(1, 6 * cm),
        Paragraph("Wedding Transformation Guide", cover_title),
        Paragraph(f"{p.plan_start_month} {p.plan_start_year} &rarr; {p.wedding_month} {p.wedding_year}", cover_sub),
        Spacer(1, 0.6 * cm),
        Paragraph(f"Personalized nutrition, training &amp; recovery plan for {p.name}", cover_sub),
        Spacer(1, 0.3 * cm),
        Paragraph(f"Pure vegetarian &middot; No eggs &middot; Goal: {p.goal.title()}", cover_sub),
        PageBreak(),
    ]

    # --- Table of contents ---
    toc = TableOfContents()
    toc.levelStyles = [
        ParagraphStyle("TOCH1", fontSize=12, leading=18, firstLineIndent=0,
                        spaceBefore=6, fontName="Helvetica-Bold"),
    ]
    story += [
        Paragraph("Table of Contents", STYLES["H1"]),
        toc,
        PageBreak(),
    ]

    # --- Sections ---
    for section in sections:
        story.extend(section.flowables)
        story.append(PageBreak())

    doc.multiBuild(story)
    return output_path
