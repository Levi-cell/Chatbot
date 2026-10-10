"""GET e POST limitados ao Web App; nenhuma escrita durante importação."""

import time
from urllib.parse import urlparse
import requests
from .contrato import ErroFireAds


class PrazoConsultaFireAdsEsgotado(ErroFireAds):
    """O orçamento total da leitura terminou, inclusive seus redirecionamentos."""


def validar_url(url, *, resposta=False):
    p = urlparse(str(url))
    host = "script.googleusercontent.com" if resposta else "script.google.com"
    if (
        p.scheme != "https"
        or p.hostname != host
        or p.username
        or p.password
        or p.port not in (None, 443)
        or (
            not resposta
            and (not p.path.startswith("/macros/s/") or not p.path.endswith("/exec"))
        )
    ):
        raise ErroFireAds("URL FireAds inválida: usar Web App /exec HTTPS")
    return url


class ClienteFireAds:
    def __init__(self, url, *, segundos=25, timeout_leitura=8, session=None):
        """Leitura=None usa o prazo restante; padrões das escritas são preservados."""
        self.url = validar_url(url)
        self.deadline = None if segundos is None else time.monotonic() + segundos
        self.timeout_leitura = timeout_leitura
        self.session = session or requests.Session()
        self.session.headers.update({"Accept": "application/json"})

    def close(self):
        self.session.close()

    def _request(self, method, url, **kwargs):
        timeout = None
        if self.deadline is not None:
            restante = self.deadline - time.monotonic()
            if restante <= 0:
                raise PrazoConsultaFireAdsEsgotado("Orçamento de consulta FireAds esgotado")
            leitura = (
                restante if self.timeout_leitura is None
                else min(self.timeout_leitura, restante)
            )
            timeout = (min(4, restante), leitura)
        # O prazo da abertura é compartilhado entre abas e redirects.
        # Escritas e redirects continuam sem repetição automática de POST.
        response = self.session.request(
            method,
            url,
            timeout=timeout,
            allow_redirects=False,
            **kwargs
        )
        if response.status_code in (301, 302, 303):
            alvo = response.headers.get("Location", "")
            validar_url(alvo, resposta=True)
            response = self._request("GET", alvo)
        response.raise_for_status()
        if self.deadline is not None and time.monotonic() > self.deadline:
            raise PrazoConsultaFireAdsEsgotado("Resposta FireAds após o prazo")
        return response

    def _json(self, response):
        try:
            body = response.json()
        except ValueError as exc:
            raise ErroFireAds("Resposta FireAds não é JSON") from exc
        if not isinstance(body, dict) or body.get("success") is not True:
            raise ErroFireAds("FireAds recusou a operação")
        return body

    def consultar(self, aba):
        body = self._json(
            self._request("GET", self.url, params={"sheet": aba, "abas": "0"})
        )
        data = body.get("data")
        if (
            not isinstance(data, dict)
            or data.get("aba") != aba
            or not isinstance(data.get("headers"), list)
            or not isinstance(data.get("rows"), list)
            or any(not isinstance(r, dict) for r in data["rows"])
        ):
            raise ErroFireAds("Consulta incompleta ou aba divergente")
        return data

    def enviar(self, aba, *, dados=None, row=None, observacoes=None):
        if row is None:
            payload = {"action": "append", "sheet": aba, "rows": [dados]}
        else:
            payload = {
                "sheet": aba,
                "row": int(row),
                "updates": {"Observação": observacoes},
            }
        result = self._json(self._request("POST", self.url, json=payload))
        if result.get("aba") != aba:
            raise ErroFireAds("Recibo de outra aba")
        if row is None:
            if result.get("inserted") != 1:
                raise ErroFireAds("Cadastro sem confirmação de uma linha")
        elif result.get("row") != row or "Observação" not in result.get("updated", []):
            raise ErroFireAds("Update sem confirmação da linha/coluna")
        return result
