"""
Componentes visuais compartilhados exclusivamente pelas etapas 10 a 15.

Este helper centraliza as três opções e o rodapé das seis perguntas da
triagem. Ele não contém perguntas, não envia mensagens e não decide etapas.
"""

BOTAO_TRIAGEM_NUNCA = "Nunca"
BOTAO_TRIAGEM_AS_VEZES = "Às vezes"
BOTAO_TRIAGEM_FREQUENTEMENTE = "Frequentemente"

BOTOES_TRIAGEM = (
    BOTAO_TRIAGEM_NUNCA,
    BOTAO_TRIAGEM_AS_VEZES,
    BOTAO_TRIAGEM_FREQUENTEMENTE,
)

RODAPE_TRIAGEM = "Selecione uma opção abaixo"


def montar_botoes_triagem():
    return BOTOES_TRIAGEM


def montar_rodape_triagem():
    return RODAPE_TRIAGEM
