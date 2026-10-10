"""Interpretação da consulta inicial; não executa HTTP nem operações de banco."""

from core.integrations.fireads.contrato import selecionar, destino
from core.validacoes.email import validar_email_estrutural
from workers.worker_flow.response_flow.etapas.validadores_universais.validador_nome import validar_nome_cliente

def decisao_organica(resultado, motivo=None):
    return {
        "resultado": resultado,
        "origem": "organico",
        "motivo": motivo,
        "dados_titular": {},
    }


def interpretar(google, meta, numero, fuso):
    escolhido = selecionar(google, meta, numero, fuso)
    if escolhido is None:
        return decisao_organica("ausente")
    origem, row, data = escolhido
    nome = row.get("Nome") if origem == "google" else row.get("full_name")
    email = row.get("Email") if origem == "google" else row.get("email")
    alvo = row.get("Perfil/Faixa") if origem == "google" else row.get("para_quem")
    nome = validar_nome_cliente(nome)
    email = validar_email_estrutural(email)
    dependente = destino(alvo)
    if not nome.valido or not email.valido or dependente is None:
        return decisao_organica("incompleto", "coleta_invalida")
    return {
        "resultado": "importado",
        "origem": origem,
        "status_dependente": dependente,
        "id_registro_origem": str(row.get("id") or ""),
        "data_formulario": data.isoformat() if data else None,
        "dados_titular": {
            "nome": nome.primeiro_nome,
            "email": email.email,
            "resultado_email": "email_valido",
        },
    }
