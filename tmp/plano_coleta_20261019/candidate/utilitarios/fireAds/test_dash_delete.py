"""Teste de exclusão de lead, indisponível no Apps Script recebido.

O código fornecido não tem uma operação de exclusão de leads. Ao executar,
informa essa limitação e sai sem requisições. O test_post.py do webhook não é usado.
"""

if __package__:
    from .dash_crud_teste import main
else:
    from dash_crud_teste import main


if __name__ == "__main__":
    raise SystemExit(main("delete"))
