# Arquivo de pesquisa Meta e contador de emergência

Arquivado em 29/09/2026 a pedido do usuário. Preserva integralmente o plano anterior, incluindo contador local, faturas, permissões, fusos e atualização do PyWa. É referência histórica, não o plano vigente nem autorização para implementar essas alternativas.

O fluxo implementado está documentado em [consumo mensal Meta](../deploy/consumo_mensal_meta.md).

---

# Proposta de controle de mensagens e custos da Meta

Status: em discussão. Este documento não implementa contador, agendamento,
alteração do webhook, banco ou painel. Revisão: 28/09/2026.

## Objetivo e fontes

Exibir por número de unidade e mês as mensagens gratuitas por anúncio, o consumo
da franquia Meta, as mensagens cobradas e a divisão entre ESL e unidade.
Decisão: usar `pricing_analytics` como caminho principal de consulta e evolução
do painel. Explorar os dados oficiais disponíveis antes de construir um contador.
A disponibilidade de fatura definitiva por API é uma investigação separada.

Foco revisto em 28/09/2026: acompanhar as quantidades de mensagens gratuitas
e classificadas como cobradas em `pricing_analytics`, usando o token operacional
existente nas contas autorizadas. Consulta de faturas e alteração do fuso do
portfólio ficam fora da implementação inicial; não são pré-requisitos para
consultar os volumes. A investigação de token pessoal para editar o portfólio
foi interrompida a pedido do usuário. As ferramentas manuais já criadas ficam
preservadas, sem execução de alterações na Meta por parte do assistente.

Continua necessário consultar e respeitar o fuso da WABA/conta de mensagens
para definir o mês, sem precisar alterar esse fuso ou o do portfólio.
Separar `FREE_ENTRY_POINT`, `FREE_CUSTOMER_SERVICE` e `REGULAR`, observando
a vigência das regras e a categoria consultada. Os volumes classificados pela
Meta atendem ao acompanhamento operacional; não chamar o relatório de fatura
financeira definitiva. Gerar um token pessoal não é necessário para esse foco.

O contador local e toda a teoria das janelas ficam preservados como **plano de
emergência**, para o caso de a consulta oficial não atender às necessidades.
Não implementar esse contador junto com a primeira integração de analytics por
precaução apenas; reavaliar sua necessidade após a consulta real. Nenhum dos
dois caminhos deve apresentar uma estimativa como fatura definitiva.

Também está decidida a atualização do PyWa, com a versão 4.5.0 como alvo já
avaliado. Validar o projeto completo antes de fixar e instalar a dependência
para o deploy, conforme a seção específica abaixo.

## Plano de emergência: janela gratuita no contador

- Não condicionar a elegibilidade à primeira conversa do cliente. Um cliente
  antigo pode retornar por outro anúncio (`referral.source_type` igual a `ad`).
  O marco é a primeira resposta do bot à entrada elegível correspondente,
  não a primeira mensagem recebida nem a primeira resposta de toda a vida do
  cliente com aquele número.
- A janela pertence ao par **cliente + número de telefone da unidade**. Não é
  global por cliente, nem compartilhada entre números diferentes da unidade.
- A resposta deve ocorrer dentro das 24 horas da entrada elegível. Apenas
  encontrar `ad` em algum atendimento antigo não demonstra uma janela aberta.
- Criar outra conversa no banco não reinicia automaticamente a janela. Validar
  o comportamento de uma nova entrada por anúncio enquanto uma janela ainda
  está aberta; não prolongar a expiração automaticamente por receber outro `ad`.
- A documentação oficial consultada descreve 72 horas a partir da resposta.
  A ampliação para sete dias ainda depende de confirmação oficial. Manter a
  duração explícita e revisável, sem tratar sete dias como regra confirmada.
- A janela gratuita não substitui a janela de atendimento de 24 horas para
  permitir mensagens sem modelo. São controles diferentes.
- O horário local do envio não deve ser apresentado como horário exato de
  faturamento da Meta. Em `statuses`, `timestamp` é documentado como horário
  Unix do disparo do webhook. Quando presente, o objeto `conversation` do
  status `sent` também informa `expiration_timestamp` da janela gratuita.

## Plano de emergência: modelo de janelas

- Criar `janela_gratuita`, separada de `conversa`, com `id_janela`, `id_cliente`,
  `id_unidade`, identificação do número, origem, início e `gratuita_expira`.
  Preservar a identificação do número na época: trocar o telefone da unidade
  não deve transferir uma janela antiga para o telefone novo.
- Manter a mensagem de entrada que comprovou a origem e o identificador da
  primeira resposta relacionada. Se futuramente forem persistidos status,
  guardar também o identificador da janela e a expiração informados pela Meta.
- Permitir várias janelas ao longo do tempo para o mesmo cliente e número.
  Uma janela pode cobrir mensagens de várias conversas internas.
- A proposta de `conversa.id_janela` pode representar a janela corrente, mas
  requer um complemento antes de virar esquema SQL: uma mesma conversa pode
  atravessar uma expiração e até outra entrada elegível por anúncio. Para
  auditoria do contador, preservar a janela aplicada a cada mensagem enviada,
  sem reclassificar mensagens antigas ao trocar a janela corrente da conversa.
- Origem `ad` e elegibilidade são evidências distintas: persistir a origem
  recebida não confirma, por si só, que a Meta abriu ou renovou uma janela.
- Estes são requisitos do plano de reserva, não uma migração autorizada.

## Contagem e franquias

### Classificação documentada para 1º de outubro de 2026

Reconsulta da documentação oficial em português em 28/09/2026: a Meta descreve
a nova franquia usando os mesmos valores de `pricing_type` já consultados pelo
utilitário. Para `pricing_category=SERVICE`, a partir de 01/10/2026:

| Tipo em `pricing_analytics` | Interpretação do `volume` entregue no mês |
| --- | --- |
| `FREE_ENTRY_POINT` | Mensagens cobertas por janela de entrada gratuita; separadas da franquia mensal. |
| `FREE_CUSTOMER_SERVICE` | Mensagens individuais sem modelo entregues dentro da franquia gratuita do número. |
| `REGULAR` | Mensagens individuais de serviço classificadas como faturáveis após o consumo da franquia, fora da janela de entrada gratuita. |

`SERVICE` passa a representar mensagens individuais sem modelo, inclusive
as cobradas; até 30/09/2026 também pode incluir templates de utilidade gratuitos.
Não misturar setembro com outubro ao interpretar consumo da nova franquia.
Não confundir esses tipos com `FREE_TIER` do antigo `conversation_analytics`.

A documentação consultada não apresenta um campo de saldo restante pronto.
Os mil créditos não são acrescentados ao `volume`: esse valor conta entregas
efetuadas. Para um número usado somente no atendimento individual desta WABA,
o saldo calculado é `max(1000 - volume_FREE_CUSTOMER_SERVICE, 0)`, consultando
desde o início do mês. A franquia é por número e compartilhada com entregas de
serviço em grupos; se houver esse uso ou outros emissores/contas fora do recorte,
a consulta atual não pode anunciar cobertura integral do saldo do número.

O utilitário já consulta `SERVICE`, `VOLUME` e os três tipos acima. Seus campos
de franquia ficam nulos em setembro por uma regra local de vigência, não porque
a Meta retornou um campo novo nulo. A partir de outubro ele aplica a subtração.
Validar uma consulta real de outubro antes de publicar essa interpretação no
painel; isso não exige criar contador local nem receber status para obter os
volumes agregados. Preservar data da consulta, período e distinção entre
analytics e fechamento financeiro.

Fontes: [analytics em português](https://developers.facebook.com/documentation/business-messaging/whatsapp/analytics?locale=pt_BR)
e [franquia mensal e preços](https://developers.facebook.com/documentation/business-messaging/whatsapp/pricing?locale=pt_BR).
A versão sem parâmetro de idioma devolveu descrições anteriores na mesma
verificação; as definições com vigência em outubro acima constam explicitamente
na versão `pt_BR`, sem inferir uma data de atualização para as demais versões.

### Regras de contabilização do sistema

- Mensagens cobertas pela janela gratuita por anúncio ficam separadas do
  consumo da franquia mensal de serviço.
- A franquia Meta discutida é de 1.000 mensagens de serviço por número/mês;
  o benefício ESL proposto cobre outras 1.000 mensagens efetivamente cobradas
  pela Meta. Não apresentar as duas parcelas como uma única franquia Meta.
- Para quantidades: ESL assume `min(cobradas_meta, 1000)`; a unidade fica com
  `max(cobradas_meta - 1000, 0)`. O valor monetário exige moeda e tarifa aplicável.
- Se o contador local for implementado, incluir envios do fluxo e do follow-up
  e impedir contagem duplicada em retries. Preservar a distinção entre pedido
  aceito pela API e mensagem entregue: HTTP de sucesso não comprova entrega.
- Hoje o webhook ignora os status de saída. Uma falha posterior de entrega não
  aciona o retry do worker por esse caminho. Usar somente envios aceitos pelos
  workers não garante reproduzir a contagem de mensagens entregues da Meta.
- Decisão: deixar a persistência de status para uma evolução futura. Aceitar
  essa limitação agora não significa que a frequência de falhas foi medida.
  Quando essa evolução ocorrer, correlacionar pelo identificador da mensagem,
  impedir dupla contagem entre `sent`, `delivered`, `read` e reentregas do
  webhook, e lidar com eventos fora de ordem. Nem o horário nem a expiração,
  isoladamente, garantem conciliação de 100% com a fatura.

## Consulta e painel propostos

- Consultar o mês corrente uma vez por dia e mostrar quando os dados foram
  atualizados. Apresentar também o mês anterior, sem assumir fechamento
  definitivo à 00:01 do primeiro dia do mês seguinte.
- Informar explicitamente `start`, `end` e fuso do período consultado. Validar
  o fuso do fechamento mensal da franquia antes de usá-lo para cobrança.
- Separar no painel: gratuitas por anúncio, consumidas da franquia Meta,
  cobradas pela Meta, assumidas pela ESL e excedentes da unidade.
- O utilitário `utilitarios/consultas_franquia/consultar_franquia_meta.py` consulta atualmente
  `VOLUME`, filtrado por `SERVICE`. Ele calcula um saldo a partir do consumo;
  não recebe da Meta um campo pronto de mensagens restantes.
- A execução manual pela IDE oferece `consultar_franquia(waba_id, phone_id)`
  e `consultar_faturas(id_portfolio)`. Os atalhos carregam o ambiente local,
  imprimem o resultado e retornam os dados. As chamadas ficam no bloco final
  do arquivo; importar o módulo não dispara consultas. A consulta de faturas
  usa GET, percorre as páginas e preserva moedas e valores sem somá-los.
  Para diagnóstico manual, `consultar_faturas(id_portfolio, meses=4)` consulta
  por data de emissão o mês atual até hoje e os três anteriores. Não restringe
  as faturas ao WhatsApp; solicita também `ad_account_ids` para identificar
  vínculos com anúncios, sem presumir que os demais registros sejam WhatsApp.
  `business_invoices` é o endpoint de faturamento mensal, não uma lista geral
  de comprovantes de cartão ou recargas. Um resultado vazio não comprova
  ausência desses outros pagamentos. Esse diagnóstico não amplia o escopo
  inicial do painel nem exige alteração do token operacional.
  Diagnóstico real em 28/09/2026, no portfólio de Santo André: consulta somente
  GET de faturas emitidas entre 01/06/2026 (inclusivo) e 29/09/2026 (exclusivo),
  incluindo o campo `ad_account_ids`, retornou zero registros sem recusa
  explícita de permissão. Não confirmou visibilidade de uma fatura conhecida
  nem ausência de pagamentos de anúncios fora do faturamento mensal.
- Prever consulta com `metric_types(VOLUME,COST)`: `COST` fornece custos
  aproximados das mensagens entregues no período, na moeda da conta. Não é
  saldo devedor nem confirmação de fatura fechada. Contas que usam a linha de
  crédito de um parceiro podem não receber essa métrica.
- Consultar o mês anterior por API é possível, mas a documentação consultada
  não transforma `COST` em fatura definitiva após o fim do mês nem informa um
  sinal de fechamento financeiro. Não chamar um dado de definitivo apenas
  porque a consulta foi feita no mês seguinte.
- Existe uma API geral de faturas empresariais (`business_invoices`) no SDK
  oficial Meta Business. Não foi confirmada sua aplicabilidade às faturas de
  WhatsApp destas unidades, ao regime de pagamento e às permissões disponíveis.
  Não prometer acesso à fatura WABA por esse caminho sem validar esses pontos.
  Até isso ser confirmado, a conferência definitiva depende da fatura oficial
  disponibilizada pela Meta ou pelo parceiro de faturamento.
- O PyWa permite montar essa consulta por `wa.api.send_raw_request`, com
  `method="GET"` e `endpoint="/{business_id}/business_invoices"`. É o ID do
  negócio, não o `phone_id` ou a WABA. Esse método genérico é documentado e
  existe nas versões 3.8.0 instalada e 4.5.0 inspecionada; não equivale a um
  método dedicado de faturas. Reutilizar o cliente não concede permissões
  financeiras nem confirma que a conta possui faturas WhatsApp acessíveis.
  Em 28/09/2026, o usuário executou a consulta autenticada pelo utilitário e
  compartilhou uma lista vazia, sem erro de acesso reportado. Isso confirma a
  execução naquele portfólio, mas não comprova a disponibilidade de suas
  faturas WhatsApp nem ausência de cobranças.
- Antes de publicar totais, validar uma resposta real, a cobertura dos tipos
  de preço/categorias de anúncios, a disponibilidade de `COST`, a moeda e se
  existem outros emissores consumindo a franquia do mesmo número. Falha ou
  ausência de dados deve aparecer como indisponibilidade, não saldo integral.

### Primeira consulta real compartilhada pelo usuário

Em 28/09/2026, para setembro até 16:25 no fuso `America/Sao_Paulo`, a consulta
do número selecionado retornou 56 em `FREE_CUSTOMER_SERVICE`, 519 em
`FREE_ENTRY_POINT` e zero em `REGULAR`: 575 mensagens na categoria `SERVICE`
e no recorte consultado. São volumes de mensagens, não clientes/conversas.
O utilitário não consultou `COST` nem outras categorias; esse resultado não é
uma demonstração de saldo financeiro ou do total da fatura do portfólio.

`franquia_vigente_no_periodo=false` e os saldos `null` foram produzidos pelo
utilitário porque setembro precede a vigência configurada de 01/10/2026.
Não são campos de saldo prontos retornados pela Meta, nem significam que as
56 mensagens consumiram a franquia de outubro. A consulta não valida ainda o
comportamento da nova franquia após sua entrada em vigor.

### Fuso confirmado pela API em 28/09/2026

Consultas somente de leitura, com `fields=id,timezone_id`, retornaram:

- Portfólio terminado em `6919`: `timezone_id=0`. A tabela oficial da Meta
  identifica esse código como `TZ_UNKNOWN`; não interpretar como UTC+00:00.
- WABA terminada em `8897`: `timezone_id=206`, correspondente a
  `TZ_AMERICA_BAHIA` (`America/Bahia`), atualmente UTC−03:00.

O período dos relatórios de mensagens deve respeitar o fuso da conta de
mensagens consultada, sem deduzi-lo do portfólio, dispositivo ou servidor.
O parâmetro `fuso_horario` do utilitário ainda é informado manualmente:
`America/Sao_Paulo` e `America/Bahia` coincidem no recorte de setembro de 2026,
mas são identificadores diferentes. Para essa WABA, usar `America/Bahia`.
Uma evolução do utilitário deve consultar e validar esse dado por WABA.

O `consultado_em` das faturas usa `datetime.now(timezone.utc)` no utilitário;
seu sufixo `+00:00` não representa uma configuração retornada pela Meta.
Nenhuma configuração das contas foi alterada nesta verificação.

Ferramenta manual disponível em
`utilitarios/consultas_franquia/alterar_fuso_portfolio.py`:
`alterar_fuso_portfolio(id_portfolio, id_timezone)` usa `requests`, consulta o
valor atual, envia somente `timezone_id` ao portfólio quando necessário e
confirma com novo GET. Exemplo de ID para a Bahia: `206`; São Paulo: `25`.
O exemplo no final do arquivo fica comentado para execução deliberada na IDE.
Validada com respostas simuladas, sem executar alteração real na Meta.

Em teste real do usuário com um portfólio de cliente terminado em `8885`,
a leitura inicial passou, mas o POST foi recusado com HTTP 400 / código 3910.
A referência oficial de Business identifica esse código como falta de permissão
para editar os dados do portfólio. Acesso à WABA e leitura de dados não devem
ser tratados como autorização administrativa do portfólio. A ferramenta agora
explica o erro; nenhum novo POST foi realizado durante o diagnóstico.

Na consulta somente de leitura a `me` e `me/permissions`, em 28/09/2026,
o token configurado no projeto retornou o nome `ed` e já possuía
`business_management`, `whatsapp_business_management` e
`whatsapp_business_messaging` com status `granted`. Portanto, adicionar
`business_management` no Explorador não resolve, por si só, o erro 3910:
também é necessária autorização da identidade para editar o portfólio alvo.
Acesso pessoal do operador não é transferido ao usuário do sistema.

Preferência do usuário: manter um único token operacional para os ativos
autorizados. Não substituir a credencial do chatbot por um token pessoal nem
gerar tokens por cliente automaticamente. Alterações administrativas que não
estejam autorizadas ao token operacional exigem um acesso adequado separado;
não presumir que compartilhar uma WABA permite editar seu portfólio proprietário.

## Concorrência dos workers: comportamento preservado

A expiração autoriza uma nova tentativa de aquisição; não distribui a mensagem
para todos os workers. No código atual:

- O dequeue usa `FOR UPDATE SKIP LOCKED` e atualiza o estado e horário na mesma
  operação. Dois workers concorrentes não adquirem simultaneamente a mesma
  mensagem expirada por esse caminho.
- O lock da conversa usa `UPDATE` condicional atômico e incrementa
  `lock_version`. `proteger_conversa` verifica a versão e a validade, e o unlock
  exige a mesma versão para não liberar o lock de outro proprietário.
- O limite de recuperação da fila é de dois minutos; o lease da conversa é de
  110 segundos. Não adicionar um temporizador de reset para resolver uma corrida
  que já é arbitrada pelo banco. Uma limpeza indiscriminada poderia interferir
  em uma aquisição ou renovação recente.
- Essas proteções não garantem envio exatamente uma vez à API externa: envio
  aceito seguido de queda antes de persistir continua sendo uma limitação.
  Nenhuma alteração da fila ou dos locks faz parte desta proposta.
- A aquisição atômica decide qual worker assume; `lock_version` impede que um
  proprietário anterior finalize ou libere o lock como se ainda fosse o dono.
  Essa proteção cobre o cenário analisado e deve ser preservada nos novos
  fluxos. Não representa uma garantia geral de ausência de condições de
  corrida em qualquer mudança futura do projeto.

## Atualização do PyWa: planejada, ainda não aplicada

- Decisão de 28/09/2026: atualizar o PyWa como manutenção da dependência.
  Os ensaios iniciais passaram, mas não aprovaram compatibilidade integral;
  a execução da atualização inclui testes do projeto em ambiente isolado,
  correção de eventuais incompatibilidades, fixação no `requirements.txt` e
  instalação da mesma versão na VM durante o deploy.
- Versão instalada e fixada em `requirements.txt`: 3.8.0. Versão estável mais
  recente consultada no PyPI em 27/09/2026: 4.5.0 (Python >= 3.10).
- O guia 3.x para 4.x lista mudanças incompatíveis, incluindo identidades de
  usuários e estruturas de retorno. Não assumir compatibilidade integral
  apenas por atualizar a dependência.
- As assinaturas usadas no projeto para envio, criação do cliente e
  bloqueio/desbloqueio permanecem disponíveis. O projeto usa `.id` do retorno
  de envio; esse campo foi preservado nos ensaios locais.
- Oito chamadas simuladas com o pacote 4.5.0 passaram: texto com rodapé, botões,
  botão URL, lista, solicitação de contato, bloqueio, listagem de bloqueados e
  desbloqueio. Os ensaios usaram transporte HTTP simulado, sem enviar mensagens
  nem alterar contas. Isso não equivale à validação completa do projeto.
- Ativação/desativação da WABA e registro de número usam `requests` diretamente
  no projeto. Atualizar somente o PyWa não troca esses métodos por outros.
- O cliente público do PyWa 4.5.0 inspecionado não expõe métodos dedicados de
  `pricing_analytics` ou faturas. Há suporte a requisições genéricas por
  `wa.api.send_raw_request`. Atualizá-lo não é pré-requisito para a consulta
  Graph API já usada no utilitário.
- Na atualização planejada: testar em ambiente isolado, revisar formatos de
  retorno e erros, fixar a versão aprovada no `requirements.txt`, instalar essas
  dependências no ambiente virtual da VM e reiniciar os serviços afetados.
  `git pull` sozinho não atualiza as bibliotecas instaladas. Manter a versão da
  Graph API configurada explicitamente e validar o deploy e a reversão.

## Referências oficiais

- [Preços e janelas gratuitas](https://developers.facebook.com/documentation/business-messaging/whatsapp/pricing)
- [Análises de mensagens e custos](https://developers.facebook.com/documentation/business-messaging/whatsapp/analytics)
- [Identificadores de fuso horário da Meta](https://developers.facebook.com/docs/marketing-api/reference/ad-account/timezone-ids/)
- [Contas WhatsApp e restrições de alteração](https://developers.facebook.com/documentation/business-messaging/whatsapp/whatsapp-business-accounts)
- [Status de mensagens no webhook](https://developers.facebook.com/documentation/business-messaging/whatsapp/webhooks/reference/messages/status)
- [API de faturas no SDK oficial Meta Business](https://github.com/facebook/facebook-python-business-sdk/blob/main/facebook_business/adobjects/business.py)
- [PyWa no PyPI](https://pypi.org/project/pywa/)
- [Migração do PyWa 3.x para 4.x](https://pywa.readthedocs.io/en/latest/content/migration.html)
- [Requisições genéricas pelo PyWa](https://pywa.readthedocs.io/en/latest/content/client/api_reference.html#pywa.api.GraphAPI.send_raw_request)
