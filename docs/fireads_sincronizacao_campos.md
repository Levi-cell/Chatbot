# Plano prático — sincronização dos campos do chatbot com a FireAds

**Status: reservado para aplicação futura; não está ativo no projeto.**

Isolado em 21/10/2026 a pedido do usuário. O código proposto foi preservado
integralmente nos passos abaixo e retirado do caminho de execução. O projeto
atual conserva a entrega anterior: atualiza somente Observação em registros
existentes, preserva as outras colunas e mantém a seleção anterior de destino.
Coleta parcial, Chat Fire, turno e interpretação de parentescos continuam ativos.

**Não aplicar nem implantar este plano antes da liberação das colunas pela
FireAds descrita no último passo.** O último passo está ao final por organização
do documento, mas a confirmação externa é pré-requisito para ativar a mudança.
Nenhuma alteração no Apps Script, banco de produção ou VM foi feita ao isolar o plano.

Base de referência: HEAD `1501367116e2f39a7425b9217866ccfe2342a21a` mais as melhorias locais de coleta parcial,
Chat Fire, turno e prioridades de destinatário já presentes em 21/10/2026.
Os arquivos abaixo são completos, não patches nem trechos. Se o projeto evoluir,
comparar a base antes de substituí-los para preservar correções posteriores.
A versão 4 citada é do JSON interno de entrega, não o número da release do chatbot.

Atualização de apresentação em 21/10/2026: o projeto atual já monta observações
compactas em `core/integrations/funil/oportunidades.py` e as delimita com
`bloco_observacoes(..., versao=3)`. Esse formato de texto é independente da versão
4 do JSON proposto aqui. Manter o cabeçalho em maiúsculas, dados consecutivos e
pergunta/resposta na mesma linha, sem restaurar os títulos ou parágrafos removidos.
Os passos abaixo reutilizam o texto compartilhado já congelado, preservam as
observações anteriores e não reformatam snapshots históricos. O teste do passo 5
usa o bloco compacto. Os marcadores continuam exatamente `[INICIO CHATBOT:…]` e
`[FIM CHATBOT:…]`, sem acento em INICIO, necessários à reconciliação.
Essa alteração visual não libera a sincronização de campos nem exige ampliar as
colunas editáveis; o último passo continua sendo condição para o plano futuro.

## Escopo e contrato proposto

## Atendimento e seleção


A primeira mensagem fornece os valores prioritários. A consulta completa apenas
campos desconhecidos, sem apagar os conhecidos mesmo quando nenhuma inscrição
combina. O que continuar faltando é perguntado na etapa habitual. Correções
explícitas aceitas no atendimento prevalecem sobre os valores iniciais.

O telefone é o remetente WhatsApp. Na entrega, reutilizar a referência já vinculada.
Sem referência, procurar apenas canais elegíveis (Meta Ads, Google Ads, Orgânico
Site e Chat Fire): nome/e-mail compatíveis, relação exata, equivalência lógica
titular/dependente e demais compatíveis, com o turno no último recurso sem link.
Dentro de cada prioridade, data/hora mais recente e depois maior linha.

Se nenhuma inscrição combinar, selecionar a mais recente do telefone entre os
canais elegíveis e corrigir seus campos. A divergência não cria outro cadastro.
Sem inscrição elegível, manter a criação, com a proteção existente de e-mail em
outro telefone. Indicação/Lead Franqueador não se tornam alvos dessa seleção.

## Conteúdo gravado

| Campo | Atualização de uma inscrição existente |
| --- | --- |
| Nome | Nome informado na mensagem/atendimento, preservando o nome completo disponível e removendo o sufixo de biografia após `\|`. |
| Email | E-mail aceito da mensagem/atendimento. |
| Para quem é | Relação explícita informada ou titular/dependente confirmado no atendimento. |
| Período preferido | Manhã, Tarde, Noite ou Sábado aceito da mensagem/atendimento, somente em unidade sem link. |
| Observação | Acrescentar o mesmo bloco enviado ao Funil, abaixo do conteúdo existente. |

Campo ausente, conflitante ou inválido não é enviado para apagar o cadastro.
Campos apenas importados da FireAds não são regravados em updates. Na criação,
os dados aceitos de todas as fontes podem preencher o novo cadastro. Canal,
telefone, data de inscrição, Perfil/Faixa e demais colunas existentes são preservados.

## Recuperação

O snapshot versão 4 congela os valores antes da primeira tentativa e o destino
antes do POST. Mesmo que o cadastro local mude depois, o retry usa esse snapshot.
Uma queda durante a gravação de colunas pode deixar apenas parte aplicada:
reconhecer a inscrição pelos campos que não escrevemos e reaplicar os mesmos
valores. Se a linha mudou de posição, reencontrar a inscrição antes de enviar.
Se ela desapareceu ou ficou indistinguível, manter pendente para conferência.
Nunca escrever em outro telefone porque ocupou o antigo número da linha.

O marcador técnico evita repetir observações, mas não basta para confirmar os
quatro campos. Se o bloco existir e os campos divergirem, reaplicar os campos
mantendo a observação. Se tudo estiver gravado, confirmar sem novo POST. O recibo
HTTP precisa confirmar todas as colunas solicitadas. Append confirmado pelo
bloco não é repetido; diferenças restantes são reparadas por update.

Não há atomicidade entre nosso GET e POST no Web App atual: evitar reordenar,
excluir ou editar inscrições durante o envio. Nosso lock serializa os workers
do chatbot, mas não os operadores da planilha.

## Banco e critérios de validação da futura aplicação

Esta sincronização não acrescenta migração SQL. Reutiliza os JSONs existentes.
As migrações anteriores de coleta parcial, Chat Fire e turno continuam necessárias;
para uma instalação ainda sem elas, usar `20261021_coleta_chat_fire_completa.sql`
conforme o procedimento desse deploy, com os serviços parados.

Os seis arquivos completos deste plano foram preservados da implementação que
passou por 169 testes unitários e 17 testes de integração locais, com serviços
externos simulados. Esse resultado histórico não valida a implantação publicada
na FireAds nem substitui nova verificação quando o plano for aplicado.

Após aplicar os arquivos em ambiente local, executar os testes abaixo. Integração
exige `FIREADS_TEST_DSN` apontando para `test_chatbot_fireads` em loopback, sem
schema chatbot preexistente; nunca apontar a suíte ao banco da aplicação.

```bash
python -B -m unittest tests.unit.test_fireads_sincronizacao_coleta tests.unit.test_fireads tests.unit.test_coleta_abertura tests.unit.test_fireads_prioridade_destinatario tests.unit.test_chat_fire_turno tests.unit.test_destinatario_abertura tests.unit.test_fireads_aba_geral tests.unit.test_fireads_destino_dashboard tests.unit.test_fireads_telefones tests.unit.test_fireads_espera -q
python -B -m unittest tests.integration.test_coleta_abertura_postgres -q
```

Somente depois da liberação externa, validar com um registro de teste autorizado
na aba geral: atualizar os campos, preservar as outras colunas e observações,
e confirmar o recibo de todas as colunas. Não disparar testes sobre leads reais.
A limitação entre GET e POST continua: coordenar com a equipe para não mover ou
excluir inscrições durante o envio. Antes de ativar, alinhar a documentação de
regras/arquitetura e deploy a este contrato; hoje ela descreve a entrega anterior.

## Arquivos deste plano

| Passo | Operação | Arquivo |
| --- | --- | --- |
| 1 | Criar | `core/integrations/fireads/sincronizacao_coleta.py` |
| 2 | Alterar | `core/integrations/fireads/cliente.py` |
| 3 | Alterar | `core/repositories/fireads/envios.py` |
| 4 | Alterar | `workers/worker_funil/fireads.py` |
| 5 | Criar | `tests/unit/test_fireads_sincronizacao_coleta.py` |
| 6 | Alterar | `tests/integration/test_coleta_abertura_postgres.py` |
| 7 | Solicitar liberação externa | Configuração EDITABLE_COLUMNS do Web App FireAds |

## Passo 1 — criar `core/integrations/fireads/sincronizacao_coleta.py`

Seleciona a inscrição, prepara os quatro campos e reconhece escritas parciais/completas.

Conteúdo integral do arquivo (UTF-8; SHA-256 com finais LF: `017dfe8876d7903397aed2a5c530c1d2d25c1b5422b071075b57fa5fe18cb27d`):

```python
"""Entrega dos dados coletados, com destino e valores congelados (contrato 4)."""

from copy import deepcopy

from core.integrations.fireads.aba_geral import (
    CAMPOS_IDENTIDADE, ORIGENS, mais_recente, numero_linha, referencia_registro,
)
from core.integrations.fireads.coleta_abertura import selecionar_para_complementacao
from core.integrations.fireads.contrato import (
    CANAIS, ErroFireAds, acrescentar_observacoes, localizar, normalizar, telefone,
)
from core.integrations.fireads.destino_dashboard import linhas_com_bloco

COLUNAS = {'nome': 'Nome', 'email': 'Email', 'destinatario': 'Para quem é',
           'turno': 'Período preferido'}
TURNOS = {'manha': 'Manhã', 'tarde': 'Tarde', 'noite': 'Noite', 'sabado': 'Sábado'}


def valor_planilha(tipo, campo):
    if tipo == 'nome':
        # A saudação usa o primeiro nome; a planilha conserva o nome informado.
        return str(campo.get('bruto') or campo['valor']).split('|', 1)[0].strip()
    if tipo == 'destinatario':
        return campo['valor']['texto']
    if tipo == 'turno':
        return TURNOS[campo['valor']]
    return campo['valor']


def dados_sincronizacao(coleta, *, com_link=False):
    """Correções aceitas no atendimento prevalecem sobre a abertura original."""
    campos = deepcopy(coleta['campos'])
    turno_atendimento = (campos.get('turno') or {}).get('fonte') == 'atendimento'
    coletar_turno = bool((coleta.get('coletar_turno') or turno_atendimento) and not com_link)
    if not coletar_turno:
        campos.pop('turno', None)
    alteracoes = {}
    for tipo, coluna in COLUNAS.items():
        c = campos.get(tipo) or {}
        if c.get('status') == 'aceito' and c.get('fonte') in {'mensagem', 'atendimento'}:
            valor = valor_planilha(tipo, c)
            if valor:
                alteracoes[coluna] = valor
    return {'identidade_coleta': campos, 'campos_dashboard': alteracoes,
            'coletar_turno': coletar_turno}


def _por_telefone(rows, snapshot):
    return localizar(rows, snapshot['telefone'], 'WhatsApp', incluir_equivalentes=True)


def _email_cruzado(rows, snapshot):
    encontrados = _por_telefone(rows, snapshot)
    email = str(snapshot.get('email') or '').strip().casefold()
    if email and any(r not in encontrados and str(r.get('Email') or '').strip().casefold() == email
                     for r in rows):
        raise ErroFireAds('Email já presente em outro telefone; conferir identidade')


def _registro_marcado(rows, snapshot, bloco):
    encontrados = _por_telefone(rows, snapshot)
    linhas = linhas_com_bloco(encontrados, bloco)
    if len(linhas) > 1:
        raise ErroFireAds('Bloco da conversa presente em mais de um registro')
    return next((r for r in encontrados if numero_linha(r) in linhas), None)


def _relocalizar(rows, referencia, snapshot, marcado=None):
    """Reconhece a mesma inscrição antes, durante e depois da nossa escrita.

    Data, canal, telefone e campos não escritos continuam identificando o alvo.
    O número da linha sozinho nunca autoriza alterar outro contato.
    """
    if referencia.get('aba') != snapshot['aba']:
        raise ErroFireAds('Aba do registro selecionado diverge do envio')
    antes = referencia.get('campos')
    if not isinstance(antes, dict) or set(antes) != set(CAMPOS_IDENTIDADE):
        raise ErroFireAds('Referência do formulário incompleta')
    updates = snapshot['campos_dashboard']
    fixos = set(CAMPOS_IDENTIDADE) - set(updates)
    candidatos = [r for r in _por_telefone(rows, snapshot)
                  if all(r.get(c) == antes[c] for c in fixos)]
    if marcado is not None:
        if marcado not in candidatos:
            raise ErroFireAds('Bloco da conversa não pertence ao destino congelado')
        return marcado
    # Uma escrita pode ter sido aplicada só em parte antes da queda do Web App.
    reconhecidos = [r for r in candidatos if all(
        r.get(c) == antes[c] or (c in updates and r.get(c) == updates[c])
        for c in CAMPOS_IDENTIDADE)]
    if reconhecidos:
        candidatos = reconhecidos
    if len(candidatos) == 1:
        return candidatos[0]
    original = [r for r in candidatos if numero_linha(r) == referencia.get('linha')]
    if len(original) == 1:
        return original[0]
    raise ErroFireAds('Registro selecionado ausente ou deslocado sem identidade única')


def escolher(rows, snapshot):
    if snapshot.get('referencia') is not None:
        row = _relocalizar(rows, snapshot['referencia'], snapshot)
    else:
        elegiveis = [r for r in _por_telefone(rows, snapshot)
                    if normalizar(r.get('Canal')) in ORIGENS]
        estado = {'campos': snapshot['identidade_coleta'],
                  'coletar_turno': snapshot['coletar_turno']}
        row = selecionar_para_complementacao(elegiveis, estado, snapshot.get('fuso'))
        # Divergência não descarta os dados do chat nem cria outra inscrição.
        if row is None:
            row = mais_recente(elegiveis, snapshot.get('fuso'))
    if row is not None:
        return {'tipo': 'update', 'referencia': referencia_registro(row, snapshot['aba'], snapshot.get('fuso'))}
    _email_cruzado(rows, snapshot)
    return {'tipo': 'create'}


def _atualizar(row, snapshot, bloco):
    if 'Observação' not in row or not set(snapshot['campos_dashboard']) <= set(row):
        raise ErroFireAds('Colunas de sincronização ausentes; não sobrescrever')
    obs, mudou = acrescentar_observacoes(row['Observação'], bloco)
    updates = snapshot['campos_dashboard']
    if not mudou and all(row[c] == v for c, v in updates.items()):
        return None
    # Observação por último: um erro anterior não pode atestar entrega completa.
    return {'row': numero_linha(row), 'observacoes': obs, 'campos': dict(updates)}


def preparar(rows, snapshot, bloco):
    acrescentar_observacoes(None, bloco)
    alvo = snapshot.get('destino')
    if not alvo:
        raise ErroFireAds('Destino da coleta ainda não foi persistido')
    marcado = _registro_marcado(rows, snapshot, bloco)
    if alvo['tipo'] == 'update':
        row = _relocalizar(rows, alvo['referencia'], snapshot, marcado)
        return _atualizar(row, snapshot, bloco)
    if alvo['tipo'] != 'create':
        raise ErroFireAds('Tipo de destino desconhecido')
    if marcado is not None:
        # Append já aplicado: corrigir eventual escrita parcial, nunca duplicar.
        return _atualizar(marcado, snapshot, bloco)
    _email_cruzado(rows, snapshot)
    dados = {'Nome': snapshot['nome'], 'Email': snapshot['email'],
             'WhatsApp': telefone(snapshot['telefone']), 'Perfil/Faixa': snapshot['perfil'],
             'Para quem é': snapshot['para_quem'], 'Canal': CANAIS[snapshot['origem']][0]}
    for tipo, coluna in COLUNAS.items():
        c = snapshot['identidade_coleta'].get(tipo) or {}
        if c.get('status') == 'aceito':
            dados[coluna] = valor_planilha(tipo, c)
    dados['Observação'] = bloco
    return {'dados': dados}
```

## Passo 2 — alterar `core/integrations/fireads/cliente.py`

Envia as colunas permitidas e exige confirmação de todas no recibo.

Conteúdo integral do arquivo (UTF-8; SHA-256 com finais LF: `d79603f7f969b26e182fb0d36d624e544286aed03750b93cfc11b1ca3bdd838c`):

```python
"""GET e POST limitados ao Web App; nenhuma escrita durante importação."""

import time
from urllib.parse import urlparse
import requests
from .contrato import ErroFireAds


class PrazoConsultaFireAdsEsgotado(ErroFireAds):
    """O orçamento total da leitura terminou, inclusive seus redirecionamentos."""


def validar_url(url, *, resposta=False):
    p = urlparse(str(url))
    host = "script.googleusercontent.com" if resposta else "script.google.com"
    if (
        p.scheme != "https"
        or p.hostname != host
        or p.username
        or p.password
        or p.port not in (None, 443)
        or (
            not resposta
            and (not p.path.startswith("/macros/s/") or not p.path.endswith("/exec"))
        )
    ):
        raise ErroFireAds("URL FireAds inválida: usar Web App /exec HTTPS")
    return url


class ClienteFireAds:
    def __init__(self, url, *, segundos=25, timeout_leitura=8, session=None):
        """Leitura=None usa o prazo restante; padrões das escritas são preservados."""
        self.url = validar_url(url)
        self.deadline = None if segundos is None else time.monotonic() + segundos
        self.timeout_leitura = timeout_leitura
        self.session = session or requests.Session()
        self.session.headers.update({"Accept": "application/json"})

    def close(self):
        self.session.close()

    def _request(self, method, url, **kwargs):
        timeout = None
        if self.deadline is not None:
            restante = self.deadline - time.monotonic()
            if restante <= 0:
                raise PrazoConsultaFireAdsEsgotado("Orçamento de consulta FireAds esgotado")
            leitura = (
                restante if self.timeout_leitura is None
                else min(self.timeout_leitura, restante)
            )
            timeout = (min(4, restante), leitura)
        # O prazo da abertura é compartilhado entre abas e redirects.
        # Escritas e redirects continuam sem repetição automática de POST.
        response = self.session.request(
            method,
            url,
            timeout=timeout,
            allow_redirects=False,
            **kwargs
        )
        if response.status_code in (301, 302, 303):
            alvo = response.headers.get("Location", "")
            validar_url(alvo, resposta=True)
            response = self._request("GET", alvo)
        response.raise_for_status()
        if self.deadline is not None and time.monotonic() > self.deadline:
            raise PrazoConsultaFireAdsEsgotado("Resposta FireAds após o prazo")
        return response

    def _json(self, response):
        try:
            body = response.json()
        except ValueError as exc:
            raise ErroFireAds("Resposta FireAds não é JSON") from exc
        if not isinstance(body, dict) or body.get("success") is not True:
            if isinstance(body, dict) and str(body.get('error') or '').startswith('Coluna não editável:'):
                raise ErroFireAds('Web App FireAds não autoriza as colunas; atualizar EDITABLE_COLUMNS')
            raise ErroFireAds("FireAds recusou a operação")
        return body

    def consultar(self, aba):
        body = self._json(
            self._request("GET", self.url, params={"sheet": aba, "abas": "0"})
        )
        data = body.get("data")
        if (
            not isinstance(data, dict)
            or data.get("aba") != aba
            or not isinstance(data.get("headers"), list)
            or not isinstance(data.get("rows"), list)
            or any(not isinstance(r, dict) for r in data["rows"])
        ):
            raise ErroFireAds("Consulta incompleta ou aba divergente")
        return data

    def enviar(self, aba, *, dados=None, row=None, observacoes=None, campos=None):
        if row is None:
            if campos:
                raise ErroFireAds("Campos de atualização sem linha de destino")
            payload = {"action": "append", "sheet": aba, "rows": [dados]}
        else:
            campos = dict(campos or {})
            if (not set(campos) <= {"Nome", "Email", "Para quem é", "Período preferido"}
                    or any(not isinstance(v, str) or not v.strip() for v in campos.values())):
                raise ErroFireAds("Campos de sincronização inválidos")
            payload = {
                "sheet": aba,
                "row": int(row),
                "updates": {**campos, "Observação": observacoes},
            }
        result = self._json(self._request("POST", self.url, json=payload))
        if result.get("aba") != aba:
            raise ErroFireAds("Recibo de outra aba")
        if row is None:
            if result.get("inserted") != 1:
                raise ErroFireAds("Cadastro sem confirmação de uma linha")
        elif (result.get("row") != row or not isinstance(result.get("updated"), list)
              or not set(payload['updates']) <= set(result['updated'])):
            raise ErroFireAds("Update sem confirmação da linha/coluna")
        return result
```

## Passo 3 — alterar `core/repositories/fireads/envios.py`

Congela os dados da conversa no snapshot de entrega versão 4.

Conteúdo integral do arquivo (UTF-8; SHA-256 com finais LF: `36decb6fafd46d992086423bb57c1ea185741751fa55d342ab192fd81f67b24e`):

```python
"""Fila independente do dashboard e retrato do conteúdo aceito para o Funil."""

from psycopg.types.json import Jsonb
from core.integrations.fireads.contrato import CANAIS


def congelar(dados, payload, integracao_funil, cursor):
    origem = dados.get("origem_fireads")
    if origem is None:
        return (
            payload,
            integracao_funil["codigo_canal_venda"],
            integracao_funil["link_api_carrossel"],
        )
    # No retry, a entrega já registrada é a fonte de verdade. Não reconstruir
    # conteúdo/configuração a partir de cadastros que possam ter mudado depois.
    cursor.execute(
        "SELECT snapshot FROM chatbot.envios_dash WHERE id_conversa=%s",
        (dados["id_conversa"],),
    )
    existente = cursor.fetchone()
    if existente is not None:
        salvo = existente[0]
        return salvo["payload_funil"], salvo["canal"], salvo["url_funil"]
    canal = CANAIS[origem][1]
    estado = dados["contexto_fireads"]
    cursor.execute(
        """SELECT id_integracao_fireads, url_dashbord, aba_destino, fuso_formularios
        FROM chatbot.integracao_fireads WHERE id_integracao_fireads=%s AND id_unidade=%s""",
        (estado["id_integracao"], dados["id_unidade"]),
    )
    config = cursor.fetchone()
    if config is None:
        raise ValueError("Integração histórica FireAds não encontrada")
    oportunidade = payload["oportunidades"][0]
    obs = next(
        c["valor"]
        for c in oportunidade["personalizados"]
        if c["titulo"] == "Observações"
    )
    snapshot = {
        "versao": 2,
        "payload_funil": payload,
        "canal": canal,
        "url_funil": integracao_funil["link_api_carrossel"],
        "url": config[1],
        "aba": config[2],
        "fuso": config[3],
        "observacoes": obs,
        "telefone": dados["telefone_cliente"],
        "email": oportunidade["contato"]["email"],
        "nome": dados["nome_cliente"],
        "origem": origem,
        "referencia": estado.get("referencia"),
        "primeiro_atendimento": dados["primeiro_atendimento"],
        "status_dependente": dados["status_dependente"],
        "perfil": (
            f"Dependente: {dados['nome_dependente']} ({dados['idade_dependente']} anos)"
            if dados["status_dependente"]
            else f"Titular ({dados['idade_cliente']} anos)"
        ),
    }
    if dados.get('contexto_coleta'):
        from core.integrations.fireads.sincronizacao_coleta import dados_sincronizacao
        coleta = dados['contexto_coleta']
        sincronizacao = dados_sincronizacao(coleta, com_link=bool(dados.get('link_agendamento')))
        identidade = sincronizacao['identidade_coleta']
        alvo = identidade['destinatario']
        snapshot.update(versao=4, rota_formulario_chat=coleta['rota_formulario_chat'],
                        **sincronizacao, destino=None,
                        para_quem=alvo['valor']['texto'] if alvo['status']=='aceito' else (
                            'Para dependente' if dados['status_dependente'] else 'Para mim'))
    cursor.execute(
        """INSERT INTO chatbot.envios_dash
        (id_conversa,id_unidade,id_integracao_fireads,snapshot) VALUES (%s,%s,%s,%s)
        ON CONFLICT (id_conversa) DO NOTHING""",
        (dados["id_conversa"], dados["id_unidade"], config[0], Jsonb(snapshot)),
    )
    cursor.execute(
        """UPDATE chatbot.conversa SET lead_no_dash=FALSE
        WHERE id_conversa=%s AND lead_no_dash IS NULL""",
        (dados["id_conversa"],),
    )
    cursor.execute(
        "SELECT snapshot FROM chatbot.envios_dash WHERE id_conversa=%s",
        (dados["id_conversa"],),
    )
    salvo = cursor.fetchone()[0]
    return salvo["payload_funil"], salvo["canal"], salvo["url_funil"]


def bloquear_contato(chave, cursor):
    """Reserva de sessão: protege o contato inclusive durante chamadas HTTP."""
    cursor.execute("SELECT pg_try_advisory_lock(%s)", (chave,))
    return cursor.fetchone()[0]


def liberar_contato(chave, cursor):
    cursor.execute("SELECT pg_advisory_unlock(%s)", (chave,))


def reservar(cursor):
    cursor.execute(
        """WITH proximo AS (
        SELECT d.id_envio_dash FROM chatbot.envios_dash d
        JOIN chatbot.conversa c ON c.id_conversa=d.id_conversa
        JOIN chatbot.integracao_fireads i USING (id_integracao_fireads)
        JOIN chatbot.integracao_funil_unidade f ON f.id_unidade=d.id_unidade
        JOIN chatbot.unidade u ON u.id_unidade=d.id_unidade
        WHERE c.lead_no_funil IS TRUE AND i.integracao_ativa AND f.integracao_ativa AND f.widget_ativo
          AND u.status_pagamento IS TRUE
          AND ((d.status='pending' AND d.next_attempt_at <= clock_timestamp())
            OR (d.status='processing' AND d.processing_started_at < clock_timestamp()-INTERVAL '3 minutes'))
        ORDER BY d.attempt_count,d.id_envio_dash FOR UPDATE OF d SKIP LOCKED LIMIT 1
    ) UPDATE chatbot.envios_dash d SET status='processing',attempt_count=attempt_count+1,
        processing_started_at=clock_timestamp(),atualizado_em=clock_timestamp()
      FROM proximo p WHERE d.id_envio_dash=p.id_envio_dash
      RETURNING d.id_envio_dash,d.id_conversa,d.id_integracao_fireads,d.attempt_count,d.snapshot"""
    )
    row = cursor.fetchone()
    return (
        dict(zip(("id", "conversa", "integracao", "tentativa", "snapshot"), row))
        if row
        else None
    )


def conferir_posse(envio, cursor):
    cursor.execute(
        """SELECT 1 FROM chatbot.envios_dash d
        JOIN chatbot.integracao_fireads i USING (id_integracao_fireads)
        JOIN chatbot.integracao_funil_unidade f ON f.id_unidade=d.id_unidade
        JOIN chatbot.unidade u ON u.id_unidade=d.id_unidade
        WHERE d.id_envio_dash=%s AND d.status='processing' AND d.attempt_count=%s
          AND u.status_pagamento IS TRUE
          AND d.processing_started_at > clock_timestamp()-INTERVAL '3 minutes'
          AND i.integracao_ativa AND f.integracao_ativa AND f.widget_ativo
          AND i.url_dashbord=d.snapshot->>'url' AND i.aba_destino=d.snapshot->>'aba'
        FOR UPDATE OF d""",
        (envio["id"], envio["tentativa"]),
    )
    if cursor.fetchone() is None:
        raise ValueError("Reserva/configuração FireAds mudou; não escrever")


def concluir(envio, recibo, cursor):
    cursor.execute(
        """UPDATE chatbot.envios_dash SET status='sent',enviado_em=clock_timestamp(),
        processing_started_at=NULL,ultimo_erro=NULL,recibo=%s,atualizado_em=clock_timestamp()
        WHERE id_envio_dash=%s AND status='processing' AND attempt_count=%s RETURNING id_conversa""",
        (Jsonb(recibo), envio["id"], envio["tentativa"]),
    )
    row = cursor.fetchone()
    if row is None:
        raise ValueError("Reserva FireAds perdida após envio")
    cursor.execute(
        "UPDATE chatbot.conversa SET lead_no_dash=TRUE WHERE id_conversa=%s", (row[0],)
    )


def reagendar(envio, erro, cursor):
    cursor.execute(
        """UPDATE chatbot.envios_dash SET status='pending',
        next_attempt_at=clock_timestamp()+INTERVAL '30 minutes',processing_started_at=NULL,
        ultimo_erro=%s,atualizado_em=clock_timestamp()
        WHERE id_envio_dash=%s AND status='processing' AND attempt_count=%s""",
        (type(erro).__name__ + ": " + str(erro)[:300], envio["id"], envio["tentativa"]),
    )
```

## Passo 4 — alterar `workers/worker_funil/fireads.py`

Executa o contrato 4 e preserva os contratos das entregas antigas.

Conteúdo integral do arquivo (UTF-8; SHA-256 com finais LF: `2b3b7427ef81e6f8eeb1cbea84270a429b148b18999dfc1a188d2dd3b92965ad`):

```python
"""Entrega independente, depois do Funil. Reconsulta antes de qualquer escrita."""

import hashlib
import logging
import psycopg
from core.integrations.fireads.cliente import ClienteFireAds
from core.integrations.fireads.contrato import (
    CANAIS,
    ErroFireAds,
    telefone,
    identidade_telefone,
    localizar,
    bloco_observacoes,
    acrescentar_observacoes,
)
from core.repositories.fireads.envios import (
    reservar,
    conferir_posse,
    concluir,
    reagendar,
    bloquear_contato,
    liberar_contato,
)
from core.integrations.fireads.destino_dashboard import (
    destinatario_perfil,
    linhas_com_bloco,
    numero_linha,
    selecionar_destino,
    selecionar_destino_atual,
)

logger = logging.getLogger("worker.funil.fireads")


def preparar_escrita(rows, snapshot, bloco):
    if snapshot.get('versao') == 4:
        from core.integrations.fireads.sincronizacao_coleta import preparar
        return preparar(rows, snapshot, bloco)
    if snapshot.get('versao') == 3:
        from core.integrations.fireads.destino_coleta import preparar
        return preparar(rows, snapshot, bloco)
    acrescentar_observacoes(None, bloco)  # Mesmo limite no append e no update.
    encontrados = localizar(
        rows, snapshot["telefone"], "WhatsApp", incluir_equivalentes=True
    )
    if linhas_com_bloco(encontrados, bloco):
        return None
    if snapshot.get("versao") == 2 and (encontrados or snapshot.get("referencia") is not None):
        row = selecionar_destino_atual(encontrados, snapshot)
        if "Observação" not in row:
            raise ErroFireAds("Observação ausente na leitura do registro; não sobrescrever")
        observacoes, mudou = acrescentar_observacoes(row.get("Observação"), bloco)
        return {"row": numero_linha(row), "observacoes": observacoes} if mudou else None
    if encontrados:
        dependente = snapshot.get("status_dependente")
        if type(dependente) is not bool:
            # Envios pendentes anteriores à correção já guardam o perfil textual.
            dependente = destinatario_perfil(snapshot.get("perfil"))
        row = selecionar_destino(encontrados, snapshot["origem"], dependente)
        if "Observação" not in row:
            raise ErroFireAds(
                "Observação ausente na leitura do registro; não sobrescrever"
            )
        linha = numero_linha(row)
        # O telefone identifica o contato; e-mail e demais campos ficam intactos.
        observacoes, mudou = acrescentar_observacoes(row.get("Observação"), bloco)
        return {"row": linha, "observacoes": observacoes} if mudou else None
    # Um e-mail já presente com outro telefone não é identidade suficiente para
    # alterar outra pessoa nem para criar silenciosamente um possível duplicado.
    email = str(snapshot.get("email") or "").strip().casefold()
    if email and any(
        str(r.get("Email") or "").strip().casefold() == email for r in rows
    ):
        raise ErroFireAds("Email já presente em outro telefone; conferir identidade")
    return {
        "dados": {
            "Nome": snapshot["nome"],
            "Email": snapshot["email"],
            "WhatsApp": telefone(snapshot["telefone"]),
            "Perfil/Faixa": snapshot["perfil"],
            "Canal": CANAIS[snapshot["origem"]][0],
            "Observação": bloco,
        }
    }


def processar(envio, conn, cursor):
    snapshot = envio["snapshot"]
    # Lock de sessão (não de transação): serializa nossos envios ao mesmo contato,
    # sem manter transação aberta durante HTTP. Outros sistemas não usam este lock.
    identidade = f"fireads:{envio['integracao']}:{identidade_telefone(snapshot['telefone'])}"
    chave = int.from_bytes(
        hashlib.sha256(identidade.encode()).digest()[:8], "big", signed=True
    )
    bloqueado = False
    cliente = None
    try:
        bloqueado = bloquear_contato(chave, cursor)
        if not bloqueado:
            raise ErroFireAds("Outro envio deste contato está em andamento")
        conferir_posse(envio, cursor)
        conn.commit()
        cliente = ClienteFireAds(snapshot["url"], segundos=40)
        dados = cliente.consultar(snapshot["aba"])
        if not {"Nome", "Email", "WhatsApp", "Observação"} <= set(dados["headers"]):
            raise ErroFireAds("Cabeçalhos de destino incompletos")
        if snapshot.get('versao') in {3, 4} and not {'Para quem é', 'Canal', 'Data/Hora'} <= set(dados['headers']):
            raise ErroFireAds('Cabeçalhos da coleta incompletos')
        if snapshot.get('versao') == 4:
            exigidos = set(snapshot['campos_dashboard'])
            turno = snapshot['identidade_coleta'].get('turno') or {}
            if turno.get('status') == 'aceito':
                exigidos.add('Período preferido')
            if not exigidos <= set(dados['headers']):
                raise ErroFireAds('Cabeçalhos de sincronização incompletos')
        if snapshot.get("versao") in {2, 3, 4}:
            bloco = snapshot["observacoes"]
        elif "versao" not in snapshot:
            bloco = bloco_observacoes(
                envio["integracao"], envio["conversa"], snapshot["observacoes"]
            )
        else:
            raise ErroFireAds("Versão de envio desconhecida")
        if snapshot.get('versao') == 4 and not snapshot.get('destino'):
            from core.integrations.fireads.sincronizacao_coleta import escolher
            from core.repositories.fireads.destino_coleta import salvar_destino
            snapshot = salvar_destino(envio, escolher(dados['rows'], snapshot), cursor)
            envio['snapshot'] = snapshot
            conn.commit()
        elif snapshot.get('versao') == 3 and not snapshot.get('destino'):
            encontrados = localizar(dados['rows'], snapshot['telefone'], 'WhatsApp', incluir_equivalentes=True)
            if not linhas_com_bloco(encontrados, bloco):
                from core.integrations.fireads.destino_coleta import escolher
                from core.repositories.fireads.destino_coleta import salvar_destino
                snapshot = salvar_destino(envio, escolher(dados['rows'], snapshot), cursor)
                envio['snapshot'] = snapshot
                conn.commit()
        operacao = preparar_escrita(dados["rows"], snapshot, bloco)
        conferir_posse(envio, cursor)
        conn.commit()
        if operacao is None:
            encontrados = localizar(
                dados["rows"], snapshot["telefone"], "WhatsApp", incluir_equivalentes=True
            )
            recibo = {
                "success": True,
                "reconciliado": True,
                "aba": snapshot["aba"],
                "linhas_reconciliadas": linhas_com_bloco(encontrados, bloco),
            }
        else:
            recibo = cliente.enviar(snapshot["aba"], **operacao)
        concluir(envio, recibo, cursor)
        conn.commit()
        logger.info(
            "dash_enviado | conversa=%s tentativa=%s",
            envio["conversa"],
            envio["tentativa"],
        )
        return True
    except psycopg.Error:
        conn.rollback()
        raise
    except Exception as exc:
        conn.rollback()
        # Armazenar apenas erros de contrato controlados, sem URLs ou corpos externos.
        seguro = (
            exc if isinstance(exc, ErroFireAds) else ErroFireAds(type(exc).__name__)
        )
        reagendar(envio, seguro, cursor)
        conn.commit()
        logger.warning(
            "dash_pendente | conversa=%s tipo=%s", envio["conversa"], type(exc).__name__
        )
        return False
    finally:
        if cliente:
            cliente.close()
        if bloqueado and not conn.closed:
            liberar_contato(chave, cursor)
            conn.commit()


def processar_lote(conn, cursor, limite=100):
    resumo = {"processados": 0, "enviados": 0, "falhas": 0}
    for _ in range(limite):
        envio = reservar(cursor)
        conn.commit()
        if envio is None:
            break
        resumo["processados"] += 1
        resumo["enviados" if processar(envio, conn, cursor) else "falhas"] += 1
    return resumo
```

## Passo 5 — criar `tests/unit/test_fireads_sincronizacao_coleta.py`

Verifica prioridade dos dados, seleção, atualização, recibos e recuperação sem serviços externos.

Conteúdo integral do arquivo (UTF-8; SHA-256 com finais LF: `3df790c8c4627f9f006aa9896c77dbf5135842a916a7810bf95252e44bdb1a13`):

```python
"""Autoridade do chat e retomada de escritas parciais, sem serviços externos."""

from copy import deepcopy
import unittest
from unittest.mock import Mock, patch

from core.integrations.fireads.cliente import ClienteFireAds
from core.integrations.fireads.contrato import ABA_DESTINO, ErroFireAds, bloco_observacoes
from core.integrations.fireads.coleta_abertura import interpretar_parcial
from core.integrations.fireads.sincronizacao_coleta import dados_sincronizacao, escolher, preparar
from core.validacoes.coleta_abertura import campo, criar_contexto
from tests.unit.test_coleta_abertura import FORM, NUMERO, ROW, snapshot

BLOCO = bloco_observacoes(1, 1, 'NOVO LEAD : META ADS : TITULAR\n- Nome do cliente: Ana Paula', versao=3)


def coleta(texto=FORM + '\nTurno: Tarde', *, com_link=False):
    return criar_contexto(1, {'id_mensagem': 1, 'id_hash': 'wamid.teste',
                             'tipo_mensagem': 'text', 'conteudo_texto': texto},
                          coletar_turno=not com_link)


def retrato(estado=None, *, com_link=False):
    return dict(snapshot(), versao=4, observacoes=BLOCO,
                **dados_sincronizacao(estado or coleta(), com_link=com_link))


def row(**kwargs):
    return dict(ROW, **{'Período preferido': 'Manhã'}, **kwargs)


def planejar(rows, snap=None):
    snap = snap or retrato()
    snap['destino'] = escolher(rows, snap)
    return snap


class AutoridadeTests(unittest.TestCase):
    def test_nome_completo_relacao_email_turno_e_correcao_do_atendimento(self):
        estado = coleta(FORM.replace('Para mim', 'Minha filha') + '\nTurno: Tarde')
        estado['campos']['email'] = campo(['corrigido@example.com'], 'email', 'atendimento')
        campos = dados_sincronizacao(estado)['campos_dashboard']
        self.assertEqual(campos, {'Nome': 'Ana Paula Silva', 'Email': 'corrigido@example.com',
                                 'Para quem é': 'Minha filha', 'Período preferido': 'Tarde'})
        self.assertEqual(estado['mensagem_original']['email']['valor'], 'ana@example.com')

    def test_dados_ausentes_invalidos_conflitantes_ou_importados_nao_sobrescrevem(self):
        estado = coleta('Full name: Ana Paula Silva\nEmail: x\nPara quem é: Criança\nTurno: tarde ou noite')
        estado['campos']['email'] = campo(['importado@example.com'], 'email', 'dashboard')
        self.assertEqual(dados_sincronizacao(estado)['campos_dashboard'], {'Nome': 'Ana Paula Silva'})
        estado['campos']['email'] = campo(['a@example.com', 'b@example.com'], 'email')
        self.assertNotIn('Email', dados_sincronizacao(estado)['campos_dashboard'])

    def test_com_link_nao_escreve_turno_nem_o_usa_para_selecionar(self):
        snap = retrato(com_link=True)
        self.assertNotIn('Período preferido', snap['campos_dashboard'])
        self.assertNotIn('turno', snap['identidade_coleta'])
        self.assertFalse(snap['coletar_turno'])

    def test_consulta_divergente_preserva_os_conhecidos_e_deixa_so_ausente_pendente(self):
        estado = coleta('Nome: Ana Paula Silva\nPara quem é: Minha filha\nTurno: Tarde')
        r = interpretar_parcial([row(Nome='Outro Nome')], NUMERO, None, ABA_DESTINO, estado)
        for tipo in ('nome', 'destinatario', 'turno'):
            self.assertEqual(r['coleta']['campos'][tipo], estado['campos'][tipo])
        self.assertEqual(r['coleta']['campos']['email']['status'], 'ausente')


class SelecaoTests(unittest.TestCase):
    def test_incompativeis_do_mesmo_telefone_atualiza_mais_recente_elegivel(self):
        rows = [row(Nome='Outro', Email='outro@example.com', _row=44),
                row(Nome='Diferente', Email='dif@example.com', _row=45),
                row(_row=100, Canal='Indicação')]
        self.assertEqual(escolher(rows, retrato())['referencia']['linha'], 45)

    def test_relacao_exata_depois_logica_depois_demais_e_recencia(self):
        snap = retrato(coleta(FORM.replace('Para mim', 'Minha filha')))
        rows = [dict(row(), _row=10, **{'Para quem é': 'Para minha filha'}),
                dict(row(), _row=20, **{'Para quem é': 'Para uma amiga'}),
                dict(row(), _row=30, **{'Período preferido': 'Tarde'})]
        for restantes, linha in [(rows, 10), (rows[1:], 20), (rows[2:], 30)]:
            self.assertEqual(escolher(restantes, snap)['referencia']['linha'], linha)

    def test_prioridade_compativel_nome_email_antes_de_divergente_recente(self):
        rows = [row(_row=44), row(_row=99, Email='outro@example.com')]
        self.assertEqual(escolher(rows, retrato())['referencia']['linha'], 44)

    def test_fallback_usa_data_antes_da_linha(self):
        rows = [dict(row(Nome='X'), _row=90, **{'Data/Hora': '18/10/2026'}),
                dict(row(Nome='Y'), _row=44, **{'Data/Hora': '20/10/2026'})]
        self.assertEqual(escolher(rows, retrato())['referencia']['linha'], 44)

    def test_ausente_cria_com_nome_completo_e_turno(self):
        dados = preparar([], planejar([]), BLOCO)['dados']
        self.assertEqual(dados['Nome'], 'Ana Paula Silva')
        self.assertEqual(dados['Período preferido'], 'Tarde')
        self.assertEqual(dados['WhatsApp'], NUMERO)

    def test_manual_nao_e_alvo_e_outro_telefone_nao_e_alvo(self):
        self.assertEqual(escolher([row(Canal='Lead Franqueador')], retrato()), {'tipo': 'create'})
        with self.assertRaises(ErroFireAds):
            escolher([row(WhatsApp='5511999990003')], retrato())

    def test_vinculo_da_consulta_precede_nova_inscricao(self):
        from core.integrations.fireads.aba_geral import referencia_registro
        snap = retrato()
        snap['referencia'] = referencia_registro(row(), ABA_DESTINO)
        self.assertEqual(escolher([row(), row(_row=100)], snap)['referencia']['linha'], 44)


class RecuperacaoTests(unittest.TestCase):
    def setUp(self):
        self.original = row(Nome='Nome antigo', Email='antigo@example.com')
        self.snap = planejar([self.original])

    def aplicar(self, r, operacao):
        return dict(r, **operacao['campos'], **{'Observação': operacao['observacoes']})

    def test_update_preserva_outras_colunas_e_observacoes(self):
        antes = deepcopy(self.original)
        op = preparar([self.original], self.snap, BLOCO)
        depois = self.aplicar(self.original, op)
        self.assertEqual(depois['Nome'], 'Ana Paula Silva')
        self.assertEqual(depois['Email'], 'ana@example.com')
        self.assertEqual(depois['Período preferido'], 'Tarde')
        for c in set(self.original) - set(op['campos']) - {'Observação'}:
            self.assertEqual(depois[c], antes[c])
        self.assertEqual(depois['Observação'], antes['Observação'] + '\n\n' + BLOCO)
        self.assertEqual(self.original, antes)

    def test_resposta_perdida_reconcilia_e_nao_duplica_observacoes(self):
        depois = self.aplicar(self.original, preparar([self.original], self.snap, BLOCO))
        self.assertIsNone(preparar([depois], self.snap, BLOCO))

    def test_cada_ponto_de_queda_parcial_e_recuperavel_inclusive_linha_movida(self):
        op = preparar([self.original], self.snap, BLOCO)
        itens = list(op['campos'].items())
        for n in range(len(itens) + 1):
            with self.subTest(campos_aplicados=n):
                parcial = dict(self.original, _row=75, **dict(itens[:n]))
                reenvio = preparar([parcial], self.snap, BLOCO)
                self.assertEqual(reenvio['row'], 75)
                final = self.aplicar(parcial, reenvio)
                self.assertIsNone(preparar([final], self.snap, BLOCO))

    def test_marcador_so_nao_basta_se_campos_ainda_divergem(self):
        parcial = dict(self.original, **{'Observação': self.original['Observação'] + '\n\n' + BLOCO})
        op = preparar([parcial], self.snap, BLOCO)
        self.assertEqual(op['observacoes'], parcial['Observação'])
        self.assertEqual(op['campos']['Email'], 'ana@example.com')

    def test_mudanca_em_dado_do_chat_na_planilha_e_reaplicada(self):
        alterado = dict(self.original, Nome='Edição manual', Email='manual@example.com')
        op = preparar([alterado], self.snap, BLOCO)
        self.assertEqual(op['campos']['Nome'], 'Ana Paula Silva')

    def test_exclusao_nao_redireciona_para_outro_registro_ou_telefone(self):
        for substituto in (row(WhatsApp='5511999990003'),
                           dict(row(), **{'Data/Hora': '21/10/2026'})):
            with self.subTest(substituto=substituto):
                with self.assertRaises(ErroFireAds):
                    preparar([substituto], self.snap, BLOCO)

    def test_registros_indistinguiveis_movidos_nao_sao_adivinhados(self):
        with self.assertRaises(ErroFireAds):
            preparar([dict(self.original, _row=50), dict(self.original, _row=51)], self.snap, BLOCO)

    def test_novo_registro_apos_reserva_nao_troca_destino(self):
        rows = [self.original, dict(row(), _row=100, **{'Data/Hora': '22/10/2026'})]
        self.assertEqual(preparar(rows, self.snap, BLOCO)['row'], 44)

    def test_marcador_duplicado_ou_alterado_nao_confirma_entrega(self):
        marcado = dict(self.original, **{'Observação': BLOCO})
        with self.assertRaises(ErroFireAds):
            preparar([marcado, dict(marcado, _row=75)], self.snap, BLOCO)
        with self.assertRaises(ErroFireAds):
            preparar([dict(marcado, **{'Observação': BLOCO.replace('Resumo', 'Editado')})], self.snap, BLOCO)

    def test_append_aplicado_reconcilia_ou_repara_sem_novo_append(self):
        snap = planejar([])
        criado = dict(preparar([], snap, BLOCO)['dados'], _row=99)
        self.assertIsNone(preparar([criado], snap, BLOCO))
        criado['Email'] = 'antigo@example.com'
        op = preparar([criado], snap, BLOCO)
        self.assertEqual(op['row'], 99)
        self.assertNotIn('dados', op)
        self.assertEqual(op['observacoes'], BLOCO)

    def test_campo_ausente_na_resposta_nao_autoriza_sucesso(self):
        incompleto = dict(self.original)
        incompleto.pop('Período preferido')
        with self.assertRaises(ErroFireAds):
            preparar([incompleto], self.snap, BLOCO)


class ClienteTests(unittest.TestCase):
    def test_post_envia_quatro_campos_e_exige_recibo_de_todos(self):
        cliente = ClienteFireAds('https://script.google.com/macros/s/teste/exec')
        campos = retrato()['campos_dashboard']
        for confirmados, ok in [(list(campos) + ['Observação'], True), (['Observação'], False)]:
            with patch.object(cliente, '_request', return_value=Mock(json=Mock(return_value={
                    'success': True, 'aba': ABA_DESTINO, 'row': 44, 'updated': confirmados}))) as req:
                if ok:
                    cliente.enviar(ABA_DESTINO, row=44, campos=campos, observacoes=BLOCO)
                else:
                    with self.assertRaises(ErroFireAds):
                        cliente.enviar(ABA_DESTINO, row=44, campos=campos, observacoes=BLOCO)
                updates = req.call_args.kwargs['json']['updates']
                self.assertEqual(list(updates)[-1], 'Observação')
                self.assertEqual(updates, dict(campos, **{'Observação': BLOCO}))
        cliente.close()

    def test_campos_vazios_e_colunas_fora_do_escopo_nao_sao_enviados(self):
        cliente = ClienteFireAds('https://script.google.com/macros/s/teste/exec')
        with patch.object(cliente, '_request') as req:
            for campos in ({'Email': ''}, {'Nome': None}, {'Canal': 'Meta Ads'}, {'WhatsApp': NUMERO}):
                with self.assertRaises(ErroFireAds):
                    cliente.enviar(ABA_DESTINO, row=44, campos=campos, observacoes=BLOCO)
            req.assert_not_called()
        cliente.close()

    def test_script_recusa_coluna_mantem_erro(self):
        cliente = ClienteFireAds('https://script.google.com/macros/s/teste/exec')
        with patch.object(cliente, '_request', return_value=Mock(json=Mock(return_value={
                'success': False, 'error': 'Coluna não editável'}))):
            with self.assertRaises(ErroFireAds):
                cliente.enviar(ABA_DESTINO, row=44, campos={'Nome': 'Ana'}, observacoes=BLOCO)
        cliente.close()


if __name__ == '__main__':
    unittest.main()
```

## Passo 6 — alterar `tests/integration/test_coleta_abertura_postgres.py`

Verifica destino persistido antes do POST e retomadas com PostgreSQL descartável.

Conteúdo integral do arquivo (UTF-8; SHA-256 com finais LF: `4594bd2845065135b63bc80c9606ee4adb48a79b27f1cc29a33de16adeb7d408`):

```python
"""Coleta por campo em PostgreSQL descartável; rede e WhatsApp substituídos."""
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
import unittest
from unittest.mock import Mock, patch

import psycopg
from tests.integration import test_fireads_postgres as legado
from tests.unit.test_coleta_abertura import FORM, ROW, snapshot
from core.repositories.fireads import pendencias, envios
from core.repositories.atendimento.coleta_abertura import guardar_coletas
from core.repositories.atendimento.conversas import inicializar_conversa_resposta_bot
from core.repositories.atendimento.followup import LockConversaPerdido
from core.integrations.fireads.coleta_abertura import interpretar_parcial
from core.integrations.fireads.contrato import ABA_DESTINO
from core.repositories.funil.leads import buscar_dados_lead_funil
from core.integrations.funil.oportunidades import montar_payload_oportunidade
from workers.worker_flow.fireads import preparar_abertura
from workers.worker_flow.valida_historico import valida_historico
from workers.worker_flow.response_flow.flow_sender import flow_sender
from workers.worker_flow.transacoes.persistencia_resposta import atualizar_banco_com_contexto_final
from workers.worker_flow.suporte.consultas_fireads import ConsultaFireAdsPendente
from workers.worker_funil.fireads import processar


@unittest.skipUnless(legado.DSN, 'Exige FIREADS_TEST_DSN em loopback e test_chatbot_fireads vazio')
class ColetaPostgresTests(unittest.TestCase):
    # Reutiliza somente a montagem segura do banco, não os testes da versão antiga.
    setUp = legado.FireAdsPostgresTests.setUp
    limpar = legado.FireAdsPostgresTests.limpar
    nova_conversa = legado.FireAdsPostgresTests.nova_conversa
    preparar_mensagem = legado.FireAdsPostgresTests.preparar_mensagem

    def inicio(self, texto=FORM + '\nTurno: Tarde', fireads=True):
        cid, msg, versao, ctx = self.preparar_mensagem()
        msg.update(conteudo_texto=texto, tipo_mensagem='text', id_hash='wamid.fireads',
                   data_recebimento=datetime.now(timezone.utc), id_phone_unidade='phone-teste',
                   unidade_telefone='5511999990000')
        self.cursor.execute('UPDATE chatbot.fila_mensagens SET conteudo_texto=%s WHERE id_mensagem=%s',
                            (texto, msg['id_mensagem']))
        if not fireads:
            self.cursor.execute('DELETE FROM chatbot.integracao_fireads')
        self.conn.commit()
        return cid, msg, versao, ctx

    def concluir(self, rows):
        reserva = pendencias.reservar(self.cursor)
        self.conn.commit()
        entrada = reserva['entrada']
        decisao = interpretar_parcial(rows, entrada['numero'], entrada['fuso'], entrada['aba'], entrada['coleta'])
        self.assertTrue(pendencias.concluir(reserva, {'decisao': decisao, 'fontes': {'geral': rows}}, self.cursor))
        pendencias.liberar_reserva(reserva['id_consulta'], self.cursor)
        self.conn.commit()

    def test_completo_sem_consulta_recupera_sem_reextrair(self):
        cid, msg, v, ctx = self.inicio()
        novo = preparar_abertura(ctx, msg, v, self.cursor)
        self.conn.commit()
        self.assertEqual(novo['contexto_coleta']['etapa_inicial'], 4)
        self.assertEqual(self.conn.execute('SELECT count(*) FROM chatbot.consulta_fireads').fetchone()[0], 0)
        with patch('workers.worker_flow.coleta_abertura.criar_contexto', side_effect=AssertionError('Não reextrair')):
            retomado = preparar_abertura(ctx, dict(msg, conteudo_texto='Texto posterior'), v, self.cursor)
        self.assertEqual(retomado['contexto_coleta'], novo['contexto_coleta'])
        self.assertEqual(retomado['contexto_fireads']['origem'], 'meta')

    def test_tres_campos_sem_turno_consulta_e_persiste_preferencia_do_dashboard(self):
        cid, msg, v, ctx = self.inicio(FORM)
        with self.assertRaises(ConsultaFireAdsPendente):
            preparar_abertura(ctx, msg, v, self.cursor)
        self.conn.commit()
        self.concluir([dict(ROW, Canal='Chat Fire', **{'Período preferido': 'Sábado'})])
        novo = preparar_abertura(ctx, msg, v, self.cursor)
        self.conn.commit()
        self.assertEqual(novo['contexto_fireads']['origem'], 'chat_fire')
        self.assertEqual(novo['contexto_coleta']['campos']['turno']['fonte'], 'dashboard')
        self.assertEqual(self.conn.execute('SELECT turno FROM chatbot.conversa WHERE id_conversa=%s', (cid,)).fetchone()[0], 'sabado')
        self.assertEqual(self.conn.execute('SELECT count(*) FROM chatbot.consulta_fireads').fetchone()[0], 1)

    def test_chat_fire_parcial_nome_turno_da_mensagem_email_do_dashboard(self):
        texto = 'Olá! Sou Ana Paula. Vim pelo site.\nQuem vai fazer: Criança\nMelhor período: Sábado'
        cid, msg, v, ctx = self.inicio(texto)
        with self.assertRaises(ConsultaFireAdsPendente):
            preparar_abertura(ctx, msg, v, self.cursor)
        self.conn.commit()
        self.concluir([dict(ROW, Canal='Chat Fire', **{'Para quem é': '', 'Perfil/Faixa': 'Criança'})])
        novo = preparar_abertura(ctx, msg, v, self.cursor)
        self.assertEqual(novo['contexto_coleta']['etapa_inicial'], 2)
        self.assertEqual(novo['contexto_coleta']['campos']['email']['valor'], 'ana@example.com')
        self.assertEqual(novo['contexto_coleta']['campos']['turno']['valor'], 'sabado')
        self.assertEqual(novo['contexto_coleta']['campos']['destinatario']['status'], 'invalido')
        self.conn.rollback()
        retomado = preparar_abertura(ctx, msg, v, self.cursor)
        self.assertEqual(novo['contexto_coleta'], retomado['contexto_coleta'])
        self.conn.commit()
        self.assertEqual(self.conn.execute('SELECT origem_fireads,turno FROM chatbot.conversa WHERE id_conversa=%s', (cid,)).fetchone(), ('chat_fire', 'sabado'))

    def test_unidade_com_link_ignora_turno_na_abertura(self):
        cid, msg, v, ctx = self.inicio(FORM + '\nTurno: Sábado')
        self.cursor.execute("UPDATE chatbot.atendimento_customizado SET link_agendamento='https://example.com/agendar'")
        novo = preparar_abertura(ctx, msg, v, self.cursor)
        self.assertNotIn('turno', novo['contexto_coleta']['campos'])
        self.assertIsNone(self.conn.execute('SELECT turno FROM chatbot.conversa WHERE id_conversa=%s', (cid,)).fetchone()[0])
        self.assertEqual(self.conn.execute('SELECT count(*) FROM chatbot.consulta_fireads').fetchone()[0], 0)

    def test_unidade_sem_fireads_persiste_turno_sem_consulta(self):
        cid, msg, v, ctx = self.inicio('Eu me chamo Ana\nMelhor período: Sábado', fireads=False)
        novo = preparar_abertura(ctx, msg, v, self.cursor)
        self.assertEqual(novo['contexto_coleta']['etapa_inicial'], 2)
        self.assertEqual(self.conn.execute('SELECT turno FROM chatbot.conversa WHERE id_conversa=%s', (cid,)).fetchone()[0], 'sabado')
        self.assertEqual(self.conn.execute('SELECT count(*) FROM chatbot.consulta_fireads').fetchone()[0], 0)

    def test_turno_coletado_preserva_sexta_resposta_e_replay_sem_novo_envio(self):
        cid, msg, v, ctx = self.inicio(FORM + '\nTurno: Sábado', fireads=False)
        ctx = preparar_abertura(ctx, msg, v, self.cursor)
        self.cursor.execute('UPDATE chatbot.cliente SET idade=40 WHERE id_cliente=1')
        self.cursor.execute('UPDATE chatbot.conversa SET id_etapa_atual=17 WHERE id_conversa=%s', (cid,))
        self.cursor.execute("INSERT INTO chatbot.respostas_desafios(id_conversa,id_etapa,resposta) SELECT %s,etapa,'Nunca' FROM generate_series(12,16) etapa", (cid,))
        msg['conteudo_texto'] = 'Nunca'
        self.cursor.execute('UPDATE chatbot.fila_mensagens SET conteudo_texto=%s WHERE id_mensagem=%s', ('Nunca', msg['id_mensagem']))
        ctx['conversa']['id_etapa_atual'] = 17
        hist = valida_historico(msg, ctx, self.cursor)
        with patch('workers.worker_flow.response_flow.etapas.resolver_etapa17.enviar_etapa19', return_value={
            'enviou': True, 'resposta_ja_existia': False, 'mensagem_bot': 'Fale com o comercial',
            'id_hash_msg_bot': 'wamid.comercial', 'id_etapa_resultante': 19, 'tipo_mensagem': 'text',
            'canal': 'meta_whatsapp', 'atualizar_conversa': True, 'atualizar_last_from_bot': True,
        }) as sender:
            resposta = flow_sender(hist)
        sender.assert_called_once()
        self.assertEqual(resposta['evento_transicao'], 'triagem_concluida_turno_coletado')
        atualizar_banco_com_contexto_final(hist, resposta, self.cursor)
        self.conn.commit()
        self.assertEqual(self.conn.execute('SELECT id_etapa_atual,turno FROM chatbot.conversa WHERE id_conversa=%s', (cid,)).fetchone(), (19, 'sabado'))
        self.assertEqual(self.conn.execute('SELECT count(*) FROM chatbot.respostas_desafios WHERE id_conversa=%s', (cid,)).fetchone()[0], 6)
        # O replay parte da etapa do cliente registrada no histórico.
        ctx['conversa']['id_etapa_atual'] = 19
        replay = valida_historico(msg, ctx, self.cursor)
        with patch('workers.worker_flow.response_flow.etapas.resolver_etapa17.enviar_etapa19', side_effect=AssertionError('Não reenviar')):
            resposta = flow_sender(replay)
        self.assertTrue(resposta['resposta_ja_existia'])
        atualizar_banco_com_contexto_final(replay, resposta, self.cursor)
        self.conn.commit()
        self.assertEqual(self.conn.execute('SELECT count(*) FROM chatbot.respostas_desafios WHERE id_conversa=%s', (cid,)).fetchone()[0], 6)

    def test_migracao_chat_fire_sabado_reexecucao_preserva_contexto(self):
        cid, msg, v, ctx = self.inicio(FORM + '\nTurno: Sábado')
        preparar_abertura(ctx, msg, v, self.cursor)
        self.conn.commit()
        sql = 'SELECT contexto_coleta,turno,origem_fireads FROM chatbot.conversa WHERE id_conversa=%s'
        antes = self.conn.execute(sql, (cid,)).fetchone()
        self.conn.commit()
        migration = Path(__file__).resolve().parents[2] / 'deploy/migrations/20261021_chat_fire_turno_coleta.sql'
        self.conn.execute(migration.read_text(encoding='utf-8'), prepare=False)
        self.assertEqual(self.conn.execute(sql, (cid,)).fetchone(), antes)
        with self.conn.transaction():
            with self.assertRaises(psycopg.errors.CheckViolation):
                with self.conn.transaction():
                    self.conn.execute("UPDATE chatbot.conversa SET turno='sexta' WHERE id_conversa=%s", (cid,))

    def test_sem_fireads_preserva_canal_da_unidade(self):
        cid, msg, v, ctx = self.inicio(fireads=False)
        novo = preparar_abertura(ctx, msg, v, self.cursor)
        self.assertNotIn('contexto_fireads', novo)
        self.assertEqual(self.conn.execute('SELECT origem_fireads FROM chatbot.conversa WHERE id_conversa=%s', (cid,)).fetchone()[0], None)
        payload = {'teste': True}
        self.assertEqual(envios.congelar({'id_conversa': cid}, payload, {'codigo_canal_venda': '113340', 'link_api_carrossel': 'https://example.com'}, self.cursor)[1], '113340')
        self.assertEqual(self.conn.execute('SELECT count(*) FROM chatbot.envios_dash').fetchone()[0], 0)

    def test_parcial_recupera_consulta_salva_apos_rollback(self):
        cid, msg, v, ctx = self.inicio('Full name: Ana Paula Silva\nPara quem é: Para mim')
        with self.assertRaises(ConsultaFireAdsPendente):
            preparar_abertura(ctx, msg, v, self.cursor)
        self.conn.commit()
        self.concluir([ROW])
        novo = preparar_abertura(ctx, msg, v, self.cursor)
        self.assertEqual(novo['contexto_coleta']['campos']['email']['valor'], 'ana@example.com')
        self.conn.rollback()
        reaplicado = preparar_abertura(ctx, msg, v, self.cursor)
        self.assertEqual(reaplicado['contexto_coleta'], novo['contexto_coleta'])
        self.assertEqual(self.conn.execute('SELECT count(*) FROM chatbot.consulta_fireads').fetchone()[0], 1)

    def test_timeout_nao_reconsulta_e_pergunta_so_o_que_falta(self):
        cid, msg, v, ctx = self.inicio('Full name: Ana Paula Silva')
        with self.assertRaises(ConsultaFireAdsPendente):
            preparar_abertura(ctx, msg, v, self.cursor)
        self.cursor.execute("UPDATE chatbot.consulta_fireads SET solicitado_em=clock_timestamp()-INTERVAL '301 seconds', prazo_final=clock_timestamp()-INTERVAL '1 second'")
        self.conn.commit()
        novo = preparar_abertura(ctx, msg, v, self.cursor)
        self.assertEqual(novo['contexto_coleta']['etapa_inicial'], 2)
        self.conn.commit()
        self.assertEqual(preparar_abertura(ctx, msg, v, self.cursor)['contexto_coleta'], novo['contexto_coleta'])
        self.assertEqual(self.conn.execute('SELECT count(*) FROM chatbot.consulta_fireads').fetchone()[0], 1)

    def test_lock_perdido_nao_importa(self):
        cid, msg, v, ctx = self.inicio()
        self.cursor.execute('UPDATE chatbot.conversa SET lock_version=lock_version+1 WHERE id_conversa=%s', (cid,))
        self.conn.commit()
        with self.assertRaises(LockConversaPerdido):
            preparar_abertura(ctx, msg, v, self.cursor)
        self.conn.rollback()
        self.assertIsNone(self.conn.execute('SELECT contexto_coleta FROM chatbot.conversa WHERE id_conversa=%s', (cid,)).fetchone()[0])

    def test_email_duplicado_no_cadastro_preserva_os_outros_campos(self):
        cid, msg, v, ctx = self.inicio()
        self.cursor.execute("INSERT INTO chatbot.cliente(nome,waid_telefone,email) VALUES('Outro','5511999990003','ana@example.com')")
        novo = preparar_abertura(ctx, msg, v, self.cursor)
        coleta = novo['contexto_coleta']
        self.assertEqual(coleta['campos']['email']['status'], 'conflitante')
        self.assertEqual(coleta['campos']['nome']['valor'], 'Ana Paula')
        self.assertEqual(coleta['etapa_inicial'], 4)
        self.assertEqual(novo['contexto_fireads']['resultado'], 'incompleto')

    def test_inicializacao2_sql_e_replay_da_resposta(self):
        cid, msg, v, ctx = self.inicio('Full name: Ana Paula Silva\nEmail: ana@example.com', fireads=False)
        ctx = preparar_abertura(ctx, msg, v, self.cursor)
        hist = valida_historico(msg, ctx, self.cursor)
        self.assertEqual(hist['id_etapa_cliente'], 2)
        with patch('core.integrations.whatsapp.pywa_functions.pywa_senders.abertura_coleta.conta_wa') as wa:
            wa.return_value.send_message.return_value = {'messages': [{'id': 'wamid.resposta'}]}
            with patch('core.integrations.whatsapp.pywa_functions.pywa_senders.abertura_coleta.extrair_id_hash_msg_bot', return_value='wamid.resposta'):
                resposta = flow_sender(hist)
        atualizar_banco_com_contexto_final(hist, resposta, self.cursor)
        self.conn.commit()
        self.assertEqual(self.conn.execute('SELECT id_etapa_atual FROM chatbot.conversa WHERE id_conversa=%s', (cid,)).fetchone()[0], 2)
        ctx['conversa']['id_etapa_atual'] = 2
        replay = valida_historico(msg, ctx, self.cursor)
        with patch('core.integrations.whatsapp.pywa_functions.pywa_senders.abertura_coleta.conta_wa', side_effect=AssertionError('Não reenviar')):
            self.assertTrue(flow_sender(replay)['resposta_ja_existia'])

    def test_migracao_idempotente_preserva_coletas(self):
        cid, msg, v, ctx = self.inicio()
        preparar_abertura(ctx, msg, v, self.cursor)
        self.conn.commit()
        antes = self.conn.execute('SELECT contexto_coleta FROM chatbot.conversa WHERE id_conversa=%s', (cid,)).fetchone()[0]
        arquivo = Path(__file__).resolve().parents[2] / 'deploy/migrations/20261019_coleta_abertura.sql'
        self.conn.commit()
        self.conn.execute(arquivo.read_text(encoding='utf-8'), prepare=False)
        depois = self.conn.execute('SELECT contexto_coleta FROM chatbot.conversa WHERE id_conversa=%s', (cid,)).fetchone()[0]
        self.assertEqual(antes, depois)

    def test_nome_pendente_salta_destinatario_somente_pelo_mapa(self):
        cid, msg, v, ctx = self.inicio('Email: ana@example.com\nPara quem é: Para minha mãe', fireads=False)
        ctx = preparar_abertura(ctx, msg, v, self.cursor)
        self.assertEqual(ctx['contexto_coleta']['etapa_inicial'], 1)
        inicializar_conversa_resposta_bot(cid, 1, datetime.now(timezone.utc), self.cursor)
        self.cursor.execute("""INSERT INTO chatbot.fila_mensagens(cliente_telefone,conteudo_texto,tipo_mensagem,
            id_phone_unidade,unidade_telefone,id_hash_msg,id_conversa,status,retry_count,
            processing_started_at,received_data_hora)
            VALUES(%s,'Ana Paula','text','phone-teste','5511999990000','wamid.nome',%s,'processing',1,
            clock_timestamp(),clock_timestamp()) RETURNING id_mensagem""", (legado.NUMERO, cid))
        msg.update(id_mensagem=self.cursor.fetchone()[0], id_hash='wamid.nome', conteudo_texto='Ana Paula')
        self.conn.commit()
        ctx['conversa']['id_etapa_atual'] = 1
        ctx = preparar_abertura(ctx, msg, v, self.cursor)
        hist = valida_historico(msg, ctx, self.cursor)
        self.assertEqual(hist['transicoes_permitidas']['nome_cliente_valido_destino_coletado'], 4)
        with patch('workers.worker_flow.response_flow.etapas.resolver_etapa1.enviar_etapa4', return_value={
            'enviou': True, 'resposta_ja_existia': False, 'mensagem_bot': 'Qual sua profissão?',
            'id_hash_msg_bot': 'wamid.profissao', 'id_etapa_resultante': 4, 'tipo_mensagem': 'text',
            'canal': 'meta_whatsapp', 'atualizar_conversa': True, 'atualizar_last_from_bot': True,
        }):
            resposta = flow_sender(hist)
        atualizar_banco_com_contexto_final(hist, resposta, self.cursor)
        self.conn.commit()
        etapa, coleta = self.conn.execute('SELECT id_etapa_atual,contexto_coleta FROM chatbot.conversa WHERE id_conversa=%s', (cid,)).fetchone()
        self.assertEqual(etapa, 4)
        self.assertEqual(coleta['campos']['nome']['valor'], 'Ana Paula')
        self.assertTrue(coleta['campos']['destinatario']['valor']['dependente'])

    def test_funil_retrato_por_conversa_e_destino_congelado_antes_do_post(self):
        cid, msg, v, ctx = self.inicio()
        ctx = preparar_abertura(ctx, msg, v, self.cursor)
        self.cursor.execute('UPDATE chatbot.conversa SET id_etapa_atual=19,turno=%s,profissao=%s WHERE id_conversa=%s', ('manha', 'Professora', cid))
        self.cursor.execute('UPDATE chatbot.cliente SET idade=35 WHERE id_cliente=1')
        guardar_coletas({'id_conversa': cid, 'id_cliente': 1, 'contexto_coleta': ctx['contexto_coleta']}, {'destino_dado': 'cliente'}, self.cursor)
        self.cursor.execute("INSERT INTO chatbot.respostas_desafios(id_conversa,id_etapa,resposta) SELECT %s,etapa,'Às vezes' FROM generate_series(12,17) etapa", (cid,))
        dados = buscar_dados_lead_funil(cid, self.cursor)
        payload = montar_payload_oportunidade(dados)
        envios.congelar(dados, payload, {'codigo_canal_venda': '113340', 'link_api_carrossel': 'https://example.com/api'}, self.cursor)
        self.cursor.execute('UPDATE chatbot.conversa SET lead_no_funil=TRUE WHERE id_conversa=%s', (cid,))
        envio = envios.reservar(self.cursor)
        self.conn.commit()
        externo = Mock()
        externo.consultar.return_value = {'headers': list(ROW) + ['Período preferido'], 'rows': []}

        def enviar(*args, **kwargs):
            with psycopg.connect(legado.DSN) as verificador:
                alvo = verificador.execute("SELECT snapshot->'destino' FROM chatbot.envios_dash WHERE id_envio_dash=%s", (envio['id'],)).fetchone()[0]
                self.assertEqual(alvo, {'tipo': 'create'})
            return {'success': True, 'inserted': 1, 'aba': ABA_DESTINO}

        externo.enviar.side_effect = enviar
        with patch('workers.worker_funil.fireads.ClienteFireAds', return_value=externo):
            self.assertTrue(processar(envio, self.conn, self.cursor))
        self.assertEqual(externo.enviar.call_args.kwargs['dados']['Canal'], 'Meta Ads')
        self.assertEqual(externo.enviar.call_args.kwargs['dados']['Nome'], 'Ana Paula Silva')
        self.assertEqual(externo.enviar.call_args.kwargs['dados']['Período preferido'], 'Tarde')
        self.assertEqual(self.conn.execute('SELECT status FROM chatbot.envios_dash').fetchone()[0], 'sent')

    def test_sincronizacao_retomada_apos_escrita_parcial_e_resposta_perdida(self):
        cid, msg, v, ctx = self.inicio()
        ctx = preparar_abertura(ctx, msg, v, self.cursor)
        self.cursor.execute('UPDATE chatbot.conversa SET id_etapa_atual=19,profissao=%s WHERE id_conversa=%s', ('Professora', cid))
        self.cursor.execute('UPDATE chatbot.cliente SET idade=35 WHERE id_cliente=1')
        guardar_coletas({'id_conversa': cid, 'id_cliente': 1, 'contexto_coleta': ctx['contexto_coleta']},
                        {'destino_dado': 'cliente'}, self.cursor)
        self.cursor.execute("INSERT INTO chatbot.respostas_desafios(id_conversa,id_etapa,resposta) SELECT %s,etapa,'Às vezes' FROM generate_series(12,17) etapa", (cid,))
        dados = buscar_dados_lead_funil(cid, self.cursor)
        payload = montar_payload_oportunidade(dados)
        config = {'codigo_canal_venda': '113340', 'link_api_carrossel': 'https://example.com/api'}
        envios.congelar(dados, payload, config, self.cursor)
        self.cursor.execute('UPDATE chatbot.conversa SET lead_no_funil=TRUE WHERE id_conversa=%s', (cid,))
        envio = envios.reservar(self.cursor)
        self.conn.commit()
        self.assertEqual(envio['snapshot']['versao'], 4)
        externo = Mock()
        planilha = dict(ROW, Nome='Nome antigo', Email='antigo@example.com', **{'Período preferido': 'Manhã'})
        externo.consultar.side_effect = lambda *_: {'headers': list(planilha), 'rows': [deepcopy(planilha)]}
        tentativas = []

        def enviar(_aba, **op):
            with psycopg.connect(legado.DSN) as verificador:
                congelado = verificador.execute('SELECT snapshot FROM chatbot.envios_dash WHERE id_envio_dash=%s', (envio['id'],)).fetchone()[0]
                self.assertEqual(congelado['destino']['referencia']['linha'], 44)
                self.assertEqual(congelado['campos_dashboard'], op['campos'])
            tentativas.append(deepcopy(op))
            if len(tentativas) == 1:
                planilha['Nome'] = op['campos']['Nome']
                raise TimeoutError('Queda após gravar nome')
            planilha.update(op['campos'])
            planilha['Observação'] = op['observacoes']
            raise TimeoutError('Resposta perdida após gravar tudo')

        externo.enviar.side_effect = enviar
        with patch('workers.worker_funil.fireads.ClienteFireAds', return_value=externo):
            self.assertFalse(processar(envio, self.conn, self.cursor))
            self.assertEqual(self.conn.execute('SELECT status FROM chatbot.envios_dash').fetchone()[0], 'pending')
            # Uma alteração posterior no cadastro não muda o envio congelado.
            dados['nome_cliente'] = 'Não reenviar este nome'
            envios.congelar(dados, {}, config, self.cursor)
            for sucesso in (False, True):
                planilha['_row'] = 70  # Moveu; a identidade e o bloco permitem reencontrar.
                self.cursor.execute("UPDATE chatbot.envios_dash SET next_attempt_at=clock_timestamp()-INTERVAL '1 second'")
                envio = envios.reservar(self.cursor)
                self.conn.commit()
                self.assertEqual(processar(envio, self.conn, self.cursor), sucesso)
        self.assertEqual(len(tentativas), 2)
        self.assertEqual(tentativas[0]['campos'], tentativas[1]['campos'])
        self.assertEqual(planilha['Nome'], 'Ana Paula Silva')
        self.assertEqual(planilha['Período preferido'], 'Tarde')
        self.assertEqual(planilha['Observação'].count('[INICIO CHATBOT:'), 1)
        status, recibo = self.conn.execute('SELECT status,recibo FROM chatbot.envios_dash').fetchone()
        self.assertEqual(status, 'sent')
        self.assertTrue(recibo['reconciliado'])


if __name__ == '__main__':
    unittest.main()
```

## Passo 7 — solicitar à FireAds a liberação das colunas editáveis

Este é o último passo do plano e a condição para ativá-lo em produção. Não é
necessário criar novas colunas se já existem: é preciso autorizar a edição delas
na API do Apps Script. No código anexado, a lista atual contém apenas
`Feedback Comercial` e `Observação`; a versão publicada não foi inspecionada.

Solicitação pronta para encaminhar à FireAds:

> Precisamos que o Web App da integração permita ao chatbot atualizar, na aba
> LEADS GERAL - Feedback, as colunas Nome, Email, Para quem é e Período preferido,
> além de manter Feedback Comercial e Observação já autorizadas. Os cabeçalhos
> precisam estar disponíveis na consulta e na atualização. Por favor, ampliem
> CONFIG.EDITABLE_COLUMNS para a lista abaixo, preservem as verificações de
> autenticação e publiquem a nova versão na implantação existente para manter
> a mesma URL /exec. O retorno precisa confirmar a aba, a linha e todas as
> colunas efetivamente atualizadas em updated. Avisem quando estiver publicado
> para validarmos com um registro de teste antes de ativar no chatbot.

Trecho completo da propriedade a substituir dentro de `CONFIG` (não é um novo
script independente):

```javascript
EDITABLE_COLUMNS: [
  'Feedback Comercial',
  'Observação',
  'Nome',
  'Email',
  'Para quem é',
  'Período preferido'
],
```

Manter a lista explícita e a verificação `isEditable`; não liberar colunas
indiscriminadamente. A ampliação vale para os clientes já autorizados desse
endpoint, inclusive o painel. Manter o controle de acesso atual. Confirmar que
as validações de células aceitam o nome, e-mail, relação de titular/dependente e
os turnos Manhã, Tarde, Noite e Sábado enviados pelo chatbot.

O script anexado grava coluna por coluna. O código deste plano envia Observação
por último, reconhece aplicação parcial e exige confirmação de todas as colunas.
Se a API recusar uma coluna, o envio permanece pendente; não reduzir silenciosamente
a operação a Observação nem marcar sucesso. Não reprocessar envios antigos nem
converter seus snapshots. A liberação e publicação externas ficam a cargo da
FireAds; este documento não executa nenhuma delas automaticamente.
