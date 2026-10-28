"""Opt-in, private crop photograph snapshots; EXIF is removed on ingestion.

Photo bytes are stored in a separate SQLite table and never included in
analytics or LLM requests unless the farmer explicitly chooses analysis.
"""
import io
from .accounts import connect, DB_PATH

MAX_UPLOAD_BYTES = 4 * 1024 * 1024


def init_photos(path=DB_PATH):
    with connect(path) as db:
        db.executescript('''CREATE TABLE IF NOT EXISTS crop_photo_snapshots (
          observation_id INTEGER PRIMARY KEY REFERENCES crop_observations(id) ON DELETE CASCADE,
          farmer_id INTEGER NOT NULL REFERENCES farmers(id) ON DELETE CASCADE,
          field_id INTEGER NOT NULL REFERENCES fields(id) ON DELETE CASCADE,
          image_jpeg BLOB NOT NULL,
          created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
          CREATE INDEX IF NOT EXISTS idx_snapshots_farmer ON crop_photo_snapshots(farmer_id,field_id);''')


def _sanitize(raw):
    if not raw or len(raw)>MAX_UPLOAD_BYTES:raise ValueError('JPEG/PNG crop photo must be under 4 MB.')
    try:
        from PIL import Image, ImageOps, UnidentifiedImageError
        Image.MAX_IMAGE_PIXELS=15_000_000
        with Image.open(io.BytesIO(raw)) as photo:
            if photo.format not in ('JPEG','PNG'):
                raise ValueError('Only JPEG and PNG photographs are supported.')
            photo.load()
            im=ImageOps.exif_transpose(photo).convert('RGB')
            im.thumbnail((1400,1400))
            out=io.BytesIO()
            im.save(out,format='JPEG',quality=78,optimize=True)
            data=out.getvalue()
            if len(data)>MAX_UPLOAD_BYTES:raise ValueError('Photo is too large to store.')
            return data
    except (OSError,ValueError) as exc:
        raise ValueError(f'Could not read the image: {str(exc)[:120]}') from exc


def save_photo(farmer_id,field_id,observation_id,image_bytes,path=DB_PATH):
    data=_sanitize(image_bytes)
    with connect(path) as db:
        allowed=db.execute('''SELECT 1 FROM crop_observations o
          JOIN fields f ON f.id=o.field_id AND f.farmer_id=o.farmer_id
          WHERE o.id=? AND o.field_id=? AND o.farmer_id=?''',(observation_id,field_id,farmer_id)).fetchone()
        if not allowed:raise PermissionError('This observation is not yours.')
        db.execute('''INSERT INTO crop_photo_snapshots(observation_id,farmer_id,field_id,image_jpeg)
          VALUES(?,?,?,?) ON CONFLICT(observation_id) DO UPDATE SET image_jpeg=excluded.image_jpeg''',
          (observation_id,farmer_id,field_id,data))


def list_photos(farmer_id,field_id=None,path=DB_PATH):
    with connect(path) as db:
        q='''SELECT p.observation_id,p.field_id,p.created_at,o.stage,o.symptom,o.notes
          FROM crop_photo_snapshots p JOIN crop_observations o ON o.id=p.observation_id AND o.farmer_id=p.farmer_id
          JOIN fields f ON f.id=p.field_id AND f.farmer_id=p.farmer_id WHERE p.farmer_id=?'''
        params=[farmer_id]
        if field_id is not None:q+=' AND p.field_id=?';params.append(field_id)
        return [dict(r) for r in db.execute(q+' ORDER BY p.observation_id DESC',params)]


def _allowed_advisor(db,advisor_id,field_id,farmer_id):
    return db.execute('''SELECT 1 FROM farmer_assignments x
       JOIN advisor_permissions p ON p.farmer_id=x.farmer_id AND p.allow_assignment=1
       JOIN fields f ON f.farmer_id=x.farmer_id
       WHERE x.agronomist_id=? AND x.active=1 AND f.id=? AND f.farmer_id=?''',
       (advisor_id,field_id,farmer_id)).fetchone() is not None


def photo(role,actor_id,observation_id,path=DB_PATH):
    with connect(path) as db:
        row=db.execute('''SELECT p.* FROM crop_photo_snapshots p JOIN fields f
             ON f.id=p.field_id AND f.farmer_id=p.farmer_id WHERE p.observation_id=?''',(observation_id,)).fetchone()
        if row is None:return None
        if role=='farmer' and row['farmer_id']==actor_id:return bytes(row['image_jpeg'])
        if role=='agronomist' and _allowed_advisor(db,actor_id,row['field_id'],row['farmer_id']):return bytes(row['image_jpeg'])
        raise PermissionError('Photo not accessible to this account.')


def delete_photo(farmer_id,observation_id,path=DB_PATH):
    with connect(path) as db:
        return db.execute('DELETE FROM crop_photo_snapshots WHERE observation_id=? AND farmer_id=?',(observation_id,farmer_id)).rowcount>0
