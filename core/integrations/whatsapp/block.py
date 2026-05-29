from pywa import WhatsApp

from core.database.connection_aws import get_conn
from core.repositories.querys import buscar_unidades_para_listagem_bloqueios


ACCESS_TOKEN = "EAATYGW2lhwgBQ4NNpLFVOzkhBCfH7SeWuus3RkF47cq9ldlK7QnU9UHhYZAH9xfWlOnf6p3sbbZAZC179mGXxiS6ZBLRt0EU5bWPrkjLOsjP1mAWVrPR8xadDOnEOWDuyhD0SFhojrOpqcKoo68NzqNdtJMGNqdoKEAZCGP1xdD1EMVn6J2CY86XZCWe30HQZDZD"


def listar_bloqueados_de_cada_unidade(access_token):
    conn = get_conn()
    cursor = conn.cursor()

    unidades = buscar_unidades_para_listagem_bloqueios(cursor)

    for id_unidade, nome_unidade, phone_id_unidade in unidades:
        print(f"unidade {id_unidade} {nome_unidade} phone id ({phone_id_unidade}):")

        wa_unidade = WhatsApp(
            token=access_token,
            phone_id=str(phone_id_unidade),
        )

        bloqueados = wa_unidade.get_blocked_users().all(sleep=0.2)

        if not bloqueados:
            print("   - nenhum numero bloqueado")

        for usuario in bloqueados:
            print(f"   - {usuario.wa_id} numero bloqueado")

        print()

    conn.close()
