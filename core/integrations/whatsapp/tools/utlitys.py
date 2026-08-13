# import requests
#
# from core.integrations.whatsapp.tools.config import (
#     construir_url_graph_api,
#     get_meta_http_timeout,
#     get_token_usuario_meta,
# )
#
# WABA_ID = "1334896588725096"
#
# url = construir_url_graph_api(WABA_ID)
#
# headers = {
#     "Authorization": f"Bearer {get_token_usuario_meta()}",
# }
#
# params = {
#     "fields": (
#         "id,"
#         "name,"
#         "account_review_status,"
#         "business_verification_status"
#     )
# }
#
# response = requests.get(
#     url,
#     headers=headers,
#     params=params,
#     timeout=get_meta_http_timeout(),
# )
#
# print("STATUS HTTP:", response.status_code)
# print(response.json())

import requests

from core.integrations.whatsapp.tools.config import (
    construir_url_graph_api,
    get_meta_http_timeout,
    get_token_usuario_meta,
)

PHONE_NUMBER_ID = "1238343616032627"

url = construir_url_graph_api(PHONE_NUMBER_ID)

headers = {
    "Authorization": f"Bearer {get_token_usuario_meta()}",
}

params = {
    "fields": (
        "id,"
        "display_phone_number,"
        "verified_name,"
        "status,"
        "code_verification_status,"
        "quality_rating"
    )
}

response = requests.get(
    url,
    headers=headers,
    params=params,
    timeout=get_meta_http_timeout(),
)

print("STATUS HTTP:", response.status_code)
print(response.json())