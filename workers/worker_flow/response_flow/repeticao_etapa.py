"""Seleção do sender neutro compartilhado por tratamentos e retomadas."""

from core.integrations.whatsapp.messages.contato_comercial import montar_mensagem_contato_comercial
from core.validacoes.turno import validar_turno
from core.integrations.whatsapp.pywa_functions.pywa_senders import etapa18, etapa19

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
    etapa20,
    etapa21,
    etapa22,
    etapa23,
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
    ETAPA_18_ESCOLHA_TURNO,
    ETAPA_19_ENCAMINHAMENTO_COMERCIAL,
    ETAPA_20_AGENDAMENTO,
    ETAPA_21_PESQUISA_SATISFACAO,
    ETAPA_22_DECISAO_COMENTARIO,
    ETAPA_23_COMENTARIO_SATISFACAO,
)

SENDERS_SIMPLES = {
    ETAPA_4_PROFISSAO: etapa4.enviar_etapa4,
    ETAPA_5_NOME_DEPENDENTE: etapa5.enviar_etapa5,
    ETAPA_10_EMAIL: etapa10.enviar_etapa10,
    ETAPA_22_DECISAO_COMENTARIO: etapa22.enviar_etapa22,
    ETAPA_23_COMENTARIO_SATISFACAO: etapa23.enviar_etapa23,
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


def selecionar_sender_repeticao(etapa, dados):
    dependente = dados.get("status_dependente")
    if not isinstance(dependente, bool):
        raise ValueError("Destino de atendimento ausente para repetição")
    if etapa == ETAPA_8_OFERTA_ADIADA:
        return etapa8.enviar_etapa8, (dados.get("link_instagram"),)
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
    if etapa == ETAPA_18_ESCOLHA_TURNO:
        return etapa18.enviar_etapa18, (
            _texto(dados, "nome_dependente") if dependente else None,
        )
    if etapa == ETAPA_19_ENCAMINHAMENTO_COMERCIAL:
        # Suporte à retomada já registrada, sem ampliar a elegibilidade proativa.
        turno = validar_turno(dados.get("turno"))
        nome_dependente = _texto(dados, "nome_dependente") if dependente else None
        texto = montar_mensagem_contato_comercial(
            nome_agente=_texto(dados, "nome_agente"),
            genero_agente=_texto(dados, "genero"),
            nome_cliente=_texto(dados, "nome_titular"),
            nome_dependente=nome_dependente,
            idade_aluno=dados.get(
                "idade_dependente" if dependente else "idade_cliente"
            ),
            turno=turno,
        )
        return etapa19.enviar_etapa19, (
            _texto(dados, "numero_comercial"),
            texto,
            nome_dependente,
        )
    if etapa == ETAPA_20_AGENDAMENTO:
        return etapa20.enviar_etapa20, (
            _texto(dados, "link_agendamento"),
            _texto(dados, "nome_dependente") if dependente else None,
        )
    if etapa == ETAPA_21_PESQUISA_SATISFACAO:
        return etapa21.enviar_etapa21, (_texto(dados, "nome_titular"),)
    raise ValueError(f"Etapa não repetível: {etapa}")

