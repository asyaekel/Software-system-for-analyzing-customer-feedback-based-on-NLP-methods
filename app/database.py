import sqlite3
import pandas as pd
import hashlib

DB_NAME = "reviews_analytics_v4.db"

def init_db():
    """Створює таблиці бази даних, якщо їх ще немає."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # Таблиця користувачів
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL
        )
    ''')
    
    # Таблиця для збереження результатів аналізу
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS analyzed_reviews (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            file_name TEXT NOT NULL,
            quality REAL,
            delivery REAL,
            support REAL,
            price REAL,
            ui_ux REAL,
            packaging REAL,
            assortment REAL,
            returns REAL,
            loyalty REAL,
            recommendation REAL,
            overall_satisfaction REAL,
            analyzed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
    ''')
    
    conn.commit()
    conn.close()

def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

def register_user(username, password) -> bool:
    """Реєструє нового користувача. Повертає True, якщо успішно."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    try:
        cursor.execute('INSERT INTO users (username, password_hash) VALUES (?, ?)', (username, hash_password(password)))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False # Користувач вже існує
    finally:
        conn.close()

def verify_user(username, password):
    """Перевіряє логін і пароль. Повертає user_id або None."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('SELECT id FROM users WHERE username = ? AND password_hash = ?', (username, hash_password(password)))
    user = cursor.fetchone()
    conn.close()
    return user[0] if user else None

def save_analysis_result(user_id: int, file_name: str, result_dict: dict):
    """Зберігає один проаналізований відгук у базу."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    cursor.execute('''
        INSERT INTO analyzed_reviews (
            user_id, file_name, quality, delivery, support, price, ui_ux, 
            packaging, assortment, returns, loyalty, recommendation, overall_satisfaction
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        user_id,
        file_name,
        result_dict.get('якість товару'),
        result_dict.get('швидкість доставки'),
        result_dict.get('робота служби підтримки'),
        result_dict.get('ціна'),
        result_dict.get('зручність використання сайту'),
        result_dict.get('пакування'),
        result_dict.get('асортимент та наявність'),
        result_dict.get('процес повернення та гарантія'),
        result_dict.get('програма лояльності та знижки'),
        result_dict.get('бажання рекомендувати'),
        result_dict.get('загальне задоволення від покупки')
    ))
    
    conn.commit()
    conn.close()

def get_user_data_as_dataframe(user_id: int) -> pd.DataFrame:
    """Вивантажує всі дані з бази у форматі Pandas DataFrame для аналітики."""
    conn = sqlite3.connect(DB_NAME)
    df = pd.read_sql_query("SELECT * FROM analyzed_reviews WHERE user_id = ?", conn, params=(user_id,))
    conn.close()
    return df

def delete_file_data(user_id: int, file_name: str):
    """Видаляє всі проаналізовані відгуки для конкретного файлу користувача."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM analyzed_reviews WHERE user_id = ? AND file_name = ?", (user_id, file_name))
    conn.commit()
    conn.close()

# Ініціалізуємо базу при імпорті модуля
init_db()
