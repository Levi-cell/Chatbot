# Integração WhatsApp

Comunicação com a Meta WhatsApp Cloud API por meio da biblioteca PyWa.

- [Portal do projeto](../../../README.md)
- [Regras de negócio](../../../REGRAS_DE_NEGOCIO.md)
- [Padrões de arquitetura](../../../PADROES_DE_ARQUITETURA.md#whatsapp-e-pywa)
- [Integrações externas](../README.md)

## Estrutura

```text
core/integrations/whatsapp/
├── exceptions.py
├── numero_comercial.py
├── messages/
│   ├── etapa1_messages.py ... etapa22_messages.py
│   ├── componentes_compartilhados.py
│   ├── followup_messages.py
│   ├── tratamentos_universais.py
│   └── triagem_componentes.py
├── pywa_functions/
│   ├── cliente.py
│   ├── saudacao.py
│   ├── resposta_envio.py
│   ├── ferramentas.md
│   └── pywa_senders/
│       ├── etapa1.py ... etapa22.py
│       ├── followup.py
│       └── triagem_base.py
└── tools/
    ├── ativando_numero.py
    ├── ativando_waba_id.py
    ├── config.py
    ├── desativando_numero.py
    ├── desativa_waba_id.py
    ├── usuarios.py
    └── validando_phone_waba.py
```

## Direção das dependências

```text
worker -> pywa_functions -> messages
                      |--> cliente PyWa
                      `--> Meta
```

`messages` não importa PyWa. `pywa_senders` pode importar `messages`, cliente e
exceções da integração. Nenhum deles controla banco, fila, transição ou retry.

## Messages

Catálogo de conteúdo enviado:

- textos;
- títulos de botão;
- callbacks;
- funções puras de montagem.

Textos de WhatsApp não devem ser escritos diretamente no worker. Alterar uma
mensagem não deve mover a responsabilidade de envio para `messages`.

Cada etapa de 1 a 22 mantém seu próprio arquivo `etapaN_messages.py`.

As mensagens oferecem uma **experiência Supera gratuita**, com demonstração prática exclusiva
e **sua reserva** de dia e horário. Os botões das etapas 7 e 9 exibem **Quero reservar**;
a etapa 18 usa **Já reservei**. O aceite por texto continua reconhecendo expressões
antigas como `quero agendar` e `já agendei`, conforme a etapa. Perguntas sobre como
reservar não são aceites; na etapa 18, intenção de reservar não comprova conclusão.

A gratuidade se refere à experiência; o tratamento financeiro explica que os
valores de investimento são definidos após ela, com orientação da equipe.
O prefixo é compartilhado em `tratamentos_universais.py`; cada etapa fornece
sua pergunta de retomada, introduzida por `Mas bora lá:` uma única vez.
Não há personalização por diretor nem campos
adicionais na unidade. Os montadores são puros, e o histórico conserva o
texto efetivamente enviado. Respostas já persistidas não são reenviadas.

Os corpos das mensagens usam negrito do WhatsApp (`*texto*`) com moderação,
priorizando a experiência oferecida e a ação principal. Evitar destacar todas
as palavras ou repetir o convite completo nos tratamentos financeiros.
Títulos de botões e valores usados pelos validadores permanecem sem marcação.

Na etapa 2, negativas sem destino alternativo repetem a pergunta. Uma
correção explícita como `Não, é para mim` conserva a escolha indicada.
Na oferta e na reserva, dúvidas curtas como `É gratuita?` retomam a
experiência. Fora desse contexto, o termo feminino precisa estar ligado
explicitamente à demonstração ou experiência. O aceite flexível permanece.

A retomada da etapa 9 usa uma única saudação, tanto após follow-up quanto
após três horas de inatividade. As referências ao dependente permanecem
explícitas; titular e dependente não trocam de papel.

As apresentações inicial padrão, de mídia, financeira e de tratamento de
reforço escolar da etapa 1 recebem `nome_unidade`, `nome_agente` e `genero` como
argumentos já validados pelo worker. `messages` apenas escolhe `o` ou `a` e
formata o texto; não consulta o banco nem conhece a conversa.

`componentes_compartilhados.py` também monta `Olá novamente, <nome>!` quando
o cliente retorna com `followup_stage = 0` pelo menos três horas após o último envio confirmado do bot
na mesma conversa. A etapa 1 fica fora da regra; nome ou datas ausentes ou
incompatíveis não interrompem o atendimento e não produzem prefixo.

O worker fornece o contexto histórico e aplica a saudação à resposta corrente,
inclusive tratamentos, sem mudar o destino. Não é follow-up, mensagem separada
ou disparo automático após três horas de inatividade. No retry com resposta
persistida, não há novo envio.

## PyWa functions

Concentra a criação do cliente PyWa e o transporte das mensagens do fluxo. Os
senders são o local normal para chamadas de envio; operações compartilhadas de
bloqueio e desbloqueio ficam em `tools/usuarios.py`, que reutiliza a mesma
fábrica de cliente em `pywa_functions/cliente.py`.

- `cliente.py`: normaliza `phone_id`, cria `WhatsApp` e aplica o prefixo de
  retorno somente no escopo do envio corrente;
- `saudacao.py`: seleção de bom dia, boa tarde ou boa noite pelo horário do
  atendimento inicial, distinta da saudação de retorno;
- `resposta_envio.py`: extrai o ID confirmado pela Meta e falha se ele faltar;
- `pywa_senders/etapaN.py`: mensagens normais e tratamentos específicos da
  etapa N.

Cada sender escolhe conteúdo, legenda e lista de botões, realiza a chamada PyWa
e devolve um contexto técnico com o ID da Meta e a etapa da mensagem enviada.
O sender não escolhe origem, evento ou destino da transição.

O encaminhamento de suporte ao idoso é um sender da etapa 6 com botão para o
número comercial, normalizado por `numero_comercial.py`. A decisão de usar
`idade_minima_suporte`, comparar a idade do titular ao limite e encerrar o
atendimento é do worker. O sender recebe o limite validado e o texto de contato
montado pelo catálogo com agente, nome e idade atual do titular. Todas as faixas
usam a mesma mensagem de atendimento personalizado e o botão `Falar agora`.
O link inclui o texto pré-preenchido com codificação de URL; o cliente ainda
precisa confirmar o envio no WhatsApp. O reconhecimento do corpo atual e das
cinco variantes antigas permite recuperar respostas sem reenviá-las.
Da mesma forma, a política `email_obrigatorio` e a distinção entre
aceite da oferta e pedido de informações não pertencem aos senders.

Uma função de mídia envia somente um arquivo. Lotes e álbuns exigem um contrato
futuro capaz de persistir vários IDs e tratar sucesso parcial.

Os senders devolvem contexto simples para o worker. Falhas são encadeadas com
`ErroEnvioMeta`, permitindo rollback e retry sem esconder a causa original.

## Tools

Operações Meta compartilhadas e ferramentas administrativas usadas pelo
Django Admin e pelo webhook:

- registrar/desregistrar número;
- validar o vínculo entre WABA e phone ID;
- ativar/desativar a inscrição WABA;
- bloquear e desbloquear usuários na Meta.

Relatórios conscientes e somente leitura ficam em
[`utilitarios/monitoring/blocked_users.py`](../../../utilitarios/monitoring/blocked_users.py).
Eles comparam bloqueios pela chave completa
`(waba_id, phone_id_unidade, wa_id_cliente)` e reconciliam registros Cloud API.

`tools/usuarios.py` é a primitiva única de bloqueio e desbloqueio consumida pelo
webhook e pelo Admin. Os demais módulos deste diretório atendem às operações de
configuração da conta e do número. Eles podem reutilizar a fábrica de cliente,
mas não devem duplicar envio de etapa nem assumir responsabilidades de banco,
fila ou transação.

`tools/config.py` centraliza a configuração operacional da integração Meta, mas
os valores são lidos por `core/config_env.py` a partir de variáveis de ambiente:

```text
META_ACCESS_TOKEN
META_GRAPH_API_VERSION
META_HTTP_CONNECT_TIMEOUT_SECONDS
META_HTTP_READ_TIMEOUT_SECONDS
META_PHONE_REGISTRATION_PIN
```

`META_GRAPH_API_VERSION` usa o formato `26.0`, sem o prefixo `v`. Essa versão é
aplicada ao cliente PyWa e a todas as URLs diretas da Graph API. Se uma versão
nova apresentar incompatibilidade, a variável pode retornar manualmente para a
última versão estável validada.

Não adicione token ou outro valor sensível diretamente nesse arquivo. WABA ID e
phone number ID são dados por unidade e devem vir do banco/cache.
`META_PHONE_REGISTRATION_PIN` também é segredo operacional e só é necessário
para a operação administrativa de registro do número; não deve ser exibido em
logs, documentação ou mensagens.

## Limites

Esta integração não deve:

- executar SQL ou Redis;
- decidir etapa persistida;
- marcar fila como `sent`;
- escolher quantidade ou intervalo de retries;
- executar commit, rollback ou close;
- importar módulos de `callback` ou `workers`.

## Testes relacionados

- `tests/unit/test_fluxo_turno_abc.py`;
- `tests/unit/test_persistencia_essencial.py`;
- `tests/unit/test_retry_essencial.py`;
- `tests/unit/test_worker_flow_runtime.py`;
- `tests/unit/test_suporte_idoso_email_obrigatorio.py`;
- `tests/unit/test_saudacao_retorno.py`.

O núcleo transacional e os testes específicos estão descritos em
[`tests/README.md`](../../../tests/README.md).

## Lembrete de follow-up

`messages/followup_messages.py` também monta a saudação de retomada com stage
positivo: `Que bom te ver novamente, <nome>!` ou `Que bom te ver novamente!`.
O nome vem do cadastro persistido; não é extraído da reação que será desconsiderada.
Na etapa 1, o worker passa nome ausente ao formatador, mesmo com cadastro antigo:
a saudação é sempre genérica, seguida da pergunta de nome do atendimento atual.
O prefixo é aplicado no corpo da etapa repetida, preservado no histórico e removido
do escopo ao sair do sender, inclusive em falhas. O proativo continua sem saudação.

`messages/followup_messages.py` contém o único texto aprovado:
`Você viu a minha mensagem?`.
`pywa_senders/followup.py` envia texto sem botões, sem saudação de retorno e sem
id_mensagem_fila fictício. Usa sessão HTTP com timeout e sem retry automático;
recebe destinatário e phone_id da unidade. `conta_wa` aceita sessão opcional sem
alterar os clientes existentes. A sessão usa timeout de 20 segundos por operação,
com conexão limitada a 5 segundos. Stage e persistência pertencem ao worker/repositório.
O ID retornado confirma o aceite da API; os eventos `sent`, `delivered` e `read`
recebidos pelo webhook não atualizam o histórico nesta versão.
