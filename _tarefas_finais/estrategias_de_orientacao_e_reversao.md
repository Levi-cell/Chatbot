# Estratégias de orientação e reversão do atendimento

## Finalidade

Este documento registra melhorias futuras para situações em que o cliente:

- clica em um botão de uma pergunta antiga;
- envia várias respostas antes de o bot concluir o turno atual;
- arrepende-se de uma escolha e precisa voltar a um ponto anterior do fluxo.

Essas estratégias não devem enfraquecer as regras atuais de turno,
idempotência, ordem cronológica, retry ou transação.

## Estado atual da V1

O webhook admite uma mensagem quando não existe outra mensagem anterior aberta
para a mesma conversa. Mensagens seguintes que encontram um turno
`pending/processing` são ignoradas com HTTP 200 para não gerar duas respostas
concorrentes.

Nos botões interativos, o webhook atualmente prioriza o título visível:

```python
button_reply.get("title") or button_reply.get("id")
```

Assim, o worker recebe textos como `Para mim`, mas não preserva separadamente a
identidade técnica do botão nem a etapa que o originou.

Por isso, a V1 utiliza orientação preventiva:

- mensagens com botões exibem `Selecione apenas uma opção abaixo.`;
- tratamentos de texto exibem
  `Dica: responda apenas à mensagem mais recente e envie uma resposta por vez.`.

## 1. Clique em botão antigo

### Experiência desejada

Quando o cliente clicar em outro botão de uma pergunta já respondida:

> Essa pergunta já foi respondida. Para continuar, responda à mensagem mais
> recente.

### Por que a V1 não identifica esse caso com precisão

O título do botão antigo chega ao worker como texto comum. Sem a identidade do
botão, `Para outra pessoa` pode ser:

- um botão antigo;
- uma mensagem digitada manualmente;
- uma resposta fora do contexto da etapa atual.

O tratamento genérico protege o fluxo, mas não pode afirmar com segurança que o
cliente clicou em uma pergunta antiga.

### Estratégia futura

1. Gerar `callback_data` com origem e opção:

```text
etapa:2|evento:para_mim
etapa:2|evento:para_outra_pessoa
```

2. Preservar no webhook tanto o título quanto `button_reply.id`.
3. Transportar a origem do botão pela fila sem substituir o texto visível.
4. Sob o lock da conversa, comparar a etapa de origem do botão com a etapa
   atual persistida.
5. Se forem diferentes, não executar o validador normal da etapa.
6. Chamar um sender específico para botão antigo.
7. Permanecer na etapa atual e repetir somente a pergunta mais recente.
8. Registrar o motivo técnico sem produzir evento de transição.

Uma resposta digitada manualmente continua sendo validada normalmente, pois ela
não possui a identidade técnica de um botão.

## 2. Várias respostas seguidas

### Experiência desejada

Quando o cliente enviar várias respostas antes da próxima mensagem do bot:

> Para seguirmos direitinho, envie uma resposta por vez e aguarde minha próxima
> mensagem. 😊

### Limitação atual

As mensagens excedentes são barradas no webhook e não chegam ao worker. Como o
worker nunca as recebe, nenhum validador ou sender do `response_flow` consegue
responder diretamente a elas.

Fazer o webhook enviar WhatsApp quebraria a separação arquitetural: a borda HTTP
passaria a decidir e enviar respostas do fluxo.

### Estratégia futura recomendada

1. O webhook continua descartando a mensagem excedente com HTTP 200.
2. Ele incrementa no Redis um contador curto por cliente e unidade.
3. A chave recebe TTL pequeno para representar somente a rajada atual.
4. O worker consulta esse sinal em um ponto controlado do próximo ciclo.
5. A orientação é anexada a uma resposta apropriada, sem criar duas respostas
   do bot para o mesmo turno.
6. Depois de utilizada, a sinalização é removida de forma idempotente.
7. Aplicar limite para não repetir a orientação em toda mensagem.

Outra possibilidade é registrar eventos operacionais no banco e processá-los
assincronamente. Essa alternativa oferece auditoria, mas custa mais e não é
necessária para o volume inicial.

## 3. Estratégia de arrependimento

### Objetivo

Permitir que o cliente reverta uma decisão tomada por engano ou porque mudou de
ideia, sem alterar `id_etapa_atual` manualmente nem calcular `etapa - 1`.

Exemplos:

- escolheu atendimento para si, mas deseja informar um dependente;
- adiou a oferta, mas decidiu agendar;
- informou um dado incorreto e deseja corrigi-lo.

### Regra central

Toda reversão deve ser uma aresta explícita do mapa:

```text
origem + evento_de_reversao -> destino_autorizado
```

Nunca utilizar:

```text
id_etapa_atual - 1
```

O fluxo possui saltos e ramificações; a etapa numericamente anterior nem sempre
representa o estado correto.

### Implementação proposta

1. Definir em quais etapas o arrependimento é permitido.
2. Criar um evento específico, como `alterar_destino_atendimento`.
3. Cadastrar a transição reversa em `chatbot.etapa_transicao`.
4. Expor uma opção clara, como `Alterar resposta`, somente onde fizer sentido.
5. Resolver e revalidar a aresta pelo mesmo mecanismo das transições normais.
6. Limpar, na transação final, apenas os dados derivados da decisão revertida.
7. Preservar o histórico das mensagens para auditoria.
8. Enviar novamente a pergunta do destino autorizado.
9. Garantir idempotência em retries e respostas já existentes.

### Limpeza dos efeitos derivados

Voltar para uma etapa anterior não pode deixar dados incompatíveis:

```text
para_outra_pessoa -> para_mim
```

Pode exigir:

- remover o dependente criado naquela conversa;
- limpar `status_dependente`;
- invalidar idade e nome derivados do caminho abandonado;
- remover respostas da triagem posteriores ao ponto de retorno;
- recalcular elegibilidade de encerramento ou funil.

Essa limpeza deve acontecer no mesmo commit da transição reversa. Se qualquer
efeito falhar, toda a operação sofre rollback e a conversa permanece no estado
anterior consistente.

### Restrições

- Não permitir reversão depois de bloqueio definitivo sem uma regra própria.
- Não apagar histórico para esconder a escolha anterior.
- Não reutilizar respostas de uma ramificação abandonada automaticamente.
- Não permitir que callback antigo acione uma reversão.
- Não criar uma transição genérica capaz de voltar para qualquer etapa.

## Ordem recomendada de implementação

1. Manter apenas as orientações visuais na V1.
2. Preservar a identidade técnica dos botões.
3. Implementar detecção de botão antigo.
4. Medir se rajadas de mensagens realmente afetam clientes.
5. Implementar arrependimento somente nos pontos confirmados pelo produto.
