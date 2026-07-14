"""Monta o payload de oportunidade sem conhecer banco ou transações."""

from datetime import datetime


ORIGEM_LEAD_CHATBOT = "Meta Chatbot"
TITULO_OPORTUNIDADE = "Chatbot Lead"

MARCADORES_API_CARROSSEL = {
    "codigo_vendedor": "Code_User",
    "codigo_metodologia": "Code_Methodology",
    "codigo_canal_venda": "Code_Channel",
    "codigo_etapa": "Code_StepMethodology",
}


def montar_payload_oportunidade(dados_lead):
    """Converte o snapshot validado do atendimento no contrato ApiCarrossel."""
    _validar_dados_lead(dados_lead)

    nome_cliente = dados_lead["nome_cliente"].strip()
    id_conversa = dados_lead["id_conversa"]
    titulo = f"{TITULO_OPORTUNIDADE} [C{id_conversa}]"
    observacoes = montar_observacoes_lead(dados_lead)

    return {
        "oportunidades": [
            {
                "titulo": titulo,
                "valor": "0",
                **MARCADORES_API_CARROSSEL,
                "personalizados": [
                    {
                        "titulo": "Observações",
                        "valor": observacoes,
                    },
                    {
                        "titulo": "Origem do lead",
                        "valor": ORIGEM_LEAD_CHATBOT,
                    },
                ],
                "empresa": {
                    "nome": dados_lead["nome_unidade"].strip(),
                    "cnpj": "",
                    "codigo_segmento": "0",
                    "endereco_completo": {
                        "logradouro": "",
                        "numero": "",
                        "complemento": "",
                        "bairro": "",
                        "cidade": "",
                        "uf": "",
                        "cep": "",
                    },
                    "personalizados": [],
                },
                "contato": {
                    "nome": nome_cliente,
                    "email": dados_lead["email_cliente"].strip(),
                    "telefone1": dados_lead["telefone_cliente"].strip(),
                    "telefone2": "",
                    "cargo": "",
                    "cpf": "",
                    "personalizados": [],
                },
            }
        ]
    }


def montar_observacoes_lead(dados_lead):
    """Produz o resumo humano exibido pela oportunidade no CRM."""
    nome_cliente = dados_lead["nome_cliente"].strip()
    cabecalho = (
        "------NOVO LEAD-------\n\n"
        "Cliente concluiu a triagem cognitiva pelo chatbot e chegou à "
        "etapa de agendamento. Fique atento ao Calendly. Seguem as "
        "informações para contato:\n\n"
        f"- Nome do cliente: {nome_cliente}\n"
        f"- Telefone/WhatsApp do cliente: "
        f"{dados_lead['telefone_cliente'].strip()}\n"
        f"- E-mail do cliente: {dados_lead['email_cliente'].strip()}\n"
    )

    if dados_lead["status_dependente"]:
        pessoa_avaliada = dados_lead["nome_dependente"].strip()
        dados_pessoa = (
            f"\nO atendimento é para um dependente de {nome_cliente}:\n\n"
            f"- Nome do dependente: {pessoa_avaliada}\n"
            f"- Idade do dependente: {dados_lead['idade_dependente']}\n"
        )
    else:
        pessoa_avaliada = nome_cliente
        dados_pessoa = f"- Idade do cliente: {dados_lead['idade_cliente']}\n"

    triagem = (
        f"\nResultado do teste de triagem de {pessoa_avaliada} "
        "(6 perguntas):\n"
        f"- Nunca: {dados_lead['triagem_nunca']}\n"
        f"- Às vezes: {dados_lead['triagem_as_vezes']}\n"
        f"- Frequentemente: {dados_lead['triagem_frequentemente']}"
    )

    return cabecalho + dados_pessoa + triagem


def montar_dados_lead_teste():
    """Snapshot fixo e inofensivo para a validação manual do endpoint."""
    return {
        "id_conversa": int(datetime.now().strftime("%m%d%H%M%S")),
        "id_unidade": 1,
        "nome_unidade": "Supera Santo Antônio de Jesus",
        "status_dependente": True,
        "nome_cliente": "Edcarlos Teste - Não contatar",
        "telefone_cliente": "71994111866",
        "email_cliente": "edcaspfilho+teste@gmail.com",
        "idade_cliente": None,
        "nome_dependente": "Enzo Teste",
        "idade_dependente": 12,
        "triagem_total": 6,
        "triagem_nunca": 2,
        "triagem_as_vezes": 3,
        "triagem_frequentemente": 1,
        "triagem_desconhecida": 0,
    }


def _validar_dados_lead(dados_lead):
    obrigatorios = (
        "id_conversa",
        "id_unidade",
        "nome_unidade",
        "nome_cliente",
        "telefone_cliente",
        "email_cliente",
    )
    ausentes = [campo for campo in obrigatorios if not dados_lead.get(campo)]

    if ausentes:
        raise ValueError(
            "Dados obrigatórios ausentes para criar a oportunidade: "
            + ", ".join(ausentes)
        )

    if dados_lead.get("triagem_total") != 6:
        raise ValueError("A oportunidade exige exatamente 6 respostas da triagem")

    if dados_lead.get("triagem_desconhecida", 0) != 0:
        raise ValueError("A triagem contém respostas fora do domínio esperado")

    total_contado = sum(
        dados_lead.get(campo, 0)
        for campo in (
            "triagem_nunca",
            "triagem_as_vezes",
            "triagem_frequentemente",
        )
    )
    if total_contado != 6:
        raise ValueError("A soma das respostas da triagem deve ser igual a 6")

    if dados_lead.get("status_dependente"):
        if not dados_lead.get("nome_dependente"):
            raise ValueError("Nome do dependente ausente")
        if dados_lead.get("idade_dependente") is None:
            raise ValueError("Idade do dependente ausente")
    elif dados_lead.get("idade_cliente") is None:
        raise ValueError("Idade do cliente ausente")

