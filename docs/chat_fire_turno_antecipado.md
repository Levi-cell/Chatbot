# Chat Fire, apresentações e turno antecipado — 21/10/2026

## Abertura

Somente a primeira mensagem de uma conversa nova é extraída, após as guardas de
pagamento, unidade, bloqueios e posse. Apresentações como “Olá! Sou Alline”,
“Eu me chamo Ana”, “Eu sou João”, “Meu nome é Maria”, “Aqui é Carlos” e “Pode me
chamar de Ana” fornecem candidatos de nome. Continuação da frase não integra o
nome. Papéis, profissões e localização conhecidos não são nomes; apresentações
sem identificação segura seguem a consulta e/ou a pergunta normal.

**“Quem vai fazer” é aceito como campo de destinatário**, assim como “Para quem é”.
“Para mim” define titular; “Meu filho”, “Minha filha”, “Para uma amiga”,
“Para um conhecido” e demais relações explícitas definem dependente. Frases
curtas sem rótulo, como “Minha amiga” e “Meu filho”, também são extraídas.
Criança, adulto, idoso e Perfil/Faixa não definem destinatário, mesmo sob o rótulo
“Quem vai fazer”. Frases soltas de indicação (“Minha amiga me indicou vocês”),
posse (“Meu nome”) e negação não definem participante. A relação já aceita é preservada; ela não filtra registros na consulta.
A identificação da linha usa somente telefone e recência.

Sem link de agendamento na unidade, turno é o quarto campo da coleta. Reconhece
Manhã, Tarde, Noite e Sábado em rótulos como “Melhor período”, “Período preferido”,
“Turno” e “Turno de preferência”, além de frases explícitas de escolha. Saudação,
menção a horário de trabalho, negação e múltiplas preferências não confirmam turno.
Valores diferentes ficam pendentes/conflitantes; repetições equivalentes não.

Com link, não extrair nem exigir turno. Sem link e com FireAds, faltar qualquer
campo necessário solicita a consulta inicial existente, uma única vez por conversa.
Com todos os campos necessários aceitos, a mensagem dispensa essa consulta.
Sem FireAds, aproveitar a mensagem e perguntar o que faltar na respectiva etapa.

## Complementação pela FireAds

Google Ads, Meta Ads, Orgânico Site e Chat Fire participam da seleção.
Orgânico, Indicação e Lead Franqueador não fornecem dados nem são reutilizados
automaticamente em nova conversa. Selecionar uma única linha do mesmo
telefone por data/hora e depois maior linha, usando todas as variantes suportadas.
Nome/e-mail, destinatário e turno diferentes não excluem essa linha. Completar
apenas campos pendentes; nunca misturar dados de várias inscrições.

Mensagem completa dispensa a consulta inicial; sua estrutura não comprova Meta.
A entrega confirma o canal antes dos dois envios, inclusive sem consulta inicial.
Exemplo Alline: manter nome e Sábado da mensagem, buscar e-mail na linha mais
recente do telefone; destinatário ainda ausente inicia pergunta na etapa 2.
E-mail e turno aceitos não são perguntados novamente.

## Persistência e transição

Reutilizar `conversa.contexto_coleta` para candidatos, fontes e a decisão de coletar
turno. Reutilizar `conversa.turno` para a preferência persistida, incluindo sabado.
A importação ocorre na mesma transação de abertura e sob os locks existentes.
Retries não reextraem outra mensagem nem criam outra consulta.

Ao responder validamente a sexta pergunta da triagem:

- Com link atual: manter 17 → 20, mesmo se existir turno histórico.
- Sem link e sem turno: manter 17 → 18 → 19.
- Sem link e com turno: evento `triagem_concluida_turno_coletado`, 17 → 19.

O salto preserva a sexta resposta, o contexto, o histórico e a recuperação sem
novo envio. Mensagem inválida na triagem não aciona o salto. A preferência é
exibida no contato comercial, monitoramento e observações compartilhadas do
Funil/dashboard. Não representa confirmação de agendamento.

A etapa 18 apresenta manhã, tarde, noite e sábado em uma lista e também aceita respostas por texto. A [integração FireAds](fireads.md) descreve a entrega e o tratamento de registros orgânicos. As regras históricas de migração estão nos [scripts incrementais](../deploy/migrations).
