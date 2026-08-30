import re


def normalizar_numero_comercial_whatsapp(numero_comercial):
    """Normaliza um telefone comercial brasileiro para o formato do wa.me."""
    numero = re.sub(r"\D", "", str(numero_comercial or ""))

    if len(numero) in {10, 11}:
        numero = f"55{numero}"

    if not numero.startswith("55") or len(numero) not in {12, 13}:
        raise ValueError(
            "Número comercial da unidade inválido para link do WhatsApp"
        )

    return numero


def montar_link_numero_comercial_whatsapp(numero_comercial):
    numero = normalizar_numero_comercial_whatsapp(numero_comercial)
    return f"https://wa.me/{numero}"


def numero_comercial_whatsapp_valido(numero_comercial):
    try:
        normalizar_numero_comercial_whatsapp(numero_comercial)
    except ValueError:
        return False

    return True
