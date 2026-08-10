import re
import unicodedata

from workers.worker_flow.response_flow.etapas.validadores_universais.validador_reforco_escolar import (
    validar_duvida_reforco_escolar,
)


_SERVICO_ESCOLAR = (
    r"(?:banca(?:\s+escolar)?|cursinho|supletivo|eja|encceja|"
    r"reforco(?:\s+escolar)?)"
)
_ARTIGO_OPCIONAL = r"(?:(?:um|uma|o|a)\s+)?"
_PREPOSICAO_VINCULO = r"(?:de|do|da|em|no|na|num|numa|para)"


# Na etapa 4, o mesmo vocabulário pode descrever o local de trabalho do
# cliente. Os padrões são ancorados em declarações explícitas de vínculo
# profissional para não transformar perguntas sobre o Supera em profissões.
_PADROES_VINCULO_PROFISSIONAL = (
    re.compile(
        rf"^(?:eu\s+)?(?:trabalho|atuo)\s+"
        rf"(?:"
        rf"{_PREPOSICAO_VINCULO}\s+{_ARTIGO_OPCIONAL}{_SERVICO_ESCOLAR}"
        rf"(?:\s+(?:como|na\s+funcao\s+de)\s+.+)?|"
        rf"como\s+.+\s+{_PREPOSICAO_VINCULO}\s+"
        rf"{_ARTIGO_OPCIONAL}{_SERVICO_ESCOLAR}"
        rf")$"
    ),
    re.compile(
        rf"^(?:eu\s+)?sou\s+.+\s+{_PREPOSICAO_VINCULO}\s+"
        rf"{_ARTIGO_OPCIONAL}{_SERVICO_ESCOLAR}$"
    ),
    re.compile(
        rf"^(?:professor|professora|dono|dona|diretor|diretora|"
        rf"tecnico|tecnica|coordenador|coordenadora|gestor|gestora|"
        rf"pedagogo|pedagoga|psicopedagogo|psicopedagoga|instrutor|"
        rf"instrutora|monitor|monitora|secretario|secretaria|"
        rf"recepcionista|auxiliar|administrativo|administrativa)\s+"
        rf"{_PREPOSICAO_VINCULO}\s+{_ARTIGO_OPCIONAL}{_SERVICO_ESCOLAR}$"
    ),
)


def validar_duvida_reforco_escolar_etapa4(texto):
    """Preserva profissões sem enfraquecer dúvidas reais da etapa 4."""
    if _declaracao_vinculo_profissional(texto):
        return False

    return validar_duvida_reforco_escolar(texto)


def _declaracao_vinculo_profissional(texto):
    if not isinstance(texto, str) or "?" in texto:
        return False

    texto_normalizado = _normalizar_texto(texto)
    if not texto_normalizado:
        return False

    return any(
        padrao.fullmatch(texto_normalizado)
        for padrao in _PADROES_VINCULO_PROFISSIONAL
    )


def _normalizar_texto(texto):
    texto_decomposto = unicodedata.normalize("NFD", texto.casefold())
    texto_sem_acentos = "".join(
        caractere
        for caractere in texto_decomposto
        if unicodedata.category(caractere) != "Mn"
    )
    texto_sem_simbolos = re.sub(r"[^\w\s]", " ", texto_sem_acentos)
    return " ".join(texto_sem_simbolos.replace("_", " ").split())
