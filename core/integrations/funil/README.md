# Funil de Vendas

Adaptador da ApiCarrossel usado para criar uma oportunidade por conversa
elegível. Esta camada recebe dados prontos e não conhece PostgreSQL, retries ou
o ciclo do worker.

## Arquivos

```text
core/integrations/funil/
├── cliente.py             POST, URL e validação da resposta lógica
├── oportunidades.py       payload e texto de observações
└── exceptions.py          falhas conhecidas da integração
```

`cliente.py` exige simultaneamente:

```text
HTTP sem erro
e
JSON response = success
```

A API pode devolver HTTP 200 com `response = failure`; esse caso não confirma
`lead_no_funil`.

## E-mail no snapshot da conversa

O e-mail enviado ao Funil é reconstruído a partir da resposta da etapa 10 da
própria conversa, vinculada à resposta do bot na etapa 11. O valor atual de
`cliente.email` serve apenas como compatibilidade para atendimentos legados e
não pode substituir o resultado histórico de uma conversa nova.

Quando a política de e-mail permitiu avançar sem endereço, `contato.email` é
enviado vazio e as observações distinguem `não tem` (ausência declarada) de
`não informado` (outra resposta aceita). Nunca é enviado um texto fictício no
campo técnico de e-mail.

Essa reconstrução classifica a resposta que já avançou de `10 -> 11`; não
reaplica `email_obrigatorio` nem a idade com a configuração atual da unidade.
O worker decide a política e o repositório fornece a resposta histórica;
`core/validacoes/email.py` é compartilhado com a integração para manter a
mesma classificação.

## Profissão no snapshot da conversa

A profissão vem exclusivamente de `conversa.profissao`, capturada na etapa 4.
`cliente.profissao` pode mudar em outro atendimento e não substitui esse
snapshot. Sem profissão na conversa, as observações exibem `Não informada`.

## Identificação da oportunidade

O payload usa o título `Chatbot Lead <nome_unidade>`. O destaque principal em
`empresa.nome` contém nome e idade do titular ou nome do titular, nome e idade
do dependente. O ID da conversa não faz parte do título atual; ele não é uma
chave de idempotência externa. As garantias locais e a janela de possível
duplicidade estão no [README dos workers](../../../workers/README.md#worker-do-funil).

## Teste manual

Os testes usam dados fictícios específicos por unidade e só enviam com
confirmação explícita:

```bash
python -m utilitarios.integrations.funil_saj_teste payload
python -m utilitarios.integrations.funil_saj_teste \
  send-test --confirm-real-send
python -m utilitarios.integrations.funil_rio_teste payload
python -m utilitarios.integrations.funil_rio_teste \
  send-test --confirm-real-send
python -m utilitarios.integrations.funil_andre_teste payload
python -m utilitarios.integrations.funil_andre_teste \
  send-test --confirm-real-send
```

SAJ e Rio também oferecem o comando `catalog` para conferir os códigos obtidos
do banco. Santo André ainda usa configuração explícita de teste e não possui
esse comando. Em SAJ e Rio, use os subcomandos documentados. Em Santo André, o
ponto de entrada sem argumentos é um atalho intencional para envio real; use-o
somente quando quiser criar a oportunidade de teste e prefira `payload` para
inspeção sem envio. Cada sonda cria uma oportunidade claramente marcada com sua
unidade. Antes de ativar o worker, confira no CRM pessoa, telefone, e-mail,
título, observações e origem.
Os dois últimos são enviados pelo mecanismo `personalizados` com os títulos
exatos `Observações` e `Origem do lead`; a unidade precisa possuir campos
compatíveis no ApiCarrossel.

O teste nunca consulta dados reais do chatbot, não é chamado pelo worker e
jamais envia apenas por importar o módulo.
