from workers.worker_flow.response_flow.transicoes.eventos import (
    EVENTO_PARA_MIM,
    EVENTO_PARA_OUTRA_PESSOA,
)


OPCAO_PARA_MIM = EVENTO_PARA_MIM
OPCAO_PARA_OUTRA_PESSOA = EVENTO_PARA_OUTRA_PESSOA

TIPO_TRATAMENTO_CONTEXTO_INVALIDO = "opcao_invalida"

_OPCOES_ACEITAS = {
    "para mim": OPCAO_PARA_MIM,
    "para outra pessoa": OPCAO_PARA_OUTRA_PESSOA,
}


def validar_etapa2(conteudo_texto):
    """
    Aceita somente os dois textos exibidos nos botoes da etapa 2.

    O webhook converte a resposta interativa em conteudo_texto. Por isso,
    clique e texto digitado percorrem exatamente a mesma validacao.
    """
    if not isinstance(conteudo_texto, str):
        return None

    texto_normalizado = " ".join(
        conteudo_texto.strip().casefold().split()
    )

    return _OPCOES_ACEITAS.get(texto_normalizado)
