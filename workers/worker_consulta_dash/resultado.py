"""Interpretação da consulta inicial; não executa HTTP nem operações de banco."""

from core.integrations.fireads.contrato import selecionar, destino
from core.integrations.fireads.extratores import extrair_email, extrair_nome


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
    nome = extrair_nome(nome)
    email = extrair_email(email)
    dependente = destino(alvo)
    if not nome or not email or not str(alvo or "").strip():
        return decisao_organica("incompleto", "campos_ausentes")
    if dependente is None:
        # Uma opção fora do contrato não autoriza inventar titular/dependente.
        return decisao_organica("incompleto", "destinatario_desconhecido")
    return {
        "resultado": "importado",
        "origem": origem,
        "status_dependente": dependente,
        "id_registro_origem": str(row.get("id") or ""),
        "data_formulario": data.isoformat() if data else None,
        "dados_titular": {
            "nome": nome,
            "email": email,
            # Marcador histórico da coleta; na FireAds a fonte é o formulário.
            "resultado_email": "email_valido",
        },
    }
