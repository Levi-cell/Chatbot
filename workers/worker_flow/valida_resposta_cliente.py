import logging
import re
import unicodedata

from core.logging_config import short_value


logger = logging.getLogger("worker.valida_resposta")

TIPOS_MENSAGEM_SUPORTADOS = {"text", "interactive"}

RESULTADO_RESPOSTA_VALIDA = "resposta_valida"
RESULTADO_TIPO_MENSAGEM_NAO_SUPORTADO = "tipo_mensagem_nao_suportado"
RESULTADO_MENSAGEM_FORA_DE_CONTEXTO = "mensagem_fora_de_contexto"
RESULTADO_PERGUNTA_FINANCEIRA = "pergunta_financeira"

TIPO_TRATAMENTO_NOME_INVALIDO = "nome_invalido"
TIPO_TRATAMENTO_FINANCEIRO = "pergunta_financeira"

PADRAO_PERGUNTA_FINANCEIRA = re.compile(
    r"\b("
    r"valor(?:es)?|"
    r"preco(?:s)?|"
    r"custo(?:s)?|"
    r"mensalidade(?:s)?|"
    r"mensal|"
    r"investimento(?:s)?|"
    r"capital|"
    r"quanto\s+custa|"
    r"qual\s+(?:o\s+)?(?:valor|preco|custo)"
    r")\b"
)

PADRAO_CARACTERE_INVALIDO_NOME = re.compile(r"[^a-z\s'-]")
PADRAO_REPETICAO_CARACTERE = re.compile(r"([a-z])\1{3,}")
PADRAO_PALAVRAS = re.compile(r"[a-z]+")

PALAVRAS_NOME_PEJORATIVAS = {
    "bosta",
    "caralho",
    "fdp",
    "merda",
    "porra",
    "puta",
    "puto",
}


def validar_resposta_cliente(contexto_historico):
    tipo_mensagem = contexto_historico.get("tipo_mensagem_atual")

    if tipo_mensagem in TIPOS_MENSAGEM_SUPORTADOS:
        if _mensagem_pergunta_financeira(contexto_historico):
            _logar_tratamento_texto(contexto_historico, TIPO_TRATAMENTO_FINANCEIRO)
            return {
                "resultado": RESULTADO_PERGUNTA_FINANCEIRA,
                "tipo_tratamento": TIPO_TRATAMENTO_FINANCEIRO,
                "motivo": TIPO_TRATAMENTO_FINANCEIRO,
                "avancar_etapa": False,
            }

        if _mensagem_nome_invalido(contexto_historico):
            _logar_tratamento_texto(contexto_historico, TIPO_TRATAMENTO_NOME_INVALIDO)
            return {
                "resultado": RESULTADO_MENSAGEM_FORA_DE_CONTEXTO,
                "tipo_tratamento": TIPO_TRATAMENTO_NOME_INVALIDO,
                "motivo": TIPO_TRATAMENTO_NOME_INVALIDO,
                "avancar_etapa": False,
            }

        return {
            "resultado": RESULTADO_RESPOSTA_VALIDA,
            "tipo_tratamento": None,
            "motivo": None,
        }

    mensagem_cliente_atual = contexto_historico["mensagem_cliente_atual"]

    logger.info(
        "resposta_cliente_invalida | motivo=tipo_mensagem_nao_suportado acao=tratar_sem_avancar id_conversa=%s id_mensagem_fila=%s cliente=%s phone_number_id=%s tipo=%s etapa_cliente=%s etapa_resposta=%s",
        contexto_historico["id_conversa"],
        mensagem_cliente_atual["id_mensagem_fila"],
        short_value(mensagem_cliente_atual["cliente_telefone"]),
        short_value(mensagem_cliente_atual["id_phone_unidade"]),
        tipo_mensagem,
        contexto_historico["id_etapa_cliente"],
        contexto_historico["id_etapa_resposta"],
    )

    return {
        "resultado": RESULTADO_TIPO_MENSAGEM_NAO_SUPORTADO,
        "tipo_tratamento": RESULTADO_TIPO_MENSAGEM_NAO_SUPORTADO,
        "motivo": RESULTADO_TIPO_MENSAGEM_NAO_SUPORTADO,
        "tipo_mensagem": tipo_mensagem,
        "avancar_etapa": False,
    }


def _mensagem_pergunta_financeira(contexto_historico):
    texto = contexto_historico.get("texto_cliente_atual") or ""
    texto_normalizado = _normalizar_texto(texto)

    return bool(PADRAO_PERGUNTA_FINANCEIRA.search(texto_normalizado))


def _mensagem_nome_invalido(contexto_historico):
    if contexto_historico.get("tipo_mensagem_atual") != "text":
        return False

    if not _cliente_esta_respondendo_nome(contexto_historico):
        return False

    texto = contexto_historico.get("texto_cliente_atual") or ""
    texto_normalizado = _normalizar_texto(texto).strip()
    texto_compacto = re.sub(r"\s+", "", texto_normalizado)

    if len(texto_compacto) < 2:
        return True

    if PADRAO_CARACTERE_INVALIDO_NOME.search(texto_normalizado):
        return True

    if PADRAO_REPETICAO_CARACTERE.search(texto_compacto):
        return True

    if _tem_padrao_repetitivo(texto_compacto):
        return True

    palavras = set(PADRAO_PALAVRAS.findall(texto_normalizado))
    return bool(palavras & PALAVRAS_NOME_PEJORATIVAS)


def _cliente_esta_respondendo_nome(contexto_historico):
    return (
        contexto_historico.get("id_etapa_atual") == 1
        and contexto_historico.get("id_etapa_cliente") == 1
    )


def _tem_padrao_repetitivo(texto_compacto):
    for tamanho_bloco in range(1, 4):
        if len(texto_compacto) < tamanho_bloco * 3:
            continue

        bloco = texto_compacto[:tamanho_bloco]
        repeticoes, resto = divmod(len(texto_compacto), tamanho_bloco)

        if resto == 0 and texto_compacto == bloco * repeticoes:
            return True

    return False


def _logar_tratamento_texto(contexto_historico, motivo):
    mensagem_cliente_atual = contexto_historico["mensagem_cliente_atual"]

    logger.info(
        "resposta_cliente_tratamento | motivo=%s acao=tratar_sem_avancar id_conversa=%s id_mensagem_fila=%s cliente=%s phone_number_id=%s etapa_cliente=%s etapa_resposta=%s",
        motivo,
        contexto_historico["id_conversa"],
        mensagem_cliente_atual["id_mensagem_fila"],
        short_value(mensagem_cliente_atual["cliente_telefone"]),
        short_value(mensagem_cliente_atual["id_phone_unidade"]),
        contexto_historico["id_etapa_cliente"],
        contexto_historico["id_etapa_resposta"],
    )


def _normalizar_texto(texto):
    texto_sem_acento = unicodedata.normalize("NFKD", texto)
    texto_ascii = "".join(
        caractere
        for caractere in texto_sem_acento
        if not unicodedata.combining(caractere)
    )

    return texto_ascii.lower()
