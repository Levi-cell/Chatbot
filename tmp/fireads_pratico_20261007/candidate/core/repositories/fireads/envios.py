"""Fila independente do dashboard e retrato do conteúdo aceito para o Funil."""

from psycopg.types.json import Jsonb
from core.integrations.fireads.contrato import CANAIS


def congelar(dados, payload, integracao_funil, cursor):
    origem = dados.get("origem_fireads")
    if origem is None:
        return (
            payload,
            integracao_funil["codigo_canal_venda"],
            integracao_funil["link_api_carrossel"],
        )
    canal = CANAIS[origem][1]
    estado = dados["contexto_fireads"]
    cursor.execute(
        """SELECT id_integracao_fireads, url_dashbord, aba_destino
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
        "payload_funil": payload,
        "canal": canal,
        "url_funil": integracao_funil["link_api_carrossel"],
        "url": config[1],
        "aba": config[2],
        "observacoes": obs,
        "telefone": dados["telefone_cliente"],
        "email": oportunidade["contato"]["email"],
        "nome": dados["nome_cliente"],
        "origem": origem,
        "perfil": (
            f"Dependente: {dados['nome_dependente']} ({dados['idade_dependente']} anos)"
            if dados["status_dependente"]
            else f"Titular ({dados['idade_cliente']} anos)"
        ),
    }
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


def reservar(cursor):
    cursor.execute(
        """WITH proximo AS (
        SELECT d.id_envio_dash FROM chatbot.envios_dash d
        JOIN chatbot.conversa c ON c.id_conversa=d.id_conversa
        JOIN chatbot.integracao_fireads i USING (id_integracao_fireads)
        JOIN chatbot.integracao_funil_unidade f ON f.id_unidade=d.id_unidade
        WHERE c.lead_no_funil IS TRUE AND i.integracao_ativa AND f.integracao_ativa AND f.widget_ativo
          AND ((d.status='pending' AND d.next_attempt_at <= clock_timestamp())
            OR (d.status='processing' AND d.processing_started_at < clock_timestamp()-INTERVAL '3 minutes'))
        ORDER BY d.attempt_count,d.id_envio_dash FOR UPDATE OF d SKIP LOCKED LIMIT 1
    ) UPDATE chatbot.envios_dash d SET status='processing',attempt_count=attempt_count+1,
        processing_started_at=clock_timestamp(),atualizado_em=clock_timestamp()
      FROM proximo p WHERE d.id_envio_dash=p.id_envio_dash
      RETURNING d.id_envio_dash,d.id_conversa,d.id_integracao_fireads,d.attempt_count,d.snapshot"""
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
        WHERE d.id_envio_dash=%s AND d.status='processing' AND d.attempt_count=%s
          AND d.processing_started_at > clock_timestamp()-INTERVAL '3 minutes'
          AND i.integracao_ativa AND f.integracao_ativa AND f.widget_ativo
          AND i.url_dashbord=d.snapshot->>'url' AND i.aba_destino=d.snapshot->>'aba'
        FOR UPDATE OF d""",
        (envio["id"], envio["tentativa"]),
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
