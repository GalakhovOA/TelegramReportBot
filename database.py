import sqlite3
from datetime import datetime
import json

DB_FILE = 'reports.db'

def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            role TEXT NOT NULL,  -- 'employee' or 'manager'
            name TEXT,  -- ФИ пользователя
            manager_fi TEXT  -- ФИ руководителя для сотрудников
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            report_date TEXT,
            report_data TEXT
        )
    ''')
    conn.commit()
    conn.close()

def add_user(user_id, role, name=None, manager_fi=None):
    conn = sqlite3.connect(DB_FILE)
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
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('SELECT role FROM users WHERE user_id = ?', (user_id,))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else None

def get_user_name(user_id):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('SELECT name FROM users WHERE user_id = ?', (user_id,))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else None

def set_user_name(user_id, name):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('UPDATE users SET name = ? WHERE user_id = ?', (name, user_id))
    conn.commit()
    conn.close()

def get_manager_fi_for_employee(user_id):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('SELECT manager_fi FROM users WHERE user_id = ?', (user_id,))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else None

def set_manager_fi_for_employee(user_id, manager_fi):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('UPDATE users SET manager_fi = ? WHERE user_id = ?', (manager_fi, user_id))
    conn.commit()
    conn.close()

def get_manager_id_by_fi(manager_fi):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('SELECT user_id FROM users WHERE role = "manager" AND name = ?', (manager_fi,))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else None

def save_report(user_id, report_data):
    date = datetime.now().strftime('%Y-%m-%d')
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('INSERT INTO reports (user_id, report_date, report_data) VALUES (?, ?, ?)',
                  (user_id, date, json.dumps(report_data)))
    conn.commit()
    conn.close()

def get_report(user_id, date):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('SELECT report_data FROM reports WHERE user_id = ? AND report_date = ?', (user_id, date))
    result = cursor.fetchone()
    conn.close()
    return json.loads(result[0]) if result else None

def get_all_reports_on_date(date, manager_fi=None):
    conn = sqlite3.connect(DB_FILE)
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
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    if manager_fi:
        cursor.execute("SELECT user_id, name FROM users WHERE role = 'employee' AND manager_fi = ?", (manager_fi,))
    else:
        cursor.execute("SELECT user_id, name FROM users WHERE role = 'employee'")
    results = cursor.fetchall()
    conn.close()
    return results

init_db()

