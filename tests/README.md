# Testes essenciais

Esta pasta mantém somente as proteções contra regressões com impacto real em
produção. A suíte não tenta reproduzir cada arquivo, sender ou texto exibido.

## O que permanece coberto

- entrada segura do webhook, `statuses`, cronologia e indisponibilidade;
- flood, regra de turno A/B/C e reentrega fora de ordem;
- retry, lock com versão, idempotência e `last_message_from`;
- mapa de transições e rejeição de saltos inválidos;
- persistência final, tratamentos sem avanço e ramificações principais;
- cache de unidade e bloqueio com fallback para o banco;
- validadores de mídia, dúvida sobre reforço escolar, financeiro, nome, idade,
  decisão, email e triagem;
- persistência das respostas da triagem;
- catálogo das perguntas da triagem por faixa etária, seus limites e a mesma
  ordenação no WhatsApp e no Funil;
- apresentação uniforme dos cabeçalhos interativos do WhatsApp;
- contratos mínimos do DDL, catálogo de etapas e mapa inicial.

Testes de frases completas, comentários, estrutura de pastas, duplicações por
sender e consultas SQL triviais foram removidos. Esses testes geravam
manutenção e execução repetida sem proteger uma regra diferente.

## Rotina durante o desenvolvimento

Mudança comum e localizada:

```powershell
# Não rodar teste por padrão quando a alteração for só texto ou comentário.
```

Mudança em uma regra já protegida:

```powershell
python -m unittest tests.unit.test_validadores_essenciais
```

Mudança em webhook, fila, transação, retry ou transição:

```powershell
python -m unittest tests.unit.test_webhook_post_flow
python -m unittest tests.unit.test_persistencia_essencial
```

Suíte mínima completa, reservada para alterações compartilhadas e preparação de
deploy:

```powershell
python -m unittest discover -s tests -p "test_*.py"
```

Os cenários semelhantes usam `subTest`. Assim, várias entradas continuam sendo
validadas sem transformar cada exemplo em um teste independente.

## Arquivos

```text
tests/
|-- __init__.py
|-- helpers.py
|-- payloads.py
`-- unit/
    |-- test_cache_essencial.py
    |-- test_deploy_essencial.py
    |-- test_efeitos_triagem.py
    |-- test_triagem_faixa_etaria.py
    |-- test_flood_guard.py
    |-- test_fluxo_turno_abc.py
    |-- test_lastfrom_semantico.py
    |-- test_persistencia_essencial.py
    |-- test_retry_essencial.py
    |-- test_roteamento_essencial.py
    |-- test_transicoes_etapa.py
    |-- test_validadores_essenciais.py
    |-- test_webhook_post_flow.py
    |-- test_webhook_statuses_e_cronologia.py
    `-- test_worker_flow_runtime.py
```

Os testes são unitários e usam fakes/mocks. Eles não devem chamar Meta, Redis ou
AWS reais e não devem depender dos segredos do `.env` local.
