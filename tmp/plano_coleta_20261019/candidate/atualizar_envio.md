# Plano de atualização da consulta e dos envios FireAds/Funil

Data: 14/10/2026.

Status: implementação local em 14/10/2026; deploy ainda não realizado.
Migração: `deploy/migrations/20261014_fireads_aba_geral.sql`. Os critérios abaixo
registram o contrato aplicado e as limitações aceitas.

Revisão de viabilidade em 14/10/2026: há definição suficiente para iniciar a
implementação. Liberação para produção depende das validações das seções 11 a
13; revisão do plano não comprova ausência de bugs no código ainda não escrito.

## 1. Objetivo e decisões finais

Centralizar a consulta de abertura e a entrega do atendimento na aba
**LEADS GERAL - Feedback**, substituindo a leitura das abas Google Ads e Meta
7.2. O canal e o destinatário serão extraídos da própria linha selecionada.

As decisões mais recentes desta conversa prevalecem sobre propostas anteriores:

- Filtrar os registros do telefone pelos três canais aceitos antes de escolher
  o mais recente. Um registro manual mais novo não elimina um formulário válido
  de Google Ads, Meta Ads ou Orgânico Site.
- Manter uma consulta lógica por nova conversa, executada pelo worker separado.
- Campo obrigatório ausente, inclusive “Para quem é”, mantém o fallback orgânico
  desde a etapa 1. Não implementar coleta parcial nesta atualização.
- Orgânico Site passa a ser uma origem própria no sistema, embora use o mesmo
  código de Funil do orgânico comum: `113481`.
- Preservar as informações externas e acrescentar as observações do chatbot
  abaixo das observações que já existirem.
- Manter o identificador técnico de reconciliação, com a explicação solicitada.
- Substituir o cabeçalho fixo “NOVO LEAD” por uma classificação real entre
  primeiro atendimento e atendimento de um lead antigo na mesma unidade.

O indicador “digitando…” não faz parte desta atualização. Sua proposta continua
em [proposta_indicador_digitando.md](proposta_indicador_digitando.md).

## 2. Situação atual que será modificada

Hoje o worker de consulta lê duas abas e identifica a origem pela aba. A leitura
Google usa `Perfil/Faixa` para o destinatário; a leitura Meta usa `para_quem`.
O envio posterior ao dashboard já utiliza a aba geral.

O montador de observações do Funil escreve “NOVO LEAD” incondicionalmente. Ele
**ainda não verifica se é o primeiro atendimento**. A menção anterior ao script
FireAds não significava que essa distinção já existisse.

O dashboard recebe um bloco delimitado por marcadores como
`[INICIO CHATBOT:1:291]` e `[FIM CHATBOT:1:291]`. Os números identificam a
integração e a conversa. Eles permitem reconhecer uma entrega que ocorreu antes
de uma queda, evitando acrescentar novamente o mesmo bloco quando ele permanece
intacto na planilha.

O banco atualmente limita `origem_fireads` a `google`, `meta` e `organico`, em
um campo de dez caracteres. A integração também exige três nomes de abas
distintos. Esses contratos precisam acompanhar a alteração.

## 3. Contrato da aba geral

A leitura usará os cabeçalhos, sem depender das letras das colunas:

| Coluna | Uso |
| --- | --- |
| `WhatsApp` | Identificar o contato com os formatos de telefone já aceitos. |
| `Data/Hora` | Ordenar os formulários do mesmo telefone. |
| `_row` retornado pela API | Desempatar e localizar fisicamente o registro. |
| `Nome` | Extrair o nome com o extrator FireAds existente. |
| `Email` | Extrair o e-mail com o extrator FireAds existente. |
| `Para quem é` | Interpretar titular ou dependente. |
| `Canal` | Determinar a origem do registro selecionado. |
| `Observação` | Preservar o conteúdo e acrescentar o atendimento na entrega. |

`Perfil/Faixa` deixa de ser a fonte de destinatário na consulta. Não inferir
parentesco a partir de faixa etária nem usar esse campo para completar um
`Para quem é` vazio.

Na verificação realizada em 14/10/2026, a API já retornava `Para quem é`, mas os
452 registros dos três canais estavam sem valor nessa coluna. O usuário
confirmou que os novos formulários passarão a preenchê-la; registros antigos
podem continuar vazios e seguirão o fallback definido abaixo. O preenchimento
retroativo não é requisito desta atualização.

Cabeçalho ausente é falha de contrato da integração; célula vazia em uma linha é
dado incompleto daquele formulário. Registrar motivos distintos, sem importar
dados parciais em nenhum dos dois casos.

A decisão usa os dados disponíveis na resposta da API. Se o formulário ainda
não tiver sido consolidado na aba geral, ou o cache servir uma versão anterior,
o telefone pode parecer ausente ou o registro incompleto. Aplicar o fallback
definido, sem inventar uma nova consulta em outra etapa. Não prometer leitura
instantânea da planilha: a atualização/consolidação externa é responsabilidade
da FireAds.

## 4. Seleção do registro de abertura

### 4.1 Identidade do telefone

Preservar a normalização e os formatos brasileiros existentes, incluindo DDI,
DDD, pontuação, prefixo usado pela Meta e variantes móveis com e sem o nono
dígito. Comparar todos os equivalentes aceitos antes de ordenar os candidatos.

Não procurar pelo e-mail como substituto da identidade do WhatsApp. Não ampliar
as equivalências de telefone de modo a confundir DDDs, fixos ou números de outro
país.

### 4.2 Filtrar canal antes de ordenar

Os canais elegíveis são exclusivamente:

- Google Ads;
- Meta Ads;
- Organico Site.

Aceitar variações de maiúsculas, espaços e acentos por normalização, conservando
o texto original para diagnóstico. Não incluir novos sinônimos comerciais
silenciosamente: por exemplo, `MKT DIGITAL - GOOGLE ADS` não se torna elegível
apenas por conter as palavras Google Ads.

Procedimento:

1. Localizar todos os registros equivalentes ao telefone.
2. Separar aqueles cujo canal seja um dos três aceitos.
3. Se houver candidatos, escolher somente o mais recente entre eles.
4. Se não houver, seguir atendimento orgânico desde a etapa 1.

Indicação, Lead Franqueador e demais canais manuais não participam da seleção
de formulário. Sua presença não impede usar um registro elegível mais antigo.

### 4.3 Recência

A ordem principal será a data/hora do formulário. Empates serão resolvidos pela
maior `_row`, incluindo registros do mesmo dia sem horário.

Preparar a interpretação dos formatos de data realmente entregues pela API,
incluindo data sem hora. Datas sem offset usam o fuso configurado, preservando o
fallback atual para Brasília. Não confundir formatos brasileiros com mês/dia.

Preservar o comportamento determinístico para datas inválidas: datas válidas
têm prioridade; se não houver data válida, usar a maior linha. A seleção deve
registrar quando dependeu desse fallback. Maior linha é o critério operacional
de desempate, não uma garantia de cronologia após uma ordenação manual da aba.

Não retornar “ambiguidade” porque o mesmo telefone aparece várias vezes, tem
nomes divergentes, mudou de destinatário ou veio de canais diferentes. Não
priorizar Meta sobre Google ou Orgânico Site.

### 4.4 Usar um único formulário inteiro

Nome, e-mail, destinatário e canal vêm da linha escolhida. Se essa linha estiver
incompleta, não voltar a uma linha mais antiga e não combinar campos de vários
formulários.

| Registros do mesmo telefone | Decisão |
| --- | --- |
| Apenas Indicação | Orgânico, desde a etapa 1. |
| Apenas Lead Franqueador, ou vários canais não elegíveis | Orgânico, desde a etapa 1. |
| Google antigo e Indicação mais recente | Usar o Google. |
| Meta, Google e Orgânico Site | Usar o mais recente entre esses candidatos. |
| Dois candidatos com a mesma data/hora | Usar o de maior linha. |
| Nenhum registro do telefone | Orgânico, desde a etapa 1. |
| Candidato escolhido com `Para quem é` vazio | Orgânico, desde a etapa 1, sem completar dados com outro registro. |

## 5. Extração e aplicação no atendimento

Preservar os extratores de nome e e-mail da FireAds. Não reaplicar as restrições
dos validadores de texto livre do WhatsApp aos campos do formulário.

Interpretar opções explícitas de destinatário:

- `Para mim` corresponde a titular.
- Parentescos e opções conhecidas de atendimento para outra pessoa correspondem
  a dependente, resumidos para exibição como `Para dependente`.
- Valores novos e não reconhecidos não autorizam inventar titular ou dependente.

Ampliar o catálogo de opções a partir dos valores do formulário, preservando as
opções já reconhecidas. Não inferir que qualquer texto diferente de “Para mim”
seja dependente.

Com nome, e-mail e destinatário completos e interpretáveis, importar os dados e
manter a abertura personalizada na etapa de profissão, inclusive para Orgânico
Site. Preservar os desvios e tratamentos já previstos no atendimento.

Sem um desses campos, ou com destinatário desconhecido, aplicar o fallback
orgânico atual desde a etapa 1. Não utilizar parte do nome/e-mail importado para
pular perguntas. A proposta de coleta parcial permanece exclusivamente em
[docs/valida_dados_parciais_fireads.md](docs/valida_dados_parciais_fireads.md).

A decisão deve distinguir no diagnóstico interno:

- telefone ausente;
- telefone presente apenas em canais não elegíveis;
- formulário elegível incompleto;
- destinatário desconhecido;
- falha operacional ou prazo esgotado.

Mesmo no fallback, conservar a referência da linha encontrada quando existir.
Isso evita que a entrega posterior crie um cadastro duplicado. A origem bruta do
registro e a origem efetivamente aplicada ao atendimento são informações
distintas; não perder o diagnóstico nem afirmar que o telefone estava ausente
quando ele foi localizado.

## 6. Canais e códigos no Funil

| Origem efetiva | Valor interno proposto | Código no Funil | Descrição humana |
| --- | --- | --- | --- |
| Google Ads | `google` | `113336` | Lead veio de uma campanha do Google Ads. |
| Meta Ads | `meta` | `113340` | Lead veio de uma campanha da Meta Ads. |
| Orgânico Site | `organico_site` | `113481` | O Lead chegou ao site de maneira orgânica e preencheu o formulário. |
| Orgânico | `organico` | `113481` | Lead entrou em contato com o chatbot de maneira orgânica, possivelmente por alguma rede social Meta da unidade. |

Orgânico Site não é Google Ads e não se confunde internamente com o orgânico
comum. Compartilhar o código `113481` é uma decisão de envio ao Funil; o rótulo,
a descrição e o campo de origem devem continuar distinguindo os casos.

Nos fallbacks de formulário incompleto ou canal não elegível, o atendimento
será orgânico. A descrição não deve apresentar como fato uma campanha ou uma
rede social que não foi confirmada, nem declarar “não encontrado” quando houve
registro. O motivo específico fica preservado no diagnóstico da consulta.

Unidades sem integração FireAds conservam sua configuração de envio ao Funil;
não sobrescrever silenciosamente códigos de outras integrações.

### Evidência do teste com canal vazio

Foi realizado um POST autorizado em Santo Antônio de Jesus, com
`codigo_canal_venda` e `ForceCodeChannel` vazios. O retorno observado foi HTTP
500 sem JSON, registrado em
[resultado_saj_canal_vazio_20261014.json](utilitarios/integrations/resultado_saj_canal_vazio_20261014.json).

Esse retorno não comprova que canal vazio seja proibido e não exclui gravação
parcial ou concluída antes do erro. O usuário relatou possível cadastro no CRM,
mas não foi confirmado o canal da oportunidade exata. Não repetir o teste
automaticamente nem tratar HTTP 500 como sucesso no worker.

Independentemente dessa incerteza, a decisão final do usuário é enviar Orgânico
Site com `113481` e explicitar a origem nas observações. Não haverá fallback
automático de um POST vazio para outro POST com código, pois isso poderia criar
duas oportunidades.

## 7. Observações compartilhadas e histórico do lead

### 7.1 Texto único

Gerar uma única versão das observações do atendimento e congelá-la antes do
primeiro envio externo. Esse conteúdo será enviado ao Funil e acrescentado ao
dashboard, sem dois montadores produzindo resumos diferentes.

O texto começa com **Observações de atendimento**. Retirar o sufixo humano
“— conversa 291”; o identificador fica apenas na referência técnica necessária.

A ordem das informações do atendimento será:

1. Classificação: novo lead ou novo atendimento para lead antigo.
2. Canal de venda e descrição da origem.
3. Orientação operacional existente e preferência de turno, quando houver.
4. Dados do titular: nome, telefone, e-mail e demais dados aplicáveis.
5. Profissão do titular.
6. Dados do dependente, quando o atendimento for para dependente.
7. As mesmas perguntas e respostas de triagem, na mesma ordem atual.

Conservar as informações atuais sobre reserva, telefone, ausência declarada de
e-mail e demais particularidades. A profissão nunca deve parecer pertencer ao
dependente por estar posicionada depois dos dados dele.

### 7.2 Primeiro atendimento ou retorno

Incluir nesta atualização a distinção solicitada:

- Sem conversa anterior do cliente com aquela unidade: **Novo lead**.
- Com conversa anterior do cliente com aquela unidade: **Novo atendimento para
  Lead antigo**.

O critério é histórico do chatbot na mesma unidade, não presença na planilha,
canal comercial, existência no CRM ou conversa com outra unidade. Um cliente
pode ser antigo no dashboard e ainda estar no primeiro atendimento do chatbot.

Usar o `id_chat` correspondente ao par cliente/unidade e verificar conversas
anteriores à atual. Excluir a própria conversa e conversas posteriores. Definir
anterioridade pelo início da conversa, com ID como desempate. Não usar uma
contagem global de conversas que possa mudar o rótulo de um envio antigo.

Continuar a mesma conversa não transforma um novo lead em lead antigo durante
o atendimento. Retry também não muda a classificação. O resultado deve compor
o snapshot do envio para ser reutilizado na recuperação.

O SQL dessa consulta pertence aos repositórios. Não consultar o banco dentro do
montador de texto. O sistema só pode classificar a partir do histórico mantido;
uma exclusão de teste que removeu todo o histórico torna o contato novo segundo
os dados disponíveis.

### 7.3 Referência técnica autorizada

Manter uma chave única por integração/conversa para reconciliação. Acrescentar
a explicação com o texto solicitado pelo usuário, preservado aqui literalmente:

> **Registro técnico da ESL Tech:** esta referência é apena para manter o atendimento sincronizado entre os sistemas e a evitar registros repetidos. Não é relevante para o atendimento com o Lead

A explicação não substitui a chave técnica. O texto padrão de explicação e o
título “Observações de atendimento” não são identificadores de um atendimento.

Formato ilustrativo do bloco compartilhado:

```text
Observações de atendimento

Registro técnico da ESL Tech: esta referência é apena para manter o atendimento sincronizado entre os sistemas e a evitar registros repetidos. Não é relevante para o atendimento com o Lead
[INICIO CHATBOT:<integracao>:<conversa>]

Novo lead
Canal de venda: Orgânico Site
O Lead chegou ao site de maneira orgânica e preencheu o formulário.

<orientações e dados do titular, incluindo a profissão>
<dados do dependente, quando houver>
<perguntas e respostas atuais da triagem>

[FIM CHATBOT:<integracao>:<conversa>]
```

Para retorno, substituir apenas a classificação por “Novo atendimento para Lead
antigo”. Os placeholders representam os identificadores reais na implementação.

O reconciliador atual assume que o marcador está na primeira linha. Como o novo
texto começa pelo título humano, será necessário localizar explicitamente os
marcadores técnicos e validar o bloco completo. Não usar a primeira linha do
novo texto como chave, pois ela é igual em todos os atendimentos.

Ajustar tanto `linhas_com_bloco` quanto `acrescentar_observacoes`, pois ambas
fazem essa suposição hoje. Montar o bloco final antes do congelamento; o envio
ao dashboard não pode embrulhar novamente um bloco novo que já tenha marcadores.
Para snapshots antigos, continuar reproduzindo exatamente o formato original.

Preservar leitura dos blocos antigos e reutilizar o texto congelado de envios
anteriores. Encontrar a chave com conteúdo diferente é conflito que exige
diagnóstico; não sobrescrever nem afirmar sucesso silenciosamente.

### 7.4 Rotina antiga de importação da FireAds

O usuário confirmou que a FireAds não usa mais a rotina que importa leads do
Funil para o dashboard. Portanto, essa rotina não é uma dependência do fluxo
ativo nem impede a alteração do cabeçalho proposta neste plano.

O Apps Script anexado em 14/10/2026 ainda contém `extrairObservacoesChatbot`:
ela primeiro lê o campo personalizado `Observações` e, se estiver vazio ou
ausente, procura uma anotação que contenha `NOVO LEAD`. Depois,
`montarLinhaChatbotLead` copia as observações encontradas para a planilha.
Essas funções não geram o título nem classificam o cliente como novo ou antigo.
Quem escreve o cabeçalho fixo é o nosso `montar_observacoes_lead`, conforme
explicado na seção 2.

O alerta anterior tratava de compatibilidade caso essa importação ainda fosse
usada; não era um diagnóstico de falha no envio atual. Nosso worker envia as
observações diretamente ao dashboard, sem depender dessa busca alternativa.
Se a importação antiga for reativada no futuro, será necessário revisar sua
compatibilidade com os novos textos e com os formatos históricos.

Manter os marcadores técnicos de reconciliação usados pelo nosso envio direto,
conforme a seção 7.3. Eles têm outra finalidade e não dependem da expressão
`NOVO LEAD`. Não alterar o Apps Script externo nesta atualização.

## 8. Criação e atualização no dashboard

### 8.1 Registro localizado

Conservar todos os campos da linha. O POST de atualização altera somente
`Observação`, juntando seu conteúdo anterior ao bloco compartilhado do chatbot,
com separação legível.

Não regravar nome, e-mail, telefone, canal, perfil, destinatário, data, feedback
comercial ou outras colunas com valores obtidos durante o atendimento. O canal
efetivo do fallback não deve substituir um canal que o operador cadastrou.

A referência selecionada na consulta é o alvo da entrega, inclusive quando
aquele formulário ficou incompleto e a abertura seguiu organicamente. Um novo
formulário preenchido depois não deve redirecionar silenciosamente um envio já
preparado para outro registro.

O número da linha pode mudar após exclusão ou ordenação manual. Antes da escrita:

1. Reconsultar a aba de destino e procurar entrega já feita pela chave técnica.
2. Conferir se a linha salva ainda corresponde ao registro selecionado.
3. Se tiver sido deslocada, tentar relocalizar o mesmo registro pelos dados de
   identificação congelados, sem depender da posição antiga.
4. Ler as observações atuais e acrescentar o bloco completo.
5. Confirmar posse da reserva e configuração antes de escrever.

Para fallbacks que não produziram uma linha elegível, verificar todos os registros
do telefone antes da entrega. Havendo registro existente, a proposta é usar o
mais recente como destino das observações, preservando seu canal e seus dados;
ele não passa a ser uma fonte de importação retroativa para a conversa.

Se o registro selecionado desaparecer ou sua identidade não puder ser conferida,
registrar a condição e manter a entrega pendente para tratamento; não escrever
na posição antiga nem inventar uma correspondência por e-mail. A remoção do
critério de ambiguidade da abertura não autoriza atualizar outra pessoa.

### 8.2 Nenhum registro localizado

Preservar a criação de lead orgânico quando o telefone realmente não existir na
aba, incluindo nova conferência no momento da entrega. Se passou a existir desde
a consulta inicial, acrescentar as observações no registro identificado em vez
de criar outro automaticamente.

Manter as validações existentes para conflito de e-mail com outro telefone.
Nenhuma observação ou cadastro prévio deve ser apagado para fazer o envio passar.

### 8.3 Concorrência externa

Preservar lock local por contato, reservas versionadas, limite de observações e
reconciliação pelo bloco. Não truncar o conteúdo anterior nem o novo resumo.

Uma releitura seguida de POST por número de linha não é atômica frente a um
operador ou outro sistema. No contrato do Apps Script anteriormente fornecido,
a escrita não compara a identidade ou a versão da linha esperada pelo cliente.
O cache de leitura também precisa ser considerado ao conferir o conteúdo atual.

Portanto, esse plano não promete eliminar a janela entre ler e escrever. Para
garantia contra edição ou deslocamento externo nesse intervalo, será necessário
um contrato adicional com a FireAds que valide identidade e conteúdo/versão no
servidor antes da escrita, coordenado com os demais escritores. Essa melhoria
externa é distinta da migração do nosso banco.

O anexo atualizado configura cache de dados por 15 segundos e invalida a aba
nas escritas feitas por aquele Web App. Não há parâmetro de releitura sem cache
no contrato apresentado; adicionar um parâmetro arbitrário na URL não garante
dados novos. Alterações feitas diretamente na planilha podem aparecer depois.
Além disso, `readSheet` aplica `trim()` aos textos: o chatbot deve conservar o
conteúdo recebido, mas não consegue recuperar espaços externos já removidos
pela API. Preservação literal da célula e acréscimo atômico exigem suporte externo.

## 9. Persistência e compatibilidade

### Integração por unidade

Reutilizar `aba_destino` como configuração da única aba de leitura e escrita,
com rótulo claro no Admin, como “Aba de leads”. Não reutilizar `aba_google` e
`aba_meta` para armazenar canais: nome de aba e origem comercial são conceitos
diferentes.

Retirar a exigência de três abas distintas e remover as colunas de configuração
obsoletas na migração planejada, depois de verificar dependências e preservar
as informações históricas necessárias. Não alterar URLs, ativação, pagamento ou
configuração de outras unidades como efeito colateral.

### Consulta e conversa

Manter uma consulta por conversa e o vínculo existente ao chat/unidade. A entrada
passa a conter a única aba e a versão do contrato de leitura.

O resultado deve preservar a decisão completa e a referência do registro:
aba, linha observada, telefone normalizado, canal original, data original e
interpretada, destinatário original e os dados necessários à relocalização.
Guardar somente os registros relacionados ao contato, sem copiar toda a planilha.

Os campos JSON já existentes podem receber esses dados com versão explícita de
contrato; não é obrigatório criar uma coluna para cada atributo. A origem
`organico_site` precisa ser aceita no modelo, no tamanho do campo e no CHECK do
banco. A decisão aplicada e `conversa.origem_fireads` devem continuar coerentes.

### Envio e recibo

Congelar texto, classificação de lead, origem efetiva, código Funil, referência
do alvo e versão do formato. Preservar o vínculo por conversa e registrar no
recibo a linha efetivamente atualizada, que pode ser diferente da observada na
consulta.

Retries reutilizam o snapshot; não recalculam o canal, a condição de lead antigo
ou as observações a partir de cadastros posteriores. Consultas concluídas,
conversas já iniciadas e envios confirmados não são reinterpretados para adotar
o novo contrato.

Manter compatibilidade com snapshots legados que não possuem referência da linha
ou classificação de primeiro atendimento, conservando o texto e os códigos já
congelados. O deploy não deve transformar uma entrega antiga em outra oportunidade.

### Consulta concluída antes da migração, ainda não aplicada

Tratar separadamente esse estado: o resultado já está salvo, mas o `worker_flow`
ainda não iniciou a abertura. A remoção das colunas de abas antigas não pode ser
interpretada automaticamente como uma alteração real da integração.

Preservar resultado e entrada originais. Registrar na migração uma configuração
de compatibilidade para comparar integração, URL, fuso e aba geral no novo
contrato, sem reexecutar HTTP nem reclassificar o formulário salvo. Essa
compatibilidade só vale se a configuração legada ainda correspondia à integração
no momento da migração; não apagar evidências de uma mudança real anterior.
Mudança real de configuração ou desativação continua impedindo a importação.

O `worker_flow` deve distinguir ausência de versão em um registro legado de uma
entrada nova inválida. Uma versão futura ou desconhecida não pode ser consumida
como se tivesse o formato atual. Erros de importação, inclusive conflito de
e-mail no banco, mantêm o fallback e o rollback existentes e preservam a
referência do alvo para a entrega, sem importar dados parcialmente.

### Envios de unidades sem FireAds

Hoje `congelar` retorna diretamente para essas unidades, sem snapshot em
`envios_dash`. Não assumir que o congelamento já as cobre. Para cumprir a regra
de reutilizar o mesmo texto nos retries também nesses envios, persistir o
snapshot no repositório/fila do Funil, com a alteração SQL necessária, sem criar
integração FireAds ou entrega ao dashboard fictícia. Manter o código de canal
configurado na unidade.

Nesses envios somente ao Funil, o cabeçalho e a classificação novo/antigo se
aplicam; não inventar um ID de integração para os marcadores do dashboard.
Envios antigos sem snapshot não têm payload histórico recuperável: documentar
essa limitação e congelar no primeiro processamento com a nova versão, sem
afirmar que o texto de uma tentativa anterior foi reconstruído exatamente.

## 10. Arquitetura e roteiro de implementação

| Área | Alteração planejada |
| --- | --- |
| `core/integrations/fireads/contrato.py` | Catálogo de quatro origens, seleção por canal elegível e recência, datas e formato técnico de observações. |
| `core/integrations/fireads/extratores.py` e interpretação do resultado | Reutilizar extração atual e mapear a coluna `Para quem é`, preservando fallback sem coleta parcial. |
| `workers/worker_consulta_dash/consulta.py` e `resultado.py` | Consultar somente a aba geral e salvar a decisão/referência completas. |
| `core/repositories/fireads/consulta.py` e `pendencias.py` | Ler a configuração única, versionar a entrada e manter reservas, prazos e aplicação transacional. |
| `workers/worker_flow/fireads.py` | Comparar a configuração única, aplicar resultados legados compatíveis e preservar o alvo nos fallbacks, sem HTTP no fluxo. |
| `core/repositories/funil/leads.py` | Obter o histórico anterior da mesma unidade e os dados da conversa para a classificação. |
| `core/integrations/funil/oportunidades.py` | Produzir o texto único, ordem da profissão, rótulo novo/antigo e descrições dos quatro canais. |
| `core/repositories/fireads/envios.py` e persistência de envios necessária | Congelar payload, referência, classificação e versão de formato sem reescrever snapshots anteriores. |
| `workers/worker_funil/processamento.py` e `core/repositories/funil/envios.py` | Recuperar o payload congelado antes de reconstruí-lo; cobrir envios somente ao Funil sem depender de `envios_dash`. |
| `core/integrations/fireads/destino_dashboard.py` | Conferir e relocalizar o alvo e reconhecer blocos antigos e novos. |
| `workers/worker_funil/fireads.py` | Coordenar leitura, reconciliação, append/update e recibo, preservando as demais colunas. |
| `callback/webhook/models.py` e `admin.py` | Exibir origem Orgânico Site e a configuração de aba única; ajustar validações do formulário. |
| `core/database/deploy_database` | Atualizar o esquema de novas instalações, sem reaplicar setup em produção. |
| `deploy/migrations` | Entregar migração incremental para a instalação existente. |
| `tests` e documentação | Cobrir os contratos novos e os caminhos de recuperação legados. |

SQL de produção permanece em `core/repositories`. SQL de utilitários permanece
em `utilitarios`. Workers coordenam transações; integrações fazem HTTP ou
transformações puras; montadores de observações não consultam banco.

Preservar `status_pagamento`, bloqueios, limites de idade, personalização,
ordenação da fila, lock de conversa, fencing, retries e checkpoints existentes.
Não criar views. Não criar um segundo worker de consulta nem tarefa auxiliar
dentro do `worker_flow`.

O prazo de 300 segundos e o fluxo durável de consulta permanecem. A migração
não deve iniciar consultas em cada etapa, retroceder conversas ou exigir outra
mensagem do cliente para retomar uma pendência concluída.

## 11. Validações antes do deploy

Testes focados de comportamento, sem POST de produção automático:

- Só a aba geral é consultada; cabeçalhos usados correspondem ao novo contrato.
- Equivalências de telefone continuam válidas, inclusive candidato mais recente
  com outra representação do nono dígito.
- Canal manual mais novo não vence formulário de canal elegível mais antigo.
- Recência prevalece entre os três canais; empate de data usa maior linha.
- Registro mais recente incompleto não é substituído por formulário antigo.
- `Para quem é` vazio e destinatário desconhecido levam à etapa 1 sem coleta parcial.
- Orgânico Site completo usa abertura personalizada e código `113481`, com texto
  distinto do orgânico comum.
- Google e Meta continuam enviando os códigos `113336` e `113340`.
- Histórico de outra unidade não transforma o contato em lead antigo nesta unidade.
- Conversa atual, conversa posterior e retries não alteram a classificação histórica.
- Profissão do titular aparece antes dos dados do dependente.
- O bloco de observações congelado é o mesmo nos dois destinos.
- Update modifica somente `Observação` e preserva integralmente o conteúdo anterior.
- Linha deslocada não provoca escrita no contato errado; registro desaparecido
  não provoca recriação silenciosa de um alvo antes existente.
- Marcadores iguais com conteúdo íntegro reconciliam; marcadores com conteúdo
  divergente não autorizam sobrescrita.
- Reconhecer blocos legados e o novo formato, cujo marcador não está na primeira linha.
- Recuperação após queda, perda de reserva e suspensão por pagamento continuam válidas.
- Envios confirmados não são repetidos por mudança de formato ou código.
- Consulta legada concluída e ainda não aplicada mantém sua decisão após a
  migração; alteração real de configuração continua sendo detectada.
- Pendência legada convertida mantém ID e prazo original; conclusão tardia da
  reserva anterior não consegue substituir o resultado atual.
- Falha de importação por e-mail em conflito reverte todos os dados importados,
  preservando a referência da linha para entrega posterior.
- Duas mensagens do mesmo contato aguardam a mesma consulta e mantêm sua ordem;
  outra conversa liberada continua sendo atendida enquanto a consulta aguarda.
- Unidades sem FireAds não criam consultas ou entregas ao dashboard; conservam
  o canal configurado e recuperam seus próprios snapshots de envio ao Funil.
- Dois atendimentos distintos do mesmo telefone podem acrescentar dois blocos
  na mesma linha, apesar de ambos começarem por “Observações de atendimento”.
- Falha no dashboard não desfaz um envio confirmado ao Funil nem repete esse POST.
- Migração reexecutada preserva dados; instalação nova chega ao mesmo esquema;
  nenhum caminho de runtime consulta colunas removidas.

A reconciliação do dashboard não elimina a janela própria do Funil: se a API
gravar e falhar antes da confirmação local, um retry pode duplicar a oportunidade.
Não apresentar o marcador de observações como garantia de idempotência do CRM.

## 12. Migração SQL e implantação

O último artefato da implementação deverá ser um arquivo SQL completo para
salvar no DBeaver, acompanhado das verificações e da ordem de implantação.
Este plano não contém comandos parciais para executar antecipadamente.

A migração deverá:

1. Conferir a versão de base e os vínculos existentes.
2. Ampliar o campo de origem e sua restrição para aceitar `organico_site`.
3. Consolidar a configuração em `aba_destino`, retirando a restrição de três abas
   e as colunas obsoletas após preservar a informação histórica necessária.
4. Tratar entradas de consultas ainda pendentes no contrato antigo, preservando
   a entrada original para auditoria, convertendo a configuração para a aba geral
   e invalidando reservas antigas. Não estender o prazo original de 300 segundos.
5. Manter consultas concluídas, decisões já aplicadas, históricos e snapshots de
   envios anteriores íntegros; o código novo precisa reconhecê-los.
6. Criar apenas os campos de snapshot/versão realmente necessários à recuperação,
   se os campos existentes não forem suficientes durante a implementação.
7. Registrar a versão da migração e validar contagens, vínculos e configurações
   antes do commit. Tornar a reaplicação segura e explícita.

Executar a mudança coordenada de código e banco com webhook e workers parados,
incluindo o worker de consulta. Confirmar que não há execução antiga ainda
escrevendo antes de converter pendências ou remover colunas.

Após a migração, validar o Admin, as consultas diretas, a retomada de pendências
e os testes relevantes antes de iniciar os serviços. Entregas legadas devem
continuar recuperáveis. Um rollback de código sozinho pode ser incompatível com
o esquema novo; documentar a recuperação antes da aplicação.

Não alterar banco de produção, fazer novos POSTs de teste, limpar contatos,
editar Apps Script ou atualizar versionamento como consequência de apenas
registrar este plano. Essas ações pertencem às etapas posteriores correspondentes.

## 13. Critério de conclusão da implementação

As regras funcionais estão definidas. A mudança reduz as fontes consultadas,
mas também altera o contrato de configuração, o catálogo de origens, o texto
compartilhado e a recuperação de pendências; não é apenas trocar o nome da aba.

Antes de liberar o deploy, demonstrar com testes focados a preservação dos
fluxos de titular/dependente, conversa nova/ativa/encerrada, bloqueio de 30 dias,
restrições de idade, personalização, retomada de follow-up, elegibilidade ao
Funil e suspensão por pagamento. Confirmar também que o reaproveitamento de
e-mail importado continua condicionado à decisão da conversa correta.

Separar no relatório final: comportamento verificado em testes, contrato externo
conferido em leitura e limites que permanecem. O risco de confirmação externa
antes do commit local e a janela de edição concorrente da planilha não devem
ser apresentados como resolvidos por esta simplificação.

Esta revisão foi de código e planejamento: não executou testes da implementação
futura, não fez POST externo, não alterou banco e não validou o endpoint publicado
como se fosse necessariamente idêntico ao código anexado.


## 14. Entrega local e procedimento desta atualização

A implementação usa `core/integrations/fireads/aba_geral.py` para seleção e
relocalização e `core/repositories/funil/snapshots.py` para recuperação dos envios.
O único SQL incremental desta entrega é
[20261014_fireads_aba_geral.sql](deploy/migrations/20261014_fireads_aba_geral.sql).

Ordem do deploy sobre a instalação atual:

1. Ter backup recuperável do banco, além do backup de código; parar o follow-up
   e depois webhook, flow, consulta-dash, Funil e Consumo Meta. Confirmar os seis
   serviços inativos e ausência de outra instância antiga usando o banco.
2. Atualizar o código da VM para a revisão que inclui esta entrega.
3. Executar o SQL completo no DBeaver, do `BEGIN` ao `COMMIT`. Confirmar
   `migracao_ok=true`; pendências não precisam estar zeradas. Não executar setup,
   seeds nem migrations históricas no lugar deste arquivo.
4. Rodar `callback/manage.py check` e os testes unitários FireAds/flow/Funil.
   No shell Django, consultar uma linha (mesmo com tabela vazia) de
   `IntegracaoFireAds`, `ConsultaFireAds` e `FunilEnvio` para conferir as colunas.
5. Conferir no Admin a Aba de leads e os cabeçalhos/valores que a FireAds fornece.
   Ativação, contrato validado, URL e fuso existentes não são alterados pelo SQL.
6. Iniciar os seis serviços e conferir estados, logs, webhook e monitoramento.
   Homologar com conversa nova; conversa já iniciada não é reclassificada.

A migração preserva as configurações de abas antigas em
`migracoes_fireads.dados`, amplia o domínio de origem e acrescenta
`funil_envios.snapshot`. Entradas pendentes compatíveis são convertidas,
invalida-se a reserva antiga e mantém-se o prazo original. Consultas já concluídas
não são refeitas; uma ponte de configuração distingue migração de alteração real.
Envios antigos com snapshot de dashboard são copiados para a fila do Funil sem
alterar seu payload. Envios sem FireAds anteriores a esta versão não tinham
payload histórico: congelam no primeiro processamento novo, sem promessa de
reconstruir o texto de uma tentativa antiga não registrada.

Recuperação: erro antes do COMMIT desfaz toda a migração; executar ROLLBACK,
resolver a causa e repetir o arquivo inteiro. Depois do COMMIT, código antigo
não é compatível com as colunas removidas. Preferir correção coordenada de código;
se for necessário restaurar backup, manter serviços parados e reconciliar antes
os eventos externos/dados posteriores ao backup. Não apagar snapshots nem usar
migração histórica para tentar desfazer esta mudança. O backup de Git sozinho
não restaura o banco.

A integração externa não foi alterada nem houve POST real nesta implementação.
Permanece a janela de edição concorrente/cache da planilha e a possibilidade de
repetir operação externa aceita antes do commit. Isso não permite retroceder
etapas ou abrir outra consulta em cada mensagem da mesma conversa.


### Validação da implementação local

Foram verificados os 496 testes unitários e 72 testes de integração PostgreSQL.
A descoberta unitária apontou uma fixture antiga do retorno SQL e a falta local
de `svglib==1.5.1`, já previsto em requirements. A fixture foi atualizada, a
dependência instalada no ambiente local e ambos os testes passaram na reexecução.
A bateria focada de 110 testes FireAds/Funil/flow passou novamente após os ajustes.
Os 72 testes PostgreSQL passaram juntos; a verificação adicional da duração de
reserva configurável do Funil passou com o payload congelado no retry.

Django models/Admin/URLs foram conferidos com configurações de teste e sem
problemas. O SQL foi exercitado em PostgreSQL 16 local descartável, incluindo
execução integral e repetição. HTTP foi simulado; nenhum dado de produção foi
consultado ou alterado e nenhum POST externo foi feito nesta implementação.
