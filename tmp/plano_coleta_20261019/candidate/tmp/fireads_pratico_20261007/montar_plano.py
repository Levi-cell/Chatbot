from editar import *
import hashlib
import json
import re

docs=ROOT/'docs'
original=docs/'integracao_fireads.md'
requisitos=docs/'integracao_fireads_requisitos.md'
if not requisitos.exists():
    requisitos.write_text(original.read_text(encoding='utf-8-sig'),encoding='utf-8')

arquivos=[]
for path in DEST.rglob('*'):
    if not path.is_file() or path.suffix not in ('.py','.sql') or '__pycache__' in path.parts:
        continue
    relative=path.relative_to(DEST).as_posix()
    old=ROOT/relative
    code=path.read_text(encoding='utf-8-sig')
    if old.exists() and old.read_text(encoding='utf-8-sig')==code:
        continue
    arquivos.append(relative)

sql='deploy/migrations/20261007_fireads_chat_customizacao.sql'
def ordem(path):
    if path==sql:return (99,path)
    for i,prefix in enumerate(('core/integrations/fireads','core/repositories/fireads','workers/worker_flow/fireads',
        'core/repositories/atendimento/conversas','core/repositories/fluxo','core/integrations/whatsapp',
        'workers/worker_flow','core/repositories/funil','core/integrations/funil','workers/worker_funil',
        'core/repositories/atendimento/followup','core/repositories/monitoramento','utilitarios/reports_functions',
        'callback/webhook/models','callback/webhook/admin','core/database','tests/')):
        if path.startswith(prefix):return (i,path)
    return (90,path)
arquivos.sort(key=ordem)

introducao='''# Plano prático — FireAds, chat e atendimento customizado

**Revisão: 08/10/2026. Status: preparado para revisão e aplicação futura.**

Este documento contém o código integral de **{total} arquivos**, um por passo.
O último passo contém a migração SQL completa para executar no DBeaver no dia
do deploy. Os códigos foram preparados e testados em uma cópia isolada; a
aplicação em uso, o RDS, a Meta, o Funil e o dashboard não foram alterados por
esta preparação. Não basta alterar o Python sem executar a migração correspondente.

Base: **V1.9.2 — 395d1eb0321507cdc67d92e93b4ebe530bd57915**, considerando também
o conteúdo local dos arquivos no momento desta revisão. Os arquivos que já
existem devem ser substituídos integralmente pelos blocos abaixo somente na
fase autorizada de aplicação. Arquivos novos devem ser criados nos caminhos
indicados. Os caminhos são relativos à raiz do repositório.

O histórico detalhado das decisões permanece em
[Requisitos e decisões FireAds](integracao_fireads_requisitos.md). Para a
implementação, prevalecem os contratos concretos deste plano. Não implementar
envio pelo webhook `organicosupera`, exclusão de leads, pesquisa de origem Meta
por anúncio/post ou IA nesta entrega.

## Comportamento contemplado

- Todas as unidades passam a ter chats: um vínculo único entre cliente e unidade,
  com várias conversas ao longo do tempo. A regra de uma conversa ativa permanece.
- Unidades sem FireAds continuam começando pela pergunta do nome. Não importam
  dados nem geram entrega no dashboard; sua origem FireAds fica nula.
- Cada nova conversa de uma unidade com FireAds ativa consulta somente Google
  e Meta 7.2 antes da primeira resposta. Conversas anteriores à ativação não
  recebem importação retroativa. Nenhuma consulta é feita a cada mensagem.
- O contato é localizado pelo telefone recebido no WhatsApp. O registro mais
  recente fornece, em conjunto, nome do titular, e-mail e destinatário. Nome
  composto usa o validador existente. Faixa etária, objetivo e demais perguntas
  do formulário não preenchem coletas. Não há mais expiração de 30 dias.
- Importação completa começa na **etapa 4, profissão**, com apresentação própria.
  Essa primeira mensagem também é registrada na etapa 4, para que o retry não
  simule uma transição 1 → 4. Idade exata, dependente, oferta e triagem continuam
  sujeitos às regras atuais. Após aceitar a oferta nas etapas 7 ou 9, o e-mail
  daquela importação permite seguir à 11; e-mail antigo no cadastro não autoriza isso.
- Ausência, falha de uma fonte, resposta incompleta, ambiguidade ou dados inválidos
  resultam em atendimento orgânico completo. A classificação concluída é
  preservada para esta conversa, mesmo se o formulário aparecer depois.
- Ao atingir a elegibilidade atual, o Funil recebe o canal correspondente:
  **Google 113336, Meta 113340, orgânico 113481**. O texto de observações e o
  campo personalizado de origem informam a mesma classificação. Google inclui
  os registros daquela aba, inclusive landing page; não é prova de clique pago.
- Antes da primeira tentativa de Funil, o conteúdo da entrega é congelado.
  Depois do sucesso no Funil, uma fila separada cuida do dashboard. Falha do
  dashboard não provoca reenvio de uma oportunidade já confirmada no Funil.
- Toda escrita consulta a aba geral novamente. Contato existente: altera
  **somente Observação**, preservando integralmente o texto anterior e acrescentando
  abaixo o bloco do chatbot. Ausente: cadastra os campos disponíveis. Isso
  também vale para orgânico que já esteja na aba geral por outro atendimento.
- O bloco usa marcadores estáveis por integração e conversa. Retry reconhece o
  mesmo bloco; uma nova conversa acrescenta outro. Preservam-se `FR002`, `0`,
  anotações, espaços e conteúdo anterior. Não há truncamento silencioso.
- Cadastro não envia Data/Hora; a FireAds a define. Update não modifica a data.
  `url_operation` guarda apenas a referência do editor; GET e POST usam `/exec`.

## Banco e responsabilidades dos campos

| Estrutura | Conteúdo e finalidade |
| --- | --- |
| `unidade` | Identidade, CNPJ, contato administrativo, WABA, phone ID, pagamento, usuário de monitoramento e fuso Meta. Mantém seus IDs. |
| `atendimento_customizado` | Um registro obrigatório por unidade: agente, gênero, comercial, limite de suporte por idade, obrigatoriedade do e-mail, link de reserva, Instagram e BPA. A migração copia e confere os valores antes de retirar as colunas antigas. |
| `unidade_atendimento` | **View de leitura**, não outra tabela. Une unidade e personalização para manter o formato das consultas do fluxo, follow-up, painel, Funil e relatórios. |
| `integracao_fireads` | Zero ou um registro por unidade. Ativação, URLs, abas, confirmação do contrato e fuso de interpretação de datas. Começa desativada; ausência equivale a não integrada. |
| `chat` | `id_chat`, cliente, unidade e criação. Cliente/unidade únicos. A migração agrupa as conversas existentes sem apagar nenhuma. |
| `conversa.id_chat` | Obrigatório. FK composta garante que chat, cliente e unidade correspondem; os IDs diretos continuam presentes nesta fase. |
| `conversa.origem_fireads` | `google`, `meta`, `organico` ou `NULL`. Decisão daquela conversa; não derivar de outra conversa nem da aba geral. |
| `conversa.contexto_fireads` | JSON da decisão e das coletas aceitas: resultado, origem, consulta, integração, conversa, destinatário e retrato do titular. Preserva nome, idade e e-mail históricos usados no Funil. Nunca contém todas as linhas recebidas da planilha. |
| `conversa.lead_no_dash` | `NULL`: entrega não materializada/não aplicável. `FALSE`: entrega pendente. `TRUE`: escrita confirmada ou bloco exato reconciliado no destino. Não indica se o formulário foi encontrado na abertura. |
| `consulta_fireads` | Um registro atual por chat integrado: conversa de referência, integração, resultado, JSON da consulta, conclusão e horário. Atualiza na próxima conversa; o retrato histórico continua na conversa anterior. |
| `envios_dash` | Uma entrega por conversa, snapshot imutável, status, tentativas, próxima tentativa, reserva, erro, recibo e horários. Só é processada após `lead_no_funil=TRUE`. |
| `migracoes_fireads` | Controle técnico da aplicação desta migração, permitindo reexecução sem copiar novamente os dados. |

Resultados de consulta: `pendente`, `importado`, `ausente`, `incompleto`,
`ambiguidade` ou `erro`. `consulta_concluida` distingue a consulta reservada da
decisão já confirmada. O JSON `dados` guarda o resultado desta consulta; o JSON
da conversa também inclui os IDs e as coletas posteriores aceitas no fluxo.
Essa forma concreta substitui a enumeração preliminar de colunas de consulta.

Status da entrega: `pending`, `processing`, `sent`. A reserva dura três minutos;
um erro libera a tentativa para **30 minutos depois**, sem novo POST no mesmo
ciclo. O worker continua com sua cadência atual de 30 minutos; conforme o momento
da falha, a tentativa pode ocorrer em um ciclo posterior. Os lotes Funil e Dash
têm limite próprio de 100, usando o mesmo worker. O contador de tentativa impede
um processamento antigo de confirmar uma reserva mais nova. Um lock de sessão
serializa os envios deste sistema ao mesmo telefone/integração durante o HTTP.

## Contratos e decisões conservadoras

O adaptador atual aceita exatamente os campos e valores explícitos registrados
nos requisitos. Campos antigos `Adulto`, `Criança`, `Adolescente` e faixas etárias
não comprovam titular/dependente. Valores novos inesperados geram orgânico e
diagnóstico; não são convertidos por adivinhação. O telefone é normalizado com
país/DDD/formatação e comparado exatamente. Não há aproximação automática do
nono dígito nem fusão de contatos por semelhança.

Havendo mais de um candidato, as datas precisam ser comparáveis. Offset recebido
da Meta é respeitado. Data Google sem offset usa `fuso_formularios`; se não for
conhecido, não há escolha arbitrária entre registros. Uma correspondência única
com três dados válidos pode ser aproveitada sem inventar sua data. Empate é
tratado conservadoramente como ambiguidade, mesmo entre cópias equivalentes.

Na escrita, múltiplas linhas com o mesmo telefone, e-mails conflitantes ou e-mail
já associado a outro telefone mantêm a entrega pendente para revisão. Não se
cria outra linha silenciosamente para contornar uma identidade ambígua. Falta
da coluna/valor de Observação na leitura também impede a atualização.

O endpoint fornecido não tem comparação atômica do texto anterior nem chave de
idempotência no servidor. A consulta antes do POST e os marcadores reduzem
duplicação, mas não eliminam corrida com edição/ordenação externa da planilha.
O `_row` é obtido da aba geral consultada naquela tentativa, nunca das abas de
origem. Mudança externa entre leitura e gravação ainda é uma limitação deste
contrato. Para eliminar essa janela, a FireAds precisaria de operação atômica
por identidade + versão/bloco. Não apresentar este plano como garantia absoluta
de ausência de duplicações externas.

O texto do bloco vem do mesmo payload congelado enviado ao Funil. A célula
inteira pode ser maior porque preserva conteúdo anterior. Mudança manual no
bloco da mesma conversa não é sobrescrita: exige revisão. O limite operacional
de composição é 45.000 caracteres; excedê-lo mantém a pendência.

HTTP 200 sozinho não confirma sucesso. Conferir `success`, aba e recibo da
operação. Redirecionamento do POST é lido por GET no domínio Google autorizado,
sem repetir o POST. Requisições de abertura compartilham orçamento de 25 segundos
e entrega de 40 segundos; falha na abertura usa orgânico. Esses orçamentos são
checados também após a resposta. Timeouts de conexão/leitura não equivalem a
cancelamento remoto; por isso a posse da fila/conversa é conferida após a consulta
e a entrega desconhecida espera outro ciclo antes de reconsultar o destino.

## Validação desta preparação

- Verificação de sintaxe de todos os arquivos Python da cópia candidata.
- Verificação Django de models e Admin: sem problemas encontrados.
- Suíte de regressão: **476 testes descobertos, 419 executados sem falhas e 57
  pulados** por exigirem DSNs explícitos de PostgreSQL descartável.
- Depois da revisão do histórico da abertura importada, teste adicional confirma
  registro inicial na etapa 4 e retry sem novo envio. Lote dirigido de 48 testes
  passou, incluindo esse caso. Não foi necessário repetir testes de relatórios/login.
- Migração executada em PostgreSQL WASM/PGlite local descartável: cópia da
  personalização, preservação de conversas, agrupamento por chat, 30 transições,
  reexecução, ativação controlada e constraints conferidos.
- **24 consultas reais extraídas dos repositórios candidatos** executadas nesse
  banco: consulta/importação, snapshot, início na profissão, leitura do lead,
  congelamento, reserva, reagendamento e conclusão do dashboard.
- Nenhuma chamada real de envio à Meta, ao Funil ou à FireAds; os testes HTTP usam
  respostas simuladas do contrato fornecido. Nenhuma migração executada no RDS.

A execução PostgreSQL WASM valida SQL e dados em uma instância local, mas não
simula múltiplas sessões PostgreSQL concorrentes nem permissões/latência do RDS.
Conferir esses aspectos no ensaio de deploy antes de ativar a integração. Os
57 testes pulados não estão sendo apresentados como aprovados.

## Aplicação e ativação no dia do deploy

Preparar todos os arquivos e revisar o diff antes da implantação. Se o código
base tiver mudado, reconciliar as mudanças com a tabela de hashes abaixo; não
substituir arquivos novos por uma cópia antiga sem revisão. Durante o deploy,
parar os serviços que usam essas tabelas, atualizar o código, executar **inteiro**
o SQL do último passo com a mesma role proprietária do schema usada pelo projeto,
conferir o resultado e só então iniciar os serviços. Não usar `setup_database_aws`
em produção para migrar: ele contém seeds e reset de cache próprios do setup.

O SQL conserva os registros e seus IDs, move a configuração e cria as estruturas.
Não cria uma integração ativa por suposição de ID. No Admin, cadastrar a
integração **somente para Santo André**, selecionando a unidade pelo nome:

- `url_dashbord`: `https://script.google.com/macros/s/AKfycbxnwj1DsFD6qqihceO2F4b-YRBe3nXwQ70SjWb45LtUVOzrRxMo6nHqKlvNC53EDOLX/exec`.
- `url_operation`, referência opcional: `https://script.google.com/u/0/home/projects/1CVzuDR9S6N1EBc31kr7Eq-6N6URrcwmUyXyc0xmUVmYRC5lOOhtOJhij/edit`.
- Manter os defaults das abas Google, Meta 7.2 e LEADS GERAL.
- Conferir uma submissão do Google atualizado no retorno da API. O print confirma
  as opções, mas a leitura anterior ainda continha apenas os valores antigos.
  `contrato_validado` só deve ser marcado após essa conferência.
- Confirmar o fuso configurado na planilha. O relato de exibição **23:05** e a
  hipótese de Brasília não confirmam o fuso IANA. Se confirmado, preencher
  `America/Sao_Paulo`; enquanto desconhecido, manter nulo. Isso não altera datas externas.
- Conferir que a sincronização antiga Funil → Dash da agência continua desligada,
  mantendo apenas a captação dos formulários. Habilitar `integracao_ativa` depois
  dessas conferências; `ativada_em` é preenchido automaticamente pelo banco.

Revisar uma rota orgânica, uma importada para titular e outra para dependente,
incluindo unidade com/sem link, fechamento por idade, follow-up, retry e canais
de venda. Uma ativação não muda conversas que já começaram. Desativar a integração
interrompe novas consultas/escritas e preserva snapshots/pendências; não elimina
os dados já importados de uma conversa. Se a URL/aba mudar enquanto houver entrega
congelada, ela fica pendente, evitando enviar dados a um destino diferente.

O plano de IA reutilizará o `chat` criado aqui. As tabelas de uso da IA, modelos,
orçamentos, manual e operações de IA continuam fora desta entrega.

## Índice e conferência da base

Hash de base é SHA-256 do arquivo local antes da aplicação; `novo` indica criação.
O conteúdo de cada bloco é completo, não um diff. Preserve o restante do projeto.

| Passo | Arquivo | SHA-256 da base |
| --- | --- | --- |
'''.replace('{total}',str(len(arquivos)))

manifest=[]
for i,p in enumerate(arquivos,1):
    old=ROOT/p
    baseline=hashlib.sha256(old.read_bytes()).hexdigest() if old.exists() else 'novo'
    code=read(p)
    manifest.append({'passo':i,'arquivo':p,'sha256_base':baseline,'sha256_codigo':hashlib.sha256(code.encode()).hexdigest()})
    introducao+=f'| {i} | `{p}` | `{baseline}` |\n'

parts=[introducao]
for item in manifest:
    p=item['arquivo']; code=read(p); lang='sql' if p.endswith('.sql') else 'python'
    action='Criar' if item['sha256_base']=='novo' else 'Substituir integralmente'
    heading=f"\n## Passo {item['passo']} — {action} `{p}`\n\n"
    if p==sql:
        heading+='**Último passo — migração SQL para o DBeaver.** Executar o bloco inteiro na janela de deploy descrita acima. Qualquer erro deve abortar a transação; não continuar apenas pelos comandos posteriores.\n\n'
    fence='````' if '```' in code else '```'
    parts.append(heading+fence+lang+'\n'+code.rstrip()+'\n'+fence+'\n')

texto=''.join(parts)
original.write_text(texto,encoding='utf-8')
(DEST.parent/'manifesto.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
# Verify every embedded full file, the final SQL and Markdown fences.
for item in manifest:
    assert read(item['arquivo']).rstrip() in texto,item['arquivo']
assert arquivos[-1]==sql
validate()
print(json.dumps({'arquivos':len(manifest),'linhas':len(texto.splitlines()),'bytes':len(texto.encode()),'ultimo_passo':sql},ensure_ascii=False))
