"""Atribuição comprovada do atendimento; não infere campanha por código do Funil."""

from copy import deepcopy
from datetime import datetime, timezone

from .aba_geral import ORIGENS, CAMPOS_IDENTIDADE, referencia_registro
from .contrato import normalizar

CHAVE = 'atribuicao_monitoramento'
CHAVE_VERIFICACAO = 'verificacao_origem'
CANAIS_ANUNCIO = frozenset({'meta', 'google'})
CANAIS_FORMULARIO = frozenset({'google', 'meta', 'organico_site', 'chat_fire'})
ROTULOS = {'google': 'Google Ads', 'meta': 'Meta Ads', 'organico_site': 'Orgânico Site',
           'chat_fire': 'Chat Fire', 'organico': '100% orgânico'}


def capturar(row, aba, fuso=None, *, momento='consulta_inicial'):
    canal = ORIGENS.get(normalizar(row.get('Canal'))) if row is not None else 'organico'
    if canal not in ROTULOS:
        raise ValueError('Não atribuir canal desconhecido')
    anuncio = str(row.get('Anuncio') or '').strip() if row is not None and canal in CANAIS_ANUNCIO else ''
    return {'versao': 1, 'status': 'confirmada', 'canal': canal,
            'formulario': canal in CANAIS_FORMULARIO,
            'anuncio': anuncio or None, 'anuncio_chave': ' '.join(anuncio.split()) or None,
            'momento': momento, 'capturado_em': datetime.now(timezone.utc).isoformat(),
            'referencia': referencia_registro(row, aba, fuso)}


def vincular(atribuicao, id_conversa, anterior=None):
    atual = deepcopy(atribuicao)
    atual['id_conversa'] = id_conversa
    if anterior and anterior.get('id_conversa') == id_conversa:
        inicial = anterior.get('inicial') or (anterior if anterior.get('momento') == 'consulta_inicial' else None)
        if inicial and atual.get('momento') != 'consulta_inicial':
            atual['inicial'] = deepcopy(inicial)
        periodica = anterior.get('periodica') or (anterior if anterior.get('momento') == 'worker_origem' else None)
        if periodica and atual.get('momento') != 'worker_origem':
            atual['periodica'] = deepcopy(periodica)
    return atual


def ler(contexto, id_conversa, dados_consulta=None):
    """Só devolve dados próprios do painel. Nunca expõe configuração ou dados pessoais."""
    contexto = contexto if isinstance(contexto, dict) else {}
    salvo = contexto.get(CHAVE)
    if isinstance(salvo, dict):
        if (salvo.get('versao') != 1 or salvo.get('status') != 'confirmada'
                or salvo.get('id_conversa') != id_conversa or salvo.get('canal') not in ROTULOS):
            return None
        canal, anuncio = salvo['canal'], salvo.get('anuncio')
    else:
        verificacao = contexto.get(CHAVE_VERIFICACAO)
        if (isinstance(verificacao, dict) and verificacao.get('versao') == 1
                and verificacao.get('id_conversa') == id_conversa
                and verificacao.get('status') == 'concluida'
                and contexto.get('canal_confirmado_entrega') is not True):
            return None
        # Compatibilidade somente com evidência gravada, nunca pelo canal provisório.
        referencia = contexto.get('referencia')
        if contexto.get('canal_confirmado_entrega') is True:
            destino = contexto.get('referencia_entrega') or {}
            referencia = destino.get('referencia')
            if destino.get('tipo') == 'create':
                return {'canal': 'organico', 'rotulo': ROTULOS['organico'], 'fireads': False, 'anuncio': None}
        campos = (referencia or {}).get('campos') or {}
        canal = ORIGENS.get(normalizar(campos.get('Canal')))
        if canal not in ROTULOS:
            decisao = (dados_consulta or {}).get('decisao') or {}
            if (decisao.get('resultado') == 'ausente'
                    and decisao.get('motivo') in {'telefone_ausente', 'canal_nao_elegivel', 'sem_registro_elegivel'}):
                canal = 'organico'
            else:
                return None
        anuncio = None
        # O anúncio histórico vem exclusivamente da mesma linha selecionada e salva.
        rows = ((dados_consulta or {}).get('fontes') or {}).get('geral') or []
        iguais = [r for r in rows if isinstance(r, dict) and set(campos) == set(CAMPOS_IDENTIDADE)
                  and all(r.get(c) == campos[c] for c in CAMPOS_IDENTIDADE)]
        linha = [r for r in iguais if r.get('_row') == (referencia or {}).get('linha')]
        if canal in CANAIS_ANUNCIO and len(linha or iguais) == 1:
            anuncio = (linha or iguais)[0].get('Anuncio')
    anuncio = ' '.join(str(anuncio or '').split()) if canal in CANAIS_ANUNCIO else ''
    return {'canal': canal, 'rotulo': ROTULOS[canal], 'fireads': canal in CANAIS_FORMULARIO,
            'anuncio': anuncio or None}
