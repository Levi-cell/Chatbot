"""Leitura da aba geral, sem persistência ou envio de mensagens."""

import logging
import time

from core.integrations.fireads.cliente import ClienteFireAds, PrazoConsultaFireAdsEsgotado
from core.integrations.fireads.contrato import ErroFireAds, localizar
from core.integrations.fireads.aba_geral import VERSAO_CONSULTA
from core.integrations.fireads.coleta_abertura import interpretar_parcial
from workers.worker_consulta_dash.resultado import decisao_organica, interpretar

logger = logging.getLogger("worker.consulta_dash.http")


def consultar(reserva):
    entrada = reserva["entrada"]
    inicio = time.monotonic()
    cliente = None
    try:
        cliente = ClienteFireAds(entrada["url"], segundos=float(reserva["restante"]),
                                timeout_leitura=None)
        if entrada.get("versao") != VERSAO_CONSULTA:
            raise ErroFireAds("Versão de consulta desconhecida")
        geral = cliente.consultar(entrada["aba"])
        if not {"Nome", "Email", "WhatsApp", "Para quem é", "Canal", "Data/Hora"} <= set(geral["headers"]):
            return {"decisao": decisao_organica("erro", "cabecalhos_ausentes"), "fontes": {}}
        numero = entrada["numero"]
        if entrada.get("coleta") is not None:
            if entrada['coleta'].get('versao') != 1:
                raise ErroFireAds('Versão de coleta desconhecida')
            decisao = interpretar_parcial(geral['rows'], numero, entrada['fuso'], entrada['aba'], entrada['coleta'])
        else:
            decisao = interpretar(geral["rows"], numero, entrada["fuso"], aba=entrada["aba"])
        # O banco recebe apenas os registros deste contato e a decisão completa.
        fontes = {
            "geral": localizar(geral["rows"], numero, "WhatsApp", incluir_equivalentes=True),
        }
        if time.monotonic()-inicio >= float(reserva["restante"]):
            raise PrazoConsultaFireAdsEsgotado("Leitura concluída após o prazo")
        return {"decisao": decisao, "fontes": fontes}
    except PrazoConsultaFireAdsEsgotado:
        return {"decisao": decisao_organica("erro", "tempo_limite_300s"), "fontes": {}}
    except Exception as erro:
        # O corpo da API pode conter dados pessoais; guardar/logar só a classe.
        logger.warning("consulta_dash_http_falhou | consulta=%s tipo=%s",
                       reserva["id_consulta"], type(erro).__name__)
        return {"decisao": decisao_organica("erro", type(erro).__name__), "fontes": {}}
    finally:
        if cliente is not None:
            cliente.close()
