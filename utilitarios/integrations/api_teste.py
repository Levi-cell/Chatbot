
import requests
from utilitarios.integrations import funil_saj_teste as teste
from core.integrations.funil.cliente import montar_url_envio

url = montar_url_envio(teste.LINK_API_UNIDADE_SAJ, teste.CANAL_META_ADS)

try:
     resposta = requests.post(
         url,
         json=teste.montar_payload_oportunidade_teste(),
         timeout=teste.HTTP_TIMEOUT,
     )
     print("URL:", resposta.url)
     print("HTTP:", resposta.status_code)
     for campo in ("Date", "Content-Type", "Server", "X-Request-ID"):
         if campo in resposta.headers:
             print(f"{campo}: {resposta.headers[campo]}")
     print("\nCONTEUDO DA RESPOSTA:\n")
     print(resposta.text[:16000] or "(resposta vazia)")
except requests.RequestException as erro:
     print("FALHA DE CONEXAO:", erro)