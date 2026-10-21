from editar import *

p='workers/worker_flow/response_flow/flow_worker.py'
replace(p,'import logging\n','import logging\nfrom workers.worker_flow.fireads import preparar_abertura\n')
replace(p,'            contexto_banco = reler_conversa(contexto_banco, lock_version, cursor_ciclo)\n','            contexto_banco = reler_conversa(contexto_banco, lock_version, cursor_ciclo)\n            contexto_banco = preparar_abertura(\n                contexto_banco, mensagem, lock_version, conn_ciclo, cursor_ciclo\n            )\n')
p='workers/worker_flow/valida_historico.py'
replace(p,'        "id_conversa": id_conversa,\n        "id_cliente": contexto_banco.get("id_cliente"),','        "contexto_fireads": contexto_banco.get("contexto_fireads"),\n        "id_conversa": id_conversa,\n        "id_cliente": contexto_banco.get("id_cliente"),')
p='workers/worker_flow/response_flow/flow_sender.py'
replace(p,'import logging\n','import logging\nfrom workers.worker_flow.fireads import email_importado\nfrom core.integrations.whatsapp.pywa_functions.pywa_senders.etapa4 import enviar_abertura_fireads\n')
replace(p,'    if id_etapa_atual is None or id_etapa_atual == 1:', '    if id_etapa_atual is None and email_importado(contexto_historico):\n        return enviar_abertura_fireads(contexto_historico)\n\n    if id_etapa_atual is None or id_etapa_atual == 1:')
p='core/integrations/whatsapp/messages/etapa4_messages.py'
write(p,read(p)+'''

def montar_abertura_fireads(contexto):
    """Primeira resposta após importação completa; pergunta continua na etapa 4."""
    from workers.worker_flow.response_flow.etapas.validadores_universais.validador_midia import validar_midia
    from workers.worker_flow.response_flow.etapas.validadores_universais.validador_financeiro import validar_pergunta_financeira
    from workers.worker_flow.response_flow.etapas.validadores_universais.validador_reforco_escolar import validar_duvida_reforco_escolar

    dados = contexto['contexto_fireads']['dados_titular']
    genero = contexto.get('genero')
    if genero not in {'masculino', 'feminino'} or not contexto.get('nome_agente'):
        raise ValueError('Apresentação da unidade incompleta')
    artigo = 'a' if genero == 'feminino' else 'o'
    abertura = (
        f"Olá, {dados['nome']}! Seja muito bem-vindo(a)! Sou {artigo} "
        f"{contexto['nome_agente']}, assistente do {contexto['nome_unidade']}. ☺️\\n\\n"
        "Vi que você já preencheu um dos nossos formulários. Para continuarmos "
        "com sua reserva por cortesia da unidade, precisamos fazer mais algumas perguntinhas, ok?"
    )
    pergunta = MENSAGEM_REPETICAO_ETAPA4
    texto = contexto.get('texto_cliente_atual') or ''
    if validar_midia(contexto.get('tipo_mensagem_atual')):
        pergunta = montar_mensagem_tratamento_midia(pergunta)
    elif validar_duvida_reforco_escolar(texto):
        pergunta = montar_mensagem_tratamento_reforco_escolar(pergunta)
    elif validar_pergunta_financeira(texto):
        pergunta = montar_mensagem_tratamento_financeiro(pergunta)
    return abertura + '\\n\\n' + pergunta
''')
p='core/integrations/whatsapp/pywa_functions/pywa_senders/etapa4.py'
write(p,read(p)+'''

def enviar_abertura_fireads(contexto):
    from core.integrations.whatsapp.messages.etapa4_messages import montar_abertura_fireads
    mensagem = contexto['mensagem_cliente_atual']
    return _enviar_texto_etapa4(
        mensagem['cliente_telefone'], mensagem['id_phone_unidade'],
        montar_abertura_fireads(contexto), evento='fireads_abertura',
    )
''')
p='workers/worker_flow/transacoes/movimento_conversa.py'
replace(p,'from core.repositories.atendimento.conversas import (','from workers.worker_flow.fireads import email_importado\nfrom core.repositories.atendimento.conversas import (')
replace(p,'        if etapa_destino != ETAPA_1_NOME_CLIENTE:', '        if etapa_destino != ETAPA_1_NOME_CLIENTE and not (\n            etapa_destino == 4 and email_importado(contexto_historico)\n        ):')
replace(p,'Conversa sem etapa so pode ser inicializada na etapa 1','Inicializacao exige etapa 1 ou importacao FireAds completa na etapa 4')
p='core/repositories/atendimento/conversas.py'
replace(p,'    cursor.execute("""\n        INSERT INTO chatbot.conversa (', '''    cursor.execute("""
        INSERT INTO chatbot.chat (id_cliente, id_unidade) VALUES (%s, %s)
        ON CONFLICT (id_cliente, id_unidade) DO UPDATE SET id_cliente=EXCLUDED.id_cliente
        RETURNING id_chat;
    """, (id_cliente, id_unidade))
    id_chat = cursor.fetchone()[0]
    cursor.execute("""
        INSERT INTO chatbot.conversa (
            id_chat,''')
replace(p,"        VALUES (%s, %s, NOW(), 'cliente')", "        VALUES (%s, %s, %s, NOW(), 'cliente')")
replace(p,'RETURNING id_conversa;\n    """, (id_cliente, id_unidade))','RETURNING id_conversa;\n    """, (id_chat, id_cliente, id_unidade))')
replace(p,'    if id_etapa_resultante != ETAPA_INICIAL:', '    if id_etapa_resultante not in {ETAPA_INICIAL, 4}:')
replace(p,'          AND id_etapa_atual IS NULL;','''          AND id_etapa_atual IS NULL
          AND (%s = 1 OR (contexto_fireads->>'resultado' = 'importado'
               AND contexto_fireads->>'concluida' = 'true'
               AND contexto_fireads->>'id_conversa' = id_conversa::text));''')
replace(p,'        data_interacao,\n        id_conversa,\n    ))','        data_interacao,\n        id_conversa,\n        id_etapa_resultante,\n    ))')
p='workers/worker_flow/transacoes/persistencia_resposta.py'
replace(p,'import logging\n','import logging\nfrom core.repositories.fireads.consulta import guardar_coletas\n')
replace(p,'    intencao_encerramento = resolver_intencao_encerramento(', '    guardar_coletas(contexto_historico, efeitos_transicao, cursor)\n    intencao_encerramento = resolver_intencao_encerramento(')

for etapa,baseevento,adiado in [(7,'oferta_aceita','EVENTO_OFERTA_ADIADA'),(9,'retorno_confirmado','EVENTO_RETORNO_ADIADO')]:
    evento=baseevento+'_email_fireads'
    p=f'workers/worker_flow/response_flow/etapas/resolver_etapa{etapa}.py'
    replace(p,'import logging\n', 'import logging\nfrom workers.worker_flow.fireads import email_importado\nfrom core.integrations.whatsapp.pywa_functions.pywa_senders.etapa11 import enviar_etapa11\n')
    replace(p,'    # VALIDANDO DESTINO(S)',f'''    # Somente o snapshot desta conversa autoriza aproveitar o e-mail.
    if evento_transicao == '{baseevento}' and email_importado(contexto_historico):
        evento_transicao = '{evento}'

    # VALIDANDO DESTINO(S)''')
    replace(p,'    else:\n        contexto_envio = enviar_etapa10(',f'''    elif evento_transicao == '{evento}':
        contexto_envio = enviar_etapa11(
            cliente_telefone, phone_id_unidade,
            status_dependente=status_dependente, nome_dependente=nome_dependente,
        )
    else:
        contexto_envio = enviar_etapa10(''')
    replace(p,'def _destinos_esperados_por_evento(evento_transicao):',f"def _destinos_esperados_por_evento(evento_transicao):\n    if evento_transicao == '{evento}':\n        return {{11}}\n")
p='workers/worker_flow/transacoes/efeitos_transicao.py'
replace(p,'import logging\n','import logging\nfrom workers.worker_flow.fireads import email_importado\n')
replace(p,'    # Sem evento não existe transição nem efeito específico de etapa.', '''    if (etapa_origem, evento) in {
        (7, 'oferta_aceita_email_fireads'), (9, 'retorno_confirmado_email_fireads')
    }:
        if etapa_destino != 11 or not email_importado(contexto_historico):
            raise ValueError('Salto de email FireAds sem coleta completa nesta conversa')
        return {'email_fireads_reaproveitado': True}

    # Sem evento não existe transição nem efeito específico de etapa.''')
p='core/database/deploy_database/etapa_transicao_script.py'
replace(p,'    (7, "oferta_aceita", 10),','    (7, "oferta_aceita", 10),\n    (7, "oferta_aceita_email_fireads", 11),')
replace(p,'    (9, "retorno_confirmado", 10),','    (9, "retorno_confirmado", 10),\n    (9, "retorno_confirmado_email_fireads", 11),')
validate()
print('Fluxo preparado na copia isolada.')
