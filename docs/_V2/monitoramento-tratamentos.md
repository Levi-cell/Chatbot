# Monitoramento de Tratamentos na V2

## Decisao aprovada

Na V2, o proprio `historico_mensagens` sera a fonte de verdade das ocorrencias
de tratamento.

Cada resposta do bot devera informar:

```text
categoria_resposta
tipo_tratamento
```

Uma view relacional usara o historico para apresentar dados do atendimento,
conversa, etapa, unidade, cliente e dependente. Relatorios agregados poderao ser
calculados periodicamente sem transformar o worker em um gerador de dashboards.

## Objetivo

Na V1, tratamentos de midia, pergunta financeira e resposta fora do contexto
sao reconhecidos durante o ciclo e aparecem nos logs e no historico normal da
conversa. Entretanto, o historico nao informa semanticamente se uma resposta do
bot foi:

```text
uma etapa normal
ou
um tratamento
```

Na V2, essa classificacao permitira responder:

```text
Quantos tratamentos de midia aconteceram?
Qual etapa recebe mais perguntas financeiras?
Quantas respostas fora do contexto ocorreram por conversa?
Quais tratamentos aparecem com maior frequencia em cada unidade?
Qual mensagem ou botao precisa ser melhorado?
```

Essa evolucao serve para observabilidade, auditoria e decisoes de produto. Ela
nao controla a navegacao do atendimento.

## Separacao de responsabilidades

```text
chatbot.etapa
-> catalogo dos estados da conversa

chatbot.etapa_transicao
-> mapa autorizado de origem + evento -> destino

chatbot.historico_mensagens
-> fonte dos acontecimentos individuais, inclusive tratamentos

view de atendimento
-> leitura relacional para relatorios e dashboards

job periodico ou materialized view
-> agregacoes sem aumentar a responsabilidade do worker
```

Tratamentos sao eventos de negocio, mas nao sao eventos transicionais.

```text
Transicao:
etapa 2 + destino_atendimento_definido -> etapa 3

Tratamento:
etapa 2 + mensagem de midia -> permanece na etapa 2
```

Tratamentos nao devem ser cadastrados como autoarestas:

```text
2 + tratamento_midia -> 2
2 + tratamento_financeiro -> 2
```

Isso enfraqueceria o significado de `evento_transicao`, violaria a separacao
entre navegacao e tratamento e dificultaria a reconstrucao idempotente.

## Novas colunas do historico

### `categoria_resposta`

Classifica a finalidade da mensagem do bot.

Valores iniciais:

```text
etapa
tratamento
```

Regras:

```text
Mensagem do cliente:
categoria_resposta = NULL

Resposta normal do bot:
categoria_resposta = etapa

Resposta de tratamento:
categoria_resposta = tratamento
```

Uma restricao `CHECK` deve impedir valores desconhecidos.

### `tipo_tratamento`

Identifica o motivo especifico quando `categoria_resposta = tratamento`.

Valores iniciais possiveis:

```text
midia_nao_suportada
pergunta_financeira
contexto_invalido
nome_invalido
opcao_invalida
```

Regras:

```text
categoria_resposta = tratamento
-> tipo_tratamento obrigatorio

categoria_resposta = etapa
-> tipo_tratamento deve ser NULL

quem_enviou = cliente
-> categoria_resposta e tipo_tratamento devem ser NULL
```

Uma restricao `CHECK` deve preservar essas combinacoes.

## Exemplos no historico

Resposta normal:

| quem_enviou | id_etapa | categoria_resposta | tipo_tratamento |
|---|---:|---|---|
| bot | 2 | `etapa` | `NULL` |

Tratamento financeiro:

| quem_enviou | id_etapa | categoria_resposta | tipo_tratamento |
|---|---:|---|---|
| bot | 2 | `tratamento` | `pergunta_financeira` |

Tratamento de midia:

| quem_enviou | id_etapa | categoria_resposta | tipo_tratamento |
|---|---:|---|---|
| bot | 2 | `tratamento` | `midia_nao_suportada` |

## Responsabilidade minima do worker

O worker nao calculara contagens nem atualizara tabelas de dashboard.

Sua unica responsabilidade adicional sera persistir duas informacoes que ja
existem semanticamente no `contexto_envio`:

```python
{
    "tratamento": True,
    "tipo_tratamento": "midia_nao_suportada",
    "id_etapa_resultante": 2,
}
```

Na insercao da resposta do bot:

```text
tratamento = True
-> categoria_resposta = tratamento
-> tipo_tratamento = valor do contexto

tratamento ausente ou False
-> categoria_resposta = etapa
-> tipo_tratamento = NULL
```

Essas colunas devem ser persistidas na mesma transacao final que registra a
resposta do bot. Portanto, nao criam um novo commit nem uma segunda unidade
transacional.

## Idempotencia

O historico do bot ja e vinculado especificamente a mensagem do cliente por:

```text
id_conversa
id_mensagem_fila
id_hash_cliente_origem
```

As novas classificacoes pertencem a essa mesma resposta. Se um retry encontrar
a resposta do bot ja registrada:

```text
nao envia novamente
nao insere outra ocorrencia
reutiliza categoria_resposta e tipo_tratamento do historico existente
continua a recuperacao idempotente
```

A consulta e a normalizacao da resposta existente devem passar a carregar as
duas novas colunas.

## View relacional do atendimento

Nome conceitual sugerido:

```text
chatbot.vw_atendimento_mensagens
```

A view deve partir de:

```text
chatbot.historico_mensagens
```

e conectar:

```text
historico_mensagens.id_conversa
-> conversa.id_conversa

conversa.id_unidade
-> unidade.id_unidade

conversa.id_cliente
-> cliente.id_cliente

historico_mensagens.id_etapa
-> etapa.id_etapa

conversa.id_conversa
-> dependente.id_conversa
```

Na estrutura atual, existe no maximo um dependente vinculado diretamente a cada
conversa por `uq_dependente_conversa`. Por isso, o `LEFT JOIN` com dependente
nao deve multiplicar as linhas do historico.

O relacionamento com dependente deve ser `LEFT JOIN`, pois atendimentos
realizados para o proprio cliente nao possuem dependente.

### Colunas sugeridas para a view

Identificacao da mensagem:

```text
id_mensagem
received_data_hora
quem_enviou
conteudo_texto
tipo_mensagem
status_envio
id_mensagem_fila
id_hash_msg
id_hash_cliente_origem
```

Classificacao:

```text
categoria_resposta
tipo_tratamento
id_etapa
nome_etapa
```

Conversa:

```text
id_conversa
status_ativa
status_dependente
iniciou_em
finalizou_em
```

Unidade:

```text
id_unidade
nome_unidade
phone_number_id
status_pagamento
```

Cliente:

```text
id_cliente
nome_cliente
telefone_cliente
email_cliente
idade_cliente
```

Dependente:

```text
id_dependente
nome_dependente
telefone_dependente
email_dependente
idade_dependente
```

Dados pessoais devem ser expostos apenas em views e rotas que realmente
precisem deles. Dashboards estatisticos devem preferir identificadores,
contagens e dados agregados.

## Relatorios

A view permitirá consultas como:

```sql
SELECT
    id_unidade,
    nome_unidade,
    id_etapa,
    nome_etapa,
    tipo_tratamento,
    COUNT(*) AS quantidade
FROM chatbot.vw_atendimento_mensagens
WHERE categoria_resposta = 'tratamento'
GROUP BY
    id_unidade,
    nome_unidade,
    id_etapa,
    nome_etapa,
    tipo_tratamento;
```

Relatorios possiveis:

- tratamentos por etapa;
- tratamentos por unidade;
- tratamentos por conversa;
- tratamentos em atendimento proprio ou para dependente;
- taxa de respostas invalidas por etapa;
- frequencia de perguntas financeiras;
- frequencia de midias em etapas que exigem texto;
- comparacao antes e depois da melhoria de uma mensagem ou botao.

## View comum ou materialized view

Comecar com uma view comum:

```text
consulta sempre os dados atuais
nao duplica armazenamento
nao exige rotina de refresh
```

Quando o volume justificar, avaliar uma materialized view:

```text
consultas de dashboard mais rapidas
refresh periodico
dados podem ficar alguns minutos atrasados
```

Outra opcao futura e um job periodico que grave apenas totais agregados. Esse
job deve ler o historico classificado; nunca deve tentar deduzir tratamentos
pela repeticao de `id_etapa`.

## Por que nao inferir tratamentos por etapas repetidas

Etapas repetidas nao significam necessariamente tratamento:

```text
cliente envia "Oi"             -> etapa 1
bot pergunta o nome            -> etapa 1
cliente responde "Maria"       -> etapa 1
```

Existem tres registros seguidos na etapa 1 sem qualquer tratamento.

Repeticoes tambem podem ocorrer por:

- inicializacao;
- retry;
- recuperacao idempotente;
- pergunta e resposta pertencentes a mesma etapa;
- tratamento verdadeiro.

Por isso, `categoria_resposta` e `tipo_tratamento` devem ser marcadores
explicitos, e nao inferencias posteriores.

## Tabela `tratamento_ocorrencia`

Uma tabela separada de ocorrencias nao faz parte da primeira proposta da V2.
Ela duplicaria informacoes que o historico classificado ja consegue fornecer.

Ela somente deve ser reconsiderada se surgir uma necessidade concreta de:

- retencao independente do historico;
- auditoria com ciclo de vida proprio;
- grande diferenca entre a retencao das mensagens e das metricas;
- integracao analitica que exija uma tabela de fatos separada.

Mesmo nesse caso, a tabela serviria para observabilidade e nao se conectaria a
`etapa_transicao`.

## Fora do escopo da V1

A V1 continua utilizando:

```text
logs
historico de mensagens atual
contexto_envio.tratamento
contexto_envio.tipo_tratamento
```

Nenhuma coluna, view ou responsabilidade adicional deve ser adicionada agora.

## Checklist da implementacao futura

- adicionar `categoria_resposta` ao historico particionado;
- adicionar `tipo_tratamento` ao historico particionado;
- criar restricoes `CHECK`;
- adaptar inserts e consultas do historico;
- adaptar a normalizacao da resposta existente;
- garantir persistencia no mesmo commit da resposta do bot;
- testar retry sem duplicacao;
- criar `vw_atendimento_mensagens`;
- usar `LEFT JOIN` para dependente;
- criar indices somente a partir de consultas reais;
- revisar exposicao de dados pessoais e LGPD;
- comecar com view comum;
- avaliar materialized view ou job apenas quando o volume justificar.
