# Atendimento determinístico e atendimento com IA

Revisão: **02/10/2026**. Status: **comportamentos aprovados no plano;
nenhuma alteração de código ou banco nesta etapa**.

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
atuais do projeto. A nova estrutura universal de chat não autoriza mudar suas
mensagens, validadores, ordem de etapas ou política de suspeita/bloqueio.

**Híbrido com IA:** interpretar perguntas abertas, antecipações e correções; usar
operações validadas e etapas existentes. Pode escolher mensagens prontas quando
elas já atendem à entrada.

**Híbrido em fallback:** nenhuma nova chamada de IA. O controlador determinístico
continua a partir do estado confirmado do híbrido. Precisa de pequenas rotinas de
continuidade; não pode simplesmente reiniciar o fluxo ou interpretar toda entrada
pelos validadores legados sem considerar qual pergunta foi enviada.

| Situação | Determinístico puro / Básico | Híbrido com IA | Fallback do híbrido |
| --- | --- | --- | --- |
| Novo atendimento de cliente conhecido | Começa na etapa 1, como hoje. | Pode aproveitar nome confirmado na mesma unidade e perguntar destino na etapa 2. | Sem IA desde a abertura, mantém coleta comum; se a abertura personalizada já aconteceu, continua dali. |
| Destino ou outros dados antecipados | Validadores/transições atuais. | Registra dados claros e pula perguntas/coletas já resolvidas, inclusive confirmação de destino inequívoco. | Preserva antecipações já confirmadas e pergunta só a pendência; não inventa novas interpretações livres. |
| Dependente após conversa encerrada no segundo follow-up | Fluxo atual sem nova personalização histórica. | Pode citar dependente anterior como opção a confirmar. | Entende a escolha quando a pergunta e opções já estão estruturadas; em ambiguidade, esclarece. |
| Confirmação de e-mail/profissão anterior | Pergunta habitual. | Pode confirmar, aceitar correção ou pedir dado novo na mesma etapa. | Entende sim/não vinculados ao campo/valor pendente; não manda sim ao validador de endereço. |
| Correção de dado sem substituto | Tratamentos existentes. | Abre correção e guarda o ponto de continuação. | Resolve pendência estruturada e retoma a próxima coleta necessária. |
| Troca de dependente já confirmada | Comportamento atual. | Mesmo ID; pergunta nome e idade novamente e refaz triagem, sem herdar o perfil anterior. | Mantém invalidações e coleta pendente; nunca recupera perfil antigo para facilitar fallback. |
| Correção do nome com o nome correto já informado | Comportamento atual. | Corrige na etapa atual, preserva idade/triagem e avança somente se a coleta atual também foi resolvida. | Preserva o que já foi validado; não exige nova geração nem repete efeitos. |
| Nome do dependente contestado, sem nome correto | Comportamento atual. | Pergunta o nome na etapa 5 e retorna; não pergunta automaticamente se outros dados mudaram. | Lê campo e retorno persistidos e conclui a correção, preservando dados independentes. |
| Pedido para refazer a triagem | Comportamento atual. | Reabre as perguntas, atualiza respostas preservando os IDs existentes e mantém cadastro da mesma pessoa. | Continua a revisão persistida; não usa respostas antigas para pular perguntas pendentes. |
| Parentesco do dependente | Não acrescenta pergunta à coleta atual. | Preenche somente se o cliente revelar a relação; sem pergunta própria, mantém NULL se não informado. | Preserva o valor validado; não inventa relação nem cria coleta obrigatória. |
| Cliente de retorno nega o nome usado na saudação | Comportamento atual. | Pergunta o nome correto e suspende uso da memória antiga enquanto esclarece a identidade. | Continua a coleta pendente sem insistir no nome antigo ou expor outros dados históricos. |
| Pergunta aberta junto da resposta da etapa | Tratamentos atuais. | Responde à dúvida e avança se a coleta foi resolvida; caso contrário, repete a pergunta. | Usa tratamentos/textos disponíveis, sem prometer compreensão equivalente à IA. |
| Botões de escolha | Apresentação atual. | Pode mostrar/omitir opções do catálogo conforme o texto. | Usa opções/texto compatíveis com a pergunta persistida; replay recupera resposta e botões já aprovados. |
| Aviso após seis repetições | Não recebe esse novo tratamento. | Na próxima dúvida sem avanço, orienta uma mensagem por vez, uma única vez por conversa. | Preserva a marca e não duplica aviso; não depende de reconhecer nova dúvida para inventar esse tratamento. |
| Próxima interação após limite 12 | Mantém o bloqueio por suspeita implementado hoje. | Encaminhamento comercial e bloqueio local por 30 dias, sem novo bloqueio Meta por esse motivo. | Aplica a mesma política do regime híbrido mesmo sem modelo. |
| Encaminhamento comercial por idade | Regra atual, sem novo bloqueio de 30 dias. | Encerra sem bloqueio adicional; retorno abre nova conversa, podendo aproveitar nome confiável. | Não reabre atendimento encerrado; nova conversa segue a abertura disponível sem IA. |
| Tempo de IA | Não faz chamada. | Até 90 segundos totais; depois, fallback seguro. | Usa a margem operacional e posse válidas; não há garantia de ciclo completo em 20 segundos. |
| Indicador de digitação | Sem novo comportamento. | Solicitado enquanto a IA gera; parar renovações ao terminar ou falhar. | Não iniciar nem renovar por causa do fallback; indicador anterior pode durar até envio/expiração. |
| Cota esgotada, IA desativada ou API indisponível | Não depende de IA. | Seleciona fallback; não bloqueia o cliente por falta de tokens. | Preserva etapa, dados, correções, aviso e contador, sem nova chamada. |
| Depois de 17 → 18 | Fluxo atual. | Encerra participação do modelo; segue determinístico. | Mesmo corte, sem reativar IA ou refazer coleta concluída. |

A antiga previsão de aplicar o novo bloqueio local também ao Básico foi substituída
pela orientação mais recente: **o puro permanece como hoje**. Distinguir regime
da conversa de modo de resposta por turno, conforme o plano unificado; apenas
verificar se a API respondeu não basta para escolher a política de bloqueio.

Regras de idade, elegibilidade, e-mail opcional do titular 60+, turno único e
segurança do processamento continuam válidas. Falta de cota não cria bloqueio de
30 dias. Um ciclo admitido pode superar a cota; o próximo consulta o contador.
O atraso do agregado Plus e a subcontagem após falha continuam riscos aceitos.

O código já tem saudação de retorno por inatividade **na mesma conversa**. Isso
é diferente da memória entre atendimentos encerrados descrita neste plano.

## 2. Retorno com IA em uma nova conversa

1. Aplicar primeiro as regras existentes de conversa ativa, encerramento e bloqueio.
   Memória não autoriza reabrir uma conversa encerrada ou contornar bloqueio.
2. Se for criada uma nova conversa, procurar evidências de atendimento do mesmo
   cliente **com a mesma unidade**, e da mesma identidade reconhecida nesse contato.
3. Recuperar somente os fatos necessários, com origem e data. Um `cliente.nome`
   global preenchido não comprova atendimento anterior naquela unidade.
4. Havendo nome utilizável e nenhum indício de troca de pessoa, iniciar com
   boas-vindas e a pergunta de destino da etapa 2. Não exigir informar o nome outra vez.
5. Se a própria mensagem já trouxe nome corrigido ou destino claro, aproveitar
   esses dados conforme as regras de correção/antecipação; não impor a etapa 2.
6. Registrar o que foi reaproveitado, de qual conversa veio e o que ainda precisa
   de confirmação. Nenhum campo antigo vira coleta nova por simples cópia.

Exemplo sem destino antecipado: "Olá, Ana! Que bom ter você de volta. 😊
O atendimento de hoje é para você ou para um dependente?"

Sem nome confiável naquele vínculo, seguir a coleta do nome na etapa 1. Nome
vindo de outra unidade ou apenas do perfil do WhatsApp não é prova suficiente.

## 3. Dependente citado no atendimento anterior

Condição específica solicitada: o atendimento anterior era de um dependente e
foi encerrado por `followup_sem_resposta`, após o segundo follow-up. Usar o caso
mais recente pertinente; não procurar arbitrariamente um dependente antigo quando
o contexto mais recente indicar outra pessoa.

Exemplo: "Olá, Ana! Seja bem-vinda de volta. O atendimento de hoje é para você,
para o Pedro ou para outra pessoa?"

A opção de outra pessoa evita tratar o dependente antigo como único destino.
Essa pergunta cumpre a finalidade da etapa 2; não cria etapa nova. Se houver
ambiguidade de identidade, primeiro esclarecer, sem apresentar dados de familiares.

O nome anterior é uma referência a confirmar, não um participante já escolhido.
Após a escolha, criar/preencher o dependente **da nova conversa**, preservando
o registro da conversa antiga. Não mover o `id_dependente` entre conversas.
Atualizar o mesmo ID continua correto apenas para substituição dentro de uma
única conversa, como já definido no plano.

Não transportar automaticamente idade antiga, triagem, elegibilidade ou dispensa
de e-mail. Perguntar a idade atual quando necessária e aplicar as regras vigentes.
As respostas antigas podem ajudar a contextualizar uma dúvida, mas não substituem
a triagem prevista para o atendimento atual.

## 4. Confirmar e-mail e profissão sem inventar etapas

Confirmar no momento da coleta correspondente, sem exigir tudo na saudação.
Escolher dados do histórico daquele chat com origem conhecida, sem inferir que
o cadastro global foi confirmado pela unidade.

| Momento | Resposta do cliente | Ação |
| --- | --- | --- |
| Etapa 10: confirmação de e-mail conhecido | "Sim" | Registrar confirmação nova, valor e mensagem de origem; avançar conforme as regras. |
| Etapa 10: confirmação de e-mail conhecido | "Não" | Invalidar a sugestão para esta coleta, pedir o e-mail atual e permanecer na etapa 10. |
| Etapa 10: confirmação de e-mail conhecido | "Não, agora é ana@exemplo.com" | Validar o novo endereço, salvar a coleta e avançar. |
| Etapa 4: confirmação de profissão | "Sim, continuo professora" | Confirmar profissão desta conversa e avançar. |
| Etapa 4: confirmação de profissão | "Não" | Pedir a profissão atual e permanecer na etapa 4. |
| Qualquer confirmação | Resposta ambígua | Esclarecer sem presumir confirmação. |

Exemplo: "Você continua trabalhando como professora?". Para e-mail, usar a
confirmação contextual somente quando não houver dúvida sobre quem está sendo
atendido. Como medida de exposição mínima, recomenda-se apresentar o endereço
parcialmente oculto, ou pedir que o cliente o informe se houver dúvida de identidade.
O formato final dessa apresentação deve ser validado antes de publicar o piloto.

No estado persistente da conversa, distinguir `confirmando_dado_anterior` de
`solicitando_dado_atual`, indicando campo, valor sugerido e origem. Um "sim" só
confirma o valor ao qual a última pergunta efetivamente se referia. Depois de
uma recusa, não insistir no valor antigo nem reinterpretar outro "sim" como e-mail.

Ao rejeitar o e-mail, `email_validado` continua falso; confirmação ou endereço
válido resolve a coleta. Ausência/recusa segue a obrigatoriedade efetiva, incluindo
a exceção já aprovada. Confirmação da profissão é registrada em
`conversa.profissao` com origem auditável, sem validar outros dados por consequência.

**O contexto pode progredir sem mudança de etapa.** Passar de confirmação para
pedido de dado novo não zera o contador: permanência incrementa segundo a regra
vigente. Somente a mudança efetiva de etapa o zera.

## 5. Nome incorreto e mudança de titular do número

Se o cliente disser que o nome usado na saudação não é o dele, reconhecer a
correção e perguntar: "Desculpe pela confusão. Como você se chama?". Retomar a
coleta de nome pela etapa 1. Não insistir na informação histórica nem continuar
confirmando e-mail/profissão/familiares enquanto a identidade estiver incerta.
Guardar essa pendência para o fallback também reconhecer o nome informado.

Corrigir a grafia/nome da mesma pessoa e detectar uma pessoa diferente são eventos
distintos. Se estiver ambíguo, esclarecer com uma pergunta simples; não assumir
troca de identidade a cada correção de nome.

Quando o cliente informar que é outra pessoa, deixar de reutilizar dados da
anterior, inclusive dependente, e-mail, profissão, idade e resumos. Preservar os
atendimentos antigos para consulta autorizada e iniciar a coleta da pessoa atual.
Não reescrever registros históricos como se pertencessem ao novo titular.

Um número conhecido não garante o mesmo titular. Correção posterior não desfaz
informações que já tenham sido reveladas; por isso, a regra precisa impedir
uso de dados anteriores quando houver sinal de mudança e limitar a exposição
na confirmação. Não prometer reconhecimento de identidade infalível.

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
dependente contestado isoladamente não muda sua identidade. Já negar o nome do
titular na saudação de retorno mantém os cuidados da seção 5 sobre portador do número.

### 5.2. Retorno após encerramento por idade

O encaminhamento por idade não aplica bloqueio de 30 dias. Se houver nova entrada
do cliente, criar outra conversa no mesmo chat; não reabrir a encerrada por uma
exceção de arrependimento. Preservar o motivo e os dados históricos anteriores.
Uma reentrega/retry da mensagem antiga não conta como nova entrada de atendimento.

Com IA, aproveitar o nome confiável do titular e perguntar o destino do novo
atendimento, respeitando antecipações explícitas e possíveis mudanças de portador.
No Básico, manter a etapa 1 atual. Colher/confirmar a idade e reaplicar elegibilidade;
triagem e coleta concluídas na conversa anterior não encerram as coletas da nova.
Não presumir mentira nem prometer que iniciar de novo verifica a idade real.

Novo dependente pertence à nova conversa e recebe seu próprio registro; o ID é
preservado apenas nas correções dentro de uma conversa ativa. O chat e o uso
mensal continuam iguais, sem renovação de cota. Outros bloqueios e flood ainda valem.
Isso também vale para o mesmo dependente: nome/idade iguais não impedem um novo
registro e não justificam alterar o atendimento anterior.

### 5.3. Refazer a triagem e corrigir outros dados

Na conversa híbrida ativa, antes do corte 17 → 18, o cliente pode pedir para
refazer a triagem do titular ou dependente escolhido. Reabrir suas perguntas nas
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
Conversa encerrada continua encerrada; após o link de agendamento, a IA não é
reativada para correções. O determinístico puro mantém o comportamento atual.

### 5.4. Parentesco e apresentação no Funil

A IA não pergunta o parentesco. Preenche `dependente.parentesco` somente quando o
cliente revelar claramente a relação com o titular; caso contrário, mantém `NULL`.
Não inferir por nome, gênero ou idade. Correção apenas do nome preserva o parentesco;
troca efetiva de pessoa não transfere a relação anterior sem informação do cliente.

No Funil de atendimento de dependente, usar exatamente o conteúdo salvo:
`Parentesco: {valor}`. Se nulo, mostrar **`Parentesco: não informado`**. Não salvar
"não informado" como valor no banco, nem pedir nova interpretação à IA para gerar
essa linha. Atendimento do titular não exibe esse campo.

## 6. Fallback e continuidade do atendimento híbrido

O determinístico puro permanece com sua coleta habitual. O fallback de uma
conversa que já passou pela IA precisa, porém, entender a pergunta pendente que
o sistema realmente enviou.

Exemplo: a IA perguntou se o e-mail anterior está correto e, antes do "sim", a
cota de IA acabou. Um controlador determinístico de confirmação deve interpretar
esse "sim" a partir do estado persistido, validar a coleta e seguir o fluxo.
Não encaminhar cegamente "sim" ao validador que espera um endereço completo.

Para "não", perguntar o novo dado na mesma etapa. Para ambiguidade, esclarecer
com texto determinístico. Tudo isso funciona sem nova chamada ao modelo. Guardar
essa pendência em estado de domínio compartilhado, acessível ao controlador;
não escondê-la apenas em um resumo destinado ao modelo.

Uma conversa iniciada inteiramente em fallback não usa personalização histórica
que dependa da IA. Ao voltar a dispor de IA, retomar do estado atual; não reiniciar
a conversa, repetir boas-vindas nem zerar contador e aviso.

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

- Mesmo cliente em outra unidade não herda memórias particulares da primeira.
- Determinístico puro inicia nova conversa na etapa 1; IA pode iniciar na 2.
- Mensagem de retorno já informando destino não recebe a mesma pergunta outra vez.
- Dependente antigo é oferecido como opção, sem alterar seu registro histórico.
- E-mail/profissão confirmados, negados ou corrigidos mantêm a coleta consistente.
- Recusa de sugestão mantém etapa e contador, sem confundir contexto com transição.
- Cota acaba entre pergunta de confirmação e resposta: fallback entende a pendência.
- Troca explícita de titular impede recuperação da memória da pessoa anterior.
- Nova conversa não herda `email_validado`, triagem ou aviso como já concluídos.

- Básico mantém mensagens, etapas, botões, validadores e política de suspeita atuais.
- Híbrido mantém encaminhamento/bloqueio local mesmo quando o modelo falha ou acaba a cota.
- Correção de e-mail e troca de dependente continuam corretamente no fallback.
- Downgrade em conversa híbrida preserva pendências; nova conversa do Básico usa fluxo puro.
- Deadline total de 90 segundos inclui continuações/retries; resultado tardio não gera segundo envio.
- Digitação para de ser renovada no fim da geração, antes do envio, e não aparece no puro.
- Nome negado no retorno leva à nova coleta e suspende uso de memória de identidade incerta.
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
