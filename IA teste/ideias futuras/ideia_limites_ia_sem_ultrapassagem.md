# Evolução futura: limites de IA sem ultrapassagem

Revisão: **01/10/2026**. Status: **melhoria futura; fora da primeira implementação**.
O responsável pelo projeto aprovou explicitamente as duas possibilidades de
excesso abaixo para a versão inicial. Eliminar essas brechas será uma evolução.

Referências: [plano principal](../plano_ia_hibrida_atendimento.md),
[chat e cotas mensais](../plano_ia_hibrida_atendimento.md#consumo-ia) e
[mudanças de banco](../plano_ia_hibrida_atendimento.md#banco-ia).

## 1. Política aceita na primeira versão

O limite é uma condição para **admitir um novo ciclo de atendimento com IA**:

- Se o consumo conhecido aplicável está abaixo do limite, o ciclo pode usar IA.
- O ciclo autorizado pode alcançar ou ultrapassar o limite ao terminar.
- Quando o próximo ciclo encontra `qtd_usada >= limite`, segue no determinístico.
- A comparação inclui igualdade; não é necessário ultrapassar para aplicar fallback.
- Salvar todo consumo conhecido, inclusive o excedente. Não limitar o contador
  ao teto, descartar tokens ou rejeitar sua gravação por uma constraint.
- Não reservar previamente tokens nem implementar controle estrito de cota
  nesta primeira versão. Isso fica para a evolução descrita neste documento.

Plus tem limite de unidade e de chat. Pro tem limite apenas de chat, mas seu
total de unidade também é registrado. Básico não admite IA nem cria novos usos
de IA. Limites técnicos por ciclo, regras de atendimento, locks, idempotência e
tratamento de falhas continuam necessários.

## 2. Brecha da unidade Plus: totalização a cada cinco minutos

O `worker_flow` consulta o total já gravado em `uso_ia_unidade`. Ele incrementa
os usos dos chats, mas não o agregado da unidade. O `worker_consumo_ia_unidade`
soma `qtd_usada` dos chats ligados por `id_uso_unidade` e **substitui** o total
da unidade a cada cinco minutos. Não soma novamente ao agregado anterior.
O ciclo percorre os usos existentes do mês atual de todas as unidades, inclusive
Pro. Inclui o consumo dos chats cujas conversas já encerraram; não filtra somente
conversas ativas. Meses antigos alterados por conclusões tardias também são reapurados.

Exemplo ilustrativo, sem definir valores comerciais das cotas:

| Momento | Evento | Consequência |
| --- | --- | --- |
| 10h00 | Limite da unidade: 100.000; total apurado: 90.000 tokens. | Novos ciclos podem usar IA se seus chats também tiverem margem. |
| 10h00 a 10h05 | Cinco chats consomem 3.000 tokens cada, registrados pelo `worker_flow`. | A soma chega a 105.000, mas o agregado ainda mostra 90.000. |
| 10h05 | O worker recalcula e grava 105.000. | Novos ciclos que consultarem esse total seguem no determinístico. |
| Depois da apuração | Um ciclo autorizado anteriormente ainda termina. | Seu consumo também é salvo; a próxima apuração pode aumentar o total. |

A brecha pode abranger **vários chats e ciclos**, não necessariamente uma única
chamada de API. Um ciclo novo não é autorizado quando a leitura de admissão já
mostra o limite atingido. Ciclos admitidos antes dessa atualização podem concluir;
isso não autoriza novas interações com IA naquele período.

Cinco minutos continua sendo a cadência planejada. Se o processo/VM reiniciar,
o banco ficar indisponível ou a apuração demorar/falhar, sua conclusão pode atrasar.
Esse totalizador consulta o banco; não espera uma consulta Meta/OpenAI. Se o
worker atrasar ou parar, a janela de defasagem pode passar de cinco minutos.
A cadência não garante uma quantidade máxima de tokens excedentes. Registrar a
última apuração e as falhas permite identificar essa situação. Não converter erro
em zero nem atualizar falsamente o horário de sucesso. Pro continua totalizado,
mas não sofre fallback por total da unidade; seus chats continuam limitados.

## 3. Brecha do chat Plus/Pro: último ciclo autorizado

O `worker_flow` verifica o uso mensal do chat antes de admitir o ciclo. Cada
requisição efetivamente realizada tem seus tokens conhecidos registrados e
incrementados uma única vez no chat. Essa atualização não espera o totalizador.

Exemplo ilustrativo:

1. Chat tem limite de 10.000 e já usou 9.800 tokens.
2. A unidade permite IA e, no Plus, seu agregado ainda está abaixo do teto.
3. O ciclo é autorizado porque `9.800 < 10.000`.
4. Análise, eventuais continuações e resposta usam 500 tokens ao todo.
5. O consumo passa a 10.300. A resposta autorizada pode ser concluída.
6. Na próxima mensagem/ciclo do cliente, `10.300 >= 10.000`: usar determinístico.
7. Outras conversas desse chat no mesmo mês compartilham o contador esgotado.

Se terminar exatamente em 10.000, o próximo ciclo também usa fallback. A exceção
autoriza o **último ciclo lógico**, não chamadas ou retries ilimitados. Um ciclo
pode conter chamadas adicionais justificadas, respeitando os limites do provedor
e as validações do sistema. A decisão mais recente de 02/10 não estabelece cota
extra de tokens por ciclo, mas limita a fase de IA a 90 segundos no total, com
fallback ao vencer o prazo. Continuações não reiniciam esse relógio nem autorizam
loops de novas chamadas sem finalidade.

Serializar o processamento do mesmo chat e recuperar a decisão persistida em
retries. Execução duplicada do worker não é novo ciclo autorizado. Replay sem
nova chamada não soma tokens de novo; chamada realmente realizada tem seu
próprio consumo, mesmo quando a resposta final usa fallback.

## 4. Renovação mensal e relacionamentos

Chat é o vínculo permanente entre cliente e unidade; conversa é um episódio
desse chat. Existe no máximo um `uso_ia_chat` por chat/mês e um `uso_ia_unidade`
por unidade/mês. Todos os usos dos chats do mesmo mês/unidade apontam por FK
ao mesmo registro de uso da unidade.
Permanece no máximo uma conversa ativa por cliente/unidade. As conversas são
sucessivas: o consumo já registrado na encerrada permanece no mês e a nova
conversa ativa acrescenta ao mesmo contador, sem permitir simultaneidade.

O intervalo é `[primeiro dia às 00h, primeiro dia do próximo mês às 00h)`, no
fuso definido para a unidade, sem fixar 30 dias. Quando `agora >= data_final`,
o `worker_flow` resolve o mês atual. Primeiro obtém/cria o uso da unidade; depois
obtém/cria o uso do chat e sua FK. Se outro chat/worker já criou a linha mensal
da unidade, reutiliza-a. Unicidade e transação curta protegem essa concorrência.
O totalizador não cria linhas; sem tráfego, não é preciso criá-las à meia-noite.

O novo período tem contador e limites próprios, permitindo IA se as demais
regras permitirem. O anterior mantém o consumo real, mesmo acima da cota.
Conclusões tardias pertencem ao período da requisição e exigem reapuração do
agregado correspondente, conforme o plano de cotas.

## 5. Limites desta aceitação

Excesso conhecido é permitido. Também foi aceita a possível subcontagem por
tokens não recuperados após timeout/queda. Desconhecido continua desconhecido;
não passa a ser zero nem consumo confirmado. A
[conciliação automática](ideia_conciliacao_consumo_ia.md) fica para uma evolução.
O fallback depende de o contador persistido consultado atingir o limite; não
garante detectar tokens omitidos nem bloquear pelo consumo real exato.

Não relaxar isolamento entre unidades, locks, unicidade mensal, bloqueios de
atendimento ou proteção contra contagem duplicada. Não manter transação SQL
aberta durante chamada externa. Cota esgotada causa fallback, não bloqueio de
30 dias, encerramento da conversa ou mudança de assinatura.

## 6. Estratégias a avaliar depois da implantação

Objetivo futuro: impedir admissões que possam ultrapassar a cota, preservando o
atendimento e a contabilização. A estratégia ainda não foi escolhida e não é
requisito para liberar a versão inicial. Avaliar com dados reais:

1. Controle de admissão atualizado para a unidade, compartilhado pelos workers,
   mantendo o totalizador para conferência e painel.
2. Reserva atômica de tokens nos dois níveis, com entrada conhecida e
   saída/continuações limitadas. Soma imediata sem proteção de concorrência não basta.
3. Conciliação entre reserva e uso efetivo, inclusive chamadas interrompidas,
   sem liberar saldo possivelmente consumido nem prender reservas indefinidamente.
4. Política para agregado desatualizado, falhas, retries e virada mensal,
   preservando Pro sem teto da unidade e os limites de chat em ambos os planos.

Qualquer mudança exige decisão explícita, atualização dos planos e testes.
Não apresentar o limite como estrito enquanto essa solução não existir.

## 7. Registro obrigatório quando a IA for implementada

Na implantação, sinalizar esta limitação conhecida nas regras de negócio e na
documentação de consumo/quotas, workers e banco do projeto. Comentários junto à
admissão e à totalização devem explicar o excesso permitido e referenciar esta
evolução futura. Se a pasta de IA mudar, atualizar os links. Não perder o registro
nem afirmar que a brecha já foi eliminada.

Verificações previstas para a implementação:

- Chat conclui ciclo que iguala/ultrapassa o teto; próximo ciclo usa fallback em Plus/Pro.
- Unidade Plus aceita vários ciclos com agregado defasado; apuração `>= limite`
  impede novas admissões e contabiliza conclusões de ciclos já admitidos.
- Pro ignora teto da unidade, respeitando o do chat; Básico não chama IA.
- Falha do totalizador preserva total/horário anteriores e fica registrada.
- Retry não duplica uso; limites técnicos impedem continuação indefinida do ciclo.
- Virada exatamente às 00h reutiliza/cria registros sem duplicar, misturar meses
  ou apagar excedentes anteriores; novo chat do mês reutiliza o uso da unidade.
- Painel exibe consumo real e última apuração, sem cortar o valor no limite.
