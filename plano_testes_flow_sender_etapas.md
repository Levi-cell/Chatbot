# Plano de testes - primeira etapa simplificada

Status: revisado, ainda nÃ£o aplicado.

Este plano Ã© compatÃ­vel com `plano_flow_sender_etapas.md`.

Ele assume que o plano de produÃ§Ã£o jÃ¡ foi aplicado e que o fluxo novo Ã©:

```text
flow_worker.py
  -> flow_sender.py
      -> primeira_etapa.py
          -> detector_etapas/*
          -> pywa_senders/etapa1.py
```

## Passo 1 - deletar testes do fluxo antigo

Arquivos a deletar:

```text
tests/unit/test_flow_treat_context.py
tests/unit/test_flow_treat_financial.py
tests/unit/test_flow_treat_unsupported_type.py
tests/unit/test_rotear_resposta_cliente.py
tests/unit/test_sender_etapa1.py
tests/unit/test_sender_tratamento.py
tests/unit/test_sender_tratamento_context.py
tests/unit/test_sender_tratamento_financeiro.py
tests/unit/test_valida_resposta_cliente.py
tests/unit/test_whatsapp_message_senders.py
```

Motivo: esses testes apontam para arquivos removidos ou para o desenho antigo
de tratamento global. O novo desenho testa `flow_sender`, `primeira_etapa`,
detectores e `pywa_senders/etapa1.py`.

## Passo 2 - atualizar `test_flow_sender.py`

Arquivo: `tests/unit/test_flow_sender.py`

```python
import unittest
from unittest.mock import patch

import workers.worker_flow.response_flow.flow_sender as flow_sender_module


def contexto_historico_base(
    resposta_bot=None,
    etapa_atual=None,
    etapa_resposta=1,
    retry=1,
):
    return {
        "id_conversa": 10,
        "id_etapa_atual": etapa_atual,
        "id_etapa_cliente": 1,
        "id_etapa_resposta": etapa_resposta,
        "retry_count": retry,
        "texto_cliente_atual": "Ola",
        "tipo_mensagem_atual": "text",
        "mensagem_cliente_atual": {
            "id_mensagem_fila": 20,
            "id_hash_msg": "wamid.cliente",
            "cliente_telefone": "5571999999999",
            "id_phone_unidade": "123456",
        },
        "resposta_bot_para_mensagem_atual": resposta_bot,
    }


class FlowSenderTests(unittest.TestCase):
    def test_idempotente_nao_chama_primeira_etapa_quando_resposta_ja_existe(self):
        def falhar_se_chamar(*_args, **_kwargs):
            raise AssertionError("primeira etapa nao deveria ser chamada")

        with patch.object(
            flow_sender_module,
            "resolve_primeira_etapa",
            falhar_se_chamar,
        ):
            resultado = flow_sender_module.flow_sender(
                contexto_historico_base(
                    resposta_bot={
                        "id_mensagem": 99,
                        "id_hash_msg": "wamid.bot.existente",
                        "id_etapa": 1,
                    }
                )
            )

        self.assertFalse(resultado["enviou"])
        self.assertTrue(resultado["resposta_ja_existia"])
        self.assertEqual(resultado["id_hash_msg_bot"], "wamid.bot.existente")
        self.assertEqual(resultado["id_etapa_resultante"], 1)

    def test_conversa_sem_etapa_vai_para_primeira_etapa(self):
        esperado = {
            "enviou": True,
            "resposta_ja_existia": False,
            "id_hash_msg_bot": "wamid.bot",
            "id_etapa_resultante": 1,
        }

        with patch.object(
            flow_sender_module,
            "resolve_primeira_etapa",
            return_value=esperado,
        ) as resolver:
            resultado = flow_sender_module.flow_sender(
                contexto_historico_base(etapa_atual=None)
            )

        resolver.assert_called_once()
        self.assertEqual(resultado, esperado)

    def test_etapa_um_vai_para_primeira_etapa(self):
        esperado = {
            "enviou": True,
            "resposta_ja_existia": False,
            "id_hash_msg_bot": "wamid.bot",
            "id_etapa_resultante": 1,
        }

        with patch.object(
            flow_sender_module,
            "resolve_primeira_etapa",
            return_value=esperado,
        ) as resolver:
            resultado = flow_sender_module.flow_sender(
                contexto_historico_base(etapa_atual=1, etapa_resposta=2)
            )

        resolver.assert_called_once()
        self.assertEqual(resultado, esperado)

    def test_etapa_nao_implementada_nao_finge_sucesso(self):
        with self.assertRaises(NotImplementedError):
            flow_sender_module.flow_sender(
                contexto_historico_base(etapa_atual=2, etapa_resposta=3)
            )


if __name__ == "__main__":
    unittest.main()
```

## Passo 3 - criar `test_detector_midia.py`

Arquivo: `tests/unit/test_detector_midia.py`

```python
import unittest

from workers.worker_flow.response_flow.etapas.detector_etapas.detector_midia import (
    detecta_midia,
)


class DetectorMidiaTests(unittest.TestCase):
    def test_texto_e_interactive_sao_suportados(self):
        self.assertFalse(detecta_midia("text"))
        self.assertFalse(detecta_midia("interactive"))

    def test_midia_e_tipos_desconhecidos_sao_barrados(self):
        for tipo in ("image", "video", "audio", "document", "sticker", None):
            with self.subTest(tipo=tipo):
                self.assertTrue(detecta_midia(tipo))


if __name__ == "__main__":
    unittest.main()
```

## Passo 4 - criar `test_detector_financeiro.py`

Arquivo: `tests/unit/test_detector_financeiro.py`

```python
import unittest

from workers.worker_flow.response_flow.etapas.detector_etapas.detector_financeiro import (
    detecta_pergunta_financeira,
)


class DetectorFinanceiroTests(unittest.TestCase):
    def test_detecta_perguntas_e_termos_de_valor(self):
        frases = [
            "qual o valor?",
            "qual o preÃ§o da aula?",
            "quanto custa?",
            "tem mensalidade?",
            "qual o investimento?",
            "aceita pix?",
            "posso pagar no cartÃ£o?",
            "tem desconto?",
            "Ã© gratuito?",
            "fica por R$ 100?",
            "tem taxa de matrÃ­cula?",
            "qual o plano?",
            "tem boleto?",
            "Ã© caro?",
        ]

        for frase in frases:
            with self.subTest(frase=frase):
                self.assertTrue(detecta_pergunta_financeira(frase))

    def test_nao_detecta_texto_sem_relacao_com_valor(self):
        frases = [
            "meu nome Ã© Maria",
            "quero conhecer o supera",
            "boa tarde",
            "posso fazer uma aula?",
        ]

        for frase in frases:
            with self.subTest(frase=frase):
                self.assertFalse(detecta_pergunta_financeira(frase))


if __name__ == "__main__":
    unittest.main()
```

## Passo 5 - criar `test_detector_nome.py`

Arquivo: `tests/unit/test_detector_nome.py`

```python
import unittest

from workers.worker_flow.response_flow.etapas.detector_etapas.detector_nome import (
    detecta_nome_invalido,
)


class DetectorNomeTests(unittest.TestCase):
    def test_nomes_validos(self):
        nomes = [
            "Maria",
            "JoÃ£o",
            "Ana Clara",
            "Maria Eduarda",
            "D'Avila",
            "Jean-Luc",
        ]

        for nome in nomes:
            with self.subTest(nome=nome):
                self.assertFalse(detecta_nome_invalido(nome))

    def test_nomes_invalidos(self):
        nomes = [
            "",
            "a",
            "a123",
            "&&3as",
            "pppppppp",
            "xzxzxzxz",
            "puta",
            "bosta",
        ]

        for nome in nomes:
            with self.subTest(nome=nome):
                self.assertTrue(detecta_nome_invalido(nome))


if __name__ == "__main__":
    unittest.main()
```

## Passo 6 - criar `test_pywa_sender_etapa1.py`

Arquivo: `tests/unit/test_pywa_sender_etapa1.py`

```python
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from core.integrations.whatsapp.exceptions import ErroEnvioMeta
from core.integrations.whatsapp.messages.primeira_etapa_messages import (
    montar_mensagem_etapa_1,
    montar_mensagem_financeiro_etapa_1,
    montar_mensagem_financeiro_inicio,
    montar_mensagem_midia_inicio,
)
from core.integrations.whatsapp.pywa_functions.pywa_senders import (
    etapa1 as sender_module,
)


class FakeClienteWa:
    def __init__(self, resposta=None, erro=None):
        self.calls = []
        self.resposta = resposta or SimpleNamespace(id="wamid.bot.1")
        self.erro = erro

    def send_message(self, **kwargs):
        self.calls.append(kwargs)
        if self.erro:
            raise self.erro
        return self.resposta


class PywaSenderEtapa1Tests(unittest.TestCase):
    def test_enviar_primeira_etapa_usa_saudacao(self):
        cliente_wa = FakeClienteWa()

        with patch.object(
            sender_module,
            "conta_wa",
            return_value=cliente_wa,
        ), patch.object(
            sender_module,
            "obter_saudacao_por_horario",
            return_value="Boa tarde",
        ):
            resultado = sender_module.enviar_primeira_etapa(
                "5571999999999",
                "123456",
            )

        mensagem_esperada = montar_mensagem_etapa_1("Boa tarde")

        self.assertEqual(cliente_wa.calls[0]["to"], "5571999999999")
        self.assertEqual(cliente_wa.calls[0]["text"], mensagem_esperada)
        self.assertTrue(resultado["enviou"])
        self.assertFalse(resultado["resposta_ja_existia"])
        self.assertEqual(resultado["mensagem_bot"], mensagem_esperada)
        self.assertEqual(resultado["id_hash_msg_bot"], "wamid.bot.1")
        self.assertEqual(resultado["id_etapa_resultante"], 1)
        self.assertNotIn("tratamento", resultado)

    def test_midia_inicio_usa_saudacao_e_marca_tratamento(self):
        cliente_wa = FakeClienteWa()

        with patch.object(
            sender_module,
            "conta_wa",
            return_value=cliente_wa,
        ), patch.object(
            sender_module,
            "obter_saudacao_por_horario",
            return_value="Bom dia",
        ):
            resultado = sender_module.enviar_primeira_etapa_midia_inicio(
                "5571999999999",
                "123456",
            )

        mensagem_esperada = montar_mensagem_midia_inicio("Bom dia")

        self.assertEqual(cliente_wa.calls[0]["text"], mensagem_esperada)
        self.assertTrue(resultado["tratamento"])
        self.assertEqual(
            resultado["tipo_tratamento"],
            sender_module.TIPO_TRATAMENTO_MIDIA,
        )
        self.assertEqual(resultado["id_etapa_resultante"], 1)

    def test_financeiro_inicio_usa_saudacao_e_marca_tratamento(self):
        cliente_wa = FakeClienteWa()

        with patch.object(
            sender_module,
            "conta_wa",
            return_value=cliente_wa,
        ), patch.object(
            sender_module,
            "obter_saudacao_por_horario",
            return_value="Boa noite",
        ):
            resultado = sender_module.enviar_primeira_etapa_financeiro_inicio(
                "5571999999999",
                "123456",
            )

        mensagem_esperada = montar_mensagem_financeiro_inicio("Boa noite")

        self.assertEqual(cliente_wa.calls[0]["text"], mensagem_esperada)
        self.assertTrue(resultado["tratamento"])
        self.assertEqual(
            resultado["tipo_tratamento"],
            sender_module.TIPO_TRATAMENTO_FINANCEIRO,
        )
        self.assertEqual(resultado["id_etapa_resultante"], 1)

    def test_financeiro_etapa_um_nao_usa_saudacao(self):
        cliente_wa = FakeClienteWa()

        with patch.object(
            sender_module,
            "conta_wa",
            return_value=cliente_wa,
        ):
            resultado = sender_module.enviar_primeira_etapa_financeiro(
                "5571999999999",
                "123456",
            )

        self.assertEqual(
            cliente_wa.calls[0]["text"],
            montar_mensagem_financeiro_etapa_1(),
        )
        self.assertTrue(resultado["tratamento"])
        self.assertEqual(resultado["id_etapa_resultante"], 1)

    def test_meta_falhou_levanta_exception_controlada(self):
        cliente_wa = FakeClienteWa(erro=RuntimeError("meta indisponivel"))

        with patch.object(
            sender_module,
            "conta_wa",
            return_value=cliente_wa,
        ):
            with self.assertRaises(ErroEnvioMeta) as ctx:
                sender_module.enviar_primeira_etapa(
                    "5571999999999",
                    "123456",
                )

        self.assertEqual(ctx.exception.id_etapa, 1)
        self.assertEqual(ctx.exception.cliente_telefone, "5571999999999")
        self.assertEqual(ctx.exception.phone_id_unidade, "123456")


if __name__ == "__main__":
    unittest.main()
```

## Passo 7 - criar `test_primeira_etapa.py`

Arquivo: `tests/unit/test_primeira_etapa.py`

```python
import unittest
from unittest.mock import patch

from workers.worker_flow.response_flow.etapas import (
    primeira_etapa as etapa_module,
)


def contexto_historico(
    *,
    etapa_atual=None,
    etapa_resposta=1,
    tipo_mensagem="text",
    texto="Ola",
):
    return {
        "id_conversa": 10,
        "id_etapa_atual": etapa_atual,
        "id_etapa_cliente": 1,
        "id_etapa_resposta": etapa_resposta,
        "tipo_mensagem_atual": tipo_mensagem,
        "texto_cliente_atual": texto,
        "mensagem_cliente_atual": {
            "id_mensagem_fila": 20,
            "id_hash_msg": "wamid.cliente",
            "cliente_telefone": "5571999999999",
            "id_phone_unidade": "123456",
        },
    }


def retorno(nome):
    return {
        "nome": nome,
        "enviou": True,
        "resposta_ja_existia": False,
        "id_hash_msg_bot": f"wamid.{nome}",
        "id_etapa_resultante": 1,
    }


class PrimeiraEtapaTests(unittest.TestCase):
    def test_conversa_nova_com_midia_usa_tratamento_de_inicio(self):
        with patch.object(
            etapa_module,
            "enviar_primeira_etapa_midia_inicio",
            return_value=retorno("midia_inicio"),
        ) as sender:
            resultado = etapa_module.resolve_primeira_etapa(
                contexto_historico(tipo_mensagem="image")
            )

        sender.assert_called_once_with("5571999999999", "123456")
        self.assertEqual(resultado["nome"], "midia_inicio")

    def test_conversa_nova_com_financeiro_usa_tratamento_de_inicio(self):
        with patch.object(
            etapa_module,
            "enviar_primeira_etapa_financeiro_inicio",
            return_value=retorno("financeiro_inicio"),
        ) as sender:
            resultado = etapa_module.resolve_primeira_etapa(
                contexto_historico(texto="qual o valor?")
            )

        sender.assert_called_once_with("5571999999999", "123456")
        self.assertEqual(resultado["nome"], "financeiro_inicio")

    def test_conversa_nova_com_texto_normal_envia_primeira_etapa(self):
        with patch.object(
            etapa_module,
            "enviar_primeira_etapa",
            return_value=retorno("etapa_1"),
        ) as sender:
            resultado = etapa_module.resolve_primeira_etapa(
                contexto_historico(texto="ola")
            )

        sender.assert_called_once_with("5571999999999", "123456")
        self.assertEqual(resultado["nome"], "etapa_1")

    def test_etapa_um_com_midia_usa_tratamento_da_etapa(self):
        with patch.object(
            etapa_module,
            "enviar_primeira_etapa_midia",
            return_value=retorno("midia_etapa_1"),
        ) as sender:
            resultado = etapa_module.resolve_primeira_etapa(
                contexto_historico(etapa_atual=1, etapa_resposta=2, tipo_mensagem="video")
            )

        sender.assert_called_once_with("5571999999999", "123456")
        self.assertEqual(resultado["nome"], "midia_etapa_1")

    def test_etapa_um_com_financeiro_usa_tratamento_da_etapa(self):
        with patch.object(
            etapa_module,
            "enviar_primeira_etapa_financeiro",
            return_value=retorno("financeiro_etapa_1"),
        ) as sender:
            resultado = etapa_module.resolve_primeira_etapa(
                contexto_historico(etapa_atual=1, etapa_resposta=2, texto="quanto custa?")
            )

        sender.assert_called_once_with("5571999999999", "123456")
        self.assertEqual(resultado["nome"], "financeiro_etapa_1")

    def test_etapa_um_com_nome_invalido_usa_tratamento_de_contexto(self):
        with patch.object(
            etapa_module,
            "enviar_primeira_etapa_contexto_nome_invalido",
            return_value=retorno("nome_invalido"),
        ) as sender:
            resultado = etapa_module.resolve_primeira_etapa(
                contexto_historico(etapa_atual=1, etapa_resposta=2, texto="pppppp")
            )

        sender.assert_called_once_with("5571999999999", "123456")
        self.assertEqual(resultado["nome"], "nome_invalido")

    def test_etapa_um_com_nome_valido_tenta_avancar_para_etapa_pendente(self):
        with self.assertRaises(NotImplementedError):
            etapa_module.resolve_primeira_etapa(
                contexto_historico(etapa_atual=1, etapa_resposta=2, texto="Maria")
            )


if __name__ == "__main__":
    unittest.main()
```

## Passo 8 - atualizar `test_worker_flow_contract.py`

Arquivo: `tests/unit/test_worker_flow_contract.py`

```python
import inspect
import unittest

from workers.worker_flow.response_flow import flow_worker


class WorkerFlowContractTests(unittest.TestCase):
    def test_sent_fica_depois_do_flow_sender_e_da_persistencia_final(self):
        source = inspect.getsource(flow_worker.worker_flow)

        pos_valida_historico = source.index("contexto_historico = valida_historico")
        pos_flow_sender = source.index("contexto_envio = flow_sender")
        pos_atualizar_banco = source.index("contexto_final = atualizar_banco_com_contexto_final")
        pos_finalizar = source.index("finalizar_mensagem_processada")

        self.assertLess(pos_valida_historico, pos_flow_sender)
        self.assertLess(pos_flow_sender, pos_atualizar_banco)
        self.assertLess(pos_atualizar_banco, pos_finalizar)

    def test_erro_meta_nao_marca_sent(self):
        source = inspect.getsource(flow_worker.worker_flow)

        pos_except_meta = source.index("except ErroEnvioMeta as erro:")
        pos_except_banco_meta = source.index("except BancoFalhouAposEnvioMeta as erro:")
        bloco_meta = source[pos_except_meta:pos_except_banco_meta]

        self.assertIn("conn_ciclo.rollback()", bloco_meta)
        self.assertIn("handle_erro_generico", bloco_meta)
        self.assertNotIn("finalizar_mensagem_processada", bloco_meta)

    def test_banco_falhou_apos_meta_fica_explicito_no_log(self):
        source = inspect.getsource(flow_worker.worker_flow)

        self.assertIn("BancoFalhouAposEnvioMeta", source)
        self.assertIn("banco_falhou_apos_envio_meta", source)
        self.assertIn("risco=resposta_duplicada", source)

    def test_commit_rollback_close_continuam_no_worker(self):
        source = inspect.getsource(flow_worker.worker_flow)

        self.assertIn("conn_ciclo.commit()", source)
        self.assertIn("conn_ciclo.rollback()", source)
        self.assertIn("conn_ciclo.close()", source)


if __name__ == "__main__":
    unittest.main()
```

## Passo 9 - atualizar `test_worker_flow_runtime.py`

Arquivo: `tests/unit/test_worker_flow_runtime.py`

```python
import unittest
from contextlib import ExitStack
from datetime import datetime
from unittest.mock import patch

from tests.helpers import FakeConn, FakeCursor
from workers.worker_flow.response_flow import flow_worker


class PararWorker(BaseException):
    pass


def registro_fila():
    return (
        7,
        "5571999999999",
        "Ola",
        "text",
        "123456",
        "5571000000000",
        datetime(2026, 6, 18, 10, 0),
        "wamid.cliente.7",
        1,
    )


def contexto_banco():
    return {
        "id_unidade": 2,
        "id_cliente": 6,
        "cliente_telefone": "5571999999999",
        "id_phone_unidade": "123456",
        "cliente_inserido": False,
        "cliente_cache_pendente": False,
        "conversa": {
            "id_conversa": 10,
            "estado": "ativa",
        },
    }


def contexto_historico():
    return {
        "id_conversa": 10,
        "id_etapa_atual": None,
        "id_etapa_cliente": 1,
        "id_etapa_resposta": 1,
        "mensagem_cliente_inserida": True,
        "mensagem_cliente_atual": {
            "id_mensagem_fila": 7,
            "id_hash_msg": "wamid.cliente.7",
            "cliente_telefone": "5571999999999",
            "id_phone_unidade": "123456",
        },
        "resposta_bot_para_mensagem_atual": None,
        "retry_count": 1,
    }


def contexto_envio():
    return {
        "enviou": True,
        "resposta_ja_existia": False,
        "id_hash_msg_bot": "wamid.bot.7",
        "id_etapa_resultante": 1,
        "tipo_mensagem": "text",
    }


def contexto_final():
    return {
        "id_etapa_resultante": 1,
        "resposta_ja_existia": False,
        "id_hash_msg_bot": "wamid.bot.7",
    }


class WorkerFlowRuntimeTests(unittest.TestCase):
    def test_fila_vazia_fecha_conexao_antes_de_aguardar(self):
        conn = FakeConn(FakeCursor())

        with ExitStack() as stack:
            stack.enter_context(patch("builtins.print"))
            stack.enter_context(patch.object(
                flow_worker,
                "get_conn",
                side_effect=[conn, PararWorker()],
            ))
            stack.enter_context(patch.object(
                flow_worker,
                "pegar_mensagens_da_fila",
                return_value=None,
            ))
            close = stack.enter_context(patch.object(
                conn,
                "close",
                wraps=conn.close,
            ))

            def verificar_conexao_fechada():
                self.assertTrue(conn.closed)

            stack.enter_context(patch.object(
                flow_worker,
                "aguardar_fila_vazia",
                side_effect=verificar_conexao_fechada,
            ))

            with self.assertRaises(PararWorker):
                flow_worker.worker_flow()

        close.assert_called_once_with()
        self.assertEqual(conn.commits, 1)
        self.assertEqual(conn.rollbacks, 0)

    def _patch_fluxo_base(self, stack, conn, eventos):
        stack.enter_context(patch("builtins.print"))
        stack.enter_context(patch.object(
            flow_worker,
            "get_conn",
            side_effect=[conn, PararWorker()],
        ))
        stack.enter_context(patch.object(
            flow_worker,
            "pegar_mensagens_da_fila",
            return_value=registro_fila(),
        ))
        stack.enter_context(patch.object(
            flow_worker,
            "validar_banco_mensagem",
            side_effect=lambda *_args: eventos.append("validar_banco") or contexto_banco(),
        ))
        stack.enter_context(patch.object(
            flow_worker,
            "vincular_mensagem_fila_a_conversa",
            side_effect=lambda *_args: eventos.append("vincular_conversa") or 1,
        ))
        stack.enter_context(patch.object(
            flow_worker,
            "confirmar_cache_cliente_se_pendente",
            return_value=False,
        ))
        stack.enter_context(patch.object(
            flow_worker,
            "tentar_lock_conversa",
            side_effect=lambda *_args: eventos.append("adquirir_lock") or (True, 4),
        ))
        stack.enter_context(patch.object(
            flow_worker,
            "reagendar_se_houver_mensagem_anterior",
            return_value=False,
        ))
        stack.enter_context(patch.object(
            flow_worker,
            "valida_historico",
            side_effect=lambda *_args: eventos.append("persistir_cliente") or contexto_historico(),
        ))
        stack.enter_context(patch.object(
            flow_worker,
            "flow_sender",
            side_effect=lambda *_args: eventos.append("enviar_meta") or contexto_envio(),
        ))
        stack.enter_context(patch.object(
            flow_worker,
            "liberar_lock_conversa_se_necessario",
            side_effect=lambda *_args: eventos.append("liberar_lock") or True,
        ))
        stack.enter_context(patch.object(
            flow_worker,
            "handle_erro_generico",
        ))

    def test_ciclo_normal_persiste_resposta_antes_de_marcar_sent(self):
        conn = FakeConn(FakeCursor())
        eventos = []

        with ExitStack() as stack:
            self._patch_fluxo_base(stack, conn, eventos)
            stack.enter_context(patch.object(
                flow_worker,
                "atualizar_banco_com_contexto_final",
                side_effect=lambda *_args: eventos.append("persistir_bot") or contexto_final(),
            ))
            finalizar = stack.enter_context(patch.object(
                flow_worker,
                "finalizar_mensagem_processada",
                side_effect=lambda *_args: eventos.append("marcar_sent"),
            ))

            with self.assertRaises(PararWorker):
                flow_worker.worker_flow()

        self.assertEqual(
            eventos,
            [
                "validar_banco",
                "vincular_conversa",
                "adquirir_lock",
                "persistir_cliente",
                "enviar_meta",
                "persistir_bot",
                "marcar_sent",
                "liberar_lock",
            ],
        )
        finalizar.assert_called_once()
        self.assertEqual(conn.commits, 7)
        self.assertEqual(conn.rollbacks, 0)
        self.assertTrue(conn.closed)

    def test_falha_do_banco_apos_meta_reagenda_sem_marcar_sent(self):
        conn = FakeConn(FakeCursor())
        eventos = []

        with ExitStack() as stack:
            self._patch_fluxo_base(stack, conn, eventos)
            stack.enter_context(patch.object(
                flow_worker,
                "atualizar_banco_com_contexto_final",
                side_effect=RuntimeError("banco caiu apos envio"),
            ))
            finalizar = stack.enter_context(patch.object(
                flow_worker,
                "finalizar_mensagem_processada",
                side_effect=lambda *_args: eventos.append("marcar_sent"),
            ))
            tratar_erro = stack.enter_context(patch.object(
                flow_worker,
                "handle_erro_generico",
            ))

            with self.assertRaises(PararWorker):
                flow_worker.worker_flow()

        finalizar.assert_not_called()
        tratar_erro.assert_called_once()
        self.assertNotIn("marcar_sent", eventos)
        self.assertEqual(conn.rollbacks, 1)
        self.assertEqual(conn.commits, 6)
        self.assertTrue(conn.closed)


if __name__ == "__main__":
    unittest.main()
```

## Passo 10 - atualizar `test_fluxo_turno_abc.py`

Arquivo: `tests/unit/test_fluxo_turno_abc.py`

```python
import unittest
from datetime import datetime, timedelta
from unittest.mock import patch

from core.repositories import turno_cliente
from workers.worker_flow import suport_functions as support
from workers.worker_flow.response_flow import flow_sender


CLIENTE = "5571999999999"
PHONE_ID = "123456"
ID_CONVERSA = 10


class EstadoTurnoABC:
    def __init__(self):
        self.filas = {}
        self.respostas_bot = set()
        self.locks_turno = 0

    def adicionar_fila(self, id_mensagem, id_hash, recebida_em, status="pending"):
        self.filas[id_mensagem] = {
            "id_mensagem": id_mensagem,
            "id_conversa": ID_CONVERSA,
            "id_hash_msg": id_hash,
            "received_data_hora": recebida_em,
            "status": status,
        }

    def registrar_resposta_bot(self, id_mensagem):
        fila = self.filas[id_mensagem]
        self.respostas_bot.add((
            fila["id_conversa"],
            fila["id_mensagem"],
            fila["id_hash_msg"],
        ))

    def possui_resposta_bot(self, fila):
        return (
            fila["id_conversa"],
            fila["id_mensagem"],
            fila["id_hash_msg"],
        ) in self.respostas_bot

    def avaliar_filas_abertas(self, *_args):
        abertas = sorted(
            (
                fila
                for fila in self.filas.values()
                if fila["status"] in {"pending", "processing"}
            ),
            key=lambda fila: (
                fila["received_data_hora"],
                fila["id_mensagem"],
            ),
        )
        sem_resposta = [
            fila for fila in abertas if not self.possui_resposta_bot(fila)
        ]

        return {
            "existe_fila_aberta": bool(abertas),
            "todas_abertas_respondidas": bool(abertas) and not sem_resposta,
            "total_abertas": len(abertas),
            "id_mensagem_bloqueadora": (
                sem_resposta[0]["id_mensagem"] if sem_resposta else None
            ),
        }

    def adquirir_lock_turno(self, *_args):
        self.locks_turno += 1

    def existe_anterior(self, id_conversa, id_mensagem, recebida_em, _cursor):
        return any(
            fila["id_conversa"] == id_conversa
            and fila["id_mensagem"] != id_mensagem
            and fila["status"] in {"pending", "processing"}
            and (
                fila["received_data_hora"],
                fila["id_mensagem"],
            ) < (recebida_em, id_mensagem)
            for fila in self.filas.values()
        )

    def reagendar_sem_erro(self, id_mensagem, _cursor, delay_seconds=30):
        self.filas[id_mensagem]["status"] = "pending"
        self.filas[id_mensagem]["delay_seconds"] = delay_seconds
        return 1

    def marcar_sent(self, id_mensagem, _cursor):
        self.filas[id_mensagem]["status"] = "sent"


def mensagem_worker(estado, id_mensagem):
    fila = estado.filas[id_mensagem]
    return {
        "id_mensagem": id_mensagem,
        "cliente_telefone": CLIENTE,
        "id_phone_unidade": PHONE_ID,
        "data_recebimento": fila["received_data_hora"],
    }


def contexto_banco():
    return {
        "id_unidade": 2,
        "conversa": {
            "id_conversa": ID_CONVERSA,
            "estado": "ativa",
        },
    }


def contexto_historico(estado, id_mensagem, resposta_bot=None, retry=1):
    fila = estado.filas[id_mensagem]
    return {
        "id_conversa": ID_CONVERSA,
        "id_etapa_atual": None,
        "id_etapa_cliente": 1,
        "id_etapa_resposta": 1,
        "retry_count": retry,
        "texto_cliente_atual": "Ola",
        "tipo_mensagem_atual": "text",
        "mensagem_cliente_atual": {
            "id_mensagem_fila": id_mensagem,
            "id_hash_msg": fila["id_hash_msg"],
            "cliente_telefone": CLIENTE,
            "id_phone_unidade": PHONE_ID,
        },
        "resposta_bot_para_mensagem_atual": resposta_bot,
    }


class FluxoTurnoABCTests(unittest.TestCase):
    def test_a_respondida_libera_b_b_sem_resposta_bloqueia_c(self):
        estado = EstadoTurnoABC()
        inicio = datetime(2026, 6, 18, 10, 0)

        estado.adicionar_fila(1, "wamid.A", inicio, status="processing")
        estado.registrar_resposta_bot(1)

        with patch.object(
            turno_cliente,
            "adquirir_lock_turno_cliente",
            side_effect=estado.adquirir_lock_turno,
        ), patch.object(
            turno_cliente,
            "avaliar_filas_abertas_turno",
            side_effect=estado.avaliar_filas_abertas,
        ):
            decisao_b = turno_cliente.avaliar_turno_cliente_para_fila(
                cursor=object(),
                cliente_telefone=CLIENTE,
                id_phone_unidade=PHONE_ID,
                usar_lock=True,
            )

            self.assertTrue(decisao_b["pode_enfileirar"])
            self.assertEqual(decisao_b["motivo"], "fila_aberta_respondida_bot")

            estado.adicionar_fila(
                2,
                "wamid.B",
                inicio + timedelta(seconds=1),
                status="pending",
            )

            decisao_c_antes_da_resposta_b = (
                turno_cliente.avaliar_turno_cliente_para_fila(
                    cursor=object(),
                    cliente_telefone=CLIENTE,
                    id_phone_unidade=PHONE_ID,
                    usar_lock=True,
                )
            )

            self.assertFalse(
                decisao_c_antes_da_resposta_b["pode_enfileirar"]
            )
            self.assertEqual(
                decisao_c_antes_da_resposta_b["motivo"],
                "fila_aberta_sem_resposta_bot",
            )
            self.assertNotIn(3, estado.filas)

            estado.filas[2]["status"] = "processing"

            with patch.object(
                support,
                "existe_mensagem_anterior_aberta_conversa",
                side_effect=estado.existe_anterior,
            ), patch.object(
                support,
                "reagendar_mensagem_sem_erro",
                side_effect=estado.reagendar_sem_erro,
            ):
                b_reagendada = support.reagendar_se_houver_mensagem_anterior(
                    mensagem_worker(estado, 2),
                    contexto_banco(),
                    lock_version=4,
                    cursor=object(),
                )

            self.assertTrue(b_reagendada)
            self.assertEqual(estado.filas[2]["status"], "pending")
            self.assertEqual(estado.filas[2]["delay_seconds"], 30)

            resposta_a = {
                "id_mensagem": 101,
                "id_hash_msg": "wamid.bot.A",
                "id_etapa": 1,
            }

            with patch.object(
                flow_sender,
                "resolve_primeira_etapa",
                side_effect=AssertionError("A nao pode ser enviada novamente"),
            ):
                resultado_retry_a = flow_sender.flow_sender(
                    contexto_historico(
                        estado,
                        1,
                        resposta_bot=resposta_a,
                        retry=2,
                    )
                )

            self.assertFalse(resultado_retry_a["enviou"])
            self.assertTrue(resultado_retry_a["resposta_ja_existia"])

            with patch.object(
                support,
                "marcar_mensagem_como_enviada",
                side_effect=estado.marcar_sent,
            ):
                support.finalizar_mensagem_processada(
                    mensagem_worker(estado, 1),
                    contexto_banco(),
                    lock_version=4,
                    cursor=object(),
                )

            self.assertEqual(estado.filas[1]["status"], "sent")

            with patch.object(
                support,
                "existe_mensagem_anterior_aberta_conversa",
                side_effect=estado.existe_anterior,
            ):
                b_ainda_tem_anterior = (
                    support.reagendar_se_houver_mensagem_anterior(
                        mensagem_worker(estado, 2),
                        contexto_banco(),
                        lock_version=5,
                        cursor=object(),
                    )
                )

            self.assertFalse(b_ainda_tem_anterior)
            estado.filas[2]["status"] = "processing"

            with patch.object(
                flow_sender,
                "resolve_primeira_etapa",
                return_value={
                    "enviou": True,
                    "resposta_ja_existia": False,
                    "mensagem_bot": "Ola! Boa tarde.",
                    "id_hash_msg_bot": "wamid.bot.B",
                    "id_etapa_resultante": 1,
                    "tipo_mensagem": "text",
                    "canal": "meta_whatsapp",
                },
            ):
                resultado_b = flow_sender.flow_sender(
                    contexto_historico(estado, 2)
                )

            self.assertTrue(resultado_b["enviou"])
            estado.registrar_resposta_bot(2)

            decisao_c_apos_resposta_b = (
                turno_cliente.avaliar_turno_cliente_para_fila(
                    cursor=object(),
                    cliente_telefone=CLIENTE,
                    id_phone_unidade=PHONE_ID,
                    usar_lock=True,
                )
            )

            self.assertTrue(decisao_c_apos_resposta_b["pode_enfileirar"])
            self.assertEqual(estado.filas[2]["status"], "processing")

            estado.adicionar_fila(
                3,
                "wamid.C",
                inicio + timedelta(seconds=2),
                status="pending",
            )

            decisao_d = turno_cliente.avaliar_turno_cliente_para_fila(
                cursor=object(),
                cliente_telefone=CLIENTE,
                id_phone_unidade=PHONE_ID,
                usar_lock=True,
            )

            self.assertFalse(decisao_d["pode_enfileirar"])
            self.assertEqual(decisao_d["motivo"], "fila_aberta_sem_resposta_bot")
            self.assertNotIn(4, estado.filas)

        self.assertEqual(estado.locks_turno, 4)


if __name__ == "__main__":
    unittest.main()
```

## Passo 11 - atualizar `test_whatsapp_structure.py`

Arquivo: `tests/unit/test_whatsapp_structure.py`

```python
import ast
import unittest
from pathlib import Path

from core.integrations.whatsapp.messages.primeira_etapa_messages import (
    MENSAGEM_CONTEXTO_NOME_INVALIDO_ETAPA_1,
    MENSAGEM_ETAPA_1,
    MENSAGEM_FINANCEIRO_ETAPA_1,
    MENSAGEM_FINANCEIRO_INICIO,
    MENSAGEM_MIDIA_ETAPA_1,
    MENSAGEM_MIDIA_INICIO,
)


RAIZ_PROJETO = Path(__file__).resolve().parents[2]
RAIZ_WHATSAPP = RAIZ_PROJETO / "core" / "integrations" / "whatsapp"
RAIZ_PYWA = RAIZ_WHATSAPP / "pywa_functions"

RAIZES_PRODUCAO = (
    RAIZ_PROJETO / "core",
    RAIZ_PROJETO / "workers",
    RAIZ_PROJETO / "callback",
)

METODOS_PYWA = {
    "send_message",
    "send_image",
    "send_video",
    "send_document",
    "block_users",
    "unblock_users",
    "get_blocked_users",
}

CONTEUDOS_WHATSAPP = (
    MENSAGEM_ETAPA_1,
    MENSAGEM_MIDIA_INICIO,
    MENSAGEM_MIDIA_ETAPA_1,
    MENSAGEM_FINANCEIRO_INICIO,
    MENSAGEM_FINANCEIRO_ETAPA_1,
    MENSAGEM_CONTEXTO_NOME_INVALIDO_ETAPA_1,
)


def arquivos_python_producao():
    for raiz in RAIZES_PRODUCAO:
        yield from raiz.rglob("*.py")


def esta_em_pywa_functions(arquivo):
    try:
        arquivo.relative_to(RAIZ_PYWA)
        return True
    except ValueError:
        return False


class WhatsappStructureTests(unittest.TestCase):
    def test_imports_e_chamadas_pywa_ficam_em_pywa_functions(self):
        violacoes = []

        for arquivo in arquivos_python_producao():
            if esta_em_pywa_functions(arquivo):
                continue

            arvore = ast.parse(arquivo.read_text(encoding="utf-8"))

            for no in ast.walk(arvore):
                if isinstance(no, ast.Import):
                    if any(
                        alias.name == "pywa" or alias.name.startswith("pywa.")
                        for alias in no.names
                    ):
                        violacoes.append(f"{arquivo}:{no.lineno}: import pywa")

                if isinstance(no, ast.ImportFrom):
                    modulo = no.module or ""
                    if modulo == "pywa" or modulo.startswith("pywa."):
                        violacoes.append(f"{arquivo}:{no.lineno}: from pywa")

                if isinstance(no, ast.Call) and isinstance(no.func, ast.Attribute):
                    if no.func.attr in METODOS_PYWA:
                        violacoes.append(
                            f"{arquivo}:{no.lineno}: chamada {no.func.attr}"
                        )

        self.assertEqual(violacoes, [])

    def test_textos_de_saida_ficam_em_messages(self):
        violacoes = []

        for arquivo in arquivos_python_producao():
            if arquivo.is_relative_to(RAIZ_WHATSAPP / "messages"):
                continue

            conteudo = arquivo.read_text(encoding="utf-8")
            for conteudo_whatsapp in CONTEUDOS_WHATSAPP:
                if conteudo_whatsapp in conteudo:
                    violacoes.append(f"{arquivo}: {conteudo_whatsapp}")

        self.assertEqual(violacoes, [])


if __name__ == "__main__":
    unittest.main()
```

## Passo 12 - validaÃ§Ãµes depois da aplicaÃ§Ã£o

Buscar referÃªncias antigas em testes:

```powershell
rg -n "rotear_resposta_cliente|valida_resposta_cliente|flow_treat_context|flow_treat_financial|flow_treat_unsupported_type|sender_etapa1|sender_tratamento|messages\\.tratamentos|pywa_functions\\.envios|pywa_functions\\.etapas" tests
```

O resultado esperado Ã© zero ocorrÃªncias.

Rodar os testes de unidade:

```powershell
python -m pytest tests/unit
```

Rodar a suÃ­te completa:

```powershell
python -m pytest tests
```

Rodar check do Django:

```powershell
python callback/manage.py check
```
