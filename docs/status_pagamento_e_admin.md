# Personalização no Admin e suspensão da unidade

Atualização local de 09/10/2026, posterior ao deploy da V1.10.0
(`49af8d5`). Exige novo deploy. Nenhuma unidade de produção foi desativada
por esta alteração.

## Organização do Admin

- **Unidades:** identidade, contatos administrativos, WABA, phone ID,
  monitoramento e `status_pagamento`.
- **Atendimentos customizados:** nome e gênero do agente, BPA, contato comercial,
  regra de idade, obrigatoriedade de e-mail e links de agendamento e Instagram.
- A edição da unidade oferece um link para sua personalização. Não repete os
  campos de personalização na listagem nem no formulário de edição da unidade.
- Na criação de uma unidade, o formulário de personalização continua obrigatório
  na mesma tela/transação. Isso evita uma unidade sem as configurações necessárias.

No banco, esses campos já pertencem exclusivamente a `atendimento_customizado`
desde a migração FireAds. As propriedades de compatibilidade do modelo `Unidade`
apenas leem essa relação; não duplicam as colunas nem seus valores.

## Um único controle: status_pagamento

Usamos a coluna existente `unidade.status_pagamento`; não criamos `unidade_ativa`.
No Admin, o campo aparece como **Status pagamento / unidade ativa**.

| Valor | Efeito |
| --- | --- |
| Sim (`TRUE`) | Habilita o processamento, sujeito às demais regras e configurações de cada integração. |
| Não (`FALSE`) | Suspende o processamento daquela unidade e mantém seu histórico. |
| Desconhecido (`NULL`) | Também suspende; somente `TRUE` habilita. |

A gravação pelo Admin mantém a atualização já existente do cache de unidades.
O webhook ignora novas mensagens de unidades inativas. A fila não reserva
mensagens pendentes dessas unidades e não consome suas tentativas.
O worker principal também confere o banco antes de iniciar e de responder,
mesmo que um cache antigo ainda apresente a unidade como ativa.

Follow-up deixa de selecionar a unidade. Funil não materializa nem reserva novas
entregas dela e revalida a elegibilidade antes do envio. FireAds deixa de consultar
novas conversas e de reservar entregas; revalida a permissão antes de escrever no
dashboard. Consumo Meta deixa de consultar a conta e os meses da unidade, inclusive
quando a desativação ocorre depois de carregar a lista de unidades do ciclo.

Cadastros, conversas, respostas, consumo anterior e filas permanecem no banco.
Pendências não são marcadas como enviadas nem apagadas. O painel histórico não é
desativado por este campo. Reativar permite retomar pendências que ainda forem
elegíveis; não cria novamente uma integração ou altera suas opções individuais.

A desativação é verificada nas barreiras anteriores às operações externas.
Uma operação já autorizada/em andamento no momento da gravação pode concluir;
se houver confirmação externa, ela continua sendo registrada para não provocar
reenvio por falta de registro local. Não é um cancelamento remoto de requisições.

## Implantação

1. Parar webhook/workers e atualizar o código pelo procedimento habitual.
2. Executar inteiro no DBeaver
   [`20261009_status_pagamento_workers.sql`](../deploy/migrations/20261009_status_pagamento_workers.sql).
   O SQL unificado atualiza a função da fila e remove a antiga view na mesma
   transação. Exige o código de [consultas diretas](consultas_diretas_unidade.md).
   Não move colunas nem altera o status de nenhuma unidade. Pode reexecutar;
   não é necessário executar também o arquivo de remoção isolada.
3. Validar Django e reiniciar os serviços.
4. No Admin, editar a unidade desejada e definir **Status pagamento / unidade
   ativa = Não**. Salvar. A suspensão completa exige esta versão em execução.

Os testes de regressão abrangem unidade inativa e valor nulo, preservação do
histórico e pendências, reativação, migração/reexecução da fila, desativação durante
um ciclo, isolamento entre unidades e cadastro/edição no Admin. As verificações
usam PostgreSQL local descartável e chamadas externas simuladas.

Validação da alteração de pagamento, antes da remoção da view, em 09/10/2026:
**495 testes passaram, sem falhas, erros ou testes
pulados**. Django models/Admin sem apontamentos; sintaxe dos arquivos alterados
válida; SQL da função no setup e na migração conferidos como equivalentes.
