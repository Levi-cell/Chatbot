# Rotina operacional da VM do Supera

A instalação usa a branch `prod` em `/opt/chatbot/app`, o ambiente Python em `/opt/chatbot/venv` e o arquivo de configuração em `/etc/chatbot/chatbot.env`. O registro da última entrega está em [VERSIONAMENTO.md](../VERSIONAMENTO.md). Este procedimento serve como referência caso a instalação volte a ser operada.

## Antes de atualizar

Verificar a revisão, se a árvore da VM está limpa, os commits recebidos por `git fetch origin` e a diferença de arquivos. Registrar quais das [sete unidades systemd](../deploy/systemd) estão ativas e habilitadas. Identificar migrations incrementais e compatibilidade dos processos envolvidos. Para mudança de schema, confirmar backup e possibilidade de restauração antes de interromper o atendimento.

## Ordem da manutenção

1. Para mudança que afete fila, etapas ou schema compartilhado, pausar primeiro os lembretes. Parar o webhook e os workers de flow, consulta, Funil, consumo e origem conforme as dependências. Para uma alteração isolada de painel, verificar se basta atualizar estáticos e recarregar Gunicorn.
2. Com a árvore limpa e a revisão conferida, aplicar o avanço da branch com `git pull --ff-only origin prod`. Conferir o SHA resultante. Atualizar dependências, arquivos de unit e configuração apenas quando o diff exigir. Após troca de unit, executar `systemctl daemon-reload`.
3. Aplicar a migração específica da versão ao banco existente. Executar verificações com o usuário `chatbot`, o Python do venv e o mesmo ambiente do serviço. Usar `callback/manage.py check`, testes unitários pertinentes e `collectstatic --noinput` quando houver arquivos estáticos. Os testes que criam ou alteram estrutura usam banco de testes isolado.
4. Restabelecer consulta inicial FireAds, webhook e flow. Verificar `ActiveState`, `SubState`, `NRestarts`, logs e a resposta dos endpoints. Restabelecer Funil, consumo e origem que estavam ativos. Reativar follow-up por último, depois de validar o flow e o schema compatíveis.
5. Conferir os ciclos nos logs e uma leitura autenticada do painel. Um ciclo com zero selecionados pode ser normal. O utilitário `python -m utilitarios.verificar_followup` inspeciona elegibilidade sem enviar mensagens.

## Se uma etapa falhar

Guardar o SHA, o erro e a saída das validações. Identificar se o schema ou algum envio externo já mudou. A reversão de código depende de compatibilidade com o banco e as filas daquela instalação. O [guia de implantação](../deploy/README.md) cobre setup inicial, TLS, estáticos, migrações e configuração do worker de origem.
