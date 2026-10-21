from pathlib import Path
import ast
import hashlib
import json
import subprocess

HERE = Path(__file__).parent
BASE = HERE.parents[1]
ROOT = HERE / 'candidate'
paths = json.loads((HERE / 'changes.json').read_text(encoding='utf-8'))
migration = 'deploy/migrations/20261019_coleta_abertura.sql'
paths = [p for p in paths if p != migration] + [migration]
sha = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=BASE, text=True).strip()

intro = f'''# Plano prático — coleta de dados parciais na abertura

Status: código proposto para aplicação coordenada. Este documento contém os
arquivos completos; a aplicação no projeto e a migração de produção são tarefas
posteriores. Revisão-base: `{sha}`. Documento consolidado em 20/10/2026.

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

{(HERE / 'validacao.md').read_text(encoding='utf-8') if (HERE / 'validacao.md').exists() else 'Validação em andamento na cópia de preparação. Este estado será atualizado antes da entrega.'}

## Índice dos arquivos

'''
pieces = [intro]
for i, p in enumerate(paths, 1):
    pieces.append(f'{i}. `{p}` — {"alterar" if (BASE / p).exists() else "criar"}.\n')
for i, p in enumerate(paths, 1):
    content = (ROOT / p).read_text(encoding='utf-8').rstrip() + '\n'
    if p.endswith('.py'):
        ast.parse(content, filename=p)
    old = (BASE / p).read_bytes() if (BASE / p).exists() else None
    sha_old = hashlib.sha256(old).hexdigest() if old else 'arquivo novo'
    sha_new = hashlib.sha256(content.encode('utf-8')).hexdigest()
    lang = 'python' if p.endswith('.py') else ('sql' if p.endswith('.sql') else 'markdown')
    fence = '````' if '```' in content else '```'
    pieces.append(f'\n## Passo {i} — `{p}`\n\n')
    pieces.append(f'Ação: **{"alterar" if old else "criar"}**. Conteúdo completo abaixo.\n\n')
    pieces.append(f'SHA-256 anterior: `{sha_old}`.\n\nSHA-256 proposto (UTF-8/LF): `{sha_new}`.\n\n')
    if p == migration:
        pieces.append('**Passo final: salvar este arquivo e executar o bloco inteiro no DBeaver somente no deploy coordenado.**\n\n')
    pieces.append(f'{fence}{lang}\n{content.rstrip()}\n{fence}\n')

output = BASE / 'docs/valida_dados_parciais_fireads.md'
output.write_text(''.join(pieces), encoding='utf-8', newline='\n')
print(json.dumps({'arquivo': str(output), 'passos': len(paths), 'linhas': len(output.read_text(encoding='utf-8').splitlines()), 'bytes': output.stat().st_size}))
