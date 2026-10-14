"""Sonda manual de canal vazio em SAJ, sem alterar o fluxo de produção."""

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import requests

from core.integrations.funil.cliente import montar_url_envio
from core.integrations.funil.oportunidades import montar_payload_oportunidade
from utilitarios.integrations.funil_saj_teste import (
    HTTP_TIMEOUT,
    LINK_API_UNIDADE_SAJ,
    consultar_integracao_unidade,
)
from utilitarios.montar_lead_teste import montar_dados_lead_teste_saj


def preparar():
    dados = montar_dados_lead_teste_saj()
    payload = montar_payload_oportunidade(dados)
    oportunidade = payload["oportunidades"][0]
    identificador = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    oportunidade["titulo"] = f"TESTE SAJ CANAL VAZIO {identificador} - NAO CONTATAR"
    oportunidade["codigo_canal_venda"] = ""
    # Os demais campos e respostas usam o mesmo contrato da sonda de SAJ.
    for campo in oportunidade["personalizados"]:
        if campo["titulo"] == "Observações":
            campo["valor"] = (
                "TESTE AUTORIZADO: verificar aceite de canal de venda vazio. "
                "Não contatar.\n\n" + campo["valor"]
            )
        elif campo["titulo"] == "Origem do lead":
            campo["valor"] = "Orgânico Site (teste de integração)"
    return payload


def executar(payload, arquivo):
    integracao = consultar_integracao_unidade()
    if not integracao or not integracao["ativa"]:
        raise RuntimeError("Integração de SAJ não localizada ou inativa")
    oportunidade = payload["oportunidades"][0]
    resultado = {
        "titulo": oportunidade["titulo"],
        "unidade": integracao["nome_unidade"],
        "codigo_canal_venda": oportunidade["codigo_canal_venda"],
        "ForceCodeChannel": "",
        "estado": "post_iniciado_nao_repetir_sem_conferir",
        "iniciado_em_utc": datetime.now(timezone.utc).isoformat(),
    }
    # O registro exclusivo evita que reexecutar o comando repita um POST incerto.
    with arquivo.open("x", encoding="utf-8") as destino:
        json.dump(resultado, destino, ensure_ascii=False, indent=2)
    try:
        with requests.Session() as session:
            resposta = session.post(
                montar_url_envio(LINK_API_UNIDADE_SAJ, ""),
                json=payload,
                timeout=HTTP_TIMEOUT,
                allow_redirects=False,
            )
        resultado["status_http"] = resposta.status_code
        try:
            corpo = resposta.json()
        except ValueError:
            corpo = None
        if isinstance(corpo, dict):
            resultado["resposta"] = corpo
        else:
            resultado["resposta_nao_json"] = True
        resultado["aceito"] = (
            200 <= resposta.status_code < 300
            and isinstance(corpo, dict)
            and str(corpo.get("response", "")).casefold() == "success"
        )
        resultado["estado"] = "resposta_recebida"
    except requests.RequestException as erro:
        resultado["estado"] = "resultado_incerto_nao_repetir"
        resultado["erro"] = type(erro).__name__
    resultado["finalizado_em_utc"] = datetime.now(timezone.utc).isoformat()
    arquivo.write_text(
        json.dumps(resultado, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return resultado


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--confirm-real-send", action="store_true")
    parser.add_argument("--resultado", type=Path)
    args = parser.parse_args()
    payload = preparar()
    if not args.confirm_real_send:
        oportunidade = payload["oportunidades"][0]
        print(json.dumps({
            "modo": "sem_envio",
            "titulo": oportunidade["titulo"],
            "codigo_canal_venda": oportunidade["codigo_canal_venda"],
            "ForceCodeChannel": "",
            "demais_marcadores": {
                chave: oportunidade[chave] for chave in (
                    "codigo_vendedor", "codigo_metodologia", "codigo_etapa"
                )
            },
            "quantidade_oportunidades": len(payload["oportunidades"]),
        }, ensure_ascii=False, indent=2))
        return
    if args.resultado is None:
        parser.error("Informe --resultado para registrar o recibo do teste")
    print(json.dumps(executar(payload, args.resultado), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
