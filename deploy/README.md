# Implantacao no Lightsail

Os arquivos assumem a aplicacao em `/opt/chatbot/app`, o ambiente virtual em
`/opt/chatbot/venv` e as variaveis em `/etc/chatbot/chatbot.env`. Os processos
da aplicacao sao independentes e escrevem seus logs no journald. O
portal de monitoramento faz parte do processo web `chatbot-webhook`; ele não
cria outro serviço. O quarto serviço é `chatbot-worker-followup`, implantado na
V1.2.0. Este guia também cobre a preparação de uma instalação nova.

## Preparar a aplicacao

### Atualização das mensagens da experiência Supera

A oferta usa **experiência Supera gratuita** e **demonstração prática exclusiva**.
Esta revisão não altera o schema da V1.3.0 já implantada. A proposta de
cadastro de responsável foi retirada antes do deploy, junto com seu SQL
pendente. Não executar scripts antigos salvos para criar essas duas colunas.
A apresentação do agente continua usando os campos já existentes.

### Instalação inicial

Clone a branch `prod` como o usuario `ubuntu` e instale as dependencias:

```bash
git clone --branch prod --single-branch git@github.com:Levi-cell/Chatbot.git /opt/chatbot/app
python3 -m venv /opt/chatbot/venv
/opt/chatbot/venv/bin/pip install --upgrade pip
/opt/chatbot/venv/bin/pip install -r /opt/chatbot/app/requirements.txt
```

Crie `/etc/chatbot/chatbot.env` conforme o procedimento em
[`regras_deploy/modificando_env_e_banco_em_prod.md`](../regras_deploy/modificando_env_e_banco_em_prod.md),
sem registrar segredos no repositorio. Em producao, use `DJANGO_DEBUG=False`,
configure o dominio em `DJANGO_ALLOWED_HOSTS` e mantenha o arquivo restrito:

```bash
sudo chown root:chatbot /etc/chatbot/chatbot.env
sudo chmod 0640 /etc/chatbot/chatbot.env
```

Defina `FUNIL_WORKER_ENABLED=True`, configure o RDS com TLS e informe o
endpoint do Redis remoto em `REDIS_HOST`. A aplicacao nao usa nem exige um
`redis-server` local na VM. Mantenha `PGSSLCERTMODE=disable` quando o RDS
autenticar por usuario/senha. Essa opcao desativa apenas o certificado TLS de
cliente; use `DB_SSLMODE=verify-full` e `DB_SSLROOTCERT` para continuar
validando o certificado do servidor.

Se o banco estiver vazio, crie antes o schema de destino no DBeaver:

```sql
CREATE SCHEMA IF NOT EXISTS chatbot;
```

Depois, prepare o Django. Suas migrations criam `chatbot.auth_user`, necessária
antes do DDL de negócio por causa do vínculo de monitoramento:

```bash
sudo -u chatbot bash -c 'set -a; source /etc/chatbot/chatbot.env; set +a; cd /opt/chatbot/app; export PYTHONPATH=/opt/chatbot/app; /opt/chatbot/venv/bin/python callback/manage.py check --deploy'
sudo -u chatbot bash -c 'set -a; source /etc/chatbot/chatbot.env; set +a; cd /opt/chatbot/app; export PYTHONPATH=/opt/chatbot/app; /opt/chatbot/venv/bin/python callback/manage.py migrate --noinput'
sudo -u chatbot bash -c 'set -a; source /etc/chatbot/chatbot.env; set +a; cd /opt/chatbot/app; export PYTHONPATH=/opt/chatbot/app; /opt/chatbot/venv/bin/python callback/manage.py collectstatic --noinput'
```

`EnvironmentFile` é carregado automaticamente somente pelo systemd. Uma sessão
SSH comum não recebe essas variáveis; os comandos manuais acima carregam o mesmo
arquivo privado dos serviços sem exibir seu conteúdo.

Em uma instalação vazia, após as migrations do Django, siga o
[setup do banco de negócio](../core/database/README.md#setup) antes de iniciar
os serviços. Na atualização de um banco existente, use a migração incremental
específica, sem executar novamente o setup como substituto da migração.

## Instalar os servicos

```bash
sudo install -m 0644 /opt/chatbot/app/deploy/systemd/*.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now chatbot-webhook chatbot-worker-flow chatbot-worker-funil
```

O follow-up é instalado junto das demais units, mas deve ser iniciado somente
após o banco e o flow compatível estarem validados. Conclua a seção
[Ativação do follow-up](#ativação-do-follow-up) para habilitá-lo.

```bash
systemctl status chatbot-webhook chatbot-worker-flow chatbot-worker-funil chatbot-worker-followup
journalctl -u chatbot-webhook -u chatbot-worker-flow -u chatbot-worker-funil -u chatbot-worker-followup -f
```

## Habilitar o Nginx e HTTPS

Instale o template, substitua `__DOMAIN__` pelo dominio real e habilite o site.
O Gunicorn escuta somente em `127.0.0.1:8000`; apenas o Nginx recebe trafego
publico.

```bash
sudo install -m 0644 /opt/chatbot/app/deploy/nginx/chatbot.conf /etc/nginx/sites-available/chatbot
sudoedit /etc/nginx/sites-available/chatbot
sudo ln -sfn /etc/nginx/sites-available/chatbot /etc/nginx/sites-enabled/chatbot
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t
sudo systemctl reload nginx
```

Com o DNS apontando para o IP estatico e as portas 80/443 abertas, deixe o
Certbot criar a configuracao HTTPS somente depois de emitir o certificado:

```bash
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx --redirect -d SEU_DOMINIO
sudo certbot renew --dry-run
```

Somente depois de o HTTPS funcionar, ative no ambiente
`DJANGO_TRUST_X_FORWARDED_PROTO=True`, `DJANGO_SECURE_SSL_REDIRECT=True`,
`DJANGO_SESSION_COOKIE_SECURE=True` e `DJANGO_CSRF_COOKIE_SECURE=True`, e
reinicie o webhook. O Nginx sobrescreve `X-Forwarded-Proto`; o Django nao confia
em um valor enviado diretamente pelo cliente.

## Atualizacao rotineira da branch prod

O procedimento canonico esta em
[`regras_deploy/rotina_deploy.md`](../regras_deploy/rotina_deploy.md).

Na atualização dos workers ou de seus módulos compartilhados, pare o follow-up
antes do flow; retome o flow compatível e validado antes de reativar os lembretes.
Pare também o Funil quando ele for afetado. Alterações exclusivas do painel
podem manter os workers ativos. O webhook continua recebendo e enfileirando
quando o schema permite; para carregar Python/templates novos, recebe `HUP`,
pois Gunicorn não possui auto-reload. Alteração de `.env` ou da unit exige `restart` e segue
[`modificando_env_e_banco_em_prod.md`](../regras_deploy/modificando_env_e_banco_em_prod.md).

## Migracoes incrementais do banco de negocio

Os scripts SQL revisáveis para o RDS existente ficam em `deploy/migrations/`.
Eles não são executados por `manage.py migrate` nem pelo setup de instalação
limpa. Siga os pré-requisitos, as validações e a orientação de rollback do
próprio arquivo antes de publicar o código que depende do novo estado.

Para o cadastro de monitoramento, execute
`deploy/migrations/20260902_adicionar_usuario_monitoramento_unidade.sql` inteiro no DBeaver
antes de publicar o Admin atualizado. Requer `chatbot.unidade` e
`chatbot.auth_user`. O script adiciona `unidade.id_usuario_monitoramento`, com
`UNIQUE` e FK `ON DELETE SET NULL`. Se `unidade_monitoramento` já existir,
valida e transfere os vínculos antes de removê-la, sem `CASCADE`. O SQL anterior
de criação da tabela foi substituído e não deve ser executado.

É uma migração de aplicação única: coluna já existente causa erro. Em caso de
falha, execute `ROLLBACK`; investigue a causa antes de repetir. `ALTER TABLE`
fica somente nesta migração, enquanto o DDL de instalação limpa já contém a
coluna em seu `CREATE TABLE`. Depois da migração, não publique novamente o
código que depende da tabela antiga. Uma reversão exige preservar os vínculos
atuais e preparar um SQL específico antes de voltar o código.

## Operacao dos servicos e do Redis remoto

Os comandos individuais para iniciar e parar cada processo, limpar somente os
bloqueios no Redis remoto e remover o servidor Redis local da VM estao em
[`regras_deploy/servicos_e_redis_remoto.md`](../regras_deploy/servicos_e_redis_remoto.md).

Nao exponha a porta `6379` e nao use `FLUSHDB` ou `FLUSHALL` em producao.

## Ativação do follow-up

Esta alteração exige migração manual `migrations/followup_registros.sql` antes do
flow novo. Instalação limpa utiliza `followup_script.py`, chamado por `bank_script`.
As colunas `followup_stage`/`followup_last_sent_at` já existentes não são recriadas. Com o flow
parado e o follow-up desligado, a migração registra em followup_legado todas as
conversas ativas e marca followup_stage = 1, inclusive nas etapas 18–21. O horário
`followup_last_sent_at`, o histórico, a etapa e a finalização permanecem como estavam.
O script é único e transacional; não reaplicar nos próximos deploys. O setup limpo
cria as três tabelas e não marca conversas. A marcação não comprova envio de mensagem.
Conversa ativa terminal/inconsistente recusa toda a migração: concluir a recuperação
pendente do flow e revisar a anomalia antes de tentar de novo, sem encerrar em massa.

Na produção, essa migração já foi aplicada em 10/09/2026 na V1.2.0, com 106
conversas marcadas naquela execução. Não repetir nem manter esse número como
expectativa fixa: os clientes podem retomar normalmente após o deploy.

Instalar `systemd/chatbot-worker-followup.service` e executar daemon-reload não
inicia envios. A unit habilita FOLLOWUP_WORKER_ENABLED; se essa chave já existir no
EnvironmentFile, conferir a precedência antes da ativação. Nenhum segredo novo é necessário.
Antes da primeira ativação, executar o diagnóstico abaixo e conferir permissões
da role da aplicação nas novas tabelas. Reiniciar primeiro
`chatbot-worker-flow.service` e conferir estado/logs. Somente então:

```bash
sudo systemctl enable --now chatbot-worker-followup.service
sudo journalctl -u chatbot-worker-followup.service --since "5 minutes ago" -n 80 --no-pager
```

`python -m utilitarios.verificar_followup` faz leitura e mostra IDs de uma amostra.
Não é uma execução do worker e não envia mensagens. Um resultado vazio é válido.
O [README dos utilitários](../utilitarios/README.md#diagnóstico-de-follow-up)
traz o comando com o ambiente da VM e explica cada indicador. A sequência completa
de atualização fica em [rotina_deploy.md](../regras_deploy/rotina_deploy.md).

Para interromper os lembretes, parar e desabilitar a unit de follow-up. Isso mantém
o flow apto a tratar retornos de lembretes ou do legado marcado. Não apagar recibos, resetar
stages em massa nem reverter o flow incompatível enquanto existirem ciclos positivos.

## Segunda camada de follow-up

Aplicar [`migrations/20260924_segundo_followup.sql`](migrations/20260924_segundo_followup.sql)
com os workers parados, antes de iniciar o código novo. O arquivo amplia somente
o motivo de encerramento permitido; não fecha conversas nem altera stages existentes.
Não repetir `followup_registros.sql`. Instalação limpa usa o DDL atualizado.

A segunda camada usa o mesmo serviço, após mais 7h desde o primeiro envio real,
mantendo a janela de envio. Recibos antigos válidos podem se tornar elegíveis ao
iniciar o worker; marcações de legado sem recibo não geram despedida.
Atualizar também os estáticos do painel (`collectstatic`) para publicar o filtro
**Follow-up**. Validar o diagnóstico sem envio, reiniciar o flow e só então o follow-up.

## Suporte por idade mínima

O [procedimento de suporte por idade](idade_minima_suporte.md) coordena schema,
código, estáticos e serviços. A migração incremental está em
`migrations/20260911_idade_minima_suporte.sql`; a reversão restrita a NULL/60 está
em `rollback/20260911_idade_minima_suporte.sql`. Não executar em instalações
novas, não reaplicar a migração de follow-up e não editar a migração histórica
que criou a coluna booleana. Os comandos só pertencem à implantação aprovada.


## Filtro Comercial e regras de idade

Ver [procedimento coordenado](filtro_comercial_regras_idade.md). A migração
`migrations/20260926_filtro_comercial_regras_idade.sql` exige telefones reais válidos
e interrompe a transação se houver pendência. Não executá-la com código antigo
processando atendimentos ou permitindo edição simultânea no Admin.

## Consumo Meta: serviço adicional

A seção Consumo acrescenta um quinto processo independente,
`chatbot-worker-consumo-meta.service`. Exige a migração
`migrations/20260929_consumo_mensal_meta.sql`, dependências de PDF, collectstatic
e ativação por ambiente. Seguir o [guia completo](consumo_mensal_meta.md); não
executar o setup inicial de banco numa atualização. Até ativar o serviço e
existir coleta válida, o painel informa que aguarda dados.

## Reserva com e sem plataforma

Seguir o [procedimento coordenado de implantação](reserva_com_sem_link.md).
O SQL incremental está em `migrations/20261003_reserva_com_sem_link.sql`, com
reversão restrita em `rollback/20261003_reserva_com_sem_link.sql`.

A configuração atual de `unidade.link_agendamento` decide a saída da triagem: com link, 17 → 20; sem link, 17 → 18 (preferência de turno) → 19 (contato comercial). A satisfação converge em 21 → 22 → 23 → 24, com salto 22 → 24 na recusa de comentário. As etapas 1–17 conservam suas regras.

`conversa.turno` aceita NULL, manha, tarde ou noite e é salvo somente na transação de 18 → 19. É preferência, não confirmação de agendamento. Qualquer texto posterior na 19 apresenta a nota da 21; não é interpretado como nota nessa mesma interação. Mídia repete a orientação da 19.

O Funil exige 20–24 com link ou 19/21–24 sem link, considerando a configuração vigente na seleção, no claim e no snapshot. Preservar recibo de sucesso se o CRM já aceitou. O snapshot e o painel incluem turno da própria conversa, quando preenchido.

Follow-up proativo: 1–17 em ambas as rotas e 18 somente sem link; a 19 e a 20 não recebem novos lembretes. São preservadas as duas camadas de sete horas, os recibos, o encerramento no segundo lembrete e as guardas existentes. A reação ao primeiro segue a validação normal: um turno válido na 18 avança para 19 e é persistido. Contexto inválido genérico repete; tratamentos específicos continuam prioritários. Retomadas legadas são remapeadas por significado; a exceção 8 → 9 permanece.

Instalação existente exige migração própria: IDs antigos 18/19/20/21/22 tornam-se 20/21/22/23/24. Não executar setup ou seeds no banco de produção nem reaplicar migrações históricas. Preservar o Consumo Meta, seus fusos, worker, relatórios e PDFs, a compatibilidade PyWa 4.5.0, a exceção universal de idade 90+, o comentário livre e a despedida por participante.

No corte de implantação, parar webhook, flow, Funil e follow-up antes da migração das etapas. Incluir Consumo Meta na parada controlada se houver indisponibilidade de banco; ao retomar, verificar os cinco serviços e preservar as variáveis existentes de Consumo. Não alterar tokens, versões de dependências ou o .env só para introduzir a rota sem link.


## Worker de consulta FireAds

O sexto serviço é `chatbot-worker-consulta-dash.service`. Aplicar com a migração
`migrations/20261009_worker_consulta_dash.sql`, sem executar setup numa base existente.
Seguir o [procedimento e recuperação](../docs/valida_dados_parciais_fireads.md).
