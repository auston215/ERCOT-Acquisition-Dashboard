import html as html_lib
import re
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import date, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

import numpy as np
import pandas as pd
import pydeck as pdk
import streamlit as st


# ============================================================
# PAGE SETUP
# ============================================================
st.set_page_config(
    page_title="ERCOT Acquisition Dashboard",
    page_icon="⚡",
    layout="wide",
)

st.title("⚡ ERCOT Acquisition Dashboard")
st.caption(
    "M&A screening tool for ERCOT solar, battery storage, and operating wind projects"
)


# ============================================================
# SETTINGS
# ============================================================
SELLER_REFRESH_SECONDS = 6 * 60 * 60
SELLER_LOOKBACK_DAYS = 180


# ============================================================
# HELPERS
# ============================================================
def clean_text(value):
    if pd.isna(value):
        return ""
    return str(value).strip()


def has_value(value):
    return clean_text(value) != ""


def owner_key(value):
    return clean_text(value).lower()


def format_date(value):
    if pd.isna(value):
        return "N/A"
    try:
        return pd.to_datetime(value).strftime("%m/%d/%Y")
    except Exception:
        return clean_text(value)


def strip_html(value):
    if value is None:
        return ""
    text = re.sub(r"<[^>]+>", " ", str(value))
    text = html_lib.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def map_ercot_area(value):
    zone = clean_text(value)
    mapping = {
        "Load Zone - North": "ERCOT-N",
        "North Hub": "ERCOT-N",
        "Load Zone - South": "ERCOT-S",
        "South Hub": "ERCOT-S",
        "Load Zone - West": "ERCOT-W",
        "West Hub": "ERCOT-W",
        "Load Zone - Houston": "ERCOT-H",
        "Houston Hub": "ERCOT-H",
        "Panhandle Hub": "Panhandle",
    }
    return mapping.get(zone, zone if zone else "Unknown")


def to_numeric_series(series):
    return pd.to_numeric(series, errors="coerce")


# ============================================================
# SIDEBAR — DATA
# ============================================================
st.sidebar.header("1. Data")
uploaded_file = st.sidebar.file_uploader(
    "Upload latest Orennia CSV",
    type=["csv"],
)
st.sidebar.divider()


# ============================================================
# SIDEBAR — OPPORTUNITY SCORE WEIGHTS
# ============================================================
st.sidebar.header("2. Opportunity Score Weights")

distress_weight = st.sidebar.number_input(
    "Seller Motivation", 0.0, 1.0, 0.35, 0.05, key="distress_weight"
)
development_weight = st.sidebar.number_input(
    "Development Stage", 0.0, 1.0, 0.25, 0.05, key="development_weight"
)
market_weight = st.sidebar.number_input(
    "Market / Revenue", 0.0, 1.0, 0.15, 0.05, key="market_weight"
)
value_weight = st.sidebar.number_input(
    "Acquisition Value", 0.0, 1.0, 0.10, 0.05, key="value_weight"
)
exec_weight = st.sidebar.number_input(
    "Executability", 0.0, 1.0, 0.15, 0.05, key="exec_weight"
)

total_weight = (
    distress_weight
    + development_weight
    + market_weight
    + value_weight
    + exec_weight
)

if abs(total_weight - 1.0) > 0.001:
    st.sidebar.error(
        f"Weights currently total {total_weight:.0%}. They should total 100%."
    )
else:
    st.sidebar.success("Overall Weights = 100%")


# ============================================================
# SIDEBAR — SCORING INPUTS
# ============================================================
st.sidebar.divider()
st.sidebar.header("3. Scoring Inputs")

with st.sidebar.expander("Seller Motivation Points"):
    distress_5 = st.number_input("Discount Potential 5", value=100, key="distress_5")
    distress_4 = st.number_input("Discount Potential 4", value=80, key="distress_4")
    distress_3 = st.number_input("Discount Potential 3", value=60, key="distress_3")
    distress_2 = st.number_input("Discount Potential 2", value=40, key="distress_2")
    distress_1 = st.number_input("Discount Potential 1", value=20, key="distress_1")
    distress_none = st.number_input("No Seller Signal", value=0, key="distress_none")
    confidence_high = st.number_input(
        "High Confidence Multiplier", value=1.00, step=0.05, key="confidence_high"
    )
    confidence_medium = st.number_input(
        "Medium Confidence Multiplier", value=0.90, step=0.05, key="confidence_medium"
    )
    confidence_low = st.number_input(
        "Low Confidence Multiplier", value=0.75, step=0.05, key="confidence_low"
    )

with st.sidebar.expander("Development Stage Points"):
    development_operating = st.number_input(
        "Operating", value=100, key="development_operating"
    )
    development_50 = st.number_input(
        ">50% Construction", value=92, key="development_50"
    )
    development_construction = st.number_input(
        "In Construction", value=85, key="development_construction"
    )
    development_ia = st.number_input(
        "IA Executed", value=75, key="development_ia"
    )
    development_fis_complete = st.number_input(
        "FIS Completed", value=65, key="development_fis_complete"
    )
    development_fis_started = st.number_input(
        "FIS Started", value=55, key="development_fis_started"
    )
    development_studies = st.number_input(
        "Studies Undergoing", value=45, key="development_studies"
    )
    development_pre = st.number_input(
        "Pre-Study", value=35, key="development_pre"
    )
    development_inactive = st.number_input(
        "Inactive / Suspended / Retired", value=15, key="development_inactive"
    )

with st.sidebar.expander("Revenue Visibility Points"):
    market_both = st.number_input(
        "Contract + Named Offtaker", value=95, key="market_both"
    )
    market_offtaker = st.number_input(
        "Named Offtaker Only", value=90, key="market_offtaker"
    )
    market_contract = st.number_input(
        "Contract Only", value=80, key="market_contract"
    )
    market_none = st.number_input(
        "Neither Contract nor Offtaker", value=45, key="market_none"
    )

with st.sidebar.expander("ERCOT Location Points"):
    location_north = st.number_input("ERCOT-N", value=90, key="location_north")
    location_houston = st.number_input("ERCOT-H", value=85, key="location_houston")
    location_south = st.number_input("ERCOT-S", value=70, key="location_south")
    location_west = st.number_input("ERCOT-W", value=60, key="location_west")
    location_panhandle = st.number_input(
        "Panhandle", value=50, key="location_panhandle"
    )
    location_unknown = st.number_input(
        "Unknown / Other", value=50, key="location_unknown"
    )

with st.sidebar.expander("Market / Revenue Mix"):
    revenue_visibility_weight = st.number_input(
        "Revenue Visibility %",
        0.0,
        1.0,
        0.70,
        0.05,
        key="revenue_visibility_weight",
    )
    location_market_weight = st.number_input(
        "ERCOT Location %",
        0.0,
        1.0,
        0.30,
        0.05,
        key="location_market_weight",
    )

market_mix_total = revenue_visibility_weight + location_market_weight
if abs(market_mix_total - 1.0) > 0.001:
    st.sidebar.warning(
        f"Market / Revenue mix totals {market_mix_total:.0%}. It should equal 100%."
    )

with st.sidebar.expander("Acquisition Value Points"):
    value_both = st.number_input(
        "Tax Credit + Energy Community", value=75, key="value_both"
    )
    value_tax = st.number_input("Tax Credit Only", value=70, key="value_tax")
    value_ec = st.number_input("Energy Community Only", value=60, key="value_ec")
    value_none = st.number_input(
        "Neither Tax Credit nor Energy Community", value=55, key="value_none"
    )

with st.sidebar.expander("Timing Points"):
    timing_operating = st.number_input(
        "COD Reached / Passed", value=100, key="timing_operating"
    )
    timing_1 = st.number_input("COD Within 1 Year", value=90, key="timing_1")
    timing_2 = st.number_input("COD Within 2 Years", value=75, key="timing_2")
    timing_3 = st.number_input("COD Within 3 Years", value=60, key="timing_3")
    timing_long = st.number_input("COD >3 Years", value=45, key="timing_long")
    timing_missing = st.number_input("COD Missing", value=50, key="timing_missing")

with st.sidebar.expander("Executability Mix"):
    actionability_weight = st.number_input(
        "Seller Actionability %",
        0.0,
        1.0,
        0.50,
        0.05,
        key="actionability_weight",
    )
    timing_exec_weight = st.number_input(
        "Timing %", 0.0, 1.0, 0.30, 0.05, key="timing_exec_weight"
    )
    development_exec_weight = st.number_input(
        "Development Stage %",
        0.0,
        1.0,
        0.20,
        0.05,
        key="development_exec_weight",
    )

exec_mix_total = actionability_weight + timing_exec_weight + development_exec_weight
if abs(exec_mix_total - 1.0) > 0.001:
    st.sidebar.warning(
        f"Executability mix totals {exec_mix_total:.0%}. It should equal 100%."
    )


# ============================================================
# SCORE MAPPINGS
# ============================================================
discount_score_map = {
    5: distress_5,
    4: distress_4,
    3: distress_3,
    2: distress_2,
    1: distress_1,
}

confidence_score_map = {
    "High": confidence_high,
    "Medium": confidence_medium,
    "Low": confidence_low,
}

actionability_points = {
    5: 100,
    4: 80,
    3: 60,
    2: 40,
    1: 20,
}

location_points = {
    "ERCOT-N": location_north,
    "ERCOT-H": location_houston,
    "ERCOT-S": location_south,
    "ERCOT-W": location_west,
    "Panhandle": location_panhandle,
    "Unknown": location_unknown,
}


def calculate_discount_score(potential, confidence):
    if pd.isna(potential):
        return distress_none
    try:
        potential = int(potential)
    except Exception:
        return distress_none

    base_score = discount_score_map.get(potential, distress_none)
    confidence_multiplier = confidence_score_map.get(
        clean_text(confidence), confidence_low
    )
    return round(base_score * confidence_multiplier, 1)


def actionability_score(value):
    if pd.isna(value):
        return 50
    try:
        value = int(value)
    except Exception:
        return 50
    return actionability_points.get(value, 50)


def location_score(area):
    return location_points.get(clean_text(area), location_unknown)


# ============================================================
# DEFAULT SELLER ASSUMPTIONS
# ============================================================
seller_signals = pd.DataFrame(
    [
        ["Birch Creek Energy", 5, 5, "Medium"],
        ["Birch Creek Development", 5, 5, "Medium"],
        ["esVolta", 4, 5, "High"],
        ["Key Capture Energy", 4, 5, "High"],
        ["Lightsource BP", 3, 4, "High"],
        ["Ørsted U.S. Onshore", 3, 4, "Medium"],
        ["Orsted", 3, 4, "Medium"],
        ["Flatiron Energy", 2, 4, "High"],
        ["Recurrent Energy", 2, 2, "Medium"],
        ["EDF power solutions North America", 1, 1, "High"],
        ["EDF Renewables", 1, 1, "High"],
        ["Greenbacker Renewable Energy Company", 1, 1, "High"],
    ],
    columns=[
        "Owner",
        "Discount Potential",
        "Seller Actionability",
        "Confidence",
    ],
)

if "seller_assumptions" not in st.session_state:
    st.session_state["seller_assumptions"] = seller_signals.copy()


# ============================================================
# TABS
# ============================================================
dashboard_tab, map_tab = st.tabs(
    ["📊 Acquisition Dashboard", "🗺️ Map Explorer"]
)


# ============================================================
# LOAD DATA
#
# The Acquisition Dashboard does NOT require a manual upload.
# If the user uploads a newer Orennia CSV, that file is used for
# the current session. Otherwise, the app automatically loads the
# newest Power Projects-*.csv bundled in the GitHub/Streamlit repo.
# ============================================================
APP_DIR = Path(__file__).resolve().parent

repo_csv_files = sorted(
    APP_DIR.rglob("Power Projects-*.csv"),
    key=lambda path: path.stat().st_mtime,
    reverse=True,
)

if uploaded_file is not None:
    df = pd.read_csv(uploaded_file)
elif repo_csv_files:
    df = pd.read_csv(repo_csv_files[0])
else:
    st.error(
        "The dashboard data file is missing from the app repository. "
        "Add the latest Power Projects-*.csv file beside streamlit_app.py. "
        "The sidebar uploader is optional and should only be used for an ad hoc refresh."
    )
    st.stop()

required_columns = [
    "Power Project Name",
    "Owner",
    "Queue ID",
    "ISO Zone",
    "Power Project Type",
    "Capacity (MW)",
    "First Power Date",
    "Power Project Status",
]

missing_columns = [col for col in required_columns if col not in df.columns]
if missing_columns:
    st.error(
        "The uploaded file is missing these required columns: "
        + ", ".join(missing_columns)
    )
    st.stop()


# ============================================================
# CLEAN DATA
# ============================================================
df["Owner"] = df["Owner"].fillna("")
df["First Power Date"] = pd.to_datetime(df["First Power Date"], errors="coerce")
df["Capacity (MW)"] = pd.to_numeric(df["Capacity (MW)"], errors="coerce")

optional_diligence_columns = [
    "Equipment Manufacturer",
    "Equipment Model",
    "EPC",
    "Integrator",
]
available_diligence_columns = [
    col for col in optional_diligence_columns if col in df.columns
]

optional_interconnection_columns = [
    "Interconnection Service Type",
    "Queue Cycle",
    "Queue Date",
    "Interconnection Cost Physical ($)",
    "Interconnection Cost System Upgrade ($)",
    "Interconnection Cost Total ($)",
]
available_interconnection_columns = [
    col for col in optional_interconnection_columns if col in df.columns
]

optional_contract_columns = [
    "Contract Execution Date",
    "Contract Termination Date",
    "Contract Term Years (Year)",
]
available_contract_columns = [
    col for col in optional_contract_columns if col in df.columns
]


# ============================================================
# ERCOT AREA
# ============================================================
df["ERCOT Area"] = df["ISO Zone"].apply(map_ercot_area)
df["Location Score"] = df["ERCOT Area"].apply(location_score)


# ============================================================
# TECHNOLOGY UNIVERSE
# Solar = all stages
# Storage = all stages
# Wind = Operating only
# ============================================================
df = df[
    df["Power Project Type"].isin(["Solar", "Storage"])
    |
    (
        (df["Power Project Type"] == "Wind")
        & (df["Power Project Status"] == "Operating")
    )
].copy()


# ============================================================
# HARD EXCLUSIONS
# ============================================================
df = df[
    ~df["Owner"].str.contains("Pine Gate", case=False, na=False)
].copy()

excluded_projects = [
    "Texas One",
    "Rio Lago Solar",
    "Grapefruit Solar",
    "Limewood Bell Renewables",
    "Lavender Storage Project",
    "Lavender Solar",
    "Twin Oaks Solar",
    "Magnolia Solar",
    "Mesquite Solar",
]

df = df[~df["Power Project Name"].isin(excluded_projects)].copy()


# ============================================================
# DASHBOARD GUIDE + SELLER ASSUMPTIONS
# ============================================================
with dashboard_tab:
    st.markdown("## 📘 Dashboard Guide")
    guide_left, guide_right = st.columns([1.55, 1])

    with guide_left:
        st.markdown("### 🎯 Opportunity Score")
        st.caption(
            "Projects are scored from 0–100 to prioritize attractive and actionable acquisition opportunities."
        )

        scoring_methodology = pd.DataFrame(
            {
                "Factor": [
                    "Seller Motivation",
                    "Development Stage",
                    "Market / Revenue",
                    "Acquisition Value",
                    "Executability",
                ],
                "Weight": [
                    f"{distress_weight:.0%}",
                    f"{development_weight:.0%}",
                    f"{market_weight:.0%}",
                    f"{value_weight:.0%}",
                    f"{exec_weight:.0%}",
                ],
                "What It Measures": [
                    "Likelihood owner is motivated to transact",
                    "Project maturity and progress through development",
                    "Revenue visibility + ERCOT location",
                    "Tax-credit / siting attributes",
                    "Ability to realistically execute a transaction",
                ],
            }
        )
        st.dataframe(scoring_methodology, use_container_width=True, hide_index=True)

        st.markdown("#### Formula")
        st.markdown(
            f"""
            **Opportunity Score = Seller Motivation × {distress_weight:.0%}
            + Development Stage × {development_weight:.0%}
            + Market / Revenue × {market_weight:.0%}
            + Acquisition Value × {value_weight:.0%}
            + Executability × {exec_weight:.0%}**
            """
        )
        st.caption(
            f"Market / Revenue = Revenue Visibility × {revenue_visibility_weight:.0%} + "
            f"ERCOT Location × {location_market_weight:.0%}."
        )
        st.caption(
            f"Executability = Seller Actionability × {actionability_weight:.0%} + "
            f"Timing × {timing_exec_weight:.0%} + Development Stage × {development_exec_weight:.0%}."
        )

        example_seller = distress_4 * confidence_high
        example_development = development_operating
        example_revenue = market_both
        example_location = location_north
        example_market = (
            example_revenue * revenue_visibility_weight
            + example_location * location_market_weight
        )
        example_value = value_tax
        example_actionability = 100
        example_timing = timing_operating
        example_executability = (
            example_actionability * actionability_weight
            + example_timing * timing_exec_weight
            + example_development * development_exec_weight
        )
        example_final = (
            example_seller * distress_weight
            + example_development * development_weight
            + example_market * market_weight
            + example_value * value_weight
            + example_executability * exec_weight
        )

        st.markdown("#### Example")
        example_background = pd.DataFrame(
            {
                "Factor": [
                    "Seller Motivation",
                    "Development Stage",
                    "Market / Revenue",
                    "Acquisition Value",
                    "Executability",
                ],
                "Score": [
                    example_seller,
                    example_development,
                    example_market,
                    example_value,
                    example_executability,
                ],
                "Why": [
                    "Discount Potential 4 = 80; High Confidence = 100%; 80 × 100% = 80",
                    "Operating project = 100",
                    f"Revenue visibility = {example_revenue:.0f}; ERCOT-N = {example_location:.0f}",
                    "Tax Credit only = 70",
                    (
                        f"Actionability 100 × {actionability_weight:.0%} + "
                        f"Timing 100 × {timing_exec_weight:.0%} + "
                        f"Development Stage 100 × {development_exec_weight:.0%}"
                    ),
                ],
            }
        )
        st.dataframe(example_background, use_container_width=True, hide_index=True)
        st.success(f"Example Opportunity Score = {example_final:.1f}")

    with guide_right:
        st.markdown("### 🧭 How to Use")
        st.markdown(
            """
            **1. Management Shortlist** — Top 5 priorities  
            **2. Top Acquisition Targets** — Top 20 overall  
            **3. By Technology** — Solar, Storage or Wind  
            **4. ERCOT Area** — Compare market location  
            **5. Bundles** — Multiple 50–60 MW assets by owner  
            **6. Score Breakdown** — Drill into a project  
            **7. Map Explorer** — Visualize and filter the ERCOT opportunity set
            """
        )
        st.markdown("### 🚦 Score Guide")
        st.markdown(
            """
            **80+** → Contact / Diligence  
            **70–79** → Investigate  
            **60–69** → Monitor  
            **<60** → Low Priority
            """
        )
        st.markdown("### 🗺️ Location Logic")
        location_guide = pd.DataFrame(
            {
                "Area": ["ERCOT-N", "ERCOT-H", "ERCOT-S", "ERCOT-W", "Panhandle"],
                "Score": [
                    location_north,
                    location_houston,
                    location_south,
                    location_west,
                    location_panhandle,
                ],
            }
        )
        st.dataframe(location_guide, use_container_width=True, hide_index=True)
        st.caption(
            "Location is a broad screening proxy. Node-level congestion, basis, curtailment and market fundamentals can materially differ within each area."
        )

    with st.expander("📐 View Full Score Logic", expanded=False):
        st.markdown("#### Seller Motivation")
        st.caption(
            "Measures the strength of the seller-side reason to transact. The base motivation score is adjusted for confidence."
        )
        st.dataframe(
            pd.DataFrame(
                {
                    "Discount Potential": [
                        "5 – Very High",
                        "4 – High",
                        "3 – Moderate",
                        "2 – Low",
                        "1 – Very Low",
                        "No Signal",
                    ],
                    "Base Score": [
                        distress_5,
                        distress_4,
                        distress_3,
                        distress_2,
                        distress_1,
                        distress_none,
                    ],
                }
            ),
            use_container_width=True,
            hide_index=True,
        )
        st.dataframe(
            pd.DataFrame(
                {
                    "Confidence": ["High", "Medium", "Low"],
                    "Multiplier": [
                        f"{confidence_high:.0%}",
                        f"{confidence_medium:.0%}",
                        f"{confidence_low:.0%}",
                    ],
                }
            ),
            use_container_width=True,
            hide_index=True,
        )

        st.markdown("#### Development Stage")
        st.dataframe(
            pd.DataFrame(
                {
                    "Stage": [
                        "Operating / Construction Complete",
                        ">50% Construction",
                        "In Construction",
                        "IA Executed",
                        "FIS Completed",
                        "FIS Started",
                        "Studies Undergoing / Other",
                        "Pre-Study",
                        "Inactive / Suspended / Retired",
                    ],
                    "Score": [
                        development_operating,
                        development_50,
                        development_construction,
                        development_ia,
                        development_fis_complete,
                        development_fis_started,
                        development_studies,
                        development_pre,
                        development_inactive,
                    ],
                }
            ),
            use_container_width=True,
            hide_index=True,
        )

        st.markdown("#### Market / Revenue")
        st.caption(
            f"Market / Revenue = Revenue Visibility × {revenue_visibility_weight:.0%} + ERCOT Location × {location_market_weight:.0%}."
        )
        st.dataframe(
            pd.DataFrame(
                {
                    "Revenue Visibility": [
                        "Contract + Named Offtaker",
                        "Named Offtaker Only",
                        "Contract Only",
                        "Neither",
                    ],
                    "Score": [
                        market_both,
                        market_offtaker,
                        market_contract,
                        market_none,
                    ],
                }
            ),
            use_container_width=True,
            hide_index=True,
        )
        st.dataframe(
            pd.DataFrame(
                {
                    "ERCOT Area": [
                        "ERCOT-N",
                        "ERCOT-H",
                        "ERCOT-S",
                        "ERCOT-W",
                        "Panhandle",
                        "Unknown / Other",
                    ],
                    "Location Score": [
                        location_north,
                        location_houston,
                        location_south,
                        location_west,
                        location_panhandle,
                        location_unknown,
                    ],
                }
            ),
            use_container_width=True,
            hide_index=True,
        )

        st.markdown("#### Acquisition Value")
        st.dataframe(
            pd.DataFrame(
                {
                    "Attributes": [
                        "Tax Credit + Energy Community",
                        "Tax Credit Only",
                        "Energy Community Only",
                        "Neither",
                    ],
                    "Score": [value_both, value_tax, value_ec, value_none],
                }
            ),
            use_container_width=True,
            hide_index=True,
        )
        st.caption(
            "Domestic Content is not included in the automated score because Orennia does not currently expose project-level Domestic Content qualification or bonus fields. Equipment information can be used as a diligence reference but is not treated as evidence of qualification."
        )

        st.markdown("#### Executability")
        st.caption(
            f"Executability = Seller Actionability × {actionability_weight:.0%} + Timing × {timing_exec_weight:.0%} + Development Stage × {development_exec_weight:.0%}."
        )

    st.caption(
        f"ERCOT Location represents {location_market_weight * market_weight:.1%} of the total Opportunity Score under the current assumptions."
    )
    st.caption(
        "Screening tool only — rankings prioritize sourcing and diligence activity and are not a substitute for full investment underwriting."
    )
    st.divider()

    st.subheader("Seller Motivation / Actionability Assumptions")
    st.caption(
        "These assumptions drive the project rankings. Public seller intelligence below is informational only and does not automatically change project scores."
    )

    current_sellers = st.session_state["seller_assumptions"].copy()
    current_sellers.insert(
        2,
        "Discount Score",
        current_sellers.apply(
            lambda row: calculate_discount_score(
                row["Discount Potential"], row["Confidence"]
            ),
            axis=1,
        ),
    )
    current_sellers.insert(
        4,
        "Actionability Score",
        current_sellers["Seller Actionability"].apply(actionability_score),
    )

    edited_sellers_full = st.data_editor(
        current_sellers,
        use_container_width=True,
        hide_index=True,
        num_rows="dynamic",
        key="seller_assumptions_editor",
        disabled=["Discount Score", "Actionability Score"],
        column_order=[
            "Owner",
            "Discount Potential",
            "Discount Score",
            "Seller Actionability",
            "Actionability Score",
            "Confidence",
        ],
        column_config={
            "Discount Potential": st.column_config.NumberColumn(
                "Discount Potential", min_value=1, max_value=5, step=1, format="%d"
            ),
            "Discount Score": st.column_config.ProgressColumn(
                "Discount Score", min_value=0, max_value=100, format="%.0f"
            ),
            "Seller Actionability": st.column_config.NumberColumn(
                "Seller Actionability", min_value=1, max_value=5, step=1, format="%d"
            ),
            "Actionability Score": st.column_config.ProgressColumn(
                "Actionability Score", min_value=0, max_value=100, format="%.0f"
            ),
            "Confidence": st.column_config.SelectboxColumn(
                "Confidence", options=["High", "Medium", "Low"]
            ),
        },
    )

editable_seller_columns = [
    "Owner",
    "Discount Potential",
    "Seller Actionability",
    "Confidence",
]
new_seller_assumptions = edited_sellers_full[editable_seller_columns].copy()
old_seller_assumptions = st.session_state["seller_assumptions"][
    editable_seller_columns
].copy()

if not new_seller_assumptions.equals(old_seller_assumptions):
    st.session_state["seller_assumptions"] = new_seller_assumptions
    st.rerun()

edited_sellers = st.session_state["seller_assumptions"].copy()
edited_sellers["Owner Key"] = (
    edited_sellers["Owner"].astype(str).str.strip().str.lower()
)
seller_lookup = edited_sellers.set_index("Owner Key").to_dict("index")


# ============================================================
# PUBLIC SELLER INTELLIGENCE — INFORMATIONAL ONLY
# ============================================================
SELLER_SEARCH_TERMS = {
    "Birch Creek Energy": "Birch Creek Energy",
    "Birch Creek Development": "Birch Creek Energy",
    "esVolta": "esVolta",
    "Key Capture Energy": "Key Capture Energy",
    "Lightsource BP": "Lightsource bp",
    "Ørsted U.S. Onshore": "Orsted U.S. Onshore",
    "Orsted": "Orsted U.S. renewables",
    "Flatiron Energy": "Flatiron Energy",
    "Recurrent Energy": "Recurrent Energy",
    "EDF power solutions North America": "EDF power solutions North America",
    "EDF Renewables": "EDF Renewables North America",
    "Greenbacker Renewable Energy Company": "Greenbacker Renewable Energy Company",
}

SELLER_SIGNAL_TERMS = (
    '"strategic review" OR '
    '"strategic alternatives" OR '
    '"asset sale" OR '
    '"portfolio sale" OR '
    '"sale process" OR '
    "divest OR "
    "divestiture OR "
    '"capital recycling" OR '
    "monetization OR "
    '"sell-down" OR '
    '"stake sale" OR '
    "bankruptcy OR "
    "restructuring OR "
    "default OR "
    "distress OR "
    "liquidity OR "
    "layoffs OR "
    '"job cuts" OR '
    '"project cancellation"'
)


@st.cache_data(ttl=SELLER_REFRESH_SECONDS, show_spinner=False)
def fetch_company_news(search_term):
    query = f'"{search_term}" ({SELLER_SIGNAL_TERMS}) when:{SELLER_LOOKBACK_DAYS}d'
    encoded_query = urllib.parse.quote_plus(query)
    url = (
        "https://news.google.com/rss/search?"
        f"q={encoded_query}&hl=en-US&gl=US&ceid=US:en"
    )
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0 ERCOT-Acquisition-Dashboard"},
    )

    articles = []
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            xml_data = response.read()
        root = ET.fromstring(xml_data)

        for item in root.findall(".//item"):
            title = clean_text(item.findtext("title"))
            description = strip_html(item.findtext("description"))
            source = clean_text(item.findtext("source"))
            link = clean_text(item.findtext("link"))
            published_raw = clean_text(item.findtext("pubDate"))
            published = pd.NaT

            if published_raw:
                try:
                    parsed = parsedate_to_datetime(published_raw)
                    if parsed.tzinfo is None:
                        parsed = parsed.replace(tzinfo=timezone.utc)
                    published = pd.Timestamp(parsed)
                except Exception:
                    published = pd.NaT

            articles.append(
                {
                    "Title": title,
                    "Description": description,
                    "Source": source,
                    "Published": published,
                    "URL": link,
                }
            )
    except Exception:
        return []

    return articles


SELLER_SIGNAL_RULES = [
    {
        "Signal Type": "Formal Sale / Strategic Review",
        "Keywords": [
            "strategic review",
            "strategic alternatives",
            "sale process",
            "portfolio sale",
            "asset sale",
            "exploring a sale",
            "divestiture",
        ],
        "Suggested Motivation": 5,
        "Suggested Actionability": 5,
    },
    {
        "Signal Type": "Restructuring / Financial Stress",
        "Keywords": [
            "bankruptcy",
            "chapter 11",
            "restructuring",
            "default",
            "distressed",
            "liquidity crisis",
            "going concern",
        ],
        "Suggested Motivation": 5,
        "Suggested Actionability": 4,
    },
    {
        "Signal Type": "Capital Recycling / Monetization",
        "Keywords": [
            "capital recycling",
            "asset monetization",
            "monetization",
            "sell-down",
            "sell down",
            "stake sale",
        ],
        "Suggested Motivation": 4,
        "Suggested Actionability": 5,
    },
    {
        "Signal Type": "Layoffs / Cost Reduction",
        "Keywords": [
            "layoffs",
            "layoff",
            "job cuts",
            "workforce reduction",
            "headcount reduction",
        ],
        "Suggested Motivation": 4,
        "Suggested Actionability": 3,
    },
    {
        "Signal Type": "Project Cancellation / Portfolio Pressure",
        "Keywords": [
            "project cancellation",
            "project cancellations",
            "cancelled project",
            "canceled project",
            "project impairment",
            "impairment charge",
        ],
        "Suggested Motivation": 4,
        "Suggested Actionability": 3,
    },
]


def classify_article(title, description):
    text = (clean_text(title) + " " + clean_text(description)).lower()
    for rule in SELLER_SIGNAL_RULES:
        for keyword in rule["Keywords"]:
            if keyword.lower() in text:
                return rule
    return None


def build_advisory_seller_intelligence():
    rows = []

    for _, seller in edited_sellers.iterrows():
        owner = seller["Owner"]
        search_term = SELLER_SEARCH_TERMS.get(owner, owner)
        articles = fetch_company_news(search_term)
        classified_articles = []

        for article in articles:
            rule = classify_article(
                article.get("Title"),
                article.get("Description"),
            )
            if rule is None:
                continue
            classified_articles.append(
                {
                    **article,
                    "Signal Type": rule["Signal Type"],
                    "Suggested Motivation": rule["Suggested Motivation"],
                    "Suggested Actionability": rule["Suggested Actionability"],
                }
            )

        if classified_articles:
            def safe_sort_date(article):
                published = article.get("Published")
                if pd.isna(published):
                    return pd.Timestamp.min
                timestamp = pd.Timestamp(published)
                if timestamp.tzinfo is not None:
                    timestamp = timestamp.tz_localize(None)
                return timestamp

            classified_articles = sorted(
                classified_articles,
                key=safe_sort_date,
                reverse=True,
            )
            latest = classified_articles[0]
            rows.append(
                {
                    "Owner": owner,
                    "Current Motivation": seller["Discount Potential"],
                    "Current Actionability": seller["Seller Actionability"],
                    "Suggested Motivation": latest["Suggested Motivation"],
                    "Suggested Actionability": latest["Suggested Actionability"],
                    "Signal Type": latest["Signal Type"],
                    "Signal Date": latest["Published"],
                    "Source": latest["Source"],
                    "Latest Signal": latest["Title"],
                    "Article": latest["URL"],
                }
            )
        else:
            rows.append(
                {
                    "Owner": owner,
                    "Current Motivation": seller["Discount Potential"],
                    "Current Actionability": seller["Seller Actionability"],
                    "Suggested Motivation": np.nan,
                    "Suggested Actionability": np.nan,
                    "Signal Type": "No qualifying recent signal",
                    "Signal Date": pd.NaT,
                    "Source": "",
                    "Latest Signal": "",
                    "Article": "",
                }
            )

    return pd.DataFrame(rows)


with dashboard_tab:
    with st.expander("📡 Public Seller Intelligence — Informational Only", expanded=False):
        st.caption(
            "This feed monitors recent public seller signals and provides a suggested direction for review. It does NOT change the Seller Motivation or Actionability assumptions above and therefore does not automatically alter project rankings."
        )
        refresh_intelligence = st.button("🔄 Refresh Public Signals")
        if refresh_intelligence:
            fetch_company_news.clear()
            st.rerun()

        advisory_intelligence = build_advisory_seller_intelligence()
        st.dataframe(
            advisory_intelligence,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Current Motivation": st.column_config.NumberColumn(
                    "Current Motivation", format="%.0f"
                ),
                "Current Actionability": st.column_config.NumberColumn(
                    "Current Actionability", format="%.0f"
                ),
                "Suggested Motivation": st.column_config.NumberColumn(
                    "Suggested Motivation", format="%.0f"
                ),
                "Suggested Actionability": st.column_config.NumberColumn(
                    "Suggested Actionability", format="%.0f"
                ),
                "Signal Date": st.column_config.DateColumn("Signal Date"),
                "Article": st.column_config.LinkColumn("Article"),
            },
        )
    st.divider()


# ============================================================
# MAP SELLER ASSUMPTIONS TO PROJECTS
# ============================================================
def get_seller_value(owner, column):
    key = owner_key(owner)
    if key in seller_lookup:
        return seller_lookup[key].get(column)
    return np.nan


df["Discount Potential"] = df["Owner"].apply(
    lambda x: get_seller_value(x, "Discount Potential")
)
df["Seller Actionability"] = df["Owner"].apply(
    lambda x: get_seller_value(x, "Seller Actionability")
)
df["Seller Confidence"] = df["Owner"].apply(
    lambda x: get_seller_value(x, "Confidence")
)


# ============================================================
# SELLER MOTIVATION SCORE
# ============================================================
df["Distress Score"] = df.apply(
    lambda row: calculate_discount_score(
        row["Discount Potential"],
        row["Seller Confidence"],
    ),
    axis=1,
)


# ============================================================
# DEVELOPMENT STAGE SCORE
# ============================================================
def development_stage_score(row):
    status = clean_text(row.get("Power Project Status"))
    detailed = clean_text(row.get("Detailed Status"))

    if status == "Operating" or detailed == "Construction Complete":
        return development_operating
    if "More Than 50%" in detailed or ">50%" in detailed:
        return development_50
    if status == "In Construction":
        return development_construction
    if status == "IA Executed" or ", IA" in detailed:
        return development_ia
    if "FIS Completed" in detailed:
        return development_fis_complete
    if "FIS Started" in detailed:
        return development_fis_started
    if status == "Pre-Study":
        return development_pre
    if status in ["Inactive", "Suspended", "Retired"]:
        return development_inactive
    return development_studies


df["Development Stage"] = df.apply(development_stage_score, axis=1)


# ============================================================
# REVENUE VISIBILITY
# ============================================================
def revenue_visibility_score(row):
    contract = has_value(row.get("Contract Type"))
    offtaker = has_value(row.get("Contract Offtaker"))

    if contract and offtaker:
        return market_both
    if offtaker:
        return market_offtaker
    if contract:
        return market_contract
    return market_none


df["Revenue Visibility"] = df.apply(revenue_visibility_score, axis=1)


# ============================================================
# MARKET / REVENUE
# ============================================================
df["Market / Revenue"] = (
    df["Revenue Visibility"] * revenue_visibility_weight
    + df["Location Score"] * location_market_weight
)


# ============================================================
# ENERGY COMMUNITY / LOCATION-BASED BONUS SCREEN
# Existing logic preserved for ranking consistency.
# ============================================================
energy_columns = [
    "Fossil Fuel Energy Communities",
    "Retired Coal Facilities Energy Communities",
    "Low Income Communities",
    "Native American Lands",
]


def energy_community(row):
    for col in energy_columns:
        if col not in row.index:
            continue
        value = clean_text(row[col]).lower()
        if value in ["true", "yes", "1"]:
            return "Yes"
    return "No"


df["Energy Community"] = df.apply(energy_community, axis=1)


# ============================================================
# ACQUISITION VALUE
# Existing 75 / 70 / 60 / 55 scoring preserved.
# Domestic Content is not inferred or scored.
# ============================================================
def acquisition_value(row):
    tax_credit = has_value(row.get("PTC/ITC"))
    ec = row["Energy Community"] == "Yes"

    if tax_credit and ec:
        return value_both
    if tax_credit:
        return value_tax
    if ec:
        return value_ec
    return value_none


df["Acquisition Value"] = df.apply(acquisition_value, axis=1)
df["Domestic Content Review"] = "Unknown / Diligence Required"


# ============================================================
# TIMING SCORE
# ============================================================
as_of_date = pd.Timestamp(date.today())


def timing_score(row):
    cod = row["First Power Date"]
    if pd.isna(cod):
        return timing_missing

    days = (cod - as_of_date).days
    if days <= 0:
        return timing_operating
    if days <= 365:
        return timing_1
    if days <= 730:
        return timing_2
    if days <= 1095:
        return timing_3
    return timing_long


df["Timing Score"] = df.apply(timing_score, axis=1)
df["Actionability Score"] = df["Seller Actionability"].apply(actionability_score)


# ============================================================
# EXECUTABILITY
# ============================================================
df["Executability"] = (
    df["Actionability Score"] * actionability_weight
    + df["Timing Score"] * timing_exec_weight
    + df["Development Stage"] * development_exec_weight
)


# ============================================================
# DATA COMPLETENESS
# ============================================================
def completeness(row):
    score = 0
    if has_value(row.get("Owner")):
        score += 40
    if has_value(row.get("Queue ID")):
        score += 15
    if not pd.isna(row.get("First Power Date")):
        score += 15
    if has_value(row.get("Contract Type")) or has_value(row.get("Contract Offtaker")):
        score += 15
    if has_value(row.get("PTC/ITC")):
        score += 15
    return score


df["Data Completeness"] = df.apply(completeness, axis=1)


# ============================================================
# OPPORTUNITY SCORE
# ============================================================
df["Opportunity Score"] = (
    df["Distress Score"] * distress_weight
    + df["Development Stage"] * development_weight
    + df["Market / Revenue"] * market_weight
    + df["Acquisition Value"] * value_weight
    + df["Executability"] * exec_weight
).round(2)


# ============================================================
# ACTION
# ============================================================
def action(row):
    if pd.isna(row["Discount Potential"]):
        return "RESEARCH / MONITOR"

    score = row["Opportunity Score"]
    if score >= 80:
        return "CONTACT / DILIGENCE"
    if score >= 70:
        return "INVESTIGATE"
    if score >= 60:
        return "MONITOR"
    return "LOW PRIORITY"


df["Action"] = df.apply(action, axis=1)


# ============================================================
# RANK
# ============================================================
df = df.sort_values(
    by=["Opportunity Score", "Data Completeness", "Capacity (MW)"],
    ascending=[False, False, False],
).reset_index(drop=True)
df["Rank"] = np.arange(1, len(df) + 1)


# ============================================================
# MANAGEMENT EXPLANATION
# ============================================================
def why_it_ranks(row):
    reasons = []

    if row["Distress Score"] >= 70:
        reasons.append("Strong seller motivation / transaction angle")
    elif row["Distress Score"] >= 50:
        reasons.append("Credible seller opportunity")

    if row["Development Stage"] >= 95:
        reasons.append("Operating / highly mature project")
    elif row["Development Stage"] >= 80:
        reasons.append("Advanced development stage")

    if row["Revenue Visibility"] >= 90:
        reasons.append("Strong revenue / offtaker visibility")
    elif row["Revenue Visibility"] >= 80:
        reasons.append("Some contracted visibility")

    if row["Location Score"] >= 85:
        reasons.append("Attractive ERCOT market location")

    if row["Acquisition Value"] >= 70:
        reasons.append("Attractive tax-credit / siting attributes")

    if row["Executability"] >= 80:
        reasons.append("High execution readiness")

    capacity = row.get("Capacity (MW)", np.nan)
    if not pd.isna(capacity) and capacity >= 100:
        reasons.append(f"{capacity:,.0f} MW scale")

    if not reasons:
        reasons.append("Strong composite Opportunity Score")

    return "; ".join(reasons[:3])


def key_risk(row):
    risks = []

    if pd.isna(row["Discount Potential"]):
        risks.append("Seller motivation not yet verified")
    elif row["Distress Score"] < 50:
        risks.append("Limited evidence of seller pressure")

    if row["Development Stage"] < 55:
        risks.append("Early-stage development risk")
    elif row["Development Stage"] < 75:
        risks.append("Development risk remains")

    if row["Revenue Visibility"] <= 45:
        risks.append("Limited visible revenue certainty")
    elif row["Revenue Visibility"] < 90:
        risks.append("Revenue / offtaker visibility is incomplete")

    if row["Location Score"] <= 50:
        risks.append("Lower broad-area location score; node may differ")

    if pd.isna(row["First Power Date"]):
        risks.append("COD timing unclear")

    if row["Data Completeness"] < 70:
        risks.append("Material diligence data gaps")

    if not risks:
        risks.append("No major screen-level issue; full diligence still required")

    return "; ".join(risks[:2])


df["Why It Ranks"] = df.apply(why_it_ranks, axis=1)
df["Key Risk"] = df.apply(key_risk, axis=1)
df["Recommended Action"] = df["Action"]


# ============================================================
# ACQUISITION DASHBOARD TAB
# ============================================================
with dashboard_tab:
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Projects Screened", f"{len(df):,}")
    c2.metric("Total Capacity", f"{df['Capacity (MW)'].sum():,.0f} MW")
    c3.metric(
        "Contact / Diligence",
        int((df["Action"] == "CONTACT / DILIGENCE").sum()),
    )
    c4.metric("Top Score", f"{df['Opportunity Score'].max():.1f}")

    # --------------------------------------------------------
    # MANAGEMENT SHORTLIST
    # --------------------------------------------------------
    st.divider()
    st.subheader("🎯 Management Shortlist")
    st.caption(
        "Top five current acquisition priorities based on the screening model."
    )

    management_shortlist = df.head(5).copy()
    management_shortlist["Management Rank"] = np.arange(
        1, len(management_shortlist) + 1
    )

    management_columns = [
        "Management Rank",
        "Power Project Name",
        "Owner",
        "Power Project Type",
        "ERCOT Area",
        "Location Score",
        "Capacity (MW)",
        "Power Project Status",
        "Opportunity Score",
        "Why It Ranks",
        "Key Risk",
        "Recommended Action",
    ]
    management_columns = [
        col for col in management_columns if col in management_shortlist.columns
    ]

    st.dataframe(
        management_shortlist[management_columns],
        use_container_width=True,
        hide_index=True,
        column_config={
            "Management Rank": st.column_config.NumberColumn("Rank"),
            "Power Project Type": st.column_config.TextColumn("Tech"),
            "Capacity (MW)": st.column_config.NumberColumn("MW", format="%.1f"),
            "Location Score": st.column_config.NumberColumn(
                "Location", format="%.0f"
            ),
            "Opportunity Score": st.column_config.ProgressColumn(
                "Score", min_value=0, max_value=100, format="%.1f"
            ),
            "Recommended Action": st.column_config.TextColumn("Action"),
        },
    )

    # --------------------------------------------------------
    # GLOBAL FILTERS
    # --------------------------------------------------------
    st.divider()
    st.subheader("Filters")

    f1, f2, f3, f4 = st.columns(4)
    technology_options = sorted(df["Power Project Type"].dropna().unique())
    selected_technology = f1.multiselect(
        "Technology", technology_options, default=technology_options
    )

    ercot_area_options = sorted(df["ERCOT Area"].dropna().unique())
    selected_ercot_areas = f2.multiselect(
        "ERCOT Area", ercot_area_options, default=ercot_area_options
    )

    owner_options = sorted(
        [owner for owner in df["Owner"].unique() if clean_text(owner)]
    )
    selected_owners = f3.multiselect("Owner", owner_options)

    status_options = sorted(df["Power Project Status"].dropna().unique())
    selected_status = f4.multiselect(
        "Project Status", status_options, default=status_options
    )

    filtered = df[df["Power Project Type"].isin(selected_technology)].copy()
    filtered = filtered[filtered["ERCOT Area"].isin(selected_ercot_areas)]
    filtered = filtered[filtered["Power Project Status"].isin(selected_status)]
    if selected_owners:
        filtered = filtered[filtered["Owner"].isin(selected_owners)]

    # --------------------------------------------------------
    # TOP ACQUISITION TARGETS
    # --------------------------------------------------------
    st.divider()
    st.subheader("🏆 Top Acquisition Targets")
    st.caption("Top 20 projects based on Opportunity Score.")

    display_columns = [
        "Rank",
        "Power Project Name",
        "Owner",
        "Power Project Type",
        "ERCOT Area",
        "ISO Zone",
        "Location Score",
        "Capacity (MW)",
        "Power Project Status",
        "First Power Date",
        "Contract Type",
        "Contract Offtaker",
        "Distress Score",
        "Development Stage",
        "Revenue Visibility",
        "Market / Revenue",
        "Acquisition Value",
        "Executability",
        "Opportunity Score",
        "Action",
    ]
    existing_display_columns = [
        col for col in display_columns if col in filtered.columns
    ]

    st.dataframe(
        filtered[existing_display_columns].head(20),
        use_container_width=True,
        hide_index=True,
        column_config={
            "Distress Score": st.column_config.NumberColumn("Seller Motivation"),
            "Development Stage": st.column_config.NumberColumn(
                "Development Stage", format="%.1f"
            ),
            "Revenue Visibility": st.column_config.NumberColumn(
                "Revenue Visibility", format="%.1f"
            ),
            "Location Score": st.column_config.NumberColumn(
                "Location", format="%.0f"
            ),
            "Market / Revenue": st.column_config.NumberColumn(
                "Market / Revenue", format="%.1f"
            ),
            "Opportunity Score": st.column_config.ProgressColumn(
                "Opportunity Score", min_value=0, max_value=100, format="%.1f"
            ),
            "First Power Date": st.column_config.DateColumn("COD"),
        },
    )

    # --------------------------------------------------------
    # TOP PROJECTS BY TECHNOLOGY
    # --------------------------------------------------------
    st.divider()
    st.subheader("⚡ Top Projects by Technology")

    tech_options = sorted(df["Power Project Type"].dropna().unique())
    selected_tech_rank = st.selectbox(
        "Select Technology", tech_options, key="technology_ranking"
    )

    technology_ranked = df[
        df["Power Project Type"] == selected_tech_rank
    ].copy()
    technology_ranked = technology_ranked.sort_values(
        by=["Opportunity Score", "Data Completeness", "Capacity (MW)"],
        ascending=[False, False, False],
    ).reset_index(drop=True)
    technology_ranked["Technology Rank"] = np.arange(
        1, len(technology_ranked) + 1
    )
    technology_top_20 = technology_ranked.head(20)

    tech_columns = [
        "Technology Rank",
        "Power Project Name",
        "Owner",
        "ERCOT Area",
        "Location Score",
        "Capacity (MW)",
        "Power Project Status",
        "First Power Date",
        "Contract Type",
        "Contract Offtaker",
        "Distress Score",
        "Development Stage",
        "Revenue Visibility",
        "Market / Revenue",
        "Acquisition Value",
        "Executability",
        "Opportunity Score",
        "Action",
    ]
    tech_columns = [
        col for col in tech_columns if col in technology_top_20.columns
    ]

    t1, t2, t3 = st.columns(3)
    t1.metric(f"{selected_tech_rank} Projects", len(technology_ranked))
    t2.metric(
        f"{selected_tech_rank} Capacity",
        f"{technology_ranked['Capacity (MW)'].sum():,.0f} MW",
    )
    if len(technology_ranked) > 0:
        t3.metric(
            "Top Technology Score",
            f"{technology_ranked['Opportunity Score'].max():.1f}",
        )

    st.dataframe(
        technology_top_20[tech_columns],
        use_container_width=True,
        hide_index=True,
        column_config={
            "Technology Rank": st.column_config.NumberColumn("Rank"),
            "Distress Score": st.column_config.NumberColumn("Seller Motivation"),
            "Development Stage": st.column_config.NumberColumn(
                "Development Stage", format="%.1f"
            ),
            "Location Score": st.column_config.NumberColumn(
                "Location", format="%.0f"
            ),
            "Revenue Visibility": st.column_config.NumberColumn(
                "Revenue Visibility", format="%.1f"
            ),
            "Market / Revenue": st.column_config.NumberColumn(
                "Market / Revenue", format="%.1f"
            ),
            "First Power Date": st.column_config.DateColumn("COD"),
            "Opportunity Score": st.column_config.ProgressColumn(
                "Opportunity Score", min_value=0, max_value=100, format="%.1f"
            ),
        },
    )

    # --------------------------------------------------------
    # ERCOT AREA SUMMARY
    # --------------------------------------------------------
    st.divider()
    st.subheader("🗺️ ERCOT Area Summary")
    st.caption(
        "Broad market-location screen by ERCOT area. "
        "Location affects 30% of Market / Revenue and currently "
        f"{location_market_weight * market_weight:.1%} of the total Opportunity Score."
    )

    area_summary = (
        df.groupby("ERCOT Area", as_index=False)
        .agg(
            Projects=("Power Project Name", "count"),
            MW=("Capacity (MW)", "sum"),
            Location_Score=("Location Score", "mean"),
            Average_Score=("Opportunity Score", "mean"),
            Best_Score=("Opportunity Score", "max"),
        )
        .sort_values(
            by=["Location_Score", "Average_Score"],
            ascending=[False, False],
        )
    )
    area_summary_display = area_summary.rename(
        columns={
            "Location_Score": "Location Score",
            "Average_Score": "Average Score",
            "Best_Score": "Best Score",
        }
    )

    st.dataframe(
        area_summary_display,
        use_container_width=True,
        hide_index=True,
        column_config={
            "MW": st.column_config.NumberColumn("MW", format="%.0f"),
            "Location Score": st.column_config.ProgressColumn(
                "Location Score", min_value=0, max_value=100, format="%.0f"
            ),
            "Average Score": st.column_config.NumberColumn(
                "Average Score", format="%.1f"
            ),
            "Best Score": st.column_config.NumberColumn(
                "Best Score", format="%.1f"
            ),
        },
    )

    # --------------------------------------------------------
    # BUNDLE OPPORTUNITIES
    # --------------------------------------------------------
    st.divider()
    st.subheader("📦 Bundle Opportunities")
    st.caption(
        "Owners with at least two 50–60 MW projects. Bundles are ranked by average Opportunity Score."
    )

    bundle_candidates = df[
        df["Capacity (MW)"].between(50, 60, inclusive="both")
    ].copy()
    bundle_summary = (
        bundle_candidates.groupby("Owner", as_index=False)
        .agg(
            Bundle_Projects=("Power Project Name", "count"),
            Bundle_MW=("Capacity (MW)", "sum"),
            Average_Score=("Opportunity Score", "mean"),
            Best_Score=("Opportunity Score", "max"),
        )
    )
    bundle_summary = bundle_summary[
        bundle_summary["Bundle_Projects"] >= 2
    ].copy()
    bundle_summary = bundle_summary.sort_values(
        by=["Average_Score", "Best_Score", "Bundle_MW"],
        ascending=[False, False, False],
    ).reset_index(drop=True)
    bundle_summary.insert(0, "Bundle Rank", np.arange(1, len(bundle_summary) + 1))

    if bundle_summary.empty:
        st.info("No owners currently have multiple 50–60 MW projects.")
    else:
        bundle_summary_display = bundle_summary.rename(
            columns={
                "Bundle_Projects": "Projects",
                "Bundle_MW": "Total MW",
                "Average_Score": "Average Score",
                "Best_Score": "Best Score",
            }
        )
        st.dataframe(
            bundle_summary_display,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Bundle Rank": st.column_config.NumberColumn("Rank"),
                "Average Score": st.column_config.ProgressColumn(
                    "Average Score", min_value=0, max_value=100, format="%.1f"
                ),
                "Best Score": st.column_config.ProgressColumn(
                    "Best Score", min_value=0, max_value=100, format="%.1f"
                ),
                "Total MW": st.column_config.NumberColumn(
                    "Total MW", format="%.1f MW"
                ),
            },
        )

        for _, bundle in bundle_summary.iterrows():
            bundle_owner = bundle["Owner"]
            owner_projects = bundle_candidates[
                bundle_candidates["Owner"] == bundle_owner
            ].sort_values("Opportunity Score", ascending=False)

            with st.expander(
                f"#{int(bundle['Bundle Rank'])} 📦 {bundle_owner} — "
                f"{int(bundle['Bundle_Projects'])} projects | "
                f"{bundle['Bundle_MW']:,.1f} MW | "
                f"Avg Score {bundle['Average_Score']:.1f}"
            ):
                bundle_columns = [
                    "Power Project Name",
                    "ERCOT Area",
                    "ISO Zone",
                    "Location Score",
                    "Capacity (MW)",
                    "Power Project Type",
                    "Power Project Status",
                    "First Power Date",
                    "Queue ID",
                    "Contract Type",
                    "Contract Offtaker",
                    "Distress Score",
                    "Development Stage",
                    "Revenue Visibility",
                    "Market / Revenue",
                    "Acquisition Value",
                    "Executability",
                    "Opportunity Score",
                    "Action",
                ]
                bundle_columns = [
                    col for col in bundle_columns if col in owner_projects.columns
                ]
                st.dataframe(
                    owner_projects[bundle_columns],
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        "Distress Score": st.column_config.NumberColumn(
                            "Seller Motivation"
                        ),
                        "Development Stage": st.column_config.NumberColumn(
                            "Development Stage", format="%.1f"
                        ),
                        "Location Score": st.column_config.NumberColumn(
                            "Location", format="%.0f"
                        ),
                        "First Power Date": st.column_config.DateColumn("COD"),
                        "Opportunity Score": st.column_config.ProgressColumn(
                            "Opportunity Score",
                            min_value=0,
                            max_value=100,
                            format="%.1f",
                        ),
                    },
                )

    # --------------------------------------------------------
    # SCORE BREAKDOWN
    # --------------------------------------------------------
    st.divider()
    st.subheader("🔎 Score Breakdown")

    if len(filtered) > 0:
        selected_project = st.selectbox(
            "Select a Project",
            filtered["Power Project Name"].tolist(),
            key="score_breakdown_project",
        )
        project = filtered[
            filtered["Power Project Name"] == selected_project
        ].iloc[0]

        p1, p2, p3, p4, p5 = st.columns(5)
        p1.metric("ERCOT Area", project["ERCOT Area"])
        p2.metric("Location Score", f"{project['Location Score']:.0f}")
        p3.metric("COD", format_date(project.get("First Power Date")))
        p4.metric("Capacity", f"{project['Capacity (MW)']:,.1f} MW")
        p5.metric("Status", clean_text(project.get("Power Project Status")))

        st.caption(f"ISO Zone: {clean_text(project.get('ISO Zone'))}")
        if has_value(project.get("Point of Interconnection")):
            st.caption(
                f"Point of Interconnection: {project['Point of Interconnection']}"
            )

        st.markdown("#### Market / Revenue")
        m1, m2, m3 = st.columns(3)
        m1.metric("Revenue Visibility", f"{project['Revenue Visibility']:.1f}")
        m2.metric("Location Score", f"{project['Location Score']:.1f}")
        m3.metric("Market / Revenue Score", f"{project['Market / Revenue']:.1f}")
        st.caption(
            f"Market / Revenue = {project['Revenue Visibility']:.1f} × {revenue_visibility_weight:.0%} + "
            f"{project['Location Score']:.1f} × {location_market_weight:.0%} = {project['Market / Revenue']:.1f}"
        )

        st.markdown("#### Opportunity Score")
        s1, s2, s3, s4, s5 = st.columns(5)
        s1.metric("Seller Motivation", f"{project['Distress Score']:.1f}")
        s2.metric("Development Stage", f"{project['Development Stage']:.1f}")
        s3.metric("Market / Revenue", f"{project['Market / Revenue']:.1f}")
        s4.metric("Acquisition Value", f"{project['Acquisition Value']:.1f}")
        s5.metric("Executability", f"{project['Executability']:.1f}")
        st.metric("Total Opportunity Score", f"{project['Opportunity Score']:.2f}")

        st.markdown("#### Executability Detail")
        e1, e2, e3, e4 = st.columns(4)
        e1.metric("Seller Actionability", f"{project['Actionability Score']:.1f}")
        e2.metric("Timing Score", f"{project['Timing Score']:.1f}")
        e3.metric("Development Stage", f"{project['Development Stage']:.1f}")
        e4.metric("Executability", f"{project['Executability']:.1f}")
        st.caption(
            f"Executability = {project['Actionability Score']:.1f} × {actionability_weight:.0%} + "
            f"{project['Timing Score']:.1f} × {timing_exec_weight:.0%} + "
            f"{project['Development Stage']:.1f} × {development_exec_weight:.0%} = {project['Executability']:.1f}"
        )

        st.markdown("#### Tax Credit Review")
        tax1, tax2, tax3 = st.columns(3)
        tax1.metric(
            "PTC / ITC",
            clean_text(project.get("PTC/ITC")) or "Not Identified",
        )
        tax2.metric("Energy Community Screen", project["Energy Community"])
        tax3.metric("Domestic Content", project["Domestic Content Review"])
        st.caption(
            "Domestic Content is not automatically scored. Orennia does not currently provide a native project-level Domestic Content qualification field, so qualification requires project-specific diligence."
        )

        if available_diligence_columns:
            with st.expander("🏗️ Equipment / EPC Diligence", expanded=False):
                diligence_data = {
                    col: clean_text(project.get(col)) or "N/A"
                    for col in available_diligence_columns
                }
                st.dataframe(
                    pd.DataFrame(
                        {
                            "Field": list(diligence_data.keys()),
                            "Value": list(diligence_data.values()),
                        }
                    ),
                    use_container_width=True,
                    hide_index=True,
                )
                st.caption(
                    "Equipment manufacturer, model, EPC and integrator data may help prioritize Domestic Content diligence but are not treated as proof of Domestic Content qualification."
                )

        if available_interconnection_columns:
            with st.expander("🔌 Interconnection Snapshot", expanded=False):
                ix_fields = [
                    "Queue ID",
                    "Point of Interconnection",
                    *available_interconnection_columns,
                ]
                ix_fields = [col for col in ix_fields if col in project.index]
                ix_data = {
                    col: clean_text(project.get(col)) or "N/A" for col in ix_fields
                }
                st.dataframe(
                    pd.DataFrame(
                        {
                            "Field": list(ix_data.keys()),
                            "Value": list(ix_data.values()),
                        }
                    ),
                    use_container_width=True,
                    hide_index=True,
                )

        st.markdown("#### Management Readout")
        r1, r2 = st.columns(2)
        r1.info(f"**Why it ranks:**\n\n{project['Why It Ranks']}")
        r2.warning(f"**Key risk:**\n\n{project['Key Risk']}")

    # --------------------------------------------------------
    # OWNER OPPORTUNITY SUMMARY
    # --------------------------------------------------------
    st.divider()
    st.subheader("Owner Opportunity Summary")

    owner_summary = (
        df.groupby("Owner", as_index=False)
        .agg(
            Projects=("Power Project Name", "count"),
            MW=("Capacity (MW)", "sum"),
            Average_Score=("Opportunity Score", "mean"),
            Best_Score=("Opportunity Score", "max"),
        )
        .sort_values(
            by=["Best_Score", "Average_Score"],
            ascending=[False, False],
        )
    )
    owner_summary_display = owner_summary.rename(
        columns={
            "Average_Score": "Average Score",
            "Best_Score": "Best Score",
        }
    )

    st.dataframe(
        owner_summary_display.head(25),
        use_container_width=True,
        hide_index=True,
        column_config={
            "Average Score": st.column_config.NumberColumn(
                "Average Score", format="%.1f"
            ),
            "Best Score": st.column_config.ProgressColumn(
                "Best Score", min_value=0, max_value=100, format="%.1f"
            ),
        },
    )

    # --------------------------------------------------------
    # DOWNLOAD
    # --------------------------------------------------------
    st.divider()
    csv = df.to_csv(index=False).encode("utf-8")
    st.download_button(
        "⬇️ Download Scored ERCOT Universe",
        data=csv,
        file_name="ERCOT_Scored_Acquisition_Universe.csv",
        mime="text/csv",
    )


# ============================================================
# MAP EXPLORER TAB
# ============================================================
with map_tab:
    st.markdown("## 🗺️ ERCOT Map Explorer")
    st.caption(
        "Interactive geographic view of the scored ERCOT acquisition universe. Filters in this tab are independent from the main dashboard filters."
    )

    lat_col = "Latitude (Degrees)" if "Latitude (Degrees)" in df.columns else None
    lon_col = "Longitude (Degrees)" if "Longitude (Degrees)" in df.columns else None

    if lat_col is None or lon_col is None:
        st.error(
            "The uploaded Orennia file does not contain Latitude (Degrees) and Longitude (Degrees), so the map cannot be rendered."
        )
    else:
        map_base = df.copy()
        map_base["Map Latitude"] = to_numeric_series(map_base[lat_col])
        map_base["Map Longitude"] = to_numeric_series(map_base[lon_col])
        map_base = map_base.dropna(subset=["Map Latitude", "Map Longitude"])

        if map_base.empty:
            st.warning("No valid project coordinates are available in the uploaded file.")
        else:
            st.markdown("### Filters")

            mf1, mf2, mf3, mf4 = st.columns(4)

            map_tech_options = sorted(map_base["Power Project Type"].dropna().unique())
            map_tech = mf1.multiselect(
                "Technology",
                map_tech_options,
                default=map_tech_options,
                key="map_technology",
            )

            map_area_options = sorted(map_base["ERCOT Area"].dropna().unique())
            map_area = mf2.multiselect(
                "ERCOT Area",
                map_area_options,
                default=map_area_options,
                key="map_ercot_area",
            )

            map_owner_options = sorted(
                [owner for owner in map_base["Owner"].unique() if clean_text(owner)]
            )
            map_owners = mf3.multiselect(
                "Owner",
                map_owner_options,
                key="map_owner",
            )

            map_status_options = sorted(
                map_base["Power Project Status"].dropna().unique()
            )
            map_status = mf4.multiselect(
                "Project Status",
                map_status_options,
                default=map_status_options,
                key="map_status",
            )

            mf5, mf6, mf7, mf8 = st.columns(4)

            map_action_options = [
                "CONTACT / DILIGENCE",
                "INVESTIGATE",
                "MONITOR",
                "RESEARCH / MONITOR",
                "LOW PRIORITY",
            ]
            present_actions = [
                x for x in map_action_options if x in map_base["Action"].unique()
            ]
            map_actions = mf5.multiselect(
                "Action",
                present_actions,
                default=present_actions,
                key="map_action",
            )

            if "Location Source" in map_base.columns:
                map_location_source_options = sorted(
                    map_base["Location Source"].fillna("Unknown").astype(str).unique()
                )
                map_location_sources = mf6.multiselect(
                    "Location Source",
                    map_location_source_options,
                    default=map_location_source_options,
                    key="map_location_source",
                )
            else:
                map_location_sources = []
                mf6.caption("Location Source not available")

            if "County" in map_base.columns:
                map_county_options = sorted(
                    [
                        county
                        for county in map_base["County"].fillna("").astype(str).unique()
                        if clean_text(county)
                    ]
                )
                map_counties = mf7.multiselect(
                    "County",
                    map_county_options,
                    key="map_county",
                )
            else:
                map_counties = []
                mf7.caption("County not available")

            tax_values = (
                map_base["PTC/ITC"]
                .fillna("Not Identified")
                .replace("", "Not Identified")
                .astype(str)
            ) if "PTC/ITC" in map_base.columns else pd.Series(["Not Identified"] * len(map_base))
            map_base["Tax Credit Label"] = tax_values.values
            map_tax_options = sorted(map_base["Tax Credit Label"].unique())
            map_tax = mf8.multiselect(
                "Tax Credit",
                map_tax_options,
                default=map_tax_options,
                key="map_tax_credit",
            )

            mf9, mf10, mf11 = st.columns([1, 1.4, 1.4])

            min_score = float(np.floor(map_base["Opportunity Score"].min()))
            max_score = float(np.ceil(map_base["Opportunity Score"].max()))
            map_min_score = mf9.slider(
                "Minimum Opportunity Score",
                min_value=0.0,
                max_value=100.0,
                value=max(0.0, min_score),
                step=1.0,
                key="map_min_score",
            )

            cap_min = float(np.floor(map_base["Capacity (MW)"].min()))
            cap_max = float(np.ceil(map_base["Capacity (MW)"].max()))
            map_capacity_range = mf10.slider(
                "Capacity Range (MW)",
                min_value=cap_min,
                max_value=cap_max,
                value=(cap_min, cap_max),
                step=1.0,
                key="map_capacity_range",
            )

            valid_cod = map_base["First Power Date"].dropna()
            if not valid_cod.empty:
                cod_min = valid_cod.min().date()
                cod_max = valid_cod.max().date()
                map_cod_range = mf11.date_input(
                    "COD Range",
                    value=(cod_min, cod_max),
                    min_value=cod_min,
                    max_value=cod_max,
                    key="map_cod_range",
                )
            else:
                map_cod_range = None
                mf11.caption("COD dates not available")

            include_missing_cod = st.checkbox(
                "Include projects with missing COD",
                value=True,
                key="map_include_missing_cod",
            )

            map_filtered = map_base[
                map_base["Power Project Type"].isin(map_tech)
                & map_base["ERCOT Area"].isin(map_area)
                & map_base["Power Project Status"].isin(map_status)
                & map_base["Action"].isin(map_actions)
                & map_base["Tax Credit Label"].isin(map_tax)
                & (map_base["Opportunity Score"] >= map_min_score)
                & map_base["Capacity (MW)"].between(
                    map_capacity_range[0],
                    map_capacity_range[1],
                    inclusive="both",
                )
            ].copy()

            if map_owners:
                map_filtered = map_filtered[map_filtered["Owner"].isin(map_owners)]

            if "Location Source" in map_filtered.columns and map_location_sources:
                map_filtered = map_filtered[
                    map_filtered["Location Source"]
                    .fillna("Unknown")
                    .astype(str)
                    .isin(map_location_sources)
                ]

            if "County" in map_filtered.columns and map_counties:
                map_filtered = map_filtered[map_filtered["County"].isin(map_counties)]

            if map_cod_range is not None and len(map_cod_range) == 2:
                cod_start = pd.Timestamp(map_cod_range[0])
                cod_end = pd.Timestamp(map_cod_range[1])
                cod_mask = map_filtered["First Power Date"].between(
                    cod_start,
                    cod_end,
                    inclusive="both",
                )
                if include_missing_cod:
                    cod_mask = cod_mask | map_filtered["First Power Date"].isna()
                map_filtered = map_filtered[cod_mask]

            # ------------------------------------------------
            # MAP KPIs
            # ------------------------------------------------
            mk1, mk2, mk3, mk4 = st.columns(4)
            mk1.metric("Mapped Projects", f"{len(map_filtered):,}")
            mk2.metric(
                "Mapped Capacity",
                f"{map_filtered['Capacity (MW)'].sum():,.0f} MW",
            )
            mk3.metric(
                "Average Score",
                f"{map_filtered['Opportunity Score'].mean():.1f}"
                if len(map_filtered) > 0
                else "N/A",
            )
            mk4.metric(
                "Contact / Diligence",
                int((map_filtered["Action"] == "CONTACT / DILIGENCE").sum()),
            )

            if map_filtered.empty:
                st.warning("No projects match the current Map Explorer filters.")
            else:
                # --------------------------------------------
                # MAP DATA
                # --------------------------------------------
                technology_colors = {
                    "Solar": [245, 184, 0, 190],
                    "Storage": [30, 136, 229, 190],
                    "Wind": [52, 168, 83, 190],
                }

                map_filtered["Map Color"] = map_filtered[
                    "Power Project Type"
                ].apply(lambda x: technology_colors.get(x, [120, 120, 120, 180]))

                map_filtered["Map Radius"] = (
                    np.sqrt(map_filtered["Capacity (MW)"].clip(lower=1)) * 950
                )
                map_filtered["Project"] = map_filtered["Power Project Name"].astype(str)
                map_filtered["Tech"] = map_filtered["Power Project Type"].astype(str)
                map_filtered["MW"] = map_filtered["Capacity (MW)"].round(1)
                map_filtered["Score"] = map_filtered["Opportunity Score"].round(1)
                map_filtered["COD"] = map_filtered["First Power Date"].apply(format_date)
                map_filtered["Offtaker"] = map_filtered.get(
                    "Contract Offtaker", pd.Series(index=map_filtered.index, dtype=object)
                ).apply(lambda x: clean_text(x) or "N/A")
                map_filtered["Tax Credit"] = map_filtered.get(
                    "PTC/ITC", pd.Series(index=map_filtered.index, dtype=object)
                ).apply(lambda x: clean_text(x) or "Not Identified")
                map_filtered["Map Location Source"] = map_filtered.get(
                    "Location Source", pd.Series("N/A", index=map_filtered.index)
                ).apply(lambda x: clean_text(x) or "N/A")
                map_filtered["Map County"] = map_filtered.get(
                    "County", pd.Series("N/A", index=map_filtered.index)
                ).apply(lambda x: clean_text(x) or "N/A")

                lat_center = float(map_filtered["Map Latitude"].mean())
                lon_center = float(map_filtered["Map Longitude"].mean())
                lat_span = float(
                    map_filtered["Map Latitude"].max()
                    - map_filtered["Map Latitude"].min()
                )
                lon_span = float(
                    map_filtered["Map Longitude"].max()
                    - map_filtered["Map Longitude"].min()
                )
                max_span = max(lat_span, lon_span)

                if max_span <= 0.25:
                    zoom = 9.0
                elif max_span <= 0.5:
                    zoom = 8.0
                elif max_span <= 1.0:
                    zoom = 7.0
                elif max_span <= 2.0:
                    zoom = 6.0
                elif max_span <= 4.0:
                    zoom = 5.2
                else:
                    zoom = 4.4

                layer = pdk.Layer(
                    "ScatterplotLayer",
                    data=map_filtered,
                    get_position="[Map Longitude, Map Latitude]",
                    get_radius="Map Radius",
                    get_fill_color="Map Color",
                    get_line_color=[255, 255, 255, 180],
                    line_width_min_pixels=1,
                    radius_min_pixels=4,
                    radius_max_pixels=20,
                    pickable=True,
                    auto_highlight=True,
                    stroked=True,
                    filled=True,
                )

                view_state = pdk.ViewState(
                    latitude=lat_center,
                    longitude=lon_center,
                    zoom=zoom,
                    pitch=0,
                )

                tooltip = {
                    "html": """
                        <b>{Project}</b><br/>
                        Owner: {Owner}<br/>
                        Technology: {Tech}<br/>
                        Capacity: {MW} MW<br/>
                        ERCOT Area: {ERCOT Area}<br/>
                        County: {Map County}<br/>
                        Status: {Power Project Status}<br/>
                        COD: {COD}<br/>
                        Opportunity Score: {Score}<br/>
                        Action: {Action}<br/>
                        Offtaker: {Offtaker}<br/>
                        PTC / ITC: {Tax Credit}<br/>
                        Location Source: {Map Location Source}
                    """,
                    "style": {
                        "backgroundColor": "rgba(20,20,20,0.92)",
                        "color": "white",
                    },
                }

                deck = pdk.Deck(
                    layers=[layer],
                    initial_view_state=view_state,
                    tooltip=tooltip,
                )

                st.caption(
                    "Point size reflects project MW. Point color: Solar = yellow, Storage = blue, Wind = green. Hover over a point for project details."
                )

                if "Location Source" in map_filtered.columns:
                    source_counts = (
                        map_filtered["Location Source"]
                        .fillna("Unknown")
                        .astype(str)
                        .value_counts()
                        .to_dict()
                    )
                    source_text = " | ".join(
                        [f"{source}: {count:,}" for source, count in source_counts.items()]
                    )
                    st.caption(
                        "Coordinate quality / source for current map: " + source_text
                    )

                st.pydeck_chart(
                    deck,
                    use_container_width=True,
                    height=720,
                )

                # --------------------------------------------
                # RANKED PROJECTS ON CURRENT MAP
                # --------------------------------------------
                st.markdown("### Ranked Projects on Current Map")
                st.caption(
                    "The table below only includes projects currently visible under the Map Explorer filters."
                )

                map_table_columns = [
                    "Rank",
                    "Power Project Name",
                    "Owner",
                    "Power Project Type",
                    "County",
                    "ERCOT Area",
                    "Capacity (MW)",
                    "Power Project Status",
                    "First Power Date",
                    "Location Source",
                    "PTC/ITC",
                    "Contract Offtaker",
                    "Opportunity Score",
                    "Action",
                ]
                map_table_columns = [
                    col for col in map_table_columns if col in map_filtered.columns
                ]

                st.dataframe(
                    map_filtered[map_table_columns].sort_values(
                        "Opportunity Score", ascending=False
                    ),
                    use_container_width=True,
                    hide_index=True,
                    height=420,
                    column_config={
                        "Capacity (MW)": st.column_config.NumberColumn(
                            "MW", format="%.1f"
                        ),
                        "First Power Date": st.column_config.DateColumn("COD"),
                        "Opportunity Score": st.column_config.ProgressColumn(
                            "Opportunity Score",
                            min_value=0,
                            max_value=100,
                            format="%.1f",
                        ),
                    },
                )

                # --------------------------------------------
                # DRILL INTO ONE MAPPED PROJECT
                # --------------------------------------------
                st.markdown("### Project Drilldown")

                map_filtered = map_filtered.copy()
                map_filtered["Map Selection Label"] = map_filtered.apply(
                    lambda row: (
                        f"{clean_text(row.get('Power Project Name'))} — "
                        f"{clean_text(row.get('Owner')) or 'Unknown Owner'} — "
                        f"{row.get('Capacity (MW)', np.nan):,.1f} MW — "
                        f"{clean_text(row.get('Generator ID')) or clean_text(row.get('Queue ID')) or 'No ID'}"
                    ),
                    axis=1,
                )

                selected_map_label = st.selectbox(
                    "Select a mapped project",
                    map_filtered["Map Selection Label"].tolist(),
                    key="map_project_drilldown",
                )
                map_project = map_filtered[
                    map_filtered["Map Selection Label"] == selected_map_label
                ].iloc[0]

                d1, d2, d3, d4, d5 = st.columns(5)
                d1.metric("Opportunity Score", f"{map_project['Opportunity Score']:.1f}")
                d2.metric("Action", map_project["Action"])
                d3.metric("MW", f"{map_project['Capacity (MW)']:,.1f}")
                d4.metric("ERCOT Area", map_project["ERCOT Area"])
                d5.metric("COD", format_date(map_project["First Power Date"]))

                st.markdown(
                    f"**{map_project['Power Project Name']}** — {clean_text(map_project['Owner']) or 'Unknown Owner'}"
                )

                drill_left, drill_right = st.columns(2)

                with drill_left:
                    st.markdown("#### Project / Market")
                    project_market_fields = [
                        "Power Project Type",
                        "Power Project Status",
                        "Detailed Status",
                        "County",
                        "ISO Zone",
                        "Point of Interconnection",
                        "Location Source",
                        "Latitude (Degrees)",
                        "Longitude (Degrees)",
                    ]
                    project_market_fields = [
                        col for col in project_market_fields if col in map_project.index
                    ]
                    pm_values = {
                        col: clean_text(map_project.get(col)) or "N/A"
                        for col in project_market_fields
                    }
                    st.dataframe(
                        pd.DataFrame(
                            {
                                "Field": list(pm_values.keys()),
                                "Value": list(pm_values.values()),
                            }
                        ),
                        use_container_width=True,
                        hide_index=True,
                    )

                with drill_right:
                    st.markdown("#### Commercial / Tax")
                    commercial_fields = [
                        "Contract Type",
                        "Contract Capacity (MW)",
                        "Contract Offtaker",
                        *available_contract_columns,
                        "PTC/ITC",
                        "Energy Community",
                        "Domestic Content Review",
                    ]
                    commercial_fields = [
                        col for col in commercial_fields if col in map_project.index
                    ]
                    commercial_values = {
                        col: clean_text(map_project.get(col)) or "N/A"
                        for col in commercial_fields
                    }
                    st.dataframe(
                        pd.DataFrame(
                            {
                                "Field": list(commercial_values.keys()),
                                "Value": list(commercial_values.values()),
                            }
                        ),
                        use_container_width=True,
                        hide_index=True,
                    )

                with st.expander("🔌 Interconnection Detail", expanded=False):
                    ix_fields = [
                        "Queue ID",
                        "Point of Interconnection",
                        *available_interconnection_columns,
                    ]
                    ix_fields = [col for col in ix_fields if col in map_project.index]
                    ix_values = {
                        col: clean_text(map_project.get(col)) or "N/A"
                        for col in ix_fields
                    }
                    st.dataframe(
                        pd.DataFrame(
                            {
                                "Field": list(ix_values.keys()),
                                "Value": list(ix_values.values()),
                            }
                        ),
                        use_container_width=True,
                        hide_index=True,
                    )

                if available_diligence_columns:
                    with st.expander("🏗️ Equipment / EPC Diligence", expanded=False):
                        equipment_values = {
                            col: clean_text(map_project.get(col)) or "N/A"
                            for col in available_diligence_columns
                        }
                        st.dataframe(
                            pd.DataFrame(
                                {
                                    "Field": list(equipment_values.keys()),
                                    "Value": list(equipment_values.values()),
                                }
                            ),
                            use_container_width=True,
                            hide_index=True,
                        )
                        st.caption(
                            "Equipment data is for diligence only and is not treated as proof of Domestic Content qualification."
                        )

                st.info(f"**Why it ranks:** {map_project['Why It Ranks']}")
                st.warning(f"**Key risk:** {map_project['Key Risk']}")
