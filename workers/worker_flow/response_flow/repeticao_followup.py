"""Retoma após follow-up: repete a etapa, exceto a 8, que avança para a 9."""

from core.integrations.whatsapp.messages.componentes_compartilhados import (
    montar_texto_com_cabecalho,
)
from core.integrations.whatsapp.messages.tratamentos.retorno_followup import (
    montar_saudacao_retomada_followup,
)
from core.integrations.whatsapp.pywa_functions.cliente import (
    aplicar_prefixo_mensagem_bot,
    usar_prefixo_mensagem_bot,
)
from core.integrations.whatsapp.pywa_functions.pywa_senders import (
    etapa1,
    etapa2,
    etapa3,
    etapa4,
    etapa5,
    etapa6,
    etapa7,
    etapa9,
    etapa10,
    etapa11,
    etapa12,
    etapa13,
    etapa14,
    etapa15,
    etapa16,
    etapa17,
    etapa18,
    etapa19,
    etapa20,
    etapa21,
)

from workers.worker_flow.response_flow.etapas.resolver_etapa8 import resolve_etapa8
from workers.worker_flow.response_flow.transicoes.eventos import (
    ETAPA_1_NOME_CLIENTE,
    ETAPA_2_DESTINO_ATENDIMENTO,
    ETAPA_3_CONFIRMACAO_DESTINO,
    ETAPA_4_PROFISSAO,
    ETAPA_5_NOME_DEPENDENTE,
    ETAPA_6_IDADE_ALUNO,
    ETAPA_7_OFERTA_AULA,
    ETAPA_8_OFERTA_ADIADA,
    ETAPA_9_RETORNO_OFERTA,
    ETAPA_10_EMAIL,
    ETAPA_11_INTRODUCAO_TRIAGEM,
    ETAPA_12_TRIAGEM_PERGUNTA_1,
    ETAPA_13_TRIAGEM_PERGUNTA_2,
    ETAPA_14_TRIAGEM_PERGUNTA_3,
    ETAPA_15_TRIAGEM_PERGUNTA_4,
    ETAPA_16_TRIAGEM_PERGUNTA_5,
    ETAPA_17_TRIAGEM_PERGUNTA_6,
    ETAPA_18_AGENDAMENTO,
    ETAPA_19_PESQUISA_SATISFACAO,
    ETAPA_20_DECISAO_COMENTARIO,
    ETAPA_21_COMENTARIO_SATISFACAO,
)

SENDERS_SIMPLES = {
    ETAPA_4_PROFISSAO: etapa4.enviar_etapa4,
    ETAPA_5_NOME_DEPENDENTE: etapa5.enviar_etapa5,
    ETAPA_10_EMAIL: etapa10.enviar_etapa10,
    ETAPA_20_DECISAO_COMENTARIO: etapa20.enviar_etapa20,
    ETAPA_21_COMENTARIO_SATISFACAO: etapa21.enviar_etapa21,
}
SENDERS_TRIAGEM = {
    ETAPA_12_TRIAGEM_PERGUNTA_1: (
        etapa12.enviar_etapa12_cliente,
        etapa12.enviar_etapa12_dependente,
    ),
    ETAPA_13_TRIAGEM_PERGUNTA_2: (
        etapa13.enviar_etapa13_cliente,
        etapa13.enviar_etapa13_dependente,
    ),
    ETAPA_14_TRIAGEM_PERGUNTA_3: (
        etapa14.enviar_etapa14_cliente,
        etapa14.enviar_etapa14_dependente,
    ),
    ETAPA_15_TRIAGEM_PERGUNTA_4: (
        etapa15.enviar_etapa15_cliente,
        etapa15.enviar_etapa15_dependente,
    ),
    ETAPA_16_TRIAGEM_PERGUNTA_5: (
        etapa16.enviar_etapa16_cliente,
        etapa16.enviar_etapa16_dependente,
    ),
    ETAPA_17_TRIAGEM_PERGUNTA_6: (
        etapa17.enviar_etapa17_cliente,
        etapa17.enviar_etapa17_dependente,
    ),
}


def _texto(dados, chave):
    valor = dados.get(chave)
    if not isinstance(valor, str) or not valor.strip():
        raise ValueError(f"Dado persistido ausente para repetição: {chave}")
    return valor.strip()


def _selecionar_sender(etapa, dados):
    dependente = dados.get("status_dependente")
    if not isinstance(dependente, bool):
        raise ValueError("Destino de atendimento ausente para repetição")
    if etapa in SENDERS_SIMPLES:
        return SENDERS_SIMPLES[etapa], ()
    if etapa in SENDERS_TRIAGEM:
        titular, dp = SENDERS_TRIAGEM[etapa]
        if not dependente:
            return titular, ()
        idade = dados.get("idade_dependente")
        if type(idade) is not int or not 4 <= idade < 100:
            raise ValueError("Idade do dependente inválida para triagem")
        return dp, (_texto(dados, "nome_dependente"), idade)
    if etapa == ETAPA_1_NOME_CLIENTE:
        return etapa1.enviar_etapa1, tuple(
            _texto(dados, k) for k in ("nome_unidade", "nome_agente", "genero")
        )
    if etapa == ETAPA_2_DESTINO_ATENDIMENTO:
        return etapa2.enviar_etapa2, (_texto(dados, "nome_titular"),)
    if etapa == ETAPA_3_CONFIRMACAO_DESTINO:
        return etapa3.enviar_etapa3, (dependente,)
    if etapa == ETAPA_6_IDADE_ALUNO:
        return (
            (etapa6.enviar_etapa6_dependente, (_texto(dados, "nome_dependente"),))
            if dependente
            else (etapa6.enviar_etapa6_cliente, ())
        )
    if etapa == ETAPA_7_OFERTA_AULA:
        return (
            (
                etapa7.enviar_etapa7_dependente,
                (dados.get("nome_titular"), _texto(dados, "nome_dependente")),
            )
            if dependente
            else (etapa7.enviar_etapa7_cliente, (_texto(dados, "nome_titular"),))
        )
    if etapa == ETAPA_9_RETORNO_OFERTA:
        nome_titular = _texto(dados, "nome_titular")
        return (
            (
                etapa9.enviar_etapa9_dependente,
                (nome_titular, _texto(dados, "nome_dependente")),
            )
            if dependente
            else (etapa9.enviar_etapa9_cliente, (nome_titular,))
        )
    if etapa == ETAPA_11_INTRODUCAO_TRIAGEM:
        return etapa11.enviar_etapa11, (
            dependente,
            _texto(dados, "nome_dependente") if dependente else None,
        )
    if etapa == ETAPA_18_AGENDAMENTO:
        return etapa18.enviar_etapa18, (
            _texto(dados, "link_agendamento"),
            _texto(dados, "nome_dependente") if dependente else None,
        )
    if etapa == ETAPA_19_PESQUISA_SATISFACAO:
        return etapa19.enviar_etapa19, (_texto(dados, "nome_titular"),)
    raise ValueError(f"Etapa não repetível: {etapa}")


def enviar_repeticao_followup(contexto):
    resposta = contexto.get("resposta_bot_para_mensagem_atual")
    if resposta:
        return {
            "enviou": False,
            "resposta_ja_existia": True,
            "id_hash_msg_bot": resposta["id_hash_msg"],
            "id_etapa_resultante": resposta.get("id_etapa", contexto["id_etapa_atual"]),
        }
    mensagem = contexto["mensagem_cliente_atual"]
    # Na etapa 1, o nome ainda não foi coletado neste atendimento. O cadastro
    # pode ter um nome de conversa anterior e não autoriza essa personalização.
    nome_titular = (
        None
        if contexto["id_etapa_atual"] == ETAPA_1_NOME_CLIENTE
        else contexto["dados_repeticao"].get("nome_titular")
    )
    saudacao = montar_saudacao_retomada_followup(nome_titular)
    # Fora da triagem, a etapa possui uma repetição neutra. As perguntas
    # canônicas da triagem já são iguais na apresentação e na reapresentação.
    opcoes_envio = (
        {} if contexto["id_etapa_atual"] in SENDERS_TRIAGEM else {"repeticao": True}
    )
    with usar_prefixo_mensagem_bot(saudacao):
        if contexto["id_etapa_atual"] == ETAPA_8_OFERTA_ADIADA:
            envio = _enviar_retorno_etapa8(contexto, saudacao)
        else:
            sender, extras = _selecionar_sender(
                contexto["id_etapa_atual"], contexto["dados_repeticao"]
            )
            envio = sender(
                mensagem["cliente_telefone"],
                mensagem["id_phone_unidade"],
                *extras,
                **opcoes_envio,
            )
    # O cabeçalho já foi ao WhatsApp no corpo. O histórico recebe o mesmo texto.
    texto = envio["mensagem_bot"]
    if envio.get("cabecalho_mensagem"):
        texto = montar_texto_com_cabecalho(texto, envio["cabecalho_mensagem"])
    texto = aplicar_prefixo_mensagem_bot(texto, saudacao)
    resultado = {
        "enviou": envio["enviou"],
        "resposta_ja_existia": False,
        "id_hash_msg_bot": envio["id_hash_msg_bot"],
        "mensagem_bot": texto,
        "tipo_mensagem": envio["tipo_mensagem"],
        "id_etapa_resultante": envio["id_etapa_resultante"],
    }
    if contexto["id_etapa_atual"] == ETAPA_8_OFERTA_ADIADA:
        resultado.update(
            id_etapa_origem_transicao=envio["id_etapa_origem_transicao"],
            evento_transicao=envio["evento_transicao"],
        )
    return resultado


def _enviar_retorno_etapa8(contexto, saudacao):
    """Qualquer reação retoma a oferta; não interpreta aceite nem envia a etapa 8."""
    dados = contexto["dados_repeticao"]
    dependente = dados.get("status_dependente")
    if not isinstance(dependente, bool):
        raise ValueError("Destino de atendimento ausente para retorno da etapa 8")
    contexto_retorno = dict(
        contexto,
        status_dependente=dependente,
        nome_titular=_texto(dados, "nome_titular"),
        nome_dependente=_texto(dados, "nome_dependente") if dependente else None,
        # Suprime a saudação própria da etapa 9; o prefixo de follow-up já a acolhe.
        saudacao_retorno=saudacao,
    )
    return resolve_etapa8(contexto_retorno)
