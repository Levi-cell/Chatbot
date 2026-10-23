# Plano prático — sincronização FireAds, telefone e ordem das entregas

**Revisão aplicada ao código local em 22/10/2026, sobre V1.15.0 (`5ff1681`).**
Não representa deploy na VM, alteração de produção ou execução no Apps Script.
Este documento substitui o plano anterior de seis arquivos; os passos abaixo
contêm o código completo atualizado. Não reaplicar uma cópia antiga sobre esta
revisão. O último passo conserva a orientação das colunas editáveis da FireAds.

## Regras consolidadas

1. O telefone do remetente identifica o contato. Considerar todas as variantes
   brasileiras já mapeadas, inclusive máscaras, DDI e nono dígito.
2. Na abertura, a primeira mensagem continua prioritária. Consultar somente se
   faltarem nome/e-mail/destinatário ou, sem link, turno. Preencher apenas ausências
   a partir de uma linha; o restante é perguntado na etapa normal.
3. Selecionar o registro elegível por data/hora mais recente e maior linha em
   empate; sem data válida, maior linha. Nome, email, relação e turno não filtram.
4. Somente Google Ads, Meta Ads, Chat Fire e Orgânico Site são elegíveis. Indicação
   e Lead Franqueador nunca são alterados nem fornecem dados. Havendo apenas
   canais manuais, Orgânico ou ausência real do telefone, criar novo Orgânico
   (113481) para a nova conversa. Retentativas reconciliam a própria entrega.
   Sem formulário elegível, canal desconhecido/vazio mantém entrega pendente.
   Recusa explícita por telefone duplicado permite atualizar o Orgânico mais
   recente do mesmo telefone no próximo ciclo; persistir a alternativa antes do
   POST. Timeout ou erro genérico não autorizam essa troca.
5. Antes da primeira entrega, confirmar a linha/canal na planilha, inclusive se
   houve consulta inicial. Google Ads=113336; Meta Ads=113340; Orgânico Site,
   Chat Fire e Orgânico=113481. Formato de mensagem não implica origem Meta Ads.
6. Congelar a decisão e o texto comum antes do primeiro POST. Gravar/confirmar
   dashboard primeiro e só então enviar ao Funil. Sem FireAds, envio direto ao
   Funil com código da unidade. Dashboard pendente impede o POST ao Funil.
7. Atualizar Nome, Email, Para quem é e Período preferido aceitos na mensagem ou
   atendimento; turno só sem link. Correção explícita aceita prevalece. Não apagar
   campos por ausência. Dados apenas importados não são regravados em updates.
   Preservar Canal, WhatsApp, Data/Hora, Perfil/Faixa e demais colunas.
8. Observação recebe abaixo do conteúdo anterior o mesmo bloco compacto usado no
   Funil. Marcadores não mudam; não basta o marcador se os campos divergem.
9. Canal/anúncio são capturados nos GETs existentes, usando `Anuncio` somente
   para Meta Ads. A chave `atribuicao_monitoramento` no contexto e no snapshot
   preserva evidência por conversa. O painel não consulta serviços externos.
   Filtros e relatórios estão descritos em `monitoramento_fireads_filtros_relatorios.md`.

## Prazos e recuperação

Cada consulta, update ou append tem 300s próprios de HTTP. Redirects compartilham
esse prazo e não repetem POST automaticamente. A conexão mantém limite de 4s.
Consulta inicial pendente espera até 300s na fila; ao reservar sob advisory lock,
o prazo é renovado para 330s: 300s HTTP e 30s de margem. O indicador consome essa
margem; uma parte é preservada para persistir o resultado. Consulta já expirada
não ganha tentativas ilimitadas. A entrega tem reserva de 960s para os GETs/POSTs
sequenciais; o lease Funil tem no mínimo 960s mesmo com configuração antiga menor.

Novos snapshots 5 congelam destino, origem, campos e payload compartilhado. Um
retry não escolhe outra linha recém-criada nem recalcula campanha. Reconhecer
resposta perdida/escrita parcial pelo marcador e campos congelados. Dashboard
sent com Funil pendente retoma só Funil. Snapshots 1–4 já salvos conservam conteúdo
e canal. Entregas concluídas não são reprocessadas. Erro/timeout GET nunca prova
ausência de cadastro.

Locks de sessão por contato serializam nossos workers durante preparação/escrita.
GET e POST não são atômicos em relação à FireAds ou à edição manual da planilha;
evitar reordenar/excluir registros durante o envio. A janela histórica de perda
da resposta do Funil permanece: a API não tem neste projeto reconciliação igual
à do dashboard. Não prometer ausência absoluta de duplicidade externa.

## Banco e implantação

**Não há migração SQL nova.** Reutiliza os JSONs e prazos existentes, sobre as
migrações já aplicadas da V1.14.0. Não executar setup/seeds nem converter dados.
Parar follow-up, flow, consulta-dash, Funil e webhook para atualizar o código;
executar check e collectstatic e retomar conforme `deploy/README.md`. Nenhuma alteração de .env,
dependências ou serviço systemd é exigida por esta revisão.

Não voltar ao worker V1.15.0 enquanto existirem snapshots 5 pendentes sem tratar
compatibilidade. A liberação de colunas do Web App já exigida para V1.15.0 continua.

## Validação

Testes unitários incluem coleta, relações, canais, recência, formatos de telefone,
turno, observações, indicador e orçamento HTTP. Integração usa PostgreSQL local
vazio `test_chatbot_fireads`, com HTTP/WhatsApp simulados; nunca credenciais reais.
As suites principais adicionais são:

```bash
python -B -m unittest tests.unit.test_fireads_entrega_telefone tests.unit.test_fireads_sincronizacao_coleta tests.unit.test_fireads_prioridade_destinatario tests.unit.test_coleta_abertura tests.unit.test_chat_fire_turno tests.unit.test_indicador_digitacao -q
python -B -m unittest tests.integration.test_entrega_fireads_primeiro_postgres tests.integration.test_coleta_abertura_postgres -q
```

## Arquivos completos

SHA-256 abaixo considera UTF-8 e quebras LF do conteúdo exibido.

## Passo 1 — `core/integrations/fireads/prazos.py`

SHA-256 (LF): `fb7bbe20eba76da199bd0af2f0e2ab6ba83dcf456ca6fe8536e09a426e87c901`

```python
"""Prazos compartilhados entre HTTP, reservas e recuperação da FireAds."""

HTTP_SEGUNDOS = 300
MARGEM_PERSISTENCIA_SEGUNDOS = 30
RESERVA_CONSULTA_SEGUNDOS = HTTP_SEGUNDOS + MARGEM_PERSISTENCIA_SEGUNDOS
# Uma entrega faz GET + POST. Uma decisão nova pode exigir um GET anterior.
RESERVA_ENTREGA_SEGUNDOS = 3 * HTTP_SEGUNDOS + 2 * MARGEM_PERSISTENCIA_SEGUNDOS
```

## Passo 2 — `core/integrations/fireads/aba_geral.py`

SHA-256 (LF): `c4b3ddaaa1872220f12bcbba43ea2f7b259f6d068e5909b8991f130c1d359776`

```python
"""Seleção e identidade do formulário da aba geral, sem HTTP ou SQL."""

from datetime import datetime, timezone

from .contrato import ErroFireAds, instante, localizar, normalizar, telefone

VERSAO_CONSULTA = 2
ORIGENS = {"google ads": "google", "meta ads": "meta", "organico site": "organico_site",
           "chat fire": "chat_fire", "organico": "organico"}
CANAIS_FORMULARIO = {chave for chave, valor in ORIGENS.items() if valor != 'organico'}
CANAIS_MANUAIS = {"indicacao", "lead franqueador"}
CAMPOS_IDENTIDADE = ("WhatsApp", "Data/Hora", "Canal", "Nome", "Email", "Para quem é")


def numero_linha(row):
    linha = row.get("_row")
    if type(linha) is not int or linha < 2:
        raise ErroFireAds("Linha de destino inválida")
    return linha


def mais_recente(rows, fuso=None):
    """Datas válidas precedem inválidas; empates usam a posição física da linha."""
    if not rows:
        return None
    return max(rows, key=lambda row: (
        instante(row.get("Data/Hora"), fuso or "America/Sao_Paulo")
        or datetime.min.replace(tzinfo=timezone.utc),
        numero_linha(row),
    ))


def selecionar_registro(rows, numero, fuso=None):
    encontrados = localizar(rows, numero, "WhatsApp", incluir_equivalentes=True)
    elegiveis = [r for r in encontrados if normalizar(r.get("Canal")) in CANAIS_FORMULARIO]
    return mais_recente(elegiveis, fuso), encontrados


def selecionar_entrega(rows, numero, fuso=None):
    """Só o telefone identifica; canais manuais nunca são alvo de escrita.

    Canal desconhecido não é prova de ausência: exige configuração, sem criar
    duplicata nem atribuir um código comercial inventado.
    """
    encontrados = localizar(rows, numero, "WhatsApp", incluir_equivalentes=True)
    candidatos = [r for r in encontrados if normalizar(r.get("Canal")) in CANAIS_FORMULARIO]
    row = mais_recente(candidatos, fuso)
    if row is None and any(normalizar(r.get('Canal')) not in set(ORIGENS) | CANAIS_MANUAIS for r in encontrados):
        raise ErroFireAds("Canal da linha mais recente não reconhecido; configurar antes de enviar")
    return row


def referencia_registro(row, aba, fuso=None):
    if row is None:
        return None
    data = instante(row.get("Data/Hora"), fuso or "America/Sao_Paulo")
    return {
        "aba": aba, "linha": numero_linha(row),
        "telefone": telefone(row.get("WhatsApp")),
        "campos": {campo: row.get(campo) for campo in CAMPOS_IDENTIDADE},
        "data_interpretada": data.isoformat() if data else None,
        "criterio_recencia": "data_linha" if data else "linha_sem_data_valida",
    }


def relocalizar(rows, referencia, aba):
    """Não troca um formulário já escolhido por um novo cadastro do mesmo telefone."""
    if referencia.get("aba") != aba:
        raise ErroFireAds("Aba do registro selecionado diverge do envio")
    campos = referencia.get("campos")
    if not isinstance(campos, dict) or set(campos) != set(CAMPOS_IDENTIDADE):
        raise ErroFireAds("Referência do formulário incompleta")
    candidatos = [r for r in rows if all(r.get(c) == campos[c] for c in CAMPOS_IDENTIDADE)]
    if len(candidatos) == 1:
        return candidatos[0]
    # Linhas integralmente idênticas não possuem identidade estável na API.
    # A posição original resolve apenas enquanto continua apontando para esse conteúdo.
    original = [r for r in candidatos if numero_linha(r) == referencia.get("linha")]
    if len(original) == 1:
        return original[0]
    raise ErroFireAds("Registro selecionado ausente ou deslocado sem identidade única")


def configuracao_compativel(entrada, abertura):
    """A migração fornece a ponte de configuração para resultados legados concluídos."""
    if entrada.get("versao") == VERSAO_CONSULTA:
        config = entrada
    elif "versao" not in entrada:
        config = entrada.get("compatibilidade_aba_geral") or {}
        if config.get("valida") is not True:
            return False
    else:
        return False
    return all(config.get(campo) == abertura.get(campo) for campo in ("url", "aba", "fuso"))
```

## Passo 3 — `core/integrations/fireads/cliente.py`

SHA-256 (LF): `029dbd51a6807a7b4c3ca456bd2805ad8e8557afed36f869f4b8545d5cfc08bb`

```python
"""GET e POST limitados ao Web App; nenhuma escrita durante importação."""

import time
from urllib.parse import urlparse
import requests
from .contrato import ErroFireAds, normalizar


class TelefoneDuplicadoFireAds(ErroFireAds):
    """Recusa inequívoca do append; não representa timeout ou falha genérica."""


def _duplicidade(body):
    return isinstance(body, dict) and body.get('success') is False and (
        body.get('code') == 'DUPLICATE_PHONE' or normalizar(body.get('error')) in {
            'telefone ja cadastrado', 'telefone duplicado', 'numero de telefone ja cadastrado',
        })


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
    def __init__(self, url, *, segundos=25, timeout_leitura=8, session=None, por_operacao=False):
        """Leitura=None usa o prazo restante; padrões das escritas são preservados."""
        self.url = validar_url(url)
        self.segundos = segundos
        self.por_operacao = por_operacao
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
        if _duplicidade(body):
            raise TelefoneDuplicadoFireAds('Criação recusada por telefone duplicado')
        if not isinstance(body, dict) or body.get("success") is not True:
            if isinstance(body, dict) and str(body.get('error') or '').startswith('Coluna não editável:'):
                raise ErroFireAds('Web App FireAds não autoriza as colunas; atualizar EDITABLE_COLUMNS')
            raise ErroFireAds("FireAds recusou a operação")
        return body

    def consultar(self, aba):
        self._iniciar_operacao()
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
        self._iniciar_operacao()
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
        try:
            result = self._json(self._request("POST", self.url, json=payload))
        except requests.HTTPError as exc:
            if row is None and exc.response is not None and exc.response.status_code in (400, 409):
                try:
                    recusada = _duplicidade(exc.response.json())
                except ValueError:
                    recusada = False
                if recusada:
                    raise TelefoneDuplicadoFireAds('Criação recusada por telefone duplicado') from None
            raise
        if result.get("aba") != aba:
            raise ErroFireAds("Recibo de outra aba")
        if row is None:
            if result.get("inserted") != 1:
                raise ErroFireAds("Cadastro sem confirmação de uma linha")
        elif (result.get("row") != row or not isinstance(result.get("updated"), list)
              or not set(payload['updates']) <= set(result['updated'])):
            raise ErroFireAds("Update sem confirmação da linha/coluna")
        return result

    def _iniciar_operacao(self):
        # GET e POST têm orçamentos próprios. Redirects não reiniciam o prazo.
        if self.por_operacao:
            self.deadline = None if self.segundos is None else time.monotonic() + self.segundos
```

## Passo 4 — `core/integrations/fireads/coleta_abertura.py`

SHA-256 (LF): `b8b03c8e3f26de527a2743a7a19ed2c4e7377f946db01048cefb51f74ff4eba7`

```python
"""Completa ausências a partir do registro mais recente do mesmo telefone."""

from copy import deepcopy
from core.validacoes.coleta_abertura import CAMPOS, campo, aceito, completo, normalizar
from core.integrations.fireads.aba_geral import ORIGENS, selecionar_entrega, referencia_registro, mais_recente
from core.integrations.fireads.atribuicao import CHAVE, capturar
from core.integrations.fireads.contrato import localizar
from core.integrations.fireads.extratores import extrair_nome, extrair_email

COLUNAS = {'nome': 'Nome', 'email': 'Email', 'destinatario': 'Para quem é', 'turno': 'Período preferido'}


def campos_registro(row):
    campos = {c: campo([row.get(coluna) or ''], c, 'dashboard') for c, coluna in COLUNAS.items()}
    # Campos estruturados preservam os extratores FireAds existentes. A validação
    # de texto livre do WhatsApp não é imposta novamente ao formulário externo.
    for tipo, extrator in (('nome', extrair_nome), ('email', extrair_email)):
        bruto = str(row.get(COLUNAS[tipo]) or '').strip()
        valor = extrator(bruto)
        if valor:
            identidade = normalizar(bruto.split('|', 1)[0]) if tipo == 'nome' else valor.casefold()
            campos[tipo].update(status='aceito', valor=valor, identidade=identidade, bruto=bruto)
    return campos


def compativel(conhecidos, candidatos, *, campos=CAMPOS):
    for c in campos:
        a, b = conhecidos[c], candidatos[c]
        if a['status'] != 'aceito':
            continue
        if b['status'] != 'aceito':
            return False
        if c == 'nome':
            # Mesmo nome extraído, mas sobrenomes explícitos divergentes bloqueiam.
            ca, cb = a['identidade'].split(), b['identidade'].split()
            somente_nome = a['identidade'] == normalizar(a['valor'])
            if ca != cb and not (somente_nome and cb[:len(ca)] == ca):
                return False
        elif c == 'destinatario' and a['identidade'] == 'dependente' and b['valor']['dependente']:
            continue
        elif a['identidade'] != b['identidade']:
            return False
    return True


def selecionar_para_complementacao(rows, estado, fuso=None):
    """Recebe somente linhas elegíveis do telefone; outros campos não filtram."""
    return mais_recente(rows, fuso)


def interpretar_parcial(rows, numero, fuso, aba, estado):
    resultado = deepcopy(estado)
    row = selecionar_entrega(rows, numero, fuso)
    if row is not None:
        for c, recebido in campos_registro(row).items():
            if c == 'turno' and not resultado.get('coletar_turno'):
                continue
            if not aceito(resultado, c) and recebido['status'] == 'aceito':
                resultado['campos'][c] = recebido
        resultado['formulario_identificado'] = True
    return {'resultado': 'importado' if completo(resultado) else ('incompleto' if row else 'ausente'),
            'origem': ORIGENS[normalizar(row.get('Canal'))] if row else 'organico',
            'referencia': referencia_registro(row, aba, fuso), 'coleta': resultado,
            CHAVE: capturar(row, aba, fuso),
            'motivo': None if row else 'sem_registro_elegivel', 'dados_titular': {}}
```

## Passo 5 — `core/integrations/fireads/sincronizacao_coleta.py`

SHA-256 (LF): `2712b075a7817bd557f8dd2936d77cd530c3a7344e9cf114cd4932759e9b2433`

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
    if snapshot.get('versao') != 5:
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
    if snapshot.get('versao') != 5:
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

## Passo 6 — `core/repositories/fireads/envios.py`

SHA-256 (LF): `14eecfaf7f2d6eee55468df0d12c11c6ac69794f0c6013d2d1f2875db2815fff`

```python
"""Fila independente do dashboard e retrato do conteúdo aceito para o Funil."""

from psycopg.types.json import Jsonb
import hashlib
from core.integrations.fireads.contrato import CANAIS
from core.integrations.fireads.contrato import identidade_telefone
from core.integrations.fireads.prazos import RESERVA_ENTREGA_SEGUNDOS
from core.integrations.fireads.atribuicao import CHAVE


def buscar_configuracao_entrega(dados, cursor):
    cursor.execute("""SELECT i.url_dashbord,i.aba_destino,i.fuso_formularios
        FROM chatbot.integracao_fireads i JOIN chatbot.unidade u USING (id_unidade)
        WHERE i.id_integracao_fireads=%s AND i.id_unidade=%s
          AND i.integracao_ativa AND i.contrato_validado AND u.status_pagamento IS TRUE""",
                   (dados['contexto_fireads']['id_integracao'], dados['id_unidade']))
    return cursor.fetchone()


def buscar_status(id_conversa, cursor):
    cursor.execute('SELECT status FROM chatbot.envios_dash WHERE id_conversa=%s', (id_conversa,))
    row = cursor.fetchone()
    return row[0] if row else None


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
    entrega = dados.get('entrega_fireads')
    if entrega is not None:
        if (entrega['url'], entrega['aba'], entrega['fuso']) != tuple(config[1:]):
            raise ValueError('Configuração FireAds mudou durante a preparação')
        snapshot.update(versao=5, destino=entrega['destino'])
        if estado.get(CHAVE):
            snapshot[CHAVE] = estado[CHAVE]
        snapshot.setdefault('campos_dashboard', {})
        snapshot.setdefault('identidade_coleta', {})
        snapshot.setdefault('coletar_turno', False)
        snapshot.setdefault('para_quem', 'Para dependente' if dados['status_dependente'] else 'Para mim')
        cursor.execute("""UPDATE chatbot.conversa SET origem_fireads=%s,
            contexto_fireads=contexto_fireads || %s WHERE id_conversa=%s""",
            (origem, Jsonb({'origem': origem, 'referencia_entrega': entrega['destino'],
                           'canal_confirmado_entrega': True,
                           **({CHAVE: estado[CHAVE]} if estado.get(CHAVE) else {})}), dados['id_conversa']))
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


def chave_contato(id_integracao, numero):
    identidade = f'fireads:{id_integracao}:{identidade_telefone(numero)}'
    return int.from_bytes(hashlib.sha256(identidade.encode()).digest()[:8], 'big', signed=True)


def liberar_contato(chave, cursor):
    cursor.execute("SELECT pg_advisory_unlock(%s)", (chave,))


def reservar(cursor, id_conversa=None):
    cursor.execute(
        """WITH proximo AS (
        SELECT d.id_envio_dash FROM chatbot.envios_dash d
        JOIN chatbot.conversa c ON c.id_conversa=d.id_conversa
        JOIN chatbot.integracao_fireads i USING (id_integracao_fireads)
        JOIN chatbot.integracao_funil_unidade f ON f.id_unidade=d.id_unidade
        JOIN chatbot.unidade u ON u.id_unidade=d.id_unidade
        WHERE i.integracao_ativa AND i.contrato_validado AND f.integracao_ativa AND f.widget_ativo
          AND (c.lead_no_funil IS TRUE OR EXISTS (
              SELECT 1 FROM chatbot.funil_envios fe WHERE fe.id_conversa=d.id_conversa
              AND fe.snapshot IS NOT NULL))
          AND (%s::bigint IS NULL OR d.id_conversa=%s)
          AND u.status_pagamento IS TRUE
          AND ((d.status='pending' AND d.next_attempt_at <= clock_timestamp())
            OR (d.status='processing' AND d.processing_started_at < clock_timestamp()-(%s * INTERVAL '1 second')))
        ORDER BY d.attempt_count,d.id_envio_dash FOR UPDATE OF d SKIP LOCKED LIMIT 1
    ) UPDATE chatbot.envios_dash d SET status='processing',attempt_count=attempt_count+1,
        processing_started_at=clock_timestamp(),atualizado_em=clock_timestamp()
      FROM proximo p WHERE d.id_envio_dash=p.id_envio_dash
      RETURNING d.id_envio_dash,d.id_conversa,d.id_integracao_fireads,d.attempt_count,d.snapshot""",
        (id_conversa, id_conversa, RESERVA_ENTREGA_SEGUNDOS),
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
          AND d.processing_started_at > clock_timestamp()-(%s * INTERVAL '1 second')
          AND i.integracao_ativa AND i.contrato_validado AND f.integracao_ativa AND f.widget_ativo
          AND i.url_dashbord=d.snapshot->>'url' AND i.aba_destino=d.snapshot->>'aba'
        FOR UPDATE OF d""",
        (envio["id"], envio["tentativa"], RESERVA_ENTREGA_SEGUNDOS),
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


def registrar_duplicidade(envio, cursor, *, destino=None):
    """Somente append novo recusado pode passar a atualizar um Orgânico existente."""
    conferir_posse(envio, cursor)
    snapshot = envio['snapshot']
    if (snapshot.get('versao') != 5 or snapshot.get('origem') != 'organico'
            or (snapshot.get('destino') or {}).get('tipo') != 'create'):
        raise ValueError('Entrega não permite alternativa por duplicidade')
    if destino is not None and not snapshot.get('append_recusado_duplicidade'):
        raise ValueError('Não houve recusa explícita de duplicidade')
    campos = {'append_recusado_duplicidade': True}
    if destino is not None:
        campos['destino'] = destino
    cursor.execute('''UPDATE chatbot.envios_dash SET snapshot=snapshot || %s
        WHERE id_envio_dash=%s AND status='processing' AND attempt_count=%s
        RETURNING snapshot''', (Jsonb(campos), envio['id'], envio['tentativa']))
    row = cursor.fetchone()
    if row is None:
        raise ValueError('Reserva FireAds perdida')
    envio['snapshot'] = row[0]
    return row[0]
```

## Passo 7 — `core/repositories/fireads/pendencias.py`

SHA-256 (LF): `742eceb878441507170df7dba1af3902c22c859f52c698d7708d83a2e295e66d`

```python
"""Fila durável de consultas; SQL sem HTTP e sem controle de transações."""

from psycopg.types.json import Jsonb
from core.integrations.fireads.aba_geral import VERSAO_CONSULTA
from core.integrations.fireads.prazos import RESERVA_CONSULTA_SEGUNDOS


def solicitar(abertura, id_conversa, numero, cursor):
    """Retorna se criou a solicitação; retry não altera entrada nem prazo."""
    entrada = {
        "url": abertura["url"],
        "aba": abertura["aba"],
        "versao": VERSAO_CONSULTA,
        "fuso": abertura["fuso"],
        "numero": numero,
    }
    if abertura.get("coleta") is not None:
        entrada["coleta"] = abertura["coleta"]
    cursor.execute(
        """INSERT INTO chatbot.consulta_fireads
        (id_unidade,id_integracao_fireads,id_conversa,entrada)
        VALUES (%s,%s,%s,%s) ON CONFLICT (id_conversa) DO NOTHING""",
        (
            abertura["id_unidade"],
            abertura["id_integracao"],
            id_conversa,
            Jsonb(entrada),
        ),
    )
    return cursor.rowcount == 1


def buscar(id_conversa, cursor):
    """O fluxo segura esta linha somente durante a decisão local, nunca no HTTP."""
    cursor.execute(
        """SELECT id_consulta,id_integracao_fireads,status,dados,entrada,
                  prazo_final <= clock_timestamp(),aplicacao
        FROM chatbot.consulta_fireads WHERE id_conversa=%s FOR UPDATE""",
        (id_conversa,),
    )
    row = cursor.fetchone()
    if row is None:
        return None
    return dict(
        zip(
            (
                "id_consulta",
                "id_integracao",
                "status",
                "dados",
                "entrada",
                "expirada",
                "aplicacao",
            ),
            row,
        )
    )


def concluir_sem_http(id_consulta, decisao, cursor):
    """Timeout ou cancelamento vence só pendências; resultado concluído é imutável."""
    cursor.execute(
        """UPDATE chatbot.consulta_fireads SET status='concluida',
          consulta_concluida=TRUE,resultado=%s,dados=%s,
          consultado_em=clock_timestamp(),atualizado_em=clock_timestamp(),
          reserva_ate=NULL,processing_started_at=NULL,
          versao_reserva=versao_reserva+1,ultimo_erro=%s
        WHERE id_consulta=%s AND status<>'concluida'""",
        (
            decisao["resultado"],
            Jsonb({"decisao": decisao, "fontes": {}}),
            decisao.get("motivo"),
            id_consulta,
        ),
    )
    return cursor.rowcount == 1


def marcar_aplicada(id_consulta, id_conversa, decisao, cursor):
    cursor.execute(
        """UPDATE chatbot.consulta_fireads SET aplicacao=%s,
        aplicado_em=clock_timestamp(),atualizado_em=clock_timestamp()
        WHERE id_consulta=%s AND id_conversa=%s AND status='concluida'
          AND aplicado_em IS NULL""",
        (Jsonb(decisao), id_consulta, id_conversa),
    )
    if cursor.rowcount != 1:
        raise ValueError("Consulta já aplicada ou não pertence à conversa")


def expirar(cursor):
    """Também limpa pendências abandonadas; unidades suspensas ficam preservadas."""
    cursor.execute("""UPDATE chatbot.consulta_fireads q SET status='concluida',
          consulta_concluida=TRUE,resultado='erro',
          dados=jsonb_build_object('decisao',jsonb_build_object(
            'resultado','erro','origem','organico','motivo','tempo_limite_300s',
            'dados_titular','{}'::jsonb),'fontes','{}'::jsonb),
          consultado_em=clock_timestamp(),atualizado_em=clock_timestamp(),
          reserva_ate=NULL,processing_started_at=NULL,
          versao_reserva=versao_reserva+1,ultimo_erro='tempo_limite_300s'
        FROM chatbot.unidade u WHERE u.id_unidade=q.id_unidade
          AND u.status_pagamento IS TRUE AND q.status<>'concluida'
          AND q.prazo_final<=clock_timestamp()""")
    return cursor.rowcount


def _chave(id_consulta):
    return f"chatbot:consulta_fireads:{id_consulta}"


def liberar_reserva(id_consulta, cursor):
    """A sessão mantém o advisory lock durante HTTP; close também o libera."""
    cursor.execute(
        "SELECT pg_advisory_unlock(hashtextextended(%s,0))", (_chave(id_consulta),)
    )
    return cursor.fetchone()[0]


def reservar(cursor):
    """Reserva exclusiva: 300s de HTTP e margem para indicador/persistência.

    A consulta de candidatos não adquire advisory locks. Cada lock é solicitado
    explicitamente para um único ID, evitando locks extras por avaliação do SQL.
    O orquestrador confirma a reserva antes de HTTP e mantém a conexão ociosa.
    """
    cursor.execute("""SELECT q.id_consulta FROM chatbot.consulta_fireads q
        JOIN chatbot.conversa c ON c.id_conversa=q.id_conversa
        JOIN chatbot.unidade u ON u.id_unidade=q.id_unidade
        JOIN chatbot.integracao_fireads i ON i.id_integracao_fireads=q.id_integracao_fireads
        WHERE q.status IN ('pendente','processando') AND q.prazo_final>clock_timestamp()
          AND c.status_ativa AND c.finalizou_em IS NULL AND c.id_etapa_atual IS NULL
          AND c.contexto_fireads IS NULL AND u.status_pagamento IS TRUE
          AND i.integracao_ativa AND i.contrato_validado
        ORDER BY q.solicitado_em,q.id_consulta LIMIT 100""")
    candidatos = [row[0] for row in cursor.fetchall()]
    for ident in candidatos:
        cursor.execute(
            "SELECT pg_try_advisory_lock(hashtextextended(%s,0))", (_chave(ident),)
        )
        if not cursor.fetchone()[0]:
            continue
        cursor.execute(
            """UPDATE chatbot.consulta_fireads q SET status='processando',
              tentativas=tentativas+1,versao_reserva=versao_reserva+1,
              processing_started_at=clock_timestamp(),
              prazo_final=clock_timestamp()+(%s * INTERVAL '1 second'),
              reserva_ate=clock_timestamp()+(%s * INTERVAL '1 second'),
              atualizado_em=clock_timestamp()
            FROM chatbot.conversa c,chatbot.unidade u,chatbot.integracao_fireads i
            WHERE q.id_consulta=%s AND q.status IN ('pendente','processando')
              AND q.prazo_final>clock_timestamp() AND c.id_conversa=q.id_conversa
              AND c.status_ativa AND c.finalizou_em IS NULL AND c.id_etapa_atual IS NULL
              AND c.contexto_fireads IS NULL AND u.id_unidade=q.id_unidade
              AND u.status_pagamento IS TRUE AND i.id_integracao_fireads=q.id_integracao_fireads
              AND i.integracao_ativa AND i.contrato_validado
              AND i.url_dashbord=q.entrada->>'url'
              AND i.aba_destino=q.entrada->>'aba' AND q.entrada->>'versao'='2'
              AND i.fuso_formularios IS NOT DISTINCT FROM q.entrada->>'fuso'
            RETURNING q.id_consulta,q.id_conversa,q.versao_reserva,q.entrada,
                      EXTRACT(EPOCH FROM q.prazo_final-clock_timestamp())""",
            (RESERVA_CONSULTA_SEGUNDOS, RESERVA_CONSULTA_SEGUNDOS, ident),
        )
        row = cursor.fetchone()
        if row is not None:
            return dict(
                zip(
                    ("id_consulta", "id_conversa", "versao", "entrada", "restante"), row
                )
            )
        liberar_reserva(ident, cursor)
    return None


def buscar_mensagem_aguardando(reserva, cursor):
    """Entrada da consulta reservada, para o indicador opcional, sem travar linhas."""
    cursor.execute(
        """SELECT f.id_mensagem,f.id_phone_unidade,f.id_hash_msg
        FROM chatbot.consulta_fireads q
        JOIN chatbot.conversa c ON c.id_conversa=q.id_conversa
        JOIN chatbot.unidade u ON u.id_unidade=q.id_unidade AND u.id_unidade=c.id_unidade
        JOIN chatbot.integracao_fireads i ON i.id_integracao_fireads=q.id_integracao_fireads
        JOIN chatbot.fila_mensagens f ON f.id_conversa=c.id_conversa
          AND f.id_phone_unidade=u.phone_number_id
          AND f.cliente_telefone=q.entrada->>'numero'
        WHERE q.id_consulta=%s AND q.versao_reserva=%s AND q.status='processando'
          AND q.reserva_ate>clock_timestamp() AND q.prazo_final>clock_timestamp()
          AND c.status_ativa AND c.finalizou_em IS NULL AND c.id_etapa_atual IS NULL
          AND c.contexto_fireads IS NULL AND u.status_pagamento IS TRUE
          AND i.integracao_ativa AND i.contrato_validado
          AND i.url_dashbord=q.entrada->>'url'
          AND i.aba_destino=q.entrada->>'aba' AND q.entrada->>'versao'='2'
          AND i.fuso_formularios IS NOT DISTINCT FROM q.entrada->>'fuso'
          AND f.status IN ('pending','processing')
          AND NOT EXISTS (SELECT 1 FROM chatbot.historico_mensagens h
                          WHERE h.id_conversa=c.id_conversa AND h.quem_enviou='bot')
        ORDER BY f.received_data_hora,f.id_mensagem LIMIT 1""",
        (reserva["id_consulta"], reserva["versao"]),
    )
    row = cursor.fetchone()
    return dict(zip(("id_mensagem", "id_phone_unidade", "id_hash"), row)) if row else None


def concluir(reserva, resultado, cursor):
    """A gravação única inclui os registros e a decisão, sem resultados parciais."""
    decisao = resultado["decisao"]
    cursor.execute(
        """UPDATE chatbot.consulta_fireads q SET status='concluida',
          consulta_concluida=TRUE,resultado=%s,dados=%s,
          consultado_em=clock_timestamp(),atualizado_em=clock_timestamp(),
          reserva_ate=NULL,processing_started_at=NULL,ultimo_erro=%s
        FROM chatbot.conversa c,chatbot.unidade u,chatbot.integracao_fireads i
        WHERE q.id_consulta=%s AND q.versao_reserva=%s AND q.status='processando'
          AND q.reserva_ate>clock_timestamp() AND q.prazo_final>clock_timestamp()
          AND c.id_conversa=q.id_conversa AND c.status_ativa AND c.finalizou_em IS NULL
          AND c.id_etapa_atual IS NULL AND c.contexto_fireads IS NULL
          AND u.id_unidade=q.id_unidade AND u.status_pagamento IS TRUE
          AND i.id_integracao_fireads=q.id_integracao_fireads AND i.integracao_ativa
          AND i.url_dashbord=q.entrada->>'url'
          AND i.aba_destino=q.entrada->>'aba' AND q.entrada->>'versao'='2'
          AND i.contrato_validado
          AND i.fuso_formularios IS NOT DISTINCT FROM q.entrada->>'fuso'""",
        (
            decisao["resultado"],
            Jsonb(resultado),
            decisao.get("motivo") if decisao["resultado"] == "erro" else None,
            reserva["id_consulta"],
            reserva["versao"],
        ),
    )
    return cursor.rowcount == 1
```

## Passo 8 — `workers/worker_consulta_dash/consulta_worker.py`

SHA-256 (LF): `89de2f7c0cc7e3981b3a2129040595d8e863b3cd0d7866808bce51e6e9a09175`

```python
"""Orquestra reservas duráveis e sinaliza a espera; não envia respostas nem muda etapas."""

import logging
import time

from core.database.connection_aws import get_conn
from core.integrations.whatsapp.pywa_functions.digitacao import indicar_digitacao
from core.integrations.fireads.prazos import HTTP_SEGUNDOS, MARGEM_PERSISTENCIA_SEGUNDOS
from core.repositories.fireads import pendencias
from workers.worker_consulta_dash.consulta import consultar

logger = logging.getLogger("worker.consulta_dash")
INTERVALO_OCIOSO_SEGUNDOS = 2


def executar_ciclo():
    """Uma consulta por ciclo, com conexão sem transação aberta durante o HTTP."""
    conn = None
    reserva = None
    try:
        conn = get_conn(application_name="worker_consulta_dash", connect_timeout=5)
        cursor = conn.cursor()
        pendencias.expirar(cursor)
        conn.commit()
        reserva = pendencias.reservar(cursor)
        inicio_reserva = time.monotonic()
        conn.commit()
        if reserva is None:
            return False
        logger.info("consulta_dash_iniciada | consulta=%s conversa=%s tentativa=%s",
                    reserva["id_consulta"], reserva["id_conversa"], reserva["versao"])
        mensagem = pendencias.buscar_mensagem_aguardando(reserva, cursor)
        conn.commit()
        if mensagem is not None:
            indicar_digitacao(
                mensagem["id_phone_unidade"], mensagem["id_hash"],
                id_mensagem=mensagem["id_mensagem"], id_conversa=reserva["id_conversa"],
            )
        # A espera na fila não consome os 300s do HTTP. A reserva foi renovada
        # sob advisory lock; margem separada permite confirmar o resultado.
        reserva["restante"] = min(HTTP_SEGUNDOS, max(
            0.0, float(reserva["restante"]) - (time.monotonic() - inicio_reserva)
            - MARGEM_PERSISTENCIA_SEGUNDOS / 2,
        ))
        resultado = consultar(reserva)
        gravado = pendencias.concluir(reserva, resultado, cursor)
        # Se o orçamento terminou durante a chamada, persistir o timeout também
        # sem depender de um novo ciclo do worker de atendimento.
        pendencias.expirar(cursor)
        conn.commit()
        logger.info("consulta_dash_finalizada | consulta=%s resultado=%s confirmado=%s",
                    reserva["id_consulta"], resultado["decisao"]["resultado"], gravado)
        return True
    except Exception:
        if conn is not None and not conn.closed:
            conn.rollback()
        raise
    finally:
        if conn is not None:
            try:
                if reserva is not None and not conn.closed:
                    pendencias.liberar_reserva(reserva["id_consulta"], conn.cursor())
                    conn.commit()
            finally:
                # Mesmo falha no unlock não deixa uma sessão reutilizável com lock.
                conn.close()


def consulta_worker():
    while True:
        if not executar_ciclo():
            time.sleep(INTERVALO_OCIOSO_SEGUNDOS)
```

## Passo 9 — `workers/worker_flow/coleta_abertura.py`

SHA-256 (LF): `58dd60dffd8c1e4edacac1bf1bd67e038196c96af8724226b9443ee05664c431`

```python
"""Coordena a coleta da primeira mensagem, sem HTTP, commits ou envio WhatsApp."""

from copy import deepcopy
from core.validacoes.coleta_abertura import criar_contexto, completo, aceito, valor
from core.repositories.atendimento.coleta_abertura import salvar, importar
from core.repositories.atendimento.followup import proteger_conversa
from core.repositories.fireads.consulta import proteger_mensagem_abertura, aplicar_decisao
from core.repositories.fireads import pendencias
from core.integrations.fireads.aba_geral import configuracao_compativel
from workers.worker_consulta_dash.resultado import decisao_organica
from workers.worker_flow.suporte.consultas_fireads import ConsultaFireAdsPendente


def anexar(contexto, estado, fireads=None):
    novo = dict(contexto, contexto_coleta=estado)
    if fireads is not None:
        novo['contexto_fireads'] = fireads
    if aceito(estado, 'destinatario'):
        novo['conversa'] = dict(novo['conversa'], status_dependente=valor(estado, 'destinatario')['dependente'])
    return novo


def preparar(contexto, mensagem, lock_version, cursor, abertura, consulta):
    cid = contexto['conversa']['id_conversa']
    estado = abertura.get('coleta')
    if estado and estado.get('status') == 'pronto':
        return anexar(contexto, estado, abertura.get('contexto'))
    proteger_conversa(cid, lock_version, cursor)
    proteger_mensagem_abertura(mensagem, cursor)
    if estado is None:
        estado = criar_contexto(cid, mensagem, coletar_turno=not abertura.get('link_agendamento'))
        estado['fireads_aplicavel'] = bool(abertura['aplicavel'])
        estado['formulario_identificado'] = bool(abertura['aplicavel'] and estado['rota_formulario_chat'])
        salvar(cid, estado, cursor)
    # Não substituir o primeiro formulário por outra mensagem enquanto espera.
    if estado['id_mensagem'] != mensagem['id_mensagem']:
        raise ConsultaFireAdsPendente('primeira_mensagem_ainda_pendente', consulta_nova=False)
    consulta_nova = False
    decisao = None
    if estado['fireads_aplicavel'] and not completo(estado):
        if consulta is None:
            consulta_nova = pendencias.solicitar(dict(abertura, coleta=estado), cid,
                                                 mensagem['cliente_telefone'], cursor)
            consulta = pendencias.buscar(cid, cursor)
        motivo = None
        if not abertura['aplicavel']:
            motivo = 'integracao_desativada'
        elif consulta['id_integracao'] != abertura['id_integracao'] or not configuracao_compativel(consulta['entrada'], abertura):
            motivo = 'configuracao_alterada'
        elif consulta['expirada'] and consulta['status'] != 'concluida':
            motivo = 'tempo_limite_300s'
        if motivo and consulta['status'] != 'concluida':
            pendencias.concluir_sem_http(consulta['id_consulta'], decisao_organica('erro', motivo), cursor)
            consulta = pendencias.buscar(cid, cursor)
        if consulta['status'] != 'concluida':
            estado['status'] = 'aguardando_consulta'
            salvar(cid, estado, cursor)
            raise ConsultaFireAdsPendente('aguardando_resultado', consulta_nova=consulta_nova)
        if consulta['aplicacao'] is not None:
            raise ValueError('Consulta aplicada sem coleta pronta')
        decisao = decisao_organica('erro', motivo) if motivo else deepcopy(consulta['dados']['decisao'])
        if decisao.get('coleta'):
            recebido = decisao['coleta']
            if recebido.get('id_conversa') != cid or recebido.get('id_mensagem') != estado['id_mensagem']:
                raise ValueError('Resultado da consulta não pertence à abertura')
            estado = recebido
        abertura = dict(abertura, id_integracao=consulta['id_integracao'])
    estado = importar(abertura, cid, estado, cursor)
    if not estado['fireads_aplicavel']:
        return anexar(contexto, estado)
    if decisao is None:
        # Sem consulta não há atribuição de campanha. A entrega resolve a origem
        # pela planilha antes de congelar as observações dos dois destinos.
        decisao = {'resultado': 'importado', 'origem': 'organico', 'referencia': None,
                   'motivo': 'canal_pendente_entrega'}
    decisao.pop('coleta', None)
    if decisao.get('resultado') == 'importado' and not completo(estado):
        decisao['resultado'] = 'incompleto'
        decisao['motivo'] = 'campo_pendente_apos_importacao'
    decisao['dados_titular'] = {c: valor(estado, c) for c in ('nome', 'email') if aceito(estado, c)}
    if aceito(estado, 'email'):
        decisao['dados_titular']['resultado_email'] = 'email_valido'
    if aceito(estado, 'destinatario'):
        decisao['status_dependente'] = valor(estado, 'destinatario')['dependente']
    decisao['coleta_parcial'] = True
    decisao = aplicar_decisao(abertura, cid, consulta['id_consulta'] if consulta else None, decisao, cursor)
    if consulta:
        pendencias.marcar_aplicada(consulta['id_consulta'], cid, decisao, cursor)
    return anexar(contexto, estado, decisao)
```

## Passo 10 — `workers/worker_funil/config.py`

SHA-256 (LF): `c30f5991dc02a6f176f6cc75ae4319da96894d7eab5e574e7f8155a6fc1caee7`

```python
"""Configuração operacional do worker de Funil."""

from core.config_env import env_bool, env_int
from core.integrations.fireads.prazos import RESERVA_ENTREGA_SEGUNDOS


FUNIL_WORKER_ENABLED = env_bool("FUNIL_WORKER_ENABLED", False)
FUNIL_INTERVALO_SEGUNDOS = env_int("FUNIL_INTERVALO_SEGUNDOS", 1800)
FUNIL_LIMITE_POR_CICLO = env_int("FUNIL_LIMITE_POR_CICLO", 100)
FUNIL_LEASE_SEGUNDOS = max(env_int("FUNIL_LEASE_SEGUNDOS", 900), RESERVA_ENTREGA_SEGUNDOS)
FUNIL_RETRY_LEAD_SEGUNDOS = env_int("FUNIL_RETRY_LEAD_SEGUNDOS", 3600)
FUNIL_HTTP_TIMEOUT = (
    env_int("FUNIL_HTTP_CONNECT_TIMEOUT_SECONDS", 10),
    env_int("FUNIL_HTTP_READ_TIMEOUT_SECONDS", 30),
)


def validar_configuracao_funil():
    valores_positivos = {
        "FUNIL_INTERVALO_SEGUNDOS": FUNIL_INTERVALO_SEGUNDOS,
        "FUNIL_LIMITE_POR_CICLO": FUNIL_LIMITE_POR_CICLO,
        "FUNIL_LEASE_SEGUNDOS": FUNIL_LEASE_SEGUNDOS,
        "FUNIL_RETRY_LEAD_SEGUNDOS": FUNIL_RETRY_LEAD_SEGUNDOS,
        "FUNIL_HTTP_CONNECT_TIMEOUT_SECONDS": FUNIL_HTTP_TIMEOUT[0],
        "FUNIL_HTTP_READ_TIMEOUT_SECONDS": FUNIL_HTTP_TIMEOUT[1],
    }

    invalidos = [nome for nome, valor in valores_positivos.items() if valor <= 0]
    if invalidos:
        raise RuntimeError(
            "Configurações do Funil devem ser positivas: "
            + ", ".join(invalidos)
        )
```

## Passo 11 — `workers/worker_funil/preparacao_fireads.py`

SHA-256 (LF): `1f1bcf87c12715cdcd85bcb82c0dac898955ac1768d7d189411fa1cc716fe30b`

```python
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
```

## Passo 12 — `workers/worker_funil/fireads.py`

SHA-256 (LF): `3646c0b0381e1d4d8b994b4ea11e757740b6321c7cc218c3983de76a860bb331`

```python
"""Entrega ao dashboard e reconciliação, antes de liberar o Funil."""

import logging
import psycopg
from core.integrations.fireads.cliente import ClienteFireAds, TelefoneDuplicadoFireAds
from core.integrations.fireads.prazos import HTTP_SEGUNDOS
from core.integrations.fireads.contrato import (
    CANAIS,
    ErroFireAds,
    telefone,
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
    chave_contato,
    buscar_status,
    registrar_duplicidade,
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
    if snapshot.get('versao') in {4, 5}:
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
    chave = chave_contato(envio['integracao'], snapshot['telefone'])
    bloqueado = False
    cliente = None
    try:
        bloqueado = bloquear_contato(chave, cursor)
        if not bloqueado:
            raise ErroFireAds("Outro envio deste contato está em andamento")
        conferir_posse(envio, cursor)
        conn.commit()
        cliente = ClienteFireAds(snapshot["url"], segundos=HTTP_SEGUNDOS,
                                 timeout_leitura=None, por_operacao=True)
        dados = cliente.consultar(snapshot["aba"])
        if not {"Nome", "Email", "WhatsApp", "Observação"} <= set(dados["headers"]):
            raise ErroFireAds("Cabeçalhos de destino incompletos")
        if snapshot.get('versao') in {3, 4, 5} and not {'Para quem é', 'Canal', 'Data/Hora'} <= set(dados['headers']):
            raise ErroFireAds('Cabeçalhos da coleta incompletos')
        if snapshot.get('versao') in {4, 5}:
            exigidos = set(snapshot['campos_dashboard'])
            turno = snapshot['identidade_coleta'].get('turno') or {}
            if turno.get('status') == 'aceito':
                exigidos.add('Período preferido')
            if not exigidos <= set(dados['headers']):
                raise ErroFireAds('Cabeçalhos de sincronização incompletos')
        if snapshot.get("versao") in {2, 3, 4, 5}:
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
        if (snapshot.get('append_recusado_duplicidade')
                and (snapshot.get('destino') or {}).get('tipo') == 'create'):
            from core.integrations.fireads.aba_geral import mais_recente, referencia_registro
            from core.integrations.fireads.contrato import normalizar
            encontrados = localizar(dados['rows'], snapshot['telefone'], 'WhatsApp', incluir_equivalentes=True)
            if not linhas_com_bloco(encontrados, bloco):
                organico = mais_recente([r for r in encontrados if normalizar(r.get('Canal')) == 'organico'], snapshot.get('fuso'))
                if organico is None:
                    raise ErroFireAds('Duplicidade recusada sem linha orgânica segura para atualizar')
                snapshot = registrar_duplicidade(envio, cursor, destino={
                    'tipo': 'update', 'referencia': referencia_registro(organico, snapshot['aba'], snapshot.get('fuso'))})
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
            try:
                recibo = cliente.enviar(snapshot["aba"], **operacao)
            except TelefoneDuplicadoFireAds:
                if 'dados' in operacao and snapshot.get('versao') == 5 and snapshot.get('origem') == 'organico':
                    registrar_duplicidade(envio, cursor)
                    conn.commit()
                # Nova reserva e leitura no próximo ciclo: não estender os 960s.
                raise
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


def processar_antes_funil(id_conversa, conn, cursor):
    """Sem FireAds é imediato; com FireAds só libera após confirmação durável."""
    status = buscar_status(id_conversa, cursor)
    conn.commit()
    if status is None or status == 'sent':
        return True
    envio = reservar(cursor, id_conversa=id_conversa)
    conn.commit()
    return processar(envio, conn, cursor) if envio else False


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

## Passo 13 — `workers/worker_funil/processamento.py`

SHA-256 (LF): `84705ec45252cd40003d232a51fc9194230ed33c49c3a1486ed277c99d5c8ed3`

```python
"""Processa uma reserva do Funil preservando a fronteira transacional."""

import json
from core.repositories.fireads.envios import congelar, bloquear_contato, liberar_contato, chave_contato
from core.repositories.funil import snapshots
from workers.worker_funil.preparacao_fireads import preparar_destino
from workers.worker_funil.fireads import processar_antes_funil
import logging

import psycopg

from core.integrations.funil.cliente import enviar_oportunidade
from core.integrations.funil.oportunidades import montar_payload_oportunidade
from core.repositories.funil.envios import (
    marcar_envio_como_concluido,
    registrar_falha_envio,
)
from core.repositories.funil.integracao import (
    buscar_integracao_funil_por_unidade,
)
from core.repositories.funil.leads import buscar_dados_lead_funil
from workers.worker_funil.config import (
    FUNIL_HTTP_TIMEOUT,
    FUNIL_LEASE_SEGUNDOS,
    FUNIL_RETRY_LEAD_SEGUNDOS,
)
from workers.worker_funil.exceptions import BancoFalhouAposEnvioFunil


logger = logging.getLogger("worker.funil.processamento")


def processar_envio_funil(envio, conn, cursor):
    """Envia um lead reservado; erros externos ficam para o próximo ciclo."""
    id_funil_envio = envio["id_funil_envio"]
    id_conversa = envio["id_conversa"]
    sucesso_externo = False
    contato_reservado = None

    try:
        snapshot = snapshots.buscar(id_conversa, cursor)
        if snapshot is None:
            dados_lead = buscar_dados_lead_funil(id_conversa, cursor)
            if dados_lead is None:
                raise ValueError("Conversa não está mais elegível ao Funil")
            integracao = buscar_integracao_funil_por_unidade(dados_lead["id_unidade"], cursor)
            _validar_integracao_ativa(integracao)
            if dados_lead.get('origem_fireads') is not None:
                chave = chave_contato(dados_lead['contexto_fireads']['id_integracao'],
                                      dados_lead['telefone_cliente'])
                if not bloquear_contato(chave, cursor):
                    raise ValueError('Outro envio deste contato está em andamento')
                contato_reservado = chave
            # A origem é resolvida antes de produzir as observações comuns.
            dados_lead = preparar_destino(dados_lead, conn, cursor)
            snapshots.conferir(envio, {'url_funil': integracao['link_api_carrossel']}, cursor,
                               lease_segundos=FUNIL_LEASE_SEGUNDOS)
            payload = montar_payload_oportunidade(dados_lead)
            payload, canal, url_funil = congelar(dados_lead, payload, integracao, cursor)
            snapshot = snapshots.salvar(id_conversa, payload, canal, url_funil, cursor)
        snapshots.conferir(envio, snapshot, cursor, lease_segundos=FUNIL_LEASE_SEGUNDOS)

        # O SELECT não deve manter uma transação aberta durante a chamada HTTP.
        conn.commit()

        if not processar_antes_funil(id_conversa, conn, cursor):
            registrar_falha_envio(id_funil_envio, 'Dashboard ainda pendente', cursor,
                                 retry_segundos=1800)
            conn.commit()
            logger.info('funil_aguardando_dashboard | id_conversa=%s', id_conversa)
            return False
        # HTTP pode ter consumido minutos: revalidar posse antes do POST Funil.
        snapshots.conferir(envio, snapshot, cursor, lease_segundos=FUNIL_LEASE_SEGUNDOS)
        conn.commit()

        resultado = enviar_oportunidade(
            link_api_carrossel=snapshot["url_funil"],
            codigo_canal_venda=snapshot["canal"],
            payload=snapshot["payload_funil"],
            timeout=FUNIL_HTTP_TIMEOUT,
        )
        sucesso_externo = True

        # JANELA RARA CONHECIDA:
        # o Funil já confirmou a oportunidade, mas o banco ainda não marcou
        # lead_no_funil. Se o processo ou o banco cair exatamente aqui, o lease
        # permitirá uma nova tentativa e poderá gerar duplicidade. A futura
        # reconciliação por título [C{id_conversa}] deve fechar essa janela.
        resposta_serializada = json.dumps(
            resultado["resposta"],
            ensure_ascii=False,
        )[:4000]
        marcar_envio_como_concluido(
            id_funil_envio,
            id_conversa,
            resposta_serializada,
            cursor,
        )
        conn.commit()

        logger.info(
            "funil_lead_enviado | acao=confirmar_envio "
            "id_funil_envio=%s id_conversa=%s tentativa=%s status_http=%s",
            id_funil_envio,
            id_conversa,
            envio["attempt_count"],
            resultado["status_http"],
        )
        return True

    except psycopg.Error:
        conn.rollback()
        if sucesso_externo:
            logger.critical(
                "funil_banco_falhou_apos_envio | acao=preservar_processing "
                "id_funil_envio=%s id_conversa=%s",
                id_funil_envio,
                id_conversa,
                exc_info=True,
            )
            raise BancoFalhouAposEnvioFunil(
                "Banco falhou depois de o Funil confirmar a oportunidade"
            )
        raise

    except Exception as exc:
        conn.rollback()

        if sucesso_externo:
            logger.critical(
                "funil_estado_local_falhou_apos_envio | "
                "acao=preservar_processing id_funil_envio=%s id_conversa=%s "
                "erro=%s",
                id_funil_envio,
                id_conversa,
                exc,
            )
            raise BancoFalhouAposEnvioFunil(
                "Estado local falhou depois de o Funil confirmar o lead"
            ) from exc

        try:
            registrado = registrar_falha_envio(
                id_funil_envio,
                exc,
                cursor,
                retry_segundos=FUNIL_RETRY_LEAD_SEGUNDOS,
            )
            if not registrado:
                raise RuntimeError(
                    "Não foi possível devolver o lead reservado para pending"
                )
            conn.commit()
        except Exception:
            conn.rollback()
            raise

        logger.exception(
            "funil_lead_falhou | acao=reagendar_proximo_ciclo "
            "id_funil_envio=%s id_conversa=%s tentativa=%s erro=%s",
            id_funil_envio,
            id_conversa,
            envio["attempt_count"],
            exc,
        )
        return False

    finally:
        if contato_reservado is not None and not conn.closed:
            liberar_contato(contato_reservado, cursor)
            conn.commit()


def _validar_integracao_ativa(integracao):
    if integracao is None:
        raise ValueError("Unidade sem configuração do Funil")
    if not integracao["integracao_ativa"]:
        raise ValueError("Integração do Funil está desativada para a unidade")
    if not integracao["widget_ativo"]:
        raise ValueError("Widget do Funil está desativado para a unidade")
```

## Passo 14 — `workers/worker_funil/funil_worker.py`

SHA-256 (LF): `7fcd26560a44e82b15292c5378609c4bd2f8aa74b2858cf15a8c44fdbb615eb9`

```python
"""Executa continuamente os ciclos de publicacao de leads no Funil."""

import logging
from workers.worker_funil.fireads import processar_lote
import time

import psycopg

from core.database.connection_aws import get_conn
from core.repositories.funil.envios import (
    reivindicar_proximo_envio,
    sincronizar_envios_elegiveis,
)
from workers.tratamento_erros_externos.erro_conexao import handle_erro_conexao
from workers.worker_funil.config import (
    FUNIL_INTERVALO_SEGUNDOS,
    FUNIL_LEASE_SEGUNDOS,
    FUNIL_LIMITE_POR_CICLO,
)
from workers.worker_funil.processamento import processar_envio_funil


logger = logging.getLogger("worker.funil")


def funil_worker():
    """Mantem o Funil ativo e recupera falhas operacionais esperadas."""
    logger.info(
        "funil_worker_iniciado | intervalo_segundos=%s limite_por_ciclo=%s",
        FUNIL_INTERVALO_SEGUNDOS,
        FUNIL_LIMITE_POR_CICLO,
    )
    retry_conexao = 5

    while True:
        try:
            logger.info("funil_ciclo_iniciando")
            resumo = executar_ciclo_funil()
            retry_conexao = 5

            logger.info(
                "funil_ciclo_concluido | acao=aguardar_proximo "
                "materializados=%s processados=%s enviados=%s falhas=%s "
                "limite_por_ciclo=%s aguardar=%ss",
                resumo["materializados"],
                resumo["processados"],
                resumo["enviados"],
                resumo["falhas"],
                FUNIL_LIMITE_POR_CICLO,
                FUNIL_INTERVALO_SEGUNDOS,
            )
            print("PROXIMO CICLO EM 30 MINUTOS")
            time.sleep(FUNIL_INTERVALO_SEGUNDOS)

        except KeyboardInterrupt:
            logger.info("funil_worker_interrompido | acao=encerrar")
            raise

        except psycopg.OperationalError as erro:
            # Falha esperada: o proprio worker aguarda e abre uma nova conexao.
            retry_conexao = handle_erro_conexao(
                erro,
                retry_conexao,
                incremento_retry=5,
            )


def executar_ciclo_funil():
    """Materializa e processa um lote; cada reserva é commitada isoladamente."""
    conn = None
    cursor = None
    resumo = {
        "materializados": 0,
        "processados": 0,
        "enviados": 0,
        "falhas": 0,
    }

    try:
        conn = get_conn(application_name="worker_funil")
        cursor = conn.cursor()

        resumo["materializados"] = sincronizar_envios_elegiveis(
            cursor,
            limite=FUNIL_LIMITE_POR_CICLO,
        )
        conn.commit()

        for _ in range(FUNIL_LIMITE_POR_CICLO):
            envio = reivindicar_proximo_envio(
                cursor,
                lease_segundos=FUNIL_LEASE_SEGUNDOS,
            )
            conn.commit()

            if envio is None:
                break

            resumo["processados"] += 1
            if processar_envio_funil(envio, conn, cursor):
                resumo["enviados"] += 1
            else:
                resumo["falhas"] += 1
            print("---------------PROXIMO ENVIO------------------")

        # Recupera também entregas históricas (Funil já enviado) e pendências
        # do dashboard cujo retry ficou pronto antes do retry do Funil.
        resumo['dash'] = processar_lote(conn, cursor, FUNIL_LIMITE_POR_CICLO)
        logger.info('dash_ciclo | %s', resumo['dash'])
        return resumo

    except Exception:
        if conn:
            conn.rollback()
        raise

    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()
```

## Passo 15 — `tests/unit/test_fireads_entrega_telefone.py`

SHA-256 (LF): `b794fd95461c4f55885e6bee5d4ef5a1d2a6288afd227d1c2925e77e39c98f2c`

```python
"""Telefone/recência e orçamento por operação, sem rede nem banco."""

import unittest
from unittest.mock import Mock, patch

from core.integrations.fireads.aba_geral import selecionar_entrega, referencia_registro
from core.integrations.fireads.cliente import ClienteFireAds
from core.integrations.fireads.contrato import ABA_DESTINO, ErroFireAds
from core.integrations.fireads.coleta_abertura import interpretar_parcial
from core.integrations.fireads.sincronizacao_coleta import preparar
from tests.unit.test_coleta_abertura import ROW, NUMERO
from tests.unit.test_fireads_sincronizacao_coleta import retrato, BLOCO, coleta


class TelefoneTests(unittest.TestCase):
    def test_nome_email_relacao_turno_nao_filtram_e_variantes_concorrem(self):
        for numero in (NUMERO, NUMERO[2:], 'p:+' + NUMERO, '(11) 99999-0002',
                       '551199990002', '(11) 9999-0002'):
            with self.subTest(numero=numero):
                recente = dict(ROW, _row=751, WhatsApp=numero, Nome='Ed',
                               Email='outro@example.com', Canal='Chat Fire',
                               **{'Para quem é': 'Meu filho', 'Período preferido': 'Manhã'})
                self.assertIs(selecionar_entrega([ROW, recente], NUMERO), recente)

    def test_excecao_manual_independe_da_quantidade_e_recencia(self):
        manuais = [dict(ROW, _row=900, Canal='Indicação'), dict(ROW, _row=901, Canal='Lead Franqueador')]
        self.assertIsNone(selecionar_entrega(manuais, NUMERO))
        self.assertIs(selecionar_entrega([ROW, *manuais], NUMERO), ROW)
        organico = dict(ROW, _row=902, Canal='Orgânico')
        self.assertIsNone(selecionar_entrega([*manuais, organico], NUMERO))
        self.assertIs(selecionar_entrega([ROW, *manuais, organico], NUMERO), ROW)

    def test_data_precede_linha_e_canal_desconhecido_nao_autoriza_criacao(self):
        novo = dict(ROW, _row=2, **{'Data/Hora': '22/10/2026 15:01'})
        self.assertIs(selecionar_entrega([ROW, novo], NUMERO), novo)
        self.assertIsNone(selecionar_entrega([ROW], '5511999990003'))
        for canal in ('', 'Canal novo'):
            with self.assertRaises(ErroFireAds):
                selecionar_entrega([dict(novo, Canal=canal)], NUMERO)

    def test_consulta_importa_so_ausencias_e_nao_inventa_meta(self):
        estado = coleta('Nome: Edcarlos\nPara quem é: Minha filha\nTurno: Sábado')
        row = dict(ROW, Nome='Ed', Canal='Chat Fire', **{'Período preferido': 'Tarde'})
        r = interpretar_parcial([row], NUMERO, None, ABA_DESTINO, estado)
        self.assertEqual(r['origem'], 'chat_fire')
        self.assertEqual(r['coleta']['campos']['email']['valor'], 'ana@example.com')
        for tipo in ('nome', 'destinatario', 'turno'):
            self.assertEqual(r['coleta']['campos'][tipo], estado['campos'][tipo])
        self.assertEqual(interpretar_parcial([], NUMERO, None, ABA_DESTINO, estado)['origem'], 'organico')

    def test_v5_reconcilia_append_organico_sem_novo_cadastro(self):
        snap = dict(retrato(), versao=5, origem='organico', destino={'tipo': 'create'})
        manual = dict(ROW, Canal='Indicação')
        op = preparar([manual], snap, BLOCO)
        self.assertEqual(op['dados']['Canal'], 'Orgânico')
        criado = dict(op['dados'], _row=100)
        self.assertIsNone(preparar([manual, criado], snap, BLOCO))
        # Telefone é identidade: mesmo e-mail de outro telefone não impede append.
        self.assertIn('dados', preparar([dict(manual, WhatsApp='5511999990003')], snap, BLOCO))

    def test_v5_retry_mantem_linha_mesmo_que_apareca_registro_novo(self):
        row = dict(ROW, **{'Período preferido': 'Manhã'})
        snap = dict(retrato(), versao=5, destino={
            'tipo': 'update', 'referencia': referencia_registro(row, ABA_DESTINO)})
        recente = dict(row, _row=751, Canal='Chat Fire')
        op = preparar([row, recente], snap, BLOCO)
        self.assertEqual(op['row'], 44)
        modificado = dict(row, **op['campos'], **{'Observação': op['observacoes']})
        self.assertIsNone(preparar([modificado, recente], snap, BLOCO))
        self.assertEqual(recente['Observação'], ROW['Observação'])


class PrazosTests(unittest.TestCase):
    def test_get_e_post_tem_300s_cada_redirect_compartilha_orcamento(self):
        session = Mock()
        with patch('core.integrations.fireads.cliente.time.monotonic', return_value=0) as tempo:
            cliente = ClienteFireAds('https://script.google.com/macros/s/teste/exec',
                                     segundos=300, timeout_leitura=None,
                                     por_operacao=True, session=session)

            def responder(method, *_args, **_kwargs):
                if session.request.call_count == 1:
                    tempo.return_value = 250
                    return Mock(status_code=302, headers={'Location': 'https://script.googleusercontent.com/macros/echo'})
                if method == 'GET':
                    tempo.return_value = 299
                    return Mock(status_code=200, json=Mock(return_value={
                        'success': True, 'data': {'aba': ABA_DESTINO, 'headers': [], 'rows': []}}))
                tempo.return_value = 580
                return Mock(status_code=200, json=Mock(return_value={'success': True, 'aba': ABA_DESTINO, 'inserted': 1}))

            session.request.side_effect = responder
            cliente.consultar(ABA_DESTINO)
            cliente.enviar(ABA_DESTINO, dados={})
            self.assertEqual([c.kwargs['timeout'][1] for c in session.request.call_args_list], [300, 50, 300])
            self.assertEqual([c.args[0] for c in session.request.call_args_list], ['GET', 'GET', 'POST'])
            cliente.close()

    def test_post_nao_e_repetido_automaticamente_apos_timeout(self):
        session = Mock()
        session.request.side_effect = TimeoutError('Resposta perdida')
        cliente = ClienteFireAds('https://script.google.com/macros/s/teste/exec',
                                 segundos=300, timeout_leitura=None, por_operacao=True, session=session)
        with self.assertRaises(TimeoutError):
            cliente.enviar(ABA_DESTINO, dados={})
        session.request.assert_called_once()
        cliente.close()
```

## Passo 16 — `tests/unit/test_fireads_sincronizacao_coleta.py`

SHA-256 (LF): `20c260890d416197146ac36ceff1c72fecc3da5b062d17cb93bbc9f96b831623`

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

    def test_consulta_divergente_preserva_conhecidos_e_completa_email(self):
        estado = coleta('Nome: Ana Paula Silva\nPara quem é: Minha filha\nTurno: Tarde')
        r = interpretar_parcial([row(Nome='Outro Nome')], NUMERO, None, ABA_DESTINO, estado)
        for tipo in ('nome', 'destinatario', 'turno'):
            self.assertEqual(r['coleta']['campos'][tipo], estado['campos'][tipo])
        self.assertEqual(r['coleta']['campos']['email']['valor'], 'ana@example.com')


class SelecaoTests(unittest.TestCase):
    def test_incompativeis_do_mesmo_telefone_atualiza_mais_recente_elegivel(self):
        rows = [row(Nome='Outro', Email='outro@example.com', _row=44),
                row(Nome='Diferente', Email='dif@example.com', _row=45),
                row(_row=100, Canal='Indicação')]
        self.assertEqual(escolher(rows, retrato())['referencia']['linha'], 45)

    def test_recencia_independe_da_relacao_e_do_turno(self):
        snap = retrato(coleta(FORM.replace('Para mim', 'Minha filha')))
        rows = [dict(row(), _row=10, **{'Para quem é': 'Para minha filha'}),
                dict(row(), _row=20, **{'Para quem é': 'Para uma amiga'}),
                dict(row(), _row=30, **{'Período preferido': 'Tarde'})]
        for restantes, linha in [(rows, 30), (rows[1:], 30), (rows[2:], 30)]:
            self.assertEqual(escolher(restantes, snap)['referencia']['linha'], linha)

    def test_email_divergente_nao_exclui_registro_mais_recente(self):
        rows = [row(_row=44), row(_row=99, Email='outro@example.com')]
        self.assertEqual(escolher(rows, retrato())['referencia']['linha'], 99)

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
            preparar([dict(marcado, **{'Observação': BLOCO.replace('Ana Paula', 'Nome editado')})], self.snap, BLOCO)

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
                'success': False, 'error': 'Coluna não editável: Nome'}))):
            with self.assertRaisesRegex(ErroFireAds, 'atualizar EDITABLE_COLUMNS'):
                cliente.enviar(ABA_DESTINO, row=44, campos={'Nome': 'Ana'}, observacoes=BLOCO)
        cliente.close()


if __name__ == '__main__':
    unittest.main()
```

## Passo 17 — `tests/unit/test_coleta_abertura.py`

SHA-256 (LF): `5a56a90450a556a89284eb42f4af2ec850d7ab37c0b8702623a15c336bc187f2`

```python
"""Extração, compatibilidade, etapas e entrega; nenhum serviço externo."""
from copy import deepcopy
from itertools import product
import unittest
from unittest.mock import patch

from core.validacoes.coleta_abertura import (
    extrair, criar_contexto, etapa_inicial, completo, campo, valor, email_coletado, destinatario,
)
from core.integrations.fireads.coleta_abertura import interpretar_parcial
from core.integrations.fireads.destino_coleta import escolher, preparar, identidade_entrega
from core.integrations.fireads.contrato import ABA_DESTINO, ErroFireAds, bloco_observacoes
from core.integrations.whatsapp.messages.abertura_coleta import montar_abertura
from workers.worker_flow.transacoes.movimento_conversa import resolver_movimento_conversa

NUMERO = '5511999990002'
FORM = 'Full name: Ana Paula Silva\nEmail: ana@example.com\nPara quem é o treino?: Para mim'
ROW = {'_row': 44, 'Nome': 'Ana Paula Silva', 'Email': 'ana@example.com', 'WhatsApp': NUMERO,
       'Canal': 'Meta Ads', 'Para quem é': 'Para mim', 'Data/Hora': '19/10/2026 10:00', 'Observação': 'Anotação da unidade'}


def estado(texto=FORM):
    coleta = criar_contexto(1, {'id_mensagem': 1, 'id_hash': 'wamid.teste', 'tipo_mensagem': 'text', 'conteudo_texto': texto})
    coleta.update(status='pronto', etapa_inicial=etapa_inicial(coleta))
    return coleta


def snapshot(texto=FORM):
    coleta = estado(texto)
    return {'versao': 3, 'aba': ABA_DESTINO, 'telefone': NUMERO, 'email': 'ana@example.com',
            'nome': 'Ana Paula', 'origem': 'meta', 'perfil': 'Titular (35 anos)', 'para_quem': 'Para mim',
            'fuso': None, 'referencia': None, 'rota_formulario_chat': True,
            'identidade_coleta': identidade_entrega(coleta), 'destino': None}


class ExtracaoTests(unittest.TestCase):
    def test_oito_combinacoes(self):
        partes = ['Full name: Ana Paula Silva', 'Email: ana@example.com', 'Para quem é: Para mim']
        for n, e, d in product((False, True), repeat=3):
            with self.subTest(nome=n, email=e, destinatario=d):
                coleta = estado('\n'.join(p for p, incluir in zip(partes, (n, e, d)) if incluir))
                self.assertEqual(etapa_inicial(coleta), 1 if not n else (4 if d else 2))
                self.assertEqual(completo(coleta), n and e and d)
                self.assertEqual(email_coletado({'id_conversa': 1, 'contexto_coleta': coleta}), e)

    def test_nome_titular_composto_biografia_e_nao_nome_dependente(self):
        campos = extrair('Nome do dependente: Carlos\nFull name: João Pedro Silva | Programador\nEmail: jp@example.com\nPara quem é: Para minha mãe')
        self.assertEqual(campos['nome']['valor'], 'João Pedro')
        self.assertEqual(campos['destinatario']['valor']['chave'], 'mae')
        self.assertEqual(extrair('Olá, quero informações')['nome']['status'], 'ausente')

    def test_duplicatas_identicas_nao_conflitam(self):
        self.assertEqual(extrair(FORM + '\nEmail: ANA@example.com')['email']['status'], 'aceito')

    def test_conflitos_por_campo_nao_apagam_outros(self):
        for extra, tipo in [('Email: outro@example.com', 'email'), ('Full name: Ana Paula Souza', 'nome'),
                            ('Para quem é: Para meu filho', 'destinatario')]:
            with self.subTest(tipo=tipo):
                campos = extrair(FORM + '\n' + extra)
                self.assertEqual(campos[tipo]['status'], 'conflitante')
                self.assertIsNone(campos[tipo]['valor'])
                self.assertTrue(all(campos[c]['status']=='aceito' for c in campos if c != tipo))

    def test_faixa_etaria_nao_inventa_destinatario(self):
        self.assertIsNone(destinatario('61 a 75 anos'))
        for parentesco in ('Para meu pai', 'Para minha tia', 'Para outra pessoa', 'Para mim e outra pessoa'):
            self.assertTrue(destinatario(parentesco)['dependente'])

    def test_telefone_de_formulario_nao_altera_identidade(self):
        self.assertTrue(completo(estado(FORM + '\nPhone number: +5511888880000')))
        self.assertNotIn('telefone', estado(FORM)['campos'])

    def test_sem_fireads_nao_alega_formulario_externo(self):
        coleta = estado()
        ctx = {'id_conversa': 1, 'contexto_coleta': coleta, 'genero': 'feminino', 'nome_agente': 'Dora', 'nome_unidade': 'Teste'}
        texto = montar_abertura(ctx, 'Bom dia')
        self.assertNotIn('formulários', texto)
        self.assertIn('profissão', texto)
        coleta['formulario_identificado'] = True
        self.assertIn('formulários', montar_abertura(ctx, 'Bom dia'))

    def test_inicializacao_so_na_etapa_persistida(self):
        coleta = estado('Full name: Ana\nEmail: ana@example.com')
        ctx = {'id_conversa': 1, 'id_etapa_atual': None, 'contexto_coleta': coleta}
        self.assertEqual(resolver_movimento_conversa(ctx, {'id_etapa_resultante': 2}), 'inicializacao')
        for etapa in (1, 4):
            with self.assertRaises(ValueError):
                resolver_movimento_conversa(ctx, {'id_etapa_resultante': etapa})


class MomentoEmailTests(unittest.TestCase):
    def test_email_pendente_so_e_perguntado_na_etapa_de_email(self):
        from workers.worker_flow.response_flow.etapas import resolver_etapa7, resolver_etapa9

        for trecho, aceito in (
            ('', False),
            ('Email: invalido', False),
            ('Email: ana@example.com\nEmail: outra@example.com', False),
            ('Email: ana@example.com', True),
        ):
            coleta = estado('Full name: Ana Paula Silva\nPara quem é: Para mim\n' + trecho)
            abertura = montar_abertura({
                'id_conversa': 1, 'contexto_coleta': coleta, 'genero': 'feminino',
                'nome_agente': 'Dora', 'nome_unidade': 'Teste',
            }, 'Bom dia')
            self.assertIn('profissão', abertura)
            self.assertNotIn('e-mail', abertura.casefold())
            for etapa, modulo, evento in (
                (7, resolver_etapa7, 'oferta_aceita'),
                (9, resolver_etapa9, 'retorno_confirmado'),
            ):
                with self.subTest(trecho=trecho, etapa=etapa):
                    contexto = {
                        'id_conversa': 1, 'id_etapa_atual': etapa,
                        'id_etapa_origem_transicao': etapa, 'id_etapa_cliente': etapa,
                        'contexto_coleta': coleta, 'tipo_mensagem_atual': 'text',
                        'texto_cliente_atual': 'sim',
                        'transicoes_permitidas': {evento: 10, evento + '_email_fireads': 11},
                        'mensagem_cliente_atual': {
                            'cliente_telefone': NUMERO, 'id_phone_unidade': 'teste',
                            'id_mensagem_fila': 1,
                        },
                    }
                    with patch.object(modulo, 'enviar_etapa10', return_value={'id_etapa_resultante': 10}) as email, patch.object(
                        modulo, 'enviar_etapa11', return_value={'id_etapa_resultante': 11}
                    ) as triagem:
                        resposta = getattr(modulo, f'resolve_etapa{etapa}')(contexto)
                    self.assertEqual(resposta['id_etapa_resultante'], 11 if aceito else 10)
                    self.assertEqual(email.call_count, 0 if aceito else 1)
                    self.assertEqual(triagem.call_count, 1 if aceito else 0)


class ComplementacaoTests(unittest.TestCase):
    def consulta(self, texto, rows):
        return interpretar_parcial(rows, NUMERO, None, ABA_DESTINO, estado(texto))

    def test_dashboard_preserva_extrator_de_email_estruturado(self):
        row = dict(ROW, Email=' ANA@INTRANET ')
        r = self.consulta('Full name: Ana Paula Silva\nPara quem é: Para mim', [row])
        self.assertEqual(valor(r['coleta'], 'email'), 'ana@intranet')
        self.assertEqual(r['resultado'], 'importado')
        self.assertEqual(extrair('Email: ANA@INTRANET')['email']['status'], 'invalido')

    def test_nome_composto_sem_sobrenome_compativel_com_cadastro_completo(self):
        texto = 'Full name: Ana Paula\nPara quem é: Para mim'
        resultado = self.consulta(texto, [ROW])
        self.assertEqual(resultado['resultado'], 'importado')
        self.assertEqual(valor(resultado['coleta'], 'email'), 'ana@example.com')
        diferente = dict(ROW, Nome='Ana Maria Silva')
        self.assertEqual(self.consulta(texto, [diferente])['resultado'], 'importado')
        self.assertEqual(valor(self.consulta(texto, [diferente])['coleta'], 'nome'), 'Ana Paula')

    def test_completa_so_campo_faltante_de_um_registro_compativel(self):
        r = self.consulta('Full name: Ana Paula Silva\nPara quem é: Para mim', [ROW])
        self.assertEqual(valor(r['coleta'], 'email'), 'ana@example.com')
        self.assertEqual(r['coleta']['campos']['nome']['fonte'], 'mensagem')
        self.assertEqual(r['coleta']['campos']['email']['fonte'], 'dashboard')

    def test_email_conflitante_pode_ser_resolvido_por_terceiro_email(self):
        r = self.consulta(FORM + '\nEmail: outro@example.com', [dict(ROW, Email='terceiro@example.com')])
        self.assertEqual(valor(r['coleta'], 'email'), 'terceiro@example.com')

    def test_divergencia_nao_impede_complementar_destinatario_pelo_telefone(self):
        r = self.consulta('Full name: Ana Paula Silva\nEmail: novo@example.com', [ROW])
        self.assertEqual(r['referencia']['linha'], 44)
        self.assertFalse(valor(r['coleta'], 'destinatario')['dependente'])
        self.assertEqual(valor(r['coleta'], 'email'), 'novo@example.com')

    def test_nao_mistura_campos_entre_inscricoes(self):
        r = self.consulta('Oi', [dict(ROW, Email='', _row=45), dict(ROW, Nome='', _row=46)])
        self.assertEqual(r['referencia']['linha'], 46)
        self.assertIsNone(valor(r['coleta'], 'nome'))
        self.assertEqual(valor(r['coleta'], 'email'), 'ana@example.com')

    def test_canais_e_recencia_data_depois_linha(self):
        manual = dict(ROW, Canal='Indicação', _row=100, **{'Data/Hora': '20/10/2026'})
        for canal, origem in [('Meta Ads', 'meta'), ('Google Ads', 'google'), ('Organico Site', 'organico_site')]:
            r = self.consulta('Oi', [ROW, dict(ROW, _row=46, Canal=canal), manual])
            self.assertEqual(r['origem'], origem)
            self.assertEqual(r['referencia']['linha'], 46)
        self.assertEqual(self.consulta('Oi', [manual])['origem'], 'organico')

    def test_variante_nono_digito(self):
        self.assertIsNotNone(self.consulta('Oi', [dict(ROW, WhatsApp='551199990002')])['referencia'])


class EntregaTests(unittest.TestCase):
    def test_email_e_parentesco_precedem_recencia(self):
        snap = snapshot()
        alvo = escolher([ROW, dict(ROW, Email='outro@example.com', _row=46),
                         dict(ROW, _row=47, **{'Para quem é': 'Para minha mãe'})], snap)
        self.assertEqual(alvo['referencia']['linha'], 44)
        self.assertEqual(escolher([ROW, dict(ROW, _row=46)], snap)['referencia']['linha'], 46)

    def test_cria_quando_ausente_ou_incompativel(self):
        for rows in ([], [dict(ROW, Email='outro@example.com')], [dict(ROW, **{'Para quem é': 'Para minha mãe'})]):
            snap = snapshot()
            snap['destino'] = escolher(rows, snap)
            self.assertEqual(snap['destino'], {'tipo': 'create'})
            dados = preparar(rows, snap, bloco_observacoes(1, 1, 'Resumo'))['dados']
            self.assertEqual(dados['Canal'], 'Meta Ads')
            self.assertEqual(dados['Para quem é'], 'Para mim')

    def test_update_preserva_observacoes_e_demais_campos(self):
        snap = snapshot()
        snap['destino'] = escolher([ROW], snap)
        before = deepcopy(ROW)
        op = preparar([ROW], snap, bloco_observacoes(1, 1, 'Resumo'))
        self.assertEqual(set(op), {'row', 'observacoes'})
        self.assertTrue(op['observacoes'].startswith('Anotação da unidade'))
        self.assertEqual(ROW, before)

    def test_reconciliacao_apos_create_sem_novo_post(self):
        snap = snapshot()
        snap['destino'] = escolher([], snap)
        bloco = bloco_observacoes(1, 1, 'Resumo')
        self.assertIsNone(preparar([dict(ROW, **{'Observação': bloco})], snap, bloco))

    def test_alvo_persistido_deslocado_e_alvo_apagado(self):
        snap = snapshot()
        snap['destino'] = escolher([ROW], snap)
        self.assertEqual(preparar([dict(ROW, _row=100)], snap, bloco_observacoes(1, 1, 'Resumo'))['row'], 100)
        with self.assertRaises(ErroFireAds):
            preparar([dict(ROW, Email='mudou@example.com')], snap, bloco_observacoes(1, 1, 'Resumo'))

    def test_outro_telefone_com_mesmo_email_nao_autoriza_create(self):
        with self.assertRaises(ErroFireAds):
            escolher([dict(ROW, WhatsApp='5511999990003')], snapshot())

    def test_correcao_posterior_nao_troca_identidade_do_formulario(self):
        coleta = estado()
        coleta['campos']['email'] = campo(['corrigido@example.com'], 'email', 'atendimento')
        self.assertEqual(identidade_entrega(coleta)['email']['valor'], 'ana@example.com')


if __name__ == '__main__':
    unittest.main()
```

## Passo 18 — `tests/unit/test_chat_fire_turno.py`

SHA-256 (LF): `44e48bf2137e03263a453ae5b5599604ebaff31b3d79d9dbddf72a605129a7a8`

```python
"""Abertura Chat Fire, preferência antecipada e salto seguro após a triagem."""

from copy import deepcopy
from unittest import TestCase
from unittest.mock import patch

from core.validacoes.coleta_abertura import criar_contexto, extrair, completo, valor, etapa_inicial
from core.integrations.fireads.coleta_abertura import interpretar_parcial
from core.integrations.fireads.contrato import CANAIS, ABA_DESTINO
from core.integrations.fireads.destino_coleta import preparar, escolher
from workers.worker_flow.response_flow.etapas.validadores_contexto.valida_etapa18 import validar_etapa18
from workers.worker_flow.response_flow.etapas import resolver_etapa17 as r17
from tests.unit.test_coleta_abertura import FORM, ROW, NUMERO, snapshot


def coleta(texto=FORM, *, turno=True):
    return criar_contexto(1, {'id_mensagem': 1, 'id_hash': 'teste',
                            'tipo_mensagem': 'text', 'conteudo_texto': texto}, coletar_turno=turno)


class ApresentacaoTests(TestCase):
    def test_apresentacoes_naturais(self):
        for prefixo in ('Eu me chamo', 'Me chamo', 'Sou', 'Eu sou', 'Eu sou a',
                        'Meu nome é', 'O meu nome é', 'Aqui é', 'Aqui quem fala é',
                        'Pode me chamar de'):
            for saudacao in ('', 'Olá! ', 'Oi, ', 'Boa tarde. '):
                with self.subTest(prefixo=prefixo, saudacao=saudacao):
                    campo = extrair(saudacao + prefixo + ' Alline. Vim pelo site.')['nome']
                    self.assertEqual(campo['valor'], 'Alline')
                    self.assertEqual(campo['identidade'], 'alline')

    def test_compostos_e_continuacao_sem_pontuacao(self):
        self.assertEqual(extrair('Eu me chamo João Pedro Silva e quero conhecer o curso')['nome']['valor'], 'João Pedro')
        self.assertEqual(extrair('Olá sou Alline vim pelo site')['nome']['identidade'], 'alline')

    def test_profissao_local_parentesco_e_idade_nao_sao_nomes(self):
        for texto in ('Eu sou professora', 'Sou de Santo André', 'Sou aposentada',
                      'Sou a mãe da Ana', 'Meu filho se chama Carlos', 'Sou de manhã',
                      'Sou uma pessoa interessada', 'Eu sou 60+', 'Sou o responsável',
                      'Olá! Quero informações', 'Sou aluna', 'Aqui é a professora'):
            with self.subTest(texto=texto):
                self.assertNotEqual(extrair(texto)['nome']['status'], 'aceito')

    def test_apresentacoes_distintas_mantem_conflito(self):
        self.assertEqual(extrair('Sou Ana\nEu me chamo Maria')['nome']['status'], 'conflitante')

    def test_quem_vai_fazer_nao_inventa_destinatario_por_faixa(self):
        for opcao in ('Criança', 'Adulto', 'Idoso'):
            self.assertEqual(extrair('Quem vai fazer: ' + opcao)['destinatario']['status'], 'invalido')
        self.assertFalse(extrair('Quem vai fazer: Para mim')['destinatario']['valor']['dependente'])


class TurnoAberturaTests(TestCase):
    def test_rotulos_e_valores_validos(self):
        for rotulo in ('Melhor período', 'Período preferido', 'Turno', 'Turno de preferência'):
            for texto, esperado in [('Manhã', 'manha'), ('Tarde', 'tarde'), ('Noite', 'noite'), ('Sábado', 'sabado')]:
                with self.subTest(rotulo=rotulo, texto=texto):
                    c = coleta(FORM + '\n' + rotulo + ': ' + texto)
                    self.assertEqual(valor(c, 'turno'), esperado)
                    self.assertTrue(completo(c))
                    self.assertEqual(etapa_inicial(c), 4)

    def test_escolha_explicita_e_nao_saudacao_ou_trabalho(self):
        for texto, esperado in [('Prefiro ir de manhã', 'manha'), ('Posso sábado', 'sabado'),
                                 ('Boa tarde', None), ('Trabalho à noite', None),
                                 ('Prefiro tarde ou noite', None), ('Prefiro não ir sábado', None)]:
            with self.subTest(texto=texto):
                self.assertEqual(valor(coleta(FORM + '\n' + texto), 'turno'), esperado)

    def test_turno_nao_e_exigido_nem_extraido_com_link(self):
        c = coleta(FORM + '\nMelhor período: Sábado', turno=False)
        self.assertTrue(completo(c))
        self.assertNotIn('turno', c['campos'])
        r = interpretar_parcial([dict(ROW, **{'Período preferido': 'Tarde'})], NUMERO, None, ABA_DESTINO, c)
        self.assertNotIn('turno', r['coleta']['campos'])

    def test_duplicado_equivalente_e_conflitante(self):
        self.assertEqual(valor(coleta(FORM + '\nTurno: Tarde\nMelhor período: tarde'), 'turno'), 'tarde')
        c = coleta(FORM + '\nTurno: Tarde\nMelhor período: Sábado')
        self.assertEqual(c['campos']['turno']['status'], 'conflitante')
        self.assertFalse(completo(c))

    def test_turno_pendente_nao_muda_a_etapa_inicial(self):
        c = coleta()
        self.assertFalse(completo(c))
        self.assertEqual(etapa_inicial(c), 4)

    def test_sabado_digitado_na_etapa18(self):
        for texto in ('Sábado', 'Pode ser sábado', 'Só posso sábado'):
            self.assertEqual(validar_etapa18(texto), 'sabado')
        self.assertIsNone(validar_etapa18('sábado ou tarde'))


class ChatFireTests(TestCase):
    def consultar(self, c, rows):
        return interpretar_parcial(rows, NUMERO, None, ABA_DESTINO, c)

    def test_caso_alline_email_no_dash_destinatario_perguntado_turno_preservado(self):
        texto = ('Olá! Sou Alline. Vim pelo site e quero agendar minha demonstração de cortesia.\n'
                 'Quem vai fazer: Criança\nMotivo: Apoiar o desempenho nos estudos\n'
                 'De onde venho: Outra cidade\nMelhor período: Sábado')
        row = dict(ROW, Nome='Alline', Email='alline@example.com', Canal='Chat Fire',
                   **{'Para quem é': '', 'Perfil/Faixa': 'Criança', 'Período preferido': ''})
        r = self.consultar(coleta(texto), [row])
        self.assertEqual(r['origem'], 'chat_fire')
        self.assertEqual(valor(r['coleta'], 'nome'), 'Alline')
        self.assertEqual(valor(r['coleta'], 'email'), 'alline@example.com')
        self.assertEqual(valor(r['coleta'], 'turno'), 'sabado')
        self.assertIsNone(valor(r['coleta'], 'destinatario'))
        self.assertEqual(etapa_inicial(r['coleta']), 2)
        self.assertEqual(r['referencia']['linha'], ROW['_row'])

    def test_turno_do_dash_completa_conflito_sem_sobrescrever_aceito(self):
        row = dict(ROW, Canal='Chat Fire', **{'Período preferido': 'Noite'})
        for complemento, esperado in [('', 'noite'), ('\nTurno: Tarde\nTurno: Sábado', 'noite'),
                                     ('\nTurno: Sábado', 'sabado')]:
            r = self.consultar(coleta(FORM + complemento), [row])
            self.assertEqual(valor(r['coleta'], 'turno'), esperado)
            self.assertTrue(completo(r['coleta']))

    def test_mesmo_telefone_vincula_sem_substituir_email_aceito(self):
        c = coleta(FORM + '\nTurno: Sábado')
        r = self.consultar(c, [dict(ROW, Email='outro@example.com', Canal='Chat Fire', **{'Período preferido': 'Sábado'})])
        self.assertEqual(r['referencia']['linha'], 44)
        self.assertEqual(valor(r['coleta'], 'email'), 'ana@example.com')

    def test_chat_fire_participa_da_recencia_sem_alterar_outros_codigos(self):
        row = dict(ROW, Canal='Chat Fire', _row=50)
        self.assertEqual(self.consultar(coleta('Oi'), [ROW, row])['origem'], 'chat_fire')
        self.assertEqual(CANAIS['chat_fire'], ('Chat Fire', '113481'))
        self.assertEqual(CANAIS['google'][1], '113336')
        self.assertEqual(CANAIS['meta'][1], '113340')

    def test_create_chat_fire_preserva_nome_canal(self):
        from core.integrations.fireads.contrato import bloco_observacoes
        snap = snapshot()
        snap.update(origem='chat_fire', destino=escolher([], snap))
        dados = preparar([], snap, bloco_observacoes(1, 1, 'Resumo'))['dados']
        self.assertEqual(dados['Canal'], 'Chat Fire')


class SaidaTriagemTests(TestCase):
    def contexto(self, turno=None, link=None):
        return {'id_conversa': 1, 'id_etapa_cliente': 17, 'id_etapa_atual': 17,
                'id_etapa_origem_transicao': 17, 'tipo_mensagem_atual': 'text',
                'texto_cliente_atual': 'Às vezes', 'status_dependente': False,
                'idade_pessoa_triagem': 40, 'idade_cliente': 40, 'nome_cliente': 'Ana',
                'nome_agente_unidade': 'Dora', 'genero_agente_unidade': 'feminino',
                'numero_comercial_unidade': '5511999990001', 'turno': turno,
                'link_agendamento_unidade': link,
                'transicoes_permitidas': {'triagem_concluida_turno_coletado': 19,
                    'triagem_concluida_sem_link': 18, 'triagem_pergunta_6_respondida': 20},
                'mensagem_cliente_atual': {'cliente_telefone': NUMERO,
                    'id_phone_unidade': 'teste', 'id_mensagem_fila': 1}}

    def resolver(self, ctx):
        with patch.object(r17, 'enviar_etapa18', return_value={'id_etapa_resultante': 18}) as turno, \
             patch.object(r17, 'enviar_etapa19', return_value={'id_etapa_resultante': 19}) as comercial, \
             patch.object(r17, 'enviar_etapa20', return_value={'id_etapa_resultante': 20}) as agenda:
            resultado = r17.resolve_etapa17(ctx)
        return resultado, turno, comercial, agenda

    def test_sem_link_turno_coletado_pula_pergunta_e_inclui_preferencia(self):
        for turno in ('manha', 'tarde', 'noite', 'sabado'):
            with self.subTest(turno=turno):
                r, pergunta, comercial, agenda = self.resolver(self.contexto(turno=turno))
                self.assertEqual(r['id_etapa_resultante'], 19)
                self.assertEqual(r['resposta_triagem'], 'às vezes')
                pergunta.assert_not_called()
                agenda.assert_not_called()
                comercial.assert_called_once()

    def test_link_atual_prevalece_mesmo_com_turno_salvo(self):
        r, pergunta, comercial, agenda = self.resolver(self.contexto(turno='sabado', link='https://example.com'))
        self.assertEqual(r['id_etapa_resultante'], 20)
        comercial.assert_not_called()
        pergunta.assert_not_called()

    def test_sem_turno_mantem_pergunta_original(self):
        r, pergunta, comercial, _ = self.resolver(self.contexto())
        self.assertEqual(r['id_etapa_resultante'], 18)
        pergunta.assert_called_once()
        comercial.assert_not_called()

    def test_resposta_triagem_invalida_nao_pula(self):
        c = self.contexto(turno='sabado')
        c['texto_cliente_atual'] = 'quero saber mais'
        with patch.object(r17, 'enviar_etapa17_cliente_contexto_invalido', return_value={'id_etapa_resultante': 17}):
            r, pergunta, comercial, agenda = self.resolver(c)
        self.assertEqual(r['id_etapa_resultante'], 17)
        comercial.assert_not_called()
```

## Passo 19 — `tests/unit/test_destinatario_abertura.py`

SHA-256 (LF): `5d2aedbb3fe904c9571418582d14289cb73a35cddb041c76c05a13b3a34ffc3b`

```python
"""Destinatário explícito na abertura e compatibilidade da inscrição externa."""

import unittest

from core.validacoes.coleta_abertura import extrair, destinatario, etapa_inicial, valor
from core.integrations.fireads.coleta_abertura import interpretar_parcial
from core.integrations.fireads.destino_coleta import escolher
from core.integrations.fireads.contrato import ABA_DESTINO
from tests.unit.test_coleta_abertura import estado, snapshot, ROW, NUMERO


class DestinatarioAberturaTests(unittest.TestCase):
    def test_exemplos_com_e_sem_para_definem_dependente(self):
        exemplos = {
            'Para uma amiga': 'amiga', 'Para um conhecido': 'conhecido',
            'Para minha amiga': 'amiga', 'Para meu amigo': 'amigo',
            'Minha filha': 'filha', 'Meu filho': 'filho',
            'Minha amiga': 'amiga', 'Meu amigo': 'amigo',
            'Meu conhecido': 'conhecido', 'Minha conhecida': 'conhecida',
            'Para uma conhecida': 'conhecida', 'Para um amigo': 'amigo',
            'A minha cunhada': 'cunhada', 'Para o meu enteado': 'enteado',
            'Minha afilhada': 'afilhada', 'Meu padrasto': 'padrasto',
            'Minha madrasta': 'madrasta', 'Meu genro': 'genro',
            'Minha nora': 'nora', 'Meu bisavô': 'bisavo',
            'Minha bisneta': 'bisneta', 'Minha vizinha': 'vizinha',
            'Meu colega': 'colega', 'Minha namorada': 'namorada',
            'Meu noivo': 'noivo', 'Para um familiar': 'familiar',
            'Minhas filhas': 'filhas', 'Meus sobrinhos': 'sobrinhos',
            'Para minhas amigas': 'amigas', 'Para meus irmãos': 'irmaos',
            ' MINHA AMIGA! 😊 ': 'amiga', 'Pra minha amiga': 'amiga',
        }
        for texto, chave in exemplos.items():
            with self.subTest(texto=texto):
                campo = extrair(texto)['destinatario']
                self.assertEqual(campo['status'], 'aceito')
                self.assertIs(campo['valor']['dependente'], True)
                self.assertEqual(campo['valor']['chave'], chave)

    def test_rotulos_identificam_o_campo_sem_inferir_idade(self):
        for rotulo in ('Para quem é', 'Para quem é o treino?', 'Quem vai fazer',
                       'Quem vai fazer o curso?', 'Quem vai fazer o treino'):
            for resposta, dependente in [('Meu filho', True), ('Minha amiga', True),
                                         ('Para um conhecido', True), ('Para mim', False)]:
                with self.subTest(rotulo=rotulo, resposta=resposta):
                    campo = extrair(f'{rotulo}: {resposta}')['destinatario']
                    self.assertEqual(campo['status'], 'aceito')
                    self.assertIs(campo['valor']['dependente'], dependente)

    def test_faixas_etarias_nao_definem_destinatario(self):
        for texto in ('Criança', 'Adulto', 'Idoso', 'Para uma criança', 'Para um adulto',
                      'Minha criança', 'Meu bebê', 'Para uma pessoa idosa', '61 a 75 anos'):
            for prefixo in ('', 'Quem vai fazer: ', 'Para quem é: '):
                with self.subTest(texto=prefixo + texto):
                    campo = extrair(prefixo + texto)['destinatario']
                    self.assertNotEqual(campo['status'], 'aceito')
                    self.assertIsNone(campo['valor'])

    def test_mencao_posse_negacao_e_pergunta_nao_definem_participante(self):
        for texto in ('Meu nome é João', 'Minha preferência é tarde', 'Meu email é ana@example.com',
                      'Minha amiga me indicou vocês', 'Meu filho já faz o curso',
                      'Minha filha não vai participar', 'Para meu amigo não',
                      'Meu amigo?', 'Quem vai fazer o pagamento: Minha mãe',
                      'Não é para minha amiga', 'Meu', 'Minha', 'Para uma', 'Para um'):
            with self.subTest(texto=texto):
                self.assertNotEqual(extrair(texto)['destinatario']['status'], 'aceito')
        self.assertIsNone(destinatario('Independente'))

    def test_preserva_chaves_historicas_e_combinacoes(self):
        for texto, chave in [('pai_ou_mae', 'mae+pai'), ('Para meu filho', 'filho'),
                             ('Para outra pessoa', 'dependente'),
                             ('Para mim e outra pessoa', 'titular+dependente')]:
            self.assertEqual(destinatario(texto)['chave'], chave)
        self.assertEqual(extrair('Minha mãe e meu pai')['destinatario']['valor']['chave'], 'mae+pai')

    def test_variantes_equivalentes_nao_conflitam_e_destinos_distintos_conflitam(self):
        iguais = extrair('Minha amiga\nPara uma amiga\nQuem vai fazer: Para minha amiga')
        self.assertEqual(iguais['destinatario']['status'], 'aceito')
        for outro in ('Para mim', 'Minha filha', 'Meu conhecido'):
            self.assertEqual(extrair('Minha amiga\n' + outro)['destinatario']['status'], 'conflitante')

    def test_nome_conhecido_pula_pergunta_destinatario_mas_preserva_email_pendente(self):
        coleta = estado('Sou Ana\nQuem vai fazer: Minha filha')
        self.assertEqual(etapa_inicial(coleta), 4)
        self.assertIsNone(valor(coleta, 'email'))
        self.assertTrue(valor(coleta, 'destinatario')['dependente'])
        self.assertEqual(etapa_inicial(estado('Meu amigo')), 1)

    def test_dashboard_usa_recencia_sem_substituir_relacao_da_mensagem(self):
        coleta = estado('Full name: Ana Paula Silva\nMinha amiga')
        amiga = dict(ROW, **{'Para quem é': 'Para uma amiga'})
        filha = dict(ROW, _row=46, **{'Para quem é': 'Para minha filha'})
        decisao = interpretar_parcial([amiga, filha], NUMERO, None, ABA_DESTINO, coleta)
        self.assertEqual(decisao['referencia']['linha'], filha['_row'])
        self.assertEqual(valor(decisao['coleta'], 'email'), 'ana@example.com')
        self.assertEqual(decisao['coleta']['campos']['destinatario']['fonte'], 'mensagem')
        equivalente = interpretar_parcial([filha], NUMERO, None, ABA_DESTINO, coleta)
        self.assertEqual(equivalente['referencia']['linha'], filha['_row'])
        self.assertEqual(valor(equivalente['coleta'], 'email'), 'ana@example.com')
        self.assertEqual(valor(equivalente['coleta'], 'destinatario')['chave'], 'amiga')

    def test_entrega_atualiza_relacao_compativel_ou_cria_se_divergente(self):
        snap = snapshot('Sou Ana Paula Silva\nana@example.com\nQuem vai fazer: Minha amiga')
        snap['rota_formulario_chat'] = estado(
            'Sou Ana Paula Silva\nana@example.com\nQuem vai fazer: Minha amiga'
        )['rota_formulario_chat']
        self.assertTrue(snap['rota_formulario_chat'])
        amiga = dict(ROW, **{'Para quem é': 'Para uma amiga'})
        filha = dict(ROW, _row=46, **{'Para quem é': 'Para minha filha'})
        destino = escolher([amiga, filha], snap)
        self.assertEqual(destino['tipo'], 'update')
        self.assertEqual(destino['referencia']['linha'], amiga['_row'])
        self.assertEqual(escolher([filha], snap), {'tipo': 'create'})
```

## Passo 20 — `tests/unit/test_fireads_prioridade_destinatario.py`

SHA-256 (LF): `bffb5a5cf0ac941026b26d06fc14f0377dd87af88320d71450600e5adb67a4a4`

```python
"""Complementação por telefone e recência sem sobrescrever a mensagem."""

from copy import deepcopy
import unittest

from core.validacoes.coleta_abertura import criar_contexto, valor
from core.integrations.fireads.coleta_abertura import interpretar_parcial
from core.integrations.fireads.destino_coleta import escolher, preparar
from core.integrations.fireads.contrato import ABA_DESTINO, bloco_observacoes
from tests.unit.test_coleta_abertura import ROW, NUMERO, snapshot


def registro(linha, destinatario, **dados):
    return dict(ROW, _row=linha, **{'Para quem é': destinatario}, **dados)


def coleta(destinatario='Minha filha', *, turno=None, com_link=False, extras=''):
    texto = 'Full name: Ana Paula Silva\nPara quem é: ' + destinatario
    if turno:
        texto += '\nTurno: ' + turno
    return criar_contexto(1, {'id_mensagem': 1, 'id_hash': 'wamid.teste',
                             'tipo_mensagem': 'text', 'conteudo_texto': texto + extras},
                          coletar_turno=not com_link)


def consultar(rows, estado=None):
    return interpretar_parcial(rows, NUMERO, None, ABA_DESTINO, estado or coleta())


class PrioridadeDestinatarioTests(unittest.TestCase):
    def test_registro_unico_de_amiga_completa_email_da_conversa_para_filha(self):
        estado = coleta()
        antes = deepcopy(estado)
        r = consultar([registro(44, 'Minha amiga')], estado)
        self.assertEqual(r['referencia']['linha'], 44)
        self.assertEqual(valor(r['coleta'], 'email'), 'ana@example.com')
        self.assertEqual(valor(r['coleta'], 'destinatario')['chave'], 'filha')
        self.assertEqual(r['coleta']['campos']['destinatario']['fonte'], 'mensagem')
        self.assertEqual(estado, antes)

    def test_registro_recente_precede_relacao_exata_antiga(self):
        r = consultar([registro(44, 'Para minha filha'), registro(90, 'Para uma amiga',
                       **{'Data/Hora': '21/10/2026 10:00'})])
        self.assertEqual(r['referencia']['linha'], 90)

    def test_tipo_diferente_recente_e_selecionado_sem_substituir_o_informado(self):
        r = consultar([registro(44, 'Minha amiga'), registro(90, 'Para mim',
                       **{'Data/Hora': '21/10/2026 10:00'})])
        self.assertEqual(r['referencia']['linha'], 90)
        self.assertTrue(valor(r['coleta'], 'destinatario')['dependente'])

    def test_cada_prioridade_desempata_por_data_e_linha(self):
        for destinatario in ('Minha filha', 'Meu amigo', 'Para mim'):
            with self.subTest(destinatario=destinatario):
                rows = [registro(100, destinatario, **{'Data/Hora': '18/10/2026'}),
                        registro(44, destinatario), registro(45, destinatario)]
                self.assertEqual(consultar(rows)['referencia']['linha'], 45)

    def test_fallback_outro_tipo_preserva_destinatario_aceito(self):
        for informado, planilha in [('Minha filha', 'Para mim'), ('Para mim', 'Minha amiga'),
                                   ('Minha filha', ''), ('Minha filha', 'Criança')]:
            with self.subTest(informado=informado, planilha=planilha):
                estado = coleta(informado)
                r = consultar([registro(44, planilha)], estado)
                self.assertEqual(r['referencia']['linha'], 44)
                self.assertEqual(valor(r['coleta'], 'email'), 'ana@example.com')
                self.assertEqual(r['coleta']['campos']['destinatario'], estado['campos']['destinatario'])

    def test_turno_divergente_nao_filtra_e_aceito_e_preservado(self):
        estado = coleta(turno='Tarde')
        rows = [registro(44, 'Para mim', **{'Período preferido': 'Tarde'}),
                registro(45, 'Para mim', **{'Período preferido': 'Noite'}),
                registro(46, 'Para mim', **{'Período preferido': ''})]
        r = consultar(rows, estado)
        self.assertEqual(r['referencia']['linha'], 46)
        self.assertEqual(valor(r['coleta'], 'turno'), 'tarde')
        r = consultar(rows[1:], estado)
        self.assertEqual(r['referencia']['linha'], 46)
        self.assertEqual(valor(r['coleta'], 'email'), 'ana@example.com')

    def test_turno_nao_anula_prioridades_de_relacao_ou_tipo(self):
        for destinatario in ('Minha filha', 'Minha amiga'):
            with self.subTest(destinatario=destinatario):
                r = consultar([registro(44, destinatario, **{'Período preferido': 'Noite'})],
                              coleta(turno='Tarde'))
                self.assertEqual(r['referencia']['linha'], 44)
                self.assertEqual(valor(r['coleta'], 'turno'), 'tarde')

    def test_com_link_turno_nao_participa_do_ultimo_recurso(self):
        r = consultar([registro(44, 'Para mim', **{'Período preferido': 'Noite'})],
                      coleta(turno='Tarde', com_link=True))
        self.assertEqual(r['referencia']['linha'], 44)
        self.assertNotIn('turno', r['coleta']['campos'])

    def test_nome_email_divergentes_nao_filtram_e_conhecidos_sao_preservados(self):
        for destinatario in ('Minha filha', 'Minha amiga', 'Para mim'):
            with self.subTest(destinatario=destinatario):
                self.assertEqual(consultar([registro(44, destinatario, Nome='Outra Pessoa')])['referencia']['linha'], 44)
                r = consultar([registro(44, destinatario, Email='outro@example.com')],
                              coleta(extras='\nEmail: ana@example.com'))
                self.assertEqual(r['referencia']['linha'], 44)
                self.assertEqual(valor(r['coleta'], 'email'), 'ana@example.com')
        rows = [registro(45, 'Minha filha', Nome='Outra Pessoa'), registro(44, 'Minha amiga')]
        self.assertEqual(consultar(rows)['referencia']['linha'], 45)

    def test_outro_telefone_e_canal_manual_nao_entram_na_prioridade(self):
        rows = [registro(44, 'Minha filha', WhatsApp='5511999990003'),
                registro(45, 'Minha filha', Canal='Indicação'), registro(43, 'Minha amiga')]
        self.assertEqual(consultar(rows)['referencia']['linha'], 43)
        self.assertIsNone(consultar(rows[:2])['referencia'])

    def test_destinatario_ausente_usa_mais_recente_sem_inventar_valor(self):
        rows = [registro(44, 'Minha filha'), registro(45, '', **{'Período preferido': ''})]
        r = consultar(rows, coleta('', turno='Sábado'))
        self.assertEqual(r['referencia']['linha'], 45)
        self.assertIsNone(valor(r['coleta'], 'destinatario'))
        self.assertEqual(valor(r['coleta'], 'turno'), 'sabado')

    def test_nao_resgata_email_antigo_quando_linha_recente_esta_vazia(self):
        rows = [registro(44, 'Minha filha'), registro(45, 'Minha amiga', Email='')]
        r = consultar(rows)
        self.assertEqual(r['referencia']['linha'], 45)
        self.assertIsNone(valor(r['coleta'], 'email'))

    def test_entrega_usa_a_linha_vinculada_sem_alterar_campos_da_planilha(self):
        row = registro(44, 'Minha amiga')
        antes = deepcopy(row)
        r = consultar([row])
        snap = snapshot()
        snap['referencia'] = r['referencia']
        snap['destino'] = escolher([row], snap)
        op = preparar([row], snap, bloco_observacoes(1, 1, 'Resumo para a filha'))
        self.assertEqual(op['row'], 44)
        self.assertEqual(set(op), {'row', 'observacoes'})
        self.assertTrue(op['observacoes'].startswith(ROW['Observação']))
        self.assertEqual(row, antes)
```

## Passo 21 — `tests/unit/test_fireads_aba_geral.py`

SHA-256 (LF): `1347905064f8356505cb285328af7f71cfda106857899c6a5368f966773b9b98`

```python
"""Contrato da aba única e entrega do mesmo formulário, sem serviços externos."""

from copy import deepcopy
import unittest
from unittest.mock import Mock, patch

from core.integrations.fireads.aba_geral import configuracao_compativel
from core.integrations.fireads.contrato import (
    ABA_DESTINO, CANAIS, ErroFireAds, bloco_observacoes, acrescentar_observacoes,
)
from core.integrations.funil.oportunidades import montar_observacoes_lead
from workers.worker_consulta_dash.resultado import interpretar
from workers.worker_consulta_dash.consulta import consultar
from workers.worker_funil.fireads import preparar_escrita

NUMERO = "5511999990002"
REGISTRO = {
    "_row": 44, "Nome": "Ana Paula Silva", "Email": "ana@example.com",
    "WhatsApp": NUMERO, "Canal": "Google Ads", "Para quem é": "Para mim",
    "Data/Hora": "14/10/2026", "Observação": "Anotação do operador",
}


class AbaGeralTests(unittest.TestCase):
    def test_canais_permitidos_antes_da_recencia(self):
        manual = dict(REGISTRO, _row=99, Canal="Lead Franqueador", **{"Data/Hora": "15/10/2026"})
        for canal, origem in (("Google Ads", "google"), ("META ADS", "meta"), (" Orgânico   Site ", "organico_site")):
            with self.subTest(canal=canal):
                decisao = interpretar([dict(REGISTRO, Canal=canal), manual], NUMERO)
                self.assertEqual(decisao["origem"], origem)
                self.assertEqual(decisao["referencia"]["linha"], 44)
                self.assertEqual(decisao["dados_titular"]["nome"], "Ana Paula")
        for canal in ("Indicação", "Lead Franqueador", "Orgânico"):
            decisao = interpretar([dict(REGISTRO, Canal=canal)], NUMERO)
            self.assertEqual(decisao["motivo"], "canal_nao_elegivel")
            self.assertEqual(decisao["dados_titular"], {})
            self.assertIsNotNone(decisao["referencia"])
        with self.assertRaises(ErroFireAds):
            interpretar([dict(REGISTRO, Canal="MKT DIGITAL - GOOGLE ADS")], NUMERO)

    def test_data_hora_e_depois_linha_sem_preferencia_por_canal(self):
        for canal in ("Google Ads", "Meta Ads", "Organico Site"):
            rows = [dict(REGISTRO, _row=n, Canal=canal if n == 46 else "Google Ads") for n in (44,45,46)]
            self.assertEqual(interpretar(rows, NUMERO)["referencia"]["linha"], 46)
        rows = [dict(REGISTRO, _row=90), dict(REGISTRO, _row=2, **{"Data/Hora": "15/10/2026"})]
        self.assertEqual(interpretar(rows, NUMERO)["referencia"]["linha"], 2)
        rows[0]["Data/Hora"] = "15/10/2026 12:00:01"
        self.assertEqual(interpretar(rows, NUMERO)["referencia"]["linha"], 90)

    def test_data_invalida_prioriza_data_valida_ou_maior_linha(self):
        invalido = dict(REGISTRO, _row=90, **{"Data/Hora": "sem data"})
        self.assertEqual(interpretar([REGISTRO, invalido], NUMERO)["referencia"]["linha"], 44)
        decisao = interpretar([invalido], NUMERO)
        self.assertEqual(decisao["referencia"]["criterio_recencia"], "linha_sem_data_valida")
        for linha in (None, True, 1, "44"):
            with self.assertRaises(ErroFireAds):
                interpretar([dict(REGISTRO, _row=linha)], NUMERO)

    def test_incompleto_nao_resgata_outro_formulario_e_preserva_alvo(self):
        for campo in ("Nome", "Email", "Para quem é"):
            novo = dict(REGISTRO, _row=46, **{campo: ""})
            decisao = interpretar([REGISTRO, novo], NUMERO)
            self.assertEqual(decisao["origem"], "organico")
            self.assertEqual(decisao["motivo"], "campos_ausentes")
            self.assertEqual(decisao["dados_titular"], {})
            self.assertEqual(decisao["referencia"]["linha"], 46)
        decisao = interpretar([dict(REGISTRO, **{"Para quem é": "61_a_75"})], NUMERO)
        self.assertEqual(decisao["motivo"], "destinatario_desconhecido")

    def test_parentescos_nao_importam_idade_e_variante_telefone_participa(self):
        for parentesco in ("Para meu pai/mãe", "filho_ou_filha", "Para outra pessoa", "Para dependente"):
            decisao = interpretar([dict(REGISTRO, **{"Para quem é": parentesco})], NUMERO)
            self.assertTrue(decisao["status_dependente"])
            self.assertNotIn("idade", decisao["dados_titular"])
        recente = dict(REGISTRO, _row=46, WhatsApp="p:+551199990002")
        self.assertEqual(interpretar([REGISTRO, recente], NUMERO)["referencia"]["linha"], 46)
        self.assertEqual(interpretar([REGISTRO], "5511999990003")["motivo"], "telefone_ausente")

    def test_consulta_uma_aba_e_guarda_apenas_o_contato(self):
        outro = dict(REGISTRO, _row=50, WhatsApp="5511999990003")
        api = Mock()
        api.consultar.return_value = {"headers": list(REGISTRO), "rows": [REGISTRO, outro]}
        reserva = {"id_consulta": 1, "restante": 300, "entrada": {
            "versao": 2, "url": "https://script.google.com/macros/s/teste/exec",
            "aba": ABA_DESTINO, "numero": NUMERO, "fuso": None,
        }}
        with patch("workers.worker_consulta_dash.consulta.ClienteFireAds", return_value=api):
            resultado = consultar(reserva)
        api.consultar.assert_called_once_with(ABA_DESTINO)
        self.assertEqual(resultado["fontes"], {"geral": [REGISTRO]})
        api.enviar.assert_not_called()
        api.consultar.return_value["headers"].remove("Para quem é")
        with patch("workers.worker_consulta_dash.consulta.ClienteFireAds", return_value=api):
            self.assertEqual(consultar(reserva)["decisao"]["motivo"], "cabecalhos_ausentes")

    def test_configuracao_legada_compatibilidade_e_versao_desconhecida(self):
        abertura = {"url": "url", "aba": ABA_DESTINO, "fuso": None}
        self.assertTrue(configuracao_compativel(dict(abertura, versao=2), abertura))
        self.assertTrue(configuracao_compativel({"compatibilidade_aba_geral": dict(abertura, valida=True)}, abertura))
        self.assertFalse(configuracao_compativel(dict(abertura, versao=3), abertura))
        self.assertFalse(configuracao_compativel({"aba_google": "antiga"}, abertura))
        self.assertFalse(configuracao_compativel(dict(abertura, versao=2, aba="Outra"), abertura))


class EntregaAbaGeralTests(unittest.TestCase):
    def setUp(self):
        self.bloco = bloco_observacoes(1, 25, "Novo lead\nDados de atendimento", versao=2)
        self.snapshot = {
            "versao": 2, "aba": ABA_DESTINO, "telefone": NUMERO,
            "nome": "Ana", "email": "ana@example.com", "perfil": "Titular",
            "origem": "google", "referencia": interpretar([REGISTRO], NUMERO)["referencia"],
        }

    def test_atualiza_mesmo_formulario_mesmo_com_nova_inscricao(self):
        novo = dict(REGISTRO, _row=100, Nome="Carlos", Canal="Meta Ads")
        antes = deepcopy(REGISTRO)
        op = preparar_escrita([REGISTRO, novo], self.snapshot, self.bloco)
        self.assertEqual(op["row"], 44)
        self.assertEqual(set(op), {"row", "observacoes"})
        self.assertEqual(op["observacoes"], REGISTRO["Observação"] + "\n\n" + self.bloco)
        self.assertEqual(REGISTRO, antes)

    def test_relocaliza_mas_nao_atualiza_posicao_reutilizada_ou_alvo_excluido(self):
        deslocado = dict(REGISTRO, _row=43)
        outro = dict(REGISTRO, Nome="Outra pessoa", WhatsApp="5511999990003")
        self.assertEqual(preparar_escrita([outro, deslocado], self.snapshot, self.bloco)["row"], 43)
        for rows in ([], [outro], [dict(REGISTRO, Nome="Editado")]):
            with self.assertRaises(ErroFireAds):
                preparar_escrita(rows, self.snapshot, self.bloco)

    def test_reconcilia_antes_de_relocalizar_e_nao_repete_apos_queda(self):
        entregue = dict(REGISTRO, _row=43, **{"Observação": "Operador\n\n" + self.bloco})
        self.assertIsNone(preparar_escrita([entregue], self.snapshot, self.bloco))
        entregue["Observação"] = entregue["Observação"].replace("Dados de atendimento", "Editado")
        with self.assertRaises(ErroFireAds):
            preparar_escrita([entregue], self.snapshot, self.bloco)

    def test_duas_conversas_mesmo_titulo_e_bloco_legado(self):
        legado = bloco_observacoes(1, 24, "Texto antigo")
        novo, _ = acrescentar_observacoes(legado, self.bloco)
        self.assertTrue(novo.startswith(legado))
        outro = bloco_observacoes(1, 26, "Novo atendimento para Lead antigo", versao=2)
        final, mudou = acrescentar_observacoes(novo, outro)
        self.assertTrue(mudou)
        self.assertEqual(acrescentar_observacoes(final, outro), (final, False))

    def test_organico_sem_alvo_reconfere_antes_do_append(self):
        snapshot = dict(self.snapshot, referencia=None, origem="organico")
        self.assertEqual(preparar_escrita([REGISTRO], snapshot, self.bloco)["row"], 44)
        self.assertEqual(preparar_escrita([], snapshot, self.bloco)["dados"]["Canal"], "Orgânico")
        with self.assertRaises(ErroFireAds):
            preparar_escrita([dict(REGISTRO, WhatsApp="5511999990003")], snapshot, self.bloco)

    def test_resumo_canais_e_profissao_antes_do_dependente(self):
        dados = {
            "id_conversa": 25, "nome_cliente": "Ana", "telefone_cliente": NUMERO,
            "email_cliente": "ana@example.com", "profissao": "Professora",
            "status_dependente": True, "nome_dependente": "João", "idade_dependente": 12,
            "resultado_email_fireads": "email_valido", "contexto_fireads": {"id_integracao": 1},
            "triagem_respostas": [{"id_etapa": etapa, "resposta": "nunca"} for etapa in range(12,18)],
        }
        for origem, codigo in (("google", "113336"), ("meta", "113340"), ("organico_site", "113481"), ("organico", "113481"), ("chat_fire", "113481")):
            for primeiro in (True, False, None):
                texto = montar_observacoes_lead(dict(dados, origem_fireads=origem, primeiro_atendimento=primeiro))
                classificacao = ("NOVO LEAD" if primeiro is True else
                                 "NOVO ATENDIMENTO PARA LEAD ANTIGO" if primeiro is False else "ATENDIMENTO")
                self.assertTrue(texto.startswith(
                    f"[INICIO CHATBOT:1:25]\n{classificacao} : {CANAIS[origem][0].upper()} : DEPENDENTE\n"
                ))
                self.assertNotIn("— conversa", texto)
                self.assertLess(texto.index("Profissão:"), texto.index("Nome do dependente:"))
                self.assertEqual(CANAIS[origem][1], codigo)
                self.assertIn("Com que frequência João se distrai com facilidade durante tarefas ou atividades escolares? : Nunca", texto)
                self.assertIn("Com que frequência João fica desmotivado(a), impaciente ou frustrado(a) diante de atividades que exigem concentração? : Nunca", texto)

    def test_bloco_compacto_preserva_historico_e_reconcilia_sem_repetir(self):
        antigo = bloco_observacoes(1, 24, "Histórico antigo")
        historico = "  Anotação manual preservada  \n\n" + antigo + "\n\n" + self.bloco
        compacto = bloco_observacoes(1, 26, "NOVO ATENDIMENTO PARA LEAD ANTIGO : GOOGLE ADS : TITULAR\nDados", versao=3)
        registro = dict(REGISTRO, **{"Observação": historico})
        op = preparar_escrita([registro], self.snapshot, compacto)
        self.assertEqual(op, {"row": 44, "observacoes": historico + "\n\n" + compacto})
        # Simula resposta perdida: próximo ciclo encontra exatamente o bloco enviado.
        entregue = dict(registro, _row=43, **{"Observação": op["observacoes"]})
        self.assertIsNone(preparar_escrita([entregue], self.snapshot, compacto))
        entregue["Observação"] = entregue["Observação"].replace("TITULAR", "DEPENDENTE")
        with self.assertRaises(ErroFireAds):
            preparar_escrita([entregue], self.snapshot, compacto)
```

## Passo 22 — `tests/unit/test_indicador_digitacao.py`

SHA-256 (LF): `6b345aeaa2d57b3cb6de6eda24f518482400142e7e8c4007f17bab8bd01b7d84`

```python
"""PyWa real e transporte simulado: nenhum acesso à Meta, RDS ou Redis."""

import json
import unittest
from contextlib import ExitStack
from functools import partial
from unittest.mock import patch

import httpx
from pywa import WhatsApp

from core.integrations.whatsapp.pywa_functions import cliente, digitacao
from tests.helpers import FakeConn, FakeCursor
from tests.unit import test_worker_flow_runtime as runtime
from workers.worker_consulta_dash import consulta_worker
from workers.worker_flow.response_flow.flow_sender import flow_sender
from workers.worker_flow.response_flow.retomada_followup import enviar_retorno_followup


PHONE_ID = "123456"
WAMID = "wamid.cliente.7"
TELEFONE = "5571999999999"


class HTTPMetaSimulada:
    def preparar_http(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.requisicoes = []
        self.eventos = []
        self.resposta_indicador = {"success": True}
        self.falha_indicador = None
        self.status_indicador = 200
        self.ao_indicar = None
        self.sessoes = []
        self.transporte = self.stack.enter_context(patch.object(
            digitacao.httpx, "HTTPTransport",
            side_effect=lambda **_: httpx.MockTransport(self.responder),
        ))
        self.stack.enter_context(patch.object(
            cliente, "WhatsApp", side_effect=self.criar_cliente,
        ))

    def criar_cliente(self, **kwargs):
        if "session" not in kwargs:
            sessao = httpx.Client(
                timeout=30.0, transport=httpx.MockTransport(self.responder),
            )
            self.stack.callback(sessao.close)
            kwargs["session"] = sessao
        self.sessoes.append(kwargs["session"])
        return WhatsApp(**kwargs)

    def responder(self, request):
        self.requisicoes.append(request)
        payload = json.loads(request.content)
        if "typing_indicator" in payload:
            self.eventos.append("digitacao")
            if self.ao_indicar:
                self.ao_indicar()
            if self.falha_indicador:
                raise self.falha_indicador
            return httpx.Response(self.status_indicador, json=self.resposta_indicador)
        self.eventos.append("resposta")
        return httpx.Response(200, json={
            "messaging_product": "whatsapp",
            "contacts": [{"input": TELEFONE, "wa_id": TELEFONE}],
            "messages": [{"id": "wamid.bot.7"}],
        })

    def solicitar(self):
        return digitacao.indicar_digitacao(
            PHONE_ID, WAMID, id_mensagem=7, id_conversa=10,
        )


class DigitacaoTransporteTests(HTTPMetaSimulada, unittest.TestCase):
    def setUp(self):
        self.preparar_http()

    def test_sdk_marca_entrada_lida_na_conta_correta_com_timeout_isolado(self):
        with cliente.antes_do_primeiro_envio(self.solicitar):
            wa = cliente.conta_wa(PHONE_ID)
            self.assertEqual(self.requisicoes, [])  # Criar o cliente não ativa.
            wa.send_message(to=TELEFONE, text="Olá!")
        self.assertEqual(self.eventos, ["digitacao", "resposta"])
        indicador, resposta = self.requisicoes
        self.assertTrue(indicador.url.path.endswith(f"/{PHONE_ID}/messages"))
        self.assertEqual(json.loads(indicador.content), {
            "messaging_product": "whatsapp", "status": "read",
            "message_id": WAMID, "typing_indicator": {"type": "text"},
        })
        self.assertEqual(indicador.extensions["timeout"], {
            "connect": 1.0, "read": 2.0, "write": 2.0, "pool": 1.0,
        })
        self.assertEqual(resposta.extensions["timeout"]["read"], 30.0)
        self.transporte.assert_called_once_with(retries=0)
        self.assertIsNot(self.sessoes[0], self.sessoes[1])
        self.assertTrue(self.sessoes[1].is_closed)

    def test_uma_tentativa_por_turno_mesmo_com_dois_clientes_e_prefixo(self):
        with cliente.antes_do_primeiro_envio(self.solicitar):
            with cliente.usar_prefixo_mensagem_bot("Olá novamente!\n\n"):
                cliente.conta_wa(PHONE_ID).send_message(to=TELEFONE, text="Primeira")
                cliente.conta_wa(PHONE_ID).request_contact_info(
                    to=TELEFONE, text="Segunda",
                )
        self.assertEqual(self.eventos, ["digitacao", "resposta", "resposta"])
        self.assertEqual(json.loads(self.requisicoes[1].content)["text"]["body"],
                         "Olá novamente!\n\nPrimeira")
        # Um envio fora do worker (por exemplo, proativo) não herda o indicador.
        cliente.conta_wa(PHONE_ID).send_message(to=TELEFONE, text="Fora do turno")
        self.assertEqual(self.eventos.count("digitacao"), 1)

    def test_falhas_opcionais_nao_retentam_nem_impedem_resposta(self):
        for erro, status, payload in (
            (httpx.ReadTimeout("segredo nao deve aparecer"), 200, {}),
            (httpx.ConnectError("indisponivel"), 200, {}),
            (None, 400, {"error": {"code": 100, "message": "recusado"}}),
            (None, 200, {"success": False}),
            (None, 200, {}),
        ):
            with self.subTest(erro=erro, status=status, payload=payload):
                self.eventos.clear()
                self.falha_indicador = erro
                self.status_indicador = status
                self.resposta_indicador = payload
                with patch.object(digitacao.logger, "warning") as log:
                    with cliente.antes_do_primeiro_envio(self.solicitar):
                        wa = cliente.conta_wa(PHONE_ID)
                        wa.send_message(to=TELEFONE, text="Resposta")
                        wa.send_message(to=TELEFONE, text="Complemento")
                self.assertEqual(self.eventos, ["digitacao", "resposta", "resposta"])
                log.assert_called_once()
                self.assertNotIn("segredo", str(log.call_args))
                self.assertNotIn(WAMID, str(log.call_args))
                self.assertTrue(self.sessoes[-1].is_closed)

    def test_identificadores_ausentes_ou_invalidos_omitem_apenas_indicador(self):
        for phone, wamid in ((None, WAMID), (PHONE_ID, None),
                             (PHONE_ID, 7), (PHONE_ID, "wamid.")):
            with self.subTest(phone=phone, wamid=wamid):
                with cliente.antes_do_primeiro_envio(partial(
                    digitacao.indicar_digitacao, phone, wamid,
                )):
                    cliente.conta_wa(PHONE_ID).send_message(to=TELEFONE, text="Ok")
        self.assertEqual(self.eventos, ["resposta"] * 4)
        self.transporte.assert_not_called()

    def test_escopo_restaurado_apos_excecao_e_nao_vaza_entre_unidades(self):
        with self.assertRaises(ValueError):
            with cliente.antes_do_primeiro_envio(self.solicitar):
                raise ValueError("resolver sem resposta")
        cliente.conta_wa(PHONE_ID).send_message(to=TELEFONE, text="Sem indicador")
        with cliente.antes_do_primeiro_envio(partial(
            digitacao.indicar_digitacao, "987654", "wamid.outro.cliente",
        )):
            cliente.conta_wa("987654").send_message(to=TELEFONE, text="Outra unidade")
        self.assertEqual(self.eventos, ["resposta", "digitacao", "resposta"])
        self.assertTrue(self.requisicoes[1].url.path.endswith("/987654/messages"))
        self.assertEqual(json.loads(self.requisicoes[1].content)["message_id"],
                         "wamid.outro.cliente")


class DigitacaoWorkerTests(HTTPMetaSimulada, unittest.TestCase):
    def setUp(self):
        self.preparar_http()
        self.conn = FakeConn(FakeCursor())
        runtime.WorkerFlowRuntimeTests._patch_fluxo_base(
            self, self.stack, self.conn, self.eventos,
        )
        self.contexto = dict(
            runtime.contexto_historico(), nome_unidade="Supera Teste",
            nome_agente="Dora", genero="feminino", tipo_mensagem_atual="text",
            texto_cliente_atual="Olá", status_dependente=False,
            dados_repeticao={"nome_titular": "Ana", "status_dependente": False,
                             "nome_unidade": "Supera Teste", "nome_agente": "Dora",
                             "genero": "feminino"},
        )
        self.patch("valida_historico", side_effect=lambda *_: self.contexto)
        self.patch("flow_sender", side_effect=flow_sender)
        self.patch("enviar_retorno_followup", side_effect=enviar_retorno_followup)
        self.guarda_unidade = self.patch(
            "exigir_unidade_habilitada_por_phone_id",
            side_effect=lambda *_: self.eventos.append("unidade_ok"),
        )
        self.guarda_lock = self.patch(
            "proteger_conversa", side_effect=lambda *_a, **_kw: self.eventos.append("lock_ok"),
        )
        self.persistir = self.patch(
            "atualizar_banco_com_contexto_final", return_value=runtime.contexto_final(),
        )
        self.persistir_followup = self.patch(
            "persistir_retorno_followup", return_value=runtime.contexto_final(),
        )
        self.finalizar = self.patch(
            "finalizar_mensagem_processada", return_value={"atendimento_encerrado": False},
        )
        self.patch("registrar_cache_bloqueio_apos_commit")
        self.reagendar = self.patch("reagendar_mensagem_sem_erro")
        self.erro = self.patch("handle_erro_generico")

    def patch(self, nome, **kwargs):
        return self.stack.enter_context(patch.object(runtime.flow_worker, nome, **kwargs))

    def executar(self):
        with self.assertRaises(runtime.PararWorker):
            runtime.flow_worker.worker_flow()

    def test_abertura_ativa_so_apos_guardas_e_commit_sem_alterar_persistencia(self):
        # Verifica o checkpoint sem criar uma transação para a chamada opcional.
        self.ao_indicar = lambda: self.assertEqual(self.conn.commits, 5)
        self.executar()
        indice = self.eventos.index("digitacao")
        self.assertEqual(self.eventos[indice - 2:indice], ["lock_ok", "unidade_ok"])
        self.assertEqual(self.eventos[indice:indice + 2], ["digitacao", "resposta"])
        self.persistir.assert_called_once()
        self.assertTrue(self.persistir.call_args.args[1]["enviou"])
        self.finalizar.assert_called_once()
        self.reagendar.assert_not_called()
        self.assertEqual(self.conn.commits, 8)

    def test_falha_indicador_preserva_envio_fila_e_retry(self):
        self.falha_indicador = httpx.ReadTimeout("Meta indisponivel")
        self.executar()
        self.assertIn("resposta", self.eventos)
        self.persistir.assert_called_once()
        self.finalizar.assert_called_once()
        self.reagendar.assert_not_called()
        self.erro.assert_not_called()
        self.assertEqual(self.conn.rollbacks, 0)

    def test_replay_recupera_resposta_sem_indicador_ou_reenvio(self):
        self.contexto["resposta_bot_para_mensagem_atual"] = {
            "id_etapa": 1, "id_hash_msg": "wamid.bot.7", "id_mensagem": 99,
        }
        self.executar()
        self.assertEqual(self.requisicoes, [])
        self.assertFalse(self.persistir.call_args.args[1]["enviou"])
        self.finalizar.assert_called_once()

    def test_fireads_pendente_existente_nao_ativa(self):
        self.patch("preparar_abertura", side_effect=runtime.flow_worker.ConsultaFireAdsPendente())
        self.executar()
        self.assertEqual(self.requisicoes, [])
        self.persistir.assert_not_called()
        self.reagendar.assert_called_once_with(
            7, self.conn.cursor_obj, delay_seconds=5, retry_esperado=1,
        )

    def test_fireads_nova_pendencia_ativa_apos_commit_mesmo_se_meta_falhar(self):
        self.patch("preparar_abertura", side_effect=runtime.flow_worker.ConsultaFireAdsPendente(
            consulta_nova=True,
        ))
        self.ao_indicar = lambda: self.assertEqual(self.conn.commits, 4)
        self.falha_indicador = httpx.ReadTimeout("Meta indisponivel")
        self.executar()
        self.assertEqual(self.eventos.count("digitacao"), 1)
        self.assertNotIn("resposta", self.eventos)
        self.persistir.assert_not_called()
        self.finalizar.assert_not_called()
        self.reagendar.assert_called_once()
        self.erro.assert_not_called()
        self.assertEqual(self.conn.rollbacks, 0)

    def test_pendencia_sem_commit_nao_ativa_indicador(self):
        self.patch("preparar_abertura", side_effect=runtime.flow_worker.ConsultaFireAdsPendente(
            consulta_nova=True,
        ))
        with patch.object(self.conn, "commit", side_effect=[
            None, None, None, RuntimeError("commit indisponivel"), None,
        ]):
            with self.assertRaisesRegex(RuntimeError, "commit indisponivel"):
                runtime.flow_worker.worker_flow()
        self.assertEqual(self.requisicoes, [])

    def test_fireads_tres_ativacoes_com_rechecagens_sem_repeticao(self):
        conexoes = [FakeConn(FakeCursor()) for _ in range(4)]
        self.patch("get_conn", side_effect=[
            item for conn in conexoes for item in (conn, runtime.PararWorker())
        ])
        self.patch("preparar_abertura", side_effect=[
            runtime.flow_worker.ConsultaFireAdsPendente(consulta_nova=True),
            runtime.flow_worker.ConsultaFireAdsPendente(),
            runtime.flow_worker.ConsultaFireAdsPendente(),
            runtime.contexto_banco(),
        ])
        for _ in range(3):
            self.executar()
        self.assertEqual(self.eventos.count("digitacao"), 1)
        self.assertNotIn("resposta", self.eventos)

        with ExitStack() as stack:
            preparar_consulta_simulada(stack, self.eventos)
            self.assertTrue(consulta_worker.executar_ciclo())
        self.assertEqual(self.eventos.count("digitacao"), 2)
        self.executar()
        self.assertEqual([e for e in self.eventos if e in {"digitacao", "consulta", "resposta"}],
                         ["digitacao", "digitacao", "consulta", "digitacao", "resposta"])
        self.assertEqual([json.loads(r.content)["message_id"] for r in self.requisicoes[:-1]],
                         [WAMID] * 3)
        self.persistir.assert_called_once()
        self.finalizar.assert_called_once()

    def test_fireads_concluida_ativa_para_abertura_personalizada(self):
        self.contexto["contexto_fireads"] = {
            "concluida": True, "resultado": "importado", "id_conversa": 10,
            "dados_titular": {"nome": "Ana", "email": "ana@example.test",
                              "resultado_email": "email_valido"},
        }
        self.executar()
        self.assertEqual(self.eventos.count("digitacao"), 1)
        self.assertEqual(self.persistir.call_args.args[1]["id_etapa_resultante"], 4)
        texto = json.loads(self.requisicoes[-1].content)["text"]["body"]
        self.assertIn("preencheu um dos nossos formulários", texto)

    def test_continuacao_e_reacao_followup_ativam_uma_vez(self):
        self.contexto.update(id_etapa_atual=1, retorno_followup=True,
                             texto_cliente_atual="123")
        self.patch("preparar_retorno_followup", return_value=self.contexto)
        self.executar()
        self.assertEqual(self.eventos.count("digitacao"), 1)
        self.assertEqual(self.eventos.count("resposta"), 1)
        self.persistir_followup.assert_called_once()
        self.erro.assert_not_called()

    def test_continuacao_normal_ativa_antes_de_repetir_pergunta(self):
        self.contexto.update(id_etapa_atual=1, texto_cliente_atual="123")
        self.executar()
        self.assertEqual(self.eventos.count("digitacao"), 1)
        self.assertEqual(self.eventos.count("resposta"), 1)
        self.assertEqual(self.persistir.call_args.args[1]["id_etapa_resultante"], 1)
        self.erro.assert_not_called()

    def test_followup_replay_nao_ativa(self):
        self.contexto.update(id_etapa_atual=1, retorno_followup=True,
                             resposta_bot_para_mensagem_atual={
                                 "id_etapa": 1, "id_hash_msg": "wamid.bot.7",
                             })
        self.patch("preparar_retorno_followup", return_value=self.contexto)
        self.executar()
        self.assertEqual(self.requisicoes, [])
        self.persistir_followup.assert_called_once()

    def test_etapa_sem_rota_nao_ativa(self):
        self.contexto["id_etapa_atual"] = 999
        self.executar()
        self.assertEqual(self.requisicoes, [])
        self.erro.assert_called_once()
        self.persistir.assert_not_called()

    def test_apresentacao_incompleta_nao_ativa(self):
        self.contexto.pop("nome_agente")
        self.executar()
        self.assertEqual(self.requisicoes, [])
        self.erro.assert_called_once()

    def test_guardas_rejeitadas_nao_chegam_a_meta(self):
        casos = (
            ("reagendar_se_houver_mensagem_anterior", {"return_value": True}),
            ("tentar_lock_conversa", {"return_value": (False, None)}),
            ("vincular_mensagem_fila_a_conversa", {"return_value": 0}),
            ("exigir_unidade_habilitada_por_phone_id", {
                "side_effect": [None, None, runtime.flow_worker.UnidadeDesativada()],
            }),
            ("proteger_conversa", {"side_effect": runtime.flow_worker.LockConversaPerdido()}),
            ("validar_banco_mensagem", {"return_value": dict(
                runtime.contexto_banco(), conversa={"id_conversa": 10, "estado": "bloqueada"},
            )}),
        )
        for nome, kwargs in casos:
            with self.subTest(guarda=nome):
                self.patch("get_conn", side_effect=[self.conn, runtime.PararWorker()])
                self.patch("tratar_conversa_bloqueada")
                with patch.object(runtime.flow_worker, nome, **kwargs):
                    self.executar()
                self.assertEqual(self.requisicoes, [])
                self.persistir.assert_not_called()
                self.erro.assert_not_called()


def preparar_consulta_simulada(stack, eventos):
    conn = FakeConn(FakeCursor())
    reserva = dict(id_consulta=20, id_conversa=10, versao=1, restante=290, entrada={})
    stack.enter_context(patch.object(consulta_worker, "get_conn", return_value=conn))
    reservar = stack.enter_context(patch.object(
        consulta_worker.pendencias, "reservar", return_value=reserva,
    ))
    mensagem = stack.enter_context(patch.object(
        consulta_worker.pendencias, "buscar_mensagem_aguardando", return_value={
            "id_mensagem": 7, "id_phone_unidade": PHONE_ID, "id_hash": WAMID,
        },
    ))
    stack.enter_context(patch.object(consulta_worker.pendencias, "expirar", return_value=0))
    concluir = stack.enter_context(patch.object(consulta_worker.pendencias, "concluir", return_value=True))
    liberar = stack.enter_context(patch.object(consulta_worker.pendencias, "liberar_reserva", return_value=True))
    consultar = stack.enter_context(patch.object(
        consulta_worker, "consultar", side_effect=lambda _: eventos.append("consulta")
        or {"decisao": {"resultado": "ausente"}, "fontes": {}},
    ))
    return conn, reserva, reservar, mensagem, consultar, concluir, liberar


class DigitacaoConsultaTests(HTTPMetaSimulada, unittest.TestCase):
    def setUp(self):
        self.preparar_http()
        (self.conn, self.reserva, self.reservar, self.mensagem,
         self.consultar, self.concluir, self.liberar) = preparar_consulta_simulada(
            self.stack, self.eventos,
        )

    def test_indicador_apos_commit_e_antes_da_consulta_preserva_resultado(self):
        self.ao_indicar = lambda: self.assertEqual(self.conn.commits, 3)
        self.assertTrue(consulta_worker.executar_ciclo())
        self.assertEqual(self.eventos, ["digitacao", "consulta"])
        self.concluir.assert_called_once()
        self.liberar.assert_called_once_with(20, self.conn.cursor_obj)
        self.assertEqual(self.conn.rollbacks, 0)
        self.assertTrue(self.conn.closed)

    def test_timeout_indicador_nao_impede_consulta_nem_salvamento(self):
        self.falha_indicador = httpx.ReadTimeout("Meta indisponivel")
        self.assertTrue(consulta_worker.executar_ciclo())
        self.assertEqual(self.eventos, ["digitacao", "consulta"])
        self.concluir.assert_called_once()
        self.assertEqual(self.conn.rollbacks, 0)

    def test_sem_entrada_elegivel_omite_so_indicador(self):
        self.mensagem.return_value = None
        self.assertTrue(consulta_worker.executar_ciclo())
        self.assertEqual(self.eventos, ["consulta"])
        self.concluir.assert_called_once()

    def test_sem_reserva_nao_busca_mensagem_nem_ativa(self):
        self.reservar.return_value = None
        self.assertFalse(consulta_worker.executar_ciclo())
        self.assertEqual(self.eventos, [])
        self.mensagem.assert_not_called()
        self.liberar.assert_not_called()

    def test_indicador_respeita_reserva_e_margem_de_persistencia(self):
        for inicio, fim, esperado in ((100, 103, 300), (100, 120, 295), (100, 431, 0)):
            with self.subTest(restante=esperado):
                self.reserva["restante"] = 330
                with patch.object(consulta_worker, "time") as relogio, patch.object(
                    consulta_worker, "get_conn", return_value=FakeConn(FakeCursor()),
                ):
                    relogio.monotonic.side_effect = [inicio, fim]
                    self.assertTrue(consulta_worker.executar_ciclo())
                self.assertEqual(self.consultar.call_args.args[0]["restante"], esperado)


if __name__ == "__main__":
    unittest.main()
```

## Passo 23 — `tests/integration/test_coleta_abertura_postgres.py`

SHA-256 (LF): `5b6710c0c8fdeef4abc04d983dd6807c82f820b5c00bb40e818daa75f8bf5d81`

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
        self.assertEqual(retomado['contexto_fireads']['origem'], 'organico')
        self.assertEqual(retomado['contexto_fireads']['motivo'], 'canal_pendente_entrega')

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
        self.assertEqual(externo.enviar.call_args.kwargs['dados']['Canal'], 'Orgânico')
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

## Passo 24 — `tests/integration/test_entrega_fireads_primeiro_postgres.py`

SHA-256 (LF): `b1149551b051640c8737be937ec0a16ff40fe510839cf9bb376219ad713a8eb8`

```python
"""Ordem real das filas, snapshots e recuperação; HTTP somente simulado."""

from copy import deepcopy
import unittest
from unittest.mock import Mock, patch

import psycopg
from tests.integration import test_coleta_abertura_postgres as coleta_testes
from tests.integration.test_fireads_postgres import DSN
from tests.unit.test_coleta_abertura import ROW, FORM
from core.repositories.atendimento.coleta_abertura import guardar_coletas
from core.integrations.fireads.atribuicao import CHAVE, ler
from core.integrations.fireads.cliente import TelefoneDuplicadoFireAds
from core.repositories.fireads import envios, pendencias
from core.repositories.funil.envios import sincronizar_envios_elegiveis, reivindicar_proximo_envio
from workers.worker_flow.fireads import preparar_abertura
from workers.worker_funil.processamento import processar_envio_funil
from workers.worker_flow.suporte.consultas_fireads import ConsultaFireAdsPendente


@unittest.skipUnless(DSN, 'Exige PostgreSQL descartável em loopback')
class EntregaPrimeiroTests(unittest.TestCase):
    setUp = coleta_testes.ColetaPostgresTests.setUp
    limpar = coleta_testes.ColetaPostgresTests.limpar
    nova_conversa = coleta_testes.ColetaPostgresTests.nova_conversa
    preparar_mensagem = coleta_testes.ColetaPostgresTests.preparar_mensagem
    inicio = coleta_testes.ColetaPostgresTests.inicio

    def concluida(self, fireads=True):
        cid, msg, v, ctx = self.inicio(fireads=fireads)
        ctx = preparar_abertura(ctx, msg, v, self.cursor)
        self.cursor.execute('UPDATE chatbot.conversa SET id_etapa_atual=19,profissao=%s WHERE id_conversa=%s', ('Professora', cid))
        self.cursor.execute('UPDATE chatbot.cliente SET idade=35 WHERE id_cliente=1')
        guardar_coletas({'id_conversa': cid, 'id_cliente': 1, 'contexto_coleta': ctx['contexto_coleta']},
                        {'destino_dado': 'cliente'}, self.cursor)
        self.cursor.execute("INSERT INTO chatbot.respostas_desafios(id_conversa,id_etapa,resposta) SELECT %s,e,'Às vezes' FROM generate_series(12,17) e", (cid,))
        sincronizar_envios_elegiveis(self.cursor)
        envio = reivindicar_proximo_envio(self.cursor)
        self.conn.commit()
        return cid, envio

    def simular(self, rows):
        eventos = []
        externo = Mock()

        def ler(*_):
            self.assertEqual(self.conn.info.transaction_status, psycopg.pq.TransactionStatus.IDLE)
            eventos.append('GET')
            return {'headers': list(ROW) + ['Período preferido'], 'rows': deepcopy(rows)}

        def escrever(_aba, **op):
            self.assertEqual(self.conn.info.transaction_status, psycopg.pq.TransactionStatus.IDLE)
            eventos.append('DASH')
            if 'row' in op:
                row = next(r for r in rows if r['_row'] == op['row'])
                row.update(op['campos'])
                row['Observação'] = op['observacoes']
                return {'success': True, 'row': op['row'], 'aba': _aba,
                        'updated': [*op['campos'], 'Observação']}
            rows.append(dict(op['dados'], _row=max([r['_row'] for r in rows] + [1]) + 1))
            return {'success': True, 'inserted': 1, 'aba': _aba}

        def funil(**kwargs):
            self.assertEqual(self.conn.info.transaction_status, psycopg.pq.TransactionStatus.IDLE)
            eventos.append('FUNIL')
            with psycopg.connect(DSN) as verificar:
                row = verificar.execute('SELECT status,snapshot FROM chatbot.envios_dash').fetchone()
            if row is not None:
                self.assertEqual(row[0], 'sent')
                self.assertEqual(kwargs['codigo_canal_venda'], row[1]['canal'])
                self.assertEqual(kwargs['payload'], row[1]['payload_funil'])
            return {'status_http': 200, 'resposta': {'success': True}}

        externo.consultar.side_effect = ler
        externo.enviar.side_effect = escrever
        self.enterContext(patch('workers.worker_funil.preparacao_fireads.ClienteFireAds', return_value=externo))
        self.enterContext(patch('workers.worker_funil.fireads.ClienteFireAds', return_value=externo))
        postar_funil = self.enterContext(patch('workers.worker_funil.processamento.enviar_oportunidade', side_effect=funil))
        return externo, postar_funil, eventos

    def retry(self):
        self.cursor.execute("UPDATE chatbot.funil_envios SET next_attempt_at=clock_timestamp()-INTERVAL '1 second'")
        self.cursor.execute("UPDATE chatbot.envios_dash SET next_attempt_at=clock_timestamp()-INTERVAL '1 second'")
        envio = reivindicar_proximo_envio(self.cursor)
        self.conn.commit()
        return envio

    def test_completo_resolve_chat_fire_por_telefone_e_grava_dash_antes_funil(self):
        cid, envio = self.concluida()
        rows = [dict(ROW, _row=751, Nome='Ed', Email='divergente@example.com', Canal='Chat Fire',
                     **{'Para quem é': '', 'Período preferido': 'Noite'})]
        externo, funil, eventos = self.simular(rows)
        self.assertTrue(processar_envio_funil(envio, self.conn, self.cursor))
        self.assertEqual(eventos, ['GET', 'GET', 'DASH', 'FUNIL'])
        self.assertEqual(rows[0]['Nome'], 'Ana Paula Silva')
        self.assertEqual(rows[0]['Período preferido'], 'Tarde')
        self.assertEqual(rows[0]['Canal'], 'Chat Fire')
        self.assertTrue(rows[0]['Observação'].startswith(ROW['Observação']))
        self.assertIn('CHAT FIRE', rows[0]['Observação'])
        self.assertEqual(funil.call_args.kwargs['codigo_canal_venda'], '113481')
        self.assertEqual(self.conn.execute('SELECT count(*) FROM chatbot.consulta_fireads').fetchone()[0], 0)
        self.assertEqual(self.conn.execute('SELECT origem_fireads,lead_no_dash,lead_no_funil FROM chatbot.conversa WHERE id_conversa=%s', (cid,)).fetchone(), ('chat_fire', True, True))

    def test_get_timeout_nao_congela_origem_nem_envia_nem_cria(self):
        cid, envio = self.concluida()
        externo, funil, eventos = self.simular([])
        externo.consultar.side_effect = TimeoutError('Leitura indisponível')
        self.assertFalse(processar_envio_funil(envio, self.conn, self.cursor))
        funil.assert_not_called()
        externo.enviar.assert_not_called()
        self.assertEqual(self.conn.execute('SELECT count(*) FROM chatbot.envios_dash').fetchone()[0], 0)
        self.assertEqual(self.conn.execute('SELECT status,snapshot FROM chatbot.funil_envios').fetchone(), ('pending', None))

    def test_post_com_resposta_perdida_reconcilia_destino_e_so_depois_envia_funil(self):
        cid, envio = self.concluida()
        rows = [dict(ROW, Canal='Chat Fire', **{'Período preferido': 'Noite'})]
        externo, funil, eventos = self.simular(rows)
        escrever = externo.enviar.side_effect

        def perder_resposta(*args, **kwargs):
            escrever(*args, **kwargs)
            raise TimeoutError('Gravou e perdeu resposta')

        externo.enviar.side_effect = perder_resposta
        self.assertFalse(processar_envio_funil(envio, self.conn, self.cursor))
        funil.assert_not_called()
        congelado = self.conn.execute('SELECT snapshot FROM chatbot.envios_dash').fetchone()[0]
        # Novo cadastro e edição local não mudam o destino de uma entrega iniciada.
        rows.append(dict(ROW, _row=999, Canal='Google Ads', **{'Período preferido': 'Manhã'}))
        self.assertTrue(processar_envio_funil(self.retry(), self.conn, self.cursor))
        self.assertEqual(externo.enviar.call_count, 1)
        self.assertEqual(rows[0]['Observação'].count('[INICIO CHATBOT:'), 1)
        self.assertEqual(rows[1]['Observação'], ROW['Observação'])
        self.assertEqual(self.conn.execute('SELECT snapshot FROM chatbot.envios_dash').fetchone()[0], congelado)
        self.assertEqual(funil.call_args.kwargs['codigo_canal_venda'], '113481')

    def test_somente_manuais_cria_organico_e_retry_funil_nao_reenvia_dashboard(self):
        cid, envio = self.concluida()
        rows = [dict(ROW, Canal='Indicação'), dict(ROW, _row=45, Canal='Lead Franqueador')]
        antes = deepcopy(rows)
        externo, funil, eventos = self.simular(rows)
        sucesso_funil = funil.side_effect
        funil.side_effect = TimeoutError('Funil indisponível')
        self.assertFalse(processar_envio_funil(envio, self.conn, self.cursor))
        self.assertEqual(rows[:2], antes)
        self.assertEqual(rows[2]['Canal'], 'Orgânico')
        self.assertEqual(self.conn.execute('SELECT status FROM chatbot.envios_dash').fetchone()[0], 'sent')
        funil.side_effect = sucesso_funil
        self.assertTrue(processar_envio_funil(self.retry(), self.conn, self.cursor))
        self.assertEqual(externo.enviar.call_count, 1)
        self.assertEqual(externo.consultar.call_count, 2)
        self.assertEqual(funil.call_args.kwargs['codigo_canal_venda'], '113481')

    def test_sem_fireads_envia_direto_com_codigo_da_unidade(self):
        cid, envio = self.concluida(fireads=False)
        externo, funil, eventos = self.simular([])
        self.assertTrue(processar_envio_funil(envio, self.conn, self.cursor))
        externo.consultar.assert_not_called()
        externo.enviar.assert_not_called()
        self.assertEqual(funil.call_args.kwargs['codigo_canal_venda'], '113340')

    def test_anuncio_confirmado_no_banco_e_snapshot_sem_consulta_inicial(self):
        cid, envio = self.concluida()
        contexto = self.conn.execute('SELECT contexto_fireads FROM chatbot.conversa WHERE id_conversa=%s', (cid,)).fetchone()[0]
        self.assertIsNone(ler(contexto, cid))
        self.conn.commit()
        rows = [dict(ROW, Canal='Meta Ads', Anuncio='QR001 [form-8.0]', **{'Período preferido': ''})]
        self.simular(rows)
        self.assertTrue(processar_envio_funil(envio, self.conn, self.cursor))
        ctx = self.conn.execute('SELECT contexto_fireads FROM chatbot.conversa WHERE id_conversa=%s', (cid,)).fetchone()[0]
        snap = self.conn.execute('SELECT snapshot FROM chatbot.envios_dash').fetchone()[0]
        self.assertEqual(ler(ctx, cid)['anuncio'], 'QR001 [form-8.0]')
        self.assertEqual(snap[CHAVE], ctx[CHAVE])
        self.assertEqual(ctx['id_conversa'], cid)

    def test_so_organico_cria_novo_e_resposta_perdida_reconcilia_sem_duplicar(self):
        cid, envio = self.concluida()
        rows = [dict(ROW, Canal='Orgânico')]
        antigo = deepcopy(rows[0])
        externo, funil, _ = self.simular(rows)
        escrever = externo.enviar.side_effect
        def perder(*args, **kwargs):
            escrever(*args, **kwargs)
            raise TimeoutError('Resposta perdida')
        externo.enviar.side_effect = perder
        self.assertFalse(processar_envio_funil(envio, self.conn, self.cursor))
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0], antigo)
        self.assertTrue(processar_envio_funil(self.retry(), self.conn, self.cursor))
        externo.enviar.assert_called_once()
        self.assertEqual(len(rows), 2)

    def test_duplicidade_explicita_recupera_atualizando_so_o_organico(self):
        cid, envio = self.concluida()
        rows = [dict(ROW, Canal='Orgânico', **{'Período preferido': ''}), dict(ROW, _row=99, Canal='Indicação')]
        externo, funil, _ = self.simular(rows)
        escrever = externo.enviar.side_effect
        externo.enviar.side_effect = TelefoneDuplicadoFireAds('Telefone duplicado')
        self.assertFalse(processar_envio_funil(envio, self.conn, self.cursor))
        funil.assert_not_called()
        snap = self.conn.execute('SELECT snapshot FROM chatbot.envios_dash').fetchone()[0]
        self.assertTrue(snap['append_recusado_duplicidade'])
        externo.enviar.side_effect = escrever
        self.assertTrue(processar_envio_funil(self.retry(), self.conn, self.cursor))
        self.assertEqual(externo.enviar.call_args.kwargs['row'], 44)
        self.assertEqual(rows[1]['Observação'], ROW['Observação'])
        self.assertEqual(len(rows), 2)

    def test_consulta_inicial_captura_anuncio_mesmo_com_dados_parciais(self):
        cid, msg, v, ctx = self.inicio('Olá')
        with self.assertRaises(ConsultaFireAdsPendente):
            preparar_abertura(ctx, msg, v, self.cursor)
        self.conn.commit()
        coleta_testes.ColetaPostgresTests.concluir(self, [dict(ROW, Canal='Meta Ads', Anuncio='QR002', Email='')])
        novo = preparar_abertura(ctx, msg, v, self.cursor)
        self.conn.commit()
        self.assertEqual(ler(novo['contexto_fireads'], cid)['anuncio'], 'QR002')
        self.assertNotEqual(novo['contexto_coleta']['campos']['email']['status'], 'aceito')

    def test_reserva_apos_fila_recebe_300s_e_margem_sem_disputa(self):
        cid, msg, v, ctx = self.inicio('Oi')
        with self.assertRaises(ConsultaFireAdsPendente):
            preparar_abertura(ctx, msg, v, self.cursor)
        self.cursor.execute("UPDATE chatbot.consulta_fireads SET prazo_final=clock_timestamp()+INTERVAL '1 second'")
        self.conn.commit()
        reserva = pendencias.reservar(self.cursor)
        self.conn.commit()
        self.assertGreater(float(reserva['restante']), 325)
        with psycopg.connect(DSN) as outra:
            self.assertIsNone(pendencias.reservar(outra.cursor()))
        pendencias.liberar_reserva(reserva['id_consulta'], self.cursor)
        self.conn.commit()

    def test_reserva_dash_nao_expira_aos_tres_minutos(self):
        cid, envio = self.concluida()
        externo, funil, eventos = self.simular([])
        externo.enviar.side_effect = TimeoutError('Sem recibo')
        self.assertFalse(processar_envio_funil(envio, self.conn, self.cursor))
        self.cursor.execute("UPDATE chatbot.envios_dash SET status='processing',processing_started_at=clock_timestamp()-INTERVAL '5 minutes'")
        self.conn.commit()
        self.assertIsNone(envios.reservar(self.cursor))
        self.conn.commit()
```

## Passo 25 — `core/integrations/fireads/atribuicao.py`

SHA-256 (LF): `c26586d0424ee0900a8e491f18b2f07865d3bc8e2a39adc1b08cae024b2d2ae8`

```python
"""Atribuição comprovada do atendimento; não infere campanha por código do Funil."""

from copy import deepcopy
from datetime import datetime, timezone

from .aba_geral import ORIGENS, CAMPOS_IDENTIDADE, referencia_registro
from .contrato import normalizar

CHAVE = 'atribuicao_monitoramento'
CANAIS_FORMULARIO = frozenset({'google', 'meta', 'organico_site', 'chat_fire'})
ROTULOS = {'google': 'Google Ads', 'meta': 'Meta Ads', 'organico_site': 'Orgânico Site',
           'chat_fire': 'Chat Fire', 'organico': '100% orgânico'}


def capturar(row, aba, fuso=None, *, momento='consulta_inicial'):
    canal = ORIGENS.get(normalizar(row.get('Canal'))) if row is not None else 'organico'
    if canal not in ROTULOS:
        raise ValueError('Não atribuir canal desconhecido')
    anuncio = str(row.get('Anuncio') or '').strip() if row is not None and canal == 'meta' else ''
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
        if canal == 'meta' and len(linha or iguais) == 1:
            anuncio = (linha or iguais)[0].get('Anuncio')
    anuncio = ' '.join(str(anuncio or '').split()) if canal == 'meta' else ''
    return {'canal': canal, 'rotulo': ROTULOS[canal], 'fireads': canal in CANAIS_FORMULARIO,
            'anuncio': anuncio or None}
```

## Passo 26 — `core/repositories/fireads/consulta.py`

SHA-256 (LF): `efdb9c04f188f4660af5da87b46d3e82512bd627fe73691c5a5e9807216706ad`

```python
"""SQL FireAds; o orquestrador controla commits e as chamadas externas."""

from psycopg.errors import UniqueViolation
from psycopg.types.json import Jsonb
from core.integrations.fireads.atribuicao import CHAVE, vincular

from core.repositories.atendimento.dependentes import inserir_dependente_para_conversa
from core.repositories.atendimento.followup import LockConversaPerdido


def proteger_mensagem_abertura(mensagem, cursor):
    """Só o dono atual da mensagem pode confirmar os dados obtidos na FireAds."""
    cursor.execute(
        """SELECT id_mensagem FROM chatbot.fila_mensagens
        WHERE id_mensagem=%s AND status='processing' AND retry_count=%s
          AND processing_started_at>clock_timestamp()-INTERVAL '120 seconds' FOR UPDATE""",
        (mensagem["id_mensagem"], mensagem["retry_count"]),
    )
    if cursor.fetchone() is None:
        raise LockConversaPerdido("Mensagem perdeu a reserva durante consulta FireAds")


def importar_dados_abertura(id_cliente, id_conversa, decisao, cursor):
    """Importa titular e destino juntos; conflito de e-mail não deixa dados parciais."""
    cursor.execute("SAVEPOINT fireads_importacao")
    try:
        dados = decisao["dados_titular"]
        cursor.execute(
            "UPDATE chatbot.cliente SET nome=%s,email=%s WHERE id_cliente=%s",
            (dados["nome"], dados["email"], id_cliente),
        )
        cursor.execute(
            "UPDATE chatbot.conversa SET status_dependente=%s WHERE id_conversa=%s",
            (decisao["status_dependente"], id_conversa),
        )
        if decisao["status_dependente"]:
            inserir_dependente_para_conversa(id_conversa, cursor)
    except UniqueViolation:
        cursor.execute("ROLLBACK TO SAVEPOINT fireads_importacao")
        return False
    finally:
        cursor.execute("RELEASE SAVEPOINT fireads_importacao")
    return True


def buscar_abertura(id_conversa, cursor):
    cursor.execute(
        """
        SELECT c.id_chat,c.id_cliente,c.id_unidade,c.id_etapa_atual,
               c.contexto_fireads,c.origem_fireads,i.id_integracao_fireads,
               i.url_dashbord,i.aba_destino,i.fuso_formularios,
               (u.status_pagamento IS TRUE AND i.integracao_ativa AND i.contrato_validado
                AND c.iniciou_em >= i.ativada_em) AS aplicavel, c.contexto_coleta, u.status_pagamento,
               NULLIF(BTRIM(ac.link_agendamento), '')
        FROM chatbot.conversa c JOIN chatbot.unidade u ON u.id_unidade=c.id_unidade
        JOIN chatbot.atendimento_customizado ac ON ac.id_unidade=u.id_unidade
        LEFT JOIN chatbot.integracao_fireads i
          ON i.id_unidade=c.id_unidade WHERE c.id_conversa=%s;
    """,
        (id_conversa,),
    )
    row = cursor.fetchone()
    if row is None:
        raise ValueError("Conversa inexistente")
    return dict(
        zip(
            (
                "id_chat",
                "id_cliente",
                "id_unidade",
                "etapa",
                "contexto",
                "origem",
                "id_integracao",
                "url",
                "aba",
                "fuso",
                "aplicavel",
                "coleta",
                "unidade_ativa",
                "link_agendamento",
            ),
            row,
        )
    )


def aplicar_decisao(abertura, id_conversa, id_consulta, decisao, cursor):
    """Importação, snapshot da conversa e marcador são confirmados pelo fluxo."""
    decisao = dict(
        decisao,
        id_consulta=id_consulta,
        id_integracao=abertura["id_integracao"],
        concluida=True,
        id_conversa=id_conversa,
    )
    if decisao.get(CHAVE):
        decisao[CHAVE] = vincular(decisao[CHAVE], id_conversa)
    cursor.execute(
        """UPDATE chatbot.conversa SET origem_fireads=%s,contexto_fireads=%s
        WHERE id_conversa=%s AND id_etapa_atual IS NULL AND contexto_fireads IS NULL
          AND status_ativa AND finalizou_em IS NULL""",
        (decisao["origem"], Jsonb(decisao), id_conversa),
    )
    if cursor.rowcount != 1:
        raise LockConversaPerdido("A abertura já foi aplicada ou a conversa avançou")
    return decisao


def guardar_coletas(contexto, efeitos, cursor):
    """Captura dados aceitos nesta transação, nunca cadastro de conversa antiga."""
    if not contexto.get("contexto_fireads") or not efeitos:
        return
    campos = []
    if efeitos.get("cliente_nome_atualizado"):
        campos.append("nome")
    if efeitos.get("destino_dado") == "cliente":
        campos.append("idade")
    if efeitos.get("cliente_email_atualizado"):
        campos.append("email")
    if not campos:
        return
    cursor.execute(
        "SELECT nome,idade,email FROM chatbot.cliente WHERE id_cliente=%s",
        (contexto["id_cliente"],),
    )
    valores = dict(zip(("nome", "idade", "email"), cursor.fetchone()))
    dados = {c: valores[c] for c in campos}
    if "email" in campos:
        dados["resultado_email"] = efeitos["resultado_coleta_email"]
    cursor.execute(
        """UPDATE chatbot.conversa SET contexto_fireads=jsonb_set(
        contexto_fireads,'{dados_titular}',
        COALESCE(contexto_fireads->'dados_titular','{}'::jsonb) || %s)
        WHERE id_conversa=%s AND contexto_fireads IS NOT NULL;""",
        (Jsonb(dados), contexto["id_conversa"]),
    )
```

## Passo 27 — `workers/worker_consulta_dash/resultado.py`

SHA-256 (LF): `537ddf8a0e3a312b924f04d7b8723d03ca30e3a2b78dcb3f76dd0d30a8cde737`

```python
"""Interpretação da consulta inicial; não executa HTTP nem operações de banco."""

from core.integrations.fireads.contrato import ABA_DESTINO, destino, normalizar
from core.integrations.fireads.aba_geral import (
    ORIGENS, VERSAO_CONSULTA, selecionar_registro, mais_recente, referencia_registro,
)
from core.integrations.fireads.extratores import extrair_email, extrair_nome
from core.integrations.fireads.atribuicao import CHAVE, capturar


def decisao_organica(resultado, motivo=None, *, referencia=None):
    return {
        "resultado": resultado,
        "origem": "organico",
        "motivo": motivo,
        "dados_titular": {},
        "referencia": referencia,
    }


def _interpretar(rows, numero, fuso=None, *, aba=ABA_DESTINO):
    row, encontrados = selecionar_registro(rows, numero, fuso)
    alvo_entrega = row if row is not None else mais_recente(encontrados, fuso)
    referencia = referencia_registro(alvo_entrega, aba, fuso)
    if row is None:
        return decisao_organica(
            "ausente", "canal_nao_elegivel" if encontrados else "telefone_ausente",
            referencia=referencia,
        )
    origem = ORIGENS[normalizar(row.get("Canal"))]
    nome = extrair_nome(row.get("Nome"))
    email = extrair_email(row.get("Email"))
    alvo = row.get("Para quem é")
    dependente = destino(alvo)
    if not nome or not email or not str(alvo or "").strip():
        return decisao_organica("incompleto", "campos_ausentes", referencia=referencia)
    if dependente is None:
        # Uma opção fora do contrato não autoriza inventar titular/dependente.
        return decisao_organica("incompleto", "destinatario_desconhecido", referencia=referencia)
    return {
        "resultado": "importado",
        "origem": origem,
        "status_dependente": dependente,
        "id_registro_origem": str(row.get("id") or ""),
        "data_formulario": referencia["data_interpretada"],
        "referencia": referencia,
        "versao": VERSAO_CONSULTA,
        "dados_titular": {
            "nome": nome,
            "email": email,
            # Marcador histórico da coleta; na FireAds a fonte é o formulário.
            "resultado_email": "email_valido",
        },
    }


def interpretar(rows, numero, fuso=None, *, aba=ABA_DESTINO):
    from core.integrations.fireads.aba_geral import selecionar_entrega
    row = selecionar_entrega(rows, numero, fuso)
    decisao = _interpretar(rows, numero, fuso, aba=aba)
    decisao[CHAVE] = capturar(row, aba, fuso)
    return decisao
```

## Passo 28 — solicitar à FireAds a liberação das colunas editáveis

Este é o último passo do plano. As permissões são as mesmas exigidas na V1.15.0; se a FireAds já as publicou, basta preservar o contrato. Não é
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
