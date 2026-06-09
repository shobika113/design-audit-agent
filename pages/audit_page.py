"""
app.py
Design Audit Agent — Streamlit Dashboard
Production-grade UI for the Level 1 Design Audit Agent.
"""

from __future__ import annotations

import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components
from dotenv import load_dotenv

# ── Path setup ─────────────────────────────────────────────────────────────────
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

# ── Logging setup ──────────────────────────────────────────────────────────────
LOG_DIR = ROOT / "logs"
LOG_DIR.mkdir(exist_ok=True)
log_file = LOG_DIR / f"audit_{datetime.now().strftime('%Y%m%d')}.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    handlers=[
        logging.FileHandler(log_file, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger("design_audit.app")

# ── Env ────────────────────────────────────────────────────────────────────────
load_dotenv()

# ── Late import (after path setup) ────────────────────────────────────────────
from agents.pipeline import AuditPipeline
from models.finding import SeverityLevel

# ── Severity color map ─────────────────────────────────────────────────────────
SEVERITY_COLORS = {
    "Critical": "#FF2D55",
    "High":     "#FF6B35",
    "Medium":   "#FFD60A",
    "Low":      "#30D158",
    "Info":     "#0A84FF",
}
SEVERITY_BG = {
    "Critical": "#2D0A0F",
    "High":     "#2D1A0A",
    "Medium":   "#2D2800",
    "Low":      "#0A2D17",
    "Info":     "#000F2D",
}

PRINCIPLE_ICONS = {
    "Visual Hierarchy": "👁️",
    "Contrast":         "🌗",
    "Spacing":          "↔️",
    "Alignment":        "⬛",
    "Consistency":      "🔄",
}


def get_severity_badge(severity: str) -> str:
    color = SEVERITY_COLORS.get(severity, "#888")
    return (
        f'<span style="background:{color};color:#000;padding:2px 10px;'
        f'border-radius:12px;font-size:12px;font-weight:700;'
        f'letter-spacing:0.5px">{severity.upper()}</span>'
    )


# ── Card CSS (injected inside each components.html iframe) ────────────────────
CARD_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;700&family=Inter:wght@300;400;500;600;700&display=swap');
* { box-sizing: border-box; margin: 0; padding: 0; }
body { background: transparent; font-family: 'Inter', sans-serif; padding: 0; }
.finding-card {
    background: #1C1C2E;
    border: 1px solid #2C2C3E;
    border-radius: 12px;
    padding: 20px 24px;
    transition: border-color 0.2s;
}
.finding-card:hover { border-color: #3C3C5E; }
.finding-title { font-size: 15px; font-weight: 600; color: #E5E5EA; margin-bottom: 8px; }
.finding-location {
    font-size: 13px; color: #636366;
    font-family: 'JetBrains Mono', monospace; margin-bottom: 12px;
}
.finding-section-label {
    font-size: 11px; font-weight: 600; color: #636366;
    text-transform: uppercase; letter-spacing: 1px; margin-bottom: 4px; margin-top: 12px;
}
.finding-section-value { font-size: 14px; color: #C7C7CC; margin-bottom: 4px; }
.rec-box {
    background: #0A1A2D;
    border-left: 3px solid #0A84FF;
    border-radius: 0 8px 8px 0;
    padding: 10px 14px;
    font-size: 14px;
    color: #BFC7D5;
}
.tag-pill {
    display: inline-block;
    background: #2C2C3E;
    color: #8E8E93;
    padding: 3px 10px;
    border-radius: 20px;
    font-size: 12px;
    margin-right: 6px;
    margin-bottom: 4px;
}
.header-row {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    margin-bottom: 8px;
}
</style>
"""


def finding_card_html(i, finding, sev_color, principle_icon, badge, element_html, wcag_html):
    """Return a complete self-contained HTML string for one finding card."""
    return f"""
    {CARD_CSS}
    <div class="finding-card" style="border-left: 4px solid {sev_color}">
        <div class="header-row">
            <div class="finding-title">{i}. {principle_icon} {finding.principle.value}</div>
            {badge}
        </div>
        <div class="finding-location">! {finding.location}</div>
        {element_html}
        <div class="finding-section-label">User Impact</div>
        <div class="finding-section-value">{finding.user_impact}</div>
        <div class="finding-section-label">Recommendation</div>
        <div class="rec-box">{finding.recommendation}</div>
        {wcag_html}
        <div class="finding-section-label">Confidence</div>
        <div class="finding-section-value">{finding.confidence}%</div>
    </div>
    """


# ── Custom CSS ─────────────────────────────────────────────────────────────────
def inject_css():
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;700&family=Inter:wght@300;400;500;600;700&display=swap');

        html, body, [class*="css"] {
            font-family: 'Inter', sans-serif;
        }
        .stApp {
            background: #0A0A0F;
            color: #E5E5EA;
        }
        .agent-header {
            background: linear-gradient(135deg, #1C1C2E 0%, #0A0A1A 100%);
            border: 1px solid #2C2C3E;
            border-radius: 16px;
            padding: 32px 40px;
            margin-bottom: 32px;
        }
        .agent-title {
            font-size: 36px;
            font-weight: 700;
            background: linear-gradient(90deg, #0A84FF, #5E5CE6);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            margin: 0;
        }
        .agent-subtitle {
            color: #8E8E93;
            font-size: 15px;
            margin-top: 6px;
        }
        .metric-card {
            background: #1C1C2E;
            border: 1px solid #2C2C3E;
            border-radius: 12px;
            padding: 20px;
            text-align: center;
        }
        .metric-value {
            font-size: 36px;
            font-weight: 700;
            color: #0A84FF;
            font-family: 'JetBrains Mono', monospace;
        }
        .metric-label {
            font-size: 13px;
            color: #8E8E93;
            margin-top: 4px;
        }
        .summary-box {
            background: #1C2C1C;
            border: 1px solid #2C3E2C;
            border-radius: 12px;
            padding: 20px 24px;
            margin-bottom: 24px;
            font-size: 15px;
            color: #C7C7CC;
            line-height: 1.6;
        }
        .error-box {
            background: #2D0A0F;
            border: 1px solid #FF2D55;
            border-radius: 12px;
            padding: 20px 24px;
            color: #FF6B80;
        }
        .tag-pill {
            display: inline-block;
            background: #2C2C3E;
            color: #8E8E93;
            padding: 3px 10px;
            border-radius: 20px;
            font-size: 12px;
            margin-right: 6px;
            margin-bottom: 4px;
        }
        .stButton > button {
            background: linear-gradient(135deg, #0A84FF, #5E5CE6) !important;
            color: white !important;
            border: none !important;
            border-radius: 10px !important;
            font-weight: 600 !important;
            padding: 10px 24px !important;
            font-size: 15px !important;
        }
        .stButton > button:hover {
            opacity: 0.85 !important;
            transform: translateY(-1px);
        }
        .upload-zone {
            border: 2px dashed #2C2C3E;
            border-radius: 12px;
            padding: 40px;
            text-align: center;
            color: #8E8E93;
        }
        div[data-testid="stSidebar"] {
            background: #111118 !important;
        }
        .stTextInput > div > div {
            background: #1C1C2E !important;
            border-color: #2C2C3E !important;
            color: #E5E5EA !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


# ── Sidebar ────────────────────────────────────────────────────────────────────
def render_sidebar():
    load_dotenv()
    api_key = os.getenv("GEMINI_API_KEY")
    return api_key


# ── Main dashboard ──────────────────────────────────────────────────────────────
def main():
    inject_css()

    # Header
    st.markdown(
        """
        <div class="agent-header">
            <h1 class="agent-title"> Design Audit Agent</h1>
            <p class="agent-subtitle">
                Production-grade autonomous UI/UX analysis · WCAG AA · 5 Design Principles · Zero Hallucinations
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    api_key = render_sidebar()

    # ── Upload section ─────────────────────────────────────────────────────────
    col_upload, col_preview = st.columns([1, 1], gap="large")

    with col_upload:
        st.markdown("###  Upload Page Design")
        uploaded_file = st.file_uploader(
            "Drop your UI Page here",
            type=["png", "jpg", "jpeg", "webp"],
            help="PNG, JPG/JPEG, or WebP · Max 20 MB · Min 200×200px",
        )

        if uploaded_file:
            st.success(
                f"**{uploaded_file.name}** — {uploaded_file.size / 1024:.1f} KB"
            )

            audit_btn = st.button(
                "🚀 Run Design Audit",
                use_container_width=True,
                disabled=not api_key,
            )

            if not api_key:
                st.warning(" Enter your Gemini API key in the sidebar to enable analysis.")
        else:
            st.markdown(
                '<div class="upload-zone"> Drag & drop a UI screenshot here<br>'
                '<small>Supports PNG · JPG · WebP</small></div>',
                unsafe_allow_html=True,
            )
            audit_btn = False

    with col_preview:
        if uploaded_file:
            st.markdown("### Page Preview")
            st.image(uploaded_file, caption=uploaded_file.name)

    # ── Run audit ──────────────────────────────────────────────────────────────
    if uploaded_file and audit_btn:
        logger.info("Audit triggered via UI for '%s'", uploaded_file.name)

        with st.spinner("Analyzing design — this takes 10–30 seconds…"):
            try:
                pipeline = AuditPipeline(gemini_api_key=api_key)
                result = pipeline.run(
                    file_bytes=uploaded_file.getvalue(),
                    filename=uploaded_file.name,
                )
            except Exception as exc:
                logger.exception("Pipeline initialization failed: %s", exc)
                st.error(f"Failed to initialize pipeline: {exc}")
                return

        # ── Results ────────────────────────────────────────────────────────────
        if result.success and result.report:
            report = result.report
            logger.info(
                "Audit displayed: %d findings in %.2fs",
                report.total_findings,
                result.duration_seconds,
            )

            st.markdown("---")
            st.markdown("## Audit Results")

            # Metrics row
            m1, m2, m3, m4, m5 = st.columns(5)
            metrics = [
                (m1, report.total_findings, "Total Findings"),
                (m2, report.overall_severity.value, "Overall Severity"),
                (m3, f"{report.analysis_confidence}%", "Confidence"),
                (m4, f"{result.duration_seconds:.1f}s", "Duration"),
                (m5, len(report.principles_with_issues), "Principles Affected"),
            ]
            for col, val, label in metrics:
                with col:
                    st.markdown(
                        f'<div class="metric-card">'
                        f'<div class="metric-value">{val}</div>'
                        f'<div class="metric-label">{label}</div>'
                        f'</div>',
                        unsafe_allow_html=True,
                    )

            st.markdown("<br>", unsafe_allow_html=True)

            # Summary
            st.markdown(
                f'<div class="summary-box"><strong>Summary:</strong> {report.summary}</div>',
                unsafe_allow_html=True,
            )

            # Principles pills
            if report.principles_with_issues:
                issues_html = " ".join(
                    f'<span class="tag-pill">{PRINCIPLE_ICONS.get(p.value,"")}'
                    f' {p.value}</span>'
                    for p in report.principles_with_issues
                )
                st.markdown(
                    f"**Issues found in:** {issues_html}", unsafe_allow_html=True
                )
                st.markdown("<br>", unsafe_allow_html=True)

            # ── Findings ───────────────────────────────────────────────────────
            st.markdown("###  Detailed Findings")

            # Filter controls
            filter_col, sort_col = st.columns([2, 1])
            with filter_col:
                severity_filter = st.multiselect(
                    "Filter by severity",
                    options=["Critical", "High", "Medium", "Low", "Info"],
                    default=["Critical", "High", "Medium", "Low", "Info"],
                )
            with sort_col:
                sort_by = st.selectbox(
                    "Sort by",
                    options=["Severity (worst first)", "Confidence (highest first)", "Principle"],
                )

            # Apply filters and sort
            filtered = [
                f for f in report.findings if f.severity.value in severity_filter
            ]
            severity_order = {
                SeverityLevel.CRITICAL: 0,
                SeverityLevel.HIGH: 1,
                SeverityLevel.MEDIUM: 2,
                SeverityLevel.LOW: 3,
                SeverityLevel.INFO: 4,
            }
            if sort_by == "Severity (worst first)":
                filtered.sort(key=lambda f: severity_order[f.severity])
            elif sort_by == "Confidence (highest first)":
                filtered.sort(key=lambda f: f.confidence, reverse=True)
            else:
                filtered.sort(key=lambda f: f.principle.value)

            st.caption(f"Showing {len(filtered)} of {report.total_findings} findings")

            for i, finding in enumerate(filtered, 1):
                sev_color = SEVERITY_COLORS.get(finding.severity.value, "#888")
                principle_icon = PRINCIPLE_ICONS.get(finding.principle.value, "•")
                badge = get_severity_badge(finding.severity.value)

                element_html = (
                    f'<div class="tag-pill">🔍 {finding.element_description}</div><br><br>'
                    if finding.element_description else ""
                )
                wcag_html = (
                    f'<br><div class="tag-pill">{finding.wcag_criterion}</div>'
                    if finding.wcag_criterion else ""
                )

                card_html = finding_card_html(
                    i, finding, sev_color, principle_icon, badge, element_html, wcag_html
                )
                components.html(card_html, height=320, scrolling=False)

            # ── JSON viewer ────────────────────────────────────────────────────
            st.markdown("---")
            st.markdown("### JSON Report")

            from services.report_generator import ReportGenerator
            rg = ReportGenerator()
            json_str = rg.to_json(report)

            col_view, col_dl = st.columns([3, 1])
            with col_view:
                with st.expander("View full JSON", expanded=False):
                    st.code(json_str, language="json")
            with col_dl:
                st.download_button(
                    label="Download JSON",
                    data=json_str,
                    file_name=f"audit_{uploaded_file.name}_{report.timestamp[:10]}.json",
                    mime="application/json",
                    use_container_width=True,
                )

            # ── Log preview ────────────────────────────────────────────────────
            with st.expander("View Agent Logs"):
                try:
                    log_content = log_file.read_text(encoding="utf-8")
                    lines = log_content.strip().split("\n")
                    st.code("\n".join(lines[-80:]), language="bash")
                except Exception:
                    st.info("Log file not yet available.")

        else:
            # Error display
            error = result.error
            if error:
                logger.error(
                    "Audit failed: [%s] %s", error.error_code, error.message
                )
                st.markdown(
                    f"""
                    <div class="error-box">
                        <h4> Audit Failed</h4>
                        <p><strong>Error Code:</strong> <code>{error.error_code}</code></p>
                        <p><strong>Message:</strong> {error.message}</p>
                        {f'<p><strong>Detail:</strong> {error.detail}</p>' if error.detail else ''}
                        {f'<p><strong>Suggested Action:</strong> {error.suggested_action}</p>' if error.suggested_action else ''}
                        <p><strong>Recoverable:</strong> {" Yes — try again" if error.recoverable else "No — contact support"}</p>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
            else:
                st.error("An unknown error occurred. Check the logs.")


if __name__ == "__main__":
    main()