import unittest
from unittest.mock import patch

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
