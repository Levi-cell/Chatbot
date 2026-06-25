# Workers

Camada assíncrona responsável por retirar mensagens da fila, interpretar o estado
persistido, enviar respostas e concluir o processamento.

- [Portal do projeto](../README.md)
- [Regras de negócio](../REGRAS_DE_NEGOCIO.md)
- [Padrões de arquitetura](../PADROES_DE_ARQUITETURA.md)

## Estrutura

```text
workers/
├── worker_flow/
│   ├── main_worker.py
│   ├── valida_banco.py
│   ├── valida_historico.py
│   ├── valida_resposta_cliente.py
│   ├── tratar_bloqueio.py
│   ├── suport_functions.py
│   └── response_flow/
├── tratamento_erros_externos/
└── challenge_template.py
```

`challenge_template.py` é apoio operacional e não participa do ciclo principal
do worker.

## Ciclo principal

`worker_flow/main_worker.py` supervisiona o processo. Se `worker_flow()` escapar
com uma exceção, registra o traceback, aguarda e reinicia o fluxo.

`worker_flow/response_flow/flow_worker.py` é o orquestrador do ciclo:

```text
dequeue
-> validar cliente, unidade e conversa
-> vincular fila à conversa
-> adquirir lock
-> respeitar mensagem anterior
-> persistir histórico do cliente
-> rotear e enviar resposta
-> persistir histórico/contexto do bot
-> marcar fila como sent
-> liberar lock e fechar conexão
```

## Propriedade transacional

Conexão, `commit`, `rollback` e `close` do ciclo pertencem ao `flow_worker.py`.
Os commits intermediários são checkpoints recuperáveis:

1. claim da fila;
2. vínculo com a conversa;
3. lock;
4. histórico do cliente;
5. histórico e contexto do bot;
6. status `sent`;
7. unlock.

Uma função auxiliar pode executar uma operação com o cursor recebido, mas não
deve decidir a transação fora do orquestrador.

## Retry e recuperação

- dequeue incrementa `retry_count`;
- `processing` abandonado volta a ser elegível após o timeout do banco;
- falhas tratadas usam `tratamento_erros_externos/expection_process.py`;
- o limite atual é de três tentativas;
- ao atingir o limite, a mensagem é excluída;
- retry com histórico do bot existente não chama a Meta novamente.

O worker mantém a fila sem `sent` quando envio ou persistência final falham.
Depois de uma resposta do bot persistida, o retry repara contexto e conclui a
fila sem duplicar o envio.

## Locks e ordenação

- apenas um worker processa a conversa por vez;
- `lock_version` impede unlock por proprietário antigo;
- uma mensagem posterior não ultrapassa outra anterior aberta;
- espera por mensagem anterior não consome tentativa de erro.

## Response flow

- `rotear_resposta_cliente.py`: escolhe fluxo normal ou tratamento;
- `flow_sender.py`: seleciona o sender da etapa;
- `flow_treat_context.py`: tratamento de resposta fora do contexto da etapa;
- `flow_treat_financial.py`: tratamento de pergunta sobre valor, custo ou
  investimento;
- `flow_treat_unsupported_type.py`: tratamento de mídia ou tipo não suportado;
- `flow_worker.py`: transação, checkpoints e handlers.

Textos e chamadas PyWa não pertencem a essa pasta. Use
`core/integrations/whatsapp/messages` e `pywa_functions`.

## Testes relacionados

- `tests/unit/test_worker_flow_runtime.py`;
- `tests/unit/test_worker_flow_contract.py`;
- `tests/unit/test_worker_support_finalizacao.py`;
- `tests/unit/test_retry_lock_lifecycle.py`;
- `tests/unit/test_lastfrom_semantico.py`;
- `tests/unit/test_flow_sender.py`;
- `tests/unit/test_flow_treat_context.py`;
- `tests/unit/test_flow_treat_financial.py`;
- `tests/unit/test_flow_treat_unsupported_type.py`;
- `tests/unit/test_repositories.py`.
