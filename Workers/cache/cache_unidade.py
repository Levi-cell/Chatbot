from Database.redis_client import get_redis
from SQLfunctions.Querys import pegar_unidades, buscar_id_unidade_por_phone_id

REDIS_KEY = "unidades_cache"
TTL = 60  # segundos


class UnidadeNaoEncontrada(Exception):
    pass


def carregar_cache_redis():
    r = get_redis()

    try:
        unidades_raw = pegar_unidades()

        if not unidades_raw:
            return

        # 🔥 GARANTE FORMATO CORRETO
        # esperado: {phone_number_id: id_unidade}
        if isinstance(unidades_raw, list):
            unidades = {
                str(u["phone_number_id"]).strip(): int(u["id_unidade"])
                for u in unidades_raw
                if u.get("phone_number_id") and u.get("id_unidade")
            }
        elif isinstance(unidades_raw, dict):
            unidades = {
                str(k).strip(): int(v)
                for k, v in unidades_raw.items()
                if k and v
            }
        else:
            print("⚠️ Formato inesperado de unidades")
            return

        if not unidades:
            return

        # salva tudo como hash no redis
        r.hset(REDIS_KEY, mapping=unidades)
        r.expire(REDIS_KEY, TTL)

        print(f"📦 Cache Redis carregado: {len(unidades)} unidades")

    except Exception as e:
        print(f"⚠️ Erro ao carregar cache Redis: {e}")


def obter_id_unidade(id_phone_unidade):
    r = get_redis()

    phone_key = _normalizar_phone_number_id(id_phone_unidade)

    if phone_key is None:
        raise UnidadeNaoEncontrada("phone_number_id inválido")

    id_unidade = None

    # 🔥 1. TENTA REDIS (sem quebrar)
    try:
        id_unidade = r.hget(REDIS_KEY, phone_key)
    except Exception as e:
        print(f"⚠️ Redis indisponível: {e}")

    if id_unidade:
        try:
            return int(id_unidade)
        except:
            print("⚠️ Valor inválido no Redis, ignorando...")

    # 🛟 2. FALLBACK PRO BANCO (OBRIGATÓRIO)
    id_unidade = buscar_id_unidade_por_phone_id(phone_key)

    if not _id_unidade_valido(id_unidade):
        raise UnidadeNaoEncontrada(f"Unidade não encontrada: {phone_key}")

    # 🔁 3. TENTA REABASTECER CACHE (sem quebrar)
    try:
        r.hset(REDIS_KEY, phone_key, int(id_unidade))
    except Exception:
        pass

    return int(id_unidade)


def atualizar_cache_se_necessario():
    try:
        r = get_redis()

        # se a chave expirou → recarrega
        if not r.exists(REDIS_KEY):
            print("🔄 Recarregando cache Redis...")
            carregar_cache_redis()

    except Exception as e:
        print(f"⚠️ Redis indisponível ao verificar cache: {e}")


# ---------- utils ----------

def _id_unidade_valido(id_unidade):
    if id_unidade is None:
        return False
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