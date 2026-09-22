"""Compatibilidade: os tratamentos agora vivem em módulos separados.

Novas etapas importam diretamente de messages.tratamentos.<tipo>.
"""

from .tratamentos.financeiro import (
    MENSAGEM_TRATAMENTO_FINANCEIRO,
    montar_mensagem_tratamento_financeiro,
)
from .tratamentos.reforco_escolar import (
    MENSAGEM_TRATAMENTO_REFORCO_ESCOLAR,
    montar_mensagem_tratamento_reforco_escolar,
)

__all__ = [
    "MENSAGEM_TRATAMENTO_FINANCEIRO",
    "montar_mensagem_tratamento_financeiro",
    "MENSAGEM_TRATAMENTO_REFORCO_ESCOLAR",
    "montar_mensagem_tratamento_reforco_escolar",
]
