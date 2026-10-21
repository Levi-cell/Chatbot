"""Consulta manual do dashboard da FireAds, sem cadastrar ou alterar leads.

Executar sem argumentos consulta o mesmo número configurado para test_post.py.
Adaptado da consulta original em teste_Dash.py, preservada na raiz do projeto.
"""

import argparse
import json
import re

import requests

if __package__:
    from .config_teste import (
        ABA_DASHBOARD,
        NUMERO_WHATSAPP_TESTE,
        TIMEOUT_CONSULTA,
        URL_DASHBOARD,
    )
else:
    from config_teste import (
        ABA_DASHBOARD,
        NUMERO_WHATSAPP_TESTE,
        TIMEOUT_CONSULTA,
        URL_DASHBOARD,
    )


# Nomes mantidos para facilitar consultas manuais a partir do interpretador.
URL_ACESSO = URL_DASHBOARD
ABA = ABA_DASHBOARD


def limpar_numero(numero):
    return re.sub(r"[^0-9]", "", str(numero or ""))


def normalizar_numero_brasileiro(numero):
    """Normaliza máscaras, prefixo p:+ e formato nacional/internacional."""
    digitos = limpar_numero(numero)
    if len(digitos) in (12, 13) and digitos.startswith("55"):
        nacional = digitos[2:]
    elif len(digitos) in (10, 11):
        nacional = digitos
    else:
        raise ValueError("Telefone brasileiro com quantidade de digitos invalida.")
    if nacional[0] == "0":
        raise ValueError("DDD invalido para a consulta.")
    return f"55{nacional}"


def gerar_formatos_dashboard(numero):
    """Prioriza o número exato e admite a variante móvel antiga como alternativa."""
    exato = normalizar_numero_brasileiro(numero)
    nacional = exato[2:]
    formatos = [exato]
    if len(nacional) == 11 and nacional[2] == "9" and nacional[3] in "6789":
        formatos.append(f"55{nacional[:2]}{nacional[3:]}")
    elif len(nacional) == 10 and nacional[2] in "6789":
        formatos.append(f"55{nacional[:2]}9{nacional[2:]}")
    return formatos


def extrair_registros(resposta_json):
    """Resposta ausente/malformada não pode ser tratada como lista sem leads."""
    if not isinstance(resposta_json, dict):
        raise ValueError("Resposta do dashboard nao e um objeto JSON.")
    if resposta_json.get("success") is False or resposta_json.get("error"):
        raise ValueError("O dashboard informou erro no corpo da resposta.")
    dados = resposta_json.get("data")
    if not isinstance(dados, dict) or not isinstance(dados.get("rows"), list):
        raise ValueError("Contrato inesperado: a resposta nao possui data.rows como lista.")
    registros = dados["rows"]
    if any(not isinstance(lead, dict) or "WhatsApp" not in lead for lead in registros):
        raise ValueError("Contrato inesperado: registro sem o campo WhatsApp.")
    return registros


def localizar_registros(registros, numero_whatsapp):
    """Retorna todos os registros exatos; só depois tenta variante de nono dígito."""
    formatos = gerar_formatos_dashboard(numero_whatsapp)
    por_formato = {formato: [] for formato in formatos}
    for lead in registros:
        try:
            telefone = normalizar_numero_brasileiro(lead["WhatsApp"])
        except ValueError:
            continue
        if telefone in por_formato:
            por_formato[telefone].append(lead)
    for formato in formatos:
        if por_formato[formato]:
            return por_formato[formato]
    return []


def buscar_lead_dashboard(url_acesso, numero_whatsapp):
    formatos = gerar_formatos_dashboard(numero_whatsapp)
    print(f"Consultando numero: {formatos[0]}", flush=True)
    print(f"Aba: {ABA_DASHBOARD}", flush=True)
    resposta = requests.get(
        url_acesso,
        params={"sheet": ABA_DASHBOARD},
        headers={"Accept": "application/json", "User-Agent": "Mozilla/5.0"},
        timeout=TIMEOUT_CONSULTA,
    )
    print(f"HTTP DASHBOARD: {resposta.status_code}", flush=True)
    resposta.raise_for_status()
    registros = extrair_registros(resposta.json())
    encontrados = localizar_registros(registros, numero_whatsapp)
    print(f"Total de registros recebidos: {len(registros)}")
    print(f"Registros encontrados para o numero: {len(encontrados)}")
    for indice, lead in enumerate(encontrados, start=1):
        print(f"\nLEAD ENCONTRADO ({indice}):")
        print(json.dumps(lead, indent=2, ensure_ascii=False, default=str))
    if not encontrados:
        print("\nLEAD NAO LOCALIZADO nos registros retornados nesta consulta.")
        print("Isso nao prova falha do POST: pode haver atraso ou filtro na listagem.")
    return encontrados


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--numero", default=NUMERO_WHATSAPP_TESTE)
    args = parser.parse_args(argv)
    try:
        encontrados = buscar_lead_dashboard(URL_ACESSO, args.numero)
    except (requests.RequestException, ValueError) as erro:
        print(f"\nCONSULTA_FALHOU: {type(erro).__name__}: {erro}")
        print("Nao foi possivel concluir se o lead esta no dashboard.")
        return 1
    return 0 if encontrados else 3


if __name__ == "__main__":
    raise SystemExit(main())
