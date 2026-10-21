"""Apresentação única e pergunta correspondente ao primeiro campo necessário."""

from core.validacoes.coleta_abertura import valor, validar_contexto
from core.integrations.whatsapp.messages.etapa2_messages import MENSAGEM_REPETICAO_ETAPA2
from core.integrations.whatsapp.messages.etapa4_messages import MENSAGEM_REPETICAO_ETAPA4
from core.integrations.whatsapp.messages.tratamentos.financeiro import montar_mensagem_tratamento_financeiro
from core.integrations.whatsapp.messages.tratamentos.midia import montar_mensagem_tratamento_midia
from core.integrations.whatsapp.messages.tratamentos.reforco_escolar import montar_mensagem_tratamento_reforco_escolar


def montar_abertura(contexto, saudacao, tratamento=None):
    estado = validar_contexto(contexto)
    if not estado:
        raise ValueError('Abertura parcial sem contexto')
    genero = contexto.get('genero')
    if genero not in {'feminino', 'masculino'} or not all(contexto.get(c) for c in ('nome_agente', 'nome_unidade')):
        raise ValueError('Apresentação da unidade incompleta')
    nome = valor(estado, 'nome')
    saudacao = f'{saudacao}, {nome}!' if nome else f'{saudacao}!'
    artigo = 'a' if genero == 'feminino' else 'o'
    apresentacao = f"{saudacao} Sou {artigo} {contexto['nome_agente']}, assistente do {contexto['nome_unidade']}. ☺️"
    if estado['formulario_identificado']:
        apresentacao += ('\n\nVi que você já preencheu um dos nossos formulários. Para continuarmos '
                         'com sua reserva por cortesia da unidade vamos precisar fazer mais algumas perguntinhas, ok?')
    pergunta = {1: 'Me diz, qual o seu nome?', 2: MENSAGEM_REPETICAO_ETAPA2,
                4: MENSAGEM_REPETICAO_ETAPA4}[estado['etapa_inicial']]
    tratamentos = {'pergunta_financeira': montar_mensagem_tratamento_financeiro,
                   'duvida_reforco_escolar': montar_mensagem_tratamento_reforco_escolar,
                   'tipo_mensagem_nao_suportado': montar_mensagem_tratamento_midia}
    if tratamento:
        pergunta = tratamentos[tratamento](pergunta)
    return apresentacao + '\n\n' + pergunta
