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
│   │   ├── encerramento_atendimento.py
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
└── tratamento_erros_externos/
```

## Ciclo principal

`worker_flow/iniciar_flow_worker.py` supervisiona o processo. Se
`worker_flow()` escapar com uma exceção, registra o traceback, aguarda e
reinicia o fluxo.

`worker_flow/response_flow/flow_worker.py` é o orquestrador do ciclo:

```text
dequeue
-> respeitar mensagem anterior
-> validar cliente, unidade e conversa
-> barrar conversa com bloqueio vigente
-> adquirir lock
-> vincular fila à conversa
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
2. espera por mensagem anterior, quando necessária;
3. validação do banco;
4. lock e vínculo com a conversa;
5. histórico do cliente;
6. histórico e contexto do bot;
7. status `sent`;
8. unlock.

Uma função auxiliar pode executar uma operação com o cursor recebido, mas não
deve decidir a transação fora do orquestrador.

### Vínculo da fila com a conversa

O vínculo `fila_mensagens.id_conversa` é uma anotação de integridade e
ordenação; ele não é o lock de turno e não substitui a resolução atual por
`(cliente, unidade)`.

O repositório preenche o vínculo quando ele está vazio ou já aponta para a mesma
conversa. Um vínculo legado divergente só é reparado quando a fila ainda não tem
histórico. Se nenhuma linha puder ser vinculada com segurança, o worker falha
fechado: devolve a mensagem para `pending` por 300 segundos, sem consumir uma
tentativa de erro e sem enviar resposta.

Se a conversa anterior continuar ativa, a mensagem permanece na mesma conversa
e segue a etapa já atualizada. Se o encerramento tiver bloqueio vigente, a
mensagem é removida como conversa bloqueada. Uma conversa nova só é resolvida
quando o encerramento permite recomeço imediato (`bloqueio_dias = 0`) ou quando
o bloqueio já expirou.

As barreiras que continuam decidindo o atendimento são:

- advisory lock do turno por cliente e unidade no webhook;
- lock versionado da conversa no worker;
- verificação de mensagem anterior ainda aberta;
- `resposta_bot_para_mensagem_atual`, que impede novo envio em um retry.

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
- a verificação de mensagem anterior ocorre logo depois do claim, antes de
  resolver conversa e tentar seu lock;
- espera por mensagem anterior (30 segundos) ou lock recusado (5 segundos) não
  consome tentativa de erro.

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

### Regras atuais das etapas

- Etapa 4: profissão válida é persistida em `conversa.profissao` e atualiza
  também `cliente.profissao`. O snapshot da conversa preserva o atendimento
  anterior quando o cadastro do cliente muda.
- Etapa 6: `suporte_idoso=True` encaminha somente o próprio titular entre 60 e
  99 anos ao número comercial da unidade. O worker persiste a idade e encerra
  na própria etapa 6 com `encaminhado_suporte_idoso`, sem bloqueio de dias.
  Dependentes não entram nessa regra; idade de 100 anos ou mais conserva o
  encerramento próprio por idade inválida. Com suporte desativado, o titular
  de 60 a 99 anos segue para a oferta.
- Etapa 7: confirmações de aceite geram `oferta_aceita` (`7 -> 10`);
  `Talvez mais tarde` gera `oferta_adiada` (`7 -> 8`). Pedidos como
  `quero mais informações` ou `quero saber mais` não são aceite; assim como
  negativas livres, recebem tratamento sem avançar.
- Etapa 10: a política parte de `email_obrigatorio` da unidade, mas o próprio
  titular de 60 a 99 anos fica dispensado quando chega a essa etapa. A exceção
  não se aplica ao dependente nem à idade do responsável. Mídia, reforço e
  financeiro são tratados antes da coleta. Com e-mail opcional, a resposta
  pode avançar como endereço válido, ausência declarada ou não informado;
  os três casos usam `email_valido` (`10 -> 11`). Sem endereço, o efeito grava
  `cliente.email = NULL`, sem manter um e-mail de atendimento anterior.

No retry já respondido, o resultado aceito do e-mail e o encaminhamento de
suporte são reconstruídos pelo histórico original, sem nova chamada à Meta
nem reavaliação da decisão pela configuração atual da unidade.

### Saudação de retorno

Após a etapa 1, `valida_historico.py` compara o horário da mensagem atual do
cliente com o último envio do bot confirmado como `sent` na mesma conversa.
Com intervalo de pelo menos três horas e nome disponível, `flow_sender.py`
prefixa a resposta com `Olá novamente, <nome>!`, inclusive quando ela é um
tratamento. O texto enviado e o histórico recebem o mesmo prefixo uma vez.

Essa saudação não é follow-up nem disparo por inatividade: depende de uma nova
mensagem do cliente, não cria mensagem separada e não altera a transição. A
etapa 1, dados de nome/data ausentes ou incompatíveis e retries com resposta
persistida não geram uma nova saudação.

## Persistência de transições

As responsabilidades estão divididas assim:

- `transacoes/persistencia_resposta.py`: orquestra a persistência final;
- `transacoes/movimento_conversa.py`: classifica e persiste inicialização,
  transição ou permanência;
- `transacoes/efeitos_transicao.py`: exibe cada ponte como
  `origem + evento -> destino` e grava seus efeitos específicos;
- `transacoes/encerramento_atendimento.py`: resolve e aplica encerramentos,
  inclusive a reconstrução do encaminhamento ao suporte no retry.

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
aguarda `FUNIL_INTERVALO_SEGUNDOS` depois do sucesso (padrão: 1.800 segundos,
30 minutos) e recupera indisponibilidade esperada do
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
-> aguardar FUNIL_INTERVALO_SEGUNDOS
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
reenviado após o lease. O título atual é `Chatbot Lead <nome_unidade>` e não
contém o ID da conversa; ele não identifica sozinho um envio nem impede
duplicidade externa. Não há reconciliação automática com o CRM.

O processo nasce desativado. `FUNIL_WORKER_ENABLED=True` deve ser configurado
somente depois do teste manual da unidade. O ponto de entrada é
`python -m workers.worker_funil.iniciar_worker_funil`; o serviço de produção
está em
[`deploy/systemd/chatbot-worker-funil.service`](../deploy/systemd/chatbot-worker-funil.service).

## Testes relacionados

- `tests/unit/test_worker_flow_runtime.py`;
- `tests/unit/test_persistencia_essencial.py`;
- `tests/unit/test_retry_essencial.py`;
- `tests/unit/test_fluxo_turno_abc.py`;
- `tests/unit/test_suporte_idoso_email_obrigatorio.py`;
- `tests/unit/test_saudacao_retorno.py`;
- `tests/unit/test_validador_profissao.py`;
- `tests/unit/test_valida_etapa7.py`;
- `tests/unit/test_sondas_funil.py`.

O núcleo transacional e os testes específicos estão descritos em
[`tests/README.md`](../tests/README.md).
