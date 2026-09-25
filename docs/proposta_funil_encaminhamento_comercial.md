# Proposta: enviar ao funil os atendimentos encaminhados ao comercial

**Registrado em:** 24/09/2026  
**Status:** proposta para desenvolver após o próximo deploy. Este documento não implementa a mudança.

## Objetivo

Além dos atendimentos já elegíveis pelas regras atuais, enviar ao funil os novos
atendimentos encerrados após disponibilizar ao lead o contato comercial da unidade.
Enviar os dados coletados, mesmo quando o encaminhamento acontecer antes da triagem,
e informar claramente esse encaminhamento na observação do lead.

A regra deve valer para novos encaminhamentos após sua implantação. Não reclassificar
nem enviar automaticamente atendimentos antigos. Na implementação, revisar o código
que estiver em produção depois do próximo deploy, preservando as regras existentes.

## Estratégia proposta para o banco

Reutilizar `conversa.motivo_encerramento`, padronizando os novos encaminhamentos como
`encaminhado_comercial`. Não criar uma coluna booleana redundante para o mesmo fato.

O motivo representa que o bot disponibilizou o contato comercial. Não comprova que
o lead clicou no botão, falou com um consultor ou reservou sua experiência.

Será necessário atualizar o DDL e preparar uma migração incremental da restrição
de motivos permitidos, com base no banco após o próximo deploy. Não gerar nem aplicar
essa migração nesta tarefa de documentação. Preservar os motivos históricos.

Antes de padronizar o motivo, mapear todos os consumidores dos motivos atuais,
incluindo relatórios de suporte por idade, recuperação de atendimentos e bloqueios.
A mudança não pode apagar a distinção necessária a esses consumidores nem alterar
as regras que decidem quem recebe o contato comercial.

## Elegibilidade adicional para o funil

A nova rota precisa satisfazer, em conjunto:

1. Estar em uma etapa explicitamente autorizada a encaminhar ao comercial.
2. Ter confirmação do envio da mensagem com o botão de contato comercial.
3. Estar encerrada com `motivo_encerramento = 'encaminhado_comercial'`.
4. Satisfazer os requisitos operacionais da integração e o controle de envios existente.

Confirmar histórico, motivo e encerramento na mesma transação após o envio confirmado.
Não inferir encaminhamento apenas pela idade, pela etapa ou pela existência do número
comercial na configuração da unidade. Encerramento por menor de idade, silêncio do
segundo follow-up ou qualquer outro motivo não cria essa elegibilidade.

Manter as rotas atuais do funil. A tolerância à triagem ausente pertence somente à nova
rota de encaminhamento; não enfraquecer a validação de completude das demais rotas.
Conferir na implementação se o encaminhamento fica disponível no próximo ciclo do
worker ou se há algum intervalo de espera aplicável no contrato vigente.

## Montagem dos dados e envio

- Reutilizar o formato, a integração por unidade e os registros de envio do funil.
- Enviar os dados efetivamente coletados naquele atendimento, preservando a distinção
  entre titular e dependente e as nomenclaturas `nome_titular`, `nome_dependente` e `nome_agente`.
- Na rota dependente, identificar quem é o contato responsável e quem receberá a experiência.
  Não atribuir ao titular a idade do dependente, nem o inverso.
- Informações não coletadas devem ficar ausentes ou identificadas como não informadas,
  conforme o contrato do campo. Não preencher com dados inventados.
- Quando não houve triagem, registrar “Triagem não realizada — encaminhamento anterior
  a essa etapa”. Se houver coleta parcial em uma futura rota, preservar as respostas
  reais e sinalizar que a triagem está incompleta.
- Revisar os campos obrigatórios do destino antes de admitir dados parciais.
- Reutilizar o controle de envio por conversa e a recuperação de falhas, evitando
  criar uma segunda fila ou um caminho paralelo de envio para o mesmo atendimento.

## Exemplo de observação

Exemplo ilustrativo de titular encaminhada por uma unidade com suporte a partir de 70 anos:

```text
Encaminhamento ao comercial

Lead atendido pela assistente Mia, da unidade Supera Porto Velho Olaria.

Titular: Ana
Idade: 71 anos
Profissão: Aposentada
Atendimento: Para a própria titular.

Foi disponibilizado ao lead o número comercial da unidade por meio do botão
“Falar agora”, para continuidade do atendimento e reserva da experiência Supera gratuita.

Triagem: Não realizada — encaminhamento anterior a essa etapa.

Confira o painel de monitoramento e o WhatsApp comercial para verificar se o lead
entrou em contato.
```

Para dependente, usar campos separados, por exemplo `Titular: Maria`,
`Dependente: João` e `Idade do dependente: 100 anos`, mantendo somente as informações
coletadas. A orientação final deve direcionar ao painel e ao WhatsApp comercial,
sem sugerir que já existe uma reserva na plataforma de agendamento.

## Painel de monitoramento

O filtro **Funil** deve incluir esses chats depois que o worker confirmar o envio
ao funil. Elegibilidade ou tentativa com erro não equivale a envio concluído.

Preservar a representação de um chat por cliente/unidade, reunindo seus IDs de
conversa, o isolamento entre unidades e as regras de período do painel. O fato de
uma dessas conversas ter sido enviada com sucesso deve alimentar a marcação já
existente, sem duplicar chats e sem aplicar a regra particular do filtro Follow-up
que descarta marcadores de atendimentos anteriores.

## Verificações antes do deploy desta implementação

- Encaminhamento por faixa configurada e regra geral de idade avançada, nas rotas
  titular/dependente em que cada encaminhamento for permitido.
- Encerramentos sem disponibilização do contato comercial permanecem fora da nova rota.
- Falha no envio do botão não registra encaminhamento concluído nem habilita o funil.
- Dados parciais não interrompem a nova rota e não afrouxam as regras das rotas atuais.
- Retries, recibos, marcação de sucesso e recuperação respeitam o contrato atual do funil.
- O filtro Funil mostra sucesso confirmado, respeitando unidade, período e agrupamento.
- Relatórios e demais consumidores dos motivos anteriores continuam coerentes.
- Histórico anterior à implantação não recebe envios retroativos por essa alteração.
- DDL e migração incremental correspondem à versão efetivamente implantada no banco.

Os testes devem usar integrações simuladas e banco local descartável. Esta proposta
não autoriza envios de teste a leads nem alterações no banco de produção.
