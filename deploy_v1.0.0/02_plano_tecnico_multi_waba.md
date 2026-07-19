# Plano 2 — Runtime multi-WABA com BISU isolado por unidade

> Status: especificação de implementação. Este documento não altera o banco
> nem o runtime por si só.
>
> Revisado em: 19/07/2026.

## Resultado esperado

Preparar o sistema para operar exatamente esta topologia:

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

A cardinalidade de produto da V1.0.0 é:

```text
1 unidade = 1 portfólio de cliente = 1 BISU = 1 WABA = 1 phone_number_id
```

O App, o webhook e o usuário de sistema `ed` continuam únicos. O token do
usuário de sistema da ESL não substitui o BISU de um cliente terceiro.

Este plano preserva as regras do atendimento, o cliente global, as conversas
por unidade, as etapas 1 a 19, o funil e o Redis como acelerador. A mudança é de
identidade, roteamento, segurança e onboarding Meta.

## Respostas fechadas antes da implementação

### O BISU precisa expirar?

Não. A documentação atual da Meta informa que o Business Integration System
User Access Token é criado, por padrão, sem expiração temporal programada para
comunicação servidor-servidor. A opção de 60 dias é uma configuração
específica, inclusive presente em modelos prontos do configurador; ela não é
uma obrigação da Meta.

A V1 usará BISU sem expiração programada. Isso exige três cuidados:

1. não selecionar nem manter inadvertidamente a opção
   `set_token_expires_in_60_days=true`;
2. confirmar o token realmente emitido por `/debug_token`;
3. gravar `token_expires_at=NULL` somente quando a Meta confirmar que não há
   expiração programada.

Sem expiração não significa irrevogável. O cliente pode remover a integração,
as permissões podem mudar, o App pode ser desautorizado e a Meta pode invalidar
o token. Por isso `is_valid` e as permissões retornadas pela Meta continuam
sendo a autoridade.

Referências oficiais:
[Access Tokens](https://developers.facebook.com/documentation/business-messaging/whatsapp/access-tokens)
e
[Facebook Login for Business](https://developers.facebook.com/documentation/facebook-login/facebook-login-for-business#business-integration-system-user-access-tokens).

### O token global fica no venv?

Não literalmente. O ambiente virtual `/opt/chatbot/venv` contém bibliotecas
Python. O segredo global fica no arquivo de ambiente de produção, atualmente
`/etc/chatbot/chatbot.env`, e é injetado nos serviços pelo systemd.

`META_ACCESS_TOKEN` continuará representando somente o System User Access
Token do `ed`. Ele será aceito:

- nas operações administrativas da própria ESL;
- temporariamente, na unidade piloto explicitamente autorizada durante a
  migração;
- nunca como fallback silencioso para qualquer WABA desconhecida.

Cada BISU de cliente ficará no PostgreSQL, criptografado e isolado por unidade.

### É necessário criar todas as tabelas do plano anterior?

Não. Três tabelas separadas para business/grant, WABA e número modelariam uma
cardinalidade que a V1 decidiu não oferecer. Para a regra estrita 1:1, isso
introduziria joins, estados duplicados e risco de divergência sem benefício
operacional.

A solução mínima e segura é:

- manter `unidade.waba_id` como a WABA única da unidade;
- manter `unidade.phone_number_id` como o número único da unidade;
- criar uma única tabela `integracao_meta_unidade`, em relação 1:1 com
  `unidade`, para BISU, PIN e estado do onboarding;
- adicionar `fila_mensagens.waba_id_origem` para preservar a proveniência do
  evento recebido.

Não serão criadas:

- `meta_business_integracao`;
- `meta_waba_integracao`;
- `meta_numero_integracao`;
- `usuario_meta`;
- uma tabela de App por unidade;
- uma cópia de `waba_id` ou `phone_number_id` dentro da integração.

### Por que não colocar BISU e PIN diretamente em `unidade`?

Seria tecnicamente possível, mas não é a escolha recomendada. `unidade` contém
a identidade comercial e o roteamento público. BISU e PIN são segredos com
ciclo de vida próprio, rotação, auditoria e estado de onboarding. Uma única
tabela 1:1 mantém essa separação sem criar uma hierarquia desnecessária.

### O Admin chama a Meta enquanto o operador digita cada campo?

Não. O Django Admin padrão valida e salva quando o formulário é enviado. Fazer
requisições externas a cada tecla ou saída de campo exigiria JavaScript e
criaria chamadas duplicadas e efeitos parciais.

A V1 seguirá o comportamento seguro:

1. o operador preenche todos os campos;
2. envia o formulário uma vez;
3. o backend valida o BISU e a tupla WABA/número;
4. executa os efeitos Meta necessários;
5. confirma os efeitos por consultas de leitura;
6. somente depois grava/ativa a integração local;
7. mostra aviso claro e não ativa a unidade se a Meta falhar.

Isso preserva o padrão Meta-first já usado pelo projeto sem transformar o
formulário em um portal de Embedded Signup.

## Fonte de verdade e invariantes

O PostgreSQL é a fonte de verdade do runtime. O Redis continua sendo apenas
cache:

- ausência no cache provoca consulta ao banco;
- dado presente no cache pode acelerar a decisão;
- divergência detectada invalida/reconstrói o cache;
- token e PIN nunca são gravados no Redis;
- nenhum efeito Meta é autorizado somente porque uma chave existe no cache.

Invariantes obrigatórios:

1. uma unidade possui exatamente um `waba_id`;
2. uma unidade possui exatamente um `phone_number_id`;
3. uma unidade possui no máximo uma linha em `integracao_meta_unidade`;
4. uma integração ativa possui exatamente um BISU e um PIN criptografados;
5. o mesmo `client_business_id` não pertence a duas unidades na V1;
6. o mesmo BISU não é cadastrado em duas unidades;
7. um evento só entra na fila se `entry.id`, `phone_number_id` e a unidade
   ativa formarem a mesma tupla;
8. o worker só responde depois de repetir essa validação;
9. a credencial de envio é resolvida pelo `phone_number_id` da unidade;
10. o token global do `ed` nunca é escolhido por tentativa ou conveniência.

## Schema mínimo da V1.0.0

### Relação final

```text
unidade
  id_unidade PK
  waba_id UNIQUE NOT NULL
  phone_number_id UNIQUE NOT NULL
       │
       └── 1 : 0..1 ── integracao_meta_unidade
                         id_unidade PK/FK
                         client_business_id UNIQUE
                         BISU criptografado
                         PIN criptografado
                         estado e auditoria

fila_mensagens
  id_phone_unidade
  waba_id_origem
```

Uma unidade ainda sem integração pode existir somente durante migração
controlada. Para participar do runtime multi-WABA sem fallback, ela precisa de
uma integração ativa.

### Tabela nova final

O `bank_script.py` de instalação limpa deverá representar esta definição final:

```sql
CREATE TABLE chatbot.integracao_meta_unidade (
    id_unidade INT PRIMARY KEY,
    client_business_id VARCHAR(100) UNIQUE NOT NULL,
    bisu_access_token_criptografado TEXT NOT NULL,
    bisu_token_fingerprint CHAR(64) UNIQUE NOT NULL,
    pin_registro_criptografado TEXT NOT NULL,
    token_expires_at TIMESTAMPTZ,
    data_access_expires_at TIMESTAMPTZ,
    status_integracao VARCHAR(20) NOT NULL DEFAULT 'pendente',
    token_validado_em TIMESTAMPTZ,
    app_assinado_em TIMESTAMPTZ,
    numero_registrado_em TIMESTAMPTZ,
    ultima_verificacao_em TIMESTAMPTZ,
    ultimo_erro TEXT,
    criado_em TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    atualizado_em TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT fk_integracao_meta_unidade
        FOREIGN KEY (id_unidade)
        REFERENCES chatbot.unidade(id_unidade)
        ON DELETE RESTRICT,

    CONSTRAINT ck_integracao_meta_status
        CHECK (
            status_integracao IN (
                'pendente',
                'ativa',
                'erro',
                'revogada'
            )
        ),

    CONSTRAINT ck_integracao_meta_ativa_confirmada
        CHECK (
            status_integracao <> 'ativa'
            OR (
                token_validado_em IS NOT NULL
                AND app_assinado_em IS NOT NULL
                AND numero_registrado_em IS NOT NULL
                AND ultima_verificacao_em IS NOT NULL
            )
        )
);
```

Semântica dos campos:

- `id_unidade` como PK e FK impõe 1:1 sem um ID artificial;
- `client_business_id` identifica o portfólio do cliente e é único pela regra
  comercial da V1;
- `bisu_access_token_criptografado` contém apenas ciphertext autenticado;
- `bisu_token_fingerprint` é SHA-256/HMAC seguro para detectar reutilização
  acidental sem revelar o token;
- `pin_registro_criptografado` contém o PIN individual de seis dígitos;
- `token_expires_at=NULL` significa ausência de expiração programada
  confirmada, não “ainda não verificado”;
- `data_access_expires_at` permanece nullable porque é um prazo distinto;
- os quatro timestamps de confirmação tornam o onboarding retomável e
  auditável;
- `ultimo_erro` nunca recebe token, PIN, OTP ou corpo bruto da Meta.

O `bisu_subject_id` retornado pela Meta, quando existir, não é necessário para
roteamento nem autorização na V1. Ele pode ser adicionado no futuro como
metadado, mas não justifica outra tabela agora.

### Ajustes finais em tabelas existentes

No DDL de instalação limpa:

- `unidade.waba_id` passa a `NOT NULL` e `UNIQUE`;
- `unidade.phone_number_id` permanece `NOT NULL` e `UNIQUE`;
- `fila_mensagens.waba_id_origem` passa a
  `VARCHAR(100) NOT NULL`.

`waba_id_origem` não substitui `id_phone_unidade`. Os dois juntos permitem
provar que a mensagem veio da WABA esperada para aquele número.

Não será criada FK direta de `fila_mensagens.waba_id_origem` para `unidade`.
A fila é histórico operacional, e uma troca futura de WABA não deve apagar nem
invalidar a proveniência antiga. A validação é feita no momento da entrada e
novamente no worker.

### DDL final versus RDS atual

Quando a implementação começar, serão entregues dois arquivos completos:

1. `core/database/deploy/bank_script.py` com o `CREATE` final para instalação
   limpa;
2. um SQL versionado de transição do RDS com
   `CREATE/ALTER/BACKFILL/VALIDATE`.

O SQL do RDS não será inventado sem conferir os dados existentes. A sequência
segura será:

1. backup do RDS;
2. criar `integracao_meta_unidade`;
3. adicionar `waba_id_origem` nullable;
4. cadastrar e validar a integração piloto;
5. preencher a proveniência das filas ainda relevantes quando houver evidência
   inequívoca;
6. validar duplicidades e nulos em `unidade`;
7. criar índices/constraints `UNIQUE`;
8. aplicar `NOT NULL` somente depois do backfill;
9. comparar o catálogo do RDS com o DDL final;
10. nunca derrubar as tabelas operacionais para aplicar essa evolução.

O `bank_script.py` não guardará um histórico de `ALTER`. Ele sempre refletirá o
estado final desejado; o arquivo SQL de transição registra a mudança do banco
existente.

## Proteção das credenciais

### Segredos de ambiente

Continuam fora do Git:

- `META_ACCESS_TOKEN`: token do usuário de sistema `ed`;
- `META_APP_ID` e `META_APP_SECRET`;
- `META_WEBHOOK_VERIFY_TOKEN`;
- `META_CREDENTIAL_ENCRYPTION_KEY`: chave usada para criptografar BISUs e PINs;
- `META_LEGACY_FALLBACK_PHONE_IDS`: allowlist temporária e explícita do piloto.

O `.env.example` contém apenas nomes e exemplos neutros.

### Criptografia

A implementação deve usar criptografia autenticada, com chave fora do banco.
Não basta Base64 e não se deve usar somente hash para o token/PIN, porque esses
valores precisam ser recuperados para chamadas legítimas.

Regras:

- ciphertext no PostgreSQL;
- chave no ambiente da VM;
- valor puro somente em memória pelo tempo da chamada;
- campos do Admin são write-only;
- `repr`, exceções, métricas e logs mascaram segredos;
- token/PIN não aparecem em argumentos de terminal;
- rotação descriptografa com a chave anterior e recriptografa de forma
  controlada;
- o fingerprint não substitui o ciphertext.

### Fallback do piloto

O fallback legado:

- começa desativado por padrão;
- só pode ser habilitado junto com uma allowlist de `phone_number_id`;
- não aceita WABA desconhecida;
- emite alerta quando usado;
- não é tentado depois de `401` ou `403` de um BISU;
- é removido após o piloto receber seu próprio BISU.

## Fluxo administrativo Meta-first

### Formulário da unidade

O cadastro/alteração da unidade no Django Admin receberá:

- dados comerciais já existentes;
- `waba_id`;
- `phone_number_id`;
- `client_business_id`;
- BISU em campo write-only;
- PIN individual em campo write-only.

Na edição, deixar BISU/PIN vazios significa preservar os segredos atuais. Uma
substituição explícita inicia nova validação. O valor salvo nunca volta para a
tela.

### Orquestração ao enviar o formulário

O serviço de onboarding executará, nesta ordem:

1. validar formato local dos IDs e do PIN;
2. inspecionar o BISU em `/debug_token`;
3. confirmar `is_valid`, App emissor e permissões necessárias;
4. confirmar que o business da autorização é o
   `client_business_id` informado;
5. listar as WABAs autorizadas e exigir exatamente a WABA escolhida;
6. paginar `GET /{WABA_ID}/phone_numbers`;
7. confirmar que o `phone_number_id` pertence à WABA e corresponde ao número
   comercial informado;
8. executar `POST /{WABA_ID}/subscribed_apps`;
9. confirmar o App com `GET /{WABA_ID}/subscribed_apps`;
10. registrar o número quando necessário com
    `POST /{PHONE_NUMBER_ID}/register`;
11. consultar o número e confirmar o estado registrado;
12. produzir um resultado sem segredos contendo os timestamps confirmados;
13. abrir transação local;
14. salvar a unidade;
15. salvar/atualizar `integracao_meta_unidade` criptografada como `ativa`;
16. registrar `transaction.on_commit` para atualizar o cache da unidade;
17. confirmar o salvamento ao operador.

Se uma chamada Meta falhar:

- a unidade não é ativada;
- a alteração local sensível não é confirmada;
- o Admin mostra uma mensagem segura e acionável;
- nenhum token/PIN aparece na mensagem;
- o operador pode repetir o processo.

Se a Meta confirmar um efeito e o banco falhar depois, não existe rollback
distribuído automático. O serviço deve classificar a situação como
“reconciliação necessária”. A nova tentativa consulta o estado remoto antes de
repetir `subscribe` ou `register` e trata o estado já confirmado como sucesso
idempotente.

### Estado e operações posteriores

O Admin também oferecerá ações explícitas:

- validar novamente a integração;
- substituir/rotacionar o BISU;
- substituir o PIN;
- refazer/confirmar `subscribed_apps`;
- refazer/confirmar o registro do número;
- diagnosticar sem revelar segredos;
- iniciar offboarding com confirmação adicional.

Excluir uma linha no Admin não deve desregistrar silenciosamente o telefone.
Offboarding é efeito externo destrutivo e exige uma ação própria.

## Resolução de credencial no runtime

### Envio de mensagens

`conta_wa(phone_number_id)` deixará de capturar `META_ACCESS_TOKEN` no import.
Ela resolverá:

```text
phone_number_id
  -> unidade ativa
  -> integracao_meta_unidade ativa
  -> descriptografar BISU em memória
  -> construir cliente PyWa/Graph
```

Todos os senders das etapas 1 a 19 já passam pelo cliente compartilhado. Assim,
não será necessário inserir lógica de token em cada etapa. Os arquivos de
mensagem e as regras do funil não mudam.

### Webhook

O webhook deve percorrer todos os:

- `entry[]`;
- `changes[]`;
- `value.messages[]`;
- `value.statuses[]`;
- contatos e metadados correlacionados a cada `value`.

“Processar todos os eventos” não significa colocar tudo na fila. Significa:

- cada mensagem recebida é normalizada e avaliada;
- statuses de enviado/entregue/lido/falhou seguem um caminho separado;
- eventos sem mensagem não viram mensagens fictícias;
- um item inválido não impede os demais itens válidos do lote;
- a assinatura HTTP e o limite de tamanho são verificados uma vez por request.

Para cada mensagem:

1. `entry.id` fornece o `waba_id_origem`;
2. `metadata.phone_number_id` fornece o número receptor;
3. `message.from` fornece o `wa_id` do cliente final;
4. o banco resolve a unidade pelo `phone_number_id`;
5. o webhook exige igualdade com `unidade.waba_id`;
6. o webhook exige integração ativa;
7. só então grava a fila com a proveniência.

O status HTTP deve permitir reentrega do que realmente falhou sem duplicar os
itens já persistidos. A idempotência por `wamid` continua obrigatória.

### Worker principal

Ao retirar a fila, o worker recebe `waba_id_origem` e repete:

- unidade do `id_phone_unidade` ainda existe e está ativa;
- `waba_id_origem == unidade.waba_id`;
- integração 1:1 ainda está ativa;
- BISU válido pertence àquela unidade;
- o envio usa o `phone_number_id` daquela mesma unidade.

Uma divergência é erro de segurança/roteamento, não motivo para tentar o token
global. A mensagem vai para retry/erro conforme a política existente, com
alerta sem segredo.

### Reconciliação

`block_report.py` e utilitários semelhantes deixam de consultar apenas o
`META_WABA_ID` global. Eles listam as integrações ativas e processam cada WABA
com seu BISU isolado.

Falha de uma unidade:

- não interrompe as demais;
- não apaga o resultado da unidade anterior;
- identifica apenas IDs não sensíveis no log;
- preserva paginação e limites da Graph API.

### Cliente global

O cadastro do cliente continua global por telefone/`wa_id`, conforme decisão
de negócio. A mesma pessoa conserva um `id_cliente` ao conversar com duas
unidades, enquanto cada unidade mantém sua própria conversa. Nome, idade e
e-mail podem ser atualizados pelo atendimento mais recente.

Uma futura tabela de perfil por cliente/unidade permanece fora desta versão.

### Worker do funil

Nenhuma credencial Meta é necessária para materializar/enviar o funil atual. A
regra de elegibilidade das etapas 16 a 19 e `lead_no_funil` não muda. O
`worker_funil` deve receber apenas testes de regressão e observabilidade de
deploy; ele não participa do roteamento BISU.

## Utilitários Graph API necessários

Todos os utilitários recebem `access_token` explicitamente ou usam um resolver
por unidade. Nenhum lê silenciosamente `META_ACCESS_TOKEN` para um cliente.

| Operação | Responsabilidade |
|---|---|
| trocar código | trocar imediatamente o código do Embedded Signup pelo BISU |
| inspecionar token | validar App, business, permissões, `is_valid` e prazos |
| listar WABAs | confirmar os `target_ids` autorizados |
| listar números | paginar `/{WABA_ID}/phone_numbers` |
| assinar App | `POST /{WABA_ID}/subscribed_apps` |
| confirmar assinatura | `GET /{WABA_ID}/subscribed_apps` |
| solicitar OTP | `POST /{PHONE_NUMBER_ID}/request_code` quando aplicável |
| verificar OTP | `POST /{PHONE_NUMBER_ID}/verify_code` |
| registrar número | `POST /{PHONE_NUMBER_ID}/register` com PIN da unidade |
| consultar número | confirmar status e identidade do telefone |
| desregistrar número | somente em offboarding aprovado |
| enviar teste | `POST /{PHONE_NUMBER_ID}/messages` com o BISU correto |
| diagnosticar | reunir estado sem imprimir segredos |

`ativando_waba_id.py` permanece útil: `subscribed_apps` é exatamente a
assinatura do App atual na nova WABA. Ele não cria outro App nem outro webhook.

## Plano de implementação arquivo por arquivo

### Regra obrigatória de entrega

Este Markdown é a especificação. Durante a implementação, cada passo abaixo
deve alterar ou criar **um único arquivo** e entregar:

1. objetivo do arquivo;
2. caminho;
3. conteúdo final completo do arquivo;
4. testes que o validam;
5. comando de verificação;
6. dependências anteriores;
7. risco e rollback quando houver efeito externo.

Não serão aceitos `...`, pseudocódigo, “restante igual” ou trechos omitidos.
Arquivos grandes existentes também serão entregues completos. Se uma
responsabilidade puder ser extraída para um módulo menor, o módulo novo vem em
um passo próprio e o chamador completo em outro.

O plano não executa agora essas mudanças; ele fixa a ordem e o conteúdo exigido
para a fase de implementação.

### Fase 1 — Dependências e configuração

| Passo | Arquivo único | Resultado completo exigido |
|---:|---|---|
| 1.1 | `requirements.txt` | incluir somente a biblioteca de criptografia escolhida, com versão compatível |
| 1.2 | `.env.example` | documentar chave de criptografia, token global ESL e allowlist de fallback sem segredos |
| 1.3 | `core/integrations/whatsapp/tools/config.py` | validar configurações globais e impedir fallback aberto |
| 1.4 | `tests/unit/test_configuracao_meta_multi_waba.py` | provar falha fechada, allowlist e ausência de segredo em mensagens |

O arquivo de configuração existente será ampliado; não será criado outro
módulo concorrente para a mesma responsabilidade.

### Fase 2 — DDL e models

| Passo | Arquivo único | Resultado completo exigido |
|---:|---|---|
| 2.1 | `core/database/deploy/bank_script.py` | DDL final limpo com a única tabela 1:1, constraints finais e `waba_id_origem` |
| 2.2 | `deploy/sql/v1_0_0_integracao_meta_unidade.sql` | transição idempotente e revisável do RDS atual, sem apagar dados |
| 2.3 | `callback/webhook/models.py` | model 1:1 `IntegracaoMetaUnidade`, `Unidade.waba_id` final e fila com proveniência |
| 2.4 | `tests/unit/test_ddl_integracao_meta_unidade.py` | compatibilidade entre DDL, constraints e models |

O arquivo SQL só será fechado depois de uma consulta read-only ao catálogo e
aos dados atuais. O `bank_script.py` já nascerá com o estado final.

### Fase 3 — Criptografia e repositório

| Passo | Arquivo único | Resultado completo exigido |
|---:|---|---|
| 3.1 | `core/integrations/whatsapp/credentials/__init__.py` | exportações públicas mínimas |
| 3.2 | `core/integrations/whatsapp/credentials/types.py` | tipos imutáveis sem `repr` de segredo |
| 3.3 | `core/integrations/whatsapp/credentials/crypto.py` | criptografar, descriptografar e gerar fingerprint sem logar valores |
| 3.4 | `core/repositories/unidades/integracao_meta.py` | consultas por unidade, WABA e telefone usando parâmetros SQL |
| 3.5 | `core/integrations/whatsapp/credentials/resolver.py` | resolver BISU/PIN e aplicar fallback somente à allowlist |
| 3.6 | `tests/unit/test_meta_credentials_crypto.py` | round-trip, chave errada, ciphertext adulterado e mascaramento |
| 3.7 | `tests/unit/test_meta_credentials_resolver.py` | isolamento A/B, revogação, expiração e fallback fechado |

O repositório retorna ciphertext e metadados. Somente o resolver
descriptografa, imediatamente antes da chamada.

### Fase 4 — Cliente Graph central

| Passo | Arquivo único | Resultado completo exigido |
|---:|---|---|
| 4.1 | `core/integrations/whatsapp/graph/__init__.py` | interface pública mínima |
| 4.2 | `core/integrations/whatsapp/graph/exceptions.py` | erros tipados e seguros |
| 4.3 | `core/integrations/whatsapp/graph/client.py` | timeout, paginação, retry permitido e redaction |
| 4.4 | `tests/unit/test_meta_graph_client.py` | paginação, timeout, erros Meta e ausência de token no log |

O cliente não possui token default. Toda instância exige credencial explícita.

### Fase 5 — Onboarding idempotente

| Passo | Arquivo único | Resultado completo exigido |
|---:|---|---|
| 5.1 | `core/integrations/whatsapp/onboarding/__init__.py` | interface pública do serviço |
| 5.2 | `core/integrations/whatsapp/onboarding/types.py` | comando e resultado sem segredos |
| 5.3 | `core/integrations/whatsapp/onboarding/service.py` | sequência Meta-first completa, confirmações e retomada idempotente |
| 5.4 | `tests/unit/test_meta_onboarding_service.py` | ordem das chamadas, falhas em cada etapa, repetição segura e isolamento |

O serviço recebe token e PIN em memória. Ele não grava banco por conta própria;
retorna material já validado/criptografado para a camada administrativa
persistir em transação.

### Fase 6 — Utilitários existentes

Cada arquivo abaixo é entregue em um passo separado e completo:

| Passo | Arquivo único | Resultado completo exigido |
|---:|---|---|
| 6.1 | `core/integrations/whatsapp/tools/ativando_waba_id.py` | token explícito, subscribe e confirmação |
| 6.2 | `core/integrations/whatsapp/tools/desativa_waba_id.py` | token explícito e offboarding seguro |
| 6.3 | `core/integrations/whatsapp/tools/ativando_numero.py` | token/PIN explícitos ou resolvidos pela unidade |
| 6.4 | `core/integrations/whatsapp/tools/desativando_numero.py` | credencial correta e confirmação destrutiva |
| 6.5 | `core/integrations/whatsapp/tools/block_report.py` | iteração isolada por integração ativa |
| 6.6 | `tests/unit/test_meta_tools_multi_waba.py` | A/B, paginação, 401/403 e nenhum fallback cruzado |

### Fase 7 — Envio e webhook

| Passo | Arquivo único | Resultado completo exigido |
|---:|---|---|
| 7.1 | `core/integrations/whatsapp/pywa_functions/cliente.py` | construir cliente pelo `phone_number_id` e BISU resolvido |
| 7.2 | `tests/unit/test_cliente_pywa_multi_waba.py` | credencial correta por unidade e nenhum token no import |
| 7.3 | `callback/webhook/services/meta_eventos.py` | normalizar todos os entries, changes, messages e statuses |
| 7.4 | `callback/webhook/services/post_flow.py` | validar e processar cada evento sem perder os demais |
| 7.5 | `callback/webhook/services/populating_fila_mensagens.py` | persistir `waba_id_origem` e manter idempotência por `wamid` |
| 7.6 | `callback/webhook/services/flood_guard.py` | contar apenas mensagens normalizadas únicas |
| 7.7 | `callback/webhook/views.py` | uma validação de assinatura/tamanho e resposta correta ao lote |
| 7.8 | `tests/unit/test_webhook_meta_lotes.py` | matrizes multi-entry/multi-WABA, statuses e falhas parciais |

Antes de alterar `views.py`, a implementação deve preservar o contrato de
verificação do webhook já publicado na Meta.

### Fase 8 — Worker e cache

| Passo | Arquivo único | Resultado completo exigido |
|---:|---|---|
| 8.1 | `workers/worker_flow/suporte/estado_ciclo.py` | transportar `waba_id_origem` sem mudar regras de etapa |
| 8.2 | `workers/worker_flow/valida_banco.py` | repetir a validação WABA/número/integração |
| 8.3 | `workers/worker_flow/response_flow/flow_sender.py` | enviar pelo cliente resolvido da unidade |
| 8.4 | `core/cache/cache_unidade.py` | cachear apenas roteamento não sensível e curar por banco |
| 8.5 | `tests/unit/test_worker_flow_meta_proveniencia.py` | divergência, retry, revogação e isolamento A/B |
| 8.6 | `tests/unit/test_cache_meta_unidade.py` | miss consulta banco, divergência cura cache e segredo nunca entra no Redis |

`cache_unidade.py` continua responsável somente por roteamento não sensível;
BISU e PIN permanecem fora do Redis.

### Fase 9 — Django Admin

| Passo | Arquivo único | Resultado completo exigido |
|---:|---|---|
| 9.1 | `callback/webhook/admin.py` | campos write-only, orquestração Meta-first, mensagens seguras e ações explícitas |
| 9.2 | `tests/unit/test_admin_integracao_meta_unidade.py` | sucesso, falha Meta, falha DB, rotação, repetição e ausência de segredo |

O Admin chama o serviço uma vez no envio do formulário. A tabela de integração
pode ser exibida como estado/auditoria, mas o token e o PIN jamais são
visualizados.

### Fase 10 — Deploy e documentação

| Passo | Arquivo único | Resultado completo exigido |
|---:|---|---|
| 10.1 | `deploy/systemd/chatbot-webhook.service` | manter leitura segura do ambiente sem expor segredo |
| 10.2 | `deploy/systemd/chatbot-worker-flow.service` | mesma configuração de credenciais do webhook |
| 10.3 | `deploy/systemd/chatbot-worker-funil.service` | regressão sem dependência Meta desnecessária |
| 10.4 | `deploy/README.md` | ordem de atualização, checks e rollback |
| 10.5 | `meta_anotacoes/README.md` | topologia final e distinção System User/BISU |

Arquivos systemd só serão modificados se a auditoria mostrar necessidade real.
Se já estiverem corretos, o passo registra a verificação e não cria diff
artificial.

## Matriz mínima de testes

### Credenciais

- BISU A nunca abre WABA B;
- token revogado A não afeta B;
- token com prazo é recusado depois do prazo;
- token sem prazo fica com `token_expires_at=NULL` após `debug_token`;
- BISU duplicado em duas unidades é rejeitado;
- PIN nunca aparece em formulário de edição, log ou exceção;
- chave incorreta falha de forma fechada;
- fallback só funciona para o piloto listado.

### Admin/onboarding

- todos os campos válidos: Meta confirma e banco ativa;
- `debug_token` inválido: nada é ativado;
- business divergente: bloqueio;
- WABA fora dos `target_ids`: bloqueio;
- telefone fora da WABA: bloqueio;
- subscribe falha: banco não marca assinatura;
- register já confirmado: repetição idempotente;
- Meta conclui e banco falha: aviso de reconciliação;
- edição sem novo token/PIN preserva ciphertext;
- rotação substitui apenas a unidade escolhida.

### Webhook

- dois `entry[]` no mesmo payload;
- dois `changes[]`;
- várias mensagens;
- mensagens e statuses no mesmo `value`;
- duas WABAs no mesmo request;
- primeira inválida e segunda válida;
- `entry.id` divergente do telefone;
- reentrega do mesmo `wamid`;
- status não vira item de fila;
- `waba_id_origem` chega íntegro ao banco.

### Worker

- fila A usa BISU A;
- divergência WABA/telefone impede envio;
- integração revogada entra na política de erro/retry;
- ausência no cache consulta PostgreSQL;
- cache errado é curado;
- etapas 1 a 19 mantêm comportamento;
- etapas 16 a 19 continuam elegíveis ao funil;
- somente etapa 19 encerra a conversa;
- `lead_no_funil` continua sendo a marca de envio.

### Banco e deploy

- DDL final e models coincidem;
- tabela 1:1 é imposta pelo PK/FK;
- IDs de WABA e telefone são únicos;
- ciphertext nunca é igual ao valor puro;
- RDS recebe ALTER sem apagar tabelas;
- os três serviços sobem depois do deploy;
- webhook responde `200`;
- worker principal e funil não reiniciam em loop.

## Ordem de rollout

### Etapa 0 — Preparação

- backup do RDS;
- snapshot da Lightsail;
- branch `prod` limpa;
- chave de criptografia criada fora do Git;
- App Review/Tech Provider e webhook conferidos;
- configuração do Hosted Embedded Signup sem a opção de 60 dias;
- fallback do piloto fechado por allowlist.

### Etapa 1 — Schema expansivo

- criar a tabela 1:1;
- adicionar `waba_id_origem` nullable;
- publicar models e repositório sem trocar o runtime;
- validar o catálogo e os dados;
- não aplicar `NOT NULL` antes do backfill.

### Etapa 2 — Piloto

- obter BISU próprio do portfólio Método Supera;
- validar/criptografar token e PIN;
- assinar App e confirmar número;
- cadastrar a integração piloto;
- publicar resolver e Admin;
- manter fallback somente enquanto o piloto é observado.

### Etapa 3 — Runtime protegido

- publicar cliente de envio por unidade;
- publicar webhook em lote e proveniência;
- publicar revalidação no worker;
- adaptar reconciliação;
- executar testes ponta a ponta.

### Etapa 4 — Segundo cliente real

- executar o Plano 1 com o cliente B;
- cadastrar pelo Admin;
- confirmar BISU B/WABA B/phone B;
- testar isolamento A/B;
- provocar falha controlada em B e confirmar A saudável.

### Etapa 5 — Constraints finais

- completar backfill;
- validar ausência de nulos/duplicados;
- aplicar `UNIQUE` e `NOT NULL` finais;
- comparar RDS com `bank_script.py`;
- desabilitar e remover o fallback global do caminho de clientes.

## Critérios de aceite da V1.0.0 multi-WABA

- [ ] Um App e um webhook atendem todas as WABAs autorizadas.
- [ ] O token do `ed` permanece somente no ambiente da ESL/piloto temporário.
- [ ] Cada unidade possui um BISU próprio criptografado.
- [ ] Cada unidade possui uma WABA e um número únicos.
- [ ] Há apenas uma nova tabela de integração 1:1.
- [ ] A fila preserva `waba_id_origem`.
- [ ] Admin executa Meta-first no envio do formulário.
- [ ] Subscribe/register são confirmados e idempotentes.
- [ ] Webhook percorre todos os eventos do lote.
- [ ] Worker revalida WABA/número antes de enviar.
- [ ] `conta_wa` resolve o BISU por unidade.
- [ ] Falha/revogação de A não afeta B.
- [ ] Tokens/PINs não aparecem em Git, Redis, Admin ou logs.
- [ ] Cliente continua global e conversa continua por unidade.
- [ ] Fluxo, etapas e funil não mudam.
- [ ] DDL final, SQL de transição, models e RDS estão compatíveis.
- [ ] Um segundo cliente real passou no teste ponta a ponta.

## Fora da V1.0.0

- portal próprio de Embedded Signup;
- JavaScript que chama a Meta enquanto campos são digitados;
- múltiplas WABAs ou múltiplos números por unidade;
- um usuário humano/System User manual por WABA;
- tabela `usuario_meta`;
- cache de token no Redis;
- perfil do consumidor separado por unidade;
- interface comercial para pausar o bot;
- persistência completa de todos os statuses de entrega;
- migração automatizada entre BSPs.

## Fontes oficiais

- [Access Tokens](https://developers.facebook.com/documentation/business-messaging/whatsapp/access-tokens)
- [Facebook Login for Business — BISU](https://developers.facebook.com/documentation/facebook-login/facebook-login-for-business#business-integration-system-user-access-tokens)
- [Embedded Signup](https://developers.facebook.com/documentation/business-messaging/whatsapp/embedded-signup/overview)
- [Solution Providers](https://developers.facebook.com/documentation/business-messaging/whatsapp/solution-providers/overview)
- [Tech Provider onboarding](https://developers.facebook.com/documentation/business-messaging/whatsapp/solution-providers/get-started-for-tech-providers)
- [Debug Token](https://developers.facebook.com/docs/graph-api/reference/debug_token/)
- [Subscribe to a WABA](https://www.postman.com/meta/whatsapp-business-platform/request/26gui66/subscribe-to-a-waba)
- [Webhook Payload Reference](https://www.postman.com/meta/whatsapp-business-platform/folder/vzaxn16/webhook-payload-reference)
