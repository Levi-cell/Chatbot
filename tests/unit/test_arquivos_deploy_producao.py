import unittest
from pathlib import Path


RAIZ_PROJETO = Path(__file__).resolve().parents[2]
DEPLOY = RAIZ_PROJETO / "deploy"


class ArquivosDeployProducaoTests(unittest.TestCase):
    def test_tres_servicos_sao_independentes_e_supervisionados(self):
        unidades = {
            "chatbot-webhook.service": (
                "gunicorn",
                "--bind 127.0.0.1:8000",
            ),
            "chatbot-worker-flow.service": (
                "python -m workers.worker_flow.iniciar_flow_worker",
            ),
            "chatbot-worker-funil.service": (
                "python -m workers.worker_funil.iniciar_worker_funil",
            ),
        }

        for nome, comandos in unidades.items():
            with self.subTest(servico=nome):
                conteudo = (DEPLOY / "systemd" / nome).read_text(encoding="utf-8")
                self.assertIn("User=chatbot", conteudo)
                self.assertIn("Group=chatbot", conteudo)
                self.assertIn(
                    "EnvironmentFile=/etc/chatbot/chatbot.env",
                    conteudo,
                )
                self.assertIn("Restart=always", conteudo)
                self.assertIn("WantedBy=multi-user.target", conteudo)

                for comando in comandos:
                    self.assertIn(comando, conteudo)

    def test_nginx_expoe_somente_o_proxy_local_do_gunicorn(self):
        conteudo = (DEPLOY / "nginx" / "chatbot.conf").read_text(
            encoding="utf-8"
        )

        self.assertIn("listen 80;", conteudo)
        self.assertIn("server_name __DOMAIN__;", conteudo)
        self.assertIn("proxy_pass http://127.0.0.1:8000;", conteudo)
        self.assertIn("proxy_set_header X-Forwarded-Proto $scheme;", conteudo)
        self.assertNotIn("0.0.0.0:8000", conteudo)
        self.assertNotIn("listen 6379", conteudo)
        self.assertNotIn("listen 5432", conteudo)


if __name__ == "__main__":
    unittest.main()
