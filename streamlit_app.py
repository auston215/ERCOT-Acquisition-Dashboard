import html as html_lib
import re
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import date, timezone
from email.utils import parsedate_to_datetime

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
    layout="wide"
)

st.title("⚡ ERCOT Acquisition Dashboard")

st.caption(
    "M&A screening tool for ERCOT solar, battery storage, "
    "and operating wind projects"
)

SELLER_REFRESH_SECONDS = 6 * 60 * 60
SELLER_LOOKBACK_DAYS = 180


# ============================================================
# HELPERS
# ============================================================
def clean_text(value):
    return "" if pd.isna(value) else str(value).strip()


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

    return re.sub(
        r"\s+",
        " ",
        html_lib.unescape(
            text
        )
    ).strip()


def map_ercot_area(value):

    zone = clean_text(
        value
    )

    return {

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

    }.get(
        zone,
        zone if zone else "Unknown"
    )


def field_value_table(
    row,
    fields
):

    output = []

    for field in fields:

        if field not in row.index:
            continue

        value = row.get(
            field
        )

        if isinstance(
            value,
            (
                pd.Timestamp,
                np.datetime64
            )
        ):

            value = format_date(
                value
            )

        else:

            value = (
                clean_text(
                    value
                )
                or "N/A"
            )

        output.append(
            {
                "Field":
                    field,

                "Value":
                    value
            }
        )

    return pd.DataFrame(
        output
    )


# ============================================================
# SIDEBAR — DATA
# ============================================================
st.sidebar.header(
    "1. Data"
)

uploaded_file = st.sidebar.file_uploader(
    "Upload latest Orennia CSV",
    type=[
        "csv"
    ]
)

st.sidebar.divider()


# ============================================================
# SIDEBAR — OPPORTUNITY SCORE WEIGHTS
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
        f"Weights currently total "
        f"{total_weight:.0%}. "
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


if abs(
    revenue_visibility_weight
    + location_market_weight
    - 1.0
) > 0.001:

    st.sidebar.warning(
        "Market / Revenue mix should equal 100%."
    )


# ------------------------------------------------------------
# ACQUISITION VALUE
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


if abs(
    actionability_weight
    + timing_exec_weight
    + development_exec_weight
    - 1.0
) > 0.001:

    st.sidebar.warning(
        "Executability mix should equal 100%."
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
        distress_1
}


confidence_score_map = {
    "High":
        confidence_high,

    "Medium":
        confidence_medium,

    "Low":
        confidence_low
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
        20
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
        location_unknown
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

    return round(
        discount_score_map.get(
            potential,
            distress_none
        )
        *
        confidence_score_map.get(
            clean_text(
                confidence
            ),
            confidence_low
        ),
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

        return actionability_points.get(
            int(
                value
            ),
            50
        )

    except Exception:

        return 50


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
# SELLER ASSUMPTIONS
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


if "seller_assumptions" not in st.session_state:

    st.session_state[
        "seller_assumptions"
    ] = seller_signals.copy()


# ============================================================
# MAIN TABS
# ============================================================
dashboard_tab, map_tab = st.tabs(
    [
        "📊 Acquisition Dashboard",
        "🗺️ Map Explorer"
    ]
)


# ============================================================
# NO FILE
# ============================================================
if uploaded_file is None:

    with dashboard_tab:

        st.info(
            "Upload the latest Orennia Power Projects CSV "
            "using the sidebar to populate the dashboard."
        )

    with map_tab:

        st.info(
            "Upload the latest Orennia CSV with Latitude "
            "and Longitude fields to populate the Map Explorer."
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
    "Power Project Status"
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


for col in [
    "Queue Date",
    "Contract Execution Date",
    "Contract Termination Date"
]:

    if col in df.columns:

        df[
            col
        ] = pd.to_datetime(
            df[
                col
            ],
            errors="coerce"
        )


for col in [
    "Contract Capacity (MW)",
    "Contract Term Years (Year)",
    "Distance to Brownfield Sites (Miles)",
    "Interconnection Cost Physical ($)",
    "Interconnection Cost System Upgrade ($)",
    "Interconnection Cost Total ($)",
    "Latitude (Degrees)",
    "Longitude (Degrees)"
]:

    if col in df.columns:

        df[
            col
        ] = pd.to_numeric(
            df[
                col
            ],
            errors="coerce"
        )


# ============================================================
# OPTIONAL ORENNIA FIELDS
# ============================================================
optional_diligence_columns = [
    "Equipment Manufacturer",
    "Equipment Model",
    "EPC",
    "Integrator"
]


available_diligence_columns = [
    col

    for col in optional_diligence_columns

    if col in df.columns
]


optional_interconnection_columns = [
    "Interconnection Service Type",
    "Queue Cycle",
    "Queue Date",
    "Interconnection Cost Physical ($)",
    "Interconnection Cost System Upgrade ($)",
    "Interconnection Cost Total ($)"
]


available_interconnection_columns = [
    col

    for col in optional_interconnection_columns

    if col in df.columns
]


optional_contract_columns = [
    "Contract Execution Date",
    "Contract Termination Date",
    "Contract Term Years (Year)"
]


available_contract_columns = [
    col

    for col in optional_contract_columns

    if col in df.columns
]


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
# Solar = all stages
# Storage = all stages
# Wind = Operating only
# ============================================================
df = df[
    df[
        "Power Project Type"
    ].isin(
        [
            "Solar",
            "Storage"
        ]
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
    "Mesquite Solar"
]


df = df[
    ~df[
        "Power Project Name"
    ].isin(
        excluded_projects
    )
].copy()


# ============================================================
# DASHBOARD GUIDE
# ============================================================
with dashboard_tab:

    st.markdown(
        "## 📘 Dashboard Guide"
    )

    left, right = st.columns(
        [
            1.55,
            1
        ]
    )


    with left:

        st.markdown(
            "### 🎯 Opportunity Score"
        )

        st.caption(
            "Projects are scored from 0–100 to prioritize "
            "attractive and actionable acquisition opportunities."
        )


        st.dataframe(
            pd.DataFrame(
                {
                    "Factor":
                        [
                            "Seller Motivation",
                            "Development Stage",
                            "Market / Revenue",
                            "Acquisition Value",
                            "Executability"
                        ],

                    "Weight":
                        [
                            f"{distress_weight:.0%}",
                            f"{development_weight:.0%}",
                            f"{market_weight:.0%}",
                            f"{value_weight:.0%}",
                            f"{exec_weight:.0%}"
                        ],

                    "What It Measures":
                        [
                            "Likelihood owner is motivated to transact",
                            "Project maturity and progress through development",
                            "Revenue visibility + ERCOT location",
                            "Tax-credit / siting attributes",
                            "Ability to realistically execute a transaction"
                        ]
                }
            ),

            use_container_width=True,

            hide_index=True
        )


        st.markdown(
            "#### Formula"
        )


        st.markdown(
            f"""
            **Opportunity Score =
            Seller Motivation × {distress_weight:.0%}
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


        ex_seller = (
            distress_4
            * confidence_high
        )

        ex_dev = (
            development_operating
        )

        ex_market = (
            market_both
            * revenue_visibility_weight

            +

            location_north
            * location_market_weight
        )

        ex_value = (
            value_tax
        )

        ex_exec = (
            100
            * actionability_weight

            +

            timing_operating
            * timing_exec_weight

            +

            ex_dev
            * development_exec_weight
        )

        ex_total = (
            ex_seller
            * distress_weight

            +

            ex_dev
            * development_weight

            +

            ex_market
            * market_weight

            +

            ex_value
            * value_weight

            +

            ex_exec
            * exec_weight
        )


        st.markdown(
            "#### Example"
        )


        st.dataframe(
            pd.DataFrame(
                {
                    "Factor":
                        [
                            "Seller Motivation",
                            "Development Stage",
                            "Market / Revenue",
                            "Acquisition Value",
                            "Executability"
                        ],

                    "Score":
                        [
                            ex_seller,
                            ex_dev,
                            ex_market,
                            ex_value,
                            ex_exec
                        ],

                    "Why":
                        [
                            "Discount Potential 4 = 80; High Confidence = 100%",
                            "Operating project = 100",
                            f"Revenue visibility {market_both:.0f}; "
                            f"ERCOT-N {location_north:.0f}",
                            "Tax Credit only = 70",
                            "Actionability + Timing + Development Stage"
                        ]
                }
            ),

            use_container_width=True,

            hide_index=True
        )


        st.success(
            f"Example Opportunity Score = "
            f"{ex_total:.1f}"
        )


    with right:

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
            **7. Map Explorer** — Visualize and filter the ERCOT opportunity set
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


        st.dataframe(
            pd.DataFrame(
                {
                    "Area":
                        [
                            "ERCOT-N",
                            "ERCOT-H",
                            "ERCOT-S",
                            "ERCOT-W",
                            "Panhandle"
                        ],

                    "Score":
                        [
                            location_north,
                            location_houston,
                            location_south,
                            location_west,
                            location_panhandle
                        ]
                }
            ),

            use_container_width=True,

            hide_index=True
        )


        st.caption(
            "Location is a broad screening proxy. "
            "Node-level congestion, basis, curtailment and "
            "market fundamentals can materially differ within each area."
        )


    # --------------------------------------------------------
    # FULL SCORE LOGIC
    # --------------------------------------------------------
    with st.expander(
        "📐 View Full Score Logic",
        expanded=False
    ):

        st.markdown(
            "#### Seller Motivation"
        )


        st.dataframe(
            pd.DataFrame(
                {
                    "Discount Potential":
                        [
                            "5 – Very High",
                            "4 – High",
                            "3 – Moderate",
                            "2 – Low",
                            "1 – Very Low",
                            "No Signal"
                        ],

                    "Base Score":
                        [
                            distress_5,
                            distress_4,
                            distress_3,
                            distress_2,
                            distress_1,
                            distress_none
                        ]
                }
            ),

            use_container_width=True,

            hide_index=True
        )


        st.dataframe(
            pd.DataFrame(
                {
                    "Confidence":
                        [
                            "High",
                            "Medium",
                            "Low"
                        ],

                    "Multiplier":
                        [
                            f"{confidence_high:.0%}",
                            f"{confidence_medium:.0%}",
                            f"{confidence_low:.0%}"
                        ]
                }
            ),

            use_container_width=True,

            hide_index=True
        )


        st.markdown(
            "#### Development Stage"
        )


        st.dataframe(
            pd.DataFrame(
                {
                    "Stage":
                        [
                            "Operating / Construction Complete",
                            ">50% Construction",
                            "In Construction",
                            "IA Executed",
                            "FIS Completed",
                            "FIS Started",
                            "Studies Undergoing / Other",
                            "Pre-Study",
                            "Inactive / Suspended / Retired"
                        ],

                    "Score":
                        [
                            development_operating,
                            development_50,
                            development_construction,
                            development_ia,
                            development_fis_complete,
                            development_fis_started,
                            development_studies,
                            development_pre,
                            development_inactive
                        ]
                }
            ),

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


        st.dataframe(
            pd.DataFrame(
                {
                    "Revenue Visibility":
                        [
                            "Contract + Named Offtaker",
                            "Named Offtaker Only",
                            "Contract Only",
                            "Neither"
                        ],

                    "Score":
                        [
                            market_both,
                            market_offtaker,
                            market_contract,
                            market_none
                        ]
                }
            ),

            use_container_width=True,

            hide_index=True
        )


        st.dataframe(
            pd.DataFrame(
                {
                    "ERCOT Area":
                        [
                            "ERCOT-N",
                            "ERCOT-H",
                            "ERCOT-S",
                            "ERCOT-W",
                            "Panhandle",
                            "Unknown / Other"
                        ],

                    "Location Score":
                        [
                            location_north,
                            location_houston,
                            location_south,
                            location_west,
                            location_panhandle,
                            location_unknown
                        ]
                }
            ),

            use_container_width=True,

            hide_index=True
        )


        st.markdown(
            "#### Acquisition Value"
        )


        st.dataframe(
            pd.DataFrame(
                {
                    "Attributes":
                        [
                            "Tax Credit + Energy Community",
                            "Tax Credit Only",
                            "Energy Community Only",
                            "Neither"
                        ],

                    "Score":
                        [
                            value_both,
                            value_tax,
                            value_ec,
                            value_none
                        ]
                }
            ),

            use_container_width=True,

            hide_index=True
        )


        st.caption(
            "Domestic Content is not included in the automated score "
            "because Orennia does not currently expose project-level "
            "Domestic Content qualification or bonus fields. "
            "Equipment information can be used as a diligence reference "
            "but is not treated as evidence of qualification."
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
        f"{location_market_weight * market_weight:.1%} "
        "of the total Opportunity Score under the current assumptions."
    )


    st.caption(
        "Screening tool only — rankings prioritize sourcing and "
        "diligence activity and are not a substitute for full "
        "investment underwriting."
    )


    st.divider()


# ============================================================
# SELLER ASSUMPTIONS EDITOR
# ============================================================
with dashboard_tab:

    st.subheader(
        "Seller Motivation / Actionability Assumptions"
    )


    st.caption(
        "These assumptions drive the project rankings. "
        "Public seller intelligence below is informational only "
        "and does not automatically change project scores."
    )


    current_sellers = st.session_state[
        "seller_assumptions"
    ].copy()


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
            "Confidence"
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
                )
        }
    )


editable_seller_columns = [
    "Owner",
    "Discount Potential",
    "Seller Actionability",
    "Confidence"
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
    ]
    .copy()
)


edited_sellers[
    "Owner Key"
] = (
    edited_sellers[
        "Owner"
    ]
    .astype(
        str
    )
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
# PUBLIC SELLER INTELLIGENCE
# INFORMATIONAL ONLY — DOES NOT CHANGE SCORE
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
        "Greenbacker Renewable Energy Company"
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


SELLER_SIGNAL_RULES = [

    (
        "Formal Sale / Strategic Review",

        [
            "strategic review",
            "strategic alternatives",
            "sale process",
            "portfolio sale",
            "asset sale",
            "exploring a sale",
            "divestiture"
        ],

        5,
        5
    ),

    (
        "Restructuring / Financial Stress",

        [
            "bankruptcy",
            "chapter 11",
            "restructuring",
            "default",
            "distressed",
            "liquidity crisis",
            "going concern"
        ],

        5,
        4
    ),

    (
        "Capital Recycling / Monetization",

        [
            "capital recycling",
            "asset monetization",
            "monetization",
            "sell-down",
            "sell down",
            "stake sale"
        ],

        4,
        5
    ),

    (
        "Layoffs / Cost Reduction",

        [
            "layoffs",
            "layoff",
            "job cuts",
            "workforce reduction",
            "headcount reduction"
        ],

        4,
        3
    ),

    (
        "Project Cancellation / Portfolio Pressure",

        [
            "project cancellation",
            "project cancellations",
            "cancelled project",
            "canceled project",
            "project impairment",
            "impairment charge"
        ],

        4,
        3
    )
]


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


    url = (
        "https://news.google.com/rss/search?q="
        + urllib.parse.quote_plus(
            query
        )
        + "&hl=en-US&gl=US&ceid=US:en"
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

            root = ET.fromstring(
                response.read()
            )


        for item in root.findall(
            ".//item"
        ):

            published = pd.NaT

            raw = clean_text(
                item.findtext(
                    "pubDate"
                )
            )


            if raw:

                try:

                    parsed = parsedate_to_datetime(
                        raw
                    )

                    if parsed.tzinfo is None:

                        parsed = parsed.replace(
                            tzinfo=timezone.utc
                        )

                    published = pd.Timestamp(
                        parsed
                    )

                except Exception:
                    pass


            articles.append(
                {
                    "Title":
                        clean_text(
                            item.findtext(
                                "title"
                            )
                        ),

                    "Description":
                        strip_html(
                            item.findtext(
                                "description"
                            )
                        ),

                    "Source":
                        clean_text(
                            item.findtext(
                                "source"
                            )
                        ),

                    "Published":
                        published,

                    "URL":
                        clean_text(
                            item.findtext(
                                "link"
                            )
                        )
                }
            )


    except Exception:

        return []


    return articles


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


    for (
        signal_type,
        keywords,
        motivation,
        actionability
    ) in SELLER_SIGNAL_RULES:

        if any(
            keyword in text
            for keyword in keywords
        ):

            return {
                "Signal Type":
                    signal_type,

                "Suggested Motivation":
                    motivation,

                "Suggested Actionability":
                    actionability
            }


    return None


def build_advisory_seller_intelligence():

    rows = []


    for _, seller in edited_sellers.iterrows():

        owner = clean_text(
            seller.get(
                "Owner"
            )
        )


        if not owner:
            continue


        classified = []


        for article in fetch_company_news(
            SELLER_SEARCH_TERMS.get(
                owner,
                owner
            )
        ):

            rule = classify_article(
                article.get(
                    "Title"
                ),
                article.get(
                    "Description"
                )
            )


            if rule:

                classified.append(
                    {
                        **article,
                        **rule
                    }
                )


        if classified:

            def sort_date(
                article
            ):

                value = article.get(
                    "Published"
                )


                if pd.isna(
                    value
                ):

                    return pd.Timestamp.min


                timestamp = pd.Timestamp(
                    value
                )


                if timestamp.tzinfo is not None:

                    return timestamp.tz_localize(
                        None
                    )


                return timestamp


            latest = sorted(
                classified,
                key=sort_date,
                reverse=True
            )[0]


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
                        ]
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
                        ""
                }
            )


    return pd.DataFrame(
        rows
    )


with dashboard_tab:

    with st.expander(
        "📡 Public Seller Intelligence — Informational Only",
        expanded=False
    ):

        st.caption(
            "This feed monitors recent public seller signals and "
            "provides a suggested direction for review. "
            "It does NOT change the Seller Motivation or Actionability "
            "assumptions above and therefore does not automatically "
            "alter project rankings."
        )


        if st.button(
            "🔄 Refresh Public Signals",
            key="refresh_public_signals"
        ):

            fetch_company_news.clear()

            st.rerun()


        st.dataframe(
            build_advisory_seller_intelligence(),

            use_container_width=True,

            hide_index=True,

            column_config={

                "Current Motivation":
                    st.column_config.NumberColumn(
                        format="%.0f"
                    ),

                "Current Actionability":
                    st.column_config.NumberColumn(
                        format="%.0f"
                    ),

                "Suggested Motivation":
                    st.column_config.NumberColumn(
                        format="%.0f"
                    ),

                "Suggested Actionability":
                    st.column_config.NumberColumn(
                        format="%.0f"
                    ),

                "Signal Date":
                    st.column_config.DateColumn(
                        "Signal Date"
                    ),

                "Article":
                    st.column_config.LinkColumn(
                        "Article"
                    )
            }
        )


    st.divider()


# ============================================================
# MAP SELLER ASSUMPTIONS TO PROJECTS
# ============================================================
def get_seller_value(
    owner,
    column
):

    return seller_lookup.get(
        owner_key(
            owner
        ),
        {}
    ).get(
        column,
        np.nan
    )


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


    if (
        "More Than 50%" in detailed
        or ">50%" in detailed
    ):

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


# ============================================================
# REVENUE VISIBILITY SCORE
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


# ============================================================
# ENERGY COMMUNITY
#
# Existing scoring logic preserved for ranking consistency.
# ============================================================
def energy_community(
    row
):

    for col in [
        "Fossil Fuel Energy Communities",
        "Retired Coal Facilities Energy Communities",
        "Low Income Communities",
        "Native American Lands"
    ]:

        if (
            col in row.index
            and clean_text(
                row[
                    col
                ]
            ).lower()
            in [
                "true",
                "yes",
                "1"
            ]
        ):

            return "Yes"


    return "No"


# ============================================================
# ACQUISITION VALUE
# ============================================================
def acquisition_value(
    row
):

    tax = has_value(
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


    if tax and ec:

        return value_both


    if tax:

        return value_tax


    if ec:

        return value_ec


    return value_none


# ============================================================
# TIMING
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


# ============================================================
# COMPLETENESS
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
        or has_value(
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


# ============================================================
# RUN SCORING
# ============================================================
df[
    "Development Stage"
] = df.apply(
    development_stage_score,
    axis=1
)


df[
    "Revenue Visibility"
] = df.apply(
    revenue_visibility_score,
    axis=1
)


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


df[
    "Energy Community"
] = df.apply(
    energy_community,
    axis=1
)


df[
    "Acquisition Value"
] = df.apply(
    acquisition_value,
    axis=1
)


df[
    "Domestic Content Review"
] = "Unknown / Diligence Required"


df[
    "Timing Score"
] = df.apply(
    timing_score,
    axis=1
)


df[
    "Actionability Score"
] = df[
    "Seller Actionability"
].apply(
    actionability_score
)


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


df[
    "Data Completeness"
] = df.apply(
    completeness,
    axis=1
)


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
).round(
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


    if row[
        "Opportunity Score"
    ] >= 80:

        return "CONTACT / DILIGENCE"


    if row[
        "Opportunity Score"
    ] >= 70:

        return "INVESTIGATE"


    if row[
        "Opportunity Score"
    ] >= 60:

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
    [
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
# MANAGEMENT READOUT
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


    if (
        not pd.isna(
            row.get(
                "Capacity (MW)"
            )
        )
        and row[
            "Capacity (MW)"
        ] >= 100
    ):

        reasons.append(
            f"{row['Capacity (MW)']:,.0f} MW scale"
        )


    return "; ".join(
        (
            reasons
            or [
                "Strong composite Opportunity Score"
            ]
        )[:3]
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


    return "; ".join(
        (
            risks
            or [
                "No major screen-level issue; full diligence still required"
            ]
        )[:2]
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
# ACQUISITION DASHBOARD
# ============================================================
with dashboard_tab:

    # --------------------------------------------------------
    # KPIs
    # --------------------------------------------------------
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


    # --------------------------------------------------------
    # MANAGEMENT SHORTLIST
    # --------------------------------------------------------
    st.divider()

    st.subheader(
        "🎯 Management Shortlist"
    )


    st.caption(
        "Top five current acquisition priorities "
        "based on the screening model."
    )


    shortlist = df.head(
        5
    ).copy()


    shortlist[
        "Management Rank"
    ] = np.arange(
        1,
        len(
            shortlist
        )
        + 1
    )


    cols = [
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
        "Recommended Action"
    ]


    st.dataframe(
        shortlist[
            [
                col

                for col in cols

                if col in shortlist.columns
            ]
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
                )
        }
    )


    # --------------------------------------------------------
    # FILTERS
    # --------------------------------------------------------
    st.divider()

    st.subheader(
        "Filters"
    )


    f1, f2, f3, f4 = st.columns(
        4
    )


    tech_opts = sorted(
        df[
            "Power Project Type"
        ]
        .dropna()
        .unique()
    )


    selected_technology = f1.multiselect(
        "Technology",
        tech_opts,
        default=tech_opts,
        key="dashboard_technology"
    )


    area_opts = sorted(
        df[
            "ERCOT Area"
        ]
        .dropna()
        .unique()
    )


    selected_ercot_areas = f2.multiselect(
        "ERCOT Area",
        area_opts,
        default=area_opts,
        key="dashboard_ercot_area"
    )


    owner_opts = sorted(
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
        owner_opts,
        key="dashboard_owner"
    )


    status_opts = sorted(
        df[
            "Power Project Status"
        ]
        .dropna()
        .unique()
    )


    selected_status = f4.multiselect(
        "Project Status",
        status_opts,
        default=status_opts,
        key="dashboard_status"
    )


    filtered = df[
        df[
            "Power Project Type"
        ].isin(
            selected_technology
        )

        &

        df[
            "ERCOT Area"
        ].isin(
            selected_ercot_areas
        )

        &

        df[
            "Power Project Status"
        ].isin(
            selected_status
        )
    ].copy()


    if selected_owners:

        filtered = filtered[
            filtered[
                "Owner"
            ].isin(
                selected_owners
            )
        ]


    # --------------------------------------------------------
    # TOP ACQUISITION TARGETS
    # --------------------------------------------------------
    st.divider()

    st.subheader(
        "🏆 Top Acquisition Targets"
    )


    st.caption(
        "Top 20 projects based on Opportunity Score."
    )


    display_cols = [
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
        "Action"
    ]


    st.dataframe(
        filtered[
            [
                col

                for col in display_cols

                if col in filtered.columns
            ]
        ].head(
            20
        ),

        use_container_width=True,

        hide_index=True,

        column_config={

            "Distress Score":
                st.column_config.NumberColumn(
                    "Seller Motivation"
                ),

            "Development Stage":
                st.column_config.NumberColumn(
                    format="%.1f"
                ),

            "Revenue Visibility":
                st.column_config.NumberColumn(
                    format="%.1f"
                ),

            "Location Score":
                st.column_config.NumberColumn(
                    "Location",
                    format="%.0f"
                ),

            "Market / Revenue":
                st.column_config.NumberColumn(
                    format="%.1f"
                ),

            "Opportunity Score":
                st.column_config.ProgressColumn(
                    min_value=0,
                    max_value=100,
                    format="%.1f"
                ),

            "First Power Date":
                st.column_config.DateColumn(
                    "COD"
                )
        }
    )


    # --------------------------------------------------------
    # TOP PROJECTS BY TECHNOLOGY
    # --------------------------------------------------------
    st.divider()

    st.subheader(
        "⚡ Top Projects by Technology"
    )


    selected_tech_rank = st.selectbox(
        "Select Technology",
        sorted(
            df[
                "Power Project Type"
            ]
            .dropna()
            .unique()
        ),
        key="technology_ranking"
    )


    tech_ranked = df[
        df[
            "Power Project Type"
        ]
        == selected_tech_rank
    ].sort_values(
        [
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


    tech_ranked[
        "Technology Rank"
    ] = np.arange(
        1,
        len(
            tech_ranked
        )
        + 1
    )


    a, b, c = st.columns(
        3
    )


    a.metric(
        f"{selected_tech_rank} Projects",
        len(
            tech_ranked
        )
    )


    b.metric(
        f"{selected_tech_rank} Capacity",
        f"{tech_ranked['Capacity (MW)'].sum():,.0f} MW"
    )


    if len(
        tech_ranked
    ):

        c.metric(
            "Top Technology Score",
            f"{tech_ranked['Opportunity Score'].max():.1f}"
        )


    tech_cols = [
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
        "Action"
    ]


    st.dataframe(
        tech_ranked[
            [
                col

                for col in tech_cols

                if col in tech_ranked.columns
            ]
        ].head(
            20
        ),

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
                    min_value=0,
                    max_value=100,
                    format="%.1f"
                )
        }
    )


    # --------------------------------------------------------
    # ERCOT AREA SUMMARY
    # --------------------------------------------------------
    st.divider()

    st.subheader(
        "🗺️ ERCOT Area Summary"
    )


    st.caption(
        "Broad market-location screen by ERCOT area. "
        f"Location currently represents "
        f"{location_market_weight * market_weight:.1%} "
        "of the total Opportunity Score."
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
        .sort_values(
            [
                "Location_Score",
                "Average_Score"
            ],
            ascending=[
                False,
                False
            ]
        )
        .rename(
            columns={
                "Location_Score":
                    "Location Score",

                "Average_Score":
                    "Average Score",

                "Best_Score":
                    "Best Score"
            }
        )
    )


    st.dataframe(
        area_summary,

        use_container_width=True,

        hide_index=True,

        column_config={

            "MW":
                st.column_config.NumberColumn(
                    format="%.0f"
                ),

            "Location Score":
                st.column_config.ProgressColumn(
                    min_value=0,
                    max_value=100,
                    format="%.0f"
                ),

            "Average Score":
                st.column_config.NumberColumn(
                    format="%.1f"
                ),

            "Best Score":
                st.column_config.NumberColumn(
                    format="%.1f"
                )
        }
    )


    # --------------------------------------------------------
    # BUNDLE OPPORTUNITIES
    # --------------------------------------------------------
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
        ]
        >= 2
    ].sort_values(
        [
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

        st.dataframe(
            bundle_summary.rename(
                columns={
                    "Bundle_Projects":
                        "Projects",

                    "Bundle_MW":
                        "Total MW",

                    "Average_Score":
                        "Average Score",

                    "Best_Score":
                        "Best Score"
                }
            ),

            use_container_width=True,

            hide_index=True
        )


        for _, bundle in bundle_summary.iterrows():

            owner_projects = (
                bundle_candidates[
                    bundle_candidates[
                        "Owner"
                    ]
                    == bundle[
                        "Owner"
                    ]
                ]
                .sort_values(
                    "Opportunity Score",
                    ascending=False
                )
            )


            with st.expander(
                f"#{int(bundle['Bundle Rank'])} 📦 "
                f"{bundle['Owner']} — "
                f"{int(bundle['Bundle_Projects'])} projects | "
                f"{bundle['Bundle_MW']:,.1f} MW | "
                f"Avg Score "
                f"{bundle['Average_Score']:.1f}"
            ):

                bundle_cols = [
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
                    "Action"
                ]


                st.dataframe(
                    owner_projects[
                        [
                            col

                            for col in bundle_cols

                            if col in owner_projects.columns
                        ]
                    ],

                    use_container_width=True,

                    hide_index=True
                )


    # --------------------------------------------------------
    # SCORE BREAKDOWN
    # --------------------------------------------------------
    st.divider()

    st.subheader(
        "🔎 Score Breakdown"
    )


    if len(
        filtered
    ):

        selectable = filtered.copy()


        selectable[
            "Selection Label"
        ] = selectable.apply(
            lambda row:
                f"{clean_text(row.get('Power Project Name'))} — "
                f"{clean_text(row.get('Owner')) or 'Unknown Owner'} — "
                f"{clean_text(row.get('Generator ID')) or clean_text(row.get('Queue ID')) or 'No ID'}",
            axis=1
        )


        selected_label = st.selectbox(
            "Select a Project",
            selectable[
                "Selection Label"
            ].tolist(),
            key="score_breakdown_project"
        )


        project = selectable[
            selectable[
                "Selection Label"
            ]
            == selected_label
        ].iloc[
            0
        ]


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
                project[
                    "First Power Date"
                ]
            )
        )


        p4.metric(
            "Capacity",
            f"{project['Capacity (MW)']:,.1f} MW"
        )


        p5.metric(
            "Status",
            clean_text(
                project[
                    "Power Project Status"
                ]
            )
        )


        st.caption(
            f"ISO Zone: "
            f"{clean_text(project.get('ISO Zone')) or 'N/A'}"
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


        # ----------------------------------------------------
        # TAX CREDIT REVIEW
        # ----------------------------------------------------
        st.markdown(
            "#### Tax Credit Review"
        )


        t1, t2, t3 = st.columns(
            3
        )


        t1.metric(
            "PTC / ITC",
            clean_text(
                project.get(
                    "PTC/ITC"
                )
            )
            or "Not Identified"
        )


        t2.metric(
            "Energy Community Screen",
            project[
                "Energy Community"
            ]
        )


        t3.metric(
            "Domestic Content",
            project[
                "Domestic Content Review"
            ]
        )


        st.caption(
            "Domestic Content is not automatically scored. "
            "Orennia does not currently provide a native "
            "project-level Domestic Content qualification field, "
            "so qualification requires project-specific diligence."
        )


        # ----------------------------------------------------
        # EQUIPMENT
        # ----------------------------------------------------
        if available_diligence_columns:

            with st.expander(
                "🏗️ Equipment / EPC Diligence",
                expanded=False
            ):

                st.dataframe(
                    field_value_table(
                        project,
                        available_diligence_columns
                    ),

                    use_container_width=True,

                    hide_index=True
                )


                st.caption(
                    "Equipment manufacturer, model, EPC and integrator "
                    "data may help prioritize Domestic Content diligence "
                    "but are not treated as proof of Domestic Content "
                    "qualification."
                )


        # ----------------------------------------------------
        # INTERCONNECTION
        # ----------------------------------------------------
        if available_interconnection_columns:

            with st.expander(
                "🔌 Interconnection Snapshot",
                expanded=False
            ):

                st.dataframe(
                    field_value_table(
                        project,

                        [
                            "Queue ID",
                            "Point of Interconnection",
                            *available_interconnection_columns
                        ]
                    ),

                    use_container_width=True,

                    hide_index=True
                )


        # ----------------------------------------------------
        # CONTRACT
        # ----------------------------------------------------
        if available_contract_columns:

            with st.expander(
                "📄 Contract Detail",
                expanded=False
            ):

                st.dataframe(
                    field_value_table(
                        project,

                        [
                            "Contract Type",
                            "Contract Capacity (MW)",
                            "Contract Offtaker",
                            "Contract Offtaker 2",
                            "Contract Offtaker 3",
                            "Contract Offtaker 4",
                            *available_contract_columns
                        ]
                    ),

                    use_container_width=True,

                    hide_index=True
                )


        # ----------------------------------------------------
        # MANAGEMENT READOUT
        # ----------------------------------------------------
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


    # --------------------------------------------------------
    # OWNER SUMMARY
    # --------------------------------------------------------
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
            )
        )
        .sort_values(
            [
                "Best_Score",
                "Average_Score"
            ],

            ascending=[
                False,
                False
            ]
        )
        .rename(
            columns={
                "Average_Score":
                    "Average Score",

                "Best_Score":
                    "Best Score"
            }
        )
    )


    st.dataframe(
        owner_summary.head(
            25
        ),

        use_container_width=True,

        hide_index=True
    )


    # --------------------------------------------------------
    # DOWNLOAD
    # --------------------------------------------------------
    st.divider()


    st.download_button(
        "⬇️ Download Scored ERCOT Universe",

        df.to_csv(
            index=False
        ).encode(
            "utf-8"
        ),

        "ERCOT_Scored_Acquisition_Universe.csv",

        "text/csv",

        key="download_scored_universe"
    )


# ============================================================
# MAP EXPLORER
# ============================================================
with map_tab:

    st.markdown(
        "## 🗺️ ERCOT Map Explorer"
    )


    st.caption(
        "Interactive geographic view of the scored ERCOT acquisition "
        "universe. Filters in this tab are independent from the main "
        "dashboard filters."
    )


    # --------------------------------------------------------
    # CHECK LAT / LONG
    # --------------------------------------------------------
    if (
        "Latitude (Degrees)" not in df.columns
        or
        "Longitude (Degrees)" not in df.columns
    ):

        st.error(
            "The uploaded Orennia file does not contain "
            "Latitude (Degrees) and Longitude (Degrees), "
            "so the map cannot be rendered."
        )


    else:

        map_base = df.copy()


        map_base[
            "map_lat"
        ] = pd.to_numeric(
            map_base[
                "Latitude (Degrees)"
            ],
            errors="coerce"
        )


        map_base[
            "map_lon"
        ] = pd.to_numeric(
            map_base[
                "Longitude (Degrees)"
            ],
            errors="coerce"
        )


        map_base = map_base.dropna(
            subset=[
                "map_lat",
                "map_lon"
            ]
        )


        if map_base.empty:

            st.warning(
                "No valid project coordinates are available "
                "in the uploaded file."
            )


        else:

            # =================================================
            # MAP FILTERS
            # =================================================
            st.markdown(
                "### Filters"
            )


            mf1, mf2, mf3, mf4 = st.columns(
                4
            )


            map_tech_opts = sorted(
                map_base[
                    "Power Project Type"
                ]
                .dropna()
                .unique()
            )


            map_tech = mf1.multiselect(
                "Technology",
                map_tech_opts,
                default=map_tech_opts,
                key="map_technology"
            )


            map_area_opts = sorted(
                map_base[
                    "ERCOT Area"
                ]
                .dropna()
                .unique()
            )


            map_area = mf2.multiselect(
                "ERCOT Area",
                map_area_opts,
                default=map_area_opts,
                key="map_ercot_area"
            )


            map_owner_opts = sorted(
                [
                    owner

                    for owner in map_base[
                        "Owner"
                    ].unique()

                    if clean_text(
                        owner
                    )
                ]
            )


            map_owners = mf3.multiselect(
                "Owner",
                map_owner_opts,
                key="map_owner"
            )


            map_status_opts = sorted(
                map_base[
                    "Power Project Status"
                ]
                .dropna()
                .unique()
            )


            map_status = mf4.multiselect(
                "Project Status",
                map_status_opts,
                default=map_status_opts,
                key="map_status"
            )


            mf5, mf6, mf7, mf8 = st.columns(
                4
            )


            action_order = [
                "CONTACT / DILIGENCE",
                "INVESTIGATE",
                "MONITOR",
                "RESEARCH / MONITOR",
                "LOW PRIORITY"
            ]


            present_actions = [
                action_name

                for action_name in action_order

                if action_name
                in map_base[
                    "Action"
                ].unique()
            ]


            map_actions = mf5.multiselect(
                "Action",
                present_actions,
                default=present_actions,
                key="map_action"
            )


            # -------------------------------------------------
            # LOCATION SOURCE
            # -------------------------------------------------
            if "Location Source" in map_base.columns:

                source_opts = sorted(
                    map_base[
                        "Location Source"
                    ]
                    .fillna(
                        "Unknown"
                    )
                    .astype(
                        str
                    )
                    .unique()
                )


                map_sources = mf6.multiselect(
                    "Location Source",
                    source_opts,
                    default=source_opts,
                    key="map_location_source"
                )


            else:

                map_sources = []

                mf6.caption(
                    "Location Source not available"
                )


            # -------------------------------------------------
            # COUNTY
            # -------------------------------------------------
            if "County" in map_base.columns:

                county_opts = sorted(
                    [
                        county

                        for county in map_base[
                            "County"
                        ]
                        .fillna(
                            ""
                        )
                        .astype(
                            str
                        )
                        .unique()

                        if clean_text(
                            county
                        )
                    ]
                )


                map_counties = mf7.multiselect(
                    "County",
                    county_opts,
                    key="map_county"
                )


            else:

                map_counties = []

                mf7.caption(
                    "County not available"
                )


            # -------------------------------------------------
            # TAX CREDIT
            # -------------------------------------------------
            if "PTC/ITC" in map_base.columns:

                map_base[
                    "Tax Credit Label"
                ] = (
                    map_base[
                        "PTC/ITC"
                    ]
                    .fillna(
                        "Not Identified"
                    )
                    .replace(
                        "",
                        "Not Identified"
                    )
                    .astype(
                        str
                    )
                )


            else:

                map_base[
                    "Tax Credit Label"
                ] = "Not Identified"


            tax_opts = sorted(
                map_base[
                    "Tax Credit Label"
                ].unique()
            )


            map_tax = mf8.multiselect(
                "Tax Credit",
                tax_opts,
                default=tax_opts,
                key="map_tax_credit"
            )


            # -------------------------------------------------
            # SCORE / CAPACITY / COD FILTERS
            # -------------------------------------------------
            mf9, mf10, mf11 = st.columns(
                [
                    1,
                    1.4,
                    1.4
                ]
            )


            map_min_score = mf9.slider(
                "Minimum Opportunity Score",
                min_value=0.0,
                max_value=100.0,
                value=0.0,
                step=1.0,
                key="map_min_score"
            )


            cap_min = float(
                np.floor(
                    map_base[
                        "Capacity (MW)"
                    ].min()
                )
            )


            cap_max = float(
                np.ceil(
                    map_base[
                        "Capacity (MW)"
                    ].max()
                )
            )


            map_capacity_range = mf10.slider(
                "Capacity Range (MW)",
                min_value=cap_min,
                max_value=cap_max,
                value=(
                    cap_min,
                    cap_max
                ),
                step=1.0,
                key="map_capacity_range"
            )


            valid_cod = map_base[
                "First Power Date"
            ].dropna()


            if len(
                valid_cod
            ):

                cod_min = valid_cod.min().date()

                cod_max = valid_cod.max().date()


                map_cod_range = mf11.date_input(
                    "COD Range",
                    value=(
                        cod_min,
                        cod_max
                    ),
                    min_value=cod_min,
                    max_value=cod_max,
                    key="map_cod_range"
                )


            else:

                map_cod_range = None

                mf11.caption(
                    "COD dates not available"
                )


            include_missing_cod = st.checkbox(
                "Include projects with missing COD",
                value=True,
                key="map_include_missing_cod"
            )


            # =================================================
            # APPLY MAP FILTERS
            # =================================================
            map_filtered = map_base[
                map_base[
                    "Power Project Type"
                ].isin(
                    map_tech
                )

                &

                map_base[
                    "ERCOT Area"
                ].isin(
                    map_area
                )

                &

                map_base[
                    "Power Project Status"
                ].isin(
                    map_status
                )

                &

                map_base[
                    "Action"
                ].isin(
                    map_actions
                )

                &

                map_base[
                    "Tax Credit Label"
                ].isin(
                    map_tax
                )

                &

                (
                    map_base[
                        "Opportunity Score"
                    ]
                    >= map_min_score
                )

                &

                map_base[
                    "Capacity (MW)"
                ].between(
                    map_capacity_range[
                        0
                    ],
                    map_capacity_range[
                        1
                    ],
                    inclusive="both"
                )
            ].copy()


            if map_owners:

                map_filtered = map_filtered[
                    map_filtered[
                        "Owner"
                    ].isin(
                        map_owners
                    )
                ]


            if (
                "Location Source"
                in map_filtered.columns
                and map_sources
            ):

                map_filtered = map_filtered[
                    map_filtered[
                        "Location Source"
                    ]
                    .fillna(
                        "Unknown"
                    )
                    .astype(
                        str
                    )
                    .isin(
                        map_sources
                    )
                ]


            if (
                "County"
                in map_filtered.columns
                and map_counties
            ):

                map_filtered = map_filtered[
                    map_filtered[
                        "County"
                    ].isin(
                        map_counties
                    )
                ]


            if (
                map_cod_range is not None
                and len(
                    map_cod_range
                )
                == 2
            ):

                mask = map_filtered[
                    "First Power Date"
                ].between(
                    pd.Timestamp(
                        map_cod_range[
                            0
                        ]
                    ),
                    pd.Timestamp(
                        map_cod_range[
                            1
                        ]
                    ),
                    inclusive="both"
                )


                if include_missing_cod:

                    mask = (
                        mask
                        |
                        map_filtered[
                            "First Power Date"
                        ].isna()
                    )


                map_filtered = map_filtered[
                    mask
                ]


            # =================================================
            # MAP KPIs
            # =================================================
            mk1, mk2, mk3, mk4 = st.columns(
                4
            )


            mk1.metric(
                "Mapped Projects",
                f"{len(map_filtered):,}"
            )


            mk2.metric(
                "Mapped Capacity",
                f"{map_filtered['Capacity (MW)'].sum():,.0f} MW"
            )


            mk3.metric(
                "Average Score",
                (
                    f"{map_filtered['Opportunity Score'].mean():.1f}"

                    if len(
                        map_filtered
                    )

                    else "N/A"
                )
            )


            mk4.metric(
                "Contact / Diligence",
                int(
                    (
                        map_filtered[
                            "Action"
                        ]
                        == "CONTACT / DILIGENCE"
                    ).sum()
                )
            )


            if map_filtered.empty:

                st.warning(
                    "No projects match the current "
                    "Map Explorer filters."
                )


            else:

                # =============================================
                # MAP COLORS
                # =============================================
                technology_colors = {

                    "Solar":
                        [
                            245,
                            184,
                            0,
                            190
                        ],

                    "Storage":
                        [
                            30,
                            136,
                            229,
                            190
                        ],

                    "Wind":
                        [
                            52,
                            168,
                            83,
                            190
                        ]
                }


                map_filtered[
                    "map_color"
                ] = map_filtered[
                    "Power Project Type"
                ].apply(
                    lambda x:
                        technology_colors.get(
                            x,
                            [
                                120,
                                120,
                                120,
                                180
                            ]
                        )
                )


                # =============================================
                # MAP SIZE
                # =============================================
                map_filtered[
                    "map_radius"
                ] = (
                    np.sqrt(
                        map_filtered[
                            "Capacity (MW)"
                        ].clip(
                            lower=1
                        )
                    )
                    * 950
                )


                # =============================================
                # TOOLTIP DATA
                # =============================================
                map_filtered[
                    "tooltip_project"
                ] = map_filtered[
                    "Power Project Name"
                ].astype(
                    str
                )


                map_filtered[
                    "tooltip_owner"
                ] = map_filtered[
                    "Owner"
                ].astype(
                    str
                )


                map_filtered[
                    "tooltip_tech"
                ] = map_filtered[
                    "Power Project Type"
                ].astype(
                    str
                )


                map_filtered[
                    "tooltip_mw"
                ] = map_filtered[
                    "Capacity (MW)"
                ].round(
                    1
                )


                map_filtered[
                    "tooltip_score"
                ] = map_filtered[
                    "Opportunity Score"
                ].round(
                    1
                )


                map_filtered[
                    "tooltip_cod"
                ] = map_filtered[
                    "First Power Date"
                ].apply(
                    format_date
                )


                map_filtered[
                    "tooltip_area"
                ] = map_filtered[
                    "ERCOT Area"
                ].astype(
                    str
                )


                map_filtered[
                    "tooltip_status"
                ] = map_filtered[
                    "Power Project Status"
                ].astype(
                    str
                )


                map_filtered[
                    "tooltip_action"
                ] = map_filtered[
                    "Action"
                ].astype(
                    str
                )


                if "Contract Offtaker" in map_filtered.columns:

                    map_filtered[
                        "tooltip_offtaker"
                    ] = map_filtered[
                        "Contract Offtaker"
                    ].apply(
                        lambda x:
                            clean_text(
                                x
                            )
                            or "N/A"
                    )


                else:

                    map_filtered[
                        "tooltip_offtaker"
                    ] = "N/A"


                if "PTC/ITC" in map_filtered.columns:

                    map_filtered[
                        "tooltip_tax"
                    ] = map_filtered[
                        "PTC/ITC"
                    ].apply(
                        lambda x:
                            clean_text(
                                x
                            )
                            or "Not Identified"
                    )


                else:

                    map_filtered[
                        "tooltip_tax"
                    ] = "Not Identified"


                if "Location Source" in map_filtered.columns:

                    map_filtered[
                        "tooltip_location_source"
                    ] = map_filtered[
                        "Location Source"
                    ].apply(
                        lambda x:
                            clean_text(
                                x
                            )
                            or "N/A"
                    )


                else:

                    map_filtered[
                        "tooltip_location_source"
                    ] = "N/A"


                if "County" in map_filtered.columns:

                    map_filtered[
                        "tooltip_county"
                    ] = map_filtered[
                        "County"
                    ].apply(
                        lambda x:
                            clean_text(
                                x
                            )
                            or "N/A"
                    )


                else:

                    map_filtered[
                        "tooltip_county"
                    ] = "N/A"


                # =============================================
                # MAP CENTER / ZOOM
                # =============================================
                lat_center = float(
                    map_filtered[
                        "map_lat"
                    ].mean()
                )


                lon_center = float(
                    map_filtered[
                        "map_lon"
                    ].mean()
                )


                max_span = max(
                    float(
                        map_filtered[
                            "map_lat"
                        ].max()
                        -
                        map_filtered[
                            "map_lat"
                        ].min()
                    ),

                    float(
                        map_filtered[
                            "map_lon"
                        ].max()
                        -
                        map_filtered[
                            "map_lon"
                        ].min()
                    )
                )


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


                # =============================================
                # PYDECK MAP LAYER
                # =============================================
                layer = pdk.Layer(
                    "ScatterplotLayer",

                    data=map_filtered,

                    get_position=
                        "[map_lon, map_lat]",

                    get_radius=
                        "map_radius",

                    get_fill_color=
                        "map_color",

                    get_line_color=
                        [
                            255,
                            255,
                            255,
                            180
                        ],

                    line_width_min_pixels=
                        1,

                    radius_min_pixels=
                        4,

                    radius_max_pixels=
                        20,

                    pickable=
                        True,

                    auto_highlight=
                        True,

                    stroked=
                        True,

                    filled=
                        True
                )


                tooltip = {

                    "html":
                        """
                        <b>{tooltip_project}</b><br/>
                        Owner: {tooltip_owner}<br/>
                        Technology: {tooltip_tech}<br/>
                        Capacity: {tooltip_mw} MW<br/>
                        ERCOT Area: {tooltip_area}<br/>
                        County: {tooltip_county}<br/>
                        Status: {tooltip_status}<br/>
                        COD: {tooltip_cod}<br/>
                        Opportunity Score: {tooltip_score}<br/>
                        Action: {tooltip_action}<br/>
                        Offtaker: {tooltip_offtaker}<br/>
                        PTC / ITC: {tooltip_tax}<br/>
                        Location Source: {tooltip_location_source}
                        """,

                    "style":
                        {
                            "backgroundColor":
                                "rgba(20,20,20,0.92)",

                            "color":
                                "white"
                        }
                }


                deck = pdk.Deck(
                    layers=[
                        layer
                    ],

                    initial_view_state=
                        pdk.ViewState(
                            latitude=
                                lat_center,

                            longitude=
                                lon_center,

                            zoom=
                                zoom,

                            pitch=
                                0
                        ),

                    tooltip=
                        tooltip
                )


                st.caption(
                    "Point size reflects project MW. "
                    "Point color: Solar = yellow, Storage = blue, "
                    "Wind = green. Hover over a point for project details."
                )


                # =============================================
                # LOCATION SOURCE SUMMARY
                # =============================================
                if "Location Source" in map_filtered.columns:

                    counts = (
                        map_filtered[
                            "Location Source"
                        ]
                        .fillna(
                            "Unknown"
                        )
                        .astype(
                            str
                        )
                        .value_counts()
                        .to_dict()
                    )


                    st.caption(
                        "Coordinate quality / source for current map: "
                        +
                        " | ".join(
                            [
                                f"{key}: {value:,}"

                                for key, value
                                in counts.items()
                            ]
                        )
                    )


                # =============================================
                # MAP
                # =============================================
                st.pydeck_chart(
                    deck,

                    use_container_width=True,

                    height=720
                )


                # =============================================
                # RANKED MAP TABLE
                # =============================================
                st.markdown(
                    "### Ranked Projects on Current Map"
                )


                st.caption(
                    "The table below only includes projects "
                    "currently visible under the Map Explorer filters."
                )


                map_cols = [
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
                    "Action"
                ]


                st.dataframe(
                    map_filtered[
                        [
                            col

                            for col in map_cols

                            if col in map_filtered.columns
                        ]
                    ]
                    .sort_values(
                        "Opportunity Score",
                        ascending=False
                    ),

                    use_container_width=True,

                    hide_index=True,

                    height=420,

                    column_config={

                        "Capacity (MW)":
                            st.column_config.NumberColumn(
                                "MW",
                                format="%.1f"
                            ),

                        "First Power Date":
                            st.column_config.DateColumn(
                                "COD"
                            ),

                        "Opportunity Score":
                            st.column_config.ProgressColumn(
                                min_value=0,
                                max_value=100,
                                format="%.1f"
                            )
                    }
                )


                # =============================================
                # DOWNLOAD CURRENT MAP RESULTS
                # =============================================
                st.download_button(
                    "⬇️ Download Current Map Results",

                    map_filtered.to_csv(
                        index=False
                    ).encode(
                        "utf-8"
                    ),

                    "ERCOT_Map_Explorer_Filtered.csv",

                    "text/csv",

                    key="download_map_results"
                )


                # =============================================
                # MAP PROJECT DRILLDOWN
                # =============================================
                st.markdown(
                    "### Project Drilldown"
                )


                map_filtered[
                    "Map Selection Label"
                ] = map_filtered.apply(
                    lambda row:
                        f"{clean_text(row.get('Power Project Name'))} — "
                        f"{clean_text(row.get('Owner')) or 'Unknown Owner'} — "
                        f"{row.get('Capacity (MW)', np.nan):,.1f} MW — "
                        f"{clean_text(row.get('Generator ID')) or clean_text(row.get('Queue ID')) or 'No ID'}",
                    axis=1
                )


                selected_map = st.selectbox(
                    "Select a mapped project",
                    map_filtered[
                        "Map Selection Label"
                    ].tolist(),
                    key="map_project_drilldown"
                )


                map_project = map_filtered[
                    map_filtered[
                        "Map Selection Label"
                    ]
                    == selected_map
                ].iloc[
                    0
                ]


                d1, d2, d3, d4, d5 = st.columns(
                    5
                )


                d1.metric(
                    "Opportunity Score",
                    f"{map_project['Opportunity Score']:.1f}"
                )


                d2.metric(
                    "Action",
                    map_project[
                        "Action"
                    ]
                )


                d3.metric(
                    "MW",
                    f"{map_project['Capacity (MW)']:,.1f}"
                )


                d4.metric(
                    "ERCOT Area",
                    map_project[
                        "ERCOT Area"
                    ]
                )


                d5.metric(
                    "COD",
                    format_date(
                        map_project[
                            "First Power Date"
                        ]
                    )
                )


                st.markdown(
                    f"**{map_project['Power Project Name']}** — "
                    f"{clean_text(map_project['Owner']) or 'Unknown Owner'}"
                )


                drill_left, drill_right = st.columns(
                    2
                )


                # ---------------------------------------------
                # PROJECT / MARKET
                # ---------------------------------------------
                with drill_left:

                    st.markdown(
                        "#### Project / Market"
                    )


                    st.dataframe(
                        field_value_table(
                            map_project,

                            [
                                "Generator Name",
                                "Generator ID",
                                "Power Project Type",
                                "Power Project Status",
                                "Detailed Status",
                                "County",
                                "ISO Zone",
                                "Point of Interconnection",
                                "Price Point Name",
                                "Energy Price Point ID",
                                "Location Source",
                                "Latitude (Degrees)",
                                "Longitude (Degrees)"
                            ]
                        ),

                        use_container_width=True,

                        hide_index=True
                    )


                # ---------------------------------------------
                # COMMERCIAL / TAX
                # ---------------------------------------------
                with drill_right:

                    st.markdown(
                        "#### Commercial / Tax"
                    )


                    st.dataframe(
                        field_value_table(
                            map_project,

                            [
                                "Contract Type",
                                "Contract Capacity (MW)",
                                "Contract Offtaker",
                                "Contract Offtaker 2",
                                "Contract Offtaker 3",
                                "Contract Offtaker 4",

                                *available_contract_columns,

                                "PTC/ITC",
                                "Fossil Fuel Energy Communities",
                                "Retired Coal Facilities Energy Communities",
                                "Low Income Communities",
                                "Native American Lands",
                                "Distance to Brownfield Sites (Miles)",
                                "Energy Community",
                                "Domestic Content Review"
                            ]
                        ),

                        use_container_width=True,

                        hide_index=True
                    )


                # ---------------------------------------------
                # INTERCONNECTION
                # ---------------------------------------------
                with st.expander(
                    "🔌 Interconnection Detail",
                    expanded=False
                ):

                    st.dataframe(
                        field_value_table(
                            map_project,

                            [
                                "Queue ID",
                                "Point of Interconnection",

                                *available_interconnection_columns
                            ]
                        ),

                        use_container_width=True,

                        hide_index=True
                    )


                # ---------------------------------------------
                # EQUIPMENT / EPC
                # ---------------------------------------------
                if available_diligence_columns:

                    with st.expander(
                        "🏗️ Equipment / EPC Diligence",
                        expanded=False
                    ):

                        st.dataframe(
                            field_value_table(
                                map_project,
                                available_diligence_columns
                            ),

                            use_container_width=True,

                            hide_index=True
                        )


                        st.caption(
                            "Equipment data is for diligence only "
                            "and is not treated as proof of "
                            "Domestic Content qualification."
                        )


                # ---------------------------------------------
                # MANAGEMENT READOUT
                # ---------------------------------------------
                st.info(
                    f"**Why it ranks:** "
                    f"{map_project['Why It Ranks']}"
                )


                st.warning(
                    f"**Key risk:** "
                    f"{map_project['Key Risk']}"
                )
