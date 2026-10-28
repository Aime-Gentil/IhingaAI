from pathlib import Path
import html
import base64
import json
from collections import Counter
from datetime import timedelta, date

import pandas as pd
import streamlit as st

from core.accounts import init_db, register, login, get_farmer, connect
from core import fields as F
from core import ai_assistant as AI
from core import smartfarm as S
from core import engagement as E
from core import assignments as AS
from core import agro_map as AG
from core.router import IhingaRouter
from core import labels as L
from core import navigation as NAV
from core import season as FS
from core import consultations as CON
from core import photo_journal as PJ
from core import estimate_store as EST
from core.market_prices import market_prices_page
from core.risk_assessment import risk_assessment_page, planner_risk_page

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / 'data'

from functools import lru_cache

@lru_cache(maxsize=20)
def image_url_local(relative_path):
    """Embed an existing local JPEG without browser network requests."""
    file_path = ROOT / 'assets' / relative_path
    if not file_path.is_file():
        return ''
    return 'data:image/jpeg;base64,' + base64.b64encode(file_path.read_bytes()).decode('ascii')

st.set_page_config(page_title='IhingaAI • Smarter Farming Together', page_icon=str(ROOT / 'assets/brand/favicon.png'), layout='wide', initial_sidebar_state='expanded')
st.markdown(f'<style>{(ROOT / "assets/theme.css").read_text(encoding="utf-8")}</style>', unsafe_allow_html=True)
init_db()
F.init_fields()
S.init_smart()
E.init_engagement()
AS.init_assignments()
FS.init_season()
CON.init_consultations()
PJ.init_photos()
EST.init_store()


@st.cache_resource
def get_router():
    return IhingaRouter(DATA_DIR)


@st.cache_data
def get_districts():
    return L.load_districts()


def fmt_kg(x):
    return '<1' if x < 1 else f'{x:,.0f}'


def range_bar(low, est, high):
    top = high * 1.15 if high > 0 else 1.0
    lo, e, hi = 100*low/top, 100*est/top, 100*high/top
    return ('<div style="position:relative;height:22px;background:#e7f0e7;border-radius:13px;margin:12px 0 19px">'
            f'<div style="position:absolute;left:{lo:.1f}%;width:{hi-lo:.1f}%;top:0;bottom:0;background:#a4d6ac;border-radius:13px"></div>'
            f'<div style="position:absolute;left:calc({e:.1f}% - 3px);width:6px;top:-5px;bottom:-5px;background:#1d6c42;border-radius:3px"></div></div>')


def T(key, **kw):
    return L.t(key, st.session_state.lang, **kw)


def bilingual(en, rw):
    return rw if st.session_state.lang == 'rw' else en


def feature(icon, title, caption):
    st.markdown(f'<div class="feature"><div class="em">{icon}</div><strong>{html.escape(title)}</strong><span>{html.escape(caption)}</span></div>', unsafe_allow_html=True)


def hero(kicker, title, subtitle):
    st.markdown(f'<div class="hero"><div class="eyebrow">{html.escape(kicker)}</div><h1>{html.escape(title)}</h1><p>{html.escape(subtitle)}</p></div>', unsafe_allow_html=True)


def user_now():
    uid = st.session_state.get('farmer_id')
    if not uid:
        return None
    user = get_farmer(uid)
    if not user:
        st.session_state.farmer_id = None
    return user


def district_label(code):
    dl = get_districts(); d = dl['districts'][code]
    return d['name'] + ' — ' + dl['provinces'][d['province_code']][st.session_state.lang]


def brand_logo_html(width=110, background='white'):
    """Safe local brand mark with consistent aspect ratio in every portal."""
    path = ROOT / 'assets/brand/ihingaai_logo.png'
    raw = base64.b64encode(path.read_bytes()).decode('ascii')
    return (f'<div class="ih-logo-container" style="max-width:{int(width)}px;background:{background};">'
            f'<img src="data:image/png;base64,{raw}" alt="IhingaAI — Data Insights Impact" '
            'style="width:100%;height:auto;display:block;object-fit:contain" />'
            '</div>')


def about_ihingaai():
    """Shared sources, honest limitations and product information for all roles."""
    st.markdown('<div class="ih-about-head"><h1>About IhingaAI</h1>'
                '<p>Smarter Farming Together · Data, insights and impact</p></div>',unsafe_allow_html=True)
    st.markdown('IhingaAI helps farmers and agricultural professionals understand field records, '
                'explore harvest estimates and make more informed farming decisions. '
                'It is a decision-support tool, not a guarantee of future results.')
    st.subheader('Data sources and acknowledgements')
    cards=[
        ('🌾','Agricultural statistics — NISR',
         '2025 Seasonal Agricultural Survey records underpin the frozen harvest prediction models. '
         'Historical observations are not current field measurements.',
         'https://www.statistics.gov.rw/'),
        ('🌦️','Weather — Open-Meteo',
         'Forecasts are calculated for approximate district reference locations. '
         'They may differ from conditions at a particular farm.',
         'https://open-meteo.com/'),
        ('🛒','Market information — TangaBid / eSoko',
         'Dated market-price records are displayed only when source data is available. '
         'Market observations are not real-time offers or guaranteed sale prices.',
         'https://www.tangabid.com/market/prices/'),
        ('🤖','AI assistance — Google Gemini',
         'Optional AI-generated advice and photo reviews may contain errors and are not '
         'professional diagnoses. Availability depends on the configured service.',
         'https://ai.google.dev/'),
    ]
    for start in (0,2):
        columns=st.columns(2)
        for col,(icon,title,description,url) in zip(columns,cards[start:start+2]):
            with col:
                with st.container(border=True):
                    st.markdown(f'### {icon} {title}')
                    st.write(description)
                    st.link_button('Visit source',url)
    with st.expander('Research sources not used in live harvest predictions'):
        st.write('ISRIC SoilGrids and Sentinel-2 via Google Earth Engine were evaluated in research. '
                 'They are not live inputs to the frozen 14-crop models.')
    st.subheader('Interpreting results responsibly')
    st.info('Harvest figures are model estimates, risk assessments depend on available records, '
            'weather forecasts can change, and market prices may be historical. '
            'If supporting data is missing, do not interpret missing information as low risk.')
    st.caption('Source methodology and redistribution permissions should be confirmed before public release.')


def landing_page():
    st.markdown(brand_logo_html(110),unsafe_allow_html=True)
    st.markdown('<div class="landing-copy"><h1>Better planning.<br>Brighter harvests.</h1><p>Your farming assistant.</p></div>', unsafe_allow_html=True)
    if st.button('Get started', type='primary', key='landing_start'):
        st.session_state.entry_screen = 'login'
        st.rerun()


def authenticate():
    st.markdown(brand_logo_html(105)+ '<div class="auth-heading"><h2>Welcome to IhingaAI</h2><p>Choose how you want to continue.</p></div>', unsafe_allow_html=True)
    st.session_state.setdefault('portal_mode', 'farmer')
    mode = st.session_state.portal_mode
    c1, c2, c3 = st.columns(3, gap='small')
    if c1.button('Farmer', use_container_width=True, type='primary' if mode == 'farmer' else 'secondary'):
        st.session_state.portal_mode = 'farmer'; st.rerun()
    if c2.button('Agronomist', use_container_width=True, type='primary' if mode == 'agronomist' else 'secondary'):
        st.session_state.portal_mode = 'agronomist'; st.rerun()
    if c3.button('Planner / Admin', use_container_width=True, type='primary' if mode == 'planner' else 'secondary'):
        st.session_state.portal_mode = 'planner'; st.rerun()
    st.divider()
    if mode == 'farmer':
        st.markdown('#### Farmer access')
        option = st.segmented_control(bilingual('Get started', 'Tangira'), ['Login', 'Create account'], default='Login', key='auth_option')
        if option == 'Create account':
            st.subheader(bilingual('Create your farmer account', 'Fungura konti y’umuhinzi'))
            st.caption(bilingual('No SMS or email verification is required.', 'Nta kwemeza ukoresheje SMS cyangwa imeyili bisabwa.'))
            with st.form('signup', clear_on_submit=False):
                name = st.text_input(bilingual('Full name', 'Amazina yose'), max_chars=100, placeholder='Jean Claude')
                phone = st.text_input(bilingual('Phone number', 'Nomero ya telefoni'), placeholder='0788 123 456')
                password = st.text_input(bilingual('Create password (8+ characters)', 'Hitamo ijambo ry’ibanga (inyuguti 8+)'), type='password')
                confirm = st.text_input(bilingual('Confirm password', 'Subiramo ijambo ry’ibanga'), type='password')
                ok = st.form_submit_button(bilingual('Create my account →', 'Fungura konti →'), type='primary', use_container_width=True)
            if ok:
                if password != confirm:
                    st.error(bilingual('Passwords do not match.', 'Amagambo y’ibanga ntabwo ahuye.'))
                else:
                    try:
                        user = register(name, phone, password)
                        st.session_state.farmer_id = user['id']
                        st.session_state.page = 'Home'
                        st.rerun()
                    except ValueError as exc:
                        st.error(str(exc))
        else:
            st.subheader(bilingual('Welcome back', 'Murakaza neza'))
            with st.form('signin'):
                phone = st.text_input(bilingual('Phone number', 'Nomero ya telefoni'), placeholder='0788 123 456')
                password = st.text_input(bilingual('Password', 'Ijambo ry’ibanga'), type='password')
                ok = st.form_submit_button(bilingual('Log in →', 'Injira →'), type='primary', use_container_width=True)
            if ok:
                user, err = login(phone, password)
                if err:
                    st.error(err)
                else:
                    st.session_state.farmer_id = user['id']
                    st.session_state.page = 'Home'
                    st.rerun()
        st.caption(bilingual('Demo account only. Use a unique password, not your bank or email password.', 'Iyi ni konti y’igerageza. Koresha ijambo ry’ibanga ridasanzwe.'))
        if st.button(bilingual('Explore estimates without an account', 'Reba igereranya nta konti'), use_container_width=True):
            st.session_state.guest = True
            st.session_state.page = 'Estimate'
            st.rerun()
    elif mode == 'agronomist':
        st.markdown('#### Agronomist portal')
        st.caption('Review consent-shared fields, compare farmer records, and send notes back to farmers.')
        tab1, tab2 = st.tabs(['Sign in', 'Create demo agronomist profile'])
        with tab1:
            with st.form('advisor_login'):
                phone = st.text_input('Phone number', key='ag_phone')
                pw = st.text_input('Password', type='password', key='ag_password')
                if st.form_submit_button('Sign in', type='primary', use_container_width=True):
                    account = S.advisor_login(phone, pw)
                    if account:
                        st.session_state.advisor_id = account['id']
                        st.rerun()
                    else:
                        st.error('Phone or password incorrect.')
        with tab2:
            with st.form('advisor_register'):
                nm = st.text_input('Full name'); ph = st.text_input('Phone', key='new_ag_phone'); pw = st.text_input('Password (min. 8 characters)', type='password', key='new_ag_pass')
                if st.form_submit_button('Create profile', type='primary', use_container_width=True):
                    try:
                        S.create_agronomist(nm, ph, pw); st.success('Account created. Sign in using the other tab.')
                    except ValueError as exc:
                        st.error(str(exc))
    else:
        st.markdown('#### Planner / admin portal')
        st.caption('See cross-farmer summaries, field distribution, estimated production, and operational planning information.')
        tab1, tab2 = st.tabs(['Sign in', 'Create planner profile'])
        with tab1:
            with st.form('planner_login'):
                phone = st.text_input('Phone number', key='pl_phone')
                pw = st.text_input('Password', type='password', key='pl_password')
                if st.form_submit_button('Sign in', type='primary', use_container_width=True):
                    account = S.planner_login(phone, pw)
                    if account:
                        st.session_state.planner_id = account['id']
                        st.rerun()
                    else:
                        st.error('Phone or password incorrect.')
        with tab2:
            with st.form('planner_register'):
                nm = st.text_input('Full name', key='pl_name'); ph = st.text_input('Phone', key='new_pl_phone'); pw = st.text_input('Password (min. 8 characters)', type='password', key='new_pl_pass')
                setup_code = st.text_input('Administrator setup code', type='password', help='Obtain this from the app administrator; it is configured locally in secrets.toml.')
                if st.form_submit_button('Create profile', type='primary', use_container_width=True):
                    try:
                        S.create_planner_authorized(nm, ph, pw, setup_code); st.success('Planner account created. Sign in using the other tab.')
                    except (ValueError, PermissionError) as exc:
                        st.error(str(exc))
    st.caption('Demonstration accounts. Professional roles are not independently verified.')
    if st.button('Back to landing page', key='back_to_landing'):
        st.session_state.entry_screen = 'landing'
        st.rerun()


def estimate(router):
    section_banner('Harvest | Model-based forecast', bilingual('Harvest Estimator','Igereranya ry’umusaruro'), bilingual('Estimate likely crop production using your farm details and historical evidence.','Gereranya umusaruro ushingiye ku makuru y’umurima wawe.'), 'farmer', 'estimate')
    if st.session_state.lang == 'rw':
        st.caption(T('draft_rw'))
    st.markdown('### ' + bilingual('01 · Crop & season', '01 · Igihingwa n’igihembwe'))
    c1, c2 = st.columns(2)
    crop_codes = sorted(router.crops(), key=lambda c: L.CROPS[c][st.session_state.lang])
    with c1:
        crop = st.selectbox(T('crop'), crop_codes, format_func=lambda c: L.CROPS[c][st.session_state.lang])
    with c2:
        season = st.selectbox(T('season'), router.seasons(crop), format_func=lambda s: L.SEASONS[s][st.session_state.lang])
    st.caption(T('other_crops_note'))
    st.markdown('### ' + bilingual('02 · Your field', '02 · Umurima wawe'))
    dl = get_districts()
    district_codes = sorted(dl['districts'], key=lambda c: (dl['districts'][c]['province_code'], dl['districts'][c]['name']))
    c1,c2 = st.columns(2)
    with c1:
        district = st.selectbox(T('district'), district_codes, format_func=district_label, index=None, placeholder=T('choose'))
    with c2:
        ft = st.selectbox(T('farmer_type'), list(L.FARMER_TYPES), format_func=lambda k: L.FARMER_TYPES[k][st.session_state.lang])
    c1,c2 = st.columns([1,2])
    with c1:
        unit = st.radio(T('area_unit'), ['sqm', 'ha'], format_func=lambda u: T(u), horizontal=True)
    with c2:
        area = st.number_input(T('area'), min_value=0.0, value=None, step=50.0 if unit=='sqm' else 0.01,
                               format='%.2f' if unit=='ha' else '%.0f', help=T('area_help'))
    harvest = None
    if router.catalog[crop]['harvest_question']:
        ans = st.radio(T('harvest_q'), ['yes','no'], format_func=lambda k: T(k), horizontal=True)
        harvest = ans == 'yes'
    st.markdown('### ' + bilingual('03 · Your estimate', '03 · Igereranya ry’umusaruro'))
    current_signature=(crop,season,district,ft,unit,float(area or 0),harvest)
    if st.session_state.get('estimate_input_signature') != current_signature:
        st.session_state.pop('pending_estimate',None)
    if st.button('  ' + T('submit'), type='primary', use_container_width=True):
        st.session_state.pop('pending_estimate',None)
        if district is None or not area:
            st.error(T('missing'))
        else:
            area_kw = {'plot_area_sqm':area} if unit == 'sqm' else {'plot_area_ha':area}
            res = router.predict(crop, season, district, ft, harvest_this_season=harvest, **area_kw)
            if res['status'] == 'ok':
                st.subheader(T('likely_range'))
                st.caption(T('evidence_' + res['evidence']))
                x,y,z = st.columns(3)
                x.metric(T('low'), fmt_kg(res['lower_kg'])+' kg')
                y.metric(T('typical'),fmt_kg(res['estimate_kg'])+' kg')
                z.metric(T('high'),fmt_kg(res['upper_kg'])+' kg')
                st.markdown(range_bar(res['lower_kg'],res['estimate_kg'],res['upper_kg']),unsafe_allow_html=True)
                st.write(T('range_sentence',low=fmt_kg(res['lower_kg']),high=fmt_kg(res['upper_kg']),crop=L.CROPS[crop][st.session_state.lang+'_s']))
                st.caption(T('coverage',n=res['coverage_in_10']))
                st.caption(T('guide'))
                for warning in res['warnings']:
                    st.warning(T(warning))
                st.session_state.estimate_input_signature=current_signature
                st.session_state.pending_estimate = {'crop':crop,'season':season,'district':district,'ft':ft,'area_sqm':area*(10000 if unit=='ha' else 1),'harvest':harvest,'result':res}
            elif res['status'] == 'invalid_input':
                st.error(T('status_invalid_input'))
            else:
                st.info(T('status_' + res['status']))
    if st.session_state.get('pending_estimate',{}).get('result',{}).get('status') == 'ok':
        st.markdown('<div class="next-step-label">NEXT STEP · PERSONALIZED GUIDANCE</div>',unsafe_allow_html=True)
        st.caption('Answer a short set of questions to get suggestions related to your current farm conditions. The model estimate will not be changed.')
        if st.button('Get AI-generated recommendations', key='guided_from_estimate', type='primary',use_container_width=True):
            st.session_state.page='Guided recommendations'
            st.session_state.nav_target='Guided recommendations'
            st.rerun()
    pending=st.session_state.get('pending_estimate')
    if pending and st.session_state.get('farmer_id'):
        st.divider()
        st.subheader(bilingual(' Save your last estimate',' Bika igereranya rya nyuma'))
        p=pending
        st.caption(f"{L.CROPS[p['crop']][st.session_state.lang]} · {L.SEASONS[p['season']][st.session_state.lang]} · {fmt_kg(p['result']['estimate_kg'])} kg")
        matching=[f for f in F.list_fields(st.session_state.farmer_id) if f['crop_code']==p['crop'] and f['season']==p['season'] and f['district_code']==p['district'] and abs(f['area_sqm']-p['area_sqm'])<0.01 and f['farmer_type_code']==p['ft'] and f['harvest_this_season']==(None if p['harvest'] is None else int(p['harvest']))]
        if matching:
            target=st.selectbox(bilingual('Matching field','Umurima uhuye'),matching,format_func=lambda f:f['name'],key='matching_field')
            if st.button(bilingual('Save estimate to field','Bika igereranya mu murima'),key='save_estimate_button',type='primary'):
                F.save_estimate(st.session_state.farmer_id,target['id'],{k:p[k] for k in ['crop','season','district','ft','area_sqm','harvest']},p['result'])
                st.session_state.pop('pending_estimate',None)
                st.success(bilingual('Estimate saved successfully.','Igereranya ryabitswe neza.'))
        else:
            st.info(bilingual('Create a matching field in My fields, or calculate directly from a registered field.','Andika umurima uhuye cyangwa gereranya umusaruro uhereye ku murima wanditse.'))
    # Independent save is optional; does not register a field or change prediction.
    if pending and pending.get('result',{}).get('status')=='ok' and st.session_state.get('farmer_id'):
        st.markdown('#### Save this estimate independently')
        st.caption('Save this prediction to your private history, without registering a field. You may also skip.')
        left,right=st.columns(2)
        if left.button('Save estimate to my history',key='save_independent_estimate',type='primary',use_container_width=True):
            try:
                snapshot={k:pending[k] for k in ('crop','season','district','ft','area_sqm','harvest')}
                saved_id=EST.save(st.session_state.farmer_id,snapshot,pending['result'])
                st.session_state.pop('pending_estimate',None)
                st.success(f'Estimate saved to your private history (#{saved_id}).')
                st.rerun()
            except (ValueError,PermissionError) as e:
                st.error(str(e))
        if right.button('Continue without saving',key='skip_independent_estimate',use_container_width=True):
            st.session_state.pop('pending_estimate',None)
            st.info('Estimate not saved. You can continue using IhingaAI.')
            st.rerun()
    with st.expander(T('about_title')):
        st.markdown(T('about_body'))


def field_form(owner,router,existing=None):
    fid=existing['id'] if existing else None
    st.subheader(bilingual('Edit field' if existing else 'Register a field','Hindura umurima' if existing else 'Andika umurima'))
    crop_codes=sorted(router.crops(),key=lambda c:L.CROPS[c][st.session_state.lang])
    crop=st.selectbox(T('crop'),crop_codes,index=crop_codes.index(existing['crop_code']) if existing else 0,format_func=lambda x:L.CROPS[x][st.session_state.lang],key='field_crop_'+str(fid))
    with st.form('field_form_'+str(fid)):
        name=st.text_input(bilingual('Field name','Izina ry’umurima'),value=existing['name'] if existing else '',placeholder='e.g. Hillside plot',max_chars=80)
        c1,c2=st.columns(2)
        with c1:
            st.caption(bilingual('Selected crop','Igihingwa wahisemo')+': '+L.CROPS[crop][st.session_state.lang])
        with c2:
            possible=router.seasons(crop)
            season=st.selectbox(T('season'),possible,index=possible.index(existing['season']) if existing and existing['season'] in possible else 0,format_func=lambda s:L.SEASONS[s][st.session_state.lang])
        c1,c2=st.columns(2)
        with c1:
            dl=get_districts()['districts']; codes=sorted(dl,key=lambda x:district_label(x))
            district=st.selectbox(T('district'),codes,index=codes.index(existing['district_code']) if existing else None,format_func=district_label,placeholder=T('choose'))
        with c2:
            ft=st.selectbox(T('farmer_type'),list(L.FARMER_TYPES),index=list(L.FARMER_TYPES).index(existing['farmer_type_code']) if existing else 0,format_func=lambda x:L.FARMER_TYPES[x][st.session_state.lang])
        c1,c2=st.columns(2)
        with c1:
            unit=st.radio(T('area_unit'),['sqm','ha'],format_func=lambda u:T(u),horizontal=True,key='field_unit_'+str(fid))
        with c2:
            initial=(existing['area_sqm']/(10000 if unit=='ha' else 1)) if existing else 0.0
            area=st.number_input(T('area'),min_value=0.,value=float(initial),step=0.01 if unit=='ha' else 10.,format='%.4f' if unit=='ha' else '%.1f')
        seed=st.selectbox(bilingual('Seed type (record only)','Ubwoko bw’imbuto'),['unknown','local','improved'],index=['unknown','local','improved'].index(existing['seed_type']) if existing else 0,format_func=lambda x:{'unknown':'Not specified','local':'Local','improved':'Improved'}[x])
        planting=st.date_input(bilingual('Planting date (optional)','Itariki yo gutera'),value=date.fromisoformat(existing['planting_date']) if existing and existing['planting_date'] else None)
        practices=st.text_area(bilingual('Planned practices (notes only)','Ibikorwa uteganya'),value=existing['planned_practices'] if existing else '',max_chars=1500)
        answer=None
        if router.catalog[crop]['harvest_question']:
            opts=['unknown','yes','no']
            current=('unknown' if not existing or existing['harvest_this_season'] is None else ('yes' if existing['harvest_this_season'] else 'no'))
            answer=st.selectbox(T('harvest_q'),opts,index=opts.index(current),format_func=lambda x:{'unknown':'Not sure yet','yes':'Yes','no':'No'}[x])
        save=st.form_submit_button(bilingual(' Save field',' Bika umurima'),type='primary',use_container_width=True)
    st.caption(bilingual('Seed type, planting date and planned practices are records, not inputs to the prediction model.','Amakuru y’imbuto n’ibikorwa by’ubuhinzi ntabwo akoreshwa na moderi.'))
    if save:
        if district is None or area<=0:
            st.error(bilingual('Select a district and enter a positive area.','Hitamo akarere n’ubuso burenze zeru.'));return
        val=None if answer in (None,'unknown') else answer=='yes'
        kw=dict(name=name,crop=crop,season=season,district=district,area_sqm=area*(10000 if unit=='ha' else 1),farmer_type=ft,seed=seed,planting=planting.isoformat() if planting else None,practices=practices,harvest=val)
        try:
            if fid: F.update_field(owner,fid,**kw)
            else: F.create_field(owner,**kw)
            st.session_state.edit_field=None
            st.success(bilingual('Field saved.','Umurima wabitswe.'));st.rerun()
        except ValueError as exc: st.error(str(exc))


def _field_page_header(title, subtitle):
    """Decorative photo header, with accessible text and an offline gradient fallback."""
    st.markdown(f"""<section class="ih-field-hero"><div class="ih-field-hero-content">
        <h1>{html.escape(str(title))}</h1><p>{html.escape(str(subtitle))}</p>
        </div></section>""", unsafe_allow_html=True)


def _field_actions_nav(label, page, field_id, key):
    if st.button(label, key=key, use_container_width=True):
        st.session_state['selected_field'] = field_id
        st.session_state['page'] = page
        st.session_state['nav_target'] = page
        st.rerun()


def _field_detail(user, router, field_id):
    """Owner-validated field detail view; reuses Phase 14 field services."""
    owner = user['id']
    f = F.get_field(owner, field_id)
    if not f:
        st.session_state.pop('field_detail_id', None)
        st.error(bilingual('Field not found or no longer accessible.', 'Umurima ntubonetse.'))
        if st.button('Back to My Fields', key='back_missing_field'):
            st.rerun()
        return
    if st.button('← ' + bilingual('Back to My Fields', 'Subira ku mirima'), key='back_field_detail'):
        st.session_state.pop('field_detail_id', None)
        st.rerun()
    _field_page_header(f['name'], f"{L.CROPS[f['crop_code']][st.session_state.lang]} · Season {f['season']} · {district_label(f['district_code'])}")
    es = F.list_estimates(owner, f['id'])
    tasks = F.list_activities(owner, f['id'])
    reports = F.list_harvest_reports(owner, f['id'])
    c1,c2,c3,c4 = st.columns(4)
    c1.metric(bilingual('Area (m²)', 'Ubuso (m²)'), f"{f['area_sqm']:,.0f}")
    c2.metric(bilingual('Saved estimates','Amagereranya'),len(es))
    c3.metric(bilingual('Open activities','Ibikorwa bisigaye'),sum(not t['completed'] for t in tasks))
    c4.metric(bilingual('Harvest reports','Raporo y’umusaruro'),len(reports))

    st.subheader(bilingual('Field details','Ibisobanuro by’umurima'))
    with st.container(border=True):
        a,b = st.columns(2)
        with a:
            st.write('**'+bilingual('Crop','Igihingwa')+':**',L.CROPS[f['crop_code']][st.session_state.lang])
            st.write('**'+bilingual('Season','Igihembwe')+':**',L.SEASONS[f['season']][st.session_state.lang])
            st.write('**'+bilingual('District','Akarere')+':**',district_label(f['district_code']))
            st.write('**'+bilingual('Area','Ubuso')+':**',f"{f['area_sqm']:,.0f} m² ({f['area_sqm']/10000:,.3f} ha)")
        with b:
            st.write('**Seed type:**',f['seed_type'])
            st.write('**Planting date:**',f['planting_date'] or '—')
            st.write('**Farmer type:**',L.FARMER_TYPES.get(f['farmer_type_code'],{}).get(st.session_state.lang,f['farmer_type_code']))
            st.write('**Planned practices:**',f['planned_practices'] or '—')

    st.subheader(bilingual('Field actions','Ibikorwa by’uyu murima'))
    x,y,z = st.columns(3)
    with x: _field_actions_nav('🌱 Crop monitoring','Crop monitoring', f['id'],f'detail_crop_{f["id"]}')
    with y: _field_actions_nav('📅 Farming season','My farming season', f['id'],f'detail_season_{f["id"]}')
    with z: _field_actions_nav('💰 Farm finances','Farm finances', f['id'],f'detail_finances_{f["id"]}')
    x,y,z=st.columns(3)
    with x: _field_actions_nav('☀️ District weather','Weather', f['id'],f'detail_weather_{f["id"]}')
    with y: _field_actions_nav('🛡️ Farm risk assessment','Farm Risk Assessment', f['id'],f'detail_risk_{f["id"]}')
    with z: _field_actions_nav('🤝 Agronomist support','Agronomist support', f['id'],f'detail_support_{f["id"]}')
    st.caption('These shortcuts open existing IhingaAI modules. Where a module has its own field selector, choose this field there.')

    with st.expander(bilingual('Calculate and save a harvest estimate','Gereranya umusaruro ubike'),expanded=True):
        if router.catalog[f['crop_code']]['harvest_question'] and f['harvest_this_season'] is None:
            st.warning(bilingual('Edit this field and answer the harvest question before estimating.','Subiza ikibazo cy’umusaruro mbere yo kugereranya.'))
        elif f['harvest_this_season']==0 and router.catalog[f['crop_code']]['harvest_question']:
            st.info(T('status_no_harvest_this_season'))
        elif st.button(bilingual('Calculate & save estimate','Gereranya ubike'),key=f'field_predict_{f["id"]}',type='primary'):
            try:
                result=router.predict(f['crop_code'],f['season'],f['district_code'],f['farmer_type_code'],plot_area_sqm=f['area_sqm'],harvest_this_season=None if f['harvest_this_season'] is None else bool(f['harvest_this_season']))
                if result['status']=='ok':
                    inputs={k:f[k] for k in ['crop_code','season','district_code','farmer_type_code','area_sqm','harvest_this_season']}
                    F.save_estimate(owner,f['id'],inputs,result)
                    st.success(bilingual('Estimate calculated and saved.','Igereranya ryabitswe.'))
                    st.rerun()
                else:
                    st.warning(T('status_'+result['status']))
            except (ValueError, PermissionError) as exc:
                st.error(str(exc))
    st.subheader(bilingual('Saved estimates','Amagereranya yabitswe'))
    if es:
        rows=[]
        for e in es:
            r=json.loads(e['output_json'])
            rows.append({'Date':e['created_at'],'Estimate (kg)':r.get('estimate_kg'),'Lower (kg)':r.get('lower_kg'),'Upper (kg)':r.get('upper_kg'),'Model':e['model_version']})
        st.dataframe(pd.DataFrame(rows),use_container_width=True,hide_index=True)
        with st.expander('Latest estimate warnings and evidence'):
            latest_result=json.loads(es[0]['output_json'])
            st.write('Evidence:',latest_result.get('evidence','—'))
            st.write('Coverage out of 10:',latest_result.get('coverage_in_10','—'))
            for warning in latest_result.get('warnings',[]):
                st.warning(T(warning))
    else:
        st.info('No estimates saved for this field yet.')

    st.subheader(bilingual('Field activities','Ibikorwa by’umurima'))
    with st.form(f'field_detail_task_{f["id"]}',clear_on_submit=True):
        title=st.text_input('New activity',max_chars=180)
        due=st.date_input('Due date (optional)',value=None)
        submitted=st.form_submit_button('Add activity',type='primary')
        if submitted:
            try:
                F.add_activity(owner,f['id'],title,due.isoformat() if due else None)
                st.rerun()
            except ValueError as exc: st.error(str(exc))
    for t in tasks:
        a,b=st.columns([8,1])
        checked=a.checkbox(t['title']+(f" · {t['due_date']}" if t['due_date'] else ''),value=bool(t['completed']),key=f'field_detail_task_done_{t["id"]}')
        if checked!=bool(t['completed']):
            F.set_activity_done(owner,t['id'],checked)
            st.rerun()
        if b.button('✕',key=f'field_detail_task_delete_{t["id"]}',help='Delete activity'):
            F.delete_activity(owner,t['id'])
            st.rerun()

    st.subheader(bilingual('Harvest reports','Raporo z’umusaruro'))
    with st.form(f'field_detail_harvest_{f["id"]}'):
        actual_kg=st.number_input('Actual harvest (kg)',min_value=0.0,value=0.0,step=1.0)
        reported_date=st.date_input('Report date',value=date.today())
        notes=st.text_area('Notes (optional)',max_chars=1200)
        submitted=st.form_submit_button('Save harvest report',type='primary')
        if submitted:
            try:
                F.report_actual_harvest(owner,f['id'],actual_kg,reported_date.isoformat(),notes)
                st.rerun()
            except (ValueError,PermissionError) as exc: st.error(str(exc))
    if reports:
        st.dataframe(pd.DataFrame([{'Date':r['reported_date'],'Harvest (kg)':r['actual_kg'],'Notes':r['notes']} for r in reports]),hide_index=True,use_container_width=True)
    else:
        st.caption('No actual harvest recorded yet.')
    if st.button('✎ Edit field details',key=f'edit_from_detail_{f["id"]}'):
        st.session_state.edit_field=f['id']
        st.session_state.pop('field_detail_id',None)
        st.rerun()


def my_fields(user,router):
    owner=user['id']
    fields=F.list_fields(owner)
    current_id=st.session_state.get('field_detail_id')
    if current_id is not None:
        _field_detail(user,router,current_id)
        return
    _field_page_header(bilingual('My Fields','Imirima yanjye'),bilingual('Manage your fields and keep your farm information up to date.','Genzura imirima yawe n’amakuru yayo.'))
    x,y=st.columns([4,1.4],vertical_alignment='center')
    x.markdown('### '+bilingual('Your Fields','Imirima yawe'))
    if y.button('＋ '+bilingual('Register New Field','Andika umurima mushya'),type='primary',use_container_width=True,key='register_new_field'):
        st.session_state.edit_field='new'
        st.rerun()
    chosen=st.session_state.get('edit_field')
    if chosen is not None:
        with st.container(border=True):
            if st.button('✕ Close form',key='close_field_editor'):
                st.session_state.edit_field=None
                st.rerun()
            existing=F.get_field(owner,chosen) if chosen!='new' else None
            if chosen=='new' or existing:
                field_form(owner,router,existing)
            else:
                st.error('Selected field is not available.')
                st.session_state.edit_field=None
    if not fields:
        st.info(bilingual('No fields registered yet. Use Register New Field to begin.','Nta mirima irandikwa.'))
    for f in fields:
        fid=f['id']
        with st.container(border=True):
            details,view,edit,delete=st.columns([5.8,1.05,1.05,1.15],vertical_alignment='center')
            with details:
                st.markdown(f"<div class='ih-field-title'>{html.escape(f['name'])} — {html.escape(L.CROPS[f['crop_code']][st.session_state.lang])}</div>",unsafe_allow_html=True)
                st.caption(f"🌾 {L.SEASONS[f['season']][st.session_state.lang]}    ·    {f['area_sqm']:,.0f} m²    ·    {district_label(f['district_code'])}")
            if view.button(bilingual('View','Reba'),key=f'field_view_{fid}',use_container_width=True):
                st.session_state.field_detail_id=fid
                st.rerun()
            if edit.button(bilingual('Edit','Hindura'),key=f'field_edit_{fid}',use_container_width=True):
                st.session_state.edit_field=fid
                st.rerun()
            if delete.button(bilingual('Delete','Siba'),key=f'field_delete_{fid}',use_container_width=True):
                st.session_state.field_delete_confirm_id=fid
                st.rerun()
            if st.session_state.get('field_delete_confirm_id')==fid:
                st.warning('Deleting this field also deletes its linked estimates, activities and harvest reports. This cannot be undone.')
                confirm=st.checkbox('I understand that the linked history will be deleted.',key=f'field_ack_delete_{fid}')
                c1,c2=st.columns(2)
                if c1.button('Permanently delete field',key=f'field_confirm_delete_{fid}',type='primary',disabled=not confirm):
                    if F.delete_field(owner,fid):
                        st.session_state.pop('field_delete_confirm_id',None)
                        st.session_state.pop('edit_field',None)
                        st.rerun()
                    else: st.error('The field was not deleted.')
                if c2.button('Cancel',key=f'field_cancel_delete_{fid}'):
                    st.session_state.pop('field_delete_confirm_id',None)
                    st.rerun()
    st.divider()
    st.subheader(bilingual('Recent Saved Estimates','Amagereranya ya vuba'))
    rows=[]
    for f in fields:
        for e in F.list_estimates(owner,f['id']):
            result=json.loads(e['output_json'])
            rows.append({'Date':e['created_at'],'Crop':L.CROPS[f['crop_code']]['en'],'Season':f['season'],
                         'Area (ha)':round(f['area_sqm']/10000,4),'Estimate (kg)':result.get('estimate_kg'),
                         'Range (kg)':f"{result.get('lower_kg',0):,.0f}–{result.get('upper_kg',0):,.0f}",
                         '_field_id':f['id']})
    for item in EST.recent(owner,limit=100):
        inp=json.loads(item['input_json']);result=json.loads(item['output_json'])
        rows.append({'Date':item['created_at'],'Crop':L.CROPS.get(inp['crop'],{}).get('en',inp['crop']),
                     'Season':inp['season'],'Area (ha)':round(inp['area_sqm']/10000,4),
                     'Estimate (kg)':result.get('estimate_kg'),
                     'Range (kg)':f"{result.get('lower_kg',0):,.0f}–{result.get('upper_kg',0):,.0f}",
                     '_field_id':None})
    if rows:
        rows.sort(key=lambda r:r['Date'],reverse=True)
        frame=pd.DataFrame(rows[:100]).drop(columns=['_field_id'])
        st.dataframe(frame,use_container_width=True,hide_index=True)
        st.caption('Includes field-linked estimates and independently saved predictions. Original inputs and model outputs remain stored.')
    else:
        st.info('No saved estimates yet. Use Harvest Estimator or open a field to calculate one.')

def activities_page(user):
    owner=user['id']; all_fields=F.list_fields(owner)
    section_banner('Your fields | Activities',bilingual('Farm activities','Ibikorwa by’ubuhinzi'),bilingual('Plan, complete and review activities for registered fields.','Tegura kandi ukurikirane ibikorwa by’imirima.'),'farmer','activities')
    st.caption(bilingual('Your own reminders, not automatic agronomic recommendations.','Ibyibutsa wanditse, si inama z’ubuhinzi zatanzwe na sisitemu.'))
    if not all_fields:
        st.info(bilingual('Register a field before creating activities.','Banza wandike umurima.'));return
    with st.container(border=True):
        st.subheader(bilingual('Add an activity','Ongeraho igikorwa'))
        with st.form('new_activity',clear_on_submit=True):
            field=st.selectbox(bilingual('Field','Umurima'),all_fields,format_func=lambda f:f['name'])
            title=st.text_input(bilingual('Activity (e.g. inspect for pests)','Igikorwa'),max_chars=180)
            due=st.date_input(bilingual('Due date (optional)','Itariki (ushobora kutayishyiraho)'),value=None)
            if st.form_submit_button(bilingual('Add activity','Ongeraho'),type='primary'):
                try:
                    F.add_activity(owner,field['id'],title,due.isoformat() if due else None)
                    st.success(bilingual('Activity added.','Igikorwa cyongeweho.'));st.rerun()
                except ValueError as exc: st.error(str(exc))
    tasks=F.list_activities(owner)
    if not tasks: st.info(bilingual('No activities yet.','Nta bikorwa birandikwa.'))
    else:
        for t in tasks:
            with st.container(border=True):
                c1,c2=st.columns([7,1])
                with c1:
                    done=st.checkbox(t['title'],value=bool(t['completed']),key='task_'+str(t['id']))
                    if done!=bool(t['completed']): F.set_activity_done(owner,t['id'],done);st.rerun()
                    st.caption(f" {t['field_name']} ·  {t['due_date'] or 'No due date'}")
                with c2:
                    if st.button('',key='task_del_'+str(t['id']),help='Delete activity'):
                        F.delete_activity(owner,t['id']);st.rerun()


def guided_recommendations(user):
    section_banner('IhingaAI | Farm guidance','Recommendations for your field','Tell the assistant what is happening on your farm before receiving practical suggestions.','farmer')
    pending=st.session_state.get('pending_estimate')
    fields=F.list_fields(user['id']) if user else []
    selected=None
    if pending and pending['result'].get('status')=='ok':
        st.success(f"Recent estimate: {L.CROPS[pending['crop']]['en']} · Season {pending['season']} · {fmt_kg(pending['result']['estimate_kg'])} kg")
        context={
            'crop': L.CROPS[pending['crop']]['en'], 'season':pending['season'],
            'district':district_label(pending['district']),
            'area_hectares':round(pending['area_sqm']/10000,4),
            'saved_model_estimate':{
                'estimate_kg':pending['result']['estimate_kg'],
                'lower_kg':pending['result']['lower_kg'],
                'upper_kg':pending['result']['upper_kg'],
                'evidence':pending['result'].get('evidence'),
                'coverage_out_of_10':pending['result'].get('coverage_in_10'),
                'warning_codes':pending['result'].get('warnings',[]),
                'note':'Experimental historical estimate, not a guarantee; Gemini must not recalculate it.'},
        }
        matching=[f for f in fields if f['crop_code']==pending['crop'] and f['season']==pending['season'] and f['district_code']==pending['district']]
        if matching:
            selected=st.selectbox('Registered field (optional, for saving approved tasks)',[None]+matching,
                                  format_func=lambda f:'Do not link a field' if f is None else f['name'],key='guided_link_field')
    elif fields:
        selected=st.selectbox('Select a field',fields,format_func=lambda f:f['name'],key='guided_existing_field')
        previous=F.list_estimates(user['id'],selected['id'])
        context=AI.field_context(selected,previous[0] if previous else None,district_label(selected['district_code']),L.CROPS[selected['crop_code']]['en'])
    else:
        st.info('First calculate a crop estimate, or register a field to receive tailored advice.');return
    st.markdown('### Tell us about your current field conditions')
    with st.form('guided_recommendation_form'):
        c1,c2=st.columns(2)
        with c1:
            stage=st.radio('Current crop stage',['Not yet planted','Just planted / germination','Vegetative growth','Flowering / fruiting','Maturing / near harvest','Not sure'],key='guided_stage')
            water=st.radio('Water / rainfall conditions',['Adequate rainfall or irrigation','Too little water / dry soil','Too much water / waterlogging','Not sure'],key='guided_water')
        with c2:
            visible=st.multiselect('What are you noticing?',['Weeds','Insect pests','Leaf spots or discoloration','Poor growth','Wilting','Soil erosion','No visible issue','Not sure'],key='guided_symptoms')
            fertilizer=st.selectbox('Fertilizer or manure use',['Not applied','Organic manure/compost','Mineral fertilizer','Both organic and mineral','Not sure'],key='guided_fert')
        current=st.text_area('What actions have you already taken? (optional)',placeholder='For example: weeded last week, irrigated twice, applied compost...',max_chars=900)
        question=st.text_area('Anything else you would like advice on? (optional)',placeholder='For example: What should I prioritize this week?',max_chars=500)
        st.warning('Advice is educational and may be incorrect. For pests, diseases, fertilizer rates, and serious crop problems, consult a qualified local agronomist.')
        consent=st.checkbox('I agree to send these responses and selected field/estimate information to Google Gemini. My account name and phone will not be sent.')
        submitted=st.form_submit_button('Generate my recommendations',type='primary',use_container_width=True)
    if submitted:
        if not consent:st.error('Consent is required before contacting Gemini.')
        elif not AI.api_key():st.error('Add your Gemini API key in .streamlit/secrets.toml first.')
        else:
            answers={'crop_stage':stage,'water_condition':water,'observed_issues':visible,'fertilizer_or_manure':fertilizer,'actions_already_taken':current,'farmer_question':question}
            context['farmer_reported_conditions']=answers
            prompt=('Using the farmer-reported observations and existing historical estimate, give a clear, practical priority list. '
                    'Explain any limitations, and specify when a qualified agronomist should be contacted. '
                    'Ask at most two follow-up questions if the observations are insufficient. '
                    'Do not assume the reported symptoms prove a disease; do not prescribe product rates. '
                    'The numerical estimate must remain unchanged.')
            try:
                with st.spinner('Preparing field-specific suggestions…'):
                    st.session_state.guided_output=AI.call_gemini(AI.api_key(),prompt,context,language=st.session_state.lang)
                st.session_state.guided_field_id=selected['id'] if selected else None
                st.rerun()
            except Exception as e:st.error(f'Gemini could not generate recommendations. Technical detail: {str(e)[:230]}')
    response=st.session_state.get('guided_output')
    if response:
        st.markdown('### Your recommendations')
        with st.container(border=True):st.write(response['answer'])
        for q in response.get('questions',[]):st.info('Further question: '+q)
        if response.get('actions'):
            st.markdown('#### Suggested activities')
            for i,action in enumerate(response['actions']):
                with st.container(border=True):
                    st.markdown('**'+html.escape(action['title'])+'**')
                    st.caption(action['reason'])
                    fid=st.session_state.get('guided_field_id')
                    if user and fid and st.button('Add to my field activities',key=f'guided_action_{i}_{fid}'):
                        try:F.add_activity(user['id'],fid,action['title']);st.success('Activity saved to your field.')
                        except (PermissionError,ValueError) as e:st.error(str(e))
        st.info('Need specific fertilizer, pesticide, or disease advice? Contact your assigned agronomist or local agricultural extension service before taking action.')
        if user and st.button('Go to agronomist support'):
            st.session_state.page='Agronomist support';st.rerun()


def assistant_page(user):
    role_chat('farmer', {'id':user['id'],'name':user['full_name']})


@st.cache_data(ttl=3600, show_spinner=False)
def district_weather(district):
    return S.weather_for_district(district)


def weather_page(user):
    section_banner('Weather | District reference',bilingual('District Weather','Iteganyagihe ry’akarere'),bilingual('Check weather forecasts to plan your farming activities.','Reba iteganyagihe kugira ngo utegure ibikorwa by’ubuhinzi.'),'farmer','weather')
    st.caption('Open-Meteo · Approximate district reference point, not a surveyed district centroid or a measurement at your field. Forecasts can change.')
    fields=F.list_fields(user['id'])
    if fields:
        field=st.selectbox('Select a field',fields,format_func=lambda f:f['name']+' · '+district_label(f['district_code']))
        district=district_label(field['district_code'])
    else:
        st.info('Register a field to see its approximate district forecast.');return
    try:
        forecast=district_weather(district)
    except Exception as exc:
        st.warning('Live weather is temporarily unavailable. Try again later; your fields and estimates are safe.')
        with st.expander('Technical information'):st.code(str(exc)[:250])
        return
    st.caption(f"Forecast reference point: {forecast['location']} ({forecast['latitude']:.3f}, {forecast['longitude']:.3f}) · not plot-specific · Retrieved (UTC): {forecast['retrieved_at_utc']}")
    rows=forecast['daily']
    a,b,c=st.columns(3)
    a.metric('Next-day maximum temperature',f"{rows[1]['max_c']} °C" if len(rows)>1 else '—')
    b.metric('Forecast rain, next 7 days',f"{sum((r['rain_mm'] or 0) for r in rows):.1f} mm")
    c.metric('Days with forecast rain',sum((r['rain_mm'] or 0)>0.5 for r in rows))
    st.markdown('### Three-day forecast')
    short=rows[:3]
    if short:
        cols=st.columns(len(short))
        for col, r in zip(cols, short):
            with col:
                with st.container(border=True):
                    st.markdown('#### 🌤️ '+html.escape(str(r['date'])))
                    st.metric('Maximum',f"{r['max_c']} °C" if r.get('max_c') is not None else '—')
                    st.caption(f"Minimum: {r['min_c']} °C · Rain: {r['rain_mm']} mm · Chance: {r['rain_chance']}%")
    st.markdown('### Full forecast records')
    st.dataframe([{'Date':r['date'],'Min °C':r['min_c'],'Max °C':r['max_c'],'Rain (mm)':r['rain_mm'],'Rain probability (%)':r['rain_chance']} for r in rows], hide_index=True, use_container_width=True)
    st.info('Use this forecast to plan observations; do not treat it as confirmed rainfall at your field. Ask a local agronomist about high-stakes farm decisions.')
    st.caption('Prototype weather points are approximate and require geographic validation for deployment. Open-Meteo attribution: open-meteo.com. Review provider terms before wider use.')


def calendar_page(user):
    section_banner('Your season | Calendar',bilingual('Farming calendar','Kalindari y’ubuhinzi'),bilingual('Upcoming field activities and important recorded dates.','Amatariki y’ibikorwa by’ubuhinzi.'),'farmer','calendar')
    fields=F.list_fields(user['id']); tasks=F.list_activities(user['id'])
    if not fields:st.info('Register a field first.');return
    choice=st.selectbox('Field', [None]+fields,format_func=lambda f:'All fields' if f is None else f['name'])
    fid=choice['id'] if choice else None
    entries=[]
    for f in fields:
        if (fid is None or f['id']==fid) and f['planting_date']:
            entries.append({'date':f['planting_date'],'event':' Planted / planned planting','field':f['name'],'status':'Recorded by farmer'})
    for t in tasks:
        if t['due_date'] and (fid is None or t['field_id']==fid):
            entries.append({'date':t['due_date'],'event':t['title'],'field':t['field_name'],'status':'Completed' if t['completed'] else ('Overdue' if t['due_date']<date.today().isoformat() else 'Planned')})
    if entries:
        entries.sort(key=lambda e:e['date'])
        st.dataframe([{'Date':e['date'],'Field':e['field'],'Activity':e['event'],'Status':e['status']} for e in entries],hide_index=True,use_container_width=True)
        st.caption('Dates are based only on the farmer’s entries. No automatic crop schedules are assumed.')
    else:st.info('Add planting dates or tasks with due dates to populate the calendar.')
    st.subheader('Add activity')
    with st.form('calendar_task'):
        ff=st.selectbox('Field for this activity',fields,format_func=lambda f:f['name'])
        title=st.text_input('Action',max_chars=180)
        due=st.date_input('Target date',value=date.today())
        if st.form_submit_button('Save activity',type='primary'):
            try:F.add_activity(user['id'],ff['id'],title,due.isoformat());st.success('Activity saved');st.rerun()
            except ValueError as exc:st.error(str(exc))




def farming_season_page(user):
    """One season workspace links existing field journal, activities and calendar."""
    section_banner('Your season | Field journey','My farming season',
        'Track each field from preparation to harvest. Stages are chosen by you—not predicted by AI.', 'farmer')
    owner=user['id']; fields=F.list_fields(owner)
    if not fields:
        st.info('Register a field under My fields to start your farming season.')
        if st.button('Go to My fields',type='primary'):
            st.session_state.page='My fields'; st.rerun()
        return
    stage_records=FS.progress(owner)
    observations=E.observations(owner)
    tasks=F.list_activities(owner)
    money=FS.transactions(owner)
    flags=FS.local_alerts(owner,fields,tasks,observations)
    a,b,c,d=st.columns(4)
    a.metric('Registered fields',len(fields))
    b.metric('Open activities',sum(not t['completed'] for t in tasks))
    c.metric('Items to review',len(flags))
    d.metric('Recorded costs',f"{FS.totals(money)['expenses']:,.0f} RWF")
    tab1,tab2,tab3=st.tabs(['Field journey','Activities','Calendar'])
    with tab1:
        selected=st.selectbox('Follow a field',fields,format_func=lambda f:f['name']+' · '+L.CROPS[f['crop_code']]['en'],key=f'season_field_{owner}')
        current=stage_records.get(selected['id'],{'stage':'Planning','note':'','updated_at':None})
        pos=FS.STAGES.index(current['stage']) if current['stage'] in FS.STAGES else 0
        st.markdown(f"**{html.escape(selected['name'])}** · {L.CROPS[selected['crop_code']]['en']} · Season {selected['season']}")
        st.progress(pos/(len(FS.STAGES)-1), text=f"Stage {pos+1} of {len(FS.STAGES)}: {current['stage']}")
        st.caption('The stage reflects your report. It is not a remote or sensor measurement.')
        with st.form(f'stage_{owner}_{selected["id"]}'):
            new_stage=st.selectbox('Current stage',FS.STAGES,index=pos)
            note=st.text_area('What changed? (optional)',value=current.get('note',''),max_chars=500)
            if st.form_submit_button('Update field stage',type='primary'):
                try:
                    FS.set_stage(owner,selected['id'],new_stage,note)
                    st.success('Season progress saved.');st.rerun()
                except (ValueError,PermissionError) as exc:st.error(str(exc))
        planting=selected.get('planting_date') or 'Not recorded'
        related_tasks=[t for t in tasks if t['field_id']==selected['id']]
        related_obs=[o for o in observations if o['field_id']==selected['id']]
        related_fin=FS.totals([t for t in money if t['field_id']==selected['id']])
        x,y,z=st.columns(3)
        x.metric('Planting date',planting)
        y.metric('Completed tasks',f"{sum(t['completed'] for t in related_tasks)}/{len(related_tasks)}")
        z.metric('Crop check-ins',len(related_obs))
        with st.container(border=True):
            st.subheader('Field journal snapshot')
            st.write('**Recorded field practices:**',selected.get('planned_practices') or 'Not recorded')
            st.write('**Latest crop observation:**',related_obs[0]['symptom'] if related_obs else 'No observations yet')
            st.write('**Recorded cash position:**',f"{related_fin['net']:,.0f} RWF")
            st.caption('Cash position uses only expenses and sales entered in Farm finances.')
            actions=st.columns(3)
            for i,(label,target) in enumerate((('Monitor crop','Crop monitoring'),('Farm finances','Farm finances'),('Review alerts','Smart alerts'))):
                if actions[i].button(label,use_container_width=True,key=f'season_go_{i}'):
                    st.session_state.page=target;st.rerun()
    with tab2:
        activities_page(user)
    with tab3:
        calendar_page(user)


def farm_finances_page(user):
    """Simple cash ledger in RWF, not accounting or guaranteed profitability."""
    section_banner('Farmer tools | Money management','Farm expenses & sales',
        'Record actual purchases and harvest sales per field. Figures are private to this account.', 'farmer', 'finances')
    owner=user['id']; fields=F.list_fields(owner)
    if not fields:
        st.info('Register a field before entering farm expenses or sales.');return
    choice=st.selectbox('View field finances',[None]+fields,format_func=lambda f:'All my fields' if f is None else f['name'],key=f'finance_field_{owner}')
    rows=FS.transactions(owner,choice['id'] if choice else None)
    summary=FS.totals(rows)
    x,y,z=st.columns(3)
    x.metric('Recorded expenses',f"{summary['expenses']:,.0f} RWF")
    y.metric('Recorded sales',f"{summary['revenue']:,.0f} RWF")
    z.metric('Net recorded cash',f"{summary['net']:+,.0f} RWF")
    st.caption('Net recorded cash = entered sales − entered expenses. It is NOT a final profit calculation if other costs, sales or harvests are missing.')
    with st.container(border=True):
        st.subheader('Record a transaction')
        kind=st.radio('Transaction type',['expense','sale'],horizontal=True,format_func=lambda x:'Expense' if x=='expense' else 'Harvest sale', key=f'finance_type_{owner}')
        with st.form(f'finance_entry_{owner}_{kind}',clear_on_submit=True):
            f=st.selectbox('Your field',fields,format_func=lambda x:x['name'],
                           index=next((i for i,x in enumerate(fields) if choice and x['id']==choice['id']),0))
            c1,c2=st.columns(2)
            with c1:
                category=st.selectbox('Cost category',FS.EXPENSE_CATEGORIES) if kind=='expense' else 'Harvest sale'
                amount=st.number_input('Amount paid / received (RWF)',min_value=0.0,value=0.0,step=500.0)
            with c2:
                when=st.date_input('Transaction date',value=date.today(),max_value=date.today())
                qty=st.number_input('Quantity sold (kg, optional)',min_value=0.0,value=0.0,step=1.0) if kind=='sale' else None
            note=st.text_input('Note (optional)',max_chars=600,placeholder='e.g. fertilizer bought at local shop')
            if st.form_submit_button('Save transaction',type='primary'):
                try:
                    FS.add_transaction(owner,f['id'],kind,category,amount,when,note,qty if qty and kind=='sale' else None)
                    st.success('Transaction saved to this field.');st.rerun()
                except (ValueError,PermissionError) as exc:st.error(str(exc))
    if not rows:
        st.info('No recorded farm expenses or sales yet. Add a transaction to see the analysis.');return
    df=pd.DataFrame(rows)
    st.markdown('### Profit & cash flow over time')
    st.caption('Interactive record of sales, expenses and cumulative net cash. Hover for amounts; zoom or select a date range to explore changes.')
    choice_window=st.segmented_control('Time range',['All recorded','Last 30 days','Last 90 days'],default='All recorded',key=f'profit_window_{owner}')
    trend=df.copy()
    trend['Date']=pd.to_datetime(trend['transaction_date'])
    if choice_window=='Last 30 days':trend=trend[trend['Date']>=pd.Timestamp(date.today()-timedelta(days=29))]
    if choice_window=='Last 90 days':trend=trend[trend['Date']>=pd.Timestamp(date.today()-timedelta(days=89))]
    if not trend.empty:
        sums=trend.assign(Expense=lambda x:x['amount_rwf'].where(x['kind']=='expense',0),
                          Sales=lambda x:x['amount_rwf'].where(x['kind']=='sale',0)).groupby('Date',as_index=False)[['Expense','Sales']].sum().sort_values('Date')
        sums['Net cash']=sums['Sales'].cumsum()-sums['Expense'].cumsum()
        import plotly.graph_objects as go
        fig=go.Figure()
        fig.add_trace(go.Scatter(x=sums['Date'],y=sums['Net cash'],mode='lines+markers',name='Net cash',
                line=dict(color='#267549',width=4,shape='linear'),marker=dict(size=7,color='#267549'),
                fill='tozeroy',fillcolor='rgba(57,132,82,.11)',hovertemplate='%{x|%d %b %Y}<br>Net cash: %{y:,.0f} RWF<extra></extra>'))
        fig.add_hline(y=0,line_width=1,line_dash='dot',line_color='#A67C41')
        fig.update_layout(height=355,margin=dict(t=25,l=12,r=12,b=20),paper_bgcolor='rgba(0,0,0,0)',
               plot_bgcolor='rgba(245,249,241,.5)',hovermode='x unified',
               xaxis=dict(title='',rangeslider=dict(visible=len(sums)>8,thickness=.065),showgrid=False),
               yaxis=dict(title='RWF',tickformat=','),showlegend=False,dragmode='zoom')
        st.plotly_chart(fig,use_container_width=True,config={'displaylogo':False})
        last=float(sums['Net cash'].iloc[-1]);left_metric,right_metric=st.columns(2)
        left_metric.metric('Net cash for selected period',f'{last:+,.0f} RWF')
        right_metric.metric('Transactions in this period',len(trend))
        st.caption('A positive cash position is not confirmed profit: unpaid inputs, stock, labor and sales outside the app are not captured.')
    else:st.info('No transactions in the selected time range. Switch to all recorded dates.')
    with st.expander('Break-even and selling-price scenario'):
        st.caption('These are illustrative scenarios based on recorded transactions; no current market prices are assumed.')
        t=FS.totals(rows)
        if t['sold_kg']>0:
            st.metric('Recorded spending per kilogram sold',f"{t['cost_per_kg_sold']:,.0f} RWF/kg")
            st.caption('Includes all selected recorded expenses divided by kilograms recorded as sold; not a full production-cost estimate.')
        planned_kg=st.number_input('Additional kilograms you might sell',min_value=0.0,value=100.0,step=10.0,key=f'break_even_kg_{owner}')
        sale_price=st.number_input('Possible selling price (RWF/kg)',min_value=0.0,value=500.0,step=25.0,key=f'break_even_price_{owner}')
        potential=t['net']+planned_kg*sale_price
        st.metric('Illustrative net cash after those sales',f'{potential:+,.0f} RWF')
        if planned_kg>0:
            needed=max(0,-t['net'])/planned_kg
            st.caption(f'Price to cover the current recorded cash deficit with these additional sales: {needed:,.0f} RWF/kg. Additional costs are not included.')
    left,right=st.columns(2)
    import plotly.express as px
    with left:
        expenses=df[df['kind']=='expense'].groupby('category',as_index=False)['amount_rwf'].sum()
        if not expenses.empty:
            fig=px.pie(expenses,names='category',values='amount_rwf',hole=.55,color_discrete_sequence=['#164B35','#398452','#88A56F','#D7AB55','#B96F4D','#5D6F60','#C7D9B8','#7D8B56'])
            fig.update_layout(title='Where your money was spent',height=310,margin=dict(t=40,b=10,l=0,r=0),paper_bgcolor='rgba(0,0,0,0)')
            st.plotly_chart(fig,use_container_width=True)
        else:st.info('Add expenses to see the cost breakdown.')
    with right:
        if len(df):
            summary_by_date=df.groupby(['transaction_date','kind'],as_index=False)['amount_rwf'].sum()
            fig=px.bar(summary_by_date,x='transaction_date',y='amount_rwf',color='kind',barmode='group',
                       color_discrete_map={'expense':'#B96F4D','sale':'#398452'},labels={'amount_rwf':'RWF','transaction_date':'Date','kind':'Type'})
            fig.update_layout(title='Money in and out over time',height=310,margin=dict(t=40,b=10,l=0,r=0),paper_bgcolor='rgba(0,0,0,0)',legend_title_text='')
            st.plotly_chart(fig,use_container_width=True)
    st.subheader('Transaction history')
    st.dataframe(df.rename(columns={'transaction_date':'Date','field_name':'Field','kind':'Type','category':'Category','amount_rwf':'RWF','quantity_kg':'Sold kg','note':'Notes'})[['Date','Field','Type','Category','RWF','Sold kg','Notes']],hide_index=True,use_container_width=True)
    export=df.rename(columns={'transaction_date':'Date','field_name':'Field','kind':'Type','category':'Category','amount_rwf':'RWF','quantity_kg':'Sold kg','note':'Notes'})[['Date','Field','Type','Category','RWF','Sold kg','Notes']]
    st.download_button('Download my transaction history (CSV)',export.to_csv(index=False).encode('utf-8-sig'),
                       file_name='IhingaAI_farm_transactions.csv',mime='text/csv')
    with st.expander('Delete an incorrect entry'):
        record=st.selectbox('Select entry',rows,format_func=lambda t:f"{t['transaction_date']} · {t['field_name']} · {t['category']} · {t['amount_rwf']:,.0f} RWF",key=f'finance_delete_{owner}')
        confirm=st.checkbox('Confirm deletion of this transaction',key=f'finance_delete_confirm_{owner}')
        if st.button('Delete selected entry',disabled=not confirm):
            FS.delete_transaction(owner,record['id']);st.rerun()
    st.caption('A forecast harvest is not a completed sale. Financial reports include only transactions that you enter.')


def crop_health_progress_section(user,selected):
    """Evidence-based progress, never an invented disease severity score."""
    owner=user['id'];records=E.observations(owner,selected['id'])
    st.subheader('Crop health progress')
    st.caption('History of your recorded observations. Photos are sent for optional analysis but are not saved in the app.')
    if not records:
        st.info('Save an observation above to start tracking this field’s crop health.');return
    latest=records[0]
    a,b,c=st.columns(3)
    a.metric('Recorded check-ins',len(records))
    b.metric('Latest observed state',latest['symptom'])
    c.metric('Last check-in',str(latest['created_at'])[:10])
    if len(records)>1:
        import plotly.express as px
        plot=pd.DataFrame(records)
        plot['Date']=pd.to_datetime(plot['created_at']).dt.date
        counts=plot.groupby(['Date','symptom'],as_index=False).size().rename(columns={'size':'Checks','symptom':'Observation'})
        fig=px.bar(counts,x='Date',y='Checks',color='Observation',barmode='stack',
                   color_discrete_sequence=['#398452','#A5BA85','#D7AB55','#B96F4D','#164B35','#5D6F60'])
        fig.update_layout(height=290,title='Observation categories over time',paper_bgcolor='rgba(0,0,0,0)',margin=dict(t=42,b=10,l=0,r=0))
        st.plotly_chart(fig,use_container_width=True)
    st.dataframe([{'When':r['created_at'],'Crop stage':r['stage'],'What you saw':r['symptom'],
                   'Actions / notes':r['notes'],'AI assessment saved':bool(r['ai_summary'])} for r in records],hide_index=True,use_container_width=True)
    with st.expander('Previous AI reviews'):
        for r in records:
            if r['ai_summary']:
                st.caption(f"Review from {r['created_at']}")
                st.info(r['ai_summary'])
    st.markdown('#### My saved crop photographs')
    photos=PJ.list_photos(owner,selected['id'])
    if not photos:
        st.caption('No photographs retained. Use the save-photo checkbox next time you record an observation.')
    else:
        chosen=st.selectbox('Photo check-in',photos,
              format_func=lambda p:f"{p['created_at'][:10]} · {p['symptom']}",
              key=f'photo_review_{owner}_{selected["id"]}')
        image_bytes=PJ.photo('farmer',owner,chosen['observation_id'])
        if image_bytes:
            st.image(image_bytes,caption=f"{chosen['stage']} · {chosen['symptom']} · {chosen['created_at'][:10]}",width=520)
        if len(photos)>1:
            st.markdown('##### Compare crop photos')
            earlier=st.selectbox('Earlier photo',photos[1:],format_func=lambda p:f"{p['created_at'][:10]} · {p['symptom']}",key=f'photo_before_{owner}_{selected["id"]}')
            recent=st.selectbox('Later photo',photos,format_func=lambda p:f"{p['created_at'][:10]} · {p['symptom']}",key=f'photo_after_{owner}_{selected["id"]}')
            col_a,col_b=st.columns(2)
            col_a.image(PJ.photo('farmer',owner,earlier['observation_id']),caption=f"Earlier: {earlier['created_at'][:10]}",use_container_width=True)
            col_b.image(PJ.photo('farmer',owner,recent['observation_id']),caption=f"Later: {recent['created_at'][:10]}",use_container_width=True)
            st.caption('Photo differences alone cannot establish whether treatment worked. Lighting, angle, weather, and crop stage also change.')
        if st.button('Delete this saved photo',key=f'photo_delete_{owner}_{selected["id"]}'):
            PJ.delete_photo(owner,chosen['observation_id']);st.rerun()
        st.caption('Your observation text remains after you delete the saved photo. Only authorized assigned agronomists can view it.')
    st.warning('The trend reflects farmer-entered check-ins, not a continuous health measurement. Visible symptoms may have many causes; consult an agronomist before treatment.')


def smart_alerts_page(user):
    """On-demand transparent reminders; optional weather forecast checks."""
    section_banner('Your farm | Things to review','Smart farm alerts',
        'Review due activities, missed field check-ins and optional district weather forecasts.', 'farmer', 'alerts')
    owner=user['id'];fields=F.list_fields(owner)
    if not fields:
        st.info('Add a field under My fields to start receiving on-page reminders.');return
    tasks=F.list_activities(owner);observations=E.observations(owner)
    chosen=st.selectbox('Alerts for',[None]+fields,format_func=lambda f:'All my fields' if f is None else f['name'],key=f'alert_field_{owner}')
    alerts=FS.local_alerts(owner,fields,tasks,observations)
    if chosen:alerts=[a for a in alerts if a['field_id']==chosen['id']]
    c1,c2,c3=st.columns(3)
    c1.metric('Overdue activities',sum(x['level']=='Overdue' for x in alerts))
    c2.metric('Coming up',sum(x['level']=='Upcoming' for x in alerts))
    c3.metric('Check-ins to consider',sum(x['level']=='Check-in' for x in alerts))
    with st.expander('Check district rainfall forecast (optional)'):
        target=st.selectbox('Field for forecast',fields,
                index=next((i for i,x in enumerate(fields) if chosen and x['id']==chosen['id']),0),
                format_func=lambda x:x['name']+' · '+district_label(x['district_code']))
        st.caption('Weather is checked only when you request it. It uses an approximate district point, not your field’s location.')
        if st.button('Check the next 3 days',type='primary'):
            try:
                with st.spinner('Fetching approximate district forecast…'):
                    data=district_weather(district_label(target['district_code']))
                st.session_state[f'season_forecast_{owner}']={'field_id':target['id'],'items':FS.forecast_alerts(data,target['id'])}
            except Exception:
                st.warning('Forecast unavailable right now. Your saved field data is unaffected.')
        weather=st.session_state.get(f'season_forecast_{owner}')
        if weather and weather['field_id']==target['id']:
            if weather['items']:alerts=weather['items']+alerts
            else:st.success('No heavy-rain watch met the current rule in the selected three-day forecast.')
    if not alerts:
        st.success('No reminders require review according to your recorded activities and crop check-ins.')
    for alert in alerts:
        f=next((x for x in fields if x['id']==alert['field_id']),None)
        with st.container(border=True):
            a,b=st.columns([5,1])
            with a:
                st.markdown(f"**{html.escape(alert['title'])}**")
                st.caption(f"{f['name'] if f else 'Field'} · {alert['level']} · {alert['source']}")
                st.write(alert['detail'])
            with b:
                if alert['level']=='Overdue':st.error('Overdue')
                elif alert['level']=='Upcoming':st.warning('Soon')
                else:st.info('Review')
    st.caption('Alerts appear only when you open this page; they are not push notifications, crop diagnoses, or guaranteed weather warnings.')
    if st.button('Manage activity reminders',use_container_width=True):
        st.session_state.page='My farming season';st.rerun()


def farmer_consultations(user):
    """Farmer can open cases, read their own threads, and close them."""
    owner=user['id'];fields=F.list_fields(owner)
    st.markdown('### Consultation requests')
    st.caption('Ask an assigned agronomist for a review of a specific field. Your messages remain in your account.')
    if not AS.allows_assignment(owner):
        st.info('Enable agronomist assignment sharing above to request a new consultation.')
    else:
        with st.expander('Request a new consultation',expanded=False):
            if not fields:st.info('Register a field first.')
            else:
                target=st.selectbox('Field to discuss',fields,format_func=lambda f:f['name'],key=f'con_field_{owner}')
                choices=CON.available_advisors(owner,target['id'])
                if not choices:st.info('No agronomist currently assigned to this field. Ask a planner to assign one.')
                else:
                    advisor=st.selectbox('Assigned agronomist',choices,format_func=lambda a:a['name'],key=f'con_advisor_{owner}')
                    observations=E.observations(owner,target['id'])
                    chosen=st.selectbox('Related crop observation (optional)',[None]+observations,
                       format_func=lambda o:'Do not attach an observation' if o is None else f"{o['created_at'][:10]} · {o['symptom']}",
                       key=f'con_obs_{owner}')
                    with st.form(f'con_open_{owner}',clear_on_submit=True):
                        subject=st.text_input('What do you need help with?',max_chars=140)
                        message=st.text_area('Describe the problem and actions already taken',max_chars=2500)
                        send=st.form_submit_button('Send consultation request',type='primary')
                    if send:
                        try:
                            CON.open_request(owner,target['id'],advisor['id'],subject,message,chosen['id'] if chosen else None)
                            st.success('Request sent to your assigned agronomist.');st.rerun()
                        except (ValueError,PermissionError) as exc:st.error(str(exc))
    conversations=CON.consultations_for_farmer(owner)
    if not conversations:st.caption('You have no consultation requests yet.');return
    st.markdown('#### My consultations')
    for thread in conversations:
        with st.expander(f"{thread['subject']} · {thread['field_name']} · {thread['status']} · {thread['advisor_name']}"):
            st.caption(f"Started {thread['created_at']} · Replies received: {thread['replies']}")
            for msg in CON.messages('farmer',owner,thread['id']):
                with st.chat_message('user' if msg['sender_role']=='farmer' else 'assistant'):
                    st.caption('You' if msg['sender_role']=='farmer' else thread['advisor_name'])
                    st.write(msg['body'])
            if thread['status']!='Closed' and any(a['id']==thread['advisor_id'] for a in CON.available_advisors(owner,thread['field_id'])):
                with st.form(f"con_reply_f_{thread['id']}",clear_on_submit=True):
                    reply=st.text_area('Add follow-up',max_chars=2500)
                    if st.form_submit_button('Send follow-up'):
                        try:CON.reply('farmer',owner,thread['id'],reply);st.rerun()
                        except (ValueError,PermissionError) as exc:st.error(str(exc))
                if st.button('Mark consultation resolved',key=f"con_close_{thread['id']}"):
                    CON.close(owner,thread['id']);st.rerun()
            elif thread['status']=='Closed':st.caption('This request is closed. You can start another request if needed.')
            else:st.caption('This agronomist no longer has active sharing access; previous messages remain visible to you.')


def advisor_consultations(advisor):
    """Inbox only for currently assigned, consented farmer cases."""
    section_banner('Agronomist | Consultations','Farmer requests',
                   'Review questions from your assigned farmers and provide follow-up guidance.','agronomist')
    cases=CON.consultations_for_advisor(advisor['id'])
    a,b,c=st.columns(3)
    a.metric('Open requests',sum(x['status']=='Open' for x in cases))
    b.metric('Answered requests',sum(x['status']=='Responded' for x in cases))
    c.metric('Total accessible',len(cases))
    if not cases:st.info('No accessible consultation requests. This inbox updates when farmers send questions.');return
    for thread in cases:
        with st.expander(f"{thread['status']} · {thread['subject']} · {thread['farmer_name']} · {thread['field_name']}"):
            if thread['observation_id']:
                observations=E.observations_for_advisor(advisor['id'],thread['field_id'])
                attached=next((x for x in observations if x['id']==thread['observation_id']),None)
                if attached:
                    st.caption(f"Attached crop observation · {attached['created_at'][:10]} · {attached['symptom']}")
                    st.write(attached['notes'])
                    if attached['ai_summary']:st.info('Preliminary AI review: '+attached['ai_summary'])
                    try:
                        picture=PJ.photo('agronomist',advisor['id'],attached['id'])
                        if picture:st.image(picture,caption='Photo shared with the field observation',width=330)
                    except PermissionError:pass
            for msg in CON.messages('agronomist',advisor['id'],thread['id']):
                with st.chat_message('assistant' if msg['sender_role']=='agronomist' else 'user'):
                    st.caption('You' if msg['sender_role']=='agronomist' else thread['farmer_name'])
                    st.write(msg['body'])
            if thread['status']!='Closed':
                with st.form(f"con_reply_a_{thread['id']}",clear_on_submit=True):
                    response=st.text_area('Your advice or follow-up questions',max_chars=2500)
                    if st.form_submit_button('Send to farmer',type='primary'):
                        try:CON.reply('agronomist',advisor['id'],thread['id'],response);st.rerun()
                        except (ValueError,PermissionError) as exc:st.error(str(exc))
            else:st.caption('Closed by the farmer.')
    st.caption('Advice should be grounded in field evidence. Refer uncertain disease or treatment decisions for on-site professional verification.')


def sharing_page(user):
    st.title('Agronomist support')
    st.caption('Your planner can assign an agronomist to your registered fields when you allow it.')
    allowed=AS.allows_assignment(user['id'])
    new=st.toggle('Allow the planner to assign an agronomist to view my registered fields and give advice',value=allowed,key='assignment_consent')
    if new != allowed:
        AS.set_permission(user['id'],new)
        st.success('Sharing permission updated. Existing assignments are revoked if you turned it off.')
        st.rerun()
    st.info('Your account and phone information can be viewed by the assigned agronomist. Disable sharing here to immediately revoke assignment-based access.')
    farmer_consultations(user)
    st.subheader('Agronomist notes')
    notes=S.farmer_notes(user['id'])
    if not notes:st.caption('No notes yet.')
    for n in notes[:30]:
        with st.container(border=True):
            st.write(f"**{n['field_name']}** · {n['advisor_name']} · {n['created_at']}")
            st.write(n['note'])
    st.caption('Older invitation-code shares may still exist from previous versions. Review or revoke those below.')
    for sh in S.shares_for_farmer(user['id']):
        if sh['active']:
            c1,c2=st.columns([4,1]);c1.write(f"{sh['field_name']} — {sh['advisor_name'] or 'Pending invitation'}")
            if c2.button('Revoke old share',key=f"legacy_revoke_{sh['id']}"):
                S.revoke(user['id'],sh['id']);st.rerun()


def _planner_dataframes():
    with connect() as db:
        farmers = [dict(r) for r in db.execute('SELECT id, full_name, phone, created_at FROM farmers ORDER BY id DESC')]
        fields = [dict(r) for r in db.execute('''SELECT f.*, fm.full_name AS farmer_name, fm.phone AS farmer_phone
                                                FROM fields f JOIN farmers fm ON fm.id=f.farmer_id ORDER BY f.id DESC''')]
        estimates = [dict(r) for r in db.execute('SELECT * FROM estimates ORDER BY id DESC')]
        activities = [dict(r) for r in db.execute('''SELECT a.*, f.name AS field_name FROM activities a
                                                    JOIN fields f ON f.id=a.field_id ORDER BY a.id DESC''')]
        harvests = [dict(r) for r in db.execute('''SELECT h.*, f.name AS field_name FROM harvest_reports h
                                                  JOIN fields f ON f.id=h.field_id ORDER BY h.id DESC''')]
        shares = [dict(r) for r in db.execute('SELECT * FROM field_shares ORDER BY id DESC')]
    return {
        'farmers': pd.DataFrame(farmers),
        'fields': pd.DataFrame(fields),
        'estimates': pd.DataFrame(estimates),
        'activities': pd.DataFrame(activities),
        'harvests': pd.DataFrame(harvests),
        'shares': pd.DataFrame(shares),
    }


def _latest_estimate_metrics(estimates_df):
    rows=[]
    if estimates_df.empty:
        return pd.DataFrame(columns=['field_id','estimate_kg','lower_kg','upper_kg','evidence','created_at'])
    for _, row in estimates_df.iterrows():
        try:
            out = json.loads(row['output_json'])
        except Exception:
            continue
        if out.get('status') == 'ok':
            rows.append({'field_id': row['field_id'], 'estimate_kg': out.get('estimate_kg'), 'lower_kg': out.get('lower_kg'), 'upper_kg': out.get('upper_kg'), 'evidence': out.get('evidence'), 'estimate_created_at': row['created_at']})
    latest = pd.DataFrame(rows)
    if latest.empty:
        return pd.DataFrame(columns=['field_id','estimate_kg','lower_kg','upper_kg','evidence','estimate_created_at'])
    return latest.drop_duplicates(subset=['field_id'], keep='first')


def _latest_harvest_metrics(harvest_df):
    if harvest_df.empty:
        return pd.DataFrame(columns=['field_id','actual_kg','reported_date'])
    return harvest_df.drop_duplicates(subset=['field_id'], keep='first')[['field_id','actual_kg','reported_date']]


def _open_task_counts(activities_df):
    if activities_df.empty:
        return pd.DataFrame(columns=['field_id','open_tasks'])
    open_df = activities_df[activities_df['completed'] == 0]
    if open_df.empty:
        return pd.DataFrame(columns=['field_id','open_tasks'])
    return open_df.groupby('field_id', as_index=False).size().rename(columns={'size':'open_tasks'})


def _field_registry_df():
    data = _planner_dataframes()
    fields_df = data['fields'].copy()
    if fields_df.empty:
        return data, pd.DataFrame()
    latest_est = _latest_estimate_metrics(data['estimates'])
    latest_hv = _latest_harvest_metrics(data['harvests'])
    task_counts = _open_task_counts(data['activities'])
    fields_df = fields_df.merge(latest_est, left_on='id', right_on='field_id', how='left')
    fields_df = fields_df.merge(latest_hv, left_on='id', right_on='field_id', how='left', suffixes=('','_harvest'))
    fields_df = fields_df.merge(task_counts, left_on='id', right_on='field_id', how='left', suffixes=('','_tasks'))
    fields_df = ensure_analytics_columns(fields_df)
    fields_df['area_ha'] = fields_df['area_sqm'] / 10000.0
    fields_df['crop_name'] = fields_df['crop_code'].map(lambda c: L.CROPS.get(c, {}).get(st.session_state.lang, c))
    fields_df['district_name'] = fields_df['district_code'].map(district_label)
    return data, fields_df


def crop_monitoring(user):
    section_banner('Field care | Daily monitoring','Crop health monitoring',
        'Record field checks, review progress, and explore nearby mapped suppliers.', 'farmer', 'monitoring')
    owner=user['id']; fields=F.list_fields(owner)
    if not fields:
        st.info('Register a field first in My fields.');return
    selected=st.selectbox('Select field',fields,
        format_func=lambda f:f['name']+' · '+L.CROPS[f['crop_code']]['en'],key=f'monitor_field_{owner}')
    journal,progress_tab,suppliers=st.tabs(['Record crop check-in','Health progress & history','Agro-dealer map'])
    with journal:
        nonce=st.session_state.get(f'crop_upload_nonce_{owner}_{selected["id"]}',0)
        with st.form(f'new_crop_monitor_{owner}_{selected["id"]}_{nonce}'):
            stage=st.selectbox('Crop stage',['Germination','Vegetative growth','Flowering','Maturing','Near harvest','Not sure'])
            symptom=st.selectbox('Main observation',['Looks healthy','Unusual spots / discoloration','Wilting','Insect damage','Poor growth','Weeds','Other / not sure'])
            notes=st.text_area('Describe what you noticed and any actions already taken',max_chars=1200)
            photo=st.file_uploader('Optional crop photo (JPEG or PNG, max 4 MB)',type=['png','jpg','jpeg'],key=f'crop_photo_{owner}_{selected["id"]}_{nonce}')
            keep_photo=st.checkbox('Save this photo in my private crop-health timeline; my assigned agronomist may also view it while sharing is enabled (optional).')
            consent=st.checkbox('Request an AI photo review: I agree to send the photo and basic field details to Google Gemini (optional).')
            submit=st.form_submit_button('Save observation and review',type='primary')
        if submit:
            outcome=None
            if photo and photo.size>4*1024*1024:
                st.error('Photo must be smaller than 4 MB.');return
            cleaned_photo=None
            if photo:
                try:cleaned_photo=PJ._sanitize(photo.getvalue())
                except ValueError as exc:st.error(str(exc));return
            if photo and consent and not AI.api_key():
                st.warning('Gemini is not configured; your observation can still be saved without AI review.')
            if photo and consent and AI.api_key():
                context={'crop':L.CROPS[selected['crop_code']]['en'],
                         'district':district_label(selected['district_code']),
                         'season':selected['season'],'note':'No confirmed disease diagnosis'}
                try:
                    with st.spinner('Reviewing visible symptoms…'):
                        outcome=AI.inspect_crop_photo(AI.api_key(),cleaned_photo,'image/jpeg',context,
                            {'stage':stage,'symptoms':symptom,'notes':notes},st.session_state.lang)
                except Exception:
                    st.warning('Image review temporarily unavailable. Your written observation will still be recorded.')
            obs_id=E.add_observation(owner,selected['id'],stage,symptom,notes,outcome)
            if cleaned_photo and keep_photo:
                PJ.save_photo(owner,selected['id'],obs_id,cleaned_photo)
            st.session_state[f'crop_upload_nonce_{owner}_{selected["id"]}']=nonce+1
            st.success('Observation saved to your private field journal.');st.rerun()
        records=E.observations(owner,selected['id'])
        if records and records[0].get('ai_summary'):
            st.markdown('#### Latest preliminary photo review')
            st.info(records[0]['ai_summary'])
            st.warning('A photo cannot confirm the cause of crop damage. Consult an agronomist before buying or applying agrochemicals.')
        elif records:
            st.caption(f"Latest check-in: {records[0]['created_at']} · {records[0]['symptom']}")
        else:
            st.info('No check-ins saved for this field yet.')
        st.caption('Photos are saved only when you opt in. Saved copies have metadata removed; delete them any time from your health timeline.')
    with progress_tab:
        crop_health_progress_section(user,selected)
    with suppliers:
        st.caption('Crowdsourced OpenStreetMap listings near an approximate district point. Not verified recommendations or field-level distances.')
        radius=st.slider('Search radius (km)',5,30,15,5,key=f'agro_radius_{owner}_{selected["id"]}')
        if st.button('Find agro-dealers on this page',key=f'agro_find_{owner}_{selected["id"]}',type='primary'):
            with st.spinner('Checking publicly mapped agricultural suppliers…'):
                try:
                    st.session_state[f'agro_map_{owner}_{selected["id"]}']=AG.nearby_agrodealers(selected['district_code'],radius*1000)
                except Exception:
                    st.session_state.pop(f'agro_map_{owner}_{selected["id"]}',None)
                    st.warning('Supplier listings cannot be retrieved right now. Your records remain safe.')
        mapped=st.session_state.get(f'agro_map_{owner}_{selected["id"]}')
        if mapped:
            loc=mapped['reference'];shops=mapped['shops']
            if shops:
                import pydeck as pdk
                points=pd.DataFrame(shops)
                st.pydeck_chart(pdk.Deck(map_style='https://basemaps.cartocdn.com/gl/voyager-gl-style/style.json',
                     initial_view_state=pdk.ViewState(latitude=loc[0],longitude=loc[1],zoom=10),
                     layers=[pdk.Layer('ScatterplotLayer',data=points,get_position='[longitude, latitude]',
                                       get_radius=230,get_fill_color=[45,125,70],pickable=True)],
                     tooltip={'text':'{name} | {type} | Unverified OpenStreetMap listing'}),use_container_width=True)
                st.dataframe(points[['name','type','source']],hide_index=True,use_container_width=True)
            else:
                st.info('No shops found in the public map data for this area. That does not mean no suppliers exist.')
        st.info('Ask a qualified agronomist to verify a diagnosis and treatment before purchasing pesticides or fertilizer.')


def farmer_community(user):
    section_banner('Farmers | Community','Connect with farmers','Discover farmers who voluntarily share their crop and district information.','farmer','community')
    state=E.directory_settings(user['id'])
    st.markdown('### Your directory privacy')
    with st.form('community_privacy'):
        visible=st.checkbox('Show me in the voluntary farmer directory',value=bool(state['visible']))
        contact=st.checkbox('Allow other participating farmers to see my phone number',value=bool(state['contact_allowed']))
        if st.form_submit_button('Save privacy choices',type='primary'):
            E.set_directory(user['id'],visible,contact and visible);st.success('Privacy settings saved.');st.rerun()
    st.caption('Only farmers who opt in appear. You can opt out at any time; never share your phone unless you want others to contact you.')
    mine=F.list_fields(user['id'])
    codes=sorted({f['crop_code'] for f in mine})
    crop_options=[None]+codes
    crop=st.selectbox('Filter by crop',crop_options,format_func=lambda x:'Any crop' if x is None else L.CROPS[x]['en'])
    district_choices=[None]+sorted({f['district_code'] for f in mine})
    district=st.selectbox('Filter by my districts',district_choices,format_func=lambda x:'Any district' if x is None else district_label(x))
    peers=E.find_peers(user['id'],crop,district)
    if not peers:st.info('No opted-in farmers match yet. Try another filter.')
    else:
        for person in peers:
            with st.container(border=True):
                st.markdown('**'+html.escape(person['full_name'])+'**')
                st.caption(L.CROPS.get(person['crop_code'],{}).get('en',person['crop_code'])+' · '+district_label(person['district_code']))
                st.write(('Contact: '+person['phone']) if person['phone'] else 'This farmer has not shared contact information.')

def section_banner(kicker, title, description, variant='farmer', visual=None):
    """Decorative header with one consistent photographic treatment."""
    st.markdown(f'<div class="section-banner section-banner-{html.escape(variant)}' + (f' banner-{html.escape(visual)}' if visual else '') + '">'
                f'<div class="section-kicker">{html.escape(kicker)}</div>'
                f'<h1>{html.escape(title)}</h1><p>{html.escape(description)}</p>'
                '</div>', unsafe_allow_html=True)


def ensure_analytics_columns(df):
    """Schema-safe columns for accounts with no estimates, harvests, or tasks."""
    defaults = {'estimate_kg': float('nan'), 'lower_kg': float('nan'),
                'upper_kg': float('nan'), 'evidence': None,
                'actual_kg': float('nan'), 'open_tasks': 0}
    df = df.copy()
    for column, default in defaults.items():
        if column not in df.columns:
            df[column] = default
    df['open_tasks'] = df['open_tasks'].fillna(0).astype(int)
    return df


def _agronomist_records(advisor_id):
    shared = AS.assigned_fields(advisor_id)
    df = pd.DataFrame(shared)
    if df.empty:
        return df
    df['crop_name'] = df['crop_code'].map(lambda c:L.CROPS.get(c,{}).get(st.session_state.lang,c))
    df['district_name'] = df['district_code'].map(district_label)
    df['area_ha'] = df['area_sqm']/10000
    ids = df['id'].astype(int).tolist()
    marks = ','.join('?' for _ in ids)
    with connect() as db:
        es = pd.DataFrame([dict(x) for x in db.execute(f'SELECT * FROM estimates WHERE field_id IN ({marks}) ORDER BY id DESC',ids)])
        hs = pd.DataFrame([dict(x) for x in db.execute(f'SELECT * FROM harvest_reports WHERE field_id IN ({marks}) ORDER BY id DESC',ids)])
        ts = pd.DataFrame([dict(x) for x in db.execute(f'SELECT field_id,completed FROM activities WHERE field_id IN ({marks})',ids)])
    for part in [_latest_estimate_metrics(es),_latest_harvest_metrics(hs),_open_task_counts(ts)]:
        if not part.empty:
            df=df.merge(part,left_on='id',right_on='field_id',how='left',suffixes=('','_extra'))
    return ensure_analytics_columns(df)




def professional_quick_actions(role):
    """Accessible shortcuts restricted to pages already available to this role."""
    if role == 'agronomist':
        actions = [
            ('🌿','Assigned farmers','Review your authorized farmers and their fields','Shared fields'),
            ('🔎','Field monitoring','Inspect crop records and field performance','Field monitoring'),
            ('💬','Consultations','Respond to support requests','Consultations'),
            ('📝','Advisory notes','Write and review field guidance','Advisory notes'),
            ('🤖','AI Assistant','Ask for agricultural research and field guidance','AI Assistant'),
        ]
    elif role == 'planner':
        actions = [
            ('🗺️','District analytics','Compare registered crop patterns','District analytics'),
            ('📈','Harvest performance','Review recorded production outcomes','Harvest performance'),
            ('🛡️','Risk assessment','Review aggregate risks where available','Farm Risk Assessment'),
            ('🌱','Crop monitoring','Explore aggregate crop-health reports','Crop monitoring'),
            ('📦','Resource planning','Support district resource decisions','Resource planning'),
            ('👥','Farmer assignments','Manage permitted agronomist assignments','Farmer assignments'),
        ]
    else:
        return
    st.markdown('<div class="ih-role-section">Quick actions</div>',unsafe_allow_html=True)
    valid={item.page for item in NAV.nav_items(role)}
    for start in range(0,len(actions),3):
        cols=st.columns(3,gap='small')
        for col,(icon,title,description,target) in zip(cols,actions[start:start+3]):
            if target not in valid:
                continue
            with col:
                with st.container(border=True):
                    st.markdown(f'<div class="ih-role-action"><span class="ih-action-icon">{icon}</span><h4>{html.escape(title)}</h4><p>{html.escape(description)}</p></div>',unsafe_allow_html=True)
                    if st.button('Open '+title,key='quick_'+role+'_'+NAV.page_slug(target),use_container_width=True):
                        st.session_state['role_section_'+role]=target
                        st.rerun()

def agronomist_portal(advisor):
    section=st.session_state.get('role_section_agronomist','Overview')
    df=_agronomist_records(advisor['id'])
    if section=='Overview':
        section_banner('Agronomist workspace',f"Welcome, {advisor['name'].split()[0]}",'An overview of your assigned farmers and advisory work.','agronomist','overview')
        a,b,c,d=st.columns(4)
        a.metric('Assigned fields',len(df))
        b.metric('Farmers',df['farmer_name'].nunique() if not df.empty else 0)
        c.metric('Monitored area (ha)',f"{df['area_ha'].sum():.2f}" if not df.empty else '0')
        d.metric('Advisory notes',len(S.advisor_notes(advisor['id'])))
        professional_quick_actions('agronomist')
        if df.empty:st.info('No farmers assigned. Ask a planner to assign a farmer with sharing enabled.');return
        c1,c2=st.columns(2)
        with c1:st.markdown('#### Fields by crop');st.bar_chart(df.groupby('crop_name')['area_ha'].sum(),color='#398452')
        with c2:st.markdown('#### Fields by district');st.bar_chart(df.groupby('district_name').size(),color='#D7AB55')
        st.caption('Use the sidebar to open field monitoring, advisory notes, or the AI Assistant.')
    elif section=='Shared fields':
        section_banner('Agronomist | Farmers','Assigned farmers','The farmers assigned to your account and their recorded plots.','agronomist')
        if df.empty:st.info('No assigned farmers yet.');return
        options=['All']+sorted(df['farmer_name'].unique().tolist())
        farmer=st.selectbox('Farmer',options)
        subset=df if farmer=='All' else df[df['farmer_name']==farmer]
        st.dataframe(subset[['farmer_name','name','crop_name','season','district_name','area_ha']],hide_index=True,use_container_width=True)
    elif section=='Field monitoring':
        section_banner('Agronomist | Monitoring','Field monitoring','Inspect individual records, predictions, actual outcomes and planned activities.','agronomist')
        if df.empty:st.info('No assigned fields yet.');return
        crop=st.selectbox('Crop',['All']+sorted(df['crop_name'].unique().tolist()))
        subset=df if crop=='All' else df[df['crop_name']==crop]
        st.dataframe(subset[['farmer_name','name','crop_name','district_name','area_ha','estimate_kg','actual_kg','open_tasks']],hide_index=True,use_container_width=True)
        picked=st.selectbox('Inspect field',subset.to_dict('records'),format_func=lambda r:f"{r['name']} — {r['farmer_name']}")
        st.write('Planting date:',picked.get('planting_date') or 'Not provided')
        st.write('Seed:',picked.get('seed_type') or 'Not provided')
        st.write('Planned practices:',picked.get('planned_practices') or 'Not provided')
        st.caption('Estimates are historical model predictions, not guaranteed harvests.')
        st.markdown('#### Farmer crop-health observations')
        records=E.observations_for_advisor(advisor['id'],int(picked['id']))
        if records:
            st.dataframe([{'Date':x['created_at'],'Stage':x['stage'],'Observed':x['symptom'],
                           'Notes':x['notes'],'AI assessment':x['ai_summary'] or '—'} for x in records],
                           hide_index=True,use_container_width=True)
        else:st.caption('No monitoring records for this field.')
        saved=[r for r in records if PJ.photo('agronomist',advisor['id'],r['id'])]
        if saved:
            with st.expander('Saved field photographs shared by the farmer'):
                selected_pic=st.selectbox('Photograph',saved,format_func=lambda r:f"{r['created_at'][:10]} · {r['symptom']}",key=f"advisor_photo_{advisor['id']}_{picked['id']}")
                st.image(PJ.photo('agronomist',advisor['id'],selected_pic['id']),width=420)

    elif section=='Consultations':
        advisor_consultations(advisor)
    elif section=='Advisory notes':
        section_banner('Agronomist | Advisory','Farmer advisory','Send recommendations and review your previous notes.','agronomist')
        if df.empty:st.info('No assigned fields yet.');return
        field=st.selectbox('Field',df.to_dict('records'),format_func=lambda r:f"{r['name']} — {r['farmer_name']}")
        with st.form('write_advisor_note'):
            note=st.text_area('Advice to farmer',max_chars=2000)
            if st.form_submit_button('Send note',type='primary'):
                try:S.add_note(advisor['id'],int(field['id']),note);st.success('Note saved.');st.rerun()
                except (ValueError,PermissionError) as e:st.error(str(e))
        for n in S.advisor_notes(advisor['id'])[:30]:
            with st.container(border=True):st.caption(f"{n['field_name']} • {n['created_at']}");st.write(n['note'])
    else:
        role_chat('agronomist',advisor)


def _planner_filtered(df,prefix):
    a,b,c=st.columns(3)
    with a:dist=st.selectbox('District',['All']+sorted(df['district_name'].unique().tolist()),key=prefix+'_district')
    with b:crop=st.selectbox('Crop',['All']+sorted(df['crop_name'].unique().tolist()),key=prefix+'_crop')
    with c:season=st.selectbox('Season',['All']+sorted(df['season'].unique().tolist()),key=prefix+'_season')
    out=df.copy()
    if dist!='All':out=out[out['district_name']==dist]
    if crop!='All':out=out[out['crop_name']==crop]
    if season!='All':out=out[out['season']==season]
    return out


def planner_portal(planner):
    section=st.session_state.get('role_section_planner','Overview')
    data,df=_field_registry_df()
    if section=='Farm Risk Assessment':
        planner_risk_page(_field_registry_df)
        return
    if section=='Overview':
        section_banner('Planning intelligence',f"Welcome, {planner['name'].split()[0]}",'An overview of registered agriculture records and planning indicators.','planner')
        a,b,c,d=st.columns(4)
        a.metric('Registered farmers',len(data['farmers']))
        b.metric('Registered fields',len(df))
        c.metric('Registered area (ha)',f"{df['area_ha'].sum():.2f}" if not df.empty else '0')
        d.metric('Fields with estimates',int(df['estimate_kg'].notna().sum()) if not df.empty else 0)
        professional_quick_actions('planner')
        if df.empty:st.info('No registered fields yet.');return
        c1,c2=st.columns(2)
        with c1:st.markdown('#### Crop distribution');st.bar_chart(df.groupby('crop_name')['area_ha'].sum(),color='#398452')
        with c2:st.markdown('#### District coverage');st.bar_chart(df.groupby('district_name').size(),color='#D7AB55')
        st.info('These are registered-app records, not official district-level production totals. Detailed analyses are available in the sidebar.')
    elif section=='District analytics':
        section_banner('Planning | Districts','District analytics','Explore interactive crop patterns and a district-by-crop heatmap.','planner')
        if df.empty:st.info('No registered field records.');return
        filtered=_planner_filtered(df,'districts')
        if filtered.empty:st.info('No fields match those filters.');return
        st.markdown('### Rwanda district reference map')
        st.caption('Circles mark approximate district weather reference points, not field coordinates or exact district boundaries. Marker size reflects app-registered cultivated area.')
        try:
            points=json.loads((DATA_DIR/'district_weather_points.json').read_text(encoding='utf-8'))['districts']
            district_area=filtered.groupby('district_code',as_index=False)['area_ha'].sum()
            map_rows=[]
            for r in district_area.to_dict('records'):
                point=points.get(str(r['district_code']))
                if point:map_rows.append({'District':point['name'],'lat':point['latitude'],'lon':point['longitude'],'Area (ha)':float(r['area_ha'])})
            if map_rows:
                import plotly.express as px
                map_df=pd.DataFrame(map_rows)
                fig=px.scatter_map(map_df,lat='lat',lon='lon',size='Area (ha)',color='Area (ha)',hover_name='District',
                    color_continuous_scale=['#E2ECDD','#A5BA85','#398452','#164B35'],size_max=31,zoom=7.1,center={'lat':-1.95,'lon':29.87},height=440)
                fig.update_layout(map_style='carto-positron',margin=dict(l=0,r=0,t=0,b=0),paper_bgcolor='#F5F6EC',font_color='#164B35')
                st.plotly_chart(fig,use_container_width=True)
        except (ImportError,ValueError,KeyError) as e:
            st.caption('Map unavailable. District charts below remain accessible.')
        st.markdown('### District × crop area heatmap (hectares)')
        pivot=filtered.pivot_table(index='district_name',columns='crop_name',values='area_ha',aggfunc='sum',fill_value=0)
        try:
            import altair as alt
            cells=pivot.stack().reset_index(name='Area (ha)')
            heat=alt.Chart(cells).mark_rect(cornerRadius=3).encode(x=alt.X('crop_name:N',title='Crop'),y=alt.Y('district_name:N',title='District'),color=alt.Color('Area (ha):Q',scale=alt.Scale(scheme='greens')),tooltip=['district_name:N','crop_name:N',alt.Tooltip('Area (ha):Q',format='.2f')]).properties(height=max(240,32*len(pivot)))
            st.altair_chart(heat,use_container_width=True)
        except ImportError:
            st.dataframe(pivot.style.background_gradient(cmap='Greens',axis=None),use_container_width=True)
        c1,c2=st.columns(2)
        with c1:
            st.markdown('### Registered area by district')
            st.bar_chart(filtered.groupby('district_name')['area_ha'].sum(),color='#398452')
        with c2:
            st.markdown('### Latest estimate by crop (kg)')
            st.bar_chart(filtered.groupby('crop_name')['estimate_kg'].sum(),color='#D7AB55')
        st.markdown('### Explore crop composition and regional patterns')
        try:
            import plotly.express as px
            a,b=st.columns(2)
            crop_summary=filtered.groupby('crop_name',as_index=False)['area_ha'].sum()
            treemap=px.treemap(crop_summary,path=['crop_name'],values='area_ha',color='area_ha',color_continuous_scale=['#E2ECDD','#A5BA85','#398452','#164B35'])
            treemap.update_layout(margin=dict(l=8,r=8,t=20,b=8),height=340,paper_bgcolor='#F5F6EC')
            a.plotly_chart(treemap,use_container_width=True)
            donut=px.pie(crop_summary,names='crop_name',values='area_ha',hole=.55,color_discrete_sequence=['#164B35','#398452','#A5BA85','#D7AB55','#B96F4D','#5D6F60'])
            donut.update_layout(height=340,paper_bgcolor='#F5F6EC',legend_title='Crop')
            b.plotly_chart(donut,use_container_width=True)
            grouped=filtered.groupby(['district_name','crop_name'],as_index=False)['area_ha'].sum()
            fig=px.bar(grouped,x='district_name',y='area_ha',color='crop_name',barmode='stack',color_discrete_sequence=['#164B35','#398452','#A5BA85','#D7AB55','#B96F4D'])
            fig.update_layout(height=360,xaxis_title='District',yaxis_title='Registered area (ha)',paper_bgcolor='#F5F6EC',plot_bgcolor='#F5F6EC')
            st.plotly_chart(fig,use_container_width=True)
        except Exception:st.caption('Additional charts unavailable; summary table remains accessible.')
        summary=filtered.groupby('district_name',as_index=False).agg(fields=('id','count'),area_ha=('area_ha','sum'),estimated_kg=('estimate_kg','sum'))
        st.dataframe(summary.rename(columns={'district_name':'District','fields':'Fields','area_ha':'Area (ha)','estimated_kg':'Latest estimated production (kg)'}),hide_index=True,use_container_width=True)
        st.caption('Each registered field contributes at most its latest saved estimate. This is not a representative survey estimate.')
        st.markdown('### Historical agricultural benchmarks (separate source)')
        from core.historical import load_benchmarks
        try:
            historical = load_benchmarks(DATA_DIR / 'historical' / 'nisr_aggregates.csv')
        except ValueError as exc:
            st.warning('The historical statistics CSV could not be loaded: ' + str(exc))
            historical = []
        if historical:
            hist_df = pd.DataFrame(historical)
            hist_df['district_name'] = hist_df['district_code'].map(lambda x: get_districts()['districts'].get(str(x), {}).get('name', str(x)))
            hist_df['crop_name'] = hist_df['crop_code'].map(lambda x: L.CROPS.get(str(x), {}).get('en',str(x)))
            years = sorted(hist_df['year'].unique().tolist())
            chosen_year = st.selectbox('Historical year', years, index=len(years)-1)
            sample = hist_df[hist_df['year'] == chosen_year]
            st.dataframe(sample[['season','district_name','crop_name','area_ha','production_kg','yield_kg_ha','source']], hide_index=True, use_container_width=True)
            st.caption('Historical source statistics are not live farmer records. Only valid aggregate source data appears here; never interpret these as app estimates.')
        else:
            st.info('Historical NISR aggregate data has not been imported. Add validated district–crop–season aggregates to data/historical/nisr_aggregates.csv using the included template. No historical numbers are fabricated.')

    elif section=='Historical survey':
        section_banner('Planning | Historical survey','SAS 2025 sample explorer','Explore historical survey coverage and descriptive field records separately from live farmer data.','planner')
        st.warning('These are UNWEIGHTED SAMPLE DESCRIPTIVES from the IhingaAI working dataset. They are NOT NISR official district production totals, population crop distributions, or fertilizer allocation evidence.')
        from core.sample_descriptives import load_sample_descriptives
        sample_path=DATA_DIR/'historical'/'sas2025_sample_descriptives.csv'
        try:
            sample_rows=load_sample_descriptives(sample_path)
        except ValueError as exc:
            st.error('Survey sample summary could not be loaded: '+str(exc));return
        if not sample_rows:
            st.info('No validated sample descriptive records have been imported.');return
        sample_df=pd.DataFrame(sample_rows)
        dl=get_districts()['districts']
        sample_df['District']=sample_df['district_code'].map(lambda c:dl.get(str(c),{}).get('name',str(c)))
        additional_crop_labels={'102':'Paddy rice','104':'Wheat','112':'Taro','124':'Sunflower','201':'Pyrethrum'}
        sample_df['Crop']=sample_df['crop_code'].map(lambda c:L.CROPS.get(str(c),{}).get('en',additional_crop_labels.get(str(c),'Crop code '+str(c))))
        with st.expander('About these data and their limits',expanded=True):
            st.write('Source: SAS 2025 Cross_Season_Core_Working.pkl, a locally prepared survey working file. Original: 69,173 crop/plot-related records across Seasons A, B and C.')
            st.write('To protect against tiny survey groups, each published district–crop–season group contains at least 20 records, at least 15 records with reported harvest, and at least five distinct sample segments. Small groups are withheld.')
            st.write('Counts represent sampled records and are not population totals. Crop-area medians are recorded source areas; definitions and harvest denominators require further cross-season validation. No survey respondent identifiers are included.')
        f1,f2,f3=st.columns(3)
        with f1:season_filter=st.selectbox('Survey season',['All','A','B','C'],key='sample_season')
        with f2:district_filter=st.selectbox('Survey district',['All']+sorted(sample_df['District'].unique().tolist()),key='sample_district')
        with f3:crop_filter=st.selectbox('Survey crop',['All']+sorted(sample_df['Crop'].unique().tolist()),key='sample_crop')
        filtered=sample_df.copy()
        if season_filter!='All':filtered=filtered[filtered['season']==season_filter]
        if district_filter!='All':filtered=filtered[filtered['District']==district_filter]
        if crop_filter!='All':filtered=filtered[filtered['Crop']==crop_filter]
        a,b,c=st.columns(3)
        a.metric('Published sample groups',len(filtered))
        b.metric('Records in shown groups',f"{int(filtered['sample_records'].sum()):,}")
        c.metric('Districts represented',filtered['district_code'].nunique())
        st.caption('Filtered record counts are coverage information only; do not interpret as production volume or prevalence across districts.')
        if filtered.empty:
            st.info('No published survey groups match these filters. Small group suppression may be responsible.');return
        col1,col2=st.columns(2)
        with col1:
            st.markdown('#### Sample records by season')
            season_count=filtered.groupby('season',as_index=False)['sample_records'].sum()
            st.bar_chart(season_count.set_index('season'),color='#398452')
        with col2:
            st.markdown('#### Sample records by crop')
            crop_count=filtered.groupby('Crop',as_index=False)['sample_records'].sum().sort_values('sample_records',ascending=False).head(12)
            st.bar_chart(crop_count.set_index('Crop'),horizontal=True,color='#D7AB55')
        st.markdown('#### District × crop survey coverage (number of sampled records)')
        mat=filtered.pivot_table(index='District',columns='Crop',values='sample_records',aggfunc='sum',fill_value=0)
        try:
            import plotly.express as px
            fig=px.imshow(mat,labels={'x':'Crop','y':'District','color':'Sample records'},color_continuous_scale=['#F5F6EC','#A5BA85','#398452','#164B35'],aspect='auto',height=max(360,min(760,26*len(mat))))
            fig.update_layout(paper_bgcolor='#F5F6EC',plot_bgcolor='#F5F6EC',font_color='#164B35',margin=dict(t=20,b=20,l=20,r=20))
            st.plotly_chart(fig,use_container_width=True)
        except Exception:
            st.dataframe(mat,use_container_width=True)
        st.markdown('#### Filtered historical survey descriptive records')
        show=filtered[['year','season','District','Crop','sample_records','records_with_harvest','distinct_sample_segments','median_recorded_crop_area_ha']].copy()
        show.columns=['Year','Season','District','Crop','Sample records','Harvest response records','Sample segments','Median recorded crop area (ha)']
        st.dataframe(show,hide_index=True,use_container_width=True)
        st.caption('Use these tables for descriptive survey exploration only, not as official yield benchmarks or evidence for allocating farm inputs. For population estimates, obtain NISR-approved published aggregates and survey-design methodology.')

    elif section=='Farmer assignments':
        section_banner('Planning | Assignments','Farmer assignments','Manage agronomist workload and consent-based farmer assignments.','planner')
        st.caption('Only farmers with sharing enabled may be assigned. Revoked permission blocks access.')
        candidates=AS.available_farmers();advisors=AS.list_advisors()
        if candidates and advisors:
            with st.form('make_assignment'):
                farmer=st.selectbox('Farmer',candidates,format_func=lambda r:f"{r['full_name']} · {r['fields']} fields")
                advisor_choice=st.selectbox('Agronomist',advisors,format_func=lambda r:r['name'])
                if st.form_submit_button('Assign farmer',type='primary'):
                    try:AS.assign(planner['id'],farmer['id'],advisor_choice['id']);st.success('Assignment saved.');st.rerun()
                    except (ValueError,PermissionError) as e:st.error(str(e))
        else:st.info('You need at least one registered agronomist and one farmer who enabled sharing.')
        active=AS.active_assignments()
        st.metric('Current assignments',len(active))
        for item in active:
            col1,col2=st.columns([5,1]);col1.write(f"{item['farmer_name']} → {item['advisor_name']}")
            if col2.button('Unassign',key=f"remove_{item['id']}"):AS.unassign(planner['id'],item['id']);st.rerun()
    elif section=='Crop monitoring':
        section_banner('Planning | Crop care','Crop monitoring insights','Aggregated registered crop-health observations.','planner')
        with connect() as db:
            rows=[dict(r) for r in db.execute('SELECT f.district_code,f.crop_code,o.stage,o.symptom,COUNT(*) AS observations FROM crop_observations o JOIN fields f ON f.id=o.field_id AND f.farmer_id=o.farmer_id GROUP BY f.district_code,f.crop_code,o.stage,o.symptom')]
        if not rows:st.info('No farmer crop monitoring observations yet.')
        else:
            records=pd.DataFrame(rows)
            records['District']=records['district_code'].map(district_label)
            records['Crop']=records['crop_code'].map(lambda c:L.CROPS[c]['en'])
            import plotly.express as px
            fig=px.sunburst(records,path=['District','Crop','symptom'],values='observations',color='observations',color_continuous_scale=['#E5EEDF','#83B278','#174B35'])
            fig.update_layout(paper_bgcolor='#F5F6EC',height=530)
            st.plotly_chart(fig,use_container_width=True)
            st.dataframe(records[['District','Crop','stage','symptom','observations']],hide_index=True,use_container_width=True)
        st.caption('Repeated observations count individually. This is not a disease-prevalence estimate.')
    elif section=='Resource planning':
        section_banner('Planning | Resources','Resource planning','Explore available resources against registered cultivated area.','planner')
        if df.empty:st.info('No registered fields yet.');return
        filtered=_planner_filtered(df,'resources')
        total_kg=st.slider('Available fertilizer (kg)',100,20000,1200,100)
        area=float(filtered['area_ha'].sum())
        a,b,c=st.columns(3);a.metric('Selected fields',len(filtered));b.metric('Selected area (ha)',f'{area:.2f}');c.metric('Illustrative kg/ha',f'{total_kg/area:.1f}' if area else '—')
        if not filtered.empty:
            regional=filtered.groupby('district_name',as_index=False)['area_ha'].sum()
            regional['Illustrative allocation (kg)']=regional['area_ha']/area*total_kg if area else 0
            st.dataframe(regional.rename(columns={'district_name':'District','area_ha':'Registered area (ha)'}),hide_index=True,use_container_width=True)
            st.bar_chart(regional.set_index('district_name')['Illustrative allocation (kg)'],color='#398452')
        st.warning('This is allocation arithmetic, not a fertilizer prescription. Crop needs and soil conditions require agronomist review.')
    elif section=='Harvest performance':
        section_banner('Planning | Performance','Harvest performance','Compare reported outcomes with the latest saved model estimates.','planner')
        if df.empty:st.info('No registered fields yet.');return
        filtered=_planner_filtered(df,'performance')
        matched=filtered.dropna(subset=['estimate_kg','actual_kg']).copy()
        if matched.empty:st.info('No fields have both a latest estimate and reported actual harvest yet.');return
        matched['absolute_error_kg']=(matched['estimate_kg']-matched['actual_kg']).abs()
        c1,c2=st.columns(2);c1.metric('Matched fields',len(matched));c2.metric('Mean absolute difference (kg)',f"{matched['absolute_error_kg'].mean():,.1f}")
        st.scatter_chart(matched,x='estimate_kg',y='actual_kg',color='#398452')
        st.dataframe(matched[['crop_name','district_name','estimate_kg','actual_kg','absolute_error_kg']].rename(columns={'crop_name':'Crop','district_name':'District'}),hide_index=True,use_container_width=True)
        st.caption('The paired estimates and harvest reports may be from different observation dates; interpret carefully.')
    else:role_chat('planner',planner)


def dashboard_insights(fields,tasks,estimates):
    st.markdown('###  '+bilingual('Your farm at a glance','Incamake y’imirima yawe'))
    c1,c2=st.columns(2)
    with c1:
        st.markdown('**'+bilingual('Field area by crop (hectares)','Ubuso bw’imirima hakurikijwe igihingwa')+'**')
        if fields:
            per_crop={}
            for f in fields:
                label=L.CROPS.get(f['crop_code'],{}).get(st.session_state.lang,f['crop_code'])
                per_crop[label]=per_crop.get(label,0)+f['area_sqm']/10000
            st.bar_chart(pd.DataFrame({"Crop":list(per_crop),"Hectares":list(per_crop.values())}).set_index("Crop"),horizontal=True)
        else: st.info('Register a field to see crop distribution.')
    with c2:
        st.markdown('**'+bilingual('Activity progress','Aho ibikorwa bigeze')+'**')
        if tasks:
            done=sum(bool(t['completed']) for t in tasks)
            st.progress(done/len(tasks),text=f'{done} / {len(tasks)} '+bilingual('activities completed','ibikorwa byarangiye'))
            overdue=[t for t in tasks if not t['completed'] and t['due_date'] and t['due_date']<date.today().isoformat()]
            st.metric(bilingual('Overdue activities','Ibikorwa byakererewe'),len(overdue))
            upcoming=[t for t in tasks if not t['completed'] and t['due_date'] and date.today().isoformat()<=t['due_date']<=(date.today()+timedelta(days=7)).isoformat()]
            st.metric(bilingual('Due in next 7 days','Mu minsi 7'),len(upcoming))
        else: st.info('Add activities to track your progress.')
    st.markdown('###  '+bilingual('Upcoming work','Ibikorwa biri imbere'))
    pending=sorted((t for t in tasks if not t['completed']),key=lambda t:(t['due_date'] is None,t['due_date'] or '9999',t['id']))
    if pending:
        for t in pending[:5]:
            st.markdown('• **'+html.escape(t['title'])+'** — '+html.escape(t['field_name'])+' · '+(t['due_date'] or 'No deadline'))
    else: st.caption(bilingual('No open activities.','Nta bikorwa bisigaye.'))
    st.markdown('###  '+bilingual('Latest saved estimates','Amagereranya aheruka'))
    if estimates:
        for e in estimates[:4]:
            result=json.loads(e['output_json']); f=next((f for f in fields if f['id']==e['field_id']),None)
            if result.get('status')=='ok':
                st.markdown('• **'+html.escape(f['name'] if f else 'Field')+'** — '+fmt_kg(result['estimate_kg'])+' kg · '+e['created_at'][:10]+' · '+html.escape(str(result.get('evidence',''))))
        st.caption('Saved estimates are historical model outputs, not current forecasts or guaranteed harvests. Do not sum estimates from different dates as if independent.')
    else: st.caption('Your saved predictions will appear here.')


def home(user,router):
    owner=user['id']; fields=F.list_fields(owner); tasks=F.list_activities(owner); estimates=F.list_estimates(owner)
    name=user['full_name'].split()[0]
    section_banner('Your farming workspace', bilingual(f'Welcome, {name}.', f'Murakaza neza, {name}.'), bilingual('Plan your fields, follow your activities, and understand your harvest estimates.','Tegura imirima yawe, kurikirana ibikorwa n’amagereranya y’umusaruro.'), 'farmer','home')
    a,b,c,d=st.columns(4)
    a.metric(bilingual('My fields','Imirima'),len(fields))
    b.metric(bilingual('Total hectares','Hegitari'),f"{sum(f['area_sqm'] for f in fields)/10000:.2f}")
    c.metric(bilingual('Saved estimates','Amagereranya'),len(estimates))
    d.metric(bilingual('Open activities','Ibikorwa bisigaye'),sum(not t['completed'] for t in tasks))
    if fields:
        st.markdown('### '+bilingual('Your growing fields','Imirima yawe'))
        featured=fields[:3]
        visual_cols=st.columns(len(featured),gap='medium')
        for col, f in zip(visual_cols, featured):
            with col:
                with st.container(border=True):
                    st.image(str(ROOT/'assets'/'headers'/'my_fields.jpg'), use_container_width=True)
                    st.markdown('**'+html.escape(f['name'])+'**')
                    st.caption(html.escape(L.CROPS[f['crop_code']]['en'])+' · Season '+str(f['season'])+' · '+f"{f['area_sqm']/10000:.2f} ha")
                    if st.button('Open field',key='ih_home_field_'+str(f['id']),use_container_width=True):
                        st.session_state['field_detail_id']=f['id']
                        st.session_state.page='My fields'
                        st.rerun()
    st.markdown('### Today’s priorities')
    alerts=FS.local_alerts(owner,fields,tasks,E.observations(owner))
    cases=CON.consultations_for_farmer(owner)
    reply_ready=[case for case in cases if case['status']=='Responded']
    if reply_ready:
        st.success(f"{len(reply_ready)} consultation(s) have agronomist responses ready for you.")
        if st.button('Read agronomist replies',key='dashboard_read_advice'):
            st.session_state.page='Agronomist support';st.rerun()
    ordered=alerts[:3]
    if ordered:
        for alert in ordered:
            with st.container(border=True):
                x,y=st.columns([5,1],vertical_alignment='center')
                x.markdown('**'+html.escape(alert['title'])+'**')
                x.caption(html.escape(alert['detail']))
                y.caption(alert['level'])
        if len(alerts)>3:st.caption(f'+{len(alerts)-3} more reminders available in Smart alerts.')
    if not alerts and not reply_ready:
        st.success('Nothing urgent in your recorded tasks or consultations. Keep checking fields regularly.')
    st.markdown('### '+bilingual('Quick actions','Ibyo wakora'))
    quick_actions = [
        ('🌽', 'Estimate harvest', 'Predict the harvest range', 'Estimate'),
        ('🌿', 'My fields', 'View fields and records', 'My fields'),
        ('🌤️', 'District weather', 'Check the forecast', 'Weather'),
        ('📈', 'Market Prices', 'Compare recorded prices', 'Market Prices'),
        ('🛡️', 'Risk assessment', 'Review field risks', 'Farm Risk Assessment'),
        ('🤖', 'Agro Support (AI)', 'Get agricultural guidance', 'AI assistant'),
    ]
    quick_images = {
        'Estimate': 'quick_action_estimate.jpg',
        'My fields': 'quick_action_fields.jpg',
        'Weather': 'quick_action_weather.jpg',
        'Market Prices': 'quick_action_market.jpg',
        'Farm Risk Assessment': 'quick_action_risk.jpg',
        'AI assistant': 'quick_action_agro_support.jpg',
    }
    for offset in (0, 3):
        cells = st.columns(3, gap='medium')
        for col, (symbol, title, description, destination) in zip(cells, quick_actions[offset:offset+3]):
            with col:
                with st.container(border=True):
                    asset = quick_images.get(destination)
                    if asset:
                        local_image = image_url_local('cards/' + asset)
                        st.markdown(f'<img src="{local_image}" alt="{html.escape(title)}" style="width:100%;height:112px;object-fit:cover;border-radius:12px;margin-bottom:8px;" />',unsafe_allow_html=True)
                    st.markdown(f'<div class="ih-quick-icon">{symbol}</div><div class="ih-quick-title">{html.escape(title)}</div><div class="ih-quick-desc">{html.escape(description)}</div>',unsafe_allow_html=True)
                    if st.button('Open '+title,key='ih_quick_'+destination,use_container_width=True,type='primary' if destination=='Estimate' else 'secondary'):
                        st.session_state.page=destination
                        st.rerun()
    reminders=FS.local_alerts(owner,fields,tasks,E.observations(owner))
    if reminders:
        upcoming=sum(a['level'] in ('Overdue','Upcoming') for a in reminders)
        st.info(f"You have {len(reminders)} field reminders to review, including {upcoming} scheduled activities. These are based on your recorded data.")
    f1,f2=st.columns(2)
    if f1.button('Farm finances',use_container_width=True):
        st.session_state.page='Farm finances';st.rerun()
    if f2.button('Smart alerts',use_container_width=True):
        st.session_state.page='Smart alerts';st.rerun()
    dashboard_insights(fields,tasks,estimates)
    st.markdown('<div class="note">ℹ '+html.escape(bilingual('Estimates are experimental, based on historical survey patterns and are not harvest guarantees or farming-practice recommendations.','Amagereranya ntabwo ari icyemezo cy’umusaruro.'))+'</div>',unsafe_allow_html=True)


def role_chat(role, user):
    """Persistent full-page chat. Messages are isolated by role and account."""
    section_banner('IhingaAI | Intelligence','AI Assistant','Conversations are private to this account. You can delete any conversation.','farmer' if role=='farmer' else role)
    st.caption('Ask questions about crop growth and field planning. Responses may take several seconds and require an internet connection.')
    key=AI.api_key()
    if not key:
        st.warning('Gemini is not connected. Configure .streamlit/secrets.toml.')
        return
    owner=user['id']
    convs=E.list_chats(role,owner)
    a,b=st.columns([4,1])
    choices=[None]+convs
    if st.session_state.pop('reset_chat_choice',None)==f'chat_choice_{role}_{owner}':
        st.session_state[f'chat_choice_{role}_{owner}']=None
    new_chat_id=st.session_state.pop(f'open_chat_{role}_{owner}',None)
    if new_chat_id is not None:
        st.session_state[f'chat_choice_{role}_{owner}']=next((c for c in convs if c['id']==new_chat_id),None)
    current=a.selectbox('Your conversations',choices,format_func=lambda c:'New conversation' if c is None else c['title'],key=f'chat_choice_{role}_{owner}')
    if current and b.button('Delete chat',key=f'del_chat_{role}_{owner}'):
        E.delete_chat(role,owner,current['id']);st.session_state['reset_chat_choice']=f'chat_choice_{role}_{owner}';st.rerun()
    messages=E.get_messages(role,owner,current['id']) if current else []
    st.markdown('<div class="ai-conversation-note">Questions and answers have contrasting backgrounds. Recent messages in this conversation are used as context for follow-up questions.</div>',unsafe_allow_html=True)
    for m in messages:
        with st.chat_message(m['speaker']): st.markdown(m['body'])
    consent=st.checkbox('I agree to send my question and up to eight recent messages from this chat to Google Gemini.',key=f'chat_ok_{role}')
    with st.form(f'ai_fullpage_form_{role}',clear_on_submit=True):
        question=st.text_area('Your message',placeholder='Describe your question or the issue you are facing...',height=100,max_chars=1600)
        submitted=st.form_submit_button('Send message',type='primary',disabled=not consent)
    if submitted and question.strip():
        history=[{'role':m['speaker'],'text':m['body']} for m in messages[-8:]]
        context={'role':role,'scope':'general farming guidance','note':'Never invent private field records or claim to see statistics not provided.'}
        if role=='farmer':
            fields=F.list_fields(owner)
            if fields:
                context['registered_crop_names']=sorted({L.CROPS[f['crop_code']]['en'] for f in fields})
        try:
            with st.spinner('Preparing your answer…'):
                result=AI.call_gemini(key,question,context,history,st.session_state.lang)
            chat_id=current['id'] if current else E.create_chat(role,owner,question[:65])
            E.add_message(role,owner,chat_id,'user',question)
            E.add_message(role,owner,chat_id,'assistant',result['answer']+'\n\n'+('\n'.join('Question: '+q for q in result.get('questions',[]))))
            st.session_state[f'open_chat_{role}_{owner}']=chat_id
            st.rerun()
        except Exception as exc:st.error('AI request failed: '+str(exc)[:250])


def quick_assistant(role,user):
    st.markdown('<div class="ai-shortcut-anchor"></div>',unsafe_allow_html=True)
    if st.button('Ask IhingaAI',key=f'floating_assistant_{role}',type='primary',help='Open full-page AI Assistant'):
        if role=='farmer': st.session_state.page='AI assistant'
        else: st.session_state[f'role_section_{role}']='AI Assistant'; st.session_state.jump_role_nav=role
        st.rerun()


def navigation_sidebar(role, user=None):
    """Unified icon sidebar: the same expandable rail for all three portals.

    We intentionally keep navigation as native Streamlit buttons (rather than
    a disconnected HTML iframe) so the current role and page remain authoritative.
    """
    guest = role == 'farmer' and user is None
    items = NAV.nav_items(role, guest=guest)
    key = 'page' if role == 'farmer' else f'role_section_{role}'
    current = NAV.selected_page(role, st.session_state.get(key), guest=guest)
    if role == 'farmer':
        target = st.session_state.pop('nav_target', None)
        if target in {item.page for item in items}:
            current = target
    else:
        if st.session_state.pop('jump_role_nav', None) == role:
            current = 'AI Assistant'
    st.session_state[key] = current
    compact = st.session_state.setdefault('nav_compact', False)
    display_name = ('Guest visitor' if guest else
                    user.get('full_name', user.get('name', 'IhingaAI user')))
    initial = (display_name.strip() or 'I')[0].upper()
    role_name = {'farmer': 'Farmer', 'agronomist': 'Agronomist', 'planner': 'Planner / Admin'}[role]

    with st.sidebar:
        # Marker powers the compact-rail CSS without manipulating Streamlit internals.
        st.markdown('<span class="ih-nav-mode-{}"></span>'.format('compact' if compact else 'wide'),unsafe_allow_html=True)
        if compact:
            st.markdown(brand_logo_html(42),unsafe_allow_html=True)
            if st.button('Expand navigation',icon=':material/menu_open:',help='Expand navigation',
                         key='ih_toggle_nav',use_container_width=True):
                st.session_state.nav_compact=False;st.rerun()
        else:
            brand, toggle = st.columns([5,2],gap='small',vertical_alignment='center')
            with brand:
                st.markdown(brand_logo_html(100),unsafe_allow_html=True)
            with toggle:
                if st.button('Minimize navigation',icon=':material/menu:',help='Minimize navigation',
                             key='ih_toggle_nav',use_container_width=True):
                    st.session_state.nav_compact=True;st.rerun()
        if not compact:
            st.markdown('<div class="ih-workspace"><span class="ih-workspace-indicator"></span>'+html.escape(role_name)+' workspace</div>',unsafe_allow_html=True)

        previous_group = None
        for item in items:
            if item.group != previous_group:
                if compact:
                    st.markdown('<div class="ih-nav-separator" title="'+html.escape(item.group)+'"></div>',unsafe_allow_html=True)
                else:
                    st.markdown('<div class="ih-nav-group">'+html.escape(item.group)+'</div>',unsafe_allow_html=True)
                previous_group = item.group
            label = (item.rw_label if role == 'farmer' and st.session_state.get('lang') == 'rw' and item.rw_label else item.label)
            clicked = st.button(
                label,
                icon=f':material/{item.icon}:',
                type='primary' if current == item.page else 'secondary',
                help=label if compact else None,
                use_container_width=True,
                key=f'ihnav_{role}_{NAV.page_slug(item.page)}',
            )
            if clicked:
                st.session_state[key] = item.page
                st.rerun()

        with st.container(key='ih_account_footer'):
            if not compact:
                st.markdown('<div class="ih-footer-title">YOUR ACCOUNT</div>',unsafe_allow_html=True)
            safe_name = html.escape(display_name)
            safe_role = html.escape('Guest mode' if guest else role_name)
            st.markdown(
                f'<div class="ih-account"><div class="ih-avatar">{html.escape(initial)}</div>'
                + ('' if compact else f'<div class="ih-account-details"><strong title="{safe_name}">{safe_name}</strong><span>{safe_role}</span></div>')
                + '</div>', unsafe_allow_html=True)
            if role == 'farmer' and not compact:
                languages=list(L.LANGS)
                st.selectbox('Language / Ururimi',languages,
                             index=languages.index(st.session_state.get('lang','en')),
                             format_func=lambda x:L.LANGS[x],key='ih_language_input',
                             on_change=lambda: st.session_state.__setitem__('lang',st.session_state['ih_language_input']))
            if st.button('Log out' if not guest else 'Exit guest mode',
                         icon=':material/logout:', help='Leave this account' if compact else None,
                         key=f'ih_sign_out_{role}',use_container_width=True):
                if role == 'farmer':
                    st.session_state.farmer_id = None
                    st.session_state.guest = False
                    st.session_state.page = 'Home'
                    st.session_state.portal_mode = 'farmer'
                else:
                    st.session_state.pop('advisor_id' if role == 'agronomist' else 'planner_id', None)
                    st.session_state.pop(f'role_section_{role}',None)
                st.session_state.entry_screen = 'landing'
                st.rerun()
    return current


def navigation_context(role, page):
    """A restrained, consistent breadcrumb above every signed-in workspace."""
    role_label = {'farmer': 'Farmer', 'agronomist': 'Agronomist',
                  'planner': 'Planner / Admin'}[role]
    page_label = next((item.label for item in NAV.nav_items(role)
                       if item.page == page), page)
    st.markdown(
        '<div class="ih-context-strip"><div class="ih-context-path">'
        '<span>IhingaAI</span><span aria-hidden="true">/</span>'
        f'<span>{html.escape(role_label)}</span><span aria-hidden="true">/</span>'
        f'<span class="ih-current">{html.escape(page_label)}</span>'
        '</div><span class="ih-live">Workspace</span></div>',
        unsafe_allow_html=True,
    )


def role_sidebar(role, user):
    """Legacy call site: all roles now share the same renderer."""
    return navigation_sidebar(role, user)


def main():
    st.session_state.setdefault('lang','en')
    st.session_state.setdefault('farmer_id',None)
    st.session_state.setdefault('guest',False)
    st.session_state.setdefault('page','Home')
    st.session_state.setdefault('portal_mode','farmer')
    st.session_state.setdefault('entry_screen','landing')
    identity=(st.session_state.get('portal_mode'),st.session_state.get('farmer_id'),st.session_state.get('advisor_id'),st.session_state.get('planner_id'))
    if st.session_state.get('_last_identity') != identity:
        for k in list(st.session_state.keys()):
            if k in ('monitor_result','pending_estimate','ai_actions','ai_messages','ai_last_field','guided_result','guided_answers','selected_field','new_share_code','field_detail_id','field_delete_confirm_id','edit_field') or k.startswith(('crop_photo_','agro_map_','monitor_','new_crop_monitor_','crop_upload_nonce_','season_forecast_','finance_field_','finance_delete_','finance_type_','season_field_','alert_field_','monitor_field_','con_field_','con_advisor_','con_obs_','photo_review_','photo_before_','photo_after_','profit_window_','break_even_')):
                st.session_state.pop(k,None)
        st.session_state['_last_identity']=identity
    user = user_now()
    advisor = S.advisor_by_id(st.session_state.get('advisor_id')) if st.session_state.get('advisor_id') else None
    planner = S.planner_by_id(st.session_state.get('planner_id')) if st.session_state.get('planner_id') else None

    if advisor and not user and st.session_state.portal_mode == 'agronomist':
        role_sidebar('agronomist',advisor)
        navigation_context('agronomist',st.session_state['role_section_agronomist'])
        if st.session_state['role_section_agronomist'] == 'About IhingaAI':
            about_ihingaai()
        else:
            agronomist_portal(advisor)
        quick_assistant('agronomist',advisor)
        return
    if planner and not user and st.session_state.portal_mode == 'planner':
        role_sidebar('planner',planner)
        navigation_context('planner',st.session_state['role_section_planner'])
        if st.session_state['role_section_planner'] == 'About IhingaAI':
            about_ihingaai()
        else:
            planner_portal(planner)
        quick_assistant('planner',planner)
        return
    if not user and not st.session_state.guest:
        # Entry screens use locally bundled photographs. Keep entry-only styling
        # inside this branch so signed-in dashboards are never affected.
        landing_image = (image_url_local('backgrounds/landing_background.jpg')
                         or image_url_local('headers/farmer_home.jpg'))
        image_layer = f'url("{landing_image}")' if landing_image else 'linear-gradient(125deg,#185f43,#163c30)'
        entry_styles = """
        <style>
        [data-testid="stSidebar"], [data-testid="stHeader"] {display:none!important;}
        html, body {min-height:100%;}
        .stApp, [data-testid="stApp"], [data-testid="stAppViewContainer"] {
            background-image:linear-gradient(90deg,rgba(3,27,19,.80) 0%,rgba(3,27,19,.53) 52%,rgba(3,27,19,.24) 100%),IMAGE_LAYER!important;
            background-position:center center!important;
            background-repeat:no-repeat!important;
            background-size:cover!important;
            background-attachment:fixed!important;
            min-height:100vh!important;
        }
        [data-testid="stAppViewContainer"] > .main,
        [data-testid="stMain"],
        [data-testid="stMainBlockContainer"] {background:transparent!important;}
        [data-testid="stAppViewContainer"] .block-container {max-width:1100px!important;}
        .landing-copy {max-width:790px!important;margin-top:clamp(28px,7vh,85px)!important;}
        .landing-copy h1 {color:#fff!important;font-size:clamp(2.7rem,6vw,5.4rem)!important;line-height:1.08!important;}
        .landing-copy p {color:#fff!important;font-size:clamp(1.1rem,2vw,1.45rem)!important;}
        .stButton > button[kind="primary"],
        .stFormSubmitButton > button[kind="primary"] {
            background:#087a4e!important;color:#fff!important;border:1px solid #1e9a68!important;
        }
        .stButton > button[kind="primary"]:hover,
        .stFormSubmitButton > button[kind="primary"]:hover {background:#086341!important;}
        @media(max-width:700px){
            .landing-copy {margin-top:32px!important;}
            .landing-copy h1 {font-size:clamp(2.4rem,10vw,3.5rem)!important;}
        }
        </style>
        """.replace('IMAGE_LAYER', image_layer)
        st.markdown(entry_styles, unsafe_allow_html=True)
        if st.session_state.entry_screen == 'landing':
            st.markdown("""<style>
                [data-testid="stAppViewContainer"] .block-container {
                    padding-top:clamp(50px,11vh,120px)!important;
                }
                .stButton>button[kind="primary"] {min-width:185px!important;}
            </style>""", unsafe_allow_html=True)
            landing_page()
        else:
            st.markdown("""<style>
                [data-testid="stAppViewContainer"] .block-container {
                    max-width:540px!important;
                    margin:clamp(12px,3vh,40px) auto!important;
                    padding:28px 30px 34px!important;
                    border-radius:22px!important;
                    background:rgba(255,255,255,.97)!important;
                    box-shadow:0 22px 65px rgba(3,27,19,.27)!important;
                }
                .auth-heading h2 {color:#103d30!important;}
                @media(max-width:700px){
                    [data-testid="stAppViewContainer"] .block-container {
                        padding:22px 18px!important;
                        border-radius:16px!important;
                    }
                }
            </style>""", unsafe_allow_html=True)
            authenticate()
        return

    selected = navigation_sidebar('farmer', user)
    navigation_context('farmer',selected)
    router = get_router()
    if selected == 'About IhingaAI':
        about_ihingaai()
    elif selected == 'Estimate':
        estimate(router)
    elif selected == 'Home':
        home(user,router)
    elif selected == 'AI assistant':
        assistant_page(user)
    elif selected == 'Guided recommendations':
        guided_recommendations(user)
    elif selected == 'Crop monitoring':
        crop_monitoring(user)
    elif selected == 'My farming season':
        farming_season_page(user)
    elif selected == 'Farm finances':
        farm_finances_page(user)
    elif selected == 'Market Prices':
        market_prices_page()
    elif selected == 'Farm Risk Assessment':
        risk_assessment_page(user,district_label,district_weather)
    elif selected == 'Smart alerts':
        smart_alerts_page(user)
    elif selected == 'Farmer community':
        farmer_community(user)
    elif selected == 'Profile':
        st.title(' ' + bilingual('My profile', 'Umwirondoro'))
        st.text_input(bilingual('Full name', 'Amazina'), value=user['full_name'],disabled=True)
        st.text_input(bilingual('Phone', 'Telefoni'),value=user['phone'],disabled=True)
        st.caption(bilingual('Your account is stored locally on this device. Profile editing is planned for a later phase.', 'Konti yawe ibitswe kuri iki gikoresho.'))
    elif selected == 'My fields':
        my_fields(user,router)
    elif selected == 'Activities':
        activities_page(user)
    elif selected == 'Calendar':
        calendar_page(user)
    elif selected == 'Weather':
        weather_page(user)
    elif selected == 'Agronomist support':
        sharing_page(user)
    if user:
        quick_assistant('farmer',{'id':user['id'],'name':user['full_name']})
    with st.expander('Data sources & acknowledgements'):
        st.markdown('**NISR:** 2025 Seasonal Agricultural Survey records underpin the frozen harvest models. **Open-Meteo:** district-reference forecasts. **TangaBid / eSoko:** dated market observations when available. **Google Gemini:** optional, consent-based agricultural guidance and image review.')
        st.caption('Research evaluation only: ISRIC SoilGrids and Sentinel-2 via Google Earth Engine. They are not live inputs to the deployed harvest models.')
    st.markdown('<div class="footer"> IhingaAI · Agricultural decision support · Harvest estimates are not guaranteed outcomes.</div>', unsafe_allow_html=True)


if __name__ == '__main__':
    main()
