# Desenvolvimento local do Supera

A base usa Python 3.12, Django, PostgreSQL, Redis e PyWa. As versões das dependências estão em [requirements.txt](requirements.txt). Em PowerShell, a partir da raiz:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m unittest tests.unit.test_followup tests.unit.test_coleta_abertura tests.unit.test_validador_profissao -q
```

A configuração usada pelos processos está em [core/config_env.py](core/config_env.py) e nos módulos de configuração de cada integração. Use credenciais do ambiente de desenvolvimento no ambiente do processo ou no arquivo local privado `.env`. Para conferir a configuração Django, use `python callback/manage.py check`.

O [setup do banco](core/database/deploy_database/setup_database.py) prepara estruturas, funções e catálogo em uma base de desenvolvimento e reconstrói o cache. Em uma instalação existente, consulte as [migrações incrementais](deploy/migrations) e o [guia do banco](core/database/README.md). Os [testes de integração](tests/README.md) descrevem os requisitos de uma base isolada. O servidor de desenvolvimento inicia com `python callback/manage.py runserver`. Os módulos dos workers e suas flags estão no [inventário](workers/README.md).

A proposta anterior de separar credenciais, número de testes e armazenamento por ambiente está resumida em [ideias futuras](docs/ideias_futuras.md).
