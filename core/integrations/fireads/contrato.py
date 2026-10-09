"""Regras puras de origem, telefone e composição sem perda de observações."""

import re
import unicodedata
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

ABA_GOOGLE = "Leads Google Ads (NÃO EDITAR)"
ABA_META = "[FIRE] Leads Ads Geral - 7.2"
ABA_DESTINO = "LEADS GERAL - Feedback"
CANAIS = {
    "google": ("Google Ads", "113336"),
    "meta": ("Meta Ads", "113340"),
    "organico": ("Orgânico", "113481"),
}


class ErroFireAds(ValueError):
    """Contrato incompleto, identidade ambígua ou conflito externo."""


def normalizar(texto):
    base = unicodedata.normalize("NFKD", str(texto or "").lower())
    return " ".join(
        re.sub(
            r"[^a-z0-9]+", " ", "".join(c for c in base if not unicodedata.combining(c))
        ).split()
    )


def telefone(valor):
    numero = re.sub(r"\D", "", str(valor or ""))
    if len(numero) in (10, 11):
        numero = "55" + numero
    if not re.fullmatch(r"55[1-9]\d\d{8,9}", numero):
        return None
    return numero


def localizar(rows, numero, coluna):
    """Somente correspondência exata normalizada; não aproximar pessoas."""
    esperado = telefone(numero)
    if not esperado:
        raise ErroFireAds("Telefone fora do contrato brasileiro")
    return [r for r in rows if telefone(r.get(coluna)) == esperado]


def destino(valor):
    chave = normalizar(valor)
    if chave == "para mim":
        return False
    dependentes = {
        # Valores do formulário e identificadores serializados pela Meta.
        "pai ou mae",
        "filho ou filha",
        "para meu pai mae",
        "para meu pai ou minha mae",
        "para meu avo avo",
        "para meu avo ou minha avo",
        "para outra pessoa",
        "para meu filho ou filha",
        "para meu filho minha filha",
        "para meu filho filha",
        "para mim e outra pessoa",
        "mim e outra",
    }
    return True if chave in dependentes else None


def instante(valor, fuso=None):
    texto = str(valor or "").strip()
    try:
        data = datetime.fromisoformat(texto.replace("Z", "+00:00"))
    except ValueError:
        try:
            data = datetime.strptime(texto, "%d/%m/%Y %H:%M")
        except ValueError:
            return None
    if data.tzinfo is None:
        if not fuso:
            return None
        data = data.replace(tzinfo=ZoneInfo(fuso))
    return data.astimezone(timezone.utc)


def selecionar(google, meta, numero, fuso=None):
    """Escolhe um registro inteiro; sem combinar dados de diferentes formulários."""
    candidatos = [
        ("google", r, instante(r.get("Data/Hora"), fuso))
        for r in localizar(google, numero, "WhatsApp")
    ]
    candidatos += [
        ("meta", r, instante(r.get("created_time"), fuso))
        for r in localizar(meta, numero, "phone_number")
    ]
    if not candidatos:
        return None
    if len(candidatos) == 1:
        return candidatos[0]
    if any(c[2] is None for c in candidatos):
        raise ErroFireAds("Datas insuficientes para comparar formulários")
    candidatos.sort(key=lambda c: c[2], reverse=True)
    if candidatos[0][2] == candidatos[1][2]:
        raise ErroFireAds("Formulários empatados; origem não inequívoca")
    return candidatos[0]


def bloco_observacoes(id_integracao, id_conversa, observacoes):
    chave = f"CHATBOT:{int(id_integracao)}:{int(id_conversa)}"
    return (
        f"[INICIO {chave}]\nObservações do atendimento — conversa {id_conversa}\n"
        f"{observacoes}\n[FIM {chave}]"
    )


def acrescentar_observacoes(anterior, bloco):
    """Preserva inclusive zero e espaços; conflito nunca vira sobrescrita."""
    if anterior is None:
        anterior = ""
    if not isinstance(anterior, (str, int, float)) or isinstance(anterior, bool):
        raise ErroFireAds("Observação tem tipo inesperado")
    texto = str(anterior)
    marcador = bloco.split("\n", 1)[0]
    if marcador in texto:
        if texto.count(marcador) != 1 or bloco not in texto:
            raise ErroFireAds("Bloco da conversa existe com conteúdo divergente")
        return texto, False
    novo = texto + ("\n\n" if texto else "") + bloco
    if len(novo) > 45000:
        raise ErroFireAds("Observação excede limite operacional; não truncar")
    return novo, True
