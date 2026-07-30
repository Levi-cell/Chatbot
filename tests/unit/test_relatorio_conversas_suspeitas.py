import argparse
import csv
import io
import json
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from operations.monitoring import suspicious_conversations as relatorio


UTC = timezone.utc
BASE = datetime(2025, 1, 15, 12, 0, tzinfo=UTC)


def mensagem(
    indice,
    *,
    segundos,
    quem,
    etapa=4,
    fingerprint=None,
    tamanho=20,
    texto=None,
    tipo="text",
    id_fila=None,
    tem_url=False,
    tem_marcador_automacao=False,
):
    return {
        "id_mensagem": indice,
        "id_mensagem_fila": id_fila,
        "id_conversa": 10,
        "id_etapa": etapa,
        "instante": BASE + timedelta(seconds=segundos),
        "tipo_mensagem": tipo,
        "quem_enviou": quem,
        "fingerprint": fingerprint or f"fp-{indice}",
        "tamanho_texto": tamanho,
        "texto": texto,
        "tem_url": tem_url,
        "tem_marcador_automacao": tem_marcador_automacao,
    }


def conversa(**alteracoes):
    dados = {
        "id_conversa": 10,
        "id_cliente": 99,
        "nome_cliente": "Maria da Silva",
        "waid_telefone": "5511999998888",
        "id_unidade": 2,
        "nome_unidade": "Unidade Centro",
        "waba_id": "waba-2",
        "phone_number_id": "phone-2",
        "id_etapa_atual": 4,
        "status_ativa": True,
        "iniciou_em": BASE,
        "finalizou_em": None,
        "motivo_encerramento": None,
        "turnos_sem_avanco": None,
    }
    dados.update(alteracoes)
    return dados


def args_padrao(**alteracoes):
    dados = {
        "id_conversa": [10],
        "id_unidade": None,
        "todas_unidades": False,
        "inicio": "2025-01-15T00:00:00Z",
        "fim": "2025-01-16T00:00:00Z",
        "ultimas_horas": 24,
        "limite_conversas": 100,
        "limite_mensagens": 100,
        "max_mensagens_total": 10000,
        "limiar": 0,
        "formato": "json",
        "saida": None,
        "incluir_textos": False,
        "mostrar_wa_id": False,
        "max_amostras_texto": 5,
        "max_caracteres_texto": 160,
        "statement_timeout_ms": 15000,
        "lock_timeout_ms": 1000,
        "idle_timeout_ms": 20000,
    }
    dados.update(alteracoes)
    return argparse.Namespace(**dados)


class FakeCursor:
    def __init__(self, *, possui_turnos=True, conversas=None, mensagens=None):
        self.possui_turnos = possui_turnos
        self.conversas = conversas or []
        self.mensagens = mensagens or []
        self.calls = []
        self._resultado = []

    def execute(self, sql, parametros=None):
        self.calls.append((sql, parametros))
        normalizado = " ".join(sql.split())
        if "information_schema.columns" in normalizado:
            self._resultado = [(self.possui_turnos,)]
        elif "FROM chatbot.conversa AS c" in normalizado:
            self._resultado = self.conversas
        elif "FROM chatbot.historico_mensagens AS h" in normalizado:
            self._resultado = self.mensagens
        else:
            self._resultado = [(None,)]

    def fetchone(self):
        return self._resultado[0]

    def fetchall(self):
        return list(self._resultado)


class FakeConn:
    def __init__(self, cursor):
        self.cursor_obj = cursor
        self.closed = False
        self.rollbacks = 0

    def cursor(self):
        return self.cursor_obj

    def close(self):
        self.closed = True

    def rollback(self):
        self.rollbacks += 1


class PontuacaoTests(unittest.TestCase):
    def test_score_explicavel_usa_as_cinco_dimensoes(self):
        mensagens = []
        for indice in range(8):
            mensagens.append(
                mensagem(
                    indice + 1,
                    segundos=indice,
                    quem="bot" if indice % 2 == 0 else "cliente",
                    fingerprint="template" if indice % 2 == 0 else "cliente",
                    tamanho=30,
                )
            )
        resultado = relatorio.pontuar_conversa(
            conversa(
                turnos_sem_avanco=12,
                finalizou_em=BASE + timedelta(seconds=8),
            ),
            mensagens,
        )
        self.assertGreaterEqual(resultado["score"], 55)
        self.assertEqual(
            set(resultado["dimensoes"]),
            {
                "fluxo_sem_avanco",
                "repeticao_ciclos",
                "cadencia",
                "conteudo_automatizado",
                "conclusao_rapida",
            },
        )
        self.assertTrue(
            all(
                "pontos" in dimensao and "razoes" in dimensao
                for dimensao in resultado["dimensoes"].values()
            )
        )

    def test_funciona_sem_coluna_futura(self):
        mensagens = [
            mensagem(
                indice,
                segundos=indice * 5,
                quem="bot" if indice % 2 else "cliente",
                etapa=4,
            )
            for indice in range(1, 10)
        ]
        resultado = relatorio.pontuar_conversa(
            conversa(turnos_sem_avanco=None),
            mensagens,
        )
        self.assertIsInstance(resultado["score"], int)
        razoes = resultado["dimensoes"]["fluxo_sem_avanco"]["razoes"]
        self.assertFalse(any("contador persistido" in item for item in razoes))

    def test_fluxo_normal_nao_recebe_score_alto(self):
        mensagens = [
            mensagem(
                indice,
                segundos=indice * 60,
                quem="cliente" if indice % 2 else "bot",
                etapa=indice,
            )
            for indice in range(1, 7)
        ]
        resultado = relatorio.pontuar_conversa(
            conversa(turnos_sem_avanco=0),
            mensagens,
        )
        self.assertLess(resultado["score"], relatorio.DEFAULT_LIMIAR)

    def test_mesma_resposta_em_etapas_diferentes_nao_forma_loop(self):
        mensagens = [
            mensagem(
                indice,
                segundos=indice * 30,
                quem="cliente",
                etapa=indice,
                fingerprint="frequentemente",
                tipo="interactive",
            )
            for indice in range(1, 7)
        ]
        resultado = relatorio.pontuar_conversa(
            conversa(turnos_sem_avanco=None),
            mensagens,
        )
        repeticao = resultado["dimensoes"]["repeticao_ciclos"]
        self.assertEqual(repeticao["pontos"], 0)
        self.assertEqual(
            resultado["metricas"]["ciclos_cliente_detectados"],
            0,
        )

    def test_repeticao_do_nosso_bot_nao_pontua_conteudo_do_cliente(self):
        clientes = [
            mensagem(
                indice * 2,
                segundos=indice * 20,
                quem="cliente",
                etapa=indice,
                fingerprint=f"cliente-{indice}",
                tamanho=indice * 10,
            )
            for indice in range(1, 5)
        ]
        bots_repetidos = [
            mensagem(
                indice * 2 - 1,
                segundos=indice * 20 - 10,
                quem="bot",
                etapa=4,
                fingerprint="template-do-nosso-bot",
            )
            for indice in range(1, 5)
        ]
        resultado = relatorio.pontuar_conversa(
            conversa(),
            clientes + bots_repetidos,
        )
        self.assertEqual(
            resultado["dimensoes"]["conteudo_automatizado"]["pontos"],
            0,
        )
        self.assertEqual(
            resultado["metricas"]["respostas_cliente_repetidas_na_mesma_etapa"],
            0,
        )

    def test_cliente_abab_na_mesma_etapa_e_sinal_de_ciclo(self):
        mensagens = [
            mensagem(
                indice,
                segundos=indice * 10,
                quem="cliente",
                etapa=4,
                fingerprint=fingerprint,
            )
            for indice, fingerprint in enumerate(
                ("A", "B", "A", "B"),
                start=1,
            )
        ]
        resultado = relatorio.pontuar_conversa(conversa(), mensagens)
        self.assertGreater(
            resultado["dimensoes"]["repeticao_ciclos"]["pontos"],
            0,
        )
        self.assertGreater(
            resultado["metricas"]["ciclos_cliente_detectados"],
            0,
        )

    def test_latencia_e_bot_para_primeiro_cliente_seguinte(self):
        mensagens = [
            mensagem(1, segundos=0, quem="bot"),
            mensagem(2, segundos=1, quem="cliente"),
            mensagem(3, segundos=2, quem="cliente"),
            mensagem(4, segundos=10, quem="bot"),
            mensagem(5, segundos=15, quem="cliente"),
        ]
        resultado = relatorio.pontuar_conversa(conversa(), mensagens)
        self.assertEqual(
            resultado["metricas"]["latencias_bot_cliente"],
            [1.0, 5.0],
        )

    def test_movimentos_sao_pareados_por_id_mensagem_fila(self):
        mensagens = [
            mensagem(
                1,
                segundos=0,
                quem="cliente",
                etapa=None,
                id_fila=101,
            ),
            mensagem(
                2,
                segundos=1,
                quem="bot",
                etapa=1,
                id_fila=101,
            ),
            mensagem(
                3,
                segundos=10,
                quem="cliente",
                etapa=4,
                id_fila=102,
            ),
            mensagem(
                4,
                segundos=11,
                quem="bot",
                etapa=5,
                id_fila=102,
            ),
            mensagem(
                5,
                segundos=20,
                quem="cliente",
                etapa=5,
                id_fila=103,
            ),
            mensagem(
                6,
                segundos=21,
                quem="bot",
                etapa=5,
                id_fila=103,
            ),
            mensagem(
                7,
                segundos=30,
                quem="cliente",
                etapa=5,
                id_fila=None,
            ),
        ]
        self.assertEqual(
            [
                item["tipo"]
                for item in relatorio.reconstruir_movimentos(mensagens)
            ],
            ["inicializacao", "avanco", "sem_avanco", "indeterminado"],
        )

    def test_contador_doze_sozinho_supera_limiar_padrao(self):
        resultado = relatorio.pontuar_conversa(
            conversa(turnos_sem_avanco=12),
            [],
        )
        self.assertEqual(
            resultado["dimensoes"]["fluxo_sem_avanco"]["pontos"],
            70,
        )
        self.assertGreaterEqual(
            resultado["score"],
            relatorio.DEFAULT_LIMIAR,
        )


class PrivacidadeEFormatosTests(unittest.TestCase):
    def test_mascaramento_de_pii(self):
        original = (
            "maria@example.com +55 (11) 99999-8888 "
            "123.456.789-09 https://exemplo.com/abc 123456789"
        )
        mascarado = relatorio.mascarar_pii(original)
        self.assertNotIn("maria@example.com", mascarado)
        self.assertNotIn("99999-8888", mascarado)
        self.assertNotIn("123.456.789-09", mascarado)
        self.assertNotIn("https://exemplo.com/abc", mascarado)
        self.assertIn("[EMAIL]", mascarado)
        self.assertIn("[URL]", mascarado)
        self.assertEqual(
            relatorio.mascarar_wa_id("5511999998888"),
            "*********8888",
        )
        self.assertEqual(
            relatorio.mascarar_wa_id(
                "5511999998888",
                mostrar=True,
            ),
            "5511999998888",
        )
        self.assertNotEqual(
            relatorio.mascarar_nome("Maria da Silva"),
            "Maria da Silva",
        )

    def test_json_csv_e_texto_sao_validos(self):
        item = {
            "id_conversa": 10,
            "id_cliente": 99,
            "nome_cliente_mascarado": "M*** d*** S***",
            "wa_id_cliente": "*********8888",
            "id_unidade": 2,
            "nome_unidade": "Centro",
            "waba_id": "waba-2",
            "phone_number_id": "phone-2",
            "score": 80,
            "status_ativa": True,
            "id_etapa_atual": 4,
            "iniciou_em": BASE.isoformat(),
            "finalizou_em": None,
            "turnos_sem_avanco": 12,
            "historico_truncado": False,
            "dimensoes": {
                "fluxo_sem_avanco": {
                    "pontos": 20,
                    "maximo": 25,
                    "razoes": ["contador alto"],
                }
            },
            "metricas": {},
        }
        documento = {
            "metadados": {
                "inicio": BASE.isoformat(),
                "fim": (BASE + timedelta(hours=1)).isoformat(),
                "conversas_lidas": 1,
                "conversas_reportadas": 1,
                "limiar": 55,
            },
            "conversas": [item],
        }
        self.assertEqual(
            json.loads(relatorio.formatar_saida(documento, "json"))["conversas"][0]["score"],
            80,
        )
        linhas_csv = list(
            csv.DictReader(
                io.StringIO(relatorio.formatar_saida(documento, "csv"))
            )
        )
        self.assertEqual(linhas_csv[0]["id_conversa"], "10")
        self.assertIn(
            "conversa=10",
            relatorio.formatar_saida(documento, "texto"),
        )


class BancoSomenteLeituraTests(unittest.TestCase):
    def _linha_conversa(self, turnos):
        return (
            10,
            99,
            "Maria da Silva",
            "5511999998888",
            2,
            "Centro",
            "waba-2",
            "phone-2",
            4,
            True,
            BASE,
            None,
            None,
            turnos,
        )

    def _linha_mensagem(self):
        return (
            1,
            1001,
            10,
            4,
            BASE,
            "text",
            "bot",
            "fingerprint",
            20,
            False,
            False,
            None,
            1,
        )

    def test_transacao_timeouts_selects_e_texto_omitido(self):
        cursor = FakeCursor(
            possui_turnos=False,
            conversas=[self._linha_conversa(None)],
            mensagens=[self._linha_mensagem()],
        )
        conn = FakeConn(cursor)
        documento = relatorio.gerar_relatorio(
            args_padrao(),
            connection_factory=lambda **_kwargs: conn,
        )
        sql_total = "\n".join(sql for sql, _params in cursor.calls)
        self.assertIn(
            "BEGIN TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY",
            sql_total,
        )
        self.assertIn("statement_timeout", sql_total)
        self.assertIn("lock_timeout", sql_total)
        self.assertIn("idle_in_transaction_session_timeout", sql_total)
        self.assertIn("NULL::integer AS turnos_sem_avanco", sql_total)
        self.assertIn("NULL::text AS conteudo_texto", sql_total)
        self.assertIn(
            "ORDER BY h.received_data_hora DESC, h.id_mensagem DESC",
            sql_total,
        )
        self.assertIn("JOIN chatbot.cliente AS cl", sql_total)
        self.assertIn("u.waba_id", sql_total)
        self.assertIn("u.phone_number_id", sql_total)
        self.assertNotRegex(
            sql_total.upper(),
            r"\b(INSERT|UPDATE|DELETE|ALTER|CREATE|DROP|TRUNCATE|FOR UPDATE)\b",
        )
        self.assertNotIn("cliente_telefone", sql_total)
        self.assertNotIn("id_phone_unidade", sql_total)
        self.assertTrue(conn.closed)
        self.assertEqual(conn.rollbacks, 1)
        self.assertFalse(documento["metadados"]["textos_incluidos"])
        self.assertEqual(
            documento["conversas"][0]["wa_id_cliente"],
            "*********8888",
        )

    def test_coluna_futura_e_texto_explicito(self):
        linha = list(self._linha_mensagem())
        linha[11] = "contato maria@example.com"
        cursor = FakeCursor(
            possui_turnos=True,
            conversas=[self._linha_conversa(12)],
            mensagens=[tuple(linha)],
        )
        conn = FakeConn(cursor)
        documento = relatorio.gerar_relatorio(
            args_padrao(incluir_textos=True),
            connection_factory=lambda **_kwargs: conn,
        )
        sql_total = "\n".join(sql for sql, _params in cursor.calls)
        self.assertIn("c.turnos_sem_avanco", sql_total)
        self.assertIn("h.conteudo_texto", sql_total)
        amostra = documento["conversas"][0]["amostras_texto_mascarado"][0]
        self.assertEqual(amostra["texto"], "contato [EMAIL]")

    def test_wa_id_completo_exige_flag_explicita(self):
        cursor = FakeCursor(
            conversas=[self._linha_conversa(12)],
            mensagens=[],
        )
        documento = relatorio.gerar_relatorio(
            args_padrao(mostrar_wa_id=True),
            connection_factory=lambda **_kwargs: FakeConn(cursor),
        )
        self.assertEqual(
            documento["conversas"][0]["wa_id_cliente"],
            "5511999998888",
        )

    def test_limite_de_conversas_falha_fechando_conexao(self):
        cursor = FakeCursor(
            conversas=[
                self._linha_conversa(0),
                self._linha_conversa(0),
            ]
        )
        conn = FakeConn(cursor)
        with self.assertRaisesRegex(RuntimeError, "limite de conversas"):
            relatorio.gerar_relatorio(
                args_padrao(limite_conversas=1),
                connection_factory=lambda **_kwargs: conn,
            )
        self.assertTrue(conn.closed)

    def test_filtros_multiunidade_sao_parametrizados(self):
        cursor = FakeCursor()
        conn = FakeConn(cursor)
        relatorio.gerar_relatorio(
            args_padrao(
                id_conversa=None,
                id_unidade=[2, 7],
                todas_unidades=False,
            ),
            connection_factory=lambda **_kwargs: conn,
        )
        chamada = next(
            (sql, params)
            for sql, params in cursor.calls
            if "FROM chatbot.conversa AS c" in sql
        )
        self.assertIn("c.id_unidade = ANY(%s)", chamada[0])
        self.assertIn([2, 7], chamada[1])


class CliELimitesTests(unittest.TestCase):
    def test_cli_exige_escopo_explicito(self):
        parser = relatorio.criar_parser()
        args = parser.parse_args([])
        with self.assertRaises(SystemExit):
            relatorio.validar_args(parser, args)

    def test_janela_maxima_e_validada(self):
        with self.assertRaisesRegex(ValueError, "31 dias"):
            relatorio.resolver_janela(
                args_padrao(
                    inicio="2025-01-01T00:00:00Z",
                    fim="2025-03-01T00:00:00Z",
                )
            )

    def test_main_escreve_stdout_sem_arquivo(self):
        documento = {
            "metadados": {
                "inicio": BASE.isoformat(),
                "fim": (BASE + timedelta(hours=1)).isoformat(),
                "conversas_lidas": 0,
                "conversas_reportadas": 0,
                "limiar": 55,
            },
            "conversas": [],
        }
        with patch.object(
            relatorio,
            "gerar_relatorio",
            return_value=documento,
        ), patch.object(relatorio.sys, "stdout", new_callable=io.StringIO) as saida:
            codigo = relatorio.main(["--id-conversa", "10"])
        self.assertEqual(codigo, 0)
        self.assertIn("RELATÓRIO MANUAL", saida.getvalue())


if __name__ == "__main__":
    unittest.main()
