"""IhingaAI field risk review. Deterministic, evidence-led indicators; no loss probabilities."""
from datetime import date, datetime, timedelta
import math
import pandas as pd
import streamlit as st

from core import fields as F, engagement as E, smartfarm as FS
from core import labels as L


def _number(x):
    try:
        x=float(x)
        return x if math.isfinite(x) else None
    except (TypeError,ValueError): return None


def _date(x):
    try:
        if x is None or pd.isna(x): return None
        return pd.to_datetime(x).date()
    except (ValueError, TypeError, OverflowError): return None


def _risk(name, level, evidence, action, source):
    return dict(category=name, level=level, evidence=evidence, action=action, source=source)


def _recent_estimate(estimates):
    return estimates[0] if estimates else None


def _weather(forecast):
    if not forecast or not forecast.get('daily'):
        return _risk('Weather','Not assessed','No current district forecast was available.',
                     'Check the Weather page and consult local forecasts before time-sensitive work.', 'Open-Meteo district forecast')
    rows=forecast['daily'][:3]
    rain=[_number(r.get('rain_mm')) for r in rows]
    max_temp=[_number(r.get('max_c')) for r in rows]
    if any(x is not None and x>=30 for x in rain):
        return _risk('Weather','Attention','At least one of the next three forecast days has 30 mm or more of rain at the district reference point (review threshold, not a crop-loss forecast).',
                     'Inspect drainage, review vulnerable work and check official/local weather warnings.','Open-Meteo district forecast')
    if any(x is not None and x>=33 for x in max_temp):
        return _risk('Weather','Attention','At least one of the next three days has a forecast maximum of 33°C or higher at the district reference point (screening threshold).',
                     'Inspect soil moisture and crop stress; discuss crop-specific actions with an agronomist.','Open-Meteo district forecast')
    if any(x is not None for x in rain+max_temp):
        return _risk('Weather','No trigger observed','No configured rainfall or temperature screening threshold was exceeded in the next three days. This is not a guarantee of safe conditions.',
                     'Continue checking weather as forecasts change.','Open-Meteo district forecast')
    return _risk('Weather','Not assessed','Forecast observations lacked usable rainfall and temperature numbers.',
                 'Check the Weather page or local forecasts.','Open-Meteo district forecast')


def _production(estimate):
    if not estimate:
        return _risk('Production uncertainty','Not assessed','No saved harvest estimate for this field.',
                     'Create and save a harvest estimate for this field.','Saved IhingaAI estimate')
    low=next((_number(estimate.get(k)) for k in ('lower_kg','low_kg') if _number(estimate.get(k)) is not None),None)
    mid=next((_number(estimate.get(k)) for k in ('estimate_kg','predicted_kg','typical_kg') if _number(estimate.get(k)) is not None),None)
    high=next((_number(estimate.get(k)) for k in ('upper_kg','high_kg') if _number(estimate.get(k)) is not None),None)
    if low is None or mid is None or high is None or mid<=0:
        return _risk('Production uncertainty','Not assessed','A saved estimate exists but its uncertainty bounds could not be read.',
                     'Review the original estimate in My fields.','Saved IhingaAI estimate')
    ratio=max(0,(mid-low)/mid)
    level='Attention' if ratio>=0.50 else 'Review'
    return _risk('Production uncertainty',level,f'Saved estimate: {mid:,.0f} kg, lower bound {low:,.0f} kg and upper bound {high:,.0f} kg. Lower bound is {ratio:.0%} below the typical estimate. This is model uncertainty, not the probability of crop failure.',
                 'Plan using the lower-harvest scenario; monitor actual results and avoid committing sales before harvest.','Saved IhingaAI estimate')


def _market(field, df):
    if not isinstance(df,pd.DataFrame) or df.empty:
        return _risk('Market prices','Not assessed','No recorded market-price data loaded in this session.',
                     'Open Market Prices, load a dated source export and return here.','Market Prices page')
    code=str(field.get('crop_code',''))
    label=L.CROPS.get(code,{}).get('en','')
    if not label or 'Product' not in df or 'Observed date' not in df or 'Price (RWF)' not in df:
        return _risk('Market prices','Not assessed','Crop label or required market-price fields are unavailable.',
                     'Check dated price records directly on the Market Prices page.','Market Prices page')
    match=df[df['Product'].astype(str).str.strip().str.casefold()==label.strip().casefold()].copy()
    if match.empty:
        return _risk('Market prices','Not assessed',f'No direct product match for {label} in the loaded price records.',
                     'Check product naming and source coverage on the Market Prices page.','Market Prices page')
    match['Observed date']=pd.to_datetime(match['Observed date'],errors='coerce')
    match['Price (RWF)']=pd.to_numeric(match['Price (RWF)'],errors='coerce')
    match=match.dropna(subset=['Observed date','Price (RWF)'])
    if match.empty:
        return _risk('Market prices','Not assessed','Matching prices have no valid amounts or dates.',
                     'Load a verified, dated source.','Market Prices page')
    latest=match['Observed date'].max().date()
    age=(date.today()-latest).days
    if age>14 or age<0:
        return _risk('Market prices','Attention',f'Most recent matching {label} quote is dated {latest.isoformat()} ({age} days from today). Old or future-dated prices may not represent current conditions.',
                     'Confirm a new buyer quotation before deciding when or where to sell.','Dated market-price observations')
    # No price-spread comparisons unless unit and price level can be matched.
    if 'Unit' in match and 'Price type' in match:
        newest=match[match['Observed date'].dt.date >= latest-timedelta(days=7)]
        groups=newest.groupby(['Unit','Price type'],dropna=False)
        spreads=[]
        for _,g in groups:
            if len(g)>=2 and g['Price (RWF)'].min()>0:
                spread=(g['Price (RWF)'].max()-g['Price (RWF)'].min())/g['Price (RWF)'].min()
                if spread>=.25: spreads.append(spread)
        if spreads:
            return _risk('Market prices','Review',f'Comparable recorded quotes within 7 days differ by at least {max(spreads):.0%} relative to the lowest price. Observations are not guaranteed offers.',
                         'Compare market locations and transport costs, and confirm farmgate/wholesale terms with buyers.','Dated market-price observations')
    return _risk('Market prices','No trigger observed',f'{label} price records available; latest observation dated {latest.isoformat()}. No configured freshness/spread trigger detected.',
                 'Verify current selling prices and transport costs with buyers.','Dated market-price observations')


def _activities(activities):
    pending=[a for a in activities if not a.get('completed')]
    overdue=[a for a in pending if _date(a.get('due_date')) and _date(a['due_date'])<date.today()]
    if overdue:
        return _risk('Field activities','Attention',f'{len(overdue)} incomplete field activities are past their recorded due date.',
                     'Open My farming season and review or reschedule overdue tasks.','Farmer activity records')
    if not activities:
        return _risk('Field activities','Not assessed','No activities have been recorded for this field.',
                     'Add planned activities and due dates to My farming season.','Farmer activity records')
    return _risk('Field activities','No trigger observed',f'{len(activities)} recorded activities; none currently overdue.',
                 'Keep activity dates and completion statuses up to date.','Farmer activity records')


def _finances(rows):
    if rows is None or not rows:
        return _risk('Farm finances','Not assessed','No recorded expenses or sales for this field.',
                     'Record transactions under Farm finances; missing records do not mean zero financial risk.','Farmer-entered transactions')
    expenses=sum(_number(r.get('amount_rwf')) or 0 for r in rows if r.get('kind',r.get('transaction_type'))=='expense')
    sales=sum(_number(r.get('amount_rwf')) or 0 for r in rows if r.get('kind',r.get('transaction_type'))=='sale')
    if not any(r.get('kind',r.get('transaction_type')) in ('expense','sale') for r in rows):
        return _risk('Farm finances','Not assessed','The transaction type fields could not be interpreted.',
                     'Review recorded expenses and sales in Farm finances.','Farmer-entered transactions')
    if expenses>sales:
        return _risk('Farm finances','Review',f'Recorded expenses: {expenses:,.0f} RWF; recorded sales: {sales:,.0f} RWF. Sales minus expenses: {sales-expenses:,.0f} RWF. This is not profit or proof of financial distress.',
                     'Review remaining costs, stock and expected sales; maintain a budget.','Farmer-entered transactions')
    return _risk('Farm finances','Review',f'Recorded expenses: {expenses:,.0f} RWF; recorded sales: {sales:,.0f} RWF. The recorded balance is {sales-expenses:,.0f} RWF, but missing costs, unsold harvest and future obligations are unknown.',
                 'Check whether seeds, fertilizer, labour, transport and other costs were fully entered. This is not a profit or financial-health score.','Farmer-entered transactions')


def _health(observations):
    if not observations:
        return _risk('Crop health','Not assessed','No farmer crop-health observations have been recorded for this field.',
                     'Record a field check-in under Crop monitoring.','Farmer crop observations')
    recent=observations[0]
    symptom=str(recent.get('symptom') or '').strip()
    benign=('looks healthy','no visible issue','healthy','none')
    if symptom and symptom.casefold() not in benign and symptom.casefold() not in ('not sure',):
        return _risk('Crop health','Review',f'Latest farmer-reported symptom: {symptom}. This is an observation, not a confirmed diagnosis.',
                     'Document changes, take clear photos if appropriate, and contact an agronomist before treatment.','Farmer crop observations')
    return _risk('Crop health','Not assessed' if not symptom or symptom.casefold()=='not sure' else 'No trigger observed',f'Latest farmer check-in: {symptom or "symptom not specified"}. A self-report is not a diagnosis.',
                 'Continue regular crop observations.','Farmer crop observations')


def _fetch_or_none(fn,*args):
    try: return fn(*args),None
    except Exception as e: return None,type(e).__name__



# Visual presentation helpers; risk classifications remain defined above.
def _risk_visual(category):
    return {
        'Weather': ('☀️', 'View Weather', 'Weather', '#2774e5'),
        'Production uncertainty': ('🌽', 'Open Estimate', 'Estimate', '#007a4d'),
        'Market prices': ('📈', 'View Market Prices', 'Market Prices', '#f5ab27'),
        'Field activities': ('📅', 'View Activities', 'My farming season', '#2774e5'),
        'Farm finances': ('💰', 'View Finances', 'Farm finances', '#007a4d'),
        'Crop health': ('🌿', 'Open Crop Monitoring', 'Crop monitoring', '#007a4d'),
    }[category]


def _risk_badge(level):
    return {
        'Attention': ('Attention', '#ffe2df', '#a7261b'),
        'Review': ('Review recommended', '#fff0c2', '#72500b'),
        'No trigger observed': ('No trigger', '#d8f3db', '#115b32'),
        'Not assessed': ('Insufficient data', '#ebedf1', '#4b5563'),
    }.get(level, ('Needs review', '#ebedf1', '#4b5563'))


def _navigate_to(page, fid):
    # Reuse existing authorized farmer navigation; save selected field only as a hint.
    st.session_state['ihinga_active_field_id'] = fid
    st.session_state['page'] = page
    st.session_state['nav_target'] = page
    st.rerun()


def risk_assessment_page(user, district_label, district_weather):
    import base64
    import html
    from pathlib import Path

    image_path = Path(__file__).resolve().parent.parent / 'assets' / 'headers' / 'risk_assessment.jpg'
    if image_path.exists():
        image_b64 = base64.b64encode(image_path.read_bytes()).decode('ascii')
        background = ("background-image:linear-gradient(90deg, rgba(0,36,23,.85) 0%, rgba(0,36,23,.2) 82%),"
                      f"url('data:image/jpeg;base64,{image_b64}');background-position:center;background-size:cover;")
    else:
        background = 'background:linear-gradient(100deg,#003d2f,#007a4d);'
    st.markdown(f'''<div class="ih-risk-hero" style="{background}">
        <div class="ih-risk-hero-title">Farm Risk Assessment</div>
        <div class="ih-risk-hero-subtitle">Review key risks and get practical recommendations.</div>
        </div>''', unsafe_allow_html=True)
    st.markdown('''<style>
    .ih-risk-hero{min-height:174px;border-radius:12px;display:flex;flex-direction:column;
      justify-content:flex-end;padding:28px;margin:0 0 17px;color:white;}
    .ih-risk-hero-title{font-size:clamp(25px,3vw,35px);font-weight:800;line-height:1.12;color:white;}
    .ih-risk-hero-subtitle{font-size:14px;margin-top:7px;color:#f2faf5;}
    .ih-risk-section{color:#17251d;font-weight:750;font-size:21px;margin:13px 0 8px;}
    .ih-risk-card{min-height:203px;border:1px solid #dfeae3;border-radius:12px;background:white;
      padding:14px 15px 10px;box-shadow:0 3px 14px #083c1810;}
    .ih-risk-card-title{display:flex;align-items:center;gap:10px;color:#17251d;font-weight:750;
      font-size:16px;min-height:37px;}
    .ih-risk-card-icon{font-size:26px;line-height:1;}
    .ih-risk-badge{font-size:12px;font-weight:700;border-radius:8px;padding:5px 10px;display:inline-block;margin:3px 0 8px;}
    .ih-risk-description{font-size:13px;color:#354b3d;line-height:1.55;min-height:77px;}
    .ih-risk-foot{font-size:11px;color:#5b7065;margin-top:8px;}
    @media(max-width:760px){.ih-risk-hero{min-height:138px;padding:20px}.ih-risk-card{min-height:unset}}
    </style>''',unsafe_allow_html=True)
    if not user:
        st.info('Sign in and register a field to review its risks.')
        return
    owner = user['id']
    fields, error = _fetch_or_none(F.list_fields,owner)
    if error:
        st.error('Your field records are unavailable. Please try again.')
        return
    if not fields:
        st.info('Register a field in My fields before assessing its risks.')
        if st.button('Go to My fields',type='primary'):
            _navigate_to('My fields',None)
        return
    choices = {f['id']: f for f in fields}
    suggested = st.session_state.get('ihinga_active_field_id')
    stored = st.session_state.get('risk_field_id')
    default_id = stored if stored in choices else (suggested if suggested in choices else fields[0]['id'])
    ctl1,ctl2=st.columns([3.8,1.35],vertical_alignment='bottom')
    with ctl1:
        field_id=st.selectbox('Field',list(choices),index=list(choices).index(default_id),
            format_func=lambda fid:(f"{choices[fid].get('name','Field')} · "
              f"{L.CROPS.get(str(choices[fid].get('crop_code')),{}).get('en','Crop')} · "
              f"{(float(choices[fid].get('area_sqm') or 0)/10000):g} ha"),key='risk_field_select_v2')
    field=choices[field_id]
    st.session_state['risk_field_id']=field_id
    with ctl2:
        refresh=st.button('↻ Refresh assessment',key='risk_refresh_v2',type='primary',use_container_width=True)
    weather_key=f'risk_weather_{owner}_{field_id}'
    if refresh:
        with st.spinner('Checking latest district forecast…'):
            forecast,error=_fetch_or_none(district_weather,district_label(field['district_code']))
        st.session_state[weather_key]=forecast if not error else None
        if error: st.warning('District weather is unavailable. Weather risk remains not assessed.')
    forecast=st.session_state.get(weather_key)
    estimates,_=_fetch_or_none(F.list_estimates,owner,field_id)
    activities,_=_fetch_or_none(F.list_activities,owner,field_id)
    observations,_=_fetch_or_none(E.observations,owner,field_id)
    try:
        from core import field_intelligence as FI
        transactions_fn=getattr(FI,'transactions',None)
    except ImportError: transactions_fn=None
    if transactions_fn is None:
        try:
            from core import season as SEASON
            transactions_fn=getattr(SEASON,'transactions',None)
        except ImportError: transactions_fn=None
    rows,_=_fetch_or_none(transactions_fn,owner,field_id) if transactions_fn else (None,'No transaction interface')
    market_df=st.session_state.get('ihinga_market_df')
    risks=[_weather(forecast), _production(_recent_estimate(estimates or [])),
           _market(field,market_df),_activities(activities or []),_finances(rows),_health(observations or [])]
    st.markdown('<div class="ih-risk-section">Risk overview</div>',unsafe_allow_html=True)
    st.caption('These are evidence-based screening indicators, not crop-loss probabilities. A missing assessment is not a low-risk result.')
    for rownum in range(2):
        cols=st.columns(3,gap='small')
        for j in range(3):
            risk=risks[rownum*3+j]
            emoji,button,page,color=_risk_visual(risk['category'])
            name,bg,fg=_risk_badge(risk['level'])
            with cols[j]:
                with st.container(border=True):
                    st.markdown(f'''<div class="ih-risk-card-title"><span class="ih-risk-card-icon">{emoji}</span>
                      <span>{html.escape(risk['category'])}</span></div>
                      <span class="ih-risk-badge" style="background:{bg};color:{fg}">{name}</span>
                      <div class="ih-risk-description">{html.escape(risk['evidence'])}</div>''',unsafe_allow_html=True)
                    if st.button(button,key=f'risk_open_{risk["category"].replace(" ","_")}',
                                 type='primary',use_container_width=True):
                        _navigate_to(page,field_id)
                    with st.expander('Why this assessment? / What can I do?'):
                        st.write('**Recommended action:**',risk['action'])
                        st.caption('Evidence source: '+risk['source'])
    with st.expander('Market data and assessment information'):
        st.caption('Market data must come from dated source records. No sample or invented price data are used.')
        if st.button('Load recorded market prices',key='risk_load_market_prices_v2'):
            try:
                from core.market_prices import _download_csv
                with st.spinner('Loading published observations…'):
                    loaded=_download_csv()
                st.session_state['ihinga_market_df']=loaded
                st.session_state['ihinga_market_origin']='TangaBid published CSV'
                st.success(f'Loaded {len(loaded):,} dated observations. Refresh to review them.')
            except Exception:
                st.warning('Recorded price source is unavailable. Open Market Prices to load a dated CSV.')
        df=st.session_state.get('ihinga_market_df')
        if isinstance(df,pd.DataFrame) and not df.empty:
            st.caption(f"Price observations loaded: {len(df):,} · {st.session_state.get('ihinga_market_origin','imported source')}")
        st.caption('Weather is retrieved only on Refresh; latest field records are reread on each page visit.')
    st.download_button('Download this field’s risk review (CSV)',
        pd.DataFrame(risks).to_csv(index=False).encode('utf-8-sig'),
        file_name='IhingaAI_field_risk_review.csv',mime='text/csv')
    st.caption('Sources: Open-Meteo district forecast, saved NISR-based harvest estimates, dated market records and farmer-entered observations. Assessments do not diagnose crop disease or guarantee outcomes.')

def planner_risk_page(field_registry_loader):
    """Planner-level data quality / production exposure overview, using existing authorized aggregates.

    Does not expose farmer symptoms, accounts, finances, private risk records, or individual fields.
    """
    st.title('🛡️ Farm Risk Assessment — Planning Overview')
    st.caption('Coverage and production uncertainty in registered-app records. This is not a district population-risk estimate.')
    try:
        _data, df = field_registry_loader()
    except Exception:
        st.warning('Planning records are unavailable at the moment.'); return
    if not isinstance(df,pd.DataFrame) or df.empty:
        st.info('No registered field records are available for an aggregate review.');return
    df=df.copy()
    count=len(df)
    estimates=int(df['estimate_kg'].notna().sum()) if 'estimate_kg' in df else 0
    a,b,c=st.columns(3)
    a.metric('Registered fields', f'{count:,}')
    b.metric('Fields with estimates',f'{estimates:,}')
    c.metric('Missing estimates',f'{count-estimates:,}')
    st.caption('Only information from app-registered fields is counted. Fields without saved estimates need follow-up; missing estimates are not classified as low risk.')
    # Publish grouped totals only for sufficiently populated groups; avoid single-field disclosure.
    for col, heading in [('district_name','District overview'),('crop_name','Crop overview')]:
        if col not in df.columns: continue
        st.subheader(heading)
        grouped=df.groupby(col,dropna=False).agg(
            fields=(col,'size'),
            estimates=('estimate_kg',lambda v:int(v.notna().sum()))
        ).reset_index() if 'estimate_kg' in df.columns else df.groupby(col,dropna=False).size().rename('fields').reset_index()
        if 'estimates' not in grouped:grouped['estimates']=0
        grouped=grouped[grouped['fields']>=5].copy()
        if grouped.empty:
            st.info('Not enough registered fields to publish group-level results (minimum five fields per group).')
        else:
            grouped['Missing estimates']=grouped['fields']-grouped['estimates']
            st.dataframe(grouped.rename(columns={col:'Group','fields':'Registered fields','estimates':'With estimates'}),hide_index=True,use_container_width=True)
    st.info('Planner view is aggregated. Individual farmer weather, finances and crop-health data remain in the farmer workspace, subject to existing permissions.')
    st.caption('Sources: IhingaAI registered-field records and historical NISR-based model estimates, where saved. No field-level risk probabilities are inferred.')
