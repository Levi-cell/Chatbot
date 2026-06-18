# Plano de organização da integração WhatsApp/PyWa

## Status

**Plano para revisão. Ainda não aplicado.**

## Regra deste plano

Cada etapa abaixo representa exatamente um arquivo criado, alterado ou removido.
Para arquivos criados ou alterados, o bloco de código contém o conteúdo final
completo do arquivo. Não há trechos parciais nem instruções como "alterar apenas
o import".

## Objetivo

- `messages` armazena somente textos, títulos, callbacks e funções puras de
  formatação;
- `pywa_functions` concentra a criação do cliente e todas as chamadas diretas à
  biblioteca PyWa;
- o worker decide o fluxo, mas não monta mensagens destinadas ao WhatsApp;
- `tools` permanece reservado a scripts administrativos;
- nenhuma regra de negócio, retry, commit, lock, etapa ou contexto persistido é
  alterado.

`tools/config.py` não será movido neste plano. Ele contém configuração sensível e
sua migração deve ocorrer em uma tarefa própria, sem misturar reorganização com
mudança de deploy ou credenciais.

## Estrutura final

```text
core/integrations/whatsapp/
├── README.md
├── __init__.py
├── exceptions.py
├── messages/
│   ├── __init__.py
│   ├── etapas.py
│   └── tratamentos.py
├── pywa_functions/
│   ├── __init__.py
│   ├── cliente.py
│   ├── envios.py
│   ├── etapas.py
│   ├── tratamentos.py
│   └── usuarios.py
└── tools/
    ├── __init__.py
    ├── ativando_numero.py
    ├── ativando_waba_id.py
    ├── block_report.py
    ├── config.py
    └── desativando_numero.py
```

## Etapa 1 - Criar `messages/etapas.py`

Arquivo: `core/integrations/whatsapp/messages/etapas.py`

```python
MENSAGEM_ETAPA_1 = "Ola! {saudacao}."
TITULO_BOTAO_ETAPA_1 = "Aperte em mim"


def montar_mensagem_etapa_1(saudacao):
    return MENSAGEM_ETAPA_1.format(saudacao=saudacao)
```

## Etapa 2 - Criar `messages/tratamentos.py`

Arquivo: `core/integrations/whatsapp/messages/tratamentos.py`

```python
MENSAGEM_MIDIA_INICIO = (
    "Ola! Vi que voce iniciou o atendimento com uma midia.\n\n"
    "Por enquanto eu so consigo continuar por mensagem de texto ou botoes. "
    "Envie uma mensagem de texto para comecarmos."
)

MENSAGEM_MIDIA_ETAPA = (
    "Recebi uma midia, mas nesta etapa eu preciso que voce responda por texto "
    "ou use os botoes disponiveis.\n\n"
    "Envie uma mensagem de texto para continuarmos."
)

TITULO_BOTAO_CONTINUAR = "Continuar"
CALLBACK_RETORNAR_ATENDIMENTO = "retornar_atendimento"


def montar_mensagem_tipo_nao_suportado(conversa_nova):
    if conversa_nova:
        return MENSAGEM_MIDIA_INICIO

    return MENSAGEM_MIDIA_ETAPA
```

## Etapa 3 - Criar `pywa_functions/__init__.py`

Arquivo: `core/integrations/whatsapp/pywa_functions/__init__.py`

```python
"""Implementações que acessam diretamente a biblioteca PyWa."""
```

## Etapa 4 - Criar `pywa_functions/cliente.py`

Arquivo: `core/integrations/whatsapp/pywa_functions/cliente.py`

```python
from pywa import WhatsApp

from core.integrations.whatsapp.tools.config import TOKEN_USUARIO_META


def conta_wa(phone_id, token=TOKEN_USUARIO_META):
    phone_id = _normalizar_phone_id(phone_id)

    return WhatsApp(
        token=token,
        phone_id=phone_id,
    )


def _normalizar_phone_id(phone_id):
    if phone_id is None:
        raise ValueError("phone_id da unidade nao informado")

    phone_id = str(phone_id).strip()

    if not phone_id:
        raise ValueError("phone_id da unidade vazio")

    return phone_id
```

## Etapa 5 - Criar `pywa_functions/envios.py`

Arquivo: `core/integrations/whatsapp/pywa_functions/envios.py`

```python
import logging

from pywa.types import Button

from core.integrations.whatsapp.pywa_functions.cliente import conta_wa
from core.logging_config import short_value


logger = logging.getLogger("whatsapp.pywa")


def enviar_mensagem_texto(to, text, phone_id_unidade):
    cliente_wa = conta_wa(phone_id_unidade)

    sent_message = cliente_wa.send_message(
        to=to,
        text=text,
    )

    id_hash_msg = _extrair_id_mensagem_enviada(sent_message)

    logger.info(
        "whatsapp_mensagem_enviada | acao=enviar tipo=text to=%s id_hash_msg=%s",
        short_value(to),
        id_hash_msg,
    )

    return id_hash_msg


def enviar_mensagem_texto_com_botao(
    to,
    text,
    titulo_botao,
    phone_id_unidade,
    callback_data=None,
):
    cliente_wa = conta_wa(phone_id_unidade)
    dados_callback = callback_data or titulo_botao

    sent_message = cliente_wa.send_message(
        to=to,
        text=text,
        buttons=[
            Button(
                title=titulo_botao,
                callback_data=dados_callback,
            )
        ],
    )

    id_hash_msg = _extrair_id_mensagem_enviada(sent_message)

    logger.info(
        "whatsapp_mensagem_enviada | acao=enviar tipo=interactive_button to=%s id_hash_msg=%s botao=%s",
        short_value(to),
        id_hash_msg,
        titulo_botao,
    )

    return id_hash_msg


def _extrair_id_mensagem_enviada(sent_message):
    id_hash_msg = getattr(sent_message, "id", None)

    if not id_hash_msg:
        raise ValueError("PyWa nao retornou id da mensagem enviada")

    return id_hash_msg
```

## Etapa 6 - Criar `pywa_functions/etapas.py`

Arquivo: `core/integrations/whatsapp/pywa_functions/etapas.py`

```python
import logging
from datetime import datetime
from zoneinfo import ZoneInfo

from core.integrations.whatsapp.exceptions import ErroEnvioMeta
from core.integrations.whatsapp.messages.etapas import (
    TITULO_BOTAO_ETAPA_1,
    montar_mensagem_etapa_1,
)
from core.integrations.whatsapp.pywa_functions.envios import (
    enviar_mensagem_texto_com_botao,
)
from core.logging_config import short_value


logger = logging.getLogger("whatsapp.sender")

FUSO_HORARIO_ATENDIMENTO = ZoneInfo("America/Sao_Paulo")


def sender_etapa1(cliente_telefone, phone_id_unidade):
    saudacao = obter_saudacao_por_horario()
    mensagem_bot = montar_mensagem_etapa_1(saudacao)
    titulo_botao = TITULO_BOTAO_ETAPA_1

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

## Etapa 7 - Criar `pywa_functions/tratamentos.py`

Arquivo: `core/integrations/whatsapp/pywa_functions/tratamentos.py`

```python
import logging

from core.integrations.whatsapp.exceptions import ErroEnvioMeta
from core.integrations.whatsapp.messages.tratamentos import (
    CALLBACK_RETORNAR_ATENDIMENTO,
    TITULO_BOTAO_CONTINUAR,
    montar_mensagem_tipo_nao_suportado,
)
from core.integrations.whatsapp.pywa_functions.envios import (
    enviar_mensagem_texto_com_botao,
)
from core.logging_config import short_value


logger = logging.getLogger("whatsapp.sender_tratamento")


def sender_tratamento_tipo_nao_suportado(
    cliente_telefone,
    phone_id_unidade,
    id_etapa,
    tipo_mensagem,
    conversa_nova,
):
    mensagem_bot = montar_mensagem_tipo_nao_suportado(conversa_nova)

    try:
        id_hash_msg_bot = enviar_mensagem_texto_com_botao(
            to=cliente_telefone,
            text=mensagem_bot,
            titulo_botao=TITULO_BOTAO_CONTINUAR,
            phone_id_unidade=phone_id_unidade,
            callback_data=CALLBACK_RETORNAR_ATENDIMENTO,
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
            "atualizar_last_from_bot": True,
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

## Etapa 8 - Criar `pywa_functions/usuarios.py`

Arquivo: `core/integrations/whatsapp/pywa_functions/usuarios.py`

```python
import logging

from core.integrations.whatsapp.pywa_functions.cliente import conta_wa
from core.logging_config import short_value


logger = logging.getLogger("whatsapp.block")


def bloquear_usuario_meta(wa_id_cliente, phone_id_unidade):
    cliente_wa = conta_wa(phone_id_unidade)

    resultado = cliente_wa.block_users(
        users=[str(wa_id_cliente)],
        phone_id=str(phone_id_unidade),
    )

    erros = getattr(resultado, "errors", None)
    if erros:
        raise RuntimeError(f"PyWa retornou erro ao bloquear usuario: {erros}")

    logger.warning(
        "whatsapp_usuario_bloqueado | acao=bloquear wa_id_cliente=%s phone_id_unidade=%s",
        short_value(wa_id_cliente),
        short_value(phone_id_unidade),
    )

    return resultado


def desbloquear_usuario_meta(wa_id_cliente, phone_id_unidade):
    cliente_wa = conta_wa(phone_id_unidade)

    resultado = cliente_wa.unblock_users(
        users=[str(wa_id_cliente)],
        phone_id=str(phone_id_unidade),
    )

    erros = getattr(resultado, "errors", None)
    if erros:
        raise RuntimeError(f"PyWa retornou erro ao desbloquear usuario: {erros}")

    logger.warning(
        "whatsapp_usuario_desbloqueado | acao=desbloquear wa_id_cliente=%s phone_id_unidade=%s",
        short_value(wa_id_cliente),
        short_value(phone_id_unidade),
    )

    return resultado


def listar_usuarios_bloqueados_meta(phone_id_unidade):
    cliente_wa = conta_wa(phone_id_unidade)
    return cliente_wa.get_blocked_users().all(sleep=0.2)
```

## Etapa 9 - Criar `README.md`

Arquivo: `core/integrations/whatsapp/README.md`

````markdown
# Integração WhatsApp

Esta pasta concentra a comunicação do sistema com a Meta e com a biblioteca
PyWa.

## Responsabilidades

- `messages`: textos, títulos, callbacks e formatadores puros;
- `pywa_functions`: cliente PyWa e chamadas diretas à biblioteca;
- `tools`: scripts administrativos executados fora do fluxo normal;
- `exceptions.py`: exceções compartilhadas da integração;

## Direção das dependências

```text
worker -> pywa_functions -> messages
                      └──> PyWa -> Meta
```

`messages` não importa worker, banco, Redis, Meta ou PyWa.
`pywa_functions` não controla transações, retries, etapas do banco ou filas.
O worker não deve importar diretamente a biblioteca PyWa nem manter textos de
saída destinados ao WhatsApp.
````

## Etapa 10 - Alterar `flow_sender.py`

Arquivo: `workers/worker_flow/response_flow/flow_sender.py`

```python
import logging

from core.integrations.whatsapp.pywa_functions.etapas import sender_etapa1


logger = logging.getLogger("worker.sender")


def flow_sender(contexto_historico):
    id_conversa = contexto_historico["id_conversa"]
    id_etapa_resposta = contexto_historico["id_etapa_resposta"]
    retry_count = contexto_historico["retry_count"]

    mensagem_cliente_atual = contexto_historico["mensagem_cliente_atual"]
    cliente_atual_id_mensagem_fila = mensagem_cliente_atual["id_mensagem_fila"]
    cliente_atual_id_hash_msg = mensagem_cliente_atual["id_hash_msg"]
    cliente_telefone = mensagem_cliente_atual["cliente_telefone"]
    phone_id_unidade = mensagem_cliente_atual["id_phone_unidade"]

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

    if id_etapa_resposta == 1:
        return sender_etapa1(
            cliente_telefone=cliente_telefone,
            phone_id_unidade=phone_id_unidade,
        )

    logger.warning(
        "flow_sender_etapa_pendente | acao=nao_enviar id_conversa=%s etapa=%s",
        id_conversa,
        id_etapa_resposta,
    )
    raise NotImplementedError(
        f"Sender da etapa {id_etapa_resposta} ainda nao implementado"
    )
```

## Etapa 11 - Alterar `flow_treat_unsupported_type.py`

Arquivo: `workers/worker_flow/response_flow/flow_treat_unsupported_type.py`

```python
import logging

from core.integrations.whatsapp.pywa_functions.tratamentos import (
    sender_tratamento_tipo_nao_suportado,
)


logger = logging.getLogger("worker.treat_unsupported_type")


def flow_treat_unsupported_type(contexto_historico, contexto_validacao):
    # Regra de negocio V1: esta versao nao trabalha com midias/anexos.
    # Midia recebida entra no historico, recebe tratamento e nao avanca etapa.
    id_conversa = contexto_historico["id_conversa"]
    retry_count = contexto_historico["retry_count"]
    mensagem_cliente_atual = contexto_historico["mensagem_cliente_atual"]
    resposta_bot_atual = (
        contexto_historico["resposta_bot_para_mensagem_atual"] or {}
    )

    if resposta_bot_atual:
        logger.info(
            "flow_treat_unsupported_type_idempotencia_ok | motivo=resposta_bot_ja_registrada acao=nao_enviar id_conversa=%s id_mensagem_fila=%s id_hash_cliente=%s id_resposta_bot=%s tratamento=%s retry=%s",
            id_conversa,
            mensagem_cliente_atual["id_mensagem_fila"],
            mensagem_cliente_atual["id_hash_msg"],
            resposta_bot_atual.get("id_mensagem"),
            contexto_validacao["tipo_tratamento"],
            retry_count,
        )
        return {
            "enviou": False,
            "resposta_ja_existia": True,
            "id_hash_msg_bot": resposta_bot_atual.get("id_hash_msg"),
            "id_etapa_resultante": resposta_bot_atual.get("id_etapa"),
            "tratamento": True,
            "tipo_tratamento": contexto_validacao["tipo_tratamento"],
            "atualizar_conversa": False,
            "atualizar_last_from_bot": True,
        }

    if retry_count > 1:
        logger.info(
            "flow_treat_unsupported_type_reprocessamento | motivo=retry_maior_que_um acao=continuar_sem_resposta_previa id_conversa=%s id_mensagem_fila=%s id_hash_cliente=%s retry=%s tratamento=%s",
            id_conversa,
            mensagem_cliente_atual["id_mensagem_fila"],
            mensagem_cliente_atual["id_hash_msg"],
            retry_count,
            contexto_validacao["tipo_tratamento"],
        )

    if contexto_validacao["tipo_tratamento"] == "tipo_mensagem_nao_suportado":
        return sender_tratamento_tipo_nao_suportado(
            cliente_telefone=mensagem_cliente_atual["cliente_telefone"],
            phone_id_unidade=mensagem_cliente_atual["id_phone_unidade"],
            id_etapa=contexto_historico["id_etapa_cliente"],
            tipo_mensagem=contexto_validacao.get("tipo_mensagem"),
            conversa_nova=contexto_historico.get("id_etapa_atual") is None,
        )

    logger.warning(
        "flow_treat_unsupported_type_nao_implementado | acao=erro id_conversa=%s tratamento=%s",
        id_conversa,
        contexto_validacao["tipo_tratamento"],
    )
    raise NotImplementedError(
        f"Tratamento {contexto_validacao['tipo_tratamento']} ainda nao implementado"
    )
```

## Etapa 12 - Alterar `valida_resposta_cliente.py`

Arquivo: `workers/worker_flow/valida_resposta_cliente.py`

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
        "avancar_etapa": False,
    }
```

## Etapa 13 - Alterar `tools/block_report.py`

Arquivo: `core/integrations/whatsapp/tools/block_report.py`

```python
from core.database.connection_aws import get_conn
from core.integrations.whatsapp.pywa_functions.usuarios import (
    listar_usuarios_bloqueados_meta,
)
from core.repositories.bloqueio_meta import (
    listar_bloqueios_meta_banco_para_reconciliacao,
)
from core.repositories.querys import buscar_unidades_para_listagem_bloqueios


def listar_bloqueados_de_cada_unidade(imprimir=True):
    conn = get_conn(application_name="script_chatbot")
    cursor = conn.cursor()
    resultado = []

    try:
        unidades = buscar_unidades_para_listagem_bloqueios(cursor)

        for id_unidade, nome_unidade, phone_id_unidade in unidades:
            if imprimir:
                print(
                    f"unidade {id_unidade} {nome_unidade} "
                    f"phone id ({phone_id_unidade}):"
                )

            bloqueados = listar_usuarios_bloqueados_meta(phone_id_unidade)
            wa_ids_bloqueados = [
                wa_id
                for wa_id in (
                    _extrair_wa_id_bloqueado(usuario)
                    for usuario in bloqueados
                )
                if wa_id
            ]

            resultado.append({
                "id_unidade": id_unidade,
                "nome_unidade": nome_unidade,
                "phone_id_unidade": str(phone_id_unidade),
                "wa_ids_bloqueados": wa_ids_bloqueados,
            })

            if imprimir and not wa_ids_bloqueados:
                print("   - nenhum numero bloqueado")

            if imprimir:
                for wa_id in wa_ids_bloqueados:
                    print(f"   - {wa_id} numero bloqueado")

                print()

        return resultado

    finally:
        conn.close()


def job_reconciliacao_bloqueios_meta():
    bloqueios_meta = listar_bloqueados_de_cada_unidade(
        imprimir=False,
    )
    bloqueios_banco = _listar_bloqueios_banco()

    meta_por_chave = {}
    banco_por_chave = {}

    for unidade in bloqueios_meta:
        phone_id_unidade = unidade["phone_id_unidade"]

        for wa_id_cliente in unidade["wa_ids_bloqueados"]:
            chave = (phone_id_unidade, wa_id_cliente)
            meta_por_chave[chave] = unidade

    for bloqueio in bloqueios_banco:
        chave = (bloqueio["phone_id_unidade"], bloqueio["wa_id_cliente"])
        banco_por_chave[chave] = bloqueio

    somente_meta = sorted(set(meta_por_chave) - set(banco_por_chave))
    somente_banco = sorted(set(banco_por_chave) - set(meta_por_chave))
    sincronizados = sorted(set(meta_por_chave) & set(banco_por_chave))

    print("===== RECONCILIACAO BLOQUEIOS META X BANCO =====")
    print(f"bloqueios_sincronizados: {len(sincronizados)}")
    print(f"somente_na_meta: {len(somente_meta)}")
    print(f"somente_no_banco: {len(somente_banco)}")
    print()

    if somente_meta:
        print("SOMENTE NA META:")
        for phone_id_unidade, wa_id_cliente in somente_meta:
            unidade = meta_por_chave[(phone_id_unidade, wa_id_cliente)]
            print(
                f"   - wa_id {wa_id_cliente} bloqueado na Meta, "
                f"mas ausente no banco | unidade {unidade['id_unidade']} "
                f"{unidade['nome_unidade']} phone id ({phone_id_unidade})"
            )
        print()

    if somente_banco:
        print("SOMENTE NO BANCO:")
        for phone_id_unidade, wa_id_cliente in somente_banco:
            bloqueio = banco_por_chave[(phone_id_unidade, wa_id_cliente)]
            print(
                f"   - wa_id {wa_id_cliente} registrado no banco, "
                f"mas ausente na Meta | bloqueio {bloqueio['id_bloqueio']} "
                f"unidade {bloqueio['id_unidade']} {bloqueio['nome_unidade']} "
                f"phone id ({phone_id_unidade})"
            )
        print()

    if not somente_meta and not somente_banco:
        print("OK: banco e Meta estao sincronizados.")

    return {
        "sincronizados": sincronizados,
        "somente_meta": somente_meta,
        "somente_banco": somente_banco,
    }


def _listar_bloqueios_banco():
    conn = get_conn(application_name="script_chatbot")
    cursor = conn.cursor()

    try:
        bloqueios = listar_bloqueios_meta_banco_para_reconciliacao(cursor)

    finally:
        conn.close()

    return [
        {
            "id_bloqueio": id_bloqueio,
            "wa_id_cliente": str(wa_id_cliente),
            "id_unidade": id_unidade,
            "phone_id_unidade": str(phone_id_unidade),
            "nome_unidade": nome_unidade,
        }
        for (
            id_bloqueio,
            wa_id_cliente,
            id_unidade,
            phone_id_unidade,
            nome_unidade,
        ) in bloqueios
    ]


def _extrair_wa_id_bloqueado(usuario):
    wa_id = getattr(usuario, "wa_id", usuario)

    if wa_id is None:
        return None

    wa_id = str(wa_id).strip()
    return wa_id or None


"""FUNCAO FINAL"""
# job_reconciliacao_bloqueios_meta()
```

## Etapa 14 - Alterar `flood_guard.py`

Arquivo: `callback/webhook/services/flood_guard.py`

A única mudança lógica deste arquivo é o caminho do import de bloqueio. O
conteúdo completo final será:

```python
import logging

from django.http import JsonResponse

from core.cache.runtime.cache_flood_redis import avaliar_flood_redis
from core.cache.cache_flood_memoria import avaliar_flood_memoria
from core.database.connection_aws import get_conn
from core.integrations.whatsapp.pywa_functions.usuarios import (
    bloquear_usuario_meta,
)
from core.logging_config import short_value
from core.repositories.bloqueio_meta import (
    buscar_id_cliente_por_wa_id,
    buscar_unidade_bloqueio_por_phone_id,
    contar_eventos_flood_banco,
    limpar_eventos_flood_antigos,
    registrar_cliente_bloqueado_meta_banco,
    registrar_evento_flood_banco,
)
from .alerta_flood_memoria import registrar_alerta_flood_memoria


logger = logging.getLogger("webhook.flood_guard")

REGRAS_FLOOD = (
    {
        "nome": "rajada_curta",
        "limite": 15,
        "janela_segundos": 5,
    },
)


def responder_se_flood(data):
    phone_id_unidade = _extrair_phone_number_id(data)
    wa_id_cliente = _extrair_cliente_telefone(data)
    id_hash_msg = _extrair_id_hash_msg(data)

    flood = bloquear_cliente_se_flood(
        wa_id_cliente,
        phone_id_unidade,
        id_hash_msg,
    )

    if not flood["bloqueado"]:
        return None

    logger.warning(
        "mensagem_ignorada | motivo=%s regra=%s acao=bloqueio_meta_nao_enfileirar cliente=%s phone_number_id=%s total=%s meta_ok=%s",
        flood["motivo"],
        flood.get("regra"),
        short_value(wa_id_cliente),
        short_value(phone_id_unidade),
        flood["total"],
        flood.get("meta_ok"),
    )

    return JsonResponse({
        "status": "ignored",
        "reason": flood["motivo"],
    })


def bloquear_cliente_se_flood(wa_id_cliente, phone_id_unidade, id_hash_msg):
    if not wa_id_cliente or not phone_id_unidade or not id_hash_msg:
        return {
            "bloqueado": False,
            "motivo": "dados_invalidos",
            "total": 0,
            "regra": None,
            "meta_ok": None,
        }

    rate_redis = avaliar_flood_redis(
        wa_id_cliente,
        phone_id_unidade,
        regras=REGRAS_FLOOD,
    )

    if rate_redis["redis_ok"]:
        if rate_redis["flood"]:
            return _bloquear_e_registrar(
                wa_id_cliente,
                phone_id_unidade,
                origem="redis",
                total=rate_redis["total"],
                regra=rate_redis["regra"],
            )

        return {
            "bloqueado": False,
            "motivo": "abaixo_limite_redis",
            "total": rate_redis["total"],
            "regra": None,
            "meta_ok": None,
        }

    rate_banco = _avaliar_flood_banco(
        wa_id_cliente,
        phone_id_unidade,
        id_hash_msg,
    )

    if rate_banco["flood"]:
        return _bloquear_e_registrar(
            wa_id_cliente,
            phone_id_unidade,
            origem="banco",
            total=rate_banco["total"],
            regra=rate_banco["regra"],
        )

    if not rate_banco["banco_ok"]:
        rate_memoria = avaliar_flood_memoria(
            wa_id_cliente,
            phone_id_unidade,
            regras=REGRAS_FLOOD,
        )

        if rate_memoria["flood"]:
            return _bloquear_via_memoria_e_alertar(
                wa_id_cliente,
                phone_id_unidade,
                total=rate_memoria["total"],
                regra=rate_memoria["regra"],
                id_hash_msg=id_hash_msg,
            )

        return {
            "bloqueado": False,
            "motivo": rate_memoria["motivo"],
            "total": rate_memoria["total"],
            "regra": None,
            "meta_ok": None,
        }

    return {
        "bloqueado": False,
        "motivo": rate_banco["motivo"],
        "total": rate_banco["total"],
        "regra": None,
        "meta_ok": None,
    }


def _avaliar_flood_banco(wa_id_cliente, phone_id_unidade, id_hash_msg):
    conn = None

    try:
        conn = get_conn(application_name="webhook_chatbot")
        cursor = conn.cursor()

        registrar_evento_flood_banco(
            wa_id_cliente,
            phone_id_unidade,
            id_hash_msg,
            cursor,
        )
        maior_total = 0
        total = 0
        regra_estourada = None

        for regra in REGRAS_FLOOD:
            total = contar_eventos_flood_banco(
                wa_id_cliente,
                phone_id_unidade,
                cursor,
                janela_segundos=regra["janela_segundos"],
            )

            maior_total = max(maior_total, total)

            if total >= regra["limite"]:
                regra_estourada = regra
                break

        limpar_eventos_flood_antigos(cursor)

        conn.commit()

        return {
            "banco_ok": True,
            "flood": regra_estourada is not None,
            "total": total if regra_estourada else maior_total,
            "motivo": "banco",
            "regra": regra_estourada["nome"] if regra_estourada else None,
        }

    except Exception as exc:
        if conn:
            conn.rollback()

        logger.warning(
            "rate_limit_banco_falhou | acao=seguir_fluxo wa_id_cliente=%s phone_id_unidade=%s erro=%s",
            short_value(wa_id_cliente),
            short_value(phone_id_unidade),
            exc,
        )
        return {
            "banco_ok": False,
            "flood": False,
            "total": 0,
            "motivo": "banco_indisponivel",
            "regra": None,
        }

    finally:
        if conn:
            conn.close()


def _bloquear_via_memoria_e_alertar(
    wa_id_cliente,
    phone_id_unidade,
    total,
    regra,
    id_hash_msg,
):
    meta_ok = False
    erro_meta = None
    motivo = "flood_memoria"

    try:
        bloquear_usuario_meta(wa_id_cliente, phone_id_unidade)
        meta_ok = True

    except Exception as exc:
        erro_meta = str(exc)
        motivo = "flood_memoria_meta_falhou"
        logger.exception(
            "bloqueio_meta_falhou | motivo=meta_indisponivel acao=ignorar_sem_registrar origem=memoria regra=%s wa_id_cliente=%s phone_id_unidade=%s total=%s erro=%s",
            regra,
            short_value(wa_id_cliente),
            short_value(phone_id_unidade),
            total,
            exc,
        )

    registrar_alerta_flood_memoria(
        wa_id_cliente=wa_id_cliente,
        phone_id_unidade=phone_id_unidade,
        origem="memoria",
        regra=regra,
        total=total,
        meta_ok=meta_ok,
        motivo=motivo,
        id_hash_msg=id_hash_msg,
        erro_meta=erro_meta,
    )

    logger.warning(
        "flood_bloqueado_memoria | acao=ignorar_alertar regra=%s wa_id_cliente=%s phone_id_unidade=%s total=%s meta_ok=%s",
        regra,
        short_value(wa_id_cliente),
        short_value(phone_id_unidade),
        total,
        meta_ok,
    )

    return {
        "bloqueado": True,
        "motivo": motivo,
        "total": total,
        "regra": regra,
        "id_bloqueio": None,
        "id_cliente": None,
        "id_unidade": None,
        "meta_ok": meta_ok,
    }


def _bloquear_e_registrar(wa_id_cliente, phone_id_unidade, origem, total, regra):
    dados_bloqueio = _buscar_dados_bloqueio(
        wa_id_cliente,
        phone_id_unidade,
    )

    if not dados_bloqueio["id_unidade"]:
        logger.warning(
            "flood_detectado_sem_bloqueio_meta | motivo=%s acao=ignorar_sem_registrar origem=%s regra=%s wa_id_cliente=%s phone_id_unidade=%s total=%s",
            dados_bloqueio["motivo"],
            origem,
            regra,
            short_value(wa_id_cliente),
            short_value(phone_id_unidade),
            total,
        )
        return {
            "bloqueado": True,
            "motivo": dados_bloqueio["motivo"],
            "total": total,
            "regra": regra,
            "id_bloqueio": None,
            "id_cliente": None,
            "id_unidade": None,
            "meta_ok": False,
        }

    try:
        bloquear_usuario_meta(wa_id_cliente, phone_id_unidade)

    except Exception as exc:
        logger.exception(
            "bloqueio_meta_falhou | motivo=meta_indisponivel acao=ignorar_sem_registrar origem=%s regra=%s wa_id_cliente=%s phone_id_unidade=%s total=%s erro=%s",
            origem,
            regra,
            short_value(wa_id_cliente),
            short_value(phone_id_unidade),
            total,
            exc,
        )
        return {
            "bloqueado": True,
            "motivo": f"flood_{origem}_meta_falhou",
            "total": total,
            "regra": regra,
            "id_bloqueio": None,
            "id_cliente": dados_bloqueio["id_cliente"],
            "id_unidade": dados_bloqueio["id_unidade"],
            "meta_ok": False,
        }

    id_bloqueio = _registrar_bloqueio_banco_apos_meta(
        dados_bloqueio["id_cliente"],
        wa_id_cliente,
        dados_bloqueio["id_unidade"],
        dados_bloqueio["phone_id_unidade"],
    )

    if not id_bloqueio:
        logger.critical(
            "bloqueio_meta_registro_pos_meta_falhou | motivo=meta_ok_banco_falhou acao=investigar_reconciliacao wa_id_cliente=%s id_cliente=%s id_unidade=%s phone_id_unidade=%s",
            short_value(wa_id_cliente),
            dados_bloqueio["id_cliente"],
            dados_bloqueio["id_unidade"],
            short_value(dados_bloqueio["phone_id_unidade"]),
        )

    logger.warning(
        "flood_bloqueado | acao=registrar_resultado origem=%s regra=%s wa_id_cliente=%s id_cliente=%s id_unidade=%s phone_id_unidade=%s total=%s id_bloqueio=%s meta_ok=%s",
        origem,
        regra,
        short_value(wa_id_cliente),
        dados_bloqueio["id_cliente"],
        dados_bloqueio["id_unidade"],
        short_value(dados_bloqueio["phone_id_unidade"]),
        total,
        id_bloqueio,
        True,
    )

    return {
        "bloqueado": True,
        "motivo": f"flood_{origem}",
        "total": total,
        "regra": regra,
        "id_bloqueio": id_bloqueio,
        "id_cliente": dados_bloqueio["id_cliente"],
        "id_unidade": dados_bloqueio["id_unidade"],
        "meta_ok": True,
    }


def _buscar_dados_bloqueio(wa_id_cliente, phone_id_unidade):
    conn = None
    dados_vazios = {
        "id_cliente": None,
        "id_unidade": None,
        "phone_id_unidade": phone_id_unidade,
        "motivo": "dados_bloqueio_indisponiveis",
    }

    try:
        conn = get_conn(application_name="webhook_chatbot")
        cursor = conn.cursor()

        id_cliente = buscar_id_cliente_por_wa_id(wa_id_cliente, cursor)
        unidade = buscar_unidade_bloqueio_por_phone_id(
            phone_id_unidade,
            cursor,
        )

        if not unidade:
            logger.warning(
                "bloqueio_meta_dados_ignorados | motivo=unidade_nao_cadastrada acao=nao_bloquear_meta wa_id_cliente=%s phone_id_unidade=%s",
                short_value(wa_id_cliente),
                short_value(phone_id_unidade),
            )
            return {
                **dados_vazios,
                "id_cliente": id_cliente,
                "motivo": "flood_sem_unidade_ativa",
            }

        id_unidade, phone_id_cadastrado = unidade

        return {
            "id_cliente": id_cliente,
            "id_unidade": id_unidade,
            "phone_id_unidade": phone_id_cadastrado,
            "motivo": "ok",
        }

    except Exception as exc:
        logger.exception(
            "bloqueio_meta_dados_falharam | motivo=banco_indisponivel acao=nao_bloquear_meta wa_id_cliente=%s phone_id_unidade=%s erro=%s",
            short_value(wa_id_cliente),
            short_value(phone_id_unidade),
            exc,
        )
        return {
            **dados_vazios,
            "motivo": "flood_banco_indisponivel",
        }

    finally:
        if conn:
            conn.close()


def _registrar_bloqueio_banco_apos_meta(
    id_cliente,
    wa_id_cliente,
    id_unidade,
    phone_id_unidade,
):
    conn = None

    try:
        conn = get_conn(application_name="webhook_chatbot")
        cursor = conn.cursor()

        id_bloqueio = registrar_cliente_bloqueado_meta_banco(
            id_cliente,
            wa_id_cliente,
            id_unidade,
            phone_id_unidade,
            cursor,
        )

        conn.commit()
        return id_bloqueio

    except Exception as exc:
        if conn:
            conn.rollback()

        logger.exception(
            "bloqueio_meta_registro_banco_falhou | motivo=meta_ok_banco_falhou acao=nao_registrado wa_id_cliente=%s id_cliente=%s id_unidade=%s phone_id_unidade=%s erro=%s",
            short_value(wa_id_cliente),
            id_cliente,
            id_unidade,
            short_value(phone_id_unidade),
            exc,
        )
        return None

    finally:
        if conn:
            conn.close()


def _extrair_phone_number_id(data):
    value = data.get("entry", [{}])[0].get("changes", [{}])[0].get("value", {})
    metadata = value.get("metadata", {})
    return metadata.get("phone_number_id")


def _extrair_cliente_telefone(data):
    value = data.get("entry", [{}])[0].get("changes", [{}])[0].get("value", {})
    contacts = value.get("contacts", [{}])
    return contacts[0].get("wa_id") if contacts else None


def _extrair_id_hash_msg(data):
    value = data.get("entry", [{}])[0].get("changes", [{}])[0].get("value", {})
    messages = value.get("messages", [{}])
    return messages[0].get("id") if messages else None
```

## Etapa 15 - Alterar `admin.py`

Arquivo: `callback/webhook/admin.py`

A única mudança lógica deste arquivo é o caminho do import de desbloqueio. O
conteúdo completo final será:

```python
import logging

from django.contrib import admin, messages
from django.db import connection
from django.http import HttpResponseRedirect
from django.urls import reverse
from django.utils.html import format_html

from core.cache.cache_unidade import (
    CacheUnidadesIndisponivel,
    recarregar_cache_unidades_ou_erro,
    validar_cache_unidades_disponivel_ou_erro,
)
from core.integrations.whatsapp.tools.ativando_numero import registrar_numero_whatsapp
from core.integrations.whatsapp.tools.desativando_numero import desregistrar_numero_whatsapp
from core.integrations.whatsapp.pywa_functions.usuarios import (
    desbloquear_usuario_meta,
)
from core.logging_config import short_value
from core.repositories.cache_control import incrementar_versao_cache_unidades

from .models import (
    CacheControle,
    Cliente,
    ClienteBloqueadoMeta,
    Conversa,
    Dependente,
    Etapa,
    FilaMensagens,
    HistoricoMensagens,
    RespostasDesafios,
    Unidade,
    WebhookFloodEvento,
)

logger = logging.getLogger(__name__)


class SomenteVisualizacaoAdminMixin:
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def get_readonly_fields(self, request, obj=None):
        return [field.name for field in self.model._meta.fields]


@admin.register(Unidade)
class UnidadeAdmin(admin.ModelAdmin):

    list_display = (
        "id_unidade",
        "nome",
        "cnpj",
        "telefone",
        "email_responsavel",
        "link_agendamento_clickable",
        "status_ativo",
    )

    search_fields = (
        "nome",
        "cnpj",
        "telefone",
        "email_responsavel",
        "link_agendamento",
    )

    list_filter = ("status_ativo",)
    ordering = ("nome",)

    list_per_page = 50
    empty_value_display = "-"

    def changeform_view(self, request, object_id=None, form_url="", extra_context=None):
        try:
            return super().changeform_view(
                request,
                object_id=object_id,
                form_url=form_url,
                extra_context=extra_context,
            )

        except CacheUnidadesIndisponivel as exc:
            logger.exception(
                "admin_unidade_cache_falhou | acao=rollback_admin object_id=%s erro=%s",
                object_id,
                exc,
            )
            self.message_user(
                request,
                (
                    "O Redis falhou ao atualizar o cache de unidades. "
                    "Nenhuma alteracao foi feita no banco. "
                    "Se a Meta ja tiver sido chamada, ela respondeu com sucesso; tente novamente."
                ),
                level=messages.ERROR,
            )
            return HttpResponseRedirect(request.path)

    def get_form(self, request, obj=None, change=False, **kwargs):
        base_form = super().get_form(request, obj, change=change, **kwargs)
        model_admin = self

        class UnidadeAdminForm(base_form):
            def _post_clean(self):
                super()._post_clean()

                if change or self.errors:
                    if change and not self.errors:
                        model_admin._validar_cache_unidades_form(
                            self,
                            request,
                            meta_validada=False,
                        )
                    return

                phone_number_id = self.cleaned_data.get("phone_number_id")

                if not phone_number_id:
                    return

                if not model_admin._registrar_meta_antes_de_salvar(
                    request,
                    phone_number_id,
                ):
                    self.add_error(
                        "phone_number_id",
                        "A Meta falhou ao registrar este numero. Unidade nao foi salva.",
                    )
                    return

                model_admin._validar_cache_unidades_form(
                    self,
                    request,
                    meta_validada=True,
                )

        return UnidadeAdminForm

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        self._registrar_alteracao_cache_unidades()

    def delete_model(self, request, obj):
        if not self._meta_desregistrada_nesta_requisicao(request, obj):
            if not self._desregistrar_meta_antes_de_excluir(request, obj):
                return

        if not self._cache_validado_nesta_requisicao(request, obj):
            if not self._validar_cache_unidades_antes_de_alterar(
                request,
                "excluir",
                meta_validada=True,
            ):
                return

        super().delete_model(request, obj)
        self._registrar_alteracao_cache_unidades()

    def get_actions(self, request):
        actions = super().get_actions(request)
        actions.pop("delete_selected", None)
        return actions

    def delete_queryset(self, request, queryset):
        logger.warning(
            "admin_unidade_exclusao_massa_bloqueada | acao=manter_registros usuario=%s total=%s",
            request.user,
            queryset.count(),
        )
        self.message_user(
            request,
            "Exclusao em massa de unidade nao permitida. Exclua uma unidade por vez.",
            level=messages.ERROR,
        )

    def delete_view(self, request, object_id, extra_context=None):
        try:
            if request.method == "POST":
                obj = self.get_object(request, object_id)

                if obj and not self._desregistrar_meta_antes_de_excluir(request, obj):
                    return HttpResponseRedirect(
                        reverse(
                            "admin:webhook_unidade_change",
                            args=[object_id],
                        )
                    )

                if obj and not self._validar_cache_unidades_antes_de_alterar(
                    request,
                    "excluir",
                    meta_validada=True,
                ):
                    return HttpResponseRedirect(
                        reverse(
                            "admin:webhook_unidade_change",
                            args=[object_id],
                        )
                    )

                if obj:
                    self._marcar_meta_desregistrada_na_requisicao(request, obj)
                    self._marcar_cache_validado_na_requisicao(request, obj)

            return super().delete_view(request, object_id, extra_context)

        except CacheUnidadesIndisponivel as exc:
            logger.exception(
                "admin_unidade_cache_delete_falhou | acao=rollback_admin object_id=%s erro=%s",
                object_id,
                exc,
            )
            self.message_user(
                request,
                (
                    "A Meta respondeu com sucesso, mas o Redis falhou. "
                    "A unidade foi mantida no banco. Tente novamente."
                ),
                level=messages.ERROR,
            )
            return HttpResponseRedirect(
                reverse(
                    "admin:webhook_unidade_change",
                    args=[object_id],
                )
            )

    def _registrar_alteracao_cache_unidades(self):
        with connection.cursor() as cursor:
            versao = incrementar_versao_cache_unidades(cursor)
            total_unidades = recarregar_cache_unidades_ou_erro(cursor)

        logger.info(
            "cache_unidades_versao_incrementada | acao=incrementar_versao_e_recarregar versao=%s unidades=%s",
            versao,
            total_unidades,
        )

    def link_agendamento_clickable(self, obj):
        if obj.link_agendamento:
            return format_html(
                '<a href="{}" target="_blank">Abrir</a>',
                obj.link_agendamento,
            )
        return "-"

    link_agendamento_clickable.short_description = "Agendamento"

    def _registrar_meta_antes_de_salvar(self, request, phone_number_id):
        try:
            status, resposta = registrar_numero_whatsapp(phone_number_id)

            if not self._meta_resposta_sucesso(status, resposta):
                logger.error(
                    "whatsapp_numero_registrar_falhou | acao=bloquear_save phone_number_id=%s status=%s resposta=%s",
                    short_value(phone_number_id),
                    status,
                    resposta,
                )
                self.message_user(
                    request,
                    f"Erro ao registrar numero no WhatsApp. Unidade nao foi salva: {resposta}",
                    level=messages.ERROR,
                )
                return False

            logger.info(
                "whatsapp_numero_registrado | acao=permitir_save phone_number_id=%s status=%s",
                short_value(phone_number_id),
                status,
            )
            self.message_user(
                request,
                "Numero registrado com sucesso no WhatsApp. Unidade salva no banco.",
                level=messages.SUCCESS,
            )
            return True

        except Exception as exc:
            logger.exception(
                "whatsapp_numero_registrar_erro | acao=bloquear_save phone_number_id=%s erro=%s",
                short_value(phone_number_id),
                exc,
            )
            self.message_user(
                request,
                f"Erro inesperado ao registrar numero. Unidade nao foi salva: {exc}",
                level=messages.ERROR,
            )
            return False

    def _desregistrar_meta_antes_de_excluir(self, request, obj):
        try:
            status, resposta = desregistrar_numero_whatsapp(obj.phone_number_id)

            if not self._meta_resposta_sucesso(status, resposta):
                logger.error(
                    "whatsapp_numero_desregistrar_falhou | acao=bloquear_delete phone_number_id=%s status=%s resposta=%s",
                    short_value(obj.phone_number_id),
                    status,
                    resposta,
                )
                self.message_user(
                    request,
                    f"Erro ao remover registro do numero na Meta. Unidade mantida no banco: {resposta}",
                    level=messages.ERROR,
                )
                return False

            logger.warning(
                "whatsapp_numero_desregistrado | acao=permitir_delete phone_number_id=%s status=%s",
                short_value(obj.phone_number_id),
                status,
            )
            self.message_user(
                request,
                "Registro do numero removido na Meta. Unidade removida do banco.",
                level=messages.SUCCESS,
            )
            return True

        except Exception as exc:
            logger.exception(
                "whatsapp_numero_desregistrar_erro | acao=bloquear_delete phone_number_id=%s erro=%s",
                short_value(obj.phone_number_id),
                exc,
            )
            self.message_user(
                request,
                f"Erro inesperado ao remover registro do numero na Meta. Unidade mantida no banco: {exc}",
                level=messages.ERROR,
            )
            return False

    def _marcar_meta_desregistrada_na_requisicao(self, request, obj):
        ids = getattr(request, "_unidades_meta_desregistradas", set())
        ids.add(obj.id_unidade)
        request._unidades_meta_desregistradas = ids

    def _meta_desregistrada_nesta_requisicao(self, request, obj):
        ids = getattr(request, "_unidades_meta_desregistradas", set())
        return obj.id_unidade in ids

    def _marcar_cache_validado_na_requisicao(self, request, obj):
        ids = getattr(request, "_unidades_cache_validadas", set())
        ids.add(obj.id_unidade)
        request._unidades_cache_validadas = ids

    def _cache_validado_nesta_requisicao(self, request, obj):
        ids = getattr(request, "_unidades_cache_validadas", set())
        return obj.id_unidade in ids

    def _validar_cache_unidades_form(self, form, request, meta_validada):
        if self._validar_cache_unidades_antes_de_alterar(
            request,
            "salvar",
            meta_validada=meta_validada,
        ):
            return

        form.add_error(
            None,
            self._mensagem_cache_unidades_falhou(meta_validada),
        )

    def _validar_cache_unidades_antes_de_alterar(
        self,
        request,
        acao,
        meta_validada=False,
    ):
        try:
            validar_cache_unidades_disponivel_ou_erro()
            logger.info(
                "cache_unidades_preflight_admin_ok | acao=%s",
                acao,
            )
            return True

        except CacheUnidadesIndisponivel as exc:
            logger.error(
                "cache_unidades_preflight_admin_falhou | acao=%s erro=%s",
                acao,
                exc,
            )

            if request is not None:
                self.message_user(
                    request,
                    self._mensagem_cache_unidades_falhou(meta_validada),
                    level=messages.ERROR,
                )

            return False

    @staticmethod
    def _mensagem_cache_unidades_falhou(meta_validada):
        if meta_validada:
            return (
                "A Meta respondeu com sucesso, mas o Redis falhou. "
                "Nenhuma alteracao foi feita no banco. Tente novamente."
            )

        return (
            "O Redis falhou ao atualizar o cache de unidades. "
            "Nenhuma alteracao foi feita no banco. Tente novamente."
        )

    @staticmethod
    def _meta_resposta_sucesso(status, resposta):
        if status not in (200, 204):
            return False

        if isinstance(resposta, dict) and resposta.get("success") is False:
            return False

        return True


@admin.register(Cliente)
class ClienteAdmin(SomenteVisualizacaoAdminMixin, admin.ModelAdmin):

    list_display = (
        "id_cliente",
        "nome",
        "waid_telefone",
        "email",
    )

    search_fields = (
        "nome",
        "waid_telefone",
        "email",
    )

    ordering = ("nome",)
    list_per_page = 50
    empty_value_display = "-"


@admin.register(Dependente)
class DependenteAdmin(SomenteVisualizacaoAdminMixin, admin.ModelAdmin):

    list_display = (
        "id_dependente",
        "id_cliente",
        "nome_dependente",
        "telefone_dependente",
        "email_dependente",
    )

    search_fields = (
        "nome_dependente",
        "telefone_dependente",
        "email_dependente",
        "id_cliente__waid_telefone",
        "id_cliente__nome",
    )

    ordering = ("id_dependente",)
    list_per_page = 50
    empty_value_display = "-"

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("id_cliente")


@admin.register(Etapa)
class EtapaAdmin(SomenteVisualizacaoAdminMixin, admin.ModelAdmin):

    list_display = (
        "id_etapa",
        "nome_etapa",
    )

    search_fields = ("nome_etapa",)
    ordering = ("id_etapa",)

    list_per_page = 50
    empty_value_display = "-"


@admin.register(Conversa)
class ConversaAdmin(SomenteVisualizacaoAdminMixin, admin.ModelAdmin):

    list_display = (
        "id_conversa",
        "cliente_link",
        "id_unidade",
        "id_etapa_atual",
        "status_ativa",
        "last_message_from",
        "followup_stage",
        "lead_no_funil",
        "processing",
        "last_interaction_at",
        "iniciou_em",
    )

    search_fields = (
        "id_cliente__waid_telefone",
        "id_cliente__nome",
    )

    list_filter = (
        "status_ativa",
        "lead_no_funil",
        "last_message_from",
        "followup_stage",
        "processing",
        "id_unidade",
        "id_etapa_atual",
    )

    ordering = ("-iniciou_em",)

    date_hierarchy = "iniciou_em"
    list_per_page = 50
    empty_value_display = "-"

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related(
            "id_cliente",
            "id_unidade",
            "id_etapa_atual",
        )

    def cliente_link(self, obj):
        if not obj.id_cliente:
            return "-"

        try:
            url = reverse(
                "admin:webhook_cliente_change",
                args=[obj.id_cliente.id_cliente],
            )
            return format_html(
                '<a href="{}">{}</a>',
                url,
                obj.id_cliente.nome or obj.id_cliente.waid_telefone,
            )
        except Exception:
            return obj.id_cliente.nome or obj.id_cliente.waid_telefone

    cliente_link.short_description = "Cliente"


@admin.register(FilaMensagens)
class FilaMensagensAdmin(SomenteVisualizacaoAdminMixin, admin.ModelAdmin):

    list_display = (
        "id_mensagem",
        "id_conversa",
        "status_colorido",
        "tipo_mensagem",
        "cliente_telefone",
        "id_hash_msg",
        "received_data_hora",
        "retry_count",
        "next_attempt_at",
        "erro_resumido",
    )

    search_fields = (
        "cliente_telefone",
        "id_hash_msg",
        "id_conversa__id_conversa",
    )

    list_filter = (
        "status",
        "tipo_mensagem",
        "id_conversa",
    )

    ordering = ("-received_data_hora",)
    date_hierarchy = "received_data_hora"

    list_per_page = 50
    empty_value_display = "-"

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("id_conversa")

    def status_colorido(self, obj):
        cores = {
            "sent": "green",
            "failed": "red",
            "pending": "#555",
            "processing": "orange",
        }
        cor = cores.get(obj.status, "#000")
        return format_html('<b style="color:{};">{}</b>', cor, obj.status)

    status_colorido.short_description = "Status"

    def erro_resumido(self, obj):
        if not obj.last_error:
            return "-"

        texto = obj.last_error[:60]

        return format_html(
            '<span title="{}">{}</span>',
            obj.last_error,
            texto + ("..." if len(obj.last_error) > 60 else ""),
        )

    erro_resumido.short_description = "Erro"


@admin.register(HistoricoMensagens)
class HistoricoMensagensAdmin(SomenteVisualizacaoAdminMixin, admin.ModelAdmin):

    list_display = (
        "id_mensagem",
        "quem_enviou",
        "tipo_mensagem",
        "status_envio",
        "id_conversa",
        "id_etapa",
        "id_mensagem_fila",
        "id_hash_cliente_origem",
        "cliente_telefone",
        "received_data_hora",
    )

    search_fields = (
        "cliente_telefone",
        "id_hash_msg",
        "id_hash_cliente_origem",
        "id_mensagem_fila__id_mensagem",
    )

    list_filter = (
        "quem_enviou",
        "status_envio",
        "id_etapa",
        "tipo_mensagem",
    )

    ordering = ("-received_data_hora",)

    date_hierarchy = "received_data_hora"
    list_per_page = 50

    empty_value_display = "-"

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related(
            "id_conversa",
            "id_etapa",
            "id_mensagem_fila",
        )


@admin.register(RespostasDesafios)
class RespostasDesafiosAdmin(SomenteVisualizacaoAdminMixin, admin.ModelAdmin):

    list_display = (
        "id_resposta_desafio",
        "id_conversa",
        "id_etapa",
        "resposta",
        "id_historico_mensagem_cliente",
        "criado_em",
    )

    search_fields = (
        "resposta",
    )

    list_filter = (
        "id_etapa",
    )

    ordering = ("-criado_em",)
    date_hierarchy = "criado_em"
    list_per_page = 50
    empty_value_display = "-"

    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            "id_conversa",
            "id_etapa",
        )


@admin.register(WebhookFloodEvento)
class WebhookFloodEventoAdmin(SomenteVisualizacaoAdminMixin, admin.ModelAdmin):

    list_display = (
        "id_evento",
        "wa_id_cliente",
        "phone_id_unidade",
        "id_hash_msg",
        "received_at",
    )

    search_fields = (
        "wa_id_cliente",
        "phone_id_unidade",
        "id_hash_msg",
    )

    list_filter = ("phone_id_unidade",)
    ordering = ("-received_at",)
    date_hierarchy = "received_at"
    list_per_page = 50
    empty_value_display = "-"


@admin.register(CacheControle)
class CacheControleAdmin(SomenteVisualizacaoAdminMixin, admin.ModelAdmin):

    list_display = (
        "nome",
        "versao",
        "atualizado_em",
    )

    search_fields = ("nome",)
    ordering = ("nome",)
    list_per_page = 50
    empty_value_display = "-"


@admin.register(ClienteBloqueadoMeta)
class ClienteBloqueadoMetaAdmin(admin.ModelAdmin):

    list_display = (
        "id_bloqueio",
        "cliente_link",
        "wa_id_cliente",
        "id_unidade",
        "phone_id_unidade",
    )

    search_fields = (
        "wa_id_cliente",
        "phone_id_unidade",
        "id_cliente__waid_telefone",
        "id_cliente__nome",
        "id_unidade__nome",
    )

    list_filter = ("id_unidade",)
    ordering = ("wa_id_cliente", "id_unidade__nome")
    list_per_page = 50
    empty_value_display = "-"

    def has_add_permission(self, request):
        return False

    def get_actions(self, request):
        actions = super().get_actions(request)
        actions.pop("delete_selected", None)
        return actions

    def get_readonly_fields(self, request, obj=None):
        return [field.name for field in self.model._meta.fields]

    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            "id_cliente",
            "id_unidade",
        )

    def delete_view(self, request, object_id, extra_context=None):
        if request.method == "POST":
            obj = self.get_object(request, object_id)

            if obj and not self._desbloquear_meta_antes_de_excluir(request, obj):
                return HttpResponseRedirect(
                    reverse(
                        "admin:webhook_clientebloqueadometa_change",
                        args=[object_id],
                    )
                )

        return super().delete_view(request, object_id, extra_context)

    def delete_model(self, request, obj):
        logger.warning(
            "admin_bloqueio_meta_excluido | acao=excluir_registro usuario=%s wa_id_cliente=%s phone_id_unidade=%s",
            request.user,
            short_value(obj.wa_id_cliente),
            short_value(obj.phone_id_unidade),
        )
        super().delete_model(request, obj)

    def delete_queryset(self, request, queryset):
        logger.warning(
            "admin_bloqueio_meta_exclusao_massa_bloqueada | acao=manter_registros usuario=%s total=%s",
            request.user,
            queryset.count(),
        )
        self.message_user(
            request,
            "Exclusao em massa desativada. Desbloqueie um cliente por unidade de cada vez.",
            level=messages.ERROR,
        )

    def cliente_link(self, obj):
        if not obj.id_cliente:
            return "-"

        try:
            url = reverse(
                "admin:webhook_cliente_change",
                args=[obj.id_cliente.id_cliente],
            )
            return format_html(
                '<a href="{}">{}</a>',
                url,
                obj.id_cliente.nome or obj.id_cliente.waid_telefone,
            )
        except Exception:
            return obj.id_cliente.nome or obj.id_cliente.waid_telefone

    cliente_link.short_description = "Cliente"

    def _desbloquear_meta_antes_de_excluir(self, request, obj):
        try:
            desbloquear_usuario_meta(obj.wa_id_cliente, obj.phone_id_unidade)

            logger.warning(
                "admin_cliente_desbloqueado_meta | acao=desbloquear_meta_antes_excluir usuario=%s wa_id_cliente=%s phone_id_unidade=%s",
                request.user,
                short_value(obj.wa_id_cliente),
                short_value(obj.phone_id_unidade),
            )

            self.message_user(
                request,
                f"Cliente {obj.wa_id_cliente} desbloqueado na Meta. Registro removido do banco.",
                level=messages.SUCCESS,
            )
            return True

        except Exception as exc:
            logger.exception(
                "admin_desbloqueio_meta_falhou | acao=manter_registro usuario=%s wa_id_cliente=%s phone_id_unidade=%s erro=%s",
                request.user,
                short_value(obj.wa_id_cliente),
                short_value(obj.phone_id_unidade),
                exc,
            )
            self.message_user(
                request,
                f"Falha ao desbloquear na Meta. Registro mantido no banco: {exc}",
                level=messages.ERROR,
            )
            return False
```

## Etapa 16 - Remover `block.py`

Arquivo removido: `core/integrations/whatsapp/block.py`

Motivo: webhook e Django Admin passam a importar diretamente de
`pywa_functions/usuarios.py`; o arquivo deixa de possuir qualquer
responsabilidade.

## Etapa 17 - Remover `sender.py`

Arquivo removido: `core/integrations/whatsapp/sender.py`

Motivo: a implementação completa passa a existir em
`pywa_functions/etapas.py`, e o único import de produção será atualizado na
Etapa 11.

## Etapa 18 - Remover `sender_tratamento.py`

Arquivo removido: `core/integrations/whatsapp/sender_tratamento.py`

Motivo: a implementação completa passa a existir em
`pywa_functions/tratamentos.py`, e o único import de produção será atualizado na
Etapa 12.

## Etapa 19 - Remover `messages/senders.py`

Arquivo removido: `core/integrations/whatsapp/messages/senders.py`

Motivo: a pasta `messages` não pode importar PyWa nem enviar mensagens. As
primitivas passam para `pywa_functions/envios.py`.

## Etapa 20 - Remover `tools/conta.py`

Arquivo removido: `core/integrations/whatsapp/tools/conta.py`

Motivo: criação do cliente PyWa não é uma ferramenta administrativa. A função
passa para `pywa_functions/cliente.py`.

## Etapa 21 - Alterar `test_sender_etapa1.py`

Arquivo: `tests/unit/test_sender_etapa1.py`

```python
import unittest
from datetime import datetime
from unittest.mock import patch

from core.integrations.whatsapp.exceptions import ErroEnvioMeta
from core.integrations.whatsapp.pywa_functions import etapas as sender_module


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

## Etapa 22 - Alterar `test_flow_treat_unsupported_type.py`

Arquivo: `tests/unit/test_flow_treat_unsupported_type.py`

```python
import unittest
from unittest.mock import patch

from workers.worker_flow.response_flow import (
    flow_treat_unsupported_type as flow_treat_unsupported_type_module,
)


def contexto_historico_base(resposta_bot=None, id_etapa_atual=1):
    return {
        "id_conversa": 10,
        "retry_count": 1,
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
            conversa_nova,
        ):
            chamadas.append((
                cliente_telefone,
                phone_id_unidade,
                id_etapa,
                tipo_mensagem,
                conversa_nova,
            ))
            return {
                "enviou": True,
                "resposta_ja_existia": False,
                "mensagem_bot": "mensagem de tratamento",
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

        self.assertEqual(
            chamadas,
            [("5571999999999", "123456", 1, "image", False)],
        )
        self.assertTrue(resultado["enviou"])
        self.assertTrue(resultado["tratamento"])
        self.assertFalse(resultado["atualizar_conversa"])

    def test_tipo_nao_suportado_em_conversa_nova_informa_sender(self):
        chamadas = []

        def fake_sender(
            cliente_telefone,
            phone_id_unidade,
            id_etapa,
            tipo_mensagem,
            conversa_nova,
        ):
            chamadas.append(conversa_nova)
            return {
                "enviou": True,
                "resposta_ja_existia": False,
                "mensagem_bot": "mensagem inicial",
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

        self.assertEqual(chamadas, [True])
        self.assertEqual(resultado["id_etapa_resultante"], 1)


if __name__ == "__main__":
    unittest.main()
```

## Etapa 23 - Criar `test_whatsapp_structure.py`

Arquivo: `tests/unit/test_whatsapp_structure.py`

```python
import ast
import unittest
from pathlib import Path

from core.integrations.whatsapp.messages.etapas import TITULO_BOTAO_ETAPA_1
from core.integrations.whatsapp.messages.tratamentos import (
    TITULO_BOTAO_CONTINUAR,
)


RAIZ_PROJETO = Path(__file__).resolve().parents[2]
RAIZ_WHATSAPP = RAIZ_PROJETO / "core" / "integrations" / "whatsapp"
RAIZ_PYWA = RAIZ_WHATSAPP / "pywa_functions"

RAIZES_PRODUCAO = (
    RAIZ_PROJETO / "core",
    RAIZ_PROJETO / "workers",
    RAIZ_PROJETO / "callback",
)

METODOS_PYWA = {
    "send_message",
    "block_users",
    "unblock_users",
    "get_blocked_users",
}

TEXTOS_WHATSAPP = (
    "Ola! Vi que voce iniciou o atendimento com uma midia.",
    "Recebi uma midia, mas nesta etapa eu preciso que voce responda por texto",
)


def arquivos_python_producao():
    for raiz in RAIZES_PRODUCAO:
        yield from raiz.rglob("*.py")


def esta_em_pywa_functions(arquivo):
    try:
        arquivo.relative_to(RAIZ_PYWA)
        return True
    except ValueError:
        return False


class WhatsappStructureTests(unittest.TestCase):
    def test_imports_e_chamadas_pywa_ficam_em_pywa_functions(self):
        violacoes = []

        for arquivo in arquivos_python_producao():
            if esta_em_pywa_functions(arquivo):
                continue

            arvore = ast.parse(arquivo.read_text(encoding="utf-8"))

            for no in ast.walk(arvore):
                if isinstance(no, ast.Import):
                    if any(alias.name == "pywa" or alias.name.startswith("pywa.") for alias in no.names):
                        violacoes.append(f"{arquivo}:{no.lineno}: import pywa")

                if isinstance(no, ast.ImportFrom):
                    modulo = no.module or ""
                    if modulo == "pywa" or modulo.startswith("pywa."):
                        violacoes.append(f"{arquivo}:{no.lineno}: from pywa")

                if isinstance(no, ast.Call) and isinstance(no.func, ast.Attribute):
                    if no.func.attr in METODOS_PYWA:
                        violacoes.append(
                            f"{arquivo}:{no.lineno}: chamada {no.func.attr}"
                        )

        self.assertEqual(violacoes, [])

    def test_textos_de_saida_ficam_em_messages(self):
        violacoes = []

        for arquivo in arquivos_python_producao():
            if arquivo.is_relative_to(RAIZ_WHATSAPP / "messages"):
                continue

            conteudo = arquivo.read_text(encoding="utf-8")
            for texto in TEXTOS_WHATSAPP:
                if texto in conteudo:
                    violacoes.append(f"{arquivo}: {texto}")

        self.assertEqual(violacoes, [])

    def test_titulos_de_botao_respeitam_limite_da_meta(self):
        for titulo in (TITULO_BOTAO_ETAPA_1, TITULO_BOTAO_CONTINUAR):
            with self.subTest(titulo=titulo):
                self.assertGreaterEqual(len(titulo), 1)
                self.assertLessEqual(len(titulo), 20)


if __name__ == "__main__":
    unittest.main()
```

## Etapa 24 - Alterar `test_sender_tratamento.py`

Arquivo: `tests/unit/test_sender_tratamento.py`

```python
import unittest
from unittest.mock import patch

from core.integrations.whatsapp.exceptions import ErroEnvioMeta
from core.integrations.whatsapp.messages.tratamentos import (
    MENSAGEM_MIDIA_ETAPA,
    MENSAGEM_MIDIA_INICIO,
)
from core.integrations.whatsapp.pywa_functions import (
    tratamentos as sender_tratamento_module,
)


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
                conversa_nova=False,
            )

        self.assertEqual(len(chamadas), 1)
        self.assertEqual(chamadas[0][0], "5571999999999")
        self.assertEqual(chamadas[0][1], MENSAGEM_MIDIA_ETAPA)
        self.assertEqual(chamadas[0][2], "Continuar")
        self.assertLessEqual(len(chamadas[0][2]), 20)
        self.assertEqual(chamadas[0][3], "123456")
        self.assertEqual(chamadas[0][4], "retornar_atendimento")
        self.assertTrue(resultado["enviou"])
        self.assertTrue(resultado["tratamento"])
        self.assertFalse(resultado["atualizar_conversa"])
        self.assertEqual(resultado["id_hash_msg_bot"], "wamid.bot.tratamento")
        self.assertEqual(resultado["id_etapa_resultante"], 1)

    def test_sender_tipo_nao_suportado_em_conversa_nova_usa_mensagem_inicial(self):
        chamadas = []

        def fake_enviar(*_args, **kwargs):
            chamadas.append(kwargs["text"])
            return "wamid.bot.inicio"

        with patch.object(
            sender_tratamento_module,
            "enviar_mensagem_texto_com_botao",
            fake_enviar,
        ):
            resultado = sender_tratamento_module.sender_tratamento_tipo_nao_suportado(
                cliente_telefone="5571999999999",
                phone_id_unidade="123456",
                id_etapa=1,
                tipo_mensagem="image",
                conversa_nova=True,
            )

        self.assertEqual(chamadas, [MENSAGEM_MIDIA_INICIO])
        self.assertEqual(resultado["mensagem_bot"], MENSAGEM_MIDIA_INICIO)

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
                    conversa_nova=False,
                )

        self.assertEqual(ctx.exception.id_etapa, 1)
        self.assertEqual(ctx.exception.cliente_telefone, "5571999999999")
        self.assertEqual(ctx.exception.phone_id_unidade, "123456")


if __name__ == "__main__":
    unittest.main()
```

## Etapa 25 - Alterar `test_whatsapp_message_senders.py`

Arquivo: `tests/unit/test_whatsapp_message_senders.py`

```python
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from core.integrations.whatsapp.pywa_functions import envios as senders_module


class FakeClienteWa:
    def __init__(self):
        self.calls = []

    def send_message(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(id="wamid.bot.fake")


class WhatsappMessageSendersTests(unittest.TestCase):
    def test_enviar_mensagem_texto_com_botao_monta_button_pywa(self):
        cliente_wa = FakeClienteWa()

        with patch.object(senders_module, "conta_wa", return_value=cliente_wa):
            id_hash = senders_module.enviar_mensagem_texto_com_botao(
                to="5571999999999",
                text="Ola!",
                titulo_botao="Aperte em mim",
                phone_id_unidade="123456",
            )

        self.assertEqual(id_hash, "wamid.bot.fake")
        self.assertEqual(len(cliente_wa.calls), 1)

        chamada = cliente_wa.calls[0]
        self.assertEqual(chamada["to"], "5571999999999")
        self.assertEqual(chamada["text"], "Ola!")
        self.assertEqual(len(chamada["buttons"]), 1)

        botao = chamada["buttons"][0]
        self.assertEqual(botao.title, "Aperte em mim")
        self.assertEqual(botao.callback_data, "Aperte em mim")


if __name__ == "__main__":
    unittest.main()
```

## Ordem de aplicação

As etapas devem ser aplicadas nesta sequência:

1. Criar `messages` e `pywa_functions` (Etapas 1 a 8).
2. Atualizar documentação, worker e relatório (Etapas 9 a 13).
3. Atualizar webhook e Django Admin (Etapas 14 e 15).
4. Remover implementações antigas (Etapas 16 a 20).
5. Atualizar e criar testes (Etapas 21 a 25).

## Verificações após a implementação

```powershell
python -m unittest tests.unit.test_sender_etapa1 -v
python -m unittest tests.unit.test_sender_tratamento -v
python -m unittest tests.unit.test_whatsapp_message_senders -v
python -m unittest tests.unit.test_flow_sender -v
python -m unittest tests.unit.test_flow_treat_unsupported_type -v
python -m unittest tests.unit.test_valida_resposta_cliente -v
python -m unittest tests.unit.test_whatsapp_structure -v
python -m unittest discover -s tests -v
python -m compileall core workers callback tests
python callback/manage.py check
git diff --check
```

## Contratos preservados

- textos, callbacks e títulos atuais;
- limite de 20 caracteres dos botões;
- escolha entre mensagem inicial e mensagem de conversa em andamento;
- `id_etapa_resultante`, `tipo_mensagem`, `canal` e contexto retornado;
- `atualizar_conversa=False` e `atualizar_last_from_bot=True` nos tratamentos;
- idempotência por histórico;
- fluxo A/B/C, retries, locks, commits e rollbacks;
- comportamento Meta-first de bloqueio e desbloqueio;
- logs e `ErroEnvioMeta` nas falhas de envio.

## Fora do escopo

- mudar regras de negócio;
- alterar textos enviados ao cliente;
- adicionar novas etapas ou tratamentos;
- mover credenciais ou alterar configuração de deploy;
- alterar versão da Meta ou da PyWa;
- qualquer alteração em banco, Redis, fila ou transações.
