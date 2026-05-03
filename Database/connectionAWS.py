import psycopg2

setup = {
    "host": "chatbotdb.chi8soygomha.sa-east-1.rds.amazonaws.com",
    "database": "db_chatbot",
    "user": "fushi",
    "password": "fushi998874_",
    "port": "5432"
}


# conn = psycopg2.connect(**setup)
# cursor = conn.cursor()

def get_conn():
    conn = psycopg2.connect(**setup,
                            application_name= "worker_chatbot")
    return conn

## conn.close automaticamente fecha qualquer cursor associado a ela,
# se fizer conn.close n precisa fazer cursor.close