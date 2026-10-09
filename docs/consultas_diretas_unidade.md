# Consultas diretas da unidade e personalização

Alteração local de 09/10/2026, posterior ao deploy da V1.10.0 (`49af8d5`).
Ainda precisa de deploy; nenhuma view ou dado foi removido da produção.

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

## Próximo deploy

1. Parar webhook/workers e atualizar o código.
2. Aplicar inteiro o SQL unificado de pagamento e remoção da view:
   [`20261009_status_pagamento_workers.sql`](../deploy/migrations/20261009_status_pagamento_workers.sql).
   Atualiza a função da fila e remove a view na mesma transação, sem alterar
   tabelas, colunas ou dados. Usa `RESTRICT` para recusar a remoção caso outro
   objeto do banco dependa dela. Pode reexecutar. O arquivo de remoção isolada
   permanece como alternativa; não é necessário executar ambos.
3. Validar Django e iniciar os serviços pelo procedimento habitual.

Não excluir a view antes de atualizar os consumidores: a versão ainda em
produção depende dela. A migração FireAds usada no setup foi ajustada para
não criar/recriar a view. Em uma base já implantada, o SQL unificado acima
remove o objeto antigo. Não é necessário refazer a separação das tabelas.

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

## Validação

Em 09/10/2026 passaram **207 testes**: 49 de integração com PostgreSQL local
descartável e 158 dos módulos afetados de atendimento, follow-up, FireAds,
painel e relatórios. Não houve falhas, erros ou testes pulados. A sintaxe dos
arquivos Python alterados e a formatação do diff também foram verificadas.

As bases atuais de teste não possuem a view. As verificações incluem mudanças
de personalização refletidas na leitura, titular/dependente, isolamento de
unidades, rotas com/sem link, relatórios de unidades sem histórico e reexecução
das migrações sem recriar a view. Não houve requisições externas de envio nem
alterações no banco de produção.
