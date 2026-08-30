# Plano teórico — suporte ao idoso e obrigatoriedade de e-mail por unidade

## 1. Objetivo e estado deste documento

Este documento registra o contrato funcional completo de duas configurações por
unidade:

- `unidade.suporte_idoso`;
- `unidade.email_obrigatorio`.

Também registra a exceção universal que torna o e-mail opcional quando o
atendimento é para o próprio titular e a idade informada é igual ou superior a
60 anos, desde que a conversa não tenha sido encerrada antes pelo encaminhamento
ao suporte especializado.

O plano é intencionalmente teórico. Ele define regras de produto, precedências,
persistência, integração com o Funil, encerramento, idempotência, migração,
Admin, observabilidade e testes. Ele não pressupõe que cada seção corresponda a
um arquivo nem fornece o código completo de uma implementação.

As decisões registradas aqui estão aprovadas para orientar uma implementação
futura. Enquanto essa implementação não for aplicada e migrada, o runtime e o
banco continuam seguindo o comportamento atual.

---

## 2. Decisões aprovadas

### 2.1. Novas colunas da unidade

As duas configurações serão booleanas, não nulas e editáveis no Django Admin:

| Coluna | Valor inicial das unidades existentes | Significado |
|---|---:|---|
| `suporte_idoso` | `FALSE` | Quando ativa, titular com idade de 60 a 99 anos é encaminhado ao comercial e a conversa é encerrada sem bloqueio |
| `email_obrigatorio` | `TRUE` | Quando ativa, mantém a exigência atual de e-mail, salvo a exceção universal do titular 60+ |

Santo Antônio de Jesus e Rio Vermelho devem receber esses valores iniciais para
preservar o comportamento configurável atual depois da migração. A única
mudança automática nessas unidades será a exceção universal já aprovada para o
e-mail de titulares 60+.

### 2.2. Exceção universal do titular 60+

Se o atendimento for para o próprio titular e a idade válida informada for igual
ou superior a 60 anos, o e-mail não será obrigatório quando a conversa chegar à
etapa de e-mail.

Essa exceção é universal: ela prevalece mesmo quando
`unidade.email_obrigatorio = TRUE`.

Ela somente chega a ser usada quando `unidade.suporte_idoso = FALSE`. Se o
suporte estiver ativo, o titular de 60 a 99 anos será encaminhado ao comercial
na etapa da idade e não chegará à pergunta de e-mail.

### 2.3. Ausência de e-mail

`cliente.email` continuará contendo apenas:

- um endereço de e-mail estruturalmente válido; ou
- `NULL`, quando o cliente não tiver ou não informar um endereço.

Textos como `não tenho`, `não possuo` ou qualquer outro marcador de ausência não
serão gravados literalmente em `cliente.email`. Isso evita dados falsos e também
evita conflito com a unicidade atual da coluna, pois o PostgreSQL permite vários
valores `NULL`, mas não permitiria vários clientes com o mesmo texto `não tenho`.

### 2.4. Atualização do cadastro do cliente

Cada nova resposta aceita na etapa de e-mail atualiza o cadastro global do
cliente:

| Resposta aceita na conversa nova | Resultado em `cliente.email` |
|---|---|
| Mesmo e-mail que já estava salvo | O valor permanece igual |
| E-mail válido diferente | O endereço antigo é substituído pelo novo |
| Recusa explícita, como `não tenho` | O endereço anterior é removido e o campo recebe `NULL` |
| Texto comum aceito porque o e-mail é opcional | O endereço anterior é removido e o campo recebe `NULL` |

Uma mensagem que apenas recebeu tratamento e repetiu a etapa ainda não é uma
resposta aceita. Portanto, ela não altera `cliente.email`.

### 2.5. Novo motivo de encerramento

O domínio de `conversa.motivo_encerramento` passa a aceitar:

```text
encaminhado_suporte_idoso
```

Esse motivo é próprio e não deve ser convertido em `idade_invalida`. Uma pessoa
com 60 anos ou mais não está sendo rejeitada por idade inválida; ela está sendo
encaminhada para o atendimento comercial definido pela unidade.

---

## 3. Definições canônicas

### 3.1. Titular e dependente

- **Titular:** atendimento marcado como `para mim`, representado pela conversa
  sem status de dependente.
- **Dependente:** atendimento marcado como sendo para outra pessoa. O e-mail
  solicitado continua sendo o e-mail do cliente/responsável, não do dependente.
- **Pessoa atendida:** a pessoa cuja idade é coletada na etapa da idade. No
  atendimento próprio é o titular; no atendimento para dependente é o
  dependente.

A nova regra de suporte ao idoso e a exceção universal de e-mail dependem das
duas condições simultâneas:

```text
atendimento para o próprio titular
+
idade informada para a pessoa atendida >= 60
```

Uma idade de 60 anos ou mais informada para um dependente não transforma o
atendimento em atendimento próprio e não ativa essas exceções.

### 3.2. Faixas etárias usadas no plano

- `60+` significa idade igual ou superior a 60 anos;
- a nova faixa controlada por `suporte_idoso` é de 60 a 99 anos, inclusive;
- idade igual ou superior a 100 anos continua sujeita à regra preexistente de
  idade acima de 99;
- limites mínimos atuais de titular e dependente permanecem inalterados.

A separação de 60–99 e 100+ é necessária para preservar a compatibilidade: as
unidades existentes receberão `suporte_idoso = FALSE`, mas pessoas com 100 anos
ou mais devem continuar recebendo o encaminhamento que já existe hoje.

### 3.3. E-mail efetivamente obrigatório

Depois de descartados os casos que encerram na etapa da idade, a regra pode ser
expressa assim:

```text
excecao_titular_60 = atendimento_proprio AND idade >= 60

email_efetivamente_obrigatorio =
    unidade.email_obrigatorio
    AND NOT excecao_titular_60
```

`suporte_idoso` não aparece nessa fórmula porque, quando ele está ativo para um
titular de 60 a 99 anos, a conversa termina antes de chegar à etapa de e-mail.

### 3.4. Fontes de verdade

- PostgreSQL é a fonte de verdade das flags, da idade, do tipo de atendimento,
  do e-mail e do encerramento.
- O Django Admin é apenas a interface de edição da unidade.
- Redis não deve se tornar fonte de verdade dessas duas flags.
- Se no futuro as flags forem cacheadas, o cache deverá ter invalidação,
  versionamento, fallback para o banco e autocura observável.

---

## 4. Estado atual que deve ser preservado

Na baseline atual:

1. a idade é tratada na etapa 6;
2. idade superior a 99 encerra a conversa, envia o contato comercial e não cria
   bloqueio de 30 dias;
3. a pergunta de e-mail ocorre na etapa 10 da numeração atual;
4. mídia, dúvida sobre reforço escolar e dúvida financeira possuem prioridade
   sobre a validação do e-mail;
5. um e-mail válido é persistido em `cliente.email`;
6. o Funil atualmente pressupõe que o e-mail sempre existe e precisa ser
   adaptado antes que respostas sem e-mail possam chegar até ele;
7. o e-mail pertence ao cliente/responsável, inclusive quando a pessoa atendida
   é um dependente.

Os planos que renumerem etapas no futuro devem transportar estas regras pela
responsabilidade da etapa, e não confiar cegamente no número 6 ou 10.

---

## 5. Ordem autoritativa das decisões

### 5.1. Proteções operacionais permanecem primeiro

Antes das novas regras continuam valendo os guards já existentes de:

- identidade da unidade e do cliente;
- bloqueios e denylist;
- turno e ordenação;
- lock da conversa e `lock_version`;
- idempotência pelo histórico;
- retry, rollback e recuperação;
- conversa ativa e etapa atual válida.

As flags não autorizam ignorar essas proteções.

### 5.2. Decisão na etapa da idade

Depois dos tratamentos universais da própria etapa e da obtenção de uma idade
válida, a ordem conceitual é:

1. idade igual ou superior a 100: executar a regra preexistente de idade acima
   de 99, independentemente das duas novas flags e de ser titular ou dependente;
2. titular com idade entre 60 e 99 e `suporte_idoso = TRUE`: encaminhar ao
   comercial, persistir a idade válida, encerrar com
   `encaminhado_suporte_idoso` e não bloquear;
3. aplicar os limites mínimos já existentes para titular e dependente;
4. nos demais casos, persistir a idade e continuar o fluxo normal.

Mídia, dúvida sobre reforço escolar e dúvida financeira continuam recebendo os
tratamentos atuais antes dessa decisão. Texto que não contém uma idade válida
continua repetindo a etapa; nenhuma flag deve transformar uma idade ausente ou
malformada em resposta válida.

As flags de e-mail não participam da etapa da idade. Em especial,
`email_obrigatorio = FALSE` nunca impede um encaminhamento de suporte ao idoso.

### 5.3. Decisão na etapa de e-mail

Se a conversa alcançou a etapa de e-mail, a ordem é:

1. tratamento de mídia;
2. tratamento de dúvida sobre reforço escolar;
3. tratamento de dúvida financeira;
4. cálculo de `email_efetivamente_obrigatorio`;
5. classificação da resposta como e-mail válido, ausência explícita ou texto
   comum;
6. avanço ou repetição conforme a política efetiva.

Os três tratamentos prioritários continuam ativos tanto no modo obrigatório
quanto no opcional. Eles repetem a etapa e não alteram o e-mail cadastrado.

---

## 6. Regra de `suporte_idoso`

### 6.1. Condição exata

O novo encaminhamento acontece somente quando todas as condições forem
verdadeiras:

```text
conversa ativa
AND atendimento para o próprio titular
AND idade válida entre 60 e 99, inclusive
AND unidade.suporte_idoso = TRUE
```

Não se aplica a atendimento para dependente, ainda que o dependente tenha 60
anos ou mais.

### 6.2. Resposta e encerramento

O bot deve:

1. enviar uma mensagem específica de encaminhamento para suporte ao idoso;
2. apresentar o número comercial da mesma unidade, preferencialmente pelo mesmo
   padrão seguro de botão utilizado no encaminhamento de idade acima de 99;
3. persistir exatamente a resposta efetivamente enviada;
4. persistir a idade válida que determinou o encaminhamento, de forma absoluta,
   atômica e idempotente junto aos efeitos desse caminho;
5. encerrar a conversa com
   `motivo_encerramento = 'encaminhado_suporte_idoso'`;
6. usar `bloqueio_dias = 0`;
7. não inserir bloqueio de 30 dias no banco nem no Redis;
8. não encaminhar essa conversa ao Funil;
9. não executar as etapas posteriores, inclusive a etapa de e-mail.

A mensagem deve falar em atendimento ou suporte especializado. Ela não deve
chamar a idade de inválida nem reutilizar literalmente a expressão atual
`idades muito avançadas` para uma pessoa de 60 anos.

### 6.3. Falha de configuração do comercial

Se o número comercial estiver ausente ou inválido, o sistema não deve encerrar a
conversa como se o encaminhamento tivesse sido entregue.

O ciclo deve falhar de forma fechada, preservar a possibilidade de retry e gerar
log operacional identificando a unidade e o tipo de falha, sem expor dados
desnecessários do cliente.

### 6.4. Nova mensagem após o encerramento

Como não existe bloqueio de 30 dias, uma mensagem posterior do mesmo cliente
pode criar uma conversa nova. Se as mesmas condições ainda forem verdadeiras, o
encaminhamento poderá ocorrer novamente. Esse comportamento é consequência
intencional de `bloqueio_dias = 0` e não deve ser mascarado por um cache residual.

### 6.5. Regra preexistente de 100+

O comportamento atual de idade superior a 99 permanece separado:

- vale para titular e dependente;
- independe de `suporte_idoso`;
- usa o encaminhamento preexistente;
- encerra sem bloqueio de 30 dias.

Isso garante que adicionar `suporte_idoso = FALSE` às unidades atuais não libere
silenciosamente uma faixa que hoje já é encerrada.

---

## 7. Regra de `email_obrigatorio`

### 7.1. A pergunta continua existindo

E-mail opcional não significa pular a etapa. O bot continua perguntando o e-mail
para todos que chegarem a essa parte do atendimento.

A diferença está na resposta aceita:

- no modo obrigatório, somente um e-mail válido permite avançar, ressalvados os
  tratamentos prioritários;
- no modo opcional, qualquer resposta textual ordinária permite avançar, além
  de um e-mail válido ou de uma recusa explícita.

### 7.2. Modo obrigatório

Quando `email_efetivamente_obrigatorio = TRUE`:

| Tipo de resposta | Resultado |
|---|---|
| E-mail válido | Atualiza `cliente.email` e avança |
| `Não tenho` ou equivalente | Recebe o tratamento atual de e-mail inválido e repete |
| Texto comum sem e-mail | Recebe tratamento de e-mail inválido e repete |
| Texto parecido com e-mail, mas inválido | Recebe tratamento de e-mail inválido e repete |
| Mídia | Tratamento de mídia e repetição |
| Dúvida sobre reforço | Tratamento de reforço e repetição |
| Dúvida financeira | Tratamento financeiro e repetição |

### 7.3. Modo opcional

Quando `email_efetivamente_obrigatorio = FALSE`:

| Tipo de resposta | Persistência | Observação do atendimento | Resultado |
|---|---|---|---|
| E-mail válido | Endereço normalizado | `E-mail: {endereço}` | Avança |
| Recusa explícita (`não tenho`, `não possuo` etc.) | `NULL` | `E-mail: não tem` | Avança |
| Texto comum sem e-mail | `NULL` | `E-mail: não informado` | Avança |
| Texto parecido com e-mail, mas inválido | `NULL` | `E-mail: não informado` | Avança sem tratamento de e-mail |
| Mídia | Sem alteração | Sem conclusão da coleta | Tratamento de mídia e repetição |
| Dúvida sobre reforço | Sem alteração | Sem conclusão da coleta | Tratamento de reforço e repetição |
| Dúvida financeira | Sem alteração | Sem conclusão da coleta | Tratamento financeiro e repetição |

O texto comum aceito continua preservado no histórico real da conversa. Ele não
deve ser copiado para `cliente.email`.

### 7.4. Classificação conservadora de ausência explícita

O vocabulário de ausência deve reconhecer somente construções inequívocas, como:

- `não tenho`;
- `não possuo`;
- `não uso e-mail`;
- `estou sem e-mail`.

Uma resposta não classificada como ausência explícita, quando o e-mail for
opcional, entra na categoria `não informado`. Essa separação serve apenas para
uma observação fiel; as duas categorias gravam `NULL` e avançam.

No modo obrigatório, nenhuma dessas expressões avança.

### 7.5. Respostas contendo mais de uma intenção

A prioridade atual dos tratamentos permanece. Assim, uma pergunta financeira ou
sobre reforço escolar não deve ser consumida como resposta de e-mail apenas
porque contém um endereço no mesmo texto. A etapa é repetida após o tratamento e
o cadastro ainda não é atualizado.

---

## 8. Persistência e atualização do e-mail

### 8.1. Cadastro global e resultado da conversa

`cliente.email` representa o endereço mais recente declarado pelo cliente, não
um histórico imutável de todas as conversas.

Ao mesmo tempo, o Funil e a auditoria precisam representar a resposta desta
conversa. Portanto, devem ser separados dois conceitos:

- **cadastro atual:** valor mais recente de `cliente.email`;
- **resultado da coleta na conversa:** e-mail válido, `não tem` ou
  `não informado`, conforme a resposta aceita naquele atendimento.

Este plano não cria uma terceira coluna de configuração na unidade nem exige uma
nova coluna `conversa.email`. O resultado da conversa deve permanecer
reconstruível a partir da mensagem original da etapa de e-mail e do evento
semântico que permitiu a transição, ou ser transportado de forma durável pelo
contrato existente de envio ao Funil.

O Funil não pode inferir `não tem` versus `não informado` olhando apenas para
`cliente.email IS NULL`, pois ambos produzem `NULL`.

### 8.2. Atualização absoluta e idempotente

O efeito da resposta aceita deve ser absoluto:

```text
email_valido       -> SET cliente.email = email_normalizado
email_ausente      -> SET cliente.email = NULL
email_nao_informado -> SET cliente.email = NULL
```

Executar novamente o mesmo efeito em um retry produz o mesmo estado final. Não
deve existir operação relativa, concatenação ou placeholder.

### 8.3. E-mail anterior

Se existia um endereço anterior:

- um endereço novo válido o substitui;
- o mesmo endereço apenas reafirma o valor;
- `não tenho` remove o endereço;
- texto comum aceito no modo opcional remove o endereço;
- uma mensagem tratada que ainda não concluiu a etapa não o modifica.

### 8.4. Unicidade

A unicidade atual de e-mails reais pode permanecer. Vários clientes sem e-mail
podem ter `NULL` sem colisão.

Uma eventual tentativa de usar um e-mail real já associado a outro cliente
continua sendo um problema de identidade/integridade preexistente e não deve ser
silenciosamente convertido em ausência de e-mail.

---

## 9. Integração com o Funil

### 9.1. Conversas que devem chegar ao Funil

- E-mail obrigatório e válido: fluxo atual para o Funil.
- E-mail opcional e válido: fluxo normal para o Funil.
- E-mail opcional e ausente/não informado: também deve seguir para o Funil.
- Encaminhamento por `suporte_idoso`: não deve seguir para o Funil porque a
  conversa foi encerrada antes da triagem final.

### 9.2. Payload sem e-mail

O contrato atual do Funil não pode continuar chamando `.strip()` em um valor
nulo nem rejeitando o lead apenas pela ausência de e-mail.

Quando a coleta da conversa resultar em ausência:

- o campo técnico de e-mail do contato deve ser omitido ou enviado vazio,
  conforme o formato oficialmente aceito pela API do Funil;
- nunca deve receber `não tenho`, `não informado` ou um endereço fictício;
- nome, telefone, unidade, profissão, respostas da triagem e demais dados seguem
  normalmente;
- as observações humanas devem exibir a classificação correta.

A implementação deve confirmar por teste de contrato qual das opções — omissão
ou string vazia — é aceita pela API antes do deploy. Se a API externa exigir um
e-mail, isso deve ser tratado como incompatibilidade de integração e não como
motivo para fabricar um endereço.

### 9.3. Observações

O resultado esperado é:

```text
E-mail: cliente@exemplo.com
```

ou:

```text
E-mail: não tem
```

ou:

```text
E-mail: não informado
```

No atendimento para dependente, esse continua sendo o e-mail do
cliente/responsável.

### 9.4. Proteção contra deriva entre conversas

Se o mesmo cliente iniciar outra conversa e atualizar `cliente.email` antes de
um retry tardio do Funil, o atendimento antigo não pode ganhar retroativamente
uma resposta diferente. O payload/observação deve usar o resultado da coleta da
conversa que originou aquele envio, reconstruído de forma determinística.

A coluna global permanece atualizada com o dado mais recente, mas não substitui
o contexto histórico de um envio já originado.

---

## 10. Matriz das quatro configurações da unidade

| `suporte_idoso` | `email_obrigatorio` | Titular 60–99 | Demais pessoas que chegam ao e-mail |
|---:|---:|---|---|
| `FALSE` | `TRUE` | Continua; e-mail opcional pela exceção universal | E-mail obrigatório |
| `FALSE` | `FALSE` | Continua; e-mail opcional | E-mail opcional |
| `TRUE` | `TRUE` | Encaminha ao comercial, encerra sem bloqueio | E-mail obrigatório |
| `TRUE` | `FALSE` | Encaminha ao comercial, encerra sem bloqueio | E-mail opcional |

`Demais pessoas` inclui titulares abaixo de 60 anos e atendimentos para
dependentes, desde que tenham passado pelas regras etárias preexistentes.

---

## 11. Matriz exaustiva — idades válidas abaixo de 100

Nesta matriz, `S` representa `suporte_idoso` e `E` representa
`email_obrigatorio`. As faixas abaixo já pressupõem que a idade passou pelos
limites mínimos atuais.

| # | Atendimento | Idade da pessoa atendida | S | E | Resultado da idade | Política de e-mail |
|---:|---|---:|---:|---:|---|---|
| 1 | Titular | 18–59 | 0 | 0 | Continua | Opcional pela unidade |
| 2 | Titular | 18–59 | 0 | 1 | Continua | Obrigatório |
| 3 | Titular | 18–59 | 1 | 0 | Continua; suporte não se aplica | Opcional pela unidade |
| 4 | Titular | 18–59 | 1 | 1 | Continua; suporte não se aplica | Obrigatório |
| 5 | Titular | 60–99 | 0 | 0 | Continua | Opcional pela unidade e pela exceção universal |
| 6 | Titular | 60–99 | 0 | 1 | Continua | Opcional pela exceção universal |
| 7 | Titular | 60–99 | 1 | 0 | Encaminha e encerra sem bloqueio | Não alcança a etapa |
| 8 | Titular | 60–99 | 1 | 1 | Encaminha e encerra sem bloqueio | Não alcança a etapa |
| 9 | Dependente | Mínimo válido–59 | 0 | 0 | Continua | Opcional pela unidade |
| 10 | Dependente | Mínimo válido–59 | 0 | 1 | Continua | Obrigatório para o responsável |
| 11 | Dependente | Mínimo válido–59 | 1 | 0 | Continua; suporte não se aplica | Opcional pela unidade |
| 12 | Dependente | Mínimo válido–59 | 1 | 1 | Continua; suporte não se aplica | Obrigatório para o responsável |
| 13 | Dependente | 60–99 | 0 | 0 | Continua | Opcional pela unidade |
| 14 | Dependente | 60–99 | 0 | 1 | Continua | Obrigatório para o responsável |
| 15 | Dependente | 60–99 | 1 | 0 | Continua; suporte não se aplica | Opcional pela unidade |
| 16 | Dependente | 60–99 | 1 | 1 | Continua; suporte não se aplica | Obrigatório para o responsável |

---

## 12. Matriz exaustiva — idade igual ou superior a 100

A regra preexistente de idade acima de 99 prevalece em todas as combinações:

| # | Atendimento | S | E | Resultado |
|---:|---|---:|---:|---|
| 1 | Titular 100+ | 0 | 0 | Encaminhamento preexistente; encerra sem bloqueio |
| 2 | Titular 100+ | 0 | 1 | Encaminhamento preexistente; encerra sem bloqueio |
| 3 | Titular 100+ | 1 | 0 | Encaminhamento preexistente; encerra sem bloqueio |
| 4 | Titular 100+ | 1 | 1 | Encaminhamento preexistente; encerra sem bloqueio |
| 5 | Dependente 100+ | 0 | 0 | Encaminhamento preexistente; encerra sem bloqueio |
| 6 | Dependente 100+ | 0 | 1 | Encaminhamento preexistente; encerra sem bloqueio |
| 7 | Dependente 100+ | 1 | 0 | Encaminhamento preexistente; encerra sem bloqueio |
| 8 | Dependente 100+ | 1 | 1 | Encaminhamento preexistente; encerra sem bloqueio |

Esses casos não chegam à etapa de e-mail.

---

## 13. Matriz exaustiva — idades abaixo do mínimo atual

As novas flags não liberam uma idade que hoje é inválida para continuar o fluxo.

| Atendimento | S | E | Resultado |
|---|---:|---:|---|
| Titular abaixo do mínimo atual | 0 | 0 | Regra de encerramento atual; não chega ao e-mail |
| Titular abaixo do mínimo atual | 0 | 1 | Regra de encerramento atual; não chega ao e-mail |
| Titular abaixo do mínimo atual | 1 | 0 | Regra de encerramento atual; não chega ao e-mail |
| Titular abaixo do mínimo atual | 1 | 1 | Regra de encerramento atual; não chega ao e-mail |
| Dependente abaixo do mínimo configurado | 0 | 0 | Regra de encerramento atual; não chega ao e-mail |
| Dependente abaixo do mínimo configurado | 0 | 1 | Regra de encerramento atual; não chega ao e-mail |
| Dependente abaixo do mínimo configurado | 1 | 0 | Regra de encerramento atual; não chega ao e-mail |
| Dependente abaixo do mínimo configurado | 1 | 1 | Regra de encerramento atual; não chega ao e-mail |

O mínimo de dependente continua obedecendo às regras já existentes da unidade,
inclusive configurações relacionadas ao BPA. Este plano não redefine esse
limite.

Na baseline atual, o mínimo é 4 anos quando o BPA da unidade está ativo e 5 anos
quando está desativado. Se essa regra mudar em outro plano, a implementação deve
consultar a política vigente, sem congelar esses números dentro das novas flags.

### 13.1. Como combinar as matrizes

As tabelas são composicionais, não amostras. Somando as faixas válidas, a faixa
100+ e as idades abaixo do mínimo, existem 32 combinações de
titular/dependente, faixa etária e estados possíveis das duas flags. Dezoito
delas encerram antes do e-mail: oito abaixo do mínimo, oito de idade 100+ e duas
de titular 60–99 com suporte ativo. As outras 14 devem ser cruzadas com todos os
tipos de resposta das seções 7.2 e 7.3.

Assim, não existe uma exceção implícita fora das tabelas: qualquer cenário que
chegue ao e-mail usa exatamente uma das duas políticas efetivas e conserva a
mesma prioridade de tratamentos.

---

## 14. Alterações pelo Django Admin

### 14.1. Operação esperada

As duas flags devem aparecer no cadastro de cada unidade com rótulos e ajuda
claros. O administrador deve conseguir ativar ou desativar cada uma
independentemente.

Recomendação de apresentação:

- `Suporte ao idoso`: encaminha titular de 60 a 99 anos ao contato comercial e
  encerra sem bloqueio;
- `E-mail obrigatório`: exige e-mail válido, salvo a exceção universal do
  titular 60+.

Os campos devem aparecer também em filtros e na listagem, para que seja possível
auditar rapidamente a configuração de todas as unidades.

Ativar `suporte_idoso` deve exigir que a própria unidade possua um número
comercial válido. O Admin deve impedir uma configuração que inevitavelmente
falharia no encaminhamento, em vez de permitir o salvamento e descobrir o erro
somente diante de um cliente.

### 14.2. Momento em que uma alteração passa a valer

- conversas já encerradas não são reabertas nem reclassificadas;
- envios já persistidos não são reinterpretados;
- uma mensagem ainda não processada usa a configuração vigente quando o ciclo
  adquire seu contexto consistente;
- dentro do mesmo ciclo, a decisão não pode mudar no meio do envio por uma
  alteração concorrente no Admin.

Na prática, o worker deve carregar um snapshot coerente da unidade para aquele
ciclo. Um retry que encontre uma resposta do bot já persistida deve respeitar a
decisão original, e não produzir uma segunda resposta com a configuração nova.

---

## 15. Persistência, transações e idempotência

### 15.1. Separação de responsabilidades

- Contextos/repositórios consultam os dados da unidade e persistem alterações.
- O resolver da etapa decide a rota funcional.
- O sender apenas monta e envia a mensagem aprovada.
- O orquestrador do worker continua dono de `commit`, `rollback`, retry e lock.
- A integração do Funil adapta seu próprio contrato sem controlar a transação do
  `worker_flow`.
- O webhook não decide suporte ao idoso nem obrigatoriedade de e-mail.

### 15.2. Encerramento seguro

O encerramento por suporte ao idoso somente pode ser confirmado depois que a
resposta de encaminhamento estiver efetivamente enviada e duravelmente
persistida.

Uma queda entre o envio e a finalização deve ser recuperada sem:

- reenviar a mesma mensagem;
- criar bloqueio de 30 dias;
- mudar o motivo para `idade_invalida`;
- deixar a conversa ativa depois que o envio já foi confirmado;
- reavaliar a flag atual do Admin e escolher outro caminho.

### 15.3. Efeito de e-mail seguro

A transição da etapa de e-mail precisa distinguir pelo menos três resultados
semânticos:

- e-mail válido;
- ausência explícita;
- não informado em modo opcional.

Esses resultados devem ser reconstruíveis a partir da mensagem original em um
retry. A reconstrução deve usar a mesma política efetiva que autorizou o avanço
e não pode transformar uma resposta opcional já enviada em erro obrigatório
depois de uma mudança administrativa.

Um valor nulo não pode servir ao mesmo tempo como dado de negócio e como sinal
de “contexto ausente”. A implementação precisa transportar um evento/estado
explícito para distinguir `email_ausente` e `email_nao_informado` de uma falha de
reconstrução do retry.

### 15.4. Falhas

Falha de leitura da unidade, valor estruturalmente inválido ou ausência inesperada
de uma flag não pode tornar o e-mail opcional silenciosamente nem encaminhar um
idoso por suposição.

Depois da migração, as colunas são `NOT NULL`. Antes ou durante uma implantação
mista, o fallback seguro é preservar o comportamento legado:

```text
suporte_idoso ausente/indisponível -> FALSE
email_obrigatorio ausente/indisponível -> TRUE
```

Falha real de banco continua seguindo rollback e retry; fallback não deve
mascarar indisponibilidade da fonte de verdade.

---

## 16. Banco de dados e migração futura

### 16.1. Estado final conceitual

```sql
suporte_idoso     BOOLEAN NOT NULL DEFAULT FALSE
email_obrigatorio BOOLEAN NOT NULL DEFAULT TRUE
```

Além disso, a restrição de domínio de `conversa.motivo_encerramento` deve aceitar
`encaminhado_suporte_idoso`.

### 16.2. Migração incremental

A implementação futura precisará de uma migração própria e reexecutável que:

1. valide o schema de origem esperado;
2. adicione as colunas sem destruir dados;
3. preencha unidades existentes com `FALSE` e `TRUE`, respectivamente;
4. aplique defaults e `NOT NULL`;
5. amplie a restrição de `motivo_encerramento` preservando os valores atuais;
6. verifique Santo Antônio de Jesus e Rio Vermelho explicitamente;
7. execute pós-condições que comprovem ausência de `NULL` e domínio correto;
8. possa reconhecer com segurança que o estado final já está aplicado.

O DDL canônico, o modelo Django e a migração de produção precisam terminar com o
mesmo contrato. Alterar apenas o modelo não migra o PostgreSQL existente.

### 16.3. Implantação compatível

A ordem de rollout deve impedir que código novo dependa de colunas inexistentes
e que código antigo quebre ao encontrar o novo motivo. A janela de deploy deve
considerar:

- migração de schema;
- implantação do runtime;
- verificação do Admin;
- testes do Funil sem e-mail;
- ativação deliberada de `suporte_idoso` somente depois da validação.

As unidades existentes permanecem nos defaults aprovados até uma alteração
manual posterior.

---

## 17. Observabilidade e auditoria

Logs estruturados devem permitir identificar:

- unidade e conversa envolvidas;
- valores das duas flags usados na decisão;
- titular ou dependente;
- faixa etária, sem necessidade de repetir dados pessoais completos;
- caminho escolhido: normal, e-mail obrigatório, e-mail opcional,
  encaminhamento de suporte ou regra preexistente de 100+;
- resultado da coleta: válido, ausente ou não informado;
- motivo de encerramento e `bloqueio_dias = 0`;
- falha de configuração do número comercial;
- retry/reconstrução de uma decisão já enviada.

Não se deve registrar o e-mail completo em logs técnicos. Quando necessário,
usar mascaramento ou apenas a classificação do resultado.

Métricas úteis incluem:

- quantidade de encaminhamentos por unidade;
- quantidade de coletas opcionais com e-mail;
- recusas explícitas;
- respostas não informadas;
- falhas do Funil por ausência de e-mail;
- tentativas de encerramento sem número comercial válido.

---

## 18. Cobertura de testes necessária

### 18.1. Flags e faixas etárias

- as 16 linhas da matriz de idades válidas abaixo de 100;
- as 8 combinações de idade 100+;
- as 8 combinações abaixo do mínimo;
- fronteiras exatas: mínimo atual, 59, 60, 99 e 100;
- titular versus dependente;
- suporte ativo sem número comercial válido;
- confirmação de encerramento sem bloqueio em banco e Redis;
- confirmação de que o encaminhamento não entra no Funil.

### 18.2. E-mail

Para modo obrigatório e opcional:

- e-mail válido isolado;
- e-mail válido dentro de uma frase;
- mesmo e-mail já cadastrado;
- novo e-mail substituindo o anterior;
- `não tenho` removendo o anterior;
- texto comum removendo o anterior no modo opcional;
- texto parecido com e-mail, mas inválido;
- mídia;
- dúvida sobre reforço escolar;
- dúvida financeira;
- mensagem com e-mail e intenção prioritária no mesmo conteúdo;
- titular 60+ com `email_obrigatorio = TRUE` e suporte desativado;
- dependente 60+ com e-mail obrigatório;
- vários clientes com `cliente.email = NULL` sem conflito de unicidade.

### 18.3. Funil

- payload com e-mail válido;
- payload sem e-mail usando o formato aceito pela API;
- observação `não tem`;
- observação `não informado`;
- responsável de dependente sem e-mail;
- retry tardio depois de o cadastro global ter sido alterado por outra conversa;
- preservação de claim, lease, idempotência e unicidade do envio por conversa.

### 18.4. Idempotência e concorrência

- queda antes do envio;
- queda depois do envio e antes do encerramento;
- queda depois da transição de e-mail e antes do efeito persistido;
- replay de fila já respondida;
- alteração das flags pelo Admin durante um processamento;
- retry depois de alteração das flags;
- nenhuma duplicação de mensagem, efeito ou envio ao Funil.

### 18.5. Schema e Admin

- migração em banco legado;
- reexecução da migração no estado final;
- defaults de SAJ e Rio Vermelho;
- `NOT NULL` e defaults no DDL canônico;
- novo domínio de `motivo_encerramento`;
- leitura, edição, filtro e persistência das flags no Django Admin.

---

## 19. Critérios de aceite

A funcionalidade somente está completa quando:

1. as duas flags existem no banco, no modelo e no Admin com os defaults
   aprovados;
2. unidades existentes mantêm a exigência atual para os demais públicos sem
   configuração manual, enquanto a exceção universal do titular 60+ passa a
   valer;
3. titular de 60 a 99 anos é encaminhado somente quando `suporte_idoso` está
   ativo;
4. o encaminhamento usa número da própria unidade, encerra com o novo motivo e
   não cria bloqueio de 30 dias;
5. atendimento para dependente não ativa a exceção de titular 60+;
6. a pergunta de e-mail continua sendo enviada mesmo quando opcional;
7. mídia, financeiro e reforço escolar continuam recebendo tratamento;
8. respostas ordinárias avançam somente quando a política efetiva torna o
   e-mail opcional;
9. `cliente.email` contém um e-mail real ou `NULL`, nunca um placeholder;
10. cada conversa nova atualiza ou limpa o cadastro conforme sua resposta
    aceita;
11. o Funil recebe leads sem e-mail sem quebrar e exibe a observação correta;
12. retry, idempotência, lock, histórico e transações não permitem resultados
    duplicados ou contraditórios;
13. a regra preexistente de idade acima de 99 permanece intacta;
14. todas as matrizes e fronteiras deste documento possuem testes automatizados.

---

## 20. Fora de escopo

Este plano não altera:

- os limites mínimos atuais de idade;
- o significado de titular e dependente;
- a propriedade do e-mail, que continua sendo do cliente/responsável;
- os tratamentos de mídia, financeiro e reforço escolar;
- a regra preexistente de idade acima de 99;
- as políticas normais de bloqueio das conversas que chegam ao encerramento
  comercial comum;
- a arquitetura de turno, fila, lock e retry;
- a lógica do futuro `worker_followup`;
- as etapas de satisfação;
- a integração externa além do necessário para aceitar um lead sem e-mail.

Qualquer mudança nesses pontos exige uma decisão separada e não pode ser inferida
das flags `suporte_idoso` ou `email_obrigatorio`.

---

## 21. Revisão guiada dos fluxos

Esta seção reapresenta as regras anteriores no formato passo a passo, para
facilitar a validação funcional antes da implementação.

### 21.1. Ordem comum de avaliação

Para qualquer atendimento, o sistema deve seguir esta ordem:

1. identificar se o atendimento é para o próprio cliente ou para dependente;
2. obter e validar a idade da pessoa atendida;
3. aplicar primeiro as regras etárias e a configuração `suporte_idoso`;
4. somente se a conversa continuar, chegar à etapa de e-mail;
5. aplicar os tratamentos prioritários de mídia, financeiro e reforço escolar;
6. calcular se o e-mail é obrigatório ou opcional;
7. persistir a resposta aceita e continuar ou repetir a etapa.

### 21.2. Atendimento para o próprio cliente, idade entre 60 e 99 anos

#### 21.2.1. Unidade com `suporte_idoso = TRUE`

O valor de `email_obrigatorio` não interfere, porque a conversa termina antes da
etapa de e-mail.

1. O cliente escolhe `Para mim`.
2. A conversa registra que o atendimento não é para dependente.
3. O cliente informa uma idade válida entre 60 e 99 anos.
4. O sistema identifica atendimento próprio, idade 60+ e suporte ao idoso
   ativado.
5. A idade válida é persistida.
6. O bot envia a mensagem específica de encaminhamento.
7. A mensagem apresenta o botão ou número comercial da própria unidade.
8. A resposta enviada é registrada no histórico.
9. A conversa é encerrada com
   `motivo_encerramento = encaminhado_suporte_idoso`.
10. O encerramento usa `bloqueio_dias = 0`.
11. Nenhum bloqueio de 30 dias é criado no PostgreSQL ou no Redis.
12. A conversa não chega à etapa de e-mail e não segue para o Funil.

Esse resultado é o mesmo com `email_obrigatorio = TRUE` ou
`email_obrigatorio = FALSE`.

#### 21.2.2. Unidade com `suporte_idoso = FALSE`

A conversa segue normalmente e entra em ação a exceção universal do titular
60+.

1. O cliente escolhe `Para mim`.
2. Informa uma idade válida entre 60 e 99 anos.
3. O sistema verifica que o suporte especializado está desativado.
4. A idade é persistida e o atendimento continua.
5. Ao chegar à etapa de e-mail, o bot continua fazendo a pergunta.
6. A exceção universal torna o e-mail opcional, mesmo que
   `email_obrigatorio = TRUE`.
7. A resposta é processada assim:
   - e-mail válido: atualiza `cliente.email` e avança;
   - `não tenho`: grava `cliente.email = NULL`, registra
     `E-mail: não tem` para o Funil e avança;
   - outra resposta comum: grava `cliente.email = NULL`, registra
     `E-mail: não informado` e avança;
   - mídia: aplica o tratamento de mídia e repete a pergunta;
   - dúvida financeira: aplica o tratamento financeiro e repete;
   - dúvida sobre reforço escolar: aplica o tratamento correspondente e repete.
8. O cliente continua a triagem.
9. Ao concluir, pode entrar normalmente no Funil, inclusive sem e-mail.

| Suporte ao idoso | E-mail obrigatório | Resultado para titular 60–99 |
|---|---|---|
| Desativado | Ativado | E-mail opcional pela exceção universal |
| Desativado | Desativado | E-mail opcional |
| Ativado | Ativado | Encaminha e encerra antes do e-mail |
| Ativado | Desativado | Encaminha e encerra antes do e-mail |

### 21.3. Atendimento para o próprio cliente, idade entre 18 e 59 anos

`suporte_idoso` não se aplica a essa faixa.

1. O cliente escolhe `Para mim`.
2. Informa uma idade válida entre 18 e 59 anos.
3. A idade é persistida.
4. O atendimento continua normalmente.
5. Ao chegar à etapa de e-mail, prevalece `email_obrigatorio`.

#### 21.3.1. `email_obrigatorio = TRUE`

1. O bot pergunta o e-mail.
2. Mídia, financeiro e reforço escolar continuam recebendo seus tratamentos.
3. Somente um e-mail válido permite avançar.
4. `Não tenho`, texto comum ou e-mail malformado recebem o tratamento de e-mail
   inválido.
5. A etapa é repetida e o e-mail anterior não é alterado.
6. Quando chegar um e-mail válido:
   - se for novo, substitui o endereço anterior;
   - se for igual ao anterior, o valor permanece;
   - a conversa avança.

#### 21.3.2. `email_obrigatorio = FALSE`

1. O bot continua perguntando o e-mail.
2. Os três tratamentos prioritários permanecem.
3. Fora desses tratamentos:
   - e-mail válido atualiza o cadastro e avança;
   - `não tenho` remove o endereço anterior, grava `NULL` e avança;
   - texto comum ou e-mail malformado remove o endereço anterior, grava `NULL`
     e avança.
4. O atendimento continua normalmente para a triagem e o Funil.

#### 21.3.3. Titular abaixo de 18 anos

1. A regra atual de idade mínima prevalece.
2. A conversa segue o encerramento atual por idade.
3. Não chega à etapa de e-mail.
4. `suporte_idoso` e `email_obrigatorio` não interferem.

### 21.4. Atendimento para dependente com idade válida abaixo de 60 anos

A idade é a do dependente. O e-mail solicitado continua sendo o do
cliente/responsável.

1. O cliente escolhe atendimento para dependente.
2. A conversa registra `status_dependente = TRUE`.
3. O dependente é identificado.
4. O cliente informa a idade do dependente.
5. A idade precisa respeitar o mínimo vigente: 4 anos com BPA ativo e 5 anos
   com BPA desativado na baseline atual.
6. Entre o mínimo permitido e 59 anos, o atendimento continua.
7. `suporte_idoso` não se aplica, ainda que esteja ativado.
8. Ao chegar à etapa de e-mail, prevalece `email_obrigatorio`.

Com `email_obrigatorio = TRUE`:

1. o e-mail do responsável é obrigatório;
2. somente e-mail válido avança;
3. `não tenho`, texto comum ou e-mail malformado recebem tratamento e repetem;
4. mídia, financeiro e reforço escolar continuam com seus tratamentos.

Com `email_obrigatorio = FALSE`:

1. o e-mail do responsável é opcional;
2. e-mail válido é salvo;
3. `não tenho` grava `NULL` e gera `E-mail: não tem`;
4. outro texto comum grava `NULL` e gera `E-mail: não informado`;
5. mídia, financeiro e reforço escolar recebem tratamento e repetem;
6. o atendimento pode chegar ao Funil sem e-mail.

Se o dependente estiver abaixo da idade mínima, a regra atual encerra a conversa
antes do e-mail e as novas configurações não modificam o resultado.

### 21.5. Atendimento para dependente com idade entre 60 e 99 anos

Mesmo sendo 60+, a pessoa atendida é um dependente. Portanto,
`suporte_idoso` e a exceção universal do titular 60+ não se aplicam.

1. O cliente escolhe atendimento para dependente.
2. Informa que o dependente tem entre 60 e 99 anos.
3. A idade é validada e persistida.
4. Mesmo com `suporte_idoso = TRUE`, não existe encaminhamento por essa nova
   regra.
5. O fluxo continua normalmente.
6. Ao chegar à etapa de e-mail:
   - com `email_obrigatorio = TRUE`, o e-mail do responsável é obrigatório;
   - com `email_obrigatorio = FALSE`, o e-mail do responsável é opcional.
7. Depois da coleta, a conversa segue para a triagem e o Funil.

### 21.6. Titular ou dependente com idade igual ou superior a 100 anos

A regra preexistente de idade acima de 99 continua tendo prioridade.

1. O sistema recebe uma idade igual ou superior a 100.
2. Aciona o encaminhamento preexistente para o comercial.
3. Envia e registra a mensagem.
4. Encerra a conversa sem bloqueio de 30 dias.
5. A conversa não chega à etapa de e-mail.
6. `suporte_idoso` e `email_obrigatorio` não alteram esse caminho.

### 21.7. Resumo operacional

| Pessoa atendida | Idade | `suporte_idoso` | `email_obrigatorio` | Resultado |
|---|---:|---:|---:|---|
| Titular | 18–59 | Qualquer | `TRUE` | Continua; e-mail obrigatório |
| Titular | 18–59 | Qualquer | `FALSE` | Continua; e-mail opcional |
| Titular | 60–99 | `FALSE` | `TRUE` | Continua; e-mail opcional pela exceção universal |
| Titular | 60–99 | `FALSE` | `FALSE` | Continua; e-mail opcional |
| Titular | 60–99 | `TRUE` | Qualquer | Encaminha e encerra sem bloqueio |
| Dependente | Faixa válida–59 | Qualquer | `TRUE` | Continua; e-mail do responsável obrigatório |
| Dependente | Faixa válida–59 | Qualquer | `FALSE` | Continua; e-mail do responsável opcional |
| Dependente | 60–99 | Qualquer | `TRUE` | Continua; e-mail do responsável obrigatório |
| Dependente | 60–99 | Qualquer | `FALSE` | Continua; e-mail do responsável opcional |
| Titular ou dependente | 100+ | Qualquer | Qualquer | Encaminhamento preexistente; encerra sem bloqueio |

Uma expressão como `não tenho dinheiro` na etapa de e-mail não é consumida como
ausência de e-mail. O tratamento financeiro tem prioridade, responde à dúvida e
repete a pergunta. A mesma precedência vale para mídia e reforço escolar.
