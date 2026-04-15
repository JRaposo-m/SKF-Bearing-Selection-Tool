"""
report_generator.py
-------------------
Generates a professional PDF report from the SKF bearing selection results.

Usage (called from main.py after GA run):
    from report_generator import generate_report
    generate_report(report_data)

report_data dict keys
---------------------
    # Bearing
    bearing           : DeepGrooveBallBearing dataclass
    # Operating inputs
    Fr                : float   radial load [N]
    Fa                : float   axial load [N]
    n                 : float   user input speed [rpm]
    T_op              : float   operating temperature [°C]
    L10h_req          : float   required life [h]
    contamination     : str
    lubrication       : str
    lubricant         : str
    H                 : float   oil level [mm]
    # GA results
    vg                : int     ISO VG grade selected
    n_opt             : float   optimised speed [rpm]
    ga_history        : list    merit per generation
    ga_pen_history    : list    penalty per generation
    ga_lambda_history : list    lambda per generation
    # Computed results
    v_act             : float   actual viscosity [mm²/s]
    v1                : float   rated viscosity [mm²/s]
    kappa             : float   viscosity ratio
    L_skf             : float   modified life [h]
    L10h              : float   basic life [h]
    M_rr              : float   rolling moment [N·mm]
    M_sl              : float   sliding moment [N·mm]
    M_drag            : float   drag moment [N·mm]
    M_seal            : float   seal moment [N·mm]  (None if open)
    M_tot             : float   total moment [N·mm]
    # Candidate table
    candidates        : list    of DeepGrooveBallBearing (all that passed life filter)
"""

from __future__ import annotations

import os
import sys
import io
import datetime
import math

import matplotlib
matplotlib.use("Agg")   # non-interactive backend — no display needed
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import numpy as np

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    Image, HRFlowable, PageBreak, KeepTogether
)
from reportlab.platypus.flowables import Flowable

# ---------------------------------------------------------------------------
# Constants — colours matching SKF brand palette
# ---------------------------------------------------------------------------
_SKF_BLUE   = colors.HexColor("#003875")   # SKF dark blue
_SKF_ORANGE = colors.HexColor("#E8540A")   # SKF orange
_LIGHT_BLUE = colors.HexColor("#E6EEF5")   # table header fill
_LIGHT_GRAY = colors.HexColor("#F5F5F5")   # alternate row fill
_MID_GRAY   = colors.HexColor("#CCCCCC")   # borders

PAGE_W, PAGE_H = A4
MARGIN        = 20 * mm
CONTENT_W     = PAGE_W - 2 * MARGIN


# ---------------------------------------------------------------------------
# Styles
# ---------------------------------------------------------------------------

def _build_styles():
    styles = getSampleStyleSheet()

    styles.add(ParagraphStyle(
        name="ReportTitle",
        fontSize=22, leading=28,
        textColor=_SKF_BLUE,
        fontName="Helvetica-Bold",
        alignment=TA_CENTER,
        spaceAfter=4 * mm,
    ))
    styles.add(ParagraphStyle(
        name="ReportSubtitle",
        fontSize=12, leading=16,
        textColor=colors.HexColor("#555555"),
        fontName="Helvetica",
        alignment=TA_CENTER,
        spaceAfter=2 * mm,
    ))
    styles.add(ParagraphStyle(
        name="SectionHeader",
        fontSize=13, leading=18,
        textColor=_SKF_BLUE,
        fontName="Helvetica-Bold",
        spaceBefore=6 * mm,
        spaceAfter=2 * mm,
        borderPad=2 * mm,
    ))
    styles.add(ParagraphStyle(
        name="BodyText2",
        fontSize=9, leading=13,
        textColor=colors.black,
        fontName="Helvetica",
        spaceAfter=1 * mm,
    ))
    styles.add(ParagraphStyle(
        name="Caption",
        fontSize=8, leading=11,
        textColor=colors.HexColor("#666666"),
        fontName="Helvetica-Oblique",
        alignment=TA_CENTER,
        spaceAfter=3 * mm,
    ))
    styles.add(ParagraphStyle(
        name="TableHeader",
        fontSize=9,
        textColor=colors.white,
        fontName="Helvetica-Bold",
        alignment=TA_CENTER,
    ))
    styles.add(ParagraphStyle(
        name="TableCell",
        fontSize=8.5,
        textColor=colors.black,
        fontName="Helvetica",
        alignment=TA_CENTER,
    ))
    styles.add(ParagraphStyle(
        name="TableCellLeft",
        fontSize=8.5,
        textColor=colors.black,
        fontName="Helvetica",
        alignment=TA_LEFT,
    ))
    styles.add(ParagraphStyle(
        name="FooterText",
        fontSize=7.5,
        textColor=colors.HexColor("#888888"),
        fontName="Helvetica",
        alignment=TA_CENTER,
    ))
    return styles


# ---------------------------------------------------------------------------
# Helper — matplotlib figure → ReportLab Image in memory
# ---------------------------------------------------------------------------

def _fig_to_rl_image(fig, width_mm: float, height_mm: float) -> Image:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=180, bbox_inches="tight",
                facecolor="white", edgecolor="none")
    buf.seek(0)
    plt.close(fig)
    return Image(buf, width=width_mm * mm, height=height_mm * mm)


# ---------------------------------------------------------------------------
# Figure generators
# (each returns a ReportLab Image — add more here easily)
# ---------------------------------------------------------------------------

def _fig_ga_merit(ga_history: list, ga_pen_history: list) -> Image:
    """Merit and penalty evolution over generations."""
    gens = list(range(1, len(ga_history) + 1))

    fig, ax1 = plt.subplots(figsize=(7, 3.2))
    ax1.plot(gens, ga_history, color="#003875", linewidth=2, label="Best merit")
    ax1.set_xlabel("Generation", fontsize=9)
    ax1.set_ylabel("Merit (C_max − Aval)", fontsize=9, color="#003875")
    ax1.tick_params(axis="y", labelcolor="#003875", labelsize=8)
    ax1.tick_params(axis="x", labelsize=8)
    ax1.set_xlim(1, max(gens))

    # Penalty on secondary axis
    ax2 = ax1.twinx()
    pen_arr = np.array(ga_pen_history, dtype=float)
    pen_arr[pen_arr > 1e6] = np.nan   # suppress _BAD values
    ax2.plot(gens, pen_arr, color="#E8540A", linewidth=1.5,
             linestyle="--", label="Penalty sum", alpha=0.8)
    ax2.set_ylabel("Penalty Σu²", fontsize=9, color="#E8540A")
    ax2.tick_params(axis="y", labelcolor="#E8540A", labelsize=8)

    lines1, labels1 = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(lines1 + lines2, labels1 + labels2,
               fontsize=8, loc="lower right")
    ax1.grid(True, alpha=0.3, linewidth=0.5)
    fig.tight_layout()
    return _fig_to_rl_image(fig, width_mm=155, height_mm=70)


def _fig_viscosity_temperature(vg: int, T_op: float, v_act: float) -> Image:
    """Viscosity vs temperature curve for the selected VG grade."""
    try:
        from Graficos.Viscosity.Viscosity_temperature_diagram_for_ISO_viscosity_grades.viscosity_ISO import get_viscosity
        temps = np.linspace(20, 120, 200)
        visc  = [get_viscosity(vg=vg, temperature=t) for t in temps]
    except Exception:
        return None

    fig, ax = plt.subplots(figsize=(6.5, 3.2))
    ax.semilogy(temps, visc, color="#003875", linewidth=2,
                label=f"ISO VG {vg}")
    ax.axvline(T_op, color="#E8540A", linestyle="--", linewidth=1.5,
               label=f"T_op = {T_op:.0f} °C")
    ax.axhline(v_act, color="#888888", linestyle=":", linewidth=1.2,
               label=f"v = {v_act:.1f} mm2/s")
    ax.plot(T_op, v_act, "o", color="#E8540A", markersize=7, zorder=5)

    ax.set_xlabel("Temperature [°C]", fontsize=9)
    ax.set_ylabel("Kinematic viscosity [mm2/s]", fontsize=9)
    ax.legend(fontsize=8)
    ax.grid(True, which="both", alpha=0.3, linewidth=0.5)
    ax.tick_params(labelsize=8)
    fig.tight_layout()
    return _fig_to_rl_image(fig, width_mm=150, height_mm=70)


def _fig_rated_viscosity(dm: float, n_opt: float, v1: float, n_user: float) -> Image:
    """Rated viscosity v1 vs speed curve at the bearing mean diameter."""
    try:
        from Graficos.Viscosity.Rated_Viscosity.rated_viscosity import get_v1
        speeds = np.logspace(1, 5, 300)
        v1s    = [get_v1(dm=dm, n=ni) for ni in speeds]
    except Exception:
        return None

    fig, ax = plt.subplots(figsize=(6.5, 3.2))
    ax.loglog(speeds, v1s, color="#003875", linewidth=2,
              label=f"v1  (dm = {dm:.1f} mm)")
    ax.axvline(n_opt, color="#E8540A", linestyle="--", linewidth=1.5,
               label=f"n = {n_opt:.0f} rpm")
    ax.axhline(v1, color="#888888", linestyle=":", linewidth=1.2,
               label=f"v1 = {v1:.1f} mm2/s")
    ax.plot(n_opt, v1, "o", color="#E8540A", markersize=7, zorder=5)

    ax.set_xlabel("Speed [rpm]", fontsize=9)
    ax.set_ylabel("Rated viscosity v1 [mm2/s]", fontsize=9)
    ax.legend(fontsize=8)
    ax.grid(True, which="both", alpha=0.3, linewidth=0.5)
    ax.tick_params(labelsize=8)
    fig.tight_layout()
    return _fig_to_rl_image(fig, width_mm=150, height_mm=70)


def _fig_friction_breakdown(M_rr, M_sl, M_drag, M_seal) -> Image:
    """Pie chart of friction moment components."""
    labels, values, clrs = [], [], []
    pairs = [
        ("Rolling M_rr",  M_rr,   "#003875"),
        ("Sliding M_sl",  M_sl,   "#1A6EA8"),
        ("Drag M_drag",   M_drag, "#4A9FD4"),
        ("Seal M_seal",   M_seal if M_seal else 0, "#E8540A"),
    ]
    for lbl, val, c in pairs:
        if val and val > 0:
            labels.append(lbl)
            values.append(val)
            clrs.append(c)

    if not values:
        return None

    fig, ax = plt.subplots(figsize=(5, 3.2))
    wedges, texts, autotexts = ax.pie(
        values, labels=None, colors=clrs,
        autopct="%1.1f%%", startangle=90,
        pctdistance=0.75,
        wedgeprops={"linewidth": 0.8, "edgecolor": "white"}
    )
    for at in autotexts:
        at.set_fontsize(8)
    ax.legend(wedges, [f"{l} ({v:.1f} N·mm)" for l, v in zip(labels, values)],
              fontsize=7.5, loc="lower center",
              bbox_to_anchor=(0.5, -0.18), ncol=2)
    ax.set_title("Friction moment breakdown", fontsize=9, pad=8)
    fig.tight_layout()
    return _fig_to_rl_image(fig, width_mm=130, height_mm=72)


# ---------------------------------------------------------------------------
# Table builders
# ---------------------------------------------------------------------------

def _table_operating_inputs(d: dict, styles) -> Table:
    """Two-column table: Operating inputs."""
    TH = styles["TableHeader"]
    TC = styles["TableCell"]
    TCL = styles["TableCellLeft"]

    rows = [
        [Paragraph("Parameter", TH), Paragraph("Value", TH),
         Paragraph("Parameter", TH), Paragraph("Value", TH)],
        [Paragraph("Radial load Fr", TCL),
         Paragraph(f"{d['Fr']:.0f} N", TC),
         Paragraph("Axial load Fa", TCL),
         Paragraph(f"{d['Fa']:.0f} N", TC)],
        [Paragraph("Speed n", TCL),
         Paragraph(f"{d['n']:.0f} rpm", TC),
         Paragraph("Temperature T_op", TCL),
         Paragraph(f"{d['T_op']:.1f} °C", TC)],
        [Paragraph("Required life L10h", TCL),
         Paragraph(f"{d['L10h_req']:,.0f} h", TC),
         Paragraph("ISO VG grade (optimised)", TCL),
         Paragraph(f"VG {d['vg']}", TC)],
        [Paragraph("Lubrication", TCL),
         Paragraph(d['lubrication'], TC),
         Paragraph("Lubricant", TCL),
         Paragraph(d['lubricant'], TC)],
        [Paragraph("Contamination", TCL),
         Paragraph(d['contamination'].replace("_", " "), TC),
         Paragraph("Oil level H", TCL),
         Paragraph(f"{d['H']:.0f} mm", TC)],
    ]

    col_w = [CONTENT_W * 0.28, CONTENT_W * 0.22,
             CONTENT_W * 0.28, CONTENT_W * 0.22]
    t = Table(rows, colWidths=col_w)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), _SKF_BLUE),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, _LIGHT_GRAY]),
        ("GRID", (0, 0), (-1, -1), 0.5, _MID_GRAY),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING",    (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING",   (0, 0), (-1, -1), 6),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 6),
        ("SPAN", (0, 0), (0, 0)),
    ]))
    return t


def _table_bearing_properties(bearing, styles) -> Table:
    """Bearing datasheet table."""
    TH  = styles["TableHeader"]
    TC  = styles["TableCell"]
    TCL = styles["TableCellLeft"]

    rows = [
        [Paragraph("Property", TH), Paragraph("Value", TH),
         Paragraph("Property", TH), Paragraph("Value", TH)],
        [Paragraph("Designation", TCL),
         Paragraph(bearing.designation, TC),
         Paragraph("Type", TCL),
         Paragraph(str(bearing.type), TC)],
        [Paragraph("Bore d", TCL),
         Paragraph(f"{bearing.d:.0f} mm", TC),
         Paragraph("Outer diameter D", TCL),
         Paragraph(f"{bearing.D:.0f} mm", TC)],
        [Paragraph("Width B", TCL),
         Paragraph(f"{bearing.B:.0f} mm", TC),
         Paragraph("Mean diameter dm", TCL),
         Paragraph(f"{0.5*(bearing.d+bearing.D):.1f} mm", TC)],
        [Paragraph("Dynamic rating C", TCL),
         Paragraph(f"{bearing.C:.2f} kN", TC),
         Paragraph("Static rating C0", TCL),
         Paragraph(f"{bearing.C0:.2f} kN", TC)],
        [Paragraph("Fatigue limit Pu", TCL),
         Paragraph(f"{bearing.Pu:.3f} kN" if bearing.Pu else "—", TC),
         Paragraph("Limiting speed", TCL),
         Paragraph(f"{bearing.n_limit:.0f} rpm" if bearing.n_limit else "—", TC)],
        [Paragraph("Reference speed", TCL),
         Paragraph(f"{bearing.n_ref:.0f} rpm" if bearing.n_ref else "—", TC),
         Paragraph("Mass", TCL),
         Paragraph(f"{bearing.mass*1000:.0f} g" if bearing.mass else "—", TC)],
    ]

    col_w = [CONTENT_W * 0.28, CONTENT_W * 0.22,
             CONTENT_W * 0.28, CONTENT_W * 0.22]
    t = Table(rows, colWidths=col_w)
    t.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, 0), _SKF_BLUE),
        ("ROWBACKGROUNDS",(0, 1), (-1, -1), [colors.white, _LIGHT_GRAY]),
        ("GRID",          (0, 0), (-1, -1), 0.5, _MID_GRAY),
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING",    (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING",   (0, 0), (-1, -1), 6),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 6),
    ]))
    return t


def _table_results(d: dict, styles) -> Table:
    """Results table: lubrication, life, friction."""
    TH  = styles["TableHeader"]
    TC  = styles["TableCell"]
    TCL = styles["TableCellLeft"]

    margin_pct = (d["L_skf"] - d["L10h_req"]) / d["L10h_req"] * 100
    margin_color = "#1A7A1A" if margin_pct >= 0 else "#CC0000"

    rows = [
        # ---- Lubrication ----
        [Paragraph("Lubrication", TH), Paragraph("Value", TH),
         Paragraph("Life", TH),        Paragraph("Value", TH)],
        [Paragraph("Actual viscosity v", TCL),
         Paragraph(f"{d['v_act']:.2f} mm²/s", TC),
         Paragraph("L<sub>10h</sub> basic", TCL),
         Paragraph(f"{d['L10h']:,.0f} h", TC)],
        [Paragraph("Rated viscosity v<sub>1</sub>", TCL),
         Paragraph(f"{d['v1']:.2f} mm²/s", TC),
         Paragraph("L<sub>skf</sub> modified", TCL),
         Paragraph(f"{d['L_skf']:,.0f} h", TC)],
        [Paragraph("Viscosity ratio κ", TCL),
         Paragraph(f"{d['kappa']:.3f}", TC),
         Paragraph("Required L<sub>10h</sub>", TCL),
         Paragraph(f"{d['L10h_req']:,.0f} h", TC)],
        [Paragraph("κ assessment", TCL),
         Paragraph(_kappa_label(d["kappa"]), TC),
         Paragraph("Safety margin", TCL),
         Paragraph(
             f'<font color="{margin_color}"><b>{margin_pct:+.1f} %</b></font>',
             TC)],
        # ---- Friction ----
        [Paragraph("Friction", TH), Paragraph("Value [N·mm]", TH),
         Paragraph("Friction", TH), Paragraph("Value [N·mm]", TH)],
        [Paragraph("M_rr  rolling", TCL),
         Paragraph(f"{d['M_rr']:.2f}", TC),
         Paragraph("M_sl  sliding", TCL),
         Paragraph(f"{d['M_sl']:.2f}", TC)],
        [Paragraph("M_drag  drag", TCL),
         Paragraph(f"{d['M_drag']:.2f}", TC),
         Paragraph("M_seal  seal", TCL),
         Paragraph(
             f"{d['M_seal']:.2f}" if (d['M_seal'] is not None and d['M_seal'] > 0)
             else ("0.00 (no catalogue data)" if d['M_seal'] == 0.0 else "—"),
             TC)],
        [Paragraph("<b>M_total</b>", TCL),
         Paragraph(f"<b>{d['M_tot']:.2f}</b>", TC),
         Paragraph("Power loss P_loss", TCL),
         Paragraph(f"{_power_loss(d['M_tot'], d['n_opt']):.2f} W", TC)],
    ]

    col_w = [CONTENT_W * 0.28, CONTENT_W * 0.22,
             CONTENT_W * 0.28, CONTENT_W * 0.22]
    t = Table(rows, colWidths=col_w)
    t.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, 0), _SKF_BLUE),
        ("BACKGROUND",    (0, 5), (-1, 5), _SKF_BLUE),
        ("ROWBACKGROUNDS",(0, 1), (-1, 4), [colors.white, _LIGHT_GRAY]),
        ("ROWBACKGROUNDS",(0, 6), (-1, -1), [colors.white, _LIGHT_GRAY]),
        ("GRID",          (0, 0), (-1, -1), 0.5, _MID_GRAY),
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING",    (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING",   (0, 0), (-1, -1), 6),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 6),
    ]))
    return t


def _table_candidates(candidates: list, bearing_selected, styles) -> Table:
    """Table of all candidates that passed the life filter."""
    TH  = styles["TableHeader"]
    TC  = styles["TableCell"]
    TCL = styles["TableCellLeft"]

    header = [
        Paragraph("Designation",    TH),
        Paragraph("D [mm]",         TH),
        Paragraph("B [mm]",         TH),
        Paragraph("C [kN]",         TH),
        Paragraph("C0 [kN]",        TH),
        Paragraph("n_limit [rpm]",  TH),
    ]
    rows = [header]
    for b in candidates:
        selected = b.designation == bearing_selected.designation
        style    = ParagraphStyle(
            "sel" if selected else "nor",
            parent=TC,
            fontName="Helvetica-Bold" if selected else "Helvetica",
            textColor=_SKF_ORANGE if selected else colors.black,
        )
        rows.append([
            Paragraph(b.designation + (" ◀" if selected else ""), style),
            Paragraph(f"{b.D:.0f}",        style),
            Paragraph(f"{b.B:.0f}",        style),
            Paragraph(f"{b.C:.2f}",        style),
            Paragraph(f"{b.C0:.2f}",       style),
            Paragraph(f"{b.n_limit:.0f}",  style),
        ])

    col_w = [CONTENT_W*0.32, CONTENT_W*0.12, CONTENT_W*0.12,
             CONTENT_W*0.14, CONTENT_W*0.14, CONTENT_W*0.16]
    t = Table(rows, colWidths=col_w)
    t.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, 0), _SKF_BLUE),
        ("ROWBACKGROUNDS",(0, 1), (-1, -1), [colors.white, _LIGHT_GRAY]),
        ("GRID",          (0, 0), (-1, -1), 0.5, _MID_GRAY),
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING",    (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LEFTPADDING",   (0, 0), (-1, -1), 5),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 5),
    ]))
    return t


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _kappa_label(kappa: float) -> str:
    if kappa >= 4.0:
        return "Excellent (κ ≥ 4)"
    elif kappa >= 2.0:
        return "Very good (κ ≥ 2)"
    elif kappa >= 1.0:
        return "Good (κ ≥ 1)"
    elif kappa >= 0.4:
        return "Marginal — EP additive recommended"
    else:
        return "Poor — lubrication insufficient"


def _power_loss(M_tot_Nmm: float, n_rpm: float) -> float:
    """Power loss in watts from total moment [N·mm] and speed [rpm]."""
    omega = n_rpm * 2 * math.pi / 60   # rad/s
    return (M_tot_Nmm * 1e-3) * omega  # W  (N·mm → N·m)


# ---------------------------------------------------------------------------
# Header / Footer callbacks
# ---------------------------------------------------------------------------

def _make_header_footer(bearing_designation: str, timestamp: str):
    def _on_page(canvas, doc):
        canvas.saveState()
        # Header bar
        canvas.setFillColor(_SKF_BLUE)
        canvas.rect(MARGIN, PAGE_H - 14*mm, CONTENT_W, 9*mm, fill=1, stroke=0)
        canvas.setFillColor(colors.white)
        canvas.setFont("Helvetica-Bold", 9)
        canvas.drawString(MARGIN + 3*mm, PAGE_H - 9*mm,
                          "SKF Bearing Selection Tool — Technical Report")
        canvas.setFont("Helvetica", 8)
        canvas.drawRightString(PAGE_W - MARGIN - 3*mm, PAGE_H - 9*mm,
                               bearing_designation)
        # Footer
        canvas.setFillColor(colors.HexColor("#888888"))
        canvas.setFont("Helvetica", 7)
        canvas.drawString(MARGIN, 10*mm,
                          f"Generated: {timestamp}  |  SKF General Catalogue 10000 EN  |  ISO 281:2007")
        canvas.drawRightString(PAGE_W - MARGIN, 10*mm,
                               f"Page {doc.page}")
        # Footer line
        canvas.setStrokeColor(_MID_GRAY)
        canvas.setLineWidth(0.5)
        canvas.line(MARGIN, 13*mm, PAGE_W - MARGIN, 13*mm)
        canvas.restoreState()
    return _on_page


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def generate_report(data: dict) -> str:
    """
    Build and save the PDF report.

    Parameters
    ----------
    data : dict  — see module docstring for required keys

    Returns
    -------
    str — absolute path to the saved PDF
    """
    # ---- Output path ----
    repo_root   = os.path.dirname(os.path.abspath(__file__))
    reports_dir = os.path.join(repo_root, "reports")
    os.makedirs(reports_dir, exist_ok=True)

    timestamp   = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    designation = data["bearing"].designation.replace(" ", "_").replace("/", "-")
    filename    = f"SKF_Report_{designation}_{timestamp}.pdf"
    filepath    = os.path.join(reports_dir, filename)

    ts_readable = datetime.datetime.now().strftime("%d %B %Y  %H:%M:%S")

    # ---- Document ----
    doc = SimpleDocTemplate(
        filepath,
        pagesize=A4,
        leftMargin=MARGIN, rightMargin=MARGIN,
        topMargin=18*mm, bottomMargin=18*mm,
        title=f"SKF Bearing Report — {data['bearing'].designation}",
        author="SKF Bearing Selection Tool",
    )

    styles  = _build_styles()
    story   = []
    bearing = data["bearing"]
    dm      = 0.5 * (bearing.d + bearing.D)

    on_page = _make_header_footer(bearing.designation, ts_readable)

    # ==================================================================
    # SECTION 0 — Title page block
    # ==================================================================
    story.append(Spacer(1, 8*mm))
    story.append(Paragraph("SKF Bearing Selection Tool", styles["ReportTitle"]))
    story.append(Paragraph("Technical Report — Deep Groove Ball Bearing",
                            styles["ReportSubtitle"]))
    story.append(Paragraph(f"Generated: {ts_readable}", styles["ReportSubtitle"]))
    story.append(HRFlowable(width="100%", thickness=2,
                            color=_SKF_ORANGE, spaceAfter=6*mm))

    # ==================================================================
    # SECTION 1 — Operating conditions
    # ==================================================================
    story.append(Paragraph("1. Operating Conditions", styles["SectionHeader"]))
    story.append(_table_operating_inputs(data, styles))
    story.append(Spacer(1, 4*mm))

    # ==================================================================
    # SECTION 2 — Bearing properties
    # ==================================================================
    story.append(Paragraph("2. Selected Bearing", styles["SectionHeader"]))
    story.append(_table_bearing_properties(bearing, styles))
    story.append(Spacer(1, 4*mm))

    # ==================================================================
    # SECTION 3 — Candidate bearings
    # ==================================================================
    if data.get("candidates"):
        story.append(Paragraph("3. Candidate Bearings (life filter passed)",
                               styles["SectionHeader"]))
        story.append(Paragraph(
            "The following bearings passed the minimum life requirement "
            f"(L<sub>skf</sub> ≥ {data['L10h_req']:,.0f} h). "
            "The selected bearing is highlighted.",
            styles["BodyText2"]))
        story.append(Spacer(1, 2*mm))
        story.append(_table_candidates(data["candidates"], bearing, styles))
        story.append(Spacer(1, 4*mm))

    # ==================================================================
    # SECTION 4 — Results
    # ==================================================================
    story.append(Paragraph("4. Results — Lubrication, Life &amp; Friction",
                            styles["SectionHeader"]))
    story.append(_table_results(data, styles))
    story.append(Spacer(1, 4*mm))

    # ==================================================================
    # SECTION 5 — Figures
    # ==================================================================
    story.append(PageBreak())
    story.append(Paragraph("5. Figures", styles["SectionHeader"]))

    # 5.1 GA merit
    story.append(Paragraph("5.1  Genetic Algorithm — Merit Evolution",
                            styles["BodyText2"]))
    fig_merit = _fig_ga_merit(data["ga_history"], data["ga_pen_history"])
    story.append(fig_merit)
    story.append(Paragraph(
        "Figure 1 — Best merit and constraint penalty over generations. "
        "Merit = C_max − Aval; penalty = Σu_j². "
        "λ is updated adaptively (Hadj-Alouane &amp; Bean).",
        styles["Caption"]))
    story.append(Spacer(1, 4*mm))

    # 5.2 Viscosity vs temperature
    story.append(Paragraph("5.2  Viscosity–Temperature Curve",
                            styles["BodyText2"]))
    fig_vt = _fig_viscosity_temperature(data["vg"], data["T_op"], data["v_act"])
    if fig_vt:
        story.append(fig_vt)
        story.append(Paragraph(
            f"Figure 2 — Kinematic viscosity vs temperature for ISO VG {data['vg']}. "
            f"Operating point: T = {data['T_op']:.0f} °C, "
            f"v = {data['v_act']:.1f} mm²/s.",
            styles["Caption"]))
    story.append(Spacer(1, 4*mm))

    # 5.3 Rated viscosity vs speed
    story.append(Paragraph("5.3  Rated Viscosity vs Speed",
                            styles["BodyText2"]))
    fig_rv = _fig_rated_viscosity(dm, data["n_opt"], data["v1"], data["n"])
    if fig_rv:
        story.append(fig_rv)
        story.append(Paragraph(
            f"Figure 3 — Rated viscosity v1 vs speed for dm = {dm:.1f} mm. "
            f"Operating point: n = {data['n_opt']:.0f} rpm, "
            f"v1 = {data['v1']:.1f} mm²/s.",
            styles["Caption"]))
    story.append(Spacer(1, 4*mm))

    # 5.4 Friction breakdown
    story.append(Paragraph("5.4  Frictional Moment Breakdown",
                            styles["BodyText2"]))
    fig_fr = _fig_friction_breakdown(
        data["M_rr"], data["M_sl"], data["M_drag"], data.get("M_seal"))
    if fig_fr:
        story.append(fig_fr)
        story.append(Paragraph(
            f"Figure 4 — Distribution of frictional moment components. "
            f"M_total = {data['M_tot']:.2f} N·mm  "
            f"(P_loss = {_power_loss(data['M_tot'], data['n_opt']):.2f} W).",
            styles["Caption"]))

    # ==================================================================
    # SECTION 6 — References
    # ==================================================================
    story.append(PageBreak())
    story.append(Paragraph("6. References", styles["SectionHeader"]))
    refs = [
        "SKF General Catalogue 10000 EN — Bearing selection procedure, Section 17.",
        "ISO 281:2007 — Rolling bearings: Dynamic load ratings and rating life.",
        "ISO/TS 16281:2008 — Methods for calculating the modified reference rating life.",
        "Hadj-Alouane &amp; Bean (1995) — Adaptive penalty method for genetic algorithms.",
        "SKF Engineering Handbook — Friction torque models, Table 1a/1b.",
    ]
    for i, ref in enumerate(refs, 1):
        story.append(Paragraph(f"[{i}]  {ref}", styles["BodyText2"]))
    story.append(Spacer(1, 4*mm))

    # ==================================================================
    # Build
    # ==================================================================
    doc.build(story, onFirstPage=on_page, onLaterPages=on_page)

    print(f"\n  ✔  Report saved: {filepath}")
    return filepath


# ---------------------------------------------------------------------------
# Convenience — open PDF after generation
# ---------------------------------------------------------------------------

def open_report(filepath: str) -> None:
    """Open the PDF with the system default viewer."""
    import subprocess, platform
    try:
        if platform.system() == "Windows":
            os.startfile(filepath)
        elif platform.system() == "Darwin":
            subprocess.run(["open", filepath])
        else:
            subprocess.run(["xdg-open", filepath])
    except Exception as exc:
        print(f"  ⚠  Could not open PDF automatically: {exc}")
        print(f"     Path: {filepath}")