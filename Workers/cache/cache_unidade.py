from Database.redis_client import get_redis_safe
from SQLfunctions.Querys import pegar_unidades, buscar_id_unidade_por_phone_id
from Database.connectionAWS import get_conn

REDIS_KEY = "unidades_cache"
CACHE_VERSION_KEY = "unidades_cache_version"
TTL = 60


class UnidadeNaoEncontrada(Exception):
    pass


# ==============================
# 🔥 CARREGAMENTO INICIAL
# ==============================

def carregar_unidades_redis_primeira_vez():
    try:
        r = get_redis_safe()

        conn = get_conn()
        cursor = conn.cursor()

        unidades_raw = pegar_unidades(cursor)
        conn.close()

        unidades = _normalizar_unidades(unidades_raw)

        if not unidades:
            return

        _salvar_cache(r, unidades)

        print(f"📦 Cache Redis inicial carregado: {len(unidades)} unidades")

    except Exception as e:
        print(f"⚠️ Erro ao carregar cache inicial: {e}")


# ==============================
# 🔁 ATUALIZAÇÃO INTELIGENTE
# ==============================

def carregar_cache_redis(cursor):
    try:
        r = get_redis_safe()

        unidades_raw = pegar_unidades(cursor)
        unidades = _normalizar_unidades(unidades_raw)

        if not unidades:
            return

        _salvar_cache(r, unidades)

        print(f"📦 Cache Redis atualizado: {len(unidades)} unidades")

    except Exception as e:
        print(f"⚠️ Erro ao atualizar cache: {e}")


# ==============================
# 🧠 LEITURA COM FALLBACK
# ==============================

def obter_id_unidade_redis_ou_plsql(id_phone_unidade, cursor):
    phone_key = _normalizar_phone_number_id(id_phone_unidade)

    if phone_key is None:
        raise UnidadeNaoEncontrada("phone_number_id inválido")

    r = None

    # ======================
    # 1. CACHE (Redis)
    # ======================
    try:
        r = get_redis_safe()
        id_unidade = r.hget(REDIS_KEY, phone_key)

        if id_unidade:
            return int(id_unidade)

    except Exception as e:
        print(f"⚠️ Redis indisponível: {e}")

    # ======================
    # 2. BANCO (FONTE VERDADE)
    # ======================
    id_unidade = buscar_id_unidade_por_phone_id(phone_key, cursor)

    if not _id_unidade_valido(id_unidade):
        raise UnidadeNaoEncontrada(f"Unidade não encontrada: {phone_key}")

    # ======================
    # 3. REABASTECE CACHE
    # ======================
    try:
        if r is None:
            r = get_redis_safe()

        r.hset(REDIS_KEY, phone_key, int(id_unidade))

    except Exception:
        pass

    return int(id_unidade)


# ==============================
# 🔄 VALIDAÇÃO DE CACHE (BLINDAGEM LEVE)
# ==============================

def atualizar_unidade_redis_se_necessario(cursor):
    try:
        r = get_redis_safe()

        # 🔥 blindagem leve:
        # não confia só em exists → valida integridade mínima
        if not _cache_valido(r):
            print("🔄 Cache inválido ou expirado, recarregando...")
            carregar_cache_redis(cursor)

    except Exception as e:
        print(f"⚠️ Redis indisponível ao validar cache: {e}")


# ==============================
# 💾 SALVAMENTO CENTRALIZADO
# ==============================

def _salvar_cache(r, unidades):
    r.hset(REDIS_KEY, mapping=unidades)
    r.set(CACHE_VERSION_KEY, len(unidades), ex=TTL)
    r.expire(REDIS_KEY, TTL)


def _cache_valido(r):
    try:
        return (
            r.exists(REDIS_KEY)
            and r.exists(CACHE_VERSION_KEY)
        )
    except:
        return False


# ==============================
# 🔧 NORMALIZAÇÕES
# ==============================

def _normalizar_unidades(unidades_raw):
    if isinstance(unidades_raw, list):
        return {
            str(u["phone_number_id"]).strip(): int(u["id_unidade"])
            for u in unidades_raw
            if u.get("phone_number_id") and u.get("id_unidade")
        }

    if isinstance(unidades_raw, dict):
        return {
            str(k).strip(): int(v)
            for k, v in unidades_raw.items()
            if k and v
        }

    return {}


def _id_unidade_valido(id_unidade):
    try:
        return int(id_unidade) > 0
    except:
        return False


def _normalizar_phone_number_id(id_phone_unidade):
    if id_phone_unidade is None:
        return None

    if isinstance(id_phone_unidade, str):
        s = id_phone_unidade.strip()
        return s if s else None

    return str(id_phone_unidade)
















# from Database.redis_client import get_redis_safe
# from SQLfunctions.Querys import pegar_unidades, buscar_id_unidade_por_phone_id
# from Database.connectionAWS import get_conn
#
# REDIS_KEY = "unidades_cache"
# TTL = 60
#
#
# class UnidadeNaoEncontrada(Exception):
#     pass
#
#
# def carregar_cache_redis_primeira_vez():
#     try:
#         r = get_redis_safe()
#
#         conn = get_conn()
#         cursor = conn.cursor()
#
#         unidades_raw = pegar_unidades(cursor)
#         conn.close()
#
#         unidades = _normalizar_unidades(unidades_raw)
#
#         if not unidades:
#             return
#
#         r.hset(REDIS_KEY, mapping=unidades)
#         r.expire(REDIS_KEY, TTL)
#
#         print(f"📦 Cache Redis carregado: {len(unidades)} unidades")
#
#     except Exception as e:
#         print(f"⚠️ Erro ao carregar cache Redis: {e}")
#
#
# def carregar_cache_redis(cursor):
#     try:
#         r = get_redis_safe()
#
#         unidades_raw = pegar_unidades(cursor)
#         unidades = _normalizar_unidades(unidades_raw)
#
#         if not unidades:
#             return
#
#         r.hset(REDIS_KEY, mapping=unidades)
#         r.expire(REDIS_KEY, TTL)
#
#         print(f"📦 Cache Redis carregado: {len(unidades)} unidades")
#
#     except Exception as e:
#         print(f"⚠️ Erro ao carregar cache Redis: {e}")
#
#
# def obter_id_unidade(id_phone_unidade, cursor):
#     phone_key = _normalizar_phone_number_id(id_phone_unidade)
#
#     if phone_key is None:
#         raise UnidadeNaoEncontrada("phone_number_id inválido")
#
#     id_unidade = None
#
#     # 🔥 Redis seguro
#     try:
#         r = get_redis_safe()
#         id_unidade = r.hget(REDIS_KEY, phone_key)
#     except Exception as e:
#         print(f"⚠️ Redis indisponível: {e}")
#
#     if id_unidade:
#         try:
#             return int(id_unidade)
#         except:
#             print("⚠️ Valor inválido no Redis")
#
#     # fallback banco
#     id_unidade = buscar_id_unidade_por_phone_id(phone_key, cursor)
#
#     if not _id_unidade_valido(id_unidade):
#         raise UnidadeNaoEncontrada(f"Unidade não encontrada: {phone_key}")
#
#     # reabastece cache
#     try:
#         r = get_redis_safe()
#         r.hset(REDIS_KEY, phone_key, int(id_unidade))
#     except:
#         pass
#
#     return int(id_unidade)
#
#
# def atualizar_cache_se_necessario(cursor):
#     try:
#         r = get_redis_safe()
#
#         if not r.exists(REDIS_KEY):
#             print("🔄 Recarregando cache Redis...")
#             carregar_cache_redis(cursor)
#
#     except Exception as e:
#         print(f"⚠️ Redis indisponível: {e}")
#
#
# # ---------- utils ----------
#
# def _normalizar_unidades(unidades_raw):
#     if isinstance(unidades_raw, list):
#         return {
#             str(u["phone_number_id"]).strip(): int(u["id_unidade"])
#             for u in unidades_raw
#             if u.get("phone_number_id") and u.get("id_unidade")
#         }
#
#     if isinstance(unidades_raw, dict):
#         return {
#             str(k).strip(): int(v)
#             for k, v in unidades_raw.items()
#             if k and v
#         }
#
#     return {}
#
#
# def _id_unidade_valido(id_unidade):
#     try:
#         return int(id_unidade) > 0
#     except:
#         return False
#
#
# def _normalizar_phone_number_id(id_phone_unidade):
#     if id_phone_unidade is None:
#         return None
#
#     if isinstance(id_phone_unidade, str):
#         s = id_phone_unidade.strip()
#         return s if s else None
#
#     return str(id_phone_unidade)