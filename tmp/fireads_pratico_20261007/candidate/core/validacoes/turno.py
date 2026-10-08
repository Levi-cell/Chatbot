"""Domínio persistido da preferência de turno; não representa uma reserva."""

TURNOS = ("manha", "tarde", "noite")
ROTULOS_TURNO = {"manha": "manhã", "tarde": "tarde", "noite": "noite"}


def validar_turno(turno):
    if turno not in TURNOS:
        raise ValueError("Turno deve ser manha, tarde ou noite")
    return turno
