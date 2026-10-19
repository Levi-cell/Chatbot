# Regras de negócio do Chatbot - V1

## Finalidade

Este documento é a fonte de verdade para interpretar o comportamento do sistema.
Antes de classificar algo como bug ou alterar o worker, webhook, fila, histórico,
conversa, cache ou banco de dados, estas regras devem ser consultadas.

Uma proteção que aparentemente descarta, bloqueia ou repete um processamento pode
ser uma decisão deliberada da V1. Alterar uma dessas regras representa uma mudança
de produto, e não apenas uma refatoração técnica.

## Definições

- **Cliente:** identificado por `wa_id` ou `cliente_telefone`.
- **Unidade:** identificada por `phone_number_id` ou `id_phone_unidade`.
- **Turno:** interação do par `(cliente_telefone, id_phone_unidade)` que aguarda
  uma resposta do bot.
- **Mensagem aceita:** mensagem que passou pelas validações do webhook e foi
  persistida em `chatbot.fila_mensagens`.
- **Mensagem respondida:** mensagem da fila que possui histórico do bot com
  `status_envio = 'sent'`, vinculado ao seu `id_mensagem_fila` e ao hash da
  mensagem original do cliente.
- **Fonte de verdade:** dado persistido no PostgreSQL. O Redis acelera consultas,
  mas não substitui o banco de dados como fonte definitiva.

## 1. Um turno por vez

Para cada par `(cliente_telefone, id_phone_unidade)`, a V1 deve manter no máximo
uma mensagem aberta ainda sem resposta própria do bot. A decisão não depende
somente de `fila_mensagens.status`; ela combina filas abertas com a resposta do
bot especificamente vinculada a cada mensagem.

- A prioridade é determinada exclusivamente pela ordem de chegada, e não pelo
  tamanho, conteúdo ou aparente importância da mensagem.
- A primeira mensagem válida será persistida na fila.
- Enquanto essa primeira mensagem estiver `pending` ou `processing` e ainda não
  possuir sua própria resposta persistida do bot, qualquer mensagem posterior do
  mesmo cliente para a mesma unidade será descartada pelo webhook.
- A mensagem descartada não será inserida na fila nem no histórico. Para o banco,
  ela nunca existiu.
- Quando todas as filas `pending` ou `processing` já possuírem sua própria
  resposta do bot, o webhook poderá aceitar a primeira mensagem do próximo turno,
  mesmo que a limpeza da fila anterior ainda não tenha chegado ao commit de
  `fila_mensagens.status = 'sent'`.
- A decisão é serializada por `pg_advisory_xact_lock`, utilizando unidade e
  cliente como chaves.

Exemplo de comportamento esperado:

```text
cliente: oi
cliente: olá, quero solicitar determinada coisa
```

Nesse exemplo, `oi` chegou primeiro e é a única mensagem válida do turno. O bot
deverá responder somente a `oi`. A mensagem `olá, quero solicitar determinada
coisa` será descartada no webhook e não aparecerá na fila nem no histórico.

O objetivo não é escolher a mensagem mais completa ou mais útil. O objetivo é
garantir uma única entrada por turno e impedir que várias mensagens enviadas
antes da resposta do bot sejam interpretadas como etapas independentes.

### 1.1. Por que `fila_mensagens.status = 'sent'` não é a única fonte da decisão

`sent` continua sendo o estado terminal que confirma a conclusão administrativa
da fila. Porém, ele não é a única prova de que o turno funcional foi respondido.
A prova mais importante para recuperação é o histórico do bot vinculado à
mensagem específica por:

```text
id_conversa
id_mensagem_fila
id_hash_cliente_origem
```

Se a Meta confirmou o envio, o histórico do bot foi persistido e
`last_message_from` foi atualizado para `bot`, o cliente já recebeu a resposta.
O worker ainda pode cair antes do commit separado que altera a fila para `sent`.
Utilizar somente o status da fila faria o webhook descartar a resposta seguinte
do cliente durante essa janela, embora ela já pertença legitimamente ao próximo
turno.

O webhook atual usa o histórico específico do bot como prova de resposta. Ele não
libera uma mensagem apenas porque o `last_message_from` geral da conversa está
como `bot`; cada fila aberta precisa possuir sua própria resposta correspondente.

### 1.2. Recuperação detalhada entre resposta do bot e `sent`

#### Etapa 1 - A foi respondida, mas o worker caiu

```text
Fila A: processing
Histórico do cliente A: existe
Histórico do bot A: existe
last_message_from: bot
Lock da conversa: ocupado
```

O worker cai antes de marcar A como `sent`. A resposta já chegou ao WhatsApp do
cliente, mas A permanece `processing` por aproximadamente 2 minutos.

#### Etapa 2 - o cliente envia B

O webhook encontra A aberta, mas também encontra a resposta do bot vinculada
especificamente a A. B é a primeira mensagem do próximo turno e pode entrar:

```text
Fila A: processing, respondida
Fila B: pending, sem resposta
```

#### Etapa 3 - outro ciclo seleciona B

Antes de resolver a conversa ou tentar seu lock, o worker procura uma mensagem
anterior ainda aberta para o mesmo cliente e unidade. Como A continua
`processing`, B é devolvida para `pending` por 30 segundos. Essa espera não
consome tentativa de erro.

```text
Fila A: processing, respondida
Fila B: pending, sem resposta
```

#### Etapa 4 - o cliente envia C

O webhook examina individualmente todas as filas abertas:

| Fila | Status | Resposta própria do bot |
|---|---|---|
| A | `processing` | Sim |
| B | `pending` | Não |

Como B ainda não possui resposta própria:

```text
todas_abertas_respondidas = False
```

C é descartada e nunca entra no banco. O `last_message_from = 'bot'` deixado por
A não libera C, porque não existe histórico do bot vinculado especificamente a B.

#### Etapa 5 - B aguarda a recuperação de A

Enquanto A continuar aberta, cada claim de B repetirá a verificação de ordem e a
devolverá para `pending` por 30 segundos, sem tentar o lock da conversa:

```text
Fila A: processing, respondida
Fila B: pending, sem resposta
```

C e quaisquer mensagens posteriores continuarão bloqueadas por B.

#### Etapa 6 - A retorna após o timeout

Depois de aproximadamente 2 minutos:

1. A fica elegível novamente;
2. o lock antigo já expirou após 110 segundos;
3. outro worker adquire o lock;
4. encontra o histórico do bot vinculado a A;
5. não envia uma resposta duplicada;
6. marca A como `sent`;
7. libera o lock.

```text
Fila A: sent
Fila B: pending
```

#### Etapa 7 - B é processada

B já não encontra mensagem anterior aberta, resolve a conversa, adquire o lock e
segue normalmente. Se esse lock for recusado por outro motivo, B volta para
`pending` por 5 segundos, também sem consumir uma tentativa de erro.
Enquanto B não possuir sua própria resposta do bot, qualquer C será descartada.

Depois que a resposta de B for persistida, a primeira mensagem do próximo turno
poderá entrar, inclusive na pequena janela anterior ao commit de `sent` de B.

### 1.3. Limite prático de mensagens abertas

Na recuperação descrita, o sistema poderá manter temporariamente:

```text
1 mensagem antiga respondida, mas ainda processing
+
1 mensagem nova sem resposta
```

Isso não cria uma sequência ilimitada. Assim que B entra sem resposta própria,
C, D, E e todas as mensagens seguintes são descartadas pelo webhook. O advisory
lock do turno também impede que B e C sejam aceitas simultaneamente por uma
corrida entre requisições.

Implementação principal:

- `core/repositories/seguranca/turno_cliente.py`
- `callback/webhook/services/populating_fila_mensagens.py`

## 2. Idempotência na entrada do webhook

- `fila_mensagens.id_hash_msg` é único.
- A repetição do mesmo evento pela Meta não deve criar outra linha na fila.
- `ON CONFLICT DO NOTHING` é o comportamento esperado para o mesmo
  `id_hash_msg`.
- Uma mensagem nova possui outro hash e continua sujeita à regra de turno.

Ignorar um webhook duplicado não é bug.

## 3. Primeira mensagem do turno

A primeira mensagem válida deverá ser persistida na fila quando não existir outra
mensagem aberta sem resposta para o mesmo cliente e unidade.

É considerado bug quando a primeira mensagem, ou a única mensagem enviada no
turno, é ignorada sem que alguma regra explícita deste documento seja aplicável.

## 4. Estados e tentativas da fila

Estados utilizados:

- `pending`: aguardando processamento.
- `processing`: reservada por um worker.
- `sent`: processamento e resposta concluídos.
- `failed`: permitido pelo schema, mas não é o destino utilizado atualmente
  quando o limite de tentativas é atingido.

Regras da V1:

- O dequeue altera a mensagem para `processing` e incrementa `retry_count`.
- Uma mensagem `processing` abandonada poderá ser retomada depois de 2 minutos.
- Erros tratados reagendam a mensagem para 2 minutos depois, enquanto ainda
  houver tentativa disponível.
- O limite é de 3 tentativas de processamento.
- Ao identificar `retry_count >= 3`, a mensagem é excluída.
- Não existe uma quarta tentativa.

A exclusão ao atingir o limite de 3 tentativas é uma regra de negócio confirmada
da V1, e não um bug. Alterar esse comportamento para `failed`, dead-letter ou um
número maior de tentativas exige uma nova decisão de produto.

Implementação principal:

- `core/database/deploy_database/bank_script.py`, função `chatbot.dequeue_message()`
- `workers/tratamento_erros_externos/expection_process.py`
- `core/repositories/atendimento/fila.py`

## 5. Ordenação e exclusão mútua

- Uma conversa deve ser processada por apenas um worker por vez.
- O lock da conversa poderá ser retomado se estiver abandonado por mais de 110
  segundos.
- `lock_version` impede que um worker antigo libere o lock adquirido por um
  worker mais novo.
- Uma mensagem não poderá ultrapassar outra mensagem anterior ainda aberta na
  mesma conversa.
- A ordem utiliza `received_data_hora` e, em caso de empate, `id_mensagem`.
- Uma mensagem posterior que encontrar outra anterior aberta será reagendada sem
  consumir uma tentativa de erro.

Implementação principal:

- `core/database/deploy_database/bank_script.py`, funções `lock_conversa()` e
  `unlock_conversa()`
- `core/repositories/atendimento/conversas.py`
- `core/repositories/atendimento/fila.py`
- `workers/worker_flow/transacoes/lock_conversa.py`
- `workers/worker_flow/transacoes/ordem_turno.py`

## 6. Conversa ativa e bloqueio por 30 dias

- Poderá existir somente uma conversa ativa para o mesmo cliente e unidade.
- Essa garantia é protegida pelo índice parcial `idx_conversa_unica_ativa`.
- Uma conversa finalizada em etapa com `bloqueio_dias > 0` permanecerá
  bloqueada pelo prazo declarado na política.
- A etapa 2 registra a escolha inicial entre titular e dependente. A etapa 3
  aceita exclusivamente `Sim` ou `Não`, por clique nos botões ou pelo mesmo
  texto digitado. `Sim` mantém a escolha; `Não` seleciona o polo oposto.
  Os dois resultados seguem obrigatoriamente para a etapa 4. Mídia, dúvida
  sobre reforço escolar, pergunta financeira inequívoca ou qualquer outro
  conteúdo repetem a confirmação.
- A etapa 4 sempre coleta, em texto livre, a profissão. Somente depois de
  persistir esse dado ela consulta o `status_dependente` final: dependente
  segue para a etapa 5, que pergunta o nome; titular segue para a etapa 6,
  que pergunta a idade. Assim, nenhum fluxo novo pula a profissão.
- A profissão válida da etapa 4 é salva, na mesma transação, em dois níveis:
  `conversa.profissao` preserva o snapshot daquele atendimento e
  `cliente.profissao` é substituída pelo valor válido mais recente informado
  pelo cliente. Uma conversa posterior nunca reescreve a profissão das
  conversas anteriores.
- Antes dessa persistência, o validador rejeita como
  `profissao_fora_contexto` somente as oito respostas completas já observadas:
  `Pra minha filha na verdade`, `Não entendi`, `Para meu filho`,
  `Pra meu filho`, `Minha filha é autista e percebo q ela tem dificuldade no
  aprendizado , vcs atende autista tambem`, `não seria pra meu filho`,
  `Meu filho` e `Vc ouviu áudio ou ligação`. A comparação ocorre sobre a frase
  inteira normalizada, nunca pela presença isolada de palavras como `áudio`,
  `ligação`, `filho`, `filha` ou `autista`. Quando houver correspondência, a
  etapa 4 apenas reapresenta a pergunta, sem evento, avanço ou persistência e
  sem criar uma etapa de confirmação adicional.
- A etapa 11 introduz a triagem, as etapas 12 a 17 fazem as seis perguntas e a
  etapa 20 apresenta o agendamento quando há link; sem link, a 18 coleta o turno e a 19 entrega ao comercial. A 20 com link ou a 19 sem link torna a conversa elegível ao
  Funil, mas não encerra nem bloqueia o atendimento.
- Na etapa 11, o clique em `Começar triagem` e confirmações textuais inequívocas
  disparam o mesmo evento `triagem_iniciada`. A validação aceita variações de
  começar, iniciar e prosseguir, enquanto negativas e respostas ambíguas mantêm
  a conversa na etapa 11.
- As etapas 12 a 17 não mudam de ID nem de transição conforme a idade. Elas
  selecionam somente o texto da pergunta: titular usa sempre a versão adulta;
  dependente com menos de 18 anos usa a versão infantil; dependente com 18 anos
  ou mais usa a versão adulta com o nome persistido. O limite de entrada de 4
  anos em unidade com BPA e de 5 anos sem BPA continua pertencendo à validação
  de idade anterior à triagem.
- Cada unidade possui `idade_minima_suporte` (NULL/50/60/70/80, padrão NULL)
  e `email_obrigatorio` (padrão TRUE). A migração da política anterior conserva
  TRUE como 60 e FALSE como NULL; novas unidades começam sem suporte ativado.
- Na etapa 6, mídia, reforço escolar e financeiro precedem a validação de idade.
  A universal 90+ tem prioridade e vale para titular e dependente, inclusive com
  suporte desativado. Envia contato com mensagem pronta e encerra com
  `idade_universal_90`. Titulares abaixo de 90 e a partir do suporte configurado
  encerram com `suporte_idoso_50/60/70/80`; a idade desse suporte é persistida.
  Menores de 18 encerram com `titular_menor_18`. Dependentes abaixo do mínimo
  encerram com `dependente_menor_4` (BPA) ou `dependente_menor_5` (sem BPA).
  Menores não recebem contato comercial. Nenhum desses casos gera Funil ou
  bloqueio de 30 dias. Os nomes internos `idade_acima_99` permanecem compatíveis,
  mas não representam o corte dos novos atendimentos.
- Para todas as faixas configuráveis (50/60/70/80), o encaminhamento usa
  a mesma mensagem de atendimento personalizado, sem anunciar o limite, e o
  botão `Falar agora`.
- Todo botão para o comercial leva uma mensagem pronta, inclusive o universal 90+.
  O texto identifica o chatbot pelo nome e artigo conforme seu gênero, a unidade
  e o cliente que está conversando. Na rota de titular, inclui sua idade e o
  desejo de reservar sua experiência Supera. Na rota de dependente,
  identifica também o nome e a idade do dependente e pede a experiência para ele.
  A idade é a informada na resposta atual da etapa 6, nunca uma idade antiga
  nem a idade do dependente atribuída ao titular. A origem vem da unidade
  vinculada à conversa; não inventar informações ausentes.
  O cliente confirma o envio no WhatsApp; abrir o botão não envia esse texto.
- O proprietário configura o limite no Admin. Toda unidade exige número comercial
  brasileiro válido, mesmo com suporte desativado. A migração normaliza 90 para
  NULL e invalida o cache; nunca converte 90 para 80.
- Retry exige a resposta conhecida vinculada à mesma conversa, fila e hash da
  entrada. A idade vem da mensagem vinculada, nunca de `cliente.idade`;
  `validar_idade` extrai o inteiro inclusive de números acompanhados de texto
  ou escritos por extenso. Para
  suporte comprovado entre 50 e 89, usa o limite atual se ele ainda inclui a idade;
  caso contrário, usa o maior entre 50/60/70/80 que não exceda a idade, inclusive
  se o suporte foi desativado. Registra a reconstrução compatível em log, sem
  afirmar que descobriu a faixa histórica exata. Suporte legado 90–99 fica genérico.
  O mínimo BPA é recuperado do texto efetivamente enviado. Uma oferta já enviada
  não vira encerramento por mudança de regra. Universal 100+ em retry sem motivo
  confirmado conserva o legado quando o corpo não distingue a versão. Encerramento
  e fila sent continuam atômicos; o risco Meta-before-DB permanece aceito.
  Uma resposta universal comprovada para titular de 91 ou dependente de 92
  mantém `idade_universal_90` se o suporte mudar de desativado para 80+ antes
  do retry. Universal tem prioridade para ambos; adicionalmente, dependentes
  não participam do suporte configurável. A reconstrução não recalcula motivos
  de conversas concluídas e não é usada para decidir novas conversas.
- Na etapa 10, mídia, reforço escolar e financeiro continuam precedendo a
  coleta de e-mail. A exigência efetiva é a configuração da unidade, exceto
  para o titular de 60 a 99 anos, cujo e-mail é universalmente opcional quando
  o atendimento não tiver sido encerrado pelo suporte ao idoso. Dependentes
  seguem exclusivamente a configuração da unidade.
- Quando o e-mail é obrigatório, somente um endereço estruturalmente válido
  avança. Quando é opcional, um endereço válido é salvo; ausência declarada ou
  qualquer outra resposta comum aceita limpa `cliente.email` para `NULL` e
  avança sem tratamento de e-mail. A classificação da resposta permanece
  vinculada à conversa para que o Funil exiba `não tem` ou `não informado` sem
  inventar um endereço.
- A etapa 21 registra uma nota de satisfação de 1 a 5. Na etapa 22, o cliente
  escolhe se deseja comentar: a aceitação segue para a etapa 23 e a recusa
  salta diretamente para a etapa 24. A etapa 23 coleta o comentário livre e
  avança para 24 sem julgar seu conteúdo: `ok`, `sim`, emojis e pontuação também
  são aceitos. Não há tratamento de contexto inválido nessa etapa. Uma recusa
  explícita ou resposta sem texto encerra sem comentário (`NULL`); botões antigos
  não são gravados como comentário. Mídias mantêm a orientação para escrever
  por texto, sem avançar. A recuperação usa o mesmo critério de persistência. Nota e
  comentário são internos, não compõem o payload do Funil e não encerram nem
  bloqueiam o atendimento.
- A etapa 24 encerra a conversa, registra `foi_agendado` e aplica o bloqueio de
  30 dias. A despedida usa `te receber` para titular e `receber você e
  {nome_dependente}` para dependente, tanto no caminho 22 -> 24 quanto 23 -> 24.
  O nome vem do dependente vinculado à conversa e à unidade; nunca substituir
  silenciosamente a rota de dependente pela de titular quando faltar esse dado.
- Durante esse período, novas mensagens para a mesma unidade não iniciarão outro
  atendimento.
- Depois dos 30 dias, o cliente poderá iniciar uma nova conversa com a mesma
  unidade.

Implementação principal:

- `core/database/deploy_database/bank_script.py`
- `core/repositories/atendimento/conversas.py`
- `core/repositories/fluxo/politicas.py`
- `workers/worker_flow/valida_banco.py`
- `core/cache/runtime/cache_conversas_bloqueadas.py`

### 6.1 Oportunidade no Funil de Vendas

- Com link, uma conversa torna-se elegível ao entrar na etapa 20. Sem link, na etapa 19.
- Com link, as etapas 20 a 24 permanecem elegíveis; sem link, 19 e 21 a 24. Assim, avançar na pesquisa antes do
  próximo ciclo do worker não remove a conversa da fila do Funil.
- `lead_no_funil = TRUE` é a confirmação que impede um segundo envio da mesma
  conversa; nota e comentário da pesquisa não fazem parte do snapshot enviado.
- O worker cria uma oportunidade por vez na coluna `Leads` do CRM.
- O snapshot exige nome, telefone, idade da pessoa atendida e as seis respostas
  canônicas da triagem. O e-mail pode estar ausente quando a política efetiva
  da conversa o tornou opcional; nesse caso, o contato é enviado sem endereço
  e as observações exibem `não tem` ou `não informado`, conforme a resposta.
- O resultado de e-mail pertence à conversa que chegou ao Funil. Ele é
  reconstruído pela mensagem do cliente na etapa 10 vinculada à resposta do
  bot na etapa 11; uma conversa posterior não pode alterar esse snapshot por
  meio do valor global de `cliente.email`.
- A profissão da conversa é exibida nas observações; o Funil não usa
  `cliente.profissao`, pois ela pode ter sido atualizada por outro atendimento.
  Conversas legadas podem apresentar a profissão como não informada.
- As observações apresentam as seis perguntas e suas respostas na ordem das
  etapas 12 a 17. O Funil usa o mesmo catálogo de perguntas do WhatsApp e não
  envia mais o resumo por quantidade de `Nunca`, `Às vezes` e
  `Frequentemente`.
- Em atendimento para dependente, a oportunidade mantém o cliente pagante como
  contato e inclui nome e idade do dependente nas observações.
- A resposta só é confirmada quando o HTTP não falha e o JSON contém
  `response = success`.
- Falha antes da confirmação externa devolve `funil_envios` para `pending` e
  não altera `lead_no_funil`.
- `funil_envios` usa claim com `FOR UPDATE SKIP LOCKED` e lease para recuperar
  itens abandonados em `processing`.
- O título segue `Chatbot Lead <nome_unidade>`. A conversa é identificada pelos
  dados do snapshot e pelo estado local de `funil_envios`; o CRM não recebe o ID
  interno da conversa no título.
- A V1 não cria atividade e não sincroniza atualizações posteriores do CRM.

O processo é desativado por padrão e só inicia com
`FUNIL_WORKER_ENABLED=True` depois do teste manual da unidade.

## 7. Histórico da mensagem do cliente

Depois que uma mensagem da fila for aceita pelo worker:

- Ela será registrada no histórico como `quem_enviou = 'cliente'`.
- Sua identificação lógica utilizará conversa, `id_mensagem_fila` e
  `id_hash_msg`.
- Durante um retry, o registro existente deverá ser reutilizado.
- A etapa persistida no histórico deverá ser reutilizada; o retry não poderá
  reinterpretar a mensagem em outra etapa.
- `last_message_from` deverá permanecer como `cliente` enquanto não existir uma
  resposta do bot persistida para aquela mensagem.
- `last_interaction_at` deverá utilizar o horário persistido da mensagem, e não o
  horário em que o retry ocorreu.

### Respostas da triagem cognitiva

- A triagem mantém exatamente seis perguntas nas etapas 12 a 17.
- A idade e o destino do atendimento são relidos do banco em cada ciclo. Isso
  preserva a mesma variante no retry e impede escolher silenciosamente uma
  pergunta quando idade, nome do dependente ou destino estiverem inconsistentes.
- A versão infantil sempre usa o nome do dependente. A versão adulta usa
  `você` para o titular e o nome para um dependente adulto.
- Cada pergunta aceita somente `Nunca`, `Às vezes` ou `Frequentemente`.
- Botão e texto digitado percorrem a mesma validação exata.
- Qualquer outro conteúdo recebe o tratamento de contexto e mantém a conversa
  na pergunta atual.
- A resposta canônica é registrada em `chatbot.respostas_desafios` com a
  conversa, a etapa da pergunta e o histórico da mensagem do cliente.
- A restrição única por conversa e etapa torna a gravação idempotente.
- Em retry, a resposta pode ser reconstruída pela mensagem original.

## 8. Histórico e idempotência da resposta do bot

A resposta do bot a uma mensagem enfileirada é vinculada à entrada original por:

- `id_conversa`;
- `id_mensagem_fila`;
- `id_hash_cliente_origem`.

O lembrete proativo não responde a uma entrada enfileirada: deixa os dois campos
de origem nulos e usa recibo próprio por conversa e âncora do ciclo. Ele não
serve como prova de resposta para liberar um turno A/B/C.

Se `resposta_bot_para_mensagem_atual` já existir:

- a Meta não deverá ser chamada novamente;
- o histórico do bot não deverá ser duplicado;
- o contexto da conversa deverá ser reparado a partir dos dados persistidos;
- no retry normal, `last_message_from` deverá terminar como `bot`;
- a fila poderá seguir para `sent`.

O replay de uma retomada de follow-up já concluída reutiliza a resposta persistida
sem alterar a interação atual ou zerar um ciclo posterior. Essa recuperação fica
em `workers/worker_flow/transacoes/retorno_followup.py`.

As proteções `if resposta_bot_atual`, presentes nos fluxos normais e de
tratamento, são regras essenciais de idempotência da V1.

Implementação principal:

- `workers/worker_flow/valida_historico.py`
- `workers/worker_flow/response_flow/flow_sender.py`
- `workers/worker_flow/response_flow/etapas/`
- `workers/worker_flow/transacoes/persistencia_resposta.py`

## 9. Semântica de `last_message_from`

- Mensagem do cliente persistida e ainda sem resposta: `cliente`.
- Resposta do bot persistida: `bot`.
- Retry sem resposta do bot mantém ou repara o campo para `cliente`.
- Retry com resposta do bot existente mantém ou repara o campo para `bot`.
- O campo representa o último lado com mensagem persistida para o estado atual;
  ele não é apenas uma marcação de que a conversa já foi iniciada.

Recuperar uma retomada de follow-up já concluída não sobrescreve o estado de
uma interação posterior. A confirmação do lembrete proativo também registra
o bot como último lado, junto do histórico e do recibo de envio.

## 10. Etapas da conversa

- `chatbot.etapa` representa os estados existentes da conversa.
- `chatbot.etapa_transicao` representa as arestas permitidas entre esses
  estados.
- Uma resposta válida produz um evento e somente poderá seguir para o destino
  cadastrado para a combinação `origem + evento`.
- Uma etapa poderá possuir mais de um destino, desde que cada evento identifique
  uma única transição.
- Avanços, saltos e o retorno controlado `9 + retorno_adiado -> 8` são permitidos
  somente quando existe uma aresta explícita.
- Um exemplo de salto autorizado é
  `22 + comentario_satisfacao_recusado -> 24`.
- A atualização utilizará a origem persistida no histórico da mensagem e será
  revalidada no `UPDATE` da conversa.
- Um retry com resposta do bot existente reutilizará a etapa do histórico do
  bot e reconstruirá o evento pela origem e pelo destino.
- Tratamentos que apenas orientam o cliente poderão responder sem avançar a
  etapa e não produzirão evento de transição.

Qualquer transição sem aresta cadastrada é bug. A ordem numérica dos IDs serve
para organização e não define navegação.

## 11. Tipos de mensagem na V1

- `text` e `interactive` são tipos suportados pelo fluxo normal de validação.
- Mídias e anexos não são respostas suportadas pelo fluxo normal da V1.
- Uma mídia recebida deverá ser registrada no histórico.
- O bot enviará uma orientação para o cliente continuar por texto.
- Essa orientação não avançará a etapa, mas alterará `last_message_from` para
  `bot` depois de ser persistida.
- Texto com intenção de preço, custo, mensalidade ou investimento recebe
  tratamento próprio e não deve ser interpretado como resposta comum da etapa.
- Depois que a etapa 1 já foi apresentada, respostas de nome com números,
  caracteres inválidos, repetição artificial ou termos pejorativos recebem
  tratamento de contexto e não avançam a conversa.

Desconsiderar o conteúdo da mídia para fins de avanço de etapa não é bug.

### 11.1. Conversa iniciada por texto

Quando a conversa ainda não possui etapa atual persistida, qualquer mensagem de
texto comum poderá iniciar o atendimento e receber a saudação normal da etapa 1.

Essa regra vale mesmo que o texto inicial seja estranho, curto, tenha símbolos ou
pareça fora de contexto. Nessa primeira interação, o objetivo é apresentar o
agente virtual configurado para a unidade e pedir o nome do cliente.

Mídia, reforço escolar e intenção financeira conservam seus tratamentos e sua
prioridade, nessa ordem. Depois deles, o primeiro texto que perguntar o que é
o Supera ou pedir informações gerais recebe a apresentação explicativa aprovada,
com a comparação a uma academia para o cérebro e o pedido do nome. As demais
entradas recebem a abertura padrão.

A identificação aceita frases completas com ou sem saudação, nome do Supera,
acentos e interrogação, como `Do que se trata?`, `O que é?` e `Olá! Posso ter
mais informações sobre isso?`. Não basta uma palavra solta. Esse caminho só
existe antes da etapa 1 estar apresentada; depois disso, o nome continua sendo
validado normalmente. Ambas as aberturas inicializam a etapa 1, sem consumir
o primeiro texto como nome, e convergem para a mesma etapa 2 após um nome válido.
Não há novo evento de transição, flag no banco ou mudança de follow-up/retry.

Nas mensagens iniciais padrão, explicativa, de mídia, de intenção financeira
e de tratamento de reforço escolar, a apresentação é formada exclusivamente pelos dados
persistidos em `chatbot.unidade`:

- `nome_unidade`: nome público da unidade;
- `nome_agente`: nome público do agente virtual;
- `genero`: seleciona `Sou o {nome_agente}` para `masculino` e
  `Sou a {nome_agente}` para `feminino`.

Esses campos não alteram evento, transição, turno, retry ou transação. Eles são
apenas dados de apresentação lidos pelo contexto da etapa 1. As demais mensagens
mantêm seus textos próprios.

### Linguagem da experiência Supera e sua reserva

A composição das falas, a personalidade acolhedora e a organização dos
arquivos seguem o [contrato editorial de messages](core/integrations/whatsapp/messages/README.md).
Ele deve ser consultado em revisões de textos, tratamentos e retomadas,
preservando as regras operacionais deste documento.

Cada etapa separa sua mensagem padrão da repetição pura. Financeiro, mídia
e reforço escolar vêm de módulos próprios e são compostos antes dessa repetição.
Contexto inválido usa uma mensagem própria, que já orienta o cliente a responder
corretamente, sem concatenar a mensagem de repetição. Preserva os botões/opções
e rodapés nativos, assim como titular/dependente. A regra também vale na triagem
e na pesquisa. Pode receber o prefixo de inatividade de três horas quando elegível;
não recebe outro tratamento ou prefixo de follow-up nesse mesmo ciclo.
Inatividade de três horas mantém a validação normal (podendo avançar ou tratar);
a reação ao follow-up acolhe e valida a resposta. Quando não há resposta válida
nem tratamento específico, reapresenta a pergunta neutra. A etapa 8 continua
avançando diretamente para a 9. O retorno não soma saudações; quando repete a
etapa, usa sua pergunta neutra sem repetir apresentação ou despedida.

A oferta inicial da etapa 7 destaca **demonstração prática por cortesia da unidade** logo na
abertura, antes da explicação da avaliação de habilidades, e termina com o
convite para reservar uma **experiência Supera exclusiva**. A saudação
`Maravilha, {nome_titular}! ☺️` se dirige a quem conversa nas duas rotas;
quando há dependente, a demonstração, a avaliação e a reserva mencionam
`nome_dependente` como participante. Gratuidade da experiência
não significa curso ou matrícula gratuitos. Não há nome/gênero de diretor ou
novas colunas para essa oferta.

Concentrar **por cortesia da unidade** na apresentação inicial da oferta
(etapa 7) e nos lembretes proativos. O objetivo é reduzir a repetição, não impor
um limite técnico: a oferta e um ou dois lembretes somam duas ou três menções.
Retomadas, escolha de turno, envio do link, mensagens ao comercial e perguntas
repetidas usam apenas experiência ou momento Supera, sem esse complemento.
No tratamento financeiro, manter uma menção na orientação que esclarece a
cortesia; a pergunta seguinte não a repete. Essa dúvida pode acrescentar uma
menção ao atendimento. Outros tratamentos não repetem a expressão.
Não reintroduzir `gratuita` ou `gratuito` nos textos enviados ao cliente.

Cada lembrete pode mencionar a cortesia. A despedida do segundo follow-up
consecutivo não usa a expressão. Se houver mais pausas com retomada, poderão
ocorrer mais menções. A redução é apenas editorial, sem contador, consulta
adicional ao banco, coluna ou migração nova.
Preservar a alternância entre experiência e momento Supera.
Respostas do cliente com a redação anterior continuam
aceitas, e as classificações de gratuidade da Meta no painel de consumo mantêm
seu significado próprio.

O atendimento deve ser acolhedor e convidativo, com frases naturais, emojis
discretos e negrito moderado. A oferta usa **presentear**, e a comemoração
**Maravilha, {nome_titular}! ☺️** pertence à apresentação normal: não aparece após avisos de
mídia, dúvidas ou respostas não compreendidas. Nesses casos, o bot acolhe a
mensagem e orienta como continuar, sem atribuir o erro ao cliente.

Na etapa 1, a apresentação não presume quem participará da experiência.
Na oferta e na apresentação do link de reserva, o dependente é mencionado
pelo nome quando for o participante, inclusive na repetição por follow-up.
Esses ajustes de linguagem não alteram validação, transição ou elegibilidade.

Uma negativa sem alternativa na etapa 2 repete a pergunta, sem escolher
um destino. Correções explícitas com vírgula e destinos alternativos
completos continuam aceitos. A confirmação da etapa 3 é preservada.

Perguntas sobre a gratuidade da demonstração ou experiência recebem o
tratamento financeiro, sem avanço. Perguntas curtas como `É gratuita?`
podem retomar a oferta nas etapas de convite e reserva. Menções a algo
gratuito fora desse contexto não recebem uma classificação nova genérica.

As saudações de retorno não se acumulam na etapa 9. O sender devolve
ao histórico o mesmo texto enviado; retries preservam respostas anteriores.

Nas etapas 7 e 9, o botão **Quero reservar** e confirmações digitadas como
**quero**, **sim** e **quero agendar** continuam aceitos. Por decisão de
negócio, o aceite flexível não foi endurecido: expressões como `quero pensar melhor`
continuam seguindo o reconhecimento existente. Negativas reconhecidas e pedidos
informativos, como **quero saber como reservar**, não confirmam a oferta.
**Talvez mais tarde** mantém o evento de adiamento. A etapa 20 apresenta
**Já reservei** e aceita também as confirmações antigas de conclusão, como
**já agendei**. Dizer **quero reservar** nessa etapa não comprova conclusão.
Os nomes técnicos de eventos e colunas permanecem, incluindo `link_agendamento`
e `agendamento_confirmado`; idade, e-mail, follow-up e fronteiras transacionais
conservam suas regras.

### 11.2. Exceção para conversa iniciada com mídia

Quando a primeira mensagem de uma conversa for uma mídia, ainda não existirá
uma etapa atual persistida. Nesse caso:

1. o bot enviará saudação da etapa 1 junto com o aviso de mídia não suportada;
2. a mensagem solicitará o nome do cliente por texto;
3. o tratamento registrará a etapa 1 como apresentada;
4. a próxima interação válida será interpretada como resposta da etapa 1 e
   poderá direcionar o fluxo para a etapa 2.

Mensagem esperada, usando uma das duas primeiras linhas conforme o gênero do
agente:

```text
Masculino: Bom dia/Boa tarde/Boa noite! Sou o {nome_agente}, assistente do {nome_unidade}! ☺️
Feminino:  Bom dia/Boa tarde/Boa noite! Sou a {nome_agente}, assistente do {nome_unidade}! ☺️
Hoje vou te ajudar a dar os primeiros passos para conhecer o Supera! 🧡

Olha não reconhecemos ainda mensagem com mídia, apenas texto.
Me diz, qual o seu primeiro nome?
```

Para qualquer etapa já apresentada, a regra geral será diferente. Se a conversa
estiver na etapa N e o cliente enviar uma mídia:

1. o bot enviará o tratamento de tipo de mensagem não suportado;
2. o tratamento poderá repetir a pergunta da etapa atual quando essa
   reapresentação estiver implementada;
3. o tratamento não alterará a etapa persistida;
4. a interação seguinte por texto será interpretada como resposta da etapa N;
5. uma resposta válida produzirá o evento que aponta para o destino cadastrado;
6. a mensagem normal da etapa N não precisará ser enviada de novo em separado.

Na etapa 1 já apresentada, a resposta esperada para mídia será:

```text
Olha não reconhecemos ainda mensagem com mídia, apenas texto.
Me diz, qual o seu primeiro nome?
```

Para etapas ainda sem tratamento específico, a mensagem poderá ser mais genérica:

```text
Recebi uma mídia, mas nesta etapa eu preciso que você responda por texto ou use os botões disponíveis.

Envie uma mensagem de texto para continuarmos.
```

Em ambos os casos:

1. o tratamento não avança etapa;
2. a interação seguinte por texto será interpretada como resposta da etapa N;
3. uma resposta válida seguirá a transição cadastrada para a etapa N.

Portanto, o tratamento de mídia não avança etapa já apresentada. A exceção é
somente a conversa iniciada com mídia, porque a própria mensagem de tratamento
também apresenta a etapa 1.

### 11.3. Tratamento financeiro

Quando o cliente enviar texto perguntando sobre valor, custo, preço,
mensalidade, investimento ou termo equivalente:

1. a mensagem do cliente será registrada no histórico;
2. o bot explicará que os valores de investimento são definidos após a
   experiência Supera por cortesia da unidade, com orientação da equipe;
3. a mensagem também reapresentará a pergunta da etapa atual;
4. a conversa não avançará por causa da pergunta de valor;
5. `last_message_from` será atualizado para `bot` depois da resposta persistida.

Se a conversa iniciar com pergunta de valor, a resposta esperada usará uma das
duas primeiras linhas conforme o gênero do agente:

```text
Masculino: Bom dia/Boa tarde/Boa noite! Sou o {nome_agente}, assistente do {nome_unidade}! ☺️
Feminino:  Bom dia/Boa tarde/Boa noite! Sou a {nome_agente}, assistente do {nome_unidade}! ☺️

Hoje vou te ajudar a dar os primeiros passos para conhecer o Supera! 🧡

Olha, os valores de investimento são definidos após a *experiência Supera* por cortesia da unidade. Assim, nossa equipe poderá orientar você sobre a opção mais adequada. ☺️

Vamos lá:

Me diz, qual o seu primeiro nome?
```

Nesse caso, a etapa 1 fica registrada como apresentada, e a próxima resposta em
texto será interpretada como resposta da etapa 1.

Se a etapa 1 já tiver sido apresentada e o cliente responder perguntando sobre
valor, a mensagem esperada será:

```text
Olha, os valores de investimento são definidos após a *experiência Supera* por cortesia da unidade. Assim, nossa equipe poderá orientar você sobre a opção mais adequada. ☺️

Vamos lá:

Me diz, qual o seu primeiro nome?
```

Esse tratamento é financeiro, não tratamento de contexto. Ele possui fluxo e
sender próprios para evitar misturar dúvida comercial com resposta fora do
contexto da etapa.

O prefixo é único e a pergunta seguinte retoma a etapa sem repetir todo o
convite. O participante permanece correto, inclusive quando é um dependente.
Os textos destacam com moderação a experiência e a ação principal usando
`*negrito*` no corpo. Os títulos de botões não recebem essa marcação.

### 11.4. Tratamento de dúvida sobre reforço escolar

Nas mesmas etapas que oferecem tratamento financeiro, o sistema também deverá
identificar dúvidas que confundam o Supera com serviços escolares tradicionais,
como reforço escolar, banca, supletivo, cursinho, aula particular ou ensino de
matérias específicas.

O reconhecimento é universal e possui o seguinte contrato:

1. mídia ou tipo não suportado continua tendo prioridade sobre o texto;
2. a dúvida sobre reforço escolar tem prioridade sobre o tratamento financeiro;
3. a mensagem do cliente e a resposta do bot são registradas normalmente;
4. a resposta é marcada com `tipo_tratamento='duvida_reforco_escolar'`;
5. nenhuma transição é produzida e a conversa permanece na etapa atual;
6. a pergunta ou chamada da etapa é reapresentada de forma neutra, preservando
   botões, rodapés, links e as variantes de titular ou dependente aplicáveis.

Assim, uma pergunta como `Quanto custa o reforço escolar?` recebe este
tratamento antes do financeiro. Já uma mídia que contenha texto ou legenda
continua recebendo tratamento de mídia.

Expressões inequívocas de serviço escolar podem ser reconhecidas diretamente.
Nomes de matérias, como matemática ou português, exigem também contexto de
ensino, aula, ajuda ou procura pelo serviço. A palavra isolada não é suficiente,
pois respostas legítimas como `Sou professora de matemática` devem continuar
pertencendo à etapa que coleta a profissão.

A expressão `O investimento fica na faixa de um curso de inglês`, usada como
comparação no formulário, não representa procura por aulas nem pergunta de preço.
Os classificadores de reforço escolar e financeiro desconsideram esse trecho,
aceitando variações de caixa, acentos e espaços. No financeiro, desconsiderar
também o rótulo `Quem decide a matrícula?:` (com interrogação opcional) quando
acompanha diretamente a comparação. Preservar a resposta a esse rótulo e o
restante da mensagem: dúvidas reais sobre inglês, reforço ou preço conservam
seus tratamentos. A mensagem original continua intacta no histórico. Essa
exceção não identifica a origem do lead nem importa dados do formulário.

Na etapa 4, declarações claras de profissão ou vínculo de trabalho com banca,
cursinho, supletivo ou reforço também são respostas profissionais válidas. Por
exemplo, `Trabalho em um cursinho`, `Sou diretora de um supletivo` e
`Sou professora de matemática em uma banca` não acionam este tratamento. A
exceção é contextual e não altera o reconhecimento nas demais etapas.

Mensagem esperada:

```text
Olha, o Supera não é reforço escolar.
Nós trabalhamos a raiz da aprendizagem, desenvolvendo habilidades como atenção, concentração, memória e raciocínio — o alicerce necessário para aprender melhor em qualquer matéria. 🧠✨

Vamos lá:

(retomada neutra da etapa atual)
```

### 11.5. Tratamento de contexto para nome inválido

Depois que a etapa 1 já foi apresentada, a resposta esperada do cliente é o nome.
Se o cliente responder com texto que pareça fora do contexto de nome, como
caracteres inválidos, números, repetição artificial ou termo pejorativo, o bot
deverá tratar sem avançar a conversa.

Mensagem esperada:

```text
Olha, não consegui entender o seu nome. Digite só seu primeiro nome, por exemplo: Pedro.
```

Esse tratamento é diferente do financeiro e do tipo não suportado. Ele existe
para preservar a etapa atual e pedir novamente um nome utilizável.
O pedido já está completo nessa mensagem; não acrescentar a pergunta de repetição.

### 11.6. Coerência semântica ao reapresentar a etapa

Quando um tratamento reapresentar a pergunta da etapa atual, ele não deverá
concatenar automaticamente a mensagem padrão completa. A pergunta ou chamada
principal pode ser reutilizada, mas aberturas que pressuponham resposta válida,
confirmação, apresentação ou avanço — como `Entendi`, `Certo`, `Perfeito`,
`Maravilha` e `Prazer` — deverão ser omitidas ou substituídas por uma retomada
neutra.

**Exceção de contexto inválido:** a orientação possui redação própria e já
contém o pedido da resposta correta. Nunca concatenar a pergunta de repetição
nem a mensagem inicial. A apresentação visual e os botões/rodapés nativos
continuam pertencendo à etapa. Essa exceção muda a redação, não os critérios
dos validadores, a prioridade dos tratamentos ou os eventos de transição.

A mensagem final deverá ser lida como uma única fala semanticamente coerente.
Depois de informar que uma resposta não foi compreendida ou aceita, o bot não
deverá elogiar, confirmar entendimento nem pressupor que a conversa avançou.
Essa regra vale para tratamentos de mídia, financeiro, contexto e qualquer
tratamento futuro que reapresente conteúdo da etapa.

### 11.7. Saudação de retorno após inatividade

Depois que o cliente já informou o nome na etapa 1, uma nova mensagem recebida
na mesma conversa pelo menos três horas após o último envio confirmado do bot
deverá fazer a resposta começar com `Bom te ver novamente, {nome} ☺️` no caminho normal
com `followup_stage = 0`. Stage positivo ou retomada já registrada segue o
[contrato de follow-up](#follow-up-de-inatividade-e-reação-do-cliente), com o
prefixo de retorno e a validação da resposta; a etapa 8 avança diretamente para a 9.

O intervalo é inclusivo (`>= 3 horas`) e deve comparar o horário original do
evento atual do cliente com a última linha `sent` do bot no histórico da mesma
`id_conversa`. A atividade do mesmo cliente em outra unidade ou conversa não
participa desse cálculo. A própria mensagem em que o nome é informado na etapa
1 ainda não recebe a saudação; a regra começa nas mensagens seguintes, quando o
nome já está validado e persistido.

A saudação é somente um prefixo da resposta que o fluxo já produziria:

- resposta válida: saudação mais a mensagem da etapa resultante;
- mídia, financeiro ou reforço: saudação mais o tratamento e a repetição da etapa atual;
- contexto inválido: saudação mais a mensagem própria de contexto, sem outra pergunta.

Ela não cria etapa, evento de transição, envio separado nem uma segunda linha de
histórico. A barreira idempotente continua sendo executada antes dos resolvers:
se o retry já encontrar a resposta exata do bot persistida para aquela mensagem
do cliente, nenhum novo envio ou prefixo será produzido. Nome, último envio ou
timestamps ausentes/incompatíveis apenas desativam a saudação para aquele evento
e nunca impedem a resposta normal do fluxo.

## 12. Flood, payload e assinatura

- A regra atual de rajada curta considera 15 eventos em 5 segundos.
- Redis é a primeira fonte de avaliação de flood.
- Banco e memória funcionam como fallbacks previstos.
- Um cliente identificado como flood poderá ser bloqueado na Meta e não deverá
  ser enfileirado.
- Conversas explicitamente bloqueadas também não serão enfileiradas.
- Payload acima de `WEBHOOK_MAX_BODY_BYTES` deverá ser rejeitado com HTTP 413
  antes de parse, flood, cache ou banco.
- Assinatura Meta inválida deverá ser rejeitada com HTTP 403 antes de qualquer
  confiança no conteúdo do payload.

Payload grande e assinatura inválida bloqueiam a requisição na entrada, mas não
devem bloquear diretamente um cliente na Meta. Um atacante poderia montar um
payload inválido utilizando o `wa_id` de um cliente real. Bloquear esse número
atingiria a vítima informada pelo atacante, e não necessariamente a origem da
requisição.

Portanto, HTTP 413 ou 403 sem bloqueio Meta é o comportamento final e esperado da
V1, e não uma implementação parcial.

Implementação principal:

- `callback/webhook/services/post_flow.py`
- `callback/webhook/services/flood_guard.py`
- `core/cache/runtime/cache_flood_redis.py`
- `core/cache/cache_flood_memoria.py`

## 13. Commits e estados intermediários do worker

O worker de atendimento possui checkpoints duráveis separados:

1. claim da fila como `processing`;
2. espera por mensagem anterior, quando necessária;
3. validação do cliente e da conversa no banco;
4. aquisição do lock da conversa;
5. vínculo, releitura e histórico do cliente, incluindo o marcador de retomada quando aplicável;
6. renovação do lock antes do envio;
7. histórico e contexto do bot; na retomada, conclusão do marcador e reset do stage;
8. fila marcada como `sent`, depois de conferir novamente a posse do lock;
9. unlock da conversa.

Uma queda entre checkpoints normalmente deixa informações suficientes para que
o timeout e o retry reconheçam o estado intermediário. O objetivo é evitar a
perda da mensagem aceita, mesmo admitindo duplicidade rara.

As decisões de `commit`, `rollback` e `close` da conexão do ciclo pertencem ao
`flow_worker.py`. Repositórios e módulos internos executam operações utilizando a
conexão ou o cursor recebido, sem assumir a propriedade da transação.

## 14. Duplicidade aceita como exceção rara

O sistema busca entrega pelo menos uma vez, e não exatamente uma vez.

A principal janela aceita de duplicidade é:

```text
Meta confirmou ou efetivou o envio
        -> worker caiu ou perdeu a confirmação
        -> histórico do bot ainda não foi confirmado no banco
```

Nesse intervalo, o retry não encontra uma resposta persistida e poderá enviar
novamente. Depois do commit do histórico do bot, o retry deverá reconhecer a
resposta e não repetir o envio.

Duplicidade frequente, determinística ou ocorrida depois de a resposta do bot já
estar persistida é bug. Duplicidade excepcional na janela externa entre Meta e
banco é um trade-off conhecido e aceito na V1.

O Funil possui uma janela externa equivalente:

```text
Funil confirmou a oportunidade
        -> banco caiu antes de marcar lead_no_funil
        -> lease expirou
        -> retry pode criar outra oportunidade
```

O estado local `processing` e o snapshot persistido tornam o caso rastreável, mas
não existe exatamente uma vez sem consulta de reconciliação suportada pelo CRM.

## 15. O que é bug na V1

São bugs, entre outros:

- a primeira ou única mensagem válida do turno ser ignorada sem uma regra
  aplicável;
- uma mensagem aceita desaparecer antes de concluir a política prevista de
  tentativas;
- o bot enviar novamente quando a resposta atual já estiver persistida;
- `last_message_from` permanecer como `cliente` quando a resposta atual do bot já
  estiver persistida, ou como `bot` quando ainda não existir resposta persistida;
- uma etapa mudar sem a aresta `origem + evento -> destino` autorizada;
- duas mensagens do mesmo turno avançarem a conversa como se fossem turnos
  independentes;
- uma mensagem posterior ultrapassar outra anterior ainda aberta na conversa;
- uma falha prevista encerrar permanentemente o worker sem tentativa de
  recuperação.

## 16. O que não é bug na V1

Não são bugs:

- ignorar qualquer segunda mensagem quando a primeira mensagem do mesmo cliente e
  unidade ainda estiver aberta e sem resposta própria do bot;
- ignorar a repetição do mesmo webhook ou `id_hash_msg`;
- reutilizar histórico existente durante um retry;
- responder a uma mídia com orientação sem avançar etapa já apresentada;
- apresentar a etapa 1 junto com o aviso quando a conversa for iniciada com
  mídia;
- responder pergunta sobre valor sem tratar esse texto como nome ou avanço de
  etapa;
- excluir a mensagem ao atingir a terceira tentativa;
- aguardar os timeouts da fila ou do lock antes de um novo processamento;
- uma duplicidade extremamente rara na janela entre Meta e commit do bot;
- rejeitar payload grande ou assinatura inválida sem bloquear o número informado
  na Meta.

## 17. Falhas operacionais do webhook e reentrega da Meta

Quando uma mensagem válida chega à transação da fila, mas conexão, inserção ou
commit falham:

- a transação será revertida com rollback;
- o webhook registrará `insert_exception`;
- a resposta será HTTP 503 com `status = 'unavailable'`;
- a Meta poderá tratar a entrega como malsucedida e reenviar o evento;
- a repetição continuará protegida pela unicidade de `id_hash_msg`.

Também é HTTP 503 quando o webhook não consegue validar a unidade porque Redis e
banco estão indisponíveis no mesmo ponto do fluxo. Nesse caso:

- o webhook registrará `unit_validation_unavailable`;
- a mensagem não será tratada como unidade inativa;
- a Meta poderá reenviar o evento quando o endpoint voltar a responder com
  sucesso.

Esse HTTP 503 é reservado para falhas operacionais que impedem o sistema de
decidir ou persistir uma mensagem válida com segurança. Mensagens descartadas
intencionalmente por turno aberto, duplicidade, flood, unidade inativa, conversa
bloqueada ou payload sem mensagem processável continuam seguindo seus contratos
de `ignored` e não devem ser transformadas em indisponibilidade.

O retry da Meta protege a chegada ao webhook e não substitui o retry interno do
worker. Depois que a fila foi persistida e o webhook respondeu HTTP 200, qualquer
falha de processamento ou envio da resposta pertence à política de tentativas do
worker.

## 18. Cache, fallback e autocura

Tabelas e consultas de baixa volatilidade ou alta frequência devem priorizar
Redis e possuir fallback para a fonte de verdade no banco quando o cache estiver
indisponível, inválido ou inconsistente de maneira detectável.

Princípios obrigatórios:

- Redis é um acelerador; o banco continua sendo a fonte de verdade.
- Uma falha do Redis não deverá interromper o fluxo quando houver fallback seguro
  no banco.
- Depois de consultar o banco por fallback, o sistema deverá tentar reparar o
  Redis com os dados atuais.
- Uma falha na tentativa de reparo do cache não deverá apagar dados válidos do
  banco.
- Quando um valor stale causar erro de integridade, ele deverá ser removido ou o
  cache completo deverá ser recarregado para que o próximo retry consulte o banco
  e se recupere.
- Operações administrativas que exijam banco e cache coerentes deverão ser
  bloqueadas se o Redis não puder ser validado ou atualizado.

### 18.1. Cache de unidades

- Utiliza hash Redis, quantidade esperada e versão mantida em
  `chatbot.cache_controle`.
- Webhook e worker conferem periodicamente a versão do Redis contra a versão do
  banco e recarregam o cache quando encontram divergência.
- O Django Admin incrementa a versão e recria o cache depois de salvar ou excluir
  uma unidade.
- Se o Redis falhar, webhook e worker utilizam fallback no banco e tentam
  recarregar o cache.
- Se um `id_unidade` stale causar violação de FK no worker, o cache de unidades é
  recarregado antes do retry.

### 18.2. Cache de clientes

- Relaciona `wa_id` ao `id_cliente` e possui TTL.
- Miss, valor inválido ou Redis indisponível levam a consulta ao banco.
- Um cliente criado ou encontrado no banco será salvo no cache somente depois do
  commit que confirmar sua existência.
- Se um `id_cliente` stale causar violação de FK, a chave será removida para que o
  retry reconstrua o valor correto pelo banco.

### 18.3. Cache de conversas bloqueadas

- O bloqueio de 30 dias utiliza Redis com TTL calculado a partir de
  `finalizou_em`.
- Quando o Redis falha, o banco é consultado e o cache é criado ou removido para
  refletir o resultado persistido.
- Quando o worker encontra uma conversa bloqueada que ainda não estava no cache,
  ele registra a chave com o TTL restante e remove a mensagem da fila.
- Depois de expirado o período, a chave não deverá mais bloquear o cliente.
- Esse cache possui mecanismo próprio de reparo e não deverá ser incluído nos
  reparos de FK de cliente e unidade do `flow_worker.py`.

### 18.4. Escopo da autocura

- A autocura cobre falhas detectadas, versão divergente de unidades e erros FK
  de cliente ou unidade.
- Em produção, alterações manuais diretamente no banco são proibidas. Dados que
  afetam cache devem ser modificados pelos fluxos oficiais da aplicação ou pelo
  Django Admin.
- Edições manuais no banco são permitidas somente em desenvolvimento. Nesse
  ambiente, atrasos de sincronização poderão ser corrigidos pelo reset de cache
  destinado a DEV.
- O sistema não precisa comparar banco e Redis em toda leitura para detectar uma
  edição manual que viole o contrato de produção.

Dentro desse contrato, a autocura implementada atende às regras da V1. Suporte a
edições manuais silenciosas em produção não é requisito.

Implementação principal:

- `core/cache/cache_unidade.py`
- `core/cache/runtime/cache_cliente.py`
- `core/cache/runtime/cache_conversas_bloqueadas.py`
- `core/repositories/unidades/cache_control.py`
- `workers/worker_flow/suporte/cache_repair.py`

## 19. Regras do Django Admin

O Django Admin é uma superfície operacional controlada, e não uma forma livre de
editar as tabelas do fluxo.

### 19.1. Tabelas somente para visualização

Cliente, dependente, etapa, conversa, fila, histórico, respostas de desafio,
eventos de flood e controle de cache utilizam administração somente leitura:

- não permitem adicionar;
- não permitem alterar;
- não permitem excluir;
- exibem os campos somente para consulta operacional.

### 19.2. Clientes bloqueados na Meta

- `cliente_bloqueado_meta` representa a intenção persistente de bloquear o par
  `wa_id_cliente + phone_id_unidade`, além dos bloqueios já confirmados pela
  Meta.
- Um contato identificado manualmente pode ser registrado nessa tabela mesmo
  quando a janela da Meta ainda não permite confirmar o bloqueio.
- Toda nova mensagem desse par é interceptada antes do flood, da validação da
  unidade e da fila.
- O webhook tenta bloquear novamente na Meta e sempre ignora a mensagem, tanto
  no sucesso quanto na falha. Uma mensagem futura provoca uma nova tentativa.
- Falha ao consultar a lista retorna HTTP 503 para a Meta reenviar o evento;
  nenhuma mensagem é enfileirada sem que essa validação seja concluída.
- A consulta sempre inclui `wa_id_cliente` e `phone_id_unidade`, preservando o
  isolamento multi-WABA.
- Bloqueios automáticos detectados pelo sistema registram e confirmam primeiro
  a intenção local no banco; somente depois do commit tentam o bloqueio na
  Meta, sem manter transação aberta durante a chamada externa.
- Se a Meta recusar o bloqueio, a linha local permanece autoritativa: a
  mensagem atual é ignorada e uma mensagem futura provoca nova tentativa.
- Se a intenção local não puder ser persistida por indisponibilidade do banco,
  o webhook não chama a Meta, não enfileira a mensagem e retorna HTTP 503 para
  permitir reentrega.
- O Django Admin continua sem permitir a criação livre de registros enquanto
  não existir uma interface específica para classificar bots manualmente.
- O administrador poderá somente desbloquear, removendo individualmente um
  registro existente.
- Desbloqueio em massa é proibido.
- No desbloqueio, a ordem obrigatória é Meta primeiro, banco depois.
- Se o desbloqueio na Meta falhar, o registro deverá permanecer no banco.
- Não existe chave Redis equivalente: a própria tabela é consultada de forma
  autoritativa pelo webhook.

### 19.3. Unidades

- Cada unidade possui um `waba_id` único e obrigatório e um
  `phone_number_id` único e obrigatório.
- A criação valida primeiro, pela Graph API, se o `phone_number_id` pertence
  ao `waba_id` informado.
- Depois da validação, o App assina a WABA e registra o número na Meta.
- Se a Meta falhar, a unidade não será criada no banco.
- Antes da alteração no banco, o Redis deverá passar pelo preflight.
- Depois do save, a versão das unidades será incrementada e o cache recarregado.
- A exclusão desassina a WABA e desregistra o número na Meta antes de remover
  a unidade do banco.
- Se a Meta falhar durante a exclusão, a unidade permanecerá no banco.
- Se o Redis falhar depois de a Meta responder, o banco deverá permanecer sem
  alteração e o administrador deverá receber uma mensagem para tentar novamente.
- Exclusão em massa de unidades é proibida.
- `idade_minima_suporte` e `email_obrigatorio` são editáveis no Admin; a ativação do
  suporte exige um número comercial válido. `waba_id` e `phone_number_id` ficam
  somente leitura depois da criação.

### 19.4. Papel de `status_pagamento`

`status_pagamento` não representa vinculação ou desvinculação do número no WABA.

- O campo é o controle atual de admissão da unidade: somente registros com
  `status_pagamento = TRUE` entram no cache de unidades ativas e são localizados
  pelo webhook e worker.
- Uma futura tabela `payment` poderá automatizar essa decisão, mas ela não faz
  parte da V1.
- Na V1, pagamentos e contratos poderão ser controlados manualmente, contrato por
  contrato.
- Alterar `status_pagamento` deverá atualizar banco e cache de unidades, mas não
  deverá registrar ou remover o número na Meta.

O fato de uma edição de `status_pagamento` não chamar a Meta é comportamento esperado,
e não uma lacuna.

### 19.5. Desvinculação definitiva de uma unidade

Para encerrar o vínculo de uma unidade com o sistema:

1. solicitar a exclusão individualmente pelo Django Admin;
2. o sistema remove a assinatura do App na WABA;
3. o sistema desregistra o `phone_number_id`;
4. somente após as duas confirmações Meta conclui a exclusão no banco e
   atualiza o cache de unidades.

A exclusão administrativa continua protegida pela validação Meta-first do código
e pelo preflight do Redis. A exclusão em massa permanece proibida.

Implementação principal:

- `callback/webhook/admin.py`
- `core/integrations/whatsapp/tools/validando_phone_waba.py`
- `core/integrations/whatsapp/tools/ativando_waba_id.py`
- `core/integrations/whatsapp/tools/desativa_waba_id.py`
- `core/integrations/whatsapp/tools/ativando_numero.py`
- `core/integrations/whatsapp/tools/desativando_numero.py`

### 19.6. Contas de monitoramento por unidade

- `chatbot.unidade.id_usuario_monitoramento` referencia `chatbot.auth_user.id`.
  O vínculo é opcional e único: cada usuário pode monitorar no máximo uma
  unidade e cada unidade pode possuir no máximo uma conta de monitoramento.
  Várias unidades podem manter o campo `NULL`, sem acesso de monitoramento.
- Login, hash da senha e ativação da conta pertencem à autenticação do Django;
  a unidade armazena somente a referência. No Admin, crie a conta em **Usuários**
  e selecione-a no campo **Usuário de monitoramento** do cadastro da unidade.
- Contas de monitoramento não possuem `is_staff` nem `is_superuser`. O formulário
  recusa contas administrativas e a autorização também confere esses estados
  diretamente no banco, além de `is_active`.
- A identidade vem de `request.user`; usuário/unidade informados pelo navegador
  não definem o escopo. Sem sessão válida, vínculo ou conta habilitada, o acesso
  é negado. Erro de banco não autoriza leitura.
- Conversas são autorizadas por `conversa.id_unidade`; mensagens, pela unidade
  de sua conversa. O cadastro global de cliente não concede acesso às conversas
  dele em outras unidades. Se conversa e mensagem forem informadas juntas, a
  mensagem deve pertencer àquela conversa.
- O vínculo é consultado a cada requisição, sem cache nem bypass administrativo.
  Remover o vínculo, desativar a conta ou mudar sua unidade afeta a próxima
  consulta. `status_pagamento` continua com sua finalidade de admissão do bot;
  não é um novo bloqueio do monitoramento.
- Excluir um usuário limpa a referência por `ON DELETE SET NULL`, preservando
  a unidade, suas conversas e seu histórico. Excluir a unidade pelo fluxo
  administrativo existente não exclui a conta Django. Limpar somente o campo
  de monitoramento revoga o acesso sem excluir entidades.
- O login usa o par `username`/senha da mesma conta e o verificador de hash
  nativo do Django. Antes de criar a sessão, exige conta habilitada, comum e
  vinculada a uma unidade. Usuário inexistente e senha incorreta recebem o
  mesmo aviso. Não há cadastro, recuperação/troca de senha ou bloqueio após
  três tentativas no portal; o proprietário administra as contas pelo Admin.
- Login e logout usam CSRF; logout somente por POST. O destino após autenticar
  é fixo, sem aceitar redirecionamento escolhido pelo navegador. A senha fica
  mascarada e não volta preenchida após erro. Falhas de banco não liberam acesso.
- O acesso bem-sucedido abre o painel em `/`. A página e todas as rotas de dados
  usam `exigir_acesso_monitoramento` e mantêm cada SELECT limitado à unidade
  retornada. A autorização não filtra automaticamente outros SQLs ou QuerySets.
- O painel é somente leitura. Suas rotas de dados aceitam apenas GET; não há
  envio de mensagens, cadastro, edição nem exclusão de informações.
- O período padrão cobre a primeira mensagem de cliente registrada na unidade
  até o instante da consulta. Também são aceitas janelas de 24 horas, 7 e 30
  dias, 2, 3 e 6 meses e 1 ano. Uma janela finita compara seus indicadores com
  a janela imediatamente anterior de igual duração.
- Conversas técnicas do mesmo cliente são consolidadas somente dentro da unidade
  autorizada. Os filtros locais são Todas, Comercial, Follow-up, Funil e Avaliadas; os
  perfis visuais são Menor de 18, Adulto, 60+ e Dependente. Na lista de
  conversas, as etiquetas ao lado da data preservam a relação entre faixa
  etária e destino nas formas abreviadas DP -18, DP 18–59, DP 60+, 18–59 e
  60+; a descrição completa permanece disponível como informação acessível.
- O navegador consulta conversas a cada 10 segundos e relatórios a cada 30
  segundos quando a página está visível. Voltar à aba força uma leitura. Esse
  polling usa o mesmo serviço Django/Gunicorn do webhook e não cria worker ou
  serviço systemd adicional.
- As opções `idade_minima_suporte`, `email_obrigatorio` e `bpa_ativo` são lidas
  da unidade. O limite é apresentado como política; não modifica tags 18–59/60+
  ou de dependentes nem esconde envios ao Funil registrados em qualquer faixa.
- Comercial mostra somente chats cuja última conversa real na unidade encerrou
  por idade. Uma conversa nova remove a tag, mesmo fora do período consultado;
  a configuração atual não altera uma tag histórica. A legenda explica cada filtro.
- Relatórios possui a tabela Encaminhamentos e encerramentos por idade abaixo
  dos quatro KPIs. Conta conversas (não contatos), por `finalizou_em >= início`
  e `< fim`, mesmo que exista atendimento posterior. Mostra suporte do limite
  atual, universal 90+ separada por titular/dependente, titular menor e dependente
  abaixo do mínimo BPA atual. Configurações diferentes e legados sem limite
  identificável ficam fora. Reescolher a mesma configuração inclui motivos iguais
  no período, independentemente da data dessa reconfiguração.
  Distingue contato enviado de encerramento sem contato; não comprova clique,
  atendimento humano, matrícula ou envio ao Funil. Falha de consulta não é zero.
- O relatório mostra métricas, comparação, demanda ao longo do tempo, perfis,
  satisfação e a etapa atual da conversa mais recente de cada contato que teve
  atividade no período. Cada contato conta uma vez. A etapa é um retrato atual;
  o banco não permite reconstruir em qual etapa a conversa estava em uma data
  passada.
- O histórico armazena texto e tipo da mensagem, mas não o payload exato dos
  botões enviados. Para mensagens interativas, o painel mostra os botões do
  catálogo atual daquela etapa como referência visual, sempre desabilitados.
- Os quatro indicadores agregados ficam na seção Relatórios. A seção Conversas
  prioriza a visualização da lista e do histórico, mantendo filtros e período.
- O CSV completo inclui todos os contatos ativos no período e deixa campos
  ausentes vazios. O CSV elegível exige nome, e-mail estruturalmente válido e
  telefone normalizado. Ambos usam
  cabeçalhos compatíveis com importação no Google Contatos e nunca alteram o
  banco.
- Há também duas exportações de dados essenciais, para todos os contatos ou
  apenas elegíveis, com somente Nome, E-mail e Telefone. Mantêm o nome completo
  em uma coluna, sem acrescentar rótulos ou datas, e reutilizam as mesmas regras
  de período, unidade, normalização e elegibilidade dos arquivos Google CSV.
  Somente nesses dois CSVs essenciais, o telefone brasileiro é exibido sem o
  prefixo internacional `+55`, preservando o DDD e o número.

## 20. Disponibilidade e recuperação automática

“O sistema não deve cair nunca” é um requisito de resiliência operacional e
recuperação automática. Isso não significa afirmar que o interpretador Python, a
máquina ou a rede jamais poderão falhar.

Sempre deverá existir uma camada capaz de conter a falha e manter ou restaurar o
serviço:

- falha do Redis utiliza fallback quando existe uma fonte segura no banco;
- falha de uma mensagem não encerra o processamento das demais;
- o worker captura falhas, preserva ou reagenda o estado quando possível e
  continua o loop;
- o worker do Funil isola erros por lead e reinicia falhas globais com espera
  linear de 5 a 60 segundos;
- o worker de follow-up isola erros por candidata e usa espera exponencial de
  5 até 300 segundos quando a consulta do lote falha;
- `flow_worker.py` mantém o loop de consumo e os tratamentos por tipo de exceção;
- se `worker_flow()` escapar com uma exceção, `iniciar_flow_worker.py` registra a falha,
  aguarda 5 segundos e inicia outro loop;
- o webhook responde de maneira controlada a entradas inválidas e falhas
  conhecidas;
- chamadas externas à Meta falham de forma controlada, sem confirmar no banco
  uma operação recusada pela Meta;
- caches degradam para fallback ou negam uma operação administrativa que
  produziria inconsistência.

Na produção atual, webhook, worker de atendimento, worker do Funil e worker de
follow-up são quatro serviços systemd independentes. Os três primeiros usam
`Restart=always`; follow-up usa `Restart=on-failure`. Todos têm `RestartSec=5s`.
As camadas de recuperação são complementares:

```text
operação individual falha
    -> exception ou fallback trata
    -> flow_worker continua
    -> iniciar_flow_worker reinicia o fluxo se ele escapar
    -> systemd reinicia o processo se ele encerrar
```

A URL pública e os serviços de produção devem permanecer disponíveis 24x7.
Falhas previstas não poderão produzir encerramento permanente do serviço nem
corrupção silenciosa. Os loops e fallbacks da aplicação atuam antes da supervisão
dos processos pelo sistema operacional.

Implementação principal:

- `workers/worker_flow/iniciar_flow_worker.py`
- `workers/worker_flow/response_flow/flow_worker.py`
- `workers/worker_funil/funil_worker.py`
- `workers/worker_funil/iniciar_worker_funil.py`
- `core/cache/redis_client.py`
- `callback/webhook/services/post_flow.py`
- `deploy/systemd/chatbot-webhook.service`
- `deploy/systemd/chatbot-worker-flow.service`
- `deploy/systemd/chatbot-worker-funil.service`
- `workers/worker_followup/iniciar_worker_followup.py`
- `workers/worker_followup/followup_worker.py`
- `deploy/systemd/chatbot-worker-followup.service`

## 21. Matriz de aderência conferida no código

| Regra | Estado atual | Observação |
|---|---|---|
| Somente a primeira mensagem sem resposta do turno é válida | Implementada | As demais não entram na fila nem no histórico enquanto existir uma fila aberta sem resposta própria do bot. |
| Liberar o próximo turno por resposta específica do bot | Implementada | O histórico vinculado à fila permite recuperação antes de `fila.status='sent'`, sem liberar uma sequência ilimitada. |
| Bloqueio de 30 dias depois da etapa final | Implementada | Banco e cache utilizam janela ou TTL de 30 dias. |
| Flood acima da métrica | Implementada | Redis, banco e memória formam a cadeia de avaliação; flood pode bloquear na Meta. |
| Payload grande | Implementada conforme a regra | Retorna HTTP 413 e não bloqueia a identidade informada no payload. |
| Assinatura inválida | Implementada conforme a regra | Retorna HTTP 403 e não confia no payload nem bloqueia possível vítima informada nele. |
| Falha operacional do webhook com mensagem válida | Implementada | Inserção/commit da fila e validação de unidade indisponível retornam HTTP 503 para permitir reentrega; descartes de negócio continuam HTTP 200. |
| Cache Redis com fallback para banco | Implementada nos caches principais | Unidades, clientes e conversas bloqueadas possuem estratégias de fallback. |
| Autocura Redis/banco | Implementada no contrato da V1 | Cobre falhas detectáveis e FK stale; edição direta no banco é proibida em produção. |
| Admin majoritariamente somente leitura | Implementada | As exceções operacionais são unidade (incluindo seu usuário de monitoramento), integração com o Funil e desbloqueio individual. |
| Admin somente desbloqueia clientes | Implementada | Meta primeiro; falha preserva o registro no banco. |
| Unidade Meta-first na criação e exclusão | Implementada | Falha da Meta impede a alteração do banco. |
| `status_pagamento` sem chamada Meta | Implementada conforme a regra | O valor controla a admissão da unidade, mas não registra nem remove o número na Meta. |
| Desvinculação definitiva da unidade | Definida operacionalmente | Remover do WABA oficial e excluir individualmente pelo Admin. |
| Worker continua ou reinicia depois de falha | Implementada em camadas | `funil_worker.py` recupera banco e agenda os ciclos; `iniciar_worker_funil.py` recria o worker após falha crítica. `iniciar_flow_worker.py` mantém a supervisão do atendimento. |
| Conversa elegível vira oportunidade no Funil | Implementada e desativada por padrão | Etapas 20–24, `funil_envios`, claim com lease e confirmação lógica da ApiCarrossel. |
| Uma falha de lead não interrompe o lote do Funil | Implementada | O item volta para `pending`; os demais continuam no mesmo ciclo. |
| Follow-up antes do agendamento | Implementada | Primeiro lembrete após 7h; despedida e encerramento após outras 7h sem resposta, nas etapas 1–17 e a 18 somente para unidade sem link, inclusive 8, dentro da janela do cliente. Retorno antes do encerramento valida a resposta; depois, abre nova conversa. |
| Supervisão dos quatro processos | Implementada | Webhook, flow e Funil usam `Restart=always`; follow-up usa `Restart=on-failure`. Nginx encaminha o endpoint público ao webhook. |

## 22. Orientação para futuras alterações

Antes de modificar o fluxo:

1. identificar qual regra deste documento está envolvida;
2. classificar a mudança como correção, refatoração ou alteração de produto;
3. preservar turno único, idempotência e limite de tentativas quando a tarefa não
   solicitar explicitamente o contrário;
4. mapear quedas antes e depois de cada commit;
5. testar fluxo normal, retry antes do bot, retry depois do bot e finalização da
   fila;
6. não tratar um comportamento esperado da V1 como bug apenas por ele parecer
   conservador ou incompleto.

## Follow-up de inatividade e reação do cliente

Implementado na V1.2.0. As instruções de operação vivem nos
[workers](workers/README.md#worker-de-follow-up) e no
[deploy](deploy/README.md#ativação-do-follow-up); não dependem dos planos de implementação.

O worker proativo envia o lembrete definido em `messages/followup_messages.py`
depois de sete horas sem reação à última resposta comum confirmada do bot.
NULL equivale a stage zero.
O envio exige conversa ativa em etapa 1–17 e a 18 somente para unidade sem link, unidade válida e adimplente, ausência
de bloqueios, de entrada posterior no histórico e de fila pending/processing do
mesmo par cliente/unidade, mesmo se ainda não vinculada à conversa. Uma fila
respondida mas ainda aberta também adia o proativo até sua finalização.

O canal exige janela aberta desde a última mensagem do cliente; este envio em texto
livre não usa template. A implementação reserva um minuto antes de completar 24h
para evitar despacho na borda. Isso não altera o limiar de sete horas do bot.

São dois relógios distintos: a última mensagem de toda a conversa precisa ser
do bot há pelo menos sete horas, e a mensagem mais recente do cliente, anterior
a ela, precisa estar dentro de 23h59. Bot há oito horas com cliente há 25 horas
é inelegível; bot há oito horas com cliente há nove horas pode ser elegível.

O worker produz 0 → 1 no primeiro envio. Após outras sete horas sem resposta,
contadas do primeiro envio confirmado, produz 1 → 2 com a despedida e encerra a
conversa (`status_ativa = false`, `finalizou_em` e motivo `followup_sem_resposta`).
Mantém a etapa de origem, sem aplicar o bloqueio de 30 dias. Não há terceiro envio.
Histórico, recibo, stage 2 e encerramento são gravados na mesma transação, somente
após confirmação da Meta. Falha no envio mantém a conversa aberta em stage 1.
Se a janela de 23h59 já expirou, não envia nem simula encerramento.

O segundo envio exige recibo real do primeiro, correspondente ao último bot e ao
`followup_last_sent_at`; marcação de legado sem recibo não permite uma despedida.
As duas camadas são restritas às etapas 1–17 e a 18 somente para unidade sem link, incluindo a 8. Uma reação antes do
segundo envio cancela sua elegibilidade e mantém o processamento descrito abaixo.
Depois do encerramento, outra mensagem abre novo ID de conversa, com stage zero
e mensagem inicial da etapa 1, sem prefixo de retorno nem nome de cadastro antigo.

O filtro **Follow-up** do painel considera stage 1 ou 2 da conversa mais recente
do mesmo cliente/unidade. Uma conversa posterior invalida o marcador antigo,
inclusive se estiver fora do período selecionado. O chat continua reunindo todo
o histórico permitido pelo período; excluir do filtro não apaga atendimento.

A primeira entrada aceita com stage positivo em conversa ainda ativa é armazenada e validada pelos
mesmos resolvers do atendimento normal. Respeitar as prioridades de cada etapa:
tratamentos específicos existentes (mídia, financeiro e reforço) permanecem;
resposta válida segue seu evento, efeitos e destino; resposta sem validação nem
tratamento específico reapresenta a pergunta neutra, sem reprimenda de contexto.
A triagem mantém apenas suas opções canônicas, sem ganhar tratamentos novos.

A resposta começa com `Bom te ver novamente, <nome> ☺️` ou a forma sem nome
`Bom te ver novamente ☺️`. Na etapa 1, nunca usar o nome de atendimento anterior:
um nome válido recebido agora é salvo e avança para a 2; caso contrário, tratar
ou repetir conforme a regra acima. O cadastro antigo não é apagado para saudação.
O prefixo independe do tempo de retorno, aparece uma vez e substitui a saudação
de três horas. No retorno comum por três horas, o processamento continua normal,
inclusive o tratamento de contexto inválido; só a redação do prefixo é igual.

Sem avanço, essa primeira reação não incrementa `turnos_sem_avanco`, inclusive
quando recebe tratamento específico. Uma transição válida zera esse contador
normalmente. A resposta seguinte volta à contagem normal de tratamentos.

**Exceção da etapa 8:** qualquer reação processada com follow-up pendente provoca
`8 → cliente_retornou → 9`, reutilizando o resolver e o mapa do retorno normal.
Não repetir a mensagem da 8, nem criar ou enviar uma variante de repetição.
A oferta da 9 preserva titular/dependente, botões e rodapé e recebe somente a
saudação de follow-up. O conteúdo não é classificado como tratamento ou aceite:
mesmo uma confirmação nessa reação apenas apresenta a 9; a próxima resposta
segue sua validação normal. Não há Funil ou encerramento nessa transição.

O histórico do cliente e o checkpoint conservam a origem 8; a resposta do bot
usa a etapa 9. A transição, o reset de turnos sem avanço do fluxo normal,
o histórico da resposta e a conclusão do follow-up pertencem ao mesmo commit.
Falha reverte esses efeitos juntos. Retry de retomada concluída reutiliza o
destino efetivamente gravado, inclusive uma repetição antiga da 8, sem reenviar,
refazer a transição ou zerar um ciclo posterior. A exceção vale também para
stage positivo legado sem data de envio; a elegibilidade proativa não muda.

A migração inicial marca followup_stage = 1 para todas as conversas ativas antigas,
incluindo etapas 20–23, e registra seus IDs, stages anteriores e a data da marcação
em followup_legado. Não envia lembrete, não encerra conversas, não inventa recibo
nem altera followup_last_sent_at. Stage positivo passa a indicar retomada pendente,
por envio real ou marcação inicial; somente o histórico/recibo comprova envio.
Novas conversas continuam com stage zero. O setup limpo não marca conversas.

Histórico, efeitos normais, marcação da retomada, reset para zero, eventual
encerramento e finalização da fila pertencem ao mesmo commit. followup_last_sent_at permanece como auditoria. Um retry de retomada
concluída usa a resposta já persistida, sem zerar um ciclo posterior. A mensagem
seguinte é interpretada normalmente; outro período de sete horas pode iniciar um
novo ciclo somente nas etapas 1–17 e a 18 somente para unidade sem link e com as demais condições de envio atendidas.
Stage maior que um em conversa legada ainda ativa segue a mesma recuperação;
stage 2 encerrado pelo novo proativo permanece como auditoria; negativo falha fechado.

A exceção deliberada é a repetição neutra diante de contexto inválido genérico
no primeiro retorno. Stage zero preserva o processamento normal por inteiro.
O registro proativo não possui fila nem hash de cliente de origem e não prova que
uma fila A/B/C foi respondida. Os recibos próprios identificam a conversa e a âncora
do ciclo; registros de retomada identificam a entrada processada para recuperação.

Os dois workers compartilham o lock de 110 segundos e seu fencing. Entrada aceita
após o último teste pré-envio pode cruzar com a chamada da Meta: confirmamos o
envio. No primeiro, o flow lê stage positivo ao obter o lock; no segundo, relê
o estado encerrado e abre outro atendimento, reagendando uma leitura obsoleta sem
consumir retry. A janela entre aceite
externo e commit local continua sujeita à duplicidade rara já aceita na V1.


## Extração dos campos de formulário FireAds

A correspondência do telefone na aba `LEADS GERAL - Feedback` identifica o cadastro.
Filtrar primeiro os canais Google Ads, Meta Ads e Organico Site; depois selecionar
a data/hora mais recente e, no empate, a maior `_row`. Datas inválidas ficam atrás
das válidas; sem data válida, usar a maior linha. Canais manuais não participam
dessa seleção. O destinatário vem somente de `Para quem é`, nunca de `Perfil/Faixa`.
Usar somente o registro selecionado pelas regras FireAds; não completar
campos vazios com dados de outra inscrição ou de uma conversa anterior.

Nome, e-mail e destinatário vêm de campos estruturados. Não aplicar as regras de
validação de respostas livres do WhatsApp para rejeitar nomes de perfil ou o
formato do e-mail. Extrair a primeira palavra do nome, ou as duas primeiras quando
formarem um par conhecido de nome composto; ignorar sobrenomes e complementos
posteriores. Exemplo: `Edcarlos Oliveira | Programador` torna-se `Edcarlos`.
Nomes compostos desconhecidos usam a primeira palavra. Aparar espaços do e-mail e
normalizar a caixa, preservando seu conteúdo sem testes de estrutura ou domínio.
Interpretar o destinatário pelas opções explícitas do formulário, nunca por idade.

Com os três campos extraídos e destinatário reconhecido, importar os dados juntos,
manter a origem Google/Meta/Orgânico Site, abrir na profissão e dispensar a coleta posterior do
e-mail. O marcador histórico `email_valido` significa coleta aceita do formulário
nessa rota; o flow não reaplica a validação estrutural. As validações das respostas
digitadas pelo cliente nas etapas comuns continuam iguais.

Por enquanto, campo vazio mantém o atendimento comum desde a etapa 1, com motivo
`campos_ausentes`; destinatário fora das opções conhecidas registra
`destinatario_desconhecido` sem inventar um vínculo. Ausência de telefone, falha
operacional, timeout e conflito de e-mail no banco conservam os tratamentos atuais.
A coleta parcial com saudação de formulário está proposta em
[valida_dados_parciais_fireads.md](docs/valida_dados_parciais_fireads.md) e ainda não foi implementada.

## Entrega do atendimento ao dashboard FireAds

Após a confirmação do Funil, a entrega ao dashboard usa fila independente e
respeita unidade adimplente e integrações ativas. Consulta e entrega usam somente
`aba_destino`, exibida como Aba de leads no Admin.

A consulta guarda a identidade da linha selecionada, inclusive no fallback por
formulário incompleto ou canal não elegível. A entrega confere essa identidade;
se a linha mudou de posição, relocaliza o mesmo registro. Não troca o alvo por
um formulário posterior. Registro desaparecido ou modificado fica pendente para
conferência, sem escrever em outra pessoa nem recriar o cadastro automaticamente.

Bloco já gravado da mesma conversa tem prioridade e reconcilia o envio. Só
atualizar `Observação`, preservando o conteúdo recebido da API e as demais colunas.
Sem referência da consulta, conferir novamente o telefone e usar a data/linha mais
recente antes de criar um cadastro orgânico. E-mail associado a outro telefone
impede criação. Snapshot legado conserva sua seleção e seu texto originais.

Google usa 113336; Meta usa 113340; Orgânico Site e orgânico usam 113481. Os dois
últimos são origens distintas, descritas nas observações. Fallback por dado
incompleto não afirma campanha nem ausência de cadastro. Sem integração FireAds,
preservar o canal configurado na unidade.

O texto compartilhado começa com `Observações de atendimento`. Classificar como
`Novo lead` só quando não há conversa anterior no mesmo chat (cliente/unidade);
caso contrário usar `Novo atendimento para Lead antigo`. Profissão do titular
precede os dados do dependente. Manter a explicação técnica da ESL Tech e a chave
única de reconciliação. Congelar payload, canal, classificação e texto antes do
primeiro POST, também para unidades sem FireAds. Retry não reconstrói esses dados.

A API externa não oferece escrita condicional; edição manual entre leitura e
POST continua podendo conflitar. Funil aceito antes de uma queda no commit local
pode ser reenviado. Não reenviar Funil por falha exclusiva no dashboard.
Operação, migração e limites: [Plano aplicado](atualizar_envio.md).

## Consumo mensal de mensagens Meta

A seção Consumo usa analytics coletado por worker independente e armazenado por
unidade/mês. Não altera etapas, elegibilidade do Funil, bloqueios, janelas de envio
ou retries. O recorte é serviço individual: janela gratuita, franquia Meta usada
e mensagens cobradas. A ESL cobre as primeiras 1.000 cobradas de cada mês; o
excedente é separado. Franquia Meta inicial: 1.000 por número/mês, desde outubro/2026.

O calendário usa o fuso informado pela WABA. Mês atual recebe coleta horária;
meses encerrados pendentes recebem conferência diária. Só consolidar no dia 25
previsto, se os volumes coincidirem com a coleta válida anterior de mês completo
feita em data local anterior. Falha/divergência prorroga para o próximo dia 25.
Consolidado é decisão interna da ESL, não fechamento de fatura pela Meta, e encerra
as coletas automáticas do mês. Valores monetários no painel são referências.

A interface e os PDFs leem exclusivamente o banco da unidade autenticada. Falha
não apaga valores anteriores nem cria um saldo fictício. A data exibida é a última
coleta válida do worker. Fusos e fronteiras de meses existentes são preservados;
mudança incompatível de conta/número/fuso exige revisão, sem misturar recortes.
Procedimento operacional: [Consumo Meta](deploy/consumo_mensal_meta.md).

## Reserva com e sem plataforma

A configuração atual de `unidade.link_agendamento` decide a saída da triagem: com link, 17 → 20; sem link, 17 → 18 (preferência de turno) → 19 (contato comercial). A satisfação converge em 21 → 22 → 23 → 24, com salto 22 → 24 na recusa de comentário. As etapas 1–17 conservam suas regras.

`conversa.turno` aceita NULL, manha, tarde ou noite e é salvo somente na transação de 18 → 19. É preferência, não confirmação de agendamento. Qualquer texto posterior na 19 apresenta a nota da 21; não é interpretado como nota nessa mesma interação. Mídia repete a orientação da 19.

Na etapa 18, os três botões e frases afirmativas como `só posso pela tarde`,
`prefiro ir de manhã` e `à noite fica melhor para mim` definem um único turno.
Aceitar caixa, acentos, pontuação e os sinônimos matutino, vespertino e noturno.
Repetir o mesmo turno não cria uma segunda escolha. Dois turnos distintos,
negação, dúvida, pergunta ou ausência de escolha recebem o mesmo tratamento
pedindo **apenas um turno**, sem avançar nem salvar preferência. `Amanhã`,
`boa tarde` e `trabalho de manhã` não autorizam inferir um turno.

O webhook extrai o título da opção de `interactive` e `interactive_button`,
usando o identificador textual quando o título estiver ausente. O worker
aceita ambos os tipos nas etapas com opções, inclusive na recuperação de uma
resposta já enviada. Não interpretar o texto citado da pergunta anterior como
resposta; não flexibilizar a validação específica de cada etapa nem aceitar mídia.

O Funil exige 20–24 com link ou 19/21–24 sem link, considerando a configuração vigente na seleção, no claim e no snapshot. Preservar recibo de sucesso se o CRM já aceitou. O snapshot e o painel incluem turno da própria conversa, quando preenchido.

Follow-up proativo: 1–17 em ambas as rotas e 18 somente sem link; a 19 e a 20 não recebem novos lembretes. São preservadas as duas camadas de sete horas, os recibos, o encerramento no segundo lembrete e as guardas existentes. A reação ao primeiro segue a validação normal: um turno válido na 18 avança para 19 e é persistido. Contexto inválido genérico repete; tratamentos específicos continuam prioritários. Retomadas legadas são remapeadas por significado; a exceção 8 → 9 permanece.

Instalação existente exige migração própria: IDs antigos 18/19/20/21/22 tornam-se 20/21/22/23/24. Não executar setup ou seeds no banco de produção nem reaplicar migrações históricas. Preservar o Consumo Meta, seus fusos, worker, relatórios e PDFs, a compatibilidade PyWa 4.5.0, a exceção universal de idade 90+, o comentário livre e a despedida por participante.
