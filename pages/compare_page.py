"""
app_level2.py
Design Audit Agent — Level 2: Before/After Regression Analysis
Streamlit Dashboard for visual diff between baseline and current screenshots.
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
logger = logging.getLogger("design_audit.app_level2")

load_dotenv()

from agents.regression_pipeline import RegressionPipeline
from models.regression import ChangeDirection, RegressionVerdict

# ── Color maps ─────────────────────────────────────────────────────────────────
DIRECTION_COLORS = {
    "improvement": "#30D158",
    "regression":  "#FF2D55",
    "neutral":     "#636366",
}
DIRECTION_ICONS = {
    "improvement": "✅",
    "regression":  "🔴",
    "neutral":     "⚪",
}
VERDICT_CONFIG = {
    RegressionVerdict.NET_IMPROVEMENT: ("✅ Net Improvement", "#30D158", "#0A2D17"),
    RegressionVerdict.NET_REGRESSION:  ("🔴 Net Regression",  "#FF2D55", "#2D0A0F"),
    RegressionVerdict.MIXED:           ("⚠️ Mixed Results",   "#FFD60A", "#2D2800"),
    RegressionVerdict.NO_CHANGE:       ("⚪ No Change",        "#636366", "#1C1C2E"),
}
CATEGORY_ICONS = {
    "color":       "🎨",
    "typography":  "🔤",
    "spacing":     "↔️",
    "layout":      "📐",
    "component":   "🧩",
    "contrast":    "🌗",
    "iconography": "🖼️",
    "other":       "•",
}

# ── Card CSS (injected inside each components.html iframe) ────────────────────
DIFF_CARD_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;700&family=Inter:wght@300;400;500;600;700&display=swap');
* { box-sizing: border-box; margin: 0; padding: 0; }
body { background: transparent; font-family: 'Inter', sans-serif; padding: 0; }
.diff-card {
    background: #1C1C2E;
    border: 1px solid #2C2C3E;
    border-radius: 12px;
    padding: 20px 24px;
}
.diff-card:hover { border-color: #3C3C5E; }
.diff-title { font-size: 15px; font-weight: 600; color: #E5E5EA; margin-bottom: 8px; }
.diff-location {
    font-size: 13px; color: #636366;
    font-family: 'JetBrains Mono', monospace; margin-bottom: 12px;
}
.diff-section-label {
    font-size: 11px; font-weight: 600; color: #636366;
    text-transform: uppercase; letter-spacing: 1px;
    margin-bottom: 4px; margin-top: 12px;
}
.diff-section-value { font-size: 14px; color: #C7C7CC; margin-bottom: 4px; }
.direction-badge {
    padding: 3px 12px; border-radius: 20px;
    font-size: 12px; font-weight: 700; display: inline-block;
}
.hex-swatch {
    display: inline-block; width: 16px; height: 16px;
    border-radius: 3px; margin-right: 6px;
    vertical-align: middle; border: 1px solid #3C3C5E;
}
.measurement-row {
    font-family: 'JetBrains Mono', monospace;
    font-size: 13px; color: #BFC7D5;
}
.a11y-flag {
    background: #2D0A0F; border: 1px solid #FF2D55;
    border-radius: 8px; padding: 10px 14px;
    margin-top: 12px; font-size: 13px; color: #FF6B80;
}
.reasoning-box {
    background: #111118; border-left: 3px solid #636366;
    border-radius: 0 8px 8px 0; padding: 10px 14px;
    font-size: 13px; color: #8E8E93; margin-bottom: 4px;
}
.header-row {
    display: flex; justify-content: space-between;
    align-items: flex-start; margin-bottom: 8px;
}
</style>
"""


def inject_css():
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;700&family=Inter:wght@300;400;500;600;700&display=swap');

        html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
        .stApp { background: #0A0A0F; color: #E5E5EA; }

        .agent-header {
            background: linear-gradient(135deg, #1C1C2E 0%, #0A0A1A 100%);
            border: 1px solid #2C2C3E; border-radius: 16px;
            padding: 32px 40px; margin-bottom: 32px;
        }
        .agent-title {
            font-size: 36px; font-weight: 700;
            background: linear-gradient(90deg, #FF6B35, #FF2D55);
            -webkit-background-clip: text; -webkit-text-fill-color: transparent; margin: 0;
        }
        .agent-subtitle { color: #8E8E93; font-size: 15px; margin-top: 6px; }

        .metric-card {
            background: #1C1C2E; border: 1px solid #2C2C3E;
            border-radius: 12px; padding: 20px; text-align: center;
        }
        .metric-value {
            font-size: 36px; font-weight: 700; color: #FF6B35;
            font-family: 'JetBrains Mono', monospace;
        }
        .metric-label { font-size: 13px; color: #8E8E93; margin-top: 4px; }

        .verdict-box {
            border-radius: 16px; padding: 24px 32px; margin: 24px 0;
            text-align: center;
        }
        .verdict-label { font-size: 28px; font-weight: 700; margin-bottom: 8px; }
        .verdict-summary { font-size: 15px; line-height: 1.6; opacity: 0.9; }

        .upload-zone { border: 2px dashed #2C2C3E; border-radius: 12px; padding: 40px; text-align: center; color: #8E8E93; }
        .error-box { background: #2D0A0F; border: 1px solid #FF2D55; border-radius: 12px; padding: 20px 24px; color: #FF6B80; }
        .stButton > button {
            background: linear-gradient(135deg, #FF6B35, #FF2D55) !important;
            color: white !important; border: none !important; border-radius: 10px !important;
            font-weight: 600 !important; padding: 10px 24px !important; font-size: 15px !important;
        }
        .stButton > button:hover { opacity: 0.85 !important; transform: translateY(-1px); }
        div[data-testid="stSidebar"] { background: #111118 !important; }
        </style>
        """,
        unsafe_allow_html=True,
    )


def direction_badge_html(direction: str) -> str:
    color = DIRECTION_COLORS.get(direction, "#636366")
    icon = DIRECTION_ICONS.get(direction, "•")
    return (
        f'<span class="direction-badge" style="background:{color}22;color:{color};border:1px solid {color}44">'
        f'{icon} {direction.upper()}</span>'
    )


def hex_swatch_html(hex_val: str | None) -> str:
    if not hex_val:
        return ""
    return f'<span class="hex-swatch" style="background:{hex_val}"></span><code style="color:#C7C7CC">{hex_val}</code>'


def diff_card_html(diff) -> str:
    """Return a complete self-contained HTML string for one diff card."""
    dir_color = DIRECTION_COLORS.get(diff.direction.value, "#636366")
    cat_icon = CATEGORY_ICONS.get(diff.category, "•")
    badge = direction_badge_html(diff.direction.value)

    # Build measurement row
    measurements = []
    if diff.baseline_hex or diff.current_hex:
        b = hex_swatch_html(diff.baseline_hex) or "<span style='color:#636366'>n/a</span>"
        c = hex_swatch_html(diff.current_hex) or "<span style='color:#636366'>n/a</span>"
        measurements.append(f"<span class='measurement-row'>Color: {b} → {c}</span>")
    if diff.baseline_px is not None or diff.current_px is not None:
        b_px = f"{diff.baseline_px}px" if diff.baseline_px is not None else "n/a"
        c_px = f"{diff.current_px}px" if diff.current_px is not None else "n/a"
        measurements.append(f"<span class='measurement-row'>Size: {b_px} → {c_px}</span>")
    if diff.baseline_value or diff.current_value:
        b_v = diff.baseline_value or "n/a"
        c_v = diff.current_value or "n/a"
        measurements.append(f"<span class='measurement-row'>Value: {b_v} → {c_v}</span>")
    measurements_html = (
        "<div class='diff-section-label'>Measurements</div>"
        "<div style='margin-bottom:12px'>" + "<br>".join(measurements) + "</div>"
    ) if measurements else ""

    a11y_html = ""
    if diff.is_accessibility_regression:
        a11y_type = diff.accessibility_regression_type.value if diff.accessibility_regression_type else "accessibility issue"
        a11y_detail = diff.accessibility_detail or "Accessibility regression detected."
        a11y_html = (
            f'<div class="a11y-flag"><strong>Accessibility Regression</strong> '
            f'— {a11y_type.replace("_", " ").title()}: {a11y_detail}</div>'
        )

    return f"""
    {DIFF_CARD_CSS}
    <div class="diff-card" style="border-left: 4px solid {dir_color}">
        <div class="header-row">
            <div class="diff-title">#{diff.diff_id} {cat_icon} {diff.category.title()}</div>
            {badge}
        </div>
        <div class="diff-location">📍 {diff.location}</div>
        <div class="diff-section-label">What Changed</div>
        <div class="diff-section-value">{diff.what_changed}</div>
        {measurements_html}
        <div class="diff-section-label">Reasoning</div>
        <div class="reasoning-box">{diff.direction_reasoning}</div>
        <div class="diff-section-label">UX Impact</div>
        <div class="diff-section-value">{diff.ux_impact}</div>
        {a11y_html}
        <div class="diff-section-label">Confidence</div>
        <div class="diff-section-value">{diff.confidence}%</div>
    </div>
    """


def main():
    inject_css()

    # Header
    st.markdown(
        """
        <div class="agent-header">
            <h1 class="agent-title">Design Regression Audit</h1>
            <p class="agent-subtitle">
                Level 2 — Before/After Visual Diff · Hex Values · Pixel Measurements · Accessibility Regression Detection
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    api_key = os.getenv("GEMINI_API_KEY")

    # ── Upload section ─────────────────────────────────────────────────────────
    st.markdown("### Upload Page Designs")
    col_baseline, col_current = st.columns(2, gap="large")

    with col_baseline:
        st.markdown("####  Baseline (Before)")
        baseline_file = st.file_uploader(
            "Upload the BEFORE screenshot",
            type=["png", "jpg", "jpeg", "webp"],
            key="baseline_uploader",
            help="The original / reference design",
        )
        if baseline_file:
            st.success(f" **{baseline_file.name}** — {baseline_file.size / 1024:.1f} KB")
            st.image(baseline_file, caption="Baseline (Before)", use_column_width=True)

    with col_current:
        st.markdown("####  Current (After)")
        current_file = st.file_uploader(
            "Upload the AFTER screenshot",
            type=["png", "jpg", "jpeg", "webp"],
            key="current_uploader",
            help="The new / updated design to audit",
        )
        if current_file:
            st.success(f"**{current_file.name}** — {current_file.size / 1024:.1f} KB")
            st.image(current_file, caption="Current (After)", use_column_width=True)

    # Run button
    st.markdown("---")
    both_uploaded = baseline_file and current_file

    if both_uploaded:
        if not api_key:
            st.warning("GEMINI_API_KEY not set in .env file. Cannot run analysis.")
            run_btn = False
        else:
            run_btn = st.button(
                " Run Regression Analysis",
                use_container_width=True,
            )
    else:
        st.markdown(
            '<div class="upload-zone"> Upload both BEFORE and AFTER screenshots to begin</div>',
            unsafe_allow_html=True,
        )
        run_btn = False

    # ── Run analysis ───────────────────────────────────────────────────────────
    if both_uploaded and run_btn:
        logger.info(
            "Regression audit triggered: '%s' vs '%s'",
            baseline_file.name,
            current_file.name,
        )

        with st.spinner("Comparing designs — this takes 15–40 seconds…"):
            try:
                pipeline = RegressionPipeline(gemini_api_key=api_key)
                result = pipeline.run(
                    baseline_bytes=baseline_file.getvalue(),
                    baseline_name=baseline_file.name,
                    current_bytes=current_file.getvalue(),
                    current_name=current_file.name,
                )
            except Exception as exc:
                logger.exception("Pipeline initialization failed: %s", exc)
                st.error(f" Failed to initialize pipeline: {exc}")
                return

        if result.success and result.report:
            report = result.report
            logger.info(
                "Regression audit displayed: %d diffs in %.2fs",
                report.total_diffs,
                result.duration_seconds,
            )

            st.markdown("---")
            st.markdown("##  Regression Analysis Results")

            # ── Verdict box ────────────────────────────────────────────────
            verdict_label, verdict_color, verdict_bg = VERDICT_CONFIG.get(
                report.verdict, (" Unknown", "#636366", "#1C1C2E")
            )
            st.markdown(
                f"""
                <div class="verdict-box" style="background:{verdict_bg};border:2px solid {verdict_color}44">
                    <div class="verdict-label" style="color:{verdict_color}">{verdict_label}</div>
                    <div class="verdict-summary" style="color:{verdict_color}cc">{report.verdict_summary}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

            # ── Metrics row ────────────────────────────────────────────────
            m1, m2, m3, m4, m5, m6 = st.columns(6)
            metrics = [
                (m1, report.total_diffs,           "Total Diffs"),
                (m2, f" {report.improvements_count}", "Improvements"),
                (m3, f" {report.regressions_count}", "Regressions"),
                (m4, f" {report.neutral_count}",   "Neutral"),
                (m5, f" {len(report.accessibility_regressions)}", "A11y Regressions"),
                (m6, f"{report.analysis_confidence}%", "Confidence"),
            ]
            for col, val, label in metrics:
                with col:
                    st.markdown(
                        f'<div class="metric-card">'
                        f'<div class="metric-value" style="font-size:24px">{val}</div>'
                        f'<div class="metric-label">{label}</div>'
                        f'</div>',
                        unsafe_allow_html=True,
                    )

            st.markdown("<br>", unsafe_allow_html=True)

            # ── Accessibility regression alert ─────────────────────────────
            if report.has_accessibility_regressions:
                a11y_names = [d.location for d in report.accessibility_regressions]
                st.error(
                    f"**{len(report.accessibility_regressions)} Accessibility Regression(s) Detected!**  \n"
                    f"Affected locations: {', '.join(a11y_names)}"
                )

            # ── Diff filter controls ───────────────────────────────────────
            st.markdown("###  Visual Differences")
            filter_col, sort_col, a11y_col = st.columns([2, 1, 1])

            with filter_col:
                direction_filter = st.multiselect(
                    "Filter by direction",
                    options=["improvement", "regression", "neutral"],
                    default=["improvement", "regression", "neutral"],
                )
            with sort_col:
                sort_by = st.selectbox(
                    "Sort by",
                    ["Regressions first", "Improvements first", "Confidence (highest)", "Category"],
                )
            with a11y_col:
                a11y_only = st.checkbox("A11y regressions only", value=False)

            # Apply filters
            filtered = [d for d in report.diffs if d.direction.value in direction_filter]
            if a11y_only:
                filtered = [d for d in filtered if d.is_accessibility_regression]

            # Sort
            if sort_by == "Regressions first":
                order = {"regression": 0, "neutral": 1, "improvement": 2}
                filtered.sort(key=lambda d: order.get(d.direction.value, 99))
            elif sort_by == "Improvements first":
                order = {"improvement": 0, "neutral": 1, "regression": 2}
                filtered.sort(key=lambda d: order.get(d.direction.value, 99))
            elif sort_by == "Confidence (highest)":
                filtered.sort(key=lambda d: d.confidence, reverse=True)
            else:
                filtered.sort(key=lambda d: d.category)

            st.caption(f"Showing {len(filtered)} of {report.total_diffs} diffs")

            # Render diff cards using components.html
            for i, diff in enumerate(filtered):
                components.html(diff_card_html(diff), height=380, scrolling=False)

            # ── JSON output ────────────────────────────────────────────────
            st.markdown("---")
            st.markdown("### JSON Report")

            from services.regression_report_generator import RegressionReportGenerator
            rg = RegressionReportGenerator()
            json_str = rg.to_json(report)

            col_view, col_dl = st.columns([3, 1])
            with col_view:
                with st.expander("View full JSON", expanded=False):
                    st.code(json_str, language="json")
            with col_dl:
                safe_base = baseline_file.name.replace(".", "_")
                safe_curr = current_file.name.replace(".", "_")
                st.download_button(
                    label="Download JSON",
                    data=json_str,
                    file_name=f"regression_{safe_base}_vs_{safe_curr}.json",
                    mime="application/json",
                    use_container_width=True,
                )

            # ── Log viewer ─────────────────────────────────────────────────
            with st.expander("View Agent Logs"):
                try:
                    log_content = log_file.read_text(encoding="utf-8")
                    lines = log_content.strip().split("\n")
                    st.code("\n".join(lines[-80:]), language="bash")
                except Exception:
                    st.info("Log file not yet available.")

        else:
            error = result.error
            if error:
                logger.error("Regression audit failed: [%s] %s", error.error_code, error.message)
                st.markdown(
                    f"""
                    <div class="error-box">
                        <h4>Regression Analysis Failed</h4>
                        <p><strong>Error Code:</strong> <code>{error.error_code}</code></p>
                        <p><strong>Message:</strong> {error.message}</p>
                        {f'<p><strong>Detail:</strong> {error.detail}</p>' if error.detail else ''}
                        {f'<p><strong>Suggested Action:</strong> {error.suggested_action}</p>' if error.suggested_action else ''}
                        <p><strong>Recoverable:</strong> {"Yes — try again" if error.recoverable else " No — contact support"}</p>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
            else:
                st.error("An unknown error occurred. Check the logs.")

    # ── Footer ─────────────────────────────────────────────────────────────────
    st.markdown("---")
    st.markdown(
        '<div style="text-align:center;color:#636366;font-size:13px">'
        "Design Audit Agent"
        "</div>",
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()