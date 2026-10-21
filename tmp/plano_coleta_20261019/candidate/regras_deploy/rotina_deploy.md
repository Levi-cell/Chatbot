# Rotina de deploy da branch `prod`

Procedimento para atualizar a aplicação na Lightsail. Referência atual:
**V1.2.0**, com monitoramento e follow-up implantados. Versões e hashes ficam em
[VERSIONAMENTO.md](../VERSIONAMENTO.md).

## Ambiente e serviços

- repositório: `/opt/chatbot/app`, branch `prod`;
- ambiente virtual: `/opt/chatbot/venv`;
- configuração: `/etc/chatbot/chatbot.env`;
- webhook: `https://webhook.3esltech.com/webhook`;
- monitoramento: `https://monitoramento.3esltech.com/`;
- banco PostgreSQL no RDS e Redis remoto.

| Serviço | Responsabilidade |
|---|---|
| `chatbot-webhook.service` | Gunicorn/Django: webhook, Admin e monitoramento. |
| `chatbot-worker-flow.service` | Consome a fila, atende e trata a retomada após follow-up. |
| `chatbot-worker-funil.service` | Publica oportunidades no CRM. |
| `chatbot-worker-followup.service` | Envia o primeiro lembrete e, após mais 7h sem resposta, a despedida que encerra o atendimento. |

O painel compartilha o serviço web; seu polling não cria outro processo.
Há uma instância de cada worker. O follow-up é um processo contínuo, com lotes
padrão de até 20 candidatas e espera de 60 segundos, não um timer de meia hora.

## Escolher o alcance da atualização

| Alteração | Ação necessária |
|---|---|
| Somente documentação | Atualizar o checkout; não reiniciar serviços. |
| Somente painel, sem módulos compartilhados pelos workers | Atualizar, publicar estáticos se mudaram e recarregar o webhook se Python/templates mudaram; workers podem continuar. |
| Worker ou módulo compartilhado | Parar os workers afetados antes do pull; se flow ou seu contrato mudar, parar follow-up primeiro e retomá-lo por último. |
| Dependências Python | Atualizar o venv com os processos consumidores parados; avaliar a interrupção do webhook. |
| `.env` ou unit | Instalar/validar a alteração e reiniciar os serviços afetados; `HUP` não relê `EnvironmentFile`. |
| Schema | Aplicar somente a migração específica ainda pendente, antes de iniciar o código dependente. |

A sequência abaixo cobre alterações dos workers e de código compartilhado com
schema compatível. O webhook pode continuar enfileirando enquanto eles estão
parados. Uma mudança de banco incompatível com o webhook ativo exige janela de
manutenção ou estratégia expand/contract, conforme o
[guia de ambiente e banco](modificando_env_e_banco_em_prod.md).

## 1. Preparar e publicar no computador local

Antes de começar uma alteração, confira a branch e preserve qualquer trabalho
local. Com o checkout limpo:

```powershell
git switch prod
git status --short
git pull --ff-only origin prod
```

Depois de implementar, execute os testes do comportamento afetado. Alterações
de follow-up/SQL também exigem a integração PostgreSQL descartável descrita em
[tests/README.md](../tests/README.md#follow-up).

```powershell
python -m unittest discover -s tests -t . -p "test_*.py"
git diff --check
git status --short
```

Prepare somente os arquivos revisados para o commit. Confira antes de publicar:

```powershell
git diff --cached --name-status
git diff --cached --check
git commit -m "Descreva objetivamente a atualizacao"
git push origin prod
git rev-parse HEAD
```

Anote o hash completo. Não inclua `.env`, segredos, certificados privados ou
dumps. Não use `reset --hard` para contornar alterações locais.

## 2. Parar os workers afetados na VM

Na atualização completa, pare o proativo antes do flow:

```bash
sudo systemctl stop chatbot-worker-followup.service
sudo systemctl stop chatbot-worker-flow.service chatbot-worker-funil.service
systemctl is-active chatbot-webhook.service
systemctl is-active chatbot-worker-flow.service chatbot-worker-funil.service chatbot-worker-followup.service
```

Esperado: webhook `active` e três workers `inactive`. O código de saída não zero
de `is-active` para serviço parado é esperado. Em instalação anterior ao follow-up,
ele ainda pode não ter unit; siga a [primeira ativação](../deploy/README.md#ativação-do-follow-up).

## 3. Atualizar o checkout

```bash
cd /opt/chatbot/app
git status --short
git fetch origin
git checkout prod
git pull --ff-only origin prod
git rev-parse HEAD
```

O status deve estar vazio antes do pull, e o hash final deve coincidir com o
aprovado. Se houver divergência, preserve os arquivos e investigue antes de seguir.

## 4. Aplicar somente as migrações pendentes

Leia o SQL da versão e execute o script completo no DBeaver, contra o banco
correto e com a role apropriada, enquanto os workers dependentes estão parados.
Confira as validações e a conclusão do `COMMIT`. Em erro, execute `ROLLBACK` e
investigue; não aplique apenas fragmentos para contornar a falha.

**O follow-up já foi migrado na produção em 10/09/2026.**
`deploy/migrations/followup_registros.sql` marcou 106 conversas ativas naquele
deploy. Esse número é histórico, não uma condição para verificações futuras.
Não reexecute esse arquivo nos próximos deploys. Novas conversas e retomadas
alteram os contadores normalmente.

**Segunda camada de follow-up:** aplicar apenas a nova migração pendente
`deploy/migrations/20260924_segundo_followup.sql`, que libera o motivo
`followup_sem_resposta` sem alterar conversas existentes. O diagnóstico e o worker
recusam envios se essa migração estiver ausente. Publicar os estáticos do painel
para disponibilizar o filtro **Follow-up**.

`manage.py migrate` cuida somente dos modelos gerenciados pelo Django; não
substitui as migrações de negócio. `setup_database.py` serve à instalação limpa,
nunca à atualização de um RDS existente.

## 5. Dependências, Django e arquivos estáticos

Se `requirements.txt` mudou, atualize o venv conforme o alcance definido:

```bash
/opt/chatbot/venv/bin/pip install -r /opt/chatbot/app/requirements.txt
```

Para conferir Django com o mesmo ambiente dos serviços:

```bash
sudo -u chatbot bash -c 'set -a; source /etc/chatbot/chatbot.env; set +a; cd /opt/chatbot/app; export PYTHONPATH=/opt/chatbot/app PYTHONDONTWRITEBYTECODE=1; /opt/chatbot/venv/bin/python callback/manage.py check --deploy'
```

Execute `migrate --noinput` somente quando houver migrations Django pendentes,
e `collectstatic --noinput` quando os arquivos estáticos mudarem:

```bash
sudo -u chatbot bash -c 'set -a; source /etc/chatbot/chatbot.env; set +a; cd /opt/chatbot/app; export PYTHONPATH=/opt/chatbot/app PYTHONDONTWRITEBYTECODE=1; /opt/chatbot/venv/bin/python callback/manage.py migrate --noinput'
sudo -u chatbot bash -c 'set -a; source /etc/chatbot/chatbot.env; set +a; cd /opt/chatbot/app; export PYTHONPATH=/opt/chatbot/app PYTHONDONTWRITEBYTECODE=1; /opt/chatbot/venv/bin/python callback/manage.py collectstatic --noinput'
```

Esses comandos carregam explicitamente o ambiente porque a sessão SSH não herda
`EnvironmentFile`. Não imprima os valores do arquivo. Mudança somente em Python
de exportação CSV exige recarga web, mas não `collectstatic`.

## 6. Instalar units alteradas

Instale somente as units que mudaram. Exemplo para o follow-up:

```bash
sudo install -m 0644 /opt/chatbot/app/deploy/systemd/chatbot-worker-followup.service /etc/systemd/system/chatbot-worker-followup.service
sudo systemctl daemon-reload
sudo systemd-analyze verify /etc/systemd/system/chatbot-worker-followup.service
```

Instalar uma unit e recarregar o systemd não inicia o serviço. A unit do follow-up
define `FOLLOWUP_WORKER_ENABLED=true`, lote 20 e intervalo 60. Se essas chaves
também estiverem no `EnvironmentFile`, os valores do arquivo prevalecem.

## 7. Diagnosticar o follow-up sem envio

Com o schema instalado, valide o acesso usando a identidade da aplicação:

```bash
sudo -u chatbot bash -c 'set -a; source /etc/chatbot/chatbot.env; set +a; cd /opt/chatbot/app; export PYTHONPATH=/opt/chatbot/app PYTHONDONTWRITEBYTECODE=1; /opt/chatbot/venv/bin/python -m utilitarios.verificar_followup'
```

Esperado: `FOLLOWUP_CONSULTA_OK_SEM_ENVIO`. A amostra pode estar vazia.
Os [indicadores do diagnóstico](../utilitarios/README.md#diagnóstico-de-follow-up)
não são contagem de mensagens enviadas. O comando não comprova permissões de
escrita: as novas tabelas devem pertencer à role usada pela aplicação ou receber
as permissões necessárias antes da ativação.

## 8. Carregar o código web atualizado

Quando somente código Python/templates mudou, recarregue o Gunicorn:

```bash
sudo systemctl kill --signal=HUP --kill-who=main chatbot-webhook.service
sudo journalctl -u chatbot-webhook.service --since "5 minutes ago" -n 60 --no-pager
curl --fail --silent --show-error https://webhook.3esltech.com/webhook
curl --fail --silent --show-error --output /dev/null --write-out '%{http_code}\n' https://monitoramento.3esltech.com/login/
```

Espere a inicialização dos novos processos no journal e confira `Webhook ativo`
e HTTP `200` no login. `git pull` sozinho não recarrega o Gunicorn. Se o ambiente
ou a unit do webhook mudou, use `sudo systemctl restart chatbot-webhook.service`
e repita as verificações; nesse caso há uma interrupção breve.

## 9. Retomar flow e Funil antes do follow-up

Inicie os serviços que foram parados:

```bash
sudo systemctl start chatbot-worker-flow.service chatbot-worker-funil.service
systemctl is-active chatbot-worker-flow.service chatbot-worker-funil.service
sudo journalctl -u chatbot-worker-flow.service -u chatbot-worker-funil.service --since "5 minutes ago" -n 80 --no-pager
```

Somente após confirmar flow compatível ativo, sem falha de inicialização ou
acesso ao banco, inicie o proativo:

```bash
sudo systemctl start chatbot-worker-followup.service
sudo systemctl show chatbot-webhook.service chatbot-worker-flow.service chatbot-worker-funil.service chatbot-worker-followup.service -p Id -p ActiveState -p SubState -p NRestarts --no-pager
sudo journalctl -u chatbot-worker-followup.service --since "5 minutes ago" -n 80 --no-pager
```

Na primeira ativação, use `enable --now` em vez de apenas `start` para habilitar
o boot. Uma pausa deliberada de lembretes deve ser respeitada em deploys seguintes.
`After=network-online.target` não valida que o flow está pronto; essa conferência
pertence à operação.

Os quatro serviços devem ficar `active`/`running`, sem crescimento contínuo de
`NRestarts`. O follow-up registra `followup_iniciado`, mas não emite INFO a cada
consulta vazia. `followup_confirmado` comprova persistência local de um envio;
não force elegibilidade nem remova proteções para gerar um teste em produção.

## 10. Interromper lembretes ou recuperar uma falha

Para desativar somente os lembretes, mantendo o atendimento capaz de retomar:

```bash
sudo systemctl disable --now chatbot-worker-followup.service
```

Mantenha o flow compatível com `followup_retomada` e stage positivo. Não apague
recibos/tabelas, não zere stages em massa e não volte ao flow anterior à V1.2.0
enquanto houver ciclos positivos ou retomadas pendentes. A marcação do legado
não pode ser revertida sobrescrevendo estágios que já mudaram após a migração.

Falha no deploy exige leitura do journal do serviço afetado e correção da causa.
Se precisar reverter código, prepare e teste um commit de reversão compatível
com o schema e os registros atuais antes de publicar; não force o checkout antigo
na VM. Se o webhook falhar, priorize restaurá-lo para voltar a receber eventos.

Diagnósticos adicionais de Redis e manutenção ficam em
[servicos_e_redis_remoto.md](servicos_e_redis_remoto.md). Use o ambiente configurado:
`redis-cli ping` sem host consulta o Redis local e não valida a produção.
