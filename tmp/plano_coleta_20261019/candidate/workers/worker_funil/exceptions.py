"""Falhas que exigem reiniciar o ciclo completo do worker de Funil."""


class BancoFalhouAposEnvioFunil(RuntimeError):
    """O CRM confirmou o lead antes de o estado local conseguir commitar."""

