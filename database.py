# database.py
import sqlite3
from datetime import datetime
import json
import os

DB_FILE = 'reports.db'

def get_conn():
    conn = sqlite3.connect(DB_FILE)
    return conn

def init_db():
    # ensure DB dir exists if using path
    conn = get_conn()
    cursor = conn.cursor()
    # users table with is_verified
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            role TEXT NOT NULL,
            name TEXT,
            manager_fi TEXT,
            is_verified INTEGER DEFAULT 0
        )
    ''')
    # reports table; unique per user+date so save_report can replace
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            report_date TEXT,
            report_data TEXT,
            UNIQUE(user_id, report_date)
        )
    ''')
    # table for combined reports that РТП сохраняет (one per rtp+date)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS rtp_combined (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            rtp_name TEXT,
            report_date TEXT,
            combined_data TEXT,
            UNIQUE(rtp_name, report_date)
        )
    ''')
    conn.commit()

    # ensure is_verified column exists (for compatibility with older DB)
    cursor.execute("PRAGMA table_info(users)")
    cols = [row[1] for row in cursor.fetchall()]
    if 'is_verified' not in cols:
        try:
            cursor.execute("ALTER TABLE users ADD COLUMN is_verified INTEGER DEFAULT 0")
            conn.commit()
        except Exception:
            # if alter fails for some reason, ignore (older sqlite etc.)
            pass

    conn.close()

def add_user(user_id, role, name=None, manager_fi=None):
    conn = get_conn()
    cursor = conn.cursor()
    if name and manager_fi:
        cursor.execute('INSERT OR REPLACE INTO users (user_id, role, name, manager_fi) VALUES (?, ?, ?, ?)',
                      (user_id, role, name, manager_fi))
    elif name:
        cursor.execute('INSERT OR REPLACE INTO users (user_id, role, name) VALUES (?, ?, ?)',
                      (user_id, role, name))
    else:
        cursor.execute('INSERT OR REPLACE INTO users (user_id, role) VALUES (?, ?)',
                      (user_id, role))
    conn.commit()
    conn.close()

def get_user_role(user_id):
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute('SELECT role FROM users WHERE user_id = ?', (user_id,))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else None

def get_user_name(user_id):
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute('SELECT name FROM users WHERE user_id = ?', (user_id,))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else None

def set_user_name(user_id, name):
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute('UPDATE users SET name = ? WHERE user_id = ?', (name, user_id))
    conn.commit()
    conn.close()

def get_manager_fi_for_employee(user_id):
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute('SELECT manager_fi FROM users WHERE user_id = ?', (user_id,))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else None

def set_manager_fi_for_employee(user_id, manager_fi):
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute('UPDATE users SET manager_fi = ? WHERE user_id = ?', (manager_fi, user_id))
    conn.commit()
    conn.close()

def get_manager_id_by_fi(manager_fi):
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute('SELECT user_id FROM users WHERE role = "rtp" AND name = ?', (manager_fi,))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else None

def save_report(user_id, report_data):
    # save or replace report for today (unique constraint ensures single report per user/date)
    date = datetime.now().strftime('%Y-%m-%d')
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute('INSERT OR REPLACE INTO reports (user_id, report_date, report_data) VALUES (?, ?, ?)',
                  (user_id, date, json.dumps(report_data, ensure_ascii=False)))
    conn.commit()
    conn.close()

def get_report(user_id, date):
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute('SELECT report_data FROM reports WHERE user_id = ? AND report_date = ?', (user_id, date))
    result = cursor.fetchone()
    conn.close()
    return json.loads(result[0]) if result else None

def get_all_reports_on_date(date, manager_fi=None):
    conn = get_conn()
    cursor = conn.cursor()
    if manager_fi:
        cursor.execute('''
            SELECT r.user_id, r.report_data
            FROM reports r
            JOIN users u ON r.user_id = u.user_id
            WHERE r.report_date = ? AND u.manager_fi = ?
        ''', (date, manager_fi))
    else:
        cursor.execute('SELECT user_id, report_data FROM reports WHERE report_date = ?', (date,))
    results = cursor.fetchall()
    conn.close()
    return [(uid, json.loads(data)) for uid, data in results]

def get_employees(manager_fi=None):
    conn = get_conn()
    cursor = conn.cursor()
    if manager_fi:
        cursor.execute("SELECT user_id, name FROM users WHERE role = 'mkk' AND manager_fi = ?", (manager_fi,))
    else:
        cursor.execute("SELECT user_id, name FROM users WHERE role = 'mkk'")
    results = cursor.fetchall()
    conn.close()
    return results

# -------------------------
# Combined RТП reports
# -------------------------
def save_rtp_combined(rtp_name, combined_data, date):
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute('INSERT OR REPLACE INTO rtp_combined (rtp_name, report_date, combined_data) VALUES (?, ?, ?)',
                   (rtp_name, date, json.dumps(combined_data, ensure_ascii=False)))
    conn.commit()
    conn.close()

def get_rtp_combined(rtp_name, date):
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute('SELECT combined_data FROM rtp_combined WHERE rtp_name = ? AND report_date = ?', (rtp_name, date))
    row = cursor.fetchone()
    conn.close()
    return json.loads(row[0]) if row else None

def get_all_rtp_combined_on_date(date):
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute('SELECT rtp_name, combined_data FROM rtp_combined WHERE report_date = ?', (date,))
    rows = cursor.fetchall()
    conn.close()
    return [(r[0], json.loads(r[1])) for r in rows]

def get_rtp_combined_status_for_all(rtp_list, date):
    # returns dict {rtp_name: True/False}
    conn = get_conn()
    cursor = conn.cursor()
    result = {}
    for r in rtp_list:
        cursor.execute('SELECT 1 FROM rtp_combined WHERE rtp_name = ? AND report_date = ?', (r, date))
        row = cursor.fetchone()
        result[r] = bool(row)
    conn.close()
    return result

# -------------------------
# Authorization (password remembered)
# -------------------------
def set_user_verified(user_id, val=1):
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute('UPDATE users SET is_verified = ? WHERE user_id = ?', (1 if val else 0, user_id))
    conn.commit()
    conn.close()

def is_user_verified(user_id):
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute('SELECT is_verified FROM users WHERE user_id = ?', (user_id,))
    row = cursor.fetchone()
    conn.close()
    return bool(row[0]) if row else False

# helper: find user by name
def get_user_by_name(name):
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("SELECT user_id, role, name, manager_fi FROM users WHERE name = ?", (name,))
    row = cursor.fetchone()
    conn.close()
    if not row:
        return None
    return {"user_id": row[0], "role": row[1], "name": row[2], "manager_fi": row[3]}

# initialize DB on import
init_db()
