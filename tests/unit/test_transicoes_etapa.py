import unittest

from core.repositories import transicoes_etapa
from tests.helpers import FakeCursor
from workers.worker_flow.response_flow.transicoes.contexto_transicao import (
    montar_contexto_transicao,
    prever_etapa_resposta,
)
from workers.worker_flow.response_flow.transicoes.eventos import (
    ETAPA_3_NOME_DEPENDENTE,
    ETAPA_4_IDADE_ALUNO,
    ETAPA_5_OFERTA_AULA,
    EVENTO_IDADE_VALIDA,
    EVENTO_NOME_DEPENDENTE_VALIDO,
    EVENTO_PARA_MIM,
    EVENTO_PARA_OUTRA_PESSOA,
)
from workers.worker_flow.response_flow.transicoes.resolver_transicao import (
    TransicaoEtapaInvalida,
    anexar_transicao_ao_contexto_envio,
    identificar_evento_por_destino,
    resolver_destino_transicao,
)


def contexto_transicoes():
    return {
        "id_etapa_origem_transicao": 2,
        "transicoes_permitidas": {
            EVENTO_PARA_MIM: ETAPA_4_IDADE_ALUNO,
            EVENTO_PARA_OUTRA_PESSOA: ETAPA_3_NOME_DEPENDENTE,
        },
    }


def contexto_transicao_etapa3():
    return {
        "id_etapa_origem_transicao": ETAPA_3_NOME_DEPENDENTE,
        "transicoes_permitidas": {
            EVENTO_NOME_DEPENDENTE_VALIDO: ETAPA_4_IDADE_ALUNO,
        },
    }


def contexto_transicao_etapa4():
    return {
        "id_etapa_origem_transicao": ETAPA_4_IDADE_ALUNO,
        "transicoes_permitidas": {
            EVENTO_IDADE_VALIDA: ETAPA_5_OFERTA_AULA,
        },
    }


class TransicoesEtapaTests(unittest.TestCase):
    def test_resultado_da_consulta_vira_contexto_explicito(self):
        transicoes = {
            EVENTO_PARA_MIM: ETAPA_4_IDADE_ALUNO,
            EVENTO_PARA_OUTRA_PESSOA: ETAPA_3_NOME_DEPENDENTE,
        }

        resultado = montar_contexto_transicao(2, transicoes)

        self.assertEqual(
            resultado,
            {
                "id_etapa_origem_transicao": 2,
                "transicoes_permitidas": transicoes,
            },
        )
        self.assertIsNot(
            resultado["transicoes_permitidas"],
            transicoes,
        )

    def test_previsao_nao_escolhe_entre_multiplos_destinos(self):
        resultado = prever_etapa_resposta(
            2,
            {
                EVENTO_PARA_MIM: ETAPA_4_IDADE_ALUNO,
                EVENTO_PARA_OUTRA_PESSOA: ETAPA_3_NOME_DEPENDENTE,
            },
            etapa_inicial=1,
        )

        self.assertIsNone(resultado)

    def test_repositorio_carrega_eventos_e_destinos(self):
        cursor = FakeCursor(
            fetchall_result=[
                (EVENTO_PARA_MIM, ETAPA_4_IDADE_ALUNO),
                (
                    EVENTO_PARA_OUTRA_PESSOA,
                    ETAPA_3_NOME_DEPENDENTE,
                ),
            ]
        )

        resultado = transicoes_etapa.listar_transicoes_permitidas(
            2,
            cursor,
        )

        self.assertEqual(
            resultado,
            {
                EVENTO_PARA_MIM: ETAPA_4_IDADE_ALUNO,
                EVENTO_PARA_OUTRA_PESSOA: ETAPA_3_NOME_DEPENDENTE,
            },
        )
        sql, params = cursor.calls[0]
        self.assertIn("FROM chatbot.etapa_transicao", sql)
        self.assertIn("WHERE id_etapa_origem = %s", sql)
        self.assertEqual(params, (2,))

    def test_para_mim_resolve_etapa4(self):
        destino = resolver_destino_transicao(
            contexto_transicoes(),
            EVENTO_PARA_MIM,
            destinos_esperados={ETAPA_4_IDADE_ALUNO},
        )

        self.assertEqual(destino, ETAPA_4_IDADE_ALUNO)

    def test_para_outra_pessoa_resolve_etapa3(self):
        destino = resolver_destino_transicao(
            contexto_transicoes(),
            EVENTO_PARA_OUTRA_PESSOA,
            destinos_esperados={ETAPA_3_NOME_DEPENDENTE},
        )

        self.assertEqual(destino, ETAPA_3_NOME_DEPENDENTE)

    def test_nome_dependente_valido_resolve_etapa4(self):
        destino = resolver_destino_transicao(
            contexto_transicao_etapa3(),
            EVENTO_NOME_DEPENDENTE_VALIDO,
            destinos_esperados={ETAPA_4_IDADE_ALUNO},
        )

        self.assertEqual(destino, ETAPA_4_IDADE_ALUNO)

    def test_idade_valida_resolve_etapa5(self):
        destino = resolver_destino_transicao(
            contexto_transicao_etapa4(),
            EVENTO_IDADE_VALIDA,
            destinos_esperados={ETAPA_5_OFERTA_AULA},
        )

        self.assertEqual(destino, ETAPA_5_OFERTA_AULA)

    def test_evento_ausente_e_recusado_antes_do_envio(self):
        with self.assertRaises(TransicaoEtapaInvalida):
            resolver_destino_transicao(
                contexto_transicoes(),
                "evento_inventado",
            )

    def test_destino_trocado_no_seed_e_recusado(self):
        contexto = contexto_transicoes()
        contexto["transicoes_permitidas"][EVENTO_PARA_MIM] = 3

        with self.assertRaises(TransicaoEtapaInvalida):
            resolver_destino_transicao(
                contexto,
                EVENTO_PARA_MIM,
                destinos_esperados={ETAPA_4_IDADE_ALUNO},
            )

    def test_sender_nao_pode_retornar_destino_diferente(self):
        with self.assertRaises(TransicaoEtapaInvalida):
            anexar_transicao_ao_contexto_envio(
                contexto_transicoes(),
                {
                    "id_etapa_resultante": 3,
                    "enviou": True,
                },
                EVENTO_PARA_MIM,
                ETAPA_4_IDADE_ALUNO,
            )

    def test_tratamento_nao_pode_carregar_evento(self):
        with self.assertRaises(TransicaoEtapaInvalida):
            anexar_transicao_ao_contexto_envio(
                contexto_transicoes(),
                {
                    "id_etapa_resultante": ETAPA_4_IDADE_ALUNO,
                    "enviou": True,
                    "tratamento": True,
                },
                EVENTO_PARA_MIM,
                ETAPA_4_IDADE_ALUNO,
            )

    def test_retry_reconstroi_evento_pelo_destino(self):
        evento = identificar_evento_por_destino(
            contexto_transicoes(),
            ETAPA_4_IDADE_ALUNO,
        )

        self.assertEqual(evento, EVENTO_PARA_MIM)

    def test_resposta_na_mesma_etapa_nao_inventa_transicao(self):
        evento = identificar_evento_por_destino(
            contexto_transicoes(),
            2,
        )

        self.assertIsNone(evento)


if __name__ == "__main__":
    unittest.main()
