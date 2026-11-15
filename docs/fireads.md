# FireAds no atendimento do Supera

A integração é configurada por unidade. As personalizações comerciais ficam em `atendimento_customizado`. O webhook recebe mensagens e o worker de fluxo conduz a conversa. A consulta HTTP à agência e a entrega comercial têm workers próprios.

## Abertura e atribuição

O [worker de fluxo](../workers/worker_flow/coleta_abertura.py) congela a primeira mensagem e o contexto de coleta por conversa. Com link, procura nome do titular, e-mail e para quem é o atendimento. Sem link, acrescenta manhã, tarde, noite ou sábado. A coleta da mensagem também funciona sem FireAds. Havendo integração e campos ausentes ou ambíguos, o flow registra uma consulta pendente e libera o ciclo para outros atendimentos. O worker de consulta lê a aba geral e grava o resultado. O flow aplica o resultado à abertura correspondente e pergunta os campos pendentes nas respectivas etapas.

O [seletor](../core/integrations/fireads/aba_geral.py) considera as representações equivalentes do telefone. Entre linhas de formulário elegíveis escolhe a data válida mais recente, com desempate pelo maior número de linha. Sem data válida, usa a maior linha elegível. Os canais elegíveis são Meta Ads, Google Ads, Orgânico Site e Chat Fire. Nome, e-mail e destinatário podem divergir do registro e não servem de chave de busca. A mensagem aceita prevalece na coleta. Ausência de linha elegível após leitura e falha técnica são resultados distintos.

A consulta inicial, quando necessária, pode identificar a origem. Com a coleta completa, a origem pode ficar pendente. O worker periódico de origem lê o canal e o anúncio para as conversas elegíveis que dispensaram a consulta inicial. Atua a cada duas horas por padrão, a partir da data configurada. Uma consulta anterior que já concluiu ausência não participa dessa seleção. A entrega comercial volta a conferir o registro. O campo `Anuncio` se aplica a Meta e Google. A atribuição persiste em `conversa.contexto_fireads`; os códigos comerciais compartilhados não distinguem todas as origens.

## Entrega e recuperação

O worker do Funil prepara a entrega por conversa. Com FireAds, seleciona a linha elegível pelo telefone, atualiza os campos permitidos e compõe as observações preservando o conteúdo anterior. Sem formulário elegível, o caminho de criação é orgânico. Linhas de indicação e lead franqueador são preservadas. Um canal desconhecido impede a criação automática por engano. Quando a API recusa explicitamente a criação por telefone duplicado, é possível reutilizar um registro Orgânico compatível no ciclo seguinte. Em caso de timeout, o worker reconcilia a tentativa anterior. A [seleção do destino](../core/integrations/fireads/destino_dashboard.py), a [sincronização](../core/integrations/fireads/sincronizacao_coleta.py) e o [worker](../workers/worker_funil/fireads.py) definem os casos de reutilização, duplicidade e recuperação.

O Funil só é liberado depois da confirmação do dashboard para a unidade integrada. Falha e timeout deixam a entrega pendente. Após resultado incerto, a recuperação usa decisão persistida, referência da linha, observações e recibos para verificar o que foi escrito. O serviço externo e a confirmação no banco local não compõem uma única transação.

Os tempos, reservas e efeitos de cada worker estão no [inventário](../workers/README.md). O [painel](monitoramento_fireads_filtros_relatorios.md) lê as atribuições já registradas. As migrações históricas aplicáveis ao banco existente estão em [deploy/migrations](../deploy/migrations).
