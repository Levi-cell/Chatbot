# Reparo opcional de nome na transicao 1 -> 2

## Classificacao

```text
Prioridade: opcional
Obrigatorio para a V2: nao
Implementar somente se testes, logs ou producao demonstrarem um caso real
```

Este documento registra uma defesa hipotetica contra corrupcao de dados,
regressao futura ou alteracao indevida do fluxo. Ele nao descreve uma falha
conhecida da V1 e nao deve competir com funcionalidades obrigatorias da V2.

Nao existe porcentagem confiavel para essa hipotese. Sem ocorrencias reais ou
testes que reproduzam o problema, nao se deve atribuir a ela uma probabilidade
como `0,1%`.

## Garantias existentes na V1

A etapa 1 nao aceita nome vazio como resposta valida.

O fluxo atual e:

```text
texto invalido
-> tratamento da etapa 1
-> conversa permanece na etapa 1

texto valido
-> primeiro nome e extraido
-> etapa 2 e enviada usando esse nome
-> nome e persistido na transicao 1 -> 2
```

Antes de enviar a etapa 2, `etapa1.py` executa a validacao do nome.
Somente um resultado valido fornece `primeiro_nome` ao sender da etapa 2.

Depois do envio:

```text
contexto_envio["primeiro_nome_cliente"] = primeiro_nome
```

Na persistencia final, o nome e resolvido nesta ordem:

```text
1. primeiro_nome_cliente presente no contexto de envio;
2. nova validacao do texto original da mensagem atual.
```

Se nenhum nome puder ser resolvido:

```text
-> registra erro
-> levanta ValueError
-> rollback da transacao final
-> fila nao vira sent
-> mensagem segue para retry
```

A funcao SQL de atualizacao do cliente tambem rejeita nome vazio antes de
executar o `UPDATE`.

Portanto, o codigo atual nao oferece um caminho normal para:

```text
aceitar nome vazio
salvar nome vazio
avancar conscientemente da etapa 1 para a etapa 2 sem nome
```

## Queda do processo nao esvazia o nome

Uma queda do worker nao apaga somente o nome e permite que o restante do ciclo
continue. A queda encerra o ciclo inteiro.

No retry, o worker volta a ler a mesma mensagem persistida e reconstrui o
contexto. A mensagem do cliente tambem ja foi registrada no historico antes do
envio da resposta do bot.

Assim, o risco operacional real nessa janela nao e o nome se tornar vazio. O
risco real e:

```text
1. Meta confirma o envio da etapa 2;
2. worker ou banco falha antes do commit final;
3. banco nao possui a resposta do bot;
4. retry pode enviar a mesma resposta novamente.
```

Esse risco pertence ao mecanismo de tracker/status Meta e ao reparo de envio,
documentados separadamente na V2.

## Transacao correta

Na V1, depois que a Meta confirma o envio, a transacao final persiste em
conjunto:

```text
historico da resposta do bot
etapa atual da conversa
nome do cliente
```

Somente depois ocorre o commit.

Nao se recomenda criar um commit isolado de `cliente.nome` imediatamente depois
do envio. Isso poderia produzir um estado parcial:

```text
nome salvo
historico do bot ausente
conversa ainda na etapa 1
fila ainda processing
```

Manter esses efeitos na mesma transacao preserva a coerencia do ciclo.

## Quando esta defesa opcional faria sentido

Uma implementacao adicional somente deve ser considerada se houver evidencia
de pelo menos um destes casos:

```text
- regressao futura remove primeiro_nome_cliente do contexto;
- mensagem atual sofre corrupcao ou alteracao indevida;
- migracao futura muda a origem do texto usado no retry;
- teste de integracao reproduz transicao 1 -> 2 sem nome resolvido;
- logs de producao registram repetidamente nome_nao_reconstruido.
```

Falha de Meta, queda normal do worker ou rollback do banco, isoladamente, nao
comprovam essa anomalia.

## Possivel defesa futura

Se um caso real for comprovado, a V2 pode criar um reparo dedicado:

```text
workers/worker_flow/reparos/reparo_transicao_nome.py
```

Ordem segura de reparo:

```text
1. consultar o nome presente no contexto do ciclo;
2. revalidar o texto da mensagem atual da fila;
3. consultar a copia da mesma mensagem no historico atual;
4. se ainda nao houver nome, interromper a transicao;
5. registrar estado tecnico de reparo ou dead-letter;
6. decidir um fallback controlado sem salvar nome vazio.
```

Nao usar como fallback automatico:

```text
- cliente.nome de uma conversa antiga;
- mensagens de outras conversas;
- nomes inferidos de outro atendimento.
```

O numero pode ter mudado de titular ou o atendimento pode estar sendo feito
para outra pessoa.

## Excecao opcional na regra de turno

Uma coluna como `status_anomalia` e uma excecao no webhook nao sao requisitos
da V2.

Elas so devem ser consideradas se a anomalia for reproduzida e se o retry
normal realmente mantiver a conversa bloqueada.

Nesse caso, a regra precisaria ser explicita:

```text
1. mensagem A esta aberta;
2. worker comprovou falha de reconstrucao do nome na transicao 1 -> 2;
3. A recebeu um estado tecnico especifico;
4. tentativas seguras de reparo falharam;
5. webhook pode aceitar B como substituta controlada;
6. C, D e mensagens seguintes continuam bloqueadas enquanto B estiver aberta.
```

O webhook nunca deve liberar um novo turno apenas porque `cliente.nome` esta
vazio. Esse e um estado normal antes da conclusao da etapa 1.

## Relacao com tracker Meta

O tracker ajuda a determinar se uma resposta foi enviada pela Meta antes de uma
falha no banco:

```text
tracker confirmado
-> nao reenviar a resposta
-> reconstruir e persistir o estado interno
```

Ele nao e necessario para validar um nome que continua presente na mensagem
original. Sua implementacao e importante para evitar duplicidade de envio, mas
nao torna obrigatorio criar um fluxo de anomalia de nome.

## Decisao para a V2

```text
Obrigatorio:
- manter validacao que rejeita nome vazio;
- manter persistencia atomica da transicao;
- implementar tracker/status conforme o plano proprio da V2.

Opcional:
- estado status_anomalia;
- dead-letter especifica para nome;
- excecao de turno no webhook;
- mensagem de fallback exclusiva para perda de nome.
```

Conclusao:

```text
A logica atual nao permite nome vazio como valido.
O reparo adicional fica registrado apenas como defesa opcional.
Ele nao deve ser implementado sem evidencia concreta de necessidade.
```
