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
    "Seller Motivation Points
