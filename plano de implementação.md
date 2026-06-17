# Plano de Implementacao: Tratamento de Mensagens Nao Suportadas

## Objetivo

Criar uma camada de tratamento para respostas inesperadas do cliente sem avancar o fluxo da conversa.

Neste primeiro momento, o tratamento sera generico e focado em tipo de mensagem:

- `text` continua valido.
- `interactive` continua valido.
- qualquer outro tipo (`image`, `video`, `audio`, `document`, `sticker`, `location`, `contacts`, `reaction`, `unsupported` etc.) sera tratado como mensagem nao suportada.

O fluxo esperado fica assim:

```text
worker valida banco
worker valida historico
worker valida resposta do cliente

se resposta for valida:
    flow_sender normal

se resposta for invalida:
    flow_treat_unsupported_type envia aviso ao cliente
    mensagem do bot entra no historico
    conversa NAO avanca etapa
    mensagem da fila vira sent
```

## Recaptura do desenho definido

O `flow_sender` continua limpo. Ele nao valida erro de resposta do cliente; ele apenas continua a etapa oficial quando a resposta ja foi considerada valida.

O `validar_resposta_cliente()` fica responsavel por decidir a rota:

- `resposta_valida`: segue para `flow_sender`;
- `tipo_mensagem_nao_suportado`: segue para `flow_treat_unsupported_type`;
- `mensagem_fora_de_contexto`: futuramente seguira para `flow_treat_context`.

O tratamento fora de contexto ainda nao sera implementado nesta etapa, mas o plano ja deixa o esqueleto reservado. A regra futura sera:

```text
validar_resposta_cliente olha id_etapa_cliente
se a etapa exige contexto especifico:
    valida se texto/botao recebido faz sentido para aquela etapa
    se nao fizer sentido:
        resultado = mensagem_fora_de_contexto

flow_treat_context usa id_etapa_cliente
envia uma mensagem do tipo:
    "Sua resposta esta fora de contexto para esta etapa. Vamos tentar novamente..."
    + a pergunta/opcoes da etapa atual
nao avanca conversa
salva o tratamento no historico
marca fila como sent somente depois de persistir
```

Importante:

- `id_etapa_cliente` representa a etapa que a mensagem do cliente esta respondendo;
- `id_etapa_resposta` representa a proxima etapa oficial do bot caso a resposta seja valida;
- tratamento de erro sempre usa `id_etapa_cliente`;
- sender oficial usa `id_etapa_resposta`.

Continuidade depois de tratamento:

- tratamento de midia/contexto registra a mensagem invalida do cliente no historico;
- registra a resposta de tratamento do bot no historico;
- marca a mensagem da fila como `sent` depois de persistir o tratamento;
- nao atualiza `conversa.id_etapa_atual`;
- nao atualiza `conversa.last_message_from`;
- portanto nao avanca o turno oficial da conversa;
- quando o cliente responder corretamente depois do tratamento, o proximo ciclo ainda usa a mesma etapa oficial e pode seguir para `flow_sender`.

Essa regra considera `last_message_from` como estado do turno oficial da conversa, nao como espelho literal de toda mensagem fisica enviada. Mensagens de tratamento ficam no historico, mas nao movem o ponteiro oficial da conversa.

## Decisao de arquitetura

O webhook continua simples e barato. Ele aceita mensagens validas da Meta e enfileira conforme as protecoes existentes.

O worker fica responsavel por interpretar se o tipo da mensagem e aceito na etapa atual.

Isso preserva:

- historico da mensagem invalida recebida;
- baixo custo no webhook;
- regra de turno atual;
- sender normal separado de tratamento;
- commits e rollbacks apenas em `worker_flow.py`;
- SQL apenas nos repositories ja existentes.

## Performance

Para mensagem normal (`text` ou `interactive`), a nova validacao tem custo praticamente nulo:

```python
tipo_mensagem in {"text", "interactive"}
```

Nao consulta Redis.
Nao consulta banco.
Nao chama Meta.

Apenas quando o tipo for invalido o sistema envia uma resposta de tratamento pela Meta.

## Decisao final da validacao

`validar_resposta_cliente()` retorna apenas um dicionario `contexto_validacao`.

A decisao principal fica em uma chave unica:

```python
contexto_validacao = validar_resposta_cliente(contexto_historico)
resultado_validacao = contexto_validacao["resultado"]

if resultado_validacao == "tipo_mensagem_nao_suportado":
    flow_treat_unsupported_type(...)

elif resultado_validacao == "mensagem_fora_de_contexto":
    flow_treat_context(...)

else:
    flow_sender(...)
```

Motivo:

- os resultados sao mutuamente exclusivos;
- evita varios booleanos soltos como `tipo_errado=True` e `fora_de_contexto=True`;
- mantem `contexto_validacao` como apoio para logs e dados do tratamento;
- ja deixa espaco para `mensagem_fora_de_contexto`, com um esqueleto separado e sem implementar a regra antes dela existir.

Auditoria rapida:

- `resultado_fila["status"]` no webhook continua como esta, porque e estado multiresultado.
- `rate_redis["redis_ok"]`, `rate_redis["flood"]` e equivalentes continuam como estao, porque fazem parte do fallback Redis -> banco -> memoria.
- `turno["pode_enfileirar"]` continua como esta, porque vem junto com `turno["motivo"]` e esta legivel.
- `contexto_conversa["estado"]` continua como esta, porque e estado de regra de negocio.

## Otimizacao de contexto do historico

Hoje o projeto consulta as ultimas 6 mensagens da conversa em `valida_historico`, mas esse contexto nao e usado pelo fluxo atual.

O fluxo atual precisa apenas de:

- dados da conversa atual;
- etapa atual do cliente (`id_etapa_cliente`);
- etapa candidata de resposta (`id_etapa_resposta`);
- mensagem atual do cliente ja inserida no historico;
- resposta do bot vinculada a mensagem atual, para idempotencia;
- tipo/texto/retry da mensagem atual.

Por isso este plano remove a consulta generica das ultimas 6 mensagens. A consulta especifica `buscar_resposta_bot_por_mensagem_cliente()` permanece, porque ela e essencial para evitar duplicidade quando a Meta ja recebeu uma resposta do bot e o worker caiu antes de marcar a fila como `sent`.

---

## Passo 0 - Alterar `core/integrations/whatsapp/sender.py`

Arquivo completo:

```python
import logging
from datetime import datetime
from zoneinfo import ZoneInfo

from core.integrations.whatsapp.exceptions import ErroEnvioMeta
from core.integrations.whatsapp.messages.senders import (
    enviar_mensagem_texto_com_botao,
)
from core.logging_config import short_value


logger = logging.getLogger("whatsapp.sender")

FUSO_HORARIO_ATENDIMENTO = ZoneInfo("America/Sao_Paulo")


def sender_etapa1(cliente_telefone, phone_id_unidade):
    saudacao = obter_saudacao_por_horario()
    mensagem_bot = f"Ola! {saudacao}."
    titulo_botao = "Aperte em mim"

    try:
        id_hash_msg_bot = enviar_mensagem_texto_com_botao(
            to=cliente_telefone,
            text=mensagem_bot,
            titulo_botao=titulo_botao,
            phone_id_unidade=phone_id_unidade,
        )

        logger.info(
            "sender_etapa1_ok | acao=enviar_meta cliente=%s phone_number_id=%s id_hash_msg_bot=%s botao=%s saudacao=%s",
            short_value(cliente_telefone),
            short_value(phone_id_unidade),
            id_hash_msg_bot,
            titulo_botao,
            saudacao,
        )

        return {
            "enviou": True,
            "resposta_ja_existia": False,
            "mensagem_bot": mensagem_bot,
            "id_hash_msg_bot": id_hash_msg_bot,
            "id_etapa_resultante": 1,
            "tipo_mensagem": "interactive_button",
            "canal": "meta_whatsapp",
        }

    except Exception as erro:
        logger.exception(
            "sender_etapa1_erro | motivo=meta_falhou acao=levantar_erro cliente=%s phone_number_id=%s erro=%s",
            short_value(cliente_telefone),
            short_value(phone_id_unidade),
            erro,
        )
        raise ErroEnvioMeta(
            "Meta falhou ao enviar mensagem da etapa 1",
            id_etapa=1,
            phone_id_unidade=phone_id_unidade,
            cliente_telefone=cliente_telefone,
        ) from erro


def obter_saudacao_por_horario(agora=None):
    agora = agora or datetime.now(FUSO_HORARIO_ATENDIMENTO)
    hora = agora.hour

    if 5 <= hora < 12:
        return "Bom dia"

    if 12 <= hora < 18:
        return "Boa tarde"

    return "Boa noite"
```

O que faz:

- Mantem a etapa 1 como sender oficial.
- Adiciona polimento simples de saudacao por horario.
- Nao interpreta nem corrige o texto do cliente.
- Usa apenas a hora atual em `America/Sao_Paulo`.
- Mantem o mesmo contrato de retorno do `flow_sender`.
- Se a Meta falhar, segue levantando `ErroEnvioMeta`.

---

## Passo 1 - Criar `core/integrations/whatsapp/sender_tratamento.py`

Arquivo completo:

```python
import logging

from core.integrations.whatsapp.exceptions import ErroEnvioMeta
from core.integrations.whatsapp.messages.senders import (
    enviar_mensagem_texto_com_botao,
)
from core.logging_config import short_value


logger = logging.getLogger("whatsapp.sender_tratamento")


def sender_tratamento_tipo_nao_suportado(
    cliente_telefone,
    phone_id_unidade,
    id_etapa,
    tipo_mensagem,
    mensagem_bot,
):
    titulo_botao = "Retornar ao atendimento"

    try:
        id_hash_msg_bot = enviar_mensagem_texto_com_botao(
            to=cliente_telefone,
            text=mensagem_bot,
            titulo_botao=titulo_botao,
            phone_id_unidade=phone_id_unidade,
            callback_data="retornar_atendimento",
        )

        logger.info(
            "sender_tratamento_tipo_nao_suportado_ok | acao=enviar_meta cliente=%s phone_number_id=%s etapa=%s tipo_cliente=%s id_hash_msg_bot=%s",
            short_value(cliente_telefone),
            short_value(phone_id_unidade),
            id_etapa,
            tipo_mensagem,
            id_hash_msg_bot,
        )

        return {
            "enviou": True,
            "resposta_ja_existia": False,
            "mensagem_bot": mensagem_bot,
            "id_hash_msg_bot": id_hash_msg_bot,
            "id_etapa_resultante": id_etapa,
            "tipo_mensagem": "interactive_button",
            "canal": "meta_whatsapp",
            "tratamento": True,
            "tipo_tratamento": "tipo_mensagem_nao_suportado",
            "atualizar_conversa": False,
        }

    except Exception as erro:
        logger.exception(
            "sender_tratamento_tipo_nao_suportado_erro | motivo=meta_falhou acao=levantar_erro cliente=%s phone_number_id=%s etapa=%s tipo_cliente=%s erro=%s",
            short_value(cliente_telefone),
            short_value(phone_id_unidade),
            id_etapa,
            tipo_mensagem,
            erro,
        )
        raise ErroEnvioMeta(
            "Meta falhou ao enviar tratamento de tipo de mensagem nao suportado",
            id_etapa=id_etapa,
            phone_id_unidade=phone_id_unidade,
            cliente_telefone=cliente_telefone,
        ) from erro
```

O que faz:

- Envia mensagem de tratamento com botao.
- Recebe o texto do tratamento pronto, porque quem decide se a mensagem e de inicio ou continuidade e o `flow_treat_unsupported_type`.
- Retorna o mesmo contrato de `contexto_envio` usado pelo worker.
- Marca `atualizar_conversa=False` para nao avancar etapa nem alterar `last_message_from`.
- Se a Meta falhar, levanta `ErroEnvioMeta` como os senders normais.

---

## Passo 2 - Alterar `workers/worker_flow/valida_historico.py`

Arquivo completo:

```python
import logging

from core.logging_config import short_value
from core.repositories.inserts import inserir_historico_mensagem_cliente
from core.repositories.querys import buscar_resposta_bot_por_mensagem_cliente


logger = logging.getLogger("worker.valida_historico")

ETAPA_INICIAL = 1
ETAPA_FINAL = 7


def valida_historico(mensagem, contexto_banco, cursor):
    contexto_conversa = contexto_banco["conversa"]
    id_conversa = contexto_conversa["id_conversa"]

    id_etapa_cliente = _resolver_etapa_cliente(contexto_conversa)
    id_etapa_resposta = _resolver_etapa_resposta(contexto_conversa, id_etapa_cliente)

    (
        id_historico_cliente,
        data_historico_cliente,
        cliente_inserido_no_historico,
    ) = inserir_historico_mensagem_cliente(
        mensagem=mensagem,
        id_conversa=id_conversa,
        id_etapa=id_etapa_cliente,
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

    logger.info(
        "historico_validado | acao=registrar_cliente id_mensagem=%s id_historico=%s inserido=%s id_conversa=%s etapa_cliente=%s etapa_resposta=%s last_from=%s retry=%s resposta_bot_existente=%s cliente=%s phone_number_id=%s",
        mensagem["id_mensagem"],
        id_historico_cliente,
        cliente_inserido_no_historico,
        id_conversa,
        id_etapa_cliente,
        id_etapa_resposta,
        contexto_conversa.get("last_message_from"),
        mensagem["retry_count"],
        bool(resposta_bot_para_mensagem_atual),
        short_value(mensagem["cliente_telefone"]),
        short_value(mensagem["id_phone_unidade"]),
    )

    return {
        "id_conversa": id_conversa,
        "id_etapa_atual": contexto_conversa.get("id_etapa_atual"),
        "id_etapa_cliente": id_etapa_cliente,
        "id_etapa_resposta": id_etapa_resposta,
        "status_dependente": contexto_conversa.get("status_dependente"),
        "last_message_from": contexto_conversa.get("last_message_from"),
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


def _resolver_etapa_resposta(contexto_conversa, id_etapa_cliente):
    id_etapa_atual = contexto_conversa.get("id_etapa_atual")
    last_message_from = contexto_conversa.get("last_message_from")

    if id_etapa_atual is None:
        return ETAPA_INICIAL

    if last_message_from == "bot":
        return min(id_etapa_atual + 1, ETAPA_FINAL)

    return id_etapa_cliente


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

O que muda:

- Remove a consulta generica das ultimas 6 mensagens da conversa.
- Mantem a insercao da mensagem atual do cliente no historico.
- Mantem a busca especifica por resposta do bot vinculada a mensagem atual da fila.
- Mantem `id_etapa_cliente` e `id_etapa_resposta` como chaves de contexto do ciclo.

---

## Passo 3 - Criar `workers/worker_flow/valida_resposta_cliente.py`

Arquivo completo:

```python
import logging

from core.logging_config import short_value


logger = logging.getLogger("worker.valida_resposta")

TIPOS_MENSAGEM_SUPORTADOS = {"text", "interactive"}

RESULTADO_RESPOSTA_VALIDA = "resposta_valida"
RESULTADO_TIPO_MENSAGEM_NAO_SUPORTADO = "tipo_mensagem_nao_suportado"
RESULTADO_MENSAGEM_FORA_DE_CONTEXTO = "mensagem_fora_de_contexto"


def validar_resposta_cliente(contexto_historico):
    tipo_mensagem = contexto_historico.get("tipo_mensagem_atual")

    if tipo_mensagem in TIPOS_MENSAGEM_SUPORTADOS:
        return {
            "resultado": RESULTADO_RESPOSTA_VALIDA,
            "tipo_tratamento": None,
            "motivo": None,
        }

    mensagem_cliente_atual = contexto_historico["mensagem_cliente_atual"]

    logger.info(
        "resposta_cliente_invalida | motivo=tipo_mensagem_nao_suportado acao=tratar_sem_avancar id_conversa=%s id_mensagem_fila=%s cliente=%s phone_number_id=%s tipo=%s etapa_cliente=%s etapa_resposta=%s",
        contexto_historico["id_conversa"],
        mensagem_cliente_atual["id_mensagem_fila"],
        short_value(mensagem_cliente_atual["cliente_telefone"]),
        short_value(mensagem_cliente_atual["id_phone_unidade"]),
        tipo_mensagem,
        contexto_historico["id_etapa_cliente"],
        contexto_historico["id_etapa_resposta"],
    )

    return {
        "resultado": RESULTADO_TIPO_MENSAGEM_NAO_SUPORTADO,
        "tipo_tratamento": RESULTADO_TIPO_MENSAGEM_NAO_SUPORTADO,
        "motivo": RESULTADO_TIPO_MENSAGEM_NAO_SUPORTADO,
        "tipo_mensagem": tipo_mensagem,
        "mensagem_bot": (
            "Por enquanto consigo processar apenas mensagens de texto ou botoes. "
            "Envie sua resposta novamente em texto ou clique no botao para retornar ao atendimento."
        ),
        "botao": "Retornar ao atendimento",
        "avancar_etapa": False,
    }
```

O que faz:

- Validacao barata em memoria.
- Nao consulta banco.
- Nao consulta Redis.
- Nao chama Meta.
- Se tipo for invalido, retorna contexto para tratamento.
- Usa `resultado` como chave unica de decisao do fluxo, evitando varios booleanos soltos.
- Deixa `mensagem_fora_de_contexto` reservado para quando essa regra for implementada.

---

## Passo 4 - Criar `workers/worker_flow/flow_treat_unsupported_type.py`

Arquivo completo:

```python
import logging

from core.integrations.whatsapp.sender_tratamento import (
    sender_tratamento_tipo_nao_suportado,
)


logger = logging.getLogger("worker.treat_unsupported_type")


def flow_treat_unsupported_type(contexto_historico, contexto_validacao):
    # Regra de negocio V1: esta versao nao trabalha com midias/anexos.
    # Midia recebida entra no historico, recebe tratamento e nao avanca etapa.
    id_conversa = contexto_historico["id_conversa"]
    mensagem_cliente_atual = contexto_historico["mensagem_cliente_atual"]
    resposta_bot_atual = (
        contexto_historico["resposta_bot_para_mensagem_atual"] or {}
    )

    if resposta_bot_atual:
        logger.info(
            "flow_treat_unsupported_type_idempotencia_ok | motivo=resposta_bot_ja_registrada acao=nao_enviar id_conversa=%s id_mensagem_fila=%s id_hash_cliente=%s id_resposta_bot=%s tratamento=%s",
            id_conversa,
            mensagem_cliente_atual["id_mensagem_fila"],
            mensagem_cliente_atual["id_hash_msg"],
            resposta_bot_atual.get("id_mensagem"),
            contexto_validacao["tipo_tratamento"],
        )
        return {
            "enviou": False,
            "resposta_ja_existia": True,
            "id_hash_msg_bot": resposta_bot_atual.get("id_hash_msg"),
            "id_etapa_resultante": resposta_bot_atual.get("id_etapa"),
            "tratamento": True,
            "tipo_tratamento": contexto_validacao["tipo_tratamento"],
            "atualizar_conversa": False,
        }

    if contexto_validacao["tipo_tratamento"] == "tipo_mensagem_nao_suportado":
        mensagem_bot = _montar_mensagem_tipo_nao_suportado(contexto_historico)

        return sender_tratamento_tipo_nao_suportado(
            cliente_telefone=mensagem_cliente_atual["cliente_telefone"],
            phone_id_unidade=mensagem_cliente_atual["id_phone_unidade"],
            id_etapa=contexto_historico["id_etapa_cliente"],
            tipo_mensagem=contexto_validacao.get("tipo_mensagem"),
            mensagem_bot=mensagem_bot,
        )

    logger.warning(
        "flow_treat_unsupported_type_nao_implementado | acao=erro id_conversa=%s tratamento=%s",
        id_conversa,
        contexto_validacao["tipo_tratamento"],
    )
    raise NotImplementedError(
        f"Tratamento {contexto_validacao['tipo_tratamento']} ainda nao implementado"
    )


def _montar_mensagem_tipo_nao_suportado(contexto_historico):
    if contexto_historico.get("id_etapa_atual") is None:
        return (
            "Ola! Vi que voce iniciou o atendimento com uma midia.\n\n"
            "Por enquanto eu so consigo continuar por mensagem de texto ou botoes. "
            "Envie uma mensagem de texto para comecarmos."
        )

    return (
        "Recebi uma midia, mas nesta etapa eu preciso que voce responda por texto "
        "ou use os botoes disponiveis.\n\n"
        "Envie uma mensagem de texto para continuarmos."
    )
```

O que faz:

- Recebe a decisao de `validar_resposta_cliente`.
- Antes de enviar, respeita idempotencia usando `resposta_bot_para_mensagem_atual`.
- Se ja existe resposta do bot para aquela mensagem da fila, nao envia de novo.
- Para tipo nao suportado, chama sender de tratamento.
- Se a conversa ainda nao tem etapa oficial (`id_etapa_atual is None`), envia mensagem de inicio com "para comecarmos".
- Se a conversa ja esta em andamento, envia mensagem generica de continuidade com "para continuarmos".

---

## Passo 5 - Criar `workers/worker_flow/flow_treat_context.py`

Arquivo completo:

```python
import logging


logger = logging.getLogger("worker.treat_context")


def flow_treat_context(contexto_historico, contexto_validacao):
    # Esqueleto reservado para a V1 quando as regras de contexto por etapa
    # forem definidas. Tratamento de contexto deve usar id_etapa_cliente,
    # repetir a pergunta/opcoes da etapa atual e nao avancar a conversa.
    id_conversa = contexto_historico["id_conversa"]
    id_etapa_cliente = contexto_historico["id_etapa_cliente"]
    mensagem_cliente_atual = contexto_historico["mensagem_cliente_atual"]

    logger.warning(
        "flow_treat_context_nao_implementado | acao=erro id_conversa=%s etapa_cliente=%s id_mensagem_fila=%s resultado=%s",
        id_conversa,
        id_etapa_cliente,
        mensagem_cliente_atual["id_mensagem_fila"],
        contexto_validacao["resultado"],
    )
    raise NotImplementedError(
        "Tratamento de mensagem fora de contexto ainda nao implementado"
    )
```

O que faz:

- Deixa a rota de fora de contexto separada do `worker_flow.py`.
- Nao envia mensagem ainda.
- Nao altera banco.
- Garante que, quando a regra for implementada, ela ficara fora do `flow_sender`.

---

## Passo 6 - Alterar `workers/worker_flow/suport_functions.py`

Arquivo completo:

```python
import logging
import time

from core.cache.runtime.cache_cliente import remover_cliente_cache, salvar_cliente_cache
from core.cache.cache_unidade import recarregar_cache_unidades
from core.logging_config import short_value
from core.repositories.inserts import inserir_historico_mensagem_bot
from core.repositories.querys import (
    existe_mensagem_anterior_aberta_conversa,
    unlock_conversa,
)
from core.repositories.updates import (
    atualizar_conversa_resposta_bot,
    marcar_mensagem_como_enviada,
    reagendar_mensagem_sem_erro,
)


logger = logging.getLogger("worker.support")


def criar_estado_ciclo():
    return {
        "id_mensagem": None,
        "id_cliente": None,
        "id_conversa": None,
        "id_unidade": None,
        "estado": None,
        "lock_ok": False,
        "lock_version": None,
        "cliente_telefone": None,
        "id_phone_unidade": None,
        "tipo_mensagem": None,
    }


def montar_mensagem_fila(registro):
    (
        id_mensagem,
        cliente_telefone,
        conteudo_texto,
        tipo_mensagem,
        id_phone_unidade,
        unidade_telefone,
        data_recebimento,
        id_hash,
        retry_count,
    ) = registro

    return {
        "id_mensagem": id_mensagem,
        "cliente_telefone": cliente_telefone,
        "conteudo_texto": conteudo_texto,
        "tipo_mensagem": tipo_mensagem,
        "id_phone_unidade": id_phone_unidade,
        "unidade_telefone": unidade_telefone,
        "data_recebimento": data_recebimento,
        "id_hash": id_hash,
        "retry_count": retry_count,
    }


def atualizar_estado_com_mensagem(estado_ciclo, mensagem):
    estado_ciclo["id_mensagem"] = mensagem["id_mensagem"]
    estado_ciclo["cliente_telefone"] = mensagem["cliente_telefone"]
    estado_ciclo["id_phone_unidade"] = mensagem["id_phone_unidade"]
    estado_ciclo["tipo_mensagem"] = mensagem["tipo_mensagem"]


def atualizar_estado_com_contexto(estado_ciclo, contexto_banco):
    contexto_conversa = contexto_banco["conversa"]

    estado_ciclo["id_cliente"] = contexto_banco["id_cliente"]
    estado_ciclo["id_unidade"] = contexto_banco["id_unidade"]
    estado_ciclo["id_conversa"] = contexto_conversa["id_conversa"]
    estado_ciclo["estado"] = contexto_conversa["estado"]


def atualizar_estado_lock(estado_ciclo, lock_ok, lock_version):
    estado_ciclo["lock_ok"] = lock_ok
    estado_ciclo["lock_version"] = lock_version


def aguardar_fila_vazia():
    logger.debug("fila_vazia | acao=aguardar segundos=30")
    time.sleep(30)


def confirmar_cache_cliente_se_pendente(contexto_banco):
    if not contexto_banco.get("cliente_cache_pendente"):
        return False

    salvar_cliente_cache(
        contexto_banco["cliente_telefone"],
        contexto_banco["id_cliente"],
    )
    contexto_banco["cliente_cache_pendente"] = False

    logger.debug(
        "cliente_cache_confirmado | acao=salvar cliente=%s id_cliente=%s",
        short_value(contexto_banco["cliente_telefone"]),
        contexto_banco["id_cliente"],
    )
    return True


def reparar_cache_cliente_stale_se_fk_invalida(erro, estado_ciclo):
    erro_texto = str(erro)

    if "conversa_id_cliente_fkey" not in erro_texto:
        return False

    cliente_telefone = estado_ciclo.get("cliente_telefone")

    if not cliente_telefone:
        return False

    removido = remover_cliente_cache(cliente_telefone)

    logger.warning(
        "cliente_cache_stale_reparado | motivo=fk_cliente_inexistente acao=remover_cache cliente=%s id_mensagem=%s removido=%s",
        short_value(cliente_telefone),
        estado_ciclo.get("id_mensagem"),
        removido,
    )
    return removido


def reparar_cache_unidade_stale_se_fk_invalida(erro, estado_ciclo):
    erro_texto = str(erro)

    if "conversa_id_unidade_fkey" not in erro_texto:
        return False

    total_unidades = recarregar_cache_unidades()

    logger.warning(
        "unidade_cache_stale_reparado | motivo=fk_unidade_inexistente acao=recarregar_cache_unidades phone_number_id=%s id_mensagem=%s unidades=%s",
        short_value(estado_ciclo.get("id_phone_unidade")),
        estado_ciclo.get("id_mensagem"),
        total_unidades,
    )
    return total_unidades is not None


def logar_lock_recusado(mensagem, contexto_banco):
    contexto_conversa = contexto_banco["conversa"]

    logger.info(
        "conversa_lock_recusado | motivo=conversa_em_processamento acao=continuar id_mensagem=%s cliente=%s phone_number_id=%s id_unidade=%s id_conversa=%s",
        mensagem["id_mensagem"],
        short_value(mensagem["cliente_telefone"]),
        short_value(mensagem["id_phone_unidade"]),
        contexto_banco["id_unidade"],
        contexto_conversa["id_conversa"],
    )


def reagendar_se_houver_mensagem_anterior(
    mensagem,
    contexto_banco,
    lock_version,
    cursor,
):
    contexto_conversa = contexto_banco["conversa"]
    id_conversa = contexto_conversa["id_conversa"]

    existe_anterior = existe_mensagem_anterior_aberta_conversa(
        id_conversa,
        mensagem["id_mensagem"],
        mensagem["data_recebimento"],
        cursor,
    )

    if not existe_anterior:
        return False

    reagendar_mensagem_sem_erro(
        mensagem["id_mensagem"],
        cursor,
        delay_seconds=30,
    )

    logger.info(
        "mensagem_reagendada | motivo=mensagem_anterior_aberta acao=aguardar_ordem id_mensagem=%s cliente=%s phone_number_id=%s id_conversa=%s lock_version=%s",
        mensagem["id_mensagem"],
        short_value(mensagem["cliente_telefone"]),
        short_value(mensagem["id_phone_unidade"]),
        id_conversa,
        lock_version,
    )
    return True


def atualizar_banco_com_contexto_final(contexto_historico, contexto_envio, cursor):
    id_conversa = contexto_historico["id_conversa"]
    id_etapa_resultante = contexto_envio.get("id_etapa_resultante")
    atualizar_conversa = contexto_envio.get("atualizar_conversa", True)

    if contexto_envio.get("resposta_ja_existia"):
        if atualizar_conversa:
            atualizar_conversa_resposta_bot(
                id_conversa,
                id_etapa_resultante,
                cursor,
            )

        logger.info(
            "resposta_bot_idempotente | motivo=resposta_ja_existia acao=atualizar_contexto id_conversa=%s etapa=%s id_hash_msg_bot=%s atualizar_conversa=%s",
            id_conversa,
            id_etapa_resultante,
            contexto_envio.get("id_hash_msg_bot"),
            atualizar_conversa,
        )
        return {
            "historico_bot_inserido": False,
            "resposta_ja_existia": True,
            "id_hash_msg_bot": contexto_envio.get("id_hash_msg_bot"),
            "id_etapa_resultante": id_etapa_resultante,
            "atualizar_conversa": atualizar_conversa,
        }

    if not contexto_envio.get("enviou"):
        raise ValueError(
            "Contexto de envio sem resposta enviada e sem resposta existente"
        )

    id_historico_bot, data_historico_bot, historico_inserido = (
        inserir_historico_mensagem_bot(
            contexto_historico,
            contexto_envio,
            cursor,
        )
    )

    if atualizar_conversa:
        atualizar_conversa_resposta_bot(
            id_conversa,
            id_etapa_resultante,
            cursor,
        )

    logger.info(
        "resposta_bot_persistida | acao=registrar_historico_e_contexto id_conversa=%s id_historico_bot=%s inserido=%s etapa=%s id_hash_msg_bot=%s atualizar_conversa=%s",
        id_conversa,
        id_historico_bot,
        historico_inserido,
        id_etapa_resultante,
        contexto_envio.get("id_hash_msg_bot"),
        atualizar_conversa,
    )

    return {
        "historico_bot_inserido": historico_inserido,
        "resposta_ja_existia": False,
        "id_historico_bot": id_historico_bot,
        "data_historico_bot": data_historico_bot,
        "id_hash_msg_bot": contexto_envio.get("id_hash_msg_bot"),
        "id_etapa_resultante": id_etapa_resultante,
        "atualizar_conversa": atualizar_conversa,
    }


def finalizar_mensagem_processada(
    mensagem,
    contexto_banco,
    lock_version,
    cursor,
):
    contexto_conversa = contexto_banco["conversa"]

    marcar_mensagem_como_enviada(mensagem["id_mensagem"], cursor)

    logger.info(
        "mensagem_processada | acao=marcar_sent id_mensagem=%s cliente=%s phone_number_id=%s id_unidade=%s id_conversa=%s estado=%s lock_version=%s",
        mensagem["id_mensagem"],
        short_value(mensagem["cliente_telefone"]),
        short_value(mensagem["id_phone_unidade"]),
        contexto_banco["id_unidade"],
        contexto_conversa["id_conversa"],
        contexto_conversa["estado"],
        lock_version,
    )


def liberar_lock_conversa_se_necessario(cursor, estado_ciclo):
    if not (
        estado_ciclo["lock_ok"]
        and estado_ciclo["id_conversa"]
        and estado_ciclo["lock_version"] is not None
    ):
        return None

    unlock_realizado = unlock_conversa(
        estado_ciclo["id_conversa"],
        estado_ciclo["lock_version"],
        cursor,
    )

    logger.debug(
        "conversa_unlock | acao=liberar id_conversa=%s lock_version=%s liberada=%s",
        estado_ciclo["id_conversa"],
        estado_ciclo["lock_version"],
        unlock_realizado,
    )
    return unlock_realizado
```

O que muda:

- `atualizar_banco_com_contexto_final()` passa a respeitar `atualizar_conversa`.
- Para fluxo normal, nada muda porque o valor padrao e `True`.
- Para tratamento, `atualizar_conversa=False` insere a resposta do bot no historico, mas nao altera `id_etapa_atual` nem `last_message_from`.
- Isso impede avanco de etapa em tratamento.

---

## Passo 7 - Alterar `workers/worker_flow/worker_flow.py`

Arquivo completo:

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
from workers.worker_flow.flow_sender import flow_sender
from workers.worker_flow.flow_treat_context import flow_treat_context
from workers.worker_flow.flow_treat_unsupported_type import flow_treat_unsupported_type
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
from workers.worker_flow.valida_resposta_cliente import (
    RESULTADO_MENSAGEM_FORA_DE_CONTEXTO,
    RESULTADO_TIPO_MENSAGEM_NAO_SUPORTADO,
    validar_resposta_cliente,
)

logger = logging.getLogger("worker.flow")


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

            contexto_validacao = validar_resposta_cliente(contexto_historico)
            resultado_validacao = contexto_validacao["resultado"]

            if resultado_validacao == RESULTADO_TIPO_MENSAGEM_NAO_SUPORTADO:
                contexto_envio = flow_treat_unsupported_type(
                    contexto_historico,
                    contexto_validacao,
                )

            elif resultado_validacao == RESULTADO_MENSAGEM_FORA_DE_CONTEXTO:
                contexto_envio = flow_treat_context(
                    contexto_historico,
                    contexto_validacao,
                )

            else:
                contexto_envio = flow_sender(contexto_historico)

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

                    conn_ciclo.close()

                except Exception as erro:
                    logger.warning("finalizacao_ciclo_falhou | erro=%s", erro)
```

O que muda:

- Adiciona uma decisao simples depois do historico.
- Se `resultado=resposta_valida`, segue `flow_sender()`.
- Se `resultado=tipo_mensagem_nao_suportado`, segue `flow_treat_unsupported_type()`.
- Se `resultado=mensagem_fora_de_contexto`, segue `flow_treat_context()`, que por enquanto registra log e levanta `NotImplementedError`.
- Commits, rollbacks e close continuam no proprio `worker_flow.py`.

---

## Passo 8 - Criar `tests/unit/test_valida_resposta_cliente.py`

Arquivo completo:

```python
import unittest

from workers.worker_flow.valida_resposta_cliente import (
    RESULTADO_RESPOSTA_VALIDA,
    RESULTADO_TIPO_MENSAGEM_NAO_SUPORTADO,
    validar_resposta_cliente,
)


def contexto_historico_base(tipo="text"):
    return {
        "id_conversa": 10,
        "id_etapa_cliente": 1,
        "id_etapa_resposta": 2,
        "tipo_mensagem_atual": tipo,
        "mensagem_cliente_atual": {
            "id_mensagem_fila": 20,
            "cliente_telefone": "5571999999999",
            "id_phone_unidade": "123456",
        },
    }


class ValidaRespostaClienteTests(unittest.TestCase):
    def test_text_e_valido(self):
        resultado = validar_resposta_cliente(contexto_historico_base("text"))

        self.assertEqual(resultado["resultado"], RESULTADO_RESPOSTA_VALIDA)
        self.assertIsNone(resultado["tipo_tratamento"])

    def test_interactive_e_valido(self):
        resultado = validar_resposta_cliente(contexto_historico_base("interactive"))

        self.assertEqual(resultado["resultado"], RESULTADO_RESPOSTA_VALIDA)
        self.assertIsNone(resultado["tipo_tratamento"])

    def test_image_nao_e_valido_e_nao_avanca_etapa(self):
        resultado = validar_resposta_cliente(contexto_historico_base("image"))

        self.assertEqual(resultado["resultado"], RESULTADO_TIPO_MENSAGEM_NAO_SUPORTADO)
        self.assertEqual(resultado["tipo_tratamento"], RESULTADO_TIPO_MENSAGEM_NAO_SUPORTADO)
        self.assertEqual(resultado["tipo_mensagem"], "image")
        self.assertFalse(resultado["avancar_etapa"])


if __name__ == "__main__":
    unittest.main()
```

---

## Passo 9 - Criar `tests/unit/test_flow_treat_unsupported_type.py`

Arquivo completo:

```python
import unittest
from unittest.mock import patch

from workers.worker_flow import flow_treat_unsupported_type as flow_treat_unsupported_type_module


def contexto_historico_base(resposta_bot=None, id_etapa_atual=1):
    return {
        "id_conversa": 10,
        "id_etapa_atual": id_etapa_atual,
        "id_etapa_cliente": 1,
        "mensagem_cliente_atual": {
            "id_mensagem_fila": 20,
            "id_hash_msg": "wamid.cliente",
            "cliente_telefone": "5571999999999",
            "id_phone_unidade": "123456",
        },
        "resposta_bot_para_mensagem_atual": resposta_bot,
    }


def contexto_validacao_base():
    return {
        "resultado": "tipo_mensagem_nao_suportado",
        "tipo_tratamento": "tipo_mensagem_nao_suportado",
        "tipo_mensagem": "image",
    }


class FlowTreatUnsupportedTypeTests(unittest.TestCase):
    def test_idempotente_nao_envia_meta_quando_resposta_ja_existe(self):
        def falhar_se_chamar(*_args, **_kwargs):
            raise AssertionError("sender_tratamento nao deveria ser chamado")

        with patch.object(
            flow_treat_unsupported_type_module,
            "sender_tratamento_tipo_nao_suportado",
            falhar_se_chamar,
        ):
            resultado = flow_treat_unsupported_type_module.flow_treat_unsupported_type(
                contexto_historico_base(
                    resposta_bot={
                        "id_mensagem": 99,
                        "id_hash_msg": "wamid.bot.existente",
                        "id_etapa": 1,
                    }
                ),
                contexto_validacao_base(),
            )

        self.assertFalse(resultado["enviou"])
        self.assertTrue(resultado["resposta_ja_existia"])
        self.assertTrue(resultado["tratamento"])
        self.assertFalse(resultado["atualizar_conversa"])

    def test_tipo_nao_suportado_chama_sender_de_tratamento(self):
        chamadas = []

        def fake_sender(
            cliente_telefone,
            phone_id_unidade,
            id_etapa,
            tipo_mensagem,
            mensagem_bot,
        ):
            chamadas.append((
                cliente_telefone,
                phone_id_unidade,
                id_etapa,
                tipo_mensagem,
                mensagem_bot,
            ))
            return {
                "enviou": True,
                "resposta_ja_existia": False,
                "mensagem_bot": mensagem_bot,
                "id_hash_msg_bot": "wamid.bot.tratamento",
                "id_etapa_resultante": id_etapa,
                "tipo_mensagem": "interactive_button",
                "tratamento": True,
                "tipo_tratamento": "tipo_mensagem_nao_suportado",
                "atualizar_conversa": False,
            }

        with patch.object(
            flow_treat_unsupported_type_module,
            "sender_tratamento_tipo_nao_suportado",
            fake_sender,
        ):
            resultado = flow_treat_unsupported_type_module.flow_treat_unsupported_type(
                contexto_historico_base(),
                contexto_validacao_base(),
            )

        self.assertEqual(chamadas[0][:4], ("5571999999999", "123456", 1, "image"))
        self.assertIn("continuarmos", chamadas[0][4])
        self.assertTrue(resultado["enviou"])
        self.assertTrue(resultado["tratamento"])
        self.assertFalse(resultado["atualizar_conversa"])

    def test_tipo_nao_suportado_em_conversa_nova_usa_mensagem_de_inicio(self):
        chamadas = []

        def fake_sender(
            cliente_telefone,
            phone_id_unidade,
            id_etapa,
            tipo_mensagem,
            mensagem_bot,
        ):
            chamadas.append(mensagem_bot)
            return {
                "enviou": True,
                "resposta_ja_existia": False,
                "mensagem_bot": mensagem_bot,
                "id_hash_msg_bot": "wamid.bot.tratamento",
                "id_etapa_resultante": id_etapa,
                "tipo_mensagem": "interactive_button",
                "tratamento": True,
                "tipo_tratamento": "tipo_mensagem_nao_suportado",
                "atualizar_conversa": False,
            }

        with patch.object(
            flow_treat_unsupported_type_module,
            "sender_tratamento_tipo_nao_suportado",
            fake_sender,
        ):
            resultado = flow_treat_unsupported_type_module.flow_treat_unsupported_type(
                contexto_historico_base(id_etapa_atual=None),
                contexto_validacao_base(),
            )

        self.assertIn("iniciou o atendimento", chamadas[0])
        self.assertIn("comecarmos", chamadas[0])
        self.assertEqual(resultado["id_etapa_resultante"], 1)


if __name__ == "__main__":
    unittest.main()
```

---

## Passo 10 - Criar `tests/unit/test_sender_tratamento.py`

Arquivo completo:

```python
import unittest
from unittest.mock import patch

from core.integrations.whatsapp import sender_tratamento as sender_tratamento_module
from core.integrations.whatsapp.exceptions import ErroEnvioMeta


class SenderTratamentoTests(unittest.TestCase):
    def test_sender_tipo_nao_suportado_retorna_contexto_sem_avancar_conversa(self):
        chamadas = []

        def fake_enviar_mensagem_texto_com_botao(
            to,
            text,
            titulo_botao,
            phone_id_unidade,
            callback_data=None,
        ):
            chamadas.append((to, text, titulo_botao, phone_id_unidade, callback_data))
            return "wamid.bot.tratamento"

        with patch.object(
            sender_tratamento_module,
            "enviar_mensagem_texto_com_botao",
            fake_enviar_mensagem_texto_com_botao,
        ):
            resultado = sender_tratamento_module.sender_tratamento_tipo_nao_suportado(
                cliente_telefone="5571999999999",
                phone_id_unidade="123456",
                id_etapa=1,
                tipo_mensagem="image",
                mensagem_bot="Recebi uma midia. Envie texto para continuarmos.",
            )

        self.assertEqual(len(chamadas), 1)
        self.assertEqual(chamadas[0][0], "5571999999999")
        self.assertEqual(chamadas[0][2], "Retornar ao atendimento")
        self.assertEqual(chamadas[0][3], "123456")
        self.assertEqual(chamadas[0][4], "retornar_atendimento")
        self.assertEqual(chamadas[0][1], "Recebi uma midia. Envie texto para continuarmos.")
        self.assertTrue(resultado["enviou"])
        self.assertTrue(resultado["tratamento"])
        self.assertFalse(resultado["atualizar_conversa"])
        self.assertEqual(resultado["id_hash_msg_bot"], "wamid.bot.tratamento")
        self.assertEqual(resultado["id_etapa_resultante"], 1)

    def test_sender_tipo_nao_suportado_falha_meta_levanta_exception_controlada(self):
        def fake_falha(*_args, **_kwargs):
            raise RuntimeError("meta indisponivel")

        with patch.object(
            sender_tratamento_module,
            "enviar_mensagem_texto_com_botao",
            fake_falha,
        ):
            with self.assertRaises(ErroEnvioMeta) as ctx:
                sender_tratamento_module.sender_tratamento_tipo_nao_suportado(
                    cliente_telefone="5571999999999",
                    phone_id_unidade="123456",
                    id_etapa=1,
                    tipo_mensagem="image",
                    mensagem_bot="Recebi uma midia. Envie texto para continuarmos.",
                )

        self.assertEqual(ctx.exception.id_etapa, 1)
        self.assertEqual(ctx.exception.cliente_telefone, "5571999999999")
        self.assertEqual(ctx.exception.phone_id_unidade, "123456")


if __name__ == "__main__":
    unittest.main()
```

---

## Passo 11 - Alterar `tests/unit/test_worker_support_finalizacao.py`

Arquivo completo:

```python
import unittest
from unittest.mock import patch

from workers.worker_flow import suport_functions as support


def contexto_historico_base():
    return {
        "id_conversa": 10,
        "mensagem_cliente_atual": {
            "id_mensagem_fila": 20,
            "id_hash_msg": "wamid.cliente",
            "cliente_telefone": "5571999999999",
            "id_phone_unidade": "123456",
            "unidade_telefone": "5571000000000",
        },
    }


class WorkerSupportFinalizacaoTests(unittest.TestCase):
    def test_atualizar_banco_com_contexto_final_persiste_bot_e_conversa(self):
        chamadas = []

        def fake_inserir_historico(contexto_historico, contexto_envio, cursor):
            chamadas.append(("insert_bot", contexto_historico, contexto_envio, cursor))
            return 300, "2026-01-01T00:00:00", True

        def fake_atualizar_conversa(id_conversa, id_etapa_resultante, cursor):
            chamadas.append(("update_conversa", id_conversa, id_etapa_resultante, cursor))
            return 1

        cursor = object()
        contexto_envio = {
            "enviou": True,
            "resposta_ja_existia": False,
            "mensagem_bot": "Ola!",
            "id_hash_msg_bot": "wamid.bot",
            "id_etapa_resultante": 1,
            "tipo_mensagem": "interactive_button",
        }

        with patch.object(
            support,
            "inserir_historico_mensagem_bot",
            fake_inserir_historico,
        ), patch.object(
            support,
            "atualizar_conversa_resposta_bot",
            fake_atualizar_conversa,
        ):
            resultado = support.atualizar_banco_com_contexto_final(
                contexto_historico_base(),
                contexto_envio,
                cursor,
            )

        self.assertEqual([chamada[0] for chamada in chamadas], ["insert_bot", "update_conversa"])
        self.assertTrue(resultado["historico_bot_inserido"])
        self.assertEqual(resultado["id_hash_msg_bot"], "wamid.bot")
        self.assertTrue(resultado["atualizar_conversa"])

    def test_tratamento_persiste_bot_sem_atualizar_conversa(self):
        chamadas = []

        def fake_inserir_historico(contexto_historico, contexto_envio, cursor):
            chamadas.append(("insert_bot", contexto_historico, contexto_envio, cursor))
            return 301, "2026-01-01T00:00:00", True

        def fake_atualizar_conversa(*_args, **_kwargs):
            raise AssertionError("tratamento nao deve atualizar conversa")

        contexto_envio = {
            "enviou": True,
            "resposta_ja_existia": False,
            "mensagem_bot": "Tratamento",
            "id_hash_msg_bot": "wamid.bot.tratamento",
            "id_etapa_resultante": 1,
            "tipo_mensagem": "interactive_button",
            "tratamento": True,
            "atualizar_conversa": False,
        }

        with patch.object(
            support,
            "inserir_historico_mensagem_bot",
            fake_inserir_historico,
        ), patch.object(
            support,
            "atualizar_conversa_resposta_bot",
            fake_atualizar_conversa,
        ):
            resultado = support.atualizar_banco_com_contexto_final(
                contexto_historico_base(),
                contexto_envio,
                object(),
            )

        self.assertEqual([chamada[0] for chamada in chamadas], ["insert_bot"])
        self.assertTrue(resultado["historico_bot_inserido"])
        self.assertFalse(resultado["atualizar_conversa"])

    def test_resposta_ja_existia_nao_insere_historico_do_bot(self):
        chamadas = []

        def fake_inserir_historico(*_args, **_kwargs):
            raise AssertionError("nao deve inserir historico quando resposta ja existe")

        def fake_atualizar_conversa(id_conversa, id_etapa_resultante, cursor):
            chamadas.append((id_conversa, id_etapa_resultante, cursor))
            return 1

        cursor = object()

        with patch.object(
            support,
            "inserir_historico_mensagem_bot",
            fake_inserir_historico,
        ), patch.object(
            support,
            "atualizar_conversa_resposta_bot",
            fake_atualizar_conversa,
        ):
            resultado = support.atualizar_banco_com_contexto_final(
                contexto_historico_base(),
                {
                    "enviou": False,
                    "resposta_ja_existia": True,
                    "id_hash_msg_bot": "wamid.bot.existente",
                    "id_etapa_resultante": 1,
                },
                cursor,
            )

        self.assertEqual(chamadas, [(10, 1, cursor)])
        self.assertTrue(resultado["resposta_ja_existia"])
        self.assertFalse(resultado["historico_bot_inserido"])
        self.assertTrue(resultado["atualizar_conversa"])

    def test_resposta_ja_existia_de_tratamento_nao_atualiza_conversa(self):
        def fake_inserir_historico(*_args, **_kwargs):
            raise AssertionError("nao deve inserir historico quando resposta ja existe")

        def fake_atualizar_conversa(*_args, **_kwargs):
            raise AssertionError("tratamento idempotente nao deve atualizar conversa")

        with patch.object(
            support,
            "inserir_historico_mensagem_bot",
            fake_inserir_historico,
        ), patch.object(
            support,
            "atualizar_conversa_resposta_bot",
            fake_atualizar_conversa,
        ):
            resultado = support.atualizar_banco_com_contexto_final(
                contexto_historico_base(),
                {
                    "enviou": False,
                    "resposta_ja_existia": True,
                    "id_hash_msg_bot": "wamid.bot.existente",
                    "id_etapa_resultante": 1,
                    "atualizar_conversa": False,
                },
                object(),
            )

        self.assertTrue(resultado["resposta_ja_existia"])
        self.assertFalse(resultado["historico_bot_inserido"])
        self.assertFalse(resultado["atualizar_conversa"])

    def test_contexto_sem_envio_e_sem_resposta_existente_falha(self):
        with self.assertRaises(ValueError):
            support.atualizar_banco_com_contexto_final(
                contexto_historico_base(),
                {
                    "enviou": False,
                    "resposta_ja_existia": False,
                    "id_etapa_resultante": 1,
                },
                object(),
            )

    def test_reagendar_se_houver_mensagem_anterior_reagenda(self):
        chamadas = []

        def fake_reagendar(id_mensagem, cursor, delay_seconds=30):
            chamadas.append((id_mensagem, delay_seconds, cursor))
            return 1

        mensagem = {
            "id_mensagem": 44,
            "cliente_telefone": "5571999999999",
            "id_phone_unidade": "123456",
            "data_recebimento": "2026-01-01T00:00:00",
        }
        contexto_banco = {"conversa": {"id_conversa": 10}}
        cursor = object()

        with patch.object(
            support,
            "existe_mensagem_anterior_aberta_conversa",
            return_value=True,
        ), patch.object(
            support,
            "reagendar_mensagem_sem_erro",
            fake_reagendar,
        ):
            resultado = support.reagendar_se_houver_mensagem_anterior(
                mensagem,
                contexto_banco,
                lock_version=7,
                cursor=cursor,
            )

        self.assertTrue(resultado)
        self.assertEqual(chamadas, [(44, 30, cursor)])

    def test_reparar_cache_cliente_stale_so_age_com_fk_cliente(self):
        estado = {"cliente_telefone": "5571999999999", "id_mensagem": 1}

        with patch.object(support, "remover_cliente_cache", return_value=True) as remover:
            self.assertTrue(
                support.reparar_cache_cliente_stale_se_fk_invalida(
                    RuntimeError("violates foreign key constraint conversa_id_cliente_fkey"),
                    estado,
                )
            )
            remover.assert_called_once_with("5571999999999")

        with patch.object(support, "remover_cliente_cache", return_value=True) as remover:
            self.assertFalse(
                support.reparar_cache_cliente_stale_se_fk_invalida(
                    RuntimeError("erro qualquer"),
                    estado,
                )
            )
            remover.assert_not_called()


if __name__ == "__main__":
    unittest.main()
```

---

## Passo 12 - Alterar `tests/unit/test_sender_etapa1.py`

Arquivo completo:

```python
import unittest
from datetime import datetime
from unittest.mock import patch

from core.integrations.whatsapp import sender as sender_module
from core.integrations.whatsapp.exceptions import ErroEnvioMeta


class SenderEtapa1Tests(unittest.TestCase):
    def test_retorna_contexto_quando_meta_envia_botao_com_saudacao_por_horario(self):
        chamadas = []

        def fake_enviar_mensagem_texto_com_botao(
            to,
            text,
            titulo_botao,
            phone_id_unidade,
        ):
            chamadas.append((to, text, titulo_botao, phone_id_unidade))
            return "wamid.bot.1"

        with patch.object(
            sender_module,
            "enviar_mensagem_texto_com_botao",
            fake_enviar_mensagem_texto_com_botao,
        ), patch.object(
            sender_module,
            "obter_saudacao_por_horario",
            return_value="Boa tarde",
        ):
            resultado = sender_module.sender_etapa1("5571999999999", "123456")

        self.assertEqual(
            chamadas,
            [("5571999999999", "Ola! Boa tarde.", "Aperte em mim", "123456")],
        )
        self.assertTrue(resultado["enviou"])
        self.assertFalse(resultado["resposta_ja_existia"])
        self.assertEqual(resultado["mensagem_bot"], "Ola! Boa tarde.")
        self.assertEqual(resultado["id_hash_msg_bot"], "wamid.bot.1")
        self.assertEqual(resultado["id_etapa_resultante"], 1)
        self.assertEqual(resultado["tipo_mensagem"], "interactive_button")

    def test_saudacao_por_horario(self):
        self.assertEqual(
            sender_module.obter_saudacao_por_horario(datetime(2026, 1, 1, 8)),
            "Bom dia",
        )
        self.assertEqual(
            sender_module.obter_saudacao_por_horario(datetime(2026, 1, 1, 14)),
            "Boa tarde",
        )
        self.assertEqual(
            sender_module.obter_saudacao_por_horario(datetime(2026, 1, 1, 22)),
            "Boa noite",
        )

    def test_meta_falhou_levanta_exception_controlada(self):
        def fake_falha(*_args, **_kwargs):
            raise RuntimeError("meta indisponivel")

        with patch.object(
            sender_module,
            "enviar_mensagem_texto_com_botao",
            fake_falha,
        ):
            with self.assertRaises(ErroEnvioMeta) as ctx:
                sender_module.sender_etapa1("5571999999999", "123456")

        self.assertEqual(ctx.exception.id_etapa, 1)
        self.assertEqual(ctx.exception.cliente_telefone, "5571999999999")
        self.assertEqual(ctx.exception.phone_id_unidade, "123456")


if __name__ == "__main__":
    unittest.main()
```

O que faz:

- Garante que a etapa 1 usa a saudacao baseada no horario.
- Testa diretamente as faixas de horario.
- Mantem o teste de erro controlado da Meta.

---

## Validacao

Rodar:

```powershell
C:\Chatbot\venv\.venv\Scripts\python.exe -m unittest discover -s tests -v
C:\Chatbot\venv\.venv\Scripts\python.exe -m compileall -q core callback workers main.py tests
C:\Chatbot\venv\.venv\Scripts\python.exe callback\manage.py check
```

Resultado esperado:

- Etapa 1 oficial envia saudacao por horario atual (`Bom dia`, `Boa tarde` ou `Boa noite`) sem tentar interpretar o texto do cliente.
- Mensagem `text` segue `flow_sender`.
- Mensagem `interactive` segue `flow_sender`.
- Mensagem `image`, `video`, `audio`, `document`, `sticker` etc. entra no historico e recebe tratamento.
- Tratamento envia mensagem com botao `Retornar ao atendimento`.
- Tratamento nao altera `id_etapa_atual`.
- Tratamento nao altera `last_message_from`.
- Mensagem da fila ainda e marcada como `sent` apos tratamento enviado e persistido.
- Se a Meta falhar no tratamento, cai em `ErroEnvioMeta`, nao marca `sent` e permite retry.
- Se a Meta falhar no tratamento, o sender de tratamento registra log com `tipo_tratamento`.
- Se o banco falhar depois da Meta confirmar tratamento, continua caindo em `BancoFalhouAposEnvioMeta`, deixando o risco explicito como ja acontece no fluxo normal.
- Logs de sucesso/erro critico apos envio pela Meta exibem `tratamento` e `tipo_tratamento`, para diferenciar fluxo oficial de tratamento de midia/contexto.
