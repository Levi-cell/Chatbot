# Plano teórico — retorno após inatividade e worker de follow-up

## Objetivo do documento

Este documento registra o contrato funcional e os cuidados técnicos da integração entre:

- o `worker_flow`, responsável por processar a mensagem recebida do cliente e conduzir a conversa; e
- o futuro `worker_followup`, responsável por enviar até três lembretes quando o cliente não responde.

O documento é intencionalmente teórico. Ele define decisões, estados, invariantes, transações, concorrência, retries e critérios de aceite, sem pressupor que cada seção corresponda a um arquivo ou a uma função específica.

A coluna canônica usada neste documento é `conversa.followup_stage`. Expressões como “stage de follow-up” representam essa mesma coluna.

---

# Parte 1 — `worker_flow` e a nova lógica de retorno

## 1. Responsabilidade do `worker_flow`

O `worker_flow` continua sendo o único responsável por interpretar uma nova mensagem do cliente e decidir se a conversa:

- avança de etapa;
- recebe um tratamento e repete a etapa atual;
- repete obrigatoriamente a etapa porque o cliente respondeu a um follow-up;
- não deve receber resposta por bloqueio, encerramento, duplicidade ou outra proteção já existente.

A nova funcionalidade é aditiva. Ela não deve reorganizar os guards estáveis da V1.0.7 nem enfraquecer:

- a ordenação das mensagens;
- o bloqueio comercial de 30 dias;
- a denylist/bloqueios da Meta e as proteções de flood;
- o lock da conversa e seu `lock_version`;
- a barreira de idempotência baseada no histórico;
- os rollbacks e retries existentes;
- a persistência do histórico real enviado ao cliente;
- a autocura de contexto.

## 2. Dois caminhos separados por `followup_stage`

Existem dois comportamentos de retorno. A fonte de verdade que os separa é `conversa.followup_stage`.

| Estado observado | Interpretação | Comportamento |
|---|---|---|
| `followup_stage = 0` e inatividade menor que 3 horas | Resposta normal | Executa o fluxo atual sem saudação de retorno |
| `followup_stage = 0` e inatividade igual ou superior a 3 horas | Retorno espontâneo do cliente | Acrescenta a saudação e mantém validação, tratamento e avanço normais |
| `followup_stage > 0` | Resposta a uma sequência de follow-up | Ignora semanticamente a resposta para o fluxo de negócio, não avança e repete obrigatoriamente a etapa atual |

`NULL` legado deve ser normalizado como `0`.

Um valor positivo acima do máximo esperado também deve ser tratado pelo `worker_flow` como uma resposta a follow-up: é mais seguro repetir e zerar o ciclo do que interpretar a mensagem e avançar indevidamente. O valor anômalo deve ser registrado para diagnóstico.

Valor negativo, não inteiro ou estruturalmente inválido representa corrupção de estado. Nesse caso, o processamento deve falhar de forma fechada, sem enviar nem avançar, seguindo o retry/alerta operacional do projeto.

## 3. Regra final da saudação

A saudação é padronizada para os dois caminhos:

- etapa atual igual a 1, ou nome canônico indisponível: `Que bom te ver aqui novamente!`;
- etapas posteriores, com nome válido: `Que bom te ver aqui novamente, {nome}!`.

A regra final permite a saudação ainda na etapa 1, sem nome. Depois da etapa 1, o nome deve vir de `cliente.nome`, já reconciliado com o cliente canônico.

Se uma etapa posterior estiver sem nome por uma anomalia de dados, o sistema não deve quebrar nem exibir `None`, string vazia ou um valor improvisado. Deve usar a versão sem nome e registrar a inconsistência.

A saudação deve ser composta centralmente com a resposta já produzida pelo fluxo. Ela não cria um novo catálogo de mensagens para todas as etapas e não altera:

- texto, botões, identificadores ou eventos da etapa;
- ordem de mensagens já definida pelo resolver;
- tratamento escolhido para uma resposta inválida;
- efeitos transacionais de uma transição válida.

Se a resposta for composta por mais de uma mensagem, a saudação deve ser acrescentada uma única vez no início da resposta composta, preferencialmente na primeira mensagem textual útil. Ela nunca deve ser repetida em cada fragmento, botão ou mídia.

O conteúdo persistido em `historico_mensagens` deve ser exatamente o conteúdo efetivamente enviado, já com a saudação. Assim, retries e auditorias enxergam a mesma mensagem que o cliente recebeu.

## 4. Como calcular as três horas

O intervalo deve ser calculado dentro da conversa atual e da unidade atual:

```text
inatividade = horário original da mensagem atual do cliente
              - horário da última mensagem confirmada do bot na mesma conversa
```

Regras obrigatórias:

1. A mensagem do bot deve pertencer ao mesmo `id_conversa`.
2. A consulta deve buscar uma mensagem efetivamente registrada como saída do bot, não apenas uma tentativa de envio.
3. O horário da mensagem atual deve ser o horário original do evento recebido, e não o momento em que o worker retirou o item da fila.
4. Datas devem ser comparadas como `TIMESTAMPTZ`, com referência consistente em UTC.
5. O limite é inclusivo: exatamente 3 horas já ativa a saudação.
6. Ausência de mensagem anterior do bot não ativa a saudação.
7. Intervalo negativo ou timestamp futuro não ativa a saudação e deve gerar log de anomalia.

Usar o horário de processamento causaria um falso retorno em mensagens que ficaram atrasadas na fila. Por isso, backlog, retry e indisponibilidade temporária não podem transformar artificialmente uma resposta rápida do cliente em uma resposta após três horas.

## 5. Relação entre as marcas de 3 e 7 horas

Em operação normal, o retorno espontâneo acontece no intervalo de 3 horas até antes do primeiro follow-up, previsto para 7 horas.

Entretanto, o relógio de 7 horas, isoladamente, não comprova que um follow-up foi enviado. O discriminador autoritativo é o banco:

- se `followup_stage = 0`, o `worker_flow` usa o caminho normal, mesmo que já tenham passado mais de 7 horas;
- se `followup_stage > 0`, o `worker_flow` usa obrigatoriamente o caminho de resposta a follow-up.

Essa regra evita inventar um follow-up que pode não ter sido enviado por manutenção, falha, atraso ou indisponibilidade do futuro worker.

## 6. Caminho A — retorno com `followup_stage = 0`

Este caminho preserva integralmente a semântica atual da conversa.

### 6.1 Resposta válida

Fluxo esperado:

1. O cliente envia uma mensagem.
2. O `worker_flow` passa pelos guards, lock e idempotência normais.
3. A inatividade é igual ou superior a 3 horas.
4. `followup_stage` continua igual a 0.
5. O resolver da etapa valida normalmente a resposta.
6. A transição e seus efeitos continuam iguais aos da V1.0.7.
7. A resposta da próxima etapa é gerada normalmente.
8. A saudação de retorno é acrescentada no início.
9. A mensagem é enviada e persistida pelos mecanismos já existentes.

Resultado conceitual:

```text
Que bom te ver aqui novamente, {nome}!

{mensagem normal da etapa de destino}
```

Na etapa 1, a saudação não inclui o nome, ainda que a própria resposta recebida contenha um nome válido.

### 6.2 Resposta inválida

Fluxo esperado:

1. A inatividade é igual ou superior a 3 horas.
2. `followup_stage` continua igual a 0.
3. O validador e o seletor de tratamento trabalham normalmente.
4. O tratamento adequado é mantido.
5. A etapa atual é repetida conforme o fluxo existente.
6. A saudação é acrescentada antes do tratamento/repetição.
7. `turnos_sem_avanco` segue a regra normal já existente para uma resposta inválida.

Resultado conceitual:

```text
Que bom te ver aqui novamente, {nome}!

{tratamento selecionado}
{repetição normal da etapa atual}
```

Não deve existir um tratamento especial apenas porque houve três horas de inatividade. A inatividade altera a apresentação da resposta, não sua interpretação.

## 7. Caminho B — resposta com `followup_stage > 0`

Este caminho representa o cliente respondendo depois que o futuro `worker_followup` enviou um ou mais lembretes.

### 7.1 Regra funcional

Quando `followup_stage > 0`, o `worker_flow` deve:

1. reconhecer que há um ciclo de follow-up ativo;
2. registrar normalmente a nova mensagem do cliente no histórico;
3. ignorar seu conteúdo para validação da etapa neste processamento;
4. não executar validação de negócio da resposta;
5. não escolher tratamento;
6. não avançar de etapa;
7. repetir exatamente `conversa.id_etapa_atual`;
8. acrescentar a saudação padronizada;
9. não incrementar `turnos_sem_avanco`;
10. não executar efeitos de transição, funil ou encerramento derivados da mensagem ignorada;
11. enviar e persistir a repetição;
12. zerar `followup_stage` somente depois que a resposta do bot estiver duravelmente persistida.

O termo “ignorar semanticamente” se limita ao fluxo de negócio e à triagem. Guards operacionais, de segurança, bloqueio, identidade, idempotência e eventuais comandos obrigatórios de conformidade continuam tendo prioridade antes desta decisão.

### 7.2 Por que não validar a resposta

O follow-up pode provocar respostas como “oi”, “voltei”, um emoji ou uma reação ao lembrete. Interpretar esse conteúdo como resposta direta à pergunta anterior poderia:

- selecionar um tratamento indevido;
- incrementar a proteção de turnos sem avanço;
- avançar com uma resposta casual que coincida acidentalmente com um validador;
- misturar o texto do follow-up com a pergunta de negócio anterior.

A repetição limpa da etapa restabelece o contexto antes de voltar ao fluxo normal.

### 7.3 Renderização da etapa atual

A repetição deve renderizar a mensagem existente da etapa atual sem passar pelo resolver que interpreta a resposta recebida.

Essa operação deve ser conceitualmente “reemitir a etapa atual”, e não “processar novamente a etapa”. Portanto, ela não pode:

- criar uma transição;
- atualizar dados de triagem a partir da resposta ignorada;
- mudar profissão, dependente, e-mail ou outras respostas de negócio;
- marcar avanço;
- disparar o funil;
- encerrar a conversa;
- incrementar `turnos_sem_avanco`.

Mensagens dinâmicas podem continuar consultando o contexto necessário para serem renderizadas, mas a renderização deve ser livre de efeitos colaterais de negócio.

Se não houver `id_etapa_atual`, se a conversa estiver encerrada ou se a etapa não puder ser repetida, o sistema deve falhar de forma fechada e registrar a anomalia. Não deve adivinhar uma etapa.

### 7.4 Etapa 1

Se o follow-up ocorreu enquanto a conversa ainda esperava o nome:

```text
Que bom te ver aqui novamente!

{mensagem existente da etapa 1}
```

O conteúdo recebido não é aceito como nome nesse processamento. Depois da repetição, a próxima mensagem do cliente volta a ser processada normalmente, pois o ciclo terá sido zerado.

### 7.5 Etapas posteriores

```text
Que bom te ver aqui novamente, {nome}!

{mensagem existente de conversa.id_etapa_atual}
```

## 8. `followup_stage` é a fonte de verdade

Não é necessário exigir a contagem de mensagens consecutivas do bot como condição de negócio.

Seria esperado observar:

| `followup_stage` | Mensagens consecutivas do bot antes da resposta do cliente |
|---:|---:|
| 1 | 2: resposta da etapa + primeiro follow-up |
| 2 | 3: resposta da etapa + dois follow-ups |
| 3 | 4: resposta da etapa + três follow-ups |

Essa contagem pode ser usada como telemetria ou auditoria, mas não como gate. Ela é redundante, aumenta o custo da consulta e pode bloquear a retomada por uma divergência rara de histórico.

Se o banco afirma `followup_stage > 0`, o comportamento seguro é repetir a etapa. Se, por uma anomalia, um follow-up foi enviado sem que o stage fosse gravado, o `worker_flow` seguirá o caminho normal. Isso não é crítico: o cliente ainda será atendido, podendo avançar ou receber tratamento conforme a resposta.

## 9. Momento correto para ler o estado

O contexto inicialmente carregado pode ficar desatualizado enquanto o worker aguarda o lock. Por isso, a decisão sobre `followup_stage` deve usar um valor confirmado depois da aquisição do lock da conversa ou uma atualização protegida por condição e `lock_version`.

Sequência segura:

1. carregar o contexto necessário para localizar a conversa;
2. adquirir o lock;
3. confirmar que o lock pertence ao worker e guardar `lock_version`;
4. reler `status_ativa`, `id_etapa_atual`, `followup_stage` e dados necessários;
5. escolher o caminho;
6. persistir com fencing/condições compatíveis com a versão adquirida.

Um worker não pode escolher o caminho normal com um snapshot antigo se, antes do lock, o `worker_followup` acabou de gravar `followup_stage = 1`.

## 10. Ordem dos guards

A decisão de retorno não deve ocorrer antes das proteções essenciais. A ordem conceitual permanece:

1. retirada ordenada da fila;
2. proteção contra mensagem anterior ainda pendente;
3. reconstrução e autocura do contexto;
4. bloqueios e estado da conversa;
5. aquisição do lock da conversa;
6. vínculo da mensagem com a conversa;
7. histórico/idempotência da entrada;
8. releitura do estado protegido;
9. decisão entre caminho normal e resposta a follow-up;
10. geração e envio;
11. persistência do contexto final;
12. finalização da fila;
13. liberação do lock com `lock_version`.

O caminho de follow-up não pode ser usado para contornar um bloqueio, reabrir uma conversa encerrada ou responder uma mensagem duplicada.

## 11. Persistência e reset do ciclo

### 11.1 Estado a persistir

Após responder com sucesso a um `followup_stage > 0`, a persistência final deve, na mesma unidade transacional lógica:

- registrar a mensagem real do bot no histórico;
- manter `id_etapa_atual` inalterado;
- manter `turnos_sem_avanco` inalterado;
- não registrar transição de etapa;
- definir `followup_stage = 0`;
- atualizar os campos normais de última interação/último remetente conforme o contrato atual da conversa.

O reset funcional acordado é exclusivamente `followup_stage = 0`. Enquanto o stage estiver em 0, `followup_last_sent_at` não participa da decisão do `worker_flow` nem do vencimento do primeiro follow-up de um novo ciclo. Portanto, a Parte 1 não precisa limpar esse timestamp. Ele pode ser preservado como dado operacional/auditoria; uma política diferente só deve ser adotada quando o `worker_followup` for implementado e após decisão explícita, sem alterar a fonte de verdade do ciclo.

### 11.2 O que nunca deve acontecer

O stage não pode ser zerado:

- quando a mensagem apenas é retirada da fila;
- antes do envio;
- quando o sender retorna erro;
- quando a renderização falha;
- antes de a resposta do bot ser persistida;
- por um worker que perdeu o lock/fencing.

Zerar antes da hora permitiria que um retry interpretasse a mesma mensagem semanticamente e avançasse a etapa, quebrando o contrato.

## 12. Idempotência e retries

A nova lógica deve preservar a regra já existente: antes de enviar, o worker verifica se já há no histórico uma resposta do bot vinculada ao mesmo evento do cliente.

### 12.1 Retry antes do envio

Se nada foi enviado, o retry pode executar novamente a decisão com o estado ainda ativo.

### 12.2 Envio confirmado e persistência concluída

O retry encontra a resposta no histórico, não envia novamente e marca/finaliza o item conforme o fluxo atual. Como o reset ocorreu junto da persistência, `followup_stage` já estará em 0.

### 12.3 Envio externo ocorreu, mas houve falha local

Essa é a fronteira crítica, pois a API externa e o PostgreSQL não participam da mesma transação.

O projeto deve continuar usando a barreira de idempotência existente e a correlação reproduzível entre a resposta e o evento do cliente. Se o histórico comprovar que a resposta já foi registrada, o retry não reenvia.

Essa barreira, porém, não elimina a pequena janela já mapeada na V1.0.7: a Meta pode aceitar o envio e o processo falhar antes de persistir a comprovação no PostgreSQL. Nesse caso, o retry não tem evidência local do sucesso externo e ainda pode duplicar a mensagem. Fechar completamente essa janela exigiria suporte idempotente do provedor ou outro protocolo durável de entrega, o que permanece fora do escopo desta funcionalidade. A nova lógica não deve ampliar essa janela nem prometer semântica de entrega exatamente uma vez.

Na implementação nova, histórico da resposta e reset do stage devem integrar a mesma transação local; portanto, “resposta persistida sem reset” não é um estado normal. Se uma inconsistência antiga ou intervenção manual produzir esse estado, qualquer reparo só pode zerar o ciclo após correlacionar o evento e o stage exatos, além de validar o `lock_version`. Nunca basta observar genericamente `followup_stage > 0`.

O reset deve ser uma transição condicionada, por exemplo, do stage observado para 0. Um worker antigo não pode zerar um novo ciclo de follow-up que começou depois.

### 12.4 Prefixo único

O prefixo deve ser calculado para a resposta corrente e anexado uma única vez. Em retry, a mensagem persistida é autoritativa; o sistema não pode reaplicar a saudação sobre um texto que já a contém.

## 13. Concorrência e lock de 110 segundos

O `worker_flow` continua usando o lock de conversa já existente:

- lock com menos de 110 segundos é considerado atual e não pode ser tomado;
- lock com 110 segundos ou mais pode ser tratado como stale e sofrer takeover;
- cada aquisição incrementa/usa `lock_version` para identificar a posse daquela versão do lock;
- a liberação continua condicionada à versão adquirida, impedindo que um worker antigo destrave uma aquisição posterior.

Toda decisão de follow-up precisa acontecer dentro dessa proteção. A nova funcionalidade não cria um segundo lock paralelo e não zera `processing` de uma conversa que pertence a outro worker.

Na V1.0.7, `lock_version` protege diretamente a posse e a liberação do lock, mas não transforma automaticamente todas as persistências já existentes em escritas cercadas por fencing. Por isso, a transição crítica introduzida nesta Parte 1 — zerar o stage observado — deve ser condicionada ao `id_conversa`, ao stage lido sob lock e à versão ainda pertencente ao worker, com conferência do número de linhas afetadas. Isso é uma proteção aditiva da nova lógica; não pressupõe reescrever todos os rollbacks ou todas as persistências estáveis do fluxo atual.

O takeover após 110 segundos também não cancela fisicamente um processo antigo nem uma chamada HTTP que já esteja em andamento. Pode existir uma fronteira rara de sobreposição quando um worker fica parado por mais que a tolerância e depois volta a executar. Confirmar a posse imediatamente antes do envio e condicionar a persistência reduz esse risco, mas não torna atômicos o lock PostgreSQL e o envio para a Meta. Essa limitação deve permanecer mapeada, sem ser apresentada como garantia absoluta de exclusão externa.

## 14. Compatibilidade com `wa_id`, `user_id` e unidades

O estado de follow-up pertence à conversa, portanto ao par canônico `(id_cliente, id_unidade)` representado por ela. Ele não é global para o cliente.

Consequências:

- uma conversa em follow-up em uma unidade não interfere em outra unidade;
- alternar entre `wa_id` e `user_id` deve resolver para a mesma conversa canônica naquela unidade antes de ler o stage;
- um merge de cliente provisório precisa preservar o `followup_stage` da conversa que continuar ativa;
- a saudação usa o nome do cliente canônico após a reconciliação;
- o envio continua usando o resolvedor central de destinatário: `wa_id` prioritário e `user_id` como fallback permitido pelo plano de compatibilidade.

Nenhuma chave de Redis baseada apenas em `wa_id` ou apenas em `user_id` deve decidir este comportamento. O PostgreSQL da conversa é a fonte de verdade.

## 15. Pseudofluxo decisório do `worker_flow`

```text
processar mensagem do cliente
  executar guards existentes
  adquirir lock da conversa
  confirmar histórico/idempotência
  reler conversa sob proteção

  se followup_stage > 0:
      persistir entrada normalmente
      não interpretar resposta para o negócio
      renderizar conversa.id_etapa_atual sem efeitos
      acrescentar saudação de retorno
      enviar
      persistir resposta mantendo etapa e turnos_sem_avanco
      zerar followup_stage
  senão:
      calcular intervalo pela hora original do evento
      executar resolver normal
      se intervalo >= 3 horas:
          acrescentar saudação de retorno
      enviar e persistir pelo fluxo normal

  finalizar fila
  liberar lock com fencing
```

## 16. Logs e observabilidade

Cada decisão deve gerar log estruturado sem expor desnecessariamente dados pessoais. Campos úteis:

- `id_conversa`;
- `id_unidade`;
- `id_cliente`;
- identificador/hash do evento;
- etapa atual;
- `followup_stage` observado;
- intervalo desde a última mensagem do bot;
- caminho escolhido: `normal`, `retorno_3h` ou `resposta_followup`;
- etapa mantida ou transição realizada;
- stage antes e depois;
- `lock_version`;
- resultado do envio e da persistência.

Alertas relevantes:

- stage negativo, não inteiro ou acima do máximo esperado;
- etapa ausente em conversa ativa;
- falta de nome depois da etapa 1;
- tentativa de reset com stage/version divergente;
- resposta persistida sem conclusão do reset;
- timestamps futuros ou intervalos negativos.

## 17. Critérios de aceite e testes do `worker_flow`

A implementação futura deve provar, no mínimo:

1. Menos de 3 horas e stage 0 não acrescenta saudação.
2. Exatamente 3 horas e stage 0 acrescenta saudação.
3. Resposta válida após 3 horas avança normalmente.
4. Resposta inválida após 3 horas recebe o tratamento normal e repete.
5. Etapa 1 usa a saudação sem nome.
6. Etapas posteriores usam o nome canônico.
7. Nome ausente não quebra o envio.
8. Stage positivo sempre vence a decisão baseada em tempo.
9. Stage positivo com resposta aparentemente válida não avança.
10. Stage positivo com resposta inválida não executa tratamento.
11. Stage positivo com texto, botão, reação ou mídia repete a etapa sem interpretar o conteúdo para o negócio.
12. A repetição por follow-up não incrementa `turnos_sem_avanco`.
13. A repetição não cria transição nem efeitos de funil.
14. O stage só é zerado depois do envio e da persistência.
15. Falha de envio conserva o stage.
16. Se a resposta já está comprovada no histórico, falha/retry não a envia novamente; a rara janela entre sucesso na Meta e persistência local continua sendo a limitação conhecida da V1.0.7.
17. Retry de mensagem já respondida não reaplica o prefixo.
18. Mensagem atrasada na fila usa o timestamp original e não gera saudação falsa.
19. Um snapshot anterior ao lock não prevalece sobre stage recém-atualizado.
20. Lock recente é respeitado e lock stale segue a tolerância de 110 segundos.
21. A mesma pessoa em duas unidades tem estados de follow-up independentes.
22. `wa_id` e `user_id` associados levam à mesma conversa e ao mesmo stage na unidade.
23. Bloqueios e conversas encerradas continuam impedindo resposta.

---

# Parte 2 — futuro `worker_followup`

## 1. Responsabilidade exclusiva

O `worker_followup` será um orquestrador independente. Sua única responsabilidade de negócio é localizar conversas ativas sem resposta do cliente e enviar, no máximo, três mensagens proativas de follow-up em intervalos de sete horas.

Ele não deve:

- interpretar respostas do cliente;
- validar etapa;
- avançar ou retroceder etapa;
- executar tratamento;
- incrementar `turnos_sem_avanco`;
- enviar dados ao funil;
- finalizar atendimento por conta própria, salvo uma regra futura explicitamente aprovada;
- criar uma segunda conversa;
- alterar identidade de cliente.

O processamento da reação do cliente pertence ao `worker_flow`, conforme a Parte 1.

## 2. Máquina de estados do follow-up

`followup_stage` registra quantos follow-ups do ciclo atual foram enviados e persistidos com sucesso.

| Stage atual | Estado | Próxima ação possível |
|---:|---|---|
| 0 | Nenhum follow-up enviado | Enviar o primeiro após 7 horas de inatividade |
| 1 | Primeiro follow-up enviado | Enviar o segundo após mais 7 horas sem resposta |
| 2 | Segundo follow-up enviado | Enviar o terceiro após mais 7 horas sem resposta |
| 3 | Terceiro e último enviado | Não enviar novos follow-ups |

Transições válidas do `worker_followup`:

```text
0 -> 1
1 -> 2
2 -> 3
```

Transição realizada pelo `worker_flow` quando o cliente responde e a retomada é persistida:

```text
1, 2 ou 3 -> 0
```

O `worker_followup` não faz `3 -> 0`. Sem resposta do cliente, o ciclo permanece encerrado em 3 e não gera novos envios.

## 3. Relógio de sete horas

### 3.1 Primeiro follow-up

Com stage 0, a referência é a última resposta ordinária e confirmada do bot na conversa. O primeiro follow-up fica elegível quando:

```text
agora >= última mensagem do bot + 7 horas
```

e ainda não existe resposta posterior do cliente.

### 3.2 Segundo e terceiro follow-ups

Depois do primeiro envio, `followup_last_sent_at` registra o horário do follow-up efetivamente enviado e persistido.

Os próximos vencimentos são:

```text
stage 1: agora >= followup_last_sent_at + 7 horas
stage 2: agora >= followup_last_sent_at + 7 horas
```

Em condições normais, os envios acontecem aproximadamente em 7, 14 e 21 horas desde a resposta original do bot.

### 3.3 Sem rajada de recuperação

Em operação normal, intervalos sucessivos de sete horas produzem o calendário aproximado de 7, 14 e 21 horas. Se o worker ficar desligado ou atrasado, ele nunca deve enviar dois ou três follow-ups em rajada na mesma aquisição de lock ou na mesma rodada para “compensar” o período parado.

A conversa fechou o calendário normal, mas não definiu uma política de recuperação para atrasos operacionais. Antes de implementar a Parte 2, deve ser escolhida explicitamente uma destas âncoras para o vencimento seguinte: sete horas após o envio anterior efetivamente concluído ou manutenção do calendário originalmente vencido. A opção segura recomendada é contar novamente a partir do envio confirmado, porém ela permanece uma decisão da futura implementação, e não uma regra de negócio já aprovada neste documento. Independentemente da escolha, rajada de compensação continua proibida.

### 3.4 Fonte de tempo

- Os cálculos devem usar timestamps do PostgreSQL em `TIMESTAMPTZ`.
- O tempo do banco deve ser a referência comum entre workers.
- `followup_last_sent_at` representa apenas o último follow-up enviado com sucesso no ciclo ativo.
- `last_interaction_at` pode continuar sendo atualizado conforme o contrato da conversa, mas não substitui a semântica explícita de `followup_last_sent_at` para os estágios 1 e 2.

## 4. Elegibilidade de uma conversa

Uma conversa só pode ser candidata se, no momento da seleção e novamente depois do lock:

1. estiver ativa;
2. possuir unidade ativa e configuração válida de envio;
3. possuir etapa atual válida;
4. não estiver encerrada ou em finalização;
5. não estiver bloqueada comercialmente por 30 dias;
6. não estiver em denylist/bloqueio Meta ou flood aplicável àquela unidade;
7. tiver `last_message_from = 'bot'`;
8. não tiver nova mensagem do cliente posterior à referência usada;
9. não tiver mensagem inbound pendente na fila para a mesma conversa/identidade;
10. tiver `followup_stage` igual a 0, 1 ou 2;
11. tiver atingido o prazo correspondente ao stage;
12. permitir a resolução segura do destinatário;
13. não estar sob lock atual de outro worker.

A consulta inicial apenas encontra candidatos. Nenhum resultado dessa consulta autoriza o envio sem releitura depois do lock.

## 5. Seleção eficiente

O índice existente sobre `last_message_from`, `followup_stage` e `last_interaction_at` pode apoiar a busca inicial do stage 0 se a última interação representar corretamente a resposta ordinária do bot. Ele não deve ser declarado suficiente, sem medição, para os stages 1 e 2, cujo prazo usa `followup_last_sent_at`. Quando a Parte 2 for implementada, a consulta real deve ser validada com `EXPLAIN`; somente então se decide se é necessário um índice parcial ou composto que também contemple o timestamp do último follow-up.

A consulta deve ser limitada, ordenada por vencimento e executada em pequenos lotes para não manter transações longas.

O worker não deve bloquear toda a tabela enquanto envia para a Meta. Cada conversa é tratada isoladamente pelo mecanismo normal de lock/fencing.

Não é necessário Redis como fonte de verdade do agendamento. Redis pode ser usado como otimização futura, mas o PostgreSQL deve permitir reconstruir integralmente o estado após reinício, perda de cache ou troca de processo.

## 6. Fluxo seguro de processamento

Para cada candidata:

1. identificar a conversa e o stage esperado;
2. tentar adquirir o mesmo lock usado pelo `worker_flow`;
3. se o lock tiver menos de 110 segundos, ignorar a candidata nesta rodada;
4. se o lock estiver stale há pelo menos 110 segundos, permitir takeover com novo `lock_version`;
5. reler a conversa sob proteção;
6. confirmar novamente todos os critérios de elegibilidade;
7. verificar se apareceu mensagem inbound pendente ou resposta do cliente;
8. confirmar que o stage ainda é o mesmo selecionado;
9. construir a mensagem de follow-up correspondente;
10. obter uma chave idempotente determinística para aquele ciclo, `id_conversa` e stage de destino;
11. consultar se aquele follow-up já foi enviado/persistido;
12. imediatamente antes do despacho externo, confirmar novamente a posse do lock e a ausência de inbound/resposta do cliente já comprometidos no banco;
13. enviar somente se ainda não houver comprovação e os guards finais continuarem válidos;
14. persistir histórico e transição de stage;
15. atualizar `followup_last_sent_at` com o horário do envio confirmado;
16. atualizar os campos normais de última mensagem do bot;
17. efetuar commit;
18. liberar o lock apenas se ainda possuir o mesmo `lock_version`.

Se qualquer requisito deixar de ser verdadeiro na releitura, o worker abandona a candidata sem envio e sem alterar o stage.

## 7. Conteúdo das mensagens de follow-up

As mensagens específicas do primeiro, segundo e terceiro follow-up serão definidas quando o `worker_followup` for implementado.

Mesmo podendo ter textos diferentes, todas devem respeitar:

- no máximo três envios por ciclo;
- identificação clara do stage que as originou;
- persistência exata do conteúdo enviado;
- ausência de avanço de etapa;
- ausência de tratamento ou validação;
- ausência de efeitos de funil;
- compatibilidade com o sender central e com a unidade correta.

A saudação `Que bom te ver aqui novamente...` não precisa ser a mensagem proativa do `worker_followup`. Ela pertence à resposta posterior do `worker_flow`, quando o cliente efetivamente retorna.

## 8. Atualização atômica do stage

Depois de um envio confirmado, a atualização deve ser protegida pelo estado observado. Conceitualmente:

```text
atualizar conversa
   de followup_stage = N
   para followup_stage = N + 1
 somente se:
   a conversa continua ativa,
   o stage ainda é N,
   o último remetente continua sendo o bot,
   e o lock_version pertence a este worker
```

O número de linhas atualizadas deve ser exatamente um. Zero significa que o contexto mudou e exige reconciliação; nunca autoriza um segundo envio automático.

Na mesma persistência lógica devem ser registrados:

- histórico da mensagem do bot;
- `followup_stage = N + 1`;
- `followup_last_sent_at`;
- `last_message_from = 'bot'`;
- `last_interaction_at`, se esse for o contrato vigente para toda mensagem enviada;
- identificador idempotente do follow-up.

## 9. Idempotência na fronteira Meta/PostgreSQL

O envio HTTP para a Meta e o commit do PostgreSQL não são atomicamente distribuídos. O caso crítico é:

1. a Meta aceita o follow-up;
2. o processo cai antes do commit local;
3. outro ciclo encontra stage antigo e tenta enviar novamente.

Cada tentativa precisa de uma identidade reproduzível. O stage sozinho não basta, pois uma mesma conversa pode encerrar um ciclo, receber nova resposta do bot e futuramente iniciar outro ciclo também pelo stage 1.

Cada ciclo deve possuir uma âncora estável, como o identificador/hash da resposta ordinária do bot que antecedeu a primeira espera de sete horas. A identidade pode seguir o conceito:

```text
followup:{id_conversa}:{ancora_do_ciclo}:{stage_de_destino}
```

Essa identidade pode ser implementada pelo mecanismo de hash/origem já adotado no histórico. Ela permite reconhecer de forma inequívoca aquilo que já foi persistido. Os requisitos locais são:

- consultar a identidade antes do envio;
- impedir mais de um registro local para o mesmo follow-up lógico;
- impedir reenvio quando já houver comprovação local do envio;
- diferenciar os três stages;
- diferenciar ciclos antigos e novos da mesma conversa;
- manter a mesma âncora durante os três follow-ups de um ciclo.

A âncora não precisa obrigatoriamente de uma nova coluna se puder ser derivada e persistida de forma inequívoca no histórico/origem da mensagem. O requisito é que ela sobreviva a reinícios e não dependa apenas da memória do processo.

Uma identidade ou restrição única apenas no PostgreSQL não fecha a janela em que a Meta aceitou a mensagem e o processo caiu antes de gravar a comprovação local. Sem idempotência oferecida pelo endpoint da Meta ou um protocolo durável adicional de entrega/reconciliação, o retry ainda pode repetir o despacho nessa fronteira. Uma outbox comum, por si só, torna a intenção durável, mas também não prova que uma chamada externa sem chave idempotente foi aceita antes da queda.

Se a API da Meta fornecer um identificador idempotente aplicável ao endpoint usado, ele deve ser aproveitado, mas a proteção local continua necessária. Qualquer mecanismo mais forte deve ser tratado como endurecimento futuro e não como capacidade já garantida pela V1.0.7 ou por este plano.

## 10. Concorrência entre `worker_followup` e `worker_flow`

Os dois workers disputam o mesmo lock de conversa. Não deve existir um lock exclusivo do follow-up separado do lock do fluxo.

### 10.1 `worker_flow` obtém o lock primeiro

1. A resposta do cliente é processada.
2. A conversa passa a refletir a nova interação.
3. Ao obter o lock depois, o `worker_followup` relê o estado.
4. Ele encontra mensagem do cliente, fila pendente resolvida ou mudança de contexto e não envia.

### 10.2 `worker_followup` obtém o lock primeiro

1. O follow-up é enviado e o stage é incrementado.
2. O lock é liberado.
3. O `worker_flow` recebe a mensagem do cliente.
4. Ele relê `followup_stage > 0` e executa a repetição obrigatória da Parte 1.

### 10.3 Mensagem entrou na fila enquanto o follow-up estava sendo preparado

Mesmo com `last_message_from = 'bot'`, pode existir uma mensagem do cliente já recebida e ainda não consolidada na conversa. Por isso, o `worker_followup` precisa consultar a fila inbound antes do envio, depois de obter o lock.

Se houver mensagem válida pendente para aquela conversa ou para os aliases canônicos daquela identidade na unidade, o follow-up é cancelado. O `worker_flow` deve ter prioridade para responder ao cliente.

Essa prioridade possui uma fronteira temporal objetiva: uma mensagem inbound já comprometida antes da checagem final cancela o follow-up; uma mensagem que chega depois do início do despacho externo pode cruzar com ele. O lock da conversa não bloqueia o webhook de receber e enfileirar o evento. Nesse cruzamento raro, a mensagem do cliente não pode ser perdida: depois da persistência do follow-up, o `worker_flow` observará o stage positivo e aplicará a repetição obrigatória da Parte 1. Eliminar também essa fronteira exigiria um protocolo de coordenação mais amplo e não deve ser prometido implicitamente.

## 11. Fencing e lock stale

O contrato de 110 segundos é igual ao do `worker_flow`:

- antes de 110 segundos, outro worker não toma a conversa;
- a partir de 110 segundos, um worker pode recuperar o lock;
- o takeover produz uma nova versão;
- a transição de stage e o unlock introduzidos pelo novo worker precisam conferir a versão;
- o processo antigo não pode atualizar o stage nem liberar o lock da nova versão.

O `worker_followup` nunca deve “destravar por precaução” uma conversa pertencente a outro worker. Toda liberação deve ser condicionada ao próprio fencing token.

O fencing do banco não revoga uma requisição Meta que já começou. Se um processo exceder os 110 segundos e sofrer takeover enquanto ainda executa uma chamada externa, pode existir sobreposição na fronteira de envio. Por isso, o futuro worker precisa reduzir o tempo sob lock, revalidar a posse imediatamente antes do despacho e nunca interpretar `lock_version` como cancelamento remoto. Renovação de lease, fencing mais amplo ou idempotência do provedor são endurecimentos possíveis, mas não fazem parte da regra de negócio fechada aqui.

## 12. Falhas e recuperação

### 12.1 Falha antes do envio

- não incrementa stage;
- não atualiza `followup_last_sent_at`;
- libera o lock se ainda for dono;
- a candidata poderá reaparecer numa rodada futura.

### 12.2 Falha de envio

- stage permanece inalterado;
- registra erro e política de retry;
- não simula mensagem de bot no histórico;
- não começa o próximo intervalo de sete horas.

### 12.3 Envio confirmado e falha de banco

- se existir comprovação local, a chave idempotente impede novo registro e novo despacho;
- se a queda aconteceu antes da comprovação local, permanece a pequena janela de possível reenvio na fronteira Meta/PostgreSQL;
- o retry não pode inventar sucesso, stage ou timestamp sem evidência reconciliável;
- uma persistência condicionada não incrementa o stage duas vezes;
- não envia o stage seguinte na mesma rodada.

### 12.4 Falha de liberação do lock

- o lock não fica permanente;
- após 110 segundos, outro worker pode recuperá-lo;
- `lock_version` impede o worker antigo de desfazer o novo lock.

### 12.5 Estado inesperado

- `followup_stage >= 3`: não enviar;
- stage negativo ou inválido: falhar fechado e alertar;
- `followup_last_sent_at` ausente em stage 1 ou 2: não adivinhar o prazo; registrar e reconciliar;
- conversa sem etapa ou sem destinatário seguro: não enviar.

## 13. Bloqueios e encerramentos

Antes de cada follow-up, o worker deve consultar as mesmas fontes canônicas usadas pelos demais fluxos:

- bloqueio comercial de 30 dias por cliente e unidade;
- aliases comprovados de `wa_id` e `user_id`;
- bloqueios de flood;
- denylist/bloqueio Meta;
- status da conversa e da unidade.

Um cache pode acelerar a consulta, mas divergência de cache não pode autorizar um envio proibido. A lógica deve continuar isolada por unidade; bloqueio em uma unidade não bloqueia automaticamente outra, salvo regra explícita do tipo de bloqueio.

Conversa encerrada entre a seleção e o lock é descartada na releitura.

## 14. Compatibilidade com a identidade futura da Meta

O follow-up deve usar a conversa canônica já resolvida:

- `phone_number_id` identifica o sender/unidade;
- `wa_id` é o destinatário prioritário quando disponível;
- `user_id` é o fallback escopado pela unidade conforme o plano de compatibilidade;
- `username` é apenas informação complementar e não participa do agendamento;
- `display_phone_number` não substitui `phone_number_id`.

O mesmo cliente pode ter stages independentes em unidades diferentes. Nenhuma consulta deve escolher uma conversa apenas pelo `wa_id` sem considerar a unidade e o vínculo canônico.

## 15. Reinício de um novo ciclo

Quando o cliente responde a qualquer follow-up e o `worker_flow` conclui a repetição:

```text
followup_stage = 0
```

A resposta do bot que repetiu a etapa passa a ser a nova mensagem ordinária de referência. Se o cliente voltar a ficar sete horas sem responder, um novo ciclo pode começar do stage 0.

O reset funcional obrigatório é apenas do stage. Com `followup_stage = 0`, o timestamp antigo de follow-up não participa do vencimento do primeiro envio do novo ciclo; ele pode permanecer como informação operacional/auditoria. Limpar ou preservar `followup_last_sent_at` deve ser decidido explicitamente na implementação da Parte 2, sem condicionar o comportamento correto do `worker_flow`.

Assim:

1. não há herança indevida do ciclo anterior;
2. o máximo de três mensagens vale por período contínuo sem resposta;
3. uma resposta real do cliente reinicia a oportunidade de follow-up;
4. o histórico antigo continua disponível para auditoria.

## 16. Observabilidade do `worker_followup`

Logs estruturados devem incluir:

- `id_conversa`, `id_cliente` e `id_unidade`;
- stage atual e stage de destino;
- horário-base e horário de vencimento;
- motivo de elegibilidade ou descarte;
- presença de inbound pendente;
- lock e `lock_version`;
- chave idempotente;
- resultado da Meta;
- resultado da persistência;
- duração do processamento.

Métricas úteis:

- candidatas examinadas;
- primeiro, segundo e terceiro follow-ups enviados;
- descartes por resposta pendente;
- descartes por bloqueio ou encerramento;
- conflitos de lock;
- takeovers stale;
- retries de envio;
- reconciliações pós-envio;
- clientes que responderam em cada stage;
- conversas que chegaram ao stage 3 sem resposta.

Logs não devem expor telefone, `wa_id`, `user_id`, nome ou conteúdo integral sem necessidade operacional e proteção adequada.

## 17. Critérios de aceite e testes do `worker_followup`

A futura implementação deve cobrir, no mínimo:

1. Com 6h59min não envia o primeiro follow-up.
2. Com exatamente 7 horas fica elegível para o primeiro; o envio ocorre após seleção, lock e guards.
3. Primeiro envio muda 0 para 1.
4. Sete horas depois do primeiro envia o segundo e muda 1 para 2.
5. Sete horas depois do segundo envia o terceiro e muda 2 para 3.
6. Stage 3 nunca envia um quarto follow-up.
7. Atraso do worker não produz rajada de compensação, e a política de âncora escolhida para o próximo prazo é testada explicitamente.
8. Cliente respondeu antes do lock: não envia.
9. Há inbound pendente na fila: não envia.
10. Conversa encerrada ou bloqueada: não envia.
11. Unidade inativa ou sender inválido: não envia.
12. Dois workers concorrentes, sem takeover stale nem falha na fronteira externa, produzem uma única transição local e um único follow-up comprovado.
13. Lock com menos de 110 segundos é respeitado.
14. Lock stale pode ser recuperado com nova versão.
15. Worker antigo não atualiza o stage nem libera o lock após perder a versão.
16. Falha antes ou durante o sender não incrementa o stage.
17. Com comprovação local, o retry não reenvia; sucesso Meta sem commit local é exercitado e registrado como a janela residual conhecida, sem falsa promessa de exatamente uma entrega.
18. Atualização condicionada com stage divergente afeta zero linhas e não reenvia.
19. `followup_last_sent_at` começa o próximo intervalo apenas após sucesso.
20. Cada follow-up é registrado exatamente como foi enviado.
21. Follow-up não altera etapa, respostas de triagem, `turnos_sem_avanco` ou funil.
22. `wa_id` e `user_id` resolvem o destinatário dentro da mesma unidade.
23. A mesma pessoa em duas unidades mantém ciclos independentes.
24. Resposta em stages 1, 2 e 3 leva o `worker_flow` à repetição obrigatória e ao reset.
25. Depois do reset, uma nova inatividade pode iniciar um novo ciclo no stage 0.

## 18. Invariantes finais da integração

O desenho completo deve manter permanentemente estas garantias:

1. `followup_stage` é a fonte de verdade do ciclo ativo.
2. Tempo sozinho nunca prova que um follow-up foi enviado.
3. O `worker_followup` só envia; o `worker_flow` processa a reação.
4. Uma resposta com stage positivo nunca avança de etapa no primeiro processamento.
5. A repetição causada por follow-up nunca pune o cliente em `turnos_sem_avanco`.
6. O stage só avança após follow-up enviado e persistido.
7. O stage só zera após a resposta de retomada do bot enviada e persistida.
8. Os dois workers usam o mesmo lock, respeitam a tolerância de 110 segundos e condicionam suas novas transições à versão possuída; takeover stale continua sendo uma fronteira rara de possível sobreposição externa.
9. Retries não reenviam quando existe comprovação local; a janela entre aceite da Meta e commit PostgreSQL permanece explicitamente mapeada.
10. Follow-up é escopado por conversa e unidade, nunca global por cliente.
11. Bloqueios, encerramentos e identidade canônica continuam tendo precedência.
12. Todo estado local confirmado da lógica é reconstruível pelo PostgreSQL e não depende de estado efêmero para permanecer correto; um envio externo não confirmado localmente continua sendo a exceção de fronteira já documentada.
