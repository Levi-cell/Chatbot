import unittest
from types import SimpleNamespace
from unittest.mock import patch

from core.integrations.whatsapp.tools import usuarios


class FakePaginadorBloqueios:
    def __init__(self, bloqueados):
        self.bloqueados = bloqueados
        self.chamadas = []

    def all(self, **kwargs):
        self.chamadas.append(kwargs)
        return self.bloqueados


class FakeClienteWa:
    def __init__(self):
        self.chamadas_bloqueio = []
        self.chamadas_desbloqueio = []
        self.resultado_bloqueio = SimpleNamespace(errors=None)
        self.resultado_desbloqueio = SimpleNamespace(errors=None)
        self.paginador = FakePaginadorBloqueios([])

    def block_users(self, **kwargs):
        self.chamadas_bloqueio.append(kwargs)
        return self.resultado_bloqueio

    def unblock_users(self, **kwargs):
        self.chamadas_desbloqueio.append(kwargs)
        return self.resultado_desbloqueio

    def get_blocked_users(self):
        return self.paginador


class WhatsappUsuariosTests(unittest.TestCase):
    def test_bloqueio_normaliza_ids_e_retorna_resultado_meta(self):
        cliente_wa = FakeClienteWa()

        with patch.object(usuarios, "conta_wa", return_value=cliente_wa):
            resultado = usuarios.bloquear_usuario_meta(5571999999999, 123456)

        self.assertIs(resultado, cliente_wa.resultado_bloqueio)
        self.assertEqual(
            cliente_wa.chamadas_bloqueio,
            [{"users": ["5571999999999"], "phone_id": "123456"}],
        )

    def test_desbloqueio_normaliza_ids_e_retorna_resultado_meta(self):
        cliente_wa = FakeClienteWa()

        with patch.object(usuarios, "conta_wa", return_value=cliente_wa):
            resultado = usuarios.desbloquear_usuario_meta(5571999999999, 123456)

        self.assertIs(resultado, cliente_wa.resultado_desbloqueio)
        self.assertEqual(
            cliente_wa.chamadas_desbloqueio,
            [{"users": ["5571999999999"], "phone_id": "123456"}],
        )

    def test_erro_retornado_pela_pywa_nao_e_tratado_como_sucesso(self):
        cliente_wa = FakeClienteWa()
        cliente_wa.resultado_bloqueio = SimpleNamespace(
            errors=[{"code": "falha_meta"}],
        )

        with patch.object(usuarios, "conta_wa", return_value=cliente_wa):
            with self.assertRaisesRegex(RuntimeError, "erro ao bloquear usuario"):
                usuarios.bloquear_usuario_meta("5571999999999", "123456")

    def test_listagem_preserva_paginacao_controlada(self):
        cliente_wa = FakeClienteWa()
        bloqueados = [SimpleNamespace(wa_id="5571999999999")]
        cliente_wa.paginador = FakePaginadorBloqueios(bloqueados)

        with patch.object(usuarios, "conta_wa", return_value=cliente_wa):
            resultado = usuarios.listar_usuarios_bloqueados_meta("123456")

        self.assertEqual(resultado, bloqueados)
        self.assertEqual(cliente_wa.paginador.chamadas, [{"sleep": 0.2}])


if __name__ == "__main__":
    unittest.main()
