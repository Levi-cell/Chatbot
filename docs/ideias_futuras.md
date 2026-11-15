# Ideias de evolução do Supera

Registro teórico na data de encerramento do desenvolvimento. A implantação conhecida usa atendimento determinístico, seis workers e monitoramento de leitura. A única proposta com roteiro de implementação mantido é [identidade WhatsApp por user_id](user_id_plano_logico_pratico.md).

| Ideia | Ponto de partida e questão que ficou aberta |
| --- | --- |
| Acordar o flow quando chegar uma mensagem | Hoje há polling da fila PostgreSQL. LISTEN/NOTIFY poderia reduzir consultas vazias, conservando a fila durável e a recuperação após desconexão. Avaliar pela latência e pelo custo observados. |
| Rastrear envio externo de resultado incerto | Fila, lock de conversa, histórico e recibos já sustentam retries. Uma resposta aceita pela Meta antes de uma queda local ainda pode ser duplicada. A ideia era estudar confirmação do provedor e uma forma de conciliar sem novo envio indevido. |
| Monitorar tratamentos | O painel atual mede origens, perfis, consumo e resultados. Medir a frequência de pedidos de endereço, reforço escolar e preço por etapa ajudaria a avaliar as perguntas do bot, preservando a privacidade dos contatos. |
| Reavaliar ausência inicial na FireAds | Uma planilha pode mudar após a abertura. A recuperação periódica atual cobre outra população. Ficaram em aberto prazo, limite de tentativas e precedência da evidência posterior para fins de métricas. |
| Observar agendamento efetivo | Hoje o chatbot encaminha para o link da unidade ou para o consultor. Confirmar comparecimento ou agendamento por calendário exigiria uma fonte confiável por unidade e regras de atribuição e cancelamento. |
| Referência de anúncio na mensagem do WhatsApp | A [proposta de referral](plano_origem_meta_anuncios_posts.md) complementaria a atribuição FireAds, especialmente nas unidades sem planilha. |
| Escalar o fluxo e atender mais de um app da Meta | Uma instância de flow já coordena turnos pela fila e pelos locks. Paralelizar processos exigiria preservar ordenação e medir contenção. Receber apps distintos no mesmo endpoint levantaria outra questão: como escolher a credencial e validar a assinatura antes de atribuir a unidade? |
| Governança operacional | Isolar banco, cache, credenciais e número de homologação, revisar retenção e acesso, acompanhar custo por unidade e validar restauração são objetivos para eventual retomada. A cobertura depende do ambiente real. |
| Validação e conversas mais flexíveis | Avaliar a qualidade da identificação de nomes sem bloquear nomes raros. Mensagens seguidas, áudio, solicitação de humano e mais de um participante permanecem hipóteses da [proposta de IA](../IA%20teste/plano_ia_hibrida_atendimento.md). |
| Consumo e PIN | O consumo mensal já é coletado da Meta. Controle por janela de gratuidade confirmada e rotação assistida do PIN exigiriam evidências externas e uma política de recuperação. A operação de PIN disponível é manual. |

Os roteiros antigos para recriar os arquivos da FireAds, do Funil, da digitação e dos relatórios deram lugar à [documentação do comportamento entregue](../README.md).
