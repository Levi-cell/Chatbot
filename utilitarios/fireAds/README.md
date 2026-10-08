# Testes manuais da FireAds

| Destino | Arquivos |
| --- | --- |
| Planilha, pela URL do Apps Script (`URL_DASHBOARD`) | `test_dash_post.py`, `test_dash_update.py`, `test_dash_delete.py` e a consulta `test_Dash.py` |
| Webhook do Eduardo (`URL_WEBHOOK`) | `test_post.py` |

## Utilitários originais de consulta e envio ao webhook

Os utilitários originais `test_post.py` e `test_Dash.py` usam o número **(71) 99411-1866**, normalizado como
`5571994111866`, em `config_teste.py`. Não acessam o banco do chatbot nem enviam
oportunidades ao Funil.

1. Executar `test_post.py` pelo Run do PyCharm faz **um POST real** ao webhook
   informado por Eduardo. O terminal mostra o JSON enviado, o HTTP, cabeçalhos
   de diagnóstico e o corpo da resposta. Não há reenvio automático.
2. Executar `test_Dash.py` consulta o mesmo número e mostra os registros encontrados.
   Pode ser repetido para verificar eventual atraso do dashboard, sem reenviar o POST.

O JSON de inclusão é **experimental**: foram escolhidos campos de nome, telefone,
e-mail fictício, origem orgânica e identificação do teste. Ainda precisamos
confirmar os nomes esperados pelo fluxo de Eduardo. Sucesso HTTP comprova a
resposta do webhook, mas não garante que o cadastro foi gravado na planilha.

Também é possível executar a partir da raiz do projeto:

```powershell
python -m utilitarios.fireAds.test_post --payload
python -m utilitarios.fireAds.test_post
python -m utilitarios.fireAds.test_Dash
```

`--payload` somente exibe os dados. Importar os módulos não faz requisições.
O identificador `id_teste` muda a cada execução; ele permite correlacionar o envio,
mas não é garantia de deduplicação pelo webhook. Não repetir um POST de resultado
incerto sem conferir o dashboard.

A consulta aproveita a estrutura da sonda original da raiz. Diferencia erro de
ausência nos dados retornados, prioriza telefone exato e mostra todos os registros
correspondentes. Paginação, filtros e prazo de sincronização ainda não foram
confirmados com a agência.

## Resultado do primeiro envio — 05/10/2026

- POST único às **19:03:09 (America/Sao_Paulo)**.
- Identificador: `esl-fireads-5b93c902caa0468ab506c9e8e6d35187`.
- Resposta: **HTTP 200 OK**, corpo `{"message":"Workflow was started"}`.
- Foram feitas duas consultas posteriores, ambas com HTTP 200 e 678 registros.
- O telefone já aparece nas linhas 511 e 512, com datas **31/08/2026 18:03** e
  **31/08/2026 18:22**, nome `Edcarlos Teste Santo André - Não contatar` e canal
  `Meta Ads`. São registros anteriores, não confirmação de cadastro novo.
- Na rechecagem de **19:04:58**, nenhum registro retornado continha o nome, e-mail
  fictício ou identificador do POST atual.

Resultado: recebimento/início do workflow confirmado pela resposta HTTP;
**gravação do teste atual no dashboard ainda não confirmada**. Pode haver atraso,
deduplicação, divergência de campos ou falha interna; a resposta não permite
distinguir essas hipóteses. Não houve segundo POST.

Encontrar um telefone já cadastrado não comprova que a execução atual criou ou
atualizou uma linha. Para investigar com Eduardo, usar o horário, identificador,
JSON de `test_post.py` e corpo da resposta acima. Ainda falta o contrato dos campos.

## Testes de cadastro, atualização e exclusão na URL_DASHBOARD

O código do Apps Script foi fornecido em **07/10/2026**. Com ele, os testes
deixaram de adivinhar nomes de ações e passaram a respeitar as operações existentes:

| Arquivo | Comportamento atual |
| --- | --- |
| `test_dash_post.py` | Segundo teste: tenta cadastrar **Carlos**, telefone fictício **550000000002**, com `action: "append"`. Executar pelo Run do PyCharm, sem parâmetros. |
| `test_dash_update.py` | Localiza o cadastro de **Carlos** e altera somente **Observação**, colocando o texto do teste com **` 2`** no final. Run no PyCharm, sem parâmetros. |
| `test_dash_delete.py` | Informa que não existe operação de exclusão de leads no código recebido e sai sem requisições. |

Esses nomes substituem `testDash_post.py`, `testDash_update.py` e
`testDash_delete.py`; não há duas versões de cada operação.

Os testes se referem a `URL_DASHBOARD` e `ABA_DASHBOARD` do `config_teste.py`. Não usam
`URL_WEBHOOK`, não acessam o banco/cache do chatbot e não enviam ao Funil.
O código compartilhado fica em `dash_crud_teste.py`, incluindo a identidade
do contato de teste e a montagem dos pedidos.

### URL de execução e URL do editor

- `URL_DASHBOARD`, terminada em `/exec`: recebe as consultas e o POST de cadastro.
- O link `/home/projects/.../edit` enviado pelo Eduardo: abre o editor do projeto.
  Não é um segundo endereço que precisa ser chamado ou enviado junto no POST.
  Não é usado pelos utilitários.

O código visível no editor pode ser diferente da versão publicada na URL `/exec`.
O teste ainda depende da versão implantada pelo responsável; não altera o Apps Script.

### Formato de cadastro identificado no código

`doPost(e)` encaminha `action: "append"` para `appendRows(body)`:

```json
{
  "action": "append",
  "sheet": "LEADS GERAL - Feedback",
  "rows": [
    {
      "Nome": "Carlos",
      "WhatsApp": "550000000002",
      "Email": "email-de-teste@example.com"
    }
  ]
}
```

Esse é um exemplo reduzido: o utilitário inclui o e-mail exclusivo, observação e
demais dados do teste. As chaves de cada item de `rows` precisam corresponder a
colunas existentes. Não se envia `row` para cadastrar: o script acrescenta no fim
da aba, preenche Data/Hora e retorna `success`, `inserted` e `aba`.
No código fornecido, `ALLOW_APPEND` está habilitado. Há limite de 500 linhas por
pedido; nosso teste envia apenas uma. O exemplo `action: "create"` anterior era
uma hipótese incompatível com essa implementação.

### Limites de atualização e exclusão

A edição existente usa `{sheet, row, updates: {coluna: valor}}`, ou o formato
antigo `{sheet, row, column, value}`. `row` é a linha real devolvida em `_row` na
consulta. O servidor exige linha maior que o cabeçalho e já existente.

**Somente `Feedback Comercial` e `Observação` estão em `CONFIG.EDITABLE_COLUMNS`.**
O pedido anterior de mudar o nome foi substituído pelo teste de **Observação**.
O `test_dash_update.py` envia em `updates` somente esse campo, com o texto exato:

```text
[esl-dash-crud-67ae21f904d8] Cadastro de teste na planilha. NAO CONTATAR. 2
```

Nome, telefone, e-mail, canal e feedback não são enviados para edição. O utilitário
consulta primeiro, exige um único registro com a identidade do teste e obtém sua
linha pelo `_row`. Não usa linha fixa. Se não encontrar o cadastro, se houver
duplicidade ou se `_row` for inválido, não envia a atualização. Se o texto já for
exatamente o solicitado, não repete o POST nem acrescenta outro `2`.

Não existe ação de exclusão de **leads** em `doPost(e)`. As ações de gestão de
usuários são de outra tabela e não servem para excluir contatos. O arquivo de
exclusão permanece reservado, sem enviar uma ação inventada.

O teste atual usa **550000000002**, número fictício com DDD 00, e uma nova
identificação: `esl-dash-crud-67ae21f904d8`. O e-mail exclusivo usa `example.com`
e a observação contém essa identificação. O Apps Script fornecido grava o campo
WhatsApp sem validar DDD. O utilitário compara esse número fictício diretamente;
para números brasileiros reais, mantém suporte a máscara e nono dígito.
A configuração do teste fica no início de `dash_crud_teste.py`.

O primeiro teste usou **5571994111866**, com identificação
`esl-dash-crud-9f327a8ec601`, e foi localizado na linha **695**, data/hora exibida
**07/10/2026 07:49**. A segunda execução desse mesmo teste foi interrompida pelo
próprio utilitário com `Este cadastro de teste ja existe`, sem enviar outro POST.
O teste atual tem número, e-mail e identificação diferentes; mantém a proteção
para não duplicar esse novo cadastro quando o arquivo for executado novamente.

Os testes de cadastro e atualização consultam a aba antes e depois da tentativa, mostram HTTP, cabeçalhos
e corpo da resposta. Um HTTP 200 sozinho não confirma alteração. O resultado
é comparado com os dados visíveis na consulta posterior, que pode sofrer atraso
ou filtros. A consulta informa a quantidade de registros com o telefone de teste e exibe
somente os dados dos registros identificados como este teste.

- Cadastros antigos com seu telefone não impedem o teste de criação. O cadastro
  não é reenviado se o e-mail ou identificador deste teste já aparecer no mesmo número.
- Cada execução de cadastro ou atualização faz no máximo um POST, sem retry. Um redirecionamento 302/303 para
  o conteúdo do Google é consultado com GET, sem repetir a operação de escrita.
- No anexo, o login por usuário está desabilitado, mas existe suporte a token
  de acesso nas propriedades do script. O utilitário não muda autenticação e
  mostra a recusa caso a implantação exija credenciais.

Para apenas visualizar os pedidos, sem acessar a rede (a prévia de atualização
não inclui `row`, pois a linha real só será obtida na consulta da execução normal):

```powershell
python -m utilitarios.fireAds.test_dash_post --payload
python -m utilitarios.fireAds.test_dash_update --payload
```

Os arquivos foram validados localmente com respostas simuladas; isso não confirma
qual versão do código está implantada no dashboard nem gravação real.

### Diagnóstico do POST na planilha — 07/10/2026

Na execução real informada pelo usuário, o POST recebeu um redirecionamento 302.
A resposta final foi HTTP 200 com `{"success":false,"error":"Linha inválida."}`.
A consulta seguinte encontrou seis registros do telefone, mas nenhum identificado
como este teste. O cadastro não foi confirmado, e o script declarou falha.

O teste agora destaca o erro devolvido pelo Apps Script e termina com código 4
quando há falha declarada e a consulta não confirma o resultado. Não apresenta
esse caso apenas como possível atraso. Se a consulta mostrar o resultado esperado
apesar da resposta de falha, informa a divergência e retorna 2, sem repetir o POST.

O código recebido depois esclareceu a causa: `action: "create"` não é tratado
como cadastro; o pedido continua até a validação da edição e falha por não ter
`row`. A correção é usar `append` e `rows`, não acrescentar uma linha aleatória.
Se o mesmo erro persistir com o pedido corrigido, será necessário conferir se o
código publicado no `/exec` corresponde à versão fornecida.
