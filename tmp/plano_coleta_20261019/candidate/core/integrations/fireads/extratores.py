"""Extrai campos estruturados dos formulários, sem validar respostas de chat."""

import unicodedata

from core.integrations.fireads.contrato import normalizar
from core.validacoes.nomes_compostos import PRIMEIROS_NOMES_COMPOSTOS


def extrair_nome(valor):
    """Usa um par conhecido ou a primeira palavra; ignora o restante do perfil."""
    palavras = unicodedata.normalize("NFC", str(valor or "")).split()
    if not palavras:
        return None

    # Reconhecer pares explícitos evita confundir sobrenome ou profissão com
    # nome composto. Caracteres desconhecidos não impedem a importação.
    par = tuple(normalizar(palavra) for palavra in palavras[:2])
    quantidade = 2 if par in PRIMEIROS_NOMES_COMPOSTOS else 1
    return " ".join(palavra.capitalize() for palavra in palavras[:quantidade])


def extrair_email(valor):
    """Lê o campo fornecido pelo formulário, sem impor a gramática do WhatsApp."""
    return str(valor or "").strip().lower() or None
