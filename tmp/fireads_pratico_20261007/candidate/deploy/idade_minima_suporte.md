# Publicação do suporte por idade mínima

Este procedimento pertence à entrega que substitui `unidade.suporte_idoso` por
`idade_minima_suporte`. Código, SQL, Admin e painel devem ser publicados juntos.
O modelo Django é `managed=False`; `manage.py migrate` não converte essa coluna.
Não há nova configuração de `.env`, serviço ou alteração dos ciclos do follow-up.

## Homologação antes de produção

1. Materializar todos os arquivos da entrega e revisar o diff. Preservar a etapa
   10, as tags fixas, os quatro CSVs e as proteções transacionais do flow.
2. Executar a suíte unitária na raiz, com as dependências do projeto:

```powershell
python -B -m unittest discover -s tests -t . -p "test_*.py"
```

3. Criar um banco PostgreSQL local vazio chamado `test_chatbot_suporte_idade`,
   exclusivo de testes. `SUPORTE_IDADE_TEST_DSN` deve indicar esse banco com host
   loopback e credenciais locais. Nunca usar a conexão de produção do DBeaver
   nessa variável. Com ela configurada, executar:

```powershell
python -B -m unittest tests.integration.test_suporte_por_idade_postgres
```

O teste cria e remove somente seu próprio schema `chatbot`, recusa um schema
preexistente, aplica o SQL integral, verifica conversão, defaults, domínio,
reaplicação, schema parcial e rollback. Sem a variável, o teste é pulado;
um resultado pulado não comprova que a migração foi homologada.

4. Confirmar os senders com Meta simulada e homologar manualmente o CTA em uma
   unidade de teste, sem usar leads reais. O botão continua abrindo o WhatsApp
   comercial e a mensagem usa a faixa configurada.
5. Conferir Admin e relatórios em computador e celular, em retrato e paisagem.
   Trocar períodos, conferir zero real, erro de consulta e histórico de suporte.
6. Registrar o commit aprovado e um backup recuperável do banco de produção.
   O SQL não é um mecanismo de backup. Garantir que o backup pode ser restaurado
   antes da janela de manutenção.

## Janela de manutenção

Antes de iniciar, interromper execuções manuais de relatórios e edições no Admin.
Guardar o commit anterior retornado abaixo para eventual retorno:

```bash
cd /opt/chatbot/app
git status --short
git rev-parse HEAD
```

A árvore precisa estar limpa. Conferir que a branch e o commit remoto correspondem
à entrega revisada. Os comandos abaixo usam a branch de produção atual do projeto:

```bash
git fetch origin
git checkout prod
```

Parar primeiro o follow-up e depois os demais consumidores. A indisponibilidade
do webhook é parte desta manutenção; não manter processos antigos lendo a coluna
removida e não iniciar o código novo antes da migração.

```bash
sudo systemctl stop chatbot-worker-followup.service
sudo systemctl stop chatbot-worker-flow.service chatbot-worker-funil.service chatbot-webhook.service
systemctl is-active chatbot-worker-followup.service chatbot-worker-flow.service chatbot-worker-funil.service chatbot-webhook.service
```

Só continuar quando todos estiverem `inactive`:

```bash
git pull --ff-only origin prod
git rev-parse HEAD
```

Conferir o hash aprovado. Não executar `setup_database.py` e não reaplicar a
migração do follow-up ou os scripts antigos de criação das flags.

## Momento de executar o SQL no DBeaver

**Executar agora o conteúdo integral de
`deploy/migrations/20260911_idade_minima_suporte.sql`, de BEGIN a COMMIT, na
conexão de produção correta.** Usar a execução do script completo, não apenas
a instrução sob o cursor. O arquivo contém as pré-condições e pós-condições.

O resultado deve preservar a quantidade de unidades: habilitadas antes viram
60 e desativadas antes viram NULL. Nenhuma conversa ou stage é alterado.
Após sucesso e COMMIT, conferir em nova consulta:

```sql
SELECT idade_minima_suporte, COUNT(*) AS unidades
FROM chatbot.unidade
GROUP BY idade_minima_suporte
ORDER BY idade_minima_suporte NULLS FIRST;

SELECT column_name, data_type, is_nullable, column_default
FROM information_schema.columns
WHERE table_schema = 'chatbot' AND table_name = 'unidade'
  AND column_name IN ('suporte_idoso', 'idade_minima_suporte');
```

Se houver erro, executar `ROLLBACK` na mesma sessão e manter os serviços parados
até identificar o estado do banco. Não ignorar uma exceção nem executar trechos
soltos para contornar as pré-condições.

## Validação e retomada

Na VM, carregar o ambiente sem imprimir segredos e verificar o Django:

```bash
sudo -u chatbot bash -c 'set -a; source /etc/chatbot/chatbot.env; set +a; cd /opt/chatbot/app; export PYTHONPATH=/opt/chatbot/app PYTHONDONTWRITEBYTECODE=1; /opt/chatbot/venv/bin/python callback/manage.py check --deploy'
```

Revisar o resultado; warnings já conhecidos não devem esconder erros novos.
Publicar o CSS/JS com a referência de cache atualizada pelo template:

```bash
sudo -u chatbot bash -c 'set -a; source /etc/chatbot/chatbot.env; set +a; cd /opt/chatbot/app; export PYTHONPATH=/opt/chatbot/app PYTHONDONTWRITEBYTECODE=1; /opt/chatbot/venv/bin/python callback/manage.py collectstatic --noinput'
sudo systemctl start chatbot-webhook.service chatbot-worker-flow.service chatbot-worker-funil.service
systemctl is-active chatbot-webhook.service chatbot-worker-flow.service chatbot-worker-funil.service
sudo journalctl -u chatbot-worker-flow.service -u chatbot-webhook.service --since "5 minutes ago" -n 80 --no-pager
```

Confirmar que o flow compatível está funcionando e sem erros de coluna/contexto.
Somente então retomar o follow-up já instalado:

```bash
sudo systemctl start chatbot-worker-followup.service
sudo systemctl show chatbot-webhook.service chatbot-worker-flow.service chatbot-worker-funil.service chatbot-worker-followup.service -p Id -p ActiveState -p SubState -p NRestarts --no-pager
curl --fail --silent --show-error --output /dev/null --write-out '%{http_code}\n' https://monitoramento.3esltech.com/login/
```

No navegador, validar o seletor do Admin, os quatro downloads, tags fixas e o
card de encaminhamentos em todos os períodos. Conferir logs e relatórios manuais.
Manter as unidades em NULL/60 até concluir essa conferência; a escolha de outras
faixas é uma edição posterior e deliberada do proprietário.

## Retorno de versão

Parar os quatro consumidores e suspender relatórios/edições como na manutenção.
Um `git checkout` isolado não restaura compatibilidade com a coluna antiga.

- Se a migração falhou e houve rollback, confirmar a presença de `suporte_idoso`
  booleano antes de retornar ao commit anterior.
- Se a migração foi confirmada e todas as unidades ainda estão em NULL/60,
  executar integralmente `deploy/rollback/20260911_idade_minima_suporte.sql` no
  DBeaver. Ele converte NULL para FALSE e 60 para TRUE e preserva os demais dados.
- Havendo 50/70/80/90, a reversão é recusada. Decidir entre corrigir a nova versão
  ou restaurar uma configuração anterior validada com o responsável. Não
  transformar todos os limites em TRUE e não apagar históricos de atendimento.

Após o schema voltar ao booleano, selecionar o **hash anterior que foi registrado**,
republicar os estáticos dessa versão, executar o check e retomar os serviços.
Não usar `reset --hard` para descartar mudanças locais ou reescrever histórico Git.
Uma restauração integral de backup exige avaliar também as mensagens recebidas
desde o backup; não é substituída automaticamente pelo SQL de reversão.
