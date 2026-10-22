"""Seleção e identidade do formulário da aba geral, sem HTTP ou SQL."""

from datetime import datetime, timezone

from .contrato import ErroFireAds, instante, localizar, normalizar, telefone

VERSAO_CONSULTA = 2
ORIGENS = {"google ads": "google", "meta ads": "meta", "organico site": "organico_site",
           "chat fire": "chat_fire"}
CAMPOS_IDENTIDADE = ("WhatsApp", "Data/Hora", "Canal", "Nome", "Email", "Para quem é")


def numero_linha(row):
    linha = row.get("_row")
    if type(linha) is not int or linha < 2:
        raise ErroFireAds("Linha de destino inválida")
    return linha


def mais_recente(rows, fuso=None):
    """Datas válidas precedem inválidas; empates usam a posição física da linha."""
    if not rows:
        return None
    return max(rows, key=lambda row: (
        instante(row.get("Data/Hora"), fuso or "America/Sao_Paulo")
        or datetime.min.replace(tzinfo=timezone.utc),
        numero_linha(row),
    ))


def selecionar_registro(rows, numero, fuso=None):
    encontrados = localizar(rows, numero, "WhatsApp", incluir_equivalentes=True)
    elegiveis = [r for r in encontrados if normalizar(r.get("Canal")) in ORIGENS]
    return mais_recente(elegiveis, fuso), encontrados


def referencia_registro(row, aba, fuso=None):
    if row is None:
        return None
    data = instante(row.get("Data/Hora"), fuso or "America/Sao_Paulo")
    return {
        "aba": aba, "linha": numero_linha(row),
        "telefone": telefone(row.get("WhatsApp")),
        "campos": {campo: row.get(campo) for campo in CAMPOS_IDENTIDADE},
        "data_interpretada": data.isoformat() if data else None,
        "criterio_recencia": "data_linha" if data else "linha_sem_data_valida",
    }


def relocalizar(rows, referencia, aba):
    """Não troca um formulário já escolhido por um novo cadastro do mesmo telefone."""
    if referencia.get("aba") != aba:
        raise ErroFireAds("Aba do registro selecionado diverge do envio")
    campos = referencia.get("campos")
    if not isinstance(campos, dict) or set(campos) != set(CAMPOS_IDENTIDADE):
        raise ErroFireAds("Referência do formulário incompleta")
    candidatos = [r for r in rows if all(r.get(c) == campos[c] for c in CAMPOS_IDENTIDADE)]
    if len(candidatos) == 1:
        return candidatos[0]
    # Linhas integralmente idênticas não possuem identidade estável na API.
    # A posição original resolve apenas enquanto continua apontando para esse conteúdo.
    original = [r for r in candidatos if numero_linha(r) == referencia.get("linha")]
    if len(original) == 1:
        return original[0]
    raise ErroFireAds("Registro selecionado ausente ou deslocado sem identidade única")


def configuracao_compativel(entrada, abertura):
    """A migração fornece a ponte de configuração para resultados legados concluídos."""
    if entrada.get("versao") == VERSAO_CONSULTA:
        config = entrada
    elif "versao" not in entrada:
        config = entrada.get("compatibilidade_aba_geral") or {}
        if config.get("valida") is not True:
            return False
    else:
        return False
    return all(config.get(campo) == abertura.get(campo) for campo in ("url", "aba", "fuso"))
