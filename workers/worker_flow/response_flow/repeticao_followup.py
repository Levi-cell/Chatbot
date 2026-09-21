"""Repete conteúdo de etapa sem interpretar a reação nem resolver transições."""

from core.integrations.whatsapp.messages.componentes_compartilhados import (
    montar_texto_com_cabecalho,
)
from core.integrations.whatsapp.messages.followup_messages import (
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
    etapa8,
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
    ETAPA_11_INTRODUCAO_TRIAGEM: etapa11.enviar_etapa11,
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
        return etapa2.enviar_etapa2, (_texto(dados, "nome_cliente"),)
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
            (etapa7.enviar_etapa7_dependente, (_texto(dados, "nome_dependente"),))
            if dependente
            else (etapa7.enviar_etapa7_cliente, (_texto(dados, "nome_cliente"),))
        )
    if etapa == ETAPA_8_OFERTA_ADIADA:
        return etapa8.enviar_etapa8, (dados.get("link_instagram"),)
    if etapa == ETAPA_9_RETORNO_OFERTA:
        nome = _texto(dados, "nome_cliente")
        return (
            (etapa9.enviar_etapa9_dependente, (nome, _texto(dados, "nome_dependente")))
            if dependente
            else (etapa9.enviar_etapa9_cliente, (nome,))
        )
    if etapa == ETAPA_18_AGENDAMENTO:
        return etapa18.enviar_etapa18, (_texto(dados, "link_agendamento"),)
    if etapa == ETAPA_19_PESQUISA_SATISFACAO:
        return etapa19.enviar_etapa19, (_texto(dados, "nome_cliente"),)
    raise ValueError(f"Etapa não repetível: {etapa}")


def enviar_repeticao_followup(contexto):
    resposta = contexto.get("resposta_bot_para_mensagem_atual")
    if resposta:
        return {
            "enviou": False,
            "resposta_ja_existia": True,
            "id_hash_msg_bot": resposta["id_hash_msg"],
            "id_etapa_resultante": contexto["id_etapa_atual"],
        }
    sender, extras = _selecionar_sender(
        contexto["id_etapa_atual"], contexto["dados_repeticao"]
    )
    mensagem = contexto["mensagem_cliente_atual"]
    # Na etapa 1, o nome ainda não foi coletado neste atendimento. O cadastro
    # pode ter um nome de conversa anterior e não autoriza essa personalização.
    nome_saudacao = (
        None
        if contexto["id_etapa_atual"] == ETAPA_1_NOME_CLIENTE
        else contexto["dados_repeticao"].get("nome_cliente")
    )
    saudacao = montar_saudacao_retomada_followup(
        nome_saudacao
    )
    # O prefixo da retomada substitui a saudação própria da oferta da etapa 9.
    opcoes_envio = (
        {"incluir_saudacao": False}
        if contexto["id_etapa_atual"] == ETAPA_9_RETORNO_OFERTA
        else {}
    )
    with usar_prefixo_mensagem_bot(saudacao):
        envio = sender(
            mensagem["cliente_telefone"], mensagem["id_phone_unidade"],
            *extras, **opcoes_envio,
        )
    # O cabeçalho já foi ao WhatsApp no corpo. O histórico recebe o mesmo texto.
    texto = envio["mensagem_bot"]
    if envio.get("cabecalho_mensagem"):
        texto = montar_texto_com_cabecalho(texto, envio["cabecalho_mensagem"])
    texto = aplicar_prefixo_mensagem_bot(texto, saudacao)
    return {
        "enviou": envio["enviou"],
        "resposta_ja_existia": False,
        "id_hash_msg_bot": envio["id_hash_msg_bot"],
        "mensagem_bot": texto,
        "tipo_mensagem": envio["tipo_mensagem"],
        "id_etapa_resultante": contexto["id_etapa_atual"],
    }
