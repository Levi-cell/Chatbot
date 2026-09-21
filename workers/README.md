# Workers

Camada assíncrona responsável pelo atendimento no WhatsApp, lembretes de
inatividade e publicação periódica de oportunidades no Funil de Vendas.

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
│   │   ├── repeticao_followup.py
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
│   │   ├── retorno_followup.py
│   │   ├── movimento_conversa.py
│   │   ├── finalizacao_fila.py
│   │   ├── lock_conversa.py
│   │   └── ordem_turno.py
│   └── suporte/
│       ├── cache_repair.py
│       └── estado_ciclo.py
├── worker_followup/
│   ├── iniciar_worker_followup.py
│   ├── config.py
│   └── followup_worker.py
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
-> reler conversa sob lock e reconhecer retomada de follow-up
-> persistir histórico do cliente
-> repetir etapa na retomada; nos demais casos, rotear e enviar resposta
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
4. aquisição do lock;
5. vínculo, releitura e histórico do cliente, incluindo o marcador de retomada quando aplicável;
6. renovação do lock antes do envio;
7. histórico e contexto do bot; na retomada, conclusão do marcador e reset do stage;
8. status `sent`, após conferir novamente a posse do lock;
9. unlock.

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
- `repeticao_followup.py`: reapresentação da etapa na reação ao follow-up ou
  legado marcado, preservando a resposta já existente;
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
- Etapa 6: `idade_minima_suporte` aceita NULL (desativado), 50, 60, 70, 80 ou 90.
  Encaminha somente titulares a partir do limite até 99 anos, persiste a idade e
  encerra na etapa 6 com `encaminhado_suporte_idoso`, sem bloqueio ou Funil.
  Dependentes seguem as regras atuais. Pessoas de 100+ conservam o encaminhamento
  próprio para titular ou dependente, mesmo com suporte desativado.
  Na recuperação, as cinco mensagens oficiais identificam a resposta já enviada;
  uma reavaliação usa o limite atual, sem recuperar a configuração anterior.
  A barreira de idempotência impede reenvio e não cria avanço de etapa.
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
- Etapa 11: `Começar triagem`, o callback do botão e confirmações textuais como
  `iniciar triagem`, `sim` e `vamos começar` autorizam o início. A classificação
  permanece no validador contextual da etapa, após os tratamentos universais.

No retry já respondido da etapa 10, o resultado aceito do e-mail é reconstruído
pelo histórico original, sem nova chamada à Meta nem reavaliação pela política
de e-mail atual da unidade.

No encaminhamento por idade da etapa 6, o histórico comprova a resposta já
enviada, e a reavaliação do encerramento usa o limite atual da unidade. Se esse
limite estiver desativado ou não abranger mais a idade do titular, a recuperação
não encerra por suporte, não reenvia a resposta nem avança automaticamente a
etapa. O limite anterior não é restaurado e o histórico original é preservado.

### Saudação de retorno

No caminho normal com `followup_stage = 0`, após a etapa 1,
`valida_historico.py` compara o horário da mensagem atual do
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
- `tests/unit/test_sondas_funil.py`;
- `tests/unit/test_followup.py`;
- `tests/integration/test_followup_postgres.py`.

O núcleo transacional e os testes específicos estão descritos em
[`tests/README.md`](../tests/README.md).

## Worker de follow-up

`worker_followup/iniciar_worker_followup.py` é o quarto serviço da VM. Seu laço
seleciona candidatos pelo PostgreSQL e chama `followup_worker.py`, proprietário
da conexão e dos commits proativos. Não faz dequeue nem chama validadores de etapas.
`FOLLOWUP_WORKER_ENABLED` é falso por padrão em execução manual; a unit systemd
o habilita explicitamente. Lote padrão: 20; intervalo entre lotes: 60 segundos.
As candidatas são processadas uma por vez, com lock e transações independentes.
Somente etapas 1–17 admitem novos lembretes; etapas 18–22 são inelegíveis.
A paginação visita candidatos posteriores mesmo quando os primeiros falham.
Uma falha individual não interrompe o lote. A candidata pode ser tentada novamente
quando a paginação voltar ao início, depois de revalidar todas as condições; não
há promessa de retry no lote imediatamente seguinte ou de reenvio fora da janela Meta.

### Configuração e elegibilidade

| Variável | Padrão no Python | Valores aceitos |
|---|---|---|
| `FOLLOWUP_WORKER_ENABLED` | `False` | Booleano; a unit configura `true`. |
| `FOLLOWUP_POLL_SECONDS` | `60` | 5–3.600 segundos de espera após cada lote. |
| `FOLLOWUP_BATCH_SIZE` | `20` | 1–100 candidatas por lote; processamento sequencial. |

O texto é `Você viu a minha mensagem?`. Para despachar, todas as condições
precisam continuar válidas na releitura após adquirir o lock:

- conversa ativa, sem finalização, em etapa 1–17 não terminal;
- `followup_stage = 0` (`NULL` é tratado como zero);
- última mensagem da conversa é do bot, confirmada como `sent`, com pelo menos
  sete horas, e `last_interaction_at` corresponde a essa mensagem;
- última mensagem do cliente tem menos de 23h59, reservando um minuto da janela
  de 24 horas; não existe mensagem do cliente com horário igual ou posterior ao bot;
- unidade adimplente, destinatário e números da unidade presentes;
- menos de 12 turnos sem avanço, sem bloqueio persistido ou flood no banco;
- nenhuma fila `pending`/`processing` do par cliente/unidade, inclusive sem vínculo;
- nenhum recibo que já cubra a âncora ou o próprio lembrete, nem retomada aberta com fila pendente.

Exemplo: bot há 8 horas e cliente há 25 horas não permitem envio; bot há 8 horas
e cliente há 9 horas permitem, se os demais critérios forem atendidos.
O relógio de elegibilidade vem do PostgreSQL. Os limites de etapa e de tempo
são regras do código/SQL, não novas variáveis de ambiente.

O sucesso persiste histórico, recibo e stage 1 no mesmo commit. Não há segunda
mensagem enquanto o cliente não reagir. Uma confirmação da Meta seguida de
falha no commit local ainda pode resultar em duplicidade no retry; o worker
registra `followup_commit_falhou` como crítico.

### Retomada pelo flow

No flow, o contexto é relido depois do lock. `transacoes/retorno_followup.py` registra
a reação e recupera a prova de repetição. `response_flow/repeticao_followup.py`
chama os senders normais da etapa, sem resolvers de negócio. A renovação do lock
antes do envio acrescenta um checkpoint; persistência final e finalização da fila
validam a posse antes de alterar dados. Repositórios não controlam commits.
Stage positivo, por lembrete ou migração inicial, prefixa a repetição com
`Que bom te ver novamente, <nome>!` ou `Que bom te ver novamente!` sem nome salvo.
Na etapa 1, o worker sempre omite o nome, inclusive para cliente antigo com nome
no cadastro, e mantém a pergunta de nome desse atendimento. A reação não valida
o nome nem avança a etapa; o cadastro anterior não é apagado.
O histórico guarda exatamente o texto enviado. Stage zero mantém `Olá novamente`
na regra existente de três horas.

A primeira reação é guardada, mas não valida nem avança a etapa. A repetição
mantém botões e dados persistidos; não altera `turnos_sem_avanco`, Funil ou
encerramento. Stage zero, histórico da repetição e conclusão do marcador só são
confirmados juntos após o envio. `followup_last_sent_at` permanece como auditoria.
Falha preserva a retomada; replay concluído não reenvia nem zera um ciclo posterior.
O legado marcado também pode repetir etapas 18–21, embora elas não recebam
proativos. A etapa terminal 22 não é repetível por esse caminho.

### Operação e logs

`SIGTERM`/`SIGINT` sinalizam parada e interrompem a espera entre lotes; uma
candidata já em andamento passa pela limpeza da conexão e do lock. Falhas de
consulta usam espera exponencial de 5 até 300 segundos. A unit usa
`Restart=on-failure`, `RestartSec=5s` e `TimeoutStopSec=100s`.

`followup_iniciado` informa a configuração. `followup_despacho` antecede a chamada
externa, e `followup_confirmado` confirma a persistência local. Não há log INFO a
cada varredura vazia; ausência de despachos não comprova falha. Para consultar
candidatas sem envio, use o [diagnóstico](../utilitarios/README.md#diagnóstico-de-follow-up).

Deploy: preparar banco e código, reiniciar flow compatível, então iniciar follow-up.
Rollback: parar o proativo primeiro e manter flow compatível enquanto houver stage
positivo ou retomadas pendentes. Desligar o serviço não limpa esses registros.
Os comandos completos ficam na [rotina de deploy](../regras_deploy/rotina_deploy.md)
e no [guia de ativação](../deploy/README.md#ativação-do-follow-up).
