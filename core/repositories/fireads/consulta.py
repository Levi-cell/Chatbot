"""SQL FireAds; o orquestrador controla commits e as chamadas externas."""

from psycopg.errors import UniqueViolation
from psycopg.types.json import Jsonb

from core.repositories.atendimento.dependentes import inserir_dependente_para_conversa
from core.repositories.atendimento.followup import LockConversaPerdido


def proteger_mensagem_abertura(mensagem, cursor):
    """Só o dono atual da mensagem pode confirmar os dados obtidos na FireAds."""
    cursor.execute(
        """SELECT id_mensagem FROM chatbot.fila_mensagens
        WHERE id_mensagem=%s AND status='processing' AND retry_count=%s
          AND processing_started_at>clock_timestamp()-INTERVAL '120 seconds' FOR UPDATE""",
        (mensagem["id_mensagem"], mensagem["retry_count"]),
    )
    if cursor.fetchone() is None:
        raise LockConversaPerdido("Mensagem perdeu a reserva durante consulta FireAds")


def importar_dados_abertura(id_cliente, id_conversa, decisao, cursor):
    """Importa titular e destino juntos; conflito de e-mail não deixa dados parciais."""
    cursor.execute("SAVEPOINT fireads_importacao")
    try:
        dados = decisao["dados_titular"]
        cursor.execute(
            "UPDATE chatbot.cliente SET nome=%s,email=%s WHERE id_cliente=%s",
            (dados["nome"], dados["email"], id_cliente),
        )
        cursor.execute(
            "UPDATE chatbot.conversa SET status_dependente=%s WHERE id_conversa=%s",
            (decisao["status_dependente"], id_conversa),
        )
        if decisao["status_dependente"]:
            inserir_dependente_para_conversa(id_conversa, cursor)
    except UniqueViolation:
        cursor.execute("ROLLBACK TO SAVEPOINT fireads_importacao")
        return False
    finally:
        cursor.execute("RELEASE SAVEPOINT fireads_importacao")
    return True


def buscar_abertura(id_conversa, cursor):
    cursor.execute(
        """
        SELECT c.id_chat,c.id_cliente,c.id_unidade,c.id_etapa_atual,
               c.contexto_fireads,c.origem_fireads,i.id_integracao_fireads,
               i.url_dashbord,i.aba_destino,i.fuso_formularios,
               (u.status_pagamento IS TRUE AND i.integracao_ativa AND i.contrato_validado
                AND c.iniciou_em >= i.ativada_em) AS aplicavel
        FROM chatbot.conversa c JOIN chatbot.unidade u ON u.id_unidade=c.id_unidade
        LEFT JOIN chatbot.integracao_fireads i
          ON i.id_unidade=c.id_unidade WHERE c.id_conversa=%s;
    """,
        (id_conversa,),
    )
    row = cursor.fetchone()
    if row is None:
        raise ValueError("Conversa inexistente")
    return dict(
        zip(
            (
                "id_chat",
                "id_cliente",
                "id_unidade",
                "etapa",
                "contexto",
                "origem",
                "id_integracao",
                "url",
                "aba",
                "fuso",
                "aplicavel",
            ),
            row,
        )
    )


def aplicar_decisao(abertura, id_conversa, id_consulta, decisao, cursor):
    """Importação, snapshot da conversa e marcador são confirmados pelo fluxo."""
    decisao = dict(
        decisao,
        id_consulta=id_consulta,
        id_integracao=abertura["id_integracao"],
        concluida=True,
        id_conversa=id_conversa,
    )
    cursor.execute(
        """UPDATE chatbot.conversa SET origem_fireads=%s,contexto_fireads=%s
        WHERE id_conversa=%s AND id_etapa_atual IS NULL AND contexto_fireads IS NULL
          AND status_ativa AND finalizou_em IS NULL""",
        (decisao["origem"], Jsonb(decisao), id_conversa),
    )
    if cursor.rowcount != 1:
        raise LockConversaPerdido("A abertura já foi aplicada ou a conversa avançou")
    return decisao


def guardar_coletas(contexto, efeitos, cursor):
    """Captura dados aceitos nesta transação, nunca cadastro de conversa antiga."""
    if not contexto.get("contexto_fireads") or not efeitos:
        return
    campos = []
    if efeitos.get("cliente_nome_atualizado"):
        campos.append("nome")
    if efeitos.get("destino_dado") == "cliente":
        campos.append("idade")
    if efeitos.get("cliente_email_atualizado"):
        campos.append("email")
    if not campos:
        return
    cursor.execute(
        "SELECT nome,idade,email FROM chatbot.cliente WHERE id_cliente=%s",
        (contexto["id_cliente"],),
    )
    valores = dict(zip(("nome", "idade", "email"), cursor.fetchone()))
    dados = {c: valores[c] for c in campos}
    if "email" in campos:
        dados["resultado_email"] = efeitos["resultado_coleta_email"]
    cursor.execute(
        """UPDATE chatbot.conversa SET contexto_fireads=jsonb_set(
        contexto_fireads,'{dados_titular}',
        COALESCE(contexto_fireads->'dados_titular','{}'::jsonb) || %s)
        WHERE id_conversa=%s AND contexto_fireads IS NOT NULL;""",
        (Jsonb(dados), contexto["id_conversa"]),
    )
