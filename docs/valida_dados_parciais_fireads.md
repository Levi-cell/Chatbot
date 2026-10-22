# Plano prático — coleta de dados parciais na abertura

> Complemento de 21/10/2026: [Chat Fire e turno antecipado](chat_fire_turno_antecipado.md).
> Proposta futura, ainda não ativa: [Sincronização dos campos do chatbot](fireads_sincronizacao_campos.md).
> A entrega atual continua atualizando somente Observação em registros existentes.
> Os blocos deste plano registram a aplicação de 20/10. O complemento descreve
> as alterações posteriores e a migração adicional; não sobrescrever o código
> atual com estes blocos históricos.

Status: aplicado e validado localmente em 20/10/2026. A migração de produção
permanece pendente para o deploy coordenado.
Revisão-base do plano: `3d689f35ba0b67b93d6d2decb17d29b690227307`.
Backup anterior à aplicação: `0c8824d` (20/10/2026 21:02).
Os blocos abaixo contêm os arquivos completos, atualizados com os ajustes da aplicação.

Este plano substitui a proposta teórica e os procedimentos históricos que
compartilhavam este arquivo. Não reinstalar o worker de consulta: ele já existe.
O último passo contém o arquivo SQL completo para salvar e executar no DBeaver.

## Contrato funcional

- Examinar somente a primeira mensagem de cada conversa, após as guardas atuais
  de unidade, pagamento, bloqueios, atendimento ativo e posse da mensagem.
- Extrair nome do titular, e-mail e destinatário explicitamente identificáveis.
  O parser reconhece rótulos sem depender da ordem das perguntas, da saudação ou
  do formulário inteiro. Não promete interpretar qualquer frase livre como um
  formulário: nome sem identificação segura e destinatário desconhecido serão
  perguntados. Nome do dependente e telefone escrito no formulário não substituem
  o titular e o remetente WhatsApp. Idade não determina destinatário.
- Dados completos: iniciar na profissão, etapa **4 no código atual**, sem consulta.
  Em unidade FireAds, o formulário no chat identifica Meta. Sem FireAds, manter a
  configuração do canal Funil da unidade (padrão Meta `113340`) e não criar consulta,
  origem FireAds ou envio ao dashboard.
- Texto livre recebido no WhatsApp usa validação estrutural de e-mail. Os campos
  estruturados da planilha preservam os extratores FireAds já existentes: não
  passam novamente pelas regras de resposta do chat. Campo externo vazio continua
  pendente; o destinatário precisa ser interpretável e não é inferido pela idade.
- Dados parciais/conflitantes com FireAds: criar uma consulta persistida, com o
  prazo total atual de 300 segundos, e liberar o fluxo para outros atendimentos.
  Completar exclusivamente a partir de uma inscrição compatível; não misturar
  registros. Sem resultado compatível, erro ou timeout, perguntar o que faltar.
- E-mails equivalentes repetidos contam como um valor. Valores diferentes ficam
  conflitantes. Os outros campos aceitos filtram o registro de complementação;
  o campo conflitante não serve de filtro. A planilha pode resolver um conflito
  com um valor diferente dos candidatos da mensagem.
- Filtrar os canais elegíveis Google Ads, Meta Ads e Orgânico Site antes da
  recência; escolher data/hora mais recente e depois maior linha. Indicação e
  Lead Franqueador não fornecem dados da abertura. Somente uma inscrição fornece
  os valores faltantes. Consulta sem dados de formulário mantém a rota orgânica.
- Conservar as exceções de tratamento já implantadas para a comparação com curso
  de inglês e o enunciado financeiro do formulário. Dúvidas reais acrescentadas
  pelo cliente continuam recebendo tratamento.

| Nome aceito | Destinatário aceito | E-mail aceito | Abertura e continuidade |
| --- | --- | --- | --- |
| Não | Não | Não | Etapa 1 → 2 → 3 → profissão; e-mail na etapa 10. |
| Não | Não | Sim | Etapa 1 → 2 → 3 → profissão; reutilizar e-mail. |
| Não | Sim | Não | Etapa 1 → profissão pela nova aresta; e-mail na etapa 10. |
| Não | Sim | Sim | Etapa 1 → profissão pela nova aresta; reutilizar e-mail. |
| Sim | Não | Não | Etapa 2 → confirmação 3 → profissão; e-mail na etapa 10. |
| Sim | Não | Sim | Etapa 2 → confirmação 3 → profissão; reutilizar e-mail. |
| Sim | Sim | Não | Profissão; e-mail na etapa 10. |
| Sim | Sim | Sim | Profissão; reutilizar e-mail. |

O nome do formulário sempre pertence ao titular. Profissão, idade, nome/idade do
dependente, restrições etárias, triagem, customização, follow-up, reserva e
encerramento mantêm os validadores e as transições existentes. A política atual
de e-mail obrigatório/opcional continua valendo quando o e-mail não foi coletado.
Uma correção do cliente atualiza a coleta da conversa, preservando os dados
originais usados para identificar a inscrição externa.

## Persistência, concorrência e compatibilidade

`conversa.contexto_coleta` guarda versão, conversa, primeira mensagem, candidatos,
status e fonte de cada campo, cópia dos campos originais e etapa inicial. É
independente de FireAds. O contexto, a importação e a aplicação da consulta usam
a mesma transação do worker, sob os locks existentes. Conflito de e-mail no
cadastro não descarta nome e destinatário aceitos; deixa o e-mail pendente.

A consulta HTTP continua exclusivamente no worker_consulta_dash. Mensagem completa
não cria consulta fictícia. A API de consulta versão 2 recebe um contrato adicional
`coleta.versao=1`; entradas antigas sem esse contrato continuam na interpretação
legada. Conversas já iniciadas e contextos FireAds anteriores não são reinterpretados.

O mapa ganha somente `nome_cliente_valido_destino_coletado` (1 → 4). A inicialização
na 2 ou 4 exige a decisão persistida; SQL e camada de movimento conferem a etapa.
Os eventos históricos de reutilização de e-mail 7/9 → 11 conservam seus nomes
para permitir replay e passam a aceitar também a coleta genérica da conversa.
O seed histórico mantém suas 30 arestas: a migração nova adiciona a aresta depois
das validações das migrações antigas. Não executar seeds em produção.

Os momentos de “digitando” existentes permanecem: após confirmar a nova pendência,
antes da consulta e antes da resposta. Quando a mensagem já é completa, somente
o envio normal sinaliza digitação; não há espera artificial nem tarefa auxiliar.

Para formulário no chat sem linha vinculada, procurar telefone, e-mail e destinatário
compatíveis no dashboard; desempatar por data/hora e linha. Parentesco específico
preservado diferencia mãe de filho; “para dependente” sem parentesco identifica
somente a categoria dependente. Se nada corresponder, criar nova linha com a
origem correta. Erro de leitura não equivale a ausência. E-mail presente em outro
telefone mantém a exigência de conferência já existente.

A entrega versão 3 congela `update` com identidade do registro ou `create` **antes
do POST**. Retries reconciliam primeiro o marcador técnico e conservam a escolha.
Referência vinculada apagada/alterada não autoriza escolher outro registro nem
criar automaticamente. Updates alteram apenas Observação, acrescentando o mesmo
resumo do Funil abaixo do texto anterior. Snapshots antigos não são reescritos.

Limites externos conhecidos: queda depois do envio WhatsApp/Funil e antes do
commit pode repetir o envio; queda antes de salvar um GET pode repetir a leitura.
O marcador permite reconciliar a entrega ao dashboard, mas a API não oferece
transação conjunta nem proteção contra edição manual entre GET e POST. Não há
promessa de ausência absoluta de falhas.

## Aplicação e validação

Cada passo abaixo é um arquivo inteiro, em UTF-8. Não executar o sistema entre
passos incompletos. Conferir a revisão-base e reconciliar mudanças posteriores
antes de substituir arquivos; os hashes identificam o conteúdo esperado.

1. Aplicar todos os arquivos numa revisão de desenvolvimento e executar os testes.
2. Na implantação, parar follow-up, webhook, flow, consulta, Funil e consumo Meta;
   atualizar o código com todos os arquivos presentes.
3. Executar integralmente o SQL do último passo. Exigir `migracao_ok=true` e
   `transicao_ok=true`. `conversas_com_coleta=0` é esperado no primeiro deploy:
   o histórico anterior não é inventado nem convertido.
4. Conferir os models com `manage.py check` e a leitura de `Conversa` no banco;
   executar a bateria unitária de regressão antes de religar os serviços.
5. Iniciar consulta/webhook/flow; depois Funil, consumo e follow-up. Testar uma
   conversa nova autorizada, com e sem formulário, e conferir histórico e entrega.

Reversão: após existirem conversas com `contexto_coleta`, não voltar simplesmente
para a revisão antiga. Ela não conhece a inicialização parcial na etapa 2 nem o
novo evento 1 → 4. Parar os serviços e preparar uma reversão que preserve essas
conversas e os snapshots pendentes; não apagar o contexto para forçar reinício.

Os models de domínio são `managed=False`: esta alteração usa o SQL explícito,
não `makemigrations`. Não atualizar VERSIONAMENTO nem fazer deploy como parte da
preparação deste documento. A decisão de versão será feita na aplicação.

Verificação unitária prevista, usando o ambiente do projeto:

```bash
python -m unittest tests.unit.test_coleta_abertura tests.unit.test_fireads tests.unit.test_fireads_espera tests.unit.test_fireads_aba_geral tests.unit.test_fireads_extratores tests.unit.test_fireads_telefones tests.unit.test_fireads_destino_dashboard tests.unit.test_worker_flow_runtime tests.unit.test_indicador_digitacao tests.unit.test_sondas_funil -q
```

Integração: `python -m unittest tests.integration.test_coleta_abertura_postgres -q`,
com `FIREADS_TEST_DSN` apontando exclusivamente para PostgreSQL descartável em
loopback, banco `test_chatbot_fireads`, sem schema `chatbot` preexistente. O teste
recusa outro destino e cria/remove somente seu schema de teste. As chamadas
externas são substituídas; não usar dados ou credenciais da produção.

## Evidências da preparação

Antes da aplicação, o código abaixo foi montado e validado em uma cópia de
trabalho isolada da revisão-base. As evidências desta seção correspondem àquela
preparação; a migração de produção não foi executada.

- **156 testes unitários passaram** na bateria indicada acima, incluindo os
  testes novos de extração, combinações de campos, conflitos, recência, mensagens
  e destino da entrega, junto das regressões de FireAds, fluxo e digitação.
- **48 cenários de integração foram validados em PostgreSQL local descartável**:
  38 da suíte FireAds e 10 da coleta parcial. A execução conjunta passou em 47;
  um teste de migração histórica precisou corrigir a preparação da fixture
  (origem e contexto devem ser gravados juntos) e passou na reexecução isolada.
  Essa última alteração afetou somente a fixture, sem mudança no código funcional.
- A integração executou o SQL real, incluindo reexecução sem perda de dados,
  preservação de consultas anteriores, aplicação após rollback, expiração sem
  nova consulta, perda do lock, conflito de e-mail, inicialização na etapa 2,
  transição autorizada 1 → 4 e reaproveitamento de resposta já persistida.
- A entrega ao dashboard foi verificada com HTTP substituído: o destino fica
  confirmado no PostgreSQL antes do POST. Atualizações e criação mantêm o
  contrato de observações e o canal correspondente.
- Os arquivos Python propostos passaram por análise sintática; os blocos de
  código do documento foram conferidos contra os arquivos usados na validação.

Essas verificações não são um teste de ponta a ponta na VM, na Meta ou na planilha
real. O PostgreSQL foi descartável e os serviços externos foram substituídos;
os testes simulam rollback/retomada, não perda física do disco ou crash do sistema
operacional. A homologação de uma conversa nova continua sendo uma etapa do
deploy. Os limites de falha externa descritos anteriormente continuam valendo.


## Validação da aplicação — 20/10/2026

Os 33 arquivos foram aplicados após conferir os hashes da base e do conteúdo
proposto. O guia `deploy/README.md` também recebeu a orientação desta migração.
A implementação preserva a coleta do e-mail no momento da etapa 10 quando esse
campo permanece ausente, inválido ou conflitante.

- Suíte unitária completa: **551 testes aprovados**.
- Suíte de coleta reexecutada após os dois casos adicionais: **24 testes aprovados**;
  inclui o encaminhamento real dos resolvers 7/9 para a etapa de e-mail ou triagem
  conforme a coleta e a compatibilidade de nome composto sem sobrenome.
- PostgreSQL local descartável: **48 testes de integração aprovados juntos**,
  incluindo migrações antigas, nova migração, rollback, locks e retomada.
- Checagem Django com configuração de teste: **nenhum problema identificado**.
- `git diff --check`: sem erros de espaço/formatação.

O ajuste de compatibilidade aceita “Ana Paula” diante de “Ana Paula Silva”, mas
continua recusando nomes compostos diferentes e sobrenomes explícitos divergentes.
A validação do código não acessou AWS, Redis, Meta, Funil ou FireAds reais. O SQL
foi executado apenas no PostgreSQL descartável. **Produção e VM aguardam deploy.**

## Índice dos arquivos

1. `core/validacoes/coleta_abertura.py` — criar.
2. `core/integrations/fireads/coleta_abertura.py` — criar.
3. `core/repositories/atendimento/coleta_abertura.py` — criar.
4. `workers/worker_flow/coleta_abertura.py` — criar.
5. `core/repositories/fireads/consulta.py` — alterar.
6. `core/repositories/fireads/pendencias.py` — alterar.
7. `workers/worker_consulta_dash/consulta.py` — alterar.
8. `workers/worker_flow/fireads.py` — alterar.
9. `core/integrations/whatsapp/messages/abertura_coleta.py` — criar.
10. `core/integrations/whatsapp/pywa_functions/pywa_senders/abertura_coleta.py` — criar.
11. `workers/worker_flow/valida_historico.py` — alterar.
12. `workers/worker_flow/response_flow/flow_sender.py` — alterar.
13. `workers/worker_flow/transacoes/movimento_conversa.py` — alterar.
14. `core/repositories/atendimento/conversas.py` — alterar.
15. `workers/worker_flow/response_flow/etapas/resolver_etapa1.py` — alterar.
16. `workers/worker_flow/transacoes/efeitos_transicao.py` — alterar.
17. `workers/worker_flow/transacoes/persistencia_resposta.py` — alterar.
18. `callback/webhook/models.py` — alterar.
19. `core/repositories/funil/leads.py` — alterar.
20. `core/integrations/funil/oportunidades.py` — alterar.
21. `core/integrations/fireads/destino_coleta.py` — criar.
22. `core/repositories/fireads/envios.py` — alterar.
23. `core/repositories/fireads/destino_coleta.py` — criar.
24. `workers/worker_funil/fireads.py` — alterar.
25. `core/database/deploy_database/fireads_script.py` — alterar.
26. `tests/fixtures/fireads.py` — alterar.
27. `tests/integration/test_fireads_postgres.py` — alterar.
28. `tests/unit/test_coleta_abertura.py` — criar.
29. `tests/integration/test_coleta_abertura_postgres.py` — criar.
30. `REGRAS_DE_NEGOCIO.md` — alterar.
31. `PADROES_DE_ARQUITETURA.md` — alterar.
32. `tests/README.md` — alterar.
33. `deploy/migrations/20261019_coleta_abertura.sql` — criar.

## Passo 1 — `core/validacoes/coleta_abertura.py`

Ação: **criar**. Conteúdo completo abaixo.

SHA-256 anterior: `arquivo novo`.

SHA-256 proposto (UTF-8/LF): `ecd8c928c08bbaac2f66f232182278344c51a4b00a79cc6b76263ee5461d4594`.

```python
"""Extração pura e conservadora de campos explícitos da primeira mensagem."""

import re
import unicodedata
from copy import deepcopy

from core.validacoes.email import validar_email_estrutural
from core.validacoes.nomes_compostos import PRIMEIROS_NOMES_COMPOSTOS

CAMPOS = ('nome', 'email', 'destinatario')
EVENTO_NOME_DESTINO_COLETADO = 'nome_cliente_valido_destino_coletado'


def normalizar(valor):
    base = unicodedata.normalize('NFKD', str(valor or '').casefold())
    return ' '.join(re.sub(r'[^a-z0-9]+', ' ', ''.join(
        c for c in base if not unicodedata.combining(c))).split())


def nome(valor):
    # Um título profissional/sufixo não invalida o nome explícito do titular.
    original = str(valor or '').strip()
    palavras = re.findall(r"[^\W\d_]+(?:[-'][^\W\d_]+)*", original.split('|', 1)[0], re.UNICODE)
    if not palavras or normalizar(palavras[0]) in {'ola', 'oi', 'nome', 'teste', 'email', 'nao'}:
        return None
    primeiro = palavras[0]
    composto = ' '.join(palavras[:2])
    if tuple(normalizar(composto).split()) in PRIMEIROS_NOMES_COMPOSTOS:
        primeiro = composto
    return primeiro.title()


def email(valor):
    validacao = validar_email_estrutural(valor)
    return validacao.email if validacao.valido else None


def destinatario(valor):
    chave = normalizar(valor)
    if chave in {'para mim', 'mim', 'titular', 'para o titular', 'eu', 'para voce'}:
        return {'dependente': False, 'chave': 'titular', 'texto': str(valor).strip()}
    parentes = {'pai', 'mae', 'avo', 'avos', 'filho', 'filha', 'filhos', 'neto', 'neta',
                'irmao', 'irma', 'tio', 'tia', 'sobrinho', 'sobrinha', 'marido', 'esposa',
                'companheiro', 'companheira', 'sogro', 'sogra', 'primo', 'prima', 'enteado', 'enteada'}
    palavras = set(chave.split())
    parentes_presentes = sorted(palavras & parentes)
    if parentes_presentes or any(t in chave for t in ('outra pessoa', 'dependente', 'outras pessoas')):
        # Guardar o parentesco: mãe e filho não são a mesma inscrição no dashboard.
        identidade = '+'.join(parentes_presentes) if parentes_presentes else 'dependente'
        if 'mim' in palavras:
            identidade = 'titular+' + identidade
        return {'dependente': True, 'chave': identidade, 'texto': str(valor).strip()}
    return None  # Faixa etária não define para quem é o atendimento.


def campo(valores, tipo, fonte='mensagem'):
    candidatos = list(dict.fromkeys(str(v).strip() for v in valores if str(v).strip()))
    extrair = {'nome': nome, 'email': email, 'destinatario': destinatario}[tipo]
    validos = {}
    for bruto in candidatos:
        valor = extrair(bruto)
        if valor is None:
            continue
        chave = valor['chave'] if tipo == 'destinatario' else (
            normalizar(bruto.split('|', 1)[0]) if tipo == 'nome' else valor.casefold())
        validos.setdefault(chave, (valor, bruto))
    status = 'ausente' if not candidatos else 'invalido'
    resultado = {'status': status, 'valor': None, 'candidatos': candidatos, 'fonte': fonte}
    if len(validos) > 1:
        resultado['status'] = 'conflitante'
    elif len(validos) == 1:
        chave, (valor, bruto) = next(iter(validos.items()))
        resultado.update(status='aceito', valor=valor, identidade=chave, bruto=bruto)
    return resultado


def extrair(texto):
    texto = str(texto or '')
    valores = {c: [] for c in CAMPOS}
    # E-mails diferentes nunca são resolvidos escolhendo a primeira ocorrência.
    valores['email'] = re.findall(r'[^\s@:,;<>]+@[^\s@,;<>]+', texto)
    for linha in texto.splitlines():
        if ':' in linha:
            rotulo, valor = linha.split(':', 1)
            rotulo = normalizar(rotulo)
            if rotulo in {'nome', 'nome completo', 'full name', 'nome do titular', 'seu nome', 'qual seu nome', 'qual e seu nome'}:
                valores['nome'].append(valor)
            elif rotulo.startswith('para quem') or rotulo in {'destinatario', 'atendimento para', 'treino para'}:
                valores['destinatario'].append(valor)
            elif rotulo in {'email', 'e mail', 'seu email', 'seu e mail'} and not valor.strip().count('@'):
                valores['email'].append(valor)
        apresentacao = re.match(r'^\s*(?:me chamo|meu nome é)\s+([^\n,.!?]+)', linha, re.I)
        if apresentacao:
            valores['nome'].append(apresentacao.group(1))
        if normalizar(linha).startswith('para ') and ':' not in linha:
            if destinatario(linha):
                valores['destinatario'].append(linha)
    return {c: campo(valores[c], c) for c in CAMPOS}


def aceito(estado, tipo):
    return (estado.get('campos', {}).get(tipo) or {}).get('status') == 'aceito'


def valor(estado, tipo):
    return estado['campos'][tipo]['valor'] if aceito(estado, tipo) else None


def etapa_inicial(estado):
    return 1 if not aceito(estado, 'nome') else (2 if not aceito(estado, 'destinatario') else 4)


def completo(estado):
    return all(aceito(estado, c) for c in CAMPOS)


def validar_contexto(contexto):
    estado = contexto.get('contexto_coleta')
    if not estado:
        return None
    if (estado.get('versao') != 1 or estado.get('id_conversa') != contexto.get('id_conversa')
            or estado.get('status') != 'pronto'):
        raise ValueError('Contexto de coleta não está pronto para esta conversa')
    return estado


def destinatario_coletado(contexto):
    estado = validar_contexto(contexto)
    return bool(estado and aceito(estado, 'destinatario'))


def email_coletado(contexto):
    estado = validar_contexto(contexto)
    return bool(estado and aceito(estado, 'email'))


def criar_contexto(id_conversa, mensagem):
    campos = extrair(mensagem.get('conteudo_texto') if mensagem.get('tipo_mensagem') == 'text' else '')
    return {'versao': 1, 'id_conversa': id_conversa, 'id_mensagem': mensagem['id_mensagem'],
            'id_hash': mensagem['id_hash'], 'status': 'preparando', 'campos': campos,
            'mensagem_original': deepcopy(campos), 'formulario_identificado': False,
            'rota_formulario_chat': bool(re.search(r'(?im)^\s*(?:full name|nome(?: completo| do titular)?|para quem[^:\n]*|e-?mail)\s*[?:]', str(mensagem.get('conteudo_texto') or '')))}
```

## Passo 2 — `core/integrations/fireads/coleta_abertura.py`

Ação: **criar**. Conteúdo completo abaixo.

SHA-256 anterior: `arquivo novo`.

SHA-256 proposto (UTF-8/LF): `68f639033ff7d8f887609e265397de2c5f64b1424cf7cb6acd74ca21bc08eda8`.

```python
"""Completa campos a partir de uma única inscrição compatível da aba geral."""

from copy import deepcopy
from core.validacoes.coleta_abertura import CAMPOS, campo, aceito, completo, normalizar
from core.integrations.fireads.aba_geral import ORIGENS, mais_recente, referencia_registro
from core.integrations.fireads.contrato import localizar
from core.integrations.fireads.extratores import extrair_nome, extrair_email

COLUNAS = {'nome': 'Nome', 'email': 'Email', 'destinatario': 'Para quem é'}


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


def interpretar_parcial(rows, numero, fuso, aba, estado):
    resultado = deepcopy(estado)
    encontrados = localizar(rows, numero, 'WhatsApp', incluir_equivalentes=True)
    candidatos = [r for r in encontrados if normalizar(r.get('Canal')) in ORIGENS
                  and compativel(estado['campos'], campos_registro(r))]
    row = mais_recente(candidatos, fuso)
    if row is not None:
        for c, recebido in campos_registro(row).items():
            if not aceito(resultado, c) and recebido['status'] == 'aceito':
                resultado['campos'][c] = recebido
        resultado['formulario_identificado'] = True
    return {'resultado': 'importado' if completo(resultado) else ('incompleto' if row else 'ausente'),
            'origem': ORIGENS[normalizar(row.get('Canal'))] if row else (
                'meta' if estado['rota_formulario_chat'] else 'organico'),
            'referencia': referencia_registro(row, aba, fuso), 'coleta': resultado,
            'motivo': None if row else 'sem_registro_compativel', 'dados_titular': {}}
```

## Passo 3 — `core/repositories/atendimento/coleta_abertura.py`

Ação: **criar**. Conteúdo completo abaixo.

SHA-256 anterior: `arquivo novo`.

SHA-256 proposto (UTF-8/LF): `c441605f02bad14b7cac9de96dd58d34aaf147445e73ec04357987ffc6688fe3`.

```python
"""Persistência da coleta na transação já protegida pelo lock da conversa."""

from copy import deepcopy
from psycopg.errors import UniqueViolation
from psycopg.types.json import Jsonb
from core.repositories.atendimento.dependentes import inserir_dependente_para_conversa
from core.validacoes.coleta_abertura import aceito, valor, campo, etapa_inicial


def salvar(id_conversa, estado, cursor):
    cursor.execute('UPDATE chatbot.conversa SET contexto_coleta=%s WHERE id_conversa=%s',
                   (Jsonb(estado), id_conversa))
    if cursor.rowcount != 1:
        raise ValueError('Conversa ausente ao salvar coleta')


def importar(abertura, id_conversa, estado, cursor):
    estado = deepcopy(estado)
    if aceito(estado, 'nome'):
        cursor.execute('UPDATE chatbot.cliente SET nome=%s WHERE id_cliente=%s',
                       (valor(estado, 'nome'), abertura['id_cliente']))
    if aceito(estado, 'email'):
        cursor.execute('SAVEPOINT coleta_email')
        try:
            cursor.execute('UPDATE chatbot.cliente SET email=%s WHERE id_cliente=%s',
                           (valor(estado, 'email'), abertura['id_cliente']))
        except UniqueViolation:
            cursor.execute('ROLLBACK TO SAVEPOINT coleta_email')
            estado['campos']['email'].update(status='conflitante', valor=None, motivo='email_em_outro_cliente')
        finally:
            cursor.execute('RELEASE SAVEPOINT coleta_email')
    if aceito(estado, 'destinatario'):
        dependente = valor(estado, 'destinatario')['dependente']
        cursor.execute('UPDATE chatbot.conversa SET status_dependente=%s WHERE id_conversa=%s',
                       (dependente, id_conversa))
        if dependente:
            inserir_dependente_para_conversa(id_conversa, cursor)
    estado.update(status='pronto', etapa_inicial=etapa_inicial(estado))
    salvar(id_conversa, estado, cursor)
    return estado


def guardar_coletas(contexto, efeitos, cursor):
    if not contexto.get('contexto_coleta') or not efeitos:
        return
    cursor.execute('SELECT contexto_coleta FROM chatbot.conversa WHERE id_conversa=%s FOR UPDATE',
                   (contexto['id_conversa'],))
    estado = cursor.fetchone()[0]
    if efeitos.get('cliente_nome_atualizado'):
        estado['campos']['nome'] = campo([efeitos['primeiro_nome_cliente']], 'nome', 'atendimento')
    if efeitos.get('cliente_email_atualizado'):
        cursor.execute('SELECT email FROM chatbot.cliente WHERE id_cliente=%s', (contexto['id_cliente'],))
        estado['campos']['email'] = campo([cursor.fetchone()[0] or ''], 'email', 'atendimento')
        estado['resultado_email'] = efeitos['resultado_coleta_email']
    if efeitos.get('status_dependente_atualizado'):
        texto = 'Para dependente' if efeitos['status_dependente'] else 'Para mim'
        estado['campos']['destinatario'] = campo([texto], 'destinatario', 'atendimento')
    if efeitos.get('destino_dado') == 'cliente':
        cursor.execute('SELECT idade FROM chatbot.cliente WHERE id_cliente=%s', (contexto['id_cliente'],))
        estado['idade_titular'] = cursor.fetchone()[0]
    salvar(contexto['id_conversa'], estado, cursor)
```

## Passo 4 — `workers/worker_flow/coleta_abertura.py`

Ação: **criar**. Conteúdo completo abaixo.

SHA-256 anterior: `arquivo novo`.

SHA-256 proposto (UTF-8/LF): `b79d274555796cda2f689a6c396eef5f4518bde82a338d73669c21225391a4ad`.

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
        estado = criar_contexto(cid, mensagem)
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
        decisao = {'resultado': 'importado', 'origem': 'meta', 'referencia': None, 'motivo': 'formulario_chat_completo'}
    elif estado['rota_formulario_chat'] and decisao.get('origem') == 'organico' and not decisao.get('referencia'):
        decisao['origem'] = 'meta'
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

## Passo 5 — `core/repositories/fireads/consulta.py`

Ação: **alterar**. Conteúdo completo abaixo.

SHA-256 anterior: `a64cc1c75abdbfbc88bbf4e2a20bbec27f7da4d4c2ce447c82bf633da139eb54`.

SHA-256 proposto (UTF-8/LF): `ea43f874a67546a71942018c9330652edd70108e3fec227fe5637d9c2910f452`.

```python
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
               i.url_dashbord,i.aba_destino,i.fuso_formularios,
               (u.status_pagamento IS TRUE AND i.integracao_ativa AND i.contrato_validado
                AND c.iniciou_em >= i.ativada_em) AS aplicavel, c.contexto_coleta, u.status_pagamento
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
                "aba",
                "fuso",
                "aplicavel",
                "coleta",
                "unidade_ativa",
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
```

## Passo 6 — `core/repositories/fireads/pendencias.py`

Ação: **alterar**. Conteúdo completo abaixo.

SHA-256 anterior: `68b1480feacc5e93ffdbc460ae5eeccb8ba9ae510f9f68ffb4f06bcb6a28e8ce`.

SHA-256 proposto (UTF-8/LF): `3dae7ba5c8301b1db140c9ed4583afa4b6d45dfde16d4af36731ccce110f6cec`.

```python
"""Fila durável de consultas; SQL sem HTTP e sem controle de transações."""

from psycopg.types.json import Jsonb
from core.integrations.fireads.aba_geral import VERSAO_CONSULTA


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
              AND i.aba_destino=q.entrada->>'aba' AND q.entrada->>'versao'='2'
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

## Passo 7 — `workers/worker_consulta_dash/consulta.py`

Ação: **alterar**. Conteúdo completo abaixo.

SHA-256 anterior: `bc4aa0dcdfa9e61ea77ee3089759cc5ca76ef1fefff759126902132c2b9c8f3b`.

SHA-256 proposto (UTF-8/LF): `3e71fe05ece5727198013a358cfc664016d6b10c97fc5da8b8289193571c9ae4`.

```python
"""Leitura da aba geral, sem persistência ou envio de mensagens."""

import logging
import time

from core.integrations.fireads.cliente import ClienteFireAds, PrazoConsultaFireAdsEsgotado
from core.integrations.fireads.contrato import ErroFireAds, localizar
from core.integrations.fireads.aba_geral import VERSAO_CONSULTA
from core.integrations.fireads.coleta_abertura import interpretar_parcial
from workers.worker_consulta_dash.resultado import decisao_organica, interpretar

logger = logging.getLogger("worker.consulta_dash.http")


def consultar(reserva):
    entrada = reserva["entrada"]
    inicio = time.monotonic()
    cliente = None
    try:
        cliente = ClienteFireAds(entrada["url"], segundos=float(reserva["restante"]),
                                timeout_leitura=None)
        if entrada.get("versao") != VERSAO_CONSULTA:
            raise ErroFireAds("Versão de consulta desconhecida")
        geral = cliente.consultar(entrada["aba"])
        if not {"Nome", "Email", "WhatsApp", "Para quem é", "Canal", "Data/Hora"} <= set(geral["headers"]):
            return {"decisao": decisao_organica("erro", "cabecalhos_ausentes"), "fontes": {}}
        numero = entrada["numero"]
        if entrada.get("coleta") is not None:
            if entrada['coleta'].get('versao') != 1:
                raise ErroFireAds('Versão de coleta desconhecida')
            decisao = interpretar_parcial(geral['rows'], numero, entrada['fuso'], entrada['aba'], entrada['coleta'])
        else:
            decisao = interpretar(geral["rows"], numero, entrada["fuso"], aba=entrada["aba"])
        # O banco recebe apenas os registros deste contato e a decisão completa.
        fontes = {
            "geral": localizar(geral["rows"], numero, "WhatsApp", incluir_equivalentes=True),
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
```

## Passo 8 — `workers/worker_flow/fireads.py`

Ação: **alterar**. Conteúdo completo abaixo.

SHA-256 anterior: `32cccf2a64cc0bc1eb51d396847a4b6007833eaa0e06139986c4225bd5b8bed8`.

SHA-256 proposto (UTF-8/LF): `9ce3e627ae2c8ad5353f0476db18ebf33e0b6954a1013071ce796e84c267408a`.

```python
"""Prepara somente a abertura, consumindo a consulta persistida pelo outro worker."""

from core.integrations.fireads.extratores import extrair_email
from core.integrations.fireads.aba_geral import configuracao_compativel
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
    from workers.worker_flow.coleta_abertura import preparar, anexar
    cid = contexto_banco['conversa']['id_conversa']
    abertura = buscar_abertura(cid, cursor)
    if 'unidade_ativa' in abertura and abertura['unidade_ativa'] is not True:
        return contexto_banco
    if abertura.get('coleta'):
        if abertura['etapa'] is not None:
            return anexar(contexto_banco, abertura['coleta'], abertura.get('contexto'))
        return preparar(contexto_banco, mensagem, lock_version, cursor, abertura, pendencias.buscar(cid, cursor))
    # Contextos e consultas anteriores ao deploy conservam o contrato original.
    if 'coleta' not in abertura or abertura.get('contexto') or abertura['etapa'] is not None:
        return _preparar_abertura_legada(contexto_banco, mensagem, lock_version, cursor)
    consulta = pendencias.buscar(cid, cursor)
    if consulta is not None:
        return _preparar_abertura_legada(contexto_banco, mensagem, lock_version, cursor)
    return preparar(contexto_banco, mensagem, lock_version, cursor, abertura, None)


def _preparar_abertura_legada(contexto_banco, mensagem, lock_version, cursor):
    """Não executa HTTP nem commit. O orquestrador confirma também a espera."""
    cid = contexto_banco["conversa"]["id_conversa"]
    abertura = buscar_abertura(cid, cursor)
    if abertura["contexto"]:
        return aplicar_contexto(contexto_banco, abertura["contexto"])
    if abertura["etapa"] is not None:
        return contexto_banco  # Nunca reconsultar ou retroceder uma etapa iniciada.
    proteger_conversa(cid, lock_version, cursor)
    proteger_mensagem_abertura(mensagem, cursor)
    consulta_nova = False
    consulta = pendencias.buscar(cid, cursor)
    if consulta is None:
        if not abertura["aplicavel"]:
            return contexto_banco
        consulta_nova = pendencias.solicitar(abertura, cid, mensagem["cliente_telefone"], cursor)
        consulta = pendencias.buscar(cid, cursor)
    motivo = None
    if not abertura["aplicavel"]:
        motivo = "integracao_desativada"
    elif consulta["id_integracao"] != abertura["id_integracao"] or not configuracao_compativel(
        consulta["entrada"], abertura
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
        raise ConsultaFireAdsPendente("aguardando_resultado", consulta_nova=consulta_nova)
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
            decisao = decisao_organica(
                "incompleto", "conflito_email", referencia=decisao.get("referencia")
            )
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
    """Confia na coleta FireAds desta conversa, sem revalidar como texto de chat."""
    # Nome histórico da API mantido para replay dos eventos 7/9 -> 11.
    if contexto.get('contexto_coleta'):
        from core.validacoes.coleta_abertura import email_coletado
        return email_coletado(contexto)
    estado = contexto.get("contexto_fireads") or {}
    return (
        estado.get("concluida") is True
        and estado.get("resultado") == "importado"
        and estado.get("id_conversa") == contexto.get("id_conversa")
        and estado.get("dados_titular", {}).get("resultado_email") == "email_valido"
        and bool(extrair_email(estado.get("dados_titular", {}).get("email")))
    )
```

## Passo 9 — `core/integrations/whatsapp/messages/abertura_coleta.py`

Ação: **criar**. Conteúdo completo abaixo.

SHA-256 anterior: `arquivo novo`.

SHA-256 proposto (UTF-8/LF): `94d0887df9fe86ce1e339407858ed80cedb2c4f4fbec1d9aa2e5e982306f5e63`.

```python
"""Apresentação única e pergunta correspondente ao primeiro campo necessário."""

from core.validacoes.coleta_abertura import valor, validar_contexto
from core.integrations.whatsapp.messages.etapa2_messages import MENSAGEM_REPETICAO_ETAPA2
from core.integrations.whatsapp.messages.etapa4_messages import MENSAGEM_REPETICAO_ETAPA4
from core.integrations.whatsapp.messages.tratamentos.financeiro import montar_mensagem_tratamento_financeiro
from core.integrations.whatsapp.messages.tratamentos.midia import montar_mensagem_tratamento_midia
from core.integrations.whatsapp.messages.tratamentos.reforco_escolar import montar_mensagem_tratamento_reforco_escolar


def montar_abertura(contexto, saudacao, tratamento=None):
    estado = validar_contexto(contexto)
    if not estado:
        raise ValueError('Abertura parcial sem contexto')
    genero = contexto.get('genero')
    if genero not in {'feminino', 'masculino'} or not all(contexto.get(c) for c in ('nome_agente', 'nome_unidade')):
        raise ValueError('Apresentação da unidade incompleta')
    nome = valor(estado, 'nome')
    saudacao = f'{saudacao}, {nome}!' if nome else f'{saudacao}!'
    artigo = 'a' if genero == 'feminino' else 'o'
    apresentacao = f"{saudacao} Sou {artigo} {contexto['nome_agente']}, assistente do {contexto['nome_unidade']}. ☺️"
    if estado['formulario_identificado']:
        apresentacao += ('\n\nVi que você já preencheu um dos nossos formulários. Para continuarmos '
                         'com sua reserva por cortesia da unidade vamos precisar fazer mais algumas perguntinhas, ok?')
    pergunta = {1: 'Me diz, qual o seu nome?', 2: MENSAGEM_REPETICAO_ETAPA2,
                4: MENSAGEM_REPETICAO_ETAPA4}[estado['etapa_inicial']]
    tratamentos = {'pergunta_financeira': montar_mensagem_tratamento_financeiro,
                   'duvida_reforco_escolar': montar_mensagem_tratamento_reforco_escolar,
                   'tipo_mensagem_nao_suportado': montar_mensagem_tratamento_midia}
    if tratamento:
        pergunta = tratamentos[tratamento](pergunta)
    return apresentacao + '\n\n' + pergunta
```

## Passo 10 — `core/integrations/whatsapp/pywa_functions/pywa_senders/abertura_coleta.py`

Ação: **criar**. Conteúdo completo abaixo.

SHA-256 anterior: `arquivo novo`.

SHA-256 proposto (UTF-8/LF): `ddd1128fe2fd7b9ab34b64bc0119a482487e2b77f7e3d29d61f2f597c198c57f`.

```python
"""Envio da abertura adaptada com o contrato de persistência dos demais senders."""

from pywa.types import Button
from core.integrations.whatsapp.exceptions import ErroEnvioMeta
from core.integrations.whatsapp.messages.abertura_coleta import montar_abertura
from core.integrations.whatsapp.messages.etapa2_messages import montar_botoes_etapa2
from core.integrations.whatsapp.messages.componentes_compartilhados import RODAPE_OPCAO_UNICA, montar_texto_com_rodape
from core.integrations.whatsapp.pywa_functions.cliente import conta_wa
from core.integrations.whatsapp.pywa_functions.resposta_envio import extrair_id_hash_msg_bot
from core.integrations.whatsapp.pywa_functions.saudacao import obter_saudacao_por_horario


def enviar_abertura_coleta(contexto, *, tratamento=None):
    mensagem = contexto['mensagem_cliente_atual']
    etapa = contexto['contexto_coleta']['etapa_inicial']
    texto = montar_abertura(contexto, obter_saudacao_por_horario(), tratamento)
    argumentos = {'to': mensagem['cliente_telefone'], 'text': texto}
    if etapa == 2:
        texto = montar_texto_com_rodape(texto, RODAPE_OPCAO_UNICA)
        argumentos.update(text=texto, buttons=[Button(title=b, callback_data=b) for b in montar_botoes_etapa2()])
    try:
        enviado = conta_wa(mensagem['id_phone_unidade']).send_message(**argumentos)
        resultado = {'enviou': True, 'resposta_ja_existia': False, 'mensagem_bot': texto,
                     'id_hash_msg_bot': extrair_id_hash_msg_bot(enviado), 'id_etapa_resultante': etapa,
                     'tipo_mensagem': 'interactive_button' if etapa == 2 else 'text',
                     'canal': 'meta_whatsapp', 'atualizar_conversa': True, 'atualizar_last_from_bot': True}
        if etapa == 2:
            resultado['rodape_mensagem'] = RODAPE_OPCAO_UNICA
        if tratamento:
            resultado.update(tratamento=True, tipo_tratamento=tratamento)
        return resultado
    except Exception as erro:
        raise ErroEnvioMeta('Meta falhou ao enviar abertura adaptada', id_etapa=etapa,
                            phone_id_unidade=mensagem['id_phone_unidade'],
                            cliente_telefone=mensagem['cliente_telefone']) from erro
```

## Passo 11 — `workers/worker_flow/valida_historico.py`

Ação: **alterar**. Conteúdo completo abaixo.

SHA-256 anterior: `4881f53733f8eb1d224de7d392b25945c375e1b7c91784dc98fa497f54768987`.

SHA-256 proposto (UTF-8/LF): `f9ca6dd99d375ed3efe0ad4f61fcdd38311b398dba61d8d242d3716a461e82f7`.

```python
import logging
from workers.worker_flow.fireads import email_importado
from core.validacoes.coleta_abertura import validar_contexto


from core.logging_config import short_value
from core.integrations.whatsapp.messages.tratamentos.retorno_inatividade import (
    montar_saudacao_retorno,
)
from core.repositories.atendimento.conversas import (
    atualizar_conversa_mensagem_cliente,
    atualizar_conversa_resposta_bot_sem_avancar,
)
from core.repositories.atendimento.historico import (
    buscar_contexto_saudacao_retorno,
    buscar_resposta_bot_por_mensagem_cliente,
    inserir_historico_mensagem_cliente,
)
from core.repositories.fluxo.contextos.etapa1 import buscar_contexto_etapa1
from core.repositories.fluxo.contextos.etapa6 import buscar_contexto_etapa6
from core.repositories.fluxo.contextos.etapa7 import buscar_contexto_etapa7
from core.repositories.fluxo.contextos.etapa9 import buscar_contexto_etapa9
from core.repositories.fluxo.contextos.etapa10 import buscar_contexto_etapa10
from core.repositories.fluxo.contextos.etapa18 import buscar_contexto_etapa18
from core.repositories.fluxo.contextos.etapa20 import buscar_contexto_etapa20
from core.repositories.fluxo.contextos.etapa24 import buscar_contexto_etapa24
from core.repositories.fluxo.contextos.triagem import buscar_contexto_triagem
from core.repositories.fluxo.transicoes import listar_transicoes_permitidas
from workers.worker_flow.response_flow.transicoes.contexto_transicao import (
    montar_contexto_transicao,
    prever_etapa_resposta,
)
from workers.worker_flow.response_flow.transicoes.eventos import (
    ETAPA_6_IDADE_ALUNO,
    ETAPA_7_OFERTA_AULA,
    ETAPA_8_OFERTA_ADIADA,
    ETAPA_9_RETORNO_OFERTA,
    ETAPA_10_EMAIL,
    ETAPA_11_INTRODUCAO_TRIAGEM,
    ETAPA_12_TRIAGEM_PERGUNTA_1,
    ETAPA_13_TRIAGEM_PERGUNTA_2,
    ETAPA_14_TRIAGEM_PERGUNTA_3,
    ETAPA_15_TRIAGEM_PERGUNTA_4,
    ETAPA_16_TRIAGEM_PERGUNTA_5,
    ETAPA_17_TRIAGEM_PERGUNTA_6,
    ETAPA_18_ESCOLHA_TURNO,
    ETAPA_19_ENCAMINHAMENTO_COMERCIAL,
    ETAPA_20_AGENDAMENTO,
    ETAPA_22_DECISAO_COMENTARIO,
    ETAPA_23_COMENTARIO_SATISFACAO,
)


logger = logging.getLogger("worker.valida_historico")

ETAPA_INICIAL = 1

ETAPAS_TRIAGEM = {
    ETAPA_11_INTRODUCAO_TRIAGEM,
    ETAPA_12_TRIAGEM_PERGUNTA_1,
    ETAPA_13_TRIAGEM_PERGUNTA_2,
    ETAPA_14_TRIAGEM_PERGUNTA_3,
    ETAPA_15_TRIAGEM_PERGUNTA_4,
    ETAPA_16_TRIAGEM_PERGUNTA_5,
    ETAPA_17_TRIAGEM_PERGUNTA_6,
}


def valida_historico(mensagem, contexto_banco, cursor, *, retorno_followup=False):
    contexto_conversa = contexto_banco["conversa"]
    id_conversa = contexto_conversa["id_conversa"]

    last_message_from_entrada = contexto_conversa.get("last_message_from")
    id_etapa_para_insert = _resolver_etapa_cliente(contexto_conversa)
    coleta = contexto_banco.get('contexto_coleta')
    if coleta and contexto_conversa.get('id_etapa_atual') is None:
        estado = validar_contexto({'id_conversa': id_conversa, 'contexto_coleta': coleta})
        id_etapa_para_insert = estado['etapa_inicial']
    # A primeira interação importada pertence à pergunta de profissão.
    # Assim seu replay permanece na etapa 4 sem simular uma transição 1 -> 4.
    if not coleta and contexto_conversa.get("id_etapa_atual") is None and email_importado({
        "id_conversa": id_conversa,
        "contexto_fireads": contexto_banco.get("contexto_fireads"),
    }):
        id_etapa_para_insert = 4

    (
        id_historico_cliente,
        data_historico_cliente,
        id_etapa_cliente,
        cliente_inserido_no_historico,
    ) = inserir_historico_mensagem_cliente(
        mensagem=mensagem,
        id_conversa=id_conversa,
        id_etapa=id_etapa_para_insert,
        cursor=cursor,
    )

    mensagem_cliente_atual = {
        "id_mensagem": id_historico_cliente,
        "id_conversa": id_conversa,
        "id_etapa": id_etapa_cliente,
        "received_data_hora": data_historico_cliente,
        "cliente_telefone": mensagem["cliente_telefone"],
        "conteudo_texto": mensagem["conteudo_texto"],
        "tipo_mensagem": mensagem["tipo_mensagem"],
        "id_hash_msg": mensagem["id_hash"],
        "id_mensagem_fila": mensagem["id_mensagem"],
        "id_hash_cliente_origem": None,
        "id_phone_unidade": mensagem["id_phone_unidade"],
        "unidade_telefone": mensagem["unidade_telefone"],
        "quem_enviou": "cliente",
        "status_envio": None,
    }

    resposta_bot_para_mensagem_atual = _normalizar_resposta_bot(
        buscar_resposta_bot_por_mensagem_cliente(
            id_conversa=id_conversa,
            id_mensagem_fila=mensagem["id_mensagem"],
            id_hash_cliente_origem=mensagem["id_hash"],
            cursor=cursor,
        )
    )

    saudacao_retorno = None
    if (
        not retorno_followup
        and not resposta_bot_para_mensagem_atual
        and contexto_conversa.get("id_etapa_atual") not in {None, 1}
    ):
        nome_titular, ultima_mensagem_bot_em = (
            buscar_contexto_saudacao_retorno(
                id_conversa,
                contexto_banco["id_cliente"],
                cursor,
            )
        )
        saudacao_retorno = montar_saudacao_retorno(
            nome_titular,
            ultima_mensagem_bot_em,
            data_historico_cliente,
            contexto_conversa.get("id_etapa_atual"),
        )

        if saudacao_retorno:
            logger.info(
                "saudacao_retorno_ativada | acao=prefixar_resposta "
                "id_conversa=%s id_cliente=%s etapa=%s "
                "ultima_mensagem_bot_em=%s mensagem_cliente_em=%s",
                id_conversa,
                contexto_banco["id_cliente"],
                contexto_conversa.get("id_etapa_atual"),
                ultima_mensagem_bot_em,
                data_historico_cliente,
            )

    transicoes_permitidas = listar_transicoes_permitidas(
        id_etapa_cliente,
        cursor,
    )
    contexto_transicao = montar_contexto_transicao(
        id_etapa_cliente,
        transicoes_permitidas,
    )
    contexto_especifico_etapa = {}

    # Os dados de apresentação da unidade vêm do banco somente no primeiro
    # contato. Respostas posteriores da etapa 1 não repetem essa apresentação.
    if contexto_conversa.get("id_etapa_atual") is None:
        contexto_especifico_etapa.update(
            buscar_contexto_etapa1(
                contexto_banco["id_unidade"],
                cursor,
            )
        )

    if id_etapa_cliente == ETAPA_6_IDADE_ALUNO:
        contexto_especifico_etapa = buscar_contexto_etapa6(
            id_conversa,
            contexto_banco["id_unidade"],
            cursor,
        )

        if (
            contexto_conversa.get("status_dependente")
            and not contexto_especifico_etapa["nome_dependente"]
        ):
            raise ValueError(
                "Etapa 6 de dependente sem nome persistido"
            )

        if (
            not contexto_conversa.get("status_dependente")
            and not contexto_especifico_etapa["nome_titular"]
        ):
            raise ValueError(
                "Etapa 6 do cliente sem nome persistido"
            )

    if id_etapa_cliente == ETAPA_7_OFERTA_AULA:
        contexto_especifico_etapa = buscar_contexto_etapa7(
            id_conversa,
            contexto_banco["id_unidade"],
            cursor,
        )

        chave_nome = (
            "nome_dependente"
            if contexto_conversa.get("status_dependente")
            else "nome_titular"
        )
        if not contexto_especifico_etapa[chave_nome]:
            raise ValueError(
                "Etapa 7 sem nome do aluno persistido "
                f"(campo={chave_nome})"
            )

    if id_etapa_cliente in {
        ETAPA_8_OFERTA_ADIADA,
        ETAPA_9_RETORNO_OFERTA,
    }:
        contexto_especifico_etapa = buscar_contexto_etapa9(
            id_conversa,
            contexto_banco["id_unidade"],
            cursor,
        )

        if not contexto_especifico_etapa["nome_titular"]:
            raise ValueError(
                "Retorno da etapa 9 sem nome do cliente persistido "
                f"(etapa={id_etapa_cliente})"
            )

        if (
            contexto_conversa.get("status_dependente")
            and not contexto_especifico_etapa["nome_dependente"]
        ):
            raise ValueError(
                "Retorno de dependente sem nome persistido "
                f"(etapa={id_etapa_cliente})"
            )

    if id_etapa_cliente == ETAPA_10_EMAIL:
        contexto_email = buscar_contexto_etapa10(
            id_conversa,
            contexto_banco["id_unidade"],
            cursor,
        )
        status_dependente_email = contexto_email.pop(
            "status_dependente_contexto_email"
        )

        if status_dependente_email != contexto_conversa.get(
            "status_dependente"
        ):
            raise ValueError(
                "Etapa 10 com destino de atendimento inconsistente "
                f"(id_conversa={id_conversa})"
            )

        contexto_especifico_etapa.update(contexto_email)

    # As etapas 11-17 relêem do banco a pessoa atendida em cada ciclo. Assim,
    # retries reconstroem a mesma variante etária sem depender de memória.
    if id_etapa_cliente in ETAPAS_TRIAGEM:
        contexto_especifico_etapa.update(
            buscar_contexto_triagem(
                id_conversa,
                contexto_banco["id_unidade"],
                cursor,
            )
        )

        status_dependente = contexto_conversa.get("status_dependente")
        status_dependente_contexto = contexto_especifico_etapa[
            "status_dependente_contexto_triagem"
        ]

        if not isinstance(status_dependente, bool):
            raise ValueError(
                "Triagem sem destino de atendimento definido "
                f"(etapa={id_etapa_cliente}, id_conversa={id_conversa})"
            )

        if (
            not isinstance(status_dependente_contexto, bool)
            or status_dependente_contexto != status_dependente
        ):
            raise ValueError(
                "Triagem com destino de atendimento inconsistente "
                f"(etapa={id_etapa_cliente}, id_conversa={id_conversa})"
            )

        idade_pessoa_triagem = contexto_especifico_etapa[
            "idade_pessoa_triagem"
        ]
        if (
            isinstance(idade_pessoa_triagem, bool)
            or not isinstance(idade_pessoa_triagem, int)
            or idade_pessoa_triagem <= 0
            or idade_pessoa_triagem >= 100
        ):
            raise ValueError(
                "Triagem sem idade valida da pessoa atendida "
                f"(etapa={id_etapa_cliente}, id_conversa={id_conversa})"
            )

        if status_dependente and idade_pessoa_triagem < 4:
            raise ValueError(
                "Triagem de dependente abaixo da idade minima suportada "
                f"(etapa={id_etapa_cliente}, id_conversa={id_conversa})"
            )

        if not status_dependente and idade_pessoa_triagem < 18:
            raise ValueError(
                "Triagem de titular menor de idade "
                f"(etapa={id_etapa_cliente}, id_conversa={id_conversa})"
            )

        nome_dependente = contexto_especifico_etapa["nome_dependente"]
        if status_dependente and (
            not nome_dependente or not str(nome_dependente).strip()
        ):
            raise ValueError(
                "Triagem de dependente sem nome persistido "
                f"(etapa={id_etapa_cliente}, id_conversa={id_conversa})"
            )

        contexto_especifico_etapa.pop(
            "status_dependente_contexto_triagem"
        )

    # As rotas de reserva compartilham dados, mas só a etapa 20 exige plataforma.
    if id_etapa_cliente in {
        ETAPA_17_TRIAGEM_PERGUNTA_6,
        ETAPA_18_ESCOLHA_TURNO,
        ETAPA_19_ENCAMINHAMENTO_COMERCIAL,
    }:
        dados_reserva = buscar_contexto_etapa18(
            id_conversa, contexto_banco["id_unidade"], cursor
        )
        if dados_reserva.pop("status_dependente_reserva") != contexto_conversa.get(
            "status_dependente"
        ):
            raise ValueError(
                "Destino de atendimento divergente na preparação de sua reserva"
            )
        contexto_especifico_etapa.update(dados_reserva)
    elif (
        id_etapa_cliente == ETAPA_20_AGENDAMENTO
        and not resposta_bot_para_mensagem_atual
    ):
        # No replay, o histórico já comprova o envio e o mapa reconstrói a
        # transição. Uma alteração posterior no link não invalida esse envio.
        contexto_especifico_etapa.update(
            buscar_contexto_etapa20(id_conversa, contexto_banco["id_unidade"], cursor)
        )
    # Tanto a recusa na etapa 22 quanto o comentário na 23 podem enviar a 24.
    # Respostas já gravadas são reaproveitadas; não precisam remontar a despedida.
    if not resposta_bot_para_mensagem_atual and id_etapa_cliente in {
        ETAPA_22_DECISAO_COMENTARIO,
        ETAPA_23_COMENTARIO_SATISFACAO,
    }:
        contexto_finalizacao = buscar_contexto_etapa24(
            id_conversa,
            contexto_banco["id_unidade"],
            cursor,
        )
        status_dependente = contexto_conversa.get("status_dependente")
        if type(status_dependente) is not bool or status_dependente != (
            contexto_finalizacao.pop("status_dependente_contexto_finalizacao")
        ):
            raise ValueError("Destino do atendimento inconsistente para a finalização")
        contexto_especifico_etapa.update(contexto_finalizacao)

    if resposta_bot_para_mensagem_atual:
        id_etapa_resposta = resposta_bot_para_mensagem_atual["id_etapa"]

        if last_message_from_entrada != "bot":
            atualizar_conversa_resposta_bot_sem_avancar(
                id_conversa,
                resposta_bot_para_mensagem_atual["received_data_hora"],
                cursor,
            )

        last_message_from_saida = "bot"
    else:
        id_etapa_resposta = prever_etapa_resposta(
            contexto_conversa.get("id_etapa_atual"),
            contexto_transicao["transicoes_permitidas"],
            etapa_inicial=id_etapa_para_insert,
        )
        atualizar_conversa_mensagem_cliente(
            id_conversa,
            data_historico_cliente,
            cursor,
        )
        last_message_from_saida = "cliente"

    logger.info(
        "historico_validado | acao=registrar_cliente id_mensagem=%s id_historico=%s inserido=%s id_conversa=%s etapa_cliente=%s etapa_resposta_previa=%s eventos_transicao=%s last_from_entrada=%s last_from_saida=%s retry=%s resposta_bot_existente=%s cliente=%s phone_number_id=%s",
        mensagem["id_mensagem"],
        id_historico_cliente,
        cliente_inserido_no_historico,
        id_conversa,
        id_etapa_cliente,
        id_etapa_resposta,
        sorted(transicoes_permitidas),
        last_message_from_entrada,
        last_message_from_saida,
        mensagem["retry_count"],
        bool(resposta_bot_para_mensagem_atual),
        short_value(mensagem["cliente_telefone"]),
        short_value(mensagem["id_phone_unidade"]),
    )

    contexto_historico = {
        "contexto_fireads": contexto_banco.get("contexto_fireads"),
        "contexto_coleta": contexto_banco.get("contexto_coleta"),
        "id_conversa": id_conversa,
        "id_cliente": contexto_banco.get("id_cliente"),
        "id_unidade": contexto_banco.get("id_unidade"),
        "id_etapa_atual": contexto_conversa.get("id_etapa_atual"),
        "id_etapa_cliente": id_etapa_cliente,
        # Compatibilidade apenas para logs existentes. Este campo nunca decide
        # uma transição e pode ser None quando há mais de um destino.
        "id_etapa_resposta": id_etapa_resposta,
        "id_etapa_origem_transicao": contexto_transicao[
            "id_etapa_origem_transicao"
        ],
        "transicoes_permitidas": contexto_transicao[
            "transicoes_permitidas"
        ],
        "status_dependente": contexto_conversa.get("status_dependente"),
        "last_message_from": last_message_from_saida,
        "last_message_from_entrada": last_message_from_entrada,
        "mensagem_cliente_atual": mensagem_cliente_atual,
        "mensagem_cliente_inserida": cliente_inserido_no_historico,
        "resposta_bot_para_mensagem_atual": resposta_bot_para_mensagem_atual,
        "texto_cliente_atual": mensagem["conteudo_texto"],
        "tipo_mensagem_atual": mensagem["tipo_mensagem"],
        "retry_count": mensagem["retry_count"],
        "precisa_tratamento_erro": False,
        "motivo_tratamento_erro": None,
        "saudacao_retorno": saudacao_retorno,
    }
    contexto_historico.update(contexto_especifico_etapa)
    return contexto_historico


def _resolver_etapa_cliente(contexto_conversa):
    id_etapa_atual = contexto_conversa.get("id_etapa_atual")

    if id_etapa_atual is None:
        return ETAPA_INICIAL

    return id_etapa_atual


def _normalizar_linha_historico(registro):
    (
        id_mensagem,
        id_conversa,
        id_etapa,
        received_data_hora,
        cliente_telefone,
        conteudo_texto,
        tipo_mensagem,
        id_hash_msg,
        id_mensagem_fila,
        id_hash_cliente_origem,
        id_phone_unidade,
        unidade_telefone,
        quem_enviou,
        status_envio,
    ) = registro

    return {
        "id_mensagem": id_mensagem,
        "id_conversa": id_conversa,
        "id_etapa": id_etapa,
        "received_data_hora": received_data_hora,
        "cliente_telefone": cliente_telefone,
        "conteudo_texto": conteudo_texto,
        "tipo_mensagem": tipo_mensagem,
        "id_hash_msg": id_hash_msg,
        "id_mensagem_fila": id_mensagem_fila,
        "id_hash_cliente_origem": id_hash_cliente_origem,
        "id_phone_unidade": id_phone_unidade,
        "unidade_telefone": unidade_telefone,
        "quem_enviou": quem_enviou,
        "status_envio": status_envio,
    }


def _normalizar_resposta_bot(registro):
    if not registro:
        return None

    return _normalizar_linha_historico(registro)
```

## Passo 12 — `workers/worker_flow/response_flow/flow_sender.py`

Ação: **alterar**. Conteúdo completo abaixo.

SHA-256 anterior: `01f75c25786aa2b84355122afc4e2a8767b75c61c5123bdff91818ed22ed116d`.

SHA-256 proposto (UTF-8/LF): `cee2c858bb09ee4a7c2530e2f8cb4e70ecea698a954ace44725b783f72e2afba`.

```python
import logging
from workers.worker_flow.fireads import email_importado, classificar_tratamento_abertura
from core.integrations.whatsapp.pywa_functions.pywa_senders.etapa4 import enviar_abertura_fireads

from core.integrations.whatsapp.messages.componentes_compartilhados import (
    montar_texto_com_cabecalho,
)

from core.integrations.whatsapp.pywa_functions.cliente import (
    aplicar_prefixo_mensagem_bot,
    usar_prefixo_mensagem_bot,
)
from workers.worker_flow.response_flow.etapas.resolver_etapa1 import (
    resolve_etapa1,
)
from workers.worker_flow.response_flow.etapas.resolver_etapa2 import (
    resolve_etapa2,
)
from workers.worker_flow.response_flow.etapas.resolver_etapa3 import (
    resolve_etapa3,
)
from workers.worker_flow.response_flow.etapas.resolver_etapa4 import (
    resolve_etapa4,
)
from workers.worker_flow.response_flow.etapas.resolver_etapa5 import (
    resolve_etapa5,
)
from workers.worker_flow.response_flow.etapas.resolver_etapa6 import (
    resolve_etapa6,
)
from workers.worker_flow.response_flow.etapas.resolver_etapa7 import (
    resolve_etapa7,
)
from workers.worker_flow.response_flow.etapas.resolver_etapa8 import (
    resolve_etapa8,
)
from workers.worker_flow.response_flow.etapas.resolver_etapa9 import (
    resolve_etapa9,
)
from workers.worker_flow.response_flow.etapas.resolver_etapa10 import (
    resolve_etapa10,
)
from workers.worker_flow.response_flow.etapas.resolver_etapa11 import (
    resolve_etapa11,
)
from workers.worker_flow.response_flow.etapas.resolver_etapa12 import (
    resolve_etapa12,
)
from workers.worker_flow.response_flow.etapas.resolver_etapa13 import (
    resolve_etapa13,
)
from workers.worker_flow.response_flow.etapas.resolver_etapa14 import (
    resolve_etapa14,
)
from workers.worker_flow.response_flow.etapas.resolver_etapa15 import (
    resolve_etapa15,
)
from workers.worker_flow.response_flow.etapas.resolver_etapa16 import (
    resolve_etapa16,
)
from workers.worker_flow.response_flow.etapas.resolver_etapa17 import (
    resolve_etapa17,
)
from workers.worker_flow.response_flow.etapas.resolver_etapa18 import (
    resolve_etapa18,
)
from workers.worker_flow.response_flow.etapas.resolver_etapa19 import (
    resolve_etapa19,
)
from workers.worker_flow.response_flow.etapas.resolver_etapa20 import (
    resolve_etapa20,
)
from workers.worker_flow.response_flow.etapas.resolver_etapa21 import (
    resolve_etapa21,
)
from workers.worker_flow.response_flow.etapas.resolver_etapa22 import (
    resolve_etapa22,
)
from workers.worker_flow.response_flow.etapas.resolver_etapa23 import (
    resolve_etapa23,
)
from workers.worker_flow.response_flow.transicoes.resolver_transicao import (
    identificar_evento_por_destino,
)
from workers.worker_flow.response_flow.transicoes.eventos import (
    ETAPA_3_CONFIRMACAO_DESTINO,
    EVENTO_DESTINO_ATENDIMENTO_CONFIRMADO,
)


logger = logging.getLogger("worker.sender")


def flow_sender(contexto_historico):
    id_conversa = contexto_historico["id_conversa"]
    id_etapa_atual = contexto_historico.get("id_etapa_atual")
    retry_count = contexto_historico["retry_count"]

    mensagem_cliente_atual = contexto_historico["mensagem_cliente_atual"]
    cliente_atual_id_mensagem_fila = mensagem_cliente_atual["id_mensagem_fila"]
    cliente_atual_id_hash_msg = mensagem_cliente_atual["id_hash_msg"]

    resposta_bot_atual = (
        contexto_historico["resposta_bot_para_mensagem_atual"] or {}
    )

    # Esta barreira continua antes de qualquer resolver ou sender.
    if resposta_bot_atual:
        id_etapa_resposta = resposta_bot_atual.get("id_etapa")
        evento_transicao = identificar_evento_por_destino(
            contexto_historico,
            id_etapa_resposta,
        )

        logger.info(
            "flow_sender_idempotencia_ok | motivo=resposta_bot_ja_registrada acao=nao_enviar id_conversa=%s id_mensagem_fila=%s id_hash_cliente=%s id_resposta_bot=%s etapa_resposta=%s evento_transicao=%s retry=%s",
            id_conversa,
            cliente_atual_id_mensagem_fila,
            cliente_atual_id_hash_msg,
            resposta_bot_atual.get("id_mensagem"),
            id_etapa_resposta,
            evento_transicao,
            retry_count,
        )

        contexto_envio = {
            "enviou": False,
            "resposta_ja_existia": True,
            "id_hash_msg_bot": resposta_bot_atual.get("id_hash_msg"),
            "id_etapa_resultante": id_etapa_resposta,
            "id_etapa_origem_transicao": contexto_historico.get(
                "id_etapa_origem_transicao"
            ),
        }

        if evento_transicao:
            contexto_envio["evento_transicao"] = evento_transicao

        # Movimento e efeito são confirmados na mesma transação. No replay da
        # etapa 3, o status atual da conversa já é o valor final absoluto; não
        # reinterpretamos "Não" nem reaplicamos uma inversão.
        if (
            contexto_historico.get("id_etapa_origem_transicao")
            == ETAPA_3_CONFIRMACAO_DESTINO
            and evento_transicao
            == EVENTO_DESTINO_ATENDIMENTO_CONFIRMADO
        ):
            status_dependente_final = contexto_historico.get(
                "status_dependente"
            )
            if not isinstance(status_dependente_final, bool):
                raise ValueError(
                    "Replay da confirmacao da etapa 3 sem "
                    "status_dependente booleano persistido "
                    f"(valor={status_dependente_final!r})"
                )
            contexto_envio["status_dependente_final"] = (
                status_dependente_final
            )

        return contexto_envio

    if retry_count > 1:
        logger.info(
            "flow_sender_reprocessamento | motivo=retry_maior_que_um acao=continuar_sem_resposta_previa id_conversa=%s id_mensagem_fila=%s id_hash_cliente=%s retry=%s",
            id_conversa,
            cliente_atual_id_mensagem_fila,
            cliente_atual_id_hash_msg,
            retry_count,
        )

    if id_etapa_atual is None and contexto_historico.get('contexto_coleta'):
        from core.validacoes.coleta_abertura import validar_contexto, aceito
        from core.integrations.whatsapp.pywa_functions.pywa_senders.abertura_coleta import enviar_abertura_coleta
        coleta = validar_contexto(contexto_historico)
        if coleta['formulario_identificado'] or any(aceito(coleta, c) for c in ('nome', 'email', 'destinatario')):
            return enviar_abertura_coleta(contexto_historico, tratamento=classificar_tratamento_abertura(contexto_historico))
    if id_etapa_atual is None and not contexto_historico.get('contexto_coleta') and email_importado(contexto_historico):
        return enviar_abertura_fireads(
            contexto_historico,
            tratamento=classificar_tratamento_abertura(contexto_historico),
        )

    if id_etapa_atual is None or id_etapa_atual == 1:
        return _resolver_com_saudacao(resolve_etapa1, contexto_historico)

    if id_etapa_atual == 2:
        return _resolver_com_saudacao(
            resolve_etapa2,
            contexto_historico,
        )

    if id_etapa_atual == 3:
        return _resolver_com_saudacao(
            resolve_etapa3,
            contexto_historico,
        )

    if id_etapa_atual == 4:
        return _resolver_com_saudacao(
            resolve_etapa4,
            contexto_historico,
        )

    if id_etapa_atual == 5:
        return _resolver_com_saudacao(
            resolve_etapa5,
            contexto_historico,
        )

    if id_etapa_atual == 6:
        return _resolver_com_saudacao(
            resolve_etapa6,
            contexto_historico,
        )

    if id_etapa_atual == 7:
        return _resolver_com_saudacao(
            resolve_etapa7,
            contexto_historico,
        )

    if id_etapa_atual == 8:
        return _resolver_com_saudacao(
            resolve_etapa8,
            contexto_historico,
        )

    if id_etapa_atual == 9:
        return _resolver_com_saudacao(
            resolve_etapa9,
            contexto_historico,
        )

    if id_etapa_atual == 10:
        return _resolver_com_saudacao(
            resolve_etapa10,
            contexto_historico,
        )

    if id_etapa_atual == 11:
        return _resolver_com_saudacao(
            resolve_etapa11,
            contexto_historico,
        )

    if id_etapa_atual == 12:
        return _resolver_com_saudacao(
            resolve_etapa12,
            contexto_historico,
        )

    if id_etapa_atual == 13:
        return _resolver_com_saudacao(
            resolve_etapa13,
            contexto_historico,
        )

    if id_etapa_atual == 14:
        return _resolver_com_saudacao(
            resolve_etapa14,
            contexto_historico,
        )

    if id_etapa_atual == 15:
        return _resolver_com_saudacao(
            resolve_etapa15,
            contexto_historico,
        )

    if id_etapa_atual == 16:
        return _resolver_com_saudacao(
            resolve_etapa16,
            contexto_historico,
        )

    if id_etapa_atual == 17:
        return _resolver_com_saudacao(
            resolve_etapa17,
            contexto_historico,
        )

    if id_etapa_atual == 18:
        return _resolver_com_saudacao(
            resolve_etapa18,
            contexto_historico,
        )

    if id_etapa_atual == 19:
        return _resolver_com_saudacao(
            resolve_etapa19,
            contexto_historico,
        )

    if id_etapa_atual == 20:
        return _resolver_com_saudacao(
            resolve_etapa20,
            contexto_historico,
        )

    if id_etapa_atual == 21:
        return _resolver_com_saudacao(
            resolve_etapa21,
            contexto_historico,
        )

    if id_etapa_atual == 22:
        return _resolver_com_saudacao(
            resolve_etapa22,
            contexto_historico,
        )

    if id_etapa_atual == 23:
        return _resolver_com_saudacao(
            resolve_etapa23,
            contexto_historico,
        )

    # A etapa 24 é terminal e não possui resolver. Conversas encerradas são
    # barradas pelo cache/webhook e pelo fallback transacional do worker.

    logger.warning(
        "flow_sender_etapa_pendente | acao=nao_enviar id_conversa=%s etapa=%s",
        id_conversa,
        id_etapa_atual,
    )
    raise NotImplementedError(
        f"Sender da etapa atual {id_etapa_atual} ainda nao implementado"
    )


def _resolver_com_saudacao(resolver, contexto_historico):
    """Aplica a saudação sem alterar o despacho legado das etapas."""
    saudacao_retorno = contexto_historico.get("saudacao_retorno")

    with usar_prefixo_mensagem_bot(saudacao_retorno):
        contexto_envio = resolver(contexto_historico)

    if saudacao_retorno and contexto_envio.get("mensagem_bot"):
        contexto_envio = dict(contexto_envio)
        texto = contexto_envio["mensagem_bot"]
        if contexto_envio.get("cabecalho_mensagem"):
            # O sender enviou este cabeçalho no corpo, antes de aplicar o prefixo.
            # O histórico deve refletir exatamente a mesma ordem do WhatsApp.
            texto = montar_texto_com_cabecalho(
                texto, contexto_envio["cabecalho_mensagem"]
            )
        contexto_envio["mensagem_bot"] = aplicar_prefixo_mensagem_bot(
            texto,
            saudacao_retorno,
        )
        contexto_envio["saudacao_retorno_aplicada"] = True

    return contexto_envio
```

## Passo 13 — `workers/worker_flow/transacoes/movimento_conversa.py`

Ação: **alterar**. Conteúdo completo abaixo.

SHA-256 anterior: `a0a15e6a453715b44543594178a4a453b9bb1143e48d9efa63bb34fed0522219`.

SHA-256 proposto (UTF-8/LF): `b0cccd9bab08614949326d92cad8ce06c3e4ae9c4667a6dfee033522ba31a619`.

```python
from workers.worker_flow.fireads import email_importado
from core.validacoes.coleta_abertura import validar_contexto
from core.repositories.atendimento.conversas import (
    atualizar_conversa_por_transicao,
    atualizar_conversa_resposta_bot_sem_avancar,
    inicializar_conversa_resposta_bot,
)
from workers.worker_flow.response_flow.transicoes.eventos import (
    ETAPA_1_NOME_CLIENTE,
)


MOVIMENTO_INICIALIZACAO = "inicializacao"
MOVIMENTO_TRANSICAO = "transicao"
MOVIMENTO_SEM_AVANCO = "sem_avanco"


def persistir_movimento_conversa(
    contexto_historico,
    contexto_envio,
    data_interacao_bot,
    cursor,
):
    movimento = resolver_movimento_conversa(
        contexto_historico,
        contexto_envio,
    )
    id_conversa = contexto_historico["id_conversa"]
    id_etapa_destino = contexto_envio.get("id_etapa_resultante")

    if movimento == MOVIMENTO_INICIALIZACAO:
        inicializar_conversa_resposta_bot(
            id_conversa,
            id_etapa_destino,
            data_interacao_bot,
            cursor,
        )
        return movimento

    if movimento == MOVIMENTO_TRANSICAO:
        atualizar_conversa_por_transicao(
            id_conversa,
            contexto_historico["id_etapa_origem_transicao"],
            contexto_envio["evento_transicao"],
            id_etapa_destino,
            data_interacao_bot,
            cursor,
            permitir_reaplicacao=bool(
                contexto_envio.get("resposta_ja_existia")
            ),
        )
        return movimento

    atualizar_conversa_resposta_bot_sem_avancar(
        id_conversa,
        data_interacao_bot,
        cursor,
    )
    return movimento


def resolver_movimento_conversa(
    contexto_historico,
    contexto_envio,
):
    etapa_atual = contexto_historico.get("id_etapa_atual")
    etapa_origem = contexto_historico.get(
        "id_etapa_origem_transicao"
    )
    etapa_destino = contexto_envio.get("id_etapa_resultante")
    evento_transicao = contexto_envio.get("evento_transicao")
    tratamento = bool(contexto_envio.get("tratamento"))

    if etapa_destino is None:
        raise ValueError("Resposta do bot sem id_etapa_resultante")

    # Primeiro contato: apenas apresenta a etapa 1, sem transição.
    if etapa_atual is None:
        coleta = validar_contexto(contexto_historico)
        autorizada = coleta['etapa_inicial'] if coleta else (4 if email_importado(contexto_historico) else ETAPA_1_NOME_CLIENTE)
        if etapa_destino != autorizada:
            raise ValueError(
                "Inicializacao exige etapa 1 ou importacao FireAds completa na etapa 4"
            )

        if evento_transicao:
            raise ValueError(
                "Inicializacao da conversa nao aceita evento de transicao"
            )

        return MOVIMENTO_INICIALIZACAO

    # Uma resposta válida produz evento e pode mudar de etapa.
    if evento_transicao:
        if tratamento:
            raise ValueError(
                "Tratamento nao pode avancar por evento de transicao"
            )

        if etapa_origem is None:
            raise ValueError(
                "Evento de transicao sem etapa de origem persistida"
            )

        return MOVIMENTO_TRANSICAO

    # Tratamentos não produzem evento e obrigatoriamente permanecem na origem.
    if etapa_destino != etapa_origem:
        raise ValueError(
            "Resposta sem evento tentou alterar a etapa da conversa "
            f"(origem={etapa_origem}, destino={etapa_destino})"
        )

    return MOVIMENTO_SEM_AVANCO
```

## Passo 14 — `core/repositories/atendimento/conversas.py`

Ação: **alterar**. Conteúdo completo abaixo.

SHA-256 anterior: `f15e810b78b651b3be6800194911ca832f897126d804719ec7f51dceba35875c`.

SHA-256 proposto (UTF-8/LF): `25093d28c14a1e27928ece4a432a6a00c2b4629354050d386aedc66217a6d072`.

```python
import logging

from core.validacoes.encerramento_por_idade import MOTIVOS_IDADE


logger = logging.getLogger("db.atendimento.conversas")

ETAPA_INICIAL = 1

# Catálogo compartilhado: preserva os motivos de follow-up e agendamento.
MOTIVOS_ENCERRAMENTO_VALIDOS = MOTIVOS_IDADE | {'foi_agendado', 'followup_sem_resposta'}


def inserindo_em_conversa_caso_seja_nova(id_cliente, id_unidade, cursor):
    cursor.execute("""
        INSERT INTO chatbot.chat (id_cliente, id_unidade) VALUES (%s, %s)
        ON CONFLICT (id_cliente, id_unidade) DO UPDATE SET id_cliente=EXCLUDED.id_cliente
        RETURNING id_chat;
    """, (id_cliente, id_unidade))
    id_chat = cursor.fetchone()[0]
    cursor.execute("""
        INSERT INTO chatbot.conversa (
            id_chat,
            id_cliente,
            id_unidade,
            last_interaction_at,
            last_message_from
        )
        VALUES (%s, %s, %s, NOW(), 'cliente')
        RETURNING id_conversa;
    """, (id_chat, id_cliente, id_unidade))

    resultado = cursor.fetchone()

    if resultado:
        logger.debug(
            "conversa_insert_resultado | acao=criar_conversa id_cliente=%s id_unidade=%s id_conversa=%s",
            id_cliente,
            id_unidade,
            resultado[0],
        )
        return resultado[0]

    raise ValueError(
        f"Anomalia Crítica: conversa do cliente {id_cliente} "
        f"e unidade {id_unidade} não foi criada!"
    )


def tentar_lock_conversa(id_conversa, cursor):
    cursor.execute(
        "SELECT lock_ok, lock_version_atual "
        "FROM chatbot.lock_conversa(%s);",
        (id_conversa,),
    )
    resultado = cursor.fetchone()

    if not resultado:
        logger.warning(
            "conversa_lock_sem_retorno | acao=negar_lock id_conversa=%s",
            id_conversa,
        )
        return False, None

    logger.debug(
        "conversa_lock_resultado | acao=lock id_conversa=%s lock_ok=%s lock_version=%s",
        id_conversa,
        bool(resultado[0]),
        resultado[1],
    )
    return bool(resultado[0]), resultado[1]


def unlock_conversa(id_conversa, lock_version, cursor):
    if lock_version is None:
        return False

    cursor.execute(
        "SELECT chatbot.unlock_conversa(%s, %s);",
        (id_conversa, lock_version),
    )
    resultado = cursor.fetchone()
    logger.debug(
        "conversa_unlock_resultado | acao=unlock id_conversa=%s lock_version=%s liberada=%s",
        id_conversa,
        lock_version,
        bool(resultado[0]) if resultado else False,
    )
    return bool(resultado[0]) if resultado else False


def buscar_estado_conversa(id_cliente, id_unidade, cursor):
    cursor.execute("""
        WITH conversa_ativa AS (
            SELECT
                id_conversa,
                id_etapa_atual,
                status_ativa,
                finalizou_em,
                'ativa' AS estado,
                status_dependente,
                last_message_from,
                followup_stage,
                followup_last_sent_at,
                lead_no_funil
            FROM chatbot.conversa
            WHERE id_cliente = %s
              AND id_unidade = %s
              AND status_ativa = TRUE
            LIMIT 1
        ),
        ultima_conversa AS (
            SELECT
                c.id_conversa,
                c.id_etapa_atual,
                c.status_ativa,
                c.finalizou_em,
                CASE
                    WHEN COALESCE(e.bloqueio_dias, 0) > 0
                     AND c.finalizou_em
                         > NOW() - (
                             COALESCE(e.bloqueio_dias, 0)
                             * INTERVAL '1 day'
                         )
                    THEN 'bloqueada'
                    ELSE 'liberada'
                END AS estado,
                c.status_dependente,
                c.last_message_from,
                c.followup_stage,
                c.followup_last_sent_at,
                c.lead_no_funil
            FROM chatbot.conversa c
            LEFT JOIN chatbot.etapa e
              ON e.id_etapa = c.id_etapa_atual
            WHERE c.id_cliente = %s
              AND c.id_unidade = %s
              AND c.status_ativa = FALSE
            ORDER BY c.finalizou_em DESC
            LIMIT 1
        )
        SELECT
            id_conversa,
            id_etapa_atual,
            status_ativa,
            finalizou_em,
            estado,
            status_dependente,
            last_message_from,
            followup_stage,
            followup_last_sent_at,
            lead_no_funil
        FROM conversa_ativa

        UNION ALL

        SELECT
            id_conversa,
            id_etapa_atual,
            status_ativa,
            finalizou_em,
            estado,
            status_dependente,
            last_message_from,
            followup_stage,
            followup_last_sent_at,
            lead_no_funil
        FROM ultima_conversa
        WHERE NOT EXISTS (SELECT 1 FROM conversa_ativa)

        LIMIT 1;
    """, (id_cliente, id_unidade, id_cliente, id_unidade))

    resultado = cursor.fetchone()
    logger.debug(
        "conversa_estado_consultado | acao=buscar_estado id_cliente=%s id_unidade=%s encontrada=%s estado=%s",
        id_cliente,
        id_unidade,
        bool(resultado),
        resultado[4] if resultado else None,
    )
    return resultado


def atualizar_conversa_mensagem_cliente(
    id_conversa,
    data_interacao,
    cursor,
):
    if data_interacao is None:
        raise ValueError(
            "data_interacao nao informada para registrar mensagem do cliente"
        )

    cursor.execute("""
        UPDATE chatbot.conversa
        SET
            last_message_from = 'cliente',
            last_interaction_at = %s
        WHERE id_conversa = %s;
    """, (data_interacao, id_conversa))

    logger.debug(
        "conversa_update | acao=registrar_mensagem_cliente id_conversa=%s data_interacao=%s linhas=%s",
        id_conversa,
        data_interacao,
        cursor.rowcount,
    )

    if cursor.rowcount != 1:
        raise ValueError(
            "Conversa nao foi atualizada com mensagem do cliente "
            f"(id_conversa={id_conversa}, linhas={cursor.rowcount})"
        )

    return cursor.rowcount


def inicializar_conversa_resposta_bot(
    id_conversa,
    id_etapa_resultante,
    data_interacao,
    cursor,
):
    if id_etapa_resultante not in {ETAPA_INICIAL, 2, 4}:
        raise ValueError(
            "Inicializacao exige etapa 1 ou importacao FireAds na etapa 4"
        )

    _validar_data_interacao_bot(data_interacao)

    cursor.execute("""
        UPDATE chatbot.conversa
        SET
            id_etapa_atual = %s,
            last_message_from = 'bot',
            last_interaction_at = %s
        WHERE id_conversa = %s
          AND id_etapa_atual IS NULL
          AND ((contexto_coleta IS NOT NULL
                AND contexto_coleta->>'status'='pronto'
                AND contexto_coleta->>'id_conversa'=id_conversa::text
                AND contexto_coleta->>'etapa_inicial'=%s::text)
              OR (contexto_coleta IS NULL AND (%s=1 OR (%s=4
                AND contexto_fireads->>'resultado'='importado'
                AND contexto_fireads->>'concluida'='true'
                AND contexto_fireads->>'id_conversa'=id_conversa::text))));
    """, (
        id_etapa_resultante,
        data_interacao,
        id_conversa,
        id_etapa_resultante,
        id_etapa_resultante,
        id_etapa_resultante,
    ))

    logger.debug(
        "conversa_update | acao=inicializar_etapa id_conversa=%s etapa=%s linhas=%s",
        id_conversa,
        id_etapa_resultante,
        cursor.rowcount,
    )

    if cursor.rowcount != 1:
        raise ValueError(
            "Conversa nao foi inicializada na etapa autorizada "
            f"(id_conversa={id_conversa}, linhas={cursor.rowcount})"
        )

    return cursor.rowcount


def atualizar_conversa_por_transicao(
    id_conversa,
    id_etapa_origem,
    evento_transicao,
    id_etapa_destino,
    data_interacao,
    cursor,
    *,
    permitir_reaplicacao=False,
):
    if id_etapa_origem is None:
        raise ValueError("Etapa de origem nao informada para transicao")

    if not evento_transicao:
        raise ValueError("Evento nao informado para transicao")

    if id_etapa_destino is None:
        raise ValueError("Etapa de destino nao informada para transicao")

    _validar_data_interacao_bot(data_interacao)

    cursor.execute(
        """
        UPDATE chatbot.conversa AS conversa
        SET
            id_etapa_atual = CASE
                WHEN conversa.id_etapa_atual = %s THEN %s
                ELSE conversa.id_etapa_atual
            END,
            last_message_from = 'bot',
            last_interaction_at = %s
        WHERE conversa.id_conversa = %s
          AND EXISTS (
              SELECT 1
              FROM chatbot.etapa_transicao AS transicao
              WHERE transicao.id_etapa_origem = %s
                AND transicao.evento = %s
                AND transicao.id_etapa_destino = %s
          )
          AND (
              conversa.id_etapa_atual = %s
              OR (
                  %s = TRUE
                  AND conversa.id_etapa_atual = %s
              )
          );
        """,
        (
            id_etapa_origem,
            id_etapa_destino,
            data_interacao,
            id_conversa,
            id_etapa_origem,
            evento_transicao,
            id_etapa_destino,
            id_etapa_origem,
            bool(permitir_reaplicacao),
            id_etapa_destino,
        ),
    )

    logger.debug(
        "conversa_update | acao=aplicar_transicao id_conversa=%s etapa_origem=%s evento=%s etapa_destino=%s reaplicacao=%s linhas=%s",
        id_conversa,
        id_etapa_origem,
        evento_transicao,
        id_etapa_destino,
        bool(permitir_reaplicacao),
        cursor.rowcount,
    )

    if cursor.rowcount != 1:
        raise ValueError(
            "Conversa nao foi atualizada; transicao inexistente, origem "
            "incompativel ou conversa ausente "
            f"(id_conversa={id_conversa}, origem={id_etapa_origem}, "
            f"evento={evento_transicao}, destino={id_etapa_destino}, "
            f"reaplicacao={bool(permitir_reaplicacao)}, "
            f"linhas={cursor.rowcount})"
        )

    return cursor.rowcount


def atualizar_conversa_resposta_bot_sem_avancar(
    id_conversa,
    data_interacao,
    cursor,
):
    _validar_data_interacao_bot(data_interacao)

    cursor.execute("""
        UPDATE chatbot.conversa
        SET
            last_message_from = 'bot',
            last_interaction_at = %s
        WHERE id_conversa = %s;
    """, (data_interacao, id_conversa))

    logger.debug(
        "conversa_update | acao=registrar_resposta_bot_sem_avancar id_conversa=%s data_interacao=%s linhas=%s",
        id_conversa,
        data_interacao,
        cursor.rowcount,
    )

    if cursor.rowcount != 1:
        raise ValueError(
            "Conversa nao foi atualizada com resposta do bot sem avancar etapa "
            f"(id_conversa={id_conversa}, linhas={cursor.rowcount})"
        )

    return cursor.rowcount


def atualizar_status_dependente_conversa(
    id_conversa,
    status_dependente,
    cursor,
):
    cursor.execute("""
        UPDATE chatbot.conversa
        SET status_dependente = %s
        WHERE id_conversa = %s;
    """, (bool(status_dependente), id_conversa))

    logger.debug(
        "conversa_update | acao=atualizar_status_dependente id_conversa=%s status_dependente=%s linhas=%s",
        id_conversa,
        bool(status_dependente),
        cursor.rowcount,
    )

    if cursor.rowcount != 1:
        raise ValueError(
            "Conversa nao foi atualizada com status_dependente "
            f"(id_conversa={id_conversa}, linhas={cursor.rowcount})"
        )

    return cursor.rowcount


def atualizar_profissao_conversa(id_conversa, profissao, cursor):
    if not id_conversa:
        raise ValueError(
            "id_conversa nao informado para atualizar profissao"
        )

    if not isinstance(profissao, str):
        raise ValueError("profissao deve ser um texto")

    profissao_normalizada = profissao.strip()

    if (
        not profissao_normalizada
        or len(profissao_normalizada) > 100
        or "\n" in profissao_normalizada
        or "\r" in profissao_normalizada
    ):
        raise ValueError(
            "profissao deve conter uma unica linha entre 1 e 100 caracteres"
        )

    cursor.execute(
        """
        UPDATE chatbot.conversa
        SET profissao = %s
        WHERE id_conversa = %s;
        """,
        (profissao_normalizada, id_conversa),
    )

    logger.debug(
        "conversa_update | acao=atualizar_profissao id_conversa=%s linhas=%s",
        id_conversa,
        cursor.rowcount,
    )

    if cursor.rowcount != 1:
        raise ValueError(
            "Conversa nao foi atualizada com profissao "
            f"(id_conversa={id_conversa}, linhas={cursor.rowcount})"
        )

    return cursor.rowcount


def encerrar_conversa(id_conversa, motivo_encerramento, cursor):
    if motivo_encerramento not in MOTIVOS_ENCERRAMENTO_VALIDOS:
        raise ValueError(
            "Motivo de encerramento invalido "
            f"(motivo={motivo_encerramento!r})"
        )

    cursor.execute(
        """
        UPDATE chatbot.conversa
        SET
            status_ativa = FALSE,
            finalizou_em = NOW(),
            motivo_encerramento = %s,
            processing = FALSE,
            processing_started_at = NULL
        WHERE id_conversa = %s
          AND status_ativa = TRUE
        RETURNING finalizou_em;
        """,
        (motivo_encerramento, id_conversa),
    )

    resultado = cursor.fetchone()

    if not resultado:
        raise RuntimeError(
            "Conversa não encerrada "
            f"(id_conversa={id_conversa}, linhas={cursor.rowcount})"
        )

    return resultado[0]


def _validar_data_interacao_bot(data_interacao):
    if data_interacao is None:
        raise ValueError(
            "data_interacao nao informada para registrar resposta do bot"
        )
```

## Passo 15 — `workers/worker_flow/response_flow/etapas/resolver_etapa1.py`

Ação: **alterar**. Conteúdo completo abaixo.

SHA-256 anterior: `6a12a962b7eedd034b6328ab9ca495ff48926d40630955b8a7101a6d60627785`.

SHA-256 proposto (UTF-8/LF): `357b15e71630168be2d032c85eead1818fcfab5a449a24778974409ab78e3c51`.

```python
import logging
from core.validacoes.coleta_abertura import destinatario_coletado, EVENTO_NOME_DESTINO_COLETADO
from core.integrations.whatsapp.pywa_functions.pywa_senders.etapa4 import enviar_etapa4

from workers.worker_flow.response_flow.repeticao_followup import (
    enviar_repeticao_followup,
)

from core.integrations.whatsapp.pywa_functions.pywa_senders.etapa1 import (
    enviar_etapa1,
    enviar_etapa1_contexto_nome_invalido,
    enviar_etapa1_financeiro,
    enviar_etapa1_financeiro_inicio,
    enviar_etapa1_informacoes_inicio,
    enviar_etapa1_midia,
    enviar_etapa1_midia_inicio,
    enviar_etapa1_reforco_escolar,
    enviar_etapa1_reforco_escolar_inicio,
)
from core.integrations.whatsapp.pywa_functions.pywa_senders.etapa2 import (
    enviar_etapa2,
)
from core.logging_config import short_value
from workers.worker_flow.response_flow.etapas.validadores_contexto.valida_inicio_etapa1 import (
    validar_pedido_informacoes_supera,
)
from workers.worker_flow.response_flow.etapas.validadores_universais.validador_financeiro import (
    TIPO_TRATAMENTO_FINANCEIRO,
    validar_pergunta_financeira,
)
from workers.worker_flow.response_flow.etapas.validadores_universais.validador_midia import (
    TIPO_TRATAMENTO_TIPO_NAO_SUPORTADO,
    validar_midia,
)
from workers.worker_flow.response_flow.etapas.validadores_universais.validador_reforco_escolar import (
    TIPO_TRATAMENTO_REFORCO_ESCOLAR,
    validar_duvida_reforco_escolar,
)
from workers.worker_flow.response_flow.etapas.validadores_universais.validador_nome import (
    TIPO_TRATAMENTO_NOME_INVALIDO,
    validar_nome_cliente,
)
from workers.worker_flow.response_flow.transicoes.eventos import (
    ETAPA_2_DESTINO_ATENDIMENTO,
    EVENTO_NOME_CLIENTE_VALIDO,
)
from workers.worker_flow.response_flow.transicoes.resolver_transicao import (
    anexar_transicao_ao_contexto_envio,
    resolver_destino_transicao,
)


"""
ESSE ARQUIVO TEM DUAS RESPONSABILIDADES

- VALIDAR PRIMEIRA ETAPA
- ENCAMINHAR PARA SEGUNDA ETAPA
"""


logger = logging.getLogger("worker.etapa1")


def resolve_etapa1(contexto_historico):
    """
    id_etapa_atual is None não é uma etapa separada.
    É apenas o primeiro contato antes da etapa 1 ser persistida.

    Nome inválido, mídia e pergunta financeira possuem tratamento próprio.
    Somente nome válido produz o evento nome_cliente_valido.
    """
    id_conversa = contexto_historico["id_conversa"]
    id_etapa_atual = contexto_historico.get("id_etapa_atual")
    tipo_mensagem = contexto_historico.get("tipo_mensagem_atual")
    texto_cliente = contexto_historico.get("texto_cliente_atual") or ""
    mensagem_cliente_atual = contexto_historico["mensagem_cliente_atual"]
    cliente_telefone = mensagem_cliente_atual["cliente_telefone"]
    phone_id_unidade = mensagem_cliente_atual["id_phone_unidade"]

    conversa_sem_etapa = id_etapa_atual is None
    nome_unidade = contexto_historico.get("nome_unidade")
    nome_agente = contexto_historico.get("nome_agente")
    genero = contexto_historico.get("genero")

    if conversa_sem_etapa:
        campos_ausentes = [
            campo
            for campo, valor in (
                ("nome_unidade", nome_unidade),
                ("nome_agente", nome_agente),
                ("genero", genero),
            )
            if not valor
        ]
        if campos_ausentes:
            raise ValueError(
                "Etapa 1 inicial sem dados de apresentacao da unidade "
                f"(id_conversa={id_conversa}, "
                f"campos_ausentes={campos_ausentes})"
            )

        if genero not in {"masculino", "feminino"}:
            raise ValueError(
                "Etapa 1 inicial com genero de agente invalido "
                f"(id_conversa={id_conversa}, genero={genero!r})"
            )

    # Mídia tem prioridade sobre todas as validações de texto.
    if validar_midia(tipo_mensagem):
        _logar_tipo_nao_suportado(contexto_historico)

        if conversa_sem_etapa:
            return enviar_etapa1_midia_inicio(
                cliente_telefone,
                phone_id_unidade,
                nome_unidade,
                nome_agente,
                genero,
            )

        return enviar_etapa1_midia(
            cliente_telefone,
            phone_id_unidade,
        )

    # A dúvida sobre reforço é mais específica que o financeiro e o nome.
    if validar_duvida_reforco_escolar(texto_cliente):
        _logar_tratamento_texto(
            contexto_historico,
            TIPO_TRATAMENTO_REFORCO_ESCOLAR,
        )

        if conversa_sem_etapa:
            return enviar_etapa1_reforco_escolar_inicio(
                cliente_telefone,
                phone_id_unidade,
                nome_unidade,
                nome_agente,
                genero,
            )

        return enviar_etapa1_reforco_escolar(
            cliente_telefone,
            phone_id_unidade,
        )

    if validar_pergunta_financeira(texto_cliente):
        _logar_tratamento_texto(
            contexto_historico,
            TIPO_TRATAMENTO_FINANCEIRO,
        )

        if conversa_sem_etapa:
            return enviar_etapa1_financeiro_inicio(
                cliente_telefone,
                phone_id_unidade,
                nome_unidade,
                nome_agente,
                genero,
            )

        return enviar_etapa1_financeiro(
            cliente_telefone,
            phone_id_unidade,
        )

    # As duas aberturas inicializam a etapa 1 e aguardam o nome. A explicação
    # só se aplica ao primeiro texto, depois dos tratamentos mais específicos;
    # não substitui a validação do nome nem a repetição após follow-up.
    if conversa_sem_etapa:
        if tipo_mensagem == "text" and validar_pedido_informacoes_supera(texto_cliente):
            return enviar_etapa1_informacoes_inicio(
                cliente_telefone,
                phone_id_unidade,
                nome_unidade,
                nome_agente,
                genero,
            )
        return enviar_etapa1(
            cliente_telefone,
            phone_id_unidade,
            nome_unidade,
            nome_agente,
            genero,
        )

    ### VALIDANDO NOME

    resultado_nome = validar_nome_cliente(texto_cliente)

    if not resultado_nome.valido:
        if contexto_historico.get("retorno_followup"):
            return enviar_repeticao_followup(contexto_historico)
        _logar_tratamento_texto(
            contexto_historico,
            TIPO_TRATAMENTO_NOME_INVALIDO,
            motivo_detalhado=resultado_nome.motivo,
        )

        return enviar_etapa1_contexto_nome_invalido(
            cliente_telefone,
            phone_id_unidade,
        )

    if destinatario_coletado(contexto_historico):
        etapa = resolver_destino_transicao(contexto_historico, EVENTO_NOME_DESTINO_COLETADO, destinos_esperados={4})
        envio = enviar_etapa4(cliente_telefone, phone_id_unidade, status_dependente=contexto_historico['status_dependente'])
        envio['primeiro_nome_cliente'] = resultado_nome.primeiro_nome
        return anexar_transicao_ao_contexto_envio(contexto_historico, envio, EVENTO_NOME_DESTINO_COLETADO, etapa)

    # VALIDANDO DESTINO(S)
    # A resposta já passou pelos tratamentos; agora o mapa autoriza a aresta.
    etapa_destino = resolver_destino_transicao(
        contexto_historico,
        EVENTO_NOME_CLIENTE_VALIDO,
        destinos_esperados={ETAPA_2_DESTINO_ATENDIMENTO},
    )

    logger.debug(
        "etapa1_nome_validado | acao=enviar_etapa_destino id_conversa=%s evento=%s etapa_destino=%s primeiro_nome=%s",
        id_conversa,
        EVENTO_NOME_CLIENTE_VALIDO,
        etapa_destino,
        short_value(resultado_nome.primeiro_nome),
    )

    contexto_envio = enviar_etapa2(
        cliente_telefone,
        phone_id_unidade,
        nome_titular=resultado_nome.primeiro_nome,
    )
    contexto_envio["primeiro_nome_cliente"] = resultado_nome.primeiro_nome

    return anexar_transicao_ao_contexto_envio(
        contexto_historico,
        contexto_envio,
        EVENTO_NOME_CLIENTE_VALIDO,
        etapa_destino,
    )


















def _logar_tipo_nao_suportado(contexto_historico):
    mensagem_cliente_atual = contexto_historico["mensagem_cliente_atual"]

    logger.info(
        "resposta_cliente_invalida | motivo=tipo_mensagem_nao_suportado acao=tratar_sem_avancar id_conversa=%s id_mensagem_fila=%s cliente=%s phone_number_id=%s tipo=%s etapa_cliente=%s",
        contexto_historico["id_conversa"],
        mensagem_cliente_atual["id_mensagem_fila"],
        short_value(mensagem_cliente_atual["cliente_telefone"]),
        short_value(mensagem_cliente_atual["id_phone_unidade"]),
        contexto_historico.get("tipo_mensagem_atual"),
        contexto_historico["id_etapa_cliente"],
    )


def _logar_tratamento_texto(
    contexto_historico,
    motivo,
    *,
    motivo_detalhado=None,
):
    mensagem_cliente_atual = contexto_historico["mensagem_cliente_atual"]

    logger.info(
        "resposta_cliente_tratamento | motivo=%s motivo_detalhado=%s acao=tratar_sem_avancar id_conversa=%s id_mensagem_fila=%s cliente=%s phone_number_id=%s etapa_cliente=%s",
        motivo,
        motivo_detalhado,
        contexto_historico["id_conversa"],
        mensagem_cliente_atual["id_mensagem_fila"],
        short_value(mensagem_cliente_atual["cliente_telefone"]),
        short_value(mensagem_cliente_atual["id_phone_unidade"]),
        contexto_historico["id_etapa_cliente"],
    )
```

## Passo 16 — `workers/worker_flow/transacoes/efeitos_transicao.py`

Ação: **alterar**. Conteúdo completo abaixo.

SHA-256 anterior: `7a4ff1c9d38de1a98696c35c1914c268a14327eab5b3e5516a6db6ac6809ed37`.

SHA-256 proposto (UTF-8/LF): `662f2db40c3d8443a7c361315c0a46b61be3ce3a30f8a98ff1b59dc8f17cbcb3`.

```python
import logging
from core.validacoes.coleta_abertura import destinatario_coletado, EVENTO_NOME_DESTINO_COLETADO
from workers.worker_flow.fireads import email_importado

from core.repositories.atendimento.turnos import salvar_turno_conversa
from workers.worker_flow.response_flow.etapas.validadores_contexto.valida_etapa18 import validar_etapa18

from core.logging_config import short_value
from core.repositories.atendimento.clientes import (
    atualizar_email_cliente,
    atualizar_idade_cliente,
    atualizar_nome_cliente_por_telefone,
    atualizar_profissao_cliente,
)
from core.repositories.atendimento.conversas import (
    atualizar_profissao_conversa,
    atualizar_status_dependente_conversa,
)
from core.repositories.atendimento.dependentes import (
    atualizar_idade_dependente,
    atualizar_nome_dependente_por_conversa,
    inserir_dependente_para_conversa,
    remover_dependente_placeholder_da_conversa,
)
from core.repositories.fluxo.triagem import registrar_resposta_triagem
from core.repositories.fluxo.pesquisa_satisfacao import (
    salvar_comentario_satisfacao,
    salvar_nota_satisfacao,
)
from workers.worker_flow.response_flow.etapas.validadores_contexto.valida_etapa21 import (
    validar_etapa21,
)
from workers.worker_flow.response_flow.etapas.validadores_contexto.valida_etapa22 import (
    TIPOS_MENSAGEM_ACEITOS_ETAPA22,
)
from workers.worker_flow.response_flow.etapas.validadores_contexto.valida_etapa23 import (
    normalizar_comentario_etapa23,
)
from workers.worker_flow.response_flow.etapas.validadores_universais.validador_nome import (
    validar_nome_cliente,
)
from workers.worker_flow.response_flow.etapas.validadores_universais.validador_triagem import (
    validar_resposta_triagem,
)
from workers.worker_flow.response_flow.etapas.validadores_contexto.valida_etapa6 import (
    validar_idade,
)
from workers.worker_flow.response_flow.etapas.validadores_contexto.valida_etapa2 import (
    OPCAO_PARA_OUTRA_PESSOA,
    validar_etapa2,
)
from workers.worker_flow.response_flow.etapas.validadores_contexto.valida_etapa4 import (
    validar_profissao_etapa4,
)
from workers.worker_flow.response_flow.etapas.validadores_contexto.valida_etapa10 import (
    CLASSIFICACAO_EMAIL_AUSENTE,
    CLASSIFICACAO_EMAIL_NAO_INFORMADO,
    CLASSIFICACAO_EMAIL_VALIDO,
    calcular_email_obrigatorio_efetivo,
    classificar_resposta_email,
    classificar_resposta_email_aceita,
    validar_etapa10,
)
from workers.worker_flow.response_flow.transicoes.eventos import (
    ETAPA_1_NOME_CLIENTE,
    ETAPA_2_DESTINO_ATENDIMENTO,
    ETAPA_3_CONFIRMACAO_DESTINO,
    ETAPA_4_PROFISSAO,
    ETAPA_5_NOME_DEPENDENTE,
    ETAPA_6_IDADE_ALUNO,
    ETAPA_7_OFERTA_AULA,
    ETAPA_8_OFERTA_ADIADA,
    ETAPA_9_RETORNO_OFERTA,
    ETAPA_10_EMAIL,
    ETAPA_11_INTRODUCAO_TRIAGEM,
    ETAPA_12_TRIAGEM_PERGUNTA_1,
    ETAPA_13_TRIAGEM_PERGUNTA_2,
    ETAPA_14_TRIAGEM_PERGUNTA_3,
    ETAPA_15_TRIAGEM_PERGUNTA_4,
    ETAPA_16_TRIAGEM_PERGUNTA_5,
    ETAPA_17_TRIAGEM_PERGUNTA_6,
    ETAPA_18_ESCOLHA_TURNO,
    ETAPA_19_ENCAMINHAMENTO_COMERCIAL,
    EVENTO_TRIAGEM_CONCLUIDA_SEM_LINK,
    EVENTO_TURNO_ESCOLHIDO,
    EVENTO_AVALIACAO_SOLICITADA,
    ETAPA_20_AGENDAMENTO,
    ETAPA_21_PESQUISA_SATISFACAO,
    ETAPA_22_DECISAO_COMENTARIO,
    ETAPA_23_COMENTARIO_SATISFACAO,
    ETAPA_24_FINALIZACAO,
    EVENTO_AGENDAMENTO_CONFIRMADO,
    EVENTO_CLIENTE_RETORNOU,
    EVENTO_COMENTARIO_SATISFACAO_ACEITO,
    EVENTO_COMENTARIO_SATISFACAO_RECUSADO,
    EVENTO_COMENTARIO_SATISFACAO_RECEBIDO,
    EVENTO_DESTINO_ATENDIMENTO_DEFINIDO,
    EVENTO_DESTINO_ATENDIMENTO_CONFIRMADO,
    EVENTO_EMAIL_VALIDO,
    EVENTO_IDADE_VALIDA,
    EVENTO_NOME_CLIENTE_VALIDO,
    EVENTO_NOME_DEPENDENTE_VALIDO,
    EVENTO_OFERTA_ACEITA,
    EVENTO_OFERTA_ADIADA,
    EVENTO_PROFISSAO_DEPENDENTE_VALIDA,
    EVENTO_PROFISSAO_TITULAR_VALIDA,
    EVENTO_RETORNO_ADIADO,
    EVENTO_RETORNO_CONFIRMADO,
    EVENTO_SATISFACAO_AVALIADA,
    EVENTO_TRIAGEM_INICIADA,
    EVENTO_TRIAGEM_PERGUNTA_1_RESPONDIDA,
    EVENTO_TRIAGEM_PERGUNTA_2_RESPONDIDA,
    EVENTO_TRIAGEM_PERGUNTA_3_RESPONDIDA,
    EVENTO_TRIAGEM_PERGUNTA_4_RESPONDIDA,
    EVENTO_TRIAGEM_PERGUNTA_5_RESPONDIDA,
    EVENTO_TRIAGEM_PERGUNTA_6_RESPONDIDA,
)


logger = logging.getLogger("worker.support")

MOTIVO_ENCAMINHAMENTO_SUPORTE_IDOSO = "encaminhado_suporte_idoso"


def atualizar_banco_conforme_transicao_de_etapa(
    contexto_historico,
    contexto_envio,
    cursor,
):
    """
    Aplica somente os efeitos de negócio da aresta já autorizada.

    A navegação é definida pelo mapa etapa_transicao e persistida antes desta
    função. Os ifs abaixo tornam explícito o efeito de cada origem + evento.
    """
    etapa_origem = contexto_historico.get(
        "id_etapa_origem_transicao"
    )
    evento = contexto_envio.get("evento_transicao")
    etapa_destino = contexto_envio.get("id_etapa_resultante")

    if (
        etapa_origem == ETAPA_6_IDADE_ALUNO
        and contexto_envio.get("encerrar_atendimento")
        and contexto_envio.get("motivo_encerramento")
        == MOTIVO_ENCAMINHAMENTO_SUPORTE_IDOSO
    ):
        return _persistir_idade_encaminhamento_suporte_idoso(
            contexto_historico,
            contexto_envio,
            cursor,
        )

    if (etapa_origem, evento) in {
        (7, 'oferta_aceita_email_fireads'), (9, 'retorno_confirmado_email_fireads')
    }:
        if etapa_destino != 11 or not email_importado(contexto_historico):
            raise ValueError('Salto de email FireAds sem coleta completa nesta conversa')
        return {'email_fireads_reaproveitado': True}

    # Sem evento não existe transição nem efeito específico de etapa.
    if not evento:
        return None

    # ETAPA 1
    if etapa_origem == ETAPA_1_NOME_CLIENTE:
        if evento == EVENTO_NOME_DESTINO_COLETADO:
            _exigir_destino(etapa_origem, evento, etapa_destino, 4)
            if not destinatario_coletado(contexto_historico):
                raise ValueError('Salto de destinatário sem dado aceito nesta conversa')
            return _persistir_nome_cliente_capturado_na_etapa1(contexto_historico, contexto_envio, cursor)
        # 1 -> 2: o cliente informou o próprio nome.
        if evento == EVENTO_NOME_CLIENTE_VALIDO:
            _exigir_destino(
                etapa_origem,
                evento,
                etapa_destino,
                ETAPA_2_DESTINO_ATENDIMENTO,
            )
            return _persistir_nome_cliente_capturado_na_etapa1(
                contexto_historico,
                contexto_envio,
                cursor,
            )

    # ETAPA 2
    if etapa_origem == ETAPA_2_DESTINO_ATENDIMENTO:
        # 2 -> 3: a opção foi validada e aguarda confirmação explícita.
        if evento == EVENTO_DESTINO_ATENDIMENTO_DEFINIDO:
            _exigir_destino(
                etapa_origem,
                evento,
                etapa_destino,
                ETAPA_3_CONFIRMACAO_DESTINO,
            )
            return _persistir_destino_atendimento_da_etapa2(
                contexto_historico,
                contexto_envio,
                etapa_destino,
                cursor=cursor,
            )

    # ETAPA 3
    if etapa_origem == ETAPA_3_CONFIRMACAO_DESTINO:
        if evento == EVENTO_DESTINO_ATENDIMENTO_CONFIRMADO:
            _exigir_destino(
                etapa_origem,
                evento,
                etapa_destino,
                ETAPA_4_PROFISSAO,
            )
            return _persistir_confirmacao_destino_da_etapa3(
                contexto_historico,
                contexto_envio,
                cursor,
            )

    # ETAPA 4
    if etapa_origem == ETAPA_4_PROFISSAO:
        if evento == EVENTO_PROFISSAO_DEPENDENTE_VALIDA:
            _exigir_destino(
                etapa_origem,
                evento,
                etapa_destino,
                ETAPA_5_NOME_DEPENDENTE,
            )
            return _persistir_profissao_capturada_na_etapa4(
                contexto_historico,
                contexto_envio,
                cursor,
                status_dependente_esperado=True,
            )

        if evento == EVENTO_PROFISSAO_TITULAR_VALIDA:
            _exigir_destino(
                etapa_origem,
                evento,
                etapa_destino,
                ETAPA_6_IDADE_ALUNO,
            )
            return _persistir_profissao_capturada_na_etapa4(
                contexto_historico,
                contexto_envio,
                cursor,
                status_dependente_esperado=False,
            )

    # ETAPA 5
    if etapa_origem == ETAPA_5_NOME_DEPENDENTE:
        # 5 -> 6: o cliente informou o nome do dependente.
        if evento == EVENTO_NOME_DEPENDENTE_VALIDO:
            _exigir_destino(
                etapa_origem,
                evento,
                etapa_destino,
                ETAPA_6_IDADE_ALUNO,
            )
            return _persistir_nome_dependente_capturado_na_etapa5(
                contexto_historico,
                contexto_envio,
                cursor,
            )

    # ETAPA 6
    if etapa_origem == ETAPA_6_IDADE_ALUNO:
        # 6 -> 7: a idade do aluno foi validada.
        if evento == EVENTO_IDADE_VALIDA:
            _exigir_destino(
                etapa_origem,
                evento,
                etapa_destino,
                ETAPA_7_OFERTA_AULA,
            )
            return _persistir_idade_capturada_na_etapa6(
                contexto_historico,
                contexto_envio,
                cursor,
            )

    # ETAPA 7
    if etapa_origem == ETAPA_7_OFERTA_AULA:
        # 7 -> 10: o cliente aceitou agendar.
        if evento == EVENTO_OFERTA_ACEITA:
            _exigir_destino(
                etapa_origem,
                evento,
                etapa_destino,
                ETAPA_10_EMAIL,
            )
            return _confirmar_decisao_oferta_da_etapa7(
                contexto_historico,
                evento,
                etapa_destino,
            )

        # 7 -> 8: o cliente preferiu adiar.
        if evento == EVENTO_OFERTA_ADIADA:
            _exigir_destino(
                etapa_origem,
                evento,
                etapa_destino,
                ETAPA_8_OFERTA_ADIADA,
            )
            return _confirmar_decisao_oferta_da_etapa7(
                contexto_historico,
                evento,
                etapa_destino,
            )

    # ETAPA 8
    if etapa_origem == ETAPA_8_OFERTA_ADIADA:
        # 8 -> 9: o cliente enviou uma nova mensagem após adiar a oferta.
        if evento == EVENTO_CLIENTE_RETORNOU:
            _exigir_destino(
                etapa_origem,
                evento,
                etapa_destino,
                ETAPA_9_RETORNO_OFERTA,
            )
            return _confirmar_retorno_cliente_da_etapa8(
                contexto_historico,
                evento,
                etapa_destino,
            )

    # ETAPA 9
    if etapa_origem == ETAPA_9_RETORNO_OFERTA:
        # 9 -> 10: o cliente retomou e confirmou o agendamento.
        if evento == EVENTO_RETORNO_CONFIRMADO:
            _exigir_destino(
                etapa_origem,
                evento,
                etapa_destino,
                ETAPA_10_EMAIL,
            )
            return _confirmar_decisao_retorno_da_etapa9(
                contexto_historico,
                evento,
                etapa_destino,
            )

        # 9 -> 8: o cliente preferiu adiar novamente.
        if evento == EVENTO_RETORNO_ADIADO:
            _exigir_destino(
                etapa_origem,
                evento,
                etapa_destino,
                ETAPA_8_OFERTA_ADIADA,
            )
            return _confirmar_decisao_retorno_da_etapa9(
                contexto_historico,
                evento,
                etapa_destino,
            )

    # ETAPA 10
    if etapa_origem == ETAPA_10_EMAIL:
        # 10 -> 11: a coleta foi aceita. A aresta técnica legada é única;
        # o resultado semântico distingue endereço, ausência e não informado.
        if evento == EVENTO_EMAIL_VALIDO:
            _exigir_destino(
                etapa_origem,
                evento,
                etapa_destino,
                ETAPA_11_INTRODUCAO_TRIAGEM,
            )
            return _persistir_email_capturado_na_etapa10(
                contexto_historico,
                contexto_envio,
                cursor,
            )

    # ETAPA 11
    if etapa_origem == ETAPA_11_INTRODUCAO_TRIAGEM:
        # 11 -> 12: o cliente iniciou a triagem cognitiva.
        if evento == EVENTO_TRIAGEM_INICIADA:
            _exigir_destino(
                etapa_origem,
                evento,
                etapa_destino,
                ETAPA_12_TRIAGEM_PERGUNTA_1,
            )
            return _confirmar_inicio_triagem_da_etapa11(
                contexto_historico,
                evento,
                etapa_destino,
            )

    # ETAPA 12
    if etapa_origem == ETAPA_12_TRIAGEM_PERGUNTA_1:
        # 12 -> 13: registra a resposta da pergunta 1.
        if evento == EVENTO_TRIAGEM_PERGUNTA_1_RESPONDIDA:
            _exigir_destino(
                etapa_origem,
                evento,
                etapa_destino,
                ETAPA_13_TRIAGEM_PERGUNTA_2,
            )
            return _persistir_resposta_triagem(
                contexto_historico,
                contexto_envio,
                cursor,
            )

    # ETAPA 13
    if etapa_origem == ETAPA_13_TRIAGEM_PERGUNTA_2:
        # 13 -> 14: registra a resposta da pergunta 2.
        if evento == EVENTO_TRIAGEM_PERGUNTA_2_RESPONDIDA:
            _exigir_destino(
                etapa_origem,
                evento,
                etapa_destino,
                ETAPA_14_TRIAGEM_PERGUNTA_3,
            )
            return _persistir_resposta_triagem(
                contexto_historico,
                contexto_envio,
                cursor,
            )

    # ETAPA 14
    if etapa_origem == ETAPA_14_TRIAGEM_PERGUNTA_3:
        # 14 -> 15: registra a resposta da pergunta 3.
        if evento == EVENTO_TRIAGEM_PERGUNTA_3_RESPONDIDA:
            _exigir_destino(
                etapa_origem,
                evento,
                etapa_destino,
                ETAPA_15_TRIAGEM_PERGUNTA_4,
            )
            return _persistir_resposta_triagem(
                contexto_historico,
                contexto_envio,
                cursor,
            )

    # ETAPA 15
    if etapa_origem == ETAPA_15_TRIAGEM_PERGUNTA_4:
        # 15 -> 16: registra a resposta da pergunta 4.
        if evento == EVENTO_TRIAGEM_PERGUNTA_4_RESPONDIDA:
            _exigir_destino(
                etapa_origem,
                evento,
                etapa_destino,
                ETAPA_16_TRIAGEM_PERGUNTA_5,
            )
            return _persistir_resposta_triagem(
                contexto_historico,
                contexto_envio,
                cursor,
            )

    # ETAPA 16
    if etapa_origem == ETAPA_16_TRIAGEM_PERGUNTA_5:
        # 16 -> 17: registra a resposta da pergunta 5.
        if evento == EVENTO_TRIAGEM_PERGUNTA_5_RESPONDIDA:
            _exigir_destino(
                etapa_origem,
                evento,
                etapa_destino,
                ETAPA_17_TRIAGEM_PERGUNTA_6,
            )
            return _persistir_resposta_triagem(
                contexto_historico,
                contexto_envio,
                cursor,
            )

    # ETAPA 17
    if etapa_origem == ETAPA_17_TRIAGEM_PERGUNTA_6:
        destinos = {
            EVENTO_TRIAGEM_PERGUNTA_6_RESPONDIDA: ETAPA_20_AGENDAMENTO,
            EVENTO_TRIAGEM_CONCLUIDA_SEM_LINK: ETAPA_18_ESCOLHA_TURNO,
        }
        if evento in destinos:
            # 17 -> 18 ou 20: as duas rotas preservam a sexta resposta da triagem.
            _exigir_destino(etapa_origem, evento, etapa_destino, destinos[evento])
            return _persistir_resposta_triagem(contexto_historico, contexto_envio, cursor)

    # ETAPA 18
    if etapa_origem == ETAPA_18_ESCOLHA_TURNO and evento == EVENTO_TURNO_ESCOLHIDO:
        # 18 -> 19: salvar o turno no mesmo commit do movimento da conversa.
        _exigir_destino(etapa_origem, evento, etapa_destino, ETAPA_19_ENCAMINHAMENTO_COMERCIAL)
        turno = contexto_envio.get("turno")
        if turno is None:
            # A resposta do bot já persistida dispensa novo envio; a mensagem
            # original contém a preferência necessária para reconstruir o efeito.
            turno = validar_etapa18(
                contexto_historico.get("texto_cliente_atual"),
                contexto_historico.get("tipo_mensagem_atual"),
            )
        return salvar_turno_conversa(
            contexto_historico["id_conversa"], contexto_historico["id_unidade"], turno, cursor,
        )

    # ETAPA 19
    if etapa_origem == ETAPA_19_ENCAMINHAMENTO_COMERCIAL and evento == EVENTO_AVALIACAO_SOLICITADA:
        # 19 -> 21: apenas apresenta a pesquisa, sem salvar uma nota nesta aresta.
        _exigir_destino(etapa_origem, evento, etapa_destino, ETAPA_21_PESQUISA_SATISFACAO)
        return {"pesquisa_apresentada": True}

    # ETAPA 20
    if etapa_origem == ETAPA_20_AGENDAMENTO:
        # 20 -> 21: o cliente confirmou o agendamento e inicia a pesquisa.
        if evento == EVENTO_AGENDAMENTO_CONFIRMADO:
            _exigir_destino(
                etapa_origem,
                evento,
                etapa_destino,
                ETAPA_21_PESQUISA_SATISFACAO,
            )
            return _confirmar_agendamento_da_etapa20(
                contexto_historico,
                evento,
                etapa_destino,
            )

    # ETAPA 21
    if etapa_origem == ETAPA_21_PESQUISA_SATISFACAO:
        # 21 -> 22: registra a nota normalizada da pesquisa de satisfacao.
        if evento == EVENTO_SATISFACAO_AVALIADA:
            _exigir_destino(
                etapa_origem,
                evento,
                etapa_destino,
                ETAPA_22_DECISAO_COMENTARIO,
            )
            return _persistir_nota_satisfacao_da_etapa21(
                contexto_historico,
                contexto_envio,
                cursor,
            )

    # ETAPA 22
    if etapa_origem == ETAPA_22_DECISAO_COMENTARIO:
        # 22 -> 23: confirma que o cliente deseja escrever um comentario.
        if evento == EVENTO_COMENTARIO_SATISFACAO_ACEITO:
            _exigir_destino(
                etapa_origem,
                evento,
                etapa_destino,
                ETAPA_23_COMENTARIO_SATISFACAO,
            )
            return _confirmar_decisao_comentario_da_etapa22(
                contexto_historico,
                evento,
                etapa_destino,
            )

        # 22 -> 24: registra a recusa explicita e encerra o atendimento.
        if evento == EVENTO_COMENTARIO_SATISFACAO_RECUSADO:
            _exigir_destino(
                etapa_origem,
                evento,
                etapa_destino,
                ETAPA_24_FINALIZACAO,
            )
            return _persistir_recusa_comentario_da_etapa22(
                contexto_historico,
                cursor,
            )

    # ETAPA 23
    if etapa_origem == ETAPA_23_COMENTARIO_SATISFACAO:
        # 23 -> 24: registra o comentario livre antes da finalizacao.
        if evento == EVENTO_COMENTARIO_SATISFACAO_RECEBIDO:
            _exigir_destino(
                etapa_origem,
                evento,
                etapa_destino,
                ETAPA_24_FINALIZACAO,
            )
            return _persistir_comentario_satisfacao_da_etapa23(
                contexto_historico,
                contexto_envio,
                cursor,
            )

    raise ValueError(
        "Transicao sem efeitos conhecidos "
        f"(origem={etapa_origem}, evento={evento}, "
        f"destino={etapa_destino})"
    )


def _exigir_destino(
    etapa_origem,
    evento,
    etapa_destino,
    destino_esperado,
):
    if etapa_destino != destino_esperado:
        raise ValueError(
            "Efeito de transicao recebeu destino incompativel "
            f"(origem={etapa_origem}, evento={evento}, "
            f"destino={etapa_destino}, "
            f"destino_esperado={destino_esperado})"
        )


def _persistir_nome_cliente_capturado_na_etapa1(
    contexto_historico,
    contexto_envio,
    cursor,
):
    primeiro_nome = _resolver_primeiro_nome_capturado(
        contexto_historico,
        contexto_envio,
        "primeiro_nome_cliente",
    )

    if not primeiro_nome:
        print(
            "\n"
            "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!\n"
            "!!! NOME VAZIO NA TRANSICAO 1 -> 2: ANOMALIA RARA E CRITICA !!!\n"
            "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!\n"
        )
        logger.critical(
            "cliente_nome_anomalia_critica | motivo=nome_vazio_na_transicao_1_2 acao=rollback_e_retry id_conversa=%s etapa_origem=%s etapa_resultante=%s",
            contexto_historico["id_conversa"],
            contexto_historico.get("id_etapa_origem_transicao"),
            contexto_envio.get("id_etapa_resultante"),
        )
        raise ValueError(
            "Nome do cliente nao foi resolvido na transicao 1 -> 2"
        )

    mensagem_cliente = contexto_historico["mensagem_cliente_atual"]
    cliente_telefone = mensagem_cliente["cliente_telefone"]

    atualizar_nome_cliente_por_telefone(
        cliente_telefone,
        primeiro_nome,
        cursor,
    )

    logger.info(
        "cliente_nome_persistido | acao=salvar_nome evento=%s etapa_origem=%s etapa_resultante=%s id_conversa=%s cliente=%s",
        EVENTO_NOME_CLIENTE_VALIDO,
        contexto_historico.get("id_etapa_origem_transicao"),
        contexto_envio.get("id_etapa_resultante"),
        contexto_historico["id_conversa"],
        short_value(cliente_telefone),
    )

    return {
        "cliente_nome_atualizado": True,
        "primeiro_nome_cliente": primeiro_nome,
    }


def _persistir_destino_atendimento_da_etapa2(
    contexto_historico,
    contexto_envio,
    etapa_destino,
    *,
    cursor,
):
    id_conversa = contexto_historico["id_conversa"]
    opcao_atendimento = contexto_envio.get("opcao_atendimento")

    if opcao_atendimento is None:
        opcao_atendimento = validar_etapa2(
            contexto_historico.get("texto_cliente_atual") or ""
        )

    if opcao_atendimento is None:
        raise ValueError(
            "Destino do atendimento nao reconstruido na transicao 2 -> 3"
        )

    status_dependente = (
        opcao_atendimento == OPCAO_PARA_OUTRA_PESSOA
    )

    atualizar_status_dependente_conversa(
        id_conversa,
        status_dependente,
        cursor,
    )

    contexto_persistido = {
        "status_dependente_atualizado": True,
        "status_dependente": status_dependente,
        "opcao_atendimento": opcao_atendimento,
        "dependente_criado": False,
    }

    if status_dependente:
        dependente = inserir_dependente_para_conversa(
            id_conversa,
            cursor,
        )
        contexto_persistido.update(
            {
                "dependente_criado": dependente["inserido"],
                "id_dependente": dependente["id_dependente"],
                "id_cliente_dependente": dependente["id_cliente"],
            }
        )

    logger.info(
        "destino_atendimento_persistido | acao=salvar_efeitos_transicao evento=%s etapa_origem=%s etapa_resultante=%s id_conversa=%s status_dependente=%s dependente_criado=%s",
        EVENTO_DESTINO_ATENDIMENTO_DEFINIDO,
        contexto_historico.get("id_etapa_origem_transicao"),
        etapa_destino,
        id_conversa,
        status_dependente,
        contexto_persistido["dependente_criado"],
    )

    return contexto_persistido


def _persistir_confirmacao_destino_da_etapa3(
    contexto_historico,
    contexto_envio,
    cursor,
):
    """Aplica o destino final como valor absoluto e seguro para replay.

    No primeiro processamento, o validador produz o valor absoluto. Em replay,
    movimento e efeito já foram confirmados juntos, então o worker relê esse
    mesmo valor da conversa. A resposta relativa nunca é reinterpretada.
    """
    status_dependente_final = contexto_envio.get(
        "status_dependente_final"
    )
    if not isinstance(status_dependente_final, bool):
        raise ValueError(
            "Confirmacao da etapa 3 sem status_dependente_final booleano "
            f"(valor={status_dependente_final!r})"
        )

    id_conversa = contexto_historico["id_conversa"]
    status_anterior = contexto_historico.get("status_dependente")
    if not isinstance(status_anterior, bool):
        raise ValueError(
            "Confirmacao da etapa 3 sem status_dependente anterior booleano "
            f"(valor={status_anterior!r})"
        )

    atualizar_status_dependente_conversa(
        id_conversa,
        status_dependente_final,
        cursor,
    )

    resultado = {
        "status_dependente_atualizado": True,
        "status_dependente": status_dependente_final,
        "status_dependente_alterado": (
            status_anterior != status_dependente_final
        ),
        "dependente_criado": False,
        "dependente_removido": False,
    }

    if status_dependente_final:
        dependente = inserir_dependente_para_conversa(id_conversa, cursor)
        resultado.update(
            {
                "dependente_criado": dependente["inserido"],
                "id_dependente": dependente["id_dependente"],
                "id_cliente_dependente": dependente["id_cliente"],
            }
        )
    else:
        resultado["dependente_removido"] = (
            remover_dependente_placeholder_da_conversa(
                id_conversa,
                cursor,
            )
        )

    logger.info(
        "destino_atendimento_confirmado | acao=aplicar_status_absoluto "
        "evento=%s etapa_origem=%s etapa_resultante=%s id_conversa=%s "
        "status_anterior=%s status_final=%s dependente_criado=%s "
        "dependente_removido=%s",
        contexto_envio.get("evento_transicao"),
        contexto_historico.get("id_etapa_origem_transicao"),
        contexto_envio.get("id_etapa_resultante"),
        id_conversa,
        status_anterior,
        status_dependente_final,
        resultado["dependente_criado"],
        resultado["dependente_removido"],
    )

    return resultado


def _persistir_profissao_capturada_na_etapa4(
    contexto_historico,
    contexto_envio,
    cursor,
    *,
    status_dependente_esperado,
):
    status_dependente = contexto_historico.get("status_dependente")
    if not isinstance(status_dependente, bool):
        raise ValueError(
            "Profissao sem status_dependente booleano persistido "
            f"(valor={status_dependente!r})"
        )

    if status_dependente != status_dependente_esperado:
        raise ValueError(
            "Evento da profissao incompativel com o destino do atendimento "
            f"(id_conversa={contexto_historico['id_conversa']}, "
            f"status_dependente={status_dependente})"
        )

    profissao = contexto_envio.get("profissao")

    if profissao is None:
        resultado = validar_profissao_etapa4(
            contexto_historico.get("texto_cliente_atual") or "",
            contexto_historico.get("tipo_mensagem_atual"),
        )
        if resultado.valida:
            profissao = resultado.profissao

    if not profissao:
        raise ValueError(
            "Profissao nao reconstruida na transicao da etapa 4"
        )

    atualizar_profissao_conversa(
        contexto_historico["id_conversa"],
        profissao,
        cursor,
    )
    atualizar_profissao_cliente(
        contexto_historico["id_cliente"],
        profissao,
        cursor,
    )

    logger.info(
        "profissao_persistida | acao=salvar_snapshot_e_atualizar_cliente "
        "evento=%s etapa_origem=%s etapa_resultante=%s "
        "id_conversa=%s id_cliente=%s profissao=%s",
        contexto_envio.get("evento_transicao"),
        contexto_historico["id_etapa_origem_transicao"],
        contexto_envio["id_etapa_resultante"],
        contexto_historico["id_conversa"],
        contexto_historico["id_cliente"],
        short_value(profissao),
    )

    return {
        "profissao_atualizada": True,
        "profissao": profissao,
    }


def _persistir_nome_dependente_capturado_na_etapa5(
    contexto_historico,
    contexto_envio,
    cursor,
):
    primeiro_nome = _resolver_primeiro_nome_capturado(
        contexto_historico,
        contexto_envio,
        "primeiro_nome_dependente",
    )

    if not primeiro_nome:
        logger.critical(
            "dependente_nome_anomalia_critica | motivo=nome_vazio_na_transicao_5_6 acao=rollback_e_retry id_conversa=%s etapa_origem=%s etapa_resultante=%s",
            contexto_historico["id_conversa"],
            contexto_historico.get("id_etapa_origem_transicao"),
            contexto_envio.get("id_etapa_resultante"),
        )
        raise ValueError(
            "Nome do dependente nao foi resolvido na transicao 5 -> 6"
        )

    id_conversa = contexto_historico["id_conversa"]
    atualizar_nome_dependente_por_conversa(
        id_conversa,
        primeiro_nome,
        cursor,
    )

    logger.info(
        "dependente_nome_persistido | acao=salvar_nome evento=%s etapa_origem=%s etapa_resultante=%s id_conversa=%s",
        EVENTO_NOME_DEPENDENTE_VALIDO,
        contexto_historico.get("id_etapa_origem_transicao"),
        contexto_envio.get("id_etapa_resultante"),
        id_conversa,
    )

    return {
        "dependente_nome_atualizado": True,
        "primeiro_nome_dependente": primeiro_nome,
    }


def _resolver_primeiro_nome_capturado(
    contexto_historico,
    contexto_envio,
    chave_contexto,
):
    primeiro_nome = contexto_envio.get(chave_contexto)

    if primeiro_nome:
        return primeiro_nome

    resultado_nome = validar_nome_cliente(
        contexto_historico.get("texto_cliente_atual") or ""
    )

    if resultado_nome.valido:
        return resultado_nome.primeiro_nome

    return None


def _persistir_idade_capturada_na_etapa6(
    contexto_historico,
    contexto_envio,
    cursor,
):
    idade = contexto_envio.get("idade_aluno")

    if idade is None:
        resultado = validar_idade(
            contexto_historico.get("texto_cliente_atual") or ""
        )
        if resultado.valida:
            idade = resultado.idade

    if idade is None:
        raise ValueError(
            "Idade não reconstruída na transição 6 -> 7"
        )

    if contexto_historico.get("status_dependente"):
        atualizar_idade_dependente(
            contexto_historico["id_conversa"],
            idade,
            cursor,
        )
        destino_dado = "dependente"
    else:
        atualizar_idade_cliente(
            contexto_historico["id_cliente"],
            idade,
            cursor,
        )
        destino_dado = "cliente"

    logger.info(
        "idade_aluno_persistida | acao=salvar_efeito_transicao "
        "evento=%s etapa_origem=%s etapa_resultante=%s "
        "id_conversa=%s idade=%s destino_dado=%s",
        EVENTO_IDADE_VALIDA,
        contexto_historico["id_etapa_origem_transicao"],
        contexto_envio["id_etapa_resultante"],
        contexto_historico["id_conversa"],
        idade,
        destino_dado,
    )

    return {
        "idade_aluno_atualizada": True,
        "idade_aluno": idade,
        "destino_dado": destino_dado,
    }


def _persistir_idade_encaminhamento_suporte_idoso(
    contexto_historico,
    contexto_envio,
    cursor,
):
    if contexto_historico.get("status_dependente"):
        raise ValueError(
            "Encaminhamento de suporte ao idoso não aceita dependente"
        )

    idade = contexto_envio.get("idade_aluno")
    if idade is None:
        resultado = validar_idade(
            contexto_historico.get("texto_cliente_atual") or ""
        )
        idade = resultado.idade if resultado.valida else None

    if (
        isinstance(idade, bool)
        or not isinstance(idade, int)
        or not 50 <= idade <= 99
    ):
        raise ValueError(
            "Idade inválida no encaminhamento de suporte ao idoso "
            f"(idade={idade!r})"
        )

    atualizar_idade_cliente(
        contexto_historico["id_cliente"],
        idade,
        cursor,
    )

    logger.info(
        "idade_titular_persistida | acao=encaminhar_suporte_idoso "
        "id_conversa=%s id_cliente=%s faixa=50_99",
        contexto_historico["id_conversa"],
        contexto_historico["id_cliente"],
    )
    return {
        "idade_aluno_atualizada": True,
        "idade_aluno": idade,
        "destino_dado": "cliente",
        "encaminhamento_suporte_idoso": True,
    }


def _confirmar_decisao_oferta_da_etapa7(
    contexto_historico,
    evento,
    etapa_destino,
):
    """
    Torna explícita a aresta da oferta sem duplicar persistência.

    A mudança de id_etapa_atual já foi executada e revalidada no PostgreSQL
    por persistir_movimento_conversa antes dos efeitos específicos.
    """
    logger.info(
        "decisao_oferta_persistida | acao=confirmar_transicao "
        "evento=%s etapa_origem=%s etapa_resultante=%s id_conversa=%s",
        evento,
        contexto_historico["id_etapa_origem_transicao"],
        etapa_destino,
        contexto_historico["id_conversa"],
    )

    return {
        "decisao_oferta_persistida": True,
        "decisao_oferta": evento,
    }


def _confirmar_retorno_cliente_da_etapa8(
    contexto_historico,
    evento,
    etapa_destino,
):
    """
    Confirma a continuidade sem criar dado de negócio adicional.

    A mudança de id_etapa_atual já foi persistida pelo movimento genérico da
    conversa. Esta etapa apenas torna explícita a aresta 8 -> 9.
    """
    logger.info(
        "retorno_cliente_persistido | acao=confirmar_transicao "
        "evento=%s etapa_origem=%s etapa_resultante=%s id_conversa=%s",
        evento,
        contexto_historico["id_etapa_origem_transicao"],
        etapa_destino,
        contexto_historico["id_conversa"],
    )

    return {
        "retorno_cliente_persistido": True,
        "evento_retorno": evento,
    }


def _confirmar_decisao_retorno_da_etapa9(
    contexto_historico,
    evento,
    etapa_destino,
):
    """
    Torna explícita a decisão do retorno sem duplicar persistência.

    A mudança de id_etapa_atual já foi persistida pelo movimento genérico da
    conversa. Esta função confirma apenas as arestas 9 -> 10 e 9 -> 8.
    """
    logger.info(
        "decisao_retorno_persistida | acao=confirmar_transicao "
        "evento=%s etapa_origem=%s etapa_resultante=%s id_conversa=%s",
        evento,
        contexto_historico["id_etapa_origem_transicao"],
        etapa_destino,
        contexto_historico["id_conversa"],
    )

    return {
        "decisao_retorno_persistida": True,
        "decisao_retorno": evento,
    }


def _persistir_email_capturado_na_etapa10(
    contexto_historico,
    contexto_envio,
    cursor,
):
    """Persiste de forma absoluta o resultado aceito na conversa atual."""
    classificacao = contexto_envio.get("resultado_coleta_email")
    email = contexto_envio.get("email_cliente")

    if classificacao is None and email:
        classificacao = CLASSIFICACAO_EMAIL_VALIDO
        email = validar_etapa10(email).email

    if classificacao is None:
        texto_cliente = contexto_historico.get("texto_cliente_atual") or ""

        if contexto_envio.get("resposta_ja_existia"):
            resultado_email = classificar_resposta_email_aceita(
                texto_cliente
            )
        else:
            email_obrigatorio = calcular_email_obrigatorio_efetivo(
                contexto_historico.get("email_obrigatorio_unidade"),
                contexto_historico.get("status_dependente"),
                contexto_historico.get("idade_cliente"),
            )
            resultado_email = classificar_resposta_email(
                texto_cliente,
                email_obrigatorio=email_obrigatorio,
            )

        if not resultado_email.aceita:
            raise ValueError(
                "Resultado de email nao reconstruido na transicao 10 -> 11"
            )

        classificacao = resultado_email.classificacao
        email = resultado_email.email

    classificacoes_validas = {
        CLASSIFICACAO_EMAIL_VALIDO,
        CLASSIFICACAO_EMAIL_AUSENTE,
        CLASSIFICACAO_EMAIL_NAO_INFORMADO,
    }
    if classificacao not in classificacoes_validas:
        raise ValueError(
            "Classificacao de email invalida na transicao 10 -> 11 "
            f"(classificacao={classificacao!r})"
        )

    if classificacao == CLASSIFICACAO_EMAIL_VALIDO:
        resultado_estrutural = validar_etapa10(email)
        if not resultado_estrutural.valido:
            raise ValueError(
                "Email valido sem endereco reconstruivel na transicao 10 -> 11"
            )
        email = resultado_estrutural.email
    else:
        email = None

    atualizar_email_cliente(
        contexto_historico["id_cliente"],
        email,
        cursor,
    )

    logger.info(
        "cliente_email_persistido | acao=salvar_efeito_transicao "
        "evento=%s etapa_origem=%s etapa_resultante=%s "
        "id_conversa=%s id_cliente=%s email_preenchido=%s "
        "resultado_coleta=%s",
        EVENTO_EMAIL_VALIDO,
        contexto_historico["id_etapa_origem_transicao"],
        contexto_envio["id_etapa_resultante"],
        contexto_historico["id_conversa"],
        contexto_historico["id_cliente"],
        bool(email),
        classificacao,
    )

    return {
        "cliente_email_atualizado": True,
        "email_preenchido": bool(email),
        "resultado_coleta_email": classificacao,
    }


def _confirmar_inicio_triagem_da_etapa11(
    contexto_historico,
    evento,
    etapa_destino,
):
    """
    Confirma a continuidade sem criar dado de negócio adicional.

    A mudança de id_etapa_atual já foi persistida pelo movimento genérico da
    conversa. Esta função torna explícita somente a aresta 11 -> 12.
    """
    logger.info(
        "inicio_triagem_persistido | acao=confirmar_transicao "
        "evento=%s etapa_origem=%s etapa_resultante=%s id_conversa=%s",
        evento,
        contexto_historico["id_etapa_origem_transicao"],
        etapa_destino,
        contexto_historico["id_conversa"],
    )

    return {
        "inicio_triagem_persistido": True,
        "evento_triagem": evento,
    }


def _persistir_resposta_triagem(
    contexto_historico,
    contexto_envio,
    cursor,
):
    """
    Persiste a opção da pergunta de origem dentro da transação final.

    Em reaplicação idempotente, o contexto de envio não possui a resposta.
    Nesse caso, a opção é reconstruída pela mensagem original do cliente.
    """
    resposta_triagem = contexto_envio.get("resposta_triagem")

    if resposta_triagem is None:
        resposta_triagem = validar_resposta_triagem(
            contexto_historico.get("texto_cliente_atual") or "",
            contexto_historico.get("tipo_mensagem_atual"),
        )

    if resposta_triagem is None:
        raise ValueError(
            "Resposta da triagem não foi reconstruída na transição "
            f"(etapa={contexto_historico.get('id_etapa_origem_transicao')})"
        )

    mensagem_cliente = contexto_historico["mensagem_cliente_atual"]
    resultado = registrar_resposta_triagem(
        contexto_historico["id_conversa"],
        contexto_historico["id_etapa_origem_transicao"],
        resposta_triagem,
        mensagem_cliente.get("id_mensagem"),
        cursor,
    )

    logger.info(
        "efeito_resposta_triagem_persistido | acao=salvar_resposta "
        "evento=%s etapa_origem=%s etapa_resultante=%s "
        "id_conversa=%s resposta=%s inserido=%s",
        contexto_envio.get("evento_transicao"),
        contexto_historico["id_etapa_origem_transicao"],
        contexto_envio["id_etapa_resultante"],
        contexto_historico["id_conversa"],
        resposta_triagem,
        resultado["inserido"],
    )

    return {
        "resposta_triagem_persistida": True,
        **resultado,
    }


def _confirmar_agendamento_da_etapa20(
    contexto_historico,
    evento,
    etapa_destino,
):
    """Confirma a aresta 20 -> 21 sem criar dado de negocio adicional."""
    logger.info(
        "agendamento_confirmado_persistido | acao=confirmar_transicao "
        "evento=%s etapa_origem=%s etapa_resultante=%s id_conversa=%s",
        evento,
        contexto_historico["id_etapa_origem_transicao"],
        etapa_destino,
        contexto_historico["id_conversa"],
    )

    return {
        "agendamento_confirmado": True,
        "evento_agendamento": evento,
    }


def _persistir_nota_satisfacao_da_etapa21(
    contexto_historico,
    contexto_envio,
    cursor,
):
    """Persiste a nota; em retry, reconstrói o valor pela mensagem original."""
    nota_satisfacao = contexto_envio.get("nota_satisfacao")

    if nota_satisfacao is None:
        nota_satisfacao = validar_etapa21(
            contexto_historico.get("texto_cliente_atual") or ""
        )

    if nota_satisfacao is None:
        raise ValueError(
            "Nota de satisfacao ausente na transicao 21 -> 22 "
            f"(id_conversa={contexto_historico['id_conversa']})"
        )

    resultado = salvar_nota_satisfacao(
        contexto_historico["id_conversa"],
        nota_satisfacao,
        cursor,
    )

    logger.info(
        "efeito_nota_satisfacao_persistido | acao=salvar_nota "
        "evento=%s etapa_origem=%s etapa_resultante=%s "
        "id_conversa=%s nota=%s inserido=%s",
        contexto_envio.get("evento_transicao"),
        contexto_historico["id_etapa_origem_transicao"],
        contexto_envio["id_etapa_resultante"],
        contexto_historico["id_conversa"],
        nota_satisfacao,
        resultado["inserido"],
    )

    return {
        "nota_satisfacao_persistida": True,
        **resultado,
    }


def _confirmar_decisao_comentario_da_etapa22(
    contexto_historico,
    evento,
    etapa_destino,
):
    """Confirma a escolha sem criar dado antes do comentário efetivo."""
    logger.info(
        "decisao_comentario_persistida | acao=confirmar_transicao "
        "evento=%s etapa_origem=%s etapa_resultante=%s id_conversa=%s",
        evento,
        contexto_historico["id_etapa_origem_transicao"],
        etapa_destino,
        contexto_historico["id_conversa"],
    )

    return {
        "decisao_comentario_persistida": True,
        "decisao_comentario": evento,
    }


def _persistir_recusa_comentario_da_etapa22(
    contexto_historico,
    cursor,
):
    """Registra NULL de forma idempotente para a recusa explícita."""
    resultado = salvar_comentario_satisfacao(
        contexto_historico["id_conversa"],
        None,
        cursor,
    )

    logger.info(
        "recusa_comentario_satisfacao_persistida | "
        "acao=salvar_comentario_nulo evento=%s etapa_origem=%s "
        "etapa_resultante=%s id_conversa=%s inserido=%s",
        EVENTO_COMENTARIO_SATISFACAO_RECUSADO,
        contexto_historico["id_etapa_origem_transicao"],
        ETAPA_24_FINALIZACAO,
        contexto_historico["id_conversa"],
        resultado["inserido"],
    )

    return {
        "comentario_satisfacao_persistido": True,
        **resultado,
    }


def _persistir_comentario_satisfacao_da_etapa23(
    contexto_historico,
    contexto_envio,
    cursor,
):
    """Persiste o texto; em retry, reconstrói a mensagem original."""
    if "comentario_satisfacao" in contexto_envio:
        comentario_satisfacao = contexto_envio["comentario_satisfacao"]
    else:
        texto_cliente = contexto_historico.get("texto_cliente_atual") or ""
        tipo_mensagem = contexto_historico.get("tipo_mensagem_atual")
        # Reconstruir o mesmo resultado do primeiro processamento, inclusive NULL
        # quando não houve texto ou o cliente recusou comentar. Mídia não avança.
        if tipo_mensagem not in TIPOS_MENSAGEM_ACEITOS_ETAPA22:
            raise ValueError(
                "Tipo de mensagem não permitido na transição 23 -> 24 "
                f"(id_conversa={contexto_historico['id_conversa']})"
            )
        comentario_satisfacao = normalizar_comentario_etapa23(
            texto_cliente,
            tipo_mensagem,
        )

    resultado = salvar_comentario_satisfacao(
        contexto_historico["id_conversa"],
        comentario_satisfacao,
        cursor,
    )

    logger.info(
        "efeito_comentario_satisfacao_persistido | "
        "acao=salvar_comentario evento=%s etapa_origem=%s "
        "etapa_resultante=%s id_conversa=%s "
        "comentario_preenchido=%s inserido=%s",
        contexto_envio.get("evento_transicao"),
        contexto_historico["id_etapa_origem_transicao"],
        contexto_envio["id_etapa_resultante"],
        contexto_historico["id_conversa"],
        bool(comentario_satisfacao),
        resultado["inserido"],
    )

    return {
        "comentario_satisfacao_persistido": True,
        **resultado,
    }
```

## Passo 17 — `workers/worker_flow/transacoes/persistencia_resposta.py`

Ação: **alterar**. Conteúdo completo abaixo.

SHA-256 anterior: `ba63651ed5dafb5b94b1d27b3f8c2cce930193ecf5cd2dbbf6719d6e73127e08`.

SHA-256 proposto (UTF-8/LF): `df45b60c128a9dc9141efc4896a6c1b642e6c3043116ac8c1c2a70b622484f58`.

```python
import logging
from core.repositories.fireads.consulta import guardar_coletas
from core.repositories.atendimento.coleta_abertura import guardar_coletas as guardar_coleta_abertura

from core.repositories.atendimento.historico import inserir_historico_mensagem_bot
from core.repositories.seguranca.suspeita_bot import (
    incrementar_turnos_sem_avanco,
    resetar_turnos_sem_avanco,
)
from workers.worker_flow.transacoes.encerramento_atendimento import (
    resolver_intencao_encerramento,
)
from workers.worker_flow.transacoes.efeitos_transicao import (
    atualizar_banco_conforme_transicao_de_etapa,
)
from workers.worker_flow.transacoes.movimento_conversa import (
    MOVIMENTO_SEM_AVANCO,
    MOVIMENTO_TRANSICAO,
    persistir_movimento_conversa,
)


logger = logging.getLogger("worker.support")


def _obter_data_interacao_bot_existente(contexto_historico):
    resposta_bot = (
        contexto_historico.get("resposta_bot_para_mensagem_atual") or {}
    )
    data_interacao = resposta_bot.get("received_data_hora")

    if data_interacao is None:
        raise ValueError(
            "Resposta do bot existente sem received_data_hora persistido"
        )

    return data_interacao


def atualizar_banco_com_contexto_final(
    contexto_historico,
    contexto_envio,
    cursor,
):
    """
    Persiste o resultado completo do ciclo em uma única transação.

    Ordem preservada:
    1. registrar ou recuperar a resposta do bot;
    2. persistir inicialização, transição ou permanência;
    3. incrementar ou zerar a suspeita de bot;
    4. aplicar os efeitos específicos da aresta;
    5. devolver o contexto final para a finalização da fila.
    """
    id_conversa = contexto_historico["id_conversa"]
    id_etapa_resultante = contexto_envio.get("id_etapa_resultante")
    resposta_ja_existia = bool(
        contexto_envio.get("resposta_ja_existia")
    )

    (
        id_historico_bot,
        data_interacao_bot,
        historico_bot_inserido,
    ) = _persistir_ou_recuperar_resposta_bot(
        contexto_historico,
        contexto_envio,
        cursor,
    )

    movimento = persistir_movimento_conversa(
        contexto_historico,
        contexto_envio,
        data_interacao_bot,
        cursor,
    )

    turnos_sem_avanco = _persistir_turnos_sem_avanco(
        id_conversa=id_conversa,
        movimento=movimento,
        tratamento=bool(contexto_envio.get("tratamento")),
        historico_bot_inserido=historico_bot_inserido,
        retorno_followup=bool(contexto_historico.get("retorno_followup")),
        cursor=cursor,
    )

    efeitos_transicao = atualizar_banco_conforme_transicao_de_etapa(
        contexto_historico,
        contexto_envio,
        cursor,
    )
    guardar_coletas(contexto_historico, efeitos_transicao, cursor)
    guardar_coleta_abertura(contexto_historico, efeitos_transicao, cursor)
    intencao_encerramento = resolver_intencao_encerramento(
        contexto_historico,
        contexto_envio,
        cursor,
    )

    logger.info(
        "resposta_bot_persistida | acao=registrar_historico_e_contexto "
        "id_conversa=%s id_historico_bot=%s inserido=%s "
        "resposta_ja_existia=%s movimento=%s etapa=%s evento=%s "
        "id_hash_msg_bot=%s turnos_sem_avanco=%s",
        id_conversa,
        id_historico_bot,
        historico_bot_inserido,
        resposta_ja_existia,
        movimento,
        id_etapa_resultante,
        contexto_envio.get("evento_transicao"),
        contexto_envio.get("id_hash_msg_bot"),
        turnos_sem_avanco,
    )

    contexto_final = {
        "historico_bot_inserido": historico_bot_inserido,
        "resposta_ja_existia": resposta_ja_existia,
        "id_hash_msg_bot": contexto_envio.get("id_hash_msg_bot"),
        "id_etapa_resultante": id_etapa_resultante,
        "movimento_conversa": movimento,
        "atualizar_conversa": movimento != MOVIMENTO_SEM_AVANCO,
        "atualizar_last_from_bot": True,
        "intencao_encerramento": intencao_encerramento,
    }

    if turnos_sem_avanco is not None:
        contexto_final["turnos_sem_avanco"] = turnos_sem_avanco

    if id_historico_bot is not None:
        contexto_final.update(
            {
                "id_historico_bot": id_historico_bot,
                "data_historico_bot": data_interacao_bot,
            }
        )

    if efeitos_transicao:
        contexto_final["efeitos_transicao"] = efeitos_transicao

    return contexto_final


def _persistir_turnos_sem_avanco(
    *,
    id_conversa,
    movimento,
    tratamento,
    historico_bot_inserido,
    cursor,
    retorno_followup=False,
):
    if movimento == MOVIMENTO_TRANSICAO:
        return resetar_turnos_sem_avanco(id_conversa, cursor)

    if (
        movimento == MOVIMENTO_SEM_AVANCO
        and tratamento
        # A primeira reação ao lembrete não penaliza o cliente.
        and not retorno_followup
        and historico_bot_inserido
    ):
        return incrementar_turnos_sem_avanco(id_conversa, cursor)

    return None


def _persistir_ou_recuperar_resposta_bot(
    contexto_historico,
    contexto_envio,
    cursor,
):
    if contexto_envio.get("resposta_ja_existia"):
        return (
            None,
            _obter_data_interacao_bot_existente(contexto_historico),
            False,
        )

    if not contexto_envio.get("enviou"):
        raise ValueError(
            "Contexto de envio sem resposta enviada e sem resposta existente"
        )

    return inserir_historico_mensagem_bot(
        contexto_historico,
        contexto_envio,
        cursor,
    )
```

## Passo 18 — `callback/webhook/models.py`

Ação: **alterar**. Conteúdo completo abaixo.

SHA-256 anterior: `acfea4e67fc5611895eb3147affd63fdeac2d6f3cec67f1d4cd284bd176c2ed7`.

SHA-256 proposto (UTF-8/LF): `cc259b1d7e8470da00fc6da28da5bc35587ec01c3bc4209a39f284a9ec090c62`.

```python
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
    origem_fireads = models.CharField(max_length=20, null=True, blank=True, choices=[('google','Google Ads'),('meta','Meta Ads'),('organico_site','Orgânico Site'),('organico','Orgânico')])
    contexto_fireads = models.JSONField(null=True, blank=True)
    contexto_coleta = models.JSONField(null=True, blank=True, editable=False)
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
    snapshot = models.JSONField(blank=True, null=True)
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
    aba_destino = models.CharField(
        "Aba de leads", max_length=200, default="LEADS GERAL - Feedback",
        help_text="Aba única para consultar formulários e acrescentar observações.",
    )
    fuso_formularios = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        help_text="Somente interpretação de datas sem offset. Preencher após confirmação na planilha; não altera o fuso externo.",
    )
    contrato_validado = models.BooleanField(
        default=False,
        help_text="Confirmar a aba de leads, os cabeçalhos e os valores de Canal e Para quem é antes de ativar.",
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
        self.aba_destino = self.aba_destino.strip()
        if not self.aba_destino:
            raise ValidationError({"aba_destino": "Informe a aba de leads."})

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
```

## Passo 19 — `core/repositories/funil/leads.py`

Ação: **alterar**. Conteúdo completo abaixo.

SHA-256 anterior: `ee7b7b3e0ef645743f603cfbe9e47e94ede507f38faa2f7fcdcfdde973b765f9`.

SHA-256 proposto (UTF-8/LF): `3a89e6beb3c21843bdee42b8c878126ba0ed7c12102979621722fb89a5dc58e1`.

```python
"""Leitura do snapshot completo de uma conversa elegível ao Funil."""


def buscar_dados_lead_funil(id_conversa, cursor):
    """Retorna o snapshot da conversa, inclusive sua profissão histórica.

    ``cliente.profissao`` é mutável entre atendimentos e não participa do lead.
    """
    cursor.execute(
        """
        SELECT
            c.id_conversa,
            c.id_unidade,
            u.nome_unidade,
            COALESCE(c.status_dependente, FALSE) AS status_dependente,
            cl.nome AS nome_cliente,
            cl.waid_telefone AS telefone_cliente,
            cl.email AS email_cliente,
            cl.idade AS idade_cliente,
            c.profissao,
            d.nome_dependente,
            d.idade AS idade_dependente,
            triagem.respostas,
            coleta_email.conteudo_texto AS resposta_email_conversa,
            NULLIF(BTRIM(ac.link_agendamento), '') AS link_agendamento,
            c.turno, c.origem_fireads, c.contexto_fireads,
            NOT EXISTS (
                SELECT 1 FROM chatbot.conversa anterior
                WHERE anterior.id_chat=c.id_chat
                  AND (anterior.iniciou_em,anterior.id_conversa)<(c.iniciou_em,c.id_conversa)
            ) AS primeiro_atendimento, c.contexto_coleta
        FROM chatbot.conversa c
        JOIN chatbot.cliente cl
          ON cl.id_cliente = c.id_cliente
        JOIN chatbot.unidade u
          ON u.id_unidade = c.id_unidade
        JOIN chatbot.atendimento_customizado ac ON ac.id_unidade = u.id_unidade
        JOIN chatbot.etapa etapa_atual
          ON etapa_atual.id_etapa = c.id_etapa_atual
        LEFT JOIN chatbot.dependente d
          ON d.id_conversa = c.id_conversa
        CROSS JOIN LATERAL (
            SELECT
                COALESCE(
                    JSONB_AGG(
                        JSONB_BUILD_OBJECT(
                            'id_etapa', r.id_etapa,
                            'resposta', r.resposta
                        )
                        ORDER BY r.id_etapa
                    ),
                    '[]'::JSONB
                ) AS respostas
            FROM chatbot.respostas_desafios r
            WHERE r.id_conversa = c.id_conversa
              AND r.id_etapa BETWEEN 12 AND 17
        ) AS triagem
        LEFT JOIN LATERAL (
            SELECT mensagem_cliente.conteudo_texto
            FROM chatbot.historico_mensagens mensagem_bot
            JOIN chatbot.historico_mensagens mensagem_cliente
              ON mensagem_cliente.id_conversa = mensagem_bot.id_conversa
             AND mensagem_cliente.quem_enviou = 'cliente'
             AND mensagem_cliente.id_etapa = 10
             AND mensagem_cliente.id_mensagem_fila
                 = mensagem_bot.id_mensagem_fila
             AND mensagem_cliente.id_hash_msg
                 = mensagem_bot.id_hash_cliente_origem
            WHERE mensagem_bot.id_conversa = c.id_conversa
              AND mensagem_bot.quem_enviou = 'bot'
              AND mensagem_bot.status_envio = 'sent'
              AND mensagem_bot.id_etapa = 11
            ORDER BY
                mensagem_bot.received_data_hora DESC,
                mensagem_bot.id_mensagem DESC
            LIMIT 1
        ) AS coleta_email ON TRUE
        WHERE c.id_conversa = %s
          AND u.status_pagamento IS TRUE
          AND etapa_atual.elegivel_funil = TRUE
          AND (
                (NULLIF(BTRIM(ac.link_agendamento), '') IS NOT NULL
                 AND c.id_etapa_atual >= 20)
                OR (NULLIF(BTRIM(ac.link_agendamento), '') IS NULL
                    AND (c.id_etapa_atual = 19 OR c.id_etapa_atual >= 21))
              )
          AND c.lead_no_funil IS NOT TRUE
        LIMIT 1;
        """,
        (id_conversa,),
    )

    resultado = cursor.fetchone()
    if resultado is None:
        return None

    dados = {
        "link_agendamento": resultado[13],
        "turno": resultado[14],
        "id_conversa": resultado[0],
        "id_unidade": resultado[1],
        "nome_unidade": resultado[2],
        "status_dependente": bool(resultado[3]),
        "nome_cliente": resultado[4],
        "telefone_cliente": resultado[5],
        "email_cliente": resultado[6],
        "idade_cliente": resultado[7],
        "profissao": resultado[8],
        "nome_dependente": resultado[9],
        "idade_dependente": resultado[10],
        "triagem_respostas": resultado[11],
        "resposta_email_conversa": (
            resultado[12] if len(resultado) > 12 else None
        ),
    }

    if len(resultado) > 16 and resultado[15] is not None:
        dados['origem_fireads'] = resultado[15]
        dados['contexto_fireads'] = resultado[16]
        retrato = (resultado[16] or {}).get('dados_titular') or {}
        if not (len(resultado) > 18 and resultado[18]):
            if 'nome' not in retrato or 'resultado_email' not in retrato:
                raise ValueError('Coletas históricas FireAds incompletas para o Funil')
            dados.update(nome_cliente=retrato['nome'], email_cliente=retrato.get('email'),
                         idade_cliente=retrato.get('idade'), resultado_email_fireads=retrato['resultado_email'])
    coleta = resultado[18] if len(resultado) > 18 else None
    if coleta:
        from core.validacoes.coleta_abertura import validar_contexto, valor, aceito
        validar_contexto({'id_conversa': id_conversa, 'contexto_coleta': coleta})
        dados['contexto_coleta'] = coleta
        dados['nome_cliente'] = valor(coleta, 'nome')
        dados['email_cliente'] = valor(coleta, 'email')
        dados['idade_cliente'] = coleta.get('idade_titular')
        dados['resultado_email_coleta'] = 'email_valido' if aceito(coleta, 'email') else coleta.get('resultado_email')
        if not dados['nome_cliente'] or not dados['resultado_email_coleta']:
            raise ValueError('Coletas históricas incompletas para o Funil')
    dados['primeiro_atendimento'] = resultado[17]
    return dados
```

## Passo 20 — `core/integrations/funil/oportunidades.py`

Ação: **alterar**. Conteúdo completo abaixo.

SHA-256 anterior: `b73f37d2fe11f11b5d1c3defcc23369bfb3a82e64dcc7ac6bc972dd2e97e8843`.

SHA-256 proposto (UTF-8/LF): `40e94cd0cf94761afb2bc95df097787a089009c9383d14f54268438f1b42126f`.

```python
"""Monta o payload de oportunidade sem conhecer banco ou transações."""

import re
from core.integrations.fireads.contrato import CANAIS, bloco_observacoes
from core.validacoes.email import ResultadoColetaEmail

from core.validacoes.turno import ROTULOS_TURNO, validar_turno

from core.triagem.perguntas import (
    montar_pergunta_triagem,
    obter_faixa_etaria_triagem,
)
from core.validacoes.email import (
    CLASSIFICACAO_EMAIL_AUSENTE,
    CLASSIFICACAO_EMAIL_NAO_INFORMADO,
    CLASSIFICACAO_EMAIL_VALIDO,
    classificar_resposta_email_aceita,
)


ORIGEM_LEAD_CHATBOT = "Meta Chatbot"
TITULO_OPORTUNIDADE = "Chatbot Lead"

ETAPAS_TRIAGEM_ESPERADAS = tuple(range(12, 18))
RESPOSTAS_TRIAGEM_EXIBICAO = {
    "nunca": "Nunca",
    "às vezes": "Às vezes",
    "as vezes": "Às vezes",
    "frequentemente": "Frequentemente",
}

MARCADORES_API_CARROSSEL = {
    "codigo_vendedor": "Code_User",
    "codigo_metodologia": "Code_Methodology",
    "codigo_canal_venda": "Code_Channel",
    "codigo_etapa": "Code_StepMethodology",
}

PADRAO_TELEFONE_BRASIL = re.compile(
    r"^55(?P<ddd>[1-9]\d)(?P<numero>\d{8,9})$"
)
AVISO_TELEFONE_INTERNACIONAL = (
    "O cliente possui um número internacional fora do padrão brasileiro, "
    "por isso o campo Telefone 1 não foi preenchido."
)


def montar_payload_oportunidade(dados_lead):
    """Converte o snapshot validado do atendimento no contrato ApiCarrossel."""
    _validar_dados_lead(dados_lead)

    nome_cliente = dados_lead["nome_cliente"].strip()
    nome_unidade = dados_lead["nome_unidade"].strip()
    titulo = f"{TITULO_OPORTUNIDADE} {nome_unidade}"
    nome_destaque = _montar_nome_destaque(dados_lead)
    telefone_funil = _normalizar_telefone_brasileiro(
        dados_lead["telefone_cliente"]
    )
    resultado_email = _resolver_resultado_email_conversa(dados_lead)
    observacoes = montar_observacoes_lead(
        dados_lead,
        resultado_email=resultado_email,
    )

    return {
        "oportunidades": [
            {
                "titulo": titulo,
                "valor": "0",
                **MARCADORES_API_CARROSSEL,
                "personalizados": [
                    {
                        "titulo": "Observações",
                        "valor": observacoes,
                    },
                    {
                        "titulo": "Origem do lead",
                        "valor": CANAIS[dados_lead["origem_fireads"]][0] if dados_lead.get("origem_fireads") else ORIGEM_LEAD_CHATBOT,
                    },
                ],
                "empresa": {
                    # O CRM usa empresa.nome como destaque principal do card.
                    "nome": nome_destaque,
                    "cnpj": "",
                    "codigo_segmento": "0",
                    "endereco_completo": {
                        "logradouro": "",
                        "numero": "",
                        "complemento": "",
                        "bairro": "",
                        "cidade": "",
                        "uf": "",
                        "cep": "",
                    },
                    "personalizados": [],
                },
                "contato": {
                    "nome": nome_cliente,
                    # Ausência é representada pelo valor vazio já usado no
                    # contrato do projeto; placeholders nunca ocupam o campo.
                    "email": resultado_email.email or "",
                    "telefone1": telefone_funil,
                    "telefone2": "",
                    "cargo": "",
                    "cpf": "",
                    "personalizados": [],
                },
            }
        ]
    }


def montar_observacoes_lead(dados_lead, *, resultado_email=None):
    """Produz o resumo humano exibido pela oportunidade no CRM."""
    nome_cliente = dados_lead["nome_cliente"].strip()
    telefone_cliente = dados_lead["telefone_cliente"].strip()
    profissao = str(dados_lead.get("profissao") or "").strip()
    profissao = profissao or "Não informada"
    aviso_telefone = ""
    resultado_email = resultado_email or _resolver_resultado_email_conversa(
        dados_lead
    )
    email_exibicao = _montar_email_exibicao(resultado_email)

    if not _normalizar_telefone_brasileiro(telefone_cliente):
        aviso_telefone = f"\n{AVISO_TELEFONE_INTERNACIONAL}\n"

    tem_link = bool(str(dados_lead.get("link_agendamento") or "").strip())
    orientacao = (
        "Confira sua plataforma de reserva (como o Calendly) e o painel de monitoramento."
        if tem_link else
        "Confira o painel de monitoramento e o número comercial para verificar se o cliente enviou mensagem."
    )
    turno = dados_lead.get("turno")
    if turno is not None:
        validar_turno(turno)
    preferencia = f"- Turno de preferência: {ROTULOS_TURNO[turno]}\n" if turno else ""
    origem = dados_lead.get("origem_fireads")
    descricoes = {
        "google": "Lead veio de uma campanha do Google Ads.",
        "meta": "Lead veio de uma campanha da Meta Ads.",
        "organico_site": "O Lead chegou ao site de maneira orgânica e preencheu o formulário.",
        "organico": "Lead entrou em contato com o chatbot de maneira orgânica, possivelmente por alguma rede social Meta da unidade.",
    }
    descricao = descricoes.get(origem, "")
    estado = dados_lead.get("contexto_fireads") or {}
    if origem == "organico" and estado.get("motivo") not in (None, "telefone_ausente"):
        descricao = "Atendimento iniciado pelo fluxo orgânico, sem importar os dados do formulário."
    canal = f"Canal de venda: {CANAIS[origem][0]}\n{descricao}\n\n" if origem else ""
    primeiro = dados_lead.get("primeiro_atendimento")
    classificacao = (
        "Novo lead" if primeiro is True else
        "Novo atendimento para Lead antigo" if primeiro is False else "Atendimento"
    )
    cabecalho = (
        f"{classificacao}\n\n"
        f"{canal}"
        "Cliente concluiu a triagem cognitiva pelo chatbot. "
        f"{orientacao} A disponibilidade e a efetivação de sua reserva devem ser conferidas pela equipe.\n\n"
        f"{preferencia}"
        f"- Nome do cliente: {nome_cliente}\n"
        f"- Telefone/WhatsApp do cliente: "
        f"{telefone_cliente}\n"
        f"- E-mail do cliente: {email_exibicao}\n"
    )

    if dados_lead["status_dependente"]:
        dados_pessoa = (
            f"\nO atendimento é para um dependente de {nome_cliente}:\n\n"
            f"- Nome do dependente: "
            f"{dados_lead['nome_dependente'].strip()}\n"
            f"- Idade do dependente: {dados_lead['idade_dependente']}\n"
        )
    else:
        dados_pessoa = f"- Idade do cliente: {dados_lead['idade_cliente']}\n"

    triagem = _montar_perguntas_e_respostas_triagem(dados_lead)

    dados_profissao = f"\n- Profissão: {profissao}\n"

    resumo = (
        cabecalho
        + dados_profissao
        + dados_pessoa
        + aviso_telefone
        + triagem
    )
    if origem:
        return bloco_observacoes(estado['id_integracao'], dados_lead['id_conversa'], resumo, versao=2)
    return f"Observações de atendimento\n\n{resumo}"


def _montar_perguntas_e_respostas_triagem(dados_lead):
    respostas = _obter_respostas_triagem_validadas(dados_lead)

    if dados_lead["status_dependente"]:
        idade_pessoa = dados_lead["idade_dependente"]
        nome_dependente = dados_lead["nome_dependente"].strip()
    else:
        idade_pessoa = dados_lead["idade_cliente"]
        nome_dependente = None

    faixa_etaria = obter_faixa_etaria_triagem(idade_pessoa)
    blocos = []

    for numero, item in enumerate(respostas, start=1):
        pergunta = montar_pergunta_triagem(
            item["id_etapa"],
            faixa_etaria=faixa_etaria,
            nome_dependente=nome_dependente,
        )
        blocos.append(
            f"-Pergunta {numero}:\n\n"
            f"{pergunta}\n\n"
            f"Resposta: {item['resposta_exibicao']}"
        )

    return "\nPerguntas e respostas da triagem:\n\n" + "\n\n".join(blocos)


def _montar_nome_destaque(dados_lead):
    """Monta a linha principal do card conforme a pessoa atendida."""
    nome_cliente = dados_lead["nome_cliente"].strip()

    if dados_lead["status_dependente"]:
        return " | ".join(
            (
                nome_cliente,
                dados_lead["nome_dependente"].strip(),
                str(dados_lead["idade_dependente"]),
            )
        )

    return " | ".join((nome_cliente, str(dados_lead["idade_cliente"])))


def _normalizar_telefone_brasileiro(telefone):
    """Prepara o wa_id brasileiro para o campo Telefone 1 do CRM."""
    somente_digitos = re.sub(r"\D", "", str(telefone or ""))
    correspondencia = PADRAO_TELEFONE_BRASIL.fullmatch(somente_digitos)

    if correspondencia is None:
        return ""

    numero = correspondencia.group("numero")

    if len(numero) == 8:
        numero = f"9{numero}"
    elif not numero.startswith("9"):
        return ""

    return f"55{correspondencia.group('ddd')}{numero}"


def _validar_dados_lead(dados_lead):
    obrigatorios = (
        "id_conversa",
        "id_unidade",
        "nome_unidade",
        "nome_cliente",
        "telefone_cliente",
    )
    ausentes = [campo for campo in obrigatorios if not dados_lead.get(campo)]

    if ausentes:
        raise ValueError(
            "Dados obrigatórios ausentes para criar a oportunidade: "
            + ", ".join(ausentes)
        )

    _obter_respostas_triagem_validadas(dados_lead)

    if dados_lead.get("status_dependente"):
        if not dados_lead.get("nome_dependente"):
            raise ValueError("Nome do dependente ausente")
        if dados_lead.get("idade_dependente") is None:
            raise ValueError("Idade do dependente ausente")
    elif dados_lead.get("idade_cliente") is None:
        raise ValueError("Idade do cliente ausente")


def _resolver_resultado_email_conversa(dados_lead):
    if dados_lead.get('contexto_coleta') or dados_lead.get('origem_fireads'):
        classificacao = dados_lead.get('resultado_email_coleta') or dados_lead.get('resultado_email_fireads')
        if classificacao not in {CLASSIFICACAO_EMAIL_VALIDO, CLASSIFICACAO_EMAIL_AUSENTE, CLASSIFICACAO_EMAIL_NAO_INFORMADO}:
            raise ValueError('Resultado histórico de email inválido')
        return ResultadoColetaEmail(aceita=True, classificacao=classificacao, email=dados_lead.get('email_cliente'))

    resposta_historica = dados_lead.get("resposta_email_conversa")

    if resposta_historica is not None:
        return classificar_resposta_email_aceita(resposta_historica)

    # Compatibilidade com atendimentos legados que não possuem o vínculo
    # histórico da resposta de e-mail. Dados novos sempre usam a conversa.
    email_cadastro = dados_lead.get("email_cliente")
    if email_cadastro:
        return classificar_resposta_email_aceita(email_cadastro)

    return classificar_resposta_email_aceita("")


def _montar_email_exibicao(resultado_email):
    if resultado_email.classificacao == CLASSIFICACAO_EMAIL_VALIDO:
        return resultado_email.email

    if resultado_email.classificacao == CLASSIFICACAO_EMAIL_AUSENTE:
        return "não tem"

    if resultado_email.classificacao == CLASSIFICACAO_EMAIL_NAO_INFORMADO:
        return "não informado"

    raise ValueError(
        "Classificação de e-mail inválida para observações do Funil "
        f"(classificacao={resultado_email.classificacao!r})"
    )


def _obter_respostas_triagem_validadas(dados_lead):
    respostas = dados_lead.get("triagem_respostas")

    if not isinstance(respostas, (list, tuple)):
        raise ValueError("Respostas da triagem ausentes ou inválidas")

    ids_etapas = []
    respostas_validadas = []

    for item in respostas:
        if not isinstance(item, dict):
            raise ValueError("Item de resposta da triagem inválido")

        id_etapa = item.get("id_etapa")
        resposta = item.get("resposta")
        resposta_normalizada = str(resposta or "").strip().casefold()

        ids_etapas.append(id_etapa)

        if resposta_normalizada not in RESPOSTAS_TRIAGEM_EXIBICAO:
            raise ValueError(
                "A triagem contém resposta fora do domínio esperado "
                f"(etapa={id_etapa}, resposta={resposta})"
            )

        respostas_validadas.append(
            {
                "id_etapa": id_etapa,
                "resposta": resposta_normalizada,
                "resposta_exibicao": RESPOSTAS_TRIAGEM_EXIBICAO[
                    resposta_normalizada
                ],
            }
        )

    if tuple(ids_etapas) != ETAPAS_TRIAGEM_ESPERADAS:
        raise ValueError(
            "A oportunidade exige respostas ordenadas para as etapas "
            "12, 13, 14, 15, 16 e 17"
        )

    return respostas_validadas
```

## Passo 21 — `core/integrations/fireads/destino_coleta.py`

Ação: **criar**. Conteúdo completo abaixo.

SHA-256 anterior: `arquivo novo`.

SHA-256 proposto (UTF-8/LF): `d1f41de70cfa274670387129a11e0e21a8a98589384efddd0ad69e2e27024fa2`.

```python
"""Escolha persistível do alvo de entrega para a coleta por campo."""

from copy import deepcopy
from core.validacoes.coleta_abertura import aceito, campo
from core.integrations.fireads.coleta_abertura import campos_registro, compativel
from core.integrations.fireads.aba_geral import mais_recente, referencia_registro, relocalizar, numero_linha
from core.integrations.fireads.contrato import CANAIS, ErroFireAds, telefone, localizar, acrescentar_observacoes
from core.integrations.fireads.destino_dashboard import linhas_com_bloco


def identidade_entrega(estado):
    # Conhecidos no formulário não são substituídos por correções posteriores.
    campos = deepcopy(estado['mensagem_original'])
    for tipo in ('email', 'nome', 'destinatario'):
        if campos[tipo]['status'] != 'aceito':
            campos[tipo] = deepcopy(estado['campos'][tipo])
    return campos


def escolher(rows, snapshot):
    if snapshot.get('referencia') is not None:
        # Exclusão/edição de um registro já vinculado exige conferência.
        relocalizar(rows, snapshot['referencia'], snapshot['aba'])
        return {'tipo': 'update', 'referencia': snapshot['referencia']}
    encontrados = localizar(rows, snapshot['telefone'], 'WhatsApp', incluir_equivalentes=True)
    candidatos = encontrados
    if snapshot['rota_formulario_chat']:
        identidade = snapshot['identidade_coleta']
        # Sem confirmação final de e-mail/destinatário não inventar equivalência.
        candidatos = [r for r in encontrados if all(identidade[c]['status'] == 'aceito' for c in ('email', 'destinatario'))
                       and compativel(identidade, campos_registro(r), campos=('email', 'destinatario'))]
    row = mais_recente(candidatos, snapshot.get('fuso'))
    if row:
        return {'tipo': 'update', 'referencia': referencia_registro(row, snapshot['aba'], snapshot.get('fuso'))}
    email = str(snapshot.get('email') or '').strip().casefold()
    outros = [r for r in rows if r not in encontrados]
    if email and any(str(r.get('Email') or '').strip().casefold() == email for r in outros):
        raise ErroFireAds('Email já presente em outro telefone; conferir identidade')
    return {'tipo': 'create'}


def preparar(rows, snapshot, bloco):
    acrescentar_observacoes(None, bloco)
    encontrados = localizar(rows, snapshot['telefone'], 'WhatsApp', incluir_equivalentes=True)
    if linhas_com_bloco(encontrados, bloco):
        return None
    alvo = snapshot.get('destino')
    if not alvo:
        raise ErroFireAds('Destino da coleta ainda não foi persistido')
    if alvo['tipo'] == 'update':
        row = relocalizar(rows, alvo['referencia'], snapshot['aba'])
        if 'Observação' not in row:
            raise ErroFireAds('Observação ausente; não sobrescrever')
        obs, mudou = acrescentar_observacoes(row.get('Observação'), bloco)
        return {'row': numero_linha(row), 'observacoes': obs} if mudou else None
    if alvo['tipo'] != 'create':
        raise ErroFireAds('Tipo de destino desconhecido')
    # Rechecar identidade cruzada também em retries de um create planejado.
    email = str(snapshot.get('email') or '').strip().casefold()
    if email and any(r not in encontrados and str(r.get('Email') or '').strip().casefold() == email for r in rows):
        raise ErroFireAds('Email já presente em outro telefone; conferir identidade')
    return {'dados': {'Nome': snapshot['nome'], 'Email': snapshot['email'],
                       'WhatsApp': telefone(snapshot['telefone']), 'Perfil/Faixa': snapshot['perfil'],
                       'Para quem é': snapshot['para_quem'], 'Canal': CANAIS[snapshot['origem']][0], 'Observação': bloco}}
```

## Passo 22 — `core/repositories/fireads/envios.py`

Ação: **alterar**. Conteúdo completo abaixo.

SHA-256 anterior: `fddcf964fff252a12d6178e08f894bbfa31bf15020105b5ca9795974bfce81ce`.

SHA-256 proposto (UTF-8/LF): `b9daee3a354d78bac39326485e7b00dc4dea6f5cdc42f0b1a9865e4418cf67f1`.

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
        from core.integrations.fireads.destino_coleta import identidade_entrega
        coleta = dados['contexto_coleta']
        identidade = identidade_entrega(coleta)
        alvo = identidade['destinatario']
        snapshot.update(versao=3, rota_formulario_chat=coleta['rota_formulario_chat'],
                        identidade_coleta=identidade, destino=None,
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

## Passo 23 — `core/repositories/fireads/destino_coleta.py`

Ação: **criar**. Conteúdo completo abaixo.

SHA-256 anterior: `arquivo novo`.

SHA-256 proposto (UTF-8/LF): `c55f0498d13f7fbab86696595ac96b37862badbccd8c05f18faf474714dca2b0`.

```python
"""Congela a decisão de update/create sob a mesma reserva do envio."""

from psycopg.types.json import Jsonb
from core.repositories.fireads.envios import conferir_posse


def salvar_destino(envio, destino, cursor):
    conferir_posse(envio, cursor)
    cursor.execute("""UPDATE chatbot.envios_dash SET snapshot=jsonb_set(snapshot,'{destino}',%s),
                      atualizado_em=clock_timestamp()
                      WHERE id_envio_dash=%s AND status='processing' AND attempt_count=%s
                        AND (snapshot->'destino' IS NULL OR snapshot->'destino'='null'::jsonb)
                      RETURNING snapshot""", (Jsonb(destino), envio['id'], envio['tentativa']))
    row = cursor.fetchone()
    if row is None:
        raise ValueError('Destino já congelado ou reserva perdida')
    return row[0]
```

## Passo 24 — `workers/worker_funil/fireads.py`

Ação: **alterar**. Conteúdo completo abaixo.

SHA-256 anterior: `52fecc425ca2830f177500c1973b331411c6b7781ff43e8466e99efe3931bd21`.

SHA-256 proposto (UTF-8/LF): `ccec58c3c36696a4ad1df930acdffa3cdb4392f4eb214347c1487a843a0ab828`.

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
        if snapshot.get('versao') == 3 and not {'Para quem é', 'Canal', 'Data/Hora'} <= set(dados['headers']):
            raise ErroFireAds('Cabeçalhos da coleta incompletos')
        if snapshot.get("versao") in {2, 3}:
            bloco = snapshot["observacoes"]
        elif "versao" not in snapshot:
            bloco = bloco_observacoes(
                envio["integracao"], envio["conversa"], snapshot["observacoes"]
            )
        else:
            raise ErroFireAds("Versão de envio desconhecida")
        if snapshot.get('versao') == 3 and not snapshot.get('destino'):
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

## Passo 25 — `core/database/deploy_database/fireads_script.py`

Ação: **alterar**. Conteúdo completo abaixo.

SHA-256 anterior: `e4ad86d8a2a907e4c5281e99fe6b2e35597381d8d2aed61a39a0a539bcb5a697`.

SHA-256 proposto (UTF-8/LF): `549fe178458bd15f27924db14c1d1d8b5b941cf70fe732a02bd40122875648b6`.

```python
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
        geral = caminho.with_name("20261014_fireads_aba_geral.sql").read_text(encoding="utf-8")
        cursor.execute(geral.split("-- INICIO DDL FIREADS ABA GERAL\n", 1)[1].split(
            "-- FIM DDL FIREADS ABA GERAL", 1
        )[0])
        coleta = caminho.with_name('20261019_coleta_abertura.sql').read_text(encoding='utf-8')
        cursor.execute(coleta.split('-- INICIO DDL COLETA ABERTURA\n', 1)[1].split(
            '-- FIM DDL COLETA ABERTURA', 1)[0])
```

## Passo 26 — `tests/fixtures/fireads.py`

Ação: **alterar**. Conteúdo completo abaixo.

SHA-256 anterior: `b0cdb689565038a0ce6973c3669dea5752f7821eba25e67f65c746018c9ce366`.

SHA-256 proposto (UTF-8/LF): `593fd14a8aa407522d8574c818e5f921b766bbb4e0dc8bd10a7b8c2f07511532`.

```python
"""Migração real nas bases PostgreSQL descartáveis da suíte."""

from pathlib import Path

MIGRACAO_FIREADS = (
    Path(__file__).resolve().parents[2]
    / "deploy/migrations/20261007_fireads_chat_customizacao.sql"
)


def aplicar_fireads(cursor, *, aba_geral=True):
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
    if aba_geral:
        aplicar_aba_geral(cursor)


def aplicar_aba_geral(cursor):
    texto = MIGRACAO_FIREADS.with_name("20261014_fireads_aba_geral.sql").read_text(encoding="utf-8")
    cursor.execute(texto.split("-- INICIO DDL FIREADS ABA GERAL\n", 1)[1].split(
        "-- FIM DDL FIREADS ABA GERAL", 1
    )[0])

    coleta = MIGRACAO_FIREADS.with_name('20261019_coleta_abertura.sql').read_text(encoding='utf-8')
    cursor.execute(coleta.split('-- INICIO DDL COLETA ABERTURA\n', 1)[1].split('-- FIM DDL COLETA ABERTURA', 1)[0])


def como_aba_geral(google, meta):
    """Representa na aba consolidada os formulários históricos usados pelas fixtures."""
    rows = []
    for row in google:
        rows.append(dict(row, **{
            "Canal": "Google Ads", "Para quem é": row.get("Perfil/Faixa"),
            "_row": row.get("_row", len(rows) + 2),
        }))
    for row in meta:
        rows.append({
            "Nome": row.get("full_name"), "Email": row.get("email"),
            "WhatsApp": row.get("phone_number"), "Para quem é": row.get("para_quem"),
            "Data/Hora": row.get("created_time"), "Canal": "Meta Ads",
            "_row": row.get("_row", len(rows) + 2),
        })
    return rows
```

## Passo 27 — `tests/integration/test_fireads_postgres.py`

Ação: **alterar**. Conteúdo completo abaixo.

SHA-256 anterior: `12037cc58295ce98043e452663c46c089a92ce2c40bc6be37797cc7be778e2a3`.

SHA-256 proposto (UTF-8/LF): `a5615b082ac5c6cc994cecac26047684fde45b8e5fc0ba135ee5614059cab848`.

```python
"""FireAds em PostgreSQL local descartável; apenas HTTP é substituído."""

from contextlib import contextmanager, ExitStack
from datetime import timedelta
import os
from threading import Event
from tests.fixtures.fireads import como_aba_geral
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
        self.indicador = self.enterContext(patch(
            "workers.worker_consulta_dash.consulta_worker.indicar_digitacao", return_value=True,
        ))
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
        legado = (self._testMethodName == "test_migracao_com_registro_legado_preserva_resultado_e_reexecucao"
                  or self._testMethodName.startswith("test_migracao_aba_geral"))
        aplicar_fireads(self.cursor, aba_geral=not legado)
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
            "id_hash": "wamid.fireads",
            "tipo_mensagem": "text",
            "conteudo_texto": "Oi",
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
        decisao = interpretar(como_aba_geral([GOOGLE], []), NUMERO, None)
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
        snapshot = self.conn.execute("SELECT snapshot FROM chatbot.envios_dash").fetchone()[0]
        self.assertIs(snapshot["status_dependente"], False)
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
            [("20261007_fireads_v1",), ("20261009_consulta_dash_v1",),
             ("20261014_fireads_aba_geral_v1",), ("20261019_coleta_abertura_v1",)],
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
            31,
        )

    def test_importacao_dependente_e_retry_recuperam_snapshot(self):
        cid, mensagem, versao, contexto = self.preparar_mensagem()
        api = Mock()
        rows = como_aba_geral([dict(GOOGLE, **{"Perfil/Faixa": "Para outra pessoa"})], [])
        api.consultar.return_value = {"headers": list(rows[0]), "rows": rows}
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

    def test_meta_perfil_com_biografia_persiste_extracao_e_recupera_no_retry(self):
        cid, mensagem, versao, contexto = self.preparar_mensagem()
        registro = {
            "full_name": "Edcarlos Oliveira | Programador",
            "email": " EDCARLOS@INTRANET ", "phone_number": NUMERO,
            "para_quem": "pai_ou_mae", "_row": 24,
            "created_time": "2026-10-14T04:26:03Z",
        }
        api = Mock()
        rows = como_aba_geral([], [registro])
        api.consultar.return_value = {"headers": list(rows[0]), "rows": rows}
        with patch("workers.worker_consulta_dash.consulta.ClienteFireAds", return_value=api):
            obtido = self.preparar_apos_http(contexto, mensagem, versao)
        self.assertEqual(
            self.conn.execute("SELECT nome,email FROM chatbot.cliente").fetchone(),
            ("Edcarlos", "edcarlos@intranet"),
        )
        self.assertTrue(obtido["conversa"]["status_dependente"])
        self.assertEqual(obtido["contexto_fireads"]["origem"], "meta")
        self.assertEqual(obtido["contexto_fireads"]["resultado"], "importado")
        dados, aplicacao = self.conn.execute(
            "SELECT dados,aplicacao FROM chatbot.consulta_fireads WHERE id_conversa=%s", (cid,),
        ).fetchone()
        self.assertEqual(dados["fontes"]["geral"], rows)
        self.assertEqual(aplicacao, obtido["contexto_fireads"])
        with patch("workers.worker_consulta_dash.consulta.ClienteFireAds") as http:
            self.assertEqual(preparar_abertura(contexto, mensagem, versao, self.cursor), obtido)
            http.assert_not_called()
        self.assertEqual(self.conn.execute(
            "SELECT count(*) FROM chatbot.dependente WHERE id_conversa=%s", (cid,),
        ).fetchone()[0], 1)

    def test_lock_perdido_durante_http_nao_importa_dados(self):
        cid, mensagem, versao, contexto = self.preparar_mensagem()

        def resposta(aba):
            with psycopg.connect(DSN) as outro:
                outro.execute(
                    "UPDATE chatbot.conversa SET lock_version=lock_version+1 WHERE id_conversa=%s", (cid,),
                )
            rows = como_aba_geral([GOOGLE], [])
            return {"headers": list(rows[0]), "rows": rows}

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
            return_value=self.resultado_google(),
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
        bloco = snap["observacoes"]
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
        with self.assertRaises(ConsultaFireAdsPendente) as espera:
            preparar_abertura(contexto, mensagem, versao, self.cursor)
        self.assertTrue(espera.exception.consulta_nova)
        self.conn.commit()
        return cid, mensagem, versao, contexto

    def test_rechecagem_nao_sinaliza_consulta_nova(self):
        cid, mensagem, versao, contexto = self.solicitar_pendente()
        with self.assertRaises(ConsultaFireAdsPendente) as espera:
            preparar_abertura(contexto, mensagem, versao, self.cursor)
        self.assertFalse(espera.exception.consulta_nova)
        self.assertFalse(pendencias.solicitar(
            consulta.buscar_abertura(cid, self.cursor), cid, NUMERO, self.cursor,
        ))
        self.assertEqual(self.conn.execute(
            "SELECT count(*),max(tentativas) FROM chatbot.consulta_fireads",
        ).fetchone(), (1, 0))

    def test_mensagem_digitacao_da_reserva_confere_unidade_entrada_e_estado(self):
        cid, mensagem, _, _ = self.solicitar_pendente()
        reserva = pendencias.reservar(self.cursor)
        self.conn.commit()
        self.assertEqual(pendencias.buscar_mensagem_aguardando(reserva, self.cursor), {
            "id_mensagem": mensagem["id_mensagem"], "id_phone_unidade": "phone-teste",
            "id_hash": "wamid.fireads",
        })
        self.assertIsNone(pendencias.buscar_mensagem_aguardando(
            dict(reserva, versao=reserva["versao"] - 1), self.cursor,
        ))
        alteracoes = (
            "UPDATE chatbot.unidade SET status_pagamento=FALSE",
            "UPDATE chatbot.conversa SET status_ativa=FALSE",
            "UPDATE chatbot.conversa SET id_etapa_atual=1",
            "UPDATE chatbot.fila_mensagens SET status='sent'",
            "UPDATE chatbot.fila_mensagens SET id_phone_unidade='outra-unidade'",
            "UPDATE chatbot.fila_mensagens SET cliente_telefone='5511999990003'",
            "UPDATE chatbot.integracao_fireads SET integracao_ativa=FALSE",
            "UPDATE chatbot.integracao_fireads SET aba_destino='Outra aba'",
            "UPDATE chatbot.consulta_fireads SET solicitado_em=now()-INTERVAL '400 seconds',"
            " prazo_final=now()-INTERVAL '1 second'",
            "INSERT INTO chatbot.historico_mensagens"
            " (id_conversa,id_etapa,received_data_hora,cliente_telefone,conteudo_texto,"
            " tipo_mensagem,id_hash_msg,id_phone_unidade,unidade_telefone,quem_enviou,status_envio)"
            f" VALUES({cid},1,now(),'{NUMERO}','Olá','text','wamid.bot',"
            " 'phone-teste','5511999990000','bot','sent')",
        )
        for sql in alteracoes:
            with self.subTest(alteracao=sql):
                self.cursor.execute("SAVEPOINT estado_digitacao")
                self.cursor.execute(sql)
                self.assertIsNone(pendencias.buscar_mensagem_aguardando(reserva, self.cursor))
                self.cursor.execute("ROLLBACK TO SAVEPOINT estado_digitacao")
                self.cursor.execute("RELEASE SAVEPOINT estado_digitacao")

    def test_worker_consulta_sinaliza_sem_transacao_aberta_e_mantem_reserva(self):
        cid, mensagem, _, _ = self.solicitar_pendente()
        conexao_worker = psycopg.connect(DSN)
        self.addCleanup(conexao_worker.close)
        def conferir_chamada(*args, **kwargs):
            self.assertEqual(conexao_worker.info.transaction_status, psycopg.pq.TransactionStatus.IDLE)
            self.assertEqual(args, ("phone-teste", "wamid.fireads"))
            self.assertEqual(kwargs, {"id_mensagem": mensagem["id_mensagem"], "id_conversa": cid})
            with psycopg.connect(DSN) as concorrente:
                self.assertIsNone(pendencias.reservar(concorrente.cursor()))
        self.indicador.side_effect = conferir_chamada
        with patch("workers.worker_consulta_dash.consulta_worker.get_conn", return_value=conexao_worker), patch(
            "workers.worker_consulta_dash.consulta_worker.consultar", return_value=self.resultado_google(),
        ):
            self.assertTrue(executar_ciclo())
        self.indicador.assert_called_once()
        self.assertEqual(self.conn.execute(
            "SELECT status,resultado FROM chatbot.consulta_fireads",
        ).fetchone(), ('concluida', 'importado'))

    def resultado_google(self):
        entrada = self.conn.execute('SELECT entrada FROM chatbot.consulta_fireads ORDER BY id_consulta DESC LIMIT 1').fetchone()
        if entrada and entrada[0].get('coleta'):
            from core.integrations.fireads.coleta_abertura import interpretar_parcial
            e = entrada[0]
            rows = como_aba_geral([GOOGLE], [])
            return {'decisao': interpretar_parcial(rows, NUMERO, e['fuso'], e['aba'], e['coleta']), 'fontes': {'geral': rows}}
        return {
            "decisao": interpretar(como_aba_geral([GOOGLE], []), NUMERO, None),
            "fontes": {"google": [GOOGLE], "meta": []},
        }

    def test_migracao_aba_geral_preserva_resultados_prazos_e_envios(self):
        from psycopg.types.json import Jsonb
        from core.integrations.fireads.aba_geral import configuracao_compativel

        cid, mensagem, versao, contexto = self.preparar_mensagem()
        entrada = self.conn.execute("""SELECT jsonb_build_object(
            'url',url_dashbord,'aba_google',aba_google,'aba_meta',aba_meta,
            'fuso',fuso_formularios,'numero',%s::text) FROM chatbot.integracao_fireads""",
            (NUMERO,)).fetchone()[0]
        decisao = self.resultado_google()
        # O resultado antigo não possuía referência da aba consolidada.
        decisao['decisao'].pop('referencia')
        decisao['decisao'].pop('versao')
        self.cursor.execute("""INSERT INTO chatbot.consulta_fireads
            (id_unidade,id_integracao_fireads,id_conversa,entrada,status,
             consulta_concluida,resultado,dados,consultado_em)
            VALUES(1,1,%s,%s,'concluida',TRUE,'importado',%s,now())""",
            (cid, Jsonb(entrada), Jsonb(decisao)))
        self.cursor.execute("""INSERT INTO chatbot.consulta_fireads
            (id_unidade,id_integracao_fireads,id_conversa,entrada,status,
             solicitado_em,prazo_final,tentativas,versao_reserva,processing_started_at,reserva_ate)
            VALUES(1,1,1,%s,'processando',now()-INTERVAL '100 seconds',
                   now()+INTERVAL '200 seconds',2,3,now(),now()+INTERVAL '210 seconds')""",
            (Jsonb(entrada),))
        prazo = self.conn.execute("SELECT solicitado_em,prazo_final FROM chatbot.consulta_fireads WHERE id_conversa=1").fetchone()
        legado = {'payload_funil': {'texto': 'NOVO LEAD antigo'}, 'canal': '113340',
                  'url_funil': 'https://example.com/api', 'observacoes': 'Texto original'}
        self.cursor.execute("INSERT INTO chatbot.funil_envios(id_conversa) VALUES(1)")
        self.cursor.execute("""INSERT INTO chatbot.envios_dash
            (id_conversa,id_unidade,id_integracao_fireads,snapshot) VALUES(1,1,1,%s)""", (Jsonb(legado),))
        self.conn.commit()
        sql = MIGRACAO_FIREADS.with_name('20261014_fireads_aba_geral.sql').read_text(encoding='utf-8')
        for _ in range(2):
            self.conn.execute(sql, prepare=False)
        # O runtime atual só entra depois de todas as migrações do deploy.
        self.conn.execute(MIGRACAO_FIREADS.with_name('20261019_coleta_abertura.sql').read_text(encoding='utf-8'), prepare=False)
        pendente = self.conn.execute("""SELECT status,entrada,tentativas,versao_reserva,
            solicitado_em,prazo_final,processing_started_at,reserva_ate
            FROM chatbot.consulta_fireads WHERE id_conversa=1""").fetchone()
        self.assertEqual(pendente[0], 'pendente')
        self.assertEqual(pendente[1]['versao'], 2)
        self.assertEqual(pendente[1]['entrada_anterior']['aba_google'], entrada['aba_google'])
        self.assertEqual(pendente[2:4], (2, 4))
        self.assertEqual(pendente[4:6], prazo)
        self.assertEqual(pendente[6:], (None, None))
        salvo = self.conn.execute("SELECT entrada,dados,aplicado_em FROM chatbot.consulta_fireads WHERE id_conversa=%s", (cid,)).fetchone()
        self.assertEqual(salvo[1:], (decisao, None))
        self.assertTrue(configuracao_compativel(salvo[0], consulta.buscar_abertura(cid, self.cursor)))
        with patch('workers.worker_consulta_dash.consulta.ClienteFireAds') as http:
            aplicado = preparar_abertura(contexto, mensagem, versao, self.cursor)
        http.assert_not_called()
        self.assertEqual(aplicado['contexto_fireads']['origem'], 'google')
        self.assertEqual(self.conn.execute('SELECT snapshot FROM chatbot.envios_dash').fetchone()[0], legado)
        self.assertEqual(self.conn.execute('SELECT snapshot FROM chatbot.funil_envios').fetchone()[0]['payload_funil'], legado['payload_funil'])
        self.assertEqual(self.conn.execute("SELECT count(*) FROM information_schema.columns WHERE table_schema='chatbot' AND table_name='integracao_fireads' AND column_name IN ('aba_google','aba_meta')").fetchone()[0], 0)
        auditoria = self.conn.execute("SELECT dados FROM chatbot.migracoes_fireads WHERE versao='20261014_fireads_aba_geral_v1'").fetchone()[0]
        self.assertEqual(auditoria['contagens']['consultas'], 2)
        self.assertEqual(auditoria['configuracoes_anteriores'][0]['aba_google'], entrada['aba_google'])

    def test_migracao_aba_geral_nao_apaga_alteracao_real_anterior(self):
        from psycopg.types.json import Jsonb
        from tests.fixtures.fireads import aplicar_aba_geral
        cid, mensagem, versao, contexto = self.preparar_mensagem()
        entrada = {'url': 'https://script.google.com/macros/s/antigo/exec',
                   'aba_google': 'Antiga', 'aba_meta': 'Antiga Meta', 'fuso': None, 'numero': NUMERO}
        self.cursor.execute("""INSERT INTO chatbot.consulta_fireads
            (id_conversa,id_unidade,id_integracao_fireads,entrada,status,consulta_concluida,resultado,dados,consultado_em)
            VALUES(%s,1,1,%s,'concluida',TRUE,'importado',%s,now())""",
            (cid, Jsonb(entrada), Jsonb(self.resultado_google())))
        aplicar_aba_geral(self.cursor)
        resultado = preparar_abertura(contexto, mensagem, versao, self.cursor)
        self.assertEqual(resultado['contexto_fireads']['origem'], 'organico')
        self.assertEqual(self.conn.execute('SELECT nome FROM chatbot.cliente').fetchone()[0], 'Antigo')

    def test_funil_sem_fireads_recupera_payload_congelado_no_retry(self):
        from core.repositories.funil import envios as fila_funil
        from core.repositories.funil import snapshots
        from workers.worker_funil.processamento import processar_envio_funil
        cid = self.nova_conversa()
        self.cursor.execute("UPDATE chatbot.conversa SET id_etapa_atual=19,profissao='Professora',turno='manha' WHERE id_conversa=%s", (cid,))
        self.cursor.execute('UPDATE chatbot.cliente SET idade=35')
        self.cursor.execute("""INSERT INTO chatbot.respostas_desafios(id_conversa,id_etapa,resposta)
            SELECT %s,etapa,'Às vezes' FROM generate_series(12,17) etapa""", (cid,))
        fila_funil.sincronizar_envios_elegiveis(self.cursor)
        envio = fila_funil.reivindicar_proximo_envio(self.cursor)
        self.conn.commit()
        alvo = 'workers.worker_funil.processamento.enviar_oportunidade'
        with patch(alvo, side_effect=RuntimeError('HTTP indisponível')) as http:
            self.assertFalse(processar_envio_funil(envio, self.conn, self.cursor))
        self.assertTrue(http.called, self.conn.execute('SELECT ultimo_erro FROM chatbot.funil_envios').fetchone())
        primeira = http.call_args.kwargs
        self.assertEqual(primeira['codigo_canal_venda'], '113340')
        self.assertEqual(self.conn.execute('SELECT count(*) FROM chatbot.envios_dash').fetchone()[0], 0)
        self.cursor.execute("UPDATE chatbot.cliente SET nome='Nome alterado depois'")
        self.cursor.execute("UPDATE chatbot.integracao_funil_unidade SET codigo_canal_venda='113336'")
        self.cursor.execute("UPDATE chatbot.funil_envios SET next_attempt_at=NOW()-INTERVAL '1 second'")
        envio = fila_funil.reivindicar_proximo_envio(self.cursor)
        snapshot = snapshots.buscar(cid, self.cursor)
        self.cursor.execute("UPDATE chatbot.funil_envios SET processing_started_at=clock_timestamp()-INTERVAL '60 seconds'")
        with self.assertRaises(ValueError):
            snapshots.conferir(envio, snapshot, self.cursor, lease_segundos=30)
        snapshots.conferir(envio, snapshot, self.cursor, lease_segundos=120)
        self.conn.commit()
        with patch(alvo, return_value={'resposta': {}, 'status_http': 200}) as http:
            self.assertTrue(processar_envio_funil(envio, self.conn, self.cursor))
        self.assertEqual(http.call_args.kwargs, primeira)
        self.assertEqual(self.conn.execute('SELECT status FROM chatbot.funil_envios').fetchone()[0], 'sent')

    def test_classificacao_historica_considera_apenas_conversas_anteriores_do_chat(self):
        self.cursor.execute('UPDATE chatbot.conversa SET id_etapa_atual=19 WHERE id_conversa=1')
        self.assertTrue(buscar_dados_lead_funil(1, self.cursor)['primeiro_atendimento'])
        cid = self.nova_conversa()
        self.cursor.execute('UPDATE chatbot.conversa SET id_etapa_atual=19 WHERE id_conversa=%s', (cid,))
        self.assertFalse(buscar_dados_lead_funil(cid, self.cursor)['primeiro_atendimento'])
        # Uma conversa posterior não muda a classificação da primeira.
        self.assertTrue(buscar_dados_lead_funil(1, self.cursor)['primeiro_atendimento'])
        self.cursor.execute("""INSERT INTO chatbot.unidade(nome_unidade,cnpj,email_responsavel,telefone,waba_id,phone_number_id)
            VALUES('Outra unidade','outro','outro@example.com','5511999990003','outro','phone-outro');
            INSERT INTO chatbot.atendimento_customizado(id_unidade,nome_agente,genero,numero_comercial)
            VALUES(2,'Dora','feminino','5511999990004');""")
        outro = inserindo_em_conversa_caso_seja_nova(1, 2, self.cursor)
        self.cursor.execute('UPDATE chatbot.conversa SET id_etapa_atual=19 WHERE id_conversa=%s', (outro,))
        self.assertTrue(buscar_dados_lead_funil(outro, self.cursor)['primeiro_atendimento'])

    def test_organico_site_importa_e_compartilha_observacoes_nos_dois_envios(self):
        from core.repositories.funil import envios as fila_funil
        from workers.worker_funil.processamento import processar_envio_funil
        cid, mensagem, versao, contexto = self.solicitar_pendente()
        reserva = pendencias.reservar(self.cursor)
        row = dict(como_aba_geral([GOOGLE], [])[0], Canal='Organico Site')
        from core.integrations.fireads.coleta_abertura import interpretar_parcial
        decisao = interpretar_parcial([row], NUMERO, None, reserva['entrada']['aba'], reserva['entrada']['coleta'])
        self.assertTrue(pendencias.concluir(reserva, {'decisao': decisao, 'fontes': {'geral': [row]}}, self.cursor))
        pendencias.liberar_reserva(reserva['id_consulta'], self.cursor)
        resultado = preparar_abertura(contexto, mensagem, versao, self.cursor)
        self.assertEqual(resultado['contexto_fireads']['origem'], 'organico_site')
        self.cursor.execute("UPDATE chatbot.conversa SET id_etapa_atual=19,profissao='Professora',turno='manha' WHERE id_conversa=%s", (cid,))
        self.cursor.execute('UPDATE chatbot.cliente SET idade=35')
        self.cursor.execute("""INSERT INTO chatbot.respostas_desafios(id_conversa,id_etapa,resposta)
            SELECT %s,etapa,'Às vezes' FROM generate_series(12,17) etapa""", (cid,))
        consulta.guardar_coletas(
            {'id_cliente': 1, 'id_conversa': cid, 'contexto_fireads': resultado['contexto_fireads']},
            {'destino_dado': 'cliente'}, self.cursor,
        )
        from core.repositories.atendimento.coleta_abertura import guardar_coletas
        guardar_coletas({'id_cliente': 1, 'id_conversa': cid,
                         'contexto_coleta': resultado['contexto_coleta']},
                        {'destino_dado': 'cliente'}, self.cursor)
        fila_funil.sincronizar_envios_elegiveis(self.cursor)
        envio = fila_funil.reivindicar_proximo_envio(self.cursor)
        self.conn.commit()
        with patch('workers.worker_funil.processamento.enviar_oportunidade', return_value={'resposta': {}, 'status_http': 200}) as http:
            sucesso = processar_envio_funil(envio, self.conn, self.cursor)
            self.assertTrue(sucesso, self.conn.execute('SELECT ultimo_erro FROM chatbot.funil_envios').fetchone())
        self.assertEqual(http.call_args.kwargs['codigo_canal_venda'], '113481')
        payload = http.call_args.kwargs['payload']
        obs = next(c['valor'] for c in payload['oportunidades'][0]['personalizados'] if c['titulo'] == 'Observações')
        snapshot = self.conn.execute('SELECT snapshot FROM chatbot.envios_dash').fetchone()[0]
        self.assertEqual(snapshot['observacoes'], obs)
        self.assertEqual(snapshot['referencia']['linha'], row['_row'])
        self.assertIn('Orgânico Site', obs)
        self.assertIn('Novo atendimento para Lead antigo', obs)

    def test_conflito_email_preserva_referencia_sem_importacao_parcial(self):
        # Consulta já existente antes do novo contrato mantém importação legada.
        cid, mensagem, versao, contexto = self.preparar_mensagem()
        pendencias.solicitar(consulta.buscar_abertura(cid, self.cursor), cid, NUMERO, self.cursor)
        self.conn.commit()
        self.cursor.execute("""INSERT INTO chatbot.cliente(nome,waid_telefone,email)
            VALUES('Outro','5511999990003','ana@example.com')""")
        reserva = pendencias.reservar(self.cursor)
        resultado = self.resultado_google()
        self.assertTrue(pendencias.concluir(reserva, resultado, self.cursor))
        pendencias.liberar_reserva(reserva['id_consulta'], self.cursor)
        self.conn.commit()
        aplicado = preparar_abertura(contexto, mensagem, versao, self.cursor)['contexto_fireads']
        self.assertEqual(aplicado['motivo'], 'conflito_email')
        self.assertEqual(aplicado['origem'], 'organico')
        self.assertEqual(aplicado['dados_titular'], {})
        self.assertEqual(aplicado['referencia'], resultado['decisao']['referencia'])
        self.assertEqual(self.conn.execute('SELECT nome,email FROM chatbot.cliente WHERE id_cliente=1').fetchone(), ('Antigo', 'antigo@example.com'))

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
            "UPDATE chatbot.integracao_fireads SET aba_destino='Outra aba'"
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
        from psycopg.types.json import Jsonb
        cid = self.nova_conversa()
        # Semeia o contrato histórico sem chamar o runtime novo no esquema antigo.
        decisao = dict(interpretar(como_aba_geral([GOOGLE], []), NUMERO, None),
                       id_conversa=cid, concluida=True)
        self.cursor.execute('UPDATE chatbot.conversa SET origem_fireads=%s,contexto_fireads=%s WHERE id_conversa=%s',
                            (decisao['origem'], Jsonb(decisao), cid))
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
        preparado = preparar_abertura(contexto, mensagem, versao, self.cursor)
        self.assertEqual(preparado['conversa'], contexto['conversa'])
        self.assertEqual(preparado['contexto_coleta']['etapa_inicial'], 1)
        self.assertNotIn('contexto_fireads', preparado)
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
```

## Passo 28 — `tests/unit/test_coleta_abertura.py`

Ação: **criar**. Conteúdo completo abaixo.

SHA-256 anterior: `arquivo novo`.

SHA-256 proposto (UTF-8/LF): `925bb6d5ddc3205b9458f211b7fd3ddb1946c2ddb762248b31b391b3af673c6d`.

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
        self.assertEqual(self.consulta(texto, [diferente])['resultado'], 'ausente')

    def test_completa_so_campo_faltante_de_um_registro_compativel(self):
        r = self.consulta('Full name: Ana Paula Silva\nPara quem é: Para mim', [ROW])
        self.assertEqual(valor(r['coleta'], 'email'), 'ana@example.com')
        self.assertEqual(r['coleta']['campos']['nome']['fonte'], 'mensagem')
        self.assertEqual(r['coleta']['campos']['email']['fonte'], 'dashboard')

    def test_email_conflitante_pode_ser_resolvido_por_terceiro_email(self):
        r = self.consulta(FORM + '\nEmail: outro@example.com', [dict(ROW, Email='terceiro@example.com')])
        self.assertEqual(valor(r['coleta'], 'email'), 'terceiro@example.com')

    def test_incompativel_nao_e_aproveitado_nem_vinculado(self):
        r = self.consulta('Full name: Ana Paula Silva\nEmail: novo@example.com', [ROW])
        self.assertIsNone(r['referencia'])
        self.assertIsNone(valor(r['coleta'], 'destinatario'))

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

## Passo 29 — `tests/integration/test_coleta_abertura_postgres.py`

Ação: **criar**. Conteúdo completo abaixo.

SHA-256 anterior: `arquivo novo`.

SHA-256 proposto (UTF-8/LF): `98641bc921ab727ada840857fd9001053fa57b04a857a7d36c40e3b619b9429d`.

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

    def inicio(self, texto=FORM, fireads=True):
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
        externo.consultar.return_value = {'headers': list(ROW), 'rows': []}

        def enviar(*args, **kwargs):
            with psycopg.connect(legado.DSN) as verificador:
                alvo = verificador.execute("SELECT snapshot->'destino' FROM chatbot.envios_dash WHERE id_envio_dash=%s", (envio['id'],)).fetchone()[0]
                self.assertEqual(alvo, {'tipo': 'create'})
            return {'success': True, 'inserted': 1, 'aba': ABA_DESTINO}

        externo.enviar.side_effect = enviar
        with patch('workers.worker_funil.fireads.ClienteFireAds', return_value=externo):
            self.assertTrue(processar(envio, self.conn, self.cursor))
        self.assertEqual(externo.enviar.call_args.kwargs['dados']['Canal'], 'Meta Ads')
        self.assertEqual(self.conn.execute('SELECT status FROM chatbot.envios_dash').fetchone()[0], 'sent')


if __name__ == '__main__':
    unittest.main()
```

## Passo 30 — `REGRAS_DE_NEGOCIO.md`

Ação: **alterar**. Conteúdo completo abaixo.

SHA-256 anterior: `757407da95561bfb9e0b9d127099221e2c72df9b704a98b5fe601b59bafc6534`.

SHA-256 proposto (UTF-8/LF): `b2240fea5653a13e70a058ee49dde7bd100d4c57d85b448ddc57d94f42c51893`.

````markdown
# Regras de negócio do Chatbot - V1

## Finalidade

Este documento é a fonte de verdade para interpretar o comportamento do sistema.
Antes de classificar algo como bug ou alterar o worker, webhook, fila, histórico,
conversa, cache ou banco de dados, estas regras devem ser consultadas.

Uma proteção que aparentemente descarta, bloqueia ou repete um processamento pode
ser uma decisão deliberada da V1. Alterar uma dessas regras representa uma mudança
de produto, e não apenas uma refatoração técnica.

## Definições

- **Cliente:** identificado por `wa_id` ou `cliente_telefone`.
- **Unidade:** identificada por `phone_number_id` ou `id_phone_unidade`.
- **Turno:** interação do par `(cliente_telefone, id_phone_unidade)` que aguarda
  uma resposta do bot.
- **Mensagem aceita:** mensagem que passou pelas validações do webhook e foi
  persistida em `chatbot.fila_mensagens`.
- **Mensagem respondida:** mensagem da fila que possui histórico do bot com
  `status_envio = 'sent'`, vinculado ao seu `id_mensagem_fila` e ao hash da
  mensagem original do cliente.
- **Fonte de verdade:** dado persistido no PostgreSQL. O Redis acelera consultas,
  mas não substitui o banco de dados como fonte definitiva.

## 1. Um turno por vez

Para cada par `(cliente_telefone, id_phone_unidade)`, a V1 deve manter no máximo
uma mensagem aberta ainda sem resposta própria do bot. A decisão não depende
somente de `fila_mensagens.status`; ela combina filas abertas com a resposta do
bot especificamente vinculada a cada mensagem.

- A prioridade é determinada exclusivamente pela ordem de chegada, e não pelo
  tamanho, conteúdo ou aparente importância da mensagem.
- A primeira mensagem válida será persistida na fila.
- Enquanto essa primeira mensagem estiver `pending` ou `processing` e ainda não
  possuir sua própria resposta persistida do bot, qualquer mensagem posterior do
  mesmo cliente para a mesma unidade será descartada pelo webhook.
- A mensagem descartada não será inserida na fila nem no histórico. Para o banco,
  ela nunca existiu.
- Quando todas as filas `pending` ou `processing` já possuírem sua própria
  resposta do bot, o webhook poderá aceitar a primeira mensagem do próximo turno,
  mesmo que a limpeza da fila anterior ainda não tenha chegado ao commit de
  `fila_mensagens.status = 'sent'`.
- A decisão é serializada por `pg_advisory_xact_lock`, utilizando unidade e
  cliente como chaves.

Exemplo de comportamento esperado:

```text
cliente: oi
cliente: olá, quero solicitar determinada coisa
```

Nesse exemplo, `oi` chegou primeiro e é a única mensagem válida do turno. O bot
deverá responder somente a `oi`. A mensagem `olá, quero solicitar determinada
coisa` será descartada no webhook e não aparecerá na fila nem no histórico.

O objetivo não é escolher a mensagem mais completa ou mais útil. O objetivo é
garantir uma única entrada por turno e impedir que várias mensagens enviadas
antes da resposta do bot sejam interpretadas como etapas independentes.

### 1.1. Por que `fila_mensagens.status = 'sent'` não é a única fonte da decisão

`sent` continua sendo o estado terminal que confirma a conclusão administrativa
da fila. Porém, ele não é a única prova de que o turno funcional foi respondido.
A prova mais importante para recuperação é o histórico do bot vinculado à
mensagem específica por:

```text
id_conversa
id_mensagem_fila
id_hash_cliente_origem
```

Se a Meta confirmou o envio, o histórico do bot foi persistido e
`last_message_from` foi atualizado para `bot`, o cliente já recebeu a resposta.
O worker ainda pode cair antes do commit separado que altera a fila para `sent`.
Utilizar somente o status da fila faria o webhook descartar a resposta seguinte
do cliente durante essa janela, embora ela já pertença legitimamente ao próximo
turno.

O webhook atual usa o histórico específico do bot como prova de resposta. Ele não
libera uma mensagem apenas porque o `last_message_from` geral da conversa está
como `bot`; cada fila aberta precisa possuir sua própria resposta correspondente.

### 1.2. Recuperação detalhada entre resposta do bot e `sent`

#### Etapa 1 - A foi respondida, mas o worker caiu

```text
Fila A: processing
Histórico do cliente A: existe
Histórico do bot A: existe
last_message_from: bot
Lock da conversa: ocupado
```

O worker cai antes de marcar A como `sent`. A resposta já chegou ao WhatsApp do
cliente, mas A permanece `processing` por aproximadamente 2 minutos.

#### Etapa 2 - o cliente envia B

O webhook encontra A aberta, mas também encontra a resposta do bot vinculada
especificamente a A. B é a primeira mensagem do próximo turno e pode entrar:

```text
Fila A: processing, respondida
Fila B: pending, sem resposta
```

#### Etapa 3 - outro ciclo seleciona B

Antes de resolver a conversa ou tentar seu lock, o worker procura uma mensagem
anterior ainda aberta para o mesmo cliente e unidade. Como A continua
`processing`, B é devolvida para `pending` por 30 segundos. Essa espera não
consome tentativa de erro.

```text
Fila A: processing, respondida
Fila B: pending, sem resposta
```

#### Etapa 4 - o cliente envia C

O webhook examina individualmente todas as filas abertas:

| Fila | Status | Resposta própria do bot |
|---|---|---|
| A | `processing` | Sim |
| B | `pending` | Não |

Como B ainda não possui resposta própria:

```text
todas_abertas_respondidas = False
```

C é descartada e nunca entra no banco. O `last_message_from = 'bot'` deixado por
A não libera C, porque não existe histórico do bot vinculado especificamente a B.

#### Etapa 5 - B aguarda a recuperação de A

Enquanto A continuar aberta, cada claim de B repetirá a verificação de ordem e a
devolverá para `pending` por 30 segundos, sem tentar o lock da conversa:

```text
Fila A: processing, respondida
Fila B: pending, sem resposta
```

C e quaisquer mensagens posteriores continuarão bloqueadas por B.

#### Etapa 6 - A retorna após o timeout

Depois de aproximadamente 2 minutos:

1. A fica elegível novamente;
2. o lock antigo já expirou após 110 segundos;
3. outro worker adquire o lock;
4. encontra o histórico do bot vinculado a A;
5. não envia uma resposta duplicada;
6. marca A como `sent`;
7. libera o lock.

```text
Fila A: sent
Fila B: pending
```

#### Etapa 7 - B é processada

B já não encontra mensagem anterior aberta, resolve a conversa, adquire o lock e
segue normalmente. Se esse lock for recusado por outro motivo, B volta para
`pending` por 5 segundos, também sem consumir uma tentativa de erro.
Enquanto B não possuir sua própria resposta do bot, qualquer C será descartada.

Depois que a resposta de B for persistida, a primeira mensagem do próximo turno
poderá entrar, inclusive na pequena janela anterior ao commit de `sent` de B.

### 1.3. Limite prático de mensagens abertas

Na recuperação descrita, o sistema poderá manter temporariamente:

```text
1 mensagem antiga respondida, mas ainda processing
+
1 mensagem nova sem resposta
```

Isso não cria uma sequência ilimitada. Assim que B entra sem resposta própria,
C, D, E e todas as mensagens seguintes são descartadas pelo webhook. O advisory
lock do turno também impede que B e C sejam aceitas simultaneamente por uma
corrida entre requisições.

Implementação principal:

- `core/repositories/seguranca/turno_cliente.py`
- `callback/webhook/services/populating_fila_mensagens.py`

## 2. Idempotência na entrada do webhook

- `fila_mensagens.id_hash_msg` é único.
- A repetição do mesmo evento pela Meta não deve criar outra linha na fila.
- `ON CONFLICT DO NOTHING` é o comportamento esperado para o mesmo
  `id_hash_msg`.
- Uma mensagem nova possui outro hash e continua sujeita à regra de turno.

Ignorar um webhook duplicado não é bug.

## 3. Primeira mensagem do turno

A primeira mensagem válida deverá ser persistida na fila quando não existir outra
mensagem aberta sem resposta para o mesmo cliente e unidade.

É considerado bug quando a primeira mensagem, ou a única mensagem enviada no
turno, é ignorada sem que alguma regra explícita deste documento seja aplicável.

## 4. Estados e tentativas da fila

Estados utilizados:

- `pending`: aguardando processamento.
- `processing`: reservada por um worker.
- `sent`: processamento e resposta concluídos.
- `failed`: permitido pelo schema, mas não é o destino utilizado atualmente
  quando o limite de tentativas é atingido.

Regras da V1:

- O dequeue altera a mensagem para `processing` e incrementa `retry_count`.
- Uma mensagem `processing` abandonada poderá ser retomada depois de 2 minutos.
- Erros tratados reagendam a mensagem para 2 minutos depois, enquanto ainda
  houver tentativa disponível.
- O limite é de 3 tentativas de processamento.
- Ao identificar `retry_count >= 3`, a mensagem é excluída.
- Não existe uma quarta tentativa.

A exclusão ao atingir o limite de 3 tentativas é uma regra de negócio confirmada
da V1, e não um bug. Alterar esse comportamento para `failed`, dead-letter ou um
número maior de tentativas exige uma nova decisão de produto.

Implementação principal:

- `core/database/deploy_database/bank_script.py`, função `chatbot.dequeue_message()`
- `workers/tratamento_erros_externos/expection_process.py`
- `core/repositories/atendimento/fila.py`

## 5. Ordenação e exclusão mútua

- Uma conversa deve ser processada por apenas um worker por vez.
- O lock da conversa poderá ser retomado se estiver abandonado por mais de 110
  segundos.
- `lock_version` impede que um worker antigo libere o lock adquirido por um
  worker mais novo.
- Uma mensagem não poderá ultrapassar outra mensagem anterior ainda aberta na
  mesma conversa.
- A ordem utiliza `received_data_hora` e, em caso de empate, `id_mensagem`.
- Uma mensagem posterior que encontrar outra anterior aberta será reagendada sem
  consumir uma tentativa de erro.

Implementação principal:

- `core/database/deploy_database/bank_script.py`, funções `lock_conversa()` e
  `unlock_conversa()`
- `core/repositories/atendimento/conversas.py`
- `core/repositories/atendimento/fila.py`
- `workers/worker_flow/transacoes/lock_conversa.py`
- `workers/worker_flow/transacoes/ordem_turno.py`

## 6. Conversa ativa e bloqueio por 30 dias

- Poderá existir somente uma conversa ativa para o mesmo cliente e unidade.
- Essa garantia é protegida pelo índice parcial `idx_conversa_unica_ativa`.
- Uma conversa finalizada em etapa com `bloqueio_dias > 0` permanecerá
  bloqueada pelo prazo declarado na política.
- A etapa 2 registra a escolha inicial entre titular e dependente. A etapa 3
  aceita exclusivamente `Sim` ou `Não`, por clique nos botões ou pelo mesmo
  texto digitado. `Sim` mantém a escolha; `Não` seleciona o polo oposto.
  Os dois resultados seguem obrigatoriamente para a etapa 4. Mídia, dúvida
  sobre reforço escolar, pergunta financeira inequívoca ou qualquer outro
  conteúdo repetem a confirmação.
- A etapa 4 sempre coleta, em texto livre, a profissão. Somente depois de
  persistir esse dado ela consulta o `status_dependente` final: dependente
  segue para a etapa 5, que pergunta o nome; titular segue para a etapa 6,
  que pergunta a idade. Assim, nenhum fluxo novo pula a profissão.
- A profissão válida da etapa 4 é salva, na mesma transação, em dois níveis:
  `conversa.profissao` preserva o snapshot daquele atendimento e
  `cliente.profissao` é substituída pelo valor válido mais recente informado
  pelo cliente. Uma conversa posterior nunca reescreve a profissão das
  conversas anteriores.
- Antes dessa persistência, o validador rejeita como
  `profissao_fora_contexto` somente as oito respostas completas já observadas:
  `Pra minha filha na verdade`, `Não entendi`, `Para meu filho`,
  `Pra meu filho`, `Minha filha é autista e percebo q ela tem dificuldade no
  aprendizado , vcs atende autista tambem`, `não seria pra meu filho`,
  `Meu filho` e `Vc ouviu áudio ou ligação`. A comparação ocorre sobre a frase
  inteira normalizada, nunca pela presença isolada de palavras como `áudio`,
  `ligação`, `filho`, `filha` ou `autista`. Quando houver correspondência, a
  etapa 4 apenas reapresenta a pergunta, sem evento, avanço ou persistência e
  sem criar uma etapa de confirmação adicional.
- A etapa 11 introduz a triagem, as etapas 12 a 17 fazem as seis perguntas e a
  etapa 20 apresenta o agendamento quando há link; sem link, a 18 coleta o turno e a 19 entrega ao comercial. A 20 com link ou a 19 sem link torna a conversa elegível ao
  Funil, mas não encerra nem bloqueia o atendimento.
- Na etapa 11, o clique em `Começar triagem` e confirmações textuais inequívocas
  disparam o mesmo evento `triagem_iniciada`. A validação aceita variações de
  começar, iniciar e prosseguir, enquanto negativas e respostas ambíguas mantêm
  a conversa na etapa 11.
- As etapas 12 a 17 não mudam de ID nem de transição conforme a idade. Elas
  selecionam somente o texto da pergunta: titular usa sempre a versão adulta;
  dependente com menos de 18 anos usa a versão infantil; dependente com 18 anos
  ou mais usa a versão adulta com o nome persistido. O limite de entrada de 4
  anos em unidade com BPA e de 5 anos sem BPA continua pertencendo à validação
  de idade anterior à triagem.
- Cada unidade possui `idade_minima_suporte` (NULL/50/60/70/80, padrão NULL)
  e `email_obrigatorio` (padrão TRUE). A migração da política anterior conserva
  TRUE como 60 e FALSE como NULL; novas unidades começam sem suporte ativado.
- Na etapa 6, mídia, reforço escolar e financeiro precedem a validação de idade.
  A universal 90+ tem prioridade e vale para titular e dependente, inclusive com
  suporte desativado. Envia contato com mensagem pronta e encerra com
  `idade_universal_90`. Titulares abaixo de 90 e a partir do suporte configurado
  encerram com `suporte_idoso_50/60/70/80`; a idade desse suporte é persistida.
  Menores de 18 encerram com `titular_menor_18`. Dependentes abaixo do mínimo
  encerram com `dependente_menor_4` (BPA) ou `dependente_menor_5` (sem BPA).
  Menores não recebem contato comercial. Nenhum desses casos gera Funil ou
  bloqueio de 30 dias. Os nomes internos `idade_acima_99` permanecem compatíveis,
  mas não representam o corte dos novos atendimentos.
- Para todas as faixas configuráveis (50/60/70/80), o encaminhamento usa
  a mesma mensagem de atendimento personalizado, sem anunciar o limite, e o
  botão `Falar agora`.
- Todo botão para o comercial leva uma mensagem pronta, inclusive o universal 90+.
  O texto identifica o chatbot pelo nome e artigo conforme seu gênero, a unidade
  e o cliente que está conversando. Na rota de titular, inclui sua idade e o
  desejo de reservar sua experiência Supera. Na rota de dependente,
  identifica também o nome e a idade do dependente e pede a experiência para ele.
  A idade é a informada na resposta atual da etapa 6, nunca uma idade antiga
  nem a idade do dependente atribuída ao titular. A origem vem da unidade
  vinculada à conversa; não inventar informações ausentes.
  O cliente confirma o envio no WhatsApp; abrir o botão não envia esse texto.
- O proprietário configura o limite no Admin. Toda unidade exige número comercial
  brasileiro válido, mesmo com suporte desativado. A migração normaliza 90 para
  NULL e invalida o cache; nunca converte 90 para 80.
- Retry exige a resposta conhecida vinculada à mesma conversa, fila e hash da
  entrada. A idade vem da mensagem vinculada, nunca de `cliente.idade`;
  `validar_idade` extrai o inteiro inclusive de números acompanhados de texto
  ou escritos por extenso. Para
  suporte comprovado entre 50 e 89, usa o limite atual se ele ainda inclui a idade;
  caso contrário, usa o maior entre 50/60/70/80 que não exceda a idade, inclusive
  se o suporte foi desativado. Registra a reconstrução compatível em log, sem
  afirmar que descobriu a faixa histórica exata. Suporte legado 90–99 fica genérico.
  O mínimo BPA é recuperado do texto efetivamente enviado. Uma oferta já enviada
  não vira encerramento por mudança de regra. Universal 100+ em retry sem motivo
  confirmado conserva o legado quando o corpo não distingue a versão. Encerramento
  e fila sent continuam atômicos; o risco Meta-before-DB permanece aceito.
  Uma resposta universal comprovada para titular de 91 ou dependente de 92
  mantém `idade_universal_90` se o suporte mudar de desativado para 80+ antes
  do retry. Universal tem prioridade para ambos; adicionalmente, dependentes
  não participam do suporte configurável. A reconstrução não recalcula motivos
  de conversas concluídas e não é usada para decidir novas conversas.
- Na etapa 10, mídia, reforço escolar e financeiro continuam precedendo a
  coleta de e-mail. A exigência efetiva é a configuração da unidade, exceto
  para o titular de 60 a 99 anos, cujo e-mail é universalmente opcional quando
  o atendimento não tiver sido encerrado pelo suporte ao idoso. Dependentes
  seguem exclusivamente a configuração da unidade.
- Quando o e-mail é obrigatório, somente um endereço estruturalmente válido
  avança. Quando é opcional, um endereço válido é salvo; ausência declarada ou
  qualquer outra resposta comum aceita limpa `cliente.email` para `NULL` e
  avança sem tratamento de e-mail. A classificação da resposta permanece
  vinculada à conversa para que o Funil exiba `não tem` ou `não informado` sem
  inventar um endereço.
- A etapa 21 registra uma nota de satisfação de 1 a 5. Na etapa 22, o cliente
  escolhe se deseja comentar: a aceitação segue para a etapa 23 e a recusa
  salta diretamente para a etapa 24. A etapa 23 coleta o comentário livre e
  avança para 24 sem julgar seu conteúdo: `ok`, `sim`, emojis e pontuação também
  são aceitos. Não há tratamento de contexto inválido nessa etapa. Uma recusa
  explícita ou resposta sem texto encerra sem comentário (`NULL`); botões antigos
  não são gravados como comentário. Mídias mantêm a orientação para escrever
  por texto, sem avançar. A recuperação usa o mesmo critério de persistência. Nota e
  comentário são internos, não compõem o payload do Funil e não encerram nem
  bloqueiam o atendimento.
- A etapa 24 encerra a conversa, registra `foi_agendado` e aplica o bloqueio de
  30 dias. A despedida usa `te receber` para titular e `receber você e
  {nome_dependente}` para dependente, tanto no caminho 22 -> 24 quanto 23 -> 24.
  O nome vem do dependente vinculado à conversa e à unidade; nunca substituir
  silenciosamente a rota de dependente pela de titular quando faltar esse dado.
- Durante esse período, novas mensagens para a mesma unidade não iniciarão outro
  atendimento.
- Depois dos 30 dias, o cliente poderá iniciar uma nova conversa com a mesma
  unidade.

Implementação principal:

- `core/database/deploy_database/bank_script.py`
- `core/repositories/atendimento/conversas.py`
- `core/repositories/fluxo/politicas.py`
- `workers/worker_flow/valida_banco.py`
- `core/cache/runtime/cache_conversas_bloqueadas.py`

### 6.1 Oportunidade no Funil de Vendas

- Com link, uma conversa torna-se elegível ao entrar na etapa 20. Sem link, na etapa 19.
- Com link, as etapas 20 a 24 permanecem elegíveis; sem link, 19 e 21 a 24. Assim, avançar na pesquisa antes do
  próximo ciclo do worker não remove a conversa da fila do Funil.
- `lead_no_funil = TRUE` é a confirmação que impede um segundo envio da mesma
  conversa; nota e comentário da pesquisa não fazem parte do snapshot enviado.
- O worker cria uma oportunidade por vez na coluna `Leads` do CRM.
- O snapshot exige nome, telefone, idade da pessoa atendida e as seis respostas
  canônicas da triagem. O e-mail pode estar ausente quando a política efetiva
  da conversa o tornou opcional; nesse caso, o contato é enviado sem endereço
  e as observações exibem `não tem` ou `não informado`, conforme a resposta.
- O resultado de e-mail pertence à conversa que chegou ao Funil. Ele é
  reconstruído pela mensagem do cliente na etapa 10 vinculada à resposta do
  bot na etapa 11; uma conversa posterior não pode alterar esse snapshot por
  meio do valor global de `cliente.email`.
- A profissão da conversa é exibida nas observações; o Funil não usa
  `cliente.profissao`, pois ela pode ter sido atualizada por outro atendimento.
  Conversas legadas podem apresentar a profissão como não informada.
- As observações apresentam as seis perguntas e suas respostas na ordem das
  etapas 12 a 17. O Funil usa o mesmo catálogo de perguntas do WhatsApp e não
  envia mais o resumo por quantidade de `Nunca`, `Às vezes` e
  `Frequentemente`.
- Em atendimento para dependente, a oportunidade mantém o cliente pagante como
  contato e inclui nome e idade do dependente nas observações.
- A resposta só é confirmada quando o HTTP não falha e o JSON contém
  `response = success`.
- Falha antes da confirmação externa devolve `funil_envios` para `pending` e
  não altera `lead_no_funil`.
- `funil_envios` usa claim com `FOR UPDATE SKIP LOCKED` e lease para recuperar
  itens abandonados em `processing`.
- O título segue `Chatbot Lead <nome_unidade>`. A conversa é identificada pelos
  dados do snapshot e pelo estado local de `funil_envios`; o CRM não recebe o ID
  interno da conversa no título.
- A V1 não cria atividade e não sincroniza atualizações posteriores do CRM.

O processo é desativado por padrão e só inicia com
`FUNIL_WORKER_ENABLED=True` depois do teste manual da unidade.

## 7. Histórico da mensagem do cliente

Depois que uma mensagem da fila for aceita pelo worker:

- Ela será registrada no histórico como `quem_enviou = 'cliente'`.
- Sua identificação lógica utilizará conversa, `id_mensagem_fila` e
  `id_hash_msg`.
- Durante um retry, o registro existente deverá ser reutilizado.
- A etapa persistida no histórico deverá ser reutilizada; o retry não poderá
  reinterpretar a mensagem em outra etapa.
- `last_message_from` deverá permanecer como `cliente` enquanto não existir uma
  resposta do bot persistida para aquela mensagem.
- `last_interaction_at` deverá utilizar o horário persistido da mensagem, e não o
  horário em que o retry ocorreu.

### Respostas da triagem cognitiva

- A triagem mantém exatamente seis perguntas nas etapas 12 a 17.
- A idade e o destino do atendimento são relidos do banco em cada ciclo. Isso
  preserva a mesma variante no retry e impede escolher silenciosamente uma
  pergunta quando idade, nome do dependente ou destino estiverem inconsistentes.
- A versão infantil sempre usa o nome do dependente. A versão adulta usa
  `você` para o titular e o nome para um dependente adulto.
- Cada pergunta aceita somente `Nunca`, `Às vezes` ou `Frequentemente`.
- Botão e texto digitado percorrem a mesma validação exata.
- Qualquer outro conteúdo recebe o tratamento de contexto e mantém a conversa
  na pergunta atual.
- A resposta canônica é registrada em `chatbot.respostas_desafios` com a
  conversa, a etapa da pergunta e o histórico da mensagem do cliente.
- A restrição única por conversa e etapa torna a gravação idempotente.
- Em retry, a resposta pode ser reconstruída pela mensagem original.

## 8. Histórico e idempotência da resposta do bot

A resposta do bot a uma mensagem enfileirada é vinculada à entrada original por:

- `id_conversa`;
- `id_mensagem_fila`;
- `id_hash_cliente_origem`.

O lembrete proativo não responde a uma entrada enfileirada: deixa os dois campos
de origem nulos e usa recibo próprio por conversa e âncora do ciclo. Ele não
serve como prova de resposta para liberar um turno A/B/C.

Se `resposta_bot_para_mensagem_atual` já existir:

- a Meta não deverá ser chamada novamente;
- o histórico do bot não deverá ser duplicado;
- o contexto da conversa deverá ser reparado a partir dos dados persistidos;
- no retry normal, `last_message_from` deverá terminar como `bot`;
- a fila poderá seguir para `sent`.

O replay de uma retomada de follow-up já concluída reutiliza a resposta persistida
sem alterar a interação atual ou zerar um ciclo posterior. Essa recuperação fica
em `workers/worker_flow/transacoes/retorno_followup.py`.

As proteções `if resposta_bot_atual`, presentes nos fluxos normais e de
tratamento, são regras essenciais de idempotência da V1.

Implementação principal:

- `workers/worker_flow/valida_historico.py`
- `workers/worker_flow/response_flow/flow_sender.py`
- `workers/worker_flow/response_flow/etapas/`
- `workers/worker_flow/transacoes/persistencia_resposta.py`

## 9. Semântica de `last_message_from`

- Mensagem do cliente persistida e ainda sem resposta: `cliente`.
- Resposta do bot persistida: `bot`.
- Retry sem resposta do bot mantém ou repara o campo para `cliente`.
- Retry com resposta do bot existente mantém ou repara o campo para `bot`.
- O campo representa o último lado com mensagem persistida para o estado atual;
  ele não é apenas uma marcação de que a conversa já foi iniciada.

Recuperar uma retomada de follow-up já concluída não sobrescreve o estado de
uma interação posterior. A confirmação do lembrete proativo também registra
o bot como último lado, junto do histórico e do recibo de envio.

## 10. Etapas da conversa

- `chatbot.etapa` representa os estados existentes da conversa.
- `chatbot.etapa_transicao` representa as arestas permitidas entre esses
  estados.
- Uma resposta válida produz um evento e somente poderá seguir para o destino
  cadastrado para a combinação `origem + evento`.
- Uma etapa poderá possuir mais de um destino, desde que cada evento identifique
  uma única transição.
- Avanços, saltos e o retorno controlado `9 + retorno_adiado -> 8` são permitidos
  somente quando existe uma aresta explícita.
- Um exemplo de salto autorizado é
  `22 + comentario_satisfacao_recusado -> 24`.
- A atualização utilizará a origem persistida no histórico da mensagem e será
  revalidada no `UPDATE` da conversa.
- Um retry com resposta do bot existente reutilizará a etapa do histórico do
  bot e reconstruirá o evento pela origem e pelo destino.
- Tratamentos que apenas orientam o cliente poderão responder sem avançar a
  etapa e não produzirão evento de transição.

Qualquer transição sem aresta cadastrada é bug. A ordem numérica dos IDs serve
para organização e não define navegação.

## 11. Tipos de mensagem na V1

- `text` e `interactive` são tipos suportados pelo fluxo normal de validação.
- Mídias e anexos não são respostas suportadas pelo fluxo normal da V1.
- Uma mídia recebida deverá ser registrada no histórico.
- O bot enviará uma orientação para o cliente continuar por texto.
- Essa orientação não avançará a etapa, mas alterará `last_message_from` para
  `bot` depois de ser persistida.
- Texto com intenção de preço, custo, mensalidade ou investimento recebe
  tratamento próprio e não deve ser interpretado como resposta comum da etapa.
- Depois que a etapa 1 já foi apresentada, respostas de nome com números,
  caracteres inválidos, repetição artificial ou termos pejorativos recebem
  tratamento de contexto e não avançam a conversa.

Desconsiderar o conteúdo da mídia para fins de avanço de etapa não é bug.

### 11.1. Conversa iniciada por texto

Quando a conversa ainda não possui etapa atual persistida, qualquer mensagem de
texto comum poderá iniciar o atendimento e receber a saudação normal da etapa 1.

Essa regra vale mesmo que o texto inicial seja estranho, curto, tenha símbolos ou
pareça fora de contexto. Nessa primeira interação, o objetivo é apresentar o
agente virtual configurado para a unidade e pedir o nome do cliente.

Mídia, reforço escolar e intenção financeira conservam seus tratamentos e sua
prioridade, nessa ordem. Depois deles, o primeiro texto que perguntar o que é
o Supera ou pedir informações gerais recebe a apresentação explicativa aprovada,
com a comparação a uma academia para o cérebro e o pedido do nome. As demais
entradas recebem a abertura padrão.

A identificação aceita frases completas com ou sem saudação, nome do Supera,
acentos e interrogação, como `Do que se trata?`, `O que é?` e `Olá! Posso ter
mais informações sobre isso?`. Não basta uma palavra solta. Esse caminho só
existe antes da etapa 1 estar apresentada; depois disso, o nome continua sendo
validado normalmente. Ambas as aberturas inicializam a etapa 1, sem consumir
o primeiro texto como nome, e convergem para a mesma etapa 2 após um nome válido.
Não há novo evento de transição, flag no banco ou mudança de follow-up/retry.

Nas mensagens iniciais padrão, explicativa, de mídia, de intenção financeira
e de tratamento de reforço escolar, a apresentação é formada exclusivamente pelos dados
persistidos em `chatbot.unidade`:

- `nome_unidade`: nome público da unidade;
- `nome_agente`: nome público do agente virtual;
- `genero`: seleciona `Sou o {nome_agente}` para `masculino` e
  `Sou a {nome_agente}` para `feminino`.

Esses campos não alteram evento, transição, turno, retry ou transação. Eles são
apenas dados de apresentação lidos pelo contexto da etapa 1. As demais mensagens
mantêm seus textos próprios.

### Linguagem da experiência Supera e sua reserva

A composição das falas, a personalidade acolhedora e a organização dos
arquivos seguem o [contrato editorial de messages](core/integrations/whatsapp/messages/README.md).
Ele deve ser consultado em revisões de textos, tratamentos e retomadas,
preservando as regras operacionais deste documento.

Cada etapa separa sua mensagem padrão da repetição pura. Financeiro, mídia
e reforço escolar vêm de módulos próprios e são compostos antes dessa repetição.
Contexto inválido usa uma mensagem própria, que já orienta o cliente a responder
corretamente, sem concatenar a mensagem de repetição. Preserva os botões/opções
e rodapés nativos, assim como titular/dependente. A regra também vale na triagem
e na pesquisa. Pode receber o prefixo de inatividade de três horas quando elegível;
não recebe outro tratamento ou prefixo de follow-up nesse mesmo ciclo.
Inatividade de três horas mantém a validação normal (podendo avançar ou tratar);
a reação ao follow-up acolhe e valida a resposta. Quando não há resposta válida
nem tratamento específico, reapresenta a pergunta neutra. A etapa 8 continua
avançando diretamente para a 9. O retorno não soma saudações; quando repete a
etapa, usa sua pergunta neutra sem repetir apresentação ou despedida.

A oferta inicial da etapa 7 destaca **demonstração prática por cortesia da unidade** logo na
abertura, antes da explicação da avaliação de habilidades, e termina com o
convite para reservar uma **experiência Supera exclusiva**. A saudação
`Maravilha, {nome_titular}! ☺️` se dirige a quem conversa nas duas rotas;
quando há dependente, a demonstração, a avaliação e a reserva mencionam
`nome_dependente` como participante. Gratuidade da experiência
não significa curso ou matrícula gratuitos. Não há nome/gênero de diretor ou
novas colunas para essa oferta.

Concentrar **por cortesia da unidade** na apresentação inicial da oferta
(etapa 7) e nos lembretes proativos. O objetivo é reduzir a repetição, não impor
um limite técnico: a oferta e um ou dois lembretes somam duas ou três menções.
Retomadas, escolha de turno, envio do link, mensagens ao comercial e perguntas
repetidas usam apenas experiência ou momento Supera, sem esse complemento.
No tratamento financeiro, manter uma menção na orientação que esclarece a
cortesia; a pergunta seguinte não a repete. Essa dúvida pode acrescentar uma
menção ao atendimento. Outros tratamentos não repetem a expressão.
Não reintroduzir `gratuita` ou `gratuito` nos textos enviados ao cliente.

Cada lembrete pode mencionar a cortesia. A despedida do segundo follow-up
consecutivo não usa a expressão. Se houver mais pausas com retomada, poderão
ocorrer mais menções. A redução é apenas editorial, sem contador, consulta
adicional ao banco, coluna ou migração nova.
Preservar a alternância entre experiência e momento Supera.
Respostas do cliente com a redação anterior continuam
aceitas, e as classificações de gratuidade da Meta no painel de consumo mantêm
seu significado próprio.

O atendimento deve ser acolhedor e convidativo, com frases naturais, emojis
discretos e negrito moderado. A oferta usa **presentear**, e a comemoração
**Maravilha, {nome_titular}! ☺️** pertence à apresentação normal: não aparece após avisos de
mídia, dúvidas ou respostas não compreendidas. Nesses casos, o bot acolhe a
mensagem e orienta como continuar, sem atribuir o erro ao cliente.

Na etapa 1, a apresentação não presume quem participará da experiência.
Na oferta e na apresentação do link de reserva, o dependente é mencionado
pelo nome quando for o participante, inclusive na repetição por follow-up.
Esses ajustes de linguagem não alteram validação, transição ou elegibilidade.

Uma negativa sem alternativa na etapa 2 repete a pergunta, sem escolher
um destino. Correções explícitas com vírgula e destinos alternativos
completos continuam aceitos. A confirmação da etapa 3 é preservada.

Perguntas sobre a gratuidade da demonstração ou experiência recebem o
tratamento financeiro, sem avanço. Perguntas curtas como `É gratuita?`
podem retomar a oferta nas etapas de convite e reserva. Menções a algo
gratuito fora desse contexto não recebem uma classificação nova genérica.

As saudações de retorno não se acumulam na etapa 9. O sender devolve
ao histórico o mesmo texto enviado; retries preservam respostas anteriores.

Nas etapas 7 e 9, o botão **Quero reservar** e confirmações digitadas como
**quero**, **sim** e **quero agendar** continuam aceitos. Por decisão de
negócio, o aceite flexível não foi endurecido: expressões como `quero pensar melhor`
continuam seguindo o reconhecimento existente. Negativas reconhecidas e pedidos
informativos, como **quero saber como reservar**, não confirmam a oferta.
**Talvez mais tarde** mantém o evento de adiamento. A etapa 20 apresenta
**Já reservei** e aceita também as confirmações antigas de conclusão, como
**já agendei**. Dizer **quero reservar** nessa etapa não comprova conclusão.
Os nomes técnicos de eventos e colunas permanecem, incluindo `link_agendamento`
e `agendamento_confirmado`; idade, e-mail, follow-up e fronteiras transacionais
conservam suas regras.

### 11.2. Exceção para conversa iniciada com mídia

Quando a primeira mensagem de uma conversa for uma mídia, ainda não existirá
uma etapa atual persistida. Nesse caso:

1. o bot enviará saudação da etapa 1 junto com o aviso de mídia não suportada;
2. a mensagem solicitará o nome do cliente por texto;
3. o tratamento registrará a etapa 1 como apresentada;
4. a próxima interação válida será interpretada como resposta da etapa 1 e
   poderá direcionar o fluxo para a etapa 2.

Mensagem esperada, usando uma das duas primeiras linhas conforme o gênero do
agente:

```text
Masculino: Bom dia/Boa tarde/Boa noite! Sou o {nome_agente}, assistente do {nome_unidade}! ☺️
Feminino:  Bom dia/Boa tarde/Boa noite! Sou a {nome_agente}, assistente do {nome_unidade}! ☺️
Hoje vou te ajudar a dar os primeiros passos para conhecer o Supera! 🧡

Olha não reconhecemos ainda mensagem com mídia, apenas texto.
Me diz, qual o seu primeiro nome?
```

Para qualquer etapa já apresentada, a regra geral será diferente. Se a conversa
estiver na etapa N e o cliente enviar uma mídia:

1. o bot enviará o tratamento de tipo de mensagem não suportado;
2. o tratamento poderá repetir a pergunta da etapa atual quando essa
   reapresentação estiver implementada;
3. o tratamento não alterará a etapa persistida;
4. a interação seguinte por texto será interpretada como resposta da etapa N;
5. uma resposta válida produzirá o evento que aponta para o destino cadastrado;
6. a mensagem normal da etapa N não precisará ser enviada de novo em separado.

Na etapa 1 já apresentada, a resposta esperada para mídia será:

```text
Olha não reconhecemos ainda mensagem com mídia, apenas texto.
Me diz, qual o seu primeiro nome?
```

Para etapas ainda sem tratamento específico, a mensagem poderá ser mais genérica:

```text
Recebi uma mídia, mas nesta etapa eu preciso que você responda por texto ou use os botões disponíveis.

Envie uma mensagem de texto para continuarmos.
```

Em ambos os casos:

1. o tratamento não avança etapa;
2. a interação seguinte por texto será interpretada como resposta da etapa N;
3. uma resposta válida seguirá a transição cadastrada para a etapa N.

Portanto, o tratamento de mídia não avança etapa já apresentada. A exceção é
somente a conversa iniciada com mídia, porque a própria mensagem de tratamento
também apresenta a etapa 1.

### 11.3. Tratamento financeiro

Quando o cliente enviar texto perguntando sobre valor, custo, preço,
mensalidade, investimento ou termo equivalente:

1. a mensagem do cliente será registrada no histórico;
2. o bot explicará que os valores de investimento são definidos após a
   experiência Supera por cortesia da unidade, com orientação da equipe;
3. a mensagem também reapresentará a pergunta da etapa atual;
4. a conversa não avançará por causa da pergunta de valor;
5. `last_message_from` será atualizado para `bot` depois da resposta persistida.

Se a conversa iniciar com pergunta de valor, a resposta esperada usará uma das
duas primeiras linhas conforme o gênero do agente:

```text
Masculino: Bom dia/Boa tarde/Boa noite! Sou o {nome_agente}, assistente do {nome_unidade}! ☺️
Feminino:  Bom dia/Boa tarde/Boa noite! Sou a {nome_agente}, assistente do {nome_unidade}! ☺️

Hoje vou te ajudar a dar os primeiros passos para conhecer o Supera! 🧡

Olha, os valores de investimento são definidos após a *experiência Supera* por cortesia da unidade. Assim, nossa equipe poderá orientar você sobre a opção mais adequada. ☺️

Vamos lá:

Me diz, qual o seu primeiro nome?
```

Nesse caso, a etapa 1 fica registrada como apresentada, e a próxima resposta em
texto será interpretada como resposta da etapa 1.

Se a etapa 1 já tiver sido apresentada e o cliente responder perguntando sobre
valor, a mensagem esperada será:

```text
Olha, os valores de investimento são definidos após a *experiência Supera* por cortesia da unidade. Assim, nossa equipe poderá orientar você sobre a opção mais adequada. ☺️

Vamos lá:

Me diz, qual o seu primeiro nome?
```

Esse tratamento é financeiro, não tratamento de contexto. Ele possui fluxo e
sender próprios para evitar misturar dúvida comercial com resposta fora do
contexto da etapa.

O prefixo é único e a pergunta seguinte retoma a etapa sem repetir todo o
convite. O participante permanece correto, inclusive quando é um dependente.
Os textos destacam com moderação a experiência e a ação principal usando
`*negrito*` no corpo. Os títulos de botões não recebem essa marcação.

### 11.4. Tratamento de dúvida sobre reforço escolar

Nas mesmas etapas que oferecem tratamento financeiro, o sistema também deverá
identificar dúvidas que confundam o Supera com serviços escolares tradicionais,
como reforço escolar, banca, supletivo, cursinho, aula particular ou ensino de
matérias específicas.

O reconhecimento é universal e possui o seguinte contrato:

1. mídia ou tipo não suportado continua tendo prioridade sobre o texto;
2. a dúvida sobre reforço escolar tem prioridade sobre o tratamento financeiro;
3. a mensagem do cliente e a resposta do bot são registradas normalmente;
4. a resposta é marcada com `tipo_tratamento='duvida_reforco_escolar'`;
5. nenhuma transição é produzida e a conversa permanece na etapa atual;
6. a pergunta ou chamada da etapa é reapresentada de forma neutra, preservando
   botões, rodapés, links e as variantes de titular ou dependente aplicáveis.

Assim, uma pergunta como `Quanto custa o reforço escolar?` recebe este
tratamento antes do financeiro. Já uma mídia que contenha texto ou legenda
continua recebendo tratamento de mídia.

Expressões inequívocas de serviço escolar podem ser reconhecidas diretamente.
Nomes de matérias, como matemática ou português, exigem também contexto de
ensino, aula, ajuda ou procura pelo serviço. A palavra isolada não é suficiente,
pois respostas legítimas como `Sou professora de matemática` devem continuar
pertencendo à etapa que coleta a profissão.

A expressão `O investimento fica na faixa de um curso de inglês`, usada como
comparação no formulário, não representa procura por aulas nem pergunta de preço.
Os classificadores de reforço escolar e financeiro desconsideram esse trecho,
aceitando variações de caixa, acentos e espaços. No financeiro, desconsiderar
também o rótulo `Quem decide a matrícula?:` (com interrogação opcional) quando
acompanha diretamente a comparação. Preservar a resposta a esse rótulo e o
restante da mensagem: dúvidas reais sobre inglês, reforço ou preço conservam
seus tratamentos. A mensagem original continua intacta no histórico. Essa
exceção não identifica a origem do lead nem importa dados do formulário.

Na etapa 4, declarações claras de profissão ou vínculo de trabalho com banca,
cursinho, supletivo ou reforço também são respostas profissionais válidas. Por
exemplo, `Trabalho em um cursinho`, `Sou diretora de um supletivo` e
`Sou professora de matemática em uma banca` não acionam este tratamento. A
exceção é contextual e não altera o reconhecimento nas demais etapas.

Mensagem esperada:

```text
Olha, o Supera não é reforço escolar.
Nós trabalhamos a raiz da aprendizagem, desenvolvendo habilidades como atenção, concentração, memória e raciocínio — o alicerce necessário para aprender melhor em qualquer matéria. 🧠✨

Vamos lá:

(retomada neutra da etapa atual)
```

### 11.5. Tratamento de contexto para nome inválido

Depois que a etapa 1 já foi apresentada, a resposta esperada do cliente é o nome.
Se o cliente responder com texto que pareça fora do contexto de nome, como
caracteres inválidos, números, repetição artificial ou termo pejorativo, o bot
deverá tratar sem avançar a conversa.

Mensagem esperada:

```text
Olha, não consegui entender o seu nome. Digite só seu primeiro nome, por exemplo: Pedro.
```

Esse tratamento é diferente do financeiro e do tipo não suportado. Ele existe
para preservar a etapa atual e pedir novamente um nome utilizável.
O pedido já está completo nessa mensagem; não acrescentar a pergunta de repetição.

### 11.6. Coerência semântica ao reapresentar a etapa

Quando um tratamento reapresentar a pergunta da etapa atual, ele não deverá
concatenar automaticamente a mensagem padrão completa. A pergunta ou chamada
principal pode ser reutilizada, mas aberturas que pressuponham resposta válida,
confirmação, apresentação ou avanço — como `Entendi`, `Certo`, `Perfeito`,
`Maravilha` e `Prazer` — deverão ser omitidas ou substituídas por uma retomada
neutra.

**Exceção de contexto inválido:** a orientação possui redação própria e já
contém o pedido da resposta correta. Nunca concatenar a pergunta de repetição
nem a mensagem inicial. A apresentação visual e os botões/rodapés nativos
continuam pertencendo à etapa. Essa exceção muda a redação, não os critérios
dos validadores, a prioridade dos tratamentos ou os eventos de transição.

A mensagem final deverá ser lida como uma única fala semanticamente coerente.
Depois de informar que uma resposta não foi compreendida ou aceita, o bot não
deverá elogiar, confirmar entendimento nem pressupor que a conversa avançou.
Essa regra vale para tratamentos de mídia, financeiro, contexto e qualquer
tratamento futuro que reapresente conteúdo da etapa.

### 11.7. Saudação de retorno após inatividade

Depois que o cliente já informou o nome na etapa 1, uma nova mensagem recebida
na mesma conversa pelo menos três horas após o último envio confirmado do bot
deverá fazer a resposta começar com `Bom te ver novamente, {nome} ☺️` no caminho normal
com `followup_stage = 0`. Stage positivo ou retomada já registrada segue o
[contrato de follow-up](#follow-up-de-inatividade-e-reação-do-cliente), com o
prefixo de retorno e a validação da resposta; a etapa 8 avança diretamente para a 9.

O intervalo é inclusivo (`>= 3 horas`) e deve comparar o horário original do
evento atual do cliente com a última linha `sent` do bot no histórico da mesma
`id_conversa`. A atividade do mesmo cliente em outra unidade ou conversa não
participa desse cálculo. A própria mensagem em que o nome é informado na etapa
1 ainda não recebe a saudação; a regra começa nas mensagens seguintes, quando o
nome já está validado e persistido.

A saudação é somente um prefixo da resposta que o fluxo já produziria:

- resposta válida: saudação mais a mensagem da etapa resultante;
- mídia, financeiro ou reforço: saudação mais o tratamento e a repetição da etapa atual;
- contexto inválido: saudação mais a mensagem própria de contexto, sem outra pergunta.

Ela não cria etapa, evento de transição, envio separado nem uma segunda linha de
histórico. A barreira idempotente continua sendo executada antes dos resolvers:
se o retry já encontrar a resposta exata do bot persistida para aquela mensagem
do cliente, nenhum novo envio ou prefixo será produzido. Nome, último envio ou
timestamps ausentes/incompatíveis apenas desativam a saudação para aquele evento
e nunca impedem a resposta normal do fluxo.

## 12. Flood, payload e assinatura

- A regra atual de rajada curta considera 15 eventos em 5 segundos.
- Redis é a primeira fonte de avaliação de flood.
- Banco e memória funcionam como fallbacks previstos.
- Um cliente identificado como flood poderá ser bloqueado na Meta e não deverá
  ser enfileirado.
- Conversas explicitamente bloqueadas também não serão enfileiradas.
- Payload acima de `WEBHOOK_MAX_BODY_BYTES` deverá ser rejeitado com HTTP 413
  antes de parse, flood, cache ou banco.
- Assinatura Meta inválida deverá ser rejeitada com HTTP 403 antes de qualquer
  confiança no conteúdo do payload.

Payload grande e assinatura inválida bloqueiam a requisição na entrada, mas não
devem bloquear diretamente um cliente na Meta. Um atacante poderia montar um
payload inválido utilizando o `wa_id` de um cliente real. Bloquear esse número
atingiria a vítima informada pelo atacante, e não necessariamente a origem da
requisição.

Portanto, HTTP 413 ou 403 sem bloqueio Meta é o comportamento final e esperado da
V1, e não uma implementação parcial.

Implementação principal:

- `callback/webhook/services/post_flow.py`
- `callback/webhook/services/flood_guard.py`
- `core/cache/runtime/cache_flood_redis.py`
- `core/cache/cache_flood_memoria.py`

## 13. Commits e estados intermediários do worker

O worker de atendimento possui checkpoints duráveis separados:

1. claim da fila como `processing`;
2. espera por mensagem anterior, quando necessária;
3. validação do cliente e da conversa no banco;
4. aquisição do lock da conversa;
5. vínculo, releitura e histórico do cliente, incluindo o marcador de retomada quando aplicável;
6. renovação do lock antes do envio;
7. histórico e contexto do bot; na retomada, conclusão do marcador e reset do stage;
8. fila marcada como `sent`, depois de conferir novamente a posse do lock;
9. unlock da conversa.

Uma queda entre checkpoints normalmente deixa informações suficientes para que
o timeout e o retry reconheçam o estado intermediário. O objetivo é evitar a
perda da mensagem aceita, mesmo admitindo duplicidade rara.

As decisões de `commit`, `rollback` e `close` da conexão do ciclo pertencem ao
`flow_worker.py`. Repositórios e módulos internos executam operações utilizando a
conexão ou o cursor recebido, sem assumir a propriedade da transação.

## 14. Duplicidade aceita como exceção rara

O sistema busca entrega pelo menos uma vez, e não exatamente uma vez.

A principal janela aceita de duplicidade é:

```text
Meta confirmou ou efetivou o envio
        -> worker caiu ou perdeu a confirmação
        -> histórico do bot ainda não foi confirmado no banco
```

Nesse intervalo, o retry não encontra uma resposta persistida e poderá enviar
novamente. Depois do commit do histórico do bot, o retry deverá reconhecer a
resposta e não repetir o envio.

Duplicidade frequente, determinística ou ocorrida depois de a resposta do bot já
estar persistida é bug. Duplicidade excepcional na janela externa entre Meta e
banco é um trade-off conhecido e aceito na V1.

O Funil possui uma janela externa equivalente:

```text
Funil confirmou a oportunidade
        -> banco caiu antes de marcar lead_no_funil
        -> lease expirou
        -> retry pode criar outra oportunidade
```

O estado local `processing` e o snapshot persistido tornam o caso rastreável, mas
não existe exatamente uma vez sem consulta de reconciliação suportada pelo CRM.

## 15. O que é bug na V1

São bugs, entre outros:

- a primeira ou única mensagem válida do turno ser ignorada sem uma regra
  aplicável;
- uma mensagem aceita desaparecer antes de concluir a política prevista de
  tentativas;
- o bot enviar novamente quando a resposta atual já estiver persistida;
- `last_message_from` permanecer como `cliente` quando a resposta atual do bot já
  estiver persistida, ou como `bot` quando ainda não existir resposta persistida;
- uma etapa mudar sem a aresta `origem + evento -> destino` autorizada;
- duas mensagens do mesmo turno avançarem a conversa como se fossem turnos
  independentes;
- uma mensagem posterior ultrapassar outra anterior ainda aberta na conversa;
- uma falha prevista encerrar permanentemente o worker sem tentativa de
  recuperação.

## 16. O que não é bug na V1

Não são bugs:

- ignorar qualquer segunda mensagem quando a primeira mensagem do mesmo cliente e
  unidade ainda estiver aberta e sem resposta própria do bot;
- ignorar a repetição do mesmo webhook ou `id_hash_msg`;
- reutilizar histórico existente durante um retry;
- responder a uma mídia com orientação sem avançar etapa já apresentada;
- apresentar a etapa 1 junto com o aviso quando a conversa for iniciada com
  mídia;
- responder pergunta sobre valor sem tratar esse texto como nome ou avanço de
  etapa;
- excluir a mensagem ao atingir a terceira tentativa;
- aguardar os timeouts da fila ou do lock antes de um novo processamento;
- uma duplicidade extremamente rara na janela entre Meta e commit do bot;
- rejeitar payload grande ou assinatura inválida sem bloquear o número informado
  na Meta.

## 17. Falhas operacionais do webhook e reentrega da Meta

Quando uma mensagem válida chega à transação da fila, mas conexão, inserção ou
commit falham:

- a transação será revertida com rollback;
- o webhook registrará `insert_exception`;
- a resposta será HTTP 503 com `status = 'unavailable'`;
- a Meta poderá tratar a entrega como malsucedida e reenviar o evento;
- a repetição continuará protegida pela unicidade de `id_hash_msg`.

Também é HTTP 503 quando o webhook não consegue validar a unidade porque Redis e
banco estão indisponíveis no mesmo ponto do fluxo. Nesse caso:

- o webhook registrará `unit_validation_unavailable`;
- a mensagem não será tratada como unidade inativa;
- a Meta poderá reenviar o evento quando o endpoint voltar a responder com
  sucesso.

Esse HTTP 503 é reservado para falhas operacionais que impedem o sistema de
decidir ou persistir uma mensagem válida com segurança. Mensagens descartadas
intencionalmente por turno aberto, duplicidade, flood, unidade inativa, conversa
bloqueada ou payload sem mensagem processável continuam seguindo seus contratos
de `ignored` e não devem ser transformadas em indisponibilidade.

O retry da Meta protege a chegada ao webhook e não substitui o retry interno do
worker. Depois que a fila foi persistida e o webhook respondeu HTTP 200, qualquer
falha de processamento ou envio da resposta pertence à política de tentativas do
worker.

## 18. Cache, fallback e autocura

Tabelas e consultas de baixa volatilidade ou alta frequência devem priorizar
Redis e possuir fallback para a fonte de verdade no banco quando o cache estiver
indisponível, inválido ou inconsistente de maneira detectável.

Princípios obrigatórios:

- Redis é um acelerador; o banco continua sendo a fonte de verdade.
- Uma falha do Redis não deverá interromper o fluxo quando houver fallback seguro
  no banco.
- Depois de consultar o banco por fallback, o sistema deverá tentar reparar o
  Redis com os dados atuais.
- Uma falha na tentativa de reparo do cache não deverá apagar dados válidos do
  banco.
- Quando um valor stale causar erro de integridade, ele deverá ser removido ou o
  cache completo deverá ser recarregado para que o próximo retry consulte o banco
  e se recupere.
- Operações administrativas que exijam banco e cache coerentes deverão ser
  bloqueadas se o Redis não puder ser validado ou atualizado.

### 18.1. Cache de unidades

- Utiliza hash Redis, quantidade esperada e versão mantida em
  `chatbot.cache_controle`.
- Webhook e worker conferem periodicamente a versão do Redis contra a versão do
  banco e recarregam o cache quando encontram divergência.
- O Django Admin incrementa a versão e recria o cache depois de salvar ou excluir
  uma unidade.
- Se o Redis falhar, webhook e worker utilizam fallback no banco e tentam
  recarregar o cache.
- Se um `id_unidade` stale causar violação de FK no worker, o cache de unidades é
  recarregado antes do retry.

### 18.2. Cache de clientes

- Relaciona `wa_id` ao `id_cliente` e possui TTL.
- Miss, valor inválido ou Redis indisponível levam a consulta ao banco.
- Um cliente criado ou encontrado no banco será salvo no cache somente depois do
  commit que confirmar sua existência.
- Se um `id_cliente` stale causar violação de FK, a chave será removida para que o
  retry reconstrua o valor correto pelo banco.

### 18.3. Cache de conversas bloqueadas

- O bloqueio de 30 dias utiliza Redis com TTL calculado a partir de
  `finalizou_em`.
- Quando o Redis falha, o banco é consultado e o cache é criado ou removido para
  refletir o resultado persistido.
- Quando o worker encontra uma conversa bloqueada que ainda não estava no cache,
  ele registra a chave com o TTL restante e remove a mensagem da fila.
- Depois de expirado o período, a chave não deverá mais bloquear o cliente.
- Esse cache possui mecanismo próprio de reparo e não deverá ser incluído nos
  reparos de FK de cliente e unidade do `flow_worker.py`.

### 18.4. Escopo da autocura

- A autocura cobre falhas detectadas, versão divergente de unidades e erros FK
  de cliente ou unidade.
- Em produção, alterações manuais diretamente no banco são proibidas. Dados que
  afetam cache devem ser modificados pelos fluxos oficiais da aplicação ou pelo
  Django Admin.
- Edições manuais no banco são permitidas somente em desenvolvimento. Nesse
  ambiente, atrasos de sincronização poderão ser corrigidos pelo reset de cache
  destinado a DEV.
- O sistema não precisa comparar banco e Redis em toda leitura para detectar uma
  edição manual que viole o contrato de produção.

Dentro desse contrato, a autocura implementada atende às regras da V1. Suporte a
edições manuais silenciosas em produção não é requisito.

Implementação principal:

- `core/cache/cache_unidade.py`
- `core/cache/runtime/cache_cliente.py`
- `core/cache/runtime/cache_conversas_bloqueadas.py`
- `core/repositories/unidades/cache_control.py`
- `workers/worker_flow/suporte/cache_repair.py`

## 19. Regras do Django Admin

O Django Admin é uma superfície operacional controlada, e não uma forma livre de
editar as tabelas do fluxo.

### 19.1. Tabelas somente para visualização

Cliente, dependente, etapa, conversa, fila, histórico, respostas de desafio,
eventos de flood e controle de cache utilizam administração somente leitura:

- não permitem adicionar;
- não permitem alterar;
- não permitem excluir;
- exibem os campos somente para consulta operacional.

### 19.2. Clientes bloqueados na Meta

- `cliente_bloqueado_meta` representa a intenção persistente de bloquear o par
  `wa_id_cliente + phone_id_unidade`, além dos bloqueios já confirmados pela
  Meta.
- Um contato identificado manualmente pode ser registrado nessa tabela mesmo
  quando a janela da Meta ainda não permite confirmar o bloqueio.
- Toda nova mensagem desse par é interceptada antes do flood, da validação da
  unidade e da fila.
- O webhook tenta bloquear novamente na Meta e sempre ignora a mensagem, tanto
  no sucesso quanto na falha. Uma mensagem futura provoca uma nova tentativa.
- Falha ao consultar a lista retorna HTTP 503 para a Meta reenviar o evento;
  nenhuma mensagem é enfileirada sem que essa validação seja concluída.
- A consulta sempre inclui `wa_id_cliente` e `phone_id_unidade`, preservando o
  isolamento multi-WABA.
- Bloqueios automáticos detectados pelo sistema registram e confirmam primeiro
  a intenção local no banco; somente depois do commit tentam o bloqueio na
  Meta, sem manter transação aberta durante a chamada externa.
- Se a Meta recusar o bloqueio, a linha local permanece autoritativa: a
  mensagem atual é ignorada e uma mensagem futura provoca nova tentativa.
- Se a intenção local não puder ser persistida por indisponibilidade do banco,
  o webhook não chama a Meta, não enfileira a mensagem e retorna HTTP 503 para
  permitir reentrega.
- O Django Admin continua sem permitir a criação livre de registros enquanto
  não existir uma interface específica para classificar bots manualmente.
- O administrador poderá somente desbloquear, removendo individualmente um
  registro existente.
- Desbloqueio em massa é proibido.
- No desbloqueio, a ordem obrigatória é Meta primeiro, banco depois.
- Se o desbloqueio na Meta falhar, o registro deverá permanecer no banco.
- Não existe chave Redis equivalente: a própria tabela é consultada de forma
  autoritativa pelo webhook.

### 19.3. Unidades

- Cada unidade possui um `waba_id` único e obrigatório e um
  `phone_number_id` único e obrigatório.
- A criação valida primeiro, pela Graph API, se o `phone_number_id` pertence
  ao `waba_id` informado.
- Depois da validação, o App assina a WABA e registra o número na Meta.
- Se a Meta falhar, a unidade não será criada no banco.
- Antes da alteração no banco, o Redis deverá passar pelo preflight.
- Depois do save, a versão das unidades será incrementada e o cache recarregado.
- A exclusão desassina a WABA e desregistra o número na Meta antes de remover
  a unidade do banco.
- Se a Meta falhar durante a exclusão, a unidade permanecerá no banco.
- Se o Redis falhar depois de a Meta responder, o banco deverá permanecer sem
  alteração e o administrador deverá receber uma mensagem para tentar novamente.
- Exclusão em massa de unidades é proibida.
- `idade_minima_suporte` e `email_obrigatorio` são editáveis no Admin; a ativação do
  suporte exige um número comercial válido. `waba_id` e `phone_number_id` ficam
  somente leitura depois da criação.

### 19.4. Papel de `status_pagamento`

`status_pagamento` não representa vinculação ou desvinculação do número no WABA.

- O campo é o controle atual de admissão da unidade: somente registros com
  `status_pagamento = TRUE` entram no cache de unidades ativas e são localizados
  pelo webhook e worker.
- Uma futura tabela `payment` poderá automatizar essa decisão, mas ela não faz
  parte da V1.
- Na V1, pagamentos e contratos poderão ser controlados manualmente, contrato por
  contrato.
- Alterar `status_pagamento` deverá atualizar banco e cache de unidades, mas não
  deverá registrar ou remover o número na Meta.

O fato de uma edição de `status_pagamento` não chamar a Meta é comportamento esperado,
e não uma lacuna.

### 19.5. Desvinculação definitiva de uma unidade

Para encerrar o vínculo de uma unidade com o sistema:

1. solicitar a exclusão individualmente pelo Django Admin;
2. o sistema remove a assinatura do App na WABA;
3. o sistema desregistra o `phone_number_id`;
4. somente após as duas confirmações Meta conclui a exclusão no banco e
   atualiza o cache de unidades.

A exclusão administrativa continua protegida pela validação Meta-first do código
e pelo preflight do Redis. A exclusão em massa permanece proibida.

Implementação principal:

- `callback/webhook/admin.py`
- `core/integrations/whatsapp/tools/validando_phone_waba.py`
- `core/integrations/whatsapp/tools/ativando_waba_id.py`
- `core/integrations/whatsapp/tools/desativa_waba_id.py`
- `core/integrations/whatsapp/tools/ativando_numero.py`
- `core/integrations/whatsapp/tools/desativando_numero.py`

### 19.6. Contas de monitoramento por unidade

- `chatbot.unidade.id_usuario_monitoramento` referencia `chatbot.auth_user.id`.
  O vínculo é opcional e único: cada usuário pode monitorar no máximo uma
  unidade e cada unidade pode possuir no máximo uma conta de monitoramento.
  Várias unidades podem manter o campo `NULL`, sem acesso de monitoramento.
- Login, hash da senha e ativação da conta pertencem à autenticação do Django;
  a unidade armazena somente a referência. No Admin, crie a conta em **Usuários**
  e selecione-a no campo **Usuário de monitoramento** do cadastro da unidade.
- Contas de monitoramento não possuem `is_staff` nem `is_superuser`. O formulário
  recusa contas administrativas e a autorização também confere esses estados
  diretamente no banco, além de `is_active`.
- A identidade vem de `request.user`; usuário/unidade informados pelo navegador
  não definem o escopo. Sem sessão válida, vínculo ou conta habilitada, o acesso
  é negado. Erro de banco não autoriza leitura.
- Conversas são autorizadas por `conversa.id_unidade`; mensagens, pela unidade
  de sua conversa. O cadastro global de cliente não concede acesso às conversas
  dele em outras unidades. Se conversa e mensagem forem informadas juntas, a
  mensagem deve pertencer àquela conversa.
- O vínculo é consultado a cada requisição, sem cache nem bypass administrativo.
  Remover o vínculo, desativar a conta ou mudar sua unidade afeta a próxima
  consulta. `status_pagamento` continua com sua finalidade de admissão do bot;
  não é um novo bloqueio do monitoramento.
- Excluir um usuário limpa a referência por `ON DELETE SET NULL`, preservando
  a unidade, suas conversas e seu histórico. Excluir a unidade pelo fluxo
  administrativo existente não exclui a conta Django. Limpar somente o campo
  de monitoramento revoga o acesso sem excluir entidades.
- O login usa o par `username`/senha da mesma conta e o verificador de hash
  nativo do Django. Antes de criar a sessão, exige conta habilitada, comum e
  vinculada a uma unidade. Usuário inexistente e senha incorreta recebem o
  mesmo aviso. Não há cadastro, recuperação/troca de senha ou bloqueio após
  três tentativas no portal; o proprietário administra as contas pelo Admin.
- Login e logout usam CSRF; logout somente por POST. O destino após autenticar
  é fixo, sem aceitar redirecionamento escolhido pelo navegador. A senha fica
  mascarada e não volta preenchida após erro. Falhas de banco não liberam acesso.
- O acesso bem-sucedido abre o painel em `/`. A página e todas as rotas de dados
  usam `exigir_acesso_monitoramento` e mantêm cada SELECT limitado à unidade
  retornada. A autorização não filtra automaticamente outros SQLs ou QuerySets.
- O painel é somente leitura. Suas rotas de dados aceitam apenas GET; não há
  envio de mensagens, cadastro, edição nem exclusão de informações.
- O período padrão cobre a primeira mensagem de cliente registrada na unidade
  até o instante da consulta. Também são aceitas janelas de 24 horas, 7 e 30
  dias, 2, 3 e 6 meses e 1 ano. Uma janela finita compara seus indicadores com
  a janela imediatamente anterior de igual duração.
- Conversas técnicas do mesmo cliente são consolidadas somente dentro da unidade
  autorizada. Os filtros locais são Todas, Comercial, Follow-up, Funil e Avaliadas; os
  perfis visuais são Menor de 18, Adulto, 60+ e Dependente. Na lista de
  conversas, as etiquetas ao lado da data preservam a relação entre faixa
  etária e destino nas formas abreviadas DP -18, DP 18–59, DP 60+, 18–59 e
  60+; a descrição completa permanece disponível como informação acessível.
- O navegador consulta conversas a cada 10 segundos e relatórios a cada 30
  segundos quando a página está visível. Voltar à aba força uma leitura. Esse
  polling usa o mesmo serviço Django/Gunicorn do webhook e não cria worker ou
  serviço systemd adicional.
- As opções `idade_minima_suporte`, `email_obrigatorio` e `bpa_ativo` são lidas
  da unidade. O limite é apresentado como política; não modifica tags 18–59/60+
  ou de dependentes nem esconde envios ao Funil registrados em qualquer faixa.
- Comercial mostra somente chats cuja última conversa real na unidade encerrou
  por idade. Uma conversa nova remove a tag, mesmo fora do período consultado;
  a configuração atual não altera uma tag histórica. A legenda explica cada filtro.
- Relatórios possui a tabela Encaminhamentos e encerramentos por idade abaixo
  dos quatro KPIs. Conta conversas (não contatos), por `finalizou_em >= início`
  e `< fim`, mesmo que exista atendimento posterior. Mostra suporte do limite
  atual, universal 90+ separada por titular/dependente, titular menor e dependente
  abaixo do mínimo BPA atual. Configurações diferentes e legados sem limite
  identificável ficam fora. Reescolher a mesma configuração inclui motivos iguais
  no período, independentemente da data dessa reconfiguração.
  Distingue contato enviado de encerramento sem contato; não comprova clique,
  atendimento humano, matrícula ou envio ao Funil. Falha de consulta não é zero.
- O relatório mostra métricas, comparação, demanda ao longo do tempo, perfis,
  satisfação e a etapa atual da conversa mais recente de cada contato que teve
  atividade no período. Cada contato conta uma vez. A etapa é um retrato atual;
  o banco não permite reconstruir em qual etapa a conversa estava em uma data
  passada.
- O histórico armazena texto e tipo da mensagem, mas não o payload exato dos
  botões enviados. Para mensagens interativas, o painel mostra os botões do
  catálogo atual daquela etapa como referência visual, sempre desabilitados.
- Os quatro indicadores agregados ficam na seção Relatórios. A seção Conversas
  prioriza a visualização da lista e do histórico, mantendo filtros e período.
- O CSV completo inclui todos os contatos ativos no período e deixa campos
  ausentes vazios. O CSV elegível exige nome, e-mail estruturalmente válido e
  telefone normalizado. Ambos usam
  cabeçalhos compatíveis com importação no Google Contatos e nunca alteram o
  banco.
- Há também duas exportações de dados essenciais, para todos os contatos ou
  apenas elegíveis, com somente Nome, E-mail e Telefone. Mantêm o nome completo
  em uma coluna, sem acrescentar rótulos ou datas, e reutilizam as mesmas regras
  de período, unidade, normalização e elegibilidade dos arquivos Google CSV.
  Somente nesses dois CSVs essenciais, o telefone brasileiro é exibido sem o
  prefixo internacional `+55`, preservando o DDD e o número.

## 20. Disponibilidade e recuperação automática

“O sistema não deve cair nunca” é um requisito de resiliência operacional e
recuperação automática. Isso não significa afirmar que o interpretador Python, a
máquina ou a rede jamais poderão falhar.

Sempre deverá existir uma camada capaz de conter a falha e manter ou restaurar o
serviço:

- falha do Redis utiliza fallback quando existe uma fonte segura no banco;
- falha de uma mensagem não encerra o processamento das demais;
- o worker captura falhas, preserva ou reagenda o estado quando possível e
  continua o loop;
- o worker do Funil isola erros por lead e reinicia falhas globais com espera
  linear de 5 a 60 segundos;
- o worker de follow-up isola erros por candidata e usa espera exponencial de
  5 até 300 segundos quando a consulta do lote falha;
- `flow_worker.py` mantém o loop de consumo e os tratamentos por tipo de exceção;
- se `worker_flow()` escapar com uma exceção, `iniciar_flow_worker.py` registra a falha,
  aguarda 5 segundos e inicia outro loop;
- o webhook responde de maneira controlada a entradas inválidas e falhas
  conhecidas;
- chamadas externas à Meta falham de forma controlada, sem confirmar no banco
  uma operação recusada pela Meta;
- caches degradam para fallback ou negam uma operação administrativa que
  produziria inconsistência.

Na produção atual, webhook, worker de atendimento, worker do Funil e worker de
follow-up são quatro serviços systemd independentes. Os três primeiros usam
`Restart=always`; follow-up usa `Restart=on-failure`. Todos têm `RestartSec=5s`.
As camadas de recuperação são complementares:

```text
operação individual falha
    -> exception ou fallback trata
    -> flow_worker continua
    -> iniciar_flow_worker reinicia o fluxo se ele escapar
    -> systemd reinicia o processo se ele encerrar
```

A URL pública e os serviços de produção devem permanecer disponíveis 24x7.
Falhas previstas não poderão produzir encerramento permanente do serviço nem
corrupção silenciosa. Os loops e fallbacks da aplicação atuam antes da supervisão
dos processos pelo sistema operacional.

Implementação principal:

- `workers/worker_flow/iniciar_flow_worker.py`
- `workers/worker_flow/response_flow/flow_worker.py`
- `workers/worker_funil/funil_worker.py`
- `workers/worker_funil/iniciar_worker_funil.py`
- `core/cache/redis_client.py`
- `callback/webhook/services/post_flow.py`
- `deploy/systemd/chatbot-webhook.service`
- `deploy/systemd/chatbot-worker-flow.service`
- `deploy/systemd/chatbot-worker-funil.service`
- `workers/worker_followup/iniciar_worker_followup.py`
- `workers/worker_followup/followup_worker.py`
- `deploy/systemd/chatbot-worker-followup.service`

## 21. Matriz de aderência conferida no código

| Regra | Estado atual | Observação |
|---|---|---|
| Somente a primeira mensagem sem resposta do turno é válida | Implementada | As demais não entram na fila nem no histórico enquanto existir uma fila aberta sem resposta própria do bot. |
| Liberar o próximo turno por resposta específica do bot | Implementada | O histórico vinculado à fila permite recuperação antes de `fila.status='sent'`, sem liberar uma sequência ilimitada. |
| Bloqueio de 30 dias depois da etapa final | Implementada | Banco e cache utilizam janela ou TTL de 30 dias. |
| Flood acima da métrica | Implementada | Redis, banco e memória formam a cadeia de avaliação; flood pode bloquear na Meta. |
| Payload grande | Implementada conforme a regra | Retorna HTTP 413 e não bloqueia a identidade informada no payload. |
| Assinatura inválida | Implementada conforme a regra | Retorna HTTP 403 e não confia no payload nem bloqueia possível vítima informada nele. |
| Falha operacional do webhook com mensagem válida | Implementada | Inserção/commit da fila e validação de unidade indisponível retornam HTTP 503 para permitir reentrega; descartes de negócio continuam HTTP 200. |
| Cache Redis com fallback para banco | Implementada nos caches principais | Unidades, clientes e conversas bloqueadas possuem estratégias de fallback. |
| Autocura Redis/banco | Implementada no contrato da V1 | Cobre falhas detectáveis e FK stale; edição direta no banco é proibida em produção. |
| Admin majoritariamente somente leitura | Implementada | As exceções operacionais são unidade (incluindo seu usuário de monitoramento), integração com o Funil e desbloqueio individual. |
| Admin somente desbloqueia clientes | Implementada | Meta primeiro; falha preserva o registro no banco. |
| Unidade Meta-first na criação e exclusão | Implementada | Falha da Meta impede a alteração do banco. |
| `status_pagamento` sem chamada Meta | Implementada conforme a regra | O valor controla a admissão da unidade, mas não registra nem remove o número na Meta. |
| Desvinculação definitiva da unidade | Definida operacionalmente | Remover do WABA oficial e excluir individualmente pelo Admin. |
| Worker continua ou reinicia depois de falha | Implementada em camadas | `funil_worker.py` recupera banco e agenda os ciclos; `iniciar_worker_funil.py` recria o worker após falha crítica. `iniciar_flow_worker.py` mantém a supervisão do atendimento. |
| Conversa elegível vira oportunidade no Funil | Implementada e desativada por padrão | Etapas 20–24, `funil_envios`, claim com lease e confirmação lógica da ApiCarrossel. |
| Uma falha de lead não interrompe o lote do Funil | Implementada | O item volta para `pending`; os demais continuam no mesmo ciclo. |
| Follow-up antes do agendamento | Implementada | Primeiro lembrete após 7h; despedida e encerramento após outras 7h sem resposta, nas etapas 1–17 e a 18 somente para unidade sem link, inclusive 8, dentro da janela do cliente. Retorno antes do encerramento valida a resposta; depois, abre nova conversa. |
| Supervisão dos quatro processos | Implementada | Webhook, flow e Funil usam `Restart=always`; follow-up usa `Restart=on-failure`. Nginx encaminha o endpoint público ao webhook. |

## 22. Orientação para futuras alterações

Antes de modificar o fluxo:

1. identificar qual regra deste documento está envolvida;
2. classificar a mudança como correção, refatoração ou alteração de produto;
3. preservar turno único, idempotência e limite de tentativas quando a tarefa não
   solicitar explicitamente o contrário;
4. mapear quedas antes e depois de cada commit;
5. testar fluxo normal, retry antes do bot, retry depois do bot e finalização da
   fila;
6. não tratar um comportamento esperado da V1 como bug apenas por ele parecer
   conservador ou incompleto.

## Follow-up de inatividade e reação do cliente

Implementado na V1.2.0. As instruções de operação vivem nos
[workers](workers/README.md#worker-de-follow-up) e no
[deploy](deploy/README.md#ativação-do-follow-up); não dependem dos planos de implementação.

O worker proativo envia o lembrete definido em `messages/followup_messages.py`
depois de sete horas sem reação à última resposta comum confirmada do bot.
NULL equivale a stage zero.
O envio exige conversa ativa em etapa 1–17 e a 18 somente para unidade sem link, unidade válida e adimplente, ausência
de bloqueios, de entrada posterior no histórico e de fila pending/processing do
mesmo par cliente/unidade, mesmo se ainda não vinculada à conversa. Uma fila
respondida mas ainda aberta também adia o proativo até sua finalização.

O canal exige janela aberta desde a última mensagem do cliente; este envio em texto
livre não usa template. A implementação reserva um minuto antes de completar 24h
para evitar despacho na borda. Isso não altera o limiar de sete horas do bot.

São dois relógios distintos: a última mensagem de toda a conversa precisa ser
do bot há pelo menos sete horas, e a mensagem mais recente do cliente, anterior
a ela, precisa estar dentro de 23h59. Bot há oito horas com cliente há 25 horas
é inelegível; bot há oito horas com cliente há nove horas pode ser elegível.

O worker produz 0 → 1 no primeiro envio. Após outras sete horas sem resposta,
contadas do primeiro envio confirmado, produz 1 → 2 com a despedida e encerra a
conversa (`status_ativa = false`, `finalizou_em` e motivo `followup_sem_resposta`).
Mantém a etapa de origem, sem aplicar o bloqueio de 30 dias. Não há terceiro envio.
Histórico, recibo, stage 2 e encerramento são gravados na mesma transação, somente
após confirmação da Meta. Falha no envio mantém a conversa aberta em stage 1.
Se a janela de 23h59 já expirou, não envia nem simula encerramento.

O segundo envio exige recibo real do primeiro, correspondente ao último bot e ao
`followup_last_sent_at`; marcação de legado sem recibo não permite uma despedida.
As duas camadas são restritas às etapas 1–17 e a 18 somente para unidade sem link, incluindo a 8. Uma reação antes do
segundo envio cancela sua elegibilidade e mantém o processamento descrito abaixo.
Depois do encerramento, outra mensagem abre novo ID de conversa, com stage zero
e mensagem inicial da etapa 1, sem prefixo de retorno nem nome de cadastro antigo.

O filtro **Follow-up** do painel considera stage 1 ou 2 da conversa mais recente
do mesmo cliente/unidade. Uma conversa posterior invalida o marcador antigo,
inclusive se estiver fora do período selecionado. O chat continua reunindo todo
o histórico permitido pelo período; excluir do filtro não apaga atendimento.

A primeira entrada aceita com stage positivo em conversa ainda ativa é armazenada e validada pelos
mesmos resolvers do atendimento normal. Respeitar as prioridades de cada etapa:
tratamentos específicos existentes (mídia, financeiro e reforço) permanecem;
resposta válida segue seu evento, efeitos e destino; resposta sem validação nem
tratamento específico reapresenta a pergunta neutra, sem reprimenda de contexto.
A triagem mantém apenas suas opções canônicas, sem ganhar tratamentos novos.

A resposta começa com `Bom te ver novamente, <nome> ☺️` ou a forma sem nome
`Bom te ver novamente ☺️`. Na etapa 1, nunca usar o nome de atendimento anterior:
um nome válido recebido agora é salvo e avança para a 2; caso contrário, tratar
ou repetir conforme a regra acima. O cadastro antigo não é apagado para saudação.
O prefixo independe do tempo de retorno, aparece uma vez e substitui a saudação
de três horas. No retorno comum por três horas, o processamento continua normal,
inclusive o tratamento de contexto inválido; só a redação do prefixo é igual.

Sem avanço, essa primeira reação não incrementa `turnos_sem_avanco`, inclusive
quando recebe tratamento específico. Uma transição válida zera esse contador
normalmente. A resposta seguinte volta à contagem normal de tratamentos.

**Exceção da etapa 8:** qualquer reação processada com follow-up pendente provoca
`8 → cliente_retornou → 9`, reutilizando o resolver e o mapa do retorno normal.
Não repetir a mensagem da 8, nem criar ou enviar uma variante de repetição.
A oferta da 9 preserva titular/dependente, botões e rodapé e recebe somente a
saudação de follow-up. O conteúdo não é classificado como tratamento ou aceite:
mesmo uma confirmação nessa reação apenas apresenta a 9; a próxima resposta
segue sua validação normal. Não há Funil ou encerramento nessa transição.

O histórico do cliente e o checkpoint conservam a origem 8; a resposta do bot
usa a etapa 9. A transição, o reset de turnos sem avanço do fluxo normal,
o histórico da resposta e a conclusão do follow-up pertencem ao mesmo commit.
Falha reverte esses efeitos juntos. Retry de retomada concluída reutiliza o
destino efetivamente gravado, inclusive uma repetição antiga da 8, sem reenviar,
refazer a transição ou zerar um ciclo posterior. A exceção vale também para
stage positivo legado sem data de envio; a elegibilidade proativa não muda.

A migração inicial marca followup_stage = 1 para todas as conversas ativas antigas,
incluindo etapas 20–23, e registra seus IDs, stages anteriores e a data da marcação
em followup_legado. Não envia lembrete, não encerra conversas, não inventa recibo
nem altera followup_last_sent_at. Stage positivo passa a indicar retomada pendente,
por envio real ou marcação inicial; somente o histórico/recibo comprova envio.
Novas conversas continuam com stage zero. O setup limpo não marca conversas.

Histórico, efeitos normais, marcação da retomada, reset para zero, eventual
encerramento e finalização da fila pertencem ao mesmo commit. followup_last_sent_at permanece como auditoria. Um retry de retomada
concluída usa a resposta já persistida, sem zerar um ciclo posterior. A mensagem
seguinte é interpretada normalmente; outro período de sete horas pode iniciar um
novo ciclo somente nas etapas 1–17 e a 18 somente para unidade sem link e com as demais condições de envio atendidas.
Stage maior que um em conversa legada ainda ativa segue a mesma recuperação;
stage 2 encerrado pelo novo proativo permanece como auditoria; negativo falha fechado.

A exceção deliberada é a repetição neutra diante de contexto inválido genérico
no primeiro retorno. Stage zero preserva o processamento normal por inteiro.
O registro proativo não possui fila nem hash de cliente de origem e não prova que
uma fila A/B/C foi respondida. Os recibos próprios identificam a conversa e a âncora
do ciclo; registros de retomada identificam a entrada processada para recuperação.

Os dois workers compartilham o lock de 110 segundos e seu fencing. Entrada aceita
após o último teste pré-envio pode cruzar com a chamada da Meta: confirmamos o
envio. No primeiro, o flow lê stage positivo ao obter o lock; no segundo, relê
o estado encerrado e abre outro atendimento, reagendando uma leitura obsoleta sem
consumir retry. A janela entre aceite
externo e commit local continua sujeita à duplicidade rara já aceita na V1.


## Extração dos campos de formulário FireAds

A correspondência do telefone na aba `LEADS GERAL - Feedback` identifica o cadastro.
Filtrar primeiro os canais Google Ads, Meta Ads e Organico Site; depois selecionar
a data/hora mais recente e, no empate, a maior `_row`. Datas inválidas ficam atrás
das válidas; sem data válida, usar a maior linha. Canais manuais não participam
dessa seleção. O destinatário vem somente de `Para quem é`, nunca de `Perfil/Faixa`.
Usar somente o registro selecionado pelas regras FireAds; não completar
campos vazios com dados de outra inscrição ou de uma conversa anterior.

Nome, e-mail e destinatário vêm de campos estruturados. Não aplicar as regras de
validação de respostas livres do WhatsApp para rejeitar nomes de perfil ou o
formato do e-mail. Extrair a primeira palavra do nome, ou as duas primeiras quando
formarem um par conhecido de nome composto; ignorar sobrenomes e complementos
posteriores. Exemplo: `Edcarlos Oliveira | Programador` torna-se `Edcarlos`.
Nomes compostos desconhecidos usam a primeira palavra. Aparar espaços do e-mail e
normalizar a caixa, preservando seu conteúdo sem testes de estrutura ou domínio.
Interpretar o destinatário pelas opções explícitas do formulário, nunca por idade.

Com os três campos extraídos e destinatário reconhecido, importar os dados juntos,
manter a origem Google/Meta/Orgânico Site, abrir na profissão e dispensar a coleta posterior do
e-mail. O marcador histórico `email_valido` significa coleta aceita do formulário
nessa rota; o flow não reaplica a validação estrutural. As validações das respostas
digitadas pelo cliente nas etapas comuns continuam iguais.

Por enquanto, campo vazio mantém o atendimento comum desde a etapa 1, com motivo
`campos_ausentes`; destinatário fora das opções conhecidas registra
`destinatario_desconhecido` sem inventar um vínculo. Ausência de telefone, falha
operacional, timeout e conflito de e-mail no banco conservam os tratamentos atuais.
A coleta parcial com saudação de formulário está proposta em
[valida_dados_parciais_fireads.md](docs/valida_dados_parciais_fireads.md) e ainda não foi implementada.

## Entrega do atendimento ao dashboard FireAds

Após a confirmação do Funil, a entrega ao dashboard usa fila independente e
respeita unidade adimplente e integrações ativas. Consulta e entrega usam somente
`aba_destino`, exibida como Aba de leads no Admin.

A consulta guarda a identidade da linha selecionada, inclusive no fallback por
formulário incompleto ou canal não elegível. A entrega confere essa identidade;
se a linha mudou de posição, relocaliza o mesmo registro. Não troca o alvo por
um formulário posterior. Registro desaparecido ou modificado fica pendente para
conferência, sem escrever em outra pessoa nem recriar o cadastro automaticamente.

Bloco já gravado da mesma conversa tem prioridade e reconcilia o envio. Só
atualizar `Observação`, preservando o conteúdo recebido da API e as demais colunas.
Sem referência da consulta, conferir novamente o telefone e usar a data/linha mais
recente antes de criar um cadastro orgânico. E-mail associado a outro telefone
impede criação. Snapshot legado conserva sua seleção e seu texto originais.

Google usa 113336; Meta usa 113340; Orgânico Site e orgânico usam 113481. Os dois
últimos são origens distintas, descritas nas observações. Fallback por dado
incompleto não afirma campanha nem ausência de cadastro. Sem integração FireAds,
preservar o canal configurado na unidade.

O texto compartilhado começa com `Observações de atendimento`. Classificar como
`Novo lead` só quando não há conversa anterior no mesmo chat (cliente/unidade);
caso contrário usar `Novo atendimento para Lead antigo`. Profissão do titular
precede os dados do dependente. Manter a explicação técnica da ESL Tech e a chave
única de reconciliação. Congelar payload, canal, classificação e texto antes do
primeiro POST, também para unidades sem FireAds. Retry não reconstrói esses dados.

A API externa não oferece escrita condicional; edição manual entre leitura e
POST continua podendo conflitar. Funil aceito antes de uma queda no commit local
pode ser reenviado. Não reenviar Funil por falha exclusiva no dashboard.
Operação, migração e limites: [Plano aplicado](atualizar_envio.md).

## Consumo mensal de mensagens Meta

A seção Consumo usa analytics coletado por worker independente e armazenado por
unidade/mês. Não altera etapas, elegibilidade do Funil, bloqueios, janelas de envio
ou retries. O recorte é serviço individual: janela gratuita, franquia Meta usada
e mensagens cobradas. A ESL cobre as primeiras 1.000 cobradas de cada mês; o
excedente é separado. Franquia Meta inicial: 1.000 por número/mês, desde outubro/2026.

O calendário usa o fuso informado pela WABA. Mês atual recebe coleta horária;
meses encerrados pendentes recebem conferência diária. Só consolidar no dia 25
previsto, se os volumes coincidirem com a coleta válida anterior de mês completo
feita em data local anterior. Falha/divergência prorroga para o próximo dia 25.
Consolidado é decisão interna da ESL, não fechamento de fatura pela Meta, e encerra
as coletas automáticas do mês. Valores monetários no painel são referências.

A interface e os PDFs leem exclusivamente o banco da unidade autenticada. Falha
não apaga valores anteriores nem cria um saldo fictício. A data exibida é a última
coleta válida do worker. Fusos e fronteiras de meses existentes são preservados;
mudança incompatível de conta/número/fuso exige revisão, sem misturar recortes.
Procedimento operacional: [Consumo Meta](deploy/consumo_mensal_meta.md).

## Reserva com e sem plataforma

A configuração atual de `unidade.link_agendamento` decide a saída da triagem: com link, 17 → 20; sem link, 17 → 18 (preferência de turno) → 19 (contato comercial). A satisfação converge em 21 → 22 → 23 → 24, com salto 22 → 24 na recusa de comentário. As etapas 1–17 conservam suas regras.

`conversa.turno` aceita NULL, manha, tarde ou noite e é salvo somente na transação de 18 → 19. É preferência, não confirmação de agendamento. Qualquer texto posterior na 19 apresenta a nota da 21; não é interpretado como nota nessa mesma interação. Mídia repete a orientação da 19.

Na etapa 18, os três botões e frases afirmativas como `só posso pela tarde`,
`prefiro ir de manhã` e `à noite fica melhor para mim` definem um único turno.
Aceitar caixa, acentos, pontuação e os sinônimos matutino, vespertino e noturno.
Repetir o mesmo turno não cria uma segunda escolha. Dois turnos distintos,
negação, dúvida, pergunta ou ausência de escolha recebem o mesmo tratamento
pedindo **apenas um turno**, sem avançar nem salvar preferência. `Amanhã`,
`boa tarde` e `trabalho de manhã` não autorizam inferir um turno.

O webhook extrai o título da opção de `interactive` e `interactive_button`,
usando o identificador textual quando o título estiver ausente. O worker
aceita ambos os tipos nas etapas com opções, inclusive na recuperação de uma
resposta já enviada. Não interpretar o texto citado da pergunta anterior como
resposta; não flexibilizar a validação específica de cada etapa nem aceitar mídia.

O Funil exige 20–24 com link ou 19/21–24 sem link, considerando a configuração vigente na seleção, no claim e no snapshot. Preservar recibo de sucesso se o CRM já aceitou. O snapshot e o painel incluem turno da própria conversa, quando preenchido.

Follow-up proativo: 1–17 em ambas as rotas e 18 somente sem link; a 19 e a 20 não recebem novos lembretes. São preservadas as duas camadas de sete horas, os recibos, o encerramento no segundo lembrete e as guardas existentes. A reação ao primeiro segue a validação normal: um turno válido na 18 avança para 19 e é persistido. Contexto inválido genérico repete; tratamentos específicos continuam prioritários. Retomadas legadas são remapeadas por significado; a exceção 8 → 9 permanece.

Instalação existente exige migração própria: IDs antigos 18/19/20/21/22 tornam-se 20/21/22/23/24. Não executar setup ou seeds no banco de produção nem reaplicar migrações históricas. Preservar o Consumo Meta, seus fusos, worker, relatórios e PDFs, a compatibilidade PyWa 4.5.0, a exceção universal de idade 90+, o comentário livre e a despedida por participante.


## Coleta por campo na abertura (contrato 1)

Esta regra substitui, para novas conversas, a exigência de importação completa
FireAds. A primeira mensagem pode fornecer nome do titular, e-mail e destinatário
explícitos. Valores diferentes no mesmo campo ficam conflitantes; repetições
equivalentes são um único valor. O telefone é sempre o remetente WhatsApp.

Com os três campos aceitos, iniciar na profissão (etapa 4) sem consulta. Com
FireAds e coleta incompleta, consultar uma vez uma inscrição compatível; completar
somente o desconhecido a partir dessa inscrição. Sem FireAds, perguntar o que
falta. Nome pendente inicia na 1; destinatário pendente com nome conhecido inicia
na 2; nome e destinatário conhecidos iniciam na 4. E-mail pendente mantém a etapa
10 e sua política atual. Nome aceito na 1 com destinatário já coletado usa a nova
aresta autorizada 1 -> 4. Não antecipar profissão, idade ou dados do dependente.

Contexto próprio por conversa conserva candidatos, fonte de cada campo e dados
originais. Conversas e consultas legadas conservam o contrato antigo. Não
reinterpretar mensagens de conversas em andamento nem reconsultar por etapa.
Unidades sem FireAds preservam codigo_canal_venda da integração Funil (padrão
113340); a coleta não lhes atribui origem FireAds nem gera entrega ao dashboard.

Para formulário recebido no chat sem referência já vinculada, a entrega procura
telefone, e-mail e destinatário compatíveis e escolhe data/hora mais recente,
depois maior linha. Parentesco conhecido distingue inscrições para dependentes
diferentes. Ausência ou incompatibilidade gera nova linha preservando a origem.
Erro de leitura não autoriza criar. Salvar o destino antes do POST; retry mantém
esse destino e reconcilia primeiro o marcador técnico. Não substituir referência
vinculada apagada/alterada por uma inscrição nova. Somente Observação muda em
updates, preservando conteúdo anterior; append inclui Para quem é.
````

## Passo 31 — `PADROES_DE_ARQUITETURA.md`

Ação: **alterar**. Conteúdo completo abaixo.

SHA-256 anterior: `e6d2c4768d5c8512263afc451cd77567327ea33142cf7d7c36d256f889775292`.

SHA-256 proposto (UTF-8/LF): `1c911c9fd92221e7cae7aee8532dd4fda73cff47f2758188e5b30b1291257266`.

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

O `worker_flow` prepara `antes_do_primeiro_envio` depois das guardas finais e do
commit. Esse escopo síncrono executa a ação apenas quando um sender chama
`send_message` ou `request_contact_info`, uma vez no turno. Criar o cliente,
reconciliar uma resposta persistida ou resolver um contexto sem envio não ativa
o indicador. O escopo é restaurado mesmo sob exceção, sem tarefa auxiliar.
`digitacao.py` encapsula `indicate_typing` com sessão HTTP exclusiva, timeouts
curtos e sem retry; trata somente falhas da operação opcional. Não altera as
guardas, o transporte das respostas, o histórico, a fila ou o follow-up proativo.

Na abertura FireAds, também há sinalização após o commit da nova pendência no
flow e antes do HTTP no worker de consulta. `solicitar` informa se inseriu a
consulta; rechecagens não sinalizam. O repositório recupera a entrada aguardando
pela reserva vigente, com guardas de unidade, conversa, integração e prazo.
O worker encerra a transação antes do indicador, mantém a reserva compartilhada
e desconta esse custo do orçamento restante. Não há renovação periódica nem
novo estado persistido para os pontinhos. A consulta continua sem enviar respostas.

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

Os campos estruturados do formulário são extraídos em
`core/integrations/fireads/extratores.py`, sem usar validadores de respostas livres
do atendimento. O catálogo puro de pares de nomes compostos fica em
`core/validacoes/nomes_compostos.py`, compartilhado com o validador de nome do fluxo;
essa reutilização não muda as regras do validador. A interpretação de titular ou
dependente continua no contrato FireAds. Extratores não executam SQL ou HTTP e não
decidem etapas. O worker de consulta interpreta o registro; o flow aplica a decisão
persistida sob as mesmas guardas de conversa e transação.


## Contrato FireAds de aba única

`core/integrations/fireads/aba_geral.py` seleciona e relocaliza registros com
funções puras. O worker de consulta coordena HTTP e interpretação; o flow aplica
somente decisões persistidas. A referência do formulário fica no JSON da decisão
e do snapshot, sem SQL dentro de extratores ou montadores de texto.

`core/repositories/funil/snapshots.py` persiste o payload de todos os envios,
inclusive sem FireAds. O orquestrador confirma o snapshot antes do POST e revalida
reserva, pagamento, elegibilidade e URL nas tentativas seguintes. O dashboard
reutiliza as mesmas observações congeladas. Formatos legados são consumidos sem
reconstrução; configuração legada de consultas concluídas usa a ponte registrada
pela migração, sem repetir HTTP nem mudar uma decisão já salva.


## Coleta da primeira mensagem e dados parciais

`core/validacoes/coleta_abertura.py` extrai campos e mantém o contrato puro.
`core/integrations/fireads/coleta_abertura.py` cruza uma única inscrição externa.
`core/repositories/atendimento/coleta_abertura.py` persiste o JSON da conversa;
`workers/worker_flow/coleta_abertura.py` orquestra a abertura sem HTTP/commit.
O ciclo principal continua responsável pelas guardas, transações e envio.

`contexto_coleta` é independente de FireAds. O contrato 1 registra o estado por
campo e uma cópia imutável dos dados da primeira mensagem. Não usar cache ou
cadastro de outra conversa como fonte desses campos. As consultas reais usam a
fila existente; mensagem completa não cria consulta fictícia. Eventos históricos
`oferta_aceita_email_fireads` e `retorno_confirmado_email_fireads` conservam seus
nomes para replay, mas aceitam também e-mail previamente coletado nesta conversa.

Snapshots de entrega versão 3 acrescentam identidade de coleta e destino
persistido, sem mudar snapshots antigos. A escolha do alvo é feita na integração,
salva pelo repositório sob a reserva atual e confirmada pelo worker antes do POST.
As limitações da API externa entre leitura/escrita continuam as mesmas.
````

## Passo 32 — `tests/README.md`

Ação: **alterar**. Conteúdo completo abaixo.

SHA-256 anterior: `a42c8ad95e991cc166e0f9b970744264879a210770a070af3a168647ee9713a0`.

SHA-256 proposto (UTF-8/LF): `70be02de589d715632ed95fe2a1ef1e2bb2f1ed3e220864294e0947149020138`.

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

`test_indicador_digitacao.py` exercita o indicador com PyWa 4.5.0 real e HTTP
simulado: conta/entrada corretas, marcação de leitura, timeouts isolados, ausência
de retry e falhas opcionais que preservam a resposta e sua persistência. Cobre
abertura, continuação, retomada e replay de follow-up, três ativações na abertura
FireAds e rechecagens sem indicador, guardas, contexto inválido e limpeza do
escopo entre turnos/unidades. O indicador antes da consulta preserva seu orçamento
e falhas de HTTP não impedem salvar o resultado. Não acessa Meta, banco ou Redis
reais. A suíte de integração FireAds usa PostgreSQL local e indicador simulado
para conferir vínculos, reserva vigente e ausência de transação durante a chamada.
Verificação focada:

```bash
python -m unittest tests.unit.test_indicador_digitacao tests.unit.test_worker_flow_runtime tests.unit.test_pywa_compatibilidade tests.unit.test_followup tests.unit.test_fireads tests.unit.test_fireads_espera -q
```

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
e-mail importado da própria conversa, abertura na profissão, replay, tratamentos,
preservação das observações, e-mail de outro telefone e redirecionamento sem repetir POST.
Também verifica que um inline inválido da personalização impede o cadastro na Meta.

`unit/test_fireads_extratores.py` cobre nomes de perfil com complementos, catálogo
de compostos, fallback para a primeira palavra, e-mail sem revalidação estrutural,
campos vazios e destinatário desconhecido. A integração PostgreSQL cobre o registro
Meta, persistência da extração e retomada idempotente com o resultado salvo.

`unit/test_fireads_destino_dashboard.py` cobre a seleção da linha por telefone,
canal, destinatário explícito e maior `_row`, compatibilidade de snapshots antigos,
preservação dos demais campos, orgânicos e reconciliação antes de escolher outra
linha. HTTP e persistência são simulados. `unit/test_fireads_telefones.py` preserva
as máscaras e variantes do nono dígito também nessa seleção de destino.

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


## FireAds: aba única, referência da linha e snapshots do Funil

`unit/test_fireads_aba_geral.py` cobre filtro de canal antes da recência, empate
por linha, variantes de telefone, campos incompletos, origem Orgânico Site,
relocalização sem trocar o formulário, preservação das observações, marcadores
antigos/novos e cabeçalho/classificação compartilhados.

`integration/test_fireads_postgres.py` usa PostgreSQL local descartável e HTTP
simulado. Inclui migração completa com pendências/resultados legados e reexecução,
URLs anteriormente alteradas, prazo preservado, reservas concorrentes, rollback,
pagamento, contexto por conversa, histórico por chat/unidade, conflito de e-mail
com referência preservada e retry do payload do Funil com e sem FireAds.

Verificação unitária focada (sem rede/produção):

```sh
python -m unittest tests.unit.test_fireads_aba_geral tests.unit.test_fireads tests.unit.test_fireads_espera tests.unit.test_fireads_extratores tests.unit.test_fireads_telefones tests.unit.test_fireads_destino_dashboard tests.unit.test_worker_flow_runtime tests.unit.test_sondas_funil -q
```

Para integração, fornecer `FIREADS_TEST_DSN` apontando exclusivamente para banco
vazio `test_chatbot_fireads` em loopback. A suíte recusa schema `chatbot`
preexistente. Não usar credenciais do banco da aplicação.


## Coleta por campo na abertura

`python -m unittest tests.unit.test_coleta_abertura -q` cobre as oito combinações
de campos, conflitos, nomes compostos, fontes, recência e escolha de destino.
`tests.integration.test_coleta_abertura_postgres` usa FIREADS_TEST_DSN exclusivamente
em loopback, banco descartável test_chatbot_fireads sem schema chatbot preexistente.
O teste recusa outros destinos; usa o SQL real e substitui serviços externos.
Não fornecer credenciais de produção aos testes.
````

## Passo 33 — `deploy/migrations/20261019_coleta_abertura.sql`

Ação: **criar**. Conteúdo completo abaixo.

SHA-256 anterior: `arquivo novo`.

SHA-256 proposto (UTF-8/LF): `87ef26f7513a490eafb856ab393e2edb666d24ff53a5c76eaa627c780313c9ca`.

**Passo final: salvar este arquivo e executar o bloco inteiro no DBeaver somente no deploy coordenado.**

```sql
-- Executar inteiro no DBeaver, com webhook e TODOS os workers parados.
-- Exige a migração 20261014_fireads_aba_geral_v1. Não chama serviços externos.
BEGIN;
SET LOCAL lock_timeout = '5s';
SET LOCAL statement_timeout = '120s';

-- INICIO DDL COLETA ABERTURA
DO $migracao$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM chatbot.migracoes_fireads WHERE versao='20261014_fireads_aba_geral_v1') THEN
        RAISE EXCEPTION 'Aplicar primeiro a migração da aba geral.';
    END IF;
    LOCK TABLE chatbot.conversa, chatbot.etapa_transicao, chatbot.migracoes_fireads IN ACCESS EXCLUSIVE MODE;
    IF EXISTS (SELECT 1 FROM chatbot.migracoes_fireads WHERE versao='20261019_coleta_abertura_v1') THEN
        RAISE NOTICE 'Coleta por campo já migrada; nenhum atendimento reprocessado.';
        RETURN;
    END IF;
    ALTER TABLE chatbot.conversa ADD COLUMN contexto_coleta JSONB NULL;
    ALTER TABLE chatbot.conversa ADD CONSTRAINT ck_conversa_contexto_coleta CHECK (
        contexto_coleta IS NULL OR COALESCE((
            jsonb_typeof(contexto_coleta)='object'
            AND contexto_coleta->>'versao'='1'
            AND contexto_coleta->>'id_conversa'=id_conversa::text
            AND jsonb_typeof(contexto_coleta->'campos')='object'
            AND jsonb_typeof(contexto_coleta->'mensagem_original')='object'
            AND contexto_coleta->>'status' IN ('preparando','aguardando_consulta','pronto')
            AND (contexto_coleta->>'status'<>'pronto' OR contexto_coleta->>'etapa_inicial' IN ('1','2','4'))
        ), FALSE)
    );
    -- Preserva os IDs e o mapa atual. A aresta adicional só é usada com destino coletado.
    IF EXISTS (SELECT 1 FROM chatbot.etapa_transicao WHERE id_etapa_origem=1
               AND (evento='nome_cliente_valido_destino_coletado' OR id_etapa_destino=4)
               AND NOT (evento='nome_cliente_valido_destino_coletado' AND id_etapa_destino=4)) THEN
        RAISE EXCEPTION 'Aresta 1 -> 4 conflita com o mapa existente.';
    END IF;
    INSERT INTO chatbot.etapa_transicao(id_etapa_origem,evento,id_etapa_destino)
    VALUES (1,'nome_cliente_valido_destino_coletado',4)
    ON CONFLICT (id_etapa_origem,evento) DO NOTHING;
    INSERT INTO chatbot.migracoes_fireads(versao) VALUES ('20261019_coleta_abertura_v1');
END $migracao$;
-- FIM DDL COLETA ABERTURA

COMMIT;
SELECT EXISTS (SELECT 1 FROM chatbot.migracoes_fireads WHERE versao='20261019_coleta_abertura_v1') AS migracao_ok,
       EXISTS (SELECT 1 FROM chatbot.etapa_transicao WHERE id_etapa_origem=1
               AND evento='nome_cliente_valido_destino_coletado' AND id_etapa_destino=4) AS transicao_ok,
       (SELECT COUNT(*) FROM chatbot.conversa WHERE contexto_coleta IS NOT NULL) AS conversas_com_coleta;
```
