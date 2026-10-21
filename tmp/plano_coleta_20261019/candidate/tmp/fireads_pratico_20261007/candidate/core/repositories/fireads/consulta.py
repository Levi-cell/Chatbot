"""SQL FireAds; o orquestrador controla commits e as chamadas externas."""

from psycopg.types.json import Jsonb


def buscar_abertura(id_conversa, cursor):
    cursor.execute(
        """
        SELECT c.id_chat,c.id_cliente,c.id_unidade,c.id_etapa_atual,
               c.contexto_fireads,c.origem_fireads,i.id_integracao_fireads,
               i.url_dashbord,i.aba_google,i.aba_meta,i.fuso_formularios,
               (i.integracao_ativa AND c.iniciou_em >= i.ativada_em) AS aplicavel
        FROM chatbot.conversa c LEFT JOIN chatbot.integracao_fireads i
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
                "aba_google",
                "aba_meta",
                "fuso",
                "aplicavel",
            ),
            row,
        )
    )


def reservar_consulta(abertura, id_conversa, cursor):
    cursor.execute(
        """
        INSERT INTO chatbot.consulta_fireads
          (id_chat,id_unidade,id_integracao_fireads,id_conversa_referencia)
        VALUES (%s,%s,%s,%s)
        ON CONFLICT (id_chat) DO UPDATE SET
          id_integracao_fireads=EXCLUDED.id_integracao_fireads,
          id_conversa_referencia=EXCLUDED.id_conversa_referencia,
          consulta_concluida=FALSE,resultado='pendente',dados=NULL,
          consultado_em=NULL,atualizado_em=clock_timestamp()
        RETURNING id_consulta;
    """,
        (
            abertura["id_chat"],
            abertura["id_unidade"],
            abertura["id_integracao"],
            id_conversa,
        ),
    )
    return cursor.fetchone()[0]


def concluir_consulta(abertura, id_conversa, id_consulta, decisao, cursor):
    cursor.execute(
        """
        UPDATE chatbot.consulta_fireads SET consulta_concluida=TRUE,
          resultado=%s,dados=%s,consultado_em=clock_timestamp(),
          atualizado_em=clock_timestamp()
        WHERE id_consulta=%s AND id_chat=%s AND id_conversa_referencia=%s;
    """,
        (
            decisao["resultado"],
            Jsonb(decisao),
            id_consulta,
            abertura["id_chat"],
            id_conversa,
        ),
    )
    if cursor.rowcount != 1:
        raise ValueError("Consulta pertence a outra conversa")
    decisao = dict(
        decisao,
        id_consulta=id_consulta,
        id_integracao=abertura["id_integracao"],
        concluida=True,
        id_conversa=id_conversa,
    )
    cursor.execute(
        """UPDATE chatbot.conversa SET origem_fireads=%s,contexto_fireads=%s
                      WHERE id_conversa=%s AND id_etapa_atual IS NULL;""",
        (decisao["origem"], Jsonb(decisao), id_conversa),
    )
    if cursor.rowcount != 1:
        raise ValueError("Conversa já iniciou antes da decisão FireAds")
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
