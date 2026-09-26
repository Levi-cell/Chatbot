# Plano: filtro Comercial e regras de encerramento por idade

**Registrado em:** 24/09/2026

**Revisado conforme a decisão do usuário após conversar com Milena:** 25/09/2026

**Status:** planejamento, sem implementação nesta tarefa.

Este conteúdo substitui integralmente a proposta anterior. O arquivo mantém o nome
`proposta_funil_encaminhamento_comercial.md` para preservar sua localização e referências,
mas o objetivo deixou de ser enviar esses atendimentos ao funil.

## Decisão vigente e escopo

Manter o atendimento humano desses casos pelo painel, com o filtro **Comercial**
no lugar de **Continuações**. O filtro reunirá os encerramentos especiais por idade
da última conversa de cada cliente/unidade, incluindo casos que não receberam o
número comercial. Seu nome representa a fila de análise do franqueado no painel,
não uma confirmação de que houve encaminhamento pelo botão.

Somente idosos continuam recebendo o contato comercial, com mensagem pronta no
botão, encerramento e sem bloqueio de 30 dias. Titulares menores de 18 anos e
dependentes abaixo do limite da unidade continuam recebendo a explicação do motivo
e tendo a conversa encerrada, sem contato comercial e sem bloqueio de 30 dias.

As mudanças de atendimento desta proposta são: retirar 90+ das opções configuráveis
do suporte e baixar a exceção universal de 100 anos ou mais para **90 anos ou mais**.

Ficam cancelados os pontos da proposta anterior:

- Envio ao funil desses encerramentos, tanto novos quanto antigos.
- Bloqueio de 30 dias por qualquer um desses encerramentos.
- Botão comercial e mensagem pronta de contato para os casos de menores.
- Observações especiais, atualização de oportunidades e classificação retroativa
  para criar envios no CRM.
- Regra que fazia do filtro Comercial um subconjunto do filtro Funil.
- Mudanças na fila do funil e em suas quatro verificações de elegibilidade.

O funil mantém a regra normal existente: triagem respondida até a etapa 17 e entrada
na etapa 18, com elegibilidade nas etapas 18 a 22. Uma conversa especial encerrada
na etapa 6 não ganha elegibilidade por aparecer no filtro Comercial. Bloqueios já
existentes de outros encerramentos permanecem sob suas regras atuais.

## Matriz de atendimento e tags

| Situação da última conversa | Encerramento e contato | Tag no painel |
| --- | --- | --- |
| Titular menor de 18 anos | Explicar a necessidade de um adulto responsável e encerrar, sem botão comercial | **Menor** |
| Dependente abaixo da idade mínima da unidade | Informar o limite aplicado e encerrar, sem botão comercial | **Limite mínimo** |
| Titular com idade a partir do suporte configurado, até 89 anos | Enviar o contato comercial com mensagem pronta e encerrar | **50+**, **60+**, **70+** ou **80+**, conforme o limite configurado naquele atendimento |
| Titular ou dependente com 90 anos ou mais | Aplicar a exceção universal, enviar o contato comercial com mensagem pronta e encerrar | **90+** |

Nenhum desses quatro casos gera envio ao funil ou bloqueio de 30 dias.

Para dependentes, o mínimo continua sendo:

- **BPA ativo: 4 anos.** Abaixo de 4 recebe a tag Limite mínimo.
- **BPA desativado: 5 anos.** Abaixo de 5 recebe a tag Limite mínimo.
- Exatamente 4 anos com BPA ou 5 anos sem BPA pode seguir normalmente; não é caso
  de encerramento por limite mínimo.

O suporte configurado continua exclusivo para titulares. Um dependente de 70 anos,
por exemplo, não é encaminhado apenas porque a unidade configurou suporte em 60+.
A exceção universal é que alcança ambas as rotas, agora desde 90 anos inclusive.

## Suporte configurável e exceção universal

Opções permitidas para `idade_minima_suporte`: **50, 60, 70, 80**, além do estado
desativado já existente (`NULL`). Remover 90 do seletor, da validação de domínio,
das mensagens de ajuda, do modelo/admin e da restrição do banco.

Avaliar a regra universal antes do suporte configurado:

1. Idade maior ou igual a 90: universal, em qualquer unidade, titular ou dependente.
2. Titular de idade inferior a 90 e igual ou superior ao suporte habilitado:
   suporte configurado da unidade.
3. Titular menor de 18: encerramento por menoridade.
4. Dependente abaixo do mínimo aplicável: encerramento por limite mínimo.
5. Demais idades válidas: continuar o fluxo normal.

O suporte desativado não desativa a exceção universal. Uma pessoa com 90 anos em
unidade com suporte 50+ pertence à regra universal e recebe a tag 90+, não duas tags.

Usar **90+** por ser curto e consistente com as outras tags. Nos detalhes,
explicar “Regra universal de idade avançada — titular ou dependente com 90 anos
ou mais”. Não inferir o gênero do cliente/dependente para redigir a explicação.

A mensagem atual de idades avançadas e seu botão com texto pronto continuam sendo
a base da rota universal. Atualizar referências a “100+”, “acima de 99” e o intervalo
do suporte configurado para refletir a nova regra, distinguindo conteúdo histórico
e novos envios.

### Unidades que hoje estejam configuradas em 90+

Na futura migração, levantar essas unidades e converter a configuração específica
90 para `NULL`: elas passam a depender da regra universal 90+, que vale para todas
as unidades. Não converter para 80, pois isso ampliaria indevidamente o suporte para
titulares de 80 a 89 anos.

Essa conversão não apaga a explicação de atendimentos antigos que aconteceram sob
a configuração 90+. Preservar a origem histórica na classificação do painel.

Coordenar a alteração da restrição e a normalização desses valores com o código
que passa a aceitar apenas 50/60/70/80. Atualizar/inutilizar os caches de configuração
pelos mecanismos existentes. Verificar que o número comercial válido continua
disponível para a exceção universal, inclusive nas unidades com suporte desativado.

Nenhuma consulta ou alteração no banco de produção é executada nesta tarefa.

## Filtro Comercial: última conversa por cliente e unidade

Substituir o botão **Continuações** por **Comercial**, mantendo posição e estilo.
Preservar Todas, Follow-up, Funil, Avaliadas, busca por contato e seleção de período.

Um chat continua sendo a união das conversas do mesmo cliente com a mesma unidade.
Não criar um cartão por conversa nem misturar unidades ao procurar a mais recente.

Para incluir o chat em Comercial:

1. Identificar a última conversa real daquele par cliente/unidade, considerando
   também conversas posteriores fora do período selecionado.
2. Essa última conversa precisa estar encerrada por um dos quatro casos da matriz,
   com a resposta correspondente registrada conforme o fluxo atual.
3. O chat e a conversa qualificadora precisam pertencer ao recorte de período usado
   pela listagem. Não acrescentar a exigência de envio ao CRM nem usar sua data.
4. Selecionar uma única tag de motivo dessa última conversa, sem agregar motivos
   de outras conversas.

Assim que uma nova conversa for criada para esse cliente/unidade:

- Retirar o chat do filtro Comercial e remover a tag especial.
- Mantê-lo em Todas e nos demais filtros em que satisfizer as respectivas regras.
- Não transferir automaticamente para Funil, Follow-up ou Avaliadas.
- Preservar todo o histórico e os separadores de início/continuação do atendimento.
- Se a nova conversa também terminar em um desses casos, recolocar o chat no filtro
  com a tag e os dados desse novo encerramento.

Não basta uma nova mensagem na mesma conversa ou um evento de entrega: o que
invalida o marcador anterior é a criação de outra conversa. Uma conversa nova em
outra unidade não remove a tag desta unidade. Eventos atrasados/retries da conversa
anterior também não podem recolocá-la como “última”.

### Período e histórico

Manter a seleção de período da seção Conversas. Para formar a lista, usar as mesmas
regras de participação de conversas no período já utilizadas pelo painel. Para
decidir se existe uma conversa posterior, consultar o histórico completo daquele
cliente/unidade, antes de limitar pelo período. Isso impede que um filtro de datas
antigas ressuscite a tag de um atendimento substituído.

Atendimentos históricos podem aparecer no filtro se forem o último daquele chat
e houver evidência suficiente do motivo. Essa exibição não envia mensagens, não
encaminha ao CRM e não reabre/encerra conversas.

## Apresentação das tags

Usar a área ilustrada pelo usuário, onde aparecem os selos Funil e Avaliada, para
mostrar **somente a tag especial de motivo** enquanto a última conversa qualificar
o chat para Comercial. Aplicar a mesma prioridade visual em Todas e nos detalhes
do chat para evitar informações diferentes sobre o estado especial atual.

Preservar os indicadores históricos reais de envio ao funil e avaliação usados
pelos outros filtros. A prioridade visual da tag especial não apaga sucessos antigos.
Um chat pode ter uma conversa antiga enviada ao funil e, atualmente, outra conversa
encerrada por idade; o encerramento atual não cria outro envio ao funil.

Ao criar uma nova conversa, remover a tag especial e voltar à apresentação normal
dos selos, conforme os dados e período. Não alterar os marcadores de perfil
(titular/dependente/faixa etária) sem necessidade dessa implementação.

As tags indicam o motivo, não a idade exata:

- **Limite mínimo:** dependente abaixo do mínimo; nos detalhes, mostrar o mínimo
  aplicado (4 ou 5) e a idade informada quando disponível.
- **Menor:** titular com menos de 18; não confundir com um dependente menor de idade
  que pode seguir normalmente.
- **50+/60+/70+/80+:** limite de suporte selecionado naquele atendimento, não um
  arredondamento da idade do cliente.
- **90+:** regra universal para novos encaminhamentos. Em histórico anterior que
  tenha usado suporte configurado 90+, explicar essa origem real nos detalhes.

Manter cores, tamanho, contraste e espaçamento compatíveis com os selos atuais.
A descrição do filtro/detalhes deve deixar claro que casos de menores não receberam
o número comercial; não presumir esse envio pela presença do chat no filtro.

## Dados e fidelidade ao atendimento original

A classificação deve vir do encerramento e da resposta correspondente à conversa,
não da idade atual do cadastro global, da configuração atual da unidade ou de
palavras pesquisadas apenas no navegador.

No código atual, `idade_invalida` reúne menores e a antiga exceção universal. Esse
motivo genérico sozinho não distingue as tags. O plano precisa de uma classificação
persistente ou derivada de histórico comprovado para:

- Titular menor de 18.
- Dependente abaixo do mínimo, com o limite de 4/5 efetivamente aplicado.
- Suporte de titular pelo limite configurado naquele atendimento.
- Exceção universal, com idade e regra vigentes no encaminhamento.

Preservar nome/idade da pessoa atendida e motivo/limite necessários aos detalhes,
a partir do contexto da conversa. Não depender exclusivamente do cadastro atual do
dependente: hoje o fluxo exclui o dependente abaixo do mínimo no encerramento.
Garantir que a classificação e os dados explicativos sobrevivam a essa exclusão,
por meio do histórico ou do registro do encerramento; não recuperar dados de outro
dependente só para preencher a tela.

A implementação deve definir a representação mínima dessa classificação e os
campos adicionais estritamente necessários, se o histórico não fornecer uma fonte
estável. Não criar o motivo genérico `encaminhado_comercial` da proposta cancelada
para todos esses casos: os menores não receberam esse encaminhamento.

Para novos encerramentos, conservar o motivo específico, a idade informada, a rota,
o limite aplicado e a configuração relevante do momento. Alterações posteriores
de BPA ou suporte só afetam novas decisões; não mudam a tag de uma conversa encerrada.

Para históricos, recuperar apenas fatos comprovados. Não classificar um titular
de 95 anos que seguiu normalmente antes do deploy como se tivesse recebido a nova
exceção universal. Quando faltar evidência para distinguir uma categoria, registrar
a pendência de classificação para revisão, sem inventar idade/limite ou motivo.

Não reescrever mensagens históricas nem enviar contatos retroativamente. Preservar
respostas antigas na recuperação: não trocar a decisão de uma mensagem já enviada
pela nova política. Revisar consumidores posteriores da idade (como a etapa 10)
para não rejeitar um atendimento antigo de 90 a 99 anos que já avançou legitimamente
antes da mudança. A regra nova rege a decisão de encaminhamento na etapa 6.

## Nome exibido no painel

Preservar o comportamento atual, confirmado no código:

- A consulta lê `cliente.nome` e a consolidação usa esse valor como nome do chat.
- O cadastro do cliente é global; a atualização do nome é refletida no painel
  quando seus dados são recarregados, inclusive nas unidades relacionadas.
- Uma nova conversa na etapa 1 pode exibir o nome antigo até que o cliente informe
  outro, sem copiar esse nome para a coleta do novo atendimento.
- Sem nome cadastrado, manter “Cliente sem nome”.
- Histórico de mensagens mantém os textos originais, mesmo que o nome do cadastro
  mude posteriormente.

A continuidade visual do nome no painel não autoriza o bot a pular a coleta do nome
ou usar o nome antigo nas mensagens da nova conversa.

## Pontos de implementação futura

- `core/validacoes/suporte_por_idade.py`, modelo/admin e DDL: remover 90 das opções
  configuráveis e ajustar textos de ajuda e restrição do banco.
- Validador/resolver da etapa 6: universal em 90+, precedência sobre suporte,
  suporte configurado apenas para titular e manutenção dos limites BPA de 4/5.
- Mensagens, senders e recuperação: ajustar nomes/referências ao limiar universal,
  preservar mensagens prontas dos botões de idosos e não criar botões para menores.
- Persistência/recuperação do encerramento: manter ausência de bloqueio, conservar
  classificação e dados do momento para o painel sem alterar commits do worker.
- Repositório e consolidação do monitoramento: obter o motivo da última conversa
  real e o limite original; não fazer OR das tags sobre todo o histórico do chat.
- Template/JavaScript/CSS do painel: trocar Continuações por Comercial e renderizar
  a tag específica sem perder agrupamento, período ou atualização de dados.
- Relatórios que consomem os motivos: preservar seus significados; a categoria
  Comercial do painel não transforma menores em suporte ao idoso.
- Documentação e testes: alinhar com a decisão atual e remover expectativas da
  proposta anterior de envio ao funil ou bloqueio comercial.

Manter a confirmação da Meta e as fronteiras transacionais existentes, inclusive
recuperação de resposta registrada e encerramento pendente. O cache continua sendo
auxiliar dos bloqueios existentes; esta proposta não cria um novo bloqueio.

## Verificação antes da implementação/deploy

- Titular com 17/18 anos; dependente com 3/4 anos com BPA e 4/5 sem BPA.
- Titular com 89/90/99/100 anos e dependente com 89/90/100, com suporte ativo/inativo.
- Cada limite configurável 50/60/70/80 e universal prioritária desde 90.
- Unidade previamente configurada com suporte 90 normalizada sem virar suporte 80.
- Nenhum encerramento especial ganha envio ao CRM, tentativa na fila do funil,
  bloqueio de 30 dias ou follow-up depois de encerrado.
- Botões de idosos mantêm texto pronto contextual; menores recebem somente a
  explicação de encerramento, sem botão comercial.
- Comercial não depende de `lead_no_funil` nem de `funil_envios.status = 'sent'`.
- Uma tag especial por chat, baseada na última conversa do par cliente/unidade.
- Nova conversa remove tag e presença em Comercial, mesmo fora do período em tela.
- Nova conversa em outra unidade e eventos tardios não alteram essa decisão.
- Novo encerramento especial reaplica a tag com o novo motivo; atualizações de
  configuração não mudam o motivo de encerramentos anteriores.
- Históricos qualificáveis aparecem apenas quando comprovados e ainda últimos,
  sem reclassificar pela idade atual ou pelo novo limite universal.
- Casos com dependente excluído continuam tendo classificação histórica coerente.
- Nome global antigo permanece visível na etapa 1 e é atualizado após nova coleta,
  sem reaproveitamento pelo bot.
- Funil/Avaliadas/Follow-up e os bloqueios normais continuam com suas regras.
- Conversas antigas já avançadas de 90 a 99 anos e recuperações de mensagens
  anteriores ao deploy não ficam presas por uma substituição indiscriminada de 100 por 90.
- Migração, domínio, admin, cache de configuração e documentação ficam alinhados.

Testar com integrações simuladas e banco local descartável. Nesta tarefa,
alterar somente este plano; não implementar, migrar, enviar mensagens ou fazer deploy.
