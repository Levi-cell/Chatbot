import unittest

from core.integrations.whatsapp.messages.componentes_compartilhados import (
    CABECALHO_ETAPA1_SAUDACAO,
    RODAPE_ETAPA1_BOAS_VINDAS,
    RODAPE_ETAPA6_ESPERA,
    RODAPE_TRATAMENTO_TEXTO,
    montar_texto_com_cabecalho_e_rodape,
    montar_texto_com_rodape,
)
from core.integrations.whatsapp.messages.etapa1_messages import (
    montar_mensagem_contexto_nome_invalido_etapa1,
    montar_mensagem_etapa1,
    montar_mensagem_financeiro_inicio,
    montar_mensagem_midia_inicio,
)
from core.integrations.whatsapp.messages.etapa3_messages import (
    montar_mensagem_contexto_nome_invalido_etapa3,
)
from core.integrations.whatsapp.messages.etapa4_messages import (
    montar_mensagem_contexto_idade_invalida_etapa4,
)
from core.integrations.whatsapp.messages.etapa6_messages import (
    montar_mensagem_oferta_adiada_etapa6,
)
from core.integrations.whatsapp.messages.etapa8_messages import (
    montar_mensagem_contexto_email_invalido_etapa8,
)


class ComponentesMensagensTests(unittest.TestCase):
    def test_formatador_reproduz_cabecalho_e_rodape_em_texto_simples(self):
        mensagem = montar_texto_com_cabecalho_e_rodape(
            "Corpo",
            "Cabeçalho",
            "Rodapé",
        )

        self.assertEqual(
            mensagem,
            "*Cabeçalho*\n\nCorpo\n\n_Rodapé_",
        )

    def test_tres_entradas_da_etapa1_usam_saudacao_e_boas_vindas(self):
        mensagens = (
            montar_mensagem_etapa1("Bom dia"),
            montar_mensagem_midia_inicio("Bom dia"),
            montar_mensagem_financeiro_inicio("Bom dia"),
        )

        for mensagem in mensagens:
            with self.subTest(mensagem=mensagem):
                self.assertTrue(
                    mensagem.startswith(
                        f"*{CABECALHO_ETAPA1_SAUDACAO}*"
                    )
                )
                self.assertTrue(
                    mensagem.endswith(
                        f"_{RODAPE_ETAPA1_BOAS_VINDAS}_"
                    )
                )

    def test_tratamentos_sem_botoes_usam_dica_compartilhada(self):
        mensagens = (
            montar_mensagem_contexto_nome_invalido_etapa1(),
            montar_mensagem_contexto_nome_invalido_etapa3(),
            montar_mensagem_contexto_idade_invalida_etapa4(),
            montar_mensagem_contexto_email_invalido_etapa8(),
        )

        for mensagem in mensagens:
            with self.subTest(mensagem=mensagem):
                self.assertTrue(
                    mensagem.endswith(
                        f"_{RODAPE_TRATAMENTO_TEXTO}_"
                    )
                )

    def test_etapa6_usa_rodape_de_espera(self):
        mensagem = montar_mensagem_oferta_adiada_etapa6(
            "https://instagram.com/supera.saj/"
        )

        self.assertTrue(
            mensagem.endswith(f"_{RODAPE_ETAPA6_ESPERA}_")
        )

    def test_formatador_de_rodape_nao_adiciona_espacos_externos(self):
        mensagem = montar_texto_com_rodape("Corpo", "Rodapé")

        self.assertEqual(mensagem, mensagem.strip())


if __name__ == "__main__":
    unittest.main()
