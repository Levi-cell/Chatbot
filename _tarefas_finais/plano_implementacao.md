# Plano arquivado - fluxo de 24 etapas com confirmação de dados

## Estado do documento

Este plano substitui integralmente o plano anterior de retorno direto para a
etapa 2. Nenhum código deste documento foi aplicado ao projeto.

O documento fica **arquivado para avaliação futura**. O fluxo atualmente
implementado continua sendo a versão escolhida para produção; a existência
deste arquivo não autoriza aplicação parcial nem automática de suas mudanças.

> **Observação para uma eventual aplicação futura:** antes de usar este
> plano, ele deverá ser revisado e receber pequenas otimizações para incluir
> `conversa.motivo_encerramento` em todos os encerramentos, usar
> `{nome_unidade}` na saudação da etapa 5 destinada ao cliente novo e adaptar
> o worker periódico do funil para considerar elegibilidade a partir da nova
> etapa 24. Os blocos de código abaixo ainda não incorporam essas mudanças.

Cada passo abaixo apresenta o conteúdo completo do arquivo criado ou alterado.
Arquivos explicitamente removidos aparecem em uma seção própria, pois não
possuem conteúdo final.

## Objetivo

Reorganizar o atendimento em 24 estados explícitos para:

1. diferenciar cliente veterano de cliente novato por cliente + unidade;
2. permitir que o veterano mantenha ou atualize o nome;
3. persistir cada dado válido na coleta e permitir sua correção pela etapa de
   confirmação;
4. preservar tratamentos de mídia, financeiro e contexto;
5. preservar fila, histórico, idempotência, retry, regra de turno e bloqueio;
6. identificar nominalmente a unidade na saudação do cliente novato;
7. tornar o lead elegível ao funil a partir da etapa 23;
8. manter a etapa 24 como terminal com bloqueio de 30 dias.

## Decisões fechadas

- `cliente.nome` continua global por `wa_id`.
- Não será criada relação de nome por cliente e unidade.
- Veterano significa: existe conversa anterior encerrada do mesmo cliente na
  mesma unidade e `cliente.nome` está preenchido.
- Cliente conhecido em outra unidade, mas sem conversa anterior na unidade
  atual, é novato naquela unidade e começa na etapa 5.
- Conversas anteriores, dependentes, histórico e fila nunca são apagados pelo
  encerramento por idade.
- Nome, nome do dependente, idade permitida e email são persistidos assim que
  a resposta válida produz a transição para a confirmação.
- O valor exibido na confirmação continua reconstruído pelo histórico da
  conversa, não por variável volátil nem por nova coluna temporária.
- A resposta `Não` volta exatamente à etapa que coletou o dado, sem apagar,
  limpar ou gravar `NULL`; o valor anterior permanece até a próxima resposta
  válida executar o `UPDATE` que o substitui.
- Idade acima de 99, idade do titular abaixo de 18 e idade do dependente abaixo
  do mínimo da unidade encerram a conversa ainda na etapa 9, antes da etapa de
  confirmação.
- A resposta válida da sexta pergunta produz diretamente `22 -> 23` e envia a
  mensagem de agendamento. Não existe etapa técnica intermediária nem cadeia
  automática de transições.
- A etapa 23 marca elegibilidade ao funil e permanece ativa aguardando uma
  interação explícita que confirme o agendamento.
- Somente uma confirmação aceita na etapa 23 produz `23 -> 24`, envia a
  mensagem final e permite que a política da etapa 24 encerre a conversa.
- A etapa 24 é terminal porque sua política declara encerramento e bloqueio,
  não porque possui o maior ID.
- Meta-first, transações do worker, commits, fila, histórico, locks, regra de
  turno, retry e idempotência permanecem exatamente sob os contratos atuais.
  Este plano altera somente o fluxo de atendimento, seus componentes e o mapa
  `origem + evento -> destino`, usando o motor transacional já existente.
- O Redis não precisa guardar nome da unidade, veterano ou candidatos.

## Correção de interpretação do mapa solicitado

O mapa final informado pelo usuário é a fonte de verdade deste plano. Assim,
uma frase anterior que dizia que o cliente com conversa encerrada começaria na
etapa 2 fica substituída pela regra definitiva: veterano começa na etapa 1; a
etapa 2 só é alcançada quando ele escolhe `Mudar nome`. Cliente novato naquela
unidade começa na etapa 5.

Na descrição inicial apareceu que as etapas 4 e 6 poderiam apontar para a
etapa 8 ao escolher `Para mim`. A etapa 8 confirma exclusivamente o nome do
dependente, portanto o fluxo coerente é:

```text
4/6 + para_mim          -> 9
4/6 + para_outra_pessoa -> 7
7   + nome informado    -> 8
8   + sim               -> 9
```

Da mesma forma, a etapa 11 não é destino direto da etapa 8. O caminho fechado
é `8 -> 9 -> 10 -> 11`, pois o nome do dependente precisa ser confirmado,
depois a idade precisa ser coletada e confirmada antes da oferta.

## Mapa final

| Etapa | Estado | Destinos possíveis |
|---:|---|---|
| 1 | Retorno do veterano | 2 ou 4 |
| 2 | Novo nome do veterano | 3 |
| 3 | Confirmação do nome do cliente | 2, 4, 5 ou 6 |
| 4 | Destino do atendimento do veterano | 7 ou 9 |
| 5 | Saudação e nome do novato | 3 |
| 6 | Apresentação e destino do novato | 7 ou 9 |
| 7 | Nome do dependente | 8 |
| 8 | Confirmação do nome do dependente | 7 ou 9 |
| 9 | Idade do aluno | 10 ou encerramento sem bloqueio |
| 10 | Confirmação da idade permitida | 9 ou 11 |
| 11 | Oferta | 12 ou 14 |
| 12 | Oferta adiada | 13 |
| 13 | Retorno à oferta | 12 ou 14 |
| 14 | Email | 15 |
| 15 | Confirmação do email | 14 ou 16 |
| 16 | Introdução à triagem | 17 |
| 17–22 | Seis perguntas da triagem | próxima etapa |
| 23 | Agendamento pendente e lead elegível | 24 somente após confirmação explícita |
| 24 | Mensagem final e finalização | terminal, bloqueio de 30 dias |

## Persistência dos candidatos

```text
mensagem com nome/idade/email
-> validador extrai candidato
-> sender apresenta etapa de confirmação
-> depois do envio Meta bem-sucedido, a primeira transação local:
   - guarda a resposta do bot no histórico;
   - move a conversa para a etapa de confirmação;
   - persiste imediatamente o valor válido coletado
-> commit da resposta, movimento e efeito
-> segunda transação aplica eventual encerramento e marca a fila como sent
-> commit da finalização; eventual bloqueio Redis é materializado depois
-> confirmação seguinte consulta esse histórico
-> Sim: prossegue sem uma segunda escrita do mesmo dado
-> Não: volta à coleta sem apagar o valor atual
-> próxima resposta válida: substitui o valor anterior no banco
```

Essa ordem preserva o contrato Meta-first já usado pelo worker. Portanto,
"persistir na coleta" não significa escrever antes da chamada externa: significa
que, depois de a confirmação ser enviada com sucesso, o dado fica confirmado no
mesmo commit que registra a resposta e a transição, antes de a mensagem da fila
ser marcada como concluída. A segunda transação já existente continua cuidando
do encerramento e do `sent`; essa separação preserva os cenários A/B/C atuais.
Se qualquer commit falhar, o retry continua reconstruindo candidato, resposta e
aresta pelo histórico/fila, sem depender de memória volátil.

Se a idade estiver fora da faixa permitida, o fluxo envia a mensagem de
encerramento e não chega à confirmação. Resposta, movimento e efeitos continuam
na primeira transação; encerramento e conclusão da fila continuam na segunda,
mantendo o contexto reconstruível nos cenários A/B/C e em qualquer retry.

## Ordem fechada da idade

```text
etapa 9 recebe a resposta
-> mídia/financeiro continuam usando seus tratamentos atuais
-> validador extrai uma única idade
-> idade inválida sintaticamente: tratamento e permanência na etapa 9
-> idade acima de 99: mensagem da consultora e encerramento sem bloqueio
-> titular abaixo de 18: mensagem específica e encerramento sem bloqueio
-> dependente abaixo de 4 com BPA ou abaixo de 5 sem BPA:
   mensagem específica e encerramento sem bloqueio
-> somente idade permitida é persistida e segue para confirmação na etapa 10
```

Uma conversa encerrada por qualquer um desses cortes permanece armazenada e
inativa. Como a classificação consulta qualquer conversa inativa anterior do
mesmo cliente na mesma unidade, a próxima conversa começa na etapa 1 como
veterano. Em outra unidade, o mesmo cliente continua sendo classificado de
forma independente.

A etapa 23 representa o instante semântico em que o lead se torna elegível ao
funil. A conversa permanece armazenada e ativa nessa etapa até o cliente
confirmar o agendamento. Portanto, a consulta periódica do funil passa a usar
`etapa.elegivel_funil`, sem exigir que a conversa já esteja encerrada. Se o
cliente confirmar antes do envio ao funil, a etapa 24 preserva
`elegivel_funil=True`; `lead_no_funil` continua impedindo duplicidade nos dois
estados.

## Confirmação explícita do agendamento

Na etapa 23, clicar no botão `Já agendei` ou enviar uma frase que contenha uma
das expressões aceitas produz a transição para a etapa 24. A comparação é feita
após normalização de caixa, acentos, pontuação e espaços, com limites de palavra
para não aceitar uma expressão apenas como parte de outra palavra.

Exemplos aceitos:

```text
Já agendei
Agendado para sexta às 14h
Consegui agendar para amanhã
Já marquei a avaliação
```

Qualquer mensagem sem uma dessas expressões recebe tratamento e mantém a
conversa na etapa 23. Não existe avanço automático `23 -> 24`.

## Fase 1 - Catálogo e mapa

### Passo 1 - Sincronizar as 24 etapas

Arquivo: `core/database/deploy/povoar_etapas.py`

```python
import logging

from core.database.deploy.transacao_deploy import transacao_deploy


logger = logging.getLogger("db.seed")


ETAPAS = (
    (1, "Retorno do cliente veterano", False, 0, False),
    (2, "Novo nome do cliente veterano", False, 0, False),
    (3, "Confirmação do nome do cliente", False, 0, False),
    (4, "Destino do atendimento do veterano", False, 0, False),
    (5, "Saudação e nome do cliente novato", False, 0, False),
    (6, "Apresentação e destino do cliente novato", False, 0, False),
    (7, "Nome do dependente", False, 0, False),
    (8, "Confirmação do nome do dependente", False, 0, False),
    (9, "Idade do aluno", False, 0, False),
    (10, "Confirmação da idade do aluno", False, 0, False),
    (11, "Oferta de aula experimental e avaliação cognitiva", False, 0, False),
    (12, "Oferta adiada e Instagram", False, 0, False),
    (13, "Confirmação de retorno ao atendimento", False, 0, False),
    (14, "Email do cliente", False, 0, False),
    (15, "Confirmação do email do cliente", False, 0, False),
    (16, "Introdução à triagem cognitiva", False, 0, False),
    (17, "Triagem cognitiva - pergunta 1", False, 0, False),
    (18, "Triagem cognitiva - pergunta 2", False, 0, False),
    (19, "Triagem cognitiva - pergunta 3", False, 0, False),
    (20, "Triagem cognitiva - pergunta 4", False, 0, False),
    (21, "Triagem cognitiva - pergunta 5", False, 0, False),
    (22, "Triagem cognitiva - pergunta 6", False, 0, False),
    (23, "Agendamento pendente e lead elegível", False, 0, True),
    (24, "Mensagem final e finalização do atendimento", True, 30, True),
)


def insere_etapa_once():
    with transacao_deploy("sincronizar_etapas", logger) as cursor:
        cursor.executemany(
            """
            INSERT INTO chatbot.etapa (
                id_etapa,
                nome_etapa,
                encerra_automaticamente,
                bloqueio_dias,
                elegivel_funil
            )
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (id_etapa)
            DO UPDATE SET
                nome_etapa = EXCLUDED.nome_etapa,
                encerra_automaticamente = EXCLUDED.encerra_automaticamente,
                bloqueio_dias = EXCLUDED.bloqueio_dias,
                elegivel_funil = EXCLUDED.elegivel_funil;
            """,
            ETAPAS,
        )

        cursor.execute(
            """
            SELECT setval(
                pg_get_serial_sequence('chatbot.etapa', 'id_etapa'),
                (SELECT MAX(id_etapa) FROM chatbot.etapa),
                TRUE
            );
            """
        )

    logger.info(
        "banco_seed_ok | acao=sincronizar_etapas quantidade=%s",
        len(ETAPAS),
    )
```

> Observação de aplicação: os IDs antigos mudam de significado. Em
> desenvolvimento, o banco deve ser recriado antes desta versão. Em uma base
> produtiva com atendimentos reais, é obrigatória uma migração de dados
> dedicada; o seed não tenta reinterpretar históricos existentes.

### Passo 2 - Sincronizar o mapa de transições

Arquivo: `core/database/deploy/etapa_transicao_script.py`

```python
import logging

from core.database.deploy.transacao_deploy import transacao_deploy


logger = logging.getLogger("db.etapa_transicao")


TRANSICOES_INICIAIS = (
    (1, "atualizar_nome", 2),
    (1, "novo_atendimento", 4),
    (2, "nome_cliente_informado", 3),
    (3, "nome_cliente_confirmado_veterano", 4),
    (3, "nome_cliente_rejeitado_veterano", 2),
    (3, "nome_cliente_confirmado_novato", 6),
    (3, "nome_cliente_rejeitado_novato", 5),
    (4, "para_mim", 9),
    (4, "para_outra_pessoa", 7),
    (5, "nome_cliente_informado", 3),
    (6, "para_mim", 9),
    (6, "para_outra_pessoa", 7),
    (7, "nome_dependente_informado", 8),
    (8, "nome_dependente_confirmado", 9),
    (8, "nome_dependente_rejeitado", 7),
    (9, "idade_informada", 10),
    (10, "idade_confirmada", 11),
    (10, "idade_rejeitada", 9),
    (11, "oferta_aceita", 14),
    (11, "oferta_adiada", 12),
    (12, "cliente_retornou", 13),
    (13, "retorno_confirmado", 14),
    (13, "retorno_adiado", 12),
    (14, "email_informado", 15),
    (15, "email_confirmado", 16),
    (15, "email_rejeitado", 14),
    (16, "triagem_iniciada", 17),
    (17, "triagem_pergunta_1_respondida", 18),
    (18, "triagem_pergunta_2_respondida", 19),
    (19, "triagem_pergunta_3_respondida", 20),
    (20, "triagem_pergunta_4_respondida", 21),
    (21, "triagem_pergunta_5_respondida", 22),
    (22, "triagem_pergunta_6_respondida", 23),
    (23, "agendamento_confirmado", 24),
)


def criar_e_povoar_transicoes_etapa():
    with transacao_deploy("sincronizar_mapa_transicoes", logger) as cursor:
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS chatbot.etapa_transicao (
                id_transicao SERIAL PRIMARY KEY,
                id_etapa_origem INT NOT NULL,
                evento VARCHAR(100) NOT NULL,
                id_etapa_destino INT NOT NULL,

                CONSTRAINT etapa_transicao_origem_fkey
                    FOREIGN KEY (id_etapa_origem)
                    REFERENCES chatbot.etapa(id_etapa)
                    ON DELETE RESTRICT,

                CONSTRAINT etapa_transicao_destino_fkey
                    FOREIGN KEY (id_etapa_destino)
                    REFERENCES chatbot.etapa(id_etapa)
                    ON DELETE RESTRICT,

                CONSTRAINT etapa_transicao_sem_auto_salto
                    CHECK (id_etapa_origem <> id_etapa_destino),

                CONSTRAINT etapa_transicao_origem_evento_unique
                    UNIQUE (id_etapa_origem, evento),

                CONSTRAINT etapa_transicao_origem_destino_unique
                    UNIQUE (id_etapa_origem, id_etapa_destino)
            );
            """
        )

        cursor.execute(
            "TRUNCATE TABLE chatbot.etapa_transicao RESTART IDENTITY;"
        )
        cursor.executemany(
            """
            INSERT INTO chatbot.etapa_transicao (
                id_etapa_origem,
                evento,
                id_etapa_destino
            )
            VALUES (%s, %s, %s);
            """,
            TRANSICOES_INICIAIS,
        )

    logger.info(
        "etapa_transicao_setup_ok | acao=sincronizar_mapa quantidade=%s",
        len(TRANSICOES_INICIAIS),
    )
```

### Passo 3 - Centralizar IDs e eventos

Arquivo: `workers/worker_flow/response_flow/transicoes/eventos.py`

```python
ETAPA_1_RETORNO_VETERANO = 1
ETAPA_2_NOVO_NOME_VETERANO = 2
ETAPA_3_CONFIRMACAO_NOME_CLIENTE = 3
ETAPA_4_DESTINO_VETERANO = 4
ETAPA_5_NOME_CLIENTE_NOVATO = 5
ETAPA_6_DESTINO_NOVATO = 6
ETAPA_7_NOME_DEPENDENTE = 7
ETAPA_8_CONFIRMACAO_NOME_DEPENDENTE = 8
ETAPA_9_IDADE_ALUNO = 9
ETAPA_10_CONFIRMACAO_IDADE = 10
ETAPA_11_OFERTA_AULA = 11
ETAPA_12_OFERTA_ADIADA = 12
ETAPA_13_RETORNO_OFERTA = 13
ETAPA_14_EMAIL = 14
ETAPA_15_CONFIRMACAO_EMAIL = 15
ETAPA_16_INTRODUCAO_TRIAGEM = 16
ETAPA_17_TRIAGEM_PERGUNTA_1 = 17
ETAPA_18_TRIAGEM_PERGUNTA_2 = 18
ETAPA_19_TRIAGEM_PERGUNTA_3 = 19
ETAPA_20_TRIAGEM_PERGUNTA_4 = 20
ETAPA_21_TRIAGEM_PERGUNTA_5 = 21
ETAPA_22_TRIAGEM_PERGUNTA_6 = 22
ETAPA_23_AGENDAMENTO_PENDENTE = 23
ETAPA_24_FINALIZACAO = 24

EVENTO_ATUALIZAR_NOME = "atualizar_nome"
EVENTO_NOVO_ATENDIMENTO = "novo_atendimento"
EVENTO_NOME_CLIENTE_INFORMADO = "nome_cliente_informado"
EVENTO_NOME_CLIENTE_CONFIRMADO_VETERANO = (
    "nome_cliente_confirmado_veterano"
)
EVENTO_NOME_CLIENTE_REJEITADO_VETERANO = (
    "nome_cliente_rejeitado_veterano"
)
EVENTO_NOME_CLIENTE_CONFIRMADO_NOVATO = "nome_cliente_confirmado_novato"
EVENTO_NOME_CLIENTE_REJEITADO_NOVATO = "nome_cliente_rejeitado_novato"
EVENTO_PARA_MIM = "para_mim"
EVENTO_PARA_OUTRA_PESSOA = "para_outra_pessoa"
EVENTO_NOME_DEPENDENTE_INFORMADO = "nome_dependente_informado"
EVENTO_NOME_DEPENDENTE_CONFIRMADO = "nome_dependente_confirmado"
EVENTO_NOME_DEPENDENTE_REJEITADO = "nome_dependente_rejeitado"
EVENTO_IDADE_INFORMADA = "idade_informada"
EVENTO_IDADE_CONFIRMADA = "idade_confirmada"
EVENTO_IDADE_REJEITADA = "idade_rejeitada"
EVENTO_OFERTA_ACEITA = "oferta_aceita"
EVENTO_OFERTA_ADIADA = "oferta_adiada"
EVENTO_CLIENTE_RETORNOU = "cliente_retornou"
EVENTO_RETORNO_CONFIRMADO = "retorno_confirmado"
EVENTO_RETORNO_ADIADO = "retorno_adiado"
EVENTO_EMAIL_INFORMADO = "email_informado"
EVENTO_EMAIL_CONFIRMADO = "email_confirmado"
EVENTO_EMAIL_REJEITADO = "email_rejeitado"
EVENTO_TRIAGEM_INICIADA = "triagem_iniciada"
EVENTO_TRIAGEM_PERGUNTA_1_RESPONDIDA = "triagem_pergunta_1_respondida"
EVENTO_TRIAGEM_PERGUNTA_2_RESPONDIDA = "triagem_pergunta_2_respondida"
EVENTO_TRIAGEM_PERGUNTA_3_RESPONDIDA = "triagem_pergunta_3_respondida"
EVENTO_TRIAGEM_PERGUNTA_4_RESPONDIDA = "triagem_pergunta_4_respondida"
EVENTO_TRIAGEM_PERGUNTA_5_RESPONDIDA = "triagem_pergunta_5_respondida"
EVENTO_TRIAGEM_PERGUNTA_6_RESPONDIDA = "triagem_pergunta_6_respondida"
EVENTO_AGENDAMENTO_CONFIRMADO = "agendamento_confirmado"
```

## Fase 2 - Contexto reconstruível

### Passo 4 - Carregar o contexto estável do atendimento

Arquivo: `core/repositories/contexto_atendimento.py`

```python
import logging


logger = logging.getLogger("db.contexto_atendimento")


def buscar_contexto_atendimento(
    id_conversa,
    id_cliente,
    id_unidade,
    cursor,
):
    """Carrega identidade, unidade e classificação veterano/novato."""
    cursor.execute(
        """
        SELECT
            NULLIF(BTRIM(cl.nome), '') AS nome_cliente,
            NULLIF(BTRIM(cl.email), '') AS email_cliente,
            NULLIF(BTRIM(u.nome), '') AS nome_unidade,
            NULLIF(BTRIM(u.numero_comercial), '') AS numero_comercial,
            NULLIF(BTRIM(u.link_agendamento), '') AS link_agendamento,
            NULLIF(BTRIM(u.link_instagram), '') AS link_instagram,
            u.bpa_ativo,
            d.id_dependente,
            NULLIF(BTRIM(d.nome_dependente), '') AS nome_dependente,
            d.idade AS idade_dependente,
            cl.idade AS idade_cliente,
            EXISTS (
                SELECT 1
                FROM chatbot.conversa anterior
                WHERE anterior.id_cliente = atual.id_cliente
                  AND anterior.id_unidade = atual.id_unidade
                  AND anterior.id_conversa <> atual.id_conversa
                  AND anterior.status_ativa = FALSE
            ) AS possui_conversa_anterior
        FROM chatbot.conversa atual
        JOIN chatbot.cliente cl
          ON cl.id_cliente = atual.id_cliente
        JOIN chatbot.unidade u
          ON u.id_unidade = atual.id_unidade
        LEFT JOIN LATERAL (
            SELECT
                dep.id_dependente,
                dep.nome_dependente,
                dep.idade
            FROM chatbot.dependente dep
            WHERE dep.id_conversa = atual.id_conversa
            ORDER BY dep.id_dependente DESC
            LIMIT 1
        ) d ON TRUE
        WHERE atual.id_conversa = %s
          AND atual.id_cliente = %s
          AND atual.id_unidade = %s
          AND atual.status_ativa = TRUE
        LIMIT 1;
        """,
        (id_conversa, id_cliente, id_unidade),
    )

    resultado = cursor.fetchone()

    if not resultado:
        raise ValueError(
            "Contexto do atendimento não encontrado "
            f"(id_conversa={id_conversa}, id_cliente={id_cliente}, "
            f"id_unidade={id_unidade})"
        )

    (
        nome_cliente,
        email_cliente,
        nome_unidade,
        numero_comercial,
        link_agendamento,
        link_instagram,
        bpa_ativo,
        id_dependente,
        nome_dependente,
        idade_dependente,
        idade_cliente,
        possui_conversa_anterior,
    ) = resultado

    if not nome_unidade:
        raise ValueError(
            "Unidade sem nome para atendimento "
            f"(id_unidade={id_unidade})"
        )

    cliente_veterano = bool(
        possui_conversa_anterior and nome_cliente
    )

    logger.debug(
        "contexto_atendimento_consultado | id_conversa=%s "
        "id_cliente=%s id_unidade=%s veterano=%s "
        "status_dependente=%s",
        id_conversa,
        id_cliente,
        id_unidade,
        cliente_veterano,
        bool(id_dependente),
    )

    return {
        "nome_cliente": nome_cliente,
        "email_cliente": email_cliente,
        "nome_unidade": nome_unidade,
        "numero_comercial_unidade": numero_comercial,
        "link_agendamento_unidade": link_agendamento,
        "link_instagram_unidade": link_instagram,
        "bpa_ativo_unidade": bool(bpa_ativo),
        "id_dependente": id_dependente,
        "nome_dependente": nome_dependente,
        "idade_dependente": idade_dependente,
        "idade_cliente": idade_cliente,
        "cliente_veterano": cliente_veterano,
    }
```

### Passo 5 - Recuperar o valor candidato pelo histórico

Arquivo: `core/repositories/contexto_confirmacoes.py`

```python
import logging


logger = logging.getLogger("db.contexto_confirmacoes")


def buscar_candidato_confirmacao(
    id_conversa,
    etapas_coleta,
    cursor,
):
    """Retorna a última resposta do cliente em uma etapa de coleta."""
    etapas = sorted({int(etapa) for etapa in etapas_coleta})

    if not etapas:
        raise ValueError("Confirmação sem etapas de coleta configuradas")

    cursor.execute(
        """
        SELECT
            id_etapa,
            conteudo_texto,
            id_mensagem,
            received_data_hora
        FROM chatbot.historico_mensagens
        WHERE id_conversa = %s
          AND quem_enviou = 'cliente'
          AND id_etapa = ANY(%s)
        ORDER BY received_data_hora DESC, id_mensagem DESC
        LIMIT 1;
        """,
        (id_conversa, etapas),
    )

    resultado = cursor.fetchone()

    if not resultado:
        raise ValueError(
            "Candidato de confirmação não encontrado "
            f"(id_conversa={id_conversa}, etapas={etapas})"
        )

    logger.debug(
        "candidato_confirmacao_consultado | id_conversa=%s "
        "etapa_coleta=%s id_mensagem=%s",
        id_conversa,
        resultado[0],
        resultado[2],
    )

    return {
        "id_etapa_coleta_candidato": resultado[0],
        "texto_candidato": resultado[1],
        "id_mensagem_candidato": resultado[2],
        "data_candidato": resultado[3],
    }
```

### Passo 6 - Montar o contexto completo antes do resolver

Arquivo: `workers/worker_flow/valida_historico.py`

```python
import logging

from core.logging_config import short_value
from core.repositories.contexto_atendimento import buscar_contexto_atendimento
from core.repositories.contexto_confirmacoes import (
    buscar_candidato_confirmacao,
)
from core.repositories.inserts import inserir_historico_mensagem_cliente
from core.repositories.querys import buscar_resposta_bot_por_mensagem_cliente
from core.repositories.transicoes_etapa import listar_transicoes_permitidas
from core.repositories.updates import (
    atualizar_conversa_mensagem_cliente,
    atualizar_conversa_resposta_bot_sem_avancar,
)
from workers.worker_flow.response_flow.etapas.validadores_contexto.valida_etapa14 import (
    validar_etapa14,
)
from workers.worker_flow.response_flow.etapas.validadores_contexto.valida_etapa9 import (
    validar_etapa9,
)
from workers.worker_flow.response_flow.etapas.validadores_universais.validador_nome import (
    validar_nome_cliente,
)
from workers.worker_flow.response_flow.transicoes.contexto_transicao import (
    montar_contexto_transicao,
    prever_etapa_resposta,
)
from workers.worker_flow.response_flow.transicoes.eventos import (
    ETAPA_1_RETORNO_VETERANO,
    ETAPA_2_NOVO_NOME_VETERANO,
    ETAPA_3_CONFIRMACAO_NOME_CLIENTE,
    ETAPA_5_NOME_CLIENTE_NOVATO,
    ETAPA_7_NOME_DEPENDENTE,
    ETAPA_8_CONFIRMACAO_NOME_DEPENDENTE,
    ETAPA_9_IDADE_ALUNO,
    ETAPA_10_CONFIRMACAO_IDADE,
    ETAPA_14_EMAIL,
    ETAPA_15_CONFIRMACAO_EMAIL,
)


logger = logging.getLogger("worker.valida_historico")


def valida_historico(mensagem, contexto_banco, cursor):
    contexto_conversa = contexto_banco["conversa"]
    id_conversa = contexto_conversa["id_conversa"]
    contexto_atendimento = buscar_contexto_atendimento(
        id_conversa,
        contexto_banco["id_cliente"],
        contexto_banco["id_unidade"],
        cursor,
    )

    last_message_from_entrada = contexto_conversa.get("last_message_from")
    id_etapa_para_insert = _resolver_etapa_cliente(
        contexto_conversa,
        contexto_atendimento,
    )

    (
        id_historico_cliente,
        data_historico_cliente,
        id_etapa_cliente,
        cliente_inserido_no_historico,
    ) = inserir_historico_mensagem_cliente(
        mensagem=mensagem,
        id_conversa=id_conversa,
        id_etapa=id_etapa_para_insert,
        cursor=cursor,
    )

    mensagem_cliente_atual = {
        "id_mensagem": id_historico_cliente,
        "id_conversa": id_conversa,
        "id_etapa": id_etapa_cliente,
        "received_data_hora": data_historico_cliente,
        "cliente_telefone": mensagem["cliente_telefone"],
        "conteudo_texto": mensagem["conteudo_texto"],
        "tipo_mensagem": mensagem["tipo_mensagem"],
        "id_hash_msg": mensagem["id_hash"],
        "id_mensagem_fila": mensagem["id_mensagem"],
        "id_hash_cliente_origem": None,
        "id_phone_unidade": mensagem["id_phone_unidade"],
        "unidade_telefone": mensagem["unidade_telefone"],
        "quem_enviou": "cliente",
        "status_envio": None,
    }

    resposta_bot = _normalizar_resposta_bot(
        buscar_resposta_bot_por_mensagem_cliente(
            id_conversa=id_conversa,
            id_mensagem_fila=mensagem["id_mensagem"],
            id_hash_cliente_origem=mensagem["id_hash"],
            cursor=cursor,
        )
    )
    transicoes_permitidas = listar_transicoes_permitidas(
        id_etapa_cliente,
        cursor,
    )
    contexto_transicao = montar_contexto_transicao(
        id_etapa_cliente,
        transicoes_permitidas,
    )

    contexto_confirmacao = _carregar_contexto_confirmacao(
        id_conversa,
        id_etapa_cliente,
        cursor,
    )

    if resposta_bot:
        id_etapa_resposta = resposta_bot["id_etapa"]

        if last_message_from_entrada != "bot":
            atualizar_conversa_resposta_bot_sem_avancar(
                id_conversa,
                resposta_bot["received_data_hora"],
                cursor,
            )

        last_message_from_saida = "bot"
    else:
        id_etapa_resposta = prever_etapa_resposta(
            contexto_conversa.get("id_etapa_atual"),
            contexto_transicao["transicoes_permitidas"],
            etapa_inicial=id_etapa_para_insert,
        )
        atualizar_conversa_mensagem_cliente(
            id_conversa,
            data_historico_cliente,
            cursor,
        )
        last_message_from_saida = "cliente"

    logger.info(
        "historico_validado | acao=registrar_cliente id_mensagem=%s "
        "id_historico=%s inserido=%s id_conversa=%s etapa_cliente=%s "
        "etapa_resposta_previa=%s eventos_transicao=%s "
        "veterano=%s retry=%s resposta_bot_existente=%s cliente=%s "
        "phone_number_id=%s",
        mensagem["id_mensagem"],
        id_historico_cliente,
        cliente_inserido_no_historico,
        id_conversa,
        id_etapa_cliente,
        id_etapa_resposta,
        sorted(transicoes_permitidas),
        contexto_atendimento["cliente_veterano"],
        mensagem["retry_count"],
        bool(resposta_bot),
        short_value(mensagem["cliente_telefone"]),
        short_value(mensagem["id_phone_unidade"]),
    )

    contexto_historico = {
        "id_conversa": id_conversa,
        "id_cliente": contexto_banco["id_cliente"],
        "id_unidade": contexto_banco["id_unidade"],
        "id_etapa_atual": contexto_conversa.get("id_etapa_atual"),
        "id_etapa_cliente": id_etapa_cliente,
        "id_etapa_resposta": id_etapa_resposta,
        "id_etapa_origem_transicao": contexto_transicao[
            "id_etapa_origem_transicao"
        ],
        "transicoes_permitidas": contexto_transicao[
            "transicoes_permitidas"
        ],
        "status_dependente": bool(
            contexto_conversa.get("status_dependente")
        ),
        "last_message_from": last_message_from_saida,
        "last_message_from_entrada": last_message_from_entrada,
        "mensagem_cliente_atual": mensagem_cliente_atual,
        "mensagem_cliente_inserida": cliente_inserido_no_historico,
        "resposta_bot_para_mensagem_atual": resposta_bot,
        "texto_cliente_atual": mensagem["conteudo_texto"],
        "tipo_mensagem_atual": mensagem["tipo_mensagem"],
        "retry_count": mensagem["retry_count"],
        "precisa_tratamento_erro": False,
        "motivo_tratamento_erro": None,
    }
    contexto_historico.update(contexto_atendimento)
    contexto_historico.update(contexto_confirmacao)
    return contexto_historico


def _resolver_etapa_cliente(contexto_conversa, contexto_atendimento):
    id_etapa_atual = contexto_conversa.get("id_etapa_atual")

    if id_etapa_atual is not None:
        return id_etapa_atual

    if contexto_atendimento["cliente_veterano"]:
        return ETAPA_1_RETORNO_VETERANO

    return ETAPA_5_NOME_CLIENTE_NOVATO


def _carregar_contexto_confirmacao(id_conversa, id_etapa, cursor):
    if id_etapa == ETAPA_3_CONFIRMACAO_NOME_CLIENTE:
        candidato = buscar_candidato_confirmacao(
            id_conversa,
            {ETAPA_2_NOVO_NOME_VETERANO, ETAPA_5_NOME_CLIENTE_NOVATO},
            cursor,
        )
        resultado = validar_nome_cliente(candidato["texto_candidato"])

        if not resultado.valido:
            raise ValueError("Nome do cliente candidato não foi reconstruído")

        return {
            **candidato,
            "nome_cliente_candidato": resultado.primeiro_nome,
            "candidato_cliente_veterano": (
                candidato["id_etapa_coleta_candidato"]
                == ETAPA_2_NOVO_NOME_VETERANO
            ),
        }

    if id_etapa == ETAPA_8_CONFIRMACAO_NOME_DEPENDENTE:
        candidato = buscar_candidato_confirmacao(
            id_conversa,
            {ETAPA_7_NOME_DEPENDENTE},
            cursor,
        )
        resultado = validar_nome_cliente(candidato["texto_candidato"])

        if not resultado.valido:
            raise ValueError("Nome do dependente candidato não reconstruído")

        return {
            **candidato,
            "nome_dependente_candidato": resultado.primeiro_nome,
        }

    if id_etapa == ETAPA_10_CONFIRMACAO_IDADE:
        candidato = buscar_candidato_confirmacao(
            id_conversa,
            {ETAPA_9_IDADE_ALUNO},
            cursor,
        )
        resultado = validar_etapa9(candidato["texto_candidato"])

        if not resultado.valida:
            raise ValueError("Idade permitida não foi reconstruída")

        return {
            **candidato,
            "idade_aluno_candidata": resultado.idade,
        }

    if id_etapa == ETAPA_15_CONFIRMACAO_EMAIL:
        candidato = buscar_candidato_confirmacao(
            id_conversa,
            {ETAPA_14_EMAIL},
            cursor,
        )
        resultado = validar_etapa14(candidato["texto_candidato"])

        if not resultado.valido:
            raise ValueError("Email candidato não foi reconstruído")

        return {
            **candidato,
            "email_cliente_candidato": resultado.email,
        }

    return {}


def _normalizar_linha_historico(registro):
    chaves = (
        "id_mensagem",
        "id_conversa",
        "id_etapa",
        "received_data_hora",
        "cliente_telefone",
        "conteudo_texto",
        "tipo_mensagem",
        "id_hash_msg",
        "id_mensagem_fila",
        "id_hash_cliente_origem",
        "id_phone_unidade",
        "unidade_telefone",
        "quem_enviou",
        "status_envio",
    )
    return dict(zip(chaves, registro, strict=True))


def _normalizar_resposta_bot(registro):
    if not registro:
        return None

    return _normalizar_linha_historico(registro)
```

### Passo 7 - Permitir as duas etapas iniciais no repositório atual

Arquivo: `core/repositories/updates.py`

```python
import logging

from core.logging_config import short_value


logger = logging.getLogger("db.updates")

ETAPAS_INICIAIS = {1, 5}


def marcar_mensagem_como_enviada(id_mensagem, cursor):
    cursor.execute("""
        UPDATE chatbot.fila_mensagens
        SET status = 'sent',
            processing_started_at = NULL,
            last_error = NULL
        WHERE id_mensagem = %s
    """, (id_mensagem,))
    logger.debug(
        "fila_update | acao=marcar_sent id_mensagem=%s linhas=%s",
        id_mensagem,
        cursor.rowcount,
    )


def vincular_mensagem_fila_a_conversa(id_mensagem, id_conversa, cursor):
    cursor.execute("""
        UPDATE chatbot.fila_mensagens
        SET id_conversa = %s
        WHERE id_mensagem = %s
          AND (
              id_conversa IS NULL
              OR id_conversa = %s
          );
    """, (id_conversa, id_mensagem, id_conversa))
    logger.debug(
        "fila_update | acao=vincular_conversa id_mensagem=%s id_conversa=%s linhas=%s",
        id_mensagem,
        id_conversa,
        cursor.rowcount,
    )
    return cursor.rowcount


def atualizar_conversa_mensagem_cliente(
    id_conversa,
    data_interacao,
    cursor,
):
    if data_interacao is None:
        raise ValueError(
            "data_interacao nao informada para registrar mensagem do cliente"
        )

    cursor.execute("""
        UPDATE chatbot.conversa
        SET
            last_message_from = 'cliente',
            last_interaction_at = %s
        WHERE id_conversa = %s;
    """, (data_interacao, id_conversa))

    logger.debug(
        "conversa_update | acao=registrar_mensagem_cliente id_conversa=%s data_interacao=%s linhas=%s",
        id_conversa,
        data_interacao,
        cursor.rowcount,
    )

    if cursor.rowcount != 1:
        raise ValueError(
            "Conversa nao foi atualizada com mensagem do cliente "
            f"(id_conversa={id_conversa}, linhas={cursor.rowcount})"
        )

    return cursor.rowcount


def inicializar_conversa_resposta_bot(
    id_conversa,
    id_etapa_resultante,
    data_interacao,
    cursor,
):
    if id_etapa_resultante not in ETAPAS_INICIAIS:
        raise ValueError(
            "Inicializacao recebeu etapa invalida "
            f"(etapa={id_etapa_resultante})"
        )

    _validar_data_interacao_bot(data_interacao)

    cursor.execute("""
        UPDATE chatbot.conversa
        SET
            id_etapa_atual = %s,
            last_message_from = 'bot',
            last_interaction_at = %s
        WHERE id_conversa = %s
          AND id_etapa_atual IS NULL;
    """, (
        id_etapa_resultante,
        data_interacao,
        id_conversa,
    ))

    logger.debug(
        "conversa_update | acao=inicializar_etapa id_conversa=%s etapa=%s linhas=%s",
        id_conversa,
        id_etapa_resultante,
        cursor.rowcount,
    )

    if cursor.rowcount != 1:
        raise ValueError(
            "Conversa nao foi inicializada "
            f"(id_conversa={id_conversa}, "
            f"etapa={id_etapa_resultante}, linhas={cursor.rowcount})"
        )

    return cursor.rowcount


def atualizar_conversa_por_transicao(
    id_conversa,
    id_etapa_origem,
    evento_transicao,
    id_etapa_destino,
    data_interacao,
    cursor,
    *,
    permitir_reaplicacao=False,
):
    if id_etapa_origem is None:
        raise ValueError("Etapa de origem nao informada para transicao")

    if not evento_transicao:
        raise ValueError("Evento nao informado para transicao")

    if id_etapa_destino is None:
        raise ValueError("Etapa de destino nao informada para transicao")

    _validar_data_interacao_bot(data_interacao)

    cursor.execute(
        """
        UPDATE chatbot.conversa AS conversa
        SET
            id_etapa_atual = CASE
                WHEN conversa.id_etapa_atual = %s THEN %s
                ELSE conversa.id_etapa_atual
            END,
            last_message_from = 'bot',
            last_interaction_at = %s
        WHERE conversa.id_conversa = %s
          AND EXISTS (
              SELECT 1
              FROM chatbot.etapa_transicao AS transicao
              WHERE transicao.id_etapa_origem = %s
                AND transicao.evento = %s
                AND transicao.id_etapa_destino = %s
          )
          AND (
              conversa.id_etapa_atual = %s
              OR (
                  %s = TRUE
                  AND conversa.id_etapa_atual = %s
              )
          );
        """,
        (
            id_etapa_origem,
            id_etapa_destino,
            data_interacao,
            id_conversa,
            id_etapa_origem,
            evento_transicao,
            id_etapa_destino,
            id_etapa_origem,
            bool(permitir_reaplicacao),
            id_etapa_destino,
        ),
    )

    logger.debug(
        "conversa_update | acao=aplicar_transicao id_conversa=%s etapa_origem=%s evento=%s etapa_destino=%s reaplicacao=%s linhas=%s",
        id_conversa,
        id_etapa_origem,
        evento_transicao,
        id_etapa_destino,
        bool(permitir_reaplicacao),
        cursor.rowcount,
    )

    if cursor.rowcount != 1:
        raise ValueError(
            "Conversa nao foi atualizada; transicao inexistente, origem "
            "incompativel ou conversa ausente "
            f"(id_conversa={id_conversa}, origem={id_etapa_origem}, "
            f"evento={evento_transicao}, destino={id_etapa_destino}, "
            f"reaplicacao={bool(permitir_reaplicacao)}, "
            f"linhas={cursor.rowcount})"
        )

    return cursor.rowcount


def atualizar_conversa_resposta_bot_sem_avancar(
    id_conversa,
    data_interacao,
    cursor,
):
    _validar_data_interacao_bot(data_interacao)

    cursor.execute("""
        UPDATE chatbot.conversa
        SET
            last_message_from = 'bot',
            last_interaction_at = %s
        WHERE id_conversa = %s;
    """, (data_interacao, id_conversa))

    logger.debug(
        "conversa_update | acao=registrar_resposta_bot_sem_avancar id_conversa=%s data_interacao=%s linhas=%s",
        id_conversa,
        data_interacao,
        cursor.rowcount,
    )

    if cursor.rowcount != 1:
        raise ValueError(
            "Conversa nao foi atualizada com resposta do bot sem avancar etapa "
            f"(id_conversa={id_conversa}, linhas={cursor.rowcount})"
        )

    return cursor.rowcount


def _validar_data_interacao_bot(data_interacao):
    if data_interacao is None:
        raise ValueError(
            "data_interacao nao informada para registrar resposta do bot"
        )


def atualizar_nome_cliente_por_telefone(waid_telefone, nome, cursor):
    if not waid_telefone:
        raise ValueError("waid_telefone nao informado para atualizar nome do cliente")

    if not nome:
        raise ValueError("nome nao informado para atualizar cliente")

    cursor.execute("""
        UPDATE chatbot.cliente
        SET nome = %s
        WHERE waid_telefone = %s;
    """, (nome, waid_telefone))

    logger.debug(
        "cliente_update | acao=atualizar_nome telefone=%s linhas=%s",
        short_value(waid_telefone),
        cursor.rowcount,
    )

    if cursor.rowcount != 1:
        raise ValueError(
            "Cliente nao foi atualizado com nome "
            f"(telefone={short_value(waid_telefone)}, linhas={cursor.rowcount})"
        )

    return cursor.rowcount


def atualizar_nome_dependente_por_conversa(id_conversa, nome, cursor):
    if not id_conversa:
        raise ValueError(
            "id_conversa nao informado para atualizar nome do dependente"
        )

    if not nome:
        raise ValueError("nome nao informado para atualizar dependente")

    cursor.execute(
        """
        UPDATE chatbot.dependente
        SET nome_dependente = %s
        WHERE id_conversa = %s;
        """,
        (nome, id_conversa),
    )

    logger.debug(
        "dependente_update | acao=atualizar_nome id_conversa=%s linhas=%s",
        id_conversa,
        cursor.rowcount,
    )

    if cursor.rowcount != 1:
        raise ValueError(
            "Dependente nao foi atualizado com nome "
            f"(id_conversa={id_conversa}, linhas={cursor.rowcount})"
        )

    return cursor.rowcount


def atualizar_status_dependente_conversa(
    id_conversa,
    status_dependente,
    cursor,
):
    cursor.execute("""
        UPDATE chatbot.conversa
        SET status_dependente = %s
        WHERE id_conversa = %s;
    """, (bool(status_dependente), id_conversa))

    logger.debug(
        "conversa_update | acao=atualizar_status_dependente id_conversa=%s status_dependente=%s linhas=%s",
        id_conversa,
        bool(status_dependente),
        cursor.rowcount,
    )

    if cursor.rowcount != 1:
        raise ValueError(
            "Conversa nao foi atualizada com status_dependente "
            f"(id_conversa={id_conversa}, linhas={cursor.rowcount})"
        )

    return cursor.rowcount


def reagendar_mensagem_sem_erro(id_mensagem, cursor, delay_seconds=30):
    cursor.execute("""
        UPDATE chatbot.fila_mensagens
        SET
            status = 'pending',
            next_attempt_at = NOW() + (%s * INTERVAL '1 second'),
            processing_started_at = NULL,
            retry_count = GREATEST(COALESCE(retry_count, 0) - 1, 0),
            last_error = NULL
        WHERE id_mensagem = %s;
    """, (delay_seconds, id_mensagem))
    logger.debug(
        "fila_update | acao=reagendar_sem_erro id_mensagem=%s delay=%s linhas=%s",
        id_mensagem,
        delay_seconds,
        cursor.rowcount,
    )
    return cursor.rowcount


def reagendar_mensagem(id_mensagem, erro, max_retry, cursor):
    cursor.execute("""
        UPDATE chatbot.fila_mensagens
        SET
            status = 'pending',
            next_attempt_at = NOW() + INTERVAL '2 minutes',
            processing_started_at = NULL,
            last_error = %s
        WHERE id_mensagem = %s AND retry_count < %s;
    """, (str(erro), id_mensagem, max_retry))
    logger.debug(
        "fila_update | acao=reagendar_com_erro id_mensagem=%s max_retry=%s linhas=%s",
        id_mensagem,
        max_retry,
        cursor.rowcount,
    )
    return cursor.rowcount
```

A única mudança transacional deste arquivo é ampliar a validação da
inicialização de `{1}` para `{1, 5}`. O SQL de transição, a reaplicação
idempotente e todos os commits continuam intactos.

### Passo 8 - Permitir inicialização nas etapas 1 ou 5

Arquivo: `workers/worker_flow/transacoes/movimento_conversa.py`

```python
from core.repositories.updates import (
    atualizar_conversa_por_transicao,
    atualizar_conversa_resposta_bot_sem_avancar,
    inicializar_conversa_resposta_bot,
)
from workers.worker_flow.response_flow.transicoes.eventos import (
    ETAPA_1_RETORNO_VETERANO,
    ETAPA_5_NOME_CLIENTE_NOVATO,
)


MOVIMENTO_INICIALIZACAO = "inicializacao"
MOVIMENTO_TRANSICAO = "transicao"
MOVIMENTO_SEM_AVANCO = "sem_avanco"

ETAPAS_INICIAIS = {
    ETAPA_1_RETORNO_VETERANO,
    ETAPA_5_NOME_CLIENTE_NOVATO,
}


def persistir_movimento_conversa(
    contexto_historico,
    contexto_envio,
    data_interacao_bot,
    cursor,
):
    movimento = resolver_movimento_conversa(
        contexto_historico,
        contexto_envio,
    )
    id_conversa = contexto_historico["id_conversa"]
    id_etapa_destino = contexto_envio.get("id_etapa_resultante")
    if movimento == MOVIMENTO_INICIALIZACAO:
        inicializar_conversa_resposta_bot(
            id_conversa,
            id_etapa_destino,
            data_interacao_bot,
            cursor,
        )
        return movimento

    if movimento == MOVIMENTO_TRANSICAO:
        atualizar_conversa_por_transicao(
            id_conversa,
            contexto_historico["id_etapa_origem_transicao"],
            contexto_envio["evento_transicao"],
            id_etapa_destino,
            data_interacao_bot,
            cursor,
            permitir_reaplicacao=bool(
                contexto_envio.get("resposta_ja_existia")
            ),
        )
        return movimento

    atualizar_conversa_resposta_bot_sem_avancar(
        id_conversa,
        data_interacao_bot,
        cursor,
    )
    return movimento


def resolver_movimento_conversa(contexto_historico, contexto_envio):
    etapa_atual = contexto_historico.get("id_etapa_atual")
    etapa_origem = contexto_historico.get("id_etapa_origem_transicao")
    etapa_destino = contexto_envio.get("id_etapa_resultante")
    evento_transicao = contexto_envio.get("evento_transicao")
    tratamento = bool(contexto_envio.get("tratamento"))

    if etapa_destino is None:
        raise ValueError("Resposta do bot sem id_etapa_resultante")

    if etapa_atual is None:
        etapa_inicial = contexto_historico.get("id_etapa_cliente")

        if etapa_inicial not in ETAPAS_INICIAIS:
            raise ValueError(
                "Conversa sem etapa recebeu origem inicial inválida "
                f"(origem={etapa_inicial})"
            )

        if etapa_destino != etapa_inicial:
            raise ValueError(
                "Inicialização tentou usar etapa diferente da origem "
                f"(origem={etapa_inicial}, destino={etapa_destino})"
            )

        if evento_transicao:
            raise ValueError(
                "Inicialização da conversa não aceita evento de transição"
            )

        return MOVIMENTO_INICIALIZACAO

    if evento_transicao:
        if tratamento:
            raise ValueError(
                "Tratamento não pode avançar por evento de transição"
            )

        if etapa_origem is None:
            raise ValueError(
                "Evento de transição sem etapa de origem persistida"
            )

        return MOVIMENTO_TRANSICAO

    if etapa_destino != etapa_origem:
        raise ValueError(
            "Resposta sem evento tentou alterar a etapa da conversa "
            f"(origem={etapa_origem}, destino={etapa_destino})"
        )

    return MOVIMENTO_SEM_AVANCO
```

Este passo mantém a mesma sequência de chamadas e o mesmo contrato
transacional do `movimento_conversa.py` atual. A única adaptação é escolher,
para uma conversa ainda sem etapa, entre as etapas iniciais 1 e 5 já
classificadas no contexto histórico. Não existe movimento automático novo.

## Fase 3 - Componentes compartilhados e validadores

### Passo 9 - Centralizar o contrato de envio das etapas

Arquivo: `core/integrations/whatsapp/pywa_functions/pywa_senders/sender_base.py`

```python
import logging

from pywa.types import Button, URLButton

from core.integrations.whatsapp.exceptions import ErroEnvioMeta
from core.integrations.whatsapp.pywa_functions.cliente import conta_wa
from core.integrations.whatsapp.pywa_functions.resposta_envio import (
    extrair_id_hash_msg_bot,
)
from core.logging_config import short_value


logger = logging.getLogger("whatsapp.sender_base")


def enviar_mensagem_etapa(
    cliente_telefone,
    phone_id_unidade,
    mensagem_bot,
    *,
    id_etapa,
    evento_log,
    botoes=None,
    cabecalho=None,
    botao_url=None,
    tipo_tratamento=None,
):
    """Executa somente o contrato técnico comum dos senders."""
    try:
        parametros = {
            "to": cliente_telefone,
            "text": mensagem_bot,
        }

        if botoes:
            parametros["buttons"] = [
                Button(title=titulo, callback_data=titulo)
                for titulo in botoes
            ]
        elif botao_url:
            parametros["buttons"] = URLButton(
                title=botao_url["titulo"],
                url=botao_url["url"],
            )

        if cabecalho:
            parametros["header"] = cabecalho

        sent_message = conta_wa(phone_id_unidade).send_message(**parametros)
        id_hash_msg_bot = extrair_id_hash_msg_bot(sent_message)

        logger.info(
            "%s_ok | acao=enviar_meta etapa=%s cliente=%s "
            "phone_number_id=%s id_hash_msg_bot=%s tratamento=%s",
            evento_log,
            id_etapa,
            short_value(cliente_telefone),
            short_value(phone_id_unidade),
            id_hash_msg_bot,
            tipo_tratamento,
        )

        contexto = {
            "enviou": True,
            "resposta_ja_existia": False,
            "mensagem_bot": mensagem_bot,
            "id_hash_msg_bot": id_hash_msg_bot,
            "id_etapa_resultante": id_etapa,
            "tipo_mensagem": _resolver_tipo_mensagem(
                botoes,
                botao_url,
            ),
            "canal": "meta_whatsapp",
            "atualizar_conversa": True,
            "atualizar_last_from_bot": True,
        }

        if cabecalho:
            contexto["cabecalho_mensagem"] = cabecalho

        if tipo_tratamento:
            contexto["tratamento"] = True
            contexto["tipo_tratamento"] = tipo_tratamento

        return contexto

    except Exception as erro:
        logger.exception(
            "%s_erro | motivo=meta_falhou acao=levantar_erro etapa=%s "
            "cliente=%s phone_number_id=%s erro=%s",
            evento_log,
            id_etapa,
            short_value(cliente_telefone),
            short_value(phone_id_unidade),
            erro,
        )
        raise ErroEnvioMeta(
            f"Meta falhou ao enviar mensagem da etapa {id_etapa}",
            id_etapa=id_etapa,
            phone_id_unidade=phone_id_unidade,
            cliente_telefone=cliente_telefone,
        ) from erro


def _resolver_tipo_mensagem(botoes, botao_url):
    if botoes:
        return "interactive_button"

    if botao_url:
        return "interactive_cta_url"

    return "text"
```

### Passo 10 - Criar componentes das confirmações

Arquivo: `core/integrations/whatsapp/messages/confirmacao_componentes.py`

```python
from core.integrations.whatsapp.messages.componentes_compartilhados import (
    RODAPE_OPCAO_UNICA,
    montar_texto_com_rodape,
)


BOTAO_CONFIRMACAO_SIM = "Sim"
BOTAO_CONFIRMACAO_NAO = "Não"

BOTOES_CONFIRMACAO = (
    BOTAO_CONFIRMACAO_SIM,
    BOTAO_CONFIRMACAO_NAO,
)


def montar_botoes_confirmacao():
    return BOTOES_CONFIRMACAO


def montar_mensagem_confirmacao(pergunta, prefixo=None):
    partes = []

    if prefixo:
        partes.append(prefixo.strip())

    partes.append(pergunta.strip())
    return montar_texto_com_rodape(
        "\n\n".join(partes),
        RODAPE_OPCAO_UNICA,
    )
```

### Passo 11 - Normalizar respostas Sim/Não

Arquivo: `workers/worker_flow/response_flow/etapas/validadores_contexto/confirmacao.py`

```python
import unicodedata


CONFIRMACAO_SIM = True
CONFIRMACAO_NAO = False


def normalizar_confirmacao(conteudo_texto):
    """Aceita exclusivamente Sim ou Não, digitado ou vindo do botão."""
    if not isinstance(conteudo_texto, str):
        return None

    texto = unicodedata.normalize(
        "NFKD",
        conteudo_texto.strip().casefold(),
    )
    texto = "".join(
        caractere
        for caractere in texto
        if not unicodedata.combining(caractere)
    )
    texto = " ".join(texto.split())

    if texto == "sim":
        return CONFIRMACAO_SIM

    if texto == "nao":
        return CONFIRMACAO_NAO

    return None
```

### Passo 12 - Validar a decisão de retorno da etapa 1

Arquivo: `workers/worker_flow/response_flow/etapas/validadores_contexto/valida_etapa1.py`

```python
from workers.worker_flow.response_flow.transicoes.eventos import (
    EVENTO_ATUALIZAR_NOME,
    EVENTO_NOVO_ATENDIMENTO,
)


TIPO_TRATAMENTO_CONTEXTO_INVALIDO = "opcao_invalida"

_OPCOES = {
    "mudar nome": EVENTO_ATUALIZAR_NOME,
    "novo atendimento": EVENTO_NOVO_ATENDIMENTO,
}


def validar_etapa1(conteudo_texto):
    if not isinstance(conteudo_texto, str):
        return None

    texto = " ".join(conteudo_texto.strip().casefold().split())
    return _OPCOES.get(texto)
```

### Passo 13 - Validar a confirmação do nome do cliente

Arquivo: `workers/worker_flow/response_flow/etapas/validadores_contexto/valida_etapa3.py`

```python
from workers.worker_flow.response_flow.etapas.validadores_contexto.confirmacao import (
    normalizar_confirmacao,
)
from workers.worker_flow.response_flow.transicoes.eventos import (
    EVENTO_NOME_CLIENTE_CONFIRMADO_NOVATO,
    EVENTO_NOME_CLIENTE_CONFIRMADO_VETERANO,
    EVENTO_NOME_CLIENTE_REJEITADO_NOVATO,
    EVENTO_NOME_CLIENTE_REJEITADO_VETERANO,
)


TIPO_TRATAMENTO_CONFIRMACAO_INVALIDA = "confirmacao_nome_invalida"


def validar_etapa3(conteudo_texto, candidato_cliente_veterano):
    confirmacao = normalizar_confirmacao(conteudo_texto)

    if confirmacao is None:
        return None

    if candidato_cliente_veterano:
        if confirmacao:
            return EVENTO_NOME_CLIENTE_CONFIRMADO_VETERANO
        return EVENTO_NOME_CLIENTE_REJEITADO_VETERANO

    if confirmacao:
        return EVENTO_NOME_CLIENTE_CONFIRMADO_NOVATO
    return EVENTO_NOME_CLIENTE_REJEITADO_NOVATO
```

### Passo 14 - Compartilhar a validação do destino do atendimento

Arquivo: `workers/worker_flow/response_flow/etapas/validadores_universais/validador_destino_atendimento.py`

```python
from workers.worker_flow.response_flow.transicoes.eventos import (
    EVENTO_PARA_MIM,
    EVENTO_PARA_OUTRA_PESSOA,
)


TIPO_TRATAMENTO_CONTEXTO_INVALIDO = "opcao_invalida"

_OPCOES = {
    "para mim": EVENTO_PARA_MIM,
    "para outra pessoa": EVENTO_PARA_OUTRA_PESSOA,
}


def validar_destino_atendimento(conteudo_texto):
    if not isinstance(conteudo_texto, str):
        return None

    texto = " ".join(conteudo_texto.strip().casefold().split())
    return _OPCOES.get(texto)
```

### Passo 15 - Validar a confirmação do nome do dependente

Arquivo: `workers/worker_flow/response_flow/etapas/validadores_contexto/valida_etapa8.py`

```python
from workers.worker_flow.response_flow.etapas.validadores_contexto.confirmacao import (
    normalizar_confirmacao,
)
from workers.worker_flow.response_flow.transicoes.eventos import (
    EVENTO_NOME_DEPENDENTE_CONFIRMADO,
    EVENTO_NOME_DEPENDENTE_REJEITADO,
)


TIPO_TRATAMENTO_CONFIRMACAO_INVALIDA = "confirmacao_nome_invalida"


def validar_etapa8(conteudo_texto):
    confirmacao = normalizar_confirmacao(conteudo_texto)

    if confirmacao is None:
        return None

    if confirmacao:
        return EVENTO_NOME_DEPENDENTE_CONFIRMADO

    return EVENTO_NOME_DEPENDENTE_REJEITADO
```

### Passo 16 - Adaptar o validador de idade à etapa 9

Arquivo: `workers/worker_flow/response_flow/etapas/validadores_contexto/valida_etapa9.py`

```python
import re
import unicodedata
from dataclasses import dataclass


STATUS_IDADE_VALIDA = "idade_valida"
STATUS_IDADE_INVALIDA = "idade_invalida"
STATUS_IDADE_ACIMA_LIMITE = "idade_acima_limite"

MOTIVO_SEM_IDADE = "sem_idade"
MOTIVO_MULTIPLAS_IDADES = "multiplas_idades"
MOTIVO_FORA_INTERVALO = "fora_intervalo"
MOTIVO_FORMATO_INVALIDO = "formato_invalido"

IDADE_MINIMA_DEPENDENTE_PADRAO = 5
IDADE_MINIMA_DEPENDENTE_BPA = 4

UNIDADES = {
    "um": 1, "uma": 1, "dois": 2, "duas": 2, "tres": 3,
    "quatro": 4, "cinco": 5, "seis": 6, "sete": 7,
    "oito": 8, "nove": 9,
}
ATE_DEZENOVE = {
    **UNIDADES,
    "dez": 10, "onze": 11, "doze": 12, "treze": 13,
    "quatorze": 14, "catorze": 14, "quinze": 15,
    "dezesseis": 16, "dezasseis": 16, "dezessete": 17,
    "dezassete": 17, "dezoito": 18, "dezenove": 19,
}
DEZENAS = {
    "vinte": 20, "trinta": 30, "quarenta": 40,
    "cinquenta": 50, "sessenta": 60, "setenta": 70,
    "oitenta": 80, "noventa": 90,
}
CENTENAS = {
    "cem": 100, "cento": 100, "duzentos": 200, "duzentas": 200,
    "trezentos": 300, "trezentas": 300, "quatrocentos": 400,
    "quatrocentas": 400, "quinhentos": 500, "quinhentas": 500,
    "seiscentos": 600, "seiscentas": 600, "setecentos": 700,
    "setecentas": 700, "oitocentos": 800, "oitocentas": 800,
    "novecentos": 900, "novecentas": 900, "mil": 1000,
}

PADRAO_NUMERO = re.compile(r"\d+")
PADRAO_TOKEN = re.compile(r"[a-z]+", re.IGNORECASE)


@dataclass(frozen=True)
class ResultadoValidacaoIdade:
    status: str
    idade: int | None = None
    motivo: str | None = None

    @property
    def valida(self):
        return self.status == STATUS_IDADE_VALIDA

    @property
    def acima_limite(self):
        return self.status == STATUS_IDADE_ACIMA_LIMITE


def validar_etapa9(texto):
    texto_original = str(texto or "").strip()

    if not texto_original:
        return _resultado_invalido(MOTIVO_SEM_IDADE)

    texto_normalizado = _normalizar_texto(texto_original)

    if _tem_formato_numerico_invalido(texto_normalizado):
        return _resultado_invalido(MOTIVO_FORMATO_INVALIDO)

    candidatos = [
        int(valor)
        for valor in PADRAO_NUMERO.findall(texto_normalizado)
    ]
    candidatos.extend(_extrair_numeros_por_extenso(texto_normalizado))

    if not candidatos:
        return _resultado_invalido(MOTIVO_SEM_IDADE)

    if len(candidatos) != 1:
        return _resultado_invalido(MOTIVO_MULTIPLAS_IDADES)

    idade = candidatos[0]

    if idade <= 0:
        return _resultado_invalido(MOTIVO_FORA_INTERVALO)

    if idade >= 100:
        return ResultadoValidacaoIdade(
            status=STATUS_IDADE_ACIMA_LIMITE,
            idade=idade,
        )

    return ResultadoValidacaoIdade(
        status=STATUS_IDADE_VALIDA,
        idade=idade,
    )


def obter_idade_minima_dependente(bpa_ativo):
    if bpa_ativo:
        return IDADE_MINIMA_DEPENDENTE_BPA
    return IDADE_MINIMA_DEPENDENTE_PADRAO


def _tem_formato_numerico_invalido(texto):
    if re.search(r"(?:^|\s)(?:-|menos(?:\s+de)?)\s*\d", texto):
        return True

    if re.search(
        r"\bmenos(?:\s+de)?\s+(?:um|uma|dois|duas|tres|quatro|"
        r"cinco|seis|sete|oito|nove|dez|onze|doze|treze|quatorze|"
        r"catorze|quinze|dezesseis|dezasseis|dezessete|dezassete|"
        r"dezoito|dezenove|vinte|trinta|quarenta|cinquenta|sessenta|"
        r"setenta|oitenta|noventa|cem|cento)\b",
        texto,
    ):
        return True

    if re.search(r"\d+\s*[,\.]\s*\d+", texto):
        return True

    return bool(re.search(r"\b(?:virgula|ponto|meio|meia)\b", texto))


def _extrair_numeros_por_extenso(texto):
    tokens = PADRAO_TOKEN.findall(texto)
    resultados = []
    indice = 0

    while indice < len(tokens):
        valor, consumidos = _ler_numero_por_extenso(tokens, indice)

        if consumidos:
            resultados.append(valor)
            indice += consumidos
        else:
            indice += 1

    return resultados


def _ler_numero_por_extenso(tokens, indice):
    token = tokens[indice]

    if token in CENTENAS:
        valor = CENTENAS[token]
        consumidos = 1

        if _token_em(tokens, indice + 1) == "e":
            restante, usados = _ler_ate_noventa_e_nove(tokens, indice + 2)
            if usados:
                valor += restante
                consumidos += usados + 1

        return valor, consumidos

    return _ler_ate_noventa_e_nove(tokens, indice)


def _ler_ate_noventa_e_nove(tokens, indice):
    token = _token_em(tokens, indice)

    if token in ATE_DEZENOVE:
        return ATE_DEZENOVE[token], 1

    if token not in DEZENAS:
        return None, 0

    valor = DEZENAS[token]

    if (
        _token_em(tokens, indice + 1) == "e"
        and _token_em(tokens, indice + 2) in UNIDADES
    ):
        return valor + UNIDADES[tokens[indice + 2]], 3

    return valor, 1


def _token_em(tokens, indice):
    if indice < 0 or indice >= len(tokens):
        return None
    return tokens[indice]


def _normalizar_texto(texto):
    texto_decomposto = unicodedata.normalize("NFD", texto.lower())
    return "".join(
        caractere
        for caractere in texto_decomposto
        if unicodedata.category(caractere) != "Mn"
    )


def _resultado_invalido(motivo):
    return ResultadoValidacaoIdade(
        status=STATUS_IDADE_INVALIDA,
        motivo=motivo,
    )
```

### Passo 17 - Validar a confirmação da idade

Arquivo: `workers/worker_flow/response_flow/etapas/validadores_contexto/valida_etapa10.py`

```python
from workers.worker_flow.response_flow.etapas.validadores_contexto.confirmacao import (
    normalizar_confirmacao,
)
from workers.worker_flow.response_flow.transicoes.eventos import (
    EVENTO_IDADE_CONFIRMADA,
    EVENTO_IDADE_REJEITADA,
)


TIPO_TRATAMENTO_CONFIRMACAO_INVALIDA = "confirmacao_idade_invalida"


def validar_etapa10(conteudo_texto):
    confirmacao = normalizar_confirmacao(conteudo_texto)

    if confirmacao is None:
        return None

    if confirmacao:
        return EVENTO_IDADE_CONFIRMADA
    return EVENTO_IDADE_REJEITADA
```

### Passo 18 - Adaptar o validador da oferta à etapa 11

Arquivo: `workers/worker_flow/response_flow/etapas/validadores_contexto/valida_etapa11.py`

```python
import re

from workers.worker_flow.response_flow.etapas.validadores_universais.validador_financeiro import (
    normalizar_texto,
)
from workers.worker_flow.response_flow.transicoes.eventos import (
    EVENTO_OFERTA_ACEITA,
    EVENTO_OFERTA_ADIADA,
)


TIPO_TRATAMENTO_CONTEXTO_INVALIDO = "opcao_invalida"

TEXTO_QUERO_AGENDAR = "quero agendar"
TEXTO_TALVEZ_MAIS_TARDE = "talvez mais tarde"

PADRAO_RESPOSTA_NEGATIVA = re.compile(
    r"(?:\bnao\b|\bnunca\b|\bjamais\b|\bnem\s+pensar\b|"
    r"\bde\s+jeito\s+nenhum\b|\bsem\s+interesse\b|"
    r"\bdispenso\b|\brecuso\b)"
)

PADRAO_RESPOSTA_POSITIVA = re.compile(
    r"(?:\bsim\b|\bsimbora\b|\bbora(?:\s+la)?\b|\bpartiu\b|"
    r"\bclaro\b|\bcom\s+certeza\b|\bfechado\b|\bcombinado\b|"
    r"\bdemorou\b|\bbeleza\b|\bblz\b|\bok(?:ay)?\b|\btopo\b|"
    r"\baceito\b|\bquero\b|\bgostaria\b|\badoraria\b|\bdesejo\b|"
    r"\bpretendo\b|\btenho\s+interesse\b|"
    r"\bestou\s+interessad[oa]\b|\bme\s+interessa\b|"
    r"\bvamos(?:\s+sim|\s+agendar|\s+marcar|\s+nessa|\s+la)?\b|"
    r"\bvamo(?:\s+agendar|\s+marcar|\s+nessa|\s+la)?\b|"
    r"\bpode(?:m)?\s+(?:agendar|marcar|ser|continuar)\b|"
    r"\bagende\b|\bmarque\b|\bmarca\s+pra\s+mim\b)"
)


def validar_etapa11(conteudo_texto):
    if not isinstance(conteudo_texto, str):
        return None

    texto = _normalizar_resposta(conteudo_texto)

    if texto == TEXTO_TALVEZ_MAIS_TARDE:
        return EVENTO_OFERTA_ADIADA

    if not texto or PADRAO_RESPOSTA_NEGATIVA.search(texto):
        return None

    if texto == TEXTO_QUERO_AGENDAR:
        return EVENTO_OFERTA_ACEITA

    if PADRAO_RESPOSTA_POSITIVA.search(texto):
        return EVENTO_OFERTA_ACEITA

    return None


def _normalizar_resposta(texto):
    texto_sem_acento = normalizar_texto(texto)
    texto_sem_pontuacao = re.sub(r"[^a-z0-9\s]", " ", texto_sem_acento)
    return " ".join(texto_sem_pontuacao.split())
```

### Passo 19 - Adaptar o validador do retorno à etapa 13

Arquivo: `workers/worker_flow/response_flow/etapas/validadores_contexto/valida_etapa13.py`

```python
from workers.worker_flow.response_flow.etapas.validadores_contexto.valida_etapa11 import (
    validar_etapa11,
)
from workers.worker_flow.response_flow.transicoes.eventos import (
    EVENTO_OFERTA_ACEITA,
    EVENTO_OFERTA_ADIADA,
    EVENTO_RETORNO_ADIADO,
    EVENTO_RETORNO_CONFIRMADO,
)


TIPO_TRATAMENTO_CONTEXTO_INVALIDO = "opcao_invalida"


def validar_etapa13(conteudo_texto):
    resultado = validar_etapa11(conteudo_texto)

    if resultado == EVENTO_OFERTA_ACEITA:
        return EVENTO_RETORNO_CONFIRMADO

    if resultado == EVENTO_OFERTA_ADIADA:
        return EVENTO_RETORNO_ADIADO

    return None
```

### Passo 20 - Adaptar a extração de email à etapa 14

Arquivo: `workers/worker_flow/response_flow/etapas/validadores_contexto/valida_etapa14.py`

```python
import re
from dataclasses import dataclass

from workers.worker_flow.response_flow.transicoes.eventos import (
    EVENTO_EMAIL_INFORMADO,
)


TIPO_TRATAMENTO_EMAIL_INVALIDO = "email_invalido"

MOTIVO_EMAIL_AUSENTE = "email_ausente"
MOTIVO_MULTIPLOS_EMAILS = "multiplos_emails"
MOTIVO_FORMATO_INVALIDO = "formato_invalido"
MOTIVO_DOMINIO_INVALIDO = "dominio_invalido"

PONTUACAO_FINAL_FRASE = ".,;:!?)]}>\"'”’"
PONTUACAO_INICIAL_FRASE = "([<{\"'“‘"
PADRAO_CANDIDATO_EMAIL = re.compile(r"[^\s@]+@[^\s@]+", re.UNICODE)


@dataclass(frozen=True)
class ResultadoValidacaoEmail:
    valido: bool
    email: str | None = None
    evento: str | None = None
    motivo: str | None = None


def validar_etapa14(texto):
    texto_original = str(texto or "").strip()

    if not texto_original:
        return _resultado_invalido(MOTIVO_EMAIL_AUSENTE)

    if texto_original.count("@") == 0:
        return _resultado_invalido(MOTIVO_EMAIL_AUSENTE)

    if texto_original.count("@") != 1:
        return _resultado_invalido(MOTIVO_MULTIPLOS_EMAILS)

    candidatos = _extrair_candidatos(texto_original)

    if not candidatos:
        return _resultado_invalido(MOTIVO_EMAIL_AUSENTE)

    if len(candidatos) != 1:
        return _resultado_invalido(MOTIVO_MULTIPLOS_EMAILS)

    email = _normalizar_email(candidatos[0])
    motivo = _validar_estrutura_email(email)

    if motivo:
        return _resultado_invalido(motivo)

    return ResultadoValidacaoEmail(
        valido=True,
        email=email,
        evento=EVENTO_EMAIL_INFORMADO,
    )


def _extrair_candidatos(texto):
    candidatos = []

    for correspondencia in PADRAO_CANDIDATO_EMAIL.finditer(texto):
        candidato = correspondencia.group(0)
        candidato = candidato.lstrip(PONTUACAO_INICIAL_FRASE)
        candidato = candidato.rstrip(PONTUACAO_FINAL_FRASE)

        if candidato:
            candidatos.append(candidato)

    return candidatos


def _normalizar_email(email):
    parte_local, separador, dominio = email.rpartition("@")
    if not separador:
        return email
    return f"{parte_local}@{dominio.lower()}"


def _validar_estrutura_email(email):
    parte_local, separador, dominio = email.rpartition("@")

    if not separador or not parte_local or not dominio:
        return MOTIVO_FORMATO_INVALIDO

    dominio_base, ponto, terminacao = dominio.rpartition(".")

    if not ponto or not dominio_base or not terminacao:
        return MOTIVO_DOMINIO_INVALIDO

    return None


def _resultado_invalido(motivo):
    return ResultadoValidacaoEmail(valido=False, motivo=motivo)
```

### Passo 21 - Validar a confirmação do email

Arquivo: `workers/worker_flow/response_flow/etapas/validadores_contexto/valida_etapa15.py`

```python
from workers.worker_flow.response_flow.etapas.validadores_contexto.confirmacao import (
    normalizar_confirmacao,
)
from workers.worker_flow.response_flow.transicoes.eventos import (
    EVENTO_EMAIL_CONFIRMADO,
    EVENTO_EMAIL_REJEITADO,
)


TIPO_TRATAMENTO_CONFIRMACAO_INVALIDA = "confirmacao_email_invalida"


def validar_etapa15(conteudo_texto):
    confirmacao = normalizar_confirmacao(conteudo_texto)

    if confirmacao is None:
        return None

    if confirmacao:
        return EVENTO_EMAIL_CONFIRMADO
    return EVENTO_EMAIL_REJEITADO
```

### Passo 22 - Validar a confirmação de agendamento na etapa 23

Arquivo: `workers/worker_flow/response_flow/etapas/validadores_contexto/valida_etapa23.py`

```python
import re

from workers.worker_flow.response_flow.etapas.validadores_universais.validador_financeiro import (
    normalizar_texto,
)
from workers.worker_flow.response_flow.transicoes.eventos import (
    EVENTO_AGENDAMENTO_CONFIRMADO,
)


TIPO_TRATAMENTO_AGENDAMENTO_NAO_CONFIRMADO = "agendamento_nao_confirmado"

_CONFIRMACOES_ACEITAS = (
    "agendamento realizado",
    "agendamento feito",
    "ja esta agendado",
    "consegui agendar",
    "esta agendado",
    "ja agendei",
    "ja marquei",
    "agendado",
    "agendei",
    "marcado",
)

_PADROES_CONFIRMACAO = tuple(
    re.compile(rf"(?<![a-z0-9]){re.escape(expressao)}(?![a-z0-9])")
    for expressao in _CONFIRMACOES_ACEITAS
)


def validar_etapa23(conteudo_texto):
    if not isinstance(conteudo_texto, str):
        return None

    texto = normalizar_texto(conteudo_texto)
    texto = re.sub(r"[^a-z0-9\s]", " ", texto)
    texto = " ".join(texto.split())

    if any(padrao.search(texto) for padrao in _PADROES_CONFIRMACAO):
        return EVENTO_AGENDAMENTO_CONFIRMADO

    return None
```

O validador procura uma expressão aceita dentro da frase inteira. Assim,
`Agendado para sexta às 14h` e `Já marquei para amanhã` avançam, mas uma
expressão embutida dentro de outra palavra não produz falso positivo.

### Passo 23 - Manter o validador universal da triagem

Arquivo: `workers/worker_flow/response_flow/etapas/validadores_universais/validador_triagem.py`

```python
from workers.worker_flow.response_flow.etapas.validadores_universais.validador_financeiro import (
    normalizar_texto,
)


TIPO_TRATAMENTO_RESPOSTA_TRIAGEM_INVALIDA = "resposta_triagem_invalida"

RESPOSTAS_TRIAGEM = {
    "nunca": "Nunca",
    "as vezes": "Às vezes",
    "frequentemente": "Frequentemente",
}

TIPOS_MENSAGEM_ACEITOS = {"text", "interactive", "button"}


def validar_resposta_triagem(conteudo_texto, tipo_mensagem=None):
    if tipo_mensagem not in TIPOS_MENSAGEM_ACEITOS:
        return None

    if not isinstance(conteudo_texto, str):
        return None

    texto = " ".join(normalizar_texto(conteudo_texto).split())
    return RESPOSTAS_TRIAGEM.get(texto)
```

## Fase 4 - Mensagens das 24 etapas

### Passo 24 - Mensagens da etapa 1

Arquivo: `core/integrations/whatsapp/messages/etapa1_messages.py`

```python
from core.integrations.whatsapp.messages.componentes_compartilhados import (
    RODAPE_OPCAO_UNICA,
    montar_texto_com_rodape,
)


MENSAGEM_ETAPA1 = (
    "Que bom ver você de volta, {nome}! ☺️\n\n"
    "Você quer iniciar um novo atendimento ou prefere atualizar seu nome?"
)
MENSAGEM_MIDIA_ETAPA1 = (
    "Ainda não reconhecemos mensagens com mídia, apenas texto.\n\n"
    "Você quer iniciar um novo atendimento ou prefere atualizar seu nome?"
)
MENSAGEM_FINANCEIRO_ETAPA1 = (
    "Informações como valores são apresentadas no atendimento presencial "
    "após a aula *gratuita*.\n\n"
    "Você quer iniciar um novo atendimento ou prefere atualizar seu nome?"
)
MENSAGEM_CONTEXTO_INVALIDO_ETAPA1 = (
    "Não consegui entender sua resposta. Escolha uma das opções abaixo."
)

BOTAO_ETAPA1_MUDAR_NOME = "Mudar nome"
BOTAO_ETAPA1_NOVO_ATENDIMENTO = "Novo atendimento"
BOTOES_ETAPA1 = (
    BOTAO_ETAPA1_MUDAR_NOME,
    BOTAO_ETAPA1_NOVO_ATENDIMENTO,
)


def montar_mensagem_etapa1(nome):
    return _com_rodape(MENSAGEM_ETAPA1.format(nome=nome))


def montar_mensagem_midia_etapa1():
    return _com_rodape(MENSAGEM_MIDIA_ETAPA1)


def montar_mensagem_financeiro_etapa1():
    return _com_rodape(MENSAGEM_FINANCEIRO_ETAPA1)


def montar_mensagem_contexto_invalido_etapa1():
    return _com_rodape(MENSAGEM_CONTEXTO_INVALIDO_ETAPA1)


def montar_botoes_etapa1():
    return BOTOES_ETAPA1


def _com_rodape(mensagem):
    return montar_texto_com_rodape(mensagem, RODAPE_OPCAO_UNICA)
```

### Passo 25 - Mensagens da etapa 2

Arquivo: `core/integrations/whatsapp/messages/etapa2_messages.py`

```python
MENSAGEM_ETAPA2 = "Certo! Me fala seu novo primeiro nome, exemplo: Pedro."
MENSAGEM_MIDIA_ETAPA2 = (
    "Ainda não reconhecemos mensagens com mídia, apenas texto.\n"
    "Me fala seu novo primeiro nome, exemplo: Pedro."
)
MENSAGEM_FINANCEIRO_ETAPA2 = (
    "Informações como valores são apresentadas no atendimento presencial "
    "após a aula *gratuita*.\n"
    "Agora me fala seu novo primeiro nome, exemplo: Pedro."
)
MENSAGEM_NOME_INVALIDO_ETAPA2 = (
    "Não consegui entender o nome. Me fala somente o primeiro nome, "
    "exemplo: Pedro."
)


def montar_mensagem_etapa2():
    return MENSAGEM_ETAPA2


def montar_mensagem_midia_etapa2():
    return MENSAGEM_MIDIA_ETAPA2


def montar_mensagem_financeiro_etapa2():
    return MENSAGEM_FINANCEIRO_ETAPA2


def montar_mensagem_nome_invalido_etapa2():
    return MENSAGEM_NOME_INVALIDO_ETAPA2
```

### Passo 26 - Mensagens da etapa 3

Arquivo: `core/integrations/whatsapp/messages/etapa3_messages.py`

```python
from core.integrations.whatsapp.messages.confirmacao_componentes import (
    montar_botoes_confirmacao,
    montar_mensagem_confirmacao,
)


MENSAGEM_MIDIA_ETAPA3 = (
    "Ainda não reconhecemos mensagens com mídia, apenas texto."
)
MENSAGEM_FINANCEIRO_ETAPA3 = (
    "Informações como valores são apresentadas no atendimento presencial "
    "após a aula *gratuita*."
)
MENSAGEM_CONTEXTO_INVALIDO_ETAPA3 = "Não consegui entender sua resposta."


def montar_mensagem_etapa3(nome):
    return montar_mensagem_confirmacao(
        f"Confirma que seu nome é {nome}?"
    )


def montar_mensagem_midia_etapa3(nome):
    return montar_mensagem_confirmacao(
        f"Confirma que seu nome é {nome}?",
        MENSAGEM_MIDIA_ETAPA3,
    )


def montar_mensagem_financeiro_etapa3(nome):
    return montar_mensagem_confirmacao(
        f"Confirma que seu nome é {nome}?",
        MENSAGEM_FINANCEIRO_ETAPA3,
    )


def montar_mensagem_contexto_invalido_etapa3(nome):
    return montar_mensagem_confirmacao(
        f"Confirma que seu nome é {nome}?",
        MENSAGEM_CONTEXTO_INVALIDO_ETAPA3,
    )


def montar_botoes_etapa3():
    return montar_botoes_confirmacao()
```

### Passo 27 - Mensagens da etapa 4

Arquivo: `core/integrations/whatsapp/messages/etapa4_messages.py`

```python
from core.integrations.whatsapp.messages.componentes_compartilhados import (
    RODAPE_OPCAO_UNICA,
    montar_texto_com_rodape,
)


MENSAGEM_ETAPA4 = (
    "Certo, {nome}! Conta para mim, esse atendimento é para você ou "
    "para outra pessoa?"
)
MENSAGEM_MIDIA_ETAPA4 = (
    "Ainda não reconhecemos mensagens com mídia, apenas texto.\n"
    "Esse atendimento é para você ou para outra pessoa?"
)
MENSAGEM_FINANCEIRO_ETAPA4 = (
    "Informações como valores são apresentadas no atendimento presencial "
    "após a aula *gratuita*.\n"
    "Esse atendimento é para você ou para outra pessoa?"
)
MENSAGEM_CONTEXTO_INVALIDO_ETAPA4 = (
    "Não consegui entender sua resposta. Esse atendimento é para você ou "
    "para outra pessoa?"
)

BOTAO_PARA_MIM = "Para mim"
BOTAO_OUTRA_PESSOA = "Para outra pessoa"
BOTOES_ETAPA4 = (BOTAO_PARA_MIM, BOTAO_OUTRA_PESSOA)


def montar_mensagem_etapa4(nome):
    return _com_rodape(MENSAGEM_ETAPA4.format(nome=nome))


def montar_mensagem_midia_etapa4():
    return _com_rodape(MENSAGEM_MIDIA_ETAPA4)


def montar_mensagem_financeiro_etapa4():
    return _com_rodape(MENSAGEM_FINANCEIRO_ETAPA4)


def montar_mensagem_contexto_invalido_etapa4():
    return _com_rodape(MENSAGEM_CONTEXTO_INVALIDO_ETAPA4)


def montar_botoes_etapa4():
    return BOTOES_ETAPA4


def _com_rodape(mensagem):
    return montar_texto_com_rodape(mensagem, RODAPE_OPCAO_UNICA)
```

### Passo 28 - Mensagens da etapa 5

Arquivo: `core/integrations/whatsapp/messages/etapa5_messages.py`

```python
from core.integrations.whatsapp.messages.componentes_compartilhados import (
    RODAPE_ETAPA5_BOAS_VINDAS,
    montar_texto_com_rodape,
)


MENSAGEM_ETAPA5 = (
    "{saudacao}! Sou a Suh, atendente virtual do {nome_unidade}! ☺️\n"
    "Como você se chama?"
)
MENSAGEM_MIDIA_INICIO_ETAPA5 = (
    "{saudacao}! Sou a Suh, atendente virtual do {nome_unidade}! ☺️\n"
    "Ainda não reconhecemos mensagens com mídia, apenas texto.\n"
    "Me diz, qual é o seu primeiro nome?"
)
MENSAGEM_FINANCEIRO_INICIO_ETAPA5 = (
    "{saudacao}! Sou a Suh, atendente virtual do {nome_unidade}! ☺️\n"
    "Informações como valores são apresentadas no atendimento presencial "
    "após a aula *gratuita*.\n"
    "Me diz, qual é o seu primeiro nome?"
)
MENSAGEM_MIDIA_ETAPA5 = (
    "Ainda não reconhecemos mensagens com mídia, apenas texto.\n"
    "Me diz, qual é o seu primeiro nome?"
)
MENSAGEM_FINANCEIRO_ETAPA5 = (
    "Informações como valores são apresentadas no atendimento presencial "
    "após a aula *gratuita*.\n"
    "Me diz, qual é o seu primeiro nome?"
)
MENSAGEM_NOME_INVALIDO_ETAPA5 = (
    "Não consegui entender seu nome. Me fala somente o primeiro nome, "
    "exemplo: Pedro."
)
MENSAGEM_NOME_REJEITADO_ETAPA5 = (
    "Tudo bem! Me fala novamente seu primeiro nome, exemplo: Pedro."
)


def montar_mensagem_etapa5(saudacao, nome_unidade):
    return montar_texto_com_rodape(
        MENSAGEM_ETAPA5.format(
            saudacao=saudacao,
            nome_unidade=nome_unidade,
        ),
        RODAPE_ETAPA5_BOAS_VINDAS,
    )


def montar_mensagem_midia_inicio_etapa5(saudacao, nome_unidade):
    return montar_texto_com_rodape(
        MENSAGEM_MIDIA_INICIO_ETAPA5.format(
            saudacao=saudacao,
            nome_unidade=nome_unidade,
        ),
        RODAPE_ETAPA5_BOAS_VINDAS,
    )


def montar_mensagem_financeiro_inicio_etapa5(saudacao, nome_unidade):
    return montar_texto_com_rodape(
        MENSAGEM_FINANCEIRO_INICIO_ETAPA5.format(
            saudacao=saudacao,
            nome_unidade=nome_unidade,
        ),
        RODAPE_ETAPA5_BOAS_VINDAS,
    )


def montar_mensagem_midia_etapa5():
    return MENSAGEM_MIDIA_ETAPA5


def montar_mensagem_financeiro_etapa5():
    return MENSAGEM_FINANCEIRO_ETAPA5


def montar_mensagem_nome_invalido_etapa5():
    return MENSAGEM_NOME_INVALIDO_ETAPA5


def montar_mensagem_nome_rejeitado_etapa5():
    return MENSAGEM_NOME_REJEITADO_ETAPA5
```

### Passo 29 - Mensagens da etapa 6

Arquivo: `core/integrations/whatsapp/messages/etapa6_messages.py`

```python
from core.integrations.whatsapp.messages.componentes_compartilhados import (
    RODAPE_OPCAO_UNICA,
    montar_texto_com_rodape,
)


MENSAGEM_ETAPA6 = (
    "Prazer, {nome}! ☺️\n\n"
    "O Supera é um curso de estimulação cognitiva e ginástica para o cérebro. "
    "Aqui nós iremos potencializar as habilidades cognitivas, socioemocionais "
    "e éticas do aluno, como atenção, concentração e memória.\n\n"
    "Conta para mim, esse atendimento é para você ou para outra pessoa?"
)
MENSAGEM_MIDIA_ETAPA6 = (
    "Ainda não reconhecemos mensagens com mídia, apenas texto.\n"
    "Esse atendimento é para você ou para outra pessoa?"
)
MENSAGEM_FINANCEIRO_ETAPA6 = (
    "Informações como valores são apresentadas no atendimento presencial "
    "após a aula *gratuita*.\n"
    "Esse atendimento é para você ou para outra pessoa?"
)
MENSAGEM_CONTEXTO_INVALIDO_ETAPA6 = (
    "Não consegui entender sua resposta. Esse atendimento é para você ou "
    "para outra pessoa?"
)

BOTAO_PARA_MIM = "Para mim"
BOTAO_OUTRA_PESSOA = "Para outra pessoa"
BOTOES_ETAPA6 = (BOTAO_PARA_MIM, BOTAO_OUTRA_PESSOA)


def montar_mensagem_etapa6(nome):
    return _com_rodape(MENSAGEM_ETAPA6.format(nome=nome))


def montar_mensagem_midia_etapa6():
    return _com_rodape(MENSAGEM_MIDIA_ETAPA6)


def montar_mensagem_financeiro_etapa6():
    return _com_rodape(MENSAGEM_FINANCEIRO_ETAPA6)


def montar_mensagem_contexto_invalido_etapa6():
    return _com_rodape(MENSAGEM_CONTEXTO_INVALIDO_ETAPA6)


def montar_botoes_etapa6():
    return BOTOES_ETAPA6


def _com_rodape(mensagem):
    return montar_texto_com_rodape(mensagem, RODAPE_OPCAO_UNICA)
```

### Passo 30 - Mensagens da etapa 7

Arquivo: `core/integrations/whatsapp/messages/etapa7_messages.py`

```python
MENSAGEM_ETAPA7 = "Qual é o primeiro nome da pessoa?"
MENSAGEM_MIDIA_ETAPA7 = (
    "Ainda não reconhecemos mensagens com mídia, apenas texto.\n"
    "Me diz, qual é o primeiro nome da pessoa?"
)
MENSAGEM_FINANCEIRO_ETAPA7 = (
    "Informações como valores são apresentadas no atendimento presencial "
    "após a aula *gratuita*.\n"
    "Me diz, qual é o primeiro nome da pessoa?"
)
MENSAGEM_NOME_INVALIDO_ETAPA7 = (
    "Não consegui entender o nome da pessoa. Me fala somente o primeiro "
    "nome, exemplo: Pedro."
)


def montar_mensagem_etapa7():
    return MENSAGEM_ETAPA7


def montar_mensagem_midia_etapa7():
    return MENSAGEM_MIDIA_ETAPA7


def montar_mensagem_financeiro_etapa7():
    return MENSAGEM_FINANCEIRO_ETAPA7


def montar_mensagem_nome_invalido_etapa7():
    return MENSAGEM_NOME_INVALIDO_ETAPA7
```

### Passo 31 - Mensagens da etapa 8

Arquivo: `core/integrations/whatsapp/messages/etapa8_messages.py`

```python
from core.integrations.whatsapp.messages.confirmacao_componentes import (
    montar_botoes_confirmacao,
    montar_mensagem_confirmacao,
)


MENSAGEM_MIDIA_ETAPA8 = (
    "Ainda não reconhecemos mensagens com mídia, apenas texto."
)
MENSAGEM_FINANCEIRO_ETAPA8 = (
    "Informações como valores são apresentadas no atendimento presencial "
    "após a aula *gratuita*."
)
MENSAGEM_CONTEXTO_INVALIDO_ETAPA8 = "Não consegui entender sua resposta."


def montar_mensagem_etapa8(nome):
    return montar_mensagem_confirmacao(
        f"Confirma que o nome da pessoa é {nome}?"
    )


def montar_mensagem_midia_etapa8(nome):
    return montar_mensagem_confirmacao(
        f"Confirma que o nome da pessoa é {nome}?",
        MENSAGEM_MIDIA_ETAPA8,
    )


def montar_mensagem_financeiro_etapa8(nome):
    return montar_mensagem_confirmacao(
        f"Confirma que o nome da pessoa é {nome}?",
        MENSAGEM_FINANCEIRO_ETAPA8,
    )


def montar_mensagem_contexto_invalido_etapa8(nome):
    return montar_mensagem_confirmacao(
        f"Confirma que o nome da pessoa é {nome}?",
        MENSAGEM_CONTEXTO_INVALIDO_ETAPA8,
    )


def montar_botoes_etapa8():
    return montar_botoes_confirmacao()
```

### Passo 32 - Mensagens da etapa 9

Arquivo: `core/integrations/whatsapp/messages/etapa9_messages.py`

```python
MENSAGEM_CLIENTE_ETAPA9 = "Certo, agora me fala: qual é a sua idade?"
MENSAGEM_DEPENDENTE_ETAPA9 = (
    "Certo, agora me fala: qual é a idade de {nome}?"
)
MENSAGEM_CLIENTE_MIDIA_ETAPA9 = (
    "Ainda não reconhecemos mensagens com mídia, apenas texto.\n"
    "Me diz, qual é a sua idade?"
)
MENSAGEM_DEPENDENTE_MIDIA_ETAPA9 = (
    "Ainda não reconhecemos mensagens com mídia, apenas texto.\n"
    "Me diz, qual é a idade de {nome}?"
)
MENSAGEM_CLIENTE_FINANCEIRO_ETAPA9 = (
    "Informações como valores são apresentadas no atendimento presencial "
    "após a aula *gratuita*.\nMe diz, qual é a sua idade?"
)
MENSAGEM_DEPENDENTE_FINANCEIRO_ETAPA9 = (
    "Informações como valores são apresentadas no atendimento presencial "
    "após a aula *gratuita*.\nMe diz, qual é a idade de {nome}?"
)
MENSAGEM_CLIENTE_INVALIDA_ETAPA9 = (
    "Não consegui entender sua idade. Digite um único valor, exemplo: 25."
)
MENSAGEM_DEPENDENTE_INVALIDA_ETAPA9 = (
    "Não consegui entender a idade de {nome}. Digite um único valor, "
    "exemplo: 10."
)
MENSAGEM_CLIENTE_MENOR_18_ETAPA9 = (
    "Como você tem menos de 18 anos, este atendimento precisa ser realizado "
    "por um adulto responsável.\n\nPeça a um adulto para entrar em contato "
    "com a gente. Um abraço e até logo! 👋☺️"
)
MENSAGEM_DEPENDENTE_ABAIXO_MINIMO_ETAPA9 = (
    "No momento, esta unidade do Supera realiza treinamentos com crianças a "
    "partir de {idade_minima} anos. Quando {nome} completar {idade_minima} "
    "anos, você poderá entrar em contato novamente.\n\n"
    "Um abraço e até logo! 👋☺️"
)
MENSAGEM_IDADE_ACIMA_99_ETAPA9 = (
    "Entendi. Para idades muito avançadas, é melhor falar com nossa "
    "consultora especializada. Vou te passar o contato dela para continuar "
    "o atendimento, tudo bem?\n\nBasta clicar no botão abaixo."
)
BOTAO_FALAR_COM_CONSULTORA = "Falar com Consultora"


def montar_mensagem_cliente_etapa9():
    return MENSAGEM_CLIENTE_ETAPA9


def montar_mensagem_dependente_etapa9(nome):
    return MENSAGEM_DEPENDENTE_ETAPA9.format(nome=nome)


def montar_mensagem_cliente_midia_etapa9():
    return MENSAGEM_CLIENTE_MIDIA_ETAPA9


def montar_mensagem_dependente_midia_etapa9(nome):
    return MENSAGEM_DEPENDENTE_MIDIA_ETAPA9.format(nome=nome)


def montar_mensagem_cliente_financeiro_etapa9():
    return MENSAGEM_CLIENTE_FINANCEIRO_ETAPA9


def montar_mensagem_dependente_financeiro_etapa9(nome):
    return MENSAGEM_DEPENDENTE_FINANCEIRO_ETAPA9.format(nome=nome)


def montar_mensagem_cliente_invalida_etapa9():
    return MENSAGEM_CLIENTE_INVALIDA_ETAPA9


def montar_mensagem_dependente_invalida_etapa9(nome):
    return MENSAGEM_DEPENDENTE_INVALIDA_ETAPA9.format(nome=nome)


def montar_mensagem_cliente_menor_18_etapa9():
    return MENSAGEM_CLIENTE_MENOR_18_ETAPA9


def montar_mensagem_dependente_abaixo_minimo_etapa9(nome, idade_minima):
    return MENSAGEM_DEPENDENTE_ABAIXO_MINIMO_ETAPA9.format(
        nome=nome,
        idade_minima=idade_minima,
    )


def montar_mensagem_idade_acima_99_etapa9():
    return MENSAGEM_IDADE_ACIMA_99_ETAPA9
```

### Passo 33 - Mensagens da etapa 10

Arquivo: `core/integrations/whatsapp/messages/etapa10_messages.py`

```python
from core.integrations.whatsapp.messages.confirmacao_componentes import (
    montar_botoes_confirmacao,
    montar_mensagem_confirmacao,
)


MENSAGEM_MIDIA_ETAPA10 = (
    "Ainda não reconhecemos mensagens com mídia, apenas texto."
)
MENSAGEM_FINANCEIRO_ETAPA10 = (
    "Informações como valores são apresentadas no atendimento presencial "
    "após a aula *gratuita*."
)
MENSAGEM_CONTEXTO_INVALIDO_ETAPA10 = "Não consegui entender sua resposta."


def montar_mensagem_cliente_etapa10(idade):
    return montar_mensagem_confirmacao(
        f"Confirma que sua idade é {idade} anos?"
    )


def montar_mensagem_dependente_etapa10(nome, idade):
    return montar_mensagem_confirmacao(
        f"Confirma que {nome} tem {idade} anos?"
    )


def montar_mensagem_tratamento_etapa10(pergunta, prefixo):
    return montar_mensagem_confirmacao(pergunta, prefixo)


def montar_mensagem_midia_etapa10():
    return MENSAGEM_MIDIA_ETAPA10


def montar_mensagem_financeiro_etapa10():
    return MENSAGEM_FINANCEIRO_ETAPA10


def montar_mensagem_contexto_invalido_etapa10():
    return MENSAGEM_CONTEXTO_INVALIDO_ETAPA10


def montar_botoes_etapa10():
    return montar_botoes_confirmacao()
```

### Passo 34 - Mensagens da etapa 11

Arquivo: `core/integrations/whatsapp/messages/etapa11_messages.py`

```python
from core.integrations.whatsapp.messages.componentes_compartilhados import (
    RODAPE_OPCAO_UNICA,
    montar_texto_com_rodape,
)


MENSAGEM_CLIENTE_NOVATO_ETAPA11 = (
    "Que maravilha, {nome_cliente}! 🥰\n\n"
    "Gostaria de te oferecer uma aula experimental + avaliação cognitiva "
    "*gratuita*. Elas servem para que possamos saber como anda a saúde do seu "
    "cérebro e para que você possa nos conhecer. 😄\n\nVamos agendar?"
)
MENSAGEM_DEPENDENTE_NOVATO_ETAPA11 = (
    "Que maravilha! 🥰\n\nGostaria de oferecer uma aula experimental + "
    "avaliação cognitiva *gratuita* para {nome_dependente}. Elas servem para "
    "que possamos saber como anda a saúde do cérebro de {nome_dependente} e "
    "para que vocês possam nos conhecer. 😄\n\nVamos agendar?"
)
MENSAGEM_CLIENTE_VETERANO_ETAPA11 = (
    "Certo, {nome_cliente}! O que você acha de uma aula experimental + "
    "avaliação cognitiva *gratuita*? Vamos agendar?"
)
MENSAGEM_DEPENDENTE_VETERANO_ETAPA11 = (
    "Certo, {nome_cliente}! O que você acha de uma aula experimental + "
    "avaliação cognitiva *gratuita* para {nome_dependente}? Vamos agendar?"
)

BOTAO_QUERO_AGENDAR = "Quero agendar"
BOTAO_TALVEZ_MAIS_TARDE = "Talvez mais tarde"
BOTOES_ETAPA11 = (BOTAO_QUERO_AGENDAR, BOTAO_TALVEZ_MAIS_TARDE)


def montar_mensagem_etapa11(
    nome_cliente,
    nome_dependente,
    *,
    status_dependente,
    cliente_veterano,
    prefixo=None,
):
    if status_dependente and cliente_veterano:
        mensagem = MENSAGEM_DEPENDENTE_VETERANO_ETAPA11.format(
            nome_cliente=nome_cliente,
            nome_dependente=nome_dependente,
        )
    elif status_dependente:
        mensagem = MENSAGEM_DEPENDENTE_NOVATO_ETAPA11.format(
            nome_dependente=nome_dependente,
        )
    elif cliente_veterano:
        mensagem = MENSAGEM_CLIENTE_VETERANO_ETAPA11.format(
            nome_cliente=nome_cliente,
        )
    else:
        mensagem = MENSAGEM_CLIENTE_NOVATO_ETAPA11.format(
            nome_cliente=nome_cliente,
        )

    if prefixo:
        mensagem = f"{prefixo.strip()}\n\n{mensagem}"

    return montar_texto_com_rodape(mensagem, RODAPE_OPCAO_UNICA)


def montar_botoes_etapa11():
    return BOTOES_ETAPA11
```

### Passo 35 - Mensagens da etapa 12

Arquivo: `core/integrations/whatsapp/messages/etapa12_messages.py`

```python
from core.integrations.whatsapp.messages.componentes_compartilhados import (
    RODAPE_ETAPA12_ESPERA,
    montar_texto_com_rodape,
)


MENSAGEM_ETAPA12 = (
    "Tudo bem! ☺️\nEntão nos falamos novamente em breve.\n"
    "Enquanto isso, nos siga no nosso Instagram e acompanhe nossas "
    "atualizações. Um abraço! 🫂🤗\n{link_instagram}"
)


def montar_mensagem_etapa12(link_instagram):
    link = str(link_instagram or "").strip()
    if not link:
        raise ValueError("Link do Instagram da unidade não configurado")
    return montar_texto_com_rodape(
        MENSAGEM_ETAPA12.format(link_instagram=link),
        RODAPE_ETAPA12_ESPERA,
    )
```

### Passo 36 - Mensagens da etapa 13

Arquivo: `core/integrations/whatsapp/messages/etapa13_messages.py`

```python
from core.integrations.whatsapp.messages.componentes_compartilhados import (
    RODAPE_OPCAO_UNICA,
    montar_texto_com_rodape,
)


BOTAO_QUERO_AGENDAR = "Quero agendar"
BOTAO_TALVEZ_MAIS_TARDE = "Talvez mais tarde"
BOTOES_ETAPA13 = (BOTAO_QUERO_AGENDAR, BOTAO_TALVEZ_MAIS_TARDE)


def montar_mensagem_etapa13(nome_cliente, nome_dependente=None, prefixo=None):
    if nome_dependente:
        mensagem = (
            f"Que bom ver você aqui novamente, {nome_cliente}! Vamos dar "
            f"continuidade ao agendamento de {nome_dependente}? ☺️"
        )
    else:
        mensagem = (
            f"Que bom ver você aqui novamente, {nome_cliente}! Vamos dar "
            "continuidade ao seu agendamento? ☺️"
        )

    if prefixo:
        mensagem = f"{prefixo.strip()}\n\n{mensagem}"

    return montar_texto_com_rodape(mensagem, RODAPE_OPCAO_UNICA)


def montar_botoes_etapa13():
    return BOTOES_ETAPA13
```

### Passo 37 - Mensagens da etapa 14

Arquivo: `core/integrations/whatsapp/messages/etapa14_messages.py`

```python
MENSAGEM_NOVATO_ETAPA14 = "Qual é o seu melhor email?"
MENSAGEM_VETERANO_ETAPA14 = (
    "Para continuar, me confirma seu melhor email?"
)
MENSAGEM_MIDIA_ETAPA14 = (
    "Ainda não reconhecemos mensagens com mídia, apenas texto."
)
MENSAGEM_FINANCEIRO_ETAPA14 = (
    "Informações como valores são apresentadas no atendimento presencial "
    "após a aula *gratuita*."
)
MENSAGEM_EMAIL_INVALIDO_ETAPA14 = (
    "Não consegui identificar um email válido. Digite o email completo, "
    "por exemplo: nome@gmail.com."
)


def montar_mensagem_etapa14(cliente_veterano, prefixo=None):
    mensagem = (
        MENSAGEM_VETERANO_ETAPA14
        if cliente_veterano
        else MENSAGEM_NOVATO_ETAPA14
    )
    if prefixo:
        return f"{prefixo.strip()}\n\n{mensagem}"
    return mensagem
```

### Passo 38 - Mensagens da etapa 15

Arquivo: `core/integrations/whatsapp/messages/etapa15_messages.py`

```python
from core.integrations.whatsapp.messages.confirmacao_componentes import (
    montar_botoes_confirmacao,
    montar_mensagem_confirmacao,
)


def montar_mensagem_etapa15(email, prefixo=None):
    return montar_mensagem_confirmacao(
        f"Confirma que seu email é {email}?",
        prefixo,
    )


def montar_botoes_etapa15():
    return montar_botoes_confirmacao()
```

### Passo 39 - Mensagens da etapa 16

Arquivo: `core/integrations/whatsapp/messages/etapa16_messages.py`

```python
MENSAGEM_ETAPA16 = (
    "Antes de continuarmos o agendamento, vamos realizar uma pequena "
    "triagem cognitiva com 6 perguntas objetivas de seleção única, ok?"
)
BOTAO_INICIAR_TRIAGEM = "Iniciar triagem"


def montar_mensagem_etapa16():
    return MENSAGEM_ETAPA16


def montar_botoes_etapa16():
    return (BOTAO_INICIAR_TRIAGEM,)
```

### Passo 40 - Mensagens da etapa 17

Arquivo: `core/integrations/whatsapp/messages/etapa17_messages.py`

```python
CABECALHO_ETAPA17 = "Pergunta 1"
MENSAGEM_CLIENTE_ETAPA17 = (
    "Com que frequência você esquece de acontecimentos recentes, "
    "como o que fez no final de semana?"
)
MENSAGEM_DEPENDENTE_ETAPA17 = (
    "Com que frequência {nome} esquece de acontecimentos recentes, "
    "como o que fez no final de semana?"
)


def montar_cabecalho_etapa17():
    return CABECALHO_ETAPA17


def montar_mensagem_cliente_etapa17(prefixo=None):
    return _montar(MENSAGEM_CLIENTE_ETAPA17, prefixo)


def montar_mensagem_dependente_etapa17(nome, prefixo=None):
    return _montar(MENSAGEM_DEPENDENTE_ETAPA17.format(nome=nome), prefixo)


def _montar(mensagem, prefixo):
    if prefixo:
        return f"{prefixo.strip()}\n\n{mensagem}"
    return mensagem
```

### Passo 41 - Mensagens da etapa 18

Arquivo: `core/integrations/whatsapp/messages/etapa18_messages.py`

```python
CABECALHO_ETAPA18 = "Pergunta 2"
MENSAGEM_CLIENTE_ETAPA18 = (
    "Com que frequência você esquece o que foi fazer ou procurar em outro lugar?"
)
MENSAGEM_DEPENDENTE_ETAPA18 = (
    "Com que frequência {nome} esquece o que foi fazer ou procurar em outro lugar?"
)


def montar_cabecalho_etapa18():
    return CABECALHO_ETAPA18


def montar_mensagem_cliente_etapa18(prefixo=None):
    return _montar(MENSAGEM_CLIENTE_ETAPA18, prefixo)


def montar_mensagem_dependente_etapa18(nome, prefixo=None):
    return _montar(MENSAGEM_DEPENDENTE_ETAPA18.format(nome=nome), prefixo)


def _montar(mensagem, prefixo):
    return f"{prefixo.strip()}\n\n{mensagem}" if prefixo else mensagem
```

### Passo 42 - Mensagens da etapa 19

Arquivo: `core/integrations/whatsapp/messages/etapa19_messages.py`

```python
CABECALHO_ETAPA19 = "Pergunta 3"
MENSAGEM_CLIENTE_ETAPA19 = (
    "Com que frequência você esquece nomes de pessoas conhecidas ou familiares?"
)
MENSAGEM_DEPENDENTE_ETAPA19 = (
    "Com que frequência {nome} esquece nomes de pessoas conhecidas ou familiares?"
)


def montar_cabecalho_etapa19():
    return CABECALHO_ETAPA19


def montar_mensagem_cliente_etapa19(prefixo=None):
    return _montar(MENSAGEM_CLIENTE_ETAPA19, prefixo)


def montar_mensagem_dependente_etapa19(nome, prefixo=None):
    return _montar(MENSAGEM_DEPENDENTE_ETAPA19.format(nome=nome), prefixo)


def _montar(mensagem, prefixo):
    return f"{prefixo.strip()}\n\n{mensagem}" if prefixo else mensagem
```

### Passo 43 - Mensagens da etapa 20

Arquivo: `core/integrations/whatsapp/messages/etapa20_messages.py`

```python
CABECALHO_ETAPA20 = "Pergunta 4"
MENSAGEM_CLIENTE_ETAPA20 = (
    "Com que frequência você esquece de levar suas coisas com você?"
)
MENSAGEM_DEPENDENTE_ETAPA20 = (
    "Com que frequência {nome} esquece de levar as próprias coisas?"
)


def montar_cabecalho_etapa20():
    return CABECALHO_ETAPA20


def montar_mensagem_cliente_etapa20(prefixo=None):
    return _montar(MENSAGEM_CLIENTE_ETAPA20, prefixo)


def montar_mensagem_dependente_etapa20(nome, prefixo=None):
    return _montar(MENSAGEM_DEPENDENTE_ETAPA20.format(nome=nome), prefixo)


def _montar(mensagem, prefixo):
    return f"{prefixo.strip()}\n\n{mensagem}" if prefixo else mensagem
```

### Passo 44 - Mensagens da etapa 21

Arquivo: `core/integrations/whatsapp/messages/etapa21_messages.py`

```python
CABECALHO_ETAPA21 = "Pergunta 5"
MENSAGEM_CLIENTE_ETAPA21 = (
    "Com que frequência você esquece palavras que queria dizer, "
    "mas que ficam na ponta da língua?"
)
MENSAGEM_DEPENDENTE_ETAPA21 = (
    "Com que frequência {nome} esquece palavras que queria dizer, "
    "mas que ficam na ponta da língua?"
)


def montar_cabecalho_etapa21():
    return CABECALHO_ETAPA21


def montar_mensagem_cliente_etapa21(prefixo=None):
    return _montar(MENSAGEM_CLIENTE_ETAPA21, prefixo)


def montar_mensagem_dependente_etapa21(nome, prefixo=None):
    return _montar(MENSAGEM_DEPENDENTE_ETAPA21.format(nome=nome), prefixo)


def _montar(mensagem, prefixo):
    return f"{prefixo.strip()}\n\n{mensagem}" if prefixo else mensagem
```

### Passo 45 - Mensagens da etapa 22

Arquivo: `core/integrations/whatsapp/messages/etapa22_messages.py`

```python
CABECALHO_ETAPA22 = "Pergunta 6"
MENSAGEM_CLIENTE_ETAPA22 = (
    "Com que frequência você esquece o que aconteceu em um filme, "
    "desenho, série ou novela?"
)
MENSAGEM_DEPENDENTE_ETAPA22 = (
    "Com que frequência {nome} esquece o que aconteceu em um filme, "
    "desenho, série ou novela?"
)


def montar_cabecalho_etapa22():
    return CABECALHO_ETAPA22


def montar_mensagem_cliente_etapa22(prefixo=None):
    return _montar(MENSAGEM_CLIENTE_ETAPA22, prefixo)


def montar_mensagem_dependente_etapa22(nome, prefixo=None):
    return _montar(MENSAGEM_DEPENDENTE_ETAPA22.format(nome=nome), prefixo)


def _montar(mensagem, prefixo):
    return f"{prefixo.strip()}\n\n{mensagem}" if prefixo else mensagem
```

### Passo 46 - Mensagens de agendamento da etapa 23

Arquivo: `core/integrations/whatsapp/messages/etapa23_messages.py`

```python
from core.integrations.whatsapp.messages.componentes_compartilhados import (
    montar_texto_com_rodape,
)


TEXTO_BOTAO_JA_AGENDEI = "Já agendei"
RODAPE_ETAPA23 = "Após finalizar, volta aqui e nos avisa no botão abaixo"
MENSAGEM_ETAPA23 = (
    "Obrigada por responder as perguntas! ☺️\n\n"
    "Para escolher o melhor dia e horário para sua avaliação cognitiva + "
    "aula experimental *gratuita*, basta clicar no link:\n{link_agendamento}"
)
MENSAGEM_MIDIA_ETAPA23 = (
    "Ainda não reconhecemos mensagens com mídia, apenas texto.\n\n"
    "Finalize seu agendamento pelo link:\n{link_agendamento}"
)
MENSAGEM_FINANCEIRO_ETAPA23 = (
    "Informações como valores são apresentadas no atendimento presencial "
    "após a aula *gratuita*.\n\nFinalize seu agendamento pelo link:\n"
    "{link_agendamento}"
)
MENSAGEM_CONTEXTO_INVALIDO_ETAPA23 = (
    "Não consegui entender sua resposta. Depois de finalizar pelo link, "
    "selecione *Já agendei*.\n{link_agendamento}"
)


def montar_mensagem_etapa23(link_agendamento, prefixo=None):
    link = _normalizar_link(link_agendamento)
    mensagem = (prefixo or MENSAGEM_ETAPA23).format(link_agendamento=link)
    return montar_texto_com_rodape(mensagem, RODAPE_ETAPA23)


def montar_botoes_etapa23():
    return (TEXTO_BOTAO_JA_AGENDEI,)


def _normalizar_link(link_agendamento):
    link = str(link_agendamento or "").strip()
    if not link.startswith(("https://", "http://")):
        raise ValueError("Link de agendamento da unidade inválido")
    return link
```

### Passo 47 - Mensagem final emitida na etapa 24

Arquivo: `core/integrations/whatsapp/messages/etapa24_messages.py`

```python
MENSAGEM_ETAPA24 = (
    "Perfeito! 🥰\n"
    "Agora é só aguardar o dia da avaliação. Um dia antes, nossa equipe "
    "entrará em contato para lembrar você do horário agendado.\n"
    "Até breve! 👋🏼😉"
)


def montar_mensagem_etapa24():
    return MENSAGEM_ETAPA24
```

Os senders continuam sem decidir transições. Cada um monta a variação textual
de sua etapa e delega somente o contrato técnico ao `sender_base.py`.

## Fase 5 - Senders

### Passo 48 - Sender da etapa 1

Arquivo: `core/integrations/whatsapp/pywa_functions/pywa_senders/etapa1.py`

```python
from core.integrations.whatsapp.messages.etapa1_messages import (
    montar_botoes_etapa1,
    montar_mensagem_contexto_invalido_etapa1,
    montar_mensagem_etapa1,
    montar_mensagem_financeiro_etapa1,
    montar_mensagem_midia_etapa1,
)
from core.integrations.whatsapp.pywa_functions.pywa_senders.sender_base import (
    enviar_mensagem_etapa,
)


ID_ETAPA = 1


def enviar_etapa1(cliente, phone_id, nome, tipo_tratamento=None):
    if tipo_tratamento == "tipo_mensagem_nao_suportado":
        mensagem = montar_mensagem_midia_etapa1()
    elif tipo_tratamento == "pergunta_financeira":
        mensagem = montar_mensagem_financeiro_etapa1()
    elif tipo_tratamento:
        mensagem = montar_mensagem_contexto_invalido_etapa1()
    else:
        mensagem = montar_mensagem_etapa1(nome)

    return enviar_mensagem_etapa(
        cliente,
        phone_id,
        mensagem,
        id_etapa=ID_ETAPA,
        evento_log="enviar_etapa1",
        botoes=montar_botoes_etapa1(),
        tipo_tratamento=tipo_tratamento,
    )
```

### Passo 49 - Sender da etapa 2

Arquivo: `core/integrations/whatsapp/pywa_functions/pywa_senders/etapa2.py`

```python
from core.integrations.whatsapp.messages.etapa2_messages import (
    montar_mensagem_etapa2,
    montar_mensagem_financeiro_etapa2,
    montar_mensagem_midia_etapa2,
    montar_mensagem_nome_invalido_etapa2,
)
from core.integrations.whatsapp.pywa_functions.pywa_senders.sender_base import (
    enviar_mensagem_etapa,
)


ID_ETAPA = 2


def enviar_etapa2(cliente, phone_id, tipo_tratamento=None):
    if tipo_tratamento == "tipo_mensagem_nao_suportado":
        mensagem = montar_mensagem_midia_etapa2()
    elif tipo_tratamento == "pergunta_financeira":
        mensagem = montar_mensagem_financeiro_etapa2()
    elif tipo_tratamento:
        mensagem = montar_mensagem_nome_invalido_etapa2()
    else:
        mensagem = montar_mensagem_etapa2()

    return enviar_mensagem_etapa(
        cliente,
        phone_id,
        mensagem,
        id_etapa=ID_ETAPA,
        evento_log="enviar_etapa2",
        tipo_tratamento=tipo_tratamento,
    )
```

### Passo 50 - Sender da etapa 3

Arquivo: `core/integrations/whatsapp/pywa_functions/pywa_senders/etapa3.py`

```python
from core.integrations.whatsapp.messages.etapa3_messages import (
    montar_botoes_etapa3,
    montar_mensagem_contexto_invalido_etapa3,
    montar_mensagem_etapa3,
    montar_mensagem_financeiro_etapa3,
    montar_mensagem_midia_etapa3,
)
from core.integrations.whatsapp.pywa_functions.pywa_senders.sender_base import (
    enviar_mensagem_etapa,
)


ID_ETAPA = 3


def enviar_etapa3(cliente, phone_id, nome, tipo_tratamento=None):
    if tipo_tratamento == "tipo_mensagem_nao_suportado":
        mensagem = montar_mensagem_midia_etapa3(nome)
    elif tipo_tratamento == "pergunta_financeira":
        mensagem = montar_mensagem_financeiro_etapa3(nome)
    elif tipo_tratamento:
        mensagem = montar_mensagem_contexto_invalido_etapa3(nome)
    else:
        mensagem = montar_mensagem_etapa3(nome)

    return enviar_mensagem_etapa(
        cliente,
        phone_id,
        mensagem,
        id_etapa=ID_ETAPA,
        evento_log="enviar_etapa3",
        botoes=montar_botoes_etapa3(),
        tipo_tratamento=tipo_tratamento,
    )
```

### Passo 51 - Sender da etapa 4

Arquivo: `core/integrations/whatsapp/pywa_functions/pywa_senders/etapa4.py`

```python
from core.integrations.whatsapp.messages.etapa4_messages import (
    montar_botoes_etapa4,
    montar_mensagem_contexto_invalido_etapa4,
    montar_mensagem_etapa4,
    montar_mensagem_financeiro_etapa4,
    montar_mensagem_midia_etapa4,
)
from core.integrations.whatsapp.pywa_functions.pywa_senders.sender_base import (
    enviar_mensagem_etapa,
)


ID_ETAPA = 4


def enviar_etapa4(cliente, phone_id, nome, tipo_tratamento=None):
    if tipo_tratamento == "tipo_mensagem_nao_suportado":
        mensagem = montar_mensagem_midia_etapa4()
    elif tipo_tratamento == "pergunta_financeira":
        mensagem = montar_mensagem_financeiro_etapa4()
    elif tipo_tratamento:
        mensagem = montar_mensagem_contexto_invalido_etapa4()
    else:
        mensagem = montar_mensagem_etapa4(nome)

    return enviar_mensagem_etapa(
        cliente,
        phone_id,
        mensagem,
        id_etapa=ID_ETAPA,
        evento_log="enviar_etapa4",
        botoes=montar_botoes_etapa4(),
        tipo_tratamento=tipo_tratamento,
    )
```

### Passo 52 - Sender da etapa 5

Arquivo: `core/integrations/whatsapp/pywa_functions/pywa_senders/etapa5.py`

```python
from core.integrations.whatsapp.messages.etapa5_messages import (
    montar_mensagem_etapa5,
    montar_mensagem_financeiro_etapa5,
    montar_mensagem_financeiro_inicio_etapa5,
    montar_mensagem_midia_etapa5,
    montar_mensagem_midia_inicio_etapa5,
    montar_mensagem_nome_invalido_etapa5,
    montar_mensagem_nome_rejeitado_etapa5,
)
from core.integrations.whatsapp.pywa_functions.pywa_senders.sender_base import (
    enviar_mensagem_etapa,
)


ID_ETAPA = 5


def enviar_etapa5(
    cliente,
    phone_id,
    saudacao,
    nome_unidade,
    *,
    inicial=False,
    variacao=None,
    tipo_tratamento=None,
):
    if inicial and tipo_tratamento == "tipo_mensagem_nao_suportado":
        mensagem = montar_mensagem_midia_inicio_etapa5(
            saudacao,
            nome_unidade,
        )
    elif inicial and tipo_tratamento == "pergunta_financeira":
        mensagem = montar_mensagem_financeiro_inicio_etapa5(
            saudacao,
            nome_unidade,
        )
    elif inicial:
        mensagem = montar_mensagem_etapa5(saudacao, nome_unidade)
    elif tipo_tratamento == "tipo_mensagem_nao_suportado":
        mensagem = montar_mensagem_midia_etapa5()
    elif tipo_tratamento == "pergunta_financeira":
        mensagem = montar_mensagem_financeiro_etapa5()
    elif variacao == "nome_rejeitado":
        mensagem = montar_mensagem_nome_rejeitado_etapa5()
    else:
        mensagem = montar_mensagem_nome_invalido_etapa5()

    return enviar_mensagem_etapa(
        cliente,
        phone_id,
        mensagem,
        id_etapa=ID_ETAPA,
        evento_log="enviar_etapa5",
        tipo_tratamento=tipo_tratamento,
    )
```

### Passo 53 - Sender da etapa 6

Arquivo: `core/integrations/whatsapp/pywa_functions/pywa_senders/etapa6.py`

```python
from core.integrations.whatsapp.messages.etapa6_messages import (
    montar_botoes_etapa6,
    montar_mensagem_contexto_invalido_etapa6,
    montar_mensagem_etapa6,
    montar_mensagem_financeiro_etapa6,
    montar_mensagem_midia_etapa6,
)
from core.integrations.whatsapp.pywa_functions.pywa_senders.sender_base import (
    enviar_mensagem_etapa,
)


ID_ETAPA = 6


def enviar_etapa6(cliente, phone_id, nome, tipo_tratamento=None):
    if tipo_tratamento == "tipo_mensagem_nao_suportado":
        mensagem = montar_mensagem_midia_etapa6()
    elif tipo_tratamento == "pergunta_financeira":
        mensagem = montar_mensagem_financeiro_etapa6()
    elif tipo_tratamento:
        mensagem = montar_mensagem_contexto_invalido_etapa6()
    else:
        mensagem = montar_mensagem_etapa6(nome)

    return enviar_mensagem_etapa(
        cliente,
        phone_id,
        mensagem,
        id_etapa=ID_ETAPA,
        evento_log="enviar_etapa6",
        botoes=montar_botoes_etapa6(),
        tipo_tratamento=tipo_tratamento,
    )
```

### Passo 54 - Sender da etapa 7

Arquivo: `core/integrations/whatsapp/pywa_functions/pywa_senders/etapa7.py`

```python
from core.integrations.whatsapp.messages.etapa7_messages import (
    montar_mensagem_etapa7,
    montar_mensagem_financeiro_etapa7,
    montar_mensagem_midia_etapa7,
    montar_mensagem_nome_invalido_etapa7,
)
from core.integrations.whatsapp.pywa_functions.pywa_senders.sender_base import (
    enviar_mensagem_etapa,
)


ID_ETAPA = 7


def enviar_etapa7(cliente, phone_id, tipo_tratamento=None):
    if tipo_tratamento == "tipo_mensagem_nao_suportado":
        mensagem = montar_mensagem_midia_etapa7()
    elif tipo_tratamento == "pergunta_financeira":
        mensagem = montar_mensagem_financeiro_etapa7()
    elif tipo_tratamento:
        mensagem = montar_mensagem_nome_invalido_etapa7()
    else:
        mensagem = montar_mensagem_etapa7()

    return enviar_mensagem_etapa(
        cliente,
        phone_id,
        mensagem,
        id_etapa=ID_ETAPA,
        evento_log="enviar_etapa7",
        tipo_tratamento=tipo_tratamento,
    )
```

### Passo 55 - Sender da etapa 8

Arquivo: `core/integrations/whatsapp/pywa_functions/pywa_senders/etapa8.py`

```python
from core.integrations.whatsapp.messages.etapa8_messages import (
    montar_botoes_etapa8,
    montar_mensagem_contexto_invalido_etapa8,
    montar_mensagem_etapa8,
    montar_mensagem_financeiro_etapa8,
    montar_mensagem_midia_etapa8,
)
from core.integrations.whatsapp.pywa_functions.pywa_senders.sender_base import (
    enviar_mensagem_etapa,
)


ID_ETAPA = 8


def enviar_etapa8(cliente, phone_id, nome, tipo_tratamento=None):
    if tipo_tratamento == "tipo_mensagem_nao_suportado":
        mensagem = montar_mensagem_midia_etapa8(nome)
    elif tipo_tratamento == "pergunta_financeira":
        mensagem = montar_mensagem_financeiro_etapa8(nome)
    elif tipo_tratamento:
        mensagem = montar_mensagem_contexto_invalido_etapa8(nome)
    else:
        mensagem = montar_mensagem_etapa8(nome)

    return enviar_mensagem_etapa(
        cliente,
        phone_id,
        mensagem,
        id_etapa=ID_ETAPA,
        evento_log="enviar_etapa8",
        botoes=montar_botoes_etapa8(),
        tipo_tratamento=tipo_tratamento,
    )
```

### Passo 56 - Sender da etapa 9

Arquivo: `core/integrations/whatsapp/pywa_functions/pywa_senders/etapa9.py`

```python
import re

from core.integrations.whatsapp.messages.etapa9_messages import (
    BOTAO_FALAR_COM_CONSULTORA,
    montar_mensagem_cliente_etapa9,
    montar_mensagem_cliente_financeiro_etapa9,
    montar_mensagem_cliente_invalida_etapa9,
    montar_mensagem_cliente_menor_18_etapa9,
    montar_mensagem_cliente_midia_etapa9,
    montar_mensagem_dependente_abaixo_minimo_etapa9,
    montar_mensagem_dependente_etapa9,
    montar_mensagem_dependente_financeiro_etapa9,
    montar_mensagem_dependente_invalida_etapa9,
    montar_mensagem_dependente_midia_etapa9,
    montar_mensagem_idade_acima_99_etapa9,
)
from core.integrations.whatsapp.pywa_functions.pywa_senders.sender_base import (
    enviar_mensagem_etapa,
)


ID_ETAPA = 9


def enviar_etapa9(
    cliente,
    phone_id,
    *,
    nome_dependente=None,
    tipo_tratamento=None,
):
    if nome_dependente and tipo_tratamento == "tipo_mensagem_nao_suportado":
        mensagem = montar_mensagem_dependente_midia_etapa9(nome_dependente)
    elif nome_dependente and tipo_tratamento == "pergunta_financeira":
        mensagem = montar_mensagem_dependente_financeiro_etapa9(nome_dependente)
    elif nome_dependente and tipo_tratamento:
        mensagem = montar_mensagem_dependente_invalida_etapa9(nome_dependente)
    elif nome_dependente:
        mensagem = montar_mensagem_dependente_etapa9(nome_dependente)
    elif tipo_tratamento == "tipo_mensagem_nao_suportado":
        mensagem = montar_mensagem_cliente_midia_etapa9()
    elif tipo_tratamento == "pergunta_financeira":
        mensagem = montar_mensagem_cliente_financeiro_etapa9()
    elif tipo_tratamento:
        mensagem = montar_mensagem_cliente_invalida_etapa9()
    else:
        mensagem = montar_mensagem_cliente_etapa9()

    return enviar_mensagem_etapa(
        cliente,
        phone_id,
        mensagem,
        id_etapa=ID_ETAPA,
        evento_log="enviar_etapa9",
        tipo_tratamento=tipo_tratamento,
    )


def enviar_etapa9_cliente_menor_18(cliente, phone_id):
    return _enviar_encerramento(
        cliente,
        phone_id,
        montar_mensagem_cliente_menor_18_etapa9(),
        "cliente_menor_18",
    )


def enviar_etapa9_dependente_abaixo_minimo(
    cliente,
    phone_id,
    nome,
    idade_minima,
):
    return _enviar_encerramento(
        cliente,
        phone_id,
        montar_mensagem_dependente_abaixo_minimo_etapa9(
            nome,
            idade_minima,
        ),
        "dependente_abaixo_idade_minima",
    )


def enviar_etapa9_idade_acima_99(cliente, phone_id, numero_comercial):
    numero = re.sub(r"\D", "", str(numero_comercial or ""))
    if len(numero) in {10, 11}:
        numero = f"55{numero}"
    if not numero.startswith("55") or len(numero) not in {12, 13}:
        raise ValueError("Número comercial inválido")

    contexto = enviar_mensagem_etapa(
        cliente,
        phone_id,
        montar_mensagem_idade_acima_99_etapa9(),
        id_etapa=ID_ETAPA,
        evento_log="enviar_etapa9_idade_acima_99",
        botao_url={
            "titulo": BOTAO_FALAR_COM_CONSULTORA,
            "url": f"https://wa.me/{numero}",
        },
    )
    contexto.update(
        encerrar_atendimento=True,
        motivo_encerramento="idade_acima_99",
    )
    return contexto


def _enviar_encerramento(cliente, phone_id, mensagem, motivo):
    contexto = enviar_mensagem_etapa(
        cliente,
        phone_id,
        mensagem,
        id_etapa=ID_ETAPA,
        evento_log=f"enviar_etapa9_{motivo}",
    )
    contexto.update(
        encerrar_atendimento=True,
        motivo_encerramento=motivo,
    )
    return contexto
```

### Passo 57 - Sender da etapa 10

Arquivo: `core/integrations/whatsapp/pywa_functions/pywa_senders/etapa10.py`

```python
from core.integrations.whatsapp.messages.etapa10_messages import (
    montar_botoes_etapa10,
    montar_mensagem_cliente_etapa10,
    montar_mensagem_dependente_etapa10,
    montar_mensagem_tratamento_etapa10,
)
from core.integrations.whatsapp.pywa_functions.pywa_senders.sender_base import (
    enviar_mensagem_etapa,
)


ID_ETAPA = 10


def enviar_etapa10_confirmacao(
    cliente,
    phone_id,
    idade,
    *,
    nome_dependente=None,
    prefixo=None,
    tipo_tratamento=None,
):
    if nome_dependente:
        pergunta = f"Confirma que {nome_dependente} tem {idade} anos?"
        mensagem = montar_mensagem_dependente_etapa10(
            nome_dependente,
            idade,
        )
    else:
        pergunta = f"Confirma que sua idade é {idade} anos?"
        mensagem = montar_mensagem_cliente_etapa10(idade)

    if prefixo:
        mensagem = montar_mensagem_tratamento_etapa10(pergunta, prefixo)

    return enviar_mensagem_etapa(
        cliente,
        phone_id,
        mensagem,
        id_etapa=ID_ETAPA,
        evento_log="enviar_etapa10_confirmacao",
        botoes=montar_botoes_etapa10(),
        tipo_tratamento=tipo_tratamento,
    )
```

### Passo 58 - Sender da etapa 11

Arquivo: `core/integrations/whatsapp/pywa_functions/pywa_senders/etapa11.py`

```python
from core.integrations.whatsapp.messages.etapa11_messages import (
    montar_botoes_etapa11,
    montar_mensagem_etapa11,
)
from core.integrations.whatsapp.pywa_functions.pywa_senders.sender_base import (
    enviar_mensagem_etapa,
)


ID_ETAPA = 11


def enviar_etapa11(
    cliente,
    phone_id,
    nome_cliente,
    nome_dependente,
    *,
    status_dependente,
    cliente_veterano,
    prefixo=None,
    tipo_tratamento=None,
):
    mensagem = montar_mensagem_etapa11(
        nome_cliente,
        nome_dependente,
        status_dependente=status_dependente,
        cliente_veterano=cliente_veterano,
        prefixo=prefixo,
    )
    return enviar_mensagem_etapa(
        cliente,
        phone_id,
        mensagem,
        id_etapa=ID_ETAPA,
        evento_log="enviar_etapa11",
        botoes=montar_botoes_etapa11(),
        tipo_tratamento=tipo_tratamento,
    )
```

### Passo 59 - Sender da etapa 12

Arquivo: `core/integrations/whatsapp/pywa_functions/pywa_senders/etapa12.py`

```python
from core.integrations.whatsapp.messages.etapa12_messages import (
    montar_mensagem_etapa12,
)
from core.integrations.whatsapp.pywa_functions.pywa_senders.sender_base import (
    enviar_mensagem_etapa,
)


def enviar_etapa12(cliente, phone_id, link_instagram):
    return enviar_mensagem_etapa(
        cliente,
        phone_id,
        montar_mensagem_etapa12(link_instagram),
        id_etapa=12,
        evento_log="enviar_etapa12",
    )
```

### Passo 60 - Sender da etapa 13

Arquivo: `core/integrations/whatsapp/pywa_functions/pywa_senders/etapa13.py`

```python
from core.integrations.whatsapp.messages.etapa13_messages import (
    montar_botoes_etapa13,
    montar_mensagem_etapa13,
)
from core.integrations.whatsapp.pywa_functions.pywa_senders.sender_base import (
    enviar_mensagem_etapa,
)


def enviar_etapa13(
    cliente,
    phone_id,
    nome_cliente,
    nome_dependente=None,
    *,
    prefixo=None,
    tipo_tratamento=None,
):
    return enviar_mensagem_etapa(
        cliente,
        phone_id,
        montar_mensagem_etapa13(
            nome_cliente,
            nome_dependente,
            prefixo,
        ),
        id_etapa=13,
        evento_log="enviar_etapa13",
        botoes=montar_botoes_etapa13(),
        tipo_tratamento=tipo_tratamento,
    )
```

### Passo 61 - Sender da etapa 14

Arquivo: `core/integrations/whatsapp/pywa_functions/pywa_senders/etapa14.py`

```python
from core.integrations.whatsapp.messages.etapa14_messages import (
    MENSAGEM_EMAIL_INVALIDO_ETAPA14,
    MENSAGEM_FINANCEIRO_ETAPA14,
    MENSAGEM_MIDIA_ETAPA14,
    montar_mensagem_etapa14,
)
from core.integrations.whatsapp.pywa_functions.pywa_senders.sender_base import (
    enviar_mensagem_etapa,
)


def enviar_etapa14(
    cliente,
    phone_id,
    cliente_veterano,
    tipo_tratamento=None,
):
    prefixos = {
        "tipo_mensagem_nao_suportado": MENSAGEM_MIDIA_ETAPA14,
        "pergunta_financeira": MENSAGEM_FINANCEIRO_ETAPA14,
        "email_invalido": MENSAGEM_EMAIL_INVALIDO_ETAPA14,
    }
    mensagem = montar_mensagem_etapa14(
        cliente_veterano,
        prefixos.get(tipo_tratamento),
    )
    return enviar_mensagem_etapa(
        cliente,
        phone_id,
        mensagem,
        id_etapa=14,
        evento_log="enviar_etapa14",
        tipo_tratamento=tipo_tratamento,
    )
```

### Passo 62 - Sender da etapa 15

Arquivo: `core/integrations/whatsapp/pywa_functions/pywa_senders/etapa15.py`

```python
from core.integrations.whatsapp.messages.etapa15_messages import (
    montar_botoes_etapa15,
    montar_mensagem_etapa15,
)
from core.integrations.whatsapp.pywa_functions.pywa_senders.sender_base import (
    enviar_mensagem_etapa,
)


def enviar_etapa15(
    cliente,
    phone_id,
    email,
    *,
    prefixo=None,
    tipo_tratamento=None,
):
    return enviar_mensagem_etapa(
        cliente,
        phone_id,
        montar_mensagem_etapa15(email, prefixo),
        id_etapa=15,
        evento_log="enviar_etapa15",
        botoes=montar_botoes_etapa15(),
        tipo_tratamento=tipo_tratamento,
    )
```

### Passo 63 - Sender da etapa 16

Arquivo: `core/integrations/whatsapp/pywa_functions/pywa_senders/etapa16.py`

```python
from core.integrations.whatsapp.messages.componentes_compartilhados import (
    CABECALHO_ETAPA16_TRIAGEM,
)
from core.integrations.whatsapp.messages.etapa16_messages import (
    montar_botoes_etapa16,
    montar_mensagem_etapa16,
)
from core.integrations.whatsapp.pywa_functions.pywa_senders.sender_base import (
    enviar_mensagem_etapa,
)


def enviar_etapa16(cliente, phone_id):
    return enviar_mensagem_etapa(
        cliente,
        phone_id,
        montar_mensagem_etapa16(),
        id_etapa=16,
        evento_log="enviar_etapa16",
        cabecalho=CABECALHO_ETAPA16_TRIAGEM,
        botoes=montar_botoes_etapa16(),
    )
```

### Passo 64 - Atualizar o helper de envio da triagem

Arquivo: `core/integrations/whatsapp/pywa_functions/pywa_senders/triagem_base.py`

```python
"""Contrato de envio compartilhado exclusivamente pelas etapas 17 a 22."""

from core.integrations.whatsapp.messages.componentes_compartilhados import (
    montar_texto_com_rodape,
)
from core.integrations.whatsapp.messages.triagem_componentes import (
    montar_botoes_triagem,
    montar_rodape_triagem,
)
from core.integrations.whatsapp.pywa_functions.pywa_senders.sender_base import (
    enviar_mensagem_etapa,
)


TIPO_TRATAMENTO_RESPOSTA_INVALIDA = "resposta_triagem_invalida"


def enviar_pergunta_triagem(
    cliente,
    phone_id,
    *,
    id_etapa,
    cabecalho,
    mensagem,
    tipo_tratamento=None,
):
    mensagem_completa = montar_texto_com_rodape(
        mensagem,
        montar_rodape_triagem(),
    )
    return enviar_mensagem_etapa(
        cliente,
        phone_id,
        mensagem_completa,
        id_etapa=id_etapa,
        evento_log=f"enviar_etapa{id_etapa}",
        cabecalho=cabecalho,
        botoes=montar_botoes_triagem(),
        tipo_tratamento=tipo_tratamento,
    )
```

### Passo 65 - Sender da etapa 17

Arquivo: `core/integrations/whatsapp/pywa_functions/pywa_senders/etapa17.py`

```python
from core.integrations.whatsapp.messages.etapa17_messages import (
    montar_cabecalho_etapa17,
    montar_mensagem_cliente_etapa17,
    montar_mensagem_dependente_etapa17,
)
from core.integrations.whatsapp.pywa_functions.pywa_senders.triagem_base import (
    enviar_pergunta_triagem,
)


def enviar_etapa17(cliente, phone_id, nome_dependente=None, prefixo=None):
    mensagem = (
        montar_mensagem_dependente_etapa17(nome_dependente, prefixo)
        if nome_dependente
        else montar_mensagem_cliente_etapa17(prefixo)
    )
    return enviar_pergunta_triagem(
        cliente,
        phone_id,
        id_etapa=17,
        cabecalho=montar_cabecalho_etapa17(),
        mensagem=mensagem,
        tipo_tratamento=("resposta_triagem_invalida" if prefixo else None),
    )
```

### Passo 66 - Sender da etapa 18

Arquivo: `core/integrations/whatsapp/pywa_functions/pywa_senders/etapa18.py`

```python
from core.integrations.whatsapp.messages.etapa18_messages import (
    montar_cabecalho_etapa18,
    montar_mensagem_cliente_etapa18,
    montar_mensagem_dependente_etapa18,
)
from core.integrations.whatsapp.pywa_functions.pywa_senders.triagem_base import enviar_pergunta_triagem


def enviar_etapa18(cliente, phone_id, nome_dependente=None, prefixo=None):
    mensagem = montar_mensagem_dependente_etapa18(nome_dependente, prefixo) if nome_dependente else montar_mensagem_cliente_etapa18(prefixo)
    return enviar_pergunta_triagem(cliente, phone_id, id_etapa=18, cabecalho=montar_cabecalho_etapa18(), mensagem=mensagem, tipo_tratamento=("resposta_triagem_invalida" if prefixo else None))
```

### Passo 67 - Sender da etapa 19

Arquivo: `core/integrations/whatsapp/pywa_functions/pywa_senders/etapa19.py`

```python
from core.integrations.whatsapp.messages.etapa19_messages import montar_cabecalho_etapa19, montar_mensagem_cliente_etapa19, montar_mensagem_dependente_etapa19
from core.integrations.whatsapp.pywa_functions.pywa_senders.triagem_base import enviar_pergunta_triagem


def enviar_etapa19(cliente, phone_id, nome_dependente=None, prefixo=None):
    mensagem = montar_mensagem_dependente_etapa19(nome_dependente, prefixo) if nome_dependente else montar_mensagem_cliente_etapa19(prefixo)
    return enviar_pergunta_triagem(cliente, phone_id, id_etapa=19, cabecalho=montar_cabecalho_etapa19(), mensagem=mensagem, tipo_tratamento=("resposta_triagem_invalida" if prefixo else None))
```

### Passo 68 - Sender da etapa 20

Arquivo: `core/integrations/whatsapp/pywa_functions/pywa_senders/etapa20.py`

```python
from core.integrations.whatsapp.messages.etapa20_messages import montar_cabecalho_etapa20, montar_mensagem_cliente_etapa20, montar_mensagem_dependente_etapa20
from core.integrations.whatsapp.pywa_functions.pywa_senders.triagem_base import enviar_pergunta_triagem


def enviar_etapa20(cliente, phone_id, nome_dependente=None, prefixo=None):
    mensagem = montar_mensagem_dependente_etapa20(nome_dependente, prefixo) if nome_dependente else montar_mensagem_cliente_etapa20(prefixo)
    return enviar_pergunta_triagem(cliente, phone_id, id_etapa=20, cabecalho=montar_cabecalho_etapa20(), mensagem=mensagem, tipo_tratamento=("resposta_triagem_invalida" if prefixo else None))
```

### Passo 69 - Sender da etapa 21

Arquivo: `core/integrations/whatsapp/pywa_functions/pywa_senders/etapa21.py`

```python
from core.integrations.whatsapp.messages.etapa21_messages import montar_cabecalho_etapa21, montar_mensagem_cliente_etapa21, montar_mensagem_dependente_etapa21
from core.integrations.whatsapp.pywa_functions.pywa_senders.triagem_base import enviar_pergunta_triagem


def enviar_etapa21(cliente, phone_id, nome_dependente=None, prefixo=None):
    mensagem = montar_mensagem_dependente_etapa21(nome_dependente, prefixo) if nome_dependente else montar_mensagem_cliente_etapa21(prefixo)
    return enviar_pergunta_triagem(cliente, phone_id, id_etapa=21, cabecalho=montar_cabecalho_etapa21(), mensagem=mensagem, tipo_tratamento=("resposta_triagem_invalida" if prefixo else None))
```

### Passo 70 - Sender da etapa 22

Arquivo: `core/integrations/whatsapp/pywa_functions/pywa_senders/etapa22.py`

```python
from core.integrations.whatsapp.messages.etapa22_messages import montar_cabecalho_etapa22, montar_mensagem_cliente_etapa22, montar_mensagem_dependente_etapa22
from core.integrations.whatsapp.pywa_functions.pywa_senders.triagem_base import enviar_pergunta_triagem


def enviar_etapa22(cliente, phone_id, nome_dependente=None, prefixo=None):
    mensagem = montar_mensagem_dependente_etapa22(nome_dependente, prefixo) if nome_dependente else montar_mensagem_cliente_etapa22(prefixo)
    return enviar_pergunta_triagem(cliente, phone_id, id_etapa=22, cabecalho=montar_cabecalho_etapa22(), mensagem=mensagem, tipo_tratamento=("resposta_triagem_invalida" if prefixo else None))
```

### Passo 71 - Sender de agendamento da etapa 23

Arquivo: `core/integrations/whatsapp/pywa_functions/pywa_senders/etapa23.py`

```python
from core.integrations.whatsapp.messages.etapa23_messages import (
    MENSAGEM_CONTEXTO_INVALIDO_ETAPA23,
    MENSAGEM_FINANCEIRO_ETAPA23,
    MENSAGEM_MIDIA_ETAPA23,
    montar_botoes_etapa23,
    montar_mensagem_etapa23,
)
from core.integrations.whatsapp.pywa_functions.pywa_senders.sender_base import enviar_mensagem_etapa


def enviar_etapa23(cliente, phone_id, link_agendamento, tipo_tratamento=None):
    prefixos = {
        "tipo_mensagem_nao_suportado": MENSAGEM_MIDIA_ETAPA23,
        "pergunta_financeira": MENSAGEM_FINANCEIRO_ETAPA23,
        "agendamento_nao_confirmado": MENSAGEM_CONTEXTO_INVALIDO_ETAPA23,
    }
    mensagem = montar_mensagem_etapa23(
        link_agendamento,
        prefixos.get(tipo_tratamento),
    )
    return enviar_mensagem_etapa(
        cliente,
        phone_id,
        mensagem,
        id_etapa=23,
        evento_log="enviar_etapa23",
        botoes=montar_botoes_etapa23(),
        tipo_tratamento=tipo_tratamento,
    )
```

### Passo 72 - Sender da mensagem final da etapa 24

Arquivo: `core/integrations/whatsapp/pywa_functions/pywa_senders/etapa24.py`

```python
from core.integrations.whatsapp.messages.etapa24_messages import montar_mensagem_etapa24
from core.integrations.whatsapp.pywa_functions.pywa_senders.sender_base import enviar_mensagem_etapa


def enviar_etapa24(cliente, phone_id):
    return enviar_mensagem_etapa(
        cliente,
        phone_id,
        montar_mensagem_etapa24(),
        id_etapa=24,
        evento_log="enviar_etapa24",
    )
```

## Fase 6 - Resolvers

### Passo 73 - Compartilhar apenas infraestrutura dos resolvers

Arquivo: `workers/worker_flow/response_flow/etapas/suporte_resolver.py`

```python
import logging

from core.logging_config import short_value
from workers.worker_flow.response_flow.etapas.validadores_universais.validador_financeiro import (
    validar_pergunta_financeira,
)
from workers.worker_flow.response_flow.etapas.validadores_universais.validador_midia import (
    validar_midia,
)
from workers.worker_flow.response_flow.transicoes.resolver_transicao import (
    anexar_transicao_ao_contexto_envio,
    resolver_destino_transicao,
)


logger = logging.getLogger("worker.resolver")

TIPO_TRATAMENTO_MIDIA = "tipo_mensagem_nao_suportado"
TIPO_TRATAMENTO_FINANCEIRO = "pergunta_financeira"

PREFIXO_MIDIA = "Ainda não reconhecemos mensagens com mídia, apenas texto."
PREFIXO_FINANCEIRO = (
    "Informações como valores são apresentadas no atendimento presencial "
    "após a aula *gratuita*."
)
PREFIXO_CONTEXTO = "Não consegui entender sua resposta."


def dados_destinatario(contexto):
    mensagem = contexto["mensagem_cliente_atual"]
    return mensagem["cliente_telefone"], mensagem["id_phone_unidade"]


def detectar_tratamento_universal(contexto):
    if validar_midia(contexto.get("tipo_mensagem_atual")):
        return TIPO_TRATAMENTO_MIDIA

    if validar_pergunta_financeira(
        contexto.get("texto_cliente_atual") or ""
    ):
        return TIPO_TRATAMENTO_FINANCEIRO

    return None


def anexar_evento(
    contexto,
    contexto_envio,
    evento,
    destinos_esperados,
):
    destino = resolver_destino_transicao(
        contexto,
        evento,
        destinos_esperados=set(destinos_esperados),
    )
    return anexar_transicao_ao_contexto_envio(
        contexto,
        contexto_envio,
        evento,
        destino,
    )


def logar_tratamento(contexto, motivo):
    mensagem = contexto["mensagem_cliente_atual"]
    logger.info(
        "resposta_cliente_tratamento | motivo=%s acao=tratar_sem_avancar "
        "id_conversa=%s id_mensagem_fila=%s cliente=%s "
        "phone_number_id=%s etapa_cliente=%s",
        motivo,
        contexto["id_conversa"],
        mensagem["id_mensagem_fila"],
        short_value(mensagem["cliente_telefone"]),
        short_value(mensagem["id_phone_unidade"]),
        contexto["id_etapa_cliente"],
    )
```

> Este helper não conhece eventos nem IDs de destino. Essa decisão continua
> visível em cada `resolver_etapaN.py`.

### Passo 74 - Resolver da etapa 1

Arquivo: `workers/worker_flow/response_flow/etapas/resolver_etapa1.py`

```python
from core.integrations.whatsapp.pywa_functions.pywa_senders.etapa1 import enviar_etapa1
from core.integrations.whatsapp.pywa_functions.pywa_senders.etapa2 import enviar_etapa2
from core.integrations.whatsapp.pywa_functions.pywa_senders.etapa4 import enviar_etapa4
from workers.worker_flow.response_flow.etapas.suporte_resolver import (
    anexar_evento,
    dados_destinatario,
    detectar_tratamento_universal,
    logar_tratamento,
)
from workers.worker_flow.response_flow.etapas.validadores_contexto.valida_etapa1 import (
    TIPO_TRATAMENTO_CONTEXTO_INVALIDO,
    validar_etapa1,
)
from workers.worker_flow.response_flow.transicoes.eventos import (
    ETAPA_2_NOVO_NOME_VETERANO,
    ETAPA_4_DESTINO_VETERANO,
    EVENTO_ATUALIZAR_NOME,
    EVENTO_NOVO_ATENDIMENTO,
)


def resolve_etapa1(contexto):
    cliente, phone_id = dados_destinatario(contexto)
    nome = contexto["nome_cliente"]
    tratamento = detectar_tratamento_universal(contexto)

    if contexto.get("id_etapa_atual") is None:
        return enviar_etapa1(cliente, phone_id, nome, tratamento)

    if tratamento:
        logar_tratamento(contexto, tratamento)
        return enviar_etapa1(cliente, phone_id, nome, tratamento)

    evento = validar_etapa1(contexto.get("texto_cliente_atual"))
    if evento is None:
        logar_tratamento(contexto, TIPO_TRATAMENTO_CONTEXTO_INVALIDO)
        return enviar_etapa1(
            cliente,
            phone_id,
            nome,
            TIPO_TRATAMENTO_CONTEXTO_INVALIDO,
        )

    if evento == EVENTO_ATUALIZAR_NOME:
        envio = enviar_etapa2(cliente, phone_id)
        destinos = {ETAPA_2_NOVO_NOME_VETERANO}
    else:
        envio = enviar_etapa4(cliente, phone_id, nome)
        destinos = {ETAPA_4_DESTINO_VETERANO}

    return anexar_evento(contexto, envio, evento, destinos)
```

### Passo 75 - Resolver da etapa 2

Arquivo: `workers/worker_flow/response_flow/etapas/resolver_etapa2.py`

```python
from core.integrations.whatsapp.pywa_functions.pywa_senders.etapa2 import enviar_etapa2
from core.integrations.whatsapp.pywa_functions.pywa_senders.etapa3 import enviar_etapa3
from workers.worker_flow.response_flow.etapas.suporte_resolver import anexar_evento, dados_destinatario, detectar_tratamento_universal, logar_tratamento
from workers.worker_flow.response_flow.etapas.validadores_universais.validador_nome import TIPO_TRATAMENTO_NOME_INVALIDO, validar_nome_cliente
from workers.worker_flow.response_flow.transicoes.eventos import ETAPA_3_CONFIRMACAO_NOME_CLIENTE, EVENTO_NOME_CLIENTE_INFORMADO


def resolve_etapa2(contexto):
    cliente, phone_id = dados_destinatario(contexto)
    tratamento = detectar_tratamento_universal(contexto)
    if tratamento:
        logar_tratamento(contexto, tratamento)
        return enviar_etapa2(cliente, phone_id, tratamento)

    resultado = validar_nome_cliente(contexto.get("texto_cliente_atual"))
    if not resultado.valido:
        logar_tratamento(contexto, TIPO_TRATAMENTO_NOME_INVALIDO)
        return enviar_etapa2(cliente, phone_id, TIPO_TRATAMENTO_NOME_INVALIDO)

    envio = enviar_etapa3(cliente, phone_id, resultado.primeiro_nome)
    envio["nome_cliente_candidato"] = resultado.primeiro_nome
    return anexar_evento(
        contexto,
        envio,
        EVENTO_NOME_CLIENTE_INFORMADO,
        {ETAPA_3_CONFIRMACAO_NOME_CLIENTE},
    )
```

### Passo 76 - Resolver da etapa 3

Arquivo: `workers/worker_flow/response_flow/etapas/resolver_etapa3.py`

```python
from core.integrations.whatsapp.pywa_functions.pywa_senders.etapa2 import enviar_etapa2
from core.integrations.whatsapp.pywa_functions.pywa_senders.etapa3 import enviar_etapa3
from core.integrations.whatsapp.pywa_functions.pywa_senders.etapa4 import enviar_etapa4
from core.integrations.whatsapp.pywa_functions.pywa_senders.etapa5 import enviar_etapa5
from core.integrations.whatsapp.pywa_functions.pywa_senders.etapa6 import enviar_etapa6
from core.integrations.whatsapp.pywa_functions.saudacao import obter_saudacao_por_horario
from workers.worker_flow.response_flow.etapas.suporte_resolver import anexar_evento, dados_destinatario, detectar_tratamento_universal, logar_tratamento
from workers.worker_flow.response_flow.etapas.validadores_contexto.valida_etapa3 import TIPO_TRATAMENTO_CONFIRMACAO_INVALIDA, validar_etapa3
from workers.worker_flow.response_flow.transicoes.eventos import (
    ETAPA_2_NOVO_NOME_VETERANO, ETAPA_4_DESTINO_VETERANO,
    ETAPA_5_NOME_CLIENTE_NOVATO, ETAPA_6_DESTINO_NOVATO,
    EVENTO_NOME_CLIENTE_CONFIRMADO_NOVATO,
    EVENTO_NOME_CLIENTE_CONFIRMADO_VETERANO,
    EVENTO_NOME_CLIENTE_REJEITADO_NOVATO,
    EVENTO_NOME_CLIENTE_REJEITADO_VETERANO,
)


def resolve_etapa3(contexto):
    cliente, phone_id = dados_destinatario(contexto)
    nome = contexto["nome_cliente_candidato"]
    veterano = contexto["candidato_cliente_veterano"]
    tratamento = detectar_tratamento_universal(contexto)
    if tratamento:
        logar_tratamento(contexto, tratamento)
        return enviar_etapa3(cliente, phone_id, nome, tratamento)

    evento = validar_etapa3(
        contexto.get("texto_cliente_atual"),
        cliente_veterano=veterano,
    )
    if evento is None:
        logar_tratamento(contexto, TIPO_TRATAMENTO_CONFIRMACAO_INVALIDA)
        return enviar_etapa3(
            cliente,
            phone_id,
            nome,
            TIPO_TRATAMENTO_CONFIRMACAO_INVALIDA,
        )

    if evento == EVENTO_NOME_CLIENTE_CONFIRMADO_VETERANO:
        envio = enviar_etapa4(cliente, phone_id, nome)
        destinos = {ETAPA_4_DESTINO_VETERANO}
        envio["nome_cliente_candidato"] = nome
    elif evento == EVENTO_NOME_CLIENTE_REJEITADO_VETERANO:
        envio = enviar_etapa2(cliente, phone_id)
        destinos = {ETAPA_2_NOVO_NOME_VETERANO}
    elif evento == EVENTO_NOME_CLIENTE_CONFIRMADO_NOVATO:
        envio = enviar_etapa6(cliente, phone_id, nome)
        destinos = {ETAPA_6_DESTINO_NOVATO}
        envio["nome_cliente_candidato"] = nome
    else:
        envio = enviar_etapa5(
            cliente,
            phone_id,
            obter_saudacao_por_horario(),
            contexto["nome_unidade"],
            variacao="nome_rejeitado",
        )
        destinos = {ETAPA_5_NOME_CLIENTE_NOVATO}

    return anexar_evento(contexto, envio, evento, destinos)
```

### Passo 77 - Resolver da etapa 4

Arquivo: `workers/worker_flow/response_flow/etapas/resolver_etapa4.py`

```python
from core.integrations.whatsapp.pywa_functions.pywa_senders.etapa4 import enviar_etapa4
from core.integrations.whatsapp.pywa_functions.pywa_senders.etapa7 import enviar_etapa7
from core.integrations.whatsapp.pywa_functions.pywa_senders.etapa9 import enviar_etapa9
from workers.worker_flow.response_flow.etapas.suporte_resolver import anexar_evento, dados_destinatario, detectar_tratamento_universal, logar_tratamento
from workers.worker_flow.response_flow.etapas.validadores_universais.validador_destino_atendimento import TIPO_TRATAMENTO_CONTEXTO_INVALIDO, validar_destino_atendimento
from workers.worker_flow.response_flow.transicoes.eventos import ETAPA_7_NOME_DEPENDENTE, ETAPA_9_IDADE_ALUNO, EVENTO_PARA_MIM


def resolve_etapa4(contexto):
    cliente, phone_id = dados_destinatario(contexto)
    tratamento = detectar_tratamento_universal(contexto)
    if tratamento:
        logar_tratamento(contexto, tratamento)
        return enviar_etapa4(cliente, phone_id, contexto["nome_cliente"], tratamento)

    evento = validar_destino_atendimento(contexto.get("texto_cliente_atual"))
    if evento is None:
        logar_tratamento(contexto, TIPO_TRATAMENTO_CONTEXTO_INVALIDO)
        return enviar_etapa4(cliente, phone_id, contexto["nome_cliente"], TIPO_TRATAMENTO_CONTEXTO_INVALIDO)

    if evento == EVENTO_PARA_MIM:
        envio = enviar_etapa9(cliente, phone_id)
        destinos = {ETAPA_9_IDADE_ALUNO}
    else:
        envio = enviar_etapa7(cliente, phone_id)
        destinos = {ETAPA_7_NOME_DEPENDENTE}

    return anexar_evento(contexto, envio, evento, destinos)
```

### Passo 78 - Resolver da etapa 5

Arquivo: `workers/worker_flow/response_flow/etapas/resolver_etapa5.py`

```python
from core.integrations.whatsapp.pywa_functions.pywa_senders.etapa3 import enviar_etapa3
from core.integrations.whatsapp.pywa_functions.pywa_senders.etapa5 import enviar_etapa5
from core.integrations.whatsapp.pywa_functions.saudacao import obter_saudacao_por_horario
from workers.worker_flow.response_flow.etapas.suporte_resolver import anexar_evento, dados_destinatario, detectar_tratamento_universal, logar_tratamento
from workers.worker_flow.response_flow.etapas.validadores_universais.validador_nome import TIPO_TRATAMENTO_NOME_INVALIDO, validar_nome_cliente
from workers.worker_flow.response_flow.transicoes.eventos import ETAPA_3_CONFIRMACAO_NOME_CLIENTE, EVENTO_NOME_CLIENTE_INFORMADO


def resolve_etapa5(contexto):
    cliente, phone_id = dados_destinatario(contexto)
    tratamento = detectar_tratamento_universal(contexto)

    if contexto.get("id_etapa_atual") is None:
        return enviar_etapa5(
            cliente,
            phone_id,
            obter_saudacao_por_horario(),
            contexto["nome_unidade"],
            inicial=True,
            tipo_tratamento=tratamento,
        )

    if tratamento:
        logar_tratamento(contexto, tratamento)
        return enviar_etapa5(cliente, phone_id, obter_saudacao_por_horario(), contexto["nome_unidade"], tipo_tratamento=tratamento)

    resultado = validar_nome_cliente(contexto.get("texto_cliente_atual"))
    if not resultado.valido:
        logar_tratamento(contexto, TIPO_TRATAMENTO_NOME_INVALIDO)
        return enviar_etapa5(cliente, phone_id, obter_saudacao_por_horario(), contexto["nome_unidade"], tipo_tratamento=TIPO_TRATAMENTO_NOME_INVALIDO)

    envio = enviar_etapa3(cliente, phone_id, resultado.primeiro_nome)
    envio["nome_cliente_candidato"] = resultado.primeiro_nome
    return anexar_evento(contexto, envio, EVENTO_NOME_CLIENTE_INFORMADO, {ETAPA_3_CONFIRMACAO_NOME_CLIENTE})
```

### Passo 79 - Resolver da etapa 6

Arquivo: `workers/worker_flow/response_flow/etapas/resolver_etapa6.py`

```python
from core.integrations.whatsapp.pywa_functions.pywa_senders.etapa6 import enviar_etapa6
from core.integrations.whatsapp.pywa_functions.pywa_senders.etapa7 import enviar_etapa7
from core.integrations.whatsapp.pywa_functions.pywa_senders.etapa9 import enviar_etapa9
from workers.worker_flow.response_flow.etapas.suporte_resolver import anexar_evento, dados_destinatario, detectar_tratamento_universal, logar_tratamento
from workers.worker_flow.response_flow.etapas.validadores_universais.validador_destino_atendimento import TIPO_TRATAMENTO_CONTEXTO_INVALIDO, validar_destino_atendimento
from workers.worker_flow.response_flow.transicoes.eventos import ETAPA_7_NOME_DEPENDENTE, ETAPA_9_IDADE_ALUNO, EVENTO_PARA_MIM


def resolve_etapa6(contexto):
    cliente, phone_id = dados_destinatario(contexto)
    tratamento = detectar_tratamento_universal(contexto)
    if tratamento:
        logar_tratamento(contexto, tratamento)
        return enviar_etapa6(cliente, phone_id, contexto["nome_cliente"], tratamento)

    evento = validar_destino_atendimento(contexto.get("texto_cliente_atual"))
    if evento is None:
        logar_tratamento(contexto, TIPO_TRATAMENTO_CONTEXTO_INVALIDO)
        return enviar_etapa6(cliente, phone_id, contexto["nome_cliente"], TIPO_TRATAMENTO_CONTEXTO_INVALIDO)

    if evento == EVENTO_PARA_MIM:
        envio = enviar_etapa9(cliente, phone_id)
        destinos = {ETAPA_9_IDADE_ALUNO}
    else:
        envio = enviar_etapa7(cliente, phone_id)
        destinos = {ETAPA_7_NOME_DEPENDENTE}
    return anexar_evento(contexto, envio, evento, destinos)
```

### Passo 80 - Resolver da etapa 7

Arquivo: `workers/worker_flow/response_flow/etapas/resolver_etapa7.py`

```python
from core.integrations.whatsapp.pywa_functions.pywa_senders.etapa7 import enviar_etapa7
from core.integrations.whatsapp.pywa_functions.pywa_senders.etapa8 import enviar_etapa8
from workers.worker_flow.response_flow.etapas.suporte_resolver import anexar_evento, dados_destinatario, detectar_tratamento_universal, logar_tratamento
from workers.worker_flow.response_flow.etapas.validadores_universais.validador_nome import TIPO_TRATAMENTO_NOME_INVALIDO, validar_nome_cliente
from workers.worker_flow.response_flow.transicoes.eventos import ETAPA_8_CONFIRMACAO_NOME_DEPENDENTE, EVENTO_NOME_DEPENDENTE_INFORMADO


def resolve_etapa7(contexto):
    cliente, phone_id = dados_destinatario(contexto)
    tratamento = detectar_tratamento_universal(contexto)
    if tratamento:
        logar_tratamento(contexto, tratamento)
        return enviar_etapa7(cliente, phone_id, tratamento)

    resultado = validar_nome_cliente(contexto.get("texto_cliente_atual"))
    if not resultado.valido:
        logar_tratamento(contexto, TIPO_TRATAMENTO_NOME_INVALIDO)
        return enviar_etapa7(cliente, phone_id, TIPO_TRATAMENTO_NOME_INVALIDO)

    envio = enviar_etapa8(cliente, phone_id, resultado.primeiro_nome)
    envio["nome_dependente_candidato"] = resultado.primeiro_nome
    return anexar_evento(
        contexto,
        envio,
        EVENTO_NOME_DEPENDENTE_INFORMADO,
        {ETAPA_8_CONFIRMACAO_NOME_DEPENDENTE},
    )
```

### Passo 81 - Resolver da etapa 8

Arquivo: `workers/worker_flow/response_flow/etapas/resolver_etapa8.py`

```python
from core.integrations.whatsapp.pywa_functions.pywa_senders.etapa7 import enviar_etapa7
from core.integrations.whatsapp.pywa_functions.pywa_senders.etapa8 import enviar_etapa8
from core.integrations.whatsapp.pywa_functions.pywa_senders.etapa9 import enviar_etapa9
from workers.worker_flow.response_flow.etapas.suporte_resolver import anexar_evento, dados_destinatario, detectar_tratamento_universal, logar_tratamento
from workers.worker_flow.response_flow.etapas.validadores_contexto.valida_etapa8 import TIPO_TRATAMENTO_CONFIRMACAO_INVALIDA, validar_etapa8
from workers.worker_flow.response_flow.transicoes.eventos import ETAPA_7_NOME_DEPENDENTE, ETAPA_9_IDADE_ALUNO, EVENTO_NOME_DEPENDENTE_CONFIRMADO


def resolve_etapa8(contexto):
    cliente, phone_id = dados_destinatario(contexto)
    nome = contexto["nome_dependente_candidato"]
    tratamento = detectar_tratamento_universal(contexto)
    if tratamento:
        logar_tratamento(contexto, tratamento)
        return enviar_etapa8(cliente, phone_id, nome, tratamento)

    evento = validar_etapa8(contexto.get("texto_cliente_atual"))
    if evento is None:
        logar_tratamento(contexto, TIPO_TRATAMENTO_CONFIRMACAO_INVALIDA)
        return enviar_etapa8(cliente, phone_id, nome, TIPO_TRATAMENTO_CONFIRMACAO_INVALIDA)

    if evento == EVENTO_NOME_DEPENDENTE_CONFIRMADO:
        envio = enviar_etapa9(cliente, phone_id, nome_dependente=nome)
        envio["nome_dependente_candidato"] = nome
        destinos = {ETAPA_9_IDADE_ALUNO}
    else:
        envio = enviar_etapa7(cliente, phone_id)
        destinos = {ETAPA_7_NOME_DEPENDENTE}

    return anexar_evento(contexto, envio, evento, destinos)
```

### Passo 82 - Resolver da etapa 9

Arquivo: `workers/worker_flow/response_flow/etapas/resolver_etapa9.py`

```python
from core.integrations.whatsapp.pywa_functions.pywa_senders.etapa9 import (
    enviar_etapa9,
    enviar_etapa9_cliente_menor_18,
    enviar_etapa9_dependente_abaixo_minimo,
    enviar_etapa9_idade_acima_99,
)
from core.integrations.whatsapp.pywa_functions.pywa_senders.etapa10 import (
    enviar_etapa10_confirmacao,
)
from workers.worker_flow.response_flow.etapas.suporte_resolver import anexar_evento, dados_destinatario, detectar_tratamento_universal, logar_tratamento
from workers.worker_flow.response_flow.etapas.validadores_contexto.valida_etapa9 import (
    obter_idade_minima_dependente,
    validar_etapa9,
)
from workers.worker_flow.response_flow.transicoes.eventos import ETAPA_10_CONFIRMACAO_IDADE, EVENTO_IDADE_INFORMADA


def resolve_etapa9(contexto):
    cliente, phone_id = dados_destinatario(contexto)
    nome_dependente = contexto.get("nome_dependente")
    tratamento = detectar_tratamento_universal(contexto)
    if tratamento:
        logar_tratamento(contexto, tratamento)
        return enviar_etapa9(cliente, phone_id, nome_dependente=nome_dependente, tipo_tratamento=tratamento)

    resultado = validar_etapa9(contexto.get("texto_cliente_atual"))
    if not resultado.valida and not resultado.acima_limite:
        logar_tratamento(contexto, resultado.motivo)
        return enviar_etapa9(cliente, phone_id, nome_dependente=nome_dependente, tipo_tratamento="idade_invalida")

    # Faixas que encerram o atendimento têm prioridade sobre a confirmação.
    if resultado.acima_limite:
        return enviar_etapa9_idade_acima_99(
            cliente,
            phone_id,
            contexto.get("numero_comercial_unidade"),
        )

    idade = resultado.idade
    if contexto.get("status_dependente"):
        idade_minima = obter_idade_minima_dependente(
            contexto.get("bpa_ativo_unidade")
        )
        if idade < idade_minima:
            return enviar_etapa9_dependente_abaixo_minimo(
                cliente,
                phone_id,
                nome_dependente,
                idade_minima,
            )
    elif idade < 18:
        return enviar_etapa9_cliente_menor_18(cliente, phone_id)

    envio = enviar_etapa10_confirmacao(
        cliente,
        phone_id,
        idade,
        nome_dependente=nome_dependente,
    )
    envio["idade_aluno_candidata"] = idade
    return anexar_evento(
        contexto,
        envio,
        EVENTO_IDADE_INFORMADA,
        {ETAPA_10_CONFIRMACAO_IDADE},
    )
```

### Passo 83 - Resolver da etapa 10

Arquivo: `workers/worker_flow/response_flow/etapas/resolver_etapa10.py`

```python
from core.integrations.whatsapp.messages.etapa10_messages import (
    montar_mensagem_contexto_invalido_etapa10,
    montar_mensagem_financeiro_etapa10,
    montar_mensagem_midia_etapa10,
)
from core.integrations.whatsapp.pywa_functions.pywa_senders.etapa9 import enviar_etapa9
from core.integrations.whatsapp.pywa_functions.pywa_senders.etapa10 import (
    enviar_etapa10_confirmacao,
)
from core.integrations.whatsapp.pywa_functions.pywa_senders.etapa11 import enviar_etapa11
from workers.worker_flow.response_flow.etapas.suporte_resolver import anexar_evento, dados_destinatario, detectar_tratamento_universal, logar_tratamento
from workers.worker_flow.response_flow.etapas.validadores_contexto.valida_etapa10 import TIPO_TRATAMENTO_CONFIRMACAO_INVALIDA, validar_etapa10
from workers.worker_flow.response_flow.transicoes.eventos import ETAPA_9_IDADE_ALUNO, ETAPA_11_OFERTA_AULA, EVENTO_IDADE_CONFIRMADA


def resolve_etapa10(contexto):
    cliente, phone_id = dados_destinatario(contexto)
    idade = contexto["idade_aluno_candidata"]
    nome_dependente = contexto.get("nome_dependente")
    tratamento = detectar_tratamento_universal(contexto)
    if tratamento:
        prefixo = montar_mensagem_midia_etapa10() if tratamento == "tipo_mensagem_nao_suportado" else montar_mensagem_financeiro_etapa10()
        logar_tratamento(contexto, tratamento)
        return enviar_etapa10_confirmacao(cliente, phone_id, idade, nome_dependente=nome_dependente, prefixo=prefixo, tipo_tratamento=tratamento)

    evento = validar_etapa10(contexto.get("texto_cliente_atual"))
    if evento is None:
        logar_tratamento(contexto, TIPO_TRATAMENTO_CONFIRMACAO_INVALIDA)
        return enviar_etapa10_confirmacao(cliente, phone_id, idade, nome_dependente=nome_dependente, prefixo=montar_mensagem_contexto_invalido_etapa10(), tipo_tratamento=TIPO_TRATAMENTO_CONFIRMACAO_INVALIDA)

    if evento != EVENTO_IDADE_CONFIRMADA:
        envio = enviar_etapa9(cliente, phone_id, nome_dependente=nome_dependente)
        return anexar_evento(contexto, envio, evento, {ETAPA_9_IDADE_ALUNO})

    envio = enviar_etapa11(
        cliente,
        phone_id,
        contexto["nome_cliente"],
        nome_dependente,
        status_dependente=bool(contexto.get("status_dependente")),
        cliente_veterano=bool(contexto.get("cliente_veterano")),
    )
    envio["idade_aluno_candidata"] = idade
    return anexar_evento(
        contexto,
        envio,
        EVENTO_IDADE_CONFIRMADA,
        {ETAPA_11_OFERTA_AULA},
    )
```

### Passo 84 - Resolver da etapa 11

Arquivo: `workers/worker_flow/response_flow/etapas/resolver_etapa11.py`

```python
from core.integrations.whatsapp.pywa_functions.pywa_senders.etapa11 import enviar_etapa11
from core.integrations.whatsapp.pywa_functions.pywa_senders.etapa12 import enviar_etapa12
from core.integrations.whatsapp.pywa_functions.pywa_senders.etapa14 import enviar_etapa14
from workers.worker_flow.response_flow.etapas.suporte_resolver import PREFIXO_CONTEXTO, PREFIXO_FINANCEIRO, PREFIXO_MIDIA, anexar_evento, dados_destinatario, detectar_tratamento_universal, logar_tratamento
from workers.worker_flow.response_flow.etapas.validadores_contexto.valida_etapa11 import TIPO_TRATAMENTO_CONTEXTO_INVALIDO, validar_etapa11
from workers.worker_flow.response_flow.transicoes.eventos import ETAPA_12_OFERTA_ADIADA, ETAPA_14_EMAIL, EVENTO_OFERTA_ACEITA


def resolve_etapa11(contexto):
    cliente, phone_id = dados_destinatario(contexto)
    tratamento = detectar_tratamento_universal(contexto)
    prefixos = {
        "tipo_mensagem_nao_suportado": PREFIXO_MIDIA,
        "pergunta_financeira": PREFIXO_FINANCEIRO,
    }
    if tratamento:
        logar_tratamento(contexto, tratamento)
        return _repetir_oferta(contexto, cliente, phone_id, prefixos[tratamento], tratamento)

    evento = validar_etapa11(contexto.get("texto_cliente_atual"))
    if evento is None:
        logar_tratamento(contexto, TIPO_TRATAMENTO_CONTEXTO_INVALIDO)
        return _repetir_oferta(contexto, cliente, phone_id, PREFIXO_CONTEXTO, TIPO_TRATAMENTO_CONTEXTO_INVALIDO)

    if evento == EVENTO_OFERTA_ACEITA:
        envio = enviar_etapa14(cliente, phone_id, contexto["cliente_veterano"])
        destinos = {ETAPA_14_EMAIL}
    else:
        envio = enviar_etapa12(cliente, phone_id, contexto["link_instagram_unidade"])
        destinos = {ETAPA_12_OFERTA_ADIADA}
    return anexar_evento(contexto, envio, evento, destinos)


def _repetir_oferta(contexto, cliente, phone_id, prefixo, tratamento):
    return enviar_etapa11(
        cliente,
        phone_id,
        contexto["nome_cliente"],
        contexto.get("nome_dependente"),
        status_dependente=bool(contexto.get("status_dependente")),
        cliente_veterano=bool(contexto.get("cliente_veterano")),
        prefixo=prefixo,
        tipo_tratamento=tratamento,
    )
```

### Passo 85 - Resolver da etapa 12

Arquivo: `workers/worker_flow/response_flow/etapas/resolver_etapa12.py`

```python
from core.integrations.whatsapp.pywa_functions.pywa_senders.etapa13 import enviar_etapa13
from workers.worker_flow.response_flow.etapas.suporte_resolver import anexar_evento, dados_destinatario
from workers.worker_flow.response_flow.transicoes.eventos import ETAPA_13_RETORNO_OFERTA, EVENTO_CLIENTE_RETORNOU


def resolve_etapa12(contexto):
    cliente, phone_id = dados_destinatario(contexto)
    envio = enviar_etapa13(
        cliente,
        phone_id,
        contexto["nome_cliente"],
        contexto.get("nome_dependente"),
    )
    return anexar_evento(
        contexto,
        envio,
        EVENTO_CLIENTE_RETORNOU,
        {ETAPA_13_RETORNO_OFERTA},
    )
```

### Passo 86 - Resolver da etapa 13

Arquivo: `workers/worker_flow/response_flow/etapas/resolver_etapa13.py`

```python
from core.integrations.whatsapp.pywa_functions.pywa_senders.etapa12 import enviar_etapa12
from core.integrations.whatsapp.pywa_functions.pywa_senders.etapa13 import enviar_etapa13
from core.integrations.whatsapp.pywa_functions.pywa_senders.etapa14 import enviar_etapa14
from workers.worker_flow.response_flow.etapas.suporte_resolver import PREFIXO_CONTEXTO, PREFIXO_FINANCEIRO, PREFIXO_MIDIA, anexar_evento, dados_destinatario, detectar_tratamento_universal, logar_tratamento
from workers.worker_flow.response_flow.etapas.validadores_contexto.valida_etapa13 import TIPO_TRATAMENTO_CONTEXTO_INVALIDO, validar_etapa13
from workers.worker_flow.response_flow.transicoes.eventos import ETAPA_12_OFERTA_ADIADA, ETAPA_14_EMAIL, EVENTO_RETORNO_CONFIRMADO


def resolve_etapa13(contexto):
    cliente, phone_id = dados_destinatario(contexto)
    tratamento = detectar_tratamento_universal(contexto)
    prefixos = {
        "tipo_mensagem_nao_suportado": PREFIXO_MIDIA,
        "pergunta_financeira": PREFIXO_FINANCEIRO,
    }
    if tratamento:
        logar_tratamento(contexto, tratamento)
        return enviar_etapa13(cliente, phone_id, contexto["nome_cliente"], contexto.get("nome_dependente"), prefixo=prefixos[tratamento], tipo_tratamento=tratamento)

    evento = validar_etapa13(contexto.get("texto_cliente_atual"))
    if evento is None:
        logar_tratamento(contexto, TIPO_TRATAMENTO_CONTEXTO_INVALIDO)
        return enviar_etapa13(cliente, phone_id, contexto["nome_cliente"], contexto.get("nome_dependente"), prefixo=PREFIXO_CONTEXTO, tipo_tratamento=TIPO_TRATAMENTO_CONTEXTO_INVALIDO)

    if evento == EVENTO_RETORNO_CONFIRMADO:
        envio = enviar_etapa14(cliente, phone_id, contexto["cliente_veterano"])
        destinos = {ETAPA_14_EMAIL}
    else:
        envio = enviar_etapa12(cliente, phone_id, contexto["link_instagram_unidade"])
        destinos = {ETAPA_12_OFERTA_ADIADA}
    return anexar_evento(contexto, envio, evento, destinos)
```

### Passo 87 - Resolver da etapa 14

Arquivo: `workers/worker_flow/response_flow/etapas/resolver_etapa14.py`

```python
from core.integrations.whatsapp.pywa_functions.pywa_senders.etapa14 import enviar_etapa14
from core.integrations.whatsapp.pywa_functions.pywa_senders.etapa15 import enviar_etapa15
from workers.worker_flow.response_flow.etapas.suporte_resolver import anexar_evento, dados_destinatario, detectar_tratamento_universal, logar_tratamento
from workers.worker_flow.response_flow.etapas.validadores_contexto.valida_etapa14 import TIPO_TRATAMENTO_EMAIL_INVALIDO, validar_etapa14
from workers.worker_flow.response_flow.transicoes.eventos import ETAPA_15_CONFIRMACAO_EMAIL, EVENTO_EMAIL_INFORMADO


def resolve_etapa14(contexto):
    cliente, phone_id = dados_destinatario(contexto)
    tratamento = detectar_tratamento_universal(contexto)
    if tratamento:
        logar_tratamento(contexto, tratamento)
        return enviar_etapa14(cliente, phone_id, contexto["cliente_veterano"], tratamento)

    resultado = validar_etapa14(contexto.get("texto_cliente_atual"))
    if not resultado.valido:
        logar_tratamento(contexto, TIPO_TRATAMENTO_EMAIL_INVALIDO)
        return enviar_etapa14(cliente, phone_id, contexto["cliente_veterano"], TIPO_TRATAMENTO_EMAIL_INVALIDO)

    envio = enviar_etapa15(cliente, phone_id, resultado.email)
    envio["email_cliente_candidato"] = resultado.email
    return anexar_evento(
        contexto,
        envio,
        EVENTO_EMAIL_INFORMADO,
        {ETAPA_15_CONFIRMACAO_EMAIL},
    )
```

### Passo 88 - Resolver da etapa 15

Arquivo: `workers/worker_flow/response_flow/etapas/resolver_etapa15.py`

```python
from core.integrations.whatsapp.pywa_functions.pywa_senders.etapa14 import enviar_etapa14
from core.integrations.whatsapp.pywa_functions.pywa_senders.etapa15 import enviar_etapa15
from core.integrations.whatsapp.pywa_functions.pywa_senders.etapa16 import enviar_etapa16
from workers.worker_flow.response_flow.etapas.suporte_resolver import PREFIXO_CONTEXTO, PREFIXO_FINANCEIRO, PREFIXO_MIDIA, anexar_evento, dados_destinatario, detectar_tratamento_universal, logar_tratamento
from workers.worker_flow.response_flow.etapas.validadores_contexto.valida_etapa15 import TIPO_TRATAMENTO_CONFIRMACAO_INVALIDA, validar_etapa15
from workers.worker_flow.response_flow.transicoes.eventos import ETAPA_14_EMAIL, ETAPA_16_INTRODUCAO_TRIAGEM, EVENTO_EMAIL_CONFIRMADO


def resolve_etapa15(contexto):
    cliente, phone_id = dados_destinatario(contexto)
    email = contexto["email_cliente_candidato"]
    tratamento = detectar_tratamento_universal(contexto)
    prefixos = {
        "tipo_mensagem_nao_suportado": PREFIXO_MIDIA,
        "pergunta_financeira": PREFIXO_FINANCEIRO,
    }
    if tratamento:
        logar_tratamento(contexto, tratamento)
        return enviar_etapa15(cliente, phone_id, email, prefixo=prefixos[tratamento], tipo_tratamento=tratamento)

    evento = validar_etapa15(contexto.get("texto_cliente_atual"))
    if evento is None:
        logar_tratamento(contexto, TIPO_TRATAMENTO_CONFIRMACAO_INVALIDA)
        return enviar_etapa15(cliente, phone_id, email, prefixo=PREFIXO_CONTEXTO, tipo_tratamento=TIPO_TRATAMENTO_CONFIRMACAO_INVALIDA)

    if evento == EVENTO_EMAIL_CONFIRMADO:
        envio = enviar_etapa16(cliente, phone_id)
        envio["email_cliente_candidato"] = email
        destinos = {ETAPA_16_INTRODUCAO_TRIAGEM}
    else:
        envio = enviar_etapa14(cliente, phone_id, contexto["cliente_veterano"])
        destinos = {ETAPA_14_EMAIL}
    return anexar_evento(contexto, envio, evento, destinos)
```

### Passo 89 - Resolver da etapa 16

Arquivo: `workers/worker_flow/response_flow/etapas/resolver_etapa16.py`

```python
from core.integrations.whatsapp.pywa_functions.pywa_senders.etapa17 import enviar_etapa17
from workers.worker_flow.response_flow.etapas.suporte_resolver import anexar_evento, dados_destinatario
from workers.worker_flow.response_flow.transicoes.eventos import ETAPA_17_TRIAGEM_PERGUNTA_1, EVENTO_TRIAGEM_INICIADA


def resolve_etapa16(contexto):
    cliente, phone_id = dados_destinatario(contexto)
    envio = enviar_etapa17(
        cliente,
        phone_id,
        contexto.get("nome_dependente"),
    )
    return anexar_evento(
        contexto,
        envio,
        EVENTO_TRIAGEM_INICIADA,
        {ETAPA_17_TRIAGEM_PERGUNTA_1},
    )
```

### Passo 90 - Compartilhar o ciclo das seis perguntas

Arquivo: `workers/worker_flow/response_flow/etapas/resolver_triagem_base.py`

```python
from workers.worker_flow.response_flow.etapas.suporte_resolver import (
    PREFIXO_CONTEXTO,
    anexar_evento,
    dados_destinatario,
    logar_tratamento,
)
from workers.worker_flow.response_flow.etapas.validadores_universais.validador_triagem import (
    TIPO_TRATAMENTO_RESPOSTA_TRIAGEM_INVALIDA,
    validar_resposta_triagem,
)


def resolver_pergunta_triagem(
    contexto,
    *,
    evento,
    etapa_destino,
    enviar_etapa_atual,
    enviar_proxima_etapa,
):
    cliente, phone_id = dados_destinatario(contexto)
    nome_dependente = contexto.get("nome_dependente")
    resposta = validar_resposta_triagem(
        contexto.get("texto_cliente_atual"),
        contexto.get("tipo_mensagem_atual"),
    )

    if resposta is None:
        logar_tratamento(
            contexto,
            TIPO_TRATAMENTO_RESPOSTA_TRIAGEM_INVALIDA,
        )
        return enviar_etapa_atual(
            cliente,
            phone_id,
            nome_dependente,
            PREFIXO_CONTEXTO,
        )

    envio = enviar_proxima_etapa(cliente, phone_id, nome_dependente)
    envio["resposta_triagem"] = resposta
    return anexar_evento(
        contexto,
        envio,
        evento,
        {etapa_destino},
    )
```

### Passo 91 - Resolver da etapa 17

Arquivo: `workers/worker_flow/response_flow/etapas/resolver_etapa17.py`

```python
from core.integrations.whatsapp.pywa_functions.pywa_senders.etapa17 import enviar_etapa17
from core.integrations.whatsapp.pywa_functions.pywa_senders.etapa18 import enviar_etapa18
from workers.worker_flow.response_flow.etapas.resolver_triagem_base import resolver_pergunta_triagem
from workers.worker_flow.response_flow.transicoes.eventos import ETAPA_18_TRIAGEM_PERGUNTA_2, EVENTO_TRIAGEM_PERGUNTA_1_RESPONDIDA


def resolve_etapa17(contexto):
    return resolver_pergunta_triagem(
        contexto,
        evento=EVENTO_TRIAGEM_PERGUNTA_1_RESPONDIDA,
        etapa_destino=ETAPA_18_TRIAGEM_PERGUNTA_2,
        enviar_etapa_atual=enviar_etapa17,
        enviar_proxima_etapa=enviar_etapa18,
    )
```

### Passo 92 - Resolver da etapa 18

Arquivo: `workers/worker_flow/response_flow/etapas/resolver_etapa18.py`

```python
from core.integrations.whatsapp.pywa_functions.pywa_senders.etapa18 import enviar_etapa18
from core.integrations.whatsapp.pywa_functions.pywa_senders.etapa19 import enviar_etapa19
from workers.worker_flow.response_flow.etapas.resolver_triagem_base import resolver_pergunta_triagem
from workers.worker_flow.response_flow.transicoes.eventos import ETAPA_19_TRIAGEM_PERGUNTA_3, EVENTO_TRIAGEM_PERGUNTA_2_RESPONDIDA


def resolve_etapa18(contexto):
    return resolver_pergunta_triagem(contexto, evento=EVENTO_TRIAGEM_PERGUNTA_2_RESPONDIDA, etapa_destino=ETAPA_19_TRIAGEM_PERGUNTA_3, enviar_etapa_atual=enviar_etapa18, enviar_proxima_etapa=enviar_etapa19)
```

### Passo 93 - Resolver da etapa 19

Arquivo: `workers/worker_flow/response_flow/etapas/resolver_etapa19.py`

```python
from core.integrations.whatsapp.pywa_functions.pywa_senders.etapa19 import enviar_etapa19
from core.integrations.whatsapp.pywa_functions.pywa_senders.etapa20 import enviar_etapa20
from workers.worker_flow.response_flow.etapas.resolver_triagem_base import resolver_pergunta_triagem
from workers.worker_flow.response_flow.transicoes.eventos import ETAPA_20_TRIAGEM_PERGUNTA_4, EVENTO_TRIAGEM_PERGUNTA_3_RESPONDIDA


def resolve_etapa19(contexto):
    return resolver_pergunta_triagem(contexto, evento=EVENTO_TRIAGEM_PERGUNTA_3_RESPONDIDA, etapa_destino=ETAPA_20_TRIAGEM_PERGUNTA_4, enviar_etapa_atual=enviar_etapa19, enviar_proxima_etapa=enviar_etapa20)
```

### Passo 94 - Resolver da etapa 20

Arquivo: `workers/worker_flow/response_flow/etapas/resolver_etapa20.py`

```python
from core.integrations.whatsapp.pywa_functions.pywa_senders.etapa20 import enviar_etapa20
from core.integrations.whatsapp.pywa_functions.pywa_senders.etapa21 import enviar_etapa21
from workers.worker_flow.response_flow.etapas.resolver_triagem_base import resolver_pergunta_triagem
from workers.worker_flow.response_flow.transicoes.eventos import ETAPA_21_TRIAGEM_PERGUNTA_5, EVENTO_TRIAGEM_PERGUNTA_4_RESPONDIDA


def resolve_etapa20(contexto):
    return resolver_pergunta_triagem(contexto, evento=EVENTO_TRIAGEM_PERGUNTA_4_RESPONDIDA, etapa_destino=ETAPA_21_TRIAGEM_PERGUNTA_5, enviar_etapa_atual=enviar_etapa20, enviar_proxima_etapa=enviar_etapa21)
```

### Passo 95 - Resolver da etapa 21

Arquivo: `workers/worker_flow/response_flow/etapas/resolver_etapa21.py`

```python
from core.integrations.whatsapp.pywa_functions.pywa_senders.etapa21 import enviar_etapa21
from core.integrations.whatsapp.pywa_functions.pywa_senders.etapa22 import enviar_etapa22
from workers.worker_flow.response_flow.etapas.resolver_triagem_base import resolver_pergunta_triagem
from workers.worker_flow.response_flow.transicoes.eventos import ETAPA_22_TRIAGEM_PERGUNTA_6, EVENTO_TRIAGEM_PERGUNTA_5_RESPONDIDA


def resolve_etapa21(contexto):
    return resolver_pergunta_triagem(contexto, evento=EVENTO_TRIAGEM_PERGUNTA_5_RESPONDIDA, etapa_destino=ETAPA_22_TRIAGEM_PERGUNTA_6, enviar_etapa_atual=enviar_etapa21, enviar_proxima_etapa=enviar_etapa22)
```

### Passo 96 - Resolver da etapa 22

Arquivo: `workers/worker_flow/response_flow/etapas/resolver_etapa22.py`

```python
from core.integrations.whatsapp.pywa_functions.pywa_senders.etapa22 import enviar_etapa22
from core.integrations.whatsapp.pywa_functions.pywa_senders.etapa23 import enviar_etapa23
from workers.worker_flow.response_flow.etapas.suporte_resolver import PREFIXO_CONTEXTO, anexar_evento, dados_destinatario, logar_tratamento
from workers.worker_flow.response_flow.etapas.validadores_universais.validador_triagem import TIPO_TRATAMENTO_RESPOSTA_TRIAGEM_INVALIDA, validar_resposta_triagem
from workers.worker_flow.response_flow.transicoes.eventos import ETAPA_23_AGENDAMENTO_PENDENTE, EVENTO_TRIAGEM_PERGUNTA_6_RESPONDIDA


def resolve_etapa22(contexto):
    cliente, phone_id = dados_destinatario(contexto)
    nome_dependente = contexto.get("nome_dependente")
    resposta = validar_resposta_triagem(
        contexto.get("texto_cliente_atual"),
        contexto.get("tipo_mensagem_atual"),
    )
    if resposta is None:
        logar_tratamento(contexto, TIPO_TRATAMENTO_RESPOSTA_TRIAGEM_INVALIDA)
        return enviar_etapa22(cliente, phone_id, nome_dependente, PREFIXO_CONTEXTO)

    envio = enviar_etapa23(
        cliente,
        phone_id,
        contexto["link_agendamento_unidade"],
    )
    envio["resposta_triagem"] = resposta
    return anexar_evento(
        contexto,
        envio,
        EVENTO_TRIAGEM_PERGUNTA_6_RESPONDIDA,
        {ETAPA_23_AGENDAMENTO_PENDENTE},
    )
```

O sender retorna etapa 23 porque essa é a mensagem efetivamente apresentada.
O helper comum valida uma única aresta `22 -> 23`; o PostgreSQL a revalida pelo
mesmo caminho transacional usado em todas as demais etapas.

### Passo 97 - Resolver da etapa 23

Arquivo: `workers/worker_flow/response_flow/etapas/resolver_etapa23.py`

```python
from core.integrations.whatsapp.pywa_functions.pywa_senders.etapa23 import enviar_etapa23
from core.integrations.whatsapp.pywa_functions.pywa_senders.etapa24 import enviar_etapa24
from workers.worker_flow.response_flow.etapas.suporte_resolver import anexar_evento, dados_destinatario, detectar_tratamento_universal, logar_tratamento
from workers.worker_flow.response_flow.etapas.validadores_contexto.valida_etapa23 import TIPO_TRATAMENTO_AGENDAMENTO_NAO_CONFIRMADO, validar_etapa23
from workers.worker_flow.response_flow.transicoes.eventos import ETAPA_24_FINALIZACAO, EVENTO_AGENDAMENTO_CONFIRMADO


def resolve_etapa23(contexto):
    cliente, phone_id = dados_destinatario(contexto)
    tratamento = detectar_tratamento_universal(contexto)
    if tratamento:
        logar_tratamento(contexto, tratamento)
        return enviar_etapa23(
            cliente,
            phone_id,
            contexto["link_agendamento_unidade"],
            tratamento,
        )

    evento = validar_etapa23(contexto.get("texto_cliente_atual"))
    if evento is None:
        logar_tratamento(contexto, TIPO_TRATAMENTO_AGENDAMENTO_NAO_CONFIRMADO)
        return enviar_etapa23(
            cliente,
            phone_id,
            contexto["link_agendamento_unidade"],
            TIPO_TRATAMENTO_AGENDAMENTO_NAO_CONFIRMADO,
        )

    envio = enviar_etapa24(cliente, phone_id)
    return anexar_evento(
        contexto,
        envio,
        EVENTO_AGENDAMENTO_CONFIRMADO,
        {ETAPA_24_FINALIZACAO},
    )
```

> A etapa 23 possui resolver e pode permanecer ativa por qualquer tempo até uma
> confirmação aceita. A etapa 24 não possui resolver: é terminal, e novas
> mensagens são barradas pelo bloqueio cliente + unidade no Redis e pelo
> fallback transacional.

## Fase 7 - Roteamento e efeitos transacionais

### Passo 98 - Rotear as 23 etapas processáveis

Arquivo: `workers/worker_flow/response_flow/flow_sender.py`

```python
import logging

from workers.worker_flow.response_flow.etapas.resolver_etapa1 import resolve_etapa1
from workers.worker_flow.response_flow.etapas.resolver_etapa2 import resolve_etapa2
from workers.worker_flow.response_flow.etapas.resolver_etapa3 import resolve_etapa3
from workers.worker_flow.response_flow.etapas.resolver_etapa4 import resolve_etapa4
from workers.worker_flow.response_flow.etapas.resolver_etapa5 import resolve_etapa5
from workers.worker_flow.response_flow.etapas.resolver_etapa6 import resolve_etapa6
from workers.worker_flow.response_flow.etapas.resolver_etapa7 import resolve_etapa7
from workers.worker_flow.response_flow.etapas.resolver_etapa8 import resolve_etapa8
from workers.worker_flow.response_flow.etapas.resolver_etapa9 import resolve_etapa9
from workers.worker_flow.response_flow.etapas.resolver_etapa10 import resolve_etapa10
from workers.worker_flow.response_flow.etapas.resolver_etapa11 import resolve_etapa11
from workers.worker_flow.response_flow.etapas.resolver_etapa12 import resolve_etapa12
from workers.worker_flow.response_flow.etapas.resolver_etapa13 import resolve_etapa13
from workers.worker_flow.response_flow.etapas.resolver_etapa14 import resolve_etapa14
from workers.worker_flow.response_flow.etapas.resolver_etapa15 import resolve_etapa15
from workers.worker_flow.response_flow.etapas.resolver_etapa16 import resolve_etapa16
from workers.worker_flow.response_flow.etapas.resolver_etapa17 import resolve_etapa17
from workers.worker_flow.response_flow.etapas.resolver_etapa18 import resolve_etapa18
from workers.worker_flow.response_flow.etapas.resolver_etapa19 import resolve_etapa19
from workers.worker_flow.response_flow.etapas.resolver_etapa20 import resolve_etapa20
from workers.worker_flow.response_flow.etapas.resolver_etapa21 import resolve_etapa21
from workers.worker_flow.response_flow.etapas.resolver_etapa22 import resolve_etapa22
from workers.worker_flow.response_flow.etapas.resolver_etapa23 import resolve_etapa23
from workers.worker_flow.response_flow.transicoes.resolver_transicao import identificar_evento_por_destino


logger = logging.getLogger("worker.sender")

def flow_sender(contexto_historico):
    resposta_bot = contexto_historico[
        "resposta_bot_para_mensagem_atual"
    ] or {}

    # Primeira barreira: retry nunca reenvia uma resposta já persistida.
    if resposta_bot:
        etapa_resposta = resposta_bot.get("id_etapa")
        evento = identificar_evento_por_destino(
            contexto_historico,
            etapa_resposta,
        )
        contexto = {
            "enviou": False,
            "resposta_ja_existia": True,
            "id_hash_msg_bot": resposta_bot.get("id_hash_msg"),
            "id_etapa_resultante": etapa_resposta,
            "id_etapa_origem_transicao": contexto_historico.get(
                "id_etapa_origem_transicao"
            ),
        }
        if evento:
            contexto["evento_transicao"] = evento
        return contexto

    etapa_atual = contexto_historico.get("id_etapa_atual")
    etapa_para_rotear = (
        etapa_atual
        if etapa_atual is not None
        else contexto_historico["id_etapa_cliente"]
    )
    resolver = _resolvers().get(etapa_para_rotear)

    if resolver is None:
        raise NotImplementedError(
            f"Etapa {etapa_para_rotear} não possui resolver"
        )

    if contexto_historico["retry_count"] > 1:
        logger.info(
            "flow_sender_reprocessamento | acao=continuar_sem_resposta_previa "
            "id_conversa=%s etapa=%s retry=%s",
            contexto_historico["id_conversa"],
            etapa_para_rotear,
            contexto_historico["retry_count"],
        )

    return resolver(contexto_historico)


def _resolvers():
    """Monta o mapa na chamada para preservar patching nos testes focados."""
    return {
        1: resolve_etapa1,
        2: resolve_etapa2,
        3: resolve_etapa3,
        4: resolve_etapa4,
        5: resolve_etapa5,
        6: resolve_etapa6,
        7: resolve_etapa7,
        8: resolve_etapa8,
        9: resolve_etapa9,
        10: resolve_etapa10,
        11: resolve_etapa11,
        12: resolve_etapa12,
        13: resolve_etapa13,
        14: resolve_etapa14,
        15: resolve_etapa15,
        16: resolve_etapa16,
        17: resolve_etapa17,
        18: resolve_etapa18,
        19: resolve_etapa19,
        20: resolve_etapa20,
        21: resolve_etapa21,
        22: resolve_etapa22,
        23: resolve_etapa23,
    }
```

### Passo 99 - Registrar efeitos específicos de cada aresta

Arquivo: `workers/worker_flow/transacoes/efeitos_transicao.py`

```python
import logging

from core.logging_config import short_value
from core.repositories.email_cliente import atualizar_email_cliente
from core.repositories.idade_aluno import atualizar_idade_cliente, atualizar_idade_dependente
from core.repositories.inserts import inserir_dependente_para_conversa
from core.repositories.respostas_triagem import registrar_resposta_triagem
from core.repositories.updates import atualizar_nome_cliente_por_telefone, atualizar_nome_dependente_por_conversa, atualizar_status_dependente_conversa
from workers.worker_flow.response_flow.etapas.validadores_contexto.valida_etapa14 import validar_etapa14
from workers.worker_flow.response_flow.etapas.validadores_contexto.valida_etapa9 import (
    obter_idade_minima_dependente,
    validar_etapa9,
)
from workers.worker_flow.response_flow.etapas.validadores_universais.validador_nome import validar_nome_cliente
from workers.worker_flow.response_flow.etapas.validadores_universais.validador_triagem import validar_resposta_triagem
from workers.worker_flow.response_flow.transicoes.eventos import (
    ETAPA_1_RETORNO_VETERANO,
    ETAPA_2_NOVO_NOME_VETERANO,
    ETAPA_3_CONFIRMACAO_NOME_CLIENTE,
    ETAPA_4_DESTINO_VETERANO,
    ETAPA_5_NOME_CLIENTE_NOVATO,
    ETAPA_6_DESTINO_NOVATO,
    ETAPA_7_NOME_DEPENDENTE,
    ETAPA_8_CONFIRMACAO_NOME_DEPENDENTE,
    ETAPA_9_IDADE_ALUNO,
    ETAPA_10_CONFIRMACAO_IDADE,
    ETAPA_11_OFERTA_AULA,
    ETAPA_12_OFERTA_ADIADA,
    ETAPA_13_RETORNO_OFERTA,
    ETAPA_14_EMAIL,
    ETAPA_15_CONFIRMACAO_EMAIL,
    ETAPA_16_INTRODUCAO_TRIAGEM,
    ETAPA_17_TRIAGEM_PERGUNTA_1,
    ETAPA_18_TRIAGEM_PERGUNTA_2,
    ETAPA_19_TRIAGEM_PERGUNTA_3,
    ETAPA_20_TRIAGEM_PERGUNTA_4,
    ETAPA_21_TRIAGEM_PERGUNTA_5,
    ETAPA_22_TRIAGEM_PERGUNTA_6,
    ETAPA_23_AGENDAMENTO_PENDENTE,
    ETAPA_24_FINALIZACAO,
    EVENTO_AGENDAMENTO_CONFIRMADO,
    EVENTO_ATUALIZAR_NOME,
    EVENTO_CLIENTE_RETORNOU,
    EVENTO_EMAIL_CONFIRMADO,
    EVENTO_EMAIL_INFORMADO,
    EVENTO_EMAIL_REJEITADO,
    EVENTO_IDADE_CONFIRMADA,
    EVENTO_IDADE_INFORMADA,
    EVENTO_IDADE_REJEITADA,
    EVENTO_NOME_CLIENTE_CONFIRMADO_NOVATO,
    EVENTO_NOME_CLIENTE_CONFIRMADO_VETERANO,
    EVENTO_NOME_CLIENTE_INFORMADO,
    EVENTO_NOME_CLIENTE_REJEITADO_NOVATO,
    EVENTO_NOME_CLIENTE_REJEITADO_VETERANO,
    EVENTO_NOME_DEPENDENTE_CONFIRMADO,
    EVENTO_NOME_DEPENDENTE_INFORMADO,
    EVENTO_NOME_DEPENDENTE_REJEITADO,
    EVENTO_NOVO_ATENDIMENTO,
    EVENTO_OFERTA_ACEITA,
    EVENTO_OFERTA_ADIADA,
    EVENTO_PARA_MIM,
    EVENTO_PARA_OUTRA_PESSOA,
    EVENTO_RETORNO_ADIADO,
    EVENTO_RETORNO_CONFIRMADO,
    EVENTO_TRIAGEM_INICIADA,
    EVENTO_TRIAGEM_PERGUNTA_1_RESPONDIDA,
    EVENTO_TRIAGEM_PERGUNTA_2_RESPONDIDA,
    EVENTO_TRIAGEM_PERGUNTA_3_RESPONDIDA,
    EVENTO_TRIAGEM_PERGUNTA_4_RESPONDIDA,
    EVENTO_TRIAGEM_PERGUNTA_5_RESPONDIDA,
    EVENTO_TRIAGEM_PERGUNTA_6_RESPONDIDA,
)


logger = logging.getLogger("worker.support")


def atualizar_banco_conforme_transicao_de_etapa(
    contexto_historico,
    contexto_envio,
    cursor,
):
    origem = contexto_historico.get("id_etapa_origem_transicao")
    evento = contexto_envio.get("evento_transicao")
    destino = contexto_envio.get("id_etapa_resultante")

    if not evento:
        return None

    # ETAPA 1: somente escolhe o próximo ramo.
    if origem == ETAPA_1_RETORNO_VETERANO:
        if evento == EVENTO_ATUALIZAR_NOME:
            return _sem_dado(origem, evento, destino, ETAPA_2_NOVO_NOME_VETERANO)
        if evento == EVENTO_NOVO_ATENDIMENTO:
            return _sem_dado(origem, evento, destino, ETAPA_4_DESTINO_VETERANO)

    # ETAPAS 2 E 5: nome válido é persistido antes da confirmação.
    if origem in {ETAPA_2_NOVO_NOME_VETERANO, ETAPA_5_NOME_CLIENTE_NOVATO}:
        if evento == EVENTO_NOME_CLIENTE_INFORMADO:
            _exigir_destino(
                origem,
                evento,
                destino,
                ETAPA_3_CONFIRMACAO_NOME_CLIENTE,
            )
            return _persistir_nome_cliente(
                contexto_historico,
                contexto_envio,
                cursor,
            )

    # ETAPA 3: confirma ou volta à coleta; o dado já foi persistido.
    # Rejeitar nunca limpa o banco: a próxima coleta válida sobrescreve.
    if origem == ETAPA_3_CONFIRMACAO_NOME_CLIENTE:
        if evento == EVENTO_NOME_CLIENTE_CONFIRMADO_VETERANO:
            return _sem_dado(origem, evento, destino, ETAPA_4_DESTINO_VETERANO)
        if evento == EVENTO_NOME_CLIENTE_CONFIRMADO_NOVATO:
            return _sem_dado(origem, evento, destino, ETAPA_6_DESTINO_NOVATO)
        if evento == EVENTO_NOME_CLIENTE_REJEITADO_VETERANO:
            return _sem_dado(origem, evento, destino, ETAPA_2_NOVO_NOME_VETERANO)
        if evento == EVENTO_NOME_CLIENTE_REJEITADO_NOVATO:
            return _sem_dado(origem, evento, destino, ETAPA_5_NOME_CLIENTE_NOVATO)

    # ETAPAS 4 E 6: definem titular/dependente e criam o dependente vazio.
    if origem in {ETAPA_4_DESTINO_VETERANO, ETAPA_6_DESTINO_NOVATO}:
        if evento == EVENTO_PARA_MIM:
            _exigir_destino(origem, evento, destino, ETAPA_9_IDADE_ALUNO)
            return _persistir_destino(contexto_historico, False, cursor)
        if evento == EVENTO_PARA_OUTRA_PESSOA:
            _exigir_destino(origem, evento, destino, ETAPA_7_NOME_DEPENDENTE)
            return _persistir_destino(contexto_historico, True, cursor)

    # ETAPA 7: nome válido do dependente é persistido antes da confirmação.
    if origem == ETAPA_7_NOME_DEPENDENTE:
        if evento == EVENTO_NOME_DEPENDENTE_INFORMADO:
            _exigir_destino(
                origem,
                evento,
                destino,
                ETAPA_8_CONFIRMACAO_NOME_DEPENDENTE,
            )
            return _persistir_nome_dependente(
                contexto_historico,
                contexto_envio,
                cursor,
            )

    # ETAPA 8: confirma ou volta à coleta; o dado já foi persistido.
    # Rejeitar nunca limpa o banco: a próxima coleta válida sobrescreve.
    if origem == ETAPA_8_CONFIRMACAO_NOME_DEPENDENTE:
        if evento == EVENTO_NOME_DEPENDENTE_CONFIRMADO:
            return _sem_dado(origem, evento, destino, ETAPA_9_IDADE_ALUNO)
        if evento == EVENTO_NOME_DEPENDENTE_REJEITADO:
            return _sem_dado(origem, evento, destino, ETAPA_7_NOME_DEPENDENTE)

    # ETAPA 9: somente idade permitida chega aqui com evento e é persistida.
    if origem == ETAPA_9_IDADE_ALUNO:
        if evento == EVENTO_IDADE_INFORMADA:
            _exigir_destino(
                origem,
                evento,
                destino,
                ETAPA_10_CONFIRMACAO_IDADE,
            )
            return _persistir_idade(
                contexto_historico,
                contexto_envio,
                cursor,
            )

    # ETAPA 10: confirma ou volta à coleta; a idade já foi persistida.
    # Rejeitar nunca limpa o banco: a próxima coleta válida sobrescreve.
    if origem == ETAPA_10_CONFIRMACAO_IDADE:
        if evento == EVENTO_IDADE_CONFIRMADA:
            return _sem_dado(origem, evento, destino, ETAPA_11_OFERTA_AULA)
        if evento == EVENTO_IDADE_REJEITADA:
            return _sem_dado(origem, evento, destino, ETAPA_9_IDADE_ALUNO)

    # ETAPAS 11 A 13: decisões de oferta, sem novo dado cadastral.
    if origem == ETAPA_11_OFERTA_AULA:
        if evento == EVENTO_OFERTA_ACEITA:
            return _sem_dado(origem, evento, destino, ETAPA_14_EMAIL)
        if evento == EVENTO_OFERTA_ADIADA:
            return _sem_dado(origem, evento, destino, ETAPA_12_OFERTA_ADIADA)
    if origem == ETAPA_12_OFERTA_ADIADA and evento == EVENTO_CLIENTE_RETORNOU:
        return _sem_dado(origem, evento, destino, ETAPA_13_RETORNO_OFERTA)
    if origem == ETAPA_13_RETORNO_OFERTA:
        if evento == EVENTO_RETORNO_CONFIRMADO:
            return _sem_dado(origem, evento, destino, ETAPA_14_EMAIL)
        if evento == EVENTO_RETORNO_ADIADO:
            return _sem_dado(origem, evento, destino, ETAPA_12_OFERTA_ADIADA)

    # ETAPA 14: email válido é persistido antes da confirmação.
    if origem == ETAPA_14_EMAIL and evento == EVENTO_EMAIL_INFORMADO:
        _exigir_destino(
            origem,
            evento,
            destino,
            ETAPA_15_CONFIRMACAO_EMAIL,
        )
        return _persistir_email(
            contexto_historico,
            contexto_envio,
            cursor,
        )

    # ETAPA 15: confirma ou volta à coleta; o email já foi persistido.
    # Rejeitar nunca limpa o banco: a próxima coleta válida sobrescreve.
    if origem == ETAPA_15_CONFIRMACAO_EMAIL:
        if evento == EVENTO_EMAIL_CONFIRMADO:
            return _sem_dado(
                origem,
                evento,
                destino,
                ETAPA_16_INTRODUCAO_TRIAGEM,
            )
        if evento == EVENTO_EMAIL_REJEITADO:
            return _sem_dado(origem, evento, destino, ETAPA_14_EMAIL)

    if origem == ETAPA_16_INTRODUCAO_TRIAGEM and evento == EVENTO_TRIAGEM_INICIADA:
        return _sem_dado(origem, evento, destino, ETAPA_17_TRIAGEM_PERGUNTA_1)

    # ETAPAS 17 A 22: cada origem registra exatamente uma resposta.
    eventos_triagem = {
        ETAPA_17_TRIAGEM_PERGUNTA_1: (EVENTO_TRIAGEM_PERGUNTA_1_RESPONDIDA, ETAPA_18_TRIAGEM_PERGUNTA_2),
        ETAPA_18_TRIAGEM_PERGUNTA_2: (EVENTO_TRIAGEM_PERGUNTA_2_RESPONDIDA, ETAPA_19_TRIAGEM_PERGUNTA_3),
        ETAPA_19_TRIAGEM_PERGUNTA_3: (EVENTO_TRIAGEM_PERGUNTA_3_RESPONDIDA, ETAPA_20_TRIAGEM_PERGUNTA_4),
        ETAPA_20_TRIAGEM_PERGUNTA_4: (EVENTO_TRIAGEM_PERGUNTA_4_RESPONDIDA, ETAPA_21_TRIAGEM_PERGUNTA_5),
        ETAPA_21_TRIAGEM_PERGUNTA_5: (EVENTO_TRIAGEM_PERGUNTA_5_RESPONDIDA, ETAPA_22_TRIAGEM_PERGUNTA_6),
        ETAPA_22_TRIAGEM_PERGUNTA_6: (EVENTO_TRIAGEM_PERGUNTA_6_RESPONDIDA, ETAPA_23_AGENDAMENTO_PENDENTE),
    }
    if origem in eventos_triagem:
        evento_esperado, destino_esperado = eventos_triagem[origem]
        if evento == evento_esperado:
            _exigir_destino(origem, evento, destino, destino_esperado)
            return _persistir_resposta_triagem(
                contexto_historico,
                contexto_envio,
                cursor,
            )

    if origem == ETAPA_23_AGENDAMENTO_PENDENTE and evento == EVENTO_AGENDAMENTO_CONFIRMADO:
        return _sem_dado(origem, evento, destino, ETAPA_24_FINALIZACAO)

    raise ValueError(
        "Transição sem efeitos conhecidos "
        f"(origem={origem}, evento={evento}, destino={destino})"
    )


def _exigir_destino(origem, evento, destino, esperado):
    if destino != esperado:
        raise ValueError(
            "Destino incompatível com o efeito "
            f"(origem={origem}, evento={evento}, destino={destino}, esperado={esperado})"
        )


def _sem_dado(origem, evento, destino, esperado):
    _exigir_destino(origem, evento, destino, esperado)
    return {"transicao_confirmada": True}


def _persistir_nome_cliente(contexto, contexto_envio, cursor):
    nome = contexto_envio.get("nome_cliente_candidato")
    if not nome:
        resultado = validar_nome_cliente(contexto.get("texto_cliente_atual"))
        nome = resultado.primeiro_nome if resultado.valido else None
    if not nome:
        logger.critical(
            "cliente_nome_anomalia_critica | motivo=nome_candidato_vazio "
            "id_conversa=%s",
            contexto["id_conversa"],
        )
        raise ValueError("Nome do cliente candidato vazio")
    telefone = contexto["mensagem_cliente_atual"]["cliente_telefone"]
    atualizar_nome_cliente_por_telefone(telefone, nome, cursor)
    return {"cliente_nome_atualizado": True, "primeiro_nome_cliente": nome}


def _persistir_nome_dependente(contexto, contexto_envio, cursor):
    nome = contexto_envio.get("nome_dependente_candidato")
    if not nome:
        resultado = validar_nome_cliente(contexto.get("texto_cliente_atual"))
        nome = resultado.primeiro_nome if resultado.valido else None
    if not nome:
        raise ValueError("Nome do dependente não reconstruído")
    atualizar_nome_dependente_por_conversa(
        contexto["id_conversa"],
        nome,
        cursor,
    )
    return {"dependente_nome_atualizado": True, "nome_dependente": nome}


def _persistir_destino(contexto, status_dependente, cursor):
    atualizar_status_dependente_conversa(
        contexto["id_conversa"],
        status_dependente,
        cursor,
    )
    resultado = {"status_dependente": status_dependente}
    if status_dependente:
        resultado.update(
            inserir_dependente_para_conversa(
                contexto["id_conversa"],
                cursor,
            )
        )
    return resultado


def _persistir_idade(contexto, contexto_envio, cursor):
    idade = contexto_envio.get("idade_aluno_candidata")
    if idade is None:
        resultado = validar_etapa9(contexto.get("texto_cliente_atual"))
        idade = resultado.idade if resultado.valida else None
    if idade is None:
        raise ValueError("Idade permitida não reconstruída")
    if idade > 99:
        raise ValueError("Idade acima do limite não pode ser persistida")
    if contexto.get("status_dependente"):
        idade_minima = obter_idade_minima_dependente(
            contexto.get("bpa_ativo_unidade")
        )
        if idade < idade_minima:
            raise ValueError("Idade do dependente abaixo do mínimo permitido")
        atualizar_idade_dependente(contexto["id_conversa"], idade, cursor)
        destino = "dependente"
    else:
        if idade < 18:
            raise ValueError("Idade do cliente abaixo do mínimo permitido")
        atualizar_idade_cliente(contexto["id_cliente"], idade, cursor)
        destino = "cliente"
    return {"idade_aluno_atualizada": True, "idade": idade, "destino": destino}


def _persistir_email(contexto, contexto_envio, cursor):
    email = contexto_envio.get("email_cliente_candidato")
    if not email:
        resultado = validar_etapa14(contexto.get("texto_cliente_atual"))
        email = resultado.email if resultado.valido else None
    if not email:
        raise ValueError("Email válido não reconstruído")
    atualizar_email_cliente(contexto["id_cliente"], email, cursor)
    return {"cliente_email_atualizado": True, "email_cliente": email}


def _persistir_resposta_triagem(contexto, contexto_envio, cursor):
    resposta = contexto_envio.get("resposta_triagem")
    if resposta is None:
        resposta = validar_resposta_triagem(
            contexto.get("texto_cliente_atual"),
            contexto.get("tipo_mensagem_atual"),
        )
    if resposta is None:
        raise ValueError("Resposta da triagem não reconstruída")
    mensagem = contexto["mensagem_cliente_atual"]
    return registrar_resposta_triagem(
        contexto["id_conversa"],
        contexto["id_etapa_origem_transicao"],
        resposta,
        mensagem.get("id_mensagem"),
        cursor,
    )
```

### Passo 100 - Encerrar sem apagar cliente, conversa ou dependente

Arquivo: `core/repositories/encerramento_atendimento.py`

```python
def encerrar_conversa(id_conversa, cursor):
    cursor.execute(
        """
        UPDATE chatbot.conversa
        SET
            status_ativa = FALSE,
            finalizou_em = NOW(),
            processing = FALSE,
            processing_started_at = NULL
        WHERE id_conversa = %s
          AND status_ativa = TRUE
        RETURNING finalizou_em;
        """,
        (id_conversa,),
    )

    resultado = cursor.fetchone()

    if not resultado:
        raise RuntimeError(
            "Conversa não encerrada "
            f"(id_conversa={id_conversa}, linhas={cursor.rowcount})"
        )

    return resultado[0]
```

### Passo 101 - Reconstruir encerramentos no retry

Arquivo: `workers/worker_flow/transacoes/encerramento_atendimento.py`

```python
import logging

from core.repositories.encerramento_atendimento import encerrar_conversa
from core.repositories.politicas_etapa import buscar_politica_etapa
from workers.worker_flow.response_flow.etapas.validadores_contexto.valida_etapa9 import (
    obter_idade_minima_dependente,
    validar_etapa9,
)
from workers.worker_flow.response_flow.transicoes.eventos import (
    ETAPA_9_IDADE_ALUNO,
)


logger = logging.getLogger("worker.support")

MOTIVO_CLIENTE_MENOR_18 = "cliente_menor_18"
MOTIVO_DEPENDENTE_ABAIXO_MINIMO = "dependente_abaixo_idade_minima"
MOTIVO_IDADE_ACIMA_99 = "idade_acima_99"
MOTIVO_ETAPA_FINAL = "etapa_final"


def resolver_intencao_encerramento(
    contexto_historico,
    contexto_envio,
    cursor,
):
    if contexto_envio.get("encerrar_atendimento"):
        return {
            "motivo": contexto_envio["motivo_encerramento"],
            "bloqueio_dias": 0,
        }

    # Se o sender já havia respondido antes da queda, um encerramento da
    # etapa 9 é reconstruído pela mensagem original da idade.
    if contexto_envio.get("resposta_ja_existia"):
        intencao = _reconstruir_encerramento_etapa9(contexto_historico)
        if intencao:
            return intencao

    if not contexto_envio.get("evento_transicao"):
        return None

    etapa_politica = contexto_envio["id_etapa_resultante"]
    politica = buscar_politica_etapa(etapa_politica, cursor)

    if not politica.encerra_automaticamente:
        return None

    return {
        "motivo": MOTIVO_ETAPA_FINAL,
        "bloqueio_dias": politica.bloqueio_dias,
    }


def _reconstruir_encerramento_etapa9(contexto):
    if (
        contexto.get("id_etapa_origem_transicao")
        != ETAPA_9_IDADE_ALUNO
    ):
        return None

    resultado = validar_etapa9(contexto.get("texto_cliente_atual"))
    if resultado.acima_limite:
        return {"motivo": MOTIVO_IDADE_ACIMA_99, "bloqueio_dias": 0}
    if not resultado.valida:
        return None

    idade = resultado.idade

    if contexto.get("status_dependente"):
        minima = obter_idade_minima_dependente(
            contexto.get("bpa_ativo_unidade")
        )
        if idade < minima:
            return {
                "motivo": MOTIVO_DEPENDENTE_ABAIXO_MINIMO,
                "bloqueio_dias": 0,
            }
        return None

    if idade < 18:
        return {"motivo": MOTIVO_CLIENTE_MENOR_18, "bloqueio_dias": 0}

    return None


def aplicar_encerramento_se_necessario(
    id_conversa,
    intencao_encerramento,
    cursor,
):
    if not intencao_encerramento:
        return {
            "atendimento_encerrado": False,
            "finalizou_em": None,
            "bloqueio_dias": 0,
            "motivo": None,
        }

    finalizou_em = encerrar_conversa(id_conversa, cursor)
    bloqueio_dias = int(
        intencao_encerramento.get("bloqueio_dias") or 0
    )
    logger.info(
        "atendimento_encerrado | acao=encerrar_conversa "
        "id_conversa=%s motivo=%s bloqueio_dias=%s",
        id_conversa,
        intencao_encerramento["motivo"],
        bloqueio_dias,
    )
    return {
        "atendimento_encerrado": True,
        "finalizou_em": finalizou_em,
        "bloqueio_dias": bloqueio_dias,
        "motivo": intencao_encerramento["motivo"],
    }
```

## Fase 8 - Remoções e compatibilidade

### Passo 102 - Atualizar componentes visuais compartilhados

Arquivo: `core/integrations/whatsapp/messages/componentes_compartilhados.py`

```python
"""Componentes de apresentação compartilhados pelo fluxo do WhatsApp."""


CABECALHO_ETAPA16_TRIAGEM = "Triagem cognitiva"

RODAPE_ETAPA5_BOAS_VINDAS = "Seja muito bem-vindo(a)!"
RODAPE_ETAPA12_ESPERA = "Estaremos te esperando!"
RODAPE_OPCAO_UNICA = "Selecione apenas uma opção abaixo."


def montar_texto_com_rodape(mensagem, rodape):
    return f"{mensagem}\n\n_{rodape}_"
```

### Passo 103 - Atualizar componentes da triagem

Arquivo: `core/integrations/whatsapp/messages/triagem_componentes.py`

```python
"""Botões e rodapé compartilhados exclusivamente pelas etapas 17 a 22.

Este helper não contém perguntas, não envia mensagens e não decide etapas.
"""

from core.integrations.whatsapp.messages.componentes_compartilhados import (
    RODAPE_OPCAO_UNICA,
)


BOTAO_TRIAGEM_NUNCA = "Nunca"
BOTAO_TRIAGEM_AS_VEZES = "Às vezes"
BOTAO_TRIAGEM_FREQUENTEMENTE = "Frequentemente"

BOTOES_TRIAGEM = (
    BOTAO_TRIAGEM_NUNCA,
    BOTAO_TRIAGEM_AS_VEZES,
    BOTAO_TRIAGEM_FREQUENTEMENTE,
)


def montar_botoes_triagem():
    return BOTOES_TRIAGEM


def montar_rodape_triagem():
    return RODAPE_OPCAO_UNICA
```

### Passo 104 - Remover arquivos substituídos

Os arquivos abaixo não possuem conteúdo final e devem ser removidos somente
depois que todos os imports novos estiverem ativos:

```text
core/repositories/contexto_etapa4.py
core/repositories/contexto_etapa5.py
core/repositories/contexto_etapa7.py
core/repositories/contexto_etapa16.py
core/repositories/contexto_triagem.py
workers/worker_flow/response_flow/etapas/validadores_contexto/valida_etapa2.py
workers/worker_flow/response_flow/etapas/validadores_contexto/valida_etapa4.py
workers/worker_flow/response_flow/etapas/validadores_contexto/valida_etapa5.py
workers/worker_flow/response_flow/etapas/validadores_contexto/valida_etapa7.py
workers/worker_flow/response_flow/etapas/validadores_contexto/valida_etapa16.py
```

`valida_etapa8.py` não é removido: ele muda de responsabilidade e passa a
validar a confirmação do nome do dependente. A validação antiga de email passa
integralmente para `valida_etapa14.py`.

### Passo 105 - Tornar o funil compatível com a etapa 23 ativa

Arquivo: `core/repositories/funil.py`

```python
def listar_conversas_pendentes_funil(
    cursor,
    *,
    limite=100,
):
    if not isinstance(limite, int) or limite <= 0:
        raise ValueError("limite deve ser um inteiro positivo")

    cursor.execute(
        """
        SELECT c.id_conversa
        FROM chatbot.conversa c
        JOIN chatbot.etapa e
          ON e.id_etapa = c.id_etapa_atual
        WHERE e.elegivel_funil = TRUE
          AND c.lead_no_funil IS NOT TRUE
        ORDER BY
            COALESCE(c.finalizou_em, c.last_interaction_at) ASC NULLS FIRST,
            c.id_conversa ASC
        LIMIT %s;
        """,
        (limite,),
    )

    return [linha[0] for linha in cursor.fetchall()]


def marcar_conversa_como_enviada_ao_funil(id_conversa, cursor):
    cursor.execute(
        """
        UPDATE chatbot.conversa AS c
        SET lead_no_funil = TRUE
        FROM chatbot.etapa AS e
        WHERE c.id_conversa = %s
          AND e.id_etapa = c.id_etapa_atual
          AND e.elegivel_funil = TRUE
          AND c.lead_no_funil IS NOT TRUE
        RETURNING c.id_conversa;
        """,
        (id_conversa,),
    )

    return cursor.fetchone() is not None
```

A elegibilidade passa a vir exclusivamente da política da etapa. Assim, uma
conversa ativa na etapa 23 pode ser enviada ao funil mesmo que o cliente nunca
clique em `Já agendei`. Se ela avançar para a etapa 24 antes do job, continua
elegível. A coluna `lead_no_funil` mantém a operação única nos dois casos.

Redis, webhook e regra de turno não mudam. O contrato permanece:

```text
webhook
-> consulta cache de bloqueio cliente + unidade
-> em miss/falha usa a política persistida no banco
-> enfileira apenas uma mensagem válida por turno

worker
-> revalida bloqueio no banco
-> processa uma mensagem com lock
-> persiste histórico, resposta, movimento e efeitos na mesma transação
-> faz o primeiro commit
-> em uma segunda transação aplica eventual encerramento e marca a fila sent
-> depois do segundo commit registra no Redis o bloqueio de 30 dias da etapa 24
```

O Redis continua armazenando somente dados derivados. Nome da unidade,
classificação veterano/novato e candidatos de confirmação vêm do PostgreSQL e
do histórico em todo ciclo.

O worker do funil conserva seu ciclo e sua idempotência; somente a consulta do
repositório deixa de exigir `status_ativa=False` e `finalizou_em`, pois esses
campos ainda não existem semanticamente enquanto o cliente aguarda na etapa 23.

## Fase 9 - Testes essenciais

### Passo 106 - Substituir testes semânticos antigos por um teste focal

Arquivo: `tests/unit/test_fluxo_24_etapas.py`

```python
import unittest
from unittest.mock import patch

from core.database.deploy.etapa_transicao_script import TRANSICOES_INICIAIS
from core.database.deploy.povoar_etapas import ETAPAS
from workers.worker_flow import valida_historico
from workers.worker_flow.response_flow import flow_sender
from workers.worker_flow.response_flow.etapas.validadores_contexto.valida_etapa3 import validar_etapa3
from workers.worker_flow.response_flow.etapas.validadores_contexto.valida_etapa10 import validar_etapa10
from workers.worker_flow.response_flow.etapas.validadores_contexto.valida_etapa15 import validar_etapa15
from workers.worker_flow.response_flow.etapas.validadores_contexto.valida_etapa23 import validar_etapa23
from workers.worker_flow.response_flow.transicoes.eventos import (
    EVENTO_AGENDAMENTO_CONFIRMADO,
    EVENTO_EMAIL_CONFIRMADO,
    EVENTO_EMAIL_REJEITADO,
    EVENTO_IDADE_CONFIRMADA,
    EVENTO_IDADE_REJEITADA,
    EVENTO_NOME_CLIENTE_CONFIRMADO_NOVATO,
    EVENTO_NOME_CLIENTE_CONFIRMADO_VETERANO,
    EVENTO_NOME_CLIENTE_REJEITADO_NOVATO,
    EVENTO_NOME_CLIENTE_REJEITADO_VETERANO,
)


class Fluxo24EtapasTests(unittest.TestCase):
    def test_politicas_separam_elegibilidade_e_bloqueio_final(self):
        politicas = {
            id_etapa: (
                encerra_automaticamente,
                bloqueio_dias,
                elegivel_funil,
            )
            for (
                id_etapa,
                _nome,
                encerra_automaticamente,
                bloqueio_dias,
                elegivel_funil,
            ) in ETAPAS
        }
        self.assertEqual(politicas[23], (False, 0, True))
        self.assertEqual(politicas[24], (True, 30, True))

    def test_mapa_possui_as_arestas_fechadas(self):
        mapa = set(TRANSICOES_INICIAIS)
        self.assertIn((1, "atualizar_nome", 2), mapa)
        self.assertIn((1, "novo_atendimento", 4), mapa)
        self.assertIn((3, "nome_cliente_confirmado_novato", 6), mapa)
        self.assertIn((3, "nome_cliente_rejeitado_veterano", 2), mapa)
        self.assertIn((8, "nome_dependente_rejeitado", 7), mapa)
        self.assertIn((10, "idade_rejeitada", 9), mapa)
        self.assertIn((15, "email_rejeitado", 14), mapa)
        self.assertIn((22, "triagem_pergunta_6_respondida", 23), mapa)
        self.assertIn((23, "agendamento_confirmado", 24), mapa)
        self.assertFalse(any(origem == 24 for origem, _, _ in mapa))

    def test_nova_conversa_escolhe_etapa_por_cliente_e_unidade(self):
        conversa = {"id_etapa_atual": None}
        self.assertEqual(
            valida_historico._resolver_etapa_cliente(
                conversa,
                {"cliente_veterano": True},
            ),
            1,
        )
        self.assertEqual(
            valida_historico._resolver_etapa_cliente(
                conversa,
                {"cliente_veterano": False},
            ),
            5,
        )

    def test_confirmacoes_produzem_eventos_por_origem(self):
        self.assertEqual(
            validar_etapa3("Sim", cliente_veterano=True),
            EVENTO_NOME_CLIENTE_CONFIRMADO_VETERANO,
        )
        self.assertEqual(
            validar_etapa3("Não", cliente_veterano=True),
            EVENTO_NOME_CLIENTE_REJEITADO_VETERANO,
        )
        self.assertEqual(
            validar_etapa3("Sim", cliente_veterano=False),
            EVENTO_NOME_CLIENTE_CONFIRMADO_NOVATO,
        )
        self.assertEqual(
            validar_etapa3("Não", cliente_veterano=False),
            EVENTO_NOME_CLIENTE_REJEITADO_NOVATO,
        )
        self.assertEqual(validar_etapa10("Sim"), EVENTO_IDADE_CONFIRMADA)
        self.assertEqual(validar_etapa10("Não"), EVENTO_IDADE_REJEITADA)
        self.assertEqual(validar_etapa15("Sim"), EVENTO_EMAIL_CONFIRMADO)
        self.assertEqual(validar_etapa15("Não"), EVENTO_EMAIL_REJEITADO)

    def test_agendamento_aceita_expressao_dentro_de_frase(self):
        self.assertEqual(
            validar_etapa23("Agendado para sexta às 14h"),
            EVENTO_AGENDAMENTO_CONFIRMADO,
        )
        self.assertEqual(
            validar_etapa23("Já marquei para amanhã"),
            EVENTO_AGENDAMENTO_CONFIRMADO,
        )
        self.assertIsNone(validar_etapa23("Ainda vou escolher um horário"))

    def test_flow_sender_inicializa_na_etapa_classificada(self):
        contexto = {
            "id_conversa": 10,
            "id_etapa_atual": None,
            "id_etapa_cliente": 5,
            "retry_count": 1,
            "resposta_bot_para_mensagem_atual": None,
            "mensagem_cliente_atual": {
                "id_mensagem_fila": 20,
                "id_hash_msg": "wamid.cliente",
            },
        }
        esperado = {"enviou": True, "id_etapa_resultante": 5}
        with patch.object(
            flow_sender,
            "resolve_etapa5",
            return_value=esperado,
        ) as resolver:
            resultado = flow_sender.flow_sender(contexto)
        resolver.assert_called_once_with(contexto)
        self.assertEqual(resultado, esperado)

    def test_retry_com_resposta_existente_nao_reenvia(self):
        contexto = {
            "id_conversa": 10,
            "id_etapa_atual": 10,
            "id_etapa_cliente": 10,
            "id_etapa_origem_transicao": 10,
            "transicoes_permitidas": {"idade_confirmada": 11},
            "retry_count": 2,
            "mensagem_cliente_atual": {
                "id_mensagem_fila": 20,
                "id_hash_msg": "wamid.cliente",
            },
            "resposta_bot_para_mensagem_atual": {
                "id_mensagem": 30,
                "id_hash_msg": "wamid.bot",
                "id_etapa": 11,
            },
        }
        resultado = flow_sender.flow_sender(contexto)
        self.assertFalse(resultado["enviou"])
        self.assertTrue(resultado["resposta_ja_existia"])

if __name__ == "__main__":
    unittest.main()
```

### Passo 107 - Remover testes presos ao mapa antigo

Os testes abaixo serão removidos porque duplicam a mesma semântica com IDs
1–17. Sua cobertura essencial passa ao arquivo do passo anterior:

```text
tests/unit/test_transicoes_etapa.py
tests/unit/test_validadores_essenciais.py
tests/unit/test_roteamento_essencial.py
tests/unit/test_efeitos_triagem.py
tests/unit/test_lastfrom_semantico.py
```

Permanecem sem alteração os testes de webhook, flood, cache, deploy, retry,
persistência, runtime e o cenário A/B/C. Durante a implementação deste plano,
executar somente:

```powershell
python -m unittest tests.unit.test_fluxo_24_etapas tests.unit.test_fluxo_turno_abc tests.unit.test_retry_essencial tests.unit.test_persistencia_essencial
```

Não executar a suíte inteira a cada arquivo.

## Fase 10 - Documentação e aplicação

### Passo 108 - Sincronizar documentação técnica

Como esta fase altera documentação, e não código executável, as mudanças são
textuais e pontuais; os documentos não devem ser substituídos por versões
reduzidas:

```text
ROTINA_IMPLEMENTACAO_ETAPAS.md
- registrar que uma etapa de coleta pode apontar para confirmação;
- registrar que o valor válido é persistido na coleta e que `Não` retorna
  para uma nova coleta capaz de sobrescrevê-lo;
- registrar que o candidato deve ser reconstruível pelo histórico;
- manter origem + evento -> destino como única forma de navegação.

PADROES_DE_ARQUITETURA.md
- atualizar triagem de 10–15 para 17–22;
- documentar contexto_atendimento.py e contexto_confirmacoes.py;
- documentar etapas iniciais permitidas 1 e 5;
- documentar sender_base.py e resolver_triagem_base.py;
- registrar que `22 -> 23` envia diretamente a mensagem de agendamento;
- registrar que a etapa 23 inicia a elegibilidade ao funil;
- registrar que a etapa 23 só avança por confirmação explícita encontrada no
  botão ou no texto normalizado;
- registrar que a etapa 24 é terminal por política, não por ser o maior ID;
- registrar que o motor transacional atual não foi redesenhado por este plano.

REGRAS_DE_NEGOCIO.md
- substituir o mapa antigo pelo mapa de 24 etapas;
- registrar veterano por cliente + unidade;
- registrar cliente novo em outra unidade como novato;
- registrar confirmações de nome, dependente, idade e email;
- registrar encerramento sem exclusão de dados;
- registrar que `22 -> 23` é uma transição normal após a sexta resposta;
- registrar que `23 -> 24` exige confirmação explícita do agendamento e que o
  bloqueio de 30 dias pertence somente à etapa 24.
```

### Passo 109 - Ordem segura de aplicação

```text
1. Confirmar backup/commit do estado atual.
2. Atualizar catálogo, mapa e IDs/eventos para as 24 etapas reais.
3. Criar os repositórios de contexto e confirmação.
4. Criar componentes, validadores, mensagens, senders e resolvers novos.
5. Atualizar `valida_historico`, `flow_sender`, efeitos e encerramento como um
   conjunto coerente; em `updates.py` e `movimento_conversa.py`, alterar apenas
   a validação das etapas iniciais 1/5.
6. Remover arquivos substituídos somente depois de zerar os imports antigos.
7. Recriar o banco de desenvolvimento, pois os IDs mudaram de significado.
8. Executar setup_database_aws e migrations Django.
9. Cadastrar novamente unidade e superusuário quando necessário.
10. Executar somente os quatro módulos de teste essenciais definidos acima.
11. Fazer teste manual novato, veterano, dependente, confirmações Não/Sim,
    idade encerrada, transição `22 -> 23`, espera na etapa 23,
    confirmação textual em frase, `23 -> 24`, etapa final e retorno após
    30 dias.
```

### Passo 110 - Definition of done

- Cliente sem conversa anterior na unidade inicia na etapa 5.
- Cliente com conversa encerrada e nome inicia na etapa 1.
- Uma conversa encerrada por idade torna o cliente veterano na próxima
  conversa da mesma unidade, sem apagar qualquer registro anterior.
- O mesmo cliente em outra unidade inicia na etapa 5 daquela unidade.
- Etapa 5 usa `unidade.nome` na saudação.
- Nome, nome do dependente, idade permitida e email são persistidos na coleta.
- Uma resposta `Não` volta à coleta sem apagar ou limpar o valor existente; a
  próxima resposta válida o sobrescreve.
- `Não` retorna exatamente à etapa de coleta.
- Mídia, financeiro e contexto nunca avançam etapa.
- Idade acima de 99, titular abaixo de 18 e dependente abaixo do mínimo da
  unidade encerram na etapa 9 e nunca chegam à confirmação da etapa 10.
- Idade não permitida encerra sem apagar cliente, conversa ou dependente.
- A resposta válida da sexta pergunta produz `22 -> 23` e envia diretamente a
  mensagem de agendamento, sem estado técnico intermediário.
- Etapa 23 torna o lead elegível, permanece ativa e aguarda confirmação.
- O botão `Já agendei` e frases contendo uma expressão aceita produzem
  `23 -> 24`; mensagens sem confirmação recebem tratamento e permanecem em 23.
- Etapa 24 encerra e bloqueia somente cliente + unidade por 30 dias.
- As etapas 23 e 24 são elegíveis ao funil; `lead_no_funil` impede reenvio caso
  a conversa avance antes ou depois do ciclo periódico.
- Após 30 dias, a nova conversa do veterano começa na etapa 1.
- Retry com resposta existente não reenvia mensagem.
- Retry reconstrói candidato pelo histórico e reaplica somente a origem/destino
  exatos.
- Cenário A/B/C, lock, regra de turno, cronologia, cache e webhook preservam o
  comportamento atual.
- Meta-first, commits, reaplicação idempotente, finalização da fila e ordem das
  transações do worker permanecem idênticos aos do projeto atual.
- Nenhum bloco de simulação permanece.
- Nenhum arquivo importa IDs, senders, mensagens ou validadores antigos.

## Impacto em banco e cache

Não há nova coluna nem nova tabela. As mudanças de banco são somente dados de
catálogo (`etapa` e `etapa_transicao`). A estrutura DDL permanece igual.

O banco de desenvolvimento precisa ser recriado porque `id_etapa=1`, por
exemplo, deixa de significar “coleta do nome” e passa a significar “retorno do
veterano”. Atualizar os seeds sobre históricos antigos produziria registros
semanticamente incorretos.

O Redis permanece compatível sem mudança de schema. O cache de bloqueio deriva
da política da etapa 24 e continua com chave cliente + unidade.

## Pontos deliberadamente fora do escopo

- nome diferente por unidade;
- reaproveitar uma conversa encerrada;
- apagar dependente ou histórico;
- envio externo ao Funil de Vendas, além da adaptação da consulta de
  elegibilidade deste plano;
- confirmação real do Calendly/Google Agenda;
- infraestrutura de produção.

Nenhum código deste plano deve ser aplicado parcialmente em uma base que ainda
contenha conversas usando o significado antigo dos IDs.
