"""Envia um único lead de teste ao webhook e mostra o resultado HTTP.

Executar sem argumentos faz um POST real. --payload apenas exibe os dados.
O formato JSON é experimental: o contrato de campos ainda não foi informado.
Importar este módulo não envia nada; não há retry automático do POST.
"""

import argparse
import json
from time import monotonic
from uuid import uuid4

import requests

if __package__:
    from .config_teste import (
        EMAIL_LEAD_TESTE,
        NOME_LEAD_TESTE,
        NUMERO_WHATSAPP_TESTE,
        TIMEOUT_POST,
        URL_WEBHOOK,
    )
else:
    # Permite executar diretamente pelo botão Run do PyCharm.
    from config_teste import (
        EMAIL_LEAD_TESTE,
        NOME_LEAD_TESTE,
        NUMERO_WHATSAPP_TESTE,
        TIMEOUT_POST,
        URL_WEBHOOK,
    )


def montar_payload_teste():
    """Dados fictícios de cadastro; telefone de teste fornecido pelo responsável."""
    return {
        "nome": NOME_LEAD_TESTE,
        "telefone": NUMERO_WHATSAPP_TESTE,
        "email": EMAIL_LEAD_TESTE,
        "origem": "organico",
        "unidade": "Santo Andre - Jardim Bela Vista",
        "teste": True,
        "id_teste": f"esl-fireads-{uuid4().hex}",
        "observacao": (
            "Teste tecnico de integracao autorizado pela ESL Tech. "
            "Desconsiderar como oportunidade comercial real."
        ),
    }


def enviar_lead_teste(payload):
    """Faz uma tentativa; retorna a resposta inclusive quando o HTTP é de erro."""
    return requests.post(
        URL_WEBHOOK,
        json=payload,
        headers={"Accept": "application/json"},
        timeout=TIMEOUT_POST,
        # Expor redirecionamento, sem ocultar o status original ou repetir o POST.
        allow_redirects=False,
    )


def imprimir_resposta(resposta, duracao):
    """Mostra diagnóstico antes de qualquer interpretação de sucesso comercial."""
    print(f"\nURL: {resposta.url}")
    print(f"HTTP: {resposta.status_code} {resposta.reason}")
    print(f"Duracao: {duracao:.2f}s")
    for campo in ("Date", "Content-Type", "Server", "X-Request-ID", "Location"):
        if campo in resposta.headers:
            print(f"{campo}: {resposta.headers[campo]}")

    print("\nCONTEUDO DA RESPOSTA:")
    conteudo = resposta.text
    print(conteudo[:16000] or "(resposta vazia)")
    if len(conteudo) > 16000:
        print("(conteudo truncado em 16000 caracteres)")

    if 200 <= resposta.status_code < 300:
        print(
            "\nO webhook respondeu com sucesso HTTP. "
            "Isso ainda nao confirma gravacao no dashboard."
        )
        print("Execute test_Dash.py para consultar o mesmo telefone.")
    else:
        print("\nO POST nao recebeu HTTP de sucesso. Nao houve reenvio automatico.")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--payload", action="store_true", help="Mostra o JSON sem executar o POST."
    )
    args = parser.parse_args(argv)
    payload = montar_payload_teste()
    print("PAYLOAD EXPERIMENTAL DE TESTE:", flush=True)
    print(json.dumps(payload, ensure_ascii=False, indent=2), flush=True)
    if args.payload:
        return 0

    print("\nEnviando uma unica requisicao POST...", flush=True)
    inicio = monotonic()
    try:
        resposta = enviar_lead_teste(payload)
    except requests.RequestException as erro:
        print(f"\nHTTP: indisponivel ({type(erro).__name__})")
        print(f"FALHA DE CONEXAO: {erro}")
        print(
            "Sem resposta HTTP, a gravacao pode ter ocorrido. "
            "Consulte o dashboard antes de repetir o POST."
        )
        return 2

    imprimir_resposta(resposta, monotonic() - inicio)
    return 0 if 200 <= resposta.status_code < 300 else 1


if __name__ == "__main__":
    raise SystemExit(main())
