# Rotina de implementação de novas etapas

## Objetivo

Este documento define o padrão operacional para criar, alterar e conectar
etapas do atendimento.

Ele considera a arquitetura baseada em:

```text
chatbot.etapa
-> catálogo dos estados existentes

chatbot.etapa_transicao
-> mapa dos movimentos permitidos

response_flow
-> valida a resposta e identifica o evento

integração WhatsApp
-> monta e envia a mensagem

persistência final
-> confirma a transição e grava seus efeitos
```

A ordem numérica das etapas existe para facilitar leitura, logs e manutenção.
Ela não autoriza navegação. A próxima etapa nunca deve ser calculada com
`id_etapa_atual + 1`.

## Princípio central

Cada interação válida produz uma aresta:

```text
origem + evento -> destino
```

Exemplo:

```text
2 + para_mim          -> 4
2 + para_outra_pessoa -> 3
```

Os tratamentos não produzem aresta:

```text
mídia
pergunta financeira
contexto inválido
-> responder
-> permanecer na etapa atual
```

## Ordem operacional

Uma etapa nova deve ser construída nesta ordem.

### 1. Definir a regra de negócio

Antes do código, registrar:

- o que o bot perguntou;
- quais respostas são válidas;
- quais tratamentos são necessários;
- qual evento cada resposta válida produz;
- para qual etapa cada evento aponta;
- quais dados precisam ser persistidos;
- se a etapa pertence ao fluxo titular, dependente ou aos dois;
- se existe algum dado que não possa ser reconstruído pela mensagem original,
  pelo histórico e pela conversa.

A reconstrução comum já pertence à arquitetura. Em um retry, fila, histórico,
conversa e mapa de transições recompõem o contexto. Quem descreve a nova etapa
só precisa sinalizar dados externos, temporários ou ausentes da mensagem que
exijam uma estratégia adicional.

Exemplo:

```text
Origem: etapa 3
Pergunta: qual o nome do dependente?
Evento válido: nome_dependente_valido
Destino: etapa 4
Efeito: salvar dependente.nome_dependente
```

### 2. Cadastrar a etapa no deploy

Adicionar a etapa a:

```text
core/database/deploy/povoar_etapas.py
```

O ID deve ser estável e o nome deve explicar o estado:

```python
(3, "Nome do dependente")
```

Não reutilizar um ID antigo para outro significado.

### 3. Declarar o evento e a transição

Declarar o evento em:

```text
workers/worker_flow/response_flow/transicoes/eventos.py
```

Exemplo:

```python
EVENTO_NOME_DEPENDENTE_VALIDO = "nome_dependente_valido"
```

As constantes de etapa devem incluir número e significado:

```python
ETAPA_1_NOME_CLIENTE = 1
ETAPA_2_DESTINO_ATENDIMENTO = 2
ETAPA_3_NOME_DEPENDENTE = 3
ETAPA_4_IDADE_ALUNO = 4
```

Para novas etapas, seguir obrigatoriamente:

```text
ETAPA_<NÚMERO>_<SIGNIFICADO>
```

Registrar a aresta em:

```text
core/database/deploy/etapa_transicao_script.py
```

Exemplo:

```python
(3, "nome_dependente_valido", 4)
```

Uma origem e um evento possuem somente um destino. Uma origem e um destino
identificam somente um evento.

### 4. Preparar mensagens

Criar ou atualizar:

```text
core/integrations/whatsapp/messages/<etapa>_messages.py
```

Responsabilidades permitidas:

- constantes de texto;
- títulos e callbacks de botões;
- funções puras de montagem;
- interpolação de nome e outros valores;
- formatação nativa do WhatsApp.

Responsabilidades proibidas:

- importar PyWa;
- consultar banco ou Redis;
- decidir etapa;
- controlar retry;
- executar envio.

Exemplo:

```python
MENSAGEM_ETAPA3 = "Qual o nome da pessoa?"


def montar_mensagem_etapa3():
    return MENSAGEM_ETAPA3
```

### 5. Criar o sender

Criar ou atualizar:

```text
core/integrations/whatsapp/pywa_functions/pywa_senders/etapa3.py
```

O sender:

- chama a função de `messages`;
- escolhe texto, mídia e botões;
- usa PyWa;
- captura o ID retornado pela Meta;
- devolve o contexto técnico do envio;
- converte falhas da chamada externa em `ErroEnvioMeta`.

O sender não:

- escolhe a transição;
- executa SQL;
- altera conversa;
- marca fila como `sent`;
- conhece lock ou retry.

Contrato esperado:

```python
{
    "enviou": True,
    "resposta_ja_existia": False,
    "mensagem_bot": mensagem_bot,
    "id_hash_msg_bot": id_hash_msg_bot,
    "id_etapa_resultante": 3,
    "tipo_mensagem": "text",
    "canal": "meta_whatsapp",
    "atualizar_conversa": True,
    "atualizar_last_from_bot": True,
}
```

O worker acrescenta depois:

```python
{
    "id_etapa_origem_transicao": 2,
    "evento_transicao": "para_outra_pessoa",
}
```

### 6. Criar o validador de contexto

Se a resposta esperada for específica da etapa, criar:

```text
workers/worker_flow/response_flow/etapas/validadores_contexto/
```

Exemplos:

```text
valida_etapa2.py
valida_etapa3.py
valida_quarta_etapa.py
```

O validador específico:

- recebe dados simples;
- não chama sender;
- não consulta banco;
- não altera contexto;
- devolve evento ou resultado estruturado;
- devolve `None` ou resultado inválido quando não reconhecer a resposta.

Validadores reutilizados em diferentes etapas permanecem em:

```text
workers/worker_flow/response_flow/etapas/validadores_universais/
```

Exemplos:

```text
validador_midia.py
validador_financeiro.py
validador_nome.py
```

O validador de nome é universal porque valida tanto o nome do cliente quanto o
nome do dependente.

#### Regra de classificação dos validadores

Use um validador universal somente quando ele for reutilizado com o mesmo
significado e não escolher entre destinos diferentes. Ele pode identificar um
tratamento, manter a etapa ou liberar a continuação normal.

Use um validador contextual quando a resposta gerar eventos próprios da etapa,
principalmente se esses eventos pularem ou retrocederem no mapa. Validadores de
etapas distintas podem ter gramática semelhante e ainda assim permanecer
separados:

```text
etapa 5 + resposta positiva -> oferta_aceita
etapa 7 + resposta positiva -> retorno_confirmado
```

O resolver não deve traduzir uma decisão genérica para o evento. O próprio
validador contextual devolve o evento:

```python
evento_transicao = validar_etapa5(texto_cliente)

if evento_transicao is None:
    return sender_de_tratamento(...)

destinos_esperados = _destinos_esperados_por_evento(evento_transicao)
etapa_destino = resolver_destino_transicao(
    contexto_historico,
    evento_transicao,
    destinos_esperados=destinos_esperados,
)
```

### 7. Criar o resolver da etapa

Criar:

```text
workers/worker_flow/response_flow/etapas/resolver_etapa<n>.py
```

O arquivo representa a etapa à qual o cliente está respondendo. Ele possui duas
responsabilidades:

```text
validar a etapa atual
-> encaminhar para o sender do destino autorizado
```

Ordem recomendada:

```text
1. validar mídia
2. validar pergunta financeira
3. validar contexto específico
4. produzir evento
5. marcar a fronteira VALIDANDO DESTINO(S)
6. resolver destino pelo mapa
7. chamar o sender correspondente
8. anexar origem, evento e destino ao contexto de envio
```

O marcador obrigatório deve aparecer depois de todos os tratamentos:

```python
# VALIDANDO DESTINO(S)
# A resposta já passou pelos tratamentos; agora o mapa autoriza a aresta.
```

Modelo:

```python
def resolve_etapa3(contexto_historico):
    tipo_mensagem = contexto_historico["tipo_mensagem_atual"]
    texto_cliente = contexto_historico["texto_cliente_atual"]

    if validar_midia(tipo_mensagem):
        return enviar_etapa3_midia(...)

    if validar_pergunta_financeira(texto_cliente):
        return enviar_etapa3_financeiro(...)

    resultado = validar_nome_cliente(texto_cliente)

    if not resultado.valido:
        return enviar_etapa3_contexto_nome_invalido(...)

    destino = resolver_destino_transicao(
        contexto_historico,
        EVENTO_NOME_DEPENDENTE_VALIDO,
        destinos_esperados={ETAPA_4_IDADE_ALUNO},
    )

    contexto_envio = enviar_quarta_etapa(...)

    return anexar_transicao_ao_contexto_envio(
        contexto_historico,
        contexto_envio,
        EVENTO_NOME_DEPENDENTE_VALIDO,
        destino,
    )
```

Tratamentos retornam o sender da etapa atual sem `evento_transicao`.

### 8. Registrar o resolver no flow_sender

Atualizar:

```text
workers/worker_flow/response_flow/flow_sender.py
```

Exemplo:

```python
if id_etapa_atual == 3:
    return resolve_etapa3(contexto_historico)
```

O `flow_sender`:

- preserva `resposta_bot_atual` como primeira barreira;
- seleciona o resolver pela etapa atual;
- não decide destino;
- não executa SQL;
- não chama PyWa diretamente.

Uma etapa não implementada deve continuar levantando `NotImplementedError`.
Não retornar sucesso fictício.

Durante o desenvolvimento isolado de uma transição, uma simulação temporária
do sender de destino pode existir somente quando estiver explicitamente
marcada com `envio_simulado=True`, coberta por testes e sem ser classificada
como confirmação da Meta. O bloco deve ser removido assim que o sender real do
destino for implementado.

### 9. Implementar os efeitos da transição

Atualizar:

```text
workers/worker_flow/transacoes/efeitos_transicao.py
```

A navegação já foi escolhida pela tabela. Esse arquivo grava somente os efeitos
específicos da aresta e deve deixar cada ponte visualmente explícita:

```python
# ETAPA 2
if etapa_origem == ETAPA_2_DESTINO_ATENDIMENTO:
    if evento == EVENTO_PARA_MIM:
        # 2 -> 4

    if evento == EVENTO_PARA_OUTRA_PESSOA:
        # 2 -> 3
```

Exemplos:

```text
nome_cliente_valido
-> salvar cliente.nome

para_mim
-> status_dependente=False

para_outra_pessoa
-> status_dependente=True
-> criar dependente

nome_dependente_valido
-> salvar dependente.nome_dependente

idade_aluno_valida
-> salvar cliente.idade ou dependente.idade conforme status_dependente
```

Os efeitos devem:

- usar o mesmo cursor da transação final;
- ser idempotentes;
- validar evento, origem e destino esperados;
- conseguir reconstruir dados a partir da mensagem original no retry;
- levantar erro quando faltar um dado obrigatório;
- nunca executar em tratamento.

`atualizar_banco_conforme_transicao_de_etapa` não escolhe destino. Seu papel é:

```text
evento já autorizado
-> persistir efeitos de negócio
```

`persistencia_resposta.py` permanece como orquestrador curto da transação final.
`movimento_conversa.py` decide somente entre inicialização, transição e
permanência na etapa atual.

### 10. Ativar a aresta no conjunto final

Em desenvolvimento, catálogo, transição e implementação podem ser construídos
na mesma tarefa. Mesmo assim, a versão final só pode manter a aresta ativa
quando estiverem prontos:

```text
etapa cadastrada
evento declarado
mensagens
sender
validador
resolver
rota no flow_sender
efeitos transacionais
testes
```

Uma aresta ativa apontando para resolver ou sender inexistente deixa a conversa
em um estado sem atendimento.

## Subfluxo da integração WhatsApp

```text
resolver da etapa
-> sender específico
-> função de montagem em messages
-> cliente PyWa
-> Meta
-> contexto técnico do envio
```

Estrutura:

```text
core/integrations/whatsapp/
├── messages/
│   ├── etapa1_messages.py
│   ├── etapa2_messages.py
│   └── etapa3_messages.py
└── pywa_functions/
    ├── cliente.py
    ├── saudacao.py
    └── pywa_senders/
        ├── etapa1.py
        ├── etapa2.py
        └── etapa3.py
```

### Fronteiras

| Local | Decide conteúdo | Chama PyWa | Decide transição | Executa SQL |
|---|---:|---:|---:|---:|
| `messages` | Sim | Não | Não | Não |
| `pywa_senders` | Sim | Sim | Não | Não |
| resolver da etapa | Não | Não | Sim | Não |
| persistência final | Não | Não | Não | Sim |

## Subfluxo do response_flow

```text
valida_historico
-> carrega somente as transições da origem
-> flow_sender preserva idempotência
-> resolver da etapa aplica prioridades
-> validador produz evento
-> resolver_transicao localiza destino
-> sender envia
-> contexto_envio recebe origem + evento + destino
-> persistência final revalida no PostgreSQL
-> efeitos da aresta são persistidos
```

O contexto histórico carrega somente a fotografia da origem:

```python
{
    "id_etapa_origem_transicao": 2,
    "transicoes_permitidas": {
        "para_mim": 4,
        "para_outra_pessoa": 3,
    },
}
```

O contexto de envio carrega a decisão exata:

```python
{
    "id_etapa_origem_transicao": 2,
    "evento_transicao": "para_mim",
    "id_etapa_resultante": 4,
}
```

## Comentários estratégicos

Comentários devem explicar invariantes ou decisões que não são óbvias:

```python
# A origem vem do histórico da mensagem, não da etapa atual da conversa.
```

```python
# Tratamento responde, mas não produz evento de transição.
```

```python
# A tabela precisa autorizar a aresta antes da chamada externa.
```

Evitar comentários que apenas repetem o código:

```python
# Chama a função.
```

## Testes obrigatórios

### Messages e sender

- texto montado corretamente;
- parâmetros dinâmicos;
- botões e callbacks;
- ID da Meta retornado;
- `ErroEnvioMeta` em falha externa;
- `id_etapa_resultante` correto.

### Validador e resolver

- mídia tem prioridade;
- financeiro tem prioridade sobre contexto;
- resposta válida produz o evento correto;
- resposta inválida chama tratamento;
- tratamento não possui `evento_transicao`;
- mapa ausente impede sender;
- destino incompatível impede sender.

### Persistência

- PostgreSQL aceita somente origem, evento e destino cadastrados;
- efeito específico é persistido;
- tratamento não altera etapa;
- retry reconstrói o dado;
- resposta existente não chama Meta;
- reaplicação não regride conversa;
- falha provoca rollback e não marca fila como `sent`.

### Regressão

Sempre executar:

```text
test_fluxo_turno_abc
test_retry_lock_lifecycle
test_lastfrom_semantico
test_flow_sender
test_worker_support_finalizacao
test_repositories
```

## Definition of done

Uma etapa está concluída somente quando:

```text
[ ] regra de negócio definida
[ ] etapa cadastrada
[ ] evento declarado
[ ] aresta cadastrada
[ ] messages criada
[ ] sender criado
[ ] validador criado ou reutilizado
[ ] resolver criado
[ ] flow_sender atualizado
[ ] efeitos transacionais implementados
[ ] tratamentos permanecem na origem
[ ] retry reconstrói o contexto
[ ] resposta existente não duplica envio
[ ] testes específicos passam
[ ] suíte completa passa
[ ] Django check passa
[ ] compileall passa
[ ] documentação continua coerente
```

## O que não fazer

- não calcular destino com `id_etapa + 1`;
- não cadastrar auto-salto para representar tratamento;
- não decidir transição no sender;
- não importar PyWa no worker;
- não escrever mensagem do WhatsApp no resolver;
- não executar SQL em `messages` ou `pywa_senders`;
- não passar cursor para sender;
- não abrir conexão dentro do resolver;
- não atualizar etapa sem evento;
- não ativar aresta para etapa incompleta;
- não remover a barreira `resposta_bot_atual`;
- não alterar lock, turno ou retry para implementar conteúdo de etapa.

## Regra para futuras conversas de desenvolvimento

Ao receber uma solicitação de nova etapa:

1. conferir este documento;
2. mapear origem, evento, destino e tratamentos;
3. localizar as operações de banco específicas;
4. apresentar dúvidas de regra antes de codificar;
5. implementar seguindo a ordem operacional;
6. revisar idempotência, retry e concorrência;
7. testar a etapa e os fluxos críticos do sistema.

Se uma nova regra não se encaixar neste padrão, ela deve ser discutida antes de
introduzir exceção arquitetural.
