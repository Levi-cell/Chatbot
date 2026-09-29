"""Altera somente o fuso do portfólio Meta e confirma o valor por leitura.

Credenciais e versão da Graph API vêm da configuração local do projeto.
Importar ou executar este arquivo com o exemplo comentado não altera contas.
"""

import json
import re
import sys
from pathlib import Path

import requests


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def _validar_identificador(valor, nome):
    identificador = str(valor).strip()
    if not re.fullmatch(r"[0-9]+", identificador) or int(identificador) <= 0:
        raise ValueError(f"{nome} deve ser um identificador inteiro positivo")
    return str(int(identificador))


def _requisitar_meta(session, metodo, id_portfolio, **parametros):
    # Import tardio: o ambiente precisa estar carregado antes desta configuração.
    from core.integrations.whatsapp.tools.config import (
        construir_url_graph_api,
        get_meta_http_timeout,
        get_token_usuario_meta,
    )

    enviar = session.get if metodo == "GET" else session.post
    try:
        resposta = enviar(
            construir_url_graph_api(id_portfolio),
            headers={"Authorization": f"Bearer {get_token_usuario_meta()}"},
            timeout=get_meta_http_timeout(),
            allow_redirects=False,
            **parametros,
        )
    except requests.RequestException:
        # Um timeout do POST não comprova que a Meta deixou de aplicar a mudança.
        raise RuntimeError(
            f"Falha de conexão no {metodo}. Resultado não confirmado; "
            "consulte o fuso antes de repetir a alteração."
        ) from None

    try:
        dados = resposta.json()
    except ValueError:
        raise RuntimeError(f"Resposta inválida da Meta no {metodo}") from None
    if not isinstance(dados, dict):
        raise RuntimeError(f"Resposta inesperada da Meta no {metodo}")
    if not 200 <= resposta.status_code < 300 or "error" in dados:
        erro = dados.get("error")
        codigo = erro.get("code") if isinstance(erro, dict) else None
        detalhe = f", código Meta {codigo}" if type(codigo) is int else ""
        # Código documentado em /docs/marketing-api/reference/business/.
        # Permissão para consultar uma WABA não concede edição do portfólio.
        orientacao = ""
        if codigo == 3910:
            orientacao = (
                ": sem permissão para editar os dados deste portfólio. "
                "Solicite ao administrador do portfólio que realize a alteração "
                "ou revise o acesso da identidade vinculada ao token. "
                "Acesso à WABA não equivale a acesso administrativo ao portfólio."
            )
        # Não expor tokens, URLs autenticadas ou texto arbitrário da resposta.
        raise RuntimeError(
            f"Meta recusou o {metodo} (HTTP {resposta.status_code}{detalhe})"
            f"{orientacao}"
        )
    return dados


def _consultar_fuso(session, id_portfolio):
    dados = _requisitar_meta(
        session, "GET", id_portfolio, params={"fields": "id,timezone_id"},
    )
    fuso = str(dados.get("timezone_id", ""))
    if str(dados.get("id")) != id_portfolio or not re.fullmatch(r"[0-9]+", fuso):
        raise RuntimeError("A Meta não retornou o fuso do portfólio solicitado")
    # Na leitura, zero é válido como resposta: significa TZ_UNKNOWN, não UTC+0.
    return int(fuso)


def alterar_fuso_portfolio(
    id_portfolio, id_timezone, *, env_file=None, session=requests,
):
    """Configura o fuso, imprime a confirmação e retorna os IDs antes/depois.

    id_portfolio: ID do portfólio empresarial, não da WABA ou do telefone.
    id_timezone: identificador Meta, não deslocamento UTC nem nome IANA.
        206 = America/Bahia; 25 = America/Sao_Paulo (ambos UTC−03 atualmente).
        270 = America/Porto_Velho (UTC−04 atualmente).

    Requer um token autorizado a administrar o portfólio. Consulta antes de
    alterar, não envia POST se o valor já for o desejado e confirma com novo
    GET. Se a confirmação falhar após o POST, a alteração pode ter ocorrido.
    Não faz tentativas automáticas nem atualiza WABAs ou contas de anúncios.

    Referência: facebook-python-business-sdk, Business.api_update,
    parâmetro timezone_id (POST no ID do portfólio).
    """
    id_portfolio = _validar_identificador(id_portfolio, "id_portfolio")
    id_timezone = int(_validar_identificador(id_timezone, "id_timezone"))

    from utilitarios.bootstrap import configurar_ambiente_utilitario

    configurar_ambiente_utilitario(env_file)
    anterior = _consultar_fuso(session, id_portfolio)
    alterado = anterior != id_timezone
    atual = anterior
    if alterado:
        resposta = _requisitar_meta(
            session, "POST", id_portfolio, data={"timezone_id": id_timezone},
        )
        if resposta.get("success") is not True:
            raise RuntimeError(
                "O POST não confirmou a alteração. Consulte o fuso antes de repetir."
            )
        try:
            atual = _consultar_fuso(session, id_portfolio)
        except RuntimeError as erro:
            raise RuntimeError(
                "A Meta aceitou a alteração, mas a consulta de confirmação falhou. "
                "A mudança pode já estar aplicada; consulte o fuso novamente."
            ) from erro
        if atual != id_timezone:
            raise RuntimeError(
                f"A Meta aceitou o POST, mas retornou timezone_id={atual}; "
                f"esperado {id_timezone}. Alteração ainda não confirmada."
            )

    resultado = {
        "id_portfolio": id_portfolio,
        "timezone_id_anterior": anterior,
        "timezone_id_atual": atual,
        "alterado": alterado,
        "confirmado": True,
    }
    print(json.dumps(
        {**resultado, "id_portfolio": "..." + id_portfolio[-4:]}, indent=2,
    ))
    return resultado


if __name__ == "__main__":
    alterar_fuso_portfolio(891138433896919, 206)
    pass
