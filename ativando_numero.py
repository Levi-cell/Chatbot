import requests

TOKEN_USUARIO_META = "EAATYGW2lhwgBQ4NNpLFVOzkhBCfH7SeWuus3RkF47cq9ldlK7QnU9UHhYZAH9xfWlOnf6p3sbbZAZC179mGXxiS6ZBLRt0EU5bWPrkjLOsjP1mAWVrPR8xadDOnEOWDuyhD0SFhojrOpqcKoo68NzqNdtJMGNqdoKEAZCGP1xdD1EMVn6J2CY86XZCWe30HQZDZD"
PHONE_NUMBER_ID = "954435134428733"

url = f"https://graph.facebook.com/v25.0/{PHONE_NUMBER_ID}/register"

headers = {
    "Authorization": f"Bearer {TOKEN_USUARIO_META}",
    "Content-Type": "application/json"
}

payload = {
    "messaging_product": "whatsapp",
    "pin": "123456"
}

response = requests.post(url, headers=headers, json=payload)

print(response.status_code)
print(response.json())