# Testes

Todos os testes, mocks, fakes e payloads exclusivos de teste ficam nesta pasta.
Código de produção não deve importar `tests`.

- [Portal do projeto](../README.md)
- [Padrões de arquitetura](../PADROES_DE_ARQUITETURA.md#testes)

## Estrutura

```text
tests/
├── __init__.py       preparação de paths e Django
├── helpers.py        conexões, cursores e requests falsos
├── payloads.py       payloads Meta fictícios
└── unit/
    └── test_*.py
```

## Execução

Suíte completa:

```powershell
python -m unittest discover -s tests -p "test_*.py"
```

Arquivo específico:

```powershell
python -m unittest tests.unit.test_webhook_post_flow
```

Validação de sintaxe e imports:

```powershell
python -m compileall core workers callback tests
python callback/manage.py check
```

Execute com o ambiente virtual que contém as dependências de
[`requirements.txt`](../requirements.txt). Testes unitários não devem depender de
Meta, Redis ou AWS reais.

## Estratégia

Os testes cobrem comportamento e contratos arquiteturais:

- fluxo A/B/C e primeira mensagem do turno;
- idempotência por histórico específico do bot;
- `last_message_from` semântico;
- ordenação, locks e retry;
- falha do banco depois do envio Meta;
- status HTTP e transação do webhook;
- fallback de cache e operações Meta-first;
- estrutura de `messages`, `pywa_functions` e `tools`.

## Convenções

- `unittest` é o runner atual;
- `patch` e classes `Fake*` ficam somente em `tests`;
- valores de telefone, IDs e tokens são fictícios;
- sucesso, falha e retry devem ser cobertos em fluxos críticos;
- testes de contrato podem usar `inspect` quando a fronteira arquitetural é parte
  da garantia;
- alterações de regra exigem atualizar teste e `REGRAS_DE_NEGOCIO.md`.

## Ao adicionar um teste

1. Escolha o módulo em `tests/unit` correspondente ao comportamento.
2. Reutilize `helpers.py` e `payloads.py` antes de criar outro fake.
3. Simule falhas externas; não faça chamadas reais.
4. Confirme efeitos persistidos, status, commits e rollbacks relevantes.
5. Rode o arquivo específico e depois a descoberta completa.
