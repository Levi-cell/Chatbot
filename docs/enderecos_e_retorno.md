# Endereços por unidade e mensagens de retorno

## Comportamento

`chatbot.endereco_unidade` mantém um endereço público por unidade, com chave
primária/estrangeira `id_unidade`, exclusão em cascata e texto obrigatório não
vazio. O Django expõe o cadastro em **Endereços das unidades** no Admin, usando
um model não gerenciado. O endereço é consultado pelo ID da unidade atendida,
somente quando a mensagem pede localização e a etapa aceita o tratamento.
Não existe cópia em Redis; alterações no cadastro são lidas no próximo pedido.

`chatbot.unidade.horarios_funcionamento` é `TEXT NULL`, editável no Admin da
unidade. Guarda somente o complemento depois de “Nosso horário de funcionamento
é de”. O horário de Santo André foi confirmado pelo usuário e a migração o
cadastra quando o campo está NULL, vazio ou só com espaços: segunda a sexta
das 9h às 19h, exceto quarta-feira, quando vai até as 21h, e sábado das 8h30
às 13h30. Horários das outras unidades ainda precisam ser informados. `NULL`, texto
vazio ou só espaços omitem todo o parágrafo de horários. O repositório lê endereço
e horários juntos por ID, inclusive quando ainda não há endereço cadastrado.

O texto fica “Nossa unidade fica localizada na {endereço}.”, seguido de
“Nosso horário de funcionamento é de {horários}.” quando informado, e diretamente
da pergunta ou orientação da etapa. Ponto de referência, se conhecido,
pode constar no próprio texto do endereço; não é inferido nem obrigatório.
Na revisão de 29/10/2026, a ponte foi retirada de todas as etapas, incluindo
abertura e retorno. Financeiro, reforço escolar e mídia também seguem diretamente
para a repetição. Os blocos são separados por `\n\n`.

Na retomada da reserva (etapa 9), a pergunta é “Vamos dar prosseguimento à
reserva do seu *momento Supera*?” ou a versão com o nome do dependente.
Na abertura com dados FireAds, o pedido de endereço é respondido logo após a
apresentação: saudação/apresentação → endereço → horários, se cadastrados →
reconhecimento do formulário → pergunta do campo necessário. Essa ordem vale
para coleta parcial/completa e para a abertura legada. Sem formulário confirmado,
o reconhecimento é omitido; as perguntas e opções da etapa são preservadas.

Endereços fornecidos para a migração:

| Unidade | Endereço |
| --- | --- |
| Supera Santo André | Rua Dr. Eduardo Monteiro, 188 - Jardim Bela Vista, Santo André - SP, CEP 09041-300 |
| Supera Santo Antônio de Jesus | Avenida Barros e Almeida, 88, Centro - Santo Antônio de Jesus |
| Supera Rio Vermelho | R. Odilon Santos, 14 - 1 a - Rio Vermelho, Salvador - BA, 41940-350, Brasil |

Porto Velho Olaria permanece sem endereço até que ele seja informado. Quando
não há cadastro, o bot explica que ainda não dispõe do endereço e que a equipe
poderá confirmá-lo; não inventa dados nem reutiliza os de outra unidade.

O identificador aceita perguntas no meio da mensagem, com ou sem interrogação,
acentos ou diferença de maiúsculas: “Aonde fica”, “Aonde é”, “Aonde q fica”,
“aonde q fca”, “Fica aonde”, “Onde vcs ficam?”, “Em qual bairro vocês ficam?”,
“Qual o endereço?”, “Me diz o endereço de vocês”, “Me diga o endereço”,
“Pode me dizer o endereço”, “Me passa a localização”, “Como chegar aí?” e
“Qual é o CEP?”. Também considera saudações, emojis, espaços e quebras de linha. As
abreviações `q`, `vc/vcs`, `ond/aond`, `eh` e `fca/fcam` são reconhecidas em
construções de localização; não existe correção aproximada de qualquer palavra.

Regra ampliada aprovada em 29/10/2026: a palavra inteira **endereço** (com ou sem
acento) ativa mesmo sem pergunta. A única exceção é a ocorrência referente a
email: “endereço de email”, “endereço de e-mail” ou “endereço eletrônico”.
A exceção vale por ocorrência: outra menção a endereço ou uma pergunta física
na mesma mensagem continua válida. Isso deliberadamente inclui frases como
“Já tenho o endereço”, “Meu endereço é Rua X”, “Não quero o endereço” e
“Qual o endereço do site/IP”, conforme a regra ampla escolhida pelo usuário.

Para **bairro, local e rua**, é preciso um pedido, como “Me diz o bairro”,
“Qual bairro”, “Qual q é o bairro”, “Qual é o local” e “Aonde q é a rua”.
Artigos, preposições e ligações como `é`, `que` e `q` são opcionais nas
construções reconhecidas. “Onde” e “Aonde” isolados também ativam, assim como
“Onde é que fica” e “Me diz onde q fica”. As palavras bairro/local/rua isoladas
ou informações como “Meu bairro é Centro” não bastam.

Sem a palavra endereço, continuam sendo rejeitados outros assuntos e locais:
“Onde encontro o link?”, “Onde respondo a pesquisa?”, “Qual o local do botão?”
e “Me diz a rua do hospital”. Afirmações como “já sei onde fica” e recusas
como “não me diga a localização” também não acionam. “Não sei onde fica”
continua válido. A análise por oração preserva pedidos físicos separados de
outros assuntos. Não há correção aproximada nem correspondência por pedaços
de palavras. A ampliação do validador não exige nova migração SQL.

| Situação | Resposta e efeito |
| --- | --- |
| Primeira resposta | Apresentação, tratamento identificado e pergunta do campo necessário; respeita a coleta parcial e os dados FireAds já aceitos. |
| Etapas 1–7, 10–11, 18, 20 e 22 | Endereço, financeiro ou reforço escolar e repetição neutra da pergunta, preservando etapa, participante, botões e links. |
| Etapa 8, oferta adiada | Responde à dúvida e apresenta a etapa 9 com seus dois botões, pelo evento `cliente_retornou`. Não repete despedida, Instagram ou espera; não considera a pergunta um aceite da reserva. |
| Etapa 9, retorno da oferta | Os três tratamentos são respondidos sem avançar. Financeiro/reforço já existiam; endereço foi acrescentado. |
| Etapa 19, contato comercial | Os três tratamentos preservam a etapa e o botão de contato. A dúvida não inicia a pesquisa de satisfação. |
| Triagem 12–17 | Os três tratamentos reapresentam a mesma pergunta canônica, com o participante, a faixa e os botões originais. Não registram resposta da triagem nem avançam. |
| Nota 21 | Os três tratamentos reapresentam a pergunta de satisfação e as cinco notas. O pedido de informação não é interpretado como avaliação. |
| Comentário livre 23 e terminal 24 | Excluídas dos três tratamentos. A 23 conserva a coleta do comentário; a 24 conserva a finalização. |

A prioridade já existente permanece: mídia, reforço escolar, financeiro e
então endereço. Na etapa 4, continuam valendo os validadores específicos de
profissão. A frase de investimento do formulário Meta conserva suas exceções.
Uma mensagem com mais de uma intenção recebe o tratamento prioritário.

A validação de pagamento, bloqueios, fila, locks e elegibilidade do atendimento
continua antes do envio. Nas etapas de pergunta, tratamentos não geram evento
de transição. A exceção é a retomada da espera na 8: a orientação acompanha a
abertura da 9 pelo evento existente `cliente_retornou`, validado antes do envio.
Replays com resposta já persistida não consultam novamente o endereço nem
reenviam mensagens. Retornos de follow-up mantêm a confirmação atômica do
histórico/retomada. Na 8, a mensagem do cliente e o checkpoint conservam a
origem; a resposta do bot registra a etapa 9. Replays de respostas antigas que
ficaram na 8 continuam recuperáveis sem reenvio nem transição retroativa.

## Composição das mensagens

Quando há título, a ordem é **cabeçalho → saudação de retorno (se houver) →
tratamento (endereço e horários, quando cadastrados) → repetição da etapa**.
Cada bloco presente é separado do seguinte por exatamente `\n\n` (uma linha
vazia), inclusive quando os fragmentos recebidos têm quebras nas extremidades.
Financeiro e reforço escolar não acrescentam “Vamos lá”. Nenhum tratamento
acrescenta a ponte “Para continuarmos”.
Cabeçalhos e rodapés usam a mesma
separação; o conteúdo interno de cada fragmento é preservado.
O texto persistido é o mesmo enviado ao WhatsApp. A composição remove apenas
aberturas conhecidas e redundantes (“Maravilha, nome!”, “Prazer, nome!”,
“Perfeito!” e a saudação própria da etapa 9) quando já existe um prefixo de
retorno. Com “Bom te ver novamente”, também retira o “Certo” usado apenas como
abertura das perguntas de nome do dependente, email e introdução da triagem.
Confirmações com sentido próprio, a despedida e o nome do dependente no conteúdo
permanecem. Perguntas, explicações da oferta, agradecimentos substantivos e
despedidas são preservados. Sem retorno, o catálogo original permanece igual.

Exemplo para a pesquisa:

> **Pesquisa de satisfação**
>
> Bom te ver novamente ☺️
>
> Antes de finalizarmos, qual seu grau de satisfação com o nosso atendimento?

## Organização do código

- `core/validacoes/endereco.py`: identificação pura do pedido.
- `core/repositories/unidades/enderecos.py`: leitura SQL parametrizada.
- `core/integrations/whatsapp/messages/tratamentos/endereco.py`: endereço e horários seguidos da pergunta atual.
- `workers/worker_flow/valida_historico.py`: carrega o endereço e os dados necessários antes do envio HTTP.
- `workers/worker_flow/response_flow/tratamentos_informativos.py`: classificação, prioridade e composição; na 8 reutiliza o resolver de retorno para abrir a 9, nas demais etapas repete a pergunta sem avanço.
- `workers/worker_flow/response_flow/repeticao_etapa.py`: seleção de senders neutros compartilhada com o follow-up, sem duplicar perguntas/botões.
- `core/integrations/whatsapp/messages/tratamentos/composicao.py`: título e saudação em ordem, sem dupla abertura.

## Banco e instalação

A migração [20261027_endereco_unidade.sql](../deploy/migrations/20261027_endereco_unidade.sql) registra os três endereços iniciais e o horário de Santo André. Para uma instalação nova, o [DDL declarativo](../core/database/deploy_database) e os models Django representam a tabela e a coluna final. Os valores efetivamente cadastrados dependem da unidade e podem ser editados no Admin.
