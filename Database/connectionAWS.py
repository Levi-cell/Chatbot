# import psycopg2
# import time
#
# setup = {
#     "host": "chatbotdb.chi8soygomha.sa-east-1.rds.amazonaws.com",
#     "database": "db_chatbot",
#     "user": "fushi",
#     "password": "fushi998874_",
#     "port": "5432",
#     "connect_timeout": 5  # 🔥 importante
# }
#
# _conn = None
#
#
# def get_conn():
#     global _conn
#
#     if _conn is not None and _conn.closed == 0:
#         return _conn
#
#     print("🔌 Conectando ao banco...")
#
#     for tentativa in range(3):  # 🔥 retry
#         try:
#             _conn = psycopg2.connect(**setup)
#             return _conn
#
#         except psycopg2.OperationalError as e:
#             print(f"❌ Tentativa {tentativa+1} falhou: {e}")
#             time.sleep(2)
#
#     raise Exception("🚨 Não foi possível conectar ao banco após 3 tentativas")
#
#

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