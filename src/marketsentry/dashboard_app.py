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
            "Retrieval Operations",
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
    elif page == "Retrieval Operations":
        _render_retrieval_operations(db_path, exports_dir)


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


def _render_retrieval_operations(db_path: str, exports_dir: str) -> None:
    """Render the retrieval operations section."""
    from marketsentry.retrieval_dashboard import build_retrieval_operations_tables

    st.header("Retrieval Operations")
    st.caption("Read-only view of the retrieval ecosystem status.")

    tables = build_retrieval_operations_tables(database_path=db_path)
    s = tables.summary

    # Tab navigation
    tab = st.radio(
        "Subsection",
        [
            "Overview",
            "Fixture Capture Queue",
            "Approval Packages",
            "Batch Retrieval Runs",
            "Per-Item Results",
            "Retrieval Audit",
            "Retrieved Fixtures",
            "Health Checks",
        ],
        horizontal=True,
    )

    if tab == "Overview":
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Pending Captures", s.pending_capture_requests)
            st.metric("Captured", s.captured_capture_requests)
            st.metric("Total Queue Items", s.total_capture_requests)
        with col2:
            st.metric("Approval Packages", s.approval_packages_created)
            st.metric("Batch Runs", s.batch_retrieval_runs)
            st.metric("Retrieved Fixtures", s.retrieved_fixture_count)
        with col3:
            st.metric("Audit Decisions", s.audit_total_decisions)
            st.metric("Blocked Decisions", s.blocked_retrieval_decisions)
            st.metric("Network Calls", s.audit_records_network_true)

        st.subheader("Safety Configuration")
        safety_data = {
            "Setting": [
                "Live retrieval enabled",
                "Allowed sources",
                "User-Agent configured",
                "Contact email configured",
                "Dry-run required",
                "Max requests/minute",
            ],
            "Value": [
                str(s.live_retrieval_enabled),
                s.allowed_sources,
                str(s.user_agent_configured),
                str(s.contact_email_configured),
                str(s.dry_run_required),
                str(s.max_requests_per_minute),
            ],
        }
        st.table(safety_data)

        st.subheader("Latest Files")
        st.write(f"Audit file: {s.latest_audit_file or '(none)'}")
        st.write(f"Approval package: {s.latest_approval_package or '(none)'}")
        st.write(f"Batch manifest: {s.latest_batch_manifest or '(none)'}")

    elif tab == "Fixture Capture Queue":
        st.subheader("Fixture Capture Queue")
        queue = tables.capture_queue
        if not queue.rows:
            st.info("No capture queue items found.")
        else:
            # Filters
            statuses = sorted(set(r.get("status", "") for r in queue.rows))
            sources = sorted(set(r.get("source_site", "") for r in queue.rows))
            types = sorted(set(r.get("request_type", "") for r in queue.rows))

            col1, col2, col3 = st.columns(3)
            with col1:
                filt_status = st.selectbox("Status", ["All"] + statuses)
            with col2:
                filt_source = st.selectbox("Source", ["All"] + sources)
            with col3:
                filt_type = st.selectbox("Request Type", ["All"] + types)

            filtered = queue.rows
            if filt_status != "All":
                filtered = [r for r in filtered if r.get("status") == filt_status]
            if filt_source != "All":
                filtered = [r for r in filtered if r.get("source_site") == filt_source]
            if filt_type != "All":
                filtered = [r for r in filtered if r.get("request_type") == filt_type]

            st.write(f"Showing {len(filtered)} of {len(queue.rows)} items")
            df = pd.DataFrame(filtered)
            display_cols = [c for c in queue.columns if c in df.columns]
            st.dataframe(df[display_cols] if display_cols else df, use_container_width=True)

    elif tab == "Approval Packages":
        st.subheader("Approval Package Manifest")
        ap = tables.approval_packages
        if not ap.rows:
            st.info("No approval packages found.")
        else:
            df = pd.DataFrame(ap.rows)
            st.dataframe(df, use_container_width=True)

        if ap.latest_csv_files:
            st.subheader("Latest Approval CSV Files")
            for f in ap.latest_csv_files:
                st.write(f"- {f}")

    elif tab == "Batch Retrieval Runs":
        st.subheader("Batch Retrieval Manifest")
        bm = tables.batch_manifest
        if not bm.rows:
            st.info("No batch retrieval runs found.")
        else:
            df = pd.DataFrame(bm.rows)
            display_cols = [c for c in bm.columns if c in df.columns]
            st.dataframe(df[display_cols] if display_cols else df, use_container_width=True)

    elif tab == "Per-Item Results":
        st.subheader("Per-Item Retrieval Results")
        bi = tables.batch_items
        if not bi.rows:
            st.info("No per-item retrieval results found.")
        else:
            df = pd.DataFrame(bi.rows)
            display_cols = [c for c in bi.columns if c in df.columns]
            st.dataframe(df[display_cols] if display_cols else df, use_container_width=True)

    elif tab == "Retrieval Audit":
        st.subheader("Retrieval Audit Summary")
        audit = tables.audit_summary

        col1, col2 = st.columns(2)
        with col1:
            st.metric("Total Records", audit.total_records)
            st.metric("Allowed", audit.allowed)
            st.metric("Blocked", audit.blocked)
        with col2:
            st.metric("Dry Runs", audit.dry_runs)
            st.metric("Network True", audit.network_call_true)
            st.metric("Network False", audit.network_call_false)

        st.write(f"Files scanned: {audit.files_scanned}")
        st.write(f"Latest audit file: {audit.latest_audit_file or '(none)'}")

        if audit.blocked_reasons:
            st.subheader("Blocked Reasons")
            reasons_df = pd.DataFrame(
                [{"reason": k, "count": v} for k, v in sorted(
                    audit.blocked_reasons.items(), key=lambda x: -x[1]
                )]
            )
            st.dataframe(reasons_df, use_container_width=True)

        # Dry-run approvals
        st.subheader("Dry-Run Approval Summary")
        dry = tables.dry_run_summary
        st.write(f"Total dry-run records: {dry.total_records}")
        st.write(f"Allowed: {dry.allowed}")
        st.write(f"Blocked: {dry.blocked}")
        st.write(f"Files scanned: {dry.files_scanned}")

    elif tab == "Retrieved Fixtures":
        st.subheader("Retrieved Fixture Inventory")
        inv = tables.fixture_inventory
        if not inv.rows:
            st.info("No retrieved fixtures found.")
        else:
            st.write(f"Search fixtures: {inv.total_search_fixtures}")
            st.write(f"Detail fixtures: {inv.total_detail_fixtures}")
            st.write(f"Total: {len(inv.rows)}")
            df = pd.DataFrame(inv.rows)
            display_cols = [c for c in inv.columns if c in df.columns]
            st.dataframe(df[display_cols] if display_cols else df, use_container_width=True)

    elif tab == "Health Checks":
        from marketsentry.retrieval_health import run_retrieval_health_checks

        st.subheader("Retrieval Health Checks")
        st.caption("Read-only health check results. No write actions.")

        health = run_retrieval_health_checks(database_path=db_path)

        # Severity metrics
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Total Issues", health.total_issues)
        with col2:
            st.metric("Warning", health.warning_count)
        with col3:
            st.metric("Error", health.error_count)
        with col4:
            st.metric("Critical", health.critical_count)

        # Category metrics
        st.subheader("Category Counts")
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Stale Captures", health.stale_capture_request_count)
            st.metric("Stale Approvals", health.stale_approval_package_count)
        with col2:
            st.metric("Unprocessed Fixtures", health.unprocessed_fixture_count)
            st.metric("Audit Anomalies", health.audit_anomaly_count)
        with col3:
            st.metric("Missing Policies", health.missing_policy_count)
            st.metric("Repeated Blocks", health.repeated_block_count)

        # Issues table
        if health.issues:
            st.subheader("Issues")
            issue_data = [
                {
                    "severity": i.severity,
                    "category": i.category,
                    "message": i.message,
                    "detail": i.detail,
                    "source": i.source,
                }
                for i in health.issues
            ]
            st.dataframe(
                pd.DataFrame(issue_data), use_container_width=True
            )
        else:
            st.success("No health issues found.")

        # Next actions
        if health.next_actions:
            st.subheader("Next Actions")
            for action in health.next_actions:
                st.write(
                    f"**{action.priority}.** {action.action} -- "
                    f"{action.reason}"
                )
                if action.command:
                    st.code(action.command, language="bash")


if __name__ == "__main__":
    main()
