# Conversas e relatórios por origem

O painel de monitoramento é de leitura e respeita o acesso da unidade e o período escolhido. Sua origem de dados é o PostgreSQL. O painel não consulta a planilha ao abrir uma tela.

| Tela | O que entra na contagem |
| --- | --- |
| Conversas | Última conversa de cada chat cliente × unidade **dentro do período**. Os filtros de titular, dependente, avaliadas, follow-up, comercial, Funil e origem consideram essa conversa. |
| Relatórios de origem | Todas as conversas do período. Cada atendimento conta na sua origem. O indicador de contatos únicos conta cada contato uma vez. |
| No Funil | O relatório usa os envios confirmados conforme o recorte da métrica. Pendência no dashboard ou tentativa sem confirmação não equivale a envio confirmado. |

Nas unidades integradas, o filtro FireAds inclui Google Ads, Meta Ads, Chat Fire e Orgânico Site. O filtro **100% orgânico** é separado. Enquanto a origem está pendente, o atendimento permanece sem origem identificada. O painel lê o JSON de atribuição e as evidências históricas compatíveis pelos [repositórios de monitoramento](../core/repositories/monitoramento/painel.py).

Em Relatórios, o card de origem apresenta atendimentos e envios ao Funil por canal. As seções de anúncios de Meta e Google agrupam o criativo do campo `Anuncio`, inclusive “não informado” quando a origem daquele canal está confirmada. A janela de perfis detalha o canal ou anúncio e o período, distinguindo titulares, dependentes e faixas etárias. A [agregação](../callback/monitoramento/origens.py) e a [interface](../callback/monitoramento/static/monitoramento/js/origens.js) definem os grupos e seus denominadores.

A [integração FireAds](fireads.md) descreve quando a abertura, a verificação periódica e a entrega podem identificar o canal. O [diagnóstico de novembro](diagnostico_financeiro_fireads_20261108.md) mostra a diferença entre o registro visível agora e o resultado disponível ao iniciar uma conversa.
