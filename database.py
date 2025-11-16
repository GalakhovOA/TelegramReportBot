# database.py
import sqlite3
from datetime import datetime
import json
import os

DB_FILE = os.path.join(os.path.dirname(__file__), 'reports.db')

def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            role TEXT NOT NULL,
            name TEXT,
            manager_fi TEXT
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
    cursor.execute('INSERT OR REPLACE INTO users (user_id, role, name, manager_fi) VALUES (?, ?, ?, ?)',
                   (user_id, role, name, manager_fi))
    conn.commit()
    conn.close()

def get_user_role(user_id):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('SELECT role FROM users WHERE user_id = ?', (user_id,))
    r = cursor.fetchone()
    conn.close()
    return r[0] if r else None

def get_user_name(user_id):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('SELECT name FROM users WHERE user_id = ?', (user_id,))
    r = cursor.fetchone()
    conn.close()
    return r[0] if r else None

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
    r = cursor.fetchone()
    conn.close()
    return r[0] if r else None

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
    r = cursor.fetchone()
    conn.close()
    return r[0] if r else None

def save_report(user_id, report_data, date=None):
    """
    Сохраняет новый отчёт (INSERT). Если нужно перезаписать — вызовите delete + save или добавьте апдейт.
    report_data ожидается как JSON-serializable dict.
    """
    if date is None:
        date = datetime.now().strftime('%Y-%m-%d')
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('INSERT INTO reports (user_id, report_date, report_data) VALUES (?, ?, ?)',
                   (user_id, date, json.dumps(report_data, ensure_ascii=False)))
    conn.commit()
    conn.close()

def get_report(user_id, date):
    """
    Возвращает последний отчёт пользователя за date (или None).
    """
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('SELECT report_data FROM reports WHERE user_id = ? AND report_date = ? ORDER BY id DESC LIMIT 1',
                   (user_id, date))
    r = cursor.fetchone()
    conn.close()
    return json.loads(r[0]) if r else None

def get_all_reports_on_date(date, manager_fi=None):
    """
    Возвращает список (user_id, report_data_dict) за date.
    Если manager_fi задан — только для сотрудников с manager_fi.
    """
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
    rows = cursor.fetchall()
    conn.close()
    return [(uid, json.loads(data)) for uid, data in rows]

def get_employees(manager_fi=None):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    if manager_fi:
        cursor.execute("SELECT user_id, name FROM users WHERE role = 'employee' AND manager_fi = ?", (manager_fi,))
    else:
        cursor.execute("SELECT user_id, name FROM users WHERE role = 'employee'")
    rows = cursor.fetchall()
    conn.close()
    return rows

# инициализация при импорте
init_db()
