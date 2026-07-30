# Funil de Vendas

Adaptador da ApiCarrossel usado para criar uma oportunidade por conversa
elegível. Esta camada recebe dados prontos e não conhece PostgreSQL, retries ou
o ciclo do worker.

## Arquivos

```text
core/integrations/funil/
├── cliente.py             POST, URL e validação da resposta lógica
├── oportunidades.py       payload e texto de observações
└── exceptions.py          falhas conhecidas da integração
```

`cliente.py` exige simultaneamente:

```text
HTTP sem erro
e
JSON response = success
```

A API pode devolver HTTP 200 com `response = failure`; esse caso não confirma
`lead_no_funil`.

## Teste manual

O teste completo usa dados fictícios e só envia com confirmação explícita:

```bash
python -m operations.integrations.funil_probe payload
python -m operations.integrations.funil_probe send-test --confirm-real-send
```

Ele cria uma oportunidade claramente marcada como teste. Antes de ativar o
worker, confira no CRM pessoa, telefone, e-mail, título, observações e origem.
Os dois últimos são enviados pelo mecanismo `personalizados` com os títulos
exatos `Observações` e `Origem do lead`; a unidade precisa possuir campos
compatíveis no ApiCarrossel.

O teste nunca consulta dados reais do chatbot, não é chamado pelo worker e
jamais envia apenas por importar o módulo.
