# Aplicativos Django: webhook e monitoramento

Projeto Django que reúne o webhook e o aplicativo de monitoramento por unidade.
O webhook recebe eventos da Meta, valida a entrada e persiste mensagens aceitas
na fila. O processamento da conversa pertence ao worker. O monitoramento oferece
login com autenticação Django, autorização por unidade, consulta responsiva de
conversas e indicadores, além da exportação de contatos.

Documentos centrais:

- [Regras de negócio](../REGRAS_DE_NEGOCIO.md)
- [Padrões de arquitetura](../PADROES_DE_ARQUITETURA.md)
- [Portal do projeto](../README.md)

## Estrutura

```text
callback/
├── callback/              configuração Django
├── webhook/
│   ├── admin.py           operações administrativas
│   ├── models.py          mapeamento das tabelas
│   ├── urls.py            rota /webhook
│   ├── views.py           borda GET/POST
│   └── services/          fluxo HTTP e anti-flood
├── monitoramento/        aplicativo do painel por unidade
│   ├── __init__.py
│   ├── apps.py           registro MonitoramentoConfig
│   ├── forms.py          credenciais nativas e autorização antes do login
│   ├── views.py          login, saída, painel, APIs de leitura e CSV
│   ├── urls.py           rotas públicas e privadas do monitoramento
│   ├── monitoramento_guard.py  autorização da sessão e dos recursos
│   ├── periodos.py       janelas de consulta aceitas pelo servidor
│   ├── apresentacao.py   consolidação, perfis, botões e CSV Google/essencial
│   ├── services.py       orquestra leituras da unidade autorizada
│   ├── templates/monitoramento/  login, painel e acesso negado
│   └── static/monitoramento/     estilos, interação e logo ESL Tech
│       ├── css/
│       ├── js/
│       └── img/
└── manage.py
```

Arquivos principais de `services`:

- `post_flow.py`: validações e transação da fila;
- `meta_signature.py`: assinatura `X-Hub-Signature-256`;
- `bloqueio_meta_guard.py`: consulta da lista local de bloqueio, promoção de
  suspeita e nova tentativa de bloqueio na Meta;
- `flood_guard.py`: Redis, banco, memória e bloqueio Meta;
- `populating_fila_mensagens.py`: parse e inserção usando cursor recebido;
- `alerta_flood_memoria.py`: alerta local quando banco e Redis falham.

## Endpoint

```text
GET  /webhook
POST /webhook
```

A rota não possui barra final. O `GET` atende à verificação inicial da Meta. O
`POST` recebe eventos reais.

O `GET` devolve `hub.challenge` quando `hub.mode=subscribe` e
`hub.verify_token` coincide com `META_WEBHOOK_VERIFY_TOKEN`; nos demais casos,
devolve `Webhook ativo` com HTTP 200.

O limite do body é configurado por `WEBHOOK_MAX_BODY_BYTES` (padrão: 256 KiB).
Quando `META_WEBHOOK_SIGNATURE_REQUIRED=true`, o POST exige HMAC-SHA256 do body
original, calculado com `META_APP_SECRET` e comparado com
`X-Hub-Signature-256` por `hmac.compare_digest`. Secret vazio, header ausente ou
assinatura inválida resultam em 403. O padrão dessa flag no código é `False`;
a exigência efetiva depende da configuração do ambiente.

## Ordem do POST

```text
Content-Type
-> tamanho do body
-> assinatura Meta
-> parse JSON
-> classificação do evento Meta
-> lista local de bloqueio / suspeita de bot
-> anti-flood
-> unidade ativa
-> conversa bloqueada
-> preparação da mensagem
-> transação da fila
-> resposta HTTP
```

O webhook não envia etapas, não avança conversa e não executa dequeue.
O follow-up é disparado pelo worker próprio após consulta de inatividade; não
exige um evento recebido nem cria uma entrada fictícia na fila. A reação real
do cliente passa pelas mesmas barreiras de assinatura, bloqueio, flood e turno.

Eventos contendo apenas `statuses` retornam 200 sem processamento na V1.
Eventos sem `messages`/`statuses`, ou com ambos, também retornam 200 sem
enfileirar. Esses descartes ocorrem antes dos controles de bloqueio e flood.

## Contrato HTTP

| Cenário | HTTP | Resultado |
|---|---:|---|
| Mensagem inserida | 200 | `status=ok` |
| Descarte por regra de negócio | 200 | `status=ignored` ou `status=ok`, conforme o ponto do fluxo |
| JSON inválido | 200 | `status=ignored`, `reason=invalid_json` |
| Falha de conexão, inserção ou commit da fila | 503 | `status=unavailable`, `reason=insert_exception` |
| Falha ao confirmar a unidade no banco após cache sem resposta conclusiva | 503 | `status=unavailable`, `reason=unit_validation_unavailable` |
| Falha de Redis e banco ao validar bloqueio de conversa | 503 | `status=unavailable`, `reason=conversation_block_validation_unavailable` |
| Falha na consulta ou promoção da lista local de bloqueio | 503 | `status=unavailable`, `reason=blocklist_validation_unavailable` |
| Flood detectado sem conseguir consultar ou persistir o bloqueio local | 503 | `status=unavailable`, `reason=flood_<origem>_banco_indisponivel` ou `flood_<origem>_persistencia_local_falhou` |
| Erro inesperado identificável, nas três primeiras ocorrências por WAMID | 503 | `status=unavailable`, `reason=unexpected_error_retry`, com `attempt` |
| Erro inesperado com limite esgotado ou contador indisponível | 200 | `status=ignored`, `reason=unexpected_error_retry_exhausted` ou `unexpected_error_retry_unavailable` |
| Assinatura inválida | 403 | `status=forbidden` |
| Payload grande | 413 | `status=payload_too_large` |
| `Content-Type` inválido | 415 | `status=unsupported_media_type` |
| `Content-Length` inválido | 400 | `status=bad_request` |
| Método não permitido | 405 | `status=method_not_allowed` |

Turno ocupado, duplicidade, unidade inativa, conversa bloqueada e flood com
bloqueio local persistido são descartes com HTTP 200. Falhas operacionais de
validação ou persistência usam os motivos 503 acima. Em motivos de flood,
`<origem>` é `redis`, `banco` ou `memoria`.

O limite de três respostas 503 aplica-se somente ao tratamento genérico de
erro inesperado, com contador Redis por WAMID e TTL de sete dias renovado a cada
ocorrência. Sem WAMID ou sem Redis, esse tratamento retorna 200 com
`unexpected_error_retry_unavailable`; os demais cenários 503 não passam por
esse contador.

## Turno e duplicidade

O par lógico é:

```text
cliente_telefone + id_phone_unidade
```

`core/repositories/seguranca/turno_cliente.py` usa advisory lock transacional para impedir
corridas. Enquanto existir fila aberta sem resposta própria do bot, mensagens
posteriores do mesmo par são descartadas.

Mensagens com timestamp anterior a uma interação já registrada também são
descartadas como reentregas fora de ordem. Se todas as filas abertas já têm sua
própria resposta do bot com `status_envio=sent`, o turno pode ser liberado.

`id_hash_msg` é único. Reentregas da Meta não criam duas linhas; o insert utiliza
`ON CONFLICT DO NOTHING`.

## Anti-flood

A regra atual mede cada cliente dentro de cada unidade:

```text
15 WAMIDs distintos em 5 segundos
chave = wa_id_cliente + phone_id_unidade
```

Clientes diferentes da mesma unidade não compartilham contador. A ordem dos
fallbacks é Redis, banco e memória local. No Redis, deduplicação por WAMID e
incremento são atômicos, com janela fixa e deduplicação por duas horas.

O bloqueio utiliza `core/integrations/whatsapp/tools/usuarios.py`. O fluxo
persiste a intenção em `chatbot.cliente_bloqueado_meta` antes de chamar a Meta.
Se a Meta falhar, mantém o bloqueio local e descarta a mensagem com HTTP 200;
uma nova mensagem desse par tenta bloquear na Meta novamente. Se o banco
impedir a persistência, retorna 503 sem chamar a Meta. Unidade não cadastrada
é descartada sem bloqueio externo.

Antes do anti-flood, `bloqueio_meta_guard.py` verifica essa lista local e
também promove conversas que atingiram o limite de turnos sem avanço. A
promoção é confirmada no banco antes da chamada externa.

Relatórios e reconciliação manual ficam em
`utilitarios/monitoring/blocked_users.py`.

O relatório é somente leitura e possui duas conferências distintas:

- bloqueios: compara
  `(waba_id, phone_id_unidade, wa_id_cliente)` entre a lista da Meta e
  `chatbot.cliente_bloqueado_meta`;
- registros Cloud API: percorre o `waba_id` de cada unidade e compara os
  `phone_number_id` retornados pela Meta com `chatbot.unidade`.

Ele também separa falhas de coleta e vínculos divergentes; não bloqueia,
desbloqueia, registra ou remove dados automaticamente.

## Transações

`post_flow.py` é dono da conexão usada para enfileirar:

```text
abrir conexão -> povoando_fila -> commit/rollback -> close
```

`populating_fila_mensagens.py` recebe cursor e não controla conexão.

As transações independentes do anti-flood pertencem a `flood_guard.py`; a
consulta e promoção da lista local pertencem a `bloqueio_meta_guard.py`. Essa
separação está detalhada em
[Padrões de arquitetura](../PADROES_DE_ARQUITETURA.md).

## Django Admin

O Admin é majoritariamente somente leitura. As exceções operacionais são:

- criação, edição e exclusão individual de unidade;
- criação, edição e exclusão de configuração de integração do Funil por unidade;
- desbloqueio individual de cliente bloqueado na Meta.

Cada unidade exige `nome_unidade`, `nome_agente` e `genero`. O campo `genero`
oferece no formulário somente `Masculino` e `Feminino`; ele controla o artigo
usado para apresentar o agente nos inícios padrão, de mídia, financeiro e de
tratamento de reforço escolar da etapa 1.

`waba_id` e `phone_number_id` ficam somente leitura após a criação. O Admin
também expõe `idade_minima_suporte` e `email_obrigatorio`. O seletor de suporte
aceita Desativado, 50+, 60+, 70+, 80+ e 90+; ativar exige um `numero_comercial`
brasileiro válido, inclusive ao editar ou remover o número de uma unidade ativa.
Somente o titular é alcançado; o limite não altera a dispensa de e-mail dos 60+.

No Admin, criação/exclusão de unidade e desbloqueio individual seguem
Meta-first. Se a Meta falhar, a alteração local correspondente não é
confirmada. Se a Meta concluir e uma etapa local posterior falhar, a operação
externa não é compensada automaticamente: a unidade exige conferência manual.
O desbloqueio também zera `turnos_sem_avanco` das conversas ativas do par.
Essa ordem administrativa é diferente do bloqueio preventivo do webhook,
que persiste primeiro a lista local.

## Cadastro e autorização do monitoramento

O modelo `Unidade`, com `managed = False`, inclui `id_usuario_monitoramento`,
um `OneToOneField` opcional para o usuário do Django. No Admin da unidade,
**Usuário de monitoramento** seleciona uma conta comum criada em **Usuários**.
Uma conta não pode ser vinculada a duas unidades; várias unidades podem ficar
sem conta. Excluir o usuário limpa o campo com `SET_NULL` e preserva a unidade.
O formulário permite contas inativas para preparar o cadastro, mas elas não
passam pela autorização. A edição mantém o fluxo administrativo existente da
unidade; o vínculo de acesso é consultado diretamente no banco, sem cache.
As regras completas estão em [Regras de negócio, 19.6](../REGRAS_DE_NEGOCIO.md#196-contas-de-monitoramento-por-unidade).

O aplicativo `monitoramento` está registrado por
`monitoramento.apps.MonitoramentoConfig` em `callback/settings.py`. As rotas são
incluídas no URLconf do projeto; `STATIC_URL=/static/` permite carregar os assets
também nas URLs aninhadas. O login não cria tabelas nem migrações adicionais.

`monitoramento/monitoramento_guard.py` oferece
`exigir_acesso_monitoramento(request, id_conversa=..., id_mensagem=...)`.
Somente `request.user.pk` identifica a conta. Os identificadores dos recursos
são opcionais, mas, quando fornecidos, são conferidos na mesma consulta que
valida o vínculo e a conta no banco. O retorno informa a unidade autorizada;
falhas de autorização geram `PermissionDenied`, sem distinguir recurso ausente
de recurso de outra unidade. Erros de banco propagam e não liberam acesso.

`forms.py` estende `AuthenticationForm`: o Django verifica o hash da senha do
username informado, depois `exigir_acesso_usuario_monitoramento` valida a conta
e seu vínculo antes de criar a sessão. Não há consulta própria de senhas.
Usuário inexistente e senha incorreta recebem o mesmo aviso, sem confirmar a
existência de contas. Contas inativas, administrativas ou sem unidade não entram.

- `GET /login/`: formulário responsivo com logo vetorial extraída do material
  da ESL Tech, sem dependências visuais externas.
- `POST /login/`: autenticação com CSRF, sessão Django e destino fixo. O
  parâmetro `next` não controla o redirecionamento. Falhas de banco retornam 503
  com aviso genérico; a senha não é reapresentada nem registrada pela view.
- `POST /sair/`: encerra a sessão com CSRF; GET não executa logout.
- `GET /`: entrega o painel privado e responsivo.
- `GET /dados/conversas/`: resumo e lista consolidada dos contatos.
- `GET /dados/conversas/<id_cliente>/`: histórico do contato dentro da unidade.
- `GET /dados/relatorio/`: indicadores, perfis, satisfação, atividade e etapas.
- `GET /dados/relatorio/faixa-etaria/`: consulta por `idade_minima`, `publico`
  (`titulares`, `dependentes` ou `todos`) e `periodo`, somente na unidade autorizada.
- `GET /contatos.csv`: exporta todos os contatos ou somente os elegíveis.
  Por padrão, o arquivo segue as 36 colunas, a grafia e a ordem do modelo oficial do Google
  Contacts para que e-mail, telefone, observações e marcador sejam reconhecidos.
  Com `formato=essencial`, entrega somente `Nome`, `E-mail` e `Telefone`, com
  telefone brasileiro sem o prefixo internacional `+55` (preservando o DDD),
  nome completo na primeira coluna, separador `;` e UTF-8 com BOM para planilhas
  em pt-BR. Os quatro downloads usam o mesmo período e escopo autorizado.

O login bem-sucedido retorna a `/`. A página e cada endpoint de dados chamam
`exigir_acesso_monitoramento`; nenhum deles aceita unidade escolhida em URL,
query string ou JavaScript. Depois do guard, cada SQL de
`core/repositories/monitoramento/painel.py` recebe e aplica o `id_unidade`
autorizado. O guard não modifica consultas posteriores nem concede acesso ao
Admin.

O navegador atualiza a seção de conversas a cada 10 segundos e a de relatórios
a cada 30 segundos, somente enquanto a página está visível. Voltar à aba força
uma nova leitura. Não há WebSocket nem tarefa periódica no servidor para o
painel: as requisições são atendidas pelo mesmo Gunicorn/Django do webhook.
Mensagens são carregadas somente quando um contato é aberto.

O follow-up confirmado aparece como mensagem de texto do bot na conversa e
participa da contagem de mensagens no período. Não há cartão exclusivo,
controle de disparo nem edição de stage no monitoramento. A lista mostra os
perfis junto da data: `DP -18`, `DP 18–59`, `DP 60+`, `18–59` e `60+`, conforme
os dados disponíveis; o cabeçalho da conversa mantém a descrição completa.

Conversas prioriza a lista e o histórico, sem repetir os quatro indicadores do
relatório. O layout compacto preserva as fontes e ajusta o espaço do chat pela
altura real do cabeçalho e do aviso, inclusive ao girar o celular. Em telas
estreitas, lista e conversa alternam com o botão de voltar. Os downloads
essenciais ficam logo abaixo dos downloads para Google Contatos em Relatórios.

O padrão é todo o histórico até o instante da requisição. Também existem os
períodos 24 horas, 7 e 30 dias, 2, 3 e 6 meses e 1 ano. Os períodos finitos são
comparados à janela imediatamente anterior de igual duração. A distribuição por
etapa representa o estado atual da conversa mais recente de cada contato com
atividade no período; não reconstrói a etapa histórica. Como o histórico
persiste texto e tipo, mas não o
payload original dos botões, o painel apresenta como referência os botões do
catálogo atual da etapa, sempre desabilitados.

O painel é somente leitura. Os filtros, a pesquisa, os seletores de período e os
downloads não alteram registros. As regras `idade_minima_suporte`, `email_obrigatorio`
e `bpa_ativo` vêm da unidade. O CSV completo preserva campos ausentes vazios; o
CSV elegível exige nome, e-mail estruturalmente válido e telefone em formato
internacional. Essa regra vale tanto para Google CSV quanto para CSV essencial;
nenhum dos formatos acrescenta etiquetas comerciais ou datas ao nome.

O card **Encaminhados ao comercial** fica somente em Relatórios, abaixo dos
quatro indicadores. Conta clientes distintos por unidade com encerramento
`encaminhado_suporte_idoso` no período (`finalizou_em`, intervalo semiaberto).
Inclui históricos, sem filtrar pela política atual, sem duplicar conversas e sem
misturar os casos 100+. Não comprova clique, atendimento humano ou matrícula.
Tags 18–59, 60+ e de dependentes continuam fixas. Quantidades e taxas do Funil
mantêm todos os envios registrados mesmo quando a configuração atual mudou.

### Consulta de faixa etária personalizada

O card fica abaixo de Evolução da demanda/Satisfação e antes de Perfil dos
atendimentos. Enter e Consultar executam a mesma consulta. Aceita idade inteira
positiva de até três dígitos e somente um público; a API também recusa parâmetros
duplicados. Não exige migração nem altera dados.

- Usa as idades atualmente cadastradas, não uma reconstrução histórica. Considera
  conversas com mensagem do cliente no período selecionado, em `[início, fim)`;
  sete dias são 168 horas. Idades ausentes não são estimadas.
- Titular conta uma vez por cliente/unidade, mesmo com várias conversas. Somente
  conversas da rota titular contribuem para sua idade e seu envio ao funil.
- Cada `id_dependente` identificado conta separadamente, inclusive nomes iguais
  em conversas diferentes, por decisão explícita do produto. Não deduplicar por
  nome. O total de participantes pode superar o de números de contato, mostrado
  separadamente no resultado. A idade considerada é a do dependente atendido.
- Funil conta apenas `funil_envios.status = 'sent'`, com `enviado_em` no mesmo
  período, ligado às conversas consideradas. Não transfere o envio entre titular
  e dependentes, nem confunde elegibilidade ou encaminhamento comercial com envio.
- O card Dependentes por titular agrupa a quantidade desses cadastros por titular
  no período, independentemente da idade mínima consultada. Placeholders ainda
  sem nome e idade não entram; dependente identificado sem idade entra nessa
  distribuição, mas não na consulta de faixa etária.
- Atualizações automáticas preservam formulário, foco e resultado. A consulta
  mostra o horário da leitura; para atualizá-la, clicar novamente em Consultar.
  Mudar idade/público/período limpa o resultado anterior; respostas atrasadas são
  descartadas. Falhas mostram um aviso, nunca um zero inventado.

Não há cadastro, recuperação/troca de senha nem bloqueio por número de tentativas
no portal. Contas e senhas continuam administradas pelo proprietário no Django
Admin. Senhas ficam sempre mascaradas no campo; os formulários usam o mecanismo
nativo de sessão e proteção CSRF. `falha_csrf` personaliza o aviso em português
somente nas rotas de monitoramento, preservando o tratamento padrão nas demais.
O HTTPS e os cookies seguros dependem das configurações de produção descritas
na [rotina de deploy](../regras_deploy/rotina_deploy.md).

`ALLOWED_HOSTS` aceita os domínios, mas não separa rotas por hostname; essa
separação não foi implementada. Os relatórios em `utilitarios` seguem manuais.

## Testes relacionados

- `tests/unit/test_fluxo_turno_abc.py`;
- `tests/unit/test_persistencia_essencial.py`;
- `tests/unit/test_retry_essencial.py`;
- `tests/unit/test_worker_flow_runtime.py`;
- `tests/unit/test_monitoramento_unidade.py`;
- `tests/unit/test_monitoramento_login.py`;
- `tests/unit/test_monitoramento_painel.py`.

Esses arquivos cobrem o núcleo transacional; consulte também
[`tests/README.md`](../tests/README.md).
