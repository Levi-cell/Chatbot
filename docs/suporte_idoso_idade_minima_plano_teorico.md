# Plano teórico — encaminhamento ao comercial por idade mínima

**Status:** proposta para implementação; não aplicada ao código ou ao banco.
**Base analisada:** V1.2.0. **Data:** 10/09/2026.

Este plano substitui a configuração booleana de suporte ao idoso por uma idade
mínima escolhida entre seis opções fixas. Registra comportamento, responsabilidades,
migração e verificações necessárias. O código completo de cada alteração e o SQL
executável pertencem à futura implementação ou ao plano prático.

Referências: [regras atuais](../REGRAS_DE_NEGOCIO.md),
[arquitetura](../PADROES_DE_ARQUITETURA.md),
[rotina de etapas](../ROTINA_IMPLEMENTACAO_ETAPAS.md) e
[fronteiras transacionais](./_V2/fluxo-transacional-worker.md).

## 1. Objetivo e decisões confirmadas

Cada unidade poderá definir a partir de qual idade o **próprio titular** será
encaminhado ao contato comercial, logo após informar a idade na **etapa 6**.

| Opção no Admin | Valor no banco | Titulares encaminhados por esta política |
|---|---|---|
| Desativado | `NULL` | Nenhum |
| 50+ | `50` | De 50 a 99 anos |
| 60+ | `60` | De 60 a 99 anos |
| 70+ | `70` | De 70 a 99 anos |
| 80+ | `80` | De 80 a 99 anos |
| 90+ | `90` | De 90 a 99 anos |

O limite é inclusivo: com 70+, uma pessoa de 69 anos continua no fluxo normal
e uma de 70 anos é encaminhada ao comercial. Pessoas com 100 anos ou mais
mantêm o tratamento específico já existente, independentemente desta escolha.

Somente o proprietário do sistema configura essa política pelo Admin atual.
Não será criada edição pelo portal do franqueado: o monitoramento permanece
somente leitura. A configuração é por unidade, não global.

Continuam como estão:

- atendimento de dependentes, inclusive dependentes idosos;
- tratamento do titular menor de 18 anos;
- idade mínima do dependente: 4 anos com BPA e 5 anos sem BPA;
- tratamento de idade inválida, ambígua ou acima de 99 anos;
- dispensa universal de e-mail para titulares 60+ que chegam à etapa 10;
- configuração `email_obrigatorio` para os demais casos;
- regras de turno, fila, idempotência, bloqueios e follow-up;
- tags de faixa etária do monitoramento, incluindo `18–59`, `60+` e as de dependentes;
- numeração das etapas, mapa de transições e formatos dos quatro CSVs.

Na seção de relatórios, acrescentar a quantidade de leads efetivamente
encaminhados ao comercial pela política de suporte por idade, conforme a seção 7.

Não há proposta de IA, tracker, nova tabela de tentativas, histórico de mudanças
de configuração ou mecanismo de troca de política durante um envio. A alteração
deve aproveitar as proteções de recuperação que já existem.

## 2. O que existe hoje e precisa evoluir

Hoje, `chatbot.unidade.suporte_idoso` é `BOOLEAN NOT NULL DEFAULT FALSE`.
Quando habilitado, o resolver da etapa 6 encaminha titulares entre 60 e 99 anos,
persiste a idade e encerra o atendimento na própria etapa 6, sem bloqueio de dias.

O número 60 não está apenas no resolver: aparece no catálogo da mensagem, na
persistência da idade, na reconstrução do encerramento e nas regras de apresentação
dos relatórios. Há também conversões `bool(suporte_idoso)` no monitoramento e nos
utilitários. Alterar somente a coluna ou o `if` do resolver deixaria esses
consumidores incompatíveis.

O plano trata todos esses pontos como uma única entrega. Os documentos de
funcionamento atual só serão atualizados quando essa entrega for implementada.

## 3. Contrato da configuração

### Banco de dados

Nome proposto para o campo final: **`idade_minima_suporte`**.
Tipo: **`INTEGER`**, aceitando `NULL`, com padrão `NULL`.

O nome explicita que o valor é uma idade, evitando manter uma coluna de aparência
booleana com dois significados. A coluna anterior será convertida e renomeada na
migração; não haverá dois controles independentes para a mesma política.

O banco deverá limitar o domínio a:

```text
idade_minima_suporte IS NULL
OR idade_minima_suporte IN (50, 60, 70, 80, 90)
```

`NULL` significa desativado. Não usar `0`, `-1`, string vazia ou `100` como
valores especiais. Os textos `50+` e semelhantes pertencem à apresentação;
o banco armazena o número inteiro.

### Admin e contexto Python

O modelo Django terá um campo inteiro opcional com as cinco escolhas numéricas,
mais a opção vazia explicitamente rotulada **Desativado**. Usar um seletor, sem
entrada livre de idade. Rótulo sugerido:

> Encaminhar titular ao comercial a partir de

O texto de ajuda deve esclarecer que a escolha é aplicada na etapa de idade,
somente ao titular, e não modifica a regra de e-mail.

Quando a opção for diferente de `NULL`, continuar exigindo `numero_comercial`
válido para construir o link de WhatsApp. Essa validação também precisa impedir
que uma edição remova o contato comercial enquanto a política estiver ativa.
Com a política desativada, preservar a validação que já existe para os demais usos
desse número, sem criar novas exigências para todas as unidades.

No código de negócio:

- aceitar somente `None` ou um inteiro pertencente ao conjunto permitido;
- distinguir um campo presente com `None` de um campo ausente no contexto;
- rejeitar configuração ausente ou inválida, em vez de desativar silenciosamente;
- não converter o limite em `bool` nem substituir valor inválido por 60;
- rejeitar booleanos em validadores Python, mesmo que `bool` seja subtipo de `int`;
- deixar a conversão dos valores do formulário a cargo do campo tipado do Django.

Uma pequena definição compartilhada do domínio e de sua validação pode ficar
em `core/validacoes/suporte_por_idade.py`. Esse módulo será puro, sem SQL,
chamadas Meta ou dependência do Admin. A decisão de encaminhar continua no
resolver da etapa; não criar um novo sistema genérico de políticas.

## 4. Decisão na etapa 6

A ordem de tratamento deve preservar a prioridade já existente:

1. Reconhecer uma resposta do bot já persistida, pelo caminho de idempotência.
2. Para uma nova resposta, aplicar os tratamentos de mídia, reforço escolar
   e financeiro antes de interpretar a idade.
3. Validar a idade pelo validador atual; entradas inválidas repetem o tratamento.
4. Se a idade for 100 ou mais, executar o encerramento específico atual.
5. Aplicar a nova política quando for titular, houver limite e a idade for
   igual ou superior ao limite.
6. Preservar o tratamento do titular menor de 18 anos e do dependente abaixo
   da idade mínima, conforme BPA.
7. Nos demais casos, resolver o evento `idade_valida` pelo mapa e seguir para
   a etapa 7, com os efeitos atuais.

Como o menor limite permitido é 50, a nova condição não alcança menores de
18 anos. A verificação de 100+ continua anterior ao suporte por faixa.

```text
Idade validada e abaixo de 100
    -> é o próprio titular?
    -> a unidade possui limite configurado?
    -> idade >= limite?
         Sim: enviar contato comercial e encerrar pela política de suporte
         Não: continuar as demais regras atuais da etapa 6
```

### Resultado do encaminhamento

- Enviar a mensagem de suporte com o botão **Falar com Comercial**.
- Persistir a idade informada pelo titular.
- Permanecer na etapa 6; não inventar uma aresta para a etapa 7 ou 22.
- Encerrar com `motivo_encerramento = 'encaminhado_suporte_idoso'`.
- Manter bloqueio de zero dias e o comportamento atual para um contato futuro.
- Não gerar oportunidade no Funil por esse encaminhamento.
- A conversa encerrada deixa de ser elegível ao follow-up pelas regras existentes.

O motivo técnico de encerramento permanece com o nome atual para conservar a
compatibilidade com os registros existentes. Esse nome não redefine a faixa
etária do contato nos relatórios.

## 5. Mensagem e recuperação existentes

### Mensagem proposta

Manter a estrutura atual e parametrizar somente a idade mínima:

> Entendi. Para oferecer um atendimento mais adequado, esta unidade realiza o
> suporte a clientes com {idade_minima} anos ou mais diretamente com a nossa
> equipe comercial.
>
> Vou te passar o contato para continuar o atendimento. Basta clicar no botão abaixo.

O catálogo monta o texto; o sender recebe o limite já validado e envia o CTA.
O sender não consulta a unidade nem decide quem deve ser encaminhado. O texto
persistido deve ser exatamente o enviado, incluindo eventual saudação de retorno.

Com limite 60, a mensagem deve continuar idêntica à versão anterior. Isso permite
reconhecer o histórico existente sem migrar textos de mensagens já enviadas.

### Compatibilidade do retry

Sempre que a recuperação precisar avaliar ou reavaliar o encaminhamento por
idade, deverá usar `idade_minima_suporte` lida da unidade no ciclo atual.
Não guardar, reconstruir ou comparar o limite anterior para essa decisão.
Se o limite passou de 60 para 70, a avaliação usa 70; se foi desativado, usa `NULL`.

Hoje o encerramento pode ser reconstruído a partir da resposta já registrada,
do tipo `interactive_cta_url` e do conteúdo oficial. Essa proteção continua;
a parametrização não pode fazer uma resposta existente deixar de ser reconhecida.
Reconhecer uma resposta serve para recuperar o trabalho e evitar reenvio, não
para transformar a idade mencionada no texto em configuração da unidade.

A adaptação será local aos mecanismos existentes:

- reconhecer as cinco variantes oficiais da mensagem, incluindo a antiga de 60;
- manter a compatibilidade com o prefixo de saudação já suportado;
- exigir etapa de origem 6 e titular com idade válida; quando for necessário
  avaliar a política de encaminhamento, comparar com o limite atual da unidade;
- não tratar qualquer texto que mencione “comercial” como prova de encaminhamento;
- ampliar a validação da persistência para os novos limites, sem deixar o
  intervalo fixo de 60–99 rejeitar titulares de 50–59;
- conservar `resposta_bot_para_mensagem_atual`, sem enviar novamente quando
  houver resposta persistida correspondente.

O reconhecimento pode comparar o conteúdo com as cinco mensagens geradas pelo
catálogo para identificar o tipo de resposta, sem extrair o limite antigo como
regra de decisão. Não adicionar snapshots, rastreadores, histórico de configuração
ou uma validação especial de mudança de faixa.

A configuração atual não autoriza reenviar uma resposta já registrada, reescrever
o histórico ou avançar para uma etapa sem a resposta e a persistência correspondentes.
Continuam valendo os caminhos normais de recuperação de contexto e idempotência.

A atomicidade continua pertencendo ao flow: histórico e idade são confirmados
na persistência da resposta; encerramento e finalização da fila seguem o
checkpoint atual. Nenhum sender ou repositório passa a controlar commits.

Na reação ao follow-up, o caminho próprio continua repetindo a pergunta da
etapa 6, sem interpretar essa reação como idade e sem executar o encaminhamento.
A nova regra é avaliada quando o cliente responder normalmente à pergunta.

## 6. E-mail: política independente

O limite de suporte não será reutilizado como idade de dispensa de e-mail.

| Pessoa que chega à etapa 10 | E-mail efetivamente obrigatório? |
|---|---|
| Titular de 18 a 59 anos | Conforme `email_obrigatorio` da unidade |
| Titular de 60 a 99 anos | Não, independentemente da configuração da unidade |
| Dependente de qualquer idade válida | Conforme `email_obrigatorio` da unidade |

Exemplos importantes:

- Limite 70, titular de 65 anos: continua após a idade e tem e-mail opcional.
- Limite 90, titular de 89 anos: continua após a idade e tem e-mail opcional.
- Suporte desativado, titular de 60 anos: continua e mantém a dispensa de e-mail.
- Limite 50, titular de 49 anos: continua; exigência de e-mail segue a unidade.
- Limite 50, titular de 50 anos: é encaminhado na etapa 6, antes da coleta de e-mail.
- Limite 50, dependente de 70 anos: não é encaminhado por esta política;
  a exigência de e-mail segue a unidade, pois o atendimento é de dependente.

Não alterar validadores nem mensagens da etapa 10 por causa deste limite.
Os testes de e-mail existentes permanecem como proteção contra regressão.

## 7. Monitoramento e relatórios

### Identificação e configuração exibida

Manter as cinco classificações atuais de perfil e as tags de idade. Uma unidade
com suporte a partir de 50 não transforma um titular de 50 anos em integrante
da faixa 60+. O limite é uma política de encaminhamento, não uma classificação
etária geral.

As tags `18–59` e `60+` dos titulares permanecem iguais nas seis configurações,
assim como as tags dos dependentes. A proposta anterior de substituir essas tags
pelo limite de suporte foi descartada. O indicador de encaminhamentos abaixo
mostra o resultado da política sem alterar a identificação etária do atendimento.

O payload interno do painel deve transmitir `idade_minima_suporte` como inteiro
ou `null`. O JavaScript apresentará, por exemplo, **Encaminhamento ao comercial:
70+** ou **Encaminhamento por idade: desativado**. Remover o texto fixo
“Suporte 60+ ativo” e as conversões booleanas desse campo.

Frontend e backend devem ser publicados na mesma entrega, com a atualização da
referência de cache dos estáticos conforme o padrão do projeto. Não reaproveitar
um booleano `suporte_idoso` como se ele ainda descrevesse todo o grupo 60+.

### Cálculo dos números

Hoje o suporte ativo pode tornar a linha inteira de titulares 60+ “não aplicável”
ao Funil. Com limite 70, essa linha contém pessoas abaixo e acima do limite.
Com limite 50, o próprio grupo 18–59 também fica parcialmente alcançado.

Regra planejada para evitar essa ambiguidade:

- preservar as faixas e os critérios atuais de contagem e deduplicação;
- calcular quantidades e taxas pelos envios efetivamente registrados;
- não zerar uma faixa inteira nem ocultar seus envios pela configuração atual;
- manter a informação sobre o limite como nota de política da unidade;
- não reclassificar retroativamente conversas nem deduzir que todo contato acima
  do limite já foi encaminhado: ele pode nem ter chegado à etapa 6;
- acrescentar somente o indicador de encaminhamentos definido abaixo, sem novos
  gráficos, mudança das tags ou duplicação dos indicadores na seção Conversas.

Aplicar o mesmo contrato ao painel, ao relatório semanal e ao total. A política
atual não apaga fatos históricos e não comprova qual regra vigorava no passado.
Os formatos, critérios de elegibilidade e números dos CSVs não são alterados.

### Indicador: encaminhados ao comercial

Na seção **Relatórios**, apresentar um card compacto **Encaminhados ao comercial**,
logo abaixo dos quatro indicadores atuais e antes de **Evolução da demanda**.
Usar o subtítulo **Leads únicos encaminhados por suporte de idade no período**,
para tornar claro o que o número representa.

Preservar o tamanho das fontes e o aproveitamento de espaço do painel. O card
deve se adaptar a computador e celular, nas orientações vertical e horizontal,
sem sobreposição nem rolagem horizontal da página. Não recolocar indicadores
na seção Conversas. Não há novo gráfico, percentual ou comparação temporal
planejado para esse card; o seletor de período existente controla a contagem.

#### Fonte e regra de contagem

Usar os registros já existentes em `chatbot.conversa`, sem uma nova tabela ou
contador persistido. O valor é a quantidade de **clientes distintos da unidade
autorizada** com pelo menos uma conversa que cumpra simultaneamente:

- `status_ativa = FALSE`;
- `motivo_encerramento = 'encaminhado_suporte_idoso'`;
- `finalizou_em` preenchido e dentro do período selecionado.

O motivo identifica o encaminhamento efetivamente concluído pelo fluxo de suporte.
Não inferir esse fato pela idade atual do cliente, configuração atual da unidade,
tag `60+`, etapa isolada ou mera presença do número comercial.

O recorte temporal usa **a data de encerramento do encaminhamento**:

```text
finalizou_em >= início do período, quando houver início
finalizou_em < fim do período
COUNT(DISTINCT id_cliente), limitado à unidade autorizada
```

Reutilizar os limites de período e o tratamento de fuso já existentes. Em todo
o histórico, considerar todos os encerramentos desse motivo anteriores ao fim
da consulta, sem inventar uma data de corte para a nova funcionalidade.

Regras complementares:

- Duas conversas encaminhadas do mesmo cliente no período contam **um lead**.
- Um cliente com encaminhamento em períodos diferentes pode aparecer em cada
  período; somar subtotais de períodos não equivale necessariamente ao histórico total.
- Consultar todas as conversas correspondentes, não somente a mais recente do
  contato. Uma conversa posterior comum não apaga um encaminhamento anterior.
- Encaminhamentos antigos com o motivo já registrado entram na contagem, inclusive
  os feitos pelo suporte booleano anterior. Não fazer backfill por idade ou texto.
- Desativar o suporte ou mudar o limite não altera a contagem dos fatos registrados.
- Retry não pode multiplicar o número; a consulta agrega os encerramentos persistidos.
- Falha de envio ou encerramento ainda não confirmado não entra no indicador.
- O encaminhamento de pessoas com 100 anos ou mais possui tratamento e motivo
  distintos; não é incluído neste indicador específico de suporte por faixa.
- Conversas de outra unidade e outros motivos de encerramento não entram na soma.
- Uma consulta concluída sem ocorrências exibe **0**. Falha de consulta segue o
  tratamento de erro do relatório e não deve ser apresentada como zero real.

O número confirma o encaminhamento registrado pelo bot. Ele não confirma clique
no botão, atendimento humano, matrícula, venda ou envio ao CRM Funil. Explicar essa
semântica também em **Como interpretar os números**.

O indicador é medido por encerramentos no período; **Leads em contato** usa
mensagens recebidas no período. Portanto, não apresentar o novo valor como uma
porcentagem automática daquele total: um contato pode ter enviado a mensagem
antes do início do intervalo e ter seu encaminhamento concluído dentro dele.

#### Integração com o relatório

Adicionar uma consulta agregada no repositório do painel e chamá-la no serviço
de relatórios, após resolver a unidade autorizada e o período. O payload deve
expor um inteiro, por exemplo `encaminhados_comercial_por_idade`, para a montagem
e renderização do relatório. A interface não calcula esse total pela lista de
contatos ou pelas tags.

A inclusão desse indicador é solicitada para o painel web. Relatórios manuais
continuam recebendo os ajustes de configuração descritos anteriormente; criar
um card equivalente nos PDFs ou alterar os CSVs não faz parte deste acréscimo.

## 8. Responsabilidade dos arquivos na implementação

| Área | Arquivos a revisar | Responsabilidade |
|---|---|---|
| Domínio compartilhado | Novo `core/validacoes/suporte_por_idade.py` | Valores aceitos e validação pura do limite |
| Instalação limpa | `core/database/deploy_database/bank_script.py` | Nova definição da coluna e restrição de domínio |
| Banco existente | Novo SQL em `deploy/migrations/` | Converter a configuração sem mudar a política vigente |
| Modelo e formulário | `callback/webhook/models.py`, `callback/webhook/admin.py` | Campo inteiro opcional, seletor e validação do contato comercial |
| Contexto | `core/repositories/fluxo/contextos/etapa6.py` | Ler e validar o limite sem convertê-lo em booleano |
| Decisão | `workers/worker_flow/response_flow/etapas/resolver_etapa6.py` | Aplicar a idade mínima somente ao titular |
| Conteúdo | `core/integrations/whatsapp/messages/etapa6_messages.py` | Montar as variantes do texto oficial |
| Envio | `core/integrations/whatsapp/pywa_functions/pywa_senders/etapa6.py` | Enviar texto e botão a partir do limite recebido |
| Persistência | `workers/worker_flow/transacoes/efeitos_transicao.py` | Salvar a idade no encaminhamento com o novo domínio |
| Recuperação e encerramento | `workers/worker_flow/transacoes/encerramento_atendimento.py` | Reconhecer mensagens oficiais e concluir o encerramento existente |
| Dados do painel | `core/repositories/monitoramento/painel.py`, `callback/monitoramento/services.py` | Consultar o limite, adaptar o agrupamento e contar leads encaminhados por unidade e data de encerramento |
| Apresentação do relatório | `callback/monitoramento/apresentacao.py` | Incorporar o indicador ao relatório sem alterar a classificação de faixas ou as tags das conversas |
| Interface do painel | `callback/monitoramento/static/monitoramento/js/painel.js`, CSS e template do painel | Exibir o limite, renderizar o card compacto de encaminhamentos e sua explicação, preservando as tags e atualizando os estáticos |
| Relatórios manuais | `utilitarios/reports_functions/weekly.py`, consumidores em `total.py` | Atualizar snapshot, segmentação e textos de política |
| Verificação | Testes de suporte/e-mail, painel, relatórios e fixtures | Cobrir domínio, fronteiras, recuperação e preservação de regras |

Os consumidores do relatório total devem ser conferidos mesmo quando reutilizam
funções do semanal, evitando duplicar a implementação. Procurar todas as referências
a `suporte_idoso` no código ativo antes de concluir; manter as que representam
motivos históricos, nomes de mensagens ou migrações anteriores de forma intencional.

O cache atual de unidades resolve identidade/admissão e a etapa 6 lê essa política
diretamente do banco. Não criar um novo cache para o limite. Preservar os hooks
de validação e invalidação que o Admin já executa ao editar uma unidade.

Atualizar os READMEs e regras operacionais afetados na entrega do código. Não
alterar planos de `user_id` ou de IA como parte desta implementação.

## 9. Migração, publicação e retorno de versão

### Conversão preservando o comportamento

| Estado anterior | Estado novo |
|---|---|
| `suporte_idoso = FALSE` | `idade_minima_suporte = NULL` |
| `suporte_idoso = TRUE` | `idade_minima_suporte = 60` |

Não converter booleano por cast numérico para 0/1. Não atribuir 50 ou outro limite
às unidades na implantação. A escolha de uma faixa nova será feita depois pelo
proprietário, no Admin.

A migração incremental deverá ser transacional e:

1. Conferir a existência da tabela, o tipo booleano original e a ausência de
   schema parcial ou de uma coluna nova conflitante.
2. Registrar para conferência as quantidades de unidades habilitadas/desabilitadas.
3. Remover default booleano e obrigação de valor não nulo antes da conversão.
4. Converter por regra explícita `TRUE -> 60` e `FALSE -> NULL`, renomear a coluna
   e adicionar o domínio fechado de valores, com default `NULL`.
5. Verificar tipo, nulabilidade, restrição validada e correspondência dos valores.
6. Confirmar somente se todas as verificações passarem; falha deve reverter tudo.

Recusar reaplicação com mensagem clara, em vez de reconverter dados. Manter intacta
a migração histórica que criou as flags booleanas: um banco novo usa o DDL atual;
um banco V1.2.0 recebe o novo SQL incremental, não a sequência indiscriminada de
todos os scripts antigos. Como o modelo é `managed = False`, mudar o campo Django
não substitui a migração SQL.

### Publicação coordenada

Esta mudança de schema não admite manter consumidores antigos consultando a
coluna removida. O futuro procedimento deve coordenar código e SQL numa janela
de manutenção, seguindo os [guias de deploy](../deploy/README.md):

1. Validar a implementação e a migração em banco local descartável.
2. Registrar versão anterior e backup recuperável antes da alteração.
3. Parar os consumidores para a manutenção, começando pelo follow-up e incluindo
   flow, Funil e webhook; não deixar operadores executando relatórios antigos.
4. Atualizar o código, executar a migração pendente e conferir as pós-condições.
5. Executar verificações de aplicação e publicar os estáticos do painel.
6. Retomar serviços compatíveis, com flow validado antes de ativar o follow-up.
7. Conferir Admin, painel, relatórios e logs antes de mudar uma unidade para
   uma das faixas novas.

Não há necessidade planejada de nova variável `.env`, mudança no serviço systemd,
alteração do stage de conversas antigas ou reexecução da migração de follow-up.

Um retorno para código booleano precisa de reversão de schema e configuração
compatível, não apenas `git checkout`. Antes de configurar faixas novas, o par
`NULL/60` é reversível para `FALSE/TRUE`. Depois de usar 50, 70, 80 ou 90, não
converter silenciosamente tudo para `TRUE`: isso mudaria a regra para 60+.
O runbook de implementação deve orientar restaurar a configuração anterior
validada ou corrigir a nova versão, sem reescrever históricos de atendimento.

## 10. Verificações e critérios de aceite

### Domínio e migração

- Admin e banco aceitam exatamente `NULL`, 50, 60, 70, 80 e 90.
- Código rejeita valor ausente no contrato, booleanos e inteiros fora do domínio.
- Nova unidade nasce desativada; habilitar exige contato comercial válido.
- Conversão de `TRUE/FALSE` preserva a política de todas as unidades.
- Migração incompleta falha com rollback; reaplicação é recusada.
- Instalação limpa e migração resultam no mesmo contrato final da coluna.

### Fronteiras de idade

Para cada limite `L` de 50, 60, 70, 80 e 90, testar titulares com `L-1`, `L`,
`L+1` e 99 anos. O primeiro continua; os demais são encaminhados. Testar também:

| Entrada | Resultado esperado |
|---|---|
| Política desativada; titular de 50, 60, 70, 80, 90 ou 99 | Fluxo normal de idade |
| Titular de 17 anos, qualquer opção | Tratamento atual de menor de idade |
| Titular de 18 ou 49 anos, qualquer opção | Nenhum encaminhamento por suporte |
| Pessoa de 100 anos, titular ou dependente | Tratamento específico acima de 99 |
| Dependente de 60, 70, 90 ou 99 anos, limite 50 | Não aciona suporte do titular |
| Dependente de 4 anos com/sem BPA | Preserva os limites atuais de admissão |
| Mídia, financeiro, reforço escolar e idade inválida | Preserva precedência e tratamento |

### Persistência e comportamento final

- Idade, texto enviado, histórico e motivo correspondem ao encaminhamento correto.
- A conversa encerra na etapa 6, sem bloqueio de dias e sem envio ao Funil.
- Falha de envio não conclui o atendimento; falha de persistência respeita rollback.
- Retry com resposta existente não reenvia, reconhecendo as cinco variantes e
  a mensagem antiga de 60, inclusive com saudação de retorno.
- Uma avaliação necessária durante a recuperação usa o limite atual da unidade,
  inclusive `NULL`, sem recuperar o anterior pelo texto de uma mensagem.
- Sem resposta do bot registrada, um titular de 65 anos recuperado após mudança
  de 60 para 70 segue a decisão normal com 70, sem encaminhamento por esta política.
- Uma resposta comum da etapa 6 não é confundida com encaminhamento comercial.
- Reação ao follow-up repete a pergunta e mantém seu reset atômico, sem usar a
  reação como idade e sem executar a regra de suporte naquele turno.

### E-mail e apresentação

- Titulares 60+ continuam dispensados do e-mail; demais casos seguem a unidade.
- Dependentes 60+ continuam sujeitos à política de e-mail da unidade.
- Painel e relatórios exibem a faixa configurada, inclusive desativado.
- Perfis e tags continuam classificando 18–59 e 60+ independentemente do suporte.
- As seis configurações não alteram tags de titulares ou dependentes; testar
  explicitamente titulares de 55, 65 e 75 anos com limites 50, 70 e 90.
- Faixa parcialmente alcançada pelo limite não recebe “Não se aplica” global.
- Envios históricos ao Funil permanecem contabilizados; configurações não apagam dados.
- CSVs mantêm colunas, períodos, elegibilidade e tratamento de telefone atuais.

### Indicador de encaminhamentos ao comercial

- Um encerramento confirmado pelo motivo de suporte soma um lead na unidade correta.
- Duas conversas encaminhadas do mesmo cliente no período continuam somando um lead.
- Mensagens ou joins adicionais não multiplicam o resultado agregado.
- Início do período é inclusivo e fim é exclusivo, considerando `finalizou_em`.
- Validar todas as opções de período existentes e todo o histórico.
- Conversa posterior comum não elimina encaminhamento dentro do período consultado.
- Registros antigos do suporte booleano continuam contados após a migração;
  limite atual e idade atual não são filtros para apagar esses registros.
- Suporte desativado preserva a contagem histórica; sem ocorrências, o card mostra 0.
- Falhas de envio, encerramentos pendentes, outros motivos e outras unidades não contam.
- O tratamento de 100+ não se mistura com este indicador de suporte por faixa.
- A interface atualiza o número ao trocar período, mantém os quatro cards existentes
  e não altera tags nem adiciona indicadores à seção Conversas.
- Erro de consulta não é mascarado como zero; o card é legível em computador e
  celular nas duas orientações, sem reduzir fontes ou quebrar a largura da página.

Os testes devem usar fakes para Meta e banco descartável explícito para o SQL,
conforme o [padrão do projeto](../tests/README.md). A entrega só está pronta após
essa cobertura e a conferência visual do seletor e dos textos do painel. Este
plano não equivale a testes executados nem a garantia de ausência absoluta de bugs.
