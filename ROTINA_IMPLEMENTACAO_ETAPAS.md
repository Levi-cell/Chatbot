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
2 + destino_atendimento_definido -> 3
3 + destino_atendimento_confirmado_titular    -> 4
3 + destino_atendimento_confirmado_dependente -> 5
4 + profissao_dependente_valida  -> 5
4 + profissao_titular_valida     -> 6
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
Origem: etapa 4
Pergunta: qual sua profissão?
Eventos válidos: profissao_dependente_valida ou profissao_titular_valida
Destinos: etapa 5 ou etapa 6
Efeito: salvar conversa.profissao
```

### 2. Cadastrar a etapa no deploy

Adicionar a etapa a:

```text
core/database/deploy_database/povoar_etapas.py
```

O ID deve ser estável e o nome deve explicar o estado:

```python
(4, "Profissão do cliente")
```

Não reutilizar um ID antigo para outro significado.

`povoar_etapas.py` e `etapa_transicao_script.py` devem sempre representar o
catálogo e o mapa finais de uma instalação limpa. Quando já existir banco com
referências às etapas, atualize primeiro esses arquivos canônicos e entregue o
remapeamento incremental separadamente em `deploy/migrations/*.sql`, para
execução manual no DBeaver. Não acumule `ALTER TABLE`, `UPDATE` de migração ou
outro histórico de implantação nos scripts Python de criação e seed.

### 3. Declarar o evento e a transição

Declarar o evento em:

```text
workers/worker_flow/response_flow/transicoes/eventos.py
```

Exemplo:

```python
EVENTO_PROFISSAO_TITULAR_VALIDA = "profissao_titular_valida"
```

As constantes de etapa devem incluir número e significado:

```python
ETAPA_1_NOME_CLIENTE = 1
ETAPA_2_DESTINO_ATENDIMENTO = 2
ETAPA_3_CONFIRMACAO_DESTINO = 3
ETAPA_4_PROFISSAO = 4
ETAPA_5_NOME_DEPENDENTE = 5
ETAPA_6_IDADE_ALUNO = 6
```

Para novas etapas, seguir obrigatoriamente:

```text
ETAPA_<NÚMERO>_<SIGNIFICADO>
```

Registrar a aresta em:

```text
core/database/deploy_database/etapa_transicao_script.py
```

Exemplo:

```python
(4, "profissao_titular_valida", 6)
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

Quando várias etapas e integrações precisarem do mesmo catálogo de conteúdo,
centralize-o em um módulo neutro de domínio. Na triagem, as etapas 12 a 17 e o
Funil usam `core/triagem/perguntas.py`; mensagens e observações não devem
duplicar as perguntas nem a regra `< 18`/`>= 18`.

Ramificações apenas de mensagem não exigem novas etapas. Antes de criar ou
renumerar uma etapa, confirme se evento, destino, efeito e persistência são os
mesmos. Se somente o texto varia por um dado já persistido, releia esse dado no
contexto, escolha a mensagem e preserve o mapa transacional existente.

Exemplo:

```python
MENSAGEM_ETAPA4 = "Qual é a sua profissão?"


def montar_mensagem_etapa4():
    return MENSAGEM_ETAPA4
```

### 5. Criar o sender

Criar ou atualizar:

```text
core/integrations/whatsapp/pywa_functions/pywa_senders/etapa4.py
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
    "id_etapa_resultante": 4,
    "tipo_mensagem": "text",
    "canal": "meta_whatsapp",
    "atualizar_conversa": True,
    "atualizar_last_from_bot": True,
}
```

O worker acrescenta depois:

```python
{
    "id_etapa_origem_transicao": 3,
    "evento_transicao": "destino_atendimento_confirmado_titular",
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
valida_etapa4.py
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
etapa 7 + resposta positiva -> oferta_aceita
etapa 9 + resposta positiva -> retorno_confirmado
```

Uma especialização local de um tratamento universal também permanece em
`validadores_contexto/` quando o mesmo vocabulário puder ser uma resposta
legítima apenas naquela etapa. Ela deve aplicar somente a desambiguação local e
depois delegar ao validador universal, sem sender, banco ou alteração de
contexto. Não duplique nem enfraqueça a regra compartilhada para acomodar uma
única etapa.

O resolver não deve traduzir uma decisão genérica para o evento. O próprio
validador contextual devolve o evento:

```python
evento_transicao = validar_etapa7(texto_cliente)

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
2. validar dúvida sobre reforço escolar
3. validar pergunta financeira
4. validar contexto específico
5. produzir evento
6. marcar a fronteira VALIDANDO DESTINO(S)
7. resolver destino pelo mapa
8. chamar o sender correspondente
9. anexar origem, evento e destino ao contexto de envio
```

O marcador obrigatório deve aparecer depois de todos os tratamentos:

```python
# VALIDANDO DESTINO(S)
# A resposta já passou pelos tratamentos; agora o mapa autoriza a aresta.
```

Modelo:

```python
def resolve_etapa4(contexto_historico):
    tipo_mensagem = contexto_historico["tipo_mensagem_atual"]
    texto_cliente = contexto_historico["texto_cliente_atual"]

    if validar_midia(tipo_mensagem):
        return enviar_etapa4_midia(...)

    if validar_duvida_reforco_escolar_etapa4(texto_cliente):
        return enviar_etapa4_reforco_escolar(...)

    if validar_pergunta_financeira(texto_cliente):
        return enviar_etapa4_financeiro(...)

    resultado = validar_profissao_etapa4(
        texto_cliente,
        tipo_mensagem,
    )

    if not resultado.valida:
        return enviar_etapa4_contexto_profissao_invalida(...)

    destino = resolver_destino_transicao(
        contexto_historico,
        EVENTO_PROFISSAO_TITULAR_VALIDA,
        destinos_esperados={ETAPA_6_IDADE_ALUNO},
    )

    contexto_envio = enviar_etapa6_cliente(...)
    contexto_envio["profissao"] = resultado.profissao

    return anexar_transicao_ao_contexto_envio(
        contexto_historico,
        contexto_envio,
        EVENTO_PROFISSAO_TITULAR_VALIDA,
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
if id_etapa_atual == 4:
    return resolve_etapa4(contexto_historico)
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
    if evento == EVENTO_DESTINO_ATENDIMENTO_DEFINIDO:
        # 2 -> 3: persiste a escolha antes de pedir confirmação.

# ETAPA 3
if etapa_origem == ETAPA_3_CONFIRMACAO_DESTINO:
    if evento == EVENTO_DESTINO_ATENDIMENTO_CONFIRMADO_TITULAR:
        # 3 -> 4

    if evento == EVENTO_DESTINO_ATENDIMENTO_CONFIRMADO_DEPENDENTE:
        # 3 -> 5

# ETAPA 4
if etapa_origem == ETAPA_4_PROFISSAO:
    if evento == EVENTO_PROFISSAO_DEPENDENTE_VALIDA:
        # 4 -> 5

    if evento == EVENTO_PROFISSAO_TITULAR_VALIDA:
        # 4 -> 6
```

Exemplos:

```text
nome_cliente_valido
-> salvar cliente.nome

destino_atendimento_definido
-> salvar status_dependente
-> criar dependente quando o atendimento for para outra pessoa

profissao_dependente_valida
-> salvar conversa.profissao
-> seguir para o nome do dependente

profissao_titular_valida
-> salvar conversa.profissao
-> seguir diretamente para a idade

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
    "id_etapa_origem_transicao": 4,
    "transicoes_permitidas": {
        "profissao_dependente_valida": 5,
        "profissao_titular_valida": 6,
    },
}
```

O contexto de envio carrega a decisão exata:

```python
{
    "id_etapa_origem_transicao": 4,
    "evento_transicao": "profissao_titular_valida",
    "id_etapa_resultante": 6,
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
test_retry_essencial
test_lastfrom_semantico
test_roteamento_essencial
test_persistencia_essencial
test_persistencia_essencial
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
