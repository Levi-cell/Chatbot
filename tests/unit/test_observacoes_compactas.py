"""Apresentação compacta compartilhada pelo Funil e dashboard."""

import unittest

from core.integrations.funil.oportunidades import montar_payload_oportunidade


def lead(**alteracoes):
    return {
        "id_conversa": 310, "id_unidade": 1, "nome_unidade": "Unidade de teste",
        "nome_cliente": "Ana", "telefone_cliente": "5511999990002",
        "email_cliente": "ana@example.com", "profissao": "Professora",
        "idade_cliente": 58, "status_dependente": False, "turno": "manha",
        "origem_fireads": "google", "contexto_fireads": {"id_integracao": 1},
        "resultado_email_fireads": "email_valido", "primeiro_atendimento": True,
        "triagem_respostas": [
            {"id_etapa": etapa, "resposta": resposta}
            for etapa, resposta in zip(range(12, 18), ["às vezes"] + ["frequentemente"] * 5)
        ],
        **alteracoes,
    }


def observacoes(dados):
    oportunidade = montar_payload_oportunidade(dados)["oportunidades"][0]
    return next(c["valor"] for c in oportunidade["personalizados"] if c["titulo"] == "Observações")


class ObservacoesCompactasTests(unittest.TestCase):
    def test_titular_modelo_completo_sem_linhas_em_branco_entre_perguntas(self):
        esperado = """[INICIO CHATBOT:1:310]
NOVO LEAD : GOOGLE ADS : TITULAR
- Turno de preferência: manhã
- Nome do cliente: Ana
- Telefone/WhatsApp do cliente: 5511999990002
- E-mail do cliente: ana@example.com
- Profissão: Professora
- Idade do cliente: 58

- Com que frequência você esquece compromissos, recados ou onde guardou objetos pessoais? : Às vezes
- Com que frequência você tem dificuldade para lembrar nomes, palavras ou informações recentes? : Frequentemente
- Com que frequência você se distrai com facilidade durante conversas, leituras ou atividades do dia a dia? : Frequentemente
- Com que frequência você tem dificuldade para manter a concentração e concluir uma tarefa que começou? : Frequentemente
- Com que frequência você se sente ansioso(a), preocupado(a) ou com a mente muito acelerada? : Frequentemente
- Com que frequência você tem dificuldade para dormir? : Frequentemente
[FIM CHATBOT:1:310]"""
        self.assertEqual(observacoes(lead()), esperado)

    def test_dependente_preserva_profissao_do_titular_e_personaliza_as_seis_perguntas(self):
        texto = observacoes(lead(origem_fireads="organico", turno="sabado", status_dependente=True,
                                 nome_dependente="Sonia", idade_dependente=72))
        self.assertIn("NOVO LEAD : ORGÂNICO : DEPENDENTE\n", texto)
        self.assertIn("- Turno de preferência: sábado\n", texto)
        self.assertIn("- Profissão: Professora\n- Nome do dependente: Sonia\n- Idade do dependente: 72\n\n- Com", texto)
        self.assertNotIn("Idade do cliente:", texto)
        self.assertNotIn("O atendimento é para", texto)
        perguntas = texto.split("\n\n")[1].splitlines()[:-1]
        self.assertEqual(len(perguntas), 6)
        self.assertTrue(all(p.startswith("- Com que frequência Sonia ") and "? : " in p for p in perguntas))

    def test_sem_fireads_preserva_origem_e_aviso_de_telefone_internacional(self):
        dados = lead(origem_fireads=None, contexto_fireads=None, turno=None,
                     telefone_cliente="447700900000", resposta_email_conversa="Não tenho")
        oportunidade = montar_payload_oportunidade(dados)["oportunidades"][0]
        texto = oportunidade["personalizados"][0]["valor"]
        self.assertTrue(texto.startswith("NOVO LEAD : META CHATBOT : TITULAR\n"))
        self.assertEqual(oportunidade["personalizados"][1]["valor"], "Meta Chatbot")
        self.assertEqual(oportunidade["contato"]["telefone1"], "")
        self.assertEqual(oportunidade["contato"]["email"], "")
        self.assertIn("- O cliente possui um número internacional", texto)
        self.assertIn("- E-mail do cliente: não tem\n", texto)
        self.assertNotIn("Turno de preferência", texto)
        self.assertNotIn("CHATBOT:", texto)


if __name__ == "__main__":
    unittest.main()
