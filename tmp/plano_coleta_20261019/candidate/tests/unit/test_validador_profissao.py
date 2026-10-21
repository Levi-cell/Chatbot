import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from core.integrations.whatsapp.pywa_functions import cliente
from tests.unit import test_followup as fixtures
from workers.worker_flow.response_flow.flow_sender import flow_sender
from workers.worker_flow.response_flow.retomada_followup import enviar_retorno_followup
from workers.worker_flow.response_flow.etapas import resolver_etapa4
from workers.worker_flow.response_flow.etapas.validadores_contexto.valida_etapa4 import (
    MOTIVO_PROFISSAO_FORA_CONTEXTO,
    validar_profissao_etapa4,
)


RESPOSTAS_FORA_CONTEXTO_OBSERVADAS = (
    "Pra minha filha na verdade",
    "Não entendi",
    "Para meu filho",
    "Pra meu filho",
    (
        "Minha filha é autista e percebo q ela tem dificuldade no "
        "aprendizado , vcs atende autista tambem"
    ),
    "não seria pra meu filho",
    "Meu filho",
    "Vc ouviu áudio ou ligação",
)


class ValidadorProfissaoTests(unittest.TestCase):
    def test_abertura_profissao_usa_rota_confirmada_em_entradas_e_retornos(self):
        for retorno in (None, "inatividade", "followup"):
            for dependente in (False, True):
                for resposta in ("Sim", "Não"):
                    with self.subTest(
                        retorno=retorno, dependente=dependente, resposta=resposta
                    ):
                        contexto, _ = fixtures.RetornoTests().preparar(
                            etapa=3, texto=resposta, dependente=dependente
                        )
                        prefixo = (
                            "Bom te ver novamente, Ana ☺️\n\n" if retorno else ""
                        )
                        if retorno != "followup":
                            contexto.pop("retorno_followup")
                            contexto["saudacao_retorno"] = prefixo or None

                        wa = MagicMock()
                        wa.send_message.return_value = SimpleNamespace(
                            id="wamid.bot"
                        )
                        with patch.object(cliente, "WhatsApp", return_value=wa):
                            envio = (
                                enviar_retorno_followup(contexto)
                                if retorno == "followup"
                                else flow_sender(contexto)
                            )

                        rota_final = (
                            dependente if resposta == "Sim" else not dependente
                        )
                        texto = envio["mensagem_bot"]
                        wa.send_message.assert_called_once()
                        self.assertEqual(
                            texto, wa.send_message.call_args.kwargs["text"]
                        )
                        self.assertTrue(
                            texto.startswith(prefixo + "Olha, antes de continuar")
                        )
                        self.assertEqual(
                            texto.count("Bom te ver novamente"), bool(retorno)
                        )
                        self.assertEqual(
                            texto.count("vou precisar fazer algumas perguntas"), 1
                        )
                        self.assertIn("sua *profissão*", texto)
                        self.assertEqual(
                            "perfil da outra pessoa" in texto, rota_final
                        )
                        self.assertEqual(envio["status_dependente_final"], rota_final)
                        self.assertEqual(envio["id_etapa_resultante"], 4)

    def test_rejeita_somente_respostas_fora_contexto_ja_observadas(self):
        for resposta in RESPOSTAS_FORA_CONTEXTO_OBSERVADAS:
            with self.subTest(resposta=resposta):
                resultado = validar_profissao_etapa4(resposta)

                self.assertFalse(resultado.valida)
                self.assertIsNone(resultado.profissao)
                self.assertEqual(
                    resultado.motivo,
                    MOTIVO_PROFISSAO_FORA_CONTEXTO,
                )

    def test_normalizacao_cobre_caixa_acentos_pontuacao_e_espacos(self):
        resultado = validar_profissao_etapa4(
            "  VC   OUVIU ÁUDIO OU LIGAÇÃO???  "
        )

        self.assertFalse(resultado.valida)
        self.assertEqual(
            resultado.motivo,
            MOTIVO_PROFISSAO_FORA_CONTEXTO,
        )

    def test_nao_bloqueia_profissoes_legitimas_com_palavras_semelhantes(self):
        profissoes_validas = (
            "Lavradora",
            "Autonona",
            "Técnica de áudio",
            "Faço ligações, trabalho com telemarketing",
            "Trabalho para meu filho",
            "Sou psicopedagoga e minha filha é autista",
            "Não entendi antes; sou professora",
            "Sou psicóloga, mas é para minha filha de 16 anos",
        )

        for profissao in profissoes_validas:
            with self.subTest(profissao=profissao):
                resultado = validar_profissao_etapa4(profissao)

                self.assertTrue(resultado.valida)
                self.assertEqual(resultado.profissao, profissao)
                self.assertIsNone(resultado.motivo)

    def test_resolver_repete_etapa_sem_transicionar_ou_persistir_profissao(self):
        contexto = {
            "id_conversa": 121,
            "id_etapa_cliente": 4,
            "tipo_mensagem_atual": "text",
            "texto_cliente_atual": "Vc ouviu áudio ou ligação",
            "status_dependente": False,
            "mensagem_cliente_atual": {
                "id_mensagem_fila": 9001,
                "cliente_telefone": "5571999999999",
                "id_phone_unidade": "123456",
            },
        }
        resposta_repeticao = {
            "id_etapa_resultante": 4,
            "tratamento": True,
            "tipo_tratamento": "profissao_invalida",
        }

        with (
            patch.object(
                resolver_etapa4,
                "enviar_etapa4_contexto_profissao_invalida",
                return_value=resposta_repeticao,
            ) as enviar_repeticao,
            patch.object(
                resolver_etapa4,
                "resolver_destino_transicao",
            ) as resolver_transicao,
        ):
            resultado = resolver_etapa4.resolve_etapa4(contexto)

        self.assertIs(resultado, resposta_repeticao)
        enviar_repeticao.assert_called_once_with(
            "5571999999999",
            "123456",
        )
        resolver_transicao.assert_not_called()
        self.assertNotIn("profissao", resultado)


if __name__ == "__main__":
    unittest.main()
