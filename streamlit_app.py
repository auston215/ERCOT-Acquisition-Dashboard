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
    "Distressed M&A screening tool for ERCOT solar and battery storage projects"
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


def safe_date(value):
    try:
        return pd.to_datetime(value)
    except:
        return pd.NaT


def owner_key(value):
    return clean_text(value).lower()


# ------------------------------------------------------------
# SIDEBAR — UPLOAD
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
    step=0.05
)

asset_weight = st.sidebar.number_input(
    "Asset Quality",
    min_value=0.0,
    max_value=1.0,
    value=0.25,
    step=0.05
)

market_weight = st.sidebar.number_input(
    "Market / Revenue",
    min_value=0.0,
    max_value=1.0,
    value=0.15,
    step=0.05
)

value_weight = st.sidebar.number_input(
    "Acquisition Value",
    min_value=0.0,
    max_value=1.0,
    value=0.10,
    step=0.05
)

exec_weight = st.sidebar.number_input(
    "Executability",
    min_value=0.0,
    max_value=1.0,
    value=0.15,
    step=0.05
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
# SIDEBAR — HARD SCORING INPUTS
# ------------------------------------------------------------

st.sidebar.divider()
st.sidebar.header("3. Scoring Inputs")

with st.sidebar.expander("Seller Distress Points"):
    distress_5 = st.number_input("Discount Potential 5", value=100)
    distress_4 = st.number_input("Discount Potential 4", value=80)
    distress_3 = st.number_input("Discount Potential 3", value=60)
    distress_2 = st.number_input("Discount Potential 2", value=40)
    distress_1 = st.number_input("Discount Potential 1", value=20)
    distress_none = st.number_input("No seller signal", value=0)

    confidence_high = st.number_input(
        "High confidence multiplier",
        value=1.00,
        step=0.05
    )

    confidence_medium = st.number_input(
        "Medium confidence multiplier",
        value=0.90,
        step=0.05
    )

    confidence_low = st.number_input(
        "Low confidence multiplier",
        value=0.75,
        step=0.05
    )


with st.sidebar.expander("Asset Quality Points"):
    asset_operating = st.number_input("Operating", value=100)
    asset_50 = st.number_input(">50% Construction", value=92)
    asset_construction = st.number_input("In Construction", value=85)
    asset_ia = st.number_input("IA Executed", value=75)
    asset_fis_complete = st.number_input("FIS Completed", value=65)
    asset_fis_started = st.number_input("FIS Started", value=55)
    asset_studies = st.number_input("Studies Undergoing", value=45)
    asset_pre = st.number_input("Pre-Study", value=35)
    asset_inactive = st.number_input(
        "Inactive / Suspended / Retired",
        value=15
    )


with st.sidebar.expander("Market / Revenue Points"):
    market_both = st.number_input(
        "Contract + named offtaker",
        value=95
    )

    market_offtaker = st.number_input(
        "Named offtaker only",
        value=90
    )

    market_contract = st.number_input(
        "Contract only",
        value=80
    )

    market_none = st.number_input(
        "Neither",
        value=45
    )


with st.sidebar.expander("Acquisition Value Points"):
    value_both = st.number_input(
        "Tax Credit + Energy Community",
        value=75
    )

    value_tax = st.number_input(
        "Tax Credit only",
        value=70
    )

    value_ec = st.number_input(
        "Energy Community only",
        value=60
    )

    value_none = st.number_input(
        "Neither",
        value=55
    )


with st.sidebar.expander("Timing Points"):
    timing_operating = st.number_input(
        "COD reached / passed",
        value=100
    )

    timing_1 = st.number_input(
        "COD within 1 year",
        value=90
    )

    timing_2 = st.number_input(
        "COD within 2 years",
        value=75
    )

    timing_3 = st.number_input(
        "COD within 3 years",
        value=60
    )

    timing_long = st.number_input(
        "COD >3 years",
        value=45
    )

    timing_missing = st.number_input(
        "COD missing",
        value=50
    )


with st.sidebar.expander("Executability Mix"):
    actionability_weight = st.number_input(
        "Seller Actionability %",
        value=0.50,
        step=0.05
    )

    timing_exec_weight = st.number_input(
        "Timing %",
        value=0.30,
        step=0.05
    )

    asset_exec_weight = st.number_input(
        "Asset Quality %",
        value=0.20,
        step=0.05
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

    st.subheader("Seller Distress Assumptions")

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
    col for col in required_columns
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

df["Owner"] = df["Owner"].fillna("")
df["First Power Date"] = pd.to_datetime(
    df["First Power Date"],
    errors="coerce"
)

df["Capacity (MW)"] = pd.to_numeric(
    df["Capacity (MW)"],
    errors="coerce"
)

# Solar + BESS only
df = df[
    df["Power Project Type"].isin(
        ["Solar", "Storage"]
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
# SELLER ASSUMPTIONS — EDITABLE
# ------------------------------------------------------------

st.subheader("Seller Distress / Actionability Assumptions")

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

        value = clean_text(row[col]).lower()

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

    ec = row["Energy Community"] == "Yes"

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

as_of_date = pd.Timestamp(date.today())


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
# SELLER ACTIONABILITY SCORE
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
        has_value(row.get("Contract Type"))
        or has_value(
            row.get("Contract Offtaker")
        )
    ):
        score += 15

    if has_value(row.get("PTC/ITC")):
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

    score = row["Opportunity Score"]

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
# RANK
# ------------------------------------------------------------

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
).reset_index(drop=True)

df["Rank"] = (
    np.arange(len(df)) + 1
)

# ------------------------------------------------------------
# DASHBOARD KPIs
# ------------------------------------------------------------

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

# ------------------------------------------------------------
# FILTERS
# ------------------------------------------------------------

st.subheader("Filters")

f1, f2, f3 = st.columns(3)

technology_options = sorted(
    df["Power Project Type"]
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
    df["Power Project Status"]
    .dropna()
    .unique()
)

selected_status = f3.multiselect(
    "Project Status",
    status_options,
    default=status_options
)

filtered = df[
    df["Power Project Type"]
    .isin(selected_technology)
].copy()

filtered = filtered[
    filtered["Power Project Status"]
    .isin(selected_status)
]

if selected_owners:
    filtered = filtered[
        filtered["Owner"]
        .isin(selected_owners)
    ]

# ------------------------------------------------------------
# TOP TARGETS
# ------------------------------------------------------------

st.subheader("🏆 Top Acquisition Targets")

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

# ------------------------------------------------------------
# SCORE BREAKDOWN
# ------------------------------------------------------------

st.subheader("Score Breakdown")

selected_project = st.selectbox(
    "Select a project",
    filtered["Power Project Name"]
    .tolist()
)

project = filtered[
    filtered["Power Project Name"]
    == selected_project
].iloc[0]

b1, b2, b3, b4, b5 = st.columns(5)

b1.metric(
    "Distress",
    f"{project['Distress Score']:.1f}"
)

b2.metric(
    "Asset",
    f"{project['Asset Quality']:.1f}"
)

b3.metric(
    "Market / Revenue",
    f"{project['Market / Revenue']:.1f}"
)

b4.metric(
    "Acquisition Value",
    f"{project['Acquisition Value']:.1f}"
)

b5.metric(
    "Executability",
    f"{project['Executability']:.1f}"
)

st.metric(
    "Total Opportunity Score",
    f"{project['Opportunity Score']:.2f}"
)

# ------------------------------------------------------------
# OWNER OPPORTUNITY VIEW
# ------------------------------------------------------------

st.subheader("Owner Opportunity Summary")

owner_summary = (
    df.groupby("Owner", as_index=False)
    .agg(
        Projects=("Power Project Name", "count"),
        MW=("Capacity (MW)", "sum"),
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
    "Best_Score",
    ascending=False
)

st.dataframe(
    owner_summary.head(25),
    use_container_width=True,
    hide_index=True
)

# ------------------------------------------------------------
# DOWNLOAD
# ------------------------------------------------------------

st.divider()

csv = df.to_csv(
    index=False
).encode("utf-8")

st.download_button(
    "⬇️ Download Scored ERCOT Universe",
    data=csv,
    file_name="ERCOT_Scored_Acquisition_Universe.csv",
    mime="text/csv"
)
