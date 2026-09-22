"""Lembrete proativo; a saudação de reação está em tratamentos/retorno_followup."""

from .tratamentos.retorno_followup import montar_saudacao_retomada_followup

MENSAGEM_FOLLOWUP = ( "Olá, gostaria de continuar seu atendimento agora?"
                      )

__all__ = ["MENSAGEM_FOLLOWUP", "montar_saudacao_retomada_followup"]
