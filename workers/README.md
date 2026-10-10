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
-> validar a reação ao follow-up ou a resposta normal pelo mesmo fluxo
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
- `retomada_followup.py`: valida a reação com o fluxo normal e a saudação de retorno;
- `repeticao_followup.py`: repetição neutra para contexto inválido no retorno,
  compatibilidade da etapa 8 e recuperação da resposta existente;
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
- Etapa 6: suporte NULL/50/60/70/80, exclusivo do titular até 89. Universal 90+
  prioritária em ambas as rotas. Menores de 18 e dependentes abaixo de 4 com BPA
  ou 5 sem BPA encerram sem contato. Todos esses casos ficam fora do Funil e
  sem bloqueio. O contexto conserva a categoria e o limite usados no envio.
  A recuperação reconhece a resposta da entrada em retry antes de decidir a
  categoria e valida a idade daquela entrada, nunca a idade global. Se necessário,
  reconstrói suporte compatível com a idade; mínimo BPA vem do corpo enviado.
  Não recalcula um motivo já confirmado e não altera commits ou idempotência.
  O validador numérico mantém o contrato 100+ para replay de avanços antigos.
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

### Recuperação de encerramento por idade

A reconstrução em `transacoes/encerramento_atendimento.py` só é usada com
`resposta_ja_existia`: o histórico precisa comprovar a resposta do bot vinculada
à mesma conversa e à mesma entrada em recuperação. Não reclassifica uma conversa
já concluída nem procura uma mensagem qualquer de outro atendimento.

O corpo e o tipo da resposta salva identificam a categoria de encerramento.
`validar_idade(texto_cliente_atual)` extrai um inteiro da entrada vinculada:
`71`, `71 anos`, `71 anos de idade` e `Setenta e um` produzem 71. Nunca comparar
texto livre com o limite nem usar `cliente.idade`, cujos efeitos podem estar
pendentes. Entrada inválida ou ambígua não autoriza inventar uma faixa.

Para suporte comprovado de titular entre 50 e 89, manter o limite atual se
abranger a idade. Se estiver desativado ou não a abranger, usar a maior opção
50/60/70/80 que não ultrapasse a idade. Essa faixa justifica o encaminhamento,
mas não comprova qual configuração exata existia; a reconstrução fica no log.

| Resposta já registrada | Idade extraída | Suporte antes do retry | Resultado |
| --- | --- | --- | --- |
| Suporte de titular | 51 | 60+ | `suporte_idoso_50` |
| Suporte de titular | 71 | 80+ | `suporte_idoso_70` |
| Suporte de titular | 71 | 60+ | `suporte_idoso_60` |
| Universal de titular, enviada com suporte desativado | 91 | 80+ | `idade_universal_90` |
| Universal de dependente, enviada com suporte desativado | 92 | 80+ | `idade_universal_90` |

Nos dois casos universais, a categoria da resposta já enviada tem prioridade.
Para dependentes há ainda a restrição independente de que suporte configurável
é exclusivo de titulares. Nenhum desses casos é convertido em suporte 80+.
Novos atendimentos aplicam a universal a partir de 90, com qualquer configuração.
No retry legado de 100+ sem motivo confirmado, o corpo igual entre versões não
comprova o limiar histórico; conserva-se o motivo genérico. Suporte antigo de
90–99 também permanece genérico. O mínimo BPA vem da resposta efetivamente enviada.

A recuperação conclui o encerramento e a fila `sent` na mesma transação, sem
reenviar a resposta, sem Funil e sem bloqueio de 30 dias por idade. Uma conversa
nova segue as regras atuais: titular de 71 com suporte 80+ continua normalmente.
Se a Meta aceitou o envio, mas nenhuma resposta foi persistida antes da falha,
permanece o risco aceito de novo envio com a configuração atual.

### Saudação de retorno

No caminho normal com `followup_stage = 0`, após a etapa 1,
`valida_historico.py` compara o horário da mensagem atual do
cliente com o último envio do bot confirmado como `sent` na mesma conversa.
Com intervalo de pelo menos três horas e nome disponível, `flow_sender.py`
prefixa a resposta com `Bom te ver novamente, <nome> ☺️`, inclusive quando ela é um
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
Etapas 1–17 admitem novos lembretes; a 18 somente quando a unidade está sem link. As etapas 19–24 são inelegíveis.
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

Os dois textos são montados em `messages/followup_messages.py` com os dados da
releitura após o lock. O primeiro convida a continuar o atendimento e receber a
experiência Supera gratuita na unidade, com rodapé `Estaremos te esperando!`.
Usa o nome do titular já informado no atendimento (nunca nome antigo na etapa 1)
e adapta o convite para dependente com nome ou, sem o nome, “receber vocês”.
O segundo é a despedida personalizada, com rodapé `Abraços, {nome_agente}. 🧡`;
sem nome de dependente coletado, mantém a versão do titular.
Para despachar, todas as condições
precisam continuar válidas na releitura após adquirir o lock:

- conversa ativa, sem finalização, em etapa 1–17 e a 18 somente para unidade sem link não terminal;
- primeiro envio: `followup_stage = 0` (`NULL` equivale a zero); segundo: stage 1
  com recibo do primeiro correspondente ao último bot e ao `followup_last_sent_at`;
- última mensagem da conversa é do bot, confirmada como `sent`, com pelo menos
  sete horas, e `last_interaction_at` corresponde a essa mensagem;
- última mensagem do cliente tem menos de 23h59, reservando um minuto da janela
  de 24 horas; não existe mensagem do cliente com horário igual ou posterior ao bot;
- unidade adimplente, destinatário e números da unidade presentes;
- menos de 12 turnos sem avanço, sem bloqueio persistido ou flood no banco;
- nenhuma fila `pending`/`processing` do par cliente/unidade, inclusive sem vínculo;
- nenhum recibo que já cubra a âncora, nem retomada aberta com fila pendente.
  No segundo, a âncora é o primeiro follow-up, sem encadear um terceiro envio.

Exemplo: bot há 8 horas e cliente há 25 horas não permitem envio; bot há 8 horas
e cliente há 9 horas permitem, se os demais critérios forem atendidos.
O relógio de elegibilidade vem do PostgreSQL. Os limites de etapa e de tempo
são regras do código/SQL, não novas variáveis de ambiente.

O primeiro sucesso persiste histórico, recibo e stage 1 no mesmo commit. Após
outras 7h sem resposta, contadas desse envio, a segunda mensagem persiste histórico,
recibo, stage 2 e encerramento no mesmo commit. Mantém a etapa de origem e não
gera bloqueio de 30 dias. Sem janela de envio, não envia nem encerra silenciosamente.
As duas camadas incluem a etapa 8. Marcações legadas sem recibo não geram despedida.
Uma confirmação da Meta seguida de
falha no commit local ainda pode resultar em duplicidade no retry; o worker
registra `followup_commit_falhou` como crítico.

### Retomada pelo flow

Depois do segundo envio confirmado, o atendimento está encerrado. `valida_banco`
abre nova conversa, sem etapa persistida e com stage zero; o fluxo inicial pede
o nome sem prefixo de retorno. Uma leitura da conversa antiga antes do encerramento
é recusada na releitura sob lock e reagendada sem consumir retry.

No flow, o contexto é relido sob lock. `transacoes/retorno_followup.py` registra
um checkpoint e reutiliza `valida_historico.py` para os dados da etapa, sem
calcular outra saudação de três horas. `retomada_followup.py` chama o `flow_sender`
normal com o prefixo `Bom te ver novamente, <nome> ☺️`. Na etapa 1, omite o nome
antigo; um nome válido na reação é salvo e permite avançar para a 2.

Os resolvers preservam seus validadores e prioridades: resposta válida avança;
mídia, financeiro e reforço recebem os tratamentos já existentes naquela etapa;
contexto inválido genérico usa `repeticao_followup.py` para a pergunta neutra.
A triagem continua aceitando somente as opções canônicas, sem novos tratamentos.
Botões, rodapés e participante são preservados. O prefixo aparece uma vez no
envio e no histórico, inclusive nas mensagens com cabeçalho.

A persistência normal aplica os efeitos, transições e encerramentos cabíveis.
Sem avanço, a primeira reação não incrementa `turnos_sem_avanco`; com transição,
o contador é zerado normalmente. `concluir_retomada` verifica a etapa resultante
e zera `followup_stage`, mantendo `followup_last_sent_at` como auditoria.
Histórico, efeitos, checkpoint, eventual encerramento e fila `sent` são
confirmados **na mesma transação**, sem commit intermediário. Falha reverte todos
esses efeitos. Cache de bloqueio só é publicado após o commit.

Replay de uma resposta já concluída reutiliza seu destino gravado, sem enviar,
reinterpretar a reação, refazer efeitos ou zerar um ciclo posterior. Respostas
da versão antiga continuam recuperáveis, mesmo que tenham repetido a etapa.

Na etapa 8, qualquer reação leva à 9 pelo evento `cliente_retornou`, sem repetir
a 8 nem interpretar a reação como resposta à 9. O histórico do cliente e o
checkpoint mantêm a origem 8; a resposta registra o destino 9.
Stage positivo legado nas etapas 20–23 também usa a validação normal, embora
essas etapas continuem inelegíveis para novos lembretes. A etapa 24 é terminal.

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

## Worker de consumo Meta

`python -m workers.worker_consumo_meta.iniciar_worker_consumo_meta` inicia o
sincronizador de analytics. Ativar com `CONSUMO_META_ENABLED=True` após a migração.
Consulta o mês atual por hora, meses pendentes diariamente e consolida somente
no dia 25 previsto, comparando a leitura anterior de mês completo. Falha/divergência
prorroga a decisão por um mês; `consolidado` encerra coletas automáticas.

O ciclo usa advisory lock próprio de sessão, HTTP fora de transação, agenda
persistida por unidade/mês e upsert protegido de leituras antigas. Não altera
locks, retries ou regras do atendimento, follow-up e Funil. Falhas preservam
totais e última coleta válida. Detalhes em [deploy](../deploy/consumo_mensal_meta.md).

## Reserva com e sem plataforma

A configuração atual de `unidade.link_agendamento` decide a saída da triagem: com link, 17 → 20; sem link, 17 → 18 (preferência de turno) → 19 (contato comercial). A satisfação converge em 21 → 22 → 23 → 24, com salto 22 → 24 na recusa de comentário. As etapas 1–17 conservam suas regras.

`conversa.turno` aceita NULL, manha, tarde ou noite e é salvo somente na transação de 18 → 19. É preferência, não confirmação de agendamento. Qualquer texto posterior na 19 apresenta a nota da 21; não é interpretado como nota nessa mesma interação. Mídia repete a orientação da 19.

O Funil exige 20–24 com link ou 19/21–24 sem link, considerando a configuração vigente na seleção, no claim e no snapshot. Preservar recibo de sucesso se o CRM já aceitou. O snapshot e o painel incluem turno da própria conversa, quando preenchido.

Follow-up proativo: 1–17 em ambas as rotas e 18 somente sem link; a 19 e a 20 não recebem novos lembretes. São preservadas as duas camadas de sete horas, os recibos, o encerramento no segundo lembrete e as guardas existentes. A reação ao primeiro segue a validação normal: um turno válido na 18 avança para 19 e é persistido. Contexto inválido genérico repete; tratamentos específicos continuam prioritários. Retomadas legadas são remapeadas por significado; a exceção 8 → 9 permanece.

Instalação existente exige migração própria: IDs antigos 18/19/20/21/22 tornam-se 20/21/22/23/24. Não executar setup ou seeds no banco de produção nem reaplicar migrações históricas. Preservar o Consumo Meta, seus fusos, worker, relatórios e PDFs, a compatibilidade PyWa 4.5.0, a exceção universal de idade 90+, o comentário livre e a despedida por participante.


## Worker de consulta FireAds

`worker_consulta_dash` executa somente as solicitações persistidas de novas
conversas. Não envia WhatsApp, não altera etapas e não escreve no dashboard.
O flow confirma a pendência e o reagendamento sem consumo de retry; depois aplica
o resultado completo uma única vez. HTTP ocorre no processo separado, com reserva
PostgreSQL e sem transação aberta. Ver [operação e recuperação](../docs/worker_consulta_dash_operacao.md).
