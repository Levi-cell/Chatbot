"""Contrato da aba única e entrega do mesmo formulário, sem serviços externos."""

from copy import deepcopy
import unittest
from unittest.mock import Mock, patch

from core.integrations.fireads.aba_geral import configuracao_compativel
from core.integrations.fireads.contrato import (
    ABA_DESTINO, CANAIS, ErroFireAds, bloco_observacoes, acrescentar_observacoes,
)
from core.integrations.funil.oportunidades import montar_observacoes_lead
from workers.worker_consulta_dash.resultado import interpretar
from workers.worker_consulta_dash.consulta import consultar
from workers.worker_funil.fireads import preparar_escrita

NUMERO = "5511999990002"
REGISTRO = {
    "_row": 44, "Nome": "Ana Paula Silva", "Email": "ana@example.com",
    "WhatsApp": NUMERO, "Canal": "Google Ads", "Para quem é": "Para mim",
    "Data/Hora": "14/10/2026", "Observação": "Anotação do operador",
}


class AbaGeralTests(unittest.TestCase):
    def test_canais_permitidos_antes_da_recencia(self):
        manual = dict(REGISTRO, _row=99, Canal="Lead Franqueador", **{"Data/Hora": "15/10/2026"})
        for canal, origem in (("Google Ads", "google"), ("META ADS", "meta"), (" Orgânico   Site ", "organico_site")):
            with self.subTest(canal=canal):
                decisao = interpretar([dict(REGISTRO, Canal=canal), manual], NUMERO)
                self.assertEqual(decisao["origem"], origem)
                self.assertEqual(decisao["referencia"]["linha"], 44)
                self.assertEqual(decisao["dados_titular"]["nome"], "Ana Paula")
        for canal in ("Indicação", "Lead Franqueador", "MKT DIGITAL - GOOGLE ADS", "Orgânico"):
            decisao = interpretar([dict(REGISTRO, Canal=canal)], NUMERO)
            self.assertEqual(decisao["motivo"], "canal_nao_elegivel")
            self.assertEqual(decisao["dados_titular"], {})
            self.assertIsNotNone(decisao["referencia"])

    def test_data_hora_e_depois_linha_sem_preferencia_por_canal(self):
        for canal in ("Google Ads", "Meta Ads", "Organico Site"):
            rows = [dict(REGISTRO, _row=n, Canal=canal if n == 46 else "Google Ads") for n in (44,45,46)]
            self.assertEqual(interpretar(rows, NUMERO)["referencia"]["linha"], 46)
        rows = [dict(REGISTRO, _row=90), dict(REGISTRO, _row=2, **{"Data/Hora": "15/10/2026"})]
        self.assertEqual(interpretar(rows, NUMERO)["referencia"]["linha"], 2)
        rows[0]["Data/Hora"] = "15/10/2026 12:00:01"
        self.assertEqual(interpretar(rows, NUMERO)["referencia"]["linha"], 90)

    def test_data_invalida_prioriza_data_valida_ou_maior_linha(self):
        invalido = dict(REGISTRO, _row=90, **{"Data/Hora": "sem data"})
        self.assertEqual(interpretar([REGISTRO, invalido], NUMERO)["referencia"]["linha"], 44)
        decisao = interpretar([invalido], NUMERO)
        self.assertEqual(decisao["referencia"]["criterio_recencia"], "linha_sem_data_valida")
        for linha in (None, True, 1, "44"):
            with self.assertRaises(ErroFireAds):
                interpretar([dict(REGISTRO, _row=linha)], NUMERO)

    def test_incompleto_nao_resgata_outro_formulario_e_preserva_alvo(self):
        for campo in ("Nome", "Email", "Para quem é"):
            novo = dict(REGISTRO, _row=46, **{campo: ""})
            decisao = interpretar([REGISTRO, novo], NUMERO)
            self.assertEqual(decisao["origem"], "organico")
            self.assertEqual(decisao["motivo"], "campos_ausentes")
            self.assertEqual(decisao["dados_titular"], {})
            self.assertEqual(decisao["referencia"]["linha"], 46)
        decisao = interpretar([dict(REGISTRO, **{"Para quem é": "61_a_75"})], NUMERO)
        self.assertEqual(decisao["motivo"], "destinatario_desconhecido")

    def test_parentescos_nao_importam_idade_e_variante_telefone_participa(self):
        for parentesco in ("Para meu pai/mãe", "filho_ou_filha", "Para outra pessoa", "Para dependente"):
            decisao = interpretar([dict(REGISTRO, **{"Para quem é": parentesco})], NUMERO)
            self.assertTrue(decisao["status_dependente"])
            self.assertNotIn("idade", decisao["dados_titular"])
        recente = dict(REGISTRO, _row=46, WhatsApp="p:+551199990002")
        self.assertEqual(interpretar([REGISTRO, recente], NUMERO)["referencia"]["linha"], 46)
        self.assertEqual(interpretar([REGISTRO], "5511999990003")["motivo"], "telefone_ausente")

    def test_consulta_uma_aba_e_guarda_apenas_o_contato(self):
        outro = dict(REGISTRO, _row=50, WhatsApp="5511999990003")
        api = Mock()
        api.consultar.return_value = {"headers": list(REGISTRO), "rows": [REGISTRO, outro]}
        reserva = {"id_consulta": 1, "restante": 300, "entrada": {
            "versao": 2, "url": "https://script.google.com/macros/s/teste/exec",
            "aba": ABA_DESTINO, "numero": NUMERO, "fuso": None,
        }}
        with patch("workers.worker_consulta_dash.consulta.ClienteFireAds", return_value=api):
            resultado = consultar(reserva)
        api.consultar.assert_called_once_with(ABA_DESTINO)
        self.assertEqual(resultado["fontes"], {"geral": [REGISTRO]})
        api.enviar.assert_not_called()
        api.consultar.return_value["headers"].remove("Para quem é")
        with patch("workers.worker_consulta_dash.consulta.ClienteFireAds", return_value=api):
            self.assertEqual(consultar(reserva)["decisao"]["motivo"], "cabecalhos_ausentes")

    def test_configuracao_legada_compatibilidade_e_versao_desconhecida(self):
        abertura = {"url": "url", "aba": ABA_DESTINO, "fuso": None}
        self.assertTrue(configuracao_compativel(dict(abertura, versao=2), abertura))
        self.assertTrue(configuracao_compativel({"compatibilidade_aba_geral": dict(abertura, valida=True)}, abertura))
        self.assertFalse(configuracao_compativel(dict(abertura, versao=3), abertura))
        self.assertFalse(configuracao_compativel({"aba_google": "antiga"}, abertura))
        self.assertFalse(configuracao_compativel(dict(abertura, versao=2, aba="Outra"), abertura))


class EntregaAbaGeralTests(unittest.TestCase):
    def setUp(self):
        self.bloco = bloco_observacoes(1, 25, "Novo lead\nDados de atendimento", versao=2)
        self.snapshot = {
            "versao": 2, "aba": ABA_DESTINO, "telefone": NUMERO,
            "nome": "Ana", "email": "ana@example.com", "perfil": "Titular",
            "origem": "google", "referencia": interpretar([REGISTRO], NUMERO)["referencia"],
        }

    def test_atualiza_mesmo_formulario_mesmo_com_nova_inscricao(self):
        novo = dict(REGISTRO, _row=100, Nome="Carlos", Canal="Meta Ads")
        antes = deepcopy(REGISTRO)
        op = preparar_escrita([REGISTRO, novo], self.snapshot, self.bloco)
        self.assertEqual(op["row"], 44)
        self.assertEqual(set(op), {"row", "observacoes"})
        self.assertEqual(op["observacoes"], REGISTRO["Observação"] + "\n\n" + self.bloco)
        self.assertEqual(REGISTRO, antes)

    def test_relocaliza_mas_nao_atualiza_posicao_reutilizada_ou_alvo_excluido(self):
        deslocado = dict(REGISTRO, _row=43)
        outro = dict(REGISTRO, Nome="Outra pessoa", WhatsApp="5511999990003")
        self.assertEqual(preparar_escrita([outro, deslocado], self.snapshot, self.bloco)["row"], 43)
        for rows in ([], [outro], [dict(REGISTRO, Nome="Editado")]):
            with self.assertRaises(ErroFireAds):
                preparar_escrita(rows, self.snapshot, self.bloco)

    def test_reconcilia_antes_de_relocalizar_e_nao_repete_apos_queda(self):
        entregue = dict(REGISTRO, _row=43, **{"Observação": "Operador\n\n" + self.bloco})
        self.assertIsNone(preparar_escrita([entregue], self.snapshot, self.bloco))
        entregue["Observação"] = entregue["Observação"].replace("Dados de atendimento", "Editado")
        with self.assertRaises(ErroFireAds):
            preparar_escrita([entregue], self.snapshot, self.bloco)

    def test_duas_conversas_mesmo_titulo_e_bloco_legado(self):
        legado = bloco_observacoes(1, 24, "Texto antigo")
        novo, _ = acrescentar_observacoes(legado, self.bloco)
        self.assertTrue(novo.startswith(legado))
        outro = bloco_observacoes(1, 26, "Novo atendimento para Lead antigo", versao=2)
        final, mudou = acrescentar_observacoes(novo, outro)
        self.assertTrue(mudou)
        self.assertEqual(acrescentar_observacoes(final, outro), (final, False))

    def test_organico_sem_alvo_reconfere_antes_do_append(self):
        snapshot = dict(self.snapshot, referencia=None, origem="organico")
        self.assertEqual(preparar_escrita([REGISTRO], snapshot, self.bloco)["row"], 44)
        self.assertEqual(preparar_escrita([], snapshot, self.bloco)["dados"]["Canal"], "Orgânico")
        with self.assertRaises(ErroFireAds):
            preparar_escrita([dict(REGISTRO, WhatsApp="5511999990003")], snapshot, self.bloco)

    def test_resumo_canais_e_profissao_antes_do_dependente(self):
        dados = {
            "id_conversa": 25, "nome_cliente": "Ana", "telefone_cliente": NUMERO,
            "email_cliente": "ana@example.com", "profissao": "Professora",
            "status_dependente": True, "nome_dependente": "João", "idade_dependente": 12,
            "resultado_email_fireads": "email_valido", "contexto_fireads": {"id_integracao": 1},
            "triagem_respostas": [{"id_etapa": etapa, "resposta": "nunca"} for etapa in range(12,18)],
        }
        for origem, codigo in (("google", "113336"), ("meta", "113340"), ("organico_site", "113481"), ("organico", "113481")):
            for primeiro in (True, False):
                texto = montar_observacoes_lead(dict(dados, origem_fireads=origem, primeiro_atendimento=primeiro))
                self.assertTrue(texto.startswith("Observações de atendimento\n"))
                self.assertNotIn("— conversa", texto)
                self.assertIn("Novo lead" if primeiro else "Novo atendimento para Lead antigo", texto)
                self.assertLess(texto.index("Profissão:"), texto.index("Nome do dependente:"))
                self.assertEqual(CANAIS[origem][1], codigo)
                if origem == "organico_site":
                    self.assertIn("chegou ao site de maneira orgânica", texto)
