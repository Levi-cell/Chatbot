# Plano final - Base local de nomes e sobrenomes do IBGE

## Objetivo

Adicionar ao detector de nomes uma base local, pequena e somente para leitura,
gerada a partir de uma fonte oficial do IBGE.

O resultado esperado e:

```text
fonte oficial do IBGE
-> download controlado durante o build
-> validacao e normalizacao
-> arquivo SQLite local
-> arquivo incorporado na imagem Docker do worker
-> consultas locais, sem internet durante o atendimento
```

Esta tarefa deve ser aplicada somente na fase final de preparacao da producao.
Ela e isolada do webhook, PostgreSQL, Redis, Meta, fila, historico e regras de
turno.

## Decisoes obrigatorias

1. `sqlite3` ja faz parte da biblioteca padrao do Python. Nao instalar pacote
   Python e nao adicionar dependencia ao `requirements.txt`.
2. A API ou o site do IBGE nao sera consultado durante o atendimento.
3. O SQLite sera gerado antes do `docker build`.
4. O SQLite sera aberto em modo somente leitura dentro do container.
5. A base do IBGE sera evidência positiva, nunca a unica fonte da verdade.
6. Ausencia de um nome na base nao podera, sozinha, tornar o nome invalido.
7. As validacoes deterministicas atuais continuam com prioridade:
   numeros, caracteres invalidos, termos pejorativos, contexto e estrutura.
8. Se o SQLite estiver ausente, corrompido ou indisponivel, o detector atual
   continuara funcionando sem alterar o fluxo.
9. Nao usar scraping de endpoint interno ou nao documentado do site do IBGE.
10. A fonte, a versao, o hash e a data de geracao ficarao registrados dentro do
    proprio SQLite.

## Observacao importante sobre a fonte

O IBGE informa que a edicao do Censo 2022 possui quase 130 mil nomes proprios e
mais de 200 mil sobrenomes. A API publica documentada de nomes, entretanto, nao
apresenta claramente uma rota de download em massa desse catalogo completo.

Fontes oficiais para confirmar no momento da implementacao:

- [Nomes no Brasil - Censo 2022](https://censoagro2017.ibge.gov.br/1992-novo-portal/edicao/44913-nomes-censo2022.html)
- [Noticia oficial do IBGE](https://agenciadenoticias.ibge.gov.br/agencia-noticias/2012-agencia-de-noticias/noticias/44929-um-pais-de-marias-joses-silvas-e-santos-ibge-lanca-nova-edicao-do-nomes-no-brasil)
- [Nota tecnica 01/2025](https://biblioteca.ibge.gov.br/visualizacao/livros/liv102228.pdf)
- [Documentacao das APIs do IBGE](https://servicodados.ibge.gov.br/api/docs/)

Portanto, a aplicacao deste plano comeca por um checkpoint:

```text
Existe arquivo oficial em massa, CSV ou JSON?
-> sim: usar sua URL oficial no downloader
-> nao: obter/exportar o arquivo oficial manualmente e usar --arquivo
```

O plano nao inventa uma URL nem depende de uma rota privada do site. Se o IBGE
publicar um endpoint oficial em massa ate a aplicacao, ele podera ser informado
ao downloader sem alterar o restante da arquitetura.

## Estrutura final

```text
core/
├── data/
│   └── nomes_ibge/
│       └── README.md
└── repositories/
    └── nomes_ibge.py

tools/
└── nomes_ibge/
    ├── baixar_fonte_ibge.py
    ├── criar_base_sqlite.py
    └── verificar_base_sqlite.py

tests/
├── fixtures/
│   └── nomes_ibge_amostra.csv
└── unit/
    ├── test_base_nomes_ibge.py
    └── test_criar_base_nomes_ibge.py

Dockerfile.worker
.dockerignore
```

Arquivos gerados localmente:

```text
core/data/nomes_ibge/fontes/
core/data/nomes_ibge/nomes_ibge.sqlite3
```

Esses dois caminhos nao devem ser commitados. O banco sera reproduzido antes do
build e incorporado na imagem Docker.

---

## Passo 1 - Confirmar o SQLite do Python

Nenhuma instalacao por `pip` e necessaria.

Executar:

```powershell
python -c "import sqlite3; print(sqlite3.sqlite_version)"
```

Resultado esperado: uma versao do SQLite e codigo de saida zero.

O programa de linha de comando `sqlite3.exe` e opcional e serve apenas para
inspecao manual. O projeto nao dependera dele.

---

## Passo 2 - Atualizar `.gitignore`

Adicionar ao final do arquivo:

```gitignore

# Base local gerada a partir de dados publicos do IBGE.
core/data/nomes_ibge/fontes/
core/data/nomes_ibge/*.sqlite3
core/data/nomes_ibge/*.sqlite3-*
```

Isso impede o commit acidental do arquivo bruto, banco temporario, WAL e journal.

---

## Passo 3 - Criar `core/data/nomes_ibge/README.md`

Codigo completo:

```markdown
# Base local de nomes do IBGE

Esta pasta recebe artefatos gerados; ela nao contem dados pessoais individuais.

Arquivos locais:

- `fontes/`: arquivo oficial bruto ou normalizado;
- `nomes_ibge.sqlite3`: base somente leitura usada pelo worker.

O banco nao deve ser alterado em runtime. Para atualizar os dados:

1. obter a nova fonte oficial;
2. conferir origem e hash;
3. gerar um novo SQLite;
4. executar testes e verificacao de integridade;
5. construir uma nova imagem Docker;
6. implantar a nova imagem.

Se o arquivo estiver ausente, o detector usa seu comportamento deterministico
normal.
```

---

## Passo 4 - Criar o downloader oficial

Criar `tools/nomes_ibge/baixar_fonte_ibge.py`.

O script aceita somente HTTPS e dominios do IBGE. Ele baixa para arquivo
temporario, calcula SHA-256 e somente depois promove o arquivo.

Codigo completo:

```python
import argparse
import hashlib
import shutil
import sys
from pathlib import Path
from urllib.parse import urlparse

import requests


DOMINIOS_IBGE_PERMITIDOS = (
    "ibge.gov.br",
    "servicodados.ibge.gov.br",
)
CHUNK_BYTES = 1024 * 1024
TIMEOUT_HTTP = (15, 120)


def dominio_oficial_ibge(url):
    parsed = urlparse(url)
    hostname = (parsed.hostname or "").lower()

    if parsed.scheme != "https":
        return False

    return any(
        hostname == dominio or hostname.endswith(f".{dominio}")
        for dominio in DOMINIOS_IBGE_PERMITIDOS
    )


def calcular_sha256(caminho):
    digest = hashlib.sha256()

    with Path(caminho).open("rb") as arquivo:
        for bloco in iter(lambda: arquivo.read(CHUNK_BYTES), b""):
            digest.update(bloco)

    return digest.hexdigest()


def baixar_fonte(url, destino):
    if not dominio_oficial_ibge(url):
        raise ValueError("A URL precisa usar HTTPS e pertencer ao IBGE")

    destino = Path(destino).resolve()
    temporario = destino.with_suffix(f"{destino.suffix}.part")
    destino.parent.mkdir(parents=True, exist_ok=True)

    try:
        with requests.get(
            url,
            stream=True,
            timeout=TIMEOUT_HTTP,
            headers={"User-Agent": "Chatbot-Supera/1.0 base-nomes-ibge"},
        ) as resposta:
            resposta.raise_for_status()

            with temporario.open("wb") as arquivo:
                for bloco in resposta.iter_content(chunk_size=CHUNK_BYTES):
                    if bloco:
                        arquivo.write(bloco)

        if temporario.stat().st_size == 0:
            raise RuntimeError("O IBGE retornou um arquivo vazio")

        temporario.replace(destino)
        return destino, calcular_sha256(destino)

    finally:
        temporario.unlink(missing_ok=True)


def copiar_fonte_local(origem, destino):
    origem = Path(origem).resolve()
    destino = Path(destino).resolve()

    if not origem.is_file():
        raise FileNotFoundError(f"Fonte local nao encontrada: {origem}")

    destino.parent.mkdir(parents=True, exist_ok=True)
    temporario = destino.with_suffix(f"{destino.suffix}.part")

    try:
        shutil.copyfile(origem, temporario)
        temporario.replace(destino)
        return destino, calcular_sha256(destino)
    finally:
        temporario.unlink(missing_ok=True)


def salvar_hash(caminho, sha256):
    arquivo_hash = Path(f"{caminho}.sha256")
    arquivo_hash.write_text(
        f"{sha256}  {Path(caminho).name}\n",
        encoding="ascii",
    )


def criar_parser():
    parser = argparse.ArgumentParser(
        description="Baixa ou copia uma fonte oficial de nomes do IBGE.",
    )
    origem = parser.add_mutually_exclusive_group(required=True)
    origem.add_argument("--url", help="URL HTTPS oficial do IBGE")
    origem.add_argument(
        "--arquivo",
        help="Arquivo oficial obtido manualmente",
    )
    parser.add_argument("--destino", required=True)
    return parser


def main():
    argumentos = criar_parser().parse_args()

    if argumentos.url:
        destino, sha256 = baixar_fonte(
            argumentos.url,
            argumentos.destino,
        )
    else:
        destino, sha256 = copiar_fonte_local(
            argumentos.arquivo,
            argumentos.destino,
        )

    salvar_hash(destino, sha256)
    print(f"Fonte pronta: {destino}")
    print(f"SHA-256: {sha256}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as erro:
        print(f"Falha ao preparar fonte do IBGE: {erro}", file=sys.stderr)
        raise
```

Exemplo quando existir URL oficial em massa:

```powershell
python tools/nomes_ibge/baixar_fonte_ibge.py `
  --url "URL_HTTPS_OFICIAL_CONFIRMADA_NO_IBGE" `
  --destino "core/data/nomes_ibge/fontes/nomes_ibge.csv"
```

Exemplo com arquivo oficial baixado manualmente:

```powershell
python tools/nomes_ibge/baixar_fonte_ibge.py `
  --arquivo "C:\Downloads\nomes_ibge.csv" `
  --destino "core/data/nomes_ibge/fontes/nomes_ibge.csv"
```

---

## Passo 5 - Definir o contrato do arquivo de entrada

O gerador recebe CSV UTF-8 com estas colunas:

```csv
tipo,nome,frequencia
primeiro_nome,Maria,12111222
primeiro_nome,Joao,5123456
sobrenome,Silva,34123456
```

Valores validos de `tipo`:

```text
primeiro_nome
sobrenome
```

Se o arquivo oficial possuir outro formato, criar uma conversao pontual para
esse contrato somente depois de ler a documentacao da fonte. Nao adaptar o
gerador silenciosamente a colunas presumidas.

O nome original sera preservado para exibicao. Uma segunda versao normalizada,
sem diferenca de maiusculas ou acentos, sera usada na busca.

---

## Passo 6 - Criar o gerador do SQLite

Criar `tools/nomes_ibge/criar_base_sqlite.py`.

Codigo completo:

```python
import argparse
import csv
import hashlib
import re
import sqlite3
import sys
import unicodedata
from datetime import datetime, timezone
from pathlib import Path


SCHEMA_VERSION = "1"
TIPOS_VALIDOS = {"primeiro_nome", "sobrenome"}
CHUNK_BYTES = 1024 * 1024


def normalizar_termo(valor):
    decomposed = unicodedata.normalize("NFKD", valor.strip())
    sem_acentos = "".join(
        caractere
        for caractere in decomposed
        if unicodedata.category(caractere) != "Mn"
    )
    return re.sub(r"[^a-z]", "", sem_acentos.casefold())


def calcular_sha256(caminho):
    digest = hashlib.sha256()

    with Path(caminho).open("rb") as arquivo:
        for bloco in iter(lambda: arquivo.read(CHUNK_BYTES), b""):
            digest.update(bloco)

    return digest.hexdigest()


def ler_frequencia(valor):
    valor = (valor or "").strip()

    if not valor:
        return None

    frequencia = int(valor)

    if frequencia < 0:
        raise ValueError("Frequencia nao pode ser negativa")

    return frequencia


def criar_schema(conn):
    conn.executescript(
        """
        PRAGMA journal_mode = DELETE;
        PRAGMA synchronous = FULL;

        CREATE TABLE metadata (
            chave TEXT PRIMARY KEY,
            valor TEXT NOT NULL
        ) WITHOUT ROWID;

        CREATE TABLE termo (
            tipo TEXT NOT NULL
                CHECK (tipo IN ('primeiro_nome', 'sobrenome')),
            valor_normalizado TEXT NOT NULL,
            valor_exibicao TEXT NOT NULL,
            frequencia INTEGER,
            PRIMARY KEY (tipo, valor_normalizado)
        ) WITHOUT ROWID;
        """
    )


def inserir_termos(conn, fonte):
    quantidades = {
        "primeiro_nome": 0,
        "sobrenome": 0,
    }

    with Path(fonte).open("r", encoding="utf-8-sig", newline="") as arquivo:
        leitor = csv.DictReader(arquivo)
        colunas = set(leitor.fieldnames or [])
        esperadas = {"tipo", "nome", "frequencia"}

        if not esperadas.issubset(colunas):
            raise ValueError(
                "CSV precisa conter as colunas tipo,nome,frequencia"
            )

        for numero_linha, linha in enumerate(leitor, start=2):
            tipo = (linha.get("tipo") or "").strip().lower()
            nome = unicodedata.normalize(
                "NFC",
                (linha.get("nome") or "").strip(),
            )

            if tipo not in TIPOS_VALIDOS:
                raise ValueError(
                    f"Tipo invalido na linha {numero_linha}: {tipo}"
                )

            valor_normalizado = normalizar_termo(nome)

            if len(valor_normalizado) < 2:
                raise ValueError(
                    f"Nome invalido na linha {numero_linha}: {nome!r}"
                )

            frequencia = ler_frequencia(linha.get("frequencia"))

            conn.execute(
                """
                INSERT INTO termo (
                    tipo,
                    valor_normalizado,
                    valor_exibicao,
                    frequencia
                )
                VALUES (?, ?, ?, ?)
                ON CONFLICT (tipo, valor_normalizado)
                DO UPDATE SET
                    valor_exibicao = CASE
                        WHEN COALESCE(excluded.frequencia, -1)
                             > COALESCE(termo.frequencia, -1)
                        THEN excluded.valor_exibicao
                        ELSE termo.valor_exibicao
                    END,
                    frequencia = MAX(
                        COALESCE(termo.frequencia, -1),
                        COALESCE(excluded.frequencia, -1)
                    )
                """,
                (
                    tipo,
                    valor_normalizado,
                    nome,
                    frequencia,
                ),
            )

    for tipo in quantidades:
        quantidades[tipo] = conn.execute(
            "SELECT COUNT(*) FROM termo WHERE tipo = ?",
            (tipo,),
        ).fetchone()[0]

    return quantidades


def inserir_metadata(conn, *, fonte, sha256, quantidades):
    metadata = {
        "schema_version": SCHEMA_VERSION,
        "fonte_arquivo": Path(fonte).name,
        "fonte_sha256": sha256,
        "gerado_em_utc": datetime.now(timezone.utc).isoformat(),
        "quantidade_primeiros_nomes": str(
            quantidades["primeiro_nome"]
        ),
        "quantidade_sobrenomes": str(
            quantidades["sobrenome"]
        ),
    }

    conn.executemany(
        "INSERT INTO metadata (chave, valor) VALUES (?, ?)",
        metadata.items(),
    )


def validar_base(conn, *, minimo_nomes, minimo_sobrenomes):
    integridade = conn.execute("PRAGMA integrity_check").fetchone()[0]

    if integridade != "ok":
        raise RuntimeError(f"SQLite invalido: {integridade}")

    quantidade_nomes = conn.execute(
        "SELECT COUNT(*) FROM termo WHERE tipo = 'primeiro_nome'"
    ).fetchone()[0]
    quantidade_sobrenomes = conn.execute(
        "SELECT COUNT(*) FROM termo WHERE tipo = 'sobrenome'"
    ).fetchone()[0]

    if quantidade_nomes < minimo_nomes:
        raise RuntimeError(
            f"Poucos primeiros nomes: {quantidade_nomes} "
            f"(minimo {minimo_nomes})"
        )

    if quantidade_sobrenomes < minimo_sobrenomes:
        raise RuntimeError(
            f"Poucos sobrenomes: {quantidade_sobrenomes} "
            f"(minimo {minimo_sobrenomes})"
        )


def criar_base(
    fonte,
    destino,
    *,
    minimo_nomes,
    minimo_sobrenomes,
):
    fonte = Path(fonte).resolve()
    destino = Path(destino).resolve()
    temporario = destino.with_suffix(f"{destino.suffix}.part")

    if not fonte.is_file():
        raise FileNotFoundError(f"Fonte nao encontrada: {fonte}")

    destino.parent.mkdir(parents=True, exist_ok=True)
    temporario.unlink(missing_ok=True)

    conn = sqlite3.connect(temporario)

    try:
        criar_schema(conn)
        quantidades = inserir_termos(conn, fonte)
        inserir_metadata(
            conn,
            fonte=fonte,
            sha256=calcular_sha256(fonte),
            quantidades=quantidades,
        )
        validar_base(
            conn,
            minimo_nomes=minimo_nomes,
            minimo_sobrenomes=minimo_sobrenomes,
        )
        conn.commit()
        conn.execute("VACUUM")
        conn.close()
        conn = None
        temporario.replace(destino)
        return destino, quantidades
    except Exception:
        if conn is not None:
            conn.rollback()
        raise
    finally:
        if conn is not None:
            conn.close()
        temporario.unlink(missing_ok=True)


def criar_parser():
    parser = argparse.ArgumentParser(
        description="Gera a base SQLite local de nomes do IBGE.",
    )
    parser.add_argument("--fonte", required=True)
    parser.add_argument("--destino", required=True)
    parser.add_argument(
        "--minimo-nomes",
        type=int,
        default=100_000,
    )
    parser.add_argument(
        "--minimo-sobrenomes",
        type=int,
        default=150_000,
    )
    return parser


def main():
    argumentos = criar_parser().parse_args()
    destino, quantidades = criar_base(
        argumentos.fonte,
        argumentos.destino,
        minimo_nomes=argumentos.minimo_nomes,
        minimo_sobrenomes=argumentos.minimo_sobrenomes,
    )
    print(f"Base criada: {destino}")
    print(
        "Registros: "
        f"{quantidades['primeiro_nome']} primeiros nomes; "
        f"{quantidades['sobrenome']} sobrenomes"
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as erro:
        print(f"Falha ao gerar SQLite: {erro}", file=sys.stderr)
        raise
```

Comando de producao:

```powershell
python tools/nomes_ibge/criar_base_sqlite.py `
  --fonte "core/data/nomes_ibge/fontes/nomes_ibge.csv" `
  --destino "core/data/nomes_ibge/nomes_ibge.sqlite3"
```

Para uma fixture pequena de teste, os limites devem ser informados como `1`.

---

## Passo 7 - Criar o verificador do artefato

Criar `tools/nomes_ibge/verificar_base_sqlite.py`.

Codigo completo:

```python
import argparse
import sqlite3
import sys
from pathlib import Path


SCHEMA_VERSION_ESPERADA = "1"


def verificar_base(caminho, *, minimo_nomes, minimo_sobrenomes):
    caminho = Path(caminho).resolve()

    if not caminho.is_file():
        raise FileNotFoundError(f"SQLite nao encontrado: {caminho}")

    uri = f"{caminho.as_uri()}?mode=ro&immutable=1"
    conn = sqlite3.connect(uri, uri=True)

    try:
        integridade = conn.execute("PRAGMA integrity_check").fetchone()[0]

        if integridade != "ok":
            raise RuntimeError(f"Falha de integridade: {integridade}")

        metadata = dict(
            conn.execute("SELECT chave, valor FROM metadata").fetchall()
        )

        if metadata.get("schema_version") != SCHEMA_VERSION_ESPERADA:
            raise RuntimeError("Versao de schema inesperada")

        quantidade_nomes = conn.execute(
            "SELECT COUNT(*) FROM termo WHERE tipo = 'primeiro_nome'"
        ).fetchone()[0]
        quantidade_sobrenomes = conn.execute(
            "SELECT COUNT(*) FROM termo WHERE tipo = 'sobrenome'"
        ).fetchone()[0]

        if quantidade_nomes < minimo_nomes:
            raise RuntimeError("Quantidade insuficiente de primeiros nomes")

        if quantidade_sobrenomes < minimo_sobrenomes:
            raise RuntimeError("Quantidade insuficiente de sobrenomes")

        return {
            "metadata": metadata,
            "quantidade_nomes": quantidade_nomes,
            "quantidade_sobrenomes": quantidade_sobrenomes,
        }
    finally:
        conn.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", required=True)
    parser.add_argument("--minimo-nomes", type=int, default=100_000)
    parser.add_argument("--minimo-sobrenomes", type=int, default=150_000)
    argumentos = parser.parse_args()

    resultado = verificar_base(
        argumentos.base,
        minimo_nomes=argumentos.minimo_nomes,
        minimo_sobrenomes=argumentos.minimo_sobrenomes,
    )
    print("SQLite valido")
    print(resultado)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as erro:
        print(f"SQLite rejeitado: {erro}", file=sys.stderr)
        raise
```

---

## Passo 8 - Criar o repositorio local somente leitura

Criar `core/repositories/nomes_ibge.py`.

Este repositorio nao usa PostgreSQL e nao participa das transacoes do worker.
Ele e um catalogo local de referencia. Cada thread recebe sua propria conexao
SQLite preguiçosa.

Codigo completo:

```python
import logging
import re
import sqlite3
import threading
import unicodedata
from pathlib import Path

from core.config_env import PROJECT_ROOT, env_bool, env_optional


logger = logging.getLogger("core.repositories.nomes_ibge")

SCHEMA_VERSION_ESPERADA = "1"
CAMINHO_PADRAO = (
    PROJECT_ROOT / "core" / "data" / "nomes_ibge" / "nomes_ibge.sqlite3"
)


def normalizar_termo_ibge(valor):
    decomposed = unicodedata.normalize("NFKD", (valor or "").strip())
    sem_acentos = "".join(
        caractere
        for caractere in decomposed
        if unicodedata.category(caractere) != "Mn"
    )
    return re.sub(r"[^a-z]", "", sem_acentos.casefold())


class BaseNomesIBGE:
    def __init__(self, caminho=None, habilitada=None):
        caminho_configurado = caminho or env_optional(
            "NOMES_IBGE_SQLITE_PATH",
            str(CAMINHO_PADRAO),
        )
        self._caminho = Path(caminho_configurado).resolve()
        self._habilitada = (
            env_bool("NOMES_IBGE_ENABLED", False)
            if habilitada is None
            else bool(habilitada)
        )
        self._local = threading.local()
        self._aviso_emitido = False
        self._lock_aviso = threading.Lock()

    @property
    def caminho(self):
        return self._caminho

    def disponivel(self):
        if not self._habilitada:
            return False

        try:
            self._obter_conexao()
            return True
        except (OSError, sqlite3.Error, RuntimeError) as erro:
            self._avisar_indisponibilidade(erro)
            return False

    def termo_conhecido(self, tipo, valor):
        registro = self._buscar(tipo, valor)
        return registro is not None

    def obter_exibicao(self, tipo, valor):
        registro = self._buscar(tipo, valor)

        if registro is None:
            return None

        return registro[0]

    def _buscar(self, tipo, valor):
        if tipo not in {"primeiro_nome", "sobrenome"}:
            raise ValueError(f"Tipo de termo invalido: {tipo}")

        valor_normalizado = normalizar_termo_ibge(valor)

        if not valor_normalizado or not self.disponivel():
            return None

        try:
            return self._obter_conexao().execute(
                """
                SELECT valor_exibicao, frequencia
                FROM termo
                WHERE tipo = ?
                  AND valor_normalizado = ?
                LIMIT 1
                """,
                (tipo, valor_normalizado),
            ).fetchone()
        except (OSError, sqlite3.Error, RuntimeError) as erro:
            self.fechar_conexao_thread()
            self._avisar_indisponibilidade(erro)
            return None

    def _obter_conexao(self):
        conexao = getattr(self._local, "conexao", None)

        if conexao is not None:
            return conexao

        if not self._caminho.is_file():
            raise FileNotFoundError(self._caminho)

        uri = f"{self._caminho.as_uri()}?mode=ro&immutable=1"
        conexao = sqlite3.connect(
            uri,
            uri=True,
            timeout=1,
        )
        conexao.execute("PRAGMA query_only = ON")
        schema_version = conexao.execute(
            """
            SELECT valor
            FROM metadata
            WHERE chave = 'schema_version'
            """
        ).fetchone()

        if not schema_version or schema_version[0] != SCHEMA_VERSION_ESPERADA:
            conexao.close()
            raise RuntimeError("Schema da base de nomes incompativel")

        self._local.conexao = conexao
        return conexao

    def fechar_conexao_thread(self):
        conexao = getattr(self._local, "conexao", None)

        if conexao is not None:
            conexao.close()
            del self._local.conexao

    def _avisar_indisponibilidade(self, erro):
        with self._lock_aviso:
            if self._aviso_emitido:
                return

            self._aviso_emitido = True
            logger.warning(
                "base_nomes_ibge_indisponivel | "
                "acao=usar_detector_deterministico caminho=%s erro=%s",
                self._caminho,
                erro,
            )


base_nomes_ibge = BaseNomesIBGE()
```

O warning e emitido uma vez por processo para evitar poluir os logs.

---

## Passo 9 - Configurar variaveis de ambiente

Adicionar ao `.env.example`:

```dotenv

# Base local opcional de nomes e sobrenomes do IBGE.
NOMES_IBGE_ENABLED=False
NOMES_IBGE_SQLITE_PATH=core/data/nomes_ibge/nomes_ibge.sqlite3
```

No ambiente de producao:

```dotenv
NOMES_IBGE_ENABLED=True
NOMES_IBGE_SQLITE_PATH=/app/core/data/nomes_ibge/nomes_ibge.sqlite3
```

Durante desenvolvimento, `False` preserva exatamente o comportamento atual.

---

## Passo 10 - Integrar ao `detector_nome.py`

Arquivo:

```text
workers/worker_flow/response_flow/etapas/detector_etapas/detector_nome.py
```

Essa integracao deve ser cirurgica. Nao reescrever as listas, regex ou regras
atuais.

### 10.1 Import

Adicionar junto aos imports:

```python
from core.repositories.nomes_ibge import base_nomes_ibge
```

### 10.2 Sobrenome

Substituir `_e_sobrenome_comum` por:

```python
def _e_sobrenome_comum(palavra):
    palavra_compactada = re.sub(r"[-'’]", "", palavra)

    if palavra_compactada in SOBRENOMES_COMUNS_BRASIL:
        return True

    return base_nomes_ibge.termo_conhecido(
        "sobrenome",
        palavra_compactada,
    )
```

Efeito:

```text
sobrenome na lista local -> resposta imediata
sobrenome fora da lista local -> consulta SQLite
SQLite indisponivel ou miss -> False, mantendo o fluxo atual
```

### 10.3 Grafia canonica

Substituir `_formatar_parte_nome` por:

```python
def _formatar_parte_nome(palavra):
    chave_normalizada = normalizar_texto(palavra)
    nome_com_til = NOMES_BRASILEIROS_COM_TIL.get(chave_normalizada)

    if nome_com_til:
        return nome_com_til

    nome_ibge = base_nomes_ibge.obter_exibicao(
        "primeiro_nome",
        palavra,
    )

    if nome_ibge:
        return nome_ibge

    return palavra[:1].upper() + palavra[1:].lower()
```

Exemplos:

```text
joao -> Joao ou Joao conforme a grafia publicada pela fonte
jose -> Jose ou Jose conforme a grafia publicada pela fonte
nome raro ausente -> capitalizacao atual
```

O arquivo fonte pode omitir acentos conforme a metodologia da edicao. Por isso,
as excecoes atuais de `NOMES_BRASILEIROS_COM_TIL` continuam tendo prioridade.

### 10.4 Regra de seguranca

Nao adicionar isto:

```python
if not base_nomes_ibge.termo_conhecido("primeiro_nome", nome):
    return invalido
```

O IBGE protege sigilo estatistico e pode omitir nomes raros. A ausencia na base
nao prova que o nome e falso.

---

## Passo 11 - Criar fixture pequena

Criar `tests/fixtures/nomes_ibge_amostra.csv`.

Conteudo completo:

```csv
tipo,nome,frequencia
primeiro_nome,Maria,1000
primeiro_nome,Joao,900
primeiro_nome,Jose,800
primeiro_nome,Edcarlos,20
sobrenome,Silva,2000
sobrenome,Santos,1800
sobrenome,Watanabe,100
```

---

## Passo 12 - Testar geracao e repositorio

Criar `tests/unit/test_base_nomes_ibge.py`.

Codigo completo:

```python
import sqlite3
import tempfile
import unittest
from pathlib import Path

from core.repositories.nomes_ibge import BaseNomesIBGE


def criar_base_teste(caminho):
    conn = sqlite3.connect(caminho)
    conn.executescript(
        """
        CREATE TABLE metadata (
            chave TEXT PRIMARY KEY,
            valor TEXT NOT NULL
        ) WITHOUT ROWID;

        CREATE TABLE termo (
            tipo TEXT NOT NULL,
            valor_normalizado TEXT NOT NULL,
            valor_exibicao TEXT NOT NULL,
            frequencia INTEGER,
            PRIMARY KEY (tipo, valor_normalizado)
        ) WITHOUT ROWID;

        INSERT INTO metadata VALUES ('schema_version', '1');
        INSERT INTO termo VALUES (
            'primeiro_nome', 'joao', 'Joao', 100
        );
        INSERT INTO termo VALUES (
            'sobrenome', 'watanabe', 'Watanabe', 50
        );
        """
    )
    conn.commit()
    conn.close()


class BaseNomesIBGETests(unittest.TestCase):
    def test_consulta_nome_e_sobrenome(self):
        with tempfile.TemporaryDirectory() as pasta:
            caminho = Path(pasta) / "nomes.sqlite3"
            criar_base_teste(caminho)
            base = BaseNomesIBGE(caminho=caminho, habilitada=True)

            self.assertTrue(
                base.termo_conhecido("primeiro_nome", "Joao")
            )
            self.assertTrue(
                base.termo_conhecido("sobrenome", "Watanabe")
            )
            self.assertFalse(
                base.termo_conhecido("primeiro_nome", "Rarissimo")
            )

    def test_base_ausente_falha_aberta(self):
        with tempfile.TemporaryDirectory() as pasta:
            caminho = Path(pasta) / "ausente.sqlite3"
            base = BaseNomesIBGE(caminho=caminho, habilitada=True)

            self.assertFalse(
                base.termo_conhecido("primeiro_nome", "Maria")
            )

    def test_base_desabilitada_nao_abre_arquivo(self):
        base = BaseNomesIBGE(
            caminho="arquivo-inexistente.sqlite3",
            habilitada=False,
        )

        self.assertFalse(base.disponivel())


if __name__ == "__main__":
    unittest.main()
```

Criar `tests/unit/test_criar_base_nomes_ibge.py`.

Codigo completo:

```python
import sqlite3
import tempfile
import unittest
from pathlib import Path

from tools.nomes_ibge.criar_base_sqlite import criar_base


PROJECT_ROOT = Path(__file__).resolve().parents[2]
FIXTURE = PROJECT_ROOT / "tests" / "fixtures" / "nomes_ibge_amostra.csv"


class CriarBaseNomesIBGETests(unittest.TestCase):
    def test_gera_base_valida_com_metadata(self):
        with tempfile.TemporaryDirectory() as pasta:
            destino = Path(pasta) / "nomes.sqlite3"
            _, quantidades = criar_base(
                FIXTURE,
                destino,
                minimo_nomes=1,
                minimo_sobrenomes=1,
            )

            self.assertEqual(quantidades["primeiro_nome"], 4)
            self.assertEqual(quantidades["sobrenome"], 3)

            conn = sqlite3.connect(destino)

            try:
                metadata = dict(
                    conn.execute(
                        "SELECT chave, valor FROM metadata"
                    ).fetchall()
                )
                self.assertEqual(metadata["schema_version"], "1")
                self.assertIn("fonte_sha256", metadata)
            finally:
                conn.close()


if __name__ == "__main__":
    unittest.main()
```

### Testes adicionais obrigatorios no detector

Atualizar `tests/unit/test_detector_nome.py` e
`tests/unit/test_detector_nome_v1.py` para cobrir:

```text
SQLite desligado -> todos os testes atuais continuam iguais
SQLite ausente -> nome raro aceito conforme regra atual
Watanabe reconhecido como sobrenome pela base
termo pejorativo presente na base -> continua invalido
numero e caractere invalido -> continuam invalidos
nome raro ausente -> nao e barrado pela ausencia
grafia canonica conhecida -> formatada
```

Os testes nao devem depender do banco real de 10 a 25 MB. Devem criar uma base
temporaria pequena.

---

## Passo 13 - Criar `.dockerignore`

Como ainda nao existe Docker no projeto, criar:

```dockerignore
.git
.idea
.env
.env.*
!.env.example
__pycache__
*.pyc
*.pyo
*.pyd
.pytest_cache
codex_patch
_V2
_tarefas_finais
core/data/nomes_ibge/fontes
```

Nao ignorar:

```text
core/data/nomes_ibge/nomes_ibge.sqlite3
```

O banco gerado precisa entrar na imagem.

---

## Passo 14 - Criar `Dockerfile.worker`

Codigo completo:

```dockerfile
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV NOMES_IBGE_ENABLED=True
ENV NOMES_IBGE_SQLITE_PATH=/app/core/data/nomes_ibge/nomes_ibge.sqlite3

WORKDIR /app

COPY requirements.txt /app/requirements.txt

RUN python -m pip install --no-cache-dir --upgrade pip \
    && python -m pip install --no-cache-dir -r /app/requirements.txt

COPY . /app

RUN python tools/nomes_ibge/verificar_base_sqlite.py \
    --base /app/core/data/nomes_ibge/nomes_ibge.sqlite3

CMD ["python", "-m", "workers.worker_flow.main_worker"]
```

O `RUN verificar_base_sqlite.py` faz o build falhar se a base estiver ausente,
incompleta ou corrompida.

O arquivo fica dentro da camada imutavel da imagem. Nao e necessario volume,
servidor SQLite ou endereco publico para ele.

---

## Passo 15 - Sequencia local completa

```powershell
# 1. Confirmar o SQLite embutido no Python.
python -c "import sqlite3; print(sqlite3.sqlite_version)"

# 2. Preparar a fonte oficial.
python tools/nomes_ibge/baixar_fonte_ibge.py `
  --arquivo "C:\Downloads\nomes_ibge.csv" `
  --destino "core/data/nomes_ibge/fontes/nomes_ibge.csv"

# 3. Gerar o minibanco.
python tools/nomes_ibge/criar_base_sqlite.py `
  --fonte "core/data/nomes_ibge/fontes/nomes_ibge.csv" `
  --destino "core/data/nomes_ibge/nomes_ibge.sqlite3"

# 4. Verificar.
python tools/nomes_ibge/verificar_base_sqlite.py `
  --base "core/data/nomes_ibge/nomes_ibge.sqlite3"

# 5. Rodar testes.
python -m unittest discover -s tests -v
python -m compileall core workers callback tests tools
python callback/manage.py check
git diff --check

# 6. Construir imagem do worker.
docker build -f Dockerfile.worker -t chatbot-worker:nomes-ibge .

# 7. Executar smoke test da base dentro da imagem.
docker run --rm --entrypoint python chatbot-worker:nomes-ibge `
  tools/nomes_ibge/verificar_base_sqlite.py `
  --base /app/core/data/nomes_ibge/nomes_ibge.sqlite3
```

---

## Passo 16 - Hospedagem com Docker na AWS

O SQLite nao precisa de dominio nem de servidor proprio.

Separacao:

```text
ECR
-> armazena a imagem Docker

ECS/Fargate ou EC2
-> executa o container do worker 24x7

arquivo SQLite
-> viaja dentro da imagem e e lido localmente

dominio publico
-> necessario para o webhook, nao para o worker nem para o SQLite
```

### Fluxo de publicacao

1. Criar um repositorio privado no Amazon ECR.
2. Autenticar o Docker no ECR.
3. Gerar e verificar o SQLite.
4. Construir a imagem.
5. Marcar a imagem com tag imutavel, por exemplo data e hash da fonte.
6. Enviar a imagem ao ECR.
7. Atualizar a task definition do worker no ECS.
8. Informar as variaveis de ambiente e segredos pelo ambiente da task.
9. Implantar uma task do worker na V1.
10. Verificar logs e consultas.

Exemplo de tags:

```text
chatbot-worker:2026-06-ibge-<sha-curto>
chatbot-worker:stable
```

O deploy deve apontar para uma tag imutavel ou digest. `stable` pode ser apenas
um atalho humano.

### Fonte em pipeline

Como o SQLite e a fonte estao ignorados no Git, existem duas opcoes:

```text
Opcao A
pipeline baixa a fonte de uma URL publica oficial do IBGE
-> gera SQLite
-> cria imagem

Opcao B
arquivo oficial validado e guardado em S3 privado com versionamento
-> pipeline baixa pelo SHA esperado
-> gera SQLite
-> cria imagem
```

A opcao B e adequada quando nao existe URL oficial em massa estavel. O bucket S3
serve como armazenamento do artefato de build, nao como banco consultado pelo
worker.

O worker nunca deve baixar ou atualizar a base ao iniciar. Isso evitaria:

- indisponibilidade do IBGE derrubando o bot;
- mudanca silenciosa de dados;
- containers com versoes diferentes;
- aumento de latencia e custo.

---

## Passo 17 - Atualizacao futura da base

Quando o IBGE publicar nova edicao:

```text
1. baixar nova fonte oficial
2. conferir URL, metodologia e licenca
3. registrar SHA-256
4. gerar novo SQLite temporario
5. validar quantidades e integridade
6. rodar toda a suite
7. criar nova imagem Docker
8. implantar
9. manter imagem anterior para rollback
```

Nao atualizar o arquivo dentro de um container em execucao.

---

## Passo 18 - Documentacao a atualizar na aplicacao

Somente quando esta tarefa for implementada:

1. Atualizar `README.md` com o comando de geracao.
2. Atualizar `core/repositories/README.md` explicando o catalogo SQLite local.
3. Atualizar `workers/README.md` com o fallback deterministico.
4. Atualizar `tests/README.md` com os testes da base temporaria.
5. Atualizar `PADROES_DE_ARQUITETURA.md` para registrar a excecao:
   o SQLite de referencia fica em `core/repositories`, mas nao participa das
   transacoes PostgreSQL do fluxo.
6. Atualizar `_V2/VALIDACAO_NOME_V2.md`, se ainda representar a estrategia
   vigente.

---

## Impacto esperado

Estimativa conservadora:

```text
arquivo SQLite: aproximadamente 10 a 25 MB
RAM incremental: aproximadamente 2 a 10 MB por processo
consulta local indexada: normalmente abaixo de poucos milissegundos
trafego de rede por validacao: zero
custo direto do SQLite: zero
```

O tamanho real deve ser medido depois da fonte oficial ser obtida. O build deve
registrar tamanho, quantidade de linhas e hash.

---

## Falhas e comportamento

### SQLite ausente

```text
NOMES_IBGE_ENABLED=True
arquivo ausente
-> warning uma vez
-> detector deterministico atual
-> worker continua
```

### SQLite corrompido

```text
build normal
-> verificacao falha
-> imagem nao e criada

falha inesperada em runtime
-> warning uma vez
-> fecha conexao local
-> detector deterministico atual
```

### Nome ausente no IBGE

```text
nome passa pelas regras deterministicas
IBGE nao encontrou
-> nao rejeitar por esse motivo
```

### Termo invalido encontrado na base

```text
regra deterministica marca pejorativo/numero/caractere invalido
IBGE eventualmente possui termo parecido
-> regra deterministica vence
-> tratamento de nome invalido
```

---

## Criterios de aceite

O plano somente sera considerado aplicado quando:

1. A fonte for oficial e seu SHA-256 estiver registrado.
2. Nao houver endpoint privado ou scraping.
3. A base contiver quantidades coerentes com a edicao escolhida.
4. `PRAGMA integrity_check` retornar `ok`.
5. O worker nao fizer requisicao ao IBGE em runtime.
6. O arquivo abrir em modo somente leitura.
7. A ausencia da base preservar o detector atual.
8. Um nome raro nao for barrado apenas por nao constar no IBGE.
9. Regras de numero, caractere e termo pejorativo continuarem prioritarias.
10. Todos os testes atuais e novos passarem.
11. O Docker build falhar quando o banco estiver ausente.
12. O smoke test funcionar dentro do container.
13. Nenhuma regra de fila, turno, retry, historico ou transacao for alterada.
14. O worker continuar sendo executado por
    `python -m workers.worker_flow.main_worker`.

## Resultado final

Depois da aplicacao:

```text
detector atual
-> valida estrutura e seguranca
-> consulta catalogo local quando isso agrega informacao
-> reconhece mais sobrenomes
-> melhora grafia de nomes conhecidos
-> aceita nomes raros pelo fallback atual
-> nunca depende da internet durante o atendimento
```

Esta e uma melhoria de precisao e enriquecimento. Ela nao deve transformar o
catalogo do IBGE em uma lista fechada de quem pode ou nao ser cliente.
