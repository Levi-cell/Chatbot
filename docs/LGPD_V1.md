# Dados pessoais no atendimento do Supera

Este registro descreve o tratamento de dados na versão arquivada. O WhatsApp fornece o identificador de contato e as mensagens. A conversa pode reunir nome, telefone, e-mail, profissão, informações do dependente, idade ou faixa etária, preferências, respostas de triagem, avaliação e comentários, de acordo com a rota e a unidade.

| Onde aparecem | Para que são usados |
| --- | --- |
| Fila, histórico, conversa e registros de follow-up | Processar a mensagem da unidade, manter o atendimento, recuperar tentativas e documentar respostas e encerramento. |
| Banco e cache de controle | Ordenação, locks, bloqueios, contadores temporários e recuperação. A expiração de uma chave de cache não remove o histórico do banco. |
| FireAds e Funil | Consultar o formulário pelo telefone, registrar origem e anúncio quando disponíveis, sincronizar campos permitidos e encaminhar o atendimento elegível. |
| Painel e exportações | Monitoramento autenticado por unidade, leitura de conversas e métricas, consultas operacionais e arquivos destinados à equipe autorizada. |

Credenciais e tokens pertencem ao ambiente privado da instalação. Ao compartilhar diagnósticos, remover dados identificáveis e segredos. Um pedido de exclusão precisa considerar o escopo autorizado e os destinos envolvidos. Uma limpeza local de banco e cache não comprova exclusão em planilhas externas, CRM, relatórios exportados ou backups.

As referências operacionais são os [utilitários](../utilitarios/README.md), o [cache](../core/cache/README.md) e a [integração FireAds](fireads.md). O encerramento do desenvolvimento não define prazo de retenção, destino dos backups ou situação dos dados de uma instalação. Essas decisões cabem aos responsáveis pelos dados.
