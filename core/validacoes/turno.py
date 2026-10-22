"""Domínio persistido da preferência de turno; não representa uma reserva."""

TURNOS = ("manha", "tarde", "noite", "sabado")
ROTULOS_TURNO = {"manha": "manhã", "tarde": "tarde", "noite": "noite", "sabado": "sábado"}


def validar_turno(turno):
    if turno not in TURNOS:
        raise ValueError("Turno deve ser manha, tarde, noite ou sabado")
    return turno
