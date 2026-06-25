# Plano de implementação - fluxo por etapas

Status: revisado, ainda não aplicado.

## Objetivo

Reorganizar o microfluxo de resposta do worker para que cada etapa seja
responsável por:

- identificar o contexto da mensagem recebida;
- decidir se a resposta é normal, tratamento de mídia, tratamento financeiro ou
  tratamento de contexto;
- chamar diretamente os senders em `core/integrations/whatsapp/pywa_functions`;
- retornar o mesmo contrato que o `flow_worker` já espera.

Esse plano não muda regra de negócio, fluxo de atendimento nem semântica de
commit/rollback. A mudança é estrutural.

## Arquivos removidos

Esses arquivos deixam de existir porque a responsabilidade deles passa para a
pasta `workers/worker_flow/response_flow/etapas`:

```text
workers/worker_flow/response_flow/flow_sender.py
workers/worker_flow/response_flow/flow_treat_context.py
workers/worker_flow/response_flow/flow_treat_financial.py
workers/worker_flow/response_flow/flow_treat_unsupported_type.py
workers/worker_flow/response_flow/rotear_resposta_cliente.py
workers/worker_flow/valida_resposta_cliente.py
```

Justificativa: se a pasta `etapas` passa a identificar contexto e chamar os
senders, manter esses arquivos criaria dois desenhos concorrentes para a mesma
decisão.

## Contrato preservado

Todo resolver de etapa deve continuar retornando o mesmo formato de
`contexto_envio`:

```python
{
    "enviou": True | False,
    "resposta_ja_existia": True | False,
    "mensagem_bot": "...",              # quando houver envio novo
    "id_hash_msg_bot": "...",
    "id_etapa_resultante": 1,
    "tipo_mensagem": "text",            # quando houver envio novo
    "canal": "meta_whatsapp",           # quando houver envio novo
    "tratamento": True | False,         # quando for tratamento
    "tipo_tratamento": "...",           # quando for tratamento
    "atualizar_conversa": True | False,
    "atualizar_last_from_bot": True | False,
}
```

## Proteções que não podem desaparecer

O `flow_resolver.py` substitui o ponto comum que antes passava pelo
`flow_sender.py` e pelo `rotear_resposta_cliente.py`.

Por isso, a proteção que existia no `flow_sender.py` precisa acontecer no
`flow_resolver.py`, antes de qualquer chamada para `etapa_inicial.py`,
`primeira_etapa.py` ou qualquer sender:

```python
resposta_bot_atual = (
    contexto_historico["resposta_bot_para_mensagem_atual"] or {}
)

if resposta_bot_atual:
    logger.info(...)
    return {
        "enviou": False,
        "resposta_ja_existia": True,
        "id_hash_msg_bot": resposta_bot_atual.get("id_hash_msg"),
        "id_etapa_resultante": resposta_bot_atual.get("id_etapa"),
    }

if retry_count > 1:
    logger.info(...)
```

No plano, essa lógica fica concentrada em
`workers/worker_flow/response_flow/etapas/apoio.py` para evitar repetição, mas
é chamada pelo `flow_resolver.py` antes de despachar a mensagem para qualquer
etapa.

Regra obrigatória para toda etapa atual e futura:

1. `flow_resolver.py` verifica `resposta_bot_para_mensagem_atual`;
2. se já houver resposta do bot, retorna `resposta_ja_existia=True` sem chamar
   etapa e sem chamar Meta;
3. se for retry sem resposta persistida, registra log de reprocessamento;
4. só depois despacha para a etapa correta;
5. a etapa decide contexto e chama sender normal ou sender de tratamento.

Isso preserva o comportamento que evita resposta duplicada quando o worker cai
depois de responder pela Meta e antes de marcar a fila como `sent`.

## Fluxo final

```text
flow_worker.py
    -> flow_resolver.py
        -> barreira global: resposta já existente / retry
        -> etapas/etapa_inicial.py
        -> etapas/primeira_etapa.py
            -> etapas/valida_etapas/valida_midia.py
            -> etapas/valida_etapas/valida_financeiro.py
            -> etapas/valida_etapas/valida_nome.py
            -> core/integrations/whatsapp/pywa_functions/*
```

## Passo 1 - criar `flow_resolver.py`

Arquivo: `workers/worker_flow/response_flow/flow_resolver.py`

```python
import logging

from workers.worker_flow.response_flow.etapas.apoio import (
    logar_reprocessamento_sem_resposta,
    logar_resposta_existente,
    montar_contexto_resposta_existente,
)
from workers.worker_flow.response_flow.etapas.etapa_inicial import (
    resolver_etapa_inicial,
)
from workers.worker_flow.response_flow.etapas.primeira_etapa import (
    resolver_primeira_etapa,
)


logger = logging.getLogger("worker.flow_resolver")


def flow_resolver(contexto_historico):
    contexto_existente = montar_contexto_resposta_existente(contexto_historico)
    if contexto_existente:
        logar_resposta_existente(
            logger,
            "flow_resolver_idempotencia_ok",
            contexto_historico,
        )
        return contexto_existente

    logar_reprocessamento_sem_resposta(
        logger,
        "flow_resolver_reprocessamento",
        contexto_historico,
    )

    id_etapa_atual = contexto_historico.get("id_etapa_atual")

    if id_etapa_atual is None:
        contexto_resposta = resolver_etapa_inicial(contexto_historico)
        return contexto_resposta

    if id_etapa_atual == 1:
        contexto_resposta = resolver_primeira_etapa(contexto_historico)
        return contexto_resposta

    logger.warning(
        "flow_resolver_etapa_pendente | acao=nao_enviar id_conversa=%s etapa_atual=%s etapa_resposta=%s",
        contexto_historico["id_conversa"],
        id_etapa_atual,
        contexto_historico.get("id_etapa_resposta"),
    )
    raise NotImplementedError(
        f"Resolver da etapa {id_etapa_atual} ainda nao implementado"
    )
```

## Passo 2 - criar apoio comum das etapas

Arquivo: `workers/worker_flow/response_flow/etapas/apoio.py`

```python
from core.logging_config import short_value


def montar_contexto_resposta_existente(
    contexto_historico,
    *,
    tratamento=False,
    tipo_tratamento=None,
    atualizar_conversa=True,
    atualizar_last_from_bot=True,
):
    resposta_bot_atual = (
        contexto_historico["resposta_bot_para_mensagem_atual"] or {}
    )

    if not resposta_bot_atual:
        return None

    contexto_resposta = {
        "enviou": False,
        "resposta_ja_existia": True,
        "id_hash_msg_bot": resposta_bot_atual.get("id_hash_msg"),
        "id_etapa_resultante": resposta_bot_atual.get("id_etapa"),
        "atualizar_conversa": atualizar_conversa,
        "atualizar_last_from_bot": atualizar_last_from_bot,
    }

    if tratamento:
        contexto_resposta["tratamento"] = True
        contexto_resposta["tipo_tratamento"] = tipo_tratamento

    return contexto_resposta


def logar_resposta_existente(
    logger,
    evento,
    contexto_historico,
    *,
    tipo_tratamento=None,
):
    mensagem_cliente_atual = contexto_historico["mensagem_cliente_atual"]
    resposta_bot_atual = (
        contexto_historico["resposta_bot_para_mensagem_atual"] or {}
    )

    logger.info(
        "%s | motivo=resposta_bot_ja_registrada acao=nao_enviar id_conversa=%s id_mensagem_fila=%s id_hash_cliente=%s id_resposta_bot=%s etapa_bot=%s tratamento=%s retry=%s",
        evento,
        contexto_historico["id_conversa"],
        mensagem_cliente_atual["id_mensagem_fila"],
        mensagem_cliente_atual["id_hash_msg"],
        resposta_bot_atual.get("id_mensagem"),
        resposta_bot_atual.get("id_etapa"),
        tipo_tratamento,
        contexto_historico["retry_count"],
    )


def logar_reprocessamento_sem_resposta(
    logger,
    evento,
    contexto_historico,
    *,
    tipo_tratamento=None,
):
    if contexto_historico["retry_count"] <= 1:
        return

    mensagem_cliente_atual = contexto_historico["mensagem_cliente_atual"]

    logger.info(
        "%s | motivo=retry_maior_que_um acao=continuar_sem_resposta_previa id_conversa=%s id_mensagem_fila=%s id_hash_cliente=%s retry=%s tratamento=%s",
        evento,
        contexto_historico["id_conversa"],
        mensagem_cliente_atual["id_mensagem_fila"],
        mensagem_cliente_atual["id_hash_msg"],
        contexto_historico["retry_count"],
        tipo_tratamento,
    )


def logar_tratamento_texto(logger, contexto_historico, motivo):
    mensagem_cliente_atual = contexto_historico["mensagem_cliente_atual"]

    logger.info(
        "resposta_cliente_tratamento | motivo=%s acao=tratar_sem_avancar id_conversa=%s id_mensagem_fila=%s cliente=%s phone_number_id=%s etapa_cliente=%s etapa_resposta=%s",
        motivo,
        contexto_historico["id_conversa"],
        mensagem_cliente_atual["id_mensagem_fila"],
        short_value(mensagem_cliente_atual["cliente_telefone"]),
        short_value(mensagem_cliente_atual["id_phone_unidade"]),
        contexto_historico["id_etapa_cliente"],
        contexto_historico["id_etapa_resposta"],
    )


def logar_tipo_nao_suportado(logger, contexto_historico):
    mensagem_cliente_atual = contexto_historico["mensagem_cliente_atual"]

    logger.info(
        "resposta_cliente_invalida | motivo=tipo_mensagem_nao_suportado acao=tratar_sem_avancar id_conversa=%s id_mensagem_fila=%s cliente=%s phone_number_id=%s tipo=%s etapa_cliente=%s etapa_resposta=%s",
        contexto_historico["id_conversa"],
        mensagem_cliente_atual["id_mensagem_fila"],
        short_value(mensagem_cliente_atual["cliente_telefone"]),
        short_value(mensagem_cliente_atual["id_phone_unidade"]),
        contexto_historico.get("tipo_mensagem_atual"),
        contexto_historico["id_etapa_cliente"],
        contexto_historico["id_etapa_resposta"],
    )
```

## Passo 3 - criar validador de mídia/tipo

Arquivo: `workers/worker_flow/response_flow/etapas/valida_etapas/valida_midia.py`

```python
TIPOS_MENSAGEM_SUPORTADOS = {"text", "interactive"}
TIPO_TRATAMENTO_TIPO_NAO_SUPORTADO = "tipo_mensagem_nao_suportado"


def mensagem_tem_tipo_nao_suportado(contexto_historico):
    tipo_mensagem = contexto_historico.get("tipo_mensagem_atual")
    return tipo_mensagem not in TIPOS_MENSAGEM_SUPORTADOS
```

## Passo 4 - criar validador financeiro

Arquivo: `workers/worker_flow/response_flow/etapas/valida_etapas/valida_financeiro.py`

```python
import re
import unicodedata


TIPO_TRATAMENTO_FINANCEIRO = "pergunta_financeira"

PADRAO_PERGUNTA_FINANCEIRA = re.compile(
    r"\b("
    r"valor(?:es)?|"
    r"preco(?:s)?|"
    r"custo(?:s)?|"
    r"mensalidade(?:s)?|"
    r"mensal|"
    r"investimento(?:s)?|"
    r"capital|"
    r"quanto\s+custa|"
    r"qual\s+(?:o\s+)?(?:valor|preco|custo)"
    r")\b"
)


def mensagem_pergunta_financeira(contexto_historico):
    if contexto_historico.get("tipo_mensagem_atual") != "text":
        return False

    texto = contexto_historico.get("texto_cliente_atual") or ""
    texto_normalizado = normalizar_texto(texto)

    return bool(PADRAO_PERGUNTA_FINANCEIRA.search(texto_normalizado))


def normalizar_texto(texto):
    texto_sem_acento = unicodedata.normalize("NFKD", texto)
    texto_ascii = "".join(
        caractere
        for caractere in texto_sem_acento
        if not unicodedata.combining(caractere)
    )

    return texto_ascii.lower()
```

## Passo 5 - criar validador de nome da etapa 1

Arquivo: `workers/worker_flow/response_flow/etapas/valida_etapas/valida_nome.py`

```python
import re

from workers.worker_flow.response_flow.etapas.valida_etapas.valida_financeiro import (
    normalizar_texto,
)


TIPO_TRATAMENTO_NOME_INVALIDO = "nome_invalido"

PADRAO_CARACTERE_INVALIDO_NOME = re.compile(r"[^a-z\s'-]")
PADRAO_REPETICAO_CARACTERE = re.compile(r"([a-z])\1{3,}")
PADRAO_PALAVRAS = re.compile(r"[a-z]+")

PALAVRAS_NOME_PEJORATIVAS = {
    "bosta",
    "caralho",
    "fdp",
    "merda",
    "porra",
    "puta",
    "puto",
}


def mensagem_nome_invalido(contexto_historico):
    if contexto_historico.get("tipo_mensagem_atual") != "text":
        return False

    texto = contexto_historico.get("texto_cliente_atual") or ""
    texto_normalizado = normalizar_texto(texto).strip()
    texto_compacto = re.sub(r"\s+", "", texto_normalizado)

    if len(texto_compacto) < 2:
        return True

    if PADRAO_CARACTERE_INVALIDO_NOME.search(texto_normalizado):
        return True

    if PADRAO_REPETICAO_CARACTERE.search(texto_compacto):
        return True

    if _tem_padrao_repetitivo(texto_compacto):
        return True

    palavras = set(PADRAO_PALAVRAS.findall(texto_normalizado))
    return bool(palavras & PALAVRAS_NOME_PEJORATIVAS)


def _tem_padrao_repetitivo(texto_compacto):
    for tamanho_bloco in range(1, 4):
        if len(texto_compacto) < tamanho_bloco * 3:
            continue

        bloco = texto_compacto[:tamanho_bloco]
        repeticoes, resto = divmod(len(texto_compacto), tamanho_bloco)

        if resto == 0 and texto_compacto == bloco * repeticoes:
            return True

    return False
```

## Passo 6 - implementar etapa inicial

Arquivo: `workers/worker_flow/response_flow/etapas/etapa_inicial.py`

```python
import logging

from core.integrations.whatsapp.pywa_functions.etapas import sender_etapa1
from core.integrations.whatsapp.pywa_functions.tratamentos_financeiros import (
    sender_tratamento_financeiro,
)
from core.integrations.whatsapp.pywa_functions.tratamentos_type import (
    sender_tratamento_tipo_nao_suportado,
)
from workers.worker_flow.response_flow.etapas.apoio import (
    logar_tipo_nao_suportado,
    logar_tratamento_texto,
)
from workers.worker_flow.response_flow.etapas.valida_etapas.valida_financeiro import (
    TIPO_TRATAMENTO_FINANCEIRO,
    mensagem_pergunta_financeira,
)
from workers.worker_flow.response_flow.etapas.valida_etapas.valida_midia import (
    TIPO_TRATAMENTO_TIPO_NAO_SUPORTADO,
    mensagem_tem_tipo_nao_suportado,
)


logger = logging.getLogger("worker.etapa_inicial")


def resolver_etapa_inicial(contexto_historico):
    mensagem_cliente_atual = contexto_historico["mensagem_cliente_atual"]
    id_etapa_cliente = contexto_historico["id_etapa_cliente"]

    if mensagem_tem_tipo_nao_suportado(contexto_historico):
        logar_tipo_nao_suportado(logger, contexto_historico)

        return sender_tratamento_tipo_nao_suportado(
            cliente_telefone=mensagem_cliente_atual["cliente_telefone"],
            phone_id_unidade=mensagem_cliente_atual["id_phone_unidade"],
            id_etapa=id_etapa_cliente,
            tipo_mensagem=contexto_historico.get("tipo_mensagem_atual"),
            conversa_nova=True,
        )

    if mensagem_pergunta_financeira(contexto_historico):
        logar_tratamento_texto(
            logger,
            contexto_historico,
            TIPO_TRATAMENTO_FINANCEIRO,
        )

        return sender_tratamento_financeiro(
            cliente_telefone=mensagem_cliente_atual["cliente_telefone"],
            phone_id_unidade=mensagem_cliente_atual["id_phone_unidade"],
            id_etapa=id_etapa_cliente,
            conversa_nova=True,
        )

    return sender_etapa1(
        cliente_telefone=mensagem_cliente_atual["cliente_telefone"],
        phone_id_unidade=mensagem_cliente_atual["id_phone_unidade"],
    )
```

## Passo 7 - implementar primeira etapa

Arquivo: `workers/worker_flow/response_flow/etapas/primeira_etapa.py`

```python
import logging

from core.integrations.whatsapp.pywa_functions.tratamentos_context import (
    sender_tratamento_contexto_nome_invalido,
)
from core.integrations.whatsapp.pywa_functions.tratamentos_financeiros import (
    sender_tratamento_financeiro,
)
from core.integrations.whatsapp.pywa_functions.tratamentos_type import (
    sender_tratamento_tipo_nao_suportado,
)
from workers.worker_flow.response_flow.etapas.apoio import (
    logar_tipo_nao_suportado,
    logar_tratamento_texto,
)
from workers.worker_flow.response_flow.etapas.valida_etapas.valida_financeiro import (
    TIPO_TRATAMENTO_FINANCEIRO,
    mensagem_pergunta_financeira,
)
from workers.worker_flow.response_flow.etapas.valida_etapas.valida_midia import (
    TIPO_TRATAMENTO_TIPO_NAO_SUPORTADO,
    mensagem_tem_tipo_nao_suportado,
)
from workers.worker_flow.response_flow.etapas.valida_etapas.valida_nome import (
    TIPO_TRATAMENTO_NOME_INVALIDO,
    mensagem_nome_invalido,
)


logger = logging.getLogger("worker.primeira_etapa")


def resolver_primeira_etapa(contexto_historico):
    mensagem_cliente_atual = contexto_historico["mensagem_cliente_atual"]
    id_conversa = contexto_historico["id_conversa"]
    id_etapa_cliente = contexto_historico["id_etapa_cliente"]
    id_etapa_resposta = contexto_historico["id_etapa_resposta"]

    if mensagem_tem_tipo_nao_suportado(contexto_historico):
        logar_tipo_nao_suportado(logger, contexto_historico)

        return sender_tratamento_tipo_nao_suportado(
            cliente_telefone=mensagem_cliente_atual["cliente_telefone"],
            phone_id_unidade=mensagem_cliente_atual["id_phone_unidade"],
            id_etapa=id_etapa_cliente,
            tipo_mensagem=contexto_historico.get("tipo_mensagem_atual"),
            conversa_nova=False,
        )

    if mensagem_pergunta_financeira(contexto_historico):
        logar_tratamento_texto(
            logger,
            contexto_historico,
            TIPO_TRATAMENTO_FINANCEIRO,
        )

        return sender_tratamento_financeiro(
            cliente_telefone=mensagem_cliente_atual["cliente_telefone"],
            phone_id_unidade=mensagem_cliente_atual["id_phone_unidade"],
            id_etapa=id_etapa_cliente,
            conversa_nova=False,
        )

    if mensagem_nome_invalido(contexto_historico):
        logar_tratamento_texto(
            logger,
            contexto_historico,
            TIPO_TRATAMENTO_NOME_INVALIDO,
        )

        return sender_tratamento_contexto_nome_invalido(
            cliente_telefone=mensagem_cliente_atual["cliente_telefone"],
            phone_id_unidade=mensagem_cliente_atual["id_phone_unidade"],
            id_etapa=id_etapa_cliente,
        )

    logger.warning(
        "primeira_etapa_proxima_etapa_pendente | acao=nao_enviar id_conversa=%s etapa_resposta=%s",
        id_conversa,
        id_etapa_resposta,
    )
    raise NotImplementedError(
        f"Sender da etapa {id_etapa_resposta} ainda nao implementado"
    )
```

## Passo 8 - alterar `flow_worker.py`

Arquivo: `workers/worker_flow/response_flow/flow_worker.py`

```python
import logging

import psycopg2

from core.cache.cache_unidade import UnidadeNaoEncontrada
from core.database.connection_aws import get_conn
from core.integrations.whatsapp.exceptions import ErroEnvioMeta
from core.logging_config import short_value
from core.repositories.querys import pegar_mensagens_da_fila, tentar_lock_conversa
from core.repositories.updates import vincular_mensagem_fila_a_conversa
from workers.tratamento_erros_externos.erro_conexao import handle_erro_conexao
from workers.tratamento_erros_externos.erro_generico import handle_erro_generico
from workers.tratamento_erros_externos.exceptions import BancoFalhouAposEnvioMeta
from workers.tratamento_erros_externos.unidade_nao_encontrada import handle_unidade_nao_encontrada
from workers.worker_flow.response_flow.flow_resolver import flow_resolver
from workers.worker_flow.suport_functions import (
    aguardar_fila_vazia,
    atualizar_banco_com_contexto_final,
    atualizar_estado_com_contexto,
    atualizar_estado_com_mensagem,
    atualizar_estado_lock,
    confirmar_cache_cliente_se_pendente,
    criar_estado_ciclo,
    finalizar_mensagem_processada,
    liberar_lock_conversa_se_necessario,
    logar_lock_recusado,
    montar_mensagem_fila,
    reagendar_se_houver_mensagem_anterior,
    reparar_cache_cliente_stale_se_fk_invalida,
    reparar_cache_unidade_stale_se_fk_invalida,
)
from workers.worker_flow.tratar_bloqueio import tratar_conversa_bloqueada
from workers.worker_flow.valida_banco import validar_banco_mensagem
from workers.worker_flow.valida_historico import valida_historico

logger = logging.getLogger("worker.response_flow")


def worker_flow():
    logger.info("worker_iniciado")

    max_retry = 3
    retry_delay = 5

    while True:
        print("\n\n\n---------------------NOVO CICLO---------------------\n\n\n")
        logger.info("---------- ciclo_worker_inicio ----------")

        conn_ciclo = None
        cursor_ciclo = None
        estado_ciclo = criar_estado_ciclo()
        contexto_envio = {}

        try:
            conn_ciclo = get_conn(application_name="worker_chatbot")
            cursor_ciclo = conn_ciclo.cursor()
            retry_delay = 5
            logger.debug("ciclo_conexao_banco_ok | acao=dequeue")

            registro = pegar_mensagens_da_fila(cursor_ciclo)
            conn_ciclo.commit()

            if not registro:
                conn_ciclo.close()
                conn_ciclo = None
                cursor_ciclo = None
                aguardar_fila_vazia()
                continue

            mensagem = montar_mensagem_fila(registro)
            atualizar_estado_com_mensagem(estado_ciclo, mensagem)

            logger.info(
                "mensagem_processando | acao=iniciar id_mensagem=%s cliente=%s phone_number_id=%s tipo=%s retry=%s",
                mensagem["id_mensagem"],
                short_value(mensagem["cliente_telefone"]),
                short_value(mensagem["id_phone_unidade"]),
                mensagem["tipo_mensagem"],
                mensagem["retry_count"],
            )

            contexto_banco = validar_banco_mensagem(
                mensagem,
                cursor_ciclo,
            )
            atualizar_estado_com_contexto(estado_ciclo, contexto_banco)

            contexto_conversa = contexto_banco["conversa"]
            id_conversa = contexto_conversa["id_conversa"]

            vincular_mensagem_fila_a_conversa(
                mensagem["id_mensagem"],
                id_conversa,
                cursor_ciclo,
            )
            conn_ciclo.commit()
            logger.debug(
                "mensagem_conversa_vinculada | acao=commit id_mensagem=%s id_conversa=%s estado=%s",
                mensagem["id_mensagem"],
                id_conversa,
                contexto_conversa["estado"],
            )

            confirmar_cache_cliente_se_pendente(contexto_banco)

            if contexto_conversa["estado"] == "bloqueada":
                tratar_conversa_bloqueada(
                    mensagem["id_mensagem"],
                    mensagem["cliente_telefone"],
                    mensagem["id_phone_unidade"],
                    id_conversa,
                    cursor_ciclo,
                )
                conn_ciclo.commit()
                continue

            lock_ok, lock_version = tentar_lock_conversa(id_conversa, cursor_ciclo)
            conn_ciclo.commit()
            atualizar_estado_lock(estado_ciclo, lock_ok, lock_version)

            if not lock_ok:
                logar_lock_recusado(mensagem, contexto_banco)
                continue

            if reagendar_se_houver_mensagem_anterior(
                    mensagem,
                    contexto_banco,
                    lock_version,
                    cursor_ciclo,
            ):
                conn_ciclo.commit()
                continue

            contexto_historico = valida_historico(
                mensagem,
                contexto_banco,
                cursor_ciclo,
            )
            conn_ciclo.commit()
            logger.debug(
                "historico_contexto_ok | acao=commit id_mensagem=%s id_conversa=%s etapa_cliente=%s etapa_resposta=%s inserido=%s",
                mensagem["id_mensagem"],
                id_conversa,
                contexto_historico["id_etapa_cliente"],
                contexto_historico["id_etapa_resposta"],
                contexto_historico["mensagem_cliente_inserida"],
            )

            contexto_envio = flow_resolver(contexto_historico)

            try:
                contexto_final = atualizar_banco_com_contexto_final(
                    contexto_historico,
                    contexto_envio,
                    cursor_ciclo,
                )
                conn_ciclo.commit()

            except Exception as erro:
                if contexto_envio.get("enviou"):
                    raise BancoFalhouAposEnvioMeta(
                        "Banco falhou depois da Meta confirmar envio",
                        id_mensagem=mensagem["id_mensagem"],
                        id_conversa=id_conversa,
                        id_hash_msg_bot=contexto_envio.get("id_hash_msg_bot"),
                        id_etapa=contexto_envio.get("id_etapa_resultante"),
                    ) from erro

                raise

            logger.debug(
                "resposta_bot_contexto_final_ok | acao=commit id_mensagem=%s id_conversa=%s etapa=%s resposta_ja_existia=%s id_hash_msg_bot=%s tratamento=%s tipo_tratamento=%s",
                mensagem["id_mensagem"],
                id_conversa,
                contexto_final["id_etapa_resultante"],
                contexto_final["resposta_ja_existia"],
                contexto_final["id_hash_msg_bot"],
                contexto_envio.get("tratamento", False),
                contexto_envio.get("tipo_tratamento"),
            )

            finalizar_mensagem_processada(
                mensagem,
                contexto_banco,
                lock_version,
                cursor_ciclo,
            )
            conn_ciclo.commit()

        except ErroEnvioMeta as erro:
            logger.warning(
                "meta_envio_erro | acao=reagendar_sem_sent id_mensagem=%s cliente=%s phone_number_id=%s etapa=%s erro=%s",
                estado_ciclo["id_mensagem"],
                short_value(estado_ciclo["cliente_telefone"]),
                short_value(estado_ciclo["id_phone_unidade"]),
                erro.id_etapa,
                erro,
            )
            if conn_ciclo:
                conn_ciclo.rollback()

            handle_erro_generico(
                cursor_ciclo,
                estado_ciclo["id_mensagem"],
                erro,
                max_retry,
            )

            if conn_ciclo:
                conn_ciclo.commit()

        except BancoFalhouAposEnvioMeta as erro:
            logger.critical(
                "banco_falhou_apos_envio_meta | risco=resposta_duplicada acao=reagendar_sem_sent id_mensagem=%s id_conversa=%s etapa=%s id_hash_msg_bot=%s tratamento=%s tipo_tratamento=%s erro=%s",
                erro.id_mensagem,
                erro.id_conversa,
                erro.id_etapa,
                erro.id_hash_msg_bot,
                contexto_envio.get("tratamento", False),
                contexto_envio.get("tipo_tratamento"),
                erro,
            )
            if conn_ciclo:
                conn_ciclo.rollback()

            handle_erro_generico(
                cursor_ciclo,
                estado_ciclo["id_mensagem"],
                erro,
                max_retry,
            )

            if conn_ciclo:
                conn_ciclo.commit()

        except psycopg2.OperationalError as erro:
            logger.warning(
                "banco_operacional_erro | acao=retry_conexao id_mensagem=%s erro=%s",
                estado_ciclo["id_mensagem"],
                erro,
            )
            retry_delay = handle_erro_conexao(erro, retry_delay)
            continue

        except UnidadeNaoEncontrada as erro:
            logger.warning(
                "unidade_nao_encontrada | acao=tratar_unidade_invalida id_mensagem=%s cliente=%s phone_number_id=%s erro=%s",
                estado_ciclo["id_mensagem"],
                short_value(estado_ciclo["cliente_telefone"]),
                short_value(estado_ciclo["id_phone_unidade"]),
                erro,
            )
            if conn_ciclo:
                conn_ciclo.rollback()

            handle_unidade_nao_encontrada(
                cursor_ciclo,
                estado_ciclo["id_mensagem"],
                erro,
            )

            if conn_ciclo:
                conn_ciclo.commit()

        except Exception as erro:
            logger.exception(
                "mensagem_erro | acao=tratar_erro_generico id_mensagem=%s cliente=%s phone_number_id=%s id_conversa=%s estado=%s erro=%s",
                estado_ciclo["id_mensagem"],
                short_value(estado_ciclo["cliente_telefone"]),
                short_value(estado_ciclo["id_phone_unidade"]),
                estado_ciclo["id_conversa"],
                estado_ciclo["estado"],
                erro,
            )
            if conn_ciclo:
                conn_ciclo.rollback()

            reparar_cache_cliente_stale_se_fk_invalida(erro, estado_ciclo)
            reparar_cache_unidade_stale_se_fk_invalida(erro, estado_ciclo)

            handle_erro_generico(
                cursor_ciclo,
                estado_ciclo["id_mensagem"],
                erro,
                max_retry,
            )

            if conn_ciclo:
                conn_ciclo.commit()

        finally:
            if conn_ciclo:
                try:
                    unlock_realizado = liberar_lock_conversa_se_necessario(
                        cursor_ciclo,
                        estado_ciclo,
                    )

                    if unlock_realizado is not None:
                        conn_ciclo.commit()

                except Exception as erro:
                    logger.exception(
                        "finalizacao_ciclo_falhou | acao=continuar_para_close erro=%s",
                        erro,
                    )

                finally:
                    try:
                        conn_ciclo.close()

                    except Exception as erro:
                        logger.exception(
                            "conexao_ciclo_close_falhou | acao=registrar_e_continuar erro=%s",
                            erro,
                        )
```

## Passo 9 - remover testes acoplados ao fluxo antigo

Arquivos a deletar:

```text
tests/unit/test_flow_sender.py
tests/unit/test_flow_treat_context.py
tests/unit/test_flow_treat_financial.py
tests/unit/test_flow_treat_unsupported_type.py
tests/unit/test_rotear_resposta_cliente.py
tests/unit/test_valida_resposta_cliente.py
```

Esses testes devem ser substituídos por testes dos novos pontos:

```text
tests/unit/test_flow_resolver.py
tests/unit/test_etapa_inicial.py
tests/unit/test_primeira_etapa.py
tests/unit/test_validadores_etapas.py
```

## Passo 10 - atualizar testes que referenciam o roteador antigo

Arquivos a alterar:

```text
tests/unit/test_worker_flow_runtime.py
tests/unit/test_worker_flow_contract.py
tests/unit/test_fluxo_turno_abc.py
```

Mudanças esperadas:

```text
rotear_resposta_cliente -> flow_resolver
flow_sender.flow_sender -> flow_resolver.flow_resolver ou resolver da etapa específica
```

## Passo 11 - atualizar documentação

Arquivos a revisar após aplicar o código:

```text
workers/README.md
PADROES_DE_ARQUITETURA.md
REGRAS_DE_NEGOCIO.md
```

Pontos a documentar:

- o `flow_worker` não decide contexto de etapa;
- `flow_worker` só controla transação, lock, retry, erro e persistência;
- `flow_resolver.py` escolhe a etapa;
- a pasta `response_flow/etapas` decide contexto e chama senders;
- validadores reutilizáveis ficam em `response_flow/etapas/valida_etapas`;
- funções PyWa continuam somente em `core/integrations/whatsapp/pywa_functions`;
- mensagens continuam em `core/integrations/whatsapp/messages`.

## Passo 12 - validações obrigatórias depois da aplicação

Buscar imports mortos:

```powershell
rg -n "rotear_resposta_cliente|valida_resposta_cliente|flow_treat_context|flow_treat_financial|flow_treat_unsupported_type|flow_sender" workers tests
```

O resultado esperado é zero ocorrências, exceto se algum README ainda estiver
sendo atualizado.

Rodar testes:

```powershell
python -m pytest tests
```

Rodar check do Django:

```powershell
python callback/manage.py check
```

## Resultado esperado

Depois de aplicado:

- cliente iniciando conversa com texto continua recebendo etapa 1;
- cliente iniciando conversa com mídia continua recebendo saudação + aviso de
  mídia + pedido de nome;
- cliente iniciando conversa com pergunta financeira continua recebendo saudação
  + aviso financeiro + pedido de nome;
- cliente na etapa 1 enviando mídia recebe tratamento de mídia + pedido de nome;
- cliente na etapa 1 perguntando valor recebe tratamento financeiro + pedido de
  nome;
- cliente na etapa 1 enviando nome inválido recebe tratamento de contexto +
  pedido de nome;
- resposta já existente continua sendo reconhecida em retry;
- mensagem válida não é perdida;
- o `flow_worker` continua sendo o único dono de commit, rollback e close.
