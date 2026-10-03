# Evolução futura: conciliação do consumo de IA não registrado

Revisão: **02/10/2026**. Status: **ideia futura; risco aceito na primeira versão**.
O responsável pelo projeto aceita que uma falha possa deixar tokens consumidos
sem contabilização local. A recuperação automática desse consumo não é requisito
para implementar a IA. Registrar o risco e os indícios de falha desde o início.

Referências: [plano principal](../plano_ia_hibrida_atendimento.md),
[chat e limites](../plano_ia_hibrida_atendimento.md#consumo-ia),
[banco](../plano_ia_hibrida_atendimento.md#banco-ia) e
[excesso de cota permitido](ideia_limites_ia_sem_ultrapassagem.md).

## 1. Como o consumo pode ficar desconhecido

Uma chamada externa e uma transação no PostgreSQL não são uma operação atômica.
Exemplo: OpenAI processa a chamada, mas o worker cai antes de salvar seu uso.
Também pode ocorrer timeout depois de a requisição chegar ao provedor, sem que
o worker receba o resultado. Um retry indica tentativa incompleta; sozinho não
revela se houve processamento remoto, quais tokens foram usados ou se o commit
local chegou a ocorrer.

| Situação | Tratamento inicial |
| --- | --- |
| Falha comprovadamente antes da chamada externa | Nenhum consumo dessa chamada; não inventar tokens. |
| Chamada processada, resultado/uso não recuperado | Tentativa incompleta ou consumo desconhecido; não preencher zero confirmado. |
| Uso e incremento local já persistidos, ciclo falha depois | Recuperar registros e não incrementar novamente. |
| Retry efetivamente faz outra chamada | Registrar o uso conhecido dessa nova tentativa uma vez; não apagar a anterior. |
| Falha da Meta depois de persistir o uso de IA | Tokens continuam contabilizados; não exigir nova geração só por falha de envio. |

A existência e frequência dessas situações serão observadas no piloto. Não
prometer diferença sempre pequena, falha impossível ou causa exclusivamente
externa: reinício de processo, recursos esgotados, configuração e defeitos de
software também podem interromper uma execução. Testes reduzem o risco, mas não
criam atomicidade entre o provedor e o banco.

## 2. Decisão para a implementação atual

- Manter registro por tentativa, uso conhecido e incremento único do chat na
  mesma transação. Identificadores e horários disponíveis ajudam a recuperação.
- Não fazer conciliação global nem pausar o sistema automaticamente após um retry.
- Usar os contadores efetivamente persistidos para a admissão. Uso não recuperado
  pode deixar o contador abaixo do consumo real; essa subcontagem é aceita.
- Não substituir desconhecido por zero nem por estimativa apresentada como exata.
- O próximo ciclo usa determinístico quando o contador aplicável lido é
  `>= limite`. Isso não garante bloqueio no instante em que o consumo real não
  registrado cruza a cota. Se faltar uso no contador, o bloqueio pode ocorrer
  depois ou nem ocorrer naquele mês, caso ele termine antes de o contador atingir o teto.

Não alterar a assinatura ou bloquear o cliente por causa dessa divergência.
Preservar locks, recuperação de mensagens e as regras do atendimento.

## 3. Proposta do usuário: comparar banco e OpenAI após um retry

Ideia a estudar: após recuperar um ciclo que falhou, registrar o consumo novo
e consultar o total da OpenAI no mesmo intervalo usado para somar o banco:

```text
diferenca = tokens_openai_no_intervalo - tokens_locais_no_mesmo_intervalo
```

Preferência confirmada em 02/10: comparar o consumo de todos os chats do banco
no mesmo mês, sem consultar toda a história. Somar cada consumo uma vez; o total
por unidade já representa os mesmos tokens e não deve ser somado novamente.
Para um mês ainda em andamento, fixar também um instante final comum já passado:
consultas feitas em instantes diferentes não podem comparar totais móveis.
As condições de escopo e completude abaixo continuam necessárias. O intervalo
pode ser reapurado posteriormente, sem pausar os atendimentos atuais.

A hipótese é que a diferença revele os tokens da tentativa anterior não gravados.
Exemplo controlado: OpenAI informa 12.500, banco contém 12.000, e há exatamente
uma tentativa sem uso registrado. Os 500 são uma divergência candidata dessa
tentativa, desde que ambos os totais estejam completos, com o mesmo escopo e
sem outras inconsistências. Não atribuir automaticamente o saldo ao último retry.

Uma diferença positiva pode reunir várias tentativas perdidas ou outros usos.
Diferença zero significa apenas que os totais consultados coincidem: não prova
em qual ponto o ciclo falhou. Erros de soma opostos também podem se compensar.
Diferença negativa exige investigação, nunca redução automática de consumo.

## 4. Consulta disponível e condições para comparar

Verificação documental em 01/10/2026: a Usage API oferece
`GET /v1/organization/usage/completions`, com `start_time` inclusivo,
`end_time` exclusivo, agregações de minuto/hora/dia, filtros de projeto/chave e
paginação. A referência usa credencial administrativa. Retorna tokens de entrada
e saída agregados; não fornece o `id_chat` local como dimensão.
[Referência oficial](https://developers.openai.com/api/reference/python/resources/admin/subresources/organization/subresources/usage/methods/completions).

Antes de confiar na diferença, validar:

1. Mesmo projeto/chaves/modelos e tipos de chamadas em ambas as fontes, excluindo
   experimentos e outros sistemas ou incluindo-os de forma correspondente.
2. Mesmo intervalo absoluto e critério temporal. O mês local usa o fuso da unidade;
   não comparar automaticamente um mês local com um dia/mês UTC. Investigar como
   a API aloca chamadas que atravessam a fronteira, sem presumir equivalência com
   o horário de admissão local.
3. Todas as páginas da resposta e todos os registros locais pertinentes. Para
   períodos menores que o mês, usar as requisições individuais; os totais mensais
   não bastam para reconstruir uma hora específica.
4. Mesma métrica: entrada + saída, sem somar novamente cache/raciocínio. Não
   somar `uso_ia_chat` com `uso_ia_unidade`: representam o mesmo consumo.
5. Chamadas e gravações locais do recorte concluídas, sem acertos pendentes que
   tornem a fotografia local incompleta. Reconsultar o período para conferir.

A referência consultada não estabelece uma garantia de completude imediata após
cada chamada. Não presumir que a primeira leitura após o retry já contém tudo.
Mesmo com totais completos, um saldo global não identifica qual chat/unidade
deve recebê-lo quando há várias tentativas sem contabilização.

## 5. Evitar uma pausa geral apenas para comparar totais

O usuário sugeriu pausar o sistema durante a comparação para impedir consumo
concorrente. Essa hipótese fica documentada, mas **não será implementada agora**.
Uma pausa, sozinha, não resolve chamadas já em voo nem a disponibilidade dos
dados no provedor.

Alternativa futura preferível: escolher um intervalo passado e fechado, esperar
as conclusões locais pertinentes e comparar sempre esse recorte. Novas chamadas
posteriores ficam fora dele; o atendimento pode continuar. Repetir a conferência
sem aplicar ajustes duplicados. Validar as fronteiras e a completude antes de
atribuir qualquer diferença. Não existe necessidade estabelecida de pausar todo
o chatbot, e a conciliação não deve virar parte síncrona de cada retry.

## 6. Recuperação específica antes de usar uma diferença global

Se o identificador da resposta foi persistido e ela está armazenada e acessível,
avaliar `GET /v1/responses/{response_id}` para recuperar o uso daquela resposta.
O objeto pode trazer `usage`. O identificador HTTP de requisição não é
automaticamente o identificador da resposta usado por esse endpoint.
[Recuperação oficial](https://developers.openai.com/api/reference/python/resources/responses/methods/retrieve).

A possibilidade depende da retenção/configuração e do resultado ainda disponível;
não assumir recuperação se o ID se perdeu ou a resposta não foi armazenada.
Não mudar a política de armazenamento de conversas só para viabilizar esta ideia.
[Controles de dados](https://developers.openai.com/api/docs/guides/your-data).

Se o uso individual for recuperado, incrementar uma única vez no período e chat
corretos; reapurar o agregado da unidade. Sem evidência individual suficiente,
registrar divergência para investigação, sem distribuir tokens arbitrariamente.

## 7. Futuras verificações e documentação de produção

Quando essa evolução for priorizada, testar falha antes/depois da chamada e do
commit, duas tentativas perdidas, uso externo no mesmo projeto, paginação,
fronteiras de mês/fuso, resposta indisponível e ajuste executado duas vezes.

Na primeira implantação da IA, a documentação de banco, workers e consumo deve
informar que tokens não recuperados podem ficar fora da cota contabilizada e
referenciar este documento. A solução permanece futura; preservar os links se
a pasta for reorganizada. Modelo, orçamento e cotas numéricas serão escolhidos
por último, conforme solicitado, e não são definidos por esta proposta.
