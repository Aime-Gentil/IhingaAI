"""Private farmer-owned saved harvest predictions, independently of a registered field."""
import json
from .accounts import connect, DB_PATH
from .fields import MODEL_VERSION

def init_store(path=DB_PATH):
    with connect(path) as db:
        db.execute("""CREATE TABLE IF NOT EXISTS independent_estimates (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          farmer_id INTEGER NOT NULL REFERENCES farmers(id) ON DELETE CASCADE,
          input_json TEXT NOT NULL,
          output_json TEXT NOT NULL,
          model_version TEXT NOT NULL,
          created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )""")
        db.execute("CREATE INDEX IF NOT EXISTS idx_independent_estimates_owner ON independent_estimates(farmer_id,id)")

def save(owner, inputs, result, path=DB_PATH):
    if not isinstance(result,dict) or result.get('status')!='ok':
        raise ValueError('Only successful predictions may be saved.')
    if not owner:raise PermissionError('Sign in before saving a prediction.')
    with connect(path) as db:
        cur=db.execute('INSERT INTO independent_estimates(farmer_id,input_json,output_json,model_version) VALUES (?,?,?,?)',
                       (owner,json.dumps(inputs),json.dumps(result),MODEL_VERSION))
        return cur.lastrowid

def recent(owner,limit=50,path=DB_PATH):
    if not owner:return []
    with connect(path) as db:
        return [dict(r) for r in db.execute('SELECT * FROM independent_estimates WHERE farmer_id=? ORDER BY id DESC LIMIT ?',
                (owner,int(min(max(limit,1),100))))]
