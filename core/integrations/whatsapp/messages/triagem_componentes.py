"""
Componentes visuais compartilhados exclusivamente pelas etapas 12 a 17.

Este helper centraliza as três opções e o rodapé das seis perguntas da
triagem. Ele não contém perguntas, não envia mensagens e não decide etapas.
"""

from core.integrations.whatsapp.messages.componentes_compartilhados import (
    RODAPE_OPCAO_UNICA,
)


BOTAO_TRIAGEM_NUNCA = "Nunca"
BOTAO_TRIAGEM_AS_VEZES = "Às vezes"
BOTAO_TRIAGEM_FREQUENTEMENTE = "Frequentemente"

BOTOES_TRIAGEM = (
    BOTAO_TRIAGEM_NUNCA,
    BOTAO_TRIAGEM_AS_VEZES,
    BOTAO_TRIAGEM_FREQUENTEMENTE,
)

RODAPE_TRIAGEM = RODAPE_OPCAO_UNICA


def montar_botoes_triagem():
    return BOTOES_TRIAGEM


def montar_rodape_triagem():
    return RODAPE_TRIAGEM
