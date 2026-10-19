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

st.set_page_config(
    page_title='ERCOT Acquisition Dashboard',
    page_icon='⚡',
    layout='wide'
)

st.title('⚡ ERCOT Acquisition Dashboard')
st.caption(
    'M&A screening tool for ERCOT solar, battery storage, '
    'and operating wind projects'
)

SELLER_REFRESH_SECONDS = 6 * 60 * 60
SELLER_LOOKBACK_DAYS = 180


def clean_text(value):
    if pd.isna(value):
        return ''
    return str(value).strip()


def has_value(value):
    return clean_text(value) != ''


def owner_key(value):
    return clean_text(value).lower()


def format_date(value):
    if pd.isna(value):
        return 'N/A'

    try:
        return pd.to_datetime(value).strftime('%m/%d/%Y')
    except Exception:
        return clean_text(value)


def strip_html(value):
    if value is None:
        return ''

    text = re.sub(
        '<[^>]+>',
        ' ',
        str(value)
    )

    text = html_lib.unescape(text)

    return re.sub(
        '\\s+',
        ' ',
        text
    ).strip()


def map_ercot_area(value):
    zone = clean_text(value)

    mapping = {
        'Load Zone - North': 'ERCOT-N',
        'North Hub': 'ERCOT-N',

        'Load Zone - South': 'ERCOT-S',
        'South Hub': 'ERCOT-S',

        'Load Zone - West': 'ERCOT-W',
        'West Hub': 'ERCOT-W',

        'Load Zone - Houston': 'ERCOT-H',
        'Houston Hub': 'ERCOT-H',

        'Panhandle Hub': 'Panhandle'
    }

    return mapping.get(
        zone,
        zone if zone else 'Unknown'
    )


def to_numeric_series(series):
    return pd.to_numeric(
        series,
        errors='coerce'
    )


st.sidebar.header('1. Data')

uploaded_file = st.sidebar.file_uploader(
    'Optional: Upload newer Orennia CSV',
    type=['csv']
)

st.sidebar.caption(
    'Not required to view the Dashboard Guide.'
)

st.sidebar.divider()

st.sidebar.header(
    '2. Opportunity Score Weights'
)

distress_weight = st.sidebar.number_input(
    'Seller Motivation',
    min_value=0.0,
    max_value=1.0,
    value=0.35,
    step=0.05,
    key='distress_weight'
)

development_weight = st.sidebar.number_input(
    'Development Stage',
    min_value=0.0,
    max_value=1.0,
    value=0.25,
    step=0.05,
    key='development_weight'
)

market_weight = st.sidebar.number_input(
    'Market / Revenue',
    min_value=0.0,
    max_value=1.0,
    value=0.15,
    step=0.05,
    key='market_weight'
)

value_weight = st.sidebar.number_input(
    'Acquisition Value',
    min_value=0.0,
    max_value=1.0,
    value=0.10,
    step=0.05,
    key='value_weight'
)

exec_weight = st.sidebar.number_input(
    'Executability',
    min_value=0.0,
    max_value=1.0,
    value=0.15,
    step=0.05,
    key='exec_weight'
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
        f'Weights currently total '
        f'{total_weight:.0%}. '
        'They should total 100%.'
    )

else:

    st.sidebar.success(
        'Overall Weights = 100%'
    )


st.sidebar.divider()

st.sidebar.header(
    '3. Scoring Inputs'
)


with st.sidebar.expander(
    'Seller Motivation Points'
):

    distress_5 = st.number_input(
        'Discount Potential 5',
        value=100,
        key='distress_5'
    )

    distress_4 = st.number_input(
        'Discount Potential 4',
        value=80,
        key='distress_4'
    )

    distress_3 = st.number_input(
        'Discount Potential 3',
        value=60,
        key='distress_3'
    )

    distress_2 = st.number_input(
        'Discount Potential 2',
        value=40,
        key='distress_2'
    )

    distress_1 = st.number_input(
        'Discount Potential 1',
        value=20,
        key='distress_1'
    )

    distress_none = st.number_input(
        'No Seller Signal',
        value=0,
        key='distress_none'
    )

    confidence_high = st.number_input(
        'High Confidence Multiplier',
        value=1.00,
        step=0.05,
        key='confidence_high'
    )

    confidence_medium = st.number_input(
        'Medium Confidence Multiplier',
        value=0.90,
        step=0.05,
        key='confidence_medium'
    )

    confidence_low = st.number_input(
        'Low Confidence Multiplier',
        value=0.75,
        step=0.05,
        key='confidence_low'
    )


with st.sidebar.expander(
    'Development Stage Points'
):

    development_operating = st.number_input(
        'Operating',
        value=100,
        key='development_operating'
    )

    development_50 = st.number_input(
        '>50% Construction',
        value=92,
        key='development_50'
    )

    development_construction = st.number_input(
        'In Construction',
        value=85,
        key='development_construction'
    )

    development_ia = st.number_input(
        'IA Executed',
        value=75,
        key='development_ia'
    )

    development_fis_complete = st.number_input(
        'FIS Completed',
        value=65,
        key='development_fis_complete'
    )

    development_fis_started = st.number_input(
        'FIS Started',
        value=55,
        key='development_fis_started'
    )

    development_studies = st.number_input(
        'Studies Undergoing',
        value=45,
        key='development_studies'
    )

    development_pre = st.number_input(
        'Pre-Study',
        value=35,
        key='development_pre'
    )

    development_inactive = st.number_input(
        'Inactive / Suspended / Retired',
        value=15,
        key='development_inactive'
    )


with st.sidebar.expander(
    'Revenue Visibility Points'
):

    market_both = st.number_input(
        'Contract + Named Offtaker',
        value=95,
        key='market_both'
    )

    market_offtaker = st.number_input(
        'Named Offtaker Only',
        value=90,
        key='market_offtaker'
    )

    market_contract = st.number_input(
        'Contract Only',
        value=80,
        key='market_contract'
    )

    market_none = st.number_input(
        'Neither Contract nor Offtaker',
        value=45,
        key='market_none'
    )


with st.sidebar.expander(
    'ERCOT Location Points'
):

    location_north = st.number_input(
        'ERCOT-N',
        value=90,
        key='location_north'
    )

    location_houston = st.number_input(
        'ERCOT-H',
        value=85,
        key='location_houston'
    )

    location_south = st.number_input(
        'ERCOT-S',
        value=70,
        key='location_south'
    )

    location_west = st.number_input(
        'ERCOT-W',
        value=60,
        key='location_west'
    )

    location_panhandle = st.number_input(
        'Panhandle',
        value=50,
        key='location_panhandle'
    )

    location_unknown = st.number_input(
        'Unknown / Other',
        value=50,
        key='location_unknown'
    )


with st.sidebar.expander(
    'Market / Revenue Mix'
):

    revenue_visibility_weight = st.number_input(
        'Revenue Visibility %',
        min_value=0.0,
        max_value=1.0,
        value=0.70,
        step=0.05,
        key='revenue_visibility_weight'
    )

    location_market_weight = st.number_input(
        'ERCOT Location %',
        min_value=0.0,
        max_value=1.0,
        value=0.30,
        step=0.05,
        key='location_market_weight'
    )


market_mix_total = (
    revenue_visibility_weight
    + location_market_weight
)

if abs(
    market_mix_total - 1.0
) > 0.001:

    st.sidebar.warning(
        f'Market / Revenue mix totals '
        f'{market_mix_total:.0%}. '
        'It should equal 100%.'
    )


with st.sidebar.expander(
    'Acquisition Value Points'
):

    value_both = st.number_input(
        'Tax Credit + Energy Community',
        value=75,
        key='value_both'
    )

    value_tax = st.number_input(
        'Tax Credit Only',
        value=70,
        key='value_tax'
    )

    value_ec = st.number_input(
        'Energy Community Only',
        value=60,
        key='value_ec'
    )

    value_none = st.number_input(
        'Neither Tax Credit nor Energy Community',
        value=55,
        key='value_none'
    )


with st.sidebar.expander(
    'Timing Points'
):

    timing_operating = st.number_input(
        'COD Reached / Passed',
        value=100,
        key='timing_operating'
    )

    timing_1 = st.number_input(
        'COD Within 1 Year',
        value=90,
        key='timing_1'
    )

    timing_2 = st.number_input(
        'COD Within 2 Years',
        value=75,
        key='timing_2'
    )

    timing_3 = st.number_input(
        'COD Within 3 Years',
        value=60,
        key='timing_3'
    )

    timing_long = st.number_input(
        'COD >3 Years',
        value=45,
        key='timing_long'
    )

    timing_missing = st.number_input(
        'COD Missing',
        value=50,
        key='timing_missing'
    )


with st.sidebar.expander(
    'Executability Mix'
):

    actionability_weight = st.number_input(
        'Seller Actionability %',
        min_value=0.0,
        max_value=1.0,
        value=0.50,
        step=0.05,
        key='actionability_weight'
    )

    timing_exec_weight = st.number_input(
        'Timing %',
        min_value=0.0,
        max_value=1.0,
        value=0.30,
        step=0.05,
        key='timing_exec_weight'
    )

    development_exec_weight = st.number_input(
        'Development Stage %',
        min_value=0.0,
        max_value=1.0,
        value=0.20,
        step=0.05,
        key='development_exec_weight'
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
        f'Executability mix totals '
        f'{exec_mix_total:.0%}. '
        'It should equal 100%.'
    )


discount_score_map = {
    5: distress_5,
    4: distress_4,
    3: distress_3,
    2: distress_2,
    1: distress_1
}

confidence_score_map = {
    'High': confidence_high,
    'Medium': confidence_medium,
    'Low': confidence_low
}

actionability_points = {
    5: 100,
    4: 80,
    3: 60,
    2: 40,
    1: 20
}

location_points = {
    'ERCOT-N': location_north,
    'ERCOT-H': location_houston,
    'ERCOT-S': location_south,
    'ERCOT-W': location_west,
    'Panhandle': location_panhandle,
    'Unknown': location_unknown
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


seller_signals = pd.DataFrame(
    [
        [
            'Birch Creek Energy',
            5,
            5,
            'Medium'
        ],

        [
            'Birch Creek Development',
            5,
            5,
            'Medium'
        ],

        [
            'esVolta',
            4,
            5,
            'High'
        ],

        [
            'Key Capture Energy',
            4,
            5,
            'High'
        ],

        [
            'Lightsource BP',
            3,
            4,
            'High'
        ],

        [
            'Ørsted U.S. Onshore',
            3,
            4,
            'Medium'
        ],

        [
            'Orsted',
            3,
            4,
            'Medium'
        ],

        [
            'Flatiron Energy',
            2,
            4,
            'High'
        ],

        [
            'Recurrent Energy',
            2,
            2,
            'Medium'
        ],

        [
            'EDF power solutions North America',
            1,
            1,
            'High'
        ],

        [
            'EDF Renewables',
            1,
            1,
            'High'
        ],

        [
            'Greenbacker Renewable Energy Company',
            1,
            1,
            'High'
        ]
    ],
    columns=[
        'Owner',
        'Discount Potential',
        'Seller Actionability',
        'Confidence'
    ]
)


if 'seller_assumptions' not in st.session_state:

    st.session_state[
        'seller_assumptions'
    ] = seller_signals.copy()


(
    dashboard_tab,
    map_tab,
    competitor_tab,
    price_tab
) = st.tabs(
    [
        '📊 Acquisition Dashboard',
        '🗺️ Map Explorer',
        '🎯 ERCOT Competitor Due Diligence',
        '📈 ERCOT Market Prices'
    ]
)


ERCOT_RT_SPP_URL = (
    'https://www.ercot.com/content/cdr/html/'
    'real_time_spp.html'
)

ERCOT_LATEST_LMP_URL = (
    'https://www.ercot.com/content/cdr/html/'
    'hb_lz.html'
)

ERCOT_DAM_SPP_URL = (
    'https://www.ercot.com/content/cdr/html/'
    'dam_spp.html'
)

ERCOT_DAM_MCPC_URL = (
    'https://www.ercot.com/content/cdr/html/'
    'dam_mcpc.html'
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
        html_text
    ):

        from html.parser import HTMLParser

        parent = self

        class _Parser(
            HTMLParser
        ):

            def handle_starttag(
                self,
                tag,
                attrs
            ):

                tag = tag.lower()

                if tag == 'table':
                    parent.current_table = []

                elif (
                    tag == 'tr'
                    and parent.current_table
                    is not None
                ):
                    parent.current_row = []

                elif (
                    tag in [
                        'td',
                        'th'
                    ]
                    and parent.current_row
                    is not None
                ):
                    parent.current_cell = []
                    parent.in_cell = True

                elif (
                    tag == 'br'
                    and parent.in_cell
                ):
                    parent.current_cell.append(
                        ' '
                    )

            def handle_data(
                self,
                data
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
                tag
            ):

                tag = tag.lower()

                if (
                    tag in [
                        'td',
                        'th'
                    ]
                    and parent.in_cell
                ):

                    value = re.sub(
                        '\\s+',
                        ' ',
                        ''.join(
                            parent.current_cell
                        )
                    ).strip()

                    parent.current_row.append(
                        value
                    )

                    parent.current_cell = None
                    parent.in_cell = False

                elif (
                    tag == 'tr'
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
                    tag == 'table'
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
    required_columns
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
                    '\\s+',
                    ' ',
                    clean_text(
                        value
                    )
                ).strip()
                for value in row
            ]

            if not all(
                required in header
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
                        '\\s+',
                        ' ',
                        clean_text(
                            value
                        )
                    ).strip()
                    for value
                    in data_row
                ]

                if len(
                    values
                ) < width:

                    values = (
                        values
                        + ['']
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
                    columns=header
                )

    raise ValueError(
        'ERCOT price table was not found '
        'in the returned HTML.'
    )


def normalize_ercot_price_table(
    frame,
    time_column
):

    result = frame.copy()

    if 'Oper Day' not in result.columns:

        raise ValueError(
            'ERCOT table is missing Oper Day.'
        )

    if time_column not in result.columns:

        raise ValueError(
            f'ERCOT table is missing '
            f'{time_column}.'
        )

    result[
        'Oper Day'
    ] = pd.to_datetime(
        result[
            'Oper Day'
        ],
        errors='coerce'
    )

    for column in result.columns:

        if column in [
            'Oper Day',
            time_column
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
                ',',
                '',
                regex=False
            )
            .str.replace(
                '$',
                '',
                regex=False
            )
            .str.strip()
        )

        result[
            column
        ] = pd.to_numeric(
            cleaned,
            errors='coerce'
        )

    result = result[
        result[
            'Oper Day'
        ].notna()
    ].copy()

    return result


def _download_ercot_html(
    url
):

    request = urllib.request.Request(
        url,
        headers={
            'User-Agent':
                'Mozilla/5.0 '
                'ERCOT-Acquisition-Dashboard/1.0',

            'Accept':
                'text/html,application/xhtml+xml'
        }
    )

    with urllib.request.urlopen(
        request,
        timeout=15
    ) as response:

        return response.read().decode(
            'utf-8',
            errors='replace'
        )


def _fetch_first_ercot_table(
    candidate_urls,
    time_column,
    required_columns
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
                        required_columns
                )
            )

            table = (
                normalize_ercot_price_table(
                    table,
                    time_column=
                        time_column
                )
            )

            if not table.empty:

                return (
                    table,
                    url
                )

        except Exception as exc:

            last_error = exc

    if last_error is not None:

        raise last_error

    raise ValueError(
        'No ERCOT market-price table '
        'was available.'
    )


def _ercot_operating_day_urls(
    report_name,
    include_generic=True
):

    now_central = (
        pd.Timestamp.now(
            tz='America/Chicago'
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
            'https://www.ercot.com/'
            'content/cdr/html/'
            f"{day.strftime('%Y%m%d')}_"
            f'{report_name}.html'
        )
        for day in [
            today,
            yesterday
        ]
    ]

    if include_generic:

        generic = (
            'https://www.ercot.com/'
            'content/cdr/html/'
            f'{report_name}.html'
        )

        return [
            generic,
            *dated_urls
        ]

    return dated_urls


def _parse_ercot_numeric_value(
    value
):

    cleaned = (
        clean_text(
            value
        )
        .replace(
            ',',
            ''
        )
        .replace(
            '$',
            ''
        )
        .strip()
    )

    if cleaned == '':

        return np.nan

    return pd.to_numeric(
        cleaned,
        errors='coerce'
    )


def parse_ercot_latest_lmp_table(
    html_text
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
                    '\\s+',
                    ' ',
                    clean_text(
                        value
                    )
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
                '(?:HB|LZ)_[A-Z0-9_]+',
                settlement_point
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
                    'Settlement Point':
                        settlement_point,

                    'LMP':
                        numeric_values[0],

                    '5 Min Change to LMP':
                        (
                            numeric_values[1]
                            if len(
                                numeric_values
                            ) > 1
                            else np.nan
                        ),

                    'RTRDPA + LMP':
                        (
                            numeric_values[2]
                            if len(
                                numeric_values
                            ) > 2
                            else np.nan
                        ),

                    '5 Min Change to RTRDPA + LMP':
                        (
                            numeric_values[3]
                            if len(
                                numeric_values
                            ) > 3
                            else np.nan
                        )
                }
            )

    if not rows:

        visible_text = (
            html_lib.unescape(
                re.sub(
                    '<[^>]+>',
                    ' | ',
                    html_text
                )
            )
        )

        visible_text = re.sub(
            '\\s+',
            ' ',
            visible_text
        )

        point_matches = list(
            re.finditer(
                '\\b(?:HB|LZ)_[A-Z0-9_]+\\b',
                visible_text,
                flags=re.IGNORECASE
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
                    + 500
                )
            )

            segment = visible_text[
                match.end():
                segment_end
            ]

            number_matches = (
                re.findall(
                    '(?<![A-Za-z0-9_])'
                    '[-+]?\\$?'
                    '\\d{1,6}'
                    '(?:,\\d{3})*'
                    '(?:\\.\\d+)?',
                    segment
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
                    'Settlement Point':
                        settlement_point,

                    'LMP':
                        numeric_values[0],

                    '5 Min Change to LMP':
                        (
                            numeric_values[1]
                            if len(
                                numeric_values
                            ) > 1
                            else np.nan
                        ),

                    'RTRDPA + LMP':
                        (
                            numeric_values[2]
                            if len(
                                numeric_values
                            ) > 2
                            else np.nan
                        ),

                    '5 Min Change to RTRDPA + LMP':
                        (
                            numeric_values[3]
                            if len(
                                numeric_values
                            ) > 3
                            else np.nan
                        )
                }
            )

    if not rows:

        raise ValueError(
            'ERCOT SCED LMP rows were '
            'not found in the returned HTML.'
        )

    table = pd.DataFrame(
        rows
    )

    table = (
        table
        .drop_duplicates(
            subset=[
                'Settlement Point'
            ],
            keep='first'
        )
        .sort_values(
            'Settlement Point'
        )
        .reset_index(
            drop=True
        )
    )

    return table


def extract_ercot_lmp_last_updated(
    html_text
):

    visible_text = strip_html(
        html_text
    )

    match = re.search(
        (
            'Last Updated:\\s*'
            '([A-Za-z]{3}\\s+'
            '\\d{1,2},\\s+'
            '\\d{4}\\s+'
            '\\d{1,2}:\\d{2}:\\d{2})'
        ),
        visible_text,
        flags=re.IGNORECASE
    )

    if match is None:

        return pd.NaT

    return pd.to_datetime(
        match.group(
            1
        ),
        errors='coerce'
    )


@st.cache_data(
    ttl=300,
    show_spinner=False
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
        'ERCOT Last Updated'
    ] = (
        extract_ercot_lmp_last_updated(
            html_text
        )
    )

    return (
        table,
        ERCOT_LATEST_LMP_URL
    )


@st.cache_data(
    ttl=300,
    show_spinner=False
)
def fetch_ercot_rt_spp():

    urls = (
        _ercot_operating_day_urls(
            'real_time_spp',
            include_generic=True
        )
    )

    return _fetch_first_ercot_table(
        candidate_urls=urls,
        time_column='Interval Ending',
        required_columns=[
            'Oper Day',
            'Interval Ending',
            'HB_NORTH'
        ]
    )


@st.cache_data(
    ttl=3600,
    show_spinner=False
)
def fetch_ercot_dam_spp():

    urls = (
        _ercot_operating_day_urls(
            'dam_spp',
            include_generic=True
        )
    )

    return _fetch_first_ercot_table(
        candidate_urls=urls,
        time_column='Hour Ending',
        required_columns=[
            'Oper Day',
            'Hour Ending',
            'HB_NORTH'
        ]
    )


@st.cache_data(
    ttl=3600,
    show_spinner=False
)
def fetch_ercot_dam_mcpc():

    dated_urls = (
        _ercot_operating_day_urls(
            'dam_mcpc',
            include_generic=False
        )
    )

    urls = [
        *dated_urls,
        ERCOT_DAM_MCPC_URL
    ]

    return _fetch_first_ercot_table(
        candidate_urls=urls,
        time_column='Hour Ending',
        required_columns=[
            'Oper Day',
            'Hour Ending',
            'NON-SPIN',
            'ECRS'
        ]
    )


def ercot_interval_timestamp(
    operating_day,
    interval_ending
):

    day = pd.to_datetime(
        operating_day,
        errors='coerce'
    )

    if pd.isna(
        day
    ):
        return pd.NaT

    digits = re.sub(
        '\\D',
        '',
        clean_text(
            interval_ending
        )
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
    hour_ending
):

    day = pd.to_datetime(
        operating_day,
        errors='coerce'
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
    interval_ending
):

    digits = re.sub(
        '\\D',
        '',
        clean_text(
            interval_ending
        )
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
        1
    )


def market_price_signal(
    latest_price,
    daily_average
):

    if pd.isna(
        latest_price
    ):

        return 'N/A'

    if latest_price < 0:

        return 'Negative'

    if pd.isna(
        daily_average
    ):

        return 'Current'

    difference = (
        latest_price
        - daily_average
    )

    if difference >= 30:

        return 'Elevated'

    if difference <= -20:

        return 'Soft'

    return 'Normal'


def price_metric_value(
    value
):

    if pd.isna(
        value
    ):

        return 'N/A'

    return (
        f'${value:,.2f}/MWh'
    )


market_lmp_df = pd.DataFrame()
market_rt_df = pd.DataFrame()
market_dam_df = pd.DataFrame()
market_mcpc_df = pd.DataFrame()

market_lmp_source = ''
market_rt_source = ''
market_dam_source = ''
market_mcpc_source = ''


with price_tab:

    st.markdown(
        '## 📈 ERCOT Market Prices'
    )

    st.caption(
        'Live market screen sourced directly '
        'from ERCOT public Current Day Reports. '
        'Real-Time SPP refreshes on a five-minute '
        'cache; Day-Ahead energy and ancillary-'
        'service prices refresh hourly. Market '
        'data is informational and does not '
        'change the acquisition Opportunity Score.'
    )

    (
        refresh_col,
        source_col
    ) = st.columns(
        [
            1,
            4
        ]
    )

    with refresh_col:

        refresh_market_prices = (
            st.button(
                '🔄 Refresh ERCOT Prices',
                key=
                    'refresh_ercot_market_prices'
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
            'Latest SCED LMP excludes Real-Time '
            'price adders; RT SPP includes ERCOT '
            'Real-Time Reliability Deployment '
            'Price Adders. Project-area comparisons '
            'use broad hub benchmarks and are not '
            'node-level project prices.'
        )

    lmp_error = ''
    rt_error = ''
    dam_error = ''
    mcpc_error = ''

    try:

        (
            market_lmp_df,
            market_lmp_source
        ) = fetch_ercot_latest_lmp()

    except Exception as exc:

        lmp_error = clean_text(
            exc
        )

    try:

        (
            market_rt_df,
            market_rt_source
        ) = fetch_ercot_rt_spp()

        market_rt_df[
            'Timestamp'
        ] = market_rt_df.apply(
            lambda row:
                ercot_interval_timestamp(
                    row[
                        'Oper Day'
                    ],
                    row[
                        'Interval Ending'
                    ]
                ),
            axis=1
        )

        market_rt_df = (
            market_rt_df[
                market_rt_df[
                    'Timestamp'
                ].notna()
            ]
            .sort_values(
                'Timestamp'
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
            market_dam_source
        ) = fetch_ercot_dam_spp()

        market_dam_df[
            'Timestamp'
        ] = market_dam_df.apply(
            lambda row:
                ercot_hour_timestamp(
                    row[
                        'Oper Day'
                    ],
                    row[
                        'Hour Ending'
                    ]
                ),
            axis=1
        )

        market_dam_df[
            'Hour Ending Numeric'
        ] = pd.to_numeric(
            market_dam_df[
                'Hour Ending'
            ],
            errors='coerce'
        )

        market_dam_df = (
            market_dam_df[
                market_dam_df[
                    'Timestamp'
                ].notna()
            ]
            .sort_values(
                'Timestamp'
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
            market_mcpc_source
        ) = fetch_ercot_dam_mcpc()

        market_mcpc_df[
            'Timestamp'
        ] = market_mcpc_df.apply(
            lambda row:
                ercot_hour_timestamp(
                    row[
                        'Oper Day'
                    ],
                    row[
                        'Hour Ending'
                    ]
                ),
            axis=1
        )

        market_mcpc_df = (
            market_mcpc_df[
                market_mcpc_df[
                    'Timestamp'
                ].notna()
            ]
            .sort_values(
                'Timestamp'
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
            'ERCOT Real-Time SPP could '
            'not be loaded. '
            + (
                rt_error
                or
                'The public report returned '
                'no usable rows.'
            )
        )

    else:

        latest_rt_row = (
            market_rt_df
            .iloc[-1]
        )

        latest_rt_timestamp = (
            latest_rt_row[
                'Timestamp'
            ]
        )

        current_operating_day = (
            latest_rt_row[
                'Oper Day'
            ]
        )

        st.success(
            'ERCOT Real-Time SPP feed connected. '
            'Latest settlement interval: '
            f"{latest_rt_timestamp.strftime('%m/%d/%Y %H:%M')} "
            'CT.'
        )

        major_hubs = [
            'HB_NORTH',
            'HB_HOUSTON',
            'HB_SOUTH',
            'HB_WEST',
            'HB_PAN'
        ]

        major_hubs = [
            hub
            for hub in major_hubs
            if hub
            in market_rt_df.columns
        ]

        market_points = [
            column
            for column
            in market_rt_df.columns
            if (
                column.startswith(
                    'HB_'
                )
                or column.startswith(
                    'LZ_'
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

        (
            point_col,
            view_col
        ) = st.columns(
            [
                1.5,
                1
            ]
        )

        with point_col:

            default_point_index = (
                market_points.index(
                    'HB_NORTH'
                )
                if 'HB_NORTH'
                in market_points
                else 0
            )

            selected_market_point = (
                st.selectbox(
                    'Hub / Load Zone',
                    options=
                        market_points,
                    index=
                        default_point_index,
                    key=
                        'ercot_market_point'
                )
            )

        with view_col:

            chart_window = (
                st.selectbox(
                    'Chart View',
                    options=[
                        'Today',
                        'Last 24 Hours Available'
                    ],
                    index=0,
                    key=
                        'ercot_market_chart_window'
                )
            )

        selected_rt = (
            market_rt_df[
                [
                    'Timestamp',
                    'Oper Day',
                    'Interval Ending',
                    selected_market_point
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

        if chart_window == 'Today':

            selected_rt = (
                selected_rt[
                    selected_rt[
                        'Oper Day'
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
                'Interval Ending'
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
                    'Oper Day'
                ].max()
            )

            selected_dam = (
                market_dam_df[
                    market_dam_df[
                        'Oper Day'
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
                        'Hour Ending Numeric'
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
                and pd.notna(
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
                        'Settlement Point'
                    ]
                    == selected_market_point
                ]
            )

            if not lmp_match.empty:

                latest_sced_lmp = (
                    lmp_match[
                        'LMP'
                    ]
                    .iloc[-1]
                )

        (
            p1,
            p2,
            p3,
            p4,
            p5,
            p6
        ) = st.columns(
            6
        )

        p1.metric(
            'Latest SCED LMP',
            price_metric_value(
                latest_sced_lmp
            )
        )

        p2.metric(
            'Latest RT SPP',
            price_metric_value(
                latest_point_price
            )
        )

        p3.metric(
            'RT Day Avg',
            price_metric_value(
                rt_day_average
            )
        )

        p4.metric(
            (
                'DAM HE '
                + (
                    str(
                        int(
                            latest_hour_ending
                        )
                    )
                    if pd.notna(
                        latest_hour_ending
                    )
                    else 'N/A'
                )
            ),
            price_metric_value(
                dam_hour_price
            )
        )

        p5.metric(
            'RT - DAM',
            (
                f'${rt_minus_dam:+,.2f}/MWh'
                if pd.notna(
                    rt_minus_dam
                )
                else 'N/A'
            )
        )

        p6.metric(
            'RT Day Range',
            (
                f'${rt_day_low:,.2f} – '
                f'${rt_day_high:,.2f}'
                if (
                    pd.notna(
                        rt_day_low
                    )
                    and pd.notna(
                        rt_day_high
                    )
                )
                else 'N/A'
            )
        )

        signal = market_price_signal(
            latest_point_price,
            rt_day_average
        )

        st.caption(
            f'Market signal for '
            f'{selected_market_point}: '
            f'**{signal}** | '
            'Negative 15-minute intervals '
            'in selected view: '
            f'**{negative_intervals}** | '
            'DAM daily average: '
            f'**{price_metric_value(dam_day_average)}**'
        )

        st.markdown(
            '### Current Hub Snapshot'
        )

        hub_rows = []

        latest_rt_oper_day = (
            latest_rt_row[
                'Oper Day'
            ]
        )

        rt_today = (
            market_rt_df[
                market_rt_df[
                    'Oper Day'
                ]
                == latest_rt_oper_day
            ]
            .copy()
        )

        latest_dam_day = (
            market_dam_df[
                'Oper Day'
            ].max()
            if not market_dam_df.empty
            else pd.NaT
        )

        dam_today = (
            market_dam_df[
                market_dam_df[
                    'Oper Day'
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
                    np.nan
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
                            'Settlement Point'
                        ]
                        == hub
                    ]
                )

                if not hub_lmp_match.empty:

                    hub_lmp = (
                        hub_lmp_match[
                            'LMP'
                        ]
                        .iloc[-1]
                    )

            hub_rows.append(
                {
                    'Hub':
                        hub,

                    'Latest SCED LMP':
                        hub_lmp,

                    'Latest RT SPP':
                        latest_value,

                    'RT Day Avg':
                        average_value,

                    'RT Day High':
                        high_value,

                    'RT Day Low':
                        low_value,

                    'DAM Day Avg':
                        hub_dam_avg,

                    'Signal':
                        market_price_signal(
                            latest_value,
                            average_value
                        )
                }
            )

        hub_snapshot = (
            pd.DataFrame(
                hub_rows
            )
        )

        st.dataframe(
            hub_snapshot,
            use_container_width=True,
            hide_index=True,
            column_config={
                'Latest SCED LMP':
                    st.column_config.NumberColumn(
                        'Latest SCED LMP ($/MWh)',
                        format='$%.2f'
                    ),

                'Latest RT SPP':
                    st.column_config.NumberColumn(
                        'Latest RT SPP ($/MWh)',
                        format='$%.2f'
                    ),

                'RT Day Avg':
                    st.column_config.NumberColumn(
                        'RT Day Avg ($/MWh)',
                        format='$%.2f'
                    ),

                'RT Day High':
                    st.column_config.NumberColumn(
                        'RT Day High ($/MWh)',
                        format='$%.2f'
                    ),

                'RT Day Low':
                    st.column_config.NumberColumn(
                        'RT Day Low ($/MWh)',
                        format='$%.2f'
                    ),

                'DAM Day Avg':
                    st.column_config.NumberColumn(
                        'DAM Day Avg ($/MWh)',
                        format='$%.2f'
                    )
            }
        )

        (
            chart_left,
            chart_right
        ) = st.columns(
            2
        )

        with chart_left:

            st.markdown(
                f'### Real-Time SPP — '
                f'{selected_market_point}'
            )

            rt_chart = (
                selected_rt[
                    [
                        'Timestamp',
                        selected_market_point
                    ]
                ]
                .rename(
                    columns={
                        selected_market_point:
                            'RT SPP ($/MWh)'
                    }
                )
            )

            if rt_chart.empty:

                st.info(
                    'No Real-Time rows are '
                    'available for this selection.'
                )

            else:

                st.line_chart(
                    rt_chart.set_index(
                        'Timestamp'
                    ),
                    use_container_width=True,
                    height=360
                )

        with chart_right:

            st.markdown(
                f'### Day-Ahead SPP — '
                f'{selected_market_point}'
            )

            if (
                market_dam_df.empty
                or selected_market_point
                not in market_dam_df.columns
            ):

                st.info(
                    'DAM SPP is currently unavailable.'
                )

            else:

                dam_chart_day = (
                    market_dam_df[
                        'Oper Day'
                    ].max()
                )

                dam_chart = (
                    market_dam_df[
                        market_dam_df[
                            'Oper Day'
                        ]
                        == dam_chart_day
                    ][
                        [
                            'Timestamp',
                            selected_market_point
                        ]
                    ]
                    .copy()
                )

                dam_chart = (
                    dam_chart.rename(
                        columns={
                            selected_market_point:
                                'DAM SPP ($/MWh)'
                        }
                    )
                )

                st.line_chart(
                    dam_chart.set_index(
                        'Timestamp'
                    ),
                    use_container_width=True,
                    height=360
                )

        with st.expander(
            '📋 View Current Real-Time Price Intervals',
            expanded=False
        ):

            rt_table_columns = [
                'Oper Day',
                'Interval Ending',
                *major_hubs
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
                hide_index=True
            )

    if (
        market_lmp_df.empty
        and lmp_error
    ):

        st.caption(
            'Latest SCED LMP display could '
            'not be loaded; the RT SPP and '
            'DAM sections can still operate. '
            f'{lmp_error}'
        )

    if (
        market_dam_df.empty
        and dam_error
    ):

        st.warning(
            'DAM Settlement Point Prices '
            'could not be loaded. '
            f'{dam_error}'
        )

    st.divider()

    st.markdown(
        '## 🔋 DAM Ancillary Service Prices'
    )

    st.caption(
        'Day-Ahead Market Clearing Price '
        'for Capacity (MCPC) for Non-Spin, '
        'Regulation Down, Regulation Up, '
        'RRS and ECRS.'
    )

    if market_mcpc_df.empty:

        st.info(
            'Current DAM ancillary-service '
            'clearing prices are not available '
            'from the public report right now. '
            + (
                mcpc_error
                if mcpc_error
                else ''
            )
        )

    else:

        ancillary_columns = [
            'NON-SPIN',
            'REG-DOWN',
            'REG-UP',
            'RRS',
            'ECRS'
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
                'Oper Day'
            ].max()
        )

        mcpc_today = (
            market_mcpc_df[
                market_mcpc_df[
                    'Oper Day'
                ]
                == latest_mcpc_day
            ]
            .copy()
        )

        ancillary_summary_rows = []

        for service in ancillary_columns:

            ancillary_summary_rows.append(
                {
                    'Service':
                        service,

                    'Daily Average':
                        mcpc_today[
                            service
                        ].mean(),

                    'Daily Peak':
                        mcpc_today[
                            service
                        ].max(),

                    'Peak Hour Ending':
                        (
                            mcpc_today.loc[
                                mcpc_today[
                                    service
                                ].idxmax(),
                                'Hour Ending'
                            ]
                            if mcpc_today[
                                service
                            ].notna().any()
                            else np.nan
                        )
                }
            )

        ancillary_summary = (
            pd.DataFrame(
                ancillary_summary_rows
            )
        )

        st.dataframe(
            ancillary_summary,
            use_container_width=True,
            hide_index=True,
            column_config={
                'Daily Average':
                    st.column_config.NumberColumn(
                        'Daily Average ($/MW-h)',
                        format='$%.2f'
                    ),

                'Daily Peak':
                    st.column_config.NumberColumn(
                        'Daily Peak ($/MW-h)',
                        format='$%.2f'
                    )
            }
        )

        selected_ancillary = (
            st.selectbox(
                'Ancillary Service',
                options=
                    ancillary_columns,
                index=
                    (
                        ancillary_columns.index(
                            'ECRS'
                        )
                        if 'ECRS'
                        in ancillary_columns
                        else 0
                    ),
                key=
                    'ercot_ancillary_service'
            )
        )

        mcpc_chart = (
            mcpc_today[
                [
                    'Timestamp',
                    selected_ancillary
                ]
            ]
            .rename(
                columns={
                    selected_ancillary:
                        f'{selected_ancillary} MCPC'
                }
            )
        )

        st.line_chart(
            mcpc_chart.set_index(
                'Timestamp'
            ),
            use_container_width=True,
            height=320
        )

        with st.expander(
            '📋 View DAM Ancillary Hourly Prices',
            expanded=False
        ):

            st.dataframe(
                mcpc_today[
                    [
                        'Oper Day',
                        'Hour Ending',
                        *ancillary_columns
                    ]
                ],
                use_container_width=True,
                hide_index=True
            )

    st.divider()

    st.markdown(
        '### ERCOT Sources'
    )

    st.markdown(
        f'- [Latest SCED LMPs for Load Zones '
        f'and Trading Hubs]'
        f'({ERCOT_LATEST_LMP_URL})  \n'
        f'- [Real-Time Settlement Point Prices]'
        f'({ERCOT_RT_SPP_URL})  \n'
        f'- [Day-Ahead Settlement Point Prices]'
        f'({ERCOT_DAM_SPP_URL})  \n'
        f'- [DAM Clearing Prices for Capacity]'
        f'({ERCOT_DAM_MCPC_URL})'
    )

    st.caption(
        'ERCOT broad hub and load-zone prices '
        'are useful market benchmarks, but an '
        "individual generation project's realized "
        'price can differ materially because of '
        'nodal basis, congestion, curtailment and '
        'project-specific settlement mechanics.'
    )


with dashboard_tab:

    st.markdown(
        '## 📘 Dashboard Guide'
    )

    (
        guide_left,
        guide_right
    ) = st.columns(
        [
            1.55,
            1
        ]
    )

    with guide_left:

        st.markdown(
            '### 🎯 Opportunity Score'
        )

        st.caption(
            'Projects are scored from 0–100 '
            'to prioritize attractive and '
            'actionable acquisition opportunities.'
        )

        scoring_methodology = (
            pd.DataFrame(
                {
                    'Factor': [
                        'Seller Motivation',
                        'Development Stage',
                        'Market / Revenue',
                        'Acquisition Value',
                        'Executability'
                    ],

                    'Weight': [
                        f'{distress_weight:.0%}',
                        f'{development_weight:.0%}',
                        f'{market_weight:.0%}',
                        f'{value_weight:.0%}',
                        f'{exec_weight:.0%}'
                    ],

                    'What It Measures': [
                        'Likelihood owner is motivated '
                        'to transact',

                        'Project maturity and progress '
                        'through development',

                        'Revenue visibility + ERCOT location',

                        'Tax-credit / siting attributes',

                        'Ability to realistically '
                        'execute a transaction'
                    ]
                }
            )
        )

        st.dataframe(
            scoring_methodology,
            use_container_width=True,
            hide_index=True
        )

        st.markdown(
            '#### Formula'
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
            f'Market / Revenue = '
            f'Revenue Visibility × '
            f'{revenue_visibility_weight:.0%} '
            f'+ ERCOT Location × '
            f'{location_market_weight:.0%}.'
        )

        st.caption(
            f'Executability = '
            f'Seller Actionability × '
            f'{actionability_weight:.0%} '
            f'+ Timing × '
            f'{timing_exec_weight:.0%} '
            f'+ Development Stage × '
            f'{development_exec_weight:.0%}.'
        )

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
            '#### Example'
        )

        example_background = (
            pd.DataFrame(
                {
                    'Factor': [
                        'Seller Motivation',
                        'Development Stage',
                        'Market / Revenue',
                        'Acquisition Value',
                        'Executability'
                    ],

                    'Score': [
                        example_seller,
                        example_development,
                        example_market,
                        example_value,
                        example_executability
                    ],

                    'Why': [
                        'Discount Potential 4 = 80; '
                        'High Confidence = 100%; '
                        '80 × 100% = 80',

                        'Operating project = 100',

                        f'Revenue visibility = '
                        f'{example_revenue:.0f}; '
                        f'ERCOT-N = '
                        f'{example_location:.0f}',

                        'Tax Credit only = 70',

                        f'Actionability 100 × '
                        f'{actionability_weight:.0%} '
                        f'+ Timing 100 × '
                        f'{timing_exec_weight:.0%} '
                        f'+ Development Stage 100 × '
                        f'{development_exec_weight:.0%}'
                    ]
                }
            )
        )

        st.dataframe(
            example_background,
            use_container_width=True,
            hide_index=True
        )

        st.success(
            f'Example Opportunity Score = '
            f'{example_final:.1f}'
        )

    with guide_right:

        st.markdown(
            '### 🧭 How to Use'
        )

        st.markdown(
            """
            **1. Management Shortlist** — Top 5 priorities  
            **2. Top Acquisition Targets** — Top 20 overall  
            **3. By Technology** — Solar, Storage or Wind  
            **4. ERCOT Area** — Compare market location  
            **5. Bundles** — Multiple 50–60 MW assets by owner  
            **6. Score Breakdown** — Drill into a project  
            **7. Map Explorer** — View all mapped projects, filter the universe, and drill into a selected project  
            **8. ERCOT Competitor Due Diligence** — Screen Project Orbit competitors in ERCOT South, map them, and download the list  
            **9. ERCOT Market Prices** — Monitor live RT SPP, DAM prices, ancillary-service clearing prices, and project-area benchmarks
            """
        )

        st.markdown(
            '### 🚦 Score Guide'
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
            '### 🗺️ Location Logic'
        )

        location_guide = (
            pd.DataFrame(
                {
                    'Area': [
                        'ERCOT-N',
                        'ERCOT-H',
                        'ERCOT-S',
                        'ERCOT-W',
                        'Panhandle'
                    ],

                    'Score': [
                        location_north,
                        location_houston,
                        location_south,
                        location_west,
                        location_panhandle
                    ]
                }
            )
        )

        st.dataframe(
            location_guide,
            use_container_width=True,
            hide_index=True
        )

        st.caption(
            'Location is a broad screening proxy. '
            'Node-level congestion, basis, curtailment '
            'and market fundamentals can materially '
            'differ within each area.'
        )

    with st.expander(
        '📐 View Full Score Logic',
        expanded=False
    ):

        st.markdown(
            '#### Seller Motivation'
        )

        st.caption(
            'Measures the strength of the '
            'seller-side reason to transact. '
            'The base motivation score is '
            'adjusted for confidence.'
        )

        st.dataframe(
            pd.DataFrame(
                {
                    'Discount Potential': [
                        '5 – Very High',
                        '4 – High',
                        '3 – Moderate',
                        '2 – Low',
                        '1 – Very Low',
                        'No Signal'
                    ],

                    'Base Score': [
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
                    'Confidence': [
                        'High',
                        'Medium',
                        'Low'
                    ],

                    'Multiplier': [
                        f'{confidence_high:.0%}',
                        f'{confidence_medium:.0%}',
                        f'{confidence_low:.0%}'
                    ]
                }
            ),
            use_container_width=True,
            hide_index=True
        )

        st.markdown(
            '#### Development Stage'
        )

        st.dataframe(
            pd.DataFrame(
                {
                    'Stage': [
                        'Operating / Construction Complete',
                        '>50% Construction',
                        'In Construction',
                        'IA Executed',
                        'FIS Completed',
                        'FIS Started',
                        'Studies Undergoing / Other',
                        'Pre-Study',
                        'Inactive / Suspended / Retired'
                    ],

                    'Score': [
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
            '#### Market / Revenue'
        )

        st.caption(
            f'Market / Revenue = Revenue Visibility × '
            f'{revenue_visibility_weight:.0%} '
            f'+ ERCOT Location × '
            f'{location_market_weight:.0%}.'
        )

        st.dataframe(
            pd.DataFrame(
                {
                    'Revenue Visibility': [
                        'Contract + Named Offtaker',
                        'Named Offtaker Only',
                        'Contract Only',
                        'Neither'
                    ],

                    'Score': [
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
                    'ERCOT Area': [
                        'ERCOT-N',
                        'ERCOT-H',
                        'ERCOT-S',
                        'ERCOT-W',
                        'Panhandle',
                        'Unknown / Other'
                    ],

                    'Location Score': [
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
            '#### Acquisition Value'
        )

        st.dataframe(
            pd.DataFrame(
                {
                    'Attributes': [
                        'Tax Credit + Energy Community',
                        'Tax Credit Only',
                        'Energy Community Only',
                        'Neither'
                    ],

                    'Score': [
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
            'Domestic Content is not included in '
            'the automated score because Orennia '
            'does not currently expose project-level '
            'Domestic Content qualification or bonus '
            'fields. Equipment information can be '
            'used as a diligence reference but is '
            'not treated as evidence of qualification.'
        )

        st.markdown(
            '#### Executability'
        )

        st.caption(
            f'Executability = Seller Actionability × '
            f'{actionability_weight:.0%} '
            f'+ Timing × '
            f'{timing_exec_weight:.0%} '
            f'+ Development Stage × '
            f'{development_exec_weight:.0%}.'
        )

    st.caption(
        f'ERCOT Location represents '
        f'{location_market_weight * market_weight:.1%} '
        'of the total Opportunity Score '
        'under the current assumptions.'
    )

    st.caption(
        'Screening tool only — rankings prioritize '
        'sourcing and diligence activity and are not '
        'a substitute for full investment underwriting.'
    )

    st.divider()

    st.subheader(
        'Seller Motivation / Actionability Assumptions'
    )

    st.caption(
        'These assumptions drive the project rankings. '
        'Public seller intelligence below is informational '
        'only and does not automatically change '
        'project scores.'
    )

    current_sellers = (
        st.session_state[
            'seller_assumptions'
        ].copy()
    )

    current_sellers.insert(
        2,
        'Discount Score',
        current_sellers.apply(
            lambda row:
                calculate_discount_score(
                    row[
                        'Discount Potential'
                    ],
                    row[
                        'Confidence'
                    ]
                ),
            axis=1
        )
    )

    current_sellers.insert(
        4,
        'Actionability Score',
        current_sellers[
            'Seller Actionability'
        ].apply(
            actionability_score
        )
    )

    edited_sellers_full = (
        st.data_editor(
            current_sellers,
            use_container_width=True,
            hide_index=True,
            num_rows='dynamic',
            key=
                'seller_assumptions_editor',
            disabled=[
                'Discount Score',
                'Actionability Score'
            ],
            column_order=[
                'Owner',
                'Discount Potential',
                'Discount Score',
                'Seller Actionability',
                'Actionability Score',
                'Confidence'
            ],
            column_config={
                'Discount Potential':
                    st.column_config.NumberColumn(
                        'Discount Potential',
                        min_value=1,
                        max_value=5,
                        step=1,
                        format='%d'
                    ),

                'Discount Score':
                    st.column_config.ProgressColumn(
                        'Discount Score',
                        min_value=0,
                        max_value=100,
                        format='%.0f'
                    ),

                'Seller Actionability':
                    st.column_config.NumberColumn(
                        'Seller Actionability',
                        min_value=1,
                        max_value=5,
                        step=1,
                        format='%d'
                    ),

                'Actionability Score':
                    st.column_config.ProgressColumn(
                        'Actionability Score',
                        min_value=0,
                        max_value=100,
                        format='%.0f'
                    ),

                'Confidence':
                    st.column_config.SelectboxColumn(
                        'Confidence',
                        options=[
                            'High',
                            'Medium',
                            'Low'
                        ]
                    )
            }
        )
    )


editable_seller_columns = [
    'Owner',
    'Discount Potential',
    'Seller Actionability',
    'Confidence'
]


new_seller_assumptions = (
    edited_sellers_full[
        editable_seller_columns
    ].copy()
)


old_seller_assumptions = (
    st.session_state[
        'seller_assumptions'
    ][
        editable_seller_columns
    ].copy()
)


if not new_seller_assumptions.equals(
    old_seller_assumptions
):

    st.session_state[
        'seller_assumptions'
    ] = new_seller_assumptions

    st.rerun()


edited_sellers = (
    st.session_state[
        'seller_assumptions'
    ].copy()
)


edited_sellers[
    'Owner Key'
] = (
    edited_sellers[
        'Owner'
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
        'Owner Key'
    )
    .to_dict(
        'index'
    )
)


SELLER_SEARCH_TERMS = {
    'Birch Creek Energy':
        'Birch Creek Energy',

    'Birch Creek Development':
        'Birch Creek Energy',

    'esVolta':
        'esVolta',

    'Key Capture Energy':
        'Key Capture Energy',

    'Lightsource BP':
        'Lightsource bp',

    'Ørsted U.S. Onshore':
        'Orsted U.S. Onshore',

    'Orsted':
        'Orsted U.S. renewables',

    'Flatiron Energy':
        'Flatiron Energy',

    'Recurrent Energy':
        'Recurrent Energy',

    'EDF power solutions North America':
        'EDF power solutions North America',

    'EDF Renewables':
        'EDF Renewables North America',

    'Greenbacker Renewable Energy Company':
        'Greenbacker Renewable Energy Company'
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

    encoded_query = (
        urllib.parse.quote_plus(
            query
        )
    )

    url = (
        'https://news.google.com/'
        'rss/search?'
        f'q={encoded_query}'
        '&hl=en-US'
        '&gl=US'
        '&ceid=US:en'
    )

    request = urllib.request.Request(
        url,
        headers={
            'User-Agent':
                'Mozilla/5.0 '
                'ERCOT-Acquisition-Dashboard'
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
            './/item'
        ):

            title = clean_text(
                item.findtext(
                    'title'
                )
            )

            description = strip_html(
                item.findtext(
                    'description'
                )
            )

            source = clean_text(
                item.findtext(
                    'source'
                )
            )

            link = clean_text(
                item.findtext(
                    'link'
                )
            )

            published_raw = clean_text(
                item.findtext(
                    'pubDate'
                )
            )

            published = pd.NaT

            if published_raw:

                try:

                    parsed = (
                        parsedate_to_datetime(
                            published_raw
                        )
                    )

                    if parsed.tzinfo is None:

                        parsed = (
                            parsed.replace(
                                tzinfo=timezone.utc
                            )
                        )

                    published = (
                        pd.Timestamp(
                            parsed
                        )
                    )

                except Exception:

                    published = pd.NaT

            articles.append(
                {
                    'Title':
                        title,

                    'Description':
                        description,

                    'Source':
                        source,

                    'Published':
                        published,

                    'URL':
                        link
                }
            )

    except Exception:

        return []

    return articles


SELLER_SIGNAL_RULES = [
    {
        'Signal Type':
            'Formal Sale / Strategic Review',

        'Keywords': [
            'strategic review',
            'strategic alternatives',
            'sale process',
            'portfolio sale',
            'asset sale',
            'exploring a sale',
            'divestiture'
        ],

        'Suggested Motivation':
            5,

        'Suggested Actionability':
            5
    },

    {
        'Signal Type':
            'Restructuring / Financial Stress',

        'Keywords': [
            'bankruptcy',
            'chapter 11',
            'restructuring',
            'default',
            'distressed',
            'liquidity crisis',
            'going concern'
        ],

        'Suggested Motivation':
            5,

        'Suggested Actionability':
            4
    },

    {
        'Signal Type':
            'Capital Recycling / Monetization',

        'Keywords': [
            'capital recycling',
            'asset monetization',
            'monetization',
            'sell-down',
            'sell down',
            'stake sale'
        ],

        'Suggested Motivation':
            4,

        'Suggested Actionability':
            5
    },

    {
        'Signal Type':
            'Layoffs / Cost Reduction',

        'Keywords': [
            'layoffs',
            'layoff',
            'job cuts',
            'workforce reduction',
            'headcount reduction'
        ],

        'Suggested Motivation':
            4,

        'Suggested Actionability':
            3
    },

    {
        'Signal Type':
            'Project Cancellation / Portfolio Pressure',

        'Keywords': [
            'project cancellation',
            'project cancellations',
            'cancelled project',
            'canceled project',
            'project impairment',
            'impairment charge'
        ],

        'Suggested Motivation':
            4,

        'Suggested Actionability':
            3
    }
]


def classify_article(
    title,
    description
):

    text = (
        clean_text(
            title
        )
        + ' '
        + clean_text(
            description
        )
    ).lower()

    for rule in SELLER_SIGNAL_RULES:

        for keyword in rule[
            'Keywords'
        ]:

            if keyword.lower() in text:

                return rule

    return None


def build_advisory_seller_intelligence():

    rows = []

    for _, seller in edited_sellers.iterrows():

        owner = seller[
            'Owner'
        ]

        search_term = (
            SELLER_SEARCH_TERMS.get(
                owner,
                owner
            )
        )

        articles = fetch_company_news(
            search_term
        )

        classified_articles = []

        for article in articles:

            rule = classify_article(
                article.get(
                    'Title'
                ),
                article.get(
                    'Description'
                )
            )

            if rule is None:

                continue

            classified_articles.append(
                {
                    **article,

                    'Signal Type':
                        rule[
                            'Signal Type'
                        ],

                    'Suggested Motivation':
                        rule[
                            'Suggested Motivation'
                        ],

                    'Suggested Actionability':
                        rule[
                            'Suggested Actionability'
                        ]
                }
            )

        if classified_articles:

            def safe_sort_date(
                article
            ):

                published = article.get(
                    'Published'
                )

                if pd.isna(
                    published
                ):

                    return pd.Timestamp.min

                timestamp = pd.Timestamp(
                    published
                )

                if timestamp.tzinfo is not None:

                    timestamp = (
                        timestamp
                        .tz_localize(
                            None
                        )
                    )

                return timestamp

            classified_articles = sorted(
                classified_articles,
                key=safe_sort_date,
                reverse=True
            )

            latest = (
                classified_articles[0]
            )

            rows.append(
                {
                    'Owner':
                        owner,

                    'Current Motivation':
                        seller[
                            'Discount Potential'
                        ],

                    'Current Actionability':
                        seller[
                            'Seller Actionability'
                        ],

                    'Suggested Motivation':
                        latest[
                            'Suggested Motivation'
                        ],

                    'Suggested Actionability':
                        latest[
                            'Suggested Actionability'
                        ],

                    'Signal Type':
                        latest[
                            'Signal Type'
                        ],

                    'Signal Date':
                        latest[
                            'Published'
                        ],

                    'Source':
                        latest[
                            'Source'
                        ],

                    'Latest Signal':
                        latest[
                            'Title'
                        ],

                    'Article':
                        latest[
                            'URL'
                        ]
                }
            )

        else:

            rows.append(
                {
                    'Owner':
                        owner,

                    'Current Motivation':
                        seller[
                            'Discount Potential'
                        ],

                    'Current Actionability':
                        seller[
                            'Seller Actionability'
                        ],

                    'Suggested Motivation':
                        np.nan,

                    'Suggested Actionability':
                        np.nan,

                    'Signal Type':
                        'No qualifying recent signal',

                    'Signal Date':
                        pd.NaT,

                    'Source':
                        '',

                    'Latest Signal':
                        '',

                    'Article':
                        ''
                }
            )

    return pd.DataFrame(
        rows
    )


with dashboard_tab:

    with st.expander(
        '📡 Public Seller Intelligence — Informational Only',
        expanded=False
    ):

        st.caption(
            'This feed monitors recent public seller '
            'signals and provides a suggested direction '
            'for review. It does NOT change the Seller '
            'Motivation or Actionability assumptions '
            'above and therefore does not automatically '
            'alter project rankings.'
        )

        refresh_intelligence = (
            st.button(
                '🔄 Refresh Public Signals'
            )
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
                'Current Motivation':
                    st.column_config.NumberColumn(
                        'Current Motivation',
                        format='%.0f'
                    ),

                'Current Actionability':
                    st.column_config.NumberColumn(
                        'Current Actionability',
                        format='%.0f'
                    ),

                'Suggested Motivation':
                    st.column_config.NumberColumn(
                        'Suggested Motivation',
                        format='%.0f'
                    ),

                'Suggested Actionability':
                    st.column_config.NumberColumn(
                        'Suggested Actionability',
                        format='%.0f'
                    ),

                'Signal Date':
                    st.column_config.DateColumn(
                        'Signal Date'
                    ),

                'Article':
                    st.column_config.LinkColumn(
                        'Article'
                    )
            }
        )

    st.divider()


APP_DIR = Path(
    __file__
).resolve().parent


repo_csv_files = [
    path
    for path
    in APP_DIR.rglob(
        '*.csv'
    )
    if path.name.startswith(
        (
            'Power Projects-',
            'Power%20Projects-',
            'Power_Projects-'
        )
    )
]


repo_csv_files = sorted(
    repo_csv_files,
    key=lambda path:
        path.stat().st_mtime,
    reverse=True
)


if uploaded_file is not None:

    df = pd.read_csv(
        uploaded_file
    )

    active_data_source = (
        'Optional uploaded CSV'
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
            'The Dashboard Guide and scoring '
            'methodology above are available '
            'without a CSV. Project rankings '
            'and project-level tables will '
            'populate automatically when a '
            'Power Projects CSV is stored in '
            'the app repository.'
        )

    with map_tab:

        st.info(
            'The Map Explorer needs project '
            'coordinates. Add the latest Power '
            'Projects CSV to the GitHub / '
            'Streamlit repository to make the '
            'project selector and map load '
            'automatically. A manual upload '
            'is optional.'
        )

    with competitor_tab:

        st.info(
            'The ERCOT Competitor Due Diligence '
            'tab needs the Orennia Power Projects '
            'CSV. Add the latest export to the '
            'repository or upload it from the '
            'sidebar.'
        )

    st.stop()


required_columns = [
    'Power Project Name',
    'Owner',
    'Queue ID',
    'ISO Zone',
    'Power Project Type',
    'Capacity (MW)',
    'First Power Date',
    'Power Project Status'
]


missing_columns = [
    col
    for col
    in required_columns
    if col
    not in df.columns
]


if missing_columns:

    with dashboard_tab:

        st.error(
            'The active project data file '
            'is missing these required columns: '
            + ', '.join(
                missing_columns
            )
        )

    with map_tab:

        st.error(
            'The active project data file '
            'is missing required dashboard '
            'columns, so the map cannot '
            'be populated.'
        )

    with competitor_tab:

        st.error(
            'The active project data file '
            'is missing required columns, '
            'so the Orbit competitor screen '
            'cannot be populated.'
        )

    st.stop()


df[
    'Owner'
] = df[
    'Owner'
].fillna(
    ''
)


df[
    'First Power Date'
] = pd.to_datetime(
    df[
        'First Power Date'
    ],
    errors='coerce'
)


df[
    'Capacity (MW)'
] = pd.to_numeric(
    df[
        'Capacity (MW)'
    ],
    errors='coerce'
)


optional_diligence_columns = [
    'Equipment Manufacturer',
    'Equipment Model',
    'EPC',
    'Integrator'
]


available_diligence_columns = [
    col
    for col
    in optional_diligence_columns
    if col
    in df.columns
]


optional_interconnection_columns = [
    'Interconnection Service Type',
    'Queue Cycle',
    'Queue Date',
    'Interconnection Cost Physical ($)',
    'Interconnection Cost System Upgrade ($)',
    'Interconnection Cost Total ($)'
]


available_interconnection_columns = [
    col
    for col
    in optional_interconnection_columns
    if col
    in df.columns
]


optional_contract_columns = [
    'Contract Execution Date',
    'Contract Termination Date',
    'Contract Term Years (Year)'
]


available_contract_columns = [
    col
    for col
    in optional_contract_columns
    if col
    in df.columns
]


df[
    'ERCOT Area'
] = df[
    'ISO Zone'
].apply(
    map_ercot_area
)


df[
    'Location Score'
] = df[
    'ERCOT Area'
].apply(
    location_score
)


competitor_source = (
    df.copy()
)


df = df[
    (
        df[
            'Power Project Type'
        ].isin(
            [
                'Solar',
                'Storage'
            ]
        )
    )
    |
    (
        (
            df[
                'Power Project Type'
            ]
            == 'Wind'
        )
        &
        (
            df[
                'Power Project Status'
            ]
            == 'Operating'
        )
    )
].copy()


df = df[
    ~df[
        'Owner'
    ].str.contains(
        'Pine Gate',
        case=False,
        na=False
    )
].copy()


excluded_projects = [
    'Texas One',
    'Rio Lago Solar',
    'Grapefruit Solar',
    'Limewood Bell Renewables',
    'Lavender Storage Project',
    'Lavender Solar',
    'Twin Oaks Solar',
    'Magnolia Solar',
    'Mesquite Solar'
]


df = df[
    ~df[
        'Power Project Name'
    ].isin(
        excluded_projects
    )
].copy()


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
    'Discount Potential'
] = df[
    'Owner'
].apply(
    lambda x:
        get_seller_value(
            x,
            'Discount Potential'
        )
)


df[
    'Seller Actionability'
] = df[
    'Owner'
].apply(
    lambda x:
        get_seller_value(
            x,
            'Seller Actionability'
        )
)


df[
    'Seller Confidence'
] = df[
    'Owner'
].apply(
    lambda x:
        get_seller_value(
            x,
            'Confidence'
        )
)


df[
    'Distress Score'
] = df.apply(
    lambda row:
        calculate_discount_score(
            row[
                'Discount Potential'
            ],
            row[
                'Seller Confidence'
            ]
        ),
    axis=1
)


def development_stage_score(
    row
):

    status = clean_text(
        row.get(
            'Power Project Status'
        )
    )

    detailed = clean_text(
        row.get(
            'Detailed Status'
        )
    )

    if (
        status == 'Operating'
        or detailed
        == 'Construction Complete'
    ):

        return development_operating

    if (
        'More Than 50%'
        in detailed
        or '>50%'
        in detailed
    ):

        return development_50

    if status == 'In Construction':

        return development_construction

    if (
        status == 'IA Executed'
        or ', IA'
        in detailed
    ):

        return development_ia

    if 'FIS Completed' in detailed:

        return development_fis_complete

    if 'FIS Started' in detailed:

        return development_fis_started

    if status == 'Pre-Study':

        return development_pre

    if status in [
        'Inactive',
        'Suspended',
        'Retired'
    ]:

        return development_inactive

    return development_studies


df[
    'Development Stage'
] = df.apply(
    development_stage_score,
    axis=1
)


def revenue_visibility_score(
    row
):

    contract = has_value(
        row.get(
            'Contract Type'
        )
    )

    offtaker = has_value(
        row.get(
            'Contract Offtaker'
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
    'Revenue Visibility'
] = df.apply(
    revenue_visibility_score,
    axis=1
)


df[
    'Market / Revenue'
] = (
    df[
        'Revenue Visibility'
    ]
    * revenue_visibility_weight
    +
    df[
        'Location Score'
    ]
    * location_market_weight
)


energy_columns = [
    'Fossil Fuel Energy Communities',
    'Retired Coal Facilities Energy Communities',
    'Low Income Communities',
    'Native American Lands'
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
            'true',
            'yes',
            '1'
        ]:

            return 'Yes'

    return 'No'


df[
    'Energy Community'
] = df.apply(
    energy_community,
    axis=1
)


def acquisition_value(
    row
):

    tax_credit = has_value(
        row.get(
            'PTC/ITC'
        )
    )

    ec = (
        row[
            'Energy Community'
        ]
        == 'Yes'
    )

    if (
        tax_credit
        and ec
    ):

        return value_both

    if tax_credit:

        return value_tax

    if ec:

        return value_ec

    return value_none


df[
    'Acquisition Value'
] = df.apply(
    acquisition_value,
    axis=1
)


df[
    'Domestic Content Review'
] = (
    'Unknown / Diligence Required'
)


as_of_date = pd.Timestamp(
    date.today()
)


def timing_score(
    row
):

    cod = row[
        'First Power Date'
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
    'Timing Score'
] = df.apply(
    timing_score,
    axis=1
)


df[
    'Actionability Score'
] = df[
    'Seller Actionability'
].apply(
    actionability_score
)


df[
    'Executability'
] = (
    df[
        'Actionability Score'
    ]
    * actionability_weight
    +
    df[
        'Timing Score'
    ]
    * timing_exec_weight
    +
    df[
        'Development Stage'
    ]
    * development_exec_weight
)


def completeness(
    row
):

    score = 0

    if has_value(
        row.get(
            'Owner'
        )
    ):

        score += 40

    if has_value(
        row.get(
            'Queue ID'
        )
    ):

        score += 15

    if not pd.isna(
        row.get(
            'First Power Date'
        )
    ):

        score += 15

    if (
        has_value(
            row.get(
                'Contract Type'
            )
        )
        or
        has_value(
            row.get(
                'Contract Offtaker'
            )
        )
    ):

        score += 15

    if has_value(
        row.get(
            'PTC/ITC'
        )
    ):

        score += 15

    return score


df[
    'Data Completeness'
] = df.apply(
    completeness,
    axis=1
)


df[
    'Opportunity Score'
] = (
    df[
        'Distress Score'
    ]
    * distress_weight
    +
    df[
        'Development Stage'
    ]
    * development_weight
    +
    df[
        'Market / Revenue'
    ]
    * market_weight
    +
    df[
        'Acquisition Value'
    ]
    * value_weight
    +
    df[
        'Executability'
    ]
    * exec_weight
).round(
    2
)


def action(
    row
):

    if pd.isna(
        row[
            'Discount Potential'
        ]
    ):

        return (
            'RESEARCH / MONITOR'
        )

    score = row[
        'Opportunity Score'
    ]

    if score >= 80:

        return 'CONTACT / DILIGENCE'

    if score >= 70:

        return 'INVESTIGATE'

    if score >= 60:

        return 'MONITOR'

    return 'LOW PRIORITY'


df[
    'Action'
] = df.apply(
    action,
    axis=1
)


df = (
    df.sort_values(
        by=[
            'Opportunity Score',
            'Data Completeness',
            'Capacity (MW)'
        ],
        ascending=[
            False,
            False,
            False
        ]
    )
    .reset_index(
        drop=True
    )
)


df[
    'Rank'
] = np.arange(
    1,
    len(
        df
    ) + 1
)


def why_it_ranks(
    row
):

    reasons = []

    if (
        row[
            'Distress Score'
        ]
        >= 70
    ):

        reasons.append(
            'Strong seller motivation / transaction angle'
        )

    elif (
        row[
            'Distress Score'
        ]
        >= 50
    ):

        reasons.append(
            'Credible seller opportunity'
        )

    if (
        row[
            'Development Stage'
        ]
        >= 95
    ):

        reasons.append(
            'Operating / highly mature project'
        )

    elif (
        row[
            'Development Stage'
        ]
        >= 80
    ):

        reasons.append(
            'Advanced development stage'
        )

    if (
        row[
            'Revenue Visibility'
        ]
        >= 90
    ):

        reasons.append(
            'Strong revenue / offtaker visibility'
        )

    elif (
        row[
            'Revenue Visibility'
        ]
        >= 80
    ):

        reasons.append(
            'Some contracted visibility'
        )

    if (
        row[
            'Location Score'
        ]
        >= 85
    ):

        reasons.append(
            'Attractive ERCOT market location'
        )

    if (
        row[
            'Acquisition Value'
        ]
        >= 70
    ):

        reasons.append(
            'Attractive tax-credit / siting attributes'
        )

    if (
        row[
            'Executability'
        ]
        >= 80
    ):

        reasons.append(
            'High execution readiness'
        )

    capacity = row.get(
        'Capacity (MW)',
        np.nan
    )

    if (
        not pd.isna(
            capacity
        )
        and capacity >= 100
    ):

        reasons.append(
            f'{capacity:,.0f} MW scale'
        )

    if not reasons:

        reasons.append(
            'Strong composite Opportunity Score'
        )

    return '; '.join(
        reasons[:3]
    )


def key_risk(
    row
):

    risks = []

    if pd.isna(
        row[
            'Discount Potential'
        ]
    ):

        risks.append(
            'Seller motivation not yet verified'
        )

    elif (
        row[
            'Distress Score'
        ]
        < 50
    ):

        risks.append(
            'Limited evidence of seller pressure'
        )

    if (
        row[
            'Development Stage'
        ]
        < 55
    ):

        risks.append(
            'Early-stage development risk'
        )

    elif (
        row[
            'Development Stage'
        ]
        < 75
    ):

        risks.append(
            'Development risk remains'
        )

    if (
        row[
            'Revenue Visibility'
        ]
        <= 45
    ):

        risks.append(
            'Limited visible revenue certainty'
        )

    elif (
        row[
            'Revenue Visibility'
        ]
        < 90
    ):

        risks.append(
            'Revenue / offtaker visibility is incomplete'
        )

    if (
        row[
            'Location Score'
        ]
        <= 50
    ):

        risks.append(
            'Lower broad-area location score; node may differ'
        )

    if pd.isna(
        row[
            'First Power Date'
        ]
    ):

        risks.append(
            'COD timing unclear'
        )

    if (
        row[
            'Data Completeness'
        ]
        < 70
    ):

        risks.append(
            'Material diligence data gaps'
        )

    if not risks:

        risks.append(
            'No major screen-level issue; '
            'full diligence still required'
        )

    return '; '.join(
        risks[:2]
    )


df[
    'Why It Ranks'
] = df.apply(
    why_it_ranks,
    axis=1
)


df[
    'Key Risk'
] = df.apply(
    key_risk,
    axis=1
)


df[
    'Recommended Action'
] = df[
    'Action'
]


with dashboard_tab:

    (
        c1,
        c2,
        c3,
        c4
    ) = st.columns(
        4
    )

    c1.metric(
        'Projects Screened',
        f'{len(df):,}'
    )

    c2.metric(
        'Total Capacity',
        f"{df['Capacity (MW)'].sum():,.0f} MW"
    )

    c3.metric(
        'Contact / Diligence',
        int(
            (
                df[
                    'Action'
                ]
                == 'CONTACT / DILIGENCE'
            ).sum()
        )
    )

    c4.metric(
        'Top Score',
        f"{df['Opportunity Score'].max():.1f}"
    )

    st.divider()

    st.subheader(
        '🎯 Management Shortlist'
    )

    st.caption(
        'Top five current acquisition priorities '
        'based on the screening model.'
    )

    management_shortlist = (
        df.head(
            5
        ).copy()
    )

    management_shortlist[
        'Management Rank'
    ] = np.arange(
        1,
        len(
            management_shortlist
        ) + 1
    )

    management_columns = [
        'Management Rank',
        'Power Project Name',
        'Owner',
        'Power Project Type',
        'ERCOT Area',
        'Location Score',
        'Capacity (MW)',
        'Power Project Status',
        'Opportunity Score',
        'Why It Ranks',
        'Key Risk',
        'Recommended Action'
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
        column_config={
            'Management Rank':
                st.column_config.NumberColumn(
                    'Rank'
                ),

            'Power Project Type':
                st.column_config.TextColumn(
                    'Tech'
                ),

            'Capacity (MW)':
                st.column_config.NumberColumn(
                    'MW',
                    format='%.1f'
                ),

            'Location Score':
                st.column_config.NumberColumn(
                    'Location',
                    format='%.0f'
                ),

            'Opportunity Score':
                st.column_config.ProgressColumn(
                    'Score',
                    min_value=0,
                    max_value=100,
                    format='%.1f'
                ),

            'Recommended Action':
                st.column_config.TextColumn(
                    'Action'
                )
        }
    )

    st.divider()

    st.subheader(
        'Filters'
    )

    (
        f1,
        f2,
        f3,
        f4
    ) = st.columns(
        4
    )

    technology_options = sorted(
        df[
            'Power Project Type'
        ].dropna().unique()
    )

    selected_technology = (
        f1.multiselect(
            'Technology',
            technology_options,
            default=
                technology_options
        )
    )

    ercot_area_options = sorted(
        df[
            'ERCOT Area'
        ].dropna().unique()
    )

    selected_ercot_areas = (
        f2.multiselect(
            'ERCOT Area',
            ercot_area_options,
            default=
                ercot_area_options
        )
    )

    owner_options = sorted(
        [
            owner
            for owner
            in df[
                'Owner'
            ].unique()
            if clean_text(
                owner
            )
        ]
    )

    selected_owners = (
        f3.multiselect(
            'Owner',
            owner_options
        )
    )

    status_options = sorted(
        df[
            'Power Project Status'
        ].dropna().unique()
    )

    selected_status = (
        f4.multiselect(
            'Project Status',
            status_options,
            default=
                status_options
        )
    )

    filtered = df[
        df[
            'Power Project Type'
        ].isin(
            selected_technology
        )
    ].copy()

    filtered = filtered[
        filtered[
            'ERCOT Area'
        ].isin(
            selected_ercot_areas
        )
    ]

    filtered = filtered[
        filtered[
            'Power Project Status'
        ].isin(
            selected_status
        )
    ]

    if selected_owners:

        filtered = filtered[
            filtered[
                'Owner'
            ].isin(
                selected_owners
            )
        ]

    st.divider()

    st.subheader(
        '🏆 Top Acquisition Targets'
    )

    st.caption(
        'Top 20 projects based on Opportunity Score.'
    )

    display_columns = [
        'Rank',
        'Power Project Name',
        'Owner',
        'Power Project Type',
        'ERCOT Area',
        'ISO Zone',
        'Location Score',
        'Capacity (MW)',
        'Power Project Status',
        'First Power Date',
        'Contract Type',
        'Contract Offtaker',
        'Distress Score',
        'Development Stage',
        'Revenue Visibility',
        'Market / Revenue',
        'Acquisition Value',
        'Executability',
        'Opportunity Score',
        'Action'
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
        column_config={
            'Distress Score':
                st.column_config.NumberColumn(
                    'Seller Motivation'
                ),

            'Development Stage':
                st.column_config.NumberColumn(
                    'Development Stage',
                    format='%.1f'
                ),

            'Revenue Visibility':
                st.column_config.NumberColumn(
                    'Revenue Visibility',
                    format='%.1f'
                ),

            'Location Score':
                st.column_config.NumberColumn(
                    'Location',
                    format='%.0f'
                ),

            'Market / Revenue':
                st.column_config.NumberColumn(
                    'Market / Revenue',
                    format='%.1f'
                ),

            'Opportunity Score':
                st.column_config.ProgressColumn(
                    'Opportunity Score',
                    min_value=0,
                    max_value=100,
                    format='%.1f'
                ),

            'First Power Date':
                st.column_config.DateColumn(
                    'COD'
                )
        }
    )

    st.divider()

    st.subheader(
        '⚡ Top Projects by Technology'
    )

    tech_options = sorted(
        df[
            'Power Project Type'
        ].dropna().unique()
    )

    selected_tech_rank = (
        st.selectbox(
            'Select Technology',
            tech_options,
            key=
                'technology_ranking'
        )
    )

    technology_ranked = (
        df[
            df[
                'Power Project Type'
            ]
            == selected_tech_rank
        ].copy()
    )

    technology_ranked = (
        technology_ranked
        .sort_values(
            by=[
                'Opportunity Score',
                'Data Completeness',
                'Capacity (MW)'
            ],
            ascending=[
                False,
                False,
                False
            ]
        )
        .reset_index(
            drop=True
        )
    )

    technology_ranked[
        'Technology Rank'
    ] = np.arange(
        1,
        len(
            technology_ranked
        ) + 1
    )

    technology_top_20 = (
        technology_ranked
        .head(
            20
        )
    )

    tech_columns = [
        'Technology Rank',
        'Power Project Name',
        'Owner',
        'ERCOT Area',
        'Location Score',
        'Capacity (MW)',
        'Power Project Status',
        'First Power Date',
        'Contract Type',
        'Contract Offtaker',
        'Distress Score',
        'Development Stage',
        'Revenue Visibility',
        'Market / Revenue',
        'Acquisition Value',
        'Executability',
        'Opportunity Score',
        'Action'
    ]

    tech_columns = [
        col
        for col
        in tech_columns
        if col
        in technology_top_20.columns
    ]

    (
        t1,
        t2,
        t3
    ) = st.columns(
        3
    )

    t1.metric(
        f'{selected_tech_rank} Projects',
        len(
            technology_ranked
        )
    )

    t2.metric(
        f'{selected_tech_rank} Capacity',
        f"{technology_ranked['Capacity (MW)'].sum():,.0f} MW"
    )

    if len(
        technology_ranked
    ) > 0:

        t3.metric(
            'Top Technology Score',
            f"{technology_ranked['Opportunity Score'].max():.1f}"
        )

    st.dataframe(
        technology_top_20[
            tech_columns
        ],
        use_container_width=True,
        hide_index=True,
        column_config={
            'Technology Rank':
                st.column_config.NumberColumn(
                    'Rank'
                ),

            'Distress Score':
                st.column_config.NumberColumn(
                    'Seller Motivation'
                ),

            'Development Stage':
                st.column_config.NumberColumn(
                    'Development Stage',
                    format='%.1f'
                ),

            'Location Score':
                st.column_config.NumberColumn(
                    'Location',
                    format='%.0f'
                ),

            'Revenue Visibility':
                st.column_config.NumberColumn(
                    'Revenue Visibility',
                    format='%.1f'
                ),

            'Market / Revenue':
                st.column_config.NumberColumn(
                    'Market / Revenue',
                    format='%.1f'
                ),

            'First Power Date':
                st.column_config.DateColumn(
                    'COD'
                ),

            'Opportunity Score':
                st.column_config.ProgressColumn(
                    'Opportunity Score',
                    min_value=0,
                    max_value=100,
                    format='%.1f'
                )
        }
    )

    st.divider()

    st.subheader(
        '🗺️ ERCOT Area Summary'
    )

    st.caption(
        'Broad market-location screen by ERCOT area. '
        'Location affects 30% of Market / Revenue '
        f'and currently '
        f'{location_market_weight * market_weight:.1%} '
        'of the total Opportunity Score.'
    )

    area_summary = (
        df.groupby(
            'ERCOT Area',
            as_index=False
        )
        .agg(
            Projects=(
                'Power Project Name',
                'count'
            ),

            MW=(
                'Capacity (MW)',
                'sum'
            ),

            Location_Score=(
                'Location Score',
                'mean'
            ),

            Average_Score=(
                'Opportunity Score',
                'mean'
            ),

            Best_Score=(
                'Opportunity Score',
                'max'
            )
        )
    )

    area_summary = (
        area_summary
        .sort_values(
            by=[
                'Location_Score',
                'Average_Score'
            ],
            ascending=[
                False,
                False
            ]
        )
    )

    area_summary_display = (
        area_summary.rename(
            columns={
                'Location_Score':
                    'Location Score',

                'Average_Score':
                    'Average Score',

                'Best_Score':
                    'Best Score'
            }
        )
    )

    st.dataframe(
        area_summary_display,
        use_container_width=True,
        hide_index=True,
        column_config={
            'MW':
                st.column_config.NumberColumn(
                    'MW',
                    format='%.0f'
                ),

            'Location Score':
                st.column_config.ProgressColumn(
                    'Location Score',
                    min_value=0,
                    max_value=100,
                    format='%.0f'
                ),

            'Average Score':
                st.column_config.NumberColumn(
                    'Average Score',
                    format='%.1f'
                ),

            'Best Score':
                st.column_config.NumberColumn(
                    'Best Score',
                    format='%.1f'
                )
        }
    )

    st.divider()

    st.subheader(
        '📦 Bundle Opportunities'
    )

    st.caption(
        'Owners with at least two 50–60 MW '
        'projects. Bundles are ranked by '
        'average Opportunity Score.'
    )

    bundle_candidates = (
        df[
            df[
                'Capacity (MW)'
            ].between(
                50,
                60,
                inclusive='both'
            )
        ]
        .copy()
    )

    bundle_summary = (
        bundle_candidates
        .groupby(
            'Owner',
            as_index=False
        )
        .agg(
            Bundle_Projects=(
                'Power Project Name',
                'count'
            ),

            Bundle_MW=(
                'Capacity (MW)',
                'sum'
            ),

            Average_Score=(
                'Opportunity Score',
                'mean'
            ),

            Best_Score=(
                'Opportunity Score',
                'max'
            )
        )
    )

    bundle_summary = (
        bundle_summary[
            bundle_summary[
                'Bundle_Projects'
            ]
            >= 2
        ]
        .copy()
    )

    bundle_summary = (
        bundle_summary
        .sort_values(
            by=[
                'Average_Score',
                'Best_Score',
                'Bundle_MW'
            ],
            ascending=[
                False,
                False,
                False
            ]
        )
        .reset_index(
            drop=True
        )
    )

    bundle_summary.insert(
        0,
        'Bundle Rank',
        np.arange(
            1,
            len(
                bundle_summary
            ) + 1
        )
    )

    if bundle_summary.empty:

        st.info(
            'No owners currently have '
            'multiple 50–60 MW projects.'
        )

    else:

        bundle_summary_display = (
            bundle_summary.rename(
                columns={
                    'Bundle_Projects':
                        'Projects',

                    'Bundle_MW':
                        'Total MW',

                    'Average_Score':
                        'Average Score',

                    'Best_Score':
                        'Best Score'
                }
            )
        )

        st.dataframe(
            bundle_summary_display,
            use_container_width=True,
            hide_index=True,
            column_config={
                'Bundle Rank':
                    st.column_config.NumberColumn(
                        'Rank'
                    ),

                'Average Score':
                    st.column_config.ProgressColumn(
                        'Average Score',
                        min_value=0,
                        max_value=100,
                        format='%.1f'
                    ),

                'Best Score':
                    st.column_config.ProgressColumn(
                        'Best Score',
                        min_value=0,
                        max_value=100,
                        format='%.1f'
                    ),

                'Total MW':
                    st.column_config.NumberColumn(
                        'Total MW',
                        format='%.1f MW'
                    )
            }
        )

        for _, bundle in bundle_summary.iterrows():

            bundle_owner = bundle[
                'Owner'
            ]

            bundle_rank = int(
                bundle[
                    'Bundle Rank'
                ]
            )

            bundle_count = int(
                bundle[
                    'Bundle_Projects'
                ]
            )

            bundle_mw = bundle[
                'Bundle_MW'
            ]

            bundle_avg = bundle[
                'Average_Score'
            ]

            owner_projects = (
                bundle_candidates[
                    bundle_candidates[
                        'Owner'
                    ]
                    == bundle_owner
                ]
                .sort_values(
                    'Opportunity Score',
                    ascending=False
                )
            )

            with st.expander(
                f'#{bundle_rank} 📦 '
                f'{bundle_owner} — '
                f'{bundle_count} projects | '
                f'{bundle_mw:,.1f} MW | '
                f'Avg Score {bundle_avg:.1f}'
            ):

                bundle_columns = [
                    'Power Project Name',
                    'ERCOT Area',
                    'ISO Zone',
                    'Location Score',
                    'Capacity (MW)',
                    'Power Project Type',
                    'Power Project Status',
                    'First Power Date',
                    'Queue ID',
                    'Contract Type',
                    'Contract Offtaker',
                    'Distress Score',
                    'Development Stage',
                    'Revenue Visibility',
                    'Market / Revenue',
                    'Acquisition Value',
                    'Executability',
                    'Opportunity Score',
                    'Action'
                ]

                bundle_columns = [
                    col
                    for col
                    in bundle_columns
                    if col
                    in owner_projects.columns
                ]

                st.dataframe(
                    owner_projects[
                        bundle_columns
                    ],
                    use_container_width=True,
                    hide_index=True
                )

    st.divider()

    st.subheader(
        '🔎 Score Breakdown'
    )

    if len(
        filtered
    ) > 0:

        selected_project = (
            st.selectbox(
                'Select a Project',
                filtered[
                    'Power Project Name'
                ].tolist(),
                key=
                    'score_breakdown_project'
            )
        )

        project = (
            filtered[
                filtered[
                    'Power Project Name'
                ]
                == selected_project
            ]
            .iloc[0]
        )

        (
            p1,
            p2,
            p3,
            p4,
            p5
        ) = st.columns(
            5
        )

        p1.metric(
            'ERCOT Area',
            project[
                'ERCOT Area'
            ]
        )

        p2.metric(
            'Location Score',
            f"{project['Location Score']:.0f}"
        )

        p3.metric(
            'COD',
            format_date(
                project.get(
                    'First Power Date'
                )
            )
        )

        p4.metric(
            'Capacity',
            f"{project['Capacity (MW)']:,.1f} MW"
        )

        p5.metric(
            'Status',
            clean_text(
                project.get(
                    'Power Project Status'
                )
            )
        )

        st.caption(
            f"ISO Zone: "
            f"{clean_text(project.get('ISO Zone'))}"
        )

        if has_value(
            project.get(
                'Point of Interconnection'
            )
        ):

            st.caption(
                f"Point of Interconnection: "
                f"{project['Point of Interconnection']}"
            )

        st.markdown(
            '#### Market / Revenue'
        )

        (
            m1,
            m2,
            m3
        ) = st.columns(
            3
        )

        m1.metric(
            'Revenue Visibility',
            f"{project['Revenue Visibility']:.1f}"
        )

        m2.metric(
            'Location Score',
            f"{project['Location Score']:.1f}"
        )

        m3.metric(
            'Market / Revenue Score',
            f"{project['Market / Revenue']:.1f}"
        )

        st.caption(
            f"Market / Revenue = "
            f"{project['Revenue Visibility']:.1f} × "
            f"{revenue_visibility_weight:.0%} "
            f"+ {project['Location Score']:.1f} × "
            f"{location_market_weight:.0%} "
            f"= {project['Market / Revenue']:.1f}"
        )

        st.markdown(
            '#### Opportunity Score'
        )

        (
            s1,
            s2,
            s3,
            s4,
            s5
        ) = st.columns(
            5
        )

        s1.metric(
            'Seller Motivation',
            f"{project['Distress Score']:.1f}"
        )

        s2.metric(
            'Development Stage',
            f"{project['Development Stage']:.1f}"
        )

        s3.metric(
            'Market / Revenue',
            f"{project['Market / Revenue']:.1f}"
        )

        s4.metric(
            'Acquisition Value',
            f"{project['Acquisition Value']:.1f}"
        )

        s5.metric(
            'Executability',
            f"{project['Executability']:.1f}"
        )

        st.metric(
            'Total Opportunity Score',
            f"{project['Opportunity Score']:.2f}"
        )

        st.markdown(
            '#### Executability Detail'
        )

        (
            e1,
            e2,
            e3,
            e4
        ) = st.columns(
            4
        )

        e1.metric(
            'Seller Actionability',
            f"{project['Actionability Score']:.1f}"
        )

        e2.metric(
            'Timing Score',
            f"{project['Timing Score']:.1f}"
        )

        e3.metric(
            'Development Stage',
            f"{project['Development Stage']:.1f}"
        )

        e4.metric(
            'Executability',
            f"{project['Executability']:.1f}"
        )

        st.caption(
            f"Executability = "
            f"{project['Actionability Score']:.1f} × "
            f"{actionability_weight:.0%} "
            f"+ {project['Timing Score']:.1f} × "
            f"{timing_exec_weight:.0%} "
            f"+ {project['Development Stage']:.1f} × "
            f"{development_exec_weight:.0%} "
            f"= {project['Executability']:.1f}"
        )

        st.markdown(
            '#### Tax Credit Review'
        )

        (
            tax1,
            tax2,
            tax3
        ) = st.columns(
            3
        )

        tax1.metric(
            'PTC / ITC',
            clean_text(
                project.get(
                    'PTC/ITC'
                )
            )
            or 'Not Identified'
        )

        tax2.metric(
            'Energy Community Screen',
            project[
                'Energy Community'
            ]
        )

        tax3.metric(
            'Domestic Content',
            project[
                'Domestic Content Review'
            ]
        )

        st.caption(
            'Domestic Content is not automatically '
            'scored. Orennia does not currently '
            'provide a native project-level Domestic '
            'Content qualification field, so '
            'qualification requires project-specific '
            'diligence.'
        )

        if available_diligence_columns:

            with st.expander(
                '🏗️ Equipment / EPC Diligence',
                expanded=False
            ):

                diligence_data = {
                    col:
                        clean_text(
                            project.get(
                                col
                            )
                        )
                        or 'N/A'
                    for col
                    in available_diligence_columns
                }

                diligence_df = (
                    pd.DataFrame(
                        {
                            'Field':
                                list(
                                    diligence_data.keys()
                                ),

                            'Value':
                                list(
                                    diligence_data.values()
                                )
                        }
                    )
                )

                st.dataframe(
                    diligence_df,
                    use_container_width=True,
                    hide_index=True
                )

                st.caption(
                    'Equipment manufacturer, model, '
                    'EPC and integrator data may help '
                    'prioritize Domestic Content diligence '
                    'but are not treated as proof of '
                    'Domestic Content qualification.'
                )

        if available_interconnection_columns:

            with st.expander(
                '🔌 Interconnection Snapshot',
                expanded=False
            ):

                ix_fields = [
                    'Queue ID',
                    'Point of Interconnection',
                    *available_interconnection_columns
                ]

                ix_fields = [
                    col
                    for col
                    in ix_fields
                    if col
                    in project.index
                ]

                ix_data = {
                    col:
                        clean_text(
                            project.get(
                                col
                            )
                        )
                        or 'N/A'
                    for col
                    in ix_fields
                }

                st.dataframe(
                    pd.DataFrame(
                        {
                            'Field':
                                list(
                                    ix_data.keys()
                                ),

                            'Value':
                                list(
                                    ix_data.values()
                                )
                        }
                    ),
                    use_container_width=True,
                    hide_index=True
                )

        st.markdown(
            '#### Management Readout'
        )

        (
            r1,
            r2
        ) = st.columns(
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

    st.divider()

    st.subheader(
        'Owner Opportunity Summary'
    )

    owner_summary = (
        df.groupby(
            'Owner',
            as_index=False
        )
        .agg(
            Projects=(
                'Power Project Name',
                'count'
            ),

            MW=(
                'Capacity (MW)',
                'sum'
            ),

            Average_Score=(
                'Opportunity Score',
                'mean'
            ),

            Best_Score=(
                'Opportunity Score',
                'max'
            )
        )
    )

    owner_summary = (
        owner_summary
        .sort_values(
            by=[
                'Best_Score',
                'Average_Score'
            ],
            ascending=[
                False,
                False
            ]
        )
    )

    owner_summary_display = (
        owner_summary.rename(
            columns={
                'Average_Score':
                    'Average Score',

                'Best_Score':
                    'Best Score'
            }
        )
    )

    st.dataframe(
        owner_summary_display.head(
            25
        ),
        use_container_width=True,
        hide_index=True,
        column_config={
            'Average Score':
                st.column_config.NumberColumn(
                    'Average Score',
                    format='%.1f'
                ),

            'Best Score':
                st.column_config.ProgressColumn(
                    'Best Score',
                    min_value=0,
                    max_value=100,
                    format='%.1f'
                )
        }
    )

    st.divider()

    csv = (
        df.to_csv(
            index=False
        )
        .encode(
            'utf-8'
        )
    )

    st.download_button(
        '⬇️ Download Scored ERCOT Universe',
        data=csv,
        file_name=
            'ERCOT_Scored_Acquisition_Universe.csv',
        mime='text/csv'
    )


with competitor_tab:

    st.markdown(
        '## 🎯 ERCOT Competitor Due Diligence'
    )

    st.caption(
        'Project Orbit competitive screen using '
        'the current Orennia project universe. '
        'The default competitor definition is '
        '**Storage / BESS in ERCOT South with '
        '250–700 MW of capacity**, inclusive. '
        'Project Orbit and its prior Gunsight name '
        'are treated as the reference project and '
        'are excluded from the competitor list.'
    )

    st.info(
        'This tab is a competitive-landscape screen, '
        'not an acquisition ranking. It intentionally '
        'uses the full cleaned Orennia universe before '
        "the main dashboard's acquisition exclusions "
        'are applied.'
    )

    ORBIT_PROJECT_ALIASES = [
        'orbit',
        'gunsight'
    ]

    def _orbit_name_mask(
        frame
    ):

        project_names = (
            frame[
                'Power Project Name'
            ]
            .fillna(
                ''
            )
            .astype(
                str
            )
            .str.lower()
        )

        mask = pd.Series(
            False,
            index=frame.index
        )

        for alias in ORBIT_PROJECT_ALIASES:

            mask = (
                mask
                |
                project_names.str.contains(
                    alias,
                    regex=False,
                    na=False
                )
            )

        return mask

    orbit_reference_candidates = (
        competitor_source[
            _orbit_name_mask(
                competitor_source
            )
        ].copy()
    )

    if not orbit_reference_candidates.empty:

        orbit_reference_candidates = (
            orbit_reference_candidates
            .sort_values(
                by=[
                    'Capacity (MW)',
                    'First Power Date'
                ],
                ascending=[
                    False,
                    True
                ],
                na_position='last'
            )
        )

        orbit_reference_labels = (
            orbit_reference_candidates
            .apply(
                lambda row:
                    f"{clean_text(row.get('Power Project Name'))} — "
                    f"{clean_text(row.get('Owner')) or 'Unknown Owner'} — "
                    f"{row.get('Capacity (MW)', np.nan):,.1f} MW",
                axis=1
            )
            .tolist()
        )

        orbit_reference_label = (
            st.selectbox(
                'Project Orbit reference',
                options=
                    orbit_reference_labels,
                index=0,
                key=
                    'orbit_competitor_reference'
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

        (
            o1,
            o2,
            o3,
            o4,
            o5
        ) = st.columns(
            5
        )

        o1.metric(
            'Orbit Reference',
            clean_text(
                orbit_reference.get(
                    'Power Project Name'
                )
            )
            or 'N/A'
        )

        o2.metric(
            'Capacity',
            (
                f"{orbit_reference['Capacity (MW)']:,.0f} MW"
                if pd.notna(
                    orbit_reference.get(
                        'Capacity (MW)'
                    )
                )
                else 'N/A'
            )
        )

        o3.metric(
            'Status',
            clean_text(
                orbit_reference.get(
                    'Power Project Status'
                )
            )
            or 'N/A'
        )

        o4.metric(
            'COD',
            format_date(
                orbit_reference.get(
                    'First Power Date'
                )
            )
        )

        o5.metric(
            'County',
            clean_text(
                orbit_reference.get(
                    'County'
                )
            )
            or 'N/A'
        )

    else:

        orbit_reference = None

        st.caption(
            "No project with 'Orbit' or "
            "'Gunsight' in the Orennia project "
            'name was found. The competitor '
            'universe below still works normally.'
        )

    competitor_base = (
        competitor_source[
            (
                competitor_source[
                    'ERCOT Area'
                ]
                == 'ERCOT-S'
            )
            &
            (
                competitor_source[
                    'Power Project Type'
                ]
                == 'Storage'
            )
            &
            (
                competitor_source[
                    'Capacity (MW)'
                ].between(
                    250,
                    700,
                    inclusive='both'
                )
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
            'No ERCOT South storage projects '
            'between 250 MW and 700 MW were '
            'found in the active Orennia file.'
        )

    else:

        st.markdown(
            '### Competitor Universe'
        )

        (
            filter_1,
            filter_2,
            filter_3,
            filter_4
        ) = st.columns(
            [
                1.15,
                1.25,
                1.10,
                1
            ]
        )

        competitor_status_options = sorted(
            [
                value
                for value
                in competitor_base[
                    'Power Project Status'
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
                    'Project Status',
                    options=
                        competitor_status_options,
                    default=
                        competitor_status_options,
                    key=
                        'orbit_competitor_status_filter'
                )
            )

        competitor_owner_options = sorted(
            [
                value
                for value
                in competitor_base[
                    'Owner'
                ]
                .fillna(
                    ''
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
                    'Owner / Developer',
                    options=
                        competitor_owner_options,
                    default=[],
                    placeholder=
                        'All owners',
                    key=
                        'orbit_competitor_owner_filter'
                )
            )

        competitor_county_options = (
            sorted(
                [
                    value
                    for value
                    in competitor_base[
                        'County'
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
            if 'County'
            in competitor_base.columns
            else []
        )

        with filter_3:

            competitor_county_filter = (
                st.multiselect(
                    'County',
                    options=
                        competitor_county_options,
                    default=[],
                    placeholder=
                        'All counties',
                    key=
                        'orbit_competitor_county_filter',
                    disabled=
                        (
                            len(
                                competitor_county_options
                            )
                            == 0
                        )
                )
            )

        with filter_4:

            competitor_capacity_range = (
                st.slider(
                    'Capacity Range (MW)',
                    min_value=250,
                    max_value=700,
                    value=(
                        250,
                        700
                    ),
                    step=25,
                    key=
                        'orbit_competitor_capacity_range'
                )
            )

        competitor_view = (
            competitor_base.copy()
        )

        if competitor_status_filter:

            competitor_view = (
                competitor_view[
                    competitor_view[
                        'Power Project Status'
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
                        'Owner'
                    ].isin(
                        competitor_owner_filter
                    )
                ]
            )

        if (
            competitor_county_filter
            and 'County'
            in competitor_view.columns
        ):

            competitor_view = (
                competitor_view[
                    competitor_view[
                        'County'
                    ]
                    .astype(
                        str
                    )
                    .isin(
                        competitor_county_filter
                    )
                ]
            )

        competitor_view = (
            competitor_view[
                competitor_view[
                    'Capacity (MW)'
                ].between(
                    competitor_capacity_range[0],
                    competitor_capacity_range[1],
                    inclusive='both'
                )
            ]
            .copy()
        )

        orbit_capacity = np.nan

        if orbit_reference is not None:

            orbit_capacity = (
                pd.to_numeric(
                    pd.Series(
                        [
                            orbit_reference.get(
                                'Capacity (MW)'
                            )
                        ]
                    ),
                    errors='coerce'
                )
                .iloc[0]
            )

        if pd.notna(
            orbit_capacity
        ):

            competitor_view[
                'MW Delta vs Orbit'
            ] = (
                competitor_view[
                    'Capacity (MW)'
                ]
                - orbit_capacity
            )

            competitor_view[
                'Absolute MW Delta vs Orbit'
            ] = (
                competitor_view[
                    'MW Delta vs Orbit'
                ].abs()
            )

            competitor_view = (
                competitor_view
                .sort_values(
                    by=[
                        'Absolute MW Delta vs Orbit',
                        'First Power Date',
                        'Capacity (MW)'
                    ],
                    ascending=[
                        True,
                        True,
                        False
                    ],
                    na_position='last'
                )
            )

        else:

            competitor_view = (
                competitor_view
                .sort_values(
                    by=[
                        'Capacity (MW)',
                        'First Power Date'
                    ],
                    ascending=[
                        False,
                        True
                    ],
                    na_position='last'
                )
            )

        (
            c1,
            c2,
            c3,
            c4,
            c5
        ) = st.columns(
            5
        )

        c1.metric(
            'Competitor Projects',
            f'{len(competitor_view):,}'
        )

        c2.metric(
            'Competitor Capacity',
            f"{competitor_view['Capacity (MW)'].sum():,.0f} MW"
        )

        c3.metric(
            'Average Project Size',
            (
                f"{competitor_view['Capacity (MW)'].mean():,.0f} MW"
                if not competitor_view.empty
                else 'N/A'
            )
        )

        c4.metric(
            'Owners / Developers',
            f"{competitor_view['Owner'].replace('', np.nan).nunique():,}"
        )

        advanced_competitor_count = int(
            competitor_view[
                'Power Project Status'
            ].isin(
                [
                    'Operating',
                    'In Construction',
                    'IA Executed'
                ]
            ).sum()
        )

        c5.metric(
            'Operating / Advanced',
            f'{advanced_competitor_count:,}'
        )

        st.caption(
            f'Active source: '
            f'**{active_data_source}** | '
            'Fixed market: **ERCOT-S** | '
            'Technology: **Storage** | '
            'Base size screen: **250–700 MW**.'
        )

        if competitor_view.empty:

            st.warning(
                'No competitors match the '
                'current tab filters.'
            )

        else:

            st.divider()

            st.markdown(
                '### Competitor Map'
            )

            st.caption(
                'Blue markers are ERCOT South BESS '
                'competitors in the selected size range. '
                'The orange marker is Project Orbit / '
                'Gunsight when a matching Orennia row '
                'with valid coordinates is available.'
            )

            competitor_lat_col = (
                'Latitude (Degrees)'
                if 'Latitude (Degrees)'
                in competitor_view.columns
                else None
            )

            competitor_lon_col = (
                'Longitude (Degrees)'
                if 'Longitude (Degrees)'
                in competitor_view.columns
                else None
            )

            if (
                competitor_lat_col is None
                or competitor_lon_col is None
            ):

                st.info(
                    'The active Orennia file does not '
                    'include latitude / longitude fields, '
                    'so the competitor list is available '
                    'but the map cannot be rendered.'
                )

            else:

                competitor_map = (
                    competitor_view.copy()
                )

                competitor_map[
                    'lat'
                ] = pd.to_numeric(
                    competitor_map[
                        competitor_lat_col
                    ],
                    errors='coerce'
                )

                competitor_map[
                    'lon'
                ] = pd.to_numeric(
                    competitor_map[
                        competitor_lon_col
                    ],
                    errors='coerce'
                )

                competitor_map = (
                    competitor_map[
                        competitor_map[
                            'lat'
                        ].between(
                            24.0,
                            37.5,
                            inclusive='both'
                        )
                        &
                        competitor_map[
                            'lon'
                        ].between(
                            -107.5,
                            -92.0,
                            inclusive='both'
                        )
                    ]
                    .copy()
                )

                competitor_map[
                    'Project'
                ] = (
                    competitor_map[
                        'Power Project Name'
                    ]
                    .fillna(
                        ''
                    )
                    .astype(
                        str
                    )
                )

                competitor_map[
                    'Owner Display'
                ] = (
                    competitor_map[
                        'Owner'
                    ]
                    .replace(
                        '',
                        np.nan
                    )
                    .fillna(
                        'N/A'
                    )
                )

                competitor_map[
                    'Capacity Display'
                ] = (
                    competitor_map[
                        'Capacity (MW)'
                    ]
                    .apply(
                        lambda value:
                            f'{value:,.0f} MW'
                            if pd.notna(
                                value
                            )
                            else 'N/A'
                    )
                )

                competitor_map[
                    'Status Display'
                ] = (
                    competitor_map[
                        'Power Project Status'
                    ]
                    .fillna(
                        'N/A'
                    )
                    .astype(
                        str
                    )
                )

                competitor_map[
                    'Detailed Status Display'
                ] = (
                    competitor_map[
                        'Detailed Status'
                    ]
                    .fillna(
                        'N/A'
                    )
                    .astype(
                        str
                    )
                    if 'Detailed Status'
                    in competitor_map.columns
                    else 'N/A'
                )

                competitor_map[
                    'County Display'
                ] = (
                    competitor_map[
                        'County'
                    ]
                    .fillna(
                        'N/A'
                    )
                    .astype(
                        str
                    )
                    if 'County'
                    in competitor_map.columns
                    else 'N/A'
                )

                competitor_map[
                    'POI Display'
                ] = (
                    competitor_map[
                        'Point of Interconnection'
                    ]
                    .fillna(
                        'N/A'
                    )
                    .astype(
                        str
                    )
                    if 'Point of Interconnection'
                    in competitor_map.columns
                    else 'N/A'
                )

                competitor_map[
                    'Queue Display'
                ] = (
                    competitor_map[
                        'Queue ID'
                    ]
                    .fillna(
                        'N/A'
                    )
                    .astype(
                        str
                    )
                )

                competitor_map[
                    'COD Display'
                ] = (
                    competitor_map[
                        'First Power Date'
                    ]
                    .apply(
                        format_date
                    )
                )

                competitor_map[
                    'Marker Type'
                ] = 'Competitor'

                competitor_map[
                    'Map Radius'
                ] = (
                    competitor_map[
                        'Capacity (MW)'
                    ]
                    .fillna(
                        250
                    )
                    .clip(
                        lower=250,
                        upper=700
                    )
                    * 60
                )

                competitor_layers = []

                if not competitor_map.empty:

                    competitor_layers.append(
                        pdk.Layer(
                            'ScatterplotLayer',
                            data=
                                competitor_map,
                            id=
                                'orbit_competitors',
                            get_position=
                                '[lon, lat]',
                            get_radius=
                                'Map Radius',
                            get_fill_color=[
                                38,
                                132,
                                255,
                                210
                            ],
                            get_line_color=[
                                255,
                                255,
                                255,
                                235
                            ],
                            radius_min_pixels=7,
                            radius_max_pixels=20,
                            line_width_min_pixels=1,
                            pickable=True,
                            auto_highlight=True,
                            stroked=True,
                            filled=True
                        )
                    )

                orbit_map = pd.DataFrame()

                if orbit_reference is not None:

                    orbit_lat = (
                        pd.to_numeric(
                            pd.Series(
                                [
                                    orbit_reference.get(
                                        competitor_lat_col
                                    )
                                ]
                            ),
                            errors='coerce'
                        )
                        .iloc[0]
                    )

                    orbit_lon = (
                        pd.to_numeric(
                            pd.Series(
                                [
                                    orbit_reference.get(
                                        competitor_lon_col
                                    )
                                ]
                            ),
                            errors='coerce'
                        )
                        .iloc[0]
                    )

                    if (
                        pd.notna(
                            orbit_lat
                        )
                        and pd.notna(
                            orbit_lon
                        )
                        and (
                            24.0
                            <= orbit_lat
                            <= 37.5
                        )
                        and (
                            -107.5
                            <= orbit_lon
                            <= -92.0
                        )
                    ):

                        orbit_map = pd.DataFrame(
                            [
                                {
                                    'lat':
                                        float(
                                            orbit_lat
                                        ),

                                    'lon':
                                        float(
                                            orbit_lon
                                        ),

                                    'Project':
                                        clean_text(
                                            orbit_reference.get(
                                                'Power Project Name'
                                            )
                                        )
                                        or 'Project Orbit',

                                    'Owner Display':
                                        clean_text(
                                            orbit_reference.get(
                                                'Owner'
                                            )
                                        )
                                        or 'N/A',

                                    'Capacity Display':
                                        (
                                            f"{orbit_reference.get('Capacity (MW)'):,.0f} MW"
                                            if pd.notna(
                                                orbit_reference.get(
                                                    'Capacity (MW)'
                                                )
                                            )
                                            else 'N/A'
                                        ),

                                    'Status Display':
                                        clean_text(
                                            orbit_reference.get(
                                                'Power Project Status'
                                            )
                                        )
                                        or 'N/A',

                                    'Detailed Status Display':
                                        clean_text(
                                            orbit_reference.get(
                                                'Detailed Status'
                                            )
                                        )
                                        or 'N/A',

                                    'County Display':
                                        clean_text(
                                            orbit_reference.get(
                                                'County'
                                            )
                                        )
                                        or 'N/A',

                                    'POI Display':
                                        clean_text(
                                            orbit_reference.get(
                                                'Point of Interconnection'
                                            )
                                        )
                                        or 'N/A',

                                    'Queue Display':
                                        clean_text(
                                            orbit_reference.get(
                                                'Queue ID'
                                            )
                                        )
                                        or 'N/A',

                                    'COD Display':
                                        format_date(
                                            orbit_reference.get(
                                                'First Power Date'
                                            )
                                        ),

                                    'Marker Type':
                                        'Project Orbit',

                                    'Map Radius':
                                        42000
                                }
                            ]
                        )

                        competitor_layers.append(
                            pdk.Layer(
                                'ScatterplotLayer',
                                data=
                                    orbit_map,
                                id=
                                    'project_orbit_reference',
                                get_position=
                                    '[lon, lat]',
                                get_radius=
                                    'Map Radius',
                                get_fill_color=[
                                    245,
                                    166,
                                    35,
                                    240
                                ],
                                get_line_color=[
                                    20,
                                    20,
                                    20,
                                    255
                                ],
                                radius_min_pixels=13,
                                radius_max_pixels=26,
                                line_width_min_pixels=3,
                                pickable=True,
                                auto_highlight=True,
                                stroked=True,
                                filled=True
                            )
                        )

                map_frames = [
                    frame[
                        [
                            'lat',
                            'lon'
                        ]
                    ]
                    for frame
                    in [
                        competitor_map,
                        orbit_map
                    ]
                    if not frame.empty
                ]

                if not map_frames:

                    st.info(
                        'No competitors in the current '
                        'filtered view have usable '
                        'coordinates for mapping.'
                    )

                else:

                    combined_map_points = (
                        pd.concat(
                            map_frames,
                            ignore_index=True
                        )
                    )

                    competitor_map_lat = float(
                        combined_map_points[
                            'lat'
                        ].mean()
                    )

                    competitor_map_lon = float(
                        combined_map_points[
                            'lon'
                        ].mean()
                    )

                    lat_span = float(
                        combined_map_points[
                            'lat'
                        ].max()
                        -
                        combined_map_points[
                            'lat'
                        ].min()
                    )

                    lon_span = float(
                        combined_map_points[
                            'lon'
                        ].max()
                        -
                        combined_map_points[
                            'lon'
                        ].min()
                    )

                    max_span = max(
                        lat_span,
                        lon_span
                    )

                    if max_span > 5:

                        competitor_map_zoom = 5.0

                    elif max_span > 3:

                        competitor_map_zoom = 5.6

                    elif max_span > 1.5:

                        competitor_map_zoom = 6.2

                    elif max_span > 0.75:

                        competitor_map_zoom = 7.0

                    else:

                        competitor_map_zoom = 8.0

                    competitor_deck = (
                        pdk.Deck(
                            map_style=(
                                'https://basemaps.cartocdn.com/'
                                'gl/positron-gl-style/style.json'
                            ),
                            initial_view_state=
                                pdk.ViewState(
                                    latitude=
                                        competitor_map_lat,
                                    longitude=
                                        competitor_map_lon,
                                    zoom=
                                        competitor_map_zoom,
                                    pitch=0
                                ),
                            layers=
                                competitor_layers,
                            tooltip={
                                'html':
                                    '<b>{Project}</b><br/>'
                                    'Type: {Marker Type}<br/>'
                                    'Owner: {Owner Display}<br/>'
                                    'Capacity: {Capacity Display}<br/>'
                                    'Status: {Status Display}<br/>'
                                    'Detailed Status: {Detailed Status Display}<br/>'
                                    'County: {County Display}<br/>'
                                    'POI: {POI Display}<br/>'
                                    'Queue ID: {Queue Display}<br/>'
                                    'COD: {COD Display}',

                                'style': {
                                    'backgroundColor':
                                        'rgba(20,20,20,0.92)',

                                    'color':
                                        'white'
                                }
                            }
                        )
                    )

                    st.pydeck_chart(
                        competitor_deck,
                        use_container_width=True,
                        height=650
                    )

                    st.caption(
                        f'Mapped competitors: '
                        f'{len(competitor_map):,} '
                        f'of {len(competitor_view):,}. '
                        'Projects without usable '
                        'coordinates remain in the '
                        'downloadable competitor list.'
                    )

            st.divider()

            st.markdown(
                '### Owner / Developer Concentration'
            )

            competitor_owner_summary = (
                competitor_view
                .groupby(
                    'Owner',
                    as_index=False
                )
                .agg(
                    Projects=(
                        'Power Project Name',
                        'count'
                    ),

                    Total_MW=(
                        'Capacity (MW)',
                        'sum'
                    ),

                    Average_MW=(
                        'Capacity (MW)',
                        'mean'
                    ),

                    Earliest_COD=(
                        'First Power Date',
                        'min'
                    )
                )
                .sort_values(
                    by=[
                        'Total_MW',
                        'Projects'
                    ],
                    ascending=[
                        False,
                        False
                    ]
                )
                .reset_index(
                    drop=True
                )
            )

            competitor_owner_summary = (
                competitor_owner_summary.rename(
                    columns={
                        'Total_MW':
                            'Total MW',

                        'Average_MW':
                            'Average MW',

                        'Earliest_COD':
                            'Earliest COD'
                    }
                )
            )

            st.dataframe(
                competitor_owner_summary,
                use_container_width=True,
                hide_index=True,
                column_config={
                    'Total MW':
                        st.column_config.NumberColumn(
                            'Total MW',
                            format='%.0f'
                        ),

                    'Average MW':
                        st.column_config.NumberColumn(
                            'Average MW',
                            format='%.0f'
                        ),

                    'Earliest COD':
                        st.column_config.DateColumn(
                            'Earliest COD'
                        )
                }
            )

            st.divider()

            st.markdown(
                '### ERCOT South Competitor List'
            )

            competitor_list_columns = [
                'Power Project Name',
                'Owner',
                'Power Project Type',
                'Capacity (MW)',
                'MW Delta vs Orbit',
                'Power Project Status',
                'Detailed Status',
                'First Power Date',
                'County',
                'Queue ID',
                'Point of Interconnection',
                'ISO Zone',
                'Interconnection Service Type',
                'Queue Cycle',
                'Queue Date',
                'Interconnection Cost Physical ($)',
                'Interconnection Cost System Upgrade ($)',
                'Interconnection Cost Total ($)',
                'Contract Type',
                'Contract Offtaker',
                'Contract Execution Date',
                'Contract Termination Date',
                'Contract Term Years (Year)',
                'PTC/ITC',
                'Equipment Manufacturer',
                'Equipment Model',
                'EPC',
                'Integrator',
                'Latitude (Degrees)',
                'Longitude (Degrees)'
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
                ].copy()
            )

            competitor_list.insert(
                0,
                'Competitor Rank',
                np.arange(
                    1,
                    len(
                        competitor_list
                    ) + 1
                )
            )

            st.dataframe(
                competitor_list,
                use_container_width=True,
                hide_index=True,
                column_config={
                    'Capacity (MW)':
                        st.column_config.NumberColumn(
                            'Capacity (MW)',
                            format='%.0f'
                        ),

                    'MW Delta vs Orbit':
                        st.column_config.NumberColumn(
                            'MW Delta vs Orbit',
                            format='%+.0f'
                        ),

                    'First Power Date':
                        st.column_config.DateColumn(
                            'COD'
                        ),

                    'Queue Date':
                        st.column_config.DateColumn(
                            'Queue Date'
                        ),

                    'Contract Execution Date':
                        st.column_config.DateColumn(
                            'Contract Execution Date'
                        ),

                    'Contract Termination Date':
                        st.column_config.DateColumn(
                            'Contract Termination Date'
                        )
                }
            )

            competitor_csv = (
                competitor_list
                .to_csv(
                    index=False
                )
                .encode(
                    'utf-8'
                )
            )

            st.download_button(
                '⬇️ Download ERCOT South Orbit Competitor List',
                data=
                    competitor_csv,
                file_name=
                    'ERCOT_South_Orbit_Competitors_250_to_700MW.csv',
                mime=
                    'text/csv',
                key=
                    'download_orbit_competitor_list'
            )

            st.divider()

            st.markdown(
                '### Competitor Project Drill-Down'
            )

            competitor_drill_labels = (
                competitor_view
                .apply(
                    lambda row:
                        f"{clean_text(row.get('Power Project Name'))} — "
                        f"{clean_text(row.get('Owner')) or 'Unknown Owner'} — "
                        f"{row.get('Capacity (MW)', np.nan):,.0f} MW",
                    axis=1
                )
                .tolist()
            )

            competitor_drill_label = (
                st.selectbox(
                    'Select competitor',
                    options=
                        competitor_drill_labels,
                    key=
                        'orbit_competitor_drilldown'
                )
            )

            competitor_drill = (
                competitor_view
                .iloc[
                    competitor_drill_labels.index(
                        competitor_drill_label
                    )
                ]
            )

            (
                d1,
                d2,
                d3,
                d4,
                d5
            ) = st.columns(
                5
            )

            d1.metric(
                'Capacity',
                f"{competitor_drill['Capacity (MW)']:,.0f} MW"
            )

            d2.metric(
                'Status',
                clean_text(
                    competitor_drill.get(
                        'Power Project Status'
                    )
                )
                or 'N/A'
            )

            d3.metric(
                'COD',
                format_date(
                    competitor_drill.get(
                        'First Power Date'
                    )
                )
            )

            d4.metric(
                'County',
                clean_text(
                    competitor_drill.get(
                        'County'
                    )
                )
                or 'N/A'
            )

            d5.metric(
                'Queue ID',
                clean_text(
                    competitor_drill.get(
                        'Queue ID'
                    )
                )
                or 'N/A'
            )

            competitor_detail_fields = [
                'Power Project Name',
                'Generator Name',
                'Generator ID',
                'Owner',
                'Power Project Type',
                'Capacity (MW)',
                'Power Project Status',
                'Detailed Status',
                'First Power Date',
                'ERCOT Area',
                'ISO Zone',
                'County',
                'Queue ID',
                'Point of Interconnection',
                'Interconnection Service Type',
                'Queue Cycle',
                'Queue Date',
                'Interconnection Cost Physical ($)',
                'Interconnection Cost System Upgrade ($)',
                'Interconnection Cost Total ($)',
                'Contract Type',
                'Contract Offtaker',
                'Contract Execution Date',
                'Contract Termination Date',
                'Contract Term Years (Year)',
                'PTC/ITC',
                'Equipment Manufacturer',
                'Equipment Model',
                'EPC',
                'Integrator',
                'Latitude (Degrees)',
                'Longitude (Degrees)'
            ]

            competitor_detail_rows = []

            for field in competitor_detail_fields:

                if field not in competitor_drill.index:

                    continue

                value = competitor_drill.get(
                    field
                )

                if field in [
                    'First Power Date',
                    'Queue Date',
                    'Contract Execution Date',
                    'Contract Termination Date'
                ]:

                    display_value = format_date(
                        value
                    )

                elif pd.isna(
                    value
                ):

                    display_value = 'N/A'

                else:

                    display_value = str(
                        value
                    )

                competitor_detail_rows.append(
                    {
                        'Field':
                            field,

                        'Value':
                            display_value
                    }
                )

            st.dataframe(
                pd.DataFrame(
                    competitor_detail_rows
                ),
                use_container_width=True,
                hide_index=True
            )


with map_tab:

    st.markdown(
        '## 🗺️ ERCOT Acquisition Map'
    )

    st.caption(
        'All projects with valid Orennia coordinates '
        'are shown by default. Use the filters to '
        'screen by technology, ERCOT area, score, '
        'owner, development stage and COD. Select '
        'a project to isolate it and drill down.'
    )

    lat_col = (
        'Latitude (Degrees)'
        if 'Latitude (Degrees)'
        in df.columns
        else None
    )

    lon_col = (
        'Longitude (Degrees)'
        if 'Longitude (Degrees)'
        in df.columns
        else None
    )

    if (
        lat_col is None
        or lon_col is None
    ):

        st.error(
            'The active Power Projects CSV does not '
            'contain Latitude (Degrees) and Longitude '
            '(Degrees). Use the Orennia export that '
            'includes those fields.'
        )

    else:

        map_base = df.copy()

        map_base[
            'Map Latitude'
        ] = pd.to_numeric(
            map_base[
                lat_col
            ],
            errors='coerce'
        )

        map_base[
            'Map Longitude'
        ] = pd.to_numeric(
            map_base[
                lon_col
            ],
            errors='coerce'
        )

        def map_development_stage_label(
            row
        ):

            status = clean_text(
                row.get(
                    'Power Project Status'
                )
            )

            detailed = clean_text(
                row.get(
                    'Detailed Status'
                )
            )

            if (
                status == 'Operating'
                or detailed
                == 'Construction Complete'
            ):

                return 'Operating / Complete'

            if (
                'More Than 50%'
                in detailed
                or '>50%'
                in detailed
            ):

                return '>50% Construction'

            if status == 'In Construction':

                return 'In Construction'

            if (
                status == 'IA Executed'
                or ', IA'
                in detailed
            ):

                return 'IA Executed'

            if 'FIS Completed' in detailed:

                return 'FIS Completed'

            if 'FIS Started' in detailed:

                return 'FIS Started'

            if status == 'Pre-Study':

                return 'Pre-Study'

            if status in [
                'Inactive',
                'Suspended',
                'Retired'
            ]:

                return (
                    'Inactive / Suspended / Retired'
                )

            return 'Studies / Other'

        map_base[
            'Map Development Stage'
        ] = map_base.apply(
            map_development_stage_label,
            axis=1
        )

        valid_coordinate_mask = (
            map_base[
                'Map Latitude'
            ].between(
                24.0,
                37.5,
                inclusive='both'
            )
            &
            map_base[
                'Map Longitude'
            ].between(
                -107.5,
                -92.0,
                inclusive='both'
            )
        )

        mapped_universe = (
            map_base[
                valid_coordinate_mask
            ].copy()
        )

        unmapped_count = int(
            len(
                map_base
            )
            - len(
                mapped_universe
            )
        )

        if mapped_universe.empty:

            st.warning(
                'No projects in the current '
                'acquisition universe have valid '
                'latitude / longitude coordinates '
                'that can be mapped.'
            )

        else:

            technology_options = sorted(
                [
                    value
                    for value
                    in mapped_universe[
                        'Power Project Type'
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

            area_options = sorted(
                [
                    value
                    for value
                    in mapped_universe[
                        'ERCOT Area'
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

            stage_order = [
                'Operating / Complete',
                '>50% Construction',
                'In Construction',
                'IA Executed',
                'FIS Completed',
                'FIS Started',
                'Studies / Other',
                'Pre-Study',
                'Inactive / Suspended / Retired'
            ]

            existing_stages = set(
                mapped_universe[
                    'Map Development Stage'
                ]
                .dropna()
                .astype(
                    str
                )
                .tolist()
            )

            stage_options = [
                stage
                for stage
                in stage_order
                if stage
                in existing_stages
            ]

            owner_options = sorted(
                [
                    value
                    for value
                    in mapped_universe[
                        'Owner'
                    ]
                    .fillna(
                        ''
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

            status_options = sorted(
                [
                    value
                    for value
                    in mapped_universe[
                        'Power Project Status'
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

            cod_year_options = sorted(
                mapped_universe[
                    'First Power Date'
                ]
                .dropna()
                .dt.year
                .astype(
                    int
                )
                .unique()
                .tolist()
            )

            (
                f1,
                f2,
                f3
            ) = st.columns(
                [
                    1.15,
                    1.15,
                    1
                ]
            )

            with f1:

                selected_technologies = (
                    st.multiselect(
                        'Technology',
                        options=
                            technology_options,
                        default=
                            technology_options,
                        key=
                            'map_technology_filter'
                    )
                )

            with f2:

                selected_areas = (
                    st.multiselect(
                        'ERCOT Area',
                        options=
                            area_options,
                        default=
                            area_options,
                        key=
                            'map_area_filter'
                    )
                )

            with f3:

                top_score_filter = (
                    st.selectbox(
                        'Top Scored Projects',
                        options=[
                            'All Projects',
                            'Top 10',
                            'Top 20',
                            'Top 50',
                            'Score 80+',
                            'Score 70+',
                            'Score 60+'
                        ],
                        index=0,
                        key=
                            'map_top_score_filter'
                    )
                )

            (
                f4,
                f5,
                f6
            ) = st.columns(
                [
                    1.35,
                    1.2,
                    1
                ]
            )

            with f4:

                selected_owners = (
                    st.multiselect(
                        'Owner / Seller',
                        options=
                            owner_options,
                        default=[],
                        placeholder=
                            'All owners',
                        key=
                            'map_owner_filter'
                    )
                )

            with f5:

                selected_stages = (
                    st.multiselect(
                        'Development Stage',
                        options=
                            stage_options,
                        default=
                            stage_options,
                        key=
                            'map_stage_filter'
                    )
                )

            with f6:

                selected_statuses = (
                    st.multiselect(
                        'Project Status',
                        options=
                            status_options,
                        default=
                            status_options,
                        key=
                            'map_status_filter'
                    )
                )

            (
                f7,
                f8
            ) = st.columns(
                [
                    1.1,
                    2
                ]
            )

            with f7:

                cod_filter_options = (
                    [
                        'All COD Years'
                    ]
                    + [
                        str(
                            year
                        )
                        for year
                        in cod_year_options
                    ]
                    + [
                        'COD Missing'
                    ]
                )

                selected_cod = (
                    st.selectbox(
                        'COD',
                        options=
                            cod_filter_options,
                        index=0,
                        key=
                            'map_cod_filter'
                    )
                )

            filtered_map = (
                mapped_universe.copy()
            )

            if selected_technologies:

                filtered_map = (
                    filtered_map[
                        filtered_map[
                            'Power Project Type'
                        ].isin(
                            selected_technologies
                        )
                    ]
                )

            else:

                filtered_map = (
                    filtered_map
                    .iloc[
                        0:0
                    ]
                )

            if selected_areas:

                filtered_map = (
                    filtered_map[
                        filtered_map[
                            'ERCOT Area'
                        ].isin(
                            selected_areas
                        )
                    ]
                )

            else:

                filtered_map = (
                    filtered_map
                    .iloc[
                        0:0
                    ]
                )

            if selected_owners:

                filtered_map = (
                    filtered_map[
                        filtered_map[
                            'Owner'
                        ].isin(
                            selected_owners
                        )
                    ]
                )

            if selected_stages:

                filtered_map = (
                    filtered_map[
                        filtered_map[
                            'Map Development Stage'
                        ].isin(
                            selected_stages
                        )
                    ]
                )

            else:

                filtered_map = (
                    filtered_map
                    .iloc[
                        0:0
                    ]
                )

            if selected_statuses:

                filtered_map = (
                    filtered_map[
                        filtered_map[
                            'Power Project Status'
                        ].isin(
                            selected_statuses
                        )
                    ]
                )

            else:

                filtered_map = (
                    filtered_map
                    .iloc[
                        0:0
                    ]
                )

            if selected_cod == 'COD Missing':

                filtered_map = (
                    filtered_map[
                        filtered_map[
                            'First Power Date'
                        ].isna()
                    ]
                )

            elif (
                selected_cod
                != 'All COD Years'
            ):

                selected_cod_year = int(
                    selected_cod
                )

                filtered_map = (
                    filtered_map[
                        filtered_map[
                            'First Power Date'
                        ].dt.year
                        == selected_cod_year
                    ]
                )

            filtered_map = (
                filtered_map
                .sort_values(
                    by=[
                        'Opportunity Score',
                        'Data Completeness',
                        'Capacity (MW)'
                    ],
                    ascending=[
                        False,
                        False,
                        False
                    ]
                )
                .copy()
            )

            if top_score_filter == 'Top 10':

                filtered_map = (
                    filtered_map.head(
                        10
                    )
                )

            elif top_score_filter == 'Top 20':

                filtered_map = (
                    filtered_map.head(
                        20
                    )
                )

            elif top_score_filter == 'Top 50':

                filtered_map = (
                    filtered_map.head(
                        50
                    )
                )

            elif top_score_filter == 'Score 80+':

                filtered_map = (
                    filtered_map[
                        pd.to_numeric(
                            filtered_map[
                                'Opportunity Score'
                            ],
                            errors='coerce'
                        )
                        >= 80
                    ]
                )

            elif top_score_filter == 'Score 70+':

                filtered_map = (
                    filtered_map[
                        pd.to_numeric(
                            filtered_map[
                                'Opportunity Score'
                            ],
                            errors='coerce'
                        )
                        >= 70
                    ]
                )

            elif top_score_filter == 'Score 60+':

                filtered_map = (
                    filtered_map[
                        pd.to_numeric(
                            filtered_map[
                                'Opportunity Score'
                            ],
                            errors='coerce'
                        )
                        >= 60
                    ]
                )

            filtered_map[
                'Map Selection Label'
            ] = filtered_map.apply(
                lambda row:
                    f"{clean_text(row.get('Power Project Name'))} — "
                    f"{clean_text(row.get('Owner')) or 'Unknown Owner'} — "
                    f"{row.get('Capacity (MW)', np.nan):,.1f} MW — "
                    f"{clean_text(row.get('Generator ID')) or clean_text(row.get('Queue ID')) or 'No ID'}",
                axis=1
            )

            project_options = (
                [
                    'All filtered projects'
                ]
                + filtered_map[
                    'Map Selection Label'
                ].tolist()
            )

            with f8:

                selected_map_label = (
                    st.selectbox(
                        'Specific Project Drill-Down',
                        options=
                            project_options,
                        key=
                            'portfolio_project_map_selector'
                    )
                )

            st.markdown(
                '**Technology colors:** '
                '🟠 Solar &nbsp;&nbsp; | &nbsp;&nbsp; '
                '🔵 Storage &nbsp;&nbsp; | &nbsp;&nbsp; '
                '🟢 Wind'
            )

            if filtered_map.empty:

                st.warning(
                    'No mapped projects match the '
                    'current filters. Broaden one or '
                    'more filters to repopulate the map.'
                )

            else:

                selected_project = None

                if (
                    selected_map_label
                    != 'All filtered projects'
                ):

                    selected_project = (
                        filtered_map[
                            filtered_map[
                                'Map Selection Label'
                            ]
                            == selected_map_label
                        ]
                        .iloc[0]
                    )

                if selected_project is None:

                    map_view = (
                        filtered_map.copy()
                    )

                else:

                    map_view = (
                        filtered_map[
                            filtered_map[
                                'Map Selection Label'
                            ]
                            == selected_map_label
                        ]
                        .copy()
                    )

                (
                    k1,
                    k2,
                    k3,
                    k4,
                    k5
                ) = st.columns(
                    5
                )

                k1.metric(
                    'Mapped Projects',
                    f'{len(map_view):,}'
                )

                total_capacity = (
                    pd.to_numeric(
                        map_view[
                            'Capacity (MW)'
                        ],
                        errors='coerce'
                    )
                    .sum()
                )

                k2.metric(
                    'Capacity',
                    f'{total_capacity:,.0f} MW'
                )

                average_score = (
                    pd.to_numeric(
                        map_view[
                            'Opportunity Score'
                        ],
                        errors='coerce'
                    )
                    .mean()
                )

                k3.metric(
                    'Average Score',
                    (
                        f'{average_score:.1f}'
                        if pd.notna(
                            average_score
                        )
                        else 'N/A'
                    )
                )

                priority_count = int(
                    (
                        pd.to_numeric(
                            map_view[
                                'Opportunity Score'
                            ],
                            errors='coerce'
                        )
                        >= 70
                    ).sum()
                )

                k4.metric(
                    '70+ Score Targets',
                    f'{priority_count:,}'
                )

                if selected_project is None:

                    k5.metric(
                        'Selected Project',
                        'All'
                    )

                else:

                    k5.metric(
                        'Selected Project',
                        clean_text(
                            selected_project.get(
                                'Power Project Name'
                            )
                        )
                        or 'N/A'
                    )

                if unmapped_count > 0:

                    st.caption(
                        f'{unmapped_count:,} projects '
                        'in the acquisition universe '
                        'do not currently have usable '
                        'map coordinates and are '
                        'excluded from the map only.'
                    )

                map_plot = (
                    map_view.copy()
                )

                map_plot[
                    'Project'
                ] = (
                    map_plot[
                        'Power Project Name'
                    ]
                    .fillna(
                        ''
                    )
                    .astype(
                        str
                    )
                )

                map_plot[
                    'Owner Display'
                ] = (
                    map_plot[
                        'Owner'
                    ]
                    .replace(
                        '',
                        np.nan
                    )
                    .fillna(
                        'N/A'
                    )
                )

                map_plot[
                    'Technology'
                ] = (
                    map_plot[
                        'Power Project Type'
                    ]
                    .fillna(
                        'N/A'
                    )
                    .astype(
                        str
                    )
                )

                map_plot[
                    'Capacity Display'
                ] = (
                    pd.to_numeric(
                        map_plot[
                            'Capacity (MW)'
                        ],
                        errors='coerce'
                    )
                    .apply(
                        lambda value:
                            f'{value:,.1f} MW'
                            if pd.notna(
                                value
                            )
                            else 'N/A'
                    )
                )

                map_plot[
                    'Development Stage Display'
                ] = (
                    map_plot[
                        'Map Development Stage'
                    ]
                    .fillna(
                        'N/A'
                    )
                )

                map_plot[
                    'Project Status Display'
                ] = (
                    map_plot[
                        'Power Project Status'
                    ]
                    .fillna(
                        'N/A'
                    )
                    .astype(
                        str
                    )
                )

                map_plot[
                    'County Display'
                ] = (
                    map_plot[
                        'County'
                    ]
                    .fillna(
                        'N/A'
                    )
                    .astype(
                        str
                    )
                    if 'County'
                    in map_plot.columns
                    else 'N/A'
                )

                map_plot[
                    'COD Display'
                ] = (
                    map_plot[
                        'First Power Date'
                    ]
                    .apply(
                        format_date
                    )
                )

                map_plot[
                    'Score Display'
                ] = (
                    pd.to_numeric(
                        map_plot[
                            'Opportunity Score'
                        ],
                        errors='coerce'
                    )
                    .apply(
                        lambda value:
                            f'{value:.1f}'
                            if pd.notna(
                                value
                            )
                            else 'N/A'
                    )
                )

                map_plot[
                    'Rank Display'
                ] = (
                    pd.to_numeric(
                        map_plot.get(
                            'Rank',
                            pd.Series(
                                np.nan,
                                index=
                                    map_plot.index
                            )
                        ),
                        errors='coerce'
                    )
                    .apply(
                        lambda value:
                            f'#{int(value)}'
                            if pd.notna(
                                value
                            )
                            else 'N/A'
                    )
                )

                map_plot[
                    'Location Source Display'
                ] = (
                    map_plot[
                        'Location Source'
                    ]
                    .fillna(
                        'N/A'
                    )
                    .astype(
                        str
                    )
                    if 'Location Source'
                    in map_plot.columns
                    else 'N/A'
                )

                technology_colors = {
                    'Solar': [
                        245,
                        166,
                        35,
                        220
                    ],

                    'Storage': [
                        38,
                        132,
                        255,
                        220
                    ],

                    'Wind': [
                        47,
                        158,
                        68,
                        220
                    ]
                }

                map_plot[
                    'Map Radius'
                ] = (
                    pd.to_numeric(
                        map_plot[
                            'Capacity (MW)'
                        ],
                        errors='coerce'
                    )
                    .fillna(
                        50
                    )
                    .clip(
                        lower=20,
                        upper=500
                    )
                    * 125
                )

                map_plot[
                    'lat'
                ] = (
                    map_plot[
                        'Map Latitude'
                    ]
                    .astype(
                        float
                    )
                )

                map_plot[
                    'lon'
                ] = (
                    map_plot[
                        'Map Longitude'
                    ]
                    .astype(
                        float
                    )
                )

                layers = []

                for (
                    technology_name,
                    technology_color
                ) in technology_colors.items():

                    technology_map = (
                        map_plot[
                            map_plot[
                                'Power Project Type'
                            ]
                            == technology_name
                        ]
                        .copy()
                    )

                    if technology_map.empty:

                        continue

                    technology_layer = (
                        pdk.Layer(
                            'ScatterplotLayer',
                            data=
                                technology_map,
                            id=
                                f'{technology_name.lower()}_projects',
                            get_position=
                                '[lon, lat]',
                            get_radius=
                                'Map Radius',
                            get_fill_color=
                                technology_color,
                            get_line_color=
                                (
                                    [
                                        20,
                                        20,
                                        20,
                                        255
                                    ]
                                    if selected_project
                                    is not None
                                    else [
                                        255,
                                        255,
                                        255,
                                        230
                                    ]
                                ),
                            radius_min_pixels=
                                (
                                    14
                                    if selected_project
                                    is not None
                                    else 6
                                ),
                            radius_max_pixels=
                                (
                                    30
                                    if selected_project
                                    is not None
                                    else 18
                                ),
                            line_width_min_pixels=
                                (
                                    3
                                    if selected_project
                                    is not None
                                    else 1
                                ),
                            pickable=True,
                            auto_highlight=True,
                            stroked=True,
                            filled=True
                        )
                    )

                    layers.append(
                        technology_layer
                    )

                known_technologies = set(
                    technology_colors.keys()
                )

                other_technology_map = (
                    map_plot[
                        ~map_plot[
                            'Power Project Type'
                        ].isin(
                            known_technologies
                        )
                    ]
                    .copy()
                )

                if not other_technology_map.empty:

                    other_layer = (
                        pdk.Layer(
                            'ScatterplotLayer',
                            data=
                                other_technology_map,
                            id=
                                'other_projects',
                            get_position=
                                '[lon, lat]',
                            get_radius=
                                'Map Radius',
                            get_fill_color=[
                                120,
                                120,
                                120,
                                210
                            ],
                            get_line_color=[
                                255,
                                255,
                                255,
                                230
                            ],
                            radius_min_pixels=6,
                            radius_max_pixels=18,
                            line_width_min_pixels=1,
                            pickable=True,
                            auto_highlight=True,
                            stroked=True,
                            filled=True
                        )
                    )

                    layers.append(
                        other_layer
                    )

                if selected_project is not None:

                    map_latitude = float(
                        selected_project[
                            'Map Latitude'
                        ]
                    )

                    map_longitude = float(
                        selected_project[
                            'Map Longitude'
                        ]
                    )

                    map_zoom = 8.0

                else:

                    map_latitude = float(
                        map_plot[
                            'Map Latitude'
                        ].mean()
                    )

                    map_longitude = float(
                        map_plot[
                            'Map Longitude'
                        ].mean()
                    )

                    lat_span = float(
                        map_plot[
                            'Map Latitude'
                        ].max()
                        -
                        map_plot[
                            'Map Latitude'
                        ].min()
                    )

                    lon_span = float(
                        map_plot[
                            'Map Longitude'
                        ].max()
                        -
                        map_plot[
                            'Map Longitude'
                        ].min()
                    )

                    max_span = max(
                        lat_span,
                        lon_span
                    )

                    if max_span > 8:

                        map_zoom = 4.6

                    elif max_span > 5:

                        map_zoom = 5.0

                    elif max_span > 3:

                        map_zoom = 5.5

                    elif max_span > 1.5:

                        map_zoom = 6.2

                    elif max_span > 0.75:

                        map_zoom = 7.0

                    else:

                        map_zoom = 8.0

                deck = pdk.Deck(
                    map_style=(
                        'https://basemaps.cartocdn.com/'
                        'gl/positron-gl-style/style.json'
                    ),
                    initial_view_state=
                        pdk.ViewState(
                            latitude=
                                map_latitude,
                            longitude=
                                map_longitude,
                            zoom=
                                map_zoom,
                            pitch=0
                        ),
                    layers=
                        layers,
                    tooltip={
                        'html':
                            '<b>{Project}</b><br/>'
                            'Rank: {Rank Display}<br/>'
                            'Owner: {Owner Display}<br/>'
                            'Technology: {Technology}<br/>'
                            'Capacity: {Capacity Display}<br/>'
                            'Project Status: {Project Status Display}<br/>'
                            'Development Stage: {Development Stage Display}<br/>'
                            'ERCOT Area: {ERCOT Area}<br/>'
                            'County: {County Display}<br/>'
                            'COD: {COD Display}<br/>'
                            'Opportunity Score: {Score Display}<br/>'
                            'Location Source: {Location Source Display}',

                        'style': {
                            'backgroundColor':
                                'rgba(20,20,20,0.92)',

                            'color':
                                'white'
                        }
                    }
                )

                st.pydeck_chart(
                    deck,
                    use_container_width=True,
                    height=700
                )

                st.caption(
                    (
                        'Single-project drill-down active — '
                        'only the selected project is shown. '
                        'Its marker color represents technology.'
                    )
                    if selected_project is not None
                    else
                    (
                        'Marker color represents technology; '
                        'marker size scales with MW. Hover '
                        'over any project for rank, score, '
                        'owner, status, COD and location details.'
                    )
                )

                st.markdown(
                    '### Selected Project'
                    if selected_project is not None
                    else
                    '### Filtered Project Universe'
                )

                map_table_columns = [
                    'Rank',
                    'Power Project Name',
                    'Owner',
                    'Power Project Type',
                    'Capacity (MW)',
                    'Map Development Stage',
                    'Power Project Status',
                    'ERCOT Area',
                    'First Power Date',
                    'Opportunity Score',
                    'Action'
                ]

                available_map_table_columns = [
                    col
                    for col
                    in map_table_columns
                    if col
                    in filtered_map.columns
                ]

                map_table = (
                    map_view[
                        available_map_table_columns
                    ]
                    .sort_values(
                        'Opportunity Score',
                        ascending=False
                    )
                    .reset_index(
                        drop=True
                    )
                )

                st.dataframe(
                    map_table,
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        'Rank':
                            st.column_config.NumberColumn(
                                'Rank',
                                format='%d'
                            ),

                        'Opportunity Score':
                            st.column_config.ProgressColumn(
                                'Opportunity Score',
                                min_value=0,
                                max_value=100,
                                format='%.1f'
                            ),

                        'Capacity (MW)':
                            st.column_config.NumberColumn(
                                'Capacity (MW)',
                                format='%.1f'
                            ),

                        'First Power Date':
                            st.column_config.DateColumn(
                                'COD'
                            )
                    }
                )

                if selected_project is not None:

                    st.markdown(
                        '### Selected Project Detail'
                    )

                    (
                        d1,
                        d2,
                        d3,
                        d4,
                        d5
                    ) = st.columns(
                        5
                    )

                    d1.metric(
                        'Opportunity Score',
                        f"{selected_project['Opportunity Score']:.1f}"
                    )

                    d2.metric(
                        'Technology',
                        clean_text(
                            selected_project.get(
                                'Power Project Type'
                            )
                        )
                        or 'N/A'
                    )

                    d3.metric(
                        'Capacity',
                        (
                            f"{selected_project['Capacity (MW)']:,.1f} MW"
                            if pd.notna(
                                selected_project.get(
                                    'Capacity (MW)'
                                )
                            )
                            else 'N/A'
                        )
                    )

                    d4.metric(
                        'ERCOT Area',
                        clean_text(
                            selected_project.get(
                                'ERCOT Area'
                            )
                        )
                        or 'N/A'
                    )

                    d5.metric(
                        'COD',
                        format_date(
                            selected_project.get(
                                'First Power Date'
                            )
                        )
                    )

                    detail_fields = [
                        'Rank',
                        'Power Project Name',
                        'Generator Name',
                        'Generator ID',
                        'Owner',
                        'Queue ID',
                        'Power Project Type',
                        'Capacity (MW)',
                        'Power Project Status',
                        'Detailed Status',
                        'Map Development Stage',
                        'First Power Date',
                        'ERCOT Area',
                        'ISO Zone',
                        'County',
                        'Point of Interconnection',
                        'Location Source',
                        'Latitude (Degrees)',
                        'Longitude (Degrees)',
                        'Contract Type',
                        'Contract Offtaker',
                        'PTC/ITC',
                        'Distress Score',
                        'Development Stage',
                        'Market / Revenue',
                        'Acquisition Value',
                        'Executability',
                        'Opportunity Score',
                        'Action'
                    ]

                    detail_rows = []

                    for field in detail_fields:

                        if field not in selected_project.index:

                            continue

                        value = selected_project.get(
                            field
                        )

                        if field == 'First Power Date':

                            display_value = format_date(
                                value
                            )

                        elif pd.isna(
                            value
                        ):

                            display_value = 'N/A'

                        else:

                            display_value = str(
                                value
                            )

                        detail_rows.append(
                            {
                                'Field':
                                    field,

                                'Value':
                                    display_value
                            }
                        )

                    st.dataframe(
                        pd.DataFrame(
                            detail_rows
                        ),
                        use_container_width=True,
                        hide_index=True
                    )


with price_tab:

    st.divider()

    st.markdown(
        '## 🎯 Acquisition Project Market Benchmark'
    )

    st.caption(
        'Select an acquisition target to compare '
        'it with the latest broad ERCOT hub price '
        'for its area. This is a screening benchmark, '
        "not the project's nodal settlement price."
    )

    if market_rt_df.empty:

        st.info(
            'Live Real-Time SPP is unavailable, '
            'so project market benchmarking cannot '
            'be shown right now.'
        )

    elif df.empty:

        st.info(
            'No acquisition projects are available '
            'for benchmarking.'
        )

    else:

        project_market_options = (
            df.apply(
                lambda row:
                    f"{clean_text(row.get('Power Project Name'))} — "
                    f"{clean_text(row.get('Owner')) or 'Unknown Owner'} — "
                    f"{clean_text(row.get('ERCOT Area')) or 'Unknown Area'}",
                axis=1
            )
            .tolist()
        )

        selected_project_market_label = (
            st.selectbox(
                'Project',
                options=
                    project_market_options,
                key=
                    'market_project_benchmark_selector'
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
            'ERCOT-N':
                'HB_NORTH',

            'ERCOT-H':
                'HB_HOUSTON',

            'ERCOT-S':
                'HB_SOUTH',

            'ERCOT-W':
                'HB_WEST',

            'Panhandle':
                'HB_PAN'
        }

        project_area = clean_text(
            market_project.get(
                'ERCOT Area'
            )
        )

        benchmark_hub = (
            area_to_hub.get(
                project_area
            )
        )

        if (
            benchmark_hub is None
            or benchmark_hub
            not in market_rt_df.columns
        ):

            st.warning(
                f'No broad hub benchmark is '
                f'configured for '
                f"{project_area or 'this project area'}."
            )

        else:

            latest_market_day = (
                market_rt_df[
                    'Oper Day'
                ].max()
            )

            project_rt = (
                market_rt_df[
                    market_rt_df[
                        'Oper Day'
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
                and benchmark_hub
                in market_dam_df.columns
            ):

                latest_project_dam_day = (
                    market_dam_df[
                        'Oper Day'
                    ].max()
                )

                benchmark_dam_average = (
                    market_dam_df[
                        market_dam_df[
                            'Oper Day'
                        ]
                        == latest_project_dam_day
                    ][
                        benchmark_hub
                    ]
                    .mean()
                )

            (
                b1,
                b2,
                b3,
                b4,
                b5,
                b6
            ) = st.columns(
                6
            )

            b1.metric(
                'Project',
                clean_text(
                    market_project.get(
                        'Power Project Name'
                    )
                )
                or 'N/A'
            )

            b2.metric(
                'ERCOT Area',
                project_area
                or 'N/A'
            )

            b3.metric(
                'Benchmark Hub',
                benchmark_hub
            )

            b4.metric(
                'Latest RT',
                price_metric_value(
                    latest_benchmark_price
                )
            )

            b5.metric(
                'RT Day Avg',
                price_metric_value(
                    benchmark_average
                )
            )

            b6.metric(
                'DAM Day Avg',
                price_metric_value(
                    benchmark_dam_average
                )
            )

            st.caption(
                f'Today at {benchmark_hub}: '
                f'high '
                f'**{price_metric_value(benchmark_high)}**, '
                f'low '
                f'**{price_metric_value(benchmark_low)}**. '
                'This broad benchmark is intentionally '
                'not included in the automated '
                'Opportunity Score yet.'
            )

            project_market_chart = (
                project_rt[
                    [
                        'Timestamp',
                        benchmark_hub
                    ]
                ]
                .rename(
                    columns={
                        benchmark_hub:
                            f'{benchmark_hub} RT SPP'
                    }
                )
            )

            st.line_chart(
                project_market_chart.set_index(
                    'Timestamp'
                ),
                use_container_width=True,
                height=320
            )
