from editar import *
p='core/repositories/funil/leads.py'
replace(p,'            c.turno\n','            c.turno, c.origem_fireads, c.contexto_fireads\n')
replace(p,'    return {\n','    dados = {\n')
write(p,read(p)+'''
    if len(resultado) > 16 and resultado[15] is not None:
        dados['origem_fireads'] = resultado[15]
        dados['contexto_fireads'] = resultado[16]
        retrato = (resultado[16] or {}).get('dados_titular') or {}
        if 'nome' not in retrato or 'resultado_email' not in retrato:
            raise ValueError('Coletas históricas FireAds incompletas para o Funil')
        dados.update(nome_cliente=retrato['nome'], email_cliente=retrato.get('email'),
                     idade_cliente=retrato.get('idade'), resultado_email_fireads=retrato['resultado_email'])
    return dados
''')
p='core/integrations/funil/oportunidades.py'
replace(p,'import re\n','import re\nfrom core.integrations.fireads.contrato import CANAIS\nfrom core.validacoes.email import ResultadoColetaEmail\n')
replace(p,'"valor": ORIGEM_LEAD_CHATBOT,','"valor": CANAIS[dados_lead["origem_fireads"]][0] if dados_lead.get("origem_fireads") else ORIGEM_LEAD_CHATBOT,')
replace(p,'    cabecalho = (','    canal = f"Canal de venda: {CANAIS[dados_lead[\'origem_fireads\']][0]}\\n\\n" if dados_lead.get("origem_fireads") else ""\n    cabecalho = (')
replace(p,'        "------NOVO LEAD-------\\n\\n"','        "------NOVO LEAD-------\\n\\n"\n        f"{canal}"')
replace(p,'def _resolver_resultado_email_conversa(dados_lead):','''def _resolver_resultado_email_conversa(dados_lead):
    if dados_lead.get('origem_fireads'):
        classificacao = dados_lead['resultado_email_fireads']
        if classificacao not in {CLASSIFICACAO_EMAIL_VALIDO, CLASSIFICACAO_EMAIL_AUSENTE, CLASSIFICACAO_EMAIL_NAO_INFORMADO}:
            raise ValueError('Resultado histórico de email inválido')
        return ResultadoColetaEmail(aceita=True, classificacao=classificacao, email=dados_lead.get('email_cliente'))
''')
p='workers/worker_funil/processamento.py'
replace(p,'import json\n','import json\nfrom core.repositories.fireads.envios import congelar\n')
replace(p,'        payload = montar_payload_oportunidade(dados_lead)','''        payload = montar_payload_oportunidade(dados_lead)
        payload, canal, url_funil = congelar(dados_lead, payload, integracao, cursor)''')
replace(p,'link_api_carrossel=integracao["link_api_carrossel"],','link_api_carrossel=url_funil,')
replace(p,'codigo_canal_venda=integracao["codigo_canal_venda"],','codigo_canal_venda=canal,')
p='workers/worker_funil/funil_worker.py'
replace(p,'import logging\n','import logging\nfrom workers.worker_funil.fireads import processar_lote\n')
replace(p,'        return resumo','''        # Fila independente: tentativas de dashboard não dependem de haver
        # novos leads elegíveis ao Funil neste ciclo.
        resumo['dash'] = processar_lote(conn, cursor, FUNIL_LIMITE_POR_CICLO)
        logger.info('dash_ciclo | %s', resumo['dash'])
        return resumo''')
p='callback/webhook/models.py'
s=read(p).replace('url_dashboard','url_dashbord').replace('    concluida = models.BooleanField(default=False)','    consulta_concluida = models.BooleanField(default=False)')
write(p,s)
p='callback/webhook/admin.py'
replace(p,'for modelo in (Chat, ConsultaFireAds, EnvioDash):','class FireAdsConsultaAdmin(SomenteVisualizacaoAdminMixin, admin.ModelAdmin):\n    pass\n\n\nfor modelo in (Chat, ConsultaFireAds, EnvioDash):')
replace(p,'admin.site.register(modelo, IntegracaoFunilUnidadeAdmin)','admin.site.register(modelo, FireAdsConsultaAdmin)')
validate()
print('Entrega e snapshots preparados.')
