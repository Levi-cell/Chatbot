# Plano autoritativo — `user_id`, WA ID e PyWa 4.x

> **Baseline autoritativa — V1.0.7 (`2bc41888db4987e957c5653825acf4a55e9d611d`):** o estado inicial deste plano
> já possui `unidade.nome_unidade`, `unidade.nome_agente` e `unidade.genero`,
> com gênero restrito a `masculino` ou `feminino`. Esses campos configuram
> somente as apresentações iniciais padrão, de mídia, financeira e de
> tratamento de reforço escolar da etapa 1. Eles não identificam cliente e não
> entram em turno, lock, fila, cache de identidade, anti-flood ou
> reconciliação. A implementação de `user_id` deve preservar esse contrato e
> nunca restaurar a coluna legada `unidade.nome`.

## 1. Estado deste documento

Este plano substitui integralmente as versões anteriores do desenho de
`user_id`.
Ele ainda **não foi aplicado ao runtime**. Nesta revisão, os dois planos
Markdown são sincronizados com a baseline; todos os caminhos de código, banco,
testes e deploy citados abaixo continuam descrevendo impacto futuro.

A baseline versionada usada nesta revisão é a V1.0.7, commit completo
`2bc41888db4987e957c5653825acf4a55e9d611d`, com 22 etapas e 25 transições.
Sobre ela, o estado pré-`user_id` auditado em 29/08/2026 contém os deltas
aprovados e ainda não necessariamente consolidados em um único commit descritos
nesta seção. A futura implementação deste plano acrescentará somente a etapa de
compartilhamento oficial do contato após o nome; por isso o estado final terá 23
etapas e 27 transições. Nenhum dos deltas pré-existentes abaixo cria etapa ou
aresta adicional.

O commit-base já contém as mensagens editoriais das etapas atuais 2, 10 e 22
(que continuam sendo 3, 11 e 23 após a renumeração), o snapshot de profissão em
`conversa.profissao`, a coluna `cliente.profissao`, sua migração e a proteção
aditiva do validador de profissão. Esses itens não são deltas posteriores ao
commit: o plano apenas os preserva nos blocos renumerados e exige que o estado
do banco já esteja materializado. A proteção continua recusando somente as oito
respostas completas observadas como fora de contexto, repetindo a própria etapa
sem criar nova etapa, evento ou persistência.

O estado de trabalho auditado depois do commit acrescenta somente os deltas que
precisam atravessar explicitamente a renumeração: o prefixo atual da mensagem da
etapa 11 e o botão `Começar triagem` (futura etapa 12), a saudação de retorno, a
proteção contextual da oferta e a política de suporte ao idoso/e-mail. O texto
original da etapa 11 permanece como parte da baseline; o prefixo e o botão são
os únicos ajustes editoriais dessa mensagem a preservar.

A saudação de retorno `Olá novamente, {nome}!` ocorre quando o cliente
responde na mesma conversa e unidade depois de pelo menos três horas desde a
última mensagem efetivamente enviada pelo bot. Ela é apenas um prefixo da
resposta normal já escolhida, tanto em avanço válido quanto em tratamento
inválido. Não cria etapa, evento, transição, envio ou linha de histórico
adicional e não altera turno, retry, lock, identidade ou persistência. Seu
contrato completo está na seção 10.2.

Outro delta funcional é a proteção contextual da oferta: pedidos de informação como
`quero mais informações` não são confirmação positiva, enquanto respostas
curtas como `quero`, `sim, quero`, `quero sim` e `sim, gostaria` continuam
válidas. Essa regra está na etapa atual 7 e passa à futura etapa 8 sem criar
evento ou aresta.

O último grupo é a política de suporte ao idoso e obrigatoriedade de e-mail,
materializada pela migração prévia
`deploy/migrations/20260829_adicionar_suporte_idoso_email_obrigatorio.sql`.
Ela adiciona `unidade.suporte_idoso BOOLEAN NOT NULL DEFAULT FALSE`,
`unidade.email_obrigatorio BOOLEAN NOT NULL DEFAULT TRUE` e o motivo de
encerramento `encaminhado_suporte_idoso`. As unidades existentes preservam a
configuração geral anterior pelos defaults, ressalvada a exceção universal
aprovada de e-mail opcional para titular de 60 a 99 anos. Essa migração é
pré-requisito do plano
de `user_id`: o SQL futuro apenas prova e preserva seu estado, sem recriar as
colunas, reexecutar backfill ou alterar seus valores.

Os contratos de payload usados como referência são:

- `payloads/WAID.json`;
- `payloads/BSUID_USERNAME.json`;
- `payloads/WAID_BSUID_USERNAME.json`;
- `payloads/CONTACT_INFO.json`.

Os três primeiros representam combinações normais de identidade no envelope.
`CONTACT_INFO.json` representa o webhook inbound recebido como resposta ao envio
outbound `request_contact_info(...)`: o nome da chamada não aparece literalmente
no retorno; a prova persistível é `type='contacts'` com
`origin='contact_request'` e o WA ID dentro do cartão oficial.

Os nomes de dois fixtures e o nome deste próprio Markdown ainda contêm `BSUID`
por legado de arquivo; esses caminhos serão preservados para não quebrar as
referências da tarefa. No contrato, no banco, no código e nos logs o nome correto
será sempre `user_id`. Não são dois identificadores diferentes.

Esses arquivos são fixtures representativas, e não capturas reais de produção.
Antes do deploy, o primeiro payload bruto real de cada formato deverá ser salvo,
anonimizado e confrontado com os testes.

Quando este plano for aplicado, cada passo deverá apresentar o conteúdo completo
de todo arquivo criado ou alterado. Não serão aceitos trechos soltos que
dependam de interpretação durante o deploy. Como os senders ainda serão
refinados antes da aplicação, o apêndice de código completo deverá ser
regenerado a partir do commit definitivo imediatamente antes da implementação;
o contrato comportamental e de banco deste documento já é autoritativo.

## 2. Objetivo e limites

O objetivo é aceitar os dois identificadores técnicos enviados pela Meta e
preservar uma informação complementar:

1. WA ID, identificador técnico prioritário;
2. `user_id` privado e escopado ao negócio, usado como fallback de destinatário
   e de identidade de negócio somente no início do atendimento enquanto o WA ID
   ainda não foi compartilhado; no transporte inbound ele continua sendo aceito
   quando for o único identificador que a Meta entregar;
3. username opcional, salvo apenas como informação adicional.

Prioridade técnica:

```text
wa_id conhecido                          -> usar wa_id
wa_id ausente nas etapas iniciais        -> usar user_id
username                                 -> snapshot e informação opcional no Funil
etapa posterior sem wa_id                -> não enviar
```

O plano não autoriza:

- mudar os pontos ou a ordem de `commit` e `rollback` do `flow_worker`;
- mudar posse da fila, dequeue, quantidade de retries ou autocura;
- deslocar `reagendar_se_houver_mensagem_anterior()`;
- alterar a semântica de `reagendar_mensagem_sem_erro()` ou
  `reagendar_mensagem()`;
- deslocar ou remover `bot_resposta_atual()`;
- criar advisory lock novo no worker;
- mudar a posição de `chatbot.lock_conversa()`;
- alterar os resultados funcionais dos fluxos A/B/C de turno;
- criar salto, retorno ou avanço fora de `chatbot.etapa_transicao`;
- usar username como identidade, lock, destinatário Meta ou chave de conversa;
- usar `user_id` como fallback de sender depois da etapa obrigatória de
  compartilhamento do WA ID;
- usar WAMID como identidade da pessoa;
- executar `ALTER TABLE` em Python;
- usar `metadata.display_phone_number` como telefone do cliente, fallback de
  `metadata.phone_number_id` ou argumento `sender` da Meta.

As extensões comportamentais aprovadas neste plano são:

1. transportar `wa_id`, `user_id` e username como dados adicionais nos contextos
   já existentes, deixando o resolver escolher para o sender `wa_id` ou, apenas
   antes do compartilhamento obrigatório, `user_id`;
2. reconciliar um cliente provisório com o cliente global canônico quando um
   payload conjunto ou o compartilhamento oficial provar o vínculo;
3. preservar uma única janela anti-flood para `user_id` e `wa_id` oficialmente
   vinculados na mesma unidade, somando as duas rajadas e deduplicando-as por
   WAMID, sem inferir equivalência por username, nome ou proximidade temporal;
4. resolver turno, ordem, bloqueios e denylist pelo conjunto de aliases
   oficialmente comprovado do cliente na unidade, sem exigir que clientes
   legados passem a possuir user ID;
5. tornar a reconciliação consciente da posse das conversas envolvidas: o merge
   reutiliza exatamente o limiar da V1.0.7, no qual um lock só é stale quando
   `processing_started_at < NOW() - INTERVAL '110.0 seconds'`; antes disso ele
   nunca é removido. O takeover incrementa `lock_version`, preservando a proteção
   já existente no `unlock` sem prometer cancelamento de um trabalho externo já
   iniciado.

A reconciliação é um efeito de dados executado pelo mesmo cursor dentro da
transação que `validar_banco_mensagem()` já utiliza e não cria um novo ponto de
`commit` ou `rollback`. Existem duas saídas controladas. Se qualquer conversa que
o merge precise alterar estiver com lock fresco, a transação não faz mutação e o
item volta a `pending` pelo requeue sem erro de 5 segundos, compensando a
tentativa consumida. Se a reconciliação comprovar um bloqueio anterior ainda
vigente, ela encerra a conversa nova com `bloqueio_reconciliado`, remove o item
atual da fila na mesma transação e devolve um resultado terminal; o commit que já
existe logo depois da validação confirma o conjunto atômico e o ciclo não chega
a histórico, lock normal, resolver ou sender. Fora desses dois casos,
`validar_banco_mensagem()` devolve o contexto normal esperado pelo restante do
`flow_worker`.

O plano não cria tratamento especial para Funil dentro da transação de
reconciliação. Denylist, bloqueio temporário, bloqueio de 30 dias e bloqueio Meta
passam a consultar os aliases comprovados da mesma pessoa/unidade. A
reconciliação não reinicia prazo nem inventa bloqueio: ela apenas preserva um
bloqueio canônico anterior e consolida a referência operacional necessária para
que ambos os aliases o reconheçam. A continuidade anti-flood aprovada continua
nas camadas próprias de webhook/cache/repositório.

O WAMID continua servindo para deduplicar e correlacionar uma mensagem. Ele não
substitui a identidade usada pelo turno. Antes de existir prova, o turno usa o
único alias tipado disponível com `id_phone_unidade`; depois da prova, qualquer
alias recebido resolve o mesmo sujeito lógico `(id_cliente, id_unidade)` e o
mesmo conjunto de aliases daquela unidade.

## 3. Contrato dos payloads

### 3.1 Campos da unidade

Dentro de `entry[].changes[].value`:

- `metadata.phone_number_id`: ID técnico obrigatório do número da unidade e
  única fonte autoritativa para localizar a unidade;
- `metadata.display_phone_number`: texto público opcional, apenas para
  observabilidade/apresentação;
- `entry[].id`: WABA ID;
- `id_portfolio`: não vem no webhook; será lido do cadastro da unidade;
- `nome_unidade`, `nome_agente` e `genero`: não vêm no webhook; são lidos da
  unidade localizada por `metadata.phone_number_id` somente para montar a
  apresentação inicial da etapa 1;
- `suporte_idoso` e `email_obrigatorio`: não vêm no webhook; são políticas
  booleanas lidas da mesma unidade em snapshots específicos das etapas de idade
  e e-mail. Elas não participam da identidade nem podem ser inferidas pelo
  conteúdo da mensagem.

`nome_unidade` é o nome institucional exibido, `nome_agente` é o nome editorial
do atendente virtual e `genero` aceita somente `masculino` ou `feminino`, para
selecionar o artigo da apresentação. Nenhum desses campos identifica o cliente,
escolhe destinatário ou participa de turno, lock, fila, cache de identidade,
anti-flood ou reconciliação.

`numero_comercial` também permanece dado cadastral da unidade. O módulo
compartilhado `core/integrations/whatsapp/numero_comercial.py` é a única fonte
para normalizar, validar e montar o link `wa.me`; tanto o Admin quanto o sender
usam esse mesmo contrato. Ativar `suporte_idoso` exige um número comercial
brasileiro válido.

Sem `metadata.phone_number_id`, o evento estruturalmente inválido recebe HTTP 200
e não entra na fila: a Meta reenviaria o mesmo envelope, não um envelope
“corrigido”. `metadata.display_phone_number` jamais substitui esse ID, jamais
identifica cliente ou unidade e jamais é passado como `sender`; todo envio usa o
`phone_number_id` canônico da unidade validada no banco. HTTP 503 fica reservado
a falha transitória depois de uma entrada estruturalmente válida quando não
existir fallback seguro, como RDS indisponível, falha de `INSERT` ou de commit.
Falha isolada do Redis continua usando os fallbacks já definidos pela V1.0.7.

### 3.2 Campos do cliente

| Informação | Caminho principal | Fallback permitido |
|---|---|---|
| WA ID do remetente | `value.contacts[].wa_id` | `value.messages[].from` |
| User ID | `value.contacts[].user_id` | `value.messages[].from_user_id` |
| Username | `value.contacts[].profile.username` | nenhum |

No retorno oficial de compartilhamento:

| Informação | Caminho |
|---|---|
| Tipo | `value.messages[].type = "contacts"` |
| Origem | `value.messages[].contacts[].origin = "contact_request"` |
| Telefone exibido | `value.messages[].contacts[].phones[].phone` |
| WA ID compartilhado | `value.messages[].contacts[].phones[].wa_id` |

Existem dois arrays `contacts` diferentes:

- `value.contacts[]` descreve o remetente;
- `value.messages[].contacts[]` descreve o cartão de contato compartilhado.

Eles nunca podem ser confundidos.

### 3.3 Matriz de entrada

| Entrada | Webhook | Identidade técnica | Funil |
|---|---|---|---|
| WA ID + user ID + username | aceita | WA ID | WA ID + `@username` |
| WA ID + user ID | aceita | WA ID | WA ID |
| WA ID + username | aceita | WA ID | WA ID + `@username` |
| somente WA ID | aceita | WA ID | WA ID |
| user ID + username, sem WA ID, vínculo desconhecido | aceita | user ID temporariamente | exige etapa de contato |
| somente user ID, vínculo desconhecido | aceita | user ID temporariamente | exige etapa de contato |
| somente user ID já mapeado, em qualquer etapa | aceita | user ID permanece a identidade do item; cliente e WA ID canônico são resolvidos no worker | fluxo normal somente com WA ID canônico |
| somente username | ignora com HTTP 200 | inexistente | não executa |
| nenhum dos três | ignora com HTTP 200 | inexistente | não executa |

Um evento é processável quando:

```python
processavel = bool(wa_id_remetente or user_id)
```

O WA ID contido no cartão de um `contact_request` não torna o evento processável
por si só e não vira identidade do remetente. Ele é o
`wa_id_compartilhado`; no fixture atual o remetente continua processável pelo
`user_id` presente no envelope.

## 4. Decisões de identidade

### 4.1 WA ID é a identidade prioritária

O resolver escolhe o destinatário do sender a partir dos valores canônicos
carregados do banco no contexto. Nas etapas iniciais, antes do compartilhamento
obrigatório:

```python
destinatario = wa_id_banco or user_id_banco
```

Depois que a etapa obrigatória comprovar e persistir o WA ID, todos os senders
posteriores exigem `wa_id_banco`; eles não voltam silenciosamente ao `user_id`.
O username nunca entra nessa seleção.

O evento serve para alimentar a persistência. Antes do envio, o worker lê e
reconstrói os valores pelo banco e os coloca em `contexto_historico`; nenhum
resolver deve encaminhar diretamente ao sender um identificador bruto do payload.
A ausência de um campo em evento posterior nunca apaga valor já conhecido.

#### 4.1.1 Identidade do item, WA ID compartilhado e WA ID canônico

Os três papéis abaixo são distintos e não podem ser intercambiados antes da
validação bancária:

- `identidade_do_item`: identidade técnica pela qual o evento entrou. Ela é
  definida uma única vez na entrada, persistida pelos snapshots originais da
  fila e reconstruída deterministicamente sem consultar valores enriquecidos
  depois. Ela permanece congelada durante turno, ordem, retry, logs e autocura
  daquele item;
- `wa_id_compartilhado`: candidato extraído exclusivamente do
  `contacts/contact_request`. Antes da prova bancária, não é destinatário, chave
  de turno, chave de cache nem identidade da conversa;
- `wa_id_canonico`: `cliente.wa_id` relido do banco depois da persistência ou
  reconciliação. Somente ele pode ser usado pelo sender que avança da etapa 2
  para a 3 e por todos os senders posteriores.

No handoff representado por `payloads/CONTACT_INFO.json`:

```text
identidade_do_item  = (user_id, user_id do remetente)
wa_id_compartilhado = WA ID do contato oficial
wa_id_canonico      = cliente.wa_id relido depois da validação
```

Persistir ou descobrir o WA ID canônico não recalcula a identidade do item no
meio do ciclo. Um retry do mesmo item reconstrói a mesma identidade original.
Fila e histórico daquele item nunca recebem backfill de WA ID, user ID ou
username. Essa separação é apenas de papel lógico; não cria uma quarta coluna de
snapshot: no `contact_request`, o marcador persistido + o user ID identificam o
alias de entrada, enquanto o WA ID do mesmo evento permanece o candidato oficial.

### 4.2 User ID escopado e conjunto de aliases

O `user_id` não é global como o WA ID. O vínculo canônico será:

```text
cliente 1 --- N user_id_cliente N --- 1 unidade --- id_portfolio
```

Cada linha de `chatbot.user_id_cliente` liga exatamente um `id_cliente` a um
`user_id` dentro de uma unidade. Assim:

- o mesmo cliente global continua tendo um único `id_cliente`;
- o cliente pode ter um `user_id` diferente em cada unidade;
- a volta futura usando somente `user_id` resolve o cliente canônico sem criar
  outro cliente provisório;
- um payload que já contenha WA ID + user ID registra ou atualiza o vínculo no
  primeiro processamento, sem esperar a etapa especial;
- `id_portfolio` permanece na unidade para consultas de monitoramento e não
  entra no caminho transacional online.

O sujeito lógico da unidade é `(id_cliente, id_unidade)`. Seus aliases
comprovados são o conjunto:

```text
{ ('wa_id', cliente.wa_id), ('user_id', user_id_cliente.user_id) }
```

Somente membros existentes entram no conjunto. Isso é uma relação de
equivalência, não uma chave concatenada e não uma exigência de coexistência:

- cliente legado apenas com WA ID continua válido com um conjunto de um alias;
- cliente privado provisório apenas com user ID continua válido temporariamente
  com um conjunto de um alias;
- depois da prova oficial, WA ID e user ID da mesma unidade resolvem o mesmo
  cliente e o mesmo turno/bloqueio;
- o mesmo user ID em outra unidade pertence a outro escopo;
- o WA ID continua global no cadastro de cliente, mas toda proteção online o
  combina com o `phone_id_unidade` recebido e validado;
- igualdade textual entre um WA ID e um user ID não prova associação.

Quando não existe prova persistida, o fluxo online usa
somente o alias tipado do evento: `(tipo, valor, phone_id_unidade)`. Quando existe
prova, turno, ordem, anti-flood, bloqueios e denylist recebem o conjunto inteiro,
adquirem os locks de aliases em ordem determinística e consultam qualquer membro
do conjunto. Não se cria uma string `wa_id+user_id`, não se exige user ID de dados
legados e não se executam duas decisões independentes para a mesma mensagem.

`id_portfolio` não será colocado na fila, nas chaves de turno nem nos locks. Ele
servirá a consultas futuras de monitoramento.

### 4.3 Username não é identidade

Username:

- pode ser `NULL` em todas as tabelas;
- nunca é `UNIQUE`;
- nunca seleciona cliente ou conversa;
- nunca entra em lock, turno, cache ou deduplicação;
- nunca é usado no campo `to` da Meta;
- é mostrado no funil com exatamente um `@`, quando existir.

Somente `cliente.username` representa o valor canônico mais recente. Todo novo
payload com username não vazio sobrescreve essa coluna; payload sem username
preserva o valor anterior.

As demais tabelas guardam snapshots históricos:

- fila, histórico e flood: username daquele evento, imutável após o `INSERT`;
- conversa: username presente na criação da conversa, imutável; se a conversa
  nasceu sem username, permanece `NULL`;
- bloqueio: username conhecido no instante em que o bloqueio foi criado.

Reconciliação oficialmente provada não preenche nem reescreve fila, histórico ou
`conversa.username`. O contexto do sender pode reler os aliases canônicos do
banco, mas isso não altera o registro histórico do evento. A única coluna
mutável de username é `cliente.username`, sempre pelo último valor não vazio.

### 4.3.1 Profissão canônica e snapshot da conversa

`cliente.profissao` já pertence ao commit-base e guarda a profissão válida mais
recente do cliente global. Sua migração própria também está versionada nessa
baseline e precisa estar materializada no banco antes da migração de `user_id`.
`conversa.profissao` continua sendo o snapshot da
conversa em que aquela profissão foi aceita e nunca é reescrita por uma conversa
posterior.

As duas colunas só são persistidas quando a etapa de profissão aceita o valor;
criar ou retomar uma conversa não copia automaticamente a profissão canônica para
ela. O efeito da transição atualiza `conversa.profissao` e
`cliente.profissao` com o mesmo cursor e na mesma transação. A repetição do mesmo
efeito é idempotente, e uma conversa futura com outra profissão válida atualiza
somente seu próprio snapshot e o último valor do cliente, sem retroagir nas
conversas anteriores.

Antes de produzir um evento de profissão válida, o validador compara a resposta
inteira após a normalização já existente. Somente estas oito respostas
observadas retornam `profissao_fora_contexto`: `Pra minha filha na verdade`,
`Não entendi`, `Para meu filho`, `Pra meu filho`, `Minha filha é autista e
percebo q ela tem dificuldade no aprendizado , vcs atende autista tambem`,
`não seria pra meu filho`, `Meu filho` e `Vc ouviu áudio ou ligação`. Esse
resultado reapresenta a pergunta da etapa de profissão sem evento, avanço ou
persistência. A proteção não procura palavras isoladas e, portanto, não pode
barrar por si só respostas legítimas como `Técnica de áudio`, `Faço ligações,
trabalho com telemarketing` ou `Sou psicóloga, mas é para minha filha de 16
anos`.

O Funil continua lendo exclusivamente `conversa.profissao`. No handoff de um
cliente provisório para um cliente canônico, uma profissão válida já capturada na
conversa/cliente provisório é copiada para `cliente.profissao` do canônico antes
da exclusão do provisório; o snapshot da conversa reatribuída permanece intacto.

### 4.3.2 Suporte ao idoso e política de e-mail preservados

Essas regras são ortogonais à identidade e já pertencem ao estado
pré-`user_id`. A renumeração muda apenas os IDs técnicos: a etapa atual de idade
6 passa a 7; a coleta atual de e-mail 10 passa a 11; a resposta do bot que hoje
entra na etapa 11 passa a 12.

Na etapa futura 7, a ordem é invariável:

1. mídia, reforço escolar e financeiro continuam sendo tratamentos sem avanço;
2. uma idade inválida continua repetindo a etapa;
3. idade maior que 99 conserva o encerramento histórico e sua precedência;
4. somente titular — nunca dependente — entre 60 e 99 anos, inclusive, com
   `unidade.suporte_idoso = TRUE`, recebe a mensagem de encaminhamento e o botão
   `Falar com Comercial`;
5. o encaminhamento persiste a idade, encerra com
   `motivo_encerramento='encaminhado_suporte_idoso'`, usa `bloqueio_dias=0`, não
   produz evento/transição e não gera lead no Funil;
6. com a flag desativada, ou para dependente, o fluxo etário anterior continua
   normalmente.

No retry, o encerramento especializado é reconstruído pela resposta do bot já
persistida para a mensagem original. A configuração atual do Admin não é
reavaliada para reinterpretar uma decisão histórica. O helper compartilhado de
número comercial é reutilizado pelo sender; não se cria normalizador local.

Na futura etapa 11, a precedência também permanece:

```text
mídia/tipo não suportado -> reforço escolar -> financeiro -> política de e-mail
```

A política efetiva é calculada pelo snapshot da conversa/unidade:

- titular de 60 a 99 anos: e-mail sempre opcional, mesmo com a flag ativa;
- titular abaixo de 60: segue `unidade.email_obrigatorio`;
- dependente de qualquer idade elegível: segue `unidade.email_obrigatorio`;
- `email_obrigatorio = FALSE`: e-mail opcional para todos que chegaram à etapa.

`core/validacoes/email.py` é o classificador puro e autoritativo. Ele distingue
`email_valido`, `email_ausente` e `email_nao_informado`. Em modo obrigatório,
somente um endereço estruturalmente válido avança; em modo opcional, endereço,
ausência explícita (`não tenho`, por exemplo) ou outra resposta ordinária
avançam. As três possibilidades reutilizam a única aresta técnica
`email_valido` da futura etapa 11 para a 12; não se criam eventos nem transições
paralelas para resultados sem endereço.

O efeito é absoluto e idempotente: endereço válido substitui `cliente.email`;
ausência ou resposta comum aceita grava `NULL`, inclusive se existia e-mail de
uma conversa anterior. Tratamentos de mídia, reforço e financeiro e respostas
rejeitadas no modo obrigatório não alteram o cadastro. No retry, uma resposta
que comprovadamente já recebeu a mensagem da futura etapa 12 é reclassificada
pela própria mensagem histórica, sem consultar a flag mutável do Admin.

O contexto da coleta de e-mail deve existir no arquivo futuro
`core/repositories/fluxo/contextos/etapa11.py`. O caminho atual
`contextos/etapa10.py` não pode ser perdido quando a etapa atual 9 for
renumerada para 10: o plano prático primeiro materializa o novo contexto 11 e
depois substitui o contexto 10 pelo conteúdo correspondente à etapa renumerada.

### 4.4 Handoff seguro de user ID para WA ID

O evento `CONTACT_INFO.json` contém o `user_id` do remetente e o novo WA ID em
`messages[].contacts[].phones[].wa_id`.

Esse evento deve:

1. exigir que a assinatura do webhook já tenha sido validada, exigir
   `metadata.phone_number_id` e localizar por ele uma única unidade;
2. localizar a conversa atual pelo vínculo `(user_id, id_unidade)`;
3. confirmar, antes de qualquer mutação, que a conversa está ativa na etapa 2 e
   que o item pertence exatamente a essa conversa/unidade;
4. validar que se trata de `type='contacts'`, com conjunto de origens exatamente
   `{'contact_request'}`, user ID presente e exatamente um WA ID oficial não
   ambíguo; `display_phone_number` nunca completa essa prova;
5. validar o estado dos dois vínculos, dos clientes envolvidos, dos aliases e das
   conversas sob row locks adquiridos em ordem determinística;
6. somente depois desse gate completo tratar o número do cartão como
   `wa_id_compartilhado`, persistir o WA ID comprovado e consolidar
   `user_id_cliente`;
7. reconciliar o cliente provisório, se necessário, como efeito de dados dentro
   da validação de banco já existente;
8. reconstruir `wa_id`, `user_id` e username a partir do banco no
   `contexto_historico`;
9. usar o WA ID persistido como destinatário da resposta que avança o fluxo;
10. manter o `user_id` e o username apenas como dados refletidos no
    `contexto_envio`, sem reescrever snapshots históricos.

O gate é indivisível: origem ausente/desconhecida, contato manual, múltiplos
candidatos, user ID sem vínculo, unidade divergente, etapa divergente ou conflito
de WA ID não executam `UPDATE`, `INSERT` ou `DELETE` de identidade. Entrada apenas
inválida recebe o tratamento de contexto da etapa; contradição entre vínculos ou
indisponibilidade que impeça decidir com segurança falha de forma fechada e segue
rollback/reentrega, nunca merge parcial.

O item continua seguindo exatamente o turno que já foi adquirido para a
mensagem. Sua identidade primária continua sendo o user ID para logs, cache,
retry e autocura; não é recalculada no meio do ciclo. A consulta de ordem, porém,
usa o conjunto de aliases oficialmente provado da pessoa/unidade para que um item
WA e um item user ID não ultrapassem um ao outro. Somente o destinatário muda
para o WA ID canônico depois de o valor ter sido confirmado e relido do banco.

Existem três resultados idempotentes:

- WA ID novo: completar o próprio cliente provisório e manter a conversa;
- WA ID do mesmo cliente: confirmar o vínculo e enriquecer apenas o cadastro e os
  aliases canônicos permitidos, sem backfill de fila/histórico/username da
  conversa;
- WA ID de um cliente global antigo: executar a reconciliação canônica descrita
  na seção 4.5.

O webhook não decide merge de cliente, porque ele não é dono do `id_cliente` nem
da conversa. Ele valida e persiste o evento; a eventual reconciliação pertence à
validação de banco já existente no worker.

### 4.5 Reconciliação do cliente global

O cenário aprovado é:

1. no passado, o cliente falou com WA ID público e recebeu um `id_cliente`;
2. depois, volta para a mesma unidade somente com `user_id`;
3. sem vínculo prévio, o sistema cria cliente provisório + conversa nova +
   `user_id_cliente` na mesma transação;
4. após responder o nome, o cliente compartilha oficialmente seu contato;
5. o WA ID oficial já pertence ao cliente global antigo.

Isso não representa duas pessoas compartilhando o mesmo WA ID. O caso esperado é
o **mesmo cliente** que antes expunha o número e, depois de ativar a privacidade,
foi visto provisoriamente apenas pelo `user_id`. A ocorrência deve ser rara, mas
é legítima; a relação `user_id_cliente` faz essa reconciliação acontecer no
máximo uma vez por cliente/unidade enquanto aquele vínculo permanecer válido.

Nesse caso, a conversa nova é legítima e será preservada. Usando o mesmo cursor
e a mesma transação que já existem em `validar_banco_mensagem()`, a reconciliação
executa somente estes efeitos de dados, depois do gate completo da seção 4.4:

1. localizar por leitura pura e depois bloquear em ordem global determinística:
   clientes provisório/canônico por `id_cliente`, vínculo
   `(user_id, id_unidade)` e, por fim, conversa nova atual e eventual conversa
   canônica anterior por `id_conversa`;
2. confirmar que o provisório ainda possui `wa_id IS NULL`, que a conversa nova é
   exatamente a conversa da etapa 2 e que o WA ID pertence ao cliente canônico;
3. inspecionar `processing`, `processing_started_at` e `lock_version` das duas
   conversas. Se qualquer lock ainda não satisfizer literalmente
   `processing_started_at < NOW() - INTERVAL '110.0 seconds'`, não executar
   nenhuma mutação e devolver contenção para requeue sem erro de 5 segundos;
4. somente quando o predicado anterior for verdadeiro, considerar o lock stale,
   limpar a posse sob o row lock e incrementar atomicamente `lock_version` antes
   de alterar a conversa. O `unlock` de um dono anterior, que ainda possua
   a versão antiga, não poderá liberar uma posse mais nova. O merge não antecipa
   o lock normal do sender nem redesenha todas as escritas pós-lock existentes;
5. copiar o nome capturado na etapa 1 do cliente provisório para o cliente
   canônico **sempre sobrescrevendo** `cliente.nome`, inclusive quando o canônico
   já possuía outro nome. Copiar também a profissão válida mais recente do
   provisório para `cliente.profissao` do canônico antes de excluir o provisório,
   sem reescrever `conversa.profissao`. Nome/username de perfil Meta nunca
   substitui esse nome;
6. se existir conversa canônica anterior ativa e diferente da atual, encerrá-la
   com `motivo_encerramento='ativou_privacidade'`; ela é preservada e não é
   retomada;
7. atualizar a conversa nova atual para usar o `id_cliente` canônico, mantendo o
   mesmo `id_conversa`, etapa, fila, histórico e respostas já ligadas a ela;
8. se, **no snapshot bloqueado antes das mutações**, a última conversa canônica
   anterior já estiver encerrada e ainda dentro de um bloqueio por dias,
   preservar integralmente `finalizou_em`, etapa e expiração daquela conversa e
   encerrar também a conversa nova com
   `motivo_encerramento='bloqueio_reconciliado'` e não reiniciar nem ampliar o
   prazo. `ativou_privacidade` não é usado neste caso: ele fica reservado ao
   encerramento de outra conversa canônica que ainda estava ativa. O item segue
   o tratamento de conversa bloqueada e não envia a etapa 3. A data de
   encerramento da conversa nova serve somente à auditoria; ela e sua etapa não
   entram no cálculo da expiração herdada. O item atual da fila é excluído na
   mesma transação da reconciliação. Depois do commit já existente após
   `validar_banco_mensagem()`, o worker apenas confirma no cache os aliases com a
   expiração original e encerra esse ciclo antes de histórico, lock normal,
   `bot_resposta_atual()`, resolver, sender e persistência final;
9. se não houver bloqueio vigente, manter a conversa nova ativa e continuar o
   fluxo normalmente;
10. consolidar `user_id_cliente` para ligar o user ID atual e a unidade ao cliente
    canônico: se ainda não houver linha canônica, reatribuir a linha provisória;
    se o canônico já tiver outro user ID na mesma unidade, remover primeiro a
    linha provisória comprovada e atualizar a linha canônica para o novo user ID;
11. preencher apenas `conversa.wa_id`/`conversa.user_id` que ainda forem `NULL`.
    Não alterar fila, histórico ou `conversa.username`;
12. preservar `cliente.username` como o último valor não vazio: o username não
    vazio do evento atual vence; na ausência dele, o username não vazio do
    provisório vence o valor canônico anterior; se ambos faltarem, manter o
    canônico. Essa cópia ocorre antes de excluir o provisório;
13. consolidar eventual `cliente_bloqueado_meta` do provisório na única linha
    canônica da unidade, preservando o bloqueio e ambos os aliases conhecidos;
    nunca desbloquear como efeito do merge;
14. excluir o cliente provisório somente depois de executar verificações
    explícitas de ausência de referência em `conversa`, `dependente`,
    `cliente_bloqueado_meta` e `user_id_cliente`; não basta confiar na ação da
    FK nem em uma verificação genérica não enumerada;
15. devolver o contexto normal da conversa nova somente quando ela não estiver
     bloqueada, para que o sender envie “Para quem é o atendimento?” pelo WA ID
     lido do banco. Se a conversa permanecer ativa, o passo normal posterior de
     `lock_conversa()` adquire uma nova versão antes do sender; se outro worker a
     adquirir primeiro, o requeue de lock recusado já existente prevalece. Se o
     bloqueio comercial ou Meta ainda estiver vigente, devolver o resultado
     terminal `bloqueio_reconciliado`, sem resposta da etapa 3.

No caminho normal, histórico e fila não trocam de `id_conversa`, portanto não
precisam ser movidos. No caminho terminal, somente o item atual da fila é
excluído; snapshots históricos já persistidos continuam intactos. Pelo fluxo
normal, o cliente provisório permanece na primeira conversa/etapa
especial até provar o WA ID, logo não deve possuir outra conversa. Se uma
referência extra impedir sua exclusão, a operação não usa cascata nem apaga dados;
o erro segue o tratamento transacional já existente.

O gate anterior é obrigatório porque `conversa.id_cliente` e
`dependente.id_cliente` possuem `ON DELETE CASCADE`, enquanto
`cliente_bloqueado_meta.id_cliente` possui `ON DELETE SET NULL`; a futura FK de
`user_id_cliente.id_cliente` será `ON DELETE RESTRICT`. Antes do `DELETE`, a
conversa atual já deve apontar ao cliente canônico, a linha provisória do vínculo
deve ter sido consolidada e cada uma dessas quatro consultas deve retornar zero.
Fila, histórico, respostas e itens de funil não entram nessa lista de FKs diretas
porque continuam ligados à conversa preservada e nunca são reparentados
individualmente. Qualquer resultado diferente de zero impede o `DELETE` e segue
o rollback/tratamento já existente, sem cascata.

Se a conversa canônica anterior estiver encerrada e liberada, ela permanece
intacta e a conversa nova continua. Se estiver bloqueada, vale o item 8: a
expiração original vence. Se um vínculo `(user_id, unidade)` apontar para cliente
com outro WA ID não nulo e incompatível, ou se WA e user ID resolverem clientes
canônicos distintos, não ocorre merge por username, nome ou aproximação. A
transação faz rollback e falha de forma fechada.

Quando um payload normal já trouxer WA ID + user ID, o contrato roda de forma
simplificada: depois do mesmo gate de consistência, resolve pelo WA ID,
cria/atualiza `user_id_cliente`, grava os snapshots do próprio evento somente no
momento de cada `INSERT` e preenche apenas aliases nulos permitidos da conversa.
Fila, histórico e username da conversa nunca sofrem backfill. Isso evita criar um
provisório numa volta futura somente por user ID sem falsificar registros antigos.

O repositório não usa `UPSERT` cego. Ele compara tanto o vínculo de
`(user_id, unidade)` quanto o de `(cliente, unidade)`. Se o mesmo cliente passou
a usar outro user ID e o WA ID conjunto prova o vínculo, o novo user ID passa a
ser o vínculo atual daquela unidade. Quando ele ainda aponta para o provisório e
já existe uma linha canônica com user ID antigo, a linha provisória é removida
antes da atualização da canônica; nunca se tenta apontar ambas ao mesmo
`(cliente, unidade)`. Se o novo user ID aponta para terceiro cliente com WA ID
diferente e não nulo, a transação falha sem fundir pessoas distintas.

## 5. Banco declarativo final

### 5.1 Nomes canônicos

A grafia correta é `id_portfolio`. A forma `id_portofolio` não será usada.

Estado final:

`chatbot.unidade`:

```sql
nome_unidade VARCHAR(300) NOT NULL
nome_agente VARCHAR(100) NOT NULL
genero VARCHAR(9) NOT NULL
suporte_idoso BOOLEAN NOT NULL DEFAULT FALSE
email_obrigatorio BOOLEAN NOT NULL DEFAULT TRUE
id_portfolio VARCHAR(100) NOT NULL

CONSTRAINT uq_unidade_nome_unidade
    UNIQUE (nome_unidade)
CONSTRAINT ck_unidade_nome_unidade_nao_vazio
    CHECK (nome_unidade ~ '[^[:space:]]')
CONSTRAINT ck_unidade_nome_agente_nao_vazio
    CHECK (nome_agente ~ '[^[:space:]]')
CONSTRAINT ck_unidade_genero
    CHECK (genero IN ('masculino', 'feminino'))
```

As três primeiras colunas e suas quatro constraints pertencem à baseline
versionada. As duas flags pertencem ao delta pré-`user_id` de 29/08/2026 e são
preservadas sem nova migração ou alteração de dados por este plano.
`id_portfolio` é a única ampliação futura da unidade pertencente à feature de
`user_id`; isso não significa que seja a única evolução já existente na tabela.

`chatbot.cliente`:

```sql
wa_id VARCHAR(50) NULL
username VARCHAR(255) NULL
profissao VARCHAR(100) NULL
```

`cliente` não recebe `user_id`: ele continua global. Os user IDs escopados
ficam exclusivamente na relação por unidade abaixo. `cliente.profissao` já
existe no estado pré-`user_id` após a aplicação de sua migração própria, não faz
parte das 22 alterações da feature e não deve ser adicionada novamente pela
migração de `user_id`.

`chatbot.user_id_cliente`:

```sql
id_user_id_cliente BIGSERIAL PRIMARY KEY
id_cliente INTEGER NOT NULL
user_id VARCHAR(255) NOT NULL
id_unidade INTEGER NOT NULL
```

Essa é a tabela canônica do vínculo privado. O nome `user_id_cliente` fica
fixado neste contrato para não haver variações durante a implementação. As
colunas de identidade presentes nas demais tabelas continuam como snapshots
operacionais e de auditoria.

`chatbot.fila_mensagens`:

```sql
wa_id VARCHAR(50) NULL
user_id VARCHAR(255) NULL
username VARCHAR(255) NULL
```

`chatbot.historico_mensagens`:

```sql
wa_id VARCHAR(50) NULL
user_id VARCHAR(255) NULL
username VARCHAR(255) NULL
```

`chatbot.conversa`:

```sql
wa_id VARCHAR(50) NULL
user_id VARCHAR(255) NULL
username VARCHAR(255) NULL
profissao VARCHAR(100) NULL
```

Em `conversa`, `profissao` é o snapshot imutável daquela conversa; o Funil lê
esse campo, não `cliente.profissao`.

`chatbot.cliente_bloqueado_meta`:

```sql
wa_id VARCHAR(50) NULL
user_id VARCHAR(255) NULL
username VARCHAR(255) NULL
```

`chatbot.webhook_flood_evento`:

```sql
wa_id VARCHAR(50) NULL
user_id VARCHAR(255) NULL
username VARCHAR(255) NULL
```

Contrato existente ampliado sem coluna nova:

```sql
chatbot.conversa.motivo_encerramento
    IN (
        'idade_invalida',
        'foi_agendado',
        'encaminhado_suporte_idoso',
        'ativou_privacidade',
        'bloqueio_reconciliado'
    )
```

O delta da feature de `user_id` soma 22 campos listados nesta seção, contando
chaves/FKs da tabela de vínculo e colunas renomeadas. As três colunas de
apresentação da unidade já existentes na baseline V1.0.7 e as profissões já
presentes no estado pré-`user_id` não entram nessa conta. Renome não cria uma
segunda cópia do WA ID legado.

Não existirão `telefone_informado`, `username_informado`,
`telefone_contato_compartilhado`, `wa_id_contato_compartilhado`,
`bsuid_cliente`, `username_whatsapp`, `cliente_telefone`, `waid_telefone` ou
`wa_id_cliente` no estado final.

Os campos existentes de WA ID serão **renomeados**, não duplicados:

- `cliente.waid_telefone -> cliente.wa_id`;
- `fila_mensagens.cliente_telefone -> fila_mensagens.wa_id`;
- `historico_mensagens.cliente_telefone -> historico_mensagens.wa_id`;
- `cliente_bloqueado_meta.wa_id_cliente -> cliente_bloqueado_meta.wa_id`;
- `webhook_flood_evento.wa_id_cliente -> webhook_flood_evento.wa_id`.

### 5.2 Nulabilidade e integridade

As colunas de snapshot são individualmente anuláveis. Isso não significa que
uma mensagem operacional possa ficar sem identidade. Fila, histórico, conversa,
bloqueio e flood exigem pelo menos um identificador técnico:

```sql
CHECK (
    NULLIF(BTRIM(wa_id), '') IS NOT NULL
    OR NULLIF(BTRIM(user_id), '') IS NOT NULL
)
```

Cada texto opcional também impede string vazia:

```sql
CHECK (campo IS NULL OR BTRIM(campo) <> '')
```

`cliente` é a exceção ao CHECK combinado: um cliente recém-criado apenas por
user ID pode possuir `wa_id = NULL` e `username = NULL`; o vínculo técnico fica
em `user_id_cliente` e a conversa guarda seu snapshot.

Também são exceções à nulabilidade:

- `unidade.nome_unidade` e `unidade.nome_agente` são obrigatórios, não vazios e
  `nome_unidade` permanece único;
- `unidade.genero` é obrigatório e aceita somente `masculino` ou `feminino`;
- `unidade.suporte_idoso` e `unidade.email_obrigatorio` são booleanos
  obrigatórios, com defaults `FALSE` e `TRUE`, respectivamente;
- `unidade.id_portfolio` é obrigatório e não vazio;
- `user_id_cliente.id_cliente`, `user_id` e `id_unidade` são obrigatórios;
- `user_id_cliente.user_id` não aceita string vazia.

`id_portfolio` recebe índice normal, não `UNIQUE`, pois o mesmo portfólio pode
administrar mais de uma unidade. O SQL de produção adiciona a coluna
temporariamente anulável, preenche um mapa explícito e validado de todas as
unidades e somente então aplica `NOT NULL`; nunca infere portfólio pelo WABA.

A tabela de vínculo impõe:

```sql
UNIQUE (user_id, id_unidade)
UNIQUE (id_cliente, id_unidade)
```

A primeira restrição impede dois clientes para a mesma identidade privada na
unidade. A segunda mantém um único user ID atual por cliente/unidade. Uma troca
só é aceita quando WA ID + user ID chegam juntos ou quando o
`contact_request` oficial prova o vínculo.

Essas unicidades modelam aliases, não uma chave composta obrigatória entre WA ID
e user ID. Nenhuma constraint exige que `cliente.wa_id` e uma linha
`user_id_cliente` coexistam. Isso preserva tanto o legado WA-only quanto o período
provisório user-only.

### 5.3 Índices

Não se indexa username. Os índices de identidade são mantidos por caminho para
que o resolvedor monte o conjunto comprovado e execute a consulta alias-aware
sem transformar os valores em uma concatenação:

- fila aberta por `(wa_id, id_phone_unidade, ...)`;
- fila aberta por `(user_id, id_phone_unidade, ...)`;
- conversa para auditoria/último atendimento por
  `(wa_id, id_unidade, finalizou_em DESC)` quando WA ID existe;
- conversa para auditoria/último atendimento por
  `(user_id, id_unidade, finalizou_em DESC)` quando user ID existe;
- bloqueio com a restrição `UNIQUE (wa_id, id_unidade)` existente; como o
  PostgreSQL permite múltiplos `NULL`, ela continua compatível com WA ID
  anulável;
- bloqueio parcial único por `(user_id, id_unidade)` quando user ID existe;
- bloqueio parcial único por `(id_cliente, id_unidade)` quando o cliente
  canônico já é conhecido, impedindo duas linhas da mesma pessoa/unidade depois
  da reconciliação;
- flood por `(wa_id, phone_id_unidade, received_at)`;
- flood por `(user_id, phone_id_unidade, received_at)`;
- vínculo canônico único por `(user_id, id_unidade)`;
- vínculo canônico único por `(id_cliente, id_unidade)`;
- apoio à FK/cascade de unidade por `(id_unidade, id_cliente)`;
- histórico mantém apenas seus índices cronológicos atuais; não será criado
  índice por identidade sem consulta operacional concreta que o justifique.

A saudação de retorno da seção 10.2 consulta o último histórico do bot pela
`id_conversa` exata e reutiliza o índice cronológico já existente. Ela não
autoriza índice, coluna, migração ou DDL adicional.

A fila continua usando `id_phone_unidade`. Não será adicionada uma coluna
redundante `id_unidade`. Toda consulta de turno/bloqueio exige
`id_phone_unidade`; `unidade_telefone`/`display_phone_number` não participa da
chave nem serve de fallback.

### 5.4 DDL e migração

Os arquivos Python de deploy conterão somente o estado final de criação. Não
haverá `ALTER TABLE` em Python.

O último passo do plano conterá um único SQL puro, transacional, para produção,
com:

1. preflight exato do estado bancário pré-`user_id` — baseline V1.0.7 com a
   migração de profissão já materializada, mais o delta de suporte ao idoso e
   política de e-mail —, complementado pelo manifesto de código que preserva a
   proteção contextual da oferta, inclusive `cliente.profissao VARCHAR(100) NULL`
   sem default, as três colunas
   de apresentação, `suporte_idoso BOOLEAN NOT NULL DEFAULT FALSE`,
   `email_obrigatorio BOOLEAN NOT NULL DEFAULT TRUE`, suas constraints e a
   ausência de `unidade.nome`;
2. serviços parados e filas operacionais vazias;
3. renome das cinco colunas existentes de WA ID;
4. preservação, sem renome, recriação, backfill ou novo `ADD COLUMN`, de
   `cliente.profissao`, `nome_unidade`, `nome_agente`, `genero`,
   `suporte_idoso` e `email_obrigatorio`;
5. criação das colunas novas e de `user_id_cliente`;
6. preenchimento explícito de `id_portfolio` para todas as unidades e aplicação
   de `NOT NULL`;
7. remoção de `NOT NULL` dos WA IDs de snapshot;
8. ampliação do CHECK já composto por `idade_invalida`, `foi_agendado` e
   `encaminhado_suporte_idoso` para incluir `ativou_privacidade` e
   `bloqueio_reconciliado`;
9. constraints, FKs e índices finais;
10. atualização preservada do catálogo/mapa de etapas;
11. recriação controlada de `chatbot.dequeue_message()` e preservação semântica
    de `chatbot.lock_conversa()`/`chatbot.unlock_conversa()`: a fila mantém sua
    recuperação própria de 2 minutos, enquanto a conversa conserva o predicado
    exato da V1.0.7, `processing_started_at < NOW() - INTERVAL '110.0 seconds'`,
    com `lock_version` no takeover e `unlock` condicionado à versão vigente;
12. pós-validação completa, incluindo apresentação da unidade, ações das FKs e
    definição dos índices;
13. `COMMIT` apenas depois de todas as validações.

A migração `deploy/migrations/20260812_personalizar_agente_unidade.sql` já
pertence à baseline e não será incorporada, repetida nem reexecutada pela
migração de `user_id`. O SQL futuro apenas prova que seu estado final continua
íntegro antes e depois da mudança.

A transação desse SQL pertence exclusivamente à futura janela de migração com
os serviços parados. Ela não move commits, rollbacks, ponto do lock ou política
de retry do `flow_worker`; preserva os dois limiares distintos da V1.0.7 — 2
minutos para recuperação da fila e 110 segundos para posse da conversa — e a
proteção de versão já exigida para o `unlock`.

Como `historico_mensagens` é particionada, a migração validará pai e partições.
Como a assinatura de retorno de `dequeue_message()` mudará, não será usado
`CREATE OR REPLACE` sobre a assinatura antiga: o SQL fará `DROP FUNCTION` e
recriará a função com o mesmo CTE, filtros, ordem, `FOR UPDATE SKIP LOCKED`,
posse, incremento de retry e timestamps, alterando somente nomes/colunas de
retorno.

Essa recriação é mecânica para transportar `wa_id`, `user_id` e username lidos
da fila. Ela não autoriza qualquer mudança no algoritmo transacional da função.

## 6. Webhook

### 6.1 Extração determinística

O parser não fará busca recursiva por qualquer chave chamada `phone`. Ele usará
somente caminhos semânticos conhecidos.

A cardinalidade externa continuará igual à do webhook atual: somente
`entry[0]`, `changes[0]`, `value.contacts[0]` e `messages[0]` participam do
evento processado. Este plano não amplia um POST para vários turnos nem altera a
unidade de idempotência. Dentro da mensagem `contacts` selecionada, porém, todos
os `messages[0].contacts[*].phones[*]` serão examinados apenas para decidir se
existe um único número inequívoco compartilhado pelo botão oficial.

Ordem do WA ID do remetente (`wa_id_remetente`):

1. `value.contacts[].wa_id`;
2. `value.messages[].from`.

Ordem do WA ID compartilhado (`wa_id_compartilhado`):

1. somente em `type="contacts"` com origem `contact_request`, aceitar
   `messages[].contacts[].phones[].wa_id` explícito;
2. exigir exatamente uma ocorrência, em texto ASCII com 10 a 15 dígitos;
3. ausência, valor inválido ou mais de uma ocorrência não produz candidato.

O parser mantém esses dois resultados separados. O WA ID compartilhado não
participa de `wa_id_remetente or user_id` usado pelos guardas do webhook, pelo
turno ou pela autocura. Ele é apenas o candidato transportado para a validação
bancária do handoff.

Ordem de user ID:

1. `value.contacts[].user_id`;
2. `value.messages[].from_user_id`.

Username:

1. `value.contacts[].profile.username`;
2. ausência é aceita e representada por `NULL`.

Regras:

- `contacts[0].wa_id` e `messages[0].from` devem coincidir quando ambos
  existirem;
- `contacts[0].user_id` e `messages[0].from_user_id` devem coincidir quando
  ambos existirem;
- divergência registra `CRITICAL`, retorna HTTP 200 e não cria fila;
- `metadata.display_phone_number` jamais participa da extração do cliente;
- `messages[].id` é WAMID, não WA ID;
- um `phones[].wa_id` explícito é preservado como `wa_id_compartilhado`
  exatamente, salvo remoção de
  espaços externos;
- nenhum dígito é acrescentado ou removido de um WA ID explícito.

`phones[].phone` é apenas apresentação do cartão e nunca prova o vínculo. Ele não
é normalizado nem usado como fallback. Assim, o fixture `CONTACT_INFO.json` usa
diretamente seu único `phones[].wa_id`; sem esse campo explícito, a etapa 2 não
promove, não reconcilia e apenas reapresenta o pedido oficial.

### 6.2 Mensagem `contacts`

O tipo bruto persistido na fila continuará sendo `contacts`. Não será inventado
um tipo substituto que apague a informação original.

Como webhook e worker são processos diferentes, a origem não pode existir
somente em memória. Sem criar outra coluna, a fila persistirá:

```text
tipo_mensagem = 'contacts'
conteudo_texto = 'contact_request'  # resposta oficial
conteudo_texto = 'other'            # contato/vCard manual
```

Esse marcador normalizado distingue:

- `contact_request`: resposta ao botão oficial;
- `other`/ausente: contato ou vCard enviado manualmente.

Para tolerar as duas formas de normalização observáveis sem fazer busca
recursiva, a origem será lida exclusivamente de um destes pontos semânticos:

1. `messages[0].origin`, quando a biblioteca expuser a origem no nível da
   mensagem;
2. `messages[0].contacts[*].origin`, como ocorre no fixture
   `payloads/CONTACT_INFO.json`.

O parser reúne as origens não vazias desses dois caminhos. O marcador somente é
`contact_request` quando o conjunto resultante é exatamente
`{'contact_request'}`. Origem desconhecida, ausente ou conflitante não recebe
privilégio e é persistida como `other`.

Somente `tipo_mensagem='contacts'` com
`conteudo_texto='contact_request'`, durante a etapa especial, pode fornecer o
WA ID e avançar. Um contato manual continua recebendo tratamento de
contexto/mídia. O conteúdo de um contato não é texto livre do cliente, portanto
usar esse marcador em `conteudo_texto` não apaga uma resposta textual.

O payload pode conter vários contatos e telefones. Para a etapa especial, o
evento válido deve identificar inequivocamente o contato solicitado. Se a
origem estiver no nível da mensagem, todos os contatos pertencem à resposta
oficial; se estiver no contato, somente os contatos cujo `origin` seja
`contact_request` fornecem candidatos.

O parser coleta apenas ocorrências explícitas de `wa_id_compartilhado` nesses
contatos oficiais: exatamente uma ocorrência ASCII com 10 a 15 dígitos avança;
ausência, formato inválido ou mais de uma ocorrência recebe tratamento de
contexto. `phones[].phone` é exclusivamente apresentação do cartão e nunca é
normalizado nem usado como fallback. Não se escolhe silenciosamente o primeiro
número.

### 6.3 Ordem das proteções

A ordem atual será preservada. O webhook passa a extrair `user_id` e username
junto dos campos que já normaliza e o anti-flood passa a resolver aliases
oficialmente vinculados antes de contabilizar a janela:

1. validação de content type, tamanho, assinatura e estrutura JSON;
2. classificação do evento, extração dos identificadores e exigência de
   `metadata.phone_number_id`;
3. denylist/bloqueio alias-aware e tentativa de bloqueio na Meta;
4. deduplicação e flood por WAMID;
5. validação da unidade ativa;
6. bloqueio temporário da conversa;
7. regra de turno e inserção idempotente na mesma transação de fila;
8. resposta HTTP e tratamento atual das exceções.

O limite de 15 WAMIDs distintos em 5 segundos, o efeito do bloqueio e a posição
relativa desses guardas não mudam. São acrescentados somente TTLs auxiliares da
resolução de aliases — vínculo confirmado em cache por 1 hora e ausência de
vínculo por 5 segundos — e o retorno HTTP 503 fail-safe quando o RDS não puder
decidir o vínculo ou quando outra falha transitória impedir a persistência. Uma
falha isolada do Redis depois de o RDS provar a ausência do vínculo não rejeita
o evento: ele continua como identidade unitária pelo fallback atual. Antes
de promover qualquer contato compartilhado, o webhook escolhe uma única
identidade técnica para o evento pela mesma regra reconstruída no worker:

```python
if tipo_mensagem == "contacts" and origem == "contact_request" and user_id:
    tipo_identidade_do_item = "user_id"
    identidade_do_item = user_id
elif wa_id_remetente:
    tipo_identidade_do_item = "wa_id"
    identidade_do_item = wa_id_remetente
else:
    tipo_identidade_do_item = "user_id"
    identidade_do_item = user_id
```

Em eventos normais, WA ID do remetente continua prioritário. A única exceção é o
`contact_request` oficial que também possui user ID: esse item mantém user ID
como identidade congelada, mesmo se um formato futuro trouxer excepcionalmente
WA ID no envelope. Isso impede que o WA ID do cartão ou do envelope troque a
chave do handoff; depois da validação, o WA ID canônico ainda vence como
destinatário. Um formato real diferente exige fixture e revisão deste contrato,
nunca mudança silenciosa.

Fora dessa exceção, se WA ID do remetente faltar, user ID ocupa seu lugar no
transporte inbound. Isso também vale se a Meta continuar entregando somente user
ID depois da etapa 2: o webhook não conhece nem decide a etapa antes de
enfileirar. A limitação às etapas iniciais vale para o avanço de negócio e para o
fallback de destinatário, não para aceitar e proteger o envelope recebido. Não
se executam duas avaliações ou incrementos independentes para a mesma mensagem;
quando o sujeito possui dois aliases, os advisory locks necessários são
adquiridos como um único protocolo, em ordem determinística. Username nunca
participa da identidade técnica.

No anti-flood, a janela pertence ao sujeito lógico comprovado dentro do mesmo
`phone_id_unidade`. Antes da prova, user ID e WA ID permanecem separados. Depois
da associação oficial, os eventos ainda válidos das duas identidades são
somados, o WA ID torna-se a referência canônica e a troca de identificador não
reinicia a métrica.

Existe uma única prova operacional para unir aliases fora da transação que está
validando o próprio item: o vínculo persistido em `chatbot.user_id_cliente`,
ligado ao cliente canônico com WA ID na mesma unidade. O envelope conjunto e o
`contact_request` fornecem candidatos à prova, mas não autorizam o webhook a
publicar uma ponte de identidade antes do gate bancário completo. Até o commit do
worker, flood e denylist tratam o item pelo alias congelado com que ele entrou.

Depois de validar o par e antes de qualquer mutação, o worker executa uma segunda
barreira de predecessor sobre os snapshots WA/user da mesma unidade. Se existir
item anterior `pending` ou `processing` em qualquer alias, o item de prova sofre
rollback e requeue de 5 segundos sem consumir retry. Essa barreira fecha a janela
anterior ao vínculo sem conceder ao webhook autoridade de etapa ou reconciliação.
Após o commit, o vínculo persistido passa a unir os aliases no anti-flood, turno,
ordem, bloqueios e denylist.

Redis e memória somam os contadores das duas identidades sem duplicar eventos. O
fallback SQL usa `COUNT(DISTINCT id_hash_msg)` sobre WA ID e user ID associados.
O WAMID é deduplicado por unidade, de modo que uma reentrega ou o mesmo evento
visto pelos dois aliases conta uma única vez. Limite, janela e efeito de bloqueio
permanecem 15 WAMIDs distintos em 5 segundos.

Ausência de vínculo pode receber cache negativo de 5 segundos para evitar uma
consulta ao RDS por evento. Se o RDS responder autoritativamente que não existe
vínculo, falha do Redis conserva o alias unitário e deixa o anti-flood seguir seu
fallback banco -> memória da V1.0.7; o cache negativo e sua releitura são apenas
otimizações. Conflito determinístico é descartado com HTTP 200, sem mutação ou
bloqueio Meta. HTTP 503 fica reservado à indisponibilidade transitória do RDS ou
de outra fonte indispensável à decisão. Contato manual, username, nome,
coincidência temporal ou semelhança de valores nunca unem identidades.

O clique no botão gera uma nova mensagem inbound com WAMID e timestamp próprios.
Ela passa por deduplicação, flood, turno e fila como qualquer outra mensagem.

### 6.4 Turno, aliases e identidade do item

Cada item conserva uma identidade primária tipada e imutável. A reconstrução usa
somente os campos persistidos no `INSERT` e não cria coluna adicional:

```python
if (
    tipo_mensagem == "contacts"
    and conteudo_texto == "contact_request"
    and user_id_item_fila
):
    tipo_identidade_do_item = "user_id"
    identidade_do_item = user_id_item_fila
elif wa_id_item_fila:
    tipo_identidade_do_item = "wa_id"
    identidade_do_item = wa_id_item_fila
else:
    tipo_identidade_do_item = "user_id"
    identidade_do_item = user_id_item_fila

chave_turno = (
    tipo_identidade_do_item,
    identidade_do_item,
    id_phone_unidade,
)
```

`chave_turno` acima é a referência primária do item para logs, cache, retry e
autocura; ela não vira `wa_id+user_id`. Para exclusão mútua e ordem, o repositório
resolve adicionalmente `aliases_turno`:

```text
sem prova: { (tipo_identidade_do_item, identidade_do_item) }
com prova: aliases existentes de (id_cliente, id_unidade)
```

Cliente legacy WA-only e provisório user-only possuem conjunto unitário. Cliente
com vínculo comprovado pode possuir os dois aliases. O webhook adquire
`pg_advisory_xact_lock` para cada par tipado do conjunto, sempre ordenado por
`(tipo, valor)`, e executa **uma** decisão de turno que consulta as filas abertas
por qualquer alias com o mesmo `id_phone_unidade`. Assim, requisições simultâneas
que entram uma por WA e outra por user ID convergem para os mesmos locks; não há
duas decisões nem duas cotas.

A ordem no worker usa o mesmo conjunto comprovado e os filtros atuais de status,
data e desempate. A consulta pode conter os dois predicados, mas produz uma única
resposta. O alias primário do item continua congelado, inclusive no
`contact_request`; antes do primeiro commit, o WA ID candidato participa somente
da segunda barreira transacional de predecessor e não se torna destinatário,
vínculo, identidade de flood/denylist ou chave de cache prematuramente.

O tipo permanece no namespace lógico: strings iguais sem prova não colidem.
Falha ao resolver uma equivalência compartilhada não reduz silenciosamente o
conjunto para um alias: retorna 503 para reentrega antes da inserção.

### 6.5 Persistência na fila

Cada item recebe snapshots de criação:

```python
{
    "wa_id": wa_id,
    "user_id": user_id,
    "username": username,
}
```

Ao menos `wa_id` ou `user_id` deve existir. Username ausente não causa erro.
Depois do `INSERT`, `wa_id`, `user_id` e username dessa linha são imutáveis; retry
e reconciliação não os enriquecem nem corrigem retroativamente.

No `contact_request` representado pelos fixtures, `fila_mensagens.wa_id` pode
transportar o candidato compartilhado sem criar `wa_id_compartilhado` físico. A
combinação persistida `tipo_mensagem='contacts'`,
`conteudo_texto='contact_request'` e `user_id` obriga a reconstrução da
`identidade_do_item` pelo user ID. A validação bancária é que promove esse mesmo
valor candidato a WA ID comprovado; até lá, nenhuma lógica de turno, cache,
bloqueio ou autocura pode tratá-lo como identidade canônica.

O histórico do cliente copia os snapshots imutáveis da fila. O histórico do bot
grava, no próprio `INSERT`, os valores canônicos então presentes no contexto;
nenhum dos dois é atualizado depois. Essa política garante que um retry
reconstrua o mesmo item mesmo após a associação dos aliases.

Quando houver saudação de retorno, o histórico do bot continua recebendo uma
única linha com o texto final já prefixado. Não existe linha separada para a
saudação, e o histórico anterior nunca é reescrito para produzi-la.

## 7. `flow_worker`: núcleo congelado e reconciliação delimitada

### 7.1 Sequência congelada

A sequência abaixo permanece exatamente no mesmo lugar no caminho normal:

1. `dequeue_message()` e commit atual;
2. `reagendar_se_houver_mensagem_anterior()` imediatamente após o dequeue;
3. `validar_banco_mensagem()` e commit atual;
4. confirmação/reparo de cache;
5. tratamento de bloqueio;
6. `chatbot.lock_conversa()` e commit atual;
7. vínculo fila -> conversa;
8. `valida_historico()` e commit atual;
9. `bot_resposta_atual()` antes do resolver/sender;
10. `flow_sender()`;
11. `atualizar_banco_com_contexto_final()` e commit atual;
12. marcação `sent` no ponto atual;
13. mesmos rollbacks, retries e autocura.

A saudação da seção 10.2 não insere passo transacional nessa sequência. No
caminho ainda sem resposta registrada para a mensagem atual, sua consulta
auxiliar ocorre depois da barreira idempotente do passo 9 e antes da única
chamada de sender do passo 10. Se o passo 9 encontrar resposta existente, o
ciclo sai pelo comportamento atual sem consultar, compor ou reenviar a
saudação.

No passo 2, encontrar predecessor sempre interrompe o ciclo atual. O retorno de
`reagendar_mensagem_sem_erro()` diferente de uma linha continua gerando o alerta
de corrida `mensagem_ordem_nao_reagendada`; ele não autoriza ultrapassar a
mensagem anterior e não muda o `return True` da V1.0.7.

Durante o passo 3, a reconciliação pode devolver dois resultados controlados:

1. `conversa_em_processamento`, antes de qualquer mutação, quando uma das
   conversas envolvidas tiver lock fresco. O ciclo faz rollback, usa o requeue
   sem erro de 5 segundos, compensa o incremento de retry e segue para o próximo
   item. Isso não antecipa o lock normal do passo 6 e não permite ao merge limpar
   a posse de outro worker;
2. `bloqueio_reconciliado`, depois de validar e consolidar a identidade quando
   existir bloqueio comercial ou Meta ainda vigente. A mesma transação já fecha
   a conversa nova e exclui sua fila atual. O commit normal imediatamente após a
   validação confirma esses efeitos; em seguida o worker confirma no cache os
   aliases do bloqueio — usando a expiração original e o TTL restante quando se
   tratar dos 30 dias — e usa `continue`, sem executar os passos normais 4 a 13,
   sem criar histórico e sem chamar lock, `bot_resposta_atual()`, resolver ou
   sender.

Se houver stale takeover dentro da reconciliação, as linhas são mantidas sob
row lock, `processing` é limpo e `lock_version` é incrementado. A conversa nova
que permanecer ativa ainda precisa adquirir uma versão no `lock_conversa()`
normal do passo 6. Isso preserva o ponto arquitetural do lock e impede que o
merge contorne a disputa normal com outro item.

Também permanecem:

- requeue sem erro de 30 segundos para mensagem anterior;
- requeue sem erro de 5 segundos quando lock é recusado;
- requeue sem erro de 300 segundos para vínculo fila/conversa inconsistente;
- retry genérico de 2 minutos;
- limite atual de tentativas;
- espera atual de 1,5 segundo quando a fila está vazia;
- toda a verdade lógica de `tests/unit/test_fluxo_turno_abc.py`.

A janela de posse da conversa permanece exatamente a da V1.0.7 e não deve ser
confundida com os 2 minutos de recuperação da fila. O takeover da conversa só é
permitido quando `processing_started_at < NOW() - INTERVAL '110.0 seconds'`;
enquanto esse predicado não for verdadeiro, o lock é fresco e recusado. A
retomada incrementa `lock_version`. O contrato já existente de posse é mantido:
`unlock_conversa()`
só libera `processing` quando recebe a versão vigente. Incrementar a versão no
takeover impede que um `unlock` tardio com o token anterior solte a posse nova.
Este plano não condiciona retroativamente cada escrita pós-lock ao token e não
afirma que consiga cancelar uma chamada Meta já iniciada.

Se um worker ultrapassar a janela e outro adquirir a versão seguinte, a versão
mais nova vence. Uma chamada externa que já tenha sido confirmada pela Meta antes
da perda de posse continua dentro da rara janela Meta -> banco já documentada;
o plano não afirma que um efeito externo em andamento possa ser cancelado.

Fora dos dois resultados controlados descritos acima, o item de handoff passa
pelo mesmo passo 2 com a identidade pela qual foi enfileirado e segue para a
mesma validação, lock, histórico, sender e persistência dos demais itens. Não se
adiciona outra política de retorno, `continue` ou reagendamento específica desta
feature.

### 7.2 Transporte de contexto

Os três valores de identidade (`wa_id`, `user_id` e username) percorrem a cadeia
existente, sem criar uma etapa nova no worker:

```text
fila -> validar_banco_mensagem() -> contexto_banco
     -> valida_historico() -> contexto_historico
     -> flow_sender() -> resolver -> sender -> contexto_envio
     -> flow_sender() enriquece e devolve
```

O item da fila é um snapshot de entrada. Para o sender, porém, a fonte
autoritativa é o banco: `validar_banco_mensagem()` resolve o cliente, a conversa
e `user_id_cliente`; `valida_historico()` copia os valores resolvidos para o
`contexto_historico`.

Ao final da resolução — inclusive depois de criar vínculo ou reconciliar
cliente — `validar_banco_mensagem()` faz uma projeção final obrigatória pelo
`id_cliente`, `id_unidade` e `id_conversa` definitivos. Essa leitura retorna as
três chaves, ainda que o valor de alguma delas seja `None`:

- `wa_id`: `cliente.wa_id` do cliente canônico final;
- `user_id`: `user_id_cliente.user_id` do mesmo cliente na unidade atual;
- `username`: `conversa.username`, snapshot da conversa atual.

`cliente.username` continua sendo o valor global mais recente para cadastro e
Admin, mas não substitui silenciosamente o snapshot da conversa no contexto nem
no histórico do bot.

Em paralelo e sem integrar esse trio de identidade, a baseline V1.0.7 conserva
o contexto editorial da etapa 1. Quando `id_etapa_atual is None`, e somente
nesse primeiro contato, `valida_historico()` chama
`core/repositories/fluxo/contextos/etapa1.py` e acrescenta ao
`contexto_historico`:

- `nome_unidade`;
- `nome_agente`;
- `genero`.

Esses valores são lidos pelo `id_unidade`, validados de forma fechada e usados
apenas pelo resolver/sender para a apresentação inicial. Eles não são snapshots
de identidade, não entram em `estado_ciclo`, não alteram a projeção bancária
final e não são usados para escolher `wa_id` ou `user_id`.

Outros contextos pré-existentes também permanecem separados da identidade. A
futura etapa 7 relê `suporte_idoso`, número comercial e destino do atendimento;
a futura etapa 11 relê `email_obrigatorio`, destino e idade do titular. Essas
leituras acontecem no mesmo cursor do ciclo, são validadas de forma fechada e
não entram no `estado_ciclo`, no resolvedor de aliases nem na escolha do
destinatário. A saudação de retorno continua sendo calculada por conversa antes
do resolver, sem substituir esses snapshots de política.

```python
identidades_banco = buscar_identidades_para_contexto(
    id_cliente=id_cliente_final,
    id_unidade=id_unidade,
    id_conversa=id_conversa_final,
    cursor=cursor,
)

contexto_banco.update(
    {
        "wa_id": identidades_banco["wa_id"],
        "user_id": identidades_banco["user_id"],
        "username": identidades_banco["username"],
    }
)
```

O `estado_ciclo` passa a transportar, como campos aditivos:

- `tipo_identidade_do_item` e `identidade_do_item`, reconstruídos imediatamente
  após o dequeue e imutáveis até a finalização daquele item;
- `wa_id_compartilhado`, somente quando o marcador persistido provar que o
  snapshot de WA veio do cartão oficial;
- `wa_id_canonico`, preenchido apenas depois da projeção bancária final;
- `id_phone_unidade`;
- `referencia_cache_cliente`, a única chave tipada admissível para resolver o
  cliente daquele item.

Turno, logs, finalização da fila, retry e autocura usam
`identidade_do_item`. A seleção do destinatário usa somente `wa_id`, `user_id` e
username provenientes do `contexto_banco`. Nenhum desses campos é recalculado a
partir do outro no meio do ciclo.

O cache de cliente não pode reutilizar a chave global atual de WA ID para um
user ID. O namespace lógico preserva a chave WA existente e acrescenta uma chave
escopada para user ID:

```text
WA ID:   cliente_cache:{wa_id}
user ID: cliente_cache:user:{id_phone_unidade}:{user_id}
```

A chave WA continua global. A chave de user ID sempre inclui a unidade e o tipo;
uma mesma string vista como WA ID e como user ID não colide. Os fallbacks em
memória seguem a mesma separação. TTL, precedência Redis -> banco, tolerância a
falha e quantidade de tentativas permanecem os atuais.

Um helper puro monta `referencia_cache_cliente` a partir de
`tipo_identidade_do_item`, `identidade_do_item` e `id_phone_unidade` ainda em
`montar_mensagem_fila()`. `atualizar_estado_com_mensagem()` a copia antes de
`validar_banco_mensagem()`, e a validação usa exatamente essa mesma referência.
Assim, se a validação falhar antes de devolver `contexto_banco`, a autocura ainda
conhece a chave correta. O reparo de FK stale remove somente essa referência; ele
não recalcula uma chave a partir do WA ID compartilhado ou do WA ID canônico e
não pode apagar a chave de outra unidade. No handoff, a confirmação de cache que
já ocorre depois do commit atual passa a apontar a chave de user ID usada para o
`id_cliente` canônico. Não há escrita antes do commit, ponto adicional de
confirmação, commit, retry, requeue ou ramo de autocura novo.

Um hit de cache pode ajudar a localizar o `id_cliente`, mas não substitui essa
projeção final. Se o banco não devolver o contrato completo, a validação falha;
não existe fallback silencioso para os campos brutos da fila ou do payload.

Contrato aditivo de entrada de `flow_sender()` e dos resolvers:

```python
contexto_historico.update(
    {
        "wa_id": contexto_banco["wa_id"],
        "user_id": contexto_banco["user_id"],
        "username": contexto_banco["username"],
    }
)
```

Além dos três snapshots canônicos, `valida_historico()` expõe no topo do
contexto um campo lógico separado para o validador da etapa 2:

```python
eh_contact_request = (
    mensagem_cliente_atual["tipo_mensagem"] == "contacts"
    and mensagem_cliente_atual["conteudo_texto"] == "contact_request"
)

contexto_historico["wa_id_compartilhado"] = (
    mensagem_cliente_atual.get("wa_id")
    if eh_contact_request
    else None
)
```

Esse valor vem do snapshot normalizado do item e serve somente para o validador
reconhecer a prova oficial. `contexto_historico["wa_id"]` continua sendo o WA ID
canônico relido do banco. É proibido usar o canônico como prova de que o payload
era `contact_request`, assim como é proibido usar `wa_id_compartilhado` como
destinatário. O `contexto_envio` continua refletindo apenas `wa_id`, `user_id` e
username canônicos/snapshots; não transporta o candidato como quarto campo.

`flow_sender(contexto_historico)` e os resolvers não leem novamente o banco e
não usam diretamente os identificadores brutos do payload. Uma única função
central resolve o destinatário:

```python
def resolver_destinatario_sender(
    contexto_historico,
    *,
    permitir_user_id=False,
):
    wa_id = contexto_historico.get("wa_id")
    user_id = contexto_historico.get("user_id")
    id_etapa_atual = contexto_historico.get("id_etapa_atual")

    if wa_id:
        return wa_id

    if permitir_user_id and id_etapa_atual in (None, 1, 2) and user_id:
        return user_id

    raise ValueError("Sender sem WA ID fora das etapas iniciais")
```

O `contexto_envio` devolvido em envio novo ou no caminho idempotente mantém o
contrato técnico já existente e apenas reflete os snapshots que chegaram no
`contexto_historico`:

```python
contexto_envio.update(
    {
        "wa_id": contexto_historico.get("wa_id"),
        "user_id": contexto_historico.get("user_id"),
        "username": contexto_historico.get("username"),
    }
)
```

Essa anexação pertence à fronteira de `flow_sender()`, não a um sender de etapa.
No ramo em que `resposta_bot_para_mensagem_atual` já existe, ela é executada
antes do retorno antecipado. Nos demais ramos, é executada sobre o resultado do
resolver antes de `flow_sender()` devolvê-lo. Assim nenhum caminho retorna um
formato parcial.

Esses campos não comandam commit ou transição. Eles acompanham o resultado para
a persistência existente e garantem o mesmo formato nos envios novos, nos
tratamentos e no retorno idempotente de resposta já registrada.

Regras finais:

- ausência no evento não apaga valor conhecido;
- WA ID lido do banco sempre vence user ID para o sender;
- user ID só pode ser destinatário quando o resolver da etapa habilita
  explicitamente `permitir_user_id=True`, a conversa está em `None/1/2` e não há
  WA ID;
- a resposta válida `contato_oficial_compartilhado`, embora parta da etapa 2,
  chama o helper com o padrão `False` e exige WA ID;
- username só é transportado e persistido; nunca entra em `to`;
- retry reconstrói os valores do banco;
- sender e resolver não executam SQL;
- o transporte de contexto não cria commit, lock, retorno de ciclo, exceção de
  retry ou política de retry; a contenção do merge e a terminação por bloqueio
  reconciliado são as duas exceções controladas, definidas fora do sender na
  seção 7.1;
- `dequeue_message()` apenas amplia/renomeia os dados retornados;
- CTE, `ORDER BY`, `FOR UPDATE SKIP LOCKED`, posse, retry e timestamps permanecem
  semanticamente idênticos; a fila conserva sua fronteira stale própria de 2
  minutos, sem reutilizá-la como limiar do lock da conversa.

### 7.3 Resolução e reconciliação dentro da validação existente

`validar_banco_mensagem()` passa a resolver na seguinte ordem:

1. exigir `id_phone_unidade`, localizar por ele a unidade e nunca usar
   `unidade_telefone`/`display_phone_number` como fallback;
2. se houver user ID, consultar `(user_id, id_unidade)`;
3. em evento de handoff, usar primeiro esse vínculo para reencontrar a conversa
   provisória; somente depois consultar o cliente canônico pelo WA ID;
4. em payload normal com WA ID, resolver/criar o cliente global pelo WA ID e
   registrar imediatamente o user ID que chegou junto;
5. em primeiro evento somente-user-ID sem vínculo, criar cliente provisório,
   vínculo e conversa na mesma transação;
6. em retorno somente-user-ID já mapeado, reutilizar o cliente e a conversa
   canônicos; se o cliente já possuir WA ID, acumulá-lo e não abrir a etapa 2;
7. em qualquer associação WA + user, validar o conjunto completo e falhar de
   forma fechada se os aliases apontarem para clientes canônicos incompatíveis;
8. em merge, aplicar o protocolo de posse, versão, nome e bloqueio da seção 4.5;
9. devolver ao restante do ciclo o `id_cliente` e `id_conversa` finais.

As restrições de unicidade de `(user_id, id_unidade)` e
`(id_cliente, id_unidade)` continuam sendo a proteção de integridade. Violação ou
contradição nunca cai para um alias isolado. Contenção por lock fresco retorna o
resultado controlado de requeue sem erro; demais conflitos seguem rollback e
reentrega. O nome capturado continua atualizado por `id_cliente`; durante merge,
o valor do provisório sempre sobrescreve o canônico antes da exclusão.

Quando WA ID e user ID provarem que o cliente provisório corresponde a cliente
antigo, aplica-se exatamente a seção 4.5. O commit já existente depois de
`validar_banco_mensagem()` confirma os efeitos; o rollback e o retry atuais
continuam responsáveis por falhas. A contenção por lock fresco e a terminação
por bloqueio reconciliado são os dois resultados controlados da seção 7.1.

O banco é a fonte da verdade do vínculo e dos identificadores passados aos
contextos. Esta reconciliação não consulta nem modifica `funil_envios`. No
caminho normal, não remove fila antecipadamente. No caminho terminal, ela fecha
a conversa nova e exclui somente o item atual da fila na mesma transação, para
que ele não seja retomado após o commit. Ela consulta bloqueio/conversa anterior
apenas para preservar a expiração canônica e consolida a linha de bloqueio Meta
quando necessário para excluir o provisório sem perder proteção. Uma conversa
nova fechada por bloqueio vigente não alcança histórico, lock normal,
`bot_resposta_atual()`, resolver ou sender.

### 7.4 Persistência dos snapshots

- fila: snapshot normalizado/resolvido pelo webhook antes de existir conversa;
  todos os seus identificadores permanecem imutáveis após o `INSERT`;
- histórico do cliente: cópia imutável do snapshot do item da fila;
- histórico do bot: snapshot imutável gravado no próprio `INSERT`, refletindo o
  `contexto_envio` daquele instante;
- conversa: pode preencher `user_id`/`wa_id` nulos após prova oficial, mas o
  `UPDATE` é condicionado à existência de um valor novo para uma coluna ainda
  nula; quando ambos já estão preenchidos, o caminho é no-op e não adquire row
  lock desnecessário. `username` é exclusivamente o valor recebido na criação;
  não há preenchimento posterior nem sobrescrita;
- cliente: atualiza `wa_id` quando ocorre promoção válida e atualiza username
  sempre que a Meta trouxer um valor novo não vazio; no merge, o evento atual
  não vazio vence, senão o username não vazio do provisório vence o canônico
  anterior. O nome capturado do provisório sempre sobrescreve o nome canônico;
- `user_id_cliente`: relação canônica atual do cliente naquela unidade;
- resolver: recebe os valores pelo `contexto_historico`, escolhe o destinatário
  pelo helper e passa somente o escalar ao sender;
- sender: não persiste nem consulta identificadores; devolve seu contexto técnico
  normal, que `flow_sender()` enriquece com os snapshots no `contexto_envio`;
- prova oficial nunca executa backfill em fila ou histórico;
- valores de fila/histórico e `conversa.username` nunca são sobrescritos;
- flood continua sendo snapshot do evento e não sofre backfill, pois não possui
  `id_conversa`;
- conflito realmente contraditório entre dois clientes com WA IDs não nulos e
  diferentes nunca é resolvido por username ou aproximação.

### 7.5 Fronteiras arquiteturais e donos da persistência

A implementação da nova etapa e a renumeração preservam as responsabilidades
atuais:

- `core/integrations/whatsapp/messages/etapaN_messages.py` contém somente
  constantes, textos e builders puros. Não chama Meta, não valida resposta, não
  conhece evento/destino e não acessa banco;
- `core/integrations/whatsapp/pywa_functions/pywa_senders/etapaN.py` chama o
  builder da etapa, realiza somente o I/O da Meta e monta o `contexto_envio` no
  formato já existente. Recebe o destinatário escalar e os parâmetros técnicos;
  não recebe responsabilidade de validar conteúdo, escolher evento/transição ou
  executar SQL/commit;
- `workers/worker_flow/response_flow/etapas/validadores_contexto/valida_etapaN.py`
  classifica o contexto normalizado e devolve resultado/valor. Não envia, não
  consulta banco e não escolhe destino;
- `core/validacoes/email.py` concentra a gramática pura reutilizada pela futura
  etapa 11, pelo replay e pelo Funil; o wrapper contextual conserva a API da
  etapa, sem duplicar regex ou expressões de ausência;
- `core/integrations/whatsapp/numero_comercial.py` concentra a normalização e o
  link do contato comercial usados pelo Admin e pelo sender da futura etapa 7;
- `resolver_etapaN.py` mantém a prioridade dos validadores, produz no máximo um
  evento, chama `resolver_destino_transicao()`, resolve o destinatário por meio
  do helper puro, chama o sender adequado e usa
  `anexar_transicao_ao_contexto_envio()`. Tratamentos não carregam evento e o
  resolver não faz SQL/commit;
- `flow_sender.py` conserva a barreira idempotente e apenas roteia pela etapa
  persistida: `None/1 -> resolver 1`, `2 -> resolver 2`, até `22 -> resolver 22`.
  A etapa 23 é terminal e não possui resolver. `flow_sender()` acrescenta os
  três snapshots antes de todo retorno, inclusive o idempotente. Ele também
  preserva a reconstrução idempotente já existente da confirmação do destino:
  ao recuperar uma resposta do bot, o evento único identifica a transição e o
  `status_dependente` booleano, já persistido na mesma transação da resposta,
  repõe o `status_dependente_final` absoluto sem reaplicar uma inversão. Valor
  ausente ou não booleano é inconsistência e falha de forma fechada; nunca é
  convertido silenciosamente para titular. Fora esse contrato existente, ele
  não valida conteúdo, executa SQL nem chama a Meta diretamente;
- `transicoes/eventos.py` e `chatbot.etapa_transicao` definem nomes e arestas,
  sem conter efeitos de dados;
- `persistencia_resposta.py` e `efeitos_transicao.py` continuam sendo os donos
  dos efeitos finais de negócio na transação já existente. O encaminhamento de
  suporte persiste a idade antes do encerramento terminal, e a coleta de e-mail
  grava endereço ou `NULL` segundo a classificação transportada/reconstruída.

O resolver, por conhecer a etapa e o evento que está sendo tratado, é o chamador
de `resolver_destinatario_sender()`. Ele passa somente o escalar retornado ao
sender PyWa. Assim, nenhum sender recebe o dicionário completo para decidir por
conta própria se user ID é permitido.

A divisão transacional fica fixada desta forma:

1. `validar_banco_mensagem()` resolve, promove e, quando comprovado, reconcilia a
   identidade necessária antes do sender, usando o cursor, a transação e o
   commit que já existem depois da validação. Não escolhe evento, não movimenta
   etapa nem registra resposta do bot. O nome da mensagem atual continua sendo
   efeito da transição; a única cópia de nome feita aqui é o valor já persistido
   no provisório que, durante o merge, sobrescreve o canônico;
2. após o lock normal da conversa, resolver e sender produzem
   `contexto_envio` sem SQL; a posse continua representada pelo
   `lock_version` devolvido por `lock_conversa()` e usada pelo `unlock` atual;
3. `atualizar_banco_com_contexto_final()` mantém internamente a ordem atual:
   registrar/recuperar histórico do bot -> `persistir_movimento_conversa()` ->
   turnos sem avanço -> `atualizar_banco_conforme_transicao_de_etapa()` ->
   `resolver_intencao_encerramento()`;
4. o commit final permanece no ponto atual do `flow_worker`.

A reconciliação de identidade não é movida para `efeitos_transicao.py`, porque o
sender da etapa 3 precisa do WA ID canônico antes do envio. Ela também não é
duplicada: `atualizar_banco_conforme_transicao_de_etapa()` reconhece a aresta e
aplica somente os efeitos finais próprios da transição. Uma falha continua
seguindo o rollback/retry da transação correspondente. As únicas políticas novas
são a contenção sem erro quando o merge encontra lock fresco e o encerramento
terminal quando ele comprova bloqueio vigente, definidos na seção 7.1.

## 8. Etapa especial obrigatória

### 8.1 Gatilho

Depois que o cliente responde o nome na etapa 1:

- se o contexto acumulado já possui WA ID, inclusive resolvido por
  `user_id_cliente`, pula a etapa especial e segue para
  “Para quem é o atendimento?”;
- se possui apenas user ID, entra obrigatoriamente na etapa especial;
- username não interfere na decisão.

O gate olha o contexto acumulado do primeiro evento, da resposta do nome e do
banco. Ele não olha apenas o payload atual.

### 8.2 Mensagem

```text
Olha, para prosseguir precisamos que compartilhe o seu número de telefone. Aperte no botão abaixo.
```

Esse texto pertence ao novo
`core/integrations/whatsapp/messages/etapa2_messages.py`, em uma constante e em
um builder puro, seguindo o padrão das demais etapas. O resolver escolhe o
destinatário e passa somente o escalar ao sender:

```python
destinatario = resolver_destinatario_sender(
    contexto_historico,
    permitir_user_id=True,
)

contexto_envio = enviar_etapa2_compartilhamento_contato(
    destinatario,
    id_phone_unidade,
    id_conversa,
)
```

O sender importa o builder e realiza o I/O:

```python
mensagem_bot = montar_mensagem_etapa2()

wa.request_contact_info(
    to=destinatario,
    sender=id_phone_unidade,
    text=mensagem_bot,
    tracker=f"contato:{id_conversa}:etapa:2",
)
```

Nesta etapa, `destinatario` será o `user_id` lido do banco porque o WA ID ainda
não existe. O sender não recebe o valor diretamente do payload.

Não haverá:

- botão “Prefiro não informar”;
- entrada de telefone por texto;
- confirmação manual posterior;
- coleta de username;
- pausa ou rota alternativa.

O mesmo arquivo de mensagens expõe uma retomada neutra própria para os
tratamentos da etapa 2. Os builders de mídia, reforço escolar, financeiro e
contexto usam essa retomada e o mesmo componente oficial; não concatenam
automaticamente o prefixo de tratamento com a mensagem inaugural iniciada por
“Olha, para prosseguir...”. O plano fixa o contrato semântico, sem obrigar uma
segunda frase literal antes da implementação final.

### 8.3 Validação

Enquanto aguarda:

- primeiro, reconhecer
  `contacts + contact_request + wa_id_compartilhado` válido;
- depois, tratar qualquer outro `contacts` como contexto inválido;
- nas demais entradas, mídia: tratamento clássico de mídia + repetição;
- depois, dúvida sobre reforço escolar/banca/cursinho: tratamento universal +
  repetição;
- depois, pergunta financeira: tratamento financeiro + repetição;
- por fim, texto residual, mesmo que contenha um número: contexto específico e
  repetição do pedido oficial;
- contato manual/vCard já caiu no segundo item e nunca é reinterpretado como
  texto;
- somente `contacts` com origem `contact_request` e WA ID compartilhado extraído
  avança.

Todos os tratamentos reapresentam o pedido oficial com formulação neutra,
preservando o componente de compartilhamento e sem repetir uma abertura que
pressuponha sucesso na resposta anterior.

Essa ordem é obrigatória. O validador universal de mídia atual classifica
`contacts` como mídia/não texto; se ele rodar antes do reconhecimento oficial,
o clique correto nunca alcançará a transição. Da mesma forma, texto residual só
pode cair em contexto depois de reforço e financeiro, para que uma pergunta
mista como “qual o valor da banca?” receba o tratamento correto.

Depois do compartilhamento válido, o WA ID é persistido e volta ao sender pelo
`contexto_historico` reconstruído a partir do banco. A resposta seguinte usa esse
WA ID para enviar “Para quem é o atendimento?”. A promoção/reconciliação da
identidade já terminou em `validar_banco_mensagem()` antes desse envio. O
movimento 2 -> 3 e os efeitos finais da aresta continuam exclusivamente em
`atualizar_banco_com_contexto_final()` ->
`atualizar_banco_conforme_transicao_de_etapa()`.

### 8.4 Contrato exato das novas arestas

As três arestas afetadas ficam fechadas desta forma:

1. `1 -> 2`, evento `nome_cliente_valido_sem_wa_id`: o resolver da etapa 1 usa
   o validador de nome atual, comprova pelo contexto bancário que ainda não há WA
   ID, resolve o destino pelo mapa, envia o pedido oficial da nova etapa 2 ao
   user ID e anexa `primeiro_nome_cliente`. O efeito final persiste o nome por
   `id_cliente`, nunca por telefone;
2. `1 -> 3`, evento `nome_cliente_valido_com_wa_id`: o mesmo validador de nome
   resolve a aresta pelo mapa e envia ao WA ID o conteúdo da antiga etapa 2,
   renumerada para 3. O mesmo helper de efeito da saída anterior persiste o nome
   por `id_cliente`; reexecuções no retry são idempotentes e mantêm o mesmo
   resultado;
3. `2 -> 3`, evento `contato_oficial_compartilhado`: o resolver da etapa 2
   reconhece primeiro `contacts + contact_request + wa_id_compartilhado`, exige
   `wa_id_canonico` no contexto bancário, resolve a aresta e envia a etapa 3 a
   esse WA ID. `efeitos_transicao.py` reconhece explicitamente origem 2, evento e
   destino 3, mas não repete a promoção/reconciliação já concluída antes do
   sender.

O helper compartilhado de persistência do nome recebe o evento e o destino
efetivos do `contexto_envio`. Ele não mantém hardcode do legado
`EVENTO_NOME_CLIENTE_VALIDO`, de destino 2 nem textos de log “1 -> 2”; os logs e
as validações de destino refletem corretamente 1 -> 2 ou 1 -> 3. A idempotência
é de resultado: o efeito pode ser invocado novamente pelo caminho atual de retry
sem produzir nome divergente nem depender de telefone.

Texto, mídia, dúvida sobre reforço escolar, financeiro e contato manual tratados
na etapa 2 permanecem na etapa 2, repetem o pedido quando aplicável e não
carregam evento de transição. O contato oficial válido é reconhecido antes dos
tratamentos; nas demais entradas a ordem é mídia -> reforço -> financeiro ->
contexto. Nenhuma dessas decisões ocorre no sender nem dentro da função de
efeito.

## 9. Catálogo e mapa de transição

O catálogo final terá 23 etapas:

| ID | Etapa | Funil | Terminal |
|---:|---|:---:|:---:|
| 1 | Saudação e nome | não | não |
| 2 | Compartilhamento oficial do contato | não | não |
| 3 | Destino do atendimento | não | não |
| 4 | Confirmação do destino do atendimento | não | não |
| 5 | Profissão | não | não |
| 6 | Nome do dependente | não | não |
| 7 | Idade | não | não |
| 8 | Oferta | não | não |
| 9 | Oferta adiada | não | não |
| 10 | Retorno ao atendimento | não | não |
| 11 | Email | não | não |
| 12 | Introdução à triagem | não | não |
| 13–18 | Perguntas 1–6 da triagem | não | não |
| 19 | Agendamento | sim | não |
| 20 | Satisfação — nota | sim | não |
| 21 | Satisfação — opção de comentário | sim | não |
| 22 | Satisfação — comentário | sim | não |
| 23 | Finalização | sim | sim, bloqueio de 30 dias |

A baseline V1.0.7 já possui 22 etapas. Na migração futura, as etapas atuais
2..22 serão remapeadas para 3..23 sem apagar dados. A etapa 1 permanece no
mesmo ID e a única etapa realmente adicionada sobre essa baseline é a etapa 2
de compartilhamento oficial.

Essa renumeração é uma **regra de negócio deliberada**, não uma limitação
técnica do mapa. A tabela `etapa` representa a sequência integral percorrida por
um cliente elegível a todas as perguntas; por isso seus IDs acompanham a ordem
editorial e cronológica 1..23. O mapa `etapa_transicao` continua sendo a fonte de
verdade para desvios: o cliente que já possui WA ID salta a nova etapa 2, enquanto
o cliente somente com `user_id` percorre 1, 2, 3 ... 23. Inserir a etapa especial
como ID 23 apenas para evitar a migração contrariaria essa convenção do negócio,
mesmo sendo tecnicamente possível.

Conversas já existentes conservam seu progresso: uma conversa atual na etapa 2
vai para a futura etapa 3, a atual 3 vai para a futura 4 e assim por diante. Elas
não são devolvidas à etapa especial. Isso é seguro para a baseline, na qual o
WA ID ainda é obrigatório; somente atendimentos privados processados pelo código
novo entram na etapa 2 quando terminarem a captura do nome sem WA ID canônico.

Mapa final:

```python
TRANSICOES = (
    (1, "nome_cliente_valido_com_wa_id", 3),
    (1, "nome_cliente_valido_sem_wa_id", 2),
    (2, "contato_oficial_compartilhado", 3),
    (3, "destino_atendimento_definido", 4),
    (4, "destino_atendimento_confirmado", 5),
    (5, "profissao_dependente_valida", 6),
    (5, "profissao_titular_valida", 7),
    (6, "nome_dependente_valido", 7),
    (7, "idade_valida", 8),
    (8, "oferta_aceita", 11),
    (8, "oferta_adiada", 9),
    (9, "cliente_retornou", 10),
    (10, "retorno_confirmado", 11),
    (10, "retorno_adiado", 9),
    (11, "email_valido", 12),
    (12, "triagem_iniciada", 13),
    (13, "triagem_pergunta_1_respondida", 14),
    (14, "triagem_pergunta_2_respondida", 15),
    (15, "triagem_pergunta_3_respondida", 16),
    (16, "triagem_pergunta_4_respondida", 17),
    (17, "triagem_pergunta_5_respondida", 18),
    (18, "triagem_pergunta_6_respondida", 19),
    (19, "agendamento_confirmado", 20),
    (20, "satisfacao_avaliada", 21),
    (21, "comentario_satisfacao_aceito", 22),
    (21, "comentario_satisfacao_recusado", 23),
    (22, "comentario_satisfacao_recebido", 23),
)
```

Haverá resolvers para 1..22. A etapa 23 é terminal e não possui resolver.

### 9.1 Destino do atendimento preservado

A etapa atual 2 passa à futura etapa 3 conservando sua interface e seu
validador contextual:

- os botões visíveis continuam `Para mim` e `Para um dependente`;
- o texto legado `Para outra pessoa` e as frases inequívocas já catalogadas para
  titular, dependente, parentescos e destinos genéricos continuam aceitos;
- caixa, acentos, pontuação, espaços e vírgulas ausentes seguem a normalização
  atual;
- mídia, dúvida sobre reforço escolar, pergunta financeira ou qualquer conteúdo
  fora dos conjuntos reconhecidos permanecem como tratamento na etapa 3;
- a escolha continua sendo persistida pelos efeitos transacionais existentes e
  encaminha ambas as opções à confirmação, sem salto direto para profissão ou
  nome do dependente.

### 9.2 Confirmação do destino preservada

A confirmação implantada na V1.0.4 e preservada na baseline V1.0.7 passa da etapa
atual 3 para a futura etapa 4 sem ampliar sua gramática. Na baseline corrigida,
ela produz o evento único `destino_atendimento_confirmado` e sempre segue de 3
para a profissão atual 4; depois da renumeração, a mesma regra segue da
confirmação futura 4 para a profissão futura 5:

- aceita somente o clique nos botões `Sim`/`Não` ou o texto digitado
  `Sim`/`Não`, após a normalização já existente;
- `Sim` mantém o `status_dependente` definido na etapa anterior;
- `Não` persiste o polo oposto e segue adiante, sem voltar à etapa 3;
- qualquer outro texto que não tenha sido classificado antes como reforço
  escolar ou financeiro recebe tratamento de contexto e repete a etapa 4;
- mídia, dúvida sobre reforço escolar e pergunta financeira permanecem como
  tratamentos sem evento e sem avanço;
- o contexto carrega `status_dependente_final` absoluto, nunca uma ordem de
  inversão. O efeito transacional faz `SET` idempotente, cria o placeholder do
  dependente quando o valor final é verdadeiro e remove o placeholder quando o
  valor final é falso;
- titular e dependente produzem o mesmo evento
  `destino_atendimento_confirmado` e seguem obrigatoriamente para a profissão na
  etapa 5. Somente a resposta da profissão bifurca para o nome do dependente na
  etapa 6 ou para a idade do titular na etapa 7;
- o caminho de resposta do bot já existente reconstrói esse mesmo valor absoluto
  a partir do `status_dependente` booleano persistido na conversa. Ausência ou
  tipo inválido interrompe o ciclo para retry, sem assumir `False` e sem inverter
  novamente a resposta original.

Essa convergência não altera a identidade nem o destinatário do atendimento:
as regras de WA ID canônico, fallback de user ID antes do compartilhamento e
exigência de WA ID da futura etapa 3 em diante permanecem exatamente as mesmas.

### 9.3 Triagem por faixa etária preservada

O catálogo canônico compartilhado por WhatsApp e Funil continua em
`core/triagem/perguntas.py`, com as chaves renumeradas de 12..17 para 13..18:

- `valida_historico.ETAPAS_TRIAGEM` passa do intervalo atual 11..17 para
  12..18; a introdução futura 12 também relê nome, idade e destino para que o
  sender monte corretamente a primeira pergunta;
- titular usa as seis perguntas adultas com `você`;
- dependente menor de 18 anos usa as seis perguntas infantis com o nome;
- dependente adulto usa as seis perguntas adultas com o nome;
- a elegibilidade mínima de 4 anos em unidade com BPA ou 5 anos sem BPA
  continua pertencendo à validação de idade anterior à triagem;
- a regra histórica de idade acima de 99 continua sendo avaliada antes do
  suporte ao idoso; na futura etapa 7, titular de 60 a 99 anos só é encaminhado
  quando `suporte_idoso` estiver ativo, enquanto dependente nunca entra nesse
  ramo;
- status de dependente, nome e idade são relidos do banco em cada ciclo; dados
  ausentes ou inconsistentes falham de forma fechada;
- as respostas continuam restritas a `Nunca`, `Às vezes` e `Frequentemente`;
- a unicidade e a idempotência de `respostas_desafios (id_conversa, id_etapa)`
  permanecem iguais.

O contexto de agendamento que hoje é carregado nos ciclos 17/18 passa aos ciclos
18/19: a resposta da sexta pergunta precisa do link para enviar a etapa 19 e os
tratamentos da própria etapa 19 precisam repetir a mesma mensagem.

Confirmação, tratamentos e triagem por idade não exigem coluna nova da feature
de `user_id`. As flags de unidade e o novo motivo terminal já pertencem ao
estado prévio validado. Suas
mudanças futuras são de numeração, catálogo, validadores, mensagens e projeções
já previstas; o desenho físico de identidade da seção 5 permanece intacto.

## 10. Senders

Todos os resolvers recebem os identificadores já resolvidos pelo banco no
`contexto_historico`. Antes de chamar o sender de etapa, o resolver faz a seleção
central e consciente da etapa:

```python
destinatario = resolver_destinatario_sender(
    contexto_historico,
    permitir_user_id=envio_inicial_antes_do_wa_id,
)
```

Isso evita espalhar regras divergentes pelos arquivos de etapa e impede que um
erro posterior seja mascarado por fallback para user ID. O valor booleano só é
`True` nos envios da etapa 1 e no pedido/repetição de compartilhamento da etapa
2. A resposta `contato_oficial_compartilhado` usa o padrão `False`: se o WA ID
não estiver no contexto bancário, nenhuma mensagem da etapa 3 é enviada. O
helper devolve apenas o escalar usado no mesmo método PyWa atual. Username não
participa.

Ortogonalmente à escolha do destinatário, os quatro envios de primeiro contato
da etapa 1 — padrão, mídia, financeiro e reforço escolar — recebem também
`nome_unidade`, `nome_agente` e `genero` do contexto bancário da unidade. O
builder escolhe `o`/`a` a partir do gênero e monta a mesma apresentação dinâmica
nos quatro ramos. Tratamentos posteriores da etapa 1 não repetem essa abertura.
Nenhum sender infere apresentação a partir do destinatário, nem usa esses três
campos para decidir fallback entre WA ID e user ID.

Regras:

- `sender` é sempre o `phone_number_id` canônico da unidade localizada no banco;
  ausência do ID falha antes da Meta e `display_phone_number` nunca o substitui;
- antes do contato oficial, sem WA ID: user ID lido do banco;
- no evento válido de compartilhamento: WA ID primeiro persistido e depois lido
  do banco no contexto;
- depois da promoção: WA ID obrigatório em todos os senders;
- se evento posterior omitir WA ID, o banco preserva o valor canônico;
- username nunca é `to`;
- nenhuma função acrescenta ou remove o nono dígito do destinatário.

O sender de etapa devolve seu contexto técnico normal. A fronteira de
`flow_sender()` acrescenta `wa_id`, `user_id` e username ao `contexto_envio`
antes de qualquer retorno, inclusive no caminho idempotente, sem consultar banco
e sem alterar a persistência. O helper é exclusivo da resolução de destinatário
outbound e é chamado pelo resolver; bloqueio, desbloqueio e flood não o
reutilizam. Esses componentes resolvem a identidade tipada do evento para o
conjunto alias-aware quando houver prova persistida; isso não
autoriza fallback no sender. O evento inbound pode continuar chegando somente
com user ID depois da etapa 2, mas qualquer outbound posterior exige o WA ID
canônico relido do banco.

### 10.1 Tratamentos atuais preservados

A implementação futura não volta ao conjunto de validadores anterior à V1.0.7.
Toda etapa que possui tratamento financeiro continua possuindo também o
tratamento universal de dúvida sobre reforço escolar, inclusive a nova etapa 2.
O tipo técnico permanece `duvida_reforco_escolar`.

A gramática implantada é congelada durante a renumeração. Ela reconhece reforço
escolar/pedagógico, banca escolar, supletivo, EJA, Encceja, cursinho,
pré-vestibular/preparatório, aula ou professor particular, apoio,
acompanhamento, recuperação e nivelamento escolar, além de tarefa/dever de casa.
Matérias como matemática ou português só disparam quando ligadas a intenção de
aula, ensino ou ajuda; a palavra isolada não basta. Banca examinadora,
avaliadora, acadêmica, de concurso ou de TCC permanece excluída, assim como usos
não escolares de “reforço”. Formas curtas de `banca`/`reforço` continuam sujeitas
aos contextos controlados do validador atual. Ampliar ou reduzir esse vocabulário
é tarefa separada, não efeito da migração de identidade.

Na etapa especial, o validador do contato oficial válido roda primeiro, pois
`contacts + contact_request + wa_id_compartilhado` é a prova que autoriza a
transição. Contato manual ou inválido não satisfaz essa prova. Para as demais
entradas, e nas outras etapas, a prioridade permanece:

```text
mídia/tipo não suportado -> reforço escolar -> financeiro -> contexto/regra da etapa
```

Assim, uma frase mista como “qual o valor da banca?” recebe o tratamento de
reforço escolar, não o financeiro. Tratamentos ficam na etapa atual, retornam
`tratamento=True`, não carregam evento e não alteram transação, retry nem
contadores além do comportamento transversal já existente. As mensagens
financeiras preservam a expressão atual “valores de investimento”.

A profissão atual da etapa 4 passa à futura etapa 5 e continua obrigatória para
titular e dependente. A confirmação sempre apresenta essa pergunta; depois de
persisti-la, `status_dependente` escolhe a futura etapa 6, com o nome do
dependente, ou a futura etapa 7, com a idade do titular. Seus adaptadores
contextuais de reforço e financeiro também são renumerados e continuam
protegendo declarações inequívocas de vínculo profissional com banca, cursinho,
supletivo ou reforço. O classificador universal não é enfraquecido para as
demais etapas.

O validador renumerado da futura etapa 5 também preserva a proteção exata das
oito respostas completas fora de contexto definida na seção 4.3.1. Uma
correspondência apenas repete a pergunta na etapa 5, sem evento, transição,
persistência ou confirmação adicional. Não são permitidas regex ou listas de
palavras como `áudio`, `ligação`, `filho`, `filha` e `autista`, pois esses termos
podem fazer parte de uma profissão legítima ou de uma explicação válida.

Essa bifurcação também é fail-closed: `status_dependente` precisa ser um
booleano persistido tanto no resolver quanto no efeito da profissão. Ausência
ou tipo inválido interrompe o ciclo para retry, sem transformar `None` em
titular por coerção.

Cada mensagem de tratamento deve reapresentar a pergunta de forma neutra. Não é
permitido concatenar cegamente a mensagem inaugural quando ela começa com
expressões que pressupõem avanço ou resposta válida, como `Entendi`, `Certo`,
`Perfeito`, `Maravilha` ou `Prazer`. Mídia, reforço, financeiro e contexto
preservam os componentes, botões, rodapés e variantes titular/dependente da
etapa, mas usam uma retomada semanticamente coerente.

O validador da oferta atual 7, futuro 8, conserva a ordem
`negativo -> pedido de informação -> positivo`. Assim, `quero mais
informações`, `quero saber`, `quero entender` e `quero tirar uma dúvida` repetem
a etapa como pedido informativo, mas `quero`, `sim, quero`, `quero sim` e
`sim, gostaria` continuam confirmando. A renumeração não pode restaurar um
classificador que aceite a palavra `quero` dentro de qualquer frase.

A futura etapa 11 aplica a política de e-mail da seção 4.3.2 somente depois dos
três tratamentos prioritários. Resposta opcional aceita continua usando o evento
técnico `email_valido`; a classificação semântica viaja separadamente no
`contexto_envio` para o efeito transacional. A introdução da triagem resultante,
na futura etapa 12, preserva o texto atual iniciado por `Certo, antes...` e o
botão `Começar triagem`.

### 10.2 Saudação de retorno após três horas

Como delta estritamente aditivo da V1.0.7, uma resposta pode receber o prefixo
`Olá novamente, {nome}!` quando todas as condições abaixo forem verdadeiras:

1. o atendimento continua na mesma `id_conversa`, que já determina o mesmo
   cliente e a mesma unidade; não se procura a mensagem anterior por WA ID,
   user ID ou `id_cliente` global;
2. a etapa 1 já estava concluída antes do evento atual e o nome válido já estava
   persistido no cliente;
3. existe histórico anterior do bot nessa `id_conversa` com
   `quem_enviou='bot'` e `status_envio='sent'`;
4. a diferença entre o timestamp do evento atual e o timestamp desse último
   histórico `sent` do bot é maior ou igual a três horas.

A fonte temporal autoritativa é a última linha elegível de
`historico_mensagens`, ordenada por `received_data_hora DESC, id_mensagem DESC`,
comparada a `mensagem_cliente_atual.received_data_hora`. É proibido usar
`NOW()`, o horário em que o worker processou o item ou
`conversa.last_interaction_at`: atraso de fila e retry não podem fabricar uma
inatividade que não existiu no evento, e a interação da conversa já pode ter
sido atualizada com a própria mensagem atual do cliente.

O limiar é inclusivo: exatamente três horas saúdam; qualquer diferença menor
não saúda. Timestamp ausente, inválido ou sem ordenação temporal coerente resulta
apenas na omissão do prefixo. Já uma falha SQL segue o rollback e o retry normais
do worker: a feature não pode engolir erro bancário nem tentar continuar uma
transação abortada. Em nenhum desses casos a apresentação muda evento,
transição ou regra de negócio.

O gate de nome e etapa é avaliado sobre o estado anterior ao evento atual. Por
isso a própria mensagem válida que informa o nome na etapa 1 nunca recebe
`Olá novamente`, mesmo que o último envio do bot tenha ocorrido há três horas
ou mais. A saudação só se torna elegível em uma mensagem posterior, depois de o
nome estar persistido e a etapa 1 já ter sido concluída.

Depois de o resolver produzir a resposta normal, a composição faz, quando
elegível:

```text
Olá novamente, {nome}!

{mesma resposta normal já produzida}
```

O corpo normal não é reclassificado nem reconstruído. Em resposta válida, o
prefixo acompanha a mesma mensagem que encaminha à etapa de destino; em entrada
inválida, acompanha o mesmo tratamento que repete a etapa. Em ambos os casos
permanecem exatamente um `contexto_envio`, uma chamada Meta e uma linha de
histórico do bot, com os mesmos botões, mídia, evento, destino e metadados que a
resposta teria sem a saudação.

A barreira idempotente já existente continua anterior à composição:
`bot_resposta_atual()`/`resposta_bot_para_mensagem_atual` deve encerrar o caminho
já respondido antes de consultar ou aplicar a saudação. Um retry que encontra a
resposta do bot apenas marca/reconstrói o resultado atual, sem novo prefixo,
novo sender ou novo histórico. A feature não acrescenta etapa, evento,
transição, commit, rollback, retry, lock, envio, registro ou contador.

## 11. Funil

WA ID continua obrigatório para o comercial e para materializar o lead. A
implementação deve adaptar o fluxo atual — `buscar_dados_lead_funil()`,
`montar_observacoes_lead()` e `montar_payload_oportunidade()` — sem criar uma
arquitetura paralela.

Regras:

- WA ID + username: enviar os dois nas observações;
- somente WA ID: enviar WA ID;
- somente username: nunca materializar;
- user ID: nunca mostrar ao comercial;
- username aparece com exatamente um `@`;
- elegibilidade começa na etapa 19 e abrange 19..23;
- a etapa especial impede que uma conversa sem WA ID alcance a etapa 19.

O Funil usa `conversa.username` para representar o snapshot daquele atendimento
e o coloca, quando existir, junto às informações de contato antes da seção de
triagem. `cliente.username` continua disponível como valor canônico atual, mas
não reescreve retroativamente o lead antigo.

No contrato futuro do repositório, `buscar_dados_lead_funil()` seleciona
`cliente.wa_id` como telefone obrigatório e `conversa.username` como username
do atendimento, devolve ambos no dicionário do snapshot e filtra
`respostas_desafios.id_etapa BETWEEN 13 AND 18`. Não usa
`cliente.username` como atalho e não projeta `user_id` para a integração.

O e-mail também é histórico da conversa, não uma leitura tardia cega de
`cliente.email`. O repositório localiza a mensagem exata do cliente na futura
etapa 11 ligada à resposta `sent` do bot na futura etapa 12 pelos campos
`id_mensagem_fila` e `id_hash_cliente_origem`. Essa resposta é reclassificada
pelo classificador puro como endereço válido, ausência explícita ou não
informado. O payload usa o endereço quando existir e valor vazio quando não
existir; nunca grava placeholders no campo técnico. Nas observações, mostra
respectivamente o endereço, `não tem` ou `não informado`.

Atendimentos legados sem vínculo histórico podem usar `cliente.email` apenas
como fallback de compatibilidade. Dados novos não podem ser contaminados por
uma conversa posterior que tenha atualizado ou limpado o e-mail global do mesmo
cliente. `montar_payload_oportunidade()` e `montar_observacoes_lead()` recebem a
mesma classificação já resolvida para não divergirem entre campo técnico e
texto humano.

O detalhamento preservado na V1.0.7 também é obrigatório:

- `buscar_dados_lead_funil()` lê as respostas das futuras etapas 13..18 em
  ordem crescente;
- `core/triagem/perguntas.py` é a única fonte dos textos exibidos no WhatsApp e
  reconstruídos no Funil;
- `montar_observacoes_lead()` apresenta “Perguntas e respostas da triagem” com
  seis blocos ordenados, cada um contendo número, pergunta completa e resposta;
- não volta a existir resumo quantitativo como “Nunca: 2 vezes”;
- titular usa a variante adulta com `você`; dependente usa o nome e a variante
  infantil ou adulta conforme a idade;
- ausência, duplicidade, desordem ou resposta fora de `Nunca`, `Às vezes` e
  `Frequentemente` impede a montagem do lead;
- ausência de username não impede o lead; ausência de WA ID continua impedindo.

## 12. Bloqueio, desbloqueio e Django Admin

`cliente_bloqueado_meta` exige WA ID ou user ID. Toda proteção recebe primeiro o
`phone_id_unidade` obrigatório e resolve o mesmo conjunto da seção 4.2:

1. sem prova, consultar somente o alias tipado do evento;
2. com prova, consultar por `id_cliente + id_unidade` e por qualquer WA/user ID
   conhecido daquela unidade;
3. considerar a pessoa bloqueada se qualquer membro do conjunto estiver na
   denylist, no bloqueio Meta, no cache temporário ou em conversa dentro do prazo;
4. username servir somente à exibição.

Assim, depois do vínculo, entrar por user ID não contorna bloqueio criado por WA
ID, e entrar por WA ID não contorna bloqueio criado por user ID. Isso não torna
user ID destinatário de sender posterior: aliases de proteção e destinatário
outbound continuam contratos diferentes.

Ao promover uma pessoa à denylist/Meta, vale o seguinte contrato de persistência:

- existe uma única linha canônica por pessoa comprovada e unidade, ancorada por
  `(id_cliente, id_unidade)` quando o cliente já foi resolvido;
- a linha exige pelo menos um entre `wa_id` e `user_id`;
- se o evento de bloqueio trouxer os dois aliases, ambos são gravados na mesma
  linha e ambos são enviados à operação de bloqueio da Meta;
- se inicialmente existir somente WA ID ou somente user ID, a linha pode nascer
  com o outro campo `NULL`. Uma prova oficial posterior preenche apenas esse
  campo nulo; nunca sobrescreve silenciosamente um alias não nulo divergente;
- se antes da prova existirem linhas separadas que depois forem demonstradas
  como a mesma pessoa/unidade, elas são bloqueadas em ordem determinística,
  consolidadas na linha canônica e a linha equivalente excedente é removida sem
  apagar a intenção de bloqueio;
- unidades diferentes mantêm linhas diferentes. O mesmo WA ID pode aparecer em
  mais de uma unidade, enquanto o user ID continua específico de cada unidade;
- contradição entre aliases já não nulos falha de forma fechada e não provoca
  merge por nome, username ou coincidência temporal.

Antes de enriquecer uma linha ou chamar a Meta, o guard compara os aliases
explícitos do envelope com qualquer vínculo já persistido. Um par contraditório
gera log crítico e descarte determinístico sem `UPDATE`, bloqueio externo ou
merge. Toda seleção, preenchimento de campo `NULL` e consolidação de linhas usa o
mesmo advisory lock transacional da unidade/sujeito; o `LIMIT 1` nunca decide
sozinho em presença de possíveis linhas equivalentes.

Um envelope assinado WA+user que já esteja barrado no webhook não cria
`user_id_cliente`, pois o worker continua sendo o único dono da identidade
canônica. Os dois aliases ficam, entretanto, preservados na linha de denylist.
No desbloqueio administrativo, uma pré-validação resolve de forma inequívoca
`id_cliente + id_unidade`; após desbloquear todos os aliases na Meta e antes de
apagar a linha local, a mesma transação consolida `user_id_cliente` quando houver
cliente canônico. Conflito preserva a linha e falha de forma fechada; ausência de
cliente canônico não inventa cadastro nem vínculo.

A tentativa na Meta é feita para cada alias conhecido em ordem determinística,
com resultado individual observável; falha parcial mantém o registro local e
provoca nova tentativa, nunca libera o alias que falhou. Durante merge, uma
eventual linha do provisório é reatribuída/consolidada com a linha canônica, sem
apagar a intenção de bloqueio. Se esse bloqueio Meta for descoberto no handoff,
a conversa nova também é encerrada com `bloqueio_reconciliado`, sua fila atual é
removida atomicamente e nenhuma resposta é enviada.

O bloqueio de conversa por dias também é alias-aware. Se a reconciliação descobrir
uma conversa canônica que **já estava encerrada antes do merge** e ainda está
dentro do prazo, a data `finalizou_em` original é a única origem da expiração: a
conversa nova é encerrada sem criar novo prazo, sem
reiniciar 30 dias e sem avançar/sender, usando
`motivo_encerramento='bloqueio_reconciliado'`. Bloqueio expirado não impede que a
nova conversa continue. `ativou_privacidade` só encerra outra conversa canônica
que ainda estava ativa no momento da reconciliação; esse encerramento novo não é
reinterpretado como bloqueio preexistente.

Para isso, a consulta de proteção não pode continuar escolhendo simplesmente a
conversa encerrada mais recente. Ela procura, no sujeito canônico e em todos os
aliases comprovados da unidade, conversas já encerradas cuja etapa tenha
`bloqueio_dias > 0`, calcula `finalizou_em + bloqueio_dias` e considera vigente
qualquer expiração maior que `NOW()`. Se houver mais de uma, prevalece a maior
expiração original. A conversa fechada com `bloqueio_reconciliado` não cria uma
nova fonte de prazo; serve apenas para registrar por que aquele atendimento novo
não continuou.

Ao excluir um bloqueado no Admin, o sistema continua chamando primeiro o
desbloqueio na Meta para **todos** os aliases registrados e só exclui localmente
após sucesso integral, conforme a ordem Meta -> banco. Uma falha em qualquer
alias preserva a linha canônica inteira para retry. Cliente legacy com apenas WA
ID e provisório com apenas user ID continuam funcionando como conjuntos
unitários.

Admin:

- Unidade exige, exibe e edita `nome_unidade`, `nome_agente`, `genero` e
  `id_portfolio`; também exibe/edita/filtra `suporte_idoso` e
  `email_obrigatorio`, pesquisa por nome da unidade/agente, filtra por gênero e
  ordena por `nome_unidade`;
- o formulário de Unidade só aceita `suporte_idoso=TRUE` quando
  `numero_comercial` passa pelo validador compartilhado. Alterar as flags afeta
  ciclos futuros; retry de resposta já persistida conserva a decisão histórica;
- Cliente exibe WA ID anulável e username opcional;
- Fila, histórico, conversa, bloqueio e flood exibem os três snapshots;
- `user_id_cliente` é consultável, pesquisável por cliente/unidade/user ID e
  somente leitura; vínculos são alterados apenas pelo fluxo transacional;
- buscas aceitam WA ID, user ID e username;
- `__str__` não presume WA ID e usa fallback legível para user ID/chave;
- username não altera ações, filtros de identidade ou permissões;
- relações administrativas com unidade usam `id_unidade__nome_unidade`, nunca o
  caminho legado `id_unidade__nome`.

## 13. PyWa 4.x

A atualização da biblioteca será feita em mudança isolada e com versão exata
confirmada no dia da implementação. Não se usará uma versão futura presumida.

Antes do deploy serão validados:

- criação de `WhatsApp(...)` com Graph API v26.0 central;
- envio normal para WA ID;
- envio inicial para user ID somente antes do compartilhamento obrigatório;
- `request_contact_info(to=user_id, sender=phone_id_unidade, ...)`, com o sender
  obrigatoriamente vindo da unidade validada e nunca de `display_phone_number`;
- parsing de `ContactsOrigin.CONTACT_REQUEST`;
- extração do `phones[].wa_id` explícito, com validação própria de cardinalidade
  e formato; `Phone.phone` não serve de fallback;
- bloqueio e desbloqueio com todos os aliases comprovados da unidade, inclusive
  conjuntos unitários WA-only/user-only, sem ampliar o fallback dos senders;
- ativação/desativação de WABA e número;
- um smoke test real em ambiente de teste.

Não haverá fallback automático entre versões da Graph API.

## 14. Arquivos e passos de implementação

### Passo 1 — Contratos puros

Criar/alterar, com arquivo completo no apêndice definitivo:

- `core/integrations/whatsapp/identidade.py`;
- `callback/webhook/services/identidade_meta.py`;
- testes usando os quatro JSONs de `payloads/`.

### Passo 2 — Banco declarativo

Atualizar, com arquivo completo:

- `core/database/deploy_database/bank_script.py`;
- `core/database/deploy_database/floodscript.py`;
- `core/database/deploy_database/turno_cliente_script.py`;
- `core/database/deploy_database/povoar_etapas.py`;
- `core/database/deploy_database/etapa_transicao_script.py`;
- `callback/webhook/models.py`;
- `callback/webhook/admin.py`.

Ao mesclar o estado final, `bank_script.py`, models e Admin devem partir do
contrato pré-`user_id` auditado: `nome_unidade`, `nome_agente`, `genero`,
`suporte_idoso`, `email_obrigatorio`, suas constraints/defaults e todos os
caminhos ORM com `nome_unidade` são preservados. Este passo acrescenta
`id_portfolio` e o contrato de identidade sem restaurar `unidade.nome` nem
reaplicar as migrações de apresentação, profissão ou políticas de unidade.

O DDL cria `chatbot.user_id_cliente`; o model correspondente usa
`id_user_id_cliente = models.BigAutoField(primary_key=True)`, `models.PROTECT` na
FK de cliente e `models.CASCADE` na FK de unidade, em correspondência a
`ON DELETE RESTRICT`/`ON DELETE CASCADE` do PostgreSQL. Ele será registrado no
Admin em modo somente leitura. O mesmo passo inclui `ativou_privacidade` e
`bloqueio_reconciliado` no CHECK/choices de conversa, preservando também
`encaminhado_suporte_idoso`: o primeiro encerra outra
conversa canônica ativa durante o merge; o segundo encerra a conversa nova ao
herdar um bloqueio canônico ainda vigente, sem alterar a data-base do prazo.

### Passo 3 — Webhook e fila

Atualizar, com arquivo completo:

- parser/serviço de POST;
- população idempotente da fila;
- `callback/webhook/services/flood_guard.py`;
- bloqueio guard;
- repositório de turno;
- `core/cache/runtime/cache_flood_redis.py`;
- `core/cache/cache_flood_memoria.py`;
- `core/repositories/seguranca/bloqueio_meta.py`;
- demais caches Redis e fallbacks em memória que recebem identidade técnica.

Turno, denylist e bloqueios preservam o alias primário do item, mas resolvem uma
única decisão sobre todo o conjunto comprovado da pessoa/unidade. Os advisory
locks dos aliases são adquiridos em ordem determinística e a consulta usa WA/user
como alternativas, nunca como duas decisões nem como chave concatenada. O parser
mantém `wa_id_remetente` separado de `wa_id_compartilhado`; este último só integra
a prova candidata quando um `contact_request` oficial, autenticado e inequívoco
chega ao worker; ele não cria vínculo no webhook.

O anti-flood resolve o vínculo permanente por `user_id_cliente`. Redis, memória
e fallback SQL somam os eventos dos aliases oficialmente vinculados, com
deduplicação por WAMID; novos eventos
incrementam a referência canônica WA ID. Um cache negativo de 5 segundos evita
consultar o RDS a cada evento sem vínculo, e o vínculo confirmado permanece em
cache por 1 hora. Conflito ou indisponibilidade que impeça uma decisão segura
falha de forma fechada sem criar equivalência ou bloqueio por hipótese: conflito
determinístico recebe HTTP 200 e indisponibilidade transitória do RDS recebe HTTP
503. Quando o RDS prova que ainda não existe vínculo, Redis indisponível não
descarta a mensagem válida; o alias unitário continua pelo fallback banco ->
memória da V1.0.7. O limite continua 15 WAMIDs distintos em 5 segundos. Antes do primeiro
commit, a segunda barreira de predecessor do worker impede que a prova posterior
ultrapasse item anterior do outro alias. Essa continuidade
fica nas camadas próprias do webhook/cache/repositório e não cria efeito lateral
dentro da reconciliação transacional.

### Passo 4 — Repositórios e transporte do worker

Atualizar, com arquivo completo:

- fila;
- cliente;
- conversa;
- histórico;
- bloqueio/flood;
- estado do ciclo;
- validação de banco;
- validação de histórico;
- contexto de envio.

Entre os arquivos completos deste passo estão explicitamente
`core/repositories/fluxo/contextos/etapa1.py` e
`workers/worker_flow/valida_historico.py`. A primeira consulta continua
retornando `nome_unidade`, `nome_agente` e `genero`; a segunda continua fazendo
essa carga somente quando a conversa ainda não possui etapa. O transporte novo
de identidade deve ser mesclado a esse comportamento, sem substituir nem
reclassificar os três campos editoriais como identidade.

Criar também o repositório de `user_id_cliente` e os helpers restritos de
reconciliação. A resolução pelo vínculo deve acontecer antes da criação de
cliente provisório; no handoff, antes da busca prioritária do cliente pelo WA
ID, para não perder a conversa nova.

`flow_worker.py` recebe somente campos adicionais nos dicionários que já
trafegam pelo ciclo. `contexto_banco` alimenta `contexto_historico`, o resolver
recebe esse contexto, passa somente o destinatário escalar ao sender e
`flow_sender()` faz `contexto_envio` refletir os mesmos snapshots. Não se
adicionam commits nem tratamento genérico novo. Acrescentam-se apenas os dois
resultados controlados: lock fresco causa rollback, requeue sem erro de 5
segundos e `continue`, antes de qualquer mutação; bloqueio reconciliado usa o
commit pós-validação já existente e então faz `continue`, depois de confirmar o
cache e antes de histórico, lock normal ou sender.

Na mesma fronteira, o repositório de histórico expõe uma consulta auxiliar para
o último envio do bot com `status_envio='sent'` pela `id_conversa` exata. O
worker só a chama no caminho ainda não respondido, depois da barreira
idempotente, compara o resultado ao timestamp do evento atual e transporta no
contexto apenas o prefixo opcional já decidido. Resolver e sender não executam
SQL. Ausência ou inconsistência temporal deixa o prefixo vazio e não impede a
resposta normal; falha SQL conserva o rollback e o retry transacionais já
existentes.

`montar_mensagem_fila()` calcula a identidade tipada/congelada e sua única
referência de cache; `atualizar_estado_com_mensagem()` registra ambas antes da
validação. Depois, o estado recebe o candidato compartilhado e o WA ID canônico
quando disponíveis. Ordem, logs, finalização, retry e autocura usam a identidade
do item; o reparo stale remove somente a referência registrada. A implementação
não pode reconstruir essa chave pelo WA ID compartilhado/canônico nem remover
cache de outra unidade.

Os mesmos arquivos preservam `lock_version` no contrato atual de posse e
`unlock`. Os helpers de reconciliação bloqueiam linhas em ordem determinística,
recusam todo lock que ainda não satisfaça o predicado stale de 110 segundos da
V1.0.7 e, no takeover stale, incrementam a versão antes de limpar a posse. Assim,
um `unlock` tardio com a
versão anterior não libera um lock novo; esta feature não reescreve toda a
persistência pós-lock. Os helpers também copiam o nome provisório para o canônico
e nunca fazem backfill de fila/histórico/username da conversa.

### Passo 5 — Etapa especial e renumeração

Antes de criar a etapa especial, atualizar e entregar completos os arquivos da
etapa 1 já personalizados na baseline V1.0.7:

- `core/integrations/whatsapp/messages/etapa1_messages.py`;
- `core/integrations/whatsapp/pywa_functions/pywa_senders/etapa1.py`;
- `workers/worker_flow/response_flow/etapas/resolver_etapa1.py`.

O merge preserva as apresentações dinâmicas nos quatro ramos iniciais — padrão,
mídia, financeiro e reforço escolar — e mantém as retomadas posteriores sem
repetir a abertura. O resolver combina duas decisões independentes: recebe o
destinatário escalar já autorizado pelo contrato `wa_id`/`user_id` e, somente no
primeiro contato, passa os três dados editoriais da unidade ao sender.

Criar e entregar completos, com as fronteiras da seção 7.5:

- `core/integrations/whatsapp/messages/etapa2_messages.py`;
- `core/integrations/whatsapp/pywa_functions/pywa_senders/etapa2.py`;
- `workers/worker_flow/response_flow/etapas/validadores_contexto/valida_etapa2.py`;
- `workers/worker_flow/response_flow/etapas/resolver_etapa2.py`.

Atualizar explicitamente `flow_sender.py`, `transicoes/eventos.py`,
`transicoes/resolver_transicao.py` sem mudar seu algoritmo e
`transacoes/efeitos_transicao.py`. Esse último reconhece 1 -> 2, 1 -> 3 e
2 -> 3; as duas saídas da etapa 1 chamam o mesmo efeito de persistência do nome
por `id_cliente`, com evento/destino efetivos e sem hardcode legado, e 2 -> 3 não
repete SQL de identidade.

Renumerar mecanicamente todos os arquivos atuais 2..22 para 3..23, incluindo
mensagens, senders, validadores, resolvers, constantes, imports, IDs usados nos
efeitos, testes, catálogo e mapa. A regra das etapas atuais não muda; o conteúdo
preserva as quatro mensagens iniciais editoriais aprovadas das etapas atuais 2,
10, 11 e 22, o botão `Começar triagem`, a proteção da oferta e as políticas de
suporte/e-mail. A etapa terminal 23 não ganha resolver.

Nos caminhos físicos, a movimentação ocorre em ordem decrescente — 22 -> 23 até
2 -> 3 — ou por nomes temporários equivalentes. Só depois é criado o novo
arquivo da etapa 2, evitando sobrescrever módulos da baseline.

A renumeração inclui explicitamente:

- a confirmação atual 3 -> futura 4, seu bloco idempotente em
  `flow_sender.py`, seu evento único `destino_atendimento_confirmado`, a saída
  obrigatória para a profissão e os efeitos de valor absoluto reconstruídos
  somente de `status_dependente` booleano persistido;
- a profissão atual 4 -> futura 5, inclusive
  `validadores_contexto/valida_etapa4.py` ->
  `validadores_contexto/valida_etapa5.py`, preservando a comparação exata das
  oito respostas completas fora de contexto, e os adaptadores contextuais
  `validador_reforco_escolar_etapa4.py` ->
  `validador_reforco_escolar_etapa5.py` e
  `validador_financeiro_etapa4.py` ->
  `validador_financeiro_etapa5.py`, com imports e testes ajustados. A etapa 5
  permanece obrigatória nos dois fluxos e somente ela bifurca dependente para 6
  ou titular para 7;
- a introdução à triagem atual 11 -> futura 12;
- o fluxo de idade atual 6 -> futuro 7, incluindo `suporte_idoso`, CTA,
  persistência de idade, encerramento sem bloqueio e replay histórico;
- a oferta atual 7 -> futura 8, incluindo a precedência de pedidos de
  informação antes das confirmações positivas;
- a coleta de e-mail atual 10 -> futura 11, incluindo o novo contexto de
  política, classificador compartilhado, gravação absoluta de `cliente.email`
  e replay sem reavaliar a flag;
- `core/triagem/perguntas.py`, cujas chaves atuais 12..17 passam a 13..18;
- `valida_historico.ETAPAS_TRIAGEM`, que passa de 11..17 para 12..18;
- `core/repositories/fluxo/contextos/triagem.py`, os módulos numerados de
  triagem, `pywa_senders/triagem_base.py` e o contexto atual da etapa 18, que
  passa a representar o agendamento na etapa 19; a carga desse contexto muda
  dos ciclos 17/18 para 18/19;
- `core/repositories/funil/leads.py`, com filtro das respostas 13..18;
- `core/integrations/funil/oportunidades.py`, com conjunto esperado 13..18 e
  representação histórica de e-mail válido/ausente/não informado;
- `core/integrations/whatsapp/messages/triagem_componentes.py`;
- `REGRAS_DE_NEGOCIO.md`, `PADROES_DE_ARQUITETURA.md`,
  `ROTINA_IMPLEMENTACAO_ETAPAS.md` e `tests/README.md`, para que a documentação
  aplicada não mantenha IDs anteriores;
- testes de confirmação, triagem etária, Funil, tratamentos, efeitos,
  transições, deploy, roteamento e terminalidade.

A varredura de 29/08/2026 também identificou consumidores executáveis fora do
runtime dos serviços. Eles não mudam a regra de negócio, mas precisam acompanhar
os nomes finais do schema e a numeração para continuarem utilizáveis:

- `utilitarios/reports_functions/weekly.py` e, por reutilização, `total.py`:
  consultar `cliente.wa_id` em vez de `waid_telefone`;
- `utilitarios/monitoring/suspicious_conversations.py`: usar `cliente.wa_id`;
- `utilitarios/monitoring/blocked_users.py`: projetar cada alias persistido por
  uma lateral de `wa_id` e `user_id`, para comparar ambos sem ocultar bloqueios
  privados nem reduzir uma linha enriquecida a apenas um identificador;
- `utilitarios/montar_lead_teste.py`: usar as futuras etapas de triagem 13..18;
- `utilitarios/cache_consulta.py`: revisar o contrato de exibição legado
`cliente_telefone` para `tipo_identidade`/`identidade`, sem tratá-lo como nome
físico de coluna;
- `utilitarios/operacoes_rotineiras.sql`: consultar `cliente.wa_id`;
- `tests/unit/test_valida_etapa7.py`: mover integralmente para a futura etapa 8;
- `tests/unit/test_suporte_idoso_email_obrigatorio.py`: conservar a matriz e
  renumerar somente idade 6→7, e-mail 10→11 e triagem 12..17→13..18.

O plano prático deve trazer o conteúdo integral de cada utilitário realmente
alterado. Arquivos de relatório/monitoramento gerados e dependências exclusivas
desses utilitários continuam fora do deploy dos três serviços.

### Passo 6 — Senders e Meta

Centralizar a seleção consciente da etapa: WA ID sempre prioritário; user ID só
quando o resolver do envio da etapa 1 ou do pedido/repetição de compartilhamento
habilitar explicitamente o fallback. A resposta válida da etapa 2 e todos os envios
posteriores exigem WA ID. Alterar apenas as assinaturas/calls necessárias e
garantir o mesmo contrato no retorno idempotente de `flow_sender()`. Não
regredir textos, tratamentos, perguntas etárias ou regras das etapas atuais; a
mudança nelas é de numeração e de transporte dos novos snapshots.

O resolver chama o helper puro com a permissão explícita da etapa e passa apenas
o destinatário escalar ao sender. O sender não recebe o contexto inteiro para
decidir fallback. `flow_sender()` acrescenta os snapshots ao retorno de todo
resolver e ao retorno idempotente antes de devolver `contexto_envio`.

Nas assinaturas da etapa 1, conservar `nome_unidade`, `nome_agente` e `genero`
nos quatro senders iniciais. Esses argumentos são de apresentação e não entram
no helper de destinatário; o destinatário continua sendo um único escalar
resolvido antes da chamada.

Também transportar o prefixo opcional de retorno já calculado pelo worker. A
composição acontece antes da única chamada Meta e envolve o mesmo corpo normal
que o resolver já escolheu, inclusive tratamentos que repetem a etapa. Não se
cria sender separado nem uma segunda chamada; botões, mídia, evento, destino e
persistência continuam pertencendo à resposta original. A própria mensagem de
nome da etapa 1 permanece inelegível, e o retorno idempotente ocorre antes dessa
composição.

### Passo 7 — Funil, bloqueio e Admin

No Funil, manter WA ID obrigatório e acrescentar username somente como
informação opcional quando existir. Preservar o relatório atual com as seis
perguntas e respostas em ordem, usando o catálogo compartilhado e nunca o
resumo quantitativo antigo. Não transferir, reagendar ou conciliar itens de
`funil_envios` durante a reconciliação. Bloqueio, desbloqueio, denylist e Admin
recebem a resolução alias-aware e a consolidação segura da linha do provisório.
`cliente_bloqueado_meta` mantém uma linha canônica por pessoa/unidade após a
prova, exige ao menos um alias, grava ambos quando conhecidos e somente enriquece
campos `NULL`; linhas equivalentes são consolidadas e unidades distintas
continuam isoladas. Bloqueio e desbloqueio chamam todos os aliases conhecidos,
e o Admin só exclui a linha local depois do desbloqueio Meta integral.
O snapshot do Funil deve ligar a resposta do cliente na futura etapa 11 à
resposta do bot na etapa 12, sem usar um e-mail global posterior como se fosse
histórico. Na implementação futura, atualizar as choices e
`MOTIVOS_ENCERRAMENTO_VALIDOS` com `ativou_privacidade` e
`bloqueio_reconciliado`, mantendo também `encaminhado_suporte_idoso` e os usos
distintos definidos nas seções 4.3.2 e 4.5.

No Admin de unidade, preservar ainda os campos V1.0.7 `nome_unidade`,
`nome_agente` e `genero`, incluindo pesquisa, filtro, ordenação e referências
ORM por `id_unidade__nome_unidade`; preservar as flags de suporte/e-mail e a
validação compartilhada do número comercial; acrescentar `id_portfolio` sem
reduzir esse contrato.

### Passo 8 — PyWa

Atualizar `requirements.txt`, adaptar apenas APIs incompatíveis e executar os
smokes reais antes de produção.

### Passo 9 — SQL manual final

O SQL normativo é a migração-base completa para o schema derivado da V1.0.7,
commit `2bc41888db4987e957c5653825acf4a55e9d611d`, acrescido dos deltas
pré-`user_id` aprovados. Ele deverá ser revalidado contra o commit definitivo antes da
execução, porque os serviços e o banco ainda não receberam a feature de
`user_id`. As migrações de apresentação, profissão e
`20260829_adicionar_suporte_idoso_email_obrigatorio.sql` são pré-condições e não
são reaplicadas por este SQL.

O comando normativo e integral está mantido em um único lugar: o **Passo 160
(final)** de `docs/user_id_plano_logico_pratico.md`. Esta seção teórica define
o contrato e os cuidados; o plano prático contém o SQL executável, seu SHA-256,
preflight, snapshots, pós-validações e instruções operacionais. Essa fonte única
evita que duas cópias extensas do mesmo artefato divirjam silenciosamente.

Esse comando **não deve ser executado agora**. Antes da futura execução será
comparado ao DDL efetivamente implementado e aplicado integralmente em um
ambiente dev controlado. Este plano não inclui SQL inverso nem kill switch: a
promoção para produção só poderá usar o mesmo artefato já validado em dev.
O SQL garante aquisição/takeover e `unlock` por versão. A implementação Python
preserva o uso atual do `lock_version` na posse e no `unlock`. Para esta feature,
o requisito adicional é delimitado: o merge nunca limpa um lock enquanto não for
verdadeiro o predicado stale de 110 segundos da V1.0.7; depois disso, o takeover
incrementa a versão sob row lock, de modo que um `unlock` atrasado com a versão
anterior não solte a posse nova.
Não se inclui neste plano uma conversão de cada escrita pós-lock em CAS.

## 15. Testes essenciais

Os itens abaixo são critérios de aceitação, não autorização para criar um teste
isolado por linha. A implementação deve agrupá-los em poucas suítes
parametrizadas: preservar A/B/C, acrescentar somente cenários controlados de
identidade/handoff, bloqueio e dois workers, e evitar multiplicação combinatória
de testes que repitam a mesma regra. O plano prático consolida essa cobertura nos
suítes integrais enumeradas no plano prático; esta lista não autoriza criar
variações redundantes da mesma regra.

Três desses métodos formam uma prova diferencial explícita da baseline: depois de
normalizar a renumeração deliberada `1 -> 1` e `2..22 -> 3..23`, eles comparam o
catálogo e o mapa legados, os textos e botões das 22 etapas existentes e o
payload do Funil no caminho WA-only sem username. A comparação textual aceita
exclusivamente os deltas posteriores ao commit `2bc4188`: a mensagem e o CTA de
suporte na etapa atual 6/futura 7, além do prefixo “Certo” e do botão “Começar
triagem” na etapa atual 11/futura 12. Todos os demais textos e botões devem
permanecer idênticos. Essa prova
complementa os testes funcionais de destinatário, persistência, retry e turno;
ela não autoriza copiar a implementação antiga nem enfraquecer os testes
aditivos de `user_id`.

### 15.1 Payload e webhook

- cada um dos quatro fixtures é interpretado corretamente;
- ausência estrutural de `metadata.phone_number_id` responde HTTP 200 e não
  enfileira; falha transitória de RDS/insert/commit responde HTTP 503. Redis
  indisponível só produz 503 quando não existir fallback seguro;
  `display_phone_number` não serve de fallback nem de `sender`;
- WA ID principal vence `from` equivalente;
- user ID principal vence `from_user_id` equivalente;
- campos equivalentes divergentes são descartados com HTTP 200;
- `display_phone_number` nunca vira cliente;
- sem WA ID e user ID: HTTP 200, sem fila;
- username ausente: atendimento normal;
- `contacts` oficial persiste `conteudo_texto='contact_request'`;
- `contacts` manual persiste `conteudo_texto='other'` e não satisfaz a etapa;
- origem em `messages[0].origin` e em `contacts[*].origin` é reconhecida;
- origens ausentes, desconhecidas ou conflitantes persistem `other`;
- um único WA ID explícito de `contacts[*].phones[*]` é aceito;
- duas ou mais ocorrências, inclusive repetindo o mesmo WA ID, não escolhem o
  primeiro e não avançam;
- `CONTACT_INFO.json` mantém `user_id` como identidade do item e extrai o número
  do cartão separadamente como `wa_id_compartilhado`;
- teste sintético de `contact_request` com WA ID no envelope, user ID e WA ID no
  cartão ainda congela o item pelo user ID e só usa WA canônico após a prova;
- `wa_id_compartilhado` não vira identidade de denylist, bloqueio, turno, cache
  de cliente, autocura ou anti-flood antes da validação bancária;
- `valida_historico()` expõe `wa_id_compartilhado` somente para o item oficial e
  mantém `contexto_historico['wa_id']` reservado ao WA ID canônico do banco;
- ausência, Unicode numérico, valor formatado, `phones[].phone` sem WA ID ou
  mais de uma ocorrência explícita não promovem identidade;
- WA ID explícito preserva todos os dígitos, inclusive o nono;
- os arrays externos continuam processando somente um evento por POST;
- somente user ID já mapeado é resolvido pelo banco no worker sem criar outro
  cliente provisório;
- evento somente-user-ID já mapeado em etapa posterior é aceito no transporte,
  resolve WA ID canônico no worker e envia exclusivamente a esse WA ID;
- evento em etapa 3 ou posterior cujo vínculo não devolva WA ID canônico falha
  antes de chamar a Meta;
- WA ID + user ID + username registra o vínculo proativamente;
- sem vínculo comprovado, denylist, bloqueio e turno recebem somente o alias
  tipado pelo qual o item entrou; com vínculo persistido,
  resolvem uma única decisão sobre todos os aliases da pessoa/unidade;
- no handoff, a identidade primária do item continua sendo o user ID com que foi
  enfileirado, mas ordem, turno e proteção consultam o conjunto comprovado para
  impedir ultrapassagem por um item contemporâneo do alias WA ID;
- flood mantém uma única janela lógica por sujeito oficialmente comprovado e
  unidade, soma os contadores de user ID e WA ID, promove novos incrementos para
  o WA ID canônico e deduplica cada evento pelo WAMID;
- depois do commit do vínculo, eventos ainda válidos de user ID e WA ID compõem
  juntos o limite de 15; antes do commit não se presume equivalência;
- a mesma sequência sem vínculo oficial mantém contadores separados;
- contato manual, contato ambíguo, unidade diferente e identidades de pessoas
  distintas não criam equivalência;
- conflito ou indisponibilidade da prova persistida devolve HTTP 503 somente
  quando a falha é transitória e não bloqueia o cliente na Meta;
- WAMID continua idempotente.

### 15.2 Banco e snapshots

- todas as colunas finais existem com os nomes exatos;
- `unidade.nome` não existe e `nome_unidade VARCHAR(300)`,
  `nome_agente VARCHAR(100)` e `genero VARCHAR(9)` permanecem `NOT NULL`, sem
  default e com as quatro constraints canônicas da V1.0.7 validadas;
- `nome_unidade` e `nome_agente` rejeitam valores sem caractere não branco,
  `nome_unidade` permanece único e `genero` rejeita qualquer valor diferente de
  `masculino`/`feminino`;
- a migração de `user_id` preserva os valores de apresentação existentes e não
  tenta recriar, renomear ou repovoar essas três colunas;
- colunas individuais de snapshot aceitam `NULL`;
- `unidade.id_portfolio` e as três colunas de negócio de `user_id_cliente`
  rejeitam `NULL`; `id_portfolio` e `user_id` também rejeitam vazio;
- `user_id_cliente` possui exatamente duas FKs, com `PROTECT/RESTRICT` para
  cliente e `CASCADE` para unidade;
- `user_id_cliente` rejeita dois clientes para `(user_id, unidade)` e rejeita
  dois user IDs atuais para `(cliente, unidade)`;
- registros operacionais rejeitam ausência simultânea de WA ID e user ID;
- username novo atualiza o valor canônico mutável em `cliente.username`; os
  snapshots seguem a política histórica desta seção;
- reconciliação preenche somente `conversa.wa_id`/`conversa.user_id` que estejam
  `NULL`; `conversa.username` é o snapshot imutável da criação, inclusive quando
  nasceu `NULL`;
- payload normal com WA ID + user ID registra imediatamente o vínculo e pode
  preencher apenas aliases nulos da conversa; não atualiza fila, histórico,
  flood nem username da conversa;
- fila, histórico e flood nunca sofrem backfill; seus snapshots permanecem os
  do evento original;
- ausência posterior de username preserva o canônico;
- todo username posterior não vazio sobrescreve `cliente.username`;
- no merge, username não vazio do evento atual vence; se ele faltar, o valor não
  vazio do provisório é copiado antes da exclusão; somente então o canônico
  anterior é preservado;
- no merge, o nome capturado no provisório sempre sobrescreve `cliente.nome` do
  canônico, mesmo quando o canônico já tinha nome;
- não existe coluna física `wa_id_compartilhado` nem deadline no banco: o papel
  do candidato é derivado do item oficial e não cria vínculo antes do gate;
- pai e partições do histórico permanecem alinhados.

### 15.3 Turno, retry e atomicidade

- `(WA, phone A)` não mistura com `(WA, phone B)`;
- `(user ID, phone A)` não mistura com `(user ID, phone B)`;
- a mesma string usada uma vez como WA ID e outra como user ID não colide por
  causa do namespace tipado;
- o mesmo user ID em unidades diferentes não colide em cache, turno, flood nem
  autocura;
- identidades tipadas diferentes só compartilham a janela anti-flood quando uma
  prova oficial as vincula ao mesmo cliente e à mesma unidade; coincidência de
  texto, username, nome ou horário nunca produz essa união;
- primeiro evento somente-user cria cliente provisório + vínculo + conversa no
  mesmo commit;
- segundo evento somente-user reutiliza o provisório e não duplica cliente;
- cliente canônico que já possui user ID antigo na unidade troca para o novo
  user ID oficialmente provado sem violar nenhuma das duas unicidades;
- evento de contato reencontra primeiro a conversa pelo vínculo, preserva o
  turno e promove WA ID;
- cada falha do gate de `contact_request` — phone ID, unidade, etapa 2, tipo,
  origem, user ID, cardinalidade do contato ou consistência dos aliases — ocorre
  antes da primeira mutação de identidade; contradição causa rollback fail-closed;
- a primeira prova WA/user consulta, depois do gate e antes da mutação, qualquer
  predecessor aberto dos dois aliases na unidade; predecessor existente causa
  rollback e requeue de 5 segundos sem consumir retry;
- WA ID novo completa o provisório idempotentemente;
- WA ID do cliente canônico reatribui a conversa nova, preservando seu
  `id_conversa`, etapa, fila e histórico;
- conversa canônica antiga ativa é encerrada antes da reatribuição com
  `ativou_privacidade`; lock fresco impede o merge e uma posse stale somente é
  limpa sob row lock após incrementar `lock_version`, sem
  violar `idx_conversa_unica_ativa`;
- conversa canônica já encerrada e ainda bloqueada conserva seu `finalizou_em` e
  expiração originais; a conversa nova é encerrada com
  `bloqueio_reconciliado`, sem sender e sem criar/reiniciar prazo;
- no resultado terminal, a fila atual é excluída na mesma transação do merge; o
  commit pós-validação confirma tudo, o cache recebe os aliases comprovados —
  com o TTL restante da expiração original no bloqueio de 30 dias — e o ciclo
  não cria histórico nem chama lock normal,
  `bot_resposta_atual()`, resolver ou sender;
- a busca de bloqueio considera qualquer conversa canônica/alias cuja etapa
  tenha `bloqueio_dias > 0`, escolhe a maior expiração original e não é enganada
  pela conversa nova mais recente fechada com `bloqueio_reconciliado`;
- conversa canônica com bloqueio expirado não bloqueia a conversa nova;
- o nome capturado no provisório sempre sobrescreve o nome canônico antes da
  exclusão do provisório;
- conversa adicional inesperada do provisório impede `DELETE`, não é reatribuída
  por aproximação;
- cliente provisório só é excluído depois de `NOT EXISTS` explícito para
  `conversa`, `dependente`, `cliente_bloqueado_meta` e `user_id_cliente`;
- uma referência remanescente em qualquer uma dessas quatro tabelas impede o
  `DELETE`, sem acionar `CASCADE` nem `SET NULL`;
- conflito real entre WA IDs não nulos diferentes não funde clientes;
- testes A/B/C passam sem mudança de verdade;
- no caminho normal, a ordem de commits/rollbacks é idêntica; contenção usa o
  rollback já existente e terminação usa o commit pós-validação já existente;
- `bot_resposta_atual()` permanece no mesmo ponto;
- reagendamentos mantêm 30 s, 5 s, 300 s e 2 min conforme o ramo atual;
- retry reconstrói WA ID/user ID/username do banco;
- no retry do mesmo `contact_request`, `identidade_do_item` continua sendo o
  user ID original mesmo depois de o candidato já persistido em
  `fila_mensagens.wa_id` ter sido comprovado; a fila não é atualizada;
- `identidade_do_item` não muda depois de `validar_banco_mensagem()`;
- cache hit de cliente ainda executa a projeção final das identidades no banco;
- reparo de cache stale remove somente `referencia_cache_cliente`, sem remover a
  chave WA ou a chave de user ID de outra unidade;
- falha de FK dentro de `validar_banco_mensagem()` antes de existir
  `contexto_banco` ainda encontra no `estado_ciclo` a referência tipada montada
  antes da validação;
- reconciliação aponta a chave user ID usada para o cliente canônico somente no
  ponto de confirmação posterior ao commit já existente;
- ausência de qualquer chave do contrato bancário falha sem usar o snapshot da
  fila como substituto;
- falha em cada ponto anterior ao commit desfaz toda a reconciliação;
- retry posterior ao commit reencontra o cliente canônico e a mesma conversa;
- `contexto_historico` recebe os três snapshots do banco em envio normal e retry;
- `contexto_envio` não ganha quarto snapshot de WA compartilhado;
- `contexto_envio` preserva os mesmos campos tanto em envio novo quanto no
  retorno idempotente;
- a anexação dos snapshots ocorre antes do retorno antecipado de resposta já
  registrada em `flow_sender()`;
- advisory locks de todos os aliases comprovados são adquiridos na mesma ordem
  determinística em webhook/turno/bloqueio, sem duas decisões concorrentes;
- merge que encontra lock ainda não elegível pelo limiar de 110 segundos não
  altera nenhuma conversa, compensa a tentativa e usa somente o requeue
  controlado de 5 s;
- lock com `processing_started_at < NOW() - INTERVAL '110.0 seconds'` pode sofrer
  stale takeover, sempre incrementando `lock_version`;
- um `unlock` atrasado com a versão anterior não limpa a posse criada depois do
  stale takeover; o teste não presume CAS em todas as escritas pós-lock;
- o único requeue acrescentado é o resultado controlado de lock fresco no merge;
- o único encerramento antecipado acrescentado é o resultado terminal
  `bloqueio_reconciliado`, que usa o commit pós-validação já existente;
- nenhuma mensagem é marcada `sent` antes do ponto atual;
- a ordem interna de `atualizar_banco_com_contexto_final()` permanece histórico
  do bot -> movimento -> turnos sem avanço -> efeitos da transição -> intenção
  de encerramento.

### 15.4 Etapa especial

- no primeiro contato da etapa 1, os ramos padrão, mídia, financeiro e reforço
  escolar usam `nome_unidade`, `nome_agente` e o artigo coerente com `genero`;
- a matriz dos quatro ramos é testada com `masculino` e `feminino`, tanto quando
  o destinatário escalar é WA ID quanto no fallback autorizado para user ID;
- campos editoriais ausentes ou gênero fora do domínio falham antes de chamar a
  Meta, sem fallback para nome hardcoded;
- tratamentos posteriores da etapa 1 não repetem a apresentação inicial;
- WA ID acumulado, inclusive via `user_id_cliente`, pula 1 -> 3;
- somente user ID desconhecido e sem WA acumulado leva 1 -> 2;
- 1 -> 2 e 1 -> 3 usam o mesmo efeito por `id_cliente`, nunca por telefone; a
  reexecução em retry é idempotente e mantém o mesmo nome/resultado;
- o helper de nome registra e valida evento/destino efetivos nas duas arestas,
  sem constante ou mensagem de log hardcoded em 1 -> 2;
- etapa 2 envia `request_contact_info` ao user ID obtido do banco por meio do
  contexto;
- texto, mídia, financeiro e contato manual não avançam;
- dúvida sobre reforço escolar também não avança e tem prioridade sobre o
  financeiro quando os dois classificadores reconhecerem a frase;
- não existe recusa nem confirmação posterior;
- `contact_request` válido fornece WA ID e leva 2 -> 3;
- o efeito final reconhece explicitamente 2 -> 3 sem repetir a
  promoção/reconciliação de identidade;
- tratamentos da etapa 2 não carregam evento e não avançam;
- o sender de “Para quem é o atendimento?” usa o novo WA ID persistido e lido do
  banco, nunca o valor bruto recebido diretamente do payload;
- os resolvers dos envios da etapa 1 e do pedido/repetição da etapa 2 permitem
  explicitamente fallback para user ID quando WA ID ainda não existe;
- `contato_oficial_compartilhado` sem WA ID bancário falha antes de enviar a
  etapa 3;
- etapa 3 em diante sem WA ID falha antes de chamar a Meta;
- username nunca é usado no campo `to`;
- nenhuma conversa sem WA ID chega à etapa 19.

### 15.5 Confirmação, tratamentos e triagem preservados

- a futura etapa 4 aceita somente botão ou texto normalizado `Sim`/`Não`;
- `Sim` mantém o destino escolhido na etapa 3 e `Não` persiste o oposto;
- qualquer outra frase que não tenha sido classificada antes como reforço
  escolar ou financeiro, inclusive tentativas de linguagem natural, repete a
  confirmação como tratamento de contexto;
- titular e dependente produzem `destino_atendimento_confirmado` e sempre seguem
  da confirmação 4 para a profissão 5; somente a profissão bifurca dependente
  para 6 ou titular para 7;
- retry da confirmação exige `status_dependente` booleano persistido, reconstrói
  dele o valor final absoluto e nunca reaplica uma inversão; valor ausente ou de
  outro tipo falha de forma fechada;
- trocar para dependente cria o placeholder necessário de forma idempotente e
  trocar para titular remove somente o placeholder da conversa;
- em etapas com financeiro, a prioridade permanece mídia -> reforço escolar ->
  financeiro -> contexto/regra específica;
- a profissão futura 5 não classifica como dúvida escolar uma declaração
  profissional inequívoca com banca, cursinho, supletivo ou reforço;
- as oito respostas completas fora de contexto já observadas repetem a futura
  etapa 5 sem evento nem persistência, enquanto controles legítimos que contêm
  termos como `áudio`, `ligação`, `filho`, `filha` ou `autista` continuam
  aceitos;
- mensagens de tratamento reapresentam a etapa com texto neutro, sem repetir
  aberturas de confirmação ou avanço;
- o catálogo de perguntas usa as futuras etapas 13..18 e seleciona corretamente
  titular adulto, dependente infantil ou dependente adulto;
- a pergunta reconstruída no retry é a mesma variante etária, relida do banco;
- a migração preserva as seis respostas existentes e desloca seus IDs atuais
  12..17 para 13..18 sem colisão.
- a futura etapa 7 preserva a precedência idade 100+ e só encaminha titular de
  60–99 quando `suporte_idoso=TRUE`; dependente nunca entra nessa exceção;
- o encaminhamento persiste a idade, encerra com
  `encaminhado_suporte_idoso`, não bloqueia por 30 dias, não envia ao Funil e o
  retry reconstrói a decisão pela resposta persistida;
- a futura etapa 8 continua aceitando “quero” e variações curtas, mas rejeita
  pedidos informativos como “quero mais informações” antes do padrão positivo;
- a futura etapa 11 aplica a matriz de e-mail efetivamente obrigatório, mantém
  mídia/reforço/financeiro prioritários, grava e-mail válido ou `NULL` de forma
  absoluta e não reavalia a configuração da unidade no retry.

### 15.6 Arquitetura

- `core/repositories/fluxo/contextos/etapa1.py` lê e valida os três campos de
  apresentação somente pelo `id_unidade`, e `valida_historico()` só o chama no
  primeiro contato (`id_etapa_atual is None`);
- dados de apresentação não entram em identidade, turno, lock, fila, cache,
  anti-flood, reconciliação ou escolha de destinatário;
- `etapa2_messages.py` contém o texto/builder e não chama Meta nem banco;
- o sender da etapa 2 usa o builder, realiza somente I/O Meta e não escolhe
  evento ou destino;
- o validador da etapa 2 reconhece o contexto oficial antes do validador
  universal de mídia, sem enviar ou consultar banco;
- o resolver produz o evento, consulta o mapa, resolve o destinatário, chama o
  sender e anexa a transição, sem SQL/commit;
- `flow_sender()` roteia resolvers 1..22, não possui resolver 23 e acrescenta os
  snapshots também no retorno idempotente;
- nenhum arquivo de `messages`, sender, validador ou resolver executa SQL ou
  `commit`, e nenhum sender escolhe evento;
- `validar_banco_mensagem()` é o único dono da promoção/reconciliação anterior
  ao sender; `atualizar_banco_com_contexto_final()` ->
  `atualizar_banco_conforme_transicao_de_etapa()` são os donos do movimento e
  dos efeitos finais.

### 15.7 Funil, bloqueio e Admin

- funil recusa lead sem WA ID;
- funil inclui `@username` somente quando existir;
- user ID nunca aparece no funil;
- username ausente não impede um lead que possua WA ID;
- o snapshot do username vem de `conversa.username`, nunca de
  `cliente.username`;
- `alice` e `@alice` são exibidos como exatamente `@alice`, e ausência não cria
  linha vazia nas observações;
- quando presente, username aparece junto ao contato e antes da triagem;
- a etapa 18 futura ainda não é elegível; exatamente 19..23 são elegíveis;
- o Funil consulta exatamente as respostas das futuras etapas 13..18;
- as seis perguntas e respostas aparecem completas e em ordem nas observações;
- os textos reconstruídos no Funil são idênticos aos do catálogo usado pelo
  WhatsApp para a mesma faixa etária;
- os 12 textos canônicos de pergunta permanecem intactos; somente suas chaves
  mudam de 12..17 para 13..18;
- o resumo quantitativo antigo por quantidade de alternativas não reaparece;
- o e-mail do lead vem da resposta histórica da futura etapa 11 vinculada à
  resposta `bot/sent` da etapa 12; e-mail válido preenche contato/observações,
  ausência explícita vira “não tem” e outra resposta opcional vira “não
  informado”, sem usar um cadastro global mais novo;
- reconciliação não move nem altera `funil_envios` e não cria regra concorrente
  nova no `worker_funil`;
- denylist, bloqueio temporário, bloqueio por dias e bloqueio Meta reconhecem
  qualquer alias comprovado da pessoa/unidade; WA ID e user ID não são consultas
  alternativas independentes nem uma cadeia de prioridade/fallback;
- `cliente_bloqueado_meta` rejeita uma linha sem WA ID e sem user ID;
- evento de bloqueio com WA ID + user ID grava ambos na mesma linha canônica da
  unidade e tenta bloquear ambos na Meta;
- linha criada só com WA ID ou só com user ID recebe o alias faltante somente
  após prova oficial e apenas se a coluna estiver `NULL`;
- duas linhas anteriormente separadas, mas depois provadas como a mesma
  pessoa/unidade, são consolidadas sem perder o bloqueio; aliases não nulos
  divergentes falham de forma fechada;
- envelope cujo user ID contradiz o vínculo persistido do WA ID não enriquece a
  denylist e não chama bloqueio Meta;
- o mesmo WA ID em unidades diferentes permanece em linhas distintas, cada uma
  com o user ID específico daquela unidade;
- bloqueio Meta descoberto durante o handoff fecha a conversa nova, remove a
  fila atual e não chama sender;
- promoção ao bloqueio Meta tenta todos os aliases conhecidos e conserva a
  proteção local em falha parcial;
- exclusão Admin preserva a ordem Meta -> banco, tenta todos os aliases e somente
  remove o registro local após sucesso integral; antes da remoção, transfere a
  prova WA/user coerente para `user_id_cliente` quando existir cliente canônico;
  falha parcial ou conflito preserva a linha;
- models/Admin não quebram com WA ID nulo;
- unidade exige e exibe `nome_unidade`, `nome_agente`, `genero`, `id_portfolio`,
  `suporte_idoso` e `email_obrigatorio`, usa `id_unidade__nome_unidade` nas
  relações, oferece os filtros aprovados e valida o número comercial pelo helper
  compartilhado quando o suporte é ativado;
- Admin de `user_id_cliente` é somente leitura.

### 15.8 Saudação de retorno

- exatamente três horas entre o último histórico `sent` do bot e o timestamp do
  evento atual habilitam `Olá novamente, {nome}!`; duas horas, 59 minutos e 59
  segundos não habilitam;
- uma resposta válida depois do limiar mantém o mesmo evento, destino,
  componentes e uma única chamada Meta, apenas com o prefixo no corpo normal;
- uma entrada inválida depois do limiar mantém o mesmo tratamento e repete a
  mesma etapa, também em uma única chamada e uma única linha de histórico;
- etapa 1 ainda não concluída, nome ausente ou a própria mensagem que informa o
  nome nunca recebem a saudação;
- a fonte é o último histórico do bot com `status_envio='sent'` na mesma
  `id_conversa`; mensagem do cliente, envio do bot não `sent` e conversa do
  mesmo cliente em outra unidade não contaminam o cálculo;
- o teste usa o timestamp do evento, não `NOW()` nem o momento do processamento,
  e cobre item enfileirado com atraso superior a três horas sem falso positivo;
- retry que já encontra resposta do bot sai antes da consulta/composição e não
  chama sender nem cria novo histórico;
- ausência de histórico elegível ou timestamp ausente/inválido/invertido
  conserva integralmente a resposta sem prefixo; falha SQL propaga para o
  rollback e o retry normais do worker;
- quando elegível, transporte e histórico recebem o mesmo prefixo uma única
  vez, preservando o corpo canônico que cada sender já enviava/persistia; não
  há linha de histórico própria para a saudação;
- a cobertura confirma que nenhum DDL, índice, etapa, evento, transição, commit,
  rollback, retry, lock ou contador novo foi introduzido.

## 16. Sequência de deploy futura

1. congelar e commitar a baseline definitiva derivada da V1.0.7 atualizada
   `2bc4188`, preservando profissão, suporte/e-mail, saudação de retorno de três
   horas, proteção contextual da oferta e o texto/CTA atual da introdução da
   triagem;
2. regenerar o apêndice de código completo deste plano;
3. implementar em branch separada;
4. executar testes unitários e de integração;
5. capturar payloads reais em ambiente de teste;
6. validar PyWa/Graph v26.0;
7. gerar e revisar o SQL final;
8. aplicar e validar código, dependências e SQL em ambiente dev controlado;
9. promover para produção somente o mesmo artefato aprovado em dev;
10. garantir fila, conversa processing e funil sem trabalho aberto;
11. parar webhook, flow worker e funil worker;
12. atualizar código e o virtualenv pelo `requirements.txt` versionado;
13. executar SQL e checks de produção;
14. subir webhook e executar smoke;
15. subir flow worker e funil worker;
16. verificar logs, fila, transições e funil.

## 17. Gates finais

O plano só poderá ser aplicado se:

- não existir `telefone_informado` nem `username_informado`;
- os nomes das colunas forem exatamente os da seção 5;
- não existir `unidade.nome`, e `nome_unidade`, `nome_agente` e `genero`
  corresponderem exatamente aos tipos, à nulabilidade, aos dados e às quatro
  constraints da baseline V1.0.7 atualizada `2bc4188`;
- `id_portfolio` estiver escrito corretamente, obrigatório e preenchido em toda
  unidade;
- `suporte_idoso` e `email_obrigatorio` permanecerem `BOOLEAN NOT NULL` com
  defaults `FALSE` e `TRUE`, respectivamente, sem alteração dos valores por
  unidade durante a migração;
- `user_id_cliente` possuir PK técnica, duas unicidades, FKs e CHECK definidos
  neste plano;
- WA ID explícito nunca sofrer alteração de dígitos;
- `metadata.phone_number_id` for obrigatório e resolver uma única unidade antes
  de enfileirar; `display_phone_number` não for fallback nem `sender`;
- ausência estrutural de identidade ou `phone_number_id` responder HTTP 200 sem
  fila, e HTTP 503 ficar restrito a falhas transitórias de processamento;
- `phones[].phone` nunca for fallback de `contact_request`; somente um
  `phones[].wa_id` explícito ASCII de 10 a 15 dígitos puder provar o handoff;
- `wa_id_remetente`, `wa_id_compartilhado` e `wa_id_canonico` permanecerem
  separados até a validação bancária;
- o validador da etapa 2 receber `wa_id_compartilhado` separado e nunca usar o
  WA ID canônico como prova da origem do payload;
- username nunca for identidade técnica;
- WA ID for obrigatório para chegar ao funil;
- somente a etapa especial 2 for adicionada sobre a baseline V1.0.7;
- catálogo tiver 23 etapas e mapa 27 transições;
- somente etapa 23 encerrar e bloquear por 30 dias; o encerramento especial
  `encaminhado_suporte_idoso` na futura etapa 7 permanece sem bloqueio;
- etapa 23 não tiver resolver;
- a confirmação futura 4 continuar aceitando exclusivamente `Sim`/`Não` e
  persistir o valor final absoluto de forma idempotente, sempre avançar para a
  profissão futura 5 e exigir `status_dependente` booleano no replay;
- a profissão futura 5 conservar seus validadores contextuais para não barrar
  vínculos profissionais inequívocos com serviços escolares, rejeitar somente
  as oito respostas completas fora de contexto após normalização, sem filtro
  por palavra isolada, e ser a única etapa que bifurca dependente para 6 ou
  titular para 7;
- titular de 60–99 anos na futura etapa 7 respeitar `suporte_idoso`, idade 100+
  manter precedência, dependente permanecer fora da exceção e o CTA terminal
  persistir idade sem Funil ou bloqueio;
- a oferta futura 8 preservar o aceite curto sem confundir pedidos de
  informação com confirmação;
- a coleta futura 11 preservar a matriz de e-mail opcional/obrigatório, a
  prioridade dos tratamentos e a escrita absoluta de `cliente.email`;
- contato oficial válido ser reconhecido antes dos tratamentos da etapa 2 e,
  nas entradas comuns, a prioridade permanecer mídia -> reforço -> financeiro
  -> contexto;
- toda retomada de tratamento ser semanticamente neutra e preservar os
  componentes da etapa;
- o catálogo compartilhado de triagem usar 13..18 e manter as variantes por
  idade e pessoa atendida;
- o Funil exibir as seis perguntas/respostas ordenadas, nunca o resumo por
  quantidade, acrescentar username apenas quando existir e representar o e-mail
  histórico da conversa sem consultar um valor global posterior;
- nenhum sender usar username;
- nenhum sender usar user ID quando WA ID lido do banco existir;
- somente os resolvers dos envios da etapa 1 e do pedido/repetição de
  compartilhamento da etapa 2 habilitarem explicitamente o fallback para user
  ID e passarem o escalar ao sender;
- os quatro ramos iniciais da etapa 1 preservarem a apresentação dinâmica por
  unidade e mantiverem essa decisão independente do escalar WA ID/user ID;
- retomadas posteriores da etapa 1 não repetirem a abertura, e ausência ou
  invalidade dos três campos editoriais falhar de forma fechada antes do envio;
- a resposta `contato_oficial_compartilhado` e a etapa 3 em diante exigirem WA
  ID antes de chamar a Meta;
- `contexto_historico` receber os identificadores do banco e
  `contexto_envio` refletir os mesmos snapshots em todos os caminhos;
- a projeção bancária final ocorrer mesmo em cache hit e não possuir fallback
  silencioso para fila ou payload;
- o item de handoff conservar sua identidade primária tipada, enquanto turno e
  ordem produzem uma única decisão alias-aware sobre o conjunto comprovado;
- `identidade_do_item` permanecer tipada e imutável durante turno, logs, retry,
  finalização e autocura do item;
- cache por WA ID conservar escopo global e cache por user ID incluir tipo e
  unidade, com a autocura removendo somente a referência efetivamente usada;
- evento inbound somente-user-ID continuar processável depois da etapa 2, mas
  nenhum envio dessa etapa em diante ocorrer sem WA ID canônico do banco;
- primeiro evento somente-user criar vínculo antes da conversa seguinte;
- payload conjunto criar/atualizar vínculo imediatamente;
- troca oficialmente provada de user ID na mesma unidade consolidar primeiro a
  linha provisória e manter uma única linha canônica;
- o gate completo de `contact_request` validar phone ID/unidade, vínculo user,
  conversa ativa na etapa 2, tipo, origem oficial, candidato único e ausência de
  contradição antes de qualquer mutação de identidade;
- aliases serem representados como conjunto por `(id_cliente, id_unidade)`, sem
  chave concatenada obrigatória e sem exigir user ID de cliente legacy;
- conversa canônica ativa ser encerrada com `ativou_privacidade` antes de
  reatribuir a nova;
- conversa canônica encerrada mas ainda bloqueada conservar `finalizou_em` e a
  expiração originais, enquanto a conversa nova fecha com
  `bloqueio_reconciliado`, sem sender nem reinício do prazo;
- a proteção por dias consultar a maior expiração ainda vigente entre as
  conversas bloqueantes do conjunto, em vez de assumir que a conversa encerrada
  mais recente é a fonte do prazo;
- o nome capturado no provisório sempre sobrescrever o nome canônico, e somente
  `cliente.username` aceitar o último username não vazio, usando no merge a
  precedência evento atual -> provisório -> canônico anterior;
- fila, histórico, flood e `conversa.username` permanecerem snapshots imutáveis;
  apenas aliases `NULL` da conversa podem ser preenchidos após prova;
- nenhuma exclusão de provisório depender de `ON DELETE CASCADE` ou
  `ON DELETE SET NULL`, e os quatro gates explícitos de `conversa`, `dependente`,
  `cliente_bloqueado_meta` e `user_id_cliente` retornarem zero;
- reconciliação não alterar `funil_envios`, não criar bypass de bloqueio e
  consolidar eventual linha de bloqueio provisória na canônica sem desbloquear;
- denylist, bloqueio temporário, bloqueio por dias, bloqueio Meta e Admin
  reconhecerem todos os aliases comprovados da unidade;
- `cliente_bloqueado_meta` exigir ao menos um alias, manter uma linha canônica
  por pessoa/unidade após a prova, preencher somente alias `NULL`, consolidar
  equivalentes e manter unidades diferentes em linhas separadas;
- bloqueio/desbloqueio Meta operar sobre todos os aliases conhecidos; o Admin
  só excluir localmente depois do desbloqueio integral Meta-first;
- existirem somente os dois resultados controlados do merge: lock fresco causa
  rollback, requeue sem erro de 5 s e compensação da tentativa, sem mutação;
  bloqueio vigente fecha a conversa, exclui a fila atual na mesma transação, usa
  o commit pós-validação e interrompe o ciclo antes de histórico, lock normal,
  `bot_resposta_atual()` e sender;
- `lock_conversa()` preservar o predicado exato da V1.0.7: lock fresco enquanto
  `processing_started_at >= NOW() - INTERVAL '110.0 seconds'` e stale takeover
  somente com `<`, incrementando `lock_version`; `unlock_conversa()` exige o
  token;
- o merge nunca limpar posse fresca e um `unlock` atrasado com versão anterior
  não liberar a posse criada depois do takeover stale, sem exigir nesta feature
  a conversão de toda escrita pós-lock em CAS;
- `dequeue_message()` mantiver seu CTE, ordem, `SKIP LOCKED` e retry, com seu
  limiar próprio de 2 minutos, enquanto `lock_conversa()` preservar literalmente
  o limiar de 110 segundos da V1.0.7;
- no caminho normal, commits, rollbacks, retries, locks, turnos e autocura
  permanecerem nos mesmos pontos; os dois ramos controlados reutilizarem o
  rollback/commit da validação, sem nova fronteira transacional;
- `atualizar_banco_com_contexto_final()` preservar sua ordem interna atual e
  continuar chamando `atualizar_banco_conforme_transicao_de_etapa()` como único
  dono dos efeitos finais;
- 1 -> 2 e 1 -> 3 reutilizarem o mesmo efeito de persistência do nome por
  `id_cliente`, usando evento/destino efetivos e resultado idempotente, e 2 -> 3
  reconhecer o evento sem duplicar a reconciliação;
- mensagens, senders, validadores, resolvers e `flow_sender()` respeitarem as
  fronteiras da seção 7.5, sem SQL/commit fora das camadas transacionais;
- `bot_resposta_atual()` e reagendamentos permanecerem intocados;
- a saudação de retorno consultar somente o último histórico `sent` do bot na
  mesma `id_conversa`, comparar com o timestamp do evento atual e usar limiar
  inclusivo de três horas;
- a própria mensagem que persiste o nome permanecer inelegível, e ausência de
  nome ou etapa 1 ainda não concluída apenas omitirem o prefixo sem bloquear a
  resposta, enquanto falha SQL conserva rollback e retry normais;
- avanço válido e tratamento inválido conservarem uma única resposta, chamada
  Meta e linha de histórico, com o retorno idempotente encerrado antes da
  consulta/composição da saudação;
- a saudação não exigir coluna, índice, migração, etapa, transição ou fronteira
  transacional nova;
- a espera de fila vazia permanecer em 1,5 segundo;
- testes com os quatro fixtures e payloads reais, a matriz de suporte/e-mail e
  a proteção da oferta passarem;
- SQL de migração não apagar clientes, conversas, fila ou histórico;
- em runtime, somente cliente estritamente provisório e sem referências ser
  excluído depois da reatribuição canônica comprovada.

## 18. Riscos residuais documentados

1. Os fixtures ainda não provam o formato exato que chegará em produção.
2. Um mesmo usuário privado pode gerar um provisório em cada unidade ainda não
   vinculada até fornecer WA ID; após a prova, `user_id_cliente` impede repetição
   naquela unidade. Username não pode ser usado para uni-los.
3. Alternância anômala entre um evento somente-WA e outro somente-user-ID sem
   payload conjunto, vínculo já salvo ou `contact_request` não pode ser
   reconciliada por aproximação.
4. A janela já conhecida Meta -> banco continua existindo: envio confirmado e
   queda antes da persistência pode duplicar resposta em retry. Esta feature não
   amplia nem resolve esse problema.
5. Uma falha durante a promoção user ID -> WA ID segue rollback/retry/autocura
   atuais. A idempotência do vínculo evita repetir efeitos após o commit.
6. Um conflito realmente contraditório — user ID já ligado a um cliente com WA
   ID não nulo diferente do WA oficial atual — não é fundido automaticamente e
   exige investigação. Esse caso é diferente do provisório com WA ID nulo.
7. Dois `flow_worker` podem alcançar a mesma conversa. Esse risco operacional
   permanece permitido. Esta feature fecha a brecha nova do merge: respeita lock
   fresco, incrementa a versão no stale takeover e impede que um `unlock` tardio
   com a versão antiga solte a posse nova. Ela não redesenha todas as escritas
   pós-lock nem cancela chamada externa já iniciada; esta última continua coberta
   pela janela Meta -> banco do item 4.

O antigo reset da janela anti-flood na promoção `user_id` -> `wa_id` não é mais
um risco aceito. A implementação prática deve somar as duas rajadas como uma só
depois que a associação estiver persistida; antes disso, a barreira de
predecessor impede a prova posterior de ultrapassar um item anterior do outro
alias sem publicar identidade provisória no webhook.

## 19. Veredito

Com estes limites, `user_id` entra como identidade lógica temporária quando o WA
ID está ausente e como alias canônico escopado por cliente/unidade. Ele pode ser
fallback de destinatário somente nos envios explicitamente autorizados das
etapas iniciais. No transporte inbound, continua aceito em qualquer etapa quando
for o único identificador entregue pela Meta; o worker então exige o WA ID
canônico do banco antes de qualquer envio posterior. `cliente.username` guarda o
último valor não vazio, enquanto fila, histórico, flood e conversa preservam seus
snapshots; o Funil usa o snapshot imutável da conversa. WA ID continua sendo o
destinatário prioritário, torna-se obrigatório depois do compartilhamento e
permanece obrigatório para o Funil.

A lógica transacional central não é redesenhada: no caminho normal, pontos de
commit, rollback, retry, dequeue, turno, lock da conversa,
`bot_resposta_atual()` e `sent` continuam nos mesmos lugares. A reconciliação
executa os efeitos de dados aprovados usando a validação e o cursor já existentes.
Há somente duas ramificações delimitadas: lock fresco interrompe o merge antes
de mutação e usa rollback/requeue sem erro de 5 segundos; bloqueio vigente fecha
a conversa e remove sua fila na transação de validação, usa o commit já existente
e termina o ciclo sem histórico, lock normal ou sender. No stale takeover da
conversa, a janela de 110 segundos da V1.0.7 é mantida e `lock_version` é
incrementado antes de limpar a posse.

O anti-flood também preserva a continuidade de identidade: quando a prova
oficial demonstrar que `user_id` e `wa_id` pertencem ao mesmo cliente na mesma
unidade, as rajadas dos dois identificadores compõem uma única janela de 15
WAMIDs distintos em 5 segundos. A barreira de predecessor protege a troca
imediata anterior ao commit do worker sem publicar um vínculo prematuro; depois
dele, o vínculo persistido confirma a associação. WAMIDs repetidos contam uma
vez. Conflito determinístico recebe HTTP 200 sem mutação; ausência transitória da
fonte autoritativa gera reentrega por HTTP 503. Redis indisponível depois de o
RDS provar ausência de vínculo não invalida o alias unitário.

O desenho fecha o caso normal de privacidade sem permitir dois `id_cliente` para
a mesma pessoa depois da prova oficial. O handoff user ID -> WA ID, a conversa
canônica anterior, o transporte pelos contextos e o fallback limitado do sender
exigem os testes integrados listados antes de qualquer deploy.

A saudação de retorno também permanece aditiva: depois de três horas ou mais
desde o último envio `sent` do bot na mesma conversa, ela prefixa a resposta
normal usando o nome já persistido, sem criar segunda mensagem ou alterar o
fluxo. O timestamp do evento preserva a semântica diante de filas e retries; a
barreira idempotente continua anterior à feature, dados opcionais ausentes
apenas removem o prefixo e erros SQL mantêm o rollback/retry já existente.

O único risco funcional conhecido e deliberadamente aceito continua sendo a
janela rara entre o envio confirmado pela Meta e sua persistência final no banco,
na qual um retry pode duplicar a resposta externa. A continuidade anti-flood não
acrescenta um segundo risco aceito e elimina o reset de janela que a versão
anterior deste plano tolerava.

Sobre essa identidade nova, o comportamento funcional da baseline atual permanece
reconhecível: a apresentação inicial dinâmica por unidade é preservada nos
quatro ramos, enquanto confirmação binária, tratamentos atuais, triagem por
faixa etária, perguntas e respostas detalhadas no Funil e terminalidade de 30
dias são apenas renumerados, nunca redesenhados. As políticas já aprovadas de
suporte ao idoso, e-mail opcional/obrigatório, proteção da oferta, botão “Começar
triagem”, profissão e saudação de retorno atravessam a aplicação sem regressão.
