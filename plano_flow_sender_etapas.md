# Plano de implementaÃ§Ã£o - primeira etapa simplificada

Status: revisado, ainda nÃ£o aplicado.

## Objetivo

Manter `flow_sender.py` como o ponto do worker onde o envio de mensagem Ã©
decidido, mas simplificar a semÃ¢ntica das etapas.

Neste desenho, `id_etapa_atual is None` nÃ£o vira uma etapa separada. Ele Ã©
apenas o primeiro contato antes da etapa 1 ser persistida. Por isso, tanto
`id_etapa_atual is None` quanto `id_etapa_atual == 1` sÃ£o resolvidos por:

```text
workers/worker_flow/response_flow/etapas/primeira_etapa.py
```

O comentÃ¡rio abaixo deve ficar em `primeira_etapa.py`, no topo da funÃ§Ã£o
`resolve_primeira_etapa()`:

```text
id_etapa_atual is None nÃ£o Ã© uma etapa separada.
Ã‰ apenas o primeiro contato antes da etapa 1 ser persistida.
```

## Responsabilidades

```text
flow_worker.py
  controla banco, lock, commit, rollback, retry, close e persistÃªncia final

flow_sender.py
  protege idempotÃªncia, registra retry e chama a etapa responsÃ¡vel

primeira_etapa.py
  decide se a mensagem Ã© abertura normal, mÃ­dia, pergunta financeira,
  nome invÃ¡lido ou resposta vÃ¡lida

detector_etapas/
  concentra detectores reutilizÃ¡veis da etapa

pywa_senders/etapa1.py
  monta mensagem com saudaÃ§Ã£o, envia pela PyWa e retorna contexto_envio

messages/primeira_etapa_messages.py
  guarda textos e funÃ§Ãµes de montagem das mensagens da etapa 1
```

## Fluxo Desejado

```text
id_etapa_atual = None + mÃ­dia
  -> primeira_etapa.py
  -> enviar_primeira_etapa_midia_inicio()
  -> usa MENSAGEM_MIDIA_INICIO
  -> id_etapa_resultante = 1

id_etapa_atual = None + pergunta financeira
  -> primeira_etapa.py
  -> enviar_primeira_etapa_financeiro_inicio()
  -> usa MENSAGEM_FINANCEIRO_INICIO
  -> id_etapa_resultante = 1

id_etapa_atual = None + texto normal
  -> primeira_etapa.py
  -> enviar_primeira_etapa()
  -> usa MENSAGEM_ETAPA_1
  -> id_etapa_resultante = 1

id_etapa_atual = 1 + mÃ­dia
  -> primeira_etapa.py
  -> enviar_primeira_etapa_midia()
  -> usa MENSAGEM_MIDIA_ETAPA_1
  -> id_etapa_resultante = 1

id_etapa_atual = 1 + pergunta financeira
  -> primeira_etapa.py
  -> enviar_primeira_etapa_financeiro()
  -> usa MENSAGEM_FINANCEIRO_ETAPA_1
  -> id_etapa_resultante = 1

id_etapa_atual = 1 + nome invÃ¡lido
  -> primeira_etapa.py
  -> enviar_primeira_etapa_contexto_nome_invalido()
  -> usa MENSAGEM_CONTEXTO_NOME_INVALIDO_ETAPA_1
  -> id_etapa_resultante = 1

id_etapa_atual = 1 + nome vÃ¡lido
  -> primeira_etapa.py
  -> futura etapa 2
  -> id_etapa_resultante = id_etapa_resposta
```

## Arquivos Removidos

Esses arquivos continuam fora do novo desenho:

```text
workers/worker_flow/response_flow/flow_treat_context.py
workers/worker_flow/response_flow/flow_treat_financial.py
workers/worker_flow/response_flow/flow_treat_unsupported_type.py
workers/worker_flow/response_flow/rotear_resposta_cliente.py
workers/worker_flow/valida_resposta_cliente.py
```

## Passo 1 - alterar `flow_sender.py`

Arquivo: `workers/worker_flow/response_flow/flow_sender.py`

```python
import logging

from workers.worker_flow.response_flow.etapas.primeira_etapa import (
    resolve_primeira_etapa,
)


logger = logging.getLogger("worker.sender")


def flow_sender(contexto_historico):
    id_conversa = contexto_historico["id_conversa"]
    id_etapa_proxima = contexto_historico["id_etapa_resposta"]
    id_etapa_atual = contexto_historico.get("id_etapa_atual")
    retry_count = contexto_historico["retry_count"]

    mensagem_cliente_atual = contexto_historico["mensagem_cliente_atual"]
    cliente_atual_id_mensagem_fila = mensagem_cliente_atual["id_mensagem_fila"]
    cliente_atual_id_hash_msg = mensagem_cliente_atual["id_hash_msg"]

    resposta_bot_atual = (
        contexto_historico["resposta_bot_para_mensagem_atual"] or {}
    )

    if resposta_bot_atual:
        logger.info(
            "flow_sender_idempotencia_ok | motivo=resposta_bot_ja_registrada acao=nao_enviar id_conversa=%s id_mensagem_fila=%s id_hash_cliente=%s id_resposta_bot=%s etapa_resposta=%s retry=%s",
            id_conversa,
            cliente_atual_id_mensagem_fila,
            cliente_atual_id_hash_msg,
            resposta_bot_atual.get("id_mensagem"),
            resposta_bot_atual.get("id_etapa"),
            retry_count,
        )
        return {
            "enviou": False,
            "resposta_ja_existia": True,
            "id_hash_msg_bot": resposta_bot_atual.get("id_hash_msg"),
            "id_etapa_resultante": resposta_bot_atual.get("id_etapa"),
        }

    if retry_count > 1:
        logger.info(
            "flow_sender_reprocessamento | motivo=retry_maior_que_um acao=continuar_sem_resposta_previa id_conversa=%s id_mensagem_fila=%s id_hash_cliente=%s retry=%s",
            id_conversa,
            cliente_atual_id_mensagem_fila,
            cliente_atual_id_hash_msg,
            retry_count,
        )

    if id_etapa_atual is None or id_etapa_atual == 1:
        contexto_resposta = resolve_primeira_etapa(contexto_historico)
        return contexto_resposta

    logger.warning(
        "flow_sender_etapa_pendente | acao=nao_enviar id_conversa=%s etapa=%s",
        id_conversa,
        id_etapa_proxima,
    )
    raise NotImplementedError(
        f"Sender da etapa {id_etapa_proxima} ainda nao implementado"
    )
```

## Passo 2 - criar `__init__.py` das novas pastas

Arquivo: `workers/worker_flow/response_flow/etapas/__init__.py`

```python
```

Arquivo: `workers/worker_flow/response_flow/etapas/detector_etapas/__init__.py`

```python
```

Arquivo: `core/integrations/whatsapp/pywa_functions/pywa_senders/__init__.py`

```python
```

## Passo 3 - atualizar mensagens da primeira etapa

Arquivo: `core/integrations/whatsapp/messages/primeira_etapa_messages.py`

```python
MENSAGEM_MIDIA_INICIO = (
    "{saudacao}! Seja bem vindo (a), sou a Su, atendente virtual do Supera! â˜ºï¸\n"
    "Olha nÃ£o reconhecemos ainda mensagem com mÃ­dia, apenas texto.\n"
    "Me diz, qual o seu nome?"
)

MENSAGEM_FINANCEIRO_INICIO = (
    "{saudacao}! Seja bem vindo (a), sou a Su, atendente virtual do Supera! â˜ºï¸\n"
    "Olha demais informaÃ§Ãµes como valores sÃ£o apresentados no atendimento "
    "presencial apÃ³s sua aula gratuita.\n"
    "Me diz, qual o seu nome?"
)

MENSAGEM_ETAPA_1 = (
    "{saudacao}! Seja bem vindo (a), sou a Su, atendente virtual do Supera! â˜ºï¸\n"
    "Como vocÃª se chama?"
)

MENSAGEM_MIDIA_ETAPA_1 = (
    "Olha nÃ£o reconhecemos ainda mensagem com mÃ­dia, apenas texto.\n"
    "Me diz, qual o seu nome?"
)

MENSAGEM_FINANCEIRO_ETAPA_1 = (
    "Olha demais informaÃ§Ãµes como valores sÃ£o apresentados no atendimento "
    "presencial apÃ³s sua aula gratuita.\n"
    "Me diz, qual o seu nome?"
)

MENSAGEM_CONTEXTO_NOME_INVALIDO_ETAPA_1 = (
    "Olha sua mensagem parece estar fora do contexto e tambÃ©m nÃ£o aceitamos "
    "nomes e apelidos pejorativos.\n"
    "Me diz, qual o seu nome?"
)


def montar_mensagem_midia_inicio(saudacao):
    return MENSAGEM_MIDIA_INICIO.format(saudacao=saudacao)


def montar_mensagem_financeiro_inicio(saudacao):
    return MENSAGEM_FINANCEIRO_INICIO.format(saudacao=saudacao)


def montar_mensagem_etapa_1(saudacao):
    return MENSAGEM_ETAPA_1.format(saudacao=saudacao)


def montar_mensagem_midia_etapa_1():
    return MENSAGEM_MIDIA_ETAPA_1


def montar_mensagem_financeiro_etapa_1():
    return MENSAGEM_FINANCEIRO_ETAPA_1


def montar_mensagem_contexto_nome_invalido_etapa_1():
    return MENSAGEM_CONTEXTO_NOME_INVALIDO_ETAPA_1
```

## Passo 4 - implementar detector de mÃ­dia

Arquivo: `workers/worker_flow/response_flow/etapas/detector_etapas/detector_midia.py`

```python
TIPOS_MENSAGEM_SUPORTADOS = {"text", "interactive"}
TIPO_TRATAMENTO_TIPO_NAO_SUPORTADO = "tipo_mensagem_nao_suportado"


def detecta_midia(tipo_mensagem):
    return tipo_mensagem not in TIPOS_MENSAGEM_SUPORTADOS
```

## Passo 5 - implementar detector financeiro

Arquivo: `workers/worker_flow/response_flow/etapas/detector_etapas/detector_financeiro.py`

```python
import re
import unicodedata


TIPO_TRATAMENTO_FINANCEIRO = "pergunta_financeira"

PADRAO_PERGUNTA_FINANCEIRA = re.compile(
    r"("
    r"r\s*\$|"
    r"\$|"
    r"\b("
    r"valor(?:es)?|"
    r"preco(?:s)?|"
    r"custo(?:s)?|"
    r"mensalidade(?:s)?|"
    r"mensal|"
    r"pagamento(?:s)?|"
    r"pagar|"
    r"pago|"
    r"cobra(?:r|m|do|da)?|"
    r"cobranca(?:s)?|"
    r"taxa(?:s)?|"
    r"investimento(?:s)?|"
    r"investir|"
    r"capital|"
    r"orcamento(?:s)?|"
    r"plano(?:s)?|"
    r"pacote(?:s)?|"
    r"matricula(?:s)?|"
    r"inscricao(?:s)?|"
    r"parcela(?:s)?|"
    r"parcelamento|"
    r"parcelado|"
    r"pix|"
    r"boleto(?:s)?|"
    r"cartao|"
    r"credito|"
    r"debito|"
    r"dinheiro|"
    r"real|"
    r"reais|"
    r"barato|"
    r"caro|"
    r"desconto(?:s)?|"
    r"promocao|"
    r"gratis|"
    r"gratuito"
    r")\b|"
    r"\bquanto\s+(?:custa|e|fica|sai|vou\s+pagar|tenho\s+que\s+pagar)\b|"
    r"\bqual\s+(?:o\s+)?(?:valor|preco|custo|investimento)\b|"
    r"\btem\s+(?:valor|preco|custo|mensalidade|taxa)\b"
    r")"
)


def detecta_pergunta_financeira(texto):
    texto_normalizado = normalizar_texto(texto or "")
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

## Passo 6 - implementar detector de nome invÃ¡lido

Arquivo: `workers/worker_flow/response_flow/etapas/detector_etapas/detector_nome.py`

```python
import re

from workers.worker_flow.response_flow.etapas.detector_etapas.detector_financeiro import (
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


def detecta_nome_invalido(texto):
    texto_normalizado = normalizar_texto(texto or "").strip()
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

## Passo 7 - implementar envios PyWa da etapa 1

Arquivo: `core/integrations/whatsapp/pywa_functions/pywa_senders/etapa1.py`

```python
import logging

from core.integrations.whatsapp.exceptions import ErroEnvioMeta
from core.integrations.whatsapp.messages.primeira_etapa_messages import (
    montar_mensagem_contexto_nome_invalido_etapa_1,
    montar_mensagem_etapa_1,
    montar_mensagem_financeiro_etapa_1,
    montar_mensagem_financeiro_inicio,
    montar_mensagem_midia_etapa_1,
    montar_mensagem_midia_inicio,
)
from core.integrations.whatsapp.pywa_functions.cliente import conta_wa
from core.integrations.whatsapp.pywa_functions.saudacao import (
    obter_saudacao_por_horario,
)
from core.logging_config import short_value


logger = logging.getLogger("whatsapp.etapa1")

ID_ETAPA_1 = 1

TIPO_TRATAMENTO_MIDIA = "tipo_mensagem_nao_suportado"
TIPO_TRATAMENTO_FINANCEIRO = "pergunta_financeira"
TIPO_TRATAMENTO_NOME_INVALIDO = "nome_invalido"


def enviar_primeira_etapa(cliente_telefone, phone_id_unidade):
    saudacao = obter_saudacao_por_horario()
    mensagem_bot = montar_mensagem_etapa_1(saudacao)

    return _enviar_texto_etapa_1(
        cliente_telefone,
        phone_id_unidade,
        mensagem_bot,
        evento="enviar_primeira_etapa",
    )


def enviar_primeira_etapa_midia_inicio(cliente_telefone, phone_id_unidade):
    saudacao = obter_saudacao_por_horario()
    mensagem_bot = montar_mensagem_midia_inicio(saudacao)

    return _enviar_texto_etapa_1(
        cliente_telefone,
        phone_id_unidade,
        mensagem_bot,
        evento="enviar_primeira_etapa_midia_inicio",
        tipo_tratamento=TIPO_TRATAMENTO_MIDIA,
    )


def enviar_primeira_etapa_financeiro_inicio(cliente_telefone, phone_id_unidade):
    saudacao = obter_saudacao_por_horario()
    mensagem_bot = montar_mensagem_financeiro_inicio(saudacao)

    return _enviar_texto_etapa_1(
        cliente_telefone,
        phone_id_unidade,
        mensagem_bot,
        evento="enviar_primeira_etapa_financeiro_inicio",
        tipo_tratamento=TIPO_TRATAMENTO_FINANCEIRO,
    )


def enviar_primeira_etapa_midia(cliente_telefone, phone_id_unidade):
    mensagem_bot = montar_mensagem_midia_etapa_1()

    return _enviar_texto_etapa_1(
        cliente_telefone,
        phone_id_unidade,
        mensagem_bot,
        evento="enviar_primeira_etapa_midia",
        tipo_tratamento=TIPO_TRATAMENTO_MIDIA,
    )


def enviar_primeira_etapa_financeiro(cliente_telefone, phone_id_unidade):
    mensagem_bot = montar_mensagem_financeiro_etapa_1()

    return _enviar_texto_etapa_1(
        cliente_telefone,
        phone_id_unidade,
        mensagem_bot,
        evento="enviar_primeira_etapa_financeiro",
        tipo_tratamento=TIPO_TRATAMENTO_FINANCEIRO,
    )


def enviar_primeira_etapa_contexto_nome_invalido(
    cliente_telefone,
    phone_id_unidade,
):
    mensagem_bot = montar_mensagem_contexto_nome_invalido_etapa_1()

    return _enviar_texto_etapa_1(
        cliente_telefone,
        phone_id_unidade,
        mensagem_bot,
        evento="enviar_primeira_etapa_contexto_nome_invalido",
        tipo_tratamento=TIPO_TRATAMENTO_NOME_INVALIDO,
    )


def _enviar_texto_etapa_1(
    cliente_telefone,
    phone_id_unidade,
    mensagem_bot,
    *,
    evento,
    tipo_tratamento=None,
):
    try:
        cliente_wa = conta_wa(phone_id_unidade)
        sent_message = cliente_wa.send_message(
            to=cliente_telefone,
            text=mensagem_bot,
        )
        id_hash_msg_bot = _extrair_id_hash_msg_bot(sent_message)

        logger.info(
            "%s_ok | acao=enviar_meta cliente=%s phone_number_id=%s id_hash_msg_bot=%s tratamento=%s",
            evento,
            short_value(cliente_telefone),
            short_value(phone_id_unidade),
            id_hash_msg_bot,
            tipo_tratamento,
        )

        contexto_envio = {
            "enviou": True,
            "resposta_ja_existia": False,
            "mensagem_bot": mensagem_bot,
            "id_hash_msg_bot": id_hash_msg_bot,
            "id_etapa_resultante": ID_ETAPA_1,
            "tipo_mensagem": "text",
            "canal": "meta_whatsapp",
            "atualizar_conversa": True,
            "atualizar_last_from_bot": True,
        }

        if tipo_tratamento:
            contexto_envio["tratamento"] = True
            contexto_envio["tipo_tratamento"] = tipo_tratamento

        return contexto_envio

    except Exception as erro:
        logger.exception(
            "%s_erro | motivo=meta_falhou acao=levantar_erro cliente=%s phone_number_id=%s erro=%s",
            evento,
            short_value(cliente_telefone),
            short_value(phone_id_unidade),
            erro,
        )
        raise ErroEnvioMeta(
            "Meta falhou ao enviar mensagem da etapa 1",
            id_etapa=ID_ETAPA_1,
            phone_id_unidade=phone_id_unidade,
            cliente_telefone=cliente_telefone,
        ) from erro


def _extrair_id_hash_msg_bot(sent_message):
    id_hash = getattr(sent_message, "id", None)
    if id_hash:
        return id_hash

    if isinstance(sent_message, dict):
        mensagens = sent_message.get("messages") or []
        if mensagens:
            id_hash = mensagens[0].get("id")
            if id_hash:
                return id_hash

    raise ValueError("Meta confirmou envio, mas nao retornou id da mensagem")
```

## Passo 8 - implementar `primeira_etapa.py`

Arquivo: `workers/worker_flow/response_flow/etapas/primeira_etapa.py`

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
from core.logging_config import short_value
from workers.worker_flow.response_flow.etapas.detector_etapas.detector_financeiro import (
    TIPO_TRATAMENTO_FINANCEIRO,
    detecta_pergunta_financeira,
)
from workers.worker_flow.response_flow.etapas.detector_etapas.detector_midia import (
    TIPO_TRATAMENTO_TIPO_NAO_SUPORTADO,
    detecta_midia,
)
from workers.worker_flow.response_flow.etapas.detector_etapas.detector_nome import (
    TIPO_TRATAMENTO_NOME_INVALIDO,
    detecta_nome_invalido,
)


logger = logging.getLogger("worker.primeira_etapa")


def resolve_primeira_etapa(contexto_historico):
    """
    id_etapa_atual is None nÃ£o Ã© uma etapa separada.
    Ã‰ apenas o primeiro contato antes da etapa 1 ser persistida.

    NotImplementedError nÃ£o representa nome invÃ¡lido, mÃ­dia ou pergunta
    financeira. Esses casos tÃªm tratamento da etapa 1 e mantÃªm a conversa
    na etapa atual.
    """
    id_conversa = contexto_historico["id_conversa"]
    id_etapa_atual = contexto_historico.get("id_etapa_atual")
    id_etapa_proxima = contexto_historico["id_etapa_resposta"]
    tipo_mensagem = contexto_historico.get("tipo_mensagem_atual")
    texto_cliente = contexto_historico.get("texto_cliente_atual") or ""
    mensagem_cliente_atual = contexto_historico["mensagem_cliente_atual"]
    cliente_telefone = mensagem_cliente_atual["cliente_telefone"]
    phone_id_unidade = mensagem_cliente_atual["id_phone_unidade"]

    conversa_sem_etapa = id_etapa_atual is None

    if detecta_midia(tipo_mensagem):
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

    if detecta_pergunta_financeira(texto_cliente):
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

    if conversa_sem_etapa:
        return enviar_primeira_etapa(
            cliente_telefone,
            phone_id_unidade,
        )

    if detecta_nome_invalido(texto_cliente):
        _logar_tratamento_texto(
            contexto_historico,
            TIPO_TRATAMENTO_NOME_INVALIDO,
        )

        return enviar_primeira_etapa_contexto_nome_invalido(
            cliente_telefone,
            phone_id_unidade,
        )

    # Se chegou aqui, a mensagem passou por mÃ­dia, pergunta financeira e
    # validaÃ§Ã£o de nome. Portanto, para a etapa 1, ela Ã© uma resposta vÃ¡lida.
    # O erro abaixo sÃ³ existe porque a prÃ³xima etapa ainda nÃ£o foi implementada.
    logger.warning(
        "primeira_etapa_proxima_etapa_pendente | acao=nao_enviar id_conversa=%s etapa_proxima=%s",
        id_conversa,
        id_etapa_proxima,
    )
    raise NotImplementedError(
        f"Sender da etapa {id_etapa_proxima} ainda nao implementado"
    )


def _logar_tipo_nao_suportado(contexto_historico):
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


def _logar_tratamento_texto(contexto_historico, motivo):
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
```

## Passo 9 - fora do escopo deste plano

Para cumprir a regra de que cada passo deve conter o cÃ³digo completo de todo
arquivo criado ou alterado, este plano fica limitado aos arquivos de produÃ§Ã£o.

Testes e documentaÃ§Ã£o devem entrar em um plano separado, tambÃ©m com o conteÃºdo
completo de cada arquivo criado ou alterado.

Arquivos de teste que provavelmente precisarÃ£o ser removidos ou reescritos no
plano de testes:

```text
tests/unit/test_flow_sender.py
tests/unit/test_flow_treat_context.py
tests/unit/test_flow_treat_financial.py
tests/unit/test_flow_treat_unsupported_type.py
tests/unit/test_rotear_resposta_cliente.py
tests/unit/test_sender_etapa1.py
tests/unit/test_sender_tratamento.py
tests/unit/test_sender_tratamento_context.py
tests/unit/test_sender_tratamento_financeiro.py
tests/unit/test_valida_resposta_cliente.py
tests/unit/test_whatsapp_structure.py
tests/unit/test_worker_flow_contract.py
tests/unit/test_worker_flow_runtime.py
```

## Passo 10 - validaÃ§Ãµes depois da aplicaÃ§Ã£o do cÃ³digo de produÃ§Ã£o

Buscar referÃªncias removidas:

```powershell
rg -n "rotear_resposta_cliente|valida_resposta_cliente|flow_treat_context|flow_treat_financial|flow_treat_unsupported_type|flow_resolver|etapa_inicial" workers core
```

Rodar check do Django:

```powershell
python callback/manage.py check
```

ObservaÃ§Ã£o: a suÃ­te completa de testes sÃ³ deve ser rodada depois do plano de
testes ser atualizado, porque ainda existem testes antigos apontando para
arquivos removidos neste novo desenho.

## Resposta Sobre AvanÃ§ar Ou Manter Etapa

Sim, o desenho permite que o `flow_sender` e a etapa digam para
`atualizar_banco_com_contexto_final()` se a conversa deve avanÃ§ar ou ficar na
etapa atual.

Quem decide isso Ã© o `contexto_envio` retornado:

```python
"id_etapa_resultante": 1
```

mantÃ©m a conversa na etapa 1.

```python
"id_etapa_resultante": contexto_historico["id_etapa_resposta"]
```

avanÃ§a para a prÃ³xima etapa.

Neste plano, os tratamentos de mÃ­dia, financeiro e contexto retornam
`id_etapa_resultante = 1`, entÃ£o a conversa fica na etapa atual.

Nome invÃ¡lido nÃ£o cai em `NotImplementedError`. Ele chama:

```python
enviar_primeira_etapa_contexto_nome_invalido(...)
```

e retorna `id_etapa_resultante = 1`, mantendo a conversa na etapa 1.

Quando a etapa 2 existir, o caso de nome vÃ¡lido deve chamar o sender da etapa 2
e retornar:

```python
"id_etapa_resultante": contexto_historico["id_etapa_resposta"]
```

fazendo o banco avanÃ§ar a conversa.

Enquanto a etapa 2 nÃ£o existir, somente o caso de nome vÃ¡lido cai em
`NotImplementedError`, porque ele representa uma tentativa legÃ­tima de avanÃ§ar
para uma etapa ainda nÃ£o implementada.
