# Janelas gratuitas confirmadas pela Meta para decisões de atendimento

Registrado em 29/09/2026. **Ideia futura, sem implementação autorizada nesta etapa.**

Esta pasta concentra a proposta de aproveitar os webhooks `statuses` para saber
se existe uma janela gratuita válida antes de decidir um envio, especialmente
um template. O objetivo é guardar o entendimento e os pontos de implementação
para retomar o assunto quando houver necessidade.

## 1. Decisão e relação com o consumo mensal

O acompanhamento atual continua usando `pricing_analytics`, por meio do
`worker_consumo_meta`, com persistência em `consumo_mensal_meta` e apresentação
na seção **Consumo**. Essa é a fonte dos volumes classificados pela Meta no
recorte consultado; não é necessário construir um contador local para esta ideia.

Há duas necessidades diferentes:

| Necessidade | Fonte e responsabilidade |
| --- | --- |
| Acompanhar mensagens gratuitas e cobradas por número e mês | Integração atual com `pricing_analytics`. |
| Decidir se um próximo envio pode aproveitar uma janela gratuita | Futuro processamento dos `statuses` e consulta da janela registrada. |

Os eventos individuais não substituirão os totais de analytics nem serão somados
a eles. Os volumes consultados não devem ser confundidos com uma fatura
financeira definitiva ou com uma autorização em tempo real para o próximo envio.
O escopo atual de analytics é `SERVICE`; não passar a incluir templates de
outras categorias no painel como consequência desta proposta.

Documentos relacionados:

- [Consumo mensal implementado e implantação](../../deploy/consumo_mensal_meta.md).
- [Pesquisa histórica e contador de emergência](../arquivo_pesquisa_meta_e_contador_emergencia.md).

O contador arquivado continua sendo uma alternativa separada. Esta proposta não
reativa aquele plano nem solicita alteração de produção, SQL ou deploy agora.

## 2. Regras que motivam a proposta

Segundo a documentação de preços referenciada ao final:

- A entrada elegível inclui anúncios de clique para WhatsApp da Meta e botões
  de contato de Páginas do Facebook. Um anúncio externo com link para WhatsApp
  não se torna elegível apenas por ter esse link.
- A condição documentada para abrir a janela exige o aplicativo Android/iOS;
  Web/Desktop não são suportados nessa entrada. Não inferir que uma troca de
  dispositivo posterior cancela uma janela já aberta.
- A resposta à entrada elegível precisa ocorrer em até 24 horas. A janela
  gratuita documentada dura 72 horas a partir dessa resposta e inclui templates.
- A permissão de responder sem template depende de outro prazo: 24 horas após
  a última mensagem do cliente. Uma mensagem comum renova esse prazo, mas não
  reinicia automaticamente a janela gratuita.
- Depois das 24 horas de atendimento, só templates podem ser enviados, mesmo
  que a gratuidade ainda esteja ativa. Templates continuam sujeitos à aprovação
  e às demais regras da Meta.

Revalidar essas condições antes de implementar. A hipótese de sete dias discutida
anteriormente não está adotada aqui. O controle deve privilegiar o vencimento
informado pela Meta, sem fixar um novo prazo contado pelo relógio do worker.

## 3. O que cada payload permite saber

### Mensagem recebida do cliente: `messages`

O caminho usual é `entry[].changes[].value.messages[]`. A origem pode aparecer
em `messages[].referral.source_type`, com valor `ad`. `source_id`, `source_url`
e `ctwa_clid`, quando presentes, servem à atribuição do anúncio/clique.

Não há campo documentado nesse payload normal que identifique Android, iPhone,
Web ou Desktop, nem um indicador direto de janela gratuita ativa com vencimento.
Não deduzir o dispositivo pelo `wamid`, horário ou cabeçalho HTTP do webhook.
O `referral` pode estar ausente; sua ausência também não comprova cobrança.

Portanto, `source_type = ad` é informação de origem, não confirmação suficiente
para liberar um template supondo gratuidade. Tampouco basta procurar um anúncio
na primeira conversa histórica daquele cliente.

### Evento sobre a resposta do bot: `statuses`

Base: `entry[].changes[].value`. O `field` do webhook continua sendo `messages`;
o conteúdo relevante fica no array `value.statuses[]`.

| Campo relativo a `value` | Uso previsto |
| --- | --- |
| `metadata.phone_number_id` | Identificar o número da unidade. |
| `statuses[].id` | Correlacionar o `wamid` da mensagem enviada. |
| `statuses[].recipient_id` | Identificar o destinatário. |
| `statuses[].status` | Distinguir `sent`, `delivered`, `read` e `failed`. |
| `statuses[].timestamp` | Guardar o horário informado para o evento, separado do recebimento local. |
| `statuses[].pricing.type` | `free_entry_point` indica classificação gratuita pela janela elegível. |
| `statuses[].conversation.origin.type` | `referral_conversion` identifica essa origem. |
| `statuses[].conversation.id` | Identificar a janela da Meta. Não é o ID da conversa local. |
| `statuses[].conversation.expiration_timestamp` | Vencimento Unix, documentado no status `sent`. |

A referência de status descreve que, da versão 24.0 em diante, `conversation`
fica ausente fora de uma janela gratuita de entrada; dentro dela, o identificador
é único por janela. Não exigir esse objeto em todos os eventos.

`billable = false` isolado não identifica uma janela de anúncio. Classificação
gratuita de uma mensagem sem vencimento válido não autoriza inferir o prazo das
próximas. Não confundir os valores minúsculos do webhook com os tipos em
maiúsculas usados em analytics.

Uma resposta HTTP de sucesso ao pedido de envio não substitui esses eventos e
não garante entrega ao cliente. O status `sent` também não equivale a `delivered`.

## 4. Situação real do projeto nesta revisão

O endpoint já recebe e reconhece eventos de status, mas não persiste sua
classificação nem o vencimento da janela:

- [post_flow.py](../../callback/webhook/services/post_flow.py):
  `responder_post_webhook` valida a assinatura antes de classificar o evento;
  `_responder_status_meta_sem_processar` registra um resumo no log e responde
  HTTP 200. Esse é o ponto principal a evoluir futuramente.
- `_classificar_evento_meta` examina o primeiro `entry/change`. Um `value` com
  `messages` e `statuses` simultaneamente é classificado como desconhecido.
  Uma evolução precisará tratar os arrays completos e preservar mensagens em
  envelopes mistos, sem repetir efeitos quando houver reentrega.
- [meta_signature.py](../../callback/webhook/services/meta_signature.py):
  mantém a validação de `X-Hub-Signature-256`; o novo caminho deve preservá-la.
- [historico.py](../../core/repositories/atendimento/historico.py):
  `inserir_historico_mensagem_bot` já grava `id_hash_msg_bot` como `id_hash_msg`,
  junto do número da unidade e dos vínculos com a conversa e a mensagem de origem.
- [persistencia_resposta.py](../../workers/worker_flow/transacoes/persistencia_resposta.py):
  coordena os efeitos da resposta do bot. Um status pode chegar antes do commit
  dessa persistência; não assumir que o histórico já existe ao receber o evento.
- [consumo.py](../../core/integrations/whatsapp/consumo.py) e
  [consumo_worker.py](../../workers/worker_consumo_meta/consumo_worker.py):
  permanecem responsáveis pelas métricas mensais, de forma independente.

O `sent` usado na fila e no histórico hoje representa a conclusão do fluxo local
existente. Não passar a esperar `delivered` para finalizar a fila nem modificar
retries, locks ou transições de etapa como efeito colateral desta funcionalidade.

## 5. Fluxo futuro proposto

1. O cliente envia uma mensagem. O atendimento segue normalmente pelo caminho
   existente; a origem do anúncio, se disponível, é apenas contexto adicional.
2. O bot responde e recebe o identificador da mensagem. Não calcular uma janela
   confirmada apenas a partir desse retorno ou da hora local do envio.
3. A Meta envia um `statuses`. O webhook valida a assinatura e separa esse evento
   das mensagens recebidas do cliente.
4. O evento relevante é persistido de forma durável e idempotente. O caminho
   deve ser curto, sem consultar analytics ou enviar mensagens durante o webhook.
5. Um serviço relaciona número, destinatário e `wamid` à unidade e ao histórico.
   A correlação pode ficar pendente até o histórico ser gravado pelo worker.
6. Havendo evidência coerente de janela gratuita e vencimento válido, o serviço
   registra a janela usando o prazo fornecido pela Meta.
7. Antes de um futuro template cujo envio dependa de gratuidade, a aplicação
   consulta essa janela e revalida o prazo imediatamente antes de enviar.
8. Sem confirmação suficiente, esse envio opcional não é liberado como gratuito.
   Isso não bloqueia o atendimento normal nem autoriza cobrar ou consumir reserva
   por uma regra local inventada.

O objetivo é tomar decisões com a informação recebida da Meta. Ainda assim, uma
decisão local não reserva preço: atraso entre a decisão e o envio pode atravessar
o vencimento. Definir uma pequena margem operacional antes de automatizar esses
templates; a classificação final da mensagem continua sendo da Meta.

## 6. Escopo e persistência propostos

Esta seção é desenho conceitual, não um esquema SQL pronto para aplicar.

### Identidade da janela

A janela pertence ao **cliente + número de WhatsApp da unidade**, com WABA e
identificador da janela da Meta como contexto. Não pertence ao cliente global
nem exclusivamente a uma linha de `conversa`.

- Criar uma nova conversa local não abre ou renova a janela.
- A mesma janela pode abranger mais de uma conversa local.
- Um cliente pode voltar por outra entrada elegível; registrar a nova janela
  somente quando a Meta a confirmar.
- Trocar o número da unidade não transfere a gratuidade do número anterior.
- Trocar a configuração atual da unidade não reescreve a identidade histórica
  do número/WABA que recebeu o evento.

### Dados mínimos sugeridos

Manter registros separados para eventos recebidos e janelas reconhecidas:

| Registro | Dados necessários |
| --- | --- |
| Evento de status | WABA, `phone_number_id`, destinatário, `wamid`, status, horário Meta, horário de recebimento, classificação, dados de janela quando presentes e situação da correlação. |
| Janela gratuita | Unidade/cliente identificados, número/WABA da época, ID da janela Meta, vencimento, evento que a confirmou e datas de primeira/última observação. |

O vínculo do evento com `historico_mensagens` pode ser inicialmente nulo. Não
descartar o evento por o bot ainda não ter terminado sua transação. Resolver
posteriormente, sem ligar por aproximação à conversa mais recente do cliente.

Usar timestamps com fuso (`TIMESTAMPTZ`) para os instantes. A conversão para o
fuso da unidade é de apresentação, não uma alteração do instante de expiração.
O momento em que recebemos a confirmação não é necessariamente o início da
janela; não inventar uma coluna de início subtraindo 72 horas do vencimento.

Uma função de consulta pode distinguir três resultados, sem obrigatoriamente
persistir um estado que ficará desatualizado com o tempo:

- **Confirmada e vigente:** identificação coerente, vencimento válido e ainda
  dentro do limite operacional de envio.
- **Expirada:** havia confirmação, mas o vencimento já passou.
- **Não confirmada:** faltam informações suficientes ou há inconsistência.

“Não confirmada” não significa que a próxima mensagem necessariamente será paga;
significa que esta aplicação não deve prometer gratuidade por aquela janela.

## 7. Duplicidade, ordem e falhas

- Reentregar um evento não pode criar outra janela nem renovar o prazo. A chave
  de deduplicação deve distinguir eventos do mesmo `wamid`; usar apenas o ID da
  mensagem apagaria a diferença entre `sent`, `delivered` e `read`.
- Definir no projeto prático uma chave por número, mensagem, tipo de status e
  timestamp, com tratamento explícito para enriquecimento/correção do payload.
  A mesma evidência não deve produzir efeitos duas vezes, inclusive com workers
  concorrentes.
- Um `delivered` ou `read` sem `conversation` não apaga o vencimento já confirmado
  por `sent`. A falta de um campo num evento posterior não é revogação da janela.
- Um evento atrasado de uma janela anterior deve atualizar seu próprio registro,
  sem substituir uma janela mais recente. Não usar ordem de chegada como prova
  de ordem dos fatos.
- Vencimentos conflitantes para a mesma janela exigem diagnóstico. Não escolher
  automaticamente o maior prazo, pois isso poderia liberar um envio cobrado.
- Se houver falha antes de persistir um evento relevante, permitir reentrega;
  não responder sucesso como se a gravação tivesse ocorrido. Depois de gravar,
  responder sucesso e concluir correlações pendentes fora da requisição.
- O tratamento de erro atual procura o ID em `messages`; não reaproveitá-lo
  cegamente para `statuses`, que têm identificadores e efeitos diferentes.
- Um status não representa nova fala do cliente: não entra na fila de entrada,
  não passa pelo filtro de flood do cliente, não renova 24 horas e não avança
  etapas, follow-up ou funil.
- Um evento de número desconhecido, assinatura inválida ou correlação divergente
  não deve criar autorização de envio. Manter isolamento entre unidades.
- Não reinterpretar `failed` como ordem para reenviar automaticamente. Tratar
  falhas de entrega é outra evolução, fora deste objetivo inicial.

## 8. Exemplos para validar o entendimento

Horários abaixo são ilustrativos, no mesmo fuso, assumindo que a Meta informou
o vencimento indicado.

| Situação | Resultado esperado |
| --- | --- |
| Ana chega pelo anúncio no celular na segunda às 10h; bot responde às 10h05; `sent` confirma expiração na quinta às 10h05. | Registrar esse vencimento para Ana e aquele número. |
| Ana não escreve novamente; na quarta ainda existe a janela acima. | O prazo normal de resposta já acabou. Um template aprovado pode aproveitar a janela; texto comum não ganha permissão por causa das 72 horas. |
| Ana escreve novamente na quarta. | Renovar as 24 horas conforme a regra de atendimento; não estender automaticamente a expiração de quinta. |
| Bruno tem `source_type = ad`, mas não chegou confirmação de janela. | Preservar a origem, sem liberar template opcional como gratuito por inferência. |
| Carla inicia o contato pelo PC. | A condição documentada não abre a janela por essa entrada; não simular uma janela local apenas por haver anúncio. |
| Chega `read` antes de `sent`; o `sent` depois confirma o vencimento. | Processar sem exigir ordem de chegada e registrar a evidência suficiente quando disponível. |
| O `sent` chega antes do commit do histórico do bot. | Guardar o evento e reconciliar depois, sem perder a confirmação nem criar conversa artificial. |
| Ana conversa com outro número/unidade. | Não reutilizar a janela do primeiro número. |
| Ana abre outra conversa local com o mesmo número. | Consultar a janela existente; o novo ID local não renova o prazo. |
| Um template é decidido próximo do vencimento. | Aplicar a margem definida e conferir novamente antes do envio, sem prometer preço reservado. |

## 9. Responsabilidades na futura implementação

Preservar a organização já adotada pelo projeto:

- **Webhook:** validação, separação dos eventos e aceite após persistência.
- **Integração Meta:** interpretação do contrato da API e normalização dos campos.
- **Serviço de janelas:** correlação, coerência dos dados, validade e decisão.
- **Repositórios:** consultas e transações de eventos/janelas, sem lógica HTTP.
- **Atendimento:** consulta ao serviço no ponto em que um envio realmente dependa
  de gratuidade. Não espalhar comparação de timestamps por todos os senders.
- **Reconciliação:** resolver eventos ainda sem histórico vinculado; avaliar se
  cabe em uma rotina existente antes de criar outro worker permanente.

Os nomes definitivos dos novos arquivos/tabelas, índices, política de retenção,
margem de envio e estratégia de reconciliação ficam para o projeto prático.
Registrar apenas dados necessários; evitar tokens e payloads completos em logs.

## 10. Verificações antes de implementar

1. Reconsultar a documentação oficial e a versão efetiva do webhook, não apenas
   a versão usada nos pedidos de envio. Confirmar o contrato vigente dos campos.
2. Capturar exemplos reais com dados protegidos: entrada elegível, origem comum,
   status com e sem janela, diferentes eventos e falhas. O exemplo histórico do
   Postman usa `CBP`; não copiá-lo como contrato atual de preços.
3. Confirmar com payload real a combinação de classificação e vencimento que
   será aceita pelo serviço. Campo ausente permanece desconhecido, não vira zero
   nem cria uma janela por conta própria.
4. Testar assinatura, múltiplos `entry/changes/statuses` e envelopes mistos, sem
   perder ou duplicar o processamento atual de mensagens recebidas.
5. Testar correlação antes/depois do commit, duplicidade, ordem invertida,
   concorrência, vencimentos conflitantes e falha de banco seguida de reentrega.
6. Testar fronteiras de tempo, fuso, janela expirada, falta de confirmação,
   novo número, outra unidade e nova conversa local do mesmo cliente.
7. Demonstrar que fila `sent`, locks, retries, etapas, follow-up, encerramentos
   por idade, funil e métricas de consumo preservam seu comportamento.
8. Preparar migração e rollback somente quando a implementação for solicitada.
   Primeiro observar a coleta; habilitar decisões de templates depois de validar
   os eventos. Coletar status, por si só, não deve disparar mensagem alguma.

## 11. Fontes e limites da verificação

Referências registradas em 29/09/2026:

- [Referência oficial de preços da Meta](https://developers.facebook.com/documentation/business-messaging/whatsapp/pricing).
- [Referência oficial de status](https://developers.facebook.com/documentation/business-messaging/whatsapp/webhooks/reference/messages/status).
- [Objeto de mensagem recebida — coleção oficial da Meta no Postman](https://www.postman.com/meta/whatsapp-business-platform/folder/1dtuocp/messages-object).
- [Exemplo histórico de status `sent` — coleção oficial da Meta no Postman](https://www.postman.com/meta/whatsapp-business-platform/request/85iyhv5/status-message-sent-business-reply-to-user).
- [Reprodução da documentação de preços](https://support.chatarchitect.com/books/meta-whatsapp/page/pricing-on-the-whatsapp-business-platform-developer-documentation).
- [Reprodução da referência de status](https://support.chatarchitect.com/books/meta-whatsapp/page/status-messages-webhook-reference-developer-documentation).

Nesta revisão, os endereços diretos da Meta responderam HTTP 429. Foram usados
o conteúdo indexado da coleção oficial e reproduções identificadas do texto da
documentação para registrar o entendimento. Isso não equivale a uma validação
ao vivo dos webhooks da conta: os campos opcionais e as regras vigentes devem
ser conferidos novamente na implementação. Não transportar descrições antigas
de preços para a política de outubro sem verificar sua vigência.

**Entrega desta etapa:** documentação da ideia. O projeto continua operando com
o comportamento atual até uma solicitação futura de implementação.
