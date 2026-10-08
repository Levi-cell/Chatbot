# Fluxo transacional dos workers

Referência: **V1.2.0**, revisada em **10/09/2026**.

Este guia descreve os caminhos já implementados no atendimento e no follow-up:
quais dados são confirmados juntos, o que permanece após uma falha e como o
processamento pode ser recuperado. Embora esteja em `docs/_V2/`, seu conteúdo
descreve o código atual e as garantias que futuras versões precisam preservar.

Os exemplos detalham as fronteiras transacionais. As regras completas ficam em
[Regras de negócio](../../REGRAS_DE_NEGOCIO.md); a organização dos módulos, em
[Workers](../../workers/README.md). A proposta de
[tracker Meta](tracker-meta-e-reparo-de-envio.md) continua sendo um plano futuro.

## 1. O que uma transação protege

Uma transação PostgreSQL confirma ou desfaz em conjunto as alterações feitas
desde o último commit. Ela não desfaz uma mensagem já enviada pela Meta nem
remove dados confirmados em checkpoints anteriores.

```text
Banco confirma o histórico do cliente
        -> Meta aceita o envio do bot
        -> banco confirma histórico do bot e efeitos da resposta
        -> banco confirma a finalização da fila
```

Uma queda entre esses passos deixa estados diferentes. O retry consulta os
registros persistidos para decidir se precisa enviar ou apenas concluir o trabalho.

Neste guia, “envio confirmado pela Meta” significa que a chamada de envio
retornou sucesso ao sender; não significa confirmação de entrega ou leitura
pelo cliente. Na V1.2.0, o webhook registra os eventos de status em log, mas não
os persiste para reconciliar uma tentativa cujo commit local falhou.

### Propriedade das transações

| Caminho | Dono da conexão, commits e rollback | Unidade de trabalho |
|---|---|---|
| Atendimento normal | `flow_worker.py` | Uma mensagem da fila |
| Reação ao follow-up | `flow_worker.py` | Uma mensagem da fila e seu marcador de retomada |
| Follow-up proativo | `followup_worker.py` | Uma conversa candidata por vez |

Repositórios e módulos de persistência recebem o cursor; eles não confirmam
a transação. Flow e follow-up compartilham o lock versionado da conversa,
mantendo conexões e transações próprias.

O worker do Funil possui outro ciclo, documentado em
[Worker do Funil](../../workers/README.md#worker-do-funil). Seus envios não
participam da transação final da resposta de atendimento.

### Limites reais de recuperação

- Um histórico já confirmado permite recuperar o trabalho sem repetir o envio
  correspondente, desde que os registros e o contexto estejam consistentes.
- A chamada à Meta e o commit local não formam uma transação distribuída.
  Sucesso externo seguido de falha local ainda pode produzir duplicidade.
- Timeout de envio pode deixar resultado externo desconhecido: ausência de
  confirmação local não prova que a Meta deixou de enviar.
- O flow usa `max_retry = 3`. No tratamento de erro genérico, a fila é reagendada
  por dois minutos enquanto houver tentativas; ao atingir o limite, a linha
  pode ser excluída da fila. Isso não apaga o histórico já confirmado.
- Espera por lock e conflito de vínculo usam reagendamento sem consumir uma
  tentativa de erro. Perda de posse do lock tem tratamento próprio.
- O follow-up proativo não consome essa fila nem seu contador de retry.
  Uma falha permite nova avaliação enquanto a conversa continuar elegível.

Portanto, persistência recuperável não significa retry ilimitado ou garantia
absoluta de conclusão do atendimento diante de falhas permanentes.

## 2. Salvar efeitos pela transição confirmada

O exemplo principal continua sendo a passagem da etapa 1 para a etapa 2:

```text
Cliente: Maria
Bot: Prazer, Maria! ...
Transição: 1 -> 2, evento nome_cliente_valido
Efeito: salvar cliente.nome = Maria
```

No caminho normal, `id_etapa_atual` representa o estado lido da conversa;
`id_etapa_origem_transicao` vem da etapa persistida da mensagem do cliente.
Em retry, essa origem pode diferir da etapa atual, pois a resposta anterior
já pode ter avançado o atendimento. `id_etapa_resultante` indica o destino
da resposta do bot.

Salvar o nome depende da aresta `1 -> 2`, não de a conversa estar
isoladamente na etapa 1 ou 2. Assim, um tratamento `1 -> 1` não salva como
nome uma pergunta financeira, uma mídia ou um texto inválido. Uma resposta
da etapa 2 também não vira nome do cliente.

O [resolver da etapa 1](../../workers/worker_flow/response_flow/etapas/resolver_etapa1.py)
valida a entrada e prepara a resposta. A
[persistência final](../../workers/worker_flow/transacoes/persistencia_resposta.py)
aplica os
[efeitos da transição](../../workers/worker_flow/transacoes/efeitos_transicao.py)
com o mesmo cursor usado para o histórico e a conversa.

| Movimento | Efeito atual |
|---|---|
| `None -> 1` | Apresenta o atendimento e inicializa a etapa, sem salvar nome |
| `1 -> 1` | Orienta ou repete a pergunta, sem salvar nome |
| `1 -> 2` | Salva o primeiro nome validado |
| `2 -> 3` | Persiste o destino do atendimento e cria o dependente inicial quando necessário |
| Repetição por follow-up | Reapresenta a etapa, sem executar os efeitos de transição |

A passagem `2 -> 3` já está implementada. As demais arestas continuam
submetidas ao mapa de transições do banco; IDs consecutivos não autorizam
avanço por si só.

## 3. Checkpoints do flow

O caminho abaixo supõe uma mensagem elegível, conversa ativa e aquisição
bem-sucedida do lock. Saídas por bloqueio, ordem da fila ou falta de lock
interrompem o ciclo antes do envio.

```text
1. Claim da fila como processing                              -> commit
2. Validação/criação do cliente e da conversa                 -> commit
3. Aquisição do lock e obtenção de lock_version               -> commit
4. Vínculo da fila + releitura da conversa + histórico
   do cliente + preparação da retomada, quando aplicável      -> commit
5. Renovação do lock antes do envio                          -> commit
6. Chamada do sender normal ou da repetição de follow-up      -> Meta
7. Conferência da posse + persistência final da resposta      -> commit
8. Nova conferência da posse + encerramento, se necessário,
   e fila sent                                               -> commit
9. Materialização do bloqueio no cache, quando aplicável
10. Unlock condicionado à versão                             -> commit
11. Fechamento da conexão
```

No passo 4, uma resposta já persistida pode ser recuperada em vez de registrar
uma nova interação pendente. A retomada concluída também possui regras próprias
para não sobrescrever um ciclo posterior.

No passo 7 do caminho normal ficam juntos: histórico do bot, movimento da
conversa, contadores de turnos e efeitos específicos da transição. A intenção
de encerramento é calculada nesse caminho; sua aplicação acontece no passo 8,
junto da finalização da fila. O cache só recebe um bloqueio já confirmado no banco.

Essa ordem está em
[flow_worker.py](../../workers/worker_flow/response_flow/flow_worker.py) e
[finalizacao_fila.py](../../workers/worker_flow/transacoes/finalizacao_fila.py).

### Vínculo da fila: reparo seguro ou reagendamento

O vínculo `fila_mensagens.id_conversa` continua sendo uma proteção de
integridade e ordenação. Ele não substitui as regras de turno, o lock da conversa
ou a busca da resposta específica à mensagem atual.

Depois de adquirir o lock, o
[repositório da fila](../../core/repositories/atendimento/fila.py) tenta:

1. Preencher uma fila em `processing` com vínculo vazio ou já correspondente.
2. Se o vínculo divergir, repará-lo somente quando não existir histórico
   associado àquela fila.
3. Se nenhuma linha puder ser vinculada, o flow registra
   `mensagem_conversa_vinculo_inconsistente` e reagenda por **300 segundos**,
   sem consumir tentativa de erro e sem enviar resposta.

Um exemplo é uma mensagem aceita perto do encerramento de uma conversa, que
depois precisa ser associada à nova conversa resolvida para o atendimento.
O reparo sem histórico registra `fila_vinculo_reparado`. Com histórico
conflitante, o worker não continua usando um vínculo incompatível.

### Lock: posse lógica e proteção de escrita

O lock lógico fica registrado na conversa e sobrevive aos commits.
`proteger_conversa()` confere `processing`, `lock_version` e validade
temporal, usando `SELECT ... FOR UPDATE`. Esse bloqueio de linha dura somente
até o fim da transação; não é mantido durante toda a chamada HTTP.

O código considera a posse válida dentro de **110 segundos**, renova antes
do envio e confere novamente antes de persistir e finalizar a fila. Se outra
execução adquirir uma versão nova, a antiga não pode confirmar alterações
nem liberar o lock da nova dona.

Sem conseguir adquirir o lock, o flow reagenda por **cinco segundos**, sem
consumir tentativa de erro. Se perder a posse depois, faz rollback e aguarda
a recuperação da fila, sem reescrevê-la como se ainda fosse seu proprietário.

## 4. Cenário: Meta falha ao enviar a etapa 2

Premissas: Maria respondeu à etapa 1; seu histórico já foi confirmado e
ainda não existe resposta do bot para essa entrada.

```text
Validar Maria
        -> tentar enviar etapa 2
        -> sender levanta ErroEnvioMeta
        -> rollback da transação atual
        -> tratar retry da fila
```

| Registro | Estado após rollback, antes do tratamento de retry |
|---|---|
| Histórico do cliente | Preservado pelo checkpoint anterior |
| Histórico dessa resposta do bot | Ausente |
| Etapa e nome dessa transição | Não confirmados; conversa permanece na etapa 1 |
| Último lado da conversa | Cliente |
| Fila | Ainda não foi marcada como sent |

Se houver tentativas e o reagendamento for confirmado, a fila volta a
`pending`. No retry, o sistema reconhece o histórico do cliente, valida
a mesma entrada e tenta enviar novamente. Se envio e persistência funcionarem,
salva histórico do bot, etapa 2 e nome na mesma transação.

A possibilidade de tentar novamente segue o limite descrito na seção 1.
Em timeout, o resultado externo pode ser desconhecido mesmo sem histórico local.

## 5. Cenário: Meta envia, mas banco falha depois

```text
Meta confirma a resposta
        -> contexto_envio.enviou = True
        -> falha ao salvar histórico, etapa ou nome
        -> rollback da transação final
        -> BancoFalhouAposEnvioMeta
        -> tratamento de retry
```

Com rollback confirmado, histórico do bot, avanço e nome dessa tentativa
não ficam parcialmente salvos. O histórico do cliente permanece, pois pertence
a um commit anterior. A fila não recebe `sent` por esse caminho.

O cliente, porém, pode já ter recebido a resposta. Um retry sem prova local
do envio poderá enviar novamente. O log
`banco_falhou_apos_envio_meta` sinaliza esse risco.

Se a conexão cair durante o próprio commit, a aplicação pode não saber se o
banco confirmou a transação. A recuperação precisa reler os registros:
se a resposta existir, reutiliza; se não existir, pode tentar enviar.

Essa é a fronteira entre o sucesso externo da Meta e a confirmação local.
O código atual não elimina essa janela por tracker ou reconciliação de status.

## 6. Cenário: banco confirma a resposta, mas o worker cai antes de sent

```text
Histórico do bot + etapa 2 + nome Maria                       -> commit
Queda antes da finalização da fila
```

O banco já contém os efeitos da resposta. A fila pode continuar em
`processing` até voltar a ser recuperável.

No retry:

1. O flow respeita a ordem das mensagens e readquire o lock.
2. `valida_historico()` encontra a resposta vinculada à entrada original.
3. Os caminhos com `resposta_bot_para_mensagem_atual` reutilizam essa resposta,
   sem chamar a Meta novamente.
4. A persistência reaplica ou repara os efeitos de forma idempotente.
5. Com a posse válida, a fila é finalizada.

O mesmo princípio vale se a resposta estiver salva, mas o commit de
finalização da fila falhar. Falhas de recuperação seguem a política de retry;
existir histórico não autoriza ignorar conflitos ou a perda do lock.

## 7. Cenário: Meta falha e o banco também falha ao reagendar

```text
ErroEnvioMeta
        -> rollback
        -> tentativa de reagendamento
        -> banco falha
        -> handler_generico_falhou
```

O handler registra sua própria falha. Isso não garante que um commit, rollback
ou unlock posterior também vá funcionar. O ciclo tenta liberar os recursos;
se uma exceção escapar, `iniciar_flow_worker.py` supervisiona o reinício.

A fila não deve ser marcada como `sent` sem resposta persistida. O histórico
confirmado anteriormente permanece; a recuperação depende de o banco voltar,
da elegibilidade da fila e da política de tentativas.

## 8. Cenário: recuperar nome sem reenviar a resposta

O caminho normal confirma nome, etapa e histórico juntos. Portanto, uma queda
comum não deve produzir “resposta confirmada, mas nome perdido” dentro dessa
mesma transação.

Ainda assim, o código permite reconstruir o nome no retry idempotente:

```text
Encontrar resposta do bot já persistida
        -> não reenviar
        -> reconhecer a origem 1 e o destino 2
        -> reconstruir primeiro_nome_cliente pela entrada original, se necessário
        -> reaplicar a persistência do nome
        -> confirmar e finalizar a fila
```

Essa defesa não valida texto arbitrário. Se o nome não puder ser reconstruído,
a persistência levanta erro e desfaz a transação atual. Não é permitido concluir
a aresta `1 -> 2` com nome vazio.

## 9. Cenário: perder o lock antes ou depois da chamada Meta

| Momento | Ação do flow | Consequência |
|---|---|---|
| Antes do envio | Rollback e log `lock_perdido` | Não chama a Meta nem reescreve a fila |
| Após envio confirmado, antes do commit final | Rollback e log `meta_confirmou_com_lock_perdido` | Não confirma com versão antiga; há risco de duplicidade externa |
| Após commit da resposta, antes de finalizar a fila | Rollback da transação de finalização | A resposta já salva poderá ser reutilizada na recuperação |
| Durante a liberação do lock | Unlock condicionado à versão | Não libera o lock adquirido por outra execução |

Perda de lock não segue cegamente o reagendamento de erro genérico: a fila
pode estar sendo recuperada por outro proprietário. Se o lock expirar ou o
processo morrer sem liberá-lo, sua recuperação depende das regras do banco.

## 10. Follow-up proativo: transação sem mensagem atual do cliente

O worker proativo parte de uma conversa candidata, não de um dequeue.
As principais condições implementadas são:

- conversa ativa, sem encerramento e na etapa **1–17**;
- `followup_stage = 0`;
- última mensagem da conversa enviada pelo bot há pelo menos **sete horas**;
- última mensagem do cliente ainda dentro da janela de **24 horas**, com
  **um minuto de margem** no SQL;
- ausência das pendências e bloqueios verificados na seleção.

Os dois relógios são independentes: bot há oito horas e cliente há 25 horas
não permitem envio; bot há oito horas e cliente há nove horas satisfazem
a parte temporal. Fila pendente, unidade ou bloqueios ainda podem impedir o envio.

O SQL completo está em
[followup.py](../../core/repositories/atendimento/followup.py); as condições
adicionais estão descritas no
[README dos workers](../../workers/README.md#worker-de-follow-up).

### Caminho de sucesso

```text
Selecionar candidata
        -> adquirir lock versionado                          -> commit
        -> proteger/renovar lock e reler elegibilidade        -> commit
        -> enviar "Você viu a minha mensagem?"                -> Meta
        -> proteger novamente e persistir:
           histórico do bot
           recibo followup_envio
           followup_stage = 1
           followup_last_sent_at e última interação do bot    -> commit
        -> liberar lock da própria versão                    -> commit
```

O [worker proativo](../../workers/worker_followup/followup_worker.py) confirma
histórico, recibo e estado da conversa juntos. O histórico desse lembrete deixa
`id_mensagem_fila` e `id_hash_cliente_origem` nulos: ele não responde a uma
entrada antiga nem libera turno A/B/C como se fosse sua resposta.

O recibo identifica a conversa e a âncora do ciclo, incluindo o horário da
mensagem no histórico particionado. Ele impede tratar um envio já confirmado
localmente como um novo lembrete para a mesma âncora.

### Falhas entre as fronteiras

| Fronteira | Estado persistido e recuperação |
|---|---|
| Candidata perdeu elegibilidade ou lock está ocupado | Não envia; continua para a próxima candidata |
| Sender falha sem confirmação local | Stage e recibo ficam preservados; a conversa poderá ser reavaliada |
| Meta confirma, mas a transação final sofre rollback | Histórico, recibo e stage dessa tentativa não são confirmados; log `followup_commit_falhou` e risco de duplicidade |
| Commit final funciona, mas processo cai antes do unlock | Stage 1 e recibo permanecem; não envia outro lembrete do ciclo ao recuperar |
| Uma candidata falha durante o lote | Registra a falha e segue para as demais; não desfaz sucessos já confirmados |

O lote padrão contém até 20 conversas processadas individualmente, com intervalo
de 60 segundos entre lotes. A paginação avança pelas âncoras; uma candidata que
falhou pode voltar em uma rodada posterior, não necessariamente no lote seguinte.
Se a janela do cliente expirar, ela deixa de ser elegível.

Uma entrada do cliente que chegue após o despacho não desfaz um envio já
confirmado pela Meta. O flow aguardará o lock e relerá o stage confirmado.
A releitura reduz conflitos, mas não torna o HTTP e a chegada de novos eventos
uma operação atômica.

## 11. Reação ao follow-up: repetição e reset atômicos

O flow verifica o stage e procura um marcador de retomada depois de adquirir
o lock e reler a conversa. O registro é feito por
[retorno_followup.py](../../workers/worker_flow/transacoes/retorno_followup.py).

Uma resposta normal já persistida para a entrada tem prioridade quando não
há marcador de retomada correspondente. Encontrar stage positivo não autoriza
transformar retroativamente aquele retry normal em reação ao follow-up.

Para uma nova reação:

```text
Stage positivo
        -> registrar followup_retomada para a entrada
        -> guardar histórico do cliente e última interação   -> commit
        -> renovar lock                                      -> commit
        -> repetir a etapa com a saudação de retorno          -> Meta
        -> conferir a posse e persistir juntos:
           histórico da repetição
           followup_retomada.concluida_em
           followup_stage = 0
           última interação do bot                           -> commit
        -> finalizar a fila                                  -> commit
```

A mensagem do cliente é armazenada, mas não é interpretada como resposta da
pergunta. `repeticao_followup.py` chama os senders das etapas usando os dados
persistidos, sem resolvers de negócio ou efeitos de transição.

A saudação é `Que bom te ver novamente, Maria!` quando existe nome salvo,
ou `Que bom te ver novamente!` quando não existe. O texto persistido inclui
a mesma saudação enviada.

A repetição preserva etapa, contadores de turnos, `lead_no_funil` e estado
de encerramento. Também preserva `followup_last_sent_at`: o reset do stage
não apaga a data do último lembrete confirmado. Stage zero, sem retomada
pendente, mantém o caminho normal e sua saudação reativa de três horas.

### Falha antes de confirmar a repetição

Se a Meta falhar, ou se o banco desfizer a transação final:

- o histórico do cliente e o marcador já confirmados permanecem;
- o stage continua positivo;
- a retomada continua aberta;
- a etapa não avança e a reação não vira resposta de negócio no retry.

Se a Meta enviou e o commit local falhou, repetir o envio ainda pode gerar
duplicidade, como no atendimento normal. O reset só acontece quando histórico
da repetição e conclusão da retomada forem confirmados juntos.

### Queda depois do reset, antes de finalizar a fila

```text
Repetição persistida + retomada concluída + stage zero       -> commit
Queda antes de sent
        -> retry encontra o marcador e a resposta persistida
        -> reutiliza a resposta sem enviar
        -> finaliza a fila sob lock válido
```

O marcador permite reconhecer a reação original mesmo com stage já zerado.
Esse replay não altera `last_interaction_at` nem zera um possível ciclo
posterior de follow-up. A busca da resposta continua específica à fila e ao
hash da mensagem do cliente.

Retomada concluída sem histórico correspondente, ou retomada aberta em contexto
incompatível, produz erro. Esses estados não autorizam envio ou avanço automático.

### Conversas antigas marcadas na migração

A migração inicial marcou as conversas antigas ativas com stage 1 e preservou
os valores anteriores em `followup_legado`, sem enviar lembrete retroativo.

Por isso, stage positivo não é prova de envio: pode representar o legado.
O flow usa a mesma repetição quando esse cliente volta. A repetição suporta
etapas **1–21**, inclusive etapas antigas após o agendamento; isso não amplia
a elegibilidade proativa, que permanece **1–17**. A etapa 22 não é repetível.

Não é necessário nem correto inventar uma data de envio para o legado.
`followup_last_sent_at` pode estar nulo nesse retorno e é comparado de forma
compatível com esse estado. A operação de migração está no
[guia de deploy](../../deploy/README.md#ativação-do-follow-up), sem necessidade
de reaplicá-la em atualizações posteriores.

## 12. Invariantes a preservar

1. Confirmar o histórico da entrada antes de uma nova resposta reativa.
2. Verificar a resposta específica da entrada antes de reenviar.
3. Confirmar histórico, movimento e efeitos da resposta normal na mesma transação.
4. Aplicar efeitos pela aresta validada, nunca apenas pelo número da etapa.
5. Finalizar a fila somente depois da persistência da resposta e sob posse válida.
6. Reler a conversa após o lock e proteger as escritas com sua versão.
7. Confirmar histórico, recibo e stage do lembrete proativo juntos.
8. Confirmar histórico da repetição, conclusão da retomada e reset do stage juntos.
9. Preservar um ciclo posterior quando uma reação antiga for recuperada.
10. Não usar o lembrete proativo como resposta de uma mensagem enfileirada.
11. Não tratar logs de status da Meta como recibos transacionais já persistidos.
12. Tornar explícitos os limites de retry e a janela de duplicidade externa.

## 13. Onde conferir esses cenários

| Assunto | Implementação ou teste |
|---|---|
| Ordem dos commits, vínculo e perda do lock | [flow_worker.py](../../workers/worker_flow/response_flow/flow_worker.py) e [test_worker_flow_runtime.py](../../tests/unit/test_worker_flow_runtime.py) |
| Persistência normal e efeitos da aresta | [persistencia_resposta.py](../../workers/worker_flow/transacoes/persistencia_resposta.py) e [efeitos_transicao.py](../../workers/worker_flow/transacoes/efeitos_transicao.py) |
| Reagendamento e limite de tentativas | [fila.py](../../core/repositories/atendimento/fila.py) e [expection_process.py](../../workers/tratamento_erros_externos/expection_process.py) |
| Envio proativo e continuação do lote | [followup_worker.py](../../workers/worker_followup/followup_worker.py) e [test_followup.py](../../tests/unit/test_followup.py) |
| Marcador de reação e replay | [retorno_followup.py](../../workers/worker_flow/transacoes/retorno_followup.py) e [repeticao_followup.py](../../workers/worker_flow/response_flow/repeticao_followup.py) |
| Rollback real, recibos, locks, migração e ciclo posterior | [test_followup_postgres.py](../../tests/integration/test_followup_postgres.py) |

Os testes de PostgreSQL exigem ambiente local descartável explícito, conforme
[Testes](../../tests/README.md#follow-up). Os envios Meta nesses testes são
simulados; o comportamento de entrega externa precisa de homologação própria.
