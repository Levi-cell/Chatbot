"""Campos de formulário não passam pelas regras de respostas livres do chat."""

from tests.fixtures.fireads import como_aba_geral
import unittest

from core.integrations.fireads.extratores import extrair_email, extrair_nome
from core.integrations.whatsapp.messages.etapa4_messages import montar_abertura_fireads
from tests.unit.test_fireads import GOOGLE, META, NUMERO
from workers.worker_consulta_dash.resultado import interpretar
from workers.worker_flow.fireads import email_importado
from workers.worker_flow.transacoes.movimento_conversa import resolver_movimento_conversa


class ExtratoresFireAdsTests(unittest.TestCase):
    def test_nome_de_perfil_descarta_sobrenome_e_biografia(self):
        for recebido, esperado in (
            ("Edcarlos Oliveira | Programador", "Edcarlos"),
            ("  EDCARLOS\tOliveira | Programador  ", "Edcarlos"),
            ("Edcarlos 💻 Programador", "Edcarlos"),
            ("Zélia SobrenomeDesconhecido", "Zélia"),
            ("李 Silva", "李"),
            ("João Oliveira", "João"),
            ("Edcarlos|Programador", "Edcarlos|programador"),
        ):
            with self.subTest(recebido=recebido):
                self.assertEqual(extrair_nome(recebido), esperado)

    def test_composto_so_usa_par_conhecido_com_fallback_para_primeira_palavra(self):
        for recebido, esperado in (
            ("JOÃO PEDRO Silva | Programador", "João Pedro"),
            ("Joa\u0303o\u00a0Pedro Silva", "João Pedro"),
            ("Ana Paula Silva", "Ana Paula"),
            ("José Carlos de Souza", "José Carlos"),
            ("João | Pedro", "João"),
            ("João Nometeste Silva", "João"),
        ):
            with self.subTest(recebido=recebido):
                self.assertEqual(extrair_nome(recebido), esperado)

    def test_email_e_extraido_sem_validacao_estrutural_ou_de_dominio(self):
        for recebido, esperado in (
            ("  ANA+FORM@EXAMPLE.COM  ", "ana+form@example.com"),
            ("contato@intranet", "contato@intranet"),
            ("valor recebido no formulário", "valor recebido no formulário"),
        ):
            with self.subTest(recebido=recebido):
                self.assertEqual(extrair_email(recebido), esperado)

    def test_vazio_nao_inventa_nome_nem_email(self):
        for valor in (None, "", " \t\n\u00a0"):
            with self.subTest(valor=valor):
                self.assertIsNone(extrair_nome(valor))
                self.assertIsNone(extrair_email(valor))

    def test_validadores_de_respostas_livres_mantem_as_regras(self):
        from core.validacoes.email import validar_email_estrutural
        from workers.worker_flow.response_flow.etapas.validadores_universais.validador_nome import (
            validar_nome_cliente,
        )

        self.assertFalse(validar_nome_cliente("Edcarlos Oliveira | Programador").valido)
        self.assertFalse(validar_email_estrutural("edcarlos@intranet").valido)
        composto = validar_nome_cliente("João Pedro Silva")
        self.assertTrue(composto.valido)
        self.assertEqual(composto.primeiro_nome, "João Pedro")


class ImportacaoCamposFireAdsTests(unittest.TestCase):
    def test_google_e_meta_importam_campos_sem_rejeitar_caracteres_de_perfil(self):
        for origem, base, campos, alvo in (
            ("google", GOOGLE, ("Nome", "Email"), "Perfil/Faixa"),
            ("meta", META, ("full_name", "email"), "para_quem"),
        ):
            for valor, dependente in (("para_mim", False), ("pai_ou_mae", True)):
                with self.subTest(origem=origem, alvo=valor):
                    registro = dict(base, **{
                        campos[0]: "Edcarlos Oliveira | Programador",
                        campos[1]: " CONTATO@INTRANET ", alvo: valor,
                    })
                    google, meta = ([registro], []) if origem == "google" else ([], [registro])
                    decisao = interpretar(como_aba_geral(google, meta), NUMERO, None)
                    self.assertEqual(decisao["resultado"], "importado")
                    self.assertEqual(decisao["origem"], origem)
                    self.assertIs(decisao["status_dependente"], dependente)
                    self.assertEqual(decisao["dados_titular"], {
                        "nome": "Edcarlos", "email": "contato@intranet",
                        "resultado_email": "email_valido",
                    })

    def test_formulario_encontrado_mas_vazio_segue_fallback_atual(self):
        for campo in ("full_name", "email", "para_quem"):
            for valor in (None, "", " \t "):
                with self.subTest(campo=campo, valor=valor):
                    decisao = interpretar(como_aba_geral([], [dict(META, **{campo: valor})]), NUMERO, None)
                    self.assertEqual(decisao["resultado"], "incompleto")
                    self.assertEqual(decisao["motivo"], "campos_ausentes")
                    self.assertEqual(decisao["dados_titular"], {})

    def test_numero_diferente_nao_importa_dados_mesmo_com_campos_preenchidos(self):
        decisao = interpretar(como_aba_geral([], [META]), "5511999990003", None)
        self.assertEqual(decisao["resultado"], "ausente")
        self.assertEqual(decisao["dados_titular"], {})

    def test_destinatario_desconhecido_nao_e_inventado_por_faixa_etaria(self):
        for valor in ("Adulto", "61_a_75", "opcao_nova"):
            with self.subTest(valor=valor):
                decisao = interpretar(como_aba_geral([], [dict(META, para_quem=valor)]), NUMERO, None)
                self.assertEqual(decisao["resultado"], "incompleto")
                self.assertEqual(decisao["motivo"], "destinatario_desconhecido")

    def test_abertura_usa_nome_extraido_e_email_nao_e_revalidado_pelo_flow(self):
        decisao = dict(interpretar(como_aba_geral([], [dict(
            META, full_name="Edcarlos Oliveira | Programador", email="edcarlos@intranet",
        )]), NUMERO, None), concluida=True, id_conversa=290)
        contexto = {
            "id_conversa": 290, "id_etapa_atual": None, "contexto_fireads": decisao,
            "nome_agente": "Dora", "genero": "feminino", "nome_unidade": "Supera Teste",
        }
        self.assertTrue(email_importado(contexto))
        self.assertEqual(resolver_movimento_conversa(
            contexto, {"id_etapa_resultante": 4},
        ), "inicializacao")
        mensagem = montar_abertura_fireads(contexto, saudacao="Boa noite")
        self.assertIn("Boa noite, Edcarlos!", mensagem)
        self.assertNotIn("Oliveira", mensagem)
        self.assertNotIn("Programador", mensagem)
        self.assertIn("profiss", mensagem)
        self.assertFalse(email_importado(dict(contexto, id_conversa=291)))
        for mudanca in ({"concluida": False}, {"resultado": "incompleto"}):
            self.assertFalse(email_importado(dict(
                contexto, contexto_fireads=dict(decisao, **mudanca),
            )))


if __name__ == "__main__":
    unittest.main()
