import unittest
from unittest.mock import patch

from core.repositories.fluxo.politicas import PoliticaEtapa
from workers.worker_flow.response_flow.transicoes.eventos import (
    EVENTO_NOME_CLIENTE_VALIDO,
    EVENTO_PARA_MIM,
    EVENTO_PARA_OUTRA_PESSOA,
)
from workers.worker_flow.transacoes import efeitos_transicao as efeitos
from workers.worker_flow.transacoes import encerramento_atendimento as encerramento
from workers.worker_flow.transacoes import movimento_conversa as movimento
from workers.worker_flow.transacoes import persistencia_resposta as persistencia


DATA_BOT = "2026-01-01T00:00:00"


def contexto_historico_base(
    resposta_bot=None,
    *,
    id_etapa_atual=None,
    texto_cliente="Ola",
):
    return {
        "resposta_bot_para_mensagem_atual": resposta_bot,
        "id_conversa": 10,
        "id_etapa_atual": id_etapa_atual,
        "id_etapa_origem_transicao": (
            id_etapa_atual if id_etapa_atual is not None else 1
        ),
        "texto_cliente_atual": texto_cliente,
        "mensagem_cliente_atual": {
            "id_mensagem_fila": 20,
            "id_hash_msg": "wamid.cliente",
            "cliente_telefone": "5571999999999",
            "id_phone_unidade": "123456",
            "unidade_telefone": "5571000000000",
        },
    }


class PersistenciaEssencialTests(unittest.TestCase):
    def test_resposta_normal_persiste_bot_e_avanca_conversa(self):
        cursor = object()

        with patch.object(
            persistencia,
            "inserir_historico_mensagem_bot",
            return_value=(300, DATA_BOT, True),
        ) as inserir_bot, patch.object(
            movimento,
            "inicializar_conversa_resposta_bot",
            return_value=1,
        ) as avancar, patch.object(
            movimento,
            "atualizar_conversa_resposta_bot_sem_avancar",
        ) as manter:
            resultado = persistencia.atualizar_banco_com_contexto_final(
                contexto_historico_base(),
                {
                    "enviou": True,
                    "resposta_ja_existia": False,
                    "mensagem_bot": "Ola!",
                    "id_hash_msg_bot": "wamid.bot",
                    "id_etapa_resultante": 1,
                    "tipo_mensagem": "interactive_button",
                },
                cursor,
            )

        inserir_bot.assert_called_once()
        avancar.assert_called_once_with(10, 1, DATA_BOT, cursor)
        manter.assert_not_called()
        self.assertTrue(resultado["historico_bot_inserido"])
        self.assertTrue(resultado["atualizar_conversa"])

    def test_tratamento_persiste_resposta_sem_avancar_etapa(self):
        cursor = object()

        with patch.object(
            persistencia,
            "inserir_historico_mensagem_bot",
            return_value=(301, DATA_BOT, True),
        ), patch.object(
            movimento,
            "inicializar_conversa_resposta_bot",
        ) as avancar, patch.object(
            movimento,
            "atualizar_conversa_resposta_bot_sem_avancar",
            return_value=1,
        ) as manter:
            resultado = persistencia.atualizar_banco_com_contexto_final(
                contexto_historico_base(id_etapa_atual=1),
                {
                    "enviou": True,
                    "resposta_ja_existia": False,
                    "mensagem_bot": "Tratamento",
                    "id_hash_msg_bot": "wamid.bot.tratamento",
                    "id_etapa_resultante": 1,
                    "tipo_mensagem": "text",
                    "tratamento": True,
                    "atualizar_conversa": False,
                    "atualizar_last_from_bot": True,
                },
                cursor,
            )

        avancar.assert_not_called()
        manter.assert_called_once_with(10, DATA_BOT, cursor)
        self.assertFalse(resultado["atualizar_conversa"])
        self.assertTrue(resultado["atualizar_last_from_bot"])

    def test_resposta_existente_nao_e_enviada_nem_inserida_novamente(self):
        cursor = object()

        with patch.object(
            persistencia,
            "inserir_historico_mensagem_bot",
        ) as inserir_bot, patch.object(
            movimento,
            "atualizar_conversa_resposta_bot_sem_avancar",
            return_value=1,
        ) as manter:
            resultado = persistencia.atualizar_banco_com_contexto_final(
                contexto_historico_base(
                    {"received_data_hora": DATA_BOT},
                    id_etapa_atual=1,
                ),
                {
                    "enviou": False,
                    "resposta_ja_existia": True,
                    "id_hash_msg_bot": "wamid.bot.existente",
                    "id_etapa_resultante": 1,
                },
                cursor,
            )

        inserir_bot.assert_not_called()
        manter.assert_called_once_with(10, DATA_BOT, cursor)
        self.assertTrue(resultado["resposta_ja_existia"])
        self.assertFalse(resultado["historico_bot_inserido"])

    def test_transicao_um_para_dois_salva_o_nome_do_cliente(self):
        cursor = object()

        with patch.object(
            efeitos,
            "atualizar_nome_cliente_por_telefone",
            return_value=1,
        ) as atualizar_nome:
            resultado = efeitos.atualizar_banco_conforme_transicao_de_etapa(
                contexto_historico_base(
                    id_etapa_atual=1,
                    texto_cliente="Maria",
                ),
                {
                    "id_etapa_resultante": 2,
                    "evento_transicao": EVENTO_NOME_CLIENTE_VALIDO,
                    "primeiro_nome_cliente": "Maria",
                },
                cursor,
            )

        atualizar_nome.assert_called_once_with(
            "5571999999999",
            "Maria",
            cursor,
        )
        self.assertEqual(resultado["primeiro_nome_cliente"], "Maria")

    def test_etapa_dois_persiste_corretamente_os_dois_ramos(self):
        casos = (
            (EVENTO_PARA_MIM, 4, False, False),
            (EVENTO_PARA_OUTRA_PESSOA, 3, True, True),
        )

        for evento, destino, status_dependente, cria_dependente in casos:
            with self.subTest(evento=evento):
                dependente = {
                    "id_dependente": 30,
                    "id_cliente": 5,
                    "id_conversa": 10,
                    "inserido": True,
                }

                with patch.object(
                    efeitos,
                    "atualizar_status_dependente_conversa",
                    return_value=1,
                ) as atualizar_status, patch.object(
                    efeitos,
                    "inserir_dependente_para_conversa",
                    return_value=dependente,
                ) as inserir_dependente:
                    resultado = (
                        efeitos.atualizar_banco_conforme_transicao_de_etapa(
                            contexto_historico_base(id_etapa_atual=2),
                            {
                                "id_etapa_resultante": destino,
                                "evento_transicao": evento,
                            },
                            object(),
                        )
                    )

                atualizar_status.assert_called_once()
                self.assertEqual(
                    resultado["status_dependente"],
                    status_dependente,
                )
                self.assertEqual(
                    resultado["dependente_criado"],
                    cria_dependente,
                )

                if cria_dependente:
                    inserir_dependente.assert_called_once()
                else:
                    inserir_dependente.assert_not_called()

    def test_somente_etapa_19_encerra_e_aplica_bloqueio_de_30_dias(self):
        contexto = contexto_historico_base(id_etapa_atual=18)

        for id_etapa in (17, 18):
            with self.subTest(id_etapa=id_etapa), patch.object(
                encerramento,
                "buscar_politica_etapa",
                return_value=PoliticaEtapa(
                    id_etapa=id_etapa,
                    encerra_automaticamente=False,
                    bloqueio_dias=0,
                    elegivel_funil=True,
                ),
            ):
                resultado = encerramento.resolver_intencao_encerramento(
                    contexto,
                    {
                        "evento_transicao": "evento_teste",
                        "id_etapa_resultante": id_etapa,
                    },
                    object(),
                )

            self.assertIsNone(resultado)

        with patch.object(
            encerramento,
            "buscar_politica_etapa",
            return_value=PoliticaEtapa(
                id_etapa=19,
                encerra_automaticamente=True,
                bloqueio_dias=30,
                elegivel_funil=True,
            ),
        ):
            resultado = encerramento.resolver_intencao_encerramento(
                contexto,
                {
                    "evento_transicao": "comentario_satisfacao_recebido",
                    "id_etapa_resultante": 19,
                },
                object(),
            )

        self.assertEqual(resultado["motivo"], "etapa_final")
        self.assertEqual(resultado["motivo_encerramento"], "foi_agendado")
        self.assertEqual(resultado["bloqueio_dias"], 30)


if __name__ == "__main__":
    unittest.main()
