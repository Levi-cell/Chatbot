"""Persistência da preferência, sob a transação final do worker."""

from core.validacoes.turno import validar_turno


def salvar_turno_conversa(id_conversa, id_unidade, turno, cursor):
    validar_turno(turno)
    cursor.execute(
        """
        UPDATE chatbot.conversa SET turno = %s
        WHERE id_conversa = %s AND id_unidade = %s
          AND (turno IS NULL OR turno = %s)
        RETURNING turno;
        """,
        (turno, id_conversa, id_unidade, turno),
    )
    if cursor.fetchone() is None:
        raise ValueError("Conversa ausente ou turno divergente no replay")
    return {"turno_persistido": True, "turno": turno}
