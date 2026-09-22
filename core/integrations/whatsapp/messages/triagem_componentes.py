"""
Componentes compartilhados exclusivamente pelas etapas 12 a 17.

Este helper centraliza as três opções e o rodapé das seis perguntas da
triagem e a orientação própria para uma resposta inválida. Ele não contém
perguntas, não envia mensagens e não decide etapas.
"""

from core.integrations.whatsapp.messages.componentes_compartilhados import (
    RODAPE_OPCAO_UNICA,
)
from core.triagem.perguntas import FAIXA_ETARIA_ADULTA, FAIXA_ETARIA_INFANTIL


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


def montar_orientacao_contexto_triagem(
    *, nome_dependente=None, faixa_etaria=FAIXA_ETARIA_ADULTA
):
    """Orienta a escolha sem concatenar a pergunta canônica ou sua repetição."""
    # Mantém a identificação do participante usada no catálogo de perguntas.
    nome_dependente_normalizado = (
        nome_dependente.strip() if isinstance(nome_dependente, str) else ""
    )
    if faixa_etaria == FAIXA_ETARIA_INFANTIL and not nome_dependente_normalizado:
        raise ValueError("Nome da pessoa é obrigatório na triagem infantil")
    pessoa = (
        f"em {nome_dependente_normalizado}"
        if nome_dependente_normalizado
        else "em você"
    )
    return (
        "Olha, não consegui entender sua resposta. "
        f"Pensando {pessoa}, responda à pergunta acima com a frequência "
        "que melhor representa o dia a dia, usando uma das opções abaixo."
    )
