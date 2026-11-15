# Plano prático de suporte a user_id no WhatsApp

**Estado em 14/11/2026 — proposta pendente.** Base de comparação: V1.20.0, correção posterior `a7c110e` e ajustes locais de validação financeira. Este roteiro descreve mudanças a desenvolver e validar em uma cópia do projeto. O [contrato de identidade](user_id_plano_logico_teorico.md) define quais evidências permitem associar dois identificadores.

## 1. Fotografar a base e validar a capacidade da API

Partir da [estrutura declarativa atual](../core/database/deploy_database), dos [models](../callback/webhook/models.py), do [catálogo](../core/database/deploy_database/povoar_etapas.py) e das [32 transições](../core/database/deploy_database/etapa_transicao_script.py). Registrar as contagens de clientes, chats, conversas ativas por unidade, etapas por ID, transições por evento, vínculos de monitoramento, mensagens e recibos. Inventariar as dependências do telefone e da numeração de etapa em SQL, JSON, filas, caches, Django, filtros, relatórios, utilitários de manutenção e testes.

Em uma cópia do PostgreSQL, esta consulta localiza colunas que merecem inspeção. Revisar também funções, gatilhos, índices, constraints e chaves em JSON que a consulta não enumera.

```sql
SELECT table_name, column_name, data_type, is_nullable
FROM information_schema.columns
WHERE table_schema = 'chatbot'
  AND (column_name ILIKE '%waid%' OR column_name ILIKE '%wa_id%'
       OR column_name ILIKE '%telefone%' OR column_name ILIKE '%etapa%'
       OR column_name IN ('user_id', 'username', 'id_portfolio'))
ORDER BY table_name, ordinal_position;
```

O projeto fixa PyWa 4.5.0. O [cliente do turno](../core/integrations/whatsapp/pywa_functions/cliente.py) já envolve `request_contact_info` para prefixo e ação pré-envio. Validar em número de teste o envio por BSUID, o retorno da solicitação e a forma exata do webhook na versão Graph usada pela unidade. Conferir os [quatro fixtures](../payloads) e acrescentar amostras anonimizadas representativas. Confirmar qual escopo de identidade a Meta garante antes de habilitar uma unidade. O campo opcional proposto `unidade.id_portfolio` começa nulo, sem inferir vínculo entre unidades. Para o evento de troca de user_id, exigir contrato e amostra próprios antes de aceitar qualquer alteração de vínculo.

## 2. Expandir o modelo de dados

- Tornar explícito o WA ID canônico do cliente. O nome atual é `cliente.waid_telefone`. A coluna alvo `wa_id` admite nulo para um cliente provisório e continua única para telefones conhecidos. Preservar os dígitos existentes e localizar leitores antigos antes da troca de nome.
- Criar `chatbot.user_id_cliente` com chave própria, FK para cliente e FK para unidade. Garantir unicidade em `(user_id, id_unidade)` e `(id_cliente, id_unidade)`. Reservar campo opcional de username para apresentação no escopo correto. A tabela de vínculos começa vazia.
- Prever snapshots de identidade em conversa, fila e histórico, diferenciando a entrada original do destinatário canônico. Preencher o retrato das conversas legadas com o WA ID conhecido quando a fonte for inequívoca. Preservar WAMIDs, ID de chat/conversa, mensagens, atribuição, preferências, ciclos e recibos. Novos campos opcionais começam nulos quando não existe evidência.
- Entregar DDL final de instalação em Python, models Django consistentes e SQL de migração separado para banco existente. Confirmar num banco montado do zero e numa cópia migrada que ambos produzem o mesmo contrato.

## 3. Receber e conciliar a identidade

No [webhook](../callback/webhook/services), diferenciar o remetente em `value.contacts[]` de um cartão em `messages[].contacts[]`. Validar assinatura e unidade, congelar o tipo/valor original na fila e preservar a deduplicação por WAMID. Aceitar como prova de compartilhamento somente o retorno oficial `origin=contact_request`, com exatamente um WA ID utilizável do próprio remetente e contexto de solicitação pendente compatível. Número digitado, cartão comum, contato ambíguo, outra unidade ou evento de sistema sem contrato confirmado ficam sem efeito de vínculo.

Em [atendimento](../core/repositories/atendimento), [segurança](../core/repositories/seguranca) e [transações do flow](../workers/worker_flow/transacoes), resolver WA ID conhecido, alias da unidade e provisório em uma ordem única. Bloquear em ordem estável, reler estado e aplicar vínculo, reconciliação, efeitos do turno e checkpoint de forma consistente. Preservar a conversa provisória e seu histórico ao reassociá-la. Conferir a unicidade do chat cliente × unidade antes de mover FKs. Se houver conversa canônica incompatível, dois donos comprovados ou lock fresco de outro turno, impedir envio ou fusão ambígua. Reagendar contenção e registrar colisão para resolução. Excluir um provisório somente após verificar referências e confirmar os efeitos.

**Caso previsto de ativação da privacidade.** Com prova oficial, transação e posse válidas, se o telefone já pertencer ao cadastro antigo da mesma pessoa, preservar nome coletado na etapa 1 e a profissão válida mais recente conforme o contrato de reconciliação. Reassociar a conversa provisória ao cadastro e chat canônicos. Se houver conversa canônica anterior ativa da mesma unidade, encerrá-la com o motivo proposto `ativou_privacidade`, preservando seu histórico. Se ela já estava encerrada com bloqueio vigente, preservar a expiração original e encerrar a provisória com `bloqueio_reconciliado`, sem envio nem prorrogação do prazo. Não copiar recibos de follow-up de uma conversa para outra. O tratamento dessa coincidência comprovada é diferente de uma colisão entre vínculos incompatíveis.

Manter a chave original do item durante fila, ordenação, retry e autocura. Após prova, os aliases da unidade compartilham a proteção de flood e bloqueio. Somar WAMIDs distintos nas janelas, preservar TTLs e o limite atual de 15 em cinco segundos. Adaptar [Redis e fallback em memória](../core/cache), guardas SQL, desbloqueio e limpeza de contato. Evento repetido não renova uma associação ou reseta uma conversa posterior.

## 4. Inserir a solicitação de contato no catálogo

Preservar a decisão original de reservar a **nova etapa 2** ao compartilhamento oficial. A atual etapa 1 continua sendo a identificação inicial. As atuais etapas 2–24 deslocam-se uma posição. O resultado previsto é um catálogo de 25 etapas. Gerar o mapa por significado de cada evento a partir das 32 arestas atuais e acrescentar as entradas e saídas da etapa nova. Apurar a quantidade final de arestas após definir esses eventos.

| Entrada ou etapa atual | Comportamento a transportar |
| --- | --- |
| Abertura na 1, 2 ou 4 | Com telefone confirmado, entrar na futura 1, 3 ou 5 conforme os campos coletados. Sem telefone confirmado, coletar o nome se faltar e solicitar o contato antes de seguir. Com nome já aceito, ir direto à solicitação. |
| Atual 1 → 4 com destinatário conhecido | Com identidade resolvida, preservar o atalho para a futura 5. Com contato pendente, guardar o destino e retomar conforme a coleta após a nova 2. |
| Atuais 7, 8, 9 e 10 | Preservar aceite, adiamento, retorno, tratamentos e salto do e-mail já coletado. O retorno atual 8 → 9 torna-se 9 → 10. |
| Triagem 11–17 e reserva 18–20 | Preservar as seis respostas e os três caminhos ao concluir a triagem: pedir turno, encaminhar ao consultor com turno já aceito ou apresentar link. |
| Comercial e pesquisa 19–24 | Recalcular elegibilidade comercial pelos papéis das etapas. Avaliação, comentário e encerramento atual da 24 passam a terminar na 25. |

Atualizar eventos, resolução, templates, senders e efeitos, DDL, FKs e `CHECK` de etapa, seleção de workers e gráficos. Remapear `contexto_coleta.etapa_inicial` onde presente, instruções pendentes de abertura e `followup_retomada.id_etapa`. Usar mapeamento explícito em duas fases ou catálogo paralelo para evitar colisões de IDs. Preservar o significado de cada linha histórica e o vínculo de cada transição. **O contador de follow-up 0–3 não é número de etapa.**

## 5. Preservar coleta, follow-up e integrações

- **Abertura e FireAds.** Conservar a primeira mensagem e os campos aceitos no [contexto de coleta](../workers/worker_flow/coleta_abertura.py) enquanto faltar telefone. Depois da prova, reavaliar somente as pendências da mesma conversa e respeitar o checkpoint de consulta. As buscas, a atribuição, as variantes telefônicas e o dashboard/Funil usam o telefone confirmado. Não gravar “orgânico” por falta de telefone.
- **Envio e recuperação.** A entrada inicial pode responder ao BSUID persistido enquanto o telefone estiver pendente. Depois do vínculo, o sender usa o WA ID canônico relido do banco. Confirmar que prefixos, indicador de digitação e recibos continuam funcionando em ambos os caminhos.
- **Follow-up.** Manter os marcos de 15 minutos, 7 horas e 14 horas, a janela desde a última mensagem do cliente, o encerramento pelo terceiro envio e o corte das conversas legadas. Fora da etapa nova, preservar o processamento normal da primeira reação. Na solicitação de contato, prova válida pode avançar para o destino pendente. Resposta sem prova repete a solicitação com a saudação vigente, sem avançar. Confirmar a nova faixa elegível, incluindo a etapa de turno só nas unidades sem link.
- **Painel e exportação.** Preservar autenticação por unidade, última conversa do chat no período em Conversas e todas as pertinentes em Relatórios. Usar WA ID, username ou rótulo de contato não compartilhado na apresentação. Impedir exposição do BSUID em HTML, pesquisa, CSV e logs de frontend. Manter exportações de telefone e tratamento de ausências. Os validadores de profissão, endereço, financeiro e reforço e as regras de idade continuam no seu estágio funcional.

## 6. Aceite, ativação e retorno

| Ensaio | Resultado exigido |
| --- | --- |
| WA ID legado, com/sem FireAds e com/sem link | Mesmo destinatário, coleta e destino lógico do catálogo antigo. |
| Apenas BSUID, contato válido e reentrega do mesmo WAMID | Um vínculo na unidade, um avanço da conversa, um efeito de envio. |
| Cartão alheio, nome igual, username alterado, prova fora de etapa | Nenhum telefone promovido por engano, sem cruzamento entre unidades. |
| Chegada em paralelo pelos dois aliases, Redis indisponível, queda antes/depois do commit | Ordem por turno, bloqueios e recibos preservados. Replay retoma o checkpoint. |
| Conversa em triagem, reserva, recebimento de follow-up, entrega comercial em andamento | FKs e contextos apontam para a mesma etapa funcional. Sem reenvio de follow-up ou de entrega por causa da migração. |
| Painel e manutenção | Isolamento por unidade, exportação e remoção abrangendo aliases sem exibir BSUID. |

Implementar testes unitários de extração/identidade/rotas, testes de integração em PostgreSQL e testes de cache com duas unidades e dois clientes. Ensaiar restauração com a mesma fotografia inicial, executar os testes de coleta, PyWa, transições, follow-up, FireAds, monitoramento e segurança já existentes e comparar contagens e amostras históricas.

Na implantação futura, coordenar pausa dos produtores e consumidores durante a renumeração. Validar fila, catálogo, conversas ativas, recibos e últimos destinos antes de liberar envios. Restringir o piloto a uma unidade e verificar recebimento, compartilhamento e retomada reais no número de teste. Se o piloto falhar, suspender novas entradas pelo BSUID e preservar dados para conciliação. O código anterior só pode voltar a consumir o banco com a numeração e o contrato que ele entende. Restaurar a fotografia apenas com um plano para conciliar eventos e envios posteriores. O aceite desse ensaio e a confirmação do envelope real permanecem condições para uma implementação futura.
