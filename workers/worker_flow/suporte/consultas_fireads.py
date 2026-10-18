"""Sinal de espera persistida; nenhuma execução paralela em memória."""


class ConsultaFireAdsPendente(Exception):
    """Confirmar a solicitação e reagendar a mensagem sem consumir tentativa."""

    def __init__(self, motivo="aguardando_resultado", *, consulta_nova=False):
        super().__init__(motivo)
        self.consulta_nova = consulta_nova
