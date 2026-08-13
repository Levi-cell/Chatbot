# Testes transacionais essenciais

Esta pasta mantém apenas o núcleo que protege a execução do atendimento:

- cenário completo de turno A/B/C;
- retry, requeue, ordem da fila e fencing por `lock_version`;
- persistência idempotente, avanço e não avanço de etapa;
- checkpoints, commits, rollback e conclusão da fila no worker.

Testes de mensagens, Admin, documentação, estrutura, operações auxiliares e
regras periféricas não pertencem mais à suíte padrão.

Para executar o núcleo completo:

```powershell
python -m unittest discover -s tests -t . -p "test_*.py"
```

Arquivos mantidos:

```text
tests/unit/test_fluxo_turno_abc.py
tests/unit/test_retry_essencial.py
tests/unit/test_persistencia_essencial.py
tests/unit/test_worker_flow_runtime.py
```

Os testes usam somente fakes e mocks: nunca chamam Meta, Redis ou AWS reais.
