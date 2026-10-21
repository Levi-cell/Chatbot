"""Planilha: tenta cadastrar Carlos com o telefone fictício 550000000002.

Run no PyCharm, sem parâmetros. Não usa o webhook do arquivo test_post.py.
Envia action=append, sheet e rows conforme o código doPost/appendRows da FireAds.
--payload exibe o pedido sem consultar ou alterar o dashboard.
Erros no JSON (ex.: success=false, Linha inválida) são destacados mesmo com HTTP 200.
"""

if __package__:
    from .dash_crud_teste import main
else:
    from dash_crud_teste import main


if __name__ == "__main__":
    raise SystemExit(main("post"))
