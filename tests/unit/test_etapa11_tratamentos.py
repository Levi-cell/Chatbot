import unittest
from types import SimpleNamespace
from unittest.mock import patch

from core.integrations.whatsapp.messages.etapa11_messages import (
    BOTAO_ETAPA11_INICIAR_TRIAGEM,
    montar_mensagem_contexto_invalido_etapa11,
    montar_mensagem_financeiro_etapa11,
    montar_mensagem_midia_etapa11,
    montar_mensagem_triagem_cognitiva_etapa11,
)
from core.integrations.whatsapp.messages.componentes_compartilhados import (
    CABECALHO_ETAPA11_TRIAGEM,
)
from core.integrations.whatsapp.pywa_functions.pywa_senders import (
    etapa11 as sender_etapa11,
)
from workers.worker_flow.response_flow.etapas import resolver_etapa11
from workers.worker_flow.response_flow.etapas.validadores_contexto.valida_etapa11 import (
    validar_etapa11,
)
from workers.worker_flow.response_flow.transicoes.eventos import (
    ETAPA_11_INTRODUCAO_TRIAGEM,
    ETAPA_12_TRIAGEM_PERGUNTA_1,
    EVENTO_TRIAGEM_INICIADA,
)


class _ClienteWhatsAppFake:
    def __init__(self):
        self.ultimo_envio = None

    def send_message(self, **kwargs):
        self.ultimo_envio = kwargs
        return SimpleNamespace(id="wamid.etapa11")


def _contexto_historico(texto, tipo="text", *, dependente=False):
    return {
        "id_conversa": 10,
        "id_etapa_cliente": ETAPA_11_INTRODUCAO_TRIAGEM,
        "id_etapa_origem_transicao": ETAPA_11_INTRODUCAO_TRIAGEM,
        "transicoes_permitidas": {
            EVENTO_TRIAGEM_INICIADA: ETAPA_12_TRIAGEM_PERGUNTA_1,
        },
        "texto_cliente_atual": texto,
        "tipo_mensagem_atual": tipo,
        "status_dependente": dependente,
        "nome_dependente": "Ana" if dependente else None,
        "mensagem_cliente_atual": {
            "id_mensagem_fila": 20,
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
        "tipo_mensagem": "interactive_button",
    }

    if tratamento:
        contexto.update(
            {
                "tratamento": True,
                "tipo_tratamento": tratamento,
            }
        )

    return contexto


class Etapa11TratamentosTests(unittest.TestCase):
    def test_validador_aceita_botao_e_confirmacoes_digitadas(self):
        confirmacoes = (
            "Iniciar triagem",
            "  VAMOS LÁ!!!  ",
            "Começar",
            "ok",
            "certo.",
            "Pode continuar",
            "Com certeza!",
            "Estou pronta",
            "Ok, vamos lá!",
            "Sim, pode começar.",
            "Vamos prosseguir",
            "Pode seguir",
        )

        for texto in confirmacoes:
            with self.subTest(texto=texto):
                self.assertEqual(
                    validar_etapa11(texto),
                    EVENTO_TRIAGEM_INICIADA,
                )

    def test_validador_rejeita_negacoes_e_respostas_fora_do_contexto(self):
        respostas_invalidas = (
            "",
            "não quero começar",
            "agora não",
            "ok, mas não quero",
            "não, vamos lá",
            "sim, mas não quero começar",
            "talvez depois",
            "qualquer coisa",
            None,
        )

        for texto in respostas_invalidas:
            with self.subTest(texto=texto):
                self.assertIsNone(validar_etapa11(texto))

    def test_mensagens_compoem_tratamento_e_reapresentam_etapa(self):
        mensagem_base = montar_mensagem_triagem_cognitiva_etapa11()
        casos = (
            (
                montar_mensagem_midia_etapa11,
                "Olha, ainda não reconhecemos mensagens com mídia",
            ),
            (
                montar_mensagem_financeiro_etapa11,
                "Olha, demais informações, como valores de investimento",
            ),
            (
                montar_mensagem_contexto_invalido_etapa11,
                "Desculpe, não entendi.",
            ),
        )

        for montar_mensagem, inicio_tratamento in casos:
            with self.subTest(montador=montar_mensagem.__name__):
                mensagem = montar_mensagem()
                self.assertTrue(mensagem.startswith(inicio_tratamento))
                self.assertIn("\n\nMas bora lá:\n\n", mensagem)
                self.assertTrue(mensagem.endswith(mensagem_base))

    def test_senders_de_tratamento_preservam_cabecalho_e_botao(self):
        casos = (
            (
                sender_etapa11.enviar_etapa11_midia,
                sender_etapa11.TIPO_TRATAMENTO_MIDIA,
            ),
            (
                sender_etapa11.enviar_etapa11_financeiro,
                sender_etapa11.TIPO_TRATAMENTO_FINANCEIRO,
            ),
            (
                sender_etapa11.enviar_etapa11_contexto_invalido,
                sender_etapa11.TIPO_TRATAMENTO_CONTEXTO_INVALIDO,
            ),
        )

        for enviar, tipo_tratamento in casos:
            cliente = _ClienteWhatsAppFake()

            with self.subTest(sender=enviar.__name__), patch.object(
                sender_etapa11,
                "conta_wa",
                return_value=cliente,
            ):
                contexto = enviar("5571999999999", "phone-id")

            self.assertTrue(
                cliente.ultimo_envio["text"].startswith(
                    f"*{CABECALHO_ETAPA11_TRIAGEM}*\n\n"
                )
            )
            self.assertEqual(
                [botao.title for botao in cliente.ultimo_envio["buttons"]],
                [BOTAO_ETAPA11_INICIAR_TRIAGEM],
            )
            self.assertTrue(contexto["tratamento"])
            self.assertEqual(contexto["tipo_tratamento"], tipo_tratamento)
            self.assertEqual(
                contexto["id_etapa_resultante"],
                ETAPA_11_INTRODUCAO_TRIAGEM,
            )
            self.assertNotIn("evento_transicao", contexto)

    def test_resolver_prioriza_midia_financeiro_e_contexto(self):
        casos = (
            (
                "Quanto custa?",
                "image",
                "enviar_etapa11_midia",
                "tipo_mensagem_nao_suportado",
            ),
            (
                "Quanto custa?",
                "text",
                "enviar_etapa11_financeiro",
                "pergunta_financeira",
            ),
            (
                "Talvez depois",
                "text",
                "enviar_etapa11_contexto_invalido",
                "confirmacao_triagem_invalida",
            ),
        )

        nomes_senders = (
            "enviar_etapa11_midia",
            "enviar_etapa11_financeiro",
            "enviar_etapa11_contexto_invalido",
        )

        for texto, tipo, sender_esperado, tratamento in casos:
            retornos = {
                nome: _contexto_envio(
                    ETAPA_11_INTRODUCAO_TRIAGEM,
                    tratamento=tratamento,
                )
                for nome in nomes_senders
            }

            with self.subTest(texto=texto, tipo=tipo):
                with (
                    patch.object(
                        resolver_etapa11,
                        nomes_senders[0],
                        return_value=retornos[nomes_senders[0]],
                    ) as sender_midia,
                    patch.object(
                        resolver_etapa11,
                        nomes_senders[1],
                        return_value=retornos[nomes_senders[1]],
                    ) as sender_financeiro,
                    patch.object(
                        resolver_etapa11,
                        nomes_senders[2],
                        return_value=retornos[nomes_senders[2]],
                    ) as sender_contexto,
                ):
                    resultado = resolver_etapa11.resolve_etapa11(
                        _contexto_historico(texto, tipo)
                    )

            senders = {
                nomes_senders[0]: sender_midia,
                nomes_senders[1]: sender_financeiro,
                nomes_senders[2]: sender_contexto,
            }
            senders[sender_esperado].assert_called_once_with(
                "5571999999999",
                "phone-id",
            )
            for nome, sender in senders.items():
                if nome != sender_esperado:
                    sender.assert_not_called()

            self.assertTrue(resultado["tratamento"])
            self.assertEqual(
                resultado["id_etapa_resultante"],
                ETAPA_11_INTRODUCAO_TRIAGEM,
            )
            self.assertNotIn("evento_transicao", resultado)

    def test_confirmacao_avanca_para_primeira_pergunta_da_triagem(self):
        for tipo_mensagem in ("interactive", "button", "text"):
            with self.subTest(tipo_mensagem=tipo_mensagem):
                with (
                    patch.object(
                        resolver_etapa11,
                        "enviar_etapa12_cliente",
                        return_value=_contexto_envio(
                            ETAPA_12_TRIAGEM_PERGUNTA_1
                        ),
                    ) as enviar_cliente,
                    patch.object(
                        resolver_etapa11,
                        "enviar_etapa12_dependente",
                    ) as enviar_dependente,
                ):
                    resultado = resolver_etapa11.resolve_etapa11(
                        _contexto_historico(
                            "Iniciar triagem",
                            tipo_mensagem,
                        )
                    )

            enviar_cliente.assert_called_once_with(
                "5571999999999",
                "phone-id",
            )
            enviar_dependente.assert_not_called()
            self.assertEqual(
                resultado["evento_transicao"],
                EVENTO_TRIAGEM_INICIADA,
            )
            self.assertEqual(
                resultado["id_etapa_origem_transicao"],
                ETAPA_11_INTRODUCAO_TRIAGEM,
            )
            self.assertEqual(
                resultado["id_etapa_resultante"],
                ETAPA_12_TRIAGEM_PERGUNTA_1,
            )

    def test_confirmacao_de_dependente_envia_primeira_pergunta_com_nome(self):
        with (
            patch.object(
                resolver_etapa11,
                "enviar_etapa12_cliente",
            ) as enviar_cliente,
            patch.object(
                resolver_etapa11,
                "enviar_etapa12_dependente",
                return_value=_contexto_envio(
                    ETAPA_12_TRIAGEM_PERGUNTA_1
                ),
            ) as enviar_dependente,
        ):
            resultado = resolver_etapa11.resolve_etapa11(
                _contexto_historico(
                    "Vamos lá",
                    dependente=True,
                )
            )

        enviar_cliente.assert_not_called()
        enviar_dependente.assert_called_once_with(
            "5571999999999",
            "phone-id",
            "Ana",
        )
        self.assertEqual(
            resultado["evento_transicao"],
            EVENTO_TRIAGEM_INICIADA,
        )
        self.assertEqual(
            resultado["id_etapa_resultante"],
            ETAPA_12_TRIAGEM_PERGUNTA_1,
        )


if __name__ == "__main__":
    unittest.main()
