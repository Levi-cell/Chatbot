# Mensagens: personalidade e composição do atendimento

Este é o contrato editorial da pasta `messages`. Leia-o antes de criar,
reescrever ou reorganizar mensagens. Ele orienta o código atual e as próximas
alterações: o cliente deve perceber um atendimento acolhedor, coerente e
contínuo, mesmo quando precisar de orientação ou voltar depois de uma pausa.

- [Integração WhatsApp e responsabilidades das camadas](../README.md)
- [Regras de negócio do atendimento](../../../../REGRAS_DE_NEGOCIO.md)
- [Rotina para implementar etapas](../../../../ROTINA_IMPLEMENTACAO_ETAPAS.md)

Este documento não muda validadores, transições, horários, bloqueios ou
elegibilidade. Uma mudança editorial não autoriza alterar esses contratos.
Os exemplos ilustram o padrão de composição. Os montadores Python são a
fonte dos textos enviados; esta organização está implementada no projeto
local e só chegará à produção no próximo deploy.

## 1. A personalidade deve acompanhar o contexto

O bot apresenta o Supera com carinho, clareza e entusiasmo equilibrado.
Deve facilitar a próxima resposta e valorizar a pessoa, sem parecer um
formulário nem pressioná-la a continuar.

- Usar frases naturais e fáceis de ler, com uma ação ou pergunta principal.
- Demonstrar acolhimento com expressões como `Maravilha!`, `Vamos lá?` e
  `Vou te ajudar a continuar`, quando fizerem sentido naquele momento.
- Priorizar sorriso acolhedor (`☺️`, `😊`) e coração laranja (`🧡`), com
  moderação. Não é obrigatório colocar um emoji em cada pergunta.
- Reservar a comemoração para momentos compatíveis com progresso ou aceite.
  Após uma resposta não compreendida, orientar sem culpar nem comemorar.
- Usar **experiência Supera gratuita**, **demonstração prática exclusiva**,
  **presentear**, **reservar** e **sua reserva**, conforme o contexto.
  O atendimento não oferece curso ou matrícula gratuitos.
- Na oferta inicial da etapa 7, destacar **demonstração prática gratuita**
  logo na abertura, antes da explicação da avaliação. Encerrar com o convite
  para reservar a **experiência Supera exclusiva**. A gratuidade não pode ficar
  escondida somente no fim da oferta.
- Não reintroduzir `agendamento`, `aula gratuita`, nome de diretor ou cortesia
  como redação da oferta. Identificadores técnicos e textos legados aceitos
  pelos validadores têm outro papel e permanecem compatíveis.
- Usar negrito do WhatsApp (`*texto*`) para a oferta ou ação mais importante,
  sem destacar o parágrafo inteiro ou toda ocorrência de uma palavra.
- Separar acolhimento, explicação e pergunta com quebras controladas no texto
  final, sem acrescentar linhas vazias automaticamente a cada fragmento.
  Cabeçalhos e rodapés devem aparecer uma vez; títulos de botão não levam
  asteriscos de formatação.

### Espaçamento: declarar nas variáveis e conferir o resultado

**As quebras de linha pertencem às variáveis de mensagens e aos modelos
visuais, não às funções que recebem textos para compor.** `\n` muda de linha;
`\n\n` deixa uma linha vazia; `\n\n\n` deixa duas. Dividir uma string em
várias linhas do arquivo Python não insere quebras nem espaços no envio.

Manter `\n\n` entre parágrafos. A correção de excesso reduz somente três
quebras consecutivas para duas; não transformar duas em uma nem remover
quebras simples indiscriminadamente. Todo rodapé existente deve ficar
separado do corpo por uma linha vazia (`\n\n`), declarada no modelo
`MENSAGEM_COM_RODAPE`. O WhatsApp não é responsável por criar esse espaço:
o rodapé em itálico faz parte do texto enviado. Não acrescentar outro
separador ao corpo antes de aplicar o modelo.

Após o cabeçalho, usar também duas quebras (`\n\n`) antes da mensagem,
declaradas em `MENSAGEM_COM_CABECALHO`, inclusive nas perguntas da triagem.

- `compor_mensagem_inicial` e `compor_tratamento` apenas concatenam os
  fragmentos. Não inserem separadores, não removem quebras e não usam `strip()`
  no texto pronto. A apresentação, a orientação e a ponte declaram sua
  separação final; a pergunta reutilizável pode ser enviada sozinha.
- Por exemplo, `APRESENTACAO_ETAPA1` termina em `\n\n`, deixando uma linha
  vazia antes da pergunta. O compositor não acrescenta uma terceira quebra.
  Na etapa 7, a própria apresentação declara as quebras entre oferta,
  explicação e pergunta; os tratamentos continuam usando apenas a pergunta.
- As saudações de retorno têm sua quebra final nas constantes de
  `tratamentos/retorno_followup.py` e `tratamentos/retorno_inatividade.py`.
  Aplicar o prefixo apenas o concatena, uma única vez.
- Cabeçalhos e rodapés usam os modelos `MENSAGEM_COM_CABECALHO` e
  `MENSAGEM_COM_RODAPE`, em `componentes_compartilhados.py`. Suas funções
  apenas preenchem esses modelos. Os rótulos usados nos metadados continuam
  separados da formatação visual do corpo.
- Não colocar `"\n" + mensagem`, `mensagem + "\n"` ou `"\n".join(...)`
  dentro de uma função para decidir espaçamento. Declarar o formato na
  variável correspondente, perto do texto que será revisado.
- Conferir a mensagem completa nas rotas de titular, dependente, repetição,
  tratamento e retorno. Evitar quebras nos dois lados da mesma junção,
  palavras coladas e a união de blocos que precisam continuar separados.
  Preservar links completos, perguntas, negritos, botões e rodapés.
- A redução de espaçamento feita anteriormente não é uma regra automática
  de envio. Não diminuir novamente todas as quebras nem achatar parágrafos.
  Ao mover a formatação para variáveis, comparar o resultado antes e depois.
- Mensagens já persistidas não são reformatadas. A recuperação da etapa 6
  reconhece também o espaçamento anterior, exclusivamente para concluir retries.

Entusiasmo não pode afirmar algo que ainda não aconteceu. `Quero reservar`
expressa intenção; não significa que o dia e horário já foram escolhidos.
Perguntas da triagem devem permanecer neutras: não elogiar ou reprovar uma
resposta como `Nunca` ou `Frequentemente`, nem transformar triagem em diagnóstico.

## 2. Separar os momentos da mensagem

Uma etapa representa o que o bot está esperando do cliente. **Apresentar uma
etapa**, **repetir sua pergunta** e **acolher um retorno** são situações diferentes.
“Mensagem inicial da etapa” não significa começar outra conversa.

| Momento | Composição da fala | Efeito no fluxo |
|---|---|---|
| Entrada normal em uma etapa | Abertura coerente com o passo anterior + conteúdo/pergunta + componentes necessários | O fluxo já autorizou a apresentação desse destino. |
| Mídia, financeiro ou reforço em etapa apresentada | Orientação específica + retomada neutra da pergunta atual | O tratamento não autoriza avançar. |
| Contexto inválido em etapa apresentada | Mensagem própria que já pede a resposta correta, sem concatenar a repetição | Permanece na etapa atual. |
| Retorno por inatividade, sem follow-up pendente | Uma saudação de retorno + resposta que o fluxo normal produziria | A resposta do cliente continua sendo validada; pode avançar ou receber tratamento. |
| Reação a follow-up pendente, exceto na etapa 8 | Uma saudação + destino válido, tratamento específico ou repetição neutra | Usa os validadores normais; contexto inválido genérico apenas reapresenta a pergunta. |
| Reação a follow-up pendente na etapa 8 | Uma saudação de retorno + mensagem da etapa 9 | Avança diretamente de 8 para 9, sem repetir a 8 nem interpretar a reação como aceite da oferta. |
| Retry com resposta já persistida | Reutilização do registro existente | Não montar nem enviar outra mensagem. |

O conteúdo reutilizável é a **pergunta ou chamada principal**, não
necessariamente a mensagem normal inteira. Uma abertura como `Prazer`,
`Certo`, `Perfeito` ou `Maravilha` pode funcionar na entrada e não funcionar
depois de `Não consegui entender sua resposta`.

Exemplo da diferença na oferta:

```text
Entrada normal:
Maravilha, {nome_titular}! ☺️ Queremos te presentear com uma *demonstração prática gratuita* na nossa unidade!
[explicação da avaliação + pergunta sobre sua experiência Supera exclusiva]

Resposta não compreendida:
Olha, não consegui entender se você quer reservar sua experiência Supera gratuita.
Escolha Quero reservar para continuar ou Talvez mais tarde para deixar para outro momento.
```

Uma dúvida não precisa receber todo o discurso comercial novamente. O
tratamento financeiro e o de reforço escolar usam o prefixo compartilhado,
uma ponte como `Mas bora lá:` e a pergunta necessária para continuar.
Não acumular conectivos nem repetir esse prefixo dentro da mesma resposta.

## 3. A etapa 1 é a exceção de entrada

Há quatro grupos distintos em `etapa1_messages.py`:

| Grupo | Quando usar | Conteúdo |
|---|---|---|
| Apresentação inicial padrão | Primeiro contato, antes de a etapa 1 estar apresentada | Saudação, agente/unidade, acolhimento e pergunta do primeiro nome. |
| Apresentação inicial explicativa | O primeiro texto pergunta o que é o Supera ou pede informações gerais | Mensagem única aprovada: apresentação, explicação como academia para o cérebro e pedido do nome. |
| Apresentação inicial com tratamento | A primeira entrada já contém mídia, dúvida financeira ou ideia de reforço escolar | Apresentação/acolhimento + tratamento correspondente + pergunta do primeiro nome. |
| Tratamento após a apresentação | O bot já pediu o nome e a resposta precisa de orientação | Tratamento + pergunta do nome; no contexto de nome inválido, a orientação já contém esse pedido. Não repetir toda a apresentação. |

O tratamento inicial é uma **versão única da abertura**. Não enviar primeiro
o tratamento e depois outra mensagem inicial completa. A ordem exata das
frases deve formar uma única fala natural; hoje a apresentação vem antes
da orientação específica.

O tratamento de primeira entrada apresenta a etapa 1. Depois disso, uma
resposta válida de nome pode produzir a transição para a etapa seguinte.
Não tratar a primeira mensagem espontânea como nome só porque contém texto.

### Primeiro texto pedindo informações sobre o Supera

A prioridade do resolver é **mídia → reforço escolar → financeiro → pedido de
informações gerais → abertura padrão**. A apresentação explicativa só pode ser
selecionada quando `id_etapa_atual is None` e a entrada é `text`. Não classificar
novamente esse pedido depois que o bot já solicitou o nome.

`valida_inicio_etapa1.py` reconhece expressões completas como `O que é o Supera`,
`Do que se trata`, `O que é`, `Como funciona` e `Olá! Posso ter mais informações
sobre isso?`, com ou sem saudação, acentos e interrogação. Não depender de uma
palavra solta como `informações`. Pedidos sobre outro assunto e negativas não
são aceitos por esse classificador. Dúvidas específicas continuam nos tratamentos
existentes, inclusive quando misturadas ao pedido genérico.

`MENSAGEM_INFORMACOES_INICIO_ETAPA1` é uma mensagem completa: usa o texto aprovado
com `Hoje vou te ajudar a conhecer o Supera! 🧡`, a explicação da academia para o
cérebro e um único pedido do nome. Não concatenar a abertura padrão, a pergunta
de repetição ou um rodapé adicional. O montador somente formata saudação, agente,
artigo e unidade; a seleção da variante pertence ao resolver.

Ambas as aberturas apresentam a etapa 1 sem validar o primeiro texto como nome,
sem transição para a 2 e sem contar tratamento inválido. Após o nome válido,
seguem para a mesma etapa 2: `Prazer, {nome_titular}!` e `Então, o Supera…`.
Não há flag, coluna ou nova etapa para lembrar qual abertura foi usada.
Follow-up da etapa 1 mantém saudação sem nome + pergunta de repetição; não
reenvia essa explicação. Retry reutiliza a resposta já persistida.

Regras específicas:

- Antes de saber quem participará, a abertura não presume que a experiência
  será para o titular. Ela pode acolher a busca por informações sobre o Supera.
- Um nome de atendimento antigo não substitui a coleta do nome nesta conversa.
- No tratamento de **nome inválido**, a orientação `Olha, não consegui entender
  o seu nome. Digite só seu primeiro nome, por exemplo: Pedro.` já contém o
  pedido e o exemplo. Enviá-la sozinha, sem concatenar `MENSAGEM_REPETICAO_ETAPA1`
  nem usar `compor_tratamento`. A exceção é apenas de redação: permanece na
  etapa 1 aguardando um nome válido. Mídia, financeiro e reforço conservam suas composições com a pergunta.
  No follow-up, somente a resposta sem validação nem tratamento específico usa a repetição neutra.
- Na reação ao follow-up da etapa 1, usar `Bom te ver novamente ☺️`, sem nome antigo.
  Um nome válido informado na reação é aproveitado e leva à etapa 2; caso contrário,
  aplicar o tratamento específico identificado ou reapresentar a pergunta sem reprimenda.
- A saudação normal por três horas de inatividade não se aplica à etapa 1.
- Só a etapa 1 possui as variantes de **primeiro contato com tratamento**.
  Não reproduzir essa exceção automaticamente nas demais etapas.

## 4. As demais etapas seguem uma continuidade

Em cada etapa, separar **apresentação normal**, **tratamento com repetição**
e **mensagem própria de contexto inválido**.
Não criar tratamentos inexistentes só para preencher uma estrutura simétrica:
espera, pesquisa, encerramento e outras etapas têm contratos próprios.

O encadeamento deve ser lido como uma conversa: o bot acolhe a resposta
válida anterior e explica ou pergunta o próximo passo. Ao repetir, mantém o
assunto e a ação esperada, sem fingir que o cliente já respondeu corretamente.

### Contexto inválido: uma mensagem que já orienta a nova resposta

Esta exceção vale para **todas as etapas que tratam contexto inválido**,
incluindo nome, idade, escolhas, reserva, triagem e pesquisa. O texto explica
o que não foi compreendido e induz a responder corretamente, em uma única
fala. Não concatenar `MENSAGEM_REPETICAO`, a mensagem padrão, apresentação,
outro tratamento ou um segundo pedido equivalente. Não usar
`compor_tratamento` neste caminho.

Deixar claro que o bot **não entendeu a resposta do cliente**, sem sugerir
falha em uma ação já realizada. Por exemplo, evitar `Não consegui confirmar
sua reserva`: isso pode levar o cliente a reservar novamente e gerar duplicidade.
Preferir `Olha, não consegui entender sua resposta`, seguida da orientação
adequada à etapa, sem presumir que a reserva falhou.

Exemplo para idade do dependente:

```text
Olha, não consegui entender a idade de Lucas. Digite apenas o número, exemplo: 10.
```

Não acrescentar `Me diz, qual é a idade de Lucas?`. Quando a orientação
antiga disser apenas `Não entendi`, completá-la com a ação esperada dentro
da própria mensagem de contexto. Preservar titular e dependente, os dados
necessários (como o link da reserva), os botões/opções e o rodapé nativos,
sem duplicá-los. Os identificadores visuais nativos, como `Pergunta 1`,
continuam identificando a etapa; não são outra pergunta ou apresentação.

A única saudação de retorno que pode acompanhar esse tratamento é a de
**inatividade a partir de três horas**, quando elegível: saudação + mensagem
própria de contexto. Não acrescentar a repetição depois. A etapa 1 continua
fora da saudação de três horas. Na reação a follow-up pendente, o fluxo valida a resposta; se ela não for válida
nem corresponder a um tratamento específico, envia saudação + repetição neutra.

É uma regra de composição, não de validação. Botões, aceites por texto,
prioridades de classificação e eventos permanecem os mesmos. Não transformar
uma orientação para escolher um botão em uma restrição nova do validador.

### Titular e dependente

Quem conversa com o bot não é necessariamente quem fará a experiência.

Nos parâmetros, variáveis e campos de contexto usados para montar as mensagens,
usar `nome_titular` para quem conversa, `nome_dependente` para o dependente e
`nome_agente` para o chatbot. Não alternar esses papéis com `nome`, `nome_cliente`
ou `nome_bot` nos montadores e senders. O catálogo da triagem também recebe
`nome_dependente`; o titular continua sendo tratado como `você` nas perguntas.
Os repositórios traduzem os campos persistidos para esse contexto: a coluna
`cliente.nome` permanece igual. Esta padronização não exige migração nem altera
nomes de eventos já usados pelo mapa de transição ou contratos do painel e funil.

- Quando for para o titular, usar `você` e `sua experiência`.
- Quando for para um dependente, usar seu nome nas referências à participação,
  idade, perguntas da triagem, oferta e experiência que será reservada.
- Nas saudações de retorno, dirigir-se ao **cliente que está conversando**;
  no conteúdo seguinte, identificar o **participante** corretamente.
- Profissão e e-mail do cliente não passam a ser do dependente por causa da rota.
- A abertura da etapa 4 explica a coleta do perfil do titular ou dos dois perfis,
  conforme o destino confirmado na etapa 3. Nas duas rotas, a profissão pedida
  é de quem conversa. Tratamentos e repetição neutra usam somente a pergunta
  curta, sem repetir a explicação inicial; contexto inválido mantém sua orientação.
- `Sua reserva para a experiência de Lucas` é coerente: quem conversa realiza
  a reserva, enquanto Lucas participa da experiência.
- Na etapa de escolha do destinatário, o nome do dependente ainda pode não ter
  sido coletado. Não usar dados ausentes ou de outro atendimento para preencher.

Na apresentação da etapa 7, saudar `Maravilha, {nome_titular}! ☺️` nas duas
rotas. Para titular, continuar com `Queremos te presentear`; para dependente,
com `Queremos presentear {nome_dependente}`. A avaliação e a pergunta final
devem acompanhar quem participará. Os dois nomes chegam separadamente ao
montador; não usar o nome do dependente para saudar quem está conversando.

Mídia, financeiro e reforço continuam usando apenas tratamento + pergunta de
repetição, sem `Maravilha` nem a apresentação completa. Follow-up usa sua
saudação + repetição, e contexto inválido conserva a mensagem própria.
Nos demais pontos do atendimento, `experiência Supera gratuita` continua
adequado para reforçar a gratuidade, sem trocar todos os textos por `exclusiva`.

Alterar palavras não pode transformar a pergunta em outra decisão. O texto,
os botões, a interpretação de texto digitado e o evento precisam concordar.
Preservar os aceites legados e a flexibilidade aprovada; não endurecer os
validadores durante uma revisão de personalidade.

### Etapa 6: encaminhamentos por idade

A faixa configurável (50/60/70/80/90) encaminha somente titulares até 99 anos.
O caso de **100 anos ou mais** é uma regra geral para titular e dependente,
inclusive com suporte desativado, e tem mensagem própria sobre uma pequena
anamnese com um consultor. A redação não deve presumir que a pessoa conversando
será a participante quando a rota for de dependente.

Na mensagem de 100+, acrescentar uma vez o rodapé acolhedor
`Nosso time vai orientar os próximos passos. 🧡`, usando o componente de rodapé.
O botão abre o contato comercial. Não repetir a pergunta de idade, usar o
rodapé de seleção de opções ou prometer dia e horário já reservados.
Esse encaminhamento encerra o atendimento do bot; não é uma repetição de etapa.

### Mensagem pronta para o contato comercial

Todo botão de contato comercial deve abrir o WhatsApp com um pedido pronto.
Isso inclui tanto o suporte pela faixa configurada quanto o encaminhamento de
100+. O cliente ainda confirma o envio; clicar no botão não envia a mensagem.

O montador `montar_mensagem_contato_comercial_etapa6` identifica o chatbot,
a unidade e o cliente, usando os dados da conversa. Depois, adapta o pedido:

- Titular: `Me chamo {nome_titular}, tenho {idade_participante} anos e gostaria
  de reservar minha experiência Supera gratuita.`
- Dependente: `Me chamo {nome_titular} e gostaria de reservar uma experiência
  Supera gratuita para {nome_dependente}, que tem {idade_participante} anos.`

A origem comum é `Olá, vim do atendimento com {artigo} {nome_agente}, chatbot
da unidade {nome_unidade}.` O artigo acompanha o gênero do agente. A idade vem
da resposta atual da etapa 6: na rota de dependente, não inventar a idade do
titular nem atribuir a ele a idade do participante. O pedido expressa intenção
de reservar; não confirma uma reserva já realizada. Esta é a mensagem do lead
para o comercial, distinta da orientação que o bot envia antes do botão.

### Comentário livre e despedida: etapas 21 e 22

A etapa 21 não possui tratamento de contexto inválido. No fluxo normal,
qualquer comentário em texto leva à etapa 22, inclusive `ok`, `sim`, um emoji
ou pontuação. Não exigir uma opinião detalhada nem classificar o comentário
como dúvida financeira ou sobre reforço escolar. Não enviar `não consegui
entender seu comentário` nem pedir uma nova resposta por causa do conteúdo.

Permanece a orientação de mídia para escrever por texto. Recusa explícita,
texto vazio e botão antigo permitem concluir sem gravar um comentário; comentários
textuais livres são preservados. O retry deve reconstruir esse mesmo resultado.
O contrato de retomadas por follow-up permanece separado do fluxo normal.

A etapa 22 tem duas mensagens completas, sem repetição nem tratamento:

- Titular: `Estamos ansiosos para te receber na nossa unidade! 🧡`
- Dependente: `Estamos ansiosos para receber você e {nome_dependente} na nossa unidade! 🧡`

Os demais parágrafos de despedida são mantidos. Os dois caminhos de entrada,
recusa de comentário na etapa 20 e resposta na 21, precisam levar a rota e o
nome persistido do dependente ao sender. Respostas já gravadas são recuperadas
sem montar uma nova despedida. Essa variação editorial não muda o encerramento
nem o bloqueio de 30 dias.

## 5. Retornos são uma camada sobre a fala

O prefixo de retorno não deve ser copiado para cada arquivo de etapa. Sua
composição é coordenada pelo worker e aplicada ao envio e ao histórico.

### Inatividade normal: a partir de três horas

Com `followup_stage = 0`, o retorno **a partir de três horas**, inclusive,
desde o último envio confirmado do bot pode receber `Bom te ver novamente, {nome_titular} ☺️`.
O código não usa “até três horas”, nem envia uma mensagem automaticamente
quando esse prazo passa. Nome válido e horários compatíveis são necessários.

O cliente continua respondendo normalmente:

- resposta válida: saudação + apresentação da etapa de destino;
- dúvida de mídia, financeiro ou reforço: saudação + tratamento + pergunta atual;
- contexto inválido: saudação + mensagem própria de contexto, sem outra pergunta.

O prefixo não cria avanço, não impede avanço válido e não altera efeitos de
transição. Nunca acrescentá-lo novamente a uma resposta já persistida.

### Follow-up: lembrete e reação são momentos diferentes

O texto do lembrete proativo é definido em `followup_messages.py`. Ele é enviado
após sete horas e somente quando os demais critérios de elegibilidade forem
atendidos. Uma revisão de estilo não autoriza ampliar a elegibilidade do envio.

Existem duas camadas nas etapas 1–17, inclusive 8: o lembrete após 7h e a despedida
após mais 7h sem resposta desde o envio real do primeiro.

O primeiro lembrete usa `Olá, {nome_titular}! ☺️` quando o nome já foi informado
no atendimento; na etapa 1, usa `Olá! ☺️`, sem aproveitar nomes antigos.
Une “Queremos muito continuar te ajudando” ao convite para receber a
**experiência Supera gratuita** na unidade. Após `\n\n`, nas etapas 1–6 pergunta
“Podemos continuar seu atendimento por aqui?”. Nas etapas 7–17, após a oferta,
pergunta “Podemos continuar por aqui para reservar sua experiência?”; para
dependente, usa “reservar a experiência de {nome_dependente}” ou, se faltar o
nome, “reservar a experiência”. A pergunta convida a reservar, sem sugerir que
já existe uma reserva confirmada. Essa variação não altera a elegibilidade do envio.
No convite, para titular usa “receber você”; para dependente com nome, “receber
você e {nome_dependente}”; para dependente ainda sem nome, “receber vocês”, sem
presumir que a experiência será para o titular. O rodapé de todas as variantes é
`Estaremos te esperando!`, sem emoji.

A despedida usa
“para aproveitar todos os benefícios” nas duas rotas e assina com `{nome_agente}`.
Na etapa 1, nunca usa nome de cadastro anterior. Na rota dependente, usa
“você e {nome_dependente} não estão preparados”, sem repetir o nome após “benefícios”;
se o nome ainda não foi coletado (nulo, vazio ou só espaços), usa a mesma mensagem
do titular, sem alterar a rota da conversa. O corpo termina com
`Fico à disposição caso precise falar comigo novamente! ☺️👋` e o rodapé é
`Abraços, {nome_agente}. 🧡`. Os dois follow-ups usam o componente de rodapé em
itálico, separado do corpo por `\n\n` (uma linha em branco). Não acrescentar prefixo
de retorno, tratamento, pergunta da etapa ou botões aos envios proativos.

O segundo envio confirmado encerra a conversa, preservando stage 2. Uma mensagem
posterior inicia outro atendimento com a mensagem inicial da etapa 1, sem prefixo
de retorno. As regras de reação abaixo valem para a conversa ainda ativa, antes
desse encerramento, e para recuperações legadas.

Na primeira reação aceita com follow-up pendente:

1. usar `Bom te ver novamente, {nome_titular} ☺️` ou `Bom te ver novamente ☺️`
   na etapa 1/sem nome autorizado, sempre uma única vez;
2. reutilizar os validadores e a ordem de prioridade dos tratamentos da etapa;
3. resposta válida: avançar normalmente, com saudação + mensagem de destino;
4. tratamento específico reconhecido: saudação + tratamento + pergunta atual;
5. sem resposta válida nem tratamento específico: saudação + repetição neutra,
   preservando participante, botões e rodapés nativos, sem orientação de contexto inválido;
6. na triagem, aceitar somente as opções canônicas; respostas inválidas repetem a
   pergunta, sem introduzir tratamentos financeiros, de mídia ou reforço;
7. zerar `followup_stage` no sucesso, junto dos efeitos, histórico e finalização da fila.
   Se não avançar, essa primeira reação não incrementa `turnos_sem_avanco`.
   Uma transição válida zera o contador normalmente; as próximas respostas seguem
   as regras normais. Uma falha reverte a transação inteira.

**Exceção da etapa 8 — oferta adiada:** qualquer reação processada pelo flow
com follow-up pendente leva diretamente à etapa 9. Não enviar novamente a
mensagem inicial da 8, uma variante de repetição, sua despedida ou o Instagram.
A etapa 8 não possui mensagem de repetição. A resposta contém o prefixo de
follow-up uma única vez e a oferta da etapa 9, preservando titular/dependente,
botões e rodapé. Mesmo `Quero reservar` nessa reação apenas leva à 9; a próxima
resposta será validada pela etapa 9.

O worker reutiliza o resolver e a transição normal `8 → cliente_retornou → 9`.
O histórico da reação permanece na 8; a resposta do bot é registrada na 9.
Avanço, resposta e conclusão do follow-up são confirmados juntos. Uma falha
reverte esses efeitos; recuperar uma resposta já confirmada não reenvia nem
zera um ciclo posterior. Essa regra também vale para retomada legada pendente.

Esse prefixo substitui a saudação de três horas; não se somam os dois. Uma
saudação própria, como a da etapa 9, também deve ser suprimida quando já houver
saudação externa. A fala inteira deve ser acolhedora, sem parecer um novo
primeiro encontro ou anunciar um avanço que não ocorreu.

O catálogo de reapresentação contém etapas legadas que não são elegíveis para
um novo lembrete. Sua existência não autoriza envio proativo nessas etapas.
Consulte o [contrato de follow-up](../../../../REGRAS_DE_NEGOCIO.md#follow-up-de-inatividade-e-reação-do-cliente).
As exceções propostas no plano futuro de `user_id` não estão ativas neste código.

## 6. A triagem tem um contrato próprio

Na base atual, as seis perguntas são as etapas 12–17. Elas não possuem os
tratamentos específicos de mídia, financeiro e reforço escolar das etapas
comerciais. Existe apenas a mensagem própria de **resposta da triagem inválida**,
que orienta responder à pergunta já apresentada usando uma das opções
`Nunca`, `Às vezes` e `Frequentemente`. Não concatenar novamente a pergunta.

As perguntas canônicas estão em `core/triagem/perguntas.py`; não duplicá-las
nos arquivos de mensagens nem reescrever seu significado numa revisão de tom.
A etapa 11 é a introdução à triagem e conserva seus próprios tratamentos.

**Na etapa 11, o participante já está definido.** Manter versões explícitas
para titular e dependente na mensagem inicial, na repetição e no contexto
inválido. Para o titular, usar `sua triagem` e `seu cérebro`; para dependente,
usar `a triagem de {nome_dependente}` e `o cérebro de {nome_dependente}`. Não substituir as duas
rotas por uma fala genérica sobre `quem participará`, nem falar da triagem
do titular quando quem participará é o dependente.

A mensagem inicial apresenta as seis perguntas e sua finalidade; a repetição
retoma apenas o convite para iniciar e a finalidade da triagem. Financeiro,
mídia e reforço usam essa repetição com o participante correto. Contexto inválido
tem mensagem autônoma, sem concatenar outra pergunta. Inatividade e follow-up
preservam a rota e aplicam seu prefixo uma vez, segundo seus contratos.

O contexto da etapa 10 fornece o nome para apresentar a 11; a própria 11 e o
retorno de follow-up relêem o participante persistido. Dependente sem nome é
inconsistência, nunca motivo para usar silenciosamente a mensagem de titular.
Revisões de texto devem conferir também a continuidade nas perguntas 12–17,
que citam o nome do dependente tanto na faixa infantil quanto na adulta.

As seis perguntas continuam sujeitas aos dois caminhos de retorno:
ambos validam a resposta; no follow-up, uma opção válida avança e é salva,
enquanto uma entrada inválida reapresenta a pergunta sem tratamento genérico. Manter o número da pergunta, a faixa
etária, o nome do dependente e o rodapé de opção única. Não acrescentar oferta
comercial ou celebração a cada resposta da triagem.

## 7. Organização dos arquivos e do código

Cada etapa é dona da sua mensagem padrão e da sua mensagem de repetição.
Na etapa 8 existe somente a mensagem inicial: o retorno apresenta a etapa 9.
Cada tipo de tratamento é dono da orientação compartilhada. O arquivo da
etapa importa o montador do tratamento e entrega a ele sua repetição pura:
**tratamento → ponte, quando necessária → repetição da etapa**.
Contexto inválido é a exceção: sua mensagem completa pertence à etapa e não
passa pelo compositor de orientação + repetição.

| Arquivo | Responsabilidade |
|---|---|
| `etapaN_messages.py` | Mensagem padrão, repetição pura, contexto inválido autônomo, variantes de participante e composição dos demais tratamentos. |
| `tratamentos/financeiro.py` | Explicação sobre investimento e gratuidade da experiência, seguida da repetição recebida. |
| `tratamentos/midia.py` | Orientação para responder por texto; só oferece opções quando a etapa realmente possui botões. |
| `tratamentos/reforco_escolar.py` | Explicação sobre a proposta do Supera, seguida da repetição recebida. |
| `tratamentos/retorno_inatividade.py` | Elegibilidade e saudação de retorno a partir de três horas. |
| `tratamentos/retorno_followup.py` | Saudação da reação ao follow-up, inclusive a forma sem nome. |
| `tratamentos/composicao.py` | Compositores distintos para mensagem inicial e tratamento, com formatação compartilhada e aplicação única do prefixo de retorno. |
| `componentes_compartilhados.py` | Cabeçalhos e rodapés compartilhados. Mantém os imports antigos de inatividade por compatibilidade. |
| `followup_messages.py` | Primeiro lembrete e despedida personalizada do segundo. Reexporta a saudação antiga por compatibilidade. |
| `tratamentos_universais.py` | Fachada de compatibilidade dos imports antigos; não possui outra cópia dos textos. |
| `triagem_componentes.py` | Opções, rodapé e orientação autônoma de contexto comuns às seis perguntas; não contém as perguntas canônicas. |
| `README.md` | Este contrato de composição, personalidade e revisão. |

Ao criar ou reorganizar um arquivo, usar blocos identificados nesta ordem:

1. finalidade da etapa e exceções relevantes;
2. constantes da mensagem padrão e da repetição, com variantes de participante;
3. montador da apresentação normal, aceitando `repeticao=True` quando cabível;
4. montadores de tratamento: importar e compor com a repetição, exceto contexto,
   que retorna sua própria mensagem completa;
5. botões, cabeçalhos e rodapés específicos;
6. auxiliares privados de composição e validação de dados de apresentação.

Na etapa 1, reservar blocos distintos para os três grupos da seção 3. Usar
`inicio` para as versões exclusivas de primeiro contato, sem confundi-las
com o tratamento após a pergunta do nome.

Constantes podem usar `MENSAGEM_`, `PERGUNTA_`, `PREFIXO_`, `BOTAO_`,
`CABECALHO_` e `RODAPE_`; montadores usam `montar_...`. Não renomear toda a
API existente apenas por estética. Ao mover declarações, preservar a ordem
de dependências e todos os imports dos consumidores.

### Comentários que explicam a organização

Os comentários da etapa 7 são a referência para tornar o papel de cada bloco
visível durante a leitura. Eles devem explicar **onde o trecho é usado e por
que ele está separado**, especialmente quando a mesma pergunta participa da
mensagem inicial e da repetição.

Usar `### TÍTULO DO BLOCO` para as divisões principais, como na etapa 7, e
`# Explicação curta` para detalhes locais. Ambos são comentários Python.
Escrever em português, próximos ao trecho correspondente, sem depender de
números de linha ou de explicações dadas nesta conversa.

Exemplo de composição com um fragmento compartilhado:

```python
### APRESENTAÇÃO INICIAL DO TITULAR
APRESENTACAO_TITULAR = (
    "Maravilha, {nome_titular}! ☺️ Queremos te presentear com uma "
    "*demonstração prática gratuita* na nossa unidade!\n"
)

### TRECHO USADO NA MENSAGEM INICIAL E NA REPETIÇÃO
MENSAGEM_REPETICAO_TITULAR = "Vamos reservar sua *experiência Supera exclusiva*?"

### MENSAGEM INICIAL: APRESENTAÇÃO + REPETIÇÃO
MENSAGEM_PADRAO_TITULAR = compor_mensagem_inicial(
    APRESENTACAO_TITULAR,
    MENSAGEM_REPETICAO_TITULAR,
)

### FINANCEIRO: ORIENTAÇÃO + REPETIÇÃO, SEM A APRESENTAÇÃO
def montar_mensagem_financeiro():
    return montar_mensagem_tratamento_financeiro(MENSAGEM_REPETICAO_TITULAR)


### CONTEXTO INVÁLIDO: MENSAGEM PRÓPRIA, SEM CONCATENAR A REPETIÇÃO
def montar_mensagem_contexto_invalido():
    return (
        "Olha, não consegui entender se você quer reservar sua experiência. "
        "Escolha Quero reservar ou Talvez mais tarde."
    )
```

Aplicar estes cuidados:

- Identificar mensagem inicial, pergunta de repetição e composição quando
  essa separação ajuda a entender o arquivo. Uma mensagem inicial já completa
  não deve receber um comentário dizendo que ainda será concatenada.
- Dizer que o fragmento é compartilhado com a inicial **somente quando isso
  acontece no código**. Algumas etapas têm perguntas diferentes para cada momento.
- Indicar titular e dependente nos blocos que possuem as duas rotas. Os
  tratamentos devem preservar o participante, inclusive no contexto autônomo.
- Explicar exceções junto do código: contexto inválido já pede a resposta;
  etapa 8 não se repete e retorna para a 9; etapa 9 evita somar saudações.
- Na triagem, comentar que a pergunta vem do catálogo central na apresentação
  e no follow-up; contexto inválido usa sua orientação própria, sem repeti-la.
  Não criar seções de tratamentos
  financeiros, mídia ou reforço onde esses tratamentos não existem.
- Comentar a entrada de um grupo de funções, sem repetir a mesma explicação
  em cada função nem narrar operações óbvias linha por linha. Preservar
  comentários existentes que já expliquem corretamente o bloco.
- Descrever a responsabilidade real: o montador **formata a mensagem**;
  não valida a resposta do cliente, decide avanço, consulta banco ou envia.
- Atualizar o comentário junto com o código quando mudar a composição.
  Ele deve descrever o comportamento vigente, não uma intenção futura.

A etapa terminal não precisa de seções artificiais de apresentação/repetição
se possui apenas uma mensagem de encerramento. Os comentários organizam a
leitura; não exigem que todas as etapas tenham as mesmas funções.

### Mensagem inicial e tratamento têm compositores diferentes

Quando a pergunta da repetição também encerra a mensagem inicial, declarar
esse fragmento uma única vez e compartilhá-lo:

```python
APRESENTACAO = "Vamos conhecer o Supera! ☺️\n"
ORIENTACAO = "Olha, responda por texto para continuarmos.\n"
MENSAGEM_REPETICAO = "Me diz, qual é a sua profissão?"

MENSAGEM_PADRAO = compor_mensagem_inicial(
    APRESENTACAO,
    MENSAGEM_REPETICAO,
)

MENSAGEM_TRATAMENTO = compor_tratamento(
    ORIENTACAO,
    MENSAGEM_REPETICAO,
)
```

- `compor_mensagem_inicial` monta **apresentação + repetição** na entrada da
  etapa. Por exemplo, a oferta com `Maravilha!` termina em `Vamos reservar…`.
- `compor_tratamento` monta **orientação + ponte opcional + repetição**.
  Recebe apenas a pergunta reutilizável, nunca a mensagem padrão completa.
  Não é usado em contexto inválido, cuja mensagem já contém a orientação completa.
- Ambas reutilizam `_concatenar_fragmentos` internamente. Esse auxiliar
  apenas concatena: os espaços e as quebras estão nas variáveis de mensagens.
  Não escolhe o cenário nem decide o fluxo.

Não inserir a pergunta em `APRESENTACAO` se ela já será acrescentada pelo
compositor: isso duplicaria o trecho final. Quando apresentação e repetição
tiverem redações diferentes, manter suas variantes sem forçar o compartilhamento.

A exceção de primeiro contato da etapa 1 permanece: o tratamento monta a
orientação com a pergunta; o compositor inicial acrescenta a apresentação
uma única vez. Após essa entrada, mídia, financeiro e reforço usam orientação e
repetição; contexto inválido usa sua mensagem própria. Prefixos de inatividade
e follow-up continuam na camada de retorno.

Exemplo do padrão aplicado à confirmação da etapa 3:

```python
MENSAGEM_PADRAO_TITULAR = "Você confirma que esse atendimento é para você? ☺️"
MENSAGEM_REPETICAO_TITULAR = "Me confirma: esse atendimento é para você?"

# O montador importado acrescenta a orientação antes desta pergunta.
mensagem = montar_mensagem_tratamento_financeiro(MENSAGEM_REPETICAO_TITULAR)
```

As variantes para dependente seguem a mesma estrutura. O texto de repetição
pode compartilhar conteúdo com o padrão, mas não carrega sua celebração,
apresentação ou despedida. Não manter uma pergunta diferente para cada
tratamento de mídia, financeiro ou reforço: eles reutilizam a repetição da rota.

Orientações de contexto exclusivas de uma etapa (nome, idade, nota fora da
escala etc.) continuam nela como mensagens completas, sem `compor_tratamento`
nem mensagem de repetição. Não mover regras específicas para um catálogo
genérico. Etapas terminais e perguntas canônicas não precisam de variantes
artificiais. A exceção de contexto vale para todas as etapas, não só para nome.

Nos retornos, a saudação é aplicada uma única vez pelo transporte coordenado
pelo worker. Isso preserva a ordem **retorno → tratamento, se o fluxo normal
o escolher → repetição** na inatividade, exceto contexto: **retorno → mensagem
própria de contexto**. No follow-up, o worker usa os mesmos validadores e
tratamentos específicos; somente a resposta inválida sem tratamento específico
seleciona a repetição neutra (`repeticao=True`) sem mensagem de contexto.
Na triagem, usa a pergunta canônica sem esse parâmetro. A etapa 9 suprime
sua saudação própria quando recebe repetição ou `incluir_saudacao=False`.

O nome do dependente deve chegar também aos tratamentos da reserva por link,
não apenas à apresentação normal. O contexto consulta o participante da
mesma conversa/unidade; ausência de nome em uma rota dependente é erro de
contexto, não autorização para trocar a mensagem para a rota titular.

### Fronteiras de responsabilidade

```text
contexto/worker: escolhe cenário, participante e transição
        -> sender: usa o montador e envia
            -> messages: monta o conteúdo com os dados recebidos
```

`messages` não consulta banco, não importa PyWa, não valida a resposta do
cliente, não seleciona destino e não grava histórico. Pode validar os dados
necessários para montar a apresentação. Senders e worker devem conservar no
histórico a mesma fala que foi enviada, inclusive prefixos e cabeçalhos.

O controle do prefixo está em `pywa_functions/cliente.py`; sua aplicação aos
fluxos está em `flow_sender.py`, `retomada_followup.py` e `repeticao_followup.py`. Essa separação deve
permanecer. Não criar uma cópia dos fluxos dentro da pasta de mensagens.

## 8. Como revisar uma alteração

Ler o conjunto **mensagem anterior → resposta do cliente → próxima fala**,
não apenas uma constante isolada. Conferir os cenários pertinentes:

- entrada normal e tratamento, com os dados reais esperados em cada momento;
- titular e dependente, sem trocar destinatário, nome ou idade;
- retorno por inatividade com resposta válida e com resposta inválida;
- contexto inválido completo por si só, sem concatenar a pergunta de repetição;
- reação ao follow-up com saudação única: avanço válido, tratamento específico
  ou repetição neutra; preservar a exceção de 8 para 9;
- botões e rodapés, sem repetição e com a mesma ação aceita pelo validador;
- nomes ausentes e dados de atendimentos anteriores;
- texto efetivamente enviado e registro no histórico;
- recuperação com resposta persistida, sem novo envio.

Não basta contar emojis ou procurar uma palavra no arquivo: a fala final
precisa fazer sentido. Usar os testes de mensagens, saudação e follow-up
quando a mudança afetar composição, dados, envio ou retomada. Correções
ortográficas simples não exigem criar testes que espelhem cada frase.

Planos futuros que substituem arquivos completos devem preservar este
contrato e reconciliar suas mensagens com a base mais recente. A numeração
de etapas de um plano não deve ser antecipada no código em produção.

## 9. Aperfeiçoamentos aplicados em 21/09/2026

- **Etapa 2:** a repetição retoma a pergunta do destinatário sem `Prazer`.
- **Etapa 8:** a mensagem com Instagram pertence somente à entrada na etapa.
  Qualquer reação ao follow-up avança diretamente para a 9, sem repetir a 8.
- **Mídia:** a orientação compartilhada usa linguagem simples e acolhedora,
  com texto ou botões conforme os recursos reais da etapa.
- **Etapas 3–6:** a confirmação e a coleta de profissão, nome do dependente
  e idade ganharam acolhimento moderado, sem alterar o que é perguntado.

Quando precisarem repetir a etapa, os retornos usam a repetição neutra: não
reapresentam o agente na etapa 1, não comemoram novamente a oferta e não agradecem
outra vez pelas perguntas antes do link. Desde a revisão de 23/09/2026, a reação
ao follow-up é validada normalmente, com a exceção da etapa 8 descrita acima.
Os validadores, eventos e critérios de elegibilidade permanecem os mesmos.
