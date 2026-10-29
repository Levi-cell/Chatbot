"""Despedida ao adiar a oferta; novas mensagens retomam a etapa 9."""

from core.integrations.whatsapp.messages.componentes_compartilhados import (
    RODAPE_ETAPA8_ESPERA,
    montar_texto_com_rodape,
)


### MENSAGEM INICIAL QUANDO A OFERTA É ADIADA
MENSAGEM_PADRAO_ETAPA8 = (
    "Tudo bem! Podemos continuar no seu ritmo. 🧡☺️\n\n"
    "Quando quiser retomar sua reserva, é só me avisar por aqui. "
    "Enquanto isso, nos siga no nosso Instagram e acompanhe nossas atualizações.\n "
    "Um abraço! 🧡🤗 \n\n"
    "{link_instagram}"
)

# Variante neutra mantida para compatibilidade de chamadas diretas. O fluxo
# não a usa no retorno: dúvidas acompanham a apresentação da etapa 9.
MENSAGEM_REPETICAO_ETAPA8 = (
    "Quando quiser retomar sua reserva, é só me avisar por aqui. 🧡"
)


def montar_mensagem_oferta_adiada_etapa8(link_instagram, *, repeticao=False):
    if repeticao:
        return MENSAGEM_REPETICAO_ETAPA8
    link = str(link_instagram or "").strip()
    if not link:
        raise ValueError("Link do Instagram da unidade não configurado")
    return montar_texto_com_rodape(
        MENSAGEM_PADRAO_ETAPA8.format(link_instagram=link),
        RODAPE_ETAPA8_ESPERA,
    )
