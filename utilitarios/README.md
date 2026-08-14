# Utilitários operacionais

Comandos manuais de monitoramento, diagnóstico e manutenção. Esta pasta não é
importada pelo webhook, pelo `flow_worker`, pelo `funil_worker` nem pelo Django
Admin.

## Fronteira

```text
serviços de produção -> core/callback/workers
operador humano      -> utilitarios -> primitivas de core
```

Os módulos daqui podem consultar ou manter recursos de produção quando
executados conscientemente. Nenhum deles roda por import e nenhum serviço deve
depender de `utilitarios`.

## Estrutura

```text
utilitarios/
├── bootstrap.py
├── local_settings.py       configuração privada local, ignorada pelo Git
├── montar_lead_teste.py
├── cache_consulta.py
├── utlitys.py
├── pintregister.py
├── operacoes_rotineiras.sql
├── monitoring/
│   ├── blocked_users.py
│   ├── infrastructure.py
│   └── suspicious_conversations.py
├── maintenance/
│   ├── cache_reset.py
│   └── message_partitions.py
└── integrations/
    └── funil_probe.py
```

As ferramentas foram preparadas para execução local no PyCharm. Nesse modo, o
`.env` da raiz é lido explicitamente e os ajustes privados de
`utilitarios/local_settings.py`, arquivo ignorado pelo Git, são aplicados por
cima dele. Assim, o SSL do PostgreSQL continua compatível com o Windows sem
misturar variáveis antigas herdadas do processo. Os comandos que aceitam
`--env-file` devem receber `/etc/chatbot/chatbot.env` quando forem executados na
VM; eles nunca dependem do arquivo privado local.

## Regra de pertencimento

Um arquivo pertence a `utilitarios/` quando é um comando iniciado
conscientemente por uma pessoa para diagnóstico, monitoramento, manutenção ou
probe. Nenhum dos quatro pontos de entrada da aplicação — webhook,
`worker_flow`, `worker_funil` e Django Admin — pode importar esta pasta.

Não pertencem a `utilitarios/`:

- primitivas reutilizadas pelos quatro pontos de entrada, que ficam em `core`;
- instalação e DDL inicial, que ficam em `core/database/deploy_database`;
- migrações incrementais, que ficam em `deploy/migrations`;
- entrypoints do framework ou dos serviços, como `manage.py`, WSGI e workers;
- testes, mocks e fixtures de validação automatizada, que ficam em `tests`.

Todo módulo desta pasta deve ser seguro por import: importar define funções,
mas não conecta ao banco/Redis, não chama APIs, não imprime relatórios e não
altera dados. Operações mutantes exigem confirmação explícita.

Os relatórios principais podem ser executados diretamente pelo botão verde do
PyCharm. Os comandos `python -m` continuam disponíveis para filtros avançados.

No Windows, os módulos também podem ser executados diretamente pelo botão
**Run** do PyCharm. O caminho Linux configurado em `DB_SSLROOTCERT` é
automaticamente resolvido para o bundle público do RDS incluído em
`deploy/certificates`, mantendo `verify-full`.

## Consultas e alteração manual do PIN Meta

Os três comandos abaixo usam `utilitarios/local_settings.py` no Windows. Na VM,
acrescente `--env-file /etc/chatbot/chatbot.env`:

```bash
python -m utilitarios.cache_consulta --limite 200
python -m utilitarios.utlitys --phone-number-id PHONE_ID
python -m utilitarios.pintregister \
  --phone-number-id PHONE_ID \
  --confirm-phone-number-id PHONE_ID \
  --confirm-real-change
```

Os identificadores são mascarados nas consultas por padrão. O último comando é
mutante, lê o PIN somente do ambiente e exige repetição exata do alvo mais a
confirmação explícita; token, PIN e resposta bruta da Meta nunca são impressos.

## Bloqueios Meta × banco

Lista cada unidade com seu WABA e `phone_id`, consulta os bloqueados da Meta e
compara com `chatbot.cliente_bloqueado_meta`:

```bash
python -m utilitarios.monitoring.blocked_users blocked-users --show-wa-id
```

Também é possível apenas abrir `blocked_users.py` e clicar em **Run**. Sem
parâmetros, ele executa esse mesmo relatório e mostra os WA IDs completos.

Ao executar `blocked_users.py` diretamente no PyCharm sem parâmetros, esse é o
relatório escolhido por padrão.

O resultado separa:

- sincronizados no banco e na Meta;
- somente na Meta;
- somente no banco, ainda pendentes de confirmação na Meta;
- registros não comparados porque a Meta falhou naquela unidade;
- vínculo local divergente entre unidade e `phone_id`.

Uma falha em uma unidade não transforma sua lista Meta em lista vazia e não
interrompe as outras. A chave da comparação é
`(waba_id, phone_id_unidade, wa_id_cliente)`.

Para conferir os registros Cloud API dos números:

```bash
python -m utilitarios.monitoring.blocked_users phone-registrations
```

Esse segundo relatório percorre todas as WABAs conhecidas pelo banco e detecta
inclusive um mesmo `phone_id` associado a WABAs diferentes. Ele não descobre
uma WABA inteira que ainda não esteja cadastrada localmente.

Os comandos são somente leitura. Código de saída `0` significa sincronizado,
`1` indica divergência e `2` indica falha de coleta.

## Conversas suspeitas

```bash
python -m utilitarios.monitoring.suspicious_conversations \
  --id-unidade 1 --ultimas-horas 24 --formato texto
```

Use `--todas-unidades` para ampliar o escopo. WA IDs e textos sensíveis
permanecem mascarados por padrão.

## Infraestrutura remota

```bash
python -m utilitarios.monitoring.infrastructure
```

Confirma acesso ao PostgreSQL e ao Redis e recusa um destino local.

## Cache

```bash
python -m utilitarios.maintenance.cache_reset --operacional --confirmar
python -m utilitarios.maintenance.cache_reset --bloqueios --confirmar
python -m utilitarios.maintenance.cache_reset --unidades --confirmar
```

Todas as operações validam que o Redis é remoto e exigem `--confirmar`. A
remoção por `SCAN` e `DELETE` é uma manutenção *best effort*, não uma transação
atômica; no deploy, execute-a com webhook e workers parados, como determina o
runbook, para não concorrer com a criação de novas chaves.

Na VM, acrescente `--env-file /etc/chatbot/chatbot.env`. Sem `--env-file`, o
comando usa `utilitarios/local_settings.py`, preservando a execução local pelo
PyCharm.

## Partições do histórico

```bash
python -m utilitarios.maintenance.message_partitions \
  --months-ahead 3 --confirm
```

O comando executa DDL idempotente e retorna erro após rollback se alguma
partição não puder ser criada.

## Sondas do Funil

```bash
python -m utilitarios.integrations.funil_probe catalog
python -m utilitarios.integrations.funil_probe payload
python -m utilitarios.integrations.funil_probe send-test --confirm-real-send
```

Somente o último comando envia uma oportunidade real, e isso exige a flag de
confirmação. Importar o módulo nunca realiza uma requisição externa.

## Ideia futura: rotação automática do PIN

O desenho preliminar para atualizar periodicamente o PIN na Meta e no banco
está registrado em [`PIN_AUTOMATICO_FUTURO.md`](PIN_AUTOMATICO_FUTURO.md). Ele
é apenas uma proposta para uma versão futura; nenhuma automação foi ativada.
