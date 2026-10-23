# Monitoramento: filtros por período, origens FireAds e anúncios

Data da consolidação: 22/10/2026.

Status: aplicado ao código local em 22/10/2026. Inclui filtros, relatórios,
atribuição por conversa e seleção de registros. Ainda não representa deploy.

Este é o registro das definições da conversa com o responsável pelo projeto.
Para este trabalho, ele substitui as sugestões anteriores de usar a última
conversa global fora do período, contar apenas a última conversa nos relatórios
ou criar consultas extras à FireAds exclusivamente para obter métricas.

## 1. Objetivo e limites

- Melhorar a organização dos filtros na seção Conversas.
- Identificar atendimentos originados dos formulários FireAds e distinguir o
  Orgânico Site do contato 100% orgânico cadastrado pelo chatbot.
- Mostrar resultados por canal e por anúncio da Meta dentro de Relatórios.
- Usar os dados locais para renderizar o painel, sem consultar a FireAds a cada
  abertura ou atualização da página.
- Preservar as regras de dados parciais, bloqueios, pagamento, perguntas por etapa,
  indicação de digitação e isolamento entre unidades.
- Não publicar, fazer deploy ou escolher uma nova versão por causa deste documento.

## 2. Regra central: primeiro o período, depois a conversa representativa

**Conversas e seus filtros usam a última conversa de cada chat dentro do período
selecionado. Relatórios consideram todas as conversas elegíveis desse período.**

Um chat representa o relacionamento de um cliente com uma unidade. O mesmo
telefone em outra unidade não participa dos resultados da unidade autenticada.

### 2.1. Recorte temporal e seleção

1. Preservar a definição atual de participação no período: a conversa precisa
   ter mensagem do cliente no intervalo selecionado. Isso inclui atendimento
   iniciado antes do intervalo e retomado pelo cliente dentro dele.
2. Usar o mesmo intervalo em todas as leituras: início inclusivo e fim exclusivo.
   Reutilizar `callback/monitoramento/periodos.py` e a apresentação de datas no
   fuso do painel.
3. Entre as conversas elegíveis de cada chat, selecionar a mais recente por
   `iniciou_em`, com desempate por `id_conversa`. Mensagem tardia de um atendimento
   anterior não deve transformá-lo no atendimento mais novo.
4. Somente depois dessa seleção aplicar o filtro solicitado. Não buscar a última
   conversa que satisfaça o filtro, pois isso resgataria indevidamente uma antiga.
5. Conversas fora do intervalo não podem suprimir ou substituir a representante
   escolhida dentro dele.
6. O histórico de mensagens pode continuar consolidado por chat, limitado ao
   período. As tags e a condição de inclusão nos filtros vêm da representante.
7. A classificação é do atendimento selecionado; não prometer reconstrução de
   todos os estados intermediários que nunca foram registrados historicamente.

### 2.2. Exemplos obrigatórios

- A conversa A foi avaliada e depois começou B sem avaliação. Se ambas estiverem
  no período, o chat não entra em Avaliadas. Se só A estiver no recorte, entra.
- A foi enviada ao Funil e B ainda não. Com ambas no período, o chat não entra em
  Funil por causa de A. Uma retentativa de envio não cria outro atendimento.
- A era para dependente e B para titular: os filtros e tags usam B quando ela é
  a última no recorte. O histórico de A permanece acessível no período adequado.
- A veio da Meta e B é orgânica: o chat usa a origem de B quando ambas participam.
- Uma conversa posterior fora do recorte não anula Comercial, Follow-up,
  Avaliadas ou qualquer outro filtro da representante dentro do recorte.

## 3. Filtros e apresentação da seção Conversas

Todos os filtros usam a mesma conversa representativa:

| Opção | Regra |
| --- | --- |
| Todas | Todos os chats elegíveis no período, sem condição adicional. |
| Comercial | Encerramento da representante atende aos critérios comerciais já existentes. |
| Follow-up | Representante está na condição de follow-up já reconhecida pelo sistema. |
| Funil | Envio da representante confirmado localmente como `sent`, com `enviado_em` no período. |
| Avaliadas | Representante possui nota registrada no período. |
| Titular | Destinatário da representante confirmado como titular. |
| Dependentes | Destinatário da representante confirmado como dependente. |
| FireAds / Todos | Origem confirmada da representante é um dos quatro canais de formulário. |
| FireAds / Chat Fire | Origem confirmada `chat_fire`. |
| FireAds / Meta Ads | Origem confirmada `meta`. |
| FireAds / Google Ads | Origem confirmada `google`. |
| FireAds / Orgânico Site | Origem confirmada `organico_site`. |
| 100% orgânico | Origem efetivamente confirmada `organico`; não inclui origem provisória ou desconhecida. |

Titular e Dependentes não dependem de integração FireAds. Não classificar
automaticamente como titular uma conversa cuja coluna tenha apenas o valor
padrão `false`, mas que ainda não tenha confirmação de destinatário. Aproveitar
as evidências da coleta ou do fluxo, sem interpretar idade como parentesco.

FireAds, seus subfiltros e 100% orgânico ficam disponíveis para unidades com
integração FireAds. A regra de habilitação deve ser centralizada no servidor e
compartilhada com Relatórios; não inferir a integração por nome de unidade,
telefone, código comercial padrão ou existência de uma conversa antiga.

### 3.1. Organização visual

- Substituir a faixa de botões apertados por um seletor compacto abaixo da busca.
- Exibir claramente a seleção atual, por exemplo `Mostrar: Todas` ou
  `FireAds: Meta Ads`.
- Agrupar os quatro canais sob FireAds, com a opção Todos da FireAds.
- Manter 100% orgânico no nível principal, fora do grupo FireAds.
- Abrir opções por clique, toque e teclado; hover pode ajudar, mas não pode ser
  a única forma de acessar o submenu.
- Manter rótulos inteiros, foco visível, fechamento por Escape, retorno de foco
  e estados acessíveis de expansão/seleção. Evitar menus fora da tela no celular.
- Preservar identidade visual, cores, espaçamentos e hierarquia do painel.
- Evitar rolagem horizontal e rolagem desnecessária para encontrar os filtros.
- Mostrar tags Google, Meta, Chat Fire e Orgânico Site na lista/cabeçalho quando
  aplicáveis, sem acumular tags de atendimentos anteriores.
- Se o chat selecionado deixar de satisfazer o filtro após uma atualização,
  reconciliar a seleção e o histórico exibido para não parecer que ele ainda
  pertence ao resultado filtrado.

## 4. Relatórios: conversas, contatos e envios não são a mesma contagem

Manter os novos indicadores em um bloco separado dentro de Relatórios:
**Origem dos atendimentos — FireAds e orgânico**. Não criar nova seção principal.

O bloco só aparece para unidades com integração. Usa o mesmo período selecionado
e todas as conversas elegíveis do chat, sem aplicar a redução à última conversa
que é exclusiva da seção Conversas.

### 4.1. Canais

Exibir barras horizontais para Google Ads, Meta Ads, Orgânico Site, Chat Fire e
100% orgânico. Mostrar, por canal:

- Quantidade de atendimentos com aquela origem confirmada no recorte.
- Quantos desses atendimentos tiveram envio ao Funil confirmado no período.
- Valores exatos em tabela ou rótulos legíveis; a cor não deve ser a única forma
  de entender as séries.

Cada `id_conversa` conta uma vez. Joins com mensagens, dependentes, avaliações ou
tentativas de envio não podem multiplicar esse total. Uma conversa pelo Google
e outra pelo Chat Fire, do mesmo contato, contam nos respectivos canais.

Indicadores chamados **Contatos únicos** deduplicam o cliente dentro da unidade
e do período. Não somar contagens únicas por canal como se fossem o total geral,
pois o mesmo cliente pode aparecer em canais diferentes.

Envio ao Funil significa registro local `funil_envios.status = 'sent'` e data
`enviado_em` no intervalo. Dashboard enviado, envio pendente, tentativa HTTP ou
conclusão da triagem não substituem essa confirmação. O envio deve pertencer à
mesma conversa contada no canal/anúncio.

Manter explícita a base de cada indicador existente: contatos únicos,
atendimentos, mensagens, avaliações ou encerramentos. Não converter silenciosamente
todos os cartões antigos em contagens de conversas. Os indicadores históricos
não devem descartar atendimentos apenas porque o chat ganhou outra conversa.

Esses números medem atendimentos que chegaram ao chatbot. Não representam todos
os formulários preenchidos, impressões, cliques ou leads da planilha que nunca
falaram com o bot. Atendimento sem origem definida fica fora das cinco séries;
um aviso de cobertura pode informar a quantidade ainda não classificada.

### 4.2. Anúncios da Meta

- Exibir uma tabela por anúncio/criativo com atendimentos e envios ao Funil.
- Considerar exclusivamente conversas com origem confirmada Meta Ads.
- Meta com campo vazio permanece em Meta e entra em **Anúncio não informado**.
- Usar o valor da coluna `Anuncio`, não extrair identificação das observações.
- Agrupar o mesmo valor com normalização conservadora de espaços; conservar o
  texto original para apresentação. Não usar comparação aproximada nem juntar
  anúncios distintos por semelhança.
- O valor pode ser nome/código de criativo da FireAds. Não tratá-lo como `ad_id`
  oficial da Meta sem evidência adicional.
- Nunca inferir anúncio para Google, Chat Fire, Orgânico Site ou Orgânico.

## 5. Identificação da origem: apenas os dois momentos já previstos

**Não criar consulta adicional ou tarefa em segundo plano apenas para métricas.**

### 5.1. Consulta inicial elegível

- Somente unidades com integração aplicável.
- Consultar se falta algum dos três valores essenciais: nome, email e destinatário.
- Para unidades sem link de agendamento, turno é o quarto valor relevante.
- Se todos os valores necessários vieram na primeira mensagem, essa consulta
  não acontece; não reintroduzi-la por causa do painel.
- Aproveitar canal e anúncio da linha selecionada pela consulta, mesmo se os
  dados do formulário forem parciais e ainda houver perguntas a fazer.
- Preservar a prioridade dos valores aceitos da mensagem e as perguntas na etapa
  apropriada quando faltarem dados também na planilha.

### 5.2. Preparação da entrega pelo worker_funil

- Antes de escrever no dashboard e congelar o envio ao Funil, localizar o
  registro pelos formatos de telefone reconhecidos pelo projeto.
- Aproveitar o canal e o anúncio do registro escolhido. Quando houver mais de
  um elegível, usar data/hora mais recente, com desempate por maior linha; manter
  a regra existente para datas ausentes ou inválidas.
- Se precisar criar um registro segundo a seção 7, a origem será Orgânico.
- Congelar a decisão e o conteúdo para as retentativas da mesma entrega.
- A confirmação posterior pode completar/corrigir uma origem provisória. Não
  reconstruir um envio histórico já confirmado com uma nova campanha atual.

Nos dois momentos, a unidade e o telefone do atendimento são obrigatórios para
associar a origem. Nome, email, destinatário e turno não filtram a identidade da
linha. Não deduzir origem pela aparência de formulário da mensagem, pelo código
comercial compartilhado ou pelo campo `lead_no_dash`.

Timeout, falha de API e consulta não realizada não provam origem orgânica. Até
haver evidência, manter origem de monitoramento indefinida, mesmo quando um
campo legado use `organico` como fallback operacional. Uma busca bem-sucedida
sem registro elegível pode fundamentar a classificação orgânica; a preparação
da entrega confirma novamente a decisão antes do envio.

## 6. Armazenamento e evidências verificadas

### 6.1. Confirmação realizada em 22/10/2026

Foi executado GET na integração ativa de Supera Santo André, aba
`LEADS GERAL - Feedback`, usando a configuração lida do banco em transação somente
leitura. O cabeçalho retornado é exatamente **`Anuncio`**, sem acento.

Naquela leitura havia 442 linhas Meta Ads, das quais 295 tinham o campo preenchido.
Esses totais são apenas evidência da inspeção, não valores fixos do produto.
Não foi realizado POST, alteração de cadastro ou teste de duplicidade em produção.

O cliente HTTP já recebe todas as colunas. Na consulta inicial, as linhas do
telefone são persistidas em `consulta_fireads.dados.fontes.geral`. Assim, alguns
resultados históricos podem já conter `Anuncio`, mesmo sem exposição no painel.

### 6.2. Decisão de armazenamento

Usa a coluna JSONB existente `conversa.contexto_fireads`, com a chave
própria e versionada `atribuicao_monitoramento`. Não misturar os
metadados com as chaves da coleta ou sobrescrever o contexto inteiro.

O contrato dessa chave deve registrar:

- Versão 1 e estado confirmado; chave ausente ou sem prova indica origem não identificada.
- Canal normalizado e evidência de formulário/ausência de registro elegível.
- Anúncio bruto e chave de agrupamento, somente para Meta.
- Momento da captura: consulta inicial ou preparação da entrega.
- Data da captura e referência da linha escolhida.
- Identificadores locais necessários para provar a associação à conversa.

Usar nomes, tipos e um único conjunto de funções compartilhadas para escrever e
interpretar esse contrato. Guardar o mesmo metadado necessário no snapshot da
entrega para que a recuperação não dependa de uma consulta futura diferente.
Se houver confirmação inicial e outra na entrega, preservar a evidência inicial
e indicar qual confirmação final orienta o relatório; não perder a proveniência.

Não acrescentar `Anuncio` a `CAMPOS_IDENTIDADE`, pois isso mudaria o contrato de
relocalização dos snapshots antigos. O anúncio é metadado, não identificador
obrigatório da linha. Uma coluna ausente não deve quebrar atendimento ou envio.

Não está prevista migração SQL obrigatória para esse armazenamento JSONB. Se a
implementação demonstrar necessidade concreta de índice ou coluna, preparar e
documentar a migração para o deploy. Não alterar o banco de produção nesta fase.

Histórico sem prova suficiente fica não identificado. Pode-se aproveitar uma
linha já salva e comprovadamente selecionada para a conversa; não atribuir o
anúncio atual a conversas antigas por uma nova busca apenas pelo telefone.

## 7. Criação de novo Orgânico e alternativa por recusa de duplicidade

Os quatro canais de formulário elegíveis são Google Ads, Meta Ads, Chat Fire e
Orgânico Site. **Orgânico não é um quinto canal de formulário.**

| Situação do telefone | Decisão de entrega |
| --- | --- |
| Há linha de um dos quatro canais | Atualizar a mais recente entre as elegíveis. |
| Há apenas linhas Orgânicas | Criar outra linha Orgânica para a nova conversa. |
| Há apenas Indicação/Lead Franqueador | Preservar as linhas manuais e criar uma Orgânica. |
| Não há linha do telefone | Criar uma Orgânica. |

Um Orgânico mais recente não deve esconder um formulário elegível mais antigo.
As variantes de telefone continuam válidas antes de concluir ausência.

Canal desconhecido ou cabeçalho inválido não comprova ausência: manter a entrega
pendente para diagnóstico, sem inventar classificação ou sobrescrever a linha.

Se a API recusar explicitamente um append por telefone duplicado, reler e usar
como alternativa a linha **Orgânica mais recente do mesmo telefone**, preservando
suas observações. Não atualizar Indicação/Lead Franqueador como alternativa. Se
não houver alvo orgânico seguro, manter pendente com motivo identificável.

A rotina `appendRows` do Apps Script anexado não verifica duplicidade por
telefone; acrescenta linhas ao fim da aba. Isso não é prova de POST executado na
versão publicada. Só reconhecer recusa de duplicidade por resposta inequívoca
da API, nunca por qualquer HTTP 400, texto genérico ou timeout. O contrato atual
não fornece um código de duplicidade confirmado; se surgir resposta nova não
reconhecida, preservar a pendência em vez de acionar uma atualização especulativa.

Códigos comerciais mantidos: Google Ads `113336`, Meta Ads `113340`, Chat Fire,
Orgânico Site e Orgânico `113481`. O código compartilhado não serve para agrupar
as origens no painel; usar o canal confirmado.

## 8. Recuperação e integridade

- Nova conversa pode criar nova linha Orgânica. Retry da mesma conversa não.
- Preservar os marcadores técnicos e a reconciliação das observações existentes.
- Se o POST pode ter sido aceito e a resposta se perdeu, consultar o marcador
  daquela entrega antes de repetir append ou mudar o destino.
- Persistir a decisão da entrega e eventual mudança explícita para alternativa
  orgânica, para retries não escolherem linhas diferentes a cada tentativa.
- Preservar observações anteriores e acrescentar o bloco do chatbot uma única vez.
- Manter dashboard confirmado antes do Funil nas unidades integradas, reservas
  adequadas e conferência de posse antes de confirmar resultados locais.
- Canal e anúncio confirmados devem sobreviver às mesmas quedas que o snapshot.
- Reconhecer a janela residual entre serviço externo aceitar e o banco registrar.
  Não prometer exatamente uma entrega em todos os cenários; tampouco remover
  a reconciliação existente por esse risco ser conhecido.

## 9. Mapa de implementação

1. **Origem e anúncio:** centralizar o contrato JSON, extrair `Anuncio` da linha
   selecionada em `workers/worker_consulta_dash/resultado.py`,
   `core/integrations/fireads/coleta_abertura.py` e
   `workers/worker_funil/preparacao_fireads.py`; persistir pelos repositórios.
2. **Seleção e recuperação:** separar canais de formulário de canais de saída
   em `core/integrations/fireads/aba_geral.py`; revisar criação/reconciliação em
   `sincronizacao_coleta.py`, `core/repositories/fireads/envios.py` e worker_funil.
   Preservar entregas já congeladas e formatos antigos de snapshots.
3. **Conversas:** selecionar representante por período em
   `core/repositories/monitoramento/painel.py`, ajustar Comercial em
   `core/repositories/monitoramento/encerramentos.py` e remover a união de estados
   antigos em `callback/monitoramento/apresentacao.py` e `services.py`.
4. **Relatórios:** consultas em lote por unidade/período, sem multiplicação de
   conversas; disponibilizar origem/anúncio e cobertura através das APIs existentes.
5. **Interface:** atualizar `painel.html`, `painel.js` e `painel.css`, com seletor
   acessível, tags coerentes, bloco de barras e tabela de anúncios.
6. **Validação:** testes de regras/consultas/recuperação e inspeção visual local
   em tela larga e celular. Usar fixtures e serviços externos simulados para
   alterações; não fazer POST de produção para testar o painel.
7. **Documentação e deploy:** atualizar regras de negócio, arquitetura, testes e
   instruções de deploy; harmonizar `fireads_sincronizacao_campos.md` com a regra
   final de criação. Informar se haverá SQL e conferir `collectstatic` no deploy.

## 10. Critérios de aceite

- [x] Recortar o período antes de escolher a última conversa de cada chat.
- [x] Todos os filtros usam a mesma representante; nenhuma conversa externa ao
      período anula seus estados.
- [x] Avaliação/Funil da conversa anterior não qualificam a nova representante.
- [x] Titular/Dependente não usam perfil antigo nem destinatário ainda indefinido.
- [x] Relatórios contam todas as conversas elegíveis e identificam contatos únicos
      separadamente; retries e joins não aumentam números.
- [x] Funil usa confirmação e data da mesma conversa, respeitando o período.
- [x] Origem pendente/erro não vira Orgânico; não existem consultas extras só para métricas.
- [x] Meta sem `Anuncio` permanece no total Meta e no grupo Anúncio não informado.
- [x] Nome de criativo não é apresentado como identificador oficial de anúncio.
- [x] Metadados JSON coexistem com os contextos antigos sem quebrar sua leitura.
- [x] Novo atendimento orgânico cria nova linha quando não há formulário elegível;
      tentativa repetida da mesma entrega reconcilia a linha já criada.
- [x] Alternativa de update depende de recusa explícita por duplicidade e alvo
      orgânico seguro; timeout não dispara essa alternativa.
- [x] As formas reconhecidas de telefone continuam encontrando o mesmo contato.
- [x] Unidades não integradas não recebem filtros/gráficos específicos FireAds;
      dados de outra unidade nunca são consultados ou retornados.
- [x] Seletor funciona por mouse, toque e teclado, sem rótulos cortados; gráficos
      e tabelas ficam legíveis em desktop/celular, com estados vazio/erro/carregando.

## 11. Implementação e validação local

O contrato está centralizado em `core/integrations/fireads/atribuicao.py` e a
agregação em `callback/monitoramento/origens.py`. Nenhuma coluna, índice ou
migração SQL nova foi necessária. O deploy precisa atualizar os workers, webhook
e estáticos com collectstatic, conforme `deploy/README.md`.

Validação final: 331 testes unitários e 68 testes de integração aprovados;
PostgreSQL descartável em loopback, com HTTP/WhatsApp simulados. Django check
sem problemas e JavaScript aprovado na verificação de sintaxe. A interface foi exercitada no Chrome em desktop e celular, incluindo
mouse, teclado, toque, filtros vazios, anúncios e unidade sem integração.

O fallback por duplicidade reconhece `success=false` com `code=DUPLICATE_PHONE`
ou mensagens exatas normalizadas de telefone duplicado/já cadastrado; HTTP 400/409
também exige esse corpo explícito. O contrato publicado ainda não confirmou um
código próprio. Resposta diferente fica pendente e não dispara update especulativo.
Não houve POST de teste na FireAds nem retroatribuição de campanhas históricas.
