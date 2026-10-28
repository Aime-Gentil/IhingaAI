"""Consent-bound farmer / assigned agronomist consultation threads.

Every advisor read/write rechecks an *active* assignment and farmer consent.
A farmer's own conversations remain readable after they revoke access.
"""
from .accounts import connect, DB_PATH

STATUSES = ('Open', 'Responded', 'Closed')


def init_consultations(path=DB_PATH):
    with connect(path) as db:
        db.executescript('''
        CREATE TABLE IF NOT EXISTS farm_consultations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            farmer_id INTEGER NOT NULL REFERENCES farmers(id) ON DELETE CASCADE,
            field_id INTEGER NOT NULL REFERENCES fields(id) ON DELETE CASCADE,
            advisor_id INTEGER NOT NULL REFERENCES agronomists(id) ON DELETE CASCADE,
            subject TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'Open',
            observation_id INTEGER REFERENCES crop_observations(id) ON DELETE SET NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS farm_consultation_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            consultation_id INTEGER NOT NULL REFERENCES farm_consultations(id) ON DELETE CASCADE,
            sender_role TEXT NOT NULL CHECK (sender_role IN ('farmer','agronomist')),
            sender_id INTEGER NOT NULL,
            body TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
        CREATE INDEX IF NOT EXISTS idx_con_owner ON farm_consultations(farmer_id,field_id);
        CREATE INDEX IF NOT EXISTS idx_con_advisor ON farm_consultations(advisor_id,status);
        ''')


def available_advisors(farmer_id, field_id, path=DB_PATH):
    with connect(path) as db:
        return [dict(r) for r in db.execute('''SELECT DISTINCT a.id,a.name FROM farmers fm
            JOIN fields f ON f.farmer_id=fm.id AND f.id=?
            JOIN advisor_permissions p ON p.farmer_id=fm.id AND p.allow_assignment=1
            JOIN farmer_assignments x ON x.farmer_id=fm.id AND x.active=1
            JOIN agronomists a ON a.id=x.agronomist_id
            WHERE fm.id=? ORDER BY a.name''',(field_id,farmer_id))]


def _authorized(db, farmer_id, field_id, advisor_id):
    return db.execute('''SELECT 1 FROM fields f
        JOIN advisor_permissions p ON p.farmer_id=f.farmer_id AND p.allow_assignment=1
        JOIN farmer_assignments a ON a.farmer_id=f.farmer_id AND a.active=1
        WHERE f.id=? AND f.farmer_id=? AND a.agronomist_id=?''',
        (field_id,farmer_id,advisor_id)).fetchone() is not None


def open_request(farmer_id, field_id, advisor_id, subject, message, observation_id=None, path=DB_PATH):
    subject=subject.strip();message=message.strip()
    if not 5<=len(subject)<=140 or not 10<=len(message)<=2500:
        raise ValueError('Provide a subject (5–140 characters) and description (10–2500 characters).')
    with connect(path) as db:
        if not _authorized(db,farmer_id,field_id,advisor_id):
            raise PermissionError('This field is not currently shared with the selected agronomist.')
        if observation_id is not None and not db.execute('''SELECT 1 FROM crop_observations
            WHERE id=? AND farmer_id=? AND field_id=?''',(observation_id,farmer_id,field_id)).fetchone():
            raise PermissionError('Cannot attach someone else’s crop observation.')
        cur=db.execute('''INSERT INTO farm_consultations(farmer_id,field_id,advisor_id,subject,observation_id)
                           VALUES(?,?,?,?,?)''',(farmer_id,field_id,advisor_id,subject,observation_id))
        db.execute('''INSERT INTO farm_consultation_messages(consultation_id,sender_role,sender_id,body)
                       VALUES(?,?,?,?)''',(cur.lastrowid,'farmer',farmer_id,message))
        return cur.lastrowid


def consultations_for_farmer(farmer_id, path=DB_PATH):
    with connect(path) as db:
        return [dict(r) for r in db.execute('''SELECT c.*,f.name AS field_name,a.name AS advisor_name,
           (SELECT COUNT(*) FROM farm_consultation_messages m WHERE m.consultation_id=c.id AND m.sender_role='agronomist') AS replies
           FROM farm_consultations c JOIN fields f ON f.id=c.field_id AND f.farmer_id=c.farmer_id
           JOIN agronomists a ON a.id=c.advisor_id WHERE c.farmer_id=? ORDER BY c.updated_at DESC,c.id DESC''',(farmer_id,))]


def consultations_for_advisor(advisor_id, path=DB_PATH):
    with connect(path) as db:
        return [dict(r) for r in db.execute('''SELECT c.*,f.name AS field_name,fm.full_name AS farmer_name
           FROM farm_consultations c JOIN fields f ON f.id=c.field_id AND f.farmer_id=c.farmer_id
           JOIN farmers fm ON fm.id=c.farmer_id
           JOIN farmer_assignments x ON x.farmer_id=c.farmer_id AND x.agronomist_id=c.advisor_id AND x.active=1
           JOIN advisor_permissions p ON p.farmer_id=c.farmer_id AND p.allow_assignment=1
           WHERE c.advisor_id=? ORDER BY c.updated_at DESC,c.id DESC''',(advisor_id,))]


def _thread_access(db, role, actor_id, consultation_id):
    row=db.execute('SELECT * FROM farm_consultations WHERE id=?',(consultation_id,)).fetchone()
    if row is None:raise PermissionError('Consultation not available.')
    if role=='farmer' and row['farmer_id']==actor_id:return row
    if role=='agronomist' and row['advisor_id']==actor_id and _authorized(db,row['farmer_id'],row['field_id'],actor_id):return row
    raise PermissionError('Consultation not accessible to this account.')


def messages(role,actor_id,consultation_id,path=DB_PATH):
    with connect(path) as db:
        _thread_access(db,role,actor_id,consultation_id)
        return [dict(r) for r in db.execute('''SELECT sender_role,body,created_at FROM farm_consultation_messages
                WHERE consultation_id=? ORDER BY id''',(consultation_id,))]


def reply(role,actor_id,consultation_id,message,path=DB_PATH):
    message=message.strip()
    if not 2<=len(message)<=2500:raise ValueError('Reply must contain 2–2500 characters.')
    with connect(path) as db:
        item=_thread_access(db,role,actor_id,consultation_id)
        if item['status']=='Closed':raise ValueError('This consultation is closed. Open a new request if necessary.')
        if role=='farmer' and not _authorized(db,item['farmer_id'],item['field_id'],item['advisor_id']):
            raise PermissionError('Sharing is inactive. Re-enable assignment and ask the planner to reassign the advisor.')
        db.execute('''INSERT INTO farm_consultation_messages(consultation_id,sender_role,sender_id,body)
                VALUES(?,?,?,?)''',(consultation_id,role,actor_id,message))
        db.execute('UPDATE farm_consultations SET status=?,updated_at=CURRENT_TIMESTAMP WHERE id=?',
                   ('Responded' if role=='agronomist' else 'Open',consultation_id))


def close(farmer_id,consultation_id,path=DB_PATH):
    with connect(path) as db:
        return db.execute("UPDATE farm_consultations SET status='Closed',updated_at=CURRENT_TIMESTAMP WHERE id=? AND farmer_id=? AND status!='Closed'",
                          (consultation_id,farmer_id)).rowcount>0
