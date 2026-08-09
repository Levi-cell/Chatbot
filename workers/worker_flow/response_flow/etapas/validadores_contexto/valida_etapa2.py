import re

from workers.worker_flow.response_flow.etapas.validadores_universais.validador_financeiro import (
    normalizar_texto,
)
from workers.worker_flow.response_flow.transicoes.eventos import (
    EVENTO_PARA_MIM,
    EVENTO_PARA_OUTRA_PESSOA,
)


OPCAO_PARA_MIM = EVENTO_PARA_MIM
OPCAO_PARA_OUTRA_PESSOA = EVENTO_PARA_OUTRA_PESSOA

TIPO_TRATAMENTO_CONTEXTO_INVALIDO = "opcao_invalida"

# O vocabulário fica sem acentos porque as entradas são normalizadas antes da
# classificação. Flexões no masculino, feminino e plural permanecem explícitas.
PARENTESCOS_ACEITOS = frozenset(
    {
        "afilhada",
        "afilhadas",
        "afilhado",
        "afilhados",
        "amiga",
        "amigas",
        "amigo",
        "amigos",
        "avo",
        "avos",
        "bebe",
        "bebes",
        "bisavo",
        "bisavos",
        "bisneta",
        "bisnetas",
        "bisneto",
        "bisnetos",
        "companheira",
        "companheiro",
        "colega",
        "colegas",
        "crianca",
        "criancas",
        "cunhada",
        "cunhadas",
        "cunhado",
        "cunhados",
        "enteada",
        "enteadas",
        "enteado",
        "enteados",
        "esposa",
        "esposo",
        "filha",
        "filhas",
        "filho",
        "filhos",
        "genro",
        "irma",
        "irmas",
        "irmao",
        "irmaos",
        "mae",
        "maes",
        "madrasta",
        "marido",
        "menina",
        "meninas",
        "menino",
        "meninos",
        "namorada",
        "namorado",
        "neta",
        "netas",
        "neto",
        "netos",
        "nora",
        "noiva",
        "noivo",
        "pai",
        "pais",
        "padrasto",
        "parceira",
        "parceiro",
        "prima",
        "primas",
        "primo",
        "primos",
        "sobrinha",
        "sobrinhas",
        "sobrinho",
        "sobrinhos",
        "sogra",
        "sogro",
        "tutora",
        "tutor",
        "tia",
        "tias",
        "tio",
        "tios",
    }
)

FRASES_PARA_MIM = frozenset(
    {
        "comigo",
        "e para mim",
        "e para eu",
        "e so para mim",
        "eu",
        "eu mesma",
        "eu mesmo",
        "eu propria",
        "eu proprio",
        "eu quero para mim",
        "o atendimento e para mim",
        "para eu",
        "para mim",
        "para mim mesma",
        "para mim mesmo",
        "para minha pessoa",
        "pra eu",
        "pra mim",
        "pra mim mesma",
        "pra mim mesmo",
        "apenas para mim",
        "sim e para mim",
        "sim para mim",
        "sim so para mim",
        "so eu",
        "so para mim",
        "somente para mim",
        "sou eu",
        "nao e para mim",
        "vai ser para mim",
        "quero para mim",
    }
)

_MODELOS_COM_PARENTESCO = (
    "{parentesco}",
    "meu {parentesco}",
    "minha {parentesco}",
    "meus {parentesco}",
    "minhas {parentesco}",
    "o meu {parentesco}",
    "a minha {parentesco}",
    "os meus {parentesco}",
    "as minhas {parentesco}",
    "para meu {parentesco}",
    "para minha {parentesco}",
    "para o meu {parentesco}",
    "para a minha {parentesco}",
    "para meus {parentesco}",
    "para minhas {parentesco}",
    "para os meus {parentesco}",
    "para as minhas {parentesco}",
    "pra meu {parentesco}",
    "pra minha {parentesco}",
    "pro meu {parentesco}",
    "pro minha {parentesco}",
    "pros meus {parentesco}",
    "pras minhas {parentesco}",
    "sim para meu {parentesco}",
    "sim para minha {parentesco}",
    "sim para o meu {parentesco}",
    "sim para a minha {parentesco}",
    "sim para os meus {parentesco}",
    "sim para as minhas {parentesco}",
    "sim e para meu {parentesco}",
    "sim e para minha {parentesco}",
    "sim e para o meu {parentesco}",
    "sim e para a minha {parentesco}",
    "sim pro meu {parentesco}",
    "sim pra minha {parentesco}",
    "sim e pro meu {parentesco}",
    "sim e pra minha {parentesco}",
    "quero para meu {parentesco}",
    "quero para minha {parentesco}",
    "quero para o meu {parentesco}",
    "quero para a minha {parentesco}",
    "quero para os meus {parentesco}",
    "quero para as minhas {parentesco}",
    "e para meu {parentesco}",
    "e para minha {parentesco}",
    "e para o meu {parentesco}",
    "e para a minha {parentesco}",
    "e para os meus {parentesco}",
    "e para as minhas {parentesco}",
    "e pro meu {parentesco}",
    "e pra minha {parentesco}",
    "nao para meu {parentesco}",
    "nao para minha {parentesco}",
    "nao e para meu {parentesco}",
    "nao e para minha {parentesco}",
    "nao e para o meu {parentesco}",
    "nao e para a minha {parentesco}",
    "nao e para mim e para meu {parentesco}",
    "nao e para mim e para minha {parentesco}",
    "nao e para mim e para o meu {parentesco}",
    "nao e para mim e para a minha {parentesco}",
    "sim eu quero e para meu {parentesco}",
    "sim eu quero e para minha {parentesco}",
    "sim eu quero e para o meu {parentesco}",
    "sim eu quero e para a minha {parentesco}",
    "sim eu quero e para os meus {parentesco}",
    "sim eu quero e para as minhas {parentesco}",
    "sim eu quero para meu {parentesco}",
    "sim eu quero para minha {parentesco}",
    "sim eu quero para o meu {parentesco}",
    "sim eu quero para a minha {parentesco}",
)

_DESTINOS_GENERICOS_DEPENDENTE = {
    "alguem",
    "alguem da minha familia",
    "alguem que depende de mim",
    "dependente",
    "outra pessoa",
    "um dependente",
    "um dependente meu",
    "um deficiente",
    "um familiar",
    "um idoso",
    "uma crianca",
    "uma dependente",
    "uma dependente minha",
    "uma deficiente",
    "uma familiar",
    "uma idosa",
    "uma pessoa com deficiencia",
    "uma pessoa da minha familia",
    "uma pessoa idosa",
    "uma pessoa",
}

_MODELOS_COM_DESTINO_GENERICO = (
    "{destino}",
    "para {destino}",
    "pra {destino}",
    "sim para {destino}",
    "sim e para {destino}",
    "sim pro {destino}",
    "sim pra {destino}",
    "sim e pro {destino}",
    "sim e pra {destino}",
    "quero para {destino}",
    "e para {destino}",
    "e pro {destino}",
    "e pra {destino}",
    "nao para {destino}",
    "nao e para {destino}",
    "nao e para mim e para {destino}",
    "sim eu quero e para {destino}",
    "o atendimento e para {destino}",
)

FRASES_PARA_DEPENDENTE = frozenset(
    {
        modelo.format(parentesco=parentesco)
        for parentesco in PARENTESCOS_ACEITOS
        for modelo in _MODELOS_COM_PARENTESCO
    }
    | {
        modelo.format(destino=destino)
        for destino in _DESTINOS_GENERICOS_DEPENDENTE
        for modelo in _MODELOS_COM_DESTINO_GENERICO
    }
    | {
        "quero para a minha",
        "quero para o meu",
    }
)


def validar_etapa2(conteudo_texto):
    """Classifica somente frases inequívocas sobre quem receberá atendimento.

    O clique no botão e o texto digitado chegam no mesmo campo. A normalização
    também tolera caixa, acentos, pontuação, espaços e vírgulas ausentes.
    """
    if not isinstance(conteudo_texto, str):
        return None

    resposta_normalizada = _normalizar_resposta(conteudo_texto)

    if resposta_normalizada in FRASES_PARA_MIM:
        return OPCAO_PARA_MIM

    if resposta_normalizada in FRASES_PARA_DEPENDENTE:
        return OPCAO_PARA_OUTRA_PESSOA

    return None


def _normalizar_resposta(texto):
    texto_sem_acento = normalizar_texto(texto)
    texto_sem_pontuacao = re.sub(
        r"[^a-z0-9\s]",
        " ",
        texto_sem_acento,
    )
    return " ".join(texto_sem_pontuacao.split())
