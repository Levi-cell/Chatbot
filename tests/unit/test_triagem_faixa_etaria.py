import importlib
import unittest
from unittest.mock import patch

from core.repositories.fluxo.contextos.triagem import (
    buscar_contexto_triagem,
)
from core.triagem.perguntas import (
    FAIXA_ETARIA_ADULTA,
    FAIXA_ETARIA_INFANTIL,
    montar_pergunta_triagem,
    obter_faixa_etaria_triagem,
)
from workers.worker_flow import valida_historico


PERGUNTAS_INFANTIS = (
    "Com que frequência Ana se distrai com facilidade durante tarefas "
    "ou atividades escolares?",
    "Com que frequência Ana tem dificuldade para concluir uma atividade "
    "que começou?",
    "Com que frequência Ana esquece orientações ou "
    "conteúdos que acabou de aprender?",
    "Com que frequência Ana precisa que as instruções sejam repetidas "
    "várias vezes para conseguir realizá-las?",
    "Com que frequência Ana passa mais de 4h por dia em frente a telas "
    "(celular, tablet ou TV)?",
    "Com que frequência Ana fica desmotivado(a), impaciente ou "
    "frustrado(a) diante de atividades que exigem concentração?",
)

PERGUNTAS_ADULTAS_TITULAR = (
    "Com que frequência você esquece compromissos, recados ou onde "
    "guardou objetos pessoais?",
    "Com que frequência você tem dificuldade para lembrar nomes, "
    "palavras ou informações recentes?",
    "Com que frequência você se distrai com facilidade durante "
    "conversas, leituras ou atividades do dia a dia?",
    "Com que frequência você tem dificuldade para manter a concentração "
    "e concluir uma tarefa que começou?",
    "Com que frequência você se sente ansioso(a), preocupado(a) ou com "
    "a mente muito acelerada?",
    "Com que frequência você tem dificuldade para dormir?",
)


class _CursorFake:
    def __init__(self, resultado):
        self.resultado = resultado
        self.calls = []

    def execute(self, sql, parametros):
        self.calls.append((sql, parametros))

    def fetchone(self):
        return self.resultado


def _mensagem_worker():
    return {
        "id_mensagem": 20,
        "cliente_telefone": "5571999999999",
        "conteudo_texto": "Iniciar triagem",
        "tipo_mensagem": "text",
        "id_phone_unidade": "phone-id",
        "unidade_telefone": "5571000000000",
        "id_hash": "wamid.cliente",
        "retry_count": 1,
    }


def _contexto_banco(*, dependente, etapa=11):
    return {
        "id_cliente": 7,
        "id_unidade": 3,
        "conversa": {
            "id_conversa": 10,
            "id_etapa_atual": etapa,
            "status_dependente": dependente,
            "last_message_from": "bot",
        },
    }


class TriagemFaixaEtariaTests(unittest.TestCase):
    def test_catalogo_infantil_tem_as_seis_perguntas_canonicas(self):
        perguntas = tuple(
            montar_pergunta_triagem(
                id_etapa,
                faixa_etaria=FAIXA_ETARIA_INFANTIL,
                nome_pessoa="Ana",
            )
            for id_etapa in range(12, 18)
        )

        self.assertEqual(perguntas, PERGUNTAS_INFANTIS)

    def test_catalogo_adulto_titular_tem_as_seis_perguntas_canonicas(self):
        perguntas = tuple(
            montar_pergunta_triagem(
                id_etapa,
                faixa_etaria=FAIXA_ETARIA_ADULTA,
            )
            for id_etapa in range(12, 18)
        )

        self.assertEqual(perguntas, PERGUNTAS_ADULTAS_TITULAR)

    def test_dependente_adulto_usa_o_nome_em_todas_as_perguntas(self):
        for id_etapa, pergunta_titular in zip(
            range(12, 18),
            PERGUNTAS_ADULTAS_TITULAR,
        ):
            with self.subTest(id_etapa=id_etapa):
                pergunta = montar_pergunta_triagem(
                    id_etapa,
                    faixa_etaria=FAIXA_ETARIA_ADULTA,
                    nome_pessoa="João",
                )
                self.assertEqual(
                    pergunta,
                    pergunta_titular.replace("você", "João", 1),
                )

    def test_limites_etarios_selecionam_a_variante_correta(self):
        for idade in (4, 5, 17):
            with self.subTest(idade=idade):
                self.assertEqual(
                    obter_faixa_etaria_triagem(idade),
                    FAIXA_ETARIA_INFANTIL,
                )

        for idade in (18, 60, 99):
            with self.subTest(idade=idade):
                self.assertEqual(
                    obter_faixa_etaria_triagem(idade),
                    FAIXA_ETARIA_ADULTA,
                )

        for idade in (None, True, 0, -1, 100, "18"):
            with self.subTest(idade=idade):
                with self.assertRaises(ValueError):
                    obter_faixa_etaria_triagem(idade)

    def test_triagem_infantil_exige_nome_persistido(self):
        with self.assertRaisesRegex(ValueError, "Nome da pessoa"):
            montar_pergunta_triagem(
                12,
                faixa_etaria=FAIXA_ETARIA_INFANTIL,
            )

    def test_messages_12_a_17_usam_o_mesmo_catalogo_por_idade(self):
        for id_etapa in range(12, 18):
            modulo = importlib.import_module(
                "core.integrations.whatsapp.messages."
                f"etapa{id_etapa}_messages"
            )
            montar_cliente = getattr(
                modulo,
                f"montar_mensagem_cliente_etapa{id_etapa}",
            )
            montar_dependente = getattr(
                modulo,
                f"montar_mensagem_dependente_etapa{id_etapa}",
            )
            montar_repeticao_dependente = getattr(
                modulo,
                "montar_mensagem_dependente_contexto_invalido_"
                f"etapa{id_etapa}",
            )

            with self.subTest(id_etapa=id_etapa):
                self.assertEqual(
                    montar_cliente(),
                    PERGUNTAS_ADULTAS_TITULAR[id_etapa - 12],
                )
                self.assertEqual(
                    montar_dependente("Ana", 17),
                    PERGUNTAS_INFANTIS[id_etapa - 12],
                )
                pergunta_adulta = PERGUNTAS_ADULTAS_TITULAR[
                    id_etapa - 12
                ].replace("você", "Ana", 1)
                self.assertEqual(
                    montar_dependente("Ana", 18),
                    pergunta_adulta,
                )
                self.assertTrue(
                    montar_repeticao_dependente("Ana", 17).endswith(
                        PERGUNTAS_INFANTIS[id_etapa - 12]
                    )
                )

    def test_repositorio_rele_status_nome_e_idade_da_pessoa_atendida(self):
        cursor = _CursorFake((True, "Ana", 12))

        contexto = buscar_contexto_triagem(10, 3, cursor)

        self.assertEqual(
            contexto,
            {
                "status_dependente_contexto_triagem": True,
                "nome_dependente": "Ana",
                "idade_pessoa_triagem": 12,
            },
        )
        sql, parametros = cursor.calls[0]
        self.assertIn("WHEN c.status_dependente IS TRUE THEN d.idade", sql)
        self.assertIn("WHEN c.status_dependente IS FALSE THEN cl.idade", sql)
        self.assertEqual(parametros, (10, 3))

    def test_contexto_worker_aceita_titular_adulto_e_dependente_desde_quatro(self):
        casos = (
            (False, None, 18),
            (True, "Ana", 4),
            (True, "João", 35),
        )

        for dependente, nome, idade in casos:
            with self.subTest(dependente=dependente, idade=idade):
                contexto = self._validar_contexto_worker(
                    dependente=dependente,
                    contexto_triagem={
                        "status_dependente_contexto_triagem": dependente,
                        "nome_dependente": nome,
                        "idade_pessoa_triagem": idade,
                    },
                )
                self.assertEqual(contexto["idade_pessoa_triagem"], idade)
                self.assertNotIn(
                    "status_dependente_contexto_triagem",
                    contexto,
                )

    def test_contexto_worker_falha_fechado_para_identidade_inconsistente(self):
        casos = (
            (
                False,
                {
                    "status_dependente_contexto_triagem": False,
                    "nome_dependente": None,
                    "idade_pessoa_triagem": 17,
                },
                "titular menor",
            ),
            (
                True,
                {
                    "status_dependente_contexto_triagem": True,
                    "nome_dependente": "Ana",
                    "idade_pessoa_triagem": 3,
                },
                "abaixo da idade",
            ),
            (
                True,
                {
                    "status_dependente_contexto_triagem": True,
                    "nome_dependente": " ",
                    "idade_pessoa_triagem": 12,
                },
                "sem nome persistido",
            ),
            (
                True,
                {
                    "status_dependente_contexto_triagem": False,
                    "nome_dependente": "Ana",
                    "idade_pessoa_triagem": 12,
                },
                "inconsistente",
            ),
        )

        for dependente, contexto_triagem, mensagem_erro in casos:
            with self.subTest(
                dependente=dependente,
                contexto_triagem=contexto_triagem,
            ):
                with self.assertRaisesRegex(ValueError, mensagem_erro):
                    self._validar_contexto_worker(
                        dependente=dependente,
                        contexto_triagem=contexto_triagem,
                    )

    def _validar_contexto_worker(self, *, dependente, contexto_triagem):
        with (
            patch.object(
                valida_historico,
                "inserir_historico_mensagem_cliente",
                return_value=(100, "2026-01-01T00:00:00", 11, True),
            ),
            patch.object(
                valida_historico,
                "buscar_resposta_bot_por_mensagem_cliente",
                return_value=None,
            ),
            patch.object(
                valida_historico,
                "listar_transicoes_permitidas",
                return_value={"triagem_iniciada": 12},
            ),
            patch.object(
                valida_historico,
                "buscar_contexto_triagem",
                return_value=contexto_triagem,
            ),
            patch.object(
                valida_historico,
                "atualizar_conversa_mensagem_cliente",
                return_value=1,
            ),
        ):
            return valida_historico.valida_historico(
                _mensagem_worker(),
                _contexto_banco(dependente=dependente),
                object(),
            )


if __name__ == "__main__":
    unittest.main()
