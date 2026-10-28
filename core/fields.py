"""Private farmer field records, immutable prediction snapshots, farmer-created tasks, and harvest reports."""
import json
from datetime import date
from .accounts import connect, DB_PATH

MODEL_VERSION = 'IhingaAI_Frozen_v1 / IhingaAI_Extension_v1 (routed)'


def init_fields(path=DB_PATH):
    with connect(path) as db:
        db.executescript('''
        CREATE TABLE IF NOT EXISTS fields (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            farmer_id INTEGER NOT NULL REFERENCES farmers(id) ON DELETE CASCADE,
            name TEXT NOT NULL, crop_code TEXT NOT NULL, season TEXT NOT NULL,
            district_code TEXT NOT NULL, area_sqm REAL NOT NULL CHECK(area_sqm > 0),
            farmer_type_code TEXT NOT NULL DEFAULT '1',
            seed_type TEXT NOT NULL DEFAULT 'unknown', planting_date TEXT,
            planned_practices TEXT NOT NULL DEFAULT '', harvest_this_season INTEGER,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX IF NOT EXISTS idx_fields_owner ON fields(farmer_id);
        CREATE TABLE IF NOT EXISTS estimates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            farmer_id INTEGER NOT NULL REFERENCES farmers(id) ON DELETE CASCADE,
            field_id INTEGER NOT NULL REFERENCES fields(id) ON DELETE CASCADE,
            model_version TEXT NOT NULL, input_json TEXT NOT NULL, output_json TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX IF NOT EXISTS idx_estimates_owner ON estimates(farmer_id,field_id);
        CREATE TABLE IF NOT EXISTS activities (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            farmer_id INTEGER NOT NULL REFERENCES farmers(id) ON DELETE CASCADE,
            field_id INTEGER NOT NULL REFERENCES fields(id) ON DELETE CASCADE,
            title TEXT NOT NULL, due_date TEXT, completed INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            completed_at TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_activities_owner ON activities(farmer_id,field_id);
        CREATE TABLE IF NOT EXISTS harvest_reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            farmer_id INTEGER NOT NULL REFERENCES farmers(id) ON DELETE CASCADE,
            field_id INTEGER NOT NULL REFERENCES fields(id) ON DELETE CASCADE,
            actual_kg REAL NOT NULL CHECK(actual_kg >= 0),
            notes TEXT NOT NULL DEFAULT '',
            reported_date TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX IF NOT EXISTS idx_harvest_reports_owner ON harvest_reports(farmer_id, field_id);
        ''')


def _validate(name, crop, season, district, area, farmer_type, seed, planting, practices):
    if not (1 <= len(name.strip()) <= 80): raise ValueError('Field name must be 1–80 characters.')
    if not (0 < float(area) <= 1e10): raise ValueError('Enter a valid positive field area.')
    if season not in {'A','B','C'} or not crop or not district: raise ValueError('Choose a valid crop, season and district.')
    if farmer_type not in {'1','2','3','4'}: raise ValueError('Invalid farmer type.')
    if seed not in {'unknown','local','improved'}: raise ValueError('Invalid seed type.')
    if planting: date.fromisoformat(planting)
    if len(practices)>1500: raise ValueError('Practice notes must be under 1,500 characters.')


def create_field(owner, name, crop, season, district, area_sqm, farmer_type='1', seed='unknown', planting=None, practices='', harvest=None, path=DB_PATH):
    _validate(name,crop,season,district,area_sqm,farmer_type,seed,planting,practices)
    with connect(path) as db:
        cur=db.execute('''INSERT INTO fields(farmer_id,name,crop_code,season,district_code,area_sqm,farmer_type_code,seed_type,planting_date,planned_practices,harvest_this_season)
            VALUES (?,?,?,?,?,?,?,?,?,?,?)''',(owner,name.strip(),crop,season,district,float(area_sqm),farmer_type,seed,planting,practices,None if harvest is None else int(harvest)))
        return cur.lastrowid


def list_fields(owner,path=DB_PATH):
    with connect(path) as db:
        return [dict(r) for r in db.execute('SELECT * FROM fields WHERE farmer_id=? ORDER BY id DESC',(owner,))]


def get_field(owner,field_id,path=DB_PATH):
    with connect(path) as db:
        r=db.execute('SELECT * FROM fields WHERE farmer_id=? AND id=?',(owner,field_id)).fetchone()
        return dict(r) if r else None


def update_field(owner,field_id,name,crop,season,district,area_sqm,farmer_type='1',seed='unknown',planting=None,practices='',harvest=None,path=DB_PATH):
    _validate(name,crop,season,district,area_sqm,farmer_type,seed,planting,practices)
    with connect(path) as db:
        cur=db.execute('''UPDATE fields SET name=?,crop_code=?,season=?,district_code=?,area_sqm=?,farmer_type_code=?,seed_type=?,planting_date=?,planned_practices=?,harvest_this_season=?,updated_at=CURRENT_TIMESTAMP WHERE id=? AND farmer_id=?''',
            (name.strip(),crop,season,district,float(area_sqm),farmer_type,seed,planting,practices,None if harvest is None else int(harvest),field_id,owner))
        return cur.rowcount>0


def delete_field(owner,field_id,path=DB_PATH):
    with connect(path) as db:
        return db.execute('DELETE FROM fields WHERE id=? AND farmer_id=?',(field_id,owner)).rowcount>0


def save_estimate(owner,field_id,input_values,result,path=DB_PATH):
    if not get_field(owner,field_id,path): raise PermissionError('Field is not owned by this account.')
    with connect(path) as db:
        cur=db.execute('INSERT INTO estimates(farmer_id,field_id,model_version,input_json,output_json) VALUES (?,?,?,?,?)',
           (owner,field_id,MODEL_VERSION,json.dumps(input_values),json.dumps(result)))
        return cur.lastrowid


def list_estimates(owner,field_id=None,path=DB_PATH):
    query='SELECT * FROM estimates WHERE farmer_id=?'; args=[owner]
    if field_id is not None: query+=' AND field_id=?'; args.append(field_id)
    with connect(path) as db:
        return [dict(r) for r in db.execute(query+' ORDER BY id DESC',args)]


def add_activity(owner,field_id,title,due=None,path=DB_PATH):
    title=title.strip()
    if not (1<=len(title)<=180): raise ValueError('Enter a task title (1–180 characters).')
    if due: date.fromisoformat(due)
    if not get_field(owner,field_id,path): raise PermissionError('Field not found.')
    with connect(path) as db:
        return db.execute('INSERT INTO activities(farmer_id,field_id,title,due_date) VALUES (?,?,?,?)',(owner,field_id,title,due)).lastrowid


def list_activities(owner,field_id=None,path=DB_PATH):
    q='SELECT a.*,f.name AS field_name FROM activities a JOIN fields f ON f.id=a.field_id AND f.farmer_id=a.farmer_id WHERE a.farmer_id=?'; args=[owner]
    if field_id is not None: q+=' AND a.field_id=?'; args.append(field_id)
    with connect(path) as db:
        return [dict(r) for r in db.execute(q+' ORDER BY a.completed, a.due_date IS NULL, a.due_date, a.id DESC',args)]


def set_activity_done(owner,activity_id,done,path=DB_PATH):
    with connect(path) as db:
        return db.execute('UPDATE activities SET completed=?,completed_at=CASE WHEN ? THEN CURRENT_TIMESTAMP ELSE NULL END WHERE id=? AND farmer_id=?',
              (int(done),int(done),activity_id,owner)).rowcount>0


def delete_activity(owner,activity_id,path=DB_PATH):
    with connect(path) as db:
        return db.execute('DELETE FROM activities WHERE id=? AND farmer_id=?',(activity_id,owner)).rowcount>0


def report_actual_harvest(owner, field_id, actual_kg, reported_date=None, notes='', path=DB_PATH):
    if not get_field(owner, field_id, path):
        raise PermissionError('Field not found.')
    actual_kg = float(actual_kg)
    if actual_kg < 0:
        raise ValueError('Actual harvest must be zero or greater.')
    if reported_date is None:
        reported_date = date.today().isoformat()
    date.fromisoformat(reported_date)
    notes = notes.strip()
    if len(notes) > 1200:
        raise ValueError('Harvest notes must be under 1,200 characters.')
    with connect(path) as db:
        return db.execute('INSERT INTO harvest_reports(farmer_id, field_id, actual_kg, notes, reported_date) VALUES (?,?,?,?,?)',
                          (owner, field_id, actual_kg, notes, reported_date)).lastrowid


def list_harvest_reports(owner, field_id=None, path=DB_PATH):
    q = 'SELECT h.*, f.name AS field_name FROM harvest_reports h JOIN fields f ON f.id=h.field_id AND f.farmer_id=h.farmer_id WHERE h.farmer_id=?'
    args = [owner]
    if field_id is not None:
        q += ' AND h.field_id=?'; args.append(field_id)
    with connect(path) as db:
        return [dict(r) for r in db.execute(q + ' ORDER BY h.reported_date DESC, h.id DESC', args)]
