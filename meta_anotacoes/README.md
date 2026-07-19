# Anotações da infraestrutura Meta da ESL

> Registro técnico do estado observado e das decisões de arquitetura em
> 18/07/2026. As telas da Meta mudam com frequência; antes de executar um novo
> onboarding, confronte este material com a documentação oficial atual.

## Estrutura confirmada nas contas Meta

- **May S. Lemos e Levi** são administradores humanos e devem usar perfis
  pessoais autênticos, cada um com seu próprio acesso e autenticação em dois
  fatores.
- **ESL Soluções Tec** é o Business Portfolio da empresa provedora.
- O App Meta **Supera Santo Antônio de Jesus** é propriedade formal do
  portfólio ESL Soluções Tec.
- O usuário de sistema **`ed`** pertence ao portfólio ESL. Ele é uma identidade
  de máquina da provedora, não um usuário humano e não um usuário de um
  franqueado.
- **Método Supera Santo Antônio de Jesus** é o portfólio do cliente piloto e
  permanece proprietário da própria WABA e do próprio número.
- A WABA do cliente foi compartilhada com a ESL como ativo de parceiro e
  atribuída ao usuário de sistema `ed` no piloto.

Não deve ser criado um perfil pessoal fictício chamado "ESL Tech". A empresa é
representada pelo Business Portfolio; pessoas reais administram esse portfólio
com seus perfis autênticos.

## Piloto atual versus arquitetura definitiva

### Piloto atual

```text
Portfólio ESL
├── App da ESL
├── usuário de sistema ed
│   └── System User Access Token da ESL
└── acesso de parceiro à WABA piloto
    └── phone_number_id piloto
```

O token do `ed` pode funcionar no piloto porque a WABA foi compartilhada com a
ESL e atribuída a esse usuário de sistema. Ele é adequado para validar a
integração e administrar ativos próprios ou explicitamente compartilhados.

Esse token não deve virar a credencial universal de runtime de todos os
clientes da ESL.

### Alvo como Tech Provider

```text
Portfólio ESL
├── 1 App Meta da ESL
├── 1 webhook da ESL
├── usuário de sistema ed + token da ESL
│   └── administração, bootstrap e contingência de ativos da própria ESL
└── N autorizações de clientes
    ├── cliente A ── BISU A ── WABA A ── phone_number_id A
    ├── cliente B ── BISU B ── WABA B ── phone_number_id B
    └── cliente C ── BISU C ── WABA C ── phone_number_id C
```

**BISU** significa *Business Integration System User access token*. Ele nasce
da autorização do cliente no Embedded Signup/Facebook Login for Business e é
a credencial usada pelo backend para operar os ativos daquele cliente.

O BISU não exige criar manualmente um novo usuário de sistema no portfólio ESL
para cada WABA. A identidade de integração é administrada pela Meta e o sistema
da ESL armazena a autorização e o segredo de maneira segura.

## Cardinalidade adotada na V1.0.0

A regra comercial inicial será:

```text
1 cliente = 1 Business Portfolio = 1 autorização = 1 BISU ativo
          = 1 WABA = 1 phone_number_id
```

Por isso, durante a V1, parecerá existir "um BISU por WABA". A causa correta,
porém, é haver uma autorização isolada por cliente. Se no futuro um mesmo
cliente autorizar várias WABAs no mesmo *grant*, um único BISU poderá operar as
WABAs explicitamente incluídas nos escopos desse *grant*.

Portanto:

- não criar um App por cliente;
- não criar um usuário humano por WABA;
- não criar um usuário de sistema `ed-A`, `ed-B`, `ed-C` por WABA;
- não gerar um System User Access Token da ESL por WABA;
- obter e isolar um BISU por integração de cliente;
- usar somente uma credencial em cada chamada Graph API: o BISU do cliente
  daquela operação, nunca o BISU e o token do `ed` ao mesmo tempo.

## Onde cada segredo participa

| Segredo | Escopo | Uso |
|---|---|---|
| App Secret | Global do único App | Validar `X-Hub-Signature-256` no webhook |
| Webhook verify token | Global do único App | Verificação inicial do endpoint do webhook |
| Token de usuário do sistema `ed` | Portfólio ESL | Administração/bootstrap de ativos da ESL e piloto controlado |
| BISU do cliente | Uma autorização de cliente | Envio de mensagens e operações Graph API nos ativos autorizados |
| PIN | Um número | Registro/verificação em duas etapas do `phone_number_id` |

O webhook de entrada não recebe BISU. Ele identifica a origem por
`entry.id` (`waba_id`) e `metadata.phone_number_id` e valida a autenticidade com
o App Secret. O `worker_flow`, ao enviar uma resposta, resolve:

```text
phone_number_id -> unidade -> WABA -> integração do cliente -> BISU
```

O BISU deve ficar criptografado ou em um gerenciador de segredos. Ele nunca
deve ser salvo em texto puro na fila, no histórico, no cache de cliente ou em
logs.

## Acesso do cliente ao App da ESL

Na tela inspecionada, o portfólio Método Supera aparece como parceiro com
controle total do App da ESL. Isso pode permanecer no piloto quando for uma
decisão consciente, mas não é requisito para cada novo cliente operar a própria
WABA pelo App da provedora.

Para os próximos clientes, aplicar menor privilégio: o cliente autoriza e
mantém a propriedade da WABA e do número; a ESL recebe somente os acessos
necessários para prestar o serviço. Não conceder automaticamente controle
administrativo do App da ESL a cada franqueado.

## Fontes oficiais

- [Guia de tokens de acesso do WhatsApp](https://developers.facebook.com/documentation/business-messaging/whatsapp/access-tokens)
- [Facebook Login for Business e BISU](https://developers.facebook.com/documentation/facebook-login/facebook-login-for-business#business-integration-system-user-access-tokens)
- [Embedded Signup](https://developers.facebook.com/documentation/business-messaging/whatsapp/embedded-signup/overview)
- [Visão geral para Solution Providers](https://developers.facebook.com/documentation/business-messaging/whatsapp/solution-providers/overview)

