# Diagnóstico de profissão e consulta inicial FireAds — 08/11/2026

## Escopo e evidências

Investigação dos exemplos de Santo André enviados pelo responsável pelo projeto.
Banco consultado em transação somente leitura e FireAds consultada somente por GET.
Nenhuma mensagem enviada, linha da planilha editada ou conversa histórica corrigida.

## Pedido financeiro salvo como profissão

A conversa 341, iniciada em 02/11/2026, contém `Só queria saber valores.` como
profissão. A etapa 4 já verifica financeiro antes de aceitar profissão, mas seu
validador contextual não reconhecia esse pedido. O teste reproduziu avanço
indevido para a etapa 5 na rota dependente e para a 6 na rota titular.

Correção local: reconhecer pedidos de informação sobre valores/preços/custos,
incluindo singular/plural e formas sem interrogação. Preservar profissões que
apenas mencionam termos financeiros. A resposta usa o tratamento existente,
repete a pergunta da etapa 4 e não inclui profissão ou evento de transição no
resultado do envio. Não exige migração SQL. Ainda depende de deploy na VM.

Os testes de endereço também tiveram três expectativas alinhadas ao texto
`localizada na`, já alterado pelo commit anterior `a7c110e`. O texto de produção
do endereço não foi modificado nesta correção.

## Maria: ausência na consulta histórica, Meta Ads na leitura atual

- Conversa 353 iniciada em **07/11/2026 às 13:40:24**, horário de Brasília.
- Consulta inicial concluída às **13:40:31**, com `resultado=ausente`,
  `motivo=sem_registro_elegivel`, `referencia=null` e `fontes.geral=[]`.
- Atribuição gravada: orgânico. Todos os campos essenciais permaneceram ausentes;
  por isso a abertura pediu o nome na etapa 1.
- A URL e a aba atuais coincidem com as usadas nessa consulta.
- Em **08/11/2026 às 20:19**, a API retornou a linha **837**, canal **Meta Ads**,
  anúncio **FR001 [form-8.0]**, nome válido, e-mail válido e destinatário
  `pai_ou_mae`. O campo de período preferido estava vazio.
- A simulação sem escrita, usando a entrada original da consulta e a resposta
  atual, reconheceu o telefone com prefixo `p:+55`, importou os três campos e
  atribuiu Meta Ads. Apenas o turno permaneceu ausente.

Não houve timeout registrado nesse atendimento: houve uma decisão de ausência.
A origem não foi descartada por nome, e-mail ou destinatário incompatível.
A máscara do telefone da linha atual é aceita pelo código.

O snapshot histórico conserva apenas linhas correspondentes ao contato, não a
resposta inteira da API. Portanto, não comprova quando a linha ficou disponível
nem permite distinguir atraso de sincronização, cache externo ou alteração
posterior na planilha. A data exibida na linha (`07/11/2026 00:00`) não comprova
o horário em que ela passou a ser retornada pela API. Não atribuir uma causa
externa definitiva sem o histórico da FireAds.

## Por que a origem não foi revista automaticamente

O `worker_origem_fireads` seleciona somente conversas sem consulta inicial,
com motivo `canal_pendente_entrega`. Conversas com consulta inicial já concluída
não entram nessa seleção, inclusive quando ela retornou ausência. O worker do
Funil confirma novamente a origem quando o atendimento se torna elegível para
entrega; essa conversa permaneceu na etapa 1.

Uma evolução possível é permitir reconciliação posterior e limitada para
ausências iniciais. Isso exige definir prazo/tentativas e precedência sobre
outras atribuições, sem reenviar mensagens nem reiniciar a coleta já concluída.
Essa alteração de elegibilidade não foi aplicada nesta investigação.
