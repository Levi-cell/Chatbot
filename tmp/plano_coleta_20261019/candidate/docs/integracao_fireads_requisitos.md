# Plano de integração com a FireAds

Revisão: **07/10/2026 — decisões confirmadas após a retomada da conversa**.

**Status:** decisões de negócio desta revisão registradas. P1, P2 e as três
perguntas de retomada estão respondidas. A implementação, a migração SQL e o
deploy continuam aguardando o comando de aplicação. As verificações técnicas
indicadas neste plano fazem parte dessa implementação; não significam recursos
já implantados.

**Complemento de banco aprovado em 07/10:** a aplicação FireAds passa a incluir
o vínculo universal `chat` e a tabela `consulta_fireads`, com uma consulta atual
por chat integrado. `conversa.id_cliente` e `id_unidade` permanecem nesta fase.
As abas terão defaults no SQL e no Django. O estado de consulta é ligado ao chat,
mas os dados adotados por cada conversa permanecem preservados nela.

**Complemento de observações e datas em 07/10:** ao atualizar um contato existente,
preservar integralmente a Observação atual e acrescentar abaixo um bloco com o
texto do atendimento enviado ao Funil, sem repetir o bloco em retries. Isso
preserva referências de criativo/campanha e anotações da agência/comercial.
Não enviar Data/Hora nem configuração de fuso à FireAds: no cadastro o Apps
Script define a data; no update a data existente permanece intocada.

**Base:** V1.9.2, 24 etapas, reserva com/sem link, Funil, follow-up e Consumo Meta.
Preservar as mudanças locais existentes. A integração será determinística;
não depende da futura IA. Seus efeitos estão alinhados ao plano unificado e ao
comparativo; os TXT ainda devem acompanhar os contratos efetivamente implementados.

## 1. Objetivo e decisões vigentes

Aproveitar os três dados úteis dos formulários FireAds para reduzir perguntas,
preservar a origem do atendimento no Funil e manter o cadastro no dashboard
atualizado com as observações completas produzidas pelo chatbot.

O piloto é Santo André — Jardim Bela Vista/Dora. A configuração será por unidade,
sem fixar seus nomes, agente, telefone ou ID na lógica do atendimento.

| Tema | Decisão confirmada |
| --- | --- |
| Google | Eduardo alterou “Para quem é?” para distinguir titular/dependente. P1 resolvida. |
| Meta | Consultar somente **[FIRE] Leads Ads Geral - 7.2**. P2 resolvida. |
| Abas de formulário | Google e Meta 7.2 são somente fontes de consulta do chatbot. |
| Destino de escrita | Cadastrar/atualizar em **LEADS GERAL - Feedback**. |
| Consulta inicial | No início de **toda nova conversa**, antes da primeira resposta. |
| Idade do formulário | Sem prazo de expiração: inclusive formulários com mais de 30 dias. |
| Registro em ambas as fontes | Escolher o mais recente e sua origem. |
| Dados aproveitados | Nome do titular, e-mail do titular e escolha titular/dependente. |
| Importação completa válida | Começar na profissão com mensagem personalizada; dispensar nome, destino, confirmação do destino e coleta posterior de e-mail. |
| Ausência, dados incompletos/inválidos ou falha na consulta inicial | Classificar como orgânico e seguir atendimento completo. |
| Exportação | Primeiro Funil; depois cadastro/atualização no dashboard pelo worker_funil. |
| Contato existente no destino | Atualizar **somente Observação**, mantendo o conteúdo anterior e acrescentando abaixo o bloco integral enviado ao Funil, uma vez por conversa. |
| Contato ausente no destino | Cadastrar com os dados disponíveis, incluindo as mesmas observações do Funil. |
| Sincronização da agência | O responsável confirmou que a FireAds desativou nesta tarde a varredura Funil → dashboard. A agência continua registrando os formulários. |
| Controle de entrega ao dashboard | conversa.lead_no_dash e tabela envios_dash, com tentativas independentes da entrega ao Funil. |
| Organização da unidade | Separar unidade, atendimento_customizado e integracao_fireads. |
| Chat permanente | Criar nesta aplicação para todas as unidades; uma linha por cliente/unidade, sem implementar IA ou cotas. |
| Consulta FireAds | Uma linha atual por chat integrado, atualizada a cada nova conversa; preservar o resultado utilizado por cada conversa. |

Estas decisões substituem a versão anterior: somente leitura, exportação apenas
ao Funil, sincronização a cargo da agência, limite de 30 dias e consulta restrita
à primeira conversa/retorno após encerramento por idade.

Não haverá exclusão de contatos em produção neste escopo. O webhook experimental
organicosupera não será usado; o contrato considerado é o Apps Script do dashboard.

## 2. Responsabilidades e dois momentos de consulta

### 2.1. Entrada do atendimento

O worker_flow consulta **as duas abas dos formulários** para saber se há dados
válidos que possam ser aproveitados e determinar a origem da nova conversa.
Ele não cria nem atualiza linhas na planilha nessa fase.

### 2.2. Entrega após o Funil

O worker_funil consulta **LEADS GERAL - Feedback** para decidir se deve atualizar
a Observação de um contato existente ou cadastrar um contato novo. Essa consulta
é feita para todas as origens, inclusive orgânico.

Encontrar alguém no formulário não garante que já exista uma linha na aba geral.
Se só estiver no formulário, cadastrar na aba geral preservando a origem
Meta/Google. Se já estiver na aba geral, atualizar somente Observação.

Da mesma forma, origem orgânica não comprova ausência na aba geral: pode ser um
contato orgânico de outra conversa, um cadastro incompleto ou uma falha na
consulta inicial. Nunca usar apenas origem_fireads para decidir fazer append.

A segunda consulta é para localizar o destino da entrega. Ela não muda a origem,
não reinicia o atendimento nem importa dados atrasados para a conversa em curso.

### 2.3. Responsável único pela exportação

A FireAds mantém a captação dos formulários. O worker_funil passa a cuidar das
entregas das conversas do chatbot à aba geral. Não chamar a antiga rotina de
importação do Funil nem implementar dois caminhos de exportação concorrentes.

O código fornecido do Apps Script continha sincronizarChatbotLeadsFunil e
configuração de execução a cada 15 minutos. A desativação foi **informada pelo
responsável**, não executada por esta revisão. Antes da ativação, conferir que
o gatilho antigo permanece desativado; não reativá-lo ao publicar o script.

## 3. Abas, URLs e contrato real da integração

### 3.1. Fontes e destino

| Finalidade | Aba de Santo André | Campos relevantes |
| --- | --- | --- |
| Consultar Google | Leads Google Ads (NÃO EDITAR) | Nome, Email, WhatsApp, Perfil/Faixa, Data/Hora. |
| Consultar Meta | [FIRE] Leads Ads Geral - 7.2 | full_name, email, phone_number, para_quem, created_time; id quando disponível. |
| Cadastrar/atualizar | LEADS GERAL - Feedback | Nome, Email, WhatsApp, Perfil/Faixa, Canal, Observação e demais colunas existentes. |

As abas Meta antigas 7.0, 6.0, 4.0 e outras não entram na consulta.
Não procurar automaticamente todas as abas com “Meta” ou “Fire” no nome.
LEADS GERAL não é fonte de formulário para pular etapas: registros produzidos
pelo próprio chatbot não passam a comprovar uma nova captação por anúncio.

As duas abas de formulário consultadas em 07/10 não possuíam a coluna Observação.
A aba geral possui essa coluna e aceita sua atualização pelo contrato fornecido.

Na conferência somente de leitura desta revisão, as duas consultas retornaram
HTTP 200 e success=true, com a aba solicitada. Google retornou 40 registros ainda
com valores antigos em Perfil/Faixa; Meta 7.2 retornou 10 registros e também
as colunas ad_id, ad_name, adset_id/adset_name e campaign_id/campaign_name.
Esses metadados não ampliam as três coletas importadas para o atendimento.

O responsável forneceu um print com Observação="FR002" e a confirmação do
Matheus de que esse conteúdo reflete o nome do criativo da planilha. Preservá-lo
como texto da FireAds, sem assumir que seja source_id/ad_id da Meta ou que toda
Observação represente exclusivamente campanha. Não é necessário interpretar o
texto para mantê-lo no dashboard. A agência continua responsável por sua atribuição.

O contrato e os nomes das abas devem pertencer à configuração da integração,
para permitir outras unidades sem copiar condições específicas de Santo André.

### 3.2. Endereço usado pelo sistema

URL de execução, tanto para consultas GET quanto para alterações POST:

https://script.google.com/macros/s/AKfycbxnwj1DsFD6qqihceO2F4b-YRBe3nXwQ70SjWb45LtUVOzrRxMo6nHqKlvNC53EDOLX/exec

URL do editor fornecida por Eduardo:

https://script.google.com/u/0/home/projects/1CVzuDR9S6N1EBc31kr7Eq-6N6URrcwmUyXyc0xmUVmYRC5lOOhtOJhij/edit

**/edit abre o código no navegador; não é uma API de alterações.**
A coluna solicitada url_operation pode guardar esse link como referência
administrativa opcional, com rótulo claro no Admin. As operações do worker
continuam usando url_dashbord, terminada em /exec. Não enviar dados de leads
ao endereço do editor.

Não transportar credenciais existentes no código fornecido para este documento,
logs ou URLs. Se a implantação exigir autenticação, seguir o contrato autorizado.

### 3.3. Consulta GET

Solicitar a aba por sheet. Validar HTTP, success, data.aba, headers e rows;
verificar se a resposta corresponde à aba pedida. HTTP 200 sozinho não prova
sucesso. No contrato observado, os registros da aba são retornados e o filtro
por telefone é feito pelo cliente; não presumir filtro remoto por telefone.

Conferir completude/paginação antes de interpretar “não encontrado”.
A lista de abas já marcou uma aba Meta como indisponível por não conter Nome,
embora sua consulta direta funcionasse. Não usar esse indicador isoladamente.

### 3.4. Cadastro POST — contrato confirmado no código fornecido

Exemplo estrutural, com valores ilustrativos:

~~~json
{
  "action": "append",
  "sheet": "LEADS GERAL - Feedback",
  "rows": [
    {
      "Nome": "<nome>",
      "Email": "<email ou vazio conforme cadastro>",
      "WhatsApp": "<telefone normalizado>",
      "Perfil/Faixa": "<titular ou dependente>",
      "Canal": "<Google Ads, Meta Ads ou Orgânico>",
      "Observação": "<bloco identificado da conversa contendo o texto integral enviado ao Funil>"
    }
  ]
}
~~~

Usar os nomes reais das colunas. O script possui ALLOW_APPEND e exige rows;
action=create com data não é o contrato de inclusão.
Omitir Data/Hora no payload: appendRows preenche a data ausente com new Date(),
e a apresentação usa o fuso da própria planilha. Não enviar fuso nem uma data
convertida para o fuso da WABA. O sistema da FireAds controla essa informação.

### 3.5. Atualização POST — somente Observação

~~~json
{
  "sheet": "LEADS GERAL - Feedback",
  "row": 123,
  "updates": {
    "Observação": "<conteúdo atual preservado>\n\n<bloco identificado da conversa contendo o texto integral enviado ao Funil>"
  }
}
~~~

123 é apenas ilustrativo: obter row do _row do contato localizado na mesma aba.
Nunca usar um _row da aba Google/Meta para editar a aba geral. Não mandar Nome,
Email, Canal, Perfil/Faixa, Feedback Comercial ou outros campos no update.

Ler a Observação atual do alvo e compor o valor completo no Python conforme a
seção 8.2: o endpoint fornecido substitui o valor da célula, não acrescenta texto
automaticamente. Nunca mandar somente o bloco novo se já houver conteúdo.
Se o campo não estiver no retorno ou a leitura estiver incompleta, manter a
entrega pendente; ausência de coluna não equivale a Observação vazia.

O contrato fornecido permite editar Feedback Comercial e Observação, mas este
projeto utilizará somente Observação. Não depende de liberar edição das demais
colunas. Não existe ação de exclusão de lead no contrato analisado.

### 3.6. Confirmação de execução

O Apps Script pode redirecionar a resposta de POST para uma leitura GET no
domínio Google correspondente. Ler a resposta final sem reenviar o POST.

Validar success e os dados da operação: inserted no cadastro; row, aba e updated
na alteração. success=false com HTTP 200 continua sendo falha.
Uma resposta “workflow iniciado” de outro webhook não confirma escrita na planilha.

Em falha ambígua após envio, consultar o destino antes de repetir um cadastro.
O cache de leitura observado é curto e pode atrasar a visibilidade: ausência
imediata após timeout não autoriza cadastrar novamente no mesmo ciclo.
A implementação deve distinguir recusa explícita de resultado desconhecido.

## 4. Organização do banco e Admin

A divisão em três responsabilidades foi aprovada. O detalhamento de campos abaixo
é a proposta técnica para implementá-la preservando valores e regras existentes.
A tabela atual integracao_funil_unidade continua existindo.

### 4.1. unidade

Manter identidade, vínculo administrativo e configuração da conexão Meta:

- id_unidade, nome_unidade, cnpj, email_responsavel e telefone.
- waba_id e phone_number_id, sem alterar seus valores ou unicidade.
- id_fuso, nome_fuso e fuso_verificado_em.
- status_pagamento e id_usuario_monitoramento.

Não recriar unidades nem mudar seus IDs na migração.

`id_fuso` e `nome_fuso` continuam automáticos: o worker de Consumo Meta consulta
o `timezone_id` da WABA, o Python o converte pelo mapeamento de fusos suportados
e persiste ID/nome junto de `fuso_verificado_em`. Não solicitar preenchimento
manual no Admin. Esse fuso da WABA não comprova o fuso usado pelo Apps Script
nas datas sem offset dos formulários; validar a configuração dessa fonte separadamente.

### 4.2. atendimento_customizado

Uma configuração por unidade, vinculada por id_unidade obrigatório e UNIQUE,
com chave própria id_customizacao. Proposta de campos a mover da unidade:

- nome_agente e genero.
- numero_comercial.
- idade_minima_suporte e email_obrigatorio.
- link_agendamento e link_instagram.
- bpa_ativo.

Preservar os tipos, valores, nulabilidade, defaults, unicidade aplicável e validações,
inclusive número comercial válido quando não há link de agendamento.
A criação de uma nova unidade deve criar sua configuração na mesma transação.

O vínculo UNIQUE garante no máximo uma configuração por unidade. Para garantir
que todas tenham uma, migrar todas as unidades existentes e validar contagens
antes de remover colunas antigas.

### 4.3. integracao_fireads

Zero ou uma integração por unidade; cada integração pertence a uma única unidade.
Somente Santo André será configurada inicialmente.

Proposta de estrutura:

| Campo | Finalidade |
| --- | --- |
| id_integracao_fireads | Chave primária. |
| id_unidade | FK obrigatória, UNIQUE. |
| integracao_ativa | Habilitar/desabilitar sem apagar histórico. |
| url_dashbord | Endereço /exec para GET e POST, com a grafia solicitada. |
| url_operation | Link /edit opcional, apenas referência administrativa. |
| aba_google | DEFAULT `Leads Google Ads (NÃO EDITAR)`. |
| aba_meta | DEFAULT `[FIRE] Leads Ads Geral - 7.2`. |
| aba_destino | DEFAULT `LEADS GERAL - Feedback`. |
| Metadado de leitura de datas/fuso | Representar o fuso efetivamente usado pela fonte quando a data não possui offset; não configurar nem alterar o fuso externo. |
| criado_em / atualizado_em | Auditoria da configuração. |

A existência da integração ativa substitui a antiga proposta de flag/url
diretamente em unidade. Não manter dois controles de ativação independentes.

As três abas ficam preenchidas automaticamente ao criar a integração: definir
os mesmos defaults no SQL e nos models Django. Não exigir digitação no Admin.
Podem aparecer como configuração avançada para uma futura unidade com contrato
diferente; não descobrir nem trocar versões de abas automaticamente.

No Django Admin, mostrar o nome da unidade nos registros de customização e
FireAds por meio do relacionamento; não duplicar nome_unidade em outra coluna.
Permitir busca/filtro pela unidade e validação clara das URLs e abas.

Criar/editar customização ou FireAds não deve disparar novamente as operações
de cadastro Meta já associadas à criação de unidade.

### 4.4. conversa

Adicionar `id_chat`, FK para o vínculo cliente/unidade descrito na seção 4.7.
Preencher todas as conversas existentes e exigir NOT NULL depois da validação.
Manter `id_cliente`/`id_unidade` e sua consistência com o chat no banco.

Manter a coluna planejada **origem_fireads** com valores canônicos google, meta
e organico; NULL para conversas sem integração na abertura. Os nomes exibidos
são Google Ads, Meta Ads e Orgânico. No texto do usuário, google_ads/meta_ads
designam essas mesmas origens; não criar uma segunda coluna de canal redundante.

Adicionar **lead_no_dash**, Booleano anulável, equivalente ao controle de entrega
da conversa ao destino. Semântica técnica proposta:

| Valor | Significado |
| --- | --- |
| NULL | Entrega não aplicável/não materializada; inclusive histórico anterior à ativação. |
| false | Entrega desta conversa ao dashboard pendente ou ainda sem confirmação. |
| true | Observações desta conversa confirmadas no dashboard, por cadastro ou update. |

A presença inicial no formulário não marca lead_no_dash=true: ainda falta enviar
o resultado do atendimento. Essa presença ficará no estado de consulta FireAds.

Adicionar `contexto_fireads JSONB NULL`: retrato enxuto da decisão adotada por
esta conversa, inclusive resultado, referência da consulta, origem e os três
dados importados quando válidos. Deve identificar e-mail resolvido nessa abertura.
Nas conversas sem integração/histórico não convertido, permanece NULL.
Nas conversas integradas com resultado orgânico, registra o motivo sem aproveitar
parcialmente dados inválidos. Não guardar o formulário inteiro nem credenciais.

O retrato fica independente da linha atualizável de consulta: atualizar a
consulta no próximo atendimento não modifica e-mail, nome ou destino históricos
do anterior. A leitura do Funil usa os dados daquela conversa/entrega.
Correções aceitas dentro da conversa prevalecem sobre o retrato inicial conforme
os mecanismos de coleta; não sobrescrever correções com uma nova leitura.

Separar nesse JSON a evidência inicial de importação dos dados efetivamente
aceitos no atendimento. Nas conversas integradas, inclusive orgânicas, preservar
nome, idade e resultado da coleta de e-mail do titular conforme forem aceitos,
na mesma transação da respectiva coleta. Dados não coletados continuam pendentes;
não inicializá-los pelo cadastro global. Profissão, dependente e triagem já têm
vínculos próprios à conversa e não precisam de cópias redundantes nesse JSON.
Isso resolve uma lacuna da leitura atual do Funil, que ainda busca nome/idade em
cliente: outro atendimento pode alterar esses valores antes da preparação da entrega.
O formatador deve usar o retrato desta conversa; depois de preparada a entrega,
usa a cópia integral descrita na seção 7.3. Histórico legado mantém sua leitura atual.

### 4.5. Nova tabela consulta_fireads — última consulta por chat

A tabela foi aprovada pelo responsável, com vínculo ao chat permanente.
Uma linha representa a consulta atual daquele par cliente/unidade; cada nova
conversa integrada atualiza a mesma linha, preservando `id_consulta`.
Não criar uma consulta diferente por mensagem nem vincular a linha somente à conversa.

Estrutura técnica a concretizar na migração:

| Campo | Tipo/regra | Finalidade |
| --- | --- | --- |
| id_consulta | Chave primária inteira. | Identidade da linha, preservada entre novas conversas do mesmo chat. |
| id_chat | FK NOT NULL, UNIQUE. | No máximo uma consulta atual por chat. |
| id_integracao_fireads | FK NOT NULL. | Integração da mesma unidade do chat. |
| id_conversa_referencia | FK NOT NULL. | Conversa daquele chat a que o resultado atual pertence. |
| consulta_concluida | Booleano, FALSE enquanto não concluída. | Não confundir linha criada com resultado já obtido. |
| resultado | pendente, importado, ausente, incompleto, erro ou ambiguidade. | Resultado operacional da tentativa. |
| origem_fireads | google, meta, organico ou NULL enquanto pendente. | Classificação da tentativa; não substitui a origem histórica da conversa. |
| aba_origem | Texto ou NULL. | Aba do formulário selecionado. |
| id_registro_origem | Texto ou NULL. | ID externo do registro, quando houver. |
| data_formulario | TIMESTAMPTZ ou NULL. | Instante usado para comparar os cadastros. |
| nome_titular | Texto ou NULL. | Nome validado para importação. |
| email_titular | Texto ou NULL. | E-mail validado para importação. |
| status_dependente | Booleano ou NULL. | Destino validado; NULL não significa titular. |
| consultado_em | TIMESTAMPTZ ou NULL. | Momento da última consulta concluída. |
| ultimo_erro | Texto ou NULL. | Diagnóstico resumido quando houver. |
| criado_em / atualizado_em | TIMESTAMPTZ. | Auditoria da linha. |

Para chats de unidades integradas, garantir a linha ao iniciar a primeira
conversa sob essa integração; para os demais chats, não criar consulta.
Na ativação, não consultar todo o histórico em massa: obter/criar a linha quando
o próximo atendimento começar. Sem integração, não exigir uma linha fictícia.

Regras de abertura e retry:

1. Obter/criar o chat e a nova conversa, mantendo uma ativa por par.
2. Reservar o processamento da conversa pelo mecanismo atual.
3. Se `conversa.contexto_fireads` já foi concluído, usá-lo; não sobrescrever
   o estado com consulta de uma conversa posterior.
4. Se a linha de consulta aponta para esta conversa e está concluída, recuperar
   o resultado e finalizar sua aplicação/persistência coerente.
5. Se esta é outra conversa do mesmo chat, atualizar `id_conversa_referencia`,
   limpar o resultado anterior e marcar pendente; realizar uma nova consulta.
6. Se a tentativa caiu antes da conclusão, refazer a consulta e atualizar a mesma
   linha. Antes de gravar, revalidar referência da conversa e posse do processamento.
7. Persistir a conclusão, o retrato da conversa e a importação dos dados de forma
   atômica. Retry após isso reutiliza a decisão; não reconsulta dados diferentes.

`erro`, `ausente` e `incompleto` também concluem a decisão inicial como orgânico.
Não deixar um retry comercial mudar a rota depois que o atendimento já começou.
Um retry antigo não pode atualizar a linha reservada para uma nova conversa:
usar a referência de conversa e a proteção de versão/lock existentes.

Invariantes da persistência: a conversa de referência pertence ao mesmo chat e
a integração pertence à unidade desse chat. Uma FK isolada para cada ID não
comprova esses relacionamentos: validar sob a reserva e incluir as restrições
relacionais correspondentes na migração. `consulta_concluida=false` corresponde
a `resultado=pendente`; resultados finais, inclusive erro e ambiguidade, concluem
a decisão. `importado` exige os três dados validados e origem google/meta; os
demais resultados finais usam organico, sem dados parcialmente importados.
Uma decisão orgânica concluída não dispara nova consulta a cada retry/mensagem.

Não salvar o formulário inteiro. _row não é identidade imutável do contato.

O Funil hoje recupera e-mail do histórico 10→11, com fallback em cliente.email.
Pular a etapa 10 exige preservar o e-mail importado na conversa e adaptar sua
leitura, sem inventar mensagens no histórico. Uma correção efetivamente aceita
durante o atendimento deve prevalecer sobre o dado inicialmente importado.

cliente.email é único e o cadastro é compartilhado. Conflito não autoriza unir
pessoas ou alterar outro cadastro: recusar o aproveitamento de forma controlada,
registrar a causa e seguir o atendimento completo, sem retry infinito.

Não pular a etapa 10 apenas porque `cliente.email` está preenchido: ele pode vir
de outro atendimento ou unidade. Exigir e-mail válido adotado nesta conversa,
com origem registrada. Atualizar o cadastro global quando houver coleta/importação
válida; não limpar globalmente seu e-mail ao abrir uma conversa, pois isso poderia
afetar atendimento simultâneo em outra unidade. O contexto desta conversa inicia
a coleta pendente quando não houver importação válida.

### 4.6. envios_dash

Criar fila persistida com id_conversa UNIQUE, espelhando o comportamento da tabela
existente **chatbot.funil_envios** (nome real no projeto). Não renomear a fila
atual apenas porque ela foi chamada de envios_funil na conversa.

Base de campos:

- id_envio_dash e id_conversa (FK).
- status: pending, processing ou sent.
- attempt_count, next_attempt_at e processing_started_at.
- enviado_em, ultimo_erro e resposta_dash.
- criado_em e atualizado_em.

Acrescentar o mínimo necessário para uma entrega reproduzível: integração/destino
da entrega, texto integral das observações e dados de cadastro considerados.
Usar TEXT/JSON adequado, sem truncar as observações. A forma final desses campos
deve ser definida no SQL e documentada junto ao código.

Guardar separadamente o texto imutável enviado ao Funil e a identificação estável
do bloco dessa conversa. Para a tentativa no dashboard, preservar o valor anterior
lido e o valor completo preparado/enviado, permitindo conferência após timeout.
Esses dados pertencem ao retrato da entrega, não a uma nova tabela de campanhas.
Em retry, reler a célula antes de decidir: um payload antigo não autoriza apagar
anotações externas inseridas depois da tentativa anterior.

Fila por conversa não significa nova linha por conversa na planilha: um contato
já existente recebe somente a atualização da Observação.

Reservar tarefas, recuperar processamento abandonado e concluir fila/lead_no_dash
atomicamente com o padrão já utilizado pelo Funil. A unicidade por conversa evita
duas tarefas locais iguais, mas não substitui a busca do contato na planilha.

### 4.7. Nova tabela chat — antecipada da preparação da IA

Implementar nesta entrega FireAds somente o vínculo permanente, válido para
todas as unidades. Isso permite ligar consulta_fireads diretamente ao chat e
reutilizar o mesmo vínculo nas futuras tabelas de uso da IA.

| Campo | Tipo/regra | Finalidade |
| --- | --- | --- |
| id_chat | SERIAL PRIMARY KEY. | Identifica o par cliente/unidade. |
| id_cliente | INTEGER NOT NULL, FK. | Cliente do vínculo. |
| id_unidade | INTEGER NOT NULL, FK. | Unidade do vínculo. |
| criado_em | TIMESTAMPTZ NOT NULL DEFAULT NOW(). | Criação do vínculo. |

Exigir UNIQUE (id_cliente, id_unidade). Obter/criar com proteção contra
concorrência: duas mensagens não podem gerar dois chats para o mesmo par.
Um chat pode possuir várias conversas; conserva-se uma conversa ativa por par.

Adicionar/preencher `conversa.id_chat` sem retirar os IDs diretos nesta entrega.
Garantir a correspondência dos três IDs por FK composta para chave única
compatível em chat; não confiar somente na validação Python.
Não mudar o nome/telefone de um cliente para criar outro chat artificialmente.

Relacionamentos: cliente/unidade → chat → conversas; chat → consulta_fireads
(zero/uma, aplicável à integração); conversa → envios_dash (zero/um).
Futuras cotas da IA se ligam ao mesmo id_chat, sem recriar esse vínculo.

## 5. Consulta inicial, seleção e classificação

### 5.1. Quando consultar

Toda **nova conversa** de uma unidade com integração ativa recebe a consulta,
antes da primeira resposta, independentemente de atendimentos anteriores terem
terminado por idade, follow-up, satisfação ou outro motivo.

Não consultar a cada mensagem da mesma conversa. Preservar o controle de decisão
concluída para retries e mensagens seguintes. Conversas encerradas continuam
encerradas; criar uma nova pelos mecanismos atuais, respeitando bloqueios e a
regra de uma conversa ativa por cliente/unidade.

Ativar a integração não inicia uma importação em massa nem reinicia conversas
em andamento. Preencher formulário sem falar com o bot não cria conversa ou
entrega do chatbot ao Funil/dashboard.

### 5.2. Telefone e registro mais recente

1. Usar o telefone recebido da Meta para consultar as duas fontes da unidade.
2. Normalizar país/DDD e formatação conforme as regras existentes, priorizando
   correspondência exata. Variantes com/sem nono dígito exigem correspondência
   segura; não aproximar telefones diferentes nem trocar o número do WhatsApp.
3. Reunir os registros desse contato nas duas abas.
4. Selecionar o mais recente pela data do formulário, comparando instantes
   equivalentes; a posição da linha e a versão da aba não definem recência.
5. Validar os três dados daquele registro e usar sua fonte para a origem.
   Não juntar nome de um registro, e-mail de outro e destino de um terceiro.

Se o registro mais recente estiver incompleto/inválido, seguir orgânico,
sem buscar um registro antigo “melhor”. Cópias equivalentes podem ser deduplicadas.
Para empate conflitante ou identidade ambígua, registrar o diagnóstico e seguir
a opção conservadora de atendimento completo.

### 5.3. Datas, sem prazo de validade

**Não existe mais limite de 30 dias.** Uma única correspondência antiga, completa
e válida pode ser aproveitada. A data continua útil para comparar múltiplos
registros, não para expirar o contato.

**Escrita:** respeitar as datas e o fuso da FireAds. Cadastro novo omite Data/Hora
e deixa o script preenchê-la; atualização envia apenas Observação e preserva a
data já registrada. Não alterar configurações de fuso da planilha/Apps Script nem
copiar o fuso Meta da unidade para lá. unidade.id_fuso/nome_fuso continuam com sua
finalidade atual, independentes do dashboard.

**Leitura para escolher o mais recente:** interpretar os formatos recebidos,
respeitando offsets explícitos. A consulta desta revisão recebeu created_time
Meta como ISO 8601 com offset -05:00; Google retornou Data/Hora em dd/MM/yyyy HH:mm,
sem offset. O código fornecido formata datas usando getSpreadsheetTimeZone(),
mas a resposta consultada não informa esse fuso. Para comparar fontes diferentes,
é necessário conhecer esse dado, sem modificá-lo ou inferi-lo da WABA/VM.
Normalizar instantes internamente não muda o horário salvo/exibido pela FireAds.
Não corrigir a diferença aparente de testes somando horas fixas. Horário ausente
ou reduzido a 00:00 não permite inventar uma ordem entre eventos empatados.

Data ausente/ilegível que impeça escolher entre registros concorrentes deve
produzir diagnóstico e atendimento completo, sem uma escolha aleatória.
A ausência de uma data isolada não deve recriar indiretamente a expiração removida;
se houver apenas uma correspondência inequívoca e completa, não há disputa de
recência. Datas futuras incoerentes exigem validação do contrato antes de ordenar.

### 5.4. Resultado inicial

| Resultado | origem_fireads | Atendimento |
| --- | --- | --- |
| Registro Google selecionado e três campos válidos | google | Importa e começa na profissão. |
| Registro Meta 7.2 selecionado e três campos válidos | meta | Importa e começa na profissão. |
| Mesmo cadastro, mesmo que tenha mais de 30 dias | Fonte selecionada | Mesma importação, sem expiração. |
| Não encontrado nas fontes | organico | Completo, desde o nome. |
| Nome, e-mail ou destino inválido/ausente | organico | Completo, sem importação parcial. |
| Falha HTTP, timeout, JSON inválido, aba incorreta ou consulta incompleta | organico | Completo, com diagnóstico técnico. |
| Configuração ativa inválida | organico | Completo, com diagnóstico técnico. |
| Unidade sem integração na abertura | NULL | Comportamento atual. |

Se uma fonte falhar e a outra responder, a consulta está incompleta e não permite
garantir qual registro é o mais recente. Aplicar a regra aprovada de erro:
orgânico, sem aproveitamento parcial.

Essa classificação é operacional; não prova que o cliente nunca viu um anúncio.
Guardar o motivo da decisão para distinguir ausência, erro e dados inválidos.
Depois de concluída, não reclassificar a conversa porque o formulário apareceu
mais tarde. A próxima conversa fará sua própria consulta.

## 6. Mapeamento dos formulários e atendimento

### 6.1. Dados aproveitados

Importar somente nome do titular/contato, e-mail do titular e destino do atendimento.
O telefone do WhatsApp já identifica o cliente e não será perguntado.

Usar o validador de nome existente para primeiro nome simples ou composto;
não dividir simplesmente no primeiro espaço. Nome/e-mail do formulário não são
o nome/e-mail do dependente. O false padrão de status_dependente não comprova
escolha: registrar que o destino foi validado/importado.

Descartar objetivo, faixa etária, cidade, bairro e decisor para preencher coletas.
Continuar perguntando a idade exata e realizando a triagem.
Formulário preenchido não equivale a aceitar a oferta do chatbot.

### 6.2. Google — P1 resolvida

O print atualizado confirma:

| Opção | Destino |
| --- | --- |
| Para mim | Titular. |
| Para meu pai/mãe | Dependente. |
| Para meu avô/avó | Dependente. |
| Para outra pessoa | Dependente. |

O contrato observado até agora retorna Perfil/Faixa. Conferir uma submissão nova
na implementação para registrar exatamente a chave e os valores serializados
depois da alteração do formulário. A decisão de negócio está resolvida; falta
apenas verificar sua representação na API.

Conferência somente de leitura em 07/10 nesta revisão: Perfil/Faixa ainda contém
Adolescente (6), Pessoa com 60 anos ou mais (17), Adulto (14), vazio (2) e Criança (1).
Nenhum dos 40 registros retornados comprova ainda o formato serializado das opções
novas. Adaptar o leitor ao dado realmente recebido quando houver uma submissão
nova; não impor outro formato ao formulário nem criar lead de teste de produção
apenas para encerrar essa verificação.

Há registros antigos com Adulto, Criança, Adolescente ou Pessoa com 60 anos ou mais.
Esses valores não comprovam quem vai treinar. Não converter automaticamente
Adulto em titular, nem qualquer faixa em dependente. Aplicar a regra de cadastro
incompleto/inválido para o destino, mesmo que o formulário antigo seja encontrado.

### 6.3. Meta 7.2 — P2 resolvida

| Opção | Destino |
| --- | --- |
| Para mim | Titular. |
| Para meu pai ou minha mãe | Dependente. |
| Para meu filho ou filha | Dependente. |
| Para mim e outra pessoa | Dependente. |

O adaptador deve mapear valores reais explícitos, incluindo para_mim e mim_e_outra
observados em para_quem. Valores não reconhecidos ou textos de teste não viram
dependente por padrão. Continuar com um único participante do atendimento.

### 6.4. Sequência no worker_flow

1. Preservar assinatura, filtros, bloqueios, turnos de mensagem e fila atuais.
2. Obter/criar o chat, carregar a conversa e configuração da unidade já reorganizada.
3. Se houver decisão FireAds concluída para esta conversa, continuar usando-a,
   sem importar o resultado atual de outra conversa do mesmo chat.
4. Sem integração, executar a abertura normal.
5. Com integração e nova conversa ainda sem decisão, consultar as duas fontes
   fora de uma transação longa.
6. Selecionar e validar os três dados e a origem.
7. Revalidar posse/estado e referência da conversa; persistir atomicamente
   consulta_fireads, contexto_fireads desta conversa, origem e os dados importados
   quando válidos. Não deixar importação pela metade.
8. Preparar a primeira resposta da rota resultante e usar o envio/persistência atuais.

A consulta é responsabilidade do worker, não do webhook.
Os timeouts totais, incluindo redirecionamentos e as duas fontes, devem caber no
ciclo com reserva para responder e persistir. As proteções atuais são de cerca
de 110 segundos na conversa e 120 na fila: definir um orçamento total coerente,
sem multiplicar cegamente o timeout experimental de cada chamada.

### 6.5. Saudação especial da profissão

Mensagem de referência, com os ajustes de gênero/nome já usados no projeto:

> Olá, {nome}! Seja muito bem-vindo(a)! Sou {artigo_agente} {nome_agente},
> assistente do {nome_unidade}. Vi que você já preencheu um dos nossos formulários.
> Para continuarmos com sua reserva por cortesia da unidade, precisamos fazer
> mais algumas perguntinhas, ok? Me diz, qual é a sua profissão hoje?

Essa abertura pertence à **etapa 4 — profissão** e só acontece quando os três
dados foram aproveitados. Repetições/tratamentos da etapa 4 usam suas mensagens
normais, sem repetir a apresentação. Em ausência/erro/dado inválido, perguntar
o nome pela abertura atual. Registro antigo válido também recebe a abertura especial.

### 6.6. Coletas e mapa de transições

| Parte do atendimento | Com importação completa |
| --- | --- |
| Etapa 1: nome do titular | Resolvida pelo formulário; a saudação continua existindo na abertura. |
| Etapa 2: para quem é | Resolvida pelo mapeamento aprovado. |
| Etapa 3: confirmação do destino | Dispensada pela escolha explícita importada. |
| Etapa 4: profissão | Primeira pergunta; coleta mantida. |
| Etapa 5: nome do dependente | Mantida na rota dependente. |
| Etapa 6: idade exata | Mantida, incluindo todas as restrições/exceções. |
| Etapas 7 a 9: oferta, aceite e retomada | Preservadas. |
| Etapa 10: e-mail do titular | Dispensada pelo e-mail válido importado nesta conversa. |
| Etapa 11 e triagem 12 a 17 | Preservadas. |
| Turno/comercial 18–19, link 20 e satisfação 21–24 | Preservados conforme a rota. |

Tratar explicitamente três adaptações diferentes:

1. **Inicialização na etapa 4:** hoje `resolver_movimento_conversa` e
   `inicializar_conversa_resposta_bot` só aceitam a etapa 1 quando ainda não há
   etapa persistida. Ampliar ambos com uma abertura FireAds controlada, exigindo
   decisão importada válida da própria conversa. Inicialização não é uma aresta
   1→4 nem uma transição com origem NULL. Preparar a saudação da profissão e
   registrar a etapa/pergunta enviada na conclusão do envio, seguindo a recuperação
   existente. Não interpretar o primeiro “Olá” como resposta de profissão nem
   persistir que essa pergunta foi enviada antes do sucesso do sender.
2. **Efeitos do destino importado:** as etapas 2/3 hoje criam o registro vazio
   do dependente. Como serão dispensadas, a importação precisa persistir o destino
   e garantir esse registro único da conversa de forma atômica e idempotente.
   Não importar nome de familiar nem reutilizar dependente de outra conversa.
   Na etapa 5 o código atual atualiza um registro existente; sem isso a coleta
   do nome falharia. A rota titular não deve ganhar dependente fictício.
3. **Dispensa da etapa 10:** adicionar eventos distintos e guardas para 7→11
   e 9→11 quando o e-mail foi validamente importado nesta conversa. Preservar
   os eventos atuais 7→10 e 9→10 para as demais situações. Respeitar a unicidade
   (origem, evento) do mapa e preparar a mensagem correta da etapa 11; não chamar
   um efeito antigo que tente validar a resposta de aceite como se fosse e-mail.

Reutilizar as operações de persistência necessárias, sem produzir sucessivos
envios, respostas fictícias do cliente ou histórico das etapas dispensadas.
Retry com decisão importada persistida e sem resposta concluída recupera a
mesma abertura especial; resposta já registrada segue a recuperação normal.

O catálogo mantém 24 etapas. As 28 transições são a base anterior à FireAds;
os novos caminhos ampliam esse mapa e precisam constar no SQL incremental, no
DDL de instalação limpa e nas verificações. Não executar o seed que faz
TRUNCATE de etapa_transicao sobre a base existente.

Não basta trocar id_etapa_atual; verificar todos os efeitos e consumidores.
Unidades sem integração e conversas orgânicas mantêm o mapa atual.
A importação não conta como respostas do cliente nem tentativas inválidas.

Manter tratamentos universais de dúvida financeira, reforço escolar e demais
regras atuais; revisar a entrada que contenha pergunta junto da saudação.
Não conceder navegação livre/arrependimento da futura IA nesta integração.
Se o cliente contestar dados, preservar os tratamentos disponíveis e não reaplicar
a importação por cima de uma correção aceita no atendimento.

## 7. Funil: canal, observações e momento da entrega

### 7.1. Canal por origem

| origem_fireads | Exibição / valor da linha Canal de venda | Código Funil |
| --- | --- | --- |
| google | Google Ads | 113336 |
| meta | Meta Ads | 113340 |
| organico | Orgânico | 113481 |

Complemento confirmado em 07/10: a fonte Google da FireAds pode receber contatos
da landing page de Santo André ou de anúncios Google. Manter a classificação
pela aba e o canal aprovados: registro válido selecionado dessa fonte recebe
google/113336, sem criar uma quarta origem ou exigir prova de clique pago.
Isso identifica a fonte comercial combinada; não comprova, por si só, tráfego
pago nem autoriza inventar anúncio/campanha. Se a consulta não permitir aproveitar
os três dados, continua valendo o fallback orgânico já definido.

Usar constante/função Python compartilhada, sem tabela de canais.
Resolver o código para montar_url_envio/ForceCodeChannel. Se houver Code_Channel
no payload, mantê-lo consistente com a URL. Não deixar a constante Meta antiga
sobrescrever Google ou Orgânico.

Revisar também o personalizado **Origem do lead**: hoje o formatador usa a
constante `ORIGEM_LEAD_CHATBOT = "Meta Chatbot"`. Para conversas FireAds,
derivar o texto da mesma origem (Google Ads, Meta Ads ou Orgânico), validando o
formato aceito pelo campo do CRM. Não corrigir somente ForceCodeChannel e deixar
Google/Orgânico rotulados como Meta nesse outro campo. Preservar o contrato
legado para unidades sem FireAds e os marcadores da ApiCarrossel; não confundir
esses marcadores de payload com os códigos numéricos da URL.

Nas conversas integradas, acrescentar exatamente a linha correspondente:

~~~text
Canal de venda: Google Ads
~~~

ou Meta Ads ou Orgânico. Preservar o restante das observações: contato,
titular/dependente, idade, profissão, triagem e turno escolhido quando aplicável.

Unidades sem FireAds continuam usando codigo_canal_venda da configuração atual
do Funil. Não exibir origem fictícia nelas. Conversas históricas sem origem
permanecem no comportamento legado, sem reclassificação retroativa.

### 7.2. Elegibilidade atual preservada

- Com link: etapas 20 a 24.
- Sem link: etapa 19 e etapas 21 a 24.
- Etapa 18, que pergunta turno, ainda não basta para envio.
- Preservar demais filtros e condições existentes do Funil.

“Concluir o atendimento” nesta entrega significa atingir os marcos atuais de
elegibilidade; não criar exigência nova de aguardar o fim da satisfação.
Formulário completo sozinho não autoriza exportar.

### 7.3. Um bloco do atendimento para os dois destinos

Gerar as observações uma vez para a entrega e persistir uma cópia completa antes
do primeiro envio ao Funil. Usar essa mesma string no personalizado Observações
do Funil e como conteúdo do bloco do chatbot na Observação do dashboard.
O campo completo do dashboard pode ser maior, pois preserva o texto anterior
da FireAds/comercial e os blocos de outros atendimentos. A igualdade exigida é
do conteúdo do bloco desta conversa com o texto enviado ao Funil, não da célula
inteira com o personalizado do CRM.

A fila envios_dash pode armazenar esse retrato com os dados necessários ao
cadastro, associado à mesma conversa. O processamento do Funil deve consumir o
mesmo texto persistido, inclusive em retry. Definir a estrutura final na implementação.

Não reconstruir o texto a partir de um recibo abreviado: a resposta do Funil hoje
pode ser truncada. Não regenerar observações diferentes depois do sucesso do
Funil por mudança de etapa, de cadastro ou de configuração.

O worker já conhece o texto enviado. Não é necessário consultar novamente a API
do Funil para copiá-lo. A sequência lógica permanece Funil → dashboard.

Preservar o criativo já presente no dashboard não o adiciona automaticamente às
observações do Funil. Importar/enriquecer a oportunidade com metadados de campanha
seria outra ampliação; esta correção conserva o texto externo onde já existe.

## 8. Cadastro e atualização no dashboard

### 8.1. Localizar antes de decidir

Após confirmação do envio ao Funil, consultar a aba geral da integração correta.
Usar telefone normalizado como chave principal de busca e e-mail/dados conhecidos
para conferir a identidade. Esse passo vale para Google, Meta e Orgânico.

| Situação no destino | Operação |
| --- | --- |
| Um contato correspondente e identidade consistente | Preservar a Observação atual e acrescentar o bloco desta conversa, se ainda ausente. |
| Não existe correspondência, consulta completa e sem conflito | Cadastrar uma linha com dados disponíveis e observações integrais. |
| Só existe no formulário | Cadastrar na aba geral mantendo o canal Meta/Google da conversa. |
| Já existe na aba geral, mesmo sendo orgânico | Mesma preservação e acréscimo do bloco, sem criar outro contato. |
| Consulta ao destino falhou/incompleta | Manter pendente; não interpretar falha como autorização para cadastrar. |
| Contatos duplicados/identidade conflitante | Registrar conflito e manter entrega pendente para resolução; não escolher arbitrariamente nem criar mais uma linha. |

A regra “falha = orgânico” pertence à **consulta inicial do atendimento**.
Na **consulta de entrega**, falha significa retry da entrega, pois cadastrar
às cegas criaria duplicação.

Uma divergência de e-mail, por exemplo, não autoriza automaticamente duplicar
o telefone. Conferir a identidade e o contexto; se não for possível resolvê-la
com segurança, registrar pendência. Não fundir pessoas pelo e-mail isoladamente.

### 8.2. Registro existente

O POST contém somente updates.Observação. O valor enviado deve conter o texto
anterior integralmente, seguido de separação visual e do bloco desta conversa.
Essa regra vale para qualquer contato existente, inclusive um orgânico de
atendimento anterior: preservar criativos, campanhas e notas comerciais, sem
limpar espaços/quebras do conteúdo antigo, resumi-lo ou reinterpretá-lo.

A preservação foi explicitamente confirmada também para Google Ads e landing
page em 07/10. Inclusive uma Observação contendo apenas `0`, como no print do
responsável, é conteúdo existente e deve permanecer acima do novo bloco.
Não usar uma verificação de valor verdadeiro/falso para decidir se a célula está
vazia: zero numérico ou textual não é ausência. Converter conforme o contrato
de leitura, preservando sua representação, sem interpretar `0` como campanha,
como descarte autorizado ou como resposta válida de "para quem é".

Exemplo ilustrativo de exibição:

~~~text
FR002

Observações do atendimento — conversa 123
<texto integral enviado ao Funil>
~~~

O bloco recebe delimitadores de início/fim e referência estável da integração/
conversa, definidos no contrato Python, para distingui-lo de anotações livres.
O conteúdo interno é exatamente a string congelada enviada ao Funil. Não usar
nome, telefone, timestamp da tentativa ou igualdade do texto como chave do bloco:
uma nova conversa pode produzir o mesmo texto, mas é outra entrega.

Sequência da operação:

1. Reconsultar o contato na aba geral e obter o conteúdo atual completo.
2. Se o bloco identificado desta conversa já estiver presente e corresponder
   integralmente ao texto esperado, reconhecer a entrega sem acrescentar de novo.
3. Se estiver ausente, compor conteúdo atual + separador + bloco e enviar o update.
4. Se houver o mesmo identificador com conteúdo divergente/incompleto, registrar
   conflito e manter pendente; não duplicar o bloco nem sobrescrever possível
   edição humana. Uma correspondência textual sem identificador não basta.
5. Conferir sucesso/identidade conforme o contrato; resultado desconhecido exige
   nova leitura em retry, considerando o cache, antes de repetir a alteração.

Cada conversa nova pode acrescentar um novo bloco; retry da mesma não o repete.
Observação realmente vazia recebe somente o bloco. Se o campo acumular conteúdo
além do limite aceito pelo destino, manter pendente e registrar o diagnóstico,
sem cortar campanhas, anotações antigas ou a observação integral do atendimento.
Nome, telefone, e-mail, data, origem/canal de captação, feedback e demais campos
da linha existente permanecem como estão.

O canal do novo atendimento fica explícito dentro da Observação. Isso permite
preservar o Canal originalmente salvo na planilha enquanto registra o canal
usado no Funil para esta conversa.

### 8.3. Registro novo

Preencher os campos disponíveis e semanticamente corretos:
Nome do contato, Email, WhatsApp, Perfil/Faixa, Canal e Observação.
Na Observação, usar o bloco identificado da conversa com o texto integral do
Funil, também para reconhecer um cadastro cujo retorno se perdeu. Omitir Data/Hora
e qualquer parâmetro de fuso; o script preenche a data. Não inventar criativo.
Idade/dados do dependente podem compor a descrição apropriada, conforme o
formatador existente, sem substituir o titular pelo dependente como contato.

Não inventar consentimento, bairro, objetivo, classificação de temperatura ou
feedback comercial. Não reutilizar marcadores “TESTE” dos utilitários no runtime.
Quando as regras normais permitirem ausência de e-mail, não inventar endereço:
usar o formato vazio aceito pelo contrato de cadastro.

O e-mail é obrigatório no formulário para dispensar a coleta, mas essa exigência
não muda a regra do atendimento orgânico configurada para a unidade.

### 8.4. Duplicação, retentativas e linhas mutáveis

A consulta no início da conversa melhora o atendimento. A prevenção de cadastros
duplicados depende também da conferência no destino imediatamente antes da escrita.

Usar reserva de tarefas e serialização local por integração/telefone para evitar
dois envios locais concorrentes do mesmo contato. Em retry após resultado
desconhecido, procurar o cadastro antes de decidir por outro append.

O Apps Script fornecido não possui chave de idempotência de cadastro nem operação
atômica “criar se não existe”. A conferência seguida de POST reduz o risco, mas
não promete ausência absoluta de duplicação diante de timeout, cache ou outro
gravador externo. Se precisar dessa garantia, adaptar o servidor para deduplicar
sob lock com uma chave estável; não atribuir essa garantia ao cliente Python.

_row é uma posição e pode mudar se alguém ordenar/excluir linhas. Reconsultar
o alvo antes do update. A garantia contra mudança entre leitura e gravação exige
validação de identidade dentro do Apps Script, além do row; o contrato atual não
faz essa comparação. Registrar e tratar essa limitação na implementação.

Preservar conteúdo exige também uma leitura atual: não reutilizar como base a
Observação lida na abertura do atendimento. O contrato atual executa setValue;
o lock do POST não abrange o GET anterior do Python nem compara a versão da célula.
Assim, edição externa entre leitura e gravação ainda pode sofrer sobrescrita.
Serialização local, releitura e conferência reduzem o risco, sem garantia atômica.
Uma garantia estrita requer evolução no Apps Script para acrescentar/deduplicar
sob o mesmo lock ou comparar o valor anterior e recusar conflito. Essa evolução
externa não foi implementada nem presumida neste plano. Diante de leitura
desatualizada conhecida ou conflito detectado, adiar a tentativa em vez de gravar.

Também ordenar entregas do mesmo contato para que um retry antigo não sobrescreva
as observações de uma conversa mais recente. Processar em ordem por contato,
respeitando pendências anteriores, sem bloquear contatos de outras unidades.
Não substituir silenciosamente uma entrega antiga pelo texto de outra conversa.

## 9. worker_funil e as duas filas

O mesmo worker coordena as duas integrações, com repositórios e clientes separados.
Não copiar indiscriminadamente todo o worker nem acoplar os sucessos dos destinos.

### 9.1. Ciclo de processamento

1. Materializar conversas elegíveis ao Funil pelo mecanismo existente.
2. Para conversas integradas, preparar a entrega ao dashboard e o retrato completo
   das observações/dados. Impedir duplicidade local por id_conversa.
3. Reservar/processar o envio ao Funil com seus controles atuais.
4. Se falhar no Funil, registrar a falha, continuar os próximos itens e não enviar
   essa conversa ao dashboard antes da confirmação do Funil.
5. Se o Funil confirmar, concluir funil_envios/lead_no_funil pelos mecanismos atuais.
6. Processar envios_dash pendentes cuja entrega ao Funil já esteja confirmada:
   consultar o destino, decidir append/update, enviar e validar a resposta.
7. Em sucesso, concluir envios_dash e lead_no_dash na mesma transação local.
8. Em falha, voltar a pending, incrementar tentativas/registrar erro e agendar
   o próximo ciclo; continuar as outras entregas.
9. Processar pendências antigas do dashboard mesmo se não houver novas
   oportunidades para enviar ao Funil neste ciclo.

Somente conversas de unidades com FireAds e integração Funil aplicáveis geram
essas entregas ao dashboard. Unidades com apenas Funil seguem como hoje.
A consulta inicial ao formulário e a entrega são responsabilidades diferentes.

### 9.2. Falhas e retomadas

| Estado | Próxima ação |
| --- | --- |
| Funil pendente; dashboard ainda não liberado | Tentar Funil conforme sua fila. |
| Funil enviado; dashboard pendente | Tentar somente dashboard. |
| Funil e dashboard enviados | Nenhum reenvio por retry do worker. |
| Processo caiu com dashboard em processing | Recuperar pelo mecanismo de lease e conferir o destino antes de repetir cadastro. |
| Resposta dashboard success=false | Falha, mesmo com HTTP 200. |
| Timeout após POST | Resultado desconhecido; conferir antes de repetir. |
| Integração desativada depois da criação da tarefa | Não fazer nova escrita enquanto desativada; preservar pendência/histórico e registrar motivo. |

A consulta atual de candidatos do Funil exclui lead_no_funil=true.
A entrega pendente ao dashboard precisa de consulta própria ou do retrato salvo,
pois reutilizar somente a consulta atual faria desaparecer as conversas que já
chegaram ao Funil.

### 9.3. Intervalos, reserva e retomada

Configuração atual observada: ciclo do Funil de 1800 segundos (30 minutos),
limite de 100 por ciclo, lease de 900 segundos e retry de Funil de 3600 segundos.
São defaults configuráveis, não confirmação dos valores em produção.

Para o dashboard, respeitar o pedido de nova tentativa no próximo ciclo:
definir next_attempt_at e processamento de forma que falhas não sejam tentadas
em loop no mesmo ciclo. Não copiar cegamente o retry de 1 hora do Funil para o
dashboard. Preservar o retry do Funil já existente.

Separar limites/tempos de processamento para que falha ou lentidão do dashboard
não impeça todas as entregas ao Funil. Não manter transação de banco aberta
durante HTTP. Reservas e recuperação devem seguir o padrão existente de
FOR UPDATE SKIP LOCKED e processamento abandonado.

## 10. Migração e compatibilidade do projeto

Os modelos usam managed=False: mudar o model não muda o banco.
A implementação exige SQL incremental e verificação dos dados, sem seeds que
apaguem ou recriem unidades/conversas.

Sequência prevista:

1. Criar atendimento_customizado, integracao_fireads, chat, consulta_fireads,
   envios_dash e os campos id_chat, origem, entrega e contexto FireAds de conversa.
2. Copiar as configurações atuais de todas as unidades para atendimento_customizado,
   preservando IDs de unidade, valores, regras e vínculos.
3. Criar um chat por par distinto cliente/unidade de todas as conversas existentes;
   preencher conversa.id_chat. Validar contagens, correspondência e constraints
   sem apagar histórico. Validar também uma customização por unidade e valores movidos.
4. Atualizar consultas, models, Admin e montagem de contexto para buscar os
   campos na nova localização, preservando o contrato dos consumidores.
5. Remover as colunas antigas apenas na migração coordenada com o código adaptado.
   Preparar rollback que preserve dados de configuração e entregas.
6. Cadastrar a configuração FireAds de Santo André, inicialmente sem exportação
   retroativa ou alteração de conversas em andamento.
7. Ativar conforme o procedimento de deploy autorizado.

Revisar especialmente:

- Consultas SQL que acessam diretamente unidade.link_agendamento e outros campos movidos.
- Consultas com posições fixas em tuplas e serialização de contexto.
- Resolvers, mensagens, senders e efeitos de transição.
- Inicialização controlada na etapa 4, criação do dependente importado e
  inclusão incremental dos caminhos 7/9→11, sem apagar o mapa existente.
- Repositórios do Funil, elegibilidade com/sem link e formatação de observações.
- Follow-up, painel, relatórios e formulários administrativos.
- Cache de unidade e invalidação das configurações alteradas.
- Validação de número comercial, e-mail e regras de idade.
- Criação de unidade no Admin, sem repetir cadastro Meta ao editar tabelas filhas.

Definir um marco de ativação para conversas novas. Histórico anterior permanece
sem origem/entrega FireAds e não deve ser exportado em massa por acidente.
Conversas em andamento preservam a decisão/rota já adotada; não saltar etapas
no meio do atendimento por ativação da integração.

O chat é a única estrutura antes prevista para a IA que será antecipada nesta
entrega. Não implementar cotas, assinatura, chamadas ao provedor ou funções de IA.

## 11. Organização técnica

| Camada | Trabalho previsto |
| --- | --- |
| core/integrations/fireads/ | Cliente GET/POST, validação de respostas, contrato, normalização e mapeamento de fontes. |
| Serviço de consulta inicial | Seleção do mais recente, validação dos três dados, classificação e decisão persistida. |
| Repositórios FireAds | Configuração, consulta atual por chat, retrato da conversa e fila envios_dash. |
| Repositórios de chat/conversa | Obter/criar vínculo único e manter a consistência dos IDs coexistentes. |
| Repositórios de unidade/contexto | Adaptar a divisão de unidade/customização/integração. |
| worker_flow | Consulta na abertura de toda nova conversa integrada e transições controladas. |
| Etapa 4 e senders | Saudação especial inicial, preservando tratamentos. |
| Mapa e efeitos de transição | Coletas dispensadas sem mensagens ou histórico fictícios. |
| Repositório/formatador Funil | E-mail importado, canal correto e observações completas preservadas. |
| worker_funil | Processar Funil e dashboard com filas independentes e sequência de entrega. |
| Models/Admin/SQL/cache | Nova estrutura, validações, migração e invalidação. |
| Utilitários FireAds | Referência do contrato/testes; não importar sondas que executem envios para o runtime. |

## 12. Regras preservadas e limites conhecidos

- Assinatura de webhook, flood, turnos de mensagem, bloqueios, idempotência local
  e locks seguem valendo.
- Uma conversa ativa por cliente/unidade; encerradas não são reabertas.
- Idade mínima, suporte ao idoso, exceção universal e e-mail por unidade
  continuam como no projeto. Faixa etária não substitui idade exata.
- Botões interactive/interactive_button, seleção de um único turno e mensagens
  com/sem link continuam funcionando.
- Follow-up permanece determinístico, orientado pela pergunta realmente enviada.
- Consumo Meta e suas regras não mudam. Formulário Meta não prova gratuidade de 72 horas.
- Falha inicial pode classificar como orgânico quem possui formulário. Isso é
  uma decisão aceita; registrar a causa sem trocar a origem depois.
- Formulário antigo pode conter dados desatualizados, mas não será descartado por
  idade. Validar os dados e não usar a planilha para sobrescrever correções posteriores.
- Fila local não elimina sozinha a incerteza entre POST externo e gravação local.
  Aplicar a conferência do destino e registrar o resultado desconhecido.
- Conflitos preexistentes no dashboard não autorizam exclusão ou fusão automática.

Origem de anúncios/posts recebida diretamente da Meta continua em plano separado:
[plano_origem_meta_anuncios_posts.md](plano_origem_meta_anuncios_posts.md).
Ela é independente da origem FireAds e não deve ser acoplada a esta entrega.
Nesta revisão recomenda-se priorizar esse recurso nas unidades sem FireAds,
mantendo a preservação de criativos da agência nesta entrega. Formulário e
referral não são equivalentes: uma referência obtida diretamente do WhatsApp
pode trazer origem que nunca passou pelo formulário, inclusive em unidade integrada.
Não converter FR002 ou qualquer texto da Observação em source_id da Meta.

Os PDFs produzidos anteriormente refletem decisões antigas, incluindo prazo de
30 dias e exportação a cargo da agência. **Precisam de revisão antes de serem
redistribuídos como descrição deste fluxo**. Eles não foram atualizados nesta
revisão do plano:
[guia de atendimento](../output/pdf/guia_chatbot_fireads_flavio.pdf) e
[apoio à integração](../output/pdf/apoio_fireads_funil_dashboard_sem_duplicacao.pdf).

## 13. Decisões respondidas e verificações da aplicação

### 13.1. Respostas preservadas

| Código | Questão | Resposta do responsável |
| --- | --- | --- |
| P1 | Destino no Google | Formulário atualizado para titular/parentescos. Resolvida. |
| P2 | Versão Meta | Somente 7.2. Resolvida. |
| D1 | Onde escrever | LEADS GERAL - Feedback; formulários apenas consultados. Resolvida. |
| D2 | Quem exporta chatbot → dashboard | worker_funil. Agência já desativou a varredura do Funil nesta tarde. Resolvida. |
| D3 | Quando consultar formulário | Toda nova conversa. Resolvida. |
| Prazo | Limite de 30 dias | Removido. |
| Consulta persistida | Tabela consulta_fireads aprovada | Uma linha atual por chat integrado, com referência à conversa consultada. |
| Chat | Momento da implantação | Incluir o vínculo na aplicação FireAds; manter IDs diretos da conversa. |
| Abas | Preenchimento | Defaults SQL/Django; dispensar digitação no Admin. |
| Observação já existente | Preservação | Manter integralmente e acrescentar o bloco do chatbot abaixo; retry não repete o bloco. |
| Datas e fuso no dashboard | Responsabilidade | Cadastro deixa o script datar; update não altera data/fuso; o fuso Meta da unidade permanece independente. |

Não pedir novamente essas decisões como se continuassem pendentes.

### 13.2. Verificações técnicas antes de ativar

- Confirmar chave/valor de uma submissão do Google após a mudança das opções.
- Conhecer o fuso de leitura das datas sem offset para comparar as fontes;
  não alterar nem impor fuso à FireAds. Respeitar os offsets já recebidos da Meta.
- Validar que o /exec publicado corresponde ao contrato de GET/append/update.
- Conferir que a antiga sincronização continua desativada e a captação dos
  formulários permanece ativa.
- Fechar SQL/nomes do estado persistido e dos campos de retrato das entregas.
- Verificar orçamento de tempo do worker_flow e do worker_funil.
- Verificar conflitos de telefone/e-mail, cache, retentativas e _row mutável.
- Confirmar o comportamento diante de contestação dos dados importados usando
  os tratamentos determinísticos disponíveis, sem acrescentar IA.
- Definir o marco de ativação, conferências da migração e recuperação/rollback.

Esses itens são trabalho técnico da futura aplicação. Quando houver uma
ambiguidade de negócio nova, apresentá-la com o cenário concreto.

## 14. Matriz de verificação da implementação futura

| Cenário | Resultado esperado |
| --- | --- |
| Unidade sem FireAds | Zero consultas/escritas FireAds; origem/entrega nulas; comportamento atual. |
| Primeira conversa integrada | Consulta as duas fontes antes de responder. |
| Nova conversa após idade, follow-up ou satisfação | Nova consulta, sem reabrir conversa anterior. |
| Mensagem seguinte na mesma conversa | Não consulta nem reapresenta o bot novamente. |
| Retry após decisão persistida | Reutiliza decisão, sem importação duplicada. |
| Meta e Google com mesmo telefone | Usa registro mais recente e canal correspondente. |
| Formulário válido com 29, 30 ou mais de 30 dias | Sem diferença por idade do formulário; pode importar. |
| Mais recente incompleto e anterior completo | Orgânico; não combina nem escolhe o anterior. |
| Erro em uma das fontes | Orgânico, diagnóstico e atendimento completo. |
| Google Para mim | Titular. |
| Google pai/mãe, avô/avó, outra pessoa | Dependente. |
| Google antigo Adulto/60+ sem destino claro | Não supõe titular/dependente; atendimento completo. |
| Meta Para mim e outra pessoa | Somente dependente. |
| Dados completos | Profissão na abertura; nome/destino/confirmação/e-mail dispensados. |
| Primeira entrada é apenas Olá, importação válida | Saudação da profissão; não validar Olá como profissão nem inventar etapa de origem. |
| Importação dependente e retry | Um dependente da conversa; etapa 5 consegue salvar o nome nesse registro. |
| Aceite nas etapas 7 e 9, com/sem e-mail importado | 11 somente com evidência da conversa; caso contrário, 10 pelo mapa atual. |
| Falha após importação, antes de concluir a primeira resposta | Recuperar a abertura especial sem reimportar nem supor que profissão já foi perguntada. |
| Faixa etária/objetivo presentes | Não resolve idade exata/triagem. |
| E-mail importado sem etapa 10 | Funil usa e-mail da conversa sem histórico inventado. |
| Conflito de e-mail único | Fallback controlado, sem alterar outra pessoa ou loop de retry. |
| Google, Meta, Orgânico no Funil | 113336, 113340, 113481 e linha Canal de venda correspondente. |
| Personalizado Origem do lead | Não rotular Google/Orgânico como Meta Chatbot; manter coerência com canal e observações. |
| Rota sem link | Preserva turno e elegibilidade 19/21–24. |
| Rota com link | Preserva elegibilidade 20–24. |
| Funil falha | Dashboard aguarda; outros itens seguem. |
| Funil confirma e dashboard falha | Funil não é reenviado; dashboard fica pending. |
| Nenhum novo envio ao Funil | Pendências antigas do dashboard continuam sendo processadas. |
| Contato existente na aba geral | Conteúdo atual da Observação preservado e bloco do chatbot acrescentado abaixo; demais campos intactos. |
| Observação com FR002/campanha/anotação comercial | Texto externo integralmente preservado antes do novo bloco. |
| Lead Google Ads ou da landing page com Observação 0 | Preservar 0 e acrescentar o bloco abaixo, sem trocar data ou outros campos. |
| Registro válido da fonte Google captado pela landing page | origem_fireads=google e canal 113336 conforme classificação combinada; não inventar evidência de anúncio pago. |
| Retry do update após sucesso externo sem gravação local | Identificar bloco completo da mesma conversa, sem duplicá-lo. |
| Nova conversa com mesmo texto de observações | Acrescentar bloco da nova conversa, distinguindo-a de retry. |
| Bloco com mesma referência e conteúdo divergente | Conflito pendente; não sobrescrever edição nem acrescentar cópia. |
| Observação omitida da resposta ou leitura incompleta | Pending; não tratar campo desconhecido como vazio. |
| Cadastro/update no dashboard | Sem Data/Hora no payload; novo registro recebe data do script, existente conserva sua data. |
| Datas Meta com offset e Google sem offset | Comparar instantes só com a interpretação correta da fonte, sem alterar fuso externo. |
| Contato só no formulário | Cadastro na geral com Meta/Google preservado. |
| Orgânico já na geral | Update de Observação, sem nova linha. |
| Contato ausente após consulta válida | Append com dados disponíveis e observações integrais. |
| Consulta ao destino falha | Pending; nenhum cadastro às cegas. |
| Nome/telefone/e-mail conflitantes ou linhas duplicadas | Não escolher/fundir/cadastrar arbitrariamente. |
| HTTP 200 com success=false | Falha registrada. |
| Timeout depois do cadastro | Conferir antes de repetir; não reenviar imediatamente. |
| Dois ciclos locais para mesma conversa/contato | Reserva/serialização evita duas entregas locais concorrentes. |
| Retry antigo e conversa posterior do mesmo contato | Não sobrescrever observações novas por atendimento antigo. |
| Duas integrações/unidades | Isolar configuração e destino; não cruzar contatos/linhas. |
| Migração de customização | Valores preservados, uma configuração por unidade, Admin identifica a unidade. |
| Migração de chat | Um vínculo por par, IDs de conversa preservados, FK composta consistente. |
| Integração criada no Admin | As três abas aparecem preenchidas pelos defaults aprovados. |
| Chat de unidade sem FireAds | Chat existe; nenhuma linha consulta_fireads fictícia. |
| Nova conversa do mesmo chat | Mesmo id_chat/id_consulta; consulta atualizada para o novo id_conversa_referencia. |
| Retry antes de concluir consulta | Refaz e atualiza a mesma linha, sem duplicar id_consulta. |
| Retry depois de concluir | Usa contexto FireAds da conversa e não reimporta. |
| Consulta do chat atualizada por conversa posterior | Conversa/entrega anterior conserva seus dados, inclusive e-mail. |
| Cadastro global alterado antes da entrega de conversa integrada | Nome, idade e e-mail da entrega vêm dos dados aceitos naquela conversa. |
| Referência de consulta ou integração de outro chat/unidade | Persistência rejeitada; nenhum dado ou destino cruzado. |
| E-mail global presente, sem importação nesta conversa | Coleta normal; não dispensa etapa 10 pelo cadastro antigo. |
| Retry antigo após nova conversa | Não altera a consulta de referência atual nem sobrescreve dados novos. |
| Desativação FireAds | Sem novas escritas enquanto desativada; histórico preservado. |

Usar fixtures e HTTP simulado para validar os contratos e regressões.
Testes de banco seguem os mecanismos isolados do projeto.
Testes com escrita real precisam da autorização correspondente; revisar um plano
não autoriza produzir oportunidades ou alterar a planilha de produção.

## 15. Ordem futura de aplicação

1. Revisar o schema/código atual e concluir as verificações técnicas da seção 13.
2. Preparar migração incremental, chat/id_chat, models/Admin com defaults e
   adaptação dos consumidores/cache, preservando os IDs diretos da conversa.
3. Implementar cliente FireAds, consulta_fireads por chat e decisão/retrato da
   conversa para a consulta inicial e retomada de retries.
4. Integrar abertura na profissão, coletas resolvidas e mapa de transições.
5. Adaptar Funil para canal, e-mail importado e observações integrais persistidas.
6. Implementar envios_dash e cadastro/update no worker_funil.
7. Validar a matriz e as regressões de unidades sem integração.
8. Preparar versionamento, migração, recuperação e deploy para comando do responsável.
9. Ativar somente a integração configurada, sem exportação retroativa.
10. Revisar materiais de alinhamento e os planos da IA conforme a base realmente
    implementada. A antecipação de chat/consulta já está registrada no plano de IA;
    após o deploy, conferir schema efetivo, nomes e contratos antes de aplicar IA.

Nenhuma etapa dessa implementação foi executada pela edição deste documento.

## 16. Referências locais

- [Consulta experimental](../utilitarios/fireAds/test_Dash.py).
- [Configuração dos utilitários](../utilitarios/fireAds/config_teste.py).
- [Contrato e utilitários de escrita](../utilitarios/fireAds/dash_crud_teste.py).
- [Cadastro de teste](../utilitarios/fireAds/test_dash_post.py).
- [Atualização de teste](../utilitarios/fireAds/test_dash_update.py).
- [Instruções dos utilitários](../utilitarios/fireAds/README.md).
- [Mapa das etapas](../core/database/deploy_database/etapa_transicao_script.py).
- [Resolver de transições](../workers/worker_flow/response_flow/transicoes/resolver_transicao.py).
- [Efeitos de transição](../workers/worker_flow/transacoes/efeitos_transicao.py).
- [Validador de nome](../workers/worker_flow/response_flow/etapas/validadores_universais/validador_nome.py).
- [Repositório de conversas](../core/repositories/atendimento/conversas.py).
- [Models](../callback/webhook/models.py) e [Admin](../callback/webhook/admin.py).
- [Schema atual](../core/database/deploy_database/bank_script.py).
- [Leitura do Funil](../core/repositories/funil/leads.py).
- [Processamento do Funil](../workers/worker_funil/processamento.py).
- [Configuração do worker](../workers/worker_funil/config.py).
- [Payload e observações](../core/integrations/funil/oportunidades.py).
- [Cliente HTTP e canal](../core/integrations/funil/cliente.py).
- [Plano futuro da IA](<../IA teste/plano_ia_hibrida_atendimento.md>).

## 17. Histórico de investigação — não confundir com o contrato atual

### 17.1. Webhook experimental em 05/10/2026

Eduardo forneceu o webhook organicosupera, sem contrato de campos. O teste
autorizado usou telefone 71994111866, normalizado para 5571994111866, e identificação
esl-fireads-5b93c902caa0468ab506c9e8e6d35187.

O POST de 19:03:09 (America/Sao_Paulo) respondeu HTTP 200 e “Workflow was started”.
Duas leituras posteriores retornaram 678 registros, incluindo contatos de teste
nas linhas 511/512 com datas de 31/08/2026, anteriores ao envio.
A leitura de 19:04:58 não encontrou nome/e-mail/identificação do cadastro novo.

Isso confirmou apenas a recepção pelo webhook, não a criação na planilha.
Não atribuir os registros antigos a esse POST. Esse endereço e seu payload
experimental não são o caminho da integração de produção planejada aqui.
O utilitário test_post.py continua distinto dos testes diretos do Apps Script.

### 17.2. Cópias do Funil observadas em 06/10

A inspeção não encontrou exportação direta dos workers de produção ao dashboard.
Foram observadas cópias de observações do Funil no dashboard, inicialmente sem
identificação comprovada do mecanismo. Depois foi fornecido o Apps Script com a
rotina de importação do Funil. Nesta revisão, o responsável confirmou sua
desativação pela agência. A exportação planejada passa a ser do worker_funil.

### 17.3. Contrato e testes do Apps Script em 07/10

O primeiro ensaio com action=create respondeu “Linha inválida”.
O código doPost/appendRows fornecido esclareceu os contratos reais:
append/sheet/rows para inclusão e sheet/row/updates para alteração.

O cadastro de Edcarlos com identificação esl-dash-crud-9f327a8ec601 foi encontrado
na aba geral; uma execução posterior do utilitário foi bloqueada localmente
porque esse teste já existia. Depois os utilitários passaram a usar um teste
separado de Carlos, telefone fictício 550000000002 e identificação
esl-dash-crud-67ae21f904d8.

O update foi ajustado para alterar somente Observação, acrescentando “ 2” ao texto
do teste. A revisão de código com simulações confirmou o payload restrito,
a preservação dos demais campos e os bloqueios para alvos ausentes/ambíguos.
O responsável relatou bons resultados dos testes reais.

Esses utilitários são referências do contrato e não devem ser executados
automaticamente pelo projeto. Uma prova de escrita de teste não significa
que o fluxo de produção descrito neste plano já esteja implementado.
