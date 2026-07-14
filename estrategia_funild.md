# Estrategia de integracao com o Funil de Vendas

## Objetivo deste documento

Este documento preserva as decisoes, descobertas e duvidas ainda abertas sobre
a integracao entre o chatbot e o Funil de Vendas. Ele nao e um plano de
implementacao e, por isso, nao contem o codigo completo dos arquivos.

O documento começou como estratégia. Em 13/07/2026, a criação periódica de
oportunidades foi implementada. As seções sobre atividades e reconciliação
autenticada continuam registrando evolução futura.

```text
etapas 16 e 17 elegíveis
-> funil_envios
-> claim com SKIP LOCKED e lease
-> uma oportunidade ApiCarrossel por conversa
-> validar JSON response=success
-> lead_no_funil=TRUE e funil_envios=sent
```

O worker permanece desativado por padrão até o teste manual dos campos da
unidade. Nenhuma atividade é criada nesta versão.

## Fontes analisadas

Foram analisados:

- `Supera - Guia migracao CRM4U para Funil de Vendas (1).pdf`;
- `Playbook- CRM (1).pdf`;
- planilhas de De-Para de oportunidades e contatos citadas no guia;
- documentacao oficial da API de entrada de dados;
- documentacao oficial de consulta de oportunidades;
- documentacao oficial de criacao e listagem de atividades;
- endpoints oficiais de referencias do Funil de Vendas.

Links tecnicos principais:

- Entrada de dados:
  <https://www.funildevendas.com.br/ajuda/api-entrada-de-dados/>
- Contrato de inclusao e edicao de oportunidades:
  <https://www.funildevendas.com.br/wp-content/uploads/2019/06/API-Insert_Edit.pdf>
- Consulta de oportunidades:
  <https://www.funildevendas.com.br/ajuda/api-consulta/>
- Criacao e consulta individual de atividades:
  <https://www.funildevendas.com.br/ajuda/api-de-atividades/>
- Listagem de atividades:
  <https://www.funildevendas.com.br/ajuda/api-listagem-de-atividades-usuarios/>
- Tipos de atividade:
  <https://www.funildevendas.com.br/ajuda/api-listagem-de-atividades-tipo/>

## Decisoes de negocio ja estabelecidas

### Elegibilidade

Uma conversa se torna elegivel para o Funil de Vendas ao chegar na etapa 16.

Isso significa:

```text
Etapa 15 -> ainda nao elegivel
Etapa 16 -> elegivel
Etapa 17 -> continua elegivel caso ainda nao tenha sido enviada
```

A etapa 17 mantem sua responsabilidade atual:

- finalizar a conversa;
- bloquear novas conversas entre aquele cliente e aquela unidade por 30 dias.

O envio ao Funil nao dependera de o cliente realmente ter concluido o
agendamento no Calendly. Ao chegar na etapa 16, ele ja demonstrou interesse
suficiente para ser tratado como oportunidade comercial.

### Objeto comercial criado

O lead deve entrar no CRM como uma oportunidade aberta na etapa `Leads`.

A API permite criar uma oportunidade sem atividade. O teste real com o
ApiCarrossel confirmou que a oportunidade entra em `Leads`, recebe o canal de
venda selecionado e ganha automaticamente o vendedor configurado pela unidade.
Nenhuma atividade e criada automaticamente.

O Playbook recomenda que uma oportunidade nao fique sem atividade, mas ainda
nao esta confirmado se o Supera autoriza a criacao automatizada desse objeto.
Por isso, o escopo confirmado da V1 e:

```text
1. criar a oportunidade;
2. confirmar a resposta do ApiCarrossel;
3. marcar o lead como enviado ao CRM.
```

Se o time do Supera confirmar a automacao de atividades, o fluxo sera ampliado
para localizar a oportunidade, obter seu codigo e criar a atividade inicial.
Essa ampliacao nao deve ser tratada como obrigatoria antes da confirmacao.

### Campos personalizados enviados

O teste e o modelo oficial do Supera confirmaram dois campos personalizados da
oportunidade:

```text
Observacoes
Origem do lead
```

No JSON, os titulos devem ser enviados com a grafia exata configurada no CRM:
o equivalente a `Observacoes`, com cedilha e tildes, e `Origem do lead`. O
primeiro recebe o resumo do atendimento; o segundo identifica o chatbot como
`Meta Chatbot`. Como a tela do CRM também possui campos nativos com nomes
semelhantes, o preenchimento visual deve ser confirmado no teste manual de cada
widget antes de ativar o worker.

### Ausencia de sincronizacao posterior

Na primeira versao, o chatbot fara uma entrega unica:

- cria a oportunidade;
- entrega os dados coletados;
- marca o envio como concluido.

Depois disso, o vendedor assume a responsabilidade por atualizar o CRM. Nao
sera criado webhook de retorno do Funil nesta fase.

Se a automacao de atividades for autorizada futuramente, ela sera adicionada
como uma segunda fase independente desta entrega inicial.

## Dados enviados

### Contato da oportunidade

- nome do cliente;
- telefone do cliente;
- email do cliente;
- idade do cliente, quando o atendimento for para ele proprio.

### Atendimento para dependente

- indicador de atendimento para dependente;
- nome do dependente;
- idade do dependente.

Quando o atendimento for para o proprio cliente, nenhum dependente sera
inventado ou enviado.

### Triagem cognitiva

As seis respostas ja estao registradas em `chatbot.respostas_desafios`. O
resumo deve contar os tres valores canonicos atualmente aceitos:

```text
nunca: X
as vezes: X
frequentemente: X
```

No texto apresentado ao usuario e ao vendedor, `as vezes` podera ser formatado
como `as vezes` com acento, sem alterar o valor canonico persistido.

### Identificacao deterministica

O titulo da oportunidade deve conter uma identificacao interna que nao muda:

```text
Chatbot Lead [C123]
```

`C123` representa `id_conversa = 123`. Essa identificacao permite localizar a
oportunidade depois de uma queda e evita depender apenas de nome ou telefone,
que podem se repetir.

Caso a automacao de atividade seja autorizada, ela tambem devera receber um
marcador deterministico em sua anotacao, por exemplo:

```text
[CHATBOT ATIVIDADE C123]
```

## Modelo de dados recomendado

### `integracao_funil_unidade`

As configuracoes do Funil nao devem ser espalhadas como varias colunas em
`chatbot.unidade`. Elas formam outro conceito e merecem uma tabela propria.

Relacao:

```text
unidade 1 ---- 0..1 integracao_funil_unidade
```

Uma unidade pode ainda nao ter a integracao configurada, mas nunca deve possuir
duas configuracoes ativas concorrentes.

Campos necessarios para a criacao de oportunidade pelo ApiCarrossel:

```text
id_integracao_funil
id_unidade UNIQUE
status_ativa
widget_api_carrossel
codigo_canal_venda
criado_em
atualizado_em
```

O ApiCarrossel resolve internamente vendedor, metodologia e etapa `Leads` a
partir do widget da unidade. O teste real nao exigiu login, senha nem
`IntegrationKey`.

Os campos abaixo ficam reservados somente para uma futura consulta autenticada
ou automacao de atividades, caso essa possibilidade seja aprovada:

```text
codigo_funil
usuario_email_api
usuario_segredo_api_criptografado
codigo_tipo_atividade
```

`IntegrationKey` e o segredo de autenticacao Basic nao devem aparecer em logs,
mensagens do Admin ou excecoes. O segredo nao deve ser armazenado em texto
aberto.

### `funil_envios`

Essa tabela representa o estado operacional de entrega de uma conversa ao CRM.

Relacao:

```text
conversa 1 ---- 0..1 funil_envios
```

Campos implementados:

```text
id_funil_envio
id_conversa UNIQUE
status
retry_count
next_attempt_at
processing_started_at
enviado_em
ultimo_erro
resposta_funil
criado_em
atualizado_em
```

Nao e necessario duplicar `id_unidade` em `funil_envios`:

```text
funil_envios
-> conversa
-> unidade
-> integracao_funil_unidade
```

Essa cadeia garante uma unica fonte para a relacao. A V1 guarda a resposta do
ApiCarrossel para auditoria, mas nao possui um codigo externo confiavel porque o
endpoint de inclusao nao o devolve. `codigo_oportunidade` e
`codigo_atividade` somente devem ser adicionados quando a consulta autenticada
e a automacao de atividades forem aprovadas.

O campo atual `conversa.lead_no_funil` pode continuar como resumo rapido:

```text
FALSE -> oportunidade ainda nao confirmada
TRUE  -> oportunidade confirmada no CRM
```

A tabela `funil_envios` guarda os detalhes necessarios para retry, auditoria e
recuperacao de estados intermediarios.

## Arquitetura implementada

```text
core/integrations/funil/
    cliente HTTP, autenticacao, payloads e interpretacao das respostas

core/repositories/funil/integracao.py
    configuracao da integracao do CRM por unidade

core/repositories/funil/leads.py
    fotografia completa do cliente, dependente e triagem

core/repositories/funil/envios.py
    materializacao, claim e atualizacoes transacionais da fila

workers/worker_funil/
    supervisor, ciclo horario e processamento isolado de cada lead
```

O `worker_flow` do atendimento nao deve receber chamadas ao CRM. Ele apenas
continua atualizando a etapa da conversa de forma transacional.

### Codigo compartilhado entre workers

Podem ser reaproveitados:

- configuracao central de logs;
- fabrica de conexoes PostgreSQL;
- utilitarios realmente genericos de retry, backoff e supervisao;
- mascaramento de valores sensiveis em logs.

Nao devem ser movidos para uma pasta comum apenas por parecerem semelhantes:

- regra de turno da conversa;
- lock especifico da conversa do WhatsApp;
- persistencia de resposta do bot;
- finalizacao da fila de mensagens;
- reparos de cache exclusivos do atendimento.

Esses componentes pertencem ao dominio do `worker_flow`. Compartilhar funcoes
especificas entre os dois workers aumentaria acoplamento e risco de regressao.

Se o plano identificar duplicacao real, podera ser criado algo como
`workers/comum/`, mas somente para primitivas sem regra de negocio.

## Processamento de um ciclo

O worker e um processo supervisionado que executa um ciclo e aguarda uma
hora antes do proximo. O intervalo sera configuravel, com padrao de 3.600
segundos.

Exemplo com tres leads elegiveis:

```text
Lead 1
-> claim exclusivo
-> criar oportunidade
-> validar resposta do ApiCarrossel
-> confirmar no banco

Lead 2
-> claim exclusivo
-> criar oportunidade
-> validar resposta do ApiCarrossel
-> confirmar no banco

Lead 3
-> claim exclusivo
-> criar oportunidade
-> validar resposta do ApiCarrossel
-> confirmar no banco
```

Embora a API de entrada aceite uma lista de oportunidades, nao devemos agrupar
varios leads no mesmo POST nesta versao. O processamento individual simplifica
a identificacao do erro e impede que uma resposta ambigua afete todo o lote.

Se o Lead 2 falhar:

```text
Lead 1 -> enviado
Lead 2 -> volta para retry, sem lead_no_funil = TRUE
Lead 3 -> continua sendo processado normalmente
```

Uma excecao de um lead nunca deve encerrar o ciclo inteiro.

## Transacoes e concorrencia

### Claim

O worker deve pegar cada pendencia com uma operacao equivalente a:

```text
FOR UPDATE SKIP LOCKED
```

e registrar `processing_started_at`. Isso impede duas instancias de trabalharem
na mesma conversa ao mesmo tempo.

### Lease de processamento

Se o processo morrer enquanto um envio estiver como `processing`, outro ciclo
devera considerar o claim abandonado depois de um timeout e torna-lo elegivel
novamente.

### Limite transacional

Uma transacao PostgreSQL nao consegue incluir atomicamente uma requisicao HTTP
feita para outro sistema. Portanto, nao existe um unico `commit` que confirme
Funil e PostgreSQL simultaneamente.

A protecao correta combina:

- estado persistido em `funil_envios`;
- identificadores deterministicos;
- consulta de reconciliacao no Funil, quando a API autenticada estiver
  disponivel;
- operacoes locais pequenas e idempotentes.

## O que significa reconciliacao

Reconciliacao e consultar a fonte externa para descobrir se uma operacao ja
aconteceu quando o banco local nao conseguiu registrar o resultado.

Exemplo futuro, depois de adicionar o codigo externo ao modelo:

```text
1. Funil cria a oportunidade C123 com sucesso.
2. O banco cai antes de confirmar o envio local.
3. funil_envios continua pendente ou processing.
4. No retry, o worker procura Chatbot Lead [C123] no Funil, se a consulta
   autenticada estiver disponivel.
5. Se encontrar, salva o codigo externo e reutiliza a oportunidade.
6. Nao cria outra oportunidade.
7. Confirma o envio local.
```

Se a atividade automatizada for autorizada posteriormente, surgira outro estado
parcial:

```text
1. Oportunidade foi criada e seu futuro codigo externo foi salvo.
2. Criacao da atividade falha.
3. O envio nao recebe lead_no_funil = TRUE.
4. No retry, o worker nao recria a oportunidade.
5. Ele tenta apenas localizar ou criar a atividade pendente.
```

Se a atividade for criada e o banco cair antes de salvar seu codigo, o marcador
`[CHATBOT ATIVIDADE C123]` permite procura-la na listagem antes de uma nova
criacao. A documentacao atual da listagem retorna `code_opportunity`, codigo da
atividade, anotacao e datas, mas nao documenta filtro direto por oportunidade;
o plano devera limitar a janela e paginar a busca com cuidado.

Sem consulta de reconciliacao, resta a janela classica:

```text
Funil confirmou
-> banco caiu
-> retry nao sabe que confirmou
-> risco de duplicidade
```

E por isso a consulta externa continua proposta como reforco de idempotencia.
Entretanto, a API publica documentada exige autenticacao Basic e o codigo do
funil para listar oportunidades. Sem essas informacoes, o titulo deterministico
reduz o trabalho de reconciliacao manual, mas nao elimina sozinho a janela de
duplicidade.

## Credenciais e codigos por unidade

### Criacao de oportunidade

O endpoint ApiCarrossel validado usa:

```text
widget da unidade
codigo_canal_venda
```

O portal do Supera gera uma URL com esses dois valores. O endpoint substitui os
marcadores de vendedor, metodologia, canal e etapa antes de inserir o lead. A
criacao testada funcionou sem login e senha da unidade.

### Consulta e atividade

A documentacao publica atual exige Basic Authentication, no formato
`email:senha`, para:

- consultar oportunidades;
- listar referencias;
- criar atividades;
- listar atividades.

Uma funcao manual de teste pode receber `titulo`, `codigo_funil`, `email_api` e
`senha_api`, consultar a listagem por titulo exato e devolver o campo `code`.
As credenciais nao devem ficar gravadas no arquivo.

Antes do plano final, deve ser confirmado com o suporte do Funil:

1. Existe usuario ou chave exclusiva para API, sem usar a senha humana?
2. A criacao de atividade aceita `IntegrationKey` em alguma modalidade?
3. A inclusao de oportunidade pode devolver seu codigo em outro endpoint ou
   configuracao?
4. Existe busca de atividade filtrada diretamente por codigo da oportunidade?
5. Quais valores representam atividade pendente/concluida no campo `status`?

O usuario nao deve enviar senhas reais pelo chat. As credenciais serao inseridas
diretamente no ambiente ou no Django Admin quando o mecanismo estiver definido.

## Respostas HTTP da API de oportunidade

A API de inclusao pode retornar HTTP 200 tanto para sucesso quanto para falha.
O cliente deve validar tambem o JSON:

```text
response = success -> operacao aceita
response = failure -> operacao rejeitada
```

Confiar apenas no status HTTP marcaria falhas como enviadas.

## Configuracoes globais no ambiente

Valores globais, sem segredo especifico de unidade:

```text
FUNIL_WORKER_ENABLED=False
FUNIL_INTERVALO_SEGUNDOS=3600
FUNIL_LIMITE_POR_CICLO=100
FUNIL_LEASE_SEGUNDOS=900
FUNIL_RETRY_LEAD_SEGUNDOS=3600
FUNIL_HTTP_CONNECT_TIMEOUT_SECONDS=10
FUNIL_HTTP_READ_TIMEOUT_SECONDS=30
```

Uma chave mestra de criptografia podera ser necessaria caso credenciais por
unidade sejam armazenadas criptografadas no PostgreSQL. Essa decisao depende da
resposta sobre credencial exclusiva de API.

## Pontos ainda pendentes

- confirmar com o Supera se atividades podem ser criadas automaticamente;
- confirmar o mecanismo seguro de autenticacao Basic, caso a resposta seja
  positiva;
- obter o codigo do funil da unidade para a consulta autenticada;
- confirmar codigos e status exigidos para a atividade inicial, se aprovada;
- decidir a data e o horario da atividade inicial, se aprovada;
- confirmar se o tipo de atividade sera `WHATSAPP`, se aprovada;
- validar no ambiente real a resposta da criacao de atividade;
- confirmar a estrategia de consulta da atividade para reconciliacao;
- validar manualmente se os campos personalizados `Observacoes` e
  `Origem do lead` aparecem nos campos visuais esperados de cada widget;
- somente ativar `FUNIL_WORKER_ENABLED` depois dessa validacao.

## Veredito atual

A arquitetura implementada atende aos requisitos de:

- elegibilidade desde a etapa 16;
- isolamento por unidade;
- uma oportunidade por conversa;
- processamento horario;
- continuidade do lote quando um lead falha;
- retry sem marcar falhas como enviadas;
- recuperacao de worker interrompido;
- protecao contra duplicidade em estados intermediarios;
- manutencao do `worker_flow` atual sem acoplar o atendimento ao CRM.

A criacao periodica de oportunidades via ApiCarrossel esta implementada e
desativada por padrao ate a validacao manual. A criacao de atividade e a
reconciliacao automatica pelo codigo externo permanecem como extensoes
condicionadas a autenticacao e a confirmacao da regra do Supera.
