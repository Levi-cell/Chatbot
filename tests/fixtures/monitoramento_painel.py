"""Dados inteiramente fictícios usados pelos testes e pela revisão visual local."""


CONVERSAS = {
    'unidade': {'nome': 'Supera Santo Antônio de Jesus', 'agente': 'Suh', 'regras': {
        'suporte_idoso': True, 'email_obrigatorio': True, 'bpa_ativo': True,
    }},
    'periodo': {'chave': 'total', 'rotulo': 'Todo o histórico',
                'inicio': '2026-07-29T23:55:00-03:00', 'fim': '2026-09-03T12:00:00-03:00',
                'texto': '29/07/2026 23:55 até agora'},
    'metricas': {'leads': 119, 'mensagens': 1864, 'funil': 31, 'avaliacoes': 17, 'nota_media': 4.53},
    'conversas': [
        {'id_cliente': 140, 'nome': 'Edcarlos', 'contato': '557194111866',
         'email': 'edcarlos@example.com', 'profissao': 'Empresário', 'ids_conversa': [157, 159],
         'perfis': ['adulto'], 'dependentes': [], 'foi_funil': True, 'avaliada': True,
         'ultima_atividade': '2026-09-03T14:43:35Z', 'ultima_mensagem_id': 4,
         'ultima_mensagem': 'Podemos começar? ☺️'},
        {'id_cliente': 141, 'nome': 'Maria Souza', 'contato': '557599111222',
         'email': 'maria@example.com', 'profissao': 'Professora', 'ids_conversa': [158],
         'perfis': ['dependente', 'menor'], 'dependentes': ['Lucas'], 'foi_funil': True, 'avaliada': False,
         'ultima_atividade': '2026-09-03T13:31:17Z', 'ultima_mensagem_id': 141,
         'ultima_mensagem': 'Quero agendar'},
        {'id_cliente': 142, 'nome': 'Ariana', 'contato': '557791238060',
         'email': '', 'profissao': 'Aposentada', 'ids_conversa': [150], 'perfis': ['idoso'],
         'dependentes': [], 'foi_funil': False, 'avaliada': True,
         'ultima_atividade': '2026-09-02T14:55:35Z', 'ultima_mensagem_id': 142,
         'ultima_mensagem': 'Obrigada pelo atendimento'},
        {'id_cliente': 143, 'nome': 'Joana Lima', 'contato': '557588000111',
         'email': 'joana@example.com', 'profissao': 'Autônoma', 'ids_conversa': [149],
         'perfis': ['dependente', 'adulto'], 'dependentes': ['Beatriz'], 'foi_funil': False, 'avaliada': False,
         'ultima_atividade': '2026-09-01T11:41:00Z', 'ultima_mensagem_id': 143,
         'ultima_mensagem': 'Às vezes'},
    ],
    'atualizado_em': '2026-09-03T15:00:00Z',
}

MENSAGENS = {
    140: {'id_cliente': 140, 'mensagens': [
        {'id_mensagem': 1, 'id_conversa': 157, 'id_etapa': 1, 'data': '2026-09-03T14:40:00Z', 'quem_enviou': 'cliente', 'tipo': 'text', 'texto': 'Olá', 'botoes': []},
        {'id_mensagem': 2, 'id_conversa': 157, 'id_etapa': 2, 'data': '2026-09-03T14:40:04Z', 'quem_enviou': 'bot', 'tipo': 'interactive_button', 'texto': 'Esse atendimento é para você ou para um dependente?', 'botoes': ['Para mim', 'Para um dependente']},
        {'id_mensagem': 3, 'id_conversa': 157, 'id_etapa': 2, 'data': '2026-09-03T14:40:20Z', 'quem_enviou': 'cliente', 'tipo': 'interactive', 'texto': 'Para mim', 'botoes': []},
        {'id_mensagem': 4, 'id_conversa': 159, 'id_etapa': 11, 'data': '2026-09-03T14:43:35Z', 'quem_enviou': 'bot', 'tipo': 'interactive_button', 'texto': 'Vou fazer uma triagem rápida. Podemos começar? ☺️', 'botoes': ['Começar triagem']},
    ]},
}
for _id in (141, 142, 143):
    MENSAGENS[_id] = {'id_cliente': _id, 'mensagens': [
        {'id_mensagem': _id, 'id_conversa': _id + 17, 'id_etapa': 7,
         'data': '2026-09-03T13:31:17Z', 'quem_enviou': 'cliente',
         'tipo': 'text', 'texto': 'Mensagem fictícia de revisão visual', 'botoes': []},
    ]}

NOMES_ETAPAS = [
    'Saudação e nome do cliente', 'Destino do atendimento', 'Confirmação do destino',
    'Profissão do cliente', 'Nome do dependente', 'Idade do aluno', 'Oferta de aula',
    'Oferta adiada', 'Retorno ao atendimento', 'E-mail', 'Introdução à triagem',
    'Triagem · pergunta 1', 'Triagem · pergunta 2', 'Triagem · pergunta 3',
    'Triagem · pergunta 4', 'Triagem · pergunta 5', 'Triagem · pergunta 6',
    'Agendamento', 'Pesquisa · nota', 'Opção de comentário', 'Comentário', 'Finalização',
]
RELATORIO = {
    'unidade': {'nome': 'Supera Santo Antônio de Jesus'},
    'periodo': CONVERSAS['periodo'], 'metricas': CONVERSAS['metricas'],
    'tendencias': {'leads': 12.4, 'mensagens': 8.1, 'funil': -3.2, 'avaliacoes': 5.0, 'nota_media': 2.1},
    'atividade': [
        {'periodo': f'2026-08-{dia:02d}T12:00:00-03:00', 'leads': 7 + dia % 5, 'mensagens': 80 + dia * 3}
        for dia in range(24, 31)
    ],
    'satisfacao': {'1': 0, '2': 0, '3': 1, '4': 6, '5': 10},
    'perfis': {'idade_minima_dependente': 4, 'sem_classificacao': 12, 'linhas': [
        {'rotulo': 'Dependentes de 4 a 17 anos', 'leads': 37, 'conversas': 37, 'funil': 24, 'taxa_funil': 64.9},
        {'rotulo': 'Dependentes de 18 a 59 anos', 'leads': 3, 'conversas': 3, 'funil': 1, 'taxa_funil': 33.3},
        {'rotulo': 'Dependentes com 60 anos ou mais', 'leads': 2, 'conversas': 2, 'funil': 0, 'taxa_funil': 0},
        {'rotulo': 'Titulares de 18 a 59 anos', 'leads': 54, 'conversas': 56, 'funil': 6, 'taxa_funil': 11.1},
        {'rotulo': 'Titulares com 60 anos ou mais', 'leads': 11, 'conversas': 11, 'funil': 0, 'taxa_funil': None},
    ]},
    'etapas': [{'id_etapa': i + 1, 'nome_etapa': nome, 'quantidade': (i * 7) % 19} for i, nome in enumerate(NOMES_ETAPAS)],
    'atualizado_em': '2026-09-03T15:00:00Z',
}

CONTATOS = [
    {'id_cliente': 140, 'nome': 'Edcarlos Silva', 'email': 'edcarlos@example.com', 'waid_telefone': '557194111866'},
    {'id_cliente': 141, 'nome': None, 'email': None, 'waid_telefone': '557599111222'},
]
