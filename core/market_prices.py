"""IhingaAI market price viewer. Recorded prices only; no prediction.

Source: TangaBid CSV export (eSoko-attributed records). Website and CSV link are
provided even when downloads are unavailable. No dependency beyond Streamlit/pandas.
"""
from datetime import datetime, timezone, timedelta
from pathlib import Path
import base64
import html
from io import BytesIO
from urllib.request import Request, urlopen
import pandas as pd
import streamlit as st

SOURCE = "https://www.tangabid.com/market/prices/"
EXPORT = "https://www.tangabid.com/market/prices/?export=csv"


def _column(df, candidates):
    norm = {str(c).lower().strip().replace(' ', '_').replace('-', '_'): c for c in df.columns}
    for c in candidates:
        if c in norm:
            return norm[c]
    return None


def _parse(data):
    df = pd.read_csv(BytesIO(data), low_memory=False)
    if df.empty:
        raise ValueError("The downloaded CSV contains no price records.")
    cols = {
        'Product': _column(df, ['product', 'product_name', 'commodity', 'crop', 'item']),
        'Market': _column(df, ['market', 'market_name', 'location', 'location_name']),
        'Region': _column(df, ['region', 'district', 'province', 'area']),
        'Price (RWF)': _column(df, ['price', 'price_rwf', 'price_value', 'amount']),
        'Observed date': _column(df, ['observed_date', 'observation_date', 'date', 'price_date', 'recorded_date']),
        'Unit': _column(df, ['unit', 'price_unit', 'measurement_unit']),
        'Source': _column(df, ['source', 'data_source']),
        'Price type': _column(df, ['price_type', 'market_level', 'price_level', 'type']),
    }
    if any(cols[k] is None for k in ('Product', 'Market', 'Price (RWF)', 'Observed date')):
        raise ValueError("Export structure changed. Columns received: " + ", ".join(map(str, df.columns)))
    out = pd.DataFrame({k: df[c] for k,c in cols.items() if c is not None})
    out['Price (RWF)'] = pd.to_numeric(out['Price (RWF)'].astype(str).str.replace(',', '', regex=False), errors='coerce')
    out['Observed date'] = pd.to_datetime(out['Observed date'], errors='coerce', utc=True).dt.tz_localize(None)
    out = out.dropna(subset=['Product','Market','Price (RWF)','Observed date'])
    out = out[out['Price (RWF)'] >= 0]
    if out.empty:
        raise ValueError('The CSV had no usable dated price records.')
    return out.sort_values('Observed date', ascending=False).reset_index(drop=True)


@st.cache_data(ttl=3600, show_spinner=False)
def _download_csv():
    req = Request(EXPORT, headers={'User-Agent': 'IhingaAI-MarketPrices/1.0 (public CSV viewer)', 'Accept': 'text/csv'})
    with urlopen(req, timeout=25) as r:
        data = r.read(60 * 1024 * 1024 + 1)
        content_type = r.headers.get('Content-Type','')
    if len(data) > 60 * 1024 * 1024:
        raise ValueError('The export exceeds the 60 MB safe download limit.')
    if b'<html' in data[:1000].lower() or 'text/html' in content_type.lower():
        raise ValueError('The source returned a webpage rather than a CSV.')
    return _parse(data)




def _hero():
    # Photo header aligned with the Phase 14 field/risk interface.
    path = Path(__file__).resolve().parents[1] / 'assets' / 'headers' / 'market_prices.jpg'
    if path.is_file():
        image_data = base64.b64encode(path.read_bytes()).decode('ascii')
        backdrop = ("background-image:linear-gradient(90deg,rgba(0,44,30,.88),rgba(0,46,28,.23)),"
                    f"url('data:image/jpeg;base64,{image_data}');background-size:cover;background-position:center;")
    else:
        backdrop = "background:linear-gradient(110deg,#00432f,#168654);"
    st.markdown(f'''<div class="ih-market-hero" style="{backdrop}">
        <div class="ih-market-title">Market Prices</div>
        <div class="ih-market-subtitle">View recent product prices from available market data sources.</div>
        </div>''', unsafe_allow_html=True)


def _styles():
    st.markdown('''<style>
      .ih-market-hero{min-height:176px;border-radius:12px;padding:26px 30px;
         margin:2px 0 18px;display:flex;flex-direction:column;justify-content:end;}
      .ih-market-title{font-size:clamp(25px,3vw,34px);font-weight:800;color:#fff;line-height:1.1;}
      .ih-market-subtitle{font-size:14px;color:#f3fff7;margin-top:7px;}
      .ih-market-panel{background:#fff;border:1px solid #e2eae6;border-radius:11px;
         padding:14px 16px;margin:2px 0 12px;}
      .ih-market-panel-title{font-size:16px;font-weight:750;color:#192a21;margin-bottom:9px;}
      .ih-market-small{color:#65756d;font-size:12px;}
      div[data-testid="stButton"] button[kind="primary"] {background:#007a4d;border-color:#007a4d;}
      div[data-testid="stButton"] button[kind="primary"]:hover {background:#005e3d;border-color:#005e3d;}
      @media(max-width:760px){.ih-market-hero{min-height:142px;padding:20px}}
    </style>''', unsafe_allow_html=True)


def _category_subset(frame, column, selected):
    return frame if selected.startswith('All ') else frame[frame[column].astype(str) == selected]


def market_prices_page():
    _styles()
    _hero()
    st.caption('Recorded source observations, not predictions or guaranteed buyer offers.')

    if 'ihinga_market_df' not in st.session_state:
        st.session_state.ihinga_market_df = None
        st.session_state.ihinga_market_origin = None

    # A source-management section is kept available while the main view remains uncluttered.
    with st.expander('↻ Load / update market data', expanded=st.session_state.ihinga_market_df is None):
        st.link_button('Open published source (TangaBid)', SOURCE, use_container_width=True)
        load_col, upload_col = st.columns(2)
        if load_col.button('↻ Load published prices', key='ih_market_refresh', type='primary', use_container_width=True):
            try:
                with st.spinner('Downloading the published dated price records…'):
                    data = _download_csv()
                st.session_state.ihinga_market_df = data
                st.session_state.ihinga_market_origin = 'TangaBid public CSV export'
                st.success(f'{len(data):,} recorded prices loaded.')
            except Exception as exc:
                st.warning(f'Automatic source unavailable: {exc}')
                st.info('You can export CSV from the source site and upload it here instead.')
        incoming = upload_col.file_uploader('Or upload source CSV', type=['csv'], key='ihinga_price_csv')
        if incoming is not None:
            try:
                content = incoming.getvalue()
                token = (incoming.name, len(content), content[:200])
                if st.session_state.get('_market_upload_token') != token:
                    data = _parse(content)
                    st.session_state.ihinga_market_df = data
                    st.session_state.ihinga_market_origin = 'Uploaded TangaBid-style CSV'
                    st.session_state._market_upload_token = token
                    st.success(f'{len(data):,} recorded prices loaded from CSV.')
            except Exception as exc:
                st.error(f'Could not read uploaded CSV: {exc}')

    raw = st.session_state.ihinga_market_df
    if raw is None or raw.empty:
        st.info('No market-price records loaded. Open “Load / update market data” to download or upload a dated CSV. Example prices are never substituted.')
        return

    df = raw.copy()
    products = sorted(df['Product'].dropna().astype(str).unique().tolist())
    if not products:
        st.warning('The source has no valid product names.')
        return
    # One selected product is essential for meaningful price trends.
    p_col, m_col, t_col = st.columns(3)
    product = p_col.selectbox('Product', products, key='market_ui_product')
    df = df[df['Product'].astype(str) == product]
    markets = sorted(df['Market'].dropna().astype(str).unique().tolist())
    market = m_col.selectbox('District / Market', ['All markets'] + markets, key='market_ui_market')
    if market != 'All markets':
        df = df[df['Market'].astype(str) == market]
    periods = {'Last 30 days': 30, 'Last 3 months': 90, 'Last 6 months': 183,
               'Last 12 months': 365, 'All available dates': None}
    period = t_col.selectbox('Time period', list(periods), index=1, key='market_ui_period')
    df['Observed date'] = pd.to_datetime(df['Observed date'], errors='coerce')
    df['Price (RWF)'] = pd.to_numeric(df['Price (RWF)'], errors='coerce')
    df = df.dropna(subset=['Observed date', 'Price (RWF)'])
    if periods[period] is not None:
        cutoff = pd.Timestamp(datetime.now(timezone.utc).date() - timedelta(days=periods[period]))
        df = df[df['Observed date'] >= cutoff]
    if df.empty:
        st.info('No observations match these filters. Try All available dates or another market.')
        return

    # All displayed numeric comparisons must refer to the same quoted unit and price level.
    compat_cols = [col for col in ('Unit','Price type') if col in df.columns]
    if compat_cols:
        opts = {}
        cols = st.columns(len(compat_cols))
        for i, name in enumerate(compat_cols):
            options = sorted(df[name].dropna().astype(str).unique().tolist())
            if options:
                opts[name] = cols[i].selectbox(name, options, key='market_ui_'+name.replace(' ','_'))
        for name, val in opts.items():
            df = df[df[name].astype(str) == val]
        if df.empty:
            st.info('No records for the selected unit and price type.')
            return
    else:
        st.warning('The export does not identify price units or price type. Trend values may not be directly comparable; confirm quote definitions with the source.')

    latest = df['Observed date'].max().date()
    age = (datetime.now(timezone.utc).date() - latest).days
    st.caption(f"Source: {st.session_state.get('ihinga_market_origin') or 'Loaded market records'} · "
               f"Latest matching observation: {latest.isoformat()} · {len(df):,} records")
    if age > 14:
        st.warning(f'Most recent matching quote is {age} days old. Do not treat historical prices as current offers.')
    elif age < 0:
        st.warning('Future-dated observations detected; please check the source.')

    chart_col, prices_col = st.columns([3, 2], gap='medium')
    with chart_col:
        st.markdown('<div class="ih-market-panel-title">Price trend — '+html.escape(product)+' (RWF per quoted unit)</div>',unsafe_allow_html=True)
        # Median of records per observation date; no synthetic interpolation or invented values.
        trend = (df.assign(Day=df['Observed date'].dt.normalize())
                   .groupby('Day', as_index=False)['Price (RWF)'].median().sort_values('Day'))
        if len(trend) >= 2:
            st.line_chart(trend.set_index('Day')['Price (RWF)'], color='#007a4d', height=260)
        else:
            st.info('A price trend needs at least two dates. The available observation is listed on the right.')
        st.caption('Daily median of recorded quotes in the current selection; prices are not forecasts.')
    with prices_col:
        st.markdown('<div class="ih-market-panel-title">Latest prices</div>', unsafe_allow_html=True)
        # One latest original record per market (not a misleading cross-market average).
        recent = (df.sort_values('Observed date',ascending=False)
                    .drop_duplicates('Market').head(12).copy())
        recent['Recorded price'] = recent['Price (RWF)'].map(lambda v:f'{v:,.0f} RWF')
        recent['Date'] = recent['Observed date'].dt.strftime('%Y-%m-%d')
        st.dataframe(recent[['Market','Recorded price','Date']].rename(columns={'Market':'Market'}),
                     hide_index=True,use_container_width=True,height=min(440, 68+len(recent)*35))
        st.caption('Latest dated observation per market, not a verified live selling offer.')

    with st.expander('Compare markets and explore individual price records', expanded=False):
        st.subheader('Market comparison')
        st.caption('Market quotations may have different dates. Comparable units and price types are selected above when provided.')
        grouping=['Market'] + [c for c in ('Region','Unit','Price type') if c in df]
        comparison = df.sort_values('Observed date',ascending=False).drop_duplicates(subset=grouping)
        display = [c for c in ['Market','Region','Observed date','Price (RWF)','Unit','Price type','Source'] if c in comparison]
        st.dataframe(comparison[display].head(100),use_container_width=True,hide_index=True)
        st.subheader('All matching observations')
        st.dataframe(df.sort_values('Observed date',ascending=False).head(300),use_container_width=True,hide_index=True)
        st.download_button('Download matching prices (CSV)',df.to_csv(index=False).encode('utf-8'),
                           file_name='ihingaai_market_prices.csv',mime='text/csv',key='market_ui_export')

    with st.expander('Estimate gross sales from a recorded quote', expanded=False):
        st.caption('Illustrative gross revenue only—not profit, a forecast, or a guaranteed market offer.')
        quotes = df.sort_values('Observed date',ascending=False).drop_duplicates('Market').copy()
        if 'Unit' in quotes.columns:
            normalized = quotes['Unit'].astype(str).str.strip().str.lower()
            quotes = quotes[normalized.isin(['kg','kilogram','kilograms','rwf/kg','frw/kg','1 kg','1kg'])]
        else:
            quotes = quotes.iloc[0:0]
        if quotes.empty:
            st.info('No verified RWF/kg quotations available to calculate gross sales. Check the quoted unit in the source.')
        else:
            quotes = quotes.reset_index(drop=True)
            idx = st.selectbox('Recorded market quote',range(len(quotes)),format_func=lambda i:
                f"{quotes.iloc[i]['Market']} · {quotes.iloc[i]['Price (RWF)']:,.0f} RWF/kg · {quotes.iloc[i]['Observed date'].date()}",
                key='market_ui_quote')
            quantity = st.number_input('Estimated / actual harvest in kg',min_value=0.0,value=0.0,step=10.0,key='market_ui_quantity')
            value = quantity * float(quotes.iloc[idx]['Price (RWF)'])
            st.metric('Illustrative gross sales',f'{value:,.0f} RWF')
            st.caption('Excludes transport, storage, commissions, spoilage, and cultivation costs.')

    st.caption('Data attribution: TangaBid public market-price export (eSoko attribution where supplied). Confirm prices and units with market participants before acting.')
