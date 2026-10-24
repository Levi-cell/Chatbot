# Plano: perfis por origem, identificação de origem e anúncios do Google

Registro: **23/10/2026**. Base analisada: **V1.16.1**.

**Status: aplicado ao código local em 24/10/2026, após autorização do usuário.
Ainda não implantado na VM. Não requer migração SQL.**

As seções 1–10 preservam a especificação e as decisões tomadas em 23/10/2026;
menções a trabalho futuro nessas seções descrevem aquela fase. A seção 11 registra
a implementação e substitui os avisos anteriores de que a aplicação aguardava
autorização. O novo serviço precisa ser instalado e habilitado no deploy, com
marco fixo de ativação. Banco, cache e serviços de produção não foram alterados.

## 1. Decisões e limites desta proposta

Registrar três evoluções para a seção **Relatórios**, nas unidades com integração
FireAds habilitada:

1. Detalhamento opcional dos perfis dos atendimentos por canal e por anúncio:
   titular/dependente, faixa etária, atendimentos e envios ao Funil.
2. Informação acessível junto ao indicador **“ainda sem origem”**, explicando
   quando a origem é identificada e por que ela pode permanecer desconhecida.
3. Bloco **“Anúncios do Google”** logo abaixo de **“Anúncios da Meta”**, seguindo
   o mesmo modelo visual e oferecendo o mesmo detalhamento de perfis.

**Definição adicional aprovada em 23/10/2026:** criar um worker separado para
consultar a origem dos novos atendimentos ainda não identificados, **a cada duas
horas (7.200 segundos)**, aproveitando a mesma leitura para obter a referência de anúncio de
Google Ads ou Meta Ads. Não executar essa responsabilidade no `worker_funil`.
O nome aprovado é **`worker_origem_fireads`**, conforme a seção 6. A denominação
inicial `worker_canal_fireads` fica substituída por esse nome; não se trata de
dois workers diferentes. Na fase de planejamento a autorização era apenas
documentar; a aplicação local foi autorizada em 24/10/2026.

**Confirmação do usuário em 23/10/2026:** aprovados o nome, a rotina periódica,
o tratamento de novas conversas e pendências e a concentração do detalhamento
opcional em “Origem dos atendimentos”. A aplicação deve incluir obrigatoriamente
a documentação das responsabilidades de **todos os workers**, atualizando os
documentos existentes conforme a seção 6.6.

**Refinamento de elegibilidade em 23/10/2026:** o worker periódico cobre somente
conversas cuja abertura completa dispensou a consulta inicial e que ainda não
chegaram à elegibilidade de envio ao Funil. Não é um recuperador geral de toda
origem ausente. A preparação posterior pelo `worker_funil` continua consultando
e tem prioridade para confirmar/corrigir canal e anúncio, conforme a seção 6.

**Revisão final aprovada em 23/10/2026:** executar a cada **duas horas**,
com orçamento de **300 segundos por consulta**. Esperar a abertura terminar;
consulta inicial realizada, mesmo com falha, não torna a conversa elegível ao
novo worker. Ausência de canal/anúncio na linha é falta de informação, não falha
de consulta. Distinguir leitura concluída de origem identificada, evitando
reconsultas por campo vazio. Anúncios são considerados somente para Google Ads
e Meta Ads. Pendência por erro deixa de ser processada se o Funil assumir ou
resolver a identificação antes da próxima tentativa. Detalhes na seção 6.

Manter o bloco geral de perfis: ele mostra o público da unidade; o detalhamento
por origem explica qual público chega por cada canal ou referência de anúncio.
Não acrescentar uma nova seção à navegação principal do painel.

## 2. Comportamento atual confirmado no código

### 2.1. Dois momentos para identificar a origem

- Todas as unidades podem aproveitar os dados válidos da mensagem inicial.
- Nas unidades integradas à FireAds, a consulta inicial é necessária quando falta
  algum dado essencial aceito: nome, e-mail ou para quem é o atendimento.
- Nas unidades sem link de agendamento, o turno é o quarto dado essencial.
  Ter os outros três não basta para dispensar a consulta se o turno está ausente.
- Se todos os dados necessários já foram aceitos, a consulta inicial é dispensada.
  A origem fica pendente para o monitoramento; o canal provisório usado internamente
  não comprova que o atendimento seja orgânico ou venha de uma campanha.
- Quando ocorre a consulta inicial e existe uma resposta válida, ela também permite
  identificar o canal. A ausência comprovada de registro elegível permite a
  classificação orgânica conforme as regras atuais; falha de consulta não comprova ausência.
- Se a origem não foi identificada na abertura, a rotina atual volta à planilha
  na **preparação da entrega** dos atendimentos elegíveis ao dashboard/Funil.

Precisão importante: identificar a origem na preparação da entrega não exige
que o POST no dashboard já tenha sido confirmado. A leitura pode ter funcionado
e a escrita ainda estar pendente. “Origem identificada”, “enviado ao dashboard”
e “enviado ao Funil” são estados distintos.

A elegibilidade é a regra já configurada nas etapas do projeto, não um novo
número fixo de etapa introduzido por este recurso. O Funil continua dependendo
da confirmação da entrega ao dashboard nas unidades integradas.

### 2.2. O que “ainda sem origem” realmente significa

É a quantidade de **atendimentos sem atribuição válida disponível ao relatório**,
não uma medida de abandono. Exemplos possíveis:

- Mensagem inicial completa e atendimento ainda não elegível para entrega.
- Atendimento em andamento, consulta pendente ou preparação da entrega ainda não executada.
- Consulta com falha, indisponibilidade ou prazo excedido, sem confirmação posterior.
- Atendimento antigo sem evidência suficiente preservada para determinar a origem.

Um cliente que informou tudo e não prosseguiu é um caso possível, mas não é a
explicação de todos os registros. Não afirmar que todo atendimento sem origem
abandonou a conversa nem deduzir esse motivo apenas pela ausência de atribuição.

No exemplo apresentado pelo usuário, 17 atendimentos identificados mais 4 sem
origem correspondem a 21 atendimentos. Os 19 contatos únicos são outra contagem:
um mesmo contato pode participar de mais de uma conversa.

### 2.3. Anúncio e perfil atualmente disponíveis

- A leitura do anúncio usa a chave **`Anuncio`** da linha FireAds. A apresentação
  do dashboard pode chamá-la de “Anúncio (criativo)”.
- `core/integrations/fireads/atribuicao.py` hoje captura e apresenta anúncio
  exclusivamente para o canal Meta Ads, inclusive na compatibilidade histórica.
- `callback/monitoramento/origens.py` agrega anúncios exclusivamente da Meta.
  Acrescentar uma tabela Google na tela, sozinho, não resolveria essa limitação.
- A existência de um registro Google Ads com “Escola de memoria” em anúncio foi
  informada pelo usuário. Confirmar esse campo em resposta real da API na futura
  implementação, sem criar registros de teste no dashboard.
- Origem, destinatário e idades já possuem dados usados pelo projeto, mas os
  agrupamentos de origem e perfil atualmente são separados.
- A idade do titular usada no relatório vem do cadastro atual do cliente.
  O painel já informa que utiliza faixas atuais. A idade do dependente vem do
  cadastro vinculado à conversa.

## 3. Relevância e apresentação dos perfis

O cruzamento deve responder: **“Que público este canal ou anúncio trouxe e
quantos desses atendimentos foram enviados ao Funil?”**

Isso complementa o panorama geral e ajuda a avaliar se o público atendido
corresponde ao público pretendido pela divulgação. Não mede todos os formulários
preenchidos, alcance, cliques, investimento, vendas ou retorno financeiro.

### 3.1. Organização visual proposta

- Concentrar esse detalhamento no cartão **“Origem dos atendimentos”**.
- Manter os resumos e as tabelas de canais e anúncios visíveis como hoje.
- Acrescentar a ação discreta **“Ver perfis”** em cada canal e grupo de anúncio.
- Abrir um painel lateral reutilizável com o nome da seleção, período, totais
  e uma tabela **Perfil | Atendimentos | No Funil**.
- Permitir apenas um painel de detalhamento aberto por vez. Em telas pequenas,
  adaptar o painel à largura disponível sem provocar rolagem horizontal na página.
- Usar “Titular” e “Dependente” por extenso. Não exigir que o usuário conheça “DP”.
- Manter os dois grupos de anúncios recolhíveis, Meta primeiro e Google depois.
- A atualização automática deve preservar o painel selecionado e os grupos abertos.
  A troca de período deve atualizar conteúdo e título juntos; não exibir detalhes
  antigos sob um período novo. Se não houver dados, mostrar um estado vazio claro.
- Garantir operação por clique, toque e teclado, fechamento por Escape, nome
  acessível, foco visível e retorno do foco à ação que abriu o detalhamento.

Não colocar cinco ou mais colunas de perfil na tabela principal nem repetir
todos os gráficos em cada linha. A primeira versão deve favorecer quantidades
exatas, sem rankings automáticos de “melhor anúncio” baseados em amostras pequenas.

#### Escolha do cartão e hierarquia

| Cartão | Pergunta principal | Papel nesta evolução |
| --- | --- | --- |
| Origem dos atendimentos | Qual canal ou anúncio trouxe cada público? | Local do detalhamento de perfis por canal e anúncio |
| Perfil dos atendimentos | Qual é o público atendido pela unidade? | Manter visão geral, sem repetir a árvore de canais e anúncios |
| Consulta de faixa etária personalizada | Quantos participantes atendem ao recorte de idade escolhido? | Manter consulta específica, sem acrescentar navegação de campanhas |

O cartão de origens já conta conversas. A consulta personalizada deduplica
titulares e conta cadastros de dependentes; o perfil geral também possui
indicadores por contato. Acrescentar a mesma hierarquia nesses cartões poderia
dar a impressão de que os números têm a mesma base, quando não têm.

No cartão de origens, o canal e o anúncio são dois pontos de entrada diretos:

- **Canal → Ver perfis:** apresenta todos os perfis daquele canal no período.
- **Anúncio → Ver perfis:** apresenta somente os perfis daquele anúncio no período.

Não exigir que o cliente abra o canal, depois um anúncio e depois outro nível
de perfis. Os anúncios permanecem nos dois grupos já previstos abaixo dos canais.
O painel lateral é o mesmo para ambas as entradas, sem subpainéis encadeados.
Se futuramente houver necessidade de partir de um perfil, considerar um atalho
para esse detalhamento, em vez de duplicar a estrutura nos três cartões.

#### Padrão visual e validação obrigatória na implementação

- Manter tipografia, cores, espaçamentos e bordas do painel existente.
- No painel lateral, apresentar nesta ordem: canal/anúncio selecionado, período,
  totais de atendimentos e Funil, tabela de perfis e nota curta sobre faixas atuais.
- Usar alinhamento consistente para os números e indicar os valores por texto;
  cor e barras são complementos, não a única forma de leitura.
- Não ocupar espaço com várias linhas de valor zero; categorias incompletas
  com atendimentos devem permanecer visíveis para explicar o total.
- Nomes longos de anúncios devem quebrar linha ou ter acesso ao texto completo,
  sem esconder a ação “Ver perfis” nem cortar as contagens.
- Validar visualmente em desktop e celular: poucos e muitos anúncios, nomes
  longos, valores grandes, ausência de dados, perfis incompletos e mudança de período.
- Conferir teclado, foco e rolagem no painel lateral; em celular, o fechamento
  deve continuar acessível. Não acumular rolagem horizontal e vertical em tabelas.

A aparência deve ser conferida na implementação com a interface renderizada.
O registro destes critérios no plano não equivale a uma validação visual já feita.

### 3.2. Regras de contagem e classificação

1. Cada `id_conversa` deve contar uma única vez em seu canal e, quando aplicável,
   uma única vez no grupo de anúncio desse canal. Relacionamentos com mensagens,
   dependentes ou tentativas de envio não podem multiplicar atendimentos.
2. Usar as mesmas conversas elegíveis do período do bloco de origens atual.
   Não reduzir os relatórios à última conversa; essa regra é dos filtros de chats.
3. “No Funil” exige envio confirmado da **mesma conversa**, no período consultado.
   Conclusão da triagem ou envio de outra conversa do mesmo cliente não substituem isso.
4. Classificar a pessoa que fará o treinamento. Se uma filha procura atendimento
   para a mãe de 65 anos, o perfil é **Dependente · 60+**, independentemente da idade da filha.
5. Reutilizar as faixas e limites atuais. Apresentar separadamente casos fora da
   faixa atendida, quando presentes, em vez de removê-los silenciosamente do total.
6. Não interpretar um `status_dependente=False` inicial como escolha confirmada
   do titular. Reaproveitar o critério de confirmação já usado nas conversas.
7. Preservar categorias incompletas: **Titular · idade não informada**,
   **Dependente · idade não informada** e **Perfil não informado**. Idade inválida
   não deve virar zero nem assumir a idade de outra pessoa do cadastro.
8. As categorias são mutuamente exclusivas e sua soma deve fechar com os totais
   de atendimentos e de Funil da linha selecionada. Contatos únicos não devem
   ser somados como se fossem atendimentos.
9. Anúncio ausente em uma origem confirmada permanece no respectivo canal e
   participa do grupo **“Anúncio não informado”** desse canal.

Proposta inicial para idade: manter **faixas atuais**, deixando isso explícito
no detalhamento. Fotografar a idade na época de cada atendimento é uma evolução
separada, que exige decidir armazenamento e tratamento dos registros antigos.
Não prometer fidelidade histórica que o cadastro atual não fornece.

## 4. Informação sobre origem ainda não identificada

### 4.1. Local e interação

Colocar um botão de informação **“i” junto ao número/rótulo “ainda sem origem”**,
deixando claro a qual indicador ele se refere. O destaque no print também sugere
o cabeçalho do cartão, mas o indicador é a posição preferencial desta proposta.
Evitar duplicar a mesma explicação nos dois lugares.

Abrir uma pequena caixa de ajuda ao passar o mouse ou focar o botão; permitir
abrir e fechar por clique/toque. Não depender apenas de hover ou do atributo
HTML `title`. A caixa deve permitir leitura sem desaparecer ao mover o ponteiro
para o texto, fechar por Escape e não ser cortada pelos limites do cartão.

### 4.2. Texto proposto para o usuário do painel após ativar o worker periódico

**Por que alguns atendimentos ainda estão sem origem?**

> Quando o cliente já informa os dados necessários na primeira mensagem, o
> chatbot começa o atendimento sem consultar a planilha da FireAds. Isso evita
> uma espera desnecessária pela primeira resposta.
>
> Se faltar algum dado, o chatbot consulta a planilha para tentar aproveitá-lo
> e evitar perguntas repetidas. Nessa consulta, também pode identificar de onde
> o cliente veio.
>
> Quando a consulta inicial é dispensada, uma verificação automática a cada
> duas horas procura a origem dos novos atendimentos, mesmo que o cliente não tenha
> concluído a conversa. A origem também pode ser identificada na preparação
> do envio ao dashboard.
>
> Até essa verificação ser concluída, o atendimento pode aparecer aqui como
> “sem origem”. Em caso de falha ou acúmulo de consultas, a identificação pode
> levar mais tempo.
>
> Esse número também pode incluir consultas pendentes, falhas ou registros
> sem canal preenchido na planilha, além de atendimentos antigos sem informação
> suficiente. Estar sem origem não significa,
> necessariamente, que o cliente abandonou o atendimento.

Nota curta opcional, caso necessária na mesma ajuda:

> Os dados necessários são nome, e-mail e para quem é o atendimento. Nas
> unidades sem link de agendamento, também é necessário informar o turno.

A explicação deve permanecer factual: reduzir espera é a intenção do fluxo,
mas não foi medida uma redução de abandono. Não apresentar esse efeito como
um resultado comprovado nem dizer que todas as origens serão identificadas.
Só publicar a referência à verificação periódica quando o novo processo estiver
efetivamente implantado e ativo. Se o painel for implantado antes, explicar os
dois momentos atuais descritos na seção 2, sem anunciar uma rotina inexistente.

## 5. Anúncios do Google Ads

### 5.1. Captura, persistência e compatibilidade

- Ampliar a captura e a leitura de `Anuncio` para **Meta Ads e Google Ads**,
  aproveitando as consultas de abertura, de preparação da entrega e do novo
  worker periódico. As três rotinas devem compartilhar as regras de atribuição.
- Utilizar a linha escolhida pelas regras atuais: mesmo telefone, todas as
  representações equivalentes já suportadas, somente os quatro canais de
  formulário válidos, prioridade de data e desempate por linha conforme o seletor.
- Preservar no contexto da própria conversa o canal, a referência de anúncio,
  o momento da captura e a referência do registro selecionado.
- Reutilizar `contexto_fireads.atribuicao_monitoramento`; o formato JSON atual
  já comporta um anúncio associado ao canal Google. Não há necessidade identificada
  de uma nova coluna só para distinguir os dois canais.
- Manter o tratamento de JSONB como texto ou objeto que foi corrigido na V1.16.1.
- Não tornar `Anuncio` obrigatório para iniciar atendimento ou enviar ao dashboard.
  Campo vazio ou ausente corresponde a anúncio não informado.
- Ler e agrupar anúncio apenas para **Google Ads e Meta Ads**, na mesma linha
  já consultada para o canal. Nos demais canais, ignorar esse campo mesmo que
  preenchido; não fazer consultas adicionais para procurar anúncio.
- Não inferir a referência a partir de observações, nome do cliente, código do
  Funil ou semelhança de nomes. Não misturar anúncios de Google e Meta com texto igual.
- Normalizar apenas espaços externos/repetidos para agrupamento; não juntar nomes
  diferentes por comparação aproximada. Renderizar conteúdo externo como texto.

“Escola de memoria” pode ser uma referência usada pela FireAds. Não afirmar que
é um ID oficial de anúncio, campanha ou palavra-chave do Google sem confirmar
o significado desse campo. O relatório pode manter o título **“Anúncio / referência”**.

### 5.2. Tabela e dados antigos

Apresentar **“Anúncios do Google”** logo após Meta, com:

- Anúncio/referência;
- Atendimentos;
- No Funil;
- Ação opcional “Ver perfis”.

Sem atendimento Google no período, apresentar mensagem de ausência de dados.
Com atendimento Google e sem anúncio, usar “Anúncio não informado”. Os grupos
de anúncio de cada canal devem fechar com os totais desse canal.

Capturas antigas podem ter descartado o anúncio Google, mesmo que ele estivesse
preenchido na planilha. O novo código não recupera automaticamente essa informação.
Uma recuperação histórica só pode usar evidência já salva da mesma linha e
conversa; caso ela não exista, manter “Anúncio não informado”. A implementação
deve avaliar também registros com atribuição já salva, pois o caminho histórico
atual não é acionado automaticamente quando esse objeto está presente.

Consultar a planilha atual para completar o passado é outra decisão: uma linha
nova ou editada pode não representar a campanha do atendimento antigo. Não
reescrever snapshots de entregas em andamento nem repetir envios para corrigir métricas.

## 6. Worker de origem FireAds: execução periódica definida

### 6.1. Nome e responsabilidade

**Nome aprovado: `worker_origem_fireads`.** “Origem” abrange canal de venda e
referência de anúncio; “FireAds” identifica a fonte consultada. Usar esse nome
de forma consistente nos diretórios, inicializador, serviço, logs e documentação.

Padronização aprovada para a futura implementação:

- Diretório: `workers/worker_origem_fireads/`.
- Inicializador: `iniciar_worker_origem_fireads.py`.
- Serviço: `chatbot-worker-origem-fireads.service`.
- Identificação nos logs: `worker.origem_fireads`.
- Descrição operacional: **“Identifica canais e anúncios FireAds dos atendimentos”**.

Inventário conferido no projeto: **cinco workers e um serviço web**. O novo
processo resultará em seis workers e um serviço web, sem contar processos
internos do Gunicorn como serviços independentes.

| Processo | Responsabilidade |
| --- | --- |
| `chatbot-webhook` | Receber eventos do WhatsApp e servir o monitoramento |
| `worker_flow` | Validar e conduzir o atendimento, enviando as respostas |
| `worker_consulta_dash` | Consultar a FireAds para complementar dados necessários no início do atendimento |
| `worker_funil` | Entregar dados ao dashboard e ao Funil, incluindo preparação e recuperação de envios |
| `worker_followup` | Enviar lembretes conforme as regras de acompanhamento |
| `worker_consumo_meta` | Coletar informações de consumo de mensagens da Meta |
| `worker_origem_fireads` — proposto | Identificar canal e anúncio para as métricas, sem depender da conclusão do atendimento |

Não renomear os processos existentes como parte desta mudança. Atualizar o
inventário de serviços e as instruções de operação quando o novo for aplicado.

### 6.2. Elegibilidade e ciclo de duas horas — regra refinada pelo usuário

A cada **duas horas**, selecionar por conversa/unidade todos os itens ainda
pendentes dentro do recorte de ativação que satisfaçam simultaneamente:

1. Unidade com integração FireAds aplicável, ativa e contrato válido, respeitando
   as condições existentes de pagamento e configuração.
2. **Abertura já concluída e aplicada:** o flow confirmou que a primeira mensagem
   continha os três campos necessários, ou os quatro para unidade sem link.
3. **Consulta inicial dispensada:** nenhuma solicitação de consulta inicial
   pertence à conversa. Consulta pendente, concluída ou com erro não é dispensa.
4. A conversa **não está elegível para o envio ao Funil** pelas regras atuais e
   não possui envio dashboard/Funil já materializado ou confirmado.
5. Ainda não existe atribuição de origem confirmada para essa conversa.
6. O worker de origem ainda não concluiu uma leitura válida para essa conversa.
   Leitura concluída com canal não informado também encerra esse trabalho,
   sem transformar o atendimento em orgânico e sem forçar novas consultas.

Não basta `NOT EXISTS consulta_fireads`: uma abertura recém-criada pode ainda
não ter chegado ao ponto de solicitar a consulta. O código atual registra a
dispensa no contexto aplicado com `concluida=true`, `id_consulta=null` e motivo
`canal_pendente_entrega`, além de `contexto_coleta.status=pronto`. A seleção e a
gravação devem verificar evidência consistente da abertura, sem criar esse estado
pelo worker de origem. Conferir o vínculo dos contextos à própria conversa.

Não codificar “etapa diferente de 19” como definição universal. O envio atual
combina `etapa.elegivel_funil` com a configuração de link: sem link, etapa 19 ou
etapas a partir de 21; com link, etapas a partir de 20, sempre com a flag da etapa.
Compartilhar o critério de elegibilidade de etapa/configuração para não divergir.
Etapas posteriores ou envios já existentes não devem recolocar a conversa no
worker periódico só porque ela deixou a etapa que mostrou o contato do consultor.

Uma conversa interrompida ou encerrada antes da elegibilidade pode ser consultada
se cumprir os demais requisitos; não impor `status_ativa=true` indiscriminadamente
e perder justamente os atendimentos que não prosseguiram. Um novo atendimento de
telefone conhecido tem sua própria elegibilidade e atribuição.

**Recuperação proposta, sem fila adicional obrigatória:** em cada ciclo, buscar
novamente os itens que continuam satisfazendo essas condições, sem restringir a
busca às últimas duas horas ou a IDs maiores que o último visto. O próprio estado durável
da conversa indica a pendência. Quem teve erro continua sem origem e reaparece
no ciclo seguinte, se ainda elegível. Quem teve leitura concluída, foi identificado
por outra rotina ou ficou elegível ao Funil sai da seleção. Não criar uma fila
separada só para descartar esses itens: a seleção atualizada já os exclui.

Agrupar por integração/aba, deduplicar telefones para a leitura e reaproveitar uma
resposta completa e válida para vários contatos. Processar em lotes limitados,
com paginação/ordem que não deixe erros antigos monopolizarem o trabalho. Manter
o marco de ativação persistente/configurado, sem recalculá-lo a cada reinício;
não executar recuperação de todo o histórico sem decisão separada.

Aplicar os seletores existentes: variações de telefone, quatro canais válidos,
data mais recente e desempate por linha. Para Google/Meta, obter `Anuncio` da
mesma linha e salvar canal, anúncio, referência, momento e data da captura.
Consultar todas as representações suportadas antes de concluir ausência. Os
quatro canais são **Meta Ads, Google Ads, Chat Fire e Orgânico Site**; uma linha
100% orgânica, Indicação ou Lead Franqueador não é um formulário elegível.

**Revalidar antes da consulta e antes de gravar em uma operação curta no banco.** Se durante
o HTTP a conversa ficar elegível ao Funil, ganhar envio ou atribuição confirmada,
descartar a gravação periódica. A próxima rotina responsável assume a identificação.
Isso também vale para uma tentativa que falhou no ciclo anterior: se o Funil
resolveu antes da nova rodada, ela não deve ser consultada novamente.

O worker **não envia WhatsApp, não muda respostas/etapas ou dados de atendimento,
não cria/atualiza linhas no dashboard e não torna a conversa elegível ao Funil**.
Os relatórios continuam lendo apenas o banco.

Usar exclusão entre instâncias/ciclos do próprio worker, sem manter transação ou
lock de linha aberto durante HTTP. Duas horas é o intervalo entre ciclos; falhas ou
acúmulo podem ampliar o prazo. No reinício, a seleção por estado recupera o que
continua pendente, incluindo conversas confirmadas tardiamente no banco.

**Prazo de consulta:** reutilizar o orçamento existente de **300 segundos** e
conferir a configuração efetiva do cliente HTTP, incluindo redirecionamentos e
retries, para não multiplicar esse orçamento silenciosamente. Não reduzir o
prazo por haver vários contatos no lote. Não iniciar um ciclo concorrente se
o anterior ainda estiver em execução. O prazo maior não elimina timeouts: caso
aconteçam, registrar falha e manter a pendência para o próximo ciclo, nunca
tratar a interrupção como número ausente ou origem orgânica.

#### Resultado da leitura e conclusão do trabalho

**Consulta concluída não significa necessariamente origem identificada.**
Aplicar esta classificação após uma resposta completa e válida:

| Situação na planilha para o telefone | Resultado para métricas | Próxima ação do worker de origem |
| --- | --- | --- |
| Registro de um dos quatro canais de formulário | Confirmar o canal da linha elegível mais recente | Concluir e não repetir |
| Google/Meta com anúncio preenchido | Confirmar canal e referência do anúncio | Concluir e não repetir |
| Google/Meta sem anúncio | Manter canal confirmado e agrupar como “Anúncio não informado” | Concluir e não repetir por falta de anúncio |
| Nenhuma linha do telefone, após todas as variantes | Confirmar 100% orgânico com base nessa leitura | Concluir e não repetir |
| Somente linhas com canais conhecidos fora dos quatro de formulário, como Orgânico, Indicação ou Lead Franqueador | Confirmar 100% orgânico pela regra aprovada | Concluir; não criar nem alterar linha externa |
| Não há formulário elegível, mas existe linha do telefone com canal vazio ou valor não reconhecido | Manter origem não identificada; registrar motivo da informação insuficiente | Concluir a verificação, sem erro e sem reconsulta automática por campo vazio |
| Erro HTTP, timeout, resposta inválida ou leitura incompleta | Não atribuir origem | Deixar pendente para o próximo ciclo se ainda elegível |

Se houver uma linha válida de formulário, ela tem prioridade conforme o seletor;
linhas extras de canal vazio não invalidam essa correspondência. Se não houver
formulário válido e existir canal indefinido, não deduzir orgânico a partir da
informação insuficiente. “Não encontrou registro elegível” significa não
encontrar uma linha do mesmo telefone em um dos quatro canais aceitos; para
confirmar orgânico, a leitura também deve permitir descartar canal indefinido.

Distinguir **célula vazia** de **resposta impossível de interpretar**. Canal não
preenchido em uma linha não é erro; uma resposta sem os cabeçalhos essenciais
para localizar telefone/canal, ou incompleta, não comprova uma consulta válida.
`Anuncio` é opcional: ausência desse campo não impede confirmar Google/Meta.

Persistir um marcador pequeno e versionado no JSON já aplicado à conversa,
por exemplo `contexto_fireads.verificacao_origem`, com `versao`, `id_conversa`,
`status=concluida`, resultado/motivo, momento da consulta, integração/aba e
referência da linha quando disponível. Não duplicar o conteúdo completo da
planilha. Gravar esse marcador e a atribuição, quando houver, atomicamente.
Usar o marcador também para leituras concluídas sem canal; isso distingue dado
ausente de tentativa que falhou, sem exigir tabela de fila.

A atribuição confirmada permanece em `atribuicao_monitoramento`. Um marcador
de verificação sem canal **não** é uma atribuição orgânica: o leitor do painel
deve manter o atendimento em “ainda sem origem” e não inferir canal pelo fallback
legado. Preservar o tratamento JSONB texto/objeto e as demais chaves existentes.
Nunca inicializar o JSON durante a abertura. A conclusão dessa verificação
não dispensa a confirmação futura pelo Funil, nem interfere em seus snapshots.

Reutilizar normalização, equivalência de telefones e ordenação existentes, mas
manter explícita a diferença entre leitura de métricas e autorização de escrita.
Hoje `selecionar_entrega` rejeita canal desconhecido para proteger a entrega;
não relaxar essa validação globalmente para implementar a leitura sem canal.
O novo worker deve classificar a informação insuficiente no seu caminho de
leitura, preservando as proteções de escrita do dashboard/Funil.

### 6.3. Anúncios novos e anúncios existentes

Um anúncio já conhecido aumenta os totais do grupo correspondente; uma nova
referência cria um novo grupo no relatório. Essa distinção decorre do agrupamento
dos dados salvos, sem necessidade de criar anúncio ou consultar plataforma de mídia.

A identidade do grupo deve considerar **unidade + canal + referência normalizada**.
Mesmo texto em Google e Meta não representa o mesmo grupo. Nenhuma operação
dessa rotina deve criar campanhas ou anúncios externos.

Com o escopo refinado, **não consultar repetidamente uma origem já confirmada
somente porque o anúncio está vazio**. Guardar “Anúncio não informado”. Se a
conversa avançar, a preparação do Funil volta a ler e pode completar/corrigir
canal e anúncio. Uma rotina específica de enriquecimento de anúncio não faz
parte desta primeira versão.

### 6.4. Regras de segurança dos dados e recuperação

- **Sem perda de janela:** selecionar por estado pendente, dentro do recorte
  fixo de ativação. Não usar “desde a última execução” como corte exclusivo;
  isso preserva falhas anteriores e confirmações tardias sem uma fila adicional.
- **Sem histórico indiscriminado:** a primeira ativação precisa de um marco
  explícito. A definição atual cobre novos atendimentos e pendências acumuladas
  desde a ativação. Reprocessar todo o passado exige decisão separada.
- **Sem falso orgânico por erro:** timeout, erro de autenticação, cabeçalhos
  inválidos ou leitura incompleta mantêm pendência. Somente uma leitura válida
  pode comprovar ausência de linha elegível. Linhas orgânicas ou de canais manuais
  não comprovam origem em formulário.
- **Ausência de registro:** proposta para a primeira versão: reutilizar a regra
  atual de atribuição orgânica quando uma leitura completa e válida confirma que
  não há nenhum registro elegível nem canal indefinido, conforme a tabela da
  seção 6.2. Canal vazio/desconhecido não comprova ausência e não é erro técnico;
  concluir a verificação sem atribuir canal nesse caso.
  Essa regra não presume que a planilha nunca mudará; se o formulário surgir
  depois, a preparação posterior do Funil poderá corrigir a origem. Sem avanço,
  não há reconsulta automática de uma leitura já concluída nesta versão. Uma
  carência especial para inserção tardia fica fora deste desenho simples.
- **Sem duplicidade de trabalho:** impedir instâncias/ciclos simultâneos do
  próprio worker e tornar a gravação condicional/idempotente por conversa.
  Não manter transação aberta durante HTTP nem alterar os locks de atendimento.
- **Sem sobrescrita concorrente:** uma consulta inicial ou entrega que confirme
  a origem enquanto o novo worker consulta prevalece sobre sua gravação tardia.
  Atualizar somente os campos necessários, preservando o restante do JSON.
- **Sem alterar entregas congeladas:** a atribuição de métricas não pode modificar
  snapshots de envios preparados nem reenviar ao dashboard/Funil. A preparação
  comercial mantém a decisão congelada e a consistência dos dois destinos.
- **Prioridade aprovada:** a preparação posterior pelo `worker_funil` confirma
  novamente canal e anúncio; seu resultado substitui o do worker periódico no
  relatório. Canal igual não significa anúncio necessariamente igual: ambos
  devem ser avaliados. Preservar a captura anterior como evidência, sem duplicar
  a contagem da conversa. Depois de congelar a entrega, as retentativas seguem
  a decisão congelada; não gerar uma decisão nova a cada falha de envio.
- **Evidência temporal:** registrar o momento da leitura. A linha atual informa
  o que foi encontrado naquele momento; não prova, sozinha, a campanha histórica
  de todos os atendimentos daquele telefone.
- **Isolamento:** um mesmo número em duas unidades tem trabalhos distintos.
  Exclusão de contato deve incluir qualquer fila/estado introduzido pelo worker.

### 6.5. Detalhes técnicos a fechar na implementação

**Revisão após o refinamento do usuário:** a elegibilidade restrita e a prioridade
do Funil estão definidas. A proposta técnica fica mais simples: varredura de
conversas pendentes por estado e retentativa no próximo ciclo após falha, sem
obrigatoriedade de fila nova ou enriquecimento contínuo de anúncio vazio.

Ainda é necessário implementar a seleção, a exclusão de ciclos simultâneos,
a revalidação atômica e a paginação dos lotes. Dimensionar o trabalho com o
orçamento atual de HTTP de 300 segundos por consulta e conferir os índices.
Essas escolhas não mudam a elegibilidade aprovada nem exigem novos estados na
fila de mensagens ou na consulta inicial.

Registrar métricas de itens descobertos, identificados, leituras concluídas sem
canal, anúncios não informados de Google/Meta, já resolvidos por outra rotina,
pendentes, não encontrados e falhas, além da duração dos ciclos. Proteger
dados pessoais e credenciais nos logs. Erros não contam como consultas concluídas
nem alteram a origem para orgânico. Falhas persistentes devem ficar observáveis,
sem uma sequência de retries imediatos dentro do mesmo ciclo.

A nova regra não demonstra necessidade obrigatória de tabela/colunas. Se a
implementação identificar necessidade de índice ou outra estrutura, fornecer
a migração específica no deploy. A implementação continua aguardando aplicação.

### 6.6. Documentação obrigatória das responsabilidades de todos os workers

**Requisito explícito do usuário:** ao aplicar este plano, documentar claramente
a responsabilidade de cada worker do projeto, não apenas do novo. Já existem
`workers/README.md`, `PADROES_DE_ARQUITETURA.md` e `deploy/README.md`; priorizar
a atualização dessas referências, evitando criar um manual paralelo divergente.

Organização das referências:

- **`workers/README.md`:** manter o inventário central, a visão rápida de
  responsabilidades e o funcionamento de cada worker, incluindo o novo.
- **`PADROES_DE_ARQUITETURA.md`:** atualizar fronteiras entre componentes,
  dependências, propriedade das filas/transações e coordenação entre processos.
- **`deploy/README.md`:** atualizar serviços instalados, ativação, configuração,
  verificação de funcionamento, consulta de logs e procedimentos de operação.

Os documentos devem se referenciar para evitar repetição extensa. Se surgir
necessidade real de um documento específico, vinculá-lo ao inventário central.
Revisar também a árvore de diretórios, os totais de serviços e descrições antigas
que ficaram incompletas com a inclusão dos workers mais recentes. Preservar
notas históricas identificadas como tal, sem apresentá-las como inventário atual.

Para cada worker, registrar no mínimo:

1. **Nome e identificação:** diretório, inicializador, serviço e identificação
   dos logs, usando os nomes realmente adotados pelo projeto.
2. **Finalidade e limites:** o que faz e quais responsabilidades pertencem a
   outro processo, para não confundir consulta, atendimento, métricas e entrega.
3. **Entrada e execução:** eventos/filas que consome, critérios de elegibilidade,
   frequência, lote e configurações que governam a execução.
4. **Resultados e efeitos:** o que grava no banco/cache, quais serviços externos
   consulta e quais mensagens ou registros externos pode enviar/alterar.
5. **Coordenação:** quais outros processos produzem ou consomem seus resultados,
   condições de passagem e formas de evitar processamento concorrente indevido.
6. **Falhas e recuperação:** prazos, reservas, retentativas, retomada após reinício
   e comportamento quando uma integração está indisponível.
7. **Operação:** como iniciar, parar, reiniciar, verificar estado e consultar logs,
   com os cuidados específicos quando houver trabalho em andamento.

Destacar especialmente a separação entre `worker_consulta_dash` (complementação
da abertura), `worker_origem_fireads` (origem/anúncio para métricas) e
`worker_funil` (entrega dashboard/Funil). Incluir também flow, follow-up e consumo
Meta. Identificar o webhook/monitoramento como serviço web, sem confundi-lo com
mais um worker de aplicação.

Os valores operacionais devem ser conferidos no código e nos serviços da versão
implementada. Não inventar intervalos, variáveis de configuração ou garantias de
recuperação, nem expor credenciais na documentação. A revisão documental faz
parte da entrega: **não considerar o plano concluído com o worker funcionando
e o mapa de responsabilidades desatualizado.**

## 7. Mapa de futura implementação

| Área | Trabalho previsto |
| --- | --- |
| `core/integrations/fireads/atribuicao.py` | Capturar/ler anúncio Google, mantendo compatibilidade e evidência por conversa |
| `core/repositories/monitoramento/painel.py` | Fornecer perfil confirmado e idades para cruzar com origens, sem duplicar conversas |
| `callback/monitoramento/origens.py` | Agregar perfis por canal e por anúncio, separando Google e Meta |
| `callback/monitoramento/services.py` | Compor os dados do detalhamento e preservar os critérios existentes de período |
| `callback/monitoramento/static/monitoramento/js/painel.js` | Ajuda de origem, painel opcional de perfis e grupo de anúncios Google |
| `callback/monitoramento/static/monitoramento/css/painel.css` | Aparência e comportamento responsivo dos novos elementos |
| `workers/worker_origem_fireads/` — a criar | Rotina periódica independente para canal e anúncio dos novos atendimentos e pendências |
| Repositório do worker de origem — a criar | Seleção por estado elegível, paginação, exclusão entre ciclos e gravação condicional por conversa |
| `deploy/systemd/chatbot-worker-origem-fireads.service` — a criar | Serviço com nome, cadência e responsabilidade documentados |
| Testes de origens, painel e integração PostgreSQL | Conferir contagens, JSON, períodos, isolamento por unidade e compatibilidade histórica |
| Testes da rotina periódica | Reinício, pendências, concorrência, telefones equivalentes, atraso de formulário e ausência de efeitos externos de escrita |
| `workers/README.md`, `PADROES_DE_ARQUITETURA.md` e `deploy/README.md` | Atualizar obrigatoriamente responsabilidades de todos os workers, fronteiras, inventário e operação, conforme seção 6.6 |

As funções puras de classificação devem compartilhar as regras existentes,
evitando versões diferentes de faixa/perfil para o resumo e o detalhamento.
Os filtros de Conversas continuam representando a última conversa no período;
este recurso não modifica essa regra nem o fluxo de atendimento.

Para os três recursos de relatório, usando faixas atuais, **não foi identificada
necessidade de migração SQL**. Confirmar na implementação. Com a seleção por
estado, o worker periódico não exige uma fila própria por definição. Avaliar
índices e eventual estrutura adicional e fornecer SQL somente se necessário.
Um histórico de idades continua sendo uma evolução separada.

## 8. Critérios de aceitação para a futura aplicação

- Totais de perfis fecham com os de cada canal/anúncio, incluindo não informados.
- Um cliente com duas conversas pode contar em dois canais e perfis; não transferir
  o envio ao Funil de uma conversa para outra.
- A idade usada no atendimento de dependente é a do dependente, não a do titular.
- Destinatário ainda não confirmado não é classificado como titular por padrão.
- Google com anúncio preenchido, vazio ou ausente funciona; o mesmo texto em
  Google e Meta gera grupos independentes.
- JSONB em texto, objeto e registros antigos continuam sendo lidos sem quebrar
  Conversas ou Relatórios. Sem evidência suficiente, o dado permanece desconhecido.
- Os períodos, permissões e limites de unidade são respeitados também no detalhamento.
- Unidades sem integração não passam a receber blocos FireAds nem consultas externas.
- Ajuda funciona por mouse, teclado e toque; o texto não equipara “sem origem” a abandono.
- Interface legível no computador e celular, sem excesso de tabelas abertas,
  sem perda de seleção em atualização automática e sem detalhes de período antigo.
- Nenhuma chamada adicional à FireAds ao abrir o relatório ou o detalhamento.
- A consulta periódica não bloqueia atendimento nem entrega e não exige que a
  conversa tenha alcançado elegibilidade para o Funil.
- A consulta periódica exige abertura concluída com consulta inicial dispensada;
  uma consulta inicial com falha não torna a conversa elegível para esse worker.
- Conversas elegíveis ao Funil ou com envio já materializado ficam fora da rotina
  periódica; conferir as diferenças de etapa entre unidades com e sem link.
- Reinício/falha não perde pendências; nova conversa de telefone conhecido é
  examinada sem multiplicar consultas por telefone no mesmo lote/unidade.
- Consulta inicial ou entrega concluída durante a leitura impede sobrescrita
  pelo worker periódico. Origem não é inferida a partir de timeout.
- O texto de ajuda descreve a verificação periódica somente após sua ativação.
- O detalhamento parte de canal ou anúncio diretamente; os outros dois cartões
  mantêm suas funções e contagens, sem repetir árvores de navegação.
- O novo worker não cria linhas, não envia mensagens nem altera snapshots de
  entregas; reprocessamento histórico amplo depende de definição separada.
- A documentação central descreve todos os workers e distingue o serviço web;
  nomes, responsabilidades, periodicidades e comandos correspondem ao código
  e aos serviços efetivamente implementados, sem orientações atuais conflitantes.
- O worker de origem não inicializa `contexto_fireads` enquanto a abertura ainda
  precisa de `NULL` para funcionar; comprovar esse caso com abertura pendente,
  consulta concluída ainda não aplicada e concorrência entre processos.
- A descoberta de pendências não perde uma conversa cuja transação confirma
  depois de outra com ID maior; reinícios e mudanças de configuração também
  não permitem aplicação de resultado obtido de outra integração/aba.
- Ciclos a cada duas horas (7.200 segundos), sem sobreposição, com orçamento de
  consulta de 300 segundos. Timeout não cria atribuição orgânica e só volta a
  ser tentado no próximo ciclo se a conversa ainda for elegível.
- Canal vazio/não reconhecido em leitura válida encerra a verificação sem erro,
  mantém origem não identificada e não dispara consulta repetida a cada ciclo.
  Diferenciar esse caso de ausência real de registro e de contrato inválido.
- Anúncio ausente de Google/Meta não provoca retentativa; outros canais ignoram
  anúncio mesmo preenchido. Não fazer consulta adicional só para anúncio.
- Uma pendência por falha fica automaticamente fora da seleção se o Funil já
  resolveu ou a conversa avançou à elegibilidade. Reproduzir também avanço e
  confirmação durante a consulta para impedir sobrescrita tardia.
- Marcador de verificação sem canal não ativa fallback orgânico no painel,
  não bloqueia preparação posterior do Funil e é removido junto com a conversa
  em procedimentos de exclusão do contato.

## 9. Relação com os documentos existentes

`docs/monitoramento_fireads_filtros_relatorios.md` descreve a implementação atual,
inclusive o escopo de anúncios somente da Meta. Este plano registra a evolução
pretendida para Google e perfis, sem afirmar que ela já foi aplicada.

`docs/plano_origem_meta_anuncios_posts.md` trata de referências recebidas pela
própria API do WhatsApp/Meta. Essa fonte é distinta da coluna `Anuncio` da FireAds;
não aplicar aquele plano nem combinar automaticamente as duas fontes aqui.

## 10. Revisão de prontidão e riscos concretos — 23/10/2026

**Conclusão atualizada após a definição de elegibilidade pelo usuário:** os
pontos de interferência na abertura e de prioridade entre workers têm uma
solução clara. A recuperação pode usar seleção por estado, sem obrigar uma
fila nova. Os riscos abaixo continuam exigindo implementação e testes, mas
não justificam ampliar o escopo para toda origem ausente. Esta revisão é de
código/plano; o novo worker ainda não existe nem foi validado em execução.

### 10.1. Proteger a abertura contra uma gravação antecipada de origem

Evidência encontrada:

- `core/repositories/fireads/pendencias.py` exige `contexto_fireads IS NULL`
  para reservar e concluir consultas iniciais.
- `core/repositories/fireads/consulta.py`, em `aplicar_decisao`, exige o mesmo
  estado para aplicar os dados de abertura.

Logo, criar esse JSON com apenas `atribuicao_monitoramento` enquanto a abertura
não terminou pode impedir essas rotinas de executar. Verificar somente se há
uma consulta com status “processando” não basta: pode ainda não haver consulta,
ou ela pode estar concluída mas aguardando aplicação pelo flow.

Solução após o refinamento: exigir abertura aplicada e dispensa comprovada da
consulta inicial, com revalidação antes da gravação. Assim, o worker nunca
inicializa `contexto_fireads` durante a abertura. A mera ausência de solicitação
de consulta não basta. Testar essa fronteira com transações reais em PostgreSQL.

### 10.2. Recuperação simplificada, sem fila obrigatória

A recomendação anterior de criar uma fila própria era para uma rotina mais ampla
de recuperação/enriquecimento. Com o escopo restrito, a proposta passa a ser
selecionar novamente todas as conversas ainda elegíveis e sem atribuição no
recorte de ativação, excluindo verificações já concluídas. Erros deixam o estado
pendente; leitura válida grava a conclusão e, se identificada, a atribuição.
Canal não informado também conclui o trabalho sem erro. A falta de atribuição,
sozinha, não pode significar pendência. Aplicar o marcador descrito na seção 6.2.
Não reaproveitar a fila de consulta inicial para esse propósito.

`id_conversa` é `SERIAL`; a ordem de alocação não garante a de confirmação.
Não fazer do último ID/data processado um corte permanente entre ciclos.
Paginação local ao ciclo pode ser usada, desde que a varredura seguinte volte
a considerar todas as pendências e recupere confirmações tardias.

Uma única instância ativa por exclusão de sessão, mais gravação condicional
curta por conversa, pode atender esse desenho sem tabela de reservas. Validar
queda/reinício, perda de conexão e duas instâncias iniciadas por engano.

### 10.3. Resultado negativo, erro e campos não informados

Definição fechada com o usuário; classificação detalhada na seção 6.2:

- Registro elegível encontrado: salvar canal e anúncio disponível, este último
  somente para Google Ads e Meta Ads.
- Leitura completa sem registro elegível nem canal indefinido: classificar
  orgânico pela regra aprovada, registrando a evidência disponível na consulta.
- Sem formulário elegível e com linha do telefone sem canal definido: concluir
  a verificação, manter origem desconhecida e não tentar novamente por esse
  motivo. Isso é informação ausente na planilha, não uma falha de consulta.
- Google/Meta com anúncio vazio: guardar anúncio não informado e concluir.
  Nos demais canais não pesquisar nem agrupar anúncios.
- Erro/timeout/contrato inválido: não atribuir origem; tentar novamente na próxima
  rodada, após duas horas, se a conversa ainda cumprir todos os requisitos.
  Se o Funil resolveu ou assumiu a conversa, descartar a pendência.

Não acrescentar enriquecimento contínuo de anúncio nem regra nova de várias
leituras negativas nesta primeira versão. Se a planilha receber um formulário
mais tarde, a preparação do Funil poderá atualizar o resultado. Atendimento que
não avançar não terá reconsulta automática depois de já ter leitura concluída,
inclusive se a planilha estava sem canal. A ajuda do painel deve explicar essa
possibilidade sem apresentar falta de informação como abandono ou falha técnica.
Essa limitação de dados tardios permanece mapeada, não é garantia de origem imutável.

### 10.4. Precedência definida: preparação do Funil prevalece

A abertura e a preparação da entrega já escrevem atribuição; a preparação atual
também atualiza a origem usada nas entregas. O worker periódico deve preencher
atribuição ausente, sem sobrepor uma confirmação feita por essas rotinas durante
sua leitura. Canal provisório e atribuição confirmada precisam continuar distintos.

O usuário definiu que, se a conversa avançar, o Funil confirma novamente e
corrige a atribuição periódica quando necessário. Aplicar a confirmação comercial
mais recente ao relatório, preservando a captura anterior para auditoria e
contando a conversa uma vez. A comparação inclui o anúncio, não apenas o canal.

Se a etapa mudar durante o HTTP do worker periódico, a revalidação deve impedir
que seu resultado tardio sobrescreva a entrega. Se ele gravar antes do avanço,
a preparação comercial posterior poderá substituí-lo. Não dispensar essa
preparação por já haver origem periódica. Retentativas de entregas já congeladas
continuam usando o snapshot; não consultar novamente para mudar a decisão de
envio a cada tentativa. O worker periódico não altera snapshots existentes.

Revalidar configuração, integração habilitada, unidade e posse após o HTTP.
Resultado de uma URL/aba que foi substituída durante a consulta não pode ser
aplicado ao novo contexto. Pausas por pagamento/integração devem respeitar as
regras existentes e preservar pendências para retomada.

### 10.5. Validar a composição das métricas e a compatibilidade do painel

O detalhamento precisa usar destinatário confirmado; o booleano de dependente
começa como `False` e, sozinho, não prova escolha de titular. Cruzar perfil e
origem por conversa, com deduplicação, mantendo a base de atendimentos separada
da contagem por participantes da consulta personalizada.

Na inclusão do Google, preservar o contrato do bloco Meta durante a mudança
de captura, API e frontend. Incluir testes de anúncio ausente, JSONB em texto,
atribuição histórica, mesmo nome em canais diferentes e isolamento por unidade.
Os números e a disposição visual precisam ser conferidos na implementação;
uma tela de login respondendo HTTP 200 não valida esses resultados.

### 10.6. O que falta para declarar a entrega pronta

- Implementar a seleção restrita, lotes, exclusão entre ciclos e gravação condicional.
- Aplicar a precedência e a proposta de resultados/retentativas registradas acima.
- Conferir o marco de ativação e índices; não presumir necessidade de uma fila nova.
- Confirmar a representação de `Anuncio` para Google em leitura real da API.
- Implementar e testar abertura concorrente, retomada, exclusão, configuração
  alterada, métricas por período e compatibilidade histórica do painel.
- Conferir interface renderizada e atualizar a documentação de todos os workers.

**As regras de negócio dos cinco pontos estão definidas para aplicação.** Não
há decisão funcional pendente nesta revisão. Os itens acima são trabalho de
implementação e validação; o plano pronto não equivale a código testado ou deploy
pronto. Conferir o marco de ativação e o contrato real da API na aplicação e
resolver eventuais diferenças com as regras registradas, sem atribuir origens
por suposição. O prazo de 300 segundos reduz interrupções prematuras, mas não
garante que a integração responderá; o tratamento de falhas continua necessário.

**Entrega desta rodada: somente a revisão deste documento na raiz do Chatbot.**

## 11. Implementação local — 24/10/2026

### Estrutura aplicada

- `workers/worker_origem_fireads/`: configuração, supervisor e ciclo independente.
- `core/repositories/fireads/origens.py`: seleção por estado, paginação por ID,
  exclusão entre processos e revalidação antes da leitura e da gravação.
- `core/integrations/fireads/origem.py`: interpretação da mesma aba, telefone e
  quatro canais existentes, sem POST ou efeitos no atendimento.
- `core/integrations/fireads/atribuicao.py`: anúncios Meta/Google, leitura de
  conclusão sem canal e preservação da captura periódica quando o Funil corrige.
- `core/repositories/funil/elegibilidade.py`: critério de etapa/link compartilhado
  pela seleção comercial e pelo novo worker. Recibos já enviados permanecem válidos.
- `callback/monitoramento/origens.py` e consulta SQL de origens: perfis e faixas
  por conversa, canal e anúncio; grupos desconhecidos; mesmos limites de período.
- `callback/monitoramento/static/monitoramento/js/origens.js`: ajuda e diálogo
  único de perfis, reutilizado por canais e anúncios, com Google abaixo de Meta.
- Serviço `chatbot-worker-origem-fireads.service`, inventário de seis workers e
  instruções de deploy atualizados. Webhook/monitoramento continua serviço web.

### Persistência e operação

Sem DDL novo: o marcador versionado `contexto_fireads.verificacao_origem` contém
ID da conversa/integração, aba, conclusão, resultado, linha e horário; a origem
confirmada usa `atribuicao_monitoramento`. JSON da abertura continua intacto e
nulo até o flow concluir seu trabalho. Campos operacionais de atendimento,
`origem_fireads`, cache e snapshots de entrega não são alterados pelo worker.

`FIREADS_ORIGEM_ATIVO=False` é o padrão. Habilitar somente com
`FIREADS_ORIGEM_DESDE` ISO 8601 fixo com fuso. Páginas de 100 usam a PK da conversa
como cursor dentro do ciclo; o teto de ID não é persistido entre ciclos. Os
índices/constraints de conversa e dos vínculos únicos de consulta/entrega são
reutilizados; não foi necessária tabela, coluna ou índice adicional.

O primeiro ciclo roda ao iniciar; a espera de 7.200s ocorre após o término.
Cada integração/aba é lida no máximo uma vez por ciclo, inclusive em páginas
posteriores. Erro de leitura não provoca repetição imediata da mesma chamada.
HTTP usa 300s; gravação usa lock_timeout 3s e statement_timeout 30s, sem transação
aberta durante HTTP. Advisory lock de sessão impede ciclos concorrentes e é
liberado ao fechar a conexão. Não altera os prazos 120/110s do atendimento.

Revalidar integração/configuração/pagamento/etapa antes de consultar e antes de
persistir. Se Funil assumir ou confirmar enquanto o GET está em andamento, o
resultado periódico é descartado. Funil mantém sua reconfirmação antes da entrega,
com prioridade inclusive para alteração de anúncio dentro do mesmo canal.

### Apresentação e limites

Detalhamento opcional permanece no card de origens. Conforme refinamento aprovado
em 24/10/2026, o diálogo antes lateral passa a ser uma janela centralizada ampla,
com seleção e período em cabeçalho fixo. Mostra totais e tabelas separadas para
titulares, dependentes e perfil não informado, com quantidades, percentuais e
envios ao Funil. No celular ocupa quase toda a tela, com rolagem interna e botão
de fechamento sempre acessível. Mantém seleção/expansão durante atualização;
fecha com botão, Escape ou fundo e devolve foco. Ajuda funciona com foco, mouse e
clique/toque. Textos externos são inseridos como texto, sem HTML.

Percentuais de cada faixa e grupo usam o total de atendimentos do canal/anúncio
aberto no período, incluindo não informados; não representam conversão ao Funil.
Arredondar para até uma casa decimal e explicar a possível diferença na soma.
O período é herdado dos relatórios, sem seletor próprio. Contar todas as conversas
de cada chat (cliente × unidade) nesse período, sem reduzir à última conversa ou
a contatos únicos. Preservar menores, abaixo da idade mínima e idade/perfil
ausentes nas categorias já existentes. Não exige alteração de consulta ou SQL.

A idade exibida é a atualmente cadastrada para o participante, não uma captura
histórica. Atribuição pode ser corrigida pelo Funil. Não há retroação automática
nem consulta extra para enriquecer anúncio vazio. Dados históricos sem anúncio
preservado continuam como não informado; não se promete reconstruir campanhas.

A conferência real foi concluída em 24/10/2026. A falha anterior de conexão era
o certificado RDS configurado com caminho Linux inexistente no Windows. Usando
o bundle oficial AWS local apenas para esse processo, com `verify-full`, foi
possível ler a configuração de Santo André e consultar a FireAds em 5,31s.
A aba retornou 755 linhas e os cabeçalhos `WhatsApp`, `Canal`, `Data/Hora` e
`Anuncio`. Havia 444 registros Meta (297 com anúncio) e 24 Google (1 com anúncio,
“Escola de memoria”). O código interpretou canal/anúncio dos 468 registros em
memória, incluindo os sem anúncio. Essas quantidades são linhas da planilha,
não os atendimentos do relatório. Sem escrita no banco, cache ou API, sem iniciar
workers e sem alterar o `.env`. Contrato de leitura confirmado; a instalação
e verificação do serviço na VM continuam sendo etapas do deploy.

Testes e evidências ficam em [tests/README.md](tests/README.md). Ativação e parada
ficam em [deploy/README.md](deploy/README.md); responsabilidades de todos os
processos em [workers/README.md](workers/README.md).
