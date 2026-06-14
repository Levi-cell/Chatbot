# Plano de Implementacao - Suite de Testes Aplicada

## Objetivo

Criar uma suite de testes automatizados para validar as regras criticas do webhook, worker, cache, admin, deploy e sender sem chamar servicos reais.

A suite atual usa apenas `unittest` e `unittest.mock`, porque o projeto nao depende de `pytest` nem `pytest-django`.

## Regra principal dos testes

Os testes unitarios nao devem:

- Usar RDS real.
- Usar Redis real.
- Chamar Meta real.
- Enviar mensagem real.
- Alterar dados reais.

Tudo que depende de banco, Redis ou Meta deve ser simulado com mocks/fakes.

## Como executar

```powershell
C:\Chatbot\venv\.venv\Scripts\python.exe -m unittest discover -s tests -v
C:\Chatbot\venv\.venv\Scripts\python.exe -m compileall -q core callback workers main.py tests
C:\Chatbot\venv\.venv\Scripts\python.exe callback\manage.py check
```

## Passo 1 - Bootstrap de testes

Arquivos criados/alterados:

- `tests/__init__.py`
- `tests/unit/__init__.py`

Responsabilidade:

- Configurar `sys.path` para a raiz do projeto.
- Configurar `sys.path` para a pasta `callback`, permitindo importar o app Django `webhook`.
- Definir `DJANGO_SETTINGS_MODULE=callback.callback.settings` durante os testes.
- Inicializar Django apenas para testes que precisam de admin/models.

Motivo:

- Rodando `python -m unittest discover -s tests -v`, os modulos sao importados como `unit.*`.
- Por isso, a inicializacao precisa estar em `tests/unit/__init__.py`, nao apenas em `tests/__init__.py`.

## Passo 2 - Helpers e payloads

Arquivos criados:

- `tests/helpers.py`
- `tests/payloads.py`

Responsabilidade:

- Criar `FakeCursor`, `FakeConn` e `FakeRequest`.
- Criar payload fake da Meta/WhatsApp.
- Ler `JsonResponse` em testes sem depender de request real.

Motivo:

- Evitar banco real, Redis real, Django request real e chamada externa.

## Passo 3 - Testes do webhook

Arquivo criado:

- `tests/unit/test_webhook_post_flow.py`

Cobertura:

- `Content-Type` invalido retorna `415` antes de validar assinatura.
- Body maior que o limite retorna `413` antes de parsear JSON.
- Assinatura invalida retorna `403`.
- JSON invalido retorna `200 ignored`.
- Flood bloqueia antes de unidade ativa e antes da fila.
- Payload valido passa pelas protecoes e retorna `200 ok`.

Regra protegida:

- O webhook deve rejeitar barato antes de gastar com etapas seguintes.
- Anti-flood continua antes de unidade ativa.
- Mensagem valida so entra na fila depois de passar pelas protecoes.

## Passo 4 - Testes da fila e turno

Arquivos criados:

- `tests/unit/test_populating_fila.py`
- `tests/unit/test_turno_cliente.py`

Cobertura:

- Extracao de dados do payload da Meta.
- Payload sem mensagem e tratado sem quebrar.
- Turno bloqueado nao insere na fila.
- Turno liberado insere na fila.
- Falha de banco na insercao retorna erro controlado.
- Advisory lock usa `phone_id_unidade` e `wa_id_cliente` como chaves.
- Fila aberta sem resposta do bot bloqueia nova mensagem.
- Fila aberta ja respondida pelo bot libera recuperacao.

Regra protegida:

- O sistema trabalha com turno por cliente/unidade.
- A primeira camada fica no webhook/fila.
- A segunda camada continua no worker com `reagendar_se_houver_mensagem_anterior`.

## Passo 5 - Testes do anti-flood

Arquivo criado:

- `tests/unit/test_flood_guard.py`

Cobertura:

- Dados invalidos nao bloqueiam.
- Redis abaixo do limite nao usa banco.
- Redis detectando flood chama bloqueio/registro.
- Redis e banco falhando usam memoria local.
- Falha da Meta impede registro no banco.

Regra protegida:

- Bloqueio na Meta precisa acontecer antes de registrar no banco.
- Se a Meta falhar, o evento e ignorado sem desincronizar banco/cache.
- Banco e Redis podem falhar sem derrubar o webhook.

## Passo 6 - Testes do sender e PyWa

Arquivos criados:

- `tests/unit/test_sender_etapa1.py`
- `tests/unit/test_whatsapp_message_senders.py`
- `tests/unit/test_flow_sender.py`

Cobertura:

- `sender_etapa1` envia `Ola!` com botao `Aperte em mim`.
- Falha da Meta levanta `ErroEnvioMeta`.
- `flow_sender` retorna o contexto do sender da etapa 1.
- Etapa nao implementada levanta erro controlado.
- Idempotencia impede novo envio quando resposta do bot ja existe.
- Montagem do botao PyWa usa `Button(title=..., callback_data=...)`.

Regra protegida:

- Retorno normal do sender significa que a Meta enviou.
- Erro da Meta nao deve ser representado como sucesso parcial.
- O worker so persiste resposta do bot depois de envio confirmado.

## Passo 7 - Testes de persistencia final do worker

Arquivo criado:

- `tests/unit/test_worker_support_finalizacao.py`

Cobertura:

- Persistencia final insere historico do bot e atualiza conversa.
- Resposta ja existente nao insere historico duplicado.
- Contexto sem envio e sem resposta existente falha.
- Reagendamento por mensagem anterior aberta continua funcionando.
- Reparo de cache stale de cliente so age quando a FK prova divergencia.

Regra protegida:

- O worker nao duplica resposta do bot quando reprocessa uma mensagem ja respondida.
- Reparos de cache sao cirurgicos e nao rodam em caso normal.

## Passo 8 - Testes de contrato do worker

Arquivo criado:

- `tests/unit/test_worker_flow_contract.py`

Cobertura:

- `finalizar_mensagem_processada` fica depois de `flow_sender` e `atualizar_banco_com_contexto_final`.
- `ErroEnvioMeta` faz rollback e nao marca mensagem como `sent`.
- `BancoFalhouAposEnvioMeta` fica explicito no log.
- `commit`, `rollback` e `close` continuam no `worker_flow.py`.

Regra protegida:

- `sent` continua sendo a ultima etapa do ciclo.
- Transacoes principais continuam sob controle do arquivo `worker_flow.py`.

## Passo 9 - Testes de repositories

Arquivo criado:

- `tests/unit/test_repositories.py`

Cobertura:

- `atualizar_conversa_resposta_bot` exige etapa.
- Falha quando nenhuma conversa e atualizada.
- Sucesso quando conversa e atualizada.
- `inserir_historico_mensagem_bot` exige `id_hash_msg_bot`.
- Insercao de historico do bot retorna id.

Regra protegida:

- SQL continua isolado em repositories.
- Validacoes objetivas continuam perto da funcao que executa a query.

## Passo 10 - Testes de cache e admin

Arquivo criado:

- `tests/unit/test_cache_and_admin.py`

Cobertura:

- Cache de cliente retorna `None` quando Redis falha.
- Cache de unidade usa fallback no banco quando Redis falha.
- Cache de conversa bloqueada usa fallback no banco quando Redis falha.
- Reset de cache dev limpa prefixos e recria unidades.
- Admin de unidade bloqueia alteracao se Redis falhar depois da validacao Meta.

Regra protegida:

- Unidade e Redis precisam permanecer sincronizados nas operacoes do admin.
- Se Redis falhar no admin, o banco nao deve ser alterado.

## Passo 11 - Testes de contrato do deploy

Arquivo criado:

- `tests/unit/test_deploy_contract.py`

Cobertura:

- Banco novo ja nasce com `last_error` em `fila_mensagens`.
- `alterar_banco` nao existe mais no deploy limpo.
- `setup_database_aws` nao chama migracao historica.
- `respostas_desafios` existe no DDL com `UNIQUE (id_conversa, id_etapa)`.
- `id_historico_mensagem_cliente` em `respostas_desafios` e nullable.

Regra protegida:

- Deploy limpo deve criar o banco ja no formato atual.
- Scripts historicos de alteracao nao devem ser necessarios quando o banco sera recriado do zero.

## Passo 12 - Ajuste necessario no deploy

Arquivo alterado:

- `core/database/deploy/setup_database.py`

Mudanca:

```python
if __name__ == "__main__":
    setup_database_aws()
```

Motivo:

- Importar `setup_database.py` em teste nao pode executar setup real do banco.
- Executar o arquivo diretamente continua funcionando.

## Resultado esperado

Suite atual:

- 49 testes unitarios.
- Sem dependencia externa nova.
- Sem conexao real com Meta, Redis ou RDS.
- Foco em regras de negocio, contratos de fluxo e protecoes contra regressao.

Status validado:

```text
Ran 49 tests
OK
```
