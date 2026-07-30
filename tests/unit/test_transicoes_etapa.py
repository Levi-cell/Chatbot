import unittest

from core.repositories.fluxo import transicoes as transicoes_etapa
from tests.helpers import FakeCursor
from workers.worker_flow.response_flow.transicoes.contexto_transicao import (
    montar_contexto_transicao,
    prever_etapa_resposta,
)
from workers.worker_flow.response_flow.transicoes.eventos import (
    ETAPA_19_DECISAO_COMENTARIO,
    ETAPA_20_COMENTARIO_SATISFACAO,
    ETAPA_21_FINALIZACAO,
    ETAPA_2_DESTINO_ATENDIMENTO,
    ETAPA_3_PROFISSAO,
    ETAPA_4_NOME_DEPENDENTE,
    ETAPA_5_IDADE_ALUNO,
    ETAPA_6_OFERTA_AULA,
    EVENTO_DESTINO_ATENDIMENTO_DEFINIDO,
    EVENTO_COMENTARIO_SATISFACAO_ACEITO,
    EVENTO_COMENTARIO_SATISFACAO_RECEBIDO,
    EVENTO_COMENTARIO_SATISFACAO_RECUSADO,
    EVENTO_IDADE_VALIDA,
    EVENTO_NOME_DEPENDENTE_VALIDO,
    EVENTO_PROFISSAO_DEPENDENTE_VALIDA,
    EVENTO_PROFISSAO_TITULAR_VALIDA,
)
from workers.worker_flow.response_flow.transicoes.resolver_transicao import (
    TransicaoEtapaInvalida,
    anexar_transicao_ao_contexto_envio,
    identificar_evento_por_destino,
    resolver_destino_transicao,
)


def contexto_transicao_etapa2():
    return {
        "id_etapa_origem_transicao": ETAPA_2_DESTINO_ATENDIMENTO,
        "transicoes_permitidas": {
            EVENTO_DESTINO_ATENDIMENTO_DEFINIDO: ETAPA_3_PROFISSAO,
        },
    }


def contexto_transicao_etapa3():
    return {
        "id_etapa_origem_transicao": ETAPA_3_PROFISSAO,
        "transicoes_permitidas": {
            EVENTO_PROFISSAO_DEPENDENTE_VALIDA: ETAPA_4_NOME_DEPENDENTE,
            EVENTO_PROFISSAO_TITULAR_VALIDA: ETAPA_5_IDADE_ALUNO,
        },
    }


def contexto_transicao_etapa4():
    return {
        "id_etapa_origem_transicao": ETAPA_4_NOME_DEPENDENTE,
        "transicoes_permitidas": {
            EVENTO_NOME_DEPENDENTE_VALIDO: ETAPA_5_IDADE_ALUNO,
        },
    }


def contexto_transicao_etapa5():
    return {
        "id_etapa_origem_transicao": ETAPA_5_IDADE_ALUNO,
        "transicoes_permitidas": {
            EVENTO_IDADE_VALIDA: ETAPA_6_OFERTA_AULA,
        },
    }


def contexto_transicao_etapa19():
    return {
        "id_etapa_origem_transicao": ETAPA_19_DECISAO_COMENTARIO,
        "transicoes_permitidas": {
            EVENTO_COMENTARIO_SATISFACAO_ACEITO: (
                ETAPA_20_COMENTARIO_SATISFACAO
            ),
            EVENTO_COMENTARIO_SATISFACAO_RECUSADO: ETAPA_21_FINALIZACAO,
        },
    }


def contexto_transicao_etapa20():
    return {
        "id_etapa_origem_transicao": ETAPA_20_COMENTARIO_SATISFACAO,
        "transicoes_permitidas": {
            EVENTO_COMENTARIO_SATISFACAO_RECEBIDO: ETAPA_21_FINALIZACAO,
        },
    }


class TransicoesEtapaTests(unittest.TestCase):
    def test_resultado_da_consulta_vira_contexto_explicito(self):
        transicoes = {
            EVENTO_DESTINO_ATENDIMENTO_DEFINIDO: ETAPA_3_PROFISSAO,
        }

        resultado = montar_contexto_transicao(
            ETAPA_2_DESTINO_ATENDIMENTO,
            transicoes,
        )

        self.assertEqual(
            resultado,
            {
                "id_etapa_origem_transicao": ETAPA_2_DESTINO_ATENDIMENTO,
                "transicoes_permitidas": transicoes,
            },
        )
        self.assertIsNot(
            resultado["transicoes_permitidas"],
            transicoes,
        )

    def test_previsao_da_etapa2_aponta_para_profissao(self):
        resultado = prever_etapa_resposta(
            ETAPA_2_DESTINO_ATENDIMENTO,
            {
                EVENTO_DESTINO_ATENDIMENTO_DEFINIDO: ETAPA_3_PROFISSAO,
            },
            etapa_inicial=1,
        )

        self.assertEqual(resultado, ETAPA_3_PROFISSAO)

    def test_previsao_nao_escolhe_entre_os_ramos_da_profissao(self):
        resultado = prever_etapa_resposta(
            ETAPA_3_PROFISSAO,
            contexto_transicao_etapa3()["transicoes_permitidas"],
            etapa_inicial=1,
        )

        self.assertIsNone(resultado)

    def test_repositorio_carrega_eventos_e_destinos(self):
        cursor = FakeCursor(
            fetchall_result=[
                (
                    EVENTO_DESTINO_ATENDIMENTO_DEFINIDO,
                    ETAPA_3_PROFISSAO,
                ),
            ]
        )

        resultado = transicoes_etapa.listar_transicoes_permitidas(
            ETAPA_2_DESTINO_ATENDIMENTO,
            cursor,
        )

        self.assertEqual(
            resultado,
            {
                EVENTO_DESTINO_ATENDIMENTO_DEFINIDO: ETAPA_3_PROFISSAO,
            },
        )
        sql, params = cursor.calls[0]
        self.assertIn("FROM chatbot.etapa_transicao", sql)
        self.assertIn("WHERE id_etapa_origem = %s", sql)
        self.assertEqual(params, (ETAPA_2_DESTINO_ATENDIMENTO,))

    def test_destino_definido_resolve_profissao(self):
        destino = resolver_destino_transicao(
            contexto_transicao_etapa2(),
            EVENTO_DESTINO_ATENDIMENTO_DEFINIDO,
            destinos_esperados={ETAPA_3_PROFISSAO},
        )

        self.assertEqual(destino, ETAPA_3_PROFISSAO)

    def test_profissao_dependente_resolve_nome_dependente(self):
        destino = resolver_destino_transicao(
            contexto_transicao_etapa3(),
            EVENTO_PROFISSAO_DEPENDENTE_VALIDA,
            destinos_esperados={ETAPA_4_NOME_DEPENDENTE},
        )

        self.assertEqual(destino, ETAPA_4_NOME_DEPENDENTE)

    def test_profissao_titular_resolve_idade(self):
        destino = resolver_destino_transicao(
            contexto_transicao_etapa3(),
            EVENTO_PROFISSAO_TITULAR_VALIDA,
            destinos_esperados={ETAPA_5_IDADE_ALUNO},
        )

        self.assertEqual(destino, ETAPA_5_IDADE_ALUNO)

    def test_nome_dependente_valido_resolve_idade(self):
        destino = resolver_destino_transicao(
            contexto_transicao_etapa4(),
            EVENTO_NOME_DEPENDENTE_VALIDO,
            destinos_esperados={ETAPA_5_IDADE_ALUNO},
        )

        self.assertEqual(destino, ETAPA_5_IDADE_ALUNO)

    def test_idade_valida_resolve_oferta(self):
        destino = resolver_destino_transicao(
            contexto_transicao_etapa5(),
            EVENTO_IDADE_VALIDA,
            destinos_esperados={ETAPA_6_OFERTA_AULA},
        )

        self.assertEqual(destino, ETAPA_6_OFERTA_AULA)

    def test_decisao_de_comentario_resolve_os_dois_ramos(self):
        casos = (
            (
                EVENTO_COMENTARIO_SATISFACAO_ACEITO,
                ETAPA_20_COMENTARIO_SATISFACAO,
            ),
            (
                EVENTO_COMENTARIO_SATISFACAO_RECUSADO,
                ETAPA_21_FINALIZACAO,
            ),
        )

        for evento, destino_esperado in casos:
            with self.subTest(evento=evento):
                destino = resolver_destino_transicao(
                    contexto_transicao_etapa19(),
                    evento,
                    destinos_esperados={destino_esperado},
                )
                self.assertEqual(destino, destino_esperado)

    def test_comentario_recebido_resolve_finalizacao(self):
        destino = resolver_destino_transicao(
            contexto_transicao_etapa20(),
            EVENTO_COMENTARIO_SATISFACAO_RECEBIDO,
            destinos_esperados={ETAPA_21_FINALIZACAO},
        )

        self.assertEqual(destino, ETAPA_21_FINALIZACAO)

    def test_evento_ausente_e_recusado_antes_do_envio(self):
        with self.assertRaises(TransicaoEtapaInvalida):
            resolver_destino_transicao(
                contexto_transicao_etapa2(),
                "evento_inventado",
            )

    def test_destino_trocado_no_seed_e_recusado(self):
        contexto = contexto_transicao_etapa2()
        contexto["transicoes_permitidas"][
            EVENTO_DESTINO_ATENDIMENTO_DEFINIDO
        ] = ETAPA_4_NOME_DEPENDENTE

        with self.assertRaises(TransicaoEtapaInvalida):
            resolver_destino_transicao(
                contexto,
                EVENTO_DESTINO_ATENDIMENTO_DEFINIDO,
                destinos_esperados={ETAPA_3_PROFISSAO},
            )

    def test_sender_nao_pode_retornar_destino_diferente(self):
        with self.assertRaises(TransicaoEtapaInvalida):
            anexar_transicao_ao_contexto_envio(
                contexto_transicao_etapa2(),
                {
                    "id_etapa_resultante": ETAPA_4_NOME_DEPENDENTE,
                    "enviou": True,
                },
                EVENTO_DESTINO_ATENDIMENTO_DEFINIDO,
                ETAPA_3_PROFISSAO,
            )

    def test_tratamento_nao_pode_carregar_evento(self):
        with self.assertRaises(TransicaoEtapaInvalida):
            anexar_transicao_ao_contexto_envio(
                contexto_transicao_etapa2(),
                {
                    "id_etapa_resultante": ETAPA_3_PROFISSAO,
                    "enviou": True,
                    "tratamento": True,
                },
                EVENTO_DESTINO_ATENDIMENTO_DEFINIDO,
                ETAPA_3_PROFISSAO,
            )

    def test_retry_da_etapa2_reconstroi_evento_unico(self):
        evento = identificar_evento_por_destino(
            contexto_transicao_etapa2(),
            ETAPA_3_PROFISSAO,
        )

        self.assertEqual(evento, EVENTO_DESTINO_ATENDIMENTO_DEFINIDO)

    def test_retry_da_profissao_reconstroi_cada_evento_pelo_destino(self):
        casos = (
            (
                ETAPA_4_NOME_DEPENDENTE,
                EVENTO_PROFISSAO_DEPENDENTE_VALIDA,
            ),
            (ETAPA_5_IDADE_ALUNO, EVENTO_PROFISSAO_TITULAR_VALIDA),
        )

        for destino, esperado in casos:
            with self.subTest(destino=destino):
                evento = identificar_evento_por_destino(
                    contexto_transicao_etapa3(),
                    destino,
                )
                self.assertEqual(evento, esperado)

    def test_retry_da_decisao_reconstroi_evento_por_destino(self):
        casos = (
            (
                ETAPA_20_COMENTARIO_SATISFACAO,
                EVENTO_COMENTARIO_SATISFACAO_ACEITO,
            ),
            (
                ETAPA_21_FINALIZACAO,
                EVENTO_COMENTARIO_SATISFACAO_RECUSADO,
            ),
        )

        for destino, esperado in casos:
            with self.subTest(destino=destino):
                evento = identificar_evento_por_destino(
                    contexto_transicao_etapa19(),
                    destino,
                )
                self.assertEqual(evento, esperado)

    def test_resposta_na_mesma_etapa_nao_inventa_transicao(self):
        evento = identificar_evento_por_destino(
            contexto_transicao_etapa2(),
            ETAPA_2_DESTINO_ATENDIMENTO,
        )

        self.assertIsNone(evento)


if __name__ == "__main__":
    unittest.main()
