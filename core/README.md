# Core

Recursos compartilhados pelo webhook, monitoramento, workers, Django Admin e ferramentas
operacionais. `core` não conhece o fluxo completo de nenhum ponto de entrada.

- [Portal do projeto](../README.md)
- [Padrões de arquitetura](../PADROES_DE_ARQUITETURA.md)

## Mapa

| Pasta ou arquivo | Responsabilidade | Documento |
|---|---|---|
| `cache/` | Redis, cache local, fallback e autocura | [cache/README.md](cache/README.md) |
| `database/` | Conexão, DDL, funções PostgreSQL e setup | [database/README.md](database/README.md) |
| `repositories/` | SQL de runtime usando cursor recebido | [repositories/README.md](repositories/README.md) |
| `integrations/` | Comunicação com serviços externos | [integrations/README.md](integrations/README.md) |
| `triagem/` | Catálogo único das seis perguntas, compartilhado pelo WhatsApp e Funil | [triagem/perguntas.py](triagem/perguntas.py) |
| `validacoes/` | Validação pura de e-mail, sem acesso ao banco ou envio | [validacoes/email.py](validacoes/email.py) |
| `config_env.py` | Leitura de `.env`, variáveis de ambiente e validação de tipos | [Padrões de arquitetura](../PADROES_DE_ARQUITETURA.md#configuração-e-segredos) |
| `logging_config.py` | Configuração comum de logs e redução de identificadores | [Padrões de arquitetura](../PADROES_DE_ARQUITETURA.md#logging-e-exceções) |

## Contrato

`core` pode:

- encapsular infraestrutura compartilhada;
- executar operações de baixo nível;
- fornecer contratos simples para pontos de entrada;
- compartilhar regras puras e catálogos usados por mais de um consumidor;
- definir exceções de domínio compartilhadas.

`core` não deve:

- iniciar o laço infinito do worker;
- retornar `JsonResponse`;
- decidir etapa da conversa;
- escolher limite de retry;
- conter mocks ou dados exclusivos de teste;
- importar `workers` ou `callback`.

As transações pertencem ao arquivo que conhece o fluxo completo. Repositórios e
integrações não devem assumir propriedade de conexão recebida de outro módulo.

## Políticas e dados do atendimento

As configurações `suporte_idoso` e `email_obrigatorio` pertencem à unidade. Os
contextos em `repositories/fluxo/contextos/` fornecem esses dados aos resolvers;
a decisão de encaminhar, tratar ou avançar permanece no worker.

A profissão é preservada na conversa e atualizada no cadastro do cliente. O
Funil utiliza o e-mail da resposta aceita naquele atendimento, inclusive a
ausência permitida, sem substituir esse histórico pelo cadastro de outra
conversa. Consulte os contratos de
[repositórios](repositories/README.md) e da
[integração Funil](integrations/funil/README.md) antes de alterar essa fronteira.

O follow-up usa `repositories/atendimento/followup.py` para elegibilidade,
fencing e registros de envio/retomada; conteúdo e transporte pertencem a
`integrations/whatsapp`. A criação das tabelas fica em `database/deploy_database`,
e a migração de uma base existente em `deploy/migrations`. O laço proativo e a
decisão de repetir a etapa no retorno continuam nos respectivos workers.
