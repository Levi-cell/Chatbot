"""Monta o payload de oportunidade sem conhecer banco ou transações."""

import re
from core.integrations.fireads.contrato import CANAIS, bloco_observacoes
from core.validacoes.email import ResultadoColetaEmail

from core.validacoes.turno import ROTULOS_TURNO, validar_turno

from core.triagem.perguntas import (
    montar_pergunta_triagem,
    obter_faixa_etaria_triagem,
)
from core.validacoes.email import (
    CLASSIFICACAO_EMAIL_AUSENTE,
    CLASSIFICACAO_EMAIL_NAO_INFORMADO,
    CLASSIFICACAO_EMAIL_VALIDO,
    classificar_resposta_email_aceita,
)


ORIGEM_LEAD_CHATBOT = "Meta Chatbot"
TITULO_OPORTUNIDADE = "Chatbot Lead"

ETAPAS_TRIAGEM_ESPERADAS = tuple(range(12, 18))
RESPOSTAS_TRIAGEM_EXIBICAO = {
    "nunca": "Nunca",
    "às vezes": "Às vezes",
    "as vezes": "Às vezes",
    "frequentemente": "Frequentemente",
}

MARCADORES_API_CARROSSEL = {
    "codigo_vendedor": "Code_User",
    "codigo_metodologia": "Code_Methodology",
    "codigo_canal_venda": "Code_Channel",
    "codigo_etapa": "Code_StepMethodology",
}

PADRAO_TELEFONE_BRASIL = re.compile(
    r"^55(?P<ddd>[1-9]\d)(?P<numero>\d{8,9})$"
)
AVISO_TELEFONE_INTERNACIONAL = (
    "O cliente possui um número internacional fora do padrão brasileiro, "
    "por isso o campo Telefone 1 não foi preenchido."
)


def montar_payload_oportunidade(dados_lead):
    """Converte o snapshot validado do atendimento no contrato ApiCarrossel."""
    _validar_dados_lead(dados_lead)

    nome_cliente = dados_lead["nome_cliente"].strip()
    nome_unidade = dados_lead["nome_unidade"].strip()
    titulo = f"{TITULO_OPORTUNIDADE} {nome_unidade}"
    nome_destaque = _montar_nome_destaque(dados_lead)
    telefone_funil = _normalizar_telefone_brasileiro(
        dados_lead["telefone_cliente"]
    )
    resultado_email = _resolver_resultado_email_conversa(dados_lead)
    observacoes = montar_observacoes_lead(
        dados_lead,
        resultado_email=resultado_email,
    )

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
                        "valor": CANAIS[dados_lead["origem_fireads"]][0] if dados_lead.get("origem_fireads") else ORIGEM_LEAD_CHATBOT,
                    },
                ],
                "empresa": {
                    # O CRM usa empresa.nome como destaque principal do card.
                    "nome": nome_destaque,
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
                    # Ausência é representada pelo valor vazio já usado no
                    # contrato do projeto; placeholders nunca ocupam o campo.
                    "email": resultado_email.email or "",
                    "telefone1": telefone_funil,
                    "telefone2": "",
                    "cargo": "",
                    "cpf": "",
                    "personalizados": [],
                },
            }
        ]
    }


def montar_observacoes_lead(dados_lead, *, resultado_email=None):
    """Produz o resumo humano exibido pela oportunidade no CRM."""
    nome_cliente = dados_lead["nome_cliente"].strip()
    telefone_cliente = dados_lead["telefone_cliente"].strip()
    profissao = str(dados_lead.get("profissao") or "").strip()
    profissao = profissao or "Não informada"
    aviso_telefone = ""
    resultado_email = resultado_email or _resolver_resultado_email_conversa(
        dados_lead
    )
    email_exibicao = _montar_email_exibicao(resultado_email)

    if not _normalizar_telefone_brasileiro(telefone_cliente):
        aviso_telefone = f"\n{AVISO_TELEFONE_INTERNACIONAL}\n"

    tem_link = bool(str(dados_lead.get("link_agendamento") or "").strip())
    orientacao = (
        "Confira sua plataforma de reserva (como o Calendly) e o painel de monitoramento."
        if tem_link else
        "Confira o painel de monitoramento e o número comercial para verificar se o cliente enviou mensagem."
    )
    turno = dados_lead.get("turno")
    if turno is not None:
        validar_turno(turno)
    preferencia = f"- Turno de preferência: {ROTULOS_TURNO[turno]}\n" if turno else ""
    origem = dados_lead.get("origem_fireads")
    descricoes = {
        "google": "Lead veio de uma campanha do Google Ads.",
        "meta": "Lead veio de uma campanha da Meta Ads.",
        "organico_site": "O Lead chegou ao site de maneira orgânica e preencheu o formulário.",
        "organico": "Lead entrou em contato com o chatbot de maneira orgânica, possivelmente por alguma rede social Meta da unidade.",
    }
    descricao = descricoes.get(origem, "")
    estado = dados_lead.get("contexto_fireads") or {}
    if origem == "organico" and estado.get("motivo") not in (None, "telefone_ausente"):
        descricao = "Atendimento iniciado pelo fluxo orgânico, sem importar os dados do formulário."
    canal = f"Canal de venda: {CANAIS[origem][0]}\n{descricao}\n\n" if origem else ""
    primeiro = dados_lead.get("primeiro_atendimento")
    classificacao = (
        "Novo lead" if primeiro is True else
        "Novo atendimento para Lead antigo" if primeiro is False else "Atendimento"
    )
    cabecalho = (
        f"{classificacao}\n\n"
        f"{canal}"
        "Cliente concluiu a triagem cognitiva pelo chatbot. "
        f"{orientacao} A disponibilidade e a efetivação de sua reserva devem ser conferidas pela equipe.\n\n"
        f"{preferencia}"
        f"- Nome do cliente: {nome_cliente}\n"
        f"- Telefone/WhatsApp do cliente: "
        f"{telefone_cliente}\n"
        f"- E-mail do cliente: {email_exibicao}\n"
    )

    if dados_lead["status_dependente"]:
        dados_pessoa = (
            f"\nO atendimento é para um dependente de {nome_cliente}:\n\n"
            f"- Nome do dependente: "
            f"{dados_lead['nome_dependente'].strip()}\n"
            f"- Idade do dependente: {dados_lead['idade_dependente']}\n"
        )
    else:
        dados_pessoa = f"- Idade do cliente: {dados_lead['idade_cliente']}\n"

    triagem = _montar_perguntas_e_respostas_triagem(dados_lead)

    dados_profissao = f"\n- Profissão: {profissao}\n"

    resumo = (
        cabecalho
        + dados_profissao
        + dados_pessoa
        + aviso_telefone
        + triagem
    )
    if origem:
        return bloco_observacoes(estado['id_integracao'], dados_lead['id_conversa'], resumo, versao=2)
    return f"Observações de atendimento\n\n{resumo}"


def _montar_perguntas_e_respostas_triagem(dados_lead):
    respostas = _obter_respostas_triagem_validadas(dados_lead)

    if dados_lead["status_dependente"]:
        idade_pessoa = dados_lead["idade_dependente"]
        nome_dependente = dados_lead["nome_dependente"].strip()
    else:
        idade_pessoa = dados_lead["idade_cliente"]
        nome_dependente = None

    faixa_etaria = obter_faixa_etaria_triagem(idade_pessoa)
    blocos = []

    for numero, item in enumerate(respostas, start=1):
        pergunta = montar_pergunta_triagem(
            item["id_etapa"],
            faixa_etaria=faixa_etaria,
            nome_dependente=nome_dependente,
        )
        blocos.append(
            f"-Pergunta {numero}:\n\n"
            f"{pergunta}\n\n"
            f"Resposta: {item['resposta_exibicao']}"
        )

    return "\nPerguntas e respostas da triagem:\n\n" + "\n\n".join(blocos)


def _montar_nome_destaque(dados_lead):
    """Monta a linha principal do card conforme a pessoa atendida."""
    nome_cliente = dados_lead["nome_cliente"].strip()

    if dados_lead["status_dependente"]:
        return " | ".join(
            (
                nome_cliente,
                dados_lead["nome_dependente"].strip(),
                str(dados_lead["idade_dependente"]),
            )
        )

    return " | ".join((nome_cliente, str(dados_lead["idade_cliente"])))


def _normalizar_telefone_brasileiro(telefone):
    """Prepara o wa_id brasileiro para o campo Telefone 1 do CRM."""
    somente_digitos = re.sub(r"\D", "", str(telefone or ""))
    correspondencia = PADRAO_TELEFONE_BRASIL.fullmatch(somente_digitos)

    if correspondencia is None:
        return ""

    numero = correspondencia.group("numero")

    if len(numero) == 8:
        numero = f"9{numero}"
    elif not numero.startswith("9"):
        return ""

    return f"55{correspondencia.group('ddd')}{numero}"


def _validar_dados_lead(dados_lead):
    obrigatorios = (
        "id_conversa",
        "id_unidade",
        "nome_unidade",
        "nome_cliente",
        "telefone_cliente",
    )
    ausentes = [campo for campo in obrigatorios if not dados_lead.get(campo)]

    if ausentes:
        raise ValueError(
            "Dados obrigatórios ausentes para criar a oportunidade: "
            + ", ".join(ausentes)
        )

    _obter_respostas_triagem_validadas(dados_lead)

    if dados_lead.get("status_dependente"):
        if not dados_lead.get("nome_dependente"):
            raise ValueError("Nome do dependente ausente")
        if dados_lead.get("idade_dependente") is None:
            raise ValueError("Idade do dependente ausente")
    elif dados_lead.get("idade_cliente") is None:
        raise ValueError("Idade do cliente ausente")


def _resolver_resultado_email_conversa(dados_lead):
    if dados_lead.get('contexto_coleta') or dados_lead.get('origem_fireads'):
        classificacao = dados_lead.get('resultado_email_coleta') or dados_lead.get('resultado_email_fireads')
        if classificacao not in {CLASSIFICACAO_EMAIL_VALIDO, CLASSIFICACAO_EMAIL_AUSENTE, CLASSIFICACAO_EMAIL_NAO_INFORMADO}:
            raise ValueError('Resultado histórico de email inválido')
        return ResultadoColetaEmail(aceita=True, classificacao=classificacao, email=dados_lead.get('email_cliente'))

    resposta_historica = dados_lead.get("resposta_email_conversa")

    if resposta_historica is not None:
        return classificar_resposta_email_aceita(resposta_historica)

    # Compatibilidade com atendimentos legados que não possuem o vínculo
    # histórico da resposta de e-mail. Dados novos sempre usam a conversa.
    email_cadastro = dados_lead.get("email_cliente")
    if email_cadastro:
        return classificar_resposta_email_aceita(email_cadastro)

    return classificar_resposta_email_aceita("")


def _montar_email_exibicao(resultado_email):
    if resultado_email.classificacao == CLASSIFICACAO_EMAIL_VALIDO:
        return resultado_email.email

    if resultado_email.classificacao == CLASSIFICACAO_EMAIL_AUSENTE:
        return "não tem"

    if resultado_email.classificacao == CLASSIFICACAO_EMAIL_NAO_INFORMADO:
        return "não informado"

    raise ValueError(
        "Classificação de e-mail inválida para observações do Funil "
        f"(classificacao={resultado_email.classificacao!r})"
    )


def _obter_respostas_triagem_validadas(dados_lead):
    respostas = dados_lead.get("triagem_respostas")

    if not isinstance(respostas, (list, tuple)):
        raise ValueError("Respostas da triagem ausentes ou inválidas")

    ids_etapas = []
    respostas_validadas = []

    for item in respostas:
        if not isinstance(item, dict):
            raise ValueError("Item de resposta da triagem inválido")

        id_etapa = item.get("id_etapa")
        resposta = item.get("resposta")
        resposta_normalizada = str(resposta or "").strip().casefold()

        ids_etapas.append(id_etapa)

        if resposta_normalizada not in RESPOSTAS_TRIAGEM_EXIBICAO:
            raise ValueError(
                "A triagem contém resposta fora do domínio esperado "
                f"(etapa={id_etapa}, resposta={resposta})"
            )

        respostas_validadas.append(
            {
                "id_etapa": id_etapa,
                "resposta": resposta_normalizada,
                "resposta_exibicao": RESPOSTAS_TRIAGEM_EXIBICAO[
                    resposta_normalizada
                ],
            }
        )

    if tuple(ids_etapas) != ETAPAS_TRIAGEM_ESPERADAS:
        raise ValueError(
            "A oportunidade exige respostas ordenadas para as etapas "
            "12, 13, 14, 15, 16 e 17"
        )

    return respostas_validadas
