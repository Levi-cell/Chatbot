from pathlib import Path
import ast
import hashlib
import json
import re

here = Path(__file__).parent
base = here.parents[1]
doc = (base / 'docs/valida_dados_parciais_fireads.md').read_text(encoding='utf-8')
paths = json.loads((here / 'changes.json').read_text(encoding='utf-8'))
found = []
for match in re.finditer(r'^## Passo (\d+) — `([^`]+)`\n', doc, re.M):
    num, path = match.groups()
    remaining = doc[match.end():]
    opening = re.search(r'^(\x60{3,4})(python|markdown|sql)\n', remaining, re.M)
    assert opening is not None, path
    fence = opening.group(1)
    content = remaining[opening.end():].split('\n' + fence + '\n', 1)[0] + '\n'
    expected = (here / 'candidate' / path).read_text(encoding='utf-8').rstrip() + '\n'
    assert content == expected, path
    digest = hashlib.sha256(content.encode('utf-8')).hexdigest()
    assert f'SHA-256 proposto (UTF-8/LF): `{digest}`.' in remaining[:opening.start()], path
    if path.endswith('.py'):
        ast.parse(content, filename=path)
    assert int(num) == len(found) + 1
    found.append(path)
assert set(found) == set(paths) and len(found) == len(paths) == 33
assert found[-1] == 'deploy/migrations/20261019_coleta_abertura.sql'
assert 'Validação em andamento' not in doc
print('DOCUMENTO_OK: 33 arquivos completos, hashes e sintaxe conferidos; SQL no último passo.')
