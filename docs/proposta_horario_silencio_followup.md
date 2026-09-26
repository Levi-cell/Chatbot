# Proposta — horário de silêncio do follow-up

**Status:** ideia para implementação futura; nenhuma regra de envio foi alterada.
**Registrada em:** 25/09/2026.

## Objetivo

Evitar mensagens proativas de madrugada, considerando o horário local da unidade
e o prazo disponível para enviar dentro da janela de 24 horas.

## Comportamento atual

- A referência da janela é a última mensagem do cliente registrada no histórico.
  Cada nova mensagem dele renova o prazo; mensagens do bot não o renovam.
- O worker já exige margem de um minuto: a referência deve ter menos de 23h59.
- O primeiro follow-up espera sete horas desde a mensagem do bot que serve de
  referência. O segundo espera mais sete horas desde o envio efetivo do primeiro.
- Somente as etapas 1–17, inclusive a 8, recebem follow-up.
- A conversa só é encerrada pelo segundo follow-up após confirmação do envio
  e persistência dos efeitos. A falta de janela não autoriza encerramento silencioso.

Consultar a [seleção de elegíveis](../core/repositories/atendimento/followup.py),
o [worker](../workers/worker_followup/followup_worker.py) e o
[contrato operacional](../workers/README.md).

## Ideia proposta pelo usuário

Se o lembrete ficar elegível durante o horário de silêncio:

1. Calcular o fim da janela com base na última mensagem do cliente.
2. Se houver tempo suficiente depois do silêncio, adiar para a próxima abertura.
3. Caso contrário, permitir excepcionalmente o envio antes de a janela acabar,
   com margem de segurança. Essa alternativa pode enviar durante a madrugada.

Exemplo ilustrativo, com silêncio das 22h às 8h:

| Fim da janela | Comportamento proposto |
|---|---|
| 10h | Esperar até as 8h e revalidar a elegibilidade. |
| 4h | Enviar antes das 4h, com margem, mesmo durante o silêncio. |

O período 22h–8h é apenas um exemplo, não uma configuração aprovada.

## Alternativa discutida: silêncio absoluto

Priorizar o descanso do cliente e deixar de enviar o lembrete quando esperar
pela abertura ultrapassaria o prazo seguro. Essa foi a recomendação discutida,
mas ainda não houve escolha definitiva entre ela e a exceção acima.

Antecipar um envio para antes do silêncio só é possível se as sete horas mínimas
já tiverem sido cumpridas e todos os demais critérios continuarem válidos.
Não reduzir esse intervalo implicitamente para acomodar o horário.

## Regras a preservar na implementação

- Revalidar horário, janela, fila, bloqueios e elegibilidade com o lock da conversa
  antes de enviar. Uma resposta do cliente durante a espera exige novo cálculo.
- Não marcar envio, avançar `followup_stage` ou encerrar a conversa só por adiar
  ou deixar de enviar um lembrete.
- Adiar o primeiro pode deixar o segundo sem janela. Não enviar os dois juntos
  nem encurtar as sete horas entre os envios efetivos.
- Preservar a retomada pelo flow, o reset do stage e as proteções contra duplicidade.
- Usar fuso explícito da unidade, sem depender do horário local da VM.
- Considerar intervalo de varredura, tempo de envio e eventuais atrasos ao definir
  a margem. Não programar para o último segundo da janela.

## Decisões pendentes

Definir o horário de silêncio, o fuso de cada unidade, se a configuração será
global ou por unidade, a margem de segurança e a política quando não for possível
esperar. Antes de implementar, validar os limites de horário, as duas camadas,
retornos do cliente durante a espera e a perda de janela após adiar o primeiro.

Este documento não autoriza deploy, alteração de banco ou mudança do comportamento
atual. A necessidade de configuração persistida será avaliada na implementação.
