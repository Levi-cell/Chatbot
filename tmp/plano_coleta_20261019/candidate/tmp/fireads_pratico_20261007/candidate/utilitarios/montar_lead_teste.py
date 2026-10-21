"""Fornece snapshots fictícios isolados para as sondas do Funil."""

from datetime import datetime
from unicodedata import normalize


ID_UNIDADE_TESTE_SEM_CADASTRO = -1


def montar_dados_lead_teste_saj():
    """Monta um lead fictício identificado com a unidade SAJ."""
    return _montar_dados_lead_teste(
        id_unidade=1,
        nome_unidade="Supera Santo Antônio de Jesus",
        identificador="SAJ",
    )


def montar_dados_lead_teste_rio_vermelho():
    """Monta um lead fictício identificado com a unidade Rio Vermelho."""
    return _montar_dados_lead_teste(
        id_unidade=2,
        nome_unidade="Supera Rio Vermelho",
        identificador="Rio Vermelho",
    )


def montar_dados_lead_teste_santo_andre():
    """Monta um lead fictício para Santo André sem depender do banco."""
    return _montar_dados_lead_teste(
        id_unidade=ID_UNIDADE_TESTE_SEM_CADASTRO,
        nome_unidade="Supera Santo André - Jardim Bela Vista",
        identificador="Santo André",
    )


def _montar_dados_lead_teste(
    *,
    id_unidade,
    nome_unidade,
    identificador,
):
    """Monta a estrutura comum sem consultar banco ou executar requisição."""
    marcador = (
        normalize("NFKD", identificador)
        .encode("ascii", "ignore")
        .decode("ascii")
        .casefold()
        .replace(" ", "-")
    )
    return {
        "id_conversa": int(datetime.now().strftime("%m%d%H%M%S")),
        "id_unidade": id_unidade,
        "nome_unidade": nome_unidade,
        "status_dependente": True,
        "nome_cliente": f"Edcarlos Teste {identificador} - Não contatar",
        "telefone_cliente": "5571994111866",
        "email_cliente": f"edcaspfilho+teste-{marcador}@gmail.com",
        "idade_cliente": None,
        "profissao": "Engenheiro",
        "nome_dependente": f"Enzo Teste {identificador}",
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
