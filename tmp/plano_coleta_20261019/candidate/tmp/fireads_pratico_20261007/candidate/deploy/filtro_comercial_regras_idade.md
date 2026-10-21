# Implantação do filtro Comercial e das regras de idade

## Contrato da entrega

- Suporte configurável: desativado, 50, 60, 70 ou 80; somente titular até 89.
- Universal: 90 anos ou mais, titular ou dependente, com contato comercial.
- Titular menor de 18 e dependente abaixo de 4 com BPA/5 sem BPA encerram sem contato.
- Nenhum encerramento por idade ganha Funil ou bloqueio de 30 dias.
- Comercial no painel lê a última conversa por cliente/unidade; relatório conta
  conversas encerradas no período, somente pelos motivos da configuração atual.

## Preparação e validação

Comparar a base do plano com o checkout atual antes de substituir arquivos inteiros.
Reconciliar alterações posteriores; não sobrescrever trabalho novo com a versão do plano.
Usar uma cópia local, sem credenciais de produção e com envs de teste.

```bash
python -m unittest tests.unit.test_encerramentos_por_idade tests.unit.test_suporte_por_idade tests.unit.test_suporte_idoso_email_obrigatorio tests.unit.test_monitoramento_painel tests.unit.test_retomada_followup tests.unit.test_worker_flow_runtime tests.unit.test_metricas_perfis_relatorios tests.unit.test_followup
node --check callback/monitoramento/static/monitoramento/js/painel.js
```

Rodar também a suíte completa. As 17 falhas/subtestes antigos de texto e
espaçamento foram corrigidos nos testes antes da aplicação, preservando os
textos aprovados. Na aplicação local em 26/09/2026, a suíte de 293 testes passou;
depois, 18 testes direcionados passaram, incluindo um caso adicional de recuperação
universal após mudança de configuração (294 testes unitários distintos).

Validar a migração em PostgreSQL vazio e local, com o nome exato
`test_chatbot_comercial`, usando `COMERCIAL_IDADE_TEST_DSN`. O teste recusa host
remoto e schema chatbot preexistente. Não apontar para o banco do chatbot real.

```bash
python -m unittest tests.integration.test_encerramentos_por_idade_postgres
```

Sem a variável, os testes são ignorados: isso não valida a migração real.
Na aplicação local, 13 testes de integração passaram em PostgreSQL 18.3
descartável, incluindo a migração nova e a compatibilidade com a migração
anterior. O servidor de teste foi encerrado ao concluir. Isso não executa a
migração no banco da VM nem substitui a conferência dos dados reais no deploy.
Conferir query plans com volume representativo; consultas novas reaproveitam
os índices de conversa e histórico existentes e não fazem uma consulta por chat.
Revisar a tela com fixtures: desktop e celular, filtro, detalhes, legenda por
mouse/teclado/toque, período e ausência de rolagem horizontal.

## Sequência de deploy

1. Conferir checkout limpo, commit de destino e snapshot/recuperação disponíveis.
2. Regularizar números comerciais reais ausentes/inválidos. A migração aborta
   antes de alterar dados caso alguma unidade esteja irregular.
3. Impedir edição simultânea no Admin. Parar follow-up, flow e funil. Suspender
   temporariamente o processo web durante a troca de código/schema; o provedor
   precisa poder repetir webhooks nesse intervalo. Não manter Admin antigo ativo.
4. Atualizar o checkout. Executar a migração inteira do passo SQL e guardar a saída
   com as unidades convertidas de suporte 90 para NULL. Se falhar, dar ROLLBACK,
   resolver a causa e não iniciar o código novo com schema antigo.
5. Executar `manage.py check --deploy`, o verificador de follow-up sem envio e
   `collectstatic --noinput` com o ambiente da VM. Não rodar seeds de instalação.
6. Iniciar/reiniciar web e workers com o código novo. A migração incrementa
   `cache_controle.unidades`; o reinício evita processo com cache antigo.
7. Conferir serviços, logs e HTTP; recarregar o painel para obter JS/CSS versionados.
   Uma aba aberta com JS antigo deve ser recarregada: o indicador escalar foi substituído.
8. Conferir Comercial e relatório com dados reais somente por leitura. Não fabricar
   atendimentos, mudar motivos históricos nem gerar envios para validar a tela.

## Recuperação e limites

Motivo específico é salvo na finalização atômica com fila sent. A recuperação
usa apenas resposta comprovada do mesmo par conversa/entrada. Idade vem dessa
entrada, sem substituir pelo cadastro global. Para suporte 50–89, limite atual
compatível prevalece; se incompatível/desativado, escolhe a maior faixa permitida
que não exceda a idade. Essa faixa é compatível, não prova a configuração original.

Sem resposta persistida após sucesso externo, permanece o risco aceito de repetir
com a configuração atual. Não há nova transação antecipando motivo ou idade.
Legados sem prova do limite permanecem genéricos, e não entram na tabela por
configuração atual. Universal antiga de 100+ não vira 90+ automaticamente.

## Reversão

Parar processamento e bloquear edições novamente. O script
`rollback/20260926_filtro_comercial_regras_idade.sql` relaxa as regras da unidade,
mas conserva os motivos novos; removê-los faria perder compatibilidade com dados.
Não restaura NULL para 90 automaticamente. Usar a evidência do deploy e conferir
eventuais edições posteriores antes de uma restauração individual.

O código antigo não interpreta os motivos novos no painel/indicador comercial.
Uma reversão operacional não recupera essa interpretação: publicar correção adiante
é preferível quando os novos registros já existem. Nunca apagar registros para
forçar uma reversão. Revalidar cache, serviços, assets e histórico após o recuo.
