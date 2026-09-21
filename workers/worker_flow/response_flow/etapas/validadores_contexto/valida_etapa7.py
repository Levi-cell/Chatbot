from workers.worker_flow.response_flow.etapas.validadores_universais.validador_aceite_reserva import (
    OPCAO_ACEITA,
    OPCAO_ADIADA,
    validar_aceite_reserva,
)
from workers.worker_flow.response_flow.transicoes.eventos import (
    EVENTO_OFERTA_ACEITA,
    EVENTO_OFERTA_ADIADA,
)


TIPO_TRATAMENTO_CONTEXTO_INVALIDO = "opcao_invalida"


def validar_etapa7(conteudo_texto):
    """Converte a intenção de reserva no evento próprio desta etapa."""
    opcao = validar_aceite_reserva(conteudo_texto)
    return {
        OPCAO_ACEITA: EVENTO_OFERTA_ACEITA,
        OPCAO_ADIADA: EVENTO_OFERTA_ADIADA,
    }.get(opcao)
