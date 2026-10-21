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
| `validacoes/` | Validações puras de e-mail e domínio de suporte por idade, sem acesso ao banco ou envio | [email.py](validacoes/email.py), [suporte_por_idade.py](validacoes/suporte_por_idade.py) |
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

As configurações `idade_minima_suporte` e `email_obrigatorio` pertencem à unidade. Os
contextos em `repositories/fluxo/contextos/` fornecem esses dados aos resolvers;
a decisão de encaminhar, tratar ou avançar permanece no worker.

`validacoes/suporte_por_idade.py` centraliza as idades mínimas permitidas e a
validação da configuração: `None` (NULL no banco) desativa; 50, 60, 70, 80 e 90
são os limites aceitos. O módulo rejeita booleanos e valores fora desse domínio;
não decide se um atendimento deve ser encaminhado.

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
validação da reação do cliente continuam nos respectivos workers: o retorno
pode avançar, receber um tratamento específico ou repetir a pergunta neutra.

## Reserva com e sem plataforma

A configuração atual de `unidade.link_agendamento` decide a saída da triagem: com link, 17 → 20; sem link, 17 → 18 (preferência de turno) → 19 (contato comercial). A satisfação converge em 21 → 22 → 23 → 24, com salto 22 → 24 na recusa de comentário. As etapas 1–17 conservam suas regras.

`conversa.turno` aceita NULL, manha, tarde ou noite e é salvo somente na transação de 18 → 19. É preferência, não confirmação de agendamento. Qualquer texto posterior na 19 apresenta a nota da 21; não é interpretado como nota nessa mesma interação. Mídia repete a orientação da 19.

O Funil exige 20–24 com link ou 19/21–24 sem link, considerando a configuração vigente na seleção, no claim e no snapshot. Preservar recibo de sucesso se o CRM já aceitou. O snapshot e o painel incluem turno da própria conversa, quando preenchido.

Follow-up proativo: 1–17 em ambas as rotas e 18 somente sem link; a 19 e a 20 não recebem novos lembretes. São preservadas as duas camadas de sete horas, os recibos, o encerramento no segundo lembrete e as guardas existentes. A reação ao primeiro segue a validação normal: um turno válido na 18 avança para 19 e é persistido. Contexto inválido genérico repete; tratamentos específicos continuam prioritários. Retomadas legadas são remapeadas por significado; a exceção 8 → 9 permanece.

Instalação existente exige migração própria: IDs antigos 18/19/20/21/22 tornam-se 20/21/22/23/24. Não executar setup ou seeds no banco de produção nem reaplicar migrações históricas. Preservar o Consumo Meta, seus fusos, worker, relatórios e PDFs, a compatibilidade PyWa 4.5.0, a exceção universal de idade 90+, o comentário livre e a despedida por participante.
