"""Resolve linha e canal antes de congelar qualquer entrega externa."""

from core.integrations.fireads.aba_geral import ORIGENS, selecionar_entrega, referencia_registro
from core.integrations.fireads.cliente import ClienteFireAds
from core.integrations.fireads.contrato import ErroFireAds, normalizar
from core.integrations.fireads.prazos import HTTP_SEGUNDOS
from core.repositories.fireads.envios import buscar_configuracao_entrega
from core.integrations.fireads.atribuicao import CHAVE, capturar, vincular


def preparar_destino(dados, conn, cursor):
    if dados.get('origem_fireads') is None:
        return dados
    config = buscar_configuracao_entrega(dados, cursor)
    if config is None:
        raise ErroFireAds('Integração FireAds indisponível para preparar a entrega')
    conn.commit()
    cliente = ClienteFireAds(config[0], segundos=HTTP_SEGUNDOS,
                             timeout_leitura=None, por_operacao=True)
    try:
        resposta = cliente.consultar(config[1])
    except ErroFireAds:
        raise
    except Exception as exc:
        # Exceções HTTP podem incluir URL/corpo; não persistir esses dados.
        raise ErroFireAds(type(exc).__name__) from None
    finally:
        cliente.close()
    if not {'Nome', 'Email', 'WhatsApp', 'Canal', 'Data/Hora', 'Para quem é', 'Observação'} <= set(resposta['headers']):
        raise ErroFireAds('Cabeçalhos de destino incompletos')
    row = selecionar_entrega(resposta['rows'], dados['telefone_cliente'], config[2])
    origem = ORIGENS[normalizar(row.get('Canal'))] if row is not None else 'organico'
    referencia = referencia_registro(row, config[1], config[2])
    destino = {'tipo': 'update', 'referencia': referencia} if row is not None else {'tipo': 'create'}
    contexto = dict(dados['contexto_fireads'], origem=origem)
    contexto[CHAVE] = vincular(capturar(row, config[1], config[2], momento='preparacao_entrega'),
                              dados['id_conversa'], contexto.get(CHAVE))
    return dict(dados, origem_fireads=origem,
                contexto_fireads=contexto,
                entrega_fireads={'destino': destino, 'url': config[0], 'aba': config[1], 'fuso': config[2]})
