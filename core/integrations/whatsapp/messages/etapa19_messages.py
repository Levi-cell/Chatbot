"""Entrega ao comercial: dia e horário ainda serão combinados."""

from core.integrations.whatsapp.messages.tratamentos.composicao import (
    compor_mensagem_inicial,
)
from core.integrations.whatsapp.messages.tratamentos.midia import (
    montar_mensagem_tratamento_midia,
)

TITULO_BOTAO_COMERCIAL = "Falar com consultor"
MENSAGEM_REPETICAO_ETAPA19 = (
    "Nossa equipe entrará em contato para reservar {participante} na nossa unidade.\n\n"
    "Você também pode falar com nosso consultor pelo botão abaixo "
    "para combinar o melhor dia e horário para sua reserva.\n\n"
    "Se quiser avaliar nosso atendimento, é só me avisar por aqui!"
)
MENSAGEM_PADRAO_ETAPA19 = compor_mensagem_inicial(
    "Perfeito! ☺️\n\n", MENSAGEM_REPETICAO_ETAPA19
)


def montar_mensagem_etapa19(
    nome_dependente=None, *, pedir_texto=False, repeticao=False
):
    participante = (
        f"a *experiência Supera gratuita* de {nome_dependente}"
        if nome_dependente
        else "sua *experiência Supera gratuita*"
    )
    pergunta = MENSAGEM_REPETICAO_ETAPA19.format(participante=participante)
    if pedir_texto:
        return montar_mensagem_tratamento_midia(pergunta)
    return (
        pergunta
        if repeticao
        else MENSAGEM_PADRAO_ETAPA19.format(participante=participante)
    )
