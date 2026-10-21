"""Prepara somente a abertura, consumindo a consulta persistida pelo outro worker."""

from core.integrations.fireads.extratores import extrair_email
from core.integrations.fireads.aba_geral import configuracao_compativel
from core.repositories.fireads import pendencias
from core.repositories.fireads.consulta import (
    buscar_abertura,
    proteger_mensagem_abertura,
    importar_dados_abertura,
    aplicar_decisao,
)
from core.repositories.atendimento.followup import proteger_conversa
from workers.worker_consulta_dash.resultado import decisao_organica, interpretar
from workers.worker_flow.suporte.consultas_fireads import ConsultaFireAdsPendente


def preparar_abertura(contexto_banco, mensagem, lock_version, cursor):
    from workers.worker_flow.coleta_abertura import preparar, anexar
    cid = contexto_banco['conversa']['id_conversa']
    abertura = buscar_abertura(cid, cursor)
    if 'unidade_ativa' in abertura and abertura['unidade_ativa'] is not True:
        return contexto_banco
    if abertura.get('coleta'):
        if abertura['etapa'] is not None:
            return anexar(contexto_banco, abertura['coleta'], abertura.get('contexto'))
        return preparar(contexto_banco, mensagem, lock_version, cursor, abertura, pendencias.buscar(cid, cursor))
    # Contextos e consultas anteriores ao deploy conservam o contrato original.
    if 'coleta' not in abertura or abertura.get('contexto') or abertura['etapa'] is not None:
        return _preparar_abertura_legada(contexto_banco, mensagem, lock_version, cursor)
    consulta = pendencias.buscar(cid, cursor)
    if consulta is not None:
        return _preparar_abertura_legada(contexto_banco, mensagem, lock_version, cursor)
    return preparar(contexto_banco, mensagem, lock_version, cursor, abertura, None)


def _preparar_abertura_legada(contexto_banco, mensagem, lock_version, cursor):
    """Não executa HTTP nem commit. O orquestrador confirma também a espera."""
    cid = contexto_banco["conversa"]["id_conversa"]
    abertura = buscar_abertura(cid, cursor)
    if abertura["contexto"]:
        return aplicar_contexto(contexto_banco, abertura["contexto"])
    if abertura["etapa"] is not None:
        return contexto_banco  # Nunca reconsultar ou retroceder uma etapa iniciada.
    proteger_conversa(cid, lock_version, cursor)
    proteger_mensagem_abertura(mensagem, cursor)
    consulta_nova = False
    consulta = pendencias.buscar(cid, cursor)
    if consulta is None:
        if not abertura["aplicavel"]:
            return contexto_banco
        consulta_nova = pendencias.solicitar(abertura, cid, mensagem["cliente_telefone"], cursor)
        consulta = pendencias.buscar(cid, cursor)
    motivo = None
    if not abertura["aplicavel"]:
        motivo = "integracao_desativada"
    elif consulta["id_integracao"] != abertura["id_integracao"] or not configuracao_compativel(
        consulta["entrada"], abertura
    ):
        motivo = "configuracao_alterada"
    elif consulta["expirada"] and consulta["status"] != "concluida":
        motivo = "tempo_limite_300s"
    if motivo and consulta["status"] != "concluida":
        pendencias.concluir_sem_http(
            consulta["id_consulta"], decisao_organica("erro", motivo), cursor
        )
        consulta = pendencias.buscar(cid, cursor)
    if consulta["status"] != "concluida":
        raise ConsultaFireAdsPendente("aguardando_resultado", consulta_nova=consulta_nova)
    if consulta["aplicacao"] is not None:
        raise ValueError(
            "Consulta aplicada sem contexto da conversa; verificar integridade"
        )
    # Mudança de integração não autoriza aplicar dados de configuração anterior.
    decisao = (
        decisao_organica("erro", motivo) if motivo else consulta["dados"]["decisao"]
    )
    if decisao["resultado"] == "importado":
        if not importar_dados_abertura(abertura["id_cliente"], cid, decisao, cursor):
            decisao = decisao_organica(
                "incompleto", "conflito_email", referencia=decisao.get("referencia")
            )
    # Conservar a integração originalmente consultada, inclusive se desativada.
    abertura = dict(abertura, id_integracao=consulta["id_integracao"])
    decisao = aplicar_decisao(abertura, cid, consulta["id_consulta"], decisao, cursor)
    pendencias.marcar_aplicada(consulta["id_consulta"], cid, decisao, cursor)
    return aplicar_contexto(contexto_banco, decisao)


def classificar_tratamento_abertura(contexto):
    """A decisão fica no fluxo; messages apenas compõe o texto autorizado."""
    from workers.worker_flow.response_flow.etapas.validadores_universais.validador_midia import (
        validar_midia,
    )
    from workers.worker_flow.response_flow.etapas.validadores_universais.validador_financeiro import (
        validar_pergunta_financeira,
    )
    from workers.worker_flow.response_flow.etapas.validadores_universais.validador_reforco_escolar import (
        validar_duvida_reforco_escolar,
    )

    texto = contexto.get("texto_cliente_atual") or ""
    if validar_midia(contexto.get("tipo_mensagem_atual")):
        return "tipo_mensagem_nao_suportado"
    if validar_duvida_reforco_escolar(texto):
        return "duvida_reforco_escolar"
    if validar_pergunta_financeira(texto):
        return "pergunta_financeira"
    return None


def aplicar_contexto(contexto_banco, decisao):
    novo = dict(contexto_banco, contexto_fireads=decisao)
    if (
        decisao.get("resultado") == "importado"
        and novo["conversa"].get("id_etapa_atual") is None
    ):
        novo["conversa"] = dict(
            novo["conversa"], status_dependente=decisao["status_dependente"]
        )
    return novo


def email_importado(contexto):
    """Confia na coleta FireAds desta conversa, sem revalidar como texto de chat."""
    # Nome histórico da API mantido para replay dos eventos 7/9 -> 11.
    if contexto.get('contexto_coleta'):
        from core.validacoes.coleta_abertura import email_coletado
        return email_coletado(contexto)
    estado = contexto.get("contexto_fireads") or {}
    return (
        estado.get("concluida") is True
        and estado.get("resultado") == "importado"
        and estado.get("id_conversa") == contexto.get("id_conversa")
        and estado.get("dados_titular", {}).get("resultado_email") == "email_valido"
        and bool(extrair_email(estado.get("dados_titular", {}).get("email")))
    )
