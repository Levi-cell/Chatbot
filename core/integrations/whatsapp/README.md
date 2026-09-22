# Integração WhatsApp

Comunicação com a Meta WhatsApp Cloud API por meio da biblioteca PyWa.

- [Portal do projeto](../../../README.md)
- [Regras de negócio](../../../REGRAS_DE_NEGOCIO.md)
- [Padrões de arquitetura](../../../PADROES_DE_ARQUITETURA.md#whatsapp-e-pywa)
- [Integrações externas](../README.md)

## Estrutura

```text
core/integrations/whatsapp/
├── exceptions.py
├── numero_comercial.py
├── messages/
│   ├── README.md
│   ├── etapa1_messages.py ... etapa22_messages.py
│   ├── componentes_compartilhados.py
│   ├── followup_messages.py
│   ├── tratamentos_universais.py
│   ├── tratamentos/
│   │   ├── composicao.py
│   │   ├── financeiro.py
│   │   ├── midia.py
│   │   ├── reforco_escolar.py
│   │   ├── retorno_inatividade.py
│   │   └── retorno_followup.py
│   └── triagem_componentes.py
├── pywa_functions/
│   ├── cliente.py
│   ├── saudacao.py
│   ├── resposta_envio.py
│   ├── ferramentas.md
│   └── pywa_senders/
│       ├── etapa1.py ... etapa22.py
│       ├── followup.py
│       └── triagem_base.py
└── tools/
    ├── ativando_numero.py
    ├── ativando_waba_id.py
    ├── config.py
    ├── desativando_numero.py
    ├── desativa_waba_id.py
    ├── usuarios.py
    └── validando_phone_waba.py
```

## Direção das dependências

```text
worker -> pywa_functions -> messages
                      |--> cliente PyWa
                      `--> Meta
```

`messages` não importa PyWa. `pywa_senders` pode importar `messages`, cliente e
exceções da integração. Nenhum deles controla banco, fila, transição ou retry.

## Messages

Antes de alterar textos ou montadores, seguir o
[contrato de personalidade e composição do atendimento](messages/README.md).
Ele distingue apresentação, tratamentos, a exceção de entrada da etapa 1,
triagem e os dois tipos de retorno.

Catálogo de conteúdo enviado:

- textos;
- títulos de botão;
- callbacks;
- funções puras de montagem.

Textos de WhatsApp não devem ser escritos diretamente no worker. Alterar uma
mensagem não deve mover a responsabilidade de envio para `messages`.

Cada etapa de 1 a 22 mantém seu próprio arquivo `etapaN_messages.py`.
Nele ficam a mensagem padrão e a repetição pura, com variantes de titular e
dependente quando pertinentes. Os montadores importados de `tratamentos/`
compõem orientação, ponte quando necessária e repetição, nessa ordem.
`compor_mensagem_inicial` une apresentação e pergunta reutilizável na entrada
da etapa; `compor_tratamento` é exclusivo para orientação e repetição, sem
a apresentação. As duas funções compartilham apenas a formatação dos parágrafos.
Contexto inválido tem mensagem própria que já orienta a resposta correta:
não usa `compor_tratamento` nem concatena a repetição. Conserva botões/opções e
rodapés da etapa e aceita a saudação de três horas quando elegível.
O follow-up seleciona a repetição neutra (`repeticao=True`); a triagem usa
suas perguntas canônicas. A etapa 8 é exceção: qualquer reação ao follow-up
avança diretamente para a 9, sem repetir a 8. Os retornos não duplicam apresentações, celebrações
ou despedidas da entrada normal na etapa.

As mensagens oferecem uma **experiência Supera gratuita**. Na etapa 7, a abertura
saúda o titular pelo nome e destaca **demonstração prática gratuita**; a pergunta
final convida a reservar sua **experiência Supera exclusiva**. A rota de dependente
preserva seu nome como participante. Os montadores e contextos de atendimento
distinguem `nome_titular`, `nome_dependente` e `nome_agente`, sem alterar o esquema
do banco. Os botões das etapas 7 e 9 exibem **Quero reservar**;
a etapa 18 usa **Já reservei**. O aceite por texto continua reconhecendo expressões
antigas como `quero agendar` e `já agendei`, conforme a etapa. Perguntas sobre como
reservar não são aceites; na etapa 18, intenção de reservar não comprova conclusão.

A gratuidade se refere à experiência; o tratamento financeiro explica que os
valores de investimento são definidos após ela, com orientação da equipe.
O prefixo é compartilhado em `tratamentos/financeiro.py`; cada etapa fornece
sua pergunta de retomada, introduzida por `Mas bora lá:` uma única vez.
`tratamentos_universais.py` apenas reexporta os imports antigos por compatibilidade.
Não há personalização por diretor nem campos
adicionais na unidade. Os montadores são puros, e o histórico conserva o
texto efetivamente enviado. Respostas já persistidas não são reenviadas.

Os corpos das mensagens usam negrito do WhatsApp (`*texto*`) com moderação,
priorizando a experiência oferecida e a ação principal. Evitar destacar todas
as palavras ou repetir o convite completo nos tratamentos financeiros.
Títulos de botões e valores usados pelos validadores permanecem sem marcação.

O tom é acolhedor, com emojis discretos e orientação clara. A oferta usa
**presentear**; **Maravilha! ☺️** aparece na apresentação normal da etapa 7,
sem ser acrescentado aos tratamentos de mídia, contexto, financeiro ou reforço
escolar. A etapa 1 não presume quem participará. Na apresentação do link,
o participante é o titular ou o dependente identificado pelo nome, inclusive
na repetição por follow-up e nos tratamentos. O contexto fornece esses dados ao sender; os
montadores não consultam banco nem decidem transições.

Na etapa 2, negativas sem destino alternativo repetem a pergunta. Uma
correção explícita como `Não, é para mim` conserva a escolha indicada.
Na oferta e na reserva, dúvidas curtas como `É gratuita?` retomam a
experiência. Fora desse contexto, o termo feminino precisa estar ligado
explicitamente à demonstração ou experiência. O aceite flexível permanece.

A retomada da etapa 9 usa uma única saudação, tanto após follow-up quanto
após três horas de inatividade. As referências ao dependente permanecem
explícitas; titular e dependente não trocam de papel.

As apresentações inicial padrão, explicativa, de mídia, financeira e de tratamento
de reforço escolar da etapa 1 recebem `nome_unidade`, `nome_agente` e `genero` como
argumentos já validados pelo worker. `messages` apenas escolhe `o` ou `a` e
formata o texto; não consulta o banco nem conhece a conversa.

Antes da etapa 1 estar apresentada, um texto pedindo informações gerais sobre
o Supera pode receber a abertura explicativa. O classificador
`validadores_contexto/valida_inicio_etapa1.py` reconhece frases completas e só é
usado após os tratamentos de mídia, reforço e financeiro. Essa variante pede
o nome uma vez e converge para a mesma etapa 2, sem novas colunas ou transições.
Depois da abertura e no follow-up, preserva-se a coleta do nome já existente.

`tratamentos/retorno_inatividade.py` monta `Olá novamente, <nome>!` quando
o cliente retorna com `followup_stage = 0` pelo menos três horas após o último envio confirmado do bot
na mesma conversa. A etapa 1 fica fora da regra; nome ou datas ausentes ou
incompatíveis não interrompem o atendimento e não produzem prefixo.

O worker fornece o contexto histórico e aplica a saudação à resposta corrente,
inclusive tratamentos, sem mudar o destino. Não é follow-up, mensagem separada
ou disparo automático após três horas de inatividade. No retry com resposta
persistida, não há novo envio.

## PyWa functions

Concentra a criação do cliente PyWa e o transporte das mensagens do fluxo. Os
senders são o local normal para chamadas de envio; operações compartilhadas de
bloqueio e desbloqueio ficam em `tools/usuarios.py`, que reutiliza a mesma
fábrica de cliente em `pywa_functions/cliente.py`.

- `cliente.py`: normaliza `phone_id`, cria `WhatsApp` e aplica o prefixo de
  retorno somente no escopo do envio corrente;
- `saudacao.py`: seleção de bom dia, boa tarde ou boa noite pelo horário do
  atendimento inicial, distinta da saudação de retorno;
- `resposta_envio.py`: extrai o ID confirmado pela Meta e falha se ele faltar;
- `pywa_senders/etapaN.py`: mensagens normais e tratamentos específicos da
  etapa N.

Cada sender escolhe conteúdo, legenda e lista de botões, realiza a chamada PyWa
e devolve um contexto técnico com o ID da Meta e a etapa da mensagem enviada.
O sender não escolhe origem, evento ou destino da transição.

O encaminhamento de suporte ao idoso é um sender da etapa 6 com botão para o
número comercial, normalizado por `numero_comercial.py`. A decisão de usar
`idade_minima_suporte`, comparar a idade do titular ao limite e encerrar o
atendimento é do worker. O sender recebe o limite validado e o texto de contato
montado pelo catálogo com agente, unidade, nome e idade atual do titular. Todas as faixas
usam a mesma mensagem de atendimento personalizado e o botão `Falar agora`.
O link inclui o texto pré-preenchido com codificação de URL; o cliente ainda
precisa confirmar o envio no WhatsApp. O reconhecimento do corpo atual e do
texto ainda emitido pela versão em produção permite recuperar respostas sem
reenviá-las. As variantes antigas que citavam a faixa foram removidas após
verificação de ausência de pendências no banco.

O encaminhamento geral de 100 anos ou mais mantém um sender próprio, usado
para titular e dependente mesmo com suporte desativado. Seu catálogo apresenta
a anamnese com o consultor e acrescenta um rodapé acolhedor, sem repetir a
pergunta de idade. A decisão de encerrar continua pertencendo ao worker.
Os dois senders exigem `mensagem_comercial` e usam o mesmo montador de texto
pronto, `montar_mensagem_contato_comercial_etapa6`. O repositório da etapa 6
consulta o nome da unidade vinculada à conversa. O worker fornece a rota e a
idade da resposta atual; o catálogo adapta o pedido para titular ou dependente,
sempre mencionando a experiência Supera gratuita. Não atribuir ao cliente a
idade informada sobre seu dependente. Dados obrigatórios ausentes impedem
montar um contato incorreto antes de qualquer envio à Meta.
Da mesma forma, a política `email_obrigatorio` e a distinção entre
aceite da oferta e pedido de informações não pertencem aos senders.

Uma função de mídia envia somente um arquivo. Lotes e álbuns exigem um contrato
futuro capaz de persistir vários IDs e tratar sucesso parcial.

Os senders devolvem contexto simples para o worker. Falhas são encadeadas com
`ErroEnvioMeta`, permitindo rollback e retry sem esconder a causa original.

## Tools

Operações Meta compartilhadas e ferramentas administrativas usadas pelo
Django Admin e pelo webhook:

- registrar/desregistrar número;
- validar o vínculo entre WABA e phone ID;
- ativar/desativar a inscrição WABA;
- bloquear e desbloquear usuários na Meta.

Relatórios conscientes e somente leitura ficam em
[`utilitarios/monitoring/blocked_users.py`](../../../utilitarios/monitoring/blocked_users.py).
Eles comparam bloqueios pela chave completa
`(waba_id, phone_id_unidade, wa_id_cliente)` e reconciliam registros Cloud API.

`tools/usuarios.py` é a primitiva única de bloqueio e desbloqueio consumida pelo
webhook e pelo Admin. Os demais módulos deste diretório atendem às operações de
configuração da conta e do número. Eles podem reutilizar a fábrica de cliente,
mas não devem duplicar envio de etapa nem assumir responsabilidades de banco,
fila ou transação.

`tools/config.py` centraliza a configuração operacional da integração Meta, mas
os valores são lidos por `core/config_env.py` a partir de variáveis de ambiente:

```text
META_ACCESS_TOKEN
META_GRAPH_API_VERSION
META_HTTP_CONNECT_TIMEOUT_SECONDS
META_HTTP_READ_TIMEOUT_SECONDS
META_PHONE_REGISTRATION_PIN
```

`META_GRAPH_API_VERSION` usa o formato `26.0`, sem o prefixo `v`. Essa versão é
aplicada ao cliente PyWa e a todas as URLs diretas da Graph API. Se uma versão
nova apresentar incompatibilidade, a variável pode retornar manualmente para a
última versão estável validada.

Não adicione token ou outro valor sensível diretamente nesse arquivo. WABA ID e
phone number ID são dados por unidade e devem vir do banco/cache.
`META_PHONE_REGISTRATION_PIN` também é segredo operacional e só é necessário
para a operação administrativa de registro do número; não deve ser exibido em
logs, documentação ou mensagens.

## Limites

Esta integração não deve:

- executar SQL ou Redis;
- decidir etapa persistida;
- marcar fila como `sent`;
- escolher quantidade ou intervalo de retries;
- executar commit, rollback ou close;
- importar módulos de `callback` ou `workers`.

## Testes relacionados

- `tests/unit/test_fluxo_turno_abc.py`;
- `tests/unit/test_persistencia_essencial.py`;
- `tests/unit/test_retry_essencial.py`;
- `tests/unit/test_worker_flow_runtime.py`;
- `tests/unit/test_suporte_idoso_email_obrigatorio.py`;
- `tests/unit/test_saudacao_retorno.py`.

O núcleo transacional e os testes específicos estão descritos em
[`tests/README.md`](../../../tests/README.md).

## Lembrete de follow-up

`messages/tratamentos/retorno_followup.py` monta a saudação de retomada com stage
positivo: `Que bom te ver novamente, <nome>!` ou `Que bom te ver novamente!`.
O nome vem do cadastro persistido; não é extraído da reação que será desconsiderada.
Na etapa 1, o worker passa nome ausente ao formatador, mesmo com cadastro antigo:
a saudação é sempre genérica, seguida da pergunta de nome do atendimento atual.
O prefixo é aplicado no corpo da resposta, preservado no histórico e removido
do escopo ao sair do sender, inclusive em falhas. O proativo continua sem saudação.

Na etapa 8, o worker reutiliza a transição normal para a 9 e seus senders de
titular/dependente. A reação não vale como aceite da oferta da 9. Sua saudação
própria é suprimida para conservar somente o prefixo de follow-up. A 8 possui
apenas mensagem inicial, sem variante de repetição. Avanço e conclusão do ciclo
são persistidos juntos pelo worker, sem decisões de fluxo nos montadores.

`messages/followup_messages.py` contém o texto aprovado do lembrete proativo.
`pywa_senders/followup.py` envia texto sem botões, sem saudação de retorno e sem
id_mensagem_fila fictício. Usa sessão HTTP com timeout e sem retry automático;
recebe destinatário e phone_id da unidade. `conta_wa` aceita sessão opcional sem
alterar os clientes existentes. A sessão usa timeout de 20 segundos por operação,
com conexão limitada a 5 segundos. Stage e persistência pertencem ao worker/repositório.
O ID retornado confirma o aceite da API; os eventos `sent`, `delivered` e `read`
recebidos pelo webhook não atualizam o histórico nesta versão.
