import inspect
import unittest

from core.database.deploy import bank_script, setup_database


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


if __name__ == "__main__":
    unittest.main()
