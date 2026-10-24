"""Leitura de origem para métricas. Não autoriza nem executa escrita na FireAds."""

from datetime import datetime, timezone

from .aba_geral import CANAIS_MANUAIS, ORIGENS, mais_recente, selecionar_registro
from .atribuicao import CHAVE, CHAVE_VERIFICACAO, capturar, vincular
from .contrato import ErroFireAds, normalizar


def validar_resposta(resposta, aba):
    if (not isinstance(resposta, dict) or resposta.get('aba') != aba
            or not isinstance(resposta.get('headers'), list)
            or not {'WhatsApp', 'Canal', 'Data/Hora'} <= set(resposta['headers'])
            or not isinstance(resposta.get('rows'), list)
            or any(not isinstance(r, dict) or 'WhatsApp' not in r or 'Canal' not in r
                   for r in resposta['rows'])):
        raise ErroFireAds('Resposta de origem incompleta')


def identificar(resposta, *, numero, aba, fuso, id_conversa, id_integracao):
    validar_resposta(resposta, aba)
    row, encontrados = selecionar_registro(resposta['rows'], numero, fuso)
    indefinidos = [r for r in encontrados
                  if normalizar(r.get('Canal')) not in set(ORIGENS) | CANAIS_MANUAIS]
    verificacao = {
        'versao': 1, 'id_conversa': id_conversa, 'status': 'concluida',
        'consultado_em': datetime.now(timezone.utc).isoformat(),
        'id_integracao': id_integracao, 'aba': aba,
    }
    resultado = {CHAVE_VERIFICACAO: verificacao}
    if row is None and indefinidos:
        # Um campo não preenchido não equivale a uma leitura que falhou nem
        # comprova ausência de formulário. Não herdar um canal provisório.
        ultima = mais_recente(indefinidos, fuso)
        verificacao.update(resultado='canal_nao_informado', linha=ultima['_row'])
        return resultado
    atribuicao = vincular(capturar(row, aba, fuso, momento='worker_origem'), id_conversa)
    verificacao.update(resultado='identificada' if row else 'sem_registro_elegivel',
                       linha=row['_row'] if row else None)
    resultado[CHAVE] = atribuicao
    return resultado
