# Testes do projeto

Esta pasta reúne a suíte unitária e de contrato do projeto. Além do núcleo
transacional, ela cobre regras e utilitários já implementados:

- cenário completo de turno A/B/C;
- retry, requeue, ordem da fila e fencing por `lock_version`;
- persistência idempotente, avanço e não avanço de etapa;
- checkpoints, commits, rollback e conclusão da fila no worker.
- suporte ao idoso e obrigatoriedade do e-mail;
- validação da oferta, profissão e saudação após inatividade;
- montagem dos relatórios semanais e totais;
- payloads e sondas manuais do Funil.

Para executar a suíte completa a partir da raiz:

```powershell
python -m unittest discover -s tests -t . -p "test_*.py"
```

Organização atual:

```text
tests/unit/test_fluxo_turno_abc.py
tests/unit/test_retry_essencial.py
tests/unit/test_persistencia_essencial.py
tests/unit/test_worker_flow_runtime.py
tests/unit/test_suporte_idoso_email_obrigatorio.py
tests/unit/test_saudacao_retorno.py
tests/unit/test_valida_etapa7.py
tests/unit/test_validador_profissao.py
tests/unit/test_gerar_monitoramento_unidades.py
tests/unit/test_metricas_perfis_relatorios.py
tests/unit/test_sondas_funil.py
```

Os testes usam fakes e mocks para fronteiras externas: a descoberta da suíte não
deve chamar Meta, Funil, Redis, RDS nem outro serviço real. Um utilitário manual
não deve ser executado como forma de testar sua importação.

Novos testes pertencem a `tests/unit/`; dados e classes auxiliares exclusivos de
teste ficam em `tests/`, nunca nos módulos de produção.
