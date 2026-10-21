"""Aceita uma única preferência explícita de turno, sem inferir disponibilidade."""

import re
import unicodedata

TIPOS_MENSAGEM_ACEITOS_ETAPA18 = {"text", "interactive", "interactive_button"}

# Sinônimos descrevem o mesmo turno, nunca um horário exato de agendamento.
TURNOS_POR_TERMO = {
    "manha": "manha", "matutino": "manha", "matutina": "manha",
    "tarde": "tarde", "vespertino": "tarde", "vespertina": "tarde",
    "noite": "noite", "noturno": "noite", "noturna": "noite",
}
TERMOS_TURNO = "|".join(TURNOS_POR_TERMO)
PADRAO_TURNOS = re.compile(rf"\b({TERMOS_TURNO})\b")
PADRAO_RECUSA = re.compile(r"\b(nao|n|nunca|nem|sem|nenhum|nenhuma|impossivel)\b")
PADRAO_INDEFINICAO = re.compile(
    r"\b(talvez|qualquer|indiferente|depende|duvida|acho)\b|\btanto faz\b"
)
PADRAO_SAUDACAO = re.compile(r"^(?:(?:oi|ola|bom dia|boa tarde|boa noite)\b\s*)+")

# A frase inteira precisa expressar escolha/disponibilidade. Encontrar apenas
# 'tarde' em 'boa tarde' ou 'trabalho à tarde' não autoriza salvar preferência.
REFERENCIA_TURNO = (
    r"(?:para\s+)?(?:(?:pela|de|da|a|o|no|na)\s+)?"
    r"(?:(?:turno|periodo|horario)\s+(?:(?:da|de)\s+)?)?"
    rf"(?:{TERMOS_TURNO})"
)
PREFIXO_ESCOLHA = (
    r"(?:(?:eu|so|somente|apenas|para mim|pra mim|sim|ok|certo|"
    r"amanha|hoje|por favor)\s+)*"
)
ACAO_ESCOLHA = (
    r"(?:prefiro|quero|queria|gostaria de|posso|consigo|poderei|vou|"
    r"escolho|opto por|fico com|pode(?: ser)?|da(?: para)?|e melhor|"
    r"estou (?:livre|disponivel)|to (?:livre|disponivel)|"
    r"o melhor(?: para mim|pra mim)? e|minha preferencia e|"
    r"tenho disponibilidade(?: para)?|tenho horario livre)"
    r"(?:\s+(?:so|somente|apenas))?"
    r"(?:\s+(?:ir|comparecer|reservar|agendar|marcar))?"
)
COMPLEMENTO_ESCOLHA = (
    r"(?:\s+(?:fica|e|esta|seria|funciona)\s+(?:bem|melhor|bom|boa|otimo|otima))?"
    r"(?:\s+(?:funciona|pode ser|da certo))?"
    r"(?:\s+(?:para mim|pra mim))?"
    r"(?:\s+(?:por favor|obrigado|obrigada|sim|mesmo))?"
)
FRASE_ESCOLHA = (
    rf"{PREFIXO_ESCOLHA}(?:{ACAO_ESCOLHA}\s+)?"
    rf"{REFERENCIA_TURNO}{COMPLEMENTO_ESCOLHA}"
)
PADRAO_ESCOLHA = re.compile(rf"{FRASE_ESCOLHA}(?:\s+(?:e\s+)?{FRASE_ESCOLHA})*")


def validar_etapa18(texto, tipo_mensagem="text"):
    """Retorna o valor persistível, ou None para repetir a escolha.

    O webhook extrai o título do botão; ambos os tipos interativos percorrem
    a mesma validação do texto digitado. 'Amanhã' não significa 'manhã'.
    Dois turnos distintos, negação, dúvida ou frase sem escolha repetem a etapa.
    """
    if tipo_mensagem not in TIPOS_MENSAGEM_ACEITOS_ETAPA18 or not isinstance(
        texto, str
    ):
        return None
    normalizado = "".join(
        c
        for c in unicodedata.normalize("NFD", texto.casefold())
        if unicodedata.category(c) != "Mn"
    )
    if (
        "?" in texto
        or PADRAO_RECUSA.search(normalizado)
        or PADRAO_INDEFINICAO.search(normalizado)
    ):
        return None
    # Tolera acentos, espaços, pontuação e emojis, mas não perguntas. Remover
    # somente a saudação inicial evita contar 'boa tarde' como uma escolha.
    normalizado = " ".join(re.sub(r"[^a-z0-9\s]", " ", normalizado).split())
    normalizado = PADRAO_SAUDACAO.sub("", normalizado).strip()
    turnos = {TURNOS_POR_TERMO[termo] for termo in PADRAO_TURNOS.findall(normalizado)}
    if len(turnos) != 1 or not PADRAO_ESCOLHA.fullmatch(normalizado):
        return None
    return next(iter(turnos))
