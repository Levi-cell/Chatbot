from __future__ import annotations

import sys
import types
import unittest
from datetime import datetime, timedelta, timezone
from unittest import mock

from utilitarios.reports_functions import weekly


class MetricasPerfisRelatoriosTests(unittest.TestCase):
    FIM = datetime(2026, 8, 30, 15, tzinfo=timezone.utc)
    INICIO = FIM - timedelta(days=7)

    @staticmethod
    def _perfil(
        id_cliente: int,
        id_conversa: int,
        *,
        id_unidade: int = 1,
        status_dependente: object = False,
        idade_titular: object = 35,
        idade_dependente: object = None,
    ) -> dict[str, object]:
        return {
            "id_unidade": id_unidade,
            "id_cliente": id_cliente,
            "id_conversa": id_conversa,
            "status_dependente": status_dependente,
            "idade_titular": idade_titular,
            "idade_dependente": idade_dependente,
        }

    def _mensagem(self, perfil: dict[str, object], id_mensagem: int) -> dict[str, object]:
        return {
            **perfil,
            "id_mensagem": id_mensagem,
            "received_data_hora": self.INICIO + timedelta(minutes=id_mensagem),
            "quem_enviou": "cliente",
            "tipo_mensagem": "text",
            "conteudo_texto": "Olá",
        }

    @staticmethod
    def _unidade(
        id_unidade: int = 1, *, idade_minima_suporte: int | None = None, bpa_ativo: bool = False
    ) -> dict[str, object]:
        return {
            "id_unidade": id_unidade,
            "nome_unidade": f"Unidade {id_unidade}",
            "idade_minima_suporte": idade_minima_suporte,
            "bpa_ativo": bpa_ativo,
        }

    @staticmethod
    def _linhas(segmentacao: dict[str, object]) -> dict[str, dict[str, object]]:
        return {linha["chave"]: linha for linha in segmentacao["linhas"]}

    def _segmentacao(
        self,
        perfis: list[dict[str, object]],
        enviados: set[int] | None = None,
        *,
        idade_minima_suporte: int | None = None,
        bpa_ativo: bool = False,
    ) -> dict[str, object]:
        return weekly._montar_segmentacao_perfis(
            perfis,
            enviados or set(),
            idade_minima_suporte=idade_minima_suporte,
            bpa_ativo=bpa_ativo,
        )

    def _snapshot(
        self,
        mensagens: list[dict[str, object]],
        funil: list[dict[str, object]],
        unidades: list[dict[str, object]] | None = None,
    ) -> dict[str, object]:
        return weekly.montar_snapshot(
            [self._unidade()] if unidades is None else unidades,
            mensagens,
            funil,
            [],
            self.INICIO,
            self.FIM,
        )

    def test_fronteiras_dependentes_com_minimo_padrao_e_bpa(self) -> None:
        casos = {
            3: (None, None),
            4: (None, "dependente_infantil"),
            5: ("dependente_infantil", "dependente_infantil"),
            17: ("dependente_infantil", "dependente_infantil"),
            18: ("dependente_adulto", "dependente_adulto"),
            45: ("dependente_adulto", "dependente_adulto"),
            59: ("dependente_adulto", "dependente_adulto"),
            60: ("dependente_idoso", "dependente_idoso"),
            99: ("dependente_idoso", "dependente_idoso"),
            100: (None, None),
        }
        for idade, resultados in casos.items():
            for minimo, esperado in zip((5, 4), resultados):
                with self.subTest(idade=idade, minimo=minimo):
                    self.assertEqual(
                        weekly._classificar_perfil_atendimento(
                            status_dependente=True,
                            idade_titular=60,
                            idade_dependente=idade,
                            idade_minima_dependente=minimo,
                        ),
                        esperado,
                    )

    def test_fronteiras_titulares_e_45_permanece_adulto(self) -> None:
        casos = {
            3: None,
            4: None,
            5: None,
            17: None,
            18: "titular_adulto",
            45: "titular_adulto",
            59: "titular_adulto",
            60: "titular_idoso",
            99: "titular_idoso",
            100: None,
        }
        for idade, esperado in casos.items():
            with self.subTest(idade=idade):
                self.assertEqual(
                    weekly._classificar_perfil_atendimento(
                        status_dependente=False,
                        idade_titular=idade,
                        idade_dependente=10,
                        idade_minima_dependente=5,
                    ),
                    esperado,
                )

    def test_idades_nulas_booleanas_fracionarias_e_legadas_sao_desconhecidas(self) -> None:
        for idade in (None, True, False, 18.0, 18.5, "18", "", -1, 0, 100):
            for dependente in (True, False):
                with self.subTest(idade=idade, tipo=type(idade), dependente=dependente):
                    self.assertIsNone(
                        weekly._classificar_perfil_atendimento(
                            status_dependente=dependente,
                            idade_titular=60 if dependente else idade,
                            idade_dependente=idade if dependente else 10,
                            idade_minima_dependente=4,
                        )
                    )

    def test_status_desconhecido_nao_e_inferido_das_idades(self) -> None:
        for status in (None, 0, 1, "true", "false", "", 1.0):
            with self.subTest(status=status, tipo=type(status)):
                self.assertIsNone(
                    weekly._classificar_perfil_atendimento(
                        status_dependente=status,
                        idade_titular=35,
                        idade_dependente=10,
                        idade_minima_dependente=5,
                    )
                )

    def test_so_a_idade_da_pessoa_atendida_classifica_o_perfil(self) -> None:
        for status, titular, dependente, esperado in (
            (True, None, 10, "dependente_infantil"),
            (True, 70, 20, "dependente_adulto"),
            (True, 35, None, None),
            (False, 70, None, "titular_idoso"),
            (False, 35, 70, "titular_adulto"),
            (False, None, 10, None),
        ):
            with self.subTest(status=status, titular=titular, dependente=dependente):
                self.assertEqual(
                    weekly._classificar_perfil_atendimento(
                        status_dependente=status,
                        idade_titular=titular,
                        idade_dependente=dependente,
                        idade_minima_dependente=5,
                    ),
                    esperado,
                )

    def test_bpa_altera_apenas_o_minimo_infantil_e_seu_rotulo(self) -> None:
        perfis = [
            self._perfil(1, 101, status_dependente=True, idade_dependente=4),
            self._perfil(2, 102, status_dependente=True, idade_dependente=5),
        ]
        for bpa, minimo, leads in ((False, 5, 1), (True, 4, 2)):
            with self.subTest(bpa=bpa):
                segmentacao = self._segmentacao(perfis, {101, 102}, bpa_ativo=bpa)
                infantil = self._linhas(segmentacao)["dependente_infantil"]
                self.assertEqual(segmentacao["idade_minima_dependente"], minimo)
                self.assertEqual(infantil["rotulo"], f"Dependentes de {minimo} a 17 anos")
                self.assertEqual(infantil["leads"], leads)
                self.assertEqual(infantil["leads_funil"], leads)

    def test_duas_conversas_do_mesmo_perfil_contam_um_lead(self) -> None:
        segmentacao = self._segmentacao(
            [self._perfil(1, 101), self._perfil(1, 102), self._perfil(2, 103)],
            {101, 102},
        )
        adulto = self._linhas(segmentacao)["titular_adulto"]
        self.assertEqual(adulto["leads"], 2)
        self.assertEqual(adulto["conversas"], 3)
        self.assertEqual(adulto["leads_funil"], 1)
        self.assertEqual(adulto["leads_funil_observados"], 1)
        self.assertEqual(adulto["conversas_funil"], 2)
        self.assertEqual(adulto["conversas_funil_observadas"], 2)
        self.assertEqual(adulto["taxa_funil"], 50.0)
        self.assertEqual(segmentacao["leads_classificados"], 2)
        self.assertEqual(segmentacao["leads_multiperfil"], 0)

    def test_envio_do_dependente_nao_e_herdado_pelo_titular(self) -> None:
        titular = self._perfil(1, 101)
        dependente = self._perfil(1, 102, status_dependente=True, idade_dependente=10)
        snapshot = self._snapshot(
            [self._mensagem(titular, 1), self._mensagem(dependente, 2)],
            [dependente],
        )
        unidade = snapshot["unidades"][0]
        segmentacao = unidade["metricas"]["segmentacao_perfis"]
        linhas = self._linhas(segmentacao)

        self.assertEqual(unidade["metricas"]["leads_contato"], 1)
        self.assertEqual(unidade["metricas"]["leads_funil"], 1)
        self.assertTrue(unidade["conversas"][0]["foi_funil"])
        self.assertEqual(linhas["dependente_infantil"]["leads_funil"], 1)
        self.assertEqual(linhas["titular_adulto"]["leads_funil"], 0)
        self.assertEqual(linhas["titular_adulto"]["leads_funil_observados"], 0)
        self.assertEqual(segmentacao["leads_classificados"], 1)
        self.assertEqual(segmentacao["leads_multiperfil"], 1)

    def test_mensagens_e_envios_repetidos_nao_duplicam_perfis_no_snapshot(self) -> None:
        perfil = self._perfil(1, 101)
        snapshot = self._snapshot(
            [self._mensagem(perfil, 1), self._mensagem(perfil, 2)],
            [perfil, perfil],
        )
        unidade = snapshot["unidades"][0]
        segmentacao = unidade["metricas"]["segmentacao_perfis"]
        adulto = self._linhas(segmentacao)["titular_adulto"]
        self.assertEqual(len(unidade["perfis_atendimento"]), 1)
        self.assertEqual(len(unidade["conversas"][0]["mensagens"]), 2)
        self.assertEqual(adulto["conversas"], 1)
        self.assertEqual(adulto["conversas_funil"], 1)
        self.assertEqual(segmentacao["conversas_apenas_envio_funil"], 0)

    def test_cliente_compartilhado_nao_mistura_envios_entre_unidades(self) -> None:
        perfil_a = self._perfil(1, 101, id_unidade=1)
        perfil_b = self._perfil(1, 201, id_unidade=2)
        snapshot = self._snapshot(
            [self._mensagem(perfil_a, 1), self._mensagem(perfil_b, 2)],
            [perfil_a],
            [self._unidade(1), self._unidade(2)],
        )
        unidades = {item["id_unidade"]: item for item in snapshot["unidades"]}
        for id_unidade, enviado in ((1, 1), (2, 0)):
            with self.subTest(id_unidade=id_unidade):
                metricas = unidades[id_unidade]["metricas"]
                linha = self._linhas(metricas["segmentacao_perfis"])["titular_adulto"]
                self.assertEqual(metricas["leads_contato"], 1)
                self.assertEqual(metricas["leads_funil"], enviado)
                self.assertEqual(linha["leads_funil"], enviado)
                self.assertEqual(linha["conversas"], 1)

    def test_configuracao_bpa_e_aplicada_por_unidade(self) -> None:
        perfis = [
            self._perfil(1, unidade * 100, id_unidade=unidade,
                         status_dependente=True, idade_dependente=4)
            for unidade in (1, 2)
        ]
        snapshot = self._snapshot(
            [self._mensagem(perfil, indice) for indice, perfil in enumerate(perfis, 1)],
            perfis,
            [self._unidade(1), self._unidade(2, bpa_ativo=True)],
        )
        unidades = {item["id_unidade"]: item for item in snapshot["unidades"]}
        for id_unidade, esperado in ((1, 0), (2, 1)):
            with self.subTest(id_unidade=id_unidade):
                segmentacao = unidades[id_unidade]["metricas"]["segmentacao_perfis"]
                infantil = self._linhas(segmentacao)["dependente_infantil"]
                self.assertEqual(infantil["leads"], esperado)
                self.assertEqual(infantil["leads_funil"], esperado)

    def test_retry_de_conversa_antiga_preserva_perfil_sem_importar_mensagens(self) -> None:
        antiga = self._perfil(1, 101, status_dependente=True, idade_dependente=17)
        nova = self._perfil(1, 102, idade_titular=45)
        snapshot = self._snapshot([self._mensagem(nova, 1)], [antiga])
        unidade = snapshot["unidades"][0]
        segmentacao = unidade["metricas"]["segmentacao_perfis"]
        linhas = self._linhas(segmentacao)

        self.assertEqual(unidade["metricas"]["leads_funil"], 1)
        self.assertEqual(unidade["conversas"][0]["ids_conversa"], [102])
        self.assertEqual(len(unidade["conversas"][0]["mensagens"]), 1)
        self.assertEqual({p["id_conversa"] for p in unidade["perfis_atendimento"]}, {101, 102})
        self.assertEqual(linhas["dependente_infantil"]["leads_funil"], 1)
        self.assertEqual(linhas["titular_adulto"]["leads_funil"], 0)
        self.assertEqual(segmentacao["conversas_apenas_envio_funil"], 1)
        self.assertEqual(segmentacao["conversas_classificadas"], 2)
        self.assertEqual(segmentacao["leads_multiperfil"], 1)

    def test_funil_fora_da_coorte_nao_acrescenta_lead_nem_perfil(self) -> None:
        contato = self._perfil(1, 101)
        fora_da_coorte = self._perfil(2, 201, idade_titular=60)
        outra_unidade = self._perfil(1, 301, id_unidade=2, idade_titular=60)
        snapshot = self._snapshot(
            [self._mensagem(contato, 1)],
            [fora_da_coorte, outra_unidade],
            [self._unidade(1), self._unidade(2)],
        )
        unidades = {item["id_unidade"]: item for item in snapshot["unidades"]}
        self.assertEqual(unidades[1]["metricas"]["leads_contato"], 1)
        self.assertEqual(unidades[2]["metricas"]["leads_contato"], 0)
        for unidade in unidades.values():
            segmentacao = unidade["metricas"]["segmentacao_perfis"]
            self.assertEqual(unidade["metricas"]["leads_funil"], 0)
            self.assertEqual(self._linhas(segmentacao)["titular_idoso"]["leads"], 0)
            self.assertEqual(segmentacao["conversas_apenas_envio_funil"], 0)

    def test_idade_minima_suporte_nao_apaga_envios_observados_nem_afeta_dependente(self) -> None:
        perfis = [
            self._perfil(1, 101, idade_titular=60),
            self._perfil(1, 102, idade_titular=60),
            self._perfil(2, 201, status_dependente=True, idade_dependente=60),
        ]
        for suporte in (None, 50, 60, 70, 80):
            with self.subTest(suporte=suporte):
                segmentacao = self._segmentacao(perfis, {101, 102, 201}, idade_minima_suporte=suporte)
                linhas = self._linhas(segmentacao)
                titular = linhas["titular_idoso"]
                self.assertEqual(titular["leads"], 1)
                self.assertEqual(titular["conversas"], 2)
                self.assertEqual(titular["leads_funil_observados"], 1)
                self.assertEqual(titular["conversas_funil_observadas"], 2)
                self.assertEqual(titular["leads_funil"], 1)
                self.assertEqual(titular["conversas_funil"], 2)
                self.assertEqual(titular["taxa_funil"], 100.0)
                self.assertFalse(titular["funil_nao_aplicavel"])
                self.assertEqual(linhas["dependente_idoso"]["leads_funil"], 1)
                self.assertEqual(linhas["dependente_idoso"]["taxa_funil"], 100.0)
                self.assertFalse(linhas["dependente_idoso"]["funil_nao_aplicavel"])

    def test_suporte_atual_preserva_funil_geral_do_snapshot(self) -> None:
        perfil = self._perfil(1, 101, idade_titular=60)
        snapshot = self._snapshot(
            [self._mensagem(perfil, 1)], [perfil], [self._unidade(idade_minima_suporte=60)]
        )
        metricas = snapshot["unidades"][0]["metricas"]
        titular = self._linhas(metricas["segmentacao_perfis"])["titular_idoso"]
        self.assertEqual(metricas["leads_funil"], 1)
        self.assertEqual(titular["leads_funil_observados"], 1)
        self.assertEqual(titular["leads_funil"], 1)
        self.assertEqual(titular["taxa_funil"], 100.0)

    def test_todos_os_perfis_empatados_sao_predominantes_por_leads(self) -> None:
        perfis = [
            self._perfil(1, 101),
            self._perfil(1, 102),
            self._perfil(2, 201, status_dependente=True, idade_dependente=10),
        ]
        segmentacao = self._segmentacao(perfis)
        self.assertCountEqual(
            segmentacao["perfis_predominantes"],
            ["Titulares de 18 a 59 anos", "Dependentes de 5 a 17 anos"],
        )

    def test_desconhecidos_separam_leads_conversas_e_envios_nao_classificados(self) -> None:
        perfis = [
            self._perfil(1, 101, status_dependente=None),
            self._perfil(1, 102),
            self._perfil(2, 201, status_dependente=None),
            self._perfil(2, 202),
            self._perfil(3, 301, idade_titular=None),
        ]
        # O envio do cliente 1 só tem perfil desconhecido; o do cliente 2 tem ambos.
        segmentacao = self._segmentacao(perfis, {101, 201, 202})
        self.assertEqual(segmentacao["leads_classificados"], 2)
        self.assertEqual(segmentacao["leads_sem_classificacao"], 1)
        self.assertEqual(segmentacao["conversas_classificadas"], 2)
        self.assertEqual(segmentacao["conversas_sem_classificacao"], 3)
        self.assertEqual(segmentacao["conversas_funil_sem_classificacao"], 2)
        self.assertEqual(segmentacao["leads_funil_apenas_sem_classificacao"], 1)
        self.assertEqual(segmentacao["cobertura_conversas"], 40.0)

    def test_snapshot_vazio_mantem_cinco_perfis_sem_divisao_por_zero(self) -> None:
        snapshot = self._snapshot([], [])
        unidade = snapshot["unidades"][0]
        segmentacao = unidade["metricas"]["segmentacao_perfis"]
        self.assertEqual(unidade["conversas"], [])
        self.assertEqual(unidade["perfis_atendimento"], [])
        self.assertEqual(unidade["metricas"]["leads_contato"], 0)
        self.assertEqual(unidade["metricas"]["taxa_funil"], 0.0)
        self.assertEqual(segmentacao["perfis_predominantes"], [])
        self.assertEqual(segmentacao["cobertura_conversas"], 0.0)
        self.assertEqual(segmentacao["leads_funil_apenas_sem_classificacao"], 0)
        self.assertEqual(set(self._linhas(segmentacao)), set(weekly.PERFIS_ATENDIMENTO))
        for linha in segmentacao["linhas"]:
            with self.subTest(perfil=linha["chave"]):
                for campo in ("leads", "conversas", "leads_funil", "conversas_funil",
                              "leads_funil_observados", "conversas_funil_observadas"):
                    self.assertEqual(linha[campo], 0)
                self.assertEqual(linha["taxa_funil"], 0.0)
        self.assertEqual(self._snapshot([], [], unidades=[])["unidades"], [])

    def test_sql_seleciona_perfis_por_conversa_com_janela_semiaberta_e_so_leitura(self) -> None:
        cursor = mock.MagicMock()
        cursor.fetchall.side_effect = [[self._unidade()], [], [], []]
        cursor.fetchone.return_value = {"existe": False}
        conn = mock.MagicMock()
        conn.cursor.return_value = cursor
        driver = types.ModuleType("psycopg")
        rows = types.ModuleType("psycopg.rows")
        rows.dict_row = object()
        driver.rows = rows

        with mock.patch.dict(sys.modules, {"psycopg": driver, "psycopg.rows": rows}):
            snapshot = weekly.coletar_snapshot(
                conn, self.INICIO, self.FIM, ids_unidade=[1], max_mensagens=100
            )

        consultas = [
            (" ".join(chamada.args[0].lower().split()), chamada.args[1:])
            for chamada in cursor.execute.call_args_list
        ]
        self.assertEqual(
            consultas[0][0],
            "begin transaction isolation level repeatable read read only",
        )
        sql_mensagens, params_mensagens = next(
            item for item in consultas if "with clientes_janela as" in item[0]
        )
        sql_funil, params_funil = next(
            item for item in consultas if "from chatbot.funil_envios f" in item[0]
        )
        for sql in (sql_mensagens, sql_funil):
            with self.subTest(consulta="funil" if sql == sql_funil else "mensagens"):
                for coluna in (
                    "c.id_conversa", "c.status_dependente", "cl.idade as idade_titular",
                    "d.idade as idade_dependente", "d.nome_dependente",
                ):
                    self.assertIn(coluna, sql)
                self.assertIn(
                    "left join chatbot.dependente d on d.id_conversa = c.id_conversa "
                    "and d.id_cliente = c.id_cliente",
                    sql,
                )
                self.assertIn("u.id_unidade = any(%s)", sql)
        self.assertIn("h0.quem_enviou = 'cliente'", sql_mensagens)
        self.assertIn("h0.received_data_hora >= %s", sql_mensagens)
        self.assertIn("h0.received_data_hora < %s", sql_mensagens)
        self.assertIn("h.received_data_hora >= %s", sql_mensagens)
        self.assertIn("h.received_data_hora < %s", sql_mensagens)
        self.assertIn("f.status = 'sent'", sql_funil)
        self.assertIn("f.enviado_em >= %s", sql_funil)
        self.assertIn("f.enviado_em < %s", sql_funil)
        self.assertEqual(
            params_mensagens,
            ((self.INICIO, self.FIM, [1], self.INICIO, self.FIM, 101),),
        )
        self.assertEqual(params_funil, ((self.INICIO, self.FIM, [1]),))
        for sql, _ in consultas:
            self.assertNotRegex(sql, r"\b(insert|update|delete|drop|truncate|alter)\b")
        conn.cursor.assert_called_once_with(row_factory=rows.dict_row)
        conn.rollback.assert_called_once_with()
        conn.commit.assert_not_called()
        cursor.close.assert_called_once_with()
        self.assertEqual(snapshot["unidades"][0]["metricas"]["leads_contato"], 0)


if __name__ == "__main__":
    unittest.main()
