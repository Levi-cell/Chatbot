# Implantacao no Lightsail

Os arquivos assumem a aplicacao em `/opt/chatbot/app`, o ambiente virtual em
`/opt/chatbot/venv` e as variaveis em `/etc/chatbot/chatbot.env`. Os processos
da aplicacao sao independentes e escrevem seus logs no journald. O
portal de monitoramento faz parte do processo web `chatbot-webhook`; ele não
cria outro serviço. O inventário atual contém seis workers e esse serviço web;
responsabilidades e nomes estão em [workers/README.md](../workers/README.md).
Este guia também cobre a preparação de uma instalação nova.

## Perfis, anúncios Google e worker de origem — 24/10/2026

**Atualização a partir da V1.16.1: não requer migração SQL, novas colunas,
índices ou alterações no Apps Script.** Reutiliza `conversa.contexto_fireads` e
as estruturas já migradas de coleta/entregas. Não executar setup/seeds nem
reaplicar os SQLs históricos. O novo processo é opcional e começa desativado.

1. Atualizar o código na rotina habitual, respeitando a parada dos processos
   afetados antes do pull. Esta versão altera o leitor de atribuição usado por
   consulta-dash/Funil, o predicado de elegibilidade do Funil e o serviço web.
2. Rodar os testes unitários indicados abaixo e `callback/manage.py check` com
   o ambiente da VM carregado. Os testes PostgreSQL exigem um banco descartável
   local explícito: **não usar o banco de produção** como banco de teste.
3. Executar `callback/manage.py collectstatic --noinput` para publicar o novo
   `origens.js`, o painel e o CSS. Reiniciar/recarregar o web; ele precisa receber
   também a configuração do próximo passo.
4. Em `/etc/chatbot/chatbot.env`, definir `FIREADS_ORIGEM_ATIVO=True` e
   `FIREADS_ORIGEM_DESDE` com a data/hora **fixa** de ativação, em ISO 8601 com
   fuso. `date --iso-8601=seconds` fornece um valor para copiar uma única vez.
   Não colocar substituição dinâmica de comando nesse arquivo. Preservar esse
   marco nos reinícios/deploys seguintes; movê-lo para trás habilita retroação
   que não faz parte desta entrega. Para apenas publicar a interface, manter a
   flag falsa: a ajuda não anuncia a verificação periódica nesse caso.
5. Instalar/iniciar o novo serviço depois das validações e da retomada dos
   serviços existentes. Nenhuma regra de atendimento espera esse processo.

```bash
sudo install -m 0644 /opt/chatbot/app/deploy/systemd/chatbot-worker-origem-fireads.service /etc/systemd/system/chatbot-worker-origem-fireads.service
sudo systemctl daemon-reload
sudo systemctl enable --now chatbot-worker-origem-fireads.service
sudo systemctl status chatbot-worker-origem-fireads.service --no-pager
sudo journalctl -u chatbot-worker-origem-fireads.service -n 60 --no-pager
```

O primeiro ciclo ocorre ao iniciar; os seguintes esperam 7.200s **após o término**
do anterior. Um ciclo longo aumenta o intervalo observado; não há promessa de
identificar tudo em até duas horas. Cada leitura da FireAds tem orçamento 300s;
uma leitura por integração/aba atende as candidatas do ciclo. Lotes são páginas
de 100, sem teto de 100 pendências por execução. O marco fixo evita varrer o
histórico anterior à ativação. Nenhum POST FireAds, WhatsApp ou Funil é feito
pelo novo serviço.

Validação unitária direcionada (no ambiente Python configurado):

```bash
/opt/chatbot/venv/bin/python -m unittest \
  tests.unit.test_origem_fireads \
  tests.unit.test_monitoramento_origens \
  tests.unit.test_monitoramento_painel \
  tests.unit.test_fireads_entrega_telefone \
  tests.unit.test_fluxo_reserva_link -q
```

Conferir `origem_iniciado`, ausência de reinícios e os contadores de
`origem_ciclo`. Um ciclo sem candidatas é normal. No monitoramento da unidade
integrada, conferir “Ver perfis”, ajuda e os grupos Meta/Google em diferentes
períodos. Unidade sem FireAds mantém o painel sem esse bloco.

Para desativar a rotina, parar/desabilitar o novo serviço e definir
`FIREADS_ORIGEM_ATIVO=False`, recarregando o web. Não remover a evidência JSON
já salva. A flag da interface representa a configuração, não um monitor de
saúde do processo; estado e falhas devem ser conferidos no systemd/journal.
Reversão de código precisa manter a leitura de `verificacao_origem` para não
reinterpretar canal desconhecido como origem orgânica legada.

Contrato real conferido em 24/10/2026: leitura da integração Santo André e GET
da aba `LEADS GERAL - Feedback` concluídos, com `WhatsApp`, `Canal`, `Data/Hora`
e `Anuncio` presentes. A interpretação de canais/anúncios foi validada em memória
com os registros reais Meta/Google, sem escrita no banco ou na FireAds.
A falha anterior era o caminho Linux do certificado RDS no Windows. A conferência
usou o bundle oficial AWS local apenas no processo, mantendo `verify-full` e sem
alterar o `.env` destinado à VM. Após o deploy, conferir também a operação do
novo serviço pelos logs e por um atendimento elegível, sem reprocessar históricos.

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

A configuração atual de `unidade.link_agendamento` decide a saída da triagem: com link, 17 → 20; sem link, 17 → 18 (preferência de turno) → 19 (contato comercial), ou 17 → 19 quando o turno já estiver salvo. A satisfação converge em 21 → 22 → 23 → 24, com salto 22 → 24 na recusa de comentário. As etapas 1–17 conservam suas regras.

`conversa.turno` aceita NULL, manha, tarde, noite ou sabado. Pode ser salvo na abertura sem link ou na transação de 18 → 19; preferência antecipada permite 17 → 19. É preferência, não confirmação de agendamento. Qualquer texto posterior na 19 apresenta a nota da 21; não é interpretado como nota nessa mesma interação. Mídia repete a orientação da 19.

O Funil exige 20–24 com link ou 19/21–24 sem link, considerando a configuração vigente na seleção, no claim e no snapshot. Preservar recibo de sucesso se o CRM já aceitou. O snapshot e o painel incluem turno da própria conversa, quando preenchido.

Follow-up proativo: 1–17 em ambas as rotas e 18 somente sem link; a 19 e a 20 não recebem novos lembretes. São preservadas as duas camadas de sete horas, os recibos, o encerramento no segundo lembrete e as guardas existentes. A reação ao primeiro segue a validação normal: um turno válido na 18 avança para 19 e é persistido. Contexto inválido genérico repete; tratamentos específicos continuam prioritários. Retomadas legadas são remapeadas por significado; a exceção 8 → 9 permanece.

Instalação existente exige migração própria: IDs antigos 18/19/20/21/22 tornam-se 20/21/22/23/24. Não executar setup ou seeds no banco de produção nem reaplicar migrações históricas. Preservar o Consumo Meta, seus fusos, worker, relatórios e PDFs, a compatibilidade PyWa 4.5.0, a exceção universal de idade 90+, o comentário livre e a despedida por participante.

No corte de implantação, parar webhook, flow, Funil e follow-up antes da migração das etapas. Incluir Consumo Meta na parada controlada se houver indisponibilidade de banco; ao retomar, verificar os cinco serviços e preservar as variáveis existentes de Consumo. Não alterar tokens, versões de dependências ou o .env só para introduzir a rota sem link.


## Worker de consulta FireAds

O sexto serviço é `chatbot-worker-consulta-dash.service`. Aplicar com a migração
`migrations/20261009_worker_consulta_dash.sql`, sem executar setup numa base existente.
Seguir o [procedimento e recuperação](../docs/valida_dados_parciais_fireads.md).


## FireAds: aba única e observações compartilhadas — 14/10/2026

Para atualizar a instalação com worker_consulta_dash já implantado, executar
[migrations/20261014_fireads_aba_geral.sql](migrations/20261014_fireads_aba_geral.sql)
com os seis serviços parados, junto do código desta atualização. Conferir
`migracao_ok=true` e `manage.py check` antes de retomá-los. Não reaplicar setup.
[Procedimento, preservação de pendências e recuperação](../atualizar_envio.md#14-entrega-local-e-procedimento-desta-atualização).

## Coleta parcial na abertura — 20/10/2026

Esta atualização exige [a migração de coleta por conversa](migrations/20261019_coleta_abertura.sql),
após a migração da aba geral de 14/10. Parar webhook e todos os workers, atualizar
o código e executar o SQL inteiro no DBeaver antes de reiniciar os serviços.
Conferir `migracao_ok=true`, `transicao_ok=true`, leitura do model `Conversa` e
`manage.py check`. Não executar setup/seeds numa base existente.

A coluna `conversa.contexto_coleta` é independente de FireAds e preserva os campos
da primeira mensagem e os dados completados durante o atendimento. Conversas
antigas permanecem com contexto nulo. A nova transição 1 → 4 exige destinatário
já coletado; e-mail ausente continua sendo perguntado somente na etapa 10.
O [plano aplicado](../docs/valida_dados_parciais_fireads.md) detalha os cenários,
as verificações e as restrições de reversão após iniciar conversas novas.

## Chat Fire e turno antecipado — 21/10/2026

Para o deploy que ainda não aplicou a coleta parcial, executar inteiro apenas
[migrations/20261021_coleta_chat_fire_completa.sql](migrations/20261021_coleta_chat_fire_completa.sql).
Esse consolidado contém os mesmos blocos de 19/10 e 21/10 em uma transação e
substitui a execução separada abaixo. Conferir `coleta_ok`, `chat_fire_turno_ok`,
`transicao_1_4_ok` e `transicao_17_19_ok` verdadeiros, e `tamanho_turno=6`.

Como alternativa ao consolidado, após a migração de coleta de 19/10, executar
[migrations/20261021_chat_fire_turno_coleta.sql](migrations/20261021_chat_fire_turno_coleta.sql)
com webhook e todos os workers parados. Inclui a origem Chat Fire, o turno sábado
e a transição 17 → 19 para preferência já coletada. Conferir `migracao_ok=true`,
`transicao_ok=true` e `tamanho_turno=6`. O SQL preserva dados existentes e aceita
reexecução. Atualizar código e schema juntos; não executar setup em produção.
Executar `collectstatic --noinput` para o rótulo de sábado no monitoramento.
Contrato e validação: [Chat Fire e turno antecipado](../docs/chat_fire_turno_antecipado.md).

A V1.14.0 publicada em `5fc047e` atualiza somente Observação e não exige ampliar
`EDITABLE_COLUMNS` para os quatro campos.

## Sincronização de campos FireAds — aplicação local em 22/10/2026

O [plano prático](../docs/fireads_sincronizacao_campos.md) está aplicado no código
local. Novos envios com coleta congelam snapshot 4 e sincronizam Nome, Email,
Para quem é e Período preferido quando aceitos no chatbot; turno apenas sem link.
Antes de publicar este código em produção, confirmar com a FireAds a liberação
dessas colunas no Web App existente, a presença dos cabeçalhos no GET e o recibo
de todas as colunas atualizadas no POST, conforme o último passo do plano.
Não basta alterar o código-fonte do Apps Script: a implantação `/exec` precisa
usar a versão liberada. Validar o contrato com um registro de teste autorizado.

Não há nova migração SQL: reutiliza a estrutura da V1.14.0. Não converter snapshots
antigos nem reprocessar envios concluídos. Se a API recusar uma coluna ou retornar
recibo incompleto, o dashboard permanece pendente para retomada; isso não deve
reenviar um lead já confirmado no Funil. Os testes locais simulam a API e não
atestam que a implantação externa foi atualizada.


## Telefone, dashboard antes do Funil e prazos — revisão de 22/10/2026

Atualização sobre a V1.15.0; sem SQL novo, sem alteração de dependências e sem
conversão de snapshots existentes. Novas entregas FireAds gravam snapshot 5,
resolvem o canal pela linha mais recente do telefone e só enviam ao Funil após
a confirmação do dashboard. A indisponibilidade FireAds passa a adiar o Funil
nessas unidades. Unidade sem FireAds mantém seu envio direto e código configurado.

Parar follow-up, flow, consulta-dash e Funil antes de atualizar esses módulos;
executar checks/testes e retomar consulta-dash/flow, depois follow-up e Funil.
Nenhum comando de migração deve ser executado para esta revisão. Preservar as
migrações já aplicadas na V1.14.0. Não reiniciar/reprocessar envios sent.

Cada GET/POST FireAds tem 300s próprios; redirects compartilham o orçamento da
operação. A consulta pendente tem até 300s na fila, e ao ser reservada ganha
330s (300 HTTP + 30 de margem). Dashboard reserva 960s. O prazo efetivo do Funil
é no mínimo 960s, mesmo com configuração antiga de 900s, para cobrir a preparação,
GET e POST sequenciais. Reinício durante uma escrita exige reconciliação e pode
aguardar a expiração da reserva; reiniciar não ignora next_attempt_at.

Manter as colunas/recibos FireAds liberados para V1.15.0. Sem formulário elegível,
canal desconhecido/vazio mantém pendente sem atribuir código. Só os quatro canais
de formulário permitem reutilizar linha. Somente Orgânico ou canais manuais levam
a novo Orgânico (113481); retentativas reconciliam a própria entrega.

Validação direcionada: `tests.unit.test_fireads_entrega_telefone` e
`tests.integration.test_entrega_fireads_primeiro_postgres`, além da regressão de
coleta/turno/digitando e entregas legadas. Integração somente em banco descartável
local `test_chatbot_fireads`; nunca usar credenciais de produção na suíte.

Rollback: snapshots 5 não são entendidos pelo código V1.15.0. Não voltar esse
worker enquanto houver entregas 5 pendentes sem antes resolver sua compatibilidade.
As observações e payloads históricos permanecem congelados.

## Monitoramento FireAds, filtros e relatórios — revisão de 22/10/2026

Sem migração SQL adicional: origem e anúncio usam a chave versionada
`atribuicao_monitoramento` no JSONB `contexto_fireads` existente e no snapshot da
entrega. Não rodar backfill nem reprocessar atendimentos antigos. Meta sem anúncio
entra em “Anúncio não informado”; origem sem evidência fica não identificada.

Esta revisão também altera Django e arquivos estáticos: além dos workers acima,
parar/reiniciar `chatbot-webhook.service` no deploy e executar `manage.py check`
e `manage.py collectstatic --noinput` com o usuário/ambiente chatbot. Os URLs de
CSS/JS receberam nova versão para evitar cache antigo no navegador. Conferir os
filtros e o bloco Origem dos atendimentos em unidade integrada e não integrada.
Nenhum serviço systemd, variável de ambiente ou dependência nova é necessária.

Validar `tests.unit.test_monitoramento_origens`, `test_monitoramento_painel` e
`test_encerramentos_por_idade`, além das suítes FireAds. Testes SQL de período,
isolamento e contagens ficam em `tests.integration.test_monitoramento_fireads_postgres`
e só devem rodar no PostgreSQL descartável local especificado pela suíte.

### Correção de leitura JSONB do monitoramento — 23/10/2026

O repositório do painel converte `contexto_fireads` e `dados_consulta` retornados
como texto pelo cursor do Django antes da apresentação. Corrige falha ao carregar
Conversas/Relatórios com consulta FireAds salva e a ausência consequente dos filtros.
Sobre a V1.16.0 já instalada, atualizar o código, executar `manage.py check` e
`tests.unit.test_monitoramento_origens`/`tests.unit.test_monitoramento_painel`, e
recarregar `chatbot-webhook.service`. Esta correção isolada não exige SQL,
collectstatic, mudança de configuração nem reinício dos workers. Confirmar as
rotas autenticadas de dados em unidade integrada: HTTP 200 no login sozinho não
exercita a leitura de origem. O teste adicional com Django/PostgreSQL usa somente
o banco descartável local da suíte de integração.
