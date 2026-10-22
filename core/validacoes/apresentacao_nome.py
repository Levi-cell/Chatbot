"""Identifica apresentações explícitas; não infere nomes de profissão ou local."""

import re
import unicodedata


APRESENTACAO = re.compile(
    r"^\s*(?:(?:olá|ola|oi|bom dia|boa tarde|boa noite)[\s!,.:-]+)*"
    r"(?:(?:eu\s+)?me\s+chamo|(?:o\s+)?meu\s+nome\s+[eé]|"
    r"(?:eu\s+)?sou(?:\s+[oa])?|pode\s+me\s+chamar\s+de|"
    r"aqui\s+(?:quem\s+fala\s+)?[eé](?:\s+[oa])?)\s+"
    r"(?P<nome>[^\n,.!?;:|]+)", re.IGNORECASE,
)
CONTINUACAO = re.compile(
    r"\s+(?:e|vim|quero|queria|gostaria|tenho|estou|sou|preciso|moro)\b.*$",
    re.IGNORECASE,
)
# Sem contexto de pergunta sobre nome, estas apresentações descrevem papéis,
# condições ou localização. Os campos estruturados de formulário são independentes.
NAO_NOMES = {
    'de', 'da', 'do', 'um', 'uma', 'seu', 'sua', 'eu', 'voce', 'interessado',
    'interessada', 'professor', 'professora', 'aposentado', 'aposentada', 'aluno',
    'aluna', 'estudante', 'medico', 'medica', 'advogado', 'advogada', 'engenheiro',
    'engenheira', 'programador', 'programadora', 'psicologo', 'psicologa',
    'nutricionista', 'pai', 'mae', 'filho', 'filha', 'avo', 'responsavel',
    'cliente', 'autonomo', 'autonoma', 'empresario', 'empresaria', 'casado',
    'casada', 'idoso', 'idosa', 'adulto', 'adulta', 'crianca', 'deficiente',
}


def extrair_apresentacao_nome(linha):
    match = APRESENTACAO.match(linha)
    if not match:
        return None
    candidato = CONTINUACAO.sub('', match['nome']).strip()
    palavras = re.findall(r"[^\W\d_]+(?:[-'][^\W\d_]+)*", candidato, re.UNICODE)
    if not palavras or re.search(r'\d|@', candidato):
        return None
    primeiro = ''.join(c for c in unicodedata.normalize('NFKD', palavras[0].casefold())
                       if not unicodedata.combining(c))
    return None if primeiro in NAO_NOMES else candidato
