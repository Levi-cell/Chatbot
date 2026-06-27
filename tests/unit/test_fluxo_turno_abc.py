import unittest
from datetime import datetime, timedelta
from unittest.mock import patch

from core.repositories import turno_cliente
from workers.worker_flow.response_flow import flow_sender
from workers.worker_flow.transacoes import finalizacao_fila, ordem_turno


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
                ordem_turno,
                "existe_mensagem_anterior_aberta_conversa",
                side_effect=estado.existe_anterior,
            ), patch.object(
                ordem_turno,
                "reagendar_mensagem_sem_erro",
                side_effect=estado.reagendar_sem_erro,
            ):
                b_reagendada = ordem_turno.reagendar_se_houver_mensagem_anterior(
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
                finalizacao_fila,
                "marcar_mensagem_como_enviada",
                side_effect=estado.marcar_sent,
            ):
                finalizacao_fila.finalizar_mensagem_processada(
                    mensagem_worker(estado, 1),
                    contexto_banco(),
                    lock_version=4,
                    cursor=object(),
                )

            self.assertEqual(estado.filas[1]["status"], "sent")

            with patch.object(
                ordem_turno,
                "existe_mensagem_anterior_aberta_conversa",
                side_effect=estado.existe_anterior,
            ):
                b_ainda_tem_anterior = (
                    ordem_turno.reagendar_se_houver_mensagem_anterior(
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
