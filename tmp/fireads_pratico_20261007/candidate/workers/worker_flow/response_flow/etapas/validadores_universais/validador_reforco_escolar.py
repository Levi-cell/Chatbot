import re

from workers.worker_flow.response_flow.etapas.validadores_universais.validador_financeiro import (
    normalizar_texto,
)


TIPO_TRATAMENTO_REFORCO_ESCOLAR = "duvida_reforco_escolar"


# Termos que, por si ou em expressoes consagradas, identificam uma duvida sobre
# servicos escolares tradicionais. Os limites de palavra evitam coincidencias
# como "bancario", "reforcou" ou "cursista".
_PADRAO_SERVICO_ESCOLAR = re.compile(
    r"(?:"
    r"\breforco\s+(?:escolar|pedagogico|para\s+a\s+escola)\b|"
    r"\b(?:aula|curso|servico)\s+de\s+reforco\b|"
    r"\bbanca\s+(?:escolar|de\s+estudos?|de\s+reforco)\b|"
    r"\b(?:supletivo|eja|encceja)\b|"
    r"\bcursinho\b|"
    r"\bpre\s+vestibular\b|"
    r"\b(?:curso\s+)?preparatorio\b|"
    r"\b(?:aulas?|professor(?:es)?|professora(?:s)?|"
    r"explicador(?:es)?|explicadora(?:s)?)\s+particular(?:es)?\b|"
    r"\bapoio\s+(?:escolar|pedagogico)\b|"
    r"\b(?:acompanhamento|recuperacao|nivelamento)\s+escolar\b|"
    r"\b(?:dever|tarefa|licao)\s+(?:de\s+)?casa\b"
    r")"
)


_PADRAO_BANCA_NAO_ESCOLAR = re.compile(
    r"\bbanca\s+(?:"
    r"examinadora|avaliadora|academica|de\s+concurso|de\s+tcc"
    r")\b"
)


# "Reforco" e "banca" isolados sao comuns em perguntas muito curtas, mas
# tambem possuem sentidos alheios ao servico ("reforco que...", banca de
# concurso). Por isso, somente formas curtas e inequivocas entram aqui.
_RESPOSTAS_CURTAS_SERVICO_ESCOLAR = {
    "banca",
    "banca escolar",
    "e banca",
    "e banca escolar",
    "e reforco",
    "e reforco escolar",
    "reforco",
    "reforco escolar",
    "tem banca",
    "tem reforco",
    "tem reforco escolar",
}


_PADRAO_PERGUNTA_REFORCO_OU_BANCA = re.compile(
    r"\b(?:"
    r"e(?:\s+tipo)?|eh(?:\s+tipo)?|sao|seria|funciona\s+como|"
    r"tem|faz|oferece|oferecem|"
    r"trabalha\s+com|trabalham\s+com|da|dao"
    r")\s+(?:(?:um|uma)\s+)?(?:reforco|banca)\b"
)


_MATERIA = (
    r"(?:matematica|portugues|fisica|quimica|biologia|ciencias|"
    r"historia|geografia|ingles|espanhol|redacao|gramatica|"
    r"literatura|alfabetizacao|leitura|escrita)"
)


_PADRAO_PERGUNTA_CURTA_MATERIA = re.compile(
    rf"^(?:(?:voces?|o\s+supera)\s+)?"
    rf"(?:tem|possui|oferece|oferecem|trabalha|trabalham)"
    rf"(?:\s+com)?\s+(?:aulas?|cursos?)?\s*(?:de\s+)?{_MATERIA}$"
)


# A materia precisa estar ligada diretamente a uma oferta ou procura por aula,
# ensino ou ajuda. Nao basta a frase conter, em pontos soltos, "tem" e o nome
# de uma disciplina.
_PADRAO_MATERIA_COM_INTENCAO = re.compile(
    rf"(?:"
    rf"\b(?:voces?\s+)?(?:trabalha|trabalham)\s+com\s+{_MATERIA}\b|"
    rf"\b(?:voces?\s+)?(?:ensina|ensinam|ensinar|ajuda|ajudam|ajudar|"
    rf"auxilia|auxiliam|auxiliar)\s+(?:com|em|na|no|de)?\s*{_MATERIA}\b|"
    rf"\b(?:tem|possui|oferece|oferecem|da|dao|faz|fazem)\s+"
    rf"(?:aulas?|cursos?|reforco|apoio|acompanhamento|"
    rf"professor(?:es)?|professora(?:s)?)\s+(?:de|em|com)?\s*"
    rf"{_MATERIA}\b|"
    rf"\b(?:ajuda|ajudam|auxilia|auxiliam)\s+"
    rf"(?:(?:meu|minha|o|a)\s+)?"
    rf"(?:filho|filha|crianca|dependente|aluno|aluna)\s+"
    rf"(?:com|em|na|no)\s+{_MATERIA}\b|"
    rf"\b(?:tira|tiram|esclarece|esclarecem)\s+duvidas?\s+"
    rf"(?:de|em|sobre)\s+{_MATERIA}\b|"
    rf"\b(?:quero|procuro|busco|preciso\s+de)\s+"
    rf"(?:aulas?|reforco|ajuda|apoio|professor(?:a)?\s+particular)\s+"
    rf"(?:de|em|com)?\s*{_MATERIA}\b|"
    rf"\b(?:aulas?|cursos?|banca|reforco|ajuda|apoio|acompanhamento|"
    rf"recuperacao)\s+(?:de|em|com|para)\s+{_MATERIA}\b"
    rf")"
)


_PADRAO_RESPOSTA_PROFISSAO = re.compile(
    rf"^(?:"
    rf"(?:(?:sou|eu\s+sou|trabalho\s+como|atuo\s+como|"
    rf"minha\s+profissao\s+e|minha\s+profissao\s+eh)\s+)?"
    rf"(?:professor|professora|docente|explicador|explicadora)"
    rf"(?:\s+(?:particular|de\s+(?:reforco\s+escolar|cursinho|{_MATERIA})))?"
    rf"|(?:trabalho\s+com|dou|ministro)\s+aulas?\s+"
    rf"(?:particular(?:es)?|de\s+(?:reforco|{_MATERIA}))"
    rf")$"
)


_PADRAO_REFORCO_PARA_PESSOA = re.compile(
    r"\breforco\s+(?:para|pro|pra)\s+"
    r"(?:(?:o|a|meu|minha|um|uma)\s+)?"
    r"(?:filho|filha|crianca|dependente|aluno|aluna)\b"
)


_PADRAO_PREPARATORIO_ESPECIFICO = re.compile(
    r"(?:"
    r"\bpre\s+(?:enem|vestibular)\b|"
    r"\b(?:prepara|preparam|preparacao)\s+(?:o\s+aluno\s+)?"
    r"para\s+(?:o\s+)?(?:enem|vestibular)\b"
    r")"
)


def validar_duvida_reforco_escolar(texto):
    """Identifica procura por reforco ou outro servico escolar tradicional.

    O resultado apenas seleciona um tratamento de permanencia. Ele nao produz
    evento, nao escolhe transicao e nao interpreta a resposta da etapa atual.
    """
    texto_normalizado = _normalizar_texto(texto)

    if not texto_normalizado:
        return False

    # Uma declaracao ocupacional inequivoca nao e uma duvida sobre servico,
    # mesmo quando cita reforco, cursinho ou alguma materia.
    if _PADRAO_RESPOSTA_PROFISSAO.search(texto_normalizado):
        return False

    if _PADRAO_BANCA_NAO_ESCOLAR.search(texto_normalizado):
        return False

    if _PADRAO_SERVICO_ESCOLAR.search(texto_normalizado):
        return True

    if _PADRAO_PREPARATORIO_ESPECIFICO.search(texto_normalizado):
        return True

    if _PADRAO_REFORCO_PARA_PESSOA.search(texto_normalizado):
        return True

    if texto_normalizado in _RESPOSTAS_CURTAS_SERVICO_ESCOLAR:
        return True

    if _PADRAO_PERGUNTA_REFORCO_OU_BANCA.search(texto_normalizado):
        return True

    if _PADRAO_PERGUNTA_CURTA_MATERIA.fullmatch(texto_normalizado):
        return True

    return bool(_PADRAO_MATERIA_COM_INTENCAO.search(texto_normalizado))


def _normalizar_texto(texto):
    if not isinstance(texto, str):
        return ""

    texto_sem_acentos = normalizar_texto(texto)
    texto_sem_simbolos = re.sub(r"[^a-z0-9\s]", " ", texto_sem_acentos)
    return " ".join(texto_sem_simbolos.split())
