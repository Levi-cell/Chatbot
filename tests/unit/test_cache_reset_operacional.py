import fnmatch
import io
import unittest
from contextlib import redirect_stderr
from unittest.mock import patch

from core.cache import cache_reset


class FakeRedis:
    def __init__(self, chaves):
        self.chaves = set(chaves)

    def scan_iter(self, match, count):
        del count
        for chave in sorted(self.chaves):
            if fnmatch.fnmatch(chave, match):
                yield chave

    def delete(self, *chaves):
        removidas = 0
        for chave in chaves:
            if chave in self.chaves:
                self.chaves.remove(chave)
                removidas += 1
        return removidas


class CacheResetOperacionalTests(unittest.TestCase):
    def test_remove_somente_chaves_operacionais(self):
        chaves_operacionais = {
            "cliente_cache:5511999999999",
            "conversa_bloqueada:hash-conversa",
            "webhook_flood_rate:60:janela:hash",
        }
        chaves_preservadas = {
            *cache_reset.CHAVES_EXATAS_RESET,
            "unidades_cache:admin_preflight",
            "configuracao:integracao:funil",
            "outra_chave:sem_relacao",
        }
        redis = FakeRedis(chaves_operacionais | chaves_preservadas)

        resultado = cache_reset.resetar_cache_operacional(redis)

        self.assertEqual(resultado["total_removido"], 3)
        self.assertEqual(redis.chaves, chaves_preservadas)
        self.assertEqual(
            resultado["chaves_por_padrao"],
            {
                "cliente_cache:*": 1,
                "conversa_bloqueada:*": 1,
                "webhook_flood_rate:*": 1,
            },
        )

    def test_reset_operacional_e_idempotente(self):
        redis = FakeRedis({"cliente_cache:5511999999999"})

        primeiro = cache_reset.resetar_cache_operacional(redis)
        segundo = cache_reset.resetar_cache_operacional(redis)

        self.assertEqual(primeiro["total_removido"], 1)
        self.assertEqual(segundo["total_removido"], 0)

    def test_processa_mais_de_quinhentas_chaves_em_lotes(self):
        redis = FakeRedis(
            {f"cliente_cache:{indice}" for indice in range(501)}
            | {"unidades_cache"}
        )

        resultado = cache_reset.resetar_cache_operacional(redis)

        self.assertEqual(resultado["total_removido"], 501)
        self.assertEqual(redis.chaves, {"unidades_cache"})

    def test_cli_exige_confirmacao_operacional_explicita(self):
        with redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as erro:
                cache_reset.main([])

        self.assertEqual(erro.exception.code, 2)

    def test_cli_retorna_sucesso(self):
        with patch.object(
            cache_reset,
            "resetar_cache_operacional",
            return_value={
                "total_removido": 2,
                "chaves_por_padrao": {"cliente_cache:*": 2},
            },
        ), patch("builtins.print"):
            codigo = cache_reset.main(["--operacional"])

        self.assertEqual(codigo, 0)

    def test_cli_retorna_erro_se_redis_falhar(self):
        with patch.object(
            cache_reset,
            "resetar_cache_operacional",
            side_effect=ConnectionError("redis indisponivel"),
        ), patch("builtins.print"):
            codigo = cache_reset.main(["--operacional"])

        self.assertEqual(codigo, 1)


if __name__ == "__main__":
    unittest.main()
