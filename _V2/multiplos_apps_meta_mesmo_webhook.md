# Multiplos Apps Meta no Mesmo Webhook - V2

## Objetivo

Permitir que dois ou mais aplicativos Meta utilizem a mesma URL HTTPS de
webhook sem enfraquecer a verificacao de autenticidade das requisicoes.

Arquitetura esperada:

```text
App Meta A ---\
               -> https://dominio.com/webhook/
App Meta B ---/
```

Cada aplicativo continuara independente e tera:

- seu proprio `App ID`;
- seu proprio `App Secret`;
- suas proprias inscricoes de eventos;
- uma ou mais WABAs vinculadas;
- os respectivos `phone_number_id` cadastrados no banco.

## Estado Atual da V1

A V1 valida `X-Hub-Signature-256` com apenas um segredo:

```text
META_APP_SECRET
```

A implementacao atual esta em:

```text
callback/webhook/services/meta_signature.py
```

Portanto, apenas eventos assinados pelo aplicativo correspondente a esse
segredo sao aceitos quando `META_WEBHOOK_SIGNATURE_REQUIRED` esta ativo.

Configurar um segundo aplicativo na mesma URL sem adaptar essa verificacao
faria os eventos dele serem rejeitados por assinatura incompativel. Desativar
a verificacao de assinatura nao e uma solucao aceitavel para producao.

## Implementacao Futura

### 1. Configuracao dos aplicativos

Em cada aplicativo Meta:

1. cadastrar a mesma Callback URL HTTPS;
2. validar a URL com o Verify Token;
3. assinar o campo `messages`;
4. inscrever o aplicativo na WABA correspondente por
   `POST /{WABA_ID}/subscribed_apps`;
5. garantir que os numeros e WABAs estejam cadastrados na unidade correta.

O Verify Token e usado apenas no `GET` inicial de verificacao. Ele nao e o
`App Secret`. Pode ser compartilhado entre os aplicativos ou a aplicacao pode
aceitar um conjunto de tokens distintos.

### 2. Armazenamento dos App Secrets

Substituir o segredo unico por uma colecao segura de segredos ativos. Exemplo
conceitual para desenvolvimento:

```text
META_APP_SECRETS=secret_app_a,secret_app_b
```

Em producao, priorizar AWS Secrets Manager ou Parameter Store. Segredos nunca
devem ser salvos em logs, banco sem protecao, documentacao ou mensagens de
erro exibidas ao usuario.

### 3. Validacao da assinatura

Para cada `POST` recebido:

```text
capturar X-Hub-Signature-256
-> calcular HMAC-SHA256 do corpo bruto com cada App Secret ativo
-> comparar em tempo constante
-> aceitar se exatamente um segredo for compativel
-> rejeitar se nenhum segredo for compativel
```

Com poucos aplicativos, testar os segredos ativos e simples e barato. A
comparacao deve continuar usando `hmac.compare_digest`.

O corpo usado no HMAC precisa ser exatamente `request.body`, antes de qualquer
normalizacao ou nova serializacao do JSON.

### 4. Identificacao da unidade

Depois que a assinatura for validada, o fluxo continua identificando a origem
pelos dados operacionais do payload:

```text
WABA ID
phone_number_id
```

O `phone_number_id` deve permanecer como chave de roteamento para localizar a
unidade. Um numero desconhecido nao deve entrar na fila de atendimento.

Nao se deve confiar no WABA ID ou no `phone_number_id` para substituir a
assinatura HMAC. Esses identificadores orientam o roteamento somente depois da
autenticidade da requisicao ter sido confirmada.

## Alternativa Preferencial

Quando possivel, usar um unico aplicativo Meta com varias WABAs inscritas. Essa
estrutura reduz:

- quantidade de App Secrets;
- configuracoes duplicadas;
- risco de inscricao incorreta;
- complexidade de rotacao de credenciais;
- superficie de auditoria.

Usar varios aplicativos apenas quando houver uma necessidade operacional,
contratual ou de isolamento que justifique a complexidade adicional.

## Logs e Observabilidade

Registrar sem expor segredos:

```text
assinatura_meta_ok | app_identificado=<apelido_interno>
assinatura_meta_falhou | motivo=nenhum_secret_compativel
webhook_origem | waba_id=<mascarado> phone_number_id=<mascarado>
```

O apelido interno do aplicativo pode ser registrado, mas nunca o App Secret.

## Testes Minimos

1. assinatura valida do App A e aceita;
2. assinatura valida do App B e aceita;
3. assinatura invalida e rejeitada;
4. assinatura ausente e rejeitada em producao;
5. corpo alterado depois da assinatura e rejeitado;
6. verificacao `GET` funciona para todos os tokens configurados;
7. WABA conhecida e roteada para a unidade correta;
8. `phone_number_id` desconhecido nao entra na fila;
9. evento de um app nao e confundido com unidade pertencente ao outro;
10. rotacao de um segredo nao interrompe temporariamente o outro app.

## Criterios de Conclusao

A tarefa da V2 estara concluida quando:

- a mesma URL estiver verificada nos aplicativos desejados;
- todos os aplicativos enviarem eventos reais para o endpoint;
- a assinatura de cada aplicativo for validada corretamente;
- nenhuma assinatura desconhecida for aceita;
- WABA e `phone_number_id` continuarem roteando para a unidade correta;
- a V1 permanecer compativel com configuracao de apenas um aplicativo;
- houver procedimento documentado para adicionar, remover e rotacionar um
  App Secret.
