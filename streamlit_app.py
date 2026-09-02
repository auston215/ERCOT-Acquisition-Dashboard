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
# SELLER INTELLIGENCE SETTINGS
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
        str(
            value
        )
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
# PUBLIC SELLER INTELLIGENCE
# ============================================================

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
    '"going concern" OR '
    'layoffs OR '
    '"job cuts" OR '
    '"workforce reduction" OR '
    '"project cancellation" OR '
    '"funding gap"'
)


@st.cache_data(
    ttl=SELLER_REFRESH_SECONDS,
    show_spinner=False
)
def fetch_company_news(search_term):

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

            link = clean_text(
                item.findtext(
                    "link"
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
                        parsed.astimezone(
                            timezone.utc
                        )
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


# ============================================================
# SELLER SIGNAL CLASSIFICATION
# ============================================================

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
            "retained advisor",
            "retains advisor",
            "divestiture",
            "divest",
        ],

        "Discount Potential":
            5,

        "Seller Actionability":
            5,

        "Strength":
            5,
    },

    {

        "Signal Type":
            "Restructuring / Severe Financial Stress",

        "Keywords": [

            "bankruptcy",
            "chapter 11",
            "restructuring",
            "debt restructuring",
            "default",
            "covenant breach",
            "distressed",
            "insolvency",
            "going concern",
            "liquidity crisis",
        ],

        "Discount Potential":
            5,

        "Seller Actionability":
            4,

        "Strength":
            5,
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
            "asset rotation",
        ],

        "Discount Potential":
            4,

        "Seller Actionability":
            5,

        "Strength":
            4,
    },

    {

        "Signal Type":
            "Layoffs / Cost Reduction",

        "Keywords": [

            "layoffs",
            "layoff",
            "job cuts",
            "workforce reduction",
            "workforce reductions",
            "headcount reduction",
            "cost reduction",
        ],

        "Discount Potential":
            4,

        "Seller Actionability":
            3,

        "Strength":
            3,
    },

    {

        "Signal Type":
            "Project Cancellation / Portfolio Pressure",

        "Keywords": [

            "project cancellation",
            "project cancellations",
            "cancels project",
            "cancelled project",
            "canceled project",
            "withdraws project",
            "project withdrawal",
            "project impairment",
            "impairment charge",
            "write-down",
            "writedown",
        ],

        "Discount Potential":
            4,

        "Seller Actionability":
            3,

        "Strength":
            4,
    },

    {

        "Signal Type":
            "Funding / Liquidity Need",

        "Keywords": [

            "funding gap",
            "needs financing",
            "seeks financing",
            "seeking financing",
            "liquidity pressure",
            "liquidity concerns",
            "capital need",
            "needs capital",
        ],

        "Discount Potential":
            4,

        "Seller Actionability":
            3,

        "Strength":
            3,
    },
]


TRUSTED_SOURCE_KEYWORDS = [

    "reuters",
    "bloomberg",
    "financial times",
    "wall street journal",
    "s&p global",
    "fitch",
    "moody",
    "sec",
    "utility dive",
    "renewable energy world",
]


def classify_seller_article(
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

    matches = []

    for rule in SELLER_SIGNAL_RULES:

        for keyword in rule[
            "Keywords"
        ]:

            if keyword.lower() in text:

                matches.append(
                    rule
                )

                break

    if not matches:

        return None

    matches = sorted(

        matches,

        key=lambda x:
            x[
                "Strength"
            ],

        reverse=True
    )

    return matches[
        0
    ]


def recency_multiplier(
    published
):

    if pd.isna(
        published
    ):

        return 0.50

    now = pd.Timestamp.now(
        tz="UTC"
    )

    published = pd.Timestamp(
        published
    )

    if published.tzinfo is None:

        published = published.tz_localize(
            "UTC"
        )

    days_old = max(

        0,

        (
            now
            - published
        ).days
    )

    if days_old <= 7:

        return 1.00

    if days_old <= 30:

        return 0.90

    if days_old <= 90:

        return 0.75

    if days_old <= 180:

        return 0.55

    return 0.25


def trusted_source(
    source
):

    source_lower = clean_text(
        source
    ).lower()

    return any(

        keyword in source_lower

        for keyword in TRUSTED_SOURCE_KEYWORDS
    )


def derive_confidence(
    classified_articles
):

    if not classified_articles:

        return "Low"

    top = classified_articles[
        0
    ]

    top_date = top.get(
        "Published"
    )

    recent_30 = False

    if not pd.isna(
        top_date
    ):

        published = pd.Timestamp(
            top_date
        )

        if published.tzinfo is None:

            published = published.tz_localize(
                "UTC"
            )

        age = (

            pd.Timestamp.now(
                tz="UTC"
            )

            - published

        ).days

        recent_30 = (
            age <= 30
        )

    number_of_signals = len(
        classified_articles
    )

    if (
        trusted_source(
            top.get(
                "Source"
            )
        )
        and recent_30
    ):

        return "High"

    if (
        number_of_signals >= 2
        and recent_30
    ):

        return "High"

    if number_of_signals >= 1:

        return "Medium"

    return "Low"


# ============================================================
# BASELINE SELLER ASSUMPTIONS
# ============================================================

seller_baselines = pd.DataFrame(
    [

        [
            "Birch Creek Energy",
            "Birch Creek Energy",
            5,
            5,
            "Medium"
        ],

        [
            "Birch Creek Development",
            "Birch Creek Energy",
            5,
            5,
            "Medium"
        ],

        [
            "esVolta",
            "esVolta",
            4,
            5,
            "High"
        ],

        [
            "Key Capture Energy",
            "Key Capture Energy",
            4,
            5,
            "High"
        ],

        [
            "Lightsource BP",
            "Lightsource bp",
            3,
            4,
            "High"
        ],

        [
            "Ørsted U.S. Onshore",
            "Orsted U.S. Onshore",
            3,
            4,
            "Medium"
        ],

        [
            "Orsted",
            "Orsted U.S. renewables",
            3,
            4,
            "Medium"
        ],

        [
            "Flatiron Energy",
            "Flatiron Energy",
            2,
            4,
            "High"
        ],

        [
            "Recurrent Energy",
            "Recurrent Energy",
            2,
            2,
            "Medium"
        ],

        [
            "EDF power solutions North America",
            "EDF power solutions North America",
            1,
            1,
            "High"
        ],

        [
            "EDF Renewables",
            "EDF Renewables North America",
            1,
            1,
            "High"
        ],

        [
            "Greenbacker Renewable Energy Company",
            "Greenbacker Renewable Energy Company",
            1,
            1,
            "High"
        ],
    ],

    columns=[

        "Owner",
        "Search Term",
        "Baseline Discount Potential",
        "Baseline Seller Actionability",
        "Baseline Confidence",
    ]
)


# ============================================================
# BUILD LIVE SELLER INTELLIGENCE
# ============================================================

def build_live_seller_intelligence():

    output = []

    for _, baseline in seller_baselines.iterrows():

        owner = baseline[
            "Owner"
        ]

        search_term = baseline[
            "Search Term"
        ]

        articles = fetch_company_news(
            search_term
        )

        classified = []

        for article in articles:

            rule = classify_seller_article(

                article.get(
                    "Title"
                ),

                article.get(
                    "Description"
                )
            )

            if rule is None:

                continue

            recency = recency_multiplier(
                article.get(
                    "Published"
                )
            )

            weighted_strength = (

                rule[
                    "Strength"
                ]

                * recency
            )

            classified.append(
                {

                    **article,

                    "Signal Type":
                        rule[
                            "Signal Type"
                        ],

                    "Discount Potential":
                        rule[
                            "Discount Potential"
                        ],

                    "Seller Actionability":
                        rule[
                            "Seller Actionability"
                        ],

                    "Strength":
                        rule[
                            "Strength"
                        ],

                    "Weighted Strength":
                        weighted_strength,
                }
            )

        classified = sorted(

            classified,

            key=lambda x:
                x[
                    "Weighted Strength"
                ],

            reverse=True
        )

        if classified:

            strongest = classified[
                0
            ]

            confidence = derive_confidence(
                classified
            )

            discount_potential = strongest[
                "Discount Potential"
            ]

            actionability = strongest[
                "Seller Actionability"
            ]

            latest_signal = strongest[
                "Title"
            ]

            signal_type = strongest[
                "Signal Type"
            ]

            signal_date = strongest[
                "Published"
            ]

            source = strongest[
                "Source"
            ]

            source_url = strongest[
                "URL"
            ]

            status = (
                "LIVE SIGNAL"
            )

        else:

            discount_potential = baseline[
                "Baseline Discount Potential"
            ]

            actionability = baseline[
                "Baseline Seller Actionability"
            ]

            confidence = baseline[
                "Baseline Confidence"
            ]

            latest_signal = (
                "No new qualifying public signal — "
                "baseline assumption retained"
            )

            signal_type = (
                "Baseline"
            )

            signal_date = pd.NaT

            source = (
                "Baseline Assumption"
            )

            source_url = ""

            status = (
                "BASELINE"
            )

        output.append(
            {

                "Owner":
                    owner,

                "Auto Discount Potential":
                    discount_potential,

                "Auto Seller Actionability":
                    actionability,

                "Auto Confidence":
                    confidence,

                "Signal Type":
                    signal_type,

                "Latest Signal":
                    latest_signal,

                "Signal Date":
                    signal_date,

                "Source":
                    source,

                "Source URL":
                    source_url,

                "Signal Status":
                    status,
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

st.sidebar.caption(
    "Seller intelligence refreshes from public information "
    "every 6 hours when the app is being used."
)

refresh_seller_intel = st.sidebar.button(
    "🔄 Refresh Seller Intelligence Now"
)

if refresh_seller_intel:

    fetch_company_news.clear()

    st.rerun()

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
    total_weight
    - 1.0
) > 0.001:

    st.sidebar.error(
        f"Weights total "
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

market_mix_total = (

    revenue_visibility_weight
    + location_market_weight
)

if abs(
    market_mix_total
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

    value_tax_ec = st.number_input(
        "Tax Credit + Energy Community",
        value=100,
        key="value_tax_ec"
    )

    value_tax_only = st.number_input(
        "Tax Credit Only",
        value=80,
        key="value_tax_only"
    )

    value_no_tax = st.number_input(
        "No Identified Tax Credit",
        value=50,
        key="value_no_tax"
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
    exec_mix_total
    - 1.0
) > 0.001:

    st.sidebar.warning(
        "Executability mix should equal 100%."
    )


# ============================================================
# SCORE MAPS
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

    multiplier = confidence_score_map.get(
        clean_text(
            confidence
        ),
        confidence_low
    )

    return round(
        base_score
        * multiplier,
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
#
# SELLER INTELLIGENCE IS NO LONGER ABOVE THIS SECTION
# ============================================================

st.markdown(
    "## 📘 Dashboard Guide"
)

guide_left, guide_right = st.columns(
    [
        1.55,
        1
    ]
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

                "Current seller motivation / transaction opportunity",

                "Progress through development and construction",

                "Revenue visibility + ERCOT location",

                "Base tax credit and Energy Community value",

                "Ability to realistically execute the transaction",
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
        **5. Bundles** — Identify portfolio opportunities  
        **6. Score Breakdown** — Drill into individual projects  
        **7. Seller Intelligence** — Review owner-level signals
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
        "Seller Motivation is informed by current public signals "
        "such as strategic reviews, asset-sale activity, "
        "restructuring, layoffs, project cancellations, liquidity "
        "pressure and capital recycling."
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


    st.markdown(
        "#### Development Stage"
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
        f"Revenue Visibility × {revenue_visibility_weight:.0%} "
        f"+ ERCOT Location × {location_market_weight:.0%}"
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
                "Unknown",
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

    acquisition_logic = pd.DataFrame(
        {

            "Tax Position": [
                "Tax Credit + Energy Community",
                "Tax Credit Only",
                "No Identified Tax Credit",
            ],

            "Score": [
                value_tax_ec,
                value_tax_only,
                value_no_tax,
            ],
        }
    )

    st.dataframe(
        acquisition_logic,
        use_container_width=True,
        hide_index=True
    )

    st.caption(
        "Energy Community is not scored independently because "
        "the Energy Community bonus is incremental to an "
        "applicable tax credit. Domestic Content can be "
        "incorporated once that data is available."
    )


    st.markdown(
        "#### Executability"
    )

    st.caption(
        f"Seller Actionability × {actionability_weight:.0%} "
        f"+ Timing × {timing_exec_weight:.0%} "
        f"+ Development Stage × {development_exec_weight:.0%}"
    )


st.caption(
    "Screening tool only — rankings prioritize sourcing and diligence "
    "activity and are not a substitute for full investment underwriting."
)

st.divider()


# ============================================================
# STOP IF NO ORENNIA FILE
# ============================================================

if uploaded_file is None:

    st.info(
        "Upload the latest Orennia Power Projects CSV "
        "to populate the project-level dashboard."
    )

    st.stop()


# ============================================================
# LOAD ORENNIA DATA
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
        "Uploaded file is missing: "
        + ", ".join(
            missing_columns
        )
    )

    st.stop()


# ============================================================
# CLEAN ORENNIA DATA
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
# SELLER INTELLIGENCE & ACTIONABILITY
#
# MOVED BACK DOWN HERE.
# THIS REPLACES THE OLD ASSUMPTIONS TABLE LOCATION.
# ============================================================

st.subheader(
    "📡 Seller Intelligence & Actionability"
)

st.caption(
    "Current public seller signals feed the Seller Motivation and "
    "Seller Actionability scores. Data refreshes every six hours "
    "when the app is in use. Manual overrides can be used for "
    "more current internal market intelligence."
)


with st.spinner(
    "Updating seller intelligence..."
):

    auto_sellers = (
        build_live_seller_intelligence()
    )


# ============================================================
# MANUAL SELLER OVERRIDES
# ============================================================

override_template = pd.DataFrame(
    {

        "Owner":
            seller_baselines[
                "Owner"
            ],

        "Discount Override":
            np.nan,

        "Actionability Override":
            np.nan,

        "Confidence Override":
            "Auto",
    }
)


if "seller_overrides" not in st.session_state:

    st.session_state[
        "seller_overrides"
    ] = override_template.copy()


known_override_owners = set(

    st.session_state[
        "seller_overrides"
    ][
        "Owner"
    ]
)


missing_override_owners = [

    owner

    for owner in seller_baselines[
        "Owner"
    ]

    if owner not in known_override_owners
]


if missing_override_owners:

    additional = pd.DataFrame(
        {

            "Owner":
                missing_override_owners,

            "Discount Override":
                np.nan,

            "Actionability Override":
                np.nan,

            "Confidence Override":
                "Auto",
        }
    )

    st.session_state[
        "seller_overrides"
    ] = pd.concat(
        [

            st.session_state[
                "seller_overrides"
            ],

            additional

        ],

        ignore_index=True
    )


seller_live = auto_sellers.merge(

    st.session_state[
        "seller_overrides"
    ],

    on="Owner",

    how="left"
)


seller_live[
    "Discount Potential"
] = seller_live.apply(

    lambda row:

        row[
            "Discount Override"
        ]

        if not pd.isna(
            row[
                "Discount Override"
            ]
        )

        else row[
            "Auto Discount Potential"
        ],

    axis=1
)


seller_live[
    "Seller Actionability"
] = seller_live.apply(

    lambda row:

        row[
            "Actionability Override"
        ]

        if not pd.isna(
            row[
                "Actionability Override"
            ]
        )

        else row[
            "Auto Seller Actionability"
        ],

    axis=1
)


seller_live[
    "Confidence"
] = seller_live.apply(

    lambda row:

        row[
            "Confidence Override"
        ]

        if clean_text(
            row[
                "Confidence Override"
            ]
        ) not in [
            "",
            "Auto"
        ]

        else row[
            "Auto Confidence"
        ],

    axis=1
)


seller_live[
    "Discount Score"
] = seller_live.apply(

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


seller_live[
    "Actionability Score"
] = seller_live[
    "Seller Actionability"
].apply(
    actionability_score
)


# ============================================================
# COMPACT SELLER INTELLIGENCE TABLE
# ============================================================

seller_display_columns = [

    "Owner",

    "Discount Potential",

    "Discount Score",

    "Seller Actionability",

    "Actionability Score",

    "Confidence",

    "Signal Status",

    "Signal Type",

    "Signal Date",

    "Source",
]


st.dataframe(

    seller_live[
        seller_display_columns
    ],

    use_container_width=True,

    hide_index=True,

    column_config={

        "Discount Potential":
            st.column_config.NumberColumn(
                "Motivation",
                format="%.0f"
            ),

        "Discount Score":
            st.column_config.ProgressColumn(
                "Motivation Score",
                min_value=0,
                max_value=100,
                format="%.0f"
            ),

        "Seller Actionability":
            st.column_config.NumberColumn(
                "Actionability",
                format="%.0f"
            ),

        "Actionability Score":
            st.column_config.ProgressColumn(
                "Actionability Score",
                min_value=0,
                max_value=100,
                format="%.0f"
            ),

        "Signal Date":
            st.column_config.DateColumn(
                "Signal Date"
            ),
    }
)


# ============================================================
# SELLER SIGNAL DETAIL
#
# COLLAPSED BY DEFAULT SO IT IS NOT DISTRACTING
# ============================================================

with st.expander(
    "📰 View Seller Signal Detail",
    expanded=False
):

    detailed_columns = [

        "Owner",

        "Signal Status",

        "Signal Type",

        "Signal Date",

        "Source",

        "Latest Signal",

        "Source URL",
    ]

    st.dataframe(

        seller_live[
            detailed_columns
        ],

        use_container_width=True,

        hide_index=True,

        column_config={

            "Signal Date":
                st.column_config.DateColumn(
                    "Signal Date"
                ),

            "Source URL":
                st.column_config.LinkColumn(
                    "Article"
                ),
        }
    )


# ============================================================
# MANUAL OVERRIDE EDITOR
# ============================================================

with st.expander(
    "✏️ Manual Seller Overrides",
    expanded=False
):

    st.caption(
        "Leave an override blank to use the automated public-data "
        "score. Use an override when internal market intelligence "
        "is more current or reliable."
    )

    edited_overrides = st.data_editor(

        st.session_state[
            "seller_overrides"
        ],

        use_container_width=True,

        hide_index=True,

        key="seller_override_editor",

        disabled=[
            "Owner"
        ],

        column_config={

            "Discount Override":
                st.column_config.NumberColumn(
                    "Motivation Override",
                    min_value=1,
                    max_value=5,
                    step=1
                ),

            "Actionability Override":
                st.column_config.NumberColumn(
                    "Actionability Override",
                    min_value=1,
                    max_value=5,
                    step=1
                ),

            "Confidence Override":
                st.column_config.SelectboxColumn(
                    "Confidence Override",
                    options=[
                        "Auto",
                        "High",
                        "Medium",
                        "Low"
                    ]
                ),
        }
    )

    if not edited_overrides.equals(

        st.session_state[
            "seller_overrides"
        ]
    ):

        st.session_state[
            "seller_overrides"
        ] = edited_overrides

        st.rerun()


st.divider()


# ============================================================
# SELLER LOOKUP
# ============================================================

seller_lookup_df = seller_live[
    [

        "Owner",

        "Discount Potential",

        "Seller Actionability",

        "Confidence",
    ]
].copy()


seller_lookup_df[
    "Owner Key"
] = seller_lookup_df[
    "Owner"
].apply(
    owner_key
)


seller_lookup = seller_lookup_df.set_index(
    "Owner Key"
).to_dict(
    "index"
)


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

    if not tax_credit:

        return value_no_tax

    if ec:

        return value_tax_ec

    return value_tax_only


df[
    "Acquisition Value"
] = df.apply(
    acquisition_value,
    axis=1
)


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


df[
    "Timing Score"
] = df.apply(
    timing_score,
    axis=1
)


# ============================================================
# ACTIONABILITY
# ============================================================

df[
    "Actionability Score"
] = df[
    "Seller Actionability"
].apply(
    actionability_score
)


# ============================================================
# EXECUTABILITY
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
            "Some contracted revenue visibility"
        )

    if row[
        "Location Score"
    ] >= 85:

        reasons.append(
            "Attractive ERCOT market location"
        )

    if row[
        "Acquisition Value"
    ] >= 80:

        reasons.append(
            "Attractive tax-credit attributes"
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
        reasons[
            :3
        ]
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
            "Development / execution risk remains"
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
            "Lower broad-area location score"
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
        risks[
            :2
        ]
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

        "Location Score":
            st.column_config.NumberColumn(
                "Location",
                format="%.0f"
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

        "Recommended Action":
            st.column_config.TextColumn(
                "Action"
            ),
    }
)


# ============================================================
# FILTERS
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


area_options = sorted(

    df[
        "ERCOT Area"
    ]
    .dropna()
    .unique()
)


selected_areas = f2.multiselect(

    "ERCOT Area",

    area_options,

    default=area_options
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

    &

    df[
        "ERCOT Area"
    ].isin(
        selected_areas
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


# ============================================================
# TOP ACQUISITION TARGETS
# ============================================================

st.divider()

st.subheader(
    "🏆 Top Acquisition Targets"
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


st.dataframe(

    filtered[
        existing_display_columns
    ].head(
        20
    ),

    use_container_width=True,

    hide_index=True,

    column_config={

        "First Power Date":
            st.column_config.DateColumn(
                "COD"
            ),

        "Distress Score":
            st.column_config.NumberColumn(
                "Seller Motivation"
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


tech_columns = [

    "Technology Rank",

    "Power Project Name",

    "Owner",

    "ERCOT Area",

    "Location Score",

    "Capacity (MW)",

    "Power Project Status",

    "First Power Date",

    "Development Stage",

    "Market / Revenue",

    "Acquisition Value",

    "Executability",

    "Opportunity Score",

    "Action",
]


st.dataframe(

    technology_ranked[
        tech_columns
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


area_summary = area_summary.rename(
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
    area_summary,
    use_container_width=True,
    hide_index=True
)


# ============================================================
# BUNDLE OPPORTUNITIES
# ============================================================

st.divider()

st.subheader(
    "📦 Bundle Opportunities"
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
        "No owners currently have multiple 50–60 MW projects."
    )

else:

    st.dataframe(
        bundle_summary,
        use_container_width=True,
        hide_index=True
    )


    for _, bundle in bundle_summary.iterrows():

        owner = bundle[
            "Owner"
        ]

        owner_projects = bundle_candidates[
            bundle_candidates[
                "Owner"
            ]
            == owner
        ].sort_values(
            "Opportunity Score",
            ascending=False
        )

        with st.expander(
            f"📦 {owner} — "
            f"{int(bundle['Bundle_Projects'])} projects | "
            f"{bundle['Bundle_MW']:,.1f} MW | "
            f"Avg Score {bundle['Average_Score']:.1f}"
        ):

            bundle_columns = [

                "Power Project Name",

                "ERCOT Area",

                "Capacity (MW)",

                "Power Project Type",

                "Power Project Status",

                "First Power Date",

                "Development Stage",

                "Opportunity Score",

                "Action",
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
    "🔎 Score Breakdown"
)


if len(
    filtered
) > 0:

    selected_project = st.selectbox(

        "Select a Project",

        filtered[
            "Power Project Name"
        ].tolist(),

        key="project_score_breakdown"
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
        "ISO Zone: "
        + clean_text(
            project.get(
                "ISO Zone"
            )
        )
    )


    if has_value(
        project.get(
            "Point of Interconnection"
        )
    ):

        st.caption(
            "Point of Interconnection: "
            + clean_text(
                project.get(
                    "Point of Interconnection"
                )
            )
        )


    # --------------------------------------------------------
    # MARKET / REVENUE
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
        "Market / Revenue",
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
    # OPPORTUNITY SCORE
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
    # EXECUTABILITY
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
# OWNER SUMMARY
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
        )
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


owner_summary = owner_summary.rename(
    columns={

        "Average_Score":
            "Average Score",

        "Best_Score":
            "Best Score",
    }
)


st.dataframe(

    owner_summary.head(
        25
    ),

    use_container_width=True,

    hide_index=True
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

    file_name=(
        "ERCOT_Scored_Acquisition_Universe.csv"
    ),

    mime="text/csv"
)
