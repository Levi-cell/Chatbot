import unittest
from unittest.mock import patch

from workers.worker_flow.transacoes import efeitos_transicao as efeitos
from workers.worker_flow.response_flow.transicoes.eventos import (
    EVENTO_IDADE_VALIDA,
)


def contexto_historico(texto, *, status_dependente=False):
    return {
        "id_conversa": 10,
        "id_cliente": 20,
        "id_etapa_origem_transicao": 4,
        "texto_cliente_atual": texto,
        "status_dependente": status_dependente,
    }


def contexto_envio(**extra):
    resultado = {
        "id_etapa_resultante": 5,
        "evento_transicao": EVENTO_IDADE_VALIDA,
    }
    resultado.update(extra)
    return resultado


class EfeitosEtapa4Tests(unittest.TestCase):
    def test_transicao_quatro_para_cinco_salva_idade_do_cliente(self):
        with patch.object(
            efeitos,
            "atualizar_idade_cliente",
        ) as atualizar_cliente, patch.object(
            efeitos,
            "atualizar_idade_dependente",
        ) as atualizar_dependente:
            resultado = efeitos.atualizar_banco_conforme_transicao_de_etapa(
                contexto_historico("18"),
                contexto_envio(idade_aluno=18),
                object(),
            )

        atualizar_cliente.assert_called_once()
        atualizar_dependente.assert_not_called()
        self.assertEqual(resultado["idade_aluno"], 18)
        self.assertEqual(resultado["destino_dado"], "cliente")

    def test_transicao_quatro_para_cinco_salva_idade_do_dependente(self):
        with patch.object(
            efeitos,
            "atualizar_idade_cliente",
        ) as atualizar_cliente, patch.object(
            efeitos,
            "atualizar_idade_dependente",
        ) as atualizar_dependente:
            resultado = efeitos.atualizar_banco_conforme_transicao_de_etapa(
                contexto_historico("5", status_dependente=True),
                contexto_envio(idade_aluno=5),
                object(),
            )

        atualizar_cliente.assert_not_called()
        atualizar_dependente.assert_called_once()
        self.assertEqual(resultado["destino_dado"], "dependente")

    def test_retry_reconstroi_idade_da_mensagem_original(self):
        with patch.object(
            efeitos,
            "atualizar_idade_cliente",
        ) as atualizar_cliente:
            resultado = efeitos.atualizar_banco_conforme_transicao_de_etapa(
                contexto_historico("Minha idade é trinta e nove"),
                contexto_envio(resposta_ja_existia=True),
                object(),
            )

        atualizar_cliente.assert_called_once()
        self.assertEqual(resultado["idade_aluno"], 39)


if __name__ == "__main__":
    unittest.main()
