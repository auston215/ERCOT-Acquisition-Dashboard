import streamlit as st
import pandas as pd
import numpy as np
from datetime import date

# ------------------------------------------------------------
# PAGE SETUP
# ------------------------------------------------------------

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

# ------------------------------------------------------------
# HELPERS
# ------------------------------------------------------------

def clean_text(value):
    if pd.isna(value):
        return ""
    return str(value).strip()


def has_value(value):
    return clean_text(value) != ""


def owner_key(value):
    return clean_text(value).lower()


# ------------------------------------------------------------
# SIDEBAR — DATA
# ------------------------------------------------------------

st.sidebar.header("1. Data")

uploaded_file = st.sidebar.file_uploader(
    "Upload latest Orennia CSV",
    type=["csv"]
)

st.sidebar.divider()

# ------------------------------------------------------------
# SIDEBAR — OPPORTUNITY SCORE WEIGHTS
# ------------------------------------------------------------

st.sidebar.header("2. Opportunity Score Weights")

distress_weight = st.sidebar.number_input(
    "Seller Distress",
    min_value=0.0,
    max_value=1.0,
    value=0.35,
    step=0.05,
    key="distress_weight"
)

asset_weight = st.sidebar.number_input(
    "Asset Quality",
    min_value=0.0,
    max_value=1.0,
    value=0.25,
    step=0.05,
    key="asset_weight"
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
    + asset_weight
    + market_weight
    + value_weight
    + exec_weight
)

if abs(total_weight - 1.0) > 0.001:
    st.sidebar.error(
        f"Weights currently total {total_weight:.0%}. "
        "They should total 100%."
    )
else:
    st.sidebar.success("Weights = 100%")

# ------------------------------------------------------------
# SIDEBAR — SCORING INPUTS
# ------------------------------------------------------------

st.sidebar.divider()
st.sidebar.header("3. Scoring Inputs")

# ------------------------------------------------------------
# SELLER DISTRESS
# ------------------------------------------------------------

with st.sidebar.expander("Seller Distress Points"):

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
        "No seller signal",
        value=0,
        key="distress_none"
    )

    confidence_high = st.number_input(
        "High confidence multiplier",
        value=1.00,
        step=0.05,
        key="confidence_high"
    )

    confidence_medium = st.number_input(
        "Medium confidence multiplier",
        value=0.90,
        step=0.05,
        key="confidence_medium"
    )

    confidence_low = st.number_input(
        "Low confidence multiplier",
        value=0.75,
        step=0.05,
        key="confidence_low"
    )

# ------------------------------------------------------------
# ASSET QUALITY
# ------------------------------------------------------------

with st.sidebar.expander("Asset Quality Points"):

    asset_operating = st.number_input(
        "Operating",
        value=100,
        key="asset_operating"
    )

    asset_50 = st.number_input(
        ">50% Construction",
        value=92,
        key="asset_50"
    )

    asset_construction = st.number_input(
        "In Construction",
        value=85,
        key="asset_construction"
    )

    asset_ia = st.number_input(
        "IA Executed",
        value=75,
        key="asset_ia"
    )

    asset_fis_complete = st.number_input(
        "FIS Completed",
        value=65,
        key="asset_fis_complete"
    )

    asset_fis_started = st.number_input(
        "FIS Started",
        value=55,
        key="asset_fis_started"
    )

    asset_studies = st.number_input(
        "Studies Undergoing",
        value=45,
        key="asset_studies"
    )

    asset_pre = st.number_input(
        "Pre-Study",
        value=35,
        key="asset_pre"
    )

    asset_inactive = st.number_input(
        "Inactive / Suspended / Retired",
        value=15,
        key="asset_inactive"
    )

# ------------------------------------------------------------
# MARKET / REVENUE
# ------------------------------------------------------------

with st.sidebar.expander("Market / Revenue Points"):

    market_both = st.number_input(
        "Contract + named offtaker",
        value=95,
        key="market_both"
    )

    market_offtaker = st.number_input(
        "Named offtaker only",
        value=90,
        key="market_offtaker"
    )

    market_contract = st.number_input(
        "Contract only",
        value=80,
        key="market_contract"
    )

    market_none = st.number_input(
        "Neither contract nor offtaker",
        value=45,
        key="market_none"
    )

# ------------------------------------------------------------
# ACQUISITION VALUE
# ------------------------------------------------------------

with st.sidebar.expander("Acquisition Value Points"):

    value_both = st.number_input(
        "Tax Credit + Energy Community",
        value=75,
        key="value_both"
    )

    value_tax = st.number_input(
        "Tax Credit only",
        value=70,
        key="value_tax"
    )

    value_ec = st.number_input(
        "Energy Community only",
        value=60,
        key="value_ec"
    )

    value_none = st.number_input(
        "Neither tax credit nor Energy Community",
        value=55,
        key="value_none"
    )

# ------------------------------------------------------------
# TIMING
# ------------------------------------------------------------

with st.sidebar.expander("Timing Points"):

    timing_operating = st.number_input(
        "COD reached / passed",
        value=100,
        key="timing_operating"
    )

    timing_1 = st.number_input(
        "COD within 1 year",
        value=90,
        key="timing_1"
    )

    timing_2 = st.number_input(
        "COD within 2 years",
        value=75,
        key="timing_2"
    )

    timing_3 = st.number_input(
        "COD within 3 years",
        value=60,
        key="timing_3"
    )

    timing_long = st.number_input(
        "COD >3 years",
        value=45,
        key="timing_long"
    )

    timing_missing = st.number_input(
        "COD missing",
        value=50,
        key="timing_missing"
    )

# ------------------------------------------------------------
# EXECUTABILITY
# ------------------------------------------------------------

with st.sidebar.expander("Executability Mix"):

    actionability_weight = st.number_input(
        "Seller Actionability %",
        value=0.50,
        step=0.05,
        key="actionability_weight"
    )

    timing_exec_weight = st.number_input(
        "Timing %",
        value=0.30,
        step=0.05,
        key="timing_exec_weight"
    )

    asset_exec_weight = st.number_input(
        "Asset Quality %",
        value=0.20,
        step=0.05,
        key="asset_exec_weight"
    )

# ------------------------------------------------------------
# DEFAULT SELLER SIGNALS
# ------------------------------------------------------------

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
        "Confidence"
    ]
)

# ------------------------------------------------------------
# NO FILE YET
# ------------------------------------------------------------

if uploaded_file is None:

    st.info(
        "Upload your latest Orennia Power Projects CSV using the sidebar."
    )

    st.subheader(
        "Seller Distress / Actionability Assumptions"
    )

    st.dataframe(
        seller_signals,
        use_container_width=True,
        hide_index=True
    )

    st.stop()

# ------------------------------------------------------------
# LOAD DATA
# ------------------------------------------------------------

df = pd.read_csv(uploaded_file)

required_columns = [
    "Power Project Name",
    "Owner",
    "Power Project Type",
    "Capacity (MW)",
    "Queue ID",
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
        + ", ".join(missing_columns)
    )

    st.stop()

# ------------------------------------------------------------
# CLEAN DATA
# ------------------------------------------------------------

df["Owner"] = (
    df["Owner"]
    .fillna("")
)

df["First Power Date"] = pd.to_datetime(
    df["First Power Date"],
    errors="coerce"
)

df["Capacity (MW)"] = pd.to_numeric(
    df["Capacity (MW)"],
    errors="coerce"
)

# ------------------------------------------------------------
# TECHNOLOGY UNIVERSE
#
# Solar   = all stages
# Storage = all stages
# Wind    = Operating only
# ------------------------------------------------------------

df = df[
    (
        df["Power Project Type"].isin(
            ["Solar", "Storage"]
        )
    )
    |
    (
        (df["Power Project Type"] == "Wind")
        &
        (df["Power Project Status"] == "Operating")
    )
].copy()

# ------------------------------------------------------------
# HARD EXCLUSIONS
# ------------------------------------------------------------

df = df[
    ~df["Owner"]
    .str.contains(
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
    ~df["Power Project Name"].isin(
        excluded_projects
    )
].copy()

# ------------------------------------------------------------
# SELLER ASSUMPTIONS
# ------------------------------------------------------------

st.subheader(
    "Seller Distress / Actionability Assumptions"
)

edited_sellers = st.data_editor(
    seller_signals,
    use_container_width=True,
    hide_index=True,
    num_rows="dynamic"
)

edited_sellers["Owner Key"] = (
    edited_sellers["Owner"]
    .astype(str)
    .str.strip()
    .str.lower()
)

seller_lookup = (
    edited_sellers
    .set_index("Owner Key")
    .to_dict("index")
)

# ------------------------------------------------------------
# MAP SELLER ASSUMPTIONS
# ------------------------------------------------------------

def get_seller_value(owner, column):

    key = owner_key(owner)

    if key in seller_lookup:
        return seller_lookup[key].get(column)

    return np.nan


df["Discount Potential"] = df["Owner"].apply(
    lambda x: get_seller_value(
        x,
        "Discount Potential"
    )
)

df["Seller Actionability"] = df["Owner"].apply(
    lambda x: get_seller_value(
        x,
        "Seller Actionability"
    )
)

df["Seller Confidence"] = df["Owner"].apply(
    lambda x: get_seller_value(
        x,
        "Confidence"
    )
)

# ------------------------------------------------------------
# DISTRESS SCORE
# ------------------------------------------------------------

distress_points = {
    5: distress_5,
    4: distress_4,
    3: distress_3,
    2: distress_2,
    1: distress_1,
}

confidence_points = {
    "High": confidence_high,
    "Medium": confidence_medium,
    "Low": confidence_low,
}


def distress_score(row):

    discount = row["Discount Potential"]

    if pd.isna(discount):
        return distress_none

    base = distress_points.get(
        int(discount),
        distress_none
    )

    confidence = row["Seller Confidence"]

    multiplier = confidence_points.get(
        confidence,
        confidence_low
    )

    return base * multiplier


df["Distress Score"] = df.apply(
    distress_score,
    axis=1
)

# ------------------------------------------------------------
# ASSET QUALITY SCORE
# ------------------------------------------------------------

def asset_score(row):

    status = clean_text(
        row.get("Power Project Status")
    )

    detailed = clean_text(
        row.get("Detailed Status")
    )

    if (
        status == "Operating"
        or detailed == "Construction Complete"
    ):
        return asset_operating

    if "More Than 50%" in detailed:
        return asset_50

    if status == "In Construction":
        return asset_construction

    if (
        status == "IA Executed"
        or ", IA" in detailed
    ):
        return asset_ia

    if "FIS Completed" in detailed:
        return asset_fis_complete

    if "FIS Started" in detailed:
        return asset_fis_started

    if status == "Pre-Study":
        return asset_pre

    if status in [
        "Inactive",
        "Suspended",
        "Retired"
    ]:
        return asset_inactive

    return asset_studies


df["Asset Quality"] = df.apply(
    asset_score,
    axis=1
)

# ------------------------------------------------------------
# MARKET / REVENUE SCORE
# ------------------------------------------------------------

def market_score(row):

    contract = has_value(
        row.get("Contract Type")
    )

    offtaker = has_value(
        row.get("Contract Offtaker")
    )

    if contract and offtaker:
        return market_both

    if offtaker:
        return market_offtaker

    if contract:
        return market_contract

    return market_none


df["Market / Revenue"] = df.apply(
    market_score,
    axis=1
)

# ------------------------------------------------------------
# ENERGY COMMUNITY
# ------------------------------------------------------------

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

        value = clean_text(
            row[col]
        ).lower()

        if value in [
            "true",
            "yes",
            "1"
        ]:
            return "Yes"

    return "No"


df["Energy Community"] = df.apply(
    energy_community,
    axis=1
)

# ------------------------------------------------------------
# ACQUISITION VALUE SCORE
# ------------------------------------------------------------

def acquisition_value(row):

    tax_credit = has_value(
        row.get("PTC/ITC")
    )

    ec = (
        row["Energy Community"]
        == "Yes"
    )

    if tax_credit and ec:
        return value_both

    if tax_credit:
        return value_tax

    if ec:
        return value_ec

    return value_none


df["Acquisition Value"] = df.apply(
    acquisition_value,
    axis=1
)

# ------------------------------------------------------------
# TIMING SCORE
# ------------------------------------------------------------

as_of_date = pd.Timestamp(
    date.today()
)


def timing_score(row):

    cod = row["First Power Date"]

    if pd.isna(cod):
        return timing_missing

    days = (
        cod - as_of_date
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


df["Timing Score"] = df.apply(
    timing_score,
    axis=1
)

# ------------------------------------------------------------
# ACTIONABILITY
# ------------------------------------------------------------

actionability_points = {
    5: 100,
    4: 80,
    3: 60,
    2: 40,
    1: 20,
}


def actionability_score(value):

    if pd.isna(value):
        return 50

    return actionability_points.get(
        int(value),
        50
    )


df["Actionability Score"] = (
    df["Seller Actionability"]
    .apply(actionability_score)
)

# ------------------------------------------------------------
# EXECUTABILITY
# ------------------------------------------------------------

df["Executability"] = (
    df["Actionability Score"]
    * actionability_weight
    +
    df["Timing Score"]
    * timing_exec_weight
    +
    df["Asset Quality"]
    * asset_exec_weight
)

# ------------------------------------------------------------
# DATA COMPLETENESS
# ------------------------------------------------------------

def completeness(row):

    score = 0

    if has_value(row.get("Owner")):
        score += 40

    if has_value(row.get("Queue ID")):
        score += 15

    if not pd.isna(
        row.get("First Power Date")
    ):
        score += 15

    if (
        has_value(
            row.get("Contract Type")
        )
        or has_value(
            row.get("Contract Offtaker")
        )
    ):
        score += 15

    if has_value(
        row.get("PTC/ITC")
    ):
        score += 15

    return score


df["Data Completeness"] = df.apply(
    completeness,
    axis=1
)

# ------------------------------------------------------------
# OPPORTUNITY SCORE
# ------------------------------------------------------------

df["Opportunity Score"] = (
    df["Distress Score"]
    * distress_weight
    +
    df["Asset Quality"]
    * asset_weight
    +
    df["Market / Revenue"]
    * market_weight
    +
    df["Acquisition Value"]
    * value_weight
    +
    df["Executability"]
    * exec_weight
)

df["Opportunity Score"] = (
    df["Opportunity Score"]
    .round(2)
)

# ------------------------------------------------------------
# ACTION
# ------------------------------------------------------------

def action(row):

    if pd.isna(
        row["Discount Potential"]
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


df["Action"] = df.apply(
    action,
    axis=1
)

# ------------------------------------------------------------
# OVERALL RANK
# ------------------------------------------------------------

df = (
    df.sort_values(
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
    )
    .reset_index(drop=True)
)

df["Rank"] = (
    np.arange(len(df)) + 1
)

# ============================================================
# MANAGEMENT EXPLANATION LOGIC
# ============================================================

def why_it_ranks(row):

    reasons = []

    # Seller angle
    if row["Distress Score"] >= 70:
        reasons.append(
            "Strong seller motivation / transaction angle"
        )

    elif row["Distress Score"] >= 50:
        reasons.append(
            "Credible seller opportunity"
        )

    # Asset maturity
    if row["Asset Quality"] >= 95:
        reasons.append(
            "Operating / highly mature asset"
        )

    elif row["Asset Quality"] >= 80:
        reasons.append(
            "Advanced-stage project"
        )

    # Revenue
    if row["Market / Revenue"] >= 90:
        reasons.append(
            "Strong visible revenue / offtaker profile"
        )

    elif row["Market / Revenue"] >= 80:
        reasons.append(
            "Some contracted revenue visibility"
        )

    # Acquisition value
    if row["Acquisition Value"] >= 70:
        reasons.append(
            "Attractive tax-credit / siting attributes"
        )

    # Executability
    if row["Executability"] >= 80:
        reasons.append(
            "High execution readiness"
        )

    # Scale
    capacity = row.get(
        "Capacity (MW)",
        np.nan
    )

    if (
        not pd.isna(capacity)
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


def key_risk(row):

    risks = []

    # Seller certainty
    if pd.isna(
        row["Discount Potential"]
    ):
        risks.append(
            "Seller motivation not yet verified"
        )

    elif row["Distress Score"] < 50:
        risks.append(
            "Limited evidence of seller pressure"
        )

    # Asset maturity
    if row["Asset Quality"] < 55:
        risks.append(
            "Early-stage development risk"
        )

    elif row["Asset Quality"] < 75:
        risks.append(
            "Development / execution risk remains"
        )

    # Revenue
    if row["Market / Revenue"] <= 45:
        risks.append(
            "Limited visible revenue certainty"
        )

    elif row["Market / Revenue"] < 90:
        risks.append(
            "Revenue / offtaker visibility is incomplete"
        )

    # COD
    if pd.isna(
        row["First Power Date"]
    ):
        risks.append(
            "COD timing unclear"
        )

    # Data
    if row["Data Completeness"] < 70:
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


df["Why It Ranks"] = df.apply(
    why_it_ranks,
    axis=1
)

df["Key Risk"] = df.apply(
    key_risk,
    axis=1
)

df["Recommended Action"] = df[
    "Action"
]

# ============================================================
# DASHBOARD KPIs
# ============================================================

st.divider()

c1, c2, c3, c4 = st.columns(4)

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
            df["Action"]
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
    "Highest-priority opportunities based on the current "
    "screening assumptions, with an automated investment thesis "
    "and key screen-level risk."
)

management_shortlist = (
    df.head(5)
    .copy()
)

management_shortlist[
    "Management Rank"
] = (
    np.arange(
        len(management_shortlist)
    ) + 1
)

management_columns = [
    "Management Rank",
    "Power Project Name",
    "Owner",
    "Power Project Type",
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

        "Opportunity Score":
            st.column_config.ProgressColumn(
                "Score",
                min_value=0,
                max_value=100,
                format="%.1f"
            ),

        "Why It Ranks":
            st.column_config.TextColumn(
                "Why It Ranks"
            ),

        "Key Risk":
            st.column_config.TextColumn(
                "Key Risk"
            ),

        "Recommended Action":
            st.column_config.TextColumn(
                "Recommended Action"
            ),
    }
)

# ============================================================
# GLOBAL FILTERS
# ============================================================

st.divider()

st.subheader("Filters")

f1, f2, f3 = st.columns(3)

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

owner_options = sorted(
    [
        owner
        for owner in df["Owner"].unique()
        if clean_text(owner)
    ]
)

selected_owners = f2.multiselect(
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

selected_status = f3.multiselect(
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
    "Capacity (MW)",
    "Power Project Status",
    "First Power Date",
    "Contract Type",
    "Contract Offtaker",
    "Distress Score",
    "Asset Quality",
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

top_20 = (
    filtered[
        existing_display_columns
    ]
    .head(20)
)

st.dataframe(
    top_20,
    use_container_width=True,
    hide_index=True,
    column_config={

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

st.caption(
    "Select Solar, Storage, or Wind to view the Top 20 "
    "within that technology."
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
    ] == selected_tech_rank
].copy()

technology_ranked = (
    technology_ranked
    .sort_values(
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
    )
    .reset_index(drop=True)
)

technology_ranked[
    "Technology Rank"
] = (
    np.arange(
        len(technology_ranked)
    ) + 1
)

technology_top_20 = (
    technology_ranked
    .head(20)
)

tech_columns = [
    "Technology Rank",
    "Power Project Name",
    "Owner",
    "Capacity (MW)",
    "Power Project Status",
    "First Power Date",
    "Contract Type",
    "Contract Offtaker",
    "Distress Score",
    "Asset Quality",
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

t1, t2, t3 = st.columns(3)

t1.metric(
    f"{selected_tech_rank} Projects",
    len(technology_ranked)
)

t2.metric(
    f"{selected_tech_rank} Capacity",
    f"{technology_ranked['Capacity (MW)'].sum():,.0f} MW"
)

if len(technology_ranked) > 0:

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
# BUNDLE OPPORTUNITIES
# ============================================================

st.divider()

st.subheader(
    "📦 Bundle Opportunities"
)

st.caption(
    "Owners with at least two ERCOT projects between "
    "50 MW and 60 MW. Bundles are ranked by average "
    "Opportunity Score."
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

bundle_summary = (
    bundle_summary
    .sort_values(
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
    )
    .reset_index(drop=True)
)

bundle_summary.insert(
    0,
    "Bundle Rank",
    np.arange(
        len(bundle_summary)
    ) + 1
)

if bundle_summary.empty:

    st.info(
        "No owners currently have multiple 50–60 MW projects."
    )

else:

    b1, b2, b3 = st.columns(3)

    b1.metric(
        "Potential Bundles",
        len(bundle_summary)
    )

    b2.metric(
        "Projects in Bundles",
        int(
            bundle_summary[
                "Bundle_Projects"
            ].sum()
        )
    )

    b3.metric(
        "Total Bundle MW",
        f"{bundle_summary['Bundle_MW'].sum():,.0f} MW"
    )

    # --------------------------------------------------------
    # BUNDLE SUMMARY
    # --------------------------------------------------------

    st.markdown(
        "#### Bundle Summary"
    )

    bundle_summary_display = (
        bundle_summary
        .rename(
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

    # --------------------------------------------------------
    # PROJECTS WITHIN EACH BUNDLE
    # --------------------------------------------------------

    st.markdown(
        "#### Projects Within Each Bundle"
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
                ] == bundle_owner
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
                "Capacity (MW)",
                "Power Project Type",
                "Power Project Status",
                "First Power Date",
                "Queue ID",
                "Contract Type",
                "Contract Offtaker",
                "Distress Score",
                "Asset Quality",
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
    "Score Breakdown"
)

if len(filtered) > 0:

    selected_project = st.selectbox(
        "Select a project",
        filtered[
            "Power Project Name"
        ].tolist()
    )

    project = filtered[
        filtered[
            "Power Project Name"
        ] == selected_project
    ].iloc[0]

    s1, s2, s3, s4, s5 = st.columns(5)

    s1.metric(
        "Distress",
        f"{project['Distress Score']:.1f}"
    )

    s2.metric(
        "Asset Quality",
        f"{project['Asset Quality']:.1f}"
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

    st.markdown("#### Management Readout")

    r1, r2 = st.columns(2)

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

owner_summary = (
    owner_summary
    .sort_values(
        by=[
            "Best_Score",
            "Average_Score"
        ],
        ascending=[
            False,
            False
        ]
    )
)

owner_summary_display = (
    owner_summary
    .rename(
        columns={

            "Average_Score":
                "Average Score",

            "Best_Score":
                "Best Score",
        }
    )
)

st.dataframe(
    owner_summary_display.head(25),
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

csv = (
    df.to_csv(
        index=False
    )
    .encode("utf-8")
)

st.download_button(
    "⬇️ Download Scored ERCOT Universe",
    data=csv,
    file_name="ERCOT_Scored_Acquisition_Universe.csv",
    mime="text/csv"
)
