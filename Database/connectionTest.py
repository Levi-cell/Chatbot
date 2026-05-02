from Database.connectionAWS import conn, cursor

def connection_teste_psql():
    cursor.execute("SELECT version();")
    version = cursor.fetchone()

    print("Database version:")
    print("-------------------------")
    print(version[0])

    cursor.close()
    conn.close()


