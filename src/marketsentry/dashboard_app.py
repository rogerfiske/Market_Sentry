"""Streamlit dashboard app for Market_Sentry.

Local-only review dashboard and report viewer.
No live network calls. Reads local SQLite database and CSV reports.
Not a purchase recommendation tool.

Launch with:
    streamlit run src/marketsentry/dashboard_app.py
"""

import sys
from pathlib import Path

import pandas as pd

try:
    import streamlit as st
except ImportError:
    print("Streamlit is not installed. Install it with: pip install streamlit")
    print("Then run: streamlit run src/marketsentry/dashboard_app.py")
    sys.exit(1)

from marketsentry.config import config
from marketsentry.dashboard import (
    build_candidate_table,
    build_county_verification_table,
    build_cross_site_table,
    build_effective_dom_v2_table,
    build_monitoring_table,
    build_watchlist_table,
    find_workflow_summaries,
    get_dashboard_summary,
    load_latest_report_manifest,
)


def main() -> None:
    """Run the Streamlit dashboard application."""
    st.set_page_config(
        page_title="Market_Sentry Dashboard",
        page_icon="",
        layout="wide",
    )

    st.title("Market_Sentry Dashboard")
    st.caption(
        "Local review dashboard and report viewer. "
        "Reads local database and CSV reports only. "
        "Not a purchase recommendation tool."
    )

    # Sidebar configuration
    st.sidebar.header("Configuration")
    db_path = st.sidebar.text_input("Database path", value=config.database_path)
    exports_dir = st.sidebar.text_input("Exports directory", value=config.data_exports_dir)

    # Navigation
    page = st.sidebar.radio(
        "Section",
        [
            "Overview",
            "Candidate Review",
            "Watchlist",
            "Monitoring",
            "Effective DOM v2",
            "County Verification",
            "Cross-Site Review",
            "Reports",
            "Workflow Summaries",
        ],
    )

    if page == "Overview":
        _render_overview(db_path, exports_dir)
    elif page == "Candidate Review":
        _render_candidates(db_path)
    elif page == "Watchlist":
        _render_watchlist(db_path)
    elif page == "Monitoring":
        _render_monitoring(exports_dir)
    elif page == "Effective DOM v2":
        _render_effective_dom_v2(exports_dir)
    elif page == "County Verification":
        _render_county_verification(exports_dir)
    elif page == "Cross-Site Review":
        _render_cross_site(exports_dir)
    elif page == "Reports":
        _render_reports(exports_dir)
    elif page == "Workflow Summaries":
        _render_workflow_summaries(exports_dir)


def _render_overview(db_path: str, exports_dir: str) -> None:
    """Render the overview section with summary counts."""
    st.header("Overview")

    summary = get_dashboard_summary(db_path)

    if not summary.database_exists:
        st.warning(
            f"Database not found at: {summary.database_path}. "
            "Run 'marketsentry init-database' first."
        )
        return

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Candidates", summary.candidates_total)
        st.metric("Watched Properties", summary.watched_total)
        st.metric("Active Watched", summary.watched_active)
    with col2:
        st.metric("Snapshots", summary.snapshots_total)
        st.metric("Cross-Site Observations", summary.cross_site_observations)
        st.metric("County Records", summary.county_records)
    with col3:
        st.metric("Reports in Manifest", summary.reports_in_manifest)
        st.metric("High Priority Watched", summary.high_priority_watched)
        st.metric("Listing Events", summary.listing_events)
    with col4:
        st.metric("Quiet Gatekeeper Failures", summary.quiet_gatekeeper_failures)
        st.metric("Strong Review Candidates", summary.strong_review_candidates)
        st.metric("County Reset Applied", summary.county_reset_applied_count)
        st.metric("High Churn (>= 6.0)", summary.high_churn_count)


def _render_candidates(db_path: str) -> None:
    """Render the candidate review section with filters."""
    st.header("Candidate Review")

    df = build_candidate_table(db_path)
    if df.empty:
        st.info("No candidates found in database.")
        return

    # Sidebar filters
    st.sidebar.subheader("Candidate Filters")

    if "quiet_gatekeeper_result" in df.columns:
        gatekeeper_values = ["All"] + sorted(
            df["quiet_gatekeeper_result"].dropna().unique().tolist()
        )
        gatekeeper_filter = st.sidebar.selectbox(
            "Quiet Gatekeeper Result", gatekeeper_values
        )
        if gatekeeper_filter != "All":
            df = df[df["quiet_gatekeeper_result"] == gatekeeper_filter]

    if "user_decision" in df.columns:
        decision_values = ["All"] + sorted(
            df["user_decision"].dropna().unique().tolist()
        )
        decision_filter = st.sidebar.selectbox("User Decision", decision_values)
        if decision_filter != "All":
            df = df[df["user_decision"] == decision_filter]

    if "gas_service" in df.columns:
        gas_filter = st.sidebar.selectbox("Gas Service", ["All", "Yes", "No"])
        if gas_filter == "Yes":
            df = df[df["gas_service"] == 1]
        elif gas_filter == "No":
            df = df[df["gas_service"] != 1]

    if "quiet_score" in df.columns:
        min_quiet = st.sidebar.slider("Min Quiet Score", 0.0, 10.0, 0.0, 0.5)
        if min_quiet > 0:
            df = df[df["quiet_score"].fillna(0) >= min_quiet]

    if "vibrancy_score" in df.columns:
        max_vibrancy = st.sidebar.slider("Max Vibrancy Score", 0.0, 10.0, 10.0, 0.5)
        if max_vibrancy < 10.0:
            df = df[df["vibrancy_score"].fillna(10) <= max_vibrancy]

    if "recent_churn_index" in df.columns:
        min_churn = st.sidebar.slider("Min Churn Index", 0.0, 20.0, 0.0, 0.5)
        if min_churn > 0:
            df = df[df["recent_churn_index"].fillna(0) >= min_churn]

    st.write(f"Showing {len(df)} candidates")
    st.dataframe(df, use_container_width=True)


def _render_watchlist(db_path: str) -> None:
    """Render the watchlist section with filters."""
    st.header("Watchlist")

    df = build_watchlist_table(db_path)
    if df.empty:
        st.info("No watched properties found in database.")
        return

    # Sidebar filters
    st.sidebar.subheader("Watchlist Filters")

    if "watch_priority" in df.columns:
        priorities = ["All"] + sorted(
            df["watch_priority"].dropna().unique().tolist()
        )
        priority_filter = st.sidebar.selectbox("Watch Priority", priorities)
        if priority_filter != "All":
            df = df[df["watch_priority"] == priority_filter]

    if "active_watch_status" in df.columns:
        active_filter = st.sidebar.selectbox(
            "Active Status", ["All", "Active", "Inactive"]
        )
        if active_filter == "Active":
            df = df[df["active_watch_status"] == 1]
        elif active_filter == "Inactive":
            df = df[df["active_watch_status"] != 1]

    if "quiet_score" in df.columns:
        min_quiet = st.sidebar.slider(
            "Min Quiet Score (Watchlist)", 0.0, 10.0, 0.0, 0.5
        )
        if min_quiet > 0:
            df = df[df["quiet_score"].fillna(0) >= min_quiet]

    if "recent_churn_index" in df.columns:
        high_churn = st.sidebar.slider(
            "High Churn Threshold", 0.0, 20.0, 6.0, 0.5
        )
        churn_filter = st.sidebar.selectbox(
            "Churn Filter", ["All", "High Churn Only", "Low Churn Only"]
        )
        if churn_filter == "High Churn Only":
            df = df[df["recent_churn_index"].fillna(0) >= high_churn]
        elif churn_filter == "Low Churn Only":
            df = df[df["recent_churn_index"].fillna(0) < high_churn]

    if "county_reset_applied" in df.columns:
        reset_filter = st.sidebar.selectbox(
            "County Reset", ["All", "Reset Applied", "No Reset"]
        )
        if reset_filter == "Reset Applied":
            df = df[df["county_reset_applied"] == 1]
        elif reset_filter == "No Reset":
            df = df[df["county_reset_applied"] != 1]

    st.write(f"Showing {len(df)} watched properties")
    st.dataframe(df, use_container_width=True)


def _render_monitoring(exports_dir: str) -> None:
    """Render the monitoring section from latest report."""
    st.header("Monitoring")

    df = build_monitoring_table(exports_dir)
    if df.empty:
        st.info(
            "No monitoring report found. Run a watchlist refresh workflow "
            "to generate one."
        )
        return

    st.write(f"Showing {len(df)} properties from latest monitoring report")
    st.dataframe(df, use_container_width=True)


def _render_effective_dom_v2(exports_dir: str) -> None:
    """Render the Effective DOM v2 section from latest report."""
    st.header("Effective DOM v2")
    st.caption(
        "Compares v1 (listing-only) vs v2 (county-verified reset). "
        "Churn Index is preserved even when county reset is applied."
    )

    df = build_effective_dom_v2_table(exports_dir)
    if df.empty:
        st.info(
            "No Effective DOM v2 report found. Run a workflow that includes "
            "persist-effective-dom-v2 to generate one."
        )
        return

    st.write(f"Showing {len(df)} properties")

    # Highlight county reset properties
    if "county_reset_applied" in df.columns:
        reset_count = int(df["county_reset_applied"].sum())
        st.write(f"Properties with county reset applied: {reset_count}")

    st.dataframe(df, use_container_width=True)


def _render_county_verification(exports_dir: str) -> None:
    """Render the county verification section from latest report."""
    st.header("County Verification")
    st.caption("County recorder/assessor evidence for watched properties.")

    df = build_county_verification_table(exports_dir)
    if df.empty:
        st.info(
            "No county verification report found. Import county records "
            "and run a watchlist refresh workflow to generate one."
        )
        return

    st.write(f"Showing {len(df)} properties")
    st.dataframe(df, use_container_width=True)


def _render_cross_site(exports_dir: str) -> None:
    """Render the cross-site review section from latest report."""
    st.header("Cross-Site Review")
    st.caption(
        "Cross-site price, status, and DOM discrepancy flags "
        "across Zillow, Realtor, Homes, and Compass."
    )

    df = build_cross_site_table(exports_dir)
    if df.empty:
        st.info(
            "No cross-site report found. Parse cross-site fixtures "
            "and run a workflow to generate one."
        )
        return

    st.write(f"Showing {len(df)} properties")

    # Highlight discrepancies
    for flag_col in ["has_price_discrepancy", "has_status_discrepancy", "has_dom_discrepancy"]:
        if flag_col in df.columns:
            flagged = int(df[flag_col].sum())
            st.write(f"  {flag_col}: {flagged} flagged")

    st.dataframe(df, use_container_width=True)


def _render_reports(exports_dir: str) -> None:
    """Render the report manifest section."""
    st.header("Reports")
    st.caption("Report manifest showing all generated reports.")

    manifest = load_latest_report_manifest(exports_dir)
    if not manifest:
        st.info("No report manifest found. Run a workflow to generate reports.")
        return

    # Convert to DataFrame for display
    rows = [row.model_dump() for row in manifest]
    df = pd.DataFrame(rows)

    st.write(f"Total reports: {len(manifest)}")
    st.dataframe(df, use_container_width=True)


def _render_workflow_summaries(exports_dir: str) -> None:
    """Render the workflow summaries section."""
    st.header("Workflow Summaries")
    st.caption("Workflow summary markdown files from previous runs.")

    summaries = find_workflow_summaries(exports_dir)
    if not summaries:
        st.info("No workflow summaries found. Run a workflow to generate one.")
        return

    st.write(f"Found {len(summaries)} workflow summaries")

    # Show list and allow selection
    summary_names = [p.name for p in summaries]
    selected = st.selectbox("Select summary to preview", summary_names)

    if selected:
        selected_path = summaries[summary_names.index(selected)]
        try:
            content = selected_path.read_text(encoding="utf-8")
            st.markdown(content)
        except Exception as e:
            st.error(f"Could not read summary: {e}")


if __name__ == "__main__":
    main()
