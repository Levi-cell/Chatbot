"""Fornece o snapshot fictício usado somente pelas sondas manuais do Funil."""

from datetime import datetime


def montar_dados_lead_teste():
    """Monta dados inofensivos sem consultar banco nem executar requisição."""
    return {
        "id_conversa": int(datetime.now().strftime("%m%d%H%M%S")),
        "id_unidade": 1,
        "nome_unidade": "Supera Santo Antônio de Jesus",
        "status_dependente": True,
        "nome_cliente": "Edcarlos Teste - Não contatar",
        "telefone_cliente": "5571994111866",
        "email_cliente": "edcaspfilho+teste@gmail.com",
        "idade_cliente": None,
        "profissao": "Engenheiro",
        "nome_dependente": "Enzo Teste",
        "idade_dependente": 12,
        "triagem_respostas": [
            {"id_etapa": 12, "resposta": "nunca"},
            {"id_etapa": 13, "resposta": "às vezes"},
            {"id_etapa": 14, "resposta": "frequentemente"},
            {"id_etapa": 15, "resposta": "às vezes"},
            {"id_etapa": 16, "resposta": "nunca"},
            {"id_etapa": 17, "resposta": "às vezes"},
        ],
    }
