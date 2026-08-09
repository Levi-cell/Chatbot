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
)
from workers.worker_flow.response_flow.etapas.validadores_contexto.valida_etapa3 import (
    MOTIVO_SINAIS_CONTRADITORIOS,
    validar_etapa3,
)
from workers.worker_flow.response_flow.transicoes.eventos import (
    ETAPA_3_CONFIRMACAO_DESTINO,
    ETAPA_4_PROFISSAO,
    ETAPA_5_NOME_DEPENDENTE,
    EVENTO_DESTINO_ATENDIMENTO_CONFIRMADO_DEPENDENTE,
    EVENTO_DESTINO_ATENDIMENTO_CONFIRMADO_TITULAR,
    EVENTO_DESTINO_ATENDIMENTO_DEFINIDO,
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
            EVENTO_DESTINO_ATENDIMENTO_CONFIRMADO_TITULAR: (
                ETAPA_4_PROFISSAO
            ),
            EVENTO_DESTINO_ATENDIMENTO_CONFIRMADO_DEPENDENTE: (
                ETAPA_5_NOME_DEPENDENTE
            ),
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

    def test_mensagens_variam_com_destino_sem_exibir_entao(self):
        titular = montar_mensagem_etapa3(False)
        dependente = montar_mensagem_etapa3(True)

        self.assertEqual(
            titular,
            "Entendi, você confirma que esse atendimento é para você?",
        )
        self.assertEqual(
            dependente,
            "Entendi, você confirma que esse atendimento é para um "
            "dependente?",
        )
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

    def test_validador_aceita_confirmacoes_positivas_e_negativas(self):
        positivas = (
            "Sim",
            "s",
            "confirmo",
            "Confirmo sim",
            "Ok",
            "Sim, vamos lá",
            "Ok, continuar",
            "pode prosseguir",
            "isso mesmo",
        )
        negativas = (
            "Não",
            "n",
            "Não confirmo",
            "não, acabei me enganando",
            "foi um engano",
            "me confundi",
            "marquei errado",
        )

        for status_atual in (False, True):
            for texto in positivas:
                with self.subTest(
                    texto=texto,
                    status_atual=status_atual,
                ):
                    resultado = validar_etapa3(texto, status_atual)
                    self.assertTrue(resultado.valida)
                    self.assertEqual(
                        resultado.status_dependente_final,
                        status_atual,
                    )

            for texto in negativas:
                with self.subTest(
                    texto=texto,
                    status_atual=status_atual,
                ):
                    resultado = validar_etapa3(texto, status_atual)
                    self.assertTrue(resultado.valida)
                    self.assertEqual(
                        resultado.status_dependente_final,
                        not status_atual,
                    )

    def test_validador_aceita_destino_explicito_e_erros_tolerados(self):
        para_titular = (
            "Para mim",
            "eu mesmo",
            "só para mim",
            "é a para mim",
            "é para min",
            "pra min",
            "só para min",
            "somente para min",
            "apenas para min",
            "eu quero para min",
        )
        para_dependente = (
            "Para outra pessoa",
            "para um dependente",
            "é para meu filho",
            "para minha mãe",
            "para alguém que depende de mim",
            "para uma criança",
            "para um idoso",
            "para uma pessoa com deficiência",
        )

        for texto in para_titular:
            with self.subTest(texto=texto):
                resultado = validar_etapa3(texto, True)
                self.assertTrue(resultado.valida)
                self.assertFalse(resultado.status_dependente_final)

        for texto in para_dependente:
            with self.subTest(texto=texto):
                resultado = validar_etapa3(texto, False)
                self.assertTrue(resultado.valida)
                self.assertTrue(resultado.status_dependente_final)

    def test_validador_aceita_correcao_contrastiva(self):
        casos = (
            (
                "Não é para mim não, é para outra pessoa",
                False,
                True,
            ),
            ("Né para mim não é para meu filho", False, True),
            (
                "Não é para outra pessoa não, é para min",
                True,
                False,
            ),
            (
                "Não é para um dependente, mas é para eu mesmo",
                True,
                False,
            ),
        )

        for texto, status_atual, status_final in casos:
            with self.subTest(texto=texto):
                resultado = validar_etapa3(texto, status_atual)
                self.assertTrue(resultado.valida)
                self.assertEqual(
                    resultado.status_dependente_final,
                    status_final,
                )

    def test_validador_aceita_polaridades_compostas_coerentes(self):
        casos = (
            ("não, foi um engano", False),
            ("não, me enganei", False),
            ("não, errei", False),
            ("sim, confirmo", True),
            ("sim, isso mesmo", True),
        )

        for texto, polaridade_positiva in casos:
            for status_atual in (False, True):
                with self.subTest(texto=texto, status_atual=status_atual):
                    resultado = validar_etapa3(texto, status_atual)
                    self.assertTrue(resultado.valida)
                    esperado = (
                        status_atual
                        if polaridade_positiva
                        else not status_atual
                    )
                    self.assertEqual(
                        resultado.status_dependente_final,
                        esperado,
                    )

    def test_erro_sem_destino_inverte_a_escolha_atual(self):
        frases = (
            "me enganei",
            "foi um engano",
            "errei",
            "Cometi um erro",
            "Eu cometi um erro",
        )

        for status_atual in (False, True):
            for texto in frases:
                with self.subTest(texto=texto, status_atual=status_atual):
                    resultado = validar_etapa3(texto, status_atual)
                    self.assertTrue(resultado.valida)
                    self.assertIs(
                        resultado.status_dependente_final,
                        not status_atual,
                    )

    def test_erro_com_destino_so_aceita_correcao_logica(self):
        casos_validos = (
            ("me enganei, é para outra pessoa", False, True),
            ("errei, é para outra pessoa", False, True),
            ("Cometi um erro, é para outra pessoa", False, True),
            ("me enganei, é para mim", True, False),
            ("errei, é para mim", True, False),
            ("Cometi um erro, é para mim", True, False),
        )
        casos_contraditorios = (
            ("me enganei, é para outra pessoa", True),
            ("errei, é para outra pessoa", True),
            ("Cometi um erro, é para outra pessoa", True),
            ("me enganei, é para mim", False),
            ("errei, é para mim", False),
            ("Cometi um erro, é para mim", False),
        )

        for texto, status_atual, status_final in casos_validos:
            with self.subTest(texto=texto, status_atual=status_atual):
                resultado = validar_etapa3(texto, status_atual)
                self.assertTrue(resultado.valida)
                self.assertIs(
                    resultado.status_dependente_final,
                    status_final,
                )

        for texto, status_atual in casos_contraditorios:
            with self.subTest(texto=texto, status_atual=status_atual):
                resultado = validar_etapa3(texto, status_atual)
                self.assertFalse(resultado.valida)
                self.assertEqual(
                    resultado.motivo,
                    MOTIVO_SINAIS_CONTRADITORIOS,
                )

    def test_validador_rejeita_polaridades_compostas_contraditorias(self):
        for texto in ("sim, não confirmo", "não, sim"):
            with self.subTest(texto=texto):
                resultado = validar_etapa3(texto, False)
                self.assertFalse(resultado.valida)
                self.assertEqual(
                    resultado.motivo,
                    MOTIVO_SINAIS_CONTRADITORIOS,
                )

    def test_validador_entende_negacao_direta_do_destino(self):
        casos = (
            ("Não é para mim", False, True),
            ("Né pra min não", False, True),
            ("Não é para outra pessoa", True, False),
            ("Não é para o meu filho", True, False),
        )

        for texto, status_atual, status_final in casos:
            with self.subTest(texto=texto):
                resultado = validar_etapa3(texto, status_atual)
                self.assertTrue(resultado.valida)
                self.assertEqual(
                    resultado.status_dependente_final,
                    status_final,
                )

    def test_validador_rejeita_polaridade_e_destino_contraditorios(self):
        casos = (
            ("sim, é para mim", True),
            ("sim, é para outra pessoa", False),
            ("não, é para outra pessoa", True),
            ("não, é para mim", False),
            ("sim, eu quero, é para meu filho", False),
        )

        for texto, status_atual in casos:
            with self.subTest(texto=texto):
                resultado = validar_etapa3(texto, status_atual)
                self.assertFalse(resultado.valida)
                self.assertEqual(
                    resultado.motivo,
                    MOTIVO_SINAIS_CONTRADITORIOS,
                )

    def test_validador_rejeita_respostas_fora_do_contexto(self):
        for texto in ("", "talvez", "qualquer coisa", "sim banana", None):
            with self.subTest(texto=texto):
                self.assertFalse(validar_etapa3(texto, False).valida)

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
                EVENTO_DESTINO_ATENDIMENTO_CONFIRMADO_TITULAR,
                ETAPA_4_PROFISSAO,
                "enviar_etapa4",
            ),
            (
                False,
                "não",
                True,
                EVENTO_DESTINO_ATENDIMENTO_CONFIRMADO_DEPENDENTE,
                ETAPA_5_NOME_DEPENDENTE,
                "enviar_etapa5",
            ),
            (
                True,
                "sim",
                True,
                EVENTO_DESTINO_ATENDIMENTO_CONFIRMADO_DEPENDENTE,
                ETAPA_5_NOME_DEPENDENTE,
                "enviar_etapa5",
            ),
            (
                True,
                "foi um engano",
                False,
                EVENTO_DESTINO_ATENDIMENTO_CONFIRMADO_TITULAR,
                ETAPA_4_PROFISSAO,
                "enviar_etapa4",
            ),
        )

        for (
            status_atual,
            texto,
            status_final,
            evento,
            destino,
            sender_esperado,
        ) in casos:
            with self.subTest(
                status_atual=status_atual,
                texto=texto,
            ):
                with (
                    patch.object(
                        resolver_etapa3,
                        "enviar_etapa4",
                        return_value=_contexto_envio(ETAPA_4_PROFISSAO),
                    ) as enviar_titular,
                    patch.object(
                        resolver_etapa3,
                        "enviar_etapa5",
                        return_value=_contexto_envio(
                            ETAPA_5_NOME_DEPENDENTE
                        ),
                    ) as enviar_dependente,
                ):
                    resultado = resolver_etapa3.resolve_etapa3(
                        _contexto_historico(
                            texto,
                            status_dependente=status_atual,
                        )
                    )

            senders = {
                "enviar_etapa4": enviar_titular,
                "enviar_etapa5": enviar_dependente,
            }
            senders[sender_esperado].assert_called_once_with(
                "5571999999999",
                "phone-id",
            )
            self.assertEqual(resultado["evento_transicao"], evento)
            self.assertEqual(resultado["id_etapa_resultante"], destino)
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

    def test_replay_recupera_status_final_pelo_evento_sem_inverter(self):
        casos = (
            (
                EVENTO_DESTINO_ATENDIMENTO_CONFIRMADO_TITULAR,
                ETAPA_4_PROFISSAO,
                False,
            ),
            (
                EVENTO_DESTINO_ATENDIMENTO_CONFIRMADO_DEPENDENTE,
                ETAPA_5_NOME_DEPENDENTE,
                True,
            ),
        )

        for evento, destino, status_final in casos:
            contexto = _contexto_historico(
                "não",
                status_dependente=not status_final,
            )
            contexto["retry_count"] = 2
            contexto["resposta_bot_para_mensagem_atual"] = {
                "id_mensagem": 99,
                "id_hash_msg": "wamid.resposta-existente",
                "id_etapa": destino,
            }

            with self.subTest(evento=evento):
                resultado = modulo_flow_sender.flow_sender(contexto)

            self.assertTrue(resultado["resposta_ja_existia"])
            self.assertEqual(resultado["evento_transicao"], evento)
            self.assertIs(
                resultado["status_dependente_final"],
                status_final,
            )


if __name__ == "__main__":
    unittest.main()
