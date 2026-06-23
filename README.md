# Chatbot WhatsApp

Backend de atendimento assíncrono pelo WhatsApp, com entrada Django, fila em
PostgreSQL, worker resiliente, cache Redis e integração Meta por PyWa.

Este README é o portal do projeto. Regras detalhadas vivem nos documentos
centrais e os mapas técnicos vivem nos READMEs de cada camada.

## Comece por aqui

| Documento | Papel |
|---|---|
| [Regras de negócio](REGRAS_DE_NEGOCIO.md) | Fonte de verdade sobre turno, fila, etapas, retries, bloqueios e comportamentos esperados. |
| [Padrões de arquitetura](PADROES_DE_ARQUITETURA.md) | Fronteiras, dependências permitidas e local correto para novas funções. |
| [Webhook](callback/README.md) | Entrada HTTP, validações, anti-flood e persistência na fila. |
| [Core](core/README.md) | Mapa dos recursos compartilhados. |
| [Workers](workers/README.md) | Processamento assíncrono, commits, locks e recuperação. |
| [Testes](tests/README.md) | Organização, comandos e cobertura crítica. |
| [Evolução para a V2](_V2/desafios_v2.md) | Escala, múltiplos workers e desafios técnicos futuros. |

## Documentação técnica

| Camada | Documento |
|---|---|
| Cache e Redis | [core/cache/README.md](core/cache/README.md) |
| Banco e deploy | [core/database/README.md](core/database/README.md) |
| SQL de runtime | [core/repositories/README.md](core/repositories/README.md) |
| Integrações externas | [core/integrations/README.md](core/integrations/README.md) |
| WhatsApp, Meta e PyWa | [core/integrations/whatsapp/README.md](core/integrations/whatsapp/README.md) |

## Visão geral

```text
Meta/WhatsApp
    -> callback/webhook
    -> PostgreSQL: fila_mensagens
    -> workers/worker_flow
    -> core/integrations/whatsapp
    -> Meta/WhatsApp
```

Responsabilidades principais:

```text
callback/webhook  entrada HTTP e enfileiramento
workers           fluxo assíncrono e recuperação
core/repositories SQL de runtime
core/database     conexão, DDL e setup
core/cache        Redis, fallback e autocura
core/integrations serviços externos
tests             testes, fakes, mocks e contratos
```

## Requisitos

- Python 3.12;
- PostgreSQL acessível;
- Redis acessível;
- credenciais Meta/PyWa para envios reais;
- dependências de [`requirements.txt`](requirements.txt).

Não adicione novos segredos ao código. Configurações de produção devem utilizar
variáveis de ambiente ou um gerenciador de segredos.

## Preparação local

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

Configure as dependências externas antes de iniciar. Variáveis relacionadas ao
webhook incluem:

```text
META_APP_SECRET
META_WEBHOOK_SIGNATURE_REQUIRED
WEBHOOK_MAX_BODY_BYTES
```

O projeto ainda possui configurações legadas que devem ser externalizadas antes
de produção. Nunca registre valores reais de tokens, senhas ou payloads completos
na documentação.

## Banco de desenvolvimento

O setup é executado a partir da raiz:

```powershell
python -m core.database.deploy.setup_database
```

Os scripts são organizados por responsabilidade e podem ser executados novamente
para completar um setup interrompido. Consulte [Banco e deploy](core/database/README.md)
antes de alterar DDL ou funções PostgreSQL.

## Execução em desenvolvimento

O bootstrap recomendado valida o cache inicial e abre webhook e worker em
terminais separados:

```powershell
python main.py
```

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
- a V1 opera com uma única instância de worker, já protegida por contratos que
  deverão sustentar múltiplas instâncias na V2;
- chamadas Meta confirmadas são persistidas antes de a fila chegar a `sent`;
- falha ao persistir uma mensagem válida na fila retorna HTTP 503;
- descartes intencionais por regra de negócio permanecem respostas controladas;
- erros devem ser registrados sem derrubar o processo principal.

Antes de alterar comportamento, leia [REGRAS_DE_NEGOCIO.md](REGRAS_DE_NEGOCIO.md).
Antes de mover ou criar módulos, leia
[PADROES_DE_ARQUITETURA.md](PADROES_DE_ARQUITETURA.md).
