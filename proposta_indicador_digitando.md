# Proposta: indicador de digitação no atendimento

Data: 14/10/2026.

Status: implementado no projeto em 17/10/2026; publicação na VM e verificação
visual no WhatsApp ainda pendentes. A proposta abaixo registra os critérios e
a seção 14 descreve a implementação. Não há migração SQL.

## 1. Objetivo

Exibir o indicador “digitando…” do WhatsApp quando o `worker_flow` já tiver
confirmado que pode enviar uma nova resposta ao cliente. Isso vale tanto para a
abertura de uma conversa quanto para a continuação de uma conversa existente.

O gatilho é a autorização efetiva de uma resposta naquele turno. Retirar uma
mensagem pendente da fila, isoladamente, não autoriza a chamada: ainda existem
verificações de unidade, bloqueios, ordenação, contexto, concorrência e
idempotência que podem impedir ou adiar a resposta.

O indicador acompanha o preparo da resposta, incluindo a consulta inicial à
FireAds depois de autorizar o atendimento. Ele não altera quem pode receber
atendimento, qual etapa será executada ou qual mensagem será enviada.

## 2. Comportamento oferecido pela API

A biblioteca PyWa expõe a operação `WhatsApp.indicate_typing()` para solicitar o
indicador à WhatsApp Cloud API. A chamada identifica a mensagem recebida à qual o
bot vai responder e a conta da unidade responsável pelo atendimento.

A operação também marca a mensagem recebida como lida. Portanto, a proposta
inclui esse efeito visível para o cliente; não se trata apenas de uma animação
local do nosso sistema.

O indicador desaparece quando o bot responde ou após 25 segundos, o que ocorrer
primeiro. Não é necessário programar uma segunda função para interrompê-lo.
Se o processamento ou o envio da resposta falhar depois da ativação, a expiração
da API encerra o indicador.

O aceite da solicitação pela API não comprova que a animação foi vista pelo
cliente. Se a resposta sair rapidamente, os pontinhos podem aparecer por pouco
tempo. Não adicionar uma pausa artificial para prolongar sua exibição.

Referência: [documentação oficial do PyWa — indicate_typing](https://pywa.readthedocs.io/en/latest/content/client/client_reference.html#pywa.client.WhatsApp.indicate_typing).

## 3. Condições para ativar

A primeira sinalização da espera FireAds exige que o fluxo existente confirme:

1. A mensagem está reservada para processamento e pertence ao cliente e à
   unidade corretos.
2. Não há mensagem anterior que obrigue o worker a aguardar a ordenação do turno.
3. A unidade está habilitada, respeitando `status_pagamento`.
4. Os bloqueios aplicáveis permitem atendimento, incluindo o bloqueio de 30 dias
   e os controles de bloqueio do cliente já existentes.
5. A conversa foi criada ou recuperada conforme as regras atuais, e o worker
   possui sua reserva válida, com o `lock_version` correspondente.
6. O vínculo entre fila, cliente, unidade e conversa está consistente.

Para a sinalização imediatamente anterior à resposta, também são exigidos:

7. Uma eventual espera pela FireAds foi resolvida e o atendimento pode prosseguir.
8. O histórico e o contexto do turno foram reconstruídos, inclusive em retomadas.
9. Não existe uma resposta do bot já persistida para a mensagem atual que faça o
   fluxo apenas recuperar o resultado, sem novo envio.
10. Existe uma rota de resposta válida para aquele contexto, com os dados
    necessários ao envio, e as verificações finais de autorização continuam
    satisfeitas.

O worker de consulta usa sua reserva persistida e confere a entrada aguardando,
unidade ativa, integração válida, prazo e conversa ainda sem abertura aplicada
ou resposta salva. Essas condições não substituem as guardas do `worker_flow`,
que serão executadas novamente na retomada.

Uma resposta inválida do cliente pode legitimamente gerar uma orientação ou uma
repetição da pergunta. Nesse caso, existe uma resposta elegível e o indicador
pode ser ativado. Isso é diferente de um contexto interno inconsistente, uma
etapa sem rota implementada ou um bloqueio que impeça qualquer envio.

Restrições de idade, atendimento para titular ou dependente, customização da
unidade e demais decisões continuam nos seus validadores e resolvers. Quando uma
regra determina uma mensagem de orientação ou encerramento, essa mensagem também
pode ser acompanhada do indicador, desde que o envio seja autorizado.

## 4. Sequência conceitual de um atendimento

1. O `worker_flow` reserva a mensagem da fila.
2. Executa os controles de ordenação, unidade, cliente e conversa.
3. Obtém o lock e reconstrói o contexto persistido do atendimento.
4. Resolve a abertura FireAds, quando aplicável. Se ainda houver espera, reagenda
   a mensagem pelo mecanismo existente. Se acabou de criar a consulta, confirma
   o checkpoint e sinaliza a espera uma vez, antes de seguir para outro cliente.
   O worker de consulta faz outra sinalização antes da leitura externa (seção 7).
5. Reconstrói o histórico e aplica a barreira contra reenvio de resposta já salva.
6. Define a resposta elegível e passa pelas verificações finais de envio.
7. Solicita o indicador uma vez para essa tentativa de resposta.
8. Envia a mensagem normalmente, mesmo se apenas a solicitação do indicador falhar.
9. Persiste o resultado e finaliza a fila segundo os checkpoints existentes.

A proteção da conversa e a verificação de unidade devem continuar válidas antes
dos efeitos externos. Caso se detecte perda de lock ou desativação depois da
chamada opcional, a resposta continua sujeita às proteções do atendimento. A
ativação dos pontinhos nunca é uma autorização para ignorá-las.

O recurso não deve exigir manter uma transação ou um bloqueio de linha do banco
aberto enquanto aguarda a Meta. A propriedade da conexão, dos checkpoints, do
commit e do rollback continua com o orquestrador do ciclo.

## 5. Ponto de integração e responsabilidades

Na estrutura atual, `workers/worker_flow/response_flow/flow_worker.py` coordena
as guardas e a persistência. `flow_sender.py` possui uma barreira explícita de
idempotência antes do despacho das etapas; a retomada de follow-up também possui
um caminho de recuperação de resposta já persistida.

Para a ativação anterior à resposta, inserir uma chamada incondicional antes de
`flow_sender` não basta: um replay pode terminar sem enviar nada. O escopo de envio
respeita as barreiras dos dois caminhos. As duas sinalizações da espera FireAds
têm gatilhos próprios: criação confirmada da pendência e início da consulta reservada.

O ponto conceitual é depois das decisões que autorizam a resposta e antes do
transporte à Meta. Se algum resolver ainda puder concluir que não deve enviar,
a ativação anterior à resposta fica depois dessa decisão, sem duplicar regras
nem alterar a sequência dos resolvers.

Distribuição de responsabilidades proposta:

| Camada | Responsabilidade |
| --- | --- |
| `workers/worker_flow` | Sinalizar a criação confirmada da consulta; na resposta, coordenar uma tentativa do indicador antes do primeiro envio. |
| `workers/worker_consulta_dash` | Sinalizar uma vez antes de consultar a pendência reservada. Não enviar respostas nem mudar etapas. |
| `core/integrations/whatsapp/pywa_functions` | Encapsular a chamada PyWa, usar a conta correta, limitar a espera e tratar falhas específicas dessa operação opcional. |
| `core/integrations/whatsapp/pywa_functions/cliente.py` | Continuar fornecendo o cliente configurado da unidade, sem ativar o indicador automaticamente ao criar qualquer cliente. |
| `core/repositories` | Informar se a solicitação foi inserida e recuperar a mensagem aguardando da consulta reservada. Não executar HTTP. |
| `core/integrations/whatsapp/messages` | Continuar responsável pelos textos e componentes das respostas, sem conhecer o indicador. |

A função de integração recebe os identificadores necessários. Ela não busca
conversas, consulta Redis, altera etapas, controla retry da fila ou decide
bloqueios de negócio. Chamadas PyWa permanecem na camada de integração.

Não distribuir uma chamada independente por cada mensagem ou botão de uma mesma
resposta. Uma tentativa de resposta pode utilizar mais de uma operação de envio;
isso não deve ativar novamente os pontinhos a cada operação.

## 6. Identificação da mensagem e da unidade

O identificador necessário é o ID da mensagem recebida da Meta, no formato
`wamid...`. Não utilizar o ID numérico da fila, o ID da conversa, o telefone do
cliente ou o ID de uma resposta anterior do bot no lugar dele.

O projeto já transporta esse dado como `mensagem["id_hash"]` no contexto da fila
e como `id_hash_msg` no histórico da mensagem atual. A chamada deve usar o ID
correspondente à entrada que está sendo respondida nesse turno.

A conta deve corresponder ao `id_phone_unidade` daquela entrada. Nunca usar uma
unidade padrão para todos os atendimentos ou reaproveitar dados de outro ciclo.

No worker de consulta, os identificadores vêm da primeira entrada ainda pendente
ou em processamento vinculada à conversa, conferindo telefone e unidade. Os dados
já existem na fila; não são duplicados no JSON da consulta nem em novas colunas.

Se o ID necessário estiver ausente ou não for utilizável, omitir o indicador e
registrar o motivo técnico. Isso não cria, por si só, um impedimento novo para
uma resposta que o fluxo atual consiga enviar legitimamente.

## 7. Espera pela FireAds

Uma consulta à FireAds pode durar mais que os 25 segundos do indicador. A
proposta mantém a separação entre `worker_flow` e `worker_consulta_dash`:

1. O cliente A inicia uma conversa que exige consulta.
2. Após as guardas, o `worker_flow` cria a pendência, confirma vínculo e
   reagendamento no banco e solicita o primeiro indicador para A. Depois libera
   seu ciclo. Recuperar uma pendência já existente não solicita esse indicador.
3. O cliente B pode ser atendido normalmente. Quando B estiver elegível para
   resposta, o indicador é solicitado para a mensagem de B.
4. O `worker_consulta_dash` reserva a consulta de A, confirma a reserva e recupera
   a entrada elegível. Depois de encerrar a transação, solicita o segundo
   indicador, consulta a FireAds e salva o resultado completo.
5. Na retomada de A, o `worker_flow` reconstrói o contexto, verifica as guardas e
   a ausência de resposta anterior, decide a abertura e solicita o terceiro
   indicador imediatamente antes do primeiro envio efetivo.
6. A abertura personalizada ou o atendimento orgânico é enviado pelas regras
   atuais, sem exigir outra mensagem do cliente para destravar a espera.

Um resultado que leve ao fallback orgânico, incluindo timeout tratado pelas
regras atuais, também recebe a sinalização anterior à resposta, após as guardas.

São três tentativas no percurso normal completo, sem renovação periódica.
Rechecagens da pendência pelo flow não chamam a Meta. O worker de consulta
continua sem enviar mensagens de atendimento. As três chamadas não garantem
animação contínua em consultas longas; a API controla sua duração.

A retomada usa o reagendamento existente de 5 segundos, não um novo mecanismo
de notificação entre workers. As primeiras duas chamadas podem ocorrer próximas
entre si, pois a pendência fica visível após o commit. A ordem de aceite dessas
duas requisições pela Meta não é uma condição para consultar ou responder.

## 8. Falhas, tempo de espera e impacto no ciclo

O indicador é uma operação opcional. Seu sucesso não é condição para enviar a
resposta, avançar uma etapa ou concluir o processamento da mensagem.

Uma falha de conexão, timeout, recusa da Meta ou ausência de confirmação dessa
operação deve produzir diagnóstico técnico e permitir que o fluxo prossiga com
a resposta, caso as demais condições continuem válidas.

Não transformar a falha isolada do indicador em `ErroEnvioMeta` da resposta de
atendimento. Também não marcar a fila como enviada, reagendar a mensagem,
consumir uma tentativa adicional ou bloquear o cliente por causa dela. Falhas
reais do envio da resposta continuam com seu tratamento próprio.

A chamada será curta, síncrona e sem retry automático específico. Não haverá
thread auxiliar, novo worker, tarefa em segundo plano ou rotina de renovação dos
pontinhos. Há uma tentativa em cada um dos três pontos definidos para a abertura
FireAds; nos demais atendimentos, apenas a tentativa anterior à resposta.

O transporte precisa de timeouts curtos e explícitos, próprios dessa operação.
Como referência inicial, considerar limites da ordem de 1 a 2 segundos por fase
de rede, a confirmar na implementação e na validação da sessão HTTP utilizada.
Timeout por fase não equivale a um prazo total exato; avaliar também a duração
acumulada, os defaults do cliente e eventuais retries do transporte.

Essa requisição acrescenta latência ao ciclo e pode atrasar brevemente o próximo
cliente. O objetivo é limitar esse custo e não reproduzir a longa espera da
FireAds dentro do `worker_flow`. Não alterar globalmente o timeout das mensagens
de atendimento para configurar o indicador.

No worker de consulta, o tempo gasto para recuperar a entrada e sinalizar é
descontado do orçamento restante. A chamada não reinicia o prazo de 300 segundos.

Se a resposta demorar mais que 25 segundos depois da ativação, os pontinhos
expiram e o atendimento continua. Não reiniciar a consulta nem reenviar uma
mensagem por causa dessa expiração.

## 9. Concorrência, reinício e idempotência

O indicador aproveita a reserva e as verificações existentes da conversa. Não
precisa de uma tabela, lock independente, flag persistente ou chave Redis para
representar “digitando”. A API controla a duração desse estado visual.

| Situação | Comportamento esperado |
| --- | --- |
| Worker cai antes de ativar | A recuperação reconstrói o contexto e só ativa quando uma nova tentativa de resposta estiver autorizada. |
| Worker cai depois de ativar e antes da resposta | O indicador expira; o mecanismo atual recupera a mensagem e pode ativá-lo novamente antes da resposta. |
| Resposta do bot já está persistida | O replay recupera o resultado; não envia resposta nova nem solicita indicador. |
| Meta aceitou a resposta, mas o processo caiu antes de salvar | Permanece a janela conhecida de possível mensagem duplicada; a recuperação também pode solicitar o indicador novamente. |
| Timeout do indicador depois de possível aceite pela Meta | Seguir para a resposta sem repetir imediatamente a chamada opcional. |
| Lock recusado ou perdido antes da ativação | Não ativar; seguir o tratamento de concorrência existente. |
| Unidade desativada ou bloqueio detectado antes da ativação | Não ativar; aplicar o comportamento atual da regra correspondente. |

Não prometer execução exatamente uma vez para um efeito externo que não participa
da transação do banco. Pode existir uma mudança de estado depois da última
verificação local e antes do aceite da Meta. As guardas reduzem essa janela,
mas não tornam banco e API uma operação atômica.

A chamada não pode renovar, liberar ou assumir por conta própria o lock da
conversa. Uma recuperação legítima continua sob controle do worker e da versão
da reserva, sem reutilizar variáveis de outro cliente.

Se o flow cair após confirmar a pendência, mas antes do primeiro indicador, essa
sinalização pode ser omitida: a consulta já existe e não será marcada novamente
como nova. A consulta e a resposta continuam recuperáveis. Se o worker de consulta
cair, sua retomada pode sinalizar novamente antes de repetir a leitura. Por isso,
três é o percurso normal, não uma garantia de contagem sob quedas ou rejeições.

## 10. Cobertura dos cenários

| Cenário | Momento da ativação |
| --- | --- |
| Cliente novo, unidade sem FireAds | Depois das validações, antes da abertura normal. |
| Cliente retornando, nova conversa permitida | Depois de confirmar que pode abrir a conversa, antes da resposta. |
| Conversa ativa e continuação normal | Depois de reconstruir o contexto e autorizar a próxima resposta. |
| Resposta de orientação, repetição ou encerramento prevista na etapa | Depois da escolha da resposta válida, antes do envio. |
| Nova pendência FireAds | Ativar após confirmar a criação e o reagendamento. |
| Worker de consulta reservou a pendência | Ativar antes da consulta, com a entrada elegível e transação encerrada. |
| Rechecagem de pendência FireAds já existente | Não ativar. |
| Consulta FireAds resolvida | Depois de aplicar o resultado e autorizar a abertura correspondente. |
| Reação do cliente a um follow-up | Aplicar as mesmas guardas e evitar ativação duplicada quando a retomada delegar ao sender normal. |
| Mensagem posterior aguardando ordenação | Não ativar nesse ciclo. |
| Conversa bloqueada, unidade inativa ou contexto sem envio autorizado | Não ativar. |
| Retry apenas reconciliando resposta já salva | Não ativar. |
| Lembrete proativo do `worker_followup` | Fora desta proposta, que trata respostas a entradas processadas pelo `worker_flow`. |
| Operações dos workers de Funil ou Consumo Meta | Não ativar. |

## 11. Observabilidade

Registrar falhas e omissões relevantes do indicador com motivo técnico, tipo de
erro e IDs internos que permitam correlacionar fila e conversa. Identificadores
externos devem seguir o mascaramento já utilizado pelo projeto.

Não registrar tokens, payloads completos, telefone completo ou conteúdo da
mensagem para diagnosticar os pontinhos. Diferenciar falha do indicador de falha
do envio da resposta para não sugerir que o cliente ficou sem atendimento.

Sucessos podem ficar em nível de diagnóstico para evitar poluir o log de cada
ciclo. O retorno da API indica aceite da operação, não visualização comprovada.

## 12. Critérios de validação

Validar com testes focados, usando integração Meta simulada:

- Indicador ocorre depois das guardas e antes do envio nas aberturas e continuações.
- Conta da unidade e ID da mensagem recebida correspondem ao turno atual.
- Bloqueios, unidade inativa, perda de lock, espera por ordenação e contexto sem
  resposta impedem a chamada.
- Abertura FireAds percorre as três ativações; rechecagens da pendência não repetem.
- O worker de consulta usa a entrada correta e não segura transação durante HTTP.
- Reserva vencida, unidade inativa, entrada já finalizada ou resposta persistida
  impedem a sinalização do worker de consulta.
- Replay com resposta persistida não chama indicador nem envia resposta novamente.
- Retorno de follow-up não duplica a ativação ao delegar ao fluxo normal.
- Falha ou timeout isolado do indicador mantém a resposta e sua persistência,
  sem alterar retry, etapa, status de fila ou política de bloqueio.
- Ausência de ID utilizável omite apenas a operação opcional.
- Uma tentativa de resposta com múltiplos componentes não chama o indicador
  repetidamente por componente.
- Configuração de timeout é isolada e não modifica outros clientes ou envios.
- O custo do indicador não reinicia o prazo de consulta da FireAds.

Depois da implementação, um teste manual controlado pode confirmar a percepção
visual e a marcação de leitura. Os testes automatizados devem confirmar a ordem
das chamadas e os efeitos locais; não precisam esperar 25 segundos para simular
uma animação controlada pela Meta.

## 13. Limites desta proposta

Não é necessária migração SQL, criação de view, tabela, coluna, chave Redis,
serviço systemd ou alteração da lógica FireAds para esse recurso. Também não há
mudança de mensagens, etapas, códigos de origem, critérios do Funil ou regras de
atendimento.

A implementação local não significa que o indicador esteja publicado na VM ou
que sua exibição tenha sido verificada no WhatsApp do cliente.

## 14. Implementação em 17/10/2026

- `flow_worker.py` mantém suas guardas de unidade e lock e o commit anterior ao
  envio. Em seguida abre o escopo `antes_do_primeiro_envio`, compartilhado pelo
  sender normal e pelo retorno de follow-up.
- Abrir o escopo não faz requisição. O cliente da integração executa a ação
  somente quando o resolver chega a `send_message` ou `request_contact_info`,
  depois de escolher e montar a resposta. Replays e erros de contexto anteriores
  ao sender não ativam essa chamada.
- Na criação de uma consulta, `solicitar` retorna se houve INSERT efetivo.
  `ConsultaFireAdsPendente.consulta_nova` leva essa informação ao orquestrador,
  que chama o indicador apenas após o commit da espera. Rechecagens não repetem.
- `consulta_worker.py` confirma a reserva, lê a entrada pelo repositório e encerra
  a transação antes de sinalizar. A reserva compartilhada da consulta é mantida
  durante o HTTP; o prazo original inclui o custo da sinalização.
- O escopo é uma chamada síncrona, sem thread, worker ou tarefa auxiliar.
  Uma ação é consumida no máximo uma vez por tentativa de resposta, inclusive
  se o indicador falhar. O contexto é restaurado no fim, também sob exceção.
- `digitacao.py` usa `conta_wa` e `indicate_typing` com o `id_hash` da entrada e
  o `id_phone_unidade` do turno. A operação marca essa entrada como lida.
- A sessão exclusiva usa 1 segundo para conexão/pool e 2 segundos para
  leitura/escrita, com zero retries de transporte. Esses limites são por fase;
  não equivalem a uma garantia de dois segundos de duração total. Os timeouts
  das mensagens de atendimento permanecem os anteriores.
- ID ausente/inválido, timeout, rejeição e resposta sem confirmação geram aviso
  em `whatsapp.digitacao` e permitem continuar o envio. O aviso inclui IDs
  internos de fila/conversa e tipo de erro, sem texto da exceção ou dados do
  contato. Aceite do indicador fica em DEBUG.
- As guardas e os checkpoints de persistência continuam no worker. A integração
  opcional não executa SQL, abre transação, modifica retry ou controla locks.
  A janela já existente entre a última guarda e o aceite externo permanece;
  indicador e resposta não são uma operação atômica com o banco.
- `test_indicador_digitacao.py` valida os caminhos com o SDK real e transporte
  simulado, incluindo três ativações e rechecagens. Os testes FireAds em PostgreSQL
  local verificam os vínculos, guardas, reserva entre processos e commit antes do
  indicador. Nenhum teste envia mensagens para a Meta.
  A percepção visual depende do WhatsApp: a resposta pode sair tão rápido que
  o indicador apareça por pouco tempo. Não foi adicionada espera artificial.
