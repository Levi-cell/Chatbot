"""Envio da abertura adaptada com o contrato de persistência dos demais senders."""

from pywa.types import Button
from core.integrations.whatsapp.exceptions import ErroEnvioMeta
from core.integrations.whatsapp.messages.abertura_coleta import montar_abertura
from core.integrations.whatsapp.messages.etapa2_messages import montar_botoes_etapa2
from core.integrations.whatsapp.messages.componentes_compartilhados import RODAPE_OPCAO_UNICA, montar_texto_com_rodape
from core.integrations.whatsapp.pywa_functions.cliente import conta_wa
from core.integrations.whatsapp.pywa_functions.resposta_envio import extrair_id_hash_msg_bot
from core.integrations.whatsapp.pywa_functions.saudacao import obter_saudacao_por_horario


def enviar_abertura_coleta(contexto, *, tratamento=None):
    mensagem = contexto['mensagem_cliente_atual']
    etapa = contexto['contexto_coleta']['etapa_inicial']
    texto = montar_abertura(contexto, obter_saudacao_por_horario(), tratamento)
    argumentos = {'to': mensagem['cliente_telefone'], 'text': texto}
    if etapa == 2:
        texto = montar_texto_com_rodape(texto, RODAPE_OPCAO_UNICA)
        argumentos.update(text=texto, buttons=[Button(title=b, callback_data=b) for b in montar_botoes_etapa2()])
    try:
        enviado = conta_wa(mensagem['id_phone_unidade']).send_message(**argumentos)
        resultado = {'enviou': True, 'resposta_ja_existia': False, 'mensagem_bot': texto,
                     'id_hash_msg_bot': extrair_id_hash_msg_bot(enviado), 'id_etapa_resultante': etapa,
                     'tipo_mensagem': 'interactive_button' if etapa == 2 else 'text',
                     'canal': 'meta_whatsapp', 'atualizar_conversa': True, 'atualizar_last_from_bot': True}
        if etapa == 2:
            resultado['rodape_mensagem'] = RODAPE_OPCAO_UNICA
        if tratamento:
            resultado.update(tratamento=True, tipo_tratamento=tratamento)
        return resultado
    except Exception as erro:
        raise ErroEnvioMeta('Meta falhou ao enviar abertura adaptada', id_etapa=etapa,
                            phone_id_unidade=mensagem['id_phone_unidade'],
                            cliente_telefone=mensagem['cliente_telefone']) from erro
