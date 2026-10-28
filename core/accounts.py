"""Local demo farmer accounts. No survey identities are imported into this database."""
import hashlib
import hmac
import os
import re
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / 'storage' / 'farmers.sqlite3'
ITERATIONS = 600_000


def normalize_phone(phone):
    digits = re.sub(r'[^\d+]', '', phone.strip())
    if digits.startswith('00'):
        digits = '+' + digits[2:]
    if digits.startswith('0') and len(digits) == 10:
        digits = '+250' + digits[1:]
    elif digits.startswith('250') and len(digits) == 12:
        digits = '+' + digits
    if not re.fullmatch(r'\+2507\d{8}', digits):
        raise ValueError('Enter a Rwandan mobile number, e.g. 0788 123 456.')
    return digits


@contextmanager
def connect(path=DB_PATH):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA foreign_keys=ON')
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db(path=DB_PATH):
    with connect(path) as conn:
        conn.execute('''CREATE TABLE IF NOT EXISTS farmers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            full_name TEXT NOT NULL,
            phone TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            failed_attempts INTEGER NOT NULL DEFAULT 0,
            locked_until INTEGER NOT NULL DEFAULT 0
        )''')


def hash_password(password):
    salt = os.urandom(16)
    key = hashlib.pbkdf2_hmac('sha256', password.encode(), salt, ITERATIONS)
    return f'pbkdf2_sha256${ITERATIONS}${salt.hex()}${key.hex()}'


def verify_password(password, encoded):
    try:
        scheme, rounds, salt_hex, key_hex = encoded.split('$')
        if scheme != 'pbkdf2_sha256':
            return False
        actual = hashlib.pbkdf2_hmac('sha256', password.encode(), bytes.fromhex(salt_hex), int(rounds))
        return hmac.compare_digest(actual, bytes.fromhex(key_hex))
    except (ValueError, TypeError):
        return False


def register(full_name, phone, password, path=DB_PATH):
    name = ' '.join(full_name.split())
    if not (2 <= len(name) <= 100):
        raise ValueError('Enter your full name (2–100 characters).')
    phone = normalize_phone(phone)
    if len(password) < 8 or len(password) > 128:
        raise ValueError('Choose a password of 8–128 characters. For security, a 4-digit PIN alone is not supported.')
    with connect(path) as conn:
        try:
            cur = conn.execute('INSERT INTO farmers(full_name, phone, password_hash) VALUES (?,?,?)',
                               (name, phone, hash_password(password)))
            return {'id': cur.lastrowid, 'full_name': name, 'phone': phone}
        except sqlite3.IntegrityError as exc:
            raise ValueError('That phone number already has an account. Please log in.') from exc


def login(phone, password, path=DB_PATH):
    try:
        phone = normalize_phone(phone)
    except ValueError:
        return None, 'Incorrect phone number or password.'
    now = int(time.time())
    with connect(path) as conn:
        row = conn.execute('SELECT * FROM farmers WHERE phone=?', (phone,)).fetchone()
        if row is None:
            # Avoid clear fast path for unknown accounts.
            verify_password(password, _DUMMY_HASH)
            return None, 'Incorrect phone number or password.'
        if row['locked_until'] > now:
            return None, 'Too many failed attempts. Try again after 15 minutes.'
        if not verify_password(password, row['password_hash']):
            failures = row['failed_attempts'] + 1
            locked = now + 900 if failures >= 5 else 0
            conn.execute('UPDATE farmers SET failed_attempts=?, locked_until=? WHERE id=?',
                         (failures if not locked else 0, locked, row['id']))
            return None, 'Incorrect phone number or password.' if not locked else 'Too many failed attempts. Try again after 15 minutes.'
        conn.execute('UPDATE farmers SET failed_attempts=0, locked_until=0 WHERE id=?', (row['id'],))
        return {'id': row['id'], 'full_name': row['full_name'], 'phone': row['phone']}, None


def get_farmer(farmer_id, path=DB_PATH):
    with connect(path) as conn:
        row = conn.execute('SELECT id,full_name,phone,created_at FROM farmers WHERE id=?', (farmer_id,)).fetchone()
        return dict(row) if row else None


# Static dummy hash for unknown-user timing (no real credentials).
_DUMMY_HASH = 'pbkdf2_sha256$600000$00112233445566778899aabbccddeeff$' + hashlib.pbkdf2_hmac(
    'sha256', b'dummy_password_never_used', bytes.fromhex('00112233445566778899aabbccddeeff'), ITERATIONS
).hex()
