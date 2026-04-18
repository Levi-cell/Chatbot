from Database.connectionAWS import conn, cursor

cursor.execute("SELECT version();")
version = cursor.fetchone()

print("Database version:")
print("-------------------------")
print(version[0])

cursor.close()
conn.close()

print("hi")
