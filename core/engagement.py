"""Role-isolated chat history, crop observations, and opt-in farmer directory."""
import json
import sqlite3
from .accounts import connect, DB_PATH

ROLES = {'farmer', 'agronomist', 'planner'}

def init_engagement(path=DB_PATH):
    with connect(path) as db:
        db.executescript('''
        CREATE TABLE IF NOT EXISTS ai_conversations (
          id INTEGER PRIMARY KEY, role TEXT NOT NULL, owner_id INTEGER NOT NULL,
          title TEXT NOT NULL, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS ai_messages (
          id INTEGER PRIMARY KEY, conversation_id INTEGER NOT NULL REFERENCES ai_conversations(id) ON DELETE CASCADE,
          speaker TEXT NOT NULL, body TEXT NOT NULL, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
        CREATE INDEX IF NOT EXISTS idx_conv_owner ON ai_conversations(role,owner_id);
        CREATE TABLE IF NOT EXISTS crop_observations (
          id INTEGER PRIMARY KEY, farmer_id INTEGER NOT NULL REFERENCES farmers(id) ON DELETE CASCADE,
          field_id INTEGER NOT NULL REFERENCES fields(id) ON DELETE CASCADE,
          stage TEXT NOT NULL, symptom TEXT NOT NULL, notes TEXT NOT NULL,
          ai_summary TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS farmer_directory (
          farmer_id INTEGER PRIMARY KEY REFERENCES farmers(id) ON DELETE CASCADE,
          visible INTEGER NOT NULL DEFAULT 0, contact_allowed INTEGER NOT NULL DEFAULT 0);
        ''')

def create_chat(role, owner, title, path=DB_PATH):
    if role not in ROLES: raise ValueError('Invalid role')
    with connect(path) as db:
        return db.execute('INSERT INTO ai_conversations(role,owner_id,title) VALUES(?,?,?)',(role,owner,title[:110])).lastrowid

def list_chats(role, owner, path=DB_PATH):
    with connect(path) as db:
        return [dict(r) for r in db.execute('SELECT * FROM ai_conversations WHERE role=? AND owner_id=? ORDER BY id DESC',(role,owner))]

def get_messages(role, owner, chat_id, path=DB_PATH):
    with connect(path) as db:
        return [dict(r) for r in db.execute('''SELECT m.* FROM ai_messages m JOIN ai_conversations c ON c.id=m.conversation_id
          WHERE c.id=? AND c.role=? AND c.owner_id=? ORDER BY m.id''',(chat_id,role,owner))]

def add_message(role,owner,chat_id,speaker,body,path=DB_PATH):
    if speaker not in ('user','assistant'): raise ValueError('Invalid speaker')
    with connect(path) as db:
        allowed=db.execute('SELECT 1 FROM ai_conversations WHERE id=? AND role=? AND owner_id=?',(chat_id,role,owner)).fetchone()
        if not allowed:raise PermissionError('Conversation inaccessible')
        return db.execute('INSERT INTO ai_messages(conversation_id,speaker,body) VALUES(?,?,?)',(chat_id,speaker,body[:6000])).lastrowid

def delete_chat(role,owner,chat_id,path=DB_PATH):
    with connect(path) as db:
        return db.execute('DELETE FROM ai_conversations WHERE id=? AND role=? AND owner_id=?',(chat_id,role,owner)).rowcount>0

def add_observation(owner,field_id,stage,symptom,notes,ai_summary=None,path=DB_PATH):
    with connect(path) as db:
        allowed=db.execute('SELECT 1 FROM fields WHERE id=? AND farmer_id=?',(field_id,owner)).fetchone()
        if not allowed: raise PermissionError('Field not owned by farmer')
        return db.execute('INSERT INTO crop_observations(farmer_id,field_id,stage,symptom,notes,ai_summary) VALUES(?,?,?,?,?,?)',
            (owner,field_id,stage[:120],symptom[:300],notes[:1200],(ai_summary or '')[:6000])).lastrowid

def observations(owner,field_id=None,path=DB_PATH):
    with connect(path) as db:
        sql='SELECT o.*,f.name AS field_name FROM crop_observations o JOIN fields f ON f.id=o.field_id AND f.farmer_id=o.farmer_id WHERE o.farmer_id=?'
        args=[owner]
        if field_id is not None:sql+=' AND o.field_id=?';args.append(field_id)
        return [dict(r) for r in db.execute(sql+' ORDER BY o.id DESC',args)]

def set_directory(owner,visible,contact_allowed,path=DB_PATH):
    with connect(path) as db:
        db.execute('INSERT INTO farmer_directory(farmer_id,visible,contact_allowed) VALUES(?,?,?) ON CONFLICT(farmer_id) DO UPDATE SET visible=excluded.visible, contact_allowed=excluded.contact_allowed',
            (owner,int(visible),int(contact_allowed)))

def directory_settings(owner,path=DB_PATH):
    with connect(path) as db:
        r=db.execute('SELECT * FROM farmer_directory WHERE farmer_id=?',(owner,)).fetchone()
        return dict(r) if r else {'visible':0,'contact_allowed':0}

def find_peers(owner,crop=None,district=None,path=DB_PATH):
    # Peer visibility is opt-in; do not expose fields or phone without contact_allowed.
    with connect(path) as db:
        sql='''SELECT DISTINCT f.farmer_id, fm.full_name, f.crop_code, f.district_code, d.contact_allowed,
               CASE WHEN d.contact_allowed=1 THEN fm.phone ELSE NULL END AS phone
               FROM fields f JOIN farmers fm ON fm.id=f.farmer_id JOIN farmer_directory d ON d.farmer_id=f.farmer_id
               WHERE d.visible=1 AND f.farmer_id<>?'''
        args=[owner]
        if crop: sql+=' AND f.crop_code=?';args.append(crop)
        if district:sql+=' AND f.district_code=?';args.append(district)
        return [dict(r) for r in db.execute(sql+' LIMIT 80',args)]


def observations_for_advisor(advisor_id,field_id,path=DB_PATH):
    """Read only records for a currently assigned and consent-enabled farmer field."""
    with connect(path) as db:
        rows=db.execute('''SELECT o.id,o.created_at,o.stage,o.symptom,o.notes,o.ai_summary
            FROM crop_observations o JOIN fields f ON f.id=o.field_id AND f.farmer_id=o.farmer_id
            JOIN farmer_assignments a ON a.farmer_id=f.farmer_id AND a.agronomist_id=? AND a.active=1
            JOIN advisor_permissions p ON p.farmer_id=f.farmer_id AND p.allow_assignment=1
            WHERE f.id=? ORDER BY o.id DESC''' ,(advisor_id,field_id)).fetchall()
        return [dict(r) for r in rows]
