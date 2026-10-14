# Testes do projeto

A atualização de 09/10/2026 tem cobertura para suspensão por `status_pagamento`
nos testes de consumo Meta, FireAds/Funil, follow-up e runtime do worker principal.
Inclui `FALSE`/`NULL`, preservação das pendências, reativação, reexecução da migração
de dequeue e separação da edição de personalização no Admin. Consulte
[`status_pagamento_e_admin.md`](../docs/status_pagamento_e_admin.md).

Esta pasta reúne testes unitários, de contrato e de integração SQL. Além do núcleo
transacional, ela cobre regras e utilitários já implementados:

- cenário completo de turno A/B/C;
- retry, requeue, ordem da fila e fencing por `lock_version`;
- persistência idempotente, avanço e não avanço de etapa;
- checkpoints, commits, rollback e conclusão da fila no worker;
- suporte ao idoso e obrigatoriedade do e-mail;
- validação da oferta, início da triagem, profissão e saudação após inatividade;
- experiência Supera gratuita, coerência titular/dependente, aceite de reserva com
  respostas antigas e preservação do texto em replay e follow-up;
- montagem dos relatórios semanais e totais;
- payloads e sondas manuais do Funil;
- vínculo 1:1 opcional de monitoramento e autorização de conversas/mensagens por unidade;
- login nativo, par username/senha, sessão, CSRF e revogação do acesso ao portal;
- painel somente leitura, períodos, consultas por unidade, botões históricos,
  indicadores, Google CSV e CSV essencial sem o prefixo brasileiro `+55`;
- follow-up proativo, retomada reativa, elegibilidade, migração e locks entre workers.

Para executar a suíte completa a partir da raiz:

```powershell
python -m unittest discover -s tests -t . -p "test_*.py"
```

Organização atual:

```text
tests/unit/test_fluxo_turno_abc.py
tests/unit/test_retry_essencial.py
tests/unit/test_persistencia_essencial.py
tests/unit/test_worker_flow_runtime.py
tests/unit/test_suporte_idoso_email_obrigatorio.py
tests/unit/test_saudacao_retorno.py
tests/unit/test_valida_etapa7.py
tests/unit/test_mensagens_reserva.py
tests/unit/test_inicio_informacoes_supera.py
tests/unit/test_valida_etapa11.py
tests/unit/test_validador_profissao.py
tests/unit/test_gerar_monitoramento_unidades.py
tests/unit/test_metricas_perfis_relatorios.py
tests/unit/test_sondas_funil.py
tests/unit/test_monitoramento_unidade.py
tests/unit/test_monitoramento_login.py
tests/unit/test_monitoramento_painel.py
tests/unit/test_followup.py
tests/integration/test_followup_postgres.py
```

Por padrão, os testes usam fakes e mocks para fronteiras externas, sem chamar
Meta, Funil, Redis ou RDS. A integração com PostgreSQL local só executa quando
`FOLLOWUP_TEST_DSN` é fornecida explicitamente. Um utilitário manual não deve
ser executado como forma de testar sua importação.

`test_botoes_webhook.py`, `test_valida_etapa18.py`, `test_fluxo_reserva_link.py`
e `test_pywa_compatibilidade.py` cobrem a escolha de turno: JSON dos botões
serializado pela PyWa, extração no webhook, tipos `interactive` e
`interactive_button`, resolução 18 → 19, persistência e replay sem novo envio.
Cobrem também frases afirmativas e a recusa de respostas ambíguas, múltiplos
turnos e menções sem escolha. As fronteiras HTTP e SQL são simuladas.

Testes unitários pertencem a `tests/unit/`; contratos com PostgreSQL real ficam
em `tests/integration/` e exigem ambiente descartável explícito. Dados e classes
auxiliares exclusivos de teste ficam em `tests/`, nunca nos módulos de produção.
Sem `FOLLOWUP_TEST_DSN`, a descoberta pula a integração PostgreSQL.

`test_mensagens_reserva.py` cobre negativas na escolha do participante,
gratuidade contextual, preservação do aceite flexível, retomada com uma
saudação, barreira terminal e igualdade entre texto enviado e histórico.
Também verifica a composição tratamento + repetição para titular/dependente,
as apresentações exclusivas da etapa 1, inatividade com avanço ou tratamento,
follow-up sem nova apresentação/despedida e participante preservado na reserva.
Os envios são simulados; a consulta do participante é conferida com cursor
substituído, sem conexão com banco de produção.

`test_inicio_informacoes_supera.py` cobre os pedidos de apresentação com e sem
saudação, acentos e interrogação, rejeição de palavras isoladas e outros assuntos,
prioridade de mídia/reforço/financeiro e envio do texto aprovado com os dados da
unidade. Verifica a inicialização da etapa 1, convergência das duas aberturas para
a etapa 2, follow-up sem reapresentação e retry sem novo envio. Meta e banco são
substituídos nos testes; não são feitas chamadas reais.

O teste de monitoramento executa o SQL de autorização em SQLite em memória,
adaptando apenas os placeholders, com um cliente compartilhado por duas
unidades. Cobre isolamento por conversa/mensagem, revogação do vínculo,
desativação de conta, várias unidades sem conta, exclusividade do usuário,
exclusão da conta com preservação da unidade, sessão inválida e falha de banco.
Não acessa o RDS. `fixtures/unidade_monitoramento_legado.sql` representa apenas
a proposta anterior para testar a transferência dos vínculos; não é uma
migração de produção.

`test_monitoramento_login.py` usa o backend, hashes de senha e sessões reais do
Django com usuários fictícios e SQLite em memória. Cobre senha de outra conta,
contas não autorizadas, erros, expiração de CSRF, logout, rotação de sessão,
redirecionamento fixo e escape de HTML. Substitui somente a conexão da thread
durante o teste e restaura-a ao terminar; não cria usuários nem tabelas no RDS.

`test_monitoramento_painel.py` valida as rotas privadas, métodos permitidos,
propagação obrigatória da unidade autorizada, quantidade de parâmetros dos SQLs,
consolidação de perfis, 24 etapas, períodos comparáveis e os quatro downloads
CSV (Google e essencial, todos e elegíveis). Cobre todos os períodos, unidade
autorizada, revogação de acesso, acentos, campos vazios e proteção contra fórmulas
nos dados textuais. Seus payloads vivem em `fixtures/monitoramento_painel.py` e
são fictícios.
O teste distingue a remoção de `+55` no essencial da preservação do telefone
internacional no Google CSV; não remove o DDD nem altera os dados de origem.

## Follow-up

A segunda camada é coberta em `unit/test_followup.py` (redação por rota, nomes e
falha de envio) e `integration/test_followup_postgres.py` (7h contadas do primeiro
envio real, etapas 1–17 e a 18 somente para unidade sem link incluindo 8, guardas de silêncio/fila/janela, encerramento
atômico com rollback, ausência de terceiro envio e reabertura sem prefixo).
O teste do painel usa as consultas reais para provar que outra conversa do mesmo
chat invalida o stage antigo, mesmo fora do período selecionado. A migração de
segundo follow-up é executada integralmente no PostgreSQL descartável, verificando
preservação dos dados e o novo domínio do motivo de encerramento.

`unit/test_mensagens_etapa11.py` cobre a introdução da triagem para titular e
dependente: nome carregado na entrada 10→11, mensagem inicial, tratamentos,
contexto autônomo, inatividade e follow-up. Verifica falha antes do envio para
dependente sem nome e a preservação do participante nas seis perguntas,
inclusive dependente adulto, sem alterar as regras de confirmação e avanço.

`unit/test_mensagens_contexto.py` cobre a mensagem autônoma de contexto em
todas as etapas: não usa compositores de tratamento ou perguntas de repetição.
Também verifica titular/dependente, ausência de avanço, botões/rodapés, link,
dados de apresentação e o prefixo único de inatividade, com envio simulado.

`unit/test_followup.py` cobre envio exato, reação, etapas e botões reais com HTTP
substituído, recuperação, falta de lock, falhas e parâmetros SQL. O teste de runtime
do flow cobre a repetição comum sem chamar validadores ou persistência de transição.
Cobre saudação com e sem nome, texto enviado igual ao histórico, isolamento do
prefixo sob exceção, retorno legado sem data de envio e falha sem interromper o lote.
Na etapa 1, cobre cliente antigo com nome salvo: saudação genérica, coleta de nome
mantida, reação ignorada e cadastro preservado. Também verifica nome novo aceito
no fluxo normal, personalização nas etapas seguintes e retry sem novo envio.
Na etapa 8, cobre qualquer reação indo diretamente à 9, sem repetir a 8 nem
consumir aceite, para titular e dependente. Verifica saudação única, botões,
mapa obrigatório antes do envio, persistência da transição antes do reset e
recuperação de respostas antigas da 8 ou novas da 9 sem alterar outro ciclo.

`integration/test_followup_postgres.py` exige explicitamente FOLLOWUP_TEST_DSN com
host loopback e banco vazio chamado `test_chatbot_followup`. Ele cria e remove seu
próprio schema chatbot, recusando schema preexistente. Sem essa variável é pulado.
Executa DDL canônico, consultas reais, unicidade em histórico particionado, rollback,
fila sem vínculo e dois proprietários do lock. Nunca aponta para DB_HOST/DB_NAME.
Também executa o SQL integral de migração sobre uma base antiga descartável:
marca somente ativas, audita os valores anteriores, preserva os demais dados,
não produz histórico/envio, recusa reaplicação e reverte diante de legado terminal.
O retorno completo também usa fila e histórico reais nesse banco descartável:
rollback preserva stage positivo, etapa, efeitos e contadores. Respostas válidas
avançam e são salvas; repetição neutra ou tratamento específico preservam a etapa
e o contador na primeira reação. A transição válida zera os turnos sem avanço
junto da conclusão do follow-up, inclusive no retorno da 8 para a 9. Verifica histórico
do cliente e checkpoint na origem, resposta no destino e recuperação da mesma
reação sem reset de um ciclo posterior. Cobre tanto o lembrete
confirmado quanto o legado sem data de envio.
Meta permanece simulada; a confirmação de entrega real exige homologação manual.

`unit/test_retomada_followup.py` percorre os validadores e senders reais nas
rotas titular/dependente: avanço válido, repetição neutra, tratamentos específicos,
triagem, idade, confirmação do destinatário e contagem após o retorno. Confere
prefixo único e igualdade entre texto enviado e histórico, inclusive cabeçalhos.
Os testes de runtime verificam o commit único de efeitos, checkpoint,
encerramento e fila, com rollback quando a finalização falha. A inatividade
de três horas mantém o tratamento normal de contexto inválido.

## Consulta de faixa etária no painel

`unit/test_faixa_etaria_monitoramento.py` cobre a consulta personalizada do painel:
titular único em várias conversas, dependentes por cadastro (inclusive nomes
iguais), distribuição por titular, idade inclusiva e dados ausentes. Executa o
SQL real em SQLite descartável para validar unidade, contato no período,
fronteiras de data/hora e envio confirmado ao funil da pessoa atendida. Exercita
também sessão/autorização, parâmetros duplicados, público único e falhas da API.
Nenhum teste acessa a base de produção.

## Suporte por idade

`unit/test_suporte_por_idade.py` cobre as cinco configurações (desativado/50/60/70/80), fronteiras,
Admin, contato comercial, mensagem, recuperação com limite atual e contagem
real em SQLite dos encaminhamentos por unidade, data e motivo. As suítes de
e-mail, turno, follow-up, CSV e relatórios continuam como regressão.

`integration/test_suporte_por_idade_postgres.py` executa migração, domínio,
recusa de reaplicação, falha com rollback e DDL de instalação limpa. Também
verifica tabela ocupada, falha durante a reversão, preservação das conversas
e consultas reais de contexto/relatório no schema completo após a migração. Exige
`SUPORTE_IDADE_TEST_DSN`, host loopback e banco vazio `test_chatbot_suporte_idade`.
Recusa schema chatbot preexistente; não usa DB_HOST/DB_NAME. Sem a variável, é
pulado. Ver o [procedimento](../deploy/idade_minima_suporte.md) para homologação.


## Encerramentos por idade

`test_encerramentos_por_idade.py` cobre faixa compatível no retry, mensagem ligada
à recuperação, cortes de idade, BPA histórico, último chat, separação por unidade
e relatório de conversas na configuração atual. Inclui idade por extenso e com
`anos de idade`, além dos retornos de titular com 91 e dependente com 92 depois
de ativar suporte 80+: ambos conservam a categoria universal sem novo envio.
`test_encerramentos_por_idade_postgres.py`
exige `COMERCIAL_IDADE_TEST_DSN` em banco loopback vazio `test_chatbot_comercial`;
recusa qualquer schema chatbot preexistente. Nunca apontar testes para produção.

## Compatibilidade PyWa

`test_pywa_compatibilidade.py` usa a biblioteca instalada e `httpx.MockTransport`,
sem chamadas à Meta. Exercita os senders de oferta, encaminhamento comercial,
avaliação e follow-up, o prefixo, a versão configurada da Graph API, os IDs de
envio, bloqueio/desbloqueio e paginação. Rejeições HTTP, ausência de ID e timeout
precisam continuar chegando como falhas ao worker, sem reenvio automático HTTP.
Validado na atualização de PyWa 3.8.0 para 4.5.0.

## Consumo mensal Meta

`test_consumo_meta.py` cobre calendário (incluindo fevereiro bissexto), volumes,
saldo, cobertura ESL, identidade e decisão/prorrogação do dia 25.
`test_monitoramento_consumo.py` testa apresentação, ausência de primeira coleta,
autorização real do Django, isolamento por unidade, erro sem falso zero e PDFs.
Inclui a prévia de outubro durante setembro, a abertura à meia-noite no fuso da
unidade, rejeição/ocultação de meses futuros e ordenação de histórico de vários anos.
`test_consultar_franquia_meta.py` continua validando o contrato HTTP do utilitário.

`tests.integration.test_consumo_meta_postgres` exige `CONSUMO_META_TEST_DSN`,
loopback e banco `test_chatbot_consumo` sem schema chatbot. Valida o SQL real
reexecutado, upsert, rollback, concorrência, agenda persistida, duas unidades,
meses pendentes e mudança de fuso, com respostas Meta simuladas. Não usa produção.

## Reserva com e sem plataforma

`unit/test_fluxo_reserva_link.py` cobre as rotas de titular/dependente, o turno,
os botões comerciais, os efeitos de transição e o replay sem novo envio.
`integration/test_reserva_link_postgres.py` exige `RESERVA_LINK_TEST_DSN` em
loopback e banco vazio `test_chatbot_reserva_link`: executa DDL, SQL de Funil,
follow-up, preferências e isolamento do painel.

`integration/test_migracao_reserva_link_postgres.py` exige
`MIGRACAO_RESERVA_TEST_DSN`, loopback e banco vazio
`test_chatbot_migracao_reserva`. A fixture restaura o schema anterior com dados
fictícios, incluindo partições, satisfação, fila, checkpoints, Funil e Consumo.
Confere remapeamento, preservação dos demais campos, reexecução, reversão,
recusas atômicas e recuperação de resposta migrada. Ambas as suítes recusam
schema `chatbot` preexistente; nunca apontar suas DSNs para a base de aplicação.

Exemplo, depois de criar os dois bancos descartáveis no PostgreSQL local:

```powershell
$env:RESERVA_LINK_TEST_DSN = 'host=127.0.0.1 dbname=test_chatbot_reserva_link user=postgres'
$env:MIGRACAO_RESERVA_TEST_DSN = 'host=127.0.0.1 dbname=test_chatbot_migracao_reserva user=postgres'
python -m unittest tests.unit.test_fluxo_reserva_link tests.integration.test_reserva_link_postgres tests.integration.test_migracao_reserva_link_postgres -v
```

As demais suítes de integração precisam das próprias DSNs descritas acima.
Sem as variáveis, os testes PostgreSQL são ignorados, não considerados aprovados.

A configuração atual de `atendimento_customizado.link_agendamento`, lida diretamente junto de `unidade` por `id_unidade`, decide a saída da triagem: com link, 17 → 20; sem link, 17 → 18 (preferência de turno) → 19 (contato comercial). A satisfação converge em 21 → 22 → 23 → 24, com salto 22 → 24 na recusa de comentário. A FireAds pode importar as coletas iniciais e pular o e-mail apenas mediante consulta válida da própria conversa.

`conversa.turno` aceita NULL, manha, tarde ou noite e é salvo somente na transação de 18 → 19. É preferência, não confirmação de agendamento. Qualquer texto posterior na 19 apresenta a nota da 21; não é interpretado como nota nessa mesma interação. Mídia repete a orientação da 19.

O Funil exige 20–24 com link ou 19/21–24 sem link, considerando a configuração vigente na seleção, no claim e no snapshot. Preservar recibo de sucesso se o CRM já aceitou. O snapshot e o painel incluem turno da própria conversa, quando preenchido.

Follow-up proativo: 1–17 em ambas as rotas e 18 somente sem link; a 19 e a 20 não recebem novos lembretes. São preservadas as duas camadas de sete horas, os recibos, o encerramento no segundo lembrete e as guardas existentes. A reação ao primeiro segue a validação normal: um turno válido na 18 avança para 19 e é persistido. Contexto inválido genérico repete; tratamentos específicos continuam prioritários. Retomadas legadas são remapeadas por significado; a exceção 8 → 9 permanece.

Instalação existente exige migração própria: IDs antigos 18/19/20/21/22 tornam-se 20/21/22/23/24. Não executar setup ou seeds no banco de produção nem reaplicar migrações históricas. Preservar o Consumo Meta, seus fusos, worker, relatórios e PDFs, a compatibilidade PyWa 4.5.0, a exceção universal de idade 90+, o comentário livre e a despedida por participante.

## FireAds, chat e personalização da unidade

`unit/test_fireads.py` cobre importação, valores Google/Meta, comparação de datas,
e-mail importado da própria conversa, abertura na profissão, replay, tratamentos,
preservação das observações, e-mail de outro telefone e redirecionamento sem repetir POST.
Também verifica que um inline inválido da personalização impede o cadastro na Meta.

`unit/test_fireads_extratores.py` cobre nomes de perfil com complementos, catálogo
de compostos, fallback para a primeira palavra, e-mail sem revalidação estrutural,
campos vazios e destinatário desconhecido. A integração PostgreSQL cobre o registro
Meta, persistência da extração e retomada idempotente com o resultado salvo.

`unit/test_fireads_destino_dashboard.py` cobre a seleção da linha por telefone,
canal, destinatário explícito e maior `_row`, compatibilidade de snapshots antigos,
preservação dos demais campos, orgânicos e reconciliação antes de escolher outra
linha. HTTP e persistência são simulados. `unit/test_fireads_telefones.py` preserva
as máscaras e variantes do nono dígito também nessa seleção de destino.

`unit/test_fireads_espera.py` cobre o orçamento HTTP de 300 segundos entre abas
e redirecionamentos e a rejeição de resposta tardia. O runtime do flow verifica que
uma consulta pendente libera o ciclo para outro cliente sem envio prematuro.

`integration/test_fireads_postgres.py` exige FIREADS_TEST_DSN em loopback e banco
vazio test_chatbot_fireads. Executa ambas as migrações, valida preservação do legado,
reserva simultânea, recuperação após desconexão, descarte de resultado de tentativa
antiga, timeout, rollback da importação, aplicação única e todas as 24 etapas sem
reconsulta. Preserva também os testes de Funil/Dash, configuração, unidade suspensa,
relatórios e contexto histórico. Apenas fronteiras HTTP são simuladas.

```powershell
$env:FIREADS_TEST_DSN = 'host=127.0.0.1 dbname=test_chatbot_fireads user=postgres'
python -m unittest tests.unit.test_fireads tests.unit.test_fireads_espera tests.integration.test_fireads_postgres -v
```

As fronteiras HTTP continuam simuladas; não há POST para clientes ou CRM nesses
testes. A fixture `fixtures/fireads.py` compartilha o DDL do deploy com os testes
atuais de reserva e follow-up. Os testes de migrações históricas conservam seus
catálogos históricos, sem inserir os atalhos FireAds na versão anterior.

Validação da aplicação em 08/10/2026: **487 testes executados, zero falhas, zero
erros e zero pulados**, usando PostgreSQL 16 local descartável e as sete DSNs de
teste. Os binários locais de validação não são dependência do projeto ou da VM.


### Consultas diretas da unidade (09/10/2026)

O setup e as bases de teste não criam `unidade_atendimento`. As suítes FireAds,
reserva/link, suporte por idade e follow-up executam o SQL real sobre as duas
tabelas. Cobrem contexto de titular/dependente, alteração da personalização,
isolamento entre unidades, elegibilidade com/sem link, preservação da suspensão
por pagamento, painel e relatórios semanal/total (incluindo unidades sem histórico).
A migração de remoção pode ser reexecutada; a migração FireAds não recria a view.
SQL dos serviços permanece em `core/repositories`; SQL dos relatórios utilitários
permanece em `utilitarios/reports_functions`.
