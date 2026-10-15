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
    "organico_site": ("Orgânico Site", "113481"),
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
    texto = str(valor or "").strip()
    numero = re.sub(r"\D", "", texto)
    # Um DDI explícito estrangeiro não pode virar DDD brasileiro por ter 11 dígitos.
    if "+" in texto and (len(numero) not in (12, 13) or not numero.startswith("55")):
        return None
    if len(numero) in (10, 11):
        numero = "55" + numero
    if not re.fullmatch(r"55[1-9]\d\d{8,9}", numero):
        return None
    return numero


def formatos_telefone(valor):
    """Número exato primeiro, seguido da variante móvel do nono dígito.

    Preserva DDI, DDD e os oito dígitos restantes. A alternativa segue a regra
    já usada no utilitário: não transformar números fixos em celulares.
    """
    exato = telefone(valor)
    if not exato:
        return ()
    nacional = exato[2:]
    if len(nacional) == 10 and nacional[2] in "6789":
        return exato, f"55{nacional[:2]}9{nacional[2:]}"
    if len(nacional) == 11 and nacional[2] == "9" and nacional[3] in "6789":
        return exato, f"55{nacional[:2]}{nacional[3:]}"
    return (exato,)


def identidade_telefone(valor):
    """Unifica apenas a chave do lock; não altera o número salvo ou enviado."""
    return max(formatos_telefone(valor), key=len, default=None)


def localizar(rows, numero, coluna, *, incluir_equivalentes=False):
    """Prefere o exato; a escrita examina também variantes para detectar duplicados."""
    formatos = formatos_telefone(numero)
    if not formatos:
        raise ErroFireAds("Telefone fora do contrato brasileiro")
    por_formato = {formato: [] for formato in formatos}
    for row in rows:
        normalizado = telefone(row.get(coluna))
        if normalizado in por_formato:
            por_formato[normalizado].append(row)
    if incluir_equivalentes:
        return [row for formato in formatos for row in por_formato[formato]]
    return next((por_formato[f] for f in formatos if por_formato[f]), [])


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
        "para dependente",
    }
    return True if chave in dependentes else None


def instante(valor, fuso=None):
    texto = str(valor or "").strip()
    try:
        data = datetime.fromisoformat(texto.replace("Z", "+00:00"))
    except ValueError:
        data = None
        for formato in ("%d/%m/%Y %H:%M:%S", "%d/%m/%Y %H:%M", "%d/%m/%Y",
                        "%d-%m-%Y %H:%M:%S", "%d-%m-%Y %H:%M", "%d-%m-%Y"):
            try:
                data = datetime.strptime(texto, formato)
                break
            except ValueError:
                continue
        if data is None:
            return None
    if data.tzinfo is None:
        if not fuso:
            return None
        data = data.replace(tzinfo=ZoneInfo(fuso))
    return data.astimezone(timezone.utc)


def _ordem_linha(row, posicao):
    """Usa a linha para desempatar; IDs Meta não são cronológicos."""
    try:
        linha = int(row.get("_row"))
    except (TypeError, ValueError):
        return posicao
    return linha if linha > 0 else posicao


def selecionar(google, meta, numero, fuso=None):
    """Usa o formulário mais recente inteiro, mesmo com respostas divergentes.

    Datas sem offset usam o fuso configurado, ou Brasília quando ausente.
    Empate usa a maior linha e depois a última posição da resposta, sem
    prioridade por origem. Datas inválidas ficam depois das válidas. Estes
    desempates não geram resultado de ambiguidade.
    """
    candidatos = []
    fuso_leitura = fuso or "America/Sao_Paulo"
    formatos = set(formatos_telefone(numero))
    if not formatos:
        raise ErroFireAds("Telefone fora do contrato brasileiro")
    for origem, rows, coluna, campo_data in (
        ("google", google, "WhatsApp", "Data/Hora"),
        ("meta", meta, "phone_number", "created_time"),
    ):
        # O mais novo pode usar outra variante do nono dígito. Preservar a
        # ordem original para o fallback quando a API não trouxer _row.
        for posicao, row in enumerate(rows, start=1):
            if telefone(row.get(coluna)) not in formatos:
                continue
            data = instante(row.get(campo_data), fuso_leitura)
            ordem = (
                data or datetime.min.replace(tzinfo=timezone.utc),
                _ordem_linha(row, posicao),
                posicao,
            )
            candidatos.append((ordem, (origem, row, data)))
    return max(candidatos, key=lambda item: item[0])[1] if candidatos else None


def bloco_observacoes(id_integracao, id_conversa, observacoes, *, versao=1):
    chave = f"CHATBOT:{int(id_integracao)}:{int(id_conversa)}"
    if versao == 2:
        return (
            "Observações de atendimento\n\n"
            "Registro técnico da ESL Tech: esta referência é apena para manter o atendimento "
            "sincronizado entre os sistemas e a evitar registros repetidos. "
            "Não é relevante para o atendimento com o Lead\n"
            f"[INICIO {chave}]\n\n{observacoes}\n[FIM {chave}]"
        )
    if versao != 1:
        raise ErroFireAds("Versão de observações desconhecida")
    return (
        f"[INICIO {chave}]\nObservações do atendimento — conversa {id_conversa}\n"
        f"{observacoes}\n[FIM {chave}]"
    )


def marcador_observacoes(bloco):
    marcadores = re.findall(r"^\[INICIO CHATBOT:\d+:\d+\]$", bloco, re.MULTILINE)
    if len(marcadores) != 1:
        raise ErroFireAds("Bloco sem identificador técnico único")
    fim = marcadores[0].replace("[INICIO ", "[FIM ", 1)
    if bloco.count(fim) != 1 or not bloco.endswith(fim):
        raise ErroFireAds("Bloco técnico incompleto")
    return marcadores[0]


def acrescentar_observacoes(anterior, bloco):
    """Preserva inclusive zero e espaços; conflito nunca vira sobrescrita."""
    if anterior is None:
        anterior = ""
    if not isinstance(anterior, (str, int, float)) or isinstance(anterior, bool):
        raise ErroFireAds("Observação tem tipo inesperado")
    texto = str(anterior)
    marcador = marcador_observacoes(bloco)
    if marcador in texto:
        if texto.count(marcador) != 1 or bloco not in texto:
            raise ErroFireAds("Bloco da conversa existe com conteúdo divergente")
        return texto, False
    novo = texto + ("\n\n" if texto else "") + bloco
    if len(novo) > 45000:
        raise ErroFireAds("Observação excede limite operacional; não truncar")
    return novo, True
