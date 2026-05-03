from Workers.WorkerFlow.suport_functions import verifica_se_cliente_novo_ou_nao

"""Note aqui que não povoamos unidade no banco dentro do fluxo povoa_banco
a unidade já preenchida diretamente no django-admin de forma manual a medidas que novos
contratos são feitos"""

def povoa_banco(id_mensagem, cliente_telefone, conteudo_texto, tipo_mensagem, id_phone_unidade, unidade_telefone,
                data_recebimento, id_hash, retry_count, id_unidade, cursor):



    # Apenas certifica que o cliente existe ou cria. Se for novo ou não, o bot deve prosseguir.
    # Erros explícitos no banco agora explodem a Exception para fora, então não precisamos mais de if not status.
    id_cliente = verifica_se_cliente_novo_ou_nao(cliente_telefone, cursor)

    return








# def povoa_banco(...):
#
#     id_cliente = verifica_se_cliente_novo_ou_nao(cliente_telefone)
#
#     # 🔥 pega ou cria conversa
#     id_conversa, lock_version = adiciona_ou_valida_conversa_ativa_entre_cliente_unidade(
#         id_cliente,
#         id_unidade  # você precisa mapear isso
#     )
#
#     # 🔒 tenta lock
#     lock_ok = tentar_lock_conversa(id_conversa)
#
#     if not lock_ok:
#         print(f"⛔ Conversa {id_conversa} já está sendo processada")
#         return  # 🔥 VOLTA PRO WORKER (sem erro!)
#
#     try:
#         # =====================================================
#         # 🔥 SUA LÓGICA AQUI
#         # =====================================================
#         print(f"🔒 Lock adquirido na conversa {id_conversa}")
#
#         # exemplo:
#         # salvar mensagem
#         # atualizar etapa
#         # enviar resposta
#         # etc...
#
#     finally:
#         # 🔓 SEMPRE libera
#         unlock_conversa(id_conversa)