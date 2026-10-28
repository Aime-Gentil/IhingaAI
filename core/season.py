"""Farmer-owned season progress, financial journal, and explainable alert rules.

Financial figures are user-entered RWF transactions, not market data or model facts.
All reads/writes enforce farmer ownership at SQL-query level.
"""
from datetime import date, timedelta
from math import isfinite
from .accounts import connect, DB_PATH

STAGES = ('Planning', 'Land preparation', 'Planted', 'Growing', 'Flowering / fruiting', 'Harvest ready', 'Harvested')
EXPENSE_CATEGORIES = ('Seeds', 'Fertilizer / manure', 'Labor', 'Transport', 'Irrigation', 'Crop protection', 'Equipment', 'Other')


def init_season(path=DB_PATH):
    with connect(path) as db:
        db.executescript('''
        CREATE TABLE IF NOT EXISTS field_season_progress (
            farmer_id INTEGER NOT NULL REFERENCES farmers(id) ON DELETE CASCADE,
            field_id INTEGER NOT NULL REFERENCES fields(id) ON DELETE CASCADE,
            stage TEXT NOT NULL DEFAULT 'Planning',
            note TEXT NOT NULL DEFAULT '',
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (farmer_id, field_id)
        );
        CREATE TABLE IF NOT EXISTS farm_transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            farmer_id INTEGER NOT NULL REFERENCES farmers(id) ON DELETE CASCADE,
            field_id INTEGER NOT NULL REFERENCES fields(id) ON DELETE CASCADE,
            kind TEXT NOT NULL CHECK(kind IN ('expense','sale')),
            category TEXT NOT NULL,
            amount_rwf REAL NOT NULL CHECK(amount_rwf >= 0),
            quantity_kg REAL CHECK(quantity_kg IS NULL OR quantity_kg > 0),
            transaction_date TEXT NOT NULL,
            note TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX IF NOT EXISTS ix_transactions_farmer_field ON farm_transactions(farmer_id, field_id, transaction_date);
        ''')


def _owned(db, farmer_id, field_id):
    return db.execute('SELECT 1 FROM fields WHERE id=? AND farmer_id=?', (field_id, farmer_id)).fetchone() is not None


def _date(value):
    if isinstance(value, date): value = value.isoformat()
    return date.fromisoformat(str(value)).isoformat()


def set_stage(farmer_id, field_id, stage, note='', path=DB_PATH):
    if stage not in STAGES: raise ValueError('Unknown farming stage.')
    note = note.strip()
    if len(note) > 500: raise ValueError('Stage note must be 500 characters or fewer.')
    with connect(path) as db:
        if not _owned(db, farmer_id, field_id): raise PermissionError('Field is not owned by this farmer.')
        db.execute('''INSERT INTO field_season_progress(farmer_id,field_id,stage,note) VALUES(?,?,?,?)
            ON CONFLICT(farmer_id,field_id) DO UPDATE SET stage=excluded.stage,note=excluded.note,
            updated_at=CURRENT_TIMESTAMP''', (farmer_id,field_id,stage,note))


def progress(farmer_id, path=DB_PATH):
    with connect(path) as db:
        return {r['field_id']:dict(r) for r in db.execute('''SELECT p.* FROM field_season_progress p
            JOIN fields f ON f.id=p.field_id AND f.farmer_id=p.farmer_id
            WHERE p.farmer_id=?''', (farmer_id,))}


def add_transaction(farmer_id, field_id, kind, category, amount_rwf, transaction_date, note='', quantity_kg=None, path=DB_PATH):
    if kind not in ('expense','sale'): raise ValueError('Choose expense or sale.')
    if kind=='sale':
        if category!='Harvest sale': raise ValueError('Invalid sale category.')
    elif category not in EXPENSE_CATEGORIES: raise ValueError('Invalid expense category.')
    try: amount = float(amount_rwf)
    except (TypeError, ValueError): raise ValueError('Enter a valid amount in RWF.')
    if not isfinite(amount) or amount <= 0 or amount > 1e12: raise ValueError('Amount must be a positive, reasonable RWF value.')
    if quantity_kg is not None:
        try: quantity_kg = float(quantity_kg)
        except (TypeError, ValueError): raise ValueError('Enter a valid sold quantity.')
        if not isfinite(quantity_kg) or not 0 < quantity_kg <= 1e9: raise ValueError('Quantity sold must be positive.')
    if kind=='expense' and quantity_kg is not None: raise ValueError('Quantity is only for crop sales.')
    note=note.strip()
    if len(note)>600: raise ValueError('Transaction note is too long.')
    when=_date(transaction_date)
    if date.fromisoformat(when)>date.today(): raise ValueError('Cannot record future spending or sales as completed.')
    with connect(path) as db:
        if not _owned(db,farmer_id,field_id): raise PermissionError('Field is not owned by this farmer.')
        return db.execute('''INSERT INTO farm_transactions(farmer_id,field_id,kind,category,amount_rwf,quantity_kg,transaction_date,note)
            VALUES(?,?,?,?,?,?,?,?)''',(farmer_id,field_id,kind,category,amount,quantity_kg,when,note)).lastrowid


def transactions(farmer_id,field_id=None,path=DB_PATH):
    with connect(path) as db:
        q='''SELECT t.*,f.name AS field_name FROM farm_transactions t JOIN fields f
              ON t.field_id=f.id AND t.farmer_id=f.farmer_id WHERE t.farmer_id=?'''
        params=[farmer_id]
        if field_id is not None: q+=' AND t.field_id=?';params.append(field_id)
        return [dict(r) for r in db.execute(q+' ORDER BY transaction_date DESC,t.id DESC',params)]


def delete_transaction(farmer_id,transaction_id,path=DB_PATH):
    with connect(path) as db:
        return db.execute('DELETE FROM farm_transactions WHERE id=? AND farmer_id=?', (transaction_id,farmer_id)).rowcount>0


def totals(rows):
    expenses=sum(float(r['amount_rwf']) for r in rows if r['kind']=='expense')
    revenue=sum(float(r['amount_rwf']) for r in rows if r['kind']=='sale')
    sold_kg=sum(float(r['quantity_kg'] or 0) for r in rows if r['kind']=='sale')
    return {'expenses':expenses,'revenue':revenue,'net':revenue-expenses,'sold_kg':sold_kg,
            'cost_per_kg_sold':expenses/sold_kg if sold_kg>0 else None}


def local_alerts(farmer_id,fields,activities,observations,today=None):
    """Transparent on-page reminders. No disease diagnosis or autonomous notifications."""
    today=today or date.today()
    output=[]
    owned_ids={f['id'] for f in fields if f['farmer_id']==farmer_id}
    for task in activities:
        if task['field_id'] not in owned_ids or task['completed'] or not task['due_date']: continue
        try: due=date.fromisoformat(task['due_date'])
        except (TypeError,ValueError): continue
        days=(due-today).days
        if days<0:
            output.append({'level':'Overdue','field_id':task['field_id'],'title':task['title'],
                           'detail':f'Planned for {due.isoformat()} ({-days} days overdue). Check and update this task.','source':'Your activity plan'})
        elif days<=3:
            output.append({'level':'Upcoming','field_id':task['field_id'],'title':task['title'],
                           'detail':f'Due {due.isoformat()}. Review what you need before starting.','source':'Your activity plan'})
    recent={}
    for obs in observations:
        if obs['field_id'] not in owned_ids:continue
        raw=str(obs['created_at'])[:10]
        try: stamp=date.fromisoformat(raw)
        except (ValueError,TypeError): continue
        if stamp>recent.get(obs['field_id'],date.min):recent[obs['field_id']]=stamp
    for field in fields:
        if field['id'] not in owned_ids:continue
        last=recent.get(field['id'])
        if last is None:
            output.append({'level':'Check-in','field_id':field['id'],'title':'Record your first crop check',
                           'detail':'No crop observations have been saved for this field. Record what you see when convenient.',
                           'source':'Crop monitoring history'})
        elif (today-last).days>=7:
            output.append({'level':'Check-in','field_id':field['id'],'title':'Time for a crop check-in',
                           'detail':f'Your last recorded observation was {last.isoformat()}. Consider inspecting the field and updating its journal.',
                           'source':'Crop monitoring history'})
    order={'Overdue':0,'Upcoming':1,'Weather watch':2,'Check-in':3}
    return sorted(output,key=lambda a:(order.get(a['level'],9),a['field_id'],a['title']))


def forecast_alerts(forecast,field_id):
    """Optional 3-day forecast watch; coarse district references only, never prescriptions."""
    result=[]
    for day in (forecast.get('daily') or [])[:3]:
        chance=day.get('rain_chance')
        rain=day.get('rain_mm')
        if rain is not None and rain>=20 and (chance is None or chance>=60):
            result.append({'level':'Weather watch','field_id':field_id,'title':'Rainfall forecast to review',
                           'detail':f"{day['date']}: approximately {rain:.0f} mm rain is forecast near the district reference point. Check local conditions and planned field activities.",
                           'source':'Open-Meteo district forecast (not measured at your field)'})
    return result
