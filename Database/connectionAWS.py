import psycopg2

setup = {
    "host": "chatbotdb.chi8soygomha.sa-east-1.rds.amazonaws.com",
    "database": "db_chatbot",
    "user": "fushi",
    "password": "fushi998874_",
    "port": "5432"
}


conn = psycopg2.connect(**setup)
cursor = conn.cursor()
