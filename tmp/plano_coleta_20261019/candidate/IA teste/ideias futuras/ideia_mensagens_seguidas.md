# Ideia futura: várias mensagens na mesma interação

Registro: **30/09/2026**. Status: **fora do piloto inicial; manter a regra atual
de um turno por vez até a IA estar validada**.

O agrupamento continua futuro. A orientação após seis turnos sem avanço,
descrita abaixo, foi incluída no plano do piloto da IA; ainda não implementada.

Plano principal: [IA híbrida](../plano_ia_hibrida_atendimento.md).

## 1. Objetivo

Nas unidades com IA, permitir compreender informações divididas em mensagens
próximas, como "Meu nome é Ana", "É para meu filho" e "Ele tem 8 anos". Evitar
uma chamada paga e uma resposta do bot para cada fragmento.

Unidades sem IA permanecem no comportamento determinístico. A abertura para
fragmentos não remove proteção contra flood, limites de contexto ou validações.

## 2. Situação atual e paliativo

O ingresso na fila passa por `avaliar_turno_cliente_para_fila`, chamado em
`callback/webhook/services/populating_fila_mensagens.py`. Uma mensagem pode ser
ignorada por já existir um turno aguardando resposta. A IA não recebe
automaticamente o conteúdo de uma entrada que não foi aceita nesse caminho.

Não usar a IA para adivinhar que o cliente enviou mais mensagens. Não apresentar
um aviso de limitação a todos os clientes durante a saudação.

Paliativo escolhido pelo usuário, detalhado na seção 9 do plano principal:

- Usar o mesmo contador de turnos sem avanço que tem limite 12.
- Depois de seis turnos sem avanço concluídos, se a próxima entrada for uma
  dúvida que também não permitir avançar, responder à dúvida e explicar a regra.
- Orientação sugerida: "Eu acompanho uma mensagem sua por vez. Para continuarmos,
  reúna as informações em uma mensagem e aguarde minha resposta."
- Se a entrada permitir avançar, não apresentar esse aviso. Se não for dúvida,
  a condição pode ocorrer numa próxima entrada, antes do limite de 12 prevalecer.
- Decisão aprovada: uma orientação por conversa, com o horário do envio salvo
  em `conversa.aviso_turno_unico_enviado_em`. Mudar de etapa zera o contador,
  mas não apaga esse registro; novas repetições não geram outro aviso na mesma
  conversa. Uma nova conversa começa sem aviso registrado.
- Avisar não zera o contador e retry não repete a orientação. A decisão do turno
  e o registro do envio seguem a recuperação descrita nas
  [mudanças de banco](../plano_ia_hibrida_atendimento.md#banco-ia).
- O tratamento é exclusivo das etapas assistidas por IA. Não ultrapassa seu
  corte no agendamento nem habilita várias entradas no webhook.
- O aviso explica uma regra real, mas não afirma que o cliente enviou mensagens
  seguidas. Se ele disser "já mandei", pedir o dado indisponível sem fingir que o viu.

Não é necessário criar um detector de mensagens descartadas para esse aviso.
Se tal sinal for incluído futuramente, distinguir fragmentos novos de reentrega,
flood e mensagem fora de ordem. Este documento não altera o webhook agora.

## 3. Agrupamento proposto para uma evolução

1. Validar cada entrada, deduplicar por identificador e aplicar limites de abuso.
2. Agrupar mensagens próximas por cliente e unidade, respeitando a conversa ativa.
3. Fechar o grupo após uma espera curta ou ao atingir um limite de quantidade,
   tamanho ou tempo total. Novas entradas não podem prolongar a espera sem limite.
4. Persistir uma identidade estável do grupo e suas mensagens em ordem definida.
5. Interpretar uma única entrada composta, preservando autoria e origem de cada
   informação. Aplicar operações aprovadas e produzir uma resposta coerente.
6. Entradas que chegam depois do início do processamento formam outro grupo;
   não alterar silenciosamente o conteúdo sobre o qual a IA já está decidindo.

Não concatenar todo o histórico nem aceitar contexto ilimitado. Os valores da
janela e dos limites dependem de testes; não foram fixados nesta discussão.

## 4. Integração com os controles existentes

- Preservar FIFO, exclusão por conversa, `lock_version` e checagem antes do envio.
- Um grupo tem estado recuperável e composição imutável durante seu processamento.
- Distinguir fragmento aceito, deduplicado, rejeitado por limite e ainda pendente.
- Reinício não cria outro grupo com as mesmas entradas nem outra resposta para
  um grupo já concluído.
- Contabilizar progresso e limite sem avanço por interação processada, conforme
  regra a definir; não multiplicar punição pelo número de fragmentos.
- Incluir todos os IDs de origem nas operações, para auditoria e recuperação de
  correções ou decisões etárias.
- Antecipação continua permitida, mas vários fragmentos não significam que o bot
  fez perguntas que nunca enviou.
- Desativar IA com grupo pendente exige uma política de drenagem/fallback; não
  descartar dados já aceitos nem entregar ao fluxo antigo um estado incompatível.

## 5. Decisões e testes futuros

Definir janela, teto de mensagens/caracteres/tokens, prioridade de botões,
ordenação para eventos atrasados e resposta quando os limites forem atingidos.
Testar dois workers, queda durante fechamento do grupo, retry de envio, novas
entradas durante geração, fragmentos contraditórios e flood contínuo.

Aceitar áudios nos grupos depende também do
[plano de áudios](ideia_audios.md). Mensagens recebidas durante atendimento humano
precisam ser preservadas para o atendente, mas não devem reativar o bot; esse modo
é tratado em [atendimento humano](ideia_atendimento_humano.md).
