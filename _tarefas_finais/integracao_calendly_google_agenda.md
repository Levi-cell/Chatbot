# Integracao futura: Calendly gratuito observado pelo Google Agenda

## Status da ideia

Esta documentacao registra uma possibilidade para uma versao posterior do
chatbot. Ela nao representa uma funcionalidade atualmente implementada e nao
deve alterar o fluxo da V1.

Decisao para a V1:

```text
Botao "Agendar"
-> abre o Calendly
-> cliente conclui o agendamento
-> cliente confirma pelo WhatsApp usando "Ja agendei"
```

Possivel evolucao:

```text
Calendly gratuito
-> cria o compromisso no Google Agenda
-> Google Agenda avisa o chatbot
-> chatbot identifica o agendamento
-> chatbot confirma automaticamente pelo WhatsApp
```

## Objetivo

Manter a pagina de agendamento do Calendly, que oferece uma experiencia melhor
ao cliente final, sem depender do webhook pago do Calendly.

O Calendly continuaria sendo a interface usada para:

- apresentar dias e horarios disponiveis;
- impedir dois agendamentos no mesmo horario;
- coletar nome e email;
- confirmar visualmente o agendamento;
- criar o compromisso no calendario da unidade.

O Google Agenda seria usado como fonte de observacao:

- o Calendly grava o compromisso no Google Agenda;
- a API do Google Agenda notifica nosso sistema sobre a alteracao;
- nosso sistema consulta o calendario e encontra o evento criado;
- o chatbot relaciona o evento com uma conversa;
- a confirmacao final e enviada pelo WhatsApp.

## Por que essa combinacao funciona

O Calendly permite conectar um Google Agenda e escolher em qual calendario as
novas reunioes serao adicionadas. Assim, um agendamento concluido no Calendly
se transforma em um evento real no Google Agenda.

A API do Google Agenda oferece canais de notificacao do tipo `watch`. Quando
um evento e criado, alterado ou removido, o Google envia um `POST` para uma URL
HTTPS configurada pelo nosso sistema.

Importante: o Google nao envia o evento completo nesse `POST`. A notificacao
apenas informa que o calendario sofreu uma alteracao. Depois disso, nosso
backend precisa consultar a API para descobrir quais eventos mudaram.

## Fluxo explicado de forma simples

```text
1. O chatbot termina a triagem.

2. O chatbot envia:

   Obrigada por responder as perguntas!

   Para escolher o melhor dia e horario para sua avaliacao cognitiva
   e aula experimental gratuita, clique em "Agendar".

3. O cliente toca no botao e abre a pagina do Calendly.

4. O cliente escolhe uma data, informa os dados e conclui.

5. O Calendly adiciona a reuniao no Google Agenda da unidade.

6. O Google Agenda avisa nosso endpoint:

   POST /webhook/google-calendar

7. Nosso backend consulta o Google Agenda e encontra o novo evento.

8. O backend relaciona o email do participante com:

   unidade + cliente + conversa aguardando agendamento

9. O sistema registra o agendamento de maneira idempotente.

10. O worker envia:

    Apos finalizar o agendamento, nos entraremos em contato
    para te lembrar um dia antes do nosso encontro.
    Ate la.

11. A conversa avanca para o estado final definido pelo fluxo.
```

## Papel de cada plataforma

### WhatsApp

- conduz o atendimento;
- coleta o email na etapa apropriada;
- envia o link de agendamento;
- envia a confirmacao depois que o evento for encontrado;
- mantem o historico conversacional e a idempotencia de mensagens.

### Calendly

- exibe a pagina de agendamento;
- administra disponibilidade;
- recebe a escolha do cliente;
- cria o compromisso no Google Agenda conectado;
- continua sendo a interface apresentada ao cliente.

### Google Agenda

- recebe o evento criado pelo Calendly;
- funciona como fonte tecnica de observacao;
- avisa que o calendario mudou;
- permite consultar criacoes, alteracoes e cancelamentos.

### Nosso backend

- recebe a notificacao do Google;
- consulta as alteracoes;
- diferencia um agendamento valido de um evento comum;
- encontra a conversa correspondente;
- registra o evento sem duplicidade;
- pede ao worker que envie a resposta final.

## Configuracao necessaria no Calendly

Cada unidade precisara:

1. Ter uma conta Calendly.
2. Conectar a conta do Google usada pela unidade.
3. Escolher o calendario em que o Calendly adicionara novas reunioes.
4. Manter um tipo de evento identificavel, por exemplo:

   ```text
   Avaliacao cognitiva e aula experimental - Supera
   ```

5. Configurar o formulario para coletar pelo menos:

   - nome;
   - email.

O titulo e o calendario precisam seguir um padrao conhecido para reduzir o
risco de confundir um agendamento do chatbot com um evento manual.

## Configuracao necessaria no Google

Em uma implementacao futura sera necessario:

1. Criar ou utilizar um projeto no Google Cloud.
2. Habilitar a Google Calendar API.
3. Configurar a tela de consentimento OAuth.
4. Criar credenciais OAuth para a aplicacao.
5. Solicitar somente os escopos necessarios, preferencialmente leitura do
   calendario.
6. Permitir que cada unidade autorize o calendario usado pelo Calendly.
7. Armazenar o `refresh_token` de maneira criptografada.
8. Descobrir o `calendar_id` observado.
9. Fazer a sincronizacao inicial dos eventos.
10. Criar um canal `watch` para o calendario.

Para uma aplicacao publica com varias unidades, pode ser necessario passar pelo
processo de verificacao OAuth do Google. Essa exigencia deve ser revisada
quando a implementacao for iniciada.

## Endpoint separado

O endpoint deve ser separado do webhook da Meta:

```text
POST /webhook
-> eventos da Meta/WhatsApp

POST /webhook/google-calendar
-> notificacoes da Google Calendar API
```

As duas rotas podem usar o mesmo dominio e o mesmo projeto Django, mas possuem
autenticacao, payloads e regras completamente diferentes.

## Como funciona a notificacao do Google

Ao criar o canal `watch`, nosso sistema informa:

- um `channel_id` unico;
- uma URL HTTPS;
- um token secreto do canal;
- o calendario que sera observado;
- a expiracao desejada.

O Google passa a enviar cabecalhos como:

```text
X-Goog-Channel-ID
X-Goog-Channel-Token
X-Goog-Resource-ID
X-Goog-Resource-State
X-Goog-Message-Number
X-Goog-Channel-Expiration
```

O corpo da requisicao normalmente nao contem os dados do evento.

Portanto:

```text
Google avisa que algo mudou
-> endpoint valida o canal
-> registra uma tarefa local
-> responde HTTP 200 rapidamente
-> tarefa consulta a API
-> tarefa processa os eventos alterados
```

O endpoint HTTP nao deve enviar mensagens no WhatsApp diretamente. Ele deve
registrar o trabalho e deixar o processamento confiavel para um worker.

## Sincronizacao incremental

Na primeira configuracao do calendario:

```text
events.list
-> leitura inicial
-> Google retorna nextSyncToken
-> sistema salva o syncToken
```

Nas proximas notificacoes:

```text
events.list(syncToken=token_salvo)
-> retorna somente as alteracoes
-> retorna um novo nextSyncToken
-> sistema salva o token novo apos processar tudo
```

Se o Google responder `410 Gone`, o `syncToken` deixou de ser valido. Nesse
caso, o sistema precisa realizar uma nova sincronizacao completa controlada.

## Como relacionar o evento com a conversa

O Google Agenda nao deve ser consultado apenas pelo nome, pois nomes podem se
repetir.

Na arquitetura atual, o principal elo disponivel e:

```text
id_unidade
+
email coletado pelo chatbot
+
email usado no Calendly
+
conversa aguardando agendamento
```

Regra proposta:

```text
1. Identificar a unidade pelo canal/calendario observado.
2. Extrair o email do participante do evento.
3. Normalizar o email.
4. Encontrar o cliente dessa unidade com o mesmo email.
5. Encontrar uma conversa elegivel aguardando agendamento.
6. Conferir se o evento foi criado depois do envio do link.
7. Conferir se o titulo corresponde ao tipo de evento esperado.
8. Somente entao confirmar o agendamento.
```

Se houver mais de uma conversa candidata, o sistema nao deve adivinhar.
Deve registrar uma inconsistencia para reconciliacao manual.

### Limitacao importante

O Calendly suporta parametros de rastreamento em seus proprios webhooks, mas
nao devemos assumir que um identificador personalizado colocado na URL sera
copiado para o evento do Google Agenda.

Antes de depender desse mecanismo, sera necessario fazer um teste real. Se o
identificador nao chegar ao Google Agenda, o pareamento continuara usando
unidade, email, estado da conversa e horario do evento.

## Filtros contra falsos positivos

O Google notificara alteracoes de qualquer evento existente no calendario
observado. Portanto, nao basta considerar todo evento novo como agendamento do
chatbot.

Filtros recomendados:

- calendario associado a unidade correta;
- evento criado depois do envio do link;
- titulo ou prefixo padronizado do Calendly;
- participante com email;
- email existente na conversa;
- conversa em estado elegivel;
- horario futuro;
- evento ainda confirmado;
- evento ainda nao processado;
- organizador esperado;
- ausencia de cancelamento.

Sempre que possivel, o Calendly deve gravar os eventos em um calendario
dedicado a agendamentos. Se o plano utilizado nao permitir um calendario
separado, os filtros acima tornam-se ainda mais importantes.

## Estrutura de dados sugerida

Esta e apenas uma proposta para avaliacao futura.

### Integracao Google por unidade

```text
integracao_google_unidade
-------------------------
id_integracao
id_unidade
calendar_id
oauth_refresh_token_criptografado
oauth_access_token_criptografado ou temporario
oauth_expira_em
channel_id
channel_token_hash
resource_id
channel_expira_em
sync_token
status_ativo
ultima_sincronizacao_em
ultimo_erro
criado_em
atualizado_em
```

Segredos OAuth nao devem ser armazenados diretamente na tabela `unidade`.

### Agendamento encontrado

```text
agendamento
-----------
id_agendamento
id_unidade
id_cliente
id_conversa
provider
provider_event_id
calendar_id
email_participante
nome_participante
inicio_em
fim_em
status
criado_provider_em
confirmacao_whatsapp_enviada_em
cancelado_em
reagendado_de
criado_em
atualizado_em
```

Restricao essencial:

```text
UNIQUE(provider, provider_event_id)
```

Essa restricao evita processar o mesmo evento duas vezes.

### Notificacoes recebidas

Opcionalmente:

```text
google_calendar_notificacao
---------------------------
id_notificacao
channel_id
resource_id
message_number
resource_state
recebida_em
processada_em
ultimo_erro
```

A combinacao abaixo pode servir como barreira idempotente:

```text
UNIQUE(channel_id, message_number)
```

O numero das mensagens cresce, mas nao deve ser tratado como uma sequencia sem
lacunas.

## Idempotencia

O Google pode enviar notificacoes repetidas ou notificacoes muito proximas.
Um mesmo evento tambem pode aparecer em mais de uma sincronizacao.

As barreiras devem ser:

```text
1. channel_id + message_number
2. provider + provider_event_id
3. confirmacao_whatsapp_enviada_em
4. historico da resposta do bot
```

Fluxo:

```text
evento novo
-> tenta inserir provider_event_id
-> se ja existe, atualiza estado sem duplicar
-> se confirmacao ainda nao existe, agenda envio
-> worker envia
-> persistencia registra historico e confirmacao
```

Essa integracao deve seguir as mesmas ideias de retry e idempotencia que o
worker atual ja utiliza.

## Renovacao dos canais

Os canais `watch` do Google Agenda expiram. Eles nao se renovam sozinhos.

Precisaremos de uma rotina periodica:

```text
buscar canais proximos da expiracao
-> criar um novo channel_id
-> iniciar novo watch
-> confirmar novo canal
-> manter pequeno periodo de sobreposicao
-> encerrar ou deixar expirar o canal antigo
```

Durante a sobreposicao, duas notificacoes podem representar a mesma alteracao.
Por isso a idempotencia pelo ID do evento e obrigatoria.

Uma unidade com canal expirado nao deve ser silenciosamente considerada
sincronizada. O Admin deve mostrar o estado da integracao.

## Cancelamentos e reagendamentos

Uma primeira versao pode tratar somente criacao de agendamento, mas a
arquitetura deve reconhecer desde o inicio que o evento pode:

- ser cancelado;
- mudar de horario;
- mudar de participante;
- ser excluido;
- ser recriado.

Estados sugeridos:

```text
scheduled
canceled
rescheduled
unknown
```

Ao detectar cancelamento:

- atualizar o registro local;
- nao reenviar a confirmacao inicial;
- decidir futuramente se o chatbot deve entrar em contato.

Ao detectar reagendamento:

- atualizar data e horario;
- manter referencia ao evento anterior quando possivel;
- evitar tratar o novo horario como um segundo lead.

## Falhas e autocura

### Webhook temporariamente fora do ar

Uma notificacao pode ser perdida. Para reduzir o risco, deve existir uma
reconciliacao periodica que execute sincronizacao incremental mesmo sem
notificacao.

```text
watch = baixa latencia
sync periodico = fallback
```

### Google indisponivel

```text
notificacao persistida
-> consulta falha
-> tarefa fica pendente
-> retry com backoff
```

O endpoint deve responder somente depois de registrar o trabalho local.

### Banco indisponivel

Se nao for possivel registrar a notificacao, o endpoint deve retornar erro
temporario. Tambem sera necessario confiar na reconciliacao periodica, pois nao
devemos depender exclusivamente de reentrega externa.

### WhatsApp indisponivel

O agendamento permanece salvo com:

```text
confirmacao_whatsapp_enviada_em = NULL
```

O envio entra em retry sem consultar ou recriar o agendamento.

### Canal expirado

O job de renovacao cria um novo canal. Depois, uma sincronizacao incremental ou
completa recupera alteracoes ocorridas na janela de indisponibilidade.

### Sync token invalido

```text
Google retorna 410
-> marcar token invalido
-> executar full sync limitado e idempotente
-> obter novo nextSyncToken
```

## Seguranca

- usar somente HTTPS com certificado valido;
- validar `X-Goog-Channel-ID`;
- validar `X-Goog-Resource-ID`;
- validar `X-Goog-Channel-Token` com comparacao segura;
- nao colocar OAuth token no channel token;
- criptografar refresh tokens no banco;
- nao registrar tokens completos em logs;
- limitar tamanho e metodos aceitos no endpoint;
- responder rapidamente;
- usar OAuth com menor escopo possivel;
- revogar credenciais quando uma unidade cancelar o contrato;
- separar os dados por unidade;
- auditar renovacoes, falhas e desconexoes.

## Multitenancy

Cada unidade pode possuir:

- uma conta Google diferente;
- um calendario diferente;
- uma conta Calendly diferente;
- um link de agendamento diferente.

O `channel_id` deve apontar para uma integracao conhecida e, por consequencia,
para um `id_unidade`.

```text
channel_id
-> integracao_google_unidade
-> id_unidade
-> calendario
-> clientes e conversas da unidade
```

Nunca procurar um cliente apenas pelo email em todas as unidades. O isolamento
por `id_unidade` deve fazer parte de toda consulta.

## Fluxo transacional sugerido

```text
Google notifica
-> valida cabecalhos
-> registra notificacao
-> commit
-> retorna 200

worker de sincronizacao
-> adquire lock da integracao/calendario
-> consulta alteracoes com syncToken
-> identifica eventos relevantes
-> upsert em agendamento
-> associa conversa quando nao ambiguo
-> atualiza syncToken
-> commit

worker de resposta
-> seleciona agendamento sem confirmacao
-> confirma que conversa continua elegivel
-> envia WhatsApp
-> registra historico e estado final
-> marca confirmacao enviada
-> commit
```

O envio ao WhatsApp nao deve acontecer dentro da mesma requisicao HTTP recebida
do Google.

## Observabilidade

Logs recomendados:

```text
google_calendar_notificacao_recebida
google_calendar_notificacao_duplicada
google_calendar_canal_desconhecido
google_calendar_token_invalido
google_calendar_sync_iniciado
google_calendar_sync_concluido
google_calendar_sync_token_expirado
google_calendar_evento_ignorado
google_calendar_agendamento_encontrado
google_calendar_conversa_nao_encontrada
google_calendar_conversa_ambigua
google_calendar_confirmacao_whatsapp_agendada
google_calendar_canal_renovado
google_calendar_canal_expirado
```

Metricas importantes:

- canais ativos;
- canais proximos da expiracao;
- ultima sincronizacao por unidade;
- notificacoes pendentes;
- falhas consecutivas;
- agendamentos sem conversa;
- agendamentos sem confirmacao enviada;
- tempo entre agendamento e confirmacao no WhatsApp.

## Custos

Em julho de 2026, a Google Calendar API utiliza cotas por projeto e por usuario.
O uso abaixo do limite diario informado pelo Google nao gera cobranca
adicional. Essa politica deve ser verificada novamente antes da implementacao.

Custos indiretos continuam existindo:

- infraestrutura do nosso backend;
- armazenamento de tokens e eventos;
- processamento dos workers;
- manutencao da integracao OAuth;
- possivel verificacao do aplicativo Google;
- suporte a cada unidade.

O Calendly pode continuar no plano gratuito desde que os recursos utilizados
pela unidade estejam disponiveis nesse plano. Recursos premium do Calendly nao
fazem parte desta proposta.

## Vantagens

- mantem a interface amigavel do Calendly;
- evita exigir o webhook pago do Calendly;
- confirmacao pode ser automatica;
- o Google Agenda ja e usado operacionalmente pelas unidades;
- permite reconciliacao mesmo se uma notificacao falhar;
- separa interface de agendamento da observacao tecnica.

## Desvantagens

- o Google e uma fonte indireta;
- exige OAuth por unidade;
- canais expiram;
- notificacoes nao possuem o evento completo;
- eventos manuais podem gerar falsos positivos;
- pareamento por email pode ficar ambiguo;
- cancelamentos e reagendamentos aumentam a complexidade;
- exige job de renovacao e job de reconciliacao;
- e mais trabalhoso do que o botao manual "Ja agendei".

## Quando vale implementar

Esta integracao passa a valer a pena quando:

- o fluxo principal do chatbot estiver concluido;
- a V1 estiver estavel;
- houver clientes reais usando o agendamento;
- a confirmacao manual estiver causando abandono;
- houver tempo para configurar OAuth e observabilidade;
- conseguirmos testar com calendarios reais de unidades.

Ela nao deve atrasar a finalizacao das etapas atuais.

## Prova de conceito antes da implementacao

Antes de alterar o banco ou o worker, realizar uma prova isolada:

1. Criar um Calendly gratuito de teste.
2. Conectar um Google Agenda de teste.
3. Criar um agendamento pelo Calendly.
4. Consultar o evento pela Google Calendar API.
5. Registrar exatamente quais campos chegam:

   - ID do evento;
   - titulo;
   - descricao;
   - organizador;
   - participantes;
   - email;
   - data de criacao;
   - status;
   - horario;
   - links;
   - propriedades adicionais.

6. Cancelar pelo Calendly e observar a alteracao no Google.
7. Reagendar e observar se o ID muda.
8. Criar um evento manual parecido e testar os filtros.
9. Confirmar se um parametro personalizado do link aparece no evento.
10. Medir o tempo entre o agendamento e a notificacao.

Somente depois dessa prova devem ser definidos o DDL e os contratos finais.

## Criterios de aceite futuros

- unidade consegue autorizar o Google Agenda;
- Calendly grava no calendario observado;
- canal `watch` e criado e renovado;
- webhook rejeita canais desconhecidos;
- sincronizacao incremental funciona;
- notificacao duplicada nao duplica agendamento;
- agendamento e associado a unidade correta;
- email e associado sem atravessar unidades;
- evento manual nao dispara confirmacao indevida;
- conversa ambigua nao e escolhida automaticamente;
- confirmacao do WhatsApp possui retry;
- cancelamento nao dispara nova confirmacao;
- falha do webhook e recuperada pela reconciliacao;
- tokens OAuth nao aparecem em logs;
- Admin mostra a saude da integracao.

## Referencias oficiais

- Calendly e Google Calendar:
  https://help.calendly.com/hc/en-us/articles/223193288-Getting-started-with-Google-Calendar

- Google Calendar push notifications:
  https://developers.google.com/workspace/calendar/api/guides/push

- Google Calendar incremental sync:
  https://developers.google.com/workspace/calendar/api/guides/sync

- Google Calendar quotas:
  https://developers.google.com/workspace/calendar/api/guides/quota

- Google Appointment Schedules:
  https://support.google.com/calendar/answer/11608416

## Resumo da decisao

```text
Agora:
Calendly + confirmacao manual "Ja agendei"

Futuro:
Calendly cria evento no Google Agenda
-> Google notifica nosso backend
-> backend sincroniza alteracoes
-> encontra cliente e conversa
-> worker envia confirmacao automaticamente
```

Essa estrategia e tecnicamente viavel, mas deve ser implementada somente depois
de uma prova de conceito confirmar quais dados do Calendly chegam ao evento do
Google Agenda.
