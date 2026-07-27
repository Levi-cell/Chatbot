# Plano de proteção contra bots e IAs por falta de avanço

## 1. Objetivo e escopo

Este documento descreve uma implementação futura, ainda não aplicada, para
interromper loops entre o chatbot e outro atendimento automatizado.

A regra aprovada é deliberadamente simples:

1. cada conversa começa com `turnos_sem_avanco = 0`;
2. uma resposta de tratamento nova, sem avanço de etapa, incrementa
   `turnos_sem_avanco`;
3. qualquer transição válida de etapa zera `turnos_sem_avanco`;
4. `turnos_sem_avanco` é limitado a `12`;
5. quando uma nova mensagem chega e a conversa ativa já está com
   `turnos_sem_avanco = 12`,
   o webhook:
   - registra primeiro a intenção em `cliente_bloqueado_meta`;
   - confirma o commit no PostgreSQL;
   - tenta bloquear o número na Meta;
   - ignora a mensagem, tenha a Meta aceitado ou recusado o bloqueio;
6. enquanto a linha permanecer em `cliente_bloqueado_meta`, toda nova mensagem
   provocará outra tentativa de bloqueio na Meta e continuará sendo ignorada.

Não serão adicionados ao caminho automático do webhook/worker nesta versão:

- classificador de IA em tempo real;
- análise semântica em tempo real;
- score usado para bloquear automaticamente;
- quarentena;
- desafio “sou humano”;
- dependência de Redis para `turnos_sem_avanco`;
- bloqueio baseado apenas em conta Business, nome, URL ou velocidade.

O plano inclui, separadamente, um relatório manual e somente leitura com score
explicável de suspeita. Esse utilitário roda apenas quando o desenvolvedor o
executar, não é importado pelos serviços e nunca bloqueia, grava ou altera
clientes.

A premissa operacional é que uma IA de atendimento normalmente precisa de um
gatilho, lista de leads, integração ou número previamente conhecido para iniciar
uma conversa. Como o número do chatbot não será publicado em formulários de
captação, a chance de uma automação inteligente iniciar contato aleatório é
baixa, mas não é zero: listas erradas, números reciclados, campanhas antigas e
robôs de prospecção ainda podem alcançá-lo. Por isso, a proteção automática
trata o risco mais provável e caro — o loop sem avanço — e o relatório manual
serve para investigar automações que consigam avançar pelo fluxo.

## 2. Semântica exata

`turnos_sem_avanco` pertence à `chatbot.conversa`, e não ao cliente global.

Isso preserva o isolamento multi-WABA:

```text
Cliente A + unidade A -> conversa e contador próprios
Cliente A + unidade B -> outra conversa e outro contador
Cliente B + unidade A -> outra conversa e outro contador
```

Uma conversa nova começa novamente em zero. Uma conversa encerrada não é
consultada pelo guard.

Exemplo:

```text
tratamento na etapa 4 -> 1
tratamento na etapa 4 -> 2
tratamento na etapa 4 -> 3
tratamento na etapa 4 -> 4
tratamento na etapa 4 -> 5
resposta válida: etapa 4 -> etapa 5 -> 0
tratamento na etapa 5 -> 1
```

Se o décimo segundo tratamento for persistido, `turnos_sem_avanco` passa a
`12` junto com a resposta do bot. Quando a próxima mensagem chegar, o webhook
bloqueará o número remetente para aquela unidade e ignorará essa mensagem sem
colocá-la na fila. Portanto, não existe uma décima terceira resposta de
tratamento.

## 3. Garantias transacionais

- O worker incrementa somente quando uma nova resposta do bot foi realmente
  inserida no histórico (`historico_bot_inserido=True`).
- Um retry que recupera uma resposta já persistida não incrementa novamente.
- Incremento, reset, histórico do bot, movimento da conversa e efeitos da
  transição participam da mesma transação do worker.
- Se a transação falhar, todas essas alterações sofrem rollback juntas.
- O reset de uma transição é idempotente: reaplicá-lo mantém o valor zero.
- O webhook persiste a denylist local antes da chamada externa à Meta.
- Nenhuma chamada à Meta fica dentro da transação do PostgreSQL.
- Se o banco falhar antes de registrar o bloqueio, o webhook retorna HTTP 503,
  não chama a Meta e não enfileira a mensagem.
- Se a Meta recusar o bloqueio, a linha local permanece e a mensagem continua
  ignorada.

O reset será centralizado em `atualizar_banco_com_contexto_final`, logo depois
de `persistir_movimento_conversa`. Ele não deve ser colocado apenas em
`atualizar_banco_conforme_transicao_de_etapa`, porque nem toda transição possui
um efeito de domínio específico, mas toda transição válida precisa zerar o
campo `turnos_sem_avanco`.

## 4. Estado já preparado antes deste plano

O projeto já possui a base necessária:

- `cliente_bloqueado_meta` funciona como denylist local persistente;
- mensagens de um par presente nessa tabela são ignoradas;
- toda nova mensagem de um número marcado para bloqueio provoca outra tentativa
  de bloqueio na Meta;
- a falha da Meta não libera o contato localmente;
- o bloqueio por flood persiste primeiro no banco e só depois chama a Meta;
- o isolamento usa `wa_id_cliente + phone_id_unidade`;
- o nome do contato pode ser armazenado como dado opcional.

O núcleo automático dos passos abaixo implementa `turnos_sem_avanco`, com
limite 12, e sua promoção para essa denylist. Os Passos especiais 0 e 0B são
correções independentes de robustez do webhook. O relatório manual é uma
ferramenta offline de diagnóstico e não participa do atendimento.

---

## Passo especial 0 — contar somente WAMIDs únicos no anti-flood

Este passo corrige uma fragilidade independente do contador de turnos sem
avanço.
Ele não troca o Redis pelo PostgreSQL e não altera o limite aprovado de
`15 mensagens distintas em 5 segundos`.

A semântica final será:

- uma mensagem nova, com WAMID novo, conta uma vez;
- uma reentrega do mesmo WAMID dentro da janela de deduplicação de duas horas
  não aumenta o contador;
- quinze WAMIDs diferentes continuam caracterizando flood;
- os contadores continuam isolados por
  `wa_id_cliente + phone_id_unidade`;
- se o Redis falhar, o PostgreSQL continua sendo o primeiro fallback;
- se Redis e PostgreSQL falharem, o fallback em memória também deduplica por
  WAMID;
- a persistência da denylist, o bloqueio na Meta e os códigos HTTP não mudam.

O PostgreSQL já está preparado: `chatbot.webhook_flood_evento.id_hash_msg` é
único e `registrar_evento_flood_banco()` usa
`ON CONFLICT (id_hash_msg) DO NOTHING`. Portanto, nenhum DDL nem repositório
SQL deve ser alterado neste passo.

O WAMID emitido pela Meta é tratado como identificador globalmente único. Por
isso há uma diferença intencional apenas na chave de deduplicação: Redis e
memória incluem o par `wa_id_cliente + phone_id_unidade`, enquanto o fallback
PostgreSQL conserva a restrição global já existente em `id_hash_msg`. Em todos
os caminhos, a consulta do contador de flood continua isolada pelo par.

O fallback em memória é estritamente degradado e local a cada processo
Gunicorn; ele não oferece coordenação distribuída. Além disso, no fluxo do
webhook ele só pode ser alcançado depois que a consulta inicial da denylist já
conseguiu acessar o banco e, mais tarde no mesmo evento, Redis e PostgreSQL
falharam na avaliação do flood.

### Arquivo completo: `core/cache/runtime/cache_flood_redis.py`

Substituir o conteúdo completo por:

```python
import hashlib
import logging
import time

from core.cache.redis_client import get_redis_safe
from core.logging_config import short_value


logger = logging.getLogger("cache.bloqueio_meta")

RATE_PREFIX = "webhook_flood_rate"
DEDUPLICACAO_TTL_SEGUNDOS = 2 * 60 * 60

_AVALIAR_FLOOD_LUA = """
local dedupe_key = KEYS[1]
local dedupe_ttl = tonumber(ARGV[1])
local evento_novo = redis.call(
    "SET",
    dedupe_key,
    "1",
    "NX",
    "EX",
    dedupe_ttl
)
local resposta = {}

if evento_novo then
    table.insert(resposta, 1)
else
    table.insert(resposta, 0)
end

for indice = 2, #KEYS do
    local total

    if evento_novo then
        total = redis.call("INCR", KEYS[indice])

        if total == 1 then
            redis.call(
                "EXPIRE",
                KEYS[indice],
                tonumber(ARGV[indice])
            )
        end
    else
        total = tonumber(
            redis.call("GET", KEYS[indice]) or "0"
        )
    end

    table.insert(resposta, total)
end

return resposta
"""


def avaliar_flood_redis(
    wa_id_cliente,
    phone_id_unidade,
    id_hash_msg,
    regras,
):
    if (
        not wa_id_cliente
        or not phone_id_unidade
        or not id_hash_msg
        or not regras
    ):
        return {
            "redis_ok": True,
            "bloqueado": False,
            "flood": False,
            "total": 0,
            "motivo": "dados_invalidos",
            "regra": None,
            "evento_novo": False,
        }

    try:
        redis = get_redis_safe(
            retries=1,
            delay=0,
            validate=False,
        )
        agora = time.time()
        digest_par = _digest_par(
            wa_id_cliente,
            phone_id_unidade,
        )
        digest_wamid = _digest_wamid(id_hash_msg)
        chaves = [
            _dedupe_key(digest_par, digest_wamid),
        ]
        argumentos = [
            DEDUPLICACAO_TTL_SEGUNDOS,
        ]

        for regra in regras:
            janela_segundos = regra["janela_segundos"]
            janela = int(agora // janela_segundos)
            chaves.append(
                _rate_key(
                    digest_par,
                    janela_segundos,
                    janela,
                )
            )
            argumentos.append(
                janela_segundos + 10,
            )

        # A deduplicação e todos os incrementos são uma única operação
        # atômica. Duas entregas concorrentes do mesmo WAMID não conseguem
        # vencer o SET NX ao mesmo tempo.
        resultados = redis.eval(
            _AVALIAR_FLOOD_LUA,
            len(chaves),
            *chaves,
            *argumentos,
        )
        maior_total = 0
        evento_novo = bool(resultados[0])

        for indice, regra in enumerate(
            regras,
            start=1,
        ):
            total = int(resultados[indice])
            maior_total = max(maior_total, total)

            if total >= regra["limite"]:
                return {
                    "redis_ok": True,
                    "bloqueado": False,
                    "flood": True,
                    "total": total,
                    "limite": regra["limite"],
                    "janela_segundos": regra["janela_segundos"],
                    "motivo": "redis",
                    "regra": regra["nome"],
                    "evento_novo": evento_novo,
                }

        return {
            "redis_ok": True,
            "bloqueado": False,
            "flood": False,
            "total": maior_total,
            "motivo": "redis",
            "regra": None,
            "evento_novo": evento_novo,
        }

    except Exception as exc:
        logger.warning(
            "rate_limit_redis_falhou | "
            "acao=fallback_banco wa_id_cliente=%s "
            "phone_id_unidade=%s id_hash_msg=%s erro=%s",
            short_value(wa_id_cliente),
            short_value(phone_id_unidade),
            short_value(id_hash_msg),
            exc,
        )
        return {
            "redis_ok": False,
            "bloqueado": False,
            "flood": False,
            "total": 0,
            "motivo": "redis_indisponivel",
            "regra": None,
            "evento_novo": False,
        }


def _dedupe_key(digest_par, digest_wamid):
    return (
        f"{RATE_PREFIX}:{{{digest_par}}}:"
        f"wamid:{digest_wamid}"
    )


def _rate_key(digest_par, janela_segundos, janela):
    return (
        f"{RATE_PREFIX}:{{{digest_par}}}:"
        f"contador:{janela_segundos}:{janela}"
    )


def _digest_par(wa_id_cliente, phone_id_unidade):
    wa_id_cliente = _normalizar(wa_id_cliente)
    phone_id_unidade = _normalizar(phone_id_unidade)

    if not wa_id_cliente or not phone_id_unidade:
        return None

    raw = f"{phone_id_unidade}:{wa_id_cliente}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _digest_wamid(id_hash_msg):
    id_hash_msg = _normalizar(id_hash_msg)

    if not id_hash_msg:
        return None

    return hashlib.sha256(
        id_hash_msg.encode("utf-8")
    ).hexdigest()


def _normalizar(valor):
    if valor is None:
        return None

    texto = str(valor).strip()
    return texto or None
```

O script Lua preserva a janela fixa já existente e executa atomicamente:

1. `SET NX` da chave de deduplicação por duas horas;
2. `INCR` apenas quando o WAMID ainda não foi visto;
3. leitura do contador sem incremento quando for uma reentrega;
4. TTL dos contadores.

As chaves do mesmo par usam a mesma hash tag Redis (`{digest_par}`), portanto
continuam compatíveis caso o Redis remoto passe a operar em cluster. Todas as
chaves permanecem sob `webhook_flood_rate:*`. Por isso
`core/cache/cache_reset.py` já continuará removendo tanto o formato antigo
quanto o novo, sem qualquer alteração.

### Arquivo completo: `core/cache/cache_flood_memoria.py`

Substituir o conteúdo completo por:

```python
import hashlib
import logging
import threading
import time
from collections import OrderedDict

from core.logging_config import short_value


logger = logging.getLogger("cache.flood_memoria")

MAX_CHAVES_MEMORIA = 1000
MAX_WAMIDS_POR_PAR_MEMORIA = 200
LIMPEZA_INTERVALO_SEGUNDOS = 60
DEDUPLICACAO_TTL_SEGUNDOS = 2 * 60 * 60

_lock = threading.Lock()
_eventos_por_chave = OrderedDict()
_ultima_limpeza = 0.0


def avaliar_flood_memoria(
    wa_id_cliente,
    phone_id_unidade,
    id_hash_msg,
    regras,
):
    if (
        not wa_id_cliente
        or not phone_id_unidade
        or not id_hash_msg
        or not regras
    ):
        return {
            "memoria_ok": True,
            "flood": False,
            "total": 0,
            "motivo": "dados_invalidos",
            "regra": None,
            "evento_novo": False,
        }

    agora = time.monotonic()
    chave = _cache_key(
        wa_id_cliente,
        phone_id_unidade,
    )
    membro_wamid = _digest_wamid(id_hash_msg)

    with _lock:
        _limpar_chaves_expiradas(agora, regras)

        eventos = _eventos_por_chave.get(chave)

        if eventos is None:
            eventos = OrderedDict()
            _eventos_por_chave[chave] = eventos

        _remover_eventos_antigos(
            eventos,
            agora,
            DEDUPLICACAO_TTL_SEGUNDOS,
        )

        evento_novo = membro_wamid not in eventos

        if evento_novo:
            eventos[membro_wamid] = agora
            _limitar_wamids_por_par(eventos)

        _eventos_por_chave.move_to_end(chave)
        _limitar_total_chaves()
        maior_total = 0

        for regra in regras:
            total = _contar_eventos_na_janela(
                eventos,
                agora,
                regra["janela_segundos"],
            )
            maior_total = max(maior_total, total)

            if total >= regra["limite"]:
                logger.warning(
                    "rate_limit_memoria_estourou | "
                    "acao=detectar_flood wa_id_cliente=%s "
                    "phone_id_unidade=%s regra=%s total=%s "
                    "limite=%s janela=%s evento_novo=%s",
                    short_value(wa_id_cliente),
                    short_value(phone_id_unidade),
                    regra["nome"],
                    total,
                    regra["limite"],
                    regra["janela_segundos"],
                    evento_novo,
                )
                return {
                    "memoria_ok": True,
                    "flood": True,
                    "total": total,
                    "limite": regra["limite"],
                    "janela_segundos": regra["janela_segundos"],
                    "motivo": "memoria",
                    "regra": regra["nome"],
                    "evento_novo": evento_novo,
                }

        return {
            "memoria_ok": True,
            "flood": False,
            "total": maior_total,
            "motivo": "memoria",
            "regra": None,
            "evento_novo": evento_novo,
        }


def _cache_key(wa_id_cliente, phone_id_unidade):
    return (
        f"{str(phone_id_unidade).strip()}:"
        f"{str(wa_id_cliente).strip()}"
    )


def _digest_wamid(id_hash_msg):
    return hashlib.sha256(
        str(id_hash_msg).strip().encode("utf-8")
    ).hexdigest()


def _contar_eventos_na_janela(
    eventos,
    agora,
    janela_segundos,
):
    inicio_janela = agora - janela_segundos
    return sum(
        1
        for instante in eventos.values()
        if instante >= inicio_janela
    )


def _remover_eventos_antigos(
    eventos,
    agora,
    janela_segundos,
):
    limite = agora - janela_segundos

    while eventos:
        _wamid, instante = next(iter(eventos.items()))

        if instante >= limite:
            break

        eventos.popitem(last=False)


def _limpar_chaves_expiradas(agora, regras):
    global _ultima_limpeza

    if (
        agora - _ultima_limpeza
        < LIMPEZA_INTERVALO_SEGUNDOS
    ):
        return

    chaves_vazias = []

    for chave, eventos in _eventos_por_chave.items():
        _remover_eventos_antigos(
            eventos,
            agora,
            DEDUPLICACAO_TTL_SEGUNDOS,
        )

        if not eventos:
            chaves_vazias.append(chave)

    for chave in chaves_vazias:
        _eventos_por_chave.pop(chave, None)

    _ultima_limpeza = agora


def _limitar_total_chaves():
    while len(_eventos_por_chave) > MAX_CHAVES_MEMORIA:
        _eventos_por_chave.popitem(last=False)


def _limitar_wamids_por_par(eventos):
    while len(eventos) > MAX_WAMIDS_POR_PAR_MEMORIA:
        eventos.popitem(last=False)
```

Os limites permitem no máximo teórico 200 mil WAMIDs em um processo
(`1000 × 200`). Se um par ultrapassar 200 WAMIDs ainda dentro das duas horas, o
mais antigo é removido; uma reentrega tardia desse item pode voltar a contar.
Essa perda controlada de deduplicação é aceitável somente nesse último fallback
degradado, pois Redis e PostgreSQL permanecem como caminhos principais.

### Arquivo completo:
`callback/webhook/services/flood_guard.py`

Substituir o conteúdo completo por:

```python
import logging

from django.http import JsonResponse

from core.cache.runtime.cache_flood_redis import avaliar_flood_redis
from core.cache.cache_flood_memoria import avaliar_flood_memoria
from core.database.connection_aws import get_conn
from core.integrations.whatsapp.tools.usuarios import (
    bloquear_usuario_meta,
)
from core.logging_config import short_value
from core.repositories.seguranca.bloqueio_meta import (
    buscar_cliente_por_wa_id,
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
    nome_cliente = _extrair_nome_cliente(data)

    flood = bloquear_cliente_se_flood(
        wa_id_cliente,
        phone_id_unidade,
        id_hash_msg,
        nome_cliente=nome_cliente,
    )

    if not flood["bloqueado"]:
        return None

    logger.warning(
        "mensagem_ignorada | motivo=%s regra=%s "
        "acao=bloqueio_local_nao_enfileirar cliente=%s phone_number_id=%s "
        "total=%s persistencia_ok=%s meta_ok=%s",
        flood["motivo"],
        flood.get("regra"),
        short_value(wa_id_cliente),
        short_value(phone_id_unidade),
        flood["total"],
        flood.get("persistencia_ok"),
        flood.get("meta_ok"),
    )

    if flood.get("reentregar"):
        return JsonResponse(
            {
                "status": "unavailable",
                "reason": flood["motivo"],
            },
            status=503,
        )

    return JsonResponse({
        "status": "ignored",
        "reason": flood["motivo"],
    })


def bloquear_cliente_se_flood(
    wa_id_cliente,
    phone_id_unidade,
    id_hash_msg,
    nome_cliente=None,
):
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
        id_hash_msg,
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
                nome_cliente=nome_cliente,
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
            nome_cliente=nome_cliente,
        )

    if not rate_banco["banco_ok"]:
        rate_memoria = avaliar_flood_memoria(
            wa_id_cliente,
            phone_id_unidade,
            id_hash_msg,
            regras=REGRAS_FLOOD,
        )

        if rate_memoria["flood"]:
            return _bloquear_via_memoria_e_alertar(
                wa_id_cliente,
                phone_id_unidade,
                total=rate_memoria["total"],
                regra=rate_memoria["regra"],
                id_hash_msg=id_hash_msg,
                nome_cliente=nome_cliente,
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
    nome_cliente=None,
):
    resultado = _bloquear_e_registrar(
        wa_id_cliente,
        phone_id_unidade,
        origem="memoria",
        total=total,
        regra=regra,
        nome_cliente=nome_cliente,
    )

    registrar_alerta_flood_memoria(
        wa_id_cliente=wa_id_cliente,
        phone_id_unidade=phone_id_unidade,
        origem="memoria",
        regra=regra,
        total=total,
        meta_ok=resultado.get("meta_ok"),
        motivo=resultado["motivo"],
        id_hash_msg=id_hash_msg,
        erro_meta=resultado.get("erro_meta"),
    )

    logger.warning(
        "flood_bloqueado_memoria | acao=alertar regra=%s "
        "wa_id_cliente=%s phone_id_unidade=%s total=%s "
        "persistencia_ok=%s meta_ok=%s reentregar=%s",
        regra,
        short_value(wa_id_cliente),
        short_value(phone_id_unidade),
        total,
        resultado.get("persistencia_ok"),
        resultado.get("meta_ok"),
        resultado.get("reentregar"),
    )
    return resultado


def _bloquear_e_registrar(
    wa_id_cliente,
    phone_id_unidade,
    origem,
    total,
    regra,
    nome_cliente=None,
):
    dados_bloqueio = _buscar_dados_bloqueio(
        wa_id_cliente,
        phone_id_unidade,
        nome_cliente=nome_cliente,
    )

    if not dados_bloqueio["id_unidade"]:
        banco_indisponivel = (
            dados_bloqueio["motivo"] == "flood_banco_indisponivel"
        )
        motivo = (
            f"flood_{origem}_banco_indisponivel"
            if banco_indisponivel
            else f"flood_{origem}_unidade_nao_cadastrada"
        )
        logger.warning(
            "flood_detectado_sem_bloqueio_local | motivo=%s acao=%s "
            "origem=%s regra=%s wa_id_cliente=%s phone_id_unidade=%s total=%s",
            motivo,
            "retornar_503" if banco_indisponivel else "ignorar_phone_desconhecido",
            origem,
            regra,
            short_value(wa_id_cliente),
            short_value(phone_id_unidade),
            total,
        )
        return {
            "bloqueado": True,
            "motivo": motivo,
            "total": total,
            "regra": regra,
            "id_bloqueio": None,
            "id_cliente": dados_bloqueio["id_cliente"],
            "id_unidade": None,
            "persistencia_ok": False,
            "meta_ok": None,
            "erro_meta": None,
            "reentregar": banco_indisponivel,
        }

    id_bloqueio = _registrar_intencao_bloqueio_banco(
        dados_bloqueio["id_cliente"],
        dados_bloqueio["nome_cliente"],
        wa_id_cliente,
        dados_bloqueio["id_unidade"],
        dados_bloqueio["phone_id_unidade"],
    )

    if not id_bloqueio:
        logger.critical(
            "bloqueio_local_registro_falhou | "
            "motivo=banco_falhou acao=retornar_503_sem_chamar_meta "
            "wa_id_cliente=%s id_cliente=%s id_unidade=%s "
            "phone_id_unidade=%s",
            short_value(wa_id_cliente),
            dados_bloqueio["id_cliente"],
            dados_bloqueio["id_unidade"],
            short_value(dados_bloqueio["phone_id_unidade"]),
        )
        return {
            "bloqueado": True,
            "motivo": f"flood_{origem}_persistencia_local_falhou",
            "total": total,
            "regra": regra,
            "id_bloqueio": None,
            "id_cliente": dados_bloqueio["id_cliente"],
            "id_unidade": dados_bloqueio["id_unidade"],
            "persistencia_ok": False,
            "meta_ok": None,
            "erro_meta": None,
            "reentregar": True,
        }

    meta_ok = False
    erro_meta = None

    try:
        bloquear_usuario_meta(wa_id_cliente, phone_id_unidade)
        meta_ok = True

    except Exception as exc:
        erro_meta = str(exc)
        logger.exception(
            "bloqueio_meta_falhou | motivo=meta_indisponivel "
            "acao=manter_bloqueio_local_e_repetir_em_nova_mensagem "
            "origem=%s regra=%s wa_id_cliente=%s phone_id_unidade=%s "
            "total=%s id_bloqueio=%s erro=%s",
            origem,
            regra,
            short_value(wa_id_cliente),
            short_value(phone_id_unidade),
            total,
            id_bloqueio,
            exc,
        )

    motivo = (
        f"flood_{origem}"
        if meta_ok
        else f"flood_{origem}_meta_falhou"
    )

    logger.warning(
        "flood_bloqueado | acao=registrar_resultado origem=%s regra=%s "
        "wa_id_cliente=%s id_cliente=%s id_unidade=%s phone_id_unidade=%s "
        "total=%s id_bloqueio=%s meta_ok=%s erro_meta=%s",
        origem,
        regra,
        short_value(wa_id_cliente),
        dados_bloqueio["id_cliente"],
        dados_bloqueio["id_unidade"],
        short_value(dados_bloqueio["phone_id_unidade"]),
        total,
        id_bloqueio,
        meta_ok,
        erro_meta,
    )

    return {
        "bloqueado": True,
        "motivo": motivo,
        "total": total,
        "regra": regra,
        "id_bloqueio": id_bloqueio,
        "id_cliente": dados_bloqueio["id_cliente"],
        "id_unidade": dados_bloqueio["id_unidade"],
        "persistencia_ok": True,
        "meta_ok": meta_ok,
        "erro_meta": erro_meta,
        "reentregar": False,
    }


def _buscar_dados_bloqueio(
    wa_id_cliente,
    phone_id_unidade,
    nome_cliente=None,
):
    conn = None
    dados_vazios = {
        "id_cliente": None,
        "nome_cliente": _normalizar_nome_cliente(nome_cliente),
        "id_unidade": None,
        "phone_id_unidade": phone_id_unidade,
        "motivo": "dados_bloqueio_indisponiveis",
    }

    try:
        conn = get_conn(application_name="webhook_chatbot")
        cursor = conn.cursor()

        cliente = buscar_cliente_por_wa_id(wa_id_cliente, cursor)
        id_cliente = cliente[0] if cliente else None
        nome_cliente_banco = cliente[1] if cliente else None
        nome_bloqueio = (
            _normalizar_nome_cliente(nome_cliente_banco)
            or dados_vazios["nome_cliente"]
        )
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
                "nome_cliente": nome_bloqueio,
                "motivo": "flood_sem_unidade_cadastrada",
            }

        id_unidade, phone_id_cadastrado = unidade

        return {
            "id_cliente": id_cliente,
            "nome_cliente": nome_bloqueio,
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


def _registrar_intencao_bloqueio_banco(
    id_cliente,
    nome_cliente,
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
            nome_cliente=nome_cliente,
        )

        conn.commit()
        return id_bloqueio

    except Exception as exc:
        if conn:
            conn.rollback()

        logger.exception(
            "bloqueio_local_registro_banco_falhou | motivo=banco_indisponivel "
            "acao=nao_registrado wa_id_cliente=%s id_cliente=%s "
            "id_unidade=%s phone_id_unidade=%s erro=%s",
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


def _extrair_nome_cliente(data):
    value = data.get("entry", [{}])[0].get("changes", [{}])[0].get("value", {})
    contacts = value.get("contacts")

    if (
        not isinstance(contacts, list)
        or not contacts
        or not isinstance(contacts[0], dict)
    ):
        return None

    profile = contacts[0].get("profile")
    if not isinstance(profile, dict):
        return None

    return _normalizar_nome_cliente(profile.get("name"))


def _normalizar_nome_cliente(nome_cliente):
    if nome_cliente is None:
        return None

    nome_normalizado = str(nome_cliente).strip()
    return nome_normalizado[:200] or None


def _extrair_id_hash_msg(data):
    value = data.get("entry", [{}])[0].get("changes", [{}])[0].get("value", {})
    messages = value.get("messages", [{}])
    return messages[0].get("id") if messages else None

```

O arquivo final altera somente a assinatura das duas avaliações de cache para
repassar o WAMID. Todo o restante da lógica existente foi mantido. Em
especial, continuam preservados:

- Redis primeiro;
- PostgreSQL quando `redis_ok=False`;
- memória somente quando Redis e PostgreSQL falham;
- registro local da denylist antes da chamada à Meta;
- HTTP 503 quando a intenção de bloqueio não puder ser persistida;
- HTTP 200 ignorado quando a denylist já foi persistida, ainda que a Meta
  recuse o bloqueio.

### Arquivo de teste completo:
`tests/unit/test_cache_flood_wamid.py`

Criar:

```python
import unittest
from unittest.mock import patch

from callback.webhook.services import flood_guard
from core.cache import cache_flood_memoria
from core.cache.runtime import cache_flood_redis


REGRAS = (
    {
        "nome": "rajada_curta",
        "limite": 15,
        "janela_segundos": 5,
    },
)


class FakeRedis:
    def __init__(self, agora):
        self.agora = agora
        self.valores = {}
        self.expiracoes = {}
        self.expira_em = {}

    def eval(self, _script, numero_chaves, *chaves_e_argumentos):
        self._expirar_chaves()
        chaves = list(chaves_e_argumentos[:numero_chaves])
        argumentos = list(chaves_e_argumentos[numero_chaves:])
        dedupe_key = chaves[0]
        evento_novo = dedupe_key not in self.valores

        if evento_novo:
            self.valores[dedupe_key] = "1"
            self.expiracoes[dedupe_key] = int(argumentos[0])
            self.expira_em[dedupe_key] = (
                self.agora() + int(argumentos[0])
            )

        resultados = [1 if evento_novo else 0]

        for indice, contador_key in enumerate(
            chaves[1:],
            start=1,
        ):
            if evento_novo:
                total = int(
                    self.valores.get(contador_key, 0)
                ) + 1
                self.valores[contador_key] = total

                if total == 1:
                    self.expiracoes[contador_key] = int(
                        argumentos[indice]
                    )
                    self.expira_em[contador_key] = (
                        self.agora()
                        + int(argumentos[indice])
                    )

            else:
                total = int(
                    self.valores.get(contador_key, 0)
                )

            resultados.append(total)

        return resultados

    def _expirar_chaves(self):
        agora = self.agora()
        expiradas = [
            key
            for key, instante in self.expira_em.items()
            if instante <= agora
        ]

        for key in expiradas:
            self.valores.pop(key, None)
            self.expiracoes.pop(key, None)
            self.expira_em.pop(key, None)


class CacheFloodRedisWamidTests(unittest.TestCase):
    def setUp(self):
        self.agora = 1000.0
        self.redis = FakeRedis(
            agora=lambda: self.agora,
        )
        self.redis_patch = patch.object(
            cache_flood_redis,
            "get_redis_safe",
            return_value=self.redis,
        )
        self.redis_patch.start()
        self.time_patch = patch.object(
            cache_flood_redis.time,
            "time",
            side_effect=lambda: self.agora,
        )
        self.time_patch.start()

    def tearDown(self):
        self.time_patch.stop()
        self.redis_patch.stop()

    def avaliar(self, wamid, phone="phone-a", wa="cliente-a"):
        return cache_flood_redis.avaliar_flood_redis(
            wa,
            phone,
            wamid,
            REGRAS,
        )

    def test_mesmo_wamid_repetido_quinze_vezes_conta_um(self):
        resultado = None

        for _ in range(15):
            resultado = self.avaliar("wamid.unico")

        self.assertEqual(resultado["total"], 1)
        self.assertFalse(resultado["flood"])

    def test_decimo_quinto_wamid_distinto_detecta_flood(self):
        resultado = None

        for indice in range(15):
            resultado = self.avaliar(
                f"wamid.{indice}"
            )

        self.assertEqual(resultado["total"], 15)
        self.assertTrue(resultado["flood"])

    def test_mesmo_wamid_fica_isolado_por_unidade(self):
        unidade_a = self.avaliar(
            "wamid.igual",
            phone="phone-a",
        )
        unidade_b = self.avaliar(
            "wamid.igual",
            phone="phone-b",
        )

        self.assertEqual(unidade_a["total"], 1)
        self.assertEqual(unidade_b["total"], 1)
        contador_keys = [
            key
            for key in self.redis.valores
            if ":contador:" in key
        ]
        self.assertEqual(len(contador_keys), 2)

    def test_reentrega_em_outra_janela_nao_incrementa(self):
        primeiro = self.avaliar("wamid.1")
        self.agora += 10
        reentrega = self.avaliar("wamid.1")

        self.assertEqual(primeiro["total"], 1)
        self.assertEqual(reentrega["total"], 0)
        self.assertFalse(reentrega["evento_novo"])

    def test_wamid_volta_a_contar_depois_do_ttl_dedupe(self):
        primeiro = self.avaliar("wamid.1")
        self.agora += (
            cache_flood_redis
            .DEDUPLICACAO_TTL_SEGUNDOS
            + 1
        )
        depois_do_ttl = self.avaliar("wamid.1")

        self.assertTrue(primeiro["evento_novo"])
        self.assertTrue(depois_do_ttl["evento_novo"])
        self.assertEqual(depois_do_ttl["total"], 1)

    def test_chaves_tem_ttl_e_prefixo_operacional(self):
        self.avaliar("wamid.1")

        self.assertEqual(len(self.redis.expiracoes), 2)
        dedupe_key = next(
            key
            for key in self.redis.expiracoes
            if ":wamid:" in key
        )
        contador_key = next(
            key
            for key in self.redis.expiracoes
            if ":contador:" in key
        )
        self.assertTrue(
            dedupe_key.startswith("webhook_flood_rate:{")
        )
        self.assertEqual(
            self.redis.expiracoes[dedupe_key],
            7200,
        )
        self.assertEqual(
            self.redis.expiracoes[contador_key],
            15,
        )

    def test_dado_invalido_nao_acessa_redis(self):
        with patch.object(
            cache_flood_redis,
            "get_redis_safe",
        ) as get_redis:
            resultado = cache_flood_redis.avaliar_flood_redis(
                "cliente-a",
                "phone-a",
                None,
                REGRAS,
            )

        self.assertFalse(resultado["flood"])
        get_redis.assert_not_called()


class CacheFloodMemoriaWamidTests(unittest.TestCase):
    def setUp(self):
        with cache_flood_memoria._lock:
            cache_flood_memoria._eventos_por_chave.clear()
            cache_flood_memoria._ultima_limpeza = 0.0

        self.agora = 1000.0
        self.time_patch = patch.object(
            cache_flood_memoria.time,
            "monotonic",
            side_effect=lambda: self.agora,
        )
        self.time_patch.start()

    def tearDown(self):
        self.time_patch.stop()

    def avaliar(self, wamid):
        return cache_flood_memoria.avaliar_flood_memoria(
            "cliente-a",
            "phone-a",
            wamid,
            REGRAS,
        )

    def test_memoria_nao_duplica_o_mesmo_wamid(self):
        resultado = None

        for _ in range(15):
            resultado = self.avaliar("wamid.unico")

        self.assertEqual(resultado["total"], 1)
        self.assertFalse(resultado["flood"])

    def test_memoria_deduplica_em_outra_janela(self):
        primeiro = self.avaliar("wamid.unico")
        self.agora += 10
        reentrega = self.avaliar("wamid.unico")

        self.assertEqual(primeiro["total"], 1)
        self.assertEqual(reentrega["total"], 0)
        self.assertFalse(reentrega["evento_novo"])

    def test_memoria_bloqueia_quinze_wamids_distintos(self):
        resultado = None

        for indice in range(15):
            resultado = self.avaliar(
                f"wamid.{indice}"
            )

        self.assertEqual(resultado["total"], 15)
        self.assertTrue(resultado["flood"])

    def test_memoria_wamid_expirado_volta_a_contar(self):
        primeiro = self.avaliar("wamid.unico")
        self.agora += (
            cache_flood_memoria
            .DEDUPLICACAO_TTL_SEGUNDOS
            + 1
        )
        depois_do_ttl = self.avaliar("wamid.unico")

        self.assertTrue(primeiro["evento_novo"])
        self.assertTrue(depois_do_ttl["evento_novo"])
        self.assertEqual(depois_do_ttl["total"], 1)

    def test_memoria_limita_wamids_por_par(self):
        with patch.object(
            cache_flood_memoria,
            "MAX_WAMIDS_POR_PAR_MEMORIA",
            3,
        ):
            for indice in range(5):
                self.avaliar(f"wamid.{indice}")

        chave = cache_flood_memoria._cache_key(
            "cliente-a",
            "phone-a",
        )
        eventos = (
            cache_flood_memoria
            ._eventos_por_chave[chave]
        )
        self.assertEqual(len(eventos), 3)
        self.assertNotIn(
            cache_flood_memoria._digest_wamid(
                "wamid.0"
            ),
            eventos,
        )

    def test_memoria_limita_pares_antes_de_retorno_flood(
        self,
    ):
        regra_flood_imediato = (
            {
                "nome": "teste",
                "limite": 1,
                "janela_segundos": 5,
            },
        )

        with patch.object(
            cache_flood_memoria,
            "MAX_CHAVES_MEMORIA",
            1,
        ):
            cache_flood_memoria.avaliar_flood_memoria(
                "cliente-a",
                "phone-a",
                "wamid.a",
                regra_flood_imediato,
            )
            resultado = (
                cache_flood_memoria
                .avaliar_flood_memoria(
                    "cliente-b",
                    "phone-b",
                    "wamid.b",
                    regra_flood_imediato,
                )
            )

        self.assertTrue(resultado["flood"])
        self.assertEqual(
            len(
                cache_flood_memoria
                ._eventos_por_chave
            ),
            1,
        )
        self.assertIn(
            cache_flood_memoria._cache_key(
                "cliente-b",
                "phone-b",
            ),
            cache_flood_memoria._eventos_por_chave,
        )


class FloodGuardPropagacaoWamidTests(unittest.TestCase):
    def test_repassa_wamid_ao_redis(self):
        with patch.object(
            flood_guard,
            "avaliar_flood_redis",
            return_value={
                "redis_ok": True,
                "flood": False,
                "total": 1,
                "regra": None,
            },
        ) as avaliar_redis:
            resultado = flood_guard.bloquear_cliente_se_flood(
                "cliente-a",
                "phone-a",
                "wamid.1",
            )

        self.assertFalse(resultado["bloqueado"])
        avaliar_redis.assert_called_once_with(
            "cliente-a",
            "phone-a",
            "wamid.1",
            regras=flood_guard.REGRAS_FLOOD,
        )

    def test_repassa_wamid_ao_fallback_de_memoria(self):
        with patch.object(
            flood_guard,
            "avaliar_flood_redis",
            return_value={
                "redis_ok": False,
                "flood": False,
                "total": 0,
                "regra": None,
            },
        ), patch.object(
            flood_guard,
            "_avaliar_flood_banco",
            return_value={
                "banco_ok": False,
                "flood": False,
                "total": 0,
                "regra": None,
                "motivo": "banco_indisponivel",
            },
        ), patch.object(
            flood_guard,
            "avaliar_flood_memoria",
            return_value={
                "memoria_ok": True,
                "flood": False,
                "total": 1,
                "regra": None,
                "motivo": "memoria",
            },
        ) as avaliar_memoria:
            resultado = flood_guard.bloquear_cliente_se_flood(
                "cliente-a",
                "phone-a",
                "wamid.1",
            )

        self.assertFalse(resultado["bloqueado"])
        avaliar_memoria.assert_called_once_with(
            "cliente-a",
            "phone-a",
            "wamid.1",
            regras=flood_guard.REGRAS_FLOOD,
        )


if __name__ == "__main__":
    unittest.main()
```

### Critérios de aceite do Passo especial 0

1. quinze entregas do mesmo WAMID resultam em total `1` e não bloqueiam;
2. quatorze WAMIDs únicos mais repetições não bloqueiam;
3. o décimo quinto WAMID único dentro de cinco segundos bloqueia;
4. os contadores dos três caminhos permanecem isolados por
   `wa_id_cliente + phone_id_unidade`;
5. o Redis continua sendo a proteção principal;
6. falha do Redis continua acionando o fallback PostgreSQL;
7. Redis e PostgreSQL indisponíveis continuam acionando a memória;
8. Redis e memória deduplicam por WAMID dentro do par, enquanto o PostgreSQL
   conserva a unicidade global de `id_hash_msg`, coerente com a unicidade
   global do WAMID da Meta;
9. a deduplicação expira após duas horas tanto no Redis quanto na memória e o
   mesmo WAMID volta a ser contado depois desse TTL;
10. a chave Redis continua coberta pelo reset operacional;
11. o fallback em memória limita cada processo a 1000 pares e 200 WAMIDs por
    par, com máximo teórico de 200 mil entradas;
12. a eventual ejeção antecipada de um WAMID existe somente no fallback
    degradado por processo e não enfraquece Redis nem PostgreSQL;
13. nenhuma regra de `turnos_sem_avanco` é misturada ao anti-flood.

---

## Passo especial 0B — limitar reentregas de exceção inesperada por WAMID

Este passo não detecta bots e nunca bloqueia o remetente. Ele apenas limita o
custo de uma anomalia que tenha caído no `except Exception` genérico do
webhook:

```text
primeira falha do WAMID  -> HTTP 503
segunda falha do WAMID   -> HTTP 503
terceira falha do WAMID  -> HTTP 503
quarta falha ou posterior -> HTTP 200 e ignorar somente esse evento
```

Uma mensagem nova do mesmo cliente possui outro WAMID e começa normalmente.
Nenhuma linha é inserida em `cliente_bloqueado_meta`, nenhum contador da
conversa é alterado e nenhuma conversa é encerrada.

Não será criada tabela nem coluna para isso:

- a exceção pode acontecer antes de existir uma linha em
  `chatbot.fila_mensagens`;
- `fila_mensagens.retry_count` pertence ao retry do worker, não às reentregas
  HTTP da Meta;
- reutilizar essa coluna misturaria responsabilidades;
- o Redis remoto compartilhado consegue manter o pequeno orçamento de
  tentativas entre os processos Gunicorn;
- as chaves expiram automaticamente;
- se o WAMID não puder ser identificado ou o Redis estiver indisponível, o
  webhook preserva o comportamento simples anterior: registra o erro, retorna
  HTTP 200 e encerra o evento.

Portanto, este passo não altera DDL, model nem Admin. Caso uma evolução futura
decida persistir esse estado, ela deverá seguir a regra do projeto: primeiro
DDL-fonte, depois model unmanaged, Admin e somente então o SQL operacional para
sincronizar o RDS.

### Arquivo completo:
`core/cache/runtime/cache_webhook_erro_inesperado.py`

Criar:

```python
import hashlib
import logging

from core.cache.redis_client import get_redis_safe
from core.logging_config import short_value


logger = logging.getLogger(
    "cache.webhook_erro_inesperado"
)

REDIS_PREFIX = "webhook_erro_inesperado"
MAX_RESPOSTAS_503_POR_WAMID = 3
TTL_TENTATIVAS_SEGUNDOS = 7 * 24 * 60 * 60


def registrar_tentativa_erro_inesperado(id_hash_msg):
    id_hash_msg = _normalizar(id_hash_msg)

    if not id_hash_msg:
        return {
            "cache_ok": False,
            "identificavel": False,
            "tentativa": None,
            "retornar_503": False,
            "motivo": "wamid_ausente",
        }

    try:
        redis = get_redis_safe(
            retries=1,
            delay=0,
            validate=False,
        )
        key = _cache_key(id_hash_msg)
        pipe = redis.pipeline(transaction=True)
        pipe.incr(key)
        pipe.expire(
            key,
            TTL_TENTATIVAS_SEGUNDOS,
        )
        resultados = pipe.execute()
        tentativa = int(resultados[0])
        retornar_503 = (
            tentativa
            <= MAX_RESPOSTAS_503_POR_WAMID
        )

        logger.warning(
            "webhook_erro_inesperado_contabilizado | "
            "acao=%s id_hash_msg=%s tentativa=%s "
            "limite_503=%s ttl=%s",
            (
                "retornar_503"
                if retornar_503
                else "retornar_200_e_ignorar"
            ),
            short_value(id_hash_msg),
            tentativa,
            MAX_RESPOSTAS_503_POR_WAMID,
            TTL_TENTATIVAS_SEGUNDOS,
        )
        return {
            "cache_ok": True,
            "identificavel": True,
            "tentativa": tentativa,
            "retornar_503": retornar_503,
            "motivo": (
                "dentro_limite_503"
                if retornar_503
                else "limite_503_esgotado"
            ),
        }

    except Exception as exc:
        logger.exception(
            "webhook_erro_inesperado_contador_falhou | "
            "acao=retornar_200_e_ignorar "
            "id_hash_msg=%s erro=%s",
            short_value(id_hash_msg),
            exc,
        )
        return {
            "cache_ok": False,
            "identificavel": True,
            "tentativa": None,
            "retornar_503": False,
            "motivo": "redis_indisponivel",
        }


def _cache_key(id_hash_msg):
    digest = hashlib.sha256(
        id_hash_msg.encode("utf-8")
    ).hexdigest()
    return f"{REDIS_PREFIX}:{digest}"


def _normalizar(valor):
    if valor is None:
        return None

    texto = str(valor).strip()
    return texto or None
```

O TTL de sete dias é somente uma retenção operacional local. Ele não afirma nem
depende de um prazo específico de reentrega da Meta. Como esse caminho só roda
depois de uma exceção inesperada, não adiciona chamadas Redis ao fluxo normal.

### Integração no reset operacional

### Arquivo completo: `core/cache/cache_reset.py`

Substituir o conteúdo completo por:

```python
import argparse
import logging
import sys

from core.cache.runtime.cache_flood_redis import RATE_PREFIX
from core.cache.runtime.cache_webhook_erro_inesperado import (
    REDIS_PREFIX as ERRO_INESPERADO_PREFIX,
)
from core.cache.runtime.cache_cliente import REDIS_PREFIX as CLIENTE_PREFIX
from core.cache.runtime.cache_conversas_bloqueadas import REDIS_PREFIX as CONVERSA_BLOQUEADA_PREFIX
from core.cache.cache_unidade import (
    CACHE_DB_VERSION_KEY,
    CACHE_TEMP_KEY,
    CACHE_VERSION_KEY,
    REDIS_KEY,
    recarregar_cache_unidades,
)
from core.cache.redis_client import get_redis_safe, validar_redis_remoto


logger = logging.getLogger("cache.reset")

CHAVES_EXATAS_RESET = (
    REDIS_KEY,
    CACHE_VERSION_KEY,
    CACHE_DB_VERSION_KEY,
    CACHE_TEMP_KEY,
)

PADROES_OPERACIONAIS_RESET = (
    f"{CLIENTE_PREFIX}*",
    f"{CONVERSA_BLOQUEADA_PREFIX}:*",
    f"{RATE_PREFIX}:*",
    f"{ERRO_INESPERADO_PREFIX}:*",
)

# Compatibilidade com o reset completo de desenvolvimento.
PADROES_RESET = PADROES_OPERACIONAIS_RESET


def resetar_cache_operacional(redis_client=None):
    """
    Remove apenas estado operacional ligado a clientes e conversas.

    O cache de unidades e suas chaves de versao permanecem intactos. A funcao
    aceita um client apenas para facilitar testes; em producao usa a conexao
    configurada no ambiente da aplicacao.
    """

    r = (
        redis_client
        if redis_client is not None
        else get_redis_safe(retries=1, delay=0)
    )
    destino = validar_redis_remoto(r)
    removidas_por_padrao = {}

    for padrao in PADROES_OPERACIONAIS_RESET:
        removidas_por_padrao[padrao] = _remover_por_padrao(r, padrao)

    total_removido = sum(removidas_por_padrao.values())
    logger.warning(
        "cache_operacional_resetado | acao=limpar_clientes_conversas_flood "
        "destino=%s total=%s por_padrao=%s",
        destino,
        total_removido,
        removidas_por_padrao,
    )
    return {
        "destino": destino,
        "chaves_por_padrao": removidas_por_padrao,
        "total_removido": total_removido,
    }


def resetar_bloqueios_conversa(redis_client=None):
    """
    Remove somente os bloqueios temporarios de conversa, em lotes.
    """

    r = (
        redis_client
        if redis_client is not None
        else get_redis_safe(retries=1, delay=0)
    )
    destino = validar_redis_remoto(r)
    padrao = f"{CONVERSA_BLOQUEADA_PREFIX}:*"
    total_removido = _remover_por_padrao(r, padrao)
    logger.warning(
        "cache_bloqueios_resetado | acao=limpar_bloqueios_conversa "
        "destino=%s total=%s padrao=%s",
        destino,
        total_removido,
        padrao,
    )
    return {
        "destino": destino,
        "padrao": padrao,
        "total_removido": total_removido,
    }


def resetar_cache_redis_dev():
    try:
        r = get_redis_safe(retries=1, delay=0, validate=False)

        chaves_exatas_removidas = _remover_chaves_exatas(r, CHAVES_EXATAS_RESET)
        chaves_por_prefixo_removidas = 0

        for padrao in PADROES_RESET:
            chaves_por_prefixo_removidas += _remover_por_padrao(r, padrao)

        unidades_recriadas = recarregar_cache_unidades()

        logger.warning(
            "cache_redis_dev_resetado | acao=limpar_e_recriar chaves_exatas=%s chaves_prefixo=%s unidades_recriadas=%s",
            chaves_exatas_removidas,
            chaves_por_prefixo_removidas,
            unidades_recriadas,
        )
        return {
            "chaves_exatas_removidas": chaves_exatas_removidas,
            "chaves_por_prefixo_removidas": chaves_por_prefixo_removidas,
            "unidades_recriadas": unidades_recriadas,
        }

    except Exception as exc:
        logger.warning(
            "cache_redis_dev_reset_falhou | acao=seguir_sem_cache_recriado erro=%s",
            exc,
        )
        return {
            "chaves_exatas_removidas": 0,
            "chaves_por_prefixo_removidas": 0,
            "unidades_recriadas": None,
            "erro": str(exc),
        }


def _remover_chaves_exatas(redis_client, chaves):
    if not chaves:
        return 0

    return int(redis_client.delete(*chaves))


def _remover_por_padrao(redis_client, padrao):
    total_removido = 0
    lote = []

    for key in redis_client.scan_iter(match=padrao, count=500):
        lote.append(key)

        if len(lote) >= 500:
            total_removido += int(redis_client.delete(*lote))
            lote = []

    if lote:
        total_removido += int(redis_client.delete(*lote))

    return total_removido


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Utilitarios controlados de manutencao do cache Redis.",
    )
    modos = parser.add_mutually_exclusive_group(required=True)
    modos.add_argument(
        "--operacional",
        action="store_true",
        help=(
            "remove somente cache de clientes, bloqueios de conversa e "
            "contadores de flood"
        ),
    )
    modos.add_argument(
        "--bloqueios",
        action="store_true",
        help="remove somente os bloqueios temporarios de conversa",
    )
    parser.add_argument(
        "--confirmar",
        action="store_true",
        help="confirma a exclusao solicitada",
    )
    args = parser.parse_args(argv)

    if args.bloqueios and not args.confirmar:
        parser.error("--bloqueios exige --confirmar")

    if args.bloqueios:
        try:
            resultado = resetar_bloqueios_conversa()
        except Exception as exc:
            logger.exception(
                "cache_bloqueios_reset_falhou | acao=abortar erro=%s",
                exc,
            )
            print(f"RESET_CACHE_BLOQUEIOS_FALHOU: {exc}", file=sys.stderr)
            return 1

        print(
            "RESET_CACHE_BLOQUEIOS_OK "
            f"total_removido={resultado['total_removido']} "
            f"destino={resultado['destino']} "
            f"padrao={resultado['padrao']}"
        )
        return 0

    try:
        resultado = resetar_cache_operacional()
    except Exception as exc:
        logger.exception(
            "cache_operacional_reset_falhou | acao=abortar erro=%s",
            exc,
        )
        print(f"RESET_CACHE_OPERACIONAL_FALHOU: {exc}", file=sys.stderr)
        return 1

    print(
        "RESET_CACHE_OPERACIONAL_OK "
        f"total_removido={resultado['total_removido']} "
        f"destino={resultado['destino']} "
        f"por_padrao={resultado['chaves_por_padrao']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

```

Assim um reset operacional controlado também remove os orçamentos raros de
reentrega. Isso não cria dependência nova nem altera o reset de unidades.

### Arquivo de teste completo:
`tests/unit/test_cache_reset_operacional.py`

Substituir o conteúdo completo por:

```python
import fnmatch
import io
import unittest
from contextlib import redirect_stderr
from types import SimpleNamespace
from unittest.mock import patch

from core.cache import cache_reset, redis_client


class FakeRedis:
    def __init__(self, chaves, host="203.0.113.10"):
        self.chaves = set(chaves)
        self.connection_pool = SimpleNamespace(
            connection_kwargs={"host": host}
        )

    def scan_iter(self, match, count):
        del count
        for chave in sorted(self.chaves):
            if fnmatch.fnmatch(chave, match):
                yield chave

    def delete(self, *chaves):
        removidas = 0
        for chave in chaves:
            if chave in self.chaves:
                self.chaves.remove(chave)
                removidas += 1
        return removidas


class CacheResetOperacionalTests(unittest.TestCase):
    def test_remove_somente_chaves_operacionais(self):
        chaves_operacionais = {
            "cliente_cache:5511999999999",
            "conversa_bloqueada:hash-conversa",
            "webhook_flood_rate:60:janela:hash",
            "webhook_erro_inesperado:hash-wamid",
        }
        chaves_preservadas = {
            *cache_reset.CHAVES_EXATAS_RESET,
            "unidades_cache:admin_preflight",
            "configuracao:integracao:funil",
            "outra_chave:sem_relacao",
        }
        redis = FakeRedis(chaves_operacionais | chaves_preservadas)

        resultado = cache_reset.resetar_cache_operacional(redis)

        self.assertEqual(resultado["total_removido"], 4)
        self.assertEqual(redis.chaves, chaves_preservadas)
        self.assertEqual(
            resultado["chaves_por_padrao"],
            {
                "cliente_cache:*": 1,
                "conversa_bloqueada:*": 1,
                "webhook_flood_rate:*": 1,
                "webhook_erro_inesperado:*": 1,
            },
        )
        self.assertEqual(resultado["destino"], "203.0.113.10")

    def test_reset_operacional_e_idempotente(self):
        redis = FakeRedis({"cliente_cache:5511999999999"})

        primeiro = cache_reset.resetar_cache_operacional(redis)
        segundo = cache_reset.resetar_cache_operacional(redis)

        self.assertEqual(primeiro["total_removido"], 1)
        self.assertEqual(segundo["total_removido"], 0)

    def test_reset_operacional_recusa_redis_local(self):
        redis = FakeRedis(
            {"cliente_cache:5511999999999"},
            host="127.0.0.1",
        )

        with self.assertRaisesRegex(RuntimeError, "Redis local recusado"):
            cache_reset.resetar_cache_operacional(redis)

        self.assertEqual(redis.chaves, {"cliente_cache:5511999999999"})

    def test_cliente_central_recusa_redis_local_antes_do_ping(self):
        redis = FakeRedis(set(), host="127.0.0.1")

        with patch.object(
            redis_client.redis,
            "Redis",
            return_value=redis,
        ):
            with self.assertRaisesRegex(RuntimeError, "Redis local recusado"):
                redis_client._create_client()

    def test_reset_bloqueios_preserva_demais_chaves_operacionais(self):
        redis = FakeRedis(
            {
                "cliente_cache:5511999999999",
                "conversa_bloqueada:hash-conversa",
                "webhook_flood_rate:60:janela:hash",
                "webhook_erro_inesperado:hash-wamid",
                "unidades_cache",
            }
        )

        resultado = cache_reset.resetar_bloqueios_conversa(redis)

        self.assertEqual(resultado["total_removido"], 1)
        self.assertEqual(resultado["destino"], "203.0.113.10")
        self.assertEqual(
            redis.chaves,
            {
                "cliente_cache:5511999999999",
                "webhook_flood_rate:60:janela:hash",
                "webhook_erro_inesperado:hash-wamid",
                "unidades_cache",
            },
        )

    def test_reset_bloqueios_recusa_redis_local(self):
        redis = FakeRedis(
            {"conversa_bloqueada:hash-conversa"},
            host="127.0.0.1",
        )

        with self.assertRaisesRegex(RuntimeError, "Redis local recusado"):
            cache_reset.resetar_bloqueios_conversa(redis)

        self.assertEqual(
            redis.chaves,
            {"conversa_bloqueada:hash-conversa"},
        )

    def test_reset_bloqueios_processa_mais_de_quinhentas_chaves(self):
        redis = FakeRedis(
            {
                f"conversa_bloqueada:hash-{indice}"
                for indice in range(501)
            }
            | {"cliente_cache:preservado"}
        )

        resultado = cache_reset.resetar_bloqueios_conversa(redis)

        self.assertEqual(resultado["total_removido"], 501)
        self.assertEqual(redis.chaves, {"cliente_cache:preservado"})

    def test_processa_mais_de_quinhentas_chaves_em_lotes(self):
        redis = FakeRedis(
            {f"cliente_cache:{indice}" for indice in range(501)}
            | {"unidades_cache"}
        )

        resultado = cache_reset.resetar_cache_operacional(redis)

        self.assertEqual(resultado["total_removido"], 501)
        self.assertEqual(redis.chaves, {"unidades_cache"})

    def test_cli_exige_modo_de_reset_explicito(self):
        with redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as erro:
                cache_reset.main([])

        self.assertEqual(erro.exception.code, 2)

    def test_cli_retorna_sucesso(self):
        with patch.object(
            cache_reset,
            "resetar_cache_operacional",
            return_value={
                "total_removido": 2,
                "destino": "203.0.113.10",
                "chaves_por_padrao": {"cliente_cache:*": 2},
            },
        ), patch("builtins.print"):
            codigo = cache_reset.main(["--operacional"])

        self.assertEqual(codigo, 0)

    def test_cli_bloqueios_retorna_sucesso(self):
        with patch.object(
            cache_reset,
            "resetar_bloqueios_conversa",
            return_value={
                "total_removido": 2,
                "destino": "203.0.113.10",
                "padrao": "conversa_bloqueada:*",
            },
        ), patch("builtins.print"):
            codigo = cache_reset.main(["--bloqueios", "--confirmar"])

        self.assertEqual(codigo, 0)

    def test_cli_bloqueios_exige_confirmacao(self):
        with redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as erro:
                cache_reset.main(["--bloqueios"])

        self.assertEqual(erro.exception.code, 2)

    def test_cli_retorna_erro_se_redis_falhar(self):
        with patch.object(
            cache_reset,
            "resetar_cache_operacional",
            side_effect=ConnectionError("redis indisponivel"),
        ), patch("builtins.print"):
            codigo = cache_reset.main(["--operacional"])

        self.assertEqual(codigo, 1)


if __name__ == "__main__":
    unittest.main()

```

### Arquivo completo:
`callback/webhook/services/post_flow.py`

Substituir o conteúdo completo por:

```python
import json
import logging

from django.conf import settings
from django.http import JsonResponse

from core.cache.runtime.cache_conversas_bloqueadas import (
    ValidacaoBloqueioConversaIndisponivel,
    conversa_esta_bloqueada_cache,
)
from core.cache.runtime.cache_webhook_erro_inesperado import (
    MAX_RESPOSTAS_503_POR_WAMID,
    registrar_tentativa_erro_inesperado,
)
from core.cache.cache_unidade import (
    ValidacaoUnidadeIndisponivel,
    unidade_esta_ativa,
)
from core.database.connection_aws import get_conn
from core.logging_config import short_value
from .bloqueio_meta_guard import (
    responder_se_cliente_marcado_para_bloqueio,
)
from .flood_guard import responder_se_flood
from .meta_signature import validar_assinatura_meta
from .populating_fila_mensagens import preparar_dados_fila, povoando_fila


logger = logging.getLogger("webhook.post_flow")
fila_logger = logging.getLogger("webhook.fila")

TIPO_EVENTO_MENSAGEM = "messages"
TIPO_EVENTO_STATUS = "statuses"
TIPO_EVENTO_DESCONHECIDO = "unknown"


def responder_post_webhook(request):
    print("\n\n\n-----------------------------------------------------------------NOVO EVENTO-----------------------------------------------------------------\n\n\n")

    if resposta := _validar_content_type(request):
        return resposta

    if resposta := _validar_tamanho_body(request):
        return resposta

    if not validar_assinatura_meta(request):
        logger.warning(
            "mensagem_ignorada | motivo=assinatura_meta_invalida acao=retornar_403 path=%s",
            request.path,
        )
        return JsonResponse({"status": "forbidden"}, status=403)

    try:
        data = json.loads(request.body.decode("utf-8"))

    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        logger.warning(
            "mensagem_ignorada | motivo=json_invalido acao=nao_enfileirar erro=%s",
            exc,
        )
        return JsonResponse({
            "status": "ignored",
            "reason": "invalid_json",
        })

    phone_number_id = None
    cliente_telefone = None

    try:
        tipo_evento = _classificar_evento_meta(data)

        if tipo_evento == TIPO_EVENTO_STATUS:
            return _responder_status_meta_sem_processar(data)

        if tipo_evento != TIPO_EVENTO_MENSAGEM:
            logger.info(
                "evento_meta_ignorado | motivo=evento_sem_messages_ou_statuses acao=retornar_200",
            )
            return JsonResponse({"status": "ok"})

        phone_number_id = _extrair_phone_number_id(data)
        cliente_telefone = _extrair_cliente_telefone(data)

        if resposta_bloqueio := responder_se_cliente_marcado_para_bloqueio(
            cliente_telefone,
            phone_number_id,
        ):
            return resposta_bloqueio

        if resposta_flood := responder_se_flood(data):
            return resposta_flood

        if not unidade_esta_ativa(phone_number_id):
            logger.info(
                "mensagem_ignorada | motivo=unidade_inativa acao=nao_enfileirar cliente=%s phone_number_id=%s",
                short_value(cliente_telefone),
                short_value(phone_number_id),
            )
            return JsonResponse({"status": "ignored"})

        if cliente_telefone and conversa_esta_bloqueada_cache(
            cliente_telefone,
            phone_number_id,
        ):
            logger.info(
                "mensagem_ignorada | motivo=conversa_bloqueada acao=nao_enfileirar cliente=%s phone_number_id=%s",
                short_value(cliente_telefone),
                short_value(phone_number_id),
            )
            return JsonResponse({
                "status": "ignored",
                "reason": "blocked_conversation",
            })

        preparacao_fila = preparar_dados_fila(data)

        if preparacao_fila["status"] == "ready":
            resultado_fila = _executar_transacao_fila(preparacao_fila["dados"])

        else:
            resultado_fila = {
                "status": "ignored",
                "reason": preparacao_fila["reason"],
            }

        if resultado_fila["status"] == "inserted":
            logger.info(
                "request_processado | status=enfileirado acao=fila_insert cliente=%s phone_number_id=%s",
                short_value(cliente_telefone),
                short_value(phone_number_id),
            )

        elif resultado_fila["status"] == "ignored":
            logger.info(
                "mensagem_ignorada | motivo=%s acao=nao_enfileirar cliente=%s phone_number_id=%s",
                resultado_fila["reason"],
                short_value(cliente_telefone),
                short_value(phone_number_id),
            )

        else:
            logger.error(
                "request_indisponivel | motivo=%s acao=retornar_503_para_reentrega cliente=%s phone_number_id=%s",
                resultado_fila["reason"],
                short_value(cliente_telefone),
                short_value(phone_number_id),
            )
            return JsonResponse({
                "status": "unavailable",
                "reason": resultado_fila["reason"],
            }, status=503)

    except ValidacaoUnidadeIndisponivel as exc:
        logger.error(
            "request_indisponivel | motivo=validacao_unidade_indisponivel acao=retornar_503_para_reentrega cliente=%s phone_number_id=%s erro=%s",
            short_value(cliente_telefone),
            short_value(phone_number_id),
            exc,
        )
        return JsonResponse({
            "status": "unavailable",
            "reason": "unit_validation_unavailable",
        }, status=503)

    except ValidacaoBloqueioConversaIndisponivel as exc:
        logger.error(
            "request_indisponivel | motivo=validacao_bloqueio_conversa_indisponivel acao=retornar_503_para_reentrega cliente=%s phone_number_id=%s erro=%s",
            short_value(cliente_telefone),
            short_value(phone_number_id),
            exc,
        )
        return JsonResponse({
            "status": "unavailable",
            "reason": "conversation_block_validation_unavailable",
        }, status=503)

    except Exception as exc:
        id_hash_msg = _extrair_id_hash_msg_seguro(data)
        tentativa = registrar_tentativa_erro_inesperado(
            id_hash_msg,
        )

        if tentativa["retornar_503"]:
            logger.exception(
                "request_erro | "
                "acao=retornar_503_para_reentrega "
                "metodo=%s path=%s id_hash_msg=%s "
                "tentativa=%s limite_503=%s",
                request.method,
                request.path,
                short_value(id_hash_msg),
                tentativa["tentativa"],
                MAX_RESPOSTAS_503_POR_WAMID,
            )
            return JsonResponse(
                {
                    "status": "unavailable",
                    "reason": "unexpected_error_retry",
                    "attempt": tentativa["tentativa"],
                },
                status=503,
            )

        logger.error(
            "request_erro | "
            "acao=retornar_200_e_ignorar "
            "metodo=%s path=%s id_hash_msg=%s "
            "tentativa=%s motivo=%s",
            request.method,
            request.path,
            short_value(id_hash_msg),
            tentativa["tentativa"],
            tentativa["motivo"],
            exc_info=(
                type(exc),
                exc,
                exc.__traceback__,
            ),
        )
        reason = (
            "unexpected_error_retry_exhausted"
            if tentativa["motivo"]
            == "limite_503_esgotado"
            else "unexpected_error_retry_unavailable"
        )
        return JsonResponse({
            "status": "ignored",
            "reason": reason,
        })

    return JsonResponse({"status": "ok"})


def _classificar_evento_meta(data):
    value = _extrair_value(data)
    possui_mensagens = bool(value.get("messages"))
    possui_statuses = bool(value.get("statuses"))

    if possui_mensagens and not possui_statuses:
        return TIPO_EVENTO_MENSAGEM

    if possui_statuses and not possui_mensagens:
        return TIPO_EVENTO_STATUS

    return TIPO_EVENTO_DESCONHECIDO


def _responder_status_meta_sem_processar(data):
    statuses = _extrair_value(data).get("statuses") or []
    nomes_status = sorted({
        status.get("status")
        for status in statuses
        if status.get("status")
    })
    primeiro_status = statuses[0] if statuses else {}

    logger.info(
        "status_meta_recebido | acao=ignorar_na_v1 total=%s statuses=%s id_hash_msg_bot=%s",
        len(statuses),
        ",".join(nomes_status) or None,
        short_value(primeiro_status.get("id")),
    )
    return JsonResponse({"status": "ok"})


def _executar_transacao_fila(dados):
    conn_webhook = None

    try:
        conn_webhook = get_conn(application_name="webhook_chatbot")
        cursor_webhook = conn_webhook.cursor()
        resultado = povoando_fila(dados, cursor_webhook)
        conn_webhook.commit()

        if resultado["status"] == "inserted":
            fila_logger.info(
                "fila_insert_ok | acao=enfileirar id_msg=%s cliente=%s phone_number_id=%s tipo=%s",
                short_value(dados["id_hash_msg"]),
                short_value(dados["cliente_telefone"]),
                short_value(dados["id_phone_unidade"]),
                dados["tipo_mensagem"],
            )

        return resultado

    except Exception:
        if conn_webhook:
            conn_webhook.rollback()

        fila_logger.exception(
            "fila_insert_erro | acao=rollback id_msg=%s",
            short_value(dados.get("id_hash_msg") if dados else None),
        )
        return {
            "status": "error",
            "reason": "insert_exception",
        }

    finally:
        if conn_webhook:
            conn_webhook.close()


def _validar_content_type(request):
    content_type = (request.content_type or "").lower()

    if content_type.startswith("application/json"):
        return None

    logger.warning(
        "mensagem_ignorada | motivo=content_type_invalido acao=retornar_415 content_type=%s",
        content_type or None,
    )
    return JsonResponse({"status": "unsupported_media_type"}, status=415)


def _validar_tamanho_body(request):
    limite_bytes = settings.WEBHOOK_MAX_BODY_BYTES
    tamanho_header = request.headers.get("Content-Length")

    if tamanho_header:
        try:
            tamanho_bytes = int(tamanho_header)

        except ValueError:
            logger.warning(
                "mensagem_ignorada | motivo=content_length_invalido acao=retornar_400 content_length=%s",
                tamanho_header,
            )
            return JsonResponse({"status": "bad_request"}, status=400)

        if tamanho_bytes > limite_bytes:
            logger.warning(
                "mensagem_ignorada | motivo=body_muito_grande acao=retornar_413 tamanho_bytes=%s limite_bytes=%s origem=content_length",
                tamanho_bytes,
                limite_bytes,
            )
            return JsonResponse({"status": "payload_too_large"}, status=413)

    tamanho_real = len(request.body)

    if tamanho_real > limite_bytes:
        logger.warning(
            "mensagem_ignorada | motivo=body_muito_grande acao=retornar_413 tamanho_bytes=%s limite_bytes=%s origem=request_body",
            tamanho_real,
            limite_bytes,
        )
        return JsonResponse({"status": "payload_too_large"}, status=413)

    return None


def _extrair_value(data):
    return (
        data.get("entry", [{}])[0]
        .get("changes", [{}])[0]
        .get("value", {})
    )


def _extrair_phone_number_id(data):
    metadata = _extrair_value(data).get("metadata", {})
    return metadata.get("phone_number_id")


def _extrair_cliente_telefone(data):
    contacts = _extrair_value(data).get("contacts", [{}])
    return contacts[0].get("wa_id") if contacts else None



def _extrair_id_hash_msg_seguro(data):
    try:
        value = _extrair_value(data)
        messages = value.get("messages")

        if (
            not isinstance(messages, list)
            or not messages
            or not isinstance(messages[0], dict)
        ):
            return None

        id_hash_msg = messages[0].get("id")

        if id_hash_msg is None:
            return None

        id_hash_msg = str(id_hash_msg).strip()
        return id_hash_msg or None

    except Exception:
        return None
```

As exceções específicas já conhecidas continuam fora desse orçamento:

- `ValidacaoUnidadeIndisponivel` continua retornando 503 normalmente;
- `ValidacaoBloqueioConversaIndisponivel` continua retornando 503 normalmente;
- falha transacional de inserção da fila continua retornando 503 normalmente;
- somente a última captura genérica usa o limite por WAMID;
- a classificação estrutural do evento está dentro do `try`, portanto uma
  exceção inesperada nessa classificação também passa pelo orçamento genérico.

### Arquivo de teste completo:
`tests/unit/test_cache_webhook_erro_inesperado.py`

Criar:

```python
import unittest
from unittest.mock import patch

from core.cache.runtime import (
    cache_webhook_erro_inesperado as cache_erro,
)


class FakeRedis:
    def __init__(self):
        self.valores = {}
        self.expiracoes = {}

    def pipeline(self, transaction=True):
        return FakePipeline(self, transaction)


class FakePipeline:
    def __init__(self, redis, transaction):
        self.redis = redis
        self.transaction = transaction
        self.operacoes = []

    def incr(self, key):
        self.operacoes.append(("incr", key))
        return self

    def expire(self, key, ttl):
        self.operacoes.append(
            ("expire", key, ttl)
        )
        return self

    def execute(self):
        resultados = []

        for nome, key, *argumentos in self.operacoes:
            if nome == "incr":
                total = int(
                    self.redis.valores.get(key, 0)
                ) + 1
                self.redis.valores[key] = total
                resultados.append(total)

            elif nome == "expire":
                self.redis.expiracoes[key] = int(
                    argumentos[0]
                )
                resultados.append(True)

        return resultados


class CacheWebhookErroInesperadoTests(unittest.TestCase):
    def setUp(self):
        self.redis = FakeRedis()
        self.redis_patch = patch.object(
            cache_erro,
            "get_redis_safe",
            return_value=self.redis,
        )
        self.redis_patch.start()

    def tearDown(self):
        self.redis_patch.stop()

    def registrar(self, wamid="wamid.test.1"):
        return (
            cache_erro
            .registrar_tentativa_erro_inesperado(
                wamid,
            )
        )

    def test_primeiras_tres_tentativas_pedem_503(self):
        resultados = [
            self.registrar()
            for _ in range(3)
        ]

        self.assertEqual(
            [
                resultado["tentativa"]
                for resultado in resultados
            ],
            [1, 2, 3],
        )
        self.assertTrue(
            all(
                resultado["retornar_503"]
                for resultado in resultados
            )
        )

    def test_quarta_e_posteriores_pedem_200(self):
        resultados = [
            self.registrar()
            for _ in range(5)
        ]

        self.assertFalse(
            resultados[3]["retornar_503"]
        )
        self.assertFalse(
            resultados[4]["retornar_503"]
        )
        self.assertEqual(
            resultados[3]["tentativa"],
            4,
        )

    def test_wamids_diferentes_nao_compartilham_contagem(self):
        primeiro = self.registrar("wamid.a")
        segundo = self.registrar("wamid.b")

        self.assertEqual(primeiro["tentativa"], 1)
        self.assertEqual(segundo["tentativa"], 1)
        self.assertEqual(len(self.redis.valores), 2)

    def test_chave_recebe_ttl(self):
        self.registrar()

        self.assertEqual(
            list(self.redis.expiracoes.values()),
            [7 * 24 * 60 * 60],
        )

    def test_wamid_ausente_retorna_200_sem_redis(self):
        with patch.object(
            cache_erro,
            "get_redis_safe",
        ) as get_redis:
            resultado = (
                cache_erro
                .registrar_tentativa_erro_inesperado(
                    None,
                )
            )

        self.assertFalse(resultado["retornar_503"])
        self.assertEqual(
            resultado["motivo"],
            "wamid_ausente",
        )
        get_redis.assert_not_called()

    def test_redis_indisponivel_retorna_200(self):
        with patch.object(
            cache_erro,
            "get_redis_safe",
            side_effect=ConnectionError("redis caiu"),
        ):
            resultado = self.registrar()

        self.assertFalse(resultado["retornar_503"])
        self.assertEqual(
            resultado["motivo"],
            "redis_indisponivel",
        )


if __name__ == "__main__":
    unittest.main()
```

### Novo arquivo de teste de integração completo:
`tests/unit/test_webhook_erro_inesperado_integracao.py`

Criar:

```python
import unittest
from unittest.mock import patch

from django.test import override_settings

from callback.webhook.services import post_flow
from tests.helpers import (
    FakeRequest,
    json_response_payload,
)
from tests.payloads import payload_texto_meta


@override_settings(
    WEBHOOK_MAX_BODY_BYTES=1024 * 256,
)
class WebhookErroInesperadoIntegracaoTests(
    unittest.TestCase,
):
    def setUp(self):
        self.print_patcher = patch("builtins.print")
        self.print_patcher.start()
        self.addCleanup(self.print_patcher.stop)

    def _executar_com_erro_generico(
        self,
        payload,
        tentativa,
    ):
        request = FakeRequest(payload)

        with patch.object(
            post_flow,
            "validar_assinatura_meta",
            return_value=True,
        ), patch.object(
            post_flow,
            "responder_se_cliente_marcado_para_bloqueio",
            return_value=None,
        ), patch.object(
            post_flow,
            "responder_se_flood",
            side_effect=RuntimeError("falha inesperada"),
        ), patch.object(
            post_flow,
            "registrar_tentativa_erro_inesperado",
            return_value=tentativa,
        ) as registrar, patch.object(
            post_flow,
            "preparar_dados_fila",
        ) as preparar_fila:
            response = post_flow.responder_post_webhook(
                request,
            )

        return response, registrar, preparar_fila

    def test_primeiras_tres_falhas_retornam_503(self):
        for numero_tentativa in (1, 2, 3):
            with self.subTest(
                tentativa=numero_tentativa,
            ):
                tentativa = {
                    "cache_ok": True,
                    "identificavel": True,
                    "tentativa": numero_tentativa,
                    "retornar_503": True,
                    "motivo": "dentro_limite_503",
                }
                response, registrar, preparar_fila = (
                    self._executar_com_erro_generico(
                        payload_texto_meta(),
                        tentativa,
                    )
                )

                self.assertEqual(
                    response.status_code,
                    503,
                )
                self.assertEqual(
                    json_response_payload(response),
                    {
                        "status": "unavailable",
                        "reason": (
                            "unexpected_error_retry"
                        ),
                        "attempt": numero_tentativa,
                    },
                )
                registrar.assert_called_once_with(
                    "wamid.test.1",
                )
                preparar_fila.assert_not_called()

    def test_quarta_falha_retorna_200_sem_fila(self):
        tentativa = {
            "cache_ok": True,
            "identificavel": True,
            "tentativa": 4,
            "retornar_503": False,
            "motivo": "limite_503_esgotado",
        }
        response, registrar, preparar_fila = (
            self._executar_com_erro_generico(
                payload_texto_meta(),
                tentativa,
            )
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            json_response_payload(response)["reason"],
            "unexpected_error_retry_exhausted",
        )
        registrar.assert_called_once_with(
            "wamid.test.1",
        )
        preparar_fila.assert_not_called()

    def test_wamid_ausente_retorna_200_sem_fila(self):
        tentativa = {
            "cache_ok": False,
            "identificavel": False,
            "tentativa": None,
            "retornar_503": False,
            "motivo": "wamid_ausente",
        }
        response, registrar, preparar_fila = (
            self._executar_com_erro_generico(
                payload_texto_meta(message_id=None),
                tentativa,
            )
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            json_response_payload(response)["reason"],
            "unexpected_error_retry_unavailable",
        )
        registrar.assert_called_once_with(None)
        preparar_fila.assert_not_called()

    def test_redis_indisponivel_retorna_200_sem_fila(
        self,
    ):
        tentativa = {
            "cache_ok": False,
            "identificavel": True,
            "tentativa": None,
            "retornar_503": False,
            "motivo": "redis_indisponivel",
        }
        response, registrar, preparar_fila = (
            self._executar_com_erro_generico(
                payload_texto_meta(),
                tentativa,
            )
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            json_response_payload(response)["reason"],
            "unexpected_error_retry_unavailable",
        )
        registrar.assert_called_once_with(
            "wamid.test.1",
        )
        preparar_fila.assert_not_called()

    def test_erro_estrutural_na_classificacao_e_orcado(
        self,
    ):
        tentativa = {
            "cache_ok": False,
            "identificavel": False,
            "tentativa": None,
            "retornar_503": False,
            "motivo": "wamid_ausente",
        }
        request = FakeRequest({"entry": []})

        with patch.object(
            post_flow,
            "validar_assinatura_meta",
            return_value=True,
        ), patch.object(
            post_flow,
            "registrar_tentativa_erro_inesperado",
            return_value=tentativa,
        ) as registrar, patch.object(
            post_flow,
            "preparar_dados_fila",
        ) as preparar_fila:
            response = post_flow.responder_post_webhook(
                request,
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            json_response_payload(response)["reason"],
            "unexpected_error_retry_unavailable",
        )
        registrar.assert_called_once_with(None)
        preparar_fila.assert_not_called()


if __name__ == "__main__":
    unittest.main()
```

### Critérios de aceite do Passo especial 0B

1. somente o `except Exception` final usa o orçamento;
2. as três primeiras falhas do mesmo WAMID retornam 503;
3. a quarta e todas as posteriores retornam 200;
4. WAMIDs diferentes possuem contagens independentes;
5. o número do cliente nunca é bloqueado por esse mecanismo;
6. uma mensagem nova do mesmo cliente continua normalmente;
7. nenhum registro é criado no PostgreSQL;
8. nenhuma coluna ou tabela é adicionada;
9. falha do Redis não cria loop: retorna 200;
10. o fluxo normal não ganha nenhuma chamada extra ao Redis;
11. o reset operacional remove as chaves desse orçamento;
12. uma exceção estrutural inesperada durante a classificação do evento também
    passa pela captura genérica e pelo mesmo orçamento.

---
## Passo 1 — alterar diretamente o DDL-fonte

### Arquivo final completo: `core/database/deploy_database/bank_script.py`

```python

import logging

from core.database.deploy_database.transacao_deploy import transacao_deploy


logger = logging.getLogger("db.deploy_database")


def criar_funcoes_lock():
    with transacao_deploy("criar_funcoes_lock", logger) as cursor:
        cursor.execute("""
        CREATE OR REPLACE FUNCTION chatbot.lock_conversa(p_id_conversa INT)
        RETURNS TABLE (
            lock_ok BOOLEAN,
            lock_version_atual INT
        )
        LANGUAGE plpgsql
        AS $$

        DECLARE
            v_lock_version INT;

        BEGIN
            UPDATE chatbot.conversa c
            SET
                processing = TRUE,
                processing_started_at = NOW(),
                lock_version = COALESCE(c.lock_version, 0) + 1
            WHERE
                c.id_conversa = p_id_conversa
                AND (
                    c.processing = FALSE
                    OR c.processing_started_at
                        < NOW() - INTERVAL '110.0 seconds'
                )
            RETURNING c.lock_version INTO v_lock_version;

            IF v_lock_version IS NULL THEN
                RETURN QUERY SELECT FALSE, NULL::INT;
                RETURN;
            END IF;

            RETURN QUERY SELECT TRUE, v_lock_version;
        END;

        $$;
        """)

        cursor.execute("""
        CREATE OR REPLACE FUNCTION chatbot.unlock_conversa(
            p_id_conversa INT,
            p_lock_version INT
        )
        RETURNS BOOLEAN
        LANGUAGE plpgsql
        AS $$

        DECLARE
            updated_rows INTEGER;

        BEGIN
            UPDATE chatbot.conversa
            SET
                processing = FALSE,
                processing_started_at = NULL
            WHERE id_conversa = p_id_conversa
              AND lock_version = p_lock_version;

            GET DIAGNOSTICS updated_rows = ROW_COUNT;

            RETURN updated_rows = 1;
        END;

        $$;
        """)

    logger.info("banco_setup_ok | acao=criar_funcoes_lock")


def criar_funcao_dequeue_message():
    with transacao_deploy("criar_funcao_dequeue_message", logger) as cursor:
        cursor.execute("""
        CREATE OR REPLACE FUNCTION chatbot.dequeue_message()
        RETURNS TABLE (
            id_mensagem INT,
            cliente_telefone VARCHAR,
            conteudo_texto TEXT,
            tipo_mensagem VARCHAR,
            id_phone_unidade VARCHAR,
            unidade_telefone VARCHAR,
            received_data_hora TIMESTAMPTZ,
            id_hash_msg VARCHAR,
            retry_count INT
        )
        LANGUAGE plpgsql
        AS $$

        BEGIN
            RETURN QUERY

            WITH next_job AS (
                SELECT f.id_mensagem
                FROM chatbot.fila_mensagens f
                WHERE
                    (
                        f.status = 'pending'
                        AND f.next_attempt_at <= NOW()
                    )
                    OR
                    (
                        f.status = 'processing'
                        AND f.processing_started_at
                            < NOW() - INTERVAL '2 minutes'
                    )
                ORDER BY
                    CASE
                        WHEN f.status = 'pending' THEN f.next_attempt_at
                        WHEN f.status = 'processing'
                            THEN f.processing_started_at
                    END NULLS FIRST,
                    f.id_mensagem
                FOR UPDATE SKIP LOCKED
                LIMIT 1
            )

            UPDATE chatbot.fila_mensagens f
            SET
                status = 'processing',
                retry_count = f.retry_count + 1,
                processing_started_at = NOW()
            FROM next_job
            WHERE f.id_mensagem = next_job.id_mensagem

            RETURNING
                f.id_mensagem,
                f.cliente_telefone,
                f.conteudo_texto,
                f.tipo_mensagem,
                f.id_phone_unidade,
                f.unidade_telefone,
                f.received_data_hora,
                f.id_hash_msg,
                f.retry_count;
        END;

        $$;
        """)

    logger.info("banco_setup_ok | acao=criar_funcao_dequeue_message")


def criar_tabelas():
    """Cria o schema final da V1 em ordem de dependência, sem migrações."""
    with transacao_deploy("criar_tabelas", logger) as cursor:
        cursor.execute("""
        CREATE SCHEMA IF NOT EXISTS chatbot;

        -- 1. ENTIDADES SEM DEPENDÊNCIAS ENTRE TABELAS

        CREATE TABLE IF NOT EXISTS chatbot.cliente (
            id_cliente SERIAL PRIMARY KEY,
            nome VARCHAR(200),
            waid_telefone VARCHAR(50) UNIQUE NOT NULL,
            email VARCHAR(200) UNIQUE,
            idade INTEGER
        );

        CREATE TABLE IF NOT EXISTS chatbot.unidade (
            id_unidade SERIAL PRIMARY KEY,
            nome VARCHAR(300) UNIQUE NOT NULL,
            cnpj VARCHAR(50) UNIQUE NOT NULL,
            email_responsavel VARCHAR(255) UNIQUE NOT NULL,
            telefone VARCHAR(20) UNIQUE NOT NULL,
            numero_comercial VARCHAR(30),
            waba_id VARCHAR(100) UNIQUE NOT NULL,
            phone_number_id VARCHAR(100) UNIQUE NOT NULL,
            link_agendamento VARCHAR(400) UNIQUE NOT NULL,
            link_instagram VARCHAR(400),
            bpa_ativo BOOLEAN NOT NULL DEFAULT FALSE,
            status_pagamento BOOLEAN DEFAULT TRUE
        );

        CREATE TABLE IF NOT EXISTS chatbot.etapa (
            id_etapa SERIAL PRIMARY KEY,
            nome_etapa VARCHAR(100) UNIQUE NOT NULL,
            encerra_automaticamente BOOLEAN NOT NULL DEFAULT FALSE,
            bloqueio_dias INTEGER NOT NULL DEFAULT 0,
            elegivel_funil BOOLEAN NOT NULL DEFAULT FALSE,

            CONSTRAINT ck_etapa_bloqueio_dias
                CHECK (bloqueio_dias >= 0)
        );

        -- 2. CONFIGURACAO DO FUNIL POR UNIDADE

        CREATE TABLE IF NOT EXISTS chatbot.integracao_funil_unidade (
            id_integracao_funil SERIAL PRIMARY KEY,
            id_unidade INT NOT NULL UNIQUE,

            nome_widget VARCHAR(300) NOT NULL,
            data_salvamento_widget DATE,
            codigo_widget VARCHAR(100) UNIQUE NOT NULL,
            link_api_carrossel VARCHAR(500) UNIQUE NOT NULL,
            codigo_canal_venda VARCHAR(100) NOT NULL,

            widget_ativo BOOLEAN NOT NULL DEFAULT TRUE,
            integracao_ativa BOOLEAN NOT NULL DEFAULT TRUE,

            criado_em TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            atualizado_em TIMESTAMPTZ NOT NULL DEFAULT NOW(),

            CONSTRAINT ck_integracao_funil_nome_widget
                CHECK (BTRIM(nome_widget) <> ''),

            CONSTRAINT ck_integracao_funil_codigo_widget
                CHECK (BTRIM(codigo_widget) <> ''),

            CONSTRAINT ck_integracao_funil_link_api
                CHECK (BTRIM(link_api_carrossel) <> ''),

            CONSTRAINT ck_integracao_funil_codigo_canal
                CHECK (BTRIM(codigo_canal_venda) <> ''),

            CONSTRAINT integracao_funil_unidade_id_unidade_fkey
                FOREIGN KEY (id_unidade)
                REFERENCES chatbot.unidade(id_unidade)
                ON DELETE CASCADE
        );

        -- 3. CONVERSA: RAIZ TRANSACIONAL DO ATENDIMENTO

        CREATE TABLE IF NOT EXISTS chatbot.conversa (
            id_conversa SERIAL PRIMARY KEY,
            id_cliente INT NOT NULL,
            id_unidade INT NOT NULL,
            id_etapa_atual INT,

            status_ativa BOOLEAN NOT NULL DEFAULT TRUE,
            status_dependente BOOLEAN DEFAULT FALSE,

            last_interaction_at TIMESTAMPTZ,

            last_message_from VARCHAR(10)
                CHECK (last_message_from IN ('cliente', 'bot')),

            followup_stage INTEGER DEFAULT 0,
            followup_last_sent_at TIMESTAMPTZ NULL,

            lead_no_funil BOOLEAN DEFAULT FALSE,

            processing BOOLEAN DEFAULT FALSE,
            processing_started_at TIMESTAMPTZ NULL,
            lock_version INTEGER DEFAULT 0,
            turnos_sem_avanco INTEGER NOT NULL DEFAULT 0,

            iniciou_em TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            finalizou_em TIMESTAMPTZ,
            motivo_encerramento VARCHAR(30),

            CONSTRAINT ck_conversa_motivo_encerramento
                CHECK (
                    motivo_encerramento IS NULL
                    OR motivo_encerramento IN (
                        'idade_invalida',
                        'foi_agendado'
                    )
                ),

            CONSTRAINT ck_conversa_turnos_sem_avanco
                CHECK (turnos_sem_avanco BETWEEN 0 AND 12),

            FOREIGN KEY (id_cliente)
                REFERENCES chatbot.cliente(id_cliente)
                ON DELETE CASCADE,

            FOREIGN KEY (id_unidade)
                REFERENCES chatbot.unidade(id_unidade)
                ON DELETE CASCADE,

            FOREIGN KEY (id_etapa_atual)
                REFERENCES chatbot.etapa(id_etapa)
                ON DELETE SET NULL
        );

        CREATE UNIQUE INDEX IF NOT EXISTS idx_conversa_unica_ativa
        ON chatbot.conversa (id_cliente, id_unidade)
        WHERE status_ativa = TRUE;

        CREATE INDEX IF NOT EXISTS idx_conversa_followup
        ON chatbot.conversa (
            last_message_from,
            followup_stage,
            last_interaction_at
        );

        CREATE INDEX IF NOT EXISTS idx_conversa_processing
        ON chatbot.conversa (processing, processing_started_at);

        CREATE INDEX IF NOT EXISTS idx_conversa_ultima_inativa
        ON chatbot.conversa (id_cliente, id_unidade, finalizou_em DESC)
        INCLUDE (id_conversa, id_etapa_atual)
        WHERE status_ativa = FALSE;

        CREATE INDEX IF NOT EXISTS idx_conversa_funil_pendente
        ON chatbot.conversa (id_etapa_atual, id_conversa)
        WHERE lead_no_funil IS NOT TRUE;

        -- 4. DEPENDENTE: EXISTE SOMENTE DENTRO DE UMA CONVERSA

        CREATE TABLE IF NOT EXISTS chatbot.dependente (
            id_dependente SERIAL PRIMARY KEY,
            id_cliente INT NOT NULL,
            id_conversa INT,
            nome_dependente VARCHAR(200),
            idade INTEGER,

            FOREIGN KEY (id_cliente)
                REFERENCES chatbot.cliente(id_cliente)
                ON DELETE CASCADE,

            CONSTRAINT dependente_id_conversa_fkey
                FOREIGN KEY (id_conversa)
                REFERENCES chatbot.conversa(id_conversa)
                ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_dependente_cliente
        ON chatbot.dependente (id_cliente);

        CREATE UNIQUE INDEX IF NOT EXISTS uq_dependente_conversa
        ON chatbot.dependente (id_conversa)
        WHERE id_conversa IS NOT NULL;

        CREATE INDEX IF NOT EXISTS idx_dependente_conversa
        ON chatbot.dependente (id_conversa);

        -- 5. FILA: CRIADA ANTES DO HISTÓRICO PARA A FK NASCER PRONTA

        CREATE TABLE IF NOT EXISTS chatbot.fila_mensagens (
            id_mensagem SERIAL PRIMARY KEY,
            id_conversa INT NULL,
            status VARCHAR(20) NOT NULL DEFAULT 'pending',
            retry_count INTEGER DEFAULT 0,
            next_attempt_at TIMESTAMPTZ DEFAULT NOW(),
            processing_started_at TIMESTAMPTZ NULL,
            received_data_hora TIMESTAMPTZ NOT NULL,
            cliente_telefone VARCHAR(100) NOT NULL,
            conteudo_texto TEXT,
            tipo_mensagem VARCHAR(20) NOT NULL,
            id_hash_msg VARCHAR(255) UNIQUE NOT NULL,
            id_phone_unidade VARCHAR(100) NOT NULL,
            unidade_telefone VARCHAR(100) NOT NULL,
            last_error TEXT,

            FOREIGN KEY (id_conversa)
                REFERENCES chatbot.conversa(id_conversa)
                ON DELETE SET NULL,

            CHECK (status IN ('pending', 'processing', 'sent', 'failed'))
        );

        CREATE INDEX IF NOT EXISTS idx_fila_pending_next_attempt
        ON chatbot.fila_mensagens (next_attempt_at, id_mensagem)
        WHERE status = 'pending';

        CREATE INDEX IF NOT EXISTS idx_fila_processing_timeout
        ON chatbot.fila_mensagens (processing_started_at, id_mensagem)
        WHERE status = 'processing';

        CREATE INDEX IF NOT EXISTS idx_fila_conversa_aberta_data
        ON chatbot.fila_mensagens (
            id_conversa,
            received_data_hora,
            id_mensagem
        )
        WHERE id_conversa IS NOT NULL
          AND status IN ('pending', 'processing');

        -- 6. HISTÓRICO PARTICIONADO E RESPOSTAS DA TRIAGEM

        CREATE TABLE IF NOT EXISTS chatbot.historico_mensagens (
            id_mensagem SERIAL,
            id_conversa INT NOT NULL,
            id_etapa INT,
            received_data_hora TIMESTAMPTZ NOT NULL,
            cliente_telefone VARCHAR(100) NOT NULL,
            conteudo_texto TEXT,
            tipo_mensagem VARCHAR(20) NOT NULL,
            id_hash_msg VARCHAR(255) NOT NULL,
            id_mensagem_fila INT,
            id_hash_cliente_origem VARCHAR(255),
            id_phone_unidade VARCHAR(100) NOT NULL,
            unidade_telefone VARCHAR(100) NOT NULL,
            quem_enviou VARCHAR(10) NOT NULL,
            status_envio VARCHAR(20),

            PRIMARY KEY (id_mensagem, received_data_hora),

            FOREIGN KEY (id_conversa)
                REFERENCES chatbot.conversa(id_conversa)
                ON DELETE CASCADE,

            FOREIGN KEY (id_etapa)
                REFERENCES chatbot.etapa(id_etapa)
                ON DELETE SET NULL,

            CONSTRAINT fk_historico_mensagem_fila
                FOREIGN KEY (id_mensagem_fila)
                REFERENCES chatbot.fila_mensagens(id_mensagem)
                ON DELETE SET NULL,

            CONSTRAINT chk_historico_quem_enviou
                CHECK (quem_enviou IN ('cliente', 'bot')),

            CONSTRAINT chk_historico_status_envio
                CHECK (
                    (quem_enviou = 'cliente' AND status_envio IS NULL)
                    OR
                    (
                        quem_enviou = 'bot'
                        AND status_envio IS NOT NULL
                        AND status_envio IN ('pending', 'sent', 'failed')
                    )
                )
        )
        PARTITION BY RANGE (received_data_hora);

        CREATE TABLE IF NOT EXISTS chatbot.historico_mensagens_default
        PARTITION OF chatbot.historico_mensagens
        DEFAULT;

        CREATE INDEX IF NOT EXISTS idx_historico_conversa_data
        ON chatbot.historico_mensagens (
            id_conversa,
            received_data_hora DESC,
            id_mensagem DESC
        );

        CREATE INDEX IF NOT EXISTS idx_historico_cliente_mensagem_fila
        ON chatbot.historico_mensagens (
            id_conversa,
            id_mensagem_fila,
            id_hash_msg,
            received_data_hora DESC,
            id_mensagem DESC
        )
        WHERE quem_enviou = 'cliente'
          AND id_mensagem_fila IS NOT NULL;

        CREATE INDEX IF NOT EXISTS idx_historico_bot_mensagem_fila
        ON chatbot.historico_mensagens (
            id_conversa,
            id_mensagem_fila,
            id_hash_cliente_origem,
            received_data_hora DESC,
            id_mensagem DESC
        )
        WHERE quem_enviou = 'bot'
          AND id_mensagem_fila IS NOT NULL
          AND id_hash_cliente_origem IS NOT NULL;

        CREATE TABLE IF NOT EXISTS chatbot.respostas_desafios (
            id_resposta_desafio SERIAL PRIMARY KEY,
            id_conversa INT NOT NULL,
            id_etapa INT NOT NULL,
            resposta VARCHAR(20) NOT NULL,
            id_historico_mensagem_cliente INT NULL,
            criado_em TIMESTAMPTZ NOT NULL DEFAULT NOW(),

            FOREIGN KEY (id_conversa)
                REFERENCES chatbot.conversa(id_conversa)
                ON DELETE CASCADE,

            FOREIGN KEY (id_etapa)
                REFERENCES chatbot.etapa(id_etapa),

            CONSTRAINT uq_respostas_desafios_conversa_etapa
                UNIQUE (id_conversa, id_etapa)
        );

        -- 7. PESQUISA DE SATISFACAO DO ATENDIMENTO

        CREATE TABLE IF NOT EXISTS chatbot.pesquisa_satisfacao (
            id_pesquisa_satisfacao SERIAL PRIMARY KEY,
            id_conversa INT NOT NULL UNIQUE,
            nota SMALLINT,
            comentario TEXT,
            criado_em TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            atualizado_em TIMESTAMPTZ NOT NULL DEFAULT NOW(),

            CONSTRAINT pesquisa_satisfacao_id_conversa_fkey
                FOREIGN KEY (id_conversa)
                REFERENCES chatbot.conversa(id_conversa)
                ON DELETE CASCADE,

            CONSTRAINT ck_pesquisa_satisfacao_nota
                CHECK (nota IS NULL OR nota BETWEEN 1 AND 5)
        );

        -- 8. FILA OPERACIONAL DO WORKER DE FUNIL

        CREATE TABLE IF NOT EXISTS chatbot.funil_envios (
            id_funil_envio SERIAL PRIMARY KEY,
            id_conversa INT NOT NULL UNIQUE,
            status VARCHAR(20) NOT NULL DEFAULT 'pending',
            attempt_count INTEGER NOT NULL DEFAULT 0,
            next_attempt_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            processing_started_at TIMESTAMPTZ,
            enviado_em TIMESTAMPTZ,
            ultimo_erro TEXT,
            resposta_funil TEXT,
            criado_em TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            atualizado_em TIMESTAMPTZ NOT NULL DEFAULT NOW(),

            CONSTRAINT funil_envios_id_conversa_fkey
                FOREIGN KEY (id_conversa)
                REFERENCES chatbot.conversa(id_conversa)
                ON DELETE CASCADE,

            CONSTRAINT ck_funil_envios_status
                CHECK (status IN ('pending', 'processing', 'sent')),

            CONSTRAINT ck_funil_envios_attempt_count
                CHECK (attempt_count >= 0)
        );

        CREATE INDEX IF NOT EXISTS idx_funil_envios_disponiveis
        ON chatbot.funil_envios (
            status,
            next_attempt_at,
            processing_started_at,
            id_funil_envio
        )
        WHERE status IN ('pending', 'processing');
        """)

    logger.info("banco_setup_ok | acao=criar_tabelas")


def configurar_role_banco():
    """Aplica timezone e limites operacionais da role em uma transação."""
    with transacao_deploy("configurar_role_banco", logger) as cursor:
        cursor.execute("""
            ALTER ROLE fushi
            SET timezone TO 'America/Sao_Paulo';

            ALTER ROLE fushi
            SET idle_in_transaction_session_timeout = '30min';

            ALTER ROLE fushi
            SET statement_timeout = '10min';

            ALTER ROLE fushi
            SET lock_timeout = '15s';
        """)

    logger.info("banco_setup_ok | acao=configurar_role_banco role=fushi")
```

A restrição final é `CHECK (turnos_sem_avanco BETWEEN 0 AND 12)`. O SQL do
RDS existente será preparado no deploy.

---

## Passo 2 — espelhar a coluna no model unmanaged

### Arquivo final completo: `callback/webhook/models.py`

```python

from django.db import models


class Cliente(models.Model):
    id_cliente = models.AutoField(primary_key=True)
    nome = models.CharField(max_length=200, blank=True, null=True)
    waid_telefone = models.CharField(unique=True, max_length=50)
    email = models.CharField(unique=True, max_length=200, blank=True, null=True)
    idade = models.IntegerField(blank=True, null=True)

    def __str__(self):
        return self.nome or self.waid_telefone

    class Meta:
        managed = False
        db_table = 'cliente'


class Dependente(models.Model):
    id_dependente = models.AutoField(primary_key=True)
    id_cliente = models.ForeignKey(
        Cliente,
        models.CASCADE,
        db_column='id_cliente',
        related_name='dependentes',
    )
    id_conversa = models.ForeignKey(
        'Conversa',
        models.CASCADE,
        db_column='id_conversa',
        related_name='dependentes_atendidos',
        blank=True,
        null=True,
    )
    nome_dependente = models.CharField(max_length=200, blank=True, null=True)
    idade = models.IntegerField(blank=True, null=True)

    def __str__(self):
        return self.nome_dependente or str(self.id_dependente)

    class Meta:
        managed = False
        db_table = 'dependente'


class Conversa(models.Model):
    id_conversa = models.AutoField(primary_key=True)
    id_cliente = models.ForeignKey(Cliente, models.DO_NOTHING, db_column='id_cliente')
    id_unidade = models.ForeignKey('Unidade', models.DO_NOTHING, db_column='id_unidade')
    id_etapa_atual = models.ForeignKey('Etapa', models.DO_NOTHING, db_column='id_etapa_atual', blank=True, null=True)
    status_ativa = models.BooleanField(default=True)
    status_dependente = models.BooleanField(blank=True, null=True, default=False)
    last_interaction_at = models.DateTimeField(blank=True, null=True)
    last_message_from = models.CharField(
        max_length=10,
        blank=True,
        null=True,
        choices=[("cliente", "cliente"), ("bot", "bot")],
    )
    followup_stage = models.IntegerField(blank=True, null=True, default=0)
    followup_last_sent_at = models.DateTimeField(blank=True, null=True)
    lead_no_funil = models.BooleanField(blank=True, null=True, default=False)
    processing = models.BooleanField(blank=True, null=True, default=False)
    processing_started_at = models.DateTimeField(blank=True, null=True)
    lock_version = models.IntegerField(blank=True, null=True, default=0)
    turnos_sem_avanco = models.IntegerField(default=0)
    iniciou_em = models.DateTimeField()
    finalizou_em = models.DateTimeField(blank=True, null=True)
    motivo_encerramento = models.CharField(
        max_length=30,
        blank=True,
        null=True,
        choices=[
            ("idade_invalida", "Idade inválida"),
            ("foi_agendado", "Foi agendado"),
        ],
    )

    class Meta:
        managed = False
        db_table = 'conversa'


class Etapa(models.Model):
    id_etapa = models.AutoField(primary_key=True)
    nome_etapa = models.CharField(unique=True, max_length=100)
    encerra_automaticamente = models.BooleanField(default=False)
    bloqueio_dias = models.PositiveIntegerField(default=0)
    elegivel_funil = models.BooleanField(default=False)

    class Meta:
        managed = False
        db_table = 'etapa'


class FilaMensagens(models.Model):
    id_mensagem = models.AutoField(primary_key=True)
    id_conversa = models.ForeignKey(
        Conversa,
        models.SET_NULL,
        db_column='id_conversa',
        blank=True,
        null=True,
    )
    status = models.CharField(
        max_length=20,
        default="pending",
        choices=[
            ("pending", "pending"),
            ("processing", "processing"),
            ("sent", "sent"),
            ("failed", "failed"),
        ],
    )
    retry_count = models.IntegerField(blank=True, null=True, default=0)
    next_attempt_at = models.DateTimeField(blank=True, null=True)
    processing_started_at = models.DateTimeField(blank=True, null=True)
    received_data_hora = models.DateTimeField()
    cliente_telefone = models.CharField(max_length=100)
    conteudo_texto = models.TextField(blank=True, null=True)
    tipo_mensagem = models.CharField(max_length=20)
    id_hash_msg = models.CharField(unique=True, max_length=255)
    id_phone_unidade = models.CharField(max_length=100)
    unidade_telefone = models.CharField(max_length=100)
    last_error = models.TextField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'fila_mensagens'


class HistoricoMensagens(models.Model):
    id_mensagem = models.AutoField(primary_key=True)

    id_conversa = models.ForeignKey(
        Conversa,
        models.DO_NOTHING,
        db_column='id_conversa'
    )

    id_etapa = models.ForeignKey(
        Etapa,
        models.DO_NOTHING,
        db_column='id_etapa',
        blank=True,
        null=True
    )

    received_data_hora = models.DateTimeField()

    cliente_telefone = models.CharField(max_length=100)
    conteudo_texto = models.TextField(blank=True, null=True)
    tipo_mensagem = models.CharField(max_length=20)
    id_hash_msg = models.CharField(max_length=255)
    id_mensagem_fila = models.ForeignKey(
        FilaMensagens,
        models.SET_NULL,
        db_column='id_mensagem_fila',
        blank=True,
        null=True,
        related_name='historicos_originados',
    )
    id_hash_cliente_origem = models.CharField(max_length=255, blank=True, null=True)
    id_phone_unidade = models.CharField(max_length=100)
    unidade_telefone = models.CharField(max_length=100)
    quem_enviou = models.CharField(
        max_length=10,
        choices=[
            ("cliente", "cliente"),
            ("bot", "bot"),
        ],
    )
    status_envio = models.CharField(
        max_length=20,
        blank=True,
        null=True,
        choices=[
            ("pending", "pending"),
            ("sent", "sent"),
            ("failed", "failed"),
        ],
    )

    class Meta:
        managed = False
        db_table = 'historico_mensagens'
        constraints = [
            models.UniqueConstraint(
                fields=["id_mensagem", "received_data_hora"],
                name="uq_historico_mensagens_id_data",
            ),
        ]


class RespostasDesafios(models.Model):
    id_resposta_desafio = models.AutoField(primary_key=True)
    id_conversa = models.ForeignKey(
        Conversa,
        models.CASCADE,
        db_column='id_conversa',
        related_name='respostas_desafios',
    )
    id_etapa = models.ForeignKey(
        Etapa,
        models.DO_NOTHING,
        db_column='id_etapa',
        related_name='respostas_desafios',
    )
    resposta = models.CharField(max_length=20)
    id_historico_mensagem_cliente = models.IntegerField(blank=True, null=True)
    criado_em = models.DateTimeField()

    class Meta:
        managed = False
        db_table = 'respostas_desafios'
        constraints = [
            models.UniqueConstraint(
                fields=["id_conversa", "id_etapa"],
                name="uq_respostas_desafios_conversa_etapa",
            ),
        ]


class PesquisaSatisfacao(models.Model):
    id_pesquisa_satisfacao = models.AutoField(primary_key=True)
    id_conversa = models.OneToOneField(
        Conversa,
        models.CASCADE,
        db_column='id_conversa',
        related_name='pesquisa_satisfacao',
    )
    nota = models.PositiveSmallIntegerField(blank=True, null=True)
    comentario = models.TextField(blank=True, null=True)
    criado_em = models.DateTimeField()
    atualizado_em = models.DateTimeField()

    class Meta:
        managed = False
        db_table = 'pesquisa_satisfacao'
        verbose_name = 'Pesquisa de satisfação'
        verbose_name_plural = 'Pesquisas de satisfação'


class Unidade(models.Model):
    id_unidade = models.AutoField(primary_key=True)
    nome = models.CharField(unique=True, max_length=300)
    cnpj = models.CharField(unique=True, max_length=50)
    email_responsavel = models.CharField(unique=True, max_length=255)
    telefone = models.CharField(unique=True, max_length=20)
    numero_comercial = models.CharField(
        max_length=30,
        blank=True,
        null=True,
    )
    waba_id = models.CharField(
        unique=True,
        max_length=100,
    )
    phone_number_id = models.CharField(unique=True, max_length=100)
    link_agendamento = models.CharField(unique=True, max_length=400)
    link_instagram = models.CharField(
        max_length=400,
        blank=True,
        null=True,
    )
    bpa_ativo = models.BooleanField(default=False)
    status_pagamento = models.BooleanField(blank=True, null=True, default=True)

    def __str__(self):
        return self.nome

    class Meta:
        managed = False
        db_table = 'unidade'


class IntegracaoFunilUnidade(models.Model):
    id_integracao_funil = models.AutoField(primary_key=True)
    id_unidade = models.OneToOneField(
        Unidade,
        models.CASCADE,
        db_column='id_unidade',
        related_name='integracao_funil',
    )
    nome_widget = models.CharField(max_length=300)
    data_salvamento_widget = models.DateField(blank=True, null=True)
    codigo_widget = models.CharField(unique=True, max_length=100)
    link_api_carrossel = models.URLField(unique=True, max_length=500)
    codigo_canal_venda = models.CharField(max_length=100)
    widget_ativo = models.BooleanField(default=True)
    integracao_ativa = models.BooleanField(default=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.id_unidade} / {self.nome_widget}"

    class Meta:
        managed = False
        db_table = 'integracao_funil_unidade'
        verbose_name = 'Integração do Funil por unidade'
        verbose_name_plural = 'Integrações do Funil por unidade'


class FunilEnvio(models.Model):
    id_funil_envio = models.AutoField(primary_key=True)
    id_conversa = models.OneToOneField(
        Conversa,
        models.CASCADE,
        db_column='id_conversa',
        related_name='envio_funil',
    )
    status = models.CharField(
        max_length=20,
        default='pending',
        choices=[
            ('pending', 'pending'),
            ('processing', 'processing'),
            ('sent', 'sent'),
        ],
    )
    attempt_count = models.IntegerField(default=0)
    next_attempt_at = models.DateTimeField()
    processing_started_at = models.DateTimeField(blank=True, null=True)
    enviado_em = models.DateTimeField(blank=True, null=True)
    ultimo_erro = models.TextField(blank=True, null=True)
    resposta_funil = models.TextField(blank=True, null=True)
    criado_em = models.DateTimeField()
    atualizado_em = models.DateTimeField()

    class Meta:
        managed = False
        db_table = 'funil_envios'
        verbose_name = 'Envio ao Funil'
        verbose_name_plural = 'Envios ao Funil'


class ClienteBloqueadoMeta(models.Model):
    id_bloqueio = models.AutoField(primary_key=True)
    id_cliente = models.ForeignKey(
        Cliente,
        models.SET_NULL,
        db_column='id_cliente',
        blank=True,
        null=True,
        related_name='bloqueios_meta',
    )
    nome = models.CharField(max_length=200, blank=True, null=True)
    wa_id_cliente = models.CharField(max_length=50)
    id_unidade = models.ForeignKey(
        Unidade,
        models.DO_NOTHING,
        db_column='id_unidade',
        related_name='bloqueios_meta',
    )
    phone_id_unidade = models.CharField(max_length=100)

    def __str__(self):
        return f"{self.wa_id_cliente} / {self.phone_id_unidade}"

    class Meta:
        managed = False
        db_table = 'cliente_bloqueado_meta'
        constraints = [
            models.UniqueConstraint(
                fields=["wa_id_cliente", "id_unidade"],
                name="uq_cliente_bloqueado_meta_wa_unidade",
            ),
        ]


class WebhookFloodEvento(models.Model):
    id_evento = models.BigAutoField(primary_key=True)
    wa_id_cliente = models.CharField(max_length=50)
    phone_id_unidade = models.CharField(max_length=100)
    id_hash_msg = models.CharField(unique=True, max_length=255)
    received_at = models.DateTimeField()

    def __str__(self):
        return f"{self.wa_id_cliente} / {self.phone_id_unidade}"

    class Meta:
        managed = False
        db_table = 'webhook_flood_evento'


class CacheControle(models.Model):
    nome = models.CharField(primary_key=True, max_length=100)
    versao = models.BigIntegerField(default=1)
    atualizado_em = models.DateTimeField()

    def __str__(self):
        return self.nome

    class Meta:
        managed = False
        db_table = 'cache_controle'
```

`managed = False` mantém o DDL como fonte da verdade.

---

## Passo 3 — exibir e recuperar falsos positivos no Django Admin

### Arquivo final completo: `callback/webhook/admin.py`

```python

import logging

from django.contrib import admin, messages
from django.db import DatabaseError, connection
from django.http import HttpResponseRedirect
from django.urls import NoReverseMatch, reverse
from django.utils.html import format_html

from core.cache.cache_unidade import (
    CacheUnidadesIndisponivel,
    recarregar_cache_unidades_ou_erro,
    validar_cache_unidades_disponivel_ou_erro,
)
from core.integrations.whatsapp.tools.ativando_numero import registrar_numero_whatsapp
from core.integrations.whatsapp.tools.ativando_waba_id import ativar_waba_id
from core.integrations.whatsapp.tools.desativa_waba_id import desativar_waba_id
from core.integrations.whatsapp.tools.desativando_numero import desregistrar_numero_whatsapp
from core.integrations.whatsapp.tools.usuarios import (
    desbloquear_usuario_meta,
)
from core.integrations.whatsapp.tools.validando_phone_waba import (
    validar_phone_number_id_da_waba,
)
from core.logging_config import short_value
from core.repositories.unidades.cache_control import (
    incrementar_versao_cache_unidades,
)

from .models import (
    CacheControle,
    Cliente,
    ClienteBloqueadoMeta,
    Conversa,
    Dependente,
    Etapa,
    FilaMensagens,
    FunilEnvio,
    HistoricoMensagens,
    IntegracaoFunilUnidade,
    PesquisaSatisfacao,
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


@admin.register(IntegracaoFunilUnidade)
class IntegracaoFunilUnidadeAdmin(admin.ModelAdmin):
    list_display = (
        "id_integracao_funil",
        "id_unidade",
        "nome_widget",
        "codigo_widget",
        "codigo_canal_venda",
        "widget_ativo",
        "integracao_ativa",
        "data_salvamento_widget",
        "atualizado_em",
    )

    search_fields = (
        "id_unidade__nome",
        "nome_widget",
        "codigo_widget",
        "codigo_canal_venda",
        "link_api_carrossel",
    )

    list_filter = (
        "widget_ativo",
        "integracao_ativa",
        "data_salvamento_widget",
    )

    readonly_fields = (
        "criado_em",
        "atualizado_em",
    )

    ordering = ("id_unidade",)
    list_select_related = ("id_unidade",)
    list_per_page = 50
    empty_value_display = "-"


@admin.register(FunilEnvio)
class FunilEnvioAdmin(SomenteVisualizacaoAdminMixin, admin.ModelAdmin):
    list_display = (
        "id_funil_envio",
        "id_conversa",
        "status",
        "attempt_count",
        "next_attempt_at",
        "processing_started_at",
        "enviado_em",
        "atualizado_em",
    )
    search_fields = (
        "id_conversa__id_conversa",
        "id_conversa__id_cliente__nome",
        "id_conversa__id_cliente__waid_telefone",
    )
    list_filter = ("status",)
    ordering = ("-atualizado_em",)
    date_hierarchy = "criado_em"
    list_select_related = (
        "id_conversa",
        "id_conversa__id_cliente",
    )
    list_per_page = 50
    empty_value_display = "-"


@admin.register(Unidade)
class UnidadeAdmin(admin.ModelAdmin):

    list_display = (
        "id_unidade",
        "nome",
        "cnpj",
        "telefone",
        "numero_comercial",
        "email_responsavel",
        "waba_id",
        "phone_number_id",
        "link_agendamento_clickable",
        "link_instagram_clickable",
        "bpa_ativo",
        "status_pagamento",
    )

    search_fields = (
        "nome",
        "cnpj",
        "telefone",
        "numero_comercial",
        "email_responsavel",
        "waba_id",
        "phone_number_id",
        "link_agendamento",
        "link_instagram",
    )

    list_filter = ("bpa_ativo", "status_pagamento")
    ordering = ("nome",)

    list_per_page = 50
    empty_value_display = "-"

    def get_readonly_fields(self, request, obj=None):
        if obj is not None:
            return ("waba_id", "phone_number_id")

        return ()

    def changeform_view(self, request, object_id=None, form_url="", extra_context=None):
        try:
            return super().changeform_view(
                request,
                object_id=object_id,
                form_url=form_url,
                extra_context=extra_context,
            )

        except CacheUnidadesIndisponivel as exc:
            if self._falha_cache_originada_no_banco(exc):
                return self._responder_falha_banco(
                    request,
                    object_id,
                    exc,
                )

            logger.exception(
                "admin_unidade_cache_falhou | acao=rollback_admin object_id=%s meta_ok=%s erro=%s",
                object_id,
                self._meta_sucesso_nesta_requisicao(request),
                exc,
            )
            self.message_user(
                request,
                self._mensagem_falha_redis(request),
                level=messages.ERROR,
            )
            return HttpResponseRedirect(request.path)

        except DatabaseError as exc:
            return self._responder_falha_banco(
                request,
                object_id,
                exc,
            )

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

                waba_id = self.cleaned_data.get("waba_id")
                phone_number_id = self.cleaned_data.get("phone_number_id")

                if not waba_id:
                    self.add_error(
                        "waba_id",
                        "Informe a WABA que sera assinada pelo App.",
                    )
                    return

                campo_com_erro = model_admin._preparar_meta_antes_de_salvar(
                    request,
                    waba_id,
                    phone_number_id,
                )

                if campo_com_erro == "vinculo_waba_phone":
                    self.add_error(
                        "phone_number_id",
                        "Este phone ID nao pertence a WABA informada. "
                        "A unidade nao foi salva.",
                    )
                    return

                if campo_com_erro == "waba_id":
                    self.add_error(
                        "waba_id",
                        "A Meta falhou ao assinar esta WABA. Unidade nao foi salva.",
                    )
                    return

                if campo_com_erro == "phone_number_id":
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
            if self._falha_cache_originada_no_banco(exc):
                return self._responder_falha_banco_delete(
                    request,
                    object_id,
                    exc,
                )

            logger.exception(
                "admin_unidade_cache_delete_falhou | acao=rollback_admin object_id=%s meta_ok=%s erro=%s",
                object_id,
                self._meta_sucesso_nesta_requisicao(request),
                exc,
            )
            self.message_user(
                request,
                self._mensagem_falha_redis(request),
                level=messages.ERROR,
            )
            return HttpResponseRedirect(
                reverse(
                    "admin:webhook_unidade_change",
                    args=[object_id],
                )
            )

        except DatabaseError as exc:
            return self._responder_falha_banco_delete(
                request,
                object_id,
                exc,
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

    def link_instagram_clickable(self, obj):
        if obj.link_instagram:
            return format_html(
                '<a href="{}" target="_blank">Abrir</a>',
                obj.link_instagram,
            )
        return "-"

    link_instagram_clickable.short_description = "Instagram"

    def _preparar_meta_antes_de_salvar(
        self,
        request,
        waba_id,
        phone_number_id,
    ):
        if not self._validar_vinculo_phone_waba_antes_de_salvar(
            request,
            waba_id,
            phone_number_id,
        ):
            return "vinculo_waba_phone"

        if not self._ativar_waba_antes_de_salvar(request, waba_id):
            return "waba_id"

        if not self._registrar_meta_antes_de_salvar(
            request,
            phone_number_id,
        ):
            return "phone_number_id"

        return None

    def _validar_vinculo_phone_waba_antes_de_salvar(
        self,
        request,
        waba_id,
        phone_number_id,
    ):
        try:
            status, resposta = validar_phone_number_id_da_waba(
                waba_id,
                phone_number_id,
            )

            if not self._meta_resposta_sucesso(status, resposta):
                logger.error(
                    "whatsapp_phone_waba_vinculo_invalido | "
                    "acao=bloquear_save waba_id=%s phone_number_id=%s "
                    "status=%s motivo=%s",
                    short_value(waba_id),
                    short_value(phone_number_id),
                    status,
                    resposta.get("reason")
                    if isinstance(resposta, dict)
                    else None,
                )
                self.message_user(
                    request,
                    "A Meta nao confirmou que o phone ID pertence a "
                    "WABA informada. A unidade nao foi salva.",
                    level=messages.ERROR,
                )
                return False

            logger.info(
                "whatsapp_phone_waba_vinculo_ok | "
                "acao=permitir_ativacao waba_id=%s phone_number_id=%s",
                short_value(waba_id),
                short_value(phone_number_id),
            )
            return True

        except Exception as exc:
            logger.exception(
                "whatsapp_phone_waba_validacao_erro | "
                "acao=bloquear_save waba_id=%s phone_number_id=%s "
                "erro=%s",
                short_value(waba_id),
                short_value(phone_number_id),
                exc,
            )
            self.message_user(
                request,
                "Erro ao validar WABA e phone ID na Meta. "
                f"A unidade nao foi salva: {exc}",
                level=messages.ERROR,
            )
            return False

    def _ativar_waba_antes_de_salvar(self, request, waba_id):
        try:
            status, resposta = ativar_waba_id(waba_id)

            if not self._meta_resposta_sucesso(status, resposta):
                logger.error(
                    "whatsapp_waba_ativar_falhou | acao=bloquear_save "
                    "waba_id=%s status=%s resposta=%s",
                    short_value(waba_id),
                    status,
                    resposta,
                )
                self.message_user(
                    request,
                    "Erro ao assinar WABA no WhatsApp. "
                    f"Unidade nao foi salva: {resposta}",
                    level=messages.ERROR,
                )
                return False

            self._marcar_meta_sucesso(
                request,
                acao="ativar_waba",
                waba_id=waba_id,
            )
            logger.info(
                "whatsapp_waba_ativada | acao=permitir_registro_numero "
                "waba_id=%s status=%s",
                short_value(waba_id),
                status,
            )
            return True

        except Exception as exc:
            logger.exception(
                "whatsapp_waba_ativar_erro | acao=bloquear_save "
                "waba_id=%s erro=%s",
                short_value(waba_id),
                exc,
            )
            self.message_user(
                request,
                "Erro inesperado ao assinar WABA. "
                f"Unidade nao foi salva: {exc}",
                level=messages.ERROR,
            )
            return False

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

            self._marcar_meta_sucesso(
                request,
                acao="registrar_numero",
                phone_number_id=phone_number_id,
            )
            logger.info(
                "whatsapp_numero_registrado | acao=permitir_save phone_number_id=%s status=%s",
                short_value(phone_number_id),
                status,
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
        if not self._desassinar_waba_antes_de_excluir(request, obj):
            return False

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
                    "A WABA foi desassinada, mas a Meta falhou ao "
                    "desregistrar o numero. Unidade mantida no banco: "
                    f"{resposta}",
                    level=messages.ERROR,
                )
                return False

            self._marcar_meta_sucesso(
                request,
                acao="desregistrar_numero",
                phone_number_id=obj.phone_number_id,
            )
            logger.warning(
                "whatsapp_numero_desregistrado | acao=permitir_delete phone_number_id=%s status=%s",
                short_value(obj.phone_number_id),
                status,
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
                "A WABA foi desassinada, mas ocorreu um erro ao "
                "desregistrar o numero. Unidade mantida no banco: "
                f"{exc}",
                level=messages.ERROR,
            )
            return False

    def _desassinar_waba_antes_de_excluir(self, request, obj):
        try:
            status, resposta = desativar_waba_id(obj.waba_id)

            if not self._meta_resposta_sucesso(status, resposta):
                logger.error(
                    "whatsapp_waba_desassinar_falhou | "
                    "acao=bloquear_delete waba_id=%s status=%s "
                    "resposta=%s",
                    short_value(obj.waba_id),
                    status,
                    resposta,
                )
                self.message_user(
                    request,
                    "Erro ao remover a assinatura da WABA na Meta. "
                    f"Unidade mantida no banco: {resposta}",
                    level=messages.ERROR,
                )
                return False

            self._marcar_meta_sucesso(
                request,
                acao="desativar_waba",
                waba_id=obj.waba_id,
            )
            logger.warning(
                "whatsapp_waba_desassinada | acao=continuar_delete "
                "waba_id=%s status=%s",
                short_value(obj.waba_id),
                status,
            )
            return True

        except Exception as exc:
            logger.exception(
                "whatsapp_waba_desassinar_erro | "
                "acao=bloquear_delete waba_id=%s erro=%s",
                short_value(obj.waba_id),
                exc,
            )
            self.message_user(
                request,
                "Erro inesperado ao remover a assinatura da WABA. "
                f"Unidade mantida no banco: {exc}",
                level=messages.ERROR,
            )
            return False

    def _marcar_meta_sucesso(
        self,
        request,
        acao,
        **identificadores,
    ):
        operacoes = list(
            getattr(request, "_unidade_meta_sucesso", [])
        )
        operacoes.append({
            "acao": acao,
            **{
                nome: str(valor)
                for nome, valor in identificadores.items()
            },
        })
        request._unidade_meta_sucesso = operacoes

    @staticmethod
    def _meta_sucesso_nesta_requisicao(request):
        return bool(
            getattr(
                request,
                "_unidade_meta_sucesso",
                None,
            )
        )

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

    def _responder_falha_banco(
        self,
        request,
        object_id,
        exc,
    ):
        logger.exception(
            "admin_unidade_banco_falhou | acao=rollback_sem_compensacao object_id=%s meta_ok=%s erro=%s",
            object_id,
            self._meta_sucesso_nesta_requisicao(request),
            exc,
        )
        self.message_user(
            request,
            self._mensagem_falha_banco(request),
            level=messages.ERROR,
        )
        return HttpResponseRedirect(request.path)

    def _responder_falha_banco_delete(
        self,
        request,
        object_id,
        exc,
    ):
        logger.exception(
            "admin_unidade_banco_delete_falhou | acao=rollback_sem_compensacao object_id=%s meta_ok=%s erro=%s",
            object_id,
            self._meta_sucesso_nesta_requisicao(request),
            exc,
        )
        self.message_user(
            request,
            self._mensagem_falha_banco(request),
            level=messages.ERROR,
        )
        return HttpResponseRedirect(
            reverse(
                "admin:webhook_unidade_change",
                args=[object_id],
            )
        )

    def _mensagem_falha_banco(self, request):
        if self._meta_sucesso_nesta_requisicao(request):
            return (
                "A Meta concluiu a operação com sucesso, mas o banco "
                "falhou. A alteração da Meta foi mantida; banco e "
                "cache de unidades no Redis não foram confirmados. Faça uma "
                "conferência manual."
            )

        return (
            "O banco falhou e nenhuma alteração local foi "
            "confirmada. Nenhuma operação Meta foi concluída nesta "
            "requisição."
        )

    def _mensagem_falha_redis(self, request):
        if self._meta_sucesso_nesta_requisicao(request):
            return (
                "A Meta concluiu a operação com sucesso, mas o Redis "
                "falhou. A alteração da Meta foi mantida; nenhuma "
                "alteração foi confirmada no banco ou no cache. Faça "
                "uma conferência manual."
            )

        return (
            "O Redis falhou ao atualizar o cache de unidades. "
            "Nenhuma alteração foi confirmada no banco."
        )

    @staticmethod
    def _mensagem_cache_unidades_falhou(meta_validada):
        if meta_validada:
            return (
                "A Meta concluiu a operação com sucesso, mas o Redis "
                "falhou. A alteração da Meta foi mantida e a unidade "
                "não foi salva no banco. Faça uma conferência manual."
            )

        return (
            "O Redis falhou ao atualizar o cache de unidades. "
            "Nenhuma alteração foi feita no banco."
        )

    @staticmethod
    def _falha_cache_originada_no_banco(exc):
        causa = exc.__cause__

        while causa is not None:
            if isinstance(causa, DatabaseError):
                return True

            causa = causa.__cause__

        return False

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
        "idade",
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
        "id_conversa",
        "nome_dependente",
        "idade",
    )

    search_fields = (
        "nome_dependente",
        "id_cliente__waid_telefone",
        "id_cliente__nome",
    )

    ordering = ("id_dependente",)
    list_per_page = 50
    empty_value_display = "-"

    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            "id_cliente",
            "id_conversa",
        )


@admin.register(Etapa)
class EtapaAdmin(SomenteVisualizacaoAdminMixin, admin.ModelAdmin):

    list_display = (
        "id_etapa",
        "nome_etapa",
        "encerra_automaticamente",
        "bloqueio_dias",
        "elegivel_funil",
    )

    search_fields = ("nome_etapa",)
    list_filter = (
        "encerra_automaticamente",
        "elegivel_funil",
    )
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
        "turnos_sem_avanco",
        "status_ativa",
        "motivo_encerramento",
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
        "motivo_encerramento",
        "turnos_sem_avanco",
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
        except NoReverseMatch as exc:
            logger.exception(
                "admin_cliente_link_falhou | acao=retornar_texto_sem_link erro=%s",
                exc,
            )
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


@admin.register(PesquisaSatisfacao)
class PesquisaSatisfacaoAdmin(SomenteVisualizacaoAdminMixin, admin.ModelAdmin):

    list_display = (
        "id_pesquisa_satisfacao",
        "id_conversa",
        "nota",
        "comentario",
        "criado_em",
        "atualizado_em",
    )

    search_fields = (
        "id_conversa__id_conversa",
        "id_conversa__id_cliente__nome",
        "comentario",
    )

    list_filter = ("nota",)
    ordering = ("-atualizado_em",)
    date_hierarchy = "atualizado_em"
    list_per_page = 50
    empty_value_display = "-"

    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            "id_conversa",
            "id_conversa__id_cliente",
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
        "nome",
        "wa_id_cliente",
        "id_unidade",
        "phone_id_unidade",
    )

    search_fields = (
        "nome",
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
        conversas_resetadas = Conversa.objects.filter(
            id_cliente_id=obj.id_cliente_id,
            id_unidade_id=obj.id_unidade_id,
            status_ativa=True,
        ).update(turnos_sem_avanco=0)

        logger.warning(
            "admin_bloqueio_meta_excluido | "
            "acao=resetar_contador_e_excluir_registro "
            "usuario=%s wa_id_cliente=%s phone_id_unidade=%s "
            "conversas_resetadas=%s",
            request.user,
            short_value(obj.wa_id_cliente),
            short_value(obj.phone_id_unidade),
            conversas_resetadas,
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
        except NoReverseMatch as exc:
            logger.exception(
                "admin_cliente_link_falhou | acao=retornar_texto_sem_link erro=%s",
                exc,
            )
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

Na exclusão unitária, a Meta é desbloqueada e, na transação local, a conversa
ativa é zerada antes do delete da denylist. A exclusão em massa segue proibida.

---

## Passo 4 — criar o repositório dos turnos sem avanço

### Arquivo final completo: `core/repositories/seguranca/suspeita_bot.py`

```python
import logging

from core.logging_config import short_value


logger = logging.getLogger("db.suspeita_bot")

LIMITE_TURNOS_SEM_AVANCO = 12


def incrementar_turnos_sem_avanco(id_conversa, cursor):
    cursor.execute("""
        UPDATE chatbot.conversa
        SET turnos_sem_avanco = LEAST(
            turnos_sem_avanco + 1,
            %s
        )
        WHERE id_conversa = %s
        RETURNING turnos_sem_avanco;
    """, (LIMITE_TURNOS_SEM_AVANCO, id_conversa))

    resultado = cursor.fetchone()

    if not resultado:
        raise ValueError(
            "Conversa ausente ao incrementar turnos sem avanço "
            f"(id_conversa={id_conversa})"
        )

    contador = int(resultado[0])
    logger.info(
        "turnos_sem_avanco_incrementados | acao=incrementar "
        "id_conversa=%s turnos_sem_avanco=%s limite=%s",
        id_conversa,
        contador,
        LIMITE_TURNOS_SEM_AVANCO,
    )
    return contador


def resetar_turnos_sem_avanco(id_conversa, cursor):
    cursor.execute("""
        UPDATE chatbot.conversa
        SET turnos_sem_avanco = 0
        WHERE id_conversa = %s
        RETURNING turnos_sem_avanco;
    """, (id_conversa,))

    resultado = cursor.fetchone()

    if not resultado:
        raise ValueError(
            "Conversa ausente ao resetar turnos sem avanço "
            f"(id_conversa={id_conversa})"
        )

    logger.info(
        "turnos_sem_avanco_resetados | acao=resetar "
        "id_conversa=%s turnos_sem_avanco=0",
        id_conversa,
    )
    return 0


def buscar_conversa_no_limite_sem_avanco(
    wa_id_cliente,
    phone_id_unidade,
    cursor,
):
    cursor.execute("""
        SELECT
            conversa.id_conversa,
            conversa.id_cliente,
            cliente.nome,
            conversa.id_unidade,
            unidade.phone_number_id,
            conversa.turnos_sem_avanco
        FROM chatbot.conversa AS conversa
        JOIN chatbot.cliente AS cliente
          ON cliente.id_cliente = conversa.id_cliente
        JOIN chatbot.unidade AS unidade
          ON unidade.id_unidade = conversa.id_unidade
        WHERE cliente.waid_telefone = %s
          AND unidade.phone_number_id = %s
          AND conversa.status_ativa = TRUE
          AND conversa.turnos_sem_avanco >= %s
        ORDER BY conversa.id_conversa DESC
        LIMIT 1;
    """, (
        wa_id_cliente,
        phone_id_unidade,
        LIMITE_TURNOS_SEM_AVANCO,
    ))

    resultado = cursor.fetchone()

    if not resultado:
        logger.debug(
            "turnos_sem_avanco_consulta | acao=seguir_fluxo "
            "wa_id_cliente=%s phone_id_unidade=%s limite=%s",
            short_value(wa_id_cliente),
            short_value(phone_id_unidade),
            LIMITE_TURNOS_SEM_AVANCO,
        )
        return None

    dados = {
        "id_conversa": resultado[0],
        "id_cliente": resultado[1],
        "nome_cliente": resultado[2],
        "id_unidade": resultado[3],
        "phone_id_unidade": resultado[4],
        "turnos_sem_avanco": int(resultado[5]),
    }
    logger.warning(
        "turnos_sem_avanco_limite_encontrado | "
        "acao=promover_para_denylist "
        "id_conversa=%s id_cliente=%s id_unidade=%s "
        "wa_id_cliente=%s phone_id_unidade=%s "
        "turnos_sem_avanco=%s limite=%s",
        dados["id_conversa"],
        dados["id_cliente"],
        dados["id_unidade"],
        short_value(wa_id_cliente),
        short_value(phone_id_unidade),
        dados["turnos_sem_avanco"],
        LIMITE_TURNOS_SEM_AVANCO,
    )
    return dados
```

Não há `FOR UPDATE` no hot-path: o upsert com chave única
`wa_id_cliente + id_unidade` torna promoções concorrentes idempotentes.

---

## Passo 5 — atualizar os turnos sem avanço na transação do worker

### Arquivo final completo: `workers/worker_flow/transacoes/persistencia_resposta.py`

```python
import logging

from core.repositories.atendimento.historico import inserir_historico_mensagem_bot
from core.repositories.seguranca.suspeita_bot import (
    incrementar_turnos_sem_avanco,
    resetar_turnos_sem_avanco,
)
from workers.worker_flow.transacoes.encerramento_atendimento import (
    resolver_intencao_encerramento,
)
from workers.worker_flow.transacoes.efeitos_transicao import (
    atualizar_banco_conforme_transicao_de_etapa,
)
from workers.worker_flow.transacoes.movimento_conversa import (
    MOVIMENTO_SEM_AVANCO,
    MOVIMENTO_TRANSICAO,
    persistir_movimento_conversa,
)


logger = logging.getLogger("worker.support")


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
    """
    Persiste o resultado completo do ciclo em uma única transação.

    Ordem preservada:
    1. registrar ou recuperar a resposta do bot;
    2. persistir inicialização, transição ou permanência;
    3. incrementar ou zerar a suspeita de bot;
    4. aplicar os efeitos específicos da aresta;
    5. devolver o contexto final para a finalização da fila.
    """
    id_conversa = contexto_historico["id_conversa"]
    id_etapa_resultante = contexto_envio.get("id_etapa_resultante")
    resposta_ja_existia = bool(
        contexto_envio.get("resposta_ja_existia")
    )

    (
        id_historico_bot,
        data_interacao_bot,
        historico_bot_inserido,
    ) = _persistir_ou_recuperar_resposta_bot(
        contexto_historico,
        contexto_envio,
        cursor,
    )

    movimento = persistir_movimento_conversa(
        contexto_historico,
        contexto_envio,
        data_interacao_bot,
        cursor,
    )

    turnos_sem_avanco = _persistir_turnos_sem_avanco(
        id_conversa=id_conversa,
        movimento=movimento,
        tratamento=bool(contexto_envio.get("tratamento")),
        historico_bot_inserido=historico_bot_inserido,
        cursor=cursor,
    )

    efeitos_transicao = atualizar_banco_conforme_transicao_de_etapa(
        contexto_historico,
        contexto_envio,
        cursor,
    )
    intencao_encerramento = resolver_intencao_encerramento(
        contexto_historico,
        contexto_envio,
        cursor,
    )

    logger.info(
        "resposta_bot_persistida | "
        "acao=registrar_historico_e_contexto "
        "id_conversa=%s id_historico_bot=%s inserido=%s "
        "resposta_ja_existia=%s movimento=%s etapa=%s evento=%s "
        "id_hash_msg_bot=%s turnos_sem_avanco=%s",
        id_conversa,
        id_historico_bot,
        historico_bot_inserido,
        resposta_ja_existia,
        movimento,
        id_etapa_resultante,
        contexto_envio.get("evento_transicao"),
        contexto_envio.get("id_hash_msg_bot"),
        turnos_sem_avanco,
    )

    contexto_final = {
        "historico_bot_inserido": historico_bot_inserido,
        "resposta_ja_existia": resposta_ja_existia,
        "id_hash_msg_bot": contexto_envio.get("id_hash_msg_bot"),
        "id_etapa_resultante": id_etapa_resultante,
        "movimento_conversa": movimento,
        "atualizar_conversa": movimento != MOVIMENTO_SEM_AVANCO,
        "atualizar_last_from_bot": True,
        "intencao_encerramento": intencao_encerramento,
    }

    if turnos_sem_avanco is not None:
        contexto_final["turnos_sem_avanco"] = turnos_sem_avanco

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


def _persistir_turnos_sem_avanco(
    *,
    id_conversa,
    movimento,
    tratamento,
    historico_bot_inserido,
    cursor,
):
    if movimento == MOVIMENTO_TRANSICAO:
        return resetar_turnos_sem_avanco(id_conversa, cursor)

    if (
        movimento == MOVIMENTO_SEM_AVANCO
        and tratamento
        and historico_bot_inserido
    ):
        return incrementar_turnos_sem_avanco(id_conversa, cursor)

    return None


def _persistir_ou_recuperar_resposta_bot(
    contexto_historico,
    contexto_envio,
    cursor,
):
    if contexto_envio.get("resposta_ja_existia"):
        return (
            None,
            _obter_data_interacao_bot_existente(contexto_historico),
            False,
        )

    if not contexto_envio.get("enviou"):
        raise ValueError(
            "Contexto de envio sem resposta enviada e sem resposta existente"
        )

    return inserir_historico_mensagem_bot(
        contexto_historico,
        contexto_envio,
        cursor,
    )
```

Só histórico novo incrementa; retry não incrementa; transição reseta.

---

## Passo 6 — promover o limite para a denylist no webhook

### Arquivo final completo: `callback/webhook/services/bloqueio_meta_guard.py`

```python
import logging

from django.http import JsonResponse

from core.database.connection_aws import get_conn
from core.integrations.whatsapp.tools.usuarios import bloquear_usuario_meta
from core.logging_config import short_value
from core.repositories.seguranca.bloqueio_meta import (
    cliente_bloqueado_meta_existe_banco,
    registrar_cliente_bloqueado_meta_banco,
)
from core.repositories.seguranca.suspeita_bot import (
    buscar_conversa_no_limite_sem_avanco,
)


logger = logging.getLogger("webhook.bloqueio_meta_guard")


def responder_se_cliente_marcado_para_bloqueio(
    wa_id_cliente,
    phone_id_unidade,
    nome_cliente=None,
):
    """
    Intercepta a denylist existente ou promove uma conversa no limite.

    O banco é confirmado antes da chamada externa à Meta. Se a Meta recusar,
    a mensagem continua sendo ignorada e a próxima mensagem fará nova
    tentativa.
    """
    if not wa_id_cliente or not phone_id_unidade:
        return None

    consulta = _consultar_cliente_marcado_para_bloqueio(
        wa_id_cliente,
        phone_id_unidade,
        nome_cliente=nome_cliente,
    )

    if not consulta["banco_ok"]:
        return JsonResponse(
            {
                "status": "unavailable",
                "reason": "blocklist_validation_unavailable",
            },
            status=503,
        )

    if not consulta["marcado"]:
        return None

    meta_ok = False

    try:
        bloquear_usuario_meta(wa_id_cliente, phone_id_unidade)
        meta_ok = True
        logger.warning(
            "bloqueio_meta_reconfirmado | acao=bloquear_novamente "
            "wa_id_cliente=%s phone_id_unidade=%s",
            short_value(wa_id_cliente),
            short_value(phone_id_unidade),
        )

    except Exception as exc:
        logger.warning(
            "bloqueio_meta_retentativa_falhou | "
            "acao=ignorar_e_tentar_na_proxima_mensagem "
            "wa_id_cliente=%s phone_id_unidade=%s erro=%s",
            short_value(wa_id_cliente),
            short_value(phone_id_unidade),
            exc,
        )

    logger.warning(
        "mensagem_ignorada | motivo=cliente_marcado_bloqueio_meta "
        "acao=nao_enfileirar wa_id_cliente=%s phone_id_unidade=%s meta_ok=%s",
        short_value(wa_id_cliente),
        short_value(phone_id_unidade),
        meta_ok,
    )
    return JsonResponse({
        "status": "ignored",
        "reason": "cliente_marcado_bloqueio_meta",
    })


def _consultar_cliente_marcado_para_bloqueio(
    wa_id_cliente,
    phone_id_unidade,
    nome_cliente=None,
):
    conn = None

    try:
        conn = get_conn(application_name="webhook_chatbot")
        cursor = conn.cursor()

        marcado = cliente_bloqueado_meta_existe_banco(
            wa_id_cliente,
            phone_id_unidade,
            cursor,
        )

        if not marcado:
            suspeita = buscar_conversa_no_limite_sem_avanco(
                wa_id_cliente,
                phone_id_unidade,
                cursor,
            )

            if suspeita:
                id_bloqueio = registrar_cliente_bloqueado_meta_banco(
                    suspeita["id_cliente"],
                    wa_id_cliente,
                    suspeita["id_unidade"],
                    suspeita["phone_id_unidade"],
                    cursor,
                    nome_cliente=(
                        suspeita["nome_cliente"] or nome_cliente
                    ),
                )

                if not id_bloqueio:
                    raise RuntimeError(
                        "Promoção de suspeita não retornou id_bloqueio"
                    )

                marcado = True
                logger.warning(
                    "suspeita_bot_promovida | "
                    "acao=registrar_denylist_antes_da_meta "
                    "id_bloqueio=%s id_conversa=%s turnos_sem_avanco=%s "
                    "wa_id_cliente=%s phone_id_unidade=%s",
                    id_bloqueio,
                    suspeita["id_conversa"],
                    suspeita["turnos_sem_avanco"],
                    short_value(wa_id_cliente),
                    short_value(phone_id_unidade),
                )

        conn.commit()
        return {
            "banco_ok": True,
            "marcado": marcado,
        }

    except Exception as exc:
        if conn:
            conn.rollback()

        logger.exception(
            "bloqueio_meta_consulta_falhou | "
            "acao=retornar_503_para_reentrega "
            "wa_id_cliente=%s phone_id_unidade=%s erro=%s",
            short_value(wa_id_cliente),
            short_value(phone_id_unidade),
            exc,
        )
        return {
            "banco_ok": False,
            "marcado": False,
        }

    finally:
        if conn:
            conn.close()
```

O nome persistido tem precedência; o profile do payload é fallback persistido.

### Arquivo final completo acumulado após 0B: `callback/webhook/services/post_flow.py`

```python
import json
import logging

from django.conf import settings
from django.http import JsonResponse

from core.cache.runtime.cache_conversas_bloqueadas import (
    ValidacaoBloqueioConversaIndisponivel,
    conversa_esta_bloqueada_cache,
)
from core.cache.runtime.cache_webhook_erro_inesperado import (
    MAX_RESPOSTAS_503_POR_WAMID,
    registrar_tentativa_erro_inesperado,
)
from core.cache.cache_unidade import (
    ValidacaoUnidadeIndisponivel,
    unidade_esta_ativa,
)
from core.database.connection_aws import get_conn
from core.logging_config import short_value
from .bloqueio_meta_guard import (
    responder_se_cliente_marcado_para_bloqueio,
)
from .flood_guard import responder_se_flood
from .meta_signature import validar_assinatura_meta
from .populating_fila_mensagens import preparar_dados_fila, povoando_fila


logger = logging.getLogger("webhook.post_flow")
fila_logger = logging.getLogger("webhook.fila")

TIPO_EVENTO_MENSAGEM = "messages"
TIPO_EVENTO_STATUS = "statuses"
TIPO_EVENTO_DESCONHECIDO = "unknown"


def responder_post_webhook(request):
    print("\n\n\n-----------------------------------------------------------------NOVO EVENTO-----------------------------------------------------------------\n\n\n")

    if resposta := _validar_content_type(request):
        return resposta

    if resposta := _validar_tamanho_body(request):
        return resposta

    if not validar_assinatura_meta(request):
        logger.warning(
            "mensagem_ignorada | motivo=assinatura_meta_invalida acao=retornar_403 path=%s",
            request.path,
        )
        return JsonResponse({"status": "forbidden"}, status=403)

    try:
        data = json.loads(request.body.decode("utf-8"))

    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        logger.warning(
            "mensagem_ignorada | motivo=json_invalido acao=nao_enfileirar erro=%s",
            exc,
        )
        return JsonResponse({
            "status": "ignored",
            "reason": "invalid_json",
        })

    phone_number_id = None
    cliente_telefone = None

    try:
        tipo_evento = _classificar_evento_meta(data)

        if tipo_evento == TIPO_EVENTO_STATUS:
            return _responder_status_meta_sem_processar(data)

        if tipo_evento != TIPO_EVENTO_MENSAGEM:
            logger.info(
                "evento_meta_ignorado | motivo=evento_sem_messages_ou_statuses acao=retornar_200",
            )
            return JsonResponse({"status": "ok"})

        phone_number_id = _extrair_phone_number_id(data)
        cliente_telefone = _extrair_cliente_telefone(data)
        nome_cliente = _extrair_nome_cliente(data)

        if resposta_bloqueio := responder_se_cliente_marcado_para_bloqueio(
            cliente_telefone,
            phone_number_id,
            nome_cliente=nome_cliente,
        ):
            return resposta_bloqueio

        if resposta_flood := responder_se_flood(data):
            return resposta_flood

        if not unidade_esta_ativa(phone_number_id):
            logger.info(
                "mensagem_ignorada | motivo=unidade_inativa acao=nao_enfileirar cliente=%s phone_number_id=%s",
                short_value(cliente_telefone),
                short_value(phone_number_id),
            )
            return JsonResponse({"status": "ignored"})

        if cliente_telefone and conversa_esta_bloqueada_cache(
            cliente_telefone,
            phone_number_id,
        ):
            logger.info(
                "mensagem_ignorada | motivo=conversa_bloqueada acao=nao_enfileirar cliente=%s phone_number_id=%s",
                short_value(cliente_telefone),
                short_value(phone_number_id),
            )
            return JsonResponse({
                "status": "ignored",
                "reason": "blocked_conversation",
            })

        preparacao_fila = preparar_dados_fila(data)

        if preparacao_fila["status"] == "ready":
            resultado_fila = _executar_transacao_fila(preparacao_fila["dados"])

        else:
            resultado_fila = {
                "status": "ignored",
                "reason": preparacao_fila["reason"],
            }

        if resultado_fila["status"] == "inserted":
            logger.info(
                "request_processado | status=enfileirado acao=fila_insert cliente=%s phone_number_id=%s",
                short_value(cliente_telefone),
                short_value(phone_number_id),
            )

        elif resultado_fila["status"] == "ignored":
            logger.info(
                "mensagem_ignorada | motivo=%s acao=nao_enfileirar cliente=%s phone_number_id=%s",
                resultado_fila["reason"],
                short_value(cliente_telefone),
                short_value(phone_number_id),
            )

        else:
            logger.error(
                "request_indisponivel | motivo=%s acao=retornar_503_para_reentrega cliente=%s phone_number_id=%s",
                resultado_fila["reason"],
                short_value(cliente_telefone),
                short_value(phone_number_id),
            )
            return JsonResponse({
                "status": "unavailable",
                "reason": resultado_fila["reason"],
            }, status=503)

    except ValidacaoUnidadeIndisponivel as exc:
        logger.error(
            "request_indisponivel | motivo=validacao_unidade_indisponivel acao=retornar_503_para_reentrega cliente=%s phone_number_id=%s erro=%s",
            short_value(cliente_telefone),
            short_value(phone_number_id),
            exc,
        )
        return JsonResponse({
            "status": "unavailable",
            "reason": "unit_validation_unavailable",
        }, status=503)

    except ValidacaoBloqueioConversaIndisponivel as exc:
        logger.error(
            "request_indisponivel | motivo=validacao_bloqueio_conversa_indisponivel acao=retornar_503_para_reentrega cliente=%s phone_number_id=%s erro=%s",
            short_value(cliente_telefone),
            short_value(phone_number_id),
            exc,
        )
        return JsonResponse({
            "status": "unavailable",
            "reason": "conversation_block_validation_unavailable",
        }, status=503)

    except Exception as exc:
        id_hash_msg = _extrair_id_hash_msg_seguro(data)
        tentativa = registrar_tentativa_erro_inesperado(
            id_hash_msg,
        )

        if tentativa["retornar_503"]:
            logger.exception(
                "request_erro | "
                "acao=retornar_503_para_reentrega "
                "metodo=%s path=%s id_hash_msg=%s "
                "tentativa=%s limite_503=%s",
                request.method,
                request.path,
                short_value(id_hash_msg),
                tentativa["tentativa"],
                MAX_RESPOSTAS_503_POR_WAMID,
            )
            return JsonResponse(
                {
                    "status": "unavailable",
                    "reason": "unexpected_error_retry",
                    "attempt": tentativa["tentativa"],
                },
                status=503,
            )

        logger.error(
            "request_erro | "
            "acao=retornar_200_e_ignorar "
            "metodo=%s path=%s id_hash_msg=%s "
            "tentativa=%s motivo=%s",
            request.method,
            request.path,
            short_value(id_hash_msg),
            tentativa["tentativa"],
            tentativa["motivo"],
            exc_info=(
                type(exc),
                exc,
                exc.__traceback__,
            ),
        )
        reason = (
            "unexpected_error_retry_exhausted"
            if tentativa["motivo"]
            == "limite_503_esgotado"
            else "unexpected_error_retry_unavailable"
        )
        return JsonResponse({
            "status": "ignored",
            "reason": reason,
        })

    return JsonResponse({"status": "ok"})


def _classificar_evento_meta(data):
    value = _extrair_value(data)
    possui_mensagens = bool(value.get("messages"))
    possui_statuses = bool(value.get("statuses"))

    if possui_mensagens and not possui_statuses:
        return TIPO_EVENTO_MENSAGEM

    if possui_statuses and not possui_mensagens:
        return TIPO_EVENTO_STATUS

    return TIPO_EVENTO_DESCONHECIDO


def _responder_status_meta_sem_processar(data):
    statuses = _extrair_value(data).get("statuses") or []
    nomes_status = sorted({
        status.get("status")
        for status in statuses
        if status.get("status")
    })
    primeiro_status = statuses[0] if statuses else {}

    logger.info(
        "status_meta_recebido | acao=ignorar_na_v1 total=%s statuses=%s id_hash_msg_bot=%s",
        len(statuses),
        ",".join(nomes_status) or None,
        short_value(primeiro_status.get("id")),
    )
    return JsonResponse({"status": "ok"})


def _executar_transacao_fila(dados):
    conn_webhook = None

    try:
        conn_webhook = get_conn(application_name="webhook_chatbot")
        cursor_webhook = conn_webhook.cursor()
        resultado = povoando_fila(dados, cursor_webhook)
        conn_webhook.commit()

        if resultado["status"] == "inserted":
            fila_logger.info(
                "fila_insert_ok | acao=enfileirar id_msg=%s cliente=%s phone_number_id=%s tipo=%s",
                short_value(dados["id_hash_msg"]),
                short_value(dados["cliente_telefone"]),
                short_value(dados["id_phone_unidade"]),
                dados["tipo_mensagem"],
            )

        return resultado

    except Exception:
        if conn_webhook:
            conn_webhook.rollback()

        fila_logger.exception(
            "fila_insert_erro | acao=rollback id_msg=%s",
            short_value(dados.get("id_hash_msg") if dados else None),
        )
        return {
            "status": "error",
            "reason": "insert_exception",
        }

    finally:
        if conn_webhook:
            conn_webhook.close()


def _validar_content_type(request):
    content_type = (request.content_type or "").lower()

    if content_type.startswith("application/json"):
        return None

    logger.warning(
        "mensagem_ignorada | motivo=content_type_invalido acao=retornar_415 content_type=%s",
        content_type or None,
    )
    return JsonResponse({"status": "unsupported_media_type"}, status=415)


def _validar_tamanho_body(request):
    limite_bytes = settings.WEBHOOK_MAX_BODY_BYTES
    tamanho_header = request.headers.get("Content-Length")

    if tamanho_header:
        try:
            tamanho_bytes = int(tamanho_header)

        except ValueError:
            logger.warning(
                "mensagem_ignorada | motivo=content_length_invalido acao=retornar_400 content_length=%s",
                tamanho_header,
            )
            return JsonResponse({"status": "bad_request"}, status=400)

        if tamanho_bytes > limite_bytes:
            logger.warning(
                "mensagem_ignorada | motivo=body_muito_grande acao=retornar_413 tamanho_bytes=%s limite_bytes=%s origem=content_length",
                tamanho_bytes,
                limite_bytes,
            )
            return JsonResponse({"status": "payload_too_large"}, status=413)

    tamanho_real = len(request.body)

    if tamanho_real > limite_bytes:
        logger.warning(
            "mensagem_ignorada | motivo=body_muito_grande acao=retornar_413 tamanho_bytes=%s limite_bytes=%s origem=request_body",
            tamanho_real,
            limite_bytes,
        )
        return JsonResponse({"status": "payload_too_large"}, status=413)

    return None


def _extrair_value(data):
    return (
        data.get("entry", [{}])[0]
        .get("changes", [{}])[0]
        .get("value", {})
    )


def _extrair_phone_number_id(data):
    metadata = _extrair_value(data).get("metadata", {})
    return metadata.get("phone_number_id")


def _extrair_cliente_telefone(data):
    contacts = _extrair_value(data).get("contacts", [{}])
    return contacts[0].get("wa_id") if contacts else None



def _extrair_id_hash_msg_seguro(data):
    try:
        value = _extrair_value(data)
        messages = value.get("messages")

        if (
            not isinstance(messages, list)
            or not messages
            or not isinstance(messages[0], dict)
        ):
            return None

        id_hash_msg = messages[0].get("id")

        if id_hash_msg is None:
            return None

        id_hash_msg = str(id_hash_msg).strip()
        return id_hash_msg or None

    except Exception:
        return None


def _extrair_nome_cliente(data):
    contacts = _extrair_value(data).get("contacts") or []

    if not contacts or not isinstance(contacts[0], dict):
        return None

    profile = contacts[0].get("profile") or {}
    nome_cliente = profile.get("name")

    if nome_cliente is None:
        return None

    nome_cliente = str(nome_cliente).strip()
    return nome_cliente[:200] or None
```

A seção 0B permanece intacta.

### Recuperação atômica de falso positivo

```sql
BEGIN;
WITH alvo AS (
    SELECT c.id_conversa, cl.waid_telefone, c.id_unidade
    FROM chatbot.conversa c
    JOIN chatbot.cliente cl ON cl.id_cliente = c.id_cliente
    WHERE c.id_conversa = :id_conversa AND c.status_ativa = TRUE
    FOR UPDATE OF c
), reset AS (
    UPDATE chatbot.conversa c SET turnos_sem_avanco = 0
    FROM alvo a WHERE c.id_conversa = a.id_conversa
    RETURNING c.id_conversa
)
DELETE FROM chatbot.cliente_bloqueado_meta b
USING alvo a, reset r
WHERE b.wa_id_cliente = a.waid_telefone AND b.id_unidade = a.id_unidade
RETURNING r.id_conversa, b.id_bloqueio;
COMMIT;
```

Desbloquear na Meta é separado: confirmar a API primeiro, depois executar o
SQL. Se o SQL falhar, repetir a recuperação local antes de aceitar mensagens.

---

## Passo 7 — adicionar os testes dos turnos sem avanço

### Arquivo final completo: `tests/unit/test_persistencia_essencial.py`

```python

import unittest
from unittest.mock import patch

from core.repositories.fluxo.politicas import PoliticaEtapa
from workers.worker_flow.response_flow.transicoes.eventos import (
    EVENTO_NOME_CLIENTE_VALIDO,
    EVENTO_PARA_MIM,
    EVENTO_PARA_OUTRA_PESSOA,
)
from workers.worker_flow.transacoes import efeitos_transicao as efeitos
from workers.worker_flow.transacoes import encerramento_atendimento as encerramento
from workers.worker_flow.transacoes import movimento_conversa as movimento
from workers.worker_flow.transacoes import persistencia_resposta as persistencia


DATA_BOT = "2026-01-01T00:00:00"


def contexto_historico_base(
    resposta_bot=None,
    *,
    id_etapa_atual=None,
    texto_cliente="Ola",
):
    return {
        "resposta_bot_para_mensagem_atual": resposta_bot,
        "id_conversa": 10,
        "id_etapa_atual": id_etapa_atual,
        "id_etapa_origem_transicao": (
            id_etapa_atual if id_etapa_atual is not None else 1
        ),
        "texto_cliente_atual": texto_cliente,
        "mensagem_cliente_atual": {
            "id_mensagem_fila": 20,
            "id_hash_msg": "wamid.cliente",
            "cliente_telefone": "5571999999999",
            "id_phone_unidade": "123456",
            "unidade_telefone": "5571000000000",
        },
    }


class PersistenciaEssencialTests(unittest.TestCase):
    def test_resposta_normal_persiste_bot_e_avanca_conversa(self):
        cursor = object()

        with patch.object(
            persistencia,
            "inserir_historico_mensagem_bot",
            return_value=(300, DATA_BOT, True),
        ) as inserir_bot, patch.object(
            movimento,
            "inicializar_conversa_resposta_bot",
            return_value=1,
        ) as avancar, patch.object(
            movimento,
            "atualizar_conversa_resposta_bot_sem_avancar",
        ) as manter:
            resultado = persistencia.atualizar_banco_com_contexto_final(
                contexto_historico_base(),
                {
                    "enviou": True,
                    "resposta_ja_existia": False,
                    "mensagem_bot": "Ola!",
                    "id_hash_msg_bot": "wamid.bot",
                    "id_etapa_resultante": 1,
                    "tipo_mensagem": "interactive_button",
                },
                cursor,
            )

        inserir_bot.assert_called_once()
        avancar.assert_called_once_with(10, 1, DATA_BOT, cursor)
        manter.assert_not_called()
        self.assertTrue(resultado["historico_bot_inserido"])
        self.assertTrue(resultado["atualizar_conversa"])

    def test_tratamento_persiste_resposta_sem_avancar_etapa(self):
        cursor = object()

        with patch.object(
            persistencia,
            "inserir_historico_mensagem_bot",
            return_value=(301, DATA_BOT, True),
        ), patch.object(
            movimento,
            "inicializar_conversa_resposta_bot",
        ) as avancar, patch.object(
            movimento,
            "atualizar_conversa_resposta_bot_sem_avancar",
            return_value=1,
        ) as manter, patch.object(
            persistencia, "incrementar_turnos_sem_avanco", return_value=1,
        ) as incrementar, patch.object(
            persistencia, "resetar_turnos_sem_avanco",
        ) as resetar:
            resultado = persistencia.atualizar_banco_com_contexto_final(
                contexto_historico_base(id_etapa_atual=1),
                {
                    "enviou": True,
                    "resposta_ja_existia": False,
                    "mensagem_bot": "Tratamento",
                    "id_hash_msg_bot": "wamid.bot.tratamento",
                    "id_etapa_resultante": 1,
                    "tipo_mensagem": "text",
                    "tratamento": True,
                    "atualizar_conversa": False,
                    "atualizar_last_from_bot": True,
                },
                cursor,
            )

        avancar.assert_not_called()
        manter.assert_called_once_with(10, DATA_BOT, cursor)
        incrementar.assert_called_once_with(10, cursor)
        resetar.assert_not_called()
        self.assertEqual(resultado["turnos_sem_avanco"], 1)
        self.assertFalse(resultado["atualizar_conversa"])
        self.assertTrue(resultado["atualizar_last_from_bot"])

    def test_transicao_valida_reseta_turnos_sem_avanco(self):
        cursor = object()
        with patch.object(persistencia, "inserir_historico_mensagem_bot", return_value=(302, DATA_BOT, True)), patch.object(
            persistencia, "persistir_movimento_conversa", return_value="transicao"
        ), patch.object(persistencia, "resetar_turnos_sem_avanco", return_value=0) as resetar, patch.object(
            persistencia, "incrementar_turnos_sem_avanco"
        ) as incrementar, patch.object(
            persistencia, "atualizar_banco_conforme_transicao_de_etapa", return_value=None
        ), patch.object(persistencia, "resolver_intencao_encerramento", return_value=None):
            resultado = persistencia.atualizar_banco_com_contexto_final(
                contexto_historico_base(id_etapa_atual=1),
                {"enviou": True, "resposta_ja_existia": False, "mensagem_bot": "Avancou", "id_hash_msg_bot": "wamid.bot.transicao", "id_etapa_resultante": 2, "evento_transicao": EVENTO_NOME_CLIENTE_VALIDO, "tipo_mensagem": "text"},
                cursor,
            )
        resetar.assert_called_once_with(10, cursor)
        incrementar.assert_not_called()
        self.assertEqual(resultado["turnos_sem_avanco"], 0)


    def test_resposta_existente_nao_e_enviada_nem_inserida_novamente(self):
        cursor = object()

        with patch.object(
            persistencia,
            "inserir_historico_mensagem_bot",
        ) as inserir_bot, patch.object(
            movimento,
            "atualizar_conversa_resposta_bot_sem_avancar",
            return_value=1,
        ) as manter:
            resultado = persistencia.atualizar_banco_com_contexto_final(
                contexto_historico_base(
                    {"received_data_hora": DATA_BOT},
                    id_etapa_atual=1,
                ),
                {
                    "enviou": False,
                    "resposta_ja_existia": True,
                    "id_hash_msg_bot": "wamid.bot.existente",
                    "id_etapa_resultante": 1,
                },
                cursor,
            )

        inserir_bot.assert_not_called()
        manter.assert_called_once_with(10, DATA_BOT, cursor)
        self.assertTrue(resultado["resposta_ja_existia"])
        self.assertFalse(resultado["historico_bot_inserido"])

    def test_transicao_um_para_dois_salva_o_nome_do_cliente(self):
        cursor = object()

        with patch.object(
            efeitos,
            "atualizar_nome_cliente_por_telefone",
            return_value=1,
        ) as atualizar_nome:
            resultado = efeitos.atualizar_banco_conforme_transicao_de_etapa(
                contexto_historico_base(
                    id_etapa_atual=1,
                    texto_cliente="Maria",
                ),
                {
                    "id_etapa_resultante": 2,
                    "evento_transicao": EVENTO_NOME_CLIENTE_VALIDO,
                    "primeiro_nome_cliente": "Maria",
                },
                cursor,
            )

        atualizar_nome.assert_called_once_with(
            "5571999999999",
            "Maria",
            cursor,
        )
        self.assertEqual(resultado["primeiro_nome_cliente"], "Maria")

    def test_etapa_dois_persiste_corretamente_os_dois_ramos(self):
        casos = (
            (EVENTO_PARA_MIM, 4, False, False),
            (EVENTO_PARA_OUTRA_PESSOA, 3, True, True),
        )

        for evento, destino, status_dependente, cria_dependente in casos:
            with self.subTest(evento=evento):
                dependente = {
                    "id_dependente": 30,
                    "id_cliente": 5,
                    "id_conversa": 10,
                    "inserido": True,
                }

                with patch.object(
                    efeitos,
                    "atualizar_status_dependente_conversa",
                    return_value=1,
                ) as atualizar_status, patch.object(
                    efeitos,
                    "inserir_dependente_para_conversa",
                    return_value=dependente,
                ) as inserir_dependente:
                    resultado = (
                        efeitos.atualizar_banco_conforme_transicao_de_etapa(
                            contexto_historico_base(id_etapa_atual=2),
                            {
                                "id_etapa_resultante": destino,
                                "evento_transicao": evento,
                            },
                            object(),
                        )
                    )

                atualizar_status.assert_called_once()
                self.assertEqual(
                    resultado["status_dependente"],
                    status_dependente,
                )
                self.assertEqual(
                    resultado["dependente_criado"],
                    cria_dependente,
                )

                if cria_dependente:
                    inserir_dependente.assert_called_once()
                else:
                    inserir_dependente.assert_not_called()

    def test_somente_etapa_19_encerra_e_aplica_bloqueio_de_30_dias(self):
        contexto = contexto_historico_base(id_etapa_atual=18)

        for id_etapa in (17, 18):
            with self.subTest(id_etapa=id_etapa), patch.object(
                encerramento,
                "buscar_politica_etapa",
                return_value=PoliticaEtapa(
                    id_etapa=id_etapa,
                    encerra_automaticamente=False,
                    bloqueio_dias=0,
                    elegivel_funil=True,
                ),
            ):
                resultado = encerramento.resolver_intencao_encerramento(
                    contexto,
                    {
                        "evento_transicao": "evento_teste",
                        "id_etapa_resultante": id_etapa,
                    },
                    object(),
                )

            self.assertIsNone(resultado)

        with patch.object(
            encerramento,
            "buscar_politica_etapa",
            return_value=PoliticaEtapa(
                id_etapa=19,
                encerra_automaticamente=True,
                bloqueio_dias=30,
                elegivel_funil=True,
            ),
        ):
            resultado = encerramento.resolver_intencao_encerramento(
                contexto,
                {
                    "evento_transicao": "comentario_satisfacao_recebido",
                    "id_etapa_resultante": 19,
                },
                object(),
            )

        self.assertEqual(resultado["motivo"], "etapa_final")
        self.assertEqual(resultado["motivo_encerramento"], "foi_agendado")
        self.assertEqual(resultado["bloqueio_dias"], 30)


if __name__ == "__main__":
    unittest.main()
```

### Arquivo final completo: `tests/unit/test_protecao_bot_turnos_sem_avanco.py`

```python
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, call, patch

from django.contrib import admin

from callback.webhook import admin as webhook_admin
from callback.webhook.models import ClienteBloqueadoMeta
from callback.webhook.services import bloqueio_meta_guard, post_flow
from core.repositories.seguranca import suspeita_bot
from tests.helpers import FakeConn
from workers.worker_flow.transacoes import persistencia_resposta
from workers.worker_flow.transacoes.movimento_conversa import (
    MOVIMENTO_SEM_AVANCO,
    MOVIMENTO_TRANSICAO,
)


WA_ID = "5571999999999"
PHONE_ID = "123456"


class RepositorioTurnosSemAvancoTests(unittest.TestCase):
    def test_incremento_e_limitado_a_doze(self):
        cursor = MagicMock()
        cursor.fetchone.return_value = (12,)

        contador = suspeita_bot.incrementar_turnos_sem_avanco(
            10,
            cursor,
        )

        self.assertEqual(contador, 12)
        sql, parametros = cursor.execute.call_args.args
        self.assertIn("LEAST", sql)
        self.assertEqual(
            parametros,
            (suspeita_bot.LIMITE_TURNOS_SEM_AVANCO, 10),
        )

    def test_reset_define_zero(self):
        cursor = MagicMock()
        cursor.fetchone.return_value = (0,)

        contador = suspeita_bot.resetar_turnos_sem_avanco(
            10,
            cursor,
        )

        self.assertEqual(contador, 0)
        self.assertEqual(cursor.execute.call_args.args[1], (10,))

    def test_consulta_isola_wa_id_phone_id_e_conversa_ativa(self):
        cursor = MagicMock()
        cursor.fetchone.return_value = (
            10,
            20,
            "Cliente",
            30,
            PHONE_ID,
            12,
        )

        resultado = suspeita_bot.buscar_conversa_no_limite_sem_avanco(
            WA_ID,
            PHONE_ID,
            cursor,
        )

        sql, parametros = cursor.execute.call_args.args
        self.assertIn("cliente.waid_telefone = %s", sql)
        self.assertIn("unidade.phone_number_id = %s", sql)
        self.assertIn("conversa.status_ativa = TRUE", sql)
        self.assertNotIn("FOR UPDATE", sql)
        self.assertEqual(
            parametros,
            (WA_ID, PHONE_ID, suspeita_bot.LIMITE_TURNOS_SEM_AVANCO),
        )
        self.assertEqual(resultado["id_conversa"], 10)
        self.assertEqual(resultado["turnos_sem_avanco"], 12)


class WorkerTurnosSemAvancoTests(unittest.TestCase):
    def test_tratamento_novo_incrementa(self):
        cursor = object()

        with patch.object(
            persistencia_resposta,
            "incrementar_turnos_sem_avanco",
            return_value=6,
        ) as incrementar, patch.object(
            persistencia_resposta,
            "resetar_turnos_sem_avanco",
        ) as resetar:
            resultado = (
                persistencia_resposta._persistir_turnos_sem_avanco(
                    id_conversa=10,
                    movimento=MOVIMENTO_SEM_AVANCO,
                    tratamento=True,
                    historico_bot_inserido=True,
                    cursor=cursor,
                )
            )

        self.assertEqual(resultado, 6)
        incrementar.assert_called_once_with(10, cursor)
        resetar.assert_not_called()

    def test_retry_de_tratamento_nao_incrementa(self):
        with patch.object(
            persistencia_resposta,
            "incrementar_turnos_sem_avanco",
        ) as incrementar:
            resultado = (
                persistencia_resposta._persistir_turnos_sem_avanco(
                    id_conversa=10,
                    movimento=MOVIMENTO_SEM_AVANCO,
                    tratamento=True,
                    historico_bot_inserido=False,
                    cursor=object(),
                )
            )

        self.assertIsNone(resultado)
        incrementar.assert_not_called()

    def test_resposta_sem_tratamento_e_sem_transicao_nao_incrementa(self):
        with patch.object(
            persistencia_resposta,
            "incrementar_turnos_sem_avanco",
        ) as incrementar:
            resultado = (
                persistencia_resposta._persistir_turnos_sem_avanco(
                    id_conversa=10,
                    movimento=MOVIMENTO_SEM_AVANCO,
                    tratamento=False,
                    historico_bot_inserido=True,
                    cursor=object(),
                )
            )

        self.assertIsNone(resultado)
        incrementar.assert_not_called()

    def test_transicao_valida_reseta_mesmo_em_reaplicacao(self):
        cursor = object()

        with patch.object(
            persistencia_resposta,
            "resetar_turnos_sem_avanco",
            return_value=0,
        ) as resetar, patch.object(
            persistencia_resposta,
            "incrementar_turnos_sem_avanco",
        ) as incrementar:
            resultado = (
                persistencia_resposta._persistir_turnos_sem_avanco(
                    id_conversa=10,
                    movimento=MOVIMENTO_TRANSICAO,
                    tratamento=False,
                    historico_bot_inserido=False,
                    cursor=cursor,
                )
            )

        self.assertEqual(resultado, 0)
        resetar.assert_called_once_with(10, cursor)
        incrementar.assert_not_called()


class WebhookSuspeitaBotTests(unittest.TestCase):
    def test_limite_promove_para_denylist_antes_da_meta(self):
        conn = FakeConn()
        suspeita = {
            "id_conversa": 10,
            "id_cliente": 20,
            "nome_cliente": "Cliente",
            "id_unidade": 30,
            "phone_id_unidade": PHONE_ID,
            "turnos_sem_avanco": 12,
        }

        with patch.object(
            bloqueio_meta_guard,
            "get_conn",
            return_value=conn,
        ), patch.object(
            bloqueio_meta_guard,
            "cliente_bloqueado_meta_existe_banco",
            return_value=False,
        ), patch.object(
            bloqueio_meta_guard,
            "buscar_conversa_no_limite_sem_avanco",
            return_value=suspeita,
        ), patch.object(
            bloqueio_meta_guard,
            "registrar_cliente_bloqueado_meta_banco",
            return_value=99,
        ) as registrar:
            resultado = (
                bloqueio_meta_guard
                ._consultar_cliente_marcado_para_bloqueio(
                    WA_ID,
                    PHONE_ID,
                )
            )

        self.assertEqual(
            resultado,
            {
                "banco_ok": True,
                "marcado": True,
            },
        )
        registrar.assert_called_once_with(
            20,
            WA_ID,
            30,
            PHONE_ID,
            conn.cursor(),
            nome_cliente="Cliente",
        )
        self.assertEqual(conn.commits, 1)
        self.assertEqual(conn.rollbacks, 0)
        self.assertTrue(conn.closed)

    def test_abaixo_do_limite_nao_cria_denylist(self):
        conn = FakeConn()

        with patch.object(
            bloqueio_meta_guard,
            "get_conn",
            return_value=conn,
        ), patch.object(
            bloqueio_meta_guard,
            "cliente_bloqueado_meta_existe_banco",
            return_value=False,
        ), patch.object(
            bloqueio_meta_guard,
            "buscar_conversa_no_limite_sem_avanco",
            return_value=None,
        ), patch.object(
            bloqueio_meta_guard,
            "registrar_cliente_bloqueado_meta_banco",
        ) as registrar:
            resultado = (
                bloqueio_meta_guard
                ._consultar_cliente_marcado_para_bloqueio(
                    WA_ID,
                    PHONE_ID,
                )
            )

        self.assertEqual(
            resultado,
            {
                "banco_ok": True,
                "marcado": False,
            },
        )
        registrar.assert_not_called()

    def test_falha_ao_persistir_promocao_retorna_estado_indisponivel(self):
        conn = FakeConn()
        suspeita = {
            "id_conversa": 10,
            "id_cliente": 20,
            "nome_cliente": "Cliente",
            "id_unidade": 30,
            "phone_id_unidade": PHONE_ID,
            "turnos_sem_avanco": 12,
        }

        with patch.object(
            bloqueio_meta_guard,
            "get_conn",
            return_value=conn,
        ), patch.object(
            bloqueio_meta_guard,
            "cliente_bloqueado_meta_existe_banco",
            return_value=False,
        ), patch.object(
            bloqueio_meta_guard,
            "buscar_conversa_no_limite_sem_avanco",
            return_value=suspeita,
        ), patch.object(
            bloqueio_meta_guard,
            "registrar_cliente_bloqueado_meta_banco",
            side_effect=RuntimeError("banco caiu"),
        ), patch.object(
            bloqueio_meta_guard.logger,
            "exception",
        ):
            resultado = (
                bloqueio_meta_guard
                ._consultar_cliente_marcado_para_bloqueio(
                    WA_ID,
                    PHONE_ID,
                )
            )

        self.assertEqual(
            resultado,
            {
                "banco_ok": False,
                "marcado": False,
            },
        )
        self.assertEqual(conn.commits, 0)
        self.assertEqual(conn.rollbacks, 1)
        self.assertTrue(conn.closed)


class CoberturaAdicionalTests(unittest.TestCase):
    def test_isolamento_e_conversa_encerrada(self):
        cursor = MagicMock()
        cursor.fetchone.return_value = None
        limite = suspeita_bot.LIMITE_TURNOS_SEM_AVANCO
        for wa, phone in (("a", "1"), ("a", "2"), ("b", "1")):
            suspeita_bot.buscar_conversa_no_limite_sem_avanco(wa, phone, cursor)
        self.assertEqual([c.args[1] for c in cursor.execute.call_args_list], [("a", "1", limite), ("a", "2", limite), ("b", "1", limite)])
        self.assertIn("conversa.status_ativa = TRUE", cursor.execute.call_args.args[0])

    def test_nome_profile_e_fallback_persistido(self):
        payload = {"entry": [{"changes": [{"value": {"contacts": [{"profile": {"name": " Nome Meta "}}]}}]}]}
        self.assertEqual(post_flow._extrair_nome_cliente(payload), "Nome Meta")
        conn = FakeConn()
        suspeita = {"id_conversa": 10, "id_cliente": 20, "nome_cliente": None, "id_unidade": 30, "phone_id_unidade": PHONE_ID, "turnos_sem_avanco": 12}
        with patch.object(bloqueio_meta_guard, "get_conn", return_value=conn), patch.object(bloqueio_meta_guard, "cliente_bloqueado_meta_existe_banco", return_value=False), patch.object(bloqueio_meta_guard, "buscar_conversa_no_limite_sem_avanco", return_value=suspeita), patch.object(bloqueio_meta_guard, "registrar_cliente_bloqueado_meta_banco", return_value=99) as registrar:
            bloqueio_meta_guard._consultar_cliente_marcado_para_bloqueio(WA_ID, PHONE_ID, nome_cliente="Nome Meta")
        self.assertEqual(registrar.call_args.kwargs["nome_cliente"], "Nome Meta")

    def test_falha_meta_e_retry_sequencial(self):
        with patch.object(bloqueio_meta_guard, "_consultar_cliente_marcado_para_bloqueio", return_value={"banco_ok": True, "marcado": True}), patch.object(bloqueio_meta_guard, "bloquear_usuario_meta", side_effect=[RuntimeError("falha"), None]) as bloquear:
            respostas = [bloqueio_meta_guard.responder_se_cliente_marcado_para_bloqueio(WA_ID, PHONE_ID) for _ in range(2)]
        self.assertTrue(all(r.status_code == 200 for r in respostas))
        self.assertEqual(bloquear.call_args_list, [call(WA_ID, PHONE_ID), call(WA_ID, PHONE_ID)])

    def test_admin_reseta_antes_de_excluir_denylist(self):
        ma = webhook_admin.ClienteBloqueadoMetaAdmin(ClienteBloqueadoMeta, admin.site)
        request = SimpleNamespace(user="operador")
        obj = SimpleNamespace(id_cliente_id=20, id_unidade_id=30, wa_id_cliente=WA_ID, phone_id_unidade=PHONE_ID)
        qs = MagicMock()
        with patch.object(webhook_admin.Conversa.objects, "filter", return_value=qs) as filtrar, patch.object(admin.ModelAdmin, "delete_model") as excluir:
            ma.delete_model(request, obj)
        filtrar.assert_called_once_with(id_cliente_id=20, id_unidade_id=30, status_ativa=True)
        qs.update.assert_called_once_with(turnos_sem_avanco=0)
        excluir.assert_called_once_with(request, obj)


if __name__ == "__main__":
    unittest.main()
```

Cobertura: incremento/reset, isolamento, conversa encerrada, nome, falha Meta,
retry sequencial e recuperação pelo Admin.

---

## Passo especial — relatório manual de conversas suspeitas

Este passo é uma ferramenta de diagnóstico manual e independente da proteção
automática descrita acima. Ele não bloqueia clientes, não chama a Meta, não usa
Redis ou Django, não altera a conversa e não deve ser importado pelo webhook ou
pelos workers.

O relatório usa somente `SELECT` em uma transação PostgreSQL
`REPEATABLE READ READ ONLY`, com `statement_timeout`, `lock_timeout` e
`idle_in_transaction_session_timeout` locais. Ele consulta os nomes reais do
DDL atual:

- `chatbot.conversa`: `id_conversa`, `id_cliente`, `id_unidade`,
  `id_etapa_atual`,
  `status_ativa`, `iniciou_em`, `finalizou_em`, `motivo_encerramento` e,
  quando existir, `turnos_sem_avanco`;
- `chatbot.cliente`: `nome` e `waid_telefone`, mascarados por padrão;
- `chatbot.unidade`: `id_unidade`, `nome`, `waba_id` e
  `phone_number_id`, para a revisão multi-WABA;
- `chatbot.historico_mensagens`: `id_mensagem`, `id_mensagem_fila`,
  `id_conversa`, `id_etapa`, `received_data_hora`, `tipo_mensagem`,
  `quem_enviou` e derivadas não reversíveis do conteúdo.
  `cliente_telefone`, `id_phone_unidade`, `unidade_telefone` e hashes de
  transporte não são consultados.

Por padrão, `conteudo_texto` nem sequer é retornado pelo PostgreSQL. A opção
explícita `--incluir-textos` inclui somente amostras já mascaradas no processo;
o texto original nunca aparece na saída. O mascaramento é de melhor esforço
para e-mail, telefone, CPF/CNPJ, URLs, chaves longas e números extensos, por
isso a opção deve ser usada somente em ambiente controlado.
O nome do cliente e o WA ID também são mascarados por padrão. A opção
`--mostrar-wa-id` revela somente o WA ID completo, de forma explícita; o nome
permanece mascarado.

O score, de 0 a 100, é apenas uma priorização explicável e não uma decisão de
bloqueio. Ele soma cinco dimensões e limita o resultado final a 100: fluxo sem
avanço (70), repetição/ciclos (15), cadência (20), conteúdo automatizado (15)
e conclusão anormalmente rápida (10). O sinal principal é deliberadamente
forte: 12 turnos sem avanço valem 70 pontos e sempre passam pelo limiar padrão
45. A ausência da coluna futura `turnos_sem_avanco` não desativa o
relatório: nesse caso, a dimensão usa somente o histórico de etapas.

Para impedir varreduras acidentais, a CLI exige ao menos um
`--id-conversa`, `--id-unidade` ou `--todas-unidades`; limita conversas,
mensagens por conversa e mensagens totais; e usa uma janela temporal
obrigatória, derivada de `--ultimas-horas` ou de `--inicio`/`--fim`.

### Arquivo completo: `relatorio_conversas_suspeitas.py`

Criar na raiz do projeto:

```python
"""Relatório manual e somente leitura de conversas potencialmente automatizadas."""

from __future__ import annotations

import argparse
import csv
import io
import json
import re
import statistics
import sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone

from core.database.connection_aws import get_conn


MAX_CONVERSAS = 2000
MAX_MENSAGENS_POR_CONVERSA = 1000
MAX_MENSAGENS_TOTAL = 50000
DEFAULT_LIMITE_CONVERSAS = 200
DEFAULT_LIMITE_MENSAGENS = 250
DEFAULT_LIMIAR = 45
DEFAULT_STATEMENT_TIMEOUT_MS = 15000
DEFAULT_LOCK_TIMEOUT_MS = 1000
DEFAULT_IDLE_TIMEOUT_MS = 20000

_EMAIL = re.compile(r"\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b")
_URL = re.compile(r"\b(?:https?://|www\.)\S+", re.IGNORECASE)
_CPF_CNPJ = re.compile(r"\b\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b|\b\d{2}\.?\d{3}\.?\d{3}/?\d{4}-?\d{2}\b")
_TELEFONE = re.compile(r"(?<!\d)(?:\+?55\s*)?(?:\(?\d{2}\)?[\s.-]*)?\d{4,5}[\s.-]?\d{4}(?!\d)")
_NUMERO_LONGO = re.compile(r"\b\d{7,}\b")
_SEGREDO = re.compile(r"\b[A-Za-z0-9_-]{24,}\b")


def parse_instante(valor):
    texto = str(valor).strip()
    if texto.endswith("Z"):
        texto = texto[:-1] + "+00:00"
    instante = datetime.fromisoformat(texto)
    if instante.tzinfo is None:
        instante = instante.replace(tzinfo=timezone.utc)
    return instante.astimezone(timezone.utc)


def mascarar_pii(texto):
    if texto is None:
        return None
    valor = str(texto)
    valor = _EMAIL.sub("[EMAIL]", valor)
    valor = _URL.sub("[URL]", valor)
    valor = _CPF_CNPJ.sub("[DOCUMENTO]", valor)
    valor = _TELEFONE.sub("[TELEFONE]", valor)
    valor = _NUMERO_LONGO.sub("[NUMERO]", valor)
    return _SEGREDO.sub("[CHAVE]", valor)


def _iso(valor):
    if valor is None:
        return None
    if isinstance(valor, datetime):
        return valor.isoformat()
    return str(valor)


def _clamp(valor, minimo, maximo):
    return max(minimo, min(maximo, valor))


def _razao(parte, total):
    return parte / total if total else 0.0


def mascarar_wa_id(valor, *, mostrar=False):
    if valor is None:
        return None
    texto = str(valor).strip()
    if mostrar:
        return texto
    if len(texto) <= 4:
        return "*" * len(texto)
    return "*" * (len(texto) - 4) + texto[-4:]


def mascarar_nome(valor):
    if not valor:
        return None
    partes = str(valor).strip().split()
    return " ".join(
        parte[0] + "***" if parte else ""
        for parte in partes[:3]
    )


def reconstruir_movimentos(mensagens):
    """Pareia cliente/bot pela fila e classifica a evolução observada."""
    por_fila = defaultdict(list)
    for item in mensagens:
        if item.get("id_mensagem_fila") is not None:
            por_fila[item["id_mensagem_fila"]].append(item)
    movimentos = []
    for cliente in (
        item for item in mensagens if item["quem_enviou"] == "cliente"
    ):
        candidatos = [
            item
            for item in por_fila.get(cliente.get("id_mensagem_fila"), [])
            if item["quem_enviou"] == "bot"
            and item["instante"] >= cliente["instante"]
        ]
        bot = min(
            candidatos,
            key=lambda item: (item["instante"], item["id_mensagem"]),
            default=None,
        )
        if bot is None:
            tipo = "indeterminado"
        elif cliente["id_etapa"] is None and bot["id_etapa"] is not None:
            tipo = "inicializacao"
        elif cliente["id_etapa"] is None or bot["id_etapa"] is None:
            tipo = "indeterminado"
        elif cliente["id_etapa"] != bot["id_etapa"]:
            tipo = "avanco"
        else:
            tipo = "sem_avanco"
        movimentos.append(
            {
                "id_mensagem_cliente": cliente["id_mensagem"],
                "id_mensagem_bot": bot["id_mensagem"] if bot else None,
                "tipo": tipo,
                "etapa_cliente": cliente["id_etapa"],
                "etapa_bot": bot["id_etapa"] if bot else None,
            }
        )
    return movimentos


def _maior_sequencia_sem_avanco(movimentos):
    maior = atual = 0
    for movimento in movimentos:
        if movimento["tipo"] == "sem_avanco":
            atual += 1
            maior = max(maior, atual)
        else:
            atual = 0
    return maior


def _latencias_bot_cliente(mensagens):
    """Mede somente a resposta externa após a última mensagem do nosso bot."""
    ultima_bot = None
    latencias = []
    for item in mensagens:
        if item["quem_enviou"] == "bot":
            ultima_bot = item
        elif ultima_bot is not None:
            segundos = (item["instante"] - ultima_bot["instante"]).total_seconds()
            if segundos >= 0:
                latencias.append(
                    {
                        "segundos": segundos,
                        "estruturada_curta": (
                            item["tipo_mensagem"]
                            in {
                                "button",
                                "interactive",
                                "list",
                                "quick_reply",
                            }
                            and (item.get("tamanho_texto") or 0) <= 40
                        ),
                    }
                )
            ultima_bot = None
    return latencias


def _contar_ciclos(estados):
    ciclos = 0
    for tamanho in (2, 3):
        for indice in range(tamanho * 2, len(estados) + 1):
            if estados[indice - tamanho:indice] == estados[indice - tamanho * 2:indice - tamanho]:
                ciclos += 1
    return ciclos


def pontuar_conversa(conversa, mensagens):
    mensagens = sorted(
        mensagens,
        key=lambda item: (item["instante"], item["id_mensagem"]),
    )
    total = len(mensagens)
    clientes = [item for item in mensagens if item["quem_enviou"] == "cliente"]
    bots_contexto = [
        item for item in mensagens if item["quem_enviou"] == "bot"
    ]
    movimentos = reconstruir_movimentos(mensagens)
    chaves_cliente = [
        (item["id_etapa"], item["fingerprint"])
        for item in clientes
        if item.get("fingerprint")
    ]
    contagens_cliente = Counter(chaves_cliente)
    repeticoes_cliente = sum(
        max(0, quantidade - 1)
        for quantidade in contagens_cliente.values()
    )
    razao_repeticao = _razao(
        repeticoes_cliente,
        len(chaves_cliente),
    )
    estados = [
        (item["id_etapa"], item.get("fingerprint"))
        for item in clientes
        if item.get("fingerprint")
    ]
    ciclos = _contar_ciclos(estados)
    sequencia_sem_avanco = _maior_sequencia_sem_avanco(movimentos)
    contagem_movimentos = Counter(
        movimento["tipo"] for movimento in movimentos
    )

    razoes_fluxo = []
    turnos = conversa.get("turnos_sem_avanco")
    sinal_fluxo = max(turnos or 0, sequencia_sem_avanco)
    if sinal_fluxo >= 12:
        pontos_fluxo = 70
    elif sinal_fluxo >= 9:
        pontos_fluxo = 50
    elif sinal_fluxo >= 6:
        pontos_fluxo = 30
    elif sinal_fluxo >= 4:
        pontos_fluxo = 15
    else:
        pontos_fluxo = 0
    if turnos:
        razoes_fluxo.append(
            f"contador persistido em {turnos} turno(s) sem avanço"
        )
    if sequencia_sem_avanco:
        razoes_fluxo.append(
            f"{sequencia_sem_avanco} movimento(s) pareado(s) consecutivo(s) sem avanço"
        )
    if pontos_fluxo:
        razoes_fluxo.append(
            f"faixa principal de fluxo sem avanço (+{pontos_fluxo})"
        )

    pontos_repeticao = min(
        15,
        round(10 * razao_repeticao) + min(5, ciclos),
    )
    razoes_repeticao = []
    if repeticoes_cliente:
        razoes_repeticao.append(
            f"{repeticoes_cliente} resposta(s) do cliente repetida(s) na mesma etapa (+{round(10 * razao_repeticao)})"
        )
    if ciclos:
        razoes_repeticao.append(
            f"{ciclos} ciclo(s) de 2 ou 3 estados (+{min(5, ciclos)})"
        )

    latencias = _latencias_bot_cliente(mensagens)
    latencias_nao_estruturadas = [
        item["segundos"]
        for item in latencias
        if not item["estruturada_curta"]
    ]
    rapidas_nao_estruturadas = sum(
        valor <= 2 for valor in latencias_nao_estruturadas
    )
    rapidas_estruturadas = sum(
        item["segundos"] <= 2 and item["estruturada_curta"]
        for item in latencias
    )
    razao_rapida = _razao(
        rapidas_nao_estruturadas,
        len(latencias_nao_estruturadas),
    )
    cv = None
    if len(latencias_nao_estruturadas) >= 3:
        media = statistics.fmean(latencias_nao_estruturadas)
        if media > 0:
            cv = statistics.pstdev(latencias_nao_estruturadas) / media
    pontos_cadencia = min(
        20,
        round(14 * razao_rapida)
        + min(3, rapidas_estruturadas)
        + (6 if cv is not None and cv <= 0.12 else 0),
    )
    razoes_cadencia = []
    if rapidas_nao_estruturadas:
        razoes_cadencia.append(
            f"{rapidas_nao_estruturadas}/{len(latencias_nao_estruturadas)} latência(s) bot→cliente não estruturadas de até 2 s (+{round(14 * razao_rapida)})"
        )
    if rapidas_estruturadas:
        razoes_cadencia.append(
            f"{rapidas_estruturadas} resposta(s) estruturada(s) rápida(s), com peso reduzido (+{min(3, rapidas_estruturadas)})"
        )
    if cv is not None and cv <= 0.12:
        razoes_cadencia.append("latência bot→cliente muito regular (+6)")

    tipos_cliente = Counter(
        item["tipo_mensagem"] for item in clientes
    )
    tamanhos_cliente = [
        item["tamanho_texto"]
        for item in clientes
        if item.get("tamanho_texto") is not None
    ]
    tamanhos_estaveis = False
    if (
        len(tamanhos_cliente) >= 4
        and statistics.fmean(tamanhos_cliente) > 0
    ):
        tamanhos_estaveis = (
            statistics.pstdev(tamanhos_cliente)
            / statistics.fmean(tamanhos_cliente)
            <= 0.10
        )
    marcadores_automacao = sum(
        bool(item.get("tem_marcador_automacao"))
        or bool(
            item.get("texto")
            and re.search(
                r"\b(?:assistente virtual|mensagem autom[aá]tica|"
                r"n[aã]o consigo entender|digite uma op[cç][aã]o|"
                r"escolha uma op[cç][aã]o)\b",
                item["texto"],
                re.IGNORECASE,
            )
        )
        for item in clientes
    )
    mensagens_com_url = sum(bool(item.get("tem_url")) for item in clientes)
    somente_estruturadas_curtas = bool(clientes) and all(
        item["tipo_mensagem"]
        in {"button", "interactive", "list", "quick_reply"}
        and (item.get("tamanho_texto") or 0) <= 40
        for item in clientes
    )
    pontos_conteudo = min(
        15,
        (0 if somente_estruturadas_curtas else round(6 * razao_repeticao))
        + min(6, marcadores_automacao * 3)
        + min(2, mensagens_com_url)
        + (2 if tamanhos_estaveis and not somente_estruturadas_curtas else 0)
        + (
            1
            if len(tipos_cliente) == 1
            and len(clientes) >= 5
            and not somente_estruturadas_curtas
            else 0
        ),
    )
    razoes_conteudo = []
    if razao_repeticao and not somente_estruturadas_curtas:
        razoes_conteudo.append(
            f"templates idênticos do cliente na mesma etapa em {razao_repeticao:.0%} das respostas (+{round(6 * razao_repeticao)})"
        )
    if marcadores_automacao:
        razoes_conteudo.append(
            f"{marcadores_automacao} texto(s) do cliente com expressão de automação (+{min(6, marcadores_automacao * 3)})"
        )
    if mensagens_com_url:
        razoes_conteudo.append(
            f"{mensagens_com_url} mensagem(ns) do cliente com URL (+{min(2, mensagens_com_url)})"
        )
    if tamanhos_estaveis and not somente_estruturadas_curtas:
        razoes_conteudo.append("tamanho das mensagens do cliente muito estável (+2)")
    if (
        len(tipos_cliente) == 1
        and len(clientes) >= 5
        and not somente_estruturadas_curtas
    ):
        razoes_conteudo.append("um único tipo de mensagem do cliente (+1)")

    pontos_conclusao = 0
    razoes_conclusao = []
    duracao_segundos = None
    if conversa.get("finalizou_em") and conversa.get("iniciou_em"):
        duracao_segundos = max(
            0,
            (conversa["finalizou_em"] - conversa["iniciou_em"]).total_seconds(),
        )
        if len(clientes) >= 4 and duracao_segundos <= 30:
            pontos_conclusao = 10
        elif len(clientes) >= 3 and duracao_segundos <= 60:
            pontos_conclusao = 7
        elif len(clientes) >= 2 and duracao_segundos <= 120:
            pontos_conclusao = 4
        if pontos_conclusao:
            razoes_conclusao.append(
                f"conversa encerrada em {duracao_segundos:.0f} s com {len(clientes)} mensagens do cliente (+{pontos_conclusao})"
            )

    dimensoes = {
        "fluxo_sem_avanco": {
            "pontos": pontos_fluxo,
            "maximo": 70,
            "razoes": razoes_fluxo,
        },
        "repeticao_ciclos": {
            "pontos": pontos_repeticao,
            "maximo": 15,
            "razoes": razoes_repeticao,
        },
        "cadencia": {
            "pontos": pontos_cadencia,
            "maximo": 20,
            "razoes": razoes_cadencia,
        },
        "conteudo_automatizado": {
            "pontos": pontos_conteudo,
            "maximo": 15,
            "razoes": razoes_conteudo,
        },
        "conclusao_rapida": {
            "pontos": pontos_conclusao,
            "maximo": 10,
            "razoes": razoes_conclusao,
        },
    }
    score = min(100, sum(item["pontos"] for item in dimensoes.values()))
    return {
        "score": score,
        "dimensoes": dimensoes,
        "metricas": {
            "total_mensagens_analisadas": total,
            "mensagens_cliente": len(clientes),
            "mensagens_bot_contexto": len(bots_contexto),
            "movimentos": dict(contagem_movimentos),
            "maior_sequencia_sem_avanco": sequencia_sem_avanco,
            "respostas_cliente_repetidas_na_mesma_etapa": repeticoes_cliente,
            "ciclos_cliente_detectados": ciclos,
            "latencias_bot_cliente": [
                round(item["segundos"], 3) for item in latencias
            ],
            "duracao_segundos": duracao_segundos,
        },
    }


def _configurar_transacao(cursor, args):
    cursor.execute(
        "BEGIN TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY"
    )
    cursor.execute(
        "SELECT set_config('statement_timeout', %s, true)",
        (f"{args.statement_timeout_ms}ms",),
    )
    cursor.execute(
        "SELECT set_config('lock_timeout', %s, true)",
        (f"{args.lock_timeout_ms}ms",),
    )
    cursor.execute(
        "SELECT set_config('idle_in_transaction_session_timeout', %s, true)",
        (f"{args.idle_timeout_ms}ms",),
    )


def _possui_turnos_sem_avanco(cursor):
    cursor.execute(
        """
        SELECT EXISTS (
            SELECT 1
            FROM information_schema.columns
            WHERE table_schema = 'chatbot'
              AND table_name = 'conversa'
              AND column_name = 'turnos_sem_avanco'
        )
        """
    )
    return bool(cursor.fetchone()[0])


def _buscar_conversas(cursor, args, inicio, fim, possui_turnos):
    filtros = [
        "c.iniciou_em <= %s",
        "COALESCE(c.finalizou_em, c.last_interaction_at, c.iniciou_em) >= %s",
    ]
    parametros = [fim, inicio]
    if args.id_conversa:
        filtros.append("c.id_conversa = ANY(%s)")
        parametros.append(args.id_conversa)
    if args.id_unidade:
        filtros.append("c.id_unidade = ANY(%s)")
        parametros.append(args.id_unidade)
    coluna_turnos = (
        "c.turnos_sem_avanco"
        if possui_turnos
        else "NULL::integer AS turnos_sem_avanco"
    )
    parametros.append(args.limite_conversas + 1)
    cursor.execute(
        f"""
        SELECT
            c.id_conversa,
            c.id_cliente,
            cl.nome AS nome_cliente,
            cl.waid_telefone,
            c.id_unidade,
            u.nome AS nome_unidade,
            u.waba_id,
            u.phone_number_id,
            c.id_etapa_atual,
            c.status_ativa,
            c.iniciou_em,
            c.finalizou_em,
            c.motivo_encerramento,
            {coluna_turnos}
        FROM chatbot.conversa AS c
        JOIN chatbot.cliente AS cl
          ON cl.id_cliente = c.id_cliente
        JOIN chatbot.unidade AS u
          ON u.id_unidade = c.id_unidade
        WHERE {" AND ".join(filtros)}
        ORDER BY c.iniciou_em DESC, c.id_conversa DESC
        LIMIT %s
        """,
        tuple(parametros),
    )
    linhas = cursor.fetchall()
    if len(linhas) > args.limite_conversas:
        raise RuntimeError(
            "limite de conversas atingido; reduza a janela ou refine os filtros"
        )
    chaves = (
        "id_conversa",
        "id_cliente",
        "nome_cliente",
        "waid_telefone",
        "id_unidade",
        "nome_unidade",
        "waba_id",
        "phone_number_id",
        "id_etapa_atual",
        "status_ativa",
        "iniciou_em",
        "finalizou_em",
        "motivo_encerramento",
        "turnos_sem_avanco",
    )
    return [dict(zip(chaves, linha)) for linha in linhas]


def _buscar_mensagens(cursor, ids_conversa, args, inicio, fim):
    if not ids_conversa:
        return defaultdict(list), {}
    texto_sql = (
        "h.conteudo_texto"
        if args.incluir_textos
        else "NULL::text AS conteudo_texto"
    )
    cursor.execute(
        f"""
        WITH ordenadas AS (
            SELECT
                h.id_mensagem,
                h.id_mensagem_fila,
                h.id_conversa,
                h.id_etapa,
                h.received_data_hora,
                h.tipo_mensagem,
                h.quem_enviou,
                CASE
                    WHEN NULLIF(BTRIM(h.conteudo_texto), '') IS NULL
                    THEN NULL
                    ELSE md5(
                        lower(
                            regexp_replace(
                                h.conteudo_texto,
                                '\\s+',
                                ' ',
                                'g'
                            )
                        )
                    )
                END AS fingerprint,
                char_length(h.conteudo_texto) AS tamanho_texto,
                COALESCE(
                    h.conteudo_texto ~* '(https?://|www\\.)',
                    FALSE
                ) AS tem_url,
                COALESCE(
                    h.conteudo_texto ~* (
                        'assistente virtual|mensagem autom[aá]tica|'
                        'n[aã]o consigo entender|digite uma op[cç][aã]o|'
                        'escolha uma op[cç][aã]o'
                    ),
                    FALSE
                ) AS tem_marcador_automacao,
                {texto_sql},
                row_number() OVER (
                    PARTITION BY h.id_conversa
                    ORDER BY h.received_data_hora DESC, h.id_mensagem DESC
                ) AS ordem,
                count(*) OVER (
                    PARTITION BY h.id_conversa
                ) AS total_conversa
            FROM chatbot.historico_mensagens AS h
            WHERE h.id_conversa = ANY(%s)
              AND h.received_data_hora >= %s
              AND h.received_data_hora <= %s
        )
        SELECT
            id_mensagem,
            id_mensagem_fila,
            id_conversa,
            id_etapa,
            received_data_hora,
            tipo_mensagem,
            quem_enviou,
            fingerprint,
            tamanho_texto,
            tem_url,
            tem_marcador_automacao,
            conteudo_texto,
            total_conversa
        FROM ordenadas
        WHERE ordem <= %s
        ORDER BY id_conversa, received_data_hora, id_mensagem
        LIMIT %s
        """,
        (
            ids_conversa,
            inicio,
            fim,
            args.limite_mensagens,
            args.max_mensagens_total + 1,
        ),
    )
    por_conversa = defaultdict(list)
    totais = {}
    for linha in cursor.fetchall():
        mensagem = {
            "id_mensagem": linha[0],
            "id_mensagem_fila": linha[1],
            "id_conversa": linha[2],
            "id_etapa": linha[3],
            "instante": linha[4],
            "tipo_mensagem": linha[5],
            "quem_enviou": linha[6],
            "fingerprint": linha[7],
            "tamanho_texto": linha[8],
            "tem_url": bool(linha[9]),
            "tem_marcador_automacao": bool(linha[10]),
            "texto": mascarar_pii(linha[11]) if linha[11] is not None else None,
        }
        por_conversa[linha[2]].append(mensagem)
        totais[linha[2]] = linha[12]
    carregadas = sum(len(itens) for itens in por_conversa.values())
    if carregadas > args.max_mensagens_total:
        raise RuntimeError(
            "limite total de mensagens atingido; reduza a janela ou os limites"
        )
    return por_conversa, totais


def gerar_relatorio(args, *, connection_factory=get_conn):
    inicio, fim = resolver_janela(args)
    conn = connection_factory(
        application_name="relatorio_conversas_suspeitas_readonly"
    )
    try:
        cursor = conn.cursor()
        _configurar_transacao(cursor, args)
        possui_turnos = _possui_turnos_sem_avanco(cursor)
        conversas = _buscar_conversas(
            cursor,
            args,
            inicio,
            fim,
            possui_turnos,
        )
        ids = [item["id_conversa"] for item in conversas]
        mensagens, totais = _buscar_mensagens(
            cursor,
            ids,
            args,
            inicio,
            fim,
        )
        resultados = []
        for conversa in conversas:
            analise = pontuar_conversa(
                conversa,
                mensagens.get(conversa["id_conversa"], []),
            )
            if analise["score"] < args.limiar:
                continue
            item = {
                "id_conversa": conversa["id_conversa"],
                "id_cliente": conversa["id_cliente"],
                "nome_cliente_mascarado": mascarar_nome(
                    conversa["nome_cliente"]
                ),
                "wa_id_cliente": mascarar_wa_id(
                    conversa["waid_telefone"],
                    mostrar=args.mostrar_wa_id,
                ),
                "id_unidade": conversa["id_unidade"],
                "nome_unidade": conversa["nome_unidade"],
                "waba_id": conversa["waba_id"],
                "phone_number_id": conversa["phone_number_id"],
                "score": analise["score"],
                "status_ativa": conversa["status_ativa"],
                "id_etapa_atual": conversa["id_etapa_atual"],
                "iniciou_em": _iso(conversa["iniciou_em"]),
                "finalizou_em": _iso(conversa["finalizou_em"]),
                "motivo_encerramento": conversa["motivo_encerramento"],
                "turnos_sem_avanco": conversa["turnos_sem_avanco"],
                "historico_truncado": (
                    totais.get(conversa["id_conversa"], 0)
                    > args.limite_mensagens
                ),
                "metricas_sobre_recorte": (
                    "mensagens mais recentes da conversa dentro da janela"
                ),
                **analise,
            }
            if args.incluir_textos:
                item["amostras_texto_mascarado"] = [
                    {
                        "quem_enviou": mensagem["quem_enviou"],
                        "instante": _iso(mensagem["instante"]),
                        "texto": mensagem["texto"][: args.max_caracteres_texto],
                    }
                    for mensagem in mensagens.get(conversa["id_conversa"], [])
                    if mensagem.get("texto")
                ][: args.max_amostras_texto]
            resultados.append(item)
        resultados.sort(
            key=lambda item: (-item["score"], item["id_conversa"])
        )
        return {
            "metadados": {
                "gerado_em": datetime.now(timezone.utc).isoformat(),
                "inicio": inicio.isoformat(),
                "fim": fim.isoformat(),
                "somente_leitura": True,
                "isolamento": "REPEATABLE READ",
                "coluna_turnos_sem_avanco_disponivel": possui_turnos,
                "conversas_lidas": len(conversas),
                "conversas_reportadas": len(resultados),
                "limiar": args.limiar,
                "textos_incluidos": bool(args.incluir_textos),
                "wa_id_completo": bool(args.mostrar_wa_id),
                "recorte_historico": (
                    "até o limite de mensagens mais recentes por conversa "
                    "dentro da janela; métricas não representam mensagens "
                    "anteriores ao recorte"
                ),
            },
            "conversas": resultados,
        }
    finally:
        try:
            conn.rollback()
        finally:
            conn.close()


def resolver_janela(args):
    fim = parse_instante(args.fim) if args.fim else datetime.now(timezone.utc)
    inicio = (
        parse_instante(args.inicio)
        if args.inicio
        else fim - timedelta(hours=args.ultimas_horas)
    )
    if inicio >= fim:
        raise ValueError("--inicio deve ser anterior a --fim")
    if fim - inicio > timedelta(days=31):
        raise ValueError("a janela máxima é de 31 dias")
    return inicio, fim


def _razoes_texto(item):
    razoes = []
    for nome, dimensao in item["dimensoes"].items():
        for razao in dimensao["razoes"]:
            razoes.append(f"{nome}: {razao}")
    return razoes


def formatar_texto(relatorio):
    meta = relatorio["metadados"]
    linhas = [
        "RELATÓRIO MANUAL DE CONVERSAS SUSPEITAS",
        (
            f"janela={meta['inicio']}..{meta['fim']} "
            f"lidas={meta['conversas_lidas']} "
            f"reportadas={meta['conversas_reportadas']} "
            f"limiar={meta['limiar']}"
        ),
    ]
    for item in relatorio["conversas"]:
        linhas.append(
            (
                f"\nconversa={item['id_conversa']} "
                f"cliente={item['id_cliente']} "
                f"wa_id={item['wa_id_cliente']} "
                f"unidade={item['id_unidade']} "
                f"waba_id={item['waba_id']} "
                f"phone_number_id={item['phone_number_id']} "
                f"score={item['score']}/100 "
                f"ativa={item['status_ativa']}"
            )
        )
        for razao in _razoes_texto(item):
            linhas.append(f"  - {razao}")
        if item.get("historico_truncado"):
            linhas.append("  - aviso: histórico truncado pelo limite de carga")
        for amostra in item.get("amostras_texto_mascarado", []):
            linhas.append(
                f"  - amostra {amostra['quem_enviou']} "
                f"{amostra['instante']}: {amostra['texto']}"
            )
    return "\n".join(linhas) + "\n"


def formatar_csv(relatorio):
    saida = io.StringIO()
    campos = [
        "id_conversa",
        "id_cliente",
        "nome_cliente_mascarado",
        "wa_id_cliente",
        "id_unidade",
        "nome_unidade",
        "waba_id",
        "phone_number_id",
        "score",
        "status_ativa",
        "id_etapa_atual",
        "iniciou_em",
        "finalizou_em",
        "turnos_sem_avanco",
        "historico_truncado",
        "razoes",
    ]
    writer = csv.DictWriter(saida, fieldnames=campos)
    writer.writeheader()
    for item in relatorio["conversas"]:
        linha = {campo: item.get(campo) for campo in campos}
        linha["razoes"] = " | ".join(_razoes_texto(item))
        writer.writerow(linha)
    return saida.getvalue()


def formatar_saida(relatorio, formato):
    if formato == "json":
        return json.dumps(
            relatorio,
            ensure_ascii=False,
            indent=2,
            default=_iso,
        ) + "\n"
    if formato == "csv":
        return formatar_csv(relatorio)
    return formatar_texto(relatorio)


def criar_parser():
    parser = argparse.ArgumentParser(
        description="Gera relatório manual, explicável e somente leitura.",
    )
    parser.add_argument("--id-conversa", type=int, action="append")
    parser.add_argument("--id-unidade", type=int, action="append")
    parser.add_argument("--todas-unidades", action="store_true")
    parser.add_argument("--inicio")
    parser.add_argument("--fim")
    parser.add_argument("--ultimas-horas", type=int, default=24)
    parser.add_argument(
        "--limite-conversas",
        type=int,
        default=DEFAULT_LIMITE_CONVERSAS,
    )
    parser.add_argument(
        "--limite-mensagens",
        type=int,
        default=DEFAULT_LIMITE_MENSAGENS,
    )
    parser.add_argument(
        "--max-mensagens-total",
        type=int,
        default=MAX_MENSAGENS_TOTAL,
    )
    parser.add_argument("--limiar", type=int, default=DEFAULT_LIMIAR)
    parser.add_argument(
        "--formato",
        choices=("texto", "json", "csv"),
        default="texto",
    )
    parser.add_argument("--saida")
    parser.add_argument("--incluir-textos", action="store_true")
    parser.add_argument("--mostrar-wa-id", action="store_true")
    parser.add_argument("--max-amostras-texto", type=int, default=5)
    parser.add_argument("--max-caracteres-texto", type=int, default=160)
    parser.add_argument(
        "--statement-timeout-ms",
        type=int,
        default=DEFAULT_STATEMENT_TIMEOUT_MS,
    )
    parser.add_argument(
        "--lock-timeout-ms",
        type=int,
        default=DEFAULT_LOCK_TIMEOUT_MS,
    )
    parser.add_argument(
        "--idle-timeout-ms",
        type=int,
        default=DEFAULT_IDLE_TIMEOUT_MS,
    )
    return parser


def validar_args(parser, args):
    if not (args.id_conversa or args.id_unidade or args.todas_unidades):
        parser.error(
            "informe --id-conversa, --id-unidade ou --todas-unidades"
        )
    limites = (
        ("--limite-conversas", args.limite_conversas, 1, MAX_CONVERSAS),
        (
            "--limite-mensagens",
            args.limite_mensagens,
            1,
            MAX_MENSAGENS_POR_CONVERSA,
        ),
        (
            "--max-mensagens-total",
            args.max_mensagens_total,
            1,
            MAX_MENSAGENS_TOTAL,
        ),
        ("--limiar", args.limiar, 0, 100),
        ("--ultimas-horas", args.ultimas_horas, 1, 31 * 24),
        ("--max-amostras-texto", args.max_amostras_texto, 0, 20),
        ("--max-caracteres-texto", args.max_caracteres_texto, 20, 500),
        ("--statement-timeout-ms", args.statement_timeout_ms, 100, 120000),
        ("--lock-timeout-ms", args.lock_timeout_ms, 50, 10000),
        ("--idle-timeout-ms", args.idle_timeout_ms, 1000, 120000),
    )
    for nome, valor, minimo, maximo in limites:
        if not minimo <= valor <= maximo:
            parser.error(f"{nome} deve estar entre {minimo} e {maximo}")
    if args.inicio and not args.fim:
        parser.error("--inicio exige --fim")
    ids = (args.id_conversa or []) + (args.id_unidade or [])
    if any(valor <= 0 for valor in ids):
        parser.error("IDs devem ser inteiros positivos")
    if (
        args.limite_conversas * args.limite_mensagens
        > args.max_mensagens_total
    ):
        parser.error(
            "--limite-conversas x --limite-mensagens não pode exceder "
            "--max-mensagens-total"
        )


def main(argv=None):
    parser = criar_parser()
    args = parser.parse_args(argv)
    validar_args(parser, args)
    try:
        relatorio = gerar_relatorio(args)
        conteudo = formatar_saida(relatorio, args.formato)
        if args.saida:
            with open(args.saida, "w", encoding="utf-8", newline="") as arquivo:
                arquivo.write(conteudo)
        else:
            sys.stdout.write(conteudo)
        return 0
    except (ValueError, RuntimeError) as exc:
        parser.exit(2, f"erro: {exc}\n")
    except Exception as exc:
        sys.stderr.write(f"erro ao gerar relatório: {type(exc).__name__}: {exc}\n")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
```

Exemplos manuais:

```bash
python relatorio_conversas_suspeitas.py --id-conversa 123 --formato texto
python relatorio_conversas_suspeitas.py --id-unidade 2 --id-unidade 7 --ultimas-horas 6 --formato json
python relatorio_conversas_suspeitas.py --todas-unidades --inicio 2025-01-15T00:00:00Z --fim 2025-01-16T00:00:00Z --limiar 65 --formato csv --saida suspeitas.csv
```

### Arquivo completo: `tests/unit/test_relatorio_conversas_suspeitas.py`

Criar:

```python
import argparse
import csv
import io
import json
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import relatorio_conversas_suspeitas as relatorio


UTC = timezone.utc
BASE = datetime(2025, 1, 15, 12, 0, tzinfo=UTC)


def mensagem(
    indice,
    *,
    segundos,
    quem,
    etapa=4,
    fingerprint=None,
    tamanho=20,
    texto=None,
    tipo="text",
    id_fila=None,
    tem_url=False,
    tem_marcador_automacao=False,
):
    return {
        "id_mensagem": indice,
        "id_mensagem_fila": id_fila,
        "id_conversa": 10,
        "id_etapa": etapa,
        "instante": BASE + timedelta(seconds=segundos),
        "tipo_mensagem": tipo,
        "quem_enviou": quem,
        "fingerprint": fingerprint or f"fp-{indice}",
        "tamanho_texto": tamanho,
        "texto": texto,
        "tem_url": tem_url,
        "tem_marcador_automacao": tem_marcador_automacao,
    }


def conversa(**alteracoes):
    dados = {
        "id_conversa": 10,
        "id_cliente": 99,
        "nome_cliente": "Maria da Silva",
        "waid_telefone": "5511999998888",
        "id_unidade": 2,
        "nome_unidade": "Unidade Centro",
        "waba_id": "waba-2",
        "phone_number_id": "phone-2",
        "id_etapa_atual": 4,
        "status_ativa": True,
        "iniciou_em": BASE,
        "finalizou_em": None,
        "motivo_encerramento": None,
        "turnos_sem_avanco": None,
    }
    dados.update(alteracoes)
    return dados


def args_padrao(**alteracoes):
    dados = {
        "id_conversa": [10],
        "id_unidade": None,
        "todas_unidades": False,
        "inicio": "2025-01-15T00:00:00Z",
        "fim": "2025-01-16T00:00:00Z",
        "ultimas_horas": 24,
        "limite_conversas": 100,
        "limite_mensagens": 100,
        "max_mensagens_total": 10000,
        "limiar": 0,
        "formato": "json",
        "saida": None,
        "incluir_textos": False,
        "mostrar_wa_id": False,
        "max_amostras_texto": 5,
        "max_caracteres_texto": 160,
        "statement_timeout_ms": 15000,
        "lock_timeout_ms": 1000,
        "idle_timeout_ms": 20000,
    }
    dados.update(alteracoes)
    return argparse.Namespace(**dados)


class FakeCursor:
    def __init__(self, *, possui_turnos=True, conversas=None, mensagens=None):
        self.possui_turnos = possui_turnos
        self.conversas = conversas or []
        self.mensagens = mensagens or []
        self.calls = []
        self._resultado = []

    def execute(self, sql, parametros=None):
        self.calls.append((sql, parametros))
        normalizado = " ".join(sql.split())
        if "information_schema.columns" in normalizado:
            self._resultado = [(self.possui_turnos,)]
        elif "FROM chatbot.conversa AS c" in normalizado:
            self._resultado = self.conversas
        elif "FROM chatbot.historico_mensagens AS h" in normalizado:
            self._resultado = self.mensagens
        else:
            self._resultado = [(None,)]

    def fetchone(self):
        return self._resultado[0]

    def fetchall(self):
        return list(self._resultado)


class FakeConn:
    def __init__(self, cursor):
        self.cursor_obj = cursor
        self.closed = False
        self.rollbacks = 0

    def cursor(self):
        return self.cursor_obj

    def close(self):
        self.closed = True

    def rollback(self):
        self.rollbacks += 1


class PontuacaoTests(unittest.TestCase):
    def test_score_explicavel_usa_as_cinco_dimensoes(self):
        mensagens = []
        for indice in range(8):
            mensagens.append(
                mensagem(
                    indice + 1,
                    segundos=indice,
                    quem="bot" if indice % 2 == 0 else "cliente",
                    fingerprint="template" if indice % 2 == 0 else "cliente",
                    tamanho=30,
                )
            )
        resultado = relatorio.pontuar_conversa(
            conversa(
                turnos_sem_avanco=12,
                finalizou_em=BASE + timedelta(seconds=8),
            ),
            mensagens,
        )
        self.assertGreaterEqual(resultado["score"], 55)
        self.assertEqual(
            set(resultado["dimensoes"]),
            {
                "fluxo_sem_avanco",
                "repeticao_ciclos",
                "cadencia",
                "conteudo_automatizado",
                "conclusao_rapida",
            },
        )
        self.assertTrue(
            all(
                "pontos" in dimensao and "razoes" in dimensao
                for dimensao in resultado["dimensoes"].values()
            )
        )

    def test_funciona_sem_coluna_futura(self):
        mensagens = [
            mensagem(
                indice,
                segundos=indice * 5,
                quem="bot" if indice % 2 else "cliente",
                etapa=4,
            )
            for indice in range(1, 10)
        ]
        resultado = relatorio.pontuar_conversa(
            conversa(turnos_sem_avanco=None),
            mensagens,
        )
        self.assertIsInstance(resultado["score"], int)
        razoes = resultado["dimensoes"]["fluxo_sem_avanco"]["razoes"]
        self.assertFalse(any("contador persistido" in item for item in razoes))

    def test_fluxo_normal_nao_recebe_score_alto(self):
        mensagens = [
            mensagem(
                indice,
                segundos=indice * 60,
                quem="cliente" if indice % 2 else "bot",
                etapa=indice,
            )
            for indice in range(1, 7)
        ]
        resultado = relatorio.pontuar_conversa(
            conversa(turnos_sem_avanco=0),
            mensagens,
        )
        self.assertLess(resultado["score"], relatorio.DEFAULT_LIMIAR)

    def test_mesma_resposta_em_etapas_diferentes_nao_forma_loop(self):
        mensagens = [
            mensagem(
                indice,
                segundos=indice * 30,
                quem="cliente",
                etapa=indice,
                fingerprint="frequentemente",
                tipo="interactive",
            )
            for indice in range(1, 7)
        ]
        resultado = relatorio.pontuar_conversa(
            conversa(turnos_sem_avanco=None),
            mensagens,
        )
        repeticao = resultado["dimensoes"]["repeticao_ciclos"]
        self.assertEqual(repeticao["pontos"], 0)
        self.assertEqual(
            resultado["metricas"]["ciclos_cliente_detectados"],
            0,
        )

    def test_repeticao_do_nosso_bot_nao_pontua_conteudo_do_cliente(self):
        clientes = [
            mensagem(
                indice * 2,
                segundos=indice * 20,
                quem="cliente",
                etapa=indice,
                fingerprint=f"cliente-{indice}",
                tamanho=indice * 10,
            )
            for indice in range(1, 5)
        ]
        bots_repetidos = [
            mensagem(
                indice * 2 - 1,
                segundos=indice * 20 - 10,
                quem="bot",
                etapa=4,
                fingerprint="template-do-nosso-bot",
            )
            for indice in range(1, 5)
        ]
        resultado = relatorio.pontuar_conversa(
            conversa(),
            clientes + bots_repetidos,
        )
        self.assertEqual(
            resultado["dimensoes"]["conteudo_automatizado"]["pontos"],
            0,
        )
        self.assertEqual(
            resultado["metricas"]["respostas_cliente_repetidas_na_mesma_etapa"],
            0,
        )

    def test_cliente_abab_na_mesma_etapa_e_sinal_de_ciclo(self):
        mensagens = [
            mensagem(
                indice,
                segundos=indice * 10,
                quem="cliente",
                etapa=4,
                fingerprint=fingerprint,
            )
            for indice, fingerprint in enumerate(
                ("A", "B", "A", "B"),
                start=1,
            )
        ]
        resultado = relatorio.pontuar_conversa(conversa(), mensagens)
        self.assertGreater(
            resultado["dimensoes"]["repeticao_ciclos"]["pontos"],
            0,
        )
        self.assertGreater(
            resultado["metricas"]["ciclos_cliente_detectados"],
            0,
        )

    def test_latencia_e_bot_para_primeiro_cliente_seguinte(self):
        mensagens = [
            mensagem(1, segundos=0, quem="bot"),
            mensagem(2, segundos=1, quem="cliente"),
            mensagem(3, segundos=2, quem="cliente"),
            mensagem(4, segundos=10, quem="bot"),
            mensagem(5, segundos=15, quem="cliente"),
        ]
        resultado = relatorio.pontuar_conversa(conversa(), mensagens)
        self.assertEqual(
            resultado["metricas"]["latencias_bot_cliente"],
            [1.0, 5.0],
        )

    def test_movimentos_sao_pareados_por_id_mensagem_fila(self):
        mensagens = [
            mensagem(
                1,
                segundos=0,
                quem="cliente",
                etapa=None,
                id_fila=101,
            ),
            mensagem(
                2,
                segundos=1,
                quem="bot",
                etapa=1,
                id_fila=101,
            ),
            mensagem(
                3,
                segundos=10,
                quem="cliente",
                etapa=4,
                id_fila=102,
            ),
            mensagem(
                4,
                segundos=11,
                quem="bot",
                etapa=5,
                id_fila=102,
            ),
            mensagem(
                5,
                segundos=20,
                quem="cliente",
                etapa=5,
                id_fila=103,
            ),
            mensagem(
                6,
                segundos=21,
                quem="bot",
                etapa=5,
                id_fila=103,
            ),
            mensagem(
                7,
                segundos=30,
                quem="cliente",
                etapa=5,
                id_fila=None,
            ),
        ]
        self.assertEqual(
            [
                item["tipo"]
                for item in relatorio.reconstruir_movimentos(mensagens)
            ],
            ["inicializacao", "avanco", "sem_avanco", "indeterminado"],
        )

    def test_contador_doze_sozinho_supera_limiar_padrao(self):
        resultado = relatorio.pontuar_conversa(
            conversa(turnos_sem_avanco=12),
            [],
        )
        self.assertEqual(
            resultado["dimensoes"]["fluxo_sem_avanco"]["pontos"],
            70,
        )
        self.assertGreaterEqual(
            resultado["score"],
            relatorio.DEFAULT_LIMIAR,
        )


class PrivacidadeEFormatosTests(unittest.TestCase):
    def test_mascaramento_de_pii(self):
        original = (
            "maria@example.com +55 (11) 99999-8888 "
            "123.456.789-09 https://exemplo.com/abc 123456789"
        )
        mascarado = relatorio.mascarar_pii(original)
        self.assertNotIn("maria@example.com", mascarado)
        self.assertNotIn("99999-8888", mascarado)
        self.assertNotIn("123.456.789-09", mascarado)
        self.assertNotIn("https://exemplo.com/abc", mascarado)
        self.assertIn("[EMAIL]", mascarado)
        self.assertIn("[URL]", mascarado)
        self.assertEqual(
            relatorio.mascarar_wa_id("5511999998888"),
            "*********8888",
        )
        self.assertEqual(
            relatorio.mascarar_wa_id(
                "5511999998888",
                mostrar=True,
            ),
            "5511999998888",
        )
        self.assertNotEqual(
            relatorio.mascarar_nome("Maria da Silva"),
            "Maria da Silva",
        )

    def test_json_csv_e_texto_sao_validos(self):
        item = {
            "id_conversa": 10,
            "id_cliente": 99,
            "nome_cliente_mascarado": "M*** d*** S***",
            "wa_id_cliente": "*********8888",
            "id_unidade": 2,
            "nome_unidade": "Centro",
            "waba_id": "waba-2",
            "phone_number_id": "phone-2",
            "score": 80,
            "status_ativa": True,
            "id_etapa_atual": 4,
            "iniciou_em": BASE.isoformat(),
            "finalizou_em": None,
            "turnos_sem_avanco": 12,
            "historico_truncado": False,
            "dimensoes": {
                "fluxo_sem_avanco": {
                    "pontos": 20,
                    "maximo": 25,
                    "razoes": ["contador alto"],
                }
            },
            "metricas": {},
        }
        documento = {
            "metadados": {
                "inicio": BASE.isoformat(),
                "fim": (BASE + timedelta(hours=1)).isoformat(),
                "conversas_lidas": 1,
                "conversas_reportadas": 1,
                "limiar": 55,
            },
            "conversas": [item],
        }
        self.assertEqual(
            json.loads(relatorio.formatar_saida(documento, "json"))["conversas"][0]["score"],
            80,
        )
        linhas_csv = list(
            csv.DictReader(
                io.StringIO(relatorio.formatar_saida(documento, "csv"))
            )
        )
        self.assertEqual(linhas_csv[0]["id_conversa"], "10")
        self.assertIn(
            "conversa=10",
            relatorio.formatar_saida(documento, "texto"),
        )


class BancoSomenteLeituraTests(unittest.TestCase):
    def _linha_conversa(self, turnos):
        return (
            10,
            99,
            "Maria da Silva",
            "5511999998888",
            2,
            "Centro",
            "waba-2",
            "phone-2",
            4,
            True,
            BASE,
            None,
            None,
            turnos,
        )

    def _linha_mensagem(self):
        return (
            1,
            1001,
            10,
            4,
            BASE,
            "text",
            "bot",
            "fingerprint",
            20,
            False,
            False,
            None,
            1,
        )

    def test_transacao_timeouts_selects_e_texto_omitido(self):
        cursor = FakeCursor(
            possui_turnos=False,
            conversas=[self._linha_conversa(None)],
            mensagens=[self._linha_mensagem()],
        )
        conn = FakeConn(cursor)
        documento = relatorio.gerar_relatorio(
            args_padrao(),
            connection_factory=lambda **_kwargs: conn,
        )
        sql_total = "\n".join(sql for sql, _params in cursor.calls)
        self.assertIn(
            "BEGIN TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY",
            sql_total,
        )
        self.assertIn("statement_timeout", sql_total)
        self.assertIn("lock_timeout", sql_total)
        self.assertIn("idle_in_transaction_session_timeout", sql_total)
        self.assertIn("NULL::integer AS turnos_sem_avanco", sql_total)
        self.assertIn("NULL::text AS conteudo_texto", sql_total)
        self.assertIn(
            "ORDER BY h.received_data_hora DESC, h.id_mensagem DESC",
            sql_total,
        )
        self.assertIn("JOIN chatbot.cliente AS cl", sql_total)
        self.assertIn("u.waba_id", sql_total)
        self.assertIn("u.phone_number_id", sql_total)
        self.assertNotRegex(
            sql_total.upper(),
            r"\b(INSERT|UPDATE|DELETE|ALTER|CREATE|DROP|TRUNCATE|FOR UPDATE)\b",
        )
        self.assertNotIn("cliente_telefone", sql_total)
        self.assertNotIn("id_phone_unidade", sql_total)
        self.assertTrue(conn.closed)
        self.assertEqual(conn.rollbacks, 1)
        self.assertFalse(documento["metadados"]["textos_incluidos"])
        self.assertEqual(
            documento["conversas"][0]["wa_id_cliente"],
            "*********8888",
        )

    def test_coluna_futura_e_texto_explicito(self):
        linha = list(self._linha_mensagem())
        linha[11] = "contato maria@example.com"
        cursor = FakeCursor(
            possui_turnos=True,
            conversas=[self._linha_conversa(12)],
            mensagens=[tuple(linha)],
        )
        conn = FakeConn(cursor)
        documento = relatorio.gerar_relatorio(
            args_padrao(incluir_textos=True),
            connection_factory=lambda **_kwargs: conn,
        )
        sql_total = "\n".join(sql for sql, _params in cursor.calls)
        self.assertIn("c.turnos_sem_avanco", sql_total)
        self.assertIn("h.conteudo_texto", sql_total)
        amostra = documento["conversas"][0]["amostras_texto_mascarado"][0]
        self.assertEqual(amostra["texto"], "contato [EMAIL]")

    def test_wa_id_completo_exige_flag_explicita(self):
        cursor = FakeCursor(
            conversas=[self._linha_conversa(12)],
            mensagens=[],
        )
        documento = relatorio.gerar_relatorio(
            args_padrao(mostrar_wa_id=True),
            connection_factory=lambda **_kwargs: FakeConn(cursor),
        )
        self.assertEqual(
            documento["conversas"][0]["wa_id_cliente"],
            "5511999998888",
        )

    def test_limite_de_conversas_falha_fechando_conexao(self):
        cursor = FakeCursor(
            conversas=[
                self._linha_conversa(0),
                self._linha_conversa(0),
            ]
        )
        conn = FakeConn(cursor)
        with self.assertRaisesRegex(RuntimeError, "limite de conversas"):
            relatorio.gerar_relatorio(
                args_padrao(limite_conversas=1),
                connection_factory=lambda **_kwargs: conn,
            )
        self.assertTrue(conn.closed)

    def test_filtros_multiunidade_sao_parametrizados(self):
        cursor = FakeCursor()
        conn = FakeConn(cursor)
        relatorio.gerar_relatorio(
            args_padrao(
                id_conversa=None,
                id_unidade=[2, 7],
                todas_unidades=False,
            ),
            connection_factory=lambda **_kwargs: conn,
        )
        chamada = next(
            (sql, params)
            for sql, params in cursor.calls
            if "FROM chatbot.conversa AS c" in sql
        )
        self.assertIn("c.id_unidade = ANY(%s)", chamada[0])
        self.assertIn([2, 7], chamada[1])


class CliELimitesTests(unittest.TestCase):
    def test_cli_exige_escopo_explicito(self):
        parser = relatorio.criar_parser()
        args = parser.parse_args([])
        with self.assertRaises(SystemExit):
            relatorio.validar_args(parser, args)

    def test_janela_maxima_e_validada(self):
        with self.assertRaisesRegex(ValueError, "31 dias"):
            relatorio.resolver_janela(
                args_padrao(
                    inicio="2025-01-01T00:00:00Z",
                    fim="2025-03-01T00:00:00Z",
                )
            )

    def test_main_escreve_stdout_sem_arquivo(self):
        documento = {
            "metadados": {
                "inicio": BASE.isoformat(),
                "fim": (BASE + timedelta(hours=1)).isoformat(),
                "conversas_lidas": 0,
                "conversas_reportadas": 0,
                "limiar": 55,
            },
            "conversas": [],
        }
        with patch.object(
            relatorio,
            "gerar_relatorio",
            return_value=documento,
        ), patch.object(relatorio.sys, "stdout", new_callable=io.StringIO) as saida:
            codigo = relatorio.main(["--id-conversa", "10"])
        self.assertEqual(codigo, 0)
        self.assertIn("RELATÓRIO MANUAL", saida.getvalue())


if __name__ == "__main__":
    unittest.main()
```

Validação planejada para este passo, sem conexão com o RDS:

```bash
python -m unittest tests.unit.test_relatorio_conversas_suspeitas
python -m py_compile relatorio_conversas_suspeitas.py tests/unit/test_relatorio_conversas_suspeitas.py
git diff --check
```

Antes do primeiro uso no RDS, a credencial manual deve ter privilégio
`CONNECT` e `SELECT` apenas, sem privilégios de escrita. Mesmo com essa defesa
externa, o próprio script mantém a transação como `READ ONLY` e não executa
qualquer SQL de bloqueio.

---

## Passo 8 — validação antes do deploy

Executar localmente:

```bash
python -m unittest discover -s tests -p "test_*.py"
python callback/manage.py check
python -m compileall -q callback core workers tests
git diff --check
```

Ao final da implementação, gerar e aplicar o comando SQL que sincronizará o RDS
existente com o DDL-fonte. Antes de iniciar o código novo, validar no RDS:

```sql
SELECT
    column_name,
    data_type,
    is_nullable,
    column_default
FROM information_schema.columns
WHERE table_schema = 'chatbot'
  AND table_name = 'conversa'
  AND column_name = 'turnos_sem_avanco';

SELECT
    conname,
    pg_get_constraintdef(oid)
FROM pg_constraint
WHERE conrelid = 'chatbot.conversa'::regclass
  AND conname = 'ck_conversa_turnos_sem_avanco';
```

## 5. Fluxos finais previstos

### 5.1 Mensagem comum e proteção por 12 turnos

1. O webhook valida tipo de conteúdo, tamanho, assinatura e JSON.
2. O evento é classificado dentro do bloco protegido contra exceção genérica.
3. Para uma mensagem, são extraídos WAMID, WA ID, `phone_number_id` e nome do
   profile.
4. O guard consulta a denylist pelo par WA ID + unidade.
5. Se não existir denylist, consulta somente a conversa ativa daquele mesmo par.
6. Abaixo de 12, o webhook continua para anti-flood, unidade, bloqueio
   temporário e fila.
7. Em 12, registra ou atualiza `cliente_bloqueado_meta`, incluindo o nome
   disponível, e confirma o commit.
8. Só depois do commit tenta bloquear o número na Meta.
9. A mensagem que disparou a promoção retorna HTTP 200 e não entra na fila,
   mesmo se a Meta recusar o bloqueio.
10. Toda mensagem futura daquele par repete a tentativa na Meta e continua
    ignorada enquanto a denylist existir.

O bloqueio é do número para a unidade correspondente; não existe bloqueio
global do cliente em todas as unidades.

### 5.2 Atualização transacional no worker

1. Dequeue, barreira de turnos, validações, lock, vínculo com conversa,
   histórico do cliente e envio pela Meta permanecem na ordem atual.
2. Na transação final já existente, o worker insere ou recupera o histórico do
   bot e persiste o movimento da conversa.
3. Tratamento novo, com histórico novo e sem avanço, incrementa uma vez.
4. Retry que recuperou histórico já persistido não incrementa.
5. Transição válida zera o contador, inclusive quando o valor já era zero.
6. Contador, histórico, movimento, efeitos e encerramento confirmam ou sofrem
   rollback juntos.
7. A fila só é marcada como `sent` na etapa transacional já existente depois
   desse contexto final.

Não são alterados `reagendar_mensagem`, `bot_resposta_atual`, a barreira de
turnos, o lock da conversa, os resolvers das etapas nem a elegibilidade do
funil.

### 5.3 Anti-flood por WAMID único

1. A denylist continua sendo consultada antes do anti-flood.
2. No Redis, um script atômico faz `SET NX` do WAMID e incrementa os contadores
   somente para evento novo.
3. Reentrega do mesmo WAMID não aumenta a rajada.
4. Quinze WAMIDs distintos em cinco segundos continuam caracterizando flood.
5. Se o Redis falhar, o PostgreSQL usa a unicidade global do WAMID e conta por
   WA ID + unidade.
6. Se esse caminho também falhar depois da consulta inicial da denylist, o
   processo atual usa o fallback em memória limitado.
7. Detectado o flood, a denylist é persistida antes da chamada à Meta.

### 5.4 Exceção inesperada do webhook

1. Somente o último `except Exception` genérico usa o orçamento por WAMID.
2. As três primeiras falhas identificáveis retornam HTTP 503.
3. Na quarta, o webhook retorna HTTP 200 e descarta apenas aquele evento.
4. Um WAMID novo começa com orçamento próprio.
5. Sem WAMID ou sem Redis, retorna HTTP 200 para não criar loop infinito.
6. Esse mecanismo nunca bloqueia o remetente e não usa o retry do worker.

As exceções específicas de banco, unidade, bloqueio temporário e inserção da
fila preservam seus tratamentos próprios.

### 5.5 Recuperação de falso positivo

1. A exclusão unitária da denylist no Admin tenta desbloquear primeiro na Meta.
2. Confirmado o desbloqueio externo, o Admin zera `turnos_sem_avanco` da
   conversa ativa e remove a denylist na mesma transação local.
3. Se a alteração local falhar, o banco faz rollback; o operador deve repetir a
   recuperação antes de admitir novas mensagens.
4. A exclusão em massa continua proibida.
5. O SQL de emergência documentado faz o mesmo reset + delete de forma atômica.

### 5.6 Relatório manual

1. O desenvolvedor escolhe conversa, unidade ou autoriza explicitamente todas
   as unidades, sempre dentro de uma janela limitada.
2. O utilitário abre uma transação `REPEATABLE READ READ ONLY`.
3. Carrega conversas e as mensagens mais recentes dentro dos limites.
4. Reconstrói movimentos pelo `id_mensagem_fila`.
5. Analisa somente o comportamento do remetente externo: falta de avanço,
   repetição/ciclos, latência bot→cliente, marcadores de automação e conclusão
   anormalmente rápida.
6. Produz texto, JSON ou CSV com score e justificativas; PII fica mascarada por
   padrão.
7. Executa rollback e encerra a conexão.

Esse relatório não participa do webhook, dos workers, do Redis, da Meta nem do
funil.

## 6. Cenários de aceite

Antes do deploy, todos estes cenários precisam estar cobertos:

1. tratamento novo incrementa de 0 para 1;
2. cinco tratamentos deixam `turnos_sem_avanco` em 5;
3. resposta válida no sexto turno avança a etapa e zera
   `turnos_sem_avanco`;
4. novo tratamento na etapa seguinte começa novamente em 1;
5. retry de resposta já persistida não incrementa;
6. rollback do worker não deixa incremento isolado;
7. inicialização de conversa permanece em zero;
8. `turnos_sem_avanco` nunca ultrapassa 12;
9. ao chegar a 12, a próxima mensagem promove o número para a denylist daquela
   unidade e é ignorada sem entrar na fila;
10. a promoção grava `cliente_bloqueado_meta` antes da chamada à Meta;
11. o nome salvo no banco tem precedência e o nome do profile é fallback;
12. falha da Meta mantém a denylist e retorna HTTP 200 ignorado;
13. nova mensagem do número marcado repete a tentativa na Meta;
14. falha do banco retorna HTTP 503 e não chama a Meta;
15. o mesmo WA ID em outra unidade não herda `turnos_sem_avanco`;
16. outro WA ID na mesma unidade não herda `turnos_sem_avanco`;
17. conversa nova começa em zero;
18. conversa encerrada não é promovida por esse guard;
19. duas promoções concorrentes convergem para a mesma denylist;
20. desbloqueio unitário reseta o contador e remove a denylist;
21. quinze reentregas do mesmo WAMID não simulam flood;
22. quinze WAMIDs diferentes ainda disparam flood;
23. erro genérico retorna 503 três vezes e 200 na quarta;
24. o relatório não executa SQL de escrita nem chama serviços externos;
25. seis respostas iguais em etapas diferentes da triagem não viram loop no
    relatório;
26. repetição das mensagens do próprio chatbot não pontua o cliente;
27. webhook, worker de atendimento e worker de funil continuam passando em toda
    a suíte de regressão.

## 7. Ordem segura de implantação

1. implementar e validar localmente os Passos especiais 0 e 0B;
2. implementar e validar todos os arquivos dos Passos 1 a 7;
3. criar e validar localmente o relatório manual, sem consultar o RDS durante
   os testes unitários;
4. executar toda a suíte, `manage.py check`, compilação e `git diff --check`;
5. comparar o DDL final com o estado real do RDS;
6. gerar fora do código Python o SQL operacional de sincronização;
7. fazer backup lógico ou snapshot do RDS;
8. parar somente os serviços necessários;
9. aplicar primeiro o SQL e confirmar coluna, default, `NOT NULL` e
   `CHECK (turnos_sem_avanco BETWEEN 0 AND 12)`;
10. publicar o código somente depois de o schema estar confirmado;
11. reiniciar webhook e worker de atendimento;
12. o worker do funil não recebe código novo, mas deve permanecer na regressão;
13. acompanhar logs de flood, erro genérico, incremento, reset e promoção;
14. testar com um contato controlado abaixo do limite, no limite e após uma
    transição válida;
15. testar a recuperação de falso positivo;
16. manter rollback de código disponível;
17. não remover a coluna em um rollback imediato, pois o código anterior a
    ignora;
18. executar o relatório manual fora do horário de pico e inicialmente com
    janela pequena.

## 8. Auditoria de impacto e riscos residuais

| Área | Impacto | Mitigação ou decisão |
|---|---|---|
| Regra central das etapas | Nenhum resolver, transição ou mensagem é alterado. | Suíte integral e cenários por etapa continuam obrigatórios. |
| Worker transacional | Ganha um `UPDATE` dentro da transação final. | Mesmo cursor, mesmo commit e rollback conjunto; retry com histórico existente não incrementa. |
| Janela Meta → banco | A nova instrução SQL aumenta minimamente a superfície da falha já conhecida após envio e antes do commit. | Não cria uma classe nova de duplicidade; o problema preexistente de fencing/tracker continua documentado para solução futura. |
| Concorrência do worker | Um worker retomado após lease vencido ainda pode sobrepor o antigo. | Limitação preexistente aceita na V1; o plano não remove locks nem barreira de turnos. |
| Webhook | Mensagem não denylisted ganha uma consulta simples à conversa ativa. | Índice parcial existente atende cliente + unidade; consulta não usa `FOR UPDATE`. |
| Promoções concorrentes | Duas requisições podem observar 12 ao mesmo tempo. | O upsert único da denylist torna a promoção idempotente; ambas ignoram a mensagem. |
| Falso positivo | Um humano pode errar doze tratamentos consecutivos. | Limite conservador, reset em qualquer avanço e recuperação Admin/SQL que também zera o contador. |
| Bot capaz de avançar | Uma IA dirigida pode responder corretamente antes de 12 erros e escapar. | Limitação consciente: relatório manual procura cadência, ciclos, conteúdo e conclusão rápida; não há bloqueio sem evidência operacional. |
| Funil | Um bot que alcance etapa elegível pode ser materializado no funil antes de ser detectado. | O plano não muda a regra comercial das etapas 16–19; revisar candidatos pelo relatório e pelos dados do funil. |
| Redis anti-flood | Caminho principal é atômico; fallback em memória não é distribuído. | PostgreSQL é o primeiro fallback; memória é limitada e explicitamente degradada por processo. |
| PostgreSQL anti-flood | WAMID é único globalmente no DDL, enquanto a contagem é por par. | Compatível com a unicidade esperada do WAMID da Meta; o plano não promete isolamento hipotético do mesmo WAMID entre phones. |
| Erro genérico 0B | Retornar 503 pode repetir trabalho concluído antes da exceção. | Orçamento máximo de três; transações e unicidade de WAMID reduzem duplicação, mas o risco residual não é zero. |
| Falha Redis no 0B | Sem orçamento distribuído, o evento genérico é descartado com HTTP 200. | Escolha fail-open deliberada para evitar reentrega infinita. |
| Relatório manual | Pode gerar leitura pesada e falso positivo heurístico. | Read-only, timeouts, filtros e limites; score apenas prioriza revisão humana e nunca bloqueia. |
| Multi-WABA | Contador e bloqueio precisam permanecer por conversa/unidade. | Todas as consultas usam conversa, WA ID e `phone_number_id`; cliente global não compartilha contador. |

Não existe detector infalível de IA baseado apenas no conteúdo recebido. Uma
automação sofisticada pode imitar latência humana, variar textos e avançar
corretamente. O objetivo da V1 é impedir loops caros e oferecer evidência para
ajustes posteriores, não prometer identificação universal.

## 9. Decisão final

Após as correções desta revisão, o plano está coerente e apto para
implementação, desde que a ordem schema primeiro → código → regressão seja
respeitada.

A proteção automática é pequena e bem delimitada: doze tratamentos
consecutivos, na mesma conversa e sem avanço, impedem novas mensagens daquele
par cliente + unidade. Ela não bloqueia o cliente globalmente e qualquer
transição válida reinicia o contador.

Não há mudança drástica na lógica central do atendimento. Fila, locks,
`reagendar_mensagem`, `bot_resposta_atual`, resolvers, etapas e política do
funil permanecem. Existe uma alteração transacional real e intencional: o
worker passa a persistir o contador no mesmo commit do resultado do turno.

Os Passos especiais também estão isolados:

- o Passo 0 corrige reentrega de WAMID no anti-flood;
- o Passo 0B limita a três reentregas uma exceção genérica;
- o relatório manual apenas lê e classifica candidatos para revisão.

O principal limite aceito é funcional, não um buraco transacional: um bot ou IA
que avance corretamente pode não atingir 12. Isso não produz loop infinito,
mas pode produzir um lead falso. O relatório manual foi incluído justamente
para medir esse comportamento antes de adicionar regras automáticas mais
agressivas e arriscadas.
