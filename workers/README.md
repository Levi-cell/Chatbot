# Workers

Camada assíncrona responsável pelo atendimento no WhatsApp e pela publicação
periódica de oportunidades no Funil de Vendas.

- [Portal do projeto](../README.md)
- [Regras de negócio](../REGRAS_DE_NEGOCIO.md)
- [Padrões de arquitetura](../PADROES_DE_ARQUITETURA.md)
- [Rotina de implementação de etapas](../ROTINA_IMPLEMENTACAO_ETAPAS.md)

## Estrutura

```text
workers/
├── worker_flow/
│   ├── iniciar_flow_worker.py
│   ├── valida_banco.py
│   ├── valida_historico.py
│   ├── tratar_bloqueio.py
│   ├── response_flow/
│   │   ├── flow_worker.py
│   │   ├── flow_sender.py
│   │   ├── etapas/
│   │   │   ├── validadores_universais/
│   │   │   └── validadores_contexto/
│   │   └── transicoes/
│   │       ├── contexto_transicao.py
│   │       ├── eventos.py
│   │       └── resolver_transicao.py
│   ├── transacoes/
│   │   ├── efeitos_transicao.py
│   │   ├── persistencia_resposta.py
│   │   ├── movimento_conversa.py
│   │   ├── finalizacao_fila.py
│   │   ├── lock_conversa.py
│   │   └── ordem_turno.py
│   └── suporte/
│       ├── cache_repair.py
│       └── estado_ciclo.py
├── worker_funil/
│   ├── iniciar_worker_funil.py
│   ├── config.py
│   ├── funil_worker.py
│   ├── processamento.py
│   └── exceptions.py
├── tratamento_erros_externos/
└── challenge_template.py
```

`challenge_template.py` é apoio operacional e não participa do ciclo principal
do worker.

## Ciclo principal

`worker_flow/iniciar_flow_worker.py` supervisiona o processo. Se
`worker_flow()` escapar com uma exceção, registra o traceback, aguarda e
reinicia o fluxo.

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

- `flow_worker.py`: transação, checkpoints e handlers.
- `flow_sender.py`: preserva `resposta_bot_atual` e seleciona o resolver da
  etapa atual;
- `etapas/resolver_etapa<n>.py`: valida a resposta, aplica tratamentos e
  encaminha para o destino autorizado;
- `etapas/validadores_universais/`: mídia, financeiro, nome, opções da triagem
  e outras validações reutilizáveis;
- `etapas/validadores_contexto/`: respostas específicas de cada pergunta;
- `transicoes/contexto_transicao.py`: transforma o resultado da consulta em
  origem e mapa explícitos no contexto histórico;
- `transicoes/resolver_transicao.py`: decide `origem + evento -> destino`.

Textos e chamadas PyWa não pertencem a essa pasta. Use
`core/integrations/whatsapp/messages` e
`core/integrations/whatsapp/pywa_functions/pywa_senders`.

Tratamentos não produzem evento e permanecem na etapa atual. Respostas válidas
utilizam a tabela `chatbot.etapa_transicao`; o destino não é calculado com
`id_etapa + 1`.

Validadores universais mantêm o mesmo significado em todas as etapas e não
escolhem entre arestas diferentes. Quando uma resposta pode gerar destinos
distintos, o validador é contextual e devolve diretamente o evento daquela
origem, mesmo que outra etapa reconheça os mesmos textos com eventos próprios.

## Persistência de transições

As responsabilidades estão divididas assim:

- `transacoes/persistencia_resposta.py`: orquestra a persistência final;
- `transacoes/movimento_conversa.py`: classifica e persiste inicialização,
  transição ou permanência;
- `transacoes/efeitos_transicao.py`: exibe cada ponte como
  `origem + evento -> destino` e grava seus efeitos específicos.

Fluxo:

```text
histórico do bot
-> movimento da conversa e confirmação da aresta no PostgreSQL
-> efeitos específicos da transição
```

O `flow_worker.py` continua dono do commit e rollback. Os repositórios recebem o
cursor e não controlam a transação.

## Worker do Funil

`worker_funil` é independente do atendimento. Ele não consome
`fila_mensagens`, não envia WhatsApp e não altera o mapa de transições.

`funil_worker.py` possui o laço operacional interno: executa um ciclo completo,
aguarda uma hora depois do sucesso e recupera indisponibilidade esperada do
banco com espera linear de 5 em 5 segundos, limitada a 60. O arquivo
`iniciar_worker_funil.py` possui o laço supervisor externo. Se uma falha crítica
escapar do worker, ele aguarda 5 segundos fixos e cria o worker novamente.

```text
materializar conversas em etapas elegíveis
-> claim de um funil_envios com FOR UPDATE SKIP LOCKED
-> commit da reserva
-> montar snapshot do cliente/dependente/triagem
-> encerrar a transação de leitura
-> criar uma oportunidade na ApiCarrossel
-> marcar lead_no_funil e funil_envios=sent no mesmo commit local
-> repetir até o limite do lote
-> aguardar uma hora
```

Cada lead é isolado. Falha de payload ou API volta o item para `pending`, agenda
a próxima tentativa e permite processar os demais. Indisponibilidade operacional
do banco é recuperada pelo laço interno; defeitos críticos escapam para o
supervisor externo.

O claim possui lease: um item abandonado em `processing` volta a ser elegível
depois de `FUNIL_LEASE_SEGUNDOS`. Isso permite recuperação de processo morto e
protege múltiplas instâncias com `SKIP LOCKED`.

Não existe transação distribuída entre PostgreSQL e Funil. Se o CRM confirmar e
o banco cair antes do commit local, o item permanece `processing` e poderá ser
reenviado após o lease. O título `Chatbot Lead [C<id_conversa>]` permite
reconciliação manual; consulta automática é evolução futura.

O processo nasce desativado. `FUNIL_WORKER_ENABLED=True` deve ser configurado
somente depois do teste manual da unidade. Quando ativo, `main.py` abre um
terceiro terminal exclusivamente para ele.

## Testes relacionados

- `tests/unit/test_worker_flow_runtime.py`;
- `tests/unit/test_roteamento_essencial.py`;
- `tests/unit/test_persistencia_essencial.py`;
- `tests/unit/test_retry_essencial.py`;
- `tests/unit/test_lastfrom_semantico.py`;
- `tests/unit/test_validadores_essenciais.py`;
- `tests/unit/test_efeitos_triagem.py`;
- `tests/unit/test_transicoes_etapa.py`;
- `tests/unit/test_funil_essencial.py`.
