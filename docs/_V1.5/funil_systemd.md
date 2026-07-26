# V1.5 - Worker do Funil como tarefa systemd

## Status do plano

Plano futuro. Nao aplicar durante o primeiro deploy da V1 sem revisar os
caminhos, o usuario Linux, a versao do `systemd` e a forma definitiva de
carregamento das variaveis de ambiente.

Este documento deve ser atualizado durante o deploy da V1 para trocar os
caminhos provisórios pelos caminhos reais observados na EC2.

## Objetivo

Transformar o `worker_funil` em uma tarefa de execucao unica:

```text
systemd timer dispara
-> Python executa um ciclo do Funil
-> processa ate FUNIL_LIMITE_POR_CICLO
-> fecha cursor e conexao
-> processo termina
-> systemd aguarda uma hora apos o termino
```

O plano remove somente responsabilidades de infraestrutura mantidas atualmente
dentro do Python:

- `while True` do `funil_worker`;
- `while True` do supervisor `iniciar_worker_funil`;
- `time.sleep(FUNIL_INTERVALO_SEGUNDOS)`;
- backoff de conexao mantido dentro do processo;
- constante `FUNIL_INTERVALO_SEGUNDOS`;
- prints usados apenas para separar ciclos no terminal.

## Garantias que nao podem mudar

- Elegibilidade continua definida pelo banco e por `elegivel_funil`.
- `funil_envios` continua sendo materializada antes do processamento.
- O limite de lote continua configuravel.
- Menor `attempt_count` continua tendo prioridade.
- `FOR UPDATE SKIP LOCKED` e o lease continuam ativos.
- Cada lead continua reservado e commitado isoladamente.
- Falha individual continua voltando para `pending` e nao interrompe o lote.
- `lead_no_funil` e `funil_envios = sent` continuam no mesmo commit local.
- A janela entre sucesso externo e commit local continua documentada.
- O `worker_flow`, webhook, Redis e mapa de etapas nao sao alterados.

O `for` que percorre o lote nao e codigo morto e nao deve ser removido.

## Baseline de memoria antes do deploy

Medicao local realizada em 14/07/2026, com um processo Python separado para
cada entrada e apenas os modulos principais importados:

| Processo | Working set observado |
|---|---:|
| webhook Django via WSGI | 71,0 MB |
| `flow_worker` | 46,5 MB |
| `funil_worker` | 32,9 MB |
| soma dos tres processos Python | 150,4 MB |

Esses valores sao um baseline ocioso, nao um limite. O deploy ainda acrescenta
Linux, `systemd`, servidor WSGI, proxy HTTP, Redis, buffers de rede, logs e
picos de requisicoes. Como estimativa inicial, uma EC2 com um worker WSGI deve
ficar em torno de 500 a 900 MB no uso normal da V1. O valor real deve ser
medido depois do deploy.

O timer removeria aproximadamente o custo ocioso do processo do Funil entre os
ciclos, hoje na ordem de 33 MB no teste local. Ele nao reduz o pico durante a
hora em que o lote estiver sendo processado.

Atencao ao dimensionamento: `t3.micro` possui 1 GiB de RAM; `t3.small` possui
2 GiB. Portanto, o timer nao e urgente para uma instancia de 2 GiB, mas pode
dar margem adicional em uma instancia de apenas 1 GiB.

## Estrutura planejada

```text
workers/worker_funil/
├── config.py                    configuracao do ciclo unitario
├── funil_worker.py              ciclo e fronteira transacional
├── iniciar_worker_funil.py      entrada CLI com codigo de saida
├── processamento.py             processamento isolado de um lead
└── exceptions.py

deploy/systemd/
├── chatbot-funil.service        tarefa oneshot
└── chatbot-funil.timer          agenda uma hora apos o termino
```

---

## Passo 1 - `workers/worker_funil/config.py`

Remover `FUNIL_INTERVALO_SEGUNDOS`. O intervalo passa a pertencer
exclusivamente ao arquivo `.timer`.

Codigo completo planejado:

```python
"""Configuracao operacional de cada execucao do worker de Funil."""

from core.config_env import env_bool, env_int


FUNIL_WORKER_ENABLED = env_bool("FUNIL_WORKER_ENABLED", False)
FUNIL_LIMITE_POR_CICLO = env_int("FUNIL_LIMITE_POR_CICLO", 100)
FUNIL_LEASE_SEGUNDOS = env_int("FUNIL_LEASE_SEGUNDOS", 900)
FUNIL_RETRY_LEAD_SEGUNDOS = env_int("FUNIL_RETRY_LEAD_SEGUNDOS", 3600)
FUNIL_HTTP_TIMEOUT = (
    env_int("FUNIL_HTTP_CONNECT_TIMEOUT_SECONDS", 10),
    env_int("FUNIL_HTTP_READ_TIMEOUT_SECONDS", 30),
)


def validar_configuracao_funil():
    valores_positivos = {
        "FUNIL_LIMITE_POR_CICLO": FUNIL_LIMITE_POR_CICLO,
        "FUNIL_LEASE_SEGUNDOS": FUNIL_LEASE_SEGUNDOS,
        "FUNIL_RETRY_LEAD_SEGUNDOS": FUNIL_RETRY_LEAD_SEGUNDOS,
        "FUNIL_HTTP_CONNECT_TIMEOUT_SECONDS": FUNIL_HTTP_TIMEOUT[0],
        "FUNIL_HTTP_READ_TIMEOUT_SECONDS": FUNIL_HTTP_TIMEOUT[1],
    }

    invalidos = [nome for nome, valor in valores_positivos.items() if valor <= 0]
    if invalidos:
        raise RuntimeError(
            "Configuracoes do Funil devem ser positivas: "
            + ", ".join(invalidos)
        )
```

---

## Passo 2 - `workers/worker_funil/funil_worker.py`

`funil_worker()` passa a executar exatamente um ciclo e retornar seu resumo.
Excecoes globais escapam intencionalmente para gerar codigo de saida diferente
de zero e permitir que o `systemd` reinicie a tarefa.

Codigo completo planejado:

```python
"""Executa um unico ciclo de publicacao de leads no Funil."""

import logging

from core.database.connection_aws import get_conn
from core.repositories.funil.envios import (
    reivindicar_proximo_envio,
    sincronizar_envios_elegiveis,
)
from workers.worker_funil.config import (
    FUNIL_LEASE_SEGUNDOS,
    FUNIL_LIMITE_POR_CICLO,
)
from workers.worker_funil.processamento import processar_envio_funil


logger = logging.getLogger("worker.funil")


def funil_worker():
    """Executa uma vez e deixa o agendamento sob responsabilidade do systemd."""
    logger.info("funil_execucao_iniciada | acao=executar_ciclo_unico")
    resumo = executar_ciclo_funil()
    logger.info(
        "funil_execucao_concluida | acao=encerrar_processo "
        "materializados=%s processados=%s enviados=%s falhas=%s",
        resumo["materializados"],
        resumo["processados"],
        resumo["enviados"],
        resumo["falhas"],
    )
    return resumo


def executar_ciclo_funil():
    """Materializa e processa um lote; cada reserva e commitada isoladamente."""
    conn = None
    cursor = None
    resumo = {
        "materializados": 0,
        "processados": 0,
        "enviados": 0,
        "falhas": 0,
    }

    try:
        conn = get_conn(application_name="worker_funil")
        cursor = conn.cursor()

        resumo["materializados"] = sincronizar_envios_elegiveis(
            cursor,
            limite=FUNIL_LIMITE_POR_CICLO,
        )
        conn.commit()

        for _ in range(FUNIL_LIMITE_POR_CICLO):
            envio = reivindicar_proximo_envio(
                cursor,
                lease_segundos=FUNIL_LEASE_SEGUNDOS,
            )
            conn.commit()

            if envio is None:
                break

            resumo["processados"] += 1
            if processar_envio_funil(envio, conn, cursor):
                resumo["enviados"] += 1
            else:
                resumo["falhas"] += 1

        return resumo

    except Exception:
        if conn:
            conn.rollback()
        raise

    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()
```

---

## Passo 3 - `workers/worker_funil/iniciar_worker_funil.py`

O arquivo deixa de ser supervisor. Ele vira a entrada executavel da tarefa e
traduz uma falha global para codigo de saida `1`.

Codigo completo planejado:

```python
"""Entrada de execucao unica do worker de Funil para o systemd."""

import logging

from core.logging_config import setup_logging
from workers.worker_funil.config import (
    FUNIL_WORKER_ENABLED,
    validar_configuracao_funil,
)
from workers.worker_funil.funil_worker import funil_worker


logger = logging.getLogger("worker.funil.entrypoint")


def iniciar_worker_funil():
    """Valida a configuracao e executa no maximo um ciclo."""
    if not FUNIL_WORKER_ENABLED:
        logger.warning(
            "funil_worker_desativado | acao=nao_executar "
            "configuracao=FUNIL_WORKER_ENABLED"
        )
        return None

    validar_configuracao_funil()
    return funil_worker()


def main():
    setup_logging()

    try:
        iniciar_worker_funil()
        return 0
    except KeyboardInterrupt:
        logger.info("funil_execucao_interrompida | acao=encerrar")
        return 130
    except Exception as exc:
        logger.exception(
            "funil_execucao_falhou | acao=informar_systemd erro=%s",
            exc,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
```

---

## Passo 4 - configuração de ambiente

Remover `FUNIL_INTERVALO_SEGUNDOS`. O arquivo de ambiente nao deve controlar
uma responsabilidade que passa a pertencer ao Linux.

Codigo completo planejado:

```dotenv
# Copie este arquivo para .env e preencha somente no ambiente local.
# Nunca registre o arquivo .env no Git.

DJANGO_SECRET_KEY=troque-por-uma-chave-forte
DJANGO_DEBUG=True
DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1
DJANGO_CSRF_TRUSTED_ORIGINS=
DJANGO_SECURE_SSL_REDIRECT=False
DJANGO_SESSION_COOKIE_SECURE=False
DJANGO_CSRF_COOKIE_SECURE=False
DJANGO_SECURE_HSTS_SECONDS=0

DB_HOST=
DB_NAME=
DB_USER=
DB_PASSWORD=
DB_PORT=5432

REDIS_HOST=
REDIS_PORT=6379
REDIS_USERNAME=default
REDIS_PASSWORD=
REDIS_SSL=False

META_ACCESS_TOKEN=
META_WEBHOOK_VERIFY_TOKEN=troque-por-um-token-forte
META_APP_SECRET=
META_WEBHOOK_SIGNATURE_REQUIRED=False
META_APP_ID=
META_PHONE_REGISTRATION_PIN=
META_HTTP_CONNECT_TIMEOUT_SECONDS=30
META_HTTP_READ_TIMEOUT_SECONDS=35

WEBHOOK_MAX_BODY_BYTES=262144

# Tarefa de publicacao de oportunidades acionada pelo systemd timer.
# Mantenha False ate concluir o teste manual da integracao da unidade.
FUNIL_WORKER_ENABLED=False
FUNIL_LIMITE_POR_CICLO=100
FUNIL_LEASE_SEGUNDOS=900
FUNIL_RETRY_LEAD_SEGUNDOS=3600
FUNIL_HTTP_CONNECT_TIMEOUT_SECONDS=10
FUNIL_HTTP_READ_TIMEOUT_SECONDS=30
```

---

## Passo 5 - `deploy/systemd/chatbot-funil.service`

Arquivo novo. Os caminhos abaixo sao provisórios e devem ser comparados com o
deploy real antes da aplicacao:

```text
aplicacao: /opt/chatbot/app
venv:      /opt/chatbot/venv
ambiente:  /etc/chatbot/chatbot.env
usuario:   chatbot
```

O backoff de 5 ate 60 segundos passa para o `systemd`. `RestartSteps` exige
`systemd` 254 ou superior; Ubuntu 24.04 deve ser confirmado com
`systemd --version` durante o deploy.

Codigo completo planejado:

```ini
[Unit]
Description=Chatbot - publicacao de leads no Funil de Vendas
Wants=network-online.target
After=network-online.target
StartLimitIntervalSec=0

[Service]
Type=oneshot
User=chatbot
Group=chatbot
WorkingDirectory=/opt/chatbot/app
EnvironmentFile=/etc/chatbot/chatbot.env
Environment=PYTHONUNBUFFERED=1
Environment=PYTHONDONTWRITEBYTECODE=1
ExecStart=/opt/chatbot/venv/bin/python -m workers.worker_funil.iniciar_worker_funil

# Substitui os dois supervisores Python em caso de falha global.
Restart=on-failure
RestartSec=5s
RestartSteps=11
RestartMaxDelaySec=60s

# Um lote pode realizar ate 100 chamadas HTTP sequenciais.
TimeoutStartSec=infinity

NoNewPrivileges=true
PrivateTmp=true
ProtectHome=true
ProtectSystem=full
UMask=0077

StandardOutput=journal
StandardError=journal
SyslogIdentifier=chatbot-funil
```

Se a EC2 possuir `systemd` anterior a 254, remover estas linhas:

```ini
RestartSteps=11
RestartMaxDelaySec=60s
```

e usar temporariamente:

```ini
RestartSec=30s
```

---

## Passo 6 - `deploy/systemd/chatbot-funil.timer`

Arquivo novo. A proxima execucao ocorre uma hora depois que o servico anterior
terminar. Isso evita sobreposicao e preserva o retry local de 3.600 segundos.

`OnBootSec` executa um ciclo pouco depois de cada inicializacao da EC2.

Codigo completo planejado:

```ini
[Unit]
Description=Chatbot - agendamento horario do worker do Funil

[Timer]
OnBootSec=2min
OnUnitInactiveSec=1h
AccuracySec=1s
Unit=chatbot-funil.service

[Install]
WantedBy=timers.target
```

Nao usar simultaneamente:

- entrada no `crontab`;
- processo antigo do `worker_funil` em terminal;
- segundo timer para a mesma unit;
- chamada do Funil por `main.py`.

---

## Passo 7 - `tests/unit/test_funil_essencial.py`

Os dois testes de loops infinitos ficam obsoletos. Eles devem ser substituidos
por contratos pequenos que comprovem:

- uma chamada produz no maximo um ciclo;
- configuracao desativada nao chama o ciclo;
- falha global retorna codigo diferente de zero ao `systemd`;
- o lote continua processando depois de uma falha individual.

Codigo completo planejado:

```python
import unittest
from unittest.mock import patch

from core.integrations.funil.cliente import (
    enviar_oportunidade,
    montar_url_envio,
)
from core.integrations.funil.exceptions import OportunidadeRejeitadaFunil
from core.integrations.funil.oportunidades import (
    montar_dados_lead_teste,
    montar_payload_oportunidade,
)
from core.repositories.funil.envios import (
    reivindicar_proximo_envio,
    sincronizar_envios_elegiveis,
)
from tests.helpers import FakeConn, FakeCursor
from workers.worker_funil import funil_worker as executor_funil
from workers.worker_funil import iniciar_worker_funil as entrypoint_funil
from workers.worker_funil.exceptions import BancoFalhouAposEnvioFunil
from workers.worker_funil.funil_worker import executar_ciclo_funil
from workers.worker_funil.processamento import processar_envio_funil


class _FakeResponse:
    status_code = 200

    def __init__(self, corpo):
        self.corpo = corpo

    def raise_for_status(self):
        return None

    def json(self):
        return self.corpo


class _FakeSession:
    def __init__(self, corpo):
        self.corpo = corpo
        self.calls = []

    def post(self, url, json, timeout):
        self.calls.append((url, json, timeout))
        return _FakeResponse(self.corpo)


class FunilEssencialTests(unittest.TestCase):
    def test_materializacao_exclui_conversas_ja_enfileiradas_antes_do_limite(self):
        cursor = FakeCursor()

        sincronizar_envios_elegiveis(cursor, limite=100)

        sql, parametros = cursor.calls[0]
        self.assertIn("NOT EXISTS", sql)
        self.assertIn(
            "fe_existente.id_conversa = c.id_conversa",
            sql,
        )
        self.assertEqual(parametros, (100,))

    def test_reivindicacao_prioriza_menor_numero_de_tentativas(self):
        cursor = FakeCursor()

        reivindicar_proximo_envio(cursor, lease_segundos=900)

        sql, parametros = cursor.calls[0]
        ordenacao = sql.split("ORDER BY", 1)[1].split("FOR UPDATE", 1)[0]
        posicao_tentativas = ordenacao.index("fe.attempt_count ASC")
        posicao_tempo = ordenacao.index("CASE")
        posicao_id = ordenacao.index("fe.id_funil_envio ASC")

        self.assertLess(posicao_tentativas, posicao_tempo)
        self.assertLess(posicao_tempo, posicao_id)
        self.assertIn("fe.next_attempt_at", ordenacao)
        self.assertIn("fe.processing_started_at", ordenacao)
        self.assertEqual(parametros, (900,))

    def test_payload_dependente_preenche_contato_e_observacoes(self):
        dados = montar_dados_lead_teste()
        dados["id_conversa"] = 123

        oportunidade = montar_payload_oportunidade(dados)["oportunidades"][0]
        personalizados = {
            item["titulo"]: item["valor"]
            for item in oportunidade["personalizados"]
        }

        self.assertEqual(
            oportunidade["titulo"],
            "Chatbot Lead Supera Santo Antônio de Jesus",
        )
        self.assertEqual(
            oportunidade["empresa"]["nome"],
            "Edcarlos Teste - Não contatar | Enzo Teste | 12",
        )
        self.assertEqual(oportunidade["contato"]["nome"], dados["nome_cliente"])
        self.assertEqual(
            oportunidade["contato"]["telefone1"],
            "5571994111866",
        )
        self.assertEqual(
            oportunidade["contato"]["email"],
            dados["email_cliente"],
        )
        self.assertEqual(personalizados["Origem do lead"], "Meta Chatbot")
        self.assertIn("Nome do dependente: Enzo Teste", personalizados["Observações"])
        self.assertIn("Às vezes: 3", personalizados["Observações"])

    def test_payload_adiciona_nono_digito_ao_telefone_brasileiro(self):
        dados = montar_dados_lead_teste()
        dados["telefone_cliente"] = "557587006911"

        oportunidade = montar_payload_oportunidade(dados)["oportunidades"][0]

        self.assertEqual(
            oportunidade["contato"]["telefone1"],
            "5575987006911",
        )

    def test_payload_internacional_omite_telefone1_e_avisa_nas_observacoes(self):
        dados = montar_dados_lead_teste()
        dados["telefone_cliente"] = "351912345678"

        oportunidade = montar_payload_oportunidade(dados)["oportunidades"][0]
        observacoes = oportunidade["personalizados"][0]["valor"]

        self.assertEqual(oportunidade["contato"]["telefone1"], "")
        self.assertIn("351912345678", observacoes)
        self.assertIn(
            "número internacional fora do padrão brasileiro",
            observacoes,
        )
        self.assertLess(
            observacoes.index("- Idade do dependente: 12"),
            observacoes.index(
                "O cliente possui um número internacional fora do padrão brasileiro"
            ),
        )
        self.assertLess(
            observacoes.index(
                "O cliente possui um número internacional fora do padrão brasileiro"
            ),
            observacoes.index("Resultado do teste de triagem"),
        )

    def test_payload_titular_usa_somente_idade_do_cliente(self):
        dados = montar_dados_lead_teste()
        dados.update(
            {
                "status_dependente": False,
                "idade_cliente": 25,
                "nome_dependente": None,
                "idade_dependente": None,
            }
        )

        oportunidade = montar_payload_oportunidade(dados)["oportunidades"][0]
        observacoes = oportunidade["personalizados"][0]["valor"]

        self.assertEqual(
            oportunidade["titulo"],
            "Chatbot Lead Supera Santo Antônio de Jesus",
        )
        self.assertEqual(
            oportunidade["empresa"]["nome"],
            "Edcarlos Teste - Não contatar | 25",
        )
        self.assertIn("Idade do cliente: 25", observacoes)
        self.assertNotIn("Nome do dependente", observacoes)

    def test_payload_rejeita_triagem_incompleta(self):
        dados = montar_dados_lead_teste()
        dados["triagem_total"] = 5

        with self.assertRaisesRegex(ValueError, "exatamente 6"):
            montar_payload_oportunidade(dados)

    def test_cliente_preserva_widget_e_forca_canal(self):
        url = montar_url_envio(
            "https://leads.example/api/?W=ABC",
            "113340",
        )
        self.assertEqual(
            url,
            "https://leads.example/api/?W=ABC&ForceCodeChannel=113340",
        )

        session = _FakeSession({"response": "success"})
        resultado = enviar_oportunidade(
            link_api_carrossel="https://leads.example/api/?W=ABC",
            codigo_canal_venda="113340",
            payload={"oportunidades": []},
            timeout=(10, 30),
            session=session,
        )
        self.assertEqual(resultado["status_http"], 200)

    def test_cliente_nao_confunde_http_200_com_sucesso_logico(self):
        session = _FakeSession(
            {"response": "failure", "message": "payload inválido"}
        )

        with self.assertRaises(OportunidadeRejeitadaFunil):
            enviar_oportunidade(
                link_api_carrossel="https://leads.example/api/?W=ABC",
                codigo_canal_venda="113340",
                payload={"oportunidades": []},
                timeout=(10, 30),
                session=session,
            )

    @patch("workers.worker_funil.processamento.buscar_dados_lead_funil")
    @patch("workers.worker_funil.processamento.buscar_integracao_funil_por_unidade")
    @patch("workers.worker_funil.processamento.enviar_oportunidade")
    @patch("workers.worker_funil.processamento.marcar_envio_como_concluido")
    def test_falha_local_apos_sucesso_externo_preserva_janela_para_reconciliar(
        self,
        marcar_mock,
        enviar_mock,
        integracao_mock,
        dados_mock,
    ):
        dados_mock.return_value = montar_dados_lead_teste()
        integracao_mock.return_value = {
            "link_api_carrossel": "https://leads.example/api/?W=ABC",
            "codigo_canal_venda": "113340",
            "integracao_ativa": True,
            "widget_ativo": True,
        }
        enviar_mock.return_value = {
            "status_http": 200,
            "resposta": {"response": "success"},
        }
        marcar_mock.side_effect = RuntimeError("banco indisponível")
        conn = FakeConn(FakeCursor())
        envio = {"id_funil_envio": 7, "id_conversa": 123, "attempt_count": 1}

        with self.assertRaises(BancoFalhouAposEnvioFunil):
            processar_envio_funil(envio, conn, conn.cursor_obj)

        self.assertEqual(conn.commits, 1)
        self.assertEqual(conn.rollbacks, 1)

    @patch("workers.worker_funil.funil_worker.get_conn")
    @patch("workers.worker_funil.funil_worker.sincronizar_envios_elegiveis")
    @patch("workers.worker_funil.funil_worker.reivindicar_proximo_envio")
    @patch("workers.worker_funil.funil_worker.processar_envio_funil")
    def test_ciclo_continua_depois_de_falha_individual(
        self,
        processar_mock,
        reivindicar_mock,
        sincronizar_mock,
        get_conn_mock,
    ):
        cursor = FakeCursor()
        cursor.close = lambda: None
        conn = FakeConn(cursor)
        get_conn_mock.return_value = conn
        sincronizar_mock.return_value = 2
        reivindicar_mock.side_effect = [
            {"id_funil_envio": 1, "id_conversa": 101, "attempt_count": 1},
            {"id_funil_envio": 2, "id_conversa": 102, "attempt_count": 1},
            None,
        ]
        processar_mock.side_effect = [False, True]

        resumo = executar_ciclo_funil()

        self.assertEqual(
            resumo,
            {
                "materializados": 2,
                "processados": 2,
                "enviados": 1,
                "falhas": 1,
            },
        )
        self.assertEqual(processar_mock.call_count, 2)

    def test_funil_worker_executa_exatamente_um_ciclo(self):
        resumo = {
            "materializados": 2,
            "processados": 2,
            "enviados": 1,
            "falhas": 1,
        }

        with patch.object(
            executor_funil,
            "executar_ciclo_funil",
            return_value=resumo,
        ) as ciclo_mock:
            resultado = executor_funil.funil_worker()

        self.assertEqual(resultado, resumo)
        ciclo_mock.assert_called_once_with()

    def test_entrypoint_desativado_nao_executa_ciclo(self):
        with (
            patch.object(entrypoint_funil, "FUNIL_WORKER_ENABLED", False),
            patch.object(entrypoint_funil, "funil_worker") as worker_mock,
        ):
            resultado = entrypoint_funil.iniciar_worker_funil()

        self.assertIsNone(resultado)
        worker_mock.assert_not_called()

    def test_falha_global_retorna_codigo_um_para_systemd(self):
        with (
            patch.object(entrypoint_funil, "setup_logging"),
            patch.object(
                entrypoint_funil,
                "iniciar_worker_funil",
                side_effect=RuntimeError("banco indisponível"),
            ) as iniciar_mock,
            patch.object(entrypoint_funil.logger, "exception"),
        ):
            codigo_saida = entrypoint_funil.main()

        self.assertEqual(codigo_saida, 1)
        iniciar_mock.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
```

> O bloco acima preserva os acentos das strings que fazem parte do contrato
> textual da integração e das observações enviadas ao Funil.

---

## Bloqueio documental antes de aplicar

Os documentos abaixo descrevem os dois loops atuais. Como sao extensos e o
deploy real ainda nao foi definido, seus codigos completos devem ser adicionados
a este plano somente quando os caminhos finais da EC2 forem conhecidos:

- `README.md`;
- `workers/README.md`;
- `PADROES_DE_ARQUITETURA.md`;
- `REGRAS_DE_NEGOCIO.md`.

Atualizacoes semanticas obrigatorias:

```text
antes:
Python agenda uma hora e possui dois loops de supervisao

depois:
Python executa um ciclo e termina
systemd reinicia falha global e agenda o proximo ciclo
```

Tambem remover das documentacoes:

- `FUNIL_INTERVALO_SEGUNDOS`;
- referencias a terceiro terminal permanente;
- referencias a `main.py` iniciando o Funil;
- afirmacao de que o backoff global pertence ao Python.

Este passo e uma pendencia deliberada do plano incremental. O plano nao deve ser
aplicado enquanto os quatro documentos nao tiverem suas versoes completas
incorporadas aqui.

---

## Configuracao na EC2

### 1. Confirmar a versao do systemd

```bash
systemd --version
```

Para usar `RestartSteps`, a primeira linha deve indicar versao 254 ou superior.

### 2. Confirmar os caminhos reais

```bash
sudo -u chatbot test -d /opt/chatbot/app
sudo -u chatbot test -x /opt/chatbot/venv/bin/python
sudo -u chatbot test -r /etc/chatbot/chatbot.env
```

Se algum caminho for diferente, atualizar primeiro este plano e os dois arquivos
de unit.

### 3. Validar a entrada Python manualmente

```bash
cd /opt/chatbot/app
sudo -u chatbot \
  /opt/chatbot/venv/bin/python \
  -m workers.worker_funil.iniciar_worker_funil
```

Executar inicialmente com `FUNIL_WORKER_ENABLED=False`. Depois de conferir a
configuracao da integracao, ativar no arquivo protegido da EC2:

```text
FUNIL_WORKER_ENABLED=True
```

### 4. Instalar as units

```bash
sudo install -m 0644 \
  /opt/chatbot/app/deploy_database/systemd/chatbot-funil.service \
  /etc/systemd/system/chatbot-funil.service

sudo install -m 0644 \
  /opt/chatbot/app/deploy_database/systemd/chatbot-funil.timer \
  /etc/systemd/system/chatbot-funil.timer

sudo systemctl daemon-reload
```

### 5. Validar antes de agendar

```bash
sudo systemd-analyze verify \
  /etc/systemd/system/chatbot-funil.service \
  /etc/systemd/system/chatbot-funil.timer

sudo systemctl start chatbot-funil.service
sudo systemctl status chatbot-funil.service --no-pager
sudo journalctl -u chatbot-funil.service -n 100 --no-pager
```

O servico deve terminar como sucesso e nao permanecer com processo Python vivo.

### 6. Habilitar o timer

```bash
sudo systemctl enable --now chatbot-funil.timer
sudo systemctl status chatbot-funil.timer --no-pager
sudo systemctl list-timers chatbot-funil.timer --all
```

### 7. Verificar ausencia de agendamento duplicado

```bash
crontab -l
sudo crontab -l
systemctl list-unit-files | grep chatbot-funil
pgrep -af 'workers.worker_funil'
```

Nao pode existir processo antigo permanente nem entrada de cron para o Funil.

## Comportamento em falhas

```text
falha de um lead
-> processamento.py registra pending + next_attempt_at
-> lote continua
-> servico pode terminar com sucesso
-> proxima execucao ocorre uma hora depois

falha global de banco/processo
-> entrada Python retorna codigo 1
-> systemd reinicia com atraso crescente de 5 ate 60 segundos
-> ao concluir um ciclo com sucesso, o processo termina
-> timer agenda a proxima execucao uma hora depois
```

O timer nao substitui `retry_count`, `next_attempt_at` ou o lease. Ele substitui
somente o relogio externo do processo.

## Verificacao essencial

Executar somente o teste diretamente afetado:

```bash
/opt/chatbot/venv/bin/python -m unittest tests.unit.test_funil_essencial
```

Validacoes de baixo custo:

```bash
/opt/chatbot/venv/bin/python -m compileall \
  workers/worker_funil core/repositories/funil core/integrations/funil

sudo systemd-analyze verify \
  /etc/systemd/system/chatbot-funil.service \
  /etc/systemd/system/chatbot-funil.timer
```

Nao executar a suite completa como requisito desta mudanca isolada.

## Testes operacionais obrigatorios

1. Um disparo manual executa somente um ciclo.
2. O processo Python desaparece depois do ciclo.
3. O timer mostra a proxima execucao aproximadamente uma hora depois.
4. Dois `systemctl start` simultaneos nao processam dois lotes da mesma unit.
5. Falha individual de API nao interrompe os demais leads.
6. Falha global retorna codigo 1 e o systemd reinicia.
7. Um item com `next_attempt_at` futuro nao e enviado antes do prazo.
8. Uma reserva abandonada volta depois do lease.
9. Lead `sent` ou `lead_no_funil = TRUE` nao volta ao lote.
10. Reinicio da EC2 produz um ciclo depois de `OnBootSec=2min`.

## Rollback

```bash
sudo systemctl disable --now chatbot-funil.timer
sudo systemctl stop chatbot-funil.service
sudo rm /etc/systemd/system/chatbot-funil.timer
sudo rm /etc/systemd/system/chatbot-funil.service
sudo systemctl daemon-reload
sudo systemctl reset-failed
```

Depois, restaurar os arquivos Python da versao anterior e voltar a executar o
worker continuo somente se isso for realmente necessario.

## Dados para acrescentar durante o deploy da V1

Atualizar este plano com:

- distribuicao e versao real do Linux;
- versao real do `systemd`;
- usuario e grupo do servico;
- caminho real do projeto e da virtualenv;
- caminho real do arquivo de ambiente;
- duracao observada de um lote vazio e de um lote cheio;
- RSS de memoria durante e depois do ciclo;
- resultado de `systemd-analyze verify`;
- saida de `systemctl list-timers`;
- politica definitiva de logs e retencao do journal;
- procedimento de deploy e rollback realmente utilizado.

## Criterio de conclusao

O plano estara concluido quando:

```text
nenhum loop externo do Funil existir no Python
o ciclo transacional permanecer igual
systemd controlar reinicio e horario
o processo existir apenas durante o lote
nenhum cron ou processo antigo duplicar a execucao
documentacao central refletir exatamente a arquitetura instalada
```
