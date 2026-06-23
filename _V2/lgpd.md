# LGPD - V2

## Objetivo

Registrar os pontos de LGPD que ficam fora da V1 básica. A V1 deve documentar os
dados tratados e reduzir exposição desnecessária. A V2 deve transformar isso em
processo, retenção e governança.

## Dados Pessoais Tratados pelo Sistema

Na prática, o sistema pode tratar:

- telefone ou `wa_id` do cliente;
- mensagens enviadas pelo cliente;
- respostas enviadas pelo bot;
- unidade vinculada ao atendimento;
- status de fila;
- status da conversa;
- histórico de atendimento;
- registros de bloqueio por flood ou conversa finalizada;
- logs técnicos com identificadores mascarados.

## Finalidade

Finalidades esperadas:

- atendimento automatizado pelo WhatsApp;
- agendamento ou triagem comercial;
- controle de turno para evitar confusão do bot;
- prevenção contra flood e abuso;
- rastreabilidade técnica de falhas;
- suporte operacional via Django Admin.

## Fora do Escopo da V1

Ficam para a V2:

- política formal de retenção;
- anonimização automática;
- exclusão/exportação de dados mediante solicitação;
- registro completo de tratamento;
- revisão jurídica da base legal;
- política de privacidade pública;
- termos com unidades contratantes;
- rotina de resposta a incidente;
- classificação de dados por sensibilidade.

## Retenção

A V2 deve definir por quanto tempo manter:

- histórico de mensagens;
- fila processada;
- logs técnicos;
- bloqueios temporários;
- dados de clientes que finalizaram atendimento;
- dados de unidades removidas.

Essa decisão deve equilibrar:

- necessidade técnica de auditoria;
- necessidade operacional da unidade;
- minimização de dados;
- obrigações contratuais;
- custo de armazenamento.

## Solicitação de Titular

A V2 deve prever como responder solicitações de:

- confirmação de tratamento;
- acesso aos dados;
- correção;
- anonimização;
- exclusão;
- informação sobre compartilhamento;
- revogação quando aplicável.

## Observação de Produto

Na fase inicial, o risco operacional maior é vazamento acidental de credenciais e
exposição desnecessária em logs. Por isso a V1 deve ser simples e pragmática. A
V2 deve amadurecer a governança quando o produto tiver mais contratos e mais
visibilidade.
