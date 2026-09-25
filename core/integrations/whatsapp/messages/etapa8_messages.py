"""Etapa 8: oferta adiada; qualquer retorno, inclusive follow-up, apresenta a 9."""

from core.integrations.whatsapp.messages.componentes_compartilhados import (
    RODAPE_ETAPA8_ESPERA,
    montar_texto_com_rodape,
)


### MENSAGEM INICIAL QUANDO A OFERTA É ADIADA
MENSAGEM_PADRAO_ETAPA8 = (
    "Tudo bem! Podemos continuar no seu ritmo. 🧡☺️ "
    "Quando quiser retomar sua reserva, é só me avisar por aqui.\n"
    "Enquanto isso, nos siga no nosso Instagram e acompanhe nossas atualizações. "
    "Um abraço! 🧡🤗 "
    "{link_instagram}"
)

# Não há mensagem de repetição: quem voltou recebe a oferta da etapa 9.


def montar_mensagem_oferta_adiada_etapa8(link_instagram):
    link = str(link_instagram or "").strip()
    if not link:
        raise ValueError("Link do Instagram da unidade não configurado")
    return montar_texto_com_rodape(
        MENSAGEM_PADRAO_ETAPA8.format(link_instagram=link),
        RODAPE_ETAPA8_ESPERA,
    )
