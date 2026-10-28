"""Planner-managed farmer-to-agronomist assignments with farmer permission."""
from .accounts import connect, DB_PATH


def init_assignments(path=DB_PATH):
    with connect(path) as db:
        db.executescript('''
        CREATE TABLE IF NOT EXISTS advisor_permissions (
            farmer_id INTEGER PRIMARY KEY REFERENCES farmers(id) ON DELETE CASCADE,
            allow_assignment INTEGER NOT NULL DEFAULT 0,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS farmer_assignments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            farmer_id INTEGER NOT NULL REFERENCES farmers(id) ON DELETE CASCADE,
            agronomist_id INTEGER NOT NULL REFERENCES agronomists(id) ON DELETE CASCADE,
            planner_id INTEGER NOT NULL REFERENCES planners(id) ON DELETE CASCADE,
            active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            ended_at TEXT,
            UNIQUE(farmer_id,agronomist_id)
        );
        ''')


def allows_assignment(farmer_id,path=DB_PATH):
    with connect(path) as db:
        r=db.execute('SELECT allow_assignment FROM advisor_permissions WHERE farmer_id=?',(farmer_id,)).fetchone()
        return bool(r and r['allow_assignment'])


def set_permission(farmer_id, allowed, path=DB_PATH):
    with connect(path) as db:
        db.execute('INSERT INTO advisor_permissions(farmer_id,allow_assignment) VALUES(?,?) ON CONFLICT(farmer_id) DO UPDATE SET allow_assignment=excluded.allow_assignment,updated_at=CURRENT_TIMESTAMP',(farmer_id,int(allowed)))
        if not allowed:
            db.execute('UPDATE farmer_assignments SET active=0,ended_at=CURRENT_TIMESTAMP WHERE farmer_id=? AND active=1',(farmer_id,))


def available_farmers(path=DB_PATH):
    with connect(path) as db:
        return [dict(r) for r in db.execute('''SELECT f.id,f.full_name, COUNT(fi.id) AS fields FROM farmers f
                JOIN advisor_permissions ap ON ap.farmer_id=f.id AND ap.allow_assignment=1
                LEFT JOIN fields fi ON fi.farmer_id=f.id GROUP BY f.id ORDER BY f.full_name''')]


def list_advisors(path=DB_PATH):
    with connect(path) as db:
        return [dict(r) for r in db.execute('SELECT id,name FROM agronomists ORDER BY name')]


def assign(planner_id,farmer_id,advisor_id,path=DB_PATH):
    with connect(path) as db:
        if not db.execute('SELECT 1 FROM planners WHERE id=?',(planner_id,)).fetchone(): raise PermissionError('Planner not found.')
        if not db.execute('SELECT 1 FROM agronomists WHERE id=?',(advisor_id,)).fetchone(): raise ValueError('Agronomist not found.')
        permit=db.execute('SELECT allow_assignment FROM advisor_permissions WHERE farmer_id=?',(farmer_id,)).fetchone()
        if not permit or not permit['allow_assignment']: raise PermissionError('Farmer has not enabled sharing.')
        db.execute('''INSERT INTO farmer_assignments(farmer_id,agronomist_id,planner_id,active,ended_at)
            VALUES(?,?,?,1,NULL) ON CONFLICT(farmer_id,agronomist_id) DO UPDATE SET active=1,planner_id=excluded.planner_id,ended_at=NULL''',
            (farmer_id,advisor_id,planner_id))


def unassign(planner_id,assignment_id,path=DB_PATH):
    with connect(path) as db:
        if not db.execute('SELECT 1 FROM planners WHERE id=?',(planner_id,)).fetchone(): raise PermissionError('Planner not found.')
        return db.execute('UPDATE farmer_assignments SET active=0,ended_at=CURRENT_TIMESTAMP WHERE id=? AND active=1',(assignment_id,)).rowcount>0


def active_assignments(path=DB_PATH):
    with connect(path) as db:
        return [dict(r) for r in db.execute('''SELECT x.id,x.farmer_id,x.agronomist_id, f.full_name AS farmer_name,a.name AS advisor_name
         FROM farmer_assignments x JOIN farmers f ON f.id=x.farmer_id JOIN agronomists a ON a.id=x.agronomist_id
         JOIN advisor_permissions p ON p.farmer_id=x.farmer_id AND p.allow_assignment=1
         WHERE x.active=1 ORDER BY f.full_name''')]


def assigned_farmer_ids(advisor_id,path=DB_PATH):
    with connect(path) as db:
        return {r['farmer_id'] for r in db.execute('''SELECT x.farmer_id FROM farmer_assignments x
        JOIN advisor_permissions p ON p.farmer_id=x.farmer_id AND p.allow_assignment=1
        WHERE x.agronomist_id=? AND x.active=1''',(advisor_id,))}


def assigned_fields(advisor_id,path=DB_PATH):
    with connect(path) as db:
        return [dict(r) for r in db.execute('''SELECT f.id,f.name,f.crop_code,f.season,f.district_code,f.area_sqm,
        f.planting_date,f.seed_type,f.planned_practices, fm.full_name AS farmer_name,fm.phone AS farmer_phone
        FROM farmer_assignments x JOIN advisor_permissions p ON p.farmer_id=x.farmer_id AND p.allow_assignment=1
        JOIN fields f ON f.farmer_id=x.farmer_id JOIN farmers fm ON fm.id=x.farmer_id
        WHERE x.agronomist_id=? AND x.active=1 ORDER BY f.id DESC''',(advisor_id,))]
