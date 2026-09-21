import json
import requests


URL_ACESSO = (
    "https://script.google.com/macros/s/"
    "AKfycbxnwj1DsFD6qqihceO2F4b-YRBe3nXwQ70SjWb45LtUVOzrRxMo6nHqKlvNC53EDOLX/exec"
)

ABA = "LEADS GERAL - Feedback"


def limpar_numero(numero: str) -> str:
    """
    Mantém apenas números.
    Exemplo:
    +55 (11) 98505-6130 -> 5511985056130
    """
    return "".join(c for c in str(numero) if c.isdigit())


def gerar_formatos_dashboard(numero: str) -> list[str]:
    """
    Recebe números como:

    5511985056130
    551185056130

    E gera os formatos possíveis encontrados no dashboard.

    Exemplo com 5511985056130:

    (11) 8505-6130
    (11) 98505-6130
    p:+5511985056130
    +5511985056130
    """

    numero = limpar_numero(numero)

    if not numero.startswith("55"):
        raise ValueError(
            f"Número precisa começar com 55. Recebido: {numero}"
        )

    # Remove código do Brasil
    numero_sem_55 = numero[2:]

    if len(numero_sem_55) < 10:
        raise ValueError(
            f"Número brasileiro inválido: {numero}"
        )

    ddd = numero_sem_55[:2]
    telefone = numero_sem_55[2:]

    formatos = []

    # ---------------------------------------------------------
    # CASO 1:
    # telefone possui 9 dígitos
    # Ex.: 985056130
    # ---------------------------------------------------------
    if len(telefone) == 9:

        numero_com_9 = telefone

        # Remove o primeiro 9 para procurar formato antigo
        numero_sem_9 = telefone[1:] if telefone.startswith("9") else telefone

        # (11) 8505-6130
        if len(numero_sem_9) == 8:
            formato_sem_9 = (
                f"({ddd}) "
                f"{numero_sem_9[:4]}-"
                f"{numero_sem_9[4:]}"
            )

            formatos.append(formato_sem_9)

        # (11) 98505-6130
        formato_com_9 = (
            f"({ddd}) "
            f"{numero_com_9[:5]}-"
            f"{numero_com_9[5:]}"
        )

        formatos.append(formato_com_9)

        numero_internacional = f"55{ddd}{numero_com_9}"

        formatos.append(
            f"p:+{numero_internacional}"
        )

        formatos.append(
            f"+{numero_internacional}"
        )

    # ---------------------------------------------------------
    # CASO 2:
    # telefone chegou sem o 9
    # Ex.: 85056130
    # ---------------------------------------------------------
    elif len(telefone) == 8:

        numero_sem_9 = telefone
        numero_com_9 = f"9{telefone}"

        # (11) 8505-6130
        formato_sem_9 = (
            f"({ddd}) "
            f"{numero_sem_9[:4]}-"
            f"{numero_sem_9[4:]}"
        )

        formatos.append(formato_sem_9)

        # (11) 98505-6130
        formato_com_9 = (
            f"({ddd}) "
            f"{numero_com_9[:5]}-"
            f"{numero_com_9[5:]}"
        )

        formatos.append(formato_com_9)

        numero_internacional_com_9 = (
            f"55{ddd}{numero_com_9}"
        )

        formatos.append(
            f"p:+{numero_internacional_com_9}"
        )

        formatos.append(
            f"+{numero_internacional_com_9}"
        )

    else:
        raise ValueError(
            f"Quantidade inesperada de dígitos: {numero}"
        )

    # Remove duplicados mantendo a ordem
    return list(dict.fromkeys(formatos))


def buscar_lead_dashboard(
    url_acesso: str,
    numero_whatsapp: str,
):
    formatos = gerar_formatos_dashboard(
        numero_whatsapp
    )

    print("\nFormatos que serão pesquisados:")

    for formato in formatos:
        print(f"  -> {formato}")

    print("\nConsultando dashboard...\n")

    response = requests.get(
        url_acesso,
        params={
            "sheet": ABA
        },
        timeout=30,
        headers={
            "Accept": "application/json",
            "User-Agent": "Mozilla/5.0",
        },
    )

    response.raise_for_status()

    resposta = response.json()

    dados = resposta.get("data", {})

    rows = dados.get("rows", [])

    print(
        f"Total de registros recebidos: {len(rows)}"
    )

    for lead in rows:

        whatsapp_dashboard = str(
            lead.get("WhatsApp", "")
        ).strip()

        if whatsapp_dashboard in formatos:

            print("\n" + "=" * 70)
            print("LEAD ENCONTRADO")
            print("=" * 70)

            print(
                f"\nFormato encontrado: "
                f"{whatsapp_dashboard}\n"
            )

            print(
                json.dumps(
                    lead,
                    indent=4,
                    ensure_ascii=False,
                    default=str,
                )
            )

            return lead

    print("\n" + "=" * 70)
    print("LEAD NÃO ENCONTRADO")
    print("=" * 70)

    print("\nFormatos pesquisados:")

    for formato in formatos:
        print(f"  {formato}")

    return None


if __name__ == "__main__":

    buscar_lead_dashboard(
        url_acesso=URL_ACESSO,
        numero_whatsapp="5511985056130",
    )