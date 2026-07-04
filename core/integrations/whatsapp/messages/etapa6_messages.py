from core.integrations.whatsapp.messages.componentes_compartilhados import (
    RODAPE_ETAPA6_ESPERA,
    montar_texto_com_rodape,
)


# ENTRADA NA ETAPA 6 - OFERTA ADIADA

MENSAGEM_OFERTA_ADIADA_ETAPA6 = (
    "Tudo bem! ☺️\n"
    "Então nos falamos novamente em breve.\n"
    "Enquanto isso, nos siga no nosso Instagram e acompanhe nossas "
    "atualizações. Um abraço! 🫂🤗\n"
    "{link_instagram}"
)


def montar_mensagem_oferta_adiada_etapa6(link_instagram):
    link = str(link_instagram or "").strip()

    if not link:
        raise ValueError("Link do Instagram da unidade não configurado")

    return montar_texto_com_rodape(
        MENSAGEM_OFERTA_ADIADA_ETAPA6.format(
            link_instagram=link,
        ),
        RODAPE_ETAPA6_ESPERA,
    )
