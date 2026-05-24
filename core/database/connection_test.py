from core.database.connection_aws import get_conn

def connection_teste_psql():

    conn = get_conn()
    cursor = conn.cursor()

    cursor.execute("SELECT version();")
    version = cursor.fetchone()

    print("database version:")
    print("-------------------------")
    print(version[0])

    conn.close()


