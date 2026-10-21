"""Estado anterior à rota sem link, com dados sintéticos nas áreas preservadas."""

from contextlib import contextmanager
from unittest.mock import patch

from core.database.deploy_database import bank_script, etapa_transicao_script
from core.database.deploy_database.povoar_etapas import ETAPAS


ETAPAS_LEGADAS = tuple(etapa for etapa in ETAPAS if etapa[0] <= 17) + (
    (18, "Agendamento após a triagem cognitiva", False, 0, True),
    (19, "Pesquisa de satisfação - nota", False, 0, True),
    (20, "Pesquisa de satisfação - opção de comentário", False, 0, True),
    (21, "Pesquisa de satisfação - comentário", False, 0, True),
    (22, "Finalização do atendimento", True, 30, True),
)

TRANSICOES_LEGADAS = tuple(
    (origem, evento, destino)
    for origem, evento, destino in etapa_transicao_script.TRANSICOES_INICIAIS
    if origem <= 16 and not evento.endswith('_email_fireads')
) + (
    (17, "triagem_pergunta_6_respondida", 18),
    (18, "agendamento_confirmado", 19),
    (19, "satisfacao_avaliada", 20),
    (20, "comentario_satisfacao_aceito", 21),
    (20, "comentario_satisfacao_recusado", 22),
    (21, "comentario_satisfacao_recebido", 22),
)


def criar_base_legada(conn):
    """O chamador já verificou banco vazio, local e exclusivo dos testes."""
    cursor = conn.cursor()
    cursor.execute("CREATE SCHEMA chatbot; CREATE TABLE chatbot.auth_user(id SERIAL PRIMARY KEY)")

    @contextmanager
    def transacao_local(*_):
        yield cursor

    with patch.object(bank_script, "transacao_deploy", transacao_local), patch.object(
        etapa_transicao_script, "transacao_deploy", transacao_local
    ), patch.object(etapa_transicao_script, "TRANSICOES_INICIAIS", TRANSICOES_LEGADAS):
        bank_script.criar_tabelas()
        bank_script.criar_funcoes_lock()
        # Os únicos deltas de schema desta entrega são turno e link opcional.
        cursor.execute("ALTER TABLE chatbot.conversa DROP COLUMN turno")
        cursor.execute("ALTER TABLE chatbot.unidade ALTER COLUMN link_agendamento SET NOT NULL")
        cursor.executemany(
            "INSERT INTO chatbot.etapa VALUES (%s,%s,%s,%s,%s)", ETAPAS_LEGADAS
        )
        etapa_transicao_script.criar_e_povoar_transicoes_etapa()

    cursor.execute("""
        CREATE TABLE chatbot.historico_mensagens_202610
        PARTITION OF chatbot.historico_mensagens
        FOR VALUES FROM ('2026-10-01 00:00:00-03') TO ('2026-11-01 00:00:00-03');

        INSERT INTO chatbot.unidade(id_unidade,nome_unidade,nome_agente,genero,cnpj,
            email_responsavel,telefone,numero_comercial,waba_id,phone_number_id,link_agendamento,
            id_fuso,nome_fuso,fuso_verificado_em)
        VALUES (1,'Unidade teste','Suh','feminino','cnpj','teste@example.com','5511888888888',
            '5511999999999','waba','phone','https://example.com/reserva',25,'America/Sao_Paulo',NOW());

        INSERT INTO chatbot.cliente(id_cliente,nome,waid_telefone,idade,email)
        SELECT id,'Cliente ' || id,'55119999999' || id,40,'cliente' || id || '@example.com'
        FROM generate_series(18,22) id;
        INSERT INTO chatbot.conversa(id_conversa,id_cliente,id_unidade,id_etapa_atual,
            status_ativa,profissao,followup_stage,followup_last_sent_at,lead_no_funil,
            processing,processing_started_at,lock_version,turnos_sem_avanco,
            iniciou_em,finalizou_em,motivo_encerramento,last_message_from,last_interaction_at)
        SELECT id,id,1,id,id <> 22,'Professora',1,'2026-09-28 13:00:00-03',id >= 20,
            id=18,CASE WHEN id=18 THEN NOW()-INTERVAL '5 minutes' END,8,3,
            '2026-09-28 10:00:00-03',CASE WHEN id=22 THEN '2026-09-29 10:00:00-03'::timestamptz END,
            CASE WHEN id=22 THEN 'foi_agendado' END,'bot','2026-09-29 09:00:00-03'
        FROM generate_series(18,22) id;

        INSERT INTO chatbot.dependente(id_cliente,id_conversa,nome_dependente,idade)
        VALUES (21,21,'João',12);
        UPDATE chatbot.conversa SET status_dependente=TRUE WHERE id_conversa=21;

        INSERT INTO chatbot.fila_mensagens(id_mensagem,id_conversa,received_data_hora,
            cliente_telefone,conteudo_texto,tipo_mensagem,id_hash_msg,id_phone_unidade,unidade_telefone,
            status,retry_count,processing_started_at)
        SELECT id,id,'2026-09-29 09:00:00-03','55119999999' || id,'Já reservei',
            'text','wamid.cliente.' || id,'phone','5511888888888',
            CASE WHEN id=18 THEN 'processing' ELSE 'pending' END,1,NOW()-INTERVAL '5 minutes'
        FROM generate_series(18,22) id;

        INSERT INTO chatbot.historico_mensagens(id_conversa,id_etapa,received_data_hora,
            cliente_telefone,conteudo_texto,tipo_mensagem,id_hash_msg,id_phone_unidade,
            unidade_telefone,quem_enviou,status_envio,id_mensagem_fila,id_hash_cliente_origem)
        SELECT id,id,'2026-09-29 09:00:00-03','55119999999' || id,'Já reservei','text',
            'wamid.cliente.' || id,'phone','5511888888888','cliente',NULL,id,NULL
        FROM generate_series(18,22) id;
        INSERT INTO chatbot.historico_mensagens(id_conversa,id_etapa,received_data_hora,
            cliente_telefone,conteudo_texto,tipo_mensagem,id_hash_msg,id_phone_unidade,
            unidade_telefone,quem_enviou,status_envio,id_mensagem_fila,id_hash_cliente_origem)
        SELECT id,CASE WHEN id=18 THEN 19 ELSE id END,'2026-10-01 09:01:00-03',
            '55119999999' || id,'Resposta preservada','text','wamid.bot.' || id,
            'phone','5511888888888','bot','sent',id,'wamid.cliente.' || id
        FROM generate_series(18,22) id;

        INSERT INTO chatbot.respostas_desafios(id_conversa,id_etapa,resposta)
        SELECT 21,etapa,'Sim' FROM generate_series(12,17) etapa;
        INSERT INTO chatbot.pesquisa_satisfacao(id_conversa,nota,comentario)
        VALUES (22,5,'Muito bom! ☺️');
        INSERT INTO chatbot.followup_retomada(id_conversa,id_mensagem_fila,id_hash_cliente,
            id_etapa,stage_anterior,followup_em)
        SELECT id,id,'wamid.cliente.' || id,id,1,'2026-09-28 13:00:00-03'
        FROM generate_series(18,22) id;
        INSERT INTO chatbot.followup_envio(id_conversa,id_ancora,ancora_em,id_historico_bot,enviado_em,id_hash_msg)
        VALUES (18,100,'2026-09-28 06:00:00-03',101,'2026-09-28 13:00:00-03','wamid.followup');
        INSERT INTO chatbot.followup_legado(id_conversa,stage_anterior) VALUES (19,0);
        INSERT INTO chatbot.funil_envios(id_conversa,status,attempt_count,resposta_funil)
        VALUES (20,'sent',1,'aceito'),(21,'processing',2,NULL);

        INSERT INTO chatbot.consumo_mensal_meta(id_unidade,mes_referencia,waba_id,phone_number_id,
            timezone_id,fuso_horario,data_hora_inicio,data_hora_fim,qtd_janela_gratuita,
            qtd_franquia_consumida,qtd_cobradas_meta,consultado_ate,ultimo_sucesso_em,
            status_apuracao,data_proxima_consolidacao)
        VALUES (1,'2026-10-01','waba','phone',25,'America/Sao_Paulo',
            '2026-10-01 00:00:00-03','2026-11-01 00:00:00-03',3000,750,0,
            '2026-10-02 10:00:00-03','2026-10-02 10:00:00-03','em_andamento','2026-11-25');
        INSERT INTO chatbot.consumo_meta_coletas(id_unidade,periodo,proxima_consulta_em,
            ultima_tentativa_em,ultimo_erro,falhas_consecutivas)
        VALUES (1,'2026-10','2026-10-02 11:00:00-03','2026-10-02 10:00:00-03',NULL,0);
    """)
    conn.commit()
