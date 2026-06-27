from core.database.connection_aws import get_conn
from core.integrations.whatsapp.tools.usuarios import (
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


def job_reconciliacao_bloqueios_cliente_unidades_meta():
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
#job_reconciliacao_bloqueios_meta()
