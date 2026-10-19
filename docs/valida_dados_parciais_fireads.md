# Consulta FireAds por conversa — operação

> Atualização local de 14/10/2026: o contrato vigente usa somente a aba geral,
> `Para quem é` e `Canal`, com seleção dos canais elegíveis antes da recência.
> Consulte [o plano aplicado e o procedimento de deploy](../atualizar_envio.md).
> As descrições abaixo de duas/três abas e seus SQLs são históricas; não as
> reaplique neste deploy. A proposta de coleta parcial continua sem implementação.

> Definições de negócio consolidadas em 19/10/2026 na seção de coleta parcial:
> extração da primeira mensagem, unidades com/sem FireAds, resolução de campos
> conflitantes e seleção/criação no dashboard. Sem FireAds, preservar o canal
> padrão Meta Ads (`113340`) configurado no Funil da unidade. A implementação do
> fluxo adaptável e a avaliação de migração continuam pendentes.


Este documento acompanha o código do worker separado. Aplicar junto da migração
`deploy/migrations/20261009_worker_consulta_dash.sql` e do novo serviço.

Código aplicado localmente após o backup `b049a4d`. Validação da aplicação:
443 testes unitários e 28 testes de integração FireAds aprovados, sem testes
pulados, além de `manage.py check` sem problemas. O PostgreSQL usado foi local
e descartável; HTTP externo foi simulado. Deploy V1.11.0 confirmado na VM em
09/10/2026 às 23:36 (Brasília): migração aplicada e seis serviços ativos.

Correção posterior, ainda a implantar: a abertura escolhe o registro mais recente
do telefone entre Google e Meta, incluindo as variantes com/sem nono dígito.
Respostas diferentes não geram mais ambiguidade. Datas sem offset usam o fuso
configurado ou Brasília na ausência dele; isso não modifica a planilha.
Datas iguais usam a maior `_row` (última posição recebida quando não há linha
válida), inclusive entre abas, sem prioridade fixa por origem. Datas válidas
precedem inválidas; sem datas válidas, vale esse mesmo desempate por linha/posição.
Se todos esses critérios empatarem, mantém o primeiro candidato encontrado.
O desempate por linha entre abas é uma convenção de seleção; não comprova
cronologia que a fonte deixou de informar.
O formulário escolhido é usado inteiro; se estiver incompleto, não se resgatam
campos antigos. Não há migração SQL nova: `ambiguidade` continua permitido no
banco apenas para preservar resultados históricos. Validação da correção:
46 testes de FireAds, espera HTTP e runtime do flow aprovados, com HTTP simulado.

## Contrato

Consultar só uma vez logicamente por conversa nova, antes da primeira resposta.
O `worker_flow` não executa HTTP FireAds, não cria threads auxiliares e não aguarda
rede. Registra a pendência e devolve a mensagem à fila por 5 segundos, sem consumir
retry. O worker de consulta verifica o banco a cada 2 segundos quando ocioso; havendo
trabalho, processa uma consulta e segue para a próxima sem espera adicional.

A aba configurada em `aba_destino` é lida por inteiro no contrato atual do Apps
Script. A leitura e a interpretação terminam antes de gravar `dados` em uma única transação.
Armazenam-se somente as linhas correspondentes ao telefone consultado, não as de
outros clientes. Não há checkpoints parciais por aba. Uma falha real de conexão,
HTTP ou contrato conclui organicamente com diagnóstico, conforme a regra aprovada.

O prazo total é de 300 segundos desde a solicitação, incluindo fila, leitura da aba geral,
redirecionamentos e reexecuções. Não é renovado após queda. A decisão de timeout é
persistida pelo primeiro ciclo que perceber o prazo vencido, inclusive pelo flow
se o serviço de consulta estiver parado. Portanto, a resposta pode ocorrer alguns
segundos depois do limite, conforme a agenda da fila. Uma chamada de rede ainda em
andamento não pode importar nada depois desse encerramento. Um resultado confirmado
no banco antes do prazo pode ser aplicado depois, sem ser descartado por demora do flow.

## Banco e recuperação

`consulta_fireads.id_conversa` é único. O chat é obtido por `conversa.id_chat`; não
há coluna de chat duplicada nem view. `id_unidade` permanece para as FKs compostas
que impedem vincular conversa e integração de unidades diferentes.

- `entrada`: versão 2, telefone, URL, aba única e fuso congelados na solicitação.
- `status`: pendente, processando ou concluida; `consulta_concluida` é mantida por
  compatibilidade e uma constraint exige consistência com o status.
- `dados`: envelope com `decisao` e `fontes`, gravado completo ou mantido NULL.
- `resultado`: pendente/importado/ausente/incompleto/erro; ambiguidade somente no legado.
- `solicitado_em` e `prazo_final`: orçamento persistente da abertura.
- `tentativas`, `versao_reserva`, `processing_started_at` e `reserva_ate`: reserva
  operacional; tentativas adicionais apenas recuperam uma execução interrompida.
- `consultado_em`: conclusão, inclusive ausência/erro/timeout.
- `aplicacao` e `aplicado_em`: decisão efetivamente aplicada pelo flow. Pode divergir
  do resultado externo se, por exemplo, houver conflito de e-mail na importação.
- `ultimo_erro`: diagnóstico sem corpo HTTP, credenciais ou dados de outro cliente.
- `atualizado_em`: última alteração, sem servir para reiniciar o prazo.

A reserva combina advisory lock de sessão PostgreSQL e versão persistida. Não há
transação nem row lock aberto durante HTTP: a conexão fica ociosa, mantendo só o
advisory lock. Dois processos não consultam o mesmo registro simultaneamente com
a sessão viva. A morte do processo libera o lock quando o banco encerra a conexão;
o próximo worker pode recuperar a mesma consulta antes dos 300 segundos. Perda de
rede pode retardar a detecção da sessão morta; o prazo orgânico continua valendo.

A gravação exige versão e prazo válidos. Timeout, suspensão da unidade, alteração
de configuração, conversa encerrada ou abertura já iniciada impedem confirmação
indevida. Não usar pool com troca de sessão: o lock depende da mesma conexão.
O próprio fechamento da conexão libera o lock, mesmo quando unlock falha.

O flow mantém seu lock versionado de conversa, a ordem dos turnos e a identificação
da mensagem. Solicitação e reagendamento são confirmados juntos no handler de
espera. A conversa pode já ter sido criada em um checkpoint anterior: se houver
queda nesse intervalo, a fila recria apenas a solicitação, reutilizando a conversa.
Importação, snapshot, histórico do cliente e marcador de aplicação pertencem à
transação do flow. O envio WhatsApp e a recuperação de seu recibo seguem o protocolo
atual; a janela de envio aceito externamente antes do commit local continua existindo.

Não alterar as regras existentes do webhook: no contrato atual, mensagens adicionais
chegando antes da resposta da entrada aberta podem ser descartadas na admissão.
As mensagens já admitidas na fila mantêm as guardas de ordem; não prometer juntar
textos enviados durante os minutos de espera nesta mudança.

## Cenários

| Situação | Resultado |
| --- | --- |
| Sem integração / conversa já iniciada | Atendimento atual, sem nova consulta. |
| Nova conversa elegível com integração | Uma solicitação persistida; nenhuma saudação prematura. |
| Google ou Meta completo | Importa titular, e-mail e destinatário; abertura na profissão, etapa 4. |
| Ambas as fontes / várias inscrições | Registro mais recente, com os desempates documentados acima. |
| Ausente / incompleto / falha / timeout | Atendimento orgânico desde a etapa 1, motivo registrado. |
| Resultado aplicado e retry | Reutiliza o contexto; nenhuma nova leitura ou regressão de etapa. |
| Pessoa preenche formulário depois da abertura | Considerar somente na próxima conversa. |
| Outra conversa do mesmo chat | Outro id_consulta; histórico anterior preservado. |
| Unidade suspensa | Não reservar nem importar; conservar pendências e histórico. |
| Configuração FireAds alterada durante a espera | Não aplicar a configuração antiga; concluir com motivo explícito. |

Telefone com e sem nono dígito, nome composto, descarte de faixa etária/objetivo,
saudação personalizada, salto da coleta do e-mail e canais Funil mantêm as regras
existentes. A aba geral não classifica a abertura; o worker_funil mantém sua própria
consulta antes da escrita e a preservação das observações existentes.

## Extração dos campos na abertura

O adaptador em `core/integrations/fireads/extratores.py` usa os campos estruturados
sem chamar os validadores de nome/e-mail do atendimento. `Edcarlos Oliveira |
Programador` fornece `Edcarlos`; `João Pedro Silva` fornece `João Pedro` pelo catálogo
de compostos conhecidos. Qualquer outro par usa somente a primeira palavra.
O e-mail é aparado e convertido para minúsculas sem rejeição por formato/domínio.
As opções de parentesco continuam mapeadas pelo contrato, sem inferir por faixa.

O flow confia na coleta persistida da própria conversa também ao pular a etapa de
e-mail. Campos vazios registram `campos_ausentes`; opção de destinatário não
reconhecida registra `destinatario_desconhecido`. Esses casos ainda usam o fallback
comum desde a etapa 1. Falhas operacionais e conflito de unicidade no banco conservam
as guardas existentes. Nenhuma migração SQL é necessária para os extratores.
Conversas já iniciadas não são reinterpretadas nem retrocedem após o deploy.

## Coleta parcial — proposta consolidada, não implementada

Vale separar, numa evolução, a origem do formulário da completude dos campos.
Um telefone encontrado continuaria Google/Meta/Orgânico Site mesmo com campos
apagados; somente os campos ausentes seriam perguntados. Preservar uma fotografia
única da consulta com origem, dados extraídos, campos ausentes e opções não
reconhecidas.

| Campo ausente | Comportamento proposto |
| --- | --- |
| Nome | Saudação sem nome, pergunta da etapa 1; após a resposta, pular destino e confirmação se já conhecidos. |
| Destinatário | Perguntar para quem é e confirmar nas etapas 2/3; seguir para profissão. |
| E-mail | Não impedir a abertura; coletar na etapa 10, com a política de e-mail vigente. |
| Vários ou todos | Combinar os comportamentos acima. Mencionar formulário na abertura somente quando identificado na rota FireAds. |

Antes de aplicar: desacoplar abertura personalizada de `email_importado`, definir
arestas explícitas para saltar somente campos conhecidos e persistir cada coleta
com o contexto da conversa. Preservar profissão, idade, rota de dependente,
personalização, `status_pagamento`, bloqueios e replay. Testar as oito combinações
de presença/ausência, opção desconhecida, conflito de e-mail e quedas entre commits.
Não reconsultar o formulário no meio do atendimento. A necessidade de migração das
transições deverá ser avaliada com essa implementação; este texto não é um script
de deploy nem um plano executável por arquivo.

### Complemento definido em 19/10/2026 — formulário recebido pelo WhatsApp

Proposta ainda não implementada. As exceções pontuais de reforço escolar e
financeiro descritas nas regras de negócio são uma alteração independente.

Analisar a primeira mensagem que abriu cada conversa nova, depois das guardas
de elegibilidade existentes. Procurar nome do titular, e-mail e destinatário
explícitos e aproveitáveis, sem exigir a frase inteira do formulário, uma ordem
fixa de perguntas ou os demais campos. Reconhecer rótulos equivalentes e não
inventar valores quando houver mais de uma interpretação. O nome fornecido pelo
formulário é sempre do titular; os dados do dependente continuam sendo coletados
pela rota própria. Manter o telefone remetente do WhatsApp como identidade do
cliente, com as equivalências de número já usadas pelo projeto.

O uso dessa mensagem como formulário Meta corresponde ao funcionamento que o
responsável pela integração informou para unidades com FireAds. Não deduzir nome
pelo cumprimento inicial, parentesco por idade nem origem comercial pelo domínio
do e-mail. A extração deve trabalhar sobre os campos identificados. Mensagem comum ou sem extração
inequívoca continua elegível à consulta do dashboard quando a integração estiver
ativa e aplicável. A leitura de dados no texto, por si só, não habilita uma
integração ausente, suspensa ou desativada.

1. Com os três campos aproveitáveis, persistir a abertura e responder pela
   profissão, sem consulta inicial à FireAds.
2. Com parte dos campos, ou com valores conflitantes para um campo, consultar uma
   vez o dashboard e completar/resolver somente o que falta a partir de um único
   registro compatível com os valores inequívocos conhecidos.
   Escolher o mais recente entre os compatíveis por data/hora e depois linha.
   Se houver somente registros incompatíveis, mesmo que seja apenas um,
   perguntar os campos faltantes ao cliente. Não trocar silenciosamente os dados
   extraídos da mensagem pelos de outra inscrição.
3. Sem dados de formulário na primeira mensagem, manter a consulta inicial.
   Se o registro encontrado estiver incompleto, aplicar a coleta parcial desta
   proposta; se não houver formulário identificado, seguir a abertura orgânica.

Guardar separadamente os dados originais do formulário, a fonte de cada valor,
os dados complementados, campos pendentes e alterações aceitas durante o chat.
Uma correção posterior não deve apagar a identidade usada para relacionar o
atendimento à inscrição original. A decisão da abertura deve ser persistida
antes da resposta e recuperável após queda, sem reconsultar em outras etapas
ou reiniciar conversas já em andamento. Não materializar uma consulta HTTP
pendente quando a abertura foi resolvida inteiramente pela mensagem.

Na entrega de um atendimento originado pelo formulário no chat e ainda sem
referência persistida de destino:

- Procurar primeiro o marcador de reconciliação da própria conversa, inclusive
  se uma tentativa anterior criou uma linha nova e caiu antes do commit local.
- Procurar registros com telefone, e-mail e destinatário compatíveis. Se houver
  vários, selecionar o mais recente por data/hora e, no empate, maior linha.
- Para conduzir o fluxo, parentescos e outras pessoas viram dependente. Conservar
  também a opção original e sua interpretação para distinguir inscrições quando
  essa informação estiver disponível, sem confundir mãe e filho apenas porque
  ambos seguem a rota de dependente.
- Se o telefone não existir, criar um novo registro com os dados do atendimento.
  Se existir, mas não houver registro compatível, também criar um novo registro,
  preservando as linhas incompatíveis. Essa é a decisão explícita do usuário;
  não deixar pendente somente por essa incompatibilidade.
- Preservar o canal da origem, os dados da nova inscrição e o bloco técnico no
  snapshot. Uma linha nova nessa rota não transforma o lead em orgânico nem
  define, por si só, a classificação de primeiro atendimento no Funil.
- Persistir a escolha do alvo antes da escrita e reutilizar essa escolha nos
  retries. Depois de vinculado, conferir/relocalizar o mesmo registro. Não
  ampliar automaticamente a regra de criação para uma referência já vinculada
  que foi apagada ou alterada, nem para conflito de e-mail com outro telefone.

As consultas, complementações e escritas continuam sujeitas aos locks,
`status_pagamento`, integrações ativas, congelamento de payload, regras de idade,
personalização e idempotência. Erro de API ou leitura incompleta não comprova
ausência/incompatibilidade e não autoriza criar uma linha. Repetição de operação
externa após queda ainda depende da reconciliação; a API da planilha não oferece
uma garantia transacional conjunta com o banco do chatbot.

Antes de implementar o conjunto, cobrir as oito combinações de campos presentes,
as três rotas acima, conflitos entre mensagem e planilha, múltiplas inscrições,
ausência/incompatibilidade na entrega, criação seguida de retry e retomada após
queda. Os tratamentos devem ignorar os enunciados conhecidos do formulário e
continuar reconhecendo dúvidas reais acrescentadas pelo cliente. Esta seção
registra as definições; ainda exige detalhamento das transições e persistência.

### Reutilização sem FireAds e campos conflitantes — complemento da proposta

O extrator de nome do titular, e-mail e destinatário deverá ser compartilhável
entre unidades. Ele apenas identifica candidatos na primeira mensagem e devolve,
por campo, um valor aproveitável ou a classificação ausente, inválido ou conflitante.
Não faz HTTP, não escolhe o canal de venda e não cria consultas no banco. A
orquestração decide a consulta ou a pergunta ao cliente conforme a integração.

| Situação na abertura | FireAds ativa e aplicável | Sem consulta FireAds disponível |
| --- | --- | --- |
| Três campos aproveitáveis | Persistir e iniciar pela profissão, sem consulta. | Persistir e iniciar pela profissão, sem consulta. |
| Dados parciais | Consultar um registro compatível para completar; perguntar o que continuar faltando. | Aproveitar o conhecido e perguntar os campos faltantes no momento adequado. |
| Campo com valores conflitantes | Consultar para resolver esse campo; sem resultado utilizável, perguntar ao cliente. | Perguntar ao cliente para resolver o campo. |
| Nenhum dado aproveitável | Manter a consulta inicial e a coleta prevista conforme seu resultado. | Seguir a abertura comum desde o nome. |

Essa proposta não modifica as guardas que impedem o atendimento de uma unidade
ou de um cliente. Sem integração FireAds, preservar o canal padrão Meta Ads
(`113340`) no Funil, conforme definido pelo usuário. O código atual obtém esse
valor de `integracao_funil_unidade.codigo_canal_venda`; a extração dos campos não
substitui a configuração nem muda o canal para orgânico por faltar algum dado.
Esse padrão vale com dados completos, parciais, conflitantes ou ausentes.

O canal Meta Ads dessas unidades decorre da configuração do Funil, não de uma
consulta ou da identificação de formulário FireAds. Não preencher
`origem_fireads` nem criar consulta/envio ao dashboard apenas para representar
esse canal. Manter a integração do Funil e seus dados de unidade. A abertura
pode reconhecer informações já enviadas pelo cliente, sem dizer que o bot
consultou ou viu um formulário externo.

Se o cliente apagar apenas parte do formulário antes de enviá-lo, preservar os
campos ainda identificáveis e seguir a tabela. Se apagar o texto inteiro e enviar
uma saudação, tratar como mensagem comum. Não tentar reconstruir o texto apagado
nem usar dados de uma conversa antiga como se estivessem na mensagem atual.

Regra explícita para múltiplos valores do mesmo campo:

1. Identificar candidatos e distinguir repetições do mesmo valor de valores
   diferentes. Dois e-mails iguais após aparar espaços e normalizar a caixa
   representam um valor; não escolher primeiro ou último quando forem diferentes.
2. Um campo conflitante não invalida os demais campos inequívocos. Não salvar
   arbitrariamente um dos candidatos como valor confirmado.
3. Com FireAds disponível, buscar pelo telefone remetente e pelos demais dados
   conhecidos. O campo conflitante não pode ser exigido como filtro de igualdade.
   Selecionar um único registro compatível, pela data/hora e depois maior linha,
   e usar o valor aproveitável desse campo no registro escolhido. Não misturar
   campos de inscrições diferentes nem exigir que o e-mail da planilha seja
   exatamente um dos dois candidatos da mensagem.
4. Se não houver registro compatível, se o campo do registro também não for
   aproveitável, ou se a consulta falhar/expirar, manter o campo pendente e
   perguntar ao cliente. A ausência de FireAds segue diretamente esse caminho.
   Não reconsultar em ciclos indefinidos nem retornar a etapas já concluídas.
5. Aplicar o mesmo princípio a nomes de titular ou destinatários conflitantes.
   O nome de dependente não compete com o campo de nome do titular. Preservar
   a origem de cada valor, os candidatos e a resolução no contexto persistido.

O fluxo adaptável precisa desacoplar a aceitação do e-mail da importação FireAds
completa, registrar a coleta por campo e autorizar as transições que pulam apenas
perguntas já respondidas. Profissão, idade, confirmação do destinatário quando
necessária e coleta do dependente continuam obedecendo às regras próprias.
Avaliar migração do mapa de transições no plano de aplicação; não substituir
essa autorização por atribuição direta de etapa. Testar as duas configurações
de unidade, dados apagados, valores repetidos/conflitantes, falha da consulta e
retomada após queda, além dos cenários já descritos. Esta extensão permanece
documental; o runtime ainda não oferece a coleta parcial.

### Estado das definições

As regras de negócio discutidas estão consolidadas nesta proposta. Antes da
aplicação, detalhar os contratos de coleta por campo, as transições autorizadas,
a persistência e a recuperação, incluindo a eventual migração SQL. A validação
deve cobrir o canal `113340` das unidades sem FireAds em todas as situações da
tabela, sem criar efeitos de consulta ou entrega FireAds. Essa conclusão das
definições não representa implementação nem validação executada do fluxo novo.

## Seleção da linha para atualizar o dashboard

A correção posterior à V1.11.1 está aplicada no código local e depende de deploy.
Não requer migração SQL nem mudanças nas abas da FireAds. Os códigos de canal do
Funil continuam Google `113336`, Meta `113340` e Orgânico `113481`.

Na aba de destino, o worker busca todas as variantes válidas do telefone. Antes
de escolher uma linha, procura o bloco da própria conversa: um bloco já gravado
é reconciliado, sem novo POST, mesmo se outra linha mais recente tiver surgido.
Marcador com conteúdo divergente continua pendente, sem sobrescrever ou copiar
o atendimento para outra linha.

Para uma entrega ainda não gravada, prefere o canal da origem e, dentro desse
grupo, titular/dependente compatível. `Organico Site` corresponde à origem Google
somente nesse cruzamento. As variantes `MKT DIGITAL - GOOGLE ADS` e
`MKT DIGITAL - META ADS (FACEBOOK/INSTAGRAM)` também são reconhecidas.
Faixa etária não define destinatário. Sem perfil compatível, mantém os candidatos
do canal; o desempate usa a maior `_row`. Sem canal compatível, usa a maior linha
do telefone. Na escrita, a data não prevalece sobre esse critério de linha.

E-mail diferente no mesmo telefone não bloqueia o update. Somente `Observação`
é alterada, preservando conteúdo anterior, e-mail, nome, canal e data da linha.
Telefone ausente gera cadastro com os dados do atendimento, inclusive para
orgânicos; e-mail encontrado em outro telefone continua exigindo conferência.
A FireAds preenche a data dos cadastros novos. Cabeçalhos/linha inválidos, falhas
HTTP e recusas da API continuam sujeitos ao reagendamento existente.

O JSON do snapshot passa a guardar `status_dependente`; envios antigos continuam
compatíveis pelo perfil textual já congelado. A linha confirmada no update fica
no recibo da API; reconciliações guardam `linhas_reconciliadas` no mesmo campo JSON.
A posição da linha é obtida na consulta anterior à escrita, não reutilizada como
endereço permanente. Edição externa entre leitura e POST permanece possível;
o contrato atual da FireAds não oferece atualização condicional por identidade.

## Implantação coordenada

1. Salvar backup e subir a revisão contendo TODOS os arquivos do plano.
2. Na VM, conferir a revisão e parar follow-up, webhook, flow, Funil e consumo Meta.
   Se o serviço de consulta já existir de uma tentativa anterior, parar também.
3. Atualizar o checkout com fast-forward. Manter serviços parados enquanto código
   e esquema forem incompatíveis. Não executar setup ou seeds em produção.
4. Executar inteiro o SQL final do plano no DBeaver. Exigir `migracao_ok=true` e
   `vinculos_invalidos=0`. Em erro, realizar ROLLBACK e corrigir antes de continuar.
5. Instalar o novo serviço com os comandos abaixo. Não iniciar ainda.
6. Sob o usuário chatbot e o ambiente já existente, executar `manage.py check`
   e `collectstatic --noinput`. Não precisa `makemigrations`/`migrate`: os models
   do domínio são `managed=False` e a mudança é o SQL manual indicado.
7. Iniciar consulta, webhook e flow; conferir status/logs. Depois iniciar Funil,
   consumo Meta e follow-up. Usar os mesmos controles de saúde do deploy atual.
8. Observar uma NOVA conversa autorizada de teste. Não resetar conversas antigas.

Instalação do sexto serviço na VM (após conferir a revisão):

```bash
cd /opt/chatbot/app &&
sudo install -m 0644 deploy/systemd/chatbot-worker-consulta-dash.service /etc/systemd/system/chatbot-worker-consulta-dash.service &&
sudo systemctl daemon-reload &&
sudo systemctl enable chatbot-worker-consulta-dash.service
```

Inicialização, depois da migração e verificações Django:

```bash
sudo systemctl start chatbot-worker-consulta-dash.service chatbot-webhook.service chatbot-worker-flow.service &&
systemctl show chatbot-worker-consulta-dash.service chatbot-webhook.service chatbot-worker-flow.service -p Id -p ActiveState -p SubState -p NRestarts --no-pager
```

Depois da conferência anterior:

```bash
sudo systemctl start chatbot-worker-funil.service chatbot-worker-consumo-meta.service &&
sudo systemctl start chatbot-worker-followup.service &&
sudo journalctl -u chatbot-worker-consulta-dash.service -u chatbot-worker-flow.service --since "5 minutes ago" -n 100 --no-pager
```

Não executar `git reset` para a versão anterior mantendo o novo esquema. Em falha,
manter os serviços afetados parados e corrigir para frente, ou restaurar conjuntamente
backup de banco e código sob procedimento controlado. Não há reversão destrutiva
automática que descarte o novo histórico de consultas.

## Capacidade e limites

Uma instância do novo serviço faz uma leitura por vez. Isso organiza a recuperação,
mas não acelera a planilha. Picos podem consumir o orçamento enquanto uma consulta
aguarda na fila e resultar em orgânico. Os locks permitem testar mais instâncias
futuramente sem reservar a mesma consulta; esta entrega mantém uma instância.

O deadline protege a decisão e a gravação, não promete terminar qualquer operação
de rede no exato milissegundo do prazo. O atendimento continua independente dessa
chamada. Quedas podem repetir GET, que não cria leads; nenhuma abertura usa POST
no dashboard. A duplicação rara de envio WhatsApp antes de persistir recibo continua
sendo uma fronteira externa já conhecida, não uma garantia de exatamente uma vez.

## Migração do histórico

Preservar os IDs e dados das consultas que existem hoje e seus vínculos com a
conversa referenciada. A estrutura antiga guardava somente a última consulta do
chat: não inventar registros anteriores. Contextos de conversas históricas ficam
intactos; IDs antigos dentro de JSONs são referências históricas, não novas FKs.
As novas conversas passam a ter registros independentes. Pendências antigas mantêm
seu início registrado e não ganham outros 300 segundos durante o deploy.
