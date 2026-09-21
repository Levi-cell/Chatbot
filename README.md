# Chatbot WhatsApp

Backend de atendimento assíncrono pelo WhatsApp, com entrada Django, fila em
PostgreSQL, workers resilientes, cache Redis, integração Meta por PyWa e envio
periódico de oportunidades ao Funil de Vendas.

Este README é o portal do projeto. Regras detalhadas vivem nos documentos
centrais e os mapas técnicos vivem nos READMEs de cada camada.

Referência atual: **V1.3.0**, com encaminhamento de titulares por idade mínima
configurável e indicador comercial no painel, implementados e implantados.
O follow-up de inatividade continua em funcionamento. Versões e regras de
numeração ficam em
[VERSIONAMENTO.md](VERSIONAMENTO.md).

Os documentos técnicos abaixo descrevem o código atual. Os planos em `docs/`
são propostas separadas: sua existência não significa que já foram aplicados.

As mensagens oferecem uma **experiência Supera gratuita**, com demonstração
prática exclusiva e convite para **reservar** o melhor dia e horário. Esta
revisão não adiciona colunas nem exige migração sobre a V1.3.0 implantada.

## Comece por aqui

Para desenvolver novas etapas, siga a
[rotina de implementação de etapas](ROTINA_IMPLEMENTACAO_ETAPAS.md).

| Documento | Papel |
|---|---|
| [Regras de negócio](REGRAS_DE_NEGOCIO.md) | Fonte de verdade sobre turno, fila, etapas, retries, bloqueios e comportamentos esperados. |
| [Padrões de arquitetura](PADROES_DE_ARQUITETURA.md) | Fronteiras, dependências permitidas e local correto para novas funções. |
| [Aplicativos Django](callback/README.md) | Webhook, validações, fila e estrutura do aplicativo de monitoramento. |
| [Core](core/README.md) | Mapa dos recursos compartilhados. |
| [Workers](workers/README.md) | Processamento assíncrono, commits, locks e recuperação. |
| [Utilitários](utilitarios/README.md) | Monitoramento e manutenção executados manualmente. |
| [Testes](tests/README.md) | Organização, comandos e cobertura crítica. |
| [Rotina de deploy](regras_deploy/rotina_deploy.md) | Publicação da `prod`, atualização da Lightsail e ciclo dos serviços. |
| [Ambiente e banco em produção](regras_deploy/modificando_env_e_banco_em_prod.md) | Troca segura do `.env` e evolução controlada do schema no RDS. |
| [Arquivos de deploy](deploy/README.md) | Serviços systemd, Nginx e migrações versionadas. |

## Documentação técnica

| Camada | Documento |
|---|---|
| Cache e Redis | [core/cache/README.md](core/cache/README.md) |
| Banco e deploy | [core/database/README.md](core/database/README.md) |
| SQL de runtime | [core/repositories/README.md](core/repositories/README.md) |
| Integrações externas | [core/integrations/README.md](core/integrations/README.md) |
| WhatsApp, Meta e PyWa | [core/integrations/whatsapp/README.md](core/integrations/whatsapp/README.md) |
| Funil de Vendas | [core/integrations/funil/README.md](core/integrations/funil/README.md) |

### Planejamento separado do runtime

As propostas de [evolução para a V2](docs/_V2/desafios_v2.md),
[segurança avançada](docs/_V2/seguranca-avancada.md),
[infraestrutura](docs/_V2/infraestrutura.md),
[concorrência](docs/_V2/concorrencia-workers.md) e
[monitoramento de tratamentos](docs/_V2/monitoramento-tratamentos.md) permanecem
em `docs/`. Não substituem as instruções operacionais dos READMEs.

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

PostgreSQL: conversa elegível sem resposta ao bot por sete horas
    -> workers/worker_followup
    -> core/integrations/whatsapp
    -> Meta/WhatsApp: um lembrete por ciclo

Franqueado autenticado
    -> callback/monitoramento
    -> autorização pela unidade da sessão
    -> PostgreSQL: consultas somente leitura
```

Responsabilidades principais:

```text
callback/webhook  entrada HTTP e enfileiramento
callback/monitoramento login, conversas, relatórios e CSV por unidade
workers           fluxo assíncrono e recuperação
core/repositories SQL de runtime
core/database     conexão, DDL e setup
core/cache        Redis, fallback e autocura
core/integrations serviços externos
core/triagem      catálogo compartilhado das seis perguntas
core/validacoes   validações puras de e-mail e domínio de suporte por idade
utilitarios       relatórios e comandos manuais; nunca orquestradores
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
DJANGO_SECURE_SSL_REDIRECT
DJANGO_SESSION_COOKIE_SECURE
DJANGO_CSRF_COOKIE_SECURE
DJANGO_SECURE_HSTS_SECONDS
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
META_GRAPH_API_VERSION
META_WEBHOOK_VERIFY_TOKEN
META_APP_SECRET
META_WEBHOOK_SIGNATURE_REQUIRED
META_HTTP_CONNECT_TIMEOUT_SECONDS
META_HTTP_READ_TIMEOUT_SECONDS
META_PHONE_REGISTRATION_PIN
WEBHOOK_MAX_BODY_BYTES
FUNIL_WORKER_ENABLED
FUNIL_INTERVALO_SEGUNDOS
FUNIL_LIMITE_POR_CICLO
FUNIL_LEASE_SEGUNDOS
FUNIL_RETRY_LEAD_SEGUNDOS
FUNIL_HTTP_CONNECT_TIMEOUT_SECONDS
FUNIL_HTTP_READ_TIMEOUT_SECONDS
FOLLOWUP_WORKER_ENABLED
FOLLOWUP_POLL_SECONDS
FOLLOWUP_BATCH_SIZE
```

Nunca registre valores reais de tokens, senhas ou payloads completos na
documentação.

## Banco de desenvolvimento

O setup é executado a partir da raiz:

```powershell
python -m core.database.deploy_database.setup_database
```

O setup prepara um banco de desenvolvimento autorizado. Ele não substitui a
migração de um banco existente: `CREATE TABLE IF NOT EXISTS` não atualiza colunas
de tabelas já criadas. As migrações incrementais ficam em
[`deploy/migrations/`](deploy/migrations/). Consulte
[Banco e deploy](core/database/README.md) antes de executar o setup ou alterar
DDL e funções PostgreSQL.

## Execução em desenvolvimento

A aplicação não possui um processo central. Webhook, worker de atendimento,
worker do Funil e worker de follow-up têm ciclos de vida independentes e se
coordenam pelo PostgreSQL.
Inicie cada processo em seu próprio terminal:

```powershell
python callback/manage.py runserver
python -m workers.worker_flow.iniciar_flow_worker
python -m workers.worker_funil.iniciar_worker_funil
python -m workers.worker_followup.iniciar_worker_followup
```

O Funil encerra imediatamente enquanto `FUNIL_WORKER_ENABLED=False`.
O follow-up também exige `FOLLOWUP_WORKER_ENABLED=True` para executar seu laço.
Antes de ativá-lo, prepare o schema por instalação limpa ou migração pendente
e inicie o flow compatível, conforme
[Ativação do follow-up](deploy/README.md#ativação-do-follow-up).
O intervalo padrão é 60 segundos entre lotes de até 20 conversas, processadas
individualmente. A unit de produção habilita o serviço; a execução manual nasce
desabilitada. Não inicie workers locais com credenciais de produção para testar.

Endpoint do webhook:

```text
GET  /webhook
POST /webhook
```

A rota não possui barra final.

## Testes

```powershell
python -m unittest discover -s tests -t . -p "test_*.py"
```

Validações adicionais:

```powershell
python -m compileall core workers callback utilitarios tests
python callback/manage.py check
git diff --check
```

Consulte [tests/README.md](tests/README.md) para os contratos críticos e a
política de mocks.

## Portal de monitoramento

O aplicativo `callback/monitoramento` oferece login por conta Django vinculada
1:1 à unidade, histórico consolidado de conversas e relatórios por período.
São quatro downloads: Google CSV ou dados essenciais, cada um com todos os
contatos ou apenas elegíveis. O essencial contém Nome, E-mail e Telefone e remove
somente o prefixo brasileiro `+55`, preservando o DDD; Google CSV mantém o
telefone internacional. Cada requisição resolve novamente a unidade
da sessão e todos os SELECTs mantêm esse escopo. O navegador atualiza conversas
a cada 10 segundos e relatórios a cada 30 segundos pelo mesmo serviço web do
webhook; não existe processo adicional na VM.

Conversas usa o layout compacto, com etiquetas de perfil junto da data e
navegação adaptada a celular em ambas as orientações. Os indicadores agregados
ficam em Relatórios. Os lembretes confirmados entram no histórico e no total de
mensagens; não há indicador exclusivo de follow-up no painel.

Na V1.3.0, o proprietário configura no Django Admin a idade mínima para
encaminhar titulares ao comercial na etapa 6: Desativado, 50+, 60+, 70+, 80+ ou
90+. O limite preserva as regras de dependentes, de pessoas acima de 99 anos,
de e-mail e das tags de perfil. Os contratos ficam no
[README dos workers](workers/README.md#regras-atuais-das-etapas).

Em Relatórios, **Encaminhados ao comercial** conta clientes distintos por unidade
com encerramento por suporte de idade no período, inclusive históricos,
independentemente da configuração atual. A métrica não inclui o tratamento de
100+ nem comprova atendimento humano ou venda. Consulte
[callback/README.md](callback/README.md) para o contrato do painel e o
[procedimento de suporte por idade](deploy/idade_minima_suporte.md) para migração
e reversão de uma base existente.

## Follow-up em funcionamento

O quarto serviço envia um único `Você viu a minha mensagem?` por ciclo para
conversa ativa nas etapas 1–17, com `followup_stage = 0`, último envio confirmado
do bot há pelo menos sete horas e última mensagem do cliente há menos de 24 horas
(com um minuto de margem no código). A seleção também verifica unidade, fila e
bloqueios. A etapa 18 e as posteriores não recebem lembretes proativos.

Na primeira reação aceita com stage positivo, o flow guarda a mensagem e repete
a etapa com `Que bom te ver novamente`, sem usar essa reação como resposta da
pergunta. O stage só volta a zero junto da persistência da repetição. Conversas
antigas ativas foram marcadas com stage 1 na migração inicial, sem disparo retroativo.

Contratos: [regras de negócio](REGRAS_DE_NEGOCIO.md#follow-up-de-inatividade-e-reação-do-cliente),
[workers](workers/README.md#worker-de-follow-up),
[banco](core/database/README.md#registros-de-follow-up) e
[diagnóstico sem envio](utilitarios/README.md#diagnóstico-de-follow-up).

## Monitoramento manual

[`weekly.py`](utilitarios/reports_functions/weekly.py) gera o recorte semanal e
[`total.py`](utilitarios/reports_functions/total.py) cobre o histórico de cada
unidade. Os HTMLs de conversas unificam os atendimentos do mesmo cliente na mesma
unidade; os PDFs apresentam indicadores, perfis de público, encaminhamentos ao
Funil e satisfação. São materiais distintos, salvos em `monitoramento/`, pasta
ignorada pelo Git e que contém dados pessoais.

Esses utilitários não fazem parte dos serviços. Para comandos, dependências
opcionais do PDF e interpretação das métricas, consulte
[`utilitarios/README.md`](utilitarios/README.md).

## Princípios operacionais

- PostgreSQL é a fonte persistida da verdade;
- Redis acelera consultas e deve possuir fallback quando previsto;
- o webhook apenas valida e enfileira;
- o worker é dono do fluxo da conversa e das transações do ciclo;
- o worker do Funil é independente, processa uma oportunidade por vez e nasce
  desativado até a validação manual da integração;
- a V1 utiliza uma instância do worker de atendimento e uma instância independente
  de cada worker do Funil e de follow-up; flow e follow-up compartilham o lock
  versionado da conversa, mantendo conexões e transações próprias;
- chamadas Meta confirmadas são persistidas antes de a fila chegar a `sent`;
- falha ao persistir uma mensagem válida na fila retorna HTTP 503;
- falha ao validar unidade por indisponibilidade de Redis e banco retorna HTTP
  503 para permitir reentrega pela Meta;
- descartes intencionais por regra de negócio permanecem respostas controladas;
- erros devem ser registrados sem derrubar o processo principal.

Antes de alterar comportamento, leia [REGRAS_DE_NEGOCIO.md](REGRAS_DE_NEGOCIO.md).
Antes de mover ou criar módulos, leia
[PADROES_DE_ARQUITETURA.md](PADROES_DE_ARQUITETURA.md).
