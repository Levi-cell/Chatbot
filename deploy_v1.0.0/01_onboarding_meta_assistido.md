# Plano 1 — Onboarding Meta assistido da V1.0.0

> Status: runbook de preparação. Nenhuma etapa deste documento deve ser
> considerada concluída apenas porque está descrita aqui.
>
> Revisado em: 19/07/2026.

## Objetivo

Colocar os primeiros clientes no mesmo App Meta da ESLTech sem construir,
por enquanto, um portal próprio de onboarding.

A V1 usará o **Hosted Embedded Signup**: a Meta hospeda a tela e o cliente
autoriza os próprios ativos por um link. A ESLTech acompanha o procedimento e
executa as chamadas Graph API que concluem e validam o onboarding.

Isso é um onboarding assistido e parcialmente manual. Não é correto chamá-lo
de onboarding sem Embedded Signup, porque a autorização do cliente e a emissão
da credencial apropriada continuam acontecendo pelo Embedded Signup da Meta.

## Estado Meta confirmado para o piloto

Em 18/07/2026, a estrutura observada confirma que:

- o App é propriedade do Business Portfolio **ESL Soluções Tec**;
- o usuário de sistema `ed` pertence à ESL;
- o portfólio **Método Supera Santo Antônio de Jesus** permanece proprietário
  da WABA e do número piloto;
- o token do `ed` atende ao piloto porque a WABA foi compartilhada com a ESL e
  atribuída a esse usuário, mas não será a credencial universal dos futuros
  clientes;
- cada cliente futuro autorizará sua integração e fornecerá ao backend um BISU
  próprio por meio do Embedded Signup.

A nota consolidada, incluindo a separação entre piloto e arquitetura-alvo,
está em [`../meta_anotacoes/README.md`](../meta_anotacoes/README.md).

## Correção da arquitetura de credenciais

A topologia fechada para a V1 é:

```text
1 portfólio ESL
├── 1 App Meta
├── 1 webhook
├── 1 usuário de sistema ed
│   └── 1 System User Access Token
│       └── administração da ESL e fallback temporário do piloto
│
└── X portfólios de clientes
    ├── Cliente A ── BISU A ── WABA A ── phone_number_id A
    ├── Cliente B ── BISU B ── WABA B ── phone_number_id B
    └── Cliente C ── BISU C ── WABA C ── phone_number_id C
```

Para acessar WABAs pertencentes a empresas clientes, um Tech Provider deve
usar o **business integration system user access token**, chamado neste
documento de *business token*, emitido no contexto da integração daquele
cliente. O token pertence à autorização (*grant*) obtida naquele onboarding.
A API pode representar mais de um ativo nos `granular_scopes[].target_ids`,
mas a ESLTech deliberadamente não usará essa cardinalidade na V1. Portanto:

- o App pode ser único;
- o usuário de sistema `ed` pode continuar único no portfólio ESL;
- não é necessário criar um App para cada WABA;
- não é necessário criar um usuário humano para cada WABA;
- não é necessário criar um System User manual nem uma tabela
  `usuario_meta` para cada WABA;
- a regra operacional e de banco da V1 é exatamente **uma unidade, um BISU,
  uma WABA e um `phone_number_id`**;
- um onboarding que devolver zero ou mais de uma WABA/número para a unidade
  não será ativado até o operador selecionar e confirmar a tupla única;
- o token global atual pode continuar somente como credencial de
  desenvolvimento/bootstrap de ativos *first-party*, isto é, WABAs cuja dona
  formal seja o próprio Business Portfolio ESL;
- o token global atual não deve ser reutilizado como credencial universal de
  todos os clientes terceiros;
- uma revogação ou expiração de um cliente não pode interromper os demais.

Essa relação 1:1 é uma decisão de produto da ESLTech para reduzir erro de
roteamento e isolar revogações. Ela não significa criar um usuário humano ou um
System User manual por WABA: o BISU continua sendo a identidade criada pela
integração comercial daquele cliente.

A WABA piloto do Método Supera é um ativo de cliente porque pertence
formalmente ao portfólio Método Supera, ainda que os portfólios tenham sócios ou
administradores em comum. O token do `ed` pode permanecer como fallback legado
durante a migração, mas essa WABA também deve passar pelo onboarding que gera o
BISU antes da remoção do fallback.

Referências oficiais: [Access Tokens](https://developers.facebook.com/documentation/business-messaging/whatsapp/access-tokens#business-integration-system-user-access-tokens)
e [Solution Providers](https://developers.facebook.com/documentation/business-messaging/whatsapp/solution-providers/overview).

## Respostas diretas às dúvidas

### É um usuário ou um token por WABA?

Não. O usuário humano participa da autorização, mas não deve ser a identidade
de runtime da produção. O **Business Integration System User** é administrado
pela integração da Meta; não será modelado como um usuário interno 1:1 com a
unidade.

O banco armazenará uma linha de integração 1:1 por unidade. Na V1, essa linha
representa o BISU, a única WABA e o único número daquela unidade. Outra WABA
exigirá outra unidade/integração ou uma mudança explícita de arquitetura em
versão futura.

Em resumo:

```text
unidade 1 ── BISU 1 ── WABA 1 ── phone_number_id 1
```

O segredo fica criptografado em `integracao_meta_unidade`. A identificação do
Business Integration System User retornada pela Meta, quando disponível, é
apenas metadado de auditoria nessa mesma linha; não exige uma tabela
`usuario_meta`.

### O BISU pode ser permanente?

Sim. Para comunicação servidor-servidor, a Meta documenta que o Business
Integration System User Access Token, por padrão, **não expira**. A opção de
criar um token com 60 dias é configurável; não será a escolha da V1.

Alguns modelos prontos do Configurador de cadastro incorporado já vêm
identificados como token de 60 dias. Eles não devem ser usados sem revisão na
V1. Na configuração efetivamente publicada, a ESLTech deve omitir/desativar
`set_token_expires_in_60_days=true` e, depois da emissão, confirmar o resultado
real em `/debug_token`. A tela escolhida não substitui essa confirmação.

Mesmo sem data de expiração, ele não é irrevogável. O cliente pode remover o
App/integração, permissões podem mudar e a Meta pode invalidar a credencial. Por
isso, o sistema deve:

- armazenar `token_expires_at` e `data_access_expires_at` como campos
  opcionais;
- considerar `is_valid` de `/debug_token` como a autoridade de validade;
- alertar por data somente quando a Meta devolver um timestamp positivo;
- validar periodicamente o BISU e suportar substituição manual pelo Admin;
- nunca cair automaticamente no token global do `ed` para outro cliente.

Referências oficiais: [Facebook Login for Business](https://developers.facebook.com/documentation/facebook-login/facebook-login-for-business#business-integration-system-user-access-tokens)
e [`/debug_token`](https://developers.facebook.com/docs/graph-api/reference/debug_token/).

### Quem define o PIN do número?

O PIN usado em `POST /{PHONE_NUMBER_ID}/register` é definido por quem está
concluindo o registro do número. Ele é um segredo numérico de seis dígitos da
verificação em duas etapas do WhatsApp; não é o código temporário recebido por
SMS ou ligação.

Para um número novo, a ESLTech pode gerar o PIN durante o onboarding. Para um
número já existente ou migrado, pode ser necessário conhecer o PIN atual ou
seguir o procedimento de redefinição permitido pela Meta antes da migração.

O endpoint não exige que o PIN seja globalmente único, então a mesma sequência
pode até ser aceita em números diferentes. Mesmo assim, a regra operacional da
V1 será:

- usar PIN aleatório e diferente por número;
- nunca deixar o PIN global em `META_PHONE_REGISTRATION_PIN` em produção;
- nunca registrar PIN, token ou código OTP em log;
- persistir um PIN por unidade/número em `integracao_meta_unidade`, sempre
  criptografado;
- permitir somente escrita/substituição no Admin, sem nunca devolver o valor
  salvo para a tela;
- resolver o PIN pelo `phone_number_id` apenas quando uma operação de registro
  realmente precisar dele.

Reutilizar o mesmo PIN em todos os números aumenta muito o impacto de um
vazamento e dificulta auditoria e desligamento de um único cliente.

### Para que serve `/{WABA_ID}/subscribed_apps`?

Esse endpoint não cria o App, não registra um novo App na conta Meta e não
configura outra URL. Ele assina o **mesmo App já autorizado** nos eventos de
webhook de uma WABA específica.

Na prática:

1. o cliente autoriza o App e a WABA pelo Embedded Signup;
2. a ESLTech chama `POST /{WABA_ID}/subscribed_apps` com o business token
   daquele cliente;
3. a partir daí a Meta entrega ao webhook do App os eventos daquela WABA;
4. a ESLTech confirma a assinatura com `GET /{WABA_ID}/subscribed_apps`.

A assinatura é feita uma vez por WABA, não uma vez por mensagem nem uma vez por
telefone. A WABA atual já está assinada se suas mensagens chegam ao webhook;
cada futura WABA precisa da própria chamada. A assinatura deve ser refeita se a
integração for revogada ou recriada.

Referências oficiais: [Subscribe to a WABA](https://www.postman.com/meta/whatsapp-business-platform/request/26gui66/subscribe-to-a-waba)
e [Get subscribed apps](https://www.postman.com/meta/whatsapp-business-platform/documentation/wlk6lh4/whatsapp-cloud-api?entity=request-13382743-75e65a16-c157-4877-a02a-87315efaf48e).

### É necessário marcar uma reunião com o cliente?

Não. O administrador do cliente pode abrir o link do Hosted Embedded Signup e
autorizar os ativos de forma assíncrona. Uma chamada conjunta pode ajudar no
primeiro contrato ou em migração complexa, mas não é exigência técnica.

O que precisa ser rápido é a etapa posterior: o código de autorização devolvido
pela Meta deve ser trocado imediatamente no backend, e o registro do número,
quando exigido, precisa ser concluído dentro da janela descrita abaixo.

### Compartilhar a WABA manualmente substitui o Embedded Signup?

Não para o modelo atual de Tech Provider. Atribuir a ESLTech como parceiro
concede acesso administrativo ao ativo, mas não substitui a autorização que
gera o business token com escopo do cliente.

## O que significam as seções destacadas na tela da Meta

### Integração de Provedor de Tecnologia

É a área de habilitação da ESLTech como Tech Provider. Na tela inspecionada em
18/07/2026:

- a verificação da empresa já aparece como aprovada;
- a análise do App ainda não está concluída;
- a Meta solicita acesso avançado a
  `whatsapp_business_management` e `whatsapp_business_messaging`;
- a preparação da análise exige dados básicos do App, como ícone, categoria e
  URL da Política de Privacidade;
- a evidência para `whatsapp_business_messaging` deve demonstrar envio de
  mensagem;
- a evidência para `whatsapp_business_management` deve demonstrar a gestão de
  ativos, como a criação de um modelo de mensagem;
- a Access Verification e a App Review precisam ser concluídas antes de uma
  operação ampla com ativos de terceiros.

Essa é a primeira pendência estrutural antes de declarar o onboarding de novos
clientes pronto para produção.

### Configurador de cadastro incorporado

É onde se cria a configuração do Facebook Login for Business/Embedded Signup:

- tipo de token e ativos que poderão ser autorizados;
- permissões solicitadas;
- domínios HTTPS permitidos;
- versão do fluxo;
- configuração usada para gerar o link hospedado pela Meta.

Para uma implementação nova, usar a versão atual indicada pela Meta. A tela
inspecionada alerta que a versão 2 será retirada em 15/10/2026; portanto o plano
da ESLTech parte da versão 4, não da versão 2.

A configuração também permite gerar o Hosted Embedded Signup, justamente a
alternativa adequada para a V1 sem portal próprio.

### Soluções para parceiros

Essa seção é usada quando dois parceiros participam da administração dos
ativos de um cliente e precisam compartilhar responsabilidades/permissões.
Ela não é necessária no contrato direto inicial entre a ESLTech e cada cliente.

Só deve entrar no processo quando existir outro BSP/Tech Provider no desenho ou
quando um procedimento formal de coadministração exigir isso.

### Atenção à opção “Migrar clientes”

Na tela atual, essa opção está associada ao produto de Marketing Messages API.
Ela não deve ser tratada automaticamente como a migração comum de uma WABA ou
de um número da Cloud API entre provedores.

Migração de número entre provedores/WABAs exige um runbook próprio e pode
envolver elegibilidade, verificação em duas etapas, OTP, indisponibilidade
temporária e janela de corte.

## Fase A — Preparação única do App da ESLTech

### 1. Concluir os dados básicos do App

- cadastrar ícone do App;
- cadastrar categoria compatível com a solução;
- cadastrar Política de Privacidade pública em HTTPS;
- cadastrar URL/instruções de exclusão de dados, se solicitadas;
- conferir domínio do webhook e demais domínios permitidos;
- manter o App sob o Business Portfolio verificado da ESLTech.

### 2. Concluir as permissões e análises

Solicitar e obter o acesso necessário para:

- `whatsapp_business_management`;
- `whatsapp_business_messaging`.

Preparar evidências separadas e objetivas:

- vídeo do fluxo de envio de mensagem;
- vídeo do fluxo de gestão exigido pela permissão;
- explicação de que cada WABA pertence ao cliente e é autorizada por ele;
- explicação de como tokens e dados ficam isolados por integração.

Não iniciar onboarding comercial amplo enquanto o App ainda estiver apenas em
modo de desenvolvimento ou sem o acesso aprovado necessário.

### 3. Validar o webhook de produção

- URL pública fixa em HTTPS;
- certificado válido;
- `GET` de verificação funcionando com o verify token;
- assinatura `X-Hub-Signature-256` validada com o App Secret;
- endpoint capaz de retornar `200` rapidamente;
- idempotência por `wamid`;
- logs sem tokens, PINs, OTPs ou conteúdo sensível desnecessário.

### 4. Criar a configuração do Embedded Signup

No **Configurador de cadastro incorporado**:

1. criar a configuração do Facebook Login for Business;
2. escolher a versão atual suportada, partindo da versão 4;
3. solicitar somente os ativos e permissões necessários;
4. adicionar o domínio HTTPS de retorno da ESLTech;
5. escolher o perfil de BISU servidor-servidor sem expiração programada;
6. não manter a opção/modelo de token de 60 dias sem intenção explícita;
7. configurar o Hosted Embedded Signup;
8. salvar o `configuration_id` de produção;
9. testar primeiro com um ativo controlado pela própria ESLTech;
10. confirmar em `/debug_token` que o token de teste tem a validade esperada.

O link hospedado deve ser gerado somente a partir da configuração de produção
aprovada. Não colocar App Secret ou token na URL.

## Fase B — Procedimento assistido para cada cliente

### 1. Classificar o cenário antes de clicar em qualquer coisa

Registrar qual dos cenários abaixo se aplica:

1. WABA do cliente já existente na Cloud API e pertencente ao próprio cliente;
2. novo número e nova WABA do cliente;
3. número usado no WhatsApp Business App com fluxo de coexistência elegível;
4. número/WABA administrado por outro provedor e que exige migração.

Os cenários 3 e 4 não devem usar o runbook simples sem antes validar as regras
específicas da Meta. Não se “migra um `waba_id`” entre empresas: quando a WABA
pertence ao provedor antigo, normalmente é preciso trabalhar com uma WABA
pertencente ao cliente e migrar o número elegível.

### 2. Confirmar pré-requisitos do cliente

- administrador do Business Portfolio disponível;
- Business Portfolio e WABA pertencentes ao cliente;
- WABA correta identificada;
- número correto identificado;
- acesso ao número para receber SMS/ligação, quando necessário;
- situação do PIN de verificação em duas etapas conhecida;
- PIN individual definido e pronto para ser gravado somente de forma
  criptografada;
- forma de pagamento configurada quando exigida;
- autorização contratual/LGPD registrada;
- provedor atual e possível dependência de migração documentados.

### 3. Enviar o link do Hosted Embedded Signup

O operador gera e envia ao administrador do cliente o link hospedado pela Meta.
O cliente:

1. entra com sua própria conta Meta;
2. escolhe seu Business Portfolio;
3. escolhe ou cria a WABA apropriada;
4. escolhe ou adiciona o número;
5. aceita os termos e autoriza o App da ESLTech;
6. conclui o fluxo e retorna para a URL configurada.

O operador nunca deve pedir a senha pessoal da Meta ao cliente.

#### Atribuição manual de parceiro, quando aplicável

Se o cenário ou a orientação mostrada pela Meta pedir o compartilhamento
administrativo do ativo, o administrador do cliente pode acessar:

```text
Configurações do negócio
  -> Contas
  -> Contas do WhatsApp
  -> selecionar a WABA
  -> Parceiros/Atribuir parceiro
```

Ele informa o Business Portfolio ID da ESLTech e concede somente as permissões
necessárias. Depois, o operador confirma se a WABA aparece entre os ativos
compartilhados.

Essa etapa é opcional conforme o cenário e **não substitui** o Hosted Embedded
Signup nem a emissão do business token do cliente.

### 4. Capturar e trocar o código imediatamente

O retorno fornece dados da sessão e um código de autorização. A função de
backend deve:

1. validar `state` para impedir troca de código de outro onboarding;
2. trocar o código pelo business token;
3. descartar o código após a primeira tentativa bem-sucedida;
4. consultar `/debug_token`;
5. confirmar App emissor, validade, permissões, expirações e cliente esperado;
6. criptografar o token antes de armazená-lo;
7. não expor código nem token em query string, tela de erro ou log.

O código é efêmero e não representa a janela total do onboarding. A regra
operacional é trocá-lo imediatamente no callback, sem depender de uma ação
manual posterior nem prometer ao cliente uma janela longa para essa troca.

### 5. Confirmar os ativos autorizados

Com o business token daquele cliente:

- obter/confirmar o `business_id`;
- obter/confirmar o `waba_id`;
- consultar `GET /{WABA_ID}/phone_numbers`;
- confirmar que o `phone_number_id` pertence à WABA autorizada;
- comparar o número exibido com o número informado no contrato;
- impedir que um ativo do cliente A seja salvo na integração do cliente B.

### 6. Assinar o App na WABA

Executar:

```text
POST /{WABA_ID}/subscribed_apps
GET  /{WABA_ID}/subscribed_apps
```

O `POST` deve usar o business token do cliente em questão. O onboarding só
avança se o `GET` confirmar a presença do App esperado.

### 7. Verificar e registrar o número

Quando o cenário exigir verificação por SMS/voz:

```text
POST /{PHONE_NUMBER_ID}/request_code
POST /{PHONE_NUMBER_ID}/verify_code
```

Depois, quando o número exigir registro na Cloud API:

```text
POST /{PHONE_NUMBER_ID}/register
```

O registro usa o PIN de seis dígitos definido para aquele número. O PIN não é o
OTP enviado por SMS/voz. Antes da chamada, o onboarding grava/substitui o PIN
criptografado em `integracao_meta_unidade`; o valor puro só existe em memória
pelo tempo necessário para validar, criptografar e executar o registro.

### 8. Validar cobrança e estado operacional

- forma de pagamento aceita;
- nome de exibição/qualidade sem bloqueio impeditivo;
- WABA ativa;
- número registrado na Cloud API;
- App ainda inscrito na WABA;
- business token ainda válido;
- webhook reconhecendo o `phone_number_id` correto.

### 9. Fazer teste de ponta a ponta

1. enviar uma mensagem controlada pelo número da unidade;
2. confirmar a chegada no WhatsApp do destinatário;
3. responder como cliente;
4. confirmar a chegada do webhook;
5. confirmar a criação da fila apenas para a unidade correta;
6. confirmar a resposta do worker usando o mesmo `phone_number_id`;
7. confirmar que nenhum token de outra integração foi usado;
8. confirmar logs e métricas sem segredos.

### 10. Ativar a unidade somente depois do aceite

O cadastro administrativo deve ficar pendente/inativo até todos os itens abaixo
serem verdadeiros:

- token validado;
- WABA e telefone confirmados;
- App inscrito na WABA;
- número registrado quando exigido;
- webhook recebido;
- envio e resposta testados;
- credencial armazenada de forma isolada.

## Janela de 14 dias e outros prazos

- Quando o número precisa ser registrado após o Embedded Signup, concluir o
  registro em até **14 dias**. Se a janela expirar, pode ser necessário repetir
  o Embedded Signup.
- Trocar o código de autorização imediatamente; não planejar trabalho manual
  para “alguns dias depois”.
- Usar OTP de SMS/voz imediatamente; não assumir prazo não documentado.
- Criar o BISU sem expiração para o runtime servidor-servidor da V1. Ainda
  assim, registrar `expires_at` e `data_access_expires_at` quando existirem e
  verificar `is_valid`, pois o token continua revogável.
- O compartilhamento da WABA com um parceiro permanece até revogação; ele não
  possui a mesma janela curta do código de autorização.
- Se for usado um fluxo de coexistência, observar separadamente os prazos que a
  Meta mostrar para sincronização e conclusão.

Referência: [Tech Provider onboarding](https://developers.facebook.com/documentation/business-messaging/whatsapp/solution-providers/get-started-for-tech-providers)
e [Embedded Signup](https://developers.facebook.com/documentation/business-messaging/whatsapp/embedded-signup/overview).

## Funções `requests` necessárias após as telas da Meta

Este primeiro plano descreve contratos, não implementa os arquivos. Todas as
funções devem receber a credencial da integração explicitamente ou resolvê-la
por `business_id`/`waba_id`/`phone_number_id`. Nenhuma delas deve depender
silenciosamente de `META_ACCESS_TOKEN` para ativos de clientes.

| Função proposta | Responsabilidade | Chamada principal |
|---|---|---|
| `trocar_codigo_embedded_signup()` | Trocar o código efêmero pelo business token do cliente | endpoint OAuth da Meta |
| `inspecionar_business_token()` | Validar App, permissões, validade e expirações | `GET /debug_token` |
| `listar_wabas_autorizadas()` | Confirmar WABAs acessíveis ao cliente autorizado | endpoint de WABAs compartilhadas/autorizadas |
| `listar_numeros_waba()` | Paginar e validar os números de uma WABA | `GET /{WABA_ID}/phone_numbers` |
| `assinar_app_na_waba()` | Inscrever o App nos webhooks daquela WABA | `POST /{WABA_ID}/subscribed_apps` |
| `consultar_assinatura_waba()` | Confirmar a inscrição após o POST | `GET /{WABA_ID}/subscribed_apps` |
| `solicitar_codigo_numero()` | Pedir OTP por SMS/voz quando o cenário exigir | `POST /{PHONE_NUMBER_ID}/request_code` |
| `verificar_codigo_numero()` | Confirmar o OTP recebido | `POST /{PHONE_NUMBER_ID}/verify_code` |
| `salvar_pin_numero()` | Validar e criptografar o PIN individual do telefone | PostgreSQL, sem logar o valor |
| `registrar_numero_whatsapp()` | Resolver o PIN/credencial corretos e registrar o número | `POST /{PHONE_NUMBER_ID}/register` |
| `desregistrar_numero_whatsapp()` | Desregistrar somente em offboarding/migração aprovada | `POST /{PHONE_NUMBER_ID}/deregister` |
| `enviar_mensagem_teste()` | Fazer teste controlado com o token correto | `POST /{PHONE_NUMBER_ID}/messages` |
| `diagnosticar_onboarding_meta()` | Reunir token, assinatura, número e saúde sem imprimir segredos | várias consultas somente leitura |

Adaptações mínimas nos utilitários atuais:

- `ativando_waba_id.py`: receber token explícito, timeout e resposta segura;
- `ativando_numero.py`: receber token/PIN explícitos ou resolvê-los pelo
  `phone_number_id`, sem fallback global em produção;
- `desativa_waba_id.py`: receber token da WABA correta;
- `desativando_numero.py`: receber token do telefone correto;
- `block_report.py`: iterar todas as WABAs cadastradas com seus próprios tokens;
- todos os utilitários: paginação, timeout, erro estruturado e logs sem segredo.

No sistema final, essas funções não serão chamadas a cada campo digitado. O
operador preenche `client_business_id`, `waba_id`, `phone_number_id`, BISU e PIN
no formulário administrativo e o backend executa a orquestração Meta-first uma
vez, ao enviar o formulário. Cada efeito externo é confirmado antes de a
integração local ser marcada como ativa. O desenho completo está em
[`02_plano_tecnico_multi_waba.md`](02_plano_tecnico_multi_waba.md).

## Rollback e offboarding

Para apenas remover a integração da ESLTech, sem destruir os ativos do cliente:

1. inativar a unidade no sistema;
2. interromper novos envios para o telefone;
3. remover a inscrição do App em `/{WABA_ID}/subscribed_apps`, quando a WABA
   não for usada por outra unidade autorizada;
4. revogar a integração/autorização no Business Portfolio;
5. remover a ESLTech como parceiro, se ela foi atribuída;
6. revogar e apagar o token armazenado;
7. manter apenas auditoria sem segredo;
8. não excluir WABA, número ou Business Portfolio do cliente.

Migração para outro provedor deve ter um runbook próprio.

## Checklist por cliente

- [ ] Cenário classificado: vinculação, novo número, coexistência ou migração.
- [ ] Cliente é proprietário do Business Portfolio/WABA.
- [ ] Administrador do cliente concluiu o Hosted Embedded Signup.
- [ ] Código trocado imediatamente.
- [ ] Business token client-scoped validado em `/debug_token`.
- [ ] Expirações registradas e monitoradas.
- [ ] `business_id`, `waba_id` e `phone_number_id` conferidos.
- [ ] App inscrito e confirmado em `subscribed_apps`.
- [ ] Número verificado/registrado quando exigido, dentro de 14 dias.
- [ ] Forma de pagamento e estado do número conferidos.
- [ ] Webhook recebido e roteado para a unidade certa.
- [ ] Mensagem de teste enviada e respondida.
- [ ] Token e PIN ausentes de logs, cache e argumentos de terminal.
- [ ] PIN individual persistido somente como ciphertext vinculado ao número.
- [ ] Unidade ativada somente após teste ponta a ponta.
- [ ] Rollback/offboarding registrado.

## Fontes oficiais para revisar antes de cada onboarding

- [Solution Providers](https://developers.facebook.com/documentation/business-messaging/whatsapp/solution-providers/overview)
- [Get started for Tech Providers](https://developers.facebook.com/documentation/business-messaging/whatsapp/solution-providers/get-started-for-tech-providers)
- [Access Tokens](https://developers.facebook.com/documentation/business-messaging/whatsapp/access-tokens)
- [Debug Token](https://www.postman.com/meta/whatsapp-business-platform/request/i1mz7w8/debug-token)
- [Embedded Signup](https://developers.facebook.com/documentation/business-messaging/whatsapp/embedded-signup/overview)
- [WhatsApp Business Accounts](https://developers.facebook.com/documentation/business-messaging/whatsapp/whatsapp-business-accounts)
- [Subscribe to a WABA](https://www.postman.com/meta/whatsapp-business-platform/request/26gui66/subscribe-to-a-waba)
- [Webhook Subscriptions](https://www.postman.com/meta/whatsapp-business-platform/folder/ypn8q0n/webhook-subscriptions)
- [Get Shared WABAs](https://www.postman.com/meta/whatsapp-business-platform/request/fjdr6gp/get-shared-wabas)
- [Migrating phone numbers among Solution Partners](https://developers.facebook.com/documentation/business-messaging/whatsapp/solution-providers/support/migrating-phone-numbers-among-solution-partners-via-embedded-signup)
