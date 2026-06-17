# Plano de implementacao: response_flow com roteador e idempotencia de tratamentos

## Objetivo

Deixar o worker mais enxuto sem mudar regra de negocio, fluxo, commits, rollbacks, locks ou handlers.

A mudanca principal e mover a decisao entre `flow_sender`, `flow_treat_unsupported_type` e `flow_treat_context` para um roteador dedicado dentro de `response_flow`.

Tambem ajustar os tratamentos para ficarem mais alinhados com o `flow_sender`:

- `flow_treat_unsupported_type` passa a logar `retry_count > 1`, igual ao `flow_sender`;
- `flow_treat_context` passa a verificar `resposta_bot_atual` antes de qualquer fluxo, garantindo idempotencia quando esse tratamento for implementado de verdade.

Nada neste plano deve alterar:

- regras de turno;
- regra de tratamento de midia;
- regra de idempotencia;
- ordem dos commits;
- rollbacks;
- close da conexao;
- handlers de erro;
- locks;
- fluxo do webhook;
- fluxo de banco;
- marcacao final da fila como `sent`.

## Passo 1 - Criar `workers/worker_flow/response_flow/rotear_resposta_cliente.py`

Arquivo novo.

Codigo completo:

```python
import logging

from workers.worker_flow.response_flow.flow_sender import flow_sender
from workers.worker_flow.response_flow.flow_treat_context import flow_treat_context
from workers.worker_flow.response_flow.flow_treat_unsupported_type import flow_treat_unsupported_type
from workers.worker_flow.valida_resposta_cliente import (
    RESULTADO_MENSAGEM_FORA_DE_CONTEXTO,
    RESULTADO_TIPO_MENSAGEM_NAO_SUPORTADO,
    validar_resposta_cliente,
)


logger = logging.getLogger("worker.rotear_resposta")


def rotear_resposta_cliente(contexto_historico):
    contexto_validacao = validar_resposta_cliente(contexto_historico)
    resultado_validacao = contexto_validacao["resultado"]

    if resultado_validacao == RESULTADO_TIPO_MENSAGEM_NAO_SUPORTADO:
        return flow_treat_unsupported_type(
            contexto_historico,
            contexto_validacao,
        )

    if resultado_validacao == RESULTADO_MENSAGEM_FORA_DE_CONTEXTO:
        return flow_treat_context(
            contexto_historico,
            contexto_validacao,
        )

    return flow_sender(contexto_historico)
```

## Passo 2 - Alterar `workers/worker_flow/response_flow/flow_treat_unsupported_type.py`

Arquivo modificado.

Codigo completo:

```python
import logging

from core.integrations.whatsapp.sender_tratamento import (
    sender_tratamento_tipo_nao_suportado,
)


logger = logging.getLogger("worker.treat_unsupported_type")


def flow_treat_unsupported_type(contexto_historico, contexto_validacao):
    # Regra de negocio V1: esta versao nao trabalha com midias/anexos.
    # Midia recebida entra no historico, recebe tratamento e nao avanca etapa.
    id_conversa = contexto_historico["id_conversa"]
    retry_count = contexto_historico["retry_count"]
    mensagem_cliente_atual = contexto_historico["mensagem_cliente_atual"]
    resposta_bot_atual = (
        contexto_historico["resposta_bot_para_mensagem_atual"] or {}
    )

    if resposta_bot_atual:
        logger.info(
            "flow_treat_unsupported_type_idempotencia_ok | motivo=resposta_bot_ja_registrada acao=nao_enviar id_conversa=%s id_mensagem_fila=%s id_hash_cliente=%s id_resposta_bot=%s tratamento=%s retry=%s",
            id_conversa,
            mensagem_cliente_atual["id_mensagem_fila"],
            mensagem_cliente_atual["id_hash_msg"],
            resposta_bot_atual.get("id_mensagem"),
            contexto_validacao["tipo_tratamento"],
            retry_count,
        )
        return {
            "enviou": False,
            "resposta_ja_existia": True,
            "id_hash_msg_bot": resposta_bot_atual.get("id_hash_msg"),
            "id_etapa_resultante": resposta_bot_atual.get("id_etapa"),
            "tratamento": True,
            "tipo_tratamento": contexto_validacao["tipo_tratamento"],
            "atualizar_conversa": False,
        }

    if retry_count > 1:
        logger.info(
            "flow_treat_unsupported_type_reprocessamento | motivo=retry_maior_que_um acao=continuar_sem_resposta_previa id_conversa=%s id_mensagem_fila=%s id_hash_cliente=%s retry=%s tratamento=%s",
            id_conversa,
            mensagem_cliente_atual["id_mensagem_fila"],
            mensagem_cliente_atual["id_hash_msg"],
            retry_count,
            contexto_validacao["tipo_tratamento"],
        )

    if contexto_validacao["tipo_tratamento"] == "tipo_mensagem_nao_suportado":
        mensagem_bot = _montar_mensagem_tipo_nao_suportado(contexto_historico)

        return sender_tratamento_tipo_nao_suportado(
            cliente_telefone=mensagem_cliente_atual["cliente_telefone"],
            phone_id_unidade=mensagem_cliente_atual["id_phone_unidade"],
            id_etapa=contexto_historico["id_etapa_cliente"],
            tipo_mensagem=contexto_validacao.get("tipo_mensagem"),
            mensagem_bot=mensagem_bot,
        )

    logger.warning(
        "flow_treat_unsupported_type_nao_implementado | acao=erro id_conversa=%s tratamento=%s",
        id_conversa,
        contexto_validacao["tipo_tratamento"],
    )
    raise NotImplementedError(
        f"Tratamento {contexto_validacao['tipo_tratamento']} ainda nao implementado"
    )


def _montar_mensagem_tipo_nao_suportado(contexto_historico):
    if contexto_historico.get("id_etapa_atual") is None:
        return (
            "Ola! Vi que voce iniciou o atendimento com uma midia.\n\n"
            "Por enquanto eu so consigo continuar por mensagem de texto ou botoes. "
            "Envie uma mensagem de texto para comecarmos."
        )

    return (
        "Recebi uma midia, mas nesta etapa eu preciso que voce responda por texto "
        "ou use os botoes disponiveis.\n\n"
        "Envie uma mensagem de texto para continuarmos."
    )
```

## Passo 3 - Alterar `workers/worker_flow/response_flow/flow_treat_context.py`

Arquivo modificado.

Codigo completo:

```python
import logging


logger = logging.getLogger("worker.treat_context")


def flow_treat_context(contexto_historico, contexto_validacao):
    # Esqueleto reservado para a V1 quando as regras de contexto por etapa
    # forem definidas. Tratamento de contexto deve usar id_etapa_cliente,
    # repetir a pergunta/opcoes da etapa atual e nao avancar a conversa.
    id_conversa = contexto_historico["id_conversa"]
    retry_count = contexto_historico["retry_count"]
    id_etapa_cliente = contexto_historico["id_etapa_cliente"]
    mensagem_cliente_atual = contexto_historico["mensagem_cliente_atual"]
    resposta_bot_atual = (
        contexto_historico["resposta_bot_para_mensagem_atual"] or {}
    )

    if resposta_bot_atual:
        logger.info(
            "flow_treat_context_idempotencia_ok | motivo=resposta_bot_ja_registrada acao=nao_enviar id_conversa=%s id_mensagem_fila=%s id_hash_cliente=%s id_resposta_bot=%s etapa_cliente=%s tratamento=%s retry=%s",
            id_conversa,
            mensagem_cliente_atual["id_mensagem_fila"],
            mensagem_cliente_atual["id_hash_msg"],
            resposta_bot_atual.get("id_mensagem"),
            id_etapa_cliente,
            contexto_validacao["tipo_tratamento"],
            retry_count,
        )
        return {
            "enviou": False,
            "resposta_ja_existia": True,
            "id_hash_msg_bot": resposta_bot_atual.get("id_hash_msg"),
            "id_etapa_resultante": resposta_bot_atual.get("id_etapa"),
            "tratamento": True,
            "tipo_tratamento": contexto_validacao["tipo_tratamento"],
            "atualizar_conversa": False,
        }

    logger.warning(
        "flow_treat_context_nao_implementado | acao=erro id_conversa=%s etapa_cliente=%s id_mensagem_fila=%s resultado=%s retry=%s",
        id_conversa,
        id_etapa_cliente,
        mensagem_cliente_atual["id_mensagem_fila"],
        contexto_validacao["resultado"],
        retry_count,
    )
    raise NotImplementedError(
        "Tratamento de mensagem fora de contexto ainda nao implementado"
    )
```

## Passo 4 - Alterar `workers/worker_flow/response_flow/flow_worker.py`

Arquivo modificado.

Codigo completo:

```python
import logging

import psycopg2

from core.cache.cache_unidade import UnidadeNaoEncontrada
from core.database.connection_aws import get_conn
from core.integrations.whatsapp.exceptions import ErroEnvioMeta
from core.logging_config import short_value
from core.repositories.querys import pegar_mensagens_da_fila, tentar_lock_conversa
from core.repositories.updates import vincular_mensagem_fila_a_conversa
from workers.tratamento_erros_externos.erro_conexao import handle_erro_conexao
from workers.tratamento_erros_externos.erro_generico import handle_erro_generico
from workers.tratamento_erros_externos.exceptions import BancoFalhouAposEnvioMeta
from workers.tratamento_erros_externos.unidade_nao_encontrada import handle_unidade_nao_encontrada
from workers.worker_flow.response_flow.rotear_resposta_cliente import rotear_resposta_cliente
from workers.worker_flow.suport_functions import (
    aguardar_fila_vazia,
    atualizar_banco_com_contexto_final,
    atualizar_estado_com_contexto,
    atualizar_estado_com_mensagem,
    atualizar_estado_lock,
    confirmar_cache_cliente_se_pendente,
    criar_estado_ciclo,
    finalizar_mensagem_processada,
    liberar_lock_conversa_se_necessario,
    logar_lock_recusado,
    montar_mensagem_fila,
    reagendar_se_houver_mensagem_anterior,
    reparar_cache_cliente_stale_se_fk_invalida,
    reparar_cache_unidade_stale_se_fk_invalida,
)
from workers.worker_flow.tratar_bloqueio import tratar_conversa_bloqueada
from workers.worker_flow.valida_banco import validar_banco_mensagem
from workers.worker_flow.valida_historico import valida_historico

logger = logging.getLogger("worker.response_flow")


def worker_flow():
    logger.info("worker_iniciado")

    max_retry = 3
    retry_delay = 5

    while True:
        print("\n\n\n---------------------NOVO CICLO---------------------\n\n\n")
        logger.info("---------- ciclo_worker_inicio ----------")

        conn_ciclo = None
        cursor_ciclo = None
        estado_ciclo = criar_estado_ciclo()
        contexto_envio = {}

        try:
            conn_ciclo = get_conn(application_name="worker_chatbot")
            cursor_ciclo = conn_ciclo.cursor()
            retry_delay = 5
            logger.debug("ciclo_conexao_banco_ok | acao=dequeue")

            registro = pegar_mensagens_da_fila(cursor_ciclo)
            conn_ciclo.commit()

            if not registro:
                aguardar_fila_vazia()
                continue

            mensagem = montar_mensagem_fila(registro)
            atualizar_estado_com_mensagem(estado_ciclo, mensagem)

            logger.info(
                "mensagem_processando | acao=iniciar id_mensagem=%s cliente=%s phone_number_id=%s tipo=%s retry=%s",
                mensagem["id_mensagem"],
                short_value(mensagem["cliente_telefone"]),
                short_value(mensagem["id_phone_unidade"]),
                mensagem["tipo_mensagem"],
                mensagem["retry_count"],
            )

            contexto_banco = validar_banco_mensagem(
                mensagem,
                cursor_ciclo,
            )
            atualizar_estado_com_contexto(estado_ciclo, contexto_banco)

            contexto_conversa = contexto_banco["conversa"]
            id_conversa = contexto_conversa["id_conversa"]

            vincular_mensagem_fila_a_conversa(
                mensagem["id_mensagem"],
                id_conversa,
                cursor_ciclo,
            )
            conn_ciclo.commit()
            logger.debug(
                "mensagem_conversa_vinculada | acao=commit id_mensagem=%s id_conversa=%s estado=%s",
                mensagem["id_mensagem"],
                id_conversa,
                contexto_conversa["estado"],
            )

            confirmar_cache_cliente_se_pendente(contexto_banco)

            if contexto_conversa["estado"] == "bloqueada":
                tratar_conversa_bloqueada(
                    mensagem["id_mensagem"],
                    mensagem["cliente_telefone"],
                    mensagem["id_phone_unidade"],
                    id_conversa,
                    cursor_ciclo,
                )
                conn_ciclo.commit()
                continue

            lock_ok, lock_version = tentar_lock_conversa(id_conversa, cursor_ciclo)
            conn_ciclo.commit()
            atualizar_estado_lock(estado_ciclo, lock_ok, lock_version)

            if not lock_ok:
                logar_lock_recusado(mensagem, contexto_banco)
                continue

            if reagendar_se_houver_mensagem_anterior(
                    mensagem,
                    contexto_banco,
                    lock_version,
                    cursor_ciclo,
            ):
                conn_ciclo.commit()
                continue

            contexto_historico = valida_historico(
                mensagem,
                contexto_banco,
                cursor_ciclo,
            )
            conn_ciclo.commit()
            logger.debug(
                "historico_contexto_ok | acao=commit id_mensagem=%s id_conversa=%s etapa_cliente=%s etapa_resposta=%s inserido=%s",
                mensagem["id_mensagem"],
                id_conversa,
                contexto_historico["id_etapa_cliente"],
                contexto_historico["id_etapa_resposta"],
                contexto_historico["mensagem_cliente_inserida"],
            )

            contexto_envio = rotear_resposta_cliente(contexto_historico)

            try:
                contexto_final = atualizar_banco_com_contexto_final(
                    contexto_historico,
                    contexto_envio,
                    cursor_ciclo,
                )
                conn_ciclo.commit()

            except Exception as erro:
                if contexto_envio.get("enviou"):
                    raise BancoFalhouAposEnvioMeta(
                        "Banco falhou depois da Meta confirmar envio",
                        id_mensagem=mensagem["id_mensagem"],
                        id_conversa=id_conversa,
                        id_hash_msg_bot=contexto_envio.get("id_hash_msg_bot"),
                        id_etapa=contexto_envio.get("id_etapa_resultante"),
                    ) from erro

                raise

            logger.debug(
                "resposta_bot_contexto_final_ok | acao=commit id_mensagem=%s id_conversa=%s etapa=%s resposta_ja_existia=%s id_hash_msg_bot=%s tratamento=%s tipo_tratamento=%s",
                mensagem["id_mensagem"],
                id_conversa,
                contexto_final["id_etapa_resultante"],
                contexto_final["resposta_ja_existia"],
                contexto_final["id_hash_msg_bot"],
                contexto_envio.get("tratamento", False),
                contexto_envio.get("tipo_tratamento"),
            )

            finalizar_mensagem_processada(
                mensagem,
                contexto_banco,
                lock_version,
                cursor_ciclo,
            )
            conn_ciclo.commit()

        except ErroEnvioMeta as erro:
            logger.warning(
                "meta_envio_erro | acao=reagendar_sem_sent id_mensagem=%s cliente=%s phone_number_id=%s etapa=%s erro=%s",
                estado_ciclo["id_mensagem"],
                short_value(estado_ciclo["cliente_telefone"]),
                short_value(estado_ciclo["id_phone_unidade"]),
                erro.id_etapa,
                erro,
            )
            if conn_ciclo:
                conn_ciclo.rollback()

            handle_erro_generico(
                cursor_ciclo,
                estado_ciclo["id_mensagem"],
                erro,
                max_retry,
            )

            if conn_ciclo:
                conn_ciclo.commit()

        except BancoFalhouAposEnvioMeta as erro:
            logger.critical(
                "banco_falhou_apos_envio_meta | risco=resposta_duplicada acao=reagendar_sem_sent id_mensagem=%s id_conversa=%s etapa=%s id_hash_msg_bot=%s tratamento=%s tipo_tratamento=%s erro=%s",
                erro.id_mensagem,
                erro.id_conversa,
                erro.id_etapa,
                erro.id_hash_msg_bot,
                contexto_envio.get("tratamento", False),
                contexto_envio.get("tipo_tratamento"),
                erro,
            )
            if conn_ciclo:
                conn_ciclo.rollback()

            handle_erro_generico(
                cursor_ciclo,
                estado_ciclo["id_mensagem"],
                erro,
                max_retry,
            )

            if conn_ciclo:
                conn_ciclo.commit()

        except psycopg2.OperationalError as erro:
            logger.warning(
                "banco_operacional_erro | acao=retry_conexao id_mensagem=%s erro=%s",
                estado_ciclo["id_mensagem"],
                erro,
            )
            retry_delay = handle_erro_conexao(erro, retry_delay)
            continue

        except UnidadeNaoEncontrada as erro:
            logger.warning(
                "unidade_nao_encontrada | acao=tratar_unidade_invalida id_mensagem=%s cliente=%s phone_number_id=%s erro=%s",
                estado_ciclo["id_mensagem"],
                short_value(estado_ciclo["cliente_telefone"]),
                short_value(estado_ciclo["id_phone_unidade"]),
                erro,
            )
            if conn_ciclo:
                conn_ciclo.rollback()

            handle_unidade_nao_encontrada(
                cursor_ciclo,
                estado_ciclo["id_mensagem"],
                erro,
            )

            if conn_ciclo:
                conn_ciclo.commit()

        except Exception as erro:
            logger.exception(
                "mensagem_erro | acao=tratar_erro_generico id_mensagem=%s cliente=%s phone_number_id=%s id_conversa=%s estado=%s erro=%s",
                estado_ciclo["id_mensagem"],
                short_value(estado_ciclo["cliente_telefone"]),
                short_value(estado_ciclo["id_phone_unidade"]),
                estado_ciclo["id_conversa"],
                estado_ciclo["estado"],
                erro,
            )
            if conn_ciclo:
                conn_ciclo.rollback()

            reparar_cache_cliente_stale_se_fk_invalida(erro, estado_ciclo)
            reparar_cache_unidade_stale_se_fk_invalida(erro, estado_ciclo)

            handle_erro_generico(
                cursor_ciclo,
                estado_ciclo["id_mensagem"],
                erro,
                max_retry,
            )

            if conn_ciclo:
                conn_ciclo.commit()

        finally:
            if conn_ciclo:
                try:
                    unlock_realizado = liberar_lock_conversa_se_necessario(
                        cursor_ciclo,
                        estado_ciclo,
                    )

                    if unlock_realizado is not None:
                        conn_ciclo.commit()

                    conn_ciclo.close()

                except Exception as erro:
                    logger.warning("finalizacao_ciclo_falhou | erro=%s", erro)
```

## Passo 5 - Criar `tests/unit/test_rotear_resposta_cliente.py`

Arquivo novo.

Codigo completo:

```python
import unittest
from unittest.mock import patch

import workers.worker_flow.response_flow.rotear_resposta_cliente as roteador_module
from workers.worker_flow.valida_resposta_cliente import (
    RESULTADO_MENSAGEM_FORA_DE_CONTEXTO,
    RESULTADO_RESPOSTA_VALIDA,
    RESULTADO_TIPO_MENSAGEM_NAO_SUPORTADO,
)


def contexto_historico_base():
    return {
        "id_conversa": 10,
        "id_etapa_cliente": 1,
        "id_etapa_resposta": 2,
        "tipo_mensagem_atual": "text",
        "mensagem_cliente_atual": {
            "id_mensagem_fila": 20,
            "id_hash_msg": "wamid.cliente",
            "cliente_telefone": "5571999999999",
            "id_phone_unidade": "123456",
        },
        "resposta_bot_para_mensagem_atual": None,
    }


class RotearRespostaClienteTests(unittest.TestCase):
    def test_resposta_valida_vai_para_flow_sender(self):
        contexto = contexto_historico_base()

        with patch.object(
            roteador_module,
            "validar_resposta_cliente",
            return_value={"resultado": RESULTADO_RESPOSTA_VALIDA},
        ), patch.object(
            roteador_module,
            "flow_sender",
            return_value={"origem": "sender"},
        ) as flow_sender:
            resultado = roteador_module.rotear_resposta_cliente(contexto)

        self.assertEqual(resultado, {"origem": "sender"})
        flow_sender.assert_called_once_with(contexto)

    def test_tipo_nao_suportado_vai_para_tratamento_de_tipo(self):
        contexto = contexto_historico_base()
        contexto_validacao = {
            "resultado": RESULTADO_TIPO_MENSAGEM_NAO_SUPORTADO,
            "tipo_tratamento": RESULTADO_TIPO_MENSAGEM_NAO_SUPORTADO,
        }

        with patch.object(
            roteador_module,
            "validar_resposta_cliente",
            return_value=contexto_validacao,
        ), patch.object(
            roteador_module,
            "flow_treat_unsupported_type",
            return_value={"origem": "unsupported_type"},
        ) as flow_treat_unsupported_type:
            resultado = roteador_module.rotear_resposta_cliente(contexto)

        self.assertEqual(resultado, {"origem": "unsupported_type"})
        flow_treat_unsupported_type.assert_called_once_with(
            contexto,
            contexto_validacao,
        )

    def test_fora_de_contexto_vai_para_tratamento_de_contexto(self):
        contexto = contexto_historico_base()
        contexto_validacao = {
            "resultado": RESULTADO_MENSAGEM_FORA_DE_CONTEXTO,
            "tipo_tratamento": RESULTADO_MENSAGEM_FORA_DE_CONTEXTO,
        }

        with patch.object(
            roteador_module,
            "validar_resposta_cliente",
            return_value=contexto_validacao,
        ), patch.object(
            roteador_module,
            "flow_treat_context",
            return_value={"origem": "context"},
        ) as flow_treat_context:
            resultado = roteador_module.rotear_resposta_cliente(contexto)

        self.assertEqual(resultado, {"origem": "context"})
        flow_treat_context.assert_called_once_with(
            contexto,
            contexto_validacao,
        )


if __name__ == "__main__":
    unittest.main()
```

## Passo 6 - Criar `tests/unit/test_flow_treat_context.py`

Arquivo novo.

Codigo completo:

```python
import unittest

from workers.worker_flow.response_flow.flow_treat_context import flow_treat_context
from workers.worker_flow.valida_resposta_cliente import (
    RESULTADO_MENSAGEM_FORA_DE_CONTEXTO,
)


def contexto_historico_base(resposta_bot=None):
    return {
        "id_conversa": 10,
        "retry_count": 2,
        "id_etapa_cliente": 1,
        "mensagem_cliente_atual": {
            "id_mensagem_fila": 20,
            "id_hash_msg": "wamid.cliente",
        },
        "resposta_bot_para_mensagem_atual": resposta_bot,
    }


def contexto_validacao_base():
    return {
        "resultado": RESULTADO_MENSAGEM_FORA_DE_CONTEXTO,
        "tipo_tratamento": RESULTADO_MENSAGEM_FORA_DE_CONTEXTO,
    }


class FlowTreatContextTests(unittest.TestCase):
    def test_idempotente_nao_envia_meta_quando_resposta_ja_existe(self):
        resultado = flow_treat_context(
            contexto_historico_base(
                resposta_bot={
                    "id_mensagem": 99,
                    "id_hash_msg": "wamid.bot.existente",
                    "id_etapa": 1,
                }
            ),
            contexto_validacao_base(),
        )

        self.assertFalse(resultado["enviou"])
        self.assertTrue(resultado["resposta_ja_existia"])
        self.assertEqual(resultado["id_hash_msg_bot"], "wamid.bot.existente")
        self.assertEqual(resultado["id_etapa_resultante"], 1)
        self.assertTrue(resultado["tratamento"])
        self.assertFalse(resultado["atualizar_conversa"])

    def test_sem_resposta_existente_ainda_nao_implementado(self):
        with self.assertRaises(NotImplementedError):
            flow_treat_context(
                contexto_historico_base(),
                contexto_validacao_base(),
            )


if __name__ == "__main__":
    unittest.main()
```

## Passo 7 - Alterar `tests/unit/test_worker_flow_contract.py`

Arquivo modificado.

Codigo completo:

```python
import inspect
import unittest

from workers.worker_flow.response_flow import flow_worker


class WorkerFlowContractTests(unittest.TestCase):
    def test_sent_fica_depois_do_roteamento_e_da_persistencia_final(self):
        source = inspect.getsource(flow_worker.worker_flow)

        pos_valida_historico = source.index("contexto_historico = valida_historico")
        pos_rotear_resposta = source.index("contexto_envio = rotear_resposta_cliente")
        pos_atualizar_banco = source.index("contexto_final = atualizar_banco_com_contexto_final")
        pos_finalizar = source.index("finalizar_mensagem_processada")

        self.assertLess(pos_valida_historico, pos_rotear_resposta)
        self.assertLess(pos_rotear_resposta, pos_atualizar_banco)
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

## Validacao

Rodar:

```powershell
C:\Chatbot\venv\.venv\Scripts\python.exe -m compileall -q core callback workers main.py tests
C:\Chatbot\venv\.venv\Scripts\python.exe callback\manage.py check
C:\Chatbot\venv\.venv\Scripts\python.exe -m unittest discover -s tests -v
git diff --check
```

Confirmar:

- `flow_worker.py` nao chama mais diretamente `validar_resposta_cliente`, `flow_sender`, `flow_treat_unsupported_type` ou `flow_treat_context`;
- `flow_worker.py` continua mantendo todos os `commit`, `rollback` e `close`;
- `rotear_resposta_cliente.py` nao tem SQL, `commit`, `rollback` ou `close`;
- `flow_treat_unsupported_type.py` preserva idempotencia e adiciona log para `retry_count > 1`;
- `flow_treat_context.py` verifica `resposta_bot_atual` antes de qualquer fluxo futuro;
- a ordem transacional continua igual: `valida_historico` -> `rotear_resposta_cliente` -> `atualizar_banco_com_contexto_final` -> `finalizar_mensagem_processada`;
- erro da Meta continua caindo em `ErroEnvioMeta`;
- banco falhando depois de envio confirmado pela Meta continua caindo em `BancoFalhouAposEnvioMeta`;
- nenhuma regra de negocio do webhook, worker, fila, historico, tratamento de midia ou idempotencia e alterada.

## Observacao

Esta refatoracao e organizacional e de observabilidade. Ela reduz o bloco de decisao dentro do `flow_worker.py` e deixa os tratamentos preparados para retry/idempotencia, mas nao altera o comportamento funcional da V1.
