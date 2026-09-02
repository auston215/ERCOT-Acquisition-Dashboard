import streamlit as st
import pandas as pd
import numpy as np

from datetime import date, timezone
from email.utils import parsedate_to_datetime

import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET

import re
import html as html_lib


# ============================================================
# PAGE SETUP
# ============================================================

st.set_page_config(
    page_title="ERCOT Acquisition Dashboard",
    page_icon="⚡",
    layout="wide"
)

st.title("⚡ ERCOT Acquisition Dashboard")

st.caption(
    "M&A screening tool for ERCOT solar, battery storage, "
    "and operating wind projects"
)


# ============================================================
# OPTIONAL SELLER INTELLIGENCE SETTINGS
#
# IMPORTANT:
# This information DOES NOT feed the score.
# It is informational only.
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

        return pd.to_datetime(
            value
        ).strftime(
            "%m/%d/%Y"
        )

    except Exception:

        return clean_text(
            value
        )


def strip_html(value):

    if value is None:
        return ""

    text = re.sub(
        r"<[^>]+>",
        " ",
        str(value)
    )

    text = html_lib.unescape(
        text
    )

    return re.sub(
        r"\s+",
        " ",
        text
    ).strip()


def map_ercot_area(value):

    zone = clean_text(
        value
    )

    mapping = {

        "Load Zone - North":
            "ERCOT-N",

        "North Hub":
            "ERCOT-N",

        "Load Zone - South":
            "ERCOT-S",

        "South Hub":
            "ERCOT-S",

        "Load Zone - West":
            "ERCOT-W",

        "West Hub":
            "ERCOT-W",

        "Load Zone - Houston":
            "ERCOT-H",

        "Houston Hub":
            "ERCOT-H",

        "Panhandle Hub":
            "Panhandle",
    }

    return mapping.get(
        zone,
        zone if zone else "Unknown"
    )


# ============================================================
# SIDEBAR — DATA
# ============================================================

st.sidebar.header(
    "1. Data"
)

uploaded_file = st.sidebar.file_uploader(
    "Upload latest Orennia CSV",
    type=["csv"]
)

st.sidebar.divider()


# ============================================================
# SIDEBAR — OPPORTUNITY SCORE WEIGHTS
#
# ORIGINAL SCORING
# ============================================================

st.sidebar.header(
    "2. Opportunity Score Weights"
)

distress_weight = st.sidebar.number_input(
    "Seller Motivation",
    min_value=0.0,
    max_value=1.0,
    value=0.35,
    step=0.05,
    key="distress_weight"
)

development_weight = st.sidebar.number_input(
    "Development Stage",
    min_value=0.0,
    max_value=1.0,
    value=0.25,
    step=0.05,
    key="development_weight"
)

market_weight = st.sidebar.number_input(
    "Market / Revenue",
    min_value=0.0,
    max_value=1.0,
    value=0.15,
    step=0.05,
    key="market_weight"
)

value_weight = st.sidebar.number_input(
    "Acquisition Value",
    min_value=0.0,
    max_value=1.0,
    value=0.10,
    step=0.05,
    key="value_weight"
)

exec_weight = st.sidebar.number_input(
    "Executability",
    min_value=0.0,
    max_value=1.0,
    value=0.15,
    step=0.05,
    key="exec_weight"
)

total_weight = (
    distress_weight
    + development_weight
    + market_weight
    + value_weight
    + exec_weight
)

if abs(
    total_weight - 1.0
) > 0.001:

    st.sidebar.error(
        f"Weights currently total {total_weight:.0%}. "
        "They should total 100%."
    )

else:

    st.sidebar.success(
        "Overall Weights = 100%"
    )


# ============================================================
# SIDEBAR — SCORING INPUTS
# ============================================================

st.sidebar.divider()

st.sidebar.header(
    "3. Scoring Inputs"
)


# ------------------------------------------------------------
# SELLER MOTIVATION
# ------------------------------------------------------------

with st.sidebar.expander(
    "Seller Motivation Points"
):

    distress_5 = st.number_input(
        "Discount Potential 5",
        value=100,
        key="distress_5"
    )

    distress_4 = st.number_input(
        "Discount Potential 4",
        value=80,
        key="distress_4"
    )

    distress_3 = st.number_input(
        "Discount Potential 3",
        value=60,
        key="distress_3"
    )

    distress_2 = st.number_input(
        "Discount Potential 2",
        value=40,
        key="distress_2"
    )

    distress_1 = st.number_input(
        "Discount Potential 1",
        value=20,
        key="distress_1"
    )

    distress_none = st.number_input(
        "No Seller Signal",
        value=0,
        key="distress_none"
    )

    confidence_high = st.number_input(
        "High Confidence Multiplier",
        value=1.00,
        step=0.05,
        key="confidence_high"
    )

    confidence_medium = st.number_input(
        "Medium Confidence Multiplier",
        value=0.90,
        step=0.05,
        key="confidence_medium"
    )

    confidence_low = st.number_input(
        "Low Confidence Multiplier",
        value=0.75,
        step=0.05,
        key="confidence_low"
    )


# ------------------------------------------------------------
# DEVELOPMENT STAGE
# ------------------------------------------------------------

with st.sidebar.expander(
    "Development Stage Points"
):

    development_operating = st.number_input(
        "Operating",
        value=100,
        key="development_operating"
    )

    development_50 = st.number_input(
        ">50% Construction",
        value=92,
        key="development_50"
    )

    development_construction = st.number_input(
        "In Construction",
        value=85,
        key="development_construction"
    )

    development_ia = st.number_input(
        "IA Executed",
        value=75,
        key="development_ia"
    )

    development_fis_complete = st.number_input(
        "FIS Completed",
        value=65,
        key="development_fis_complete"
    )

    development_fis_started = st.number_input(
        "FIS Started",
        value=55,
        key="development_fis_started"
    )

    development_studies = st.number_input(
        "Studies Undergoing",
        value=45,
        key="development_studies"
    )

    development_pre = st.number_input(
        "Pre-Study",
        value=35,
        key="development_pre"
    )

    development_inactive = st.number_input(
        "Inactive / Suspended / Retired",
        value=15,
        key="development_inactive"
    )


# ------------------------------------------------------------
# REVENUE VISIBILITY
# ------------------------------------------------------------

with st.sidebar.expander(
    "Revenue Visibility Points"
):

    market_both = st.number_input(
        "Contract + Named Offtaker",
        value=95,
        key="market_both"
    )

    market_offtaker = st.number_input(
        "Named Offtaker Only",
        value=90,
        key="market_offtaker"
    )

    market_contract = st.number_input(
        "Contract Only",
        value=80,
        key="market_contract"
    )

    market_none = st.number_input(
        "Neither Contract nor Offtaker",
        value=45,
        key="market_none"
    )


# ------------------------------------------------------------
# ERCOT LOCATION
# ------------------------------------------------------------

with st.sidebar.expander(
    "ERCOT Location Points"
):

    location_north = st.number_input(
        "ERCOT-N",
        value=90,
        key="location_north"
    )

    location_houston = st.number_input(
        "ERCOT-H",
        value=85,
        key="location_houston"
    )

    location_south = st.number_input(
        "ERCOT-S",
        value=70,
        key="location_south"
    )

    location_west = st.number_input(
        "ERCOT-W",
        value=60,
        key="location_west"
    )

    location_panhandle = st.number_input(
        "Panhandle",
        value=50,
        key="location_panhandle"
    )

    location_unknown = st.number_input(
        "Unknown / Other",
        value=50,
        key="location_unknown"
    )


# ------------------------------------------------------------
# MARKET / REVENUE MIX
# ------------------------------------------------------------

with st.sidebar.expander(
    "Market / Revenue Mix"
):

    revenue_visibility_weight = st.number_input(
        "Revenue Visibility %",
        min_value=0.0,
        max_value=1.0,
        value=0.70,
        step=0.05,
        key="revenue_visibility_weight"
    )

    location_market_weight = st.number_input(
        "ERCOT Location %",
        min_value=0.0,
        max_value=1.0,
        value=0.30,
        step=0.05,
        key="location_market_weight"
    )

market_mix_total = (
    revenue_visibility_weight
    + location_market_weight
)

if abs(
    market_mix_total - 1.0
) > 0.001:

    st.sidebar.warning(
        f"Market / Revenue mix totals "
        f"{market_mix_total:.0%}. "
        "It should equal 100%."
    )


# ------------------------------------------------------------
# ACQUISITION VALUE
#
# RESTORED TO PREVIOUS SCORING
# ------------------------------------------------------------

with st.sidebar.expander(
    "Acquisition Value Points"
):

    value_both = st.number_input(
        "Tax Credit + Energy Community",
        value=75,
        key="value_both"
    )

    value_tax = st.number_input(
        "Tax Credit Only",
        value=70,
        key="value_tax"
    )

    value_ec = st.number_input(
        "Energy Community Only",
        value=60,
        key="value_ec"
    )

    value_none = st.number_input(
        "Neither Tax Credit nor Energy Community",
        value=55,
        key="value_none"
    )


# ------------------------------------------------------------
# TIMING
# ------------------------------------------------------------

with st.sidebar.expander(
    "Timing Points"
):

    timing_operating = st.number_input(
        "COD Reached / Passed",
        value=100,
        key="timing_operating"
    )

    timing_1 = st.number_input(
        "COD Within 1 Year",
        value=90,
        key="timing_1"
    )

    timing_2 = st.number_input(
        "COD Within 2 Years",
        value=75,
        key="timing_2"
    )

    timing_3 = st.number_input(
        "COD Within 3 Years",
        value=60,
        key="timing_3"
    )

    timing_long = st.number_input(
        "COD >3 Years",
        value=45,
        key="timing_long"
    )

    timing_missing = st.number_input(
        "COD Missing",
        value=50,
        key="timing_missing"
    )


# ------------------------------------------------------------
# EXECUTABILITY
# ------------------------------------------------------------

with st.sidebar.expander(
    "Executability Mix"
):

    actionability_weight = st.number_input(
        "Seller Actionability %",
        min_value=0.0,
        max_value=1.0,
        value=0.50,
        step=0.05,
        key="actionability_weight"
    )

    timing_exec_weight = st.number_input(
        "Timing %",
        min_value=0.0,
        max_value=1.0,
        value=0.30,
        step=0.05,
        key="timing_exec_weight"
    )

    development_exec_weight = st.number_input(
        "Development Stage %",
        min_value=0.0,
        max_value=1.0,
        value=0.20,
        step=0.05,
        key="development_exec_weight"
    )

exec_mix_total = (
    actionability_weight
    + timing_exec_weight
    + development_exec_weight
)

if abs(
    exec_mix_total - 1.0
) > 0.001:

    st.sidebar.warning(
        f"Executability mix totals "
        f"{exec_mix_total:.0%}. "
        "It should equal 100%."
    )


# ============================================================
# SCORE MAPPINGS
# ============================================================

discount_score_map = {

    5:
        distress_5,

    4:
        distress_4,

    3:
        distress_3,

    2:
        distress_2,

    1:
        distress_1,
}


confidence_score_map = {

    "High":
        confidence_high,

    "Medium":
        confidence_medium,

    "Low":
        confidence_low,
}


actionability_points = {

    5:
        100,

    4:
        80,

    3:
        60,

    2:
        40,

    1:
        20,
}


location_points = {

    "ERCOT-N":
        location_north,

    "ERCOT-H":
        location_houston,

    "ERCOT-S":
        location_south,

    "ERCOT-W":
        location_west,

    "Panhandle":
        location_panhandle,

    "Unknown":
        location_unknown,
}


def calculate_discount_score(
    potential,
    confidence
):

    if pd.isna(
        potential
    ):

        return distress_none

    try:

        potential = int(
            potential
        )

    except Exception:

        return distress_none

    base_score = discount_score_map.get(
        potential,
        distress_none
    )

    confidence_multiplier = (
        confidence_score_map.get(
            clean_text(
                confidence
            ),
            confidence_low
        )
    )

    return round(
        base_score
        * confidence_multiplier,
        1
    )


def actionability_score(
    value
):

    if pd.isna(
        value
    ):

        return 50

    try:

        value = int(
            value
        )

    except Exception:

        return 50

    return actionability_points.get(
        value,
        50
    )


def location_score(
    area
):

    return location_points.get(
        clean_text(
            area
        ),
        location_unknown
    )


# ============================================================
# DASHBOARD GUIDE
# ============================================================

st.markdown(
    "## 📘 Dashboard Guide"
)

guide_left, guide_right = st.columns(
    [1.55, 1]
)


with guide_left:

    st.markdown(
        "### 🎯 Opportunity Score"
    )

    st.caption(
        "Projects are scored from 0–100 to prioritize attractive "
        "and actionable acquisition opportunities."
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

                "Tax-credit / Energy Community attributes",

                "Ability to realistically execute a transaction",
            ],
        }
    )

    st.dataframe(
        scoring_methodology,
        use_container_width=True,
        hide_index=True
    )

    st.markdown(
        "#### Formula"
    )

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
        f"Market / Revenue = Revenue Visibility × "
        f"{revenue_visibility_weight:.0%} + ERCOT Location × "
        f"{location_market_weight:.0%}."
    )

    st.caption(
        f"Executability = Seller Actionability × "
        f"{actionability_weight:.0%} + Timing × "
        f"{timing_exec_weight:.0%} + Development Stage × "
        f"{development_exec_weight:.0%}."
    )


    # --------------------------------------------------------
    # EXAMPLE
    # --------------------------------------------------------

    example_seller = (
        distress_4
        * confidence_high
    )

    example_development = (
        development_operating
    )

    example_revenue = (
        market_both
    )

    example_location = (
        location_north
    )

    example_market = (
        example_revenue
        * revenue_visibility_weight

        +

        example_location
        * location_market_weight
    )

    example_value = (
        value_tax
    )

    example_actionability = 100

    example_timing = (
        timing_operating
    )

    example_executability = (
        example_actionability
        * actionability_weight

        +

        example_timing
        * timing_exec_weight

        +

        example_development
        * development_exec_weight
    )

    example_final = (
        example_seller
        * distress_weight

        +

        example_development
        * development_weight

        +

        example_market
        * market_weight

        +

        example_value
        * value_weight

        +

        example_executability
        * exec_weight
    )

    st.markdown(
        "#### Example"
    )

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

                (
                    "Discount Potential 4 = 80; "
                    "High Confidence = 100%; "
                    "80 × 100% = 80"
                ),

                (
                    "Operating project = 100"
                ),

                (
                    f"Contract + named offtaker = "
                    f"{example_revenue:.0f}; "
                    f"ERCOT-N = {example_location:.0f}"
                ),

                (
                    "Tax Credit only = 70"
                ),

                (
                    f"Actionability 100 × "
                    f"{actionability_weight:.0%} + "
                    f"Timing 100 × "
                    f"{timing_exec_weight:.0%} + "
                    f"Development Stage 100 × "
                    f"{development_exec_weight:.0%}"
                ),
            ],
        }
    )

    st.dataframe(
        example_background,
        use_container_width=True,
        hide_index=True
    )

    st.success(
        f"Example Opportunity Score = "
        f"{example_final:.1f}"
    )


with guide_right:

    st.markdown(
        "### 🧭 How to Use"
    )

    st.markdown(
        """
        **1. Management Shortlist** — Top 5 priorities  
        **2. Top Acquisition Targets** — Top 20 overall  
        **3. By Technology** — Solar, Storage or Wind  
        **4. ERCOT Area** — Compare market location  
        **5. Bundles** — Multiple 50–60 MW assets by owner  
        **6. Score Breakdown** — Drill into a project
        """
    )

    st.markdown(
        "### 🚦 Score Guide"
    )

    st.markdown(
        """
        **80+** → Contact / Diligence  
        **70–79** → Investigate  
        **60–69** → Monitor  
        **<60** → Low Priority
        """
    )

    st.markdown(
        "### 🗺️ Location Logic"
    )

    location_guide = pd.DataFrame(
        {

            "Area": [

                "ERCOT-N",

                "ERCOT-H",

                "ERCOT-S",

                "ERCOT-W",

                "Panhandle",
            ],

            "Score": [

                location_north,

                location_houston,

                location_south,

                location_west,

                location_panhandle,
            ],
        }
    )

    st.dataframe(
        location_guide,
        use_container_width=True,
        hide_index=True
    )

    st.caption(
        "Location is a broad screening proxy. "
        "Node-level congestion, basis, curtailment and market "
        "fundamentals can materially differ within each area."
    )


# ============================================================
# FULL SCORE LOGIC
# ============================================================

with st.expander(
    "📐 View Full Score Logic",
    expanded=False
):

    st.markdown(
        "#### Seller Motivation"
    )

    st.caption(
        "Discount Potential measures the strength of the seller "
        "motivation / transaction opportunity. The base score is "
        "then adjusted by confidence."
    )

    seller_logic = pd.DataFrame(
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
    )

    st.dataframe(
        seller_logic,
        use_container_width=True,
        hide_index=True
    )


    confidence_logic = pd.DataFrame(
        {

            "Confidence": [

                "High",

                "Medium",

                "Low",
            ],

            "Multiplier": [

                f"{confidence_high:.0%}",

                f"{confidence_medium:.0%}",

                f"{confidence_low:.0%}",
            ],
        }
    )

    st.dataframe(
        confidence_logic,
        use_container_width=True,
        hide_index=True
    )


    st.markdown(
        "#### Development Stage"
    )

    st.caption(
        "Measures how far the project has progressed through "
        "development, interconnection and construction."
    )

    development_logic = pd.DataFrame(
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
    )

    st.dataframe(
        development_logic,
        use_container_width=True,
        hide_index=True
    )


    st.markdown(
        "#### Market / Revenue"
    )

    st.caption(
        f"Market / Revenue = Revenue Visibility × "
        f"{revenue_visibility_weight:.0%} + ERCOT Location × "
        f"{location_market_weight:.0%}."
    )

    market_logic = pd.DataFrame(
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
    )

    st.dataframe(
        market_logic,
        use_container_width=True,
        hide_index=True
    )


    location_logic = pd.DataFrame(
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
    )

    st.dataframe(
        location_logic,
        use_container_width=True,
        hide_index=True
    )


    st.markdown(
        "#### Acquisition Value"
    )

    value_logic = pd.DataFrame(
        {

            "Attributes": [

                "Tax Credit + Energy Community",

                "Tax Credit Only",

                "Energy Community Only",

                "Neither",
            ],

            "Score": [

                value_both,

                value_tax,

                value_ec,

                value_none,
            ],
        }
    )

    st.dataframe(
        value_logic,
        use_container_width=True,
        hide_index=True
    )


    st.markdown(
        "#### Executability"
    )

    st.caption(
        f"Executability = Seller Actionability × "
        f"{actionability_weight:.0%} + Timing × "
        f"{timing_exec_weight:.0%} + Development Stage × "
        f"{development_exec_weight:.0%}."
    )


st.caption(
    f"ERCOT Location represents "
    f"{location_market_weight * market_weight:.1%} of the total "
    f"Opportunity Score under the current assumptions."
)

st.caption(
    "Screening tool only — rankings prioritize sourcing and diligence "
    "activity and are not a substitute for full investment underwriting."
)

st.divider()


# ============================================================
# DEFAULT SELLER ASSUMPTIONS
#
# THESE VALUES DRIVE THE SCORE.
# ============================================================

seller_signals = pd.DataFrame(
    [

        [
            "Birch Creek Energy",
            5,
            5,
            "Medium"
        ],

        [
            "Birch Creek Development",
            5,
            5,
            "Medium"
        ],

        [
            "esVolta",
            4,
            5,
            "High"
        ],

        [
            "Key Capture Energy",
            4,
            5,
            "High"
        ],

        [
            "Lightsource BP",
            3,
            4,
            "High"
        ],

        [
            "Ørsted U.S. Onshore",
            3,
            4,
            "Medium"
        ],

        [
            "Orsted",
            3,
            4,
            "Medium"
        ],

        [
            "Flatiron Energy",
            2,
            4,
            "High"
        ],

        [
            "Recurrent Energy",
            2,
            2,
            "Medium"
        ],

        [
            "EDF power solutions North America",
            1,
            1,
            "High"
        ],

        [
            "EDF Renewables",
            1,
            1,
            "High"
        ],

        [
            "Greenbacker Renewable Energy Company",
            1,
            1,
            "High"
        ],
    ],

    columns=[

        "Owner",

        "Discount Potential",

        "Seller Actionability",

        "Confidence"
    ]
)


# ============================================================
# INITIALIZE SELLER ASSUMPTIONS
# ============================================================

if "seller_assumptions" not in st.session_state:

    st.session_state[
        "seller_assumptions"
    ] = seller_signals.copy()


# ============================================================
# NO FILE YET
# ============================================================

if uploaded_file is None:

    st.info(
        "Upload the latest Orennia Power Projects CSV "
        "using the sidebar to populate the dashboard."
    )

    st.stop()


# ============================================================
# LOAD DATA
# ============================================================

df = pd.read_csv(
    uploaded_file
)


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


missing_columns = [

    col

    for col in required_columns

    if col not in df.columns
]


if missing_columns:

    st.error(
        "The uploaded file is missing these required columns: "
        + ", ".join(
            missing_columns
        )
    )

    st.stop()


# ============================================================
# CLEAN DATA
# ============================================================

df[
    "Owner"
] = df[
    "Owner"
].fillna(
    ""
)


df[
    "First Power Date"
] = pd.to_datetime(

    df[
        "First Power Date"
    ],

    errors="coerce"
)


df[
    "Capacity (MW)"
] = pd.to_numeric(

    df[
        "Capacity (MW)"
    ],

    errors="coerce"
)


# ============================================================
# ERCOT AREA
# ============================================================

df[
    "ERCOT Area"
] = df[
    "ISO Zone"
].apply(
    map_ercot_area
)


df[
    "Location Score"
] = df[
    "ERCOT Area"
].apply(
    location_score
)


# ============================================================
# TECHNOLOGY UNIVERSE
#
# Solar   = all stages
# Storage = all stages
# Wind    = Operating only
# ============================================================

df = df[
    (
        df[
            "Power Project Type"
        ].isin(
            [
                "Solar",
                "Storage"
            ]
        )
    )

    |

    (
        (
            df[
                "Power Project Type"
            ]
            == "Wind"
        )

        &

        (
            df[
                "Power Project Status"
            ]
            == "Operating"
        )
    )
].copy()


# ============================================================
# HARD EXCLUSIONS
# ============================================================

df = df[
    ~df[
        "Owner"
    ].str.contains(
        "Pine Gate",
        case=False,
        na=False
    )
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


df = df[
    ~df[
        "Power Project Name"
    ].isin(
        excluded_projects
    )
].copy()


# ============================================================
# SELLER MOTIVATION / ACTIONABILITY ASSUMPTIONS
#
# THIS IS THE ACTUAL SCORING INPUT.
# ============================================================

st.subheader(
    "Seller Motivation / Actionability Assumptions"
)

st.caption(
    "These assumptions drive the project rankings. "
    "The automated public intelligence below is informational only "
    "and does not change the score."
)


current_sellers = (
    st.session_state[
        "seller_assumptions"
    ].copy()
)


current_sellers.insert(
    2,
    "Discount Score",
    current_sellers.apply(

        lambda row:

            calculate_discount_score(

                row[
                    "Discount Potential"
                ],

                row[
                    "Confidence"
                ]
            ),

        axis=1
    )
)


current_sellers.insert(
    4,
    "Actionability Score",
    current_sellers[
        "Seller Actionability"
    ].apply(
        actionability_score
    )
)


edited_sellers_full = st.data_editor(

    current_sellers,

    use_container_width=True,

    hide_index=True,

    num_rows="dynamic",

    key="seller_assumptions_editor",

    disabled=[
        "Discount Score",
        "Actionability Score"
    ],

    column_order=[

        "Owner",

        "Discount Potential",

        "Discount Score",

        "Seller Actionability",

        "Actionability Score",

        "Confidence",
    ],

    column_config={

        "Discount Potential":
            st.column_config.NumberColumn(
                "Discount Potential",
                min_value=1,
                max_value=5,
                step=1,
                format="%d"
            ),

        "Discount Score":
            st.column_config.ProgressColumn(
                "Discount Score",
                min_value=0,
                max_value=100,
                format="%.0f"
            ),

        "Seller Actionability":
            st.column_config.NumberColumn(
                "Seller Actionability",
                min_value=1,
                max_value=5,
                step=1,
                format="%d"
            ),

        "Actionability Score":
            st.column_config.ProgressColumn(
                "Actionability Score",
                min_value=0,
                max_value=100,
                format="%.0f"
            ),

        "Confidence":
            st.column_config.SelectboxColumn(
                "Confidence",
                options=[
                    "High",
                    "Medium",
                    "Low"
                ]
            ),
    }
)


# ============================================================
# SAVE SELLER ASSUMPTIONS
# ============================================================

editable_seller_columns = [

    "Owner",

    "Discount Potential",

    "Seller Actionability",

    "Confidence",
]


new_seller_assumptions = (
    edited_sellers_full[
        editable_seller_columns
    ]
    .copy()
)


old_seller_assumptions = (
    st.session_state[
        "seller_assumptions"
    ][
        editable_seller_columns
    ]
    .copy()
)


if not new_seller_assumptions.equals(
    old_seller_assumptions
):

    st.session_state[
        "seller_assumptions"
    ] = new_seller_assumptions

    st.rerun()


edited_sellers = (
    st.session_state[
        "seller_assumptions"
    ].copy()
)


edited_sellers[
    "Owner Key"
] = (
    edited_sellers[
        "Owner"
    ]
    .astype(str)
    .str.strip()
    .str.lower()
)


seller_lookup = (
    edited_sellers
    .set_index(
        "Owner Key"
    )
    .to_dict(
        "index"
    )
)


# ============================================================
# OPTIONAL AUTOMATED SELLER INTELLIGENCE
#
# DISPLAY ONLY.
# DOES NOT FEED THE SCORE.
# ============================================================

SELLER_SEARCH_TERMS = {

    "Birch Creek Energy":
        "Birch Creek Energy",

    "Birch Creek Development":
        "Birch Creek Energy",

    "esVolta":
        "esVolta",

    "Key Capture Energy":
        "Key Capture Energy",

    "Lightsource BP":
        "Lightsource bp",

    "Ørsted U.S. Onshore":
        "Orsted U.S. Onshore",

    "Orsted":
        "Orsted U.S. renewables",

    "Flatiron Energy":
        "Flatiron Energy",

    "Recurrent Energy":
        "Recurrent Energy",

    "EDF power solutions North America":
        "EDF power solutions North America",

    "EDF Renewables":
        "EDF Renewables North America",

    "Greenbacker Renewable Energy Company":
        "Greenbacker Renewable Energy Company",
}


SELLER_SIGNAL_TERMS = (

    '"strategic review" OR '
    '"strategic alternatives" OR '
    '"asset sale" OR '
    '"portfolio sale" OR '
    '"sale process" OR '
    'divest OR '
    'divestiture OR '
    '"capital recycling" OR '
    'monetization OR '
    '"sell-down" OR '
    '"stake sale" OR '
    'bankruptcy OR '
    'restructuring OR '
    'default OR '
    'distress OR '
    'liquidity OR '
    'layoffs OR '
    '"job cuts" OR '
    '"project cancellation"'
)


@st.cache_data(
    ttl=SELLER_REFRESH_SECONDS,
    show_spinner=False
)
def fetch_company_news(
    search_term
):

    query = (
        f'"{search_term}" '
        f'({SELLER_SIGNAL_TERMS}) '
        f'when:{SELLER_LOOKBACK_DAYS}d'
    )

    encoded_query = urllib.parse.quote_plus(
        query
    )

    url = (
        "https://news.google.com/rss/search?"
        f"q={encoded_query}"
        "&hl=en-US"
        "&gl=US"
        "&ceid=US:en"
    )

    request = urllib.request.Request(
        url,
        headers={
            "User-Agent":
                "Mozilla/5.0 ERCOT-Acquisition-Dashboard"
        }
    )

    articles = []

    try:

        with urllib.request.urlopen(
            request,
            timeout=10
        ) as response:

            xml_data = response.read()

        root = ET.fromstring(
            xml_data
        )

        for item in root.findall(
            ".//item"
        ):

            title = clean_text(
                item.findtext(
                    "title"
                )
            )

            description = strip_html(
                item.findtext(
                    "description"
                )
            )

            source = clean_text(
                item.findtext(
                    "source"
                )
            )

            link = clean_text(
                item.findtext(
                    "link"
                )
            )

            published_raw = clean_text(
                item.findtext(
                    "pubDate"
                )
            )

            published = pd.NaT

            if published_raw:

                try:

                    parsed = parsedate_to_datetime(
                        published_raw
                    )

                    if parsed.tzinfo is None:

                        parsed = parsed.replace(
                            tzinfo=timezone.utc
                        )

                    published = pd.Timestamp(
                        parsed
                    )

                except Exception:

                    published = pd.NaT

            articles.append(
                {

                    "Title":
                        title,

                    "Description":
                        description,

                    "Source":
                        source,

                    "Published":
                        published,

                    "URL":
                        link,
                }
            )

    except Exception:

        return []

    return articles


SELLER_SIGNAL_RULES = [

    {

        "Signal Type":
            "Formal Sale / Strategic Review",

        "Keywords": [

            "strategic review",

            "strategic alternatives",

            "sale process",

            "portfolio sale",

            "asset sale",

            "exploring a sale",

            "divestiture",
        ],

        "Suggested Motivation":
            5,

        "Suggested Actionability":
            5,
    },

    {

        "Signal Type":
            "Restructuring / Financial Stress",

        "Keywords": [

            "bankruptcy",

            "chapter 11",

            "restructuring",

            "default",

            "distressed",

            "liquidity crisis",

            "going concern",
        ],

        "Suggested Motivation":
            5,

        "Suggested Actionability":
            4,
    },

    {

        "Signal Type":
            "Capital Recycling / Monetization",

        "Keywords": [

            "capital recycling",

            "asset monetization",

            "monetization",

            "sell-down",

            "sell down",

            "stake sale",
        ],

        "Suggested Motivation":
            4,

        "Suggested Actionability":
            5,
    },

    {

        "Signal Type":
            "Layoffs / Cost Reduction",

        "Keywords": [

            "layoffs",

            "layoff",

            "job cuts",

            "workforce reduction",

            "headcount reduction",
        ],

        "Suggested Motivation":
            4,

        "Suggested Actionability":
            3,
    },

    {

        "Signal Type":
            "Project Cancellation / Portfolio Pressure",

        "Keywords": [

            "project cancellation",

            "project cancellations",

            "cancelled project",

            "canceled project",

            "project impairment",

            "impairment charge",
        ],

        "Suggested Motivation":
            4,

        "Suggested Actionability":
            3,
    },
]


def classify_article(
    title,
    description
):

    text = (
        clean_text(
            title
        )

        + " "

        + clean_text(
            description
        )
    ).lower()

    for rule in SELLER_SIGNAL_RULES:

        for keyword in rule[
            "Keywords"
        ]:

            if keyword.lower() in text:

                return rule

    return None


def build_advisory_seller_intelligence():

    rows = []

    for _, seller in edited_sellers.iterrows():

        owner = seller[
            "Owner"
        ]

        search_term = SELLER_SEARCH_TERMS.get(
            owner,
            owner
        )

        articles = fetch_company_news(
            search_term
        )

        classified_articles = []

        for article in articles:

            rule = classify_article(

                article.get(
                    "Title"
                ),

                article.get(
                    "Description"
                )
            )

            if rule is None:
                continue

            classified_articles.append(
                {

                    **article,

                    "Signal Type":
                        rule[
                            "Signal Type"
                        ],

                    "Suggested Motivation":
                        rule[
                            "Suggested Motivation"
                        ],

                    "Suggested Actionability":
                        rule[
                            "Suggested Actionability"
                        ],
                }
            )

        if classified_articles:

            classified_articles = sorted(
                classified_articles,
                key=lambda x:
                    (
                        pd.Timestamp.min
                        if pd.isna(
                            x[
                                "Published"
                            ]
                        )
                        else pd.Timestamp(
                            x[
                                "Published"
                            ]
                        ).tz_localize(
                            None
                        )
                    ),
                reverse=True
            )

            latest = classified_articles[
                0
            ]

            rows.append(
                {

                    "Owner":
                        owner,

                    "Current Motivation":
                        seller[
                            "Discount Potential"
                        ],

                    "Current Actionability":
                        seller[
                            "Seller Actionability"
                        ],

                    "Suggested Motivation":
                        latest[
                            "Suggested Motivation"
                        ],

                    "Suggested Actionability":
                        latest[
                            "Suggested Actionability"
                        ],

                    "Signal Type":
                        latest[
                            "Signal Type"
                        ],

                    "Signal Date":
                        latest[
                            "Published"
                        ],

                    "Source":
                        latest[
                            "Source"
                        ],

                    "Latest Signal":
                        latest[
                            "Title"
                        ],

                    "Article":
                        latest[
                            "URL"
                        ],
                }
            )

        else:

            rows.append(
                {

                    "Owner":
                        owner,

                    "Current Motivation":
                        seller[
                            "Discount Potential"
                        ],

                    "Current Actionability":
                        seller[
                            "Seller Actionability"
                        ],

                    "Suggested Motivation":
                        np.nan,

                    "Suggested Actionability":
                        np.nan,

                    "Signal Type":
                        "No qualifying recent signal",

                    "Signal Date":
                        pd.NaT,

                    "Source":
                        "",

                    "Latest Signal":
                        "",

                    "Article":
                        "",
                }
            )

    return pd.DataFrame(
        rows
    )


with st.expander(
    "📡 Public Seller Intelligence — Informational Only",
    expanded=False
):

    st.caption(
        "This feed looks for recent public seller signals and provides "
        "a suggested score direction. It does NOT change the assumptions "
        "above or affect project rankings."
    )

    refresh_intelligence = st.button(
        "🔄 Refresh Public Signals"
    )

    if refresh_intelligence:

        fetch_company_news.clear()

        st.rerun()

    advisory_intelligence = (
        build_advisory_seller_intelligence()
    )

    st.dataframe(

        advisory_intelligence,

        use_container_width=True,

        hide_index=True,

        column_config={

            "Current Motivation":
                st.column_config.NumberColumn(
                    "Current Motivation",
                    format="%.0f"
                ),

            "Current Actionability":
                st.column_config.NumberColumn(
                    "Current Actionability",
                    format="%.0f"
                ),

            "Suggested Motivation":
                st.column_config.NumberColumn(
                    "Suggested Motivation",
                    format="%.0f"
                ),

            "Suggested Actionability":
                st.column_config.NumberColumn(
                    "Suggested Actionability",
                    format="%.0f"
                ),

            "Signal Date":
                st.column_config.DateColumn(
                    "Signal Date"
                ),

            "Article":
                st.column_config.LinkColumn(
                    "Article"
                ),
        }
    )


st.divider()


# ============================================================
# MAP SELLER ASSUMPTIONS TO PROJECTS
#
# ONLY THE EDITABLE ASSUMPTIONS TABLE ABOVE IS USED.
# ============================================================

def get_seller_value(
    owner,
    column
):

    key = owner_key(
        owner
    )

    if key in seller_lookup:

        return seller_lookup[
            key
        ].get(
            column
        )

    return np.nan


df[
    "Discount Potential"
] = df[
    "Owner"
].apply(

    lambda x:

        get_seller_value(
            x,
            "Discount Potential"
        )
)


df[
    "Seller Actionability"
] = df[
    "Owner"
].apply(

    lambda x:

        get_seller_value(
            x,
            "Seller Actionability"
        )
)


df[
    "Seller Confidence"
] = df[
    "Owner"
].apply(

    lambda x:

        get_seller_value(
            x,
            "Confidence"
        )
)


# ============================================================
# SELLER MOTIVATION SCORE
# ============================================================

df[
    "Distress Score"
] = df.apply(

    lambda row:

        calculate_discount_score(

            row[
                "Discount Potential"
            ],

            row[
                "Seller Confidence"
            ]
        ),

    axis=1
)


# ============================================================
# DEVELOPMENT STAGE SCORE
# ============================================================

def development_stage_score(
    row
):

    status = clean_text(
        row.get(
            "Power Project Status"
        )
    )

    detailed = clean_text(
        row.get(
            "Detailed Status"
        )
    )

    if (
        status == "Operating"
        or detailed == "Construction Complete"
    ):

        return development_operating

    if "More Than 50%" in detailed:

        return development_50

    if status == "In Construction":

        return development_construction

    if (
        status == "IA Executed"
        or ", IA" in detailed
    ):

        return development_ia

    if "FIS Completed" in detailed:

        return development_fis_complete

    if "FIS Started" in detailed:

        return development_fis_started

    if status == "Pre-Study":

        return development_pre

    if status in [
        "Inactive",
        "Suspended",
        "Retired"
    ]:

        return development_inactive

    return development_studies


df[
    "Development Stage"
] = df.apply(
    development_stage_score,
    axis=1
)


# ============================================================
# REVENUE VISIBILITY
# ============================================================

def revenue_visibility_score(
    row
):

    contract = has_value(
        row.get(
            "Contract Type"
        )
    )

    offtaker = has_value(
        row.get(
            "Contract Offtaker"
        )
    )

    if contract and offtaker:

        return market_both

    if offtaker:

        return market_offtaker

    if contract:

        return market_contract

    return market_none


df[
    "Revenue Visibility"
] = df.apply(
    revenue_visibility_score,
    axis=1
)


# ============================================================
# MARKET / REVENUE
# ============================================================

df[
    "Market / Revenue"
] = (

    df[
        "Revenue Visibility"
    ]
    * revenue_visibility_weight

    +

    df[
        "Location Score"
    ]
    * location_market_weight
)


# ============================================================
# ENERGY COMMUNITY
#
# ORIGINAL LOGIC RESTORED
# ============================================================

energy_columns = [

    "Fossil Fuel Energy Communities",

    "Retired Coal Facilities Energy Communities",

    "Low Income Communities",

    "Native American Lands",
]


def energy_community(
    row
):

    for col in energy_columns:

        if col not in row.index:

            continue

        value = clean_text(
            row[
                col
            ]
        ).lower()

        if value in [
            "true",
            "yes",
            "1"
        ]:

            return "Yes"

    return "No"


df[
    "Energy Community"
] = df.apply(
    energy_community,
    axis=1
)


# ============================================================
# ACQUISITION VALUE
#
# ORIGINAL 75 / 70 / 60 / 55 LOGIC
# ============================================================

def acquisition_value(
    row
):

    tax_credit = has_value(
        row.get(
            "PTC/ITC"
        )
    )

    ec = (
        row[
            "Energy Community"
        ]
        == "Yes"
    )

    if tax_credit and ec:

        return value_both

    if tax_credit:

        return value_tax

    if ec:

        return value_ec

    return value_none


df[
    "Acquisition Value"
] = df.apply(
    acquisition_value,
    axis=1
)


# ============================================================
# TIMING SCORE
# ============================================================

as_of_date = pd.Timestamp(
    date.today()
)


def timing_score(
    row
):

    cod = row[
        "First Power Date"
    ]

    if pd.isna(
        cod
    ):

        return timing_missing

    days = (
        cod
        - as_of_date
    ).days

    if days <= 0:

        return timing_operating

    if days <= 365:

        return timing_1

    if days <= 730:

        return timing_2

    if days <= 1095:

        return timing_3

    return timing_long


df[
    "Timing Score"
] = df.apply(
    timing_score,
    axis=1
)


# ============================================================
# ACTIONABILITY SCORE
# ============================================================

df[
    "Actionability Score"
] = df[
    "Seller Actionability"
].apply(
    actionability_score
)


# ============================================================
# EXECUTABILITY SCORE
# ============================================================

df[
    "Executability"
] = (

    df[
        "Actionability Score"
    ]
    * actionability_weight

    +

    df[
        "Timing Score"
    ]
    * timing_exec_weight

    +

    df[
        "Development Stage"
    ]
    * development_exec_weight
)


# ============================================================
# DATA COMPLETENESS
# ============================================================

def completeness(
    row
):

    score = 0

    if has_value(
        row.get(
            "Owner"
        )
    ):

        score += 40

    if has_value(
        row.get(
            "Queue ID"
        )
    ):

        score += 15

    if not pd.isna(
        row.get(
            "First Power Date"
        )
    ):

        score += 15

    if (
        has_value(
            row.get(
                "Contract Type"
            )
        )

        or

        has_value(
            row.get(
                "Contract Offtaker"
            )
        )
    ):

        score += 15

    if has_value(
        row.get(
            "PTC/ITC"
        )
    ):

        score += 15

    return score


df[
    "Data Completeness"
] = df.apply(
    completeness,
    axis=1
)


# ============================================================
# OPPORTUNITY SCORE
#
# ORIGINAL SCORING FORMULA
# ============================================================

df[
    "Opportunity Score"
] = (

    df[
        "Distress Score"
    ]
    * distress_weight

    +

    df[
        "Development Stage"
    ]
    * development_weight

    +

    df[
        "Market / Revenue"
    ]
    * market_weight

    +

    df[
        "Acquisition Value"
    ]
    * value_weight

    +

    df[
        "Executability"
    ]
    * exec_weight
)


df[
    "Opportunity Score"
] = df[
    "Opportunity Score"
].round(
    2
)


# ============================================================
# ACTION
# ============================================================

def action(
    row
):

    if pd.isna(
        row[
            "Discount Potential"
        ]
    ):

        return "RESEARCH / MONITOR"

    score = row[
        "Opportunity Score"
    ]

    if score >= 80:

        return "CONTACT / DILIGENCE"

    if score >= 70:

        return "INVESTIGATE"

    if score >= 60:

        return "MONITOR"

    return "LOW PRIORITY"


df[
    "Action"
] = df.apply(
    action,
    axis=1
)


# ============================================================
# RANK
# ============================================================

df = df.sort_values(

    by=[
        "Opportunity Score",
        "Data Completeness",
        "Capacity (MW)"
    ],

    ascending=[
        False,
        False,
        False
    ]

).reset_index(
    drop=True
)


df[
    "Rank"
] = np.arange(
    1,
    len(
        df
    )
    + 1
)


# ============================================================
# MANAGEMENT EXPLANATION
# ============================================================

def why_it_ranks(
    row
):

    reasons = []

    if row[
        "Distress Score"
    ] >= 70:

        reasons.append(
            "Strong seller motivation / transaction angle"
        )

    elif row[
        "Distress Score"
    ] >= 50:

        reasons.append(
            "Credible seller opportunity"
        )

    if row[
        "Development Stage"
    ] >= 95:

        reasons.append(
            "Operating / highly mature project"
        )

    elif row[
        "Development Stage"
    ] >= 80:

        reasons.append(
            "Advanced development stage"
        )

    if row[
        "Revenue Visibility"
    ] >= 90:

        reasons.append(
            "Strong revenue / offtaker visibility"
        )

    elif row[
        "Revenue Visibility"
    ] >= 80:

        reasons.append(
            "Some contracted visibility"
        )

    if row[
        "Location Score"
    ] >= 85:

        reasons.append(
            "Attractive ERCOT market location"
        )

    if row[
        "Acquisition Value"
    ] >= 70:

        reasons.append(
            "Attractive tax-credit / siting attributes"
        )

    if row[
        "Executability"
    ] >= 80:

        reasons.append(
            "High execution readiness"
        )

    capacity = row.get(
        "Capacity (MW)",
        np.nan
    )

    if (
        not pd.isna(
            capacity
        )
        and capacity >= 100
    ):

        reasons.append(
            f"{capacity:,.0f} MW scale"
        )

    if not reasons:

        reasons.append(
            "Strong composite Opportunity Score"
        )

    return "; ".join(
        reasons[:3]
    )


def key_risk(
    row
):

    risks = []

    if pd.isna(
        row[
            "Discount Potential"
        ]
    ):

        risks.append(
            "Seller motivation not yet verified"
        )

    elif row[
        "Distress Score"
    ] < 50:

        risks.append(
            "Limited evidence of seller pressure"
        )

    if row[
        "Development Stage"
    ] < 55:

        risks.append(
            "Early-stage development risk"
        )

    elif row[
        "Development Stage"
    ] < 75:

        risks.append(
            "Development risk remains"
        )

    if row[
        "Revenue Visibility"
    ] <= 45:

        risks.append(
            "Limited visible revenue certainty"
        )

    elif row[
        "Revenue Visibility"
    ] < 90:

        risks.append(
            "Revenue / offtaker visibility is incomplete"
        )

    if row[
        "Location Score"
    ] <= 50:

        risks.append(
            "Lower broad-area location score; node may differ"
        )

    if pd.isna(
        row[
            "First Power Date"
        ]
    ):

        risks.append(
            "COD timing unclear"
        )

    if row[
        "Data Completeness"
    ] < 70:

        risks.append(
            "Material diligence data gaps"
        )

    if not risks:

        risks.append(
            "No major screen-level issue; full diligence still required"
        )

    return "; ".join(
        risks[:2]
    )


df[
    "Why It Ranks"
] = df.apply(
    why_it_ranks,
    axis=1
)


df[
    "Key Risk"
] = df.apply(
    key_risk,
    axis=1
)


df[
    "Recommended Action"
] = df[
    "Action"
]


# ============================================================
# DASHBOARD KPIs
# ============================================================

c1, c2, c3, c4 = st.columns(
    4
)


c1.metric(
    "Projects Screened",
    f"{len(df):,}"
)


c2.metric(
    "Total Capacity",
    f"{df['Capacity (MW)'].sum():,.0f} MW"
)


c3.metric(
    "Contact / Diligence",

    int(
        (
            df[
                "Action"
            ]
            == "CONTACT / DILIGENCE"
        ).sum()
    )
)


c4.metric(
    "Top Score",
    f"{df['Opportunity Score'].max():.1f}"
)


# ============================================================
# MANAGEMENT SHORTLIST
# ============================================================

st.divider()

st.subheader(
    "🎯 Management Shortlist"
)

st.caption(
    "Top five current acquisition priorities based on the screening model."
)


management_shortlist = df.head(
    5
).copy()


management_shortlist[
    "Management Rank"
] = np.arange(
    1,
    len(
        management_shortlist
    )
    + 1
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

    col

    for col in management_columns

    if col in management_shortlist.columns
]


st.dataframe(

    management_shortlist[
        management_columns
    ],

    use_container_width=True,

    hide_index=True,

    column_config={

        "Management Rank":
            st.column_config.NumberColumn(
                "Rank"
            ),

        "Power Project Type":
            st.column_config.TextColumn(
                "Tech"
            ),

        "Capacity (MW)":
            st.column_config.NumberColumn(
                "MW",
                format="%.1f"
            ),

        "Location Score":
            st.column_config.NumberColumn(
                "Location",
                format="%.0f"
            ),

        "Opportunity Score":
            st.column_config.ProgressColumn(
                "Score",
                min_value=0,
                max_value=100,
                format="%.1f"
            ),

        "Recommended Action":
            st.column_config.TextColumn(
                "Action"
            ),
    }
)


# ============================================================
# GLOBAL FILTERS
# ============================================================

st.divider()

st.subheader(
    "Filters"
)


f1, f2, f3, f4 = st.columns(
    4
)


technology_options = sorted(
    df[
        "Power Project Type"
    ]
    .dropna()
    .unique()
)


selected_technology = f1.multiselect(
    "Technology",
    technology_options,
    default=technology_options
)


ercot_area_options = sorted(
    df[
        "ERCOT Area"
    ]
    .dropna()
    .unique()
)


selected_ercot_areas = f2.multiselect(
    "ERCOT Area",
    ercot_area_options,
    default=ercot_area_options
)


owner_options = sorted(
    [

        owner

        for owner in df[
            "Owner"
        ].unique()

        if clean_text(
            owner
        )
    ]
)


selected_owners = f3.multiselect(
    "Owner",
    owner_options
)


status_options = sorted(
    df[
        "Power Project Status"
    ]
    .dropna()
    .unique()
)


selected_status = f4.multiselect(
    "Project Status",
    status_options,
    default=status_options
)


filtered = df[
    df[
        "Power Project Type"
    ].isin(
        selected_technology
    )
].copy()


filtered = filtered[
    filtered[
        "ERCOT Area"
    ].isin(
        selected_ercot_areas
    )
]


filtered = filtered[
    filtered[
        "Power Project Status"
    ].isin(
        selected_status
    )
]


if selected_owners:

    filtered = filtered[
        filtered[
            "Owner"
        ].isin(
            selected_owners
        )
    ]


# ============================================================
# TOP ACQUISITION TARGETS
# ============================================================

st.divider()

st.subheader(
    "🏆 Top Acquisition Targets"
)

st.caption(
    "Top 20 projects based on Opportunity Score."
)


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

    col

    for col in display_columns

    if col in filtered.columns
]


top_20 = filtered[
    existing_display_columns
].head(
    20
)


st.dataframe(

    top_20,

    use_container_width=True,

    hide_index=True,

    column_config={

        "Distress Score":
            st.column_config.NumberColumn(
                "Seller Motivation"
            ),

        "Development Stage":
            st.column_config.NumberColumn(
                "Development Stage",
                format="%.1f"
            ),

        "Revenue Visibility":
            st.column_config.NumberColumn(
                "Revenue Visibility",
                format="%.1f"
            ),

        "Location Score":
            st.column_config.NumberColumn(
                "Location",
                format="%.0f"
            ),

        "Market / Revenue":
            st.column_config.NumberColumn(
                "Market / Revenue",
                format="%.1f"
            ),

        "Opportunity Score":
            st.column_config.ProgressColumn(
                "Opportunity Score",
                min_value=0,
                max_value=100,
                format="%.1f"
            ),

        "First Power Date":
            st.column_config.DateColumn(
                "COD"
            ),
    }
)


# ============================================================
# TOP PROJECTS BY TECHNOLOGY
# ============================================================

st.divider()

st.subheader(
    "⚡ Top Projects by Technology"
)


tech_options = sorted(
    df[
        "Power Project Type"
    ]
    .dropna()
    .unique()
)


selected_tech_rank = st.selectbox(
    "Select Technology",
    tech_options,
    key="technology_ranking"
)


technology_ranked = df[
    df[
        "Power Project Type"
    ]
    == selected_tech_rank
].copy()


technology_ranked = technology_ranked.sort_values(

    by=[
        "Opportunity Score",
        "Data Completeness",
        "Capacity (MW)"
    ],

    ascending=[
        False,
        False,
        False
    ]

).reset_index(
    drop=True
)


technology_ranked[
    "Technology Rank"
] = np.arange(
    1,
    len(
        technology_ranked
    )
    + 1
)


technology_top_20 = technology_ranked.head(
    20
)


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

    col

    for col in tech_columns

    if col in technology_top_20.columns
]


t1, t2, t3 = st.columns(
    3
)


t1.metric(
    f"{selected_tech_rank} Projects",
    len(
        technology_ranked
    )
)


t2.metric(
    f"{selected_tech_rank} Capacity",
    f"{technology_ranked['Capacity (MW)'].sum():,.0f} MW"
)


if len(
    technology_ranked
) > 0:

    t3.metric(
        "Top Technology Score",
        f"{technology_ranked['Opportunity Score'].max():.1f}"
    )


st.dataframe(

    technology_top_20[
        tech_columns
    ],

    use_container_width=True,

    hide_index=True,

    column_config={

        "Technology Rank":
            st.column_config.NumberColumn(
                "Rank"
            ),

        "Distress Score":
            st.column_config.NumberColumn(
                "Seller Motivation"
            ),

        "Development Stage":
            st.column_config.NumberColumn(
                "Development Stage",
                format="%.1f"
            ),

        "Location Score":
            st.column_config.NumberColumn(
                "Location",
                format="%.0f"
            ),

        "Revenue Visibility":
            st.column_config.NumberColumn(
                "Revenue Visibility",
                format="%.1f"
            ),

        "Market / Revenue":
            st.column_config.NumberColumn(
                "Market / Revenue",
                format="%.1f"
            ),

        "First Power Date":
            st.column_config.DateColumn(
                "COD"
            ),

        "Opportunity Score":
            st.column_config.ProgressColumn(
                "Opportunity Score",
                min_value=0,
                max_value=100,
                format="%.1f"
            ),
    }
)


# ============================================================
# ERCOT AREA SUMMARY
# ============================================================

st.divider()

st.subheader(
    "🗺️ ERCOT Area Summary"
)

st.caption(
    "Broad market-location screen by ERCOT area. "
    "Location affects 30% of Market / Revenue and currently "
    f"{location_market_weight * market_weight:.1%} of the total "
    "Opportunity Score."
)


area_summary = (
    df.groupby(
        "ERCOT Area",
        as_index=False
    )
    .agg(

        Projects=(
            "Power Project Name",
            "count"
        ),

        MW=(
            "Capacity (MW)",
            "sum"
        ),

        Location_Score=(
            "Location Score",
            "mean"
        ),

        Average_Score=(
            "Opportunity Score",
            "mean"
        ),

        Best_Score=(
            "Opportunity Score",
            "max"
        )
    )
)


area_summary = area_summary.sort_values(

    by=[
        "Location_Score",
        "Average_Score"
    ],

    ascending=[
        False,
        False
    ]
)


area_summary_display = area_summary.rename(
    columns={

        "Location_Score":
            "Location Score",

        "Average_Score":
            "Average Score",

        "Best_Score":
            "Best Score",
    }
)


st.dataframe(

    area_summary_display,

    use_container_width=True,

    hide_index=True,

    column_config={

        "MW":
            st.column_config.NumberColumn(
                "MW",
                format="%.0f"
            ),

        "Location Score":
            st.column_config.ProgressColumn(
                "Location Score",
                min_value=0,
                max_value=100,
                format="%.0f"
            ),

        "Average Score":
            st.column_config.NumberColumn(
                "Average Score",
                format="%.1f"
            ),

        "Best Score":
            st.column_config.NumberColumn(
                "Best Score",
                format="%.1f"
            ),
    }
)


# ============================================================
# BUNDLE OPPORTUNITIES
# ============================================================

st.divider()

st.subheader(
    "📦 Bundle Opportunities"
)

st.caption(
    "Owners with at least two 50–60 MW projects. "
    "Bundles are ranked by average Opportunity Score."
)


bundle_candidates = df[
    df[
        "Capacity (MW)"
    ].between(
        50,
        60,
        inclusive="both"
    )
].copy()


bundle_summary = (
    bundle_candidates
    .groupby(
        "Owner",
        as_index=False
    )
    .agg(

        Bundle_Projects=(
            "Power Project Name",
            "count"
        ),

        Bundle_MW=(
            "Capacity (MW)",
            "sum"
        ),

        Average_Score=(
            "Opportunity Score",
            "mean"
        ),

        Best_Score=(
            "Opportunity Score",
            "max"
        )
    )
)


bundle_summary = bundle_summary[
    bundle_summary[
        "Bundle_Projects"
    ] >= 2
].copy()


bundle_summary = bundle_summary.sort_values(

    by=[
        "Average_Score",
        "Best_Score",
        "Bundle_MW"
    ],

    ascending=[
        False,
        False,
        False
    ]

).reset_index(
    drop=True
)


bundle_summary.insert(
    0,
    "Bundle Rank",
    np.arange(
        1,
        len(
            bundle_summary
        )
        + 1
    )
)


if bundle_summary.empty:

    st.info(
        "No owners currently have multiple "
        "50–60 MW projects."
    )

else:

    bundle_summary_display = bundle_summary.rename(
        columns={

            "Bundle_Projects":
                "Projects",

            "Bundle_MW":
                "Total MW",

            "Average_Score":
                "Average Score",

            "Best_Score":
                "Best Score",
        }
    )

    st.dataframe(

        bundle_summary_display,

        use_container_width=True,

        hide_index=True,

        column_config={

            "Bundle Rank":
                st.column_config.NumberColumn(
                    "Rank"
                ),

            "Average Score":
                st.column_config.ProgressColumn(
                    "Average Score",
                    min_value=0,
                    max_value=100,
                    format="%.1f"
                ),

            "Best Score":
                st.column_config.ProgressColumn(
                    "Best Score",
                    min_value=0,
                    max_value=100,
                    format="%.1f"
                ),

            "Total MW":
                st.column_config.NumberColumn(
                    "Total MW",
                    format="%.1f MW"
                ),
        }
    )


    for _, bundle in bundle_summary.iterrows():

        bundle_owner = bundle[
            "Owner"
        ]

        bundle_rank = int(
            bundle[
                "Bundle Rank"
            ]
        )

        bundle_count = int(
            bundle[
                "Bundle_Projects"
            ]
        )

        bundle_mw = bundle[
            "Bundle_MW"
        ]

        bundle_avg = bundle[
            "Average_Score"
        ]


        owner_projects = (
            bundle_candidates[
                bundle_candidates[
                    "Owner"
                ]
                == bundle_owner
            ]
            .sort_values(
                "Opportunity Score",
                ascending=False
            )
        )


        with st.expander(
            f"#{bundle_rank} 📦 {bundle_owner} — "
            f"{bundle_count} projects | "
            f"{bundle_mw:,.1f} MW | "
            f"Avg Score {bundle_avg:.1f}"
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

                col

                for col in bundle_columns

                if col in owner_projects.columns
            ]


            st.dataframe(

                owner_projects[
                    bundle_columns
                ],

                use_container_width=True,

                hide_index=True,

                column_config={

                    "Distress Score":
                        st.column_config.NumberColumn(
                            "Seller Motivation"
                        ),

                    "Development Stage":
                        st.column_config.NumberColumn(
                            "Development Stage",
                            format="%.1f"
                        ),

                    "Location Score":
                        st.column_config.NumberColumn(
                            "Location",
                            format="%.0f"
                        ),

                    "First Power Date":
                        st.column_config.DateColumn(
                            "COD"
                        ),

                    "Opportunity Score":
                        st.column_config.ProgressColumn(
                            "Opportunity Score",
                            min_value=0,
                            max_value=100,
                            format="%.1f"
                        ),
                }
            )


# ============================================================
# SCORE BREAKDOWN
# ============================================================

st.divider()

st.subheader(
    "🔎 Score Breakdown"
)


if len(
    filtered
) > 0:

    selected_project = st.selectbox(
        "Select a Project",
        filtered[
            "Power Project Name"
        ].tolist()
    )


    project = filtered[
        filtered[
            "Power Project Name"
        ]
        == selected_project
    ].iloc[
        0
    ]


    # --------------------------------------------------------
    # PROJECT CONTEXT
    # --------------------------------------------------------

    p1, p2, p3, p4, p5 = st.columns(
        5
    )


    p1.metric(
        "ERCOT Area",
        project[
            "ERCOT Area"
        ]
    )


    p2.metric(
        "Location Score",
        f"{project['Location Score']:.0f}"
    )


    p3.metric(
        "COD",
        format_date(
            project.get(
                "First Power Date"
            )
        )
    )


    p4.metric(
        "Capacity",
        f"{project['Capacity (MW)']:,.1f} MW"
    )


    p5.metric(
        "Status",
        clean_text(
            project.get(
                "Power Project Status"
            )
        )
    )


    st.caption(
        f"ISO Zone: "
        f"{clean_text(project.get('ISO Zone'))}"
    )


    if has_value(
        project.get(
            "Point of Interconnection"
        )
    ):

        st.caption(
            f"Point of Interconnection: "
            f"{project['Point of Interconnection']}"
        )


    # --------------------------------------------------------
    # MARKET / REVENUE DETAIL
    # --------------------------------------------------------

    st.markdown(
        "#### Market / Revenue"
    )


    m1, m2, m3 = st.columns(
        3
    )


    m1.metric(
        "Revenue Visibility",
        f"{project['Revenue Visibility']:.1f}"
    )


    m2.metric(
        "Location Score",
        f"{project['Location Score']:.1f}"
    )


    m3.metric(
        "Market / Revenue Score",
        f"{project['Market / Revenue']:.1f}"
    )


    st.caption(
        f"Market / Revenue = "
        f"{project['Revenue Visibility']:.1f} × "
        f"{revenue_visibility_weight:.0%} + "
        f"{project['Location Score']:.1f} × "
        f"{location_market_weight:.0%} = "
        f"{project['Market / Revenue']:.1f}"
    )


    # --------------------------------------------------------
    # OVERALL SCORE COMPONENTS
    # --------------------------------------------------------

    st.markdown(
        "#### Opportunity Score"
    )


    s1, s2, s3, s4, s5 = st.columns(
        5
    )


    s1.metric(
        "Seller Motivation",
        f"{project['Distress Score']:.1f}"
    )


    s2.metric(
        "Development Stage",
        f"{project['Development Stage']:.1f}"
    )


    s3.metric(
        "Market / Revenue",
        f"{project['Market / Revenue']:.1f}"
    )


    s4.metric(
        "Acquisition Value",
        f"{project['Acquisition Value']:.1f}"
    )


    s5.metric(
        "Executability",
        f"{project['Executability']:.1f}"
    )


    st.metric(
        "Total Opportunity Score",
        f"{project['Opportunity Score']:.2f}"
    )


    # --------------------------------------------------------
    # EXECUTABILITY DETAIL
    # --------------------------------------------------------

    st.markdown(
        "#### Executability Detail"
    )


    e1, e2, e3, e4 = st.columns(
        4
    )


    e1.metric(
        "Seller Actionability",
        f"{project['Actionability Score']:.1f}"
    )


    e2.metric(
        "Timing Score",
        f"{project['Timing Score']:.1f}"
    )


    e3.metric(
        "Development Stage",
        f"{project['Development Stage']:.1f}"
    )


    e4.metric(
        "Executability",
        f"{project['Executability']:.1f}"
    )


    st.caption(
        f"Executability = "
        f"{project['Actionability Score']:.1f} × "
        f"{actionability_weight:.0%} + "
        f"{project['Timing Score']:.1f} × "
        f"{timing_exec_weight:.0%} + "
        f"{project['Development Stage']:.1f} × "
        f"{development_exec_weight:.0%} = "
        f"{project['Executability']:.1f}"
    )


    # --------------------------------------------------------
    # MANAGEMENT READOUT
    # --------------------------------------------------------

    st.markdown(
        "#### Management Readout"
    )


    r1, r2 = st.columns(
        2
    )


    r1.info(
        f"**Why it ranks:**\n\n"
        f"{project['Why It Ranks']}"
    )


    r2.warning(
        f"**Key risk:**\n\n"
        f"{project['Key Risk']}"
    )


# ============================================================
# OWNER OPPORTUNITY SUMMARY
# ============================================================

st.divider()

st.subheader(
    "Owner Opportunity Summary"
)


owner_summary = (
    df.groupby(
        "Owner",
        as_index=False
    )
    .agg(

        Projects=(
            "Power Project Name",
            "count"
        ),

        MW=(
            "Capacity (MW)",
            "sum"
        ),

        Average_Score=(
            "Opportunity Score",
            "mean"
        ),

        Best_Score=(
            "Opportunity Score",
            "max"
        ),
    )
)


owner_summary = owner_summary.sort_values(

    by=[
        "Best_Score",
        "Average_Score"
    ],

    ascending=[
        False,
        False
    ]
)


owner_summary_display = owner_summary.rename(
    columns={

        "Average_Score":
            "Average Score",

        "Best_Score":
            "Best Score",
    }
)


st.dataframe(

    owner_summary_display.head(
        25
    ),

    use_container_width=True,

    hide_index=True,

    column_config={

        "Average Score":
            st.column_config.NumberColumn(
                "Average Score",
                format="%.1f"
            ),

        "Best Score":
            st.column_config.ProgressColumn(
                "Best Score",
                min_value=0,
                max_value=100,
                format="%.1f"
            ),
    }
)


# ============================================================
# DOWNLOAD
# ============================================================

st.divider()


csv = df.to_csv(
    index=False
).encode(
    "utf-8"
)


st.download_button(

    "⬇️ Download Scored ERCOT Universe",

    data=csv,

    file_name="ERCOT_Scored_Acquisition_Universe.csv",

    mime="text/csv"
)
