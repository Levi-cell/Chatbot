from Database.connectionAWS import get_conn

def fetch_one(sql, params=None):
    conn = get_conn()
    try:
        with conn.cursor() as cursor:
            cursor.execute(sql, params or ())
            return cursor.fetchone()
    except Exception:
        raise


def fetch_all(sql, params=None):
    conn = get_conn()
    try:
        with conn.cursor() as cursor:
            cursor.execute(sql, params or ())
            return cursor.fetchall()
    except Exception:
        raise

def execute(sql, params=None):
    conn = get_conn()
    try:
        with conn.cursor() as cursor:
            cursor.execute(sql, params or ())
        conn.commit()
    except Exception:
        conn.rollback()
        raise