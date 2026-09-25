# Utilitários operacionais

Comandos manuais de monitoramento, diagnóstico e manutenção. Esta pasta não é
importada pelo webhook, pelo monitoramento, pelos workers nem pelo Django
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
├── reports_functions/
│   ├── weekly.py            dashboards e PDFs dos últimos 7 dias
│   └── total.py             dashboards e PDFs desde o primeiro atendimento
├── requirements-monitoramento.txt
├── montar_lead_teste.py
├── verificar_followup.py    diagnóstico somente leitura, sem envio
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
    ├── funil_saj_teste.py
    ├── funil_rio_teste.py
    └── funil_andre_teste.py
```

A maioria das ferramentas usa o bootstrap para execução local no PyCharm;
o [diagnóstico de follow-up](#diagnóstico-de-follow-up) é uma exceção.
Nas ferramentas que usam esse bootstrap, o
`.env` da raiz é lido explicitamente e os ajustes privados de
`utilitarios/local_settings.py`, arquivo ignorado pelo Git, são aplicados por
cima dele. Assim, o SSL do PostgreSQL continua compatível com o Windows sem
misturar variáveis antigas herdadas do processo. Os comandos que aceitam
`--env-file` devem receber `/etc/chatbot/chatbot.env` quando forem executados na
VM; eles nunca dependem do arquivo privado local.

## Regra de pertencimento

Um arquivo pertence a `utilitarios/` quando é um comando iniciado
conscientemente por uma pessoa para diagnóstico, monitoramento, manutenção ou
probe. Nenhum ponto de entrada da aplicação — webhook, monitoramento,
`worker_flow`, `worker_funil`, `worker_followup` ou Django Admin — pode importar esta pasta.

Não pertencem a `utilitarios/`:

- primitivas reutilizadas pelos pontos de entrada, que ficam em `core`;
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

## Monitoramento semanal e total por unidade

Os geradores de monitoramento criam, para cada unidade consultada, um dashboard
HTML de conversas e um relatório PDF de desempenho. O semanal cobre por padrão
os últimos 7 dias. O total cobre, de forma independente para cada unidade, o
intervalo entre a primeira mensagem recebida de cliente e o instante congelado
no começo da execução. Ambos usam exatamente a mesma estrutura visual, regras
de consolidação e métricas. Instale a dependência adicional uma vez:

```bash
python -m pip install -r utilitarios/requirements-monitoramento.txt
```

Depois execute:

```bash
python -m utilitarios.reports_functions.weekly
python -m utilitarios.reports_functions.total
```

Na VM, informe explicitamente o ambiente de produção:

```bash
python -m utilitarios.reports_functions.weekly \
  --env-file /etc/chatbot/chatbot.env
python -m utilitarios.reports_functions.total \
  --env-file /etc/chatbot/chatbot.env
```

As duas visões ficam isoladas dentro da pasta da unidade:

```text
monitoramento/
└── <unidade>/
    ├── semanal/
    │   ├── dashbord/
    │   │   └── conversas_<intervalo>.html
    │   └── relatorios/
    │       └── desempenho_<intervalo>.pdf
    └── total/
        ├── dashbord/
        │   └── conversas_<intervalo>.html
        └── relatorios/
            └── desempenho_<intervalo>.pdf
```

O nome comercial `Santo Antônio de Jesus` é publicado na pasta curta `SAJ`;
os demais nomes de unidade são preservados após a remoção do prefixo `Supera`.

A pasta `/monitoramento/` inteira é ignorada pelo Git. Os arquivos gerados
contêm dados pessoais e devem ser entregues somente aos responsáveis pela
respectiva unidade, sem publicação ou compartilhamento indiscriminado.

O dashboard apresenta como uma sequência as conversas técnicas pertencentes
exatamente ao mesmo par `(id_unidade, id_cliente)`. Conversas de unidades ou
clientes diferentes nunca são unificadas. O utilitário opera em modo somente
leitura: consulta o PostgreSQL e grava apenas os artefatos locais de saída, sem
alterar o banco, o Redis ou enviar mensagens e integrações externas.

O instante final do relatório total é resolvido uma única vez e compartilhado
por todas as unidades da execução. Cada unidade, porém, conserva seu próprio
início. Se uma unidade ainda não tiver mensagem recebida de cliente, ela também
recebe um relatório vazio, sem buscar ou misturar dados de outra unidade.

Flags principais:

- `--dias N`: altera a janela semanal, cujo padrão é 7 dias (somente `weekly`);
- `--ate ISO-8601`: fixa o fim da janela;
- `--id-unidade ID`: limita a uma unidade e pode ser repetida;
- `--saida CAMINHO`: troca a raiz `monitoramento`;
- `--max-mensagens N`: limita o volume consultado;
- `--statement-timeout-ms N`: ajusta o timeout das consultas;
- `--env-file CAMINHO`: escolhe explicitamente o arquivo de ambiente.

O PDF depende do ReportLab; o HTML é autocontido e pode ser aberto offline no
navegador.

### Perfis de atendimento nos PDFs

Os PDFs semanal e total compartilham os mesmos indicadores por perfil:

- dependentes de 4 a 17 anos com BPA ativo, ou de 5 a 17 sem BPA;
- dependentes de 18 a 59 anos e dependentes com 60 anos ou mais;
- titulares de 18 a 59 anos e titulares com 60 anos ou mais.

Cada faixa mostra clientes únicos, conversas, leads enviados ao funil e taxa de
envio. A idade usada é a da pessoa atendida: `cliente.idade` no atendimento
próprio; `dependente.idade` ligado à mesma conversa e cliente no atendimento
para dependente. Dados ausentes, inválidos ou fora dessas faixas ficam em
contadores explícitos de não classificados. Não há dupla contagem aos 18/60
anos. Um cliente pode representar pessoas de perfis diferentes; por isso, não
se somam as linhas para obter o total geral de leads.

O funil usa somente `funil_envios.status = 'sent'`, com `enviado_em` no período,
para clientes que entraram em contato na janela, atribuindo cada envio à sua
própria conversa. Um retry confirmado de conversa sem mensagens na janela
também entra nos perfis, mas não acrescenta mensagens antigas ao HTML. O envio
não equivale a agendamento, venda ou posição atual no CRM.

O snapshot carrega `idade_minima_suporte` como inteiro ou NULL e mostra a política
atual em uma nota. As cinco faixas etárias continuam fixas; suas quantidades e
taxas incluem os envios ao Funil registrados, sem esconder uma faixa inteira
pelo limite da unidade. As idades e configurações são as disponíveis na extração,
sem inventar histórico de alterações. O total reutiliza a implementação semanal.
O novo card de encaminhamentos pertence ao painel web; não é acrescentado ao PDF.
Os quatro CSVs mantêm formatos, telefones e elegibilidade anteriores.

O PDF inclui cobertura de classificação, participação na satisfação,
distribuição das notas, comentários com profissão e relação nominal dos leads.
Os HTMLs de conversas continuam separados e com a mesma finalidade anterior.

## Consultas Meta e alerta sobre alteração do PIN

As consultas abaixo usam `utilitarios/local_settings.py` no Windows. Na VM,
acrescente `--env-file /etc/chatbot/chatbot.env`:

```bash
python -m utilitarios.cache_consulta --limite 200
python -m utilitarios.utlitys --phone-number-id PHONE_ID
```

Os identificadores são mascarados nas consultas por padrão.

> **Não execute `utilitarios.pintregister` pela linha de comando, nem com
> `--help`.** O bloco `__main__` atual substitui os argumentos recebidos por um
> alvo e uma confirmação fixos e realiza imediatamente o POST mutante na Meta.
> Enquanto esse entrypoint não for corrigido em uma tarefa de código própria,
> ele não é uma ferramenta CLI segura. Importar o módulo não realiza o POST.

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

## Diagnóstico de follow-up

`verificar_followup.py` usa o ambiente carregado por `core.config_env`;
não usa `bootstrap.py`, `local_settings.py` nem aceita `--env-file`.
Com as variáveis do banco de teste já configuradas, execute da raiz:

```bash
python -m utilitarios.verificar_followup
```

Na VM, carregue o ambiente dos serviços:

```bash
sudo -u chatbot bash -c 'set -a; source /etc/chatbot/chatbot.env; set +a; cd /opt/chatbot/app; export PYTHONPATH=/opt/chatbot/app PYTHONDONTWRITEBYTECODE=1; /opt/chatbot/venv/bin/python -m utilitarios.verificar_followup'
```

O comando usa uma transação somente leitura. Confere a existência das três
tabelas e o motivo de encerramento da segunda camada, conta stages pendentes,
negativos/maiores que dois, encerramentos do segundo follow-up, marcações do legado e
datas futuras em `last_interaction_at`, e lista até dez candidatas por ID de
conversa, unidade e etapa. Não envia mensagens nem adquire lock de processamento.

`FOLLOWUP_CONSULTA_OK_SEM_ENVIO` confirma a consulta. Stage negativo ou data futura
encerra com `REVISAR_ANOMALIAS_ANTES_DE_ATIVAR`; ausência das tabelas falha com
`SCHEMA_FOLLOWUP_AUSENTE`. Migração da segunda camada pendente falha com
`SCHEMA_SEGUNDO_FOLLOWUP_AUSENTE`; o worker também verifica isso antes de selecionar
candidatas. Stage maior que dois aparece para revisão; o legado ativo mantém sua
recuperação. Amostra vazia é válida e não significa falha do serviço.
`ciclos_aguardando_reacao` inclui somente ativas, inclusive o legado marcado, e não
mede lembretes enviados. `encerradas_no_segundo_followup` conta as inativas em
stage 2 com motivo `followup_sem_resposta`.

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

SAJ:

```bash
python -m utilitarios.integrations.funil_saj_teste catalog
python -m utilitarios.integrations.funil_saj_teste payload
python -m utilitarios.integrations.funil_saj_teste send-test --confirm-real-send
```

Rio Vermelho:

```bash
python -m utilitarios.integrations.funil_rio_teste payload
python -m utilitarios.integrations.funil_rio_teste \
  send-test --confirm-real-send
```

Santo André - Jardim Bela Vista:

```bash
python -m utilitarios.integrations.funil_andre_teste
python -m utilitarios.integrations.funil_andre_teste payload
python -m utilitarios.integrations.funil_andre_teste \
  send-test --confirm-real-send
```

Em cada bloco, somente `send-test` envia uma oportunidade real, e isso exige a
flag de confirmação. Em Santo André, executar o arquivo ou módulo sem argumentos
é o atalho intencional para esse mesmo envio confirmado, permitindo usar
diretamente o botão **Run** do PyCharm. Cada sonda usa um lead fictício
identificado para sua própria unidade. Como Santo André ainda não existe no
banco, seu snapshot usa `id_unidade=-1` apenas para satisfazer o contrato
interno; esse campo não é incluído no payload da ApiCarrossel. Importar os
módulos nunca realiza uma requisição externa.

## Ideia futura: rotação automática do PIN

O desenho preliminar para atualizar periodicamente o PIN na Meta e no banco
está registrado em [`PIN_AUTOMATICO_FUTURO.md`](PIN_AUTOMATICO_FUTURO.md). Ele
é apenas uma proposta para uma versão futura; nenhuma automação foi ativada.
