# Plano de origem Meta — anúncios e posts

Revisão: **07/10/2026**.

**Status:** plano separado solicitado pelo responsável; implementação futura,
preferencialmente após a entrega FireAds e mediante comando de aplicação.
Este arquivo não altera webhook, banco, workers nem integrações externas.

**Recomendação desta revisão de 07/10:** manter a aplicação separada da FireAds
e priorizar unidades sem essa integração. A agência já disponibiliza referências
de criativo dos seus formulários; o plano FireAds passa a preservar esse texto
ao acrescentar as observações do chatbot. A prioridade não significa que ambas
as fontes sejam equivalentes nem determina uma restrição técnica permanente.
Uma inclusão deste módulo na mesma entrega FireAds ainda não foi aprovada.

## 1. Objetivo e alcance

Registrar a referência de anúncio ou post enviada pela Meta junto da mensagem
recebida no WhatsApp e apresentá-la nas observações da oportunidade do Funil.

A arquitetura pode atender **todas as unidades**, com ou sem FireAds, com ou sem
link e independentemente da futura IA. A prioridade de aplicação sugerida nesta
revisão é atender unidades sem FireAds, mantendo o módulo independente. A decisão
de ativação por unidade deve ficar explícita ao aplicar este plano; não assumir
que uma integração FireAds torna todo referral desnecessário.

Com referência de anúncio:

> Origem Meta: Anúncio  
> Anúncio: {identificação disponível}

Com referência de publicação:

> Origem Meta: Post  
> Post: {identificação disponível}

Exibir somente quando a Meta realmente informar o tipo e dados que permitam
identificar a origem. Sem essa informação, omitir o bloco; não inventar nome,
código, link ou linha “Orgânico” neste recurso.

## 2. Dado disponível na mensagem

O objeto relevante é **referral**, associado à mensagem recebida. Na documentação
do PyWa, source_type distingue ad/post; source_id identifica o anúncio/publicação;
source_url aponta para a origem; headline é o título exibido. Os campos podem estar
ausentes. A referência é documentada no
[PyWa — Referral](https://pywa.readthedocs.io/en/latest/content/updates/message.html#pywa.types.Referral),
consultado em 07/10/2026, cuja página se identificava como PyWa 4.5.0.

| Campo | Uso previsto |
| --- | --- |
| source_type | Converter ad em Anúncio e post em Post. |
| source_id | Guardar como texto, sem conversão numérica ou dedução de outra fonte. |
| source_url | Preservar o link válido recebido. |
| headline | Título apresentado pela Meta, quando disponível. |

O título recebido não deve ser descrito como o nome interno do Gerenciador de
Anúncios. Não prometer esse nome em todos os payloads. Identificador ou link já
permitem atender ao pedido de reconhecer a origem.

Não é preciso buscar mídia, consultar a Marketing API ou obter um título por
raspagem para esta versão. body, imagens, vídeos e ctwa_clid não são necessários
para o bloco solicitado; eventual ampliação fica fora desta entrega.

Os requisitos de exibição e as políticas abaixo são decisões do projeto, não
garantias de que todos os contatos terão referral. Ausência de informação não
autoriza concluir que um cliente nunca veio de anúncio.

## 3. Independência da FireAds e de cobranças

| Informação | Fonte | Finalidade |
| --- | --- | --- |
| origem_fireads | Consulta aos formulários, com regras de elegibilidade, validade e fallback | Dados antecipados, origem comercial e canal do Funil da integração FireAds. |
| Origem Meta | referral da mensagem recebida no webhook | Identificar anúncio/post nas observações. |

O plano [integracao_fireads.md](integracao_fireads.md) define consulta em toda
nova conversa, ausência de expiração por 30 dias e fallback orgânico.
Uma unidade sem FireAds também pode receber referral; a interpretação desse
objeto não depende da presença do telefone nos formulários.

Na confirmação fornecida pelo responsável em 07/10, Matheus descreveu o texto
"FR002" na Observação como nome do criativo refletido da planilha. A consulta
à aba Meta 7.2 nesta revisão também confirmou ad_id, ad_name e campos de campanha.
Preservar essa informação na Observação é suficiente para não perder a
atribuição já apresentada no dashboard; não exige implantar referral agora.
Não deduzir um source_id a partir de FR002, nem confundir nome do criativo,
ad_id e campaign_id. Tampouco presumir que qualquer anotação seja um anúncio.

Um cliente pode entrar diretamente no WhatsApp por anúncio/post sem preencher
formulário da agência, inclusive numa unidade integrada. Quando recebido,
referral retrata esse contato; o formulário retrata outra evidência de captação.
Por isso, as fontes podem ser complementares. A documentação oficial da
[PyWa — Referral](https://pywa.readthedocs.io/en/latest/content/updates/message.html#pywa.types.Referral)
distingue source_id (ID Meta) de headline (título), e não garante referência em
toda mensagem. A existência do nome do criativo no dashboard não substitui
universalmente a captura do webhook.

As duas informações podem ser diferentes. Por exemplo, uma falha de consulta
FireAds gera orgânico por decisão operacional; ainda assim, uma referência de
anúncio realmente recebida da Meta pode aparecer nas observações.

Este recurso não sobrescreve origem_fireads e não muda ForceCodeChannel:
os canais Google 113336, Meta 113340 e Orgânico 113481 continuam sendo resolvidos
pelo plano FireAds. Para unidades sem FireAds, manter a configuração atual do CRM.

Não usar ad/post, source_id ou URL como autorização para templates gratuitos,
prova de janela de 72 horas ou alteração do Consumo Meta. A proposta futura de
interpretar statuses/cobrança é separada e não é requisito desta captura.

## 4. Fluxo técnico proposto

1. O webhook recebe e valida o payload pelos mecanismos atuais.
2. Ao extrair cada mensagem que será processada pelo fluxo existente, ler seu
   próprio referral, sem confundir com contacts, status de envio ou mensagem citada.
3. Validar o objeto e preservar o recorte aceito junto da mensagem na fila.
   Não guardar apenas numa variável que desapareça ao terminar a requisição.
4. O worker carrega os metadados com a mensagem e os vincula à conversa correta,
   identificada pelo cliente e pela unidade.
5. Persistir a referência com o ID da mensagem de origem e seu instante, mantendo
   idempotência em reentregas e retries.
6. Quando a conversa estiver elegível ao Funil, ler os dados persistidos e acrescentar
   o bloco correspondente às observações.
7. Seguir o envio, recibo e controle de duplicidade já existentes no Funil.

Preservar os filtros e a regra atual de turnos. A captura não autoriza responder
mensagens rejeitadas, criar conversas extras, aceitar mídias antes barradas ou
processar eventos de status como se fossem mensagens do cliente.

A implementação deve revisar também os casos de payload com múltiplas entradas/
mensagens: não associar a referência de uma mensagem a outra. O parser atual lê
o primeiro item; não ampliar silenciosamente o processamento do lote sem revisar
os controles e o escopo dessa mudança.

## 5. Modelagem proposta para a aplicação futura

Os nomes abaixo são **proposta técnica**, ainda sem SQL executado:

- **Fila:** campo opcional referral_meta (JSONB ou estrutura equivalente) com
  os campos permitidos, preservando-os para o worker e suas retentativas.
- **Conversa:** campos dedicados ou registro origem_meta_conversa, único por
  id_conversa, com source_type, source_id, source_url, headline, id_hash_msg_origem
  e recebido_em.
- **Histórico:** manter evidência da mensagem que originou a atribuição, sem
  depender da permanência eterna da fila para reconstruir a origem.

Na revisão do banco, escolher uma única representação para o retrato da conversa.
Não criar tabela e colunas redundantes com a mesma responsabilidade.

Regras técnicas propostas:

- Campos opcionais, sem backfill inventado para conversas anteriores à entrega.
- IDs guardados como texto.
- Tipo reconhecido restrito a ad/post.
- id_hash_msg_origem vinculado à mensagem realmente recebida.
- FK e limpeza acompanhando a conversa e os mecanismos existentes de exclusão.
- Alteração explícita dos modelos managed=False e da migração SQL incremental.
- Metadados ausentes ou malformados não tornam inválida uma mensagem de texto
  que seria aceita pelo fluxo atual; omitir a referência inválida e registrar
  diagnóstico resumido.

Este armazenamento não depende de criar as tabelas futuras chat ou de IA.
Se chat já tiver sido criado pela aplicação FireAds, reutilizar os vínculos
existentes; este módulo não recria chat nem exige tabelas de cotas da IA.

## 6. Seleção da referência da conversa

**Política inicial proposta, a revisar na aplicação:** usar a primeira referência
válida e identificável recebida dentro daquela conversa.

- Mensagens seguintes sem referral não apagam a referência.
- Reentrega do mesmo ID não cria nova origem.
- Outra referência recebida durante a mesma conversa não substitui silenciosamente
  a origem já registrada. Preservar sua evidência junto da mensagem, se armazenada.
- Nova conversa começa sem herdar automaticamente anúncio/post da conversa antiga.
- Atribuição usa o evento vinculado à conversa, não a ordem em que dois workers
  terminam nem o cadastro global do cliente.
- Se houver eventos fora de ordem, revisar a escolha por instante da mensagem e
  manter a evidência; não escolher uma referência de outra conversa.

A sugestão de usar a primeira referência não foi uma escolha expressa do
responsável entre primeira/última campanha. Ela fica identificada como proposta
para não transformar uma política de múltiplos anúncios em decisão já aprovada.

Dados recebidos após uma oportunidade já confirmada não justificam criar outra
oportunidade. Atualizar uma oportunidade existente exigiria outro contrato e
fica fora desta versão; os metadados locais podem ser preservados.

## 7. Validação e apresentação no Funil

O bloco deve depender de:

1. Tipo reconhecido ad ou post; e
2. Alguma identificação efetivamente recebida: source_id, source_url válido ou
   headline não vazio. Tipo isolado não identifica qual anúncio/post.

Preferir código/link quando disponíveis. Se houver somente headline, exibir como
título informado pela Meta, sem alegar que é o nome interno ou um identificador
único da campanha. Isso preserva a opção solicitada de informar nome, código ou link.

Exemplo com os dados disponíveis:

~~~text
Origem Meta: Anúncio
Anúncio: {headline} | Código: {source_id} | Link: {source_url}
~~~

Exemplo de publicação com apenas código:

~~~text
Origem Meta: Post
Post: Código {source_id}
~~~

Montar apenas os trechos presentes: não imprimir placeholders, None, URLs
inventadas ou separadores vazios. Sem título, usar código/link. Sem nenhum dado
identificável, omitir o bloco.

Validar tamanho e tipo de cada campo, tratar quebras de linha/caracteres de
controle e respeitar o limite do campo de observações já usado pelo CRM.
Se for preciso reduzir texto, abreviar título antes de perder o identificador.
Não transformar texto externo em instrução, HTML executável ou comandos.

source_url deve ser HTTP(S) válido e preservado como link de referência. Não fazer
requisições a essa URL para exibir o bloco; isso evita depender de autenticação,
redirecionamento ou disponibilidade do anúncio.

O bloco complementa as observações atuais. Não retirar nome, contato, idade,
profissão, triagem, turno ou origem FireAds existentes. O retry do Funil deve
reutilizar a oportunidade/entrega atual, sem duplicar blocos na montagem do texto.

## 8. Pontos do projeto a revisar

| Arquivo/camada | Ajuste futuro |
| --- | --- |
| callback/webhook/services/populating_fila_mensagens.py | extrair_dados_whatsapp e INSERT da fila devem preservar referral. |
| callback/webhook/services/post_flow.py | Manter assinatura, filtros, tipos aceitos e vínculo da mensagem. |
| core/repositories/atendimento/fila.py | Leitura do novo metadado e compatibilidade com mensagens antigas. |
| Contexto, transações e persistência do worker_flow | Vincular metadados à conversa sob os controles de posse atuais. |
| callback/webhook/models.py e migração SQL | Representar dados opcionais na fila/conversa ou tabela auxiliar. |
| core/repositories/funil/leads.py | Recuperar a referência da conversa. |
| core/integrations/funil/oportunidades.py | Formatar o bloco condicional. |
| Testes de webhook, worker e Funil | Verificar captura, isolamento, idempotência e exibição. |

A leitura do código em 07/10 mostrou que o parser e o INSERT atuais da fila não
preservam referral. Portanto, não basta acrescentar uma linha ao formatador do
Funil: o dado precisa chegar persistido desde o webhook.

## 9. Verificação antes do deploy futuro

| Caso | Resultado esperado |
| --- | --- |
| ad com ID/link | Bloco de anúncio na oportunidade correta. |
| post com ID/link | Bloco de post na oportunidade correta. |
| Sem referral | Fluxo normal, sem bloco e sem inferir orgânico neste recurso. |
| Tipo desconhecido ou objeto inválido | Mensagem válida continua; referência não exibida como ad/post. |
| Só tipo, sem identificação | Sem bloco identificador inventado. |
| Somente tipo e headline válido | Exibe o título recebido, sem inventar código/link ou nome interno. |
| Sem headline, com ID | Exibe código recebido. |
| URL inválida e ID válido | Usa ID; não propaga link inválido. |
| Mensagem seguinte sem referral | Origem anterior da mesma conversa preservada. |
| Retry/reentrega | Sem duplicação de referência, mensagem ou oportunidade. |
| Nova conversa do mesmo telefone | Não herda origem Meta antiga automaticamente. |
| Mesmo cliente em unidades diferentes | Origem restrita à conversa/unidade correspondente. |
| FireAds ausente ou desligada e módulo de origem Meta habilitado | Captura funciona sem depender da agência. |
| FireAds integrada e módulo de origem Meta habilitado em evolução posterior | Campos independentes; canal FireAds não é sobrescrito pelo referral. |
| Texto FR002/nome do criativo no dashboard | Não deduzir source_id; preservação do texto é responsabilidade da entrega FireAds. |
| Rotas com/sem link | Mesmo comportamento atual, apenas observações adicionais. |
| Filas/conversas legadas | Campos nulos não quebram leitura nem exportação. |
| Referência chegando após envio ao Funil | Não gera segunda oportunidade. |
| Falta de dados de cobrança/statuses | Não interfere na captura nem ativa gratuidade presumida. |

Usar payloads simulados, sem disparar mensagens ou criar leads externos em testes
automatizados. Conferir um exemplo real autorizado durante a aplicação, quando
disponível, sem depender dele para os testes básicos.

## 10. Ordem de execução e limites da entrega

1. Concluir a entrega FireAds primeiro, incluindo preservação das observações
   anteriores; recomendação atual mantém este módulo separado.
2. Sob comando de aplicação deste plano, confirmar a política de múltiplas
   referências, formatos recebidos, modelagem mínima e unidades inicialmente
   habilitadas, priorizando as que não possuem FireAds.
3. Preparar SQL, parser, fila e persistência.
4. Ajustar a leitura/observações do Funil.
5. Validar regressões e preparar deploy sem reprocessar todo o histórico.

A entrega não inclui dashboard novo, painel de campanhas, enriquecimento via
Marketing API, envio à FireAds, criação de anúncios, mensagens ao cliente,
alterações de canal por referral ou decisões de cobrança.

Referência relacionada: [integração FireAds](integracao_fireads.md).
