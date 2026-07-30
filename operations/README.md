# Operations

Comandos manuais de monitoramento, diagnóstico e manutenção. Esta pasta não é
importada pelo webhook, pelo `flow_worker`, pelo `funil_worker` nem pelo Django
Admin.

## Fronteira

```text
serviços de produção -> core/callback/workers
operador humano      -> operations -> primitivas de core
```

Os módulos daqui podem consultar ou manter recursos de produção quando
executados conscientemente. Nenhum deles roda por import e nenhum serviço deve
depender de `operations`.

## Estrutura

```text
operations/
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

As ferramentas foram preparadas para execução local no PyCharm. A configuração
privada fica em `operations/local_settings.py`, arquivo ignorado pelo Git. Ela
usa o mesmo RDS, Redis e token Meta de produção, mas configura o SSL do
PostgreSQL de forma compatível com o Windows. O `.env` da VM não é carregado
como fonte dessas operações.

Os relatórios principais podem ser executados diretamente pelo botão verde do
PyCharm. Os comandos `python -m` continuam disponíveis para filtros avançados.

No Windows, os módulos também podem ser executados diretamente pelo botão
**Run** do PyCharm. O caminho Linux configurado em `DB_SSLROOTCERT` é
automaticamente resolvido para o bundle público do RDS incluído em
`deploy/certificates`, mantendo `verify-full`.

## Bloqueios Meta × banco

Lista cada unidade com seu WABA e `phone_id`, consulta os bloqueados da Meta e
compara com `chatbot.cliente_bloqueado_meta`:

```bash
python -m operations.monitoring.blocked_users blocked-users --show-wa-id
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
python -m operations.monitoring.blocked_users phone-registrations
```

Esse segundo relatório percorre todas as WABAs conhecidas pelo banco e detecta
inclusive um mesmo `phone_id` associado a WABAs diferentes. Ele não descobre
uma WABA inteira que ainda não esteja cadastrada localmente.

Os comandos são somente leitura. Código de saída `0` significa sincronizado,
`1` indica divergência e `2` indica falha de coleta.

## Conversas suspeitas

```bash
python -m operations.monitoring.suspicious_conversations \
  --id-unidade 1 --ultimas-horas 24 --formato texto
```

Use `--todas-unidades` para ampliar o escopo. WA IDs e textos sensíveis
permanecem mascarados por padrão.

## Infraestrutura remota

```bash
python -m operations.monitoring.infrastructure
```

Confirma acesso ao PostgreSQL e ao Redis e recusa um destino local.

## Cache

```bash
python -m operations.maintenance.cache_reset --operacional
python -m operations.maintenance.cache_reset --bloqueios --confirmar
python -m operations.maintenance.cache_reset --unidades
```

Todas as operações validam que o Redis é remoto. A segunda apaga somente os
bloqueios temporários de conversa e exige confirmação explícita.

## Partições do histórico

```bash
python -m operations.maintenance.message_partitions \
  --months-ahead 3 --confirm
```

O comando executa DDL idempotente e retorna erro após rollback se alguma
partição não puder ser criada.

## Sondas do Funil

```bash
python -m operations.integrations.funil_probe catalog
python -m operations.integrations.funil_probe payload
python -m operations.integrations.funil_probe send-test --confirm-real-send
```

Somente o último comando envia uma oportunidade real, e isso exige a flag de
confirmação. Importar o módulo nunca realiza uma requisição externa.
