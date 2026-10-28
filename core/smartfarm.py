"""Weather (approximate district-center), calendars, consent-based agronomist access, and planner accounts."""
import json
import secrets
import sqlite3
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
import re

from .accounts import connect, DB_PATH, hash_password, verify_password
from . import assignments as A

_WEATHER_POINTS = Path(__file__).resolve().parents[1] / 'data' / 'district_weather_points.json'


def _ensure_column(db, table, column_def):
    name = column_def.split()[0]
    cols = {row['name'] for row in db.execute(f'PRAGMA table_info({table})')}
    if name not in cols:
        db.execute(f'ALTER TABLE {table} ADD COLUMN {column_def}')


def init_smart(path=DB_PATH):
    with connect(path) as db:
        db.executescript('''
        CREATE TABLE IF NOT EXISTS agronomists (
          id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL,
          phone TEXT NOT NULL UNIQUE, password_hash TEXT NOT NULL,
          created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS planners (
          id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL,
          phone TEXT NOT NULL UNIQUE, password_hash TEXT NOT NULL,
          created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS field_shares (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          farmer_id INTEGER NOT NULL REFERENCES farmers(id) ON DELETE CASCADE,
          field_id INTEGER NOT NULL REFERENCES fields(id) ON DELETE CASCADE,
          agronomist_id INTEGER REFERENCES agronomists(id) ON DELETE CASCADE,
          invite_token TEXT NOT NULL UNIQUE, active INTEGER NOT NULL DEFAULT 1,
          created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          accepted_at TEXT, revoked_at TEXT,
          UNIQUE(field_id,agronomist_id));
        CREATE TABLE IF NOT EXISTS agronomist_notes (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          field_id INTEGER NOT NULL REFERENCES fields(id) ON DELETE CASCADE,
          agronomist_id INTEGER NOT NULL REFERENCES agronomists(id) ON DELETE CASCADE,
          note TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
        CREATE INDEX IF NOT EXISTS idx_shares_farmer ON field_shares(farmer_id,active);
        CREATE INDEX IF NOT EXISTS idx_shares_advisor ON field_shares(agronomist_id,active);
        ''')


def create_agronomist(name, phone, password, path=DB_PATH):
    from .accounts import normalize_phone
    name = ' '.join(name.split()); phone = normalize_phone(phone)
    if not 2 <= len(name) <= 100 or not 8 <= len(password) <= 128:
        raise ValueError('Enter a name and password of at least 8 characters.')
    with connect(path) as db:
        try:
            return db.execute('INSERT INTO agronomists(name,phone,password_hash) VALUES(?,?,?)',
                              (name,phone,hash_password(password))).lastrowid
        except sqlite3.IntegrityError:
            raise ValueError('This agronomist phone is already registered.')


def advisor_login(phone,password,path=DB_PATH):
    from .accounts import normalize_phone
    try: phone=normalize_phone(phone)
    except ValueError: return None
    with connect(path) as db:
        r=db.execute('SELECT * FROM agronomists WHERE phone=?',(phone,)).fetchone()
        if r and verify_password(password,r['password_hash']):
            return {'id':r['id'],'name':r['name']}
    return None


def advisor_by_id(id,path=DB_PATH):
    with connect(path) as db:
        r=db.execute('SELECT id,name,phone FROM agronomists WHERE id=?',(id,)).fetchone()
        return dict(r) if r else None


def create_planner(name, phone, password, path=DB_PATH):
    from .accounts import normalize_phone
    name = ' '.join(name.split()); phone = normalize_phone(phone)
    if not 2 <= len(name) <= 100 or not 8 <= len(password) <= 128:
        raise ValueError('Enter a name and password of at least 8 characters.')
    with connect(path) as db:
        try:
            return db.execute('INSERT INTO planners(name,phone,password_hash) VALUES(?,?,?)',
                              (name,phone,hash_password(password))).lastrowid
        except sqlite3.IntegrityError:
            raise ValueError('This planner phone is already registered.')


def planner_login(phone, password, path=DB_PATH):
    from .accounts import normalize_phone
    try: phone = normalize_phone(phone)
    except ValueError: return None
    with connect(path) as db:
        r = db.execute('SELECT * FROM planners WHERE phone=?', (phone,)).fetchone()
        if r and verify_password(password, r['password_hash']):
            return {'id': r['id'], 'name': r['name'], 'phone': r['phone']}
    return None


def planner_by_id(id, path=DB_PATH):
    with connect(path) as db:
        r = db.execute('SELECT id,name,phone FROM planners WHERE id=?', (id,)).fetchone()
        return dict(r) if r else None


def new_share(farmer_id,field_id,path=DB_PATH):
    from .fields import get_field
    if not get_field(farmer_id,field_id,path): raise PermissionError('Not your field')
    token=secrets.token_urlsafe(16)
    with connect(path) as db:
        db.execute('INSERT INTO field_shares(farmer_id,field_id,invite_token) VALUES(?,?,?)',
                   (farmer_id,field_id,token))
    return token


def shares_for_farmer(owner,path=DB_PATH):
    with connect(path) as db:
        return [dict(r) for r in db.execute('''SELECT s.*,f.name AS field_name,a.name AS advisor_name
          FROM field_shares s JOIN fields f ON f.id=s.field_id AND f.farmer_id=s.farmer_id
          LEFT JOIN agronomists a ON a.id=s.agronomist_id
          WHERE s.farmer_id=? ORDER BY s.id DESC''',(owner,))]


def revoke(owner,share_id,path=DB_PATH):
    with connect(path) as db:
        return db.execute('UPDATE field_shares SET active=0, revoked_at=CURRENT_TIMESTAMP,invite_token=? WHERE id=? AND farmer_id=? AND active=1',
                          (secrets.token_urlsafe(16),share_id,owner)).rowcount > 0


def redeem(advisor_id,token,path=DB_PATH):
    with connect(path) as db:
        row=db.execute('SELECT id,agronomist_id FROM field_shares WHERE invite_token=? AND active=1',(token.strip(),)).fetchone()
        if not row or row['agronomist_id'] is not None: return False
        return db.execute('UPDATE field_shares SET agronomist_id=?,accepted_at=CURRENT_TIMESTAMP WHERE id=? AND agronomist_id IS NULL AND active=1',
                          (advisor_id,row['id'])).rowcount>0


def advisor_fields(advisor_id,path=DB_PATH):
    with connect(path) as db:
        return [dict(r) for r in db.execute('''SELECT f.id,f.name,f.crop_code,f.season,f.district_code,f.area_sqm,f.planting_date,f.seed_type,f.planned_practices,
          s.id AS share_id, fm.full_name AS farmer_name, fm.phone AS farmer_phone
          FROM field_shares s JOIN fields f ON f.id=s.field_id AND f.farmer_id=s.farmer_id
          JOIN farmers fm ON fm.id=s.farmer_id
          WHERE s.agronomist_id=? AND s.active=1 ORDER BY s.id DESC''',(advisor_id,))]


def add_note(advisor_id,field_id,note,path=DB_PATH):
    note=note.strip()
    if not 1 <= len(note) <= 2000: raise ValueError('Note must be 1–2000 characters.')
    with connect(path) as db:
        authorized=db.execute('''SELECT 1 FROM farmer_assignments x JOIN fields f ON f.farmer_id=x.farmer_id
           JOIN advisor_permissions p ON p.farmer_id=x.farmer_id AND p.allow_assignment=1
           WHERE f.id=? AND x.agronomist_id=? AND x.active=1''', (field_id,advisor_id)).fetchone()
        if not authorized:
            authorized=db.execute('''SELECT 1 FROM field_shares WHERE field_id=? AND agronomist_id=? AND active=1''',(field_id,advisor_id)).fetchone()
        if not authorized: raise PermissionError('Access withdrawn or not granted.')
        return db.execute('INSERT INTO agronomist_notes(field_id,agronomist_id,note) VALUES(?,?,?)',
                          (field_id,advisor_id,note)).lastrowid


def farmer_notes(owner,path=DB_PATH):
    with connect(path) as db:
        return [dict(r) for r in db.execute('''SELECT n.*,f.name AS field_name,a.name AS advisor_name FROM agronomist_notes n
          JOIN fields f ON n.field_id=f.id JOIN agronomists a ON a.id=n.agronomist_id
          WHERE f.farmer_id=? ORDER BY n.id DESC''',(owner,))]


def advisor_notes(advisor_id,path=DB_PATH):
    with connect(path) as db:
        return [dict(r) for r in db.execute('''SELECT n.*,f.name AS field_name, fm.full_name AS farmer_name
          FROM agronomist_notes n JOIN fields f ON f.id=n.field_id JOIN farmers fm ON fm.id=f.farmer_id
          WHERE n.agronomist_id=? ORDER BY n.id DESC''', (advisor_id,))]


def _get_json(url, params, timeout=9):
    url += '?' + urllib.parse.urlencode(params)
    request=urllib.request.Request(url,headers={'User-Agent':'IhingaAI-demo/1.0'})
    with urllib.request.urlopen(request,timeout=timeout) as response:
        return json.load(response)


def resolve_weather_location(district):
    """Find an explicitly configured district point, without external name geocoding."""
    points = json.loads(_WEATHER_POINTS.read_text(encoding='utf-8'))['districts']
    raw = str(district).strip()
    name = re.split(r'\s+[—–-]\s+', raw, maxsplit=1)[0].strip().casefold()
    matches = [(code, point) for code, point in points.items()
               if code == raw or point['name'].casefold() == name]
    if len(matches) != 1:
        raise ValueError(f'No configured reference point for district {district!r}.')
    return matches[0]


def weather_for_district(district_name):
    """7-day forecast at an approximate configured district point; not field-level weather."""
    district_code, place = resolve_weather_location(district_name)
    data = _get_json('https://api.open-meteo.com/v1/forecast', {
        'latitude': place['latitude'], 'longitude': place['longitude'],
        'daily':'temperature_2m_max,temperature_2m_min,precipitation_sum,precipitation_probability_max',
        'timezone':'Africa/Kigali','forecast_days':7})
    daily = data.get('daily') or {}
    dates = daily.get('time') or []
    keys = ('temperature_2m_max','temperature_2m_min','precipitation_sum','precipitation_probability_max')
    if not dates or any(len(daily.get(k) or []) != len(dates) for k in keys):
        raise ValueError('Incomplete forecast response from weather provider.')
    rows = [{'date': t, 'max_c':daily['temperature_2m_max'][i],
             'min_c':daily['temperature_2m_min'][i], 'rain_mm':daily['precipitation_sum'][i],
             'rain_chance':daily['precipitation_probability_max'][i]}
            for i,t in enumerate(dates)]
    return {'location':place['name'], 'district_code':district_code,
            'latitude':place['latitude'],'longitude':place['longitude'],
            'daily':rows,'retrieved_at_utc':datetime.now(timezone.utc).isoformat(timespec='seconds'),
            'source':'Open-Meteo',
            'scope':'approximate district reference point; not a measured field location'}


def create_planner_authorized(name, phone, password, setup_code, path=DB_PATH, configured_code=None):
    """Provision planner only with an explicitly configured local setup code.

    Existing planner accounts continue to authenticate normally. No default secret.
    """
    import hmac
    import os
    if configured_code is None:
        configured_code = os.getenv('IHINGAAI_PLANNER_SETUP_CODE', '')
        if not configured_code:
            try:
                import streamlit as st
                configured_code = str(st.secrets.get('PLANNER_SETUP_CODE', ''))
            except Exception:
                configured_code = ''
    if len(configured_code) < 12 or not hmac.compare_digest(str(setup_code), configured_code):
        raise PermissionError('Administrator setup code is missing or incorrect.')
    return create_planner(name, phone, password, path)
