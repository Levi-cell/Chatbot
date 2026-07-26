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
│   ├── etapa1_messages.py
│   └── etapa2_messages.py
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
`etapa1_messages.py` e `etapa2_messages.py`.

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
- validar o vínculo entre WABA e phone ID;
- ativar/desativar a inscrição WABA;
- comparar bloqueios Meta e banco;
- reconciliar registros Cloud API percorrendo todas as WABAs das unidades;
- bloquear, desbloquear e listar usuários na Meta.

`tools` não deve conter implementação duplicada usada pelo runtime. Uma operação
compartilhada deve morar em `pywa_functions` e ser chamada pela ferramenta.

`tools/config.py` centraliza a configuração operacional da integração Meta, mas
os valores são lidos por `core/config_env.py` a partir de variáveis de ambiente:

```text
META_ACCESS_TOKEN
```

Não adicione token ou outro valor sensível diretamente nesse arquivo. WABA ID e
phone number ID são dados por unidade e devem vir do banco/cache.

## Limites

Esta integração não deve:

- executar SQL ou Redis;
- decidir etapa persistida;
- marcar fila como `sent`;
- escolher quantidade ou intervalo de retries;
- executar commit, rollback ou close;
- importar módulos de `callback` ou `workers`.

## Testes relacionados

- `tests/unit/test_roteamento_essencial.py`;
- `tests/unit/test_roteamento_essencial.py`.
