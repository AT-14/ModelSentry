import json
import sqlite3
from pathlib import Path

import pandas as pd
import streamlit as st


ARTIFACTS = Path("artifacts")
RESULTS = ARTIFACTS / "results.json"
VALIDATION_DIR = (
    ARTIFACTS / "validation_corrected"
    if (ARTIFACTS / "validation_corrected" / "validation_summary.json").exists()
    else ARTIFACTS / "validation"
)
VALIDATION_SUMMARY = VALIDATION_DIR / "validation_summary.json"
V2_HOLDOUT_DIR = ARTIFACTS / "validation_extended_v2_holdout"
V2_HOLDOUT_SUMMARY = V2_HOLDOUT_DIR / "validation_summary_v2.json"

st.set_page_config(page_title="ModelSentry", page_icon="MS", layout="wide")
st.markdown(
    """
    <style>
    .stApp { background: #071018; color: #e7edf2; }
    [data-testid="stMetric"] {
        background: #0d1c27;
        border: 1px solid #1d3948;
        border-radius: 4px;
        padding: 14px 16px;
    }
    [data-testid="stMetricValue"] { color: #f4b942; }
    .control-label {
        color: #69d4c5;
        font-size: 0.78rem;
        font-weight: 700;
        letter-spacing: 0.15em;
        margin-bottom: 0.2rem;
    }
    .control-title {
        color: #f7fafc;
        font-size: 2.4rem;
        font-weight: 750;
        line-height: 1;
        margin-bottom: 0.5rem;
    }
    .control-subtitle { color: #91a4b2; margin-bottom: 1.5rem; }
    .status-good {
        display: inline-block;
        color: #73e2c1;
        background: #0d2a27;
        border: 1px solid #225f55;
        padding: 5px 10px;
        font-size: 0.8rem;
        letter-spacing: 0.08em;
    }
    </style>
    """,
    unsafe_allow_html=True,
)
st.markdown('<div class="control-label">MODEL IP DEFENSE CONTROL ROOM</div>', unsafe_allow_html=True)
st.markdown('<div class="control-title">ModelSentry</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="control-subtitle">Stateful early warning for prediction-API extraction</div>',
    unsafe_allow_html=True,
)

if not RESULTS.exists():
    st.warning("Run `python run_demo.py --quick` to generate experiment evidence.")
    st.stop()

with RESULTS.open(encoding="utf-8") as handle:
    results = json.load(handle)

summary = results["summary"]
undefended = results["undefended_attack"]
defended = results["defended_attack"]
normal = results["normal_client"]
batch = results["batch_client"]

st.markdown('<span class="status-good">PROTECTED API ONLINE</span>', unsafe_allow_html=True)
st.write("")
columns = st.columns(5)
columns[0].metric("Attack detected", "YES" if summary["attack_detected"] else "NO")
columns[1].metric("First alert", f"Query {defended['first_alert_query']}")
columns[2].metric("Responses prevented", summary["responses_prevented"])
columns[3].metric(
    "Fidelity reduction",
    f"{summary['undefended_final_fidelity'] - summary['defended_final_fidelity']:.1%}",
)
columns[4].metric(
    "Benign clients blocked",
    f"{summary['benign_clients_blocked']}/{summary['benign_clients_tested']}",
)

overview_tab, evidence_tab, log_tab = st.tabs(
    ["Mission overview", "Attack evidence", "Event transcript"]
)

with overview_tab:
    left, right = st.columns([1.45, 1])
    with left:
        st.subheader("Clone fidelity under attack")
        chart = ARTIFACTS / "fidelity_vs_queries.png"
        if chart.exists():
            st.image(str(chart), caption="Latest seeded run; generated from actual queries")
    with right:
        st.subheader("Control outcome")
        comparison = pd.DataFrame(
            {
                "Scenario": ["Defence disabled", "ModelSentry enabled"],
                "Responses": [
                    undefended["responses_received"],
                    defended["responses_received"],
                ],
                "Final fidelity": [
                    summary["undefended_final_fidelity"],
                    summary["defended_final_fidelity"],
                ],
            }
        )
        st.dataframe(
            comparison.style.format({"Final fidelity": "{:.2%}"}),
            hide_index=True,
            width="stretch",
        )
        st.subheader("Legitimate-client checks")
        benign_table = pd.DataFrame(
            [
                {"Client": "Normal interactive", **normal},
                {"Client": "Legitimate batch", **batch},
            ]
        )
        st.dataframe(benign_table, hide_index=True, width="stretch")

    if V2_HOLDOUT_SUMMARY.exists():
        with V2_HOLDOUT_SUMMARY.open(encoding="utf-8") as handle:
            validation = json.load(handle)
        enhanced = validation["mode_overview"]["enhanced"]
        st.subheader("Frozen V2.4 holdout")
        validation_columns = st.columns(4)
        validation_columns[0].metric(
            "Attacks detected",
            f"{enhanced['attack_runs_detected']}/{enhanced['attack_runs_tested']}",
        )
        validation_columns[1].metric(
            "Benign sessions mitigated",
            f"{enhanced['benign_sessions_mitigated']}/{enhanced['benign_sessions_tested']}",
        )
        validation_columns[2].metric(
            "Mean final fidelity",
            f"{enhanced['final_fidelity']['mean']:.2%}",
        )
        validation_columns[3].metric(
            "API p50 latency",
            f"{validation['latency']['enhanced/api_in_process']['p50_ms']['mean']:.2f} ms",
        )
        comparison = pd.DataFrame(
            [
                {
                    "Mode": mode.replace("_", " ").title(),
                    "Attack detection": values["attack_detection_rate"],
                    "Benign mitigation": values["benign_false_positive_rate"],
                    "Final fidelity": values["final_fidelity"]["mean"],
                }
                for mode, values in validation["mode_overview"].items()
            ]
        )
        st.dataframe(
            comparison.style.format(
                {
                    "Attack detection": "{:.1%}",
                    "Benign mitigation": "{:.1%}",
                    "Final fidelity": "{:.2%}",
                }
            ),
            hide_index=True,
            width="stretch",
        )
        st.warning(
            "Honest limit: Enhanced V2.4 detected 11 of 12 attacks. The missed "
            "run was slow adaptive on holdout seed 1618."
        )
    elif VALIDATION_SUMMARY.exists():
        with VALIDATION_SUMMARY.open(encoding="utf-8") as handle:
            validation = json.load(handle)
        st.subheader("Historical Baseline V1 validation")
        validation_columns = st.columns(4)
        validation_columns[0].metric("Runs", validation["runs"])
        validation_columns[1].metric("Detection rate", f"{validation['detection_rate']:.1%}")
        validation_columns[2].metric(
            "Benign false-positive rate",
            f"{validation['benign_false_positive_rate']:.1%}",
        )
        validation_columns[3].metric(
            "Mean fidelity reduction",
            f"{validation['fidelity_reduction']['mean']:.1%}",
        )
        aggregate_chart = VALIDATION_DIR / "multi_seed_fidelity.png"
        if aggregate_chart.exists():
            st.image(
                str(aggregate_chart),
                caption="Three-seed mean fidelity with one-standard-deviation bands",
            )
        if validation.get("slow_attack_detection_rate") == 0:
            st.warning(
                "Residual gap: the low-rate replay evaded both ModelSentry and the "
                "rate-only baseline. It is reported as a limitation, not a success."
            )

with evidence_tab:
    st.subheader("Risk accumulation and enforcement")
    database = ARTIFACTS / "defended.db"
    if database.exists():
        with sqlite3.connect(database) as connection:
            timeline = pd.read_sql_query(
                """
                SELECT id AS query, risk, confidence, action, allowed, reasons_json
                FROM query_events
                ORDER BY id
                """,
                connection,
            )
        st.line_chart(timeline.set_index("query")[["risk", "confidence"]])
        actions = timeline.loc[timeline["action"].isin(["throttle", "block"])]
        if not actions.empty:
            first_action = actions.iloc[0]
            reasons = json.loads(first_action["reasons_json"])
            st.error(
                f"First mitigation at query {int(first_action['query'])}: "
                + ("; ".join(reasons) if reasons else "persistent multi-signal anomaly")
            )
        st.dataframe(
            timeline.loc[timeline["action"] != "allow"].tail(50),
            hide_index=True,
            width="stretch",
        )
    else:
        st.info("No defended event database is available yet.")

with log_tab:
    database = ARTIFACTS / "defended.db"
    if database.exists():
        with sqlite3.connect(database) as connection:
            events = pd.read_sql_query(
                """
                SELECT id, timestamp, client_id, predicted_class, confidence,
                       risk, action, allowed, reasons_json
                FROM query_events
                ORDER BY id DESC
                LIMIT 250
                """,
                connection,
            )
        st.dataframe(events, hide_index=True, width="stretch")
        st.download_button(
            "Download displayed evidence",
            events.to_csv(index=False),
            file_name="modelsentry_event_evidence.csv",
            mime="text/csv",
        )

st.caption(
    "Information Acquisition Budget is an operational leakage proxy, not a claim "
    "of theoretical mutual information. Results use synthetic traffic against an owned model."
)
