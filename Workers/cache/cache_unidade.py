import time
from SQLfunctions.Querys import pegar_unidades, buscar_id_unidade_por_phone_id



## Aqui jaz uma observação

"""A unidade é pega apenas pelo banco e colocada no cache
não iremos inserir unidades no banco por aqui pois isso será feito manualmente 
após cada contrato no django-admin"""

def inicializar_cache_unidades():
    unidades_map = pegar_unidades()
    last_reload = time.time()

    print(f"📦 Cache carregado: {len(unidades_map)} unidades")

    return unidades_map, last_reload


def atualizar_cache_se_necessario(unidades_map, last_reload, ttl=60):
    if time.time() - last_reload > ttl:
        unidades_map = pegar_unidades()
        last_reload = time.time()
        print("🔄 Cache atualizado")

    return unidades_map, last_reload

class UnidadeNaoEncontrada(Exception):
    pass


def _id_unidade_valido(id_unidade):
    """Aceita apenas IDs inteiros estritamente positivos (evita 0, negativos e tipos estranhos)."""
    if id_unidade is None:
        return False
    try:
        return int(id_unidade) > 0
    except (TypeError, ValueError):
        return False


def _normalizar_phone_number_id(id_phone_unidade):
    """
    phone_number_id no banco é varchar: rejeita None e string vazia / só espaços.
    Devolve a chave normalizada (strip) para cache e query baterem com o dado limpo.
    """
    if id_phone_unidade is None:
        return None
    if isinstance(id_phone_unidade, str):
        s = id_phone_unidade.strip()
        return s if s else None
    return id_phone_unidade


def obter_id_unidade(id_phone_unidade, unidades_map):
    phone_key = _normalizar_phone_number_id(id_phone_unidade)
    if phone_key is None:
        raise UnidadeNaoEncontrada(
            "phone_number_id ausente ou vazio (não é possível resolver a unidade)"
        )

    id_unidade = unidades_map.get(phone_key)

    if not _id_unidade_valido(id_unidade):
        id_unidade = buscar_id_unidade_por_phone_id(phone_key)

        if not _id_unidade_valido(id_unidade):
            raise UnidadeNaoEncontrada(f"Unidade não encontrada: {phone_key}")

        unidades_map[phone_key] = id_unidade

    return int(id_unidade)