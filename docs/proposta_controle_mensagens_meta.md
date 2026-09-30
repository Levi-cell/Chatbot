# Plano de consumo mensal de mensagens da Meta

Revisão: 29/09/2026. Implementação autorizada e aplicada ao projeto: integração,
banco, worker, seção Consumo e PDFs. A migração de produção e a ativação do serviço
continuam sendo etapas do deploy. Procedimento e SQL em
[consumo_mensal_meta.md](../deploy/consumo_mensal_meta.md).

Nomes aprovados pelo usuário: **`worker_consumo_meta`**, tabela
**`consumo_mensal_meta`** e seção **Consumo**. As fronteiras mensais de calendário
também foram aprovadas. Regra definida nesta revisão: conferência de consolidação
no dia **25** do mês seguinte; se não aprovar, prorrogar para o dia 25 do mês
posterior, mantendo consultas diárias. A coluna `status_apuracao` tem **três
valores**: `em_andamento`, `em_conferencia` e `consolidado`; o nome da coluna não
é um quarto estado. O cadastro terá `id_fuso` (INTEGER) e `nome_fuso` (nome IANA),
ambos inicialmente nulos e sincronizados com a Meta. Os valores serão mostrados
discretamente no painel, conforme detalhado abaixo.

O plano anterior foi preservado integralmente em
[arquivo_pesquisa_meta_e_contador_emergencia.md](arquivo_pesquisa_meta_e_contador_emergencia.md).
Ele contém a alternativa de contador local e a investigação de faturas,
permissões, fusos e PyWa. Essas alternativas não fazem parte deste fluxo.

## 1. Objetivo e arquitetura

Acompanhar por unidade e mês-calendário os volumes classificados pela Meta,
consumo e saldo da franquia Meta, mensagens cobradas e cobertura da ESL Tech.
Usar `pricing_analytics` como fonte. Não contar envios nos workers de atendimento
nem interpretar `source_type` para reconstruir essas métricas.

Fluxo previsto:

1. `worker_consumo_meta` consulta as unidades sequencialmente.
2. Uma função de integração recebe WABA, número e mês e devolve as métricas.
3. O worker valida o resultado e grava em `chatbot.consumo_mensal_meta`.
4. A nova seção **Consumo** lê exclusivamente o banco por endpoints internos.
5. Os dois PDFs também são gerados a partir do banco da unidade autenticada.

Nenhuma chamada à Meta ocorre ao abrir o painel, trocar o mês ou baixar PDF.
O navegador atualiza a visualização ao entrar/retornar à seção, recarregar a
página, selecionar um mês e por atualização periódica enquanto Consumo estiver
visível. Em todos esses casos, consulta endpoints que leem o banco; não dispara
uma execução do worker. A agenda de coleta da Meta é independente da navegação.
O worker é um sincronizador de métricas: por isso `worker_consumo_meta` é mais
preciso que `worker_contador`. Ele não interfere no fluxo, no funil, nas janelas
de envio, nos bloqueios de clientes nem nos mecanismos de retry de mensagens.

## 2. Significado dos números e exemplo consolidado

Para mensagens individuais de serviço, a partir de 01/10/2026:

| Tipo na Meta | Informação local | Efeito |
| --- | --- | --- |
| `FREE_ENTRY_POINT` | `qtd_janela_gratuita` | Entregues dentro de janela gratuita elegível, separadas da franquia mensal. |
| `FREE_CUSTOMER_SERVICE` | `qtd_franquia_consumida` | Entregues usando a franquia gratuita do número. |
| `REGULAR` | `qtd_cobradas_meta` | Entregues e classificadas como faturáveis pela Meta. |

Exemplo solicitado: 3.000 + 750 + 0 = **3.750 mensagens entregues** na categoria
e no período consultados. As 3.000 e as 750 foram gratuitas para a unidade:
3.000 não consumiram a franquia; 750 consumiram a franquia de 1.000; restam 250.
Não descrever as 750 como pagas. `REGULAR=0` significa zero mensagens faturáveis
na categoria consultada, não uma declaração sobre toda a fatura da empresa.

Cálculos:

- `total_mensagens = qtd_janela_gratuita + qtd_franquia_consumida + qtd_cobradas_meta`.
- `franquia_restante = max(franquia_meta_mensal - qtd_franquia_consumida, 0)`.
- `qtd_assumidas_esl = min(qtd_cobradas_meta, beneficio_esl_mensal)`.
- `qtd_excedentes_unidade = max(qtd_cobradas_meta - beneficio_esl_mensal, 0)`.

Valores iniciais: franquia Meta de 1.000 e benefício ESL de outras 1.000 por mês.
A ESL cobre mensagens que a Meta classificou como cobradas; não cria outra
franquia na Meta. Exemplo: 3.000 pela janela + 1.000 pela franquia + 1.300
cobradas = 5.300 entregues; das 1.300 cobradas, 1.000 são assumidas pela ESL
e 300 ficam sob responsabilidade da unidade. Não somar novamente a parcela
ESL ou da unidade ao total de mensagens.

O recorte atual é `SERVICE`, individual, do número e WABA consultados. Não
somar clientes, conversas, mensagens recebidas, tentativas ou confirmações
HTTP de envio como se fossem entregas. Templates e outras categorias não
entram nesse recorte. Antes de outubro, `FREE_CUSTOMER_SERVICE` tem significado
anterior; não tratar os dados de setembro como consumo da nova franquia.

A franquia Meta pode ser compartilhada com serviço em grupos e outros envios
pelo mesmo número. Este plano pressupõe a cobertura do atendimento individual
da unidade; validar o uso exclusivo antes de anunciar saldo integral. Havendo
uso fora do recorte, ampliar a cobertura ou sinalizar a limitação, sem inventar
saldo exato. Volumes incompatíveis com a regra, como consumo maior que o limite,
exigem diagnóstico, sem transformar isso automaticamente em cobrança local.

## 3. Contrato da função e preparação realizada no utilitário

Arquivo atual: `utilitarios/consultas_franquia/consultar_franquia_meta.py`.

Consulta programática compartilhada com o worker:

```python
resultado = consultar_franquia_meta(
    waba_id,
    phone_number_id=phone_id,
    mes=None,  # mês atual da WABA; ou "2026-10" para reconciliação
)
```

Para uso manual na IDE:

```python
resultado = consultar_franquia(waba_id, phone_id, mes=None)
```

São necessários WABA e número: `pricing_analytics` é consultado na WABA,
enquanto o número restringe as métricas daquela unidade. O cadastro atual
`chatbot.unidade` já possui `waba_id` e `phone_number_id`; não adicionar consultas
ao banco dentro da integração só para esconder esse parâmetro. O campo usado
pelo filtro da Meta é o telefone, resolvido e validado pelo `phone_number_id`.

O token vem da configuração central, nunca é parâmetro por unidade nem coluna
da nova tabela. O atalho de IDE carrega o ambiente local. A função programática
usa o ambiente já carregado no processo e não deve chamar o bootstrap da IDE
por unidade, pois esse bootstrap limpa/reinstala variáveis da aplicação.

A consulta:

- Só realiza GET e retorna dados; não imprime, grava, espera ou agenda ciclos.
- Obtém `timezone_id` da WABA e resolve o fuso IANA brasileiro pelo mapa oficial.
- Rejeita ID de fuso ausente/desconhecido, WABA divergente ou número fora da WABA.
- Aceita `fuso_horario` opcional como conferência: divergência gera erro, não
  substituição silenciosa do fuso da Meta. Esse é um recurso de conferência
  manual do utilitário. **O worker não deve passar o fuso antigo da unidade
  nesse argumento**, pois impediria a sincronização automática aprovada.
  No caminho normal, omitir o argumento e usar a configuração atual da Meta.
- Retorna os três volumes, total entregue, consumo/saldo da franquia e divisão
  quantitativa ESL/unidade. A divisão é política local, não informação da Meta.
- Retorna mês, fuso, ID do fuso, início/fim fixos do mês, fim efetivo da consulta,
  instante da consulta, indicação de mês em andamento, categoria e avisos.
- Preserva valores nulos de franquia/benefício anteriores à vigência.
- Erro HTTP, permissão negada, JSON inválido, métricas incompletas ou paginação
  de métricas não suportada geram erro. Não geram um saldo gratuito de 1.000.
- Uma lista de métricas explicitamente vazia numa resposta válida representa
  zero observado naquele recorte; ainda pode sofrer atualização posterior da Meta.

No retorno, `data_hora_inicio` e `data_hora_fim` são as fronteiras fixas mensais;
`fim_exclusivo` é o fim efetivamente solicitado à API, limitado ao instante de
referência quando o mês ainda está aberto. Não confundir esses dois fins.

O worker carrega o ambiente uma vez, reutiliza uma sessão HTTP com timeout
finito e trata o erro por unidade. Não é necessário atualizar o PyWa para esse
GET feito com `requests`. As funções de faturas e de alteração de fuso não foram
incluídas no fluxo periódico e não devem ser executadas pelo worker.

Por decisão de manutenção aprovada, o projeto foi atualizado de PyWa 3.8.0 para
4.5.0 e a versão foi fixada em `requirements.txt`. A suíte existente e os testes
de contrato com o SDK real e HTTP simulado passaram sem alterar os senders.
A VM receberá a mesma versão na instalação das dependências durante o deploy;
essa atualização não muda a versão da Graph API configurada no ambiente nem
introduz uma migração SQL adicional.

## 4. Fuso e fronteiras do mês

O print de Santo Antônio de Jesus mostra **America/Bahia (GMT−03:00)**. O ID
206 já foi confirmado por GET nessa WABA; o portfólio não define este período.
Também é possível verificar o fuso por código sem alterar nenhuma configuração.

O Brasil tem quatro fusos: UTC−02, UTC−03, UTC−04 e UTC−05. Porto Velho, por
exemplo, usa UTC−04. Isso não obriga a WABA de Porto Velho a usar esse fuso:
para o recorte de consumo, vale a configuração efetiva da conta WhatsApp.
Se todas as WABAs estiverem configuradas em UTC−03, seus meses coincidirão.
Nunca presumir isso só porque a unidade fica no Brasil.

Definição aprovada para `chatbot.unidade`:

| Coluna | Tipo | Valor inicial | Origem |
| --- | --- | --- | --- |
| `id_fuso` | INTEGER NULL | NULL | Código `timezone_id` retornado pela Meta para a WABA. |
| `nome_fuso` | TEXT NULL | NULL | Nome IANA correspondente ao código, como `America/Sao_Paulo`, resolvido no mapa oficial. |

Esses nomes substituem a proposta anterior de `fuso_horario_unidade` e
`timezone_id_meta`; não criar colunas duplicadas com os nomes antigos. Manter
`fuso_verificado_em` como controle auxiliar da última verificação válida.
Usar a grafia `fuso` nos identificadores. O código não é um deslocamento UTC;
o nome IANA deve respeitar a escrita canônica, como `America/Sao_Paulo`.
A migração `20260929_consumo_mensal_meta.sql` cria as duas colunas como NULL,
sem preencher todas as unidades com um fuso presumido.

**A Meta é a fonte de verdade do cadastro de fuso.** O worker seguirá este fluxo:

1. Ler o `timezone_id` da WABA e validar a identidade da conta. A primeira leitura
   não depende de existir fuso no cadastro da unidade.
2. Converter o código válido para inteiro e resolver o nome IANA correspondente.
   A API/utilitário pode representar o ID como texto numérico; o banco o guarda
   como INTEGER. Não converter um código ausente ou desconhecido para zero.
3. Se `id_fuso` e `nome_fuso` forem NULL, preencher ambos na mesma atualização.
4. Se qualquer um divergir da configuração válida recebida da Meta, atualizar
   **os dois juntos**, automaticamente, e registrar a alteração. A configuração
   antiga da unidade não bloqueia a atualização nem prevalece sobre a Meta.
5. Se os dois coincidirem, preservar os valores e registrar a verificação válida.
   Atualizações concorrentes/atrasadas não podem fazer uma leitura antiga
   sobrescrever uma configuração mais recente.
6. Após resolver o fuso, determinar o mês atual da unidade e suas fronteiras.
   Nunca criar um mês usando fuso presumido enquanto o cadastro estiver nulo.

Preencher o par de forma atômica e validar que esteja inteiramente nulo ou
inteiramente preenchido. Se houver erro HTTP, código não mapeado ou resposta
inválida, preservar a configuração anterior (ou os dois NULL no primeiro acesso),
registrar a falha e tentar no próximo ciclo. Um ID novo exige atualização do mapa,
não adivinhação de um nome IANA nem troca automática para o fuso do servidor.

A sincronização válida do cadastro é independente do sucesso da consulta de
volumes. Na implementação do worker, separar a leitura/validação do fuso da
consulta de métricas: se a Meta confirmou o novo fuso e a consulta de volumes
falhou depois, o cadastro ainda pode refletir o fuso confirmado, sem marcar a
coleta de consumo como bem-sucedida. O utilitário atual reúne essas leituras;
a separação será feita na integração definitiva, sem duplicar consultas por mês
da mesma WABA dentro de um ciclo. `fuso_verificado_em` não substitui o horário
da última coleta válida de consumo mostrado no painel.

Usar `datetime.now(timezone.utc)` como instante e convertê-lo para `ZoneInfo`
da WABA. Evitar `datetime.now()` sem fuso. Banco armazena instantes em
`TIMESTAMPTZ`; interface e PDFs apresentam o fuso do registro. Não é necessário
que o sistema operacional, o portfólio e todas as unidades tenham o mesmo fuso.
Manter relógio do servidor sincronizado e não usar o horário do navegador.

Não é necessário converter todas as tabelas ou acrescentar fuso a cada mensagem.
No código atual, `populating_fila_mensagens.py` interpreta o timestamp da Meta
com `datetime.fromtimestamp(..., tz=timezone.utc)`, e o esquema usa `TIMESTAMPTZ`
nas datas da fila, do histórico e das conversas. Preservar esses instantes;
converter para o fuso desejado somente ao montar fronteiras ou apresentar datas.
Isso também serviria a um futuro contador, que permanece fora deste plano.

É possível obter o fuso atual por mensagem → conversa → unidade. Esse caminho
não recupera a configuração antiga se a unidade mudar de fuso: por isso cada
registro de consumo preserva o próprio fuso e as fronteiras do mês. Não alterar
as datas históricas nem os fusos de Conversas/Relatórios nesta implementação.

Exemplo para outubro de 2026 em America/Bahia:

- Início inclusivo: `2026-10-01T00:00:00-03:00`.
- Fim exclusivo fixo: `2026-11-01T00:00:00-03:00`.
- Uma coleta de 15/10 vai do início até o instante dessa coleta, não até o futuro.
- Uma coleta de outubro feita em novembro consulta o intervalo completo.

Cada mês tem 28, 29, 30 ou 31 dias. O seletor e o banco trabalham com meses de
calendário, nunca blocos fixos de 30 dias. Validar dezembro/janeiro, fevereiro
bissexto e instantes que são meses diferentes entre UTC−03 e UTC−04.

Na meia-noite exata o intervalo tem duração zero. O utilitário rejeita esse
recorte: o worker deve programar a primeira coleta após a virada (por exemplo,
00:01 no fuso da WABA), sem interpretar a ausência de intervalo como resposta
zero da Meta. Não precisa acertar um segundo específico para criar o mês.

Atualizar automaticamente o cadastro da unidade não reescreve o fuso e as
fronteiras dos registros mensais existentes, inclusive os ainda em conferência.
Novos registros usam o fuso vigente validado. Para um registro já existente,
não substituir seus totais por uma consulta calculada com fronteiras diferentes:
preservar o registro e sinalizar a necessidade de tratar esse período, mantendo
as demais unidades e os períodos compatíveis em processamento. A atualização
válida de `id_fuso`/`nome_fuso` na unidade ocorre mesmo nessa situação.

A mudança de fuso no meio do mês exige cuidado com o recorte e a franquia da
Meta; não criar dois saldos de 1.000 para a mesma unidade/mês nem misturar
contagens de intervalos diferentes. Uma eventual adequação de período histórico
precisa ser explícita e rastreável. O mesmo vale para troca de WABA ou número.
A consulta atual obtém o fuso vigente; ela não certifica retroativamente o fuso
usado meses atrás. Preservar essa distinção entre cadastro atual e histórico.

## 5. Tabela mensal proposta

Nome aprovado: **`chatbot.consumo_mensal_meta`**. Abrange gratuidade e cobrança,
enquanto `registro_mensagens_gratuitas` deixaria parte do conteúdo fora do nome.
Uma unidade tem vários meses; cada registro pertence a apenas uma unidade.

| Coluna | Responsabilidade |
| --- | --- |
| `id_registro` | Chave primária. |
| `id_unidade` | FK da unidade, sem exclusão em cascata do histórico financeiro. |
| `mes_referencia` | DATE no primeiro dia do mês; chave de identificação mensal. |
| `waba_id`, `phone_number_id` | Identidade da conta/número no período, preservada. |
| `timezone_id`, `fuso_horario` | Cópia do ID Meta e nome IANA usados no recorte mensal; preservada quando `unidade.id_fuso`/`nome_fuso` forem atualizados. |
| `data_hora_inicio`, `data_hora_fim` | TIMESTAMPTZ; fronteiras fixas, fim exclusivo. |
| `qtd_janela_gratuita` | BIGINT não negativo; `FREE_ENTRY_POINT`. |
| `qtd_franquia_consumida` | BIGINT não negativo; `FREE_CUSTOMER_SERVICE`. |
| `qtd_cobradas_meta` | BIGINT não negativo; `REGULAR`. |
| `franquia_meta_mensal` | Limite aplicado ao período, inicialmente 1.000. |
| `beneficio_esl_mensal` | Cobertura ESL aplicada ao período, inicialmente 1.000. |
| `consultado_ate` | Fim do intervalo realmente consultado à Meta. |
| `ultimo_sucesso_em` | Instante da última coleta válida, mesmo se os números não mudaram. |
| `ultima_tentativa_em` | Instante da tentativa mais recente. |
| `ultimo_erro`, `falhas_consecutivas` | Diagnóstico resumido sem credenciais/payload sensível. |
| `status_apuracao` | NOT NULL; `em_andamento`, `em_conferencia` ou `consolidado`, restritos por CHECK. Substitui `confirma`, conforme decisão aprovada. |
| `consolidado_em` | Instante da consolidação interna; nulo enquanto pendente. Não certifica fechamento pela Meta. |
| `data_proxima_consolidacao` | DATE no dia 25, interpretada no fuso preservado do registro; primeiro dia 25 do mês seguinte, prorrogável por meses de calendário. Nula após consolidar. |
| `ultima_decisao_consolidacao_em` | Instante da decisão na data prevista, para rastrear aprovação/prorrogação e impedir repetição indevida. |
| `verificado_em`, `proxima_verificacao_em` | Controle persistido da reconciliação de meses antigos. |
| `criado_em`, `atualizado_em` | Auditoria do registro. |

Usar unicidade **`(id_unidade, mes_referencia)`** e `INSERT ... ON CONFLICT`.
Não procurar simplesmente o último registro: a tarefa pode consultar outubro
enquanto já existe dezembro. A chave sempre inclui o mês da consulta.
Comparar também identidade e fronteiras na atualização; divergências não são
corrigidas trocando silenciosamente essas colunas. Trocas de número no meio de
um mês ficam bloqueadas para tratamento explícito, não consolidadas em duplicata.

As quantidades substituem os totais anteriores: a API devolve o acumulado.
Nunca fazer `valor += retorno_meta`. Correções para menos também devem ser
aceitas e registradas. Derivar totais, saldo e divisão ESL/unidade dos valores
persistidos; não manter várias colunas derivadas que possam divergir.

Criar o registro com a primeira consulta válida. Se falhar antes de existir
registro, exibir indisponibilidade; não inventar zero. Para permitir diagnóstico
dessas primeiras falhas, o worker precisará de controle de coleta por unidade
(em tabela auxiliar ou mecanismo persistente equivalente) além dos logs. Essa
informação não pode depender de existir o registro mensal de sucesso.

Os limites gravados por mês permitem mudança comercial futura sem recalcular
a cobertura ESL de meses antigos por uma configuração nova.

Separar `proxima_verificacao_em` (consulta diária) de
`data_proxima_consolidacao` (decisão mensal). Atualizar o total de uma consulta
diária não altera por si só a data de consolidação. Na criação de registros
antigos recuperados após indisponibilidade, usar `em_conferencia` e a próxima
data de decisão admissível; não criar `em_andamento` por padrão para meses passados.
Manter coerência entre status, data de decisão e `consolidado_em` por validação
de domínio e constraints adequadas na implementação.

## 6. Agenda, ciclo e falhas do worker

Recomendação: **uma coleta por hora para o mês atual**. Uma vez por dia deixa
o saldo apresentado ao franqueado desatualizado por tempo demais. A interface
mostra o horário da última coleta e não promete dados instantâneos da Meta.

Um processo com `while` controla a agenda e um `for` percorre as unidades.
A mesma execução atende a coleta atual e a reconciliação diária de meses antigos;
não é necessário outro worker. Intervalos configuráveis, timeout finito,
espera interrompível, encerramento gracioso e logs no padrão do projeto.

Ciclo proposto:

1. Buscar unidades elegíveis com `id_unidade`, `waba_id`, `phone_number_id` e
   `id_fuso`/`nome_fuso`, admitindo ambos NULL inicialmente.
2. Consultar o fuso atual da WABA, sincronizar o par de colunas quando necessário
   e então determinar o mês local e o trabalho devido. Meses já existentes
   conservam as fronteiras e o fuso gravados no registro.
3. Executar a consulta fora de uma transação longa do banco.
4. Validar conta, número, período, tipos e quantidades da resposta completa.
5. Em transação curta, inserir/atualizar o mês e registrar sucesso.
6. Consultar os meses anteriores cuja verificação esteja vencida.
7. Se uma unidade/mês falhar, registrar falha, preservar os últimos dados
   válidos e seguir para a próxima. Tentar de novo no ciclo devido, sem loop
   imediato de retry da mesma conta e sem bloquear as demais unidades.

É possível um período falhar e outro ter sucesso; não sobrescrever o diagnóstico
específico do período que falhou. Consultas do mês atual têm prioridade sobre
reconciliações e preenchimento histórico. Limitar trabalho por ciclo e respeitar
limites de uso/429 da Meta, sem consultar em paralelo todas as unidades.

A agenda precisa sobreviver ao reinício: usar horários persistidos, não somente
um `sleep(3600)` como garantia. Impedir ciclos simultâneos por lock próprio do
worker no banco; se houver múltiplos processos, nenhum deve gravar um resultado
mais antigo sobre outro mais recente. O upsert deve rejeitar coleta atrasada.
Não usar nem modificar os locks das conversas para essa finalidade.

Uma falha não se identifica por números que ficaram iguais: ausência de tráfego
pode produzir métricas idênticas por vários dias. Comparar `ultimo_sucesso_em`,
estado da coleta e erro. Mostrar “Atualizado às …” para sucesso sem mudança e
“Não foi possível atualizar; exibindo dados de …” quando houver falha.

Na virada do mês, criar o novo registro quando houver resposta válida e preservar
o anterior. Se o processo ficar indisponível durante uma virada, recuperar os
meses ausentes desde o início de acompanhamento da unidade (nunca antes de
outubro/2026 para esta franquia), dentro da janela histórica admitida pela API.
Meses fora dessa janela ficam com diagnóstico explícito, não zero ou confirmados.

A seleção não deve reutilizar cegamente `pegar_unidades`, que hoje retorna apenas
phone/id e filtra `status_pagamento`. Criar consulta própria; meses pendentes de
unidades inativas continuam elegíveis à reconciliação enquanto houver acesso
válido e obrigação de acompanhamento. Perda de acesso gera estado de bloqueio
de coleta, preservando o histórico e sem tentar contornar permissões.

## 7. Conferência diária e consolidação somente no dia 25

Regra definida pelo usuário: cada mês tem uma primeira data de decisão no
**dia 25 do mês seguinte**. Se não passar na conferência dessa data, adiar a
decisão para o **dia 25 do mês posterior**, mantendo a coleta diária durante
toda a prorrogação. Uma igualdade no dia 26 não antecipa a nova data.

Exemplo: outubro tenta consolidar em 25/11. Se houver divergência ou falha,
o próximo prazo será 25/12; em dezembro, outubro e novembro serão consultados
diariamente e avaliados individualmente no dia 25. Dezembro seguirá com coleta
horária e terá a primeira decisão em 25/01. Os prazos seguem o fuso preservado
em cada registro e meses de calendário, nunca somas fixas de 30 dias.

O dia 25 é uma regra interna da ESL. A hipótese de prazos comerciais em múltiplos
de cinco dias não é uma regra técnica da Meta. Consolidado significa que a
conferência interna foi cumprida; não transforma analytics em fatura definitiva.

Estados aprovados — são três valores na coluna `status_apuracao`:

| Valor | Quando é usado | Agenda |
| --- | --- | --- |
| `em_andamento` | O mês de referência ainda está em curso, desde a primeira coleta válida. | Coleta horária. |
| `em_conferencia` | O mês terminou e ainda não passou na decisão do dia 25, inclusive se houve prorrogação. | Coleta diária até aprovar em uma data prevista. |
| `consolidado` | A consulta válida na data prevista do dia 25 coincidiu com a coleta diária válida anterior do mesmo mês. | Encerrar consultas automáticas desse mês. |

`status_apuracao` é o nome da coluna, não um quarto valor. Falha da API fica nos
campos próprios de diagnóstico; não acrescentar `erro` como estado da apuração.
Esta definição foi implementada no domínio, worker e constraints da migração SQL.

Fluxo definido:

1. Na primeira coleta do mês atual, criar `em_andamento` e programar a decisão
   para o dia 25 do mês seguinte. Na virada do mês, passar a `em_conferencia`,
   independentemente de a próxima consulta da Meta ter sucesso. O serviço de
   leitura deve apresentar mês encerrado como em conferência mesmo se o worker
   estiver temporariamente parado e ainda não tiver persistido essa transição;
   isso não consolida o mês, altera quantidades ou faz chamada à Meta.
2. Consultar o mês encerrado uma vez por dia, sempre com o intervalo completo.
   A primeira leitura completa é a referência inicial; não compará-la a uma
   leitura parcial das 23h do último dia como se fossem recortes iguais.
3. Antes da data de decisão, atualizar os totais válidos e manter
   `em_conferencia`, independentemente de os números coincidirem ou divergirem.
4. No dia 25 previsto, comparar a leitura válida com a **coleta diária válida
   anterior**, de data local anterior, para o mesmo mês. Em condições normais,
   são as leituras dos dias 24 e 25. Elas devem cobrir a mesma conta, número,
   fuso, fronteiras e categoria. Comparar os três volumes individualmente:
   reclassificar gratuidade/cobrança pode manter o total sem manter os tipos.
   A comparação entre dias distintos evita depender de exatamente 24 horas
   entre requisições, que podem variar alguns segundos durante o ciclo.
5. Se coincidirem, gravar os totais e `consolidado`, preencher `consolidado_em`,
   registrar a decisão e retirar o mês das consultas automáticas. A igualdade
   deve ser calculada contra os valores anteriores **antes** de substituí-los.
6. Se divergirem, gravar os novos totais da Meta, inclusive correções para menos,
   manter `em_conferencia` e mudar `data_proxima_consolidacao` para o dia 25 do
   mês seguinte. A coleta diária continua no dia 26, mas só a nova data permite
   consolidar. Nunca trocar `mes_referencia` nem as fronteiras de outubro por
   novembro/dezembro só porque o prazo foi prorrogado.
7. Se a consulta do dia 25 falhar, faltar leitura anterior comparável ou a
   identidade/período não for válido, preservar os dados anteriores e prorrogar
   a decisão da mesma forma. Registrar a causa; erro não é zero nem igualdade.
   Se o processo perder completamente o dia 25, recuperar a agenda no reinício
   e programar o próximo dia 25 futuro, sem consolidar retroativamente no dia 26.
8. A consulta diária prevista no dia 25 também serve à decisão, sem uma segunda
   chamada só para confirmar. Persistir dados e decisão atomicamente, com
   proteção contra concorrência. Impedir que outro ciclo no mesmo dia reverta
   uma prorrogação já registrada ou compare a resposta com ela mesma.
9. Selecionar **todos** os registros `em_conferencia` com consulta devida, não
   apenas o mês imediatamente anterior. Cada unidade/mês tem uma decisão
   independente: outubro pode consolidar e novembro prorrogar, ou vice-versa.

Programar a consulta diária em horário com margem dentro do dia local (por
exemplo, pela manhã), evitando depender de execução nos segundos finais do dia
25. A agenda e a data de decisão precisam sobreviver ao reinício do processo.
Dados que cheguem apenas depois do dia previsto não aprovam retroativamente.

Cenário de referência:

| Data | Outubro | Novembro | Dezembro |
| --- | --- | --- | --- |
| 25/11: outubro divergiu | Atualiza os números, segue em conferência; nova decisão em 25/12. | Em andamento, coleta horária. | Ainda não iniciado. |
| 26/11: outubro ficou igual | Continua em conferência e com coleta diária. | Em andamento. | Ainda não iniciado. |
| 01/12 a 24/12 | Em conferência, coleta diária. | Em conferência, coleta diária; primeira decisão em 25/12. | Em andamento, coleta horária. |
| 25/12: ambos coincidem com suas respectivas leituras anteriores | Consolidado; sai das consultas automáticas. | Consolidado; sai das consultas automáticas. | Em andamento. |
| Alternativa em 25/12: só outubro diverge | Atualiza e prorroga para 25/01. | Consolida se a própria conferência passar. | Em andamento. |

A auditoria semanal sugerida anteriormente **não faz parte do fluxo definido**:
o usuário escolheu prazo mensal com prorrogação. Uma eventual revisão manual
posterior deve preservar a trilha do dado anterior e a data da correção. Mudanças
posteriores da Meta não serão detectadas automaticamente após a consolidação.
O utilitário apenas consulta dados; agendamento, status e persistência pertencem
ao worker e aos repositórios.

## 8. Nova seção Consumo: conteúdo e comportamento

Adicionar **Consumo** ao lado de **Conversas** e **Relatórios**. Preservar identidade
visual, espaçamentos, tipografia, cores e componentes do painel. Não colocar as
métricas mensais dentro do seletor livre de períodos das outras duas seções.
O público são os franqueados Supera. Usar rótulos em português, valores legíveis
e explicações breves; nomes de campos da API, IDs e erros técnicos ficam no
diagnóstico interno. Os dados e sua compreensão têm prioridade sobre decoração.

Seletor próprio de mês, servido pelo banco da unidade:

- Ordem decrescente, mês atual sempre primeiro, mesmo antes da primeira coleta.
  Somente meses anteriores com registro da unidade entram no histórico. Meses
  futuros não aparecem e são rejeitados também no endpoint e no PDF.
- Exceção antes de outubro/2026: oferecer apenas “Out · 2026”, sem rotular como
  mês atual, com “Disponível apenas dia primeiro de outubro.”. Não mostrar saldos
  nem habilitar PDFs. A prévia funciona mesmo antes de o worker preencher o fuso.
- O calendário de navegação usa o fuso da unidade. Enquanto ele estiver NULL,
  usa America/Sao_Paulo somente para navegação, sem gravá-lo no cadastro nem
  presumir recortes ou métricas. As coletas continuam exigindo o fuso da Meta.
- Rótulos: “Dez · 2026 — mês atual”, “Nov · 2026”, “Out · 2026”.
- Controle nativo com seta e lista de meses organizada, operável por toque e
  teclado. Históricos longos usam a rolagem do seletor no navegador/sistema;
  não expandir todos os meses na página nem truncar anos antigos. Não é necessário
  acrescentar paginação. A seleção automática acompanha a virada do mês, enquanto
  uma escolha histórica explícita permanece no período escolhido.
- Manter um único seletor. Quando houver meses de mais de um ano, agrupá-los
  por ano dentro da própria lista, do mais recente ao mais antigo. Com apenas
  um ano, exibir a lista simples. Um filtro independente por ano pode ser
  considerado futuramente, conforme o tamanho do histórico e a necessidade real.
- Cada opção corresponde a fronteiras mensais exatas, não a 30 dias.
- Se o mês atual ainda não tiver coleta válida, apresentar “Aguardando primeira
  atualização” de forma distinta do zero, sem rotular o mês anterior como atual.
- Somente meses da unidade autenticada; não consultar a Meta para preencher a lista.
- Exibir abaixo do seletor datas inclusiva/exclusiva de maneira compreensível,
  fuso usado, horário de atualização e estado (“Em andamento”, “Em conferência”
  ou “Consolidado”). No detalhe de consolidado, explicar que é conferência interna
  da ESL, sujeita a revisão da Meta. Não usar “Fatura fechada” ou “Confirmado pela Meta”.

Conteúdo proposto:

1. Três cartões principais: **Gratuitas pela janela**, **Franquia Meta restante**
   (“250 de 1.000; 750 utilizadas”) e **Cobradas pela Meta**.
2. No cartão de cobradas, separar **Assumidas pela ESL Tech** e **Excedentes da
   unidade**, para que o cliente não pense que pagará as primeiras 1.000 cobradas.
3. Total de entregas no mês e barra simples de consumo da franquia, com valores
   escritos, sem depender apenas de cor e sem números negativos.
4. Gráfico empilhado ou barras horizontais dos três grupos exclusivos de entrega
   e tabela textual equivalente. Não duplicar a cobertura ESL como quarta
   categoria somável. Para poucos dados, priorizar clareza sobre excesso de gráficos.
5. Tabela histórica por mês com janela, franquia usada/restante, cobradas Meta,
   parcela ESL, excedente da unidade, atualização e estado.
6. Explicações em botão “i”/bloco expansível discreto e acessível por toque,
   teclado e leitor de tela; não depender só de passar o mouse.
7. Botões separados **Baixar PDF deste mês** e **Baixar PDF de todos os meses**.
8. Valores monetários discretos junto ao excedente, com tarifa de referência,
   moeda, vigência e aviso de alteração pela Meta, conforme seção 10. Mostrar
   claramente a parcela coberta pela ESL e a que poderá caber à unidade.

Textos explicativos propostos, sujeitos à revisão editorial final:

- **Janela gratuita:** “Mensagens que a Meta classificou como gratuitas por uma
  entrada elegível, como anúncios de clique para WhatsApp. Elas não consomem
  a franquia mensal.”
- No detalhe: a documentação consultada descreve 72 horas a partir da resposta
  à entrada elegível, quando a resposta ocorre em até 24 horas. Também inclui
  botões elegíveis de Páginas do Facebook; não afirmar “somente anúncios”.
  Mensagens comuns não estendem essa janela automaticamente. Uma nova entrada
  elegível futura não deve ser excluída por ser cliente antigo. O painel não
  calcula a janela: utiliza a classificação da Meta. Não afirmar sete dias sem
  confirmação oficial nem confundir janela de gratuidade com permissão de envio.
- **Franquia mensal Meta:** “1.000 mensagens de serviço gratuitas por número a
  cada mês, usadas fora da janela gratuita. O saldo não acumula para o mês seguinte.”
- **Cobertura ESL Tech:** “Quando a franquia da Meta termina, a ESL Tech assume
  as primeiras 1.000 mensagens de serviço cobradas no mês. Apenas o excedente
  fica sob responsabilidade da unidade, conforme as condições do serviço.”
- **Atualização:** “Dados consultados periodicamente na Meta, sujeitos a revisão.”

Responsividade: navegação com três opções sem cortar textos no celular; cartões
empilhados em telas pequenas; seletor com foco e rolagem acessíveis; tabelas com
rolagem contida no componente; PDF/ações em botões empilháveis; nada deve causar
rolagem horizontal na página inteira. Preservar estado e período próprios de
cada seção: os seletores existentes usam `[data-periodo]`, que não deve passar
a controlar o seletor de meses da seção nova.

Tratar carregamento, unidade sem meses, consulta indisponível, dados antigos,
zero legítimo e troca rápida de mês. Descartar resposta atrasada do mês anterior
se o usuário já selecionou outro. Escapar nomes e conteúdo variável no frontend.

### 8.1. Atualização da tela a partir do banco

- Carregar meses disponíveis e dados ao entrar em Consumo, ao retornar de outra
  seção, ao abrir/recarregar a página nessa seção e ao selecionar outro mês.
  Escolher o mês atual inicialmente; se ainda sem dados, mostrar a espera e
  permitir consultar o histórico, sem disfarçar o último mês como atual.
- Enquanto Consumo estiver selecionado e a página estiver visível, consultar
  o banco periodicamente. Usar inicialmente **30 segundos**, seguindo a cadência
  atual de Relatórios. Isso não muda a coleta horária/diária do worker na Meta.
- Ao voltar à aba do navegador (`visibilitychange`), atualizar a seção ativa.
  Suspender consultas periódicas de Consumo quando ela estiver oculta. Evitar
  requisições sobrepostas, descartar respostas antigas e não perder o mês
  selecionado, foco, rolagem ou controles abertos na atualização silenciosa.
- Atualizar a lista de meses na virada sem trocar à força o mês que o cliente
  está consultando. A primeira entrada usa o mês atual; um retorno preserva a
  seleção da sessão enquanto ela continuar válida para a unidade autenticada.
- Exibir a **última coleta válida da Meta** (`ultimo_sucesso_em`) junto aos
  indicadores. Reconsultar o banco às 15h não faz os dados coletados às 14h
  passarem a constar como coletados às 15h. A resposta do endpoint e o instante
  de coleta são informações distintas.
- Se a atualização do navegador falhar, manter os dados visíveis e informar a
  dificuldade discretamente; se a coleta do worker falhar, mostrar a data do
  último sucesso e o aviso correspondente. Não limpar cartões para zero.
- Proteger endpoints e PDFs pela unidade autenticada. Resolver a unidade no
  servidor; parâmetros de mês não podem permitir acesso aos dados de outra.
  Configurar respostas privadas e sem cache compartilhado entre unidades.

Ponto concreto identificado no frontend atual: `trocar(secao)` e o evento de
visibilidade de `painel.js` fazem escolhas entre apenas duas seções. Na aplicação,
substituir essas decisões por tratamento explícito de Conversas, Relatórios e
Consumo, inclusive ao ocultar/exibir os contêineres e atualizar o indicador do
cabeçalho. Não deixar Consumo cair automaticamente no carregamento de Relatórios
ou de Conversas. Preservar a cadência e o comportamento existentes dessas seções.

## 9. PDFs previstos

Gerar PDF no servidor com os mesmos dados e cálculos da seção, sem requisição
à Meta. Consultas protegidas pela mesma autenticação e isolamento de unidade
do painel. Os relatórios são de **consumo**, não notas fiscais nem faturas Meta.

**PDF do mês:** marca ESL, unidade, mês, fronteiras, fuso, atualização, estado,
resumo dos três volumes, saldo da franquia, divisão ESL/unidade e explicações
curtas. Mês atual tem indicador “Em andamento”; histórico pode indicar revisão.
O botão do mês usa exatamente o mês selecionado e o identifica no arquivo e
no conteúdo. Os dois botões mostram progresso, evitam cliques duplicados e
explicam falhas sem desmontar a tela. Sem dados válidos, não gerar um relatório
preenchido artificialmente com zeros. Consultar o banco novamente para gerar o
PDF; se houve nova coleta desde a tela, a data no documento identifica essa versão.

**PDF de todos os meses:** capa/cabeçalho compacto, resumo do intervalo disponível
e tabela cronológica legível com todos os meses persistidos da unidade. Incluir
o mês atual como parcial e não somar franquias restantes de meses diferentes
como um saldo que possa ser usado hoje. Quebras de página corretas, cabeçalho
repetido da tabela, paginação, margens e rodapé com emissão/atualização.

Manter acentos e fontes incorporadas, contraste, números alinhados e logotipo
oficial existente. Nenhum número de cliente, token ou dado pessoal de conversas
é necessário. Usar uma leitura consistente do banco para que cartões e totais
do mesmo PDF não sejam montados com versões diferentes de uma coleta.

PDF implementado com ReportLab e o SVG oficial convertido por svglib, fontes
incorporadas e geração em memória. Exemplos de uma e várias páginas foram
gerados com dados fictícios para revisão visual, fora dos arquivos da aplicação.

## 10. Tarifa por mensagem e comunicação comercial

Escolha aprovada: mostrar a tarifa do excedente com transparência, de maneira
discreta e contextualizada, informando que pode mudar por decisão da Meta.
Destacar primeiro a cobertura e quanto efetivamente
cabe à unidade. O preço do serviço ESL não é apenas o custo da mensagem: inclui
software, operação, atendimento e manutenção. Não esconder tarifa para fazer a
cobertura de 1.000 mensagens parecer financeiramente maior.

**Tarifa confirmada em 29/09/2026:** a tabela oficial em BRL com vigência em
**01/10/2026**, disponibilizada pela Meta na seção de tarifas de outubro, traz
para a linha `Brazil` e coluna `Service` o valor **0,035 BRL** por mensagem.
São **R$ 0,035 = 3,5 centavos**, não 0,035 centavo. A tabela de julho também tem
0,035 para outras categorias, mas a validação desta decisão usou especificamente
o campo de serviço da tabela de outubro.

Essa é a tarifa publicada para o mercado brasileiro na tabela em reais. Não
deduzir que toda WABA é faturada em BRL só por operar no Brasil, nem aplicar o
mesmo preço a destinatários de outros mercados ou outras categorias. Conferir
a moeda efetiva da conta e as condições aplicáveis antes de exibir um valor
financeiro específico da unidade. O utilitário atual consulta volumes, não COST,
e não estabelece a moeda de faturamento por meio do fuso da WABA.

Exemplos aritméticos nessa tarifa, antes de eventuais ajustes/impostos:

- 50 mensagens cobradas pela Meta: R$ 1,75, integralmente cobertas pela ESL.
- 400 mensagens cobradas pela Meta: R$ 14,00, integralmente cobertas pela ESL.
- 1.000 mensagens cobradas pela Meta: R$ 35,00, integralmente cobertas pela ESL.
- 1.300 mensagens cobradas: 1.000 cobertas pela ESL (R$ 35,00) e 300 excedentes
  da unidade (R$ 10,50), nessas mesmas condições.

A expectativa de 50 a 400 mensagens cobradas por unidade/mês é uma hipótese
comercial do usuário, não uma projeção validada pelo histórico. A cobertura de
até 1.000 funciona independentemente dessa expectativa; acompanhar os primeiros
meses com a nova regra para verificar frequência e custo agregado das unidades.

Texto de referência junto ao excedente, quando aplicável à conta: “Tarifa de
referência: R$ 0,035 por mensagem de serviço para o Brasil. Vigência: 01/10/2026.
Sujeita a alterações pela Meta.” Exibir separadamente a parcela já coberta pela ESL.

Antes de calcular valor no painel/PDF, definir fonte da tarifa, moeda, política
ESL de repasse, arredondamento e eventuais impostos. Usar Decimal e guardar
vigência; não recalcular preços passados com tarifa nova. Até validar isso,
mostrar quantidades e cobertura, sem inventar valor a pagar ou tratar analytics
como fatura definitiva. A utilidade atual não calcula valores monetários.

O print enviado também informa “Nenhuma forma de pagamento encontrada”. Verificar
a situação efetiva de faturamento da WABA antes de depender de entregas após
esgotar a franquia. A concessão comercial da ESL não configura pagamento na Meta;
o worker de métricas não deve cadastrar ou alterar formas de pagamento.

## 11. Responsabilidades e arquivos da aplicação

- Integração de leitura: extrair o núcleo preparado em `utilitarios/consultas_franquia/`
  para módulo de `core/integrations/whatsapp/` na aplicação definitiva; o atalho
  manual poderá delegar a ele. Não fazer workers dependerem do bootstrap de IDE.
- `workers/worker_consumo_meta/`: configuração, agenda/ciclo e reconciliação em
  módulos pequenos, com iniciador no padrão dos workers existentes.
- `core/repositories/`: consultas de unidades aptas, upsert, seleção de pendências,
  controle de coleta e leitura para o painel em repositórios dedicados.
- `core/database/deploy_database/bank_script.py` e `deploy/migrations/`: esquema
  inicial e SQL transacional versionado; rollback e procedimento de deploy.
- `callback/webhook/models.py`: modelos de leitura/admin conforme o padrão atual.
- `callback/monitoramento/`: serviço de consumo, endpoints autenticados, montagem
  de respostas e geração dos dois relatórios PDF.
- Template, CSS e JavaScript existentes do painel: terceira seção e componentes
  isolados, sem alterar seletores e cálculos de Conversas/Relatórios.
- Configuração de deploy/systemd, dependências se necessárias e documentação de
  operação, falhas e significado dos estados.

SQL preparado em `deploy/migrations/20260929_consumo_mensal_meta.sql`. Nenhum
serviço ou banco produtivo foi alterado pela implementação local.

## 12. Verificações antes de aplicar

- Exemplo 3.750/250, divisão das 1.300 cobradas e ausência de dupla contagem.
- Fuso real da WABA: primeiro preenchimento de `id_fuso`/`nome_fuso` nulos,
  conversão de código textual para inteiro e atualização atômica dos dois campos
  quando a Meta divergir do cadastro. Validar correção de nome inconsistente
  mesmo se o ID não mudou, e preservação dos registros mensais anteriores.
- ID desconhecido/erro não apaga fuso conhecido nem inventa padrão. Fuso validado
  pode ser sincronizado mesmo se os volumes falharem; isso não altera o horário
  da última coleta bem-sucedida de consumo. Leituras atrasadas não regridem o cadastro.
- Conferência manual de fuso no utilitário continua rejeitando divergência;
  o worker não usa esse argumento para fixar o cadastro antigo. Validar outra
  WABA, número fora da conta, fronteiras de mês/ano/fevereiro e meia-noite exata.
- Uma unidade falha e as demais continuam; erro não vira zero nem sucesso.
- Reinício, inserção repetida, duas execuções concorrentes e resultado antigo
  chegando depois de um novo não duplicam ou regridem indevidamente a coleta.
- Upsert substitui acumulados e aceita correções; não soma a cada hora.
- Primeira leitura completa não compara com leitura parcial; igualdade antes
  do dia 25 não consolida. Divergência/erro no dia 25 prorroga para o próximo
  dia 25; igualdade no dia 26 não antecipa a decisão. Testar dezembro/janeiro,
  fevereiro e o fuso preservado, não o relógio local do servidor.
- Comparar valores anteriores antes do upsert; detectar reclassificação entre
  tipos mesmo sem alteração do total. Duas execuções no dia 25 não revertem
  uma prorrogação nem comparam a leitura com ela mesma.
- Outubro e novembro pendentes em dezembro têm consultas e decisões independentes;
  processo parado no dia 25 reagenda sem consolidação retroativa. Recuperar meses
  perdidos dentro do período permitido pela API e excluir consolidados da agenda.
- Limites mensais preservados; troca de identidade ou fuso não reescreve passado.
- Autorização: unidade A não lê dados nem PDFs de B manipulando IDs ou URLs.
- Interface em celular e desktop, estados vazios/erro, teclado, seletor de meses,
  interação com seletores antigos e resposta fora de ordem; conferir entrada,
  retorno, recarga, troca de mês, atualização a cada 30 segundos e aba oculta.
  Atualização silenciosa preserva seleção/foco e não altera a data da coleta Meta.
- Verificar navegação com três seções e isolamento de seus carregamentos; nenhuma
  visita, troca de mês ou download pode chamar a Meta ou disparar o worker.
- PDFs de um mês e histórico longo, valores coerentes, tabelas e paginação legíveis.
  Testar os dois botões, mês selecionado correto, espera, falha e ausência de dados.
- Primeira consulta real de outubro: confirmar classificação e fronteiras dos
  dados no WABA antes de apresentar os números como consumo da nova franquia.

Validação já realizada nesta etapa: 35 testes do utilitário passaram. Uma
consulta real somente de leitura em 29/09/2026 confirmou automaticamente
`timezone_id=206`, `America/Bahia`, na WABA de Santo Antônio de Jesus. O retorno
de setembro foi 526 pela janela, 56 na classificação gratuita anterior e zero
faturáveis, totalizando 582 entregas no recorte. Franquia e cobertura ESL ficaram
nulas por ser setembro; esse ensaio não valida ainda a classificação de outubro.

Esses testes reduzem riscos; não constituem promessa de ausência de qualquer bug
nem de igualdade garantida entre analytics e o fechamento financeiro da Meta.

## 13. Fontes e pontos de alinhamento

Referências oficiais consultadas:

- [Analytics e classificação a partir de outubro](https://developers.facebook.com/documentation/business-messaging/whatsapp/analytics?locale=pt_BR).
- [Preços, franquia e entradas gratuitas](https://developers.facebook.com/documentation/business-messaging/whatsapp/pricing?locale=pt_BR).
- [IDs de fusos Meta](https://developers.facebook.com/docs/marketing-api/reference/ad-account/timezone-ids/).
- [Fusos horários — Observatório Nacional](https://www.gov.br/observatorio/pt-br/assuntos/areas-de-atuacao/tempo-e-frequencia/fusos-horarios).

A descrição com vigência em outubro foi verificada na documentação `pt_BR`;
a representação sem idioma consultada anteriormente ainda tinha trechos antigos.

Antes da implementação completa, alinhar principalmente:

1. A tarifa brasileira de serviço em BRL foi confirmada; conferir moeda efetiva
   das contas, mercados atendidos e condições comerciais antes de calcular repasse.
2. Validar cobertura de uso do número e faturamento ativo para o excedente.

Os nomes do worker, da tabela e da seção Consumo estão aprovados, assim como as
fronteiras mensais, o dia 25 com prorrogação mensal, os três estados,
`id_fuso`/`nome_fuso` inicialmente nulos e sincronizados automaticamente com a
Meta, e a apresentação discreta de valores. Coleta horária,
conferência diária, atualização do painel pelo banco e os dois PDFs estão
detalhados no fluxo. A parada após consolidação substitui a proposta anterior
de auditoria semanal; não há uma quarta opção de estado a implementar.
Banco, worker, painel e PDFs permanecem para implementação posterior; esta
revisão apenas atualiza o plano. A função de consulta já obtém o fuso da WABA;
o worker usa a informação atual da Meta para sincronizar o cadastro
local. O fuso opcional da função permanece uma conferência manual, sem servir
como bloqueio da atualização automática e sem alterar a conta Meta.


## 14. Mapa da implementação e decisões operacionais

- `core/integrations/whatsapp/consumo.py`: GET da conta/fuso e pricing analytics;
  o utilitário mantém seus atalhos IDE/CLI e delega a consulta a esse módulo.
- `core/consumo_meta/`: calendário, validação de identidade, volumes e decisão do
  dia 25. Comparação sempre usa a leitura persistida anterior ao upsert.
- `core/repositories/consumo_meta/coletas.py`: SQL sem commits ou HTTP.
- `workers/worker_consumo_meta/`: configuração, ciclo sequencial, supervisor e
  transações curtas em `processamento.py`. Serviço systemd independente.
- `consumo_meta_coletas`: agenda e diagnóstico separados, com chave unidade/período
  (`conta` ou `AAAA-MM`). `ultima_tentativa_em`, `ultimo_erro`,
  `falhas_consecutivas` e `proxima_consulta_em` ficam aqui, incluindo falhas antes
  do primeiro registro mensal. Substitui os nomes propostos de verificação
  no registro mensal sem duplicar estado de agenda.
- `core/repositories/monitoramento/consumo.py`: leituras por unidade autenticada.
- `callback/monitoramento/consumo_services.py`, `consumo_views.py`, `consumo_pdf.py`:
  apresentação, autorização dos endpoints e relatórios. Frontend dedicado em
  `consumo.js`/`consumo.css`, com seletor independente e refresh a cada 30 segundos.
- Modelos unmanaged em `callback/webhook/models.py`; migração manual transacional,
  reutilizada pelo setup inicial. Não é necessária migration Django desse domínio.
- Referência monetária e vigência são preservadas por mês; o valor não é fatura.
- Inicialmente recuperar meses desde outubro/2026; o cadastro de unidade atual
  não possui data de início de acompanhamento. Não inferir essa data de conversas.
- Reversão operacional mantém tabelas e dados (mudança aditiva), para evitar perda
  de histórico. SQL e ativação de produção seguem o guia de deploy específico.
