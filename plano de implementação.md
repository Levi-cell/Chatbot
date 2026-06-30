# Plano de implementação - transições de etapas

## Objetivo

Substituir completamente a regra genérica `id_etapa_atual + 1` por um mapa
explícito, persistido e protegido de transições:

```text
etapa 1 + nome_cliente_valido       -> etapa 2
etapa 2 + para_mim                  -> etapa 5
etapa 2 + para_outra_pessoa         -> etapa 3
```

A tabela `chatbot.etapa` continuará sendo o catálogo dos estados existentes.
A nova tabela `chatbot.etapa_transicao` será a única fonte de verdade sobre os
movimentos permitidos entre esses estados.

## Escopo e garantias

Este plano reformula somente o estado da conversa e a autorização das
transições. Ele não altera:

- dequeue ou estados `pending`, `processing` e `sent`;
- regra de turno A/B/C do webhook;
- advisory lock e `lock_version` da conversa;
- ordenação por mensagem anterior;
- número de workers da V1;
- política de retry e exclusão;
- vínculo idempotente entre mensagem do cliente e resposta do bot;
- o `if resposta_bot_atual` do `flow_sender`;
- integrações PyWa existentes;
- prioridade dos tratamentos de mídia, financeiro e contexto.

### Estado atual do worktree considerado

O plano foi escrito sobre os arquivos atuais do projeto, incluindo as edições
locais ainda não commitadas:

- `povoar_etapas.py` será substituído integralmente, eliminando as atribuições
  duplicadas de `etapa_4` e `etapa_5` sem descartar a nova intenção das etapas;
- `flow_sender.py` será substituído integralmente pelo contrato novo;
- `main.py` não participa da mudança e permanecerá intocado.

### Duas barreiras contra saltos

Uma transição será validada em dois momentos:

1. **Antes do envio:** o worker consulta o mapa carregado em
   `contexto_historico` e só chama o sender se o evento possuir destino.
2. **Antes do commit:** o `UPDATE` da conversa exige que a combinação
   `origem + evento + destino` ainda exista em `chatbot.etapa_transicao`.

O contexto não vira uma segunda fonte de verdade. Ele contém apenas a fotografia
das transições permitidas para o ciclo atual. O PostgreSQL volta a validar a
mesma aresta na transação final.

### Tratamentos

Mídia, pergunta financeira e resposta fora do contexto:

```text
enviam resposta de tratamento
-> atualizam last_message_from e last_interaction_at
-> não possuem evento_transicao
-> não alteram id_etapa_atual
-> não executam efeitos de transição
```

O primeiro contato permanece uma inicialização especial:

```text
conversa.id_etapa_atual IS NULL
-> envia etapa 1
-> persiste id_etapa_atual = 1
```

Isso não é considerado um salto entre etapas.

### Idempotência e retry

O histórico da mensagem do cliente continua fornecendo a origem estável da
transição. Isso é importante porque, em um retry após commit, a conversa pode
já estar no destino:

```text
mensagem do cliente: id_etapa = 2
resposta existente: id_etapa = 5
conversa atual: id_etapa_atual = 5
```

Nesse caso, o `flow_sender` não envia novamente. Ele reconstrói o evento
`para_mim` pelo mapa `2 -> 5`, reaplica somente efeitos idempotentes e não
retrocede a conversa.

## Passo 1 - Sincronizar o catálogo de etapas por ID

Arquivo completo:
`core/database/deploy/povoar_etapas.py`

```python
import logging

from core.database.connection_aws import get_conn


logger = logging.getLogger("db.seed")


ETAPAS = (
    (1, "Saudação e nome do cliente"),
    (2, "Destino do atendimento"),
    (3, "Nome do dependente"),
    (4, "Idade do dependente"),
    (5, "Oferta de aula experimental e avaliação cognitiva"),
    (6, "Email"),
    (7, "Link de agendamento e entrada no funil"),
)


def insere_etapa_once():
    conn = None

    try:
        conn = get_conn(application_name="script_chatbot")
        cursor = conn.cursor()

        cursor.executemany(
            """
            INSERT INTO chatbot.etapa (id_etapa, nome_etapa)
            VALUES (%s, %s)
            ON CONFLICT (id_etapa)
            DO UPDATE SET nome_etapa = EXCLUDED.nome_etapa;
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

        conn.commit()
        logger.info(
            "banco_seed_ok | acao=sincronizar_etapas quantidade=%s",
            len(ETAPAS),
        )

    except Exception as erro:
        if conn:
            conn.rollback()
        logger.exception(
            "banco_seed_erro | acao=sincronizar_etapas erro=%s",
            erro,
        )
        raise

    finally:
        if conn:
            conn.close()
```

Observações:

- os IDs são estáveis e legíveis;
- a ordem numérica continua ajudando humanos;
- o código não usará essa ordem para decidir a próxima etapa;
- etapas 6 e 7 permanecem cadastradas, mas nenhuma transição nova para elas será
  inventada antes da definição das próximas regras de negócio.

## Passo 2 - Criar e povoar a tabela de transições

Novo arquivo completo:
`core/database/deploy/etapa_transicao_script.py`

```python
import logging

from core.database.connection_aws import get_conn


logger = logging.getLogger("db.etapa_transicao")


TRANSICOES_INICIAIS = (
    (1, "nome_cliente_valido", 2),
    (2, "para_mim", 5),
    (2, "para_outra_pessoa", 3),
)

# Novas arestas só entram quando resolver, sender, efeitos transacionais
# e testes estiverem prontos no mesmo conjunto de mudanças.


def criar_e_povoar_transicoes_etapa():
    conn = None

    try:
        conn = get_conn(application_name="script_chatbot")
        cursor = conn.cursor()

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

        # O deploy mantém uma whitelist exata. Transições antigas ou manuais
        # não sobrevivem silenciosamente a uma nova versão da aplicação.
        cursor.execute("DELETE FROM chatbot.etapa_transicao;")

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

        conn.commit()
        logger.info(
            "etapa_transicao_setup_ok | acao=sincronizar_mapa quantidade=%s",
            len(TRANSICOES_INICIAIS),
        )

    except Exception as erro:
        if conn:
            conn.rollback()
        logger.exception(
            "etapa_transicao_setup_erro | acao=sincronizar_mapa erro=%s",
            erro,
        )
        raise

    finally:
        if conn:
            conn.close()
```

As próximas arestas permanecem documentadas, mas não entram no seed até que
resolver, sender, efeitos transacionais e testes estejam prontos:

```text
3 + nome_dependente_valido -> 4
4 + idade_dependente_valida -> 5
```

O código do deploy não manterá linhas comentadas para o futuro. A intenção fica
na documentação e a whitelist contém somente comportamento executável.

Proteções estruturais:

- uma origem e um evento possuem exatamente um destino;
- uma origem e um destino identificam exatamente um evento;
- não existem auto-saltos; tratamentos não são cadastrados como transições;
- FKs impedem origem ou destino inexistente;
- o seed é uma whitelist exata.

O `DELETE` e os `INSERTS` pertencem à mesma transação. Se qualquer inserção
falhar, o mapa anterior volta integralmente pelo rollback.

## Passo 3 - Integrar a nova tabela ao setup

Arquivo completo:
`core/database/deploy/setup_database.py`

```python
import logging

from core.cache.cache_reset import resetar_cache_redis_dev
from core.database.connection_check import connection_teste_psql
from core.database.deploy.bank_script import (
    configurar_timeouts_avancados,
    criar_funcao_dequeue_message,
    criar_funcoes_lock,
    criar_tabelas,
    definir_timezone_role,
)
from core.database.deploy.cache_control_script import criar_cache_controle
from core.database.deploy.etapa_transicao_script import (
    criar_e_povoar_transicoes_etapa,
)
from core.database.deploy.floodscript import criar_tabelas_bloqueio_flood
from core.database.deploy.povoar_etapas import insere_etapa_once
from core.database.deploy.turno_cliente_script import (
    criar_indices_turno_cliente,
)


logger = logging.getLogger("db.deploy")


def setup_database_aws():
    logger.info("banco_setup_iniciado | acao=configurar_banco")
    connection_teste_psql()
    definir_timezone_role()
    criar_tabelas()
    criar_cache_controle()
    criar_tabelas_bloqueio_flood()
    criar_indices_turno_cliente()
    criar_funcao_dequeue_message()
    criar_funcoes_lock()
    configurar_timeouts_avancados()
    insere_etapa_once()
    criar_e_povoar_transicoes_etapa()

    # Linha exclusiva para DEV/deploy: remove cache antigo dependente do banco
    # e recria unidades.
    resetar_cache_redis_dev()

    logger.info("banco_setup_finalizado | acao=configurar_banco")


if __name__ == "__main__":
    setup_database_aws()
```

A ordem é obrigatória:

```text
cria tabela etapa
-> sincroniza IDs das etapas
-> cria FKs e transições
```

## Passo 4 - Criar o repositório de leitura do mapa

Novo arquivo completo:
`core/repositories/transicoes_etapa.py`

```python
import logging


logger = logging.getLogger("db.transicoes_etapa")


def listar_transicoes_permitidas(id_etapa_origem, cursor):
    if id_etapa_origem is None:
        return {}

    cursor.execute(
        """
        SELECT
            evento,
            id_etapa_destino
        FROM chatbot.etapa_transicao
        WHERE id_etapa_origem = %s
        ORDER BY evento;
        """,
        (id_etapa_origem,),
    )

    transicoes = {
        evento: id_etapa_destino
        for evento, id_etapa_destino in cursor.fetchall()
    }

    logger.debug(
        "transicoes_etapa_consultadas | acao=carregar_mapa etapa_origem=%s quantidade=%s",
        id_etapa_origem,
        len(transicoes),
    )
    return transicoes
```

O repositório somente executa SQL com o cursor recebido. Ele não escolhe evento,
não abre conexão e não controla commit.

## Passo 5 - Criar o pacote de decisões de transição

Novo arquivo completo:
`workers/worker_flow/response_flow/transicoes/__init__.py`

```python
"""Contratos e decisões de transição do fluxo de atendimento."""
```

Novo arquivo completo:
`workers/worker_flow/response_flow/transicoes/eventos.py`

```python
ETAPA_NOME_CLIENTE = 1
ETAPA_DESTINO_ATENDIMENTO = 2
ETAPA_NOME_DEPENDENTE = 3
ETAPA_OFERTA = 5

EVENTO_NOME_CLIENTE_VALIDO = "nome_cliente_valido"
EVENTO_PARA_MIM = "para_mim"
EVENTO_PARA_OUTRA_PESSOA = "para_outra_pessoa"
```

Novo arquivo completo:
`workers/worker_flow/response_flow/transicoes/resolver_transicao.py`

```python
import logging


logger = logging.getLogger("worker.transicao")


class TransicaoEtapaInvalida(ValueError):
    pass


def resolver_destino_transicao(
    contexto_historico,
    evento,
    *,
    destinos_esperados=None,
):
    origem = contexto_historico.get("id_etapa_origem_transicao")
    transicoes = contexto_historico.get("transicoes_permitidas")

    if origem is None:
        raise TransicaoEtapaInvalida(
            "Transicao solicitada sem etapa de origem persistida"
        )

    if not isinstance(transicoes, dict):
        raise TransicaoEtapaInvalida(
            "Mapa de transicoes nao foi carregado no contexto historico"
        )

    destino = transicoes.get(evento)

    if destino is None:
        logger.error(
            "transicao_recusada | motivo=evento_sem_destino etapa_origem=%s evento=%s eventos_disponiveis=%s",
            origem,
            evento,
            sorted(transicoes),
        )
        raise TransicaoEtapaInvalida(
            "Evento nao autorizado para a etapa atual "
            f"(origem={origem}, evento={evento})"
        )

    if destinos_esperados is not None and destino not in set(destinos_esperados):
        logger.critical(
            "transicao_mapa_inconsistente | motivo=destino_incompativel etapa_origem=%s evento=%s destino=%s destinos_esperados=%s",
            origem,
            evento,
            destino,
            sorted(set(destinos_esperados)),
        )
        raise TransicaoEtapaInvalida(
            "Mapa de transicoes possui destino incompativel com o evento "
            f"(origem={origem}, evento={evento}, destino={destino})"
        )

    logger.debug(
        "transicao_resolvida | acao=autorizar_pre_envio etapa_origem=%s evento=%s etapa_destino=%s",
        origem,
        evento,
        destino,
    )
    return destino


def anexar_transicao_ao_contexto_envio(
    contexto_historico,
    contexto_envio,
    evento,
    destino,
):
    origem = contexto_historico.get("id_etapa_origem_transicao")

    if contexto_envio.get("tratamento"):
        raise TransicaoEtapaInvalida(
            "Resposta de tratamento nao pode carregar evento de transicao"
        )

    if contexto_envio.get("id_etapa_resultante") != destino:
        raise TransicaoEtapaInvalida(
            "Sender retornou etapa diferente da transicao autorizada "
            f"(origem={origem}, evento={evento}, destino={destino}, "
            f"sender={contexto_envio.get('id_etapa_resultante')})"
        )

    contexto_com_transicao = dict(contexto_envio)
    contexto_com_transicao.update(
        {
            "id_etapa_origem_transicao": origem,
            "evento_transicao": evento,
            "id_etapa_resultante": destino,
        }
    )
    return contexto_com_transicao


def identificar_evento_por_destino(contexto_historico, destino):
    transicoes = contexto_historico.get("transicoes_permitidas") or {}
    eventos = [
        evento
        for evento, id_destino in transicoes.items()
        if id_destino == destino
    ]

    if not eventos:
        return None

    if len(eventos) != 1:
        raise TransicaoEtapaInvalida(
            "Mais de um evento encontrado para a mesma origem e destino "
            f"(origem={contexto_historico.get('id_etapa_origem_transicao')}, "
            f"destino={destino}, eventos={eventos})"
        )

    return eventos[0]
```

Responsabilidades:

- o repositório lê dados;
- `resolver_transicao.py` decide e valida a navegação;
- os resolvers de cada etapa identificam o evento;
- o sender continua somente enviando a mensagem.

## Passo 6 - Fazer o validador da etapa 2 devolver eventos compartilhados

Arquivo completo:
`workers/worker_flow/response_flow/etapas/validadores_contexto/valida_segunda_etapa.py`

```python
from workers.worker_flow.response_flow.transicoes.eventos import (
    EVENTO_PARA_MIM,
    EVENTO_PARA_OUTRA_PESSOA,
)


OPCAO_PARA_MIM = EVENTO_PARA_MIM
OPCAO_PARA_OUTRA_PESSOA = EVENTO_PARA_OUTRA_PESSOA

TIPO_TRATAMENTO_CONTEXTO_INVALIDO = "opcao_invalida"

_OPCOES_ACEITAS = {
    "para mim": OPCAO_PARA_MIM,
    "para outra pessoa": OPCAO_PARA_OUTRA_PESSOA,
}


def validar_segunda_etapa(conteudo_texto):
    """
    Aceita somente os dois textos exibidos nos botoes da etapa 2.

    O webhook converte a resposta interativa em conteudo_texto. Por isso,
    clique e texto digitado percorrem exatamente a mesma validacao.
    """
    if not isinstance(conteudo_texto, str):
        return None

    texto_normalizado = " ".join(
        conteudo_texto.strip().casefold().split()
    )

    return _OPCOES_ACEITAS.get(texto_normalizado)
```

## Passo 7 - Carregar a fotografia das transições no contexto histórico

Arquivo completo:
`workers/worker_flow/valida_historico.py`

```python
import logging

from core.logging_config import short_value
from core.repositories.inserts import inserir_historico_mensagem_cliente
from core.repositories.querys import buscar_resposta_bot_por_mensagem_cliente
from core.repositories.transicoes_etapa import listar_transicoes_permitidas
from core.repositories.updates import (
    atualizar_conversa_mensagem_cliente,
    atualizar_conversa_resposta_bot_sem_avancar,
)


logger = logging.getLogger("worker.valida_historico")

ETAPA_INICIAL = 1


def valida_historico(mensagem, contexto_banco, cursor):
    contexto_conversa = contexto_banco["conversa"]
    id_conversa = contexto_conversa["id_conversa"]

    last_message_from_entrada = contexto_conversa.get("last_message_from")
    id_etapa_para_insert = _resolver_etapa_cliente(contexto_conversa)

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

    resposta_bot_para_mensagem_atual = _normalizar_resposta_bot(
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

    if resposta_bot_para_mensagem_atual:
        id_etapa_resposta = resposta_bot_para_mensagem_atual["id_etapa"]

        if last_message_from_entrada != "bot":
            atualizar_conversa_resposta_bot_sem_avancar(
                id_conversa,
                resposta_bot_para_mensagem_atual["received_data_hora"],
                cursor,
            )

        last_message_from_saida = "bot"
    else:
        id_etapa_resposta = _resolver_previsao_resposta(
            contexto_conversa,
            transicoes_permitidas,
        )
        atualizar_conversa_mensagem_cliente(
            id_conversa,
            data_historico_cliente,
            cursor,
        )
        last_message_from_saida = "cliente"

    logger.info(
        "historico_validado | acao=registrar_cliente id_mensagem=%s id_historico=%s inserido=%s id_conversa=%s etapa_cliente=%s etapa_resposta_previa=%s eventos_transicao=%s last_from_entrada=%s last_from_saida=%s retry=%s resposta_bot_existente=%s cliente=%s phone_number_id=%s",
        mensagem["id_mensagem"],
        id_historico_cliente,
        cliente_inserido_no_historico,
        id_conversa,
        id_etapa_cliente,
        id_etapa_resposta,
        sorted(transicoes_permitidas),
        last_message_from_entrada,
        last_message_from_saida,
        mensagem["retry_count"],
        bool(resposta_bot_para_mensagem_atual),
        short_value(mensagem["cliente_telefone"]),
        short_value(mensagem["id_phone_unidade"]),
    )

    return {
        "id_conversa": id_conversa,
        "id_etapa_atual": contexto_conversa.get("id_etapa_atual"),
        "id_etapa_cliente": id_etapa_cliente,
        # Compatibilidade apenas para logs existentes. Este campo nunca decide
        # uma transicao e pode ser None quando ha mais de um destino.
        "id_etapa_resposta": id_etapa_resposta,
        "id_etapa_origem_transicao": id_etapa_cliente,
        "transicoes_permitidas": transicoes_permitidas,
        "status_dependente": contexto_conversa.get("status_dependente"),
        "last_message_from": last_message_from_saida,
        "last_message_from_entrada": last_message_from_entrada,
        "mensagem_cliente_atual": mensagem_cliente_atual,
        "mensagem_cliente_inserida": cliente_inserido_no_historico,
        "resposta_bot_para_mensagem_atual": resposta_bot_para_mensagem_atual,
        "texto_cliente_atual": mensagem["conteudo_texto"],
        "tipo_mensagem_atual": mensagem["tipo_mensagem"],
        "retry_count": mensagem["retry_count"],
        "precisa_tratamento_erro": False,
        "motivo_tratamento_erro": None,
    }


def _resolver_etapa_cliente(contexto_conversa):
    id_etapa_atual = contexto_conversa.get("id_etapa_atual")

    if id_etapa_atual is None:
        return ETAPA_INICIAL

    return id_etapa_atual


def _resolver_previsao_resposta(
    contexto_conversa,
    transicoes_permitidas,
):
    if contexto_conversa.get("id_etapa_atual") is None:
        return ETAPA_INICIAL

    destinos = set(transicoes_permitidas.values())

    if len(destinos) == 1:
        return destinos.pop()

    return None


def _normalizar_linha_historico(registro):
    (
        id_mensagem,
        id_conversa,
        id_etapa,
        received_data_hora,
        cliente_telefone,
        conteudo_texto,
        tipo_mensagem,
        id_hash_msg,
        id_mensagem_fila,
        id_hash_cliente_origem,
        id_phone_unidade,
        unidade_telefone,
        quem_enviou,
        status_envio,
    ) = registro

    return {
        "id_mensagem": id_mensagem,
        "id_conversa": id_conversa,
        "id_etapa": id_etapa,
        "received_data_hora": received_data_hora,
        "cliente_telefone": cliente_telefone,
        "conteudo_texto": conteudo_texto,
        "tipo_mensagem": tipo_mensagem,
        "id_hash_msg": id_hash_msg,
        "id_mensagem_fila": id_mensagem_fila,
        "id_hash_cliente_origem": id_hash_cliente_origem,
        "id_phone_unidade": id_phone_unidade,
        "unidade_telefone": unidade_telefone,
        "quem_enviou": quem_enviou,
        "status_envio": status_envio,
    }


def _normalizar_resposta_bot(registro):
    if not registro:
        return None

    return _normalizar_linha_historico(registro)
```

Ponto importante: a origem é `id_etapa_cliente`, retornada pelo histórico
persistido. Ela não é recalculada a partir da etapa atual da conversa. Portanto,
continua correta em retries nos quais a conversa já chegou ao destino.

## Passo 8 - Autorizar a transição 1 -> 2 antes do sender

Arquivo completo:
`workers/worker_flow/response_flow/etapas/primeira_etapa.py`

```python
import logging

from core.integrations.whatsapp.pywa_functions.pywa_senders.etapa1 import (
    enviar_primeira_etapa,
    enviar_primeira_etapa_contexto_nome_invalido,
    enviar_primeira_etapa_financeiro,
    enviar_primeira_etapa_financeiro_inicio,
    enviar_primeira_etapa_midia,
    enviar_primeira_etapa_midia_inicio,
)
from core.integrations.whatsapp.pywa_functions.pywa_senders.etapa2 import (
    enviar_segunda_etapa,
)
from core.logging_config import short_value
from workers.worker_flow.response_flow.etapas.validadores_universais.validador_financeiro import (
    TIPO_TRATAMENTO_FINANCEIRO,
    validar_pergunta_financeira,
)
from workers.worker_flow.response_flow.etapas.validadores_universais.validador_midia import (
    TIPO_TRATAMENTO_TIPO_NAO_SUPORTADO,
    validar_midia,
)
from workers.worker_flow.response_flow.etapas.validadores_universais.validador_nome import (
    TIPO_TRATAMENTO_NOME_INVALIDO,
    validar_nome_cliente,
)
from workers.worker_flow.response_flow.transicoes.eventos import (
    ETAPA_DESTINO_ATENDIMENTO,
    EVENTO_NOME_CLIENTE_VALIDO,
)
from workers.worker_flow.response_flow.transicoes.resolver_transicao import (
    anexar_transicao_ao_contexto_envio,
    resolver_destino_transicao,
)


"""
ESSE ARQUIVO TEM DUAS RESPONSABILIDADES

- VALIDAR PRIMEIRA ETAPA
- ENCAMINHAR PARA SEGUNDA ETAPA
"""


logger = logging.getLogger("worker.primeira_etapa")


def resolve_primeira_etapa(contexto_historico):
    """
    id_etapa_atual is None não é uma etapa separada.
    É apenas o primeiro contato antes da etapa 1 ser persistida.

    Nome inválido, mídia e pergunta financeira possuem tratamento próprio.
    Somente nome válido produz o evento nome_cliente_valido.
    """
    id_conversa = contexto_historico["id_conversa"]
    id_etapa_atual = contexto_historico.get("id_etapa_atual")
    tipo_mensagem = contexto_historico.get("tipo_mensagem_atual")
    texto_cliente = contexto_historico.get("texto_cliente_atual") or ""
    mensagem_cliente_atual = contexto_historico["mensagem_cliente_atual"]
    cliente_telefone = mensagem_cliente_atual["cliente_telefone"]
    phone_id_unidade = mensagem_cliente_atual["id_phone_unidade"]

    conversa_sem_etapa = id_etapa_atual is None

    # Mídia tem prioridade sobre todas as validações de texto.
    if validar_midia(tipo_mensagem):
        _logar_tipo_nao_suportado(contexto_historico)

        if conversa_sem_etapa:
            return enviar_primeira_etapa_midia_inicio(
                cliente_telefone,
                phone_id_unidade,
            )

        return enviar_primeira_etapa_midia(
            cliente_telefone,
            phone_id_unidade,
        )

    # Pergunta financeira tem prioridade sobre a validação de nome.
    if validar_pergunta_financeira(texto_cliente):
        _logar_tratamento_texto(
            contexto_historico,
            TIPO_TRATAMENTO_FINANCEIRO,
        )

        if conversa_sem_etapa:
            return enviar_primeira_etapa_financeiro_inicio(
                cliente_telefone,
                phone_id_unidade,
            )

        return enviar_primeira_etapa_financeiro(
            cliente_telefone,
            phone_id_unidade,
        )

    # Primeiro contato normal: inicializa a conversa na etapa 1.
    if conversa_sem_etapa:
        return enviar_primeira_etapa(
            cliente_telefone,
            phone_id_unidade,
        )

    resultado_nome = validar_nome_cliente(texto_cliente)

    if not resultado_nome.valido:
        _logar_tratamento_texto(
            contexto_historico,
            TIPO_TRATAMENTO_NOME_INVALIDO,
            motivo_detalhado=resultado_nome.motivo,
        )

        return enviar_primeira_etapa_contexto_nome_invalido(
            cliente_telefone,
            phone_id_unidade,
        )

    # A tabela precisa autorizar 1 + nome_cliente_valido -> 2 antes da
    # comunicação externa. Mapa ausente ou incorreto impede o envio.
    etapa_destino = resolver_destino_transicao(
        contexto_historico,
        EVENTO_NOME_CLIENTE_VALIDO,
        destinos_esperados={ETAPA_DESTINO_ATENDIMENTO},
    )

    logger.debug(
        "primeira_etapa_nome_validado | acao=enviar_etapa_destino id_conversa=%s evento=%s etapa_destino=%s primeiro_nome=%s",
        id_conversa,
        EVENTO_NOME_CLIENTE_VALIDO,
        etapa_destino,
        short_value(resultado_nome.primeiro_nome),
    )

    contexto_envio = enviar_segunda_etapa(
        cliente_telefone,
        phone_id_unidade,
        nome=resultado_nome.primeiro_nome,
    )
    contexto_envio["primeiro_nome_cliente"] = resultado_nome.primeiro_nome

    return anexar_transicao_ao_contexto_envio(
        contexto_historico,
        contexto_envio,
        EVENTO_NOME_CLIENTE_VALIDO,
        etapa_destino,
    )


def _logar_tipo_nao_suportado(contexto_historico):
    mensagem_cliente_atual = contexto_historico["mensagem_cliente_atual"]

    logger.info(
        "resposta_cliente_invalida | motivo=tipo_mensagem_nao_suportado acao=tratar_sem_avancar id_conversa=%s id_mensagem_fila=%s cliente=%s phone_number_id=%s tipo=%s etapa_cliente=%s",
        contexto_historico["id_conversa"],
        mensagem_cliente_atual["id_mensagem_fila"],
        short_value(mensagem_cliente_atual["cliente_telefone"]),
        short_value(mensagem_cliente_atual["id_phone_unidade"]),
        contexto_historico.get("tipo_mensagem_atual"),
        contexto_historico["id_etapa_cliente"],
    )


def _logar_tratamento_texto(
    contexto_historico,
    motivo,
    *,
    motivo_detalhado=None,
):
    mensagem_cliente_atual = contexto_historico["mensagem_cliente_atual"]

    logger.info(
        "resposta_cliente_tratamento | motivo=%s motivo_detalhado=%s acao=tratar_sem_avancar id_conversa=%s id_mensagem_fila=%s cliente=%s phone_number_id=%s etapa_cliente=%s",
        motivo,
        motivo_detalhado,
        contexto_historico["id_conversa"],
        mensagem_cliente_atual["id_mensagem_fila"],
        short_value(mensagem_cliente_atual["cliente_telefone"]),
        short_value(mensagem_cliente_atual["id_phone_unidade"]),
        contexto_historico["id_etapa_cliente"],
    )
```

## Passo 9 - Fazer a etapa 2 escolher 3 ou 5 pelo mapa

Arquivo completo:
`workers/worker_flow/response_flow/etapas/segunda_etapa.py`

```python
import logging

from core.integrations.whatsapp.pywa_functions.pywa_senders.etapa2 import (
    enviar_segunda_etapa_contexto_opcao_invalida,
    enviar_segunda_etapa_financeiro,
    enviar_segunda_etapa_midia,
)
from core.logging_config import short_value
from workers.worker_flow.response_flow.etapas.validadores_contexto.valida_segunda_etapa import (
    OPCAO_PARA_MIM,
    OPCAO_PARA_OUTRA_PESSOA,
    TIPO_TRATAMENTO_CONTEXTO_INVALIDO,
    validar_segunda_etapa,
)
from workers.worker_flow.response_flow.etapas.validadores_universais.validador_financeiro import (
    TIPO_TRATAMENTO_FINANCEIRO,
    validar_pergunta_financeira,
)
from workers.worker_flow.response_flow.etapas.validadores_universais.validador_midia import (
    validar_midia,
)
from workers.worker_flow.response_flow.transicoes.eventos import (
    ETAPA_NOME_DEPENDENTE,
    ETAPA_OFERTA,
)
from workers.worker_flow.response_flow.transicoes.resolver_transicao import (
    anexar_transicao_ao_contexto_envio,
    resolver_destino_transicao,
)


"""
ESSE ARQUIVO TEM DUAS RESPONSABILIDADES

- VALIDAR A SEGUNDA ETAPA
- ENCAMINHAR PARA A ETAPA AUTORIZADA PELO MAPA
"""


logger = logging.getLogger("worker.segunda_etapa")


def resolve_segunda_etapa(contexto_historico):
    """
    Mídia, financeiro e contexto inválido recebem tratamento sem avançar.

    para_mim resolve 2 -> 5.
    para_outra_pessoa resolve 2 -> 3.

    Enquanto os senders reais das etapas 3 e 5 não existem, a resposta
    continua simulada. A simulação não altera a autorização da transição.
    """
    id_conversa = contexto_historico["id_conversa"]
    tipo_mensagem = contexto_historico.get("tipo_mensagem_atual")
    texto_cliente = contexto_historico.get("texto_cliente_atual") or ""
    mensagem_cliente_atual = contexto_historico["mensagem_cliente_atual"]
    cliente_telefone = mensagem_cliente_atual["cliente_telefone"]
    phone_id_unidade = mensagem_cliente_atual["id_phone_unidade"]

    if validar_midia(tipo_mensagem):
        _logar_tipo_nao_suportado(contexto_historico)

        return enviar_segunda_etapa_midia(
            cliente_telefone,
            phone_id_unidade,
        )

    if validar_pergunta_financeira(texto_cliente):
        _logar_tratamento_texto(
            contexto_historico,
            TIPO_TRATAMENTO_FINANCEIRO,
        )

        return enviar_segunda_etapa_financeiro(
            cliente_telefone,
            phone_id_unidade,
        )

    evento_transicao = validar_segunda_etapa(texto_cliente)

    if evento_transicao is None:
        _logar_tratamento_texto(
            contexto_historico,
            TIPO_TRATAMENTO_CONTEXTO_INVALIDO,
        )

        return enviar_segunda_etapa_contexto_opcao_invalida(
            cliente_telefone,
            phone_id_unidade,
        )

    destinos_esperados = _destinos_esperados_por_evento(evento_transicao)
    etapa_destino = resolver_destino_transicao(
        contexto_historico,
        evento_transicao,
        destinos_esperados=destinos_esperados,
    )
    status_dependente = (
        evento_transicao == OPCAO_PARA_OUTRA_PESSOA
    )

    # TEMPORÁRIO: substituir a simulação pelo sender da etapa retornada.
    # A autorização por origem + evento + destino permanece definitiva.
    logger.info(
        "nesse momento a futura etapa %s foi enviada | acao=simular_envio_etapa id_conversa=%s id_mensagem_fila=%s evento=%s status_dependente=%s",
        etapa_destino,
        id_conversa,
        mensagem_cliente_atual["id_mensagem_fila"],
        evento_transicao,
        status_dependente,
    )

    contexto_envio = _montar_contexto_etapa_simulada(
        contexto_historico,
        etapa_destino,
        evento_transicao,
        status_dependente,
    )

    return anexar_transicao_ao_contexto_envio(
        contexto_historico,
        contexto_envio,
        evento_transicao,
        etapa_destino,
    )


def _destinos_esperados_por_evento(evento_transicao):
    if evento_transicao == OPCAO_PARA_MIM:
        return {ETAPA_OFERTA}

    if evento_transicao == OPCAO_PARA_OUTRA_PESSOA:
        return {ETAPA_NOME_DEPENDENTE}

    return set()


def _montar_contexto_etapa_simulada(
    contexto_historico,
    etapa_destino,
    evento_transicao,
    status_dependente,
):
    # TEMPORÁRIO: representa somente o ponto em que o sender real será
    # chamado. Remover envio_simulado quando as etapas 3 e 5 existirem.
    mensagem_cliente = contexto_historico["mensagem_cliente_atual"]
    id_mensagem_fila = mensagem_cliente["id_mensagem_fila"]

    return {
        "enviou": True,
        "envio_simulado": True,
        "resposta_ja_existia": False,
        "mensagem_bot": (
            f"Nesse momento a futura etapa {etapa_destino} foi enviada."
        ),
        "id_hash_msg_bot": (
            f"simulacao.etapa{etapa_destino}.fila.{id_mensagem_fila}"
        ),
        "id_etapa_resultante": etapa_destino,
        "tipo_mensagem": "simulacao",
        "canal": "simulacao_worker",
        "atualizar_conversa": True,
        "atualizar_last_from_bot": True,
        "opcao_atendimento": evento_transicao,
        "status_dependente": status_dependente,
    }


def _logar_tipo_nao_suportado(contexto_historico):
    mensagem_cliente_atual = contexto_historico["mensagem_cliente_atual"]

    logger.info(
        "resposta_cliente_invalida | motivo=tipo_mensagem_nao_suportado acao=tratar_sem_avancar id_conversa=%s id_mensagem_fila=%s cliente=%s phone_number_id=%s tipo=%s etapa_cliente=%s",
        contexto_historico["id_conversa"],
        mensagem_cliente_atual["id_mensagem_fila"],
        short_value(mensagem_cliente_atual["cliente_telefone"]),
        short_value(mensagem_cliente_atual["id_phone_unidade"]),
        contexto_historico.get("tipo_mensagem_atual"),
        contexto_historico["id_etapa_cliente"],
    )


def _logar_tratamento_texto(contexto_historico, motivo):
    mensagem_cliente_atual = contexto_historico["mensagem_cliente_atual"]

    logger.info(
        "resposta_cliente_tratamento | motivo=%s motivo_detalhado=%s acao=tratar_sem_avancar id_conversa=%s id_mensagem_fila=%s cliente=%s phone_number_id=%s etapa_cliente=%s",
        motivo,
        None,
        contexto_historico["id_conversa"],
        mensagem_cliente_atual["id_mensagem_fila"],
        short_value(mensagem_cliente_atual["cliente_telefone"]),
        short_value(mensagem_cliente_atual["id_phone_unidade"]),
        contexto_historico["id_etapa_cliente"],
    )
```

## Passo 10 - Preservar a idempotência no flow_sender

Arquivo completo:
`workers/worker_flow/response_flow/flow_sender.py`

```python
import logging

from workers.worker_flow.response_flow.etapas.primeira_etapa import (
    resolve_primeira_etapa,
)
from workers.worker_flow.response_flow.etapas.segunda_etapa import (
    resolve_segunda_etapa,
)
from workers.worker_flow.response_flow.transicoes.resolver_transicao import (
    identificar_evento_por_destino,
)


logger = logging.getLogger("worker.sender")


def flow_sender(contexto_historico):
    id_conversa = contexto_historico["id_conversa"]
    id_etapa_atual = contexto_historico.get("id_etapa_atual")
    retry_count = contexto_historico["retry_count"]

    mensagem_cliente_atual = contexto_historico["mensagem_cliente_atual"]
    cliente_atual_id_mensagem_fila = mensagem_cliente_atual["id_mensagem_fila"]
    cliente_atual_id_hash_msg = mensagem_cliente_atual["id_hash_msg"]

    resposta_bot_atual = (
        contexto_historico["resposta_bot_para_mensagem_atual"] or {}
    )

    # Esta barreira continua antes de qualquer resolver ou sender.
    if resposta_bot_atual:
        id_etapa_resposta = resposta_bot_atual.get("id_etapa")
        evento_transicao = identificar_evento_por_destino(
            contexto_historico,
            id_etapa_resposta,
        )

        logger.info(
            "flow_sender_idempotencia_ok | motivo=resposta_bot_ja_registrada acao=nao_enviar id_conversa=%s id_mensagem_fila=%s id_hash_cliente=%s id_resposta_bot=%s etapa_resposta=%s evento_transicao=%s retry=%s",
            id_conversa,
            cliente_atual_id_mensagem_fila,
            cliente_atual_id_hash_msg,
            resposta_bot_atual.get("id_mensagem"),
            id_etapa_resposta,
            evento_transicao,
            retry_count,
        )

        contexto_envio = {
            "enviou": False,
            "resposta_ja_existia": True,
            "id_hash_msg_bot": resposta_bot_atual.get("id_hash_msg"),
            "id_etapa_resultante": id_etapa_resposta,
            "id_etapa_origem_transicao": contexto_historico.get(
                "id_etapa_origem_transicao"
            ),
        }

        if evento_transicao:
            contexto_envio["evento_transicao"] = evento_transicao

        return contexto_envio

    if retry_count > 1:
        logger.info(
            "flow_sender_reprocessamento | motivo=retry_maior_que_um acao=continuar_sem_resposta_previa id_conversa=%s id_mensagem_fila=%s id_hash_cliente=%s retry=%s",
            id_conversa,
            cliente_atual_id_mensagem_fila,
            cliente_atual_id_hash_msg,
            retry_count,
        )

    if id_etapa_atual is None or id_etapa_atual == 1:
        return resolve_primeira_etapa(contexto_historico)

    if id_etapa_atual == 2:
        return resolve_segunda_etapa(contexto_historico)

    logger.warning(
        "flow_sender_etapa_pendente | acao=nao_enviar id_conversa=%s etapa_atual=%s",
        id_conversa,
        id_etapa_atual,
    )
    raise NotImplementedError(
        f"Resolver da etapa {id_etapa_atual} ainda nao implementado"
    )
```

O fluxo continua parando no histórico existente. A novidade é que o evento
também é reconstruído para os efeitos idempotentes:

```text
origem 2 + resposta existente na etapa 5
-> evento para_mim
-> nenhum novo envio
-> efeitos da transição podem ser reaplicados com segurança
```

## Passo 11 - Substituir a proteção aritmética por SQL relacional

Arquivo completo:
`core/repositories/updates.py`

```python
import logging

from core.logging_config import short_value


logger = logging.getLogger("db.updates")

ETAPA_INICIAL = 1


def marcar_mensagem_como_enviada(id_mensagem, cursor):
    cursor.execute(
        """
        UPDATE chatbot.fila_mensagens
        SET status = 'sent',
            processing_started_at = NULL,
            last_error = NULL
        WHERE id_mensagem = %s
        """,
        (id_mensagem,),
    )
    logger.debug(
        "fila_update | acao=marcar_sent id_mensagem=%s linhas=%s",
        id_mensagem,
        cursor.rowcount,
    )


def vincular_mensagem_fila_a_conversa(id_mensagem, id_conversa, cursor):
    cursor.execute(
        """
        UPDATE chatbot.fila_mensagens
        SET id_conversa = %s
        WHERE id_mensagem = %s
          AND (
              id_conversa IS NULL
              OR id_conversa = %s
          );
        """,
        (id_conversa, id_mensagem, id_conversa),
    )
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

    cursor.execute(
        """
        UPDATE chatbot.conversa
        SET
            last_message_from = 'cliente',
            last_interaction_at = %s
        WHERE id_conversa = %s;
        """,
        (data_interacao, id_conversa),
    )

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
    if id_etapa_resultante != ETAPA_INICIAL:
        raise ValueError(
            "Inicializacao da conversa so pode persistir a etapa 1"
        )

    _validar_data_interacao_bot(data_interacao)

    cursor.execute(
        """
        UPDATE chatbot.conversa
        SET
            id_etapa_atual = %s,
            last_message_from = 'bot',
            last_interaction_at = %s
        WHERE id_conversa = %s
          AND id_etapa_atual IS NULL;
        """,
        (id_etapa_resultante, data_interacao, id_conversa),
    )

    logger.debug(
        "conversa_update | acao=inicializar_etapa id_conversa=%s etapa=%s linhas=%s",
        id_conversa,
        id_etapa_resultante,
        cursor.rowcount,
    )

    if cursor.rowcount != 1:
        raise ValueError(
            "Conversa nao foi inicializada na etapa 1 "
            f"(id_conversa={id_conversa}, linhas={cursor.rowcount})"
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

    cursor.execute(
        """
        UPDATE chatbot.conversa
        SET
            last_message_from = 'bot',
            last_interaction_at = %s
        WHERE id_conversa = %s;
        """,
        (data_interacao, id_conversa),
    )

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
        raise ValueError(
            "waid_telefone nao informado para atualizar nome do cliente"
        )

    if not nome:
        raise ValueError("nome nao informado para atualizar cliente")

    cursor.execute(
        """
        UPDATE chatbot.cliente
        SET nome = %s
        WHERE waid_telefone = %s;
        """,
        (nome, waid_telefone),
    )

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


def atualizar_status_dependente_conversa(
    id_conversa,
    status_dependente,
    cursor,
):
    cursor.execute(
        """
        UPDATE chatbot.conversa
        SET status_dependente = %s
        WHERE id_conversa = %s;
        """,
        (bool(status_dependente), id_conversa),
    )

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
    cursor.execute(
        """
        UPDATE chatbot.fila_mensagens
        SET
            status = 'pending',
            next_attempt_at = NOW() + (%s * INTERVAL '1 second'),
            processing_started_at = NULL,
            retry_count = GREATEST(COALESCE(retry_count, 0) - 1, 0),
            last_error = NULL
        WHERE id_mensagem = %s;
        """,
        (delay_seconds, id_mensagem),
    )
    logger.debug(
        "fila_update | acao=reagendar_sem_erro id_mensagem=%s delay=%s linhas=%s",
        id_mensagem,
        delay_seconds,
        cursor.rowcount,
    )
    return cursor.rowcount


def reagendar_mensagem(id_mensagem, erro, max_retry, cursor):
    cursor.execute(
        """
        UPDATE chatbot.fila_mensagens
        SET
            status = 'pending',
            next_attempt_at = NOW() + INTERVAL '2 minutes',
            processing_started_at = NULL,
            last_error = %s
        WHERE id_mensagem = %s AND retry_count < %s;
        """,
        (str(erro), id_mensagem, max_retry),
    )
    logger.debug(
        "fila_update | acao=reagendar_com_erro id_mensagem=%s max_retry=%s linhas=%s",
        id_mensagem,
        max_retry,
        cursor.rowcount,
    )
    return cursor.rowcount
```

Essa substituição remove totalmente:

```text
GREATEST(id_etapa_atual, destino)
destino <= id_etapa_atual + 1
```

Uma nova resposta exige que a conversa ainda esteja na origem. Uma resposta
idempotente aceita somente a origem, como reparo, ou exatamente o destino, como
confirmação. Qualquer terceira etapa é rejeitada antes que um retry antigo
altere `last_message_from` ou `last_interaction_at`.

## Passo 12 - Persistir navegação e efeitos de negócio separadamente

Arquivo completo:
`workers/worker_flow/transacoes/persistencia_resposta.py`

```python
import logging

from core.logging_config import short_value
from core.repositories.inserts import (
    inserir_dependente_para_conversa,
    inserir_historico_mensagem_bot,
)
from core.repositories.updates import (
    atualizar_conversa_por_transicao,
    atualizar_conversa_resposta_bot_sem_avancar,
    atualizar_nome_cliente_por_telefone,
    atualizar_status_dependente_conversa,
    inicializar_conversa_resposta_bot,
)
from workers.worker_flow.response_flow.etapas.validadores_universais.validador_nome import (
    validar_nome_cliente,
)
from workers.worker_flow.response_flow.transicoes.eventos import (
    ETAPA_DESTINO_ATENDIMENTO,
    ETAPA_NOME_CLIENTE,
    ETAPA_NOME_DEPENDENTE,
    ETAPA_OFERTA,
    EVENTO_NOME_CLIENTE_VALIDO,
    EVENTO_PARA_MIM,
    EVENTO_PARA_OUTRA_PESSOA,
)


logger = logging.getLogger("worker.support")

MOVIMENTO_INICIALIZACAO = "inicializacao"
MOVIMENTO_TRANSICAO = "transicao"
MOVIMENTO_SEM_AVANCO = "sem_avanco"


def _obter_data_interacao_bot_existente(contexto_historico):
    resposta_bot = (
        contexto_historico.get("resposta_bot_para_mensagem_atual") or {}
    )
    data_interacao = resposta_bot.get("received_data_hora")

    if data_interacao is None:
        raise ValueError(
            "Resposta do bot existente sem received_data_hora persistido"
        )

    return data_interacao


def atualizar_banco_com_contexto_final(
    contexto_historico,
    contexto_envio,
    cursor,
):
    id_conversa = contexto_historico["id_conversa"]
    id_etapa_resultante = contexto_envio.get("id_etapa_resultante")
    resposta_ja_existia = bool(
        contexto_envio.get("resposta_ja_existia")
    )

    if resposta_ja_existia:
        data_interacao_bot = _obter_data_interacao_bot_existente(
            contexto_historico
        )
        historico_bot_inserido = False
        id_historico_bot = None
    else:
        if not contexto_envio.get("enviou"):
            raise ValueError(
                "Contexto de envio sem resposta enviada e sem resposta existente"
            )

        (
            id_historico_bot,
            data_interacao_bot,
            historico_bot_inserido,
        ) = inserir_historico_mensagem_bot(
            contexto_historico,
            contexto_envio,
            cursor,
        )

    movimento = _persistir_estado_conversa(
        contexto_historico,
        contexto_envio,
        data_interacao_bot,
        cursor,
    )

    efeitos_transicao = atualizar_banco_conforme_transicao_de_etapa(
        contexto_historico,
        contexto_envio,
        cursor,
    )

    logger.info(
        "resposta_bot_persistida | acao=registrar_historico_e_contexto id_conversa=%s id_historico_bot=%s inserido=%s resposta_ja_existia=%s movimento=%s etapa=%s evento=%s id_hash_msg_bot=%s",
        id_conversa,
        id_historico_bot,
        historico_bot_inserido,
        resposta_ja_existia,
        movimento,
        id_etapa_resultante,
        contexto_envio.get("evento_transicao"),
        contexto_envio.get("id_hash_msg_bot"),
    )

    contexto_final = {
        "historico_bot_inserido": historico_bot_inserido,
        "resposta_ja_existia": resposta_ja_existia,
        "id_hash_msg_bot": contexto_envio.get("id_hash_msg_bot"),
        "id_etapa_resultante": id_etapa_resultante,
        "movimento_conversa": movimento,
        "atualizar_conversa": movimento != MOVIMENTO_SEM_AVANCO,
        "atualizar_last_from_bot": True,
    }

    if id_historico_bot is not None:
        contexto_final.update(
            {
                "id_historico_bot": id_historico_bot,
                "data_historico_bot": data_interacao_bot,
            }
        )

    if efeitos_transicao:
        contexto_final["efeitos_transicao"] = efeitos_transicao

    return contexto_final


def _persistir_estado_conversa(
    contexto_historico,
    contexto_envio,
    data_interacao_bot,
    cursor,
):
    movimento = _resolver_movimento_conversa(
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


def _resolver_movimento_conversa(
    contexto_historico,
    contexto_envio,
):
    etapa_atual = contexto_historico.get("id_etapa_atual")
    etapa_origem = contexto_historico.get(
        "id_etapa_origem_transicao"
    )
    etapa_destino = contexto_envio.get("id_etapa_resultante")
    evento_transicao = contexto_envio.get("evento_transicao")
    tratamento = bool(contexto_envio.get("tratamento"))

    if etapa_destino is None:
        raise ValueError("Resposta do bot sem id_etapa_resultante")

    if etapa_atual is None:
        if etapa_destino != ETAPA_NOME_CLIENTE:
            raise ValueError(
                "Conversa sem etapa so pode ser inicializada na etapa 1"
            )

        if evento_transicao:
            raise ValueError(
                "Inicializacao da conversa nao aceita evento de transicao"
            )

        return MOVIMENTO_INICIALIZACAO

    if evento_transicao:
        if tratamento:
            raise ValueError(
                "Tratamento nao pode avancar por evento de transicao"
            )

        if etapa_origem is None:
            raise ValueError(
                "Evento de transicao sem etapa de origem persistida"
            )

        return MOVIMENTO_TRANSICAO

    if etapa_destino != etapa_origem:
        raise ValueError(
            "Resposta sem evento tentou alterar a etapa da conversa "
            f"(origem={etapa_origem}, destino={etapa_destino})"
        )

    return MOVIMENTO_SEM_AVANCO


def atualizar_banco_conforme_transicao_de_etapa(
    contexto_historico,
    contexto_envio,
    cursor,
):
    """
    A tabela etapa_transicao controla a navegação.

    Esta função continua necessária para os efeitos de negócio produzidos por
    cada aresta: salvar nome, definir status_dependente e criar dependente.
    Ela não escolhe nem altera o destino da conversa.
    """
    evento_transicao = contexto_envio.get("evento_transicao")

    if not evento_transicao:
        return None

    etapa_origem = contexto_historico.get(
        "id_etapa_origem_transicao"
    )
    etapa_destino = contexto_envio.get("id_etapa_resultante")

    if evento_transicao == EVENTO_NOME_CLIENTE_VALIDO:
        _exigir_aresta(
            etapa_origem,
            etapa_destino,
            ETAPA_NOME_CLIENTE,
            ETAPA_DESTINO_ATENDIMENTO,
            evento_transicao,
        )
        return _persistir_nome_cliente_capturado_na_etapa_1(
            contexto_historico,
            contexto_envio,
            cursor,
        )

    if evento_transicao in {
        EVENTO_PARA_MIM,
        EVENTO_PARA_OUTRA_PESSOA,
    }:
        destino_esperado = (
            ETAPA_OFERTA
            if evento_transicao == EVENTO_PARA_MIM
            else ETAPA_NOME_DEPENDENTE
        )
        _exigir_aresta(
            etapa_origem,
            etapa_destino,
            ETAPA_DESTINO_ATENDIMENTO,
            destino_esperado,
            evento_transicao,
        )
        return _persistir_destino_atendimento_da_etapa_2(
            contexto_historico,
            evento_transicao,
            cursor,
        )

    raise ValueError(
        f"Evento de transicao sem efeitos conhecidos: {evento_transicao}"
    )


def _exigir_aresta(
    etapa_origem,
    etapa_destino,
    origem_esperada,
    destino_esperado,
    evento_transicao,
):
    if (
        etapa_origem != origem_esperada
        or etapa_destino != destino_esperado
    ):
        raise ValueError(
            "Efeito de transicao recebeu aresta incompativel "
            f"(evento={evento_transicao}, origem={etapa_origem}, "
            f"destino={etapa_destino}, origem_esperada={origem_esperada}, "
            f"destino_esperado={destino_esperado})"
        )


def _persistir_nome_cliente_capturado_na_etapa_1(
    contexto_historico,
    contexto_envio,
    cursor,
):
    primeiro_nome = _resolver_primeiro_nome_cliente(
        contexto_historico,
        contexto_envio,
    )

    if not primeiro_nome:
        print(
            "\n"
            "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!\n"
            "!!! NOME VAZIO NA TRANSICAO 1 -> 2: ANOMALIA RARA E CRITICA !!!\n"
            "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!\n"
        )
        logger.critical(
            "cliente_nome_anomalia_critica | motivo=nome_vazio_na_transicao_1_2 acao=rollback_e_retry id_conversa=%s etapa_origem=%s etapa_resultante=%s",
            contexto_historico["id_conversa"],
            contexto_historico.get("id_etapa_origem_transicao"),
            contexto_envio.get("id_etapa_resultante"),
        )
        raise ValueError(
            "Nome do cliente nao foi resolvido na transicao 1 -> 2"
        )

    mensagem_cliente = contexto_historico["mensagem_cliente_atual"]
    cliente_telefone = mensagem_cliente["cliente_telefone"]

    atualizar_nome_cliente_por_telefone(
        cliente_telefone,
        primeiro_nome,
        cursor,
    )

    logger.info(
        "cliente_nome_persistido | acao=salvar_nome evento=%s etapa_origem=%s etapa_resultante=%s id_conversa=%s cliente=%s",
        EVENTO_NOME_CLIENTE_VALIDO,
        contexto_historico.get("id_etapa_origem_transicao"),
        contexto_envio.get("id_etapa_resultante"),
        contexto_historico["id_conversa"],
        short_value(cliente_telefone),
    )

    return {
        "cliente_nome_atualizado": True,
        "primeiro_nome_cliente": primeiro_nome,
    }


def _persistir_destino_atendimento_da_etapa_2(
    contexto_historico,
    evento_transicao,
    cursor,
):
    id_conversa = contexto_historico["id_conversa"]
    status_dependente = (
        evento_transicao == EVENTO_PARA_OUTRA_PESSOA
    )

    atualizar_status_dependente_conversa(
        id_conversa,
        status_dependente,
        cursor,
    )

    contexto_persistido = {
        "status_dependente_atualizado": True,
        "status_dependente": status_dependente,
        "opcao_atendimento": evento_transicao,
        "dependente_criado": False,
    }

    if status_dependente:
        dependente = inserir_dependente_para_conversa(
            id_conversa,
            cursor,
        )
        contexto_persistido.update(
            {
                "dependente_criado": dependente["inserido"],
                "id_dependente": dependente["id_dependente"],
                "id_cliente_dependente": dependente["id_cliente"],
            }
        )

    logger.info(
        "destino_atendimento_persistido | acao=salvar_efeitos_transicao evento=%s etapa_origem=%s etapa_resultante=%s id_conversa=%s status_dependente=%s dependente_criado=%s",
        evento_transicao,
        contexto_historico.get("id_etapa_origem_transicao"),
        (
            ETAPA_NOME_DEPENDENTE
            if status_dependente
            else ETAPA_OFERTA
        ),
        id_conversa,
        status_dependente,
        contexto_persistido["dependente_criado"],
    )

    return contexto_persistido


def _resolver_primeiro_nome_cliente(
    contexto_historico,
    contexto_envio,
):
    primeiro_nome = contexto_envio.get("primeiro_nome_cliente")

    if primeiro_nome:
        return primeiro_nome

    resultado_nome = validar_nome_cliente(
        contexto_historico.get("texto_cliente_atual") or ""
    )

    if resultado_nome.valido:
        return resultado_nome.primeiro_nome

    return None
```

### Por que a função de efeitos continua necessária

A tabela resolve:

```text
para onde a conversa vai
```

`atualizar_banco_conforme_transicao_de_etapa` resolve:

```text
o que mais precisa ser persistido quando ela vai
```

Exemplos:

```text
nome_cliente_valido
-> navegação 1 -> 2 pela tabela
-> efeito: salvar cliente.nome

para_mim
-> navegação 2 -> 5 pela tabela
-> efeito: status_dependente=False

para_outra_pessoa
-> navegação 2 -> 3 pela tabela
-> efeitos: status_dependente=True e criar dependente
```

Portanto, a função fica mais semântica e deixa de tentar descobrir a transição
somente pela comparação de números.

## Passo 13 - Testar o contrato de transições

Novo arquivo completo:
`tests/unit/test_transicoes_etapa.py`

```python
import unittest

from core.repositories import transicoes_etapa
from tests.helpers import FakeCursor
from workers.worker_flow.response_flow.transicoes.eventos import (
    ETAPA_NOME_DEPENDENTE,
    ETAPA_OFERTA,
    EVENTO_PARA_MIM,
    EVENTO_PARA_OUTRA_PESSOA,
)
from workers.worker_flow.response_flow.transicoes.resolver_transicao import (
    TransicaoEtapaInvalida,
    anexar_transicao_ao_contexto_envio,
    identificar_evento_por_destino,
    resolver_destino_transicao,
)


def contexto_transicoes():
    return {
        "id_etapa_origem_transicao": 2,
        "transicoes_permitidas": {
            EVENTO_PARA_MIM: ETAPA_OFERTA,
            EVENTO_PARA_OUTRA_PESSOA: ETAPA_NOME_DEPENDENTE,
        },
    }


class TransicoesEtapaTests(unittest.TestCase):
    def test_repositorio_carrega_eventos_e_destinos(self):
        cursor = FakeCursor(
            fetchall_result=[
                (EVENTO_PARA_MIM, ETAPA_OFERTA),
                (
                    EVENTO_PARA_OUTRA_PESSOA,
                    ETAPA_NOME_DEPENDENTE,
                ),
            ]
        )

        resultado = transicoes_etapa.listar_transicoes_permitidas(
            2,
            cursor,
        )

        self.assertEqual(
            resultado,
            {
                EVENTO_PARA_MIM: ETAPA_OFERTA,
                EVENTO_PARA_OUTRA_PESSOA: ETAPA_NOME_DEPENDENTE,
            },
        )
        sql, params = cursor.calls[0]
        self.assertIn("FROM chatbot.etapa_transicao", sql)
        self.assertIn("WHERE id_etapa_origem = %s", sql)
        self.assertEqual(params, (2,))

    def test_para_mim_resolve_etapa_cinco(self):
        destino = resolver_destino_transicao(
            contexto_transicoes(),
            EVENTO_PARA_MIM,
            destinos_esperados={ETAPA_OFERTA},
        )

        self.assertEqual(destino, ETAPA_OFERTA)

    def test_para_outra_pessoa_resolve_etapa_tres(self):
        destino = resolver_destino_transicao(
            contexto_transicoes(),
            EVENTO_PARA_OUTRA_PESSOA,
            destinos_esperados={ETAPA_NOME_DEPENDENTE},
        )

        self.assertEqual(destino, ETAPA_NOME_DEPENDENTE)

    def test_evento_ausente_e_recusado_antes_do_envio(self):
        with self.assertRaises(TransicaoEtapaInvalida):
            resolver_destino_transicao(
                contexto_transicoes(),
                "evento_inventado",
            )

    def test_destino_trocado_no_seed_e_recusado(self):
        contexto = contexto_transicoes()
        contexto["transicoes_permitidas"][EVENTO_PARA_MIM] = 3

        with self.assertRaises(TransicaoEtapaInvalida):
            resolver_destino_transicao(
                contexto,
                EVENTO_PARA_MIM,
                destinos_esperados={ETAPA_OFERTA},
            )

    def test_sender_nao_pode_retornar_destino_diferente(self):
        with self.assertRaises(TransicaoEtapaInvalida):
            anexar_transicao_ao_contexto_envio(
                contexto_transicoes(),
                {
                    "id_etapa_resultante": 3,
                    "enviou": True,
                },
                EVENTO_PARA_MIM,
                ETAPA_OFERTA,
            )

    def test_tratamento_nao_pode_carregar_evento(self):
        with self.assertRaises(TransicaoEtapaInvalida):
            anexar_transicao_ao_contexto_envio(
                contexto_transicoes(),
                {
                    "id_etapa_resultante": ETAPA_OFERTA,
                    "enviou": True,
                    "tratamento": True,
                },
                EVENTO_PARA_MIM,
                ETAPA_OFERTA,
            )

    def test_retry_reconstroi_evento_pelo_destino(self):
        evento = identificar_evento_por_destino(
            contexto_transicoes(),
            ETAPA_OFERTA,
        )

        self.assertEqual(evento, EVENTO_PARA_MIM)

    def test_resposta_na_mesma_etapa_nao_inventa_transicao(self):
        evento = identificar_evento_por_destino(
            contexto_transicoes(),
            2,
        )

        self.assertIsNone(evento)


if __name__ == "__main__":
    unittest.main()
```

## Critérios de aplicação, validação e rollout

Este passo não cria nem modifica arquivo.

### 21.1 Baseline antes das alterações

```powershell
python -m unittest discover -s tests -t .
python callback/manage.py check
python -m compileall core workers callback tests
```

### 21.2 Aplicar os arquivos na ordem do plano

Primeiro infraestrutura e contratos:

```text
povoar_etapas.py
etapa_transicao_script.py
setup_database.py
transicoes_etapa.py
transicoes/
```

Depois runtime:

```text
valida_segunda_etapa.py
valida_historico.py
primeira_etapa.py
segunda_etapa.py
flow_sender.py
updates.py
persistencia_resposta.py
```

Por último, testes.

### 21.3 Verificações estáticas

```powershell
python -m compileall core workers callback tests
python callback/manage.py check
git diff --check
rg -n "id_etapa_atual\s*\+\s*1|GREATEST\(id_etapa_atual" core workers
```

O último comando não deve localizar nenhuma regra de navegação aritmética.
Usos de `+ 1` referentes a retry, versão, contador ou lock não pertencem ao
fluxo de etapas e permanecem válidos.

### 21.4 Testes automatizados

```powershell
python -m unittest tests.unit.test_transicoes_etapa -v
python -m unittest tests.unit.test_primeira_etapa -v
python -m unittest tests.unit.test_segunda_etapa -v
python -m unittest tests.unit.test_flow_sender -v
python -m unittest tests.unit.test_lastfrom_semantico -v
python -m unittest tests.unit.test_repositories -v
python -m unittest tests.unit.test_worker_support_finalizacao -v
python -m unittest tests.unit.test_fluxo_turno_abc -v
python -m unittest tests.unit.test_retry_lock_lifecycle -v
python -m unittest discover -s tests -t .
```

### 21.5 Preparar o banco de desenvolvimento

Antes do setup:

```text
parar o worker
-> confirmar que não existem mensagens pending/processing de testes antigos
-> executar setup
-> iniciar novamente webhook e worker
```

Isso é importante porque o código atual já gravou simulações antigas em que
`para_mim` também resultava na etapa 3. O novo mapa passa a considerar:

```text
para_mim -> 5
para_outra_pessoa -> 3
```

Como a V1 ainda está em desenvolvimento e as etapas 3 e 5 são simulações, os
dados de conversas de teste podem ser encerrados ou recriados antes do rollout.
Nenhuma migração automática deve tentar adivinhar o significado de um histórico
antigo.

Executar:

```powershell
python -m core.database.deploy.setup_database
```

Conferir:

```sql
SELECT id_etapa, nome_etapa
FROM chatbot.etapa
ORDER BY id_etapa;

SELECT id_etapa_origem, evento, id_etapa_destino
FROM chatbot.etapa_transicao
ORDER BY id_etapa_origem, evento;
```

Resultado esperado:

```text
1 nome_cliente_valido    2
2 para_mim               5
2 para_outra_pessoa      3
```

### 21.6 Testes manuais do fluxo

#### Tratamento na etapa 1

```text
cliente envia mídia
-> tratamento da etapa 1
-> conversa permanece na etapa 1
-> nenhuma linha de transição é usada
```

#### Nome válido

```text
cliente envia Maria
-> evento nome_cliente_valido
-> tabela autoriza 1 -> 2
-> sender da etapa 2 é chamado
-> nome e etapa 2 são persistidos no mesmo commit
```

#### Tratamentos na etapa 2

Testar mídia, financeiro e opção inválida:

```text
resposta de tratamento
-> id_etapa_atual continua 2
-> status_dependente não muda
-> dependente não é criado
```

#### Para mim

```text
evento para_mim
-> tabela autoriza 2 -> 5
-> status_dependente=False
-> nenhum dependente
-> id_etapa_atual=5
```

#### Para outra pessoa

```text
evento para_outra_pessoa
-> tabela autoriza 2 -> 3
-> status_dependente=True
-> dependente vinculado à conversa
-> id_etapa_atual=3
```

#### Tentativa de salto inventado

Alterar apenas um teste para produzir destino 7:

```text
origem 2 + para_mim + destino 7
-> recusado antes do sender
```

Também testar o repositório com `rowcount=0`:

```text
-> rollback
-> fila não vira sent
-> política normal de retry permanece responsável
```

## Matriz de impacto

| Proteção | Situação após o plano |
|---|---|
| Regra de turno do webhook | Não alterada |
| Apenas primeira mensagem válida | Não alterada |
| Advisory lock da conversa | Não alterado |
| `lock_version` | Não alterado |
| Ordem A/B/C | Não alterada |
| `if resposta_bot_atual` | Mantido antes de qualquer sender |
| Retry de falha Meta | Não alterado |
| Retry de falha banco | Não alterado |
| Histórico específico por fila/hash | Não alterado |
| Tratamentos sem avanço | Reforçados por ausência de evento |
| Salto de etapa | Permitido somente por aresta cadastrada |
| Retrocesso | Não ocorre; reaplicação aceita somente origem ou destino exato |
| Vários workers na V2 | Continuam protegidos pelo lock existente |
| `flow_worker.py` | Nenhuma nova decisão de transição |
| Webhook | Nenhuma alteração |
| Redis e caches | Nenhuma alteração |

## Falhas previstas

### Tabela ausente ou banco indisponível

```text
valida_historico não carrega transições
-> worker falha antes da Meta
-> fila não vira sent
-> retry normal
```

### Evento não cadastrado

```text
resolver_destino_transicao falha antes do sender
-> nenhuma mensagem externa enviada
-> nenhuma etapa alterada
```

### Sender retorna destino diferente

```text
anexar_transicao_ao_contexto_envio falha
-> banco não confirma etapa
```

Os resolvers também validam o destino esperado antes do sender. Portanto, um
mapa como `para_mim -> 3` é detectado antes da simulação ou futuro envio.

### Banco falha depois da Meta

O comportamento existente permanece:

```text
Meta confirmou
-> banco falhou antes do commit
-> BancoFalhouAposEnvioMeta
-> retry
```

A tabela de transições não amplia nem elimina essa janela. O tracker de status
Meta continua sendo uma evolução documentada para a V2.

### Resposta já persistida e fila ainda aberta

```text
valida_historico encontra resposta
-> flow_sender não envia
-> evento é reconstruído por origem + destino
-> SQL permite reaplicação sem retrocesso
-> efeitos idempotentes são reparados
-> fila vira sent
```

## Custo operacional

O worker executará uma consulta indexada adicional por mensagem processada:

```sql
SELECT evento, id_etapa_destino
FROM chatbot.etapa_transicao
WHERE id_etapa_origem = ?
```

A tabela terá poucas linhas e a constraint única já fornece índice pela origem.
Não é necessário criar cache Redis para esse mapa na V1. Ler do PostgreSQL
evita cache stale justamente na regra que autoriza saltos.

## Arquivos que permanecem intactos

Este plano não modifica:

```text
workers/worker_flow/response_flow/flow_worker.py
workers/worker_flow/transacoes/lock_conversa.py
workers/worker_flow/transacoes/ordem_turno.py
workers/worker_flow/transacoes/finalizacao_fila.py
callback/webhook/
core/cache/
core/database/deploy/bank_script.py
```

`flow_worker.py` continua enxuto porque recebe somente:

```text
contexto_historico com mapa e origem
-> contexto_envio com evento e destino
-> persistência final
```

Ele não conhece nenhuma aresta específica.

## Aval final

A tabela de transições é mais forte que uma exceção hardcoded para `2 -> 5`
porque:

- torna todos os caminhos permitidos auditáveis no banco;
- impede saltos não cadastrados;
- suporta caminhos de tamanhos diferentes;
- permite convergência em uma etapa comum;
- elimina a dependência semântica de `ID + 1`;
- mantém efeitos de negócio transacionais;
- preserva o modelo atual de idempotência e concorrência.

A implementação deve ocorrer agora, antes dos senders reais das etapas 3 e 5.
Neste momento o custo de migração é menor, pois somente as etapas 1 e 2 possuem
resolvers completos.

## Passo 14 - Atualizar os testes da persistência final

Arquivo completo:
`tests/unit/test_worker_support_finalizacao.py`

```python
import unittest
from unittest.mock import patch

from workers.worker_flow.response_flow.transicoes.eventos import (
    EVENTO_NOME_CLIENTE_VALIDO,
    EVENTO_PARA_MIM,
    EVENTO_PARA_OUTRA_PESSOA,
)
from workers.worker_flow.suporte import cache_repair
from workers.worker_flow.transacoes import ordem_turno
from workers.worker_flow.transacoes import (
    persistencia_resposta as persistencia,
)


DATA_BOT = "2026-01-01T00:00:00"


def contexto_historico_base(
    resposta_bot=None,
    *,
    id_etapa_atual=None,
    etapa_origem=1,
    texto_cliente="Ola",
):
    return {
        "resposta_bot_para_mensagem_atual": resposta_bot,
        "id_conversa": 10,
        "id_etapa_atual": id_etapa_atual,
        "id_etapa_cliente": etapa_origem,
        "id_etapa_origem_transicao": etapa_origem,
        "texto_cliente_atual": texto_cliente,
        "mensagem_cliente_atual": {
            "id_mensagem_fila": 20,
            "id_hash_msg": "wamid.cliente",
            "cliente_telefone": "5571999999999",
            "id_phone_unidade": "123456",
            "unidade_telefone": "5571000000000",
        },
    }


def contexto_envio_base(
    *,
    destino,
    evento=None,
    tratamento=False,
    resposta_ja_existia=False,
):
    contexto = {
        "enviou": not resposta_ja_existia,
        "resposta_ja_existia": resposta_ja_existia,
        "mensagem_bot": "Resposta",
        "id_hash_msg_bot": "wamid.bot",
        "id_etapa_resultante": destino,
        "tipo_mensagem": "text",
    }

    if evento:
        contexto["evento_transicao"] = evento

    if tratamento:
        contexto["tratamento"] = True

    return contexto


class WorkerSupportFinalizacaoTests(unittest.TestCase):
    def test_primeira_resposta_inicializa_conversa_na_etapa_um(self):
        chamadas = []

        def fake_inserir(*_args, **_kwargs):
            return 300, DATA_BOT, True

        def fake_inicializar(
            id_conversa,
            id_etapa,
            data_interacao,
            cursor,
        ):
            chamadas.append(
                (
                    "inicializar",
                    id_conversa,
                    id_etapa,
                    data_interacao,
                    cursor,
                )
            )
            return 1

        cursor = object()

        with (
            patch.object(
                persistencia,
                "inserir_historico_mensagem_bot",
                fake_inserir,
            ),
            patch.object(
                persistencia,
                "inicializar_conversa_resposta_bot",
                fake_inicializar,
            ),
        ):
            resultado = persistencia.atualizar_banco_com_contexto_final(
                contexto_historico_base(id_etapa_atual=None),
                contexto_envio_base(destino=1),
                cursor,
            )

        self.assertEqual(
            chamadas,
            [("inicializar", 10, 1, DATA_BOT, cursor)],
        )
        self.assertEqual(
            resultado["movimento_conversa"],
            persistencia.MOVIMENTO_INICIALIZACAO,
        )
        self.assertTrue(resultado["historico_bot_inserido"])

    def test_tratamento_persiste_sem_avancar(self):
        chamadas = []

        def fake_inserir(*_args, **_kwargs):
            return 301, DATA_BOT, True

        def fake_sem_avancar(
            id_conversa,
            data_interacao,
            cursor,
        ):
            chamadas.append(
                ("sem_avanco", id_conversa, data_interacao, cursor)
            )
            return 1

        cursor = object()

        with (
            patch.object(
                persistencia,
                "inserir_historico_mensagem_bot",
                fake_inserir,
            ),
            patch.object(
                persistencia,
                "atualizar_conversa_resposta_bot_sem_avancar",
                fake_sem_avancar,
            ),
        ):
            resultado = persistencia.atualizar_banco_com_contexto_final(
                contexto_historico_base(
                    id_etapa_atual=2,
                    etapa_origem=2,
                ),
                contexto_envio_base(
                    destino=2,
                    tratamento=True,
                ),
                cursor,
            )

        self.assertEqual(
            chamadas,
            [("sem_avanco", 10, DATA_BOT, cursor)],
        )
        self.assertEqual(
            resultado["movimento_conversa"],
            persistencia.MOVIMENTO_SEM_AVANCO,
        )
        self.assertFalse(resultado["atualizar_conversa"])

    def test_resposta_sem_evento_nao_pode_pular(self):
        with patch.object(
            persistencia,
            "inserir_historico_mensagem_bot",
            return_value=(302, DATA_BOT, True),
        ):
            with self.assertRaises(ValueError):
                persistencia.atualizar_banco_com_contexto_final(
                    contexto_historico_base(
                        id_etapa_atual=2,
                        etapa_origem=2,
                    ),
                    contexto_envio_base(destino=5),
                    object(),
                )

    def test_transicao_nova_revalida_banco(self):
        chamadas = []

        def fake_inserir(*_args, **_kwargs):
            return 303, DATA_BOT, True

        def fake_transicao(
            id_conversa,
            origem,
            evento,
            destino,
            data_interacao,
            cursor,
            *,
            permitir_reaplicacao=False,
        ):
            chamadas.append(
                (
                    id_conversa,
                    origem,
                    evento,
                    destino,
                    data_interacao,
                    cursor,
                    permitir_reaplicacao,
                )
            )
            return 1

        cursor = object()

        with (
            patch.object(
                persistencia,
                "inserir_historico_mensagem_bot",
                fake_inserir,
            ),
            patch.object(
                persistencia,
                "atualizar_conversa_por_transicao",
                fake_transicao,
            ),
            patch.object(
                persistencia,
                "atualizar_banco_conforme_transicao_de_etapa",
                return_value=None,
            ),
        ):
            resultado = persistencia.atualizar_banco_com_contexto_final(
                contexto_historico_base(
                    id_etapa_atual=2,
                    etapa_origem=2,
                ),
                contexto_envio_base(
                    destino=5,
                    evento=EVENTO_PARA_MIM,
                ),
                cursor,
            )

        self.assertEqual(
            chamadas,
            [
                (
                    10,
                    2,
                    EVENTO_PARA_MIM,
                    5,
                    DATA_BOT,
                    cursor,
                    False,
                )
            ],
        )
        self.assertEqual(
            resultado["movimento_conversa"],
            persistencia.MOVIMENTO_TRANSICAO,
        )

    def test_resposta_existente_nao_insere_e_reaplica_sem_regredir(self):
        chamadas = []

        def fake_transicao(
            id_conversa,
            origem,
            evento,
            destino,
            data_interacao,
            cursor,
            *,
            permitir_reaplicacao=False,
        ):
            chamadas.append(permitir_reaplicacao)
            return 1

        with (
            patch.object(
                persistencia,
                "inserir_historico_mensagem_bot",
            ) as inserir_historico,
            patch.object(
                persistencia,
                "atualizar_conversa_por_transicao",
                fake_transicao,
            ),
            patch.object(
                persistencia,
                "atualizar_banco_conforme_transicao_de_etapa",
                return_value=None,
            ),
        ):
            resultado = persistencia.atualizar_banco_com_contexto_final(
                contexto_historico_base(
                    {"received_data_hora": DATA_BOT},
                    id_etapa_atual=5,
                    etapa_origem=2,
                ),
                contexto_envio_base(
                    destino=5,
                    evento=EVENTO_PARA_MIM,
                    resposta_ja_existia=True,
                ),
                object(),
            )

        inserir_historico.assert_not_called()
        self.assertEqual(chamadas, [True])
        self.assertTrue(resultado["resposta_ja_existia"])
        self.assertFalse(resultado["historico_bot_inserido"])

    def test_nome_valido_persiste_somente_no_evento_um_para_dois(self):
        cursor = object()

        with patch.object(
            persistencia,
            "atualizar_nome_cliente_por_telefone",
            return_value=1,
        ) as atualizar_nome:
            resultado = (
                persistencia.atualizar_banco_conforme_transicao_de_etapa(
                    contexto_historico_base(
                        id_etapa_atual=1,
                        etapa_origem=1,
                        texto_cliente="Maria",
                    ),
                    {
                        "id_etapa_resultante": 2,
                        "evento_transicao": EVENTO_NOME_CLIENTE_VALIDO,
                        "primeiro_nome_cliente": "Maria",
                    },
                    cursor,
                )
            )

        atualizar_nome.assert_called_once_with(
            "5571999999999",
            "Maria",
            cursor,
        )
        self.assertEqual(resultado["primeiro_nome_cliente"], "Maria")

    def test_nome_e_reconstruido_no_retry(self):
        cursor = object()

        with patch.object(
            persistencia,
            "atualizar_nome_cliente_por_telefone",
            return_value=1,
        ) as atualizar_nome:
            resultado = (
                persistencia.atualizar_banco_conforme_transicao_de_etapa(
                    contexto_historico_base(
                        id_etapa_atual=2,
                        etapa_origem=1,
                        texto_cliente="Maria",
                    ),
                    {
                        "resposta_ja_existia": True,
                        "id_etapa_resultante": 2,
                        "evento_transicao": EVENTO_NOME_CLIENTE_VALIDO,
                    },
                    cursor,
                )
            )

        atualizar_nome.assert_called_once_with(
            "5571999999999",
            "Maria",
            cursor,
        )
        self.assertEqual(resultado["primeiro_nome_cliente"], "Maria")

    def test_nome_vazio_na_aresta_um_para_dois_falha(self):
        with patch.object(
            persistencia,
            "atualizar_nome_cliente_por_telefone",
        ) as atualizar_nome:
            with self.assertRaises(ValueError):
                persistencia.atualizar_banco_conforme_transicao_de_etapa(
                    contexto_historico_base(
                        id_etapa_atual=1,
                        etapa_origem=1,
                        texto_cliente="99",
                    ),
                    {
                        "id_etapa_resultante": 2,
                        "evento_transicao": EVENTO_NOME_CLIENTE_VALIDO,
                    },
                    object(),
                )

        atualizar_nome.assert_not_called()

    def test_para_mim_vai_para_cinco_sem_criar_dependente(self):
        cursor = object()

        with (
            patch.object(
                persistencia,
                "atualizar_status_dependente_conversa",
                return_value=1,
            ) as atualizar_status,
            patch.object(
                persistencia,
                "inserir_dependente_para_conversa",
            ) as inserir_dependente,
        ):
            resultado = (
                persistencia.atualizar_banco_conforme_transicao_de_etapa(
                    contexto_historico_base(
                        id_etapa_atual=2,
                        etapa_origem=2,
                        texto_cliente="Para mim",
                    ),
                    {
                        "id_etapa_resultante": 5,
                        "evento_transicao": EVENTO_PARA_MIM,
                    },
                    cursor,
                )
            )

        atualizar_status.assert_called_once_with(10, False, cursor)
        inserir_dependente.assert_not_called()
        self.assertFalse(resultado["status_dependente"])
        self.assertFalse(resultado["dependente_criado"])

    def test_para_outra_pessoa_vai_para_tres_e_cria_dependente(self):
        cursor = object()
        dependente = {
            "id_dependente": 30,
            "id_cliente": 5,
            "id_conversa": 10,
            "inserido": True,
        }

        with (
            patch.object(
                persistencia,
                "atualizar_status_dependente_conversa",
                return_value=1,
            ) as atualizar_status,
            patch.object(
                persistencia,
                "inserir_dependente_para_conversa",
                return_value=dependente,
            ) as inserir_dependente,
        ):
            resultado = (
                persistencia.atualizar_banco_conforme_transicao_de_etapa(
                    contexto_historico_base(
                        id_etapa_atual=2,
                        etapa_origem=2,
                        texto_cliente="Para outra pessoa",
                    ),
                    {
                        "id_etapa_resultante": 3,
                        "evento_transicao": (
                            EVENTO_PARA_OUTRA_PESSOA
                        ),
                    },
                    cursor,
                )
            )

        atualizar_status.assert_called_once_with(10, True, cursor)
        inserir_dependente.assert_called_once_with(10, cursor)
        self.assertTrue(resultado["status_dependente"])
        self.assertTrue(resultado["dependente_criado"])
        self.assertEqual(resultado["id_dependente"], 30)

    def test_tratamento_nao_executa_efeitos_de_transicao(self):
        with (
            patch.object(
                persistencia,
                "atualizar_status_dependente_conversa",
            ) as atualizar_status,
            patch.object(
                persistencia,
                "inserir_dependente_para_conversa",
            ) as inserir_dependente,
        ):
            resultado = (
                persistencia.atualizar_banco_conforme_transicao_de_etapa(
                    contexto_historico_base(
                        id_etapa_atual=2,
                        etapa_origem=2,
                    ),
                    {
                        "id_etapa_resultante": 2,
                        "tratamento": True,
                    },
                    object(),
                )
            )

        self.assertIsNone(resultado)
        atualizar_status.assert_not_called()
        inserir_dependente.assert_not_called()

    def test_aresta_semantica_incompativel_falha(self):
        with self.assertRaises(ValueError):
            persistencia.atualizar_banco_conforme_transicao_de_etapa(
                contexto_historico_base(
                    id_etapa_atual=2,
                    etapa_origem=2,
                ),
                {
                    "id_etapa_resultante": 3,
                    "evento_transicao": EVENTO_PARA_MIM,
                },
                object(),
            )

    def test_resposta_existente_sem_data_persistida_falha(self):
        with self.assertRaises(ValueError):
            persistencia.atualizar_banco_com_contexto_final(
                contexto_historico_base({}),
                contexto_envio_base(
                    destino=1,
                    resposta_ja_existia=True,
                ),
                object(),
            )

    def test_contexto_sem_envio_e_sem_resposta_existente_falha(self):
        contexto_envio = contexto_envio_base(destino=1)
        contexto_envio["enviou"] = False

        with self.assertRaises(ValueError):
            persistencia.atualizar_banco_com_contexto_final(
                contexto_historico_base(),
                contexto_envio,
                object(),
            )

    def test_reagendar_mensagem_anterior_preserva_ordem(self):
        chamadas = []

        def fake_reagendar(
            id_mensagem,
            cursor,
            delay_seconds=30,
        ):
            chamadas.append((id_mensagem, delay_seconds, cursor))
            return 1

        mensagem = {
            "id_mensagem": 44,
            "cliente_telefone": "5571999999999",
            "id_phone_unidade": "123456",
            "data_recebimento": DATA_BOT,
        }
        contexto_banco = {"conversa": {"id_conversa": 10}}
        cursor = object()

        with (
            patch.object(
                ordem_turno,
                "existe_mensagem_anterior_aberta_conversa",
                return_value=True,
            ),
            patch.object(
                ordem_turno,
                "reagendar_mensagem_sem_erro",
                fake_reagendar,
            ),
        ):
            resultado = (
                ordem_turno.reagendar_se_houver_mensagem_anterior(
                    mensagem,
                    contexto_banco,
                    lock_version=7,
                    cursor=cursor,
                )
            )

        self.assertTrue(resultado)
        self.assertEqual(chamadas, [(44, 30, cursor)])

    def test_reparo_cache_cliente_stale_permanece_inalterado(self):
        estado = {
            "cliente_telefone": "5571999999999",
            "id_mensagem": 1,
        }

        with patch.object(
            cache_repair,
            "remover_cliente_cache",
            return_value=True,
        ) as remover:
            resultado = (
                cache_repair.reparar_cache_cliente_stale_se_fk_invalida(
                    RuntimeError(
                        "violates foreign key constraint "
                        "conversa_id_cliente_fkey"
                    ),
                    estado,
                )
            )

        self.assertTrue(resultado)
        remover.assert_called_once_with("5571999999999")


if __name__ == "__main__":
    unittest.main()
```

## Critério de conclusão após a aplicação

Depois de aplicar integralmente os passos 1 a 20, executar os comandos, consultas
e cenários descritos em **Critérios de aplicação, validação e rollout**.

O plano só será considerado concluído quando:

```text
suíte completa passar
-> Django check passar
-> compileall passar
-> diff check passar
-> tabela etapa_transicao possuir somente a whitelist prevista
-> tratamentos permanecerem na etapa atual
-> para_mim produzir 2 -> 5
-> para_outra_pessoa produzir 2 -> 3
-> retry com resposta existente não reenviar
-> testes A/B/C e lock continuarem verdes
```

## Passo 15 - Atualizar os testes de histórico semântico

Arquivo completo:
`tests/unit/test_lastfrom_semantico.py`

```python
import unittest
from unittest.mock import patch

from workers.worker_flow import valida_historico
from workers.worker_flow.response_flow.transicoes.eventos import (
    EVENTO_NOME_CLIENTE_VALIDO,
)


DATA_CLIENTE = "2026-01-01T00:00:00"
DATA_BOT = "2026-01-01T00:01:00"


def mensagem_base(retry=1):
    return {
        "id_mensagem": 20,
        "cliente_telefone": "5571999999999",
        "conteudo_texto": "ola",
        "tipo_mensagem": "text",
        "id_phone_unidade": "123456",
        "unidade_telefone": "5571000000000",
        "data_recebimento": DATA_CLIENTE,
        "id_hash": "wamid.cliente",
        "retry_count": retry,
    }


def contexto_banco_base(last_from="bot", etapa=1):
    return {
        "conversa": {
            "id_conversa": 10,
            "id_etapa_atual": etapa,
            "status_dependente": False,
            "last_message_from": last_from,
        }
    }


def transicoes_etapa_um(_id_etapa, _cursor):
    return {EVENTO_NOME_CLIENTE_VALIDO: 2}


class LastFromSemanticoTests(unittest.TestCase):
    def test_conversa_nova_carrega_origem_sem_inventar_salto(self):
        chamadas = []

        def fake_inserir(mensagem, id_conversa, id_etapa, cursor):
            chamadas.append(("insert_cliente", id_conversa, id_etapa))
            return 100, DATA_CLIENTE, 1, True

        def fake_update_cliente(id_conversa, data_interacao, cursor):
            chamadas.append(
                ("update_cliente", id_conversa, data_interacao)
            )
            return 1

        with (
            patch.object(
                valida_historico,
                "inserir_historico_mensagem_cliente",
                fake_inserir,
            ),
            patch.object(
                valida_historico,
                "buscar_resposta_bot_por_mensagem_cliente",
                return_value=None,
            ),
            patch.object(
                valida_historico,
                "listar_transicoes_permitidas",
                transicoes_etapa_um,
            ),
            patch.object(
                valida_historico,
                "atualizar_conversa_mensagem_cliente",
                fake_update_cliente,
            ),
        ):
            contexto = valida_historico.valida_historico(
                mensagem_base(),
                contexto_banco_base(
                    last_from="cliente",
                    etapa=None,
                ),
                object(),
            )

        self.assertEqual(contexto["id_etapa_cliente"], 1)
        self.assertEqual(contexto["id_etapa_origem_transicao"], 1)
        self.assertEqual(contexto["id_etapa_resposta"], 1)
        self.assertEqual(
            contexto["transicoes_permitidas"],
            {EVENTO_NOME_CLIENTE_VALIDO: 2},
        )
        self.assertEqual(contexto["last_message_from"], "cliente")

    def test_retry_antes_da_resposta_mantem_origem_do_historico(self):
        def fake_inserir(mensagem, id_conversa, id_etapa, cursor):
            return 100, DATA_CLIENTE, 1, False

        with (
            patch.object(
                valida_historico,
                "inserir_historico_mensagem_cliente",
                fake_inserir,
            ),
            patch.object(
                valida_historico,
                "buscar_resposta_bot_por_mensagem_cliente",
                return_value=None,
            ),
            patch.object(
                valida_historico,
                "listar_transicoes_permitidas",
                transicoes_etapa_um,
            ),
            patch.object(
                valida_historico,
                "atualizar_conversa_mensagem_cliente",
                return_value=1,
            ),
        ):
            contexto = valida_historico.valida_historico(
                mensagem_base(retry=2),
                contexto_banco_base(
                    last_from="cliente",
                    etapa=1,
                ),
                object(),
            )

        self.assertEqual(contexto["id_etapa_origem_transicao"], 1)
        self.assertEqual(contexto["id_etapa_resposta"], 2)
        self.assertEqual(contexto["last_message_from"], "cliente")
        self.assertFalse(contexto["mensagem_cliente_inserida"])

    def test_retry_apos_resposta_preserva_origem_e_destino(self):
        resposta_bot = (
            200,
            10,
            2,
            DATA_BOT,
            "5571999999999",
            "Ola",
            "text",
            "wamid.bot",
            20,
            "wamid.cliente",
            "123456",
            "5571000000000",
            "bot",
            "sent",
        )

        def fake_inserir(mensagem, id_conversa, id_etapa, cursor):
            # O histórico da mensagem é a origem estável, embora a conversa
            # já esteja na etapa 2.
            return 100, DATA_CLIENTE, 1, False

        with (
            patch.object(
                valida_historico,
                "inserir_historico_mensagem_cliente",
                fake_inserir,
            ),
            patch.object(
                valida_historico,
                "buscar_resposta_bot_por_mensagem_cliente",
                return_value=resposta_bot,
            ),
            patch.object(
                valida_historico,
                "listar_transicoes_permitidas",
                transicoes_etapa_um,
            ),
        ):
            contexto = valida_historico.valida_historico(
                mensagem_base(retry=2),
                contexto_banco_base(last_from="bot", etapa=2),
                object(),
            )

        self.assertEqual(contexto["id_etapa_atual"], 2)
        self.assertEqual(contexto["id_etapa_origem_transicao"], 1)
        self.assertEqual(contexto["id_etapa_resposta"], 2)
        self.assertEqual(contexto["last_message_from"], "bot")
        self.assertTrue(
            contexto["resposta_bot_para_mensagem_atual"]
        )

    def test_retry_repara_last_from_sem_alterar_etapa(self):
        chamadas = []
        resposta_bot = (
            200,
            10,
            2,
            DATA_BOT,
            "5571999999999",
            "Ola",
            "text",
            "wamid.bot",
            20,
            "wamid.cliente",
            "123456",
            "5571000000000",
            "bot",
            "sent",
        )

        def fake_inserir(mensagem, id_conversa, id_etapa, cursor):
            return 100, DATA_CLIENTE, 1, False

        def fake_update_bot(id_conversa, data_interacao, cursor):
            chamadas.append((id_conversa, data_interacao))
            return 1

        with (
            patch.object(
                valida_historico,
                "inserir_historico_mensagem_cliente",
                fake_inserir,
            ),
            patch.object(
                valida_historico,
                "buscar_resposta_bot_por_mensagem_cliente",
                return_value=resposta_bot,
            ),
            patch.object(
                valida_historico,
                "listar_transicoes_permitidas",
                transicoes_etapa_um,
            ),
            patch.object(
                valida_historico,
                "atualizar_conversa_resposta_bot_sem_avancar",
                fake_update_bot,
            ),
        ):
            contexto = valida_historico.valida_historico(
                mensagem_base(retry=2),
                contexto_banco_base(
                    last_from="cliente",
                    etapa=2,
                ),
                object(),
            )

        self.assertEqual(contexto["id_etapa_origem_transicao"], 1)
        self.assertEqual(contexto["last_message_from"], "bot")
        self.assertEqual(chamadas, [(10, DATA_BOT)])


if __name__ == "__main__":
    unittest.main()
```

## Passo 16 - Atualizar os testes da primeira etapa

Arquivo completo:
`tests/unit/test_primeira_etapa.py`

```python
import unittest
from unittest.mock import patch

from workers.worker_flow.response_flow.etapas import (
    primeira_etapa as etapa_module,
)
from workers.worker_flow.response_flow.transicoes.eventos import (
    EVENTO_NOME_CLIENTE_VALIDO,
)


def contexto_historico(
    *,
    etapa_atual=None,
    tipo_mensagem="text",
    texto="Ola",
):
    return {
        "id_conversa": 10,
        "id_etapa_atual": etapa_atual,
        "id_etapa_cliente": 1,
        "id_etapa_origem_transicao": 1,
        "transicoes_permitidas": {
            EVENTO_NOME_CLIENTE_VALIDO: 2,
        },
        "tipo_mensagem_atual": tipo_mensagem,
        "texto_cliente_atual": texto,
        "mensagem_cliente_atual": {
            "id_mensagem_fila": 20,
            "id_hash_msg": "wamid.cliente",
            "cliente_telefone": "5571999999999",
            "id_phone_unidade": "123456",
        },
    }


def retorno(nome, *, id_etapa_resultante=1, tratamento=False):
    resultado = {
        "nome": nome,
        "enviou": True,
        "resposta_ja_existia": False,
        "id_hash_msg_bot": f"wamid.{nome}",
        "id_etapa_resultante": id_etapa_resultante,
    }

    if tratamento:
        resultado["tratamento"] = True

    return resultado


class PrimeiraEtapaTests(unittest.TestCase):
    def test_conversa_nova_com_midia_usa_tratamento_de_inicio(self):
        with patch.object(
            etapa_module,
            "enviar_primeira_etapa_midia_inicio",
            return_value=retorno("midia_inicio", tratamento=True),
        ) as sender:
            resultado = etapa_module.resolve_primeira_etapa(
                contexto_historico(tipo_mensagem="image")
            )

        sender.assert_called_once_with("5571999999999", "123456")
        self.assertEqual(resultado["nome"], "midia_inicio")
        self.assertNotIn("evento_transicao", resultado)

    def test_conversa_nova_com_financeiro_usa_tratamento_de_inicio(self):
        with patch.object(
            etapa_module,
            "enviar_primeira_etapa_financeiro_inicio",
            return_value=retorno("financeiro_inicio", tratamento=True),
        ) as sender:
            resultado = etapa_module.resolve_primeira_etapa(
                contexto_historico(texto="qual o valor?")
            )

        sender.assert_called_once_with("5571999999999", "123456")
        self.assertEqual(resultado["nome"], "financeiro_inicio")
        self.assertNotIn("evento_transicao", resultado)

    def test_conversa_nova_normal_envia_primeira_etapa(self):
        with patch.object(
            etapa_module,
            "enviar_primeira_etapa",
            return_value=retorno("etapa_1"),
        ) as sender:
            resultado = etapa_module.resolve_primeira_etapa(
                contexto_historico(texto="ola")
            )

        sender.assert_called_once_with("5571999999999", "123456")
        self.assertEqual(resultado["nome"], "etapa_1")
        self.assertNotIn("evento_transicao", resultado)

    def test_etapa_um_com_midia_trata_sem_transicao(self):
        with patch.object(
            etapa_module,
            "enviar_primeira_etapa_midia",
            return_value=retorno("midia_etapa_1", tratamento=True),
        ) as sender:
            resultado = etapa_module.resolve_primeira_etapa(
                contexto_historico(
                    etapa_atual=1,
                    tipo_mensagem="video",
                )
            )

        sender.assert_called_once_with("5571999999999", "123456")
        self.assertEqual(resultado["id_etapa_resultante"], 1)
        self.assertNotIn("evento_transicao", resultado)

    def test_etapa_um_com_financeiro_trata_sem_transicao(self):
        with patch.object(
            etapa_module,
            "enviar_primeira_etapa_financeiro",
            return_value=retorno(
                "financeiro_etapa_1",
                tratamento=True,
            ),
        ) as sender:
            resultado = etapa_module.resolve_primeira_etapa(
                contexto_historico(
                    etapa_atual=1,
                    texto="quanto custa?",
                )
            )

        sender.assert_called_once_with("5571999999999", "123456")
        self.assertNotIn("evento_transicao", resultado)

    def test_nome_invalido_trata_sem_transicao(self):
        with patch.object(
            etapa_module,
            "enviar_primeira_etapa_contexto_nome_invalido",
            return_value=retorno("nome_invalido", tratamento=True),
        ) as sender:
            resultado = etapa_module.resolve_primeira_etapa(
                contexto_historico(
                    etapa_atual=1,
                    texto="pppppp",
                )
            )

        sender.assert_called_once_with("5571999999999", "123456")
        self.assertNotIn("evento_transicao", resultado)

    def test_nome_valido_envia_etapa_dois_com_evento(self):
        with patch.object(
            etapa_module,
            "enviar_segunda_etapa",
            return_value=retorno(
                "etapa_2",
                id_etapa_resultante=2,
            ),
        ) as sender:
            resultado = etapa_module.resolve_primeira_etapa(
                contexto_historico(
                    etapa_atual=1,
                    texto="Maria",
                )
            )

        sender.assert_called_once_with(
            "5571999999999",
            "123456",
            nome="Maria",
        )
        self.assertEqual(resultado["id_etapa_resultante"], 2)
        self.assertEqual(
            resultado["evento_transicao"],
            EVENTO_NOME_CLIENTE_VALIDO,
        )
        self.assertEqual(resultado["id_etapa_origem_transicao"], 1)
        self.assertEqual(resultado["primeiro_nome_cliente"], "Maria")

    def test_nome_composto_e_normalizado_antes_do_sender(self):
        with patch.object(
            etapa_module,
            "enviar_segunda_etapa",
            return_value=retorno(
                "etapa_2",
                id_etapa_resultante=2,
            ),
        ) as sender:
            resultado = etapa_module.resolve_primeira_etapa(
                contexto_historico(
                    etapa_atual=1,
                    texto="Maria Julia.",
                )
            )

        sender.assert_called_once_with(
            "5571999999999",
            "123456",
            nome="Maria Julia",
        )
        self.assertEqual(
            resultado["primeiro_nome_cliente"],
            "Maria Julia",
        )

    def test_mapa_ausente_impede_sender(self):
        contexto = contexto_historico(
            etapa_atual=1,
            texto="Maria",
        )
        contexto["transicoes_permitidas"] = {}

        with patch.object(
            etapa_module,
            "enviar_segunda_etapa",
        ) as sender:
            with self.assertRaises(ValueError):
                etapa_module.resolve_primeira_etapa(contexto)

        sender.assert_not_called()


if __name__ == "__main__":
    unittest.main()
```

## Passo 17 - Atualizar os testes da segunda etapa

Arquivo completo:
`tests/unit/test_segunda_etapa.py`

```python
import unittest
from unittest.mock import patch

from workers.worker_flow.response_flow.etapas import (
    segunda_etapa as etapa_module,
)
from workers.worker_flow.response_flow.transicoes.eventos import (
    EVENTO_PARA_MIM,
    EVENTO_PARA_OUTRA_PESSOA,
)


def contexto_historico(
    *,
    tipo_mensagem="text",
    texto="Para mim",
):
    return {
        "id_conversa": 10,
        "id_etapa_atual": 2,
        "id_etapa_cliente": 2,
        "id_etapa_origem_transicao": 2,
        "transicoes_permitidas": {
            EVENTO_PARA_MIM: 5,
            EVENTO_PARA_OUTRA_PESSOA: 3,
        },
        "tipo_mensagem_atual": tipo_mensagem,
        "texto_cliente_atual": texto,
        "mensagem_cliente_atual": {
            "id_mensagem_fila": 20,
            "id_hash_msg": "wamid.cliente",
            "cliente_telefone": "5571999999999",
            "id_phone_unidade": "123456",
        },
    }


def retorno_tratamento(nome):
    return {
        "nome": nome,
        "enviou": True,
        "resposta_ja_existia": False,
        "id_hash_msg_bot": f"wamid.{nome}",
        "id_etapa_resultante": 2,
        "tratamento": True,
    }


class SegundaEtapaTests(unittest.TestCase):
    def test_midia_reenvia_etapa_sem_transicao(self):
        with patch.object(
            etapa_module,
            "enviar_segunda_etapa_midia",
            return_value=retorno_tratamento("midia_etapa_2"),
        ) as sender:
            resultado = etapa_module.resolve_segunda_etapa(
                contexto_historico(tipo_mensagem="image", texto="")
            )

        sender.assert_called_once_with("5571999999999", "123456")
        self.assertEqual(resultado["id_etapa_resultante"], 2)
        self.assertNotIn("evento_transicao", resultado)

    def test_financeiro_reenvia_etapa_sem_transicao(self):
        with patch.object(
            etapa_module,
            "enviar_segunda_etapa_financeiro",
            return_value=retorno_tratamento("financeiro_etapa_2"),
        ) as sender:
            resultado = etapa_module.resolve_segunda_etapa(
                contexto_historico(texto="quanto custa?")
            )

        sender.assert_called_once_with("5571999999999", "123456")
        self.assertNotIn("evento_transicao", resultado)

    def test_midia_tem_prioridade_sobre_financeiro(self):
        with (
            patch.object(
                etapa_module,
                "enviar_segunda_etapa_midia",
                return_value=retorno_tratamento("midia_etapa_2"),
            ) as sender_midia,
            patch.object(
                etapa_module,
                "enviar_segunda_etapa_financeiro",
            ) as sender_financeiro,
        ):
            etapa_module.resolve_segunda_etapa(
                contexto_historico(
                    tipo_mensagem="image",
                    texto="quanto custa?",
                )
            )

        sender_midia.assert_called_once_with(
            "5571999999999",
            "123456",
        )
        sender_financeiro.assert_not_called()

    def test_para_mim_pula_da_etapa_dois_para_cinco(self):
        resultado = etapa_module.resolve_segunda_etapa(
            contexto_historico(texto="Para mim")
        )

        self.assertTrue(resultado["enviou"])
        self.assertTrue(resultado["envio_simulado"])
        self.assertEqual(resultado["id_etapa_resultante"], 5)
        self.assertEqual(
            resultado["evento_transicao"],
            EVENTO_PARA_MIM,
        )
        self.assertFalse(resultado["status_dependente"])

    def test_para_outra_pessoa_vai_da_etapa_dois_para_tres(self):
        resultado = etapa_module.resolve_segunda_etapa(
            contexto_historico(
                tipo_mensagem="interactive",
                texto="Para outra pessoa",
            )
        )

        self.assertTrue(resultado["envio_simulado"])
        self.assertEqual(resultado["id_etapa_resultante"], 3)
        self.assertEqual(
            resultado["evento_transicao"],
            EVENTO_PARA_OUTRA_PESSOA,
        )
        self.assertTrue(resultado["status_dependente"])

    def test_opcao_invalida_reenvia_etapa_sem_transicao(self):
        with patch.object(
            etapa_module,
            "enviar_segunda_etapa_contexto_opcao_invalida",
            return_value=retorno_tratamento("contexto_etapa_2"),
        ) as sender:
            resultado = etapa_module.resolve_segunda_etapa(
                contexto_historico(
                    texto="eu quero para meu primo"
                )
            )

        sender.assert_called_once_with("5571999999999", "123456")
        self.assertEqual(resultado["id_etapa_resultante"], 2)
        self.assertNotIn("evento_transicao", resultado)

    def test_mapa_trocado_recusa_para_mim(self):
        contexto = contexto_historico(texto="Para mim")
        contexto["transicoes_permitidas"][EVENTO_PARA_MIM] = 3

        with self.assertRaises(ValueError):
            etapa_module.resolve_segunda_etapa(contexto)


if __name__ == "__main__":
    unittest.main()
```

## Passo 18 - Atualizar os testes do flow_sender

Arquivo completo:
`tests/unit/test_flow_sender.py`

```python
import unittest
from unittest.mock import patch

import workers.worker_flow.response_flow.flow_sender as flow_sender_module
from workers.worker_flow.response_flow.transicoes.eventos import (
    EVENTO_NOME_CLIENTE_VALIDO,
    EVENTO_PARA_MIM,
    EVENTO_PARA_OUTRA_PESSOA,
)


def contexto_historico_base(
    resposta_bot=None,
    *,
    etapa_atual=None,
    etapa_cliente=1,
    retry=1,
    transicoes=None,
):
    if transicoes is None:
        transicoes = {
            EVENTO_NOME_CLIENTE_VALIDO: 2,
        }

    return {
        "id_conversa": 10,
        "id_etapa_atual": etapa_atual,
        "id_etapa_cliente": etapa_cliente,
        "id_etapa_origem_transicao": etapa_cliente,
        "transicoes_permitidas": transicoes,
        "retry_count": retry,
        "texto_cliente_atual": "Ola",
        "tipo_mensagem_atual": "text",
        "mensagem_cliente_atual": {
            "id_mensagem_fila": 20,
            "id_hash_msg": "wamid.cliente",
            "cliente_telefone": "5571999999999",
            "id_phone_unidade": "123456",
        },
        "resposta_bot_para_mensagem_atual": resposta_bot,
    }


class FlowSenderTests(unittest.TestCase):
    def test_idempotencia_continua_antes_do_resolver(self):
        def falhar_se_chamar(*_args, **_kwargs):
            raise AssertionError("resolver nao deveria ser chamado")

        with patch.object(
            flow_sender_module,
            "resolve_primeira_etapa",
            falhar_se_chamar,
        ):
            resultado = flow_sender_module.flow_sender(
                contexto_historico_base(
                    resposta_bot={
                        "id_mensagem": 99,
                        "id_hash_msg": "wamid.bot.existente",
                        "id_etapa": 2,
                    },
                    etapa_atual=2,
                )
            )

        self.assertFalse(resultado["enviou"])
        self.assertTrue(resultado["resposta_ja_existia"])
        self.assertEqual(resultado["id_etapa_resultante"], 2)
        self.assertEqual(
            resultado["evento_transicao"],
            EVENTO_NOME_CLIENTE_VALIDO,
        )

    def test_retry_de_para_mim_reconstroi_evento_dois_para_cinco(self):
        resultado = flow_sender_module.flow_sender(
            contexto_historico_base(
                resposta_bot={
                    "id_mensagem": 100,
                    "id_hash_msg": "wamid.bot.oferta",
                    "id_etapa": 5,
                },
                etapa_atual=5,
                etapa_cliente=2,
                retry=2,
                transicoes={
                    EVENTO_PARA_MIM: 5,
                    EVENTO_PARA_OUTRA_PESSOA: 3,
                },
            )
        )

        self.assertFalse(resultado["enviou"])
        self.assertEqual(
            resultado["evento_transicao"],
            EVENTO_PARA_MIM,
        )
        self.assertEqual(resultado["id_etapa_resultante"], 5)

    def test_conversa_sem_etapa_vai_para_primeira_etapa(self):
        esperado = {
            "enviou": True,
            "resposta_ja_existia": False,
            "id_hash_msg_bot": "wamid.bot",
            "id_etapa_resultante": 1,
        }

        with patch.object(
            flow_sender_module,
            "resolve_primeira_etapa",
            return_value=esperado,
        ) as resolver:
            resultado = flow_sender_module.flow_sender(
                contexto_historico_base(etapa_atual=None)
            )

        resolver.assert_called_once()
        self.assertEqual(resultado, esperado)

    def test_etapa_um_vai_para_resolver_da_primeira_etapa(self):
        esperado = {
            "enviou": True,
            "resposta_ja_existia": False,
            "id_hash_msg_bot": "wamid.bot",
            "id_etapa_resultante": 2,
        }

        with patch.object(
            flow_sender_module,
            "resolve_primeira_etapa",
            return_value=esperado,
        ) as resolver:
            resultado = flow_sender_module.flow_sender(
                contexto_historico_base(etapa_atual=1)
            )

        resolver.assert_called_once()
        self.assertEqual(resultado, esperado)

    def test_etapa_dois_vai_para_resolver_da_segunda_etapa(self):
        esperado = {
            "enviou": True,
            "resposta_ja_existia": False,
            "id_hash_msg_bot": "simulacao",
            "id_etapa_resultante": 5,
        }

        with patch.object(
            flow_sender_module,
            "resolve_segunda_etapa",
            return_value=esperado,
        ) as resolver:
            resultado = flow_sender_module.flow_sender(
                contexto_historico_base(
                    etapa_atual=2,
                    etapa_cliente=2,
                    transicoes={
                        EVENTO_PARA_MIM: 5,
                        EVENTO_PARA_OUTRA_PESSOA: 3,
                    },
                )
            )

        resolver.assert_called_once()
        self.assertEqual(resultado, esperado)

    def test_etapa_nao_implementada_nao_finge_sucesso(self):
        with self.assertRaises(NotImplementedError):
            flow_sender_module.flow_sender(
                contexto_historico_base(
                    etapa_atual=3,
                    etapa_cliente=3,
                    transicoes={},
                )
            )


if __name__ == "__main__":
    unittest.main()
```

## Passo 19 - Atualizar os testes de deploy

Arquivo completo:
`tests/unit/test_deploy_contract.py`

```python
import inspect
import unittest

from core.database.deploy import (
    bank_script,
    etapa_transicao_script,
    setup_database,
)
from workers.worker_flow.response_flow.transicoes.eventos import (
    EVENTO_NOME_CLIENTE_VALIDO,
    EVENTO_PARA_MIM,
    EVENTO_PARA_OUTRA_PESSOA,
)


class DeployContractTests(unittest.TestCase):
    def test_banco_novo_nasce_com_last_error_sem_alterar_banco(self):
        source = inspect.getsource(bank_script.criar_tabelas)

        self.assertIn("last_error TEXT", source)
        self.assertFalse(hasattr(bank_script, "alterar_banco"))

    def test_setup_nao_chama_migracao_historica_alterar_banco(self):
        source = inspect.getsource(setup_database.setup_database_aws)

        self.assertNotIn("alterar_banco", source)
        self.assertIn("criar_tabelas()", source)
        self.assertIn("insere_etapa_once()", source)
        self.assertIn("criar_e_povoar_transicoes_etapa()", source)
        self.assertLess(
            source.index("insere_etapa_once()"),
            source.index("criar_e_povoar_transicoes_etapa()"),
        )

    def test_respostas_desafios_existe_no_ddl_com_unique_turno(self):
        source = inspect.getsource(bank_script.criar_tabelas)

        self.assertIn(
            "CREATE TABLE IF NOT EXISTS chatbot.respostas_desafios",
            source,
        )
        self.assertIn("UNIQUE (id_conversa, id_etapa)", source)
        self.assertIn("id_historico_mensagem_cliente INT NULL", source)

    def test_cliente_e_dependente_possuem_idade_e_conversa_vinculada(self):
        source = inspect.getsource(bank_script.criar_tabelas)

        self.assertIn("ADD COLUMN IF NOT EXISTS idade INTEGER", source)
        self.assertIn("ADD COLUMN IF NOT EXISTS id_conversa INT", source)
        self.assertIn("dependente_id_conversa_fkey", source)
        self.assertIn("uq_dependente_conversa", source)

    def test_tabela_transicao_possui_restricoes_de_seguranca(self):
        source = inspect.getsource(
            etapa_transicao_script.criar_e_povoar_transicoes_etapa
        )

        self.assertIn("CHECK (id_etapa_origem <> id_etapa_destino)", source)
        self.assertIn("UNIQUE (id_etapa_origem, evento)", source)
        self.assertIn(
            "UNIQUE (id_etapa_origem, id_etapa_destino)",
            source,
        )
        self.assertIn("DELETE FROM chatbot.etapa_transicao", source)

    def test_seed_de_transicoes_reflete_o_mapa_da_v1(self):
        self.assertEqual(
            etapa_transicao_script.TRANSICOES_INICIAIS,
            (
                (1, EVENTO_NOME_CLIENTE_VALIDO, 2),
                (2, EVENTO_PARA_MIM, 5),
                (2, EVENTO_PARA_OUTRA_PESSOA, 3),
            ),
        )


if __name__ == "__main__":
    unittest.main()
```

## Passo 20 - Atualizar os testes dos repositórios

Arquivo completo:
`tests/unit/test_repositories.py`

```python
import unittest

from core.repositories import inserts, updates
from tests.helpers import FakeCursor


DATA_CLIENTE = "2026-01-01T00:00:00"
DATA_BOT = "2026-01-01T00:01:00"


class RepositoryTests(unittest.TestCase):
    def test_inicializar_conversa_exige_etapa_um(self):
        with self.assertRaises(ValueError):
            updates.inicializar_conversa_resposta_bot(
                10,
                2,
                DATA_BOT,
                FakeCursor(),
            )

    def test_inicializar_conversa_falha_se_nenhuma_linha(self):
        with self.assertRaises(ValueError):
            updates.inicializar_conversa_resposta_bot(
                10,
                1,
                DATA_BOT,
                FakeCursor(rowcount=0),
            )

    def test_transicao_exige_origem_evento_e_destino(self):
        casos = (
            (None, "evento", 2),
            (1, None, 2),
            (1, "evento", None),
        )

        for origem, evento, destino in casos:
            with self.subTest(
                origem=origem,
                evento=evento,
                destino=destino,
            ):
                with self.assertRaises(ValueError):
                    updates.atualizar_conversa_por_transicao(
                        10,
                        origem,
                        evento,
                        destino,
                        DATA_BOT,
                        FakeCursor(),
                    )

    def test_transicao_revalida_aresta_no_postgresql(self):
        cursor = FakeCursor(rowcount=1)

        resultado = updates.atualizar_conversa_por_transicao(
            10,
            2,
            "para_mim",
            5,
            DATA_BOT,
            cursor,
        )

        self.assertEqual(resultado, 1)
        sql, params = cursor.calls[0]
        self.assertIn("FROM chatbot.etapa_transicao", sql)
        self.assertIn("transicao.id_etapa_origem = %s", sql)
        self.assertIn("transicao.evento = %s", sql)
        self.assertIn("transicao.id_etapa_destino = %s", sql)
        self.assertNotIn("id_etapa_atual + 1", sql)
        self.assertNotIn("GREATEST(id_etapa_atual", sql)
        self.assertEqual(
            params,
            (2, 5, DATA_BOT, 10, 2, "para_mim", 5, 2, False, 5),
        )

    def test_transicao_idempotente_nao_regride_etapa(self):
        cursor = FakeCursor(rowcount=1)

        updates.atualizar_conversa_por_transicao(
            10,
            2,
            "para_mim",
            5,
            DATA_BOT,
            cursor,
            permitir_reaplicacao=True,
        )

        sql, params = cursor.calls[0]
        self.assertIn(
            "ELSE conversa.id_etapa_atual",
            sql,
        )
        self.assertIn(
            "AND conversa.id_etapa_atual = %s",
            sql,
        )
        self.assertTrue(params[-2])
        self.assertEqual(params[-1], 5)

    def test_transicao_invalida_falha_se_banco_nao_atualiza(self):
        with self.assertRaises(ValueError):
            updates.atualizar_conversa_por_transicao(
                10,
                2,
                "evento_inventado",
                7,
                DATA_BOT,
                FakeCursor(rowcount=0),
            )

    def test_atualizar_conversa_mensagem_cliente_usa_data_persistida(self):
        cursor = FakeCursor(rowcount=1)

        resultado = updates.atualizar_conversa_mensagem_cliente(
            10,
            DATA_CLIENTE,
            cursor,
        )

        self.assertEqual(resultado, 1)
        sql, params = cursor.calls[0]
        self.assertIn("last_message_from = 'cliente'", sql)
        self.assertNotIn("NOW()", sql)
        self.assertEqual(params, (DATA_CLIENTE, 10))

    def test_resposta_sem_avanco_usa_data_persistida(self):
        cursor = FakeCursor(rowcount=1)

        resultado = updates.atualizar_conversa_resposta_bot_sem_avancar(
            10,
            DATA_BOT,
            cursor,
        )

        self.assertEqual(resultado, 1)
        sql, params = cursor.calls[0]
        self.assertIn("last_message_from = 'bot'", sql)
        self.assertNotIn("id_etapa_atual", sql)
        self.assertNotIn("NOW()", sql)
        self.assertEqual(params, (DATA_BOT, 10))

    def test_atualizar_status_dependente_conversa(self):
        cursor = FakeCursor(rowcount=1)

        resultado = updates.atualizar_status_dependente_conversa(
            10,
            True,
            cursor,
        )

        self.assertEqual(resultado, 1)
        sql, params = cursor.calls[0]
        self.assertIn("SET status_dependente = %s", sql)
        self.assertEqual(params, (True, 10))

    def test_atualizar_status_dependente_exige_conversa_existente(self):
        with self.assertRaises(ValueError):
            updates.atualizar_status_dependente_conversa(
                10,
                False,
                FakeCursor(rowcount=0),
            )

    def test_inserir_dependente_para_conversa_e_idempotente(self):
        cursor = FakeCursor(
            fetchone_result=(30, 5, 10, False),
        )

        resultado = inserts.inserir_dependente_para_conversa(
            10,
            cursor,
        )

        self.assertEqual(
            resultado,
            {
                "id_dependente": 30,
                "id_cliente": 5,
                "id_conversa": 10,
                "inserido": False,
            },
        )
        sql, params = cursor.calls[0]
        self.assertIn("INSERT INTO chatbot.dependente", sql)
        self.assertIn("WHERE NOT EXISTS", sql)
        self.assertEqual(params, (10, 10, 10))

    def test_inserir_historico_cliente_retorna_etapa_persistida(self):
        cursor = FakeCursor(
            fetchone_result=(100, "2026-01-01T00:00:00", 1, False)
        )
        mensagem = {
            "id_mensagem": 20,
            "cliente_telefone": "5571999999999",
            "conteudo_texto": "ola",
            "tipo_mensagem": "text",
            "id_phone_unidade": "123456",
            "unidade_telefone": "5571000000000",
            "data_recebimento": "2026-01-01T00:00:00",
            "id_hash": "wamid.cliente",
        }

        resultado = inserts.inserir_historico_mensagem_cliente(
            mensagem,
            id_conversa=10,
            id_etapa=2,
            cursor=cursor,
        )

        self.assertEqual(
            resultado,
            (100, "2026-01-01T00:00:00", 1, False),
        )
        sql, _params = cursor.calls[0]
        self.assertIn(
            "SELECT id_mensagem, received_data_hora, id_etapa",
            sql,
        )

    def test_inserir_historico_bot_exige_hash(self):
        with self.assertRaises(ValueError):
            inserts.inserir_historico_mensagem_bot(
                {
                    "id_conversa": 10,
                    "mensagem_cliente_atual": {
                        "id_mensagem_fila": 20,
                        "id_hash_msg": "wamid.cliente",
                    },
                },
                {
                    "id_etapa_resultante": 1,
                    "mensagem_bot": "Ola!",
                },
                FakeCursor(),
            )

    def test_inserir_historico_bot_sucesso(self):
        cursor = FakeCursor(
            fetchone_result=(300, DATA_CLIENTE, True)
        )

        resultado = inserts.inserir_historico_mensagem_bot(
            {
                "id_conversa": 10,
                "mensagem_cliente_atual": {
                    "id_mensagem_fila": 20,
                    "id_hash_msg": "wamid.cliente",
                    "cliente_telefone": "5571999999999",
                    "id_phone_unidade": "123456",
                    "unidade_telefone": "5571000000000",
                },
            },
            {
                "id_etapa_resultante": 1,
                "mensagem_bot": "Ola!",
                "id_hash_msg_bot": "wamid.bot",
                "tipo_mensagem": "interactive_button",
            },
            cursor,
        )

        self.assertEqual(resultado, (300, DATA_CLIENTE, True))
        sql, params = cursor.calls[0]
        self.assertIn(
            "INSERT INTO chatbot.historico_mensagens",
            sql,
        )
        self.assertEqual(params[0:3], (10, 20, "wamid.cliente"))


if __name__ == "__main__":
    unittest.main()
```

## Passo 21 - Executar a validação e o rollout

Executar integralmente os comandos, consultas e cenários descritos em
**Critérios de aplicação, validação e rollout**. A implementação só estará
concluída quando todos os itens do **Critério de conclusão após a aplicação**
forem atendidos.
