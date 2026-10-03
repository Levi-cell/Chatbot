"""Contratos de mensagens e decisões na oferta da experiência Supera."""

import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from core.integrations.whatsapp.messages import etapa6_messages, etapa7_messages
from core.integrations.whatsapp.messages import etapa9_messages, etapa20_messages
from core.integrations.whatsapp.pywa_functions import cliente
from core.integrations.whatsapp.pywa_functions.pywa_senders import etapa7, etapa20
from core.repositories.atendimento.followup import buscar_contexto_repeticao
from tests.unit.test_followup import contexto as contexto_followup
from workers.worker_flow.response_flow import repeticao_followup
from workers.worker_flow.response_flow.etapas import resolver_etapa2, resolver_etapa7
from workers.worker_flow.response_flow.etapas import resolver_etapa17
from workers.worker_flow.response_flow.flow_sender import flow_sender
from workers.worker_flow.response_flow.etapas.validadores_contexto.valida_etapa2 import (
    validar_etapa2,
)
from workers.worker_flow.response_flow.etapas.validadores_contexto.valida_etapa7 import (
    validar_etapa7,
)
from workers.worker_flow.response_flow.etapas.validadores_contexto.valida_etapa9 import (
    validar_etapa9,
)
from workers.worker_flow.response_flow.etapas.validadores_contexto.valida_etapa20 import (
    validar_etapa20,
)
from workers.worker_flow.response_flow.etapas.validadores_contexto.validador_financeiro_etapa4 import (
    validar_pergunta_financeira_etapa4,
)
from workers.worker_flow.response_flow.etapas.validadores_universais.validador_financeiro import (
    validar_pergunta_financeira,
)

from core.integrations.whatsapp.messages import etapa1_messages as etapa1
from core.integrations.whatsapp.messages import etapa3_messages as etapa3
from core.integrations.whatsapp.messages.tratamentos.financeiro import (
    MENSAGEM_TRATAMENTO_FINANCEIRO,
)
from core.integrations.whatsapp.messages.tratamentos.midia import (
    MENSAGEM_TRATAMENTO_MIDIA_COM_BOTOES,
)
from core.integrations.whatsapp.messages.tratamentos.reforco_escolar import (
    MENSAGEM_TRATAMENTO_REFORCO_ESCOLAR,
)
from core.repositories.fluxo.contextos.etapa20 import buscar_contexto_etapa20
from core.repositories.fluxo.contextos.etapa6 import buscar_contexto_etapa6
from workers.worker_flow.response_flow.repeticao_followup import (
    enviar_repeticao_followup,
)


def contexto_resposta(etapa, texto, transicoes, *, dependente=False):
    return {
        "id_conversa": 1,
        "id_etapa_atual": etapa,
        "id_etapa_cliente": etapa,
        "id_etapa_origem_transicao": etapa,
        "transicoes_permitidas": transicoes,
        "texto_cliente_atual": texto,
        "tipo_mensagem_atual": "text",
        "status_dependente": dependente,
        "nome_titular": "Maria",
        "nome_dependente": "Lucas",
        "retry_count": 0,
        "resposta_bot_para_mensagem_atual": None,
        "mensagem_cliente_atual": {
            "cliente_telefone": "5511999999999",
            "id_phone_unidade": "phone",
            "id_mensagem_fila": 10,
            "id_hash_msg": "wamid.entrada",
        },
    }


class DestinoAtendimentoTests(unittest.TestCase):
    def test_negativa_sem_destino_alternativo_repete_pergunta(self):
        for texto in (
            "Não é para mim",
            "não é para meu filho",
            "Não para minha mãe",
            "não é para a minha filha",
            "não é para um dependente",
            "não é para outra pessoa",
            "não",
        ):
            with self.subTest(texto=texto):
                self.assertIsNone(validar_etapa2(texto))

    def test_destino_explicito_e_correcao_com_virgula_continuam_validos(self):
        casos = {
            "Para mim": "para_mim",
            "Para um dependente": "para_outra_pessoa",
            "Não, é para mim": "para_mim",
            "não, para minha filha": "para_outra_pessoa",
            "Não é para mim, é para meu filho": "para_outra_pessoa",
            "É para minha mãe": "para_outra_pessoa",
            "meu neto": "para_outra_pessoa",
        }
        for texto, esperado in casos.items():
            with self.subTest(texto=texto):
                self.assertEqual(validar_etapa2(texto), esperado)

    def test_negativa_nao_gera_evento_nem_escolha_de_destino(self):
        ctx = contexto_resposta(
            2, "Não é para mim", {"destino_atendimento_definido": 3}
        )
        with patch.object(
            resolver_etapa2,
            "enviar_etapa2_contexto_opcao_invalida",
            return_value={"id_etapa_resultante": 2, "tratamento": True},
        ), patch.object(resolver_etapa2, "enviar_etapa3") as confirmar:
            envio = resolver_etapa2.resolve_etapa2(ctx)
        confirmar.assert_not_called()
        self.assertTrue(envio["tratamento"])
        self.assertNotIn("evento_transicao", envio)
        self.assertNotIn("status_dependente", envio)


class GratuidadeExperienciaTests(unittest.TestCase):
    def test_duvida_explicita_sobre_a_atividade_inclusive_na_profissao(self):
        for texto in (
            "A demonstração prática é gratuita?",
            "A experiência Supera é gratuita",
            "É gratuita a demonstração?",
            "Demonstração gratuita?",
        ):
            with self.subTest(texto=texto):
                self.assertTrue(validar_pergunta_financeira(texto))
                self.assertTrue(validar_pergunta_financeira_etapa4(texto))

    def test_pergunta_curta_exige_contexto_de_oferta(self):
        for texto in ("É gratuita?", "Gratuita mesmo?", "Quero reservar, é gratuita?"):
            with self.subTest(texto=texto):
                self.assertFalse(validar_pergunta_financeira(texto))
                self.assertTrue(
                    validar_pergunta_financeira(texto, referencia_experiencia=True)
                )
        for texto in (
            "A consulta médica é gratuita?",
            "Quero reservar minha experiência Supera gratuita",
            "Trabalho com distribuição gratuita de alimentos",
        ):
            with self.subTest(texto=texto):
                self.assertFalse(
                    validar_pergunta_financeira(texto, referencia_experiencia=True)
                )
                self.assertFalse(validar_pergunta_financeira_etapa4(texto))

    def test_duvida_na_oferta_recebe_esclarecimento_sem_avancar(self):
        wa = MagicMock()
        wa.send_message.return_value = SimpleNamespace(id="wamid.financeiro")
        for dependente in (False, True):
            ctx = contexto_resposta(
                7,
                "Quero reservar, é gratuita?",
                {"oferta_aceita": 10},
                dependente=dependente,
            )
            with self.subTest(dependente=dependente), patch.object(
                cliente, "WhatsApp", return_value=wa
            ):
                envio = resolver_etapa7.resolve_etapa7(ctx)
            self.assertEqual(envio["id_etapa_resultante"], 7)
            self.assertEqual(envio["tipo_tratamento"], "pergunta_financeira")
            self.assertNotIn("evento_transicao", envio)
            self.assertIn("*experiência supera*", envio["mensagem_bot"].casefold())
            self.assertEqual(envio["mensagem_bot"].count("por cortesia da unidade"), 1)
            self.assertIn("valores de investimento", envio["mensagem_bot"])


class MensagensReservaTests(unittest.TestCase):
    def test_transicao_para_oferta_separa_titular_e_participante(self):
        for dependente in (False, True):
            for prefixo in (None, "Olá novamente, Maria!\n\n"):
                with self.subTest(dependente=dependente, prefixo=prefixo):
                    cursor = MagicMock()
                    cursor.fetchone.return_value = (
                        "5571999999999",
                        False,
                        None,
                        "Maria",
                        "Lucas",
                        "Suh",
                        "feminino",
                        "Supera Teste",
                    )
                    ctx = contexto_resposta(
                        6,
                        "12" if dependente else "40",
                        {"idade_valida": 7},
                        dependente=dependente,
                    )
                    ctx.update(buscar_contexto_etapa6(1, 2, cursor))
                    ctx["saudacao_retorno"] = prefixo
                    self.assertEqual(cursor.execute.call_args.args[1], (1, 2))
                    wa = cliente_simulado()
                    with patch.object(cliente, "WhatsApp", return_value=wa):
                        envio = flow_sender(ctx)
                    texto = envio["mensagem_bot"]
                    self.assertEqual(envio["id_etapa_resultante"], 7)
                    self.assertEqual(envio["evento_transicao"], "idade_valida")
                    self.assertEqual(envio["idade_aluno"], 12 if dependente else 40)
                    wa.send_message.assert_called_once()
                    self.assertEqual(texto, wa.send_message.call_args.kwargs["text"])
                    self.assertEqual(texto.count("Olá novamente"), int(bool(prefixo)))
                    oferta = texto.removeprefix(prefixo or "")
                    self.assertTrue(oferta.startswith("Maravilha, Maria!"))
                    self.assertEqual(oferta.count("Maravilha"), 1)
                    paragrafos = oferta.split("\n\n")
                    self.assertEqual(paragrafos[0].strip(), "Maravilha, Maria! ☺️")
                    self.assertIn(
                        "*demonstração prática* por cortesia da unidade", paragrafos[1]
                    )
                    self.assertIn("*experiência Supera exclusiva*", oferta)
                    self.assertNotIn("{nome", oferta)
                    self.assertEqual("Lucas" in oferta, dependente)
                    self.assertIn(
                        (
                            "Lucas também participará"
                            if dependente
                            else "Você também participará"
                        ),
                        oferta,
                    )
                    self.assertEqual(
                        [b.title for b in wa.send_message.call_args.kwargs["buttons"]],
                        ["Reservar agora", "Talvez mais tarde"],
                    )
                    self.assertEqual(texto.count(envio["rodape_mensagem"]), 1)

    def test_oferta_sem_nome_nao_envia_e_retry_preserva_resposta_existente(self):
        for dependente in (False, True):
            for campo in (
                ("nome_titular", "nome_dependente") if dependente else ("nome_titular",)
            ):
                for valor in (None, "", "   "):
                    with self.subTest(dependente=dependente, campo=campo, valor=valor):
                        ctx = contexto_resposta(
                            6, "40", {"idade_valida": 7}, dependente=dependente
                        )
                        ctx.update(idade_minima_suporte=None, bpa_ativo_unidade=False)
                        ctx[campo] = valor
                        with patch.object(cliente, "WhatsApp") as enviar:
                            with self.assertRaisesRegex(ValueError, campo):
                                flow_sender(ctx)
                            enviar.assert_not_called()
                        ctx["resposta_bot_para_mensagem_atual"] = {
                            "id_etapa": 7,
                            "id_hash_msg": "wamid.oferta.persistida",
                        }
                        with patch.object(cliente, "WhatsApp") as enviar:
                            envio = flow_sender(ctx)
                            enviar.assert_not_called()
                        self.assertTrue(envio["resposta_ja_existia"])
                        self.assertEqual(
                            envio["id_hash_msg_bot"], "wamid.oferta.persistida"
                        )

    def test_dependente_continua_sendo_quem_participa(self):
        oferta = etapa7_messages.montar_mensagem_oferta_dependente_etapa7(
            nome_titular="Maria", nome_dependente="Lucas"
        )
        self.assertIn("presentear Lucas", oferta)
        self.assertIn("*experiência Supera exclusiva* de Lucas?", oferta)
        self.assertIn("Lucas também participará", oferta)
        self.assertNotIn("Você também participará", oferta)
        financeiro = etapa6_messages.montar_mensagem_idade_dependente_etapa6_financeiro(
            "Lucas"
        )
        self.assertIn("*experiência supera*", financeiro.casefold())
        self.assertIn("qual é a idade de Lucas?", financeiro)
        retorno = etapa9_messages.montar_mensagem_retorno_dependente_etapa9(
            "Maria", "Lucas"
        )
        self.assertIn("*momento Supera* de Lucas", retorno)
        self.assertNotIn("*momento Supera* de Maria", retorno)

    def test_fim_da_triagem_apresenta_reserva_para_o_participante_correto(self):
        for dependente in (False, True):
            with self.subTest(dependente=dependente):
                ctx = contexto_resposta(
                    17,
                    "Nunca",
                    {"triagem_pergunta_6_respondida": 20},
                    dependente=dependente,
                )
                ctx.update(
                    idade_pessoa_triagem=12 if dependente else 40,
                    link_agendamento_unidade="https://example.com/horarios",
                )
                wa = MagicMock()
                wa.send_message.return_value = SimpleNamespace(id="wamid.reserva")
                with patch.object(cliente, "WhatsApp", return_value=wa):
                    envio = resolver_etapa17.resolve_etapa17(ctx)
                self.assertEqual(envio["id_etapa_resultante"], 20)
                self.assertEqual(
                    envio["evento_transicao"], "triagem_pergunta_6_respondida"
                )
                self.assertEqual(wa.send_message.call_count, 1)
                self.assertEqual(
                    wa.send_message.call_args.kwargs["text"], envio["mensagem_bot"]
                )
                experiencia = (
                    "o *momento Supera* de Lucas"
                    if dependente
                    else "seu *momento Supera*"
                )
                self.assertIn(f"Para reservar {experiencia}", envio["mensagem_bot"])
                self.assertNotIn("{", envio["mensagem_bot"])
                if not dependente:
                    self.assertNotIn("Lucas", envio["mensagem_bot"])

    def test_texto_enviado_e_historico_permanecem_identicos(self):
        for modulo, enviar, extra in (
            (etapa7, etapa7.enviar_etapa7_cliente, "Maria"),
            (etapa20, etapa20.enviar_etapa20, "https://example.com/horarios"),
        ):
            with self.subTest(modulo=modulo.__name__):
                wa = MagicMock()
                wa.send_message.return_value = SimpleNamespace(id="wamid.novo")
                with patch.object(modulo, "conta_wa", return_value=wa):
                    envio = enviar("5511999999999", "phone", extra)
                self.assertEqual(
                    wa.send_message.call_args.kwargs["text"], envio["mensagem_bot"]
                )
                self.assertIn(
                    (
                        "*demonstração prática* por cortesia da unidade"
                        if modulo is etapa7
                        else "*momento Supera*"
                    ),
                    envio["mensagem_bot"],
                )
                self.assertNotRegex(
                    envio["mensagem_bot"].lower(),
                    r"agendamento|aula\s+\*?gratuita",
                )

    def test_followup_mantem_etapa_e_envia_uma_unica_saudacao(self):
        for numero in (7, 9, 20):
            for dependente in (False, True):
                with self.subTest(etapa=numero, dependente=dependente):
                    ctx = contexto_followup()
                    ctx["id_etapa_atual"] = numero
                    ctx["dados_repeticao"].update(
                        status_dependente=dependente,
                        nome_titular="Maria",
                        nome_dependente="Lucas",
                    )
                    wa = MagicMock()
                    wa.send_message.return_value = SimpleNamespace(id="wamid.followup")
                    with patch.object(cliente, "WhatsApp", return_value=wa):
                        envio = repeticao_followup.enviar_repeticao_followup(ctx)
                    self.assertEqual(envio["id_etapa_resultante"], numero)
                    self.assertEqual(wa.send_message.call_count, 1)
                    self.assertEqual(
                        wa.send_message.call_args.kwargs["text"], envio["mensagem_bot"]
                    )
                    self.assertEqual(envio["mensagem_bot"].count("novamente"), 1)
                    self.assertIn(
                        (
                            "experiência Supera exclusiva"
                            if numero == 7
                            else "momento Supera"
                        ),
                        envio["mensagem_bot"],
                    )
                    self.assertNotIn("evento_transicao", envio)
                    self.assertNotIn("por cortesia da unidade", envio["mensagem_bot"])
                    if numero == 20:
                        experiencia = (
                            "o *momento Supera* de Lucas"
                            if dependente
                            else "seu *momento Supera*"
                        )
                        self.assertIn(
                            f"Para reservar {experiencia}", envio["mensagem_bot"]
                        )

    def test_retorno_da_espera_preserva_uma_saudacao_com_ou_sem_inatividade(self):
        for dependente in (False, True):
            for saudacao in (None, "Olá novamente, Maria!\n\n"):
                with self.subTest(dependente=dependente, saudacao=saudacao):
                    ctx = contexto_resposta(
                        8, "Olá", {"cliente_retornou": 9}, dependente=dependente
                    )
                    ctx["saudacao_retorno"] = saudacao
                    wa = MagicMock()
                    wa.send_message.return_value = SimpleNamespace(id="wamid.retorno")
                    with patch.object(cliente, "WhatsApp", return_value=wa):
                        envio = flow_sender(ctx)
                    self.assertEqual(envio["id_etapa_resultante"], 9)
                    self.assertEqual(envio["mensagem_bot"].count("novamente"), 1)
                    self.assertEqual(
                        wa.send_message.call_args.kwargs["text"], envio["mensagem_bot"]
                    )

    def test_resposta_persistida_nao_envia_novamente(self):
        ctx = contexto_followup()
        ctx["resposta_bot_para_mensagem_atual"] = {"id_hash_msg": "wamid.antigo"}
        with patch.object(repeticao_followup, "_selecionar_sender") as selecionar:
            envio = repeticao_followup.enviar_repeticao_followup(ctx)
        selecionar.assert_not_called()
        self.assertFalse(envio["enviou"])
        self.assertEqual(envio["id_hash_msg_bot"], "wamid.antigo")

    def test_contexto_repeticao_preserva_barreira_terminal_sem_responsavel(self):
        cursor = MagicMock()
        cursor.fetchone.return_value = (
            "Titular",
            "Aluno",
            12,
            "Unidade",
            "Bot",
            "masculino",
            "https://example.com",
            None,
            True,
            "tarde",
            35,
            "5511999990000",
            False,
        )
        dados = buscar_contexto_repeticao(8, 2, cursor)
        self.assertTrue(dados["status_dependente"])
        self.assertEqual(cursor.execute.call_args.args[1], (8, 2))
        cursor.fetchone.return_value = (*cursor.fetchone.return_value[:-1], True)
        with self.assertRaises(ValueError):
            buscar_contexto_repeticao(8, 2, cursor)


class AceiteReservaTests(unittest.TestCase):
    def test_botao_novo_e_textos_legados_preservam_o_aceite_flexivel(self):
        for validar, esperado in (
            (validar_etapa7, "oferta_aceita"),
            (validar_etapa9, "retorno_confirmado"),
        ):
            for texto in (
                "Reservar agora",
                "  RESERVAR agora!  ",
                "Quero reservar",
                "quero",
                "Quero agendar",
                "Pode reservar",
                "sim",
                "Quero reservar!",
                "Não há problema, quero reservar",
                "Quero pensar melhor",
                "Gostaria de desistir",
            ):
                with self.subTest(validador=validar.__name__, texto=texto):
                    self.assertEqual(validar(texto), esperado)
            for texto in (
                "não quero reservar agora",
                "como reservar agora?",
                "quero saber como reservar agora",
                "não quero reservar",
                "como reservar?",
                "quero saber como reservar",
                "quero mais informações",
                "Quero cancelar",
            ):
                with self.subTest(validador=validar.__name__, texto=texto):
                    self.assertIsNone(validar(texto))
        self.assertEqual(validar_etapa7("Talvez mais tarde"), "oferta_adiada")
        self.assertEqual(validar_etapa9("Talvez mais tarde"), "retorno_adiado")

    def test_etapa20_so_avanca_com_conclusao(self):
        for texto in (
            *etapa20_messages.montar_botoes_etapa20(),
            "já reservei!",
            "Já agendei",
            "agendamento feito",
        ):
            self.assertEqual(validar_etapa20(texto), "agendamento_confirmado")
        for texto in (
            "Reservar agora",
            "Quero reservar",
            "Quero agendar",
            "não reservei",
            "vou reservar",
            "sim",
        ):
            self.assertIsNone(validar_etapa20(texto))


def cliente_simulado():
    wa = MagicMock()
    wa.send_message.return_value = SimpleNamespace(id="wamid.composicao")
    return wa


class ComposicaoTratamentosTests(unittest.TestCase):
    def test_confirmacao_reutiliza_repeticao_e_mantem_destinatario(self):
        for dependente in (False, True):
            repeticao = etapa3.montar_mensagem_etapa3(dependente, repeticao=True)
            for montar, prefixo in (
                (
                    etapa3.montar_mensagem_financeiro_etapa3,
                    MENSAGEM_TRATAMENTO_FINANCEIRO,
                ),
                (
                    etapa3.montar_mensagem_midia_etapa3,
                    MENSAGEM_TRATAMENTO_MIDIA_COM_BOTOES,
                ),
                (
                    etapa3.montar_mensagem_reforco_escolar_etapa3,
                    MENSAGEM_TRATAMENTO_REFORCO_ESCOLAR,
                ),
            ):
                with self.subTest(dependente=dependente, montar=montar.__name__):
                    mensagem = montar(dependente)
                    self.assertTrue(mensagem.startswith(prefixo))
                    self.assertTrue(mensagem.endswith(repeticao))
                    self.assertEqual(mensagem.count(repeticao), 1)
                    self.assertNotIn("Você confirma", mensagem)
                    self.assertEqual("um dependente" in mensagem, dependente)

    def test_etapa1_apresenta_uma_vez_e_depois_so_retoma_pergunta(self):
        for motivo in ("midia", "financeiro", "reforco_escolar"):
            with self.subTest(motivo=motivo):
                inicio = getattr(etapa1, f"montar_mensagem_{motivo}_inicio")(
                    "Boa tarde",
                    "Supera Teste",
                    "Mia",
                    "feminino",
                )
                repeticao = getattr(etapa1, f"montar_mensagem_{motivo}_etapa1")()
                self.assertEqual(inicio.count("Sou a Mia"), 1)
                self.assertEqual(inicio.count(etapa1.MENSAGEM_REPETICAO_ETAPA1), 1)
                self.assertIn(repeticao, inicio)
                self.assertNotIn("Sou a Mia", repeticao)
                self.assertNotIn(
                    "opções abaixo", repeticao
                )  # Coleta de nome não tem botões.

    def test_inatividade_compoe_tratamentos_mas_ainda_permite_avancar(self):
        casos = (
            ("Quero reservar", "text", 10, None),
            ("Quanto custa?", "text", 7, "pergunta_financeira"),
            ("É reforço escolar?", "text", 7, "duvida_reforco_escolar"),
            ("", "image", 7, "tipo_mensagem_nao_suportado"),
            ("batata", "text", 7, "opcao_invalida"),
        )
        for dependente in (False, True):
            for texto, tipo, destino, tratamento in casos:
                with self.subTest(dependente=dependente, texto=texto, tipo=tipo):
                    ctx = contexto_resposta(
                        7, texto, {"oferta_aceita": 10}, dependente=dependente
                    )
                    ctx.update(
                        tipo_mensagem_atual=tipo,
                        saudacao_retorno="Olá novamente, Maria!\n\n",
                    )
                    wa = cliente_simulado()
                    with patch.object(cliente, "WhatsApp", return_value=wa):
                        envio = flow_sender(ctx)
                    self.assertEqual(envio["id_etapa_resultante"], destino)
                    self.assertEqual(envio["mensagem_bot"].count("Olá novamente"), 1)
                    self.assertEqual(
                        envio["mensagem_bot"], wa.send_message.call_args.kwargs["text"]
                    )
                    if tratamento:
                        self.assertEqual(
                            envio["mensagem_bot"].count("por cortesia da unidade"),
                            1 if tratamento == "pergunta_financeira" else 0,
                        )
                        self.assertEqual(envio["tipo_tratamento"], tratamento)
                        self.assertNotIn("evento_transicao", envio)
                        self.assertNotIn("Maravilha", envio["mensagem_bot"])
                        self.assertEqual("Lucas" in envio["mensagem_bot"], dependente)
                    else:
                        self.assertEqual(envio["evento_transicao"], "oferta_aceita")

    def test_followup_nao_repete_apresentacao_nem_despedida(self):
        for numero in (1, 2, 7):
            for entrada in ("Quanto custa?", "Quero reservar", ""):
                with self.subTest(etapa=numero, entrada=entrada):
                    ctx = contexto_followup()
                    ctx["id_etapa_atual"] = numero
                    ctx["mensagem_cliente_atual"]["conteudo_texto"] = entrada
                    wa = cliente_simulado()
                    with patch.object(cliente, "WhatsApp", return_value=wa):
                        envio = enviar_repeticao_followup(ctx)
                    mensagem = envio["mensagem_bot"]
                    self.assertEqual(envio["id_etapa_resultante"], numero)
                    self.assertNotIn("evento_transicao", envio)
                    self.assertNotIn("tratamento", envio)
                    self.assertEqual(mensagem, wa.send_message.call_args.kwargs["text"])
                    for indevido in (
                        "Prazer,",
                        "nos falamos novamente em breve",
                        "Maravilha",
                        "assistente do",
                        "valores de investimento",
                    ):
                        self.assertNotIn(indevido, mensagem)

    def test_reserva_em_tratamento_preserva_dependente_e_prefixo(self):
        for dependente in (False, True):
            for texto, tipo in (
                ("Quanto custa?", "text"),
                ("É reforço escolar?", "text"),
                ("", "image"),
                ("Ainda não reservei", "text"),
            ):
                with self.subTest(dependente=dependente, texto=texto, tipo=tipo):
                    ctx = contexto_resposta(
                        20, texto, {"agendamento_confirmado": 21}, dependente=dependente
                    )
                    ctx.update(
                        tipo_mensagem_atual=tipo,
                        link_agendamento_unidade="https://example.com",
                        saudacao_retorno="Olá novamente, Maria!\n\n",
                    )
                    wa = cliente_simulado()
                    with patch.object(cliente, "WhatsApp", return_value=wa):
                        envio = flow_sender(ctx)
                    self.assertEqual(envio["id_etapa_resultante"], 20)
                    self.assertEqual(
                        envio["mensagem_bot"].count("por cortesia da unidade"),
                        1 if texto == "Quanto custa?" else 0,
                    )
                    self.assertNotIn("evento_transicao", envio)
                    self.assertEqual("de Lucas" in envio["mensagem_bot"], dependente)
                    self.assertEqual(
                        envio["mensagem_bot"].count("https://example.com"), 1
                    )
                    self.assertEqual(
                        envio["mensagem_bot"], wa.send_message.call_args.kwargs["text"]
                    )


class ContextoReservaTests(unittest.TestCase):
    def test_rele_participante_da_mesma_conversa_e_unidade(self):
        for dependente in (False, True):
            cursor = MagicMock()
            cursor.fetchone.return_value = (
                "https://example.com",
                "Maria",
                dependente,
                "Lucas",
            )
            dados = buscar_contexto_etapa20(10, 2, cursor)
            self.assertEqual(dados["nome_dependente"], "Lucas" if dependente else None)
            sql, params = cursor.execute.call_args.args
            self.assertEqual(params, (10, 2))
            self.assertIn("d.id_conversa = c.id_conversa", sql)
            self.assertIn("c.id_unidade = %s", sql)

    def test_dependente_sem_nome_nao_vira_mensagem_para_titular(self):
        cursor = MagicMock()
        cursor.fetchone.return_value = ("https://example.com", "Maria", True, None)
        with self.assertRaisesRegex(ValueError, "Nome do dependente"):
            buscar_contexto_etapa20(10, 2, cursor)
