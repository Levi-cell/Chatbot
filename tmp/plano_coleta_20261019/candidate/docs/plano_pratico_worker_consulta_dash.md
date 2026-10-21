# Plano prático — worker de consulta FireAds

**Nota posterior à aplicação:** a seleção de formulários foi corrigida para usar
o registro mais recente, sem resultado novo de ambiguidade. Os blocos abaixo
registram a entrega V1.11.0; não reaplicá-los sobre a correção. A regra atual está
em `docs/valida_dados_parciais_fireads.md` e em `core/integrations/fireads/contrato.py`.

Data: 09/10/2026. **Plano aplicado ao projeto local após o backup `b049a4d`; implantação na VM e migração do banco de produção ainda pendentes.**

Os 29 passos foram conferidos com a base do backup e aplicados. Na validação do
código aplicado, passaram novamente 443 testes unitários e 28 testes de integração
FireAds com PostgreSQL local descartável; `manage.py check` não apontou problemas.
As chamadas externas foram simuladas. Não houve alteração no banco/cache de
produção nem instalação de serviço na VM. O SQL para o DBeaver está no último
passo e em `deploy/migrations/20261009_worker_consulta_dash.sql`.

Este plano complementa a integração FireAds e substitui a proposta local de tarefa
auxiliar em memória. A referência implantada informada é V1.10.2 (`404a7ab`). Foram
consideradas também as alterações locais de timeout e interpretação já existentes.
Os dois primeiros passos incluem essas dependências completas; não pressupõem que
elas já tenham sido implantadas. Não alterar a versão do projeto até decidir a entrega.

Cada passo abaixo contém o conteúdo COMPLETO do arquivo indicado, sem recortes ou
trechos a completar. Ao aplicar, criar/substituir esse arquivo. Copiar todas as mudanças
antes de iniciar serviços: a numeração organiza a implementação, não autoriza executar
uma versão intermediária. O SQL está integralmente no último passo. Arquivos não
listados, inclusive migrações históricas, mantêm o conteúdo atual.

### Comportamento aprovado

- Consultar uma única vez logicamente, no começo de cada conversa nova elegível.
- Conversa já iniciada não consulta novamente em nenhuma etapa e não retrocede.
- A conversa é criada antes da solicitação; nenhum desses cadastros envia saudação.
- O `worker_flow` registra a consulta, mantém a entrada aguardando e atende outros clientes.
- O `worker_consulta_dash` procura pendências no banco a cada 2 segundos quando ocioso.
  Faz somente leitura FireAds e salva o resultado; não envia mensagem nem muda etapa.
- Há um `id_consulta` por `id_conversa`, imposto pelo banco. O chat é obtido pela conversa.
  Uma nova conversa do mesmo chat tem outro ID; uma tentativa após queda reutiliza o ID.
- O resultado das duas abas é confirmado de uma vez. Não há gravação parcial de Google
  antes de Meta; são guardados os registros relevantes ao telefone, sem copiar a planilha.
- O prazo de 300 segundos inclui fila e reexecuções. Resultado confirmado antes do prazo
  pode ser aplicado depois. Resultado tardio não substitui uma decisão já concluída.
- Google/Meta válido inicia na profissão (etapa 4). Ausência, incompletude, ambiguidade,
  erro ou timeout segue organicamente, mantendo o motivo no banco.
- Todas as mudanças de unidade, Funil, follow-up, consumo e etapas fora dessa abertura
  conservam as regras atuais. Não há nova view. O SQL de runtime novo ou alterado
  desta funcionalidade fica nos repositories; migração/DDL e utilitários mantêm suas pastas.

### Estados e pontos de recuperação

```text
Mensagem aceita → flow cria/reutiliza chat e conversa
    → solicita consulta pendente (UNIQUE por conversa)
    → confirma solicitação + espera na fila, sem consumir retry

consulta_dash reserva → consulta Google e Meta → confirma resultado completo

flow retoma a mesma mensagem → aplica resultado uma vez
    → importa dados ou segue orgânico → envia abertura
    → demais etapas continuam sem novas consultas
```

Criar conversa e criar consulta podem ser checkpoints separados no fluxo existente.
Queda entre eles conserva a mensagem e a conversa; o retry cria só a solicitação que
falta. A importação e seu marcador são atômicos. Esperar consulta nunca usa o tratamento
de erro que esgota tentativas da mensagem. O webhook mantém sua regra atual de um turno:
mensagens adicionais antes da resposta da primeira entrada podem ser descartadas na
admissão; esta mudança não introduz agregação de textos durante a espera.

A reserva de consulta usa advisory lock da mesma sessão PostgreSQL, liberado no
fechamento ou queda da conexão, além de versão e prazo persistidos. O banco fica sem
transação aberta durante HTTP. Somente o dono vigente pode confirmar. O flow continua
com o lock próprio da conversa e as guardas de fila. São responsabilidades diferentes.

| Queda ou disputa | Recuperação prevista |
| --- | --- |
| Antes de confirmar a solicitação | A mensagem permite reconstruir e solicitar novamente. |
| Depois da solicitação, antes de consultar | O novo worker encontra a pendência no banco. |
| Durante HTTP / antes de salvar o resultado | Refaz a leitura completa, usando o mesmo ID e prazo restante. |
| Depois de salvar o resultado | O flow usa o resultado persistido; não chama a FireAds novamente. |
| Durante a importação | Rollback de dados/contexto/marcador; próxima tentativa reaplica juntos. |
| Resposta de tentativa antiga ou após timeout | Recusada pela versão/estado/prazo; nenhuma etapa é alterada. |
| Consulta concluída e conversa em qualquer etapa | Nunca volta para pendente e não reinicia a conversa. |
| WhatsApp aceitou envio e o banco caiu antes de salvar | Mantém a janela conhecida de possível mensagem duplicada. |

### Aplicação e validação

As orientações operacionais completas, incluindo instalação e início do serviço, estão
no passo `docs/valida_dados_parciais_fireads.md`. Parar webhook e workers antes de combinar
código novo e migração. Não reaplicar o setup em produção. Não reverter somente o código
depois da migração: a estrutura nova não é compatível com o código antigo.

Uma instância processa uma consulta por vez; isto não acelera o Apps Script. Em picos,
a fila pode consumir o prazo e resultar em atendimento orgânico. A reserva permite
avaliar mais instâncias no futuro; não são criadas nesta proposta. O prazo controla a
aceitação do resultado, não garante interrupção física instantânea de qualquer socket.
O flow não fica dependente dessa interrupção para concluir o timeout.

O histórico antigo é preservado como existe. A tabela anterior substituía a última
consulta do chat: não há como inventar resultados antigos que não foram guardados.
Snapshots das conversas antigas não são reescritos pela migração.

Não há promessa de ausência absoluta de bugs: as garantias abaixo são sustentadas pelos
testes executados e pelas restrições do banco. HTTP externo foi simulado; não houve
envio para WhatsApp, Funil ou dashboard nem alteração de banco/cache de produção.

### Validação executada em 09/10/2026

**471 testes passaram, sem falhas, erros ou testes pulados:**

- 443 testes da suíte unitária, incluindo fluxo de atendimento, FireAds, follow-up,
  painel/Admin, consumo Meta, Funil, formatos de telefone e tratamento das etapas.
- 28 testes de integração FireAds com PostgreSQL 17.11 local descartável: SQL real,
  migração e reexecução com legado, disputa de reserva entre conexões simultâneas,
  queda antes do commit, recuperação sem resultado parcial, versão antiga recusada,
  prazo não renovado, resultado salvo em tempo aplicado posteriormente, suspensão,
  preservação do histórico, unicidade e todas as 24 etapas sem reconsulta.
- `manage.py check`: nenhum problema identificado nos models, Admin e aplicação.
- Sintaxe e integridade dos 29 blocos: conteúdo completo conferido contra a cópia
  validada; SQL de migração confirmado no último passo.

As chamadas externas foram simuladas. Não foram executadas as demais suítes de
integração PostgreSQL de outros domínios nesta rodada; os 443 testes unitários incluem
as regressões desses componentes. O novo serviço não foi instalado na VM. Não houve
consulta a dados reais nem alteração no banco/cache de produção.

Dependências auxiliares de validação ficaram em pasta isolada sob utilitarios.
O runtime proposto não exige nova dependência de produção; o PDF dos testes usou
svglib 1.5.1, versão já declarada no projeto. O PostgreSQL local é descartável e não
faz parte da entrega. Não copiar a pasta de testes temporária para a VM.

Comandos para repetir em ambiente de desenvolvimento, com dependências do projeto
instaladas e FIREADS_TEST_DSN apontando para banco vazio test_chatbot_fireads em loopback:

```powershell
python -m unittest discover -s tests/unit -t . -q
python -m unittest tests.integration.test_fireads_postgres -v
```

A suíte PostgreSQL recusa banco fora de loopback, nome divergente e schema chatbot
preexistente. Sem FIREADS_TEST_DSN, os testes serão pulados; isso não equivale a aprovação.


### Índice dos arquivos

1. `core/integrations/fireads/cliente.py`
2. `core/integrations/fireads/contrato.py`
3. `core/repositories/fireads/pendencias.py`
4. `core/repositories/fireads/consulta.py`
5. `workers/worker_consulta_dash/__init__.py`
6. `workers/worker_consulta_dash/resultado.py`
7. `workers/worker_consulta_dash/consulta.py`
8. `workers/worker_consulta_dash/consulta_worker.py`
9. `workers/worker_consulta_dash/iniciar_worker_consulta_dash.py`
10. `workers/worker_flow/suporte/consultas_fireads.py`
11. `workers/worker_flow/fireads.py`
12. `workers/worker_flow/response_flow/flow_worker.py`
13. `callback/webhook/models.py`
14. `callback/webhook/admin.py`
15. `core/database/deploy_database/fireads_script.py`
16. `tests/fixtures/fireads.py`
17. `tests/unit/test_fireads.py`
18. `tests/unit/test_fireads_espera.py`
19. `tests/unit/test_worker_flow_runtime.py`
20. `tests/integration/test_fireads_postgres.py`
21. `utilitarios/fireAds/diagnostico_abertura.py`
22. `deploy/systemd/chatbot-worker-consulta-dash.service`
23. `docs/valida_dados_parciais_fireads.md`
24. `workers/README.md`
25. `PADROES_DE_ARQUITETURA.md`
26. `tests/README.md`
27. `deploy/README.md`
28. `docs/fireads_aplicacao_e_deploy.md`
29. `deploy/migrations/20261009_worker_consulta_dash.sql`

## Passo 1: `core/integrations/fireads/cliente.py`

Preservar o orçamento HTTP compartilhado e os limites de escrita existentes.

````python
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

    def enviar(self, aba, *, dados=None, row=None, observacoes=None):
        if row is None:
            payload = {"action": "append", "sheet": aba, "rows": [dados]}
        else:
            payload = {
                "sheet": aba,
                "row": int(row),
                "updates": {"Observação": observacoes},
            }
        result = self._json(self._request("POST", self.url, json=payload))
        if result.get("aba") != aba:
            raise ErroFireAds("Recibo de outra aba")
        if row is None:
            if result.get("inserted") != 1:
                raise ErroFireAds("Cadastro sem confirmação de uma linha")
        elif result.get("row") != row or "Observação" not in result.get("updated", []):
            raise ErroFireAds("Update sem confirmação da linha/coluna")
        return result
````

## Passo 2: `core/integrations/fireads/contrato.py`

Preservar normalização de telefone, escolha de origem e tratamento de formulários idênticos.

````python
"""Regras puras de origem, telefone e composição sem perda de observações."""

import re
import unicodedata
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

ABA_GOOGLE = "Leads Google Ads (NÃO EDITAR)"
ABA_META = "[FIRE] Leads Ads Geral - 7.2"
ABA_DESTINO = "LEADS GERAL - Feedback"
CANAIS = {
    "google": ("Google Ads", "113336"),
    "meta": ("Meta Ads", "113340"),
    "organico": ("Orgânico", "113481"),
}


class ErroFireAds(ValueError):
    """Contrato incompleto, identidade ambígua ou conflito externo."""


def normalizar(texto):
    base = unicodedata.normalize("NFKD", str(texto or "").lower())
    return " ".join(
        re.sub(
            r"[^a-z0-9]+", " ", "".join(c for c in base if not unicodedata.combining(c))
        ).split()
    )


def telefone(valor):
    texto = str(valor or "").strip()
    numero = re.sub(r"\D", "", texto)
    # Um DDI explícito estrangeiro não pode virar DDD brasileiro por ter 11 dígitos.
    if "+" in texto and (len(numero) not in (12, 13) or not numero.startswith("55")):
        return None
    if len(numero) in (10, 11):
        numero = "55" + numero
    if not re.fullmatch(r"55[1-9]\d\d{8,9}", numero):
        return None
    return numero


def formatos_telefone(valor):
    """Número exato primeiro, seguido da variante móvel do nono dígito.

    Preserva DDI, DDD e os oito dígitos restantes. A alternativa segue a regra
    já usada no utilitário: não transformar números fixos em celulares.
    """
    exato = telefone(valor)
    if not exato:
        return ()
    nacional = exato[2:]
    if len(nacional) == 10 and nacional[2] in "6789":
        return exato, f"55{nacional[:2]}9{nacional[2:]}"
    if len(nacional) == 11 and nacional[2] == "9" and nacional[3] in "6789":
        return exato, f"55{nacional[:2]}{nacional[3:]}"
    return (exato,)


def identidade_telefone(valor):
    """Unifica apenas a chave do lock; não altera o número salvo ou enviado."""
    return max(formatos_telefone(valor), key=len, default=None)


def localizar(rows, numero, coluna, *, incluir_equivalentes=False):
    """Prefere o exato; a escrita examina também variantes para detectar duplicados."""
    formatos = formatos_telefone(numero)
    if not formatos:
        raise ErroFireAds("Telefone fora do contrato brasileiro")
    por_formato = {formato: [] for formato in formatos}
    for row in rows:
        normalizado = telefone(row.get(coluna))
        if normalizado in por_formato:
            por_formato[normalizado].append(row)
    if incluir_equivalentes:
        return [row for formato in formatos for row in por_formato[formato]]
    return next((por_formato[f] for f in formatos if por_formato[f]), [])


def destino(valor):
    chave = normalizar(valor)
    if chave == "para mim":
        return False
    dependentes = {
        # Valores do formulário e identificadores serializados pela Meta.
        "pai ou mae",
        "filho ou filha",
        "para meu pai mae",
        "para meu pai ou minha mae",
        "para meu avo avo",
        "para meu avo ou minha avo",
        "para outra pessoa",
        "para meu filho ou filha",
        "para meu filho minha filha",
        "para meu filho filha",
        "para mim e outra pessoa",
        "mim e outra",
    }
    return True if chave in dependentes else None


def instante(valor, fuso=None):
    texto = str(valor or "").strip()
    try:
        data = datetime.fromisoformat(texto.replace("Z", "+00:00"))
    except ValueError:
        try:
            data = datetime.strptime(texto, "%d/%m/%Y %H:%M")
        except ValueError:
            return None
    if data.tzinfo is None:
        if not fuso:
            return None
        data = data.replace(tzinfo=ZoneInfo(fuso))
    return data.astimezone(timezone.utc)


def selecionar(google, meta, numero, fuso=None):
    """Escolhe um registro inteiro; sem combinar dados de diferentes formulários."""
    candidatos = [
        ("google", r, instante(r.get("Data/Hora"), fuso))
        for r in localizar(google, numero, "WhatsApp")
    ]
    candidatos += [
        ("meta", r, instante(r.get("created_time"), fuso))
        for r in localizar(meta, numero, "phone_number")
    ]
    # Formulários repetidos da mesma origem/data não criam dúvida quando todos
    # os dados usados na importação são iguais. Não vale para escrita no dash.
    unicos = []
    for origem, row, data in candidatos:
        campos = (
            ("Nome", "Email", "Perfil/Faixa", "Data/Hora")
            if origem == "google"
            else ("full_name", "email", "para_quem", "created_time")
        )
        if not any(
            origem == anterior_origem
            and all(row.get(c) == anterior.get(c) for c in campos)
            for anterior_origem, anterior, _ in unicos
        ):
            unicos.append((origem, row, data))
    candidatos = unicos
    if not candidatos:
        return None
    if len(candidatos) == 1:
        return candidatos[0]
    if any(c[2] is None for c in candidatos):
        raise ErroFireAds("Datas insuficientes para comparar formulários")
    candidatos.sort(key=lambda c: c[2], reverse=True)
    if candidatos[0][2] == candidatos[1][2]:
        raise ErroFireAds("Formulários empatados; origem não inequívoca")
    return candidatos[0]


def bloco_observacoes(id_integracao, id_conversa, observacoes):
    chave = f"CHATBOT:{int(id_integracao)}:{int(id_conversa)}"
    return (
        f"[INICIO {chave}]\nObservações do atendimento — conversa {id_conversa}\n"
        f"{observacoes}\n[FIM {chave}]"
    )


def acrescentar_observacoes(anterior, bloco):
    """Preserva inclusive zero e espaços; conflito nunca vira sobrescrita."""
    if anterior is None:
        anterior = ""
    if not isinstance(anterior, (str, int, float)) or isinstance(anterior, bool):
        raise ErroFireAds("Observação tem tipo inesperado")
    texto = str(anterior)
    marcador = bloco.split("\n", 1)[0]
    if marcador in texto:
        if texto.count(marcador) != 1 or bloco not in texto:
            raise ErroFireAds("Bloco da conversa existe com conteúdo divergente")
        return texto, False
    novo = texto + ("\n\n" if texto else "") + bloco
    if len(novo) > 45000:
        raise ErroFireAds("Observação excede limite operacional; não truncar")
    return novo, True
````

## Passo 3: `core/repositories/fireads/pendencias.py`

Solicitar, reservar, concluir, expirar e marcar a aplicação usando somente SQL parametrizado.

````python
"""Fila durável de consultas; SQL sem HTTP e sem controle de transações."""

from psycopg.types.json import Jsonb


def solicitar(abertura, id_conversa, numero, cursor):
    """Uma conversa recebe uma solicitação; retry não altera entrada nem prazo."""
    entrada = {
        "url": abertura["url"],
        "aba_google": abertura["aba_google"],
        "aba_meta": abertura["aba_meta"],
        "fuso": abertura["fuso"],
        "numero": numero,
    }
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
    """Reserva entre processos e recupera queda sem esperar o prazo de 300s.

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
              processing_started_at=clock_timestamp(),reserva_ate=prazo_final,
              atualizado_em=clock_timestamp()
            FROM chatbot.conversa c,chatbot.unidade u,chatbot.integracao_fireads i
            WHERE q.id_consulta=%s AND q.status IN ('pendente','processando')
              AND q.prazo_final>clock_timestamp() AND c.id_conversa=q.id_conversa
              AND c.status_ativa AND c.finalizou_em IS NULL AND c.id_etapa_atual IS NULL
              AND c.contexto_fireads IS NULL AND u.id_unidade=q.id_unidade
              AND u.status_pagamento IS TRUE AND i.id_integracao_fireads=q.id_integracao_fireads
              AND i.integracao_ativa AND i.contrato_validado
              AND i.url_dashbord=q.entrada->>'url'
              AND i.aba_google=q.entrada->>'aba_google' AND i.aba_meta=q.entrada->>'aba_meta'
              AND i.fuso_formularios IS NOT DISTINCT FROM q.entrada->>'fuso'
            RETURNING q.id_consulta,q.id_conversa,q.versao_reserva,q.entrada,
                      EXTRACT(EPOCH FROM q.prazo_final-clock_timestamp())""",
            (ident,),
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


def concluir(reserva, resultado, cursor):
    """A gravação única inclui as duas fontes e a decisão, sem resultados parciais."""
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
          AND i.aba_google=q.entrada->>'aba_google' AND i.aba_meta=q.entrada->>'aba_meta'
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
````

## Passo 4: `core/repositories/fireads/consulta.py`

Importar dados e contexto na transação do flow; retirar o antigo upsert por chat.

````python
"""SQL FireAds; o orquestrador controla commits e as chamadas externas."""

from psycopg.errors import UniqueViolation
from psycopg.types.json import Jsonb

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
               i.url_dashbord,i.aba_google,i.aba_meta,i.fuso_formularios,
               (u.status_pagamento IS TRUE AND i.integracao_ativa
                AND c.iniciou_em >= i.ativada_em) AS aplicavel
        FROM chatbot.conversa c JOIN chatbot.unidade u ON u.id_unidade=c.id_unidade
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
                "aba_google",
                "aba_meta",
                "fuso",
                "aplicavel",
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
````

## Passo 5: `workers/worker_consulta_dash/__init__.py`

Criar o pacote do novo worker.

````python
"""Consulta periódica e durável dos formulários FireAds."""
````

## Passo 6: `workers/worker_consulta_dash/resultado.py`

Interpretar os formulários sem HTTP ou persistência.

````python
"""Interpretação da consulta inicial; não executa HTTP nem operações de banco."""

from core.integrations.fireads.contrato import selecionar, destino, ErroFireAds
from core.validacoes.email import validar_email_estrutural
from workers.worker_flow.response_flow.etapas.validadores_universais.validador_nome import validar_nome_cliente

def decisao_organica(resultado, motivo=None):
    return {
        "resultado": resultado,
        "origem": "organico",
        "motivo": motivo,
        "dados_titular": {},
    }


def interpretar(google, meta, numero, fuso):
    try:
        escolhido = selecionar(google, meta, numero, fuso)
    except ErroFireAds:
        return decisao_organica("ambiguidade", "data_ou_origem_ambigua")
    if escolhido is None:
        return decisao_organica("ausente")
    origem, row, data = escolhido
    nome = row.get("Nome") if origem == "google" else row.get("full_name")
    email = row.get("Email") if origem == "google" else row.get("email")
    alvo = row.get("Perfil/Faixa") if origem == "google" else row.get("para_quem")
    nome = validar_nome_cliente(nome)
    email = validar_email_estrutural(email)
    dependente = destino(alvo)
    if not nome.valido or not email.valido or dependente is None:
        return decisao_organica("incompleto", "coleta_invalida")
    return {
        "resultado": "importado",
        "origem": origem,
        "status_dependente": dependente,
        "id_registro_origem": str(row.get("id") or ""),
        "data_formulario": data.isoformat() if data else None,
        "dados_titular": {
            "nome": nome.primeiro_nome,
            "email": email.email,
            "resultado_email": "email_valido",
        },
    }
````

## Passo 7: `workers/worker_consulta_dash/consulta.py`

Ler as duas fontes e produzir o resultado completo, sem salvar partes de cada aba.

````python
"""Leitura completa das duas fontes, sem persistência ou envio de mensagens."""

import logging
import time

from core.integrations.fireads.cliente import ClienteFireAds, PrazoConsultaFireAdsEsgotado
from core.integrations.fireads.contrato import ErroFireAds, localizar
from workers.worker_consulta_dash.resultado import decisao_organica, interpretar

logger = logging.getLogger("worker.consulta_dash.http")


def consultar(reserva):
    entrada = reserva["entrada"]
    inicio = time.monotonic()
    cliente = None
    try:
        cliente = ClienteFireAds(entrada["url"], segundos=float(reserva["restante"]),
                                timeout_leitura=None)
        google = cliente.consultar(entrada["aba_google"])
        meta = cliente.consultar(entrada["aba_meta"])
        if not {"Nome", "Email", "WhatsApp", "Perfil/Faixa"} <= set(google["headers"]):
            raise ErroFireAds("Contrato Google incompleto")
        if not {"full_name", "email", "phone_number", "para_quem"} <= set(meta["headers"]):
            raise ErroFireAds("Contrato Meta incompleto")
        numero = entrada["numero"]
        decisao = interpretar(google["rows"], meta["rows"], numero, entrada["fuso"])
        # Não copiar dados de outros clientes. As fontes são confirmadas juntas;
        # erro na segunda fonte descarta também a primeira, sem importação parcial.
        fontes = {
            "google": localizar(google["rows"], numero, "WhatsApp", incluir_equivalentes=True),
            "meta": localizar(meta["rows"], numero, "phone_number", incluir_equivalentes=True),
        }
        if time.monotonic()-inicio >= float(reserva["restante"]):
            raise PrazoConsultaFireAdsEsgotado("Leitura concluída após o prazo")
        return {"decisao": decisao, "fontes": fontes}
    except PrazoConsultaFireAdsEsgotado:
        return {"decisao": decisao_organica("erro", "tempo_limite_300s"), "fontes": {}}
    except Exception as erro:
        # O corpo da API pode conter dados pessoais; guardar/logar só a classe.
        logger.warning("consulta_dash_http_falhou | consulta=%s tipo=%s",
                       reserva["id_consulta"], type(erro).__name__)
        return {"decisao": decisao_organica("erro", type(erro).__name__), "fontes": {}}
    finally:
        if cliente is not None:
            cliente.close()
````

## Passo 8: `workers/worker_consulta_dash/consulta_worker.py`

Controlar conexão, reserva, commits, rollback e fechamento do ciclo de consulta.

````python
"""Orquestra reservas duráveis. Não cria conversas, não muda etapas e não envia WhatsApp."""

import logging
import time

from core.database.connection_aws import get_conn
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
        conn.commit()
        if reserva is None:
            return False
        logger.info("consulta_dash_iniciada | consulta=%s conversa=%s tentativa=%s",
                    reserva["id_consulta"], reserva["id_conversa"], reserva["versao"])
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
````

## Passo 9: `workers/worker_consulta_dash/iniciar_worker_consulta_dash.py`

Supervisionar o serviço e recuperar falhas do processo.

````python
"""Ponto de entrada do serviço periódico de consulta FireAds."""

import logging
import time

from core.logging_config import setup_logging
from workers.worker_consulta_dash.consulta_worker import consulta_worker

logger = logging.getLogger("worker.consulta_dash.supervisor")


def iniciar_worker_consulta_dash():
    setup_logging()
    while True:
        try:
            logger.info("consulta_dash_worker_iniciado")
            consulta_worker()
        except KeyboardInterrupt:
            raise
        except Exception as erro:
            # Mensagens SQL/HTTP podem expor entradas; o tipo basta para este log.
            logger.error("consulta_dash_worker_falhou | tipo=%s reiniciar_em=5s",
                         type(erro).__name__)
            time.sleep(5)


if __name__ == "__main__":
    iniciar_worker_consulta_dash()
````

## Passo 10: `workers/worker_flow/suporte/consultas_fireads.py`

Substituir o executor de threads por apenas uma exceção de espera persistida.

````python
"""Sinal de espera persistida; nenhuma execução paralela em memória."""


class ConsultaFireAdsPendente(Exception):
    """Confirmar a solicitação e reagendar a mensagem sem consumir tentativa."""
````

## Passo 11: `workers/worker_flow/fireads.py`

Solicitar ou consumir o resultado somente na abertura, sem HTTP nem commits próprios.

````python
"""Prepara somente a abertura, consumindo a consulta persistida pelo outro worker."""

from core.validacoes.email import validar_email_estrutural
from core.repositories.fireads import pendencias
from core.repositories.fireads.consulta import (
    buscar_abertura,
    proteger_mensagem_abertura,
    importar_dados_abertura,
    aplicar_decisao,
)
from core.repositories.atendimento.followup import proteger_conversa
from workers.worker_consulta_dash.resultado import decisao_organica, interpretar
from workers.worker_flow.suporte.consultas_fireads import ConsultaFireAdsPendente


def preparar_abertura(contexto_banco, mensagem, lock_version, cursor):
    """Não executa HTTP nem commit. O orquestrador confirma também a espera."""
    cid = contexto_banco["conversa"]["id_conversa"]
    abertura = buscar_abertura(cid, cursor)
    if abertura["contexto"]:
        return aplicar_contexto(contexto_banco, abertura["contexto"])
    if abertura["etapa"] is not None:
        return contexto_banco  # Nunca reconsultar ou retroceder uma etapa iniciada.
    proteger_conversa(cid, lock_version, cursor)
    proteger_mensagem_abertura(mensagem, cursor)
    consulta = pendencias.buscar(cid, cursor)
    if consulta is None:
        if not abertura["aplicavel"]:
            return contexto_banco
        pendencias.solicitar(abertura, cid, mensagem["cliente_telefone"], cursor)
        consulta = pendencias.buscar(cid, cursor)
    motivo = None
    if not abertura["aplicavel"]:
        motivo = "integracao_desativada"
    elif consulta["id_integracao"] != abertura["id_integracao"] or any(
        consulta["entrada"].get(campo) != abertura[campo]
        for campo in ("url", "aba_google", "aba_meta", "fuso")
    ):
        motivo = "configuracao_alterada"
    elif consulta["expirada"] and consulta["status"] != "concluida":
        motivo = "tempo_limite_300s"
    if motivo and consulta["status"] != "concluida":
        pendencias.concluir_sem_http(
            consulta["id_consulta"], decisao_organica("erro", motivo), cursor
        )
        consulta = pendencias.buscar(cid, cursor)
    if consulta["status"] != "concluida":
        raise ConsultaFireAdsPendente("aguardando_resultado")
    if consulta["aplicacao"] is not None:
        raise ValueError(
            "Consulta aplicada sem contexto da conversa; verificar integridade"
        )
    # Mudança de integração não autoriza aplicar dados de configuração anterior.
    decisao = (
        decisao_organica("erro", motivo) if motivo else consulta["dados"]["decisao"]
    )
    if decisao["resultado"] == "importado":
        if not importar_dados_abertura(abertura["id_cliente"], cid, decisao, cursor):
            decisao = decisao_organica("incompleto", "conflito_email")
    # Conservar a integração originalmente consultada, inclusive se desativada.
    abertura = dict(abertura, id_integracao=consulta["id_integracao"])
    decisao = aplicar_decisao(abertura, cid, consulta["id_consulta"], decisao, cursor)
    pendencias.marcar_aplicada(consulta["id_consulta"], cid, decisao, cursor)
    return aplicar_contexto(contexto_banco, decisao)


def classificar_tratamento_abertura(contexto):
    """A decisão fica no fluxo; messages apenas compõe o texto autorizado."""
    from workers.worker_flow.response_flow.etapas.validadores_universais.validador_midia import (
        validar_midia,
    )
    from workers.worker_flow.response_flow.etapas.validadores_universais.validador_financeiro import (
        validar_pergunta_financeira,
    )
    from workers.worker_flow.response_flow.etapas.validadores_universais.validador_reforco_escolar import (
        validar_duvida_reforco_escolar,
    )

    texto = contexto.get("texto_cliente_atual") or ""
    if validar_midia(contexto.get("tipo_mensagem_atual")):
        return "tipo_mensagem_nao_suportado"
    if validar_duvida_reforco_escolar(texto):
        return "duvida_reforco_escolar"
    if validar_pergunta_financeira(texto):
        return "pergunta_financeira"
    return None


def aplicar_contexto(contexto_banco, decisao):
    novo = dict(contexto_banco, contexto_fireads=decisao)
    if (
        decisao.get("resultado") == "importado"
        and novo["conversa"].get("id_etapa_atual") is None
    ):
        novo["conversa"] = dict(
            novo["conversa"], status_dependente=decisao["status_dependente"]
        )
    return novo


def email_importado(contexto):
    estado = contexto.get("contexto_fireads") or {}
    return (
        estado.get("concluida") is True
        and estado.get("resultado") == "importado"
        and estado.get("id_conversa") == contexto.get("id_conversa")
        and estado.get("dados_titular", {}).get("resultado_email") == "email_valido"
        and validar_email_estrutural(
            estado.get("dados_titular", {}).get("email")
        ).valido
    )
````

## Passo 12: `workers/worker_flow/response_flow/flow_worker.py`

Confirmar solicitação e reagendamento juntos; preservar locks, turnos e resposta existente.

````python
import logging
from workers.worker_flow.fireads import preparar_abertura
from workers.worker_flow.suporte.consultas_fireads import ConsultaFireAdsPendente

import psycopg
from core.cache.cache_unidade import UnidadeNaoEncontrada
from core.repositories.unidades.consultas import (
    UnidadeDesativada,
    exigir_unidade_habilitada_por_phone_id,
)
from core.database.connection_aws import get_conn
from core.integrations.whatsapp.exceptions import ErroEnvioMeta
from core.logging_config import short_value
from core.repositories.atendimento.conversas import tentar_lock_conversa
from core.repositories.atendimento.followup import (
    LockConversaPerdido,
    proteger_conversa,
    reler_conversa,
)
from workers.worker_flow.response_flow.retomada_followup import (
    enviar_retorno_followup,
)
from workers.worker_flow.transacoes.retorno_followup import (
    preparar_retorno_followup,
    persistir_retorno_followup,
)
from core.repositories.atendimento.fila import (
    pegar_mensagens_da_fila,
    reagendar_mensagem_sem_erro,
    vincular_mensagem_fila_a_conversa,
)
from workers.tratamento_erros_externos.erro_conexao import handle_erro_conexao
from workers.tratamento_erros_externos.erro_generico import handle_erro_generico
from workers.tratamento_erros_externos.exceptions import BancoFalhouAposEnvioMeta
from workers.tratamento_erros_externos.unidade_nao_encontrada import (
    handle_unidade_nao_encontrada,
)
from workers.worker_flow.response_flow.flow_sender import flow_sender
from workers.worker_flow.suporte.cache_repair import (
    confirmar_cache_cliente_se_pendente,
    reparar_cache_cliente_stale_se_fk_invalida,
    reparar_cache_unidade_stale_se_fk_invalida,
)
from workers.worker_flow.suporte.estado_ciclo import (
    aguardar_fila_vazia,
    atualizar_estado_com_contexto,
    atualizar_estado_com_mensagem,
    atualizar_estado_lock,
    criar_estado_ciclo,
    montar_mensagem_fila,
)
from workers.worker_flow.transacoes.finalizacao_fila import (
    finalizar_mensagem_processada,
    registrar_cache_bloqueio_apos_commit,
)
from workers.worker_flow.transacoes.lock_conversa import (
    liberar_lock_conversa_se_necessario,
)
from workers.worker_flow.transacoes.ordem_turno import (
    logar_lock_recusado,
    reagendar_se_houver_mensagem_anterior,
)
from workers.worker_flow.transacoes.persistencia_resposta import (
    atualizar_banco_com_contexto_final,
)
from workers.worker_flow.tratar_bloqueio import tratar_conversa_bloqueada
from workers.worker_flow.valida_banco import validar_banco_mensagem
from workers.worker_flow.valida_historico import valida_historico

logger = logging.getLogger("worker.response_flow")


def worker_flow():
    logger.info("worker_iniciado")

    max_retry = 3
    retry_delay = 5

    while True:
        print("\n\n\n---------------------NOVO CICLO---------------------\n\n\n")
        logger.info("---------- ciclo_worker_inicio ----------")

        conn_ciclo = None
        cursor_ciclo = None
        estado_ciclo = criar_estado_ciclo()
        contexto_envio = {}

        try:
            conn_ciclo = get_conn(application_name="worker_chatbot")
            cursor_ciclo = conn_ciclo.cursor()
            retry_delay = 5
            logger.debug("ciclo_conexao_banco_ok | acao=dequeue")

            registro = pegar_mensagens_da_fila(cursor_ciclo)
            conn_ciclo.commit()

            if not registro:
                conn_ciclo.close()
                conn_ciclo = None
                cursor_ciclo = None
                aguardar_fila_vazia()
                continue

            mensagem = montar_mensagem_fila(registro)
            atualizar_estado_com_mensagem(estado_ciclo, mensagem)

            logger.info(
                "mensagem_processando | acao=iniciar id_mensagem=%s cliente=%s phone_number_id=%s tipo=%s retry=%s",
                mensagem["id_mensagem"],
                short_value(mensagem["cliente_telefone"]),
                short_value(mensagem["id_phone_unidade"]),
                mensagem["tipo_mensagem"],
                mensagem["retry_count"],
            )

            if reagendar_se_houver_mensagem_anterior(
                mensagem,
                cursor_ciclo,
            ):
                conn_ciclo.commit()
                continue

            exigir_unidade_habilitada_por_phone_id(mensagem["id_phone_unidade"], cursor_ciclo)
            contexto_banco = validar_banco_mensagem(
                mensagem,
                cursor_ciclo,
            )
            atualizar_estado_com_contexto(estado_ciclo, contexto_banco)

            contexto_conversa = contexto_banco["conversa"]
            id_conversa = contexto_conversa["id_conversa"]

            conn_ciclo.commit()
            logger.debug(
                "contexto_banco_confirmado | acao=commit id_mensagem=%s id_conversa_calculada=%s estado=%s",
                mensagem["id_mensagem"],
                id_conversa,
                contexto_conversa["estado"],
            )

            confirmar_cache_cliente_se_pendente(contexto_banco)

            if contexto_conversa["estado"] == "bloqueada":
                tratar_conversa_bloqueada(
                    mensagem["id_mensagem"],
                    mensagem["cliente_telefone"],
                    mensagem["id_phone_unidade"],
                    id_conversa,
                    cursor_ciclo,
                )
                conn_ciclo.commit()
                continue

            lock_ok, lock_version = tentar_lock_conversa(id_conversa, cursor_ciclo)
            conn_ciclo.commit()
            atualizar_estado_lock(estado_ciclo, lock_ok, lock_version)

            if not lock_ok:
                logar_lock_recusado(mensagem, contexto_banco)
                reagendar_mensagem_sem_erro(
                    mensagem["id_mensagem"],
                    cursor_ciclo,
                    delay_seconds=5,
                )
                conn_ciclo.commit()
                continue

            linhas_vinculadas = vincular_mensagem_fila_a_conversa(
                mensagem["id_mensagem"],
                id_conversa,
                cursor_ciclo,
            )

            if linhas_vinculadas == 0:
                logger.critical(
                    "mensagem_conversa_vinculo_inconsistente | "
                    "motivo=historico_conflitante_ou_fila_ausente "
                    "acao=reagendar_sem_consumir_retry id_mensagem=%s "
                    "cliente=%s phone_number_id=%s "
                    "id_conversa_calculada=%s",
                    mensagem["id_mensagem"],
                    short_value(mensagem["cliente_telefone"]),
                    short_value(mensagem["id_phone_unidade"]),
                    id_conversa,
                )
                reagendar_mensagem_sem_erro(
                    mensagem["id_mensagem"],
                    cursor_ciclo,
                    delay_seconds=300,
                )
                conn_ciclo.commit()
                continue

            contexto_banco = reler_conversa(contexto_banco, lock_version, cursor_ciclo)
            exigir_unidade_habilitada_por_phone_id(mensagem["id_phone_unidade"], cursor_ciclo)
            contexto_banco = preparar_abertura(
                contexto_banco, mensagem, lock_version, cursor_ciclo
            )
            contexto_conversa = contexto_banco["conversa"]
            contexto_historico = preparar_retorno_followup(
                mensagem,
                contexto_banco,
                cursor_ciclo,
            )
            if contexto_historico is None:
                contexto_historico = valida_historico(
                    mensagem, contexto_banco, cursor_ciclo
                )
            conn_ciclo.commit()
            logger.debug(
                "historico_contexto_ok | acao=commit id_mensagem=%s id_conversa=%s etapa_cliente=%s etapa_resposta=%s inserido=%s",
                mensagem["id_mensagem"],
                id_conversa,
                contexto_historico["id_etapa_cliente"],
                contexto_historico["id_etapa_resposta"],
                contexto_historico["mensagem_cliente_inserida"],
            )

            proteger_conversa(id_conversa, lock_version, cursor_ciclo, renovar=True)
            exigir_unidade_habilitada_por_phone_id(mensagem["id_phone_unidade"], cursor_ciclo)
            conn_ciclo.commit()
            if contexto_historico.get("retorno_followup"):
                contexto_envio = enviar_retorno_followup(contexto_historico)
            else:
                contexto_envio = flow_sender(contexto_historico)

            try:
                proteger_conversa(id_conversa, lock_version, cursor_ciclo)
                persistir = (
                    persistir_retorno_followup
                    if contexto_historico.get("retorno_followup")
                    else atualizar_banco_com_contexto_final
                )
                contexto_final = persistir(
                    contexto_historico, contexto_envio, cursor_ciclo
                )
                if contexto_historico.get("retorno_followup"):
                    # O retorno agora pode encerrar por idade ou finalizar o fluxo.
                    # Histórico, efeitos, stage=0, encerramento e fila são atômicos:
                    # um retry não pode encontrar um checkpoint concluído sem
                    # que o encerramento correspondente também esteja confirmado.
                    resultado_encerramento = finalizar_mensagem_processada(
                        mensagem,
                        contexto_banco,
                        lock_version,
                        cursor_ciclo,
                        contexto_final,
                    )
                conn_ciclo.commit()

            except Exception as erro:
                if contexto_envio.get("enviou"):
                    raise BancoFalhouAposEnvioMeta(
                        "Banco falhou depois da Meta confirmar envio",
                        id_mensagem=mensagem["id_mensagem"],
                        id_conversa=id_conversa,
                        id_hash_msg_bot=contexto_envio.get("id_hash_msg_bot"),
                        id_etapa=contexto_envio.get("id_etapa_resultante"),
                    ) from erro

                raise

            logger.debug(
                "resposta_bot_contexto_final_ok | acao=commit id_mensagem=%s id_conversa=%s etapa=%s resposta_ja_existia=%s id_hash_msg_bot=%s tratamento=%s tipo_tratamento=%s",
                mensagem["id_mensagem"],
                id_conversa,
                contexto_final["id_etapa_resultante"],
                contexto_final["resposta_ja_existia"],
                contexto_final["id_hash_msg_bot"],
                contexto_envio.get("tratamento", False),
                contexto_envio.get("tipo_tratamento"),
            )

            if not contexto_historico.get("retorno_followup"):
                proteger_conversa(id_conversa, lock_version, cursor_ciclo)
                resultado_encerramento = finalizar_mensagem_processada(
                    mensagem,
                    contexto_banco,
                    lock_version,
                    cursor_ciclo,
                    contexto_final,
                )
                conn_ciclo.commit()

            registrar_cache_bloqueio_apos_commit(
                mensagem,
                resultado_encerramento,
            )

        except ConsultaFireAdsPendente as espera:
            # A espera é uma decisão válida, não uma falha SQL. Solicitação,
            # vínculo da fila e reagendamento serão confirmados juntos abaixo.
            # Libera o ciclo para outras conversas. Esperar uma leitura não é erro
            # e não pode esgotar as três tentativas da mensagem original.
            reagendar_mensagem_sem_erro(
                mensagem["id_mensagem"], cursor_ciclo, delay_seconds=5,
                retry_esperado=mensagem["retry_count"],
            )
            conn_ciclo.commit()
            logger.debug(
                "fireads_consulta_pendente | conversa=%s motivo=%s acao=aguardar_sem_responder",
                estado_ciclo["id_conversa"], espera,
            )

        except UnidadeDesativada:
            conn_ciclo.rollback()
            # Preserva pendência/histórico; a função dequeue não reserva inativas.
            reagendar_mensagem_sem_erro(
                mensagem["id_mensagem"], cursor_ciclo, delay_seconds=300,
                retry_esperado=mensagem["retry_count"],
            )
            conn_ciclo.commit()
            logger.info("unidade_desativada | acao=preservar_pendente id_mensagem=%s", mensagem["id_mensagem"])

        except LockConversaPerdido:
            if conn_ciclo:
                conn_ciclo.rollback()
            # Não reescreve uma fila que pode estar sendo processada pelo novo dono.
            logger.warning(
                "lock_perdido | acao=aguardar_recuperacao_fila id_conversa=%s",
                estado_ciclo["id_conversa"],
            )

        except ErroEnvioMeta as erro:
            logger.warning(
                "meta_envio_erro | acao=reagendar_sem_sent id_mensagem=%s cliente=%s phone_number_id=%s etapa=%s erro=%s",
                estado_ciclo["id_mensagem"],
                short_value(estado_ciclo["cliente_telefone"]),
                short_value(estado_ciclo["id_phone_unidade"]),
                erro.id_etapa,
                erro,
            )
            if conn_ciclo:
                conn_ciclo.rollback()

            handle_erro_generico(
                cursor_ciclo,
                estado_ciclo["id_mensagem"],
                erro,
                max_retry,
            )

            if conn_ciclo:
                conn_ciclo.commit()

        except BancoFalhouAposEnvioMeta as erro:
            if isinstance(erro.__cause__, LockConversaPerdido):
                conn_ciclo.rollback()
                logger.critical(
                    "meta_confirmou_com_lock_perdido | conversa=%s hash=%s risco=duplicidade",
                    erro.id_conversa,
                    erro.id_hash_msg_bot,
                )
                continue
            logger.critical(
                "banco_falhou_apos_envio_meta | risco=resposta_duplicada acao=reagendar_sem_sent id_mensagem=%s id_conversa=%s etapa=%s id_hash_msg_bot=%s tratamento=%s tipo_tratamento=%s erro=%s",
                erro.id_mensagem,
                erro.id_conversa,
                erro.id_etapa,
                erro.id_hash_msg_bot,
                contexto_envio.get("tratamento", False),
                contexto_envio.get("tipo_tratamento"),
                erro,
            )
            if conn_ciclo:
                conn_ciclo.rollback()

            handle_erro_generico(
                cursor_ciclo,
                estado_ciclo["id_mensagem"],
                erro,
                max_retry,
            )

            if conn_ciclo:
                conn_ciclo.commit()

        except psycopg.OperationalError as erro:
            logger.warning(
                "banco_operacional_erro | acao=retry_conexao id_mensagem=%s erro=%s",
                estado_ciclo["id_mensagem"],
                erro,
            )
            retry_delay = handle_erro_conexao(erro, retry_delay)
            continue

        except UnidadeNaoEncontrada as erro:
            logger.warning(
                "unidade_nao_encontrada | acao=tratar_unidade_invalida id_mensagem=%s cliente=%s phone_number_id=%s erro=%s",
                estado_ciclo["id_mensagem"],
                short_value(estado_ciclo["cliente_telefone"]),
                short_value(estado_ciclo["id_phone_unidade"]),
                erro,
            )
            if conn_ciclo:
                conn_ciclo.rollback()

            handle_unidade_nao_encontrada(
                cursor_ciclo,
                estado_ciclo["id_mensagem"],
                erro,
            )

            if conn_ciclo:
                conn_ciclo.commit()

        except Exception as erro:
            logger.exception(
                "mensagem_erro | acao=tratar_erro_generico id_mensagem=%s cliente=%s phone_number_id=%s id_conversa=%s estado=%s erro=%s",
                estado_ciclo["id_mensagem"],
                short_value(estado_ciclo["cliente_telefone"]),
                short_value(estado_ciclo["id_phone_unidade"]),
                estado_ciclo["id_conversa"],
                estado_ciclo["estado"],
                erro,
            )
            if conn_ciclo:
                conn_ciclo.rollback()

            reparar_cache_cliente_stale_se_fk_invalida(erro, estado_ciclo)
            reparar_cache_unidade_stale_se_fk_invalida(erro, estado_ciclo)

            handle_erro_generico(
                cursor_ciclo,
                estado_ciclo["id_mensagem"],
                erro,
                max_retry,
            )

            if conn_ciclo:
                conn_ciclo.commit()

        finally:
            if conn_ciclo:
                try:
                    unlock_realizado = liberar_lock_conversa_se_necessario(
                        cursor_ciclo,
                        estado_ciclo,
                    )

                    if unlock_realizado is not None:
                        conn_ciclo.commit()

                except Exception as erro:
                    logger.exception(
                        "finalizacao_ciclo_falhou | acao=continuar_para_close erro=%s",
                        erro,
                    )

                finally:
                    try:
                        conn_ciclo.close()

                    except Exception as erro:
                        logger.exception(
                            "conexao_ciclo_close_falhou | acao=registrar_e_continuar erro=%s",
                            erro,
                        )
````

## Passo 13: `callback/webhook/models.py`

Refletir o vínculo único com conversa e os campos operacionais; models continuam managed=False.

````python
from core.integrations.whatsapp.numero_comercial import numero_comercial_whatsapp_valido
from core.validacoes.turno import ROTULOS_TURNO
from core.validacoes.suporte_por_idade import IDADES_MINIMAS_SUPORTE

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from core.validacoes.encerramento_por_idade import ROTULOS_MOTIVOS


class Cliente(models.Model):
    id_cliente = models.AutoField(primary_key=True)
    nome = models.CharField(max_length=200, blank=True, null=True)
    waid_telefone = models.CharField(unique=True, max_length=50)
    email = models.CharField(unique=True, max_length=200, blank=True, null=True)
    idade = models.IntegerField(blank=True, null=True)
    profissao = models.CharField(max_length=100, blank=True, null=True)

    def __str__(self):
        return self.nome or self.waid_telefone

    class Meta:
        managed = False
        db_table = 'cliente'


class Dependente(models.Model):
    id_dependente = models.AutoField(primary_key=True)
    id_cliente = models.ForeignKey(
        Cliente,
        models.CASCADE,
        db_column='id_cliente',
        related_name='dependentes',
    )
    id_conversa = models.ForeignKey(
        'Conversa',
        models.CASCADE,
        db_column='id_conversa',
        related_name='dependentes_atendidos',
        blank=True,
        null=True,
    )
    nome_dependente = models.CharField(max_length=200, blank=True, null=True)
    idade = models.IntegerField(blank=True, null=True)

    def __str__(self):
        return self.nome_dependente or str(self.id_dependente)

    class Meta:
        managed = False
        db_table = 'dependente'


class Conversa(models.Model):
    id_chat = models.ForeignKey('Chat', models.DO_NOTHING, db_column='id_chat')
    origem_fireads = models.CharField(max_length=10, null=True, blank=True, choices=[('google','Google Ads'),('meta','Meta Ads'),('organico','Orgânico')])
    contexto_fireads = models.JSONField(null=True, blank=True)
    lead_no_dash = models.BooleanField(null=True, blank=True, default=None)

    turno = models.CharField(
        "turno de preferência", max_length=5, blank=True, null=True,
        choices=list(ROTULOS_TURNO.items()),
        help_text="Preferência informada no atendimento; não confirma dia ou horário.",
    )
    id_conversa = models.AutoField(primary_key=True)
    id_cliente = models.ForeignKey(Cliente, models.DO_NOTHING, db_column='id_cliente')
    id_unidade = models.ForeignKey('Unidade', models.DO_NOTHING, db_column='id_unidade')
    id_etapa_atual = models.ForeignKey('Etapa', models.DO_NOTHING, db_column='id_etapa_atual', blank=True, null=True)
    status_ativa = models.BooleanField(default=True)
    status_dependente = models.BooleanField(blank=True, null=True, default=False)
    profissao = models.CharField(max_length=100, blank=True, null=True)
    last_interaction_at = models.DateTimeField(blank=True, null=True)
    last_message_from = models.CharField(
        max_length=10,
        blank=True,
        null=True,
        choices=[("cliente", "cliente"), ("bot", "bot")],
    )
    followup_stage = models.IntegerField(blank=True, null=True, default=0)
    followup_last_sent_at = models.DateTimeField(blank=True, null=True)
    lead_no_funil = models.BooleanField(blank=True, null=True, default=False)
    processing = models.BooleanField(blank=True, null=True, default=False)
    processing_started_at = models.DateTimeField(blank=True, null=True)
    lock_version = models.IntegerField(blank=True, null=True, default=0)
    turnos_sem_avanco = models.IntegerField(default=0)
    iniciou_em = models.DateTimeField()
    finalizou_em = models.DateTimeField(blank=True, null=True)
    motivo_encerramento = models.CharField(
        max_length=30,
        blank=True,
        null=True,
        choices=[*ROTULOS_MOTIVOS.items(),
                 ("foi_agendado", "Foi agendado"),
                 ("followup_sem_resposta", "Segundo follow-up sem resposta")],
    )

    class Meta:
        managed = False
        db_table = 'conversa'


class Etapa(models.Model):
    id_etapa = models.AutoField(primary_key=True)
    nome_etapa = models.CharField(unique=True, max_length=100)
    encerra_automaticamente = models.BooleanField(default=False)
    bloqueio_dias = models.PositiveIntegerField(default=0)
    elegivel_funil = models.BooleanField(default=False)

    class Meta:
        managed = False
        db_table = 'etapa'


class FilaMensagens(models.Model):
    id_mensagem = models.AutoField(primary_key=True)
    id_conversa = models.ForeignKey(
        Conversa,
        models.SET_NULL,
        db_column='id_conversa',
        blank=True,
        null=True,
    )
    status = models.CharField(
        max_length=20,
        default="pending",
        choices=[
            ("pending", "pending"),
            ("processing", "processing"),
            ("sent", "sent"),
            ("failed", "failed"),
        ],
    )
    retry_count = models.IntegerField(blank=True, null=True, default=0)
    next_attempt_at = models.DateTimeField(blank=True, null=True)
    processing_started_at = models.DateTimeField(blank=True, null=True)
    received_data_hora = models.DateTimeField()
    cliente_telefone = models.CharField(max_length=100)
    conteudo_texto = models.TextField(blank=True, null=True)
    tipo_mensagem = models.CharField(max_length=20)
    id_hash_msg = models.CharField(unique=True, max_length=255)
    id_phone_unidade = models.CharField(max_length=100)
    unidade_telefone = models.CharField(max_length=100)
    last_error = models.TextField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'fila_mensagens'


class HistoricoMensagens(models.Model):
    id_mensagem = models.AutoField(primary_key=True)

    id_conversa = models.ForeignKey(
        Conversa,
        models.DO_NOTHING,
        db_column='id_conversa'
    )

    id_etapa = models.ForeignKey(
        Etapa,
        models.DO_NOTHING,
        db_column='id_etapa',
        blank=True,
        null=True
    )

    received_data_hora = models.DateTimeField()

    cliente_telefone = models.CharField(max_length=100)
    conteudo_texto = models.TextField(blank=True, null=True)
    tipo_mensagem = models.CharField(max_length=20)
    id_hash_msg = models.CharField(max_length=255)
    id_mensagem_fila = models.ForeignKey(
        FilaMensagens,
        models.SET_NULL,
        db_column='id_mensagem_fila',
        blank=True,
        null=True,
        related_name='historicos_originados',
    )
    id_hash_cliente_origem = models.CharField(max_length=255, blank=True, null=True)
    id_phone_unidade = models.CharField(max_length=100)
    unidade_telefone = models.CharField(max_length=100)
    quem_enviou = models.CharField(
        max_length=10,
        choices=[
            ("cliente", "cliente"),
            ("bot", "bot"),
        ],
    )
    status_envio = models.CharField(
        max_length=20,
        blank=True,
        null=True,
        choices=[
            ("pending", "pending"),
            ("sent", "sent"),
            ("failed", "failed"),
        ],
    )

    class Meta:
        managed = False
        db_table = 'historico_mensagens'
        constraints = [
            models.UniqueConstraint(
                fields=["id_mensagem", "received_data_hora"],
                name="uq_historico_mensagens_id_data",
            ),
        ]


class RespostasDesafios(models.Model):
    id_resposta_desafio = models.AutoField(primary_key=True)
    id_conversa = models.ForeignKey(
        Conversa,
        models.CASCADE,
        db_column='id_conversa',
        related_name='respostas_desafios',
    )
    id_etapa = models.ForeignKey(
        Etapa,
        models.DO_NOTHING,
        db_column='id_etapa',
        related_name='respostas_desafios',
    )
    resposta = models.CharField(max_length=20)
    id_historico_mensagem_cliente = models.IntegerField(blank=True, null=True)
    criado_em = models.DateTimeField()

    class Meta:
        managed = False
        db_table = 'respostas_desafios'
        constraints = [
            models.UniqueConstraint(
                fields=["id_conversa", "id_etapa"],
                name="uq_respostas_desafios_conversa_etapa",
            ),
        ]


class PesquisaSatisfacao(models.Model):
    id_pesquisa_satisfacao = models.AutoField(primary_key=True)
    id_conversa = models.OneToOneField(
        Conversa,
        models.CASCADE,
        db_column='id_conversa',
        related_name='pesquisa_satisfacao',
    )
    nota = models.PositiveSmallIntegerField(blank=True, null=True)
    comentario = models.TextField(blank=True, null=True)
    criado_em = models.DateTimeField()
    atualizado_em = models.DateTimeField()

    class Meta:
        managed = False
        db_table = 'pesquisa_satisfacao'
        verbose_name = 'Pesquisa de satisfação'
        verbose_name_plural = 'Pesquisas de satisfação'


class Unidade(models.Model):
    class Genero(models.TextChoices):
        MASCULINO = "masculino", "Masculino"
        FEMININO = "feminino", "Feminino"

    id_unidade = models.AutoField(primary_key=True)
    nome_unidade = models.CharField(
        "nome da unidade",
        unique=True,
        max_length=300,
    )
    cnpj = models.CharField(unique=True, max_length=50)
    email_responsavel = models.CharField(unique=True, max_length=255)
    telefone = models.CharField(unique=True, max_length=20)
    waba_id = models.CharField(
        unique=True,
        max_length=100,
    )
    phone_number_id = models.CharField(unique=True, max_length=100)
    id_fuso = models.IntegerField(blank=True, null=True, editable=False)
    nome_fuso = models.TextField(blank=True, null=True, editable=False)
    fuso_verificado_em = models.DateTimeField(blank=True, null=True, editable=False)
    status_pagamento = models.BooleanField(
        "status pagamento / unidade ativa",
        blank=True, null=True, default=True,
        help_text=(
            "Sim: habilita o atendimento e os workers da unidade. Não ou desconhecido: "
            "suspende atendimento, follow-up, Funil, FireAds e consumo Meta, preservando "
            "o histórico e as pendências. Uma requisição externa já iniciada pode concluir."
        ),
    )
    id_usuario_monitoramento = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        models.SET_NULL,
        db_column='id_usuario_monitoramento',
        related_name='unidade_monitorada',
        verbose_name='usuário de monitoramento',
        blank=True,
        null=True,
        limit_choices_to={'is_staff': False, 'is_superuser': False},
        help_text=(
            'Selecione uma conta comum cadastrada em Usuários. '
            'Cada conta pode monitorar somente uma unidade. '
            'Deixe vazio para manter a unidade sem acesso de monitoramento.'
        ),
    )

    @property
    def nome_agente(self):
        return self.atendimento_customizado.nome_agente

    @property
    def genero(self):
        return self.atendimento_customizado.genero

    @property
    def numero_comercial(self):
        return self.atendimento_customizado.numero_comercial

    @property
    def idade_minima_suporte(self):
        return self.atendimento_customizado.idade_minima_suporte

    @property
    def email_obrigatorio(self):
        return self.atendimento_customizado.email_obrigatorio

    @property
    def link_agendamento(self):
        return self.atendimento_customizado.link_agendamento

    @property
    def link_instagram(self):
        return self.atendimento_customizado.link_instagram

    @property
    def bpa_ativo(self):
        return self.atendimento_customizado.bpa_ativo

    def clean(self):
        super().clean()
        if self.id_usuario_monitoramento_id and (
            self.id_usuario_monitoramento.is_staff
            or self.id_usuario_monitoramento.is_superuser
        ):
            raise ValidationError({
                'id_usuario_monitoramento': (
                    'O monitoramento exige uma conta sem acesso ao Admin '
                    'e sem status de superusuário.'
                ),
            })

    def __str__(self):
        return self.nome_unidade

    class Meta:
        managed = False
        db_table = 'unidade'


class IntegracaoFunilUnidade(models.Model):
    id_integracao_funil = models.AutoField(primary_key=True)
    id_unidade = models.OneToOneField(
        Unidade,
        models.CASCADE,
        db_column='id_unidade',
        related_name='integracao_funil',
    )
    nome_widget = models.CharField(max_length=300)
    data_salvamento_widget = models.DateField(blank=True, null=True)
    codigo_widget = models.CharField(unique=True, max_length=100)
    link_api_carrossel = models.URLField(unique=True, max_length=500)
    codigo_canal_venda = models.CharField(max_length=100)
    widget_ativo = models.BooleanField(default=True)
    integracao_ativa = models.BooleanField(default=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.id_unidade} / {self.nome_widget}"

    class Meta:
        managed = False
        db_table = 'integracao_funil_unidade'
        verbose_name = 'Integração do Funil por unidade'
        verbose_name_plural = 'Integrações do Funil por unidade'


class FunilEnvio(models.Model):
    id_funil_envio = models.AutoField(primary_key=True)
    id_conversa = models.OneToOneField(
        Conversa,
        models.CASCADE,
        db_column='id_conversa',
        related_name='envio_funil',
    )
    status = models.CharField(
        max_length=20,
        default='pending',
        choices=[
            ('pending', 'pending'),
            ('processing', 'processing'),
            ('sent', 'sent'),
        ],
    )
    attempt_count = models.IntegerField(default=0)
    next_attempt_at = models.DateTimeField()
    processing_started_at = models.DateTimeField(blank=True, null=True)
    enviado_em = models.DateTimeField(blank=True, null=True)
    ultimo_erro = models.TextField(blank=True, null=True)
    resposta_funil = models.TextField(blank=True, null=True)
    criado_em = models.DateTimeField()
    atualizado_em = models.DateTimeField()

    class Meta:
        managed = False
        db_table = 'funil_envios'
        verbose_name = 'Envio ao Funil'
        verbose_name_plural = 'Envios ao Funil'


class ClienteBloqueadoMeta(models.Model):
    id_bloqueio = models.AutoField(primary_key=True)
    id_cliente = models.ForeignKey(
        Cliente,
        models.SET_NULL,
        db_column='id_cliente',
        blank=True,
        null=True,
        related_name='bloqueios_meta',
    )
    nome = models.CharField(max_length=200, blank=True, null=True)
    wa_id_cliente = models.CharField(max_length=50)
    id_unidade = models.ForeignKey(
        Unidade,
        models.DO_NOTHING,
        db_column='id_unidade',
        related_name='bloqueios_meta',
    )
    phone_id_unidade = models.CharField(max_length=100)

    def __str__(self):
        return f"{self.wa_id_cliente} / {self.phone_id_unidade}"

    class Meta:
        managed = False
        db_table = 'cliente_bloqueado_meta'
        constraints = [
            models.UniqueConstraint(
                fields=["wa_id_cliente", "id_unidade"],
                name="uq_cliente_bloqueado_meta_wa_unidade",
            ),
        ]


class WebhookFloodEvento(models.Model):
    id_evento = models.BigAutoField(primary_key=True)
    wa_id_cliente = models.CharField(max_length=50)
    phone_id_unidade = models.CharField(max_length=100)
    id_hash_msg = models.CharField(unique=True, max_length=255)
    received_at = models.DateTimeField()

    def __str__(self):
        return f"{self.wa_id_cliente} / {self.phone_id_unidade}"

    class Meta:
        managed = False
        db_table = 'webhook_flood_evento'


class CacheControle(models.Model):
    nome = models.CharField(primary_key=True, max_length=100)
    versao = models.BigIntegerField(default=1)
    atualizado_em = models.DateTimeField()

    def __str__(self):
        return self.nome

    class Meta:
        managed = False
        db_table = 'cache_controle'


class ConsumoMensalMeta(models.Model):
    """Espelho de leitura; o worker persiste pelo repositório e a migração é SQL."""

    id_registro = models.BigAutoField(primary_key=True)
    id_unidade = models.ForeignKey(Unidade, models.DO_NOTHING, db_column='id_unidade')
    mes_referencia = models.DateField()
    waba_id = models.CharField(max_length=100)
    phone_number_id = models.CharField(max_length=100)
    timezone_id = models.IntegerField()
    fuso_horario = models.TextField()
    data_hora_inicio = models.DateTimeField()
    data_hora_fim = models.DateTimeField()
    qtd_janela_gratuita = models.BigIntegerField()
    qtd_franquia_consumida = models.BigIntegerField()
    qtd_cobradas_meta = models.BigIntegerField()
    franquia_meta_mensal = models.IntegerField(default=1000)
    beneficio_esl_mensal = models.IntegerField(default=1000)
    tarifa_referencia_brl = models.DecimalField(max_digits=12, decimal_places=6)
    tarifa_vigencia = models.DateField()
    consultado_ate = models.DateTimeField()
    ultimo_sucesso_em = models.DateTimeField()
    status_apuracao = models.CharField(max_length=20, choices=[
        ('em_andamento', 'Em andamento'), ('em_conferencia', 'Em conferência'),
        ('consolidado', 'Consolidado'),
    ])
    data_proxima_consolidacao = models.DateField(null=True, blank=True)
    consolidado_em = models.DateTimeField(null=True, blank=True)
    ultima_decisao_consolidacao_em = models.DateTimeField(null=True, blank=True)
    criado_em = models.DateTimeField()
    atualizado_em = models.DateTimeField()

    class Meta:
        managed = False
        db_table = 'consumo_mensal_meta'
        constraints = [models.UniqueConstraint(fields=['id_unidade', 'mes_referencia'], name='uq_consumo_unidade_mes')]


class ConsumoMetaColeta(models.Model):
    """Agenda de conta/período; também existe quando a primeira consulta falha."""

    pk = models.CompositePrimaryKey('id_unidade', 'periodo')
    id_unidade = models.IntegerField()
    periodo = models.CharField(max_length=7)
    proxima_consulta_em = models.DateTimeField()
    ultima_tentativa_em = models.DateTimeField(null=True, blank=True)
    ultimo_erro = models.TextField(null=True, blank=True)
    falhas_consecutivas = models.IntegerField(default=0)

    class Meta:
        managed = False
        db_table = 'consumo_meta_coletas'


class AtendimentoCustomizado(models.Model):
    Genero = Unidade.Genero
    id_customizacao = models.AutoField(primary_key=True)
    id_unidade = models.OneToOneField(
        Unidade,
        models.CASCADE,
        db_column="id_unidade",
        related_name="atendimento_customizado",
    )
    nome_agente = models.CharField("nome do agente", max_length=100)
    genero = models.CharField(
        "gênero do agente",
        max_length=9,
        choices=Genero.choices,
    )
    numero_comercial = models.CharField(
        max_length=30,
        help_text="Contato comercial obrigatório para toda unidade.",
    )
    idade_minima_suporte = models.IntegerField(
        "encaminhar titular ao comercial a partir de",
        blank=True,
        null=True,
        default=None,
        choices=[(None, "Desativado")]
        + [(idade, f"{idade}+") for idade in IDADES_MINIMAS_SUPORTE],
        help_text=(
            "Na etapa de idade, encaminha somente o titular a partir do limite "
            "até 89 anos e encerra sem bloqueio; 90+ é universal. Não altera a regra de e-mail."
        ),
    )
    email_obrigatorio = models.BooleanField(
        "e-mail obrigatório",
        default=True,
        help_text=("Exige um e-mail válido, exceto do titular com 60 anos ou mais."),
    )
    link_agendamento = models.CharField(
        unique=True,
        max_length=400,
        blank=True,
        null=True,
        help_text="Vazio: coleta o turno e entrega ao comercial após a triagem.",
    )
    link_instagram = models.CharField(
        max_length=400,
        blank=True,
        null=True,
    )
    bpa_ativo = models.BooleanField(default=False)

    def clean(self):
        super().clean()
        self.link_agendamento = (self.link_agendamento or "").strip() or None
        if not numero_comercial_whatsapp_valido(self.numero_comercial):
            raise ValidationError(
                {"numero_comercial": "Informe um número comercial brasileiro válido."}
            )

    def __str__(self):
        return str(self.id_unidade)

    class Meta:
        managed = False
        db_table = "atendimento_customizado"
        verbose_name = "Atendimento customizado"
        verbose_name_plural = "Atendimentos customizados"


class IntegracaoFireAds(models.Model):
    id_integracao_fireads = models.AutoField(primary_key=True)
    id_unidade = models.OneToOneField(
        Unidade,
        models.CASCADE,
        db_column="id_unidade",
        related_name="integracao_fireads",
    )
    integracao_ativa = models.BooleanField(default=False)
    url_dashbord = models.URLField(max_length=1000)
    url_operation = models.URLField(
        max_length=1000,
        blank=True,
        null=True,
        help_text="Referência do editor. Nunca usada para requisições.",
    )
    aba_google = models.CharField(
        max_length=200, default="Leads Google Ads (NÃO EDITAR)"
    )
    aba_meta = models.CharField(max_length=200, default="[FIRE] Leads Ads Geral - 7.2")
    aba_destino = models.CharField(max_length=200, default="LEADS GERAL - Feedback")
    fuso_formularios = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        help_text="Somente interpretação de datas sem offset. Preencher após confirmação na planilha; não altera o fuso externo.",
    )
    contrato_validado = models.BooleanField(
        default=False,
        help_text="Confirmar nomes de abas, campos e valores recebidos do formulário atualizado antes de ativar.",
    )
    ativada_em = models.DateTimeField(null=True, blank=True, editable=False)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    def clean(self):
        super().clean()
        from core.integrations.fireads.cliente import validar_url
        from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

        try:
            validar_url(self.url_dashbord)
        except ValueError as exc:
            raise ValidationError({"url_dashbord": str(exc)})
        self.fuso_formularios = (self.fuso_formularios or "").strip() or None
        if self.fuso_formularios:
            try:
                ZoneInfo(self.fuso_formularios)
            except ZoneInfoNotFoundError:
                raise ValidationError({"fuso_formularios": "Fuso IANA inválido."})
        if self.integracao_ativa and not self.contrato_validado:
            raise ValidationError(
                {"contrato_validado": "Confira o contrato de leitura antes de ativar."}
            )
        abas = [self.aba_google, self.aba_meta, self.aba_destino]
        if any(not a.strip() for a in abas) or len(set(abas)) != 3:
            raise ValidationError("Informe três abas distintas e não vazias.")

    def __str__(self):
        return str(self.id_unidade)

    class Meta:
        managed = False
        db_table = "integracao_fireads"
        verbose_name = "Integração FireAds"
        verbose_name_plural = "Integrações FireAds"


class Chat(models.Model):
    id_chat = models.BigAutoField(primary_key=True)
    id_cliente = models.ForeignKey(Cliente, models.CASCADE, db_column="id_cliente")
    id_unidade = models.ForeignKey(Unidade, models.CASCADE, db_column="id_unidade")
    criado_em = models.DateTimeField()

    def __str__(self):
        return f"{self.id_cliente} / {self.id_unidade}"

    class Meta:
        managed = False
        db_table = "chat"
        constraints = [
            models.UniqueConstraint(
                fields=["id_cliente", "id_unidade"], name="uq_chat_cliente_unidade"
            )
        ]


class ConsultaFireAds(models.Model):
    id_consulta = models.BigAutoField(primary_key=True)
    id_conversa = models.OneToOneField(Conversa, models.CASCADE, db_column="id_conversa")
    id_unidade = models.ForeignKey(Unidade, models.CASCADE, db_column="id_unidade")
    id_integracao_fireads = models.ForeignKey(
        IntegracaoFireAds, models.PROTECT, db_column="id_integracao_fireads"
    )
    status = models.CharField(max_length=20)
    consulta_concluida = models.BooleanField(default=False)
    resultado = models.CharField(max_length=30)
    entrada = models.JSONField()
    dados = models.JSONField(null=True, blank=True)
    aplicacao = models.JSONField(null=True, blank=True)
    solicitado_em = models.DateTimeField()
    prazo_final = models.DateTimeField()
    processing_started_at = models.DateTimeField(null=True, blank=True)
    reserva_ate = models.DateTimeField(null=True, blank=True)
    consultado_em = models.DateTimeField(null=True, blank=True)
    aplicado_em = models.DateTimeField(null=True, blank=True)
    atualizado_em = models.DateTimeField()
    tentativas = models.IntegerField(default=0)
    versao_reserva = models.BigIntegerField(default=0)
    ultimo_erro = models.TextField(null=True, blank=True)

    def __str__(self):
        return f"Consulta {self.pk} / conversa {self.id_conversa_id} / {self.status}"

    class Meta:
        managed = False
        db_table = "consulta_fireads"
        verbose_name_plural = "Consultas FireAds"


class EnvioDash(models.Model):
    id_envio_dash = models.BigAutoField(primary_key=True)
    id_conversa = models.OneToOneField(
        Conversa, models.CASCADE, db_column="id_conversa"
    )
    id_integracao_fireads = models.ForeignKey(
        IntegracaoFireAds, models.PROTECT, db_column="id_integracao_fireads"
    )
    id_unidade = models.ForeignKey(Unidade, models.CASCADE, db_column="id_unidade")
    status = models.CharField(max_length=20, default="pending")
    attempt_count = models.IntegerField(default=0)
    next_attempt_at = models.DateTimeField()
    processing_started_at = models.DateTimeField(null=True, blank=True)
    enviado_em = models.DateTimeField(null=True, blank=True)
    ultimo_erro = models.TextField(null=True, blank=True)
    recibo = models.JSONField(null=True, blank=True)
    snapshot = models.JSONField()
    criado_em = models.DateTimeField()
    atualizado_em = models.DateTimeField()

    class Meta:
        managed = False
        db_table = "envios_dash"
        verbose_name_plural = "Envios ao dashboard"
````

## Passo 14: `callback/webhook/admin.py`

Exibir consultas, conversa, chat e estado operacional em modo somente leitura.

````python
import logging

from django.contrib import admin, messages
from django.db import DatabaseError, connection
from django.http import HttpResponseRedirect
from django.urls import NoReverseMatch, reverse
from django.utils.html import format_html

from core.cache.cache_unidade import (
    CacheUnidadesIndisponivel,
    recarregar_cache_unidades_ou_erro,
    validar_cache_unidades_disponivel_ou_erro,
)
from core.integrations.whatsapp.tools.ativando_numero import registrar_numero_whatsapp
from core.integrations.whatsapp.tools.ativando_waba_id import ativar_waba_id
from core.integrations.whatsapp.tools.desativa_waba_id import desativar_waba_id
from core.integrations.whatsapp.tools.desativando_numero import desregistrar_numero_whatsapp
from core.integrations.whatsapp.tools.usuarios import (
    desbloquear_usuario_meta,
)
from core.integrations.whatsapp.tools.validando_phone_waba import (
    validar_phone_number_id_da_waba,
)
from core.logging_config import short_value
from core.repositories.unidades.cache_control import (
    incrementar_versao_cache_unidades,
)

from .models import (
    AtendimentoCustomizado,
    CacheControle,
    Chat,
    Cliente,
    ClienteBloqueadoMeta,
    Conversa,
    ConsultaFireAds,
    Dependente,
    Etapa,
    EnvioDash,
    FilaMensagens,
    FunilEnvio,
    HistoricoMensagens,
    IntegracaoFunilUnidade,
    IntegracaoFireAds,
    PesquisaSatisfacao,
    RespostasDesafios,
    Unidade,
    WebhookFloodEvento,
)

logger = logging.getLogger(__name__)


class SomenteVisualizacaoAdminMixin:
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def get_readonly_fields(self, request, obj=None):
        return [field.name for field in self.model._meta.fields]


@admin.register(IntegracaoFunilUnidade)
class IntegracaoFunilUnidadeAdmin(admin.ModelAdmin):
    list_display = (
        "id_integracao_funil",
        "id_unidade",
        "nome_widget",
        "codigo_widget",
        "codigo_canal_venda",
        "widget_ativo",
        "integracao_ativa",
        "data_salvamento_widget",
        "atualizado_em",
    )

    search_fields = (
        "id_unidade__nome_unidade",
        "nome_widget",
        "codigo_widget",
        "codigo_canal_venda",
        "link_api_carrossel",
    )

    list_filter = (
        "widget_ativo",
        "integracao_ativa",
        "data_salvamento_widget",
    )

    readonly_fields = (
        "criado_em",
        "atualizado_em",
    )

    ordering = ("id_unidade",)
    list_select_related = ("id_unidade",)
    list_per_page = 50
    empty_value_display = "-"


@admin.register(FunilEnvio)
class FunilEnvioAdmin(SomenteVisualizacaoAdminMixin, admin.ModelAdmin):
    list_display = (
        "id_funil_envio",
        "id_conversa",
        "status",
        "attempt_count",
        "next_attempt_at",
        "processing_started_at",
        "enviado_em",
        "atualizado_em",
    )
    search_fields = (
        "id_conversa__id_conversa",
        "id_conversa__id_cliente__nome",
        "id_conversa__id_cliente__waid_telefone",
    )
    list_filter = ("status",)
    ordering = ("-atualizado_em",)
    date_hierarchy = "criado_em"
    list_select_related = (
        "id_conversa",
        "id_conversa__id_cliente",
    )
    list_per_page = 50
    empty_value_display = "-"


class AtendimentoCustomizadoInline(admin.StackedInline):
    model = AtendimentoCustomizado
    extra = 1
    min_num = 1
    max_num = 1
    can_delete = False
    validate_min = True

    def get_formset(self, request, obj=None, **kwargs):
        kwargs.update(validate_min=True, validate_max=True)
        return super().get_formset(request, obj, **kwargs)


@admin.register(Unidade)
class UnidadeAdmin(admin.ModelAdmin):
    inlines = (AtendimentoCustomizadoInline,)

    list_display = (
        "id_unidade",
        "nome_unidade",
        "id_usuario_monitoramento",
        "cnpj",
        "telefone",
        "email_responsavel",
        "waba_id",
        "phone_number_id",
        "status_pagamento",
    )

    search_fields = (
        "nome_unidade",
        "id_usuario_monitoramento__username",
        "cnpj",
        "telefone",
        "email_responsavel",
        "waba_id",
        "phone_number_id",
    )

    list_filter = (
        "status_pagamento",
    )
    ordering = ("nome_unidade",)
    list_select_related = ("id_usuario_monitoramento", "atendimento_customizado")

    list_per_page = 50
    empty_value_display = "-"

    def get_inlines(self, request, obj=None):
        # Uma unidade nova precisa da personalização na mesma transação.
        # Depois do cadastro, a edição fica na tela própria da personalização.
        return self.inlines if obj is None else ()

    def get_readonly_fields(self, request, obj=None):
        if obj is not None:
            return ("waba_id", "phone_number_id", "abrir_atendimento_customizado")

        return ()

    @admin.display(description="Atendimento customizado")
    def abrir_atendimento_customizado(self, obj):
        url = reverse(
            "admin:webhook_atendimentocustomizado_change",
            args=[obj.atendimento_customizado.pk],
        )
        return format_html('<a href="{}">Editar personalização da unidade</a>', url)

    def _create_formsets(self, request, obj, change):
        formsets, inlines = super()._create_formsets(request, obj, change)
        # O Django cria os inlines antes de validar o formulário principal.
        # A chamada à Meta só pode acontecer com a personalização válida também.
        request._unidade_formsets = formsets
        return formsets, inlines

    def changeform_view(self, request, object_id=None, form_url="", extra_context=None):
        try:
            return super().changeform_view(
                request,
                object_id=object_id,
                form_url=form_url,
                extra_context=extra_context,
            )

        except CacheUnidadesIndisponivel as exc:
            if self._falha_cache_originada_no_banco(exc):
                return self._responder_falha_banco(
                    request,
                    object_id,
                    exc,
                )

            logger.exception(
                "admin_unidade_cache_falhou | acao=rollback_admin object_id=%s meta_ok=%s erro=%s",
                object_id,
                self._meta_sucesso_nesta_requisicao(request),
                exc,
            )
            self.message_user(
                request,
                self._mensagem_falha_redis(request),
                level=messages.ERROR,
            )
            return HttpResponseRedirect(request.path)

        except DatabaseError as exc:
            return self._responder_falha_banco(
                request,
                object_id,
                exc,
            )

    def get_form(self, request, obj=None, change=False, **kwargs):
        base_form = super().get_form(request, obj, change=change, **kwargs)
        model_admin = self

        class UnidadeAdminForm(base_form):
            def _post_clean(self):
                super()._post_clean()

                if change or self.errors:
                    if change and not self.errors:
                        model_admin._validar_cache_unidades_form(
                            self,
                            request,
                            meta_validada=False,
                        )
                    return

                if any(
                    not formset.is_valid()
                    for formset in getattr(request, "_unidade_formsets", ())
                ):
                    self.add_error(None, "Confira os dados do atendimento customizado.")
                    return

                waba_id = self.cleaned_data.get("waba_id")
                phone_number_id = self.cleaned_data.get("phone_number_id")

                if not waba_id:
                    self.add_error(
                        "waba_id",
                        "Informe a WABA que sera assinada pelo App.",
                    )
                    return

                campo_com_erro = model_admin._preparar_meta_antes_de_salvar(
                    request,
                    waba_id,
                    phone_number_id,
                )

                if campo_com_erro == "vinculo_waba_phone":
                    self.add_error(
                        "phone_number_id",
                        "Este phone ID nao pertence a WABA informada. "
                        "A unidade nao foi salva.",
                    )
                    return

                if campo_com_erro == "waba_id":
                    self.add_error(
                        "waba_id",
                        "A Meta falhou ao assinar esta WABA. Unidade nao foi salva.",
                    )
                    return

                if campo_com_erro == "phone_number_id":
                    self.add_error(
                        "phone_number_id",
                        "A Meta falhou ao registrar este numero. Unidade nao foi salva.",
                    )
                    return

                model_admin._validar_cache_unidades_form(
                    self,
                    request,
                    meta_validada=True,
                )

        return UnidadeAdminForm

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        self._registrar_alteracao_cache_unidades()

    def delete_model(self, request, obj):
        if not self._meta_desregistrada_nesta_requisicao(request, obj):
            if not self._desregistrar_meta_antes_de_excluir(request, obj):
                return

        if not self._cache_validado_nesta_requisicao(request, obj):
            if not self._validar_cache_unidades_antes_de_alterar(
                request,
                "excluir",
                meta_validada=True,
            ):
                return

        super().delete_model(request, obj)
        self._registrar_alteracao_cache_unidades()

    def get_actions(self, request):
        actions = super().get_actions(request)
        actions.pop("delete_selected", None)
        return actions

    def delete_queryset(self, request, queryset):
        logger.warning(
            "admin_unidade_exclusao_massa_bloqueada | acao=manter_registros usuario=%s total=%s",
            request.user,
            queryset.count(),
        )
        self.message_user(
            request,
            "Exclusao em massa de unidade nao permitida. Exclua uma unidade por vez.",
            level=messages.ERROR,
        )

    def delete_view(self, request, object_id, extra_context=None):
        try:
            if request.method == "POST":
                obj = self.get_object(request, object_id)

                if obj and not self._desregistrar_meta_antes_de_excluir(request, obj):
                    return HttpResponseRedirect(
                        reverse(
                            "admin:webhook_unidade_change",
                            args=[object_id],
                        )
                    )

                if obj and not self._validar_cache_unidades_antes_de_alterar(
                    request,
                    "excluir",
                    meta_validada=True,
                ):
                    return HttpResponseRedirect(
                        reverse(
                            "admin:webhook_unidade_change",
                            args=[object_id],
                        )
                    )

                if obj:
                    self._marcar_meta_desregistrada_na_requisicao(request, obj)
                    self._marcar_cache_validado_na_requisicao(request, obj)

            return super().delete_view(request, object_id, extra_context)

        except CacheUnidadesIndisponivel as exc:
            if self._falha_cache_originada_no_banco(exc):
                return self._responder_falha_banco_delete(
                    request,
                    object_id,
                    exc,
                )

            logger.exception(
                "admin_unidade_cache_delete_falhou | acao=rollback_admin object_id=%s meta_ok=%s erro=%s",
                object_id,
                self._meta_sucesso_nesta_requisicao(request),
                exc,
            )
            self.message_user(
                request,
                self._mensagem_falha_redis(request),
                level=messages.ERROR,
            )
            return HttpResponseRedirect(
                reverse(
                    "admin:webhook_unidade_change",
                    args=[object_id],
                )
            )

        except DatabaseError as exc:
            return self._responder_falha_banco_delete(
                request,
                object_id,
                exc,
            )

    def _registrar_alteracao_cache_unidades(self):
        with connection.cursor() as cursor:
            versao = incrementar_versao_cache_unidades(cursor)
            total_unidades = recarregar_cache_unidades_ou_erro(cursor)

        logger.info(
            "cache_unidades_versao_incrementada | acao=incrementar_versao_e_recarregar versao=%s unidades=%s",
            versao,
            total_unidades,
        )

    def link_agendamento_clickable(self, obj):
        if obj.link_agendamento:
            return format_html(
                '<a href="{}" target="_blank">Abrir</a>',
                obj.link_agendamento,
            )
        return "-"

    link_agendamento_clickable.short_description = "Agendamento"

    def link_instagram_clickable(self, obj):
        if obj.link_instagram:
            return format_html(
                '<a href="{}" target="_blank">Abrir</a>',
                obj.link_instagram,
            )
        return "-"

    link_instagram_clickable.short_description = "Instagram"

    def _preparar_meta_antes_de_salvar(
        self,
        request,
        waba_id,
        phone_number_id,
    ):
        if not self._validar_vinculo_phone_waba_antes_de_salvar(
            request,
            waba_id,
            phone_number_id,
        ):
            return "vinculo_waba_phone"

        if not self._ativar_waba_antes_de_salvar(request, waba_id):
            return "waba_id"

        if not self._registrar_meta_antes_de_salvar(
            request,
            phone_number_id,
        ):
            return "phone_number_id"

        return None

    def _validar_vinculo_phone_waba_antes_de_salvar(
        self,
        request,
        waba_id,
        phone_number_id,
    ):
        try:
            status, resposta = validar_phone_number_id_da_waba(
                waba_id,
                phone_number_id,
            )

            if not self._meta_resposta_sucesso(status, resposta):
                logger.error(
                    "whatsapp_phone_waba_vinculo_invalido | "
                    "acao=bloquear_save waba_id=%s phone_number_id=%s "
                    "status=%s motivo=%s",
                    short_value(waba_id),
                    short_value(phone_number_id),
                    status,
                    resposta.get("reason")
                    if isinstance(resposta, dict)
                    else None,
                )
                self.message_user(
                    request,
                    "A Meta nao confirmou que o phone ID pertence a "
                    "WABA informada. A unidade nao foi salva.",
                    level=messages.ERROR,
                )
                return False

            logger.info(
                "whatsapp_phone_waba_vinculo_ok | "
                "acao=permitir_ativacao waba_id=%s phone_number_id=%s",
                short_value(waba_id),
                short_value(phone_number_id),
            )
            return True

        except Exception as exc:
            logger.exception(
                "whatsapp_phone_waba_validacao_erro | "
                "acao=bloquear_save waba_id=%s phone_number_id=%s "
                "erro=%s",
                short_value(waba_id),
                short_value(phone_number_id),
                exc,
            )
            self.message_user(
                request,
                "Erro ao validar WABA e phone ID na Meta. "
                f"A unidade nao foi salva: {exc}",
                level=messages.ERROR,
            )
            return False

    def _ativar_waba_antes_de_salvar(self, request, waba_id):
        try:
            status, resposta = ativar_waba_id(waba_id)

            if not self._meta_resposta_sucesso(status, resposta):
                logger.error(
                    "whatsapp_waba_ativar_falhou | acao=bloquear_save "
                    "waba_id=%s status=%s resposta=%s",
                    short_value(waba_id),
                    status,
                    resposta,
                )
                self.message_user(
                    request,
                    "Erro ao assinar WABA no WhatsApp. "
                    f"Unidade nao foi salva: {resposta}",
                    level=messages.ERROR,
                )
                return False

            self._marcar_meta_sucesso(
                request,
                acao="ativar_waba",
                waba_id=waba_id,
            )
            logger.info(
                "whatsapp_waba_ativada | acao=permitir_registro_numero "
                "waba_id=%s status=%s",
                short_value(waba_id),
                status,
            )
            return True

        except Exception as exc:
            logger.exception(
                "whatsapp_waba_ativar_erro | acao=bloquear_save "
                "waba_id=%s erro=%s",
                short_value(waba_id),
                exc,
            )
            self.message_user(
                request,
                "Erro inesperado ao assinar WABA. "
                f"Unidade nao foi salva: {exc}",
                level=messages.ERROR,
            )
            return False

    def _registrar_meta_antes_de_salvar(self, request, phone_number_id):
        try:
            status, resposta = registrar_numero_whatsapp(phone_number_id)

            if not self._meta_resposta_sucesso(status, resposta):
                logger.error(
                    "whatsapp_numero_registrar_falhou | acao=bloquear_save phone_number_id=%s status=%s resposta=%s",
                    short_value(phone_number_id),
                    status,
                    resposta,
                )
                self.message_user(
                    request,
                    f"Erro ao registrar numero no WhatsApp. Unidade nao foi salva: {resposta}",
                    level=messages.ERROR,
                )
                return False

            self._marcar_meta_sucesso(
                request,
                acao="registrar_numero",
                phone_number_id=phone_number_id,
            )
            logger.info(
                "whatsapp_numero_registrado | acao=permitir_save phone_number_id=%s status=%s",
                short_value(phone_number_id),
                status,
            )
            return True

        except Exception as exc:
            logger.exception(
                "whatsapp_numero_registrar_erro | acao=bloquear_save phone_number_id=%s erro=%s",
                short_value(phone_number_id),
                exc,
            )
            self.message_user(
                request,
                f"Erro inesperado ao registrar numero. Unidade nao foi salva: {exc}",
                level=messages.ERROR,
            )
            return False

    def _desregistrar_meta_antes_de_excluir(self, request, obj):
        if not self._desassinar_waba_antes_de_excluir(request, obj):
            return False

        try:
            status, resposta = desregistrar_numero_whatsapp(obj.phone_number_id)

            if not self._meta_resposta_sucesso(status, resposta):
                logger.error(
                    "whatsapp_numero_desregistrar_falhou | acao=bloquear_delete phone_number_id=%s status=%s resposta=%s",
                    short_value(obj.phone_number_id),
                    status,
                    resposta,
                )
                self.message_user(
                    request,
                    "A WABA foi desassinada, mas a Meta falhou ao "
                    "desregistrar o numero. Unidade mantida no banco: "
                    f"{resposta}",
                    level=messages.ERROR,
                )
                return False

            self._marcar_meta_sucesso(
                request,
                acao="desregistrar_numero",
                phone_number_id=obj.phone_number_id,
            )
            logger.warning(
                "whatsapp_numero_desregistrado | acao=permitir_delete phone_number_id=%s status=%s",
                short_value(obj.phone_number_id),
                status,
            )
            return True

        except Exception as exc:
            logger.exception(
                "whatsapp_numero_desregistrar_erro | acao=bloquear_delete phone_number_id=%s erro=%s",
                short_value(obj.phone_number_id),
                exc,
            )
            self.message_user(
                request,
                "A WABA foi desassinada, mas ocorreu um erro ao "
                "desregistrar o numero. Unidade mantida no banco: "
                f"{exc}",
                level=messages.ERROR,
            )
            return False

    def _desassinar_waba_antes_de_excluir(self, request, obj):
        try:
            status, resposta = desativar_waba_id(obj.waba_id)

            if not self._meta_resposta_sucesso(status, resposta):
                logger.error(
                    "whatsapp_waba_desassinar_falhou | "
                    "acao=bloquear_delete waba_id=%s status=%s "
                    "resposta=%s",
                    short_value(obj.waba_id),
                    status,
                    resposta,
                )
                self.message_user(
                    request,
                    "Erro ao remover a assinatura da WABA na Meta. "
                    f"Unidade mantida no banco: {resposta}",
                    level=messages.ERROR,
                )
                return False

            self._marcar_meta_sucesso(
                request,
                acao="desativar_waba",
                waba_id=obj.waba_id,
            )
            logger.warning(
                "whatsapp_waba_desassinada | acao=continuar_delete "
                "waba_id=%s status=%s",
                short_value(obj.waba_id),
                status,
            )
            return True

        except Exception as exc:
            logger.exception(
                "whatsapp_waba_desassinar_erro | "
                "acao=bloquear_delete waba_id=%s erro=%s",
                short_value(obj.waba_id),
                exc,
            )
            self.message_user(
                request,
                "Erro inesperado ao remover a assinatura da WABA. "
                f"Unidade mantida no banco: {exc}",
                level=messages.ERROR,
            )
            return False

    def _marcar_meta_sucesso(
        self,
        request,
        acao,
        **identificadores,
    ):
        operacoes = list(
            getattr(request, "_unidade_meta_sucesso", [])
        )
        operacoes.append({
            "acao": acao,
            **{
                nome: str(valor)
                for nome, valor in identificadores.items()
            },
        })
        request._unidade_meta_sucesso = operacoes

    @staticmethod
    def _meta_sucesso_nesta_requisicao(request):
        return bool(
            getattr(
                request,
                "_unidade_meta_sucesso",
                None,
            )
        )

    def _marcar_meta_desregistrada_na_requisicao(self, request, obj):
        ids = getattr(request, "_unidades_meta_desregistradas", set())
        ids.add(obj.id_unidade)
        request._unidades_meta_desregistradas = ids

    def _meta_desregistrada_nesta_requisicao(self, request, obj):
        ids = getattr(request, "_unidades_meta_desregistradas", set())
        return obj.id_unidade in ids

    def _marcar_cache_validado_na_requisicao(self, request, obj):
        ids = getattr(request, "_unidades_cache_validadas", set())
        ids.add(obj.id_unidade)
        request._unidades_cache_validadas = ids

    def _cache_validado_nesta_requisicao(self, request, obj):
        ids = getattr(request, "_unidades_cache_validadas", set())
        return obj.id_unidade in ids

    def _validar_cache_unidades_form(self, form, request, meta_validada):
        if self._validar_cache_unidades_antes_de_alterar(
            request,
            "salvar",
            meta_validada=meta_validada,
        ):
            return

        form.add_error(
            None,
            self._mensagem_cache_unidades_falhou(meta_validada),
        )

    def _validar_cache_unidades_antes_de_alterar(
        self,
        request,
        acao,
        meta_validada=False,
    ):
        try:
            validar_cache_unidades_disponivel_ou_erro()
            logger.info(
                "cache_unidades_preflight_admin_ok | acao=%s",
                acao,
            )
            return True

        except CacheUnidadesIndisponivel as exc:
            logger.error(
                "cache_unidades_preflight_admin_falhou | acao=%s erro=%s",
                acao,
                exc,
            )

            if request is not None:
                self.message_user(
                    request,
                    self._mensagem_cache_unidades_falhou(meta_validada),
                    level=messages.ERROR,
                )

            return False

    def _responder_falha_banco(
        self,
        request,
        object_id,
        exc,
    ):
        logger.exception(
            "admin_unidade_banco_falhou | acao=rollback_sem_compensacao object_id=%s meta_ok=%s erro=%s",
            object_id,
            self._meta_sucesso_nesta_requisicao(request),
            exc,
        )
        self.message_user(
            request,
            self._mensagem_falha_banco(request),
            level=messages.ERROR,
        )
        return HttpResponseRedirect(request.path)

    def _responder_falha_banco_delete(
        self,
        request,
        object_id,
        exc,
    ):
        logger.exception(
            "admin_unidade_banco_delete_falhou | acao=rollback_sem_compensacao object_id=%s meta_ok=%s erro=%s",
            object_id,
            self._meta_sucesso_nesta_requisicao(request),
            exc,
        )
        self.message_user(
            request,
            self._mensagem_falha_banco(request),
            level=messages.ERROR,
        )
        return HttpResponseRedirect(
            reverse(
                "admin:webhook_unidade_change",
                args=[object_id],
            )
        )

    def _mensagem_falha_banco(self, request):
        if self._meta_sucesso_nesta_requisicao(request):
            return (
                "A Meta concluiu a operação com sucesso, mas o banco "
                "falhou. A alteração da Meta foi mantida; banco e "
                "cache de unidades no Redis não foram confirmados. Faça uma "
                "conferência manual."
            )

        return (
            "O banco falhou e nenhuma alteração local foi "
            "confirmada. Nenhuma operação Meta foi concluída nesta "
            "requisição."
        )

    def _mensagem_falha_redis(self, request):
        if self._meta_sucesso_nesta_requisicao(request):
            return (
                "A Meta concluiu a operação com sucesso, mas o Redis "
                "falhou. A alteração da Meta foi mantida; nenhuma "
                "alteração foi confirmada no banco ou no cache. Faça "
                "uma conferência manual."
            )

        return (
            "O Redis falhou ao atualizar o cache de unidades. "
            "Nenhuma alteração foi confirmada no banco."
        )

    @staticmethod
    def _mensagem_cache_unidades_falhou(meta_validada):
        if meta_validada:
            return (
                "A Meta concluiu a operação com sucesso, mas o Redis "
                "falhou. A alteração da Meta foi mantida e a unidade "
                "não foi salva no banco. Faça uma conferência manual."
            )

        return (
            "O Redis falhou ao atualizar o cache de unidades. "
            "Nenhuma alteração foi feita no banco."
        )

    @staticmethod
    def _falha_cache_originada_no_banco(exc):
        causa = exc.__cause__

        while causa is not None:
            if isinstance(causa, DatabaseError):
                return True

            causa = causa.__cause__

        return False

    @staticmethod
    def _meta_resposta_sucesso(status, resposta):
        if status not in (200, 204):
            return False

        if isinstance(resposta, dict) and resposta.get("success") is False:
            return False

        return True


@admin.register(Cliente)
class ClienteAdmin(SomenteVisualizacaoAdminMixin, admin.ModelAdmin):

    list_display = (
        "id_cliente",
        "nome",
        "waid_telefone",
        "email",
        "idade",
        "profissao",
    )

    search_fields = (
        "nome",
        "waid_telefone",
        "email",
        "profissao",
    )

    ordering = ("nome",)
    list_per_page = 50
    empty_value_display = "-"


@admin.register(Dependente)
class DependenteAdmin(SomenteVisualizacaoAdminMixin, admin.ModelAdmin):

    list_display = (
        "id_dependente",
        "id_cliente",
        "id_conversa",
        "nome_dependente",
        "idade",
    )

    search_fields = (
        "nome_dependente",
        "id_cliente__waid_telefone",
        "id_cliente__nome",
    )

    ordering = ("id_dependente",)
    list_per_page = 50
    empty_value_display = "-"

    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            "id_cliente",
            "id_conversa",
        )


@admin.register(Etapa)
class EtapaAdmin(SomenteVisualizacaoAdminMixin, admin.ModelAdmin):

    list_display = (
        "id_etapa",
        "nome_etapa",
        "encerra_automaticamente",
        "bloqueio_dias",
        "elegivel_funil",
    )

    search_fields = ("nome_etapa",)
    list_filter = (
        "encerra_automaticamente",
        "elegivel_funil",
    )
    ordering = ("id_etapa",)

    list_per_page = 50
    empty_value_display = "-"


@admin.register(Conversa)
class ConversaAdmin(SomenteVisualizacaoAdminMixin, admin.ModelAdmin):

    list_display = (
        "id_conversa",
        "cliente_link",
        "id_unidade",
        "id_etapa_atual",
        "profissao",
        "turnos_sem_avanco",
        "status_ativa",
        "motivo_encerramento",
        "last_message_from",
        "followup_stage",
        "lead_no_funil",
        "processing",
        "last_interaction_at",
        "iniciou_em",
    )

    search_fields = (
        "id_cliente__waid_telefone",
        "id_cliente__nome",
        "profissao",
    )

    list_filter = (
        "status_ativa",
        "motivo_encerramento",
        "turnos_sem_avanco",
        "lead_no_funil",
        "last_message_from",
        "followup_stage",
        "processing",
        "id_unidade",
        "id_etapa_atual",
    )

    ordering = ("-iniciou_em",)

    date_hierarchy = "iniciou_em"
    list_per_page = 50
    empty_value_display = "-"

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related(
            "id_cliente",
            "id_unidade",
            "id_etapa_atual",
        )

    def cliente_link(self, obj):
        if not obj.id_cliente:
            return "-"

        try:
            url = reverse(
                "admin:webhook_cliente_change",
                args=[obj.id_cliente.id_cliente],
            )
            return format_html(
                '<a href="{}">{}</a>',
                url,
                obj.id_cliente.nome or obj.id_cliente.waid_telefone,
            )
        except NoReverseMatch as exc:
            logger.exception(
                "admin_cliente_link_falhou | acao=retornar_texto_sem_link erro=%s",
                exc,
            )
            return obj.id_cliente.nome or obj.id_cliente.waid_telefone

    cliente_link.short_description = "Cliente"


@admin.register(FilaMensagens)
class FilaMensagensAdmin(SomenteVisualizacaoAdminMixin, admin.ModelAdmin):

    list_display = (
        "id_mensagem",
        "id_conversa",
        "status_colorido",
        "tipo_mensagem",
        "cliente_telefone",
        "id_hash_msg",
        "received_data_hora",
        "retry_count",
        "next_attempt_at",
        "erro_resumido",
    )

    search_fields = (
        "cliente_telefone",
        "id_hash_msg",
        "id_conversa__id_conversa",
    )

    list_filter = (
        "status",
        "tipo_mensagem",
        "id_conversa",
    )

    ordering = ("-received_data_hora",)
    date_hierarchy = "received_data_hora"

    list_per_page = 50
    empty_value_display = "-"

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("id_conversa")

    def status_colorido(self, obj):
        cores = {
            "sent": "green",
            "failed": "red",
            "pending": "#555",
            "processing": "orange",
        }
        cor = cores.get(obj.status, "#000")
        return format_html('<b style="color:{};">{}</b>', cor, obj.status)

    status_colorido.short_description = "Status"

    def erro_resumido(self, obj):
        if not obj.last_error:
            return "-"

        texto = obj.last_error[:60]

        return format_html(
            '<span title="{}">{}</span>',
            obj.last_error,
            texto + ("..." if len(obj.last_error) > 60 else ""),
        )

    erro_resumido.short_description = "Erro"


@admin.register(HistoricoMensagens)
class HistoricoMensagensAdmin(SomenteVisualizacaoAdminMixin, admin.ModelAdmin):

    list_display = (
        "id_mensagem",
        "quem_enviou",
        "tipo_mensagem",
        "status_envio",
        "id_conversa",
        "id_etapa",
        "id_mensagem_fila",
        "id_hash_cliente_origem",
        "cliente_telefone",
        "received_data_hora",
    )

    search_fields = (
        "cliente_telefone",
        "id_hash_msg",
        "id_hash_cliente_origem",
        "id_mensagem_fila__id_mensagem",
    )

    list_filter = (
        "quem_enviou",
        "status_envio",
        "id_etapa",
        "tipo_mensagem",
    )

    ordering = ("-received_data_hora",)

    date_hierarchy = "received_data_hora"
    list_per_page = 50

    empty_value_display = "-"

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related(
            "id_conversa",
            "id_etapa",
            "id_mensagem_fila",
        )


@admin.register(RespostasDesafios)
class RespostasDesafiosAdmin(SomenteVisualizacaoAdminMixin, admin.ModelAdmin):

    list_display = (
        "id_resposta_desafio",
        "id_conversa",
        "id_etapa",
        "resposta",
        "id_historico_mensagem_cliente",
        "criado_em",
    )

    search_fields = (
        "resposta",
    )

    list_filter = (
        "id_etapa",
    )

    ordering = ("-criado_em",)
    date_hierarchy = "criado_em"
    list_per_page = 50
    empty_value_display = "-"

    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            "id_conversa",
            "id_etapa",
        )


@admin.register(PesquisaSatisfacao)
class PesquisaSatisfacaoAdmin(SomenteVisualizacaoAdminMixin, admin.ModelAdmin):

    list_display = (
        "id_pesquisa_satisfacao",
        "id_conversa",
        "nota",
        "comentario",
        "criado_em",
        "atualizado_em",
    )

    search_fields = (
        "id_conversa__id_conversa",
        "id_conversa__id_cliente__nome",
        "comentario",
    )

    list_filter = ("nota",)
    ordering = ("-atualizado_em",)
    date_hierarchy = "atualizado_em"
    list_per_page = 50
    empty_value_display = "-"

    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            "id_conversa",
            "id_conversa__id_cliente",
        )


@admin.register(WebhookFloodEvento)
class WebhookFloodEventoAdmin(SomenteVisualizacaoAdminMixin, admin.ModelAdmin):

    list_display = (
        "id_evento",
        "wa_id_cliente",
        "phone_id_unidade",
        "id_hash_msg",
        "received_at",
    )

    search_fields = (
        "wa_id_cliente",
        "phone_id_unidade",
        "id_hash_msg",
    )

    list_filter = ("phone_id_unidade",)
    ordering = ("-received_at",)
    date_hierarchy = "received_at"
    list_per_page = 50
    empty_value_display = "-"


@admin.register(CacheControle)
class CacheControleAdmin(SomenteVisualizacaoAdminMixin, admin.ModelAdmin):

    list_display = (
        "nome",
        "versao",
        "atualizado_em",
    )

    search_fields = ("nome",)
    ordering = ("nome",)
    list_per_page = 50
    empty_value_display = "-"


@admin.register(ClienteBloqueadoMeta)
class ClienteBloqueadoMetaAdmin(admin.ModelAdmin):

    list_display = (
        "id_bloqueio",
        "cliente_link",
        "nome",
        "wa_id_cliente",
        "id_unidade",
        "phone_id_unidade",
    )

    search_fields = (
        "nome",
        "wa_id_cliente",
        "phone_id_unidade",
        "id_cliente__waid_telefone",
        "id_cliente__nome",
        "id_unidade__nome_unidade",
    )

    list_filter = ("id_unidade",)
    ordering = ("wa_id_cliente", "id_unidade__nome_unidade")
    list_per_page = 50
    empty_value_display = "-"

    def has_add_permission(self, request):
        return False

    def get_actions(self, request):
        actions = super().get_actions(request)
        actions.pop("delete_selected", None)
        return actions

    def get_readonly_fields(self, request, obj=None):
        return [field.name for field in self.model._meta.fields]

    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            "id_cliente",
            "id_unidade",
        )

    def delete_view(self, request, object_id, extra_context=None):
        if request.method == "POST":
            obj = self.get_object(request, object_id)

            if obj and not self._desbloquear_meta_antes_de_excluir(request, obj):
                return HttpResponseRedirect(
                    reverse(
                        "admin:webhook_clientebloqueadometa_change",
                        args=[object_id],
                    )
                )

        return super().delete_view(request, object_id, extra_context)

    def delete_model(self, request, obj):
        conversas_resetadas = Conversa.objects.filter(
            id_cliente_id=obj.id_cliente_id,
            id_unidade_id=obj.id_unidade_id,
            status_ativa=True,
        ).update(turnos_sem_avanco=0)

        logger.warning(
            "admin_bloqueio_meta_excluido | "
            "acao=resetar_contador_e_excluir_registro "
            "usuario=%s wa_id_cliente=%s phone_id_unidade=%s "
            "conversas_resetadas=%s",
            request.user,
            short_value(obj.wa_id_cliente),
            short_value(obj.phone_id_unidade),
            conversas_resetadas,
        )
        super().delete_model(request, obj)

    def delete_queryset(self, request, queryset):
        logger.warning(
            "admin_bloqueio_meta_exclusao_massa_bloqueada | acao=manter_registros usuario=%s total=%s",
            request.user,
            queryset.count(),
        )
        self.message_user(
            request,
            "Exclusao em massa desativada. Desbloqueie um cliente por unidade de cada vez.",
            level=messages.ERROR,
        )

    def cliente_link(self, obj):
        if not obj.id_cliente:
            return "-"

        try:
            url = reverse(
                "admin:webhook_cliente_change",
                args=[obj.id_cliente.id_cliente],
            )
            return format_html(
                '<a href="{}">{}</a>',
                url,
                obj.id_cliente.nome or obj.id_cliente.waid_telefone,
            )
        except NoReverseMatch as exc:
            logger.exception(
                "admin_cliente_link_falhou | acao=retornar_texto_sem_link erro=%s",
                exc,
            )
            return obj.id_cliente.nome or obj.id_cliente.waid_telefone

    cliente_link.short_description = "Cliente"

    def _desbloquear_meta_antes_de_excluir(self, request, obj):
        try:
            desbloquear_usuario_meta(obj.wa_id_cliente, obj.phone_id_unidade)

            logger.warning(
                "admin_cliente_desbloqueado_meta | acao=desbloquear_meta_antes_excluir usuario=%s wa_id_cliente=%s phone_id_unidade=%s",
                request.user,
                short_value(obj.wa_id_cliente),
                short_value(obj.phone_id_unidade),
            )

            self.message_user(
                request,
                f"Cliente {obj.wa_id_cliente} desbloqueado na Meta. Registro removido do banco.",
                level=messages.SUCCESS,
            )
            return True

        except Exception as exc:
            logger.exception(
                "admin_desbloqueio_meta_falhou | acao=manter_registro usuario=%s wa_id_cliente=%s phone_id_unidade=%s erro=%s",
                request.user,
                short_value(obj.wa_id_cliente),
                short_value(obj.phone_id_unidade),
                exc,
            )
            self.message_user(
                request,
                f"Falha ao desbloquear na Meta. Registro mantido no banco: {exc}",
                level=messages.ERROR,
            )
            return False


@admin.register(AtendimentoCustomizado)
class AtendimentoCustomizadoAdmin(admin.ModelAdmin):
    list_display = (
        "id_customizacao",
        "id_unidade",
        "nome_agente",
        "genero",
        "bpa_ativo",
        "numero_comercial",
        "idade_minima_suporte",
        "email_obrigatorio",
        "link_agendamento",
        "link_instagram",
    )
    list_filter = ("genero", "bpa_ativo", "email_obrigatorio", "idade_minima_suporte")
    list_select_related = ("id_unidade",)
    search_fields = ("id_unidade__nome_unidade", "nome_agente")

    def get_readonly_fields(self, request, obj=None):
        return ("id_unidade",) if obj else ()

    def has_add_permission(self, request):
        return False  # A criação é feita junto da unidade, pelo inline obrigatório.

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(IntegracaoFireAds)
class IntegracaoFireAdsAdmin(admin.ModelAdmin):
    list_display = (
        "id_integracao_fireads",
        "id_unidade",
        "integracao_ativa",
        "contrato_validado",
        "ativada_em",
    )
    list_select_related = ("id_unidade",)
    search_fields = ("id_unidade__nome_unidade",)
    readonly_fields = ("ativada_em", "criado_em", "atualizado_em")

    def get_readonly_fields(self, request, obj=None):
        return self.readonly_fields + (("id_unidade",) if obj else ())

    def has_delete_permission(self, request, obj=None):
        return False  # Desativar preserva vínculos e snapshots históricos.


class FireAdsConsultaAdmin(SomenteVisualizacaoAdminMixin, admin.ModelAdmin):
    pass


@admin.register(ConsultaFireAds)
class ConsultaFireAdsAdmin(SomenteVisualizacaoAdminMixin, admin.ModelAdmin):
    list_display = ("id_consulta", "id_conversa", "chat", "id_unidade", "status",
                    "resultado", "tentativas", "solicitado_em", "consultado_em", "aplicado_em")
    list_filter = ("status", "resultado", "id_unidade")
    list_select_related = ("id_conversa", "id_unidade")
    search_fields = ("=id_consulta", "=id_conversa__id_conversa", "id_unidade__nome_unidade")

    @admin.display(description="Chat", ordering="id_conversa__id_chat")
    def chat(self, obj):
        return obj.id_conversa.id_chat_id


for modelo in (Chat, EnvioDash):
    admin.site.register(modelo, FireAdsConsultaAdmin)
````

## Passo 15: `core/database/deploy_database/fireads_script.py`

Incluir a migração nova no setup de uma instalação vazia, sem alterar o SQL histórico.

````python
"""DDL único compartilhado com a migração manual do deploy."""

import logging
from pathlib import Path

from core.database.deploy_database.transacao_deploy import transacao_deploy


def criar_estrutura_fireads():
    caminho = (
        Path(__file__).resolve().parents[3]
        / "deploy/migrations/20261007_fireads_chat_customizacao.sql"
    )
    script = caminho.read_text(encoding="utf-8")
    ddl = script.split("-- INICIO DDL FIREADS\n", 1)[1].split("-- FIM DDL FIREADS", 1)[
        0
    ]
    with transacao_deploy(
        "estrutura_fireads", logging.getLogger("db.fireads")
    ) as cursor:
        cursor.execute(ddl)
        novo = caminho.with_name("20261009_worker_consulta_dash.sql").read_text(
            encoding="utf-8"
        )
        cursor.execute(
            novo.split("-- INICIO DDL CONSULTA DASH\n", 1)[1].split(
                "-- FIM DDL CONSULTA DASH", 1
            )[0]
        )
````

## Passo 16: `tests/fixtures/fireads.py`

Aplicar os mesmos DDLs em testes PostgreSQL descartáveis.

````python
"""Migração real nas bases PostgreSQL descartáveis da suíte."""

from pathlib import Path

MIGRACAO_FIREADS = (
    Path(__file__).resolve().parents[2]
    / "deploy/migrations/20261007_fireads_chat_customizacao.sql"
)


def aplicar_fireads(cursor):
    """Usa o DDL do deploy, preservando a transação controlada pelo teste."""
    texto = MIGRACAO_FIREADS.read_text(encoding="utf-8")
    ddl = texto.split("-- INICIO DDL FIREADS\n", 1)[1].split("-- FIM DDL FIREADS", 1)[0]
    cursor.execute(ddl)

    novo = MIGRACAO_FIREADS.with_name("20261009_worker_consulta_dash.sql").read_text(
        encoding="utf-8"
    )
    cursor.execute(
        novo.split("-- INICIO DDL CONSULTA DASH\n", 1)[1].split(
            "-- FIM DDL CONSULTA DASH", 1
        )[0]
    )
````

## Passo 17: `tests/unit/test_fireads.py`

Adaptar os contratos à consulta separada e preservar os cenários de abertura e escrita.

````python
"""Contratos de importação/entrega: HTTP e Meta sempre simulados."""

from copy import deepcopy
import unittest
from unittest.mock import Mock, patch
from core.integrations.fireads.cliente import ClienteFireAds, validar_url
from core.integrations.fireads.contrato import (
    destino,
    selecionar,
    ErroFireAds,
    bloco_observacoes,
    acrescentar_observacoes,
)
from workers.worker_flow.fireads import interpretar, email_importado, preparar_abertura
from workers.worker_funil.fireads import preparar_escrita
from workers.worker_flow.response_flow.etapas import resolver_etapa7, resolver_etapa9
from workers.worker_flow.transacoes.movimento_conversa import (
    resolver_movimento_conversa,
)
from core.integrations.funil.oportunidades import montar_payload_oportunidade
from tests.helpers import FakeConn, FakeCursor

NUMERO = "5511999990002"
GOOGLE = {
    "Nome": "Ana Paula Silva",
    "Email": "ana@example.com",
    "WhatsApp": NUMERO,
    "Perfil/Faixa": "Para mim",
    "Data/Hora": "01/10/2026 12:00",
}
META = {
    "full_name": "Carlos Silva",
    "email": "carlos@example.com",
    "phone_number": NUMERO,
    "para_quem": "mim_e_outra",
    "created_time": "2026-10-01T12:00:00-05:00",
}


def estado():
    return dict(
        interpretar([GOOGLE], [], NUMERO, None),
        concluida=True,
        id_conversa=2,
        id_integracao=1,
    )


class FireAdsTests(unittest.TestCase):
    def test_admin_nao_chama_meta_com_personalizacao_invalida(self):
        from django.contrib.admin import AdminSite
        from django.test import RequestFactory
        from types import SimpleNamespace
        from webhook.admin import UnidadeAdmin
        from webhook.models import Unidade

        admin = UnidadeAdmin(Unidade, AdminSite())
        request = RequestFactory().post("/admin/")
        request.user = SimpleNamespace(has_perm=lambda *_: True)
        request._unidade_formsets = [Mock(is_valid=Mock(return_value=False))]
        form_class = admin.get_form(request, fields=["waba_id", "phone_number_id"])
        with patch.object(Unidade, "validate_unique"), patch.object(
            Unidade, "validate_constraints"
        ), patch.object(admin, "_preparar_meta_antes_de_salvar") as meta:
            form = form_class(data={"waba_id": "123", "phone_number_id": "456"})
            self.assertFalse(form.is_valid())
            self.assertIn("atendimento customizado", str(form.non_field_errors()))
            meta.assert_not_called()

    def test_abertura_personalizada_preserva_tratamentos_sem_recoletar_nome(self):
        from workers.worker_flow.fireads import classificar_tratamento_abertura
        from core.integrations.whatsapp.messages.etapa4_messages import (
            montar_abertura_fireads,
        )

        contexto = {
            "contexto_fireads": estado(),
            "nome_agente": "Dora",
            "nome_unidade": "Supera Teste",
            "genero": "feminino",
        }
        for tipo, texto, esperado in [
            ("image", "", "tipo_mensagem_nao_suportado"),
            ("text", "quanto custa?", "pergunta_financeira"),
            ("text", "Oi", None),
        ]:
            with self.subTest(tipo=tipo, texto=texto):
                contexto.update(tipo_mensagem_atual=tipo, texto_cliente_atual=texto)
                tratamento = classificar_tratamento_abertura(contexto)
                self.assertEqual(tratamento, esperado)
                mensagem = montar_abertura_fireads(
                    contexto,
                    saudacao="Boa tarde",
                    tratamento=tratamento,
                )
                self.assertIn("Ana Paula", mensagem)
                self.assertIn("profiss", mensagem.lower())
                self.assertNotIn("Como você se chama", mensagem)

    def test_abertura_importada_registra_etapa4_e_replay_nao_reenvia(self):
        from datetime import datetime, timezone
        from workers.worker_flow import valida_historico as historico
        from workers.worker_flow.response_flow import flow_sender as sender
        from contextlib import ExitStack

        agora = datetime.now(timezone.utc)
        mensagem = {
            "id_mensagem": 10,
            "id_hash": "wamid.teste",
            "conteudo_texto": "Olá",
            "tipo_mensagem": "text",
            "cliente_telefone": NUMERO,
            "id_phone_unidade": "teste",
            "unidade_telefone": "5511999990000",
            "retry_count": 1,
        }
        banco = {
            "id_cliente": 1,
            "id_unidade": 1,
            "contexto_fireads": estado(),
            "conversa": {
                "id_conversa": 2,
                "id_etapa_atual": None,
                "last_message_from": "cliente",
                "status_dependente": False,
            },
        }
        with ExitStack() as stack:
            inserir = stack.enter_context(
                patch.object(
                    historico,
                    "inserir_historico_mensagem_cliente",
                    side_effect=lambda **k: (1, agora, k["id_etapa"], True),
                )
            )
            stack.enter_context(
                patch.object(
                    historico,
                    "buscar_resposta_bot_por_mensagem_cliente",
                    return_value=None,
                )
            )
            stack.enter_context(
                patch.object(
                    historico,
                    "listar_transicoes_permitidas",
                    return_value={
                        "profissao_titular_valida": 6,
                        "profissao_dependente_valida": 5,
                    },
                )
            )
            stack.enter_context(
                patch.object(
                    historico,
                    "buscar_contexto_etapa1",
                    return_value={
                        "nome_unidade": "Teste",
                        "nome_agente": "Dora",
                        "genero": "feminino",
                    },
                )
            )
            stack.enter_context(
                patch.object(historico, "atualizar_conversa_mensagem_cliente")
            )
            cx = historico.valida_historico(mensagem, banco, FakeCursor())
        self.assertEqual(inserir.call_args.kwargs["id_etapa"], 4)
        self.assertEqual(cx["id_etapa_origem_transicao"], 4)
        with patch.object(
            sender, "enviar_abertura_fireads", return_value={"id_etapa_resultante": 4}
        ) as envio:
            self.assertEqual(sender.flow_sender(cx)["id_etapa_resultante"], 4)
            envio.assert_called_once()
        # Banco confirmou resposta + movimento; só a fila precisou de retry.
        cx.update(
            id_etapa_atual=4,
            resposta_bot_para_mensagem_atual={
                "id_mensagem": 2,
                "id_etapa": 4,
                "id_hash_msg": "wamid.bot",
            },
        )
        with patch.object(sender, "enviar_abertura_fireads") as envio:
            resposta = sender.flow_sender(cx)
            self.assertTrue(resposta["resposta_ja_existia"])
            self.assertEqual(resolver_movimento_conversa(cx, resposta), "sem_avanco")
            envio.assert_not_called()

    def test_mapeamento_sem_inferir_por_faixa_etaria(self):
        for valor in ("Para mim", "para_mim"):
            self.assertIs(destino(valor), False)
        for valor in (
            "Para meu pai/mãe",
            "Para meu avô/avó",
            "Para outra pessoa",
            "Para meu pai ou minha mãe",
            "Para meu filho ou filha",
            "Para mim e outra pessoa",
            "mim_e_outra",
            "pai_ou_mae",
            "filho_ou_filha",
        ):
            self.assertIs(destino(valor), True, valor)
        for valor in (
            "Adulto",
            "Criança",
            "Adolescente",
            "Pessoa com 60 anos ou mais",
            "",
            None,
            "teste",
        ):
            self.assertIsNone(destino(valor), valor)

    def test_importa_nome_composto_e_nao_faixa_ou_objetivo(self):
        valor = interpretar([dict(GOOGLE, Objetivo="Memória")], [], NUMERO, None)
        self.assertEqual(valor["resultado"], "importado")
        self.assertEqual(valor["dados_titular"]["nome"], "Ana Paula")
        self.assertNotIn("idade", valor["dados_titular"])
        self.assertNotIn("Objetivo", valor)

    def test_registro_antigo_unico_nao_expira(self):
        self.assertEqual(
            interpretar(
                [dict(GOOGLE, **{"Data/Hora": "01/01/2020 12:00"})], [], NUMERO, None
            )["origem"],
            "google",
        )

    def test_datas_sao_comparadas_com_offset_da_fonte(self):
        self.assertEqual(
            selecionar([GOOGLE], [META], NUMERO, "America/Sao_Paulo")[0], "meta"
        )
        with self.assertRaises(ErroFireAds):
            selecionar([GOOGLE], [META], NUMERO, None)

    def test_mais_recente_invalido_nao_resgata_antigo(self):
        decisao = interpretar(
            [GOOGLE], [dict(META, email="inválido")], NUMERO, "America/Sao_Paulo"
        )
        self.assertEqual(decisao["origem"], "organico")
        self.assertEqual(decisao["dados_titular"], {})

    def test_empate_conflitante_e_telefone_diferente(self):
        self.assertEqual(
            interpretar(
                [GOOGLE],
                [dict(META, created_time="2026-10-01T15:00:00Z")],
                NUMERO,
                "America/Sao_Paulo",
            )["resultado"],
            "ambiguidade",
        )
        self.assertEqual(
            interpretar([GOOGLE], [], "5511999990003", None)["resultado"], "ausente"
        )

    def test_email_do_cadastro_geral_nao_autoriza_salto(self):
        self.assertFalse(
            email_importado({"id_conversa": 2, "email_cliente": "ana@example.com"})
        )
        self.assertFalse(
            email_importado({"id_conversa": 3, "contexto_fireads": estado()})
        )
        self.assertTrue(
            email_importado({"id_conversa": 2, "contexto_fireads": estado()})
        )

    def test_inicializacao_4_exige_importacao_completa(self):
        cx = {"id_conversa": 2, "id_etapa_atual": None, "contexto_fireads": estado()}
        self.assertEqual(
            resolver_movimento_conversa(cx, {"id_etapa_resultante": 4}), "inicializacao"
        )
        with self.assertRaises(ValueError):
            resolver_movimento_conversa(
                dict(cx, contexto_fireads=None), {"id_etapa_resultante": 4}
            )

    def test_aceite_da_oferta_e_retorno_pulam_email_somente_quando_importado(self):
        for etapa, mod, evento in [
            (7, resolver_etapa7, "oferta_aceita"),
            (9, resolver_etapa9, "retorno_confirmado"),
        ]:
            cx = {
                "id_conversa": 2,
                "id_etapa_atual": etapa,
                "id_etapa_origem_transicao": etapa,
                "id_etapa_cliente": etapa,
                "contexto_fireads": estado(),
                "tipo_mensagem_atual": "text",
                "texto_cliente_atual": "sim",
                "transicoes_permitidas": {evento: 10, evento + "_email_fireads": 11},
                "mensagem_cliente_atual": {
                    "cliente_telefone": NUMERO,
                    "id_phone_unidade": "teste",
                    "id_mensagem_fila": 1,
                },
            }
            with patch.object(
                mod, "enviar_etapa11", return_value={"id_etapa_resultante": 11}
            ) as triagem, patch.object(
                mod, "enviar_etapa10", return_value={"id_etapa_resultante": 10}
            ) as email:
                resultado = getattr(mod, f"resolve_etapa{etapa}")(cx)
                self.assertEqual(
                    resultado["evento_transicao"], evento + "_email_fireads"
                )
                triagem.assert_called_once()
                email.assert_not_called()
                resultado = getattr(mod, f"resolve_etapa{etapa}")(
                    dict(cx, contexto_fireads=None)
                )
                self.assertEqual(resultado["id_etapa_resultante"], 10)

    def test_preserva_observacoes_inclusive_zero_e_retry(self):
        bloco = bloco_observacoes(1, 2, "Texto do Funil")
        for anterior in ("FR002", "  notas comerciais\n", 0, "0", "", None):
            novo, mudou = acrescentar_observacoes(anterior, bloco)
            self.assertTrue(mudou)
            if anterior is not None:
                self.assertTrue(novo.startswith(str(anterior)))
            self.assertEqual(acrescentar_observacoes(novo, bloco), (novo, False))
        with self.assertRaises(ErroFireAds):
            acrescentar_observacoes(bloco.replace("Texto do Funil", "Editado"), bloco)
        with self.assertRaises(ErroFireAds):
            acrescentar_observacoes("x" * 45000, bloco)

    def test_organico_existente_atualiza_so_observacao(self):
        snap = {
            "telefone": NUMERO,
            "nome": "Ana",
            "email": "ana@example.com",
            "perfil": "Titular",
            "origem": "organico",
        }
        linha = {
            "_row": 2,
            "WhatsApp": NUMERO,
            "Email": "ana@example.com",
            "Observação": "FR002",
        }
        bloco = bloco_observacoes(1, 2, "novo")
        op = preparar_escrita([linha], snap, bloco)
        self.assertEqual(set(op), {"row", "observacoes"})
        self.assertEqual(op["observacoes"], "FR002\n\n" + bloco)
        self.assertIsNone(
            preparar_escrita(
                [dict(linha, **{"Observação": op["observacoes"]})], snap, bloco
            )
        )

    def test_organico_novo_nao_envia_data_e_identidade_ambigua_nao_escreve(self):
        snap = {
            "telefone": NUMERO,
            "nome": "Ana",
            "email": "ana@example.com",
            "perfil": "Titular",
            "origem": "organico",
        }
        bloco = bloco_observacoes(1, 2, "novo")
        self.assertNotIn("Data/Hora", preparar_escrita([], snap, bloco)["dados"])
        for linhas in (
            [{"_row": 2, "WhatsApp": NUMERO, "Email": "outra@example.com"}],
            [{"_row": 2, "WhatsApp": NUMERO}, {"_row": 3, "WhatsApp": NUMERO}],
            [{"_row": 2, "WhatsApp": "5511999990003", "Email": snap["email"]}],
        ):
            with self.assertRaises(ErroFireAds):
                preparar_escrita(linhas, snap, bloco)

    def test_exec_e_redirect_sem_repetir_post(self):
        session = Mock()
        redirect = Mock(
            status_code=302,
            headers={
                "Location": "https://script.googleusercontent.com/macros/echo?x=1"
            },
        )
        resposta = Mock(status_code=200)
        resposta.json.return_value = {"success": True, "aba": "geral", "inserted": 1}
        session.request.side_effect = [redirect, resposta]
        cli = ClienteFireAds(
            "https://script.google.com/macros/s/teste/exec", session=session
        )
        cli.enviar("geral", dados={"Nome": "Teste"})
        self.assertEqual(
            [c.args[0] for c in session.request.call_args_list], ["POST", "GET"]
        )
        with self.assertRaises(ErroFireAds):
            validar_url("https://script.google.com/u/0/home/projects/teste/edit")
        session.request.side_effect = None
        resposta.json.return_value = {"success": False, "error": "recusado"}
        session.request.return_value = resposta
        with self.assertRaises(ErroFireAds):
            cli.enviar("geral", dados={"Nome": "Teste"})

    def test_retry_recupera_decisao_sem_consultar_api(self):
        cx = {"conversa": {"id_conversa": 2, "id_etapa_atual": None}}
        with patch(
            "workers.worker_flow.fireads.buscar_abertura",
            return_value={"contexto": estado()},
        ), patch("workers.worker_consulta_dash.consulta.ClienteFireAds") as api:
            retomado = preparar_abertura(cx, {}, 1, FakeCursor())
            self.assertEqual(retomado["contexto_fireads"]["origem"], "google")
            api.assert_not_called()

    def test_segunda_fonte_falha_importa_nada(self):
        from workers.worker_consulta_dash.consulta import consultar

        api = Mock()
        api.consultar.side_effect = [
            {"headers": list(GOOGLE), "rows": [GOOGLE]},
            RuntimeError("falha"),
        ]
        with patch(
            "workers.worker_consulta_dash.consulta.ClienteFireAds", return_value=api
        ):
            resultado = consultar(
                {
                    "id_consulta": 1,
                    "restante": 300,
                    "entrada": {
                        "url": "https://script.google.com/macros/s/teste/exec",
                        "aba_google": "google",
                        "aba_meta": "meta",
                        "numero": NUMERO,
                        "fuso": None,
                    },
                }
            )
        self.assertEqual(resultado["decisao"]["origem"], "organico")
        self.assertEqual(resultado["fontes"], {})
````

## Passo 18: `tests/unit/test_fireads_espera.py`

Validar o prazo HTTP e a interpretação sem depender da antiga execução em thread.

````python
"""Latência simulada sem HTTP real: espera, retomada e limites de concorrência."""

import unittest
from unittest.mock import Mock, patch

from core.integrations.fireads.cliente import ClienteFireAds
from core.integrations.fireads.contrato import ErroFireAds
from tests.helpers import FakeConn, FakeCursor
from tests.unit.test_fireads import GOOGLE, NUMERO
from workers.worker_flow import fireads
from workers.worker_flow.suporte.consultas_fireads import (
    ConsultaFireAdsPendente,
)


class ConsultaHTTPTests(unittest.TestCase):
    def test_300_segundos_sao_compartilhados_entre_abas_e_redirects(self):
        session = Mock()
        resposta = Mock(status_code=200)
        resposta.json.side_effect = [
            {"success": True, "data": {"aba": aba, "headers": [], "rows": []}}
            for aba in ("google", "meta")
        ]
        redirect = Mock(
            status_code=302,
            headers={
                "Location": "https://script.googleusercontent.com/macros/echo?teste=1",
            },
        )
        with patch(
            "core.integrations.fireads.cliente.time.monotonic", return_value=0
        ) as tempo:
            cliente = ClienteFireAds(
                "https://script.google.com/macros/s/teste/exec",
                segundos=300,
                timeout_leitura=None,
                session=session,
            )

            def responder(*_args, **_kwargs):
                if session.request.call_count == 1:
                    tempo.return_value = 65
                    return redirect
                if session.request.call_count == 2:
                    tempo.return_value = 100
                else:
                    tempo.return_value = 299
                return resposta

            session.request.side_effect = responder
            cliente.consultar("google")
            cliente.consultar("meta")
            self.assertEqual(
                [c.kwargs["timeout"][1] for c in session.request.call_args_list],
                [300, 235, 200],
            )
            tempo.return_value = 300
            with self.assertRaises(ErroFireAds):
                cliente.consultar("meta")
            self.assertEqual(session.request.call_count, 3)

    def test_resposta_tardia_nao_e_aceita_mesmo_que_http_seja_200(self):
        session = Mock()
        with patch(
            "core.integrations.fireads.cliente.time.monotonic", return_value=0
        ) as tempo:
            cliente = ClienteFireAds(
                "https://script.google.com/macros/s/teste/exec",
                segundos=300,
                timeout_leitura=None,
                session=session,
            )

            def atrasar(*_args, **_kwargs):
                tempo.return_value = 301
                return Mock(status_code=200)

            session.request.side_effect = atrasar
            with self.assertRaises(ErroFireAds):
                cliente.consultar("google")

    def test_consulta_sem_prazo_aceita_duas_abas_e_redirect_apos_120_segundos(self):
        session = Mock()
        resposta = Mock(status_code=200)
        resposta.json.side_effect = [
            {"success": True, "data": {"aba": aba, "headers": [], "rows": []}}
            for aba in ("google", "meta")
        ]
        redirect = Mock(
            status_code=302,
            headers={
                "Location": "https://script.googleusercontent.com/macros/echo?teste=1",
            },
        )
        session.request.side_effect = [redirect, resposta, redirect, resposta]
        with patch("core.integrations.fireads.cliente.time.monotonic") as relogio:
            relogio.return_value = 0
            cliente = ClienteFireAds(
                "https://script.google.com/macros/s/teste/exec",
                segundos=None,
                session=session,
            )
            relogio.return_value = 300
            cliente.consultar("google")
            relogio.return_value = 600
            cliente.consultar("meta")
        self.assertEqual(session.request.call_count, 4)
        for chamada in session.request.call_args_list:
            self.assertIsNone(chamada.kwargs["timeout"])
            self.assertEqual(chamada.args[0], "GET")

    def test_orcamento_finito_das_escritas_permanece(self):
        session = Mock()
        with patch(
            "core.integrations.fireads.cliente.time.monotonic", return_value=0
        ) as tempo:
            cliente = ClienteFireAds(
                "https://script.google.com/macros/s/teste/exec",
                segundos=40,
                session=session,
            )
            tempo.return_value = 41
            with self.assertRaises(ErroFireAds):
                cliente.enviar("geral", dados={})
        session.request.assert_not_called()


class DecisaoConsultaTests(unittest.TestCase):
    def test_formularios_repetidos_iguais_nao_impedem_importacao_sem_fuso(self):
        for origem, rows in (
            ("google", [dict(GOOGLE, _row=44), dict(GOOGLE, _row=45)]),
            (
                "meta",
                [
                    {
                        "full_name": "Ana Paula Silva",
                        "email": "ana@example.com",
                        "para_quem": "para_mim",
                        "phone_number": NUMERO,
                        "created_time": "2026-10-09T00:00:00Z",
                        "id": id_,
                    }
                    for id_ in (1, 2)
                ],
            ),
        ):
            with self.subTest(origem=origem):
                google, meta = (rows, []) if origem == "google" else ([], rows)
                resultado = fireads.interpretar(google, meta, NUMERO, None)
                self.assertEqual(resultado["resultado"], "importado")
                self.assertEqual(resultado["origem"], origem)

    def test_registros_com_dados_ou_datas_diferentes_continuam_exigindo_desempate(self):
        for diferenca in (
            {"Nome": "Maria Silva"},
            {"Email": "outro@example.com"},
            {"Perfil/Faixa": "Para meu pai/mãe"},
            {"Data/Hora": "02/10/2026 12:00"},
        ):
            with self.subTest(diferenca=diferenca):
                resultado = fireads.interpretar(
                    [GOOGLE, dict(GOOGLE, **diferenca)], [], NUMERO, None
                )
                self.assertEqual(resultado["resultado"], "ambiguidade")
````

## Passo 19: `tests/unit/test_worker_flow_runtime.py`

Preservar a prova de liberação do ciclo para outros clientes e de ordenação/recuperação.

````python
import unittest
from contextlib import ExitStack
from datetime import datetime
from unittest.mock import patch

from tests.helpers import FakeConn, FakeCursor
from workers.worker_flow.response_flow import flow_worker
from workers.worker_flow.suporte import estado_ciclo


class PararWorker(BaseException):
    pass


def registro_fila():
    return (
        7,
        "5571999999999",
        "Ola",
        "text",
        "123456",
        "5571000000000",
        datetime(2026, 6, 18, 10, 0),
        "wamid.cliente.7",
        1,
    )


def contexto_banco():
    return {
        "id_unidade": 2,
        "id_cliente": 6,
        "cliente_telefone": "5571999999999",
        "id_phone_unidade": "123456",
        "cliente_inserido": False,
        "cliente_cache_pendente": False,
        "conversa": {
            "id_conversa": 10,
            "estado": "ativa",
        },
    }


def contexto_historico():
    return {
        "id_conversa": 10,
        "id_etapa_atual": None,
        "id_etapa_cliente": 1,
        "id_etapa_resposta": 1,
        "mensagem_cliente_inserida": True,
        "mensagem_cliente_atual": {
            "id_mensagem_fila": 7,
            "id_hash_msg": "wamid.cliente.7",
            "cliente_telefone": "5571999999999",
            "id_phone_unidade": "123456",
        },
        "resposta_bot_para_mensagem_atual": None,
        "retry_count": 1,
    }


def contexto_envio():
    return {
        "enviou": True,
        "resposta_ja_existia": False,
        "id_hash_msg_bot": "wamid.bot.7",
        "id_etapa_resultante": 1,
        "tipo_mensagem": "text",
    }


def contexto_final():
    return {
        "id_etapa_resultante": 1,
        "resposta_ja_existia": False,
        "id_hash_msg_bot": "wamid.bot.7",
    }


class WorkerFlowRuntimeTests(unittest.TestCase):

    def test_fireads_pendente_libera_ciclo_para_outro_cliente_sem_consumir_retry(self):
        conn = FakeConn(FakeCursor())
        outra_conn = FakeConn(FakeCursor())
        outro_registro = list(registro_fila())
        outro_registro[0] = 8
        outro_registro[1] = "5511999990000"
        outro_registro[4] = "outra-unidade"
        outro_contexto = dict(contexto_banco(), id_unidade=3, conversa={"id_conversa": 11, "estado": "nova"})
        with ExitStack() as stack:
            self._patch_fluxo_base(stack, conn, [])
            stack.enter_context(patch.object(flow_worker, "get_conn", side_effect=[conn, outra_conn, PararWorker()]))
            stack.enter_context(patch.object(flow_worker, "pegar_mensagens_da_fila", side_effect=[registro_fila(), outro_registro]))
            stack.enter_context(patch.object(flow_worker, "validar_banco_mensagem", side_effect=[contexto_banco(), outro_contexto]))
            stack.enter_context(patch.object(flow_worker, "preparar_abertura", side_effect=[flow_worker.ConsultaFireAdsPendente("consultando"), outro_contexto]))
            stack.enter_context(patch.object(flow_worker, "atualizar_banco_com_contexto_final", return_value=contexto_final()))
            finalizar = stack.enter_context(patch.object(flow_worker, "finalizar_mensagem_processada", return_value={"atendimento_encerrado": False}))
            historico = stack.enter_context(patch.object(flow_worker, "valida_historico", return_value=contexto_historico()))
            enviar = stack.enter_context(patch.object(flow_worker, "flow_sender", return_value=contexto_envio()))
            reagendar = stack.enter_context(patch.object(flow_worker, "reagendar_mensagem_sem_erro"))
            erro = stack.enter_context(patch.object(flow_worker, "handle_erro_generico"))
            liberar = stack.enter_context(patch.object(flow_worker, "liberar_lock_conversa_se_necessario", return_value=True))
            with self.assertRaises(PararWorker):
                flow_worker.worker_flow()
        reagendar.assert_called_once_with(7, conn.cursor_obj, delay_seconds=5, retry_esperado=1)
        historico.assert_called_once()
        self.assertEqual(historico.call_args.args[0]["id_mensagem"], 8)
        enviar.assert_called_once()
        finalizar.assert_called_once()
        erro.assert_not_called()
        self.assertEqual(liberar.call_count, 2)
        self.assertTrue(conn.closed and outra_conn.closed)

    def test_desativacao_preserva_fila_sem_enviar_ou_consumir_retry(self):
        # A unidade pode ser desativada após o dequeue, durante a consulta ou
        # depois de montar o histórico. Em nenhum caso inicia um envio Meta.
        for momento in (0, 1, 2):
            with self.subTest(momento=momento), ExitStack() as stack:
                conn = FakeConn(FakeCursor())
                self._patch_fluxo_base(stack, conn, [])
                stack.enter_context(patch.object(
                    flow_worker, "exigir_unidade_habilitada_por_phone_id",
                    side_effect=[None] * momento + [flow_worker.UnidadeDesativada()],
                ))
                enviar = stack.enter_context(patch.object(flow_worker, "flow_sender"))
                reagendar = stack.enter_context(patch.object(flow_worker, "reagendar_mensagem_sem_erro"))
                erro = stack.enter_context(patch.object(flow_worker, "handle_erro_generico"))
                with self.assertRaises(PararWorker):
                    flow_worker.worker_flow()
                enviar.assert_not_called()
                erro.assert_not_called()
                reagendar.assert_called_once_with(
                    7, conn.cursor_obj, delay_seconds=300, retry_esperado=1,
                )

    def test_followup_confirma_efeitos_encerramento_e_fila_no_mesmo_commit(self):
        conn = FakeConn(FakeCursor())
        commits = []
        with ExitStack() as stack:
            self._patch_fluxo_base(stack, conn, [])
            stack.enter_context(
                patch.object(
                    flow_worker,
                    "preparar_retorno_followup",
                    return_value=dict(contexto_historico(), retorno_followup=True),
                )
            )
            stack.enter_context(
                patch.object(
                    flow_worker,
                    "enviar_retorno_followup",
                    return_value=contexto_envio(),
                )
            )
            stack.enter_context(
                patch.object(
                    flow_worker,
                    "persistir_retorno_followup",
                    side_effect=lambda *_: commits.append(("efeitos", conn.commits))
                    or contexto_final(),
                )
            )
            stack.enter_context(
                patch.object(
                    flow_worker,
                    "finalizar_mensagem_processada",
                    side_effect=lambda *_: commits.append(
                        ("encerramento_e_fila", conn.commits)
                    )
                    or {"atendimento_encerrado": True},
                )
            )
            stack.enter_context(
                patch.object(
                    flow_worker,
                    "registrar_cache_bloqueio_apos_commit",
                    side_effect=lambda *_: commits.append(("cache", conn.commits)),
                )
            )
            with self.assertRaises(PararWorker):
                flow_worker.worker_flow()
        self.assertEqual(
            commits, [("efeitos", 5), ("encerramento_e_fila", 5), ("cache", 6)]
        )
        self.assertEqual(conn.rollbacks, 0)

    def test_falha_finalizacao_followup_reverte_resposta_efeitos_e_checkpoint(self):
        conn = FakeConn(FakeCursor())
        commits = []
        with ExitStack() as stack:
            self._patch_fluxo_base(stack, conn, [])
            stack.enter_context(
                patch.object(
                    flow_worker,
                    "preparar_retorno_followup",
                    return_value=dict(contexto_historico(), retorno_followup=True),
                )
            )
            stack.enter_context(
                patch.object(
                    flow_worker,
                    "enviar_retorno_followup",
                    return_value=contexto_envio(),
                )
            )
            stack.enter_context(
                patch.object(
                    flow_worker,
                    "persistir_retorno_followup",
                    side_effect=lambda *_: commits.append(conn.commits)
                    or contexto_final(),
                )
            )
            stack.enter_context(
                patch.object(
                    flow_worker,
                    "finalizar_mensagem_processada",
                    side_effect=RuntimeError("falha ao finalizar"),
                )
            )
            erro = stack.enter_context(
                patch.object(
                    flow_worker,
                    "handle_erro_generico",
                    side_effect=lambda *_: commits.append(conn.commits),
                )
            )
            cache = stack.enter_context(
                patch.object(flow_worker, "registrar_cache_bloqueio_apos_commit")
            )
            with self.assertRaises(PararWorker):
                flow_worker.worker_flow()
        self.assertEqual(commits, [5, 5])
        self.assertEqual(conn.rollbacks, 1)
        self.assertIsInstance(
            erro.call_args.args[2], flow_worker.BancoFalhouAposEnvioMeta
        )
        cache.assert_not_called()

    def test_reacao_followup_usa_orquestrador_e_checkpoint_proprios(self):
        conn = FakeConn(FakeCursor())
        eventos = []
        with ExitStack() as stack:
            self._patch_fluxo_base(stack, conn, eventos)
            cx = dict(contexto_historico(), retorno_followup=True)
            stack.enter_context(
                patch.object(flow_worker, "preparar_retorno_followup", return_value=cx)
            )
            normal_historico = stack.enter_context(
                patch.object(flow_worker, "valida_historico")
            )
            normal_sender = stack.enter_context(
                patch.object(flow_worker, "flow_sender")
            )
            normal_persistencia = stack.enter_context(
                patch.object(flow_worker, "atualizar_banco_com_contexto_final")
            )
            repetir = stack.enter_context(
                patch.object(
                    flow_worker,
                    "enviar_retorno_followup",
                    return_value=contexto_envio(),
                )
            )
            persistir = stack.enter_context(
                patch.object(
                    flow_worker,
                    "persistir_retorno_followup",
                    return_value=contexto_final(),
                )
            )
            finalizar = stack.enter_context(
                patch.object(
                    flow_worker,
                    "finalizar_mensagem_processada",
                    return_value={"atendimento_encerrado": False},
                )
            )
            with self.assertRaises(PararWorker):
                flow_worker.worker_flow()
        normal_historico.assert_not_called()
        normal_sender.assert_not_called()
        normal_persistencia.assert_not_called()
        repetir.assert_called_once()
        persistir.assert_called_once()
        finalizar.assert_called_once()

    def test_lock_perdido_nao_envia_nem_reescreve_fila(self):
        conn = FakeConn(FakeCursor())
        eventos = []
        with ExitStack() as stack:
            self._patch_fluxo_base(stack, conn, eventos)
            stack.enter_context(
                patch.object(
                    flow_worker,
                    "proteger_conversa",
                    side_effect=flow_worker.LockConversaPerdido,
                )
            )
            enviar = stack.enter_context(patch.object(flow_worker, "flow_sender"))
            reagendar = stack.enter_context(
                patch.object(flow_worker, "reagendar_mensagem_sem_erro")
            )
            finalizar = stack.enter_context(
                patch.object(flow_worker, "finalizar_mensagem_processada")
            )
            with self.assertRaises(PararWorker):
                flow_worker.worker_flow()
        enviar.assert_not_called()
        reagendar.assert_not_called()
        finalizar.assert_not_called()
        self.assertEqual(conn.rollbacks, 1)

    def test_fila_vazia_aguarda_um_segundo_e_meio(self):
        with (
            patch.object(estado_ciclo.time, "sleep") as sleep,
            patch.object(estado_ciclo.logger, "debug") as log_debug,
        ):
            estado_ciclo.aguardar_fila_vazia()

        sleep.assert_called_once_with(1.5)
        log_debug.assert_called_once_with("fila_vazia | acao=aguardar segundos=1.5")

    def test_erro_operacional_psycopg3_reinicia_conexao(self):
        erro = flow_worker.psycopg.OperationalError("conexao indisponivel")

        with ExitStack() as stack:
            stack.enter_context(patch("builtins.print"))
            stack.enter_context(
                patch.object(
                    flow_worker,
                    "get_conn",
                    side_effect=[erro, PararWorker()],
                )
            )
            tratar_conexao = stack.enter_context(
                patch.object(
                    flow_worker,
                    "handle_erro_conexao",
                    return_value=10,
                )
            )

            with self.assertRaises(PararWorker):
                flow_worker.worker_flow()

        tratar_conexao.assert_called_once_with(erro, 5)

    def test_fila_vazia_fecha_conexao_antes_de_aguardar(self):
        conn = FakeConn(FakeCursor())

        with ExitStack() as stack:
            stack.enter_context(patch("builtins.print"))
            stack.enter_context(
                patch.object(
                    flow_worker,
                    "get_conn",
                    side_effect=[conn, PararWorker()],
                )
            )
            stack.enter_context(
                patch.object(
                    flow_worker,
                    "pegar_mensagens_da_fila",
                    return_value=None,
                )
            )
            close = stack.enter_context(
                patch.object(
                    conn,
                    "close",
                    wraps=conn.close,
                )
            )

            def verificar_conexao_fechada():
                self.assertTrue(conn.closed)

            stack.enter_context(
                patch.object(
                    flow_worker,
                    "aguardar_fila_vazia",
                    side_effect=verificar_conexao_fechada,
                )
            )

            with self.assertRaises(PararWorker):
                flow_worker.worker_flow()

        close.assert_called_once_with()
        self.assertEqual(conn.commits, 1)
        self.assertEqual(conn.rollbacks, 0)

    def _patch_fluxo_base(self, stack, conn, eventos):
        stack.enter_context(patch.object(flow_worker, "preparar_abertura", side_effect=lambda contexto, *_: contexto))
        stack.enter_context(
            patch.object(
                flow_worker, "reler_conversa", side_effect=lambda contexto, *_: contexto
            )
        )
        stack.enter_context(patch.object(flow_worker, "proteger_conversa"))
        stack.enter_context(
            patch.object(flow_worker, "preparar_retorno_followup", return_value=None)
        )
        stack.enter_context(patch("builtins.print"))
        stack.enter_context(
            patch.object(
                flow_worker,
                "get_conn",
                side_effect=[conn, PararWorker()],
            )
        )
        stack.enter_context(
            patch.object(
                flow_worker,
                "pegar_mensagens_da_fila",
                return_value=registro_fila(),
            )
        )
        stack.enter_context(
            patch.object(
                flow_worker,
                "validar_banco_mensagem",
                side_effect=lambda *_args: eventos.append("validar_banco")
                or contexto_banco(),
            )
        )
        stack.enter_context(
            patch.object(
                flow_worker,
                "vincular_mensagem_fila_a_conversa",
                side_effect=lambda *_args: eventos.append("vincular_conversa") or 1,
            )
        )
        stack.enter_context(
            patch.object(
                flow_worker,
                "confirmar_cache_cliente_se_pendente",
                return_value=False,
            )
        )
        stack.enter_context(
            patch.object(
                flow_worker,
                "tentar_lock_conversa",
                side_effect=lambda *_args: eventos.append("adquirir_lock") or (True, 4),
            )
        )
        stack.enter_context(
            patch.object(
                flow_worker,
                "reagendar_se_houver_mensagem_anterior",
                side_effect=lambda *_args: eventos.append("verificar_ordem") or False,
            )
        )
        stack.enter_context(
            patch.object(
                flow_worker,
                "valida_historico",
                side_effect=lambda *_args: eventos.append("persistir_cliente")
                or contexto_historico(),
            )
        )
        stack.enter_context(
            patch.object(
                flow_worker,
                "flow_sender",
                side_effect=lambda *_args: eventos.append("enviar_meta")
                or contexto_envio(),
            )
        )
        stack.enter_context(
            patch.object(
                flow_worker,
                "liberar_lock_conversa_se_necessario",
                side_effect=lambda *_args: eventos.append("liberar_lock") or True,
            )
        )
        stack.enter_context(
            patch.object(
                flow_worker,
                "handle_erro_generico",
            )
        )

    def test_mensagem_anterior_reagenda_antes_de_validar_banco(self):
        conn = FakeConn(FakeCursor())

        with ExitStack() as stack:
            stack.enter_context(patch("builtins.print"))
            stack.enter_context(
                patch.object(
                    flow_worker,
                    "get_conn",
                    side_effect=[conn, PararWorker()],
                )
            )
            stack.enter_context(
                patch.object(
                    flow_worker,
                    "pegar_mensagens_da_fila",
                    return_value=registro_fila(),
                )
            )
            barreira = stack.enter_context(
                patch.object(
                    flow_worker,
                    "reagendar_se_houver_mensagem_anterior",
                    return_value=True,
                )
            )
            validar = stack.enter_context(
                patch.object(
                    flow_worker,
                    "validar_banco_mensagem",
                )
            )
            lock = stack.enter_context(
                patch.object(
                    flow_worker,
                    "tentar_lock_conversa",
                )
            )
            vincular = stack.enter_context(
                patch.object(
                    flow_worker,
                    "vincular_mensagem_fila_a_conversa",
                )
            )

            with self.assertRaises(PararWorker):
                flow_worker.worker_flow()

        barreira.assert_called_once()
        validar.assert_not_called()
        lock.assert_not_called()
        vincular.assert_not_called()
        self.assertEqual(conn.commits, 2)
        self.assertEqual(conn.rollbacks, 0)
        self.assertTrue(conn.closed)

    def test_ciclo_normal_persiste_resposta_antes_de_marcar_sent(self):
        conn = FakeConn(FakeCursor())
        eventos = []

        with ExitStack() as stack:
            self._patch_fluxo_base(stack, conn, eventos)
            stack.enter_context(
                patch.object(
                    flow_worker,
                    "atualizar_banco_com_contexto_final",
                    side_effect=lambda *_args: eventos.append("persistir_bot")
                    or contexto_final(),
                )
            )
            finalizar = stack.enter_context(
                patch.object(
                    flow_worker,
                    "finalizar_mensagem_processada",
                    side_effect=lambda *_args: (
                        eventos.append("marcar_sent")
                        or {"atendimento_encerrado": False}
                    ),
                )
            )

            with self.assertRaises(PararWorker):
                flow_worker.worker_flow()

        self.assertEqual(
            eventos,
            [
                "verificar_ordem",
                "validar_banco",
                "adquirir_lock",
                "vincular_conversa",
                "persistir_cliente",
                "enviar_meta",
                "persistir_bot",
                "marcar_sent",
                "liberar_lock",
            ],
        )
        finalizar.assert_called_once()
        self.assertEqual(conn.commits, 8)
        self.assertEqual(conn.rollbacks, 0)
        self.assertTrue(conn.closed)

    def test_checkpoint_cache_e_atomicidade_vinculo_historico(self):
        conn = FakeConn(FakeCursor())
        eventos = []
        commits_observados = {}

        def confirmar_cache(*_args):
            commits_observados["cache"] = conn.commits
            return False

        def vincular_conversa(*_args):
            commits_observados["vinculo"] = conn.commits
            return 1

        def persistir_historico(*_args):
            commits_observados["historico"] = conn.commits
            return contexto_historico()

        with ExitStack() as stack:
            self._patch_fluxo_base(stack, conn, eventos)
            stack.enter_context(
                patch.object(
                    flow_worker,
                    "confirmar_cache_cliente_se_pendente",
                    side_effect=confirmar_cache,
                )
            )
            stack.enter_context(
                patch.object(
                    flow_worker,
                    "vincular_mensagem_fila_a_conversa",
                    side_effect=vincular_conversa,
                )
            )
            stack.enter_context(
                patch.object(
                    flow_worker,
                    "valida_historico",
                    side_effect=persistir_historico,
                )
            )
            stack.enter_context(
                patch.object(
                    flow_worker,
                    "atualizar_banco_com_contexto_final",
                    return_value=contexto_final(),
                )
            )
            stack.enter_context(
                patch.object(
                    flow_worker,
                    "finalizar_mensagem_processada",
                    return_value={"atendimento_encerrado": False},
                )
            )

            with self.assertRaises(PararWorker):
                flow_worker.worker_flow()

        self.assertEqual(commits_observados["cache"], 2)
        self.assertEqual(commits_observados["vinculo"], 3)
        self.assertEqual(commits_observados["historico"], 3)

    def test_lock_recusado_reagenda_sem_consumir_retry(self):
        conn = FakeConn(FakeCursor())
        eventos = []

        with ExitStack() as stack:
            self._patch_fluxo_base(stack, conn, eventos)
            stack.enter_context(
                patch.object(
                    flow_worker,
                    "tentar_lock_conversa",
                    return_value=(False, None),
                )
            )
            reagendar = stack.enter_context(
                patch.object(
                    flow_worker,
                    "reagendar_mensagem_sem_erro",
                    return_value=1,
                )
            )
            vincular = stack.enter_context(
                patch.object(
                    flow_worker,
                    "vincular_mensagem_fila_a_conversa",
                )
            )
            historico = stack.enter_context(
                patch.object(
                    flow_worker,
                    "valida_historico",
                )
            )
            enviar = stack.enter_context(
                patch.object(
                    flow_worker,
                    "flow_sender",
                )
            )
            stack.enter_context(
                patch.object(
                    flow_worker,
                    "liberar_lock_conversa_se_necessario",
                    return_value=None,
                )
            )

            with self.assertRaises(PararWorker):
                flow_worker.worker_flow()

        reagendar.assert_called_once_with(
            7,
            conn.cursor_obj,
            delay_seconds=5,
        )
        vincular.assert_not_called()
        historico.assert_not_called()
        enviar.assert_not_called()
        self.assertEqual(conn.commits, 4)
        self.assertEqual(conn.rollbacks, 0)
        self.assertTrue(conn.closed)

    def test_vinculo_inconsistente_reagenda_sem_enviar(self):
        conn = FakeConn(FakeCursor())
        eventos = []

        with ExitStack() as stack:
            self._patch_fluxo_base(stack, conn, eventos)
            stack.enter_context(
                patch.object(
                    flow_worker,
                    "vincular_mensagem_fila_a_conversa",
                    return_value=0,
                )
            )
            tratar_erro = stack.enter_context(
                patch.object(
                    flow_worker,
                    "handle_erro_generico",
                )
            )
            reagendar = stack.enter_context(
                patch.object(
                    flow_worker,
                    "reagendar_mensagem_sem_erro",
                    return_value=1,
                )
            )
            aviso = stack.enter_context(
                patch.object(
                    flow_worker.logger,
                    "critical",
                )
            )
            persistir_bot = stack.enter_context(
                patch.object(
                    flow_worker,
                    "atualizar_banco_com_contexto_final",
                )
            )
            finalizar = stack.enter_context(
                patch.object(
                    flow_worker,
                    "finalizar_mensagem_processada",
                )
            )

            with self.assertRaises(PararWorker):
                flow_worker.worker_flow()

        tratar_erro.assert_not_called()
        persistir_bot.assert_not_called()
        finalizar.assert_not_called()
        reagendar.assert_called_once_with(7, conn.cursor_obj, delay_seconds=300)
        self.assertEqual(
            eventos,
            [
                "verificar_ordem",
                "validar_banco",
                "adquirir_lock",
                "liberar_lock",
            ],
        )
        aviso.assert_called_once()
        self.assertIn(
            "motivo=historico_conflitante_ou_fila_ausente",
            aviso.call_args.args[0],
        )
        self.assertEqual(conn.rollbacks, 0)
        self.assertTrue(conn.closed)

    def test_falha_do_banco_apos_meta_reagenda_sem_marcar_sent(self):
        conn = FakeConn(FakeCursor())
        eventos = []

        with ExitStack() as stack:
            self._patch_fluxo_base(stack, conn, eventos)
            stack.enter_context(
                patch.object(
                    flow_worker,
                    "atualizar_banco_com_contexto_final",
                    side_effect=RuntimeError("banco caiu apos envio"),
                )
            )
            finalizar = stack.enter_context(
                patch.object(
                    flow_worker,
                    "finalizar_mensagem_processada",
                    side_effect=lambda *_args: (
                        eventos.append("marcar_sent")
                        or {"atendimento_encerrado": False}
                    ),
                )
            )
            tratar_erro = stack.enter_context(
                patch.object(
                    flow_worker,
                    "handle_erro_generico",
                )
            )

            with self.assertRaises(PararWorker):
                flow_worker.worker_flow()

        finalizar.assert_not_called()
        tratar_erro.assert_called_once()
        self.assertNotIn("marcar_sent", eventos)
        self.assertEqual(conn.rollbacks, 1)
        self.assertEqual(conn.commits, 7)
        self.assertTrue(conn.closed)


if __name__ == "__main__":
    unittest.main()
````

## Passo 20: `tests/integration/test_fireads_postgres.py`

Testar SQL real, disputa, quedas, prazo, histórico, aplicação e etapas sem reconsulta.

````python
"""FireAds em PostgreSQL local descartável; apenas HTTP é substituído."""

from contextlib import contextmanager, ExitStack
from datetime import timedelta
import os
from threading import Event
import unittest
from unittest.mock import Mock, patch

import psycopg
from psycopg.conninfo import conninfo_to_dict

from core.database.deploy_database import (
    bank_script,
    povoar_etapas,
    etapa_transicao_script,
)
from core.repositories.atendimento.conversas import (
    inserindo_em_conversa_caso_seja_nova,
    tentar_lock_conversa,
)
from core.repositories.atendimento.followup import LockConversaPerdido
from core.repositories.fireads import consulta, envios, pendencias
from workers.worker_consulta_dash.consulta_worker import executar_ciclo
from core.repositories.funil.leads import buscar_dados_lead_funil
from core.integrations.funil.oportunidades import montar_payload_oportunidade
from core.integrations.fireads.contrato import bloco_observacoes
from workers.worker_flow.fireads import preparar_abertura, interpretar
from workers.worker_flow.suporte.consultas_fireads import (
    ConsultaFireAdsPendente,
)
from workers.worker_funil.fireads import processar
from tests.fixtures.fireads import MIGRACAO_FIREADS, aplicar_fireads

DSN = os.environ.get("FIREADS_TEST_DSN")
NUMERO = "5511999990002"
GOOGLE = {
    "Nome": "Ana Paula Silva",
    "Email": "ana@example.com",
    "WhatsApp": NUMERO,
    "Perfil/Faixa": "Para mim",
    "Data/Hora": "08/10/2026 12:00",
}


@unittest.skipUnless(
    DSN, "Exige FIREADS_TEST_DSN local e banco vazio test_chatbot_fireads"
)
class FireAdsPostgresTests(unittest.TestCase):
    def setUp(self):
        params = conninfo_to_dict(DSN)
        locais = {"127.0.0.1", "::1", "localhost"}
        if (
            params.get("host") not in locais
            or params.get("dbname") != "test_chatbot_fireads"
            or params.get("service")
            or (params.get("hostaddr") and params["hostaddr"] not in locais)
        ):
            raise RuntimeError("FireAds exige banco descartável explícito em loopback")
        self.conn = psycopg.connect(DSN, connect_timeout=5)
        self.addCleanup(self.conn.close)
        if (
            self.conn.info.host not in locais
            or self.conn.info.dbname != "test_chatbot_fireads"
        ):
            raise RuntimeError("Destino efetivo não é o banco de teste")
        if (
            self.conn.execute("SELECT to_regnamespace('chatbot')").fetchone()[0]
            is not None
        ):
            raise RuntimeError("Recusado schema chatbot preexistente")
        self.addCleanup(self.limpar)
        self.cursor = self.conn.cursor()
        self.cursor.execute(
            "CREATE SCHEMA chatbot; CREATE TABLE chatbot.auth_user(id SERIAL PRIMARY KEY)"
        )

        @contextmanager
        def transacao(*_):
            yield self.cursor

        with ExitStack() as stack:
            for module in (bank_script, povoar_etapas, etapa_transicao_script):
                stack.enter_context(patch.object(module, "transacao_deploy", transacao))
            bank_script.criar_tabelas()
            bank_script.criar_funcoes_lock()
            povoar_etapas.insere_etapa_once()
            etapa_transicao_script.criar_e_povoar_transicoes_etapa()
        self.cursor.execute("""
            INSERT INTO chatbot.unidade(nome_unidade,nome_agente,genero,cnpj,email_responsavel,
                telefone,numero_comercial,waba_id,phone_number_id)
            VALUES('Teste FireAds','Dora','feminino','teste','unidade@example.com',
                '5511999990000','5511999990001','waba-teste','phone-teste');
            INSERT INTO chatbot.cliente(nome,waid_telefone,email) VALUES('Antigo','5511999990002','antigo@example.com');
            INSERT INTO chatbot.conversa(id_cliente,id_unidade,status_ativa) VALUES(1,1,FALSE);
        """)
        aplicar_fireads(self.cursor)
        self.cursor.execute("""
            INSERT INTO chatbot.integracao_fireads(id_unidade,url_dashbord,contrato_validado,integracao_ativa)
            VALUES(1,'https://script.google.com/macros/s/teste/exec',TRUE,TRUE);
            INSERT INTO chatbot.integracao_funil_unidade(id_unidade,nome_widget,codigo_widget,
                link_api_carrossel,codigo_canal_venda)
            VALUES(1,'Teste','TESTE','https://example.com/api','113340');
        """)
        self.conn.commit()

    def preparar_apos_http(self, contexto, mensagem, versao):
        with self.assertRaises(ConsultaFireAdsPendente):
            preparar_abertura(contexto, mensagem, versao, self.cursor)
        self.conn.commit()
        with patch(
            "workers.worker_consulta_dash.consulta_worker.get_conn",
            side_effect=lambda **_: psycopg.connect(DSN),
        ):
            self.assertTrue(executar_ciclo())
        resultado = preparar_abertura(contexto, mensagem, versao, self.cursor)
        self.conn.commit()
        return resultado

    def limpar(self):
        self.conn.rollback()
        self.conn.execute("DROP SCHEMA IF EXISTS chatbot CASCADE")
        self.conn.commit()

    def nova_conversa(self):
        cid = inserindo_em_conversa_caso_seja_nova(1, 1, self.cursor)
        self.conn.commit()
        return cid

    def test_unidade_desativada_nao_consulta_fireads(self):
        cid, mensagem, versao, contexto = self.preparar_mensagem()
        self.cursor.execute("UPDATE chatbot.unidade SET status_pagamento=FALSE")
        self.conn.commit()
        with patch("workers.worker_consulta_dash.consulta.ClienteFireAds") as api:
            self.assertEqual(
                preparar_abertura(contexto, mensagem, versao, self.cursor), contexto
            )
        api.assert_not_called()
        self.assertEqual(
            self.conn.execute(
                "SELECT count(*) FROM chatbot.consulta_fireads"
            ).fetchone()[0],
            0,
        )

    def test_desativacao_suspende_funil_e_dash_preservando_pendencias(self):
        from core.repositories.funil import envios as funil

        envio = self.preparar_envio()
        cid = envio["conversa"]
        self.cursor.execute(
            "UPDATE chatbot.conversa SET lead_no_funil=FALSE WHERE id_conversa=%s",
            (cid,),
        )
        self.assertEqual(funil.sincronizar_envios_elegiveis(self.cursor), 1)
        self.cursor.execute(
            "UPDATE chatbot.conversa SET lead_no_funil=TRUE WHERE id_conversa=%s",
            (cid,),
        )
        self.cursor.execute("UPDATE chatbot.unidade SET status_pagamento=FALSE")
        self.conn.commit()
        with patch("workers.worker_funil.fireads.ClienteFireAds") as api:
            self.assertFalse(processar(envio, self.conn, self.cursor))
        api.assert_not_called()
        for status in (False, None):
            self.cursor.execute(
                "UPDATE chatbot.unidade SET status_pagamento=%s", (status,)
            )
            self.cursor.execute(
                "UPDATE chatbot.envios_dash SET next_attempt_at=clock_timestamp()"
            )
            self.assertIsNone(envios.reservar(self.cursor))
            self.cursor.execute(
                "UPDATE chatbot.conversa SET lead_no_funil=FALSE WHERE id_conversa=%s",
                (cid,),
            )
            self.assertIsNone(funil.reivindicar_proximo_envio(self.cursor))
            self.assertIsNone(buscar_dados_lead_funil(cid, self.cursor))
            self.cursor.execute(
                "UPDATE chatbot.conversa SET lead_no_funil=TRUE WHERE id_conversa=%s",
                (cid,),
            )
        self.assertEqual(
            self.conn.execute(
                "SELECT status,snapshot FROM chatbot.envios_dash"
            ).fetchone(),
            ("pending", envio["snapshot"]),
        )
        self.assertEqual(
            self.conn.execute("SELECT status FROM chatbot.funil_envios").fetchone(),
            ("pending",),
        )
        self.cursor.execute("UPDATE chatbot.unidade SET status_pagamento=TRUE")
        self.assertIsNotNone(envios.reservar(self.cursor))

    def test_migracao_dequeue_pula_inativas_sem_perder_ordem_ou_retry(self):
        from pathlib import Path

        migration = (
            Path(__file__).resolve().parents[2]
            / "deploy/migrations/20261009_status_pagamento_workers.sql"
        )
        self.conn.commit()
        # Usa o mesmo arquivo que será aplicado no DBeaver e confirma reexecução.
        self.conn.execute(migration.read_text(encoding="utf-8"), prepare=False)
        self.conn.execute(migration.read_text(encoding="utf-8"), prepare=False)
        cid, mensagem, _, _ = self.preparar_mensagem()
        self.cursor.execute(
            "UPDATE chatbot.fila_mensagens SET status='pending',retry_count=0,processing_started_at=NULL,next_attempt_at=clock_timestamp()-INTERVAL '1 minute'"
        )
        self.cursor.execute("""
            INSERT INTO chatbot.unidade(nome_unidade,cnpj,email_responsavel,telefone,waba_id,phone_number_id)
            VALUES('Unidade ativa','outro','outro@example.com','5511999990003','outro','phone-ativo');
            INSERT INTO chatbot.atendimento_customizado(id_unidade,nome_agente,genero,numero_comercial)
            SELECT id_unidade,'Agente','masculino','5511999990004' FROM chatbot.unidade WHERE phone_number_id='phone-ativo';
            INSERT INTO chatbot.fila_mensagens(cliente_telefone,conteudo_texto,tipo_mensagem,id_phone_unidade,unidade_telefone,
                id_hash_msg,received_data_hora,status,next_attempt_at)
            VALUES('5511999990005','Oi','text','phone-ativo','5511999990003','wamid.ativa',clock_timestamp(),'pending',clock_timestamp());
            UPDATE chatbot.unidade SET status_pagamento=FALSE WHERE id_unidade=1;
        """)
        self.conn.commit()
        row = self.conn.execute("SELECT * FROM chatbot.dequeue_message()").fetchone()
        self.assertEqual(row[4], "phone-ativo")
        self.cursor.execute(
            "UPDATE chatbot.fila_mensagens SET status='sent',processing_started_at=NULL WHERE id_mensagem=%s",
            (row[0],),
        )
        for status in (False, None):
            self.cursor.execute(
                "UPDATE chatbot.unidade SET status_pagamento=%s WHERE id_unidade=1",
                (status,),
            )
            self.assertIsNone(
                self.conn.execute("SELECT * FROM chatbot.dequeue_message()").fetchone()
            )
        self.assertEqual(
            self.conn.execute(
                "SELECT status,retry_count FROM chatbot.fila_mensagens WHERE id_mensagem=%s",
                (mensagem["id_mensagem"],),
            ).fetchone(),
            ("pending", 0),
        )
        self.cursor.execute(
            "UPDATE chatbot.unidade SET status_pagamento=TRUE WHERE id_unidade=1"
        )
        retomada = self.conn.execute(
            "SELECT * FROM chatbot.dequeue_message()"
        ).fetchone()
        self.assertEqual(retomada[0], mensagem["id_mensagem"])
        from core.repositories.atendimento.fila import reagendar_mensagem_sem_erro

        self.assertEqual(
            reagendar_mensagem_sem_erro(
                retomada[0],
                self.cursor,
                retry_esperado=retomada[-1] - 1,
            ),
            0,
        )
        self.assertEqual(
            reagendar_mensagem_sem_erro(
                retomada[0],
                self.cursor,
                retry_esperado=retomada[-1],
            ),
            1,
        )
        self.cursor.execute(
            "UPDATE chatbot.fila_mensagens SET status='sent' WHERE id_mensagem=%s",
            (retomada[0],),
        )
        self.assertEqual(
            reagendar_mensagem_sem_erro(
                retomada[0],
                self.cursor,
                retry_esperado=retomada[-1],
            ),
            0,
        )

    def preparar_mensagem(self):
        cid = self.nova_conversa()
        self.cursor.execute(
            """INSERT INTO chatbot.fila_mensagens
            (cliente_telefone,conteudo_texto,tipo_mensagem,id_phone_unidade,unidade_telefone,
             id_hash_msg,id_conversa,status,retry_count,processing_started_at,received_data_hora)
            VALUES(%s,'Oi','text','phone-teste','5511999990000','wamid.fireads',%s,'processing',1,clock_timestamp(),clock_timestamp())
            RETURNING id_mensagem""",
            (NUMERO, cid),
        )
        mensagem = {
            "id_mensagem": self.cursor.fetchone()[0],
            "retry_count": 1,
            "cliente_telefone": NUMERO,
        }
        ok, versao = tentar_lock_conversa(cid, self.cursor)
        self.assertTrue(ok)
        self.conn.commit()
        contexto = {
            "id_cliente": 1,
            "id_unidade": 1,
            "conversa": {"id_conversa": cid, "id_etapa_atual": None},
        }
        return cid, mensagem, versao, contexto

    def importar(self, cid):
        abertura = consulta.buscar_abertura(cid, self.cursor)
        pendencias.solicitar(abertura, cid, NUMERO, self.cursor)
        self.conn.commit()
        reserva = pendencias.reservar(self.cursor)
        self.conn.commit()
        decisao = interpretar([GOOGLE], [], NUMERO, None)
        self.assertTrue(
            pendencias.concluir(
                reserva, {"decisao": decisao, "fontes": {}}, self.cursor
            )
        )
        pendencias.liberar_reserva(reserva["id_consulta"], self.cursor)
        resultado = consulta.aplicar_decisao(
            abertura, cid, reserva["id_consulta"], decisao, self.cursor
        )
        pendencias.marcar_aplicada(reserva["id_consulta"], cid, resultado, self.cursor)
        return resultado

    def preparar_envio(self):
        cid = self.nova_conversa()
        estado = self.importar(cid)
        self.cursor.execute(
            """UPDATE chatbot.conversa SET id_etapa_atual=19,turno='manha',
            profissao='Professora',status_dependente=FALSE WHERE id_conversa=%s""",
            (cid,),
        )
        self.cursor.execute("UPDATE chatbot.cliente SET idade=35 WHERE id_cliente=1")
        self.cursor.execute(
            """INSERT INTO chatbot.respostas_desafios(id_conversa,id_etapa,resposta)
            SELECT %s,etapa,'Às vezes' FROM generate_series(12,17) etapa""",
            (cid,),
        )
        consulta.guardar_coletas(
            {"id_cliente": 1, "id_conversa": cid, "contexto_fireads": estado},
            {"destino_dado": "cliente"},
            self.cursor,
        )
        dados = buscar_dados_lead_funil(cid, self.cursor)
        self.assertEqual(dados["nome_cliente"], "Ana Paula")
        self.assertEqual(dados["idade_cliente"], 35)
        payload = montar_payload_oportunidade(dados)
        esperado = {
            "codigo_canal_venda": "113340",
            "link_api_carrossel": "https://example.com/api",
        }
        original = envios.congelar(dados, payload, esperado, self.cursor)
        self.assertEqual(original[1], "113336")
        self.assertEqual(envios.congelar(dados, {}, esperado, self.cursor), original)
        self.assertIsNone(envios.reservar(self.cursor))  # Funil ainda não confirmou.
        self.cursor.execute(
            "UPDATE chatbot.conversa SET lead_no_funil=TRUE WHERE id_conversa=%s",
            (cid,),
        )
        envio = envios.reservar(self.cursor)
        self.conn.commit()
        return envio

    def test_migracao_preserva_personalizacao_conversas_e_reexecuta(self):
        remocao = MIGRACAO_FIREADS.with_name(
            "20261009_remover_view_unidade_atendimento.sql"
        )
        for _ in range(2):
            self.conn.execute(remocao.read_text(encoding="utf-8"), prepare=False)
        self.conn.execute(MIGRACAO_FIREADS.read_text(encoding="utf-8"), prepare=False)
        self.assertIsNone(
            self.conn.execute(
                "SELECT to_regclass('chatbot.unidade_atendimento')"
            ).fetchone()[0]
        )
        self.assertEqual(
            self.conn.execute(
                "SELECT versao FROM chatbot.migracoes_fireads ORDER BY versao"
            ).fetchall(),
            [("20261007_fireads_v1",), ("20261009_consulta_dash_v1",)],
        )
        self.assertEqual(
            self.conn.execute(
                "SELECT ac.nome_agente FROM chatbot.unidade u "
                "JOIN chatbot.atendimento_customizado ac ON ac.id_unidade=u.id_unidade"
            ).fetchone(),
            ("Dora",),
        )
        self.assertEqual(
            self.conn.execute(
                "SELECT id_conversa,id_chat FROM chatbot.conversa"
            ).fetchall(),
            [(1, 1)],
        )
        self.nova_conversa()
        self.assertEqual(
            self.conn.execute("SELECT count(*) FROM chatbot.chat").fetchone()[0], 1
        )
        self.assertEqual(
            self.conn.execute(
                "SELECT count(*) FROM chatbot.etapa_transicao"
            ).fetchone()[0],
            30,
        )

    def test_importacao_dependente_e_retry_recuperam_snapshot(self):
        cid, mensagem, versao, contexto = self.preparar_mensagem()
        api = Mock()
        api.consultar.side_effect = [
            {
                "headers": list(GOOGLE),
                "rows": [dict(GOOGLE, **{"Perfil/Faixa": "Para outra pessoa"})],
            },
            {
                "headers": ["full_name", "email", "phone_number", "para_quem"],
                "rows": [],
            },
        ]
        with patch(
            "workers.worker_consulta_dash.consulta.ClienteFireAds", return_value=api
        ):
            obtido = self.preparar_apos_http(contexto, mensagem, versao)
        self.assertTrue(obtido["conversa"]["status_dependente"])
        self.assertEqual(
            self.conn.execute("SELECT nome,email FROM chatbot.cliente").fetchone(),
            ("Ana Paula", "ana@example.com"),
        )
        self.assertEqual(
            self.conn.execute(
                "SELECT count(*) FROM chatbot.dependente WHERE id_conversa=%s", (cid,)
            ).fetchone()[0],
            1,
        )
        with patch("workers.worker_consulta_dash.consulta.ClienteFireAds") as http:
            self.assertEqual(
                preparar_abertura(contexto, mensagem, versao, self.cursor),
                obtido,
            )
            http.assert_not_called()

    def test_lock_perdido_durante_http_nao_importa_dados(self):
        cid, mensagem, versao, contexto = self.preparar_mensagem()

        def resposta(aba):
            if "Google" in aba:
                with psycopg.connect(DSN) as outro:
                    outro.execute(
                        "UPDATE chatbot.conversa SET lock_version=lock_version+1 WHERE id_conversa=%s",
                        (cid,),
                    )
                return {"headers": list(GOOGLE), "rows": [GOOGLE]}
            return {
                "headers": ["full_name", "email", "phone_number", "para_quem"],
                "rows": [],
            }

        api = Mock()
        api.consultar.side_effect = resposta
        with patch(
            "workers.worker_consulta_dash.consulta.ClienteFireAds", return_value=api
        ):
            with self.assertRaises(LockConversaPerdido):
                self.preparar_apos_http(contexto, mensagem, versao)
        self.conn.rollback()
        self.assertEqual(
            self.conn.execute("SELECT nome FROM chatbot.cliente").fetchone()[0],
            "Antigo",
        )
        self.assertIsNone(
            self.conn.execute(
                "SELECT origem_fireads FROM chatbot.conversa WHERE id_conversa=%s",
                (cid,),
            ).fetchone()[0]
        )

    def test_espera_preserva_fila_e_importa_apos_worker_separado(self):
        from core.repositories.atendimento.conversas import unlock_conversa
        from core.repositories.atendimento.fila import reagendar_mensagem_sem_erro

        cid, mensagem, versao, contexto = self.preparar_mensagem()
        with self.assertRaises(ConsultaFireAdsPendente):
            preparar_abertura(contexto, mensagem, versao, self.cursor)
        reagendar_mensagem_sem_erro(
            mensagem["id_mensagem"], self.cursor, retry_esperado=1
        )
        unlock_conversa(cid, versao, self.cursor)
        self.conn.commit()
        self.assertEqual(
            self.conn.execute(
                "SELECT status,retry_count FROM chatbot.fila_mensagens"
            ).fetchone(),
            ("pending", 0),
        )
        self.assertEqual(
            self.conn.execute(
                "SELECT status,dados FROM chatbot.consulta_fireads"
            ).fetchone(),
            ("pendente", None),
        )
        self.assertIsNone(
            self.conn.execute(
                "SELECT contexto_fireads FROM chatbot.conversa WHERE id_conversa=%s",
                (cid,),
            ).fetchone()[0]
        )
        self.conn.commit()
        with patch(
            "workers.worker_consulta_dash.consulta_worker.get_conn",
            side_effect=lambda **_: psycopg.connect(DSN),
        ), patch(
            "workers.worker_consulta_dash.consulta_worker.consultar",
            return_value={
                "decisao": interpretar([GOOGLE], [], NUMERO, None),
                "fontes": {"google": [GOOGLE], "meta": []},
            },
        ):
            self.assertTrue(executar_ciclo())
        self.assertEqual(
            self.conn.execute("SELECT nome FROM chatbot.cliente").fetchone()[0],
            "Antigo",
        )
        self.cursor.execute(
            "UPDATE chatbot.fila_mensagens SET status='processing',retry_count=1,processing_started_at=clock_timestamp()"
        )
        ok, nova_versao = tentar_lock_conversa(cid, self.cursor)
        self.assertTrue(ok)
        self.conn.commit()
        resultado = preparar_abertura(contexto, mensagem, nova_versao, self.cursor)
        self.conn.commit()
        self.assertEqual(resultado["contexto_fireads"]["origem"], "google")
        self.assertEqual(
            self.conn.execute("SELECT nome,email FROM chatbot.cliente").fetchone(),
            ("Ana Paula", "ana@example.com"),
        )

    def test_nova_conversa_atualiza_consulta_sem_apagar_contexto_anterior(self):
        cid = self.nova_conversa()
        antigo = self.importar(cid)
        self.cursor.execute(
            "UPDATE chatbot.conversa SET status_ativa=FALSE WHERE id_conversa=%s",
            (cid,),
        )
        novo = self.nova_conversa()
        atual = self.importar(novo)
        self.assertNotEqual(atual["id_consulta"], antigo["id_consulta"])
        self.assertEqual(
            self.conn.execute(
                "SELECT contexto_fireads FROM chatbot.conversa WHERE id_conversa=%s",
                (cid,),
            ).fetchone()[0],
            antigo,
        )
        self.assertEqual(
            self.conn.execute(
                "SELECT id_conversa FROM chatbot.consulta_fireads ORDER BY id_consulta DESC LIMIT 1"
            ).fetchone()[0],
            novo,
        )

    def test_retomadas_preservam_prazo_total_e_restart_expirado_segue_organico(self):
        cid, mensagem, versao, contexto = self.preparar_mensagem()
        abertura = consulta.buscar_abertura(cid, self.cursor)
        pendencias.solicitar(abertura, cid, NUMERO, self.cursor)
        self.conn.commit()
        inicio = self.conn.execute(
            "SELECT id_consulta,prazo_final FROM chatbot.consulta_fireads"
        ).fetchone()
        for _ in range(3):
            pendencias.solicitar(abertura, cid, NUMERO, self.cursor)
            self.assertEqual(
                self.conn.execute(
                    "SELECT id_consulta,prazo_final FROM chatbot.consulta_fireads"
                ).fetchone(),
                inicio,
            )
        self.cursor.execute(
            "UPDATE chatbot.consulta_fireads SET solicitado_em=clock_timestamp()-INTERVAL '301 seconds',prazo_final=clock_timestamp()-INTERVAL '1 second'"
        )
        self.conn.commit()
        resultado = preparar_abertura(contexto, mensagem, versao, self.cursor)
        self.conn.commit()
        self.assertEqual(resultado["contexto_fireads"]["motivo"], "tempo_limite_300s")
        self.assertIsNone(pendencias.reservar(self.cursor))
        self.cursor.execute(
            "UPDATE chatbot.conversa SET status_ativa=FALSE WHERE id_conversa=%s",
            (cid,),
        )
        novo = self.nova_conversa()
        pendencias.solicitar(
            consulta.buscar_abertura(novo, self.cursor), novo, NUMERO, self.cursor
        )
        row = self.conn.execute(
            "SELECT id_consulta,prazo_final>clock_timestamp()+INTERVAL '290 seconds' FROM chatbot.consulta_fireads WHERE id_conversa=%s",
            (novo,),
        ).fetchone()
        self.assertNotEqual(row[0], inicio[0])
        self.assertTrue(row[1])

    def test_retry_dash_reconcilia_bloco_sem_segundo_post(self):
        envio = self.preparar_envio()
        snap = envio["snapshot"]
        bloco = bloco_observacoes(
            envio["integracao"], envio["conversa"], snap["observacoes"]
        )
        api = Mock()
        api.consultar.return_value = {
            "headers": ["Nome", "Email", "WhatsApp", "Observação"],
            "rows": [
                {
                    "_row": 2,
                    "Nome": "Ana",
                    "Email": "ana@example.com",
                    "WhatsApp": NUMERO,
                    "Observação": "FR002\n\n" + bloco,
                }
            ],
        }
        with patch("workers.worker_funil.fireads.ClienteFireAds", return_value=api):
            self.assertTrue(processar(envio, self.conn, self.cursor))
        api.enviar.assert_not_called()
        self.assertTrue(
            self.conn.execute(
                "SELECT lead_no_dash FROM chatbot.conversa WHERE id_conversa=%s",
                (envio["conversa"],),
            ).fetchone()[0]
        )

    def test_falha_dash_fica_pending_preserva_funil_e_nao_tenta_no_mesmo_ciclo(self):
        envio = self.preparar_envio()
        api = Mock()
        api.consultar.side_effect = TimeoutError("teste")
        with patch("workers.worker_funil.fireads.ClienteFireAds", return_value=api):
            self.assertFalse(processar(envio, self.conn, self.cursor))
        self.assertEqual(
            self.conn.execute("SELECT status FROM chatbot.envios_dash").fetchone()[0],
            "pending",
        )
        self.assertIsNone(envios.reservar(self.cursor))
        self.assertTrue(
            self.conn.execute(
                "SELECT lead_no_funil FROM chatbot.conversa WHERE id_conversa=%s",
                (envio["conversa"],),
            ).fetchone()[0]
        )

    def test_reserva_concorrente_nao_e_reivindicada_e_configuracao_mudada_bloqueia(
        self,
    ):
        envio = self.preparar_envio()
        with psycopg.connect(DSN) as outro:
            self.assertIsNone(envios.reservar(outro.cursor()))
        self.cursor.execute(
            "UPDATE chatbot.integracao_fireads SET aba_destino='Outra aba'"
        )
        self.conn.commit()
        with patch("workers.worker_funil.fireads.ClienteFireAds") as http:
            self.assertFalse(processar(envio, self.conn, self.cursor))
            http.assert_not_called()

    def test_personalizacao_obrigatoria_e_chat_nao_cruza_unidades(self):
        with self.assertRaises(psycopg.errors.RaiseException):
            self.conn.execute("DELETE FROM chatbot.atendimento_customizado")
            self.conn.commit()
        self.conn.rollback()
        with self.assertRaises(psycopg.errors.UniqueViolation):
            self.conn.execute(
                "INSERT INTO chatbot.chat(id_cliente,id_unidade) VALUES(1,1)"
            )
        self.conn.rollback()
        with self.assertRaises(psycopg.errors.ForeignKeyViolation):
            self.conn.execute(
                "UPDATE chatbot.conversa SET id_chat=999 WHERE id_conversa=1"
            )

    def test_relatorios_consultam_tabelas_sem_view_incluindo_unidades_vazias(self):
        from utilitarios.reports_functions import total, weekly

        self.conn.execute("""
            INSERT INTO chatbot.unidade(id_unidade,nome_unidade,cnpj,email_responsavel,
                telefone,waba_id,phone_number_id)
            VALUES(2,'Sem histórico','outra','outra@example.com','5511999990010','waba-2','phone-2');
            INSERT INTO chatbot.atendimento_customizado(id_unidade,nome_agente,genero,numero_comercial)
            VALUES(2,'Outro agente','masculino','5511999990011');
            UPDATE chatbot.atendimento_customizado SET bpa_ativo=TRUE,idade_minima_suporte=70
            WHERE id_unidade=1;
            UPDATE chatbot.conversa SET status_dependente=FALSE,profissao='Professora'
            WHERE id_conversa=1;
            UPDATE chatbot.cliente SET idade=35 WHERE id_cliente=1;
            INSERT INTO chatbot.historico_mensagens
                (id_conversa,id_etapa,received_data_hora,cliente_telefone,conteudo_texto,
                 tipo_mensagem,id_hash_msg,id_phone_unidade,unidade_telefone,quem_enviou)
            VALUES(1,1,clock_timestamp(),'5511999990002','Olá','text',
                'wamid.relatorio','phone-teste','5511999990000','cliente');
        """)
        instante = self.conn.execute("SELECT clock_timestamp()").fetchone()[0]
        self.conn.commit()
        fim = instante + timedelta(minutes=1)
        snapshot = weekly.coletar_snapshot(self.conn, instante - timedelta(days=1), fim)
        unidades = {u["id_unidade"]: u for u in snapshot["unidades"]}
        self.assertEqual(set(unidades), {1, 2})
        self.assertEqual(
            (
                unidades[1]["nome_agente"],
                unidades[1]["bpa_ativo"],
                unidades[1]["idade_minima_suporte"],
            ),
            ("Dora", True, 70),
        )
        self.assertEqual(len(unidades[1]["conversas"]), 1)
        self.assertEqual(unidades[2]["conversas"], [])
        filtrado = weekly.coletar_snapshot(
            self.conn, instante - timedelta(days=1), fim, ids_unidade=[2]
        )
        self.assertEqual([u["id_unidade"] for u in filtrado["unidades"]], [2])
        primeiros = {
            u["id_unidade"]: u
            for u in total.coletar_primeiros_registros(self.conn, fim)
        }
        self.assertIsNotNone(primeiros[1]["primeiro_registro"])
        self.assertIsNone(primeiros[2]["primeiro_registro"])
        self.assertEqual(
            [
                u["id_unidade"]
                for u in total.coletar_primeiros_registros(self.conn, fim, [2])
            ],
            [2],
        )

    def solicitar_pendente(self):
        cid, mensagem, versao, contexto = self.preparar_mensagem()
        with self.assertRaises(ConsultaFireAdsPendente):
            preparar_abertura(contexto, mensagem, versao, self.cursor)
        self.conn.commit()
        return cid, mensagem, versao, contexto

    def resultado_google(self):
        return {
            "decisao": interpretar([GOOGLE], [], NUMERO, None),
            "fontes": {"google": [GOOGLE], "meta": []},
        }

    def test_reserva_entre_processos_e_recuperacao_apos_queda(self):
        cid, mensagem, versao, contexto = self.solicitar_pendente()
        primeiro = psycopg.connect(DSN)
        segundo = psycopg.connect(DSN)
        self.addCleanup(primeiro.close)
        self.addCleanup(segundo.close)
        reserva1 = pendencias.reservar(primeiro.cursor())
        primeiro.commit()
        self.assertIsNone(pendencias.reservar(segundo.cursor()))
        segundo.commit()
        primeiro.close()  # Simula morte do processo; não há unlock explícito.
        reserva2 = pendencias.reservar(segundo.cursor())
        segundo.commit()
        self.assertEqual(reserva1["id_consulta"], reserva2["id_consulta"])
        self.assertGreater(reserva2["versao"], reserva1["versao"])
        self.assertFalse(
            pendencias.concluir(reserva1, self.resultado_google(), self.cursor)
        )
        self.conn.commit()
        self.assertTrue(
            pendencias.concluir(reserva2, self.resultado_google(), segundo.cursor())
        )
        segundo.commit()
        segundo.close()
        resultado = preparar_abertura(contexto, mensagem, versao, self.cursor)
        self.conn.commit()
        self.assertEqual(resultado["contexto_fireads"]["origem"], "google")
        self.assertEqual(
            self.conn.execute(
                "SELECT tentativas FROM chatbot.consulta_fireads"
            ).fetchone()[0],
            2,
        )

    def test_disputa_simultanea_so_reserva_uma_vez(self):
        from concurrent.futures import ThreadPoolExecutor
        from threading import Barrier

        self.solicitar_pendente()
        barreira = Barrier(2)
        conexoes = [psycopg.connect(DSN), psycopg.connect(DSN)]
        for conn in conexoes:
            self.addCleanup(conn.close)

        def disputar(conn):
            barreira.wait(timeout=5)
            reserva = pendencias.reservar(conn.cursor())
            conn.commit()
            return reserva

        with ThreadPoolExecutor(max_workers=2) as executor:
            resultados = list(executor.map(disputar, conexoes))
        self.assertEqual(sum(r is not None for r in resultados), 1)
        self.assertEqual(
            self.conn.execute(
                "SELECT tentativas FROM chatbot.consulta_fireads"
            ).fetchone()[0],
            1,
        )

    def test_queda_antes_de_salvar_nao_deixa_resultado_parcial(self):
        self.solicitar_pendente()
        conn = psycopg.connect(DSN)
        reserva = pendencias.reservar(conn.cursor())
        conn.commit()
        self.assertTrue(
            pendencias.concluir(reserva, self.resultado_google(), conn.cursor())
        )
        conn.rollback()
        conn.close()
        self.assertEqual(
            self.conn.execute(
                "SELECT status,dados FROM chatbot.consulta_fireads"
            ).fetchone(),
            ("processando", None),
        )
        self.conn.commit()
        retomada = pendencias.reservar(self.cursor)
        self.assertEqual(retomada["id_consulta"], reserva["id_consulta"])
        self.assertGreater(retomada["versao"], reserva["versao"])
        self.conn.commit()
        pendencias.liberar_reserva(retomada["id_consulta"], self.cursor)
        self.conn.commit()

    def test_timeout_vence_resposta_tardia_sem_mudar_etapa(self):
        cid, mensagem, versao, contexto = self.solicitar_pendente()
        outro = psycopg.connect(DSN)
        self.addCleanup(outro.close)
        reserva = pendencias.reservar(outro.cursor())
        outro.commit()
        self.cursor.execute(
            "UPDATE chatbot.consulta_fireads SET solicitado_em=now()-INTERVAL '301 seconds',prazo_final=now()-INTERVAL '1 second'"
        )
        self.conn.commit()
        obtido = preparar_abertura(contexto, mensagem, versao, self.cursor)
        self.conn.commit()
        self.assertEqual(obtido["contexto_fireads"]["motivo"], "tempo_limite_300s")
        self.assertFalse(
            pendencias.concluir(reserva, self.resultado_google(), outro.cursor())
        )
        outro.commit()
        self.assertEqual(
            self.conn.execute("SELECT nome FROM chatbot.cliente").fetchone()[0],
            "Antigo",
        )
        self.assertIsNone(
            self.conn.execute(
                "SELECT id_etapa_atual FROM chatbot.conversa WHERE id_conversa=%s",
                (cid,),
            ).fetchone()[0]
        )

    def test_resultado_salvo_antes_do_prazo_pode_ser_aplicado_depois(self):
        cid, mensagem, versao, contexto = self.solicitar_pendente()
        reserva = pendencias.reservar(self.cursor)
        self.conn.commit()
        self.assertTrue(
            pendencias.concluir(reserva, self.resultado_google(), self.cursor)
        )
        pendencias.liberar_reserva(reserva["id_consulta"], self.cursor)
        self.conn.commit()
        self.cursor.execute(
            "UPDATE chatbot.consulta_fireads SET solicitado_em=now()-INTERVAL '301 seconds',prazo_final=now()-INTERVAL '1 second'"
        )
        self.conn.commit()
        resultado = preparar_abertura(contexto, mensagem, versao, self.cursor)
        self.assertEqual(resultado["contexto_fireads"]["origem"], "google")

    def test_rollback_da_aplicacao_recupera_sem_http(self):
        cid, mensagem, versao, contexto = self.solicitar_pendente()
        reserva = pendencias.reservar(self.cursor)
        self.conn.commit()
        pendencias.concluir(reserva, self.resultado_google(), self.cursor)
        pendencias.liberar_reserva(reserva["id_consulta"], self.cursor)
        self.conn.commit()
        preparar_abertura(contexto, mensagem, versao, self.cursor)
        self.conn.rollback()
        self.assertEqual(
            self.conn.execute("SELECT nome FROM chatbot.cliente").fetchone()[0],
            "Antigo",
        )
        self.assertEqual(
            self.conn.execute(
                "SELECT status,aplicado_em FROM chatbot.consulta_fireads"
            ).fetchone(),
            ("concluida", None),
        )
        with patch("workers.worker_consulta_dash.consulta.ClienteFireAds") as http:
            obtido = preparar_abertura(contexto, mensagem, versao, self.cursor)
            self.conn.commit()
            repetido = preparar_abertura(contexto, mensagem, versao, self.cursor)
        self.assertEqual(repetido, obtido)
        http.assert_not_called()

    def test_etapas_iniciadas_nunca_disparam_consulta_nem_retrocedem(self):
        cid = self.nova_conversa()
        for etapa in range(1, 25):
            self.cursor.execute(
                "UPDATE chatbot.conversa SET id_etapa_atual=%s WHERE id_conversa=%s",
                (etapa, cid),
            )
            contexto = {"conversa": {"id_conversa": cid, "id_etapa_atual": etapa}}
            self.assertEqual(preparar_abertura(contexto, {}, 0, self.cursor), contexto)
            self.assertEqual(
                self.conn.execute(
                    "SELECT count(*) FROM chatbot.consulta_fireads"
                ).fetchone()[0],
                0,
            )
        self.assertEqual(
            self.conn.execute(
                "SELECT id_etapa_atual FROM chatbot.conversa WHERE id_conversa=%s",
                (cid,),
            ).fetchone()[0],
            24,
        )

    def test_configuracao_alterada_nao_importa_dados_da_anterior(self):
        cid, mensagem, versao, contexto = self.solicitar_pendente()
        self.cursor.execute(
            "UPDATE chatbot.integracao_fireads SET aba_google='Outra aba'"
        )
        self.conn.commit()
        self.assertIsNone(pendencias.reservar(self.cursor))
        self.conn.commit()
        obtido = preparar_abertura(contexto, mensagem, versao, self.cursor)
        self.assertEqual(obtido["contexto_fireads"]["motivo"], "configuracao_alterada")

    def test_desativar_unidade_impede_reserva_e_confirmacao(self):
        self.solicitar_pendente()
        reserva = pendencias.reservar(self.cursor)
        self.conn.commit()
        self.cursor.execute("UPDATE chatbot.unidade SET status_pagamento=FALSE")
        self.conn.commit()
        self.assertFalse(
            pendencias.concluir(reserva, self.resultado_google(), self.cursor)
        )
        pendencias.liberar_reserva(reserva["id_consulta"], self.cursor)
        self.conn.commit()
        self.assertIsNone(pendencias.reservar(self.cursor))
        self.assertIsNone(
            self.conn.execute("SELECT dados FROM chatbot.consulta_fireads").fetchone()[
                0
            ]
        )

    def test_migracao_com_registro_legado_preserva_resultado_e_reexecucao(self):
        cid = self.nova_conversa()
        decisao = self.importar(cid)
        self.conn.commit()
        ddl_antigo = MIGRACAO_FIREADS.read_text(encoding="utf-8")
        ddl_antigo = ddl_antigo[
            ddl_antigo.index(
                "    CREATE TABLE chatbot.consulta_fireads"
            ) : ddl_antigo.index("    CREATE TABLE chatbot.envios_dash")
        ]
        self.cursor.execute("DROP TABLE chatbot.consulta_fireads")
        self.cursor.execute(
            "DELETE FROM chatbot.migracoes_fireads WHERE versao='20261009_consulta_dash_v1'"
        )
        self.cursor.execute(ddl_antigo)
        from psycopg.types.json import Jsonb

        self.cursor.execute(
            """INSERT INTO chatbot.consulta_fireads
            (id_chat,id_unidade,id_integracao_fireads,id_conversa_referencia,consulta_concluida,resultado,dados,consultado_em)
            SELECT id_chat,id_unidade,1,id_conversa,TRUE,'importado',%s,now()
            FROM chatbot.conversa WHERE id_conversa=%s RETURNING id_consulta""",
            (Jsonb(decisao), cid),
        )
        ident = self.cursor.fetchone()[0]
        self.conn.commit()
        novo = MIGRACAO_FIREADS.with_name(
            "20261009_worker_consulta_dash.sql"
        ).read_text(encoding="utf-8")
        self.conn.execute(novo, prepare=False)
        self.conn.execute(novo, prepare=False)
        row = self.conn.execute(
            "SELECT id_consulta,id_conversa,dados,aplicacao,status FROM chatbot.consulta_fireads"
        ).fetchone()
        self.assertEqual(row[:2], (ident, cid))
        self.assertEqual(row[2]["decisao"], decisao)
        self.assertEqual(row[3], decisao)
        self.assertEqual(row[4], "concluida")
        self.assertEqual(
            self.conn.execute(
                "SELECT contexto_fireads FROM chatbot.conversa WHERE id_conversa=%s",
                (cid,),
            ).fetchone()[0],
            decisao,
        )

    def test_conversa_sem_integracao_nao_gera_pendencia(self):
        cid, mensagem, versao, contexto = self.preparar_mensagem()
        self.cursor.execute("DELETE FROM chatbot.integracao_fireads")
        self.conn.commit()
        self.assertEqual(
            preparar_abertura(contexto, mensagem, versao, self.cursor), contexto
        )
        self.assertEqual(
            self.conn.execute(
                "SELECT count(*) FROM chatbot.consulta_fireads"
            ).fetchone()[0],
            0,
        )

    def test_banco_recusa_duplicar_consulta_da_mesma_conversa(self):
        cid, *_ = self.solicitar_pendente()
        self.cursor.execute("SAVEPOINT segunda_consulta")
        with self.assertRaises(psycopg.errors.UniqueViolation):
            self.cursor.execute(
                """INSERT INTO chatbot.consulta_fireads
                (id_conversa,id_unidade,id_integracao_fireads,entrada)
                SELECT id_conversa,id_unidade,id_integracao_fireads,entrada
                FROM chatbot.consulta_fireads WHERE id_conversa=%s""",
                (cid,),
            )
        self.cursor.execute("ROLLBACK TO SAVEPOINT segunda_consulta")
        self.assertEqual(
            self.conn.execute(
                "SELECT count(*) FROM chatbot.consulta_fireads"
            ).fetchone()[0],
            1,
        )

    def test_conversa_encerrada_durante_http_nao_recebe_resultado(self):
        cid, *_ = self.solicitar_pendente()
        reserva = pendencias.reservar(self.cursor)
        self.conn.commit()
        self.cursor.execute(
            "UPDATE chatbot.conversa SET status_ativa=FALSE,finalizou_em=now() WHERE id_conversa=%s",
            (cid,),
        )
        self.conn.commit()
        self.assertFalse(
            pendencias.concluir(reserva, self.resultado_google(), self.cursor)
        )
        pendencias.liberar_reserva(reserva["id_consulta"], self.cursor)
        self.conn.commit()
        self.assertIsNone(pendencias.reservar(self.cursor))
        self.assertIsNone(
            self.conn.execute("SELECT dados FROM chatbot.consulta_fireads").fetchone()[
                0
            ]
        )

    def test_falha_aplicar_marcador_reverte_importacao_e_contexto(self):
        cid, mensagem, versao, contexto = self.solicitar_pendente()
        reserva = pendencias.reservar(self.cursor)
        self.conn.commit()
        pendencias.concluir(reserva, self.resultado_google(), self.cursor)
        pendencias.liberar_reserva(reserva["id_consulta"], self.cursor)
        self.conn.commit()
        with patch.object(
            pendencias, "marcar_aplicada", side_effect=RuntimeError("falha simulada")
        ):
            with self.assertRaises(RuntimeError):
                preparar_abertura(contexto, mensagem, versao, self.cursor)
        self.conn.rollback()
        self.assertEqual(
            self.conn.execute("SELECT nome FROM chatbot.cliente").fetchone()[0],
            "Antigo",
        )
        self.assertIsNone(
            self.conn.execute(
                "SELECT contexto_fireads FROM chatbot.conversa WHERE id_conversa=%s",
                (cid,),
            ).fetchone()[0]
        )
        self.assertIsNone(
            self.conn.execute(
                "SELECT aplicado_em FROM chatbot.consulta_fireads"
            ).fetchone()[0]
        )
````

## Passo 21: `utilitarios/fireAds/diagnostico_abertura.py`

Atualizar o diagnóstico manual para a nova coluna e o envelope de dados; SQL permanece em utilitarios.

````python
"""Consulta o diagnóstico gravado da abertura FireAds, sem alterar o atendimento."""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('numero')
    parser.add_argument('--dashboard', action='store_true',
                        help='Confere o telefone nas abas configuradas, somente por GET.')
    args = parser.parse_args()
    from utilitarios.bootstrap import configurar_ambiente_utilitario
    from utilitarios.maintenance.remover_contato import formatos

    configurar_ambiente_utilitario()
    from core.database.connection_aws import get_conn
    from psycopg.rows import dict_row

    with get_conn(application_name='diagnostico_abertura_fireads', connect_timeout=8) as conn:
        with conn.transaction():
            conn.execute('SET TRANSACTION READ ONLY')
            conn.execute("SET LOCAL statement_timeout = '15s'")
            with conn.cursor(row_factory=dict_row) as cursor:
                cursor.execute("""
                    SELECT c.id_conversa, u.nome_unidade, cl.waid_telefone,
                           c.iniciou_em, c.id_etapa_atual, c.origem_fireads,
                           c.contexto_fireads->>'resultado' AS resultado_contexto,
                           c.contexto_fireads->>'motivo' AS motivo_contexto,
                           q.consulta_concluida, q.resultado, q.consultado_em,
                           q.dados->'decisao'->>'motivo' AS motivo_consulta,
                           i.integracao_ativa, i.contrato_validado, i.ativada_em,
                           i.aba_google, i.aba_meta, i.aba_destino, i.url_dashbord,
                           i.fuso_formularios
                    FROM chatbot.cliente cl
                    JOIN chatbot.conversa c ON c.id_cliente=cl.id_cliente
                    JOIN chatbot.unidade u ON u.id_unidade=c.id_unidade
                    LEFT JOIN chatbot.consulta_fireads q
                        ON q.id_conversa=c.id_conversa
                    LEFT JOIN chatbot.integracao_fireads i ON i.id_unidade=c.id_unidade
                    WHERE regexp_replace(cl.waid_telefone,'[^0-9]','','g')=ANY(%s)
                    ORDER BY c.id_conversa DESC LIMIT 5
                """, (formatos(args.numero),))
                registros = cursor.fetchall()
                print(json.dumps([{k: v for k, v in r.items() if k != 'url_dashbord'}
                                  for r in registros], ensure_ascii=False, default=str, indent=2), flush=True)
    if args.dashboard and registros:
        import requests
        from concurrent.futures import ThreadPoolExecutor
        from core.integrations.fireads.contrato import telefone, localizar
        from utilitarios.fireAds.test_Dash import limpar_numero

        registro = next((r for r in registros if r.get('url_dashbord')), None)
        if not registro:
            raise ValueError('Não há configuração FireAds para estas conversas.')
        alvos = set(formatos(args.numero))
        fontes = {}

        def consultar(aba):
            try:
                resposta = requests.get(registro['url_dashbord'],
                                        params={'sheet': aba, 'abas': '0'}, timeout=(5, 25))
                resposta.raise_for_status()
                corpo = resposta.json()
                dados = corpo.get('data', {})
                if corpo.get('success') is not True or dados.get('aba') != aba:
                    return {'aba': aba, 'erro': 'Resposta recusada ou aba divergente'}
                fontes[aba] = dados
                campos = [h for h in dados['headers'] if any(
                    p in str(h).lower() for p in ('phone', 'telefone', 'whatsapp', 'celular'))]
                encontrados = []
                for row in dados['rows']:
                    if not any(limpar_numero(row.get(c)) in alvos for c in campos):
                        continue
                    resumo = {k: row.get(k) for k in ('_row', 'Nome', 'full_name',
                              'Perfil/Faixa', 'para_quem', 'Canal', 'Data/Hora', 'created_time') if k in row}
                    resumo.update({c: row.get(c) for c in campos})
                    resumo['corresponde_telefone_exato_worker'] = any(
                        telefone(row.get(c)) == telefone(registro['waid_telefone']) for c in campos)
                    resumo['corresponde_busca_local_com_variantes'] = any(
                        localizar([row], registro['waid_telefone'], c) for c in campos)
                    encontrados.append(resumo)
                return {'aba': aba, 'encontrados': encontrados}
            except (requests.RequestException, ValueError, KeyError, TypeError) as exc:
                return {'aba': aba, 'erro': type(exc).__name__}

        abas = list(dict.fromkeys(registro[k] for k in ('aba_google', 'aba_meta', 'aba_destino')))
        with ThreadPoolExecutor(max_workers=3) as pool:
            for resultado in pool.map(consultar, abas):
                print(json.dumps(resultado, ensure_ascii=False, indent=2), flush=True)
        if registro['aba_google'] in fontes and registro['aba_meta'] in fontes:
            from workers.worker_consulta_dash.resultado import interpretar

            decisao = interpretar(fontes[registro['aba_google']]['rows'],
                                  fontes[registro['aba_meta']]['rows'],
                                  registro['waid_telefone'], registro['fuso_formularios'])
            print(json.dumps({'simulacao_local_sem_gravacao': {
                k: decisao.get(k) for k in ('resultado', 'origem', 'motivo', 'status_dependente')
            }}, ensure_ascii=False, indent=2), flush=True)


if __name__ == '__main__':
    main()
````

## Passo 22: `deploy/systemd/chatbot-worker-consulta-dash.service`

Instalar o sexto serviço, com o mesmo usuário, ambiente e proteções operacionais.

````ini
[Unit]
Description=Chatbot - consulta periodica dos formularios FireAds
Wants=network-online.target
After=network-online.target

[Service]
Type=simple
User=chatbot
Group=chatbot
WorkingDirectory=/opt/chatbot/app
EnvironmentFile=/etc/chatbot/chatbot.env
Environment=PYTHONPATH=/opt/chatbot/app
Environment=PYTHONUNBUFFERED=1
Environment=PYTHONDONTWRITEBYTECODE=1
ExecStart=/opt/chatbot/venv/bin/python -m workers.worker_consulta_dash.iniciar_worker_consulta_dash
Restart=always
RestartSec=5s
TimeoutStopSec=45s
KillSignal=SIGTERM
StandardOutput=journal
StandardError=journal
SyslogIdentifier=chatbot-worker-consulta-dash

NoNewPrivileges=true
PrivateDevices=true
PrivateTmp=true
ProtectControlGroups=true
ProtectHome=true
ProtectKernelLogs=true
ProtectKernelModules=true
ProtectKernelTunables=true
ProtectSystem=full
RestrictSUIDSGID=true
UMask=0027

[Install]
WantedBy=multi-user.target
````

## Passo 23: `docs/valida_dados_parciais_fireads.md`

Documentar esquema, cenários, recuperação, capacidade e implantação coordenada.

````markdown
# Consulta FireAds por conversa — operação

Este documento acompanha o código do worker separado. Aplicar junto da migração
`deploy/migrations/20261009_worker_consulta_dash.sql` e do novo serviço.

## Contrato

Consultar só uma vez logicamente por conversa nova, antes da primeira resposta.
O `worker_flow` não executa HTTP FireAds, não cria threads auxiliares e não aguarda
rede. Registra a pendência e devolve a mensagem à fila por 5 segundos, sem consumir
retry. O worker de consulta verifica o banco a cada 2 segundos quando ocioso; havendo
trabalho, processa uma consulta e segue para a próxima sem espera adicional.

Google e Meta são lidos por inteiro no contrato atual do Apps Script. Ambas as
leituras e a interpretação terminam antes de gravar `dados` em uma única transação.
Armazenam-se somente as linhas correspondentes ao telefone consultado, não as de
outros clientes. Não há checkpoints parciais por aba. Uma falha real de conexão,
HTTP ou contrato conclui organicamente com diagnóstico, conforme a regra aprovada.

O prazo total é de 300 segundos desde a solicitação, incluindo fila, ambas as abas,
redirecionamentos e reexecuções. Não é renovado após queda. A decisão de timeout é
persistida pelo primeiro ciclo que perceber o prazo vencido, inclusive pelo flow
se o serviço de consulta estiver parado. Portanto, a resposta pode ocorrer alguns
segundos depois do limite, conforme a agenda da fila. Uma chamada de rede ainda em
andamento não pode importar nada depois desse encerramento. Um resultado confirmado
no banco antes do prazo pode ser aplicado depois, sem ser descartado por demora do flow.

## Banco e recuperação

`consulta_fireads.id_conversa` é único. O chat é obtido por `conversa.id_chat`; não
há coluna de chat duplicada nem view. `id_unidade` permanece para as FKs compostas
que impedem vincular conversa e integração de unidades diferentes.

- `entrada`: telefone, URL, abas e fuso congelados na solicitação.
- `status`: pendente, processando ou concluida; `consulta_concluida` é mantida por
  compatibilidade e uma constraint exige consistência com o status.
- `dados`: envelope com `decisao` e `fontes`, gravado completo ou mantido NULL.
- `resultado`: pendente/importado/ausente/incompleto/ambiguidade/erro.
- `solicitado_em` e `prazo_final`: orçamento persistente da abertura.
- `tentativas`, `versao_reserva`, `processing_started_at` e `reserva_ate`: reserva
  operacional; tentativas adicionais apenas recuperam uma execução interrompida.
- `consultado_em`: conclusão, inclusive ausência/erro/timeout.
- `aplicacao` e `aplicado_em`: decisão efetivamente aplicada pelo flow. Pode divergir
  do resultado externo se, por exemplo, houver conflito de e-mail na importação.
- `ultimo_erro`: diagnóstico sem corpo HTTP, credenciais ou dados de outro cliente.
- `atualizado_em`: última alteração, sem servir para reiniciar o prazo.

A reserva combina advisory lock de sessão PostgreSQL e versão persistida. Não há
transação nem row lock aberto durante HTTP: a conexão fica ociosa, mantendo só o
advisory lock. Dois processos não consultam o mesmo registro simultaneamente com
a sessão viva. A morte do processo libera o lock quando o banco encerra a conexão;
o próximo worker pode recuperar a mesma consulta antes dos 300 segundos. Perda de
rede pode retardar a detecção da sessão morta; o prazo orgânico continua valendo.

A gravação exige versão e prazo válidos. Timeout, suspensão da unidade, alteração
de configuração, conversa encerrada ou abertura já iniciada impedem confirmação
indevida. Não usar pool com troca de sessão: o lock depende da mesma conexão.
O próprio fechamento da conexão libera o lock, mesmo quando unlock falha.

O flow mantém seu lock versionado de conversa, a ordem dos turnos e a identificação
da mensagem. Solicitação e reagendamento são confirmados juntos no handler de
espera. A conversa pode já ter sido criada em um checkpoint anterior: se houver
queda nesse intervalo, a fila recria apenas a solicitação, reutilizando a conversa.
Importação, snapshot, histórico do cliente e marcador de aplicação pertencem à
transação do flow. O envio WhatsApp e a recuperação de seu recibo seguem o protocolo
atual; a janela de envio aceito externamente antes do commit local continua existindo.

Não alterar as regras existentes do webhook: no contrato atual, mensagens adicionais
chegando antes da resposta da entrada aberta podem ser descartadas na admissão.
As mensagens já admitidas na fila mantêm as guardas de ordem; não prometer juntar
textos enviados durante os minutos de espera nesta mudança.

## Cenários

| Situação | Resultado |
| --- | --- |
| Sem integração / conversa já iniciada | Atendimento atual, sem nova consulta. |
| Nova conversa elegível com integração | Uma solicitação persistida; nenhuma saudação prematura. |
| Google ou Meta completo | Importa titular, e-mail e destinatário; abertura na profissão, etapa 4. |
| Ambas as fontes | Registro mais recente comparável; ambiguidade segue orgânico. |
| Ausente / incompleto / falha / timeout | Atendimento orgânico desde a etapa 1, motivo registrado. |
| Resultado aplicado e retry | Reutiliza o contexto; nenhuma nova leitura ou regressão de etapa. |
| Pessoa preenche formulário depois da abertura | Considerar somente na próxima conversa. |
| Outra conversa do mesmo chat | Outro id_consulta; histórico anterior preservado. |
| Unidade suspensa | Não reservar nem importar; conservar pendências e histórico. |
| Configuração FireAds alterada durante a espera | Não aplicar a configuração antiga; concluir com motivo explícito. |

Telefone com e sem nono dígito, nome composto, descarte de faixa etária/objetivo,
saudação personalizada, salto da coleta do e-mail e canais Funil mantêm as regras
existentes. A aba geral não classifica a abertura; o worker_funil mantém sua própria
consulta antes da escrita e a preservação das observações existentes.

## Implantação coordenada

1. Salvar backup e subir a revisão contendo TODOS os arquivos do plano.
2. Na VM, conferir a revisão e parar follow-up, webhook, flow, Funil e consumo Meta.
   Se o serviço de consulta já existir de uma tentativa anterior, parar também.
3. Atualizar o checkout com fast-forward. Manter serviços parados enquanto código
   e esquema forem incompatíveis. Não executar setup ou seeds em produção.
4. Executar inteiro o SQL final do plano no DBeaver. Exigir `migracao_ok=true` e
   `vinculos_invalidos=0`. Em erro, realizar ROLLBACK e corrigir antes de continuar.
5. Instalar o novo serviço com os comandos abaixo. Não iniciar ainda.
6. Sob o usuário chatbot e o ambiente já existente, executar `manage.py check`
   e `collectstatic --noinput`. Não precisa `makemigrations`/`migrate`: os models
   do domínio são `managed=False` e a mudança é o SQL manual indicado.
7. Iniciar consulta, webhook e flow; conferir status/logs. Depois iniciar Funil,
   consumo Meta e follow-up. Usar os mesmos controles de saúde do deploy atual.
8. Observar uma NOVA conversa autorizada de teste. Não resetar conversas antigas.

Instalação do sexto serviço na VM (após conferir a revisão):

```bash
cd /opt/chatbot/app &&
sudo install -m 0644 deploy/systemd/chatbot-worker-consulta-dash.service /etc/systemd/system/chatbot-worker-consulta-dash.service &&
sudo systemctl daemon-reload &&
sudo systemctl enable chatbot-worker-consulta-dash.service
```

Inicialização, depois da migração e verificações Django:

```bash
sudo systemctl start chatbot-worker-consulta-dash.service chatbot-webhook.service chatbot-worker-flow.service &&
systemctl show chatbot-worker-consulta-dash.service chatbot-webhook.service chatbot-worker-flow.service -p Id -p ActiveState -p SubState -p NRestarts --no-pager
```

Depois da conferência anterior:

```bash
sudo systemctl start chatbot-worker-funil.service chatbot-worker-consumo-meta.service &&
sudo systemctl start chatbot-worker-followup.service &&
sudo journalctl -u chatbot-worker-consulta-dash.service -u chatbot-worker-flow.service --since "5 minutes ago" -n 100 --no-pager
```

Não executar `git reset` para a versão anterior mantendo o novo esquema. Em falha,
manter os serviços afetados parados e corrigir para frente, ou restaurar conjuntamente
backup de banco e código sob procedimento controlado. Não há reversão destrutiva
automática que descarte o novo histórico de consultas.

## Capacidade e limites

Uma instância do novo serviço faz uma leitura por vez. Isso organiza a recuperação,
mas não acelera a planilha. Picos podem consumir o orçamento enquanto uma consulta
aguarda na fila e resultar em orgânico. Os locks permitem testar mais instâncias
futuramente sem reservar a mesma consulta; esta entrega mantém uma instância.

O deadline protege a decisão e a gravação, não promete terminar qualquer operação
de rede no exato milissegundo do prazo. O atendimento continua independente dessa
chamada. Quedas podem repetir GET, que não cria leads; nenhuma abertura usa POST
no dashboard. A duplicação rara de envio WhatsApp antes de persistir recibo continua
sendo uma fronteira externa já conhecida, não uma garantia de exatamente uma vez.

## Migração do histórico

Preservar os IDs e dados das consultas que existem hoje e seus vínculos com a
conversa referenciada. A estrutura antiga guardava somente a última consulta do
chat: não inventar registros anteriores. Contextos de conversas históricas ficam
intactos; IDs antigos dentro de JSONs são referências históricas, não novas FKs.
As novas conversas passam a ter registros independentes. Pendências antigas mantêm
seu início registrado e não ganham outros 300 segundos durante o deploy.
````

## Passo 24: `workers/README.md`

Registrar a responsabilidade do novo worker.

````markdown
# Workers

Camada assíncrona responsável pelo atendimento no WhatsApp, lembretes de
inatividade e publicação periódica de oportunidades no Funil de Vendas.

- [Portal do projeto](../README.md)
- [Regras de negócio](../REGRAS_DE_NEGOCIO.md)
- [Padrões de arquitetura](../PADROES_DE_ARQUITETURA.md)
- [Rotina de implementação de etapas](../ROTINA_IMPLEMENTACAO_ETAPAS.md)

## Estrutura

```text
workers/
├── worker_flow/
│   ├── iniciar_flow_worker.py
│   ├── valida_banco.py
│   ├── valida_historico.py
│   ├── tratar_bloqueio.py
│   ├── response_flow/
│   │   ├── flow_worker.py
│   │   ├── flow_sender.py
│   │   ├── repeticao_followup.py
│   │   ├── etapas/
│   │   │   ├── validadores_universais/
│   │   │   └── validadores_contexto/
│   │   └── transicoes/
│   │       ├── contexto_transicao.py
│   │       ├── eventos.py
│   │       └── resolver_transicao.py
│   ├── transacoes/
│   │   ├── efeitos_transicao.py
│   │   ├── encerramento_atendimento.py
│   │   ├── persistencia_resposta.py
│   │   ├── retorno_followup.py
│   │   ├── movimento_conversa.py
│   │   ├── finalizacao_fila.py
│   │   ├── lock_conversa.py
│   │   └── ordem_turno.py
│   └── suporte/
│       ├── cache_repair.py
│       └── estado_ciclo.py
├── worker_followup/
│   ├── iniciar_worker_followup.py
│   ├── config.py
│   └── followup_worker.py
├── worker_funil/
│   ├── iniciar_worker_funil.py
│   ├── config.py
│   ├── funil_worker.py
│   ├── processamento.py
│   └── exceptions.py
└── tratamento_erros_externos/
```

## Ciclo principal

`worker_flow/iniciar_flow_worker.py` supervisiona o processo. Se
`worker_flow()` escapar com uma exceção, registra o traceback, aguarda e
reinicia o fluxo.

`worker_flow/response_flow/flow_worker.py` é o orquestrador do ciclo:

```text
dequeue
-> respeitar mensagem anterior
-> validar cliente, unidade e conversa
-> barrar conversa com bloqueio vigente
-> adquirir lock
-> vincular fila à conversa
-> reler conversa sob lock e reconhecer retomada de follow-up
-> persistir histórico do cliente
-> validar a reação ao follow-up ou a resposta normal pelo mesmo fluxo
-> persistir histórico/contexto do bot
-> marcar fila como sent
-> liberar lock e fechar conexão
```

## Propriedade transacional

Conexão, `commit`, `rollback` e `close` do ciclo pertencem ao `flow_worker.py`.
Os commits intermediários são checkpoints recuperáveis:

1. claim da fila;
2. espera por mensagem anterior, quando necessária;
3. validação do banco;
4. aquisição do lock;
5. vínculo, releitura e histórico do cliente, incluindo o marcador de retomada quando aplicável;
6. renovação do lock antes do envio;
7. histórico e contexto do bot; na retomada, conclusão do marcador e reset do stage;
8. status `sent`, após conferir novamente a posse do lock;
9. unlock.

Uma função auxiliar pode executar uma operação com o cursor recebido, mas não
deve decidir a transação fora do orquestrador.

### Vínculo da fila com a conversa

O vínculo `fila_mensagens.id_conversa` é uma anotação de integridade e
ordenação; ele não é o lock de turno e não substitui a resolução atual por
`(cliente, unidade)`.

O repositório preenche o vínculo quando ele está vazio ou já aponta para a mesma
conversa. Um vínculo legado divergente só é reparado quando a fila ainda não tem
histórico. Se nenhuma linha puder ser vinculada com segurança, o worker falha
fechado: devolve a mensagem para `pending` por 300 segundos, sem consumir uma
tentativa de erro e sem enviar resposta.

Se a conversa anterior continuar ativa, a mensagem permanece na mesma conversa
e segue a etapa já atualizada. Se o encerramento tiver bloqueio vigente, a
mensagem é removida como conversa bloqueada. Uma conversa nova só é resolvida
quando o encerramento permite recomeço imediato (`bloqueio_dias = 0`) ou quando
o bloqueio já expirou.

As barreiras que continuam decidindo o atendimento são:

- advisory lock do turno por cliente e unidade no webhook;
- lock versionado da conversa no worker;
- verificação de mensagem anterior ainda aberta;
- `resposta_bot_para_mensagem_atual`, que impede novo envio em um retry.

## Retry e recuperação

- dequeue incrementa `retry_count`;
- `processing` abandonado volta a ser elegível após o timeout do banco;
- falhas tratadas usam `tratamento_erros_externos/expection_process.py`;
- o limite atual é de três tentativas;
- ao atingir o limite, a mensagem é excluída;
- retry com histórico do bot existente não chama a Meta novamente.

O worker mantém a fila sem `sent` quando envio ou persistência final falham.
Depois de uma resposta do bot persistida, o retry repara contexto e conclui a
fila sem duplicar o envio.

## Locks e ordenação

- apenas um worker processa a conversa por vez;
- `lock_version` impede unlock por proprietário antigo;
- uma mensagem posterior não ultrapassa outra anterior aberta;
- a verificação de mensagem anterior ocorre logo depois do claim, antes de
  resolver conversa e tentar seu lock;
- espera por mensagem anterior (30 segundos) ou lock recusado (5 segundos) não
  consome tentativa de erro.

## Response flow

- `flow_worker.py`: transação, checkpoints e handlers.
- `retomada_followup.py`: valida a reação com o fluxo normal e a saudação de retorno;
- `repeticao_followup.py`: repetição neutra para contexto inválido no retorno,
  compatibilidade da etapa 8 e recuperação da resposta existente;
- `flow_sender.py`: preserva `resposta_bot_atual` e seleciona o resolver da
  etapa atual;
- `etapas/resolver_etapa<n>.py`: valida a resposta, aplica tratamentos e
  encaminha para o destino autorizado;
- `etapas/validadores_universais/`: mídia, financeiro, nome, opções da triagem
  e outras validações reutilizáveis;
- `etapas/validadores_contexto/`: respostas específicas de cada pergunta;
- `transicoes/contexto_transicao.py`: transforma o resultado da consulta em
  origem e mapa explícitos no contexto histórico;
- `transicoes/resolver_transicao.py`: decide `origem + evento -> destino`.

Textos e chamadas PyWa não pertencem a essa pasta. Use
`core/integrations/whatsapp/messages` e
`core/integrations/whatsapp/pywa_functions/pywa_senders`.

Tratamentos não produzem evento e permanecem na etapa atual. Respostas válidas
utilizam a tabela `chatbot.etapa_transicao`; o destino não é calculado com
`id_etapa + 1`.

Validadores universais mantêm o mesmo significado em todas as etapas e não
escolhem entre arestas diferentes. Quando uma resposta pode gerar destinos
distintos, o validador é contextual e devolve diretamente o evento daquela
origem, mesmo que outra etapa reconheça os mesmos textos com eventos próprios.

### Regras atuais das etapas

- Etapa 4: profissão válida é persistida em `conversa.profissao` e atualiza
  também `cliente.profissao`. O snapshot da conversa preserva o atendimento
  anterior quando o cadastro do cliente muda.
- Etapa 6: suporte NULL/50/60/70/80, exclusivo do titular até 89. Universal 90+
  prioritária em ambas as rotas. Menores de 18 e dependentes abaixo de 4 com BPA
  ou 5 sem BPA encerram sem contato. Todos esses casos ficam fora do Funil e
  sem bloqueio. O contexto conserva a categoria e o limite usados no envio.
  A recuperação reconhece a resposta da entrada em retry antes de decidir a
  categoria e valida a idade daquela entrada, nunca a idade global. Se necessário,
  reconstrói suporte compatível com a idade; mínimo BPA vem do corpo enviado.
  Não recalcula um motivo já confirmado e não altera commits ou idempotência.
  O validador numérico mantém o contrato 100+ para replay de avanços antigos.
- Etapa 7: confirmações de aceite geram `oferta_aceita` (`7 -> 10`);
  `Talvez mais tarde` gera `oferta_adiada` (`7 -> 8`). Pedidos como
  `quero mais informações` ou `quero saber mais` não são aceite; assim como
  negativas livres, recebem tratamento sem avançar.
- Etapa 10: a política parte de `email_obrigatorio` da unidade, mas o próprio
  titular de 60 a 99 anos fica dispensado quando chega a essa etapa. A exceção
  não se aplica ao dependente nem à idade do responsável. Mídia, reforço e
  financeiro são tratados antes da coleta. Com e-mail opcional, a resposta
  pode avançar como endereço válido, ausência declarada ou não informado;
  os três casos usam `email_valido` (`10 -> 11`). Sem endereço, o efeito grava
  `cliente.email = NULL`, sem manter um e-mail de atendimento anterior.
- Etapa 11: `Começar triagem`, o callback do botão e confirmações textuais como
  `iniciar triagem`, `sim` e `vamos começar` autorizam o início. A classificação
  permanece no validador contextual da etapa, após os tratamentos universais.

No retry já respondido da etapa 10, o resultado aceito do e-mail é reconstruído
pelo histórico original, sem nova chamada à Meta nem reavaliação pela política
de e-mail atual da unidade.

### Recuperação de encerramento por idade

A reconstrução em `transacoes/encerramento_atendimento.py` só é usada com
`resposta_ja_existia`: o histórico precisa comprovar a resposta do bot vinculada
à mesma conversa e à mesma entrada em recuperação. Não reclassifica uma conversa
já concluída nem procura uma mensagem qualquer de outro atendimento.

O corpo e o tipo da resposta salva identificam a categoria de encerramento.
`validar_idade(texto_cliente_atual)` extrai um inteiro da entrada vinculada:
`71`, `71 anos`, `71 anos de idade` e `Setenta e um` produzem 71. Nunca comparar
texto livre com o limite nem usar `cliente.idade`, cujos efeitos podem estar
pendentes. Entrada inválida ou ambígua não autoriza inventar uma faixa.

Para suporte comprovado de titular entre 50 e 89, manter o limite atual se
abranger a idade. Se estiver desativado ou não a abranger, usar a maior opção
50/60/70/80 que não ultrapasse a idade. Essa faixa justifica o encaminhamento,
mas não comprova qual configuração exata existia; a reconstrução fica no log.

| Resposta já registrada | Idade extraída | Suporte antes do retry | Resultado |
| --- | --- | --- | --- |
| Suporte de titular | 51 | 60+ | `suporte_idoso_50` |
| Suporte de titular | 71 | 80+ | `suporte_idoso_70` |
| Suporte de titular | 71 | 60+ | `suporte_idoso_60` |
| Universal de titular, enviada com suporte desativado | 91 | 80+ | `idade_universal_90` |
| Universal de dependente, enviada com suporte desativado | 92 | 80+ | `idade_universal_90` |

Nos dois casos universais, a categoria da resposta já enviada tem prioridade.
Para dependentes há ainda a restrição independente de que suporte configurável
é exclusivo de titulares. Nenhum desses casos é convertido em suporte 80+.
Novos atendimentos aplicam a universal a partir de 90, com qualquer configuração.
No retry legado de 100+ sem motivo confirmado, o corpo igual entre versões não
comprova o limiar histórico; conserva-se o motivo genérico. Suporte antigo de
90–99 também permanece genérico. O mínimo BPA vem da resposta efetivamente enviada.

A recuperação conclui o encerramento e a fila `sent` na mesma transação, sem
reenviar a resposta, sem Funil e sem bloqueio de 30 dias por idade. Uma conversa
nova segue as regras atuais: titular de 71 com suporte 80+ continua normalmente.
Se a Meta aceitou o envio, mas nenhuma resposta foi persistida antes da falha,
permanece o risco aceito de novo envio com a configuração atual.

### Saudação de retorno

No caminho normal com `followup_stage = 0`, após a etapa 1,
`valida_historico.py` compara o horário da mensagem atual do
cliente com o último envio do bot confirmado como `sent` na mesma conversa.
Com intervalo de pelo menos três horas e nome disponível, `flow_sender.py`
prefixa a resposta com `Bom te ver novamente, <nome> ☺️`, inclusive quando ela é um
tratamento. O texto enviado e o histórico recebem o mesmo prefixo uma vez.

Essa saudação não é follow-up nem disparo por inatividade: depende de uma nova
mensagem do cliente, não cria mensagem separada e não altera a transição. A
etapa 1, dados de nome/data ausentes ou incompatíveis e retries com resposta
persistida não geram uma nova saudação.

## Persistência de transições

As responsabilidades estão divididas assim:

- `transacoes/persistencia_resposta.py`: orquestra a persistência final;
- `transacoes/movimento_conversa.py`: classifica e persiste inicialização,
  transição ou permanência;
- `transacoes/efeitos_transicao.py`: exibe cada ponte como
  `origem + evento -> destino` e grava seus efeitos específicos;
- `transacoes/encerramento_atendimento.py`: resolve e aplica encerramentos,
  inclusive a reconstrução do encaminhamento ao suporte no retry.

Fluxo:

```text
histórico do bot
-> movimento da conversa e confirmação da aresta no PostgreSQL
-> efeitos específicos da transição
```

O `flow_worker.py` continua dono do commit e rollback. Os repositórios recebem o
cursor e não controlam a transação.

## Worker do Funil

`worker_funil` é independente do atendimento. Ele não consome
`fila_mensagens`, não envia WhatsApp e não altera o mapa de transições.

`funil_worker.py` possui o laço operacional interno: executa um ciclo completo,
aguarda `FUNIL_INTERVALO_SEGUNDOS` depois do sucesso (padrão: 1.800 segundos,
30 minutos) e recupera indisponibilidade esperada do
banco com espera linear de 5 em 5 segundos, limitada a 60. O arquivo
`iniciar_worker_funil.py` possui o laço supervisor externo. Se uma falha crítica
escapar do worker, ele aguarda 5 segundos fixos e cria o worker novamente.

```text
materializar conversas em etapas elegíveis
-> claim de um funil_envios com FOR UPDATE SKIP LOCKED
-> commit da reserva
-> montar snapshot do cliente/dependente/triagem
-> encerrar a transação de leitura
-> criar uma oportunidade na ApiCarrossel
-> marcar lead_no_funil e funil_envios=sent no mesmo commit local
-> repetir até o limite do lote
-> aguardar FUNIL_INTERVALO_SEGUNDOS
```

Cada lead é isolado. Falha de payload ou API volta o item para `pending`, agenda
a próxima tentativa e permite processar os demais. Indisponibilidade operacional
do banco é recuperada pelo laço interno; defeitos críticos escapam para o
supervisor externo.

O claim possui lease: um item abandonado em `processing` volta a ser elegível
depois de `FUNIL_LEASE_SEGUNDOS`. Isso permite recuperação de processo morto e
protege múltiplas instâncias com `SKIP LOCKED`.

Não existe transação distribuída entre PostgreSQL e Funil. Se o CRM confirmar e
o banco cair antes do commit local, o item permanece `processing` e poderá ser
reenviado após o lease. O título atual é `Chatbot Lead <nome_unidade>` e não
contém o ID da conversa; ele não identifica sozinho um envio nem impede
duplicidade externa. Não há reconciliação automática com o CRM.

O processo nasce desativado. `FUNIL_WORKER_ENABLED=True` deve ser configurado
somente depois do teste manual da unidade. O ponto de entrada é
`python -m workers.worker_funil.iniciar_worker_funil`; o serviço de produção
está em
[`deploy/systemd/chatbot-worker-funil.service`](../deploy/systemd/chatbot-worker-funil.service).

## Testes relacionados

- `tests/unit/test_worker_flow_runtime.py`;
- `tests/unit/test_persistencia_essencial.py`;
- `tests/unit/test_retry_essencial.py`;
- `tests/unit/test_fluxo_turno_abc.py`;
- `tests/unit/test_suporte_idoso_email_obrigatorio.py`;
- `tests/unit/test_saudacao_retorno.py`;
- `tests/unit/test_validador_profissao.py`;
- `tests/unit/test_valida_etapa7.py`;
- `tests/unit/test_sondas_funil.py`;
- `tests/unit/test_followup.py`;
- `tests/integration/test_followup_postgres.py`.

O núcleo transacional e os testes específicos estão descritos em
[`tests/README.md`](../tests/README.md).

## Worker de follow-up

`worker_followup/iniciar_worker_followup.py` é o quarto serviço da VM. Seu laço
seleciona candidatos pelo PostgreSQL e chama `followup_worker.py`, proprietário
da conexão e dos commits proativos. Não faz dequeue nem chama validadores de etapas.
`FOLLOWUP_WORKER_ENABLED` é falso por padrão em execução manual; a unit systemd
o habilita explicitamente. Lote padrão: 20; intervalo entre lotes: 60 segundos.
As candidatas são processadas uma por vez, com lock e transações independentes.
Etapas 1–17 admitem novos lembretes; a 18 somente quando a unidade está sem link. As etapas 19–24 são inelegíveis.
A paginação visita candidatos posteriores mesmo quando os primeiros falham.
Uma falha individual não interrompe o lote. A candidata pode ser tentada novamente
quando a paginação voltar ao início, depois de revalidar todas as condições; não
há promessa de retry no lote imediatamente seguinte ou de reenvio fora da janela Meta.

### Configuração e elegibilidade

| Variável | Padrão no Python | Valores aceitos |
|---|---|---|
| `FOLLOWUP_WORKER_ENABLED` | `False` | Booleano; a unit configura `true`. |
| `FOLLOWUP_POLL_SECONDS` | `60` | 5–3.600 segundos de espera após cada lote. |
| `FOLLOWUP_BATCH_SIZE` | `20` | 1–100 candidatas por lote; processamento sequencial. |

Os dois textos são montados em `messages/followup_messages.py` com os dados da
releitura após o lock. O primeiro convida a continuar o atendimento e receber a
experiência Supera gratuita na unidade, com rodapé `Estaremos te esperando!`.
Usa o nome do titular já informado no atendimento (nunca nome antigo na etapa 1)
e adapta o convite para dependente com nome ou, sem o nome, “receber vocês”.
O segundo é a despedida personalizada, com rodapé `Abraços, {nome_agente}. 🧡`;
sem nome de dependente coletado, mantém a versão do titular.
Para despachar, todas as condições
precisam continuar válidas na releitura após adquirir o lock:

- conversa ativa, sem finalização, em etapa 1–17 e a 18 somente para unidade sem link não terminal;
- primeiro envio: `followup_stage = 0` (`NULL` equivale a zero); segundo: stage 1
  com recibo do primeiro correspondente ao último bot e ao `followup_last_sent_at`;
- última mensagem da conversa é do bot, confirmada como `sent`, com pelo menos
  sete horas, e `last_interaction_at` corresponde a essa mensagem;
- última mensagem do cliente tem menos de 23h59, reservando um minuto da janela
  de 24 horas; não existe mensagem do cliente com horário igual ou posterior ao bot;
- unidade adimplente, destinatário e números da unidade presentes;
- menos de 12 turnos sem avanço, sem bloqueio persistido ou flood no banco;
- nenhuma fila `pending`/`processing` do par cliente/unidade, inclusive sem vínculo;
- nenhum recibo que já cubra a âncora, nem retomada aberta com fila pendente.
  No segundo, a âncora é o primeiro follow-up, sem encadear um terceiro envio.

Exemplo: bot há 8 horas e cliente há 25 horas não permitem envio; bot há 8 horas
e cliente há 9 horas permitem, se os demais critérios forem atendidos.
O relógio de elegibilidade vem do PostgreSQL. Os limites de etapa e de tempo
são regras do código/SQL, não novas variáveis de ambiente.

O primeiro sucesso persiste histórico, recibo e stage 1 no mesmo commit. Após
outras 7h sem resposta, contadas desse envio, a segunda mensagem persiste histórico,
recibo, stage 2 e encerramento no mesmo commit. Mantém a etapa de origem e não
gera bloqueio de 30 dias. Sem janela de envio, não envia nem encerra silenciosamente.
As duas camadas incluem a etapa 8. Marcações legadas sem recibo não geram despedida.
Uma confirmação da Meta seguida de
falha no commit local ainda pode resultar em duplicidade no retry; o worker
registra `followup_commit_falhou` como crítico.

### Retomada pelo flow

Depois do segundo envio confirmado, o atendimento está encerrado. `valida_banco`
abre nova conversa, sem etapa persistida e com stage zero; o fluxo inicial pede
o nome sem prefixo de retorno. Uma leitura da conversa antiga antes do encerramento
é recusada na releitura sob lock e reagendada sem consumir retry.

No flow, o contexto é relido sob lock. `transacoes/retorno_followup.py` registra
um checkpoint e reutiliza `valida_historico.py` para os dados da etapa, sem
calcular outra saudação de três horas. `retomada_followup.py` chama o `flow_sender`
normal com o prefixo `Bom te ver novamente, <nome> ☺️`. Na etapa 1, omite o nome
antigo; um nome válido na reação é salvo e permite avançar para a 2.

Os resolvers preservam seus validadores e prioridades: resposta válida avança;
mídia, financeiro e reforço recebem os tratamentos já existentes naquela etapa;
contexto inválido genérico usa `repeticao_followup.py` para a pergunta neutra.
A triagem continua aceitando somente as opções canônicas, sem novos tratamentos.
Botões, rodapés e participante são preservados. O prefixo aparece uma vez no
envio e no histórico, inclusive nas mensagens com cabeçalho.

A persistência normal aplica os efeitos, transições e encerramentos cabíveis.
Sem avanço, a primeira reação não incrementa `turnos_sem_avanco`; com transição,
o contador é zerado normalmente. `concluir_retomada` verifica a etapa resultante
e zera `followup_stage`, mantendo `followup_last_sent_at` como auditoria.
Histórico, efeitos, checkpoint, eventual encerramento e fila `sent` são
confirmados **na mesma transação**, sem commit intermediário. Falha reverte todos
esses efeitos. Cache de bloqueio só é publicado após o commit.

Replay de uma resposta já concluída reutiliza seu destino gravado, sem enviar,
reinterpretar a reação, refazer efeitos ou zerar um ciclo posterior. Respostas
da versão antiga continuam recuperáveis, mesmo que tenham repetido a etapa.

Na etapa 8, qualquer reação leva à 9 pelo evento `cliente_retornou`, sem repetir
a 8 nem interpretar a reação como resposta à 9. O histórico do cliente e o
checkpoint mantêm a origem 8; a resposta registra o destino 9.
Stage positivo legado nas etapas 20–23 também usa a validação normal, embora
essas etapas continuem inelegíveis para novos lembretes. A etapa 24 é terminal.

### Operação e logs

`SIGTERM`/`SIGINT` sinalizam parada e interrompem a espera entre lotes; uma
candidata já em andamento passa pela limpeza da conexão e do lock. Falhas de
consulta usam espera exponencial de 5 até 300 segundos. A unit usa
`Restart=on-failure`, `RestartSec=5s` e `TimeoutStopSec=100s`.

`followup_iniciado` informa a configuração. `followup_despacho` antecede a chamada
externa, e `followup_confirmado` confirma a persistência local. Não há log INFO a
cada varredura vazia; ausência de despachos não comprova falha. Para consultar
candidatas sem envio, use o [diagnóstico](../utilitarios/README.md#diagnóstico-de-follow-up).

Deploy: preparar banco e código, reiniciar flow compatível, então iniciar follow-up.
Rollback: parar o proativo primeiro e manter flow compatível enquanto houver stage
positivo ou retomadas pendentes. Desligar o serviço não limpa esses registros.
Os comandos completos ficam na [rotina de deploy](../regras_deploy/rotina_deploy.md)
e no [guia de ativação](../deploy/README.md#ativação-do-follow-up).

## Worker de consumo Meta

`python -m workers.worker_consumo_meta.iniciar_worker_consumo_meta` inicia o
sincronizador de analytics. Ativar com `CONSUMO_META_ENABLED=True` após a migração.
Consulta o mês atual por hora, meses pendentes diariamente e consolida somente
no dia 25 previsto, comparando a leitura anterior de mês completo. Falha/divergência
prorroga a decisão por um mês; `consolidado` encerra coletas automáticas.

O ciclo usa advisory lock próprio de sessão, HTTP fora de transação, agenda
persistida por unidade/mês e upsert protegido de leituras antigas. Não altera
locks, retries ou regras do atendimento, follow-up e Funil. Falhas preservam
totais e última coleta válida. Detalhes em [deploy](../deploy/consumo_mensal_meta.md).

## Reserva com e sem plataforma

A configuração atual de `unidade.link_agendamento` decide a saída da triagem: com link, 17 → 20; sem link, 17 → 18 (preferência de turno) → 19 (contato comercial). A satisfação converge em 21 → 22 → 23 → 24, com salto 22 → 24 na recusa de comentário. As etapas 1–17 conservam suas regras.

`conversa.turno` aceita NULL, manha, tarde ou noite e é salvo somente na transação de 18 → 19. É preferência, não confirmação de agendamento. Qualquer texto posterior na 19 apresenta a nota da 21; não é interpretado como nota nessa mesma interação. Mídia repete a orientação da 19.

O Funil exige 20–24 com link ou 19/21–24 sem link, considerando a configuração vigente na seleção, no claim e no snapshot. Preservar recibo de sucesso se o CRM já aceitou. O snapshot e o painel incluem turno da própria conversa, quando preenchido.

Follow-up proativo: 1–17 em ambas as rotas e 18 somente sem link; a 19 e a 20 não recebem novos lembretes. São preservadas as duas camadas de sete horas, os recibos, o encerramento no segundo lembrete e as guardas existentes. A reação ao primeiro segue a validação normal: um turno válido na 18 avança para 19 e é persistido. Contexto inválido genérico repete; tratamentos específicos continuam prioritários. Retomadas legadas são remapeadas por significado; a exceção 8 → 9 permanece.

Instalação existente exige migração própria: IDs antigos 18/19/20/21/22 tornam-se 20/21/22/23/24. Não executar setup ou seeds no banco de produção nem reaplicar migrações históricas. Preservar o Consumo Meta, seus fusos, worker, relatórios e PDFs, a compatibilidade PyWa 4.5.0, a exceção universal de idade 90+, o comentário livre e a despedida por participante.


## Worker de consulta FireAds

`worker_consulta_dash` executa somente as solicitações persistidas de novas
conversas. Não envia WhatsApp, não altera etapas e não escreve no dashboard.
O flow confirma a pendência e o reagendamento sem consumo de retry; depois aplica
o resultado completo uma única vez. HTTP ocorre no processo separado, com reserva
PostgreSQL e sem transação aberta. Ver [operação e recuperação](../docs/valida_dados_parciais_fireads.md).
````

## Passo 25: `PADROES_DE_ARQUITETURA.md`

Documentar a nova instância e as fronteiras de persistência e integração.

````markdown
# Padrões de arquitetura do Chatbot

## Finalidade

Este documento define onde cada responsabilidade deve ser implementada e quais
dependências são permitidas no projeto.

Antes de alterar código, leia também
[`REGRAS_DE_NEGOCIO.md`](REGRAS_DE_NEGOCIO.md). Os documentos possuem papéis
diferentes:

- `REGRAS_DE_NEGOCIO.md` define o comportamento esperado do sistema;
- `PADROES_DE_ARQUITETURA.md` define a organização e as fronteiras do código.

Uma reorganização nunca pode alterar silenciosamente uma regra de negócio. Caso
uma necessidade não se encaixe neste documento, a exceção deve ser discutida e
documentada antes da implementação.

## Princípios gerais

1. Cada módulo deve possuir uma responsabilidade principal clara.
2. Fluxo de negócio, persistência e integração externa não devem ser misturados.
3. Funções de baixo nível não devem controlar transações de alto nível.
4. O código deve depender de camadas mais internas, nunca do ponto de entrada.
5. Comportamentos críticos devem possuir testes em `tests/`.
6. Refatorações estruturais devem preservar entradas, saídas, logs relevantes e
   efeitos persistidos.
7. Não criar abstrações apenas para movimentar código; cada pasta deve representar
   uma fronteira real.

## Modelo de execução da V1 e evolução para a V2

Na V1, a implantação mantém uma instância do `worker_flow`, uma do `worker_funil`
e, após a migração e ativação específica, uma do `worker_followup`, além do webhook.
Cada serviço possui seu próprio ciclo de vida.

"Uma única instância ativa na V1" não deve ser confundida com a regra "um worker
por conversa". A primeira é uma decisão operacional desta versão; a segunda é
uma proteção que continuará válida mesmo quando existirem vários workers no
sistema: dois workers nunca poderão processar simultaneamente a mesma conversa.

Processamento paralelo permitido:

```text
Worker 1 -> conversa do cliente A
Worker 2 -> conversa do cliente B
```

Processamento que deverá continuar bloqueado:

```text
Worker 1 -> conversa do cliente A
Worker 2 -> conversa do cliente A ao mesmo tempo
```

Assim, vários workers poderão atender clientes diferentes em paralelo, mas cada
conversa ficará sob responsabilidade de apenas um worker por vez.

Embora a V1 execute apenas uma instância de cada worker, seus ciclos preservam as
proteções necessárias para concorrência e recuperação:

- dequeue atômico com `FOR UPDATE SKIP LOCKED`;
- exclusão mútua por conversa com `lock_version`;
- ordenação de mensagens anteriores ainda abertas;
- timeout e retomada de mensagens abandonadas em `processing`;
- idempotência pelo histórico vinculado à mensagem da fila;
- checkpoints, commits, rollbacks e fechamento da conexão por ciclo;
- `sent` somente depois da persistência da resposta do bot.

O objetivo arquitetural da V2 será permitir múltiplas instâncias de worker para
atender maior volume sem descartar essas garantias. Cada instância deverá
reutilizar os mesmos contratos de ordenação, lock, retry, idempotência e
recuperação estabelecidos na V1.

A forma de implementação da V2 permanece aberta. Classe, processos, containers,
threads ou um controlador dedicado são opções técnicas, não requisitos por si
só. A escolha deverá ser guiada por testes de concorrência, capacidade do banco,
observabilidade, desligamento gracioso e demanda real de produção.

## Mapa de responsabilidades

```text
callback/webhook  -> entrada HTTP e enfileiramento
callback/monitoramento -> login e autorização do painel por unidade
workers           -> processamento assíncrono e fluxo da conversa
core/repositories -> SQL e persistência
core/database     -> conexão, DDL e preparação do banco
core/cache        -> Redis, fallback e autocura detectável
core/integrations -> comunicação com serviços externos
core/triagem      -> catálogo puro compartilhado de perguntas
core/validacoes   -> validação pura compartilhada de e-mail e domínio de suporte por idade
utilitarios       -> diagnóstico, monitoramento e manutenção manuais
tests             -> testes, mocks, fakes e contratos
```

Direção esperada das dependências:

```text
webhook ────────┐
monitoramento ──┤──> core/repositories
worker ────────┤──> core/cache
admin ─────────┤──> core/integrations
utilitários ───┘

core nunca importa webhook ou worker
```

## Documentação por camada

O [`README.md`](README.md) da raiz é o portal da documentação. Cada README local
explica somente a responsabilidade e os contratos da sua camada:

- [`callback/README.md`](callback/README.md): aplicativos Django, webhook e estrutura do monitoramento;
- [`core/README.md`](core/README.md): mapa dos recursos compartilhados;
- [`workers/README.md`](workers/README.md): ciclo, checkpoints e recuperação;
- [`tests/README.md`](tests/README.md): estratégia e execução dos testes;
- [`core/cache/README.md`](core/cache/README.md): Redis, fallback e autocura;
- [`core/database/README.md`](core/database/README.md): conexão, DDL e setup;
- [`core/repositories/README.md`](core/repositories/README.md): contratos SQL;
- [`core/integrations/README.md`](core/integrations/README.md): integrações externas;
- [`core/integrations/whatsapp/README.md`](core/integrations/whatsapp/README.md):
  organização da integração Meta/PyWa.
- [`core/integrations/funil/README.md`](core/integrations/funil/README.md):
  envio de oportunidades e contrato do lead;
- [`utilitarios/README.md`](utilitarios/README.md): relatórios e comandos manuais;
- [`deploy/README.md`](deploy/README.md): arquivos dos serviços e migrações.

Os planos de evolução ficam separados em `docs/` e não descrevem, por si só,
funcionalidades implementadas.

READMEs locais não devem copiar regras completas. Eles apontam para
`REGRAS_DE_NEGOCIO.md` quando uma decisão de produto precisa ser interpretada e
para este documento quando a dúvida é sobre organização do código.

## `core`

`core` contém recursos compartilhados pelos diferentes pontos de entrada do
sistema. Um módulo pertence a `core` quando pode ser utilizado por webhook,
worker, Admin ou scripts sem depender do fluxo específico de nenhum deles.

Responsabilidades permitidas:

- conexão e preparação do banco;
- funções SQL de repositório;
- cache e fallback;
- integrações externas;
- validações puras reutilizadas e catálogos neutros de domínio;
- configuração por ambiente;
- configuração de logging;
- exceções compartilhadas.

Responsabilidades que não pertencem a `core`:

- laço infinito do worker;
- resposta HTTP do webhook;
- decisão de rota específica de uma etapa do worker;
- controle completo de uma transação de negócio;
- mocks ou dados exclusivos de teste.

## SQL e repositórios

### Localização

Consultas e alterações de dados da aplicação devem ficar em
`core/repositories/`.

Os repositórios são agrupados por domínio e entidade:

- `atendimento/`: clientes, conversas, dependentes, fila e histórico;
- `fluxo/`: políticas, transições, respostas da triagem e contextos por etapa;
- `unidades/`: consultas de unidade e controle de versão do cache;
- `seguranca/`: regra de turno e persistência de bloqueios Meta;
- `funil/`: configuração da integração por unidade e estado dos envios;
- `monitoramento/`: vínculo e autorização de recursos por conta/unidade.

Não agrupe operações apenas pelo verbo SQL. Uma mesma entidade pode concentrar
consultas, inserções, atualizações e exclusões relacionadas ao seu contrato.

DDL, criação de funções PostgreSQL e preparação de ambiente pertencem a
`core/database/deploy_database/`; migrações incrementais versionadas ficam em
`deploy/migrations/`. Nenhuma das duas áreas é repositório de runtime.

Os relatórios manuais em `utilitarios/reports_functions/` possuem consultas
analíticas próprias, somente leitura. Essa fronteira não autoriza mover SQL de
persistência do chatbot para os utilitários nem importá-los nos serviços.

### Contrato das funções SQL

Uma função de repositório deve:

- receber `cursor` como argumento;
- executar SQL parametrizado;
- retornar dados ou quantidade de linhas afetadas;
- validar invariantes persistidas quando necessário;
- registrar logs técnicos sem dados sensíveis completos.

Uma função de repositório não deve:

- abrir conexão com `get_conn`;
- executar `commit`, `rollback` ou `close`;
- decidir retry do worker;
- retornar `JsonResponse`;
- chamar Meta, PyWa ou Redis;
- esconder falha de persistência necessária para a regra de negócio.

Evite SQL em worker, webhook, integração ou cache quando a operação representa
persistência da aplicação. O ponto de entrada chama o repositório apropriado.

## Conexões e transações

O arquivo que conhece o fluxo completo é o dono da transação.

### Workers

Cada worker controla a conexão e os commits de seu próprio domínio:

```text
workers/worker_flow/response_flow/flow_worker.py
workers/worker_funil/funil_worker.py
workers/worker_followup/followup_worker.py
```

Repositórios e funções auxiliares recebem o cursor aberto pelo orquestrador.
Commits intermediários devem representar estados recuperáveis documentados nas
regras de negócio. Um worker não reutiliza a conexão do outro. Flow e follow-up
disputam o mesmo lock de conversa, com versão e expiração; somente seu proprietário
pode persistir o resultado. O Funil mantém sua reserva independente por envio.

### Webhook

A transação de enfileiramento pertence a:

```text
callback/webhook/services/post_flow.py
```

As transações independentes dos controles de abuso pertencem aos serviços:

```text
callback/webhook/services/flood_guard.py
callback/webhook/services/bloqueio_meta_guard.py
```

O módulo `populating_fila_mensagens.py` prepara, valida e insere usando o cursor
recebido, mas não abre ou finaliza conexão.

### Scripts e Admin

Scripts operacionais podem controlar a própria conexão quando são o ponto de
entrada completo da operação. No Django Admin, preserve o comportamento
Meta-first definido nas regras de negócio e utilize o gerenciamento transacional
do Django ou uma fronteira explícita quando necessário.

## Webhook

`callback/webhook` é a fronteira HTTP de recebimento dos eventos da Meta.

Responsabilidades:

- validar método, `Content-Type`, tamanho e assinatura;
- interpretar o payload da Meta;
- aplicar anti-flood;
- verificar se a mensagem pode entrar no turno;
- inserir a mensagem válida na fila;
- devolver a resposta HTTP apropriada;
- oferecer operações administrativas do Django relacionadas ao webhook.

O webhook não deve:

- responder a etapa da conversa;
- executar o fluxo do bot;
- retirar mensagens da fila;
- avançar etapa;
- manter textos de resposta do bot;
- importar PyWa diretamente.

Serviços HTTP pequenos ficam em `callback/webhook/services/`. `views.py` deve ser
uma borda fina e delegar o fluxo para esses serviços.

## Monitoramento

`callback/monitoramento` é um aplicativo Django próprio, registrado em
`INSTALLED_APPS`. Reúne login, autorização e interface do painel por
unidade, sem participar do recebimento de eventos da Meta. Compartilha o projeto
Django, a autenticação e o banco existentes. Login, conversas, relatórios e
exportação de contatos pertencem ao mesmo aplicativo.

`callback/monitoramento/monitoramento_guard.py` valida a sessão Django e usa um
cursor do Django para a leitura autoritativa em
`core/repositories/monitoramento/acessos.py`.
O repositório recebe o cursor, não abre conexão nem importa Django. Não há cache
do vínculo: ele é lido de `unidade.id_usuario_monitoramento`, sem tabela
intermediária. O login valida o vínculo antes de criar a sessão e ao mostrar a
confirmação de acesso. Cada rota de dados chama o guard e aplica explicitamente
o `id_unidade` retornado em todas as consultas.

`forms.py` estende a autenticação nativa do Django, sem SQL próprio para senhas.
`views.py` controla login, logout por POST, respostas HTML, APIs GET e CSV;
`urls.py` publica `/`, `/login/`, `/sair/`, `/dados/...` e `/contatos.csv`.
`services.py` coordena as leituras e `apresentacao.py` mantém transformações
puras. Os contratos completos estão no
[README dos aplicativos](callback/README.md#cadastro-e-autorização-do-monitoramento).

Templates e arquivos estáticos do painel pertencem, respectivamente, a
`callback/monitoramento/templates/monitoramento/` e
`callback/monitoramento/static/monitoramento/`. CSS, JavaScript e logo são locais,
sem recursos de terceiros na página. SQL de runtime continua em
`core/repositories/monitoramento/`, inclusive as leituras em `painel.py`; testes
continuam em `tests/`. O modelo `Unidade` e seu Admin permanecem em
`callback/webhook`.

A atualização automática é iniciada pelo JavaScript da página e gera requisições
GET comuns: 10 segundos para conversas e 30 segundos para relatórios. Ela não é
um worker, orquestrador ou serviço systemd. O mesmo processo web atende webhook,
Admin e monitoramento; o navegador só consulta a seção ativa e visível.

## Workers

`workers` contém processamento assíncrono e decisões do fluxo da conversa.

### `worker_flow`

Responsabilidades:

- selecionar mensagem da fila;
- validar cliente, unidade e conversa;
- adquirir e liberar lock da conversa;
- reconhecer estados intermediários e retries;
- validar histórico;
- rotear resposta ou tratamento;
- persistir resposta e contexto;
- reconhecer a reação com stage positivo ou marcador anterior e repetir a etapa
  sem resolver transições, zerando o stage na persistência final;
- marcar a fila como `sent` somente após a persistência necessária.

### `worker_followup`

Seleciona conversas elegíveis por inatividade no PostgreSQL, sem consumir a fila.
Cada candidata tem conexão, lock de conversa e transação próprios. O envio usa
`core/integrations/whatsapp`; elegibilidade, recibos e fencing ficam em
`core/repositories/atendimento/followup.py`.

A releitura após adquirir o lock verifica as etapas 1–17 e a 18 somente para unidade sem link, sete horas sem resposta
ao bot e a janela da última mensagem do cliente. Confirmação do lembrete, histórico
e stage 1 são persistidos juntos. Uma falha individual não interrompe o lote.

O retorno pertence ao `worker_flow`: `transacoes/retorno_followup.py` prepara o
checkpoint da reação e persiste a repetição, sem controlar commits.
`response_flow/repeticao_followup.py` seleciona os senders da etapa sem executar
validadores, transições ou efeitos de negócio. O stage só é zerado junto da
persistência da repetição confirmada. Essa exceção reativa está documentada nas
regras de negócio e não altera o fluxo normal de stage zero.

### `worker_funil`

Responsabilidades:

- materializar conversas cuja política de etapa é `elegivel_funil`;
- reservar um `funil_envios` com `FOR UPDATE SKIP LOCKED`;
- obter o snapshot persistido do lead;
- encerrar a transação de leitura antes do HTTP;
- chamar `core/integrations/funil` uma oportunidade por vez;
- reagendar falha externa sem interromper os demais leads;
- confirmar `lead_no_funil` e `funil_envios = sent` no mesmo commit local;
- recuperar reservas abandonadas por lease.

`funil_worker.py` é o processo duradouro: executa ciclos isolados, aguarda o
intervalo `FUNIL_INTERVALO_SEGUNDOS` (padrão: 1.800 segundos, ou 30 minutos)
entre ciclos bem-sucedidos e recupera indisponibilidade operacional do
banco com espera linear de 5 em 5 segundos, limitada a 60. O arquivo
`iniciar_worker_funil.py` forma o laço supervisor externo; somente uma falha
crítica que escape do worker chega nele, provocando a recriação do worker após
5 segundos fixos. Esse padrão evita nomes `flow_worker.py` duplicados e mantém
recuperação operacional separada da supervisão do processo.

SQL permanece em `core/repositories/funil`. Payload, URL e interpretação da API
permanecem em `core/integrations/funil`. O worker é o único dono do retry e da
fronteira transacional.

`worker_funil` não importa `worker_flow`, não usa lock de conversa e não acessa
Redis. As duas áreas compartilham apenas recursos verdadeiramente centrais,
como conexão, configuração, logging e o tratamento genérico de reconexão em
`workers/tratamento_erros_externos`.

Não tente manter uma transação PostgreSQL aberta durante o POST. PostgreSQL e
Funil não formam uma transação distribuída; a pequena janela entre sucesso
externo e commit local deve ser documentada e reconciliável.

### `response_flow`

Contém orquestração de respostas:

- `flow_worker.py`: ciclo e transações;
- `flow_sender.py`: preservação da idempotência e seleção do resolver da etapa
  atual;
- `etapas/resolver_etapa<n>.py`: validação da etapa atual e encaminhamento para o
  destino autorizado;
- `etapas/validadores_universais/`: validações reutilizáveis entre etapas;
- `etapas/validadores_contexto/`: validações específicas da pergunta atual;
- `transicoes/contexto_transicao.py`: montagem explícita da fotografia de
  origem e destinos permitidos no contexto histórico;
- `transicoes/resolver_transicao.py`: resolução de
  `origem + evento -> destino`;

Na pasta irmã `workers/worker_flow/transacoes/` ficam
`movimento_conversa.py` (inicialização, transição ou permanência) e
`efeitos_transicao.py` (efeitos de banco de cada aresta autorizada).

Esses arquivos podem escolher qual integração chamar, mas não devem criar cliente
PyWa, montar `Button` ou manter textos de saída.

A navegação não utiliza `id_etapa + 1`. O worker identifica o evento, consulta
as transições permitidas para a origem e transporta a decisão no contexto. A
persistência final revalida a mesma aresta no PostgreSQL antes do commit.

Tratamentos não produzem evento de transição e permanecem na etapa atual.

Contextos específicos de idade e e-mail são carregados pelos repositórios. Os
resolvers aplicam as políticas da unidade, e os efeitos transacionais persistem
a decisão. A validação de formato de e-mail é pura e compartilhada em
`core/validacoes/email.py`; não depende de um resolver ou do Funil.

O prefixo de retorno após três horas é preparado com o histórico persistido e
aplicado pelo `flow_sender` somente depois da barreira de idempotência, no escopo
do resolver corrente. Não muda o destino nem autoriza um novo envio no replay.

### Escolha entre validador universal e contextual

Um validador só pertence a `validadores_universais` quando:

- é usado por mais de uma etapa;
- possui o mesmo significado em todas elas;
- apenas identifica tratamento/permanência ou permite seguir o fluxo;
- não escolhe entre diferentes arestas do mapa.

Mídia, o classificador-base de dúvida sobre reforço escolar, financeiro e nome
atendem a esse contrato. O resultado-base deles não muda de significado
conforme a etapa que os chama.

Quando o vocabulário universal também puder representar uma resposta legítima
de uma etapa específica, a desambiguação deverá ficar em
`validadores_contexto/` e delegar ao classificador universal depois de aplicar
somente a exceção local. Esse adaptador não envia mensagem, não acessa banco,
não altera contexto e não modifica o classificador compartilhado. A etapa 4
usa esse padrão para distinguir dúvida sobre reforço escolar de uma declaração
de profissão ou vínculo de trabalho com banca, cursinho, supletivo ou reforço.

Um validador pertence a `validadores_contexto` quando a resposta produz eventos
próprios daquela etapa, especialmente quando pode pular ou retroceder no mapa.
Mesmo que duas etapas reconheçam textos idênticos, cada uma mantém seu
validador quando devolve eventos diferentes:

```text
validar_etapa7("Quero agendar") -> oferta_aceita
validar_etapa9("Quero agendar") -> retorno_confirmado
```

Nesse caso, a semelhança da gramática não transforma o validador em universal.
O contrato relevante é o evento de negócio produzido para a origem atual.

O resolver deve receber diretamente esse evento:

```python
evento_transicao = validar_etapa7(texto_cliente)

destinos_esperados = _destinos_esperados_por_evento(evento_transicao)
etapa_destino = resolver_destino_transicao(
    contexto_historico,
    evento_transicao,
    destinos_esperados=destinos_esperados,
)
```

Não criar uma decisão neutra intermediária para depois traduzi-la em evento no
resolver. A interpretação de uma resposta que escolhe arestas pertence ao
validador contextual da própria etapa.

Todo resolver de etapa deve marcar explicitamente a fronteira entre validação e
resolução do destino. O marcador fica depois de todos os retornos de tratamento
e imediatamente antes da consulta ao mapa:

```python
# VALIDANDO DESTINO(S)
# A resposta já passou pelos tratamentos; agora o mapa autoriza a aresta.
etapa_destino = resolver_destino_transicao(...)
```

Antes dessa fronteira, o resolver apenas valida a resposta e pode permanecer na
etapa atual. Depois dela, a resposta já é válida: o código resolve o destino,
chama o sender correspondente e anexa a transição ao contexto de envio.

Quando o resolver produz somente um evento e possui um único destino possível,
o conjunto esperado deve ficar explícito na chamada:

```python
etapa_destino = resolver_destino_transicao(
    contexto_historico,
    EVENTO_RESPOSTA_VALIDA,
    destinos_esperados={ETAPA_DESTINO},
)
```

Quando a mesma origem produz múltiplos eventos e destinos, o resolver deve
centralizar essa correspondência em
`_destinos_esperados_por_evento(evento_transicao)`. A função interna não é
necessária em fluxos lineares, pois apenas esconderia uma constante sem
representar uma decisão real.

### Constantes e efeitos de etapa

Toda constante de estado deve mostrar o número persistido e o significado:

```python
ETAPA_1_NOME_CLIENTE = 1
ETAPA_2_DESTINO_ATENDIMENTO = 2
ETAPA_3_CONFIRMACAO_DESTINO = 3
ETAPA_4_PROFISSAO = 4
ETAPA_5_NOME_DEPENDENTE = 5
ETAPA_6_IDADE_ALUNO = 6
```

Não usar números mágicos como `etapa_origem == 2` e não omitir o número no nome
da constante. Esse padrão permite localizar a etapa sem perder seu significado.

Em `transacoes/efeitos_transicao.py`, os efeitos devem ser agrupados primeiro
pela etapa de origem e depois pelo evento:

```python
# ETAPA 2
if etapa_origem == ETAPA_2_DESTINO_ATENDIMENTO:
    if evento == EVENTO_DESTINO_ATENDIMENTO_DEFINIDO:
        # 2 -> 3: persiste a escolha inicial antes da confirmação.

# ETAPA 3
if etapa_origem == ETAPA_3_CONFIRMACAO_DESTINO:
    if evento == EVENTO_DESTINO_ATENDIMENTO_CONFIRMADO:
        # 3 -> 4: aplica o status final absoluto e sempre pede a profissão.

# ETAPA 4
if etapa_origem == ETAPA_4_PROFISSAO:
    if evento == EVENTO_PROFISSAO_DEPENDENTE_VALIDA:
        # 4 -> 5

    if evento == EVENTO_PROFISSAO_TITULAR_VALIDA:
        # 4 -> 6
```

Cada comentário de evento deve mostrar `origem -> destino`. A tabela
`etapa_transicao` continua sendo a fonte de verdade, e o código apenas torna
visíveis os efeitos de cada aresta autorizada.

Confirmação e profissão não podem transformar ausência de estado em titular.
Resolvers, replay e efeitos dessas pontes exigem `status_dependente` booleano;
um valor ausente ou inválido falha para retry em vez de usar `bool(None)`.

### Tratamento de erros

`workers/tratamento_erros_externos/` concentra decisões de retry, exclusão e
tratamentos específicos de falhas externas. Repositórios executam a alteração
solicitada, mas não escolhem a política de retry.

## Integrações externas

Toda integração externa compartilhada pertence a `core/integrations/<serviço>/`.

As integrações implementadas são `whatsapp` e `funil`. A pasta `google/` não
possui integração de runtime implementada.

Uma integração deve:

- encapsular a biblioteca ou API externa;
- receber dados já validados pelo chamador;
- converter retorno externo para um contrato simples da aplicação;
- traduzir falhas quando houver uma exceção de domínio apropriada;
- não controlar banco, fila, retry ou transação.

## WhatsApp e PyWa

Estrutura oficial:

```text
core/integrations/whatsapp/
├── exceptions.py
├── messages/
├── pywa_functions/
└── tools/
```

### `messages`

Armazena o catálogo de conteúdo enviado ao WhatsApp:

- textos;
- títulos de botão;
- callbacks;
- templates;
- funções puras de formatação ou seleção de template.

Não pode conter:

- `import pywa`;
- envio para a Meta;
- banco ou Redis;
- logging de integração;
- decisão de retry, lock ou etapa persistida.

Novos textos não devem ser escritos diretamente no worker ou em
`pywa_functions`. Organize-os por responsabilidade, como
`etapa<n>_messages.py` e `tratamentos_universais.py`.

Componentes compartilhados por um grupo de etapas podem possuir um helper
próprio. `triagem_componentes.py`, por exemplo, atende exclusivamente às etapas
12 a 17 e centraliza botões e rodapé, sem conter envio ou decisão de fluxo.

Quando o mesmo conteúdo de negócio for consumido por canais diferentes, ele
deve possuir uma fonte neutra fora das integrações. A triagem por faixa etária
usa `core/triagem/perguntas.py` como catálogo único das etapas 12 a 17. Os
arquivos de `messages` selecionam a pergunta para o WhatsApp e a integração do
Funil reutiliza exatamente o mesmo catálogo; nenhum dos dois deve manter uma
cópia independente dos textos ou da fronteira infantil/adulta.

A elegibilidade por idade continua na regra de negócio que antecede a triagem.
O catálogo apenas classifica uma idade persistida válida como infantil (`< 18`)
ou adulta (`>= 18`) e monta o texto. Consulta ao banco, BPA, transição e envio
não pertencem a esse módulo.

Componentes visuais usados por diferentes etapas pertencem a
`componentes_compartilhados.py`. Esse helper pode armazenar textos comuns e
funções puras de composição. A saudação de retorno recebe nome, etapa e horários
já carregados pelo chamador; não consulta histórico, não altera conversa e não
escolhe evento ou destino. Usar esses valores para formatar o texto não transfere
ao helper a decisão de fluxo.

Na PyWa utilizada pelo projeto, `header` e `footer` só são enviados quando a
mensagem possui botões e se torna interativa. Em mensagens de texto simples,
esses argumentos são ignorados.

O WhatsApp aplica estilos diferentes ao `header` nativo conforme o tipo da
mensagem interativa e não oferece controle do tamanho da fonte. Por isso, os
cabeçalhos textuais do fluxo — etapas 11 a 17 e 21 a 23 — são incorporados ao
início do corpo, em negrito, por `montar_texto_com_cabecalho`. Os senders não
devem passar `header` para a Meta. Novos cabeçalhos textuais devem reutilizar
esse helper para manter a apresentação uniforme entre listas e botões.

Rodapés continuam permitidos nos pontos definidos pelo produto e devem aparecer
em itálico. Como o Markdown não produz efeito no campo `footer` de uma mensagem
interativa, o projeto incorpora o rodapé ao próprio corpo usando `_texto_`,
mesmo quando a mensagem possui botões. O sender não deve passar `footer` para a
Meta nesses casos.

### `pywa_functions`

Concentra a criação do cliente PyWa e o transporte de mensagens do atendimento.
As operações compartilhadas de bloqueio/desbloqueio atualmente ficam em
`tools/usuarios.py` e reutilizam a mesma fábrica de cliente.

Responsabilidades:

- criar o cliente `WhatsApp`;
- criar tipos PyWa, como `Button`;
- chamar `send_message`;
- extrair IDs retornados;
- produzir o contexto de envio esperado pelo worker;
- converter falhas de envio para `ErroEnvioMeta` quando aplicável.

Não pode conter:

- SQL;
- Redis;
- `commit`, `rollback` ou `close`;
- decisão sobre limite de retry;
- mutação direta de conversa, histórico ou fila.

Quando várias etapas compartilham exatamente o mesmo contrato de transporte,
um sender-base pode centralizar apenas a mecânica comum. `triagem_base.py`
atende às etapas 12 a 17: monta os componentes PyWa, envia, extrai o ID da
mensagem e produz o contexto de envio. Os senders públicos de cada etapa
continuam responsáveis pelo conteúdo e o helper-base não pode validar respostas,
produzir eventos ou escolher destinos.

Separação interna atual:

- `cliente.py`: criação e normalização do cliente;
- `resposta_envio.py`: normalização da confirmação e do ID de envio;
- `saudacao.py`: saudação inicial;
- `pywa_senders/etapa<n>.py`: envios normais e tratamentos da respectiva etapa;
- `pywa_senders/triagem_base.py`: transporte comum das seis perguntas.

`cliente.py` também mantém o escopo temporário do prefixo de retorno, restaurado
mesmo sob exceção. O texto enviado e o texto persistido devem permanecer iguais.

### `tools`

Dentro de uma integração, contém operações administrativas que pertencem ao
domínio daquela integração e são reutilizadas pelo Django Admin, como ativação
de número e inscrição do WABA.

Na estrutura atual há também primitivas compartilhadas: `usuarios.py` é usado
pelo webhook e Admin, e `config.py` pela fábrica de cliente. Portanto, essa pasta
não é exclusivamente administrativa. Essas primitivas não decidem retry,
admissão, persistência ou transações; tais decisões continuam nos chamadores.

Comandos iniciados conscientemente por uma pessoa apenas para diagnóstico,
monitoramento, manutenção ou probe pertencem à pasta `utilitarios`, não a
`core/integrations/<serviço>/tools`. Nenhum dos quatro pontos de entrada —
webhook, `worker_flow`, `worker_funil` e Django Admin — importa `utilitarios`.

Configuração operacional:

```text
core/integrations/whatsapp/tools/config.py
```

Esse arquivo fornece a configuração compartilhada da integração WhatsApp, mas os
valores vêm de `core/config_env.py` e das variáveis de ambiente. Ele não deve
armazenar token, WABA ID, phone number ID ou outro valor sensível diretamente no
código.

## Cache

`core/cache` concentra Redis, cache local e mecanismos de fallback.

Regras:

- banco continua sendo a fonte persistida da verdade;
- cache deve possuir fallback quando a regra de negócio exigir disponibilidade;
- falhas detectáveis de cache stale devem permitir reparo seguro;
- chaves devem ser normalizadas e centralizadas;
- cache não controla transações do banco;
- uma falha de Redis não deve ser silenciosamente tratada como dado válido;
- logs devem informar fallback e autocura sem expor dados completos.

`core/cache/runtime/` contém caches utilizados durante a execução normal.
Operações administrativas de reset devem permanecer separadas do caminho comum.

## Django Admin

O Admin é uma interface operacional, não uma segunda implementação das regras.

Regras:

- reutilizar funções de integração e repositório existentes;
- não duplicar chamadas PyWa;
- preservar operações Meta-first;
- se a Meta falhar, não confirmar alteração correspondente no banco ou Redis;
- manter tabelas de auditoria majoritariamente somente para leitura;
- ações permitidas devem seguir `REGRAS_DE_NEGOCIO.md`.

## Logging e exceções

- utilizar `logging`, não `print`, nos fluxos de runtime;
- obter logger por responsabilidade, como `worker.*`, `webhook.*` e
  `whatsapp.*`;
- utilizar `short_value` para dados identificadores nos logs;
- nunca registrar tokens, segredos, payloads completos ou credenciais;
- usar `logger.exception` quando o traceback é necessário;
- não capturar `Exception` apenas para ocultar erro sem fallback definido;
- exceções de integração devem carregar contexto mínimo útil, sem segredo.

`print` é aceitável em scripts de relatório executados manualmente e em saídas de
desenvolvimento já delimitadas.

## Configuração e segredos

- não adicionar novos tokens ou credenciais diretamente no código;
- usar `core/config_env.py` para leitura e validação de variáveis de ambiente;
- documentar apenas os nomes das variáveis, nunca seus valores secretos;
- manter `.env` fora do Git;
- IDs públicos e limites podem ser constantes quando não forem segredos;
- configurações de infraestrutura não devem alterar silenciosamente regras de
  negócio; políticas explícitas da unidade, como `idade_minima_suporte` e
  `email_obrigatorio`, são lidas e aplicadas pelos contextos e resolvers próprios;
- testes devem usar valores fictícios e nunca credenciais reais.

## Testes

Todo teste, mock, fake e payload exclusivo de teste deve ficar em `tests/`.

Estrutura atual:

```text
tests/
├── helpers.py
├── fixtures/
├── unit/
│   └── test_*.py
└── integration/
    └── test_followup_postgres.py
```

Regras:

- não criar testes em módulos de produção;
- não adicionar `Mock`, `MagicMock`, `patch` ou classes `Fake*` fora de `tests/`;
- testar comportamento e contratos, não somente linhas internas;
- falhas externas devem ser simuladas sem acessar Meta, Redis ou AWS reais;
- alterações de fluxo crítico devem cobrir sucesso, falha e retry;
- alterações estruturais devem possuir testes que impeçam regressão da
  organização quando isso for relevante;
- a suíte completa deve permanecer executável por descoberta.

A integração PostgreSQL exige `FOLLOWUP_TEST_DSN` apontando para loopback e um
banco descartável chamado `test_chatbot_followup`, sem schema `chatbot` prévio.
Sem essa variável, é pulada. Não usa as credenciais de produção do `.env`; Meta
continua simulada. Consulte o [guia de testes](tests/README.md#follow-up).

Comando padrão:

```powershell
python -m unittest discover -s tests -t . -p "test_*.py" -v
```

Fluxos críticos que não podem perder cobertura:

- A/B/C e primeira mensagem do turno;
- idempotência após resposta persistida;
- falha do banco após envio confirmado pela Meta;
- limite de retries e exclusão;
- ordenação e locks;
- retrocesso e salto de etapa;
- `last_message_from` semântico;
- fallback e autocura de cache;
- transações de worker e webhook;
- elegibilidade proativa, recibos, migração do legado e retorno sem avanço de etapa;
- intenção local antes dos bloqueios automáticos e desbloqueio administrativo
  Meta-first.

## Nomes e organização de arquivos

- arquivos e funções devem usar `snake_case`;
- nomes devem descrever responsabilidade, não detalhes passageiros;
- evitar arquivos genéricos como `utils.py` quando existe um domínio claro;
- uma função reutilizada deve morar na camada proprietária da responsabilidade;
- constantes de um domínio devem ficar próximas ao domínio;
- não criar pasta nova para apenas um arquivo sem perspectiva clara de fronteira;
- não criar arquivo que apenas reexporta outro sem necessidade real de
  compatibilidade.

## Imports e dependências

- preferir imports absolutos a partir da raiz do projeto;
- evitar import circular por meio de fronteiras claras, não por imports tardios
  espalhados;
- worker e webhook podem importar `core`;
- `core` não importa worker ou webhook;
- `messages` não importa `pywa_functions`;
- `pywa_functions` pode importar `messages`, cliente e exceções da integração;
- repositórios não importam integrações;
- testes podem importar qualquer módulo necessário para validar contratos.

## Anti-padrões proibidos

- SQL diretamente em `flow_worker.py` ou `post_flow.py`;
- `commit` dentro de `core/repositories`;
- texto de WhatsApp escrito dentro do worker;
- `send_message` fora de `pywa_functions`;
- regra de retry dentro de um sender;
- acesso ao Redis dentro de uma função PyWa;
- `JsonResponse` dentro de repositório;
- mock dentro de código de produção;
- duplicação de regra de negócio no Admin;
- fachada ou wrapper sem responsabilidade própria;
- captura silenciosa de erro que transforme falha em sucesso;
- refatoração estrutural misturada com mudança de comportamento sem testes e
  documentação explícita.

## Como decidir onde criar uma função

Use esta sequência:

1. Executa SQL da aplicação? `core/repositories`.
2. Abre ou prepara infraestrutura de banco? `core/database`.
3. Gerencia cache ou fallback de cache? `core/cache`.
4. Chama serviço externo compartilhado? `core/integrations/<serviço>`.
5. Envia mensagens com PyWa? `core/integrations/whatsapp/pywa_functions`;
   bloqueio/desbloqueio reutiliza `core/integrations/whatsapp/tools/usuarios.py`.
6. Define texto ou callback do WhatsApp? `messages`.
7. Trata HTTP da Meta? `callback/webhook`. Trata acesso ou interface do painel?
   `callback/monitoramento`.
8. Decide processamento assíncrono ou etapa? `workers`.
9. É comando humano de diagnóstico, monitoramento, manutenção ou probe?
   `utilitarios`.
10. Existe apenas para validar comportamento? `tests`.

Se a função responder positivamente a mais de uma pergunta, provavelmente deve
ser dividida em orquestração e operação de baixo nível.

## Checklist para alterações futuras

Antes de implementar:

1. Ler `REGRAS_DE_NEGOCIO.md` e este documento.
2. Identificar a camada proprietária da responsabilidade.
3. Mapear contratos, chamadores e estados intermediários afetados.
4. Confirmar que a mudança não duplica uma função existente.

Durante a implementação:

1. Manter transações no orquestrador correto.
2. Preservar logs e exceções relevantes.
3. Não misturar refatoração com nova regra de negócio.
4. Criar ou atualizar testes somente em `tests/`.

Depois da implementação:

```powershell
python -m unittest discover -s tests -t . -p "test_*.py" -v
python -m compileall core workers callback utilitarios tests
python callback/manage.py check
git diff --check
```

Também confira:

- imports antigos removidos;
- envios PyWa em `pywa_functions` e operações de usuários na primitiva compartilhada;
- textos de WhatsApp apenas em `messages`;
- SQL e transações nas camadas corretas;
- nenhum segredo novo no diff;
- nenhuma alteração não relacionada à tarefa.

## Atualização deste documento

Este documento deve ser atualizado quando:

- uma nova camada for criada;
- a propriedade de uma transação mudar;
- uma integração externa ganhar estrutura própria;
- uma exceção arquitetural deixar de ser temporária;
- um padrão recorrente for aprovado para uso futuro.

Mudanças neste documento não substituem testes nem alteram automaticamente as
regras de negócio.

## Reserva com e sem plataforma

A configuração atual de `unidade.link_agendamento` decide a saída da triagem: com link, 17 → 20; sem link, 17 → 18 (preferência de turno) → 19 (contato comercial). A satisfação converge em 21 → 22 → 23 → 24, com salto 22 → 24 na recusa de comentário. As etapas 1–17 conservam suas regras.

`conversa.turno` aceita NULL, manha, tarde ou noite e é salvo somente na transação de 18 → 19. É preferência, não confirmação de agendamento. Qualquer texto posterior na 19 apresenta a nota da 21; não é interpretado como nota nessa mesma interação. Mídia repete a orientação da 19.

O Funil exige 20–24 com link ou 19/21–24 sem link, considerando a configuração vigente na seleção, no claim e no snapshot. Preservar recibo de sucesso se o CRM já aceitou. O snapshot e o painel incluem turno da própria conversa, quando preenchido.

Follow-up proativo: 1–17 em ambas as rotas e 18 somente sem link; a 19 e a 20 não recebem novos lembretes. São preservadas as duas camadas de sete horas, os recibos, o encerramento no segundo lembrete e as guardas existentes. A reação ao primeiro segue a validação normal: um turno válido na 18 avança para 19 e é persistido. Contexto inválido genérico repete; tratamentos específicos continuam prioritários. Retomadas legadas são remapeadas por significado; a exceção 8 → 9 permanece.

Instalação existente exige migração própria: IDs antigos 18/19/20/21/22 tornam-se 20/21/22/23/24. Não executar setup ou seeds no banco de produção nem reaplicar migrações históricas. Preservar o Consumo Meta, seus fusos, worker, relatórios e PDFs, a compatibilidade PyWa 4.5.0, a exceção universal de idade 90+, o comentário livre e a despedida por participante.


## Consulta FireAds periódica

Após a migração específica, a V1 acrescenta uma instância do `worker_consulta_dash`.
Esse serviço lê solicitações duráveis e salva resultados completos. O flow mantém
a propriedade de importação, contexto, etapas e mensagens. A espera é confirmada
pelo orquestrador como checkpoint recuperável, nunca por commit no adaptador.
SQL de consulta/reserva fica em `core/repositories/fireads`; integração HTTP continua
em `core/integrations/fireads`; diagnóstico manual continua em `utilitarios`.
Não há tarefas HTTP auxiliares dentro do flow nem novas views.
````

## Passo 26: `tests/README.md`

Atualizar a execução e o alcance dos testes FireAds.

````markdown
# Testes do projeto

A atualização de 09/10/2026 tem cobertura para suspensão por `status_pagamento`
nos testes de consumo Meta, FireAds/Funil, follow-up e runtime do worker principal.
Inclui `FALSE`/`NULL`, preservação das pendências, reativação, reexecução da migração
de dequeue e separação da edição de personalização no Admin. Consulte
[`status_pagamento_e_admin.md`](../docs/status_pagamento_e_admin.md).

Esta pasta reúne testes unitários, de contrato e de integração SQL. Além do núcleo
transacional, ela cobre regras e utilitários já implementados:

- cenário completo de turno A/B/C;
- retry, requeue, ordem da fila e fencing por `lock_version`;
- persistência idempotente, avanço e não avanço de etapa;
- checkpoints, commits, rollback e conclusão da fila no worker;
- suporte ao idoso e obrigatoriedade do e-mail;
- validação da oferta, início da triagem, profissão e saudação após inatividade;
- experiência Supera gratuita, coerência titular/dependente, aceite de reserva com
  respostas antigas e preservação do texto em replay e follow-up;
- montagem dos relatórios semanais e totais;
- payloads e sondas manuais do Funil;
- vínculo 1:1 opcional de monitoramento e autorização de conversas/mensagens por unidade;
- login nativo, par username/senha, sessão, CSRF e revogação do acesso ao portal;
- painel somente leitura, períodos, consultas por unidade, botões históricos,
  indicadores, Google CSV e CSV essencial sem o prefixo brasileiro `+55`;
- follow-up proativo, retomada reativa, elegibilidade, migração e locks entre workers.

Para executar a suíte completa a partir da raiz:

```powershell
python -m unittest discover -s tests -t . -p "test_*.py"
```

Organização atual:

```text
tests/unit/test_fluxo_turno_abc.py
tests/unit/test_retry_essencial.py
tests/unit/test_persistencia_essencial.py
tests/unit/test_worker_flow_runtime.py
tests/unit/test_suporte_idoso_email_obrigatorio.py
tests/unit/test_saudacao_retorno.py
tests/unit/test_valida_etapa7.py
tests/unit/test_mensagens_reserva.py
tests/unit/test_inicio_informacoes_supera.py
tests/unit/test_valida_etapa11.py
tests/unit/test_validador_profissao.py
tests/unit/test_gerar_monitoramento_unidades.py
tests/unit/test_metricas_perfis_relatorios.py
tests/unit/test_sondas_funil.py
tests/unit/test_monitoramento_unidade.py
tests/unit/test_monitoramento_login.py
tests/unit/test_monitoramento_painel.py
tests/unit/test_followup.py
tests/integration/test_followup_postgres.py
```

Por padrão, os testes usam fakes e mocks para fronteiras externas, sem chamar
Meta, Funil, Redis ou RDS. A integração com PostgreSQL local só executa quando
`FOLLOWUP_TEST_DSN` é fornecida explicitamente. Um utilitário manual não deve
ser executado como forma de testar sua importação.

`test_botoes_webhook.py`, `test_valida_etapa18.py`, `test_fluxo_reserva_link.py`
e `test_pywa_compatibilidade.py` cobrem a escolha de turno: JSON dos botões
serializado pela PyWa, extração no webhook, tipos `interactive` e
`interactive_button`, resolução 18 → 19, persistência e replay sem novo envio.
Cobrem também frases afirmativas e a recusa de respostas ambíguas, múltiplos
turnos e menções sem escolha. As fronteiras HTTP e SQL são simuladas.

Testes unitários pertencem a `tests/unit/`; contratos com PostgreSQL real ficam
em `tests/integration/` e exigem ambiente descartável explícito. Dados e classes
auxiliares exclusivos de teste ficam em `tests/`, nunca nos módulos de produção.
Sem `FOLLOWUP_TEST_DSN`, a descoberta pula a integração PostgreSQL.

`test_mensagens_reserva.py` cobre negativas na escolha do participante,
gratuidade contextual, preservação do aceite flexível, retomada com uma
saudação, barreira terminal e igualdade entre texto enviado e histórico.
Também verifica a composição tratamento + repetição para titular/dependente,
as apresentações exclusivas da etapa 1, inatividade com avanço ou tratamento,
follow-up sem nova apresentação/despedida e participante preservado na reserva.
Os envios são simulados; a consulta do participante é conferida com cursor
substituído, sem conexão com banco de produção.

`test_inicio_informacoes_supera.py` cobre os pedidos de apresentação com e sem
saudação, acentos e interrogação, rejeição de palavras isoladas e outros assuntos,
prioridade de mídia/reforço/financeiro e envio do texto aprovado com os dados da
unidade. Verifica a inicialização da etapa 1, convergência das duas aberturas para
a etapa 2, follow-up sem reapresentação e retry sem novo envio. Meta e banco são
substituídos nos testes; não são feitas chamadas reais.

O teste de monitoramento executa o SQL de autorização em SQLite em memória,
adaptando apenas os placeholders, com um cliente compartilhado por duas
unidades. Cobre isolamento por conversa/mensagem, revogação do vínculo,
desativação de conta, várias unidades sem conta, exclusividade do usuário,
exclusão da conta com preservação da unidade, sessão inválida e falha de banco.
Não acessa o RDS. `fixtures/unidade_monitoramento_legado.sql` representa apenas
a proposta anterior para testar a transferência dos vínculos; não é uma
migração de produção.

`test_monitoramento_login.py` usa o backend, hashes de senha e sessões reais do
Django com usuários fictícios e SQLite em memória. Cobre senha de outra conta,
contas não autorizadas, erros, expiração de CSRF, logout, rotação de sessão,
redirecionamento fixo e escape de HTML. Substitui somente a conexão da thread
durante o teste e restaura-a ao terminar; não cria usuários nem tabelas no RDS.

`test_monitoramento_painel.py` valida as rotas privadas, métodos permitidos,
propagação obrigatória da unidade autorizada, quantidade de parâmetros dos SQLs,
consolidação de perfis, 24 etapas, períodos comparáveis e os quatro downloads
CSV (Google e essencial, todos e elegíveis). Cobre todos os períodos, unidade
autorizada, revogação de acesso, acentos, campos vazios e proteção contra fórmulas
nos dados textuais. Seus payloads vivem em `fixtures/monitoramento_painel.py` e
são fictícios.
O teste distingue a remoção de `+55` no essencial da preservação do telefone
internacional no Google CSV; não remove o DDD nem altera os dados de origem.

## Follow-up

A segunda camada é coberta em `unit/test_followup.py` (redação por rota, nomes e
falha de envio) e `integration/test_followup_postgres.py` (7h contadas do primeiro
envio real, etapas 1–17 e a 18 somente para unidade sem link incluindo 8, guardas de silêncio/fila/janela, encerramento
atômico com rollback, ausência de terceiro envio e reabertura sem prefixo).
O teste do painel usa as consultas reais para provar que outra conversa do mesmo
chat invalida o stage antigo, mesmo fora do período selecionado. A migração de
segundo follow-up é executada integralmente no PostgreSQL descartável, verificando
preservação dos dados e o novo domínio do motivo de encerramento.

`unit/test_mensagens_etapa11.py` cobre a introdução da triagem para titular e
dependente: nome carregado na entrada 10→11, mensagem inicial, tratamentos,
contexto autônomo, inatividade e follow-up. Verifica falha antes do envio para
dependente sem nome e a preservação do participante nas seis perguntas,
inclusive dependente adulto, sem alterar as regras de confirmação e avanço.

`unit/test_mensagens_contexto.py` cobre a mensagem autônoma de contexto em
todas as etapas: não usa compositores de tratamento ou perguntas de repetição.
Também verifica titular/dependente, ausência de avanço, botões/rodapés, link,
dados de apresentação e o prefixo único de inatividade, com envio simulado.

`unit/test_followup.py` cobre envio exato, reação, etapas e botões reais com HTTP
substituído, recuperação, falta de lock, falhas e parâmetros SQL. O teste de runtime
do flow cobre a repetição comum sem chamar validadores ou persistência de transição.
Cobre saudação com e sem nome, texto enviado igual ao histórico, isolamento do
prefixo sob exceção, retorno legado sem data de envio e falha sem interromper o lote.
Na etapa 1, cobre cliente antigo com nome salvo: saudação genérica, coleta de nome
mantida, reação ignorada e cadastro preservado. Também verifica nome novo aceito
no fluxo normal, personalização nas etapas seguintes e retry sem novo envio.
Na etapa 8, cobre qualquer reação indo diretamente à 9, sem repetir a 8 nem
consumir aceite, para titular e dependente. Verifica saudação única, botões,
mapa obrigatório antes do envio, persistência da transição antes do reset e
recuperação de respostas antigas da 8 ou novas da 9 sem alterar outro ciclo.

`integration/test_followup_postgres.py` exige explicitamente FOLLOWUP_TEST_DSN com
host loopback e banco vazio chamado `test_chatbot_followup`. Ele cria e remove seu
próprio schema chatbot, recusando schema preexistente. Sem essa variável é pulado.
Executa DDL canônico, consultas reais, unicidade em histórico particionado, rollback,
fila sem vínculo e dois proprietários do lock. Nunca aponta para DB_HOST/DB_NAME.
Também executa o SQL integral de migração sobre uma base antiga descartável:
marca somente ativas, audita os valores anteriores, preserva os demais dados,
não produz histórico/envio, recusa reaplicação e reverte diante de legado terminal.
O retorno completo também usa fila e histórico reais nesse banco descartável:
rollback preserva stage positivo, etapa, efeitos e contadores. Respostas válidas
avançam e são salvas; repetição neutra ou tratamento específico preservam a etapa
e o contador na primeira reação. A transição válida zera os turnos sem avanço
junto da conclusão do follow-up, inclusive no retorno da 8 para a 9. Verifica histórico
do cliente e checkpoint na origem, resposta no destino e recuperação da mesma
reação sem reset de um ciclo posterior. Cobre tanto o lembrete
confirmado quanto o legado sem data de envio.
Meta permanece simulada; a confirmação de entrega real exige homologação manual.

`unit/test_retomada_followup.py` percorre os validadores e senders reais nas
rotas titular/dependente: avanço válido, repetição neutra, tratamentos específicos,
triagem, idade, confirmação do destinatário e contagem após o retorno. Confere
prefixo único e igualdade entre texto enviado e histórico, inclusive cabeçalhos.
Os testes de runtime verificam o commit único de efeitos, checkpoint,
encerramento e fila, com rollback quando a finalização falha. A inatividade
de três horas mantém o tratamento normal de contexto inválido.

## Consulta de faixa etária no painel

`unit/test_faixa_etaria_monitoramento.py` cobre a consulta personalizada do painel:
titular único em várias conversas, dependentes por cadastro (inclusive nomes
iguais), distribuição por titular, idade inclusiva e dados ausentes. Executa o
SQL real em SQLite descartável para validar unidade, contato no período,
fronteiras de data/hora e envio confirmado ao funil da pessoa atendida. Exercita
também sessão/autorização, parâmetros duplicados, público único e falhas da API.
Nenhum teste acessa a base de produção.

## Suporte por idade

`unit/test_suporte_por_idade.py` cobre as cinco configurações (desativado/50/60/70/80), fronteiras,
Admin, contato comercial, mensagem, recuperação com limite atual e contagem
real em SQLite dos encaminhamentos por unidade, data e motivo. As suítes de
e-mail, turno, follow-up, CSV e relatórios continuam como regressão.

`integration/test_suporte_por_idade_postgres.py` executa migração, domínio,
recusa de reaplicação, falha com rollback e DDL de instalação limpa. Também
verifica tabela ocupada, falha durante a reversão, preservação das conversas
e consultas reais de contexto/relatório no schema completo após a migração. Exige
`SUPORTE_IDADE_TEST_DSN`, host loopback e banco vazio `test_chatbot_suporte_idade`.
Recusa schema chatbot preexistente; não usa DB_HOST/DB_NAME. Sem a variável, é
pulado. Ver o [procedimento](../deploy/idade_minima_suporte.md) para homologação.


## Encerramentos por idade

`test_encerramentos_por_idade.py` cobre faixa compatível no retry, mensagem ligada
à recuperação, cortes de idade, BPA histórico, último chat, separação por unidade
e relatório de conversas na configuração atual. Inclui idade por extenso e com
`anos de idade`, além dos retornos de titular com 91 e dependente com 92 depois
de ativar suporte 80+: ambos conservam a categoria universal sem novo envio.
`test_encerramentos_por_idade_postgres.py`
exige `COMERCIAL_IDADE_TEST_DSN` em banco loopback vazio `test_chatbot_comercial`;
recusa qualquer schema chatbot preexistente. Nunca apontar testes para produção.

## Compatibilidade PyWa

`test_pywa_compatibilidade.py` usa a biblioteca instalada e `httpx.MockTransport`,
sem chamadas à Meta. Exercita os senders de oferta, encaminhamento comercial,
avaliação e follow-up, o prefixo, a versão configurada da Graph API, os IDs de
envio, bloqueio/desbloqueio e paginação. Rejeições HTTP, ausência de ID e timeout
precisam continuar chegando como falhas ao worker, sem reenvio automático HTTP.
Validado na atualização de PyWa 3.8.0 para 4.5.0.

## Consumo mensal Meta

`test_consumo_meta.py` cobre calendário (incluindo fevereiro bissexto), volumes,
saldo, cobertura ESL, identidade e decisão/prorrogação do dia 25.
`test_monitoramento_consumo.py` testa apresentação, ausência de primeira coleta,
autorização real do Django, isolamento por unidade, erro sem falso zero e PDFs.
Inclui a prévia de outubro durante setembro, a abertura à meia-noite no fuso da
unidade, rejeição/ocultação de meses futuros e ordenação de histórico de vários anos.
`test_consultar_franquia_meta.py` continua validando o contrato HTTP do utilitário.

`tests.integration.test_consumo_meta_postgres` exige `CONSUMO_META_TEST_DSN`,
loopback e banco `test_chatbot_consumo` sem schema chatbot. Valida o SQL real
reexecutado, upsert, rollback, concorrência, agenda persistida, duas unidades,
meses pendentes e mudança de fuso, com respostas Meta simuladas. Não usa produção.

## Reserva com e sem plataforma

`unit/test_fluxo_reserva_link.py` cobre as rotas de titular/dependente, o turno,
os botões comerciais, os efeitos de transição e o replay sem novo envio.
`integration/test_reserva_link_postgres.py` exige `RESERVA_LINK_TEST_DSN` em
loopback e banco vazio `test_chatbot_reserva_link`: executa DDL, SQL de Funil,
follow-up, preferências e isolamento do painel.

`integration/test_migracao_reserva_link_postgres.py` exige
`MIGRACAO_RESERVA_TEST_DSN`, loopback e banco vazio
`test_chatbot_migracao_reserva`. A fixture restaura o schema anterior com dados
fictícios, incluindo partições, satisfação, fila, checkpoints, Funil e Consumo.
Confere remapeamento, preservação dos demais campos, reexecução, reversão,
recusas atômicas e recuperação de resposta migrada. Ambas as suítes recusam
schema `chatbot` preexistente; nunca apontar suas DSNs para a base de aplicação.

Exemplo, depois de criar os dois bancos descartáveis no PostgreSQL local:

```powershell
$env:RESERVA_LINK_TEST_DSN = 'host=127.0.0.1 dbname=test_chatbot_reserva_link user=postgres'
$env:MIGRACAO_RESERVA_TEST_DSN = 'host=127.0.0.1 dbname=test_chatbot_migracao_reserva user=postgres'
python -m unittest tests.unit.test_fluxo_reserva_link tests.integration.test_reserva_link_postgres tests.integration.test_migracao_reserva_link_postgres -v
```

As demais suítes de integração precisam das próprias DSNs descritas acima.
Sem as variáveis, os testes PostgreSQL são ignorados, não considerados aprovados.

A configuração atual de `atendimento_customizado.link_agendamento`, lida diretamente junto de `unidade` por `id_unidade`, decide a saída da triagem: com link, 17 → 20; sem link, 17 → 18 (preferência de turno) → 19 (contato comercial). A satisfação converge em 21 → 22 → 23 → 24, com salto 22 → 24 na recusa de comentário. A FireAds pode importar as coletas iniciais e pular o e-mail apenas mediante consulta válida da própria conversa.

`conversa.turno` aceita NULL, manha, tarde ou noite e é salvo somente na transação de 18 → 19. É preferência, não confirmação de agendamento. Qualquer texto posterior na 19 apresenta a nota da 21; não é interpretado como nota nessa mesma interação. Mídia repete a orientação da 19.

O Funil exige 20–24 com link ou 19/21–24 sem link, considerando a configuração vigente na seleção, no claim e no snapshot. Preservar recibo de sucesso se o CRM já aceitou. O snapshot e o painel incluem turno da própria conversa, quando preenchido.

Follow-up proativo: 1–17 em ambas as rotas e 18 somente sem link; a 19 e a 20 não recebem novos lembretes. São preservadas as duas camadas de sete horas, os recibos, o encerramento no segundo lembrete e as guardas existentes. A reação ao primeiro segue a validação normal: um turno válido na 18 avança para 19 e é persistido. Contexto inválido genérico repete; tratamentos específicos continuam prioritários. Retomadas legadas são remapeadas por significado; a exceção 8 → 9 permanece.

Instalação existente exige migração própria: IDs antigos 18/19/20/21/22 tornam-se 20/21/22/23/24. Não executar setup ou seeds no banco de produção nem reaplicar migrações históricas. Preservar o Consumo Meta, seus fusos, worker, relatórios e PDFs, a compatibilidade PyWa 4.5.0, a exceção universal de idade 90+, o comentário livre e a despedida por participante.

## FireAds, chat e personalização da unidade

`unit/test_fireads.py` cobre importação, valores Google/Meta, comparação de datas,
e-mail validado da própria conversa, abertura na profissão, replay, tratamentos,
preservação das observações, identidade ambígua e redirecionamento sem repetir POST.
Também verifica que um inline inválido da personalização impede o cadastro na Meta.

`unit/test_fireads_espera.py` cobre o orçamento HTTP de 300 segundos entre abas
e redirecionamentos e a rejeição de resposta tardia. O runtime do flow verifica que
uma consulta pendente libera o ciclo para outro cliente sem envio prematuro.

`integration/test_fireads_postgres.py` exige FIREADS_TEST_DSN em loopback e banco
vazio test_chatbot_fireads. Executa ambas as migrações, valida preservação do legado,
reserva simultânea, recuperação após desconexão, descarte de resultado de tentativa
antiga, timeout, rollback da importação, aplicação única e todas as 24 etapas sem
reconsulta. Preserva também os testes de Funil/Dash, configuração, unidade suspensa,
relatórios e contexto histórico. Apenas fronteiras HTTP são simuladas.

```powershell
$env:FIREADS_TEST_DSN = 'host=127.0.0.1 dbname=test_chatbot_fireads user=postgres'
python -m unittest tests.unit.test_fireads tests.unit.test_fireads_espera tests.integration.test_fireads_postgres -v
```

As fronteiras HTTP continuam simuladas; não há POST para clientes ou CRM nesses
testes. A fixture `fixtures/fireads.py` compartilha o DDL do deploy com os testes
atuais de reserva e follow-up. Os testes de migrações históricas conservam seus
catálogos históricos, sem inserir os atalhos FireAds na versão anterior.

Validação da aplicação em 08/10/2026: **487 testes executados, zero falhas, zero
erros e zero pulados**, usando PostgreSQL 16 local descartável e as sete DSNs de
teste. Os binários locais de validação não são dependência do projeto ou da VM.


### Consultas diretas da unidade (09/10/2026)

O setup e as bases de teste não criam `unidade_atendimento`. As suítes FireAds,
reserva/link, suporte por idade e follow-up executam o SQL real sobre as duas
tabelas. Cobrem contexto de titular/dependente, alteração da personalização,
isolamento entre unidades, elegibilidade com/sem link, preservação da suspensão
por pagamento, painel e relatórios semanal/total (incluindo unidades sem histórico).
A migração de remoção pode ser reexecutada; a migração FireAds não recria a view.
SQL dos serviços permanece em `core/repositories`; SQL dos relatórios utilitários
permanece em `utilitarios/reports_functions`.
````

## Passo 27: `deploy/README.md`

Apontar para o serviço e a migração novos.

````markdown
# Implantacao no Lightsail

Os arquivos assumem a aplicacao em `/opt/chatbot/app`, o ambiente virtual em
`/opt/chatbot/venv` e as variaveis em `/etc/chatbot/chatbot.env`. Os processos
da aplicacao sao independentes e escrevem seus logs no journald. O
portal de monitoramento faz parte do processo web `chatbot-webhook`; ele não
cria outro serviço. O quarto serviço é `chatbot-worker-followup`, implantado na
V1.2.0. Este guia também cobre a preparação de uma instalação nova.

## Preparar a aplicacao

### Atualização das mensagens da experiência Supera

A oferta usa **experiência Supera gratuita** e **demonstração prática exclusiva**.
Esta revisão não altera o schema da V1.3.0 já implantada. A proposta de
cadastro de responsável foi retirada antes do deploy, junto com seu SQL
pendente. Não executar scripts antigos salvos para criar essas duas colunas.
A apresentação do agente continua usando os campos já existentes.

### Instalação inicial

Clone a branch `prod` como o usuario `ubuntu` e instale as dependencias:

```bash
git clone --branch prod --single-branch git@github.com:Levi-cell/Chatbot.git /opt/chatbot/app
python3 -m venv /opt/chatbot/venv
/opt/chatbot/venv/bin/pip install --upgrade pip
/opt/chatbot/venv/bin/pip install -r /opt/chatbot/app/requirements.txt
```

Crie `/etc/chatbot/chatbot.env` conforme o procedimento em
[`regras_deploy/modificando_env_e_banco_em_prod.md`](../regras_deploy/modificando_env_e_banco_em_prod.md),
sem registrar segredos no repositorio. Em producao, use `DJANGO_DEBUG=False`,
configure o dominio em `DJANGO_ALLOWED_HOSTS` e mantenha o arquivo restrito:

```bash
sudo chown root:chatbot /etc/chatbot/chatbot.env
sudo chmod 0640 /etc/chatbot/chatbot.env
```

Defina `FUNIL_WORKER_ENABLED=True`, configure o RDS com TLS e informe o
endpoint do Redis remoto em `REDIS_HOST`. A aplicacao nao usa nem exige um
`redis-server` local na VM. Mantenha `PGSSLCERTMODE=disable` quando o RDS
autenticar por usuario/senha. Essa opcao desativa apenas o certificado TLS de
cliente; use `DB_SSLMODE=verify-full` e `DB_SSLROOTCERT` para continuar
validando o certificado do servidor.

Se o banco estiver vazio, crie antes o schema de destino no DBeaver:

```sql
CREATE SCHEMA IF NOT EXISTS chatbot;
```

Depois, prepare o Django. Suas migrations criam `chatbot.auth_user`, necessária
antes do DDL de negócio por causa do vínculo de monitoramento:

```bash
sudo -u chatbot bash -c 'set -a; source /etc/chatbot/chatbot.env; set +a; cd /opt/chatbot/app; export PYTHONPATH=/opt/chatbot/app; /opt/chatbot/venv/bin/python callback/manage.py check --deploy'
sudo -u chatbot bash -c 'set -a; source /etc/chatbot/chatbot.env; set +a; cd /opt/chatbot/app; export PYTHONPATH=/opt/chatbot/app; /opt/chatbot/venv/bin/python callback/manage.py migrate --noinput'
sudo -u chatbot bash -c 'set -a; source /etc/chatbot/chatbot.env; set +a; cd /opt/chatbot/app; export PYTHONPATH=/opt/chatbot/app; /opt/chatbot/venv/bin/python callback/manage.py collectstatic --noinput'
```

`EnvironmentFile` é carregado automaticamente somente pelo systemd. Uma sessão
SSH comum não recebe essas variáveis; os comandos manuais acima carregam o mesmo
arquivo privado dos serviços sem exibir seu conteúdo.

Em uma instalação vazia, após as migrations do Django, siga o
[setup do banco de negócio](../core/database/README.md#setup) antes de iniciar
os serviços. Na atualização de um banco existente, use a migração incremental
específica, sem executar novamente o setup como substituto da migração.

## Instalar os servicos

```bash
sudo install -m 0644 /opt/chatbot/app/deploy/systemd/*.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now chatbot-webhook chatbot-worker-flow chatbot-worker-funil
```

O follow-up é instalado junto das demais units, mas deve ser iniciado somente
após o banco e o flow compatível estarem validados. Conclua a seção
[Ativação do follow-up](#ativação-do-follow-up) para habilitá-lo.

```bash
systemctl status chatbot-webhook chatbot-worker-flow chatbot-worker-funil chatbot-worker-followup
journalctl -u chatbot-webhook -u chatbot-worker-flow -u chatbot-worker-funil -u chatbot-worker-followup -f
```

## Habilitar o Nginx e HTTPS

Instale o template, substitua `__DOMAIN__` pelo dominio real e habilite o site.
O Gunicorn escuta somente em `127.0.0.1:8000`; apenas o Nginx recebe trafego
publico.

```bash
sudo install -m 0644 /opt/chatbot/app/deploy/nginx/chatbot.conf /etc/nginx/sites-available/chatbot
sudoedit /etc/nginx/sites-available/chatbot
sudo ln -sfn /etc/nginx/sites-available/chatbot /etc/nginx/sites-enabled/chatbot
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t
sudo systemctl reload nginx
```

Com o DNS apontando para o IP estatico e as portas 80/443 abertas, deixe o
Certbot criar a configuracao HTTPS somente depois de emitir o certificado:

```bash
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx --redirect -d SEU_DOMINIO
sudo certbot renew --dry-run
```

Somente depois de o HTTPS funcionar, ative no ambiente
`DJANGO_TRUST_X_FORWARDED_PROTO=True`, `DJANGO_SECURE_SSL_REDIRECT=True`,
`DJANGO_SESSION_COOKIE_SECURE=True` e `DJANGO_CSRF_COOKIE_SECURE=True`, e
reinicie o webhook. O Nginx sobrescreve `X-Forwarded-Proto`; o Django nao confia
em um valor enviado diretamente pelo cliente.

## Atualizacao rotineira da branch prod

O procedimento canonico esta em
[`regras_deploy/rotina_deploy.md`](../regras_deploy/rotina_deploy.md).

Na atualização dos workers ou de seus módulos compartilhados, pare o follow-up
antes do flow; retome o flow compatível e validado antes de reativar os lembretes.
Pare também o Funil quando ele for afetado. Alterações exclusivas do painel
podem manter os workers ativos. O webhook continua recebendo e enfileirando
quando o schema permite; para carregar Python/templates novos, recebe `HUP`,
pois Gunicorn não possui auto-reload. Alteração de `.env` ou da unit exige `restart` e segue
[`modificando_env_e_banco_em_prod.md`](../regras_deploy/modificando_env_e_banco_em_prod.md).

## Migracoes incrementais do banco de negocio

Os scripts SQL revisáveis para o RDS existente ficam em `deploy/migrations/`.
Eles não são executados por `manage.py migrate` nem pelo setup de instalação
limpa. Siga os pré-requisitos, as validações e a orientação de rollback do
próprio arquivo antes de publicar o código que depende do novo estado.

Para o cadastro de monitoramento, execute
`deploy/migrations/20260902_adicionar_usuario_monitoramento_unidade.sql` inteiro no DBeaver
antes de publicar o Admin atualizado. Requer `chatbot.unidade` e
`chatbot.auth_user`. O script adiciona `unidade.id_usuario_monitoramento`, com
`UNIQUE` e FK `ON DELETE SET NULL`. Se `unidade_monitoramento` já existir,
valida e transfere os vínculos antes de removê-la, sem `CASCADE`. O SQL anterior
de criação da tabela foi substituído e não deve ser executado.

É uma migração de aplicação única: coluna já existente causa erro. Em caso de
falha, execute `ROLLBACK`; investigue a causa antes de repetir. `ALTER TABLE`
fica somente nesta migração, enquanto o DDL de instalação limpa já contém a
coluna em seu `CREATE TABLE`. Depois da migração, não publique novamente o
código que depende da tabela antiga. Uma reversão exige preservar os vínculos
atuais e preparar um SQL específico antes de voltar o código.

## Operacao dos servicos e do Redis remoto

Os comandos individuais para iniciar e parar cada processo, limpar somente os
bloqueios no Redis remoto e remover o servidor Redis local da VM estao em
[`regras_deploy/servicos_e_redis_remoto.md`](../regras_deploy/servicos_e_redis_remoto.md).

Nao exponha a porta `6379` e nao use `FLUSHDB` ou `FLUSHALL` em producao.

## Ativação do follow-up

Esta alteração exige migração manual `migrations/followup_registros.sql` antes do
flow novo. Instalação limpa utiliza `followup_script.py`, chamado por `bank_script`.
As colunas `followup_stage`/`followup_last_sent_at` já existentes não são recriadas. Com o flow
parado e o follow-up desligado, a migração registra em followup_legado todas as
conversas ativas e marca followup_stage = 1, inclusive nas etapas 18–21. O horário
`followup_last_sent_at`, o histórico, a etapa e a finalização permanecem como estavam.
O script é único e transacional; não reaplicar nos próximos deploys. O setup limpo
cria as três tabelas e não marca conversas. A marcação não comprova envio de mensagem.
Conversa ativa terminal/inconsistente recusa toda a migração: concluir a recuperação
pendente do flow e revisar a anomalia antes de tentar de novo, sem encerrar em massa.

Na produção, essa migração já foi aplicada em 10/09/2026 na V1.2.0, com 106
conversas marcadas naquela execução. Não repetir nem manter esse número como
expectativa fixa: os clientes podem retomar normalmente após o deploy.

Instalar `systemd/chatbot-worker-followup.service` e executar daemon-reload não
inicia envios. A unit habilita FOLLOWUP_WORKER_ENABLED; se essa chave já existir no
EnvironmentFile, conferir a precedência antes da ativação. Nenhum segredo novo é necessário.
Antes da primeira ativação, executar o diagnóstico abaixo e conferir permissões
da role da aplicação nas novas tabelas. Reiniciar primeiro
`chatbot-worker-flow.service` e conferir estado/logs. Somente então:

```bash
sudo systemctl enable --now chatbot-worker-followup.service
sudo journalctl -u chatbot-worker-followup.service --since "5 minutes ago" -n 80 --no-pager
```

`python -m utilitarios.verificar_followup` faz leitura e mostra IDs de uma amostra.
Não é uma execução do worker e não envia mensagens. Um resultado vazio é válido.
O [README dos utilitários](../utilitarios/README.md#diagnóstico-de-follow-up)
traz o comando com o ambiente da VM e explica cada indicador. A sequência completa
de atualização fica em [rotina_deploy.md](../regras_deploy/rotina_deploy.md).

Para interromper os lembretes, parar e desabilitar a unit de follow-up. Isso mantém
o flow apto a tratar retornos de lembretes ou do legado marcado. Não apagar recibos, resetar
stages em massa nem reverter o flow incompatível enquanto existirem ciclos positivos.

## Segunda camada de follow-up

Aplicar [`migrations/20260924_segundo_followup.sql`](migrations/20260924_segundo_followup.sql)
com os workers parados, antes de iniciar o código novo. O arquivo amplia somente
o motivo de encerramento permitido; não fecha conversas nem altera stages existentes.
Não repetir `followup_registros.sql`. Instalação limpa usa o DDL atualizado.

A segunda camada usa o mesmo serviço, após mais 7h desde o primeiro envio real,
mantendo a janela de envio. Recibos antigos válidos podem se tornar elegíveis ao
iniciar o worker; marcações de legado sem recibo não geram despedida.
Atualizar também os estáticos do painel (`collectstatic`) para publicar o filtro
**Follow-up**. Validar o diagnóstico sem envio, reiniciar o flow e só então o follow-up.

## Suporte por idade mínima

O [procedimento de suporte por idade](idade_minima_suporte.md) coordena schema,
código, estáticos e serviços. A migração incremental está em
`migrations/20260911_idade_minima_suporte.sql`; a reversão restrita a NULL/60 está
em `rollback/20260911_idade_minima_suporte.sql`. Não executar em instalações
novas, não reaplicar a migração de follow-up e não editar a migração histórica
que criou a coluna booleana. Os comandos só pertencem à implantação aprovada.


## Filtro Comercial e regras de idade

Ver [procedimento coordenado](filtro_comercial_regras_idade.md). A migração
`migrations/20260926_filtro_comercial_regras_idade.sql` exige telefones reais válidos
e interrompe a transação se houver pendência. Não executá-la com código antigo
processando atendimentos ou permitindo edição simultânea no Admin.

## Consumo Meta: serviço adicional

A seção Consumo acrescenta um quinto processo independente,
`chatbot-worker-consumo-meta.service`. Exige a migração
`migrations/20260929_consumo_mensal_meta.sql`, dependências de PDF, collectstatic
e ativação por ambiente. Seguir o [guia completo](consumo_mensal_meta.md); não
executar o setup inicial de banco numa atualização. Até ativar o serviço e
existir coleta válida, o painel informa que aguarda dados.

## Reserva com e sem plataforma

Seguir o [procedimento coordenado de implantação](reserva_com_sem_link.md).
O SQL incremental está em `migrations/20261003_reserva_com_sem_link.sql`, com
reversão restrita em `rollback/20261003_reserva_com_sem_link.sql`.

A configuração atual de `unidade.link_agendamento` decide a saída da triagem: com link, 17 → 20; sem link, 17 → 18 (preferência de turno) → 19 (contato comercial). A satisfação converge em 21 → 22 → 23 → 24, com salto 22 → 24 na recusa de comentário. As etapas 1–17 conservam suas regras.

`conversa.turno` aceita NULL, manha, tarde ou noite e é salvo somente na transação de 18 → 19. É preferência, não confirmação de agendamento. Qualquer texto posterior na 19 apresenta a nota da 21; não é interpretado como nota nessa mesma interação. Mídia repete a orientação da 19.

O Funil exige 20–24 com link ou 19/21–24 sem link, considerando a configuração vigente na seleção, no claim e no snapshot. Preservar recibo de sucesso se o CRM já aceitou. O snapshot e o painel incluem turno da própria conversa, quando preenchido.

Follow-up proativo: 1–17 em ambas as rotas e 18 somente sem link; a 19 e a 20 não recebem novos lembretes. São preservadas as duas camadas de sete horas, os recibos, o encerramento no segundo lembrete e as guardas existentes. A reação ao primeiro segue a validação normal: um turno válido na 18 avança para 19 e é persistido. Contexto inválido genérico repete; tratamentos específicos continuam prioritários. Retomadas legadas são remapeadas por significado; a exceção 8 → 9 permanece.

Instalação existente exige migração própria: IDs antigos 18/19/20/21/22 tornam-se 20/21/22/23/24. Não executar setup ou seeds no banco de produção nem reaplicar migrações históricas. Preservar o Consumo Meta, seus fusos, worker, relatórios e PDFs, a compatibilidade PyWa 4.5.0, a exceção universal de idade 90+, o comentário livre e a despedida por participante.

No corte de implantação, parar webhook, flow, Funil e follow-up antes da migração das etapas. Incluir Consumo Meta na parada controlada se houver indisponibilidade de banco; ao retomar, verificar os cinco serviços e preservar as variáveis existentes de Consumo. Não alterar tokens, versões de dependências ou o .env só para introduzir a rota sem link.


## Worker de consulta FireAds

O sexto serviço é `chatbot-worker-consulta-dash.service`. Aplicar com a migração
`migrations/20261009_worker_consulta_dash.sql`, sem executar setup numa base existente.
Seguir o [procedimento e recuperação](../docs/valida_dados_parciais_fireads.md).
````

## Passo 28: `docs/fireads_aplicacao_e_deploy.md`

Substituir a orientação local de threads pelo procedimento do worker separado.

````markdown
# FireAds — aplicação e deploy

Código aplicado localmente em **08/10/2026**, sobre o backup
`37b0265` (V1.9.2). **Deploy da V1.10.0 confirmado em 09/10/2026**, no commit
`49af8d5`, com a migração executada e os cinco serviços ativos. A conferência da
VM retornou 4 unidades, 4 personalizações, 4 linhas na view, nenhum vínculo de
chat inválido, 30 transições e nenhuma integração FireAds ativa. Webhook e login
responderam HTTP 200. O cadastro/ativação de Santo André no Admin continua sendo
a etapa seguinte da integração.

A [separação visual no Admin e suspensão por status_pagamento](status_pagamento_e_admin.md)
é uma atualização local posterior, com SQL próprio e ainda sem deploy. Não está
incluída no commit `49af8d5` já implantado.

A [leitura direta de unidade e personalização](consultas_diretas_unidade.md)
também está aplicada localmente para o próximo deploy. O código deixa de depender
da view; sua remoção está incluída no SQL unificado de suspensão por pagamento.
Os passos de implantação abaixo registram a entrega original da FireAds.

## Correção local de telefone — 09/10/2026

A busca compartilha agora a mesma regra entre produção e o utilitário
`utilitarios/fireAds/test_Dash.py`: normaliza DDI brasileiro, máscaras e prefixo
`p:+`, procura o número exato em cada aba e, se ausente, tenta a variante móvel
com/sem nono dígito. Preserva DDD e todos os demais dígitos. A variante segue a
regra do utilitário para números móveis antigos iniciados em 6, 7, 8 ou 9;
números fixos não ganham um nono dígito e DDI explícito estrangeiro é recusado.

Google e Meta continuam concorrendo pela data mais recente. Na escrita, todos os
formatos equivalentes são examinados para detectar linhas duplicadas: um único
cadastro compatível recebe só as observações; duplicados ou conflito de e-mail
permanecem pendentes. As variantes usam a mesma chave de lock por integração,
sem modificar o telefone do cliente ou o número enviado ao dashboard.

Esta correção requer deploy do código, sem migração SQL. Decisões de consultas
já concluídas permanecem gravadas; o teste da nova abertura exige uma nova
conversa. Os testes simulam chamadas externas, incluindo o caso de formulário
com nono dígito e WhatsApp sem ele.

## Consulta periódica por conversa

A proposta local de threads auxiliares no flow foi substituída pelo serviço
`worker_consulta_dash`, com resultado completo persistido e uma consulta por
conversa. Esta mudança REQUER a migração `20261009_worker_consulta_dash.sql` e a
instalação de um sexto serviço. Os detalhes de implantação, recuperação e prazo de
300 segundos estão no [guia do worker](valida_dados_parciais_fireads.md).

Os passos históricos abaixo descrevem a entrega inicial; não substituem o guia
novo nem autorizam reaplicar o SQL inicial numa instalação já atualizada.

## Implementação

- Adaptador HTTP e regras de importação em `core/integrations/fireads`.
- Consultas e entregas persistidas em `core/repositories/fireads`.
- Consulta de abertura em `workers/worker_flow/fireads.py`, antes da primeira
  resposta. Aguarda o worker de consulta e só importa sob a reserva da conversa.
  Falha efetiva, ambiguidade ou prazo de 300 segundos esgotado inicia como orgânico;
  enquanto aguarda dentro do prazo, a mensagem permanece pendente.
- Envio ao dashboard em `workers/worker_funil/fireads.py`, depois do sucesso no
  Funil e com fila própria. Não depende de haver novos leads para o Funil no ciclo.
- Personalização separada da identidade da unidade, com inline obrigatório no
  Admin e visualização pelo nome da unidade. Configurações FireAds são opcionais,
  únicas por unidade e começam desativadas.
- Tabela `chat` universal; conversa e consulta FireAds têm vínculos conferidos no
  banco. Uma nova conversa cria outra consulta; o chat é acessado por meio da conversa,
  preservando consultas e decisões anteriores.

## Ajustes confirmados durante a aplicação

- A leitura real do Google já retornou `Para mim` e `Para meu avô/avó`, compatíveis
  com a nova interpretação. Registros antigos com apenas faixa/perfil etário
  continuam insuficientes para decidir titular/dependente.
- Na Meta, foi observado `pai_ou_mae`. O mapeamento reconhece esse identificador,
  `para_mim`, `mim_e_outra` e as variantes explícitas previstas no contrato.
- O Admin valida a personalização antes de iniciar o cadastro da unidade na Meta.
- Messages apenas compõe o texto da abertura: a decisão de tratamento permanece
  no worker, e o sender preserva o registro do tratamento enviado.
- O repositório de entrega recupera o conteúdo congelado antes de reconstruí-lo.
- Os testes de banco foram adaptados à estrutura atual; os de migração histórica
  conservam os mapas de suas versões originais.

## Validação

**487 testes passaram, sem falhas, erros ou testes pulados.** Foram usados sete
bancos PostgreSQL 16 locais e descartáveis. A suíte inclui migração/reexecução,
preservação dos dados, locks concorrentes, importação, retry, envio pendente,
reconciliação, reserva com/sem link, follow-up, painel, consumo Meta e relatórios.
Também foram conferidas a sintaxe Python e as verificações Django de models/Admin.

As consultas reais à FireAds foram somente leitura. Os POSTs à Meta, ao Funil e
ao dashboard foram simulados nos testes. Não houve envio de leads de teste.

## Ordem de implantação

1. Subir e conferir a revisão de código que será implantada.
2. Parar webhook e workers que usam o banco, conforme o procedimento habitual.
3. Atualizar o código da VM.
4. Executar **inteiro** no DBeaver o arquivo
   [`20261007_fireads_chat_customizacao.sql`](../deploy/migrations/20261007_fireads_chat_customizacao.sql).
   Ele também está no último passo do [plano prático](integracao_fireads.md).
5. Conferir o resultado: uma personalização por unidade, nenhuma conversa sem
   chat, 30 transições e nenhuma integração ativa por padrão. Um erro aborta a
   transação; não continuar executando apenas partes posteriores do SQL.
6. Executar as verificações Django e iniciar os serviços. Conferir saúde e logs.
7. No Admin, cadastrar a integração de Santo André pelo nome, com o endereço
   `/exec` e as abas padrão. `url_operation` é só referência do editor.
8. Confirmar a configuração de fuso da planilha e a desativação da antiga
   sincronização da agência. Marcar o contrato validado e ativar a integração.

O horário exibido no dashboard sugere Brasília, mas não confirma a configuração
da planilha. Preencher `America/Sao_Paulo` apenas após essa confirmação. Enquanto
o campo estiver nulo, uma correspondência única válida pode ser importada;
registros cujas datas não possam ser comparadas resultam em atendimento orgânico.
Nenhum fuso ou Data/Hora é imposto ao dashboard nas escritas.

## Limites conhecidos

A API da planilha não oferece atualização condicional nem chave de idempotência
no servidor. A leitura antes da escrita, os locks locais e os marcadores por
conversa reduzem duplicações. Uma edição/ordenação externa entre GET e POST ainda
pode conflitar; essa limitação foi aceita. Não há exclusão automática de leads.

O rollback desta entrega não é apenas voltar o Git: o schema move colunas e cria
vínculos obrigatórios. Qualquer reversão após migrar deve considerar o banco e os
novos dados em conjunto. Não executar migrações antigas ou o setup para desfazer
essa alteração.
````

## Passo 29 — final: migração SQL para o DBeaver: `deploy/migrations/20261009_worker_consulta_dash.sql`

Migração final: executar inteira no DBeaver, apenas durante a aplicação coordenada.

````sql
-- Executar inteiro no DBeaver, com webhook e todos os workers parados.
-- Exige a migração FireAds de 07/10. Não consulta nem escreve no dashboard.
BEGIN;
SET LOCAL lock_timeout = '5s';
SET LOCAL statement_timeout = '120s';

-- INICIO DDL CONSULTA DASH
DO $migracao$
DECLARE
    total_antes BIGINT;
BEGIN
    IF NOT EXISTS (SELECT 1 FROM chatbot.migracoes_fireads
                   WHERE versao='20261007_fireads_v1') THEN
        RAISE EXCEPTION 'Aplicar primeiro a estrutura FireAds existente.';
    END IF;
    IF EXISTS (SELECT 1 FROM chatbot.migracoes_fireads
               WHERE versao='20261009_consulta_dash_v1') THEN
        RAISE NOTICE 'Worker de consulta já migrado; nenhum dado reimportado.';
        RETURN;
    END IF;
    LOCK TABLE chatbot.consulta_fireads,chatbot.conversa IN ACCESS EXCLUSIVE MODE;
    SELECT count(*) INTO total_antes FROM chatbot.consulta_fireads;

    -- DROP COLUMN elimina somente constraints locais que usam id_chat.
    -- A FK composta da conversa é substituída abaixo, sem CASCADE de objetos.
    ALTER TABLE chatbot.consulta_fireads DROP COLUMN id_chat;
    ALTER TABLE chatbot.consulta_fireads RENAME COLUMN id_conversa_referencia TO id_conversa;
    ALTER TABLE chatbot.consulta_fireads
        ADD CONSTRAINT uq_consulta_fireads_conversa UNIQUE (id_conversa),
        ADD CONSTRAINT fk_consulta_fireads_conversa_unidade
            FOREIGN KEY (id_conversa,id_unidade)
            REFERENCES chatbot.conversa(id_conversa,id_unidade) ON DELETE CASCADE,
        ADD COLUMN status VARCHAR(20) NOT NULL DEFAULT 'pendente',
        ADD COLUMN entrada JSONB,
        ADD COLUMN solicitado_em TIMESTAMPTZ NOT NULL DEFAULT now(),
        ADD COLUMN prazo_final TIMESTAMPTZ NOT NULL DEFAULT (now()+INTERVAL '300 seconds'),
        ADD COLUMN tentativas INTEGER NOT NULL DEFAULT 0,
        ADD COLUMN versao_reserva BIGINT NOT NULL DEFAULT 0,
        ADD COLUMN processing_started_at TIMESTAMPTZ,
        ADD COLUMN reserva_ate TIMESTAMPTZ,
        ADD COLUMN aplicacao JSONB,
        ADD COLUMN aplicado_em TIMESTAMPTZ,
        ADD COLUMN ultimo_erro TEXT;

    -- Preserva IDs, resultado e conteúdo antigo. Dados legados passam a um
    -- envelope; não inventar linhas de formulário que não foram armazenadas.
    UPDATE chatbot.consulta_fireads q SET
        status=CASE WHEN q.consulta_concluida THEN 'concluida' ELSE 'pendente' END,
        entrada=jsonb_build_object('url',i.url_dashbord,'aba_google',i.aba_google,
            'aba_meta',i.aba_meta,'fuso',i.fuso_formularios,'numero',cl.waid_telefone,
            'migrada',true),
        solicitado_em=COALESCE(q.consultado_em,q.atualizado_em),
        prazo_final=COALESCE(q.consultado_em,q.atualizado_em)+INTERVAL '300 seconds',
        dados=CASE WHEN q.dados IS NOT NULL
            THEN jsonb_build_object('decisao',q.dados,'fontes','{}'::jsonb,'legado',true)
            ELSE NULL END,
        aplicacao=CASE WHEN q.consulta_concluida THEN c.contexto_fireads END,
        aplicado_em=CASE WHEN q.consulta_concluida AND c.contexto_fireads IS NOT NULL
            THEN COALESCE(q.consultado_em,q.atualizado_em) END
    FROM chatbot.conversa c,chatbot.cliente cl,chatbot.integracao_fireads i
    WHERE c.id_conversa=q.id_conversa AND cl.id_cliente=c.id_cliente
      AND i.id_integracao_fireads=q.id_integracao_fireads;

    ALTER TABLE chatbot.consulta_fireads
        ALTER COLUMN entrada SET NOT NULL,
        ADD CONSTRAINT ck_consulta_entrada CHECK (jsonb_typeof(entrada)='object'),
        ADD CONSTRAINT ck_consulta_status CHECK (status IN ('pendente','processando','concluida')),
        ADD CONSTRAINT ck_consulta_conclusao CHECK ((status='concluida')=consulta_concluida),
        ADD CONSTRAINT ck_consulta_reserva CHECK (
            (status='processando' AND processing_started_at IS NOT NULL AND reserva_ate IS NOT NULL)
            OR (status<>'processando' AND processing_started_at IS NULL AND reserva_ate IS NULL)),
        ADD CONSTRAINT ck_consulta_tentativas CHECK (tentativas>=0 AND versao_reserva>=0),
        ADD CONSTRAINT ck_consulta_aplicacao CHECK (
            (aplicacao IS NULL AND aplicado_em IS NULL)
            OR (aplicacao IS NOT NULL AND aplicado_em IS NOT NULL AND consulta_concluida)),
        ADD CONSTRAINT ck_consulta_prazo CHECK (prazo_final>=solicitado_em);

    CREATE INDEX idx_consulta_fireads_pendentes
        ON chatbot.consulta_fireads(solicitado_em,id_consulta) WHERE status<>'concluida';

    IF (SELECT count(*) FROM chatbot.consulta_fireads)<>total_antes THEN
        RAISE EXCEPTION 'Quantidade de consultas alterada; migração cancelada.';
    END IF;
    INSERT INTO chatbot.migracoes_fireads(versao) VALUES ('20261009_consulta_dash_v1');
END;
$migracao$;
-- FIM DDL CONSULTA DASH

SELECT
    EXISTS (SELECT 1 FROM chatbot.migracoes_fireads
            WHERE versao='20261009_consulta_dash_v1') AS migracao_ok,
    (SELECT count(*) FROM chatbot.consulta_fireads) AS consultas,
    (SELECT count(*) FROM chatbot.consulta_fireads WHERE status<>'concluida') AS pendentes,
    (SELECT count(*) FROM chatbot.consulta_fireads q JOIN chatbot.conversa c USING (id_conversa)
     WHERE q.id_unidade<>c.id_unidade) AS vinculos_invalidos;
COMMIT;
````
