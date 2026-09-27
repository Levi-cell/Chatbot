import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from core.integrations.funil.oportunidades import montar_payload_oportunidade
from core.integrations.whatsapp.messages.etapa6_messages import (
    montar_mensagem_suporte_idoso_etapa6,
)
from core.integrations.whatsapp.numero_comercial import (
    montar_link_numero_comercial_whatsapp,
    numero_comercial_whatsapp_valido,
)
from core.validacoes.email import (
    CLASSIFICACAO_EMAIL_AUSENTE,
    CLASSIFICACAO_EMAIL_NAO_INFORMADO,
    CLASSIFICACAO_EMAIL_VALIDO,
    calcular_email_obrigatorio_efetivo,
    classificar_resposta_email,
    eh_ausencia_email_explicita,
)
from workers.worker_flow.response_flow.etapas import (
    resolver_etapa6,
    resolver_etapa10,
)
from workers.worker_flow.transacoes import (
    efeitos_transicao,
    encerramento_atendimento,
)


RAIZ_PROJETO = Path(__file__).resolve().parents[2]


def contexto_etapa6(idade, *, dependente=False, suporte=None):
    return {
        "id_conversa": 10,
        "id_cliente": 5,
        "id_etapa_atual": 6,
        "id_etapa_cliente": 6,
        "id_etapa_origem_transicao": 6,
        "transicoes_permitidas": {"idade_valida": 7},
        "status_dependente": dependente,
        "bpa_ativo_unidade": False,
        "idade_minima_suporte": suporte,
        "numero_comercial_unidade": "(71) 99999-9999",
        "nome_unidade": "Supera Santo Antônio de Jesus",
        "nome_titular": "Maria",
        "nome_agente": "Suh",
        "genero_agente_unidade": "feminino",
        "nome_dependente": "João" if dependente else None,
        "texto_cliente_atual": str(idade),
        "tipo_mensagem_atual": "text",
        "mensagem_cliente_atual": {
            "id_mensagem_fila": 20,
            "cliente_telefone": "5571999999999",
            "id_phone_unidade": "phone-id",
        },
    }


def contexto_etapa10(
    texto,
    *,
    dependente=False,
    idade=40,
    email_obrigatorio=True,
):
    return {
        "id_conversa": 10,
        "id_cliente": 5,
        "id_etapa_atual": 10,
        "id_etapa_cliente": 10,
        "id_etapa_origem_transicao": 10,
        "transicoes_permitidas": {"email_valido": 11},
        "status_dependente": dependente,
        "idade_cliente": idade,
        "email_obrigatorio_unidade": email_obrigatorio,
        "texto_cliente_atual": texto,
        "tipo_mensagem_atual": "text",
        "mensagem_cliente_atual": {
            "id_mensagem_fila": 20,
            "cliente_telefone": "5571999999999",
            "id_phone_unidade": "phone-id",
        },
        "resposta_bot_para_mensagem_atual": None,
    }


def contexto_envio(etapa):
    return {
        "enviou": True,
        "resposta_ja_existia": False,
        "mensagem_bot": "mensagem",
        "id_hash_msg_bot": "wamid.bot",
        "id_etapa_resultante": etapa,
        "tipo_mensagem": "text",
    }


def dados_lead(*, resposta_email, email_global="novo@example.com"):
    return {
        "id_conversa": 122,
        "id_unidade": 1,
        "nome_unidade": "Santo Antônio de Jesus",
        "status_dependente": False,
        "nome_cliente": "Maria",
        "telefone_cliente": "5571999999999",
        "email_cliente": email_global,
        "resposta_email_conversa": resposta_email,
        "idade_cliente": 65,
        "profissao": "Aposentada",
        "nome_dependente": None,
        "idade_dependente": None,
        "triagem_respostas": [
            {"id_etapa": etapa, "resposta": "nunca"}
            for etapa in range(12, 18)
        ],
    }


class PoliticaEmailTests(unittest.TestCase):
    def test_matriz_da_politica_efetiva(self):
        casos = (
            (True, False, 59, True),
            (False, False, 59, False),
            (True, False, 60, False),
            (True, False, 99, False),
            (True, True, 70, True),
            (False, True, 70, False),
        )

        for configuracao, dependente, idade, esperado in casos:
            with self.subTest(
                configuracao=configuracao,
                dependente=dependente,
                idade=idade,
            ):
                self.assertEqual(
                    calcular_email_obrigatorio_efetivo(
                        configuracao,
                        dependente,
                        idade,
                    ),
                    esperado,
                )

    def test_classificacao_obrigatoria_e_opcional(self):
        valido = classificar_resposta_email(
            "Meu e-mail é Maria@EXEMPLO.COM.",
            email_obrigatorio=True,
        )
        self.assertTrue(valido.aceita)
        self.assertEqual(valido.classificacao, CLASSIFICACAO_EMAIL_VALIDO)
        self.assertEqual(valido.email, "Maria@exemplo.com")

        recusado = classificar_resposta_email(
            "Não tenho",
            email_obrigatorio=True,
        )
        self.assertFalse(recusado.aceita)

        ausencia = classificar_resposta_email(
            "Não tenho e-mail.",
            email_obrigatorio=False,
        )
        self.assertEqual(
            ausencia.classificacao,
            CLASSIFICACAO_EMAIL_AUSENTE,
        )
        self.assertIsNone(ausencia.email)

        comum = classificar_resposta_email(
            "prefiro continuar",
            email_obrigatorio=False,
        )
        self.assertEqual(
            comum.classificacao,
            CLASSIFICACAO_EMAIL_NAO_INFORMADO,
        )

    def test_ausencia_explicita_nao_engole_frase_financeira(self):
        self.assertFalse(eh_ausencia_email_explicita("não tenho dinheiro"))
        self.assertTrue(eh_ausencia_email_explicita("não possuo e-mail"))


class ResolverEtapa10Tests(unittest.TestCase):
    def test_titular_60_mais_avanca_sem_email_mesmo_com_flag_ativa(self):
        with patch.object(
            resolver_etapa10,
            "enviar_etapa11",
            return_value=contexto_envio(11),
        ):
            resultado = resolver_etapa10.resolve_etapa10(
                contexto_etapa10(
                    "Não tenho",
                    idade=60,
                    email_obrigatorio=True,
                )
            )

        self.assertEqual(resultado["evento_transicao"], "email_valido")
        self.assertEqual(
            resultado["resultado_coleta_email"],
            CLASSIFICACAO_EMAIL_AUSENTE,
        )
        self.assertIsNone(resultado["email_cliente"])
        self.assertFalse(resultado["email_obrigatorio_efetivo"])

    def test_dependente_60_mais_continua_obrigado_pela_unidade(self):
        tratamento = contexto_envio(10)
        tratamento["tratamento"] = True

        with patch.object(
            resolver_etapa10,
            "enviar_etapa10_contexto_email_invalido",
            return_value=tratamento,
        ) as enviar_tratamento:
            resultado = resolver_etapa10.resolve_etapa10(
                contexto_etapa10(
                    "Não tenho",
                    dependente=True,
                    idade=70,
                    email_obrigatorio=True,
                )
            )

        enviar_tratamento.assert_called_once()
        self.assertTrue(resultado["tratamento"])
        self.assertNotIn("evento_transicao", resultado)

    def test_financeiro_tem_prioridade_sobre_email_opcional(self):
        tratamento = contexto_envio(10)
        tratamento["tratamento"] = True

        with patch.object(
            resolver_etapa10,
            "validar_pergunta_financeira",
            return_value=True,
        ), patch.object(
            resolver_etapa10,
            "enviar_etapa10_financeiro",
            return_value=tratamento,
        ) as enviar_financeiro, patch.object(
            resolver_etapa10,
            "enviar_etapa11",
        ) as enviar_proxima:
            resultado = resolver_etapa10.resolve_etapa10(
                contexto_etapa10(
                    "não tenho dinheiro",
                    idade=70,
                    email_obrigatorio=False,
                )
            )

        enviar_financeiro.assert_called_once()
        enviar_proxima.assert_not_called()
        self.assertTrue(resultado["tratamento"])


class SuporteIdosoTests(unittest.TestCase):
    def test_fronteiras_e_dependente_preservam_a_ordem_aprovada(self):
        for idade, dependente, suporte, caminho in (
            (59, False, 60, "normal"),
            (60, False, 60, "suporte"),
            (99, False, 60, "cem_mais"),
            (100, False, 60, "cem_mais"),
            (70, True, 60, "normal_dependente"),
        ):
            with self.subTest(
                idade=idade,
                dependente=dependente,
                suporte=suporte,
            ), patch.object(
                resolver_etapa6,
                "enviar_etapa6_suporte_idoso",
                return_value=contexto_envio(6),
            ) as enviar_suporte, patch.object(
                resolver_etapa6,
                "enviar_etapa6_idade_acima_99",
                return_value=contexto_envio(6),
            ) as enviar_cem, patch.object(
                resolver_etapa6,
                "enviar_etapa7_cliente",
                return_value=contexto_envio(7),
            ) as enviar_cliente, patch.object(
                resolver_etapa6,
                "enviar_etapa7_dependente",
                return_value=contexto_envio(7),
            ) as enviar_dependente:
                resultado = resolver_etapa6.resolve_etapa6(
                    contexto_etapa6(
                        idade,
                        dependente=dependente,
                        suporte=suporte,
                    )
                )

            self.assertEqual(enviar_suporte.called, caminho == "suporte")
            self.assertEqual(enviar_cem.called, caminho == "cem_mais")
            self.assertEqual(enviar_cliente.called, caminho == "normal")
            self.assertEqual(
                enviar_dependente.called,
                caminho == "normal_dependente",
            )

            if caminho == "suporte":
                self.assertTrue(resultado["encerrar_atendimento"])
                self.assertEqual(
                    resultado["motivo_encerramento"],
                    "encaminhado_suporte_idoso",
                )

    def test_efeito_terminal_persiste_idade_do_titular(self):
        cursor = object()
        contexto = contexto_etapa6(65, suporte=60)
        envio = contexto_envio(6)
        envio.update(
            {
                "encerrar_atendimento": True,
                "motivo_encerramento": "encaminhado_suporte_idoso",
                "limite_idade_encerramento": 60,
                "idade_aluno": 65,
            }
        )

        with patch.object(
            efeitos_transicao,
            "atualizar_idade_cliente",
        ) as atualizar:
            resultado = (
                efeitos_transicao.atualizar_banco_conforme_transicao_de_etapa(
                    contexto,
                    envio,
                    cursor,
                )
            )

        atualizar.assert_called_once_with(5, 65, cursor)
        self.assertTrue(resultado["encaminhamento_suporte_idoso"])

    def test_encerramento_e_replay_usam_motivo_novo_sem_bloqueio(self):
        contexto = contexto_etapa6(65, suporte=60)
        envio = contexto_envio(6)
        envio.update(
            {
                "encerrar_atendimento": True,
                "motivo_encerramento": "encaminhado_suporte_idoso",
                "limite_idade_encerramento": 60,
            }
        )
        primeira = encerramento_atendimento.resolver_intencao_encerramento(
            contexto,
            envio,
            object(),
        )
        self.assertEqual(
            primeira["motivo_encerramento"],
            "suporte_idoso_60",
        )
        self.assertEqual(primeira["bloqueio_dias"], 0)

        contexto["resposta_bot_para_mensagem_atual"] = {
            "tipo_mensagem": "interactive_cta_url",
            "conteudo_texto": (
                "Que bom te ver aqui novamente, Maria!\n\n"
                + montar_mensagem_suporte_idoso_etapa6(60)
            ),
        }
        replay = encerramento_atendimento.resolver_intencao_encerramento(
            contexto,
            {
                "resposta_ja_existia": True,
                "id_etapa_resultante": 6,
            },
            object(),
        )
        self.assertEqual(
            replay["motivo_encerramento"],
            "suporte_idoso_60",
        )
        self.assertEqual(replay["bloqueio_dias"], 0)

    def test_numero_comercial_compartilha_a_mesma_validacao(self):
        self.assertTrue(numero_comercial_whatsapp_valido("(71) 99999-9999"))
        self.assertEqual(
            montar_link_numero_comercial_whatsapp("(71) 99999-9999"),
            "https://wa.me/5571999999999",
        )
        self.assertFalse(numero_comercial_whatsapp_valido("123"))


class PersistenciaEmailEFunilTests(unittest.TestCase):
    def test_ausencia_limpa_email_anterior_e_retry_reconstroi_sem_flag(self):
        cursor = object()
        contexto = contexto_etapa10(
            "Não tenho",
            idade=70,
            email_obrigatorio=False,
        )
        contexto["resposta_bot_para_mensagem_atual"] = {
            "id_etapa": 11,
        }
        envio = {
            "resposta_ja_existia": True,
            "id_etapa_resultante": 11,
            "evento_transicao": "email_valido",
        }

        with patch.object(
            efeitos_transicao,
            "atualizar_email_cliente",
        ) as atualizar:
            resultado = (
                efeitos_transicao.atualizar_banco_conforme_transicao_de_etapa(
                    contexto,
                    envio,
                    cursor,
                )
            )

        atualizar.assert_called_once_with(5, None, cursor)
        self.assertEqual(
            resultado["resultado_coleta_email"],
            CLASSIFICACAO_EMAIL_AUSENTE,
        )

    def test_funil_usa_resposta_historica_e_nao_email_global_novo(self):
        payload = montar_payload_oportunidade(
            dados_lead(resposta_email="Não tenho")
        )["oportunidades"][0]

        self.assertEqual(payload["contato"]["email"], "")
        observacoes = payload["personalizados"][0]["valor"]
        self.assertIn("E-mail do cliente: não tem", observacoes)
        self.assertNotIn("novo@example.com", observacoes)

    def test_funil_distingue_nao_informado_e_email_historico(self):
        comum = montar_payload_oportunidade(
            dados_lead(resposta_email="prefiro continuar")
        )["oportunidades"][0]
        self.assertIn(
            "E-mail do cliente: não informado",
            comum["personalizados"][0]["valor"],
        )

        antigo = montar_payload_oportunidade(
            dados_lead(resposta_email="antigo@EXEMPLO.COM")
        )["oportunidades"][0]
        self.assertEqual(antigo["contato"]["email"], "antigo@exemplo.com")

    def test_ddl_e_migracao_publicam_o_mesmo_contrato(self):
        ddl = (
            RAIZ_PROJETO
            / "core/database/deploy_database/bank_script.py"
        ).read_text(encoding="utf-8")
        migracao = (
            RAIZ_PROJETO
            / "deploy/migrations/20260829_adicionar_suporte_idoso_email_obrigatorio.sql"
        ).read_text(encoding="utf-8")

        for conteudo in (ddl, migracao):
            self.assertIn("email_obrigatorio", conteudo)
            self.assertIn("encaminhado_suporte_idoso", conteudo)

        self.assertIn("idade_minima_suporte", ddl)
        self.assertIn("suporte_idoso", migracao)
        self.assertNotIn("UPDATE chatbot.unidade", migracao)
        self.assertNotIn("INSERT INTO chatbot.unidade", migracao)


if __name__ == "__main__":
    unittest.main()
