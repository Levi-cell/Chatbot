"""Testes conforme o Apps Script fornecido pela FireAds em 07/10/2026.

Cadastro: POST {action: "append", sheet, rows: [{coluna: valor}]}.
Edição: POST {sheet, row, updates}, restrita a Feedback Comercial e Observação.
Editar Nome e excluir leads não são operações permitidas pelo código recebido.
Importar este módulo não faz chamadas de rede. Nenhum POST é repetido.
"""

import argparse
import json
from urllib.parse import urlparse

import requests

if __package__:
    from .config_teste import (
        ABA_DASHBOARD, TIMEOUT_CONSULTA, TIMEOUT_POST, URL_DASHBOARD,
    )
    from .test_Dash import (
        extrair_registros, gerar_formatos_dashboard, limpar_numero, normalizar_numero_brasileiro,
    )
else:
    from config_teste import (
        ABA_DASHBOARD, TIMEOUT_CONSULTA, TIMEOUT_POST, URL_DASHBOARD,
    )
    from test_Dash import (
        extrair_registros, gerar_formatos_dashboard, limpar_numero, normalizar_numero_brasileiro,
    )


# CONFIGURAÇÃO DO TESTE NA PLANILHA (não utiliza o webhook de test_post.py).
# Segundo teste: número fictício com DDD 00, sem representar um telefone real.
# O primeiro teste usou o número do usuário e foi confirmado na linha 695.
# Identificador/e-mail novos permitem testar outro cadastro sem reenviar o anterior.
TELEFONE_TESTE = "550000000002"
ID_TESTE = "esl-dash-crud-67ae21f904d8"
EMAIL_TESTE = f"{ID_TESTE}@example.com"
NOME_TESTE = "Carlos"
OBSERVACAO_TESTE = f"[{ID_TESTE}] Cadastro de teste na planilha. NAO CONTATAR."
OBSERVACAO_ATUALIZADA = f"{OBSERVACAO_TESTE} 2"
LIMITACOES_OPERACOES = {
    "delete": (
        'O Apps Script recebido nao implementa exclusao de leads. A FireAds precisa '
        'implementar e publicar essa operacao antes de adaptarmos este teste. '
        'Apagar campos ou marcar feedback nao equivale a excluir o cadastro.'
    ),
}


def dados_cadastro_teste():
    """Chaves existentes na planilha; data/hora é preenchida pelo Apps Script."""
    return {
        "Nome": NOME_TESTE,
        "Email": EMAIL_TESTE,
        "WhatsApp": TELEFONE_TESTE,
        "Perfil/Faixa": "Titular (teste ficticio)",
        "Canal": "Organico",
        "Feedback Comercial": "TESTE - NAO CONTATAR",
        "Observação": OBSERVACAO_TESTE,
    }


def montar_payload(operacao, linha=None):
    """Contrato real de doPost/appendRows; não inventa ações para operações ausentes."""
    if operacao in LIMITACOES_OPERACOES:
        raise ValueError(LIMITACOES_OPERACOES[operacao])
    if operacao == "update":
        payload = {
            "sheet": ABA_DASHBOARD,
            "updates": {"Observação": OBSERVACAO_ATUALIZADA},
        }
        # Sem consulta, --payload mostra somente os dados da atualização.
        # Antes do POST, main resolve e exige a linha real devolvida em _row.
        if linha is not None:
            if type(linha) is not int or linha <= 1:
                raise ValueError("O cadastro de teste nao possui um _row inteiro valido maior que 1.")
            payload["row"] = linha
        return payload
    if operacao != "post":
        raise ValueError(f"Operacao desconhecida: {operacao}")
    return {
        "action": "append",
        "sheet": ABA_DASHBOARD,
        "rows": [dados_cadastro_teste()],
    }


def telefone_do_teste(numero):
    """Compara o número fictício; números reais também admitem máscara/nono dígito."""
    digitos = limpar_numero(numero)
    if digitos and digitos == limpar_numero(TELEFONE_TESTE):
        return True
    try:
        normalizado = normalizar_numero_brasileiro(numero)
        return normalizado in gerar_formatos_dashboard(TELEFONE_TESTE)
    except ValueError:
        return False


def consultar_teste():
    """Lê a aba e encontra o telefone, inclusive eventuais cadastros antigos."""
    resposta = requests.get(
        URL_DASHBOARD,
        params={"sheet": ABA_DASHBOARD},
        headers={"Accept": "application/json", "User-Agent": "Mozilla/5.0"},
        timeout=TIMEOUT_CONSULTA,
    )
    print(f"HTTP CONSULTA: {resposta.status_code}", flush=True)
    resposta.raise_for_status()
    dados = resposta.json()
    registros = extrair_registros(dados)
    if dados["data"].get("aba") != ABA_DASHBOARD:
        raise ValueError("O dashboard nao confirmou a aba solicitada.")
    return [r for r in registros if telefone_do_teste(r["WhatsApp"])]


def registros_deste_teste(encontrados):
    """Separa o cadastro novo dos contatos antigos que usam o mesmo telefone.

    E-mail OU identificador detectam inclusive um registro de teste incompleto.
    Para alterar/excluir, registro_do_teste exige a identidade completa.
    """
    return [
        r for r in encontrados
        if telefone_do_teste(r.get("WhatsApp")) and (
            str(r.get("Email", "")).strip().lower() == EMAIL_TESTE
            or ID_TESTE in str(r.get("Observação", ""))
        )
    ]


def registro_do_teste(registro):
    """Não permite atualizar/excluir contatos identificados só pelo telefone."""
    return (
        telefone_do_teste(registro.get("WhatsApp"))
        and str(registro.get("Email", "")).strip().lower() == EMAIL_TESTE
        and registro.get("Nome") == NOME_TESTE
        and ID_TESTE in str(registro.get("Observação", ""))
    )


def validar_alvo(operacao, encontrados):
    alvos = registros_deste_teste(encontrados)
    if operacao == "post":
        if alvos:
            raise ValueError("Este cadastro de teste ja existe. POST cancelado para nao duplica-lo.")
    elif len(alvos) != 1 or not registro_do_teste(alvos[0]):
        raise ValueError(
            "Alteracao cancelada: e necessario um unico registro com telefone, "
            "email, nome e identificador deste teste. Execute test_dash_post.py primeiro."
        )


def imprimir_resposta(resposta):
    print(f"\nURL: {resposta.url}")
    print(f"HTTP: {resposta.status_code} {resposta.reason}")
    for campo in ("Date", "Content-Type", "Server", "Location", "X-Request-ID"):
        if campo in resposta.headers:
            print(f"{campo}: {resposta.headers[campo]}")
    print("CONTEUDO DA RESPOSTA:")
    print(resposta.text[:16000] or "(resposta vazia)")
    if len(resposta.text) > 16000:
        print("(conteudo truncado em 16000 caracteres)")


def enviar_pedido(payload):
    """POST único; devolve a resposta final, inclusive erros no JSON com HTTP 200."""
    if "updates" in payload:
        if type(payload.get("row")) is not int or payload["row"] <= 1:
            raise ValueError("Atualizacao sem a linha real do cadastro de teste. POST nao enviado.")
        if payload["updates"] != {"Observação": OBSERVACAO_ATUALIZADA}:
            raise ValueError("Este teste atualiza somente Observação com o texto configurado.")
    resposta = requests.post(
        URL_DASHBOARD,
        params={"sheet": ABA_DASHBOARD},
        json=payload,
        headers={"Accept": "application/json"},
        timeout=TIMEOUT_POST,
        allow_redirects=False,
    )
    imprimir_resposta(resposta)
    destino = resposta.headers.get("Location", "")
    url_destino = urlparse(destino)
    if (
        resposta.status_code in (302, 303)
        and url_destino.scheme == "https"
        and url_destino.netloc == "script.googleusercontent.com"
    ):
        print("\nLendo a resposta redirecionada do Apps Script (GET, sem repetir o POST).")
        conteudo = requests.get(
            destino, timeout=TIMEOUT_CONSULTA, allow_redirects=False,
        )
        imprimir_resposta(conteudo)
        resposta = conteudo
    print("\nO HTTP, sozinho, nao confirma que a operacao foi executada.")
    return resposta


def motivo_recusa(resposta):
    """Separa falha declarada pelo servidor de resultado ainda não confirmado."""
    try:
        dados = resposta.json()
    except ValueError:
        dados = None
    if isinstance(dados, dict) and (
        dados.get("success") is False or dados.get("error")
    ):
        motivo = dados.get("error") or dados.get("message") or "success=false sem mensagem de erro."
        return motivo if isinstance(motivo, str) else json.dumps(motivo, ensure_ascii=False)
    if resposta.status_code >= 400:
        return f"HTTP {resposta.status_code}: {resposta.reason}"
    return None


def imprimir_recusa(motivo, operacao="post"):
    print(f"\nFALHA INFORMADA PELO APPS SCRIPT: {motivo}")
    texto = motivo.casefold()
    if "linha inv\u00e1lida" in texto or "linha invalida" in texto:
        if operacao == "update":
            print("A edicao usa row obtido em _row na consulta e updates somente com Observação.")
        else:
            print(
                "O pedido usa action=append e rows, conforme o codigo fornecido. "
                "Nesse codigo, o cadastro nao exige row; row e usado na edicao."
            )
        print(
            "Se Linha invalida persistir, confira se a URL /exec esta servindo "
            "a mesma versao do codigo do editor. Nenhum numero de linha sera inventado."
        )


def resultado_visivel(operacao, encontrados):
    alvos = registros_deste_teste(encontrados)
    if operacao not in ("post", "update"):
        return False
    if len(alvos) != 1 or not registro_do_teste(alvos[0]):
        return False
    if operacao == "update":
        return alvos[0].get("Observação") == OBSERVACAO_ATUALIZADA
    esperado = dados_cadastro_teste()
    return all(
        telefone_do_teste(alvos[0].get(k)) if k == "WhatsApp"
        else str(alvos[0].get(k, "")) == str(v)
        for k, v in esperado.items()
    )


def main(operacao, argv=None):
    parser = argparse.ArgumentParser(description=f"Teste de {operacao} no Apps Script do dashboard.")
    parser.add_argument("--payload", action="store_true", help="Exibe o pedido sem acessar a rede.")
    args = parser.parse_args(argv)
    print(f"URL_DASHBOARD: {URL_DASHBOARD}")
    try:
        payload = montar_payload(operacao)
    except ValueError as erro:
        print(f"OPERACAO INDISPONIVEL NO CODIGO DO APPS SCRIPT: {erro}")
        print("Nenhuma requisicao foi enviada.")
        return 5
    if operacao == "update":
        print("CONTRATO: sheet, row e updates. Somente o campo Observação sera enviado para edicao.")
        print("O campo row sera preenchido com _row depois de localizar o cadastro de teste.")
    else:
        print("CONTRATO: action=append, sheet e rows, conforme doPost/appendRows fornecidos pela FireAds.")
    print(f"Telefone: {TELEFONE_TESTE} | Cadastro: {NOME_TESTE}")
    print(json.dumps(payload, indent=2, ensure_ascii=False), flush=True)
    if args.payload:
        return 0

    try:
        print("\nConferindo o contato ANTES da operacao...", flush=True)
        encontrados = consultar_teste()
        validar_alvo(operacao, encontrados)
        if operacao == "update":
            alvo = registros_deste_teste(encontrados)[0]
            linha = alvo.get("_row")
            if linha is None:
                raise ValueError("A consulta nao retornou _row para o cadastro de teste.")
            payload = montar_payload(operacao, linha=linha)
    except (requests.RequestException, ValueError) as erro:
        print(f"NAO ENVIADO: {type(erro).__name__}: {erro}")
        return 1

    if operacao == "update":
        if resultado_visivel(operacao, encontrados):
            print("A observacao ja esta exatamente como solicitado. Nenhum POST foi enviado.")
            return 0
        print("\nPEDIDO DE ATUALIZACAO DO REGISTRO LOCALIZADO:")
        print(json.dumps(payload, indent=2, ensure_ascii=False), flush=True)

    print("\nEnviando uma unica tentativa...", flush=True)
    recusa = None
    try:
        resposta = enviar_pedido(payload)
        recusa = motivo_recusa(resposta)
        if recusa:
            imprimir_recusa(recusa, operacao)
    except requests.RequestException as erro:
        print(f"FALHA NA REQUISICAO: {type(erro).__name__}: {erro}")
        print("O pedido pode ter sido processado. Nao havera reenvio automatico.")

    try:
        print("\nConferindo o contato DEPOIS da tentativa...", flush=True)
        encontrados = consultar_teste()
    except (requests.RequestException, ValueError) as erro:
        print(f"VERIFICACAO INCONCLUSIVA: {type(erro).__name__}: {erro}")
        if recusa:
            print(f"A falha informada pelo script permanece registrada nesta execucao: {recusa}")
        return 2

    alvos = registros_deste_teste(encontrados)
    print(f"Registros com o telefone de teste: {len(encontrados)}")
    print(f"Registros identificados como este teste: {len(alvos)}")
    for registro in alvos:
        print(json.dumps(registro, indent=2, ensure_ascii=False))
    if recusa:
        print(f"RESULTADO: o Apps Script informou falha: {recusa}")
        if resultado_visivel(operacao, encontrados):
            print(
                "ATENCAO: a consulta mostra o resultado esperado apesar da falha informada. "
                "Ha divergencia entre a resposta e os dados; nao reenviar automaticamente."
            )
            return 2
        print("A consulta posterior tambem nao confirmou o resultado esperado. Nao houve reenvio.")
        return 4
    if resultado_visivel(operacao, encontrados):
        print(f"RESULTADO ESPERADO VISIVEL NA CONSULTA: {operacao}.")
        return 0
    print("RESULTADO NAO CONFIRMADO na consulta atual. Pode haver atraso ou contrato nao aceito.")
    print("Nao repetir o cadastro automaticamente. Nenhuma outra operacao foi tentada.")
    return 3
