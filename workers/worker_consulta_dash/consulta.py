"""Leitura completa das duas fontes, sem persistência ou envio de mensagens."""

import logging
import time

from core.integrations.fireads.cliente import ClienteFireAds, PrazoConsultaFireAdsEsgotado
from core.integrations.fireads.contrato import ErroFireAds, localizar
from workers.worker_consulta_dash.resultado import decisao_organica, interpretar

logger = logging.getLogger("worker.consulta_dash.http")


def consultar(reserva):
    entrada = reserva["entrada"]
    inicio = time.monotonic()
    cliente = None
    try:
        cliente = ClienteFireAds(entrada["url"], segundos=float(reserva["restante"]),
                                timeout_leitura=None)
        google = cliente.consultar(entrada["aba_google"])
        meta = cliente.consultar(entrada["aba_meta"])
        if not {"Nome", "Email", "WhatsApp", "Perfil/Faixa"} <= set(google["headers"]):
            raise ErroFireAds("Contrato Google incompleto")
        if not {"full_name", "email", "phone_number", "para_quem"} <= set(meta["headers"]):
            raise ErroFireAds("Contrato Meta incompleto")
        numero = entrada["numero"]
        decisao = interpretar(google["rows"], meta["rows"], numero, entrada["fuso"])
        # Não copiar dados de outros clientes. As fontes são confirmadas juntas;
        # erro na segunda fonte descarta também a primeira, sem importação parcial.
        fontes = {
            "google": localizar(google["rows"], numero, "WhatsApp", incluir_equivalentes=True),
            "meta": localizar(meta["rows"], numero, "phone_number", incluir_equivalentes=True),
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
