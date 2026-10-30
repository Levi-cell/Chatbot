"""Endereço cadastrado, sem completar dados ausentes por inferência."""

from .composicao import compor_tratamento


MENSAGEM_ENDERECO = "Nossa unidade fica localizada na {endereco}\n\n"
MENSAGEM_HORARIOS = "Nosso horário de funcionamento é de {horarios}\n\n"
MENSAGEM_SEM_ENDERECO = (
    "Ainda não tenho o endereço desta unidade cadastrado aqui. "
    "Nossa equipe poderá confirmar essa informação para você.\n\n"
)


def _frase(texto):
    texto = texto.strip()
    return texto if texto.endswith(('.', '!', '?')) else texto + '.'


def montar_mensagem_tratamento_endereco(
    mensagem_repeticao, endereco=None, horarios_funcionamento=None
):
    orientacao = (
        MENSAGEM_ENDERECO.format(endereco=_frase(endereco))
        if isinstance(endereco, str) and endereco.strip()
        else MENSAGEM_SEM_ENDERECO
    )
    if isinstance(horarios_funcionamento, str) and horarios_funcionamento.strip():
        orientacao += MENSAGEM_HORARIOS.format(horarios=_frase(horarios_funcionamento))
    return compor_tratamento(orientacao, mensagem_repeticao)
