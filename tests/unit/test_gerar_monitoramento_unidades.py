from __future__ import annotations

import re
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

from utilitarios.reports_functions import total
from utilitarios.reports_functions import weekly as monitoramento


class GerarMonitoramentoUnidadesTests(unittest.TestCase):
    FIM = datetime(2026, 8, 27, 15, 0, tzinfo=timezone.utc)
    INICIO = FIM - timedelta(days=7)

    @staticmethod
    def _mensagem(
        *,
        id_unidade: int,
        id_cliente: int,
        id_conversa: int,
        id_mensagem: int,
        quando: datetime,
        profissao_cliente: str | None = None,
        profissao_conversa: str | None = None,
        nome: str = "Maria",
        texto: str = "Olá",
        quem_enviou: str = "cliente",
    ) -> dict[str, object]:
        return {
            "id_unidade": id_unidade,
            "id_cliente": id_cliente,
            "nome_cliente": nome,
            "waid_telefone": f"55{id_cliente}",
            "email": f"cliente{id_cliente}@example.test",
            "profissao_cliente": profissao_cliente,
            "profissao_conversa_recente": profissao_conversa,
            "id_conversa": id_conversa,
            "status_ativa": id_conversa == 122,
            "id_etapa_atual": 5,
            "id_mensagem": id_mensagem,
            "id_etapa": 4,
            "received_data_hora": quando,
            "quem_enviou": quem_enviou,
            "tipo_mensagem": "text",
            "conteudo_texto": texto,
        }

    def _snapshot(self) -> dict[str, object]:
        unidades = [
            {"id_unidade": 1, "nome_unidade": "Supera SAJ", "nome_agente": "Suh"},
            {
                "id_unidade": 2,
                "nome_unidade": "Supera Rio Vermelho",
                "nome_agente": "Lia",
            },
        ]
        mensagens = [
            self._mensagem(
                id_unidade=1,
                id_cliente=10,
                id_conversa=121,
                id_mensagem=1,
                quando=self.INICIO + timedelta(hours=1),
                profissao_cliente="Professora",
                profissao_conversa="Autônoma",
            ),
            self._mensagem(
                id_unidade=1,
                id_cliente=10,
                id_conversa=122,
                id_mensagem=2,
                quando=self.INICIO + timedelta(days=1),
                profissao_cliente="Professora",
                profissao_conversa="Autônoma",
                texto="Continuação",
            ),
            self._mensagem(
                id_unidade=1,
                id_cliente=20,
                id_conversa=123,
                id_mensagem=3,
                quando=self.INICIO + timedelta(days=2),
                profissao_cliente="  ",
                profissao_conversa="Pedreira",
                nome="Joana",
            ),
            self._mensagem(
                id_unidade=2,
                id_cliente=10,
                id_conversa=130,
                id_mensagem=4,
                quando=self.INICIO + timedelta(days=3),
                profissao_cliente="Professora",
                nome="Maria",
            ),
        ]
        funil = [
            {"id_unidade": 1, "id_cliente": 10},
            {"id_unidade": 1, "id_cliente": 999},  # não contatou na janela
            {"id_unidade": 2, "id_cliente": 10},
        ]
        return monitoramento.montar_snapshot(
            unidades, mensagens, funil, [], self.INICIO, self.FIM
        )

    def test_resolver_janela_de_sete_dias(self) -> None:
        inicio, fim = monitoramento.resolver_janela(dias=7, ate=self.FIM)

        self.assertEqual(fim, self.FIM)
        self.assertEqual(inicio, self.INICIO)
        self.assertEqual(fim - inicio, timedelta(days=7))

    def test_saida_padrao_continua_na_raiz_do_projeto_apos_mover_modulo(self) -> None:
        esperado = Path(monitoramento.__file__).resolve().parents[2] / "monitoramento"

        self.assertEqual(monitoramento.SAIDA_PADRAO, esperado)
        self.assertEqual(total.SAIDA_PADRAO, esperado)

    def test_nome_de_unidade_e_seguro_inclusive_para_reservados_windows(self) -> None:
        self.assertEqual(
            monitoramento.sanear_nome_unidade(" Supera Rio: Vermelho/ ", 2),
            "Rio Vermelho",
        )
        self.assertEqual(
            monitoramento.sanear_nome_unidade("Supera Santo Antônio de Jesus", 1),
            "SAJ",
        )
        self.assertEqual(monitoramento.sanear_nome_unidade("CON", 7), "CON 7")
        self.assertNotIn(
            monitoramento.sanear_nome_unidade("Supera <SAJ>|*?", 1).upper(),
            {"CON", "PRN", "AUX", "NUL"},
        )

    def test_resolver_pastas_revalida_tambem_o_nome_alternativo(self) -> None:
        unidades = [
            {"id_unidade": 1, "nome_unidade": "Supera Centro"},
            {"id_unidade": 2, "nome_unidade": "Supera Centro"},
            {"id_unidade": 3, "nome_unidade": "Supera Centro (2)"},
        ]

        pastas = monitoramento.resolver_pastas_unidades(unidades)

        self.assertEqual(len({nome.casefold() for nome in pastas.values()}), 3)

    def test_conversas_do_mesmo_cliente_e_unidade_sao_unificadas(self) -> None:
        snapshot = self._snapshot()
        unidades = {item["id_unidade"]: item for item in snapshot["unidades"]}

        conversas_saj = {
            item["id_cliente"]: item for item in unidades[1]["conversas"]
        }
        self.assertEqual(conversas_saj[10]["ids_conversa"], [121, 122])
        self.assertEqual(len(conversas_saj[10]["mensagens"]), 2)
        self.assertEqual(unidades[2]["conversas"][0]["ids_conversa"], [130])

    def test_funil_e_limitado_a_coorte_que_contatou_na_janela(self) -> None:
        snapshot = self._snapshot()
        unidades = {item["id_unidade"]: item for item in snapshot["unidades"]}

        self.assertEqual(unidades[1]["metricas"]["leads_contato"], 2)
        self.assertEqual(unidades[1]["metricas"]["leads_funil"], 1)
        self.assertEqual(unidades[1]["metricas"]["taxa_funil"], 50.0)
        self.assertEqual(unidades[2]["metricas"]["leads_funil"], 1)

    def test_profissao_prioriza_cliente_e_faz_fallback_para_conversa(self) -> None:
        snapshot = self._snapshot()
        saj = next(item for item in snapshot["unidades"] if item["id_unidade"] == 1)
        conversas = {item["id_cliente"]: item for item in saj["conversas"]}

        self.assertEqual(conversas[10]["profissao"], "Professora")
        self.assertEqual(conversas[20]["profissao"], "Pedreira")

    def test_html_nao_permite_encerrar_script_pelo_conteudo(self) -> None:
        snapshot = self._snapshot()
        unidade = snapshot["unidades"][0]
        ataque = "</script><script>alert('x')</script>"
        unidade["conversas"][0]["nome"] = ataque
        unidade["conversas"][0]["mensagens"][0]["texto"] = ataque

        html = monitoramento.renderizar_html(unidade, snapshot["periodo"])

        self.assertNotIn(ataque, html)
        self.assertIn(r"\u003c/script\u003e", html)

    def test_html_preserva_rolagem_independente_de_conversas_e_mensagens(
        self,
    ) -> None:
        snapshot = self._snapshot()

        html = monitoramento.renderizar_html(
            snapshot["unidades"][0], snapshot["periodo"]
        )

        def declaracoes(selector: str) -> str:
            blocos = re.findall(rf"{re.escape(selector)}\{{([^}}]*)\}}", html)
            self.assertTrue(blocos, f"Regra CSS ausente: {selector}")
            return ";".join(blocos).replace(" ", "").replace("\n", "")

        self.assertIn("grid-template-rows:minmax(0,1fr)", declaracoes(".app"))
        for selector in (".sidebar", ".main"):
            regra = declaracoes(selector)
            self.assertIn("min-height:0", regra)
            self.assertIn("overflow:hidden", regra)
        for selector in (".list", ".messages"):
            regra = declaracoes(selector)
            self.assertIn("min-height:0", regra)
            self.assertIn("overflow-y:auto", regra)
            self.assertIn("overscroll-behavior:contain", regra)

        self.assertIn('<div id="chatList" class="list"></div>', html)
        self.assertIn('<div id="messages" class="messages">', html)

    def test_gera_estrutura_por_unidade_sem_expor_arquivos_temporarios(self) -> None:
        snapshot = self._snapshot()

        def pdf_falso(unidade, periodo, destino: Path) -> None:
            del unidade, periodo
            destino.write_bytes(b"%PDF-1.4\nmock")

        with tempfile.TemporaryDirectory() as temporario:
            raiz = Path(temporario) / "monitoramento"
            with mock.patch.object(
                monitoramento, "renderizar_pdf", side_effect=pdf_falso
            ) as renderizar:
                gerados = monitoramento.gerar_artefatos(snapshot, raiz)

            self.assertEqual(renderizar.call_count, 2)
            self.assertEqual(len(gerados), 2)
            self.assertEqual(
                {item["html"].parent.name for item in gerados}, {"dashbord"}
            )
            self.assertEqual(
                {item["html"].parent.parent.name for item in gerados}, {"semanal"}
            )
            self.assertEqual(
                {item["pdf"].parent.name for item in gerados}, {"relatorios"}
            )
            self.assertEqual(
                {item["pdf"].parent.parent.name for item in gerados}, {"semanal"}
            )
            for item in gerados:
                self.assertTrue(item["html"].is_file())
                self.assertTrue(item["pdf"].is_file())
                self.assertEqual(item["pdf"].read_bytes(), b"%PDF-1.4\nmock")
            self.assertEqual(list(raiz.rglob(".gerando-*")), [])

    def test_falha_do_pdf_nao_publica_metade_do_par(self) -> None:
        snapshot = self._snapshot()
        snapshot["unidades"] = snapshot["unidades"][:1]

        with tempfile.TemporaryDirectory() as temporario:
            raiz = Path(temporario) / "monitoramento"
            with mock.patch.object(
                monitoramento,
                "renderizar_pdf",
                side_effect=RuntimeError("falha simulada"),
            ):
                with self.assertRaisesRegex(RuntimeError, "falha simulada"):
                    monitoramento.gerar_artefatos(snapshot, raiz)

            self.assertEqual(list(raiz.rglob("*.html")), [])
            self.assertEqual(list(raiz.rglob("*.pdf")), [])
            self.assertEqual(list(raiz.rglob(".gerando-*")), [])

    def test_falha_na_segunda_unidade_preserva_todo_o_lote_anterior(self) -> None:
        snapshot = self._snapshot()

        def pdf_antigo(unidade, periodo, destino: Path) -> None:
            del periodo
            destino.write_bytes(f"PDF-antigo-{unidade['id_unidade']}".encode())

        with tempfile.TemporaryDirectory() as temporario:
            raiz = Path(temporario) / "monitoramento"
            with mock.patch.object(
                monitoramento, "renderizar_pdf", side_effect=pdf_antigo
            ):
                anteriores = monitoramento.gerar_artefatos(snapshot, raiz)

            conteudos_anteriores = {
                caminho: caminho.read_bytes()
                for item in anteriores
                for caminho in (item["html"], item["pdf"])
            }
            chamadas = 0

            def pdf_novo_com_falha(unidade, periodo, destino: Path) -> None:
                nonlocal chamadas
                del unidade, periodo
                chamadas += 1
                if chamadas == 2:
                    raise RuntimeError("falha na segunda unidade")
                destino.write_bytes(b"PDF-novo")

            with mock.patch.object(
                monitoramento,
                "renderizar_pdf",
                side_effect=pdf_novo_com_falha,
            ):
                with self.assertRaisesRegex(
                    RuntimeError, "falha na segunda unidade"
                ):
                    monitoramento.gerar_artefatos(snapshot, raiz)

            for caminho, conteudo in conteudos_anteriores.items():
                self.assertEqual(caminho.read_bytes(), conteudo)
            self.assertEqual(list(raiz.rglob(".gerando-*")), [])

    def test_periodo_total_publica_na_arvore_total_com_o_mesmo_renderizador(self) -> None:
        snapshot = self._snapshot()
        snapshot["periodo"]["tipo"] = "total"
        snapshot["unidades"] = snapshot["unidades"][:1]

        def pdf_falso(unidade, periodo, destino: Path) -> None:
            del unidade
            self.assertEqual(periodo["tipo"], "total")
            destino.write_bytes(b"%PDF-1.4\nmock-total")

        with tempfile.TemporaryDirectory() as temporario:
            raiz = Path(temporario) / "monitoramento"
            with mock.patch.object(
                monitoramento, "renderizar_pdf", side_effect=pdf_falso
            ):
                gerados = monitoramento.gerar_artefatos(snapshot, raiz)

            self.assertEqual(len(gerados), 1)
            self.assertEqual(gerados[0]["html"].parent.parent.name, "total")
            self.assertEqual(gerados[0]["pdf"].parent.parent.name, "total")
            self.assertTrue(gerados[0]["html"].is_file())
            self.assertEqual(
                gerados[0]["pdf"].read_bytes(), b"%PDF-1.4\nmock-total"
            )

    def test_semanal_e_total_coexistem_sem_sobrescrever_um_ao_outro(self) -> None:
        semanal = self._snapshot()
        total_snapshot = self._snapshot()
        total_snapshot["periodo"]["tipo"] = "total"
        semanal["unidades"] = semanal["unidades"][:1]
        total_snapshot["unidades"] = total_snapshot["unidades"][:1]

        def pdf_falso(unidade, periodo, destino: Path) -> None:
            del unidade
            destino.write_bytes(f"PDF-{periodo['tipo']}".encode())

        with tempfile.TemporaryDirectory() as temporario:
            raiz = Path(temporario) / "monitoramento"
            with mock.patch.object(
                monitoramento, "renderizar_pdf", side_effect=pdf_falso
            ):
                gerado_semanal = monitoramento.gerar_artefatos(semanal, raiz)[0]
                gerado_total = monitoramento.gerar_artefatos(total_snapshot, raiz)[0]

            self.assertNotEqual(gerado_semanal["html"], gerado_total["html"])
            self.assertNotEqual(gerado_semanal["pdf"], gerado_total["pdf"])
            self.assertTrue(gerado_semanal["html"].is_file())
            self.assertTrue(gerado_semanal["pdf"].is_file())
            self.assertTrue(gerado_total["html"].is_file())
            self.assertTrue(gerado_total["pdf"].is_file())

    def test_total_usa_inicio_independente_por_unidade_e_fim_congelado(self) -> None:
        primeiro_saj = self.FIM - timedelta(days=90)
        primeiro_rio = self.FIM - timedelta(days=30)
        unidades = [
            {
                "id_unidade": 1,
                "nome_unidade": "Supera SAJ",
                "primeiro_registro": primeiro_saj,
            },
            {
                "id_unidade": 2,
                "nome_unidade": "Supera Rio Vermelho",
                "primeiro_registro": primeiro_rio,
            },
        ]
        coletas: list[dict[str, object]] = []
        publicacoes: list[dict[str, object]] = []

        def coletar_falso(**kwargs):
            coletas.append(kwargs)
            id_unidade = kwargs["ids_unidade"][0]
            unidade = next(
                item for item in unidades if item["id_unidade"] == id_unidade
            )
            return {
                "periodo": {
                    "tipo": "semanal",
                    "inicio": kwargs["inicio"].isoformat(),
                    "fim": kwargs["fim"].isoformat(),
                    "dias": (
                        kwargs["fim"] - kwargs["inicio"]
                    ).total_seconds()
                    / 86_400,
                    "rotulo": "intervalo de teste",
                },
                "unidades": [
                    {
                        "id_unidade": id_unidade,
                        "nome_unidade": unidade["nome_unidade"],
                    }
                ],
            }

        def gerar_falso(snapshot, raiz_saida, nomes_pasta=None):
            publicacoes.append(
                {
                    "snapshot": snapshot,
                    "raiz_saida": raiz_saida,
                    "nomes_pasta": nomes_pasta,
                }
            )
            return [
                {
                    "html": raiz_saida / "mock.html",
                    "pdf": raiz_saida / "mock.pdf",
                }
            ]

        with mock.patch.object(
            monitoramento, "coletar_snapshot", side_effect=coletar_falso
        ), mock.patch.object(
            monitoramento, "gerar_artefatos", side_effect=gerar_falso
        ):
            gerados = total.gerar_totais(
                conn=object(),
                unidades=unidades,
                fim=self.FIM,
                raiz_saida=Path("monitoramento"),
            )

        self.assertEqual(len(gerados), 2)
        self.assertEqual([item["inicio"] for item in coletas], [primeiro_saj, primeiro_rio])
        self.assertEqual([item["fim"] for item in coletas], [self.FIM, self.FIM])
        self.assertEqual(
            [item["snapshot"]["periodo"]["tipo"] for item in publicacoes],
            ["total", "total"],
        )

    def test_total_sem_primeiro_registro_ainda_gera_snapshot_vazio(self) -> None:
        unidades = [
            {
                "id_unidade": 9,
                "nome_unidade": "Supera Unidade Nova",
                "primeiro_registro": None,
            }
        ]
        publicacoes: list[dict[str, object]] = []

        def coletar_falso(**kwargs):
            self.assertEqual(kwargs["inicio"], self.FIM)
            self.assertEqual(kwargs["fim"], self.FIM)
            return {
                "periodo": {
                    "tipo": "semanal",
                    "inicio": self.FIM.isoformat(),
                    "fim": self.FIM.isoformat(),
                    "dias": 0,
                    "rotulo": "sem registros",
                },
                "unidades": [
                    {"id_unidade": 9, "nome_unidade": "Supera Unidade Nova"}
                ],
            }

        def gerar_falso(snapshot, raiz_saida, nomes_pasta=None):
            del raiz_saida, nomes_pasta
            publicacoes.append(snapshot)
            return [{"html": Path("mock.html"), "pdf": Path("mock.pdf")}]

        with mock.patch.object(
            monitoramento, "coletar_snapshot", side_effect=coletar_falso
        ), mock.patch.object(
            monitoramento, "gerar_artefatos", side_effect=gerar_falso
        ):
            total.gerar_totais(
                conn=object(),
                unidades=unidades,
                fim=self.FIM,
                raiz_saida=Path("monitoramento"),
            )

        self.assertEqual(len(publicacoes), 1)
        self.assertTrue(publicacoes[0]["periodo"]["sem_registros"])
        self.assertEqual(publicacoes[0]["periodo"]["tipo"], "total")


if __name__ == "__main__":
    unittest.main()
