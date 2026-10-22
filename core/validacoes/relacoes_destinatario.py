"""Relações explícitas de destinatário; faixa etária não define participante."""

import re


# Preservar as chaves históricas: filho/filha, mãe/pai e relações diferentes
# continuam distinguindo inscrições na comparação com o dashboard.
RELACOES = frozenset({
    'pai', 'pais', 'mae', 'maes', 'avo', 'avos', 'bisavo', 'bisavos',
    'filho', 'filha', 'filhos', 'filhas', 'neto', 'neta', 'netos', 'netas',
    'bisneto', 'bisneta', 'bisnetos', 'bisnetas', 'irmao', 'irma', 'irmaos', 'irmas',
    'tio', 'tia', 'tios', 'tias', 'sobrinho', 'sobrinha', 'sobrinhos', 'sobrinhas',
    'marido', 'esposa', 'esposo', 'companheiro', 'companheira',
    'sogro', 'sogra', 'sogros', 'sogras', 'primo', 'prima', 'primos', 'primas',
    'enteado', 'enteada', 'enteados', 'enteadas', 'padrasto', 'madrasta',
    'cunhado', 'cunhada', 'cunhados', 'cunhadas', 'genro', 'genros', 'nora', 'noras',
    'afilhado', 'afilhada', 'afilhados', 'afilhadas', 'padrinho', 'madrinha',
    'namorado', 'namorada', 'noivo', 'noiva', 'parceiro', 'parceira',
    'amigo', 'amiga', 'amigos', 'amigas', 'conhecido', 'conhecida',
    'conhecidos', 'conhecidas', 'colega', 'colegas', 'vizinho', 'vizinha',
    'vizinhos', 'vizinhas', 'familiar', 'familiares',
})

_PESSOA = '(?:' + '|'.join(sorted(RELACOES, key=lambda s: (-len(s), s))) + (
    r'|outra pessoa|outras pessoas|dependente|mim|titular)'
)
_QUALIFICADOR = (
    r'(?:(?:para|pra|pro|pros|pras)\s+)?'
    r'(?:(?:o|a|os|as|um|uma|uns|umas)\s+)?'
    r'(?:(?:meu|minha|meus|minhas)\s+)?'
)
_RESPOSTA = re.compile(
    rf'{_QUALIFICADOR}{_PESSOA}(?:\s+(?:e|ou)\s+{_QUALIFICADOR}{_PESSOA})*'
)
_INICIO = re.compile(r'^(?:para|pra|pro|pros|pras|meu|minha|meus|minhas)\b|'
                     r'^(?:o|a|os|as)\s+(?:meu|minha|meus|minhas)\b')


def destinatario_sem_rotulo(texto_normalizado):
    """Aceita respostas curtas completas, sem confundir menção com destinatário."""
    return bool(_INICIO.match(texto_normalizado) and _RESPOSTA.fullmatch(texto_normalizado))
