"""Caminhos com/sem link e recuperação sem efeitos duplicados ou envios reais."""

import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from urllib.parse import parse_qs, urlparse

from django.core.exceptions import ValidationError
from webhook.models import Unidade
from core.database.deploy_database.etapa_transicao_script import (
    TRANSICOES_INICIAIS as TRANSICOES,
)
from core.database.deploy_database.povoar_etapas import ETAPAS
from core.integrations.whatsapp.pywa_functions import cliente
from core.integrations.whatsapp.messages.contato_comercial import (
    montar_mensagem_contato_comercial,
)
from core.integrations.whatsapp.numero_comercial import (
    montar_link_numero_comercial_whatsapp,
)
from core.integrations.funil.oportunidades import montar_observacoes_lead
from core.repositories.atendimento.turnos import salvar_turno_conversa
from core.repositories.fluxo.contextos.etapa18 import buscar_contexto_etapa18
from workers.worker_flow.response_flow.etapas import (
    resolver_etapa17,
    resolver_etapa18,
    resolver_etapa19,
)
from workers.worker_flow.response_flow.etapas.validadores_contexto.valida_etapa18 import (
    validar_etapa18,
)
from workers.worker_flow.response_flow.flow_sender import flow_sender
from workers.worker_flow.response_flow.repeticao_followup import (
    enviar_repeticao_followup,
)
from workers.worker_flow.transacoes import efeitos_transicao as efeitos
from tests.unit.test_followup import contexto as contexto_followup
from tests.unit.test_suporte_idoso_email_obrigatorio import dados_lead


def contexto(etapa, texto, *, link=None, dependente=False):
    return {
        "id_conversa": 10,
        "id_unidade": 2,
        "id_cliente": 3,
        "id_etapa_atual": etapa,
        "id_etapa_cliente": etapa,
        "id_etapa_origem_transicao": etapa,
        "retry_count": 1,
        "transicoes_permitidas": {
            evento: destino for origem, evento, destino in TRANSICOES if origem == etapa
        },
        "texto_cliente_atual": texto,
        "tipo_mensagem_atual": "text",
        "status_dependente": dependente,
        "nome_cliente": "Ana",
        "nome_dependente": "João" if dependente else None,
        "idade_cliente": 40,
        "idade_dependente": 12 if dependente else None,
        "idade_pessoa_triagem": 12 if dependente else 40,
        "nome_agente_unidade": "Suh",
        "genero_agente_unidade": "feminino",
        "numero_comercial_unidade": "5571999999999",
        "link_agendamento_unidade": link,
        "turno": "manha",
        "resposta_bot_para_mensagem_atual": None,
        "mensagem_cliente_atual": {
            "id_mensagem": 9,
            "id_mensagem_fila": 8,
            "id_hash_msg": "wamid.cliente",
            "cliente_telefone": "5571888888888",
            "id_phone_unidade": "phone",
        },
    }


class TurnoTests(unittest.TestCase):
    def test_opcoes_e_frases_com_um_turno(self):
        for texto, esperado in (
            ("Pela manhã", "manha"),
            ("Posso pela manha", "manha"),
            ("amanhã pela tarde", "tarde"),
            ("somente pela noite", "noite"),
            ("manhã, prefiro manhã", "manha"),
            ("pela TARDE", "tarde"),
        ):
            for tipo in ("text", "interactive", "interactive_button"):
                with self.subTest(texto=texto, tipo=tipo):
                    self.assertEqual(validar_etapa18(texto, tipo), esperado)

    def test_negações_multiplos_turnos_e_ausencia_nao_passam(self):
        for texto in (
            "",
            "amanhã",
            "Sim",
            "manhã ou tarde",
            "tarde e noite",
            "manhã tarde noite",
            "não posso de manhã",
            "nao pela noite",
            "n posso a tarde",
            "nunca à tarde",
            "qualquer turno",
            "talvez de manhã",
            "tem horário pela manhã?",
            "sem manhã",
        ):
            with self.subTest(texto=texto):
                self.assertIsNone(validar_etapa18(texto))
        self.assertIsNone(validar_etapa18("Pela manhã", "audio"))

    def test_unidade_sem_link_exige_contato_e_normaliza_vazio(self):
        for link in (None, "", "   "):
            unidade = Unidade(link_agendamento=link, numero_comercial="(71) 99999-9999")
            unidade.clean()
            self.assertIsNone(unidade.link_agendamento)
            unidade.numero_comercial = None
            with self.assertRaises(ValidationError):
                unidade.clean()

    def test_repositorio_restringe_conversa_unidade_e_turno(self):
        cursor = MagicMock()
        cursor.fetchone.return_value = ("manha",)
        self.assertEqual(
            salvar_turno_conversa(10, 2, "manha", cursor)["turno"], "manha"
        )
        self.assertEqual(cursor.execute.call_args.args[1], ("manha", 10, 2, "manha"))
        cursor.fetchone.return_value = None
        with self.assertRaises(ValueError):
            salvar_turno_conversa(10, 2, "tarde", cursor)
        for invalido in (None, "manhã", "manha,tarde", "", "outro"):
            with self.subTest(invalido=invalido), self.assertRaises(ValueError):
                salvar_turno_conversa(10, 2, invalido, cursor)

    def test_contexto_usa_unidade_atual_e_nao_cache(self):
        cursor = MagicMock()
        cursor.fetchone.return_value = (
            None,
            "5571999999999",
            "Suh",
            "feminino",
            "Ana",
            40,
            None,
            None,
            False,
            None,
        )
        sem = buscar_contexto_etapa18(10, 2, cursor)
        self.assertIsNone(sem["link_agendamento_unidade"])
        cursor.fetchone.return_value = (
            "https://example.com",
            *cursor.fetchone.return_value[1:],
        )
        com = buscar_contexto_etapa18(10, 2, cursor)
        self.assertEqual(com["link_agendamento_unidade"], "https://example.com")
        self.assertEqual(cursor.execute.call_args.args[1], (10, 2))


class FluxoReservaTests(unittest.TestCase):
    def setUp(self):
        self.http = MagicMock()
        self.http.send_message.return_value = SimpleNamespace(id="wamid.bot")
        p = patch.object(cliente, "WhatsApp", return_value=self.http)
        p.start()
        self.addCleanup(p.stop)

    def test_rotas_17_preservam_sexta_resposta(self):
        for dependente in (False, True):
            for link, destino in ((None, 18), ("https://example.com", 20)):
                with self.subTest(dependente=dependente, link=link):
                    ctx = contexto(17, "Nunca", link=link, dependente=dependente)
                    envio = resolver_etapa17.resolve_etapa17(ctx)
                    self.assertEqual(envio["id_etapa_resultante"], destino)
                    self.assertEqual(envio["resposta_triagem"], "nunca")
                    with patch.object(
                        efeitos,
                        "registrar_resposta_triagem",
                        return_value={"inserido": True},
                    ) as salvar:
                        efeitos.atualizar_banco_conforme_transicao_de_etapa(
                            ctx, envio, object()
                        )
                        self.assertEqual(salvar.call_args.args[:3], (10, 17, "nunca"))

    def test_etapa18_so_transita_depois_de_uma_escolha(self):
        for dependente in (False, True):
            for texto, turno in (
                ("Pela manhã", "manha"),
                ("Posso pela tarde", "tarde"),
                ("pela noite", "noite"),
            ):
                ctx = contexto(18, texto, dependente=dependente)
                envio = resolver_etapa18.resolve_etapa18(ctx)
                self.assertEqual(envio["id_etapa_resultante"], 19)
                self.assertEqual(envio["turno"], turno)
                botao = self.http.send_message.call_args.kwargs["buttons"]
                pretexto = parse_qs(urlparse(botao.url).query)["text"][0]
                self.assertIn(
                    "João, que tem 12 anos" if dependente else "tenho 40 anos", pretexto
                )
                self.assertIn("turno da ", pretexto)
                self.assertIn("experiência Supera gratuita", envio["mensagem_bot"])

    def test_tratamentos_permanecem_na18_sem_efeito(self):
        for texto, tipo, tratamento in (
            ("manha e tarde", "text", "contexto_invalido"),
            ("Pela manhã ou pela noite", "interactive", "contexto_invalido"),
            ("Talvez pela tarde", "interactive_button", "contexto_invalido"),
            ("Eu trabalho à tarde", "text", "contexto_invalido"),
            ("Não sei", "text", "contexto_invalido"),
            ("Pela manhã", "audio", "midia"),
            ("quanto custa?", "text", "financeiro"),
            ("vocês fazem reforço escolar?", "text", "reforco_escolar"),
        ):
            ctx = contexto(18, texto)
            ctx["tipo_mensagem_atual"] = tipo
            envio = resolver_etapa18.resolve_etapa18(ctx)
            self.assertEqual(envio["id_etapa_resultante"], 18)
            self.assertEqual(envio["tipo_tratamento"], tratamento)
            self.assertNotIn("evento_transicao", envio)
            self.assertNotIn("turno", envio)
            if tratamento == "contexto_invalido":
                self.assertIn("*apenas um turno*", envio["mensagem_bot"])
            with patch.object(efeitos, "salvar_turno_conversa") as salvar:
                efeitos.atualizar_banco_conforme_transicao_de_etapa(
                    ctx, envio, object()
                )
                salvar.assert_not_called()

    def test_19_apresenta_pergunta_sem_consumir_nota(self):
        for texto in ("oi", "5", "não", "quanto custa?"):
            ctx = contexto(19, texto)
            envio = resolver_etapa19.resolve_etapa19(ctx)
            self.assertEqual(envio["id_etapa_resultante"], 21)
            self.assertNotIn("nota_satisfacao", envio)
            with patch.object(efeitos, "salvar_nota_satisfacao") as salvar:
                efeitos.atualizar_banco_conforme_transicao_de_etapa(
                    ctx, envio, object()
                )
                salvar.assert_not_called()

    def test_link_adicionado_nao_redireciona_quem_ja_chegou18_ou19(self):
        envio = resolver_etapa18.resolve_etapa18(
            contexto(18, "manhã", link="https://example.com")
        )
        self.assertEqual(envio["id_etapa_resultante"], 19)
        envio = resolver_etapa19.resolve_etapa19(
            contexto(19, "ok", link="https://example.com")
        )
        self.assertEqual(envio["id_etapa_resultante"], 21)

    def test_replay_reconstroi_turno_sem_novo_envio(self):
        ctx = contexto(18, "Posso pela noite")
        ctx["resposta_bot_para_mensagem_atual"] = {
            "id_etapa": 19,
            "id_hash_msg": "wamid.persistido",
        }
        envio = flow_sender(ctx)
        self.http.send_message.assert_not_called()
        self.assertEqual(envio["evento_transicao"], "turno_escolhido")
        cursor = MagicMock()
        cursor.fetchone.return_value = ("noite",)
        efeito = efeitos.atualizar_banco_conforme_transicao_de_etapa(ctx, envio, cursor)
        self.assertEqual(efeito["turno"], "noite")

    def test_replay_de_botao_reconstroi_preferencia_sem_reenviar(self):
        for tipo in ("interactive", "interactive_button"):
            for texto, turno in (("Pela manhã", "manha"), ("Pela tarde", "tarde"), ("Pela noite", "noite")):
                with self.subTest(tipo=tipo, texto=texto):
                    ctx = contexto(18, texto)
                    ctx["tipo_mensagem_atual"] = tipo
                    ctx["resposta_bot_para_mensagem_atual"] = {
                        "id_etapa": 19, "id_hash_msg": "wamid.persistido",
                    }
                    envio = flow_sender(ctx)
                    self.http.send_message.assert_not_called()
                    cursor = MagicMock()
                    cursor.fetchone.return_value = (turno,)
                    efeito = efeitos.atualizar_banco_conforme_transicao_de_etapa(ctx, envio, cursor)
                    self.assertEqual(efeito["turno"], turno)

    def test_tipos_interativos_equivalentes_nas_outras_etapas_com_botoes(self):
        for tipo in ("interactive", "interactive_button"):
            for etapa, texto, destino in (
                (3, "Não", 4), (11, "Começar triagem", 12), (12, "Nunca", 13),
                (17, "Nunca", 18), (19, "ok", 21), (20, "Já reservei", 21),
                (21, "5", 22), (22, "Sim", 23), (22, "Não", 24),
            ):
                with self.subTest(tipo=tipo, etapa=etapa):
                    ctx = contexto(etapa, texto, link="https://example.com" if etapa == 20 else None)
                    ctx["tipo_mensagem_atual"] = tipo
                    envio = flow_sender(ctx)
                    self.assertEqual(envio["id_etapa_resultante"], destino)

    def test_replay17_respeita_resposta_ja_enviada_apos_adicao_link(self):
        ctx = contexto(17, "Nunca", link="https://example.com")
        ctx["resposta_bot_para_mensagem_atual"] = {
            "id_etapa": 18,
            "id_hash_msg": "wamid.persistido",
        }
        envio = flow_sender(ctx)
        self.assertEqual(envio["evento_transicao"], "triagem_concluida_sem_link")
        self.http.send_message.assert_not_called()

    def test_followup18_valida_escolha_e_avanca_sem_perder_prefixo(self):
        from workers.worker_flow.response_flow.retomada_followup import enviar_retorno_followup

        ctx = contexto(18, "Pela manhã")
        ctx["retorno_followup"] = True
        ctx["dados_repeticao"] = contexto_followup()["dados_repeticao"]
        envio = enviar_retorno_followup(ctx)
        self.assertEqual(envio["id_etapa_resultante"], 19)
        self.assertEqual(envio["turno"], "manha")
        self.assertEqual(envio["evento_transicao"], "turno_escolhido")
        self.assertIn("Bom te ver novamente", envio["mensagem_bot"])
        with patch.object(efeitos, "salvar_turno_conversa") as salvar:
            efeitos.atualizar_banco_conforme_transicao_de_etapa(ctx, envio, object())
        salvar.assert_called_once()

    def test_followup18_invalido_apenas_repete(self):
        from workers.worker_flow.response_flow.retomada_followup import enviar_retorno_followup

        ctx = contexto(18, "qualquer horário")
        ctx["retorno_followup"] = True
        ctx["dados_repeticao"] = contexto_followup()["dados_repeticao"]
        envio = enviar_retorno_followup(ctx)
        self.assertEqual(envio["id_etapa_resultante"], 18)
        self.assertNotIn("turno", envio)
        self.assertNotIn("evento_transicao", envio)
        self.assertIn("Bom te ver novamente", envio["mensagem_bot"])

    def test_midia19_repete_contato_sem_entrar_na_pesquisa(self):
        ctx = contexto(19, "", dependente=True)
        ctx["tipo_mensagem_atual"] = "audio"
        envio = resolver_etapa19.resolve_etapa19(ctx)
        self.assertEqual(envio["id_etapa_resultante"], 19)
        self.assertNotIn("evento_transicao", envio)
        self.assertIn("apenas texto", envio["mensagem_bot"])
        botao = self.http.send_message.call_args.kwargs["buttons"]
        mensagem = parse_qs(urlparse(botao.url).query)["text"][0]
        self.assertIn("João, que tem 12 anos", mensagem)
        self.assertIn("turno da manhã", mensagem)

    def test_pesquisa_compartilhada_ate_final24_com_e_sem_comentario(self):
        for etapa, resposta, destino, evento in (
            (20, "Já reservei", 21, "agendamento_confirmado"),
            (21, "5", 22, "satisfacao_avaliada"),
            (22, "Sim", 23, "comentario_satisfacao_aceito"),
            (22, "Não", 24, "comentario_satisfacao_recusado"),
            (23, "Gostei muito do atendimento", 24, "comentario_satisfacao_recebido"),
        ):
            with self.subTest(etapa=etapa, resposta=resposta):
                envio = flow_sender(
                    contexto(etapa, resposta, link="https://example.com")
                )
                self.assertEqual(envio["id_etapa_resultante"], destino)
                self.assertEqual(envio["evento_transicao"], evento)

    def test_catalogo_e_transicoes_finais(self):
        self.assertEqual([e[0] for e in ETAPAS], list(range(1, 25)))
        self.assertEqual([(e[0], e[3]) for e in ETAPAS if e[2]], [(24, 30)])
        self.assertFalse(next(e for e in ETAPAS if e[0] == 18)[4])
        self.assertIn((17, "triagem_concluida_sem_link", 18), TRANSICOES)
        self.assertIn((17, "triagem_pergunta_6_respondida", 20), TRANSICOES)
        self.assertIn((18, "turno_escolhido", 19), TRANSICOES)
        self.assertIn((19, "avaliacao_solicitada", 21), TRANSICOES)
        self.assertEqual(len({(a, b) for a, b, c in TRANSICOES}), len(TRANSICOES))
        self.assertEqual(len({(a, c) for a, b, c in TRANSICOES}), len(TRANSICOES))


class ContatoComercialTests(unittest.TestCase):
    def test_texto_e_url_preservam_nome_idade_e_turno_unico(self):
        for genero, artigo in (("feminino", "a"), ("masculino", "o")):
            texto = montar_mensagem_contato_comercial(
                nome_agente="Bot",
                genero_agente=genero,
                nome_cliente="Ana & João",
                idade_aluno=40,
                turno="manha",
            )
            self.assertIn(f"com {artigo} Bot", texto)
            url = montar_link_numero_comercial_whatsapp("(71) 99999-9999", texto)
            self.assertEqual(parse_qs(urlparse(url).query)["text"], [texto])
            self.assertTrue(url.startswith("https://wa.me/5571999999999?text="))

    def test_encaminhamento_por_idade_nao_inventa_turno(self):
        texto = montar_mensagem_contato_comercial(
            nome_agente="Suh",
            genero_agente="feminino",
            nome_cliente="Ana",
            idade_aluno=100,
            nome_dependente="Maria",
        )
        self.assertIn("Maria, que tem 100 anos", texto)
        self.assertNotIn("turno", texto)

    def test_funil_orienta_conforme_configuracao_vigente(self):
        for link in (None, "https://example.com"):
            lead = dados_lead(resposta_email="sem email")
            lead.update(link_agendamento=link, turno="tarde")
            texto = montar_observacoes_lead(lead)
            self.assertIn("painel de monitoramento", texto)
            self.assertIn("Turno de preferência: tarde", texto)
            if link:
                self.assertIn("Calendly", texto)
            else:
                self.assertIn("número comercial", texto)
                self.assertNotIn("Calendly", texto)
