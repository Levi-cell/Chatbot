"""Sinal de espera persistida; nenhuma execução paralela em memória."""


class ConsultaFireAdsPendente(Exception):
    """Confirmar a solicitação e reagendar a mensagem sem consumir tentativa."""
