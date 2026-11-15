# Atendimento híbrido do Supera

Estudo teórico arquivado. O Supera atende por regras determinísticas em 24 etapas e 32 transições. A abertura já aproveita dados da primeira mensagem e, nas unidades integradas, pode completá-los pela FireAds. Há três lembretes. O painel permite acompanhar o atendimento. Nenhuma dessas funções depende de um modelo generativo.

## Para que serviria a IA

O objetivo era entender dúvidas expressas em linguagem livre, aproveitar dados antecipados na conversa atual e adaptar a redação sem perder a pergunta que precisa de resposta. A aplicação continuaria decidindo quais dados são válidos, qual transição é permitida e o que pode ser enviado. Uma conversa continuaria tratando do titular ou de um dependente. Nome, e-mail e outras respostas de conversas encerradas não justificariam, sozinhos, personalizar uma nova abertura.

A proposta previa participação até o encaminhamento comercial: com link, até sua apresentação; sem link, durante a escolha de turno, quando necessária, e a entrega do contato do consultor. O Funil aproveitaria dados já persistidos. Os textos e opções atuais seriam a alternativa quando a geração falhasse ou estivesse desligada. Uma chamada por turno e um teto total proposto de 90 segundos limitariam a espera. A adequação desse prazo ao atendimento continuaria em aberto.

## Consumo e limites

O desenho distinguia Básico determinístico, Plus e Pro com assistência opcional. Tokens seriam a unidade de consumo, com limites por chat e um teto por unidade no Plus. O limite por chat seria mensal no Plus e no Pro. Na hipótese discutida, as apurações da unidade Plus teriam intervalo de cinco minutos. Os valores e o modelo ficariam em aberto. Duas diferenças importam para o orçamento: uma geração já autorizada pode superar o saldo restante; uma chamada cobrada pode perder o registro local em caso de falha. Limite estrito e conciliação seriam escolhas de produto.

A ideia antiga de personalizar um lembrete foi formulada quando só havia dois. Hoje o primeiro pergunta se o cliente viu a mensagem aos 15 minutos, o segundo retoma o atendimento e o terceiro encerra. Qualquer hipótese de personalização teria de identificar o lembrete por sua finalidade e respeitar os prazos, a janela de atendimento e o encerramento. O fluxo vigente está nas [regras de negócio](../REGRAS_DE_NEGOCIO.md).

## Hipóteses associadas

| Hipótese | Questão a resolver |
| --- | --- |
| Agrupar mensagens seguidas | Quando uma frase complementa a anterior e quando começa um novo turno? A ordenação e a proteção contra duplicidade continuam necessárias. |
| Receber áudio | Como pedir confirmação de transcrições ambíguas e limitar armazenamento de mídia e custo? |
| Encaminhar para uma pessoa | Como deixar explícito quem responde, pausar o bot e os lembretes e definir uma retomada sem respostas simultâneas? Hoje o painel é de leitura. |
| Atender várias pessoas | Como vincular idade, respostas e encaminhamento à pessoa certa, sem misturar perfis? |
| Manter memória | Que informação da conversa atual precisa durar e quem pode consultá-la? O cadastro de outro atendimento não deve substituir a coleta. |
| Avaliar qualidade | Comparar dúvidas resolvidas, retomadas corretas, erros de interpretação, tempo e custo, com casos revisados e sem identificação de clientes. |

As referências editoriais do Supera continuam úteis para discutir essas hipóteses. A implementação vigente está no [catálogo de etapas](../core/database/deploy_database/povoar_etapas.py) e nas [mensagens determinísticas](../core/integrations/whatsapp/messages/README.md).
