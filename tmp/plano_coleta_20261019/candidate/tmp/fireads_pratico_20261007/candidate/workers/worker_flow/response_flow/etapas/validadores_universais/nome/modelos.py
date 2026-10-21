from dataclasses import dataclass


STATUS_VALIDO = "valido"
STATUS_INVALIDO = "invalido"
STATUS_AMBIGUO = "ambiguo"


@dataclass(frozen=True)
class ResultadoValidacaoNome:
    valido: bool
    primeiro_nome: str | None = None
    motivo: str | None = None
    status: str = STATUS_INVALIDO
    confianca: float = 1.0

    def __post_init__(self):
        if not 0.0 <= self.confianca <= 1.0:
            raise ValueError("A confianca precisa estar entre 0 e 1")

        if self.valido:
            if not self.primeiro_nome:
                raise ValueError("Resultado valido precisa conter primeiro nome")

            if self.status != STATUS_VALIDO:
                raise ValueError("Resultado valido precisa usar status=valido")

            if self.motivo is not None:
                raise ValueError("Resultado valido nao pode conter motivo")

            return

        if self.primeiro_nome is not None:
            raise ValueError("Resultado invalido nao pode conter primeiro nome")

        if self.motivo is None:
            raise ValueError("Resultado invalido precisa conter motivo")

        if self.status not in {STATUS_INVALIDO, STATUS_AMBIGUO}:
            raise ValueError(
                "Resultado invalido precisa usar status invalido ou ambiguo"
            )
