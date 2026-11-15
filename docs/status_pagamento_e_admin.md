# Personalização no Admin e suspensão da unidade

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


A alteração histórica do schema consta em [migrações](../deploy/migrations/20261009_status_pagamento_workers.sql).
