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
            role TEXT NOT NULL  -- 'employee' or 'manager'
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            report_date TEXT,
            report_data TEXT  -- JSON
        )
    ''')
    conn.commit()
    conn.close()

def add_user(user_id, role):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('INSERT OR REPLACE INTO users (user_id, role) VALUES (?, ?)', (user_id, role))
    conn.commit()
    conn.close()

def get_user_role(user_id):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('SELECT role FROM users WHERE user_id = ?', (user_id,))
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

def get_all_reports_on_date(date):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('SELECT user_id, report_data FROM reports WHERE report_date = ?', (date,))
    results = cursor.fetchall()
    conn.close()
    return [(uid, json.loads(data)) for uid, data in results]

def get_employees():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM users WHERE role = 'employee'")
    results = cursor.fetchall()
    conn.close()
    return [uid[0] for uid in results]

# Инициализируем БД при запуске
init_db()