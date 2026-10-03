"""Texto que o cliente pode enviar ao consultor ao abrir o botão comercial."""

from core.validacoes.turno import ROTULOS_TURNO, validar_turno


def montar_mensagem_contato_comercial(
    *,
    nome_agente,
    genero_agente,
    nome_cliente,
    idade_aluno,
    nome_dependente=None,
    turno=None,
):
    if genero_agente not in {"masculino", "feminino"}:
        raise ValueError("Gênero do agente ausente para contato comercial")
    nomes = (nome_agente, nome_cliente)
    if any(not isinstance(nome, str) or not nome.strip() for nome in nomes):
        raise ValueError("Nome do agente e do cliente são necessários")
    if type(idade_aluno) is not int or idade_aluno <= 0:
        raise ValueError("Idade do participante ausente para contato comercial")
    artigo = "a" if genero_agente == "feminino" else "o"
    inicio = f"Olá, venho do atendimento com {artigo} {nome_agente.strip()}, me chamo {nome_cliente.strip()}"
    preferencia = (
        f" no turno da {ROTULOS_TURNO[validar_turno(turno)]}"
        if turno is not None
        else ""
    )
    if nome_dependente:
        # Não há gênero do dependente no cadastro; não inferir 'ele' ou 'ela'.
        return (
            f"{inicio} e gostaria de reservar uma demonstração prática para "
            f"{nome_dependente.strip()}, que tem {idade_aluno} anos."
            + (
                f" Prefiro o turno da {ROTULOS_TURNO[validar_turno(turno)]}."
                if turno is not None
                else ""
            )
        )
    return (
        f"{inicio}, tenho {idade_aluno} anos e gostaria de reservar "
        f"uma demonstração prática para mim{preferencia}."
    )
