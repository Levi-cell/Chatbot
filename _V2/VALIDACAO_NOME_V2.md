# Validação de Nome - V1

## Objetivo

Este documento define como a V1 deve validar a resposta de nome na etapa 1.
A validação não tenta provar juridicamente que o nome existe. Ela tenta separar
entradas claramente fora de contexto de respostas plausíveis, sem bloquear
clientes reais por nomes raros, apelidos ou grafias incomuns.

O princípio da V1 é:

```text
Bloquear sujeira óbvia.
Aceitar primeiro nome simples plausível.
Usar base de nomes apenas quando a resposta tiver frase ou nome composto.
```

## Dependência planejada

A V1 poderá usar `names-dataset` como apoio para respostas com espaço, frase ou
nome composto.

Pontos relevantes da biblioteca:

- possui cerca de 730 mil primeiros nomes e 983 mil sobrenomes;
- traz país, ranking e gênero provável;
- a função `search(name)` retorna metadados de primeiro nome e sobrenome;
- a biblioteca informa uso aproximado de 3.2 GB de RAM ao carregar a base;
- por esse motivo, o carregamento deve ser preguiçoso e usado somente quando
  necessário.

Fonte: https://pypi.org/project/names-dataset/

## Regras obrigatórias

As regras abaixo são obrigatórias e independem do `names-dataset`.

### 1. Número invalida

Qualquer dígito invalida a resposta.

Exemplos inválidos:

```text
xavier99
99
sou putinha 69
&&33mano
&&33
```

Motivo:

```text
numero
```

### 2. Caractere especial invalida

Caracteres especiais invalidam a resposta.

São permitidos:

- letras, incluindo letras acentuadas;
- espaços;
- vírgula;
- ponto;
- til;
- acento agudo.

Exemplos inválidos:

```text
bernado&&
&&adasd
&&33mano
&&33
joao!
ana_maria
```

Exemplos permitidos para seguir à próxima regra:

```text
Carlos.
Maria, Oliveira
João
José
```

Motivo:

```text
caractere_invalido
```

### 3. Quatro letras repetidas em sequência invalidam

Quatro ou mais letras iguais seguidas invalidam a resposta. Três letras iguais
seguidas ainda são aceitas na V1.

Exemplos inválidos:

```text
pppp
ppppppp
Ppppjoao
aaaa
```

Exemplos aceitos por essa regra:

```text
ppp
annna
```

Motivo:

```text
repeticao_caractere
```

### 4. Termo pejorativo invalida

Termos pejorativos, ofensivos ou claramente impróprios invalidam a resposta,
mesmo quando aparecem em frase ou nome composto.

Exemplos inválidos:

```text
Puta
Puta da silva
meu nome é Vagabunda
Sou putinha 69
```

Motivo:

```text
termo_pejorativo
```

## Resposta com uma única palavra

Se a resposta tiver apenas uma palavra e passar pelas regras obrigatórias, ela
será aceita sem consultar o `names-dataset`.

Essa decisão é deliberada para evitar bloquear nomes raros, apelidos reais ou
grafias diferentes.

Exemplos válidos:

```text
Alice
Ysabella
Edinho
ppp
quero
```

Observação importante:

```text
quero
```

é um falso positivo aceito na V1. A palavra não parece nome, mas é melhor aceitar
esse caso raro do que bloquear nomes reais fora da base.

## Resposta com nome composto ou frase

Se a resposta tiver mais de uma palavra e passar pelas regras obrigatórias, o
sistema usará `names-dataset`.

O objetivo é encontrar a primeira palavra que pareça primeiro nome real.
Somente essa palavra será considerada como `primeiro_nome`.

Exemplos válidos:

```text
Meu nome é Carlos
```

Resultado:

```text
primeiro_nome = Carlos
```

```text
Carlos Augusto
```

Resultado:

```text
primeiro_nome = Carlos
```

```text
Maria Oliveira
```

Resultado:

```text
primeiro_nome = Maria
```

```text
Edcarlos dos Santos Pereira Filho
```

Resultado esperado se `Edcarlos` estiver na base:

```text
primeiro_nome = Edcarlos
```

## Casos válidos que podem ser considerados inválidos na V1

Estes casos representam limitações aceitas na V1.

### Frase com nome raro fora do dataset

Exemplo:

```text
Meu nome é Ysabella
```

Se `Ysabella` não estiver no `names-dataset`, a frase poderá ser tratada como
inválida.

Por outro lado:

```text
Ysabella
```

será aceita, porque resposta com uma única palavra não consulta o dataset.

### Nome composto com primeiro nome raro

Exemplo:

```text
Ysabella Maria
```

Se `Ysabella` não estiver no dataset e `Maria` estiver, o sistema poderá capturar:

```text
primeiro_nome = Maria
```

Esse risco é aceito na V1, porque muitas pessoas também usam o segundo nome no
atendimento. A V2 poderá melhorar essa decisão.

### Palavra única que não é nome

Exemplo:

```text
quero
```

Será aceita se não tiver número, caractere inválido, repetição de quatro letras
ou termo pejorativo.

Esse falso positivo é aceito para preservar nomes raros e apelidos.

## Casos inválidos mapeados

| Entrada | Status | Motivo |
|---|---|---|
| `xavier99` | inválido | contém número |
| `99` | inválido | contém número |
| `bernado&&` | inválido | contém caractere inválido |
| `&&adasd` | inválido | contém caractere inválido |
| `&&33mano` | inválido | contém número e caractere inválido |
| `&&33` | inválido | contém número e caractere inválido |
| `Puta` | inválido | termo pejorativo |
| `Puta da silva` | inválido | termo pejorativo |
| `meu nome é Vagabunda` | inválido | termo pejorativo |
| `Sou putinha 69` | inválido | contém termo pejorativo e número |
| `ppppppp` | inválido | quatro ou mais letras repetidas |
| `Ppppjoao` | inválido | quatro letras repetidas em sequência |

## Casos válidos mapeados

| Entrada | Status | Resultado esperado |
|---|---|---|
| `ppp` | válido | `primeiro_nome = Ppp` |
| `Ysabella` | válido | `primeiro_nome = Ysabella` |
| `Alice` | válido | `primeiro_nome = Alice` |
| `Edinho` | válido | `primeiro_nome = Edinho` |
| `Meu nome é Carlos` | válido | `primeiro_nome = Carlos` |
| `Carlos Augusto` | válido | `primeiro_nome = Carlos` |
| `Maria Oliveira` | válido | `primeiro_nome = Maria` |

## Mensagem de tratamento

Quando a resposta for inválida, a etapa 1 deverá responder sem avançar etapa:

```text
Olha sua mensagem parece estar fora do contexto e também não aceitamos nomes e apelidos pejorativos. Recomendamos usar seu primeiro nome ou apelido, exemplo: Pedro.
Me diz, qual o seu primeiro nome?
```

## O que a V2 deve melhorar

A V2 poderá revisar estas limitações:

- validar frases com nomes raros fora do dataset;
- diferenciar melhor palavra comum de primeiro nome quando a resposta tem uma
  única palavra;
- reconhecer apelidos brasileiros frequentes;
- aceitar hífen ou apóstrofo se forem necessários para nomes reais;
- criar uma lista própria de nomes e apelidos observados em produção;
- salvar evidências de validação para análise posterior;
- avaliar uso de modelo leve ou serviço especializado se a regra heurística
  começar a bloquear clientes reais.

