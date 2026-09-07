# Proposta de IA no atendimento por etapas

Registro de ideias e análise em 05/09/2026.

Base consultada: V1.1.0, commit `3f75447`, código e documentação locais.
Status: planejamento futuro com decisões registradas. Este documento não
implementa IA, não escolhe definitivamente um modelo e não altera regras em
produção. A implementação de IA fica para depois das prioridades listadas ao final.

## Objetivo e recomendação

Permitir que o atendimento entenda respostas naturais e dúvidas na mesma
mensagem, mantendo o mapa de transições, as políticas da unidade e as proteções
do backend como responsáveis pelo resultado do fluxo.

Foi escolhida a estratégia de habilitar IA progressivamente por etapa, começando
pela apresentação, coleta do nome e passagem para a pergunta sobre titular ou
dependente. A IA interpreta
texto e pode produzir pequenos trechos de reação; o código valida os dados,
autoriza o destino e compõe a mensagem com os elementos obrigatórios.

Será a mesma integração de IA, com uma visão geral do fluxo e responsabilidade
delimitada pela etapa atual. Não haverá um modelo diferente para cada etapa.
Depois de validar uma etapa e sua ligação com a seguinte, será possível publicar
uma nova versão na VM e começar a adaptação da próxima. As etapas ainda não
habilitadas continuam determinísticas. Cada publicação depende dos testes de
regras, falhas e regressão; ausência absoluta de erros não é uma garantia possível.

## Decisão: ativação de IA por unidade e oferta comercial

Na implementação futura, a tabela `chatbot.unidade` receberá uma coluna booleana
para ativar ou desativar IA. Nome técnico proposto: `ia_habilitada`, com valor
inicial `false`, preservando o atendimento determinístico das unidades existentes.
O nome definitivo será alinhado aos padrões do banco no plano de implementação.

Esse controle permitirá oferecer atendimento com IA como um plano comercial ou
recurso adicional contratado pela unidade. Preço, limites contratuais e processo
de cobrança ficam para definição futura. A coluna controla o recurso; ela não
implementa cobrança ou confirmação automática de pagamento.

O uso efetivo dependerá de duas condições: IA habilitada para a unidade e etapa
já implementada e liberada para IA naquela versão. Ativar a unidade não habilita
automaticamente as etapas que ainda não foram adaptadas. A lista de etapas
liberadas pertence à implementação; esta decisão não pede uma coluna por etapa.

| Situação | Comportamento esperado |
| --- | --- |
| IA desativada na unidade | Fluxo determinístico completo, sem chamada à API de IA |
| IA ativada, mas etapa ainda não habilitada | Fluxo determinístico daquela etapa |
| IA ativada, etapa habilitada e resultado válido | Interpretação e trecho auxiliar da IA integrados aos elementos obrigatórios da etapa autorizada |
| API indisponível, limite atingido ou resultado inadequado | Resposta alternativa determinística, sem avançar a partir de dados não validados |

A composição pretendida é:

```text
Com IA: trecho auxiliar validado da IA + mensagens obrigatórias + pergunta e botões da etapa autorizada
Sem IA: mensagens, validações, pergunta e botões do fluxo determinístico
```

A ordem dos blocos respeita a conversa: a apresentação pode vir antes da reação
da IA, por exemplo. As regras de negócio são aplicadas pelo código; não são um
texto a concatenar na resposta. O trecho auxiliar não pode substituir perguntas
obrigatórias, criar opções ou contradizer a transição autorizada.

A implementação precisa preservar os dois caminhos como funcionalidades
suportadas, com testes para unidade ativada, desativada, etapa não habilitada,
falhas e recuperação. A interpretação por IA também deixa de ser chamada quando
o recurso está desligado; o atendimento não pode depender dela para funcionar.

A flag deve ser consultada pelo backend no escopo da unidade resolvida, com SQL
nos repositórios. A forma de administração será definida na implementação,
mantendo o painel do franqueado somente para consulta. Desativar IA não deve
reiniciar a conversa nem provocar reenvio de uma resposta já persistida.

Esta decisão registra apenas uma alteração futura. Quando for implementada,
o DDL refletirá a coluna na definição `CREATE TABLE` mais recente; a atualização
do banco existente terá migração incremental separada, conforme o padrão do
projeto. Nenhum DDL, model, Admin ou banco foi alterado neste registro.

Não é necessário criar uma IA do zero nem baixar um modelo. A VM poderá chamar
uma API hospedada: envia o contexto necessário e recebe a interpretação e o
texto. A inferência do modelo acontece no provedor, sem exigir GPU local. Esse
é o modo de integração descrito no [guia inicial da API da OpenAI](https://developers.openai.com/api/docs/quickstart).

## Fine-tuning e restrições por código

Fine-tuning ajusta o comportamento de um modelo por meio de exemplos de entrada
e saída. Não transforma um documento de regras em código executável nem garante
que todas as respostas estejam corretas.

Situação verificada na documentação oficial nesta data:

| Modelo | Fine-tuning informado no catálogo |
| --- | --- |
| [GPT-5.5](https://developers.openai.com/api/docs/models/gpt-5.5) | Não suportado |
| [GPT-5.6 Sol](https://developers.openai.com/api/docs/models/gpt-5.6-sol), destino do alias `gpt-5.6` | Não suportado |
| [GPT-4.1 mini](https://developers.openai.com/api/docs/models/gpt-4.1-mini) | Suportado pelo modelo, sujeito à disponibilidade da plataforma |

Há uma limitação adicional: a plataforma self-service de fine-tuning está sendo
descontinuada. Novas organizações sem uso anterior não podem criar treinamentos
desde 07/05/2026; desde 02/07/2026 há restrições adicionais para organizações sem
inferência recente de modelos ajustados. O encerramento de novos treinamentos
para clientes ativos está previsto para 06/01/2027. Não foi consultada a
elegibilidade da conta deste projeto. [Cronograma oficial](https://developers.openai.com/api/docs/deprecations#update-to-openais-self-serve-fine-tuning)

Portanto, o piloto proposto não depende de fine-tuning. Começa com instruções,
exemplos revisados, contexto da unidade e validações no Python. O
[guia de fine-tuning](https://developers.openai.com/api/docs/guides/supervised-fine-tuning)
também diferencia treinamento por exemplos de simples fornecimento de contexto.

O código de restrição pertence à aplicação. Mesmo em uma solução que utilize
fine-tuning, ele continua necessário. Podemos delimitar campos e opções com
respostas estruturadas e, se necessário no futuro, oferecer funções específicas
ao modelo. A aplicação decide se executa uma solicitação de função; não entrega
acesso livre ao banco ou ao envio de mensagens. [Function calling](https://developers.openai.com/api/docs/guides/function-calling)

Validação de formato não garante veracidade: uma resposta JSON válida ainda pode
interpretar um nome ou uma intenção incorretamente. Quando a interpretação não
for suficiente, o atendimento deve pedir esclarecimento. [Limites de Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs#handling-mistakes)

## O que acontece hoje no projeto

Na etapa 1, os tratamentos de mídia, reforço escolar e financeiro precedem a
validação do nome. Assim, depois de o nome ter sido solicitado, uma mensagem como
“Meu nome é Paula. Quanto custa?” pode ser tratada como pergunta financeira e
receber novamente a pergunta do nome.

Isso segue a regra atual documentada; aceitar o nome e avançar nessa mesma
resposta será uma evolução explícita do comportamento, e não apenas uma troca
de texto.

Arquivos relevantes consultados:

- [Regras de negócio](<C:/Chatbot/Projeto/Chatbot/REGRAS_DE_NEGOCIO.md>): seções 11, 11.1, 11.3 e 11.4 estabelecem início e tratamentos com permanência.
- [Resolver da etapa 1](<C:/Chatbot/Projeto/Chatbot/workers/worker_flow/response_flow/etapas/resolver_etapa1.py>): aplica as prioridades e produz `nome_cliente_valido` quando o nome passa pela validação.
- [Resolver de transição](<C:/Chatbot/Projeto/Chatbot/workers/worker_flow/response_flow/transicoes/resolver_transicao.py>): autoriza `origem + evento -> destino` e recusa anexar uma transição a um contexto marcado como tratamento.
- [Mensagens da etapa 2](<C:/Chatbot/Projeto/Chatbot/core/integrations/whatsapp/messages/etapa2_messages.py>): apresentação do Supera, retomada da pergunta e opções oficiais.
- [Sender da etapa 2](<C:/Chatbot/Projeto/Chatbot/core/integrations/whatsapp/pywa_functions/pywa_senders/etapa2.py>): monta os elementos PyWa e envia o conteúdo.
- [Efeitos da transição](<C:/Chatbot/Projeto/Chatbot/workers/worker_flow/transacoes/efeitos_transicao.py>): aplica os dados capturados à persistência e participa da recuperação do contexto.

Um resultado futuro com nome válido e dúvida financeira precisa ser classificado
como resposta válida da etapa acompanhada de esclarecimento comercial. Não se
deve simplesmente marcar `tratamento=True` e tentar avançar, nem remover a
proteção que proíbe essa combinação nos contratos atuais.

## Alternativa A: IA colaborando com cada etapa

Esta é a alternativa escolhida para a implementação progressiva.

### Composição da mensagem

```text
Dados oficiais da unidade e estado da conversa
                    +
Interpretação da mensagem pela IA
                    |
                    v
Validação dos dados e autorização pelo mapa
                    |
                    v
Texto obrigatório + reação contextual + pergunta autorizada + botões oficiais
                    |
                    v
Envio e persistência pelo fluxo existente, com os contratos adaptados e testados
```

Os blocos variam conforme o caso; uma apresentação não precisa ser repetida em
toda mensagem. A composição deve evitar perguntas duplicadas, saudações
repetidas, contradições e parágrafos longos.

O primeiro piloto pode gerar somente a reação curta e usar textos aprovados
para apresentação, explicação sobre valores e pergunta final. Isso entrega
personalização com uma área pequena de geração livre.

### Exemplo: primeira mensagem

Cliente sem conversa anterior: “Vi o anúncio. Vocês ajudam com memória?”

Composição proposta:

1. Apresentação com nome do agente e da unidade lidos do banco.
2. Resposta breve baseada na descrição comercial aprovada de estimulação cognitiva.
3. Pergunta do nome conforme a etapa inicial.

A resposta não deve prometer resultado clínico ou inventar benefícios ausentes
do material aprovado. O primeiro contato mantém a inicialização da etapa 1.

### Exemplo: nome e dúvida financeira juntos

Depois de o bot pedir o nome, o cliente responde:

> Meu nome é Paula. Quanto custa?

Interpretação conceitual, sem contrato de API implementado:

```json
{
  "nome_candidato": "Paula",
  "evidencia_nome": "Meu nome é Paula",
  "intencoes": ["informar_nome", "pergunta_financeira"],
  "referencias_comerciais": ["valores_no_atendimento_presencial"],
  "precisa_esclarecimento": false
}
```

O backend confirma que Paula é o nome do interlocutor, valida o candidato e
consulta a aresta de `nome_cliente_valido`. A evidência ajuda a avaliar a
extração, mas sua presença sozinha não garante que a pessoa foi identificada
corretamente.

Mensagem ilustrativa, sujeita à revisão comercial:

> Prazer, Paula! O Supera é um curso de estimulação cognitiva. Os valores de
> investimento são apresentados no atendimento presencial após sua aula gratuita.
> Para eu entender melhor como podemos ajudar, esse atendimento é para você ou
> para um dependente?

Botões: **Para mim** e **Para um dependente**.

A IA não define IDs, títulos ou destinos dos botões. A mensagem e os botões
devem corresponder à mesma etapa autorizada e ser enviados como uma resposta
coerente.

### Limites de interpretação

- “Quanto custa?” sem nome: responder à dúvida e manter a coleta do nome.
- “Minha mãe é Paula”: não gravar Paula automaticamente como nome do interlocutor.
- Nome e pergunta financeira claros: aproveitar o nome validado e responder à dúvida.
- Vários nomes ou contradição com dado confirmado: pedir esclarecimento antes de sobrescrever.
- Pergunta fora da base comercial: reconhecer o limite e oferecer o contato oficial da unidade.
- Mensagem interativa inequívoca: usar o caminho determinístico existente, sem chamada de IA desnecessária.
- Mídia: preservar o tratamento atual de tipo não suportado neste piloto.
- Recusa em prosseguir: não converter em aceitação de agendamento.

No piloto, aproveitar somente os dados necessários à etapa atual. Uma política
de capturar idade, dependente e e-mail antecipadamente, pular etapas ou aceitar
o nome já na primeira mensagem exigiria definição própria posterior.

## Alternativa B: recepção com IA antes da coleta determinística

Esta alternativa fica registrada como comparação; não é a estratégia escolhida
para a implementação planejada.

A ideia de apresentar o Supera, coletar nome, tirar dúvidas e oferecer
“Tirar dúvidas” e “Prosseguir com agendamento” também é viável.

“Desligar a IA” significa deixar de chamar a API para aquela conversa a partir
de um ponto definido. Não implica encerrar um modelo local ou criar uma IA
separada para cada lead.

| Aspecto | IA por etapa | Recepção inicial com IA |
| --- | --- | --- |
| Dúvida junto da resposta | Pode ser tratada na etapa habilitada | Funciona durante a recepção; depois exige política própria |
| Continuidade | Mantém a pergunta atual como referência | Precisa formalizar a passagem da recepção para a coleta |
| Piloto pequeno | Pode se limitar à etapa 1 e saída para a 2 | Pode se limitar à recepção, mas exige estado e critérios de saída |
| Custo | Controlado por etapas e chamadas necessárias | Controlado pelo limite da conversa de dúvidas |
| Risco de repetição | Pode repetir perguntas se a composição for mal definida | Pode criar uma espera prolongada antes de iniciar a coleta |

A recepção separada não resolve dúvidas que surjam depois de o cliente começar
a coleta. Se for escolhida, precisa ficar explícito se haverá ajuda contextual
nessas etapas, resposta fixa ou encaminhamento ao contato oficial.

Não é recomendado inserir uma nova etapa numérica ou uma permanência indefinida
na etapa 1 apenas para simular essa recepção. O nome validado hoje autoriza a
passagem para a etapa 2. Aguardar uma nova decisão de agendamento mudaria esse
contrato e precisaria de estado, transições, histórico e recuperação definidos.

## Limitar dúvidas sem forçar uma aceitação

É válido limitar o uso de IA, mas atingir um limite não prova que o cliente
aceitou agendar. O sistema não deve preencher respostas ou avançar em nome dele.

Sugestão inicial para avaliar no piloto, ainda não aprovada como regra:

1. Responder de forma breve, com uma pergunta final para retomar o objetivo.
2. Após três respostas de esclarecimento, oferecer uma escolha clara entre continuar a coleta e falar com a unidade.
3. Após cinco respostas geradas de esclarecimento por conversa ativa, parar novas gerações de FAQ e usar uma orientação fixa com essas opções.
4. Uma aceitação explícita continua o fluxo autorizado; uma recusa permite pausar ou orientar o contato com a unidade, conforme regra a definir.

Esses valores são hipóteses de produto. “Uma resposta de esclarecimento” conta
uma resposta do bot, não cada ponto de interrogação e não cada retry técnico.
O limite só poderá valer em produção depois de definirmos persistência, alcance,
reinício do contador e comportamento de retorno.

Além do limite de dúvidas, são necessários limites técnicos de chamadas, tokens,
tempo de resposta e orçamento por unidade. Atingir um limite técnico deve usar
uma resposta alternativa determinística, sem inventar uma falha do cliente.

### Conflito concreto com o contador existente

O [repositório de suspeita de bot](<C:/Chatbot/Projeto/Chatbot/core/repositories/seguranca/suspeita_bot.py>)
define `LIMITE_TURNOS_SEM_AVANCO = 12`. Uma recepção longa na mesma etapa pode
interagir com esse controle.

Antes de colocar FAQ prolongada em produção, é necessário definir como distinguir
uma dúvida comercial permitida de repetição inválida. Não desativar o controle
de abuso nem zerar seus contadores a cada resposta da IA para permitir conversa
infinita. O limite de FAQ deve ter finalidade e contagem próprias; a integração
com a proteção existente depende de uma decisão documentada e testada.

## Documentação para orientar o atendimento

É possível manter as instruções em Markdown e carregar seu conteúdo na chamada
da API. O arquivo precisa ser lido pela aplicação e enviado como instruções ou
contexto; deixá-lo apenas na pasta não produz efeito no modelo. A documentação
oficial descreve instruções, exemplos e contexto, inclusive carregamento de
arquivos de texto. [Guia de prompting](https://developers.openai.com/api/docs/guides/prompt-engineering#message-formatting-with-markdown-and-xml)

Organização sugerida para a futura base:

- Identidade e linguagem: agente, tom, tamanho das respostas e exemplos.
- Conteúdo comercial aprovado: o que é o Supera, aula gratuita, valores, diferenças em relação a reforço escolar e limites do que pode afirmar.
- Contrato de cada etapa: dado esperado, dados que não pode presumir e pergunta de retomada.
- Regras da unidade: campos atuais e políticas lidos do PostgreSQL.
- Exemplos de respostas compostas: nome e dúvida, dúvida sem nome, dependente, recusa e ambiguidade.

Instruções estáveis devem ficar versionadas. Dados que mudam, como endereço e
políticas da unidade, vêm da fonte atual. Mensagens do lead são dados de entrada;
não têm autoridade para redefinir as instruções comerciais ou o mapa.

No início, uma base pequena revisada pode ser incluída diretamente. Se crescer,
podemos recuperar apenas os trechos relevantes, sempre com filtro da unidade
aplicado pelo backend. Não é necessário começar com uma infraestrutura de busca
complexa nem enviar todo o banco em cada chamada.

## Encaixe futuro na arquitetura

As localizações abaixo são propostas, sem criação de módulos nesta atualização:

| Responsabilidade | Localização prevista |
| --- | --- |
| Cliente HTTP, autenticação e tradução de erros da API de IA | `core/integrations/ia/` |
| Seleção de contexto, instruções da etapa e interpretação do resultado | `workers/worker_flow/response_flow/ia/` |
| Aceitação de dados e decisão de evento | Resolvers e validadores da etapa |
| Autorização do destino | `response_flow/transicoes/` |
| Textos oficiais e composição pura da mensagem | `core/integrations/whatsapp/messages/` |
| Botões e envio Meta/PyWa | `core/integrations/whatsapp/pywa_functions/pywa_senders/` |
| Consultas e persistência de runtime | `core/repositories/` |
| Checkpoints e contexto final | Orquestrador e `workers/worker_flow/transacoes/` |
| Casos, contratos e simulações | `tests/` |

Uma API de IA é uma integração externa. Não exige, por si só, um quarto worker
ou uma GPU na VM. A chamada precisa ficar no processamento assíncrono, preservando
a entrada rápida do webhook. Capacidade e latência devem ser medidas antes de
decidir por processos adicionais.

### Proteções a preservar e adaptar explicitamente

- Manter a barreira `resposta_bot_para_mensagem_atual` antes da interpretação e de qualquer novo envio. Se a resposta já existe, reparar o contexto sem gerar outra.
- Preservar FIFO, exclusão por conversa, `lock_version`, histórico vinculado à mensagem de origem e revalidação da transição na persistência final.
- Não considerar uma geração da IA como prova de envio pela Meta ou como resposta do bot já persistida.
- Definir como recuperar os dados extraídos e o texto final aprovado em retries; não depender de uma nova geração para reproduzir a decisão anterior.
- Revisar os efeitos da transição 1 → 2 e o reparo de nome: o texto original misto pode não ser aceito pelo parser legado em uma recuperação.
- Continuar usando os IDs de unidade e conversa resolvidos pelo sistema. O modelo não escolhe o escopo de acesso nem executa SQL.
- Definir timeout de IA compatível com o lease do processamento e comportamento determinístico para erro, recusa do modelo, saída inválida ou orçamento atingido.
- Preservar que `sent` depende da resposta enviada e persistida. Não existe atomicidade distribuída automática entre API de IA, Meta e PostgreSQL.
- Medir a latência com a regra atual de turno: mensagens seguintes podem ser descartadas enquanto a primeira aguarda sua resposta. Agrupar mensagens seria outra mudança de produto.

As seis perguntas padronizadas da triagem, suas opções e seu significado não
devem ser reescritos livremente no piloto. A IA não deve sugerir respostas para
melhorar pontuação nem inventar diagnósticos.

## Caminho proposto para começar

1. Aprovar uma página de regras comerciais e exemplos, sobretudo o que responder sobre valores.
2. Definir o contrato da etapa 1: extrair nome do interlocutor, reconhecer dúvidas e decidir quando pedir esclarecimento. A autorização de transição continua no código.
3. Separar um conjunto revisado de mensagens de teste, sem disparos aos clientes, incluindo dados sintéticos ou desidentificados. Reservar casos não usados nos exemplos das instruções.
4. Comparar modelos pela mesma tarefa, medindo acerto, resposta comercial, preservação da etapa, tempo e custo. Escolher por resultado; fine-tuning não é pré-requisito.
5. Montar um protótipo por API fora do envio real, capaz de mostrar interpretação, decisão validada e mensagem composta.
6. Testar falhas, retries, nome de dependente, tentativas de mudar regras, dúvida sem nome, recusa, mídia e mensagem interativa.
7. Preparar um piloto usando a ativação por unidade, com desativação simples e retorno ao comportamento determinístico.
8. Validar a etapa e sua transição para a seguinte, publicar a versão na VM e acompanhar os resultados do piloto.
9. Trabalhar na próxima etapa e repetir os testes das anteriores antes de publicar outra versão. Manter determinísticas as etapas ainda não habilitadas.

Os testes precisam verificar mais do que uma resposta “bonita”: dados corretos,
nenhuma transição indevida nos casos avaliados, mensagem coerente com os botões,
nenhuma duplicação em replay, isolamento da unidade e uso comercial adequado.
Bom desempenho em testes não é garantia de ausência de erros em produção.

Métricas úteis: coleta correta do nome, redução de repetição desnecessária,
abandono, avanço ao próximo passo, encaminhamentos, latência, falhas e custo por
lead. Envio ao funil não deve ser apresentado como confirmação de agendamento
ou venda. O histórico do banco não representa diretamente a quantidade de
chamadas de IA nem permite prever custo sem medir tokens e chamadas reais.

## Decisões para a próxima discussão

- Aprovar o texto comercial sobre valores e o grau de liberdade dos trechos gerados.
- Definir o contato ou canal realmente disponível para dúvidas que exigem a equipe; não prometer transferência humana inexistente.
- Escolher limites iniciais de FAQ, orçamento, tempo de resposta e política de retomada.
- Resolver o efeito das dúvidas permitidas no controle de turnos sem avanço antes do piloto com clientes.
- Definir os casos de teste e critérios para habilitar uma unidade.
- Definir preço e condições do plano com IA, além da administração da coluna de ativação.

## Ordem de trabalho acordada para a próxima semana

O assunto IA fica pausado neste momento. A sequência definida pelo responsável
pelo projeto é:

1. Terminar o plano prático do `worker_followup`, com cada passo contendo o código completo do arquivo criado ou alterado.
2. Aplicar o plano de follow-up no projeto e validar seu funcionamento.
3. Atualizar o plano de `user_id` para refletir o projeto após o follow-up. Essa tarefa é atualização do plano, não aplicação automática de `user_id`.
4. Criar o ambiente de desenvolvimento (`dev`).
5. Somente depois iniciar a implementação de IA por etapas, incluindo a ativação por unidade e a publicação progressiva de versões.

Ao retomar IA, a base deste documento deverá ser revisada contra o estado do
projeto e o ambiente dev então existentes. As referências à V1.1.0 registram a
análise original e não substituem essa revisão.

O plano de `worker_followup` continua independente: verificar inatividade e enviar
um lembrete fixo não exige IA. A futura integração deverá respeitar o contrato de
retorno que estiver implementado nessa versão, sem aproveitar a resposta que
esse contrato mande apenas registrar e usar para reapresentar a etapa. O plano
de `user_id` permanece fora do escopo desta proposta.
