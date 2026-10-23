"""Fila independente do dashboard e retrato do conteúdo aceito para o Funil."""

from psycopg.types.json import Jsonb
import hashlib
from core.integrations.fireads.contrato import CANAIS
from core.integrations.fireads.contrato import identidade_telefone
from core.integrations.fireads.prazos import RESERVA_ENTREGA_SEGUNDOS
from core.integrations.fireads.atribuicao import CHAVE


def buscar_configuracao_entrega(dados, cursor):
    cursor.execute("""SELECT i.url_dashbord,i.aba_destino,i.fuso_formularios
        FROM chatbot.integracao_fireads i JOIN chatbot.unidade u USING (id_unidade)
        WHERE i.id_integracao_fireads=%s AND i.id_unidade=%s
          AND i.integracao_ativa AND i.contrato_validado AND u.status_pagamento IS TRUE""",
                   (dados['contexto_fireads']['id_integracao'], dados['id_unidade']))
    return cursor.fetchone()


def buscar_status(id_conversa, cursor):
    cursor.execute('SELECT status FROM chatbot.envios_dash WHERE id_conversa=%s', (id_conversa,))
    row = cursor.fetchone()
    return row[0] if row else None


def congelar(dados, payload, integracao_funil, cursor):
    origem = dados.get("origem_fireads")
    if origem is None:
        return (
            payload,
            integracao_funil["codigo_canal_venda"],
            integracao_funil["link_api_carrossel"],
        )
    # No retry, a entrega já registrada é a fonte de verdade. Não reconstruir
    # conteúdo/configuração a partir de cadastros que possam ter mudado depois.
    cursor.execute(
        "SELECT snapshot FROM chatbot.envios_dash WHERE id_conversa=%s",
        (dados["id_conversa"],),
    )
    existente = cursor.fetchone()
    if existente is not None:
        salvo = existente[0]
        return salvo["payload_funil"], salvo["canal"], salvo["url_funil"]
    canal = CANAIS[origem][1]
    estado = dados["contexto_fireads"]
    cursor.execute(
        """SELECT id_integracao_fireads, url_dashbord, aba_destino, fuso_formularios
        FROM chatbot.integracao_fireads WHERE id_integracao_fireads=%s AND id_unidade=%s""",
        (estado["id_integracao"], dados["id_unidade"]),
    )
    config = cursor.fetchone()
    if config is None:
        raise ValueError("Integração histórica FireAds não encontrada")
    oportunidade = payload["oportunidades"][0]
    obs = next(
        c["valor"]
        for c in oportunidade["personalizados"]
        if c["titulo"] == "Observações"
    )
    snapshot = {
        "versao": 2,
        "payload_funil": payload,
        "canal": canal,
        "url_funil": integracao_funil["link_api_carrossel"],
        "url": config[1],
        "aba": config[2],
        "fuso": config[3],
        "observacoes": obs,
        "telefone": dados["telefone_cliente"],
        "email": oportunidade["contato"]["email"],
        "nome": dados["nome_cliente"],
        "origem": origem,
        "referencia": estado.get("referencia"),
        "primeiro_atendimento": dados["primeiro_atendimento"],
        "status_dependente": dados["status_dependente"],
        "perfil": (
            f"Dependente: {dados['nome_dependente']} ({dados['idade_dependente']} anos)"
            if dados["status_dependente"]
            else f"Titular ({dados['idade_cliente']} anos)"
        ),
    }
    if dados.get('contexto_coleta'):
        from core.integrations.fireads.sincronizacao_coleta import dados_sincronizacao
        coleta = dados['contexto_coleta']
        sincronizacao = dados_sincronizacao(coleta, com_link=bool(dados.get('link_agendamento')))
        identidade = sincronizacao['identidade_coleta']
        alvo = identidade['destinatario']
        snapshot.update(versao=4, rota_formulario_chat=coleta['rota_formulario_chat'],
                        **sincronizacao, destino=None,
                        para_quem=alvo['valor']['texto'] if alvo['status']=='aceito' else (
                            'Para dependente' if dados['status_dependente'] else 'Para mim'))
    entrega = dados.get('entrega_fireads')
    if entrega is not None:
        if (entrega['url'], entrega['aba'], entrega['fuso']) != tuple(config[1:]):
            raise ValueError('Configuração FireAds mudou durante a preparação')
        snapshot.update(versao=5, destino=entrega['destino'])
        if estado.get(CHAVE):
            snapshot[CHAVE] = estado[CHAVE]
        snapshot.setdefault('campos_dashboard', {})
        snapshot.setdefault('identidade_coleta', {})
        snapshot.setdefault('coletar_turno', False)
        snapshot.setdefault('para_quem', 'Para dependente' if dados['status_dependente'] else 'Para mim')
        cursor.execute("""UPDATE chatbot.conversa SET origem_fireads=%s,
            contexto_fireads=contexto_fireads || %s WHERE id_conversa=%s""",
            (origem, Jsonb({'origem': origem, 'referencia_entrega': entrega['destino'],
                           'canal_confirmado_entrega': True,
                           **({CHAVE: estado[CHAVE]} if estado.get(CHAVE) else {})}), dados['id_conversa']))
    cursor.execute(
        """INSERT INTO chatbot.envios_dash
        (id_conversa,id_unidade,id_integracao_fireads,snapshot) VALUES (%s,%s,%s,%s)
        ON CONFLICT (id_conversa) DO NOTHING""",
        (dados["id_conversa"], dados["id_unidade"], config[0], Jsonb(snapshot)),
    )
    cursor.execute(
        """UPDATE chatbot.conversa SET lead_no_dash=FALSE
        WHERE id_conversa=%s AND lead_no_dash IS NULL""",
        (dados["id_conversa"],),
    )
    cursor.execute(
        "SELECT snapshot FROM chatbot.envios_dash WHERE id_conversa=%s",
        (dados["id_conversa"],),
    )
    salvo = cursor.fetchone()[0]
    return salvo["payload_funil"], salvo["canal"], salvo["url_funil"]


def bloquear_contato(chave, cursor):
    """Reserva de sessão: protege o contato inclusive durante chamadas HTTP."""
    cursor.execute("SELECT pg_try_advisory_lock(%s)", (chave,))
    return cursor.fetchone()[0]


def chave_contato(id_integracao, numero):
    identidade = f'fireads:{id_integracao}:{identidade_telefone(numero)}'
    return int.from_bytes(hashlib.sha256(identidade.encode()).digest()[:8], 'big', signed=True)


def liberar_contato(chave, cursor):
    cursor.execute("SELECT pg_advisory_unlock(%s)", (chave,))


def reservar(cursor, id_conversa=None):
    cursor.execute(
        """WITH proximo AS (
        SELECT d.id_envio_dash FROM chatbot.envios_dash d
        JOIN chatbot.conversa c ON c.id_conversa=d.id_conversa
        JOIN chatbot.integracao_fireads i USING (id_integracao_fireads)
        JOIN chatbot.integracao_funil_unidade f ON f.id_unidade=d.id_unidade
        JOIN chatbot.unidade u ON u.id_unidade=d.id_unidade
        WHERE i.integracao_ativa AND i.contrato_validado AND f.integracao_ativa AND f.widget_ativo
          AND (c.lead_no_funil IS TRUE OR EXISTS (
              SELECT 1 FROM chatbot.funil_envios fe WHERE fe.id_conversa=d.id_conversa
              AND fe.snapshot IS NOT NULL))
          AND (%s::bigint IS NULL OR d.id_conversa=%s)
          AND u.status_pagamento IS TRUE
          AND ((d.status='pending' AND d.next_attempt_at <= clock_timestamp())
            OR (d.status='processing' AND d.processing_started_at < clock_timestamp()-(%s * INTERVAL '1 second')))
        ORDER BY d.attempt_count,d.id_envio_dash FOR UPDATE OF d SKIP LOCKED LIMIT 1
    ) UPDATE chatbot.envios_dash d SET status='processing',attempt_count=attempt_count+1,
        processing_started_at=clock_timestamp(),atualizado_em=clock_timestamp()
      FROM proximo p WHERE d.id_envio_dash=p.id_envio_dash
      RETURNING d.id_envio_dash,d.id_conversa,d.id_integracao_fireads,d.attempt_count,d.snapshot""",
        (id_conversa, id_conversa, RESERVA_ENTREGA_SEGUNDOS),
    )
    row = cursor.fetchone()
    return (
        dict(zip(("id", "conversa", "integracao", "tentativa", "snapshot"), row))
        if row
        else None
    )


def conferir_posse(envio, cursor):
    cursor.execute(
        """SELECT 1 FROM chatbot.envios_dash d
        JOIN chatbot.integracao_fireads i USING (id_integracao_fireads)
        JOIN chatbot.integracao_funil_unidade f ON f.id_unidade=d.id_unidade
        JOIN chatbot.unidade u ON u.id_unidade=d.id_unidade
        WHERE d.id_envio_dash=%s AND d.status='processing' AND d.attempt_count=%s
          AND u.status_pagamento IS TRUE
          AND d.processing_started_at > clock_timestamp()-(%s * INTERVAL '1 second')
          AND i.integracao_ativa AND i.contrato_validado AND f.integracao_ativa AND f.widget_ativo
          AND i.url_dashbord=d.snapshot->>'url' AND i.aba_destino=d.snapshot->>'aba'
        FOR UPDATE OF d""",
        (envio["id"], envio["tentativa"], RESERVA_ENTREGA_SEGUNDOS),
    )
    if cursor.fetchone() is None:
        raise ValueError("Reserva/configuração FireAds mudou; não escrever")


def concluir(envio, recibo, cursor):
    cursor.execute(
        """UPDATE chatbot.envios_dash SET status='sent',enviado_em=clock_timestamp(),
        processing_started_at=NULL,ultimo_erro=NULL,recibo=%s,atualizado_em=clock_timestamp()
        WHERE id_envio_dash=%s AND status='processing' AND attempt_count=%s RETURNING id_conversa""",
        (Jsonb(recibo), envio["id"], envio["tentativa"]),
    )
    row = cursor.fetchone()
    if row is None:
        raise ValueError("Reserva FireAds perdida após envio")
    cursor.execute(
        "UPDATE chatbot.conversa SET lead_no_dash=TRUE WHERE id_conversa=%s", (row[0],)
    )


def reagendar(envio, erro, cursor):
    cursor.execute(
        """UPDATE chatbot.envios_dash SET status='pending',
        next_attempt_at=clock_timestamp()+INTERVAL '30 minutes',processing_started_at=NULL,
        ultimo_erro=%s,atualizado_em=clock_timestamp()
        WHERE id_envio_dash=%s AND status='processing' AND attempt_count=%s""",
        (type(erro).__name__ + ": " + str(erro)[:300], envio["id"], envio["tentativa"]),
    )


def registrar_duplicidade(envio, cursor, *, destino=None):
    """Somente append novo recusado pode passar a atualizar um Orgânico existente."""
    conferir_posse(envio, cursor)
    snapshot = envio['snapshot']
    if (snapshot.get('versao') != 5 or snapshot.get('origem') != 'organico'
            or (snapshot.get('destino') or {}).get('tipo') != 'create'):
        raise ValueError('Entrega não permite alternativa por duplicidade')
    if destino is not None and not snapshot.get('append_recusado_duplicidade'):
        raise ValueError('Não houve recusa explícita de duplicidade')
    campos = {'append_recusado_duplicidade': True}
    if destino is not None:
        campos['destino'] = destino
    cursor.execute('''UPDATE chatbot.envios_dash SET snapshot=snapshot || %s
        WHERE id_envio_dash=%s AND status='processing' AND attempt_count=%s
        RETURNING snapshot''', (Jsonb(campos), envio['id'], envio['tentativa']))
    row = cursor.fetchone()
    if row is None:
        raise ValueError('Reserva FireAds perdida')
    envio['snapshot'] = row[0]
    return row[0]
