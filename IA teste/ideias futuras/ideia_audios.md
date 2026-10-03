# Ideia futura: atendimento a mensagens de áudio

Registro: **30/09/2026**. Status: **documentado para depois da validação da IA;
sem implementação ou alteração na aceitação atual de mídias**.

Plano principal: [IA híbrida](../plano_ia_hibrida_atendimento.md).

## 1. Objetivo e escopo

Permitir que o cliente fale em áudio e que a transcrição seja interpretada pelo
mesmo fluxo textual da IA. A resposta continua em texto e com os botões previstos;
geração de voz não faz parte desta ideia.

Começar pelas unidades com IA habilitada. Unidades determinísticas mantêm a regra
atual de mídias. Imagens, vídeos e documentos não passam a ser aceitos porque o
provedor também oferece modelos capazes de interpretá-los.

## 2. Caminho pretendido

1. Receber a mensagem e validar assinatura, unidade, identidade, duplicidade,
   bloqueios, turno e limites de uso antes de consumir serviços pagos.
2. Identificar o tipo áudio e obter sua mídia pelo caminho autorizado da Meta.
3. Validar formato, duração e tamanho. Converter formato somente se necessário
   para o serviço escolhido, sem presumir que toda mídia do WhatsApp é aceita.
4. Transcrever com a API da OpenAI, com timeout e tentativas limitados.
5. Persistir a transcrição vinculada ao identificador da mensagem original.
6. Usar esse texto como entrada da interpretação, com a mesma validação de nomes,
   e-mail, idade, antecipações, correções e regras de negócio do piloto.
7. Compor a resposta e concluir o turno usando os controles normais de recuperação.

A OpenAI oferece transcrição de arquivos de áudio pela API. O resultado pode ser
uma string; **não é obrigatório criar um arquivo `.txt`** intermediário. Escolher
modelo e formatos ao implementar, conforme documentação e testes em português.
[Documentação oficial](https://developers.openai.com/api/docs/guides/speech-to-text).

O `if tipo == audio` é apenas o ponto de entrada. Download, transcrição,
persistência e interpretação são responsabilidades separadas.

## 3. Contexto, precisão e recuperação

- Preservar o tipo original, identificador da mídia/mensagem e origem da
  transcrição. Não fingir que o cliente enviou texto digitado.
- Uma transcrição já persistida é reutilizada no retry. Se houver timeout após
  processamento externo, registrar a tentativa: não prometer cobrança exatamente
  uma vez quando ainda não existe confirmação local do resultado.
- Nome, número ou e-mail pouco claros exigem esclarecimento; não completar um
  endereço nem escolher uma idade apenas porque parece provável.
- Se o modelo fornecer indicadores úteis de confiança, avaliá-los; não presumir
  que existe um indicador universal ou que a transcrição é infalível.
- Mensagem inaudível, vazia, inválida ou serviço indisponível: explicar brevemente
  e pedir texto. Falha técnica não aumenta o contador de erro do cliente.
- Se a transcrição demorar além do lock autorizado, não continuar enviando resposta
  com posse perdida. Aplicam-se `lock_version`, deduplicação e recuperação do fluxo.
- O texto transcrito continua sendo fala do cliente, nunca instrução para alterar
  permissões, criar etapas ou executar operações fora do catálogo.

## 4. Limites a definir antes de habilitar

| Item | Decisão futura necessária |
| --- | --- |
| Duração e tamanho | Limites por áudio, por cliente e por unidade. |
| Custos | Orçamento e medição separada de transcrição e interpretação. |
| Armazenamento | Onde guardar áudio/transcrição, prazo de retenção e acesso. |
| Processamento | Timeout, tentativas e comportamento para fila ocupada. |
| Experiência | Mensagem curta para áudio não compreendido ou não permitido. |
| Escopo | Comportamento depois do corte da IA na etapa 18. |

Não reativar IA após o agendamento por consequência de chegar um áudio. Até
definir essa integração, preservar o corte do plano principal.

## 5. Verificações para o futuro piloto

Testar português com ruído, nomes próprios, idade falada, e-mail soletrado,
negações/correções e duas pessoas citadas. Verificar áudio duplicado, fora do
limite, falha de download, timeout da OpenAI e reinício depois da transcrição.
Confirmar que nenhum desses casos envia duas respostas nem cria participante extra.

Áudios em sequência dependem do desenho de
[mensagens seguidas](ideia_mensagens_seguidas.md); uma evolução não habilita a outra.
