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
├── messages/
│   ├── primeira_etapa_messages.py
│   └── segunda_etapa_messages.py
├── pywa_functions/
│   ├── cliente.py
│   ├── saudacao.py
│   ├── ferramentas.md
│   └── pywa_senders/
│       ├── etapa1.py
│       └── etapa2.py
└── tools/
    ├── ativando_numero.py
    ├── ativando_waba_id.py
    ├── block_report.py
    ├── config.py
    ├── desativando_numero.py
    └── usuarios.py
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

Cada etapa mantém seu próprio arquivo, como
`primeira_etapa_messages.py` e `segunda_etapa_messages.py`.

## PyWa functions

Único local permitido para importação e chamada direta da PyWa.

- `cliente.py`: normaliza `phone_id` e cria `WhatsApp`;
- `saudacao.py`: seleção de bom dia, boa tarde ou boa noite pelo horário do
  atendimento;
- `pywa_senders/etapaN.py`: mensagens normais e tratamentos específicos da
  etapa N.

Cada sender escolhe conteúdo, legenda e lista de botões, realiza a chamada PyWa
e devolve um contexto técnico com o ID da Meta e a etapa da mensagem enviada.
O sender não escolhe origem, evento ou destino da transição.

Uma função de mídia envia somente um arquivo. Lotes e álbuns exigem um contrato
futuro capaz de persistir vários IDs e tratar sucesso parcial.

Os senders devolvem contexto simples para o worker. Falhas são encadeadas com
`ErroEnvioMeta`, permitindo rollback e retry sem esconder a causa original.

## Tools

Ferramentas administrativas ou relatórios executados conscientemente:

- registrar/desregistrar número;
- ativar inscrição WABA;
- comparar bloqueios Meta e banco.
- bloquear, desbloquear e listar usuários na Meta.

`tools` não deve conter implementação duplicada usada pelo runtime. Uma operação
compartilhada deve morar em `pywa_functions` e ser chamada pela ferramenta.

`tools/config.py` centraliza a configuração operacional da integração Meta, mas
os valores são lidos por `core/config_env.py` a partir de variáveis de ambiente:

```text
META_ACCESS_TOKEN
META_WABA_ID
META_PHONE_NUMBER_ID_DEV
```

Não adicione token, WABA ID, phone number ID ou outro valor sensível diretamente
nesse arquivo.

## Limites

Esta integração não deve:

- executar SQL ou Redis;
- decidir etapa persistida;
- marcar fila como `sent`;
- escolher quantidade ou intervalo de retries;
- executar commit, rollback ou close;
- importar módulos de `callback` ou `workers`.

## Testes relacionados

- `tests/unit/test_pywa_sender_etapa1.py`;
- `tests/unit/test_pywa_sender_etapa2.py`;
- `tests/unit/test_saudacao.py`;
- `tests/unit/test_whatsapp_usuarios.py`;
- `tests/unit/test_whatsapp_structure.py`.
