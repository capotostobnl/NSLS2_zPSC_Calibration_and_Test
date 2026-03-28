"""
Configure Reportlab related settings, and package to be passed to submodules
M. Capotosto 11/9/2025

Adapted from T. Caracappa's source.
"""
import os
from dataclasses import dataclass, field
from typing import List

from contextlib import contextmanager
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate,
    Table,
    Paragraph,
    PageBreak,
    Spacer,
)
from reportlab.lib.styles import getSampleStyleSheet, StyleSheet1, \
      ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.platypus import Flowable, KeepTogether

from Common.initialize_dut import DUT

# -----------------------------
# Define a small container for visual style dictionaries
# `slots=True` prevents Python from creating a dynamic __dict__ for each
# instance
# -----------------------------


@contextmanager
def channel_section(ctx: "ReportContext", chan: int, page_break=True):
    """
    Context manager for creating a grouped, distinct section for a
    specific channel.

    This helper manages the visual layout for a single channel's test results.
    It initializes a temporary list of report elements with a standardized
    header, yields this list to the caller to populate with content (plots,
    tables, etc.), and finally wraps the content in a `KeepTogether` block to
    ensure it stays on the same page if possible.

    Args:
        ctx: The main report context.
        chan: The channel number to display in the header.
        page_break: If True (default), inserts a hard PageBreak after the
            section is appended to the report.

    Yields:
        list: A mutable list where the caller should append report elements
              (paragraphs, tables, images) for this specific channel.
    """
    # local bucket for this channel
    bucket = []
    # heading
    title_style = ParagraphStyle('ChanHdr', parent=ctx.styles['Heading2'],
                                 alignment=TA_CENTER)
    bucket.append(Spacer(1, 0.15*inch))
    bucket.append(Paragraph(f"Channel {chan}", title_style))
    bucket.append(Spacer(1, 0.1*inch))
    # hand the list to callers
    yield bucket
    # close: wrap & append to doc
    ctx.elements.append(KeepTogether(bucket))
    if page_break:
        ctx.elements.append(PageBreak())


@dataclass(slots=True)
class ReportTheme:
    """
    Defines the standard color and style schemes for report visual elements.

    These dictionaries are intended to be passed directly as keyword arguments
    (e.g., `bbox=theme.props`) to Matplotlib text boxes or similar plotting
    functions to ensure consistent styling across all test plots.

    Attributes:
        props: Styling for neutral information or property
               boxes (default: wheat).
        good: Styling for 'PASS' or positive result indicators
              (default: palegreen).
        bad: Styling for 'FAIL' or error indicators (default: pink).
    """
    props = dict(boxstyle="round", facecolor="wheat", alpha=0.9)
    good = dict(boxstyle="round", facecolor="palegreen", alpha=0.9)
    bad = dict(boxstyle="round", facecolor="pink", alpha=0.9)


# -----------------------------
# Define a container for all report-wide shared resources
# -----------------------------


@dataclass
class ReportContext:
    """
    Maintains the state and configuration for generating a PDF report.

    This context object aggregates all necessary components—document templates,
    stylesheets, visual themes, and the accumulating list of content elements—
    required to build the final report using ReportLab.

    Attributes:
        doc: The ReportLab `SimpleDocTemplate` instance acting as the
             document chassis.
        theme: A `ReportTheme` instance containing standard color/box styles
               for plots and annotations.
        styles: A ReportLab `StyleSheet1` object containing paragraph styles
                (e.g., Heading1, Normal).
        elements: A mutable list of Flowable objects (Paragraphs, Tables,
                  Images) that make up the body of the report.
    """

    doc: SimpleDocTemplate

    # A nested theme object holding all the color/boxstyle dictionaries
    theme: ReportTheme = field(default_factory=ReportTheme)

    # ReportLab style sheet used by Paragraphs and other flowables
    styles: StyleSheet1 = field(default_factory=getSampleStyleSheet)

    # A list to accumulate report elements (Paragraphs, Tables, etc.)
    elements: List[Flowable] = field(default_factory=list)


def _cover_table(dut: DUT) -> Table:
    tdata = [
        ["PSC Functional Test Results", 0],
        ["Power Supply Controller Configuration", 0],
        ["Description", dut.model.description],
        ["Serial Number", dut.psc_sn],
        ["Number of Channels", dut.num_channels],
        ["Resolution", dut.resolution],
        ["Bandwidth", dut.bandwidth],
        ["Polarity", dut.polarity],
    ]

    row_h = [0.4*inch, 0.35*inch, *(0.27*inch for _ in range(6))]

    col_h = [3*inch, 3*inch]

    style = [
            ("SPAN", (0, 0), (1, 0)),
            ("SPAN", (0, 1), (1, 1)),
            ("ALIGN", (0, 0), (1, 1), "CENTER"),
            ("FONTSIZE", (0, 0), (1, 0), 16),
            ("FONTSIZE", (0, 1), (1, 1), 14),
            ("VALIGN", (0, 0), (1, 7), "MIDDLE"), 
            ("LINEABOVE", (0, 1), (1, 2), 2, colors.black),
            ("BACKGROUND", (0, 0), (1, 1), colors.lemonchiffon),
            ("BACKGROUND", (0, 2), (0, 7), colors.lightblue),
            ("FONTSIZE", (0, 1), (1, 7), 12),
            ("GRID", (0, 0), (-1, -1), 1, colors.black),
            ("BOX", (0, 0), (-1, -1), 2, colors.black),
        ]
    return Table(tdata, col_h, row_h, style=style)


def _make_filename(dut: DUT) -> str:
    return (f"{dut.num_channels}ch_{dut.resolution[:2]}"
            f"{dut.bandwidth[:1]}_SN{dut.psc_sn}_"
            f"{dut.dir_timestamp}.pdf")


def _create_context(pdf_path: str) -> ReportContext:
    doc = SimpleDocTemplate(pdf_path, pagesize=letter,
                            rightMargin=30, leftMargin=30,
                            topMargin=30, bottomMargin=18)
    styles = getSampleStyleSheet()
    theme = ReportTheme()
    return ReportContext(doc=doc, styles=styles, elements=[],
                         theme=theme)


def start_report(dut: DUT) -> tuple:
    """
    Initializes the test report context and sets up the document structure.

    This function determines the output file path based on the DUT attributes,
    initializes the PDF generation context, and creates the report cover page
    (including the title and DUT-specific summary table).

    Args:
        dut: The Device Under Test instance containing configuration details
             (e.g., serial number, report directory) needed for the filename
             and cover page.

    Returns:
        tuple: A tuple containing:
            - The initialized ReportContext object with cover page
              elements added.
            - The absolute file path to the target PDF file.
    """

    pdf_name = _make_filename(dut)
    pdf_path = os.path.join(dut.test_report_dir, pdf_name)

    ctx = _create_context(pdf_path)

    title_style = ParagraphStyle(
        'TitleCenter', parent=ctx.styles['Heading1'],
        alignment=TA_CENTER
    )
    ctx.elements.append(Paragraph("PSC Functional Test Report", title_style))
    ctx.elements.append(Spacer(1, 0.2*inch))

    ctx.elements.append(_cover_table(dut))

    return ctx, pdf_path


def finalize_report(ctx: ReportContext) -> str:
    """
    Generates and saves the final PDF report to disk.

    Triggers the build process for the ReportLab document, compiling all
    flowable elements (tables, plots, text) added to the context during
    the test execution into a single PDF file.

    Args:
        ctx: The report context containing the document template and the list
             of elements to render.

    Returns:
        str: The absolute filesystem path where the PDF was successfully saved.
    """
def finalize_report(ctx: ReportContext) -> str:
    """
    Generates and saves the final PDF report to disk.
    """
    # --- UPDATED DEBUG START ---
    def check_for_int(element_list, location_desc):
        for i, element in enumerate(element_list):
            if isinstance(element, int):
                print(f"CRITICAL ERROR: Found integer '{element}' at index {i} in {location_desc}!")
            elif isinstance(element, KeepTogether):
                # Recursively check inside KeepTogether buckets
                check_for_int(element._content, f"{location_desc} -> KeepTogether")

    check_for_int(ctx.elements, "ctx.elements")
    # --- DEBUG END ---

    pdf_path = ctx.doc.filename
    ctx.doc.build(ctx.elements)
    return pdf_path
