"""Consulta autoritativa do acesso; nunca recebe uma unidade escolhida pelo cliente."""

from dataclasses import dataclass


@dataclass(frozen=True)
class AcessoMonitoramento:
    id_usuario: int
    id_unidade: int
    nome_unidade: str


def buscar_acesso_monitoramento(
    id_usuario,
    cursor,
    *,
    id_conversa=None,
    id_mensagem=None,
):
    """Le o usuario vinculado na unidade e valida a conta e os recursos solicitados.

    A identidade vem da sessao Django, nunca do corpo/URL da requisicao.
    Mensagens sao autorizadas pela unidade da conversa, nao pelo cliente global.
    Quando conversa e mensagem sao informadas, ambas devem pertencer ao mesmo
    atendimento. Nao ha bypass para contas administrativas nem cache do vinculo.
    """
    identificadores = (id_usuario, id_conversa, id_mensagem)
    if id_usuario is None or any(
        valor is not None and (type(valor) is not int or valor <= 0)
        for valor in identificadores
    ):
        return None

    consulta = """
        SELECT u.id_usuario_monitoramento, u.id_unidade, u.nome_unidade
        FROM chatbot.unidade AS u
        JOIN chatbot.auth_user AS usuario ON usuario.id = u.id_usuario_monitoramento
        WHERE u.id_usuario_monitoramento = %s
          AND usuario.is_active = TRUE
          AND usuario.is_staff = FALSE
          AND usuario.is_superuser = FALSE
    """
    parametros = [id_usuario]

    if id_conversa is not None:
        consulta += """
          AND EXISTS (
              SELECT 1 FROM chatbot.conversa AS c
              WHERE c.id_conversa = %s AND c.id_unidade = u.id_unidade
          )
        """
        parametros.append(id_conversa)

    if id_mensagem is not None:
        consulta += """
          AND EXISTS (
              SELECT 1
              FROM chatbot.historico_mensagens AS h
              JOIN chatbot.conversa AS c ON c.id_conversa = h.id_conversa
              WHERE h.id_mensagem = %s AND c.id_unidade = u.id_unidade
        """
        parametros.append(id_mensagem)
        if id_conversa is not None:
            consulta += " AND h.id_conversa = %s"
            parametros.append(id_conversa)
        consulta += " )"

    cursor.execute(consulta, tuple(parametros))
    linha = cursor.fetchone()
    return AcessoMonitoramento(*linha) if linha else None
