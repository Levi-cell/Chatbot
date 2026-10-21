"""Planilha: altera somente a Observação do cadastro de teste de Carlos.

Run no PyCharm, sem parâmetros. Localiza o registro por telefone fictício,
e-mail e identificação do teste; usa _row para enviar updates apenas com
Observação terminada em "NAO CONTATAR. 2". Nome e demais campos não são enviados
para edição. Usa somente URL_DASHBOARD; --payload exibe uma prévia sem rede.
"""

if __package__:
    from .dash_crud_teste import main
else:
    from dash_crud_teste import main


if __name__ == "__main__":
    raise SystemExit(main("update"))
