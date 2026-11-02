import html as html_lib
import json
import os
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


st.set_page_config(
    page_title="ERCOT Acquisition Dashboard",
    page_icon="⚡",
    layout="wide",
)

st.title("⚡ ERCOT Acquisition Dashboard")
st.caption(
    "M&A screening tool for ERCOT solar, battery storage, "
    "and operating wind projects"
)

SELLER_REFRESH_SECONDS = 6 * 60 * 60
SELLER_LOOKBACK_DAYS = 180


# ============================================================
# GENERAL HELPERS
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

    text = re.sub("<[^>]+>", " ", str(value))
    text = html_lib.unescape(text)

    return re.sub("\\s+", " ", text).strip()


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

    return mapping.get(
        zone,
        zone if zone else "Unknown",
    )


def to_numeric_series(series):
    return pd.to_numeric(
        series,
        errors="coerce",
    )


# ============================================================
# SIDEBAR
# ============================================================

st.sidebar.header("1. Data")

uploaded_file = st.sidebar.file_uploader(
    "Optional: Upload newer Orennia CSV",
    type=["csv"],
)

st.sidebar.caption(
    "Not required to view the Dashboard Guide."
)

st.sidebar.divider()

st.sidebar.header(
    "2. Opportunity Score Weights"
)

distress_weight = st.sidebar.number_input(
    "Seller Motivation",
    min_value=0.0,
    max_value=1.0,
    value=0.35,
    step=0.05,
    key="distress_weight",
)

development_weight = st.sidebar.number_input(
    "Development Stage",
    min_value=0.0,
    max_value=1.0,
    value=0.25,
    step=0.05,
    key="development_weight",
)

market_weight = st.sidebar.number_input(
    "Market / Revenue",
    min_value=0.0,
    max_value=1.0,
    value=0.15,
    step=0.05,
    key="market_weight",
)

value_weight = st.sidebar.number_input(
    "Acquisition Value",
    min_value=0.0,
    max_value=1.0,
    value=0.10,
    step=0.05,
    key="value_weight",
)

exec_weight = st.sidebar.number_input(
    "Executability",
    min_value=0.0,
    max_value=1.0,
    value=0.15,
    step=0.05,
    key="exec_weight",
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
        f"Weights currently total "
        f"{total_weight:.0%}. "
        "They should total 100%."
    )
else:
    st.sidebar.success(
        "Overall Weights = 100%"
    )


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
        key="distress_5",
    )

    distress_4 = st.number_input(
        "Discount Potential 4",
        value=80,
        key="distress_4",
    )

    distress_3 = st.number_input(
        "Discount Potential 3",
        value=60,
        key="distress_3",
    )

    distress_2 = st.number_input(
        "Discount Potential 2",
        value=40,
        key="distress_2",
    )

    distress_1 = st.number_input(
        "Discount Potential 1",
        value=20,
        key="distress_1",
    )

    distress_none = st.number_input(
        "No Seller Signal",
        value=0,
        key="distress_none",
    )

    confidence_high = st.number_input(
        "High Confidence Multiplier",
        value=1.00,
        step=0.05,
        key="confidence_high",
    )

    confidence_medium = st.number_input(
        "Medium Confidence Multiplier",
        value=0.90,
        step=0.05,
        key="confidence_medium",
    )

    confidence_low = st.number_input(
        "Low Confidence Multiplier",
        value=0.75,
        step=0.05,
        key="confidence_low",
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
        key="development_operating",
    )

    development_50 = st.number_input(
        ">50% Construction",
        value=92,
        key="development_50",
    )

    development_construction = st.number_input(
        "In Construction",
        value=85,
        key="development_construction",
    )

    development_ia = st.number_input(
        "IA Executed",
        value=75,
        key="development_ia",
    )

    development_fis_complete = st.number_input(
        "FIS Completed",
        value=65,
        key="development_fis_complete",
    )

    development_fis_started = st.number_input(
        "FIS Started",
        value=55,
        key="development_fis_started",
    )

    development_studies = st.number_input(
        "Studies Undergoing",
        value=45,
        key="development_studies",
    )

    development_pre = st.number_input(
        "Pre-Study",
        value=35,
        key="development_pre",
    )

    development_inactive = st.number_input(
        "Inactive / Suspended / Retired",
        value=15,
        key="development_inactive",
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
        key="market_both",
    )

    market_offtaker = st.number_input(
        "Named Offtaker Only",
        value=80,
        key="market_offtaker_v2",
    )

    market_contract = st.number_input(
        "Contract Type Known",
        value=90,
        key="market_contract_v2",
    )

    market_none = st.number_input(
        "Neither Contract nor Offtaker",
        value=45,
        key="market_none",
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
        key="location_north",
    )

    location_houston = st.number_input(
        "ERCOT-H",
        value=85,
        key="location_houston",
    )

    location_south = st.number_input(
        "ERCOT-S",
        value=70,
        key="location_south",
    )

    location_west = st.number_input(
        "ERCOT-W",
        value=60,
        key="location_west",
    )

    location_panhandle = st.number_input(
        "Panhandle",
        value=50,
        key="location_panhandle",
    )

    location_unknown = st.number_input(
        "Unknown / Other",
        value=50,
        key="location_unknown",
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
        key="revenue_visibility_weight",
    )

    location_market_weight = st.number_input(
        "ERCOT Location %",
        min_value=0.0,
        max_value=1.0,
        value=0.30,
        step=0.05,
        key="location_market_weight",
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
        f"Market / Revenue mix totals "
        f"{market_mix_total:.0%}. "
        "It should equal 100%."
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
        key="value_both",
    )

    value_tax = st.number_input(
        "Tax Credit Only",
        value=70,
        key="value_tax",
    )

    value_ec = st.number_input(
        "Energy Community Only",
        value=60,
        key="value_ec",
    )

    value_none = st.number_input(
        "Neither Tax Credit nor Energy Community",
        value=55,
        key="value_none",
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
        key="timing_operating",
    )

    timing_1 = st.number_input(
        "COD Within 1 Year",
        value=90,
        key="timing_1",
    )

    timing_2 = st.number_input(
        "COD Within 2 Years",
        value=75,
        key="timing_2",
    )

    timing_3 = st.number_input(
        "COD Within 3 Years",
        value=60,
        key="timing_3",
    )

    timing_long = st.number_input(
        "COD >3 Years",
        value=45,
        key="timing_long",
    )

    timing_missing = st.number_input(
        "COD Missing",
        value=50,
        key="timing_missing",
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
        key="actionability_weight",
    )

    timing_exec_weight = st.number_input(
        "Timing %",
        min_value=0.0,
        max_value=1.0,
        value=0.30,
        step=0.05,
        key="timing_exec_weight",
    )

    development_exec_weight = st.number_input(
        "Development Stage %",
        min_value=0.0,
        max_value=1.0,
        value=0.20,
        step=0.05,
        key="development_exec_weight",
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
        f"Executability mix totals "
        f"{exec_mix_total:.0%}. "
        "It should equal 100%."
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


def calculate_discount_score(
    potential,
    confidence,
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
        distress_none,
    )

    confidence_multiplier = (
        confidence_score_map.get(
            clean_text(
                confidence
            ),
            confidence_low,
        )
    )

    return round(
        base_score
        * confidence_multiplier,
        1,
    )


def actionability_score(
    value,
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
        50,
    )


def location_score(
    area,
):

    return location_points.get(
        clean_text(
            area
        ),
        location_unknown,
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
            "Medium",
        ],
        [
            "Birch Creek Development",
            5,
            5,
            "Medium",
        ],
        [
            "esVolta",
            4,
            5,
            "High",
        ],
        [
            "Key Capture Energy",
            4,
            5,
            "High",
        ],
        [
            "Lightsource BP",
            3,
            4,
            "High",
        ],
        [
            "Ørsted U.S. Onshore",
            3,
            4,
            "Medium",
        ],
        [
            "Orsted",
            3,
            4,
            "Medium",
        ],
        [
            "Flatiron Energy",
            2,
            4,
            "High",
        ],
        [
            "Recurrent Energy",
            2,
            2,
            "Medium",
        ],
        [
            "EDF power solutions North America",
            1,
            1,
            "High",
        ],
        [
            "EDF Renewables",
            1,
            1,
            "High",
        ],
        [
            "Greenbacker Renewable Energy Company",
            1,
            1,
            "High",
        ],
    ],
    columns=[
        "Owner",
        "Discount Potential",
        "Seller Actionability",
        "Confidence",
    ],
)


if "seller_assumptions" not in st.session_state:

    st.session_state[
        "seller_assumptions"
    ] = seller_signals.copy()


# ============================================================
# MAIN TABS
# ============================================================

(
    dashboard_tab,
    map_tab,
    competitor_tab,
    price_tab,
) = st.tabs(
    [
        "📊 Acquisition Dashboard",
        "🗺️ Map Explorer",
        "🎯 ERCOT Competitor Due Diligence",
        "📈 ERCOT Market Prices",
    ]
)


# ============================================================
# ERCOT MARKET PRICE HELPERS
# ============================================================

ERCOT_RT_SPP_URL = (
    "https://www.ercot.com/content/cdr/html/"
    "real_time_spp.html"
)

ERCOT_LATEST_LMP_URL = (
    "https://www.ercot.com/content/cdr/html/"
    "hb_lz.html"
)

ERCOT_DAM_SPP_URL = (
    "https://www.ercot.com/content/cdr/html/"
    "dam_spp.html"
)

ERCOT_DAM_MCPC_URL = (
    "https://www.ercot.com/content/cdr/html/"
    "dam_mcpc.html"
)


class ERCOTHTMLTableParser:

    def __init__(self):

        self.tables = []
        self.current_table = None
        self.current_row = None
        self.current_cell = None
        self.in_cell = False

    def feed(
        self,
        html_text,
    ):

        from html.parser import HTMLParser

        parent = self

        class _Parser(
            HTMLParser
        ):

            def handle_starttag(
                self,
                tag,
                attrs,
            ):

                tag = tag.lower()

                if tag == "table":

                    parent.current_table = []

                elif (
                    tag == "tr"
                    and parent.current_table
                    is not None
                ):

                    parent.current_row = []

                elif (
                    tag in [
                        "td",
                        "th",
                    ]
                    and parent.current_row
                    is not None
                ):

                    parent.current_cell = []
                    parent.in_cell = True

                elif (
                    tag == "br"
                    and parent.in_cell
                ):

                    parent.current_cell.append(
                        " "
                    )

            def handle_data(
                self,
                data,
            ):

                if (
                    parent.in_cell
                    and parent.current_cell
                    is not None
                ):

                    parent.current_cell.append(
                        data
                    )

            def handle_endtag(
                self,
                tag,
            ):

                tag = tag.lower()

                if (
                    tag in [
                        "td",
                        "th",
                    ]
                    and parent.in_cell
                ):

                    value = re.sub(
                        "\\s+",
                        " ",
                        "".join(
                            parent.current_cell
                        ),
                    ).strip()

                    parent.current_row.append(
                        value
                    )

                    parent.current_cell = None
                    parent.in_cell = False

                elif (
                    tag == "tr"
                    and parent.current_row
                    is not None
                ):

                    if any(
                        clean_text(
                            x
                        )
                        for x
                        in parent.current_row
                    ):

                        parent.current_table.append(
                            parent.current_row
                        )

                    parent.current_row = None

                elif (
                    tag == "table"
                    and parent.current_table
                    is not None
                ):

                    if parent.current_table:

                        parent.tables.append(
                            parent.current_table
                        )

                    parent.current_table = None

        parser = _Parser()

        parser.feed(
            html_text
        )


def parse_ercot_html_table(
    html_text,
    required_columns,
):

    parser = ERCOTHTMLTableParser()

    parser.feed(
        html_text
    )

    required_columns = list(
        required_columns
    )

    for table_rows in parser.tables:

        for header_index, row in enumerate(
            table_rows
        ):

            header = [
                re.sub(
                    "\\s+",
                    " ",
                    clean_text(
                        value
                    ),
                ).strip()

                for value
                in row
            ]

            if not all(
                required
                in header
                for required
                in required_columns
            ):

                continue

            width = len(
                header
            )

            data_rows = []

            for data_row in table_rows[
                header_index + 1:
            ]:

                values = [
                    re.sub(
                        "\\s+",
                        " ",
                        clean_text(
                            value
                        ),
                    ).strip()

                    for value
                    in data_row
                ]

                if len(
                    values
                ) < width:

                    values = (
                        values
                        + [""]
                        * (
                            width
                            - len(
                                values
                            )
                        )
                    )

                values = values[
                    :width
                ]

                if not any(
                    values
                ):

                    continue

                if values == header:

                    continue

                data_rows.append(
                    values
                )

            if data_rows:

                return pd.DataFrame(
                    data_rows,
                    columns=header,
                )

    raise ValueError(
        "ERCOT price table was not found "
        "in the returned HTML."
    )


def normalize_ercot_price_table(
    frame,
    time_column,
):

    result = frame.copy()

    if "Oper Day" not in result.columns:

        raise ValueError(
            "ERCOT table is missing Oper Day."
        )

    if time_column not in result.columns:

        raise ValueError(
            f"ERCOT table is missing "
            f"{time_column}."
        )

    result[
        "Oper Day"
    ] = pd.to_datetime(
        result[
            "Oper Day"
        ],
        errors="coerce",
    )

    for column in result.columns:

        if column in [
            "Oper Day",
            time_column,
        ]:

            continue

        cleaned = (
            result[
                column
            ]
            .astype(
                str
            )
            .str.replace(
                ",",
                "",
                regex=False,
            )
            .str.replace(
                "$",
                "",
                regex=False,
            )
            .str.strip()
        )

        result[
            column
        ] = pd.to_numeric(
            cleaned,
            errors="coerce",
        )

    result = result[
        result[
            "Oper Day"
        ].notna()
    ].copy()

    return result


def _download_ercot_html(
    url,
):

    request = urllib.request.Request(
        url,
        headers={
            "User-Agent":
                "Mozilla/5.0 "
                "ERCOT-Acquisition-Dashboard/1.0",

            "Accept":
                "text/html,application/xhtml+xml",
        },
    )

    with urllib.request.urlopen(
        request,
        timeout=15,
    ) as response:

        return response.read().decode(
            "utf-8",
            errors="replace",
        )


def _fetch_first_ercot_table(
    candidate_urls,
    time_column,
    required_columns,
):

    last_error = None

    for url in candidate_urls:

        try:

            html_text = (
                _download_ercot_html(
                    url
                )
            )

            table = (
                parse_ercot_html_table(
                    html_text,
                    required_columns=
                        required_columns,
                )
            )

            table = (
                normalize_ercot_price_table(
                    table,
                    time_column=
                        time_column,
                )
            )

            if not table.empty:

                return (
                    table,
                    url,
                )

        except Exception as exc:

            last_error = exc

    if last_error is not None:

        raise last_error

    raise ValueError(
        "No ERCOT market-price table "
        "was available."
    )


def _ercot_operating_day_urls(
    report_name,
    include_generic=True,
):

    now_central = (
        pd.Timestamp.now(
            tz="America/Chicago"
        )
    )

    today = (
        now_central.normalize()
    )

    yesterday = (
        today
        - pd.Timedelta(
            days=1
        )
    )

    dated_urls = [
        (
            "https://www.ercot.com/"
            "content/cdr/html/"
            f"{day.strftime('%Y%m%d')}_"
            f"{report_name}.html"
        )

        for day in [
            today,
            yesterday,
        ]
    ]

    if include_generic:

        generic = (
            "https://www.ercot.com/"
            "content/cdr/html/"
            f"{report_name}.html"
        )

        return [
            generic,
            *dated_urls,
        ]

    return dated_urls


def _parse_ercot_numeric_value(
    value,
):

    cleaned = (
        clean_text(
            value
        )
        .replace(
            ",",
            "",
        )
        .replace(
            "$",
            "",
        )
        .strip()
    )

    if cleaned == "":

        return np.nan

    return pd.to_numeric(
        cleaned,
        errors="coerce",
    )


def parse_ercot_latest_lmp_table(
    html_text,
):

    parser = ERCOTHTMLTableParser()

    parser.feed(
        html_text
    )

    rows = []

    for table_rows in parser.tables:

        for raw_row in table_rows:

            values = [
                re.sub(
                    "\\s+",
                    " ",
                    clean_text(
                        value
                    ),
                ).strip()

                for value
                in raw_row
            ]

            if not values:

                continue

            settlement_point = (
                values[0]
                .upper()
            )

            if not re.fullmatch(
                "(?:HB|LZ)_[A-Z0-9_]+",
                settlement_point,
            ):

                continue

            numeric_values = [
                _parse_ercot_numeric_value(
                    value
                )

                for value
                in values[1:]
            ]

            numeric_values = [
                value
                for value
                in numeric_values
                if pd.notna(
                    value
                )
            ]

            if not numeric_values:

                continue

            rows.append(
                {
                    "Settlement Point":
                        settlement_point,

                    "LMP":
                        numeric_values[0],

                    "5 Min Change to LMP":
                        (
                            numeric_values[1]
                            if len(
                                numeric_values
                            ) > 1
                            else np.nan
                        ),

                    "RTRDPA + LMP":
                        (
                            numeric_values[2]
                            if len(
                                numeric_values
                            ) > 2
                            else np.nan
                        ),

                    "5 Min Change to RTRDPA + LMP":
                        (
                            numeric_values[3]
                            if len(
                                numeric_values
                            ) > 3
                            else np.nan
                        ),
                }
            )

    if not rows:

        visible_text = (
            html_lib.unescape(
                re.sub(
                    "<[^>]+>",
                    " | ",
                    html_text,
                )
            )
        )

        visible_text = re.sub(
            "\\s+",
            " ",
            visible_text,
        )

        point_matches = list(
            re.finditer(
                "\\b(?:HB|LZ)_[A-Z0-9_]+\\b",
                visible_text,
                flags=re.IGNORECASE,
            )
        )

        for index, match in enumerate(
            point_matches
        ):

            settlement_point = (
                match.group(
                    0
                )
                .upper()
            )

            segment_end = (
                point_matches[
                    index + 1
                ].start()

                if (
                    index + 1
                    < len(
                        point_matches
                    )
                )

                else min(
                    len(
                        visible_text
                    ),
                    match.end()
                    + 500,
                )
            )

            segment = visible_text[
                match.end():
                segment_end
            ]

            number_matches = (
                re.findall(
                    "(?<![A-Za-z0-9_])"
                    "[-+]?\\$?"
                    "\\d{1,6}"
                    "(?:,\\d{3})*"
                    "(?:\\.\\d+)?",
                    segment,
                )
            )

            numeric_values = [
                _parse_ercot_numeric_value(
                    value
                )

                for value
                in number_matches[
                    :4
                ]
            ]

            numeric_values = [
                value
                for value
                in numeric_values
                if pd.notna(
                    value
                )
            ]

            if not numeric_values:

                continue

            rows.append(
                {
                    "Settlement Point":
                        settlement_point,

                    "LMP":
                        numeric_values[0],

                    "5 Min Change to LMP":
                        (
                            numeric_values[1]
                            if len(
                                numeric_values
                            ) > 1
                            else np.nan
                        ),

                    "RTRDPA + LMP":
                        (
                            numeric_values[2]
                            if len(
                                numeric_values
                            ) > 2
                            else np.nan
                        ),

                    "5 Min Change to RTRDPA + LMP":
                        (
                            numeric_values[3]
                            if len(
                                numeric_values
                            ) > 3
                            else np.nan
                        ),
                }
            )

    if not rows:

        raise ValueError(
            "ERCOT SCED LMP rows were "
            "not found in the returned HTML."
        )

    table = pd.DataFrame(
        rows
    )

    table = (
        table
        .drop_duplicates(
            subset=[
                "Settlement Point",
            ],
            keep="first",
        )
        .sort_values(
            "Settlement Point"
        )
        .reset_index(
            drop=True
        )
    )

    return table


def extract_ercot_lmp_last_updated(
    html_text,
):

    visible_text = strip_html(
        html_text
    )

    match = re.search(
        (
            "Last Updated:\\s*"
            "([A-Za-z]{3}\\s+"
            "\\d{1,2},\\s+"
            "\\d{4}\\s+"
            "\\d{1,2}:\\d{2}:\\d{2})"
        ),
        visible_text,
        flags=re.IGNORECASE,
    )

    if match is None:

        return pd.NaT

    return pd.to_datetime(
        match.group(
            1
        ),
        errors="coerce",
    )


@st.cache_data(
    ttl=300,
    show_spinner=False,
)
def fetch_ercot_latest_lmp():

    html_text = (
        _download_ercot_html(
            ERCOT_LATEST_LMP_URL
        )
    )

    table = (
        parse_ercot_latest_lmp_table(
            html_text
        )
    )

    table[
        "ERCOT Last Updated"
    ] = (
        extract_ercot_lmp_last_updated(
            html_text
        )
    )

    return (
        table,
        ERCOT_LATEST_LMP_URL,
    )


@st.cache_data(
    ttl=300,
    show_spinner=False,
)
def fetch_ercot_rt_spp():

    urls = (
        _ercot_operating_day_urls(
            "real_time_spp",
            include_generic=True,
        )
    )

    return _fetch_first_ercot_table(
        candidate_urls=urls,
        time_column="Interval Ending",
        required_columns=[
            "Oper Day",
            "Interval Ending",
            "HB_NORTH",
        ],
    )


@st.cache_data(
    ttl=3600,
    show_spinner=False,
)
def fetch_ercot_dam_spp():

    urls = (
        _ercot_operating_day_urls(
            "dam_spp",
            include_generic=True,
        )
    )

    return _fetch_first_ercot_table(
        candidate_urls=urls,
        time_column="Hour Ending",
        required_columns=[
            "Oper Day",
            "Hour Ending",
            "HB_NORTH",
        ],
    )


@st.cache_data(
    ttl=3600,
    show_spinner=False,
)
def fetch_ercot_dam_mcpc():

    dated_urls = (
        _ercot_operating_day_urls(
            "dam_mcpc",
            include_generic=False,
        )
    )

    urls = [
        *dated_urls,
        ERCOT_DAM_MCPC_URL,
    ]

    return _fetch_first_ercot_table(
        candidate_urls=urls,
        time_column="Hour Ending",
        required_columns=[
            "Oper Day",
            "Hour Ending",
            "NON-SPIN",
            "ECRS",
        ],
    )


def ercot_interval_timestamp(
    operating_day,
    interval_ending,
):

    day = pd.to_datetime(
        operating_day,
        errors="coerce",
    )

    if pd.isna(
        day
    ):

        return pd.NaT

    digits = re.sub(
        "\\D",
        "",
        clean_text(
            interval_ending
        ),
    )

    if not digits:

        return pd.NaT

    digits = (
        digits
        .zfill(
            4
        )[-4:]
    )

    try:

        hour = int(
            digits[:2]
        )

        minute = int(
            digits[2:]
        )

    except Exception:

        return pd.NaT

    if hour == 24:

        return (
            day
            + pd.Timedelta(
                days=1
            )
            + pd.Timedelta(
                minutes=minute
            )
        )

    return (
        day
        + pd.Timedelta(
            hours=hour
        )
        + pd.Timedelta(
            minutes=minute
        )
    )


def ercot_hour_timestamp(
    operating_day,
    hour_ending,
):

    day = pd.to_datetime(
        operating_day,
        errors="coerce",
    )

    if pd.isna(
        day
    ):

        return pd.NaT

    try:

        hour = int(
            float(
                clean_text(
                    hour_ending
                )
            )
        )

    except Exception:

        return pd.NaT

    if hour == 24:

        return (
            day
            + pd.Timedelta(
                days=1
            )
        )

    return (
        day
        + pd.Timedelta(
            hours=hour
        )
    )


def rt_interval_to_hour_ending(
    interval_ending,
):

    digits = re.sub(
        "\\D",
        "",
        clean_text(
            interval_ending
        ),
    )

    if not digits:

        return np.nan

    digits = (
        digits
        .zfill(
            4
        )[-4:]
    )

    try:

        hour = int(
            digits[:2]
        )

        minute = int(
            digits[2:]
        )

    except Exception:

        return np.nan

    if hour == 24:

        return 24

    if minute > 0:

        return hour + 1

    return max(
        hour,
        1,
    )


def market_price_signal(
    latest_price,
    daily_average,
):

    if pd.isna(
        latest_price
    ):

        return "N/A"

    if latest_price < 0:

        return "Negative"

    if pd.isna(
        daily_average
    ):

        return "Current"

    difference = (
        latest_price
        - daily_average
    )

    if difference >= 30:

        return "Elevated"

    if difference <= -20:

        return "Soft"

    return "Normal"


def price_metric_value(
    value,
):

    if pd.isna(
        value
    ):

        return "N/A"

    return (
        f"${value:,.2f}/MWh"
    )


# ============================================================
# ERCOT NODAL API
# ============================================================

ERCOT_PUBLIC_API_BASE = (
    "https://api.ercot.com/api/public-reports"
)

ERCOT_PUBLIC_API_AUTH_URL = (
    "https://ercotb2c.b2clogin.com/"
    "ercotb2c.onmicrosoft.com/"
    "B2C_1_PUBAPI-ROPC-FLOW/"
    "oauth2/v2.0/token"
)

ERCOT_PUBLIC_API_CLIENT_ID = (
    "fec253ea-0d06-4272-a5e6-b478baeecd70"
)

ERCOT_PUBLIC_API_SCOPE = (
    "openid "
    + ERCOT_PUBLIC_API_CLIENT_ID
    + " offline_access"
)

ERCOT_RT_NODAL_ENDPOINT = (
    "/np6-788-cd/lmp_node_zone_hub"
)

ERCOT_RTD_NODAL_ENDPOINT = (
    "/np6-970-cd/rtd_lmp_node_zone_hub"
)

ERCOT_DAM_NODAL_ENDPOINT = (
    "/np4-190-cd/dam_stlmnt_pnt_prices"
)


def _get_ercot_api_config():

    username = clean_text(
        os.getenv(
            "ERCOT_API_USERNAME",
            "",
        )
    )

    password = clean_text(
        os.getenv(
            "ERCOT_API_PASSWORD",
            "",
        )
    )

    subscription_key = clean_text(
        os.getenv(
            "ERCOT_API_SUBSCRIPTION_KEY",
            "",
        )
    )

    try:

        secret_block = st.secrets.get(
            "ercot_api",
            {},
        )

        username = clean_text(
            secret_block.get(
                "username",
                username,
            )
        )

        password = clean_text(
            secret_block.get(
                "password",
                password,
            )
        )

        subscription_key = clean_text(
            secret_block.get(
                "subscription_key",
                subscription_key,
            )
        )

    except Exception:

        pass

    return {
        "username":
            username,

        "password":
            password,

        "subscription_key":
            subscription_key,

        "configured":
            bool(
                username
                and
                password
                and
                subscription_key
            ),
    }


def _ercot_api_authenticate(
    username,
    password,
):

    form_data = urllib.parse.urlencode(
        {
            "username":
                username,

            "password":
                password,

            "grant_type":
                "password",

            "scope":
                ERCOT_PUBLIC_API_SCOPE,

            "client_id":
                ERCOT_PUBLIC_API_CLIENT_ID,

            "response_type":
                "id_token",
        }
    ).encode(
        "utf-8"
    )

    request = urllib.request.Request(
        ERCOT_PUBLIC_API_AUTH_URL,
        data=form_data,
        headers={
            "Content-Type":
                "application/x-www-form-urlencoded",

            "Accept":
                "application/json",

            "User-Agent":
                "Mozilla/5.0 "
                "ERCOT-Acquisition-Dashboard/1.0",
        },
        method="POST",
    )

    with urllib.request.urlopen(
        request,
        timeout=25,
    ) as response:

        payload = json.loads(
            response.read().decode(
                "utf-8",
                errors="replace",
            )
        )

    token = (
        payload.get(
            "id_token"
        )
        or
        payload.get(
            "access_token"
        )
    )

    if not token:

        raise ValueError(
            "ERCOT authentication succeeded "
            "but no usable token was returned."
        )

    return token


def _ercot_api_get(
    endpoint,
    params,
    token,
    subscription_key,
):

    cleaned_params = {
        key:
            value

        for key, value
        in params.items()

        if value not in [
            None,
            "",
        ]
    }

    url = (
        ERCOT_PUBLIC_API_BASE
        + endpoint
    )

    if cleaned_params:

        url += (
            "?"
            + urllib.parse.urlencode(
                cleaned_params
            )
        )

    request = urllib.request.Request(
        url,
        headers={
            "Authorization":
                "Bearer "
                + token,

            "Ocp-Apim-Subscription-Key":
                subscription_key,

            "Accept":
                "application/json",

            "User-Agent":
                "Mozilla/5.0 "
                "ERCOT-Acquisition-Dashboard/1.0",
        },
    )

    with urllib.request.urlopen(
        request,
        timeout=35,
    ) as response:

        return json.loads(
            response.read().decode(
                "utf-8",
                errors="replace",
            )
        )


def _ercot_report_to_dataframe(
    payload,
):

    if not isinstance(
        payload,
        dict,
    ):

        return pd.DataFrame()

    data = payload.get(
        "data",
        [],
    )

    fields = payload.get(
        "fields",
        [],
    )

    field_names = [
        clean_text(
            field.get(
                "name"
            )
        )

        for field
        in fields

        if (
            isinstance(
                field,
                dict,
            )
            and
            clean_text(
                field.get(
                    "name"
                )
            )
        )
    ]

    if isinstance(
        data,
        list,
    ):

        if not data:

            return pd.DataFrame(
                columns=field_names
            )

        if isinstance(
            data[0],
            dict,
        ):

            return pd.DataFrame(
                data
            )

        if field_names:

            width = min(
                len(
                    field_names
                ),
                max(
                    (
                        len(
                            row
                        )
                        if isinstance(
                            row,
                            (
                                list,
                                tuple,
                            ),
                        )
                        else 1

                        for row
                        in data
                    )
                ),
            )

            rows = []

            for row in data:

                if isinstance(
                    row,
                    (
                        list,
                        tuple,
                    ),
                ):

                    values = list(
                        row
                    )[:width]

                else:

                    values = [
                        row
                    ]

                if len(
                    values
                ) < width:

                    values += [
                        None
                    ] * (
                        width
                        - len(
                            values
                        )
                    )

                rows.append(
                    values
                )

            return pd.DataFrame(
                rows,
                columns=
                    field_names[
                        :width
                    ],
            )

        return pd.DataFrame(
            data
        )

    if isinstance(
        data,
        dict,
    ):

        try:

            return pd.DataFrame(
                data
            )

        except Exception:

            return pd.DataFrame(
                [
                    data
                ]
            )

    return pd.DataFrame()


def _canonical_column_name(
    value,
):

    return re.sub(
        "[^a-z0-9]",
        "",
        clean_text(
            value
        ).lower(),
    )


def _find_dataframe_column(
    frame,
    candidates,
):

    if frame is None:

        return None

    lookup = {
        _canonical_column_name(
            column
        ):
            column

        for column
        in frame.columns
    }

    for candidate in candidates:

        key = (
            _canonical_column_name(
                candidate
            )
        )

        if key in lookup:

            return lookup[
                key
            ]

    return None


def _ercot_timestamp_string(
    timestamp,
):

    value = pd.Timestamp(
        timestamp
    )

    if value.tzinfo is not None:

        value = (
            value
            .tz_convert(
                "America/Chicago"
            )
            .tz_localize(
                None
            )
        )

    return value.strftime(
        "%Y-%m-%dT%H:%M:%S"
    )


def _fetch_ercot_nodal_actual(
    settlement_point,
    token,
    subscription_key,
    lookback_hours=3,
):

    now_central = (
        pd.Timestamp.now(
            tz="America/Chicago"
        )
    )

    payload = _ercot_api_get(
        ERCOT_RT_NODAL_ENDPOINT,
        {
            "SCEDTimestampFrom":
                _ercot_timestamp_string(
                    now_central
                    - pd.Timedelta(
                        hours=
                            lookback_hours
                    )
                ),

            "SCEDTimestampTo":
                _ercot_timestamp_string(
                    now_central
                    + pd.Timedelta(
                        minutes=10
                    )
                ),

            "settlementPoint":
                settlement_point,

            "size":
                1000,
        },
        token,
        subscription_key,
    )

    frame = (
        _ercot_report_to_dataframe(
            payload
        )
    )

    timestamp_col = (
        _find_dataframe_column(
            frame,
            [
                "SCEDTimestamp",
                "SCED Timestamp",
            ],
        )
    )

    lmp_col = (
        _find_dataframe_column(
            frame,
            [
                "LMP",
            ],
        )
    )

    point_col = (
        _find_dataframe_column(
            frame,
            [
                "settlementPoint",
                "Settlement Point",
            ],
        )
    )

    if timestamp_col:

        frame[
            "Nodal Timestamp"
        ] = pd.to_datetime(
            frame[
                timestamp_col
            ],
            errors="coerce",
        )

    if lmp_col:

        frame[
            "Nodal LMP"
        ] = pd.to_numeric(
            frame[
                lmp_col
            ],
            errors="coerce",
        )

    if point_col:

        frame[
            "Settlement Point"
        ] = (
            frame[
                point_col
            ]
            .astype(
                str
            )
        )

    if (
        "Nodal Timestamp"
        in frame.columns
    ):

        frame = (
            frame
            .sort_values(
                "Nodal Timestamp"
            )
            .reset_index(
                drop=True
            )
        )

    return frame


def _fetch_ercot_rtd_nodal_forecast(
    settlement_point,
    token,
    subscription_key,
    lookback_minutes=30,
):

    now_central = (
        pd.Timestamp.now(
            tz="America/Chicago"
        )
    )

    payload = _ercot_api_get(
        ERCOT_RTD_NODAL_ENDPOINT,
        {
            "RTDTimestampFrom":
                _ercot_timestamp_string(
                    now_central
                    - pd.Timedelta(
                        minutes=
                            lookback_minutes
                    )
                ),

            "RTDTimestampTo":
                _ercot_timestamp_string(
                    now_central
                    + pd.Timedelta(
                        minutes=5
                    )
                ),

            "settlementPoint":
                settlement_point,

            "size":
                2000,
        },
        token,
        subscription_key,
    )

    frame = (
        _ercot_report_to_dataframe(
            payload
        )
    )

    rtd_col = (
        _find_dataframe_column(
            frame,
            [
                "RTDTimestamp",
                "RTD Timestamp",
            ],
        )
    )

    interval_col = (
        _find_dataframe_column(
            frame,
            [
                "intervalEnding",
                "Interval Ending",
            ],
        )
    )

    interval_id_col = (
        _find_dataframe_column(
            frame,
            [
                "intervalId",
                "Interval ID",
            ],
        )
    )

    lmp_col = (
        _find_dataframe_column(
            frame,
            [
                "LMP",
            ],
        )
    )

    point_col = (
        _find_dataframe_column(
            frame,
            [
                "settlementPoint",
                "Settlement Point",
            ],
        )
    )

    if rtd_col:

        frame[
            "RTD Timestamp"
        ] = pd.to_datetime(
            frame[
                rtd_col
            ],
            errors="coerce",
        )

    if interval_col:

        frame[
            "Forecast Interval"
        ] = pd.to_datetime(
            frame[
                interval_col
            ],
            errors="coerce",
        )

    if interval_id_col:

        frame[
            "Forecast Interval ID"
        ] = pd.to_numeric(
            frame[
                interval_id_col
            ],
            errors="coerce",
        )

    if lmp_col:

        frame[
            "Forecast LMP"
        ] = pd.to_numeric(
            frame[
                lmp_col
            ],
            errors="coerce",
        )

    if point_col:

        frame[
            "Settlement Point"
        ] = (
            frame[
                point_col
            ]
            .astype(
                str
            )
        )

    if (
        "RTD Timestamp"
        in frame.columns
        and
        frame[
            "RTD Timestamp"
        ].notna().any()
    ):

        latest_rtd = (
            frame[
                "RTD Timestamp"
            ].max()
        )

        frame = (
            frame[
                frame[
                    "RTD Timestamp"
                ]
                == latest_rtd
            ]
            .copy()
        )

    sort_columns = [
        column

        for column
        in [
            "Forecast Interval",
            "Forecast Interval ID",
        ]

        if column
        in frame.columns
    ]

    if sort_columns:

        frame = (
            frame
            .sort_values(
                sort_columns
            )
            .reset_index(
                drop=True
            )
        )

    return frame


def _fetch_ercot_dam_nodal(
    settlement_point,
    token,
    subscription_key,
):

    today_central = (
        pd.Timestamp.now(
            tz="America/Chicago"
        ).date()
    )

    end_date = (
        pd.Timestamp(
            today_central
        )
        + pd.Timedelta(
            days=2
        )
    ).date()

    payload = _ercot_api_get(
        ERCOT_DAM_NODAL_ENDPOINT,
        {
            "deliveryDateFrom":
                today_central.isoformat(),

            "deliveryDateTo":
                end_date.isoformat(),

            "settlementPoint":
                settlement_point,

            "size":
                500,
        },
        token,
        subscription_key,
    )

    frame = (
        _ercot_report_to_dataframe(
            payload
        )
    )

    date_col = (
        _find_dataframe_column(
            frame,
            [
                "deliveryDate",
                "Delivery Date",
            ],
        )
    )

    he_col = (
        _find_dataframe_column(
            frame,
            [
                "hourEnding",
                "Hour Ending",
            ],
        )
    )

    price_col = (
        _find_dataframe_column(
            frame,
            [
                "settlementPointPrice",
                "Settlement Point Price",
            ],
        )
    )

    point_col = (
        _find_dataframe_column(
            frame,
            [
                "settlementPoint",
                "Settlement Point",
            ],
        )
    )

    if date_col:

        frame[
            "Delivery Date"
        ] = pd.to_datetime(
            frame[
                date_col
            ],
            errors="coerce",
        )

    if he_col:

        frame[
            "Hour Ending"
        ] = (
            frame[
                he_col
            ]
            .astype(
                str
            )
        )

        frame[
            "Hour Ending Sort"
        ] = pd.to_numeric(
            frame[
                "Hour Ending"
            ]
            .str.extract(
                "(\\d+)"
            )[0],
            errors="coerce",
        )

    if price_col:

        frame[
            "DAM SPP"
        ] = pd.to_numeric(
            frame[
                price_col
            ],
            errors="coerce",
        )

    if point_col:

        frame[
            "Settlement Point"
        ] = (
            frame[
                point_col
            ]
            .astype(
                str
            )
        )

    if (
        "Delivery Date"
        in frame.columns
        and
        frame[
            "Delivery Date"
        ].notna().any()
    ):

        latest_delivery = (
            frame[
                "Delivery Date"
            ].max()
        )

        frame = (
            frame[
                frame[
                    "Delivery Date"
                ]
                == latest_delivery
            ]
            .copy()
        )

    sort_columns = [
        column

        for column
        in [
            "Delivery Date",
            "Hour Ending Sort",
        ]

        if column
        in frame.columns
    ]

    if sort_columns:

        frame = (
            frame
            .sort_values(
                sort_columns
            )
            .reset_index(
                drop=True
            )
        )

    return frame


def _detect_project_node_column(
    frame,
):

    candidates = [
        "ERCOT Resource Node",
        "Resource Node",
        "ERCOT Settlement Point",
        "Settlement Point",
        "Settlement Point Name",
        "Pricing Node",
    ]

    return _find_dataframe_column(
        frame,
        candidates,
    )


def _parse_forward_curve_upload(
    uploaded_file,
):

    if uploaded_file is None:

        return (
            pd.DataFrame(),
            {},
        )

    frame = pd.read_csv(
        uploaded_file
    )

    node_col = (
        _find_dataframe_column(
            frame,
            [
                "Settlement Point",
                "Resource Node",
                "Node",
                "ERCOT Resource Node",
                "ERCOT Settlement Point",
            ],
        )
    )

    date_col = (
        _find_dataframe_column(
            frame,
            [
                "Date",
                "Datetime",
                "Timestamp",
                "Month",
                "Period",
            ],
        )
    )

    year_col = (
        _find_dataframe_column(
            frame,
            [
                "Year",
            ],
        )
    )

    price_col = (
        _find_dataframe_column(
            frame,
            [
                "Price ($/MWh)",
                "Forecast Price ($/MWh)",
                "Forecast Price",
                "Nodal Price",
                "Price",
                "LMP",
            ],
        )
    )

    scenario_col = (
        _find_dataframe_column(
            frame,
            [
                "Scenario",
                "Case",
            ],
        )
    )

    return (
        frame,
        {
            "node":
                node_col,

            "date":
                date_col,

            "year":
                year_col,

            "price":
                price_col,

            "scenario":
                scenario_col,
        },
    )


# ============================================================
# IX COST HELPERS
# ============================================================

def _numeric_money_value(
    value,
):

    if pd.isna(
        value
    ):

        return np.nan

    text = clean_text(
        value
    )

    if not text:

        return np.nan

    negative = (
        text.startswith(
            "("
        )
        and
        text.endswith(
            ")"
        )
    )

    text = (
        text
        .replace(
            "$",
            "",
        )
        .replace(
            ",",
            "",
        )
        .replace(
            "(",
            "",
        )
        .replace(
            ")",
            "",
        )
        .strip()
    )

    result = pd.to_numeric(
        text,
        errors="coerce",
    )

    if (
        negative
        and
        pd.notna(
            result
        )
    ):

        result = (
            -result
        )

    return result


def _ix_cost_per_kw(
    total_cost,
    capacity_mw,
):

    if (
        pd.isna(
            total_cost
        )
        or
        pd.isna(
            capacity_mw
        )
        or
        capacity_mw <= 0
    ):

        return np.nan

    return (
        float(
            total_cost
        )
        /
        (
            float(
                capacity_mw
            )
            * 1000.0
        )
    )


# ============================================================
# ERCOT MARKET PRICE TAB
# ============================================================

market_lmp_df = pd.DataFrame()
market_rt_df = pd.DataFrame()
market_dam_df = pd.DataFrame()
market_mcpc_df = pd.DataFrame()

market_lmp_source = ""
market_rt_source = ""
market_dam_source = ""
market_mcpc_source = ""


with price_tab:

    st.markdown(
        "## 📈 ERCOT Market Prices"
    )

    st.caption(
        "Live market screen sourced directly "
        "from ERCOT public Current Day Reports. "
        "Real-Time SPP refreshes on a five-minute "
        "cache; Day-Ahead energy and ancillary-"
        "service prices refresh hourly. Market "
        "data is informational and does not "
        "change the acquisition Opportunity Score."
    )

    refresh_col, source_col = st.columns(
        [
            1,
            4,
        ]
    )

    with refresh_col:

        refresh_market_prices = (
            st.button(
                "🔄 Refresh ERCOT Prices",
                key=
                    "refresh_ercot_market_prices",
            )
        )

    if refresh_market_prices:

        fetch_ercot_latest_lmp.clear()
        fetch_ercot_rt_spp.clear()
        fetch_ercot_dam_spp.clear()
        fetch_ercot_dam_mcpc.clear()

        st.rerun()

    with source_col:

        st.caption(
            "Latest SCED LMP excludes Real-Time "
            "price adders; RT SPP includes ERCOT "
            "Real-Time Reliability Deployment "
            "Price Adders. Project-area comparisons "
            "use broad hub benchmarks and are not "
            "node-level project prices."
        )

    lmp_error = ""
    rt_error = ""
    dam_error = ""
    mcpc_error = ""

    try:

        (
            market_lmp_df,
            market_lmp_source,
        ) = fetch_ercot_latest_lmp()

    except Exception as exc:

        lmp_error = clean_text(
            exc
        )

    try:

        (
            market_rt_df,
            market_rt_source,
        ) = fetch_ercot_rt_spp()

        market_rt_df[
            "Timestamp"
        ] = market_rt_df.apply(
            lambda row:
                ercot_interval_timestamp(
                    row[
                        "Oper Day"
                    ],
                    row[
                        "Interval Ending"
                    ],
                ),
            axis=1,
        )

        market_rt_df = (
            market_rt_df[
                market_rt_df[
                    "Timestamp"
                ].notna()
            ]
            .sort_values(
                "Timestamp"
            )
            .reset_index(
                drop=True
            )
        )

    except Exception as exc:

        rt_error = clean_text(
            exc
        )

    try:

        (
            market_dam_df,
            market_dam_source,
        ) = fetch_ercot_dam_spp()

        market_dam_df[
            "Timestamp"
        ] = market_dam_df.apply(
            lambda row:
                ercot_hour_timestamp(
                    row[
                        "Oper Day"
                    ],
                    row[
                        "Hour Ending"
                    ],
                ),
            axis=1,
        )

        market_dam_df[
            "Hour Ending Numeric"
        ] = pd.to_numeric(
            market_dam_df[
                "Hour Ending"
            ],
            errors="coerce",
        )

        market_dam_df = (
            market_dam_df[
                market_dam_df[
                    "Timestamp"
                ].notna()
            ]
            .sort_values(
                "Timestamp"
            )
            .reset_index(
                drop=True
            )
        )

    except Exception as exc:

        dam_error = clean_text(
            exc
        )

    try:

        (
            market_mcpc_df,
            market_mcpc_source,
        ) = fetch_ercot_dam_mcpc()

        market_mcpc_df[
            "Timestamp"
        ] = market_mcpc_df.apply(
            lambda row:
                ercot_hour_timestamp(
                    row[
                        "Oper Day"
                    ],
                    row[
                        "Hour Ending"
                    ],
                ),
            axis=1,
        )

        market_mcpc_df = (
            market_mcpc_df[
                market_mcpc_df[
                    "Timestamp"
                ].notna()
            ]
            .sort_values(
                "Timestamp"
            )
            .reset_index(
                drop=True
            )
        )

    except Exception as exc:

        mcpc_error = clean_text(
            exc
        )

    if market_rt_df.empty:

        st.error(
            "ERCOT Real-Time SPP could "
            "not be loaded. "
            + (
                rt_error
                or
                "The public report returned "
                "no usable rows."
            )
        )

    else:

        latest_rt_row = (
            market_rt_df
            .iloc[-1]
        )

        latest_rt_timestamp = (
            latest_rt_row[
                "Timestamp"
            ]
        )

        current_operating_day = (
            latest_rt_row[
                "Oper Day"
            ]
        )

        st.success(
            "ERCOT Real-Time SPP feed connected. "
            "Latest settlement interval: "
            f"{latest_rt_timestamp.strftime('%m/%d/%Y %H:%M')} "
            "CT."
        )

        major_hubs = [
            "HB_NORTH",
            "HB_HOUSTON",
            "HB_SOUTH",
            "HB_WEST",
            "HB_PAN",
        ]

        major_hubs = [
            hub
            for hub
            in major_hubs
            if hub
            in market_rt_df.columns
        ]

        market_points = [
            column
            for column
            in market_rt_df.columns
            if (
                column.startswith(
                    "HB_"
                )
                or
                column.startswith(
                    "LZ_"
                )
            )
        ]

        if not market_dam_df.empty:

            market_points = [
                point
                for point
                in market_points
                if point
                in market_dam_df.columns
            ]

        point_col, view_col = st.columns(
            [
                1.5,
                1,
            ]
        )

        with point_col:

            default_point_index = (
                market_points.index(
                    "HB_NORTH"
                )
                if "HB_NORTH"
                in market_points
                else 0
            )

            selected_market_point = (
                st.selectbox(
                    "Hub / Load Zone",
                    options=
                        market_points,
                    index=
                        default_point_index,
                    key=
                        "ercot_market_point",
                )
            )

        with view_col:

            chart_window = (
                st.selectbox(
                    "Chart View",
                    options=[
                        "Today",
                        "Last 24 Hours Available",
                    ],
                    index=0,
                    key=
                        "ercot_market_chart_window",
                )
            )

        selected_rt = (
            market_rt_df[
                [
                    "Timestamp",
                    "Oper Day",
                    "Interval Ending",
                    selected_market_point,
                ]
            ]
            .copy()
        )

        selected_rt = (
            selected_rt[
                selected_rt[
                    selected_market_point
                ].notna()
            ]
        )

        if chart_window == "Today":

            selected_rt = (
                selected_rt[
                    selected_rt[
                        "Oper Day"
                    ]
                    == current_operating_day
                ]
                .copy()
            )

        latest_point_price = (
            selected_rt[
                selected_market_point
            ].iloc[-1]
            if not selected_rt.empty
            else np.nan
        )

        rt_day_average = (
            selected_rt[
                selected_market_point
            ].mean()
            if not selected_rt.empty
            else np.nan
        )

        rt_day_high = (
            selected_rt[
                selected_market_point
            ].max()
            if not selected_rt.empty
            else np.nan
        )

        rt_day_low = (
            selected_rt[
                selected_market_point
            ].min()
            if not selected_rt.empty
            else np.nan
        )

        negative_intervals = (
            int(
                (
                    selected_rt[
                        selected_market_point
                    ]
                    < 0
                ).sum()
            )
            if not selected_rt.empty
            else 0
        )

        latest_interval = (
            latest_rt_row[
                "Interval Ending"
            ]
        )

        latest_hour_ending = (
            rt_interval_to_hour_ending(
                latest_interval
            )
        )

        dam_hour_price = np.nan
        dam_day_average = np.nan

        if (
            not market_dam_df.empty
            and selected_market_point
            in market_dam_df.columns
        ):

            dam_operating_day = (
                market_dam_df[
                    "Oper Day"
                ].max()
            )

            selected_dam = (
                market_dam_df[
                    market_dam_df[
                        "Oper Day"
                    ]
                    == dam_operating_day
                ]
                .copy()
            )

            dam_day_average = (
                selected_dam[
                    selected_market_point
                ].mean()
            )

            matching_dam = (
                selected_dam[
                    selected_dam[
                        "Hour Ending Numeric"
                    ]
                    == latest_hour_ending
                ]
            )

            if not matching_dam.empty:

                dam_hour_price = (
                    matching_dam[
                        selected_market_point
                    ]
                    .iloc[-1]
                )

        rt_minus_dam = (
            latest_point_price
            - dam_hour_price
            if (
                pd.notna(
                    latest_point_price
                )
                and
                pd.notna(
                    dam_hour_price
                )
            )
            else np.nan
        )

        latest_sced_lmp = np.nan

        if not market_lmp_df.empty:

            lmp_match = (
                market_lmp_df[
                    market_lmp_df[
                        "Settlement Point"
                    ]
                    == selected_market_point
                ]
            )

            if not lmp_match.empty:

                latest_sced_lmp = (
                    lmp_match[
                        "LMP"
                    ]
                    .iloc[-1]
                )

        p1, p2, p3, p4, p5, p6 = st.columns(
            6
        )

        p1.metric(
            "Latest SCED LMP",
            price_metric_value(
                latest_sced_lmp
            ),
        )

        p2.metric(
            "Latest RT SPP",
            price_metric_value(
                latest_point_price
            ),
        )

        p3.metric(
            "RT Day Avg",
            price_metric_value(
                rt_day_average
            ),
        )

        p4.metric(
            (
                "DAM HE "
                + (
                    str(
                        int(
                            latest_hour_ending
                        )
                    )
                    if pd.notna(
                        latest_hour_ending
                    )
                    else "N/A"
                )
            ),
            price_metric_value(
                dam_hour_price
            ),
        )

        p5.metric(
            "RT - DAM",
            (
                f"${rt_minus_dam:+,.2f}/MWh"
                if pd.notna(
                    rt_minus_dam
                )
                else "N/A"
            ),
        )

        p6.metric(
            "RT Day Range",
            (
                f"${rt_day_low:,.2f} – "
                f"${rt_day_high:,.2f}"
                if (
                    pd.notna(
                        rt_day_low
                    )
                    and
                    pd.notna(
                        rt_day_high
                    )
                )
                else "N/A"
            ),
        )

        signal = market_price_signal(
            latest_point_price,
            rt_day_average,
        )

        st.caption(
            f"Market signal for "
            f"{selected_market_point}: "
            f"**{signal}** | "
            "Negative 15-minute intervals "
            "in selected view: "
            f"**{negative_intervals}** | "
            "DAM daily average: "
            f"**{price_metric_value(dam_day_average)}**"
        )

        st.markdown(
            "### Current Hub Snapshot"
        )

        hub_rows = []

        latest_rt_oper_day = (
            latest_rt_row[
                "Oper Day"
            ]
        )

        rt_today = (
            market_rt_df[
                market_rt_df[
                    "Oper Day"
                ]
                == latest_rt_oper_day
            ]
            .copy()
        )

        latest_dam_day = (
            market_dam_df[
                "Oper Day"
            ].max()
            if not market_dam_df.empty
            else pd.NaT
        )

        dam_today = (
            market_dam_df[
                market_dam_df[
                    "Oper Day"
                ]
                == latest_dam_day
            ]
            .copy()
            if not market_dam_df.empty
            else pd.DataFrame()
        )

        for hub in major_hubs:

            latest_value = (
                latest_rt_row.get(
                    hub,
                    np.nan,
                )
            )

            average_value = (
                rt_today[
                    hub
                ].mean()
            )

            high_value = (
                rt_today[
                    hub
                ].max()
            )

            low_value = (
                rt_today[
                    hub
                ].min()
            )

            hub_dam_avg = (
                dam_today[
                    hub
                ].mean()
                if (
                    not dam_today.empty
                    and hub
                    in dam_today.columns
                )
                else np.nan
            )

            hub_lmp = np.nan

            if not market_lmp_df.empty:

                hub_lmp_match = (
                    market_lmp_df[
                        market_lmp_df[
                            "Settlement Point"
                        ]
                        == hub
                    ]
                )

                if not hub_lmp_match.empty:

                    hub_lmp = (
                        hub_lmp_match[
                            "LMP"
                        ]
                        .iloc[-1]
                    )

            hub_rows.append(
                {
                    "Hub":
                        hub,

                    "Latest SCED LMP":
                        hub_lmp,

                    "Latest RT SPP":
                        latest_value,

                    "RT Day Avg":
                        average_value,

                    "RT Day High":
                        high_value,

                    "RT Day Low":
                        low_value,

                    "DAM Day Avg":
                        hub_dam_avg,

                    "Signal":
                        market_price_signal(
                            latest_value,
                            average_value,
                        ),
                }
            )

        hub_snapshot = pd.DataFrame(
            hub_rows
        )

        st.dataframe(
            hub_snapshot,
            use_container_width=True,
            hide_index=True,
        )

        chart_left, chart_right = st.columns(
            2
        )

        with chart_left:

            st.markdown(
                f"### Real-Time SPP — "
                f"{selected_market_point}"
            )

            rt_chart = (
                selected_rt[
                    [
                        "Timestamp",
                        selected_market_point,
                    ]
                ]
                .rename(
                    columns={
                        selected_market_point:
                            "RT SPP ($/MWh)",
                    }
                )
            )

            if rt_chart.empty:

                st.info(
                    "No Real-Time rows are "
                    "available for this selection."
                )

            else:

                st.line_chart(
                    rt_chart.set_index(
                        "Timestamp"
                    ),
                    use_container_width=True,
                    height=360,
                )

        with chart_right:

            st.markdown(
                f"### Day-Ahead SPP — "
                f"{selected_market_point}"
            )

            if (
                market_dam_df.empty
                or selected_market_point
                not in market_dam_df.columns
            ):

                st.info(
                    "DAM SPP is currently unavailable."
                )

            else:

                dam_chart_day = (
                    market_dam_df[
                        "Oper Day"
                    ].max()
                )

                dam_chart = (
                    market_dam_df[
                        market_dam_df[
                            "Oper Day"
                        ]
                        == dam_chart_day
                    ][
                        [
                            "Timestamp",
                            selected_market_point,
                        ]
                    ]
                    .copy()
                )

                dam_chart = (
                    dam_chart.rename(
                        columns={
                            selected_market_point:
                                "DAM SPP ($/MWh)",
                        }
                    )
                )

                st.line_chart(
                    dam_chart.set_index(
                        "Timestamp"
                    ),
                    use_container_width=True,
                    height=360,
                )

        with st.expander(
            "📋 View Current Real-Time Price Intervals",
            expanded=False,
        ):

            rt_table_columns = [
                "Oper Day",
                "Interval Ending",
                *major_hubs,
            ]

            rt_table_columns = [
                column
                for column
                in rt_table_columns
                if column
                in market_rt_df.columns
            ]

            st.dataframe(
                market_rt_df[
                    rt_table_columns
                ].tail(
                    40
                ),
                use_container_width=True,
                hide_index=True,
            )

    if (
        market_lmp_df.empty
        and lmp_error
    ):

        st.caption(
            "Latest SCED LMP display could "
            "not be loaded; the RT SPP and "
            "DAM sections can still operate. "
            f"{lmp_error}"
        )

    if (
        market_dam_df.empty
        and dam_error
    ):

        st.warning(
            "DAM Settlement Point Prices "
            "could not be loaded. "
            f"{dam_error}"
        )

    st.divider()

    st.markdown(
        "## 🔋 DAM Ancillary Service Prices"
    )

    st.caption(
        "Day-Ahead Market Clearing Price "
        "for Capacity (MCPC) for Non-Spin, "
        "Regulation Down, Regulation Up, "
        "RRS and ECRS."
    )

    if market_mcpc_df.empty:

        st.info(
            "Current DAM ancillary-service "
            "clearing prices are not available "
            "from the public report right now. "
            + (
                mcpc_error
                if mcpc_error
                else ""
            )
        )

    else:

        ancillary_columns = [
            "NON-SPIN",
            "REG-DOWN",
            "REG-UP",
            "RRS",
            "ECRS",
        ]

        ancillary_columns = [
            column
            for column
            in ancillary_columns
            if column
            in market_mcpc_df.columns
        ]

        latest_mcpc_day = (
            market_mcpc_df[
                "Oper Day"
            ].max()
        )

        mcpc_today = (
            market_mcpc_df[
                market_mcpc_df[
                    "Oper Day"
                ]
                == latest_mcpc_day
            ]
            .copy()
        )

        ancillary_summary_rows = []

        for service in ancillary_columns:

            ancillary_summary_rows.append(
                {
                    "Service":
                        service,

                    "Daily Average":
                        mcpc_today[
                            service
                        ].mean(),

                    "Daily Peak":
                        mcpc_today[
                            service
                        ].max(),

                    "Peak Hour Ending":
                        (
                            mcpc_today.loc[
                                mcpc_today[
                                    service
                                ].idxmax(),
                                "Hour Ending",
                            ]
                            if mcpc_today[
                                service
                            ].notna().any()
                            else np.nan
                        ),
                }
            )

        ancillary_summary = pd.DataFrame(
            ancillary_summary_rows
        )

        st.dataframe(
            ancillary_summary,
            use_container_width=True,
            hide_index=True,
        )

        selected_ancillary = (
            st.selectbox(
                "Ancillary Service",
                options=
                    ancillary_columns,
                index=
                    (
                        ancillary_columns.index(
                            "ECRS"
                        )
                        if "ECRS"
                        in ancillary_columns
                        else 0
                    ),
                key=
                    "ercot_ancillary_service",
            )
        )

        mcpc_chart = (
            mcpc_today[
                [
                    "Timestamp",
                    selected_ancillary,
                ]
            ]
            .rename(
                columns={
                    selected_ancillary:
                        f"{selected_ancillary} MCPC",
                }
            )
        )

        st.line_chart(
            mcpc_chart.set_index(
                "Timestamp"
            ),
            use_container_width=True,
            height=320,
        )

        with st.expander(
            "📋 View DAM Ancillary Hourly Prices",
            expanded=False,
        ):

            st.dataframe(
                mcpc_today[
                    [
                        "Oper Day",
                        "Hour Ending",
                        *ancillary_columns,
                    ]
                ],
                use_container_width=True,
                hide_index=True,
            )

    st.divider()

    st.markdown(
        "### ERCOT Sources"
    )

    st.markdown(
        f"- [Latest SCED LMPs for Load Zones "
        f"and Trading Hubs]"
        f"({ERCOT_LATEST_LMP_URL})  \n"
        f"- [Real-Time Settlement Point Prices]"
        f"({ERCOT_RT_SPP_URL})  \n"
        f"- [Day-Ahead Settlement Point Prices]"
        f"({ERCOT_DAM_SPP_URL})  \n"
        f"- [DAM Clearing Prices for Capacity]"
        f"({ERCOT_DAM_MCPC_URL})"
    )

    st.caption(
        "ERCOT broad hub and load-zone prices "
        "are useful market benchmarks, but an "
        "individual generation project's realized "
        "price can differ materially because of "
        "nodal basis, congestion, curtailment and "
        "project-specific settlement mechanics."
    )


# ============================================================
# DASHBOARD GUIDE
# ============================================================

with dashboard_tab:

    st.markdown(
        "## 📘 Dashboard Guide"
    )

    guide_left, guide_right = st.columns(
        [
            1.55,
            1,
        ]
    )

    with guide_left:

        st.markdown(
            "### 🎯 Opportunity Score"
        )

        st.caption(
            "Projects are scored from 0–100 "
            "to prioritize attractive and "
            "actionable acquisition opportunities."
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
                    "Likelihood owner is motivated "
                    "to transact",

                    "Project maturity and progress "
                    "through development",

                    "Revenue visibility + ERCOT location",

                    "Tax-credit / siting attributes",

                    "Ability to realistically "
                    "execute a transaction",
                ],
            }
        )

        st.dataframe(
            scoring_methodology,
            use_container_width=True,
            hide_index=True,
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
            f"Market / Revenue = "
            f"Revenue Visibility × "
            f"{revenue_visibility_weight:.0%} "
            f"+ ERCOT Location × "
            f"{location_market_weight:.0%}."
        )

        st.caption(
            f"Executability = "
            f"Seller Actionability × "
            f"{actionability_weight:.0%} "
            f"+ Timing × "
            f"{timing_exec_weight:.0%} "
            f"+ Development Stage × "
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
            **5. Bundles** — Multiple 50–60 MW assets by owner  
            **6. Score Breakdown** — Drill into a project  
            **7. Map Explorer** — View all mapped projects  
            **8. ERCOT Competitor Due Diligence** — Orbit competitor screen  
            **9. ERCOT Market Prices** — Live market monitoring
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

    with st.expander(
        "📐 View Full Score Logic",
        expanded=False,
    ):

        st.markdown(
            "#### Seller Motivation"
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

        st.markdown(
            "#### Development Stage"
        )

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

        st.markdown(
            "#### Market / Revenue"
        )

        st.caption(
            f"Market / Revenue = "
            f"Revenue Visibility × "
            f"{revenue_visibility_weight:.0%} "
            f"+ ERCOT Location × "
            f"{location_market_weight:.0%}."
        )

        st.dataframe(
            pd.DataFrame(
                {
                    "Revenue Visibility": [
                        "Contract + Named Offtaker",
                        "Contract Type Known",
                        "Named Offtaker Only",
                        "Neither",
                    ],

                    "Score": [
                        market_both,
                        market_contract,
                        market_offtaker,
                        market_none,
                    ],
                }
            ),
            use_container_width=True,
            hide_index=True,
        )

    st.caption(
        "Screening tool only — rankings prioritize "
        "sourcing and diligence activity and are not "
        "a substitute for full investment underwriting."
    )

    st.divider()

    st.subheader(
        "Seller Motivation / Actionability Assumptions"
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
                    ],
                ),
            axis=1,
        ),
    )

    current_sellers.insert(
        4,
        "Actionability Score",
        current_sellers[
            "Seller Actionability"
        ].apply(
            actionability_score
        ),
    )

    edited_sellers_full = st.data_editor(
        current_sellers,
        use_container_width=True,
        hide_index=True,
        num_rows="dynamic",
        key="seller_assumptions_editor",
        disabled=[
            "Discount Score",
            "Actionability Score",
        ],
    )


editable_seller_columns = [
    "Owner",
    "Discount Potential",
    "Seller Actionability",
    "Confidence",
]


new_seller_assumptions = (
    edited_sellers_full[
        editable_seller_columns
    ].copy()
)


old_seller_assumptions = (
    st.session_state[
        "seller_assumptions"
    ][
        editable_seller_columns
    ].copy()
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
# LOAD DATA
# ============================================================

APP_DIR = Path(
    __file__
).resolve().parent


repo_csv_files = [
    path

    for path
    in APP_DIR.rglob(
        "*.csv"
    )

    if path.name.startswith(
        (
            "Power Projects-",
            "Power%20Projects-",
            "Power_Projects-",
        )
    )
]


repo_csv_files = sorted(
    repo_csv_files,
    key=lambda path:
        path.stat().st_mtime,
    reverse=True,
)


if uploaded_file is not None:

    df = pd.read_csv(
        uploaded_file
    )

    active_data_source = (
        "Optional uploaded CSV"
    )


elif repo_csv_files:

    df = pd.read_csv(
        repo_csv_files[0]
    )

    active_data_source = (
        repo_csv_files[0].name
    )


else:

    with dashboard_tab:

        st.info(
            "Add the latest Power Projects CSV "
            "to populate project-level analysis."
        )

    with map_tab:

        st.info(
            "The Map Explorer needs project data."
        )

    with competitor_tab:

        st.info(
            "The ERCOT Competitor Due Diligence "
            "tab needs the Orennia Power Projects CSV."
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


missing_columns = [
    col

    for col
    in required_columns

    if col
    not in df.columns
]


if missing_columns:

    st.error(
        "Missing required columns: "
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
    errors="coerce",
)


df[
    "Capacity (MW)"
] = pd.to_numeric(
    df[
        "Capacity (MW)"
    ],
    errors="coerce",
)


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


competitor_source = (
    df.copy()
)


# ============================================================
# ACQUISITION UNIVERSE
# ============================================================

df = df[
    (
        df[
            "Power Project Type"
        ].isin(
            [
                "Solar",
                "Storage",
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


df = df[
    ~df[
        "Owner"
    ].str.contains(
        "Pine Gate",
        case=False,
        na=False,
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


def get_seller_value(
    owner,
    column,
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
            "Discount Potential",
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
            "Seller Actionability",
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
            "Confidence",
        )
)


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
            ],
        ),
    axis=1,
)


def development_stage_score(
    row,
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
        or
        detailed == "Construction Complete"
    ):

        return development_operating

    if (
        "More Than 50%"
        in detailed
        or
        ">50%"
        in detailed
    ):

        return development_50

    if status == "In Construction":

        return development_construction

    if (
        status == "IA Executed"
        or
        ", IA"
        in detailed
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
        "Retired",
    ]:

        return development_inactive

    return development_studies


df[
    "Development Stage"
] = df.apply(
    development_stage_score,
    axis=1,
)


# ============================================================
# REVENUE VISIBILITY — UPDATED
# ============================================================

def revenue_visibility_score(
    row,
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

    if (
        contract
        and
        offtaker
    ):

        return market_both

    if contract:

        return market_contract

    if offtaker:

        return market_offtaker

    return market_none


df[
    "Revenue Visibility"
] = df.apply(
    revenue_visibility_score,
    axis=1,
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


energy_columns = [
    "Fossil Fuel Energy Communities",
    "Retired Coal Facilities Energy Communities",
    "Low Income Communities",
    "Native American Lands",
]


def energy_community(
    row,
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
            "1",
        ]:

            return "Yes"

    return "No"


df[
    "Energy Community"
] = df.apply(
    energy_community,
    axis=1,
)


def acquisition_value(
    row,
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

    if (
        tax_credit
        and
        ec
    ):

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
    axis=1,
)


df[
    "Domestic Content Review"
] = (
    "Unknown / Diligence Required"
)


as_of_date = pd.Timestamp(
    date.today()
)


def timing_score(
    row,
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
    axis=1,
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


def completeness(
    row,
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
    axis=1,
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


def action(
    row,
):

    if pd.isna(
        row[
            "Discount Potential"
        ]
    ):

        return (
            "RESEARCH / MONITOR"
        )

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
    axis=1,
)


df = (
    df.sort_values(
        by=[
            "Opportunity Score",
            "Data Completeness",
            "Capacity (MW)",
        ],
        ascending=[
            False,
            False,
            False,
        ],
    )
    .reset_index(
        drop=True
    )
)


df[
    "Rank"
] = np.arange(
    1,
    len(
        df
    ) + 1,
)


# ============================================================
# ACQUISITION DASHBOARD
# ============================================================

with dashboard_tab:

    c1, c2, c3, c4 = st.columns(
        4
    )

    c1.metric(
        "Projects Screened",
        f"{len(df):,}",
    )

    c2.metric(
        "Total Capacity",
        f"{df['Capacity (MW)'].sum():,.0f} MW",
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
        ),
    )

    c4.metric(
        "Top Score",
        f"{df['Opportunity Score'].max():.1f}",
    )

    st.divider()

    st.subheader(
        "🎯 Management Shortlist"
    )

    management_shortlist = (
        df.head(
            5
        ).copy()
    )

    management_shortlist[
        "Management Rank"
    ] = np.arange(
        1,
        len(
            management_shortlist
        ) + 1,
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
        "Action",
    ]

    management_columns = [
        col
        for col
        in management_columns
        if col
        in management_shortlist.columns
    ]

    st.dataframe(
        management_shortlist[
            management_columns
        ],
        use_container_width=True,
        hide_index=True,
    )

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
        ].dropna().unique()
    )

    selected_technology = (
        f1.multiselect(
            "Technology",
            technology_options,
            default=
                technology_options,
        )
    )

    ercot_area_options = sorted(
        df[
            "ERCOT Area"
        ].dropna().unique()
    )

    selected_ercot_areas = (
        f2.multiselect(
            "ERCOT Area",
            ercot_area_options,
            default=
                ercot_area_options,
        )
    )

    owner_options = sorted(
        [
            owner

            for owner
            in df[
                "Owner"
            ].unique()

            if clean_text(
                owner
            )
        ]
    )

    selected_owners = (
        f3.multiselect(
            "Owner",
            owner_options,
        )
    )

    status_options = sorted(
        df[
            "Power Project Status"
        ].dropna().unique()
    )

    selected_status = (
        f4.multiselect(
            "Project Status",
            status_options,
            default=
                status_options,
        )
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

        for col
        in display_columns

        if col
        in filtered.columns
    ]

    top_20 = (
        filtered[
            existing_display_columns
        ]
        .head(
            20
        )
    )

    st.dataframe(
        top_20,
        use_container_width=True,
        hide_index=True,
    )

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
            key="score_breakdown_project",
        )

        project = (
            filtered[
                filtered[
                    "Power Project Name"
                ]
                == selected_project
            ]
            .iloc[0]
        )

        p1, p2, p3, p4, p5 = st.columns(
            5
        )

        p1.metric(
            "ERCOT Area",
            project[
                "ERCOT Area"
            ],
        )

        p2.metric(
            "Location Score",
            f"{project['Location Score']:.0f}",
        )

        p3.metric(
            "COD",
            format_date(
                project.get(
                    "First Power Date"
                )
            ),
        )

        p4.metric(
            "Capacity",
            f"{project['Capacity (MW)']:,.1f} MW",
        )

        p5.metric(
            "Status",
            clean_text(
                project.get(
                    "Power Project Status"
                )
            ),
        )

        st.markdown(
            "#### Market / Revenue"
        )

        m1, m2, m3 = st.columns(
            3
        )

        m1.metric(
            "Revenue Visibility",
            f"{project['Revenue Visibility']:.1f}",
        )

        m2.metric(
            "Location Score",
            f"{project['Location Score']:.1f}",
        )

        m3.metric(
            "Market / Revenue Score",
            f"{project['Market / Revenue']:.1f}",
        )

        st.caption(
            f"Contract Type: "
            f"**{clean_text(project.get('Contract Type')) or 'Unknown'}** | "
            f"Offtaker: "
            f"**{clean_text(project.get('Contract Offtaker')) or 'Unknown'}**"
        )

    st.divider()

    csv = (
        df.to_csv(
            index=False
        )
        .encode(
            "utf-8"
        )
    )

    st.download_button(
        "⬇️ Download Scored ERCOT Universe",
        data=csv,
        file_name=
            "ERCOT_Scored_Acquisition_Universe.csv",
        mime="text/csv",
    )


# ============================================================
# ERCOT COMPETITOR DUE DILIGENCE
# ============================================================

with competitor_tab:

    st.markdown(
        "## 🎯 ERCOT Competitor Due Diligence"
    )

    st.caption(
        "Project Orbit competitive screen using "
        "the current Orennia project universe. "
        "The competitor definition is Storage / "
        "BESS in ERCOT South."
    )

    ORBIT_PROJECT_ALIASES = [
        "orbit",
        "gunsight",
    ]


    def _orbit_name_mask(
        frame,
    ):

        project_names = (
            frame[
                "Power Project Name"
            ]
            .fillna(
                ""
            )
            .astype(
                str
            )
            .str.lower()
        )

        mask = pd.Series(
            False,
            index=frame.index,
        )

        for alias in ORBIT_PROJECT_ALIASES:

            mask = (
                mask
                |
                project_names.str.contains(
                    alias,
                    regex=False,
                    na=False,
                )
            )

        return mask


    def _queue_stage(
        row,
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

        combined = (
            status
            + " "
            + detailed
        ).lower()

        if status in [
            "Inactive",
            "Suspended",
            "Retired",
        ]:

            return (
                "Inactive / Suspended / Retired",
                90,
            )

        if (
            status == "Operating"
            or
            "construction complete"
            in combined
        ):

            return (
                "Operating / Complete",
                10,
            )

        if (
            status == "In Construction"
            or
            "in construction"
            in combined
        ):

            return (
                "In Construction",
                20,
            )

        if (
            status == "IA Executed"
            or
            "ia executed"
            in combined
        ):

            return (
                "IA Executed",
                30,
            )

        if (
            "fis completed"
            in combined
        ):

            return (
                "FIS Completed",
                40,
            )

        if (
            "fis started"
            in combined
        ):

            return (
                "FIS Started",
                50,
            )

        if (
            status == "Pre-Study"
            or
            "pre-study"
            in combined
        ):

            return (
                "Pre-Study",
                70,
            )

        if (
            "study"
            in combined
        ):

            return (
                "Studies Undergoing / Other",
                60,
            )

        return (
            "Other / Unknown",
            80,
        )


    def _queue_cycle_sort_value(
        value,
    ):

        text = clean_text(
            value
        )

        if not text:

            return np.nan

        year_match = re.search(
            "\\b(20\\d{2})\\b",
            text,
        )

        if year_match:

            return float(
                year_match.group(
                    1
                )
            )

        number_match = re.search(
            "\\d+(?:\\.\\d+)?",
            text,
        )

        if number_match:

            try:

                return float(
                    number_match.group(
                        0
                    )
                )

            except Exception:

                return np.nan

        return np.nan


    def _queue_project_key(
        row,
    ):

        return (
            clean_text(
                row.get(
                    "Power Project Name"
                )
            )
            + "|"
            + clean_text(
                row.get(
                    "Owner"
                )
            )
            + "|"
            + clean_text(
                row.get(
                    "Queue ID"
                )
            )
        ).lower()


    def _add_queue_metadata(
        frame,
        reference_type="Competitor",
    ):

        result = frame.copy()

        result[
            "Queue Reference"
        ] = reference_type

        result[
            "Queue Project Key"
        ] = result.apply(
            _queue_project_key,
            axis=1,
        )

        if result.empty:

            result[
                "Queue Stage"
            ] = pd.Series(
                dtype="object"
            )

            result[
                "Queue Stage Rank"
            ] = pd.Series(
                dtype="float64"
            )

        else:

            queue_stage_data = result.apply(
                lambda row:
                    pd.Series(
                        _queue_stage(
                            row
                        ),
                        index=[
                            "Queue Stage",
                            "Queue Stage Rank",
                        ],
                    ),
                axis=1,
            )

            result[
                "Queue Stage"
            ] = queue_stage_data[
                "Queue Stage"
            ]

            result[
                "Queue Stage Rank"
            ] = pd.to_numeric(
                queue_stage_data[
                    "Queue Stage Rank"
                ],
                errors="coerce",
            )

        if "Queue Date" in result.columns:

            result[
                "Queue Date Parsed"
            ] = pd.to_datetime(
                result[
                    "Queue Date"
                ],
                errors="coerce",
            )

        else:

            result[
                "Queue Date Parsed"
            ] = pd.NaT

        if "Queue Cycle" in result.columns:

            result[
                "Queue Cycle Sort"
            ] = result[
                "Queue Cycle"
            ].apply(
                _queue_cycle_sort_value
            )

        else:

            result[
                "Queue Cycle Sort"
            ] = np.nan

        return result


    orbit_reference_candidates = (
        competitor_source[
            _orbit_name_mask(
                competitor_source
            )
        ]
        .copy()
    )

    if not orbit_reference_candidates.empty:

        orbit_reference_candidates = (
            orbit_reference_candidates
            .sort_values(
                by=[
                    "Capacity (MW)",
                    "First Power Date",
                ],
                ascending=[
                    False,
                    True,
                ],
                na_position="last",
            )
        )

        orbit_reference_labels = (
            orbit_reference_candidates
            .apply(
                lambda row:
                    f"{clean_text(row.get('Power Project Name'))} — "
                    f"{clean_text(row.get('Owner')) or 'Unknown Owner'} — "
                    f"{row.get('Capacity (MW)', np.nan):,.1f} MW",
                axis=1,
            )
            .tolist()
        )

        orbit_reference_label = (
            st.selectbox(
                "Project Orbit reference",
                options=
                    orbit_reference_labels,
                index=0,
                key=
                    "orbit_competitor_reference",
            )
        )

        orbit_reference = (
            orbit_reference_candidates
            .iloc[
                orbit_reference_labels.index(
                    orbit_reference_label
                )
            ]
        )

    else:

        orbit_reference = None


    competitor_base = (
        competitor_source[
            (
                competitor_source[
                    "ERCOT Area"
                ]
                == "ERCOT-S"
            )
            &
            (
                competitor_source[
                    "Power Project Type"
                ]
                == "Storage"
            )
            &
            (
                ~_orbit_name_mask(
                    competitor_source
                )
            )
        ]
        .copy()
    )


    if competitor_base.empty:

        st.warning(
            "No ERCOT South storage projects "
            "were found in the active Orennia file."
        )

    else:

        st.markdown(
            "### Competitor Universe"
        )

        (
            filter_1,
            filter_2,
            filter_3,
            filter_4,
            filter_5,
            filter_6,
        ) = st.columns(
            [
                1.10,
                1.20,
                1.00,
                0.72,
                0.72,
                1.05,
            ]
        )

        competitor_status_options = sorted(
            [
                value

                for value
                in competitor_base[
                    "Power Project Status"
                ]
                .dropna()
                .astype(
                    str
                )
                .unique()
                .tolist()

                if clean_text(
                    value
                )
            ]
        )

        with filter_1:

            competitor_status_filter = (
                st.multiselect(
                    "Project Status",
                    options=
                        competitor_status_options,
                    default=
                        competitor_status_options,
                    key=
                        "orbit_competitor_status_filter",
                )
            )

        competitor_owner_options = sorted(
            [
                value

                for value
                in competitor_base[
                    "Owner"
                ]
                .fillna(
                    ""
                )
                .astype(
                    str
                )
                .unique()
                .tolist()

                if clean_text(
                    value
                )
            ]
        )

        with filter_2:

            competitor_owner_filter = (
                st.multiselect(
                    "Owner / Developer",
                    options=
                        competitor_owner_options,
                    default=[],
                    placeholder=
                        "All owners",
                    key=
                        "orbit_competitor_owner_filter",
                )
            )

        competitor_county_options = (
            sorted(
                [
                    value

                    for value
                    in competitor_base[
                        "County"
                    ]
                    .dropna()
                    .astype(
                        str
                    )
                    .unique()
                    .tolist()

                    if clean_text(
                        value
                    )
                ]
            )

            if "County"
            in competitor_base.columns

            else []
        )

        with filter_3:

            competitor_county_filter = (
                st.multiselect(
                    "County",
                    options=
                        competitor_county_options,
                    default=[],
                    placeholder=
                        "All counties",
                    key=
                        "orbit_competitor_county_filter",
                    disabled=
                        (
                            len(
                                competitor_county_options
                            )
                            == 0
                        ),
                )
            )

        with filter_4:

            competitor_min_mw = (
                st.number_input(
                    "Min MW",
                    min_value=0.0,
                    value=250.0,
                    step=1.0,
                    key=
                        "orbit_competitor_min_mw",
                )
            )

        with filter_5:

            competitor_max_mw = (
                st.number_input(
                    "Max MW",
                    min_value=0.0,
                    value=700.0,
                    step=1.0,
                    key=
                        "orbit_competitor_max_mw",
                )
            )

        competitor_cod_years = sorted(
            competitor_base[
                "First Power Date"
            ]
            .dropna()
            .dt.year
            .astype(
                int
            )
            .unique()
            .tolist()
        )

        competitor_cod_options = [
            str(
                year
            )

            for year
            in competitor_cod_years
        ] + [
            "COD Missing",
        ]

        with filter_6:

            competitor_cod_filter = (
                st.multiselect(
                    "COD",
                    options=
                        competitor_cod_options,
                    default=[],
                    placeholder=
                        "All CODs",
                    key=
                        "orbit_competitor_cod_filter",
                )
            )

        competitor_view = (
            competitor_base.copy()
        )

        if competitor_status_filter:

            competitor_view = (
                competitor_view[
                    competitor_view[
                        "Power Project Status"
                    ].isin(
                        competitor_status_filter
                    )
                ]
            )

        else:

            competitor_view = (
                competitor_view
                .iloc[
                    0:0
                ]
            )

        if competitor_owner_filter:

            competitor_view = (
                competitor_view[
                    competitor_view[
                        "Owner"
                    ].isin(
                        competitor_owner_filter
                    )
                ]
            )

        if (
            competitor_county_filter
            and
            "County"
            in competitor_view.columns
        ):

            competitor_view = (
                competitor_view[
                    competitor_view[
                        "County"
                    ]
                    .astype(
                        str
                    )
                    .isin(
                        competitor_county_filter
                    )
                ]
            )

        if competitor_cod_filter:

            selected_cod_years = [
                int(
                    value
                )

                for value
                in competitor_cod_filter

                if value
                != "COD Missing"
            ]

            include_missing_cod = (
                "COD Missing"
                in competitor_cod_filter
            )

            cod_mask = pd.Series(
                False,
                index=
                    competitor_view.index,
            )

            if selected_cod_years:

                cod_mask = (
                    cod_mask
                    |
                    competitor_view[
                        "First Power Date"
                    ]
                    .dt.year
                    .isin(
                        selected_cod_years
                    )
                )

            if include_missing_cod:

                cod_mask = (
                    cod_mask
                    |
                    competitor_view[
                        "First Power Date"
                    ].isna()
                )

            competitor_view = (
                competitor_view[
                    cod_mask
                ]
            )

        if (
            competitor_max_mw
            < competitor_min_mw
        ):

            st.error(
                "Max MW must be greater than "
                "or equal to Min MW."
            )

            competitor_view = (
                competitor_view
                .iloc[
                    0:0
                ]
                .copy()
            )

        else:

            competitor_view = (
                competitor_view[
                    competitor_view[
                        "Capacity (MW)"
                    ].between(
                        competitor_min_mw,
                        competitor_max_mw,
                        inclusive="both",
                    )
                ]
                .copy()
            )


        # ----------------------------------------------------
        # QUEUE PLACEMENT
        # ----------------------------------------------------

        competitor_view = (
            _add_queue_metadata(
                competitor_view,
                reference_type="Competitor",
            )
        )

        queue_frames = [
            competitor_view.copy()
        ]

        if orbit_reference is not None:

            orbit_queue_row = pd.DataFrame(
                [
                    orbit_reference.to_dict()
                ]
            )

            orbit_queue_row = (
                _add_queue_metadata(
                    orbit_queue_row,
                    reference_type=
                        "Project Orbit",
                )
            )

            queue_frames.append(
                orbit_queue_row
            )

        queue_comparison = pd.concat(
            queue_frames,
            ignore_index=True,
            sort=False,
        )

        queue_comparison = (
            queue_comparison
            .sort_values(
                by=[
                    "Queue Stage Rank",
                    "Queue Date Parsed",
                    "Queue Cycle Sort",
                    "First Power Date",
                    "Capacity (MW)",
                ],
                ascending=[
                    True,
                    True,
                    True,
                    True,
                    False,
                ],
                na_position="last",
            )
            .reset_index(
                drop=True
            )
        )

        queue_comparison[
            "Filtered Queue Placement"
        ] = np.arange(
            1,
            len(
                queue_comparison
            ) + 1,
        )

        competitor_queue_lookup = (
            queue_comparison[
                queue_comparison[
                    "Queue Reference"
                ]
                == "Competitor"
            ]
            .drop_duplicates(
                subset=[
                    "Queue Project Key",
                ],
                keep="first",
            )
            .set_index(
                "Queue Project Key"
            )[
                "Filtered Queue Placement"
            ]
            .to_dict()
        )

        competitor_view[
            "Filtered Queue Placement"
        ] = competitor_view[
            "Queue Project Key"
        ].map(
            competitor_queue_lookup
        )


        orbit_capacity = np.nan

        if orbit_reference is not None:

            orbit_capacity = (
                pd.to_numeric(
                    pd.Series(
                        [
                            orbit_reference.get(
                                "Capacity (MW)"
                            )
                        ]
                    ),
                    errors="coerce",
                )
                .iloc[0]
            )

        if pd.notna(
            orbit_capacity
        ):

            competitor_view[
                "MW Delta vs Orbit"
            ] = (
                competitor_view[
                    "Capacity (MW)"
                ]
                - orbit_capacity
            )

            competitor_view[
                "Absolute MW Delta vs Orbit"
            ] = (
                competitor_view[
                    "MW Delta vs Orbit"
                ].abs()
            )


        # ----------------------------------------------------
        # QUEUE DISPLAY
        # ----------------------------------------------------

        st.divider()

        st.markdown(
            "### 🔌 Filtered Interconnection Queue Placement"
        )

        orbit_queue_rows = (
            queue_comparison[
                queue_comparison[
                    "Queue Reference"
                ]
                == "Project Orbit"
            ]
        )

        orbit_queue_position = np.nan

        if not orbit_queue_rows.empty:

            orbit_queue_position = int(
                orbit_queue_rows[
                    "Filtered Queue Placement"
                ].iloc[0]
            )

        q1, q2, q3, q4 = st.columns(
            4
        )

        q1.metric(
            "Orbit Queue Placement",
            (
                f"#{orbit_queue_position} "
                f"of {len(queue_comparison)}"

                if pd.notna(
                    orbit_queue_position
                )

                else "N/A"
            ),
        )

        q2.metric(
            "Projects Ahead of Orbit",
            (
                orbit_queue_position - 1

                if pd.notna(
                    orbit_queue_position
                )

                else "N/A"
            ),
        )

        q3.metric(
            "Projects Behind Orbit",
            (
                len(
                    queue_comparison
                )
                - orbit_queue_position

                if pd.notna(
                    orbit_queue_position
                )

                else "N/A"
            ),
        )

        q4.metric(
            "Filtered Queue Leader",
            (
                clean_text(
                    queue_comparison[
                        "Power Project Name"
                    ].iloc[0]
                )
                if not queue_comparison.empty
                else "N/A"
            ),
        )

        queue_table_columns = [
            "Filtered Queue Placement",
            "Queue Reference",
            "Power Project Name",
            "Owner",
            "County",
            "Capacity (MW)",
            "Queue Stage",
            "Queue ID",
            "Queue Cycle",
            "Queue Date Parsed",
            "Point of Interconnection",
            "First Power Date",
        ]

        queue_table_columns = [
            column

            for column
            in queue_table_columns

            if column
            in queue_comparison.columns
        ]

        queue_table = (
            queue_comparison[
                queue_table_columns
            ]
            .copy()
        )

        queue_table = (
            queue_table.rename(
                columns={
                    "Queue Date Parsed":
                        "Queue Date",

                    "First Power Date":
                        "COD",
                }
            )
        )

        st.dataframe(
            queue_table,
            use_container_width=True,
            hide_index=True,
        )


        # ----------------------------------------------------
        # IX COST DILIGENCE
        # ----------------------------------------------------

        st.divider()

        st.markdown(
            "### 💵 Interconnection Cost Diligence"
        )

        st.caption(
            "Competitor IX costs are sourced from "
            "the active Orennia export. Orbit can "
            "be overridden with the latest GCI / "
            "FIS / SGIA diligence number."
        )

        ix_physical_col = (
            "Interconnection Cost Physical ($)"
            if
            "Interconnection Cost Physical ($)"
            in competitor_view.columns
            else None
        )

        ix_upgrade_col = (
            "Interconnection Cost System Upgrade ($)"
            if
            "Interconnection Cost System Upgrade ($)"
            in competitor_view.columns
            else None
        )

        ix_total_col = (
            "Interconnection Cost Total ($)"
            if
            "Interconnection Cost Total ($)"
            in competitor_view.columns
            else None
        )

        if ix_total_col is None:

            st.info(
                "Add Interconnection Cost Physical ($), "
                "Interconnection Cost System Upgrade ($), "
                "and Interconnection Cost Total ($) "
                "to the Orennia export."
            )

        else:

            competitor_view[
                "IX Cost Total ($)"
            ] = competitor_view[
                ix_total_col
            ].apply(
                _numeric_money_value
            )

            competitor_view[
                "IX Cost Physical ($)"
            ] = (
                competitor_view[
                    ix_physical_col
                ].apply(
                    _numeric_money_value
                )
                if ix_physical_col
                else np.nan
            )

            competitor_view[
                "IX Cost System Upgrade ($)"
            ] = (
                competitor_view[
                    ix_upgrade_col
                ].apply(
                    _numeric_money_value
                )
                if ix_upgrade_col
                else np.nan
            )

            competitor_view[
                "IX Cost ($/kW)"
            ] = competitor_view.apply(
                lambda row:
                    _ix_cost_per_kw(
                        row.get(
                            "IX Cost Total ($)"
                        ),
                        row.get(
                            "Capacity (MW)"
                        ),
                    ),
                axis=1,
            )

            orbit_ix_total_source = np.nan
            orbit_ix_physical_source = np.nan
            orbit_ix_upgrade_source = np.nan

            if orbit_reference is not None:

                orbit_ix_total_source = (
                    _numeric_money_value(
                        orbit_reference.get(
                            ix_total_col
                        )
                    )
                )

                if ix_physical_col:

                    orbit_ix_physical_source = (
                        _numeric_money_value(
                            orbit_reference.get(
                                ix_physical_col
                            )
                        )
                    )

                if ix_upgrade_col:

                    orbit_ix_upgrade_source = (
                        _numeric_money_value(
                            orbit_reference.get(
                                ix_upgrade_col
                            )
                        )
                    )

            override_col_1, override_col_2, override_col_3 = st.columns(
                3
            )

            with override_col_1:

                orbit_ix_total_override_mm = st.number_input(
                    "Orbit Total IX Cost ($MM)",
                    min_value=0.0,
                    value=(
                        float(
                            orbit_ix_total_source
                            / 1_000_000.0
                        )
                        if pd.notna(
                            orbit_ix_total_source
                        )
                        else 0.0
                    ),
                    step=0.1,
                    key=
                        "orbit_total_ix_cost_override_mm",
                )

            with override_col_2:

                orbit_ix_physical_override_mm = st.number_input(
                    "Orbit Physical IX Cost ($MM)",
                    min_value=0.0,
                    value=(
                        float(
                            orbit_ix_physical_source
                            / 1_000_000.0
                        )
                        if pd.notna(
                            orbit_ix_physical_source
                        )
                        else 0.0
                    ),
                    step=0.1,
                    key=
                        "orbit_physical_ix_cost_override_mm",
                )

            with override_col_3:

                orbit_ix_upgrade_override_mm = st.number_input(
                    "Orbit System Upgrade Cost ($MM)",
                    min_value=0.0,
                    value=(
                        float(
                            orbit_ix_upgrade_source
                            / 1_000_000.0
                        )
                        if pd.notna(
                            orbit_ix_upgrade_source
                        )
                        else 0.0
                    ),
                    step=0.1,
                    key=
                        "orbit_upgrade_ix_cost_override_mm",
                )

            orbit_ix_total = (
                orbit_ix_total_override_mm
                * 1_000_000.0
                if
                orbit_ix_total_override_mm > 0
                else orbit_ix_total_source
            )

            orbit_ix_physical = (
                orbit_ix_physical_override_mm
                * 1_000_000.0
                if
                orbit_ix_physical_override_mm > 0
                else orbit_ix_physical_source
            )

            orbit_ix_upgrade = (
                orbit_ix_upgrade_override_mm
                * 1_000_000.0
                if
                orbit_ix_upgrade_override_mm > 0
                else orbit_ix_upgrade_source
            )

            orbit_ix_cost_per_kw = (
                _ix_cost_per_kw(
                    orbit_ix_total,
                    orbit_capacity,
                )
            )

            valid_peer_ix = (
                competitor_view[
                    competitor_view[
                        "IX Cost ($/kW)"
                    ].notna()
                ]
                .copy()
            )

            peer_median_ix_per_kw = (
                valid_peer_ix[
                    "IX Cost ($/kW)"
                ].median()
                if not valid_peer_ix.empty
                else np.nan
            )

            orbit_vs_peer_median_pct = (
                orbit_ix_cost_per_kw
                / peer_median_ix_per_kw
                - 1.0
                if (
                    pd.notna(
                        orbit_ix_cost_per_kw
                    )
                    and
                    pd.notna(
                        peer_median_ix_per_kw
                    )
                    and
                    peer_median_ix_per_kw != 0
                )
                else np.nan
            )

            ix_rank_frame = (
                valid_peer_ix[
                    [
                        "Queue Project Key",
                        "IX Cost ($/kW)",
                    ]
                ]
                .copy()
            )

            if pd.notna(
                orbit_ix_cost_per_kw
            ):

                ix_rank_frame = pd.concat(
                    [
                        ix_rank_frame,
                        pd.DataFrame(
                            [
                                {
                                    "Queue Project Key":
                                        "__orbit__",

                                    "IX Cost ($/kW)":
                                        orbit_ix_cost_per_kw,
                                }
                            ]
                        ),
                    ],
                    ignore_index=True,
                )

            ix_rank_frame = (
                ix_rank_frame
                .sort_values(
                    "IX Cost ($/kW)",
                    ascending=True,
                    na_position="last",
                )
                .reset_index(
                    drop=True
                )
            )

            ix_rank_frame[
                "Filtered IX Cost Rank"
            ] = np.arange(
                1,
                len(
                    ix_rank_frame
                ) + 1,
            )

            peer_ix_rank_lookup = (
                ix_rank_frame[
                    ix_rank_frame[
                        "Queue Project Key"
                    ]
                    != "__orbit__"
                ]
                .set_index(
                    "Queue Project Key"
                )[
                    "Filtered IX Cost Rank"
                ]
                .to_dict()
            )

            competitor_view[
                "Filtered IX Cost Rank"
            ] = competitor_view[
                "Queue Project Key"
            ].map(
                peer_ix_rank_lookup
            )

            competitor_view[
                "IX $/kW Delta vs Orbit"
            ] = (
                competitor_view[
                    "IX Cost ($/kW)"
                ]
                - orbit_ix_cost_per_kw
                if pd.notna(
                    orbit_ix_cost_per_kw
                )
                else np.nan
            )

            competitor_view[
                "IX % vs Orbit"
            ] = (
                (
                    competitor_view[
                        "IX Cost ($/kW)"
                    ]
                    / orbit_ix_cost_per_kw
                    - 1.0
                )
                * 100.0
                if (
                    pd.notna(
                        orbit_ix_cost_per_kw
                    )
                    and
                    orbit_ix_cost_per_kw != 0
                )
                else np.nan
            )

            orbit_ix_rank = np.nan

            if pd.notna(
                orbit_ix_cost_per_kw
            ):

                orbit_rank_rows = (
                    ix_rank_frame[
                        ix_rank_frame[
                            "Queue Project Key"
                        ]
                        == "__orbit__"
                    ]
                )

                if not orbit_rank_rows.empty:

                    orbit_ix_rank = int(
                        orbit_rank_rows[
                            "Filtered IX Cost Rank"
                        ].iloc[0]
                    )

            ix1, ix2, ix3, ix4, ix5 = st.columns(
                5
            )

            ix1.metric(
                "Orbit Total IX Cost",
                (
                    f"${orbit_ix_total / 1_000_000:,.1f}MM"
                    if pd.notna(
                        orbit_ix_total
                    )
                    else "N/A"
                ),
            )

            ix2.metric(
                "Orbit IX Cost $/kW",
                (
                    f"${orbit_ix_cost_per_kw:,.0f}/kW"
                    if pd.notna(
                        orbit_ix_cost_per_kw
                    )
                    else "N/A"
                ),
            )

            ix3.metric(
                "Peer Median IX $/kW",
                (
                    f"${peer_median_ix_per_kw:,.0f}/kW"
                    if pd.notna(
                        peer_median_ix_per_kw
                    )
                    else "N/A"
                ),
            )

            ix4.metric(
                "Orbit vs Peer Median",
                (
                    f"{orbit_vs_peer_median_pct:+.1%}"
                    if pd.notna(
                        orbit_vs_peer_median_pct
                    )
                    else "N/A"
                ),
            )

            ix5.metric(
                "Orbit IX Cost Rank",
                (
                    f"#{orbit_ix_rank} of {len(ix_rank_frame)}"
                    if pd.notna(
                        orbit_ix_rank
                    )
                    else "N/A"
                ),
            )

            ix_table_columns = [
                "Filtered IX Cost Rank",
                "Power Project Name",
                "Owner",
                "County",
                "Capacity (MW)",
                "Queue Stage",
                "Filtered Queue Placement",
                "IX Cost Physical ($)",
                "IX Cost System Upgrade ($)",
                "IX Cost Total ($)",
                "IX Cost ($/kW)",
                "IX $/kW Delta vs Orbit",
                "IX % vs Orbit",
                "First Power Date",
            ]

            ix_table_columns = [
                column

                for column
                in ix_table_columns

                if column
                in competitor_view.columns
            ]

            ix_table = (
                competitor_view[
                    ix_table_columns
                ]
                .sort_values(
                    by=[
                        "Filtered IX Cost Rank",
                        "IX Cost ($/kW)",
                    ],
                    ascending=[
                        True,
                        True,
                    ],
                    na_position="last",
                )
            )

            st.dataframe(
                ix_table,
                use_container_width=True,
                hide_index=True,
            )


        # ----------------------------------------------------
        # NODAL MARKET DILIGENCE
        # ----------------------------------------------------

        st.divider()

        st.markdown(
            "### ⚡ Nodal Market Diligence & Forecast"
        )

        st.caption(
            "Uses ERCOT public nodal products "
            "for recent SCED LMP, Look-Ahead RTD "
            "indicative LMPs and Day-Ahead prices."
        )

        nodal_project_rows = []

        if orbit_reference is not None:

            orbit_row_dict = (
                orbit_reference.to_dict()
            )

            orbit_row_dict[
                "Nodal Reference Type"
            ] = "Project Orbit"

            nodal_project_rows.append(
                orbit_row_dict
            )

        for _, competitor_row in competitor_view.iterrows():

            competitor_dict = (
                competitor_row.to_dict()
            )

            competitor_dict[
                "Nodal Reference Type"
            ] = "Competitor"

            nodal_project_rows.append(
                competitor_dict
            )

        nodal_project_frame = pd.DataFrame(
            nodal_project_rows
        )

        if nodal_project_frame.empty:

            st.info(
                "No project is available "
                "for nodal diligence."
            )

        else:

            nodal_project_frame[
                "Nodal Project Label"
            ] = nodal_project_frame.apply(
                lambda row:
                    f"{clean_text(row.get('Nodal Reference Type'))} — "
                    f"{clean_text(row.get('Power Project Name'))} — "
                    f"{clean_text(row.get('Owner')) or 'Unknown Owner'} — "
                    f"{row.get('Capacity (MW)', np.nan):,.0f} MW",
                axis=1,
            )

            nodal_project_label = st.selectbox(
                "Project for nodal pricing",
                options=
                    nodal_project_frame[
                        "Nodal Project Label"
                    ].tolist(),
                index=0,
                key=
                    "orbit_nodal_project_selector",
            )

            nodal_project = (
                nodal_project_frame[
                    nodal_project_frame[
                        "Nodal Project Label"
                    ]
                    == nodal_project_label
                ]
                .iloc[0]
            )

            detected_node_column = (
                _detect_project_node_column(
                    nodal_project_frame
                )
            )

            detected_node = ""

            if detected_node_column:

                detected_node = clean_text(
                    nodal_project.get(
                        detected_node_column
                    )
                )

            area_hub_map = {
                "ERCOT-N":
                    "HB_NORTH",

                "ERCOT-H":
                    "HB_HOUSTON",

                "ERCOT-S":
                    "HB_SOUTH",

                "ERCOT-W":
                    "HB_WEST",

                "Panhandle":
                    "HB_PAN",
            }

            project_area_for_node = clean_text(
                nodal_project.get(
                    "ERCOT Area"
                )
            )

            nodal_benchmark_hub = (
                area_hub_map.get(
                    project_area_for_node,
                    "HB_SOUTH",
                )
            )

            selected_resource_node = st.text_input(
                "ERCOT Resource Node / Settlement Point",
                value=
                    detected_node,
                key=
                    "orbit_nodal_resource_node",
                placeholder=
                    "Enter exact ERCOT Resource Node / Settlement Point",
            ).strip()

            nodal_api_config = (
                _get_ercot_api_config()
            )

            if not nodal_api_config[
                "configured"
            ]:

                st.warning(
                    "ERCOT Public Data API credentials "
                    "are not configured."
                )

                with st.expander(
                    "ERCOT API setup",
                    expanded=False,
                ):

                    st.code(
                        """
[ercot_api]
username = "your@email.com"
password = "your_password"
subscription_key = "your_subscription_key"
""",
                        language="toml",
                    )

            nodal_actual = pd.DataFrame()
            hub_actual = pd.DataFrame()
            nodal_rtd = pd.DataFrame()
            hub_rtd = pd.DataFrame()
            nodal_dam = pd.DataFrame()
            hub_dam = pd.DataFrame()

            if (
                selected_resource_node
                and
                nodal_api_config[
                    "configured"
                ]
            ):

                try:

                    nodal_token = (
                        _ercot_api_authenticate(
                            nodal_api_config[
                                "username"
                            ],
                            nodal_api_config[
                                "password"
                            ],
                        )
                    )

                    nodal_actual = (
                        _fetch_ercot_nodal_actual(
                            selected_resource_node,
                            nodal_token,
                            nodal_api_config[
                                "subscription_key"
                            ],
                        )
                    )

                    hub_actual = (
                        _fetch_ercot_nodal_actual(
                            nodal_benchmark_hub,
                            nodal_token,
                            nodal_api_config[
                                "subscription_key"
                            ],
                        )
                    )

                    nodal_rtd = (
                        _fetch_ercot_rtd_nodal_forecast(
                            selected_resource_node,
                            nodal_token,
                            nodal_api_config[
                                "subscription_key"
                            ],
                        )
                    )

                    hub_rtd = (
                        _fetch_ercot_rtd_nodal_forecast(
                            nodal_benchmark_hub,
                            nodal_token,
                            nodal_api_config[
                                "subscription_key"
                            ],
                        )
                    )

                    nodal_dam = (
                        _fetch_ercot_dam_nodal(
                            selected_resource_node,
                            nodal_token,
                            nodal_api_config[
                                "subscription_key"
                            ],
                        )
                    )

                    hub_dam = (
                        _fetch_ercot_dam_nodal(
                            nodal_benchmark_hub,
                            nodal_token,
                            nodal_api_config[
                                "subscription_key"
                            ],
                        )
                    )

                except Exception as exc:

                    st.error(
                        "ERCOT nodal API request failed. "
                        + clean_text(
                            exc
                        )
                    )

            latest_node_lmp = np.nan
            latest_hub_lmp = np.nan

            if (
                not nodal_actual.empty
                and
                "Nodal LMP"
                in nodal_actual.columns
            ):

                valid_node_actual = (
                    nodal_actual[
                        nodal_actual[
                            "Nodal LMP"
                        ].notna()
                    ]
                )

                if not valid_node_actual.empty:

                    latest_node_lmp = (
                        valid_node_actual[
                            "Nodal LMP"
                        ].iloc[-1]
                    )

            if (
                not hub_actual.empty
                and
                "Nodal LMP"
                in hub_actual.columns
            ):

                valid_hub_actual = (
                    hub_actual[
                        hub_actual[
                            "Nodal LMP"
                        ].notna()
                    ]
                )

                if not valid_hub_actual.empty:

                    latest_hub_lmp = (
                        valid_hub_actual[
                            "Nodal LMP"
                        ].iloc[-1]
                    )

            latest_rt_basis = (
                latest_node_lmp
                - latest_hub_lmp

                if (
                    pd.notna(
                        latest_node_lmp
                    )
                    and
                    pd.notna(
                        latest_hub_lmp
                    )
                )

                else np.nan
            )

            rtd_terminal_price = np.nan
            rtd_average_price = np.nan

            if (
                not nodal_rtd.empty
                and
                "Forecast LMP"
                in nodal_rtd.columns
            ):

                valid_rtd = (
                    nodal_rtd[
                        nodal_rtd[
                            "Forecast LMP"
                        ].notna()
                    ]
                )

                if not valid_rtd.empty:

                    rtd_terminal_price = (
                        valid_rtd[
                            "Forecast LMP"
                        ].iloc[-1]
                    )

                    rtd_average_price = (
                        valid_rtd[
                            "Forecast LMP"
                        ].mean()
                    )

            dam_average_price = np.nan

            if (
                not nodal_dam.empty
                and
                "DAM SPP"
                in nodal_dam.columns
            ):

                dam_average_price = (
                    nodal_dam[
                        "DAM SPP"
                    ].mean()
                )

            nm1, nm2, nm3, nm4, nm5, nm6 = st.columns(
                6
            )

            nm1.metric(
                "RT Nodal LMP",
                price_metric_value(
                    latest_node_lmp
                ),
            )

            nm2.metric(
                f"{nodal_benchmark_hub} RT",
                price_metric_value(
                    latest_hub_lmp
                ),
            )

            nm3.metric(
                "RT Nodal Basis",
                (
                    f"${latest_rt_basis:+,.2f}/MWh"
                    if pd.notna(
                        latest_rt_basis
                    )
                    else "N/A"
                ),
            )

            nm4.metric(
                "RTD End-of-Horizon",
                price_metric_value(
                    rtd_terminal_price
                ),
            )

            nm5.metric(
                "RTD Avg Forecast",
                price_metric_value(
                    rtd_average_price
                ),
            )

            nm6.metric(
                "DAM Avg",
                price_metric_value(
                    dam_average_price
                ),
            )

            if (
                not nodal_actual.empty
                and
                not hub_actual.empty
                and
                "Nodal Timestamp"
                in nodal_actual.columns
                and
                "Nodal Timestamp"
                in hub_actual.columns
            ):

                node_actual_chart = (
                    nodal_actual[
                        [
                            "Nodal Timestamp",
                            "Nodal LMP",
                        ]
                    ]
                    .dropna(
                        subset=[
                            "Nodal Timestamp"
                        ]
                    )
                    .rename(
                        columns={
                            "Nodal LMP":
                                selected_resource_node
                        }
                    )
                )

                hub_actual_chart = (
                    hub_actual[
                        [
                            "Nodal Timestamp",
                            "Nodal LMP",
                        ]
                    ]
                    .dropna(
                        subset=[
                            "Nodal Timestamp"
                        ]
                    )
                    .rename(
                        columns={
                            "Nodal LMP":
                                nodal_benchmark_hub
                        }
                    )
                )

                actual_chart = pd.merge_asof(
                    node_actual_chart.sort_values(
                        "Nodal Timestamp"
                    ),
                    hub_actual_chart.sort_values(
                        "Nodal Timestamp"
                    ),
                    on="Nodal Timestamp",
                    direction="nearest",
                    tolerance=
                        pd.Timedelta(
                            minutes=3
                        ),
                )

                actual_chart[
                    "Basis ($/MWh)"
                ] = (
                    actual_chart[
                        selected_resource_node
                    ]
                    -
                    actual_chart[
                        nodal_benchmark_hub
                    ]
                )

                chart_left, chart_right = st.columns(
                    2
                )

                with chart_left:

                    st.markdown(
                        "#### Recent SCED Nodal vs Hub LMP"
                    )

                    st.line_chart(
                        actual_chart.set_index(
                            "Nodal Timestamp"
                        )[
                            [
                                selected_resource_node,
                                nodal_benchmark_hub,
                            ]
                        ],
                        use_container_width=True,
                        height=320,
                    )

                with chart_right:

                    st.markdown(
                        "#### Recent Nodal Basis"
                    )

                    st.line_chart(
                        actual_chart.set_index(
                            "Nodal Timestamp"
                        )[
                            [
                                "Basis ($/MWh)"
                            ]
                        ],
                        use_container_width=True,
                        height=320,
                    )

            if (
                not nodal_rtd.empty
                and
                "Forecast Interval"
                in nodal_rtd.columns
                and
                "Forecast LMP"
                in nodal_rtd.columns
            ):

                rtd_chart = (
                    nodal_rtd[
                        [
                            "Forecast Interval",
                            "Forecast LMP",
                        ]
                    ]
                    .rename(
                        columns={
                            "Forecast LMP":
                                selected_resource_node
                        }
                    )
                )

                if (
                    not hub_rtd.empty
                    and
                    "Forecast Interval"
                    in hub_rtd.columns
                    and
                    "Forecast LMP"
                    in hub_rtd.columns
                ):

                    hub_rtd_chart = (
                        hub_rtd[
                            [
                                "Forecast Interval",
                                "Forecast LMP",
                            ]
                        ]
                        .rename(
                            columns={
                                "Forecast LMP":
                                    nodal_benchmark_hub
                            }
                        )
                    )

                    rtd_chart = rtd_chart.merge(
                        hub_rtd_chart,
                        on="Forecast Interval",
                        how="left",
                    )

                st.markdown(
                    "#### ERCOT Look-Ahead RTD Indicative Nodal Forecast"
                )

                st.line_chart(
                    rtd_chart.set_index(
                        "Forecast Interval"
                    ),
                    use_container_width=True,
                    height=320,
                )

            st.markdown(
                "#### Optional Long-Term Nodal Forward Curve"
            )

            nodal_forward_upload = st.file_uploader(
                "Optional nodal forward curve CSV",
                type=["csv"],
                key=
                    "orbit_nodal_forward_curve_upload",
            )

            if nodal_forward_upload is not None:

                try:

                    (
                        forward_curve,
                        forward_columns,
                    ) = (
                        _parse_forward_curve_upload(
                            nodal_forward_upload
                        )
                    )

                    if not forward_columns.get(
                        "price"
                    ):

                        st.warning(
                            "Forward curve CSV needs "
                            "a recognizable price column."
                        )

                    else:

                        forward_view = (
                            forward_curve.copy()
                        )

                        price_col = (
                            forward_columns[
                                "price"
                            ]
                        )

                        forward_view[
                            "Forecast Price ($/MWh)"
                        ] = pd.to_numeric(
                            forward_view[
                                price_col
                            ],
                            errors="coerce",
                        )

                        date_col = (
                            forward_columns.get(
                                "date"
                            )
                        )

                        year_col = (
                            forward_columns.get(
                                "year"
                            )
                        )

                        if date_col:

                            forward_view[
                                "Forecast Period"
                            ] = pd.to_datetime(
                                forward_view[
                                    date_col
                                ],
                                errors="coerce",
                            )

                        elif year_col:

                            forward_view[
                                "Forecast Period"
                            ] = pd.to_datetime(
                                forward_view[
                                    year_col
                                ]
                                .astype(
                                    str
                                )
                                + "-01-01",
                                errors="coerce",
                            )

                        else:

                            forward_view[
                                "Forecast Period"
                            ] = np.arange(
                                1,
                                len(
                                    forward_view
                                ) + 1,
                            )

                        st.line_chart(
                            forward_view.set_index(
                                "Forecast Period"
                            )[
                                [
                                    "Forecast Price ($/MWh)"
                                ]
                            ],
                            use_container_width=True,
                            height=340,
                        )

                except Exception as exc:

                    st.error(
                        "Unable to read the nodal "
                        "forward curve CSV. "
                        + clean_text(
                            exc
                        )
                    )


        # ----------------------------------------------------
        # COMPETITOR LIST
        # ----------------------------------------------------

        if competitor_view.empty:

            st.warning(
                "No competitors match the "
                "current tab filters."
            )

        else:

            st.divider()

            st.markdown(
                "### ERCOT South Competitor List"
            )

            competitor_list_columns = [
                "Filtered IX Cost Rank",
                "Filtered Queue Placement",
                "Queue Stage",
                "Power Project Name",
                "Owner",
                "Power Project Type",
                "Capacity (MW)",
                "MW Delta vs Orbit",
                "Power Project Status",
                "Detailed Status",
                "First Power Date",
                "County",
                "Queue ID",
                "Point of Interconnection",
                "ISO Zone",
                "Interconnection Service Type",
                "Queue Cycle",
                "Queue Date",
                "Interconnection Cost Physical ($)",
                "Interconnection Cost System Upgrade ($)",
                "Interconnection Cost Total ($)",
                "IX Cost Physical ($)",
                "IX Cost System Upgrade ($)",
                "IX Cost Total ($)",
                "IX Cost ($/kW)",
                "IX $/kW Delta vs Orbit",
                "IX % vs Orbit",
                "Contract Type",
                "Contract Offtaker",
                "Contract Execution Date",
                "Contract Termination Date",
                "Contract Term Years (Year)",
                "PTC/ITC",
                "Equipment Manufacturer",
                "Equipment Model",
                "EPC",
                "Integrator",
                "Latitude (Degrees)",
                "Longitude (Degrees)",
            ]

            competitor_list_columns = [
                column

                for column
                in competitor_list_columns

                if column
                in competitor_view.columns
            ]

            competitor_list = (
                competitor_view[
                    competitor_list_columns
                ]
                .copy()
            )

            competitor_list.insert(
                0,
                "Competitor Rank",
                np.arange(
                    1,
                    len(
                        competitor_list
                    ) + 1,
                ),
            )

            st.dataframe(
                competitor_list,
                use_container_width=True,
                hide_index=True,
            )

            competitor_csv = (
                competitor_list
                .to_csv(
                    index=False
                )
                .encode(
                    "utf-8"
                )
            )

            st.download_button(
                "⬇️ Download ERCOT South Orbit Competitor List",
                data=
                    competitor_csv,
                file_name=
                    "ERCOT_South_Orbit_Competitors_Filtered_MW.csv",
                mime=
                    "text/csv",
                key=
                    "download_orbit_competitor_list",
            )


# ============================================================
# MAP EXPLORER
# ============================================================

with map_tab:

    st.markdown(
        "## 🗺️ ERCOT Acquisition Map"
    )

    lat_col = (
        "Latitude (Degrees)"
        if
        "Latitude (Degrees)"
        in df.columns
        else None
    )

    lon_col = (
        "Longitude (Degrees)"
        if
        "Longitude (Degrees)"
        in df.columns
        else None
    )

    if (
        lat_col is None
        or
        lon_col is None
    ):

        st.error(
            "The active Power Projects CSV does not "
            "contain Latitude (Degrees) and "
            "Longitude (Degrees)."
        )

    else:

        map_base = df.copy()

        map_base[
            "Map Latitude"
        ] = pd.to_numeric(
            map_base[
                lat_col
            ],
            errors="coerce",
        )

        map_base[
            "Map Longitude"
        ] = pd.to_numeric(
            map_base[
                lon_col
            ],
            errors="coerce",
        )

        valid_coordinate_mask = (
            map_base[
                "Map Latitude"
            ].between(
                24.0,
                37.5,
                inclusive="both",
            )
            &
            map_base[
                "Map Longitude"
            ].between(
                -107.5,
                -92.0,
                inclusive="both",
            )
        )

        mapped_universe = (
            map_base[
                valid_coordinate_mask
            ]
            .copy()
        )

        if mapped_universe.empty:

            st.warning(
                "No projects have valid "
                "mapping coordinates."
            )

        else:

            technology_options = sorted(
                mapped_universe[
                    "Power Project Type"
                ]
                .dropna()
                .astype(
                    str
                )
                .unique()
                .tolist()
            )

            selected_technologies = (
                st.multiselect(
                    "Technology",
                    options=
                        technology_options,
                    default=
                        technology_options,
                    key=
                        "map_technology_filter",
                )
            )

            filtered_map = (
                mapped_universe.copy()
            )

            if selected_technologies:

                filtered_map = (
                    filtered_map[
                        filtered_map[
                            "Power Project Type"
                        ].isin(
                            selected_technologies
                        )
                    ]
                )

            if filtered_map.empty:

                st.warning(
                    "No mapped projects match "
                    "the current filters."
                )

            else:

                map_plot = (
                    filtered_map.copy()
                )

                map_plot[
                    "lat"
                ] = map_plot[
                    "Map Latitude"
                ].astype(
                    float
                )

                map_plot[
                    "lon"
                ] = map_plot[
                    "Map Longitude"
                ].astype(
                    float
                )

                map_plot[
                    "Map Radius"
                ] = (
                    pd.to_numeric(
                        map_plot[
                            "Capacity (MW)"
                        ],
                        errors="coerce",
                    )
                    .fillna(
                        50
                    )
                    .clip(
                        lower=20,
                        upper=500,
                    )
                    * 125
                )

                map_plot[
                    "Project"
                ] = (
                    map_plot[
                        "Power Project Name"
                    ]
                    .fillna(
                        ""
                    )
                    .astype(
                        str
                    )
                )

                map_plot[
                    "Owner Display"
                ] = (
                    map_plot[
                        "Owner"
                    ]
                    .replace(
                        "",
                        np.nan,
                    )
                    .fillna(
                        "N/A"
                    )
                )

                map_plot[
                    "Capacity Display"
                ] = (
                    map_plot[
                        "Capacity (MW)"
                    ]
                    .apply(
                        lambda value:
                            f"{value:,.1f} MW"
                            if pd.notna(
                                value
                            )
                            else "N/A"
                    )
                )

                technology_colors = {
                    "Solar": [
                        245,
                        166,
                        35,
                        220,
                    ],

                    "Storage": [
                        38,
                        132,
                        255,
                        220,
                    ],

                    "Wind": [
                        47,
                        158,
                        68,
                        220,
                    ],
                }

                layers = []

                for (
                    technology_name,
                    technology_color,
                ) in technology_colors.items():

                    technology_map = (
                        map_plot[
                            map_plot[
                                "Power Project Type"
                            ]
                            == technology_name
                        ]
                        .copy()
                    )

                    if technology_map.empty:

                        continue

                    layers.append(
                        pdk.Layer(
                            "ScatterplotLayer",
                            data=
                                technology_map,
                            id=
                                f"{technology_name.lower()}_projects",
                            get_position=
                                "[lon, lat]",
                            get_radius=
                                "Map Radius",
                            get_fill_color=
                                technology_color,
                            get_line_color=[
                                255,
                                255,
                                255,
                                230,
                            ],
                            radius_min_pixels=6,
                            radius_max_pixels=18,
                            line_width_min_pixels=1,
                            pickable=True,
                            auto_highlight=True,
                            stroked=True,
                            filled=True,
                        )
                    )

                map_latitude = float(
                    map_plot[
                        "Map Latitude"
                    ].mean()
                )

                map_longitude = float(
                    map_plot[
                        "Map Longitude"
                    ].mean()
                )

                deck = pdk.Deck(
                    map_style=
                        "https://basemaps.cartocdn.com/"
                        "gl/positron-gl-style/style.json",

                    initial_view_state=
                        pdk.ViewState(
                            latitude=
                                map_latitude,
                            longitude=
                                map_longitude,
                            zoom=5.0,
                            pitch=0,
                        ),

                    layers=
                        layers,

                    tooltip={
                        "html":
                            "<b>{Project}</b><br/>"
                            "Owner: {Owner Display}<br/>"
                            "Capacity: {Capacity Display}",

                        "style": {
                            "backgroundColor":
                                "rgba(20,20,20,0.92)",

                            "color":
                                "white",
                        },
                    },
                )

                st.pydeck_chart(
                    deck,
                    use_container_width=True,
                    height=700,
                )


# ============================================================
# ACQUISITION PROJECT MARKET BENCHMARK
# ============================================================

with price_tab:

    st.divider()

    st.markdown(
        "## 🎯 Acquisition Project Market Benchmark"
    )

    st.caption(
        "Select an acquisition target to compare "
        "it with the latest broad ERCOT hub price "
        "for its area."
    )

    if market_rt_df.empty:

        st.info(
            "Live Real-Time SPP is unavailable, "
            "so project market benchmarking cannot "
            "be shown right now."
        )

    elif df.empty:

        st.info(
            "No acquisition projects are available "
            "for benchmarking."
        )

    else:

        project_market_options = (
            df.apply(
                lambda row:
                    f"{clean_text(row.get('Power Project Name'))} — "
                    f"{clean_text(row.get('Owner')) or 'Unknown Owner'} — "
                    f"{clean_text(row.get('ERCOT Area')) or 'Unknown Area'}",
                axis=1,
            )
            .tolist()
        )

        selected_project_market_label = (
            st.selectbox(
                "Project",
                options=
                    project_market_options,
                key=
                    "market_project_benchmark_selector",
            )
        )

        selected_project_market_index = (
            project_market_options.index(
                selected_project_market_label
            )
        )

        market_project = (
            df.iloc[
                selected_project_market_index
            ]
        )

        area_to_hub = {
            "ERCOT-N":
                "HB_NORTH",

            "ERCOT-H":
                "HB_HOUSTON",

            "ERCOT-S":
                "HB_SOUTH",

            "ERCOT-W":
                "HB_WEST",

            "Panhandle":
                "HB_PAN",
        }

        project_area = clean_text(
            market_project.get(
                "ERCOT Area"
            )
        )

        benchmark_hub = (
            area_to_hub.get(
                project_area
            )
        )

        if (
            benchmark_hub is None
            or
            benchmark_hub
            not in market_rt_df.columns
        ):

            st.warning(
                f"No broad hub benchmark is "
                f"configured for "
                f"{project_area or 'this project area'}."
            )

        else:

            latest_market_day = (
                market_rt_df[
                    "Oper Day"
                ].max()
            )

            project_rt = (
                market_rt_df[
                    market_rt_df[
                        "Oper Day"
                    ]
                    == latest_market_day
                ]
                .copy()
            )

            latest_benchmark = (
                project_rt[
                    benchmark_hub
                ]
                .dropna()
            )

            latest_benchmark_price = (
                latest_benchmark.iloc[-1]
                if not latest_benchmark.empty
                else np.nan
            )

            benchmark_average = (
                project_rt[
                    benchmark_hub
                ].mean()
            )

            benchmark_high = (
                project_rt[
                    benchmark_hub
                ].max()
            )

            benchmark_low = (
                project_rt[
                    benchmark_hub
                ].min()
            )

            benchmark_dam_average = np.nan

            if (
                not market_dam_df.empty
                and
                benchmark_hub
                in market_dam_df.columns
            ):

                latest_project_dam_day = (
                    market_dam_df[
                        "Oper Day"
                    ].max()
                )

                benchmark_dam_average = (
                    market_dam_df[
                        market_dam_df[
                            "Oper Day"
                        ]
                        == latest_project_dam_day
                    ][
                        benchmark_hub
                    ]
                    .mean()
                )

            b1, b2, b3, b4, b5, b6 = st.columns(
                6
            )

            b1.metric(
                "Project",
                clean_text(
                    market_project.get(
                        "Power Project Name"
                    )
                )
                or "N/A",
            )

            b2.metric(
                "ERCOT Area",
                project_area
                or "N/A",
            )

            b3.metric(
                "Benchmark Hub",
                benchmark_hub,
            )

            b4.metric(
                "Latest RT",
                price_metric_value(
                    latest_benchmark_price
                ),
            )

            b5.metric(
                "RT Day Avg",
                price_metric_value(
                    benchmark_average
                ),
            )

            b6.metric(
                "DAM Day Avg",
                price_metric_value(
                    benchmark_dam_average
                ),
            )

            st.caption(
                f"Today at {benchmark_hub}: "
                f"high "
                f"**{price_metric_value(benchmark_high)}**, "
                f"low "
                f"**{price_metric_value(benchmark_low)}**."
            )

            project_market_chart = (
                project_rt[
                    [
                        "Timestamp",
                        benchmark_hub,
                    ]
                ]
                .rename(
                    columns={
                        benchmark_hub:
                            f"{benchmark_hub} RT SPP",
                    }
                )
            )

            st.line_chart(
                project_market_chart.set_index(
                    "Timestamp"
                ),
                use_container_width=True,
                height=320,
            )
