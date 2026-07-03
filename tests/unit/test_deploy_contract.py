import inspect
import unittest

from core.database.deploy import (
    bank_script,
    etapa_transicao_script,
    povoar_etapas,
    setup_database,
)
from workers.worker_flow.response_flow.transicoes.eventos import (
    EVENTO_AGENDAMENTO_FINALIZADO,
    EVENTO_CLIENTE_RETORNOU,
    EVENTO_EMAIL_VALIDO,
    EVENTO_IDADE_VALIDA,
    EVENTO_NOME_CLIENTE_VALIDO,
    EVENTO_NOME_DEPENDENTE_VALIDO,
    EVENTO_OFERTA_ACEITA,
    EVENTO_OFERTA_ADIADA,
    EVENTO_PARA_MIM,
    EVENTO_PARA_OUTRA_PESSOA,
    EVENTO_RETORNO_ADIADO,
    EVENTO_RETORNO_CONFIRMADO,
)


class DeployContractTests(unittest.TestCase):
    def test_banco_novo_nasce_com_last_error_sem_alterar_banco(self):
        source = inspect.getsource(bank_script.criar_tabelas)

        self.assertIn("last_error TEXT", source)
        self.assertFalse(hasattr(bank_script, "alterar_banco"))

    def test_setup_nao_chama_migracao_historica_alterar_banco(self):
        source = inspect.getsource(setup_database.setup_database_aws)

        self.assertNotIn("alterar_banco", source)
        self.assertIn("criar_tabelas()", source)

    def test_respostas_desafios_existe_no_ddl_com_unique_turno(self):
        source = inspect.getsource(bank_script.criar_tabelas)

        self.assertIn("CREATE TABLE IF NOT EXISTS chatbot.respostas_desafios", source)
        self.assertIn("UNIQUE (id_conversa, id_etapa)", source)
        self.assertIn("id_historico_mensagem_cliente INT NULL", source)

    def test_cliente_e_dependente_possuem_idade_e_conversa_vinculada(self):
        source = inspect.getsource(bank_script.criar_tabelas)

        self.assertIn("ADD COLUMN IF NOT EXISTS idade INTEGER", source)
        self.assertIn("ADD COLUMN IF NOT EXISTS id_conversa INT", source)
        self.assertIn("dependente_id_conversa_fkey", source)
        self.assertIn("uq_dependente_conversa", source)
        self.assertNotIn("telefone_dependente VARCHAR", source)
        self.assertNotIn("email_dependente VARCHAR", source)
        self.assertIn("DROP COLUMN IF EXISTS telefone_dependente", source)
        self.assertIn("DROP COLUMN IF EXISTS email_dependente", source)

    def test_unidade_possui_instagram_e_bootstrap_da_unidade_saj(self):
        source = inspect.getsource(bank_script.criar_tabelas)

        self.assertIn("link_instagram VARCHAR(400)", source)
        self.assertIn(
            "ADD COLUMN IF NOT EXISTS link_instagram VARCHAR(400)",
            source,
        )
        self.assertIn(
            "https://www.instagram.com/supera.saj/",
            source,
        )

    def test_etapa_possui_politicas_escalaveis(self):
        source = inspect.getsource(bank_script.criar_tabelas)

        self.assertIn("encerra_automaticamente BOOLEAN", source)
        self.assertIn("bloqueio_dias INTEGER", source)
        self.assertIn("elegivel_funil BOOLEAN", source)
        self.assertIn("ck_etapa_bloqueio_dias", source)
        self.assertIn("idx_conversa_funil_pendente", source)
        self.assertIn("WHERE id_etapa = 7", source)
        self.assertIn(
            "'Atendimento finalizado e entrada no funil'",
            source,
        )

    def test_seed_possui_dez_etapas_e_bloqueia_somente_na_etapa_10(self):
        etapa_final = povoar_etapas.ETAPAS[-1]

        self.assertEqual(
            [etapa[0] for etapa in povoar_etapas.ETAPAS],
            list(range(1, 11)),
        )
        self.assertEqual(etapa_final[0], 10)
        self.assertTrue(etapa_final[2])
        self.assertEqual(etapa_final[3], 30)
        self.assertTrue(etapa_final[4])
        self.assertTrue(
            all(
                not encerra and dias == 0 and not funil
                for (
                    _id,
                    _nome,
                    encerra,
                    dias,
                    funil,
                ) in povoar_etapas.ETAPAS[:-1]
            )
        )

    def test_tabela_transicao_possui_restricoes_de_seguranca(self):
        source = inspect.getsource(
            etapa_transicao_script.criar_e_povoar_transicoes_etapa
        )

        self.assertIn("CHECK (id_etapa_origem <> id_etapa_destino)", source)
        self.assertIn("UNIQUE (id_etapa_origem, evento)", source)
        self.assertIn(
            "UNIQUE (id_etapa_origem, id_etapa_destino)",
            source,
        )
        self.assertIn(
            "TRUNCATE TABLE chatbot.etapa_transicao RESTART IDENTITY",
            source,
        )

    def test_seed_de_transicoes_reflete_o_mapa_atual(self):
        self.assertEqual(
            etapa_transicao_script.TRANSICOES_INICIAIS,
            (
                (1, EVENTO_NOME_CLIENTE_VALIDO, 2),
                (2, EVENTO_PARA_MIM, 4),
                (2, EVENTO_PARA_OUTRA_PESSOA, 3),
                (3, EVENTO_NOME_DEPENDENTE_VALIDO, 4),
                (4, EVENTO_IDADE_VALIDA, 5),
                (5, EVENTO_OFERTA_ACEITA, 8),
                (5, EVENTO_OFERTA_ADIADA, 6),
                (6, EVENTO_CLIENTE_RETORNOU, 7),
                (7, EVENTO_RETORNO_CONFIRMADO, 8),
                (7, EVENTO_RETORNO_ADIADO, 6),
                (8, EVENTO_EMAIL_VALIDO, 9),
                (9, EVENTO_AGENDAMENTO_FINALIZADO, 10),
            ),
        )


if __name__ == "__main__":
    unittest.main()
