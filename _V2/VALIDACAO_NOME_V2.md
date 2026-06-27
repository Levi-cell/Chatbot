# Validação de Nome na V2

## Situação da V1

A V1 não consulta uma base externa de nomes. Ela utiliza uma regra local,
determinística e barata:

1. exige uma entrada de texto;
2. separa blocos contínuos de letras;
3. descarta números e símbolos apenas nas extremidades do bloco;
4. exige exatamente um bloco de letras;
5. limita o primeiro nome entre 2 e 50 caracteres;
6. rejeita três ou mais letras iguais consecutivas;
7. rejeita termos pejorativos, flexões e disfarces conhecidos;
8. rejeita respostas comuns claramente fora do contexto;
9. rejeita palavras sem vogal ou com cinco consoantes consecutivas;
10. formata a primeira letra como maiúscula.

Exemplos aceitos:

| Entrada | Nome resultante |
|---|---|
| `Pedro00` | `Pedro` |
| `Pedro##` | `Pedro` |
| `Pedro  #` | `Pedro` |
| `Mano 99` | `Mano` |
| `João` | `Joao` |
| `João99` | `Joao` |
| `Quero` | `Quero` |

Palavras comuns como `Mano`, `Cole` e `Quero` são riscos aceitos. A V1 prefere
aceitar uma palavra incomum a bloquear um nome ou apelido real.

Exemplos rejeitados:

| Entrada | Motivo |
|---|---|
| `000` | não restou nenhuma letra |
| `###` | não restou nenhuma letra |
| `## 99` | não restou nenhuma letra |
| `ppp` | três letras iguais consecutivas |
| `Pppjoao` | três letras iguais consecutivas |
| `puta` | termo pejorativo |
| `Maria Julia` | mais de uma palavra |
| `Meu nome é Pedro` | frase com mais de uma palavra |
| `Pedro#Maria` | dois blocos de letras |
| `Meu.nome.e.Pedro` | vários blocos de letras |
| `Pedro​Maria` | caractere invisível separando dois blocos |
| `pedro@gmail.com` | vários blocos de letras |
| `😀🔥` | não restou nenhuma letra |
| `Pe😀dro` | o emoji separou dois blocos |
| `A` | abaixo do tamanho mínimo |
| palavra com mais de 50 letras | acima do tamanho máximo |
| `xzxzxz` | estrutura sem vogal |
| `oi` | resposta conhecida fora do contexto |
| `teste` | resposta conhecida fora do contexto |

Números, pontuação e emojis são removidos quando aparecem antes ou depois de
um único bloco:

```text
Pedro99 -> Pedro
Pedro## -> Pedro
😀Pedro -> Pedro
Pedro😀 -> Pedro
```

Eles não podem unir partes diferentes:

```text
Pedro#Maria -> inválido
Pe😀dro -> inválido
```

## Garantia de nome não vazio

Não existe caminho normal em que a V1 retorne:

```text
valido = True
primeiro_nome = vazio
```

Sem pelo menos um bloco de letras dentro dos limites definidos, o resultado é
inválido e a etapa envia a mensagem de tratamento sem avançar.

## Limitação deliberada da heurística

Regex não consegue provar que toda palavra é um nome real. Palavras isoladas
ambíguas como `Quero`, `Vai`, `Mano` e `Cole` ainda podem ser aceitas. Uma lista
de respostas inequivocamente fora do contexto reduz falsos positivos como
`oi`, `teste`, `continuar`, `computador`, `valor` e `agendamento`.

A lista deve permanecer conservadora. Palavras que também são nomes reais,
como `Rosa`, `Sol`, `Luz`, `Violeta`, `Paulo` e `Cunha`, não devem ser
bloqueadas apenas por também possuírem significado comum.

## Estratégia names-dataset retirada da V1

A implementação anterior usava `names-dataset` para localizar um primeiro nome
em frases e nomes compostos. Ela foi retirada porque o pacote informa consumo
aproximado de 3,2 GB de RAM quando carrega a base completa.

O código foi preservado integralmente em:

```text
_V2/detector_nome_names_dataset_v2.py.txt
```

O arquivo é apenas referência e não faz parte do código executável da V1.

## Decisão futura

Usar novamente `names-dataset` não é obrigatório na V2. Antes de restaurar essa
estratégia, comparar:

- custo adicional de memória por processo do worker;
- carregamento somente de primeiros nomes;
- criação de uma base brasileira menor;
- armazenamento de nomes observados em produção;
- modelo leve ou serviço especializado;
- impacto real de rejeitar frases e nomes compostos.

A V2 poderá aceitar frases como `Meu nome é Pedro` e nomes compostos como
`Maria Julia`, mas essa evolução deve preservar a regra de não bloquear nomes
raros e não aumentar desnecessariamente o custo mensal da infraestrutura.
