"""Persistência da coleta na transação já protegida pelo lock da conversa."""

from copy import deepcopy
from psycopg.errors import UniqueViolation
from psycopg.types.json import Jsonb
from core.repositories.atendimento.dependentes import inserir_dependente_para_conversa
from core.repositories.atendimento.turnos import salvar_turno_conversa
from core.validacoes.coleta_abertura import aceito, valor, campo, etapa_inicial


def salvar(id_conversa, estado, cursor):
    cursor.execute('UPDATE chatbot.conversa SET contexto_coleta=%s WHERE id_conversa=%s',
                   (Jsonb(estado), id_conversa))
    if cursor.rowcount != 1:
        raise ValueError('Conversa ausente ao salvar coleta')


def importar(abertura, id_conversa, estado, cursor):
    estado = deepcopy(estado)
    if aceito(estado, 'nome'):
        cursor.execute('UPDATE chatbot.cliente SET nome=%s WHERE id_cliente=%s',
                       (valor(estado, 'nome'), abertura['id_cliente']))
    if aceito(estado, 'email'):
        cursor.execute('SAVEPOINT coleta_email')
        try:
            cursor.execute('UPDATE chatbot.cliente SET email=%s WHERE id_cliente=%s',
                           (valor(estado, 'email'), abertura['id_cliente']))
        except UniqueViolation:
            cursor.execute('ROLLBACK TO SAVEPOINT coleta_email')
            estado['campos']['email'].update(status='conflitante', valor=None, motivo='email_em_outro_cliente')
        finally:
            cursor.execute('RELEASE SAVEPOINT coleta_email')
    if aceito(estado, 'destinatario'):
        dependente = valor(estado, 'destinatario')['dependente']
        cursor.execute('UPDATE chatbot.conversa SET status_dependente=%s WHERE id_conversa=%s',
                       (dependente, id_conversa))
        if dependente:
            inserir_dependente_para_conversa(id_conversa, cursor)
    if estado.get('coletar_turno') and aceito(estado, 'turno'):
        salvar_turno_conversa(id_conversa, abertura['id_unidade'], valor(estado, 'turno'), cursor)
    estado.update(status='pronto', etapa_inicial=etapa_inicial(estado))
    salvar(id_conversa, estado, cursor)
    return estado


def guardar_coletas(contexto, efeitos, cursor):
    if not contexto.get('contexto_coleta') or not efeitos:
        return
    cursor.execute('SELECT contexto_coleta FROM chatbot.conversa WHERE id_conversa=%s FOR UPDATE',
                   (contexto['id_conversa'],))
    estado = cursor.fetchone()[0]
    if efeitos.get('cliente_nome_atualizado'):
        estado['campos']['nome'] = campo([efeitos['primeiro_nome_cliente']], 'nome', 'atendimento')
    if efeitos.get('cliente_email_atualizado'):
        cursor.execute('SELECT email FROM chatbot.cliente WHERE id_cliente=%s', (contexto['id_cliente'],))
        estado['campos']['email'] = campo([cursor.fetchone()[0] or ''], 'email', 'atendimento')
        estado['resultado_email'] = efeitos['resultado_coleta_email']
    if efeitos.get('status_dependente_atualizado'):
        texto = 'Para dependente' if efeitos['status_dependente'] else 'Para mim'
        estado['campos']['destinatario'] = campo([texto], 'destinatario', 'atendimento')
    if efeitos.get('turno_persistido'):
        estado['campos']['turno'] = campo([efeitos['turno']], 'turno', 'atendimento')
    if efeitos.get('destino_dado') == 'cliente':
        cursor.execute('SELECT idade FROM chatbot.cliente WHERE id_cliente=%s', (contexto['id_cliente'],))
        estado['idade_titular'] = cursor.fetchone()[0]
    salvar(contexto['id_conversa'], estado, cursor)
