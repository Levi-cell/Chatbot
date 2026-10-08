"""Seleciona os dados da pessoa atendida para a mensagem do botão comercial."""

from core.integrations.whatsapp.messages.contato_comercial import (
    montar_mensagem_contato_comercial,
)


def preparar_mensagem_comercial(contexto, *, idade_aluno=None, turno=None):
    dependente = contexto.get("status_dependente")
    if not isinstance(dependente, bool):
        raise ValueError("Destino indefinido para contato comercial")
    nome_dependente = contexto.get("nome_dependente") if dependente else None
    if dependente and not nome_dependente:
        raise ValueError("Dependente sem nome para contato comercial")
    if idade_aluno is None:
        idade_aluno = contexto.get(
            "idade_dependente" if dependente else "idade_cliente"
        )
    return montar_mensagem_contato_comercial(
        nome_agente=contexto.get("nome_agente_unidade"),
        genero_agente=contexto.get("genero_agente_unidade"),
        nome_cliente=contexto.get("nome_cliente"),
        idade_aluno=idade_aluno,
        nome_dependente=nome_dependente,
        turno=turno,
    )
