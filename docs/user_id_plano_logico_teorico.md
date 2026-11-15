# Identidade do cliente no WhatsApp

Proposta preservada para uma eventual retomada do Supera. O atendimento arquivado trabalha com o telefone/WA ID. O identificador do usuário que acessa o monitoramento pertence à autenticação Django. Os [exemplos de envelopes](../payloads) e o método de solicitação de contato no adaptador PyWa são referências de integração. O suporte de ponta a ponta a clientes que apresentam somente BSUID permanece proposto.

## Quando um cliente oculta o telefone

A proposta permite iniciar o atendimento com o identificador fornecido pela Meta (`user_id`, também chamado BSUID), no contexto da unidade que recebeu o evento. O cliente pode informar o nome e compartilhar oficialmente o próprio contato. Com o telefone confirmado, a mesma conversa segue para o próximo dado necessário. Para quem já chega com WA ID conhecido, continuam valendo os atalhos de coleta do Supera.

| Evidência | Uso pretendido |
| --- | --- |
| Apenas WA ID | Resolver o cliente pelo telefone e manter o percurso atual. |
| WA ID e BSUID do mesmo remetente, no mesmo envelope autenticado | Vincular depois de verificar unidade, concorrência e compatibilidade com os vínculos existentes. |
| Apenas BSUID | Usar identidade provisória daquela unidade e solicitar contato na etapa própria. |
| Username | Exibição opcional. Pode mudar e não constitui chave de associação, telefone ou destinatário. |
| Contato oficial solicitado ao próprio remetente | Validar a solicitação pendente e a prova antes de promover o telefone. Cartão compartilhado de terceiro e número digitado são insuficientes. |

## Continuidade do atendimento

A identidade com que uma mensagem entrou fica registrada na fila e no histórico. O destinatário de saída é resolvido no banco no momento apropriado. Um vínculo posterior preserva a autoria histórica e os recibos. A proteção de flood, os bloqueios e a exclusão mútua acompanham aliases comprovados dentro da mesma unidade. Uma colisão requer resolução explícita.

O cliente provisório pode ter uma conversa enquanto aguarda o compartilhamento. A reconciliação precisa preservar o ID dessa conversa, o histórico, o ciclo de follow-up e a unidade. A apresentação no painel pode usar WA ID confirmado, depois username e, na ausência de ambos, “Contato não compartilhado”. O BSUID é interno. Exportações e integrações que exigem telefone só podem usar o número comprovado.

O [plano prático](user_id_plano_logico_pratico.md) descreve a migração dos dados atuais, a etapa de contato, os contratos dos workers e os critérios de aceite. A documentação do [fluxo vigente](../REGRAS_DE_NEGOCIO.md) continua sendo a referência para o atendimento arquivado.
