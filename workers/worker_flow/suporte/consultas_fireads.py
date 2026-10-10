"""Executa apenas a leitura HTTP fora do ciclo, sem compartilhar conexão SQL."""

from collections import OrderedDict
from concurrent.futures import Future
from threading import Lock, Thread


class ConsultaFireAdsPendente(Exception):
    """A mensagem deve aguardar sem resposta e sem consumir uma tentativa."""


class ConsultasFireAdsEmAndamento:
    """Reutiliza uma leitura por conversa/configuração até o commit da decisão.

    Os limites controlam recursos, nunca o tempo da consulta. A fila do banco
    guarda as mensagens que aguardam uma vaga. Após reiniciar o processo, uma
    leitura não confirmada pode ser refeita: esta classe não executa escritas.
    """

    def __init__(self, *, simultaneas=4, resultados=64):
        if simultaneas < 1 or resultados < simultaneas:
            raise ValueError("Limites de consultas FireAds inválidos")
        self.simultaneas = simultaneas
        self.resultados = resultados
        self._consultas = OrderedDict()
        self._lock = Lock()

    def obter(self, chave, consultar, *args):
        """Devolve imediatamente a mesma Future enquanto a leitura estiver ativa."""
        with self._lock:
            if chave in self._consultas:
                self._consultas.move_to_end(chave)
                return self._consultas[chave]
            if sum(not f.done() for f in self._consultas.values()) >= self.simultaneas:
                raise ConsultaFireAdsPendente("aguardando_vaga")
            # Resultados abandonados (ex.: conversa removida) não crescem sem limite.
            if len(self._consultas) >= self.resultados:
                antiga = next(k for k, f in self._consultas.items() if f.done())
                del self._consultas[antiga]
            futuro = Future()
            self._consultas[chave] = futuro
            # Daemon permite parar/reiniciar o serviço mesmo se a rede nunca voltar.
            thread = Thread(
                target=self._executar,
                args=(futuro, consultar, args),
                name="fireads-consulta",
                daemon=True,
            )
            try:
                thread.start()
            except Exception:
                del self._consultas[chave]
                raise
            return futuro

    @staticmethod
    def _executar(futuro, consultar, args):
        try:
            resultado = consultar(*args)
        except BaseException as erro:
            futuro.set_exception(erro)
        else:
            futuro.set_result(resultado)

    def confirmar(self, chave, futuro):
        """Descarta somente depois do commit; falha no banco pode reutilizar a leitura."""
        with self._lock:
            if self._consultas.get(chave) is futuro and futuro.done():
                del self._consultas[chave]
