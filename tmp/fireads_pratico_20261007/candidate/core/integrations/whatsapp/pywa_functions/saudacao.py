from datetime import datetime
from zoneinfo import ZoneInfo


FUSO_HORARIO_ATENDIMENTO = ZoneInfo("America/Sao_Paulo")


def obter_saudacao_por_horario(agora=None):
    if agora is None:
        agora = datetime.now(FUSO_HORARIO_ATENDIMENTO)

    hora = agora.hour

    if 5 <= hora < 12:
        return "Bom dia"

    if 12 <= hora < 18:
        return "Boa tarde"

    return "Boa noite"
