# LGPD Mínima - V1

## Objetivo

Registrar o tratamento mínimo de dados pessoais na V1 sem alterar banco, fluxo,
worker, webhook ou regras de negócio.

A V1 começará com poucos contratos e baixa visibilidade, mas ainda precisa ter
clareza sobre quais dados trata, por qual finalidade e quais limites técnicos
foram assumidos para a primeira produção.

## Dados Tratados

O sistema pode tratar:

- telefone ou `wa_id` do cliente;
- mensagens recebidas pelo WhatsApp;
- respostas enviadas pelo bot;
- unidade vinculada ao atendimento;
- status de fila;
- status da conversa;
- histórico de mensagens;
- bloqueios temporários por conversa finalizada;
- bloqueios por flood ou abuso;
- logs técnicos com identificadores mascarados.

## Finalidade

Os dados são tratados para:

- atendimento automatizado pelo WhatsApp;
- agendamento ou triagem comercial;
- controle de turno da conversa;
- prevenção contra flood e abuso;
- recuperação de estados intermediários;
- rastreabilidade técnica de falhas;
- suporte operacional via Django Admin.

## Compromissos da V1

Na V1, o projeto deve:

- não coletar dados fora do necessário para o fluxo;
- não registrar credenciais reais em código, README, prints ou logs;
- carregar credenciais por variável de ambiente;
- manter `.env` fora do Git;
- documentar nomes de variáveis sem publicar valores secretos;
- mascarar identificadores numéricos longos nos logs;
- manter tabelas administrativas com permissões restritas;
- preservar as regras de negócio já definidas para fila, turno, bloqueios e
  recuperação.

## Fora do Escopo da V1

Ficam para a V2:

- política formal de retenção;
- anonimização automática;
- exclusão ou exportação automatizada mediante solicitação;
- revisão jurídica completa da base legal;
- política de privacidade pública;
- termos formais com unidades contratantes;
- registro completo de tratamento;
- criptografia de telefone em coluna própria;
- coluna HMAC para busca sem expor telefone original.

## Relação com a V2

Os pontos avançados de LGPD ficam documentados em [_V2/lgpd.md](_V2/lgpd.md) e
[_V2/seguranca-avancada.md](_V2/seguranca-avancada.md). A V1 registra o mínimo
técnico-operacional; a V2 deve transformar isso em governança, retenção,
auditoria e processos formais.

## Observação

Este documento não substitui revisão jurídica. Ele apenas registra o mínimo
técnico-operacional para a V1 nascer com mais clareza e menor exposição.
