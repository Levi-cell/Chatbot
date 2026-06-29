# Validacao de nome: V1 atual e evolucoes da V2

## Objetivo da V1

A V1 valida o nome localmente, sem IA, servico externo ou base extensa de
nomes. O processamento foi dividido conceitualmente em duas responsabilidades:

```text
texto do cliente
-> extrair candidato a nome
-> validar candidato e declaracao completa
-> nome aceito ou tratamento sem avancar a etapa
```

Essa separacao permite aceitar apresentacoes naturais sem procurar nomes em
qualquer posicao de uma frase.

## Contrato enriquecido sem quebrar o fluxo

O resultado continua expondo os campos utilizados pela etapa 1:

```text
valido
primeiro_nome
motivo
```

Tambem passa a expor:

```text
status = valido | invalido | ambiguo
confianca = numero entre 0.0 e 1.0
```

O worker continua avancando somente quando `valido=True`. Os novos campos sao
informativos e preparam evolucoes futuras sem alterar sender, persistencia,
retry ou transacoes. O proprio modelo impede a criacao de um resultado valido
com primeiro nome vazio.

## Organizacao interna

Os componentes especializados ficam em:

```text
detector_etapas/nome/modelos.py
detector_etapas/nome/seguranca.py
detector_etapas/nome/lexicos.py
```

O `detector_nome.py` permanece como contrato publico e orquestrador.

## Formatos aceitos

### Resposta direta

Um nome simples, composto ou acompanhado de sobrenomes conhecidos pode ser
enviado diretamente:

| Entrada | Nome resultante |
|---|---|
| `Pedro` | `Pedro` |
| `Pedro.` | `Pedro` |
| `Maria Julia` | `Maria Julia` |
| `Maria  Julia.` | `Maria Julia` |
| `joao pedro` | `João Pedro` |
| `pedro joao` | `Pedro João` |
| `Carlos Augusto` | `Carlos Augusto` |
| `Augusto Mário` | `Augusto Mário` |
| `José Alexandre` | `José Alexandre` |
| `João` | `João` |
| `Abraão` | `Abraão` |
| `Carlos Silva` | `Carlos` |
| `Carlos D'Ávila` | `Carlos` |
| `Maria Clara Silva` | `Maria Clara` |
| `Edcarlos dos Santos Pereira Filho` | `Edcarlos` |
| `Ana-Clara` | `Ana-Clara` |
| `D'Ávila` | `D'Ávila` |

Palavras ambiguas conhecidas, como `Mano`, `Cole`, `Quero` e `Vai`, sao
rejeitadas pela lista de respostas fora do contexto.

### Apresentacao explicita

O extrator reconhece apenas prefixos completos e posicionados no inicio:

```text
É João
É João Pedro
E João
Eh João
He João
Aqui é João
Prazer, João
Me chamo João
Me chamo de João
Eu me chamo João Pedro
Meu nome é João
Meu nome: João
Meu apelido é João
Meu apelido: João
O meu nome é João Pedro
Pode me chamar de João
Podem me chamar de João Pedro
Sou João
Eu sou João Pedro
```

O resultado preserva o nome declarado:

| Entrada | Nome resultante |
|---|---|
| `É jOÃO pEDRO` | `João Pedro` |
| `he joao` | `João` |
| `Meu nome é João` | `João` |
| `Me chamo Abraão` | `Abraão` |
| `Eu me chamo Maria Julia` | `Maria Julia` |
| `Pode me chamar de Cauã` | `Cauã` |

Como a validacao ocorre exclusivamente depois da pergunta do nome, as grafias
informais `e`, `eh` e `he` tambem sao aceitas como equivalentes a `é`.

Os prefixos `sou` e `eu sou` continuam conservadores: palavras posteriores so
sao descartadas quando formam uma cauda reconhecida de sobrenomes. Isso impede
que uma frase comum seja interpretada como nome:

```text
Eu sou escolhido da favela -> invalido
Sou cliente novo -> invalido
```

### Nome completo e classificacao de sobrenomes

A V1 possui um conjunto local de sobrenomes brasileiros frequentes. Ele serve
somente para separar primeiro nome simples, primeiro nome composto e sobrenome:

| Entrada | Nome resultante |
|---|---|
| `Meu nome é João Pedro da Silva` | `João Pedro` |
| `Meu nome é João da Silva` | `João` |
| `Pode me chamar de Maria Julia dos Santos` | `Maria Julia` |
| `Carlos Silva` | `Carlos` |
| `Maria Clara Silva` | `Maria Clara` |
| `Maria Clara Watanabe` | `Maria Clara` |

Os conectores `da`, `das`, `de`, `do` e `dos` so sao aceitos quando seguidos
por sobrenomes reconhecidos. Uma palavra desconhecida no final nao e descartada
silenciosamente.

## Preservacao de acentos

O texto normalizado sem acentos e usado apenas para comparar prefixos, palavras
fora do contexto e termos pejorativos. O nome devolvido e construido a partir
do texto original em Unicode NFC.

Portanto:

```text
João -> João
Abraão -> Abraão
Simão -> Simão
Cauã -> Cauã
Conceição -> Conceição
```

Outros exemplos de nomes que podem conter til incluem `Sebastião`, `Damião`,
`Adão`, `Romão`, `Julião`, `Estevão`, `Cristóvão`, `Kauã`, `Assunção`,
`Ascensão`, `Anunciação` e `Aarão`.

Quando o cliente omite o til, um mapa local e curado corrige somente nomes
conhecidos:

```text
joao -> João
abraao -> Abraão
simao -> Simão
sebastiao -> Sebastião
caua -> Cauã
conceicao -> Conceição
```

O mapa nao tenta acentuar palavras arbitrarias. Um nome fora da lista apenas
recebe inicial maiuscula e demais letras minusculas.

## Validacoes obrigatorias

Antes de aceitar o candidato, a V1:

1. exige uma entrada do tipo texto;
2. rejeita entrada vazia;
3. normaliza Unicode compativel com NFKC e volta a NFC;
4. normaliza espacos, hifens e apostrofos tipograficos seguros;
5. rejeita controles, caracteres invisiveis, texto corrompido e alfabetos fora
   do escopo latino;
6. rejeita qualquer numero;
7. remove uma sequencia final de pontos, virgulas, exclamacoes e interrogacoes;
8. aceita virgula em `Prazer, nome` e dois-pontos em `Meu nome: nome`;
9. aceita hifen e apostrofo somente entre letras e valida cada componente;
10. rejeita qualquer outro simbolo ou emoji;
11. limita cada palavra declarada entre 2 e 50 caracteres;
12. rejeita tres ou mais letras iguais consecutivas;
13. rejeita termos pejorativos, flexoes e disfarces conhecidos;
14. rejeita palavras conversacionais claramente fora do contexto;
15. rejeita palavras sem vogal ou com cinco consoantes consecutivas;
16. valida tambem os sobrenomes ignorados na extracao;
17. prioriza compostos brasileiros curados antes de classificar sobrenome;
18. formata cada nome com inicial maiuscula sem remover acentos.

Exemplos rejeitados:

| Entrada | Motivo |
|---|---|
| `Pedro99` | contem numero |
| `000` | contem numero |
| `Pedro#` | contem caractere invalido |
| `Ana\Clara` | contem caractere invalido |
| `Ana-\Clara` | contem caractere invalido |
| `Ana-Quero` | componente fora do contexto |
| `Quero-Ana` | componente fora do contexto |
| `ppp` | tres letras iguais consecutivas |
| `Pppjoao` | tres letras iguais consecutivas |
| `puta` | termo pejorativo |
| `Maria Puta` | termo pejorativo na declaracao |
| `Meu nome é João Puta da Silva` | termo pejorativo no sobrenome ignorado |
| `Quero saber valores` | frase generica |
| `Banana Feliz` | resposta conhecida fora do contexto |
| `Meu nome é Banana Feliz` | declaracao conhecida fora do contexto |
| `Girafa Alegre` | resposta conhecida fora do contexto |
| `Caderno Verde` | resposta conhecida fora do contexto |
| `Maripo` | falso nome conhecido |
| `Zuleco` | falso nome conhecido |
| `Pedro#Maria` | contem caractere invalido |
| `Meu.nome.e.Pedro` | contem caractere invalido |
| `Pedro​Maria` | contem caractere invisivel |
| `pedro@gmail.com` | contem caractere invalido |
| `😀🔥` | contem emoji |
| `Pe😀dro` | contem emoji |
| `A` | abaixo do tamanho minimo |
| palavra com mais de 50 letras | acima do tamanho maximo |
| `xzxzxz` | estrutura sem vogal |
| `oi` | resposta conhecida fora do contexto |
| `teste` | resposta conhecida fora do contexto |

Uma sequencia de pontuacao final natural e sanitizada:

```text
Pedro. -> Pedro
Pedro! -> Pedro
Pedro? -> Pedro
Pedro!! -> Pedro
Maria... -> Maria
Maria Julia. -> Maria Julia
Meu nome é João. -> João
```

Numeros e outros caracteres nunca sao removidos para transformar uma resposta
invalida em nome:

```text
Pedro99 -> invalido
Pedro😀 -> invalido
Pedro#Maria -> invalido
Pe😀dro -> invalido
```

## Garantia de nome nao vazio

Nao existe caminho normal em que a V1 retorne:

```text
valido = True
primeiro_nome = vazio
```

Sem candidato valido, o resultado e invalido e a etapa envia a mensagem de
tratamento, mantendo a conversa na etapa 1.

## Limites deliberados

Regex nao prova que uma palavra e um nome real. A V1 nao tenta localizar um
nome dentro de qualquer frase: so aceita resposta direta ou um dos prefixos
explicitos documentados.

Palavras que tambem sao nomes reais, como `Rosa`, `Sol`, `Luz`, `Violeta`,
`Paulo` e `Cunha`, nao sao bloqueadas apenas por possuirem significado comum.
A validacao prioriza o portugues do Brasil e nomes internacionais usuais.

Nomes com hifen e apostrofo sao aceitos quando o sinal aparece entre letras.
Nomes fora da estrutura alfabetica reconhecida continuam recebendo tratamento.
O conjunto de sobrenomes e deliberadamente conservador e pode precisar de
ajustes conforme casos reais aparecam em producao.

Nomes de uma unica letra e nomes escritos somente em alfabetos nao latinos
continuam fora do escopo da V1.

## Estrategia names-dataset retirada

A implementacao anterior usava `names-dataset`. Ela foi retirada porque o
pacote informa consumo aproximado de 3,2 GB de RAM ao carregar a base completa.

O codigo antigo foi preservado somente como referencia em:

```text
_V2/detector_nome_names_dataset_v2.py.txt
```

Esse arquivo nao faz parte do codigo executavel.

## Possiveis evolucoes da V2

O uso de `names-dataset` nao e obrigatorio. Antes de adotar uma solucao mais
pesada, comparar:

- frequencia real de falsos positivos e falsos negativos em producao;
- uma base brasileira pequena e carregada sob demanda;
- nomes com hifen e apostrofo;
- idiomas e alfabetos realmente encontrados nas unidades;
- custo de memoria por processo do worker;
- modelo leve ou servico especializado;
- armazenamento seguro de exemplos anonimizados para melhorar a heuristica.

A V2 deve preservar o principio atual: extrair somente quando a estrutura da
resposta demonstrar intencao clara e nunca bloquear nomes raros sem necessidade.
