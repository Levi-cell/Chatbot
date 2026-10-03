# Ideia futura: mais de uma pessoa atendida na mesma conversa

Registro: **30/09/2026**. Status: **ideia arquivada para evolução; não faz parte
da primeira implantação da IA**.

Plano vigente: [IA híbrida](../plano_ia_hibrida_atendimento.md).

## 1. Regra da primeira versão

Uma conversa atende o titular **ou um dependente**. Citar várias pessoas não
cria vários participantes. O contexto auxiliar pode guardar candidatos até o
cliente escolher a prioridade; apenas a pessoa escolhida entra na coleta ativa.

Se o cliente quiser atender mais pessoas, explicar que poderá levá-las à visita,
mas que este atendimento vai conhecer o perfil de quem ele considera prioridade.
No meio de uma coleta, essa orientação não reinicia o fluxo nem oferece mais
cadastros. Não prometer horários ou vagas para todas as pessoas.

Corrigir ou trocar o dependente continua usando um único registro na conversa.
O `id_dependente` permanece o mesmo. Na troca explícita por outro dependente,
manter o destino já escolhido, perguntar nome/idade faltantes e recolher a triagem
da nova pessoa. Invalidar os dados dependentes da anterior e preservar auditoria.
Isso não é atendimento simultâneo de várias pessoas e não habilita esta evolução.

## 2. Objetivo futuro

Permitir, se aprovado depois, atender o titular e/ou vários dependentes na mesma
conversa, identificando de quem é cada resposta e a situação de cada perfil.
O escopo original dessa possibilidade é o modo IA; não estender automaticamente
às unidades determinísticas.

## 3. Por que exige um projeto próprio

Hoje o banco e o fluxo assumem um dependente por conversa, inclusive pelo índice
`uq_dependente_conversa`. As respostas da triagem também usam unicidade por
conversa/pergunta. Remover apenas o índice ou pedir à IA para "lembrar de todos"
não cria estado, histórico ou Funil corretos para cada participante.

Proposta a estudar: entidade de participante ligada à conversa, com papel,
identidade, idade, parentesco, estado de coleta e triagem próprios. O titular do
contato pode ser diferente da pessoa atendida. Essa proposta não é um schema final.

## 4. Decisões necessárias

| Área | Pergunta a resolver |
| --- | --- |
| Limite | Quantas pessoas podem participar e quem escolhe a ordem? |
| Elegibilidade | Como tratar um participante inelegível sem encerrar os demais? |
| Coleta | Quais dados são compartilhados e quais precisam de confirmação individual? |
| Triagem | Como vincular cada resposta, corrigir e retomar sem misturar perfis? |
| E-mail | Como aplicar a regra do titular e as exceções a participantes distintos? |
| Agendamento | Uma visita ou agendas separadas, e em que momento a IA deixa de atuar? |
| Funil | Um lead ou vários, com quais vínculos e garantias contra duplicação? |
| Follow-up | Qual pendência lembrar e o que encerra a conversa inteira? |
| Painel | Como apresentar progresso, motivos de encerramento e métricas por pessoa? |
| Bloqueios | Como medir falta de progresso quando um perfil avança e outro não? |

Preservar regras de idade, BPA, suporte ao idoso e exceção universal. A elegibilidade
de uma pessoa não pode ser deduzida pela idade de outra. Definir migração dos dados
históricos e compatibilidade com o modo de um participante antes de liberar.

## 5. Cenários de aceitação futura

Ana cita Pedro e Paula; seleciona ordem; corrige a idade de um; o outro cai em
restrição; a conversa reinicia após falha; o Funil recebe somente os perfis
elegíveis uma vez. Cada resposta deve continuar atribuída à pessoa correta.

Testar ainda mudança de prioridade, desistência de um participante, participante
já encaminhado, nova conversa com as mesmas pessoas e desativação de IA no meio
do atendimento. Nenhum desses comportamentos será introduzido pelo piloto atual.
