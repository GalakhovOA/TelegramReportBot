# database.py
import sqlite3
import os
from datetime import datetime
import json

DB_FILE = os.path.join(os.path.dirname(__file__), 'reports.db')

def get_conn():
    return sqlite3.connect(DB_FILE)

def init_db():
    conn = get_conn()
    cur = conn.cursor()
    # users: role = 'mkk', 'rtp', 'rm'
    cur.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            role TEXT NOT NULL,
            name TEXT,
            manager_fi TEXT
        )
    ''')
    cur.execute('''
        CREATE TABLE IF NOT EXISTS reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            report_date TEXT,
            report_data TEXT
        )
    ''')
    cur.execute('''
        CREATE TABLE IF NOT EXISTS rtp_combined (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            rtp_fi TEXT,
            report_date TEXT,
            report_data TEXT
        )
    ''')
    conn.commit()
    conn.close()

# Users
def add_user(user_id, role, name=None, manager_fi=None):
    conn = get_conn(); cur = conn.cursor()
    cur.execute('INSERT OR REPLACE INTO users (user_id, role, name, manager_fi) VALUES (?, ?, ?, ?)',
                (user_id, role, name, manager_fi))
    conn.commit(); conn.close()

def get_user_role(user_id):
    conn = get_conn(); cur = conn.cursor()
    cur.execute('SELECT role FROM users WHERE user_id=?', (user_id,))
    r = cur.fetchone(); conn.close()
    return r[0] if r else None

def get_user_name(user_id):
    conn = get_conn(); cur = conn.cursor()
    cur.execute('SELECT name FROM users WHERE user_id=?', (user_id,))
    r = cur.fetchone(); conn.close()
    return r[0] if r else None

def set_user_name(user_id, name):
    conn = get_conn(); cur = conn.cursor()
    cur.execute('UPDATE users SET name=? WHERE user_id=?', (name, user_id))
    conn.commit(); conn.close()

def get_manager_fi_for_employee(user_id):
    conn = get_conn(); cur = conn.cursor()
    cur.execute('SELECT manager_fi FROM users WHERE user_id=?', (user_id,))
    r = cur.fetchone(); conn.close()
    return r[0] if r else None

def set_manager_fi_for_employee(user_id, manager_fi):
    conn = get_conn(); cur = conn.cursor()
    cur.execute('UPDATE users SET manager_fi=? WHERE user_id=?', (manager_fi, user_id))
    conn.commit(); conn.close()

def get_manager_id_by_fi(manager_fi):
    conn = get_conn(); cur = conn.cursor()
    cur.execute('SELECT user_id FROM users WHERE role="rtp" AND name=?', (manager_fi,))
    r = cur.fetchone(); conn.close()
    return r[0] if r else None

# Reports (one report per user per date) - upsert
def save_report(user_id, report_data, date=None):
    if date is None:
        date = datetime.now().strftime('%Y-%m-%d')
    conn = get_conn(); cur = conn.cursor()
    cur.execute('SELECT id FROM reports WHERE user_id=? AND report_date=?', (user_id, date))
    r = cur.fetchone()
    if r:
        cur.execute('UPDATE reports SET report_data=? WHERE id=?', (json.dumps(report_data, ensure_ascii=False), r[0]))
    else:
        cur.execute('INSERT INTO reports (user_id, report_date, report_data) VALUES (?, ?, ?)',
                    (user_id, date, json.dumps(report_data, ensure_ascii=False)))
    conn.commit(); conn.close()

def get_report(user_id, date):
    conn = get_conn(); cur = conn.cursor()
    cur.execute('SELECT report_data FROM reports WHERE user_id=? AND report_date=? ORDER BY id DESC LIMIT 1', (user_id, date))
    r = cur.fetchone(); conn.close()
    return json.loads(r[0]) if r else None

def delete_report(user_id, date):
    conn = get_conn(); cur = conn.cursor()
    cur.execute('DELETE FROM reports WHERE user_id=? AND report_date=?', (user_id, date))
    conn.commit(); conn.close()

def get_all_reports_on_date(date, manager_fi=None):
    conn = get_conn(); cur = conn.cursor()
    if manager_fi:
        cur.execute('''
            SELECT r.user_id, r.report_data
            FROM reports r
            JOIN users u ON r.user_id = u.user_id
            WHERE r.report_date = ? AND u.manager_fi = ?
        ''', (date, manager_fi))
    else:
        cur.execute('SELECT user_id, report_data FROM reports WHERE report_date = ?', (date,))
    rows = cur.fetchall(); conn.close()
    return [(uid, json.loads(data)) for uid, data in rows]

def get_employees(manager_fi=None):
    conn = get_conn(); cur = conn.cursor()
    if manager_fi:
        cur.execute("SELECT user_id, name FROM users WHERE role='mkk' AND manager_fi=?", (manager_fi,))
    else:
        cur.execute("SELECT user_id, name FROM users WHERE role='mkk'")
    rows = cur.fetchall(); conn.close()
    return rows

# RPT combined reports table
def save_rtp_combined(rtp_fi, report_data, date=None):
    if date is None:
        date = datetime.now().strftime('%Y-%m-%d')
    conn = get_conn(); cur = conn.cursor()
    cur.execute('SELECT id FROM rtp_combined WHERE rtp_fi=? AND report_date=?', (rtp_fi, date))
    r = cur.fetchone()
    if r:
        cur.execute('UPDATE rtp_combined SET report_data=? WHERE id=?', (json.dumps(report_data, ensure_ascii=False), r[0]))
    else:
        cur.execute('INSERT INTO rtp_combined (rtp_fi, report_date, report_data) VALUES (?, ?, ?)',
                    (rtp_fi, date, json.dumps(report_data, ensure_ascii=False)))
    conn.commit(); conn.close()

def get_rtp_combined(rtp_fi, date):
    conn = get_conn(); cur = conn.cursor()
    cur.execute('SELECT report_data FROM rtp_combined WHERE rtp_fi=? AND report_date=? ORDER BY id DESC LIMIT 1', (rtp_fi, date))
    r = cur.fetchone(); conn.close()
    return json.loads(r[0]) if r else None

def get_all_rtp_combined_on_date(date):
    conn = get_conn(); cur = conn.cursor()
    cur.execute('SELECT rtp_fi, report_data FROM rtp_combined WHERE report_date=?', (date,))
    rows = cur.fetchall(); conn.close()
    return [(fi, json.loads(data)) for fi, data in rows]

def get_rtp_combined_status_for_all(rtps, date):
    sent = {fi: False for fi in rtps}
    rows = get_all_rtp_combined_on_date(date)
    for fi, _ in rows:
        if fi in sent:
            sent[fi] = True
    return sent

def get_all_rtps_from_config_list(rtp_list):
    conn = get_conn(); cur = conn.cursor()
    out = []
    for fi in rtp_list:
        cur.execute('SELECT user_id FROM users WHERE role="rtp" AND name=?', (fi,))
        r = cur.fetchone()
        out.append((fi, r[0] if r else None))
    conn.close()
    return out

# init
init_db()
