# Atendimento determinístico e atendimento com IA

Revisão: **07/10/2026**. Status: **comportamentos de IA aprovados no plano;
nenhuma alteração de código ou banco nesta etapa**.

Base determinística de referência: **V1.9.2**, já com reserva com/sem link,
**24 etapas e 28 transições antes da FireAds**. A IA ainda não foi implementada. Este comparativo
e o plano unificado usam a numeração atual; a etapa 18 agora coleta turno,
a 19 entrega o contato comercial e a 20 apresenta o link.

Decisão de 04/10: cada nova conversa começa pela coleta normal. A IA não reconhece
o cliente por conversas encerradas nem apresenta dados antigos para confirmação.
Antecipações e correções dentro da conversa atual continuam permitidas.

Complemento de 07/10, ainda planejado: a [FireAds](../docs/integracao_fireads.md)
criará `chat`/`conversa.id_chat` antes da IA. A IA reutiliza esses vínculos e o
mapa ampliado dessa entrega, sem recriar o chat nem retornar à contagem antiga
de transições. Importação válida de formulário na abertura da conversa resolve
nome/e-mail/destino e inicia na profissão **também no Básico e no fallback**.
É uma exceção determinística à coleta inicial, não reconhecimento por histórico
de conversas encerradas. Ausência/erro/dados inválidos mantêm a coleta completa.

Decisão de 05/10: IA somente no primeiro follow-up, com consumo mensal no mesmo
chat/unidade; segundo follow-up determinístico e encerramento obrigatório. Funil
apresenta parentesco, condições e observação salvos no banco, sem nova chamada à IA.

Complementa o [plano principal](plano_ia_hibrida_atendimento.md). A estrutura
`chat` e os limites em dois níveis estão definidos no
[desenho de consumo](plano_ia_hibrida_atendimento.md#consumo-ia). A medida escolhida é tokens;
valores das cotas ainda serão definidos. O excesso entre apurações da unidade
Plus e no último ciclo autorizado do chat foi aceito para a primeira versão;
o [controle estrito](<ideias futuras/ideia_limites_ia_sem_ultrapassagem.md>) fica para o futuro.
Básico não tem IA; Plus limita chat/unidade; Pro limita apenas o chat, com teto maior.
Subcontagem por tokens não recuperados após falha também é risco aceito; a
[conciliação](<ideias futuras/ideia_conciliacao_consumo_ia.md>) será estudada depois.
Os modelos, orçamento e valores numéricos serão discutidos por último.

## 1. Três caminhos, com responsabilidades distintas

**Básico — determinístico puro:** conservar exatamente as regras de atendimento
da base implantada, incluindo a importação FireAds quando aplicada. A IA e a
estrutura universal de chat não autorizam outras mudanças em suas mensagens,
validadores, ordem de etapas ou política de suspeita/bloqueio.

**Híbrido com IA:** interpretar perguntas abertas, antecipações e correções; usar
operações validadas e etapas existentes. Pode escolher mensagens prontas quando
elas já atendem à entrada.

**Híbrido em fallback:** nenhuma nova chamada de IA. O controlador determinístico
continua a partir do estado confirmado do híbrido. Precisa de pequenas rotinas de
continuidade; não pode simplesmente reiniciar o fluxo ou interpretar toda entrada
pelos validadores legados sem considerar qual pergunta foi enviada.

| Situação | Determinístico puro / Básico | Híbrido com IA | Fallback do híbrido |
| --- | --- | --- | --- |
| Nova conversa sem importação FireAds válida, mesmo com cadastro anterior | Começa na etapa 1, como hoje. | Pergunta o nome novamente; aproveita dados antecipados na própria conversa nova. | Coleta normal, preservando dados já validados nesta conversa se houve IA antes da falha. |
| Importação FireAds válida nesta abertura | Inicia na profissão; dispensa nome, destino, confirmação e e-mail pelo formulário. | Recebe as mesmas coletas resolvidas e adapta apenas onde autorizado. | Preserva a importação e a pergunta pendente; não exige IA nem pergunta dados já resolvidos. |
| Destino ou outros dados antecipados | Validadores/transições atuais. | Registra dados claros e pula perguntas/coletas já resolvidas, inclusive confirmação de destino inequívoco. | Preserva antecipações já confirmadas e pergunta só a pendência; não inventa novas interpretações livres. |
| Dependente após conversa encerrada no segundo follow-up | Coleta atual; destino pode vir de importação FireAds válida. | Não oferece dependente antigo; coleta os dados pendentes, aproveitando destino do formulário e antecipações atuais. | Segue a coleta nova, sem importar dados do atendimento encerrado. |
| E-mail e profissão em nova conversa | Profissão mantida; e-mail dispensado somente se validamente importado nesta abertura. | Coleta pendências; pode aproveitar antecipação atual ou e-mail importado, sem apresentar dados antigos para confirmação. | Mesma origem atual dos dados; preserva correções e esclarecimentos pendentes. |
| Correção de dado sem substituto | Tratamentos existentes. | Abre correção e guarda o ponto de continuação. | Resolve pendência estruturada e retoma a próxima coleta necessária. |
| Troca de dependente já confirmada | Comportamento atual. | Mesmo ID; pergunta nome e idade novamente e refaz triagem, sem herdar o perfil anterior. | Mantém invalidações e coleta pendente; nunca recupera perfil antigo para facilitar fallback. |
| Correção do nome com o nome correto já informado | Comportamento atual. | Corrige na etapa atual, preserva idade/triagem e avança somente se a coleta atual também foi resolvida. | Preserva o que já foi validado; não exige nova geração nem repete efeitos. |
| Nome do dependente contestado, sem nome correto | Comportamento atual. | Pergunta o nome na etapa 5 e retorna; não pergunta automaticamente se outros dados mudaram. | Lê campo e retorno persistidos e conclui a correção, preservando dados independentes. |
| Pedido para refazer a triagem | Comportamento atual. | Reabre as perguntas, atualiza respostas preservando os IDs existentes e mantém cadastro da mesma pessoa. | Continua a revisão persistida; não usa respostas antigas para pular perguntas pendentes. |
| Parentesco do dependente | Não acrescenta pergunta à coleta atual. | Preenche somente se o cliente revelar a relação; sem pergunta própria, mantém NULL se não informado. | Preserva o valor validado; não inventa relação nem cria coleta obrigatória. |
| Doenças/condições e observação para o Funil | Sem novas perguntas; campos não coletados ficam NULL. | Registra relatos explícitos e pertinentes para a pessoa atendida, sem inferir diagnósticos. | Preserva dados confirmados; formatação do Funil é determinística e exibe "não informado" para NULL. |
| Primeiro follow-up | Mensagem pronta atual. | Pode personalizar somente o texto da retomada; aplica cotas e registra tokens no uso mensal do chat. | Usa a mensagem pronta se ainda elegível; não altera coleta nem navegação. |
| Segundo follow-up | Mensagem e encerramento atuais. | Sempre determinístico e encerramento obrigatório, sem chamada à IA. | Mesmo comportamento; não depende de modelo ou saldo de tokens. |
| Nome informado nesta conversa é corrigido | Comportamento atual. | Corrige o dado contestado; sem substituto, pergunta o nome e depois retoma a pendência. | Continua a correção estruturada, sem recorrer a nome de conversa encerrada. |
| Pergunta aberta junto da resposta da etapa | Tratamentos atuais. | Responde à dúvida e avança se a coleta foi resolvida; caso contrário, repete a pergunta. | Usa tratamentos/textos disponíveis, sem prometer compreensão equivalente à IA. |
| Botões de escolha | Apresentação atual. | Pode mostrar/omitir opções do catálogo conforme o texto. | Usa opções/texto compatíveis com a pergunta persistida; replay recupera resposta e botões já aprovados. |
| Aviso após seis repetições | Não recebe esse novo tratamento. | Na próxima dúvida sem avanço, orienta uma mensagem por vez, uma única vez por conversa. | Preserva a marca e não duplica aviso; não depende de reconhecer nova dúvida para inventar esse tratamento. |
| Próxima interação após limite 12 | Mantém o bloqueio por suspeita implementado hoje. | Encaminhamento comercial e bloqueio local por 30 dias, sem novo bloqueio Meta por esse motivo. | Aplica a mesma política do regime híbrido mesmo sem modelo. |
| Encaminhamento comercial por idade | Regra atual, sem novo bloqueio de 30 dias. | Encerra sem bloqueio adicional; nova entrada abre outra conversa, com nova consulta FireAds se aplicável. | Não reabre atendimento encerrado; respeita a decisão de abertura da nova conversa. |
| Tempo de IA | Não faz chamada. | Até 90 segundos totais; depois, fallback seguro. | Usa a margem operacional e posse válidas; não há garantia de ciclo completo em 20 segundos. |
| Indicador de digitação | Sem novo comportamento. | Solicitado enquanto a IA gera; parar renovações ao terminar ou falhar. | Não iniciar nem renovar por causa do fallback; indicador anterior pode durar até envio/expiração. |
| Cota esgotada, IA desativada ou API indisponível | Não depende de IA. | Seleciona fallback; não bloqueia o cliente por falta de tokens. | Preserva etapa, dados, correções, aviso e contador, sem nova chamada. |
| Com link: 17 → 20 | Entrega o link, sem passar por 18/19. | Pode compor a entrega do link; depois do envio registrado, encerra participação do modelo. | Entrega canônica com o mesmo corte; não refaz coleta nem reativa IA. |
| Sem link: 17 → 18 | Pergunta um único turno, como hoje. | Continua com IA na escolha, podendo esclarecer dúvidas e corrigir dados antes do repasse. | Continua a coleta válida de turno e as pendências confirmadas, sem modelo. |
| Sem link: 18 → 19 | Salva o turno e entrega o contato comercial. | Pode compor a entrega, preservando o botão/texto pronto; depois do envio registrado, encerra participação do modelo. | Mesmo efeito e corte; preserva turno e recupera resposta registrada sem duplicar envio. |
| Interações nas etapas 19/20 e satisfação 21–24 | Fluxo atual de cada rota. | Não chama mais IA, mesmo com cota e assinatura disponíveis. | Continuidade determinística normal; não depende de falha da API. |

A antiga previsão de aplicar o novo bloqueio local também ao Básico foi substituída
pela orientação mais recente: **o puro permanece como hoje**. Distinguir regime
da conversa de modo de resposta por turno, conforme o plano unificado; apenas
verificar se a API respondeu não basta para escolher a política de bloqueio.

Regras de idade, elegibilidade, e-mail opcional do titular 60+, turno único e
segurança do processamento continuam válidas. Falta de cota não cria bloqueio de
30 dias. Um ciclo admitido pode superar a cota; o próximo consulta o contador.
O atraso do agregado Plus e a subcontagem após falha continuam riscos aceitos.

O código já tem saudação de retorno por inatividade **na mesma conversa**. Isso
continua válido; não é reconhecimento a partir de uma conversa encerrada.

### 1.1. Continuidade das duas rotas

O corte é a **entrega do link ou do contato comercial**, não a confirmação de
uma visita e nem o encerramento da conversa. A última resposta de entrega pode
ser composta pela IA, se ela estiver disponível; as próximas não usam o modelo.
Aplicar o corte ao sucesso registrado e à recuperação do envio, sem chamar IA
de novo para uma resposta já persistida.

- **Com link:** 17 → 20; na 20, confirmação válida de reserva leva à pergunta da
  21. Dúvidas e respostas sem confirmação recebem os tratamentos determinísticos.
- **Sem link:** 17 → 18 → 19; na 18, somente `manha`, `tarde` ou `noite`, nunca
  duas escolhas. Preservar textos e respostas `interactive`/`interactive_button`.
  Na 19, a próxima resposta textual aceita apresenta a pergunta da 21; mesmo um
  texto "5" não é registrado como nota antes dessa pergunta. Mídia repete a orientação.
- **Satisfação:** 21 → 22 → 23 → 24 ou 22 → 24 se não quiser comentar, sempre
  sem IA. A etapa 24 mantém a finalização e o bloqueio atuais.

Turno é preferência e já é salvo em `conversa.turno` na transação 18 → 19.
Preservar a mensagem pronta e o botão comercial, sem prometer reserva confirmada.
Funil: 20–24 com link ou 19/21–24 sem link, com demais guardas e configuração
vigente; incluir turno nas observações quando houver. Follow-up proativo:
1–17 nas duas rotas e 18 somente sem link; não iniciar em 19/20/21–24.
Somente o primeiro pode usar IA para adaptar a retomada; o segundo mantém mensagem
e encerramento determinísticos. Revalidar elegibilidade antes do envio, inclusive
se uma nova mensagem chegar enquanto o primeiro lembrete estiver sendo gerado.

Ativar IA numa conversa já na 19/20/21–24 não libera o modelo. Renovação de cota,
upgrade, correções ou mudança de link não reabrem sua participação após o repasse.
Adicionar link não desvia conversa que já começou 18/19; remover link não cria
conversão automática de 20 para 18. Preservar as regras operacionais atuais.
O detalhamento e as referências estão na
[seção 1.1 do plano unificado](plano_ia_hibrida_atendimento.md#rotas-e-corte-ia).

## 2. Início de cada nova conversa

1. Aplicar as regras existentes de conversa ativa, encerramento e bloqueio.
2. Havendo conversa ativa, continuar nela. Silêncio, retorno de follow-up e retry
   não são motivos para perguntar tudo outra vez.
3. Ao criar nova conversa integrada à FireAds, consultar os formulários e
   persistir a decisão dessa abertura. Com importação completa, iniciar pela
   profissão; nos demais casos, começar pelo nome. Não reconhecer o cliente a
   partir de cadastro, resumo ou mensagens de atendimentos encerrados.
4. Se a mensagem da própria conversa nova já informar nome, destino ou outros
   dados, a IA pode aproveitá-los após validar. A origem é a mensagem nova.
5. Perguntar profissão, e-mail e demais dados quando pendentes. Não apresentar
   valores de conversas encerradas para confirmação nem sugerir dependente antigo.
6. Preservar chat, histórico, bloqueios e uso mensal. Recomeçar a coleta não
   significa criar outro cadastro duplicado nem renovar tokens.

Exemplo sem importação FireAds válida: cadastro antigo contém Ana, mas a mensagem nova é só "Olá". O bot
apresenta a assistente/unidade e pergunta "Como você se chama?".
Se a mensagem nova for "Olá, sou Ana e quero para meu filho", a IA pode usar os
dados informados e seguir à próxima pendência, sem reconhecimento histórico.

## 3. Dependente em uma nova conversa

Perguntar para quem é o atendimento, salvo destino antecipado nesta conversa
ou importado de formulário na abertura FireAds.
Não mencionar o dependente de atendimento encerrado, inclusive depois do segundo
follow-up. Coletar nome, idade e triagem novamente conforme o fluxo, aproveitando
somente antecipações da própria conversa nova.

O dependente da nova conversa recebe registro próprio. Não mover `id_dependente`
nem sobrescrever o registro antigo. Mesmo nome e idade podem se repetir sem
impedir a nova coleta. Dentro de uma conversa ativa, corrigir ou substituir o
dependente continua preservando seu ID e auditando os dados alterados.

## 4. E-mail e profissão coletados no atendimento atual

Coletar profissão e e-mail nas etapas correspondentes, salvo antecipação válida
na própria conversa ou e-mail importado na abertura FireAds. Profissão não vem
dessa importação. Não perguntar se a profissão ou o e-mail antigos continuam
corretos. `cliente.email` preenchido não conclui a coleta da conversa nova.

O e-mail continua sendo do titular, mesmo na rota de dependente. Ausência/recusa
segue a obrigatoriedade efetiva, incluindo a exceção do titular 60+.
`email_validado` indica coleta resolvida, não comprovação de posse da caixa postal.

Se o cliente corrigir dado que informou nesta conversa, aplicar arrependimento:
valor correto já informado permite atualizar; sem valor, abrir a coleta de
correção e depois retomar a pendência. Esclarecimentos ou confirmações necessários
usam apenas dados desta conversa, com campo e pergunta persistidos para fallback.
Um "sim" não vira e-mail sem uma pergunta de confirmação válida que o justifique.

**O contexto pode progredir sem mudança de etapa.** Corrigir um valor sem mudar
etapa não zera o contador; mudança real de etapa o zera segundo a regra vigente.

## 5. Correções de nome na conversa atual

Nome informado nesta conversa pode ser corrigido pelo cliente a qualquer momento
anterior ao corte da IA. Sem o substituto, pedir o nome correto na etapa de coleta
e depois retornar; com o substituto válido, atualizar sem deslocamento desnecessário.

Corrigir nome não implica outra pessoa nem invalida automaticamente idade/triagem.
Se houver troca explícita de pessoa na conversa ativa, revalidar os dados afetados
e preservar a auditoria. Não alterar os atendimentos encerrados nem renovar cotas.
Não existe saudação que reutilize nome antigo e dependa de o cliente contestá-lo.

### 5.1. Nome do dependente: corrigir o campo contestado

A regra mais recente elimina a pergunta automática na etapa 2 para distinguir
erro de nome de troca de pessoa. Se contestou apenas o nome, corrigir esse campo,
sem perguntar se idade e demais informações também mudaram.

- "O nome está errado", sem substituto: etapa 5 para pedir o nome correto;
  atualizar e retornar à coleta original. Preservar idade e triagem.
- "O correto é Pedro", na etapa da idade: corrigir sem retroceder e repetir a
  pergunta da idade, pois ela ainda não foi respondida.
- "É Pedro e ele tem 7 anos": corrigir nome, validar idade, aplicar as regras
  etárias e avançar quando permitido, com uma única resposta.
- "As informações estão certas, mas o nome é Camila": corrigir só o nome,
  mesmo que seja totalmente diferente; manter `respostas_desafios` válidas.
- Troca efetiva de pessoa: perguntar nome e idade novamente e refazer triagem,
  se elegível, preservando **o mesmo `id_dependente` na conversa ativa**.
- Correção de outros campos: atualizar os contestados e revalidar consequências,
  sem supor que o cliente quis outra pessoa só por corrigir vários dados.

Correção sem mudança real de etapa não zera o contador. Com ida à coleta do nome
e retorno, aplicar as transições reais, sem criar etapas extras. Se a mensagem
também resolveu a coleta original, retomar o primeiro dado ainda pendente.
Persistir campo, pessoa de referência, valor e retorno para o fallback; não
depender de uma nova análise para entender uma correção já estruturada.

A IA pode esclarecer texto duvidoso na coleta, mas não garante detectar todo
erro de nome nem deve completar "Pedr" para "Pedro" por suposição. O nome do
dependente contestado isoladamente não muda sua identidade. Nome do titular
informado nesta conversa também segue a correção pontual, como na seção 5.

### 5.2. Retorno após encerramento por idade

O encaminhamento por idade não aplica bloqueio de 30 dias. Se houver nova entrada
do cliente, criar outra conversa no mesmo chat; não reabrir a encerrada por uma
exceção de arrependimento. Preservar o motivo e os dados históricos anteriores.
Uma reentrega/retry da mensagem antiga não conta como nova entrada de atendimento.

Com IA, começar coletando o nome novamente, salvo antecipação na própria entrada
nova. No Básico, manter a etapa 1 atual. Nos dois regimes e no fallback, uma
importação FireAds válida desta nova conversa permite começar na profissão.
Colher a idade e reaplicar elegibilidade;
triagem e coleta concluídas na conversa anterior não encerram as coletas da nova.
Não presumir mentira nem prometer que iniciar de novo verifica a idade real.

Novo dependente pertence à nova conversa e recebe seu próprio registro; o ID é
preservado apenas nas correções dentro de uma conversa ativa. O chat e o uso
mensal continuam iguais, sem renovação de cota. Outros bloqueios e flood ainda valem.
Isso também vale para o mesmo dependente: nome/idade iguais não impedem um novo
registro e não justificam alterar o atendimento anterior.

### 5.3. Refazer a triagem e corrigir outros dados

Na conversa híbrida ativa, antes da entrega de link ou contato comercial, o
cliente pode pedir para refazer a triagem do titular ou dependente escolhido.
Reabrir suas perguntas nas
etapas existentes e atualizar cada resposta na mesma linha, preservando
`id_resposta_desafio`. Inserir apenas perguntas ainda sem registro nessa conversa.
Auditar os valores anteriores, sem duplicar linhas ou apagar o histórico.

Refazer a triagem não significa trocar de pessoa: preservar nome, idade, parentesco
e outros dados não contestados. Persistir quais perguntas precisam de nova resposta;
retry/fallback continuam essa revisão e não tratam respostas antigas como completas.
Depois, retomar a primeira coleta ainda pendente. Se apenas uma resposta foi
corrigida e o novo valor é válido e identificável, atualizar somente ela.

Nome e idade do titular ou dependente, profissão e e-mail do titular seguem a
mesma regra de arrependimento. Dado novo válido na mensagem permite corrigir na
etapa atual; sem ele, perguntar na coleta existente e retornar. Revalidar impactos
da idade sobre elegibilidade, triagem e e-mail. Não repetir dados independentes.
Conversa encerrada continua encerrada; após a entrega do link (20) ou do contato
comercial (19), a IA não é reativada para correções. O determinístico puro mantém
o comportamento atual.

### 5.4. Parentesco e apresentação no Funil

A IA não pergunta o parentesco. Preenche `dependente.parentesco` somente quando o
cliente revelar claramente a relação com o titular; caso contrário, mantém `NULL`.
Não inferir por nome, gênero ou idade. Correção apenas do nome preserva o parentesco;
troca efetiva de pessoa não transfere a relação anterior sem informação do cliente.

No Funil de atendimento de dependente, usar exatamente o conteúdo salvo:
`Parentesco: {valor}`. Se nulo, mostrar **`Parentesco: não informado`**. Não salvar
"não informado" como valor no banco, nem pedir nova interpretação à IA para gerar
essa linha. Atendimento do titular não exibe esse campo.

Acrescentar também `Doenças ou condições especiais:` e `Observação do atendimento:`
para a pessoa atendida, titular ou dependente. Cada campo aplicável nulo aparece
como `não informado`, sem ocultar a linha. O flow propõe e valida o registro de
relatos espontâneos; o Funil só formata os dados salvos, sem chamada à IA.
Não inferir doenças pela triagem nem atribuir condições da mãe ao filho. Correções
preservam proveniência; na troca de pessoa, invalidar os fatos da anterior e
reavaliar a observação. Correção somente do nome preserva informações independentes.

### 5.5. Primeiro follow-up com IA e consumo compartilhado

O primeiro follow-up pode aproveitar contexto da conversa ativa para convidar à
retomada, mantendo o padrão se não houver motivo para adaptar. Sua IA propõe apenas
texto: não altera cadastro, etapa, triagem, contagem de turnos ou navegação. O
segundo follow-up não consulta o modelo e encerra pelo fluxo determinístico atual.

Compartilhar personalidade e integração, com instruções/permissões por tarefa.
A orientação dos três TXT é regras comuns + atendimento + primeiro follow-up,
sem duplicar as 24 etapas. A divisão detalhada está na
[seção 21 do plano](plano_ia_hibrida_atendimento.md#funil-followup-ia).

O serviço de uso chamado pelos dois workers obtém/cria o uso mensal da unidade e
do chat, verifica plano/flag/cotas e registra tokens uma vez por requisição. Vale
o mês de admissão no fuso da unidade, não o mês de abertura da conversa. A soma
da unidade a cada cinco minutos inclui ambas as origens. Uso conhecido conta
mesmo se o texto padrão for escolhido ou o lembrete gerado não for enviado.
Segundo follow-up e montagem do Funil não fazem chamada nem consomem tokens.

## 6. Fallback e continuidade do atendimento híbrido

O determinístico puro permanece com sua coleta habitual, incluindo a importação
FireAds quando aplicada. O fallback de uma
conversa que já passou pela IA precisa, porém, entender a pergunta pendente que
o sistema realmente enviou.

Exemplo: durante a coleta da idade, o cliente contesta o e-mail informado nesta
conversa sem fornecer outro. A IA abre a correção e pede o endereço. Se a cota
acabar antes da resposta, o fallback valida o e-mail, salva e retoma a idade
pendente; não interpreta o endereço como se o bot ainda estivesse perguntando idade.

Guardar campo, pergunta e ponto de continuação no estado compartilhado, acessível
ao controlador, e não apenas em um resumo para a IA. Confirmação objetiva da
conversa atual deve continuar sendo entendida sem uma nova chamada ao modelo.

Uma conversa iniciada inteiramente em fallback começa pela coleta normal,
ou pela profissão quando a abertura FireAds importou os três dados válidos.
Ao voltar a dispor de IA, retomar do estado atual; não reiniciar a conversa,
importar dados de atendimento encerrado, repetir saudação nem zerar contador e aviso.

O mesmo vale para antecipações confirmadas, correção de e-mail com ponto de
retorno, substituição de dependente e coleta invalidada: a fonte é o estado
estruturado validado, não uma nova interpretação imaginada pelo fallback. Se
a chamada atual falhar antes de validar/persistir sua proposta, não promover
rascunhos parciais a fatos; responder com a entrada original e o estado confirmado.

No downgrade para Básico ou desligamento da IA durante uma conversa híbrida,
cessam novas admissões de IA; o atendimento em curso conserva a continuidade
determinística desse regime. Próximas conversas do Básico seguem puras. No
upgrade, entrada controlada no híbrido preserva a etapa e a pergunta atual.
Não remover bloqueios antigos nem zerar cotas com essas mudanças.

As rotinas de continuidade são compartilhadas com as operações de domínio; não
exigem copiar todos os senders/resolvers nem ativar as novas regras no Básico.
A resposta escolhida, seu modo e motivo ficam rastreáveis na decisão do turno.

## 7. Casos de verificação do piloto

- Com link, 17 → 20 entrega plataforma e encerra IA; sem link, 17 → 18 mantém IA
  até a entrega comercial em 18 → 19. Verificar as rotas para titular e dependente.
- Escolha única de turno aceita texto e botões; ambiguidade/duas escolhas não avançam.
- Turno e CTA comercial são preservados no fallback e no retry, sem gravação/envio duplicados.
- Próxima mensagem na 19 apresenta a pergunta da 21, sem contar como nota; na 20,
  exige confirmação válida de reserva. Satisfação inteira continua sem IA.
- Ativação, upgrade, renovação de cota e mudança de link não reativam IA após o repasse.
- Funil respeita as faixas por rota e apresenta turno; follow-up inclui a 18 somente sem link.
- Mesmo cliente em outra unidade não herda memórias particulares da primeira.
- Nova conversa pergunta nome mesmo com cadastro antigo; não usa saudação de reconhecimento.
- Nome/destino antecipados na própria mensagem nova podem ser aproveitados pela IA.
- Dependente antigo não é oferecido como opção, inclusive após segundo follow-up.
- E-mail/profissão são coletados novamente; nenhum valor antigo é sugerido para confirmação.
- Correções da conversa atual mantêm coleta e contador coerentes com a navegação.
- Cota acaba durante correção de e-mail: fallback entende a pendência e retoma a idade.
- Conversa ativa retomada preserva contexto; nova conversa começa com contexto próprio.
- Nova conversa não herda `email_validado`, triagem ou aviso como já concluídos.

- Básico mantém mensagens, etapas, botões, validadores e política de suspeita atuais.
- Híbrido mantém encaminhamento/bloqueio local mesmo quando o modelo falha ou acaba a cota.
- Correção de e-mail e troca de dependente continuam corretamente no fallback.
- Downgrade em conversa híbrida preserva pendências; nova conversa do Básico usa fluxo puro.
- Deadline total de 90 segundos inclui continuações/retries; resultado tardio não gera segundo envio.
- Digitação para de ser renovada no fim da geração, antes do envio, e não aparece no puro.
- Nome diferente informado no novo atendimento não altera dados históricos de conversas encerradas.
- Nome contestado sem substituto pergunta na etapa 5 e retorna, sem questionário sobre outros dados.
- Nome correto já informado é atualizado na etapa atual; resposta válida da etapa na mesma mensagem permite avanço.
- Troca de nome completo com demais dados corretos preserva idade e `respostas_desafios`.
- Troca efetiva refaz perfil/triagem mantendo o mesmo ID dentro da conversa ativa.
- Retorno após encerramento etário abre nova conversa, preserva histórico/chat/cota e reaplica idade.
- Retry da entrada que encerrou por idade não abre outro atendimento.
- Nova conversa aceita dependente com nome/idade iguais sem alterar o registro anterior.
- Parentesco espontâneo é salvo sem pergunta própria e reproduzido no Funil; NULL
  aparece como "Parentesco: não informado" somente para dependente.
- Refazer triagem preserva IDs existentes e cadastro da pessoa; mantém pendências
  no retry/fallback e não duplica respostas nem reutiliza as antigas como revisadas.
- Correção isolada de resposta não repete toda a triagem; idade corrigida reaplica regras.
- Funil mantém os três rótulos aprovados (parentesco só para dependente), com
  "não informado" para nulos; nenhuma geração por IA durante o envio do lead.
- Apenas primeiro follow-up pode personalizar texto; segundo sempre determinístico.
- Primeiro follow-up respeita cotas do mês/fuso atual e incrementa o mesmo uso de
  chat sem dupla contagem; nova mensagem exige revalidação antes do envio.
