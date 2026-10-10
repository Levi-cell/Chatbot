"""Identificação da linha de destino, sem HTTP ou persistência."""

from .contrato import ErroFireAds, acrescentar_observacoes, destino, normalizar


_ORIGENS_POR_CANAL = {
    "google ads": "google",
    "mkt digital google ads": "google",
    "organico site": "google",
    "meta ads": "meta",
    "mkt digital meta ads facebook instagram": "meta",
    "organico": "organico",
}


def destinatario_perfil(valor):
    """Lê destinatário explícito; faixa etária nunca determina parentesco."""
    informado = destino(valor)
    if informado is not None:
        return informado
    chave = normalizar(valor)
    # Formato usado pelo próprio chatbot nos cadastros e snapshots antigos.
    if chave == "titular" or chave.startswith("titular "):
        return False
    if chave == "dependente" or chave.startswith("dependente "):
        return True
    return None


def numero_linha(row):
    linha = row.get("_row")
    if type(linha) is not int or linha < 2:
        raise ErroFireAds("Linha de destino inválida")
    return linha


def selecionar_destino(encontrados, origem, dependente):
    """Recebe só registros do telefone; prefere canal, destinatário e maior linha."""
    if not encontrados:
        return None
    mesmo_canal = [
        row for row in encontrados
        if _ORIGENS_POR_CANAL.get(normalizar(row.get("Canal"))) == origem
    ]
    # Sem canal compatível, reutiliza a maior linha do telefone em vez de duplicar.
    if not mesmo_canal:
        return max(encontrados, key=numero_linha)
    candidatos = mesmo_canal
    if type(dependente) is bool:
        mesmo_destinatario = [
            row for row in candidatos
            if destinatario_perfil(row.get("Perfil/Faixa")) is dependente
        ]
        if mesmo_destinatario:
            candidatos = mesmo_destinatario
    return max(candidatos, key=numero_linha)


def linhas_com_bloco(encontrados, bloco):
    """Reconcilia uma entrega anterior antes de escolher outra linha do contato."""
    marcador = bloco.split("\n", 1)[0]
    linhas = []
    for row in encontrados:
        observacoes = row.get("Observação")
        if marcador in str(observacoes or ""):
            # Um marcador com conteúdo alterado não comprova a entrega original.
            acrescentar_observacoes(observacoes, bloco)
            linhas.append(numero_linha(row))
    return sorted(set(linhas))
