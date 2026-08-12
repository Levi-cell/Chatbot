import unittest
from types import SimpleNamespace
from unittest.mock import patch

from core.integrations.whatsapp.messages.componentes_compartilhados import (
    RODAPE_OPCAO_UNICA,
)
from core.integrations.whatsapp.messages.etapa3_messages import (
    BOTAO_ETAPA3_NAO,
    BOTAO_ETAPA3_SIM,
    montar_mensagem_contexto_etapa3,
    montar_mensagem_etapa3,
    montar_mensagem_financeiro_etapa3,
    montar_mensagem_midia_etapa3,
)
from core.integrations.whatsapp.pywa_functions.pywa_senders import (
    etapa3 as sender_etapa3,
)
from workers.worker_flow.response_flow import flow_sender as modulo_flow_sender
from workers.worker_flow.response_flow.etapas import (
    resolver_etapa2,
    resolver_etapa3,
    resolver_etapa4,
)
from workers.worker_flow.response_flow.etapas.validadores_contexto.valida_etapa3 import (
    validar_etapa3,
)
from workers.worker_flow.response_flow.transicoes.eventos import (
    ETAPA_3_CONFIRMACAO_DESTINO,
    ETAPA_4_PROFISSAO,
    ETAPA_5_NOME_DEPENDENTE,
    EVENTO_DESTINO_ATENDIMENTO_CONFIRMADO,
    EVENTO_DESTINO_ATENDIMENTO_DEFINIDO,
    EVENTO_PROFISSAO_DEPENDENTE_VALIDA,
)


class _ClienteWhatsAppFake:
    def __init__(self):
        self.ultimo_envio = None

    def send_message(self, **kwargs):
        self.ultimo_envio = kwargs
        return SimpleNamespace(id="wamid.etapa3")


def _contexto_historico(
    texto,
    *,
    status_dependente=False,
    tipo="text",
):
    return {
        "id_conversa": 30,
        "id_etapa_atual": ETAPA_3_CONFIRMACAO_DESTINO,
        "id_etapa_cliente": ETAPA_3_CONFIRMACAO_DESTINO,
        "id_etapa_origem_transicao": ETAPA_3_CONFIRMACAO_DESTINO,
        "transicoes_permitidas": {
            EVENTO_DESTINO_ATENDIMENTO_CONFIRMADO: ETAPA_4_PROFISSAO,
        },
        "texto_cliente_atual": texto,
        "tipo_mensagem_atual": tipo,
        "status_dependente": status_dependente,
        "retry_count": 1,
        "resposta_bot_para_mensagem_atual": None,
        "mensagem_cliente_atual": {
            "id_mensagem_fila": 31,
            "id_hash_msg": "wamid.cliente",
            "cliente_telefone": "5571999999999",
            "id_phone_unidade": "phone-id",
        },
    }


def _contexto_envio(id_etapa, *, tratamento=None):
    contexto = {
        "enviou": True,
        "resposta_ja_existia": False,
        "mensagem_bot": "mensagem",
        "id_hash_msg_bot": "wamid.bot",
        "id_etapa_resultante": id_etapa,
        "tipo_mensagem": "text",
    }

    if tratamento:
        contexto.update(
            {
                "tratamento": True,
                "tipo_tratamento": tratamento,
            }
        )

    return contexto


class Etapa3ConfirmacaoDestinoTests(unittest.TestCase):
    def test_etapa2_entrega_escolha_inicial_para_confirmacao(self):
        casos = (
            ("Para mim", False),
            ("Para um dependente", True),
        )

        for texto, status_dependente in casos:
            contexto = _contexto_historico(texto)
            contexto.update(
                {
                    "id_etapa_atual": 2,
                    "id_etapa_cliente": 2,
                    "id_etapa_origem_transicao": 2,
                    "transicoes_permitidas": {
                        EVENTO_DESTINO_ATENDIMENTO_DEFINIDO: (
                            ETAPA_3_CONFIRMACAO_DESTINO
                        ),
                    },
                }
            )

            with self.subTest(texto=texto), patch.object(
                resolver_etapa2,
                "enviar_etapa3",
                return_value=_contexto_envio(
                    ETAPA_3_CONFIRMACAO_DESTINO
                ),
            ) as enviar_confirmacao:
                resultado = resolver_etapa2.resolve_etapa2(contexto)

            enviar_confirmacao.assert_called_once_with(
                "5571999999999",
                "phone-id",
                status_dependente,
            )
            self.assertEqual(
                resultado["evento_transicao"],
                EVENTO_DESTINO_ATENDIMENTO_DEFINIDO,
            )
            self.assertEqual(
                resultado["id_etapa_resultante"],
                ETAPA_3_CONFIRMACAO_DESTINO,
            )
            self.assertIs(
                resultado["status_dependente"],
                status_dependente,
            )

    def test_mensagens_variam_com_destino_sem_entendi_ou_entao(self):
        titular = montar_mensagem_etapa3(False)
        dependente = montar_mensagem_etapa3(True)

        self.assertEqual(
            titular,
            "Você confirma que esse atendimento é para você?",
        )
        self.assertEqual(
            dependente,
            "Você confirma que esse atendimento é para um "
            "dependente?",
        )
        self.assertNotIn("entendi", titular.casefold())
        self.assertNotIn("entendi", dependente.casefold())
        self.assertNotIn("então", titular.casefold())
        self.assertNotIn("então", dependente.casefold())

    def test_tratamentos_reapresentam_a_pergunta_do_destino_atual(self):
        casos = (
            (montar_mensagem_midia_etapa3, "mensagens com mídia"),
            (
                montar_mensagem_financeiro_etapa3,
                "valores de investimento",
            ),
            (montar_mensagem_contexto_etapa3, "Desculpe, não entendi."),
        )

        for status_dependente in (False, True):
            pergunta = montar_mensagem_etapa3(status_dependente)
            for montar, aviso in casos:
                with self.subTest(
                    status_dependente=status_dependente,
                    montar=montar.__name__,
                ):
                    mensagem = montar(status_dependente)
                    self.assertIn(aviso, mensagem)
                    self.assertIn("\n\nMas bora lá:\n\n", mensagem)
                    self.assertNotIn(
                        "Mas bora lá:\n\nEntendi",
                        mensagem,
                    )
                    self.assertTrue(mensagem.endswith(pergunta))

    def test_sender_preserva_botoes_e_rodape_de_opcao_unica(self):
        cliente = _ClienteWhatsAppFake()

        with patch.object(
            sender_etapa3,
            "conta_wa",
            return_value=cliente,
        ):
            contexto = sender_etapa3.enviar_etapa3(
                "5571999999999",
                "phone-id",
                True,
            )

        self.assertEqual(
            [botao.title for botao in cliente.ultimo_envio["buttons"]],
            [BOTAO_ETAPA3_SIM, BOTAO_ETAPA3_NAO],
        )
        self.assertTrue(
            cliente.ultimo_envio["text"].endswith(
                f"_{RODAPE_OPCAO_UNICA}_"
            )
        )
        self.assertEqual(
            contexto["id_etapa_resultante"],
            ETAPA_3_CONFIRMACAO_DESTINO,
        )

    def test_validador_aceita_somente_sim_ou_nao(self):
        entradas_sim = ("Sim", "SIM", " sim ", "\nSim\t")
        entradas_nao = ("Não", "NÃO", "nao", " não ")

        for status_atual in (False, True):
            for texto in entradas_sim:
                with self.subTest(
                    texto=texto,
                    status_atual=status_atual,
                ):
                    resultado = validar_etapa3(texto, status_atual)
                    self.assertTrue(resultado.valida)
                    self.assertIs(
                        resultado.status_dependente_final,
                        status_atual,
                    )

            for texto in entradas_nao:
                with self.subTest(
                    texto=texto,
                    status_atual=status_atual,
                ):
                    resultado = validar_etapa3(texto, status_atual)
                    self.assertTrue(resultado.valida)
                    self.assertIs(
                        resultado.status_dependente_final,
                        not status_atual,
                    )

    def test_validador_rejeita_qualquer_outro_conteudo(self):
        respostas_invalidas = (
            "",
            "s",
            "n",
            "ok",
            "confirmo",
            "foi um engano",
            "para mim",
            "para um dependente",
            "sim!",
            "não?",
            "sim, é para mim",
            "não é para outra pessoa",
            "sim 👍",
            "qualquer coisa",
            None,
        )

        for status_atual in (False, True):
            for texto in respostas_invalidas:
                with self.subTest(
                    texto=texto,
                    status_atual=status_atual,
                ):
                    resultado = validar_etapa3(texto, status_atual)
                    self.assertFalse(resultado.valida)
                    self.assertIsNone(
                        resultado.status_dependente_final
                    )

    def test_resolver_aceita_clique_nos_botoes_sim_e_nao(self):
        casos = (
            ("interactive", "Sim"),
            ("button", "Não"),
        )

        for tipo, texto in casos:
            with self.subTest(tipo=tipo, texto=texto):
                with patch.object(
                    resolver_etapa3,
                    "enviar_etapa4",
                    return_value=_contexto_envio(ETAPA_4_PROFISSAO),
                ) as enviar_profissao:
                    resultado = resolver_etapa3.resolve_etapa3(
                        _contexto_historico(
                            texto,
                            tipo=tipo,
                            status_dependente=False,
                        )
                    )

            enviar_profissao.assert_called_once_with(
                "5571999999999",
                "phone-id",
            )
            self.assertEqual(
                resultado["id_etapa_resultante"],
                ETAPA_4_PROFISSAO,
            )

    def test_resolver_prioriza_midia_financeiro_e_contexto(self):
        casos = (
            (
                "quanto custa?",
                "image",
                "enviar_etapa3_midia",
                "tipo_mensagem_nao_suportado",
            ),
            (
                "quanto custa?",
                "text",
                "enviar_etapa3_financeiro",
                "pergunta_financeira",
            ),
            (
                "talvez",
                "text",
                "enviar_etapa3_contexto_invalido",
                "confirmacao_destino_invalida",
            ),
            (
                "sim, é para mim",
                "text",
                "enviar_etapa3_contexto_invalido",
                "confirmacao_destino_invalida",
            ),
        )
        nomes_senders = (
            "enviar_etapa3_midia",
            "enviar_etapa3_financeiro",
            "enviar_etapa3_contexto_invalido",
        )

        for texto, tipo, esperado, tratamento in casos:
            retornos = {
                nome: _contexto_envio(
                    ETAPA_3_CONFIRMACAO_DESTINO,
                    tratamento=tratamento,
                )
                for nome in nomes_senders
            }
            with self.subTest(texto=texto, tipo=tipo):
                with (
                    patch.object(
                        resolver_etapa3,
                        nomes_senders[0],
                        return_value=retornos[nomes_senders[0]],
                    ) as sender_midia,
                    patch.object(
                        resolver_etapa3,
                        nomes_senders[1],
                        return_value=retornos[nomes_senders[1]],
                    ) as sender_financeiro,
                    patch.object(
                        resolver_etapa3,
                        nomes_senders[2],
                        return_value=retornos[nomes_senders[2]],
                    ) as sender_contexto,
                ):
                    resultado = resolver_etapa3.resolve_etapa3(
                        _contexto_historico(
                            texto,
                            tipo=tipo,
                            status_dependente=True,
                        )
                    )

            senders = {
                nomes_senders[0]: sender_midia,
                nomes_senders[1]: sender_financeiro,
                nomes_senders[2]: sender_contexto,
            }
            senders[esperado].assert_called_once_with(
                "5571999999999",
                "phone-id",
                True,
            )
            for nome, sender in senders.items():
                if nome != esperado:
                    sender.assert_not_called()

            self.assertTrue(resultado["tratamento"])
            self.assertNotIn("evento_transicao", resultado)

    def test_resolver_encaminha_por_estado_final_absoluto(self):
        casos = (
            (
                False,
                "sim",
                False,
            ),
            (
                False,
                "não",
                True,
            ),
            (
                True,
                "sim",
                True,
            ),
            (
                True,
                "não",
                False,
            ),
        )

        for (
            status_atual,
            texto,
            status_final,
        ) in casos:
            with self.subTest(
                status_atual=status_atual,
                texto=texto,
            ):
                with patch.object(
                    resolver_etapa3,
                    "enviar_etapa4",
                    return_value=_contexto_envio(ETAPA_4_PROFISSAO),
                ) as enviar_profissao:
                    resultado = resolver_etapa3.resolve_etapa3(
                        _contexto_historico(
                            texto,
                            status_dependente=status_atual,
                        )
                    )

            enviar_profissao.assert_called_once_with(
                "5571999999999",
                "phone-id",
            )
            self.assertEqual(
                resultado["evento_transicao"],
                EVENTO_DESTINO_ATENDIMENTO_CONFIRMADO,
            )
            self.assertEqual(
                resultado["id_etapa_resultante"],
                ETAPA_4_PROFISSAO,
            )
            self.assertIs(
                resultado["status_dependente_final"],
                status_final,
            )
            self.assertIs(
                resultado["status_dependente_anterior"],
                status_atual,
            )
            self.assertEqual(
                resultado["status_dependente_alterado"],
                status_final != status_atual,
            )

    def test_replay_recupera_status_final_persistido_sem_inverter(self):
        for status_final in (False, True):
            contexto = _contexto_historico(
                "não",
                status_dependente=status_final,
            )
            contexto["retry_count"] = 2
            contexto["resposta_bot_para_mensagem_atual"] = {
                "id_mensagem": 99,
                "id_hash_msg": "wamid.resposta-existente",
                "id_etapa": ETAPA_4_PROFISSAO,
            }

            with self.subTest(status_final=status_final):
                resultado = modulo_flow_sender.flow_sender(contexto)

            self.assertTrue(resultado["resposta_ja_existia"])
            self.assertEqual(
                resultado["evento_transicao"],
                EVENTO_DESTINO_ATENDIMENTO_CONFIRMADO,
            )
            self.assertIs(
                resultado["status_dependente_final"],
                status_final,
            )

    def test_replay_recusa_status_dependente_ausente(self):
        contexto = _contexto_historico("sim")
        contexto["status_dependente"] = None
        contexto["retry_count"] = 2
        contexto["resposta_bot_para_mensagem_atual"] = {
            "id_mensagem": 99,
            "id_hash_msg": "wamid.resposta-existente",
            "id_etapa": ETAPA_4_PROFISSAO,
        }

        with self.assertRaisesRegex(ValueError, "status_dependente"):
            modulo_flow_sender.flow_sender(contexto)

    def test_primeiro_processamento_recusa_status_dependente_ausente(self):
        contexto = _contexto_historico("sim")
        contexto["status_dependente"] = None

        with self.assertRaisesRegex(ValueError, "status_dependente"):
            resolver_etapa3.resolve_etapa3(contexto)

    def test_dependente_confirma_depois_informa_profissao_antes_do_nome(self):
        with patch.object(
            resolver_etapa3,
            "enviar_etapa4",
            return_value=_contexto_envio(ETAPA_4_PROFISSAO),
        ):
            confirmacao = resolver_etapa3.resolve_etapa3(
                _contexto_historico("sim", status_dependente=True)
            )

        self.assertEqual(
            confirmacao["id_etapa_resultante"],
            ETAPA_4_PROFISSAO,
        )
        self.assertIs(confirmacao["status_dependente_final"], True)

        contexto_profissao = _contexto_historico(
            "Professora",
            status_dependente=confirmacao["status_dependente_final"],
        )
        contexto_profissao.update(
            {
                "id_etapa_atual": ETAPA_4_PROFISSAO,
                "id_etapa_cliente": ETAPA_4_PROFISSAO,
                "id_etapa_origem_transicao": ETAPA_4_PROFISSAO,
                "transicoes_permitidas": {
                    EVENTO_PROFISSAO_DEPENDENTE_VALIDA: (
                        ETAPA_5_NOME_DEPENDENTE
                    ),
                },
            }
        )

        with patch.object(
            resolver_etapa4,
            "enviar_etapa5",
            return_value=_contexto_envio(ETAPA_5_NOME_DEPENDENTE),
        ) as enviar_nome_dependente:
            profissao = resolver_etapa4.resolve_etapa4(contexto_profissao)

        enviar_nome_dependente.assert_called_once_with(
            "5571999999999",
            "phone-id",
        )
        self.assertEqual(
            profissao["evento_transicao"],
            EVENTO_PROFISSAO_DEPENDENTE_VALIDA,
        )
        self.assertEqual(
            profissao["id_etapa_resultante"],
            ETAPA_5_NOME_DEPENDENTE,
        )
        self.assertEqual(profissao["profissao"], "Professora")

    def test_profissao_recusa_destino_do_atendimento_ausente(self):
        contexto = _contexto_historico("Professora")
        contexto.update(
            {
                "id_etapa_atual": ETAPA_4_PROFISSAO,
                "id_etapa_cliente": ETAPA_4_PROFISSAO,
                "id_etapa_origem_transicao": ETAPA_4_PROFISSAO,
                "status_dependente": None,
            }
        )

        with self.assertRaisesRegex(ValueError, "status_dependente"):
            resolver_etapa4.resolve_etapa4(contexto)


if __name__ == "__main__":
    unittest.main()
