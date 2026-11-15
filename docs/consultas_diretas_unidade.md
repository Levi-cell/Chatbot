# Consultas diretas da unidade e personalização

## Leitura dos dados

As consultas do atendimento (etapas 1, 6, 7, 9, 10, 18 e 20), follow-up,
Funil, painel e relatórios semanal/total unem diretamente `chatbot.unidade`
e `chatbot.atendimento_customizado` por `id_unidade`. A relação obrigatória
de uma personalização por unidade permanece igual.

Cadastro e `status_pagamento` são lidos de `unidade`; agente, gênero, BPA,
comercial, regras de idade/e-mail e links são lidos de `atendimento_customizado`.
Campos retornados, ordem das colunas, validações, isolamento por unidade,
elegibilidade, reservas e regras de negócio foram preservados.

SQL utilizado pelos serviços de produção fica em `core/repositories`.
SQL de utilitários permanece em `utilitarios`, inclusive nos relatórios.
DDL de instalação/migração e preparações dos testes continuam em seus locais
próprios. Não criar novas views sem autorização expressa do usuário.

## Tabela migracoes_fireads

É o registro técnico da migração estrutural, não uma tabela de leads:

- `versao`: chave única da migração; nesta entrega, `20261007_fireads_v1`.
- `aplicada_em`: data/hora do registro da aplicação.

A marca é gravada após as conferências dentro da transação da migração.
Se a transação falhar, o registro também é desfeito. Numa reexecução, a
presença da versão impede repetir a cópia das personalizações, a criação
dos chats e o movimento das colunas. As funções e triggers idempotentes
fora desse bloco ainda podem ser atualizados pelo script.

Ela não é consultada para decidir o atendimento, não envia dados à FireAds
e não substitui `consulta_fireads` ou `envios_dash`. Deve ser preservada
para que a migração reconheça o estado já aplicado.


A [migração histórica](../deploy/migrations/20261009_status_pagamento_workers.sql) registra a substituição da view antiga e a função da fila.
