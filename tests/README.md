# Testes do projeto

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
consolidação de perfis, 22 etapas, períodos comparáveis e os quatro downloads
CSV (Google e essencial, todos e elegíveis). Cobre todos os períodos, unidade
autorizada, revogação de acesso, acentos, campos vazios e proteção contra fórmulas
nos dados textuais. Seus payloads vivem em `fixtures/monitoramento_painel.py` e
são fictícios.
O teste distingue a remoção de `+55` no essencial da preservação do telefone
internacional no Google CSV; não remove o DDD nem altera os dados de origem.

## Follow-up

A segunda camada é coberta em `unit/test_followup.py` (redação por rota, nomes e
falha de envio) e `integration/test_followup_postgres.py` (7h contadas do primeiro
envio real, etapas 1–17 incluindo 8, guardas de silêncio/fila/janela, encerramento
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
