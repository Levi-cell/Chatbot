"""Contratos de importação/entrega: HTTP e Meta sempre simulados."""

from copy import deepcopy
import unittest
from unittest.mock import Mock, patch
from core.integrations.fireads.cliente import ClienteFireAds, validar_url
from core.integrations.fireads.contrato import (
    destino,
    selecionar,
    ErroFireAds,
    bloco_observacoes,
    acrescentar_observacoes,
)
from workers.worker_flow.fireads import interpretar, email_importado, preparar_abertura
from workers.worker_funil.fireads import preparar_escrita
from workers.worker_flow.response_flow.etapas import resolver_etapa7, resolver_etapa9
from workers.worker_flow.transacoes.movimento_conversa import (
    resolver_movimento_conversa,
)
from core.integrations.funil.oportunidades import montar_payload_oportunidade
from tests.helpers import FakeConn, FakeCursor

NUMERO = "5511999990002"
GOOGLE = {
    "Nome": "Ana Paula Silva",
    "Email": "ana@example.com",
    "WhatsApp": NUMERO,
    "Perfil/Faixa": "Para mim",
    "Data/Hora": "01/10/2026 12:00",
}
META = {
    "full_name": "Carlos Silva",
    "email": "carlos@example.com",
    "phone_number": NUMERO,
    "para_quem": "mim_e_outra",
    "created_time": "2026-10-01T12:00:00-05:00",
}


def estado():
    return dict(
        interpretar([GOOGLE], [], NUMERO, None),
        concluida=True,
        id_conversa=2,
        id_integracao=1,
    )


class FireAdsTests(unittest.TestCase):
    def test_admin_nao_chama_meta_com_personalizacao_invalida(self):
        from django.contrib.admin import AdminSite
        from django.test import RequestFactory
        from types import SimpleNamespace
        from webhook.admin import UnidadeAdmin
        from webhook.models import Unidade

        admin = UnidadeAdmin(Unidade, AdminSite())
        request = RequestFactory().post("/admin/")
        request.user = SimpleNamespace(has_perm=lambda *_: True)
        request._unidade_formsets = [Mock(is_valid=Mock(return_value=False))]
        form_class = admin.get_form(request, fields=["waba_id", "phone_number_id"])
        with patch.object(Unidade, "validate_unique"), patch.object(
            Unidade, "validate_constraints"
        ), patch.object(admin, "_preparar_meta_antes_de_salvar") as meta:
            form = form_class(data={"waba_id": "123", "phone_number_id": "456"})
            self.assertFalse(form.is_valid())
            self.assertIn("atendimento customizado", str(form.non_field_errors()))
            meta.assert_not_called()

    def test_abertura_personalizada_preserva_tratamentos_sem_recoletar_nome(self):
        from workers.worker_flow.fireads import classificar_tratamento_abertura
        from core.integrations.whatsapp.messages.etapa4_messages import (
            montar_abertura_fireads,
        )

        contexto = {
            "contexto_fireads": estado(),
            "nome_agente": "Dora",
            "nome_unidade": "Supera Teste",
            "genero": "feminino",
        }
        for tipo, texto, esperado in [
            ("image", "", "tipo_mensagem_nao_suportado"),
            ("text", "quanto custa?", "pergunta_financeira"),
            ("text", "Oi", None),
        ]:
            with self.subTest(tipo=tipo, texto=texto):
                contexto.update(tipo_mensagem_atual=tipo, texto_cliente_atual=texto)
                tratamento = classificar_tratamento_abertura(contexto)
                self.assertEqual(tratamento, esperado)
                mensagem = montar_abertura_fireads(
                    contexto,
                    saudacao="Boa tarde",
                    tratamento=tratamento,
                )
                self.assertIn("Ana Paula", mensagem)
                self.assertIn("profiss", mensagem.lower())
                self.assertNotIn("Como você se chama", mensagem)

    def test_abertura_importada_registra_etapa4_e_replay_nao_reenvia(self):
        from datetime import datetime, timezone
        from workers.worker_flow import valida_historico as historico
        from workers.worker_flow.response_flow import flow_sender as sender
        from contextlib import ExitStack

        agora = datetime.now(timezone.utc)
        mensagem = {
            "id_mensagem": 10,
            "id_hash": "wamid.teste",
            "conteudo_texto": "Olá",
            "tipo_mensagem": "text",
            "cliente_telefone": NUMERO,
            "id_phone_unidade": "teste",
            "unidade_telefone": "5511999990000",
            "retry_count": 1,
        }
        banco = {
            "id_cliente": 1,
            "id_unidade": 1,
            "contexto_fireads": estado(),
            "conversa": {
                "id_conversa": 2,
                "id_etapa_atual": None,
                "last_message_from": "cliente",
                "status_dependente": False,
            },
        }
        with ExitStack() as stack:
            inserir = stack.enter_context(
                patch.object(
                    historico,
                    "inserir_historico_mensagem_cliente",
                    side_effect=lambda **k: (1, agora, k["id_etapa"], True),
                )
            )
            stack.enter_context(
                patch.object(
                    historico,
                    "buscar_resposta_bot_por_mensagem_cliente",
                    return_value=None,
                )
            )
            stack.enter_context(
                patch.object(
                    historico,
                    "listar_transicoes_permitidas",
                    return_value={
                        "profissao_titular_valida": 6,
                        "profissao_dependente_valida": 5,
                    },
                )
            )
            stack.enter_context(
                patch.object(
                    historico,
                    "buscar_contexto_etapa1",
                    return_value={
                        "nome_unidade": "Teste",
                        "nome_agente": "Dora",
                        "genero": "feminino",
                    },
                )
            )
            stack.enter_context(
                patch.object(historico, "atualizar_conversa_mensagem_cliente")
            )
            cx = historico.valida_historico(mensagem, banco, FakeCursor())
        self.assertEqual(inserir.call_args.kwargs["id_etapa"], 4)
        self.assertEqual(cx["id_etapa_origem_transicao"], 4)
        with patch.object(
            sender, "enviar_abertura_fireads", return_value={"id_etapa_resultante": 4}
        ) as envio:
            self.assertEqual(sender.flow_sender(cx)["id_etapa_resultante"], 4)
            envio.assert_called_once()
        # Banco confirmou resposta + movimento; só a fila precisou de retry.
        cx.update(
            id_etapa_atual=4,
            resposta_bot_para_mensagem_atual={
                "id_mensagem": 2,
                "id_etapa": 4,
                "id_hash_msg": "wamid.bot",
            },
        )
        with patch.object(sender, "enviar_abertura_fireads") as envio:
            resposta = sender.flow_sender(cx)
            self.assertTrue(resposta["resposta_ja_existia"])
            self.assertEqual(resolver_movimento_conversa(cx, resposta), "sem_avanco")
            envio.assert_not_called()

    def test_mapeamento_sem_inferir_por_faixa_etaria(self):
        for valor in ("Para mim", "para_mim"):
            self.assertIs(destino(valor), False)
        for valor in (
            "Para meu pai/mãe",
            "Para meu avô/avó",
            "Para outra pessoa",
            "Para meu pai ou minha mãe",
            "Para meu filho ou filha",
            "Para mim e outra pessoa",
            "mim_e_outra",
            "pai_ou_mae",
            "filho_ou_filha",
        ):
            self.assertIs(destino(valor), True, valor)
        for valor in (
            "Adulto",
            "Criança",
            "Adolescente",
            "Pessoa com 60 anos ou mais",
            "",
            None,
            "teste",
        ):
            self.assertIsNone(destino(valor), valor)

    def test_importa_nome_composto_e_nao_faixa_ou_objetivo(self):
        valor = interpretar([dict(GOOGLE, Objetivo="Memória")], [], NUMERO, None)
        self.assertEqual(valor["resultado"], "importado")
        self.assertEqual(valor["dados_titular"]["nome"], "Ana Paula")
        self.assertNotIn("idade", valor["dados_titular"])
        self.assertNotIn("Objetivo", valor)

    def test_registro_antigo_unico_nao_expira(self):
        self.assertEqual(
            interpretar(
                [dict(GOOGLE, **{"Data/Hora": "01/01/2020 12:00"})], [], NUMERO, None
            )["origem"],
            "google",
        )

    def test_datas_sao_comparadas_com_offset_da_fonte(self):
        self.assertEqual(
            selecionar([GOOGLE], [META], NUMERO, "America/Sao_Paulo")[0], "meta"
        )
        self.assertEqual(selecionar([GOOGLE], [META], NUMERO, None)[0], "meta")

    def test_mais_recente_invalido_nao_resgata_antigo(self):
        decisao = interpretar(
            [GOOGLE], [dict(META, email="inválido")], NUMERO, "America/Sao_Paulo"
        )
        self.assertEqual(decisao["origem"], "organico")
        self.assertEqual(decisao["dados_titular"], {})

    def test_empate_entre_abas_usa_maior_linha_e_telefone_diferente_ausente(self):
        self.assertEqual(
            interpretar(
                [dict(GOOGLE, _row=44)],
                [dict(META, _row=46, created_time="2026-10-01T15:00:00Z")],
                NUMERO,
                "America/Sao_Paulo",
            )["origem"],
            "meta",
        )
        self.assertEqual(
            interpretar([GOOGLE], [], "5511999990003", None)["resultado"], "ausente"
        )

    def test_email_do_cadastro_geral_nao_autoriza_salto(self):
        self.assertFalse(
            email_importado({"id_conversa": 2, "email_cliente": "ana@example.com"})
        )
        self.assertFalse(
            email_importado({"id_conversa": 3, "contexto_fireads": estado()})
        )
        self.assertTrue(
            email_importado({"id_conversa": 2, "contexto_fireads": estado()})
        )

    def test_inicializacao_4_exige_importacao_completa(self):
        cx = {"id_conversa": 2, "id_etapa_atual": None, "contexto_fireads": estado()}
        self.assertEqual(
            resolver_movimento_conversa(cx, {"id_etapa_resultante": 4}), "inicializacao"
        )
        with self.assertRaises(ValueError):
            resolver_movimento_conversa(
                dict(cx, contexto_fireads=None), {"id_etapa_resultante": 4}
            )

    def test_aceite_da_oferta_e_retorno_pulam_email_somente_quando_importado(self):
        for etapa, mod, evento in [
            (7, resolver_etapa7, "oferta_aceita"),
            (9, resolver_etapa9, "retorno_confirmado"),
        ]:
            cx = {
                "id_conversa": 2,
                "id_etapa_atual": etapa,
                "id_etapa_origem_transicao": etapa,
                "id_etapa_cliente": etapa,
                "contexto_fireads": estado(),
                "tipo_mensagem_atual": "text",
                "texto_cliente_atual": "sim",
                "transicoes_permitidas": {evento: 10, evento + "_email_fireads": 11},
                "mensagem_cliente_atual": {
                    "cliente_telefone": NUMERO,
                    "id_phone_unidade": "teste",
                    "id_mensagem_fila": 1,
                },
            }
            with patch.object(
                mod, "enviar_etapa11", return_value={"id_etapa_resultante": 11}
            ) as triagem, patch.object(
                mod, "enviar_etapa10", return_value={"id_etapa_resultante": 10}
            ) as email:
                resultado = getattr(mod, f"resolve_etapa{etapa}")(cx)
                self.assertEqual(
                    resultado["evento_transicao"], evento + "_email_fireads"
                )
                triagem.assert_called_once()
                email.assert_not_called()
                resultado = getattr(mod, f"resolve_etapa{etapa}")(
                    dict(cx, contexto_fireads=None)
                )
                self.assertEqual(resultado["id_etapa_resultante"], 10)

    def test_preserva_observacoes_inclusive_zero_e_retry(self):
        bloco = bloco_observacoes(1, 2, "Texto do Funil")
        for anterior in ("FR002", "  notas comerciais\n", 0, "0", "", None):
            novo, mudou = acrescentar_observacoes(anterior, bloco)
            self.assertTrue(mudou)
            if anterior is not None:
                self.assertTrue(novo.startswith(str(anterior)))
            self.assertEqual(acrescentar_observacoes(novo, bloco), (novo, False))
        with self.assertRaises(ErroFireAds):
            acrescentar_observacoes(bloco.replace("Texto do Funil", "Editado"), bloco)
        with self.assertRaises(ErroFireAds):
            acrescentar_observacoes("x" * 45000, bloco)

    def test_organico_existente_atualiza_so_observacao(self):
        snap = {
            "telefone": NUMERO,
            "nome": "Ana",
            "email": "ana@example.com",
            "perfil": "Titular",
            "origem": "organico",
        }
        linha = {
            "_row": 2,
            "WhatsApp": NUMERO,
            "Email": "ana@example.com",
            "Observação": "FR002",
        }
        bloco = bloco_observacoes(1, 2, "novo")
        op = preparar_escrita([linha], snap, bloco)
        self.assertEqual(set(op), {"row", "observacoes"})
        self.assertEqual(op["observacoes"], "FR002\n\n" + bloco)
        self.assertIsNone(
            preparar_escrita(
                [dict(linha, **{"Observação": op["observacoes"]})], snap, bloco
            )
        )

    def test_organico_novo_nao_envia_data_e_identidade_ambigua_nao_escreve(self):
        snap = {
            "telefone": NUMERO,
            "nome": "Ana",
            "email": "ana@example.com",
            "perfil": "Titular",
            "origem": "organico",
        }
        bloco = bloco_observacoes(1, 2, "novo")
        self.assertNotIn("Data/Hora", preparar_escrita([], snap, bloco)["dados"])
        for linhas in (
            [{"_row": 2, "WhatsApp": NUMERO, "Email": "outra@example.com"}],
            [{"_row": 2, "WhatsApp": NUMERO}, {"_row": 3, "WhatsApp": NUMERO}],
            [{"_row": 2, "WhatsApp": "5511999990003", "Email": snap["email"]}],
        ):
            with self.assertRaises(ErroFireAds):
                preparar_escrita(linhas, snap, bloco)

    def test_exec_e_redirect_sem_repetir_post(self):
        session = Mock()
        redirect = Mock(
            status_code=302,
            headers={
                "Location": "https://script.googleusercontent.com/macros/echo?x=1"
            },
        )
        resposta = Mock(status_code=200)
        resposta.json.return_value = {"success": True, "aba": "geral", "inserted": 1}
        session.request.side_effect = [redirect, resposta]
        cli = ClienteFireAds(
            "https://script.google.com/macros/s/teste/exec", session=session
        )
        cli.enviar("geral", dados={"Nome": "Teste"})
        self.assertEqual(
            [c.args[0] for c in session.request.call_args_list], ["POST", "GET"]
        )
        with self.assertRaises(ErroFireAds):
            validar_url("https://script.google.com/u/0/home/projects/teste/edit")
        session.request.side_effect = None
        resposta.json.return_value = {"success": False, "error": "recusado"}
        session.request.return_value = resposta
        with self.assertRaises(ErroFireAds):
            cli.enviar("geral", dados={"Nome": "Teste"})

    def test_retry_recupera_decisao_sem_consultar_api(self):
        cx = {"conversa": {"id_conversa": 2, "id_etapa_atual": None}}
        with patch(
            "workers.worker_flow.fireads.buscar_abertura",
            return_value={"contexto": estado()},
        ), patch("workers.worker_consulta_dash.consulta.ClienteFireAds") as api:
            retomado = preparar_abertura(cx, {}, 1, FakeCursor())
            self.assertEqual(retomado["contexto_fireads"]["origem"], "google")
            api.assert_not_called()

    def test_segunda_fonte_falha_importa_nada(self):
        from workers.worker_consulta_dash.consulta import consultar

        api = Mock()
        api.consultar.side_effect = [
            {"headers": list(GOOGLE), "rows": [GOOGLE]},
            RuntimeError("falha"),
        ]
        with patch(
            "workers.worker_consulta_dash.consulta.ClienteFireAds", return_value=api
        ):
            resultado = consultar(
                {
                    "id_consulta": 1,
                    "restante": 300,
                    "entrada": {
                        "url": "https://script.google.com/macros/s/teste/exec",
                        "aba_google": "google",
                        "aba_meta": "meta",
                        "numero": NUMERO,
                        "fuso": None,
                    },
                }
            )
        self.assertEqual(resultado["decisao"]["origem"], "organico")
        self.assertEqual(resultado["fontes"], {})
