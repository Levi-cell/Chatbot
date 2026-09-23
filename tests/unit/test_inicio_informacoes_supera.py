"""Abertura explicativa pede o nome sem alterar etapas, tratamentos ou retries."""

import unittest
from unittest.mock import patch

from core.integrations.whatsapp.messages import etapa1_messages
from core.integrations.whatsapp.pywa_functions import cliente
from core.integrations.whatsapp.pywa_functions.pywa_senders import etapa1
from tests.unit.test_followup import contexto as contexto_followup
from tests.unit.test_mensagens_reserva import cliente_simulado
from tests.unit.test_persistencia_essencial import contexto_historico_base
from workers.worker_flow.response_flow.etapas import resolver_etapa1
from workers.worker_flow.response_flow.etapas.validadores_contexto.valida_inicio_etapa1 import (
    validar_pedido_informacoes_supera,
)
from workers.worker_flow.response_flow.flow_sender import flow_sender
from workers.worker_flow.response_flow.repeticao_followup import (
    enviar_repeticao_followup,
)
from workers.worker_flow.transacoes import movimento_conversa as movimento
from workers.worker_flow.transacoes import persistencia_resposta as persistencia


def contexto_inicio(texto, *, etapa=None, tipo="text", genero="feminino"):
    contexto = contexto_historico_base(id_etapa_atual=etapa, texto_cliente=texto)
    contexto.update(
        id_etapa_cliente=1,
        retry_count=0,
        transicoes_permitidas={"nome_cliente_valido": 2},
        tipo_mensagem_atual=tipo,
        nome_unidade="Supera Teste",
        nome_agente="Mia" if genero == "feminino" else "Léo",
        genero=genero,
    )
    return contexto


class PedidoInformacoesSuperaTests(unittest.TestCase):
    def test_perguntas_e_pedidos_com_e_sem_saudacao_acentos_e_interrogacao(self):
        frases = (
            "Do que se trata",
            "O que é o supera",
            "O que é",
            "Do que se trata o supera",
            "Posso ter mais informações sobre isso",
            "Como funciona",
            "Como funciona o Supera",
            "O que é o método Supera",
            "O que é esse curso",
            "De que se trata isso",
            "Quero saber o que é o Supera",
            "Gostaria de entender como funciona",
            "Eu queria saber mais sobre o Supera",
            "Gostaria de receber informações",
            "Quero informações sobre isso",
            "Tenho interesse em saber mais",
            "Tenho interesse e queria mais informações",
            "Eu tenho interesse e gostaria de receber mais detalhes sobre isso",
            "Posso saber mais sobre o Supera",
            "Pode me passar mais informações",
            "Você poderia me explicar o que é o Supera",
            "Me explica o Supera",
            "Me explique do que se trata",
            "Pode me falar mais sobre isso",
            "Vocês podem me enviar informações sobre o curso Supera",
            "Mais detalhes sobre isso",
            "oq é isso",
        )
        for frase in frases:
            for texto in (
                frase,
                f"Olá! {frase}?",
                f"Bom dia 😊 {frase.upper()}, por favor!",
            ):
                with self.subTest(texto=texto):
                    self.assertTrue(validar_pedido_informacoes_supera(texto))
        for texto in (
            "Ola! Posso ter mais informacoes sobre isso?",
            "Oi, gostaria de saber um pouco sobre o Supera",
            "Oi, tudo bem? Queria saber mais sobre o Supera. Obrigada!",
            "  BOA NOITE!!!\nComo funciona o supera??? 🧡",
        ):
            with self.subTest(texto=texto):
                self.assertTrue(validar_pedido_informacoes_supera(texto))

    def test_palavras_soltas_negativas_e_outros_assuntos_nao_sao_explicacao(self):
        for texto in (
            None,
            1,
            "",
            "   ",
            "???",
            "Oi",
            "Olá, tudo bem?",
            "Maria",
            "Me chamo José",
            "Supera",
            "informações",
            "Não quero informações",
            "Não quero saber o que é o Supera",
            "Quero reservar",
            "Gostaria de informações sobre preços",
            "Me explica o pagamento",
            "Quero saber mais sobre o endereço",
            "O que é o pix",
            "Como funciona a matrícula",
            "Posso ter informações sobre minha reserva",
            "O que é o Supera? Não quero receber mensagens",
            "Vi informações sobre vocês ontem",
            "O que é o Superação",
        ):
            with self.subTest(texto=texto):
                self.assertFalse(validar_pedido_informacoes_supera(texto))


class AberturaInformacoesSuperaTests(unittest.TestCase):
    def test_envio_unico_com_texto_aprovado_dados_da_unidade_e_etapa_um(self):
        for genero, nome_agente, artigo in (
            ("feminino", "Mia", "a"),
            ("masculino", "Léo", "o"),
        ):
            with self.subTest(genero=genero):
                contexto = contexto_inicio(
                    "Olá! Posso ter mais informações sobre isso?", genero=genero
                )
                wa = cliente_simulado()
                with patch.object(cliente, "WhatsApp", return_value=wa), patch.object(
                    etapa1, "obter_saudacao_por_horario", return_value="Boa tarde"
                ), patch.object(
                    resolver_etapa1, "validar_nome_cliente"
                ) as validar_nome:
                    envio = flow_sender(contexto)
                esperado = (
                    f"Boa tarde! Sou {artigo} {nome_agente}, assistente do Supera Teste! ☺️\n"
                    "Para eu te orientar melhor e passar mais detalhes poderia me falar seu nome?"
                )
                wa.send_message.assert_called_once()
                validar_nome.assert_not_called()
                self.assertEqual(envio["mensagem_bot"], esperado)
                self.assertEqual(wa.send_message.call_args.kwargs["text"], esperado)
                self.assertNotIn("buttons", wa.send_message.call_args.kwargs)
                self.assertEqual(envio["id_etapa_resultante"], 1)
                self.assertNotIn("tratamento", envio)
                self.assertNotIn("evento_transicao", envio)
                self.assertNotIn("primeiro_nome_cliente", envio)

                # Usa a persistência real com fronteiras de banco substituídas:
                # apresentar a 1 não é transitar para a 2 nem contar resposta inválida.
                cursor = object()
                with patch.object(
                    persistencia,
                    "inserir_historico_mensagem_bot",
                    return_value=(300, "data", True),
                ), patch.object(
                    movimento, "inicializar_conversa_resposta_bot", return_value=1
                ) as inicializar, patch.object(
                    persistencia, "incrementar_turnos_sem_avanco"
                ) as incrementar:
                    resultado = persistencia.atualizar_banco_com_contexto_final(
                        contexto, envio, cursor
                    )
                inicializar.assert_called_once_with(10, 1, "data", cursor)
                incrementar.assert_not_called()
                self.assertTrue(resultado["historico_bot_inserido"])

    def test_ambas_as_aberturas_convergem_para_apresentacao_do_supera(self):
        for texto in (
            "Olá",
            "O que é o Supera?",
            "Oi, gostaria de saber um pouco sobre o Supera",
        ):
            with self.subTest(texto=texto), patch.object(
                cliente, "WhatsApp", return_value=cliente_simulado()
            ):
                inicio = flow_sender(contexto_inicio(texto))
                self.assertEqual(
                    "passar mais detalhes" in inicio["mensagem_bot"], texto != "Olá"
                )
                proxima = flow_sender(contexto_inicio("Maria", etapa=1))
            self.assertEqual(proxima["id_etapa_resultante"], 2)
            self.assertEqual(proxima["evento_transicao"], "nome_cliente_valido")
            self.assertEqual(proxima["primeiro_nome_cliente"], "Maria")
            self.assertTrue(
                proxima["mensagem_bot"].startswith(
                    "Prazer, Maria! ☺️\n\nO Supera"
                )
            )

    def test_tratamentos_especificos_mantem_prioridade(self):
        casos = (
            (
                "Posso ter mais informações sobre isso?",
                "image",
                "tipo_mensagem_nao_suportado",
            ),
            ("O que é o Supera? É reforço escolar?", "text", "duvida_reforco_escolar"),
            ("Quero informações sobre preços", "text", "pergunta_financeira"),
            ("É reforço escolar? Quanto custa?", "text", "duvida_reforco_escolar"),
        )
        for texto, tipo, tratamento in casos:
            for atual in (None, 1):
                with self.subTest(texto=texto, etapa=atual), patch.object(
                    cliente, "WhatsApp", return_value=cliente_simulado()
                ), patch.object(
                    resolver_etapa1, "validar_pedido_informacoes_supera"
                ) as classificar:
                    envio = flow_sender(contexto_inicio(texto, etapa=atual, tipo=tipo))
                classificar.assert_not_called()
                self.assertEqual(envio["tipo_tratamento"], tratamento)
                self.assertEqual(envio["id_etapa_resultante"], 1)
                self.assertNotIn("Hoje vou te ajudar a conhecer", envio["mensagem_bot"])

    def test_depois_da_abertura_nome_e_followup_nao_reapresentam_explicacao(self):
        with patch.object(
            cliente, "WhatsApp", return_value=cliente_simulado()
        ), patch.object(
            resolver_etapa1,
            "validar_pedido_informacoes_supera",
            side_effect=AssertionError("Só no primeiro contato"),
        ):
            envio = flow_sender(contexto_inicio("O que é o Supera?", etapa=1))
            self.assertEqual(envio["tipo_tratamento"], "nome_invalido")
            self.assertEqual(envio["id_etapa_resultante"], 1)
            self.assertNotIn("academia para o cérebro", envio["mensagem_bot"])
            contexto = contexto_followup()
            contexto["id_etapa_atual"] = 1
            contexto["dados_repeticao"]["nome_titular"] = "Nome antigo"
            contexto["mensagem_cliente_atual"]["conteudo_texto"] = "O que é o Supera?"
            retorno = enviar_repeticao_followup(contexto)
        self.assertEqual(
            retorno["mensagem_bot"],
            "Bom te ver novamente ☺️\n\n" + etapa1_messages.MENSAGEM_REPETICAO_ETAPA1,
        )
        self.assertNotIn("evento_transicao", retorno)

    def test_retry_reutiliza_resposta_salva_sem_reclassificar_ou_enviar(self):
        contexto = contexto_inicio("O que é o Supera?")
        contexto["resposta_bot_para_mensagem_atual"] = {
            "id_etapa": 1,
            "id_hash_msg": "wamid.salvo",
        }
        with patch.object(cliente, "WhatsApp") as wa, patch.object(
            resolver_etapa1, "validar_pedido_informacoes_supera"
        ) as classificar:
            envio = flow_sender(contexto)
        wa.assert_not_called()
        classificar.assert_not_called()
        self.assertTrue(envio["resposta_ja_existia"])
        self.assertFalse(envio["enviou"])

    def test_apresentacao_exige_dados_validos_antes_de_enviar(self):
        for campo in ("nome_unidade", "nome_agente", "genero"):
            with self.subTest(campo=campo):
                contexto = contexto_inicio("Do que se trata?")
                contexto[campo] = ""
                with patch.object(cliente, "WhatsApp") as wa:
                    with self.assertRaises(ValueError):
                        flow_sender(contexto)
                    wa.assert_not_called()
