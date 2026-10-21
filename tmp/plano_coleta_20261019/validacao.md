O código abaixo foi montado em uma cópia de trabalho isolada da revisão-base.
Apenas este documento foi alterado no projeto principal; o código proposto não
foi aplicado nele e nenhuma migração foi executada na produção.

- **156 testes unitários passaram** na bateria indicada acima, incluindo os
  testes novos de extração, combinações de campos, conflitos, recência, mensagens
  e destino da entrega, junto das regressões de FireAds, fluxo e digitação.
- **48 cenários de integração foram validados em PostgreSQL local descartável**:
  38 da suíte FireAds e 10 da coleta parcial. A execução conjunta passou em 47;
  um teste de migração histórica precisou corrigir a preparação da fixture
  (origem e contexto devem ser gravados juntos) e passou na reexecução isolada.
  Essa última alteração afetou somente a fixture, sem mudança no código funcional.
- A integração executou o SQL real, incluindo reexecução sem perda de dados,
  preservação de consultas anteriores, aplicação após rollback, expiração sem
  nova consulta, perda do lock, conflito de e-mail, inicialização na etapa 2,
  transição autorizada 1 → 4 e reaproveitamento de resposta já persistida.
- A entrega ao dashboard foi verificada com HTTP substituído: o destino fica
  confirmado no PostgreSQL antes do POST. Atualizações e criação mantêm o
  contrato de observações e o canal correspondente.
- Os arquivos Python propostos passaram por análise sintática; os blocos de
  código do documento foram conferidos contra os arquivos usados na validação.

Essas verificações não são um teste de ponta a ponta na VM, na Meta ou na planilha
real. O PostgreSQL foi descartável e os serviços externos foram substituídos;
os testes simulam rollback/retomada, não perda física do disco ou crash do sistema
operacional. A homologação de uma conversa nova continua sendo uma etapa do
deploy. Os limites de falha externa descritos anteriormente continuam valendo.
