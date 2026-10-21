# Implantação do consumo mensal Meta

## Entrega

O serviço `chatbot-worker-consumo-meta` consulta apenas a Meta (GET), sincroniza
o fuso da WABA e persiste os totais. A seção **Consumo** e seus dois PDFs consultam
somente o banco da unidade autenticada. Flow, follow-up e Funil não contam mensagens
nem participam desta coleta. A API e o token já configurados continuam sendo usados.

## Migração e ordem de implantação

1. Guardar o commit anterior para reversão. Parar o follow-up, depois os workers
   de fluxo e Funil e o processo web antes de trocar código/dependências/schema.
   Isso evita processos usando a PyWa antiga enquanto o pacote é atualizado e
   impede iniciar o novo modelo `Unidade` sem as colunas. O worker de consumo,
   se já instalado, também deve estar parado.
2. Atualizar o checkout e as dependências do ambiente virtual:

   ```bash
   /opt/chatbot/venv/bin/python -m pip install -r /opt/chatbot/app/requirements.txt
   /opt/chatbot/venv/bin/python -m pip check
   /opt/chatbot/venv/bin/python -c "from importlib.metadata import version; versao = version('pywa'); print('PyWa instalado:', versao); assert versao == '4.5.0', 'A VM precisa usar PyWa 4.5.0'"
   ```

   Esta entrega fixa PyWa 4.5.0 (antes 3.8.0), ReportLab 4.5.1 e svglib 1.5.1.
   A Graph API continua na versão indicada por `META_GRAPH_API_VERSION`.

3. No DBeaver, executar **o arquivo inteiro**, incluindo `BEGIN` e `COMMIT`:
   [20260929_consumo_mensal_meta.sql](migrations/20260929_consumo_mensal_meta.sql).
   Não rodar o bootstrap/seeds em produção. O SQL é aditivo e pode ser reexecutado;
   não altera conversas, mensagens, bloqueios, configurações de atendimento ou
   qualquer conta Meta. Se falhar, executar `ROLLBACK` e resolver a causa antes de
   iniciar o código novo. Usar o mesmo proprietário dos demais objetos do projeto;
   o usuário de runtime precisa ler/escrever as novas tabelas e usar sua sequência.
4. Configurar `/etc/chatbot/chatbot.env`, além das variáveis DB/META já existentes:

   ```dotenv
   CONSUMO_META_ENABLED=True
   CONSUMO_META_CICLO_SEGUNDOS=60
   CONSUMO_META_INTERVALO_SEGUNDOS=3600
   CONSUMO_META_LIMITE_POR_CICLO=100
   CONSUMO_META_HORA_CONFERENCIA=9
   ```

   Sem `CONSUMO_META_ENABLED=True`, o iniciador termina sem consultar a Meta.
   Hora de conferência é interpretada no fuso preservado de cada mês. A agenda
   persiste no banco: reiniciar o serviço não força nova coleta antes do horário.
5. Validar e atualizar os arquivos estáticos usando o ambiente da VM:

   ```bash
   sudo -u chatbot bash -c 'set -e; set -a; source /etc/chatbot/chatbot.env; set +a; cd /opt/chatbot/app; export PYTHONPATH=/opt/chatbot/app PYTHONDONTWRITEBYTECODE=1; /opt/chatbot/venv/bin/python callback/manage.py check --deploy && /opt/chatbot/venv/bin/python callback/manage.py collectstatic --noinput'
   ```

6. Instalar o novo serviço e retomar os processos:

   ```bash
   sudo install -m 0644 deploy/systemd/chatbot-worker-consumo-meta.service /etc/systemd/system/chatbot-worker-consumo-meta.service
   sudo systemctl daemon-reload
   sudo systemctl start chatbot-webhook.service
   sudo systemctl start chatbot-worker-flow.service chatbot-worker-funil.service
   sudo systemctl enable --now chatbot-worker-consumo-meta.service
   sudo systemctl start chatbot-worker-followup.service
   ```

7. Conferir logs e a seção Consumo após recarregar a página:

   ```bash
   systemctl show chatbot-worker-consumo-meta.service -p ActiveState -p SubState -p NRestarts --no-pager
   sudo journalctl -u chatbot-worker-consumo-meta.service -n 40 --no-pager
   ```

## Cadência e conferência

- Mês atual: coleta horária; meses anteriores pendentes: uma coleta diária.
- Primeira decisão: dia 25 do mês seguinte, com os três volumes iguais à última
  coleta válida de mês completo realizada em uma data local anterior.
- Divergência, falta de comparação ou falha no dia 25: próxima decisão no dia 25
  do mês seguinte. Continua consultando diariamente. Igualdade no dia 26 não aprova.
- Processo desligado no dia 25: usar o próximo dia 25 futuro, sem aprovação retroativa.
- `consolidado`: encerra consultas automáticas daquele mês; não certifica uma fatura.
- Um erro não cria mês com zero, não apaga volumes e não impede outra unidade.
- Um advisory lock próprio por ciclo impede execução simultânea por dois processos.
  Nenhuma transação fica aberta enquanto aguarda HTTP; locks do flow não são usados.

Os meses ausentes são recuperados desde outubro/2026, pois o cadastro atual de
unidade não possui uma data de início do acompanhamento. Dados fora da janela
histórica consultável ficam com erro explícito para revisão, não são presumidos zero.
O limite por ciclo prioriza o mês atual antes dos anteriores. Os registros atuais
não dependem de `status_pagamento`; esse campo não elimina pendências de consumo.

## Fusos e mudança de cadastro

`unidade.id_fuso` e `unidade.nome_fuso` começam NULL. Cada leitura válida de conta
preenche/sincroniza o par com a Meta, mesmo se a consulta de volumes falhar depois.
IDs desconhecidos não são interpretados como UTC. A configuração da WABA nunca
é alterada pelo worker. Fusos brasileiros conhecidos estão mapeados na integração.

Cada mês preserva conta, número, fuso e fronteiras originais. Se esses dados
mudarem, a unidade recebe o fuso novo, mas um mês já existente não é recortado
silenciosamente: conserva os totais e indica falha de coleta para revisão. Um novo
mês usa o cadastro novo. Antes de intervir manualmente, conferir o período na Meta;
não trocar fronteiras sem uma coleta completa correspondente.

## Diagnóstico somente por leitura

```sql
SELECT u.nome_unidade, c.periodo, c.ultima_tentativa_em,
       c.proxima_consulta_em, c.falhas_consecutivas, c.ultimo_erro
FROM chatbot.consumo_meta_coletas c
JOIN chatbot.unidade u USING (id_unidade)
WHERE c.ultimo_erro IS NOT NULL
ORDER BY c.ultima_tentativa_em DESC;

SELECT id_unidade, mes_referencia, status_apuracao, ultimo_sucesso_em,
       data_proxima_consolidacao, qtd_janela_gratuita,
       qtd_franquia_consumida, qtd_cobradas_meta
FROM chatbot.consumo_mensal_meta
ORDER BY id_unidade, mes_referencia DESC;
```

A tela mostra o horário da última coleta válida, não o horário de seu refresh.
A tarifa de R$ 0,035 é uma referência BRL para serviço no Brasil, com vigência
registrada. O excedente exibido não representa uma fatura emitida pela Meta.
A primeira validação com métricas efetivas de outubro deve conferir o retorno
real de `pricing_analytics`; testes com respostas simuladas não certificam a Meta.

## Reversão

Parar/desabilitar `chatbot-worker-consumo-meta`, retornar ao commit anterior,
executar `collectstatic` e reiniciar o processo web. **Não é necessário desfazer
o SQL:** colunas e tabelas novas são aditivas e compatíveis com o código anterior.
Preservá-las mantém histórico, agenda e fusos e permite reaplicar a versão sem
renomear objetos ou perder dados. Não usar `DROP TABLE` como reversão operacional.

## Validação local

```bash
python -m unittest tests.unit.test_consumo_meta tests.unit.test_monitoramento_consumo tests.unit.test_consultar_franquia_meta
python -m unittest tests.integration.test_consumo_meta_postgres
```

Integração exige `CONSUMO_META_TEST_DSN` apontando para loopback e banco vazio
`test_chatbot_consumo`. O teste recusa schema chatbot preexistente, cria seus
próprios objetos e remove apenas esses objetos. Nunca usar banco produtivo.
Cobertura: reexecução da migração, constraints, upsert, rollback transacional,
coletas antigas, isolamento de unidade, duas consolidações pendentes, falhas,
mudança de fuso e concorrência. Revisão visual usa dados fictícios, sem envios.


## Evidências desta implementação

Em 29/09/2026, a suíte completa executou 400 testes: 368 passaram, 32 testes
antigos de integração ficaram ignorados por exigirem outros bancos específicos.
Depois da revisão final, foi acrescentado e validado um caso de alteração do
cadastro durante HTTP (total de 11 cenários PostgreSQL desta funcionalidade).
O check do Django não apontou problemas. Foram revisados navegação, troca rápida
entre meses, preservação de dados em erro e download em navegador, nas larguras
320, 390, 667, 768, 1024 e 1440 px, sem erros JavaScript ou overflow da página.
PDF mensal, histórico curto e histórico longo foram renderizados e inspecionados.
Esses testes não executaram consultas de produção, envios ou migração no RDS.
