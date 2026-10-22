# Chat Fire, apresentações e turno antecipado — 21/10/2026

Complemento aplicado ao contrato de coleta parcial da V1.14.0. O código local
inclui estas regras; a produção exige as migrações e o deploy coordenado.

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
posse (“Meu nome”) e negação não definem participante. A compatibilidade com o
dashboard conserva a relação conhecida para priorizá-la. Na complementação,
amiga e filha também podem corresponder pelo mesmo valor lógico de dependente.

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

Os canais elegíveis passam a ser Google Ads, Meta Ads, Orgânico Site e Chat Fire.
Selecionar uma única inscrição do telefone, em canal elegível, sempre compatível
com nome/e-mail já aceitos. Quando o destinatário for conhecido, procurar nesta
ordem: relação exata; mesmo valor lógico titular/dependente; demais registros
compatíveis. Dentro de cada prioridade, usar data/hora mais recente e depois
maior linha. Assim, “Minha filha” pode aproveitar o e-mail de “Minha amiga” se
não houver inscrição compatível com a relação exata.

Somente no último recurso, com destinatário divergente/ausente na planilha, o
turno já aceito em unidade sem link também precisa coincidir. Turno vazio,
inválido ou diferente nessa linha não satisfaz o último recurso. Com relação
exata ou mesmo tipo lógico, o turno da planilha não bloqueia a inscrição. Sem
destinatário conhecido, manter a seleção mais recente por nome/e-mail, para
completar o que falta. Nenhum valor já aceito da mensagem é sobrescrito.

A linha escolhida fica vinculada à consulta e à entrega posterior, que acrescenta
somente as observações. A relação no cadastro da planilha permanece intacta,
mesmo quando o atendimento atual é para outro destinatário. Para entregas sem
consulta/referência anterior, permanece a seleção específica de destino descrita
no contrato de coleta; esta ampliação trata da complementação na consulta inicial.

Nome, Email, Para quem é e Período preferido completam apenas campos pendentes.
Não misturar inscrições. Campo ausente, incompatibilidade, erro e timeout mantêm
os dados já aceitos e deixam a coleta restante para o atendimento.

Exemplo Alline: extrair nome e Sábado da mensagem; obter e-mail no registro Chat
Fire compatível; “Para quem é” vazio inicia a pergunta de destinatário na etapa 2.
E-mail e turno já coletados não serão perguntados novamente.

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

A etapa 18 mantém seus três botões e aceita Sábado por texto, com orientação na
pergunta. Nenhum formulário antigo ou conversa já iniciada é reprocessado.

## Canais e entrega

| Origem | Código Funil |
| --- | --- |
| Google Ads | 113336 |
| Meta Ads | 113340 |
| Orgânico Site | 113481 |
| Chat Fire | 113481 |
| Orgânico | 113481 |

Chat Fire é uma origem própria (`chat_fire`). As observações compactas o identificam
no cabeçalho, por exemplo `NOVO LEAD : CHAT FIRE : TITULAR`. Os snapshots
salvos continuam sendo a fonte de verdade dos retries. A entrega atualiza apenas
Observação da linha vinculada; não altera Para quem é ou Período preferido da
planilha. A preferência consta do resumo enviado aos dois sistemas.

A sincronização desses campos foi isolada no
[plano prático futuro](fireads_sincronizacao_campos.md). Não está ativa e não é
pré-requisito deste deploy de Chat Fire/turno; depende de liberação posterior
das colunas editáveis pela FireAds.

## Migração e validação

Se a coleta parcial ainda não foi aplicada, usar apenas o consolidado
`deploy/migrations/20261021_coleta_chat_fire_completa.sql`, inteiro, com webhook
e todos os workers parados. Ele reúne os mesmos blocos das duas migrações em uma
transação; não é necessário executar os arquivos separados nesse deploy.

Como alternativa ao consolidado, com webhook e todos os workers parados, executar primeiro
`deploy/migrations/20261019_coleta_abertura.sql` se ainda pendente, depois
`deploy/migrations/20261021_chat_fire_turno_coleta.sql` inteiro. O segundo SQL
amplia os checks de origem/turno, o tamanho de turno para seis caracteres e a
aresta 17 → 19. Não reclassifica registros nem reprocessa conversas antigas.
Conferir migracao_ok, transicao_ok e tamanho_turno=6. Não usar setup em produção.

Testes unitários: `tests.unit.test_chat_fire_turno`, `test_coleta_abertura`,
`test_fluxo_reserva_link`, `test_fireads_aba_geral`. Integração:
`tests.integration.test_coleta_abertura_postgres` e `test_fireads_postgres`,
apenas em PostgreSQL descartável local e com fronteiras externas simuladas.
