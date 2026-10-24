"""Uma leitura por integração/aba no ciclo; nenhuma escrita externa."""

import logging
import time
from collections import defaultdict

from core.database.connection_aws import get_conn
from core.integrations.fireads.atribuicao import CHAVE, CHAVE_VERIFICACAO, CANAIS_ANUNCIO
from core.integrations.fireads.cliente import ClienteFireAds
from core.integrations.fireads.origem import identificar, validar_resposta
from core.integrations.fireads.prazos import HTTP_SEGUNDOS
from core.repositories.fireads import origens
from .config import TAMANHO_LOTE

logger = logging.getLogger('worker.origem_fireads')


def executar_ciclo(desde, *, parar=None):
    inicio = time.monotonic()
    resumo = dict(selecionados=0, identificados=0, sem_canal=0, sem_registro_elegivel=0,
                  anuncios_nao_informados=0, falhas=0, descartados=0, consultas=0, ocupado=False)
    conn = get_conn(application_name='worker_origem_fireads', connect_timeout=5)
    # A sessão pertence ao ciclo e não é devolvida a pool: close libera o lock.
    try:
        with conn.cursor() as cursor:
            cursor.execute("SET lock_timeout='3s'; SET statement_timeout='30s'")
            if not origens.adquirir_ciclo(cursor):
                resumo['ocupado'] = True
                return resumo
            teto = origens.limite_ciclo(cursor)
            conn.commit()
            cache, apos = {}, 0
            while not (parar and parar.is_set()):
                candidatos = origens.listar(cursor, desde, apos=apos, ate=teto, limite=TAMANHO_LOTE)
                conn.commit()
                if not candidatos:
                    break
                resumo['selecionados'] += len(candidatos)
                apos = candidatos[-1]['id_conversa']
                grupos = defaultdict(list)
                for item in candidatos:
                    chave = tuple(item[k] for k in ('id_integracao', 'url', 'aba', 'fuso'))
                    grupos[chave].append(item)
                for chave, grupo in grupos.items():
                    if parar and parar.is_set():
                        break
                    atuais = origens.revalidar_grupo(cursor, grupo, desde)
                    conn.commit()
                    resumo['descartados'] += len(grupo) - len(atuais)
                    grupo = atuais
                    if not grupo:
                        continue
                    if chave not in cache:
                        cliente = None
                        try:
                            cliente = ClienteFireAds(chave[1], segundos=HTTP_SEGUNDOS, timeout_leitura=None)
                            resumo['consultas'] += 1
                            resposta = cliente.consultar(chave[2])
                            validar_resposta(resposta, chave[2])
                            cache[chave] = resposta
                        except Exception as erro:
                            cache[chave] = None  # não repetir a mesma falha a cada página
                            logger.warning('origem_consulta_falhou | integracao=%s tipo=%s',
                                           chave[0], type(erro).__name__)
                        finally:
                            if cliente is not None:
                                cliente.close()
                    resposta = cache[chave]
                    for item in grupo:
                        if parar and parar.is_set():
                            break
                        if resposta is None:
                            resumo['falhas'] += 1
                            continue
                        try:
                            resultado = identificar(resposta, numero=item['numero'], aba=item['aba'],
                                fuso=item['fuso'], id_conversa=item['id_conversa'],
                                id_integracao=item['id_integracao'])
                            gravou = origens.concluir(cursor, item, resultado, desde)
                            conn.commit()
                            contador = ('identificados' if CHAVE in resultado else 'sem_canal') if gravou else 'descartados'
                            resumo[contador] += 1
                            if gravou:
                                origem = resultado.get(CHAVE, {})
                                resumo['sem_registro_elegivel'] += int(
                                    resultado[CHAVE_VERIFICACAO]['resultado'] == 'sem_registro_elegivel')
                                resumo['anuncios_nao_informados'] += int(
                                    origem.get('canal') in CANAIS_ANUNCIO and not origem.get('anuncio'))
                        except Exception as erro:
                            conn.rollback()
                            resumo['falhas'] += 1
                            logger.warning('origem_registro_falhou | conversa=%s tipo=%s',
                                           item['id_conversa'], type(erro).__name__)
        return resumo
    finally:
        conn.close()
        logger.info('origem_ciclo | resumo=%s duracao=%.2fs', resumo, time.monotonic() - inicio)
