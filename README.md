# Chatbot WhatsApp

Backend de atendimento assíncrono pelo WhatsApp, com entrada Django, fila em
PostgreSQL, workers resilientes, cache Redis, integração Meta por PyWa e envio
periódico de oportunidades ao Funil de Vendas.

Este README é o portal do projeto. Regras detalhadas vivem nos documentos
centrais e os mapas técnicos vivem nos READMEs de cada camada.

## Comece por aqui

Para desenvolver novas etapas, siga a
[rotina de implementação de etapas](ROTINA_IMPLEMENTACAO_ETAPAS.md).

| Documento | Papel |
|---|---|
| [Regras de negócio](REGRAS_DE_NEGOCIO.md) | Fonte de verdade sobre turno, fila, etapas, retries, bloqueios e comportamentos esperados. |
| [Padrões de arquitetura](PADROES_DE_ARQUITETURA.md) | Fronteiras, dependências permitidas e local correto para novas funções. |
| [LGPD mínima da V1](LGPD_V1.md) | Registro prático dos dados tratados, finalidades e limites de LGPD para a primeira produção. |
| [Webhook](callback/README.md) | Entrada HTTP, validações, anti-flood e persistência na fila. |
| [Core](core/README.md) | Mapa dos recursos compartilhados. |
| [Workers](workers/README.md) | Processamento assíncrono, commits, locks e recuperação. |
| [Operations](operations/README.md) | Monitoramento e manutenção executados manualmente. |
| [Testes](tests/README.md) | Organização, comandos e cobertura crítica. |
| [Rotina de deploy](regras_deploy/rotina_deploy.md) | Publicação da `prod`, atualização da Lightsail e ciclo dos serviços. |
| [Ambiente e banco em produção](regras_deploy/modificando_env_e_banco_em_prod.md) | Troca segura do `.env` e evolução controlada do schema no RDS. |
| [Evolução para a V2](_V2/desafios_v2.md) | Escala, múltiplos workers e desafios técnicos futuros. |

## Documentação técnica

| Camada | Documento |
|---|---|
| Cache e Redis | [core/cache/README.md](core/cache/README.md) |
| Banco e deploy | [core/database/README.md](core/database/README.md) |
| SQL de runtime | [core/repositories/README.md](core/repositories/README.md) |
| Integrações externas | [core/integrations/README.md](core/integrations/README.md) |
| WhatsApp, Meta e PyWa | [core/integrations/whatsapp/README.md](core/integrations/whatsapp/README.md) |
| Funil de Vendas | [core/integrations/funil/README.md](core/integrations/funil/README.md) |
| Segurança avançada futura | [_V2/seguranca-avancada.md](_V2/seguranca-avancada.md) |
| Infraestrutura futura | [_V2/infraestrutura.md](_V2/infraestrutura.md) |
| Concorrência futura | [_V2/concorrencia-workers.md](_V2/concorrencia-workers.md) |
| Monitoramento futuro de tratamentos | [_V2/monitoramento-tratamentos.md](_V2/monitoramento-tratamentos.md) |

## Visão geral

```text
Meta/WhatsApp
    -> callback/webhook
    -> PostgreSQL: fila_mensagens
    -> workers/worker_flow
    -> core/integrations/whatsapp
    -> Meta/WhatsApp

PostgreSQL: conversa em etapa elegível
    -> workers/worker_funil
    -> core/integrations/funil
    -> Funil de Vendas: oportunidade em Leads
```

Responsabilidades principais:

```text
callback/webhook  entrada HTTP e enfileiramento
workers           fluxo assíncrono e recuperação
core/repositories SQL de runtime
core/database     conexão, DDL e setup
core/cache        Redis, fallback e autocura
core/integrations serviços externos
operations        relatórios e comandos manuais; nunca orquestradores
tests             testes, fakes, mocks e contratos
```

## Requisitos

- Python 3.12;
- PostgreSQL acessível;
- Redis acessível;
- credenciais Meta/PyWa para envios reais;
- arquivo `.env` local privado, ignorado pelo Git e alinhado com o ambiente;
- dependências de [`requirements.txt`](requirements.txt).

Não adicione segredos ao código. A configuração atual é carregada por
`core/config_env.py` a partir de variáveis de ambiente e do arquivo `.env` local.
Em produção, o `.env` pode ser substituído por variáveis do serviço ou por um
gerenciador de segredos.

## Preparação local

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
# Crie/preencha o .env privado com as variáveis do ambiente autorizado.
notepad .env
```

Depois de criar o arquivo, preencha `.env` com os valores reais do ambiente. O
arquivo `.env` é ignorado pelo Git e não deve ser enviado para repositório,
print, documentação ou conversa.

Variáveis principais:

```text
DJANGO_SECRET_KEY
DJANGO_DEBUG
DJANGO_ALLOWED_HOSTS
DJANGO_CSRF_TRUSTED_ORIGINS
DJANGO_TRUST_X_FORWARDED_PROTO
DB_HOST
DB_NAME
DB_USER
DB_PASSWORD
DB_PORT
DB_SSLMODE
DB_SSLROOTCERT
REDIS_HOST
REDIS_PORT
REDIS_USERNAME
REDIS_PASSWORD
REDIS_SSL
META_ACCESS_TOKEN
META_WEBHOOK_VERIFY_TOKEN
META_APP_SECRET
META_WEBHOOK_SIGNATURE_REQUIRED
WEBHOOK_MAX_BODY_BYTES
FUNIL_WORKER_ENABLED
FUNIL_INTERVALO_SEGUNDOS
FUNIL_LIMITE_POR_CICLO
FUNIL_LEASE_SEGUNDOS
FUNIL_RETRY_LEAD_SEGUNDOS
FUNIL_HTTP_CONNECT_TIMEOUT_SECONDS
FUNIL_HTTP_READ_TIMEOUT_SECONDS
```

Nunca registre valores reais de tokens, senhas ou payloads completos na
documentação.

## Banco de desenvolvimento

O setup é executado a partir da raiz:

```powershell
python -m core.database.deploy_database.setup_database
```

Os scripts são organizados por responsabilidade e podem ser executados novamente
para completar um setup interrompido. Consulte [Banco e deploy](core/database/README.md)
antes de alterar DDL ou funções PostgreSQL.

## Execução em desenvolvimento

A aplicação não possui um processo central. Webhook, worker de atendimento e
worker do Funil têm ciclos de vida independentes e se coordenam pelo PostgreSQL.
Inicie cada processo em seu próprio terminal:

```powershell
python callback/manage.py runserver
python -m workers.worker_flow.iniciar_flow_worker
python -m workers.worker_funil.iniciar_worker_funil
```

O terceiro processo encerra imediatamente enquanto
`FUNIL_WORKER_ENABLED=False`.

Endpoint do webhook:

```text
GET  /webhook
POST /webhook
```

A rota não possui barra final.

## Testes

```powershell
python -m unittest discover -s tests -p "test_*.py"
```

Validações adicionais:

```powershell
python -m compileall core workers callback tests
python callback/manage.py check
git diff --check
```

Consulte [tests/README.md](tests/README.md) para os contratos críticos e a
política de mocks.

## Princípios operacionais

- PostgreSQL é a fonte persistida da verdade;
- Redis acelera consultas e deve possuir fallback quando previsto;
- o webhook apenas valida e enfileira;
- o worker é dono do fluxo da conversa e das transações do ciclo;
- o worker do Funil é independente, processa uma oportunidade por vez e nasce
  desativado até a validação manual da integração;
- a V1 opera com uma única instância de worker, já protegida por contratos que
  deverão sustentar múltiplas instâncias na V2;
- chamadas Meta confirmadas são persistidas antes de a fila chegar a `sent`;
- falha ao persistir uma mensagem válida na fila retorna HTTP 503;
- falha ao validar unidade por indisponibilidade de Redis e banco retorna HTTP
  503 para permitir reentrega pela Meta;
- descartes intencionais por regra de negócio permanecem respostas controladas;
- erros devem ser registrados sem derrubar o processo principal.

Antes de alterar comportamento, leia [REGRAS_DE_NEGOCIO.md](REGRAS_DE_NEGOCIO.md).
Antes de mover ou criar módulos, leia
[PADROES_DE_ARQUITETURA.md](PADROES_DE_ARQUITETURA.md).
