"""GET e POST limitados ao Web App; nenhuma escrita durante importação."""

import time
from urllib.parse import urlparse
import requests
from .contrato import ErroFireAds, normalizar


class TelefoneDuplicadoFireAds(ErroFireAds):
    """Recusa inequívoca do append; não representa timeout ou falha genérica."""


def _duplicidade(body):
    return isinstance(body, dict) and body.get('success') is False and (
        body.get('code') == 'DUPLICATE_PHONE' or normalizar(body.get('error')) in {
            'telefone ja cadastrado', 'telefone duplicado', 'numero de telefone ja cadastrado',
        })


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
    def __init__(self, url, *, segundos=25, timeout_leitura=8, session=None, por_operacao=False):
        """Leitura=None usa o prazo restante; padrões das escritas são preservados."""
        self.url = validar_url(url)
        self.segundos = segundos
        self.por_operacao = por_operacao
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
        if _duplicidade(body):
            raise TelefoneDuplicadoFireAds('Criação recusada por telefone duplicado')
        if not isinstance(body, dict) or body.get("success") is not True:
            if isinstance(body, dict) and str(body.get('error') or '').startswith('Coluna não editável:'):
                raise ErroFireAds('Web App FireAds não autoriza as colunas; atualizar EDITABLE_COLUMNS')
            raise ErroFireAds("FireAds recusou a operação")
        return body

    def consultar(self, aba):
        self._iniciar_operacao()
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

    def enviar(self, aba, *, dados=None, row=None, observacoes=None, campos=None):
        self._iniciar_operacao()
        if row is None:
            if campos:
                raise ErroFireAds("Campos de atualização sem linha de destino")
            payload = {"action": "append", "sheet": aba, "rows": [dados]}
        else:
            campos = dict(campos or {})
            if (not set(campos) <= {"Nome", "Email", "Para quem é", "Período preferido"}
                    or any(not isinstance(v, str) or not v.strip() for v in campos.values())):
                raise ErroFireAds("Campos de sincronização inválidos")
            payload = {
                "sheet": aba,
                "row": int(row),
                "updates": {**campos, "Observação": observacoes},
            }
        try:
            result = self._json(self._request("POST", self.url, json=payload))
        except requests.HTTPError as exc:
            if row is None and exc.response is not None and exc.response.status_code in (400, 409):
                try:
                    recusada = _duplicidade(exc.response.json())
                except ValueError:
                    recusada = False
                if recusada:
                    raise TelefoneDuplicadoFireAds('Criação recusada por telefone duplicado') from None
            raise
        if result.get("aba") != aba:
            raise ErroFireAds("Recibo de outra aba")
        if row is None:
            if result.get("inserted") != 1:
                raise ErroFireAds("Cadastro sem confirmação de uma linha")
        elif (result.get("row") != row or not isinstance(result.get("updated"), list)
              or not set(payload['updates']) <= set(result['updated'])):
            raise ErroFireAds("Update sem confirmação da linha/coluna")
        return result

    def _iniciar_operacao(self):
        # GET e POST têm orçamentos próprios. Redirects não reiniciam o prazo.
        if self.por_operacao:
            self.deadline = None if self.segundos is None else time.monotonic() + self.segundos
