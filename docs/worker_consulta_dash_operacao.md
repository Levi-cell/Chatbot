# Consulta FireAds por conversa — operação

Este documento acompanha o código do worker separado. Aplicar junto da migração
`deploy/migrations/20261009_worker_consulta_dash.sql` e do novo serviço.

Código aplicado localmente após o backup `b049a4d`. Validação da aplicação:
443 testes unitários e 28 testes de integração FireAds aprovados, sem testes
pulados, além de `manage.py check` sem problemas. O PostgreSQL usado foi local
e descartável; HTTP externo foi simulado. Deploy V1.11.0 confirmado na VM em
09/10/2026 às 23:36 (Brasília): migração aplicada e seis serviços ativos.

Correção posterior, ainda a implantar: a abertura escolhe o registro mais recente
do telefone entre Google e Meta, incluindo as variantes com/sem nono dígito.
Respostas diferentes não geram mais ambiguidade. Datas sem offset usam o fuso
configurado ou Brasília na ausência dele; isso não modifica a planilha.
Datas iguais usam a maior `_row` (última posição recebida quando não há linha
válida), inclusive entre abas, sem prioridade fixa por origem. Datas válidas
precedem inválidas; sem datas válidas, vale esse mesmo desempate por linha/posição.
Se todos esses critérios empatarem, mantém o primeiro candidato encontrado.
O desempate por linha entre abas é uma convenção de seleção; não comprova
cronologia que a fonte deixou de informar.
O formulário escolhido é usado inteiro; se estiver incompleto, não se resgatam
campos antigos. Não há migração SQL nova: `ambiguidade` continua permitido no
banco apenas para preservar resultados históricos. Validação da correção:
46 testes de FireAds, espera HTTP e runtime do flow aprovados, com HTTP simulado.

## Contrato

Consultar só uma vez logicamente por conversa nova, antes da primeira resposta.
O `worker_flow` não executa HTTP FireAds, não cria threads auxiliares e não aguarda
rede. Registra a pendência e devolve a mensagem à fila por 5 segundos, sem consumir
retry. O worker de consulta verifica o banco a cada 2 segundos quando ocioso; havendo
trabalho, processa uma consulta e segue para a próxima sem espera adicional.

Google e Meta são lidos por inteiro no contrato atual do Apps Script. Ambas as
leituras e a interpretação terminam antes de gravar `dados` em uma única transação.
Armazenam-se somente as linhas correspondentes ao telefone consultado, não as de
outros clientes. Não há checkpoints parciais por aba. Uma falha real de conexão,
HTTP ou contrato conclui organicamente com diagnóstico, conforme a regra aprovada.

O prazo total é de 300 segundos desde a solicitação, incluindo fila, ambas as abas,
redirecionamentos e reexecuções. Não é renovado após queda. A decisão de timeout é
persistida pelo primeiro ciclo que perceber o prazo vencido, inclusive pelo flow
se o serviço de consulta estiver parado. Portanto, a resposta pode ocorrer alguns
segundos depois do limite, conforme a agenda da fila. Uma chamada de rede ainda em
andamento não pode importar nada depois desse encerramento. Um resultado confirmado
no banco antes do prazo pode ser aplicado depois, sem ser descartado por demora do flow.

## Banco e recuperação

`consulta_fireads.id_conversa` é único. O chat é obtido por `conversa.id_chat`; não
há coluna de chat duplicada nem view. `id_unidade` permanece para as FKs compostas
que impedem vincular conversa e integração de unidades diferentes.

- `entrada`: telefone, URL, abas e fuso congelados na solicitação.
- `status`: pendente, processando ou concluida; `consulta_concluida` é mantida por
  compatibilidade e uma constraint exige consistência com o status.
- `dados`: envelope com `decisao` e `fontes`, gravado completo ou mantido NULL.
- `resultado`: pendente/importado/ausente/incompleto/erro; ambiguidade somente no legado.
- `solicitado_em` e `prazo_final`: orçamento persistente da abertura.
- `tentativas`, `versao_reserva`, `processing_started_at` e `reserva_ate`: reserva
  operacional; tentativas adicionais apenas recuperam uma execução interrompida.
- `consultado_em`: conclusão, inclusive ausência/erro/timeout.
- `aplicacao` e `aplicado_em`: decisão efetivamente aplicada pelo flow. Pode divergir
  do resultado externo se, por exemplo, houver conflito de e-mail na importação.
- `ultimo_erro`: diagnóstico sem corpo HTTP, credenciais ou dados de outro cliente.
- `atualizado_em`: última alteração, sem servir para reiniciar o prazo.

A reserva combina advisory lock de sessão PostgreSQL e versão persistida. Não há
transação nem row lock aberto durante HTTP: a conexão fica ociosa, mantendo só o
advisory lock. Dois processos não consultam o mesmo registro simultaneamente com
a sessão viva. A morte do processo libera o lock quando o banco encerra a conexão;
o próximo worker pode recuperar a mesma consulta antes dos 300 segundos. Perda de
rede pode retardar a detecção da sessão morta; o prazo orgânico continua valendo.

A gravação exige versão e prazo válidos. Timeout, suspensão da unidade, alteração
de configuração, conversa encerrada ou abertura já iniciada impedem confirmação
indevida. Não usar pool com troca de sessão: o lock depende da mesma conexão.
O próprio fechamento da conexão libera o lock, mesmo quando unlock falha.

O flow mantém seu lock versionado de conversa, a ordem dos turnos e a identificação
da mensagem. Solicitação e reagendamento são confirmados juntos no handler de
espera. A conversa pode já ter sido criada em um checkpoint anterior: se houver
queda nesse intervalo, a fila recria apenas a solicitação, reutilizando a conversa.
Importação, snapshot, histórico do cliente e marcador de aplicação pertencem à
transação do flow. O envio WhatsApp e a recuperação de seu recibo seguem o protocolo
atual; a janela de envio aceito externamente antes do commit local continua existindo.

Não alterar as regras existentes do webhook: no contrato atual, mensagens adicionais
chegando antes da resposta da entrada aberta podem ser descartadas na admissão.
As mensagens já admitidas na fila mantêm as guardas de ordem; não prometer juntar
textos enviados durante os minutos de espera nesta mudança.

## Cenários

| Situação | Resultado |
| --- | --- |
| Sem integração / conversa já iniciada | Atendimento atual, sem nova consulta. |
| Nova conversa elegível com integração | Uma solicitação persistida; nenhuma saudação prematura. |
| Google ou Meta completo | Importa titular, e-mail e destinatário; abertura na profissão, etapa 4. |
| Ambas as fontes / várias inscrições | Registro mais recente, com os desempates documentados acima. |
| Ausente / incompleto / falha / timeout | Atendimento orgânico desde a etapa 1, motivo registrado. |
| Resultado aplicado e retry | Reutiliza o contexto; nenhuma nova leitura ou regressão de etapa. |
| Pessoa preenche formulário depois da abertura | Considerar somente na próxima conversa. |
| Outra conversa do mesmo chat | Outro id_consulta; histórico anterior preservado. |
| Unidade suspensa | Não reservar nem importar; conservar pendências e histórico. |
| Configuração FireAds alterada durante a espera | Não aplicar a configuração antiga; concluir com motivo explícito. |

Telefone com e sem nono dígito, nome composto, descarte de faixa etária/objetivo,
saudação personalizada, salto da coleta do e-mail e canais Funil mantêm as regras
existentes. A aba geral não classifica a abertura; o worker_funil mantém sua própria
consulta antes da escrita e a preservação das observações existentes.

## Seleção da linha para atualizar o dashboard

A correção posterior à V1.11.1 está aplicada no código local e depende de deploy.
Não requer migração SQL nem mudanças nas abas da FireAds. Os códigos de canal do
Funil continuam Google `113336`, Meta `113340` e Orgânico `113481`.

Na aba de destino, o worker busca todas as variantes válidas do telefone. Antes
de escolher uma linha, procura o bloco da própria conversa: um bloco já gravado
é reconciliado, sem novo POST, mesmo se outra linha mais recente tiver surgido.
Marcador com conteúdo divergente continua pendente, sem sobrescrever ou copiar
o atendimento para outra linha.

Para uma entrega ainda não gravada, prefere o canal da origem e, dentro desse
grupo, titular/dependente compatível. `Organico Site` corresponde à origem Google
somente nesse cruzamento. As variantes `MKT DIGITAL - GOOGLE ADS` e
`MKT DIGITAL - META ADS (FACEBOOK/INSTAGRAM)` também são reconhecidas.
Faixa etária não define destinatário. Sem perfil compatível, mantém os candidatos
do canal; o desempate usa a maior `_row`. Sem canal compatível, usa a maior linha
do telefone. Na escrita, a data não prevalece sobre esse critério de linha.

E-mail diferente no mesmo telefone não bloqueia o update. Somente `Observação`
é alterada, preservando conteúdo anterior, e-mail, nome, canal e data da linha.
Telefone ausente gera cadastro com os dados do atendimento, inclusive para
orgânicos; e-mail encontrado em outro telefone continua exigindo conferência.
A FireAds preenche a data dos cadastros novos. Cabeçalhos/linha inválidos, falhas
HTTP e recusas da API continuam sujeitos ao reagendamento existente.

O JSON do snapshot passa a guardar `status_dependente`; envios antigos continuam
compatíveis pelo perfil textual já congelado. A linha confirmada no update fica
no recibo da API; reconciliações guardam `linhas_reconciliadas` no mesmo campo JSON.
A posição da linha é obtida na consulta anterior à escrita, não reutilizada como
endereço permanente. Edição externa entre leitura e POST permanece possível;
o contrato atual da FireAds não oferece atualização condicional por identidade.

## Implantação coordenada

1. Salvar backup e subir a revisão contendo TODOS os arquivos do plano.
2. Na VM, conferir a revisão e parar follow-up, webhook, flow, Funil e consumo Meta.
   Se o serviço de consulta já existir de uma tentativa anterior, parar também.
3. Atualizar o checkout com fast-forward. Manter serviços parados enquanto código
   e esquema forem incompatíveis. Não executar setup ou seeds em produção.
4. Executar inteiro o SQL final do plano no DBeaver. Exigir `migracao_ok=true` e
   `vinculos_invalidos=0`. Em erro, realizar ROLLBACK e corrigir antes de continuar.
5. Instalar o novo serviço com os comandos abaixo. Não iniciar ainda.
6. Sob o usuário chatbot e o ambiente já existente, executar `manage.py check`
   e `collectstatic --noinput`. Não precisa `makemigrations`/`migrate`: os models
   do domínio são `managed=False` e a mudança é o SQL manual indicado.
7. Iniciar consulta, webhook e flow; conferir status/logs. Depois iniciar Funil,
   consumo Meta e follow-up. Usar os mesmos controles de saúde do deploy atual.
8. Observar uma NOVA conversa autorizada de teste. Não resetar conversas antigas.

Instalação do sexto serviço na VM (após conferir a revisão):

```bash
cd /opt/chatbot/app &&
sudo install -m 0644 deploy/systemd/chatbot-worker-consulta-dash.service /etc/systemd/system/chatbot-worker-consulta-dash.service &&
sudo systemctl daemon-reload &&
sudo systemctl enable chatbot-worker-consulta-dash.service
```

Inicialização, depois da migração e verificações Django:

```bash
sudo systemctl start chatbot-worker-consulta-dash.service chatbot-webhook.service chatbot-worker-flow.service &&
systemctl show chatbot-worker-consulta-dash.service chatbot-webhook.service chatbot-worker-flow.service -p Id -p ActiveState -p SubState -p NRestarts --no-pager
```

Depois da conferência anterior:

```bash
sudo systemctl start chatbot-worker-funil.service chatbot-worker-consumo-meta.service &&
sudo systemctl start chatbot-worker-followup.service &&
sudo journalctl -u chatbot-worker-consulta-dash.service -u chatbot-worker-flow.service --since "5 minutes ago" -n 100 --no-pager
```

Não executar `git reset` para a versão anterior mantendo o novo esquema. Em falha,
manter os serviços afetados parados e corrigir para frente, ou restaurar conjuntamente
backup de banco e código sob procedimento controlado. Não há reversão destrutiva
automática que descarte o novo histórico de consultas.

## Capacidade e limites

Uma instância do novo serviço faz uma leitura por vez. Isso organiza a recuperação,
mas não acelera a planilha. Picos podem consumir o orçamento enquanto uma consulta
aguarda na fila e resultar em orgânico. Os locks permitem testar mais instâncias
futuramente sem reservar a mesma consulta; esta entrega mantém uma instância.

O deadline protege a decisão e a gravação, não promete terminar qualquer operação
de rede no exato milissegundo do prazo. O atendimento continua independente dessa
chamada. Quedas podem repetir GET, que não cria leads; nenhuma abertura usa POST
no dashboard. A duplicação rara de envio WhatsApp antes de persistir recibo continua
sendo uma fronteira externa já conhecida, não uma garantia de exatamente uma vez.

## Migração do histórico

Preservar os IDs e dados das consultas que existem hoje e seus vínculos com a
conversa referenciada. A estrutura antiga guardava somente a última consulta do
chat: não inventar registros anteriores. Contextos de conversas históricas ficam
intactos; IDs antigos dentro de JSONs são referências históricas, não novas FKs.
As novas conversas passam a ter registros independentes. Pendências antigas mantêm
seu início registrado e não ganham outros 300 segundos durante o deploy.
