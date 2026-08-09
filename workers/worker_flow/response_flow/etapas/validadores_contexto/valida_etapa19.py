import re

from workers.worker_flow.response_flow.etapas.validadores_universais.validador_financeiro import (
    normalizar_texto,
)


TIPO_TRATAMENTO_SATISFACAO_INVALIDA = "satisfacao_invalida"

_NOTAS_POR_RESPOSTA = {
    "1": 1,
    "muito ruim": 1,
    "1 muito ruim": 1,
    "2": 2,
    "ruim": 2,
    "2 ruim": 2,
    "3": 3,
    "regular": 3,
    "3 regular": 3,
    "4": 4,
    "muito bom": 4,
    "4 muito bom": 4,
    "5": 5,
    "excelente": 5,
    "5 excelente": 5,
}


def validar_etapa19(conteudo_texto):
    """Traduz uma unica opcao coerente da pesquisa para uma nota de 1 a 5."""
    if not isinstance(conteudo_texto, str):
        return None

    texto_normalizado = _normalizar_resposta(conteudo_texto)

    # Suporta o callback_data caso algum payload nao traga o titulo da linha.
    if texto_normalizado.startswith("satisfacao "):
        texto_normalizado = texto_normalizado.removeprefix(
            "satisfacao "
        )

    return _NOTAS_POR_RESPOSTA.get(texto_normalizado)


def _normalizar_resposta(texto):
    texto_sem_acento = normalizar_texto(texto)
    texto_sem_pontuacao = re.sub(
        r"[^a-z0-9\s]",
        " ",
        texto_sem_acento,
    )
    return " ".join(texto_sem_pontuacao.split())
