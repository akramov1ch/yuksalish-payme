import sqlite3
import logging

logger = logging.getLogger(__name__)
DB_NAME = '/app/database_files/admins.db'

def init_db():
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS admins (
                user_id INTEGER PRIMARY KEY
            )
        ''')
        conn.commit()
        conn.close()
        logger.info("Ma'lumotlar bazasi muvaffaqiyatli ishga tushirildi.")
    except Exception as e:
        logger.error(f"Ma'lumotlar bazasini ishga tushirishda xatolik: {e}")


def add_admin(user_id: int):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO admins (user_id) VALUES (?)", (user_id,))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()

def remove_admin(user_id: int):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM admins WHERE user_id = ?", (user_id,))
    affected_rows = cursor.rowcount
    conn.commit()
    conn.close()
    return affected_rows > 0

def get_all_admins() -> list[int]:
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("SELECT user_id FROM admins")
        admins = [row[0] for row in cursor.fetchall()]
        conn.close()
        return admins
    except Exception as e:
        logger.error(f"Adminlarni olishda xatolik: {e}")
        return []


def is_admin(user_id: int) -> bool:
    return user_id in get_all_admins()