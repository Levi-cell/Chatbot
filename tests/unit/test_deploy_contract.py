import inspect
import unittest

from core.database.deploy import (
    bank_script,
    etapa_transicao_script,
    setup_database,
)
from workers.worker_flow.response_flow.transicoes.eventos import (
    EVENTO_NOME_CLIENTE_VALIDO,
    EVENTO_NOME_DEPENDENTE_VALIDO,
    EVENTO_PARA_MIM,
    EVENTO_PARA_OUTRA_PESSOA,
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
        self.assertIn("DELETE FROM chatbot.etapa_transicao", source)

    def test_seed_de_transicoes_reflete_o_mapa_da_v1(self):
        self.assertEqual(
            etapa_transicao_script.TRANSICOES_INICIAIS,
            (
                (1, EVENTO_NOME_CLIENTE_VALIDO, 2),
                (2, EVENTO_PARA_MIM, 4),
                (2, EVENTO_PARA_OUTRA_PESSOA, 3),
                (3, EVENTO_NOME_DEPENDENTE_VALIDO, 4),
            ),
        )


if __name__ == "__main__":
    unittest.main()
