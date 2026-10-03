# Ideia futura: solicitação de humano e atendimento pelo painel

Registro: **30/09/2026**. Status: **pedido documentado para evolução futura;
sem alterações no painel, banco, workers ou envio de mensagens nesta etapa**.

Plano principal: [IA híbrida](../plano_ia_hibrida_atendimento.md).

## 1. Objetivo

Criar `tratamento_humano` para reconhecer pedidos de atendimento por uma pessoa
real em qualquer etapa, tanto em unidades determinísticas quanto em unidades
com IA. O franqueado também poderá pausar o bot e responder pelo painel.

A pausa solicitada pelo cliente e a pausa manual do franqueado usam **o mesmo
controle de pausa**. Não são bloqueio do cliente nem encerramento por idade.
Não aplicar o bloqueio de 30 dias por alguém preferir atendimento humano.

## 2. Fluxos solicitados

### Unidade com chatbot determinístico

1. Detectar o pedido de humano em qualquer etapa, antes da resposta comum do fluxo.
2. Registrar a solicitação e informar que um humano entrará em contato.
3. Oferecer o botão com o número comercial para o cliente agilizar o contato.
4. Pausar o atendimento automático e destacar o pedido no painel.

Texto desejado, a revisar com a operação: "Vou chamar nossa equipe para continuar
seu atendimento. Se preferir adiantar, toque no botão abaixo para falar com a unidade."
Uma promessa de contato exige fila visível e alguém responsável por atendê-la;
apenas fornecer o botão não envia automaticamente uma mensagem à equipe.

### Unidade com IA

1. Reconhecer o pedido e perguntar uma vez, com educação: "Posso tentar tirar sua
   dúvida por aqui. Você prefere continuar comigo ou falar com nossa equipe?"
2. Se o cliente confirmar humano, registrar a solicitação, avisar sobre o contato,
   fornecer o botão comercial e pausar o bot.
3. Se preferir continuar com o bot, retornar à coleta pendente, preservando contexto.
4. Não repetir a tentativa de convencimento depois da confirmação. Persistir
   essa pendência para sobreviver a reinício, sem criar uma etapa inventada pela IA.

O usuário pediu essa diferença entre os modos. O limite de intervenção da IA na
passagem 17 → 18 continua vigente. Proposta para conciliá-los: depois desse corte,
o tratamento global usa a confirmação pronta equivalente na unidade com IA, sem
chamar o modelo novamente. Validar essa redação ao implementar a funcionalidade.

Insistência já explícita, resposta ambígua à confirmação, desistência do pedido
e solicitação com bloqueio ativo precisam de cenários definidos antes do piloto.
Não conceder à IA autorização para remover bloqueios por conta própria.

## 3. Controle compartilhado de pausa

Nome conceitual sugerido: `chatbot_pausado`. O local definitivo da coluna será
decidido ao revisar o schema. Seu alcance precisa ser **cliente + unidade/chat**:
uma conversa nova não pode fazer o bot voltar sozinho enquanto o atendimento
humano desse contato estiver ativo; outra unidade não deve ser pausada por isso.

Além da pausa, registrar motivo, autor, momento, conversa de origem e situação
do pedido humano. Isso diferencia "franqueado pausou por iniciativa própria" de
"cliente está aguardando alguém", embora ambos parem o bot pelo mesmo controle.

Proposta de situações do pedido: aguardando, assumido e concluído/cancelado.
Não transformar esses valores em novas etapas do fluxo. Não definir o estado de
uma solicitação apenas por abrir a conversa ou enviar uma mensagem isolada.

Ao pausar:

- Worker_flow interrompe novas respostas automáticas e chamadas de IA.
- Follow-up e demais rotinas de envio automático ao chat respeitam a pausa.
- Verificar também trabalho já em fila ou em geração, com versão/posse do lock
  conferida antes do envio. Não basta checar a coluna no início do ciclo.
- A própria mensagem de encaminhamento precisa de autorização específica e
  recuperável, para que a pausa não a impeça nem permita vários envios.
- Se uma chamada à Meta já saiu, uma pausa posterior não consegue desfazê-la;
  representar essa fronteira no teste de concorrência, sem prometer cancelamento.

O agendamento, Funil e rotinas administrativas precisam de revisão de impacto:
pausar mensagens não equivale a apagar um agendamento ou remover um lead válido.

## 4. Entrada de mensagens durante atendimento humano

Enquanto pausado, novas mensagens do cliente precisam continuar no histórico
exibido ao franqueado, sem alimentar a geração de respostas do bot.

O controle atual de turno espera resposta automática antes de aceitar novas
entradas em certos casos. O modo humano terá de separar **registrar mensagem
para leitura** de **enfileirar resposta automática**, para não ocultar mensagens
do cliente ao atendente. Preservar assinatura, isolamento de unidade,
deduplicação e proteção contra flood. Isso não libera lotes para o chatbot.

Retomada deve ser explícita e considerar a etapa/dados atuais. Não reproduzir
automaticamente todas as mensagens que chegaram durante a pausa nem reexecutar
efeitos já concluídos. Definir quem pode retomar e quando a pendência é encerrada.

## 5. Atendimento na seção Conversas

Funcionalidades solicitadas para o franqueado:

- Selecionar a conversa e usar um botão para pausar o chatbot.
- Ver claramente que o atendimento está pausado e quem assumiu a conversa.
- Digitar em um campo de texto e clicar em enviar.
- O backend chama o sender PyWa com o número da unidade e o contato selecionado.
- Ter uma ação explícita de retomada, com comportamento a definir.

O painel atual é de monitoramento. Essa evolução cria ações de escrita e envio:
autorização por unidade, proteção da requisição, auditoria do operador, tratamento
de falhas e deduplicação contra clique duplo fazem parte do projeto futuro.
Credenciais permanecem no backend. Registrar separadamente autor humano e bot.

Definir apresentação de enviado, falhou e pendente com base no retorno realmente
disponível; não exibir entregue/lido apenas porque a API aceitou o envio.

As restrições vigentes de envio da Meta continuam aplicáveis ao atendente. A pausa
não abre janela de resposta nem garante gratuidade. Retomar esta análise junto de
[janelas e statuses](../../docs/janelas_gratuitas_por_status/README.md) antes de liberar
envios fora da janela permitida; não criar templates ou contador neste documento.

## 6. Alertas e filtro Comercial

Pedido registrado: enquanto existir cliente aguardando atendimento humano,
mostrar **um pop-up a cada 10 segundos**, com botão que abre a conversa; deixar
o botão do filtro Comercial vermelho e a conversa em destaque.

Desenho proposto para preservar organização:

- Atualizar/reapresentar um aviso agregado no intervalo solicitado, sem empilhar
  janelas duplicadas a cada ciclo. A frequência e a interação final serão testadas.
- Listar a quantidade de pedidos pendentes e oferecer acesso às conversas certas.
- Consultar o estado no banco; não tratar o fechamento visual do pop-up como
  confirmação de atendimento.
- Definir quando assumir/concluir um pedido tira o destaque e interrompe avisos.
- Distinguir solicitação humana pendente dos encaminhamentos por idade que já
  aparecem no filtro Comercial. Pausa manual, sozinha, não prova pedido pendente.
- Garantir visibilidade mesmo com mudança de conversa ativa, paginação, período
  selecionado ou duas pessoas operando o painel ao mesmo tempo.
- Usar texto/ícone além da cor, mantendo leitura em celular e desktop.

O intervalo é o comportamento pretendido do painel aberto; navegador suspenso
ou fechado não garante notificação exata a cada 10 segundos. Caso seja necessário
alertar fora dele, será preciso outro canal, ainda não solicitado para execução.

## 7. Botão comercial e texto preenchido

Preservar o mecanismo já existente de link comercial com mensagem preenchida.
O cliente decide enviá-la ao abrir o WhatsApp; não é uma mensagem disparada
automaticamente ao comercial pelo chatbot.

O fluxo atual da etapa 6 inclui titular, participante e idade. Um pedido humano
pode surgir antes desses dados. Criar um texto aprovado específico, por exemplo
"Olá, vim do atendimento com o chatbot da unidade e gostaria de falar com a equipe."
Incluir nomes somente se já confirmados.

Manter o texto padronizado inicialmente. Um resumo adicional da IA é opcional
para outra revisão, com limites e fatos confirmados; não deixar o modelo alterar
destinatário, inventar urgência, diagnóstico, promessa ou condição comercial.

## 8. Dependências e verificações para implementação futura

Definir responsáveis pelo atendimento e retomada, horário operacional, texto de
expectativa de contato, permissões do painel e ciclo de vida das solicitações.
Confirmar localização da pausa compartilhada e compatibilidade com nova conversa.

Testar os dois modos antes/depois do agendamento, confirmação e recusa, pedido
antes de informar nome, contato comercial indisponível, pausa durante envio,
reinício, follow-up pendente, mensagens recebidas durante pausa, envio humano
duplicado/falho, dois operadores, retomada e isolamento entre unidades.

Essa evolução será detalhada depois. Não alterar agora a promessa de atendimento,
o caráter de leitura do painel, a coleta de statuses ou as regras de bloqueio.
