import unittest
from unittest.mock import ANY, MagicMock, patch

from core.repositories.atendimento import clientes
from core.repositories.funil import leads
from core.repositories.fluxo.politicas import PoliticaEtapa
from workers.worker_flow.response_flow.transicoes.eventos import (
    EVENTO_COMENTARIO_SATISFACAO_ACEITO,
    EVENTO_COMENTARIO_SATISFACAO_RECEBIDO,
    EVENTO_COMENTARIO_SATISFACAO_RECUSADO,
    EVENTO_DESTINO_ATENDIMENTO_CONFIRMADO,
    EVENTO_DESTINO_ATENDIMENTO_DEFINIDO,
    EVENTO_NOME_CLIENTE_VALIDO,
    EVENTO_PARA_MIM,
    EVENTO_PARA_OUTRA_PESSOA,
    EVENTO_PROFISSAO_DEPENDENTE_VALIDA,
    EVENTO_PROFISSAO_TITULAR_VALIDA,
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
    status_dependente=False,
):
    return {
        "resposta_bot_para_mensagem_atual": resposta_bot,
        "id_conversa": 10,
        "id_etapa_atual": id_etapa_atual,
        "id_etapa_origem_transicao": (
            id_etapa_atual if id_etapa_atual is not None else 1
        ),
        "texto_cliente_atual": texto_cliente,
        "tipo_mensagem_atual": "text",
        "status_dependente": status_dependente,
        "id_cliente": 5,
        "mensagem_cliente_atual": {
            "id_mensagem_fila": 20,
            "id_hash_msg": "wamid.cliente",
            "cliente_telefone": "5571999999999",
            "id_phone_unidade": "123456",
            "unidade_telefone": "5571000000000",
        },
    }


class PersistenciaEssencialTests(unittest.TestCase):
    def test_repositorio_normaliza_e_atualiza_profissao_do_cliente(self):
        cursor = MagicMock()
        cursor.rowcount = 1

        linhas = clientes.atualizar_profissao_cliente(
            5,
            "  Trabalhadora autônoma  ",
            cursor,
        )

        consulta, parametros = cursor.execute.call_args.args
        self.assertIn("UPDATE chatbot.cliente", consulta)
        self.assertEqual(parametros, ("Trabalhadora autônoma", 5))
        self.assertEqual(linhas, 1)

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
        ) as manter, patch.object(
            persistencia,
            "incrementar_turnos_sem_avanco",
            return_value=1,
        ) as incrementar, patch.object(
            persistencia,
            "resetar_turnos_sem_avanco",
        ) as resetar:
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
        incrementar.assert_called_once_with(10, cursor)
        resetar.assert_not_called()
        self.assertEqual(resultado["turnos_sem_avanco"], 1)
        self.assertFalse(resultado["atualizar_conversa"])
        self.assertTrue(resultado["atualizar_last_from_bot"])

    def test_transicao_valida_reseta_turnos_sem_avanco(self):
        cursor = object()

        with patch.object(
            persistencia,
            "inserir_historico_mensagem_bot",
            return_value=(302, DATA_BOT, True),
        ), patch.object(
            persistencia,
            "persistir_movimento_conversa",
            return_value="transicao",
        ), patch.object(
            persistencia,
            "resetar_turnos_sem_avanco",
            return_value=0,
        ) as resetar, patch.object(
            persistencia,
            "incrementar_turnos_sem_avanco",
        ) as incrementar, patch.object(
            persistencia,
            "atualizar_banco_conforme_transicao_de_etapa",
            return_value=None,
        ), patch.object(
            persistencia,
            "resolver_intencao_encerramento",
            return_value=None,
        ):
            resultado = persistencia.atualizar_banco_com_contexto_final(
                contexto_historico_base(id_etapa_atual=1),
                {
                    "enviou": True,
                    "resposta_ja_existia": False,
                    "mensagem_bot": "Avancou",
                    "id_hash_msg_bot": "wamid.bot.transicao",
                    "id_etapa_resultante": 2,
                    "evento_transicao": EVENTO_NOME_CLIENTE_VALIDO,
                    "tipo_mensagem": "text",
                },
                cursor,
            )

        resetar.assert_called_once_with(10, cursor)
        incrementar.assert_not_called()
        self.assertEqual(resultado["turnos_sem_avanco"], 0)

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
            (EVENTO_PARA_MIM, False, False),
            (EVENTO_PARA_OUTRA_PESSOA, True, True),
        )

        for opcao, status_dependente, cria_dependente in casos:
            with self.subTest(opcao=opcao):
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
                                "id_etapa_resultante": 3,
                                "evento_transicao": (
                                    EVENTO_DESTINO_ATENDIMENTO_DEFINIDO
                                ),
                                "opcao_atendimento": opcao,
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

    def test_etapa_tres_aplica_destino_final_sem_inversao_relativa(self):
        dependente = {
            "id_dependente": 30,
            "id_cliente": 5,
            "id_conversa": 10,
            "inserido": False,
        }
        casos = (
            (
                False,
                True,
                True,
            ),
            (
                True,
                False,
                False,
            ),
        )

        for (
            status_anterior,
            status_final,
            deve_manter_dependente,
        ) in casos:
            with self.subTest(status_final=status_final), patch.object(
                efeitos,
                "atualizar_status_dependente_conversa",
                return_value=1,
            ) as atualizar_status, patch.object(
                efeitos,
                "inserir_dependente_para_conversa",
                return_value=dependente,
            ) as inserir_dependente, patch.object(
                efeitos,
                "remover_dependente_placeholder_da_conversa",
                return_value=True,
            ) as remover_dependente:
                resultado = (
                    efeitos.atualizar_banco_conforme_transicao_de_etapa(
                        contexto_historico_base(
                            id_etapa_atual=3,
                            status_dependente=status_anterior,
                        ),
                        {
                            "id_etapa_resultante": 4,
                            "evento_transicao": (
                                EVENTO_DESTINO_ATENDIMENTO_CONFIRMADO
                            ),
                            "status_dependente_final": status_final,
                        },
                        object(),
                    )
                )

            atualizar_status.assert_called_once_with(
                10,
                status_final,
                ANY,
            )
            self.assertEqual(resultado["status_dependente"], status_final)
            self.assertTrue(resultado["status_dependente_alterado"])

            if deve_manter_dependente:
                inserir_dependente.assert_called_once()
                remover_dependente.assert_not_called()
            else:
                inserir_dependente.assert_not_called()
                remover_dependente.assert_called_once()

    def test_retry_da_etapa_tres_reaplica_valor_absoluto_idempotente(self):
        dependente = {
            "id_dependente": 30,
            "id_cliente": 5,
            "id_conversa": 10,
            "inserido": False,
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
            resultado = efeitos.atualizar_banco_conforme_transicao_de_etapa(
                contexto_historico_base(
                    id_etapa_atual=3,
                    status_dependente=True,
                ),
                {
                    "resposta_ja_existia": True,
                    "id_etapa_resultante": 4,
                    "evento_transicao": (
                        EVENTO_DESTINO_ATENDIMENTO_CONFIRMADO
                    ),
                    "status_dependente_final": True,
                },
                object(),
            )

        atualizar_status.assert_called_once()
        inserir_dependente.assert_called_once()
        self.assertTrue(resultado["status_dependente"])
        self.assertFalse(resultado["status_dependente_alterado"])
        self.assertFalse(resultado["dependente_criado"])

    def test_etapa_tres_recusa_status_anterior_ausente(self):
        contexto = contexto_historico_base(
            id_etapa_atual=3,
            status_dependente=False,
        )
        contexto["status_dependente"] = None

        with self.assertRaisesRegex(ValueError, "status_dependente anterior"):
            efeitos.atualizar_banco_conforme_transicao_de_etapa(
                contexto,
                {
                    "id_etapa_resultante": 4,
                    "evento_transicao": (
                        EVENTO_DESTINO_ATENDIMENTO_CONFIRMADO
                    ),
                    "status_dependente_final": True,
                },
                object(),
            )

    def test_etapa_quatro_persiste_profissao_e_respeita_os_dois_ramos(self):
        casos = (
            (
                False,
                EVENTO_PROFISSAO_TITULAR_VALIDA,
                6,
            ),
            (
                True,
                EVENTO_PROFISSAO_DEPENDENTE_VALIDA,
                5,
            ),
        )

        for status_dependente, evento, destino in casos:
            with self.subTest(evento=evento), patch.object(
                efeitos,
                "atualizar_profissao_conversa",
                return_value=1,
            ) as atualizar_profissao_conversa, patch.object(
                efeitos,
                "atualizar_profissao_cliente",
                return_value=1,
            ) as atualizar_profissao_cliente:
                cursor = object()
                resultado = (
                    efeitos.atualizar_banco_conforme_transicao_de_etapa(
                        contexto_historico_base(
                            id_etapa_atual=4,
                            texto_cliente="Sou engenheiro",
                            status_dependente=status_dependente,
                        ),
                        {
                            "id_etapa_resultante": destino,
                            "evento_transicao": evento,
                            "profissao": "Sou engenheiro",
                        },
                        cursor,
                    )
                )

            atualizar_profissao_conversa.assert_called_once_with(
                10,
                "Sou engenheiro",
                cursor,
            )
            atualizar_profissao_cliente.assert_called_once_with(
                5,
                "Sou engenheiro",
                cursor,
            )
            self.assertTrue(resultado["profissao_atualizada"])
            self.assertEqual(resultado["profissao"], "Sou engenheiro")

    def test_etapa_quatro_recusa_status_dependente_ausente(self):
        contexto = contexto_historico_base(
            id_etapa_atual=4,
            texto_cliente="Sou engenheiro",
            status_dependente=False,
        )
        contexto["status_dependente"] = None

        with self.assertRaisesRegex(ValueError, "status_dependente"):
            efeitos.atualizar_banco_conforme_transicao_de_etapa(
                contexto,
                {
                    "id_etapa_resultante": 6,
                    "evento_transicao": EVENTO_PROFISSAO_TITULAR_VALIDA,
                    "profissao": "Sou engenheiro",
                },
                object(),
            )

    def test_retry_da_profissao_reconstroi_texto_original(self):
        cursor = object()

        with patch.object(
            efeitos,
            "atualizar_profissao_conversa",
            return_value=1,
        ) as atualizar_profissao_conversa, patch.object(
            efeitos,
            "atualizar_profissao_cliente",
            return_value=1,
        ) as atualizar_profissao_cliente:
            resultado = efeitos.atualizar_banco_conforme_transicao_de_etapa(
                contexto_historico_base(
                    id_etapa_atual=4,
                    texto_cliente="Trabalho com finanças",
                    status_dependente=False,
                ),
                {
                    "id_etapa_resultante": 6,
                    "evento_transicao": (
                        EVENTO_PROFISSAO_TITULAR_VALIDA
                    ),
                },
                cursor,
            )

        atualizar_profissao_conversa.assert_called_once_with(
            10,
            "Trabalho com finanças",
            cursor,
        )
        atualizar_profissao_cliente.assert_called_once_with(
            5,
            "Trabalho com finanças",
            cursor,
        )
        self.assertEqual(resultado["profissao"], "Trabalho com finanças")

    def test_conversa_nova_atualiza_cliente_sem_reescrever_snapshot_antigo(self):
        cursor = object()
        atualizacoes_conversa = []
        atualizacoes_cliente = []

        def registrar_conversa(id_conversa, profissao, cursor_recebido):
            atualizacoes_conversa.append(
                (id_conversa, profissao, cursor_recebido)
            )
            return 1

        def registrar_cliente(id_cliente, profissao, cursor_recebido):
            atualizacoes_cliente.append(
                (id_cliente, profissao, cursor_recebido)
            )
            return 1

        with patch.object(
            efeitos,
            "atualizar_profissao_conversa",
            side_effect=registrar_conversa,
        ), patch.object(
            efeitos,
            "atualizar_profissao_cliente",
            side_effect=registrar_cliente,
        ):
            for id_conversa, profissao in (
                (121, "Professora"),
                (122, "Lavradora"),
            ):
                contexto = contexto_historico_base(
                    id_etapa_atual=4,
                    status_dependente=False,
                )
                contexto["id_conversa"] = id_conversa
                contexto["id_cliente"] = 111

                efeitos.atualizar_banco_conforme_transicao_de_etapa(
                    contexto,
                    {
                        "id_etapa_resultante": 6,
                        "evento_transicao": (
                            EVENTO_PROFISSAO_TITULAR_VALIDA
                        ),
                        "profissao": profissao,
                    },
                    cursor,
                )

        self.assertEqual(
            atualizacoes_conversa,
            [
                (121, "Professora", cursor),
                (122, "Lavradora", cursor),
            ],
        )
        self.assertEqual(
            atualizacoes_cliente,
            [
                (111, "Professora", cursor),
                (111, "Lavradora", cursor),
            ],
        )

    def test_funil_le_profissao_do_snapshot_da_conversa(self):
        cursor = MagicMock()
        cursor.fetchone.return_value = (
            122,
            1,
            "Rio Vermelho",
            False,
            "Maria",
            "5571999999999",
            "maria@example.com",
            40,
            "Lavradora",
            None,
            None,
            [],
        )

        dados = leads.buscar_dados_lead_funil(122, cursor)

        consulta, parametros = cursor.execute.call_args.args
        self.assertIn("c.profissao", consulta)
        self.assertNotIn("cl.profissao", consulta)
        self.assertEqual(parametros, (122,))
        self.assertEqual(dados["profissao"], "Lavradora")

    def test_falha_ao_atualizar_cliente_interrompe_efeito_da_profissao(self):
        cursor = object()

        with patch.object(
            efeitos,
            "atualizar_profissao_conversa",
            return_value=1,
        ) as atualizar_conversa, patch.object(
            efeitos,
            "atualizar_profissao_cliente",
            side_effect=RuntimeError("cliente indisponivel"),
        ) as atualizar_cliente:
            with self.assertRaisesRegex(RuntimeError, "cliente indisponivel"):
                efeitos.atualizar_banco_conforme_transicao_de_etapa(
                    contexto_historico_base(
                        id_etapa_atual=4,
                        texto_cliente="Lavradora",
                        status_dependente=False,
                    ),
                    {
                        "id_etapa_resultante": 6,
                        "evento_transicao": (
                            EVENTO_PROFISSAO_TITULAR_VALIDA
                        ),
                        "profissao": "Lavradora",
                    },
                    cursor,
                )

        atualizar_conversa.assert_called_once_with(10, "Lavradora", cursor)
        atualizar_cliente.assert_called_once_with(5, "Lavradora", cursor)

    def test_decisao_de_comentar_so_persiste_quando_ha_recusa_ou_texto(self):
        cursor = object()

        with patch.object(
            efeitos,
            "salvar_comentario_satisfacao",
            return_value={
                "id_pesquisa_satisfacao": 30,
                "comentario_satisfacao": None,
                "inserido": False,
            },
        ) as salvar:
            aceite = efeitos.atualizar_banco_conforme_transicao_de_etapa(
                contexto_historico_base(id_etapa_atual=20),
                {
                    "id_etapa_resultante": 21,
                    "evento_transicao": (
                        EVENTO_COMENTARIO_SATISFACAO_ACEITO
                    ),
                },
                cursor,
            )

            salvar.assert_not_called()

            recusa = efeitos.atualizar_banco_conforme_transicao_de_etapa(
                contexto_historico_base(id_etapa_atual=20),
                {
                    "id_etapa_resultante": 22,
                    "evento_transicao": (
                        EVENTO_COMENTARIO_SATISFACAO_RECUSADO
                    ),
                    "comentario_satisfacao": None,
                },
                cursor,
            )

        self.assertTrue(aceite["decisao_comentario_persistida"])
        self.assertEqual(
            aceite["decisao_comentario"],
            EVENTO_COMENTARIO_SATISFACAO_ACEITO,
        )
        salvar.assert_called_once_with(10, None, cursor)
        self.assertTrue(recusa["comentario_satisfacao_persistido"])

    def test_comentario_da_etapa21_e_persistido_integralmente(self):
        cursor = object()

        with patch.object(
            efeitos,
            "salvar_comentario_satisfacao",
            return_value={
                "id_pesquisa_satisfacao": 30,
                "comentario_satisfacao": "Atendimento muito atencioso!",
                "inserido": False,
            },
        ) as salvar:
            resultado = efeitos.atualizar_banco_conforme_transicao_de_etapa(
                contexto_historico_base(
                    id_etapa_atual=21,
                    texto_cliente="Atendimento muito atencioso!",
                ),
                {
                    "id_etapa_resultante": 22,
                    "evento_transicao": (
                        EVENTO_COMENTARIO_SATISFACAO_RECEBIDO
                    ),
                    "comentario_satisfacao": (
                        "Atendimento muito atencioso!"
                    ),
                },
                cursor,
            )

        salvar.assert_called_once_with(
            10,
            "Atendimento muito atencioso!",
            cursor,
        )
        self.assertTrue(resultado["comentario_satisfacao_persistido"])

    def test_somente_etapa_22_encerra_e_aplica_bloqueio_de_30_dias(self):
        contexto = contexto_historico_base(id_etapa_atual=20)

        for id_etapa in (18, 19, 20, 21):
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
                id_etapa=22,
                encerra_automaticamente=True,
                bloqueio_dias=30,
                elegivel_funil=True,
            ),
        ):
            resultado = encerramento.resolver_intencao_encerramento(
                contexto,
                {
                    "evento_transicao": "comentario_satisfacao_recebido",
                    "id_etapa_resultante": 22,
                },
                object(),
            )

        self.assertEqual(resultado["motivo"], "etapa_final")
        self.assertEqual(resultado["motivo_encerramento"], "foi_agendado")
        self.assertEqual(resultado["bloqueio_dias"], 30)


if __name__ == "__main__":
    unittest.main()
