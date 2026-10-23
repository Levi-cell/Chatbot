"""Interpretação da consulta inicial; não executa HTTP nem operações de banco."""

from core.integrations.fireads.contrato import ABA_DESTINO, destino, normalizar
from core.integrations.fireads.aba_geral import (
    ORIGENS, VERSAO_CONSULTA, selecionar_registro, mais_recente, referencia_registro,
)
from core.integrations.fireads.extratores import extrair_email, extrair_nome
from core.integrations.fireads.atribuicao import CHAVE, capturar


def decisao_organica(resultado, motivo=None, *, referencia=None):
    return {
        "resultado": resultado,
        "origem": "organico",
        "motivo": motivo,
        "dados_titular": {},
        "referencia": referencia,
    }


def _interpretar(rows, numero, fuso=None, *, aba=ABA_DESTINO):
    row, encontrados = selecionar_registro(rows, numero, fuso)
    alvo_entrega = row if row is not None else mais_recente(encontrados, fuso)
    referencia = referencia_registro(alvo_entrega, aba, fuso)
    if row is None:
        return decisao_organica(
            "ausente", "canal_nao_elegivel" if encontrados else "telefone_ausente",
            referencia=referencia,
        )
    origem = ORIGENS[normalizar(row.get("Canal"))]
    nome = extrair_nome(row.get("Nome"))
    email = extrair_email(row.get("Email"))
    alvo = row.get("Para quem é")
    dependente = destino(alvo)
    if not nome or not email or not str(alvo or "").strip():
        return decisao_organica("incompleto", "campos_ausentes", referencia=referencia)
    if dependente is None:
        # Uma opção fora do contrato não autoriza inventar titular/dependente.
        return decisao_organica("incompleto", "destinatario_desconhecido", referencia=referencia)
    return {
        "resultado": "importado",
        "origem": origem,
        "status_dependente": dependente,
        "id_registro_origem": str(row.get("id") or ""),
        "data_formulario": referencia["data_interpretada"],
        "referencia": referencia,
        "versao": VERSAO_CONSULTA,
        "dados_titular": {
            "nome": nome,
            "email": email,
            # Marcador histórico da coleta; na FireAds a fonte é o formulário.
            "resultado_email": "email_valido",
        },
    }


def interpretar(rows, numero, fuso=None, *, aba=ABA_DESTINO):
    from core.integrations.fireads.aba_geral import selecionar_entrega
    row = selecionar_entrega(rows, numero, fuso)
    decisao = _interpretar(rows, numero, fuso, aba=aba)
    decisao[CHAVE] = capturar(row, aba, fuso)
    return decisao
