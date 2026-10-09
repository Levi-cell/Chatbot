# Plano prático — FireAds, chat e atendimento customizado

**Revisão: 09/10/2026. Status: código aplicado localmente; deploy e migração de produção pendentes.**

Este documento contém o código integral de **53 arquivos**, um por passo.
O último passo contém a migração SQL completa para executar no DBeaver no dia
do deploy. O código foi aplicado no projeto local e validado com PostgreSQL
descartável. A VM, o RDS e os serviços de produção não foram alterados.
Não iniciar o código novo sobre o banco antigo.

Base de aplicação: **backup 37b0265, de 08/10/2026**, sobre a V1.9.2.
Os blocos refletem os arquivos aplicados e os ajustes encontrados durante a
revisão. Os hashes registram a base anterior à aplicação; não são hashes dos
arquivos já alterados. Os caminhos são relativos à raiz do repositório.

Resultado e ordem do deploy: [Aplicação FireAds](fireads_aplicacao_e_deploy.md).

O histórico detalhado das decisões permanece em
[Requisitos e decisões FireAds](integracao_fireads_requisitos.md). A implementação segue os contratos concretos deste plano. Não implementar
envio pelo webhook `organicosupera`, exclusão de leads, pesquisa de origem Meta
por anúncio/post ou IA nesta entrega.

## Comportamento contemplado

- Todas as unidades passam a ter chats: um vínculo único entre cliente e unidade,
  com várias conversas ao longo do tempo. A regra de uma conversa ativa permanece.
- Unidades sem FireAds continuam começando pela pergunta do nome. Não importam
  dados nem geram entrega no dashboard; sua origem FireAds fica nula.
- Cada nova conversa de uma unidade com FireAds ativa consulta somente Google
  e Meta 7.2 antes da primeira resposta. Conversas anteriores à ativação não
  recebem importação retroativa. Nenhuma consulta é feita a cada mensagem.
- O contato é localizado pelo telefone recebido no WhatsApp. O registro mais
  recente fornece, em conjunto, nome do titular, e-mail e destinatário. Nome
  composto usa o validador existente. Faixa etária, objetivo e demais perguntas
  do formulário não preenchem coletas. Não há mais expiração de 30 dias.
- Importação completa começa na **etapa 4, profissão**, com apresentação própria.
  Somente essa abertura importada recebe saudação por horário + nome, usando
  a mesma função da etapa 1 (horário de Brasília). A etapa 4 comum e suas
  repetições não recebem essa apresentação.
  Essa primeira mensagem também é registrada na etapa 4, para que o retry não
  simule uma transição 1 → 4. Idade exata, dependente, oferta e triagem continuam
  sujeitos às regras atuais. Após aceitar a oferta nas etapas 7 ou 9, o e-mail
  daquela importação permite seguir à 11; e-mail antigo no cadastro não autoriza isso.
- Ausência, falha de uma fonte, resposta incompleta, ambiguidade ou dados inválidos
  resultam em atendimento orgânico completo. A classificação concluída é
  preservada para esta conversa, mesmo se o formulário aparecer depois.
- Ao atingir a elegibilidade atual, o Funil recebe o canal correspondente:
  **Google 113336, Meta 113340, orgânico 113481**. O texto de observações e o
  campo personalizado de origem informam a mesma classificação. Google inclui
  os registros daquela aba, inclusive landing page; não é prova de clique pago.
- Antes da primeira tentativa de Funil, o conteúdo da entrega é congelado.
  Depois do sucesso no Funil, uma fila separada cuida do dashboard. Falha do
  dashboard não provoca reenvio de uma oportunidade já confirmada no Funil.
- Toda escrita consulta a aba geral novamente. Contato existente: altera
  **somente Observação**, preservando integralmente o texto anterior e acrescentando
  abaixo o bloco do chatbot. Ausente: cadastra os campos disponíveis. Isso
  também vale para orgânico que já esteja na aba geral por outro atendimento.
- O bloco usa marcadores estáveis por integração e conversa. Retry reconhece o
  mesmo bloco; uma nova conversa acrescenta outro. Preservam-se `FR002`, `0`,
  anotações, espaços e conteúdo anterior. Não há truncamento silencioso.
- Cadastro não envia Data/Hora; a FireAds a define. Update não modifica a data.
  `url_operation` guarda apenas a referência do editor; GET e POST usam `/exec`.

## Banco e responsabilidades dos campos

| Estrutura | Conteúdo e finalidade |
| --- | --- |
| `unidade` | Identidade, CNPJ, contato administrativo, WABA, phone ID, pagamento, usuário de monitoramento e fuso Meta. Mantém seus IDs. |
| `atendimento_customizado` | Um registro obrigatório por unidade: agente, gênero, comercial, limite de suporte por idade, obrigatoriedade do e-mail, link de reserva, Instagram e BPA. A migração copia e confere os valores antes de retirar as colunas antigas. |
| `unidade_atendimento` | **View de leitura**, não outra tabela. Une unidade e personalização para manter o formato das consultas do fluxo, follow-up, painel, Funil e relatórios. |
| `integracao_fireads` | Zero ou um registro por unidade. Ativação, URLs, abas, confirmação do contrato e fuso de interpretação de datas. Começa desativada; ausência equivale a não integrada. |
| `chat` | `id_chat`, cliente, unidade e criação. Cliente/unidade únicos. A migração agrupa as conversas existentes sem apagar nenhuma. |
| `conversa.id_chat` | Obrigatório. FK composta garante que chat, cliente e unidade correspondem; os IDs diretos continuam presentes nesta fase. |
| `conversa.origem_fireads` | `google`, `meta`, `organico` ou `NULL`. Decisão daquela conversa; não derivar de outra conversa nem da aba geral. |
| `conversa.contexto_fireads` | JSON da decisão e das coletas aceitas: resultado, origem, consulta, integração, conversa, destinatário e retrato do titular. Preserva nome, idade e e-mail históricos usados no Funil. Nunca contém todas as linhas recebidas da planilha. |
| `conversa.lead_no_dash` | `NULL`: entrega não materializada/não aplicável. `FALSE`: entrega pendente. `TRUE`: escrita confirmada ou bloco exato reconciliado no destino. Não indica se o formulário foi encontrado na abertura. |
| `consulta_fireads` | Um registro atual por chat integrado: conversa de referência, integração, resultado, JSON da consulta, conclusão e horário. Atualiza na próxima conversa; o retrato histórico continua na conversa anterior. |
| `envios_dash` | Uma entrega por conversa, snapshot imutável, status, tentativas, próxima tentativa, reserva, erro, recibo e horários. Só é processada após `lead_no_funil=TRUE`. |
| `migracoes_fireads` | Controle técnico da aplicação desta migração, permitindo reexecução sem copiar novamente os dados. |

Resultados de consulta: `pendente`, `importado`, `ausente`, `incompleto`,
`ambiguidade` ou `erro`. `consulta_concluida` distingue a consulta reservada da
decisão já confirmada. O JSON `dados` guarda o resultado desta consulta; o JSON
da conversa também inclui os IDs e as coletas posteriores aceitas no fluxo.
Essa forma concreta substitui a enumeração preliminar de colunas de consulta.

Status da entrega: `pending`, `processing`, `sent`. A reserva dura três minutos;
um erro libera a tentativa para **30 minutos depois**, sem novo POST no mesmo
ciclo. O worker continua com sua cadência atual de 30 minutos; conforme o momento
da falha, a tentativa pode ocorrer em um ciclo posterior. Os lotes Funil e Dash
têm limite próprio de 100, usando o mesmo worker. O contador de tentativa impede
um processamento antigo de confirmar uma reserva mais nova. Um lock de sessão
serializa os envios deste sistema ao mesmo telefone/integração durante o HTTP.

## Contratos e decisões conservadoras

O adaptador atual aceita exatamente os campos e valores explícitos registrados
nos requisitos. Campos antigos `Adulto`, `Criança`, `Adolescente` e faixas etárias
não comprovam titular/dependente. Valores novos inesperados geram orgânico e
diagnóstico; não são convertidos por adivinhação. O telefone é normalizado com
país/DDD/formatação e comparado exatamente. Não há aproximação automática do
nono dígito nem fusão de contatos por semelhança.

Havendo mais de um candidato, as datas precisam ser comparáveis. Offset recebido
da Meta é respeitado. Data Google sem offset usa `fuso_formularios`; se não for
conhecido, não há escolha arbitrária entre registros. Uma correspondência única
com três dados válidos pode ser aproveitada sem inventar sua data. Empate é
tratado conservadoramente como ambiguidade, mesmo entre cópias equivalentes.

Na escrita, múltiplas linhas com o mesmo telefone, e-mails conflitantes ou e-mail
já associado a outro telefone mantêm a entrega pendente para revisão. Não se
cria outra linha silenciosamente para contornar uma identidade ambígua. Falta
da coluna/valor de Observação na leitura também impede a atualização.

O endpoint fornecido não tem comparação atômica do texto anterior nem chave de
idempotência no servidor. A consulta antes do POST e os marcadores reduzem
duplicação, mas não eliminam corrida com edição/ordenação externa da planilha.
O `_row` é obtido da aba geral consultada naquela tentativa, nunca das abas de
origem. Mudança externa entre leitura e gravação ainda é uma limitação deste
contrato. Para eliminar essa janela, a FireAds precisaria de operação atômica
por identidade + versão/bloco. Não apresentar este plano como garantia absoluta
de ausência de duplicações externas.

O texto do bloco vem do mesmo payload congelado enviado ao Funil. A célula
inteira pode ser maior porque preserva conteúdo anterior. Mudança manual no
bloco da mesma conversa não é sobrescrita: exige revisão. O limite operacional
de composição é 45.000 caracteres; excedê-lo mantém a pendência.

HTTP 200 sozinho não confirma sucesso. Conferir `success`, aba e recibo da
operação. Redirecionamento do POST é lido por GET no domínio Google autorizado,
sem repetir o POST. Requisições de abertura compartilham orçamento de 25 segundos
e entrega de 40 segundos; falha na abertura usa orgânico. Esses orçamentos são
checados também após a resposta. Timeouts de conexão/leitura não equivalem a
cancelamento remoto; por isso a posse da fila/conversa é conferida após a consulta
e a entrega desconhecida espera outro ciclo antes de reconsultar o destino.

## Validação da aplicação em 08/10/2026

- **487 testes executados, zero falhas, zero erros, zero pulados.**
- PostgreSQL 16 local descartável, usando as sete DSNs explícitas da suíte.
  Os 57 testes antes pulados foram executados; foram adicionados oito cenários
  FireAds de banco e dois testes de Admin/apresentação.
- Migração e reexecução preservam conversas, personalização, IDs e vínculos.
  Testes com conexões separadas conferem perda de lock e disputa de reserva.
- Validados importação de dependente, snapshot histórico, início na profissão,
  salto de e-mail autorizado, fila independente, reagendamento e reconciliação
  de bloco já escrito sem segundo POST.
- Validados também os fluxos anteriores: reserva com/sem link, idade, satisfação,
  follow-up, painel, autenticação, consumo Meta e relatórios.
- Sintaxe Python e verificações Django de models/Admin sem erros.
- HTTP de escrita simulado. Nenhuma mensagem ou lead foi enviado durante os testes.
- Leitura real da API FireAds confirmou campos de ambas as fontes e novos valores
  Google `Para mim`/`Para meu avô/avó`. Na Meta foi confirmado `pai_ou_mae`, incluído
  no mapeamento de dependente.

Durante a aplicação foram reforçados a validação do inline antes da chamada
à Meta, a separação entre decisão de tratamento e composição da mensagem, e a
recuperação do conteúdo congelado no repositório antes de reconstruí-lo no retry.
As migrações históricas continuam testadas com o catálogo correspondente à época.

Os testes locais não substituem a conferência operacional depois da migração
na VM/RDS. O código aplicado ainda não foi implantado em produção.

## Aplicação e ativação no dia do deploy

Os arquivos estão aplicados localmente; revisar o diff antes da implantação. Se o código
base tiver mudado, reconciliar as mudanças com a tabela de hashes abaixo; não
substituir arquivos novos por uma cópia antiga sem revisão. Durante o deploy,
parar os serviços que usam essas tabelas, atualizar o código, executar **inteiro**
o SQL do último passo com a mesma role proprietária do schema usada pelo projeto,
conferir o resultado e só então iniciar os serviços. Não usar `setup_database_aws`
em produção para migrar: ele contém seeds e reset de cache próprios do setup.

O SQL conserva os registros e seus IDs, move a configuração e cria as estruturas.
Não cria uma integração ativa por suposição de ID. No Admin, cadastrar a
integração **somente para Santo André**, selecionando a unidade pelo nome:

- `url_dashbord`: `https://script.google.com/macros/s/AKfycbxnwj1DsFD6qqihceO2F4b-YRBe3nXwQ70SjWb45LtUVOzrRxMo6nHqKlvNC53EDOLX/exec`.
- `url_operation`, referência opcional: `https://script.google.com/u/0/home/projects/1CVzuDR9S6N1EBc31kr7Eq-6N6URrcwmUyXyc0xmUVmYRC5lOOhtOJhij/edit`.
- Manter os defaults das abas Google, Meta 7.2 e LEADS GERAL.
- O Google atualizado foi conferido via API em 08/10: `Para mim` e
  `Para meu avô/avó` chegaram no campo `Perfil/Faixa`. Os cabeçalhos Google e Meta
  7.2 foram validados. Marcar `contrato_validado` na integração correspondente;
  não habilitar outras unidades por associação.
- Confirmar o fuso configurado na planilha. O relato de exibição **23:05** e a
  hipótese de Brasília não confirmam o fuso IANA. Se confirmado, preencher
  `America/Sao_Paulo`; enquanto desconhecido, manter nulo. Isso não altera datas externas.
- Conferir que a sincronização antiga Funil → Dash da agência continua desligada,
  mantendo apenas a captação dos formulários. Habilitar `integracao_ativa` depois
  dessas conferências; `ativada_em` é preenchido automaticamente pelo banco.

Revisar uma rota orgânica, uma importada para titular e outra para dependente,
incluindo unidade com/sem link, fechamento por idade, follow-up, retry e canais
de venda. Uma ativação não muda conversas que já começaram. Desativar a integração
interrompe novas consultas/escritas e preserva snapshots/pendências; não elimina
os dados já importados de uma conversa. Se a URL/aba mudar enquanto houver entrega
congelada, ela fica pendente, evitando enviar dados a um destino diferente.

O plano de IA reutilizará o `chat` criado aqui. As tabelas de uso da IA, modelos,
orçamentos, manual e operações de IA continuam fora desta entrega.

## Índice e conferência da base

Hash de base é SHA-256 do arquivo antes da aplicação; `novo` indica criação.
Cada bloco abaixo contém o arquivo completo aplicado. A documentação de operação
e testes também foi atualizada, sem alterações de comportamento da IA.

| Passo | Arquivo | SHA-256 da base |
| --- | --- | --- |
| 1 | `core/integrations/fireads/__init__.py` | `novo` |
| 2 | `core/integrations/fireads/cliente.py` | `novo` |
| 3 | `core/integrations/fireads/contrato.py` | `novo` |
| 4 | `core/repositories/fireads/__init__.py` | `novo` |
| 5 | `core/repositories/fireads/consulta.py` | `novo` |
| 6 | `core/repositories/fireads/envios.py` | `novo` |
| 7 | `workers/worker_flow/fireads.py` | `novo` |
| 8 | `core/repositories/atendimento/conversas.py` | `55c17b2306f1f2d02b2dc1170bc6409aac12f289d311c2b8763b2d33c2e7da8a` |
| 9 | `core/repositories/fluxo/contextos/etapa1.py` | `83e2336fdcb3ee585855de25a85970416767d0de611c9e12721da417e39ccf00` |
| 10 | `core/repositories/fluxo/contextos/etapa10.py` | `c7698e77f197f01a09a361f52ed7f3815cd4cff5c2ac032e639de52655415dca` |
| 11 | `core/repositories/fluxo/contextos/etapa18.py` | `f053b8c689f85d7217b01f9ebd946ee378b865bbaa87a52956c626f5ca67846b` |
| 12 | `core/repositories/fluxo/contextos/etapa20.py` | `b5f9ef04e48b6ebeefa08d08ab5b2db2465d3cb1021c1c734d015976aac986a8` |
| 13 | `core/repositories/fluxo/contextos/etapa6.py` | `ee9dbe1caea4bfe6713c240e0d5151a88dc93076dd7d2c272b63d67bd6626ae1` |
| 14 | `core/repositories/fluxo/contextos/etapa7.py` | `031e4a2bcb91569dc652344a2c4f45df6c3ad06ae7f4e762147dcf6a9de214b5` |
| 15 | `core/repositories/fluxo/contextos/etapa9.py` | `de6eb71ede05833ebbeabb363056576392a7c4f5e030d59fbc571ae9f0ea64e9` |
| 16 | `core/integrations/whatsapp/messages/etapa4_messages.py` | `6bae2ef71f98e4468e57e9df2285bdd6d4bb3939208c612cd4bcaabf903ff609` |
| 17 | `core/integrations/whatsapp/pywa_functions/pywa_senders/etapa4.py` | `492e0cb798aad311cf2dd08e633683b57a1c4e42e4ce81b8b594ef7a9aa04945` |
| 18 | `workers/worker_flow/response_flow/etapas/resolver_etapa7.py` | `54b7f664060eb255aaf424885f58a45bb1ef1325d7e651c2bb705e527ca4dc32` |
| 19 | `workers/worker_flow/response_flow/etapas/resolver_etapa9.py` | `8f13a2fa58341b015c54dd2587ee810f1cd7cba4061b45a910608f72d872b1a1` |
| 20 | `workers/worker_flow/response_flow/flow_sender.py` | `f9e5d0a9658a4f0d101c8f7862764cb38fc8bbcb068f73291f8cc2bc52920a70` |
| 21 | `workers/worker_flow/response_flow/flow_worker.py` | `95dc04cf2db276908dcfd18360ece508fda117bc1411f393d0b74f2eead8f55c` |
| 22 | `workers/worker_flow/transacoes/efeitos_transicao.py` | `543967d40b6c28f0d339f77fabc9a22fd9889d52e64ca1491df21ad29ee4d0cc` |
| 23 | `workers/worker_flow/transacoes/movimento_conversa.py` | `79a7911127900cfd3f915656255b84d127e9f26acd90a7d22960b974ab89f8fc` |
| 24 | `workers/worker_flow/transacoes/persistencia_resposta.py` | `a7b3c45e63552c3818db59e15f52a91ce463746313af5208e43beabeda076211` |
| 25 | `workers/worker_flow/valida_historico.py` | `1d728fbc04658fe22431f086c72796af8b43769b9cd2d116c340a14554d68644` |
| 26 | `core/repositories/funil/envios.py` | `b1acb4ddb40d5ea7576bc644dac3b6dbc4229f3791809caf04df63c80fdc577a` |
| 27 | `core/repositories/funil/leads.py` | `88a9d01acbaa1aa54c8efa120b7f72fd35b2c35c6bb4ac13939b5831772ca0aa` |
| 28 | `core/integrations/funil/oportunidades.py` | `d120b7cd421c82aa23f3f721f0c832e448662100395360bc5f07401279547724` |
| 29 | `workers/worker_funil/fireads.py` | `novo` |
| 30 | `workers/worker_funil/funil_worker.py` | `192a41a3ab0e00e8630db4afda5be9470f5a3de7ba5e069d335271b14899c486` |
| 31 | `workers/worker_funil/processamento.py` | `593ed6cc2bf3416606c4d50030b0773a454973383c9201aa69f7b64163bf31ed` |
| 32 | `core/repositories/atendimento/followup.py` | `33553952ab49a854f219a374060cae4ad59963090ce1192ebe00d0d21b76a0d6` |
| 33 | `core/repositories/monitoramento/painel.py` | `8fa8bc07a36b887a7918e5598d58dad177ab86da2d7168d21e376a024797e157` |
| 34 | `utilitarios/reports_functions/total.py` | `780377a8813fcc559abba6e5c71976e54cee6c4ea56145211e5038b2084f24cd` |
| 35 | `utilitarios/reports_functions/weekly.py` | `29a36d4d573a1addc688cf80deb0f28626eead6b404cc7478008f14d40e5969d` |
| 36 | `callback/webhook/models.py` | `e19238f9718578f98adc31f27347841dd12f0cc6e218de723c85b498440f3823` |
| 37 | `callback/webhook/admin.py` | `2d966fd97ad029c43d8d85fcbce55c8873da9678f8c8951e9c022eee782c02a0` |
| 38 | `core/database/deploy_database/etapa_transicao_script.py` | `94f832d8a783fc51c5e5226261e742fcae82bf9888c348e4009132c6de7b0537` |
| 39 | `core/database/deploy_database/fireads_script.py` | `novo` |
| 40 | `core/database/deploy_database/setup_database.py` | `0117837d161d0a3aedf55a676f4deb88a633710309f68f4eb80933f1bd8f2bde` |
| 41 | `tests/unit/test_fireads.py` | `novo` |
| 42 | `tests/unit/test_fluxo_reserva_link.py` | `a57c0e2fcb6759494a55f20bc232f8cc5c3af456dc2ae124c72aba1497d27c89` |
| 43 | `tests/unit/test_monitoramento_unidade.py` | `3c5be6dd379a93bfd398609e0739e71d0b069d3908e74afbfeb2944491b1057c` |
| 44 | `tests/unit/test_suporte_por_idade.py` | `3eafd78ec116cea8804a4737cee08ee2e76d899eb85fd0c1a2c2bde087aa19d0` |
| 45 | `tests/unit/test_worker_flow_runtime.py` | `98f12dc0f1226c0f558eccaa0f6f7f541eb97147d1b1d72f2d97cac34392060f` |
| 46 | `tests/fixtures/fireads.py` | `novo` |
| 47 | `tests/fixtures/reserva_migracao.py` | `edc4ef349af2e8ef1aa7b29c54cd56effb1b9b6dbe7f65d1db07f8870bd41c3f` |
| 48 | `tests/integration/test_followup_postgres.py` | `15df37916884ff6df07806bc9fb1270c8ccb643da7e4ce7dd4f645fe5454d7a5` |
| 49 | `tests/integration/test_reserva_link_postgres.py` | `9a67b5805be448f8035818e9099a0a71bc5c6c4e3239b26dc1a4c06d66334c9a` |
| 50 | `tests/integration/test_migracao_reserva_link_postgres.py` | `0c2a74b6221e498e0000e194bb5975d9b1af6d374bebee6a2ce55c1630df1faf` |
| 51 | `tests/integration/test_suporte_por_idade_postgres.py` | `e8319736e66e889cc4dfcfc41737b793ca64b7c1ca2f828c9769bb29047acc67` |
| 52 | `tests/integration/test_fireads_postgres.py` | `novo` |
| 53 | `deploy/migrations/20261007_fireads_chat_customizacao.sql` | `novo` |

## Passo 1 — Criar `core/integrations/fireads/__init__.py`

```python
"""Integração determinística com os formulários e o dashboard FireAds."""
```

## Passo 2 — Criar `core/integrations/fireads/cliente.py`

```python
"""GET e POST limitados ao Web App; nenhuma escrita durante importação."""

import time
from urllib.parse import urlparse
import requests
from .contrato import ErroFireAds


def validar_url(url, *, resposta=False):
    p = urlparse(str(url))
    host = "script.googleusercontent.com" if resposta else "script.google.com"
    if (
        p.scheme != "https"
        or p.hostname != host
        or p.username
        or p.password
        or p.port not in (None, 443)
        or (
            not resposta
            and (not p.path.startswith("/macros/s/") or not p.path.endswith("/exec"))
        )
    ):
        raise ErroFireAds("URL FireAds inválida: usar Web App /exec HTTPS")
    return url


class ClienteFireAds:
    def __init__(self, url, *, segundos=25, session=None):
        self.url = validar_url(url)
        self.deadline = time.monotonic() + segundos
        self.session = session or requests.Session()
        self.session.headers.update({"Accept": "application/json"})

    def close(self):
        self.session.close()

    def _request(self, method, url, **kwargs):
        restante = self.deadline - time.monotonic()
        if restante <= 0:
            raise ErroFireAds("Orçamento de consulta FireAds esgotado")
        # Cada chamada/redirect compartilha o orçamento; retries não são automáticos.
        response = self.session.request(
            method,
            url,
            timeout=(min(4, restante), min(8, restante)),
            allow_redirects=False,
            **kwargs
        )
        if response.status_code in (301, 302, 303):
            alvo = response.headers.get("Location", "")
            validar_url(alvo, resposta=True)
            response = self._request("GET", alvo)
        response.raise_for_status()
        if time.monotonic() > self.deadline:
            raise ErroFireAds("Resposta FireAds após o prazo")
        return response

    def _json(self, response):
        try:
            body = response.json()
        except ValueError as exc:
            raise ErroFireAds("Resposta FireAds não é JSON") from exc
        if not isinstance(body, dict) or body.get("success") is not True:
            raise ErroFireAds("FireAds recusou a operação")
        return body

    def consultar(self, aba):
        body = self._json(
            self._request("GET", self.url, params={"sheet": aba, "abas": "0"})
        )
        data = body.get("data")
        if (
            not isinstance(data, dict)
            or data.get("aba") != aba
            or not isinstance(data.get("headers"), list)
            or not isinstance(data.get("rows"), list)
            or any(not isinstance(r, dict) for r in data["rows"])
        ):
            raise ErroFireAds("Consulta incompleta ou aba divergente")
        return data

    def enviar(self, aba, *, dados=None, row=None, observacoes=None):
        if row is None:
            payload = {"action": "append", "sheet": aba, "rows": [dados]}
        else:
            payload = {
                "sheet": aba,
                "row": int(row),
                "updates": {"Observação": observacoes},
            }
        result = self._json(self._request("POST", self.url, json=payload))
        if result.get("aba") != aba:
            raise ErroFireAds("Recibo de outra aba")
        if row is None:
            if result.get("inserted") != 1:
                raise ErroFireAds("Cadastro sem confirmação de uma linha")
        elif result.get("row") != row or "Observação" not in result.get("updated", []):
            raise ErroFireAds("Update sem confirmação da linha/coluna")
        return result
```

## Passo 3 — Criar `core/integrations/fireads/contrato.py`

```python
"""Regras puras de origem, telefone e composição sem perda de observações."""

import re
import unicodedata
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

ABA_GOOGLE = "Leads Google Ads (NÃO EDITAR)"
ABA_META = "[FIRE] Leads Ads Geral - 7.2"
ABA_DESTINO = "LEADS GERAL - Feedback"
CANAIS = {
    "google": ("Google Ads", "113336"),
    "meta": ("Meta Ads", "113340"),
    "organico": ("Orgânico", "113481"),
}


class ErroFireAds(ValueError):
    """Contrato incompleto, identidade ambígua ou conflito externo."""


def normalizar(texto):
    base = unicodedata.normalize("NFKD", str(texto or "").lower())
    return " ".join(
        re.sub(
            r"[^a-z0-9]+", " ", "".join(c for c in base if not unicodedata.combining(c))
        ).split()
    )


def telefone(valor):
    numero = re.sub(r"\D", "", str(valor or ""))
    if len(numero) in (10, 11):
        numero = "55" + numero
    if not re.fullmatch(r"55[1-9]\d\d{8,9}", numero):
        return None
    return numero


def localizar(rows, numero, coluna):
    """Somente correspondência exata normalizada; não aproximar pessoas."""
    esperado = telefone(numero)
    if not esperado:
        raise ErroFireAds("Telefone fora do contrato brasileiro")
    return [r for r in rows if telefone(r.get(coluna)) == esperado]


def destino(valor):
    chave = normalizar(valor)
    if chave == "para mim":
        return False
    dependentes = {
        # Valores do formulário e identificadores serializados pela Meta.
        "pai ou mae",
        "filho ou filha",
        "para meu pai mae",
        "para meu pai ou minha mae",
        "para meu avo avo",
        "para meu avo ou minha avo",
        "para outra pessoa",
        "para meu filho ou filha",
        "para meu filho minha filha",
        "para meu filho filha",
        "para mim e outra pessoa",
        "mim e outra",
    }
    return True if chave in dependentes else None


def instante(valor, fuso=None):
    texto = str(valor or "").strip()
    try:
        data = datetime.fromisoformat(texto.replace("Z", "+00:00"))
    except ValueError:
        try:
            data = datetime.strptime(texto, "%d/%m/%Y %H:%M")
        except ValueError:
            return None
    if data.tzinfo is None:
        if not fuso:
            return None
        data = data.replace(tzinfo=ZoneInfo(fuso))
    return data.astimezone(timezone.utc)


def selecionar(google, meta, numero, fuso=None):
    """Escolhe um registro inteiro; sem combinar dados de diferentes formulários."""
    candidatos = [
        ("google", r, instante(r.get("Data/Hora"), fuso))
        for r in localizar(google, numero, "WhatsApp")
    ]
    candidatos += [
        ("meta", r, instante(r.get("created_time"), fuso))
        for r in localizar(meta, numero, "phone_number")
    ]
    if not candidatos:
        return None
    if len(candidatos) == 1:
        return candidatos[0]
    if any(c[2] is None for c in candidatos):
        raise ErroFireAds("Datas insuficientes para comparar formulários")
    candidatos.sort(key=lambda c: c[2], reverse=True)
    if candidatos[0][2] == candidatos[1][2]:
        raise ErroFireAds("Formulários empatados; origem não inequívoca")
    return candidatos[0]


def bloco_observacoes(id_integracao, id_conversa, observacoes):
    chave = f"CHATBOT:{int(id_integracao)}:{int(id_conversa)}"
    return (
        f"[INICIO {chave}]\nObservações do atendimento — conversa {id_conversa}\n"
        f"{observacoes}\n[FIM {chave}]"
    )


def acrescentar_observacoes(anterior, bloco):
    """Preserva inclusive zero e espaços; conflito nunca vira sobrescrita."""
    if anterior is None:
        anterior = ""
    if not isinstance(anterior, (str, int, float)) or isinstance(anterior, bool):
        raise ErroFireAds("Observação tem tipo inesperado")
    texto = str(anterior)
    marcador = bloco.split("\n", 1)[0]
    if marcador in texto:
        if texto.count(marcador) != 1 or bloco not in texto:
            raise ErroFireAds("Bloco da conversa existe com conteúdo divergente")
        return texto, False
    novo = texto + ("\n\n" if texto else "") + bloco
    if len(novo) > 45000:
        raise ErroFireAds("Observação excede limite operacional; não truncar")
    return novo, True
```

## Passo 4 — Criar `core/repositories/fireads/__init__.py`

```python
"""Estado de abertura por chat e entregas independentes ao dashboard."""
```

## Passo 5 — Criar `core/repositories/fireads/consulta.py`

```python
"""SQL FireAds; o orquestrador controla commits e as chamadas externas."""

from psycopg.types.json import Jsonb


def buscar_abertura(id_conversa, cursor):
    cursor.execute(
        """
        SELECT c.id_chat,c.id_cliente,c.id_unidade,c.id_etapa_atual,
               c.contexto_fireads,c.origem_fireads,i.id_integracao_fireads,
               i.url_dashbord,i.aba_google,i.aba_meta,i.fuso_formularios,
               (i.integracao_ativa AND c.iniciou_em >= i.ativada_em) AS aplicavel
        FROM chatbot.conversa c LEFT JOIN chatbot.integracao_fireads i
          ON i.id_unidade=c.id_unidade WHERE c.id_conversa=%s;
    """,
        (id_conversa,),
    )
    row = cursor.fetchone()
    if row is None:
        raise ValueError("Conversa inexistente")
    return dict(
        zip(
            (
                "id_chat",
                "id_cliente",
                "id_unidade",
                "etapa",
                "contexto",
                "origem",
                "id_integracao",
                "url",
                "aba_google",
                "aba_meta",
                "fuso",
                "aplicavel",
            ),
            row,
        )
    )


def reservar_consulta(abertura, id_conversa, cursor):
    cursor.execute(
        """
        INSERT INTO chatbot.consulta_fireads
          (id_chat,id_unidade,id_integracao_fireads,id_conversa_referencia)
        VALUES (%s,%s,%s,%s)
        ON CONFLICT (id_chat) DO UPDATE SET
          id_integracao_fireads=EXCLUDED.id_integracao_fireads,
          id_conversa_referencia=EXCLUDED.id_conversa_referencia,
          consulta_concluida=FALSE,resultado='pendente',dados=NULL,
          consultado_em=NULL,atualizado_em=clock_timestamp()
        RETURNING id_consulta;
    """,
        (
            abertura["id_chat"],
            abertura["id_unidade"],
            abertura["id_integracao"],
            id_conversa,
        ),
    )
    return cursor.fetchone()[0]


def concluir_consulta(abertura, id_conversa, id_consulta, decisao, cursor):
    cursor.execute(
        """
        UPDATE chatbot.consulta_fireads SET consulta_concluida=TRUE,
          resultado=%s,dados=%s,consultado_em=clock_timestamp(),
          atualizado_em=clock_timestamp()
        WHERE id_consulta=%s AND id_chat=%s AND id_conversa_referencia=%s;
    """,
        (
            decisao["resultado"],
            Jsonb(decisao),
            id_consulta,
            abertura["id_chat"],
            id_conversa,
        ),
    )
    if cursor.rowcount != 1:
        raise ValueError("Consulta pertence a outra conversa")
    decisao = dict(
        decisao,
        id_consulta=id_consulta,
        id_integracao=abertura["id_integracao"],
        concluida=True,
        id_conversa=id_conversa,
    )
    cursor.execute(
        """UPDATE chatbot.conversa SET origem_fireads=%s,contexto_fireads=%s
                      WHERE id_conversa=%s AND id_etapa_atual IS NULL;""",
        (decisao["origem"], Jsonb(decisao), id_conversa),
    )
    if cursor.rowcount != 1:
        raise ValueError("Conversa já iniciou antes da decisão FireAds")
    return decisao


def guardar_coletas(contexto, efeitos, cursor):
    """Captura dados aceitos nesta transação, nunca cadastro de conversa antiga."""
    if not contexto.get("contexto_fireads") or not efeitos:
        return
    campos = []
    if efeitos.get("cliente_nome_atualizado"):
        campos.append("nome")
    if efeitos.get("destino_dado") == "cliente":
        campos.append("idade")
    if efeitos.get("cliente_email_atualizado"):
        campos.append("email")
    if not campos:
        return
    cursor.execute(
        "SELECT nome,idade,email FROM chatbot.cliente WHERE id_cliente=%s",
        (contexto["id_cliente"],),
    )
    valores = dict(zip(("nome", "idade", "email"), cursor.fetchone()))
    dados = {c: valores[c] for c in campos}
    if "email" in campos:
        dados["resultado_email"] = efeitos["resultado_coleta_email"]
    cursor.execute(
        """UPDATE chatbot.conversa SET contexto_fireads=jsonb_set(
        contexto_fireads,'{dados_titular}',
        COALESCE(contexto_fireads->'dados_titular','{}'::jsonb) || %s)
        WHERE id_conversa=%s AND contexto_fireads IS NOT NULL;""",
        (Jsonb(dados), contexto["id_conversa"]),
    )
```

## Passo 6 — Criar `core/repositories/fireads/envios.py`

```python
"""Fila independente do dashboard e retrato do conteúdo aceito para o Funil."""

from psycopg.types.json import Jsonb
from core.integrations.fireads.contrato import CANAIS


def congelar(dados, payload, integracao_funil, cursor):
    origem = dados.get("origem_fireads")
    if origem is None:
        return (
            payload,
            integracao_funil["codigo_canal_venda"],
            integracao_funil["link_api_carrossel"],
        )
    # No retry, a entrega já registrada é a fonte de verdade. Não reconstruir
    # conteúdo/configuração a partir de cadastros que possam ter mudado depois.
    cursor.execute(
        "SELECT snapshot FROM chatbot.envios_dash WHERE id_conversa=%s",
        (dados["id_conversa"],),
    )
    existente = cursor.fetchone()
    if existente is not None:
        salvo = existente[0]
        return salvo["payload_funil"], salvo["canal"], salvo["url_funil"]
    canal = CANAIS[origem][1]
    estado = dados["contexto_fireads"]
    cursor.execute(
        """SELECT id_integracao_fireads, url_dashbord, aba_destino
        FROM chatbot.integracao_fireads WHERE id_integracao_fireads=%s AND id_unidade=%s""",
        (estado["id_integracao"], dados["id_unidade"]),
    )
    config = cursor.fetchone()
    if config is None:
        raise ValueError("Integração histórica FireAds não encontrada")
    oportunidade = payload["oportunidades"][0]
    obs = next(
        c["valor"]
        for c in oportunidade["personalizados"]
        if c["titulo"] == "Observações"
    )
    snapshot = {
        "payload_funil": payload,
        "canal": canal,
        "url_funil": integracao_funil["link_api_carrossel"],
        "url": config[1],
        "aba": config[2],
        "observacoes": obs,
        "telefone": dados["telefone_cliente"],
        "email": oportunidade["contato"]["email"],
        "nome": dados["nome_cliente"],
        "origem": origem,
        "perfil": (
            f"Dependente: {dados['nome_dependente']} ({dados['idade_dependente']} anos)"
            if dados["status_dependente"]
            else f"Titular ({dados['idade_cliente']} anos)"
        ),
    }
    cursor.execute(
        """INSERT INTO chatbot.envios_dash
        (id_conversa,id_unidade,id_integracao_fireads,snapshot) VALUES (%s,%s,%s,%s)
        ON CONFLICT (id_conversa) DO NOTHING""",
        (dados["id_conversa"], dados["id_unidade"], config[0], Jsonb(snapshot)),
    )
    cursor.execute(
        """UPDATE chatbot.conversa SET lead_no_dash=FALSE
        WHERE id_conversa=%s AND lead_no_dash IS NULL""",
        (dados["id_conversa"],),
    )
    cursor.execute(
        "SELECT snapshot FROM chatbot.envios_dash WHERE id_conversa=%s",
        (dados["id_conversa"],),
    )
    salvo = cursor.fetchone()[0]
    return salvo["payload_funil"], salvo["canal"], salvo["url_funil"]


def reservar(cursor):
    cursor.execute(
        """WITH proximo AS (
        SELECT d.id_envio_dash FROM chatbot.envios_dash d
        JOIN chatbot.conversa c ON c.id_conversa=d.id_conversa
        JOIN chatbot.integracao_fireads i USING (id_integracao_fireads)
        JOIN chatbot.integracao_funil_unidade f ON f.id_unidade=d.id_unidade
        WHERE c.lead_no_funil IS TRUE AND i.integracao_ativa AND f.integracao_ativa AND f.widget_ativo
          AND ((d.status='pending' AND d.next_attempt_at <= clock_timestamp())
            OR (d.status='processing' AND d.processing_started_at < clock_timestamp()-INTERVAL '3 minutes'))
        ORDER BY d.attempt_count,d.id_envio_dash FOR UPDATE OF d SKIP LOCKED LIMIT 1
    ) UPDATE chatbot.envios_dash d SET status='processing',attempt_count=attempt_count+1,
        processing_started_at=clock_timestamp(),atualizado_em=clock_timestamp()
      FROM proximo p WHERE d.id_envio_dash=p.id_envio_dash
      RETURNING d.id_envio_dash,d.id_conversa,d.id_integracao_fireads,d.attempt_count,d.snapshot"""
    )
    row = cursor.fetchone()
    return (
        dict(zip(("id", "conversa", "integracao", "tentativa", "snapshot"), row))
        if row
        else None
    )


def conferir_posse(envio, cursor):
    cursor.execute(
        """SELECT 1 FROM chatbot.envios_dash d
        JOIN chatbot.integracao_fireads i USING (id_integracao_fireads)
        JOIN chatbot.integracao_funil_unidade f ON f.id_unidade=d.id_unidade
        WHERE d.id_envio_dash=%s AND d.status='processing' AND d.attempt_count=%s
          AND d.processing_started_at > clock_timestamp()-INTERVAL '3 minutes'
          AND i.integracao_ativa AND f.integracao_ativa AND f.widget_ativo
          AND i.url_dashbord=d.snapshot->>'url' AND i.aba_destino=d.snapshot->>'aba'
        FOR UPDATE OF d""",
        (envio["id"], envio["tentativa"]),
    )
    if cursor.fetchone() is None:
        raise ValueError("Reserva/configuração FireAds mudou; não escrever")


def concluir(envio, recibo, cursor):
    cursor.execute(
        """UPDATE chatbot.envios_dash SET status='sent',enviado_em=clock_timestamp(),
        processing_started_at=NULL,ultimo_erro=NULL,recibo=%s,atualizado_em=clock_timestamp()
        WHERE id_envio_dash=%s AND status='processing' AND attempt_count=%s RETURNING id_conversa""",
        (Jsonb(recibo), envio["id"], envio["tentativa"]),
    )
    row = cursor.fetchone()
    if row is None:
        raise ValueError("Reserva FireAds perdida após envio")
    cursor.execute(
        "UPDATE chatbot.conversa SET lead_no_dash=TRUE WHERE id_conversa=%s", (row[0],)
    )


def reagendar(envio, erro, cursor):
    cursor.execute(
        """UPDATE chatbot.envios_dash SET status='pending',
        next_attempt_at=clock_timestamp()+INTERVAL '30 minutes',processing_started_at=NULL,
        ultimo_erro=%s,atualizado_em=clock_timestamp()
        WHERE id_envio_dash=%s AND status='processing' AND attempt_count=%s""",
        (type(erro).__name__ + ": " + str(erro)[:300], envio["id"], envio["tentativa"]),
    )
```

## Passo 7 — Criar `workers/worker_flow/fireads.py`

```python
"""Consulta inicial: executada sob posse da conversa, fora de transação HTTP."""

import logging
import psycopg
from core.integrations.fireads.cliente import ClienteFireAds
from core.integrations.fireads.contrato import selecionar, destino, ErroFireAds
from core.validacoes.email import validar_email_estrutural
from core.repositories.fireads.consulta import (
    buscar_abertura,
    reservar_consulta,
    concluir_consulta,
)
from core.repositories.atendimento.followup import (
    proteger_conversa,
    LockConversaPerdido,
)
from core.repositories.atendimento.dependentes import inserir_dependente_para_conversa
from workers.worker_flow.response_flow.etapas.validadores_universais.validador_nome import (
    validar_nome_cliente,
)

logger = logging.getLogger("worker.fireads")


def classificar_tratamento_abertura(contexto):
    """A decisão fica no fluxo; messages apenas compõe o texto autorizado."""
    from workers.worker_flow.response_flow.etapas.validadores_universais.validador_midia import (
        validar_midia,
    )
    from workers.worker_flow.response_flow.etapas.validadores_universais.validador_financeiro import (
        validar_pergunta_financeira,
    )
    from workers.worker_flow.response_flow.etapas.validadores_universais.validador_reforco_escolar import (
        validar_duvida_reforco_escolar,
    )

    texto = contexto.get("texto_cliente_atual") or ""
    if validar_midia(contexto.get("tipo_mensagem_atual")):
        return "tipo_mensagem_nao_suportado"
    if validar_duvida_reforco_escolar(texto):
        return "duvida_reforco_escolar"
    if validar_pergunta_financeira(texto):
        return "pergunta_financeira"
    return None


def decisao_organica(resultado, motivo=None):
    return {
        "resultado": resultado,
        "origem": "organico",
        "motivo": motivo,
        "dados_titular": {},
    }


def interpretar(google, meta, numero, fuso):
    try:
        escolhido = selecionar(google, meta, numero, fuso)
    except ErroFireAds:
        return decisao_organica("ambiguidade", "data_ou_origem_ambigua")
    if escolhido is None:
        return decisao_organica("ausente")
    origem, row, data = escolhido
    nome = row.get("Nome") if origem == "google" else row.get("full_name")
    email = row.get("Email") if origem == "google" else row.get("email")
    alvo = row.get("Perfil/Faixa") if origem == "google" else row.get("para_quem")
    nome = validar_nome_cliente(nome)
    email = validar_email_estrutural(email)
    dependente = destino(alvo)
    if not nome.valido or not email.valido or dependente is None:
        return decisao_organica("incompleto", "coleta_invalida")
    return {
        "resultado": "importado",
        "origem": origem,
        "status_dependente": dependente,
        "id_registro_origem": str(row.get("id") or ""),
        "data_formulario": data.isoformat() if data else None,
        "dados_titular": {
            "nome": nome.primeiro_nome,
            "email": email.email,
            "resultado_email": "email_valido",
        },
    }


def preparar_abertura(contexto_banco, mensagem, lock_version, conn, cursor):
    cid = contexto_banco["conversa"]["id_conversa"]
    abertura = buscar_abertura(cid, cursor)
    if abertura["contexto"]:
        return aplicar_contexto(contexto_banco, abertura["contexto"])
    if abertura["etapa"] is not None or not abertura["aplicavel"]:
        return contexto_banco
    proteger_conversa(cid, lock_version, cursor)
    consulta = reservar_consulta(abertura, cid, cursor)
    conn.commit()
    cliente = None
    try:
        cliente = ClienteFireAds(abertura["url"], segundos=25)
        google = cliente.consultar(abertura["aba_google"])
        meta = cliente.consultar(abertura["aba_meta"])
        if not {"Nome", "Email", "WhatsApp", "Perfil/Faixa"} <= set(google["headers"]):
            raise ErroFireAds("Contrato Google incompleto")
        if not {"full_name", "email", "phone_number", "para_quem"} <= set(
            meta["headers"]
        ):
            raise ErroFireAds("Contrato Meta incompleto")
        decisao = interpretar(
            google["rows"], meta["rows"], mensagem["cliente_telefone"], abertura["fuso"]
        )
    except Exception as exc:
        # Falha externa usa a regra orgânica aprovada. Nada de payload/PII em log.
        logger.warning(
            "fireads_consulta_falhou | conversa=%s tipo=%s", cid, type(exc).__name__
        )
        decisao = decisao_organica("erro", type(exc).__name__)
    finally:
        if cliente:
            cliente.close()
    proteger_conversa(cid, lock_version, cursor)
    cursor.execute(
        """SELECT id_mensagem FROM chatbot.fila_mensagens
        WHERE id_mensagem=%s AND status='processing' AND retry_count=%s
          AND processing_started_at>clock_timestamp()-INTERVAL '120 seconds' FOR UPDATE""",
        (mensagem["id_mensagem"], mensagem["retry_count"]),
    )
    if cursor.fetchone() is None:
        raise LockConversaPerdido("Mensagem perdeu a reserva durante consulta FireAds")
    if decisao["resultado"] == "importado":
        cursor.execute("SAVEPOINT fireads_importacao")
        try:
            dados = decisao["dados_titular"]
            cursor.execute(
                "UPDATE chatbot.cliente SET nome=%s,email=%s WHERE id_cliente=%s",
                (dados["nome"], dados["email"], abertura["id_cliente"]),
            )
            cursor.execute(
                "UPDATE chatbot.conversa SET status_dependente=%s WHERE id_conversa=%s",
                (decisao["status_dependente"], cid),
            )
            if decisao["status_dependente"]:
                inserir_dependente_para_conversa(cid, cursor)
        except psycopg.errors.UniqueViolation:
            cursor.execute("ROLLBACK TO SAVEPOINT fireads_importacao")
            decisao = decisao_organica("incompleto", "conflito_email")
        finally:
            cursor.execute("RELEASE SAVEPOINT fireads_importacao")
    decisao = concluir_consulta(abertura, cid, consulta, decisao, cursor)
    conn.commit()
    return aplicar_contexto(contexto_banco, decisao)


def aplicar_contexto(contexto_banco, decisao):
    novo = dict(contexto_banco, contexto_fireads=decisao)
    if (
        decisao.get("resultado") == "importado"
        and novo["conversa"].get("id_etapa_atual") is None
    ):
        novo["conversa"] = dict(
            novo["conversa"], status_dependente=decisao["status_dependente"]
        )
    return novo


def email_importado(contexto):
    estado = contexto.get("contexto_fireads") or {}
    return (
        estado.get("concluida") is True
        and estado.get("resultado") == "importado"
        and estado.get("id_conversa") == contexto.get("id_conversa")
        and estado.get("dados_titular", {}).get("resultado_email") == "email_valido"
        and validar_email_estrutural(
            estado.get("dados_titular", {}).get("email")
        ).valido
    )
```

## Passo 8 — Substituir integralmente `core/repositories/atendimento/conversas.py`

```python
import logging

from core.validacoes.encerramento_por_idade import MOTIVOS_IDADE


logger = logging.getLogger("db.atendimento.conversas")

ETAPA_INICIAL = 1

# Catálogo compartilhado: preserva os motivos de follow-up e agendamento.
MOTIVOS_ENCERRAMENTO_VALIDOS = MOTIVOS_IDADE | {'foi_agendado', 'followup_sem_resposta'}


def inserindo_em_conversa_caso_seja_nova(id_cliente, id_unidade, cursor):
    cursor.execute("""
        INSERT INTO chatbot.chat (id_cliente, id_unidade) VALUES (%s, %s)
        ON CONFLICT (id_cliente, id_unidade) DO UPDATE SET id_cliente=EXCLUDED.id_cliente
        RETURNING id_chat;
    """, (id_cliente, id_unidade))
    id_chat = cursor.fetchone()[0]
    cursor.execute("""
        INSERT INTO chatbot.conversa (
            id_chat,
            id_cliente,
            id_unidade,
            last_interaction_at,
            last_message_from
        )
        VALUES (%s, %s, %s, NOW(), 'cliente')
        RETURNING id_conversa;
    """, (id_chat, id_cliente, id_unidade))

    resultado = cursor.fetchone()

    if resultado:
        logger.debug(
            "conversa_insert_resultado | acao=criar_conversa id_cliente=%s id_unidade=%s id_conversa=%s",
            id_cliente,
            id_unidade,
            resultado[0],
        )
        return resultado[0]

    raise ValueError(
        f"Anomalia Crítica: conversa do cliente {id_cliente} "
        f"e unidade {id_unidade} não foi criada!"
    )


def tentar_lock_conversa(id_conversa, cursor):
    cursor.execute(
        "SELECT lock_ok, lock_version_atual "
        "FROM chatbot.lock_conversa(%s);",
        (id_conversa,),
    )
    resultado = cursor.fetchone()

    if not resultado:
        logger.warning(
            "conversa_lock_sem_retorno | acao=negar_lock id_conversa=%s",
            id_conversa,
        )
        return False, None

    logger.debug(
        "conversa_lock_resultado | acao=lock id_conversa=%s lock_ok=%s lock_version=%s",
        id_conversa,
        bool(resultado[0]),
        resultado[1],
    )
    return bool(resultado[0]), resultado[1]


def unlock_conversa(id_conversa, lock_version, cursor):
    if lock_version is None:
        return False

    cursor.execute(
        "SELECT chatbot.unlock_conversa(%s, %s);",
        (id_conversa, lock_version),
    )
    resultado = cursor.fetchone()
    logger.debug(
        "conversa_unlock_resultado | acao=unlock id_conversa=%s lock_version=%s liberada=%s",
        id_conversa,
        lock_version,
        bool(resultado[0]) if resultado else False,
    )
    return bool(resultado[0]) if resultado else False


def buscar_estado_conversa(id_cliente, id_unidade, cursor):
    cursor.execute("""
        WITH conversa_ativa AS (
            SELECT
                id_conversa,
                id_etapa_atual,
                status_ativa,
                finalizou_em,
                'ativa' AS estado,
                status_dependente,
                last_message_from,
                followup_stage,
                followup_last_sent_at,
                lead_no_funil
            FROM chatbot.conversa
            WHERE id_cliente = %s
              AND id_unidade = %s
              AND status_ativa = TRUE
            LIMIT 1
        ),
        ultima_conversa AS (
            SELECT
                c.id_conversa,
                c.id_etapa_atual,
                c.status_ativa,
                c.finalizou_em,
                CASE
                    WHEN COALESCE(e.bloqueio_dias, 0) > 0
                     AND c.finalizou_em
                         > NOW() - (
                             COALESCE(e.bloqueio_dias, 0)
                             * INTERVAL '1 day'
                         )
                    THEN 'bloqueada'
                    ELSE 'liberada'
                END AS estado,
                c.status_dependente,
                c.last_message_from,
                c.followup_stage,
                c.followup_last_sent_at,
                c.lead_no_funil
            FROM chatbot.conversa c
            LEFT JOIN chatbot.etapa e
              ON e.id_etapa = c.id_etapa_atual
            WHERE c.id_cliente = %s
              AND c.id_unidade = %s
              AND c.status_ativa = FALSE
            ORDER BY c.finalizou_em DESC
            LIMIT 1
        )
        SELECT
            id_conversa,
            id_etapa_atual,
            status_ativa,
            finalizou_em,
            estado,
            status_dependente,
            last_message_from,
            followup_stage,
            followup_last_sent_at,
            lead_no_funil
        FROM conversa_ativa

        UNION ALL

        SELECT
            id_conversa,
            id_etapa_atual,
            status_ativa,
            finalizou_em,
            estado,
            status_dependente,
            last_message_from,
            followup_stage,
            followup_last_sent_at,
            lead_no_funil
        FROM ultima_conversa
        WHERE NOT EXISTS (SELECT 1 FROM conversa_ativa)

        LIMIT 1;
    """, (id_cliente, id_unidade, id_cliente, id_unidade))

    resultado = cursor.fetchone()
    logger.debug(
        "conversa_estado_consultado | acao=buscar_estado id_cliente=%s id_unidade=%s encontrada=%s estado=%s",
        id_cliente,
        id_unidade,
        bool(resultado),
        resultado[4] if resultado else None,
    )
    return resultado


def atualizar_conversa_mensagem_cliente(
    id_conversa,
    data_interacao,
    cursor,
):
    if data_interacao is None:
        raise ValueError(
            "data_interacao nao informada para registrar mensagem do cliente"
        )

    cursor.execute("""
        UPDATE chatbot.conversa
        SET
            last_message_from = 'cliente',
            last_interaction_at = %s
        WHERE id_conversa = %s;
    """, (data_interacao, id_conversa))

    logger.debug(
        "conversa_update | acao=registrar_mensagem_cliente id_conversa=%s data_interacao=%s linhas=%s",
        id_conversa,
        data_interacao,
        cursor.rowcount,
    )

    if cursor.rowcount != 1:
        raise ValueError(
            "Conversa nao foi atualizada com mensagem do cliente "
            f"(id_conversa={id_conversa}, linhas={cursor.rowcount})"
        )

    return cursor.rowcount


def inicializar_conversa_resposta_bot(
    id_conversa,
    id_etapa_resultante,
    data_interacao,
    cursor,
):
    if id_etapa_resultante not in {ETAPA_INICIAL, 4}:
        raise ValueError(
            "Inicializacao exige etapa 1 ou importacao FireAds na etapa 4"
        )

    _validar_data_interacao_bot(data_interacao)

    cursor.execute("""
        UPDATE chatbot.conversa
        SET
            id_etapa_atual = %s,
            last_message_from = 'bot',
            last_interaction_at = %s
        WHERE id_conversa = %s
          AND id_etapa_atual IS NULL
          AND (%s = 1 OR (contexto_fireads->>'resultado' = 'importado'
               AND contexto_fireads->>'concluida' = 'true'
               AND contexto_fireads->>'id_conversa' = id_conversa::text));
    """, (
        id_etapa_resultante,
        data_interacao,
        id_conversa,
        id_etapa_resultante,
    ))

    logger.debug(
        "conversa_update | acao=inicializar_etapa id_conversa=%s etapa=%s linhas=%s",
        id_conversa,
        id_etapa_resultante,
        cursor.rowcount,
    )

    if cursor.rowcount != 1:
        raise ValueError(
            "Conversa nao foi inicializada na etapa autorizada "
            f"(id_conversa={id_conversa}, linhas={cursor.rowcount})"
        )

    return cursor.rowcount


def atualizar_conversa_por_transicao(
    id_conversa,
    id_etapa_origem,
    evento_transicao,
    id_etapa_destino,
    data_interacao,
    cursor,
    *,
    permitir_reaplicacao=False,
):
    if id_etapa_origem is None:
        raise ValueError("Etapa de origem nao informada para transicao")

    if not evento_transicao:
        raise ValueError("Evento nao informado para transicao")

    if id_etapa_destino is None:
        raise ValueError("Etapa de destino nao informada para transicao")

    _validar_data_interacao_bot(data_interacao)

    cursor.execute(
        """
        UPDATE chatbot.conversa AS conversa
        SET
            id_etapa_atual = CASE
                WHEN conversa.id_etapa_atual = %s THEN %s
                ELSE conversa.id_etapa_atual
            END,
            last_message_from = 'bot',
            last_interaction_at = %s
        WHERE conversa.id_conversa = %s
          AND EXISTS (
              SELECT 1
              FROM chatbot.etapa_transicao AS transicao
              WHERE transicao.id_etapa_origem = %s
                AND transicao.evento = %s
                AND transicao.id_etapa_destino = %s
          )
          AND (
              conversa.id_etapa_atual = %s
              OR (
                  %s = TRUE
                  AND conversa.id_etapa_atual = %s
              )
          );
        """,
        (
            id_etapa_origem,
            id_etapa_destino,
            data_interacao,
            id_conversa,
            id_etapa_origem,
            evento_transicao,
            id_etapa_destino,
            id_etapa_origem,
            bool(permitir_reaplicacao),
            id_etapa_destino,
        ),
    )

    logger.debug(
        "conversa_update | acao=aplicar_transicao id_conversa=%s etapa_origem=%s evento=%s etapa_destino=%s reaplicacao=%s linhas=%s",
        id_conversa,
        id_etapa_origem,
        evento_transicao,
        id_etapa_destino,
        bool(permitir_reaplicacao),
        cursor.rowcount,
    )

    if cursor.rowcount != 1:
        raise ValueError(
            "Conversa nao foi atualizada; transicao inexistente, origem "
            "incompativel ou conversa ausente "
            f"(id_conversa={id_conversa}, origem={id_etapa_origem}, "
            f"evento={evento_transicao}, destino={id_etapa_destino}, "
            f"reaplicacao={bool(permitir_reaplicacao)}, "
            f"linhas={cursor.rowcount})"
        )

    return cursor.rowcount


def atualizar_conversa_resposta_bot_sem_avancar(
    id_conversa,
    data_interacao,
    cursor,
):
    _validar_data_interacao_bot(data_interacao)

    cursor.execute("""
        UPDATE chatbot.conversa
        SET
            last_message_from = 'bot',
            last_interaction_at = %s
        WHERE id_conversa = %s;
    """, (data_interacao, id_conversa))

    logger.debug(
        "conversa_update | acao=registrar_resposta_bot_sem_avancar id_conversa=%s data_interacao=%s linhas=%s",
        id_conversa,
        data_interacao,
        cursor.rowcount,
    )

    if cursor.rowcount != 1:
        raise ValueError(
            "Conversa nao foi atualizada com resposta do bot sem avancar etapa "
            f"(id_conversa={id_conversa}, linhas={cursor.rowcount})"
        )

    return cursor.rowcount


def atualizar_status_dependente_conversa(
    id_conversa,
    status_dependente,
    cursor,
):
    cursor.execute("""
        UPDATE chatbot.conversa
        SET status_dependente = %s
        WHERE id_conversa = %s;
    """, (bool(status_dependente), id_conversa))

    logger.debug(
        "conversa_update | acao=atualizar_status_dependente id_conversa=%s status_dependente=%s linhas=%s",
        id_conversa,
        bool(status_dependente),
        cursor.rowcount,
    )

    if cursor.rowcount != 1:
        raise ValueError(
            "Conversa nao foi atualizada com status_dependente "
            f"(id_conversa={id_conversa}, linhas={cursor.rowcount})"
        )

    return cursor.rowcount


def atualizar_profissao_conversa(id_conversa, profissao, cursor):
    if not id_conversa:
        raise ValueError(
            "id_conversa nao informado para atualizar profissao"
        )

    if not isinstance(profissao, str):
        raise ValueError("profissao deve ser um texto")

    profissao_normalizada = profissao.strip()

    if (
        not profissao_normalizada
        or len(profissao_normalizada) > 100
        or "\n" in profissao_normalizada
        or "\r" in profissao_normalizada
    ):
        raise ValueError(
            "profissao deve conter uma unica linha entre 1 e 100 caracteres"
        )

    cursor.execute(
        """
        UPDATE chatbot.conversa
        SET profissao = %s
        WHERE id_conversa = %s;
        """,
        (profissao_normalizada, id_conversa),
    )

    logger.debug(
        "conversa_update | acao=atualizar_profissao id_conversa=%s linhas=%s",
        id_conversa,
        cursor.rowcount,
    )

    if cursor.rowcount != 1:
        raise ValueError(
            "Conversa nao foi atualizada com profissao "
            f"(id_conversa={id_conversa}, linhas={cursor.rowcount})"
        )

    return cursor.rowcount


def encerrar_conversa(id_conversa, motivo_encerramento, cursor):
    if motivo_encerramento not in MOTIVOS_ENCERRAMENTO_VALIDOS:
        raise ValueError(
            "Motivo de encerramento invalido "
            f"(motivo={motivo_encerramento!r})"
        )

    cursor.execute(
        """
        UPDATE chatbot.conversa
        SET
            status_ativa = FALSE,
            finalizou_em = NOW(),
            motivo_encerramento = %s,
            processing = FALSE,
            processing_started_at = NULL
        WHERE id_conversa = %s
          AND status_ativa = TRUE
        RETURNING finalizou_em;
        """,
        (motivo_encerramento, id_conversa),
    )

    resultado = cursor.fetchone()

    if not resultado:
        raise RuntimeError(
            "Conversa não encerrada "
            f"(id_conversa={id_conversa}, linhas={cursor.rowcount})"
        )

    return resultado[0]


def _validar_data_interacao_bot(data_interacao):
    if data_interacao is None:
        raise ValueError(
            "data_interacao nao informada para registrar resposta do bot"
        )
```

## Passo 9 — Substituir integralmente `core/repositories/fluxo/contextos/etapa1.py`

```python
def buscar_contexto_etapa1(id_unidade, cursor):
    cursor.execute(
        """
        SELECT nome_unidade, nome_agente, genero
        FROM chatbot.unidade_atendimento
        WHERE id_unidade = %s;
        """,
        (id_unidade,),
    )

    resultado = cursor.fetchone()

    if not resultado:
        raise ValueError(
            "Unidade nao encontrada para montar a etapa 1 "
            f"(id_unidade={id_unidade})"
        )

    nome_unidade = str(resultado[0] or "").strip()
    nome_agente = str(resultado[1] or "").strip()
    genero = str(resultado[2] or "").strip()

    if not nome_unidade:
        raise ValueError(
            "Unidade sem nome_unidade para montar a etapa 1 "
            f"(id_unidade={id_unidade})"
        )

    if not nome_agente:
        raise ValueError(
            "Unidade sem nome_agente para montar a etapa 1 "
            f"(id_unidade={id_unidade})"
        )

    if genero not in {"masculino", "feminino"}:
        raise ValueError(
            "Unidade com genero de agente invalido para montar a etapa 1 "
            f"(id_unidade={id_unidade}, genero={genero!r})"
        )

    return {
        "nome_unidade": nome_unidade,
        "nome_agente": nome_agente,
        "genero": genero,
    }
```

## Passo 10 — Substituir integralmente `core/repositories/fluxo/contextos/etapa10.py`

```python
import logging


logger = logging.getLogger("db.contexto_etapa10")


def buscar_contexto_etapa10(id_conversa, id_unidade, cursor):
    """Carrega a política de e-mail e o participante da introdução à triagem."""
    cursor.execute(
        """
        SELECT
            u.email_obrigatorio,
            c.status_dependente,
            cl.idade,
            d.nome_dependente
        FROM chatbot.conversa c
        JOIN chatbot.unidade_atendimento u
          ON u.id_unidade = c.id_unidade
        JOIN chatbot.cliente cl
          ON cl.id_cliente = c.id_cliente
        LEFT JOIN chatbot.dependente d
          ON d.id_conversa = c.id_conversa
        WHERE c.id_conversa = %s
          AND c.id_unidade = %s
        LIMIT 1;
        """,
        (id_conversa, id_unidade),
    )

    resultado = cursor.fetchone()

    if not resultado:
        raise ValueError(
            "Contexto da etapa 10 não encontrado "
            f"(id_conversa={id_conversa}, id_unidade={id_unidade})"
        )

    email_obrigatorio, status_dependente, idade_cliente, nome_dependente = resultado

    if not isinstance(email_obrigatorio, bool):
        raise ValueError(
            "Configuração email_obrigatorio inválida "
            f"(id_unidade={id_unidade}, valor={email_obrigatorio!r})"
        )

    if not isinstance(status_dependente, bool):
        raise ValueError(
            "Etapa 10 sem destino de atendimento definido "
            f"(id_conversa={id_conversa}, valor={status_dependente!r})"
        )

    if (
        not status_dependente
        and (
            isinstance(idade_cliente, bool)
            or not isinstance(idade_cliente, int)
            or idade_cliente < 18
            or idade_cliente >= 100
        )
    ):
        raise ValueError(
            "Etapa 10 de titular sem idade válida persistida "
            f"(id_conversa={id_conversa}, idade={idade_cliente!r})"
        )

    if status_dependente and (
        not isinstance(nome_dependente, str) or not nome_dependente.strip()
    ):
        raise ValueError(
            "Etapa 10 de dependente sem nome persistido para apresentar a triagem "
            f"(id_conversa={id_conversa})"
        )

    logger.debug(
        "contexto_etapa10_consultado | id_conversa=%s id_unidade=%s "
        "email_obrigatorio=%s status_dependente=%s "
        "idade_cliente_definida=%s",
        id_conversa,
        id_unidade,
        email_obrigatorio,
        status_dependente,
        idade_cliente is not None,
    )

    return {
        "email_obrigatorio_unidade": email_obrigatorio,
        "status_dependente_contexto_email": status_dependente,
        "idade_cliente": idade_cliente,
        "nome_dependente": nome_dependente.strip() if status_dependente else None,
    }
```

## Passo 11 — Substituir integralmente `core/repositories/fluxo/contextos/etapa18.py`

```python
"""Contexto da escolha de turno e da entrega ao comercial, por conversa/unidade."""


def buscar_contexto_etapa18(id_conversa, id_unidade, cursor):
    cursor.execute(
        """
        SELECT NULLIF(BTRIM(u.link_agendamento), ''), u.numero_comercial,
               u.nome_agente, u.genero, cl.nome, cl.idade,
               d.nome_dependente, d.idade, c.status_dependente, c.turno
        FROM chatbot.conversa c
        JOIN chatbot.unidade_atendimento u ON u.id_unidade = c.id_unidade
        JOIN chatbot.cliente cl ON cl.id_cliente = c.id_cliente
        LEFT JOIN chatbot.dependente d ON d.id_conversa = c.id_conversa
        WHERE c.id_conversa = %s AND c.id_unidade = %s;
        """,
        (id_conversa, id_unidade),
    )
    row = cursor.fetchone()
    if row is None:
        raise ValueError("Conversa/unidade ausente no contexto de sua reserva")
    if not isinstance(row[8], bool):
        raise ValueError("Destino de atendimento ausente no contexto de sua reserva")
    if not row[4] or (row[8] and not row[6]):
        raise ValueError("Nome do titular ou do dependente ausente")
    return dict(
        zip(
            (
                "link_agendamento_unidade",
                "numero_comercial_unidade",
                "nome_agente_unidade",
                "genero_agente_unidade",
                "nome_cliente",
                "idade_cliente",
                "nome_dependente",
                "idade_dependente",
                "status_dependente_reserva",
                "turno",
            ),
            row,
        )
    )
```

## Passo 12 — Substituir integralmente `core/repositories/fluxo/contextos/etapa20.py`

```python
import logging


logger = logging.getLogger("db.contexto_etapa20")


def buscar_contexto_etapa20(id_conversa, id_unidade, cursor):
    """Carrega link, cliente e participante para apresentar ou repetir sua reserva."""
    cursor.execute(
        """
        SELECT
            u.link_agendamento,
            cl.nome,
            c.status_dependente,
            d.nome_dependente
        FROM chatbot.conversa c
        JOIN chatbot.unidade_atendimento u
          ON u.id_unidade = c.id_unidade
        JOIN chatbot.cliente cl
          ON cl.id_cliente = c.id_cliente
        LEFT JOIN chatbot.dependente d
          ON d.id_conversa = c.id_conversa
        WHERE c.id_conversa = %s
          AND c.id_unidade = %s
        LIMIT 1;
        """,
        (id_conversa, id_unidade),
    )

    resultado = cursor.fetchone()

    if not resultado:
        raise ValueError(
            "Contexto da etapa 20 não encontrado "
            f"(id_conversa={id_conversa}, id_unidade={id_unidade})"
        )

    link_agendamento, nome_cliente, status_dependente, nome_dependente = resultado

    if not isinstance(status_dependente, bool):
        raise ValueError("Destino do atendimento ausente para sua reserva")
    if status_dependente and (
        not isinstance(nome_dependente, str) or not nome_dependente.strip()
    ):
        raise ValueError("Nome do dependente ausente para sua reserva")

    if not link_agendamento or not str(link_agendamento).strip():
        raise ValueError(
            "Unidade sem link de agendamento configurado " f"(id_unidade={id_unidade})"
        )

    if not nome_cliente or not str(nome_cliente).strip():
        raise ValueError(
            "Cliente sem nome para iniciar a pesquisa de satisfação "
            f"(id_conversa={id_conversa})"
        )

    logger.debug(
        "contexto_etapa20_consultado | id_conversa=%s id_unidade=%s "
        "link_agendamento_configurado=%s nome_cliente_configurado=%s",
        id_conversa,
        id_unidade,
        True,
        True,
    )

    return {
        "link_agendamento_unidade": str(link_agendamento).strip(),
        "nome_cliente": str(nome_cliente).strip(),
        "nome_dependente": nome_dependente.strip() if status_dependente else None,
    }
```

## Passo 13 — Substituir integralmente `core/repositories/fluxo/contextos/etapa6.py`

```python
import logging

from core.validacoes.suporte_por_idade import validar_idade_minima_suporte


logger = logging.getLogger("db.contexto_etapa6")


def buscar_contexto_etapa6(id_conversa, id_unidade, cursor):
    cursor.execute(
        """
        SELECT
            u.numero_comercial,
            u.bpa_ativo,
            u.idade_minima_suporte,
            cl.nome,
            d.nome_dependente,
            u.nome_agente,
            u.genero,
            u.nome_unidade
        FROM chatbot.unidade_atendimento u
        JOIN chatbot.conversa c
          ON c.id_conversa = %s
         AND c.id_unidade = u.id_unidade
        JOIN chatbot.cliente cl
          ON cl.id_cliente = c.id_cliente
        LEFT JOIN chatbot.dependente d
          ON d.id_conversa = c.id_conversa
        WHERE u.id_unidade = %s
        LIMIT 1;
        """,
        (id_conversa, id_unidade),
    )

    resultado = cursor.fetchone()

    if not resultado:
        raise ValueError(
            "Contexto da etapa 6 não encontrado "
            f"(id_conversa={id_conversa}, id_unidade={id_unidade})"
        )

    (
        numero_comercial,
        bpa_ativo,
        idade_minima_suporte,
        nome_titular,
        nome_dependente,
        nome_agente,
        genero_agente,
        nome_unidade,
    ) = resultado

    logger.debug(
        "contexto_etapa6_consultado | id_conversa=%s id_unidade=%s "
        "numero_comercial_configurado=%s bpa_ativo=%s idade_minima_suporte=%s "
        "cliente_nomeado=%s dependente_nomeado=%s",
        id_conversa,
        id_unidade,
        bool(numero_comercial),
        bool(bpa_ativo),
        idade_minima_suporte,
        bool(nome_titular),
        bool(nome_dependente),
    )

    validar_idade_minima_suporte(idade_minima_suporte)

    return {
        "numero_comercial_unidade": numero_comercial,
        "bpa_ativo_unidade": bool(bpa_ativo),
        "idade_minima_suporte": idade_minima_suporte,
        "nome_titular": nome_titular,
        "nome_dependente": nome_dependente,
        "nome_agente": nome_agente,
        "genero_agente_unidade": genero_agente,
        "nome_unidade": nome_unidade,
    }
```

## Passo 14 — Substituir integralmente `core/repositories/fluxo/contextos/etapa7.py`

```python
import logging


logger = logging.getLogger("db.contexto_etapa7")


def buscar_contexto_etapa7(id_conversa, id_unidade, cursor):
    cursor.execute(
        """
        SELECT
            cl.nome,
            d.nome_dependente,
            u.link_instagram
        FROM chatbot.conversa c
        JOIN chatbot.cliente cl
          ON cl.id_cliente = c.id_cliente
        JOIN chatbot.unidade_atendimento u
          ON u.id_unidade = c.id_unidade
        LEFT JOIN chatbot.dependente d
          ON d.id_conversa = c.id_conversa
        WHERE c.id_conversa = %s
          AND c.id_unidade = %s
        LIMIT 1;
        """,
        (id_conversa, id_unidade),
    )

    resultado = cursor.fetchone()

    if not resultado:
        raise ValueError(
            "Contexto da etapa 7 não encontrado "
            f"(id_conversa={id_conversa}, id_unidade={id_unidade})"
        )

    nome_titular, nome_dependente, link_instagram = resultado

    logger.debug(
        "contexto_etapa7_consultado | id_conversa=%s id_unidade=%s "
        "cliente_nomeado=%s dependente_nomeado=%s "
        "instagram_configurado=%s",
        id_conversa,
        id_unidade,
        bool(nome_titular),
        bool(nome_dependente),
        bool(link_instagram),
    )

    return {
        "nome_titular": nome_titular,
        "nome_dependente": nome_dependente,
        "link_instagram_unidade": link_instagram,
    }
```

## Passo 15 — Substituir integralmente `core/repositories/fluxo/contextos/etapa9.py`

```python
import logging


logger = logging.getLogger("db.contexto_etapa9")


def buscar_contexto_etapa9(id_conversa, id_unidade, cursor):
    """
    Carrega os dados usados na entrada e nas respostas da etapa 9.

    A etapa 8 usa o mesmo contexto para construir a entrada real da etapa 9.
    """
    cursor.execute(
        """
        SELECT
            cl.nome,
            d.nome_dependente,
            u.link_instagram
        FROM chatbot.conversa c
        JOIN chatbot.cliente cl
          ON cl.id_cliente = c.id_cliente
        JOIN chatbot.unidade_atendimento u
          ON u.id_unidade = c.id_unidade
        LEFT JOIN chatbot.dependente d
          ON d.id_conversa = c.id_conversa
        WHERE c.id_conversa = %s
          AND c.id_unidade = %s
        LIMIT 1;
        """,
        (id_conversa, id_unidade),
    )

    resultado = cursor.fetchone()

    if not resultado:
        raise ValueError(
            "Contexto da etapa 9 não encontrado "
            f"(id_conversa={id_conversa}, id_unidade={id_unidade})"
        )

    nome_titular, nome_dependente, link_instagram = resultado

    logger.debug(
        "contexto_etapa9_consultado | id_conversa=%s id_unidade=%s "
        "cliente_nomeado=%s dependente_nomeado=%s "
        "instagram_configurado=%s",
        id_conversa,
        id_unidade,
        bool(nome_titular),
        bool(nome_dependente),
        bool(link_instagram),
    )

    return {
        "nome_titular": nome_titular,
        "nome_dependente": nome_dependente,
        "link_instagram_unidade": link_instagram,
    }
```

## Passo 16 — Substituir integralmente `core/integrations/whatsapp/messages/etapa4_messages.py`

```python
"""Etapa 4: apresentação, repetição e tratamentos compostos."""

from core.integrations.whatsapp.messages.tratamentos.financeiro import (
    montar_mensagem_tratamento_financeiro,
)
from core.integrations.whatsapp.messages.tratamentos.midia import (
    montar_mensagem_tratamento_midia,
)
from core.integrations.whatsapp.messages.tratamentos.reforco_escolar import (
    montar_mensagem_tratamento_reforco_escolar,
)


### MENSAGEM INICIAL DO TITULAR: EXPLICAÇÃO + PERGUNTA DA PROFISSÃO
MENSAGEM_PADRAO_TITULAR_ETAPA4 = (
    "Olha, antes de continuar, vou precisar fazer algumas perguntas para "
    "conhecer melhor seu perfil. Me diz, qual a sua *profissão*?"
)

### MENSAGEM INICIAL DO DEPENDENTE: A PROFISSÃO CONTINUA SENDO DO TITULAR
MENSAGEM_PADRAO_DEPENDENTE_ETAPA4 = (
    "Olha, antes de continuar, vou precisar fazer algumas perguntas para "
    "conhecer melhor o seu perfil e o perfil da outra pessoa. Me diz, qual a sua *profissão* hoje?"
)

### REPETIÇÃO COMUM ÀS DUAS ROTAS, SEM REAPRESENTAR A ABERTURA
MENSAGEM_REPETICAO_ETAPA4 = "Me diz, qual a sua *profissão* hoje?"

ORIENTACAO_CONTEXTO_ETAPA4 = (
    "Olha, não consegui entender. Me conta, com o que você "
    "trabalha hoje?"
)


def montar_mensagem_etapa4(*, status_dependente=False, repeticao=False):
    if repeticao:
        return MENSAGEM_REPETICAO_ETAPA4
    return (
        MENSAGEM_PADRAO_DEPENDENTE_ETAPA4
        if status_dependente
        else MENSAGEM_PADRAO_TITULAR_ETAPA4
    )


### TRATAMENTOS: ORIENTAÇÃO + REPETIÇÃO, SEM A MENSAGEM INICIAL
def montar_mensagem_financeiro_etapa4():
    return montar_mensagem_tratamento_financeiro(MENSAGEM_REPETICAO_ETAPA4)


def montar_mensagem_midia_etapa4():
    return montar_mensagem_tratamento_midia(MENSAGEM_REPETICAO_ETAPA4)


def montar_mensagem_reforco_escolar_etapa4():
    return montar_mensagem_tratamento_reforco_escolar(MENSAGEM_REPETICAO_ETAPA4)


### CONTEXTO INVÁLIDO: MENSAGEM PRÓPRIA, SEM CONCATENAR A REPETIÇÃO
def montar_mensagem_contexto_profissao_invalida_etapa4():
    return ORIENTACAO_CONTEXTO_ETAPA4


def montar_abertura_fireads(contexto, *, saudacao, tratamento=None):
    """Primeira resposta após importação completa; pergunta continua na etapa 4."""
    dados = contexto['contexto_fireads']['dados_titular']
    genero = contexto.get('genero')
    if genero not in {'masculino', 'feminino'} or not contexto.get('nome_agente'):
        raise ValueError('Apresentação da unidade incompleta')
    artigo = 'a' if genero == 'feminino' else 'o'
    abertura = (
        f"{saudacao}, {dados['nome']}! Sou {artigo} "
        f"{contexto['nome_agente']}, assistente do {contexto['nome_unidade']}. ☺️\n\n"
        "Vi que você já preencheu um dos nossos formulários. Para continuarmos "
        "com sua reserva por cortesia da unidade, precisamos fazer mais algumas perguntinhas, ok?"
    )
    pergunta = MENSAGEM_REPETICAO_ETAPA4
    if tratamento == 'tipo_mensagem_nao_suportado':
        pergunta = montar_mensagem_tratamento_midia(pergunta)
    elif tratamento == 'duvida_reforco_escolar':
        pergunta = montar_mensagem_tratamento_reforco_escolar(pergunta)
    elif tratamento == 'pergunta_financeira':
        pergunta = montar_mensagem_tratamento_financeiro(pergunta)
    elif tratamento is not None:
        raise ValueError('Tratamento de abertura FireAds desconhecido')
    return abertura + '\n\n' + pergunta
```

## Passo 17 — Substituir integralmente `core/integrations/whatsapp/pywa_functions/pywa_senders/etapa4.py`

```python
import logging

from core.integrations.whatsapp.exceptions import ErroEnvioMeta
from core.integrations.whatsapp.messages.etapa4_messages import (
    montar_mensagem_contexto_profissao_invalida_etapa4,
    montar_mensagem_etapa4,
    montar_mensagem_financeiro_etapa4,
    montar_mensagem_midia_etapa4,
    montar_mensagem_reforco_escolar_etapa4,
    montar_abertura_fireads,
)
from core.integrations.whatsapp.pywa_functions.cliente import conta_wa
from core.integrations.whatsapp.pywa_functions.resposta_envio import (
    extrair_id_hash_msg_bot,
)
from core.integrations.whatsapp.pywa_functions.saudacao import (
    obter_saudacao_por_horario,
)
from core.logging_config import short_value


logger = logging.getLogger("whatsapp.etapa4")

ID_ETAPA4 = 4
TIPO_TRATAMENTO_MIDIA = "tipo_mensagem_nao_suportado"
TIPO_TRATAMENTO_FINANCEIRO = "pergunta_financeira"
TIPO_TRATAMENTO_REFORCO_ESCOLAR = "duvida_reforco_escolar"
TIPO_TRATAMENTO_PROFISSAO_INVALIDA = "profissao_invalida"


def enviar_etapa4(
    cliente_telefone,
    phone_id_unidade,
    *,
    status_dependente=False,
    repeticao=False,
):
    return _enviar_texto_etapa4(
        cliente_telefone,
        phone_id_unidade,
        montar_mensagem_etapa4(
            status_dependente=status_dependente,
            repeticao=repeticao,
        ),
        evento="enviar_etapa4",
    )


def enviar_etapa4_midia(cliente_telefone, phone_id_unidade):
    return _enviar_texto_etapa4(
        cliente_telefone,
        phone_id_unidade,
        montar_mensagem_midia_etapa4(),
        evento="enviar_etapa4_midia",
        tipo_tratamento=TIPO_TRATAMENTO_MIDIA,
    )


def enviar_etapa4_financeiro(cliente_telefone, phone_id_unidade):
    return _enviar_texto_etapa4(
        cliente_telefone,
        phone_id_unidade,
        montar_mensagem_financeiro_etapa4(),
        evento="enviar_etapa4_financeiro",
        tipo_tratamento=TIPO_TRATAMENTO_FINANCEIRO,
    )


def enviar_etapa4_reforco_escolar(cliente_telefone, phone_id_unidade):
    return _enviar_texto_etapa4(
        cliente_telefone,
        phone_id_unidade,
        montar_mensagem_reforco_escolar_etapa4(),
        evento="enviar_etapa4_reforco_escolar",
        tipo_tratamento=TIPO_TRATAMENTO_REFORCO_ESCOLAR,
    )


def enviar_etapa4_contexto_profissao_invalida(
    cliente_telefone,
    phone_id_unidade,
):
    return _enviar_texto_etapa4(
        cliente_telefone,
        phone_id_unidade,
        montar_mensagem_contexto_profissao_invalida_etapa4(),
        evento="enviar_etapa4_contexto_profissao_invalida",
        tipo_tratamento=TIPO_TRATAMENTO_PROFISSAO_INVALIDA,
    )


def _enviar_texto_etapa4(
    cliente_telefone,
    phone_id_unidade,
    mensagem_bot,
    *,
    evento,
    tipo_tratamento=None,
):
    try:
        cliente_wa = conta_wa(phone_id_unidade)
        sent_message = cliente_wa.send_message(
            to=cliente_telefone,
            text=mensagem_bot,
        )
        id_hash_msg_bot = extrair_id_hash_msg_bot(sent_message)

        logger.info(
            "%s_ok | acao=enviar_meta cliente=%s phone_number_id=%s "
            "id_hash_msg_bot=%s tratamento=%s",
            evento,
            short_value(cliente_telefone),
            short_value(phone_id_unidade),
            id_hash_msg_bot,
            tipo_tratamento,
        )

        contexto_envio = {
            "enviou": True,
            "resposta_ja_existia": False,
            "mensagem_bot": mensagem_bot,
            "id_hash_msg_bot": id_hash_msg_bot,
            "id_etapa_resultante": ID_ETAPA4,
            "tipo_mensagem": "text",
            "canal": "meta_whatsapp",
            "atualizar_conversa": True,
            "atualizar_last_from_bot": True,
        }

        if tipo_tratamento:
            contexto_envio["tratamento"] = True
            contexto_envio["tipo_tratamento"] = tipo_tratamento

        return contexto_envio

    except Exception as erro:
        logger.exception(
            "%s_erro | motivo=meta_falhou acao=levantar_erro cliente=%s "
            "phone_number_id=%s erro=%s",
            evento,
            short_value(cliente_telefone),
            short_value(phone_id_unidade),
            erro,
        )
        raise ErroEnvioMeta(
            "Meta falhou ao enviar mensagem da etapa 4",
            id_etapa=ID_ETAPA4,
            phone_id_unidade=phone_id_unidade,
            cliente_telefone=cliente_telefone,
        ) from erro


def enviar_abertura_fireads(contexto, *, tratamento=None):
    """Usa o mesmo envio/histórico da etapa 4, com a apresentação importada."""
    mensagem = contexto['mensagem_cliente_atual']
    return _enviar_texto_etapa4(
        mensagem['cliente_telefone'], mensagem['id_phone_unidade'],
        montar_abertura_fireads(
            contexto, saudacao=obter_saudacao_por_horario(), tratamento=tratamento,
        ),
        evento='fireads_abertura', tipo_tratamento=tratamento,
    )
```

## Passo 18 — Substituir integralmente `workers/worker_flow/response_flow/etapas/resolver_etapa7.py`

```python
import logging
from workers.worker_flow.fireads import email_importado
from core.integrations.whatsapp.pywa_functions.pywa_senders.etapa11 import enviar_etapa11

from workers.worker_flow.response_flow.repeticao_followup import (
    enviar_repeticao_followup,
)

from core.integrations.whatsapp.pywa_functions.pywa_senders.etapa7 import (
    enviar_etapa7_cliente_contexto_invalido,
    enviar_etapa7_cliente_financeiro,
    enviar_etapa7_cliente_midia,
    enviar_etapa7_cliente_reforco_escolar,
    enviar_etapa7_dependente_contexto_invalido,
    enviar_etapa7_dependente_financeiro,
    enviar_etapa7_dependente_midia,
    enviar_etapa7_dependente_reforco_escolar,
)
from core.integrations.whatsapp.pywa_functions.pywa_senders.etapa8 import (
    enviar_etapa8,
)
from core.integrations.whatsapp.pywa_functions.pywa_senders.etapa10 import (
    enviar_etapa10,
)
from core.logging_config import short_value
from workers.worker_flow.response_flow.etapas.validadores_contexto.valida_etapa7 import (
    TIPO_TRATAMENTO_CONTEXTO_INVALIDO,
    validar_etapa7,
)
from workers.worker_flow.response_flow.etapas.validadores_universais.validador_financeiro import (
    TIPO_TRATAMENTO_FINANCEIRO,
    validar_pergunta_financeira,
)
from workers.worker_flow.response_flow.etapas.validadores_universais.validador_midia import (
    validar_midia,
)
from workers.worker_flow.response_flow.etapas.validadores_universais.validador_reforco_escolar import (
    TIPO_TRATAMENTO_REFORCO_ESCOLAR,
    validar_duvida_reforco_escolar,
)
from workers.worker_flow.response_flow.transicoes.eventos import (
    ETAPA_8_OFERTA_ADIADA,
    ETAPA_10_EMAIL,
    EVENTO_OFERTA_ACEITA,
    EVENTO_OFERTA_ADIADA,
)
from workers.worker_flow.response_flow.transicoes.resolver_transicao import (
    anexar_transicao_ao_contexto_envio,
    resolver_destino_transicao,
)


"""
ESSE ARQUIVO TEM DUAS RESPONSABILIDADES

- VALIDAR A ETAPA 7
- ENCAMINHAR PARA A ETAPA AUTORIZADA PELO MAPA
"""


logger = logging.getLogger("worker.etapa7")


def resolve_etapa7(contexto_historico):
    """
    Mídia, financeiro e contexto inválido recebem tratamento sem avançar.

    oferta_aceita resolve 7 -> 10.
    oferta_adiada resolve 7 -> 8.

    As etapas 8 e 10 possuem senders reais.
    """
    tipo_mensagem = contexto_historico.get("tipo_mensagem_atual")
    texto_cliente = contexto_historico.get("texto_cliente_atual") or ""
    status_dependente = bool(
        contexto_historico.get("status_dependente")
    )
    nome_dependente = contexto_historico.get("nome_dependente")
    link_instagram = contexto_historico.get(
        "link_instagram_unidade"
    )
    mensagem_cliente = contexto_historico["mensagem_cliente_atual"]
    cliente_telefone = mensagem_cliente["cliente_telefone"]
    phone_id_unidade = mensagem_cliente["id_phone_unidade"]

# CAMPOS QUE VALIDAM MIDIA NA ETAPA 7
    if validar_midia(tipo_mensagem):
        _logar_tipo_nao_suportado(contexto_historico)

        if status_dependente:
            return enviar_etapa7_dependente_midia(
                cliente_telefone,
                phone_id_unidade,
                nome_dependente,
            )

        return enviar_etapa7_cliente_midia(
            cliente_telefone,
            phone_id_unidade,
        )

# DÚVIDA SOBRE REFORÇO TEM PRIORIDADE SOBRE O FINANCEIRO
    if validar_duvida_reforco_escolar(texto_cliente):
        _logar_tratamento_texto(
            contexto_historico,
            TIPO_TRATAMENTO_REFORCO_ESCOLAR,
        )

        if status_dependente:
            return enviar_etapa7_dependente_reforco_escolar(
                cliente_telefone,
                phone_id_unidade,
                nome_dependente,
            )

        return enviar_etapa7_cliente_reforco_escolar(
            cliente_telefone,
            phone_id_unidade,
        )

    if validar_pergunta_financeira(texto_cliente, referencia_experiencia=True):
        _logar_tratamento_texto(
            contexto_historico,
            TIPO_TRATAMENTO_FINANCEIRO,
        )

        if status_dependente:
            return enviar_etapa7_dependente_financeiro(
                cliente_telefone,
                phone_id_unidade,
                nome_dependente,
            )

        return enviar_etapa7_cliente_financeiro(
            cliente_telefone,
            phone_id_unidade,
        )

    # VALIDANDO OPCOES
    # O validador contextual já devolve o evento pertencente à etapa 7.
    evento_transicao = validar_etapa7(texto_cliente)

    if evento_transicao is None:
        if contexto_historico.get("retorno_followup"):
            return enviar_repeticao_followup(contexto_historico)
        _logar_tratamento_texto(
            contexto_historico,
            TIPO_TRATAMENTO_CONTEXTO_INVALIDO,
        )

        if status_dependente:
            return enviar_etapa7_dependente_contexto_invalido(
                cliente_telefone,
                phone_id_unidade,
                nome_dependente,
            )

        return enviar_etapa7_cliente_contexto_invalido(
            cliente_telefone,
            phone_id_unidade,
        )

    # Somente o snapshot desta conversa autoriza aproveitar o e-mail.
    if evento_transicao == 'oferta_aceita' and email_importado(contexto_historico):
        evento_transicao = 'oferta_aceita_email_fireads'

    # VALIDANDO DESTINO(S)
    # A resposta já passou pelos tratamentos; agora o mapa autoriza a aresta.
    destinos_esperados = _destinos_esperados_por_evento(
        evento_transicao
    )
    etapa_destino = resolver_destino_transicao(
        contexto_historico,
        evento_transicao,
        destinos_esperados=destinos_esperados,
    )

    logger.info(
        "etapa7_oferta_validada | acao=%s "
        "id_conversa=%s id_mensagem_fila=%s evento=%s etapa_destino=%s "
        "status_dependente=%s",
        (
            "enviar_etapa8"
            if evento_transicao == EVENTO_OFERTA_ADIADA
            else "enviar_etapa10"
        ),
        contexto_historico["id_conversa"],
        mensagem_cliente["id_mensagem_fila"],
        evento_transicao,
        etapa_destino,
        status_dependente,
    )

    if evento_transicao == EVENTO_OFERTA_ADIADA:
        contexto_envio = enviar_etapa8(
            cliente_telefone,
            phone_id_unidade,
            link_instagram,
        )
    elif evento_transicao == 'oferta_aceita_email_fireads':
        contexto_envio = enviar_etapa11(
            cliente_telefone, phone_id_unidade,
            status_dependente=status_dependente, nome_dependente=nome_dependente,
        )
    else:
        contexto_envio = enviar_etapa10(
            cliente_telefone,
            phone_id_unidade,
        )

    contexto_envio["decisao_oferta"] = evento_transicao

    return anexar_transicao_ao_contexto_envio(
        contexto_historico,
        contexto_envio,
        evento_transicao,
        etapa_destino,
    )


def _destinos_esperados_por_evento(evento_transicao):
    if evento_transicao == 'oferta_aceita_email_fireads':
        return {11}

    if evento_transicao == EVENTO_OFERTA_ACEITA:
        return {ETAPA_10_EMAIL}

    if evento_transicao == EVENTO_OFERTA_ADIADA:
        return {ETAPA_8_OFERTA_ADIADA}

    return set()


def _logar_tipo_nao_suportado(contexto_historico):
    mensagem = contexto_historico["mensagem_cliente_atual"]

    logger.info(
        "resposta_cliente_invalida | motivo=tipo_mensagem_nao_suportado "
        "acao=tratar_sem_avancar id_conversa=%s id_mensagem_fila=%s "
        "cliente=%s phone_number_id=%s tipo=%s etapa_cliente=%s",
        contexto_historico["id_conversa"],
        mensagem["id_mensagem_fila"],
        short_value(mensagem["cliente_telefone"]),
        short_value(mensagem["id_phone_unidade"]),
        contexto_historico.get("tipo_mensagem_atual"),
        contexto_historico["id_etapa_cliente"],
    )


def _logar_tratamento_texto(contexto_historico, motivo):
    mensagem = contexto_historico["mensagem_cliente_atual"]

    logger.info(
        "resposta_cliente_tratamento | motivo=%s motivo_detalhado=%s "
        "acao=tratar_sem_avancar id_conversa=%s id_mensagem_fila=%s "
        "cliente=%s phone_number_id=%s etapa_cliente=%s",
        motivo,
        None,
        contexto_historico["id_conversa"],
        mensagem["id_mensagem_fila"],
        short_value(mensagem["cliente_telefone"]),
        short_value(mensagem["id_phone_unidade"]),
        contexto_historico["id_etapa_cliente"],
    )
```

## Passo 19 — Substituir integralmente `workers/worker_flow/response_flow/etapas/resolver_etapa9.py`

```python
import logging
from workers.worker_flow.fireads import email_importado
from core.integrations.whatsapp.pywa_functions.pywa_senders.etapa11 import enviar_etapa11

from workers.worker_flow.response_flow.repeticao_followup import (
    enviar_repeticao_followup,
)

from core.integrations.whatsapp.pywa_functions.pywa_senders.etapa8 import (
    enviar_etapa8,
)
from core.integrations.whatsapp.pywa_functions.pywa_senders.etapa9 import (
    enviar_etapa9_cliente_contexto_invalido,
    enviar_etapa9_cliente_financeiro,
    enviar_etapa9_cliente_midia,
    enviar_etapa9_cliente_reforco_escolar,
    enviar_etapa9_dependente_contexto_invalido,
    enviar_etapa9_dependente_financeiro,
    enviar_etapa9_dependente_midia,
    enviar_etapa9_dependente_reforco_escolar,
)
from core.integrations.whatsapp.pywa_functions.pywa_senders.etapa10 import (
    enviar_etapa10,
)
from core.logging_config import short_value
from workers.worker_flow.response_flow.etapas.validadores_contexto.valida_etapa9 import (
    TIPO_TRATAMENTO_CONTEXTO_INVALIDO,
    validar_etapa9,
)
from workers.worker_flow.response_flow.etapas.validadores_universais.validador_financeiro import (
    TIPO_TRATAMENTO_FINANCEIRO,
    validar_pergunta_financeira,
)
from workers.worker_flow.response_flow.etapas.validadores_universais.validador_midia import (
    validar_midia,
)
from workers.worker_flow.response_flow.etapas.validadores_universais.validador_reforco_escolar import (
    TIPO_TRATAMENTO_REFORCO_ESCOLAR,
    validar_duvida_reforco_escolar,
)
from workers.worker_flow.response_flow.transicoes.eventos import (
    ETAPA_8_OFERTA_ADIADA,
    ETAPA_10_EMAIL,
    EVENTO_RETORNO_ADIADO,
    EVENTO_RETORNO_CONFIRMADO,
)
from workers.worker_flow.response_flow.transicoes.resolver_transicao import (
    anexar_transicao_ao_contexto_envio,
    resolver_destino_transicao,
)


"""
ESSE ARQUIVO TEM DUAS RESPONSABILIDADES

- VALIDAR A ETAPA 9
- ENCAMINHAR PARA A ETAPA AUTORIZADA PELO MAPA
"""


logger = logging.getLogger("worker.etapa9")


def resolve_etapa9(contexto_historico):
    """
    Mídia, financeiro e contexto inválido recebem tratamento sem avançar.

    retorno_confirmado resolve 9 -> 10.
    retorno_adiado resolve 9 -> 8.

    As etapas 8 e 10 possuem senders reais.
    """
    tipo_mensagem = contexto_historico.get("tipo_mensagem_atual")
    texto_cliente = contexto_historico.get("texto_cliente_atual") or ""
    status_dependente = bool(
        contexto_historico.get("status_dependente")
    )
    nome_dependente = contexto_historico.get("nome_dependente")
    link_instagram = contexto_historico.get(
        "link_instagram_unidade"
    )
    mensagem_cliente = contexto_historico["mensagem_cliente_atual"]
    cliente_telefone = mensagem_cliente["cliente_telefone"]
    phone_id_unidade = mensagem_cliente["id_phone_unidade"]

# CAMPOS QUE VALIDAM MIDIA NA ETAPA 9
    if validar_midia(tipo_mensagem):
        _logar_tipo_nao_suportado(contexto_historico)

        if status_dependente:
            return enviar_etapa9_dependente_midia(
                cliente_telefone,
                phone_id_unidade,
                nome_dependente,
            )

        return enviar_etapa9_cliente_midia(
            cliente_telefone,
            phone_id_unidade,
        )

# DÚVIDA SOBRE REFORÇO TEM PRIORIDADE SOBRE O FINANCEIRO
    if validar_duvida_reforco_escolar(texto_cliente):
        _logar_tratamento_texto(
            contexto_historico,
            TIPO_TRATAMENTO_REFORCO_ESCOLAR,
        )

        if status_dependente:
            return enviar_etapa9_dependente_reforco_escolar(
                cliente_telefone,
                phone_id_unidade,
                nome_dependente,
            )

        return enviar_etapa9_cliente_reforco_escolar(
            cliente_telefone,
            phone_id_unidade,
        )

    if validar_pergunta_financeira(texto_cliente, referencia_experiencia=True):
        _logar_tratamento_texto(
            contexto_historico,
            TIPO_TRATAMENTO_FINANCEIRO,
        )

        if status_dependente:
            return enviar_etapa9_dependente_financeiro(
                cliente_telefone,
                phone_id_unidade,
                nome_dependente,
            )

        return enviar_etapa9_cliente_financeiro(
            cliente_telefone,
            phone_id_unidade,
        )

    # VALIDANDO OPCOES
    # O validador contextual já devolve o evento pertencente à etapa 9.
    evento_transicao = validar_etapa9(texto_cliente)

    if evento_transicao is None:
        if contexto_historico.get("retorno_followup"):
            return enviar_repeticao_followup(contexto_historico)
        _logar_tratamento_texto(
            contexto_historico,
            TIPO_TRATAMENTO_CONTEXTO_INVALIDO,
        )

        if status_dependente:
            return enviar_etapa9_dependente_contexto_invalido(
                cliente_telefone,
                phone_id_unidade,
                nome_dependente,
            )

        return enviar_etapa9_cliente_contexto_invalido(
            cliente_telefone,
            phone_id_unidade,
        )

    # Somente o snapshot desta conversa autoriza aproveitar o e-mail.
    if evento_transicao == 'retorno_confirmado' and email_importado(contexto_historico):
        evento_transicao = 'retorno_confirmado_email_fireads'

    # VALIDANDO DESTINO(S)
    # A resposta já passou pelos tratamentos; agora o mapa autoriza a aresta.
    destinos_esperados = _destinos_esperados_por_evento(
        evento_transicao
    )
    etapa_destino = resolver_destino_transicao(
        contexto_historico,
        evento_transicao,
        destinos_esperados=destinos_esperados,
    )

    logger.info(
        "etapa9_retorno_validado | acao=%s "
        "id_conversa=%s id_mensagem_fila=%s evento=%s etapa_destino=%s "
        "status_dependente=%s",
        (
            "enviar_etapa8"
            if evento_transicao == EVENTO_RETORNO_ADIADO
            else "enviar_etapa10"
        ),
        contexto_historico["id_conversa"],
        mensagem_cliente["id_mensagem_fila"],
        evento_transicao,
        etapa_destino,
        status_dependente,
    )

    if evento_transicao == EVENTO_RETORNO_ADIADO:
        contexto_envio = enviar_etapa8(
            cliente_telefone,
            phone_id_unidade,
            link_instagram,
        )
    elif evento_transicao == 'retorno_confirmado_email_fireads':
        contexto_envio = enviar_etapa11(
            cliente_telefone, phone_id_unidade,
            status_dependente=status_dependente, nome_dependente=nome_dependente,
        )
    else:
        contexto_envio = enviar_etapa10(
            cliente_telefone,
            phone_id_unidade,
        )

    contexto_envio["decisao_retorno"] = evento_transicao

    return anexar_transicao_ao_contexto_envio(
        contexto_historico,
        contexto_envio,
        evento_transicao,
        etapa_destino,
    )


def _destinos_esperados_por_evento(evento_transicao):
    if evento_transicao == 'retorno_confirmado_email_fireads':
        return {11}

    if evento_transicao == EVENTO_RETORNO_CONFIRMADO:
        return {ETAPA_10_EMAIL}

    if evento_transicao == EVENTO_RETORNO_ADIADO:
        return {ETAPA_8_OFERTA_ADIADA}

    return set()


def _logar_tipo_nao_suportado(contexto_historico):
    mensagem = contexto_historico["mensagem_cliente_atual"]

    logger.info(
        "resposta_cliente_invalida | motivo=tipo_mensagem_nao_suportado "
        "acao=tratar_sem_avancar id_conversa=%s id_mensagem_fila=%s "
        "cliente=%s phone_number_id=%s tipo=%s etapa_cliente=%s",
        contexto_historico["id_conversa"],
        mensagem["id_mensagem_fila"],
        short_value(mensagem["cliente_telefone"]),
        short_value(mensagem["id_phone_unidade"]),
        contexto_historico.get("tipo_mensagem_atual"),
        contexto_historico["id_etapa_cliente"],
    )


def _logar_tratamento_texto(contexto_historico, motivo):
    mensagem = contexto_historico["mensagem_cliente_atual"]

    logger.info(
        "resposta_cliente_tratamento | motivo=%s motivo_detalhado=%s "
        "acao=tratar_sem_avancar id_conversa=%s id_mensagem_fila=%s "
        "cliente=%s phone_number_id=%s etapa_cliente=%s",
        motivo,
        None,
        contexto_historico["id_conversa"],
        mensagem["id_mensagem_fila"],
        short_value(mensagem["cliente_telefone"]),
        short_value(mensagem["id_phone_unidade"]),
        contexto_historico["id_etapa_cliente"],
    )
```

## Passo 20 — Substituir integralmente `workers/worker_flow/response_flow/flow_sender.py`

```python
import logging
from workers.worker_flow.fireads import email_importado, classificar_tratamento_abertura
from core.integrations.whatsapp.pywa_functions.pywa_senders.etapa4 import enviar_abertura_fireads

from core.integrations.whatsapp.messages.componentes_compartilhados import (
    montar_texto_com_cabecalho,
)

from core.integrations.whatsapp.pywa_functions.cliente import (
    aplicar_prefixo_mensagem_bot,
    usar_prefixo_mensagem_bot,
)
from workers.worker_flow.response_flow.etapas.resolver_etapa1 import (
    resolve_etapa1,
)
from workers.worker_flow.response_flow.etapas.resolver_etapa2 import (
    resolve_etapa2,
)
from workers.worker_flow.response_flow.etapas.resolver_etapa3 import (
    resolve_etapa3,
)
from workers.worker_flow.response_flow.etapas.resolver_etapa4 import (
    resolve_etapa4,
)
from workers.worker_flow.response_flow.etapas.resolver_etapa5 import (
    resolve_etapa5,
)
from workers.worker_flow.response_flow.etapas.resolver_etapa6 import (
    resolve_etapa6,
)
from workers.worker_flow.response_flow.etapas.resolver_etapa7 import (
    resolve_etapa7,
)
from workers.worker_flow.response_flow.etapas.resolver_etapa8 import (
    resolve_etapa8,
)
from workers.worker_flow.response_flow.etapas.resolver_etapa9 import (
    resolve_etapa9,
)
from workers.worker_flow.response_flow.etapas.resolver_etapa10 import (
    resolve_etapa10,
)
from workers.worker_flow.response_flow.etapas.resolver_etapa11 import (
    resolve_etapa11,
)
from workers.worker_flow.response_flow.etapas.resolver_etapa12 import (
    resolve_etapa12,
)
from workers.worker_flow.response_flow.etapas.resolver_etapa13 import (
    resolve_etapa13,
)
from workers.worker_flow.response_flow.etapas.resolver_etapa14 import (
    resolve_etapa14,
)
from workers.worker_flow.response_flow.etapas.resolver_etapa15 import (
    resolve_etapa15,
)
from workers.worker_flow.response_flow.etapas.resolver_etapa16 import (
    resolve_etapa16,
)
from workers.worker_flow.response_flow.etapas.resolver_etapa17 import (
    resolve_etapa17,
)
from workers.worker_flow.response_flow.etapas.resolver_etapa18 import (
    resolve_etapa18,
)
from workers.worker_flow.response_flow.etapas.resolver_etapa19 import (
    resolve_etapa19,
)
from workers.worker_flow.response_flow.etapas.resolver_etapa20 import (
    resolve_etapa20,
)
from workers.worker_flow.response_flow.etapas.resolver_etapa21 import (
    resolve_etapa21,
)
from workers.worker_flow.response_flow.etapas.resolver_etapa22 import (
    resolve_etapa22,
)
from workers.worker_flow.response_flow.etapas.resolver_etapa23 import (
    resolve_etapa23,
)
from workers.worker_flow.response_flow.transicoes.resolver_transicao import (
    identificar_evento_por_destino,
)
from workers.worker_flow.response_flow.transicoes.eventos import (
    ETAPA_3_CONFIRMACAO_DESTINO,
    EVENTO_DESTINO_ATENDIMENTO_CONFIRMADO,
)


logger = logging.getLogger("worker.sender")


def flow_sender(contexto_historico):
    id_conversa = contexto_historico["id_conversa"]
    id_etapa_atual = contexto_historico.get("id_etapa_atual")
    retry_count = contexto_historico["retry_count"]

    mensagem_cliente_atual = contexto_historico["mensagem_cliente_atual"]
    cliente_atual_id_mensagem_fila = mensagem_cliente_atual["id_mensagem_fila"]
    cliente_atual_id_hash_msg = mensagem_cliente_atual["id_hash_msg"]

    resposta_bot_atual = (
        contexto_historico["resposta_bot_para_mensagem_atual"] or {}
    )

    # Esta barreira continua antes de qualquer resolver ou sender.
    if resposta_bot_atual:
        id_etapa_resposta = resposta_bot_atual.get("id_etapa")
        evento_transicao = identificar_evento_por_destino(
            contexto_historico,
            id_etapa_resposta,
        )

        logger.info(
            "flow_sender_idempotencia_ok | motivo=resposta_bot_ja_registrada acao=nao_enviar id_conversa=%s id_mensagem_fila=%s id_hash_cliente=%s id_resposta_bot=%s etapa_resposta=%s evento_transicao=%s retry=%s",
            id_conversa,
            cliente_atual_id_mensagem_fila,
            cliente_atual_id_hash_msg,
            resposta_bot_atual.get("id_mensagem"),
            id_etapa_resposta,
            evento_transicao,
            retry_count,
        )

        contexto_envio = {
            "enviou": False,
            "resposta_ja_existia": True,
            "id_hash_msg_bot": resposta_bot_atual.get("id_hash_msg"),
            "id_etapa_resultante": id_etapa_resposta,
            "id_etapa_origem_transicao": contexto_historico.get(
                "id_etapa_origem_transicao"
            ),
        }

        if evento_transicao:
            contexto_envio["evento_transicao"] = evento_transicao

        # Movimento e efeito são confirmados na mesma transação. No replay da
        # etapa 3, o status atual da conversa já é o valor final absoluto; não
        # reinterpretamos "Não" nem reaplicamos uma inversão.
        if (
            contexto_historico.get("id_etapa_origem_transicao")
            == ETAPA_3_CONFIRMACAO_DESTINO
            and evento_transicao
            == EVENTO_DESTINO_ATENDIMENTO_CONFIRMADO
        ):
            status_dependente_final = contexto_historico.get(
                "status_dependente"
            )
            if not isinstance(status_dependente_final, bool):
                raise ValueError(
                    "Replay da confirmacao da etapa 3 sem "
                    "status_dependente booleano persistido "
                    f"(valor={status_dependente_final!r})"
                )
            contexto_envio["status_dependente_final"] = (
                status_dependente_final
            )

        return contexto_envio

    if retry_count > 1:
        logger.info(
            "flow_sender_reprocessamento | motivo=retry_maior_que_um acao=continuar_sem_resposta_previa id_conversa=%s id_mensagem_fila=%s id_hash_cliente=%s retry=%s",
            id_conversa,
            cliente_atual_id_mensagem_fila,
            cliente_atual_id_hash_msg,
            retry_count,
        )

    if id_etapa_atual is None and email_importado(contexto_historico):
        return enviar_abertura_fireads(
            contexto_historico,
            tratamento=classificar_tratamento_abertura(contexto_historico),
        )

    if id_etapa_atual is None or id_etapa_atual == 1:
        return _resolver_com_saudacao(resolve_etapa1, contexto_historico)

    if id_etapa_atual == 2:
        return _resolver_com_saudacao(
            resolve_etapa2,
            contexto_historico,
        )

    if id_etapa_atual == 3:
        return _resolver_com_saudacao(
            resolve_etapa3,
            contexto_historico,
        )

    if id_etapa_atual == 4:
        return _resolver_com_saudacao(
            resolve_etapa4,
            contexto_historico,
        )

    if id_etapa_atual == 5:
        return _resolver_com_saudacao(
            resolve_etapa5,
            contexto_historico,
        )

    if id_etapa_atual == 6:
        return _resolver_com_saudacao(
            resolve_etapa6,
            contexto_historico,
        )

    if id_etapa_atual == 7:
        return _resolver_com_saudacao(
            resolve_etapa7,
            contexto_historico,
        )

    if id_etapa_atual == 8:
        return _resolver_com_saudacao(
            resolve_etapa8,
            contexto_historico,
        )

    if id_etapa_atual == 9:
        return _resolver_com_saudacao(
            resolve_etapa9,
            contexto_historico,
        )

    if id_etapa_atual == 10:
        return _resolver_com_saudacao(
            resolve_etapa10,
            contexto_historico,
        )

    if id_etapa_atual == 11:
        return _resolver_com_saudacao(
            resolve_etapa11,
            contexto_historico,
        )

    if id_etapa_atual == 12:
        return _resolver_com_saudacao(
            resolve_etapa12,
            contexto_historico,
        )

    if id_etapa_atual == 13:
        return _resolver_com_saudacao(
            resolve_etapa13,
            contexto_historico,
        )

    if id_etapa_atual == 14:
        return _resolver_com_saudacao(
            resolve_etapa14,
            contexto_historico,
        )

    if id_etapa_atual == 15:
        return _resolver_com_saudacao(
            resolve_etapa15,
            contexto_historico,
        )

    if id_etapa_atual == 16:
        return _resolver_com_saudacao(
            resolve_etapa16,
            contexto_historico,
        )

    if id_etapa_atual == 17:
        return _resolver_com_saudacao(
            resolve_etapa17,
            contexto_historico,
        )

    if id_etapa_atual == 18:
        return _resolver_com_saudacao(
            resolve_etapa18,
            contexto_historico,
        )

    if id_etapa_atual == 19:
        return _resolver_com_saudacao(
            resolve_etapa19,
            contexto_historico,
        )

    if id_etapa_atual == 20:
        return _resolver_com_saudacao(
            resolve_etapa20,
            contexto_historico,
        )

    if id_etapa_atual == 21:
        return _resolver_com_saudacao(
            resolve_etapa21,
            contexto_historico,
        )

    if id_etapa_atual == 22:
        return _resolver_com_saudacao(
            resolve_etapa22,
            contexto_historico,
        )

    if id_etapa_atual == 23:
        return _resolver_com_saudacao(
            resolve_etapa23,
            contexto_historico,
        )

    # A etapa 24 é terminal e não possui resolver. Conversas encerradas são
    # barradas pelo cache/webhook e pelo fallback transacional do worker.

    logger.warning(
        "flow_sender_etapa_pendente | acao=nao_enviar id_conversa=%s etapa=%s",
        id_conversa,
        id_etapa_atual,
    )
    raise NotImplementedError(
        f"Sender da etapa atual {id_etapa_atual} ainda nao implementado"
    )


def _resolver_com_saudacao(resolver, contexto_historico):
    """Aplica a saudação sem alterar o despacho legado das etapas."""
    saudacao_retorno = contexto_historico.get("saudacao_retorno")

    with usar_prefixo_mensagem_bot(saudacao_retorno):
        contexto_envio = resolver(contexto_historico)

    if saudacao_retorno and contexto_envio.get("mensagem_bot"):
        contexto_envio = dict(contexto_envio)
        texto = contexto_envio["mensagem_bot"]
        if contexto_envio.get("cabecalho_mensagem"):
            # O sender enviou este cabeçalho no corpo, antes de aplicar o prefixo.
            # O histórico deve refletir exatamente a mesma ordem do WhatsApp.
            texto = montar_texto_com_cabecalho(
                texto, contexto_envio["cabecalho_mensagem"]
            )
        contexto_envio["mensagem_bot"] = aplicar_prefixo_mensagem_bot(
            texto,
            saudacao_retorno,
        )
        contexto_envio["saudacao_retorno_aplicada"] = True

    return contexto_envio
```

## Passo 21 — Substituir integralmente `workers/worker_flow/response_flow/flow_worker.py`

```python
import logging
from workers.worker_flow.fireads import preparar_abertura

import psycopg
from core.cache.cache_unidade import UnidadeNaoEncontrada
from core.database.connection_aws import get_conn
from core.integrations.whatsapp.exceptions import ErroEnvioMeta
from core.logging_config import short_value
from core.repositories.atendimento.conversas import tentar_lock_conversa
from core.repositories.atendimento.followup import (
    LockConversaPerdido,
    proteger_conversa,
    reler_conversa,
)
from workers.worker_flow.response_flow.retomada_followup import (
    enviar_retorno_followup,
)
from workers.worker_flow.transacoes.retorno_followup import (
    preparar_retorno_followup,
    persistir_retorno_followup,
)
from core.repositories.atendimento.fila import (
    pegar_mensagens_da_fila,
    reagendar_mensagem_sem_erro,
    vincular_mensagem_fila_a_conversa,
)
from workers.tratamento_erros_externos.erro_conexao import handle_erro_conexao
from workers.tratamento_erros_externos.erro_generico import handle_erro_generico
from workers.tratamento_erros_externos.exceptions import BancoFalhouAposEnvioMeta
from workers.tratamento_erros_externos.unidade_nao_encontrada import (
    handle_unidade_nao_encontrada,
)
from workers.worker_flow.response_flow.flow_sender import flow_sender
from workers.worker_flow.suporte.cache_repair import (
    confirmar_cache_cliente_se_pendente,
    reparar_cache_cliente_stale_se_fk_invalida,
    reparar_cache_unidade_stale_se_fk_invalida,
)
from workers.worker_flow.suporte.estado_ciclo import (
    aguardar_fila_vazia,
    atualizar_estado_com_contexto,
    atualizar_estado_com_mensagem,
    atualizar_estado_lock,
    criar_estado_ciclo,
    montar_mensagem_fila,
)
from workers.worker_flow.transacoes.finalizacao_fila import (
    finalizar_mensagem_processada,
    registrar_cache_bloqueio_apos_commit,
)
from workers.worker_flow.transacoes.lock_conversa import (
    liberar_lock_conversa_se_necessario,
)
from workers.worker_flow.transacoes.ordem_turno import (
    logar_lock_recusado,
    reagendar_se_houver_mensagem_anterior,
)
from workers.worker_flow.transacoes.persistencia_resposta import (
    atualizar_banco_com_contexto_final,
)
from workers.worker_flow.tratar_bloqueio import tratar_conversa_bloqueada
from workers.worker_flow.valida_banco import validar_banco_mensagem
from workers.worker_flow.valida_historico import valida_historico

logger = logging.getLogger("worker.response_flow")


def worker_flow():
    logger.info("worker_iniciado")

    max_retry = 3
    retry_delay = 5

    while True:
        print("\n\n\n---------------------NOVO CICLO---------------------\n\n\n")
        logger.info("---------- ciclo_worker_inicio ----------")

        conn_ciclo = None
        cursor_ciclo = None
        estado_ciclo = criar_estado_ciclo()
        contexto_envio = {}

        try:
            conn_ciclo = get_conn(application_name="worker_chatbot")
            cursor_ciclo = conn_ciclo.cursor()
            retry_delay = 5
            logger.debug("ciclo_conexao_banco_ok | acao=dequeue")

            registro = pegar_mensagens_da_fila(cursor_ciclo)
            conn_ciclo.commit()

            if not registro:
                conn_ciclo.close()
                conn_ciclo = None
                cursor_ciclo = None
                aguardar_fila_vazia()
                continue

            mensagem = montar_mensagem_fila(registro)
            atualizar_estado_com_mensagem(estado_ciclo, mensagem)

            logger.info(
                "mensagem_processando | acao=iniciar id_mensagem=%s cliente=%s phone_number_id=%s tipo=%s retry=%s",
                mensagem["id_mensagem"],
                short_value(mensagem["cliente_telefone"]),
                short_value(mensagem["id_phone_unidade"]),
                mensagem["tipo_mensagem"],
                mensagem["retry_count"],
            )

            if reagendar_se_houver_mensagem_anterior(
                mensagem,
                cursor_ciclo,
            ):
                conn_ciclo.commit()
                continue

            contexto_banco = validar_banco_mensagem(
                mensagem,
                cursor_ciclo,
            )
            atualizar_estado_com_contexto(estado_ciclo, contexto_banco)

            contexto_conversa = contexto_banco["conversa"]
            id_conversa = contexto_conversa["id_conversa"]

            conn_ciclo.commit()
            logger.debug(
                "contexto_banco_confirmado | acao=commit id_mensagem=%s id_conversa_calculada=%s estado=%s",
                mensagem["id_mensagem"],
                id_conversa,
                contexto_conversa["estado"],
            )

            confirmar_cache_cliente_se_pendente(contexto_banco)

            if contexto_conversa["estado"] == "bloqueada":
                tratar_conversa_bloqueada(
                    mensagem["id_mensagem"],
                    mensagem["cliente_telefone"],
                    mensagem["id_phone_unidade"],
                    id_conversa,
                    cursor_ciclo,
                )
                conn_ciclo.commit()
                continue

            lock_ok, lock_version = tentar_lock_conversa(id_conversa, cursor_ciclo)
            conn_ciclo.commit()
            atualizar_estado_lock(estado_ciclo, lock_ok, lock_version)

            if not lock_ok:
                logar_lock_recusado(mensagem, contexto_banco)
                reagendar_mensagem_sem_erro(
                    mensagem["id_mensagem"],
                    cursor_ciclo,
                    delay_seconds=5,
                )
                conn_ciclo.commit()
                continue

            linhas_vinculadas = vincular_mensagem_fila_a_conversa(
                mensagem["id_mensagem"],
                id_conversa,
                cursor_ciclo,
            )

            if linhas_vinculadas == 0:
                logger.critical(
                    "mensagem_conversa_vinculo_inconsistente | "
                    "motivo=historico_conflitante_ou_fila_ausente "
                    "acao=reagendar_sem_consumir_retry id_mensagem=%s "
                    "cliente=%s phone_number_id=%s "
                    "id_conversa_calculada=%s",
                    mensagem["id_mensagem"],
                    short_value(mensagem["cliente_telefone"]),
                    short_value(mensagem["id_phone_unidade"]),
                    id_conversa,
                )
                reagendar_mensagem_sem_erro(
                    mensagem["id_mensagem"],
                    cursor_ciclo,
                    delay_seconds=300,
                )
                conn_ciclo.commit()
                continue

            contexto_banco = reler_conversa(contexto_banco, lock_version, cursor_ciclo)
            contexto_banco = preparar_abertura(
                contexto_banco, mensagem, lock_version, conn_ciclo, cursor_ciclo
            )
            contexto_conversa = contexto_banco["conversa"]
            contexto_historico = preparar_retorno_followup(
                mensagem,
                contexto_banco,
                cursor_ciclo,
            )
            if contexto_historico is None:
                contexto_historico = valida_historico(
                    mensagem, contexto_banco, cursor_ciclo
                )
            conn_ciclo.commit()
            logger.debug(
                "historico_contexto_ok | acao=commit id_mensagem=%s id_conversa=%s etapa_cliente=%s etapa_resposta=%s inserido=%s",
                mensagem["id_mensagem"],
                id_conversa,
                contexto_historico["id_etapa_cliente"],
                contexto_historico["id_etapa_resposta"],
                contexto_historico["mensagem_cliente_inserida"],
            )

            proteger_conversa(id_conversa, lock_version, cursor_ciclo, renovar=True)
            conn_ciclo.commit()
            if contexto_historico.get("retorno_followup"):
                contexto_envio = enviar_retorno_followup(contexto_historico)
            else:
                contexto_envio = flow_sender(contexto_historico)

            try:
                proteger_conversa(id_conversa, lock_version, cursor_ciclo)
                persistir = (
                    persistir_retorno_followup
                    if contexto_historico.get("retorno_followup")
                    else atualizar_banco_com_contexto_final
                )
                contexto_final = persistir(
                    contexto_historico, contexto_envio, cursor_ciclo
                )
                if contexto_historico.get("retorno_followup"):
                    # O retorno agora pode encerrar por idade ou finalizar o fluxo.
                    # Histórico, efeitos, stage=0, encerramento e fila são atômicos:
                    # um retry não pode encontrar um checkpoint concluído sem
                    # que o encerramento correspondente também esteja confirmado.
                    resultado_encerramento = finalizar_mensagem_processada(
                        mensagem,
                        contexto_banco,
                        lock_version,
                        cursor_ciclo,
                        contexto_final,
                    )
                conn_ciclo.commit()

            except Exception as erro:
                if contexto_envio.get("enviou"):
                    raise BancoFalhouAposEnvioMeta(
                        "Banco falhou depois da Meta confirmar envio",
                        id_mensagem=mensagem["id_mensagem"],
                        id_conversa=id_conversa,
                        id_hash_msg_bot=contexto_envio.get("id_hash_msg_bot"),
                        id_etapa=contexto_envio.get("id_etapa_resultante"),
                    ) from erro

                raise

            logger.debug(
                "resposta_bot_contexto_final_ok | acao=commit id_mensagem=%s id_conversa=%s etapa=%s resposta_ja_existia=%s id_hash_msg_bot=%s tratamento=%s tipo_tratamento=%s",
                mensagem["id_mensagem"],
                id_conversa,
                contexto_final["id_etapa_resultante"],
                contexto_final["resposta_ja_existia"],
                contexto_final["id_hash_msg_bot"],
                contexto_envio.get("tratamento", False),
                contexto_envio.get("tipo_tratamento"),
            )

            if not contexto_historico.get("retorno_followup"):
                proteger_conversa(id_conversa, lock_version, cursor_ciclo)
                resultado_encerramento = finalizar_mensagem_processada(
                    mensagem,
                    contexto_banco,
                    lock_version,
                    cursor_ciclo,
                    contexto_final,
                )
                conn_ciclo.commit()

            registrar_cache_bloqueio_apos_commit(
                mensagem,
                resultado_encerramento,
            )

        except LockConversaPerdido:
            if conn_ciclo:
                conn_ciclo.rollback()
            # Não reescreve uma fila que pode estar sendo processada pelo novo dono.
            logger.warning(
                "lock_perdido | acao=aguardar_recuperacao_fila id_conversa=%s",
                estado_ciclo["id_conversa"],
            )

        except ErroEnvioMeta as erro:
            logger.warning(
                "meta_envio_erro | acao=reagendar_sem_sent id_mensagem=%s cliente=%s phone_number_id=%s etapa=%s erro=%s",
                estado_ciclo["id_mensagem"],
                short_value(estado_ciclo["cliente_telefone"]),
                short_value(estado_ciclo["id_phone_unidade"]),
                erro.id_etapa,
                erro,
            )
            if conn_ciclo:
                conn_ciclo.rollback()

            handle_erro_generico(
                cursor_ciclo,
                estado_ciclo["id_mensagem"],
                erro,
                max_retry,
            )

            if conn_ciclo:
                conn_ciclo.commit()

        except BancoFalhouAposEnvioMeta as erro:
            if isinstance(erro.__cause__, LockConversaPerdido):
                conn_ciclo.rollback()
                logger.critical(
                    "meta_confirmou_com_lock_perdido | conversa=%s hash=%s risco=duplicidade",
                    erro.id_conversa,
                    erro.id_hash_msg_bot,
                )
                continue
            logger.critical(
                "banco_falhou_apos_envio_meta | risco=resposta_duplicada acao=reagendar_sem_sent id_mensagem=%s id_conversa=%s etapa=%s id_hash_msg_bot=%s tratamento=%s tipo_tratamento=%s erro=%s",
                erro.id_mensagem,
                erro.id_conversa,
                erro.id_etapa,
                erro.id_hash_msg_bot,
                contexto_envio.get("tratamento", False),
                contexto_envio.get("tipo_tratamento"),
                erro,
            )
            if conn_ciclo:
                conn_ciclo.rollback()

            handle_erro_generico(
                cursor_ciclo,
                estado_ciclo["id_mensagem"],
                erro,
                max_retry,
            )

            if conn_ciclo:
                conn_ciclo.commit()

        except psycopg.OperationalError as erro:
            logger.warning(
                "banco_operacional_erro | acao=retry_conexao id_mensagem=%s erro=%s",
                estado_ciclo["id_mensagem"],
                erro,
            )
            retry_delay = handle_erro_conexao(erro, retry_delay)
            continue

        except UnidadeNaoEncontrada as erro:
            logger.warning(
                "unidade_nao_encontrada | acao=tratar_unidade_invalida id_mensagem=%s cliente=%s phone_number_id=%s erro=%s",
                estado_ciclo["id_mensagem"],
                short_value(estado_ciclo["cliente_telefone"]),
                short_value(estado_ciclo["id_phone_unidade"]),
                erro,
            )
            if conn_ciclo:
                conn_ciclo.rollback()

            handle_unidade_nao_encontrada(
                cursor_ciclo,
                estado_ciclo["id_mensagem"],
                erro,
            )

            if conn_ciclo:
                conn_ciclo.commit()

        except Exception as erro:
            logger.exception(
                "mensagem_erro | acao=tratar_erro_generico id_mensagem=%s cliente=%s phone_number_id=%s id_conversa=%s estado=%s erro=%s",
                estado_ciclo["id_mensagem"],
                short_value(estado_ciclo["cliente_telefone"]),
                short_value(estado_ciclo["id_phone_unidade"]),
                estado_ciclo["id_conversa"],
                estado_ciclo["estado"],
                erro,
            )
            if conn_ciclo:
                conn_ciclo.rollback()

            reparar_cache_cliente_stale_se_fk_invalida(erro, estado_ciclo)
            reparar_cache_unidade_stale_se_fk_invalida(erro, estado_ciclo)

            handle_erro_generico(
                cursor_ciclo,
                estado_ciclo["id_mensagem"],
                erro,
                max_retry,
            )

            if conn_ciclo:
                conn_ciclo.commit()

        finally:
            if conn_ciclo:
                try:
                    unlock_realizado = liberar_lock_conversa_se_necessario(
                        cursor_ciclo,
                        estado_ciclo,
                    )

                    if unlock_realizado is not None:
                        conn_ciclo.commit()

                except Exception as erro:
                    logger.exception(
                        "finalizacao_ciclo_falhou | acao=continuar_para_close erro=%s",
                        erro,
                    )

                finally:
                    try:
                        conn_ciclo.close()

                    except Exception as erro:
                        logger.exception(
                            "conexao_ciclo_close_falhou | acao=registrar_e_continuar erro=%s",
                            erro,
                        )
```

## Passo 22 — Substituir integralmente `workers/worker_flow/transacoes/efeitos_transicao.py`

```python
import logging
from workers.worker_flow.fireads import email_importado

from core.repositories.atendimento.turnos import salvar_turno_conversa
from workers.worker_flow.response_flow.etapas.validadores_contexto.valida_etapa18 import validar_etapa18

from core.logging_config import short_value
from core.repositories.atendimento.clientes import (
    atualizar_email_cliente,
    atualizar_idade_cliente,
    atualizar_nome_cliente_por_telefone,
    atualizar_profissao_cliente,
)
from core.repositories.atendimento.conversas import (
    atualizar_profissao_conversa,
    atualizar_status_dependente_conversa,
)
from core.repositories.atendimento.dependentes import (
    atualizar_idade_dependente,
    atualizar_nome_dependente_por_conversa,
    inserir_dependente_para_conversa,
    remover_dependente_placeholder_da_conversa,
)
from core.repositories.fluxo.triagem import registrar_resposta_triagem
from core.repositories.fluxo.pesquisa_satisfacao import (
    salvar_comentario_satisfacao,
    salvar_nota_satisfacao,
)
from workers.worker_flow.response_flow.etapas.validadores_contexto.valida_etapa21 import (
    validar_etapa21,
)
from workers.worker_flow.response_flow.etapas.validadores_contexto.valida_etapa22 import (
    TIPOS_MENSAGEM_ACEITOS_ETAPA22,
)
from workers.worker_flow.response_flow.etapas.validadores_contexto.valida_etapa23 import (
    normalizar_comentario_etapa23,
)
from workers.worker_flow.response_flow.etapas.validadores_universais.validador_nome import (
    validar_nome_cliente,
)
from workers.worker_flow.response_flow.etapas.validadores_universais.validador_triagem import (
    validar_resposta_triagem,
)
from workers.worker_flow.response_flow.etapas.validadores_contexto.valida_etapa6 import (
    validar_idade,
)
from workers.worker_flow.response_flow.etapas.validadores_contexto.valida_etapa2 import (
    OPCAO_PARA_OUTRA_PESSOA,
    validar_etapa2,
)
from workers.worker_flow.response_flow.etapas.validadores_contexto.valida_etapa4 import (
    validar_profissao_etapa4,
)
from workers.worker_flow.response_flow.etapas.validadores_contexto.valida_etapa10 import (
    CLASSIFICACAO_EMAIL_AUSENTE,
    CLASSIFICACAO_EMAIL_NAO_INFORMADO,
    CLASSIFICACAO_EMAIL_VALIDO,
    calcular_email_obrigatorio_efetivo,
    classificar_resposta_email,
    classificar_resposta_email_aceita,
    validar_etapa10,
)
from workers.worker_flow.response_flow.transicoes.eventos import (
    ETAPA_1_NOME_CLIENTE,
    ETAPA_2_DESTINO_ATENDIMENTO,
    ETAPA_3_CONFIRMACAO_DESTINO,
    ETAPA_4_PROFISSAO,
    ETAPA_5_NOME_DEPENDENTE,
    ETAPA_6_IDADE_ALUNO,
    ETAPA_7_OFERTA_AULA,
    ETAPA_8_OFERTA_ADIADA,
    ETAPA_9_RETORNO_OFERTA,
    ETAPA_10_EMAIL,
    ETAPA_11_INTRODUCAO_TRIAGEM,
    ETAPA_12_TRIAGEM_PERGUNTA_1,
    ETAPA_13_TRIAGEM_PERGUNTA_2,
    ETAPA_14_TRIAGEM_PERGUNTA_3,
    ETAPA_15_TRIAGEM_PERGUNTA_4,
    ETAPA_16_TRIAGEM_PERGUNTA_5,
    ETAPA_17_TRIAGEM_PERGUNTA_6,
    ETAPA_18_ESCOLHA_TURNO,
    ETAPA_19_ENCAMINHAMENTO_COMERCIAL,
    EVENTO_TRIAGEM_CONCLUIDA_SEM_LINK,
    EVENTO_TURNO_ESCOLHIDO,
    EVENTO_AVALIACAO_SOLICITADA,
    ETAPA_20_AGENDAMENTO,
    ETAPA_21_PESQUISA_SATISFACAO,
    ETAPA_22_DECISAO_COMENTARIO,
    ETAPA_23_COMENTARIO_SATISFACAO,
    ETAPA_24_FINALIZACAO,
    EVENTO_AGENDAMENTO_CONFIRMADO,
    EVENTO_CLIENTE_RETORNOU,
    EVENTO_COMENTARIO_SATISFACAO_ACEITO,
    EVENTO_COMENTARIO_SATISFACAO_RECUSADO,
    EVENTO_COMENTARIO_SATISFACAO_RECEBIDO,
    EVENTO_DESTINO_ATENDIMENTO_DEFINIDO,
    EVENTO_DESTINO_ATENDIMENTO_CONFIRMADO,
    EVENTO_EMAIL_VALIDO,
    EVENTO_IDADE_VALIDA,
    EVENTO_NOME_CLIENTE_VALIDO,
    EVENTO_NOME_DEPENDENTE_VALIDO,
    EVENTO_OFERTA_ACEITA,
    EVENTO_OFERTA_ADIADA,
    EVENTO_PROFISSAO_DEPENDENTE_VALIDA,
    EVENTO_PROFISSAO_TITULAR_VALIDA,
    EVENTO_RETORNO_ADIADO,
    EVENTO_RETORNO_CONFIRMADO,
    EVENTO_SATISFACAO_AVALIADA,
    EVENTO_TRIAGEM_INICIADA,
    EVENTO_TRIAGEM_PERGUNTA_1_RESPONDIDA,
    EVENTO_TRIAGEM_PERGUNTA_2_RESPONDIDA,
    EVENTO_TRIAGEM_PERGUNTA_3_RESPONDIDA,
    EVENTO_TRIAGEM_PERGUNTA_4_RESPONDIDA,
    EVENTO_TRIAGEM_PERGUNTA_5_RESPONDIDA,
    EVENTO_TRIAGEM_PERGUNTA_6_RESPONDIDA,
)


logger = logging.getLogger("worker.support")

MOTIVO_ENCAMINHAMENTO_SUPORTE_IDOSO = "encaminhado_suporte_idoso"


def atualizar_banco_conforme_transicao_de_etapa(
    contexto_historico,
    contexto_envio,
    cursor,
):
    """
    Aplica somente os efeitos de negócio da aresta já autorizada.

    A navegação é definida pelo mapa etapa_transicao e persistida antes desta
    função. Os ifs abaixo tornam explícito o efeito de cada origem + evento.
    """
    etapa_origem = contexto_historico.get(
        "id_etapa_origem_transicao"
    )
    evento = contexto_envio.get("evento_transicao")
    etapa_destino = contexto_envio.get("id_etapa_resultante")

    if (
        etapa_origem == ETAPA_6_IDADE_ALUNO
        and contexto_envio.get("encerrar_atendimento")
        and contexto_envio.get("motivo_encerramento")
        == MOTIVO_ENCAMINHAMENTO_SUPORTE_IDOSO
    ):
        return _persistir_idade_encaminhamento_suporte_idoso(
            contexto_historico,
            contexto_envio,
            cursor,
        )

    if (etapa_origem, evento) in {
        (7, 'oferta_aceita_email_fireads'), (9, 'retorno_confirmado_email_fireads')
    }:
        if etapa_destino != 11 or not email_importado(contexto_historico):
            raise ValueError('Salto de email FireAds sem coleta completa nesta conversa')
        return {'email_fireads_reaproveitado': True}

    # Sem evento não existe transição nem efeito específico de etapa.
    if not evento:
        return None

    # ETAPA 1
    if etapa_origem == ETAPA_1_NOME_CLIENTE:
        # 1 -> 2: o cliente informou o próprio nome.
        if evento == EVENTO_NOME_CLIENTE_VALIDO:
            _exigir_destino(
                etapa_origem,
                evento,
                etapa_destino,
                ETAPA_2_DESTINO_ATENDIMENTO,
            )
            return _persistir_nome_cliente_capturado_na_etapa1(
                contexto_historico,
                contexto_envio,
                cursor,
            )

    # ETAPA 2
    if etapa_origem == ETAPA_2_DESTINO_ATENDIMENTO:
        # 2 -> 3: a opção foi validada e aguarda confirmação explícita.
        if evento == EVENTO_DESTINO_ATENDIMENTO_DEFINIDO:
            _exigir_destino(
                etapa_origem,
                evento,
                etapa_destino,
                ETAPA_3_CONFIRMACAO_DESTINO,
            )
            return _persistir_destino_atendimento_da_etapa2(
                contexto_historico,
                contexto_envio,
                etapa_destino,
                cursor=cursor,
            )

    # ETAPA 3
    if etapa_origem == ETAPA_3_CONFIRMACAO_DESTINO:
        if evento == EVENTO_DESTINO_ATENDIMENTO_CONFIRMADO:
            _exigir_destino(
                etapa_origem,
                evento,
                etapa_destino,
                ETAPA_4_PROFISSAO,
            )
            return _persistir_confirmacao_destino_da_etapa3(
                contexto_historico,
                contexto_envio,
                cursor,
            )

    # ETAPA 4
    if etapa_origem == ETAPA_4_PROFISSAO:
        if evento == EVENTO_PROFISSAO_DEPENDENTE_VALIDA:
            _exigir_destino(
                etapa_origem,
                evento,
                etapa_destino,
                ETAPA_5_NOME_DEPENDENTE,
            )
            return _persistir_profissao_capturada_na_etapa4(
                contexto_historico,
                contexto_envio,
                cursor,
                status_dependente_esperado=True,
            )

        if evento == EVENTO_PROFISSAO_TITULAR_VALIDA:
            _exigir_destino(
                etapa_origem,
                evento,
                etapa_destino,
                ETAPA_6_IDADE_ALUNO,
            )
            return _persistir_profissao_capturada_na_etapa4(
                contexto_historico,
                contexto_envio,
                cursor,
                status_dependente_esperado=False,
            )

    # ETAPA 5
    if etapa_origem == ETAPA_5_NOME_DEPENDENTE:
        # 5 -> 6: o cliente informou o nome do dependente.
        if evento == EVENTO_NOME_DEPENDENTE_VALIDO:
            _exigir_destino(
                etapa_origem,
                evento,
                etapa_destino,
                ETAPA_6_IDADE_ALUNO,
            )
            return _persistir_nome_dependente_capturado_na_etapa5(
                contexto_historico,
                contexto_envio,
                cursor,
            )

    # ETAPA 6
    if etapa_origem == ETAPA_6_IDADE_ALUNO:
        # 6 -> 7: a idade do aluno foi validada.
        if evento == EVENTO_IDADE_VALIDA:
            _exigir_destino(
                etapa_origem,
                evento,
                etapa_destino,
                ETAPA_7_OFERTA_AULA,
            )
            return _persistir_idade_capturada_na_etapa6(
                contexto_historico,
                contexto_envio,
                cursor,
            )

    # ETAPA 7
    if etapa_origem == ETAPA_7_OFERTA_AULA:
        # 7 -> 10: o cliente aceitou agendar.
        if evento == EVENTO_OFERTA_ACEITA:
            _exigir_destino(
                etapa_origem,
                evento,
                etapa_destino,
                ETAPA_10_EMAIL,
            )
            return _confirmar_decisao_oferta_da_etapa7(
                contexto_historico,
                evento,
                etapa_destino,
            )

        # 7 -> 8: o cliente preferiu adiar.
        if evento == EVENTO_OFERTA_ADIADA:
            _exigir_destino(
                etapa_origem,
                evento,
                etapa_destino,
                ETAPA_8_OFERTA_ADIADA,
            )
            return _confirmar_decisao_oferta_da_etapa7(
                contexto_historico,
                evento,
                etapa_destino,
            )

    # ETAPA 8
    if etapa_origem == ETAPA_8_OFERTA_ADIADA:
        # 8 -> 9: o cliente enviou uma nova mensagem após adiar a oferta.
        if evento == EVENTO_CLIENTE_RETORNOU:
            _exigir_destino(
                etapa_origem,
                evento,
                etapa_destino,
                ETAPA_9_RETORNO_OFERTA,
            )
            return _confirmar_retorno_cliente_da_etapa8(
                contexto_historico,
                evento,
                etapa_destino,
            )

    # ETAPA 9
    if etapa_origem == ETAPA_9_RETORNO_OFERTA:
        # 9 -> 10: o cliente retomou e confirmou o agendamento.
        if evento == EVENTO_RETORNO_CONFIRMADO:
            _exigir_destino(
                etapa_origem,
                evento,
                etapa_destino,
                ETAPA_10_EMAIL,
            )
            return _confirmar_decisao_retorno_da_etapa9(
                contexto_historico,
                evento,
                etapa_destino,
            )

        # 9 -> 8: o cliente preferiu adiar novamente.
        if evento == EVENTO_RETORNO_ADIADO:
            _exigir_destino(
                etapa_origem,
                evento,
                etapa_destino,
                ETAPA_8_OFERTA_ADIADA,
            )
            return _confirmar_decisao_retorno_da_etapa9(
                contexto_historico,
                evento,
                etapa_destino,
            )

    # ETAPA 10
    if etapa_origem == ETAPA_10_EMAIL:
        # 10 -> 11: a coleta foi aceita. A aresta técnica legada é única;
        # o resultado semântico distingue endereço, ausência e não informado.
        if evento == EVENTO_EMAIL_VALIDO:
            _exigir_destino(
                etapa_origem,
                evento,
                etapa_destino,
                ETAPA_11_INTRODUCAO_TRIAGEM,
            )
            return _persistir_email_capturado_na_etapa10(
                contexto_historico,
                contexto_envio,
                cursor,
            )

    # ETAPA 11
    if etapa_origem == ETAPA_11_INTRODUCAO_TRIAGEM:
        # 11 -> 12: o cliente iniciou a triagem cognitiva.
        if evento == EVENTO_TRIAGEM_INICIADA:
            _exigir_destino(
                etapa_origem,
                evento,
                etapa_destino,
                ETAPA_12_TRIAGEM_PERGUNTA_1,
            )
            return _confirmar_inicio_triagem_da_etapa11(
                contexto_historico,
                evento,
                etapa_destino,
            )

    # ETAPA 12
    if etapa_origem == ETAPA_12_TRIAGEM_PERGUNTA_1:
        # 12 -> 13: registra a resposta da pergunta 1.
        if evento == EVENTO_TRIAGEM_PERGUNTA_1_RESPONDIDA:
            _exigir_destino(
                etapa_origem,
                evento,
                etapa_destino,
                ETAPA_13_TRIAGEM_PERGUNTA_2,
            )
            return _persistir_resposta_triagem(
                contexto_historico,
                contexto_envio,
                cursor,
            )

    # ETAPA 13
    if etapa_origem == ETAPA_13_TRIAGEM_PERGUNTA_2:
        # 13 -> 14: registra a resposta da pergunta 2.
        if evento == EVENTO_TRIAGEM_PERGUNTA_2_RESPONDIDA:
            _exigir_destino(
                etapa_origem,
                evento,
                etapa_destino,
                ETAPA_14_TRIAGEM_PERGUNTA_3,
            )
            return _persistir_resposta_triagem(
                contexto_historico,
                contexto_envio,
                cursor,
            )

    # ETAPA 14
    if etapa_origem == ETAPA_14_TRIAGEM_PERGUNTA_3:
        # 14 -> 15: registra a resposta da pergunta 3.
        if evento == EVENTO_TRIAGEM_PERGUNTA_3_RESPONDIDA:
            _exigir_destino(
                etapa_origem,
                evento,
                etapa_destino,
                ETAPA_15_TRIAGEM_PERGUNTA_4,
            )
            return _persistir_resposta_triagem(
                contexto_historico,
                contexto_envio,
                cursor,
            )

    # ETAPA 15
    if etapa_origem == ETAPA_15_TRIAGEM_PERGUNTA_4:
        # 15 -> 16: registra a resposta da pergunta 4.
        if evento == EVENTO_TRIAGEM_PERGUNTA_4_RESPONDIDA:
            _exigir_destino(
                etapa_origem,
                evento,
                etapa_destino,
                ETAPA_16_TRIAGEM_PERGUNTA_5,
            )
            return _persistir_resposta_triagem(
                contexto_historico,
                contexto_envio,
                cursor,
            )

    # ETAPA 16
    if etapa_origem == ETAPA_16_TRIAGEM_PERGUNTA_5:
        # 16 -> 17: registra a resposta da pergunta 5.
        if evento == EVENTO_TRIAGEM_PERGUNTA_5_RESPONDIDA:
            _exigir_destino(
                etapa_origem,
                evento,
                etapa_destino,
                ETAPA_17_TRIAGEM_PERGUNTA_6,
            )
            return _persistir_resposta_triagem(
                contexto_historico,
                contexto_envio,
                cursor,
            )

    # ETAPA 17
    if etapa_origem == ETAPA_17_TRIAGEM_PERGUNTA_6:
        destinos = {
            EVENTO_TRIAGEM_PERGUNTA_6_RESPONDIDA: ETAPA_20_AGENDAMENTO,
            EVENTO_TRIAGEM_CONCLUIDA_SEM_LINK: ETAPA_18_ESCOLHA_TURNO,
        }
        if evento in destinos:
            # 17 -> 18 ou 20: as duas rotas preservam a sexta resposta da triagem.
            _exigir_destino(etapa_origem, evento, etapa_destino, destinos[evento])
            return _persistir_resposta_triagem(contexto_historico, contexto_envio, cursor)

    # ETAPA 18
    if etapa_origem == ETAPA_18_ESCOLHA_TURNO and evento == EVENTO_TURNO_ESCOLHIDO:
        # 18 -> 19: salvar o turno no mesmo commit do movimento da conversa.
        _exigir_destino(etapa_origem, evento, etapa_destino, ETAPA_19_ENCAMINHAMENTO_COMERCIAL)
        turno = contexto_envio.get("turno")
        if turno is None:
            # A resposta do bot já persistida dispensa novo envio; a mensagem
            # original contém a preferência necessária para reconstruir o efeito.
            turno = validar_etapa18(
                contexto_historico.get("texto_cliente_atual"),
                contexto_historico.get("tipo_mensagem_atual"),
            )
        return salvar_turno_conversa(
            contexto_historico["id_conversa"], contexto_historico["id_unidade"], turno, cursor,
        )

    # ETAPA 19
    if etapa_origem == ETAPA_19_ENCAMINHAMENTO_COMERCIAL and evento == EVENTO_AVALIACAO_SOLICITADA:
        # 19 -> 21: apenas apresenta a pesquisa, sem salvar uma nota nesta aresta.
        _exigir_destino(etapa_origem, evento, etapa_destino, ETAPA_21_PESQUISA_SATISFACAO)
        return {"pesquisa_apresentada": True}

    # ETAPA 20
    if etapa_origem == ETAPA_20_AGENDAMENTO:
        # 20 -> 21: o cliente confirmou o agendamento e inicia a pesquisa.
        if evento == EVENTO_AGENDAMENTO_CONFIRMADO:
            _exigir_destino(
                etapa_origem,
                evento,
                etapa_destino,
                ETAPA_21_PESQUISA_SATISFACAO,
            )
            return _confirmar_agendamento_da_etapa20(
                contexto_historico,
                evento,
                etapa_destino,
            )

    # ETAPA 21
    if etapa_origem == ETAPA_21_PESQUISA_SATISFACAO:
        # 21 -> 22: registra a nota normalizada da pesquisa de satisfacao.
        if evento == EVENTO_SATISFACAO_AVALIADA:
            _exigir_destino(
                etapa_origem,
                evento,
                etapa_destino,
                ETAPA_22_DECISAO_COMENTARIO,
            )
            return _persistir_nota_satisfacao_da_etapa21(
                contexto_historico,
                contexto_envio,
                cursor,
            )

    # ETAPA 22
    if etapa_origem == ETAPA_22_DECISAO_COMENTARIO:
        # 22 -> 23: confirma que o cliente deseja escrever um comentario.
        if evento == EVENTO_COMENTARIO_SATISFACAO_ACEITO:
            _exigir_destino(
                etapa_origem,
                evento,
                etapa_destino,
                ETAPA_23_COMENTARIO_SATISFACAO,
            )
            return _confirmar_decisao_comentario_da_etapa22(
                contexto_historico,
                evento,
                etapa_destino,
            )

        # 22 -> 24: registra a recusa explicita e encerra o atendimento.
        if evento == EVENTO_COMENTARIO_SATISFACAO_RECUSADO:
            _exigir_destino(
                etapa_origem,
                evento,
                etapa_destino,
                ETAPA_24_FINALIZACAO,
            )
            return _persistir_recusa_comentario_da_etapa22(
                contexto_historico,
                cursor,
            )

    # ETAPA 23
    if etapa_origem == ETAPA_23_COMENTARIO_SATISFACAO:
        # 23 -> 24: registra o comentario livre antes da finalizacao.
        if evento == EVENTO_COMENTARIO_SATISFACAO_RECEBIDO:
            _exigir_destino(
                etapa_origem,
                evento,
                etapa_destino,
                ETAPA_24_FINALIZACAO,
            )
            return _persistir_comentario_satisfacao_da_etapa23(
                contexto_historico,
                contexto_envio,
                cursor,
            )

    raise ValueError(
        "Transicao sem efeitos conhecidos "
        f"(origem={etapa_origem}, evento={evento}, "
        f"destino={etapa_destino})"
    )


def _exigir_destino(
    etapa_origem,
    evento,
    etapa_destino,
    destino_esperado,
):
    if etapa_destino != destino_esperado:
        raise ValueError(
            "Efeito de transicao recebeu destino incompativel "
            f"(origem={etapa_origem}, evento={evento}, "
            f"destino={etapa_destino}, "
            f"destino_esperado={destino_esperado})"
        )


def _persistir_nome_cliente_capturado_na_etapa1(
    contexto_historico,
    contexto_envio,
    cursor,
):
    primeiro_nome = _resolver_primeiro_nome_capturado(
        contexto_historico,
        contexto_envio,
        "primeiro_nome_cliente",
    )

    if not primeiro_nome:
        print(
            "\n"
            "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!\n"
            "!!! NOME VAZIO NA TRANSICAO 1 -> 2: ANOMALIA RARA E CRITICA !!!\n"
            "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!\n"
        )
        logger.critical(
            "cliente_nome_anomalia_critica | motivo=nome_vazio_na_transicao_1_2 acao=rollback_e_retry id_conversa=%s etapa_origem=%s etapa_resultante=%s",
            contexto_historico["id_conversa"],
            contexto_historico.get("id_etapa_origem_transicao"),
            contexto_envio.get("id_etapa_resultante"),
        )
        raise ValueError(
            "Nome do cliente nao foi resolvido na transicao 1 -> 2"
        )

    mensagem_cliente = contexto_historico["mensagem_cliente_atual"]
    cliente_telefone = mensagem_cliente["cliente_telefone"]

    atualizar_nome_cliente_por_telefone(
        cliente_telefone,
        primeiro_nome,
        cursor,
    )

    logger.info(
        "cliente_nome_persistido | acao=salvar_nome evento=%s etapa_origem=%s etapa_resultante=%s id_conversa=%s cliente=%s",
        EVENTO_NOME_CLIENTE_VALIDO,
        contexto_historico.get("id_etapa_origem_transicao"),
        contexto_envio.get("id_etapa_resultante"),
        contexto_historico["id_conversa"],
        short_value(cliente_telefone),
    )

    return {
        "cliente_nome_atualizado": True,
        "primeiro_nome_cliente": primeiro_nome,
    }


def _persistir_destino_atendimento_da_etapa2(
    contexto_historico,
    contexto_envio,
    etapa_destino,
    *,
    cursor,
):
    id_conversa = contexto_historico["id_conversa"]
    opcao_atendimento = contexto_envio.get("opcao_atendimento")

    if opcao_atendimento is None:
        opcao_atendimento = validar_etapa2(
            contexto_historico.get("texto_cliente_atual") or ""
        )

    if opcao_atendimento is None:
        raise ValueError(
            "Destino do atendimento nao reconstruido na transicao 2 -> 3"
        )

    status_dependente = (
        opcao_atendimento == OPCAO_PARA_OUTRA_PESSOA
    )

    atualizar_status_dependente_conversa(
        id_conversa,
        status_dependente,
        cursor,
    )

    contexto_persistido = {
        "status_dependente_atualizado": True,
        "status_dependente": status_dependente,
        "opcao_atendimento": opcao_atendimento,
        "dependente_criado": False,
    }

    if status_dependente:
        dependente = inserir_dependente_para_conversa(
            id_conversa,
            cursor,
        )
        contexto_persistido.update(
            {
                "dependente_criado": dependente["inserido"],
                "id_dependente": dependente["id_dependente"],
                "id_cliente_dependente": dependente["id_cliente"],
            }
        )

    logger.info(
        "destino_atendimento_persistido | acao=salvar_efeitos_transicao evento=%s etapa_origem=%s etapa_resultante=%s id_conversa=%s status_dependente=%s dependente_criado=%s",
        EVENTO_DESTINO_ATENDIMENTO_DEFINIDO,
        contexto_historico.get("id_etapa_origem_transicao"),
        etapa_destino,
        id_conversa,
        status_dependente,
        contexto_persistido["dependente_criado"],
    )

    return contexto_persistido


def _persistir_confirmacao_destino_da_etapa3(
    contexto_historico,
    contexto_envio,
    cursor,
):
    """Aplica o destino final como valor absoluto e seguro para replay.

    No primeiro processamento, o validador produz o valor absoluto. Em replay,
    movimento e efeito já foram confirmados juntos, então o worker relê esse
    mesmo valor da conversa. A resposta relativa nunca é reinterpretada.
    """
    status_dependente_final = contexto_envio.get(
        "status_dependente_final"
    )
    if not isinstance(status_dependente_final, bool):
        raise ValueError(
            "Confirmacao da etapa 3 sem status_dependente_final booleano "
            f"(valor={status_dependente_final!r})"
        )

    id_conversa = contexto_historico["id_conversa"]
    status_anterior = contexto_historico.get("status_dependente")
    if not isinstance(status_anterior, bool):
        raise ValueError(
            "Confirmacao da etapa 3 sem status_dependente anterior booleano "
            f"(valor={status_anterior!r})"
        )

    atualizar_status_dependente_conversa(
        id_conversa,
        status_dependente_final,
        cursor,
    )

    resultado = {
        "status_dependente_atualizado": True,
        "status_dependente": status_dependente_final,
        "status_dependente_alterado": (
            status_anterior != status_dependente_final
        ),
        "dependente_criado": False,
        "dependente_removido": False,
    }

    if status_dependente_final:
        dependente = inserir_dependente_para_conversa(id_conversa, cursor)
        resultado.update(
            {
                "dependente_criado": dependente["inserido"],
                "id_dependente": dependente["id_dependente"],
                "id_cliente_dependente": dependente["id_cliente"],
            }
        )
    else:
        resultado["dependente_removido"] = (
            remover_dependente_placeholder_da_conversa(
                id_conversa,
                cursor,
            )
        )

    logger.info(
        "destino_atendimento_confirmado | acao=aplicar_status_absoluto "
        "evento=%s etapa_origem=%s etapa_resultante=%s id_conversa=%s "
        "status_anterior=%s status_final=%s dependente_criado=%s "
        "dependente_removido=%s",
        contexto_envio.get("evento_transicao"),
        contexto_historico.get("id_etapa_origem_transicao"),
        contexto_envio.get("id_etapa_resultante"),
        id_conversa,
        status_anterior,
        status_dependente_final,
        resultado["dependente_criado"],
        resultado["dependente_removido"],
    )

    return resultado


def _persistir_profissao_capturada_na_etapa4(
    contexto_historico,
    contexto_envio,
    cursor,
    *,
    status_dependente_esperado,
):
    status_dependente = contexto_historico.get("status_dependente")
    if not isinstance(status_dependente, bool):
        raise ValueError(
            "Profissao sem status_dependente booleano persistido "
            f"(valor={status_dependente!r})"
        )

    if status_dependente != status_dependente_esperado:
        raise ValueError(
            "Evento da profissao incompativel com o destino do atendimento "
            f"(id_conversa={contexto_historico['id_conversa']}, "
            f"status_dependente={status_dependente})"
        )

    profissao = contexto_envio.get("profissao")

    if profissao is None:
        resultado = validar_profissao_etapa4(
            contexto_historico.get("texto_cliente_atual") or "",
            contexto_historico.get("tipo_mensagem_atual"),
        )
        if resultado.valida:
            profissao = resultado.profissao

    if not profissao:
        raise ValueError(
            "Profissao nao reconstruida na transicao da etapa 4"
        )

    atualizar_profissao_conversa(
        contexto_historico["id_conversa"],
        profissao,
        cursor,
    )
    atualizar_profissao_cliente(
        contexto_historico["id_cliente"],
        profissao,
        cursor,
    )

    logger.info(
        "profissao_persistida | acao=salvar_snapshot_e_atualizar_cliente "
        "evento=%s etapa_origem=%s etapa_resultante=%s "
        "id_conversa=%s id_cliente=%s profissao=%s",
        contexto_envio.get("evento_transicao"),
        contexto_historico["id_etapa_origem_transicao"],
        contexto_envio["id_etapa_resultante"],
        contexto_historico["id_conversa"],
        contexto_historico["id_cliente"],
        short_value(profissao),
    )

    return {
        "profissao_atualizada": True,
        "profissao": profissao,
    }


def _persistir_nome_dependente_capturado_na_etapa5(
    contexto_historico,
    contexto_envio,
    cursor,
):
    primeiro_nome = _resolver_primeiro_nome_capturado(
        contexto_historico,
        contexto_envio,
        "primeiro_nome_dependente",
    )

    if not primeiro_nome:
        logger.critical(
            "dependente_nome_anomalia_critica | motivo=nome_vazio_na_transicao_5_6 acao=rollback_e_retry id_conversa=%s etapa_origem=%s etapa_resultante=%s",
            contexto_historico["id_conversa"],
            contexto_historico.get("id_etapa_origem_transicao"),
            contexto_envio.get("id_etapa_resultante"),
        )
        raise ValueError(
            "Nome do dependente nao foi resolvido na transicao 5 -> 6"
        )

    id_conversa = contexto_historico["id_conversa"]
    atualizar_nome_dependente_por_conversa(
        id_conversa,
        primeiro_nome,
        cursor,
    )

    logger.info(
        "dependente_nome_persistido | acao=salvar_nome evento=%s etapa_origem=%s etapa_resultante=%s id_conversa=%s",
        EVENTO_NOME_DEPENDENTE_VALIDO,
        contexto_historico.get("id_etapa_origem_transicao"),
        contexto_envio.get("id_etapa_resultante"),
        id_conversa,
    )

    return {
        "dependente_nome_atualizado": True,
        "primeiro_nome_dependente": primeiro_nome,
    }


def _resolver_primeiro_nome_capturado(
    contexto_historico,
    contexto_envio,
    chave_contexto,
):
    primeiro_nome = contexto_envio.get(chave_contexto)

    if primeiro_nome:
        return primeiro_nome

    resultado_nome = validar_nome_cliente(
        contexto_historico.get("texto_cliente_atual") or ""
    )

    if resultado_nome.valido:
        return resultado_nome.primeiro_nome

    return None


def _persistir_idade_capturada_na_etapa6(
    contexto_historico,
    contexto_envio,
    cursor,
):
    idade = contexto_envio.get("idade_aluno")

    if idade is None:
        resultado = validar_idade(
            contexto_historico.get("texto_cliente_atual") or ""
        )
        if resultado.valida:
            idade = resultado.idade

    if idade is None:
        raise ValueError(
            "Idade não reconstruída na transição 6 -> 7"
        )

    if contexto_historico.get("status_dependente"):
        atualizar_idade_dependente(
            contexto_historico["id_conversa"],
            idade,
            cursor,
        )
        destino_dado = "dependente"
    else:
        atualizar_idade_cliente(
            contexto_historico["id_cliente"],
            idade,
            cursor,
        )
        destino_dado = "cliente"

    logger.info(
        "idade_aluno_persistida | acao=salvar_efeito_transicao "
        "evento=%s etapa_origem=%s etapa_resultante=%s "
        "id_conversa=%s idade=%s destino_dado=%s",
        EVENTO_IDADE_VALIDA,
        contexto_historico["id_etapa_origem_transicao"],
        contexto_envio["id_etapa_resultante"],
        contexto_historico["id_conversa"],
        idade,
        destino_dado,
    )

    return {
        "idade_aluno_atualizada": True,
        "idade_aluno": idade,
        "destino_dado": destino_dado,
    }


def _persistir_idade_encaminhamento_suporte_idoso(
    contexto_historico,
    contexto_envio,
    cursor,
):
    if contexto_historico.get("status_dependente"):
        raise ValueError(
            "Encaminhamento de suporte ao idoso não aceita dependente"
        )

    idade = contexto_envio.get("idade_aluno")
    if idade is None:
        resultado = validar_idade(
            contexto_historico.get("texto_cliente_atual") or ""
        )
        idade = resultado.idade if resultado.valida else None

    if (
        isinstance(idade, bool)
        or not isinstance(idade, int)
        or not 50 <= idade <= 99
    ):
        raise ValueError(
            "Idade inválida no encaminhamento de suporte ao idoso "
            f"(idade={idade!r})"
        )

    atualizar_idade_cliente(
        contexto_historico["id_cliente"],
        idade,
        cursor,
    )

    logger.info(
        "idade_titular_persistida | acao=encaminhar_suporte_idoso "
        "id_conversa=%s id_cliente=%s faixa=50_99",
        contexto_historico["id_conversa"],
        contexto_historico["id_cliente"],
    )
    return {
        "idade_aluno_atualizada": True,
        "idade_aluno": idade,
        "destino_dado": "cliente",
        "encaminhamento_suporte_idoso": True,
    }


def _confirmar_decisao_oferta_da_etapa7(
    contexto_historico,
    evento,
    etapa_destino,
):
    """
    Torna explícita a aresta da oferta sem duplicar persistência.

    A mudança de id_etapa_atual já foi executada e revalidada no PostgreSQL
    por persistir_movimento_conversa antes dos efeitos específicos.
    """
    logger.info(
        "decisao_oferta_persistida | acao=confirmar_transicao "
        "evento=%s etapa_origem=%s etapa_resultante=%s id_conversa=%s",
        evento,
        contexto_historico["id_etapa_origem_transicao"],
        etapa_destino,
        contexto_historico["id_conversa"],
    )

    return {
        "decisao_oferta_persistida": True,
        "decisao_oferta": evento,
    }


def _confirmar_retorno_cliente_da_etapa8(
    contexto_historico,
    evento,
    etapa_destino,
):
    """
    Confirma a continuidade sem criar dado de negócio adicional.

    A mudança de id_etapa_atual já foi persistida pelo movimento genérico da
    conversa. Esta etapa apenas torna explícita a aresta 8 -> 9.
    """
    logger.info(
        "retorno_cliente_persistido | acao=confirmar_transicao "
        "evento=%s etapa_origem=%s etapa_resultante=%s id_conversa=%s",
        evento,
        contexto_historico["id_etapa_origem_transicao"],
        etapa_destino,
        contexto_historico["id_conversa"],
    )

    return {
        "retorno_cliente_persistido": True,
        "evento_retorno": evento,
    }


def _confirmar_decisao_retorno_da_etapa9(
    contexto_historico,
    evento,
    etapa_destino,
):
    """
    Torna explícita a decisão do retorno sem duplicar persistência.

    A mudança de id_etapa_atual já foi persistida pelo movimento genérico da
    conversa. Esta função confirma apenas as arestas 9 -> 10 e 9 -> 8.
    """
    logger.info(
        "decisao_retorno_persistida | acao=confirmar_transicao "
        "evento=%s etapa_origem=%s etapa_resultante=%s id_conversa=%s",
        evento,
        contexto_historico["id_etapa_origem_transicao"],
        etapa_destino,
        contexto_historico["id_conversa"],
    )

    return {
        "decisao_retorno_persistida": True,
        "decisao_retorno": evento,
    }


def _persistir_email_capturado_na_etapa10(
    contexto_historico,
    contexto_envio,
    cursor,
):
    """Persiste de forma absoluta o resultado aceito na conversa atual."""
    classificacao = contexto_envio.get("resultado_coleta_email")
    email = contexto_envio.get("email_cliente")

    if classificacao is None and email:
        classificacao = CLASSIFICACAO_EMAIL_VALIDO
        email = validar_etapa10(email).email

    if classificacao is None:
        texto_cliente = contexto_historico.get("texto_cliente_atual") or ""

        if contexto_envio.get("resposta_ja_existia"):
            resultado_email = classificar_resposta_email_aceita(
                texto_cliente
            )
        else:
            email_obrigatorio = calcular_email_obrigatorio_efetivo(
                contexto_historico.get("email_obrigatorio_unidade"),
                contexto_historico.get("status_dependente"),
                contexto_historico.get("idade_cliente"),
            )
            resultado_email = classificar_resposta_email(
                texto_cliente,
                email_obrigatorio=email_obrigatorio,
            )

        if not resultado_email.aceita:
            raise ValueError(
                "Resultado de email nao reconstruido na transicao 10 -> 11"
            )

        classificacao = resultado_email.classificacao
        email = resultado_email.email

    classificacoes_validas = {
        CLASSIFICACAO_EMAIL_VALIDO,
        CLASSIFICACAO_EMAIL_AUSENTE,
        CLASSIFICACAO_EMAIL_NAO_INFORMADO,
    }
    if classificacao not in classificacoes_validas:
        raise ValueError(
            "Classificacao de email invalida na transicao 10 -> 11 "
            f"(classificacao={classificacao!r})"
        )

    if classificacao == CLASSIFICACAO_EMAIL_VALIDO:
        resultado_estrutural = validar_etapa10(email)
        if not resultado_estrutural.valido:
            raise ValueError(
                "Email valido sem endereco reconstruivel na transicao 10 -> 11"
            )
        email = resultado_estrutural.email
    else:
        email = None

    atualizar_email_cliente(
        contexto_historico["id_cliente"],
        email,
        cursor,
    )

    logger.info(
        "cliente_email_persistido | acao=salvar_efeito_transicao "
        "evento=%s etapa_origem=%s etapa_resultante=%s "
        "id_conversa=%s id_cliente=%s email_preenchido=%s "
        "resultado_coleta=%s",
        EVENTO_EMAIL_VALIDO,
        contexto_historico["id_etapa_origem_transicao"],
        contexto_envio["id_etapa_resultante"],
        contexto_historico["id_conversa"],
        contexto_historico["id_cliente"],
        bool(email),
        classificacao,
    )

    return {
        "cliente_email_atualizado": True,
        "email_preenchido": bool(email),
        "resultado_coleta_email": classificacao,
    }


def _confirmar_inicio_triagem_da_etapa11(
    contexto_historico,
    evento,
    etapa_destino,
):
    """
    Confirma a continuidade sem criar dado de negócio adicional.

    A mudança de id_etapa_atual já foi persistida pelo movimento genérico da
    conversa. Esta função torna explícita somente a aresta 11 -> 12.
    """
    logger.info(
        "inicio_triagem_persistido | acao=confirmar_transicao "
        "evento=%s etapa_origem=%s etapa_resultante=%s id_conversa=%s",
        evento,
        contexto_historico["id_etapa_origem_transicao"],
        etapa_destino,
        contexto_historico["id_conversa"],
    )

    return {
        "inicio_triagem_persistido": True,
        "evento_triagem": evento,
    }


def _persistir_resposta_triagem(
    contexto_historico,
    contexto_envio,
    cursor,
):
    """
    Persiste a opção da pergunta de origem dentro da transação final.

    Em reaplicação idempotente, o contexto de envio não possui a resposta.
    Nesse caso, a opção é reconstruída pela mensagem original do cliente.
    """
    resposta_triagem = contexto_envio.get("resposta_triagem")

    if resposta_triagem is None:
        resposta_triagem = validar_resposta_triagem(
            contexto_historico.get("texto_cliente_atual") or "",
            contexto_historico.get("tipo_mensagem_atual"),
        )

    if resposta_triagem is None:
        raise ValueError(
            "Resposta da triagem não foi reconstruída na transição "
            f"(etapa={contexto_historico.get('id_etapa_origem_transicao')})"
        )

    mensagem_cliente = contexto_historico["mensagem_cliente_atual"]
    resultado = registrar_resposta_triagem(
        contexto_historico["id_conversa"],
        contexto_historico["id_etapa_origem_transicao"],
        resposta_triagem,
        mensagem_cliente.get("id_mensagem"),
        cursor,
    )

    logger.info(
        "efeito_resposta_triagem_persistido | acao=salvar_resposta "
        "evento=%s etapa_origem=%s etapa_resultante=%s "
        "id_conversa=%s resposta=%s inserido=%s",
        contexto_envio.get("evento_transicao"),
        contexto_historico["id_etapa_origem_transicao"],
        contexto_envio["id_etapa_resultante"],
        contexto_historico["id_conversa"],
        resposta_triagem,
        resultado["inserido"],
    )

    return {
        "resposta_triagem_persistida": True,
        **resultado,
    }


def _confirmar_agendamento_da_etapa20(
    contexto_historico,
    evento,
    etapa_destino,
):
    """Confirma a aresta 20 -> 21 sem criar dado de negocio adicional."""
    logger.info(
        "agendamento_confirmado_persistido | acao=confirmar_transicao "
        "evento=%s etapa_origem=%s etapa_resultante=%s id_conversa=%s",
        evento,
        contexto_historico["id_etapa_origem_transicao"],
        etapa_destino,
        contexto_historico["id_conversa"],
    )

    return {
        "agendamento_confirmado": True,
        "evento_agendamento": evento,
    }


def _persistir_nota_satisfacao_da_etapa21(
    contexto_historico,
    contexto_envio,
    cursor,
):
    """Persiste a nota; em retry, reconstrói o valor pela mensagem original."""
    nota_satisfacao = contexto_envio.get("nota_satisfacao")

    if nota_satisfacao is None:
        nota_satisfacao = validar_etapa21(
            contexto_historico.get("texto_cliente_atual") or ""
        )

    if nota_satisfacao is None:
        raise ValueError(
            "Nota de satisfacao ausente na transicao 21 -> 22 "
            f"(id_conversa={contexto_historico['id_conversa']})"
        )

    resultado = salvar_nota_satisfacao(
        contexto_historico["id_conversa"],
        nota_satisfacao,
        cursor,
    )

    logger.info(
        "efeito_nota_satisfacao_persistido | acao=salvar_nota "
        "evento=%s etapa_origem=%s etapa_resultante=%s "
        "id_conversa=%s nota=%s inserido=%s",
        contexto_envio.get("evento_transicao"),
        contexto_historico["id_etapa_origem_transicao"],
        contexto_envio["id_etapa_resultante"],
        contexto_historico["id_conversa"],
        nota_satisfacao,
        resultado["inserido"],
    )

    return {
        "nota_satisfacao_persistida": True,
        **resultado,
    }


def _confirmar_decisao_comentario_da_etapa22(
    contexto_historico,
    evento,
    etapa_destino,
):
    """Confirma a escolha sem criar dado antes do comentário efetivo."""
    logger.info(
        "decisao_comentario_persistida | acao=confirmar_transicao "
        "evento=%s etapa_origem=%s etapa_resultante=%s id_conversa=%s",
        evento,
        contexto_historico["id_etapa_origem_transicao"],
        etapa_destino,
        contexto_historico["id_conversa"],
    )

    return {
        "decisao_comentario_persistida": True,
        "decisao_comentario": evento,
    }


def _persistir_recusa_comentario_da_etapa22(
    contexto_historico,
    cursor,
):
    """Registra NULL de forma idempotente para a recusa explícita."""
    resultado = salvar_comentario_satisfacao(
        contexto_historico["id_conversa"],
        None,
        cursor,
    )

    logger.info(
        "recusa_comentario_satisfacao_persistida | "
        "acao=salvar_comentario_nulo evento=%s etapa_origem=%s "
        "etapa_resultante=%s id_conversa=%s inserido=%s",
        EVENTO_COMENTARIO_SATISFACAO_RECUSADO,
        contexto_historico["id_etapa_origem_transicao"],
        ETAPA_24_FINALIZACAO,
        contexto_historico["id_conversa"],
        resultado["inserido"],
    )

    return {
        "comentario_satisfacao_persistido": True,
        **resultado,
    }


def _persistir_comentario_satisfacao_da_etapa23(
    contexto_historico,
    contexto_envio,
    cursor,
):
    """Persiste o texto; em retry, reconstrói a mensagem original."""
    if "comentario_satisfacao" in contexto_envio:
        comentario_satisfacao = contexto_envio["comentario_satisfacao"]
    else:
        texto_cliente = contexto_historico.get("texto_cliente_atual") or ""
        tipo_mensagem = contexto_historico.get("tipo_mensagem_atual")
        # Reconstruir o mesmo resultado do primeiro processamento, inclusive NULL
        # quando não houve texto ou o cliente recusou comentar. Mídia não avança.
        if tipo_mensagem not in TIPOS_MENSAGEM_ACEITOS_ETAPA22:
            raise ValueError(
                "Tipo de mensagem não permitido na transição 23 -> 24 "
                f"(id_conversa={contexto_historico['id_conversa']})"
            )
        comentario_satisfacao = normalizar_comentario_etapa23(
            texto_cliente,
            tipo_mensagem,
        )

    resultado = salvar_comentario_satisfacao(
        contexto_historico["id_conversa"],
        comentario_satisfacao,
        cursor,
    )

    logger.info(
        "efeito_comentario_satisfacao_persistido | "
        "acao=salvar_comentario evento=%s etapa_origem=%s "
        "etapa_resultante=%s id_conversa=%s "
        "comentario_preenchido=%s inserido=%s",
        contexto_envio.get("evento_transicao"),
        contexto_historico["id_etapa_origem_transicao"],
        contexto_envio["id_etapa_resultante"],
        contexto_historico["id_conversa"],
        bool(comentario_satisfacao),
        resultado["inserido"],
    )

    return {
        "comentario_satisfacao_persistido": True,
        **resultado,
    }
```

## Passo 23 — Substituir integralmente `workers/worker_flow/transacoes/movimento_conversa.py`

```python
from workers.worker_flow.fireads import email_importado
from core.repositories.atendimento.conversas import (
    atualizar_conversa_por_transicao,
    atualizar_conversa_resposta_bot_sem_avancar,
    inicializar_conversa_resposta_bot,
)
from workers.worker_flow.response_flow.transicoes.eventos import (
    ETAPA_1_NOME_CLIENTE,
)


MOVIMENTO_INICIALIZACAO = "inicializacao"
MOVIMENTO_TRANSICAO = "transicao"
MOVIMENTO_SEM_AVANCO = "sem_avanco"


def persistir_movimento_conversa(
    contexto_historico,
    contexto_envio,
    data_interacao_bot,
    cursor,
):
    movimento = resolver_movimento_conversa(
        contexto_historico,
        contexto_envio,
    )
    id_conversa = contexto_historico["id_conversa"]
    id_etapa_destino = contexto_envio.get("id_etapa_resultante")

    if movimento == MOVIMENTO_INICIALIZACAO:
        inicializar_conversa_resposta_bot(
            id_conversa,
            id_etapa_destino,
            data_interacao_bot,
            cursor,
        )
        return movimento

    if movimento == MOVIMENTO_TRANSICAO:
        atualizar_conversa_por_transicao(
            id_conversa,
            contexto_historico["id_etapa_origem_transicao"],
            contexto_envio["evento_transicao"],
            id_etapa_destino,
            data_interacao_bot,
            cursor,
            permitir_reaplicacao=bool(
                contexto_envio.get("resposta_ja_existia")
            ),
        )
        return movimento

    atualizar_conversa_resposta_bot_sem_avancar(
        id_conversa,
        data_interacao_bot,
        cursor,
    )
    return movimento


def resolver_movimento_conversa(
    contexto_historico,
    contexto_envio,
):
    etapa_atual = contexto_historico.get("id_etapa_atual")
    etapa_origem = contexto_historico.get(
        "id_etapa_origem_transicao"
    )
    etapa_destino = contexto_envio.get("id_etapa_resultante")
    evento_transicao = contexto_envio.get("evento_transicao")
    tratamento = bool(contexto_envio.get("tratamento"))

    if etapa_destino is None:
        raise ValueError("Resposta do bot sem id_etapa_resultante")

    # Primeiro contato: apenas apresenta a etapa 1, sem transição.
    if etapa_atual is None:
        if etapa_destino != ETAPA_1_NOME_CLIENTE and not (
            etapa_destino == 4 and email_importado(contexto_historico)
        ):
            raise ValueError(
                "Inicializacao exige etapa 1 ou importacao FireAds completa na etapa 4"
            )

        if evento_transicao:
            raise ValueError(
                "Inicializacao da conversa nao aceita evento de transicao"
            )

        return MOVIMENTO_INICIALIZACAO

    # Uma resposta válida produz evento e pode mudar de etapa.
    if evento_transicao:
        if tratamento:
            raise ValueError(
                "Tratamento nao pode avancar por evento de transicao"
            )

        if etapa_origem is None:
            raise ValueError(
                "Evento de transicao sem etapa de origem persistida"
            )

        return MOVIMENTO_TRANSICAO

    # Tratamentos não produzem evento e obrigatoriamente permanecem na origem.
    if etapa_destino != etapa_origem:
        raise ValueError(
            "Resposta sem evento tentou alterar a etapa da conversa "
            f"(origem={etapa_origem}, destino={etapa_destino})"
        )

    return MOVIMENTO_SEM_AVANCO
```

## Passo 24 — Substituir integralmente `workers/worker_flow/transacoes/persistencia_resposta.py`

```python
import logging
from core.repositories.fireads.consulta import guardar_coletas

from core.repositories.atendimento.historico import inserir_historico_mensagem_bot
from core.repositories.seguranca.suspeita_bot import (
    incrementar_turnos_sem_avanco,
    resetar_turnos_sem_avanco,
)
from workers.worker_flow.transacoes.encerramento_atendimento import (
    resolver_intencao_encerramento,
)
from workers.worker_flow.transacoes.efeitos_transicao import (
    atualizar_banco_conforme_transicao_de_etapa,
)
from workers.worker_flow.transacoes.movimento_conversa import (
    MOVIMENTO_SEM_AVANCO,
    MOVIMENTO_TRANSICAO,
    persistir_movimento_conversa,
)


logger = logging.getLogger("worker.support")


def _obter_data_interacao_bot_existente(contexto_historico):
    resposta_bot = (
        contexto_historico.get("resposta_bot_para_mensagem_atual") or {}
    )
    data_interacao = resposta_bot.get("received_data_hora")

    if data_interacao is None:
        raise ValueError(
            "Resposta do bot existente sem received_data_hora persistido"
        )

    return data_interacao


def atualizar_banco_com_contexto_final(
    contexto_historico,
    contexto_envio,
    cursor,
):
    """
    Persiste o resultado completo do ciclo em uma única transação.

    Ordem preservada:
    1. registrar ou recuperar a resposta do bot;
    2. persistir inicialização, transição ou permanência;
    3. incrementar ou zerar a suspeita de bot;
    4. aplicar os efeitos específicos da aresta;
    5. devolver o contexto final para a finalização da fila.
    """
    id_conversa = contexto_historico["id_conversa"]
    id_etapa_resultante = contexto_envio.get("id_etapa_resultante")
    resposta_ja_existia = bool(
        contexto_envio.get("resposta_ja_existia")
    )

    (
        id_historico_bot,
        data_interacao_bot,
        historico_bot_inserido,
    ) = _persistir_ou_recuperar_resposta_bot(
        contexto_historico,
        contexto_envio,
        cursor,
    )

    movimento = persistir_movimento_conversa(
        contexto_historico,
        contexto_envio,
        data_interacao_bot,
        cursor,
    )

    turnos_sem_avanco = _persistir_turnos_sem_avanco(
        id_conversa=id_conversa,
        movimento=movimento,
        tratamento=bool(contexto_envio.get("tratamento")),
        historico_bot_inserido=historico_bot_inserido,
        retorno_followup=bool(contexto_historico.get("retorno_followup")),
        cursor=cursor,
    )

    efeitos_transicao = atualizar_banco_conforme_transicao_de_etapa(
        contexto_historico,
        contexto_envio,
        cursor,
    )
    guardar_coletas(contexto_historico, efeitos_transicao, cursor)
    intencao_encerramento = resolver_intencao_encerramento(
        contexto_historico,
        contexto_envio,
        cursor,
    )

    logger.info(
        "resposta_bot_persistida | acao=registrar_historico_e_contexto "
        "id_conversa=%s id_historico_bot=%s inserido=%s "
        "resposta_ja_existia=%s movimento=%s etapa=%s evento=%s "
        "id_hash_msg_bot=%s turnos_sem_avanco=%s",
        id_conversa,
        id_historico_bot,
        historico_bot_inserido,
        resposta_ja_existia,
        movimento,
        id_etapa_resultante,
        contexto_envio.get("evento_transicao"),
        contexto_envio.get("id_hash_msg_bot"),
        turnos_sem_avanco,
    )

    contexto_final = {
        "historico_bot_inserido": historico_bot_inserido,
        "resposta_ja_existia": resposta_ja_existia,
        "id_hash_msg_bot": contexto_envio.get("id_hash_msg_bot"),
        "id_etapa_resultante": id_etapa_resultante,
        "movimento_conversa": movimento,
        "atualizar_conversa": movimento != MOVIMENTO_SEM_AVANCO,
        "atualizar_last_from_bot": True,
        "intencao_encerramento": intencao_encerramento,
    }

    if turnos_sem_avanco is not None:
        contexto_final["turnos_sem_avanco"] = turnos_sem_avanco

    if id_historico_bot is not None:
        contexto_final.update(
            {
                "id_historico_bot": id_historico_bot,
                "data_historico_bot": data_interacao_bot,
            }
        )

    if efeitos_transicao:
        contexto_final["efeitos_transicao"] = efeitos_transicao

    return contexto_final


def _persistir_turnos_sem_avanco(
    *,
    id_conversa,
    movimento,
    tratamento,
    historico_bot_inserido,
    cursor,
    retorno_followup=False,
):
    if movimento == MOVIMENTO_TRANSICAO:
        return resetar_turnos_sem_avanco(id_conversa, cursor)

    if (
        movimento == MOVIMENTO_SEM_AVANCO
        and tratamento
        # A primeira reação ao lembrete não penaliza o cliente.
        and not retorno_followup
        and historico_bot_inserido
    ):
        return incrementar_turnos_sem_avanco(id_conversa, cursor)

    return None


def _persistir_ou_recuperar_resposta_bot(
    contexto_historico,
    contexto_envio,
    cursor,
):
    if contexto_envio.get("resposta_ja_existia"):
        return (
            None,
            _obter_data_interacao_bot_existente(contexto_historico),
            False,
        )

    if not contexto_envio.get("enviou"):
        raise ValueError(
            "Contexto de envio sem resposta enviada e sem resposta existente"
        )

    return inserir_historico_mensagem_bot(
        contexto_historico,
        contexto_envio,
        cursor,
    )
```

## Passo 25 — Substituir integralmente `workers/worker_flow/valida_historico.py`

```python
import logging
from workers.worker_flow.fireads import email_importado


from core.logging_config import short_value
from core.integrations.whatsapp.messages.tratamentos.retorno_inatividade import (
    montar_saudacao_retorno,
)
from core.repositories.atendimento.conversas import (
    atualizar_conversa_mensagem_cliente,
    atualizar_conversa_resposta_bot_sem_avancar,
)
from core.repositories.atendimento.historico import (
    buscar_contexto_saudacao_retorno,
    buscar_resposta_bot_por_mensagem_cliente,
    inserir_historico_mensagem_cliente,
)
from core.repositories.fluxo.contextos.etapa1 import buscar_contexto_etapa1
from core.repositories.fluxo.contextos.etapa6 import buscar_contexto_etapa6
from core.repositories.fluxo.contextos.etapa7 import buscar_contexto_etapa7
from core.repositories.fluxo.contextos.etapa9 import buscar_contexto_etapa9
from core.repositories.fluxo.contextos.etapa10 import buscar_contexto_etapa10
from core.repositories.fluxo.contextos.etapa18 import buscar_contexto_etapa18
from core.repositories.fluxo.contextos.etapa20 import buscar_contexto_etapa20
from core.repositories.fluxo.contextos.etapa24 import buscar_contexto_etapa24
from core.repositories.fluxo.contextos.triagem import buscar_contexto_triagem
from core.repositories.fluxo.transicoes import listar_transicoes_permitidas
from workers.worker_flow.response_flow.transicoes.contexto_transicao import (
    montar_contexto_transicao,
    prever_etapa_resposta,
)
from workers.worker_flow.response_flow.transicoes.eventos import (
    ETAPA_6_IDADE_ALUNO,
    ETAPA_7_OFERTA_AULA,
    ETAPA_8_OFERTA_ADIADA,
    ETAPA_9_RETORNO_OFERTA,
    ETAPA_10_EMAIL,
    ETAPA_11_INTRODUCAO_TRIAGEM,
    ETAPA_12_TRIAGEM_PERGUNTA_1,
    ETAPA_13_TRIAGEM_PERGUNTA_2,
    ETAPA_14_TRIAGEM_PERGUNTA_3,
    ETAPA_15_TRIAGEM_PERGUNTA_4,
    ETAPA_16_TRIAGEM_PERGUNTA_5,
    ETAPA_17_TRIAGEM_PERGUNTA_6,
    ETAPA_18_ESCOLHA_TURNO,
    ETAPA_19_ENCAMINHAMENTO_COMERCIAL,
    ETAPA_20_AGENDAMENTO,
    ETAPA_22_DECISAO_COMENTARIO,
    ETAPA_23_COMENTARIO_SATISFACAO,
)


logger = logging.getLogger("worker.valida_historico")

ETAPA_INICIAL = 1

ETAPAS_TRIAGEM = {
    ETAPA_11_INTRODUCAO_TRIAGEM,
    ETAPA_12_TRIAGEM_PERGUNTA_1,
    ETAPA_13_TRIAGEM_PERGUNTA_2,
    ETAPA_14_TRIAGEM_PERGUNTA_3,
    ETAPA_15_TRIAGEM_PERGUNTA_4,
    ETAPA_16_TRIAGEM_PERGUNTA_5,
    ETAPA_17_TRIAGEM_PERGUNTA_6,
}


def valida_historico(mensagem, contexto_banco, cursor, *, retorno_followup=False):
    contexto_conversa = contexto_banco["conversa"]
    id_conversa = contexto_conversa["id_conversa"]

    last_message_from_entrada = contexto_conversa.get("last_message_from")
    id_etapa_para_insert = _resolver_etapa_cliente(contexto_conversa)
    # A primeira interação importada pertence à pergunta de profissão.
    # Assim seu replay permanece na etapa 4 sem simular uma transição 1 -> 4.
    if contexto_conversa.get("id_etapa_atual") is None and email_importado({
        "id_conversa": id_conversa,
        "contexto_fireads": contexto_banco.get("contexto_fireads"),
    }):
        id_etapa_para_insert = 4

    (
        id_historico_cliente,
        data_historico_cliente,
        id_etapa_cliente,
        cliente_inserido_no_historico,
    ) = inserir_historico_mensagem_cliente(
        mensagem=mensagem,
        id_conversa=id_conversa,
        id_etapa=id_etapa_para_insert,
        cursor=cursor,
    )

    mensagem_cliente_atual = {
        "id_mensagem": id_historico_cliente,
        "id_conversa": id_conversa,
        "id_etapa": id_etapa_cliente,
        "received_data_hora": data_historico_cliente,
        "cliente_telefone": mensagem["cliente_telefone"],
        "conteudo_texto": mensagem["conteudo_texto"],
        "tipo_mensagem": mensagem["tipo_mensagem"],
        "id_hash_msg": mensagem["id_hash"],
        "id_mensagem_fila": mensagem["id_mensagem"],
        "id_hash_cliente_origem": None,
        "id_phone_unidade": mensagem["id_phone_unidade"],
        "unidade_telefone": mensagem["unidade_telefone"],
        "quem_enviou": "cliente",
        "status_envio": None,
    }

    resposta_bot_para_mensagem_atual = _normalizar_resposta_bot(
        buscar_resposta_bot_por_mensagem_cliente(
            id_conversa=id_conversa,
            id_mensagem_fila=mensagem["id_mensagem"],
            id_hash_cliente_origem=mensagem["id_hash"],
            cursor=cursor,
        )
    )

    saudacao_retorno = None
    if (
        not retorno_followup
        and not resposta_bot_para_mensagem_atual
        and contexto_conversa.get("id_etapa_atual") not in {None, 1}
    ):
        nome_titular, ultima_mensagem_bot_em = (
            buscar_contexto_saudacao_retorno(
                id_conversa,
                contexto_banco["id_cliente"],
                cursor,
            )
        )
        saudacao_retorno = montar_saudacao_retorno(
            nome_titular,
            ultima_mensagem_bot_em,
            data_historico_cliente,
            contexto_conversa.get("id_etapa_atual"),
        )

        if saudacao_retorno:
            logger.info(
                "saudacao_retorno_ativada | acao=prefixar_resposta "
                "id_conversa=%s id_cliente=%s etapa=%s "
                "ultima_mensagem_bot_em=%s mensagem_cliente_em=%s",
                id_conversa,
                contexto_banco["id_cliente"],
                contexto_conversa.get("id_etapa_atual"),
                ultima_mensagem_bot_em,
                data_historico_cliente,
            )

    transicoes_permitidas = listar_transicoes_permitidas(
        id_etapa_cliente,
        cursor,
    )
    contexto_transicao = montar_contexto_transicao(
        id_etapa_cliente,
        transicoes_permitidas,
    )
    contexto_especifico_etapa = {}

    # Os dados de apresentação da unidade vêm do banco somente no primeiro
    # contato. Respostas posteriores da etapa 1 não repetem essa apresentação.
    if contexto_conversa.get("id_etapa_atual") is None:
        contexto_especifico_etapa.update(
            buscar_contexto_etapa1(
                contexto_banco["id_unidade"],
                cursor,
            )
        )

    if id_etapa_cliente == ETAPA_6_IDADE_ALUNO:
        contexto_especifico_etapa = buscar_contexto_etapa6(
            id_conversa,
            contexto_banco["id_unidade"],
            cursor,
        )

        if (
            contexto_conversa.get("status_dependente")
            and not contexto_especifico_etapa["nome_dependente"]
        ):
            raise ValueError(
                "Etapa 6 de dependente sem nome persistido"
            )

        if (
            not contexto_conversa.get("status_dependente")
            and not contexto_especifico_etapa["nome_titular"]
        ):
            raise ValueError(
                "Etapa 6 do cliente sem nome persistido"
            )

    if id_etapa_cliente == ETAPA_7_OFERTA_AULA:
        contexto_especifico_etapa = buscar_contexto_etapa7(
            id_conversa,
            contexto_banco["id_unidade"],
            cursor,
        )

        chave_nome = (
            "nome_dependente"
            if contexto_conversa.get("status_dependente")
            else "nome_titular"
        )
        if not contexto_especifico_etapa[chave_nome]:
            raise ValueError(
                "Etapa 7 sem nome do aluno persistido "
                f"(campo={chave_nome})"
            )

    if id_etapa_cliente in {
        ETAPA_8_OFERTA_ADIADA,
        ETAPA_9_RETORNO_OFERTA,
    }:
        contexto_especifico_etapa = buscar_contexto_etapa9(
            id_conversa,
            contexto_banco["id_unidade"],
            cursor,
        )

        if not contexto_especifico_etapa["nome_titular"]:
            raise ValueError(
                "Retorno da etapa 9 sem nome do cliente persistido "
                f"(etapa={id_etapa_cliente})"
            )

        if (
            contexto_conversa.get("status_dependente")
            and not contexto_especifico_etapa["nome_dependente"]
        ):
            raise ValueError(
                "Retorno de dependente sem nome persistido "
                f"(etapa={id_etapa_cliente})"
            )

    if id_etapa_cliente == ETAPA_10_EMAIL:
        contexto_email = buscar_contexto_etapa10(
            id_conversa,
            contexto_banco["id_unidade"],
            cursor,
        )
        status_dependente_email = contexto_email.pop(
            "status_dependente_contexto_email"
        )

        if status_dependente_email != contexto_conversa.get(
            "status_dependente"
        ):
            raise ValueError(
                "Etapa 10 com destino de atendimento inconsistente "
                f"(id_conversa={id_conversa})"
            )

        contexto_especifico_etapa.update(contexto_email)

    # As etapas 11-17 relêem do banco a pessoa atendida em cada ciclo. Assim,
    # retries reconstroem a mesma variante etária sem depender de memória.
    if id_etapa_cliente in ETAPAS_TRIAGEM:
        contexto_especifico_etapa.update(
            buscar_contexto_triagem(
                id_conversa,
                contexto_banco["id_unidade"],
                cursor,
            )
        )

        status_dependente = contexto_conversa.get("status_dependente")
        status_dependente_contexto = contexto_especifico_etapa[
            "status_dependente_contexto_triagem"
        ]

        if not isinstance(status_dependente, bool):
            raise ValueError(
                "Triagem sem destino de atendimento definido "
                f"(etapa={id_etapa_cliente}, id_conversa={id_conversa})"
            )

        if (
            not isinstance(status_dependente_contexto, bool)
            or status_dependente_contexto != status_dependente
        ):
            raise ValueError(
                "Triagem com destino de atendimento inconsistente "
                f"(etapa={id_etapa_cliente}, id_conversa={id_conversa})"
            )

        idade_pessoa_triagem = contexto_especifico_etapa[
            "idade_pessoa_triagem"
        ]
        if (
            isinstance(idade_pessoa_triagem, bool)
            or not isinstance(idade_pessoa_triagem, int)
            or idade_pessoa_triagem <= 0
            or idade_pessoa_triagem >= 100
        ):
            raise ValueError(
                "Triagem sem idade valida da pessoa atendida "
                f"(etapa={id_etapa_cliente}, id_conversa={id_conversa})"
            )

        if status_dependente and idade_pessoa_triagem < 4:
            raise ValueError(
                "Triagem de dependente abaixo da idade minima suportada "
                f"(etapa={id_etapa_cliente}, id_conversa={id_conversa})"
            )

        if not status_dependente and idade_pessoa_triagem < 18:
            raise ValueError(
                "Triagem de titular menor de idade "
                f"(etapa={id_etapa_cliente}, id_conversa={id_conversa})"
            )

        nome_dependente = contexto_especifico_etapa["nome_dependente"]
        if status_dependente and (
            not nome_dependente or not str(nome_dependente).strip()
        ):
            raise ValueError(
                "Triagem de dependente sem nome persistido "
                f"(etapa={id_etapa_cliente}, id_conversa={id_conversa})"
            )

        contexto_especifico_etapa.pop(
            "status_dependente_contexto_triagem"
        )

    # As rotas de reserva compartilham dados, mas só a etapa 20 exige plataforma.
    if id_etapa_cliente in {
        ETAPA_17_TRIAGEM_PERGUNTA_6,
        ETAPA_18_ESCOLHA_TURNO,
        ETAPA_19_ENCAMINHAMENTO_COMERCIAL,
    }:
        dados_reserva = buscar_contexto_etapa18(
            id_conversa, contexto_banco["id_unidade"], cursor
        )
        if dados_reserva.pop("status_dependente_reserva") != contexto_conversa.get(
            "status_dependente"
        ):
            raise ValueError(
                "Destino de atendimento divergente na preparação de sua reserva"
            )
        contexto_especifico_etapa.update(dados_reserva)
    elif (
        id_etapa_cliente == ETAPA_20_AGENDAMENTO
        and not resposta_bot_para_mensagem_atual
    ):
        # No replay, o histórico já comprova o envio e o mapa reconstrói a
        # transição. Uma alteração posterior no link não invalida esse envio.
        contexto_especifico_etapa.update(
            buscar_contexto_etapa20(id_conversa, contexto_banco["id_unidade"], cursor)
        )
    # Tanto a recusa na etapa 22 quanto o comentário na 23 podem enviar a 24.
    # Respostas já gravadas são reaproveitadas; não precisam remontar a despedida.
    if not resposta_bot_para_mensagem_atual and id_etapa_cliente in {
        ETAPA_22_DECISAO_COMENTARIO,
        ETAPA_23_COMENTARIO_SATISFACAO,
    }:
        contexto_finalizacao = buscar_contexto_etapa24(
            id_conversa,
            contexto_banco["id_unidade"],
            cursor,
        )
        status_dependente = contexto_conversa.get("status_dependente")
        if type(status_dependente) is not bool or status_dependente != (
            contexto_finalizacao.pop("status_dependente_contexto_finalizacao")
        ):
            raise ValueError("Destino do atendimento inconsistente para a finalização")
        contexto_especifico_etapa.update(contexto_finalizacao)

    if resposta_bot_para_mensagem_atual:
        id_etapa_resposta = resposta_bot_para_mensagem_atual["id_etapa"]

        if last_message_from_entrada != "bot":
            atualizar_conversa_resposta_bot_sem_avancar(
                id_conversa,
                resposta_bot_para_mensagem_atual["received_data_hora"],
                cursor,
            )

        last_message_from_saida = "bot"
    else:
        id_etapa_resposta = prever_etapa_resposta(
            contexto_conversa.get("id_etapa_atual"),
            contexto_transicao["transicoes_permitidas"],
            etapa_inicial=id_etapa_para_insert,
        )
        atualizar_conversa_mensagem_cliente(
            id_conversa,
            data_historico_cliente,
            cursor,
        )
        last_message_from_saida = "cliente"

    logger.info(
        "historico_validado | acao=registrar_cliente id_mensagem=%s id_historico=%s inserido=%s id_conversa=%s etapa_cliente=%s etapa_resposta_previa=%s eventos_transicao=%s last_from_entrada=%s last_from_saida=%s retry=%s resposta_bot_existente=%s cliente=%s phone_number_id=%s",
        mensagem["id_mensagem"],
        id_historico_cliente,
        cliente_inserido_no_historico,
        id_conversa,
        id_etapa_cliente,
        id_etapa_resposta,
        sorted(transicoes_permitidas),
        last_message_from_entrada,
        last_message_from_saida,
        mensagem["retry_count"],
        bool(resposta_bot_para_mensagem_atual),
        short_value(mensagem["cliente_telefone"]),
        short_value(mensagem["id_phone_unidade"]),
    )

    contexto_historico = {
        "contexto_fireads": contexto_banco.get("contexto_fireads"),
        "id_conversa": id_conversa,
        "id_cliente": contexto_banco.get("id_cliente"),
        "id_unidade": contexto_banco.get("id_unidade"),
        "id_etapa_atual": contexto_conversa.get("id_etapa_atual"),
        "id_etapa_cliente": id_etapa_cliente,
        # Compatibilidade apenas para logs existentes. Este campo nunca decide
        # uma transição e pode ser None quando há mais de um destino.
        "id_etapa_resposta": id_etapa_resposta,
        "id_etapa_origem_transicao": contexto_transicao[
            "id_etapa_origem_transicao"
        ],
        "transicoes_permitidas": contexto_transicao[
            "transicoes_permitidas"
        ],
        "status_dependente": contexto_conversa.get("status_dependente"),
        "last_message_from": last_message_from_saida,
        "last_message_from_entrada": last_message_from_entrada,
        "mensagem_cliente_atual": mensagem_cliente_atual,
        "mensagem_cliente_inserida": cliente_inserido_no_historico,
        "resposta_bot_para_mensagem_atual": resposta_bot_para_mensagem_atual,
        "texto_cliente_atual": mensagem["conteudo_texto"],
        "tipo_mensagem_atual": mensagem["tipo_mensagem"],
        "retry_count": mensagem["retry_count"],
        "precisa_tratamento_erro": False,
        "motivo_tratamento_erro": None,
        "saudacao_retorno": saudacao_retorno,
    }
    contexto_historico.update(contexto_especifico_etapa)
    return contexto_historico


def _resolver_etapa_cliente(contexto_conversa):
    id_etapa_atual = contexto_conversa.get("id_etapa_atual")

    if id_etapa_atual is None:
        return ETAPA_INICIAL

    return id_etapa_atual


def _normalizar_linha_historico(registro):
    (
        id_mensagem,
        id_conversa,
        id_etapa,
        received_data_hora,
        cliente_telefone,
        conteudo_texto,
        tipo_mensagem,
        id_hash_msg,
        id_mensagem_fila,
        id_hash_cliente_origem,
        id_phone_unidade,
        unidade_telefone,
        quem_enviou,
        status_envio,
    ) = registro

    return {
        "id_mensagem": id_mensagem,
        "id_conversa": id_conversa,
        "id_etapa": id_etapa,
        "received_data_hora": received_data_hora,
        "cliente_telefone": cliente_telefone,
        "conteudo_texto": conteudo_texto,
        "tipo_mensagem": tipo_mensagem,
        "id_hash_msg": id_hash_msg,
        "id_mensagem_fila": id_mensagem_fila,
        "id_hash_cliente_origem": id_hash_cliente_origem,
        "id_phone_unidade": id_phone_unidade,
        "unidade_telefone": unidade_telefone,
        "quem_enviou": quem_enviou,
        "status_envio": status_envio,
    }


def _normalizar_resposta_bot(registro):
    if not registro:
        return None

    return _normalizar_linha_historico(registro)
```

## Passo 26 — Substituir integralmente `core/repositories/funil/envios.py`

```python
"""Fila transacional e idempotência local dos envios ao Funil."""


STATUS_PENDING = "pending"
STATUS_PROCESSING = "processing"
STATUS_SENT = "sent"


def sincronizar_envios_elegiveis(cursor, *, limite=100):
    """Materializa conversas elegíveis ainda não enviadas na fila local."""
    _validar_inteiro_positivo(limite, "limite")

    cursor.execute(
        """
        INSERT INTO chatbot.funil_envios (id_conversa)
        SELECT elegiveis.id_conversa
        FROM (
            SELECT c.id_conversa
            FROM chatbot.conversa c
            JOIN chatbot.unidade_atendimento u ON u.id_unidade = c.id_unidade
            JOIN chatbot.etapa e
              ON e.id_etapa = c.id_etapa_atual
            JOIN chatbot.integracao_funil_unidade integracao
              ON integracao.id_unidade = c.id_unidade
            WHERE e.elegivel_funil = TRUE
              AND (
                (NULLIF(BTRIM(u.link_agendamento), '') IS NOT NULL
                 AND c.id_etapa_atual >= 20)
                OR (NULLIF(BTRIM(u.link_agendamento), '') IS NULL
                    AND (c.id_etapa_atual = 19 OR c.id_etapa_atual >= 21))
              )
              AND c.lead_no_funil IS NOT TRUE
              AND integracao.integracao_ativa = TRUE
              AND integracao.widget_ativo = TRUE
              AND NOT EXISTS (
                    SELECT 1
                    FROM chatbot.funil_envios fe_existente
                    WHERE fe_existente.id_conversa = c.id_conversa
              )
            ORDER BY c.id_conversa ASC
            LIMIT %s
        ) AS elegiveis
        ON CONFLICT (id_conversa) DO NOTHING
        RETURNING id_funil_envio;
        """,
        (limite,),
    )

    return len(cursor.fetchall())


def reivindicar_proximo_envio(cursor, *, lease_segundos=900):
    """Reserva um lead com SKIP LOCKED e recupera leases abandonados."""
    _validar_inteiro_positivo(lease_segundos, "lease_segundos")

    cursor.execute(
        """
        WITH proximo AS (
            SELECT fe.id_funil_envio
            FROM chatbot.funil_envios fe
            JOIN chatbot.conversa c
              ON c.id_conversa = fe.id_conversa
            JOIN chatbot.unidade_atendimento u ON u.id_unidade = c.id_unidade
            JOIN chatbot.etapa e
              ON e.id_etapa = c.id_etapa_atual
            JOIN chatbot.integracao_funil_unidade integracao
              ON integracao.id_unidade = c.id_unidade
            WHERE (
                    (
                        fe.status = 'pending'
                        AND fe.next_attempt_at <= NOW()
                    )
                    OR
                    (
                        fe.status = 'processing'
                        AND fe.processing_started_at
                            < NOW() - (%s * INTERVAL '1 second')
                    )
                  )
              AND e.elegivel_funil = TRUE
              AND (
                (NULLIF(BTRIM(u.link_agendamento), '') IS NOT NULL
                 AND c.id_etapa_atual >= 20)
                OR (NULLIF(BTRIM(u.link_agendamento), '') IS NULL
                    AND (c.id_etapa_atual = 19 OR c.id_etapa_atual >= 21))
              )
              AND c.lead_no_funil IS NOT TRUE
              AND integracao.integracao_ativa = TRUE
              AND integracao.widget_ativo = TRUE
            -- Novos leads vencem retries; os demais criterios apenas
            -- desempatam registros com a mesma quantidade de tentativas.
            ORDER BY
                fe.attempt_count ASC,
                CASE
                    WHEN fe.status = 'pending' THEN fe.next_attempt_at
                    ELSE fe.processing_started_at
                END ASC,
                fe.id_funil_envio ASC
            FOR UPDATE OF fe SKIP LOCKED
            LIMIT 1
        )
        UPDATE chatbot.funil_envios fe
        SET
            status = 'processing',
            attempt_count = fe.attempt_count + 1,
            processing_started_at = NOW(),
            ultimo_erro = NULL,
            atualizado_em = NOW()
        FROM proximo
        WHERE fe.id_funil_envio = proximo.id_funil_envio
        RETURNING
            fe.id_funil_envio,
            fe.id_conversa,
            fe.attempt_count;
        """,
        (lease_segundos,),
    )

    resultado = cursor.fetchone()
    if resultado is None:
        return None

    return {
        "id_funil_envio": resultado[0],
        "id_conversa": resultado[1],
        "attempt_count": resultado[2],
    }


def registrar_falha_envio(
    id_funil_envio,
    erro,
    cursor,
    *,
    retry_segundos=3600,
):
    """Libera o lead para nova tentativa sem marcá-lo como enviado."""
    _validar_inteiro_positivo(retry_segundos, "retry_segundos")
    erro_resumido = str(erro)[:4000]

    cursor.execute(
        """
        UPDATE chatbot.funil_envios
        SET
            status = 'pending',
            next_attempt_at = NOW() + (%s * INTERVAL '1 second'),
            processing_started_at = NULL,
            ultimo_erro = %s,
            atualizado_em = NOW()
        WHERE id_funil_envio = %s
          AND status = 'processing'
        RETURNING id_funil_envio;
        """,
        (retry_segundos, erro_resumido, id_funil_envio),
    )

    return cursor.fetchone() is not None


def marcar_envio_como_concluido(
    id_funil_envio,
    id_conversa,
    resposta_funil,
    cursor,
):
    """Confirma conversa e fila no mesmo commit controlado pelo worker.

    O link vigente já foi conferido antes do despacho. Depois do aceite externo,
    adicionar um link não pode apagar o sucesso e provocar um segundo envio.
    """
    cursor.execute(
        """
        UPDATE chatbot.conversa c
        SET lead_no_funil = TRUE
        FROM chatbot.etapa e
        WHERE c.id_conversa = %s
          AND e.id_etapa = c.id_etapa_atual
          AND e.elegivel_funil = TRUE
          AND c.lead_no_funil IS NOT TRUE
        RETURNING c.id_conversa;
        """,
        (id_conversa,),
    )
    if cursor.fetchone() is None:
        raise RuntimeError(
            "Conversa não permaneceu elegível durante a confirmação do Funil"
        )

    cursor.execute(
        """
        UPDATE chatbot.funil_envios
        SET
            status = 'sent',
            processing_started_at = NULL,
            enviado_em = NOW(),
            resposta_funil = %s,
            ultimo_erro = NULL,
            atualizado_em = NOW()
        WHERE id_funil_envio = %s
          AND id_conversa = %s
          AND status = 'processing'
        RETURNING id_funil_envio;
        """,
        (resposta_funil, id_funil_envio, id_conversa),
    )
    if cursor.fetchone() is None:
        raise RuntimeError("Fila do Funil perdeu a reserva antes da confirmação")

    return True


def _validar_inteiro_positivo(valor, nome):
    if not isinstance(valor, int) or valor <= 0:
        raise ValueError(f"{nome} deve ser um inteiro positivo")
```

## Passo 27 — Substituir integralmente `core/repositories/funil/leads.py`

```python
"""Leitura do snapshot completo de uma conversa elegível ao Funil."""


def buscar_dados_lead_funil(id_conversa, cursor):
    """Retorna o snapshot da conversa, inclusive sua profissão histórica.

    ``cliente.profissao`` é mutável entre atendimentos e não participa do lead.
    """
    cursor.execute(
        """
        SELECT
            c.id_conversa,
            c.id_unidade,
            u.nome_unidade,
            COALESCE(c.status_dependente, FALSE) AS status_dependente,
            cl.nome AS nome_cliente,
            cl.waid_telefone AS telefone_cliente,
            cl.email AS email_cliente,
            cl.idade AS idade_cliente,
            c.profissao,
            d.nome_dependente,
            d.idade AS idade_dependente,
            triagem.respostas,
            coleta_email.conteudo_texto AS resposta_email_conversa,
            NULLIF(BTRIM(u.link_agendamento), '') AS link_agendamento,
            c.turno, c.origem_fireads, c.contexto_fireads
        FROM chatbot.conversa c
        JOIN chatbot.cliente cl
          ON cl.id_cliente = c.id_cliente
        JOIN chatbot.unidade_atendimento u
          ON u.id_unidade = c.id_unidade
        JOIN chatbot.etapa etapa_atual
          ON etapa_atual.id_etapa = c.id_etapa_atual
        LEFT JOIN chatbot.dependente d
          ON d.id_conversa = c.id_conversa
        CROSS JOIN LATERAL (
            SELECT
                COALESCE(
                    JSONB_AGG(
                        JSONB_BUILD_OBJECT(
                            'id_etapa', r.id_etapa,
                            'resposta', r.resposta
                        )
                        ORDER BY r.id_etapa
                    ),
                    '[]'::JSONB
                ) AS respostas
            FROM chatbot.respostas_desafios r
            WHERE r.id_conversa = c.id_conversa
              AND r.id_etapa BETWEEN 12 AND 17
        ) AS triagem
        LEFT JOIN LATERAL (
            SELECT mensagem_cliente.conteudo_texto
            FROM chatbot.historico_mensagens mensagem_bot
            JOIN chatbot.historico_mensagens mensagem_cliente
              ON mensagem_cliente.id_conversa = mensagem_bot.id_conversa
             AND mensagem_cliente.quem_enviou = 'cliente'
             AND mensagem_cliente.id_etapa = 10
             AND mensagem_cliente.id_mensagem_fila
                 = mensagem_bot.id_mensagem_fila
             AND mensagem_cliente.id_hash_msg
                 = mensagem_bot.id_hash_cliente_origem
            WHERE mensagem_bot.id_conversa = c.id_conversa
              AND mensagem_bot.quem_enviou = 'bot'
              AND mensagem_bot.status_envio = 'sent'
              AND mensagem_bot.id_etapa = 11
            ORDER BY
                mensagem_bot.received_data_hora DESC,
                mensagem_bot.id_mensagem DESC
            LIMIT 1
        ) AS coleta_email ON TRUE
        WHERE c.id_conversa = %s
          AND etapa_atual.elegivel_funil = TRUE
          AND (
                (NULLIF(BTRIM(u.link_agendamento), '') IS NOT NULL
                 AND c.id_etapa_atual >= 20)
                OR (NULLIF(BTRIM(u.link_agendamento), '') IS NULL
                    AND (c.id_etapa_atual = 19 OR c.id_etapa_atual >= 21))
              )
          AND c.lead_no_funil IS NOT TRUE
        LIMIT 1;
        """,
        (id_conversa,),
    )

    resultado = cursor.fetchone()
    if resultado is None:
        return None

    dados = {
        "link_agendamento": resultado[13],
        "turno": resultado[14],
        "id_conversa": resultado[0],
        "id_unidade": resultado[1],
        "nome_unidade": resultado[2],
        "status_dependente": bool(resultado[3]),
        "nome_cliente": resultado[4],
        "telefone_cliente": resultado[5],
        "email_cliente": resultado[6],
        "idade_cliente": resultado[7],
        "profissao": resultado[8],
        "nome_dependente": resultado[9],
        "idade_dependente": resultado[10],
        "triagem_respostas": resultado[11],
        "resposta_email_conversa": (
            resultado[12] if len(resultado) > 12 else None
        ),
    }

    if len(resultado) > 16 and resultado[15] is not None:
        dados['origem_fireads'] = resultado[15]
        dados['contexto_fireads'] = resultado[16]
        retrato = (resultado[16] or {}).get('dados_titular') or {}
        if 'nome' not in retrato or 'resultado_email' not in retrato:
            raise ValueError('Coletas históricas FireAds incompletas para o Funil')
        dados.update(nome_cliente=retrato['nome'], email_cliente=retrato.get('email'),
                     idade_cliente=retrato.get('idade'), resultado_email_fireads=retrato['resultado_email'])
    return dados
```

## Passo 28 — Substituir integralmente `core/integrations/funil/oportunidades.py`

```python
"""Monta o payload de oportunidade sem conhecer banco ou transações."""

import re
from core.integrations.fireads.contrato import CANAIS
from core.validacoes.email import ResultadoColetaEmail

from core.validacoes.turno import ROTULOS_TURNO, validar_turno

from core.triagem.perguntas import (
    montar_pergunta_triagem,
    obter_faixa_etaria_triagem,
)
from core.validacoes.email import (
    CLASSIFICACAO_EMAIL_AUSENTE,
    CLASSIFICACAO_EMAIL_NAO_INFORMADO,
    CLASSIFICACAO_EMAIL_VALIDO,
    classificar_resposta_email_aceita,
)


ORIGEM_LEAD_CHATBOT = "Meta Chatbot"
TITULO_OPORTUNIDADE = "Chatbot Lead"

ETAPAS_TRIAGEM_ESPERADAS = tuple(range(12, 18))
RESPOSTAS_TRIAGEM_EXIBICAO = {
    "nunca": "Nunca",
    "às vezes": "Às vezes",
    "as vezes": "Às vezes",
    "frequentemente": "Frequentemente",
}

MARCADORES_API_CARROSSEL = {
    "codigo_vendedor": "Code_User",
    "codigo_metodologia": "Code_Methodology",
    "codigo_canal_venda": "Code_Channel",
    "codigo_etapa": "Code_StepMethodology",
}

PADRAO_TELEFONE_BRASIL = re.compile(
    r"^55(?P<ddd>[1-9]\d)(?P<numero>\d{8,9})$"
)
AVISO_TELEFONE_INTERNACIONAL = (
    "O cliente possui um número internacional fora do padrão brasileiro, "
    "por isso o campo Telefone 1 não foi preenchido."
)


def montar_payload_oportunidade(dados_lead):
    """Converte o snapshot validado do atendimento no contrato ApiCarrossel."""
    _validar_dados_lead(dados_lead)

    nome_cliente = dados_lead["nome_cliente"].strip()
    nome_unidade = dados_lead["nome_unidade"].strip()
    titulo = f"{TITULO_OPORTUNIDADE} {nome_unidade}"
    nome_destaque = _montar_nome_destaque(dados_lead)
    telefone_funil = _normalizar_telefone_brasileiro(
        dados_lead["telefone_cliente"]
    )
    resultado_email = _resolver_resultado_email_conversa(dados_lead)
    observacoes = montar_observacoes_lead(
        dados_lead,
        resultado_email=resultado_email,
    )

    return {
        "oportunidades": [
            {
                "titulo": titulo,
                "valor": "0",
                **MARCADORES_API_CARROSSEL,
                "personalizados": [
                    {
                        "titulo": "Observações",
                        "valor": observacoes,
                    },
                    {
                        "titulo": "Origem do lead",
                        "valor": CANAIS[dados_lead["origem_fireads"]][0] if dados_lead.get("origem_fireads") else ORIGEM_LEAD_CHATBOT,
                    },
                ],
                "empresa": {
                    # O CRM usa empresa.nome como destaque principal do card.
                    "nome": nome_destaque,
                    "cnpj": "",
                    "codigo_segmento": "0",
                    "endereco_completo": {
                        "logradouro": "",
                        "numero": "",
                        "complemento": "",
                        "bairro": "",
                        "cidade": "",
                        "uf": "",
                        "cep": "",
                    },
                    "personalizados": [],
                },
                "contato": {
                    "nome": nome_cliente,
                    # Ausência é representada pelo valor vazio já usado no
                    # contrato do projeto; placeholders nunca ocupam o campo.
                    "email": resultado_email.email or "",
                    "telefone1": telefone_funil,
                    "telefone2": "",
                    "cargo": "",
                    "cpf": "",
                    "personalizados": [],
                },
            }
        ]
    }


def montar_observacoes_lead(dados_lead, *, resultado_email=None):
    """Produz o resumo humano exibido pela oportunidade no CRM."""
    nome_cliente = dados_lead["nome_cliente"].strip()
    telefone_cliente = dados_lead["telefone_cliente"].strip()
    profissao = str(dados_lead.get("profissao") or "").strip()
    profissao = profissao or "Não informada"
    aviso_telefone = ""
    resultado_email = resultado_email or _resolver_resultado_email_conversa(
        dados_lead
    )
    email_exibicao = _montar_email_exibicao(resultado_email)

    if not _normalizar_telefone_brasileiro(telefone_cliente):
        aviso_telefone = f"\n{AVISO_TELEFONE_INTERNACIONAL}\n"

    tem_link = bool(str(dados_lead.get("link_agendamento") or "").strip())
    orientacao = (
        "Confira sua plataforma de reserva (como o Calendly) e o painel de monitoramento."
        if tem_link else
        "Confira o painel de monitoramento e o número comercial para verificar se o cliente enviou mensagem."
    )
    turno = dados_lead.get("turno")
    if turno is not None:
        validar_turno(turno)
    preferencia = f"- Turno de preferência: {ROTULOS_TURNO[turno]}\n" if turno else ""
    canal = f"Canal de venda: {CANAIS[dados_lead['origem_fireads']][0]}\n\n" if dados_lead.get("origem_fireads") else ""
    cabecalho = (
        "------NOVO LEAD-------\n\n"
        f"{canal}"
        "Cliente concluiu a triagem cognitiva pelo chatbot. "
        f"{orientacao} A disponibilidade e a efetivação de sua reserva devem ser conferidas pela equipe.\n\n"
        f"{preferencia}"
        f"- Nome do cliente: {nome_cliente}\n"
        f"- Telefone/WhatsApp do cliente: "
        f"{telefone_cliente}\n"
        f"- E-mail do cliente: {email_exibicao}\n"
    )

    if dados_lead["status_dependente"]:
        dados_pessoa = (
            f"\nO atendimento é para um dependente de {nome_cliente}:\n\n"
            f"- Nome do dependente: "
            f"{dados_lead['nome_dependente'].strip()}\n"
            f"- Idade do dependente: {dados_lead['idade_dependente']}\n"
        )
    else:
        dados_pessoa = f"- Idade do cliente: {dados_lead['idade_cliente']}\n"

    triagem = _montar_perguntas_e_respostas_triagem(dados_lead)

    dados_profissao = f"\n- Profissão: {profissao}\n"

    return (
        cabecalho
        + dados_pessoa
        + aviso_telefone
        + dados_profissao
        + triagem
    )


def _montar_perguntas_e_respostas_triagem(dados_lead):
    respostas = _obter_respostas_triagem_validadas(dados_lead)

    if dados_lead["status_dependente"]:
        idade_pessoa = dados_lead["idade_dependente"]
        nome_dependente = dados_lead["nome_dependente"].strip()
    else:
        idade_pessoa = dados_lead["idade_cliente"]
        nome_dependente = None

    faixa_etaria = obter_faixa_etaria_triagem(idade_pessoa)
    blocos = []

    for numero, item in enumerate(respostas, start=1):
        pergunta = montar_pergunta_triagem(
            item["id_etapa"],
            faixa_etaria=faixa_etaria,
            nome_dependente=nome_dependente,
        )
        blocos.append(
            f"-Pergunta {numero}:\n\n"
            f"{pergunta}\n\n"
            f"Resposta: {item['resposta_exibicao']}"
        )

    return "\nPerguntas e respostas da triagem:\n\n" + "\n\n".join(blocos)


def _montar_nome_destaque(dados_lead):
    """Monta a linha principal do card conforme a pessoa atendida."""
    nome_cliente = dados_lead["nome_cliente"].strip()

    if dados_lead["status_dependente"]:
        return " | ".join(
            (
                nome_cliente,
                dados_lead["nome_dependente"].strip(),
                str(dados_lead["idade_dependente"]),
            )
        )

    return " | ".join((nome_cliente, str(dados_lead["idade_cliente"])))


def _normalizar_telefone_brasileiro(telefone):
    """Prepara o wa_id brasileiro para o campo Telefone 1 do CRM."""
    somente_digitos = re.sub(r"\D", "", str(telefone or ""))
    correspondencia = PADRAO_TELEFONE_BRASIL.fullmatch(somente_digitos)

    if correspondencia is None:
        return ""

    numero = correspondencia.group("numero")

    if len(numero) == 8:
        numero = f"9{numero}"
    elif not numero.startswith("9"):
        return ""

    return f"55{correspondencia.group('ddd')}{numero}"


def _validar_dados_lead(dados_lead):
    obrigatorios = (
        "id_conversa",
        "id_unidade",
        "nome_unidade",
        "nome_cliente",
        "telefone_cliente",
    )
    ausentes = [campo for campo in obrigatorios if not dados_lead.get(campo)]

    if ausentes:
        raise ValueError(
            "Dados obrigatórios ausentes para criar a oportunidade: "
            + ", ".join(ausentes)
        )

    _obter_respostas_triagem_validadas(dados_lead)

    if dados_lead.get("status_dependente"):
        if not dados_lead.get("nome_dependente"):
            raise ValueError("Nome do dependente ausente")
        if dados_lead.get("idade_dependente") is None:
            raise ValueError("Idade do dependente ausente")
    elif dados_lead.get("idade_cliente") is None:
        raise ValueError("Idade do cliente ausente")


def _resolver_resultado_email_conversa(dados_lead):
    if dados_lead.get('origem_fireads'):
        classificacao = dados_lead['resultado_email_fireads']
        if classificacao not in {CLASSIFICACAO_EMAIL_VALIDO, CLASSIFICACAO_EMAIL_AUSENTE, CLASSIFICACAO_EMAIL_NAO_INFORMADO}:
            raise ValueError('Resultado histórico de email inválido')
        return ResultadoColetaEmail(aceita=True, classificacao=classificacao, email=dados_lead.get('email_cliente'))

    resposta_historica = dados_lead.get("resposta_email_conversa")

    if resposta_historica is not None:
        return classificar_resposta_email_aceita(resposta_historica)

    # Compatibilidade com atendimentos legados que não possuem o vínculo
    # histórico da resposta de e-mail. Dados novos sempre usam a conversa.
    email_cadastro = dados_lead.get("email_cliente")
    if email_cadastro:
        return classificar_resposta_email_aceita(email_cadastro)

    return classificar_resposta_email_aceita("")


def _montar_email_exibicao(resultado_email):
    if resultado_email.classificacao == CLASSIFICACAO_EMAIL_VALIDO:
        return resultado_email.email

    if resultado_email.classificacao == CLASSIFICACAO_EMAIL_AUSENTE:
        return "não tem"

    if resultado_email.classificacao == CLASSIFICACAO_EMAIL_NAO_INFORMADO:
        return "não informado"

    raise ValueError(
        "Classificação de e-mail inválida para observações do Funil "
        f"(classificacao={resultado_email.classificacao!r})"
    )


def _obter_respostas_triagem_validadas(dados_lead):
    respostas = dados_lead.get("triagem_respostas")

    if not isinstance(respostas, (list, tuple)):
        raise ValueError("Respostas da triagem ausentes ou inválidas")

    ids_etapas = []
    respostas_validadas = []

    for item in respostas:
        if not isinstance(item, dict):
            raise ValueError("Item de resposta da triagem inválido")

        id_etapa = item.get("id_etapa")
        resposta = item.get("resposta")
        resposta_normalizada = str(resposta or "").strip().casefold()

        ids_etapas.append(id_etapa)

        if resposta_normalizada not in RESPOSTAS_TRIAGEM_EXIBICAO:
            raise ValueError(
                "A triagem contém resposta fora do domínio esperado "
                f"(etapa={id_etapa}, resposta={resposta})"
            )

        respostas_validadas.append(
            {
                "id_etapa": id_etapa,
                "resposta": resposta_normalizada,
                "resposta_exibicao": RESPOSTAS_TRIAGEM_EXIBICAO[
                    resposta_normalizada
                ],
            }
        )

    if tuple(ids_etapas) != ETAPAS_TRIAGEM_ESPERADAS:
        raise ValueError(
            "A oportunidade exige respostas ordenadas para as etapas "
            "12, 13, 14, 15, 16 e 17"
        )

    return respostas_validadas
```

## Passo 29 — Criar `workers/worker_funil/fireads.py`

```python
"""Entrega independente, depois do Funil. Reconsulta antes de qualquer escrita."""

import hashlib
import logging
import psycopg
from core.integrations.fireads.cliente import ClienteFireAds
from core.integrations.fireads.contrato import (
    CANAIS,
    ErroFireAds,
    telefone,
    localizar,
    bloco_observacoes,
    acrescentar_observacoes,
)
from core.repositories.fireads.envios import (
    reservar,
    conferir_posse,
    concluir,
    reagendar,
)

logger = logging.getLogger("worker.funil.fireads")


def preparar_escrita(rows, snapshot, bloco):
    acrescentar_observacoes(None, bloco)  # Mesmo limite no append e no update.
    encontrados = localizar(rows, snapshot["telefone"], "WhatsApp")
    if len(encontrados) > 1:
        # Nunca escolher arbitrariamente uma pessoa/linha duplicada preexistente.
        raise ErroFireAds("Mais de uma linha de destino para este telefone")
    if encontrados:
        row = encontrados[0]
        if "Observação" not in row:
            raise ErroFireAds(
                "Observação ausente na leitura do registro; não sobrescrever"
            )
        email_existente = str(row.get("Email") or "").strip().casefold()
        email_novo = str(snapshot.get("email") or "").strip().casefold()
        if email_existente and email_novo and email_existente != email_novo:
            raise ErroFireAds(
                "Mesmo telefone com emails diferentes; conferir identidade"
            )
        numero_linha = row.get("_row")
        if type(numero_linha) is not int or numero_linha < 2:
            raise ErroFireAds("Linha de destino inválida")
        observacoes, mudou = acrescentar_observacoes(row.get("Observação"), bloco)
        return {"row": numero_linha, "observacoes": observacoes} if mudou else None
    # Um e-mail já presente com outro telefone não é identidade suficiente para
    # alterar outra pessoa nem para criar silenciosamente um possível duplicado.
    email = str(snapshot.get("email") or "").strip().casefold()
    if email and any(
        str(r.get("Email") or "").strip().casefold() == email for r in rows
    ):
        raise ErroFireAds("Email já presente em outro telefone; conferir identidade")
    return {
        "dados": {
            "Nome": snapshot["nome"],
            "Email": snapshot["email"],
            "WhatsApp": telefone(snapshot["telefone"]),
            "Perfil/Faixa": snapshot["perfil"],
            "Canal": CANAIS[snapshot["origem"]][0],
            "Observação": bloco,
        }
    }


def processar(envio, conn, cursor):
    snapshot = envio["snapshot"]
    # Lock de sessão (não de transação): serializa nossos envios ao mesmo contato,
    # sem manter transação aberta durante HTTP. Outros sistemas não usam este lock.
    identidade = f"fireads:{envio['integracao']}:{telefone(snapshot['telefone'])}"
    chave = int.from_bytes(
        hashlib.sha256(identidade.encode()).digest()[:8], "big", signed=True
    )
    bloqueado = False
    cliente = None
    try:
        cursor.execute("SELECT pg_try_advisory_lock(%s)", (chave,))
        bloqueado = cursor.fetchone()[0]
        if not bloqueado:
            raise ErroFireAds("Outro envio deste contato está em andamento")
        conferir_posse(envio, cursor)
        conn.commit()
        cliente = ClienteFireAds(snapshot["url"], segundos=40)
        dados = cliente.consultar(snapshot["aba"])
        if not {"Nome", "Email", "WhatsApp", "Observação"} <= set(dados["headers"]):
            raise ErroFireAds("Cabeçalhos de destino incompletos")
        bloco = bloco_observacoes(
            envio["integracao"], envio["conversa"], snapshot["observacoes"]
        )
        operacao = preparar_escrita(dados["rows"], snapshot, bloco)
        conferir_posse(envio, cursor)
        conn.commit()
        recibo = (
            {"success": True, "reconciliado": True}
            if operacao is None
            else cliente.enviar(snapshot["aba"], **operacao)
        )
        concluir(envio, recibo, cursor)
        conn.commit()
        logger.info(
            "dash_enviado | conversa=%s tentativa=%s",
            envio["conversa"],
            envio["tentativa"],
        )
        return True
    except psycopg.Error:
        conn.rollback()
        raise
    except Exception as exc:
        conn.rollback()
        # Armazenar apenas erros de contrato controlados, sem URLs ou corpos externos.
        seguro = (
            exc if isinstance(exc, ErroFireAds) else ErroFireAds(type(exc).__name__)
        )
        reagendar(envio, seguro, cursor)
        conn.commit()
        logger.warning(
            "dash_pendente | conversa=%s tipo=%s", envio["conversa"], type(exc).__name__
        )
        return False
    finally:
        if cliente:
            cliente.close()
        if bloqueado and not conn.closed:
            cursor.execute("SELECT pg_advisory_unlock(%s)", (chave,))
            conn.commit()


def processar_lote(conn, cursor, limite=100):
    resumo = {"processados": 0, "enviados": 0, "falhas": 0}
    for _ in range(limite):
        envio = reservar(cursor)
        conn.commit()
        if envio is None:
            break
        resumo["processados"] += 1
        resumo["enviados" if processar(envio, conn, cursor) else "falhas"] += 1
    return resumo
```

## Passo 30 — Substituir integralmente `workers/worker_funil/funil_worker.py`

```python
"""Executa continuamente os ciclos de publicacao de leads no Funil."""

import logging
from workers.worker_funil.fireads import processar_lote
import time

import psycopg

from core.database.connection_aws import get_conn
from core.repositories.funil.envios import (
    reivindicar_proximo_envio,
    sincronizar_envios_elegiveis,
)
from workers.tratamento_erros_externos.erro_conexao import handle_erro_conexao
from workers.worker_funil.config import (
    FUNIL_INTERVALO_SEGUNDOS,
    FUNIL_LEASE_SEGUNDOS,
    FUNIL_LIMITE_POR_CICLO,
)
from workers.worker_funil.processamento import processar_envio_funil


logger = logging.getLogger("worker.funil")


def funil_worker():
    """Mantem o Funil ativo e recupera falhas operacionais esperadas."""
    logger.info(
        "funil_worker_iniciado | intervalo_segundos=%s limite_por_ciclo=%s",
        FUNIL_INTERVALO_SEGUNDOS,
        FUNIL_LIMITE_POR_CICLO,
    )
    retry_conexao = 5

    while True:
        try:
            logger.info("funil_ciclo_iniciando")
            resumo = executar_ciclo_funil()
            retry_conexao = 5

            logger.info(
                "funil_ciclo_concluido | acao=aguardar_proximo "
                "materializados=%s processados=%s enviados=%s falhas=%s "
                "limite_por_ciclo=%s aguardar=%ss",
                resumo["materializados"],
                resumo["processados"],
                resumo["enviados"],
                resumo["falhas"],
                FUNIL_LIMITE_POR_CICLO,
                FUNIL_INTERVALO_SEGUNDOS,
            )
            print("PROXIMO CICLO EM 30 MINUTOS")
            time.sleep(FUNIL_INTERVALO_SEGUNDOS)

        except KeyboardInterrupt:
            logger.info("funil_worker_interrompido | acao=encerrar")
            raise

        except psycopg.OperationalError as erro:
            # Falha esperada: o proprio worker aguarda e abre uma nova conexao.
            retry_conexao = handle_erro_conexao(
                erro,
                retry_conexao,
                incremento_retry=5,
            )


def executar_ciclo_funil():
    """Materializa e processa um lote; cada reserva é commitada isoladamente."""
    conn = None
    cursor = None
    resumo = {
        "materializados": 0,
        "processados": 0,
        "enviados": 0,
        "falhas": 0,
    }

    try:
        conn = get_conn(application_name="worker_funil")
        cursor = conn.cursor()

        resumo["materializados"] = sincronizar_envios_elegiveis(
            cursor,
            limite=FUNIL_LIMITE_POR_CICLO,
        )
        conn.commit()

        for _ in range(FUNIL_LIMITE_POR_CICLO):
            envio = reivindicar_proximo_envio(
                cursor,
                lease_segundos=FUNIL_LEASE_SEGUNDOS,
            )
            conn.commit()

            if envio is None:
                break

            resumo["processados"] += 1
            if processar_envio_funil(envio, conn, cursor):
                resumo["enviados"] += 1
            else:
                resumo["falhas"] += 1
            print("---------------PROXIMO ENVIO------------------")

        # Fila independente: tentativas de dashboard não dependem de haver
        # novos leads elegíveis ao Funil neste ciclo.
        resumo['dash'] = processar_lote(conn, cursor, FUNIL_LIMITE_POR_CICLO)
        logger.info('dash_ciclo | %s', resumo['dash'])
        return resumo

    except Exception:
        if conn:
            conn.rollback()
        raise

    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()
```

## Passo 31 — Substituir integralmente `workers/worker_funil/processamento.py`

```python
"""Processa uma reserva do Funil preservando a fronteira transacional."""

import json
from core.repositories.fireads.envios import congelar
import logging

import psycopg

from core.integrations.funil.cliente import enviar_oportunidade
from core.integrations.funil.oportunidades import montar_payload_oportunidade
from core.repositories.funil.envios import (
    marcar_envio_como_concluido,
    registrar_falha_envio,
)
from core.repositories.funil.integracao import (
    buscar_integracao_funil_por_unidade,
)
from core.repositories.funil.leads import buscar_dados_lead_funil
from workers.worker_funil.config import (
    FUNIL_HTTP_TIMEOUT,
    FUNIL_RETRY_LEAD_SEGUNDOS,
)
from workers.worker_funil.exceptions import BancoFalhouAposEnvioFunil


logger = logging.getLogger("worker.funil.processamento")


def processar_envio_funil(envio, conn, cursor):
    """Envia um lead reservado; erros externos ficam para o próximo ciclo."""
    id_funil_envio = envio["id_funil_envio"]
    id_conversa = envio["id_conversa"]
    sucesso_externo = False

    try:
        dados_lead = buscar_dados_lead_funil(id_conversa, cursor)
        if dados_lead is None:
            raise ValueError("Conversa não está mais elegível ao Funil")

        integracao = buscar_integracao_funil_por_unidade(
            dados_lead["id_unidade"],
            cursor,
        )
        _validar_integracao_ativa(integracao)

        payload = montar_payload_oportunidade(dados_lead)
        payload, canal, url_funil = congelar(dados_lead, payload, integracao, cursor)

        # O SELECT não deve manter uma transação aberta durante a chamada HTTP.
        conn.commit()

        resultado = enviar_oportunidade(
            link_api_carrossel=url_funil,
            codigo_canal_venda=canal,
            payload=payload,
            timeout=FUNIL_HTTP_TIMEOUT,
        )
        sucesso_externo = True

        # JANELA RARA CONHECIDA:
        # o Funil já confirmou a oportunidade, mas o banco ainda não marcou
        # lead_no_funil. Se o processo ou o banco cair exatamente aqui, o lease
        # permitirá uma nova tentativa e poderá gerar duplicidade. A futura
        # reconciliação por título [C{id_conversa}] deve fechar essa janela.
        resposta_serializada = json.dumps(
            resultado["resposta"],
            ensure_ascii=False,
        )[:4000]
        marcar_envio_como_concluido(
            id_funil_envio,
            id_conversa,
            resposta_serializada,
            cursor,
        )
        conn.commit()

        logger.info(
            "funil_lead_enviado | acao=confirmar_envio "
            "id_funil_envio=%s id_conversa=%s tentativa=%s status_http=%s",
            id_funil_envio,
            id_conversa,
            envio["attempt_count"],
            resultado["status_http"],
        )
        return True

    except psycopg.Error:
        conn.rollback()
        if sucesso_externo:
            logger.critical(
                "funil_banco_falhou_apos_envio | acao=preservar_processing "
                "id_funil_envio=%s id_conversa=%s",
                id_funil_envio,
                id_conversa,
                exc_info=True,
            )
            raise BancoFalhouAposEnvioFunil(
                "Banco falhou depois de o Funil confirmar a oportunidade"
            )
        raise

    except Exception as exc:
        conn.rollback()

        if sucesso_externo:
            logger.critical(
                "funil_estado_local_falhou_apos_envio | "
                "acao=preservar_processing id_funil_envio=%s id_conversa=%s "
                "erro=%s",
                id_funil_envio,
                id_conversa,
                exc,
            )
            raise BancoFalhouAposEnvioFunil(
                "Estado local falhou depois de o Funil confirmar o lead"
            ) from exc

        try:
            registrado = registrar_falha_envio(
                id_funil_envio,
                exc,
                cursor,
                retry_segundos=FUNIL_RETRY_LEAD_SEGUNDOS,
            )
            if not registrado:
                raise RuntimeError(
                    "Não foi possível devolver o lead reservado para pending"
                )
            conn.commit()
        except Exception:
            conn.rollback()
            raise

        logger.exception(
            "funil_lead_falhou | acao=reagendar_proximo_ciclo "
            "id_funil_envio=%s id_conversa=%s tentativa=%s erro=%s",
            id_funil_envio,
            id_conversa,
            envio["attempt_count"],
            exc,
        )
        return False


def _validar_integracao_ativa(integracao):
    if integracao is None:
        raise ValueError("Unidade sem configuração do Funil")
    if not integracao["integracao_ativa"]:
        raise ValueError("Integração do Funil está desativada para a unidade")
    if not integracao["widget_ativo"]:
        raise ValueError("Widget do Funil está desativado para a unidade")
```

## Passo 32 — Substituir integralmente `core/repositories/atendimento/followup.py`

```python
"""Consultas de follow-up e fencing; commit/rollback pertencem ao orquestrador."""


class LockConversaPerdido(RuntimeError):
    """O processamento deixou de possuir a versão válida do lock."""


def proteger_conversa(id_conversa, lock_version, cursor, *, renovar=False):
    cursor.execute(
        """
        SELECT id_conversa FROM chatbot.conversa
        WHERE id_conversa = %s AND processing IS TRUE AND lock_version = %s
          AND processing_started_at > clock_timestamp() - INTERVAL '110 seconds'
        FOR UPDATE;
    """,
        (id_conversa, lock_version),
    )
    if cursor.fetchone() is None:
        raise LockConversaPerdido(
            f"Lock perdido: conversa={id_conversa}, versao={lock_version}"
        )
    if renovar:
        cursor.execute(
            """
            UPDATE chatbot.conversa SET processing_started_at = clock_timestamp()
            WHERE id_conversa = %s AND lock_version = %s AND processing IS TRUE;
        """,
            (id_conversa, lock_version),
        )


def reler_conversa(contexto_banco, lock_version, cursor):
    anterior = contexto_banco["conversa"]
    proteger_conversa(anterior["id_conversa"], lock_version, cursor)
    cursor.execute(
        """
        SELECT id_etapa_atual, status_ativa, status_dependente, last_message_from,
               followup_stage, followup_last_sent_at, lead_no_funil, finalizou_em
        FROM chatbot.conversa
        WHERE id_conversa = %s AND id_cliente = %s AND id_unidade = %s;
    """,
        (
            anterior["id_conversa"],
            contexto_banco["id_cliente"],
            contexto_banco["id_unidade"],
        ),
    )
    row = cursor.fetchone()
    if row is None or row[1] is not True or row[7] is not None:
        raise LockConversaPerdido(
            "Conversa deixou de ser ativa para este cliente/unidade"
        )
    campos = (
        "id_etapa_atual",
        "status_ativa",
        "status_dependente",
        "last_message_from",
        "followup_stage",
        "followup_last_sent_at",
        "lead_no_funil",
        "finalizou_em",
    )
    conversa = dict(anterior, **dict(zip(campos, row)), lock_version=lock_version)
    stage = conversa["followup_stage"] or 0
    if stage < 0:
        raise ValueError("followup_stage negativo; requer saneamento explícito")
    return dict(contexto_banco, conversa=conversa)


def buscar_contexto_repeticao(id_conversa, id_unidade, cursor):
    cursor.execute(
        """
        SELECT cl.nome, d.nome_dependente, d.idade, u.nome_unidade, u.nome_agente,
               u.genero, u.link_agendamento, u.link_instagram,
               c.status_dependente,
               c.turno, cl.idade, u.numero_comercial, e.encerra_automaticamente
        FROM chatbot.conversa c
        JOIN chatbot.cliente cl ON cl.id_cliente = c.id_cliente
        JOIN chatbot.unidade_atendimento u ON u.id_unidade = c.id_unidade
        JOIN chatbot.etapa e ON e.id_etapa = c.id_etapa_atual
        LEFT JOIN chatbot.dependente d ON d.id_conversa = c.id_conversa
        WHERE c.id_conversa = %s AND c.id_unidade = %s AND c.status_ativa IS TRUE;
    """,
        (id_conversa, id_unidade),
    )
    row = cursor.fetchone()
    if not row or row[-1]:
        raise ValueError("Etapa inexistente, encerrada ou terminal para repetição")
    return dict(
        zip(
            (
                "nome_titular",
                "nome_dependente",
                "idade_dependente",
                "nome_unidade",
                "nome_agente",
                "genero",
                "link_agendamento",
                "link_instagram",
                "status_dependente",
                "turno",
                "idade_cliente",
                "numero_comercial",
                "terminal",
            ),
            row,
        )
    )


def buscar_retomada(id_conversa, mensagem, cursor):
    cursor.execute(
        """
        SELECT id_etapa, stage_anterior, followup_em, concluida_em
        FROM chatbot.followup_retomada
        WHERE id_conversa = %s AND id_mensagem_fila = %s AND id_hash_cliente = %s;
    """,
        (id_conversa, mensagem["id_mensagem"], mensagem["id_hash"]),
    )
    row = cursor.fetchone()
    return (
        dict(zip(("id_etapa", "stage_anterior", "followup_em", "concluida_em"), row))
        if row
        else None
    )


def registrar_retomada(conversa, mensagem, cursor):
    cursor.execute(
        """
        INSERT INTO chatbot.followup_retomada
            (id_conversa, id_mensagem_fila, id_hash_cliente, id_etapa, stage_anterior, followup_em)
        VALUES (%s, %s, %s, %s, %s, %s);
    """,
        (
            conversa["id_conversa"],
            mensagem["id_mensagem"],
            mensagem["id_hash"],
            conversa["id_etapa_atual"],
            conversa["followup_stage"],
            conversa["followup_last_sent_at"],
        ),
    )


def concluir_retomada(contexto, data_bot, cursor, *, id_etapa_resultante=None):
    """Conclui o ciclo após a resposta, na etapa repetida ou no destino autorizado."""
    etapa_esperada = (
        contexto["id_etapa_atual"]
        if id_etapa_resultante is None
        else id_etapa_resultante
    )
    proteger_conversa(contexto["id_conversa"], contexto["lock_version"], cursor)
    cursor.execute(
        """
        UPDATE chatbot.conversa
        SET followup_stage = 0, last_message_from = 'bot', last_interaction_at = %s
        WHERE id_conversa = %s AND lock_version = %s AND processing IS TRUE
          AND status_ativa IS TRUE AND finalizou_em IS NULL AND id_etapa_atual = %s
          AND followup_stage = %s AND followup_last_sent_at IS NOT DISTINCT FROM %s;
    """,
        (
            data_bot,
            contexto["id_conversa"],
            contexto["lock_version"],
            etapa_esperada,
            contexto["stage_anterior"],
            contexto["followup_em"],
        ),
    )
    if cursor.rowcount != 1:
        raise LockConversaPerdido(
            "Ciclo de follow-up mudou antes da confirmação da retomada"
        )
    msg = contexto["mensagem_cliente_atual"]
    cursor.execute(
        """
        UPDATE chatbot.followup_retomada SET concluida_em = %s
        WHERE id_conversa = %s AND id_mensagem_fila = %s AND id_hash_cliente = %s
          AND concluida_em IS NULL;
    """,
        (
            data_bot,
            contexto["id_conversa"],
            msg["id_mensagem_fila"],
            msg["id_hash_msg"],
        ),
    )
    if cursor.rowcount != 1:
        raise ValueError("Registro da retomada ausente ou já concluído")


# O SELECT é reexecutado com a posse do lock imediatamente antes do despacho.
# Pendências são filtradas pelo par cliente/unidade, inclusive sem id_conversa.
CONSULTA_ELEGIVEIS = """
    SELECT c.id_conversa, c.id_cliente, c.id_unidade, c.id_etapa_atual,
           cl.waid_telefone, u.phone_number_id, u.telefone,
           b.id_mensagem AS id_ancora, b.received_data_hora AS ancora_em,
           COALESCE(c.followup_stage, 0), cl.nome, u.nome_agente,
           c.status_dependente, d.nome_dependente
    FROM chatbot.conversa c
    JOIN chatbot.cliente cl ON cl.id_cliente = c.id_cliente
    JOIN chatbot.unidade_atendimento u ON u.id_unidade = c.id_unidade
    JOIN chatbot.etapa e ON e.id_etapa = c.id_etapa_atual
    LEFT JOIN chatbot.dependente d ON d.id_conversa = c.id_conversa
    JOIN LATERAL (
        SELECT h.id_mensagem, h.received_data_hora
        FROM chatbot.historico_mensagens h
        WHERE h.id_conversa = c.id_conversa AND h.quem_enviou = 'bot' AND h.status_envio = 'sent'
        ORDER BY h.received_data_hora DESC, h.id_mensagem DESC LIMIT 1
    ) b ON TRUE
    WHERE c.status_ativa IS TRUE AND c.finalizou_em IS NULL
      AND (c.id_etapa_atual BETWEEN 1 AND 17 OR
           (c.id_etapa_atual = 18 AND NULLIF(TRIM(u.link_agendamento), '') IS NULL))
      AND e.encerra_automaticamente IS FALSE
      AND COALESCE(c.followup_stage, 0) IN (0, 1) AND c.last_message_from = 'bot'
      AND c.last_interaction_at = b.received_data_hora
      AND b.received_data_hora <= clock_timestamp() - INTERVAL '7 hours'
      AND c.turnos_sem_avanco < 12 AND u.status_pagamento IS TRUE
      AND NULLIF(TRIM(cl.waid_telefone), '') IS NOT NULL
      AND NULLIF(TRIM(u.phone_number_id), '') IS NOT NULL
      AND NULLIF(TRIM(u.telefone), '') IS NOT NULL

      AND NOT EXISTS (
          SELECT 1 FROM chatbot.conversa anterior
          JOIN chatbot.etapa terminal ON terminal.id_etapa = anterior.id_etapa_atual
          WHERE anterior.id_cliente = c.id_cliente AND anterior.id_unidade = c.id_unidade
            AND anterior.status_ativa IS FALSE AND terminal.bloqueio_dias > 0
            AND anterior.finalizou_em > clock_timestamp() - terminal.bloqueio_dias * INTERVAL '1 day'
      )
      AND NOT EXISTS (
          SELECT 1 FROM chatbot.webhook_flood_evento f
          WHERE f.wa_id_cliente = cl.waid_telefone AND f.phone_id_unidade = u.phone_number_id
            AND f.received_at >= clock_timestamp() - INTERVAL '5 seconds'
          GROUP BY f.wa_id_cliente, f.phone_id_unidade HAVING COUNT(*) >= 15
      )
      AND NOT EXISTS (
          SELECT 1 FROM chatbot.cliente_bloqueado_meta x
          WHERE x.wa_id_cliente = cl.waid_telefone AND x.phone_id_unidade = u.phone_number_id
      )
      AND NOT EXISTS (
          SELECT 1 FROM chatbot.fila_mensagens f
          WHERE (f.id_conversa = c.id_conversa OR
                 (f.cliente_telefone = cl.waid_telefone AND f.id_phone_unidade = u.phone_number_id))
            AND f.status IN ('pending', 'processing')
      )
      AND NOT EXISTS (
          SELECT 1 FROM chatbot.historico_mensagens h
          WHERE h.id_conversa = c.id_conversa AND h.quem_enviou = 'cliente'
            AND h.received_data_hora >= b.received_data_hora
      )
      AND EXISTS (
          SELECT 1 FROM chatbot.historico_mensagens h
          WHERE h.id_conversa = c.id_conversa AND h.quem_enviou = 'cliente'
            AND h.received_data_hora > clock_timestamp() - INTERVAL '24 hours' + INTERVAL '1 minute'
      )
      AND NOT EXISTS (
          SELECT 1 FROM chatbot.followup_envio f WHERE f.id_conversa = c.id_conversa
            AND f.id_ancora = b.id_mensagem AND f.ancora_em = b.received_data_hora
      )
      AND (
          (COALESCE(c.followup_stage, 0) = 0 AND NOT EXISTS (
              SELECT 1 FROM chatbot.followup_envio f WHERE f.id_conversa = c.id_conversa
                AND f.id_historico_bot = b.id_mensagem AND f.enviado_em = b.received_data_hora
          ))
          OR (c.followup_stage = 1 AND c.followup_last_sent_at = b.received_data_hora
              AND EXISTS (
                  -- Stage legado sozinho não comprova um primeiro envio.
                  SELECT 1 FROM chatbot.followup_envio primeiro
                  WHERE primeiro.id_conversa = c.id_conversa
                    AND primeiro.id_historico_bot = b.id_mensagem
                    AND primeiro.enviado_em = b.received_data_hora
                    AND NOT EXISTS (
                        SELECT 1 FROM chatbot.followup_envio anterior
                        WHERE anterior.id_conversa = primeiro.id_conversa
                          AND anterior.id_historico_bot = primeiro.id_ancora
                          AND anterior.enviado_em = primeiro.ancora_em
                    )
              ))
      )
      AND NOT EXISTS (
          SELECT 1 FROM chatbot.followup_retomada r
          WHERE r.id_conversa = c.id_conversa AND r.concluida_em IS NULL
            AND EXISTS (SELECT 1 FROM chatbot.fila_mensagens f
                        WHERE f.id_mensagem = r.id_mensagem_fila
                          AND f.id_hash_msg = r.id_hash_cliente
                          AND f.status IN ('pending', 'processing'))
      )
"""

COLUNAS_ELEGIVEL = (
    "id_conversa",
    "id_cliente",
    "id_unidade",
    "id_etapa",
    "cliente_telefone",
    "id_phone_unidade",
    "unidade_telefone",
    "id_ancora",
    "ancora_em",
    "followup_stage",
    "nome_titular",
    "nome_agente",
    "status_dependente",
    "nome_dependente",
)


def listar_elegiveis(cursor, limite=20, depois=None):
    parametros = []
    sql = CONSULTA_ELEGIVEIS
    if depois is not None:
        sql += " AND (b.received_data_hora, c.id_conversa) > (%s, %s)"
        parametros.extend(depois)
    sql += " ORDER BY b.received_data_hora, c.id_conversa LIMIT %s;"
    parametros.append(limite)
    cursor.execute(sql, parametros)
    return [dict(zip(COLUNAS_ELEGIVEL, row)) for row in cursor.fetchall()]


def reler_elegivel(id_conversa, cursor):
    cursor.execute(CONSULTA_ELEGIVEIS + " AND c.id_conversa = %s;", (id_conversa,))
    row = cursor.fetchone()
    return dict(zip(COLUNAS_ELEGIVEL, row)) if row else None


def persistir_followup(dados, envio, lock_version, cursor):
    stage_anterior = dados["followup_stage"]
    if stage_anterior not in (0, 1):
        raise ValueError("Follow-up proativo só pode partir dos stages 0 ou 1")
    stage = stage_anterior + 1
    proteger_conversa(dados["id_conversa"], lock_version, cursor)
    if not envio.get("id_hash_msg_bot") or not envio.get("enviou"):
        raise ValueError("Follow-up sem confirmação da Meta")
    cursor.execute(
        """
        INSERT INTO chatbot.historico_mensagens
            (id_conversa, id_etapa, received_data_hora, cliente_telefone, conteudo_texto,
             tipo_mensagem, id_hash_msg, id_mensagem_fila, id_hash_cliente_origem,
             id_phone_unidade, unidade_telefone, quem_enviou, status_envio)
        VALUES (%s, %s, clock_timestamp(), %s, %s, 'text', %s, NULL, NULL, %s, %s, 'bot', 'sent')
        RETURNING id_mensagem, received_data_hora;
    """,
        (
            dados["id_conversa"],
            dados["id_etapa"],
            dados["cliente_telefone"],
            envio["mensagem_bot"],
            envio["id_hash_msg_bot"],
            dados["id_phone_unidade"],
            dados["unidade_telefone"],
        ),
    )
    id_bot, data_bot = cursor.fetchone()
    cursor.execute(
        """
        INSERT INTO chatbot.followup_envio
            (id_conversa, id_ancora, ancora_em, id_historico_bot, enviado_em, id_hash_msg)
        VALUES (%s, %s, %s, %s, %s, %s);
    """,
        (
            dados["id_conversa"],
            dados["id_ancora"],
            dados["ancora_em"],
            id_bot,
            data_bot,
            envio["id_hash_msg_bot"],
        ),
    )
    # Uma entrada nova na fila após o despacho não invalida a confirmação da Meta.
    # O flow aguardará este lock: stage 1 retoma; stage 2 abre outra conversa.
    # Confirmação, histórico e encerramento pertencem à mesma transação.
    cursor.execute(
        """
        UPDATE chatbot.conversa
        SET followup_stage = %s, followup_last_sent_at = %s,
            last_message_from = 'bot', last_interaction_at = %s,
            status_ativa = CASE WHEN %s = 2 THEN FALSE ELSE status_ativa END,
            finalizou_em = CASE WHEN %s = 2 THEN %s ELSE finalizou_em END,
            motivo_encerramento = CASE WHEN %s = 2 THEN 'followup_sem_resposta'
                                      ELSE motivo_encerramento END
        WHERE id_conversa = %s AND lock_version = %s AND processing IS TRUE
          AND status_ativa IS TRUE AND finalizou_em IS NULL AND id_etapa_atual = %s
          AND COALESCE(followup_stage, 0) = %s AND last_message_from = 'bot'
          AND last_interaction_at = %s;
    """,
        (
            stage,
            data_bot,
            data_bot,
            stage,
            stage,
            data_bot,
            stage,
            dados["id_conversa"],
            lock_version,
            dados["id_etapa"],
            stage_anterior,
            dados["ancora_em"],
        ),
    )
    if cursor.rowcount != 1:
        raise LockConversaPerdido("Contexto mudou depois do despacho do follow-up")
    return id_bot, data_bot


def configurar_consulta_followup(cursor, *, sessao=False):
    if sessao:
        cursor.execute("SET statement_timeout = '15s'")
        cursor.execute("SET lock_timeout = '5s'")
    else:
        cursor.execute("SET LOCAL statement_timeout = '15s'")


def validar_schema_followup(cursor):
    """Recusa despachos antes da migração, sem depender de uma falha pós-Meta."""
    cursor.execute(
        "SELECT to_regclass('chatbot.followup_envio'), to_regclass('chatbot.followup_retomada'), to_regclass('chatbot.followup_legado')"
    )
    if not all(cursor.fetchone()):
        raise ValueError("SCHEMA_FOLLOWUP_AUSENTE")
    cursor.execute("""
        SELECT EXISTS (
            SELECT 1 FROM pg_constraint
            WHERE conrelid = 'chatbot.conversa'::regclass
              AND conname = 'ck_conversa_motivo_encerramento'
              AND contype = 'c' AND convalidated
              AND POSITION('followup_sem_resposta' IN pg_get_constraintdef(oid)) > 0
        );
    """)
    if not cursor.fetchone()[0]:
        raise ValueError(
            "SCHEMA_SEGUNDO_FOLLOWUP_AUSENTE: aplicar 20260924_segundo_followup.sql"
        )


def consultar_diagnostico(cursor):
    cursor.execute("SET TRANSACTION READ ONLY")
    configurar_consulta_followup(cursor)
    validar_schema_followup(cursor)
    cursor.execute("""
        SELECT COUNT(*) FILTER (WHERE followup_stage > 0 AND status_ativa IS TRUE),
               COUNT(*) FILTER (WHERE followup_stage < 0),
               COUNT(*) FILTER (WHERE followup_stage > 2),
               COUNT(*) FILTER (WHERE last_interaction_at > clock_timestamp()),
               COUNT(*) FILTER (WHERE followup_stage = 2 AND status_ativa IS FALSE
                                 AND motivo_encerramento = 'followup_sem_resposta')
        FROM chatbot.conversa;
    """)
    positivos, negativos, legados, futuros, encerrados = cursor.fetchone()
    cursor.execute("SELECT COUNT(*) FROM chatbot.followup_legado")
    marcadas_na_migracao = cursor.fetchone()[0]
    candidatos = listar_elegiveis(cursor, 10)
    return {
        "ciclos_aguardando_reacao": positivos,
        "conversas_marcadas_na_migracao": marcadas_na_migracao,
        "stages_negativos": negativos,
        "stages_maiores_que_dois": legados,
        "encerradas_no_segundo_followup": encerrados,
        "horarios_futuros": futuros,
        "amostra_elegiveis": [
            {k: item[k] for k in ("id_conversa", "id_unidade", "id_etapa")}
            for item in candidatos
        ],
    }
```

## Passo 33 — Substituir integralmente `core/repositories/monitoramento/painel.py`

```python
"""Consultas somente leitura do painel, sempre limitadas à unidade autorizada."""


def _linhas(cursor):
    colunas = [item[0] for item in cursor.description]
    return [dict(zip(colunas, linha)) for linha in cursor.fetchall()]


def _linha(cursor):
    colunas = [item[0] for item in cursor.description]
    valor = cursor.fetchone()
    return dict(zip(colunas, valor)) if valor else None


def _periodo(coluna, inicio, fim, parametros):
    trecho = f' AND {coluna} < %s'
    if inicio is not None:
        trecho = f' AND {coluna} >= %s' + trecho
        parametros.extend((inicio, fim))
    else:
        parametros.append(fim)
    return trecho


def buscar_unidade(id_unidade, cursor):
    cursor.execute("""
        SELECT u.id_unidade, u.nome_unidade, u.nome_agente, u.idade_minima_suporte,
               u.email_obrigatorio, u.bpa_ativo,
               MIN(CASE WHEN h.quem_enviou = 'cliente' THEN h.received_data_hora END) AS inicio_historico
          FROM chatbot.unidade_atendimento u
          LEFT JOIN chatbot.conversa c ON c.id_unidade = u.id_unidade
          LEFT JOIN chatbot.historico_mensagens h ON h.id_conversa = c.id_conversa
         WHERE u.id_unidade = %s
         GROUP BY u.id_unidade, u.nome_unidade, u.nome_agente,
                  u.idade_minima_suporte, u.email_obrigatorio, u.bpa_ativo
    """, (id_unidade,))
    return _linha(cursor)


def listar_conversas(id_unidade, inicio, fim, cursor):
    p_contato = [id_unidade]
    filtro_contato = _periodo('h0.received_data_hora', inicio, fim, p_contato)
    p_funil = []
    filtro_funil = _periodo('f.enviado_em', inicio, fim, p_funil)
    p_avaliacao = []
    filtro_avaliacao = _periodo('p.criado_em', inicio, fim, p_avaliacao)
    p_atividade = []
    filtro_atividade = _periodo('h.received_data_hora', inicio, fim, p_atividade)
    cursor.execute(f"""
        WITH conversas_periodo AS (
            SELECT c.*
              FROM chatbot.conversa c
             WHERE c.id_unidade = %s
               AND EXISTS (
                   SELECT 1 FROM chatbot.historico_mensagens h0
                    WHERE h0.id_conversa = c.id_conversa
                      AND h0.quem_enviou = 'cliente' {filtro_contato}
               )
        )
        SELECT c.id_cliente, c.id_conversa, c.status_dependente,
               c.id_etapa_atual, c.turno, cl.nome AS nome_cliente, cl.waid_telefone,
               cl.email, cl.idade AS idade_titular,
               cl.profissao AS profissao_cliente, c.profissao AS profissao_conversa,
               d.nome_dependente, d.idade AS idade_dependente,
               CASE WHEN c.followup_stage IN (1, 2) AND NOT EXISTS (
                   -- Considera atendimentos novos até fora do período selecionado.
                   SELECT 1 FROM chatbot.conversa posterior
                   WHERE posterior.id_cliente = c.id_cliente
                     AND posterior.id_unidade = c.id_unidade
                     AND posterior.id_conversa > c.id_conversa
               ) THEN c.followup_stage ELSE 0 END AS followup_stage_atual,
               EXISTS (SELECT 1 FROM chatbot.funil_envios f
                        WHERE f.id_conversa = c.id_conversa AND f.status = 'sent'
                        {filtro_funil}) AS foi_funil,
               EXISTS (SELECT 1 FROM chatbot.pesquisa_satisfacao p
                        WHERE p.id_conversa = c.id_conversa AND p.nota IS NOT NULL
                        {filtro_avaliacao}) AS avaliada,
               (SELECT h.received_data_hora FROM chatbot.historico_mensagens h
                 WHERE h.id_conversa = c.id_conversa {filtro_atividade}
                   AND (h.quem_enviou = 'cliente' OR (h.quem_enviou = 'bot' AND h.status_envio = 'sent'))
                 ORDER BY h.received_data_hora DESC, h.id_mensagem DESC LIMIT 1) AS ultima_atividade,
               (SELECT h.conteudo_texto FROM chatbot.historico_mensagens h
                 WHERE h.id_conversa = c.id_conversa {filtro_atividade}
                   AND (h.quem_enviou = 'cliente' OR (h.quem_enviou = 'bot' AND h.status_envio = 'sent'))
                 ORDER BY h.received_data_hora DESC, h.id_mensagem DESC LIMIT 1) AS ultima_mensagem,
               (SELECT h.id_mensagem FROM chatbot.historico_mensagens h
                 WHERE h.id_conversa = c.id_conversa {filtro_atividade}
                   AND (h.quem_enviou = 'cliente' OR (h.quem_enviou = 'bot' AND h.status_envio = 'sent'))
                 ORDER BY h.received_data_hora DESC, h.id_mensagem DESC LIMIT 1) AS ultima_mensagem_id
          FROM conversas_periodo c
          JOIN chatbot.cliente cl ON cl.id_cliente = c.id_cliente
          LEFT JOIN chatbot.dependente d ON d.id_conversa = c.id_conversa
         ORDER BY ultima_atividade DESC NULLS LAST, c.id_conversa DESC
    """, tuple(
        p_contato + p_funil + p_avaliacao
        + p_atividade + p_atividade + p_atividade
    ))
    return _linhas(cursor)


def buscar_mensagens(id_unidade, id_cliente, inicio, fim, cursor):
    parametros = [id_unidade, id_cliente]
    filtro = _periodo('h.received_data_hora', inicio, fim, parametros)
    cursor.execute(f"""
        SELECT h.id_mensagem, h.id_conversa, h.id_etapa,
               h.received_data_hora AS data, h.quem_enviou,
               h.tipo_mensagem AS tipo, h.conteudo_texto AS texto
          FROM chatbot.historico_mensagens h
          JOIN chatbot.conversa c ON c.id_conversa = h.id_conversa
         WHERE c.id_unidade = %s AND c.id_cliente = %s {filtro}
           AND (h.quem_enviou = 'cliente' OR (h.quem_enviou = 'bot' AND h.status_envio = 'sent'))
         ORDER BY h.received_data_hora, h.id_mensagem
    """, tuple(parametros))
    return _linhas(cursor)


def buscar_metricas(id_unidade, inicio, fim, cursor):
    parametros = [id_unidade]
    filtro = _periodo('h.received_data_hora', inicio, fim, parametros)
    p_msg = []
    f_msg = _periodo('h.received_data_hora', inicio, fim, p_msg)
    p_funil = []
    f_funil = _periodo('f.enviado_em', inicio, fim, p_funil)
    p_nota = []
    f_nota = _periodo('p.criado_em', inicio, fim, p_nota)
    cursor.execute(f"""
        WITH contatos AS (
          SELECT DISTINCT c.id_cliente
            FROM chatbot.conversa c JOIN chatbot.historico_mensagens h ON h.id_conversa=c.id_conversa
           WHERE c.id_unidade=%s AND h.quem_enviou='cliente' {filtro}
        )
        SELECT (SELECT COUNT(*) FROM contatos) AS leads,
               (SELECT COUNT(*) FROM chatbot.historico_mensagens h
                 JOIN chatbot.conversa c ON c.id_conversa=h.id_conversa
                WHERE c.id_unidade=%s AND c.id_cliente IN (SELECT id_cliente FROM contatos)
                  {f_msg} AND (h.quem_enviou='cliente' OR (h.quem_enviou='bot' AND h.status_envio='sent'))) AS mensagens,
               (SELECT COUNT(DISTINCT c.id_cliente) FROM chatbot.funil_envios f
                 JOIN chatbot.conversa c ON c.id_conversa=f.id_conversa
                WHERE c.id_unidade=%s AND c.id_cliente IN (SELECT id_cliente FROM contatos)
                  AND f.status='sent' {f_funil}) AS funil,
               (SELECT COUNT(DISTINCT c.id_cliente) FROM chatbot.pesquisa_satisfacao p
                 JOIN chatbot.conversa c ON c.id_conversa=p.id_conversa
                WHERE c.id_unidade=%s AND c.id_cliente IN (SELECT id_cliente FROM contatos)
                  AND p.nota IS NOT NULL {f_nota}) AS avaliacoes,
               (SELECT ROUND(AVG(p.nota)::numeric,2) FROM chatbot.pesquisa_satisfacao p
                 JOIN chatbot.conversa c ON c.id_conversa=p.id_conversa
                WHERE c.id_unidade=%s AND c.id_cliente IN (SELECT id_cliente FROM contatos)
                  AND p.nota IS NOT NULL {f_nota}) AS nota_media
    """, tuple(parametros + [id_unidade] + p_msg + [id_unidade] + p_funil + [id_unidade] + p_nota + [id_unidade] + p_nota))
    return _linha(cursor)


def contar_encaminhados_comercial_por_idade(id_unidade, inicio, fim, cursor):
    """Conta o fato concluído, pela data de encerramento, sem inferir pela idade."""
    parametros = [id_unidade]
    filtro = _periodo('c.finalizou_em', inicio, fim, parametros)
    cursor.execute(f"""
        SELECT COUNT(DISTINCT c.id_cliente)
          FROM chatbot.conversa c
         WHERE c.id_unidade = %s
           AND c.status_ativa = FALSE
           AND c.motivo_encerramento = 'encaminhado_suporte_idoso'
           AND c.finalizou_em IS NOT NULL {filtro}
    """, tuple(parametros))
    return int(cursor.fetchone()[0])


def buscar_perfis(id_unidade, inicio, fim, cursor):
    parametros = [id_unidade]
    filtro = _periodo('h.received_data_hora', inicio, fim, parametros)
    parametros_funil = []
    filtro_funil = _periodo('f.enviado_em', inicio, fim, parametros_funil)
    cursor.execute(f"""
        SELECT DISTINCT c.id_cliente, c.id_conversa, c.status_dependente,
               cl.idade AS idade_titular, d.idade AS idade_dependente,
               d.id_dependente, d.nome_dependente,
               EXISTS (SELECT 1 FROM chatbot.funil_envios f
                        WHERE f.id_conversa=c.id_conversa AND f.status='sent'
                        {filtro_funil}) AS foi_funil
          FROM chatbot.conversa c JOIN chatbot.cliente cl ON cl.id_cliente=c.id_cliente
          LEFT JOIN chatbot.dependente d ON d.id_conversa=c.id_conversa
         WHERE c.id_unidade=%s AND EXISTS (
               SELECT 1 FROM chatbot.historico_mensagens h
                WHERE h.id_conversa=c.id_conversa AND h.quem_enviou='cliente' {filtro})
    """, tuple(parametros_funil + parametros))
    return _linhas(cursor)


def buscar_satisfacao(id_unidade, inicio, fim, cursor):
    parametros = [id_unidade]
    filtro = _periodo('p.criado_em', inicio, fim, parametros)
    cursor.execute(f"""
        SELECT p.nota, COUNT(*) AS quantidade
          FROM chatbot.pesquisa_satisfacao p
          JOIN chatbot.conversa c ON c.id_conversa=p.id_conversa
         WHERE c.id_unidade=%s AND p.nota IS NOT NULL {filtro}
         GROUP BY p.nota ORDER BY p.nota
    """, tuple(parametros))
    return _linhas(cursor)


def buscar_etapas(id_unidade, inicio, fim, cursor):
    parametros = [id_unidade]
    filtro = _periodo('h.received_data_hora', inicio, fim, parametros)
    cursor.execute(f"""
        WITH conversas_periodo AS (
            SELECT c.id_cliente, c.id_conversa, c.id_etapa_atual,
                   MAX(h.received_data_hora) AS ultima_atividade
              FROM chatbot.conversa c
              JOIN chatbot.historico_mensagens h
                ON h.id_conversa = c.id_conversa
             WHERE c.id_unidade = %s AND h.quem_enviou = 'cliente' {filtro}
             GROUP BY c.id_cliente, c.id_conversa, c.id_etapa_atual
        ),
        ultimas_conversas AS (
            SELECT *, ROW_NUMBER() OVER (
                       PARTITION BY id_cliente
                       ORDER BY ultima_atividade DESC, id_conversa DESC
                   ) AS ordem
              FROM conversas_periodo
        )
        SELECT e.id_etapa, e.nome_etapa, COUNT(c.id_cliente) AS quantidade
          FROM chatbot.etapa e
          LEFT JOIN ultimas_conversas c
            ON c.id_etapa_atual = e.id_etapa AND c.ordem = 1
         WHERE e.id_etapa BETWEEN 1 AND 24
         GROUP BY e.id_etapa, e.nome_etapa ORDER BY e.id_etapa
    """, tuple(parametros))
    return _linhas(cursor)


def buscar_atividade(id_unidade, inicio, fim, cursor, granularidade):
    unidade_tempo = {'dia': 'day', 'semana': 'week', 'mes': 'month'}[granularidade]
    parametros = [id_unidade]
    filtro = _periodo('h.received_data_hora', inicio, fim, parametros)
    cursor.execute(f"""
        SELECT DATE_TRUNC('{unidade_tempo}', h.received_data_hora AT TIME ZONE 'America/Sao_Paulo') AS periodo,
               COUNT(*) FILTER (WHERE h.quem_enviou='cliente' OR (h.quem_enviou='bot' AND h.status_envio='sent')) AS mensagens,
               COUNT(DISTINCT c.id_cliente) FILTER (WHERE h.quem_enviou='cliente') AS leads
          FROM chatbot.historico_mensagens h JOIN chatbot.conversa c ON c.id_conversa=h.id_conversa
         WHERE c.id_unidade=%s {filtro}
         GROUP BY 1 ORDER BY 1
    """, tuple(parametros))
    return _linhas(cursor)


def listar_contatos(id_unidade, inicio, fim, cursor):
    parametros = [id_unidade]
    filtro = _periodo('h.received_data_hora', inicio, fim, parametros)
    cursor.execute(f"""
        SELECT cl.id_cliente, cl.nome, cl.email, cl.waid_telefone
          FROM chatbot.cliente cl
         WHERE EXISTS (
             SELECT 1 FROM chatbot.conversa c
             JOIN chatbot.historico_mensagens h ON h.id_conversa=c.id_conversa
              WHERE c.id_cliente=cl.id_cliente AND c.id_unidade=%s
                AND h.quem_enviou='cliente' {filtro})
         ORDER BY cl.nome NULLS LAST, cl.id_cliente
    """, tuple(parametros))
    return _linhas(cursor)
```

## Passo 34 — Substituir integralmente `utilitarios/reports_functions/total.py`

```python
"""Gera dashboards HTML e relatórios PDF totais por unidade.

O instante final é congelado no começo da execução. Para cada unidade, a
janela começa no primeiro contato recebido de um cliente e termina nesse mesmo
instante final, preservando a estrutura, a consolidação e as métricas do
relatório semanal.

Uso padrão::

    python -m utilitarios.reports_functions.total

Na VM::

    python -m utilitarios.reports_functions.total \
        --env-file /etc/chatbot/chatbot.env
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

from utilitarios.reports_functions import weekly


SAIDA_PADRAO = weekly.SAIDA_PADRAO
MAX_MENSAGENS_PADRAO = weekly.MAX_MENSAGENS_PADRAO


def criar_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Gera um dashboard HTML e um relatório PDF com todo o histórico "
            "disponível de cada unidade."
        )
    )
    parser.add_argument(
        "--env-file",
        type=Path,
        help="Arquivo .env explícito; sem ele usa utilitarios/local_settings.py.",
    )
    parser.add_argument(
        "--ate",
        help=(
            "Fim do período em ISO-8601. Sem fuso, considera America/Sao_Paulo; "
            "sem o parâmetro, congela o instante atual no início da execução."
        ),
    )
    parser.add_argument(
        "--id-unidade",
        type=int,
        action="append",
        dest="ids_unidade",
        help="Limita a uma unidade; pode ser repetido.",
    )
    parser.add_argument(
        "--saida",
        type=Path,
        default=SAIDA_PADRAO,
        help="Diretório raiz da saída (padrão: monitoramento).",
    )
    parser.add_argument(
        "--max-mensagens",
        type=int,
        default=MAX_MENSAGENS_PADRAO,
        help="Limite por unidade; falha sem truncar quando for excedido.",
    )
    parser.add_argument(
        "--statement-timeout-ms",
        type=int,
        default=60_000,
        help="Timeout das consultas do snapshot (padrão: 60000).",
    )
    return parser


def resolver_fim(ate: str | datetime | None = None) -> datetime:
    """Normaliza e congela o instante final em UTC."""
    return weekly.resolver_janela(dias=1, ate=ate)[1]


def coletar_primeiros_registros(
    conn: Any,
    fim: datetime,
    ids_unidade: Sequence[int] | None = None,
    statement_timeout_ms: int = 60_000,
) -> list[dict[str, Any]]:
    """Obtém o primeiro contato real de cada unidade em uma leitura consistente.

    Unidades sem mensagem recebida de cliente continuam na lista com início
    nulo para que também recebam um relatório vazio.
    """
    if statement_timeout_ms <= 0:
        raise ValueError("--statement-timeout-ms precisa ser maior que zero")

    from psycopg.rows import dict_row

    cursor = conn.cursor(row_factory=dict_row)
    try:
        cursor.execute("BEGIN TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
        cursor.execute(
            "SELECT set_config('statement_timeout', %s, true)",
            (f"{statement_timeout_ms}ms",),
        )
        cursor.execute("SELECT set_config('lock_timeout', '5000ms', true)")
        filtro, params_filtro = weekly._filtro_unidades(ids_unidade)
        cursor.execute(
            f"""
            SELECT
                u.id_unidade,
                u.nome_unidade,
                MIN(h.received_data_hora) FILTER (
                    WHERE h.quem_enviou = 'cliente'
                      AND h.received_data_hora < %s
                ) AS primeiro_registro
              FROM chatbot.unidade_atendimento u
              LEFT JOIN chatbot.conversa c ON c.id_unidade = u.id_unidade
              LEFT JOIN chatbot.historico_mensagens h
                ON h.id_conversa = c.id_conversa
             WHERE TRUE {filtro}
             GROUP BY u.id_unidade, u.nome_unidade
             ORDER BY u.nome_unidade, u.id_unidade
            """,
            (fim, *params_filtro),
        )
        unidades = [dict(linha) for linha in cursor.fetchall()]
        if ids_unidade and len(unidades) != len(set(ids_unidade)):
            encontrados = {int(linha["id_unidade"]) for linha in unidades}
            ausentes = sorted(set(ids_unidade) - encontrados)
            raise RuntimeError(f"Unidade(s) não encontrada(s): {ausentes}")
        conn.rollback()
        return unidades
    except Exception:
        conn.rollback()
        raise
    finally:
        cursor.close()


def gerar_totais(
    conn: Any,
    unidades: Sequence[Mapping[str, Any]],
    fim: datetime,
    raiz_saida: Path,
    max_mensagens: int = MAX_MENSAGENS_PADRAO,
    statement_timeout_ms: int = 60_000,
) -> list[dict[str, Path]]:
    """Coleta e publica um snapshot total independente para cada unidade."""
    nomes_pasta = weekly.resolver_pastas_unidades(unidades)
    gerados: list[dict[str, Path]] = []
    for unidade in unidades:
        id_unidade = int(unidade["id_unidade"])
        primeiro_registro = unidade.get("primeiro_registro")
        inicio = primeiro_registro or fim
        if isinstance(inicio, datetime) and inicio.tzinfo is None:
            inicio = inicio.replace(tzinfo=timezone.utc)
        inicio = inicio.astimezone(timezone.utc)

        snapshot = weekly.coletar_snapshot(
            conn=conn,
            inicio=inicio,
            fim=fim,
            ids_unidade=[id_unidade],
            max_mensagens=max_mensagens,
            statement_timeout_ms=statement_timeout_ms,
        )
        snapshot["periodo"]["tipo"] = "total"
        snapshot["periodo"]["sem_registros"] = primeiro_registro is None
        gerados.extend(
            weekly.gerar_artefatos(
                snapshot,
                raiz_saida,
                nomes_pasta=nomes_pasta,
            )
        )
    return gerados


def executar(args: argparse.Namespace) -> list[dict[str, Path]]:
    from utilitarios.bootstrap import configurar_ambiente_utilitario

    configurar_ambiente_utilitario(args.env_file)
    from core.database.connection_aws import get_conn

    fim = resolver_fim(args.ate)
    conn = get_conn(application_name="utilitario_monitoramento_total")
    try:
        unidades = coletar_primeiros_registros(
            conn=conn,
            fim=fim,
            ids_unidade=args.ids_unidade,
            statement_timeout_ms=args.statement_timeout_ms,
        )
        return gerar_totais(
            conn=conn,
            unidades=unidades,
            fim=fim,
            raiz_saida=args.saida,
            max_mensagens=args.max_mensagens,
            statement_timeout_ms=args.statement_timeout_ms,
        )
    finally:
        conn.close()


def main(argv: Sequence[str] | None = None) -> int:
    parser = criar_parser()
    args = parser.parse_args(argv)
    try:
        gerados = executar(args)
    except Exception as exc:
        parser.exit(1, f"Falha ao gerar monitoramento total: {exc}\n")

    if not gerados:
        print("Nenhuma unidade encontrada; nenhum arquivo foi gerado.")
        return 0
    print(f"Monitoramento total concluído para {len(gerados)} unidade(s):")
    for item in gerados:
        print(f"- HTML: {item['html']}")
        print(f"  PDF:  {item['pdf']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

## Passo 35 — Substituir integralmente `utilitarios/reports_functions/weekly.py`

```python
"""Gera dashboards HTML e relatórios PDF semanais por unidade.

O utilitário é deliberadamente import-safe: banco, configuração privada e
ReportLab só são carregados quando ``main`` é executado.  A visão humana
agrupa as conversas técnicas por ``(id_unidade, id_cliente)`` sem alterar a
forma como o chatbot persiste ou processa cada conversa.

Uso padrão (configuração de ``utilitarios/local_settings.py``)::

    python -m utilitarios.reports_functions.weekly

Para consultar uma configuração explícita ou uma unidade específica::

    python -m utilitarios.reports_functions.weekly --env-file .env.prod \
        --id-unidade 1
"""

from __future__ import annotations

import argparse
import json
import os
import re
import tempfile
import unicodedata
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from html import escape as html_escape
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence
from zoneinfo import ZoneInfo

from core.validacoes.suporte_por_idade import validar_idade_minima_suporte


RAIZ_PROJETO = Path(__file__).resolve().parents[2]
SAIDA_PADRAO = RAIZ_PROJETO / "monitoramento"
FUSO_RELATORIO = ZoneInfo("America/Sao_Paulo")
DIAS_PADRAO = 7
MAX_MENSAGENS_PADRAO = 100_000
IDADE_ADULTA_MINIMA = 18
IDADE_IDOSA_MINIMA = 60
IDADE_MINIMA_DEPENDENTE_PADRAO = 5
IDADE_MINIMA_DEPENDENTE_BPA = 4

PERFIS_ATENDIMENTO = (
    "dependente_infantil",
    "dependente_adulto",
    "dependente_idoso",
    "titular_adulto",
    "titular_idoso",
)

ROTULOS_TIPO_MENSAGEM = {
    "audio": "Áudio",
    "button": "Botão",
    "contacts": "Contato compartilhado",
    "document": "Documento",
    "image": "Imagem",
    "interactive": "Interação",
    "location": "Localização",
    "reaction": "Reação",
    "sticker": "Figurinha",
    "text": "Mensagem",
    "unknown": "Conteúdo não textual",
    "video": "Vídeo",
}


def criar_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Gera um dashboard HTML e um relatório PDF dos últimos dias "
            "para cada unidade."
        )
    )
    parser.add_argument(
        "--env-file",
        type=Path,
        help="Arquivo .env explícito; sem ele usa utilitarios/local_settings.py.",
    )
    parser.add_argument(
        "--dias",
        type=int,
        default=DIAS_PADRAO,
        help=f"Tamanho da janela móvel (padrão: {DIAS_PADRAO}).",
    )
    parser.add_argument(
        "--ate",
        help=(
            "Fim da janela em ISO-8601. Sem fuso, considera America/Sao_Paulo; "
            "sem o parâmetro, usa o instante atual."
        ),
    )
    parser.add_argument(
        "--id-unidade",
        type=int,
        action="append",
        dest="ids_unidade",
        help="Limita a uma unidade; pode ser repetido.",
    )
    parser.add_argument(
        "--saida",
        type=Path,
        default=SAIDA_PADRAO,
        help="Diretório raiz da saída (padrão: monitoramento).",
    )
    parser.add_argument(
        "--max-mensagens",
        type=int,
        default=MAX_MENSAGENS_PADRAO,
        help="Proteção contra um HTML grande demais.",
    )
    parser.add_argument(
        "--statement-timeout-ms",
        type=int,
        default=60_000,
        help="Timeout das consultas do snapshot (padrão: 60000).",
    )
    return parser


def resolver_janela(
    dias: int = DIAS_PADRAO,
    ate: str | datetime | None = None,
) -> tuple[datetime, datetime]:
    """Retorna ``[inicio, fim)`` em UTC para uma janela móvel."""
    if dias <= 0:
        raise ValueError("--dias precisa ser maior que zero")

    if ate is None:
        fim = datetime.now(timezone.utc)
    elif isinstance(ate, datetime):
        fim = ate
    else:
        valor = ate.strip().replace("Z", "+00:00")
        fim = datetime.fromisoformat(valor)

    if fim.tzinfo is None:
        fim = fim.replace(tzinfo=FUSO_RELATORIO)
    fim = fim.astimezone(timezone.utc)
    return fim - timedelta(days=dias), fim


def sanear_nome_unidade(nome: str, id_unidade: int | None = None) -> str:
    """Converte o nome de uma unidade em um componente de caminho seguro."""
    limpo = re.sub(r"^\s*supera(?:\s+|-)+", "", nome or "", flags=re.I)
    limpo = re.sub(r"[<>:\"/\\|?*\x00-\x1f]", " ", limpo)
    limpo = re.sub(r"\s+", " ", limpo).strip(" .")
    chave = "".join(
        caractere
        for caractere in unicodedata.normalize("NFKD", limpo)
        if not unicodedata.combining(caractere)
    ).casefold()
    if chave in {"saj", "santo antonio de jesus"}:
        limpo = "SAJ"
    if not limpo:
        limpo = f"Unidade {id_unidade}" if id_unidade is not None else "Unidade"
    reservados_windows = {
        "CON",
        "PRN",
        "AUX",
        "NUL",
        *(f"COM{numero}" for numero in range(1, 10)),
        *(f"LPT{numero}" for numero in range(1, 10)),
    }
    if limpo.upper() in reservados_windows:
        sufixo = f" {id_unidade}" if id_unidade is not None else " unidade"
        limpo += sufixo
    return limpo


def _texto_mensagem(texto: Any, tipo: Any) -> str:
    valor = str(texto).strip() if texto is not None else ""
    if valor:
        return valor
    tipo_normalizado = str(tipo or "unknown").strip().lower()
    return f"[{ROTULOS_TIPO_MENSAGEM.get(tipo_normalizado, tipo_normalizado or 'Conteúdo')}]"


def _iso(valor: Any) -> str | None:
    if valor is None:
        return None
    if isinstance(valor, datetime):
        if valor.tzinfo is None:
            valor = valor.replace(tzinfo=timezone.utc)
        return valor.astimezone(timezone.utc).isoformat()
    return str(valor)


def _data_local(valor: Any, formato: str = "%d/%m/%Y %H:%M") -> str:
    if valor is None:
        return "—"
    if isinstance(valor, str):
        valor = datetime.fromisoformat(valor.replace("Z", "+00:00"))
    if valor.tzinfo is None:
        valor = valor.replace(tzinfo=timezone.utc)
    return valor.astimezone(FUSO_RELATORIO).strftime(formato)


def _profissao_atual(linha: Mapping[str, Any]) -> str | None:
    for chave in ("profissao_cliente", "profissao_conversa_recente"):
        valor = linha.get(chave)
        if valor is not None and str(valor).strip():
            return str(valor).strip()
    return None


def _idade_inteira(valor: Any) -> int | None:
    """Valida 1–99 anos sem converter booleanos ou truncar idades fracionárias."""
    if isinstance(valor, bool) or not isinstance(valor, int):
        return None
    return valor if 0 < valor < 100 else None


def _classificar_perfil_atendimento(
    *,
    status_dependente: Any,
    idade_titular: Any,
    idade_dependente: Any,
    idade_minima_dependente: int,
) -> str | None:
    """Classifica a pessoa atendida, mantendo ``NULL`` e legado como desconhecidos."""
    if status_dependente is True:
        idade = _idade_inteira(idade_dependente)
        if idade is None or idade < idade_minima_dependente:
            return None
        if idade < IDADE_ADULTA_MINIMA:
            return "dependente_infantil"
        if idade < IDADE_IDOSA_MINIMA:
            return "dependente_adulto"
        return "dependente_idoso"

    if status_dependente is False:
        idade = _idade_inteira(idade_titular)
        if idade is None or idade < IDADE_ADULTA_MINIMA:
            return None
        if idade < IDADE_IDOSA_MINIMA:
            return "titular_adulto"
        return "titular_idoso"

    return None


def _rotulos_perfis(idade_minima_dependente: int) -> dict[str, str]:
    return {
        "dependente_infantil": (
            f"Dependentes de {idade_minima_dependente} a 17 anos"
        ),
        "dependente_adulto": "Dependentes de 18 a 59 anos",
        "dependente_idoso": "Dependentes com 60 anos ou mais",
        "titular_adulto": "Titulares de 18 a 59 anos",
        "titular_idoso": "Titulares com 60 anos ou mais",
    }


def _montar_segmentacao_perfis(
    perfis_conversa: Sequence[Mapping[str, Any]],
    ids_conversas_funil: set[int],
    *,
    idade_minima_suporte: int | None,
    bpa_ativo: bool,
) -> dict[str, Any]:
    """Agrega perfis por conversa sem confundi-los com o lead consolidado.

    Um cliente conta uma vez em cada segmento no qual apareceu. A quantidade
    de conversas permanece disponível porque um mesmo contato pode iniciar
    atendimentos para pessoas diferentes durante o período.
    """
    validar_idade_minima_suporte(idade_minima_suporte)
    idade_minima_dependente = (
        IDADE_MINIMA_DEPENDENTE_BPA
        if bpa_ativo
        else IDADE_MINIMA_DEPENDENTE_PADRAO
    )
    rotulos = _rotulos_perfis(idade_minima_dependente)
    acumuladores = {
        chave: {
            "ids_clientes": set(),
            "ids_conversas": set(),
            "ids_clientes_funil": set(),
            "ids_conversas_funil": set(),
        }
        for chave in PERFIS_ATENDIMENTO
    }
    todos_clientes: set[int] = set()
    clientes_classificados: set[int] = set()
    clientes_por_perfil: dict[int, set[str]] = defaultdict(set)
    conversas_classificadas: set[int] = set()
    conversas_sem_classificacao: set[int] = set()
    clientes_funil_sem_classificacao: set[int] = set()
    clientes_funil_classificados: set[int] = set()

    for perfil in perfis_conversa:
        id_cliente = int(perfil["id_cliente"])
        id_conversa = int(perfil["id_conversa"])
        todos_clientes.add(id_cliente)
        chave = _classificar_perfil_atendimento(
            status_dependente=perfil.get("status_dependente"),
            idade_titular=perfil.get("idade_titular"),
            idade_dependente=perfil.get("idade_dependente"),
            idade_minima_dependente=idade_minima_dependente,
        )
        if chave is None:
            conversas_sem_classificacao.add(id_conversa)
            if id_conversa in ids_conversas_funil:
                clientes_funil_sem_classificacao.add(id_cliente)
            continue

        acumulador = acumuladores[chave]
        acumulador["ids_clientes"].add(id_cliente)
        acumulador["ids_conversas"].add(id_conversa)
        clientes_classificados.add(id_cliente)
        clientes_por_perfil[id_cliente].add(chave)
        conversas_classificadas.add(id_conversa)
        if id_conversa in ids_conversas_funil:
            acumulador["ids_clientes_funil"].add(id_cliente)
            acumulador["ids_conversas_funil"].add(id_conversa)
            clientes_funil_classificados.add(id_cliente)

    linhas: list[dict[str, Any]] = []
    for chave in PERFIS_ATENDIMENTO:
        acumulador = acumuladores[chave]
        total_leads = len(acumulador["ids_clientes"])
        total_conversas = len(acumulador["ids_conversas"])
        funil_observado = len(acumulador["ids_clientes_funil"])
        total_funil = funil_observado
        linhas.append(
            {
                "chave": chave,
                "rotulo": rotulos[chave],
                "leads": total_leads,
                "conversas": total_conversas,
                "leads_funil": total_funil,
                "leads_funil_observados": funil_observado,
                "conversas_funil": (
                    len(acumulador["ids_conversas_funil"])
                ),
                "conversas_funil_observadas": len(
                    acumulador["ids_conversas_funil"]
                ),
                "taxa_funil": (
                    round(total_funil / total_leads * 100, 1)
                    if total_leads
                    else 0.0
                ),
                "funil_nao_aplicavel": False,
            }
        )

    total_conversas = len(perfis_conversa)
    maior_volume = max(item["leads"] for item in linhas)
    perfis_predominantes = [
        item["rotulo"] for item in linhas
        if maior_volume and item["leads"] == maior_volume
    ]

    return {
        "linhas": linhas,
        "idade_minima_dependente": idade_minima_dependente,
        "leads_classificados": len(clientes_classificados),
        "leads_sem_classificacao": len(todos_clientes - clientes_classificados),
        "leads_multiperfil": sum(
            len(perfis) > 1 for perfis in clientes_por_perfil.values()
        ),
        "conversas_classificadas": len(conversas_classificadas),
        "conversas_sem_classificacao": len(conversas_sem_classificacao),
        "conversas_funil_sem_classificacao": len(
            conversas_sem_classificacao & ids_conversas_funil
        ),
        "leads_funil_apenas_sem_classificacao": len(
            clientes_funil_sem_classificacao - clientes_funil_classificados
        ),
        "conversas_apenas_envio_funil": sum(
            bool(perfil.get("apenas_envio_funil")) for perfil in perfis_conversa
        ),
        "cobertura_conversas": round(
            len(conversas_classificadas) / total_conversas * 100, 1
        )
        if total_conversas
        else 0.0,
        "perfis_predominantes": perfis_predominantes,
        "idade_minima_suporte": idade_minima_suporte,
    }


def _ordenar_data(valor: Any) -> datetime:
    if isinstance(valor, datetime):
        data = valor
    elif valor:
        data = datetime.fromisoformat(str(valor).replace("Z", "+00:00"))
    else:
        return datetime.min.replace(tzinfo=timezone.utc)
    if data.tzinfo is None:
        data = data.replace(tzinfo=timezone.utc)
    return data.astimezone(timezone.utc)


def montar_snapshot(
    unidades: Sequence[Mapping[str, Any]],
    mensagens: Sequence[Mapping[str, Any]],
    funil: Sequence[Mapping[str, Any]],
    pesquisas: Sequence[Mapping[str, Any]],
    inicio: datetime,
    fim: datetime,
) -> dict[str, Any]:
    """Materializa a visão de relatório a partir de linhas do banco.

    A chave visual é sempre ``(id_unidade, id_cliente)``. Os IDs das
    conversas técnicas permanecem no resultado para auditoria.
    """
    unidades_por_id: dict[int, dict[str, Any]] = {}
    for linha in unidades:
        id_unidade = int(linha["id_unidade"])
        unidades_por_id[id_unidade] = {
            "id_unidade": id_unidade,
            "nome_unidade": str(linha["nome_unidade"]),
            "nome_agente": str(linha.get("nome_agente") or "Assistente"),
            "idade_minima_suporte": validar_idade_minima_suporte(linha["idade_minima_suporte"]),
            "bpa_ativo": bool(linha.get("bpa_ativo", False)),
            "conversas": [],
            "pesquisas": [],
        }

    funil_por_unidade: dict[int, set[int]] = defaultdict(set)
    conversas_funil_por_unidade: dict[int, set[int]] = defaultdict(set)
    for linha in funil:
        id_unidade = int(linha["id_unidade"])
        funil_por_unidade[id_unidade].add(int(linha["id_cliente"]))
        if linha.get("id_conversa") is not None:
            conversas_funil_por_unidade[id_unidade].add(
                int(linha["id_conversa"])
            )

    grupos: dict[tuple[int, int], dict[str, Any]] = {}
    perfis_conversa: dict[tuple[int, int, int], dict[str, Any]] = {}
    for linha in mensagens:
        id_unidade = int(linha["id_unidade"])
        id_cliente = int(linha["id_cliente"])
        if id_unidade not in unidades_por_id:
            continue
        chave = (id_unidade, id_cliente)
        grupo = grupos.get(chave)
        if grupo is None:
            grupo = {
                "id_cliente": id_cliente,
                "nome": str(linha.get("nome_cliente") or "Cliente sem nome"),
                "waid_telefone": str(linha.get("waid_telefone") or ""),
                "email": str(linha.get("email") or ""),
                "profissao": _profissao_atual(linha),
                "ids_conversa": [],
                "mensagens": [],
                "primeira_atividade": None,
                "ultima_atividade": None,
                "status_ativa": False,
                "etapa_atual": None,
                "foi_funil": False,
            }
            grupos[chave] = grupo

        id_conversa = int(linha["id_conversa"])
        if id_conversa not in grupo["ids_conversa"]:
            grupo["ids_conversa"].append(id_conversa)
        perfis_conversa.setdefault(
            (id_unidade, id_cliente, id_conversa),
            {
                "id_unidade": id_unidade,
                "id_cliente": id_cliente,
                "id_conversa": id_conversa,
                "status_dependente": linha.get("status_dependente"),
                "idade_titular": linha.get("idade_titular"),
                "idade_dependente": linha.get("idade_dependente"),
                "nome_dependente": linha.get("nome_dependente"),
                "apenas_envio_funil": False,
            },
        )

        data_mensagem = linha.get("received_data_hora")
        data_ordenacao = _ordenar_data(data_mensagem)
        if (
            grupo["primeira_atividade"] is None
            or data_ordenacao < _ordenar_data(grupo["primeira_atividade"])
        ):
            grupo["primeira_atividade"] = _iso(data_mensagem)
        if (
            grupo["ultima_atividade"] is None
            or data_ordenacao >= _ordenar_data(grupo["ultima_atividade"])
        ):
            grupo["ultima_atividade"] = _iso(data_mensagem)
            grupo["status_ativa"] = bool(linha.get("status_ativa"))
            grupo["etapa_atual"] = linha.get("id_etapa_atual")

        grupo["mensagens"].append(
            {
                "id_mensagem": int(linha["id_mensagem"]),
                "id_conversa": id_conversa,
                "data": _iso(data_mensagem),
                "quem_enviou": str(linha["quem_enviou"]),
                "tipo": str(linha.get("tipo_mensagem") or "unknown"),
                "texto": _texto_mensagem(
                    linha.get("conteudo_texto"), linha.get("tipo_mensagem")
                ),
                "id_etapa": linha.get("id_etapa"),
            }
        )

    for (id_unidade, id_cliente), grupo in grupos.items():
        grupo["mensagens"].sort(
            key=lambda item: (_ordenar_data(item["data"]), item["id_mensagem"])
        )
        grupo["foi_funil"] = id_cliente in funil_por_unidade[id_unidade]
        unidades_por_id[id_unidade]["conversas"].append(grupo)

    for unidade in unidades_por_id.values():
        unidade["conversas"].sort(
            key=lambda grupo: _ordenar_data(grupo["ultima_atividade"]), reverse=True
        )

    # Um retry pode confirmar o envio de uma conversa antiga enquanto o mesmo
    # contato interage em outra. Preservamos o perfil do envio, sem acrescentar
    # suas mensagens fora da janela ao dashboard de conversas.
    for linha in funil:
        id_unidade = int(linha["id_unidade"])
        id_cliente = int(linha["id_cliente"])
        if (id_unidade, id_cliente) not in grupos or linha.get("id_conversa") is None:
            continue
        id_conversa = int(linha["id_conversa"])
        perfis_conversa.setdefault(
            (id_unidade, id_cliente, id_conversa),
            {
                "id_unidade": id_unidade,
                "id_cliente": id_cliente,
                "id_conversa": id_conversa,
                "status_dependente": linha.get("status_dependente"),
                "idade_titular": linha.get("idade_titular"),
                "idade_dependente": linha.get("idade_dependente"),
                "nome_dependente": linha.get("nome_dependente"),
                "apenas_envio_funil": True,
            },
        )

    perfis_por_unidade: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for perfil in perfis_conversa.values():
        perfis_por_unidade[int(perfil["id_unidade"])].append(perfil)
    for id_unidade, unidade in unidades_por_id.items():
        unidade["perfis_atendimento"] = perfis_por_unidade[id_unidade]

    for linha in pesquisas:
        id_unidade = int(linha["id_unidade"])
        if id_unidade not in unidades_por_id:
            continue
        unidades_por_id[id_unidade]["pesquisas"].append(
            {
                "id_cliente": int(linha["id_cliente"]),
                "id_conversa": int(linha["id_conversa"]),
                "nome": str(linha.get("nome_cliente") or "Cliente sem nome"),
                "waid_telefone": str(linha.get("waid_telefone") or ""),
                "profissao": _profissao_atual(linha),
                "nota": linha.get("nota"),
                "comentario": (
                    str(linha["comentario"]).strip()
                    if linha.get("comentario") is not None
                    else ""
                ),
                "criado_em": _iso(linha.get("criado_em")),
            }
        )

    for id_unidade, unidade in unidades_por_id.items():
        ids_leads_periodo = {
            int(conversa["id_cliente"]) for conversa in unidade["conversas"]
        }
        # O relatório de satisfação responde à pergunta "quantos desses leads".
        # Portanto, notas e comentários só entram quando o cliente também faz
        # parte da coorte que enviou mensagem à unidade dentro da janela.
        unidade["pesquisas"] = [
            item
            for item in unidade["pesquisas"]
            if int(item["id_cliente"]) in ids_leads_periodo
        ]
        pesquisas_unidade = unidade["pesquisas"]
        notas = [int(item["nota"]) for item in pesquisas_unidade if item["nota"] is not None]
        distribuicao = {str(nota): notas.count(nota) for nota in range(1, 6)}
        leads_com_nota = {
            item["id_cliente"] for item in pesquisas_unidade if item["nota"] is not None
        }
        ids_funil_periodo = funil_por_unidade[id_unidade] & ids_leads_periodo
        total_leads = len(ids_leads_periodo)
        total_funil = len(ids_funil_periodo)
        unidade["metricas"] = {
            "leads_contato": total_leads,
            "leads_funil": total_funil,
            "taxa_funil": round((total_funil / total_leads * 100), 1)
            if total_leads
            else 0.0,
            "leads_com_nota": len(leads_com_nota),
            "respostas_satisfacao": len(notas),
            "media_satisfacao": round(sum(notas) / len(notas), 2) if notas else None,
            "distribuicao_notas": distribuicao,
            "comentarios": sum(bool(item["comentario"]) for item in pesquisas_unidade),
            "taxa_participacao_satisfacao": round(
                len(leads_com_nota) / total_leads * 100, 1
            ) if total_leads else 0.0,
            "segmentacao_perfis": _montar_segmentacao_perfis(
                perfis_por_unidade[id_unidade],
                conversas_funil_por_unidade[id_unidade],
                idade_minima_suporte=unidade["idade_minima_suporte"],
                bpa_ativo=bool(unidade["bpa_ativo"]),
            ),
        }
        pesquisas_unidade.sort(
            key=lambda item: _ordenar_data(item["criado_em"]), reverse=True
        )

    return {
        "periodo": {
            "tipo": "semanal",
            "inicio": inicio.astimezone(timezone.utc).isoformat(),
            "fim": fim.astimezone(timezone.utc).isoformat(),
            "dias": (fim - inicio).total_seconds() / 86_400,
            "rotulo": (
                f"{_data_local(inicio, '%d/%m/%Y %H:%M')} até "
                f"{_data_local(fim, '%d/%m/%Y %H:%M')}"
            ),
        },
        "gerado_em": datetime.now(timezone.utc).isoformat(),
        "unidades": sorted(
            unidades_por_id.values(), key=lambda item: item["nome_unidade"].casefold()
        ),
    }


def _filtro_unidades(ids_unidade: Sequence[int] | None, alias: str = "u") -> tuple[str, tuple[Any, ...]]:
    if not ids_unidade:
        return "", ()
    ids = sorted(set(int(valor) for valor in ids_unidade))
    return f" AND {alias}.id_unidade = ANY(%s)", (ids,)


def _coluna_existe(cursor: Any, tabela: str, coluna: str) -> bool:
    cursor.execute(
        """
        SELECT EXISTS (
            SELECT 1
              FROM information_schema.columns
             WHERE table_schema = 'chatbot'
               AND table_name = %s
               AND column_name = %s
        ) AS existe
        """,
        (tabela, coluna),
    )
    return bool(cursor.fetchone()["existe"])


def coletar_snapshot(
    conn: Any,
    inicio: datetime,
    fim: datetime,
    ids_unidade: Sequence[int] | None = None,
    max_mensagens: int = MAX_MENSAGENS_PADRAO,
    statement_timeout_ms: int = 60_000,
) -> dict[str, Any]:
    """Consulta um snapshot consistente sem realizar nenhuma mutação."""
    if max_mensagens <= 0:
        raise ValueError("--max-mensagens precisa ser maior que zero")
    if statement_timeout_ms <= 0:
        raise ValueError("--statement-timeout-ms precisa ser maior que zero")

    from psycopg.rows import dict_row

    cursor = conn.cursor(row_factory=dict_row)
    try:
        cursor.execute("BEGIN TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
        cursor.execute(
            "SELECT set_config('statement_timeout', %s, true)",
            (f"{statement_timeout_ms}ms",),
        )
        cursor.execute("SELECT set_config('lock_timeout', '5000ms', true)")

        filtro, params_filtro = _filtro_unidades(ids_unidade)
        cursor.execute(
            f"""
            SELECT
                u.id_unidade,
                u.nome_unidade,
                u.nome_agente,
                u.idade_minima_suporte,
                u.bpa_ativo
              FROM chatbot.unidade_atendimento u
             WHERE TRUE {filtro}
             ORDER BY u.nome_unidade, u.id_unidade
            """,
            params_filtro,
        )
        unidades = cursor.fetchall()
        if ids_unidade and len(unidades) != len(set(ids_unidade)):
            encontrados = {int(linha["id_unidade"]) for linha in unidades}
            ausentes = sorted(set(ids_unidade) - encontrados)
            raise RuntimeError(f"Unidade(s) não encontrada(s): {ausentes}")

        tem_profissao_cliente = _coluna_existe(cursor, "cliente", "profissao")
        tem_profissao_conversa = _coluna_existe(cursor, "conversa", "profissao")
        expr_profissao_cliente = (
            "cl.profissao" if tem_profissao_cliente else "NULL::text"
        )
        if tem_profissao_conversa:
            expr_profissao_conversa = "cx_prof.profissao"
            lateral_profissao = """
               LEFT JOIN LATERAL (
                    SELECT cx_prof.profissao
                      FROM chatbot.conversa cx_prof
                     WHERE cx_prof.id_cliente = c.id_cliente
                       AND NULLIF(BTRIM(cx_prof.profissao), '') IS NOT NULL
                     ORDER BY cx_prof.iniciou_em DESC, cx_prof.id_conversa DESC
                     LIMIT 1
               ) cx_prof ON TRUE
            """
        else:
            expr_profissao_conversa = "NULL::text"
            lateral_profissao = ""

        filtro_mensagens, params_mensagens_filtro = _filtro_unidades(ids_unidade)
        cursor.execute(
            f"""
            WITH clientes_janela AS (
                SELECT DISTINCT c.id_unidade, c.id_cliente
                  FROM chatbot.historico_mensagens h0
                  JOIN chatbot.conversa c ON c.id_conversa = h0.id_conversa
                  JOIN chatbot.unidade_atendimento u ON u.id_unidade = c.id_unidade
                 WHERE h0.quem_enviou = 'cliente'
                   AND h0.received_data_hora >= %s
                   AND h0.received_data_hora < %s
                   {filtro_mensagens}
            )
            SELECT
                u.id_unidade,
                u.nome_unidade,
                c.id_cliente,
                cl.nome AS nome_cliente,
                cl.waid_telefone,
                cl.email,
                {expr_profissao_cliente} AS profissao_cliente,
                {expr_profissao_conversa} AS profissao_conversa_recente,
                c.id_conversa,
                c.status_ativa,
                c.status_dependente,
                c.id_etapa_atual,
                cl.idade AS idade_titular,
                d.idade AS idade_dependente,
                d.nome_dependente,
                h.id_mensagem,
                h.id_etapa,
                h.received_data_hora,
                h.quem_enviou,
                h.tipo_mensagem,
                h.conteudo_texto
              FROM clientes_janela cj
              JOIN chatbot.conversa c
                ON c.id_unidade = cj.id_unidade
               AND c.id_cliente = cj.id_cliente
              JOIN chatbot.unidade_atendimento u ON u.id_unidade = c.id_unidade
              JOIN chatbot.cliente cl ON cl.id_cliente = c.id_cliente
              LEFT JOIN chatbot.dependente d
                ON d.id_conversa = c.id_conversa AND d.id_cliente = c.id_cliente
              JOIN chatbot.historico_mensagens h ON h.id_conversa = c.id_conversa
              {lateral_profissao}
             WHERE h.received_data_hora >= %s
               AND h.received_data_hora < %s
               AND (
                    h.quem_enviou = 'cliente'
                    OR (h.quem_enviou = 'bot' AND h.status_envio = 'sent')
               )
             ORDER BY u.id_unidade, c.id_cliente,
                      h.received_data_hora, h.id_mensagem
             LIMIT %s
            """,
            (
                inicio,
                fim,
                *params_mensagens_filtro,
                inicio,
                fim,
                max_mensagens + 1,
            ),
        )
        mensagens = cursor.fetchall()
        if len(mensagens) > max_mensagens:
            raise RuntimeError(
                "O intervalo excedeu o limite de mensagens; reduza a janela ou "
                "aumente --max-mensagens conscientemente."
            )

        filtro_funil, params_funil_filtro = _filtro_unidades(ids_unidade)
        cursor.execute(
            f"""
            SELECT DISTINCT
                u.id_unidade,
                c.id_cliente,
                c.id_conversa,
                c.status_dependente,
                cl.idade AS idade_titular,
                d.idade AS idade_dependente,
                d.nome_dependente
              FROM chatbot.funil_envios f
              JOIN chatbot.conversa c ON c.id_conversa = f.id_conversa
              JOIN chatbot.unidade_atendimento u ON u.id_unidade = c.id_unidade
              JOIN chatbot.cliente cl ON cl.id_cliente = c.id_cliente
              LEFT JOIN chatbot.dependente d
                ON d.id_conversa = c.id_conversa AND d.id_cliente = c.id_cliente
             WHERE f.status = 'sent'
               AND f.enviado_em >= %s
               AND f.enviado_em < %s
               {filtro_funil}
            """,
            (inicio, fim, *params_funil_filtro),
        )
        funil = cursor.fetchall()

        filtro_pesquisa, params_pesquisa_filtro = _filtro_unidades(ids_unidade)
        cursor.execute(
            f"""
            SELECT
                u.id_unidade,
                c.id_cliente,
                c.id_conversa,
                cl.nome AS nome_cliente,
                cl.waid_telefone,
                {expr_profissao_cliente} AS profissao_cliente,
                {expr_profissao_conversa} AS profissao_conversa_recente,
                p.nota,
                p.comentario,
                p.criado_em
              FROM chatbot.pesquisa_satisfacao p
              JOIN chatbot.conversa c ON c.id_conversa = p.id_conversa
              JOIN chatbot.unidade_atendimento u ON u.id_unidade = c.id_unidade
              JOIN chatbot.cliente cl ON cl.id_cliente = c.id_cliente
               {lateral_profissao}
             WHERE p.criado_em >= %s
               AND p.criado_em < %s
               {filtro_pesquisa}
             ORDER BY p.criado_em DESC, p.id_pesquisa_satisfacao DESC
            """,
            (inicio, fim, *params_pesquisa_filtro),
        )
        pesquisas = cursor.fetchall()

        snapshot = montar_snapshot(
            unidades=unidades,
            mensagens=mensagens,
            funil=funil,
            pesquisas=pesquisas,
            inicio=inicio,
            fim=fim,
        )
        conn.rollback()
        return snapshot
    except Exception:
        conn.rollback()
        raise
    finally:
        cursor.close()


def _json_seguro(valor: Any) -> str:
    return (
        json.dumps(valor, ensure_ascii=False, separators=(",", ":"))
        .replace("&", "\\u0026")
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
        .replace("\u2028", "\\u2028")
        .replace("\u2029", "\\u2029")
    )


def renderizar_html(unidade: Mapping[str, Any], periodo: Mapping[str, Any]) -> str:
    """Cria um dashboard offline; dados do banco entram apenas como JSON seguro."""
    payload = {
        "unidade": {
            "id_unidade": unidade["id_unidade"],
            "nome_unidade": unidade["nome_unidade"],
            "nome_agente": unidade["nome_agente"],
            "conversas": unidade["conversas"],
            "pesquisas": unidade["pesquisas"],
            "metricas": unidade["metricas"],
        },
        "periodo": periodo,
    }
    nome_titulo = html_escape(str(unidade["nome_unidade"]), quote=True)
    dados_json = _json_seguro(payload)
    return f'''<!doctype html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <meta name="robots" content="noindex,nofollow">
  <title>Conversas — {nome_titulo}</title>
  <style>
    :root{{--verde:#00a884;--verde2:#008069;--fundo:#efeae2;--painel:#f7f9fa;
      --linha:#e5e7eb;--texto:#182229;--muted:#667781;--bot:#d9fdd3;--cliente:#fff;
      --sombra:0 18px 60px rgba(24,34,41,.16)}}
    *{{box-sizing:border-box}} html,body{{height:100%;margin:0}}
    body{{font:14px/1.45 "Segoe UI",Arial,sans-serif;color:var(--texto);
      background:linear-gradient(180deg,var(--verde2) 0 126px,#e9edef 126px)}}
    button,input{{font:inherit}} .app{{height:calc(100vh - 34px);min-height:620px;max-width:1500px;
      margin:17px auto;background:#fff;display:grid;grid-template-columns:390px 1fr;grid-template-rows:minmax(0,1fr);
      overflow:hidden;box-shadow:var(--sombra);border-radius:5px}}
    .sidebar{{display:flex;flex-direction:column;min-width:0;min-height:0;overflow:hidden;border-right:1px solid var(--linha);background:#fff}}
    .brand{{padding:18px 20px;background:#f0f2f5;border-bottom:1px solid var(--linha)}}
    .brand h1{{font-size:17px;margin:0 0 3px}} .brand p{{margin:0;color:var(--muted);font-size:12px}}
    .stats{{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;padding:12px;border-bottom:1px solid var(--linha)}}
    .stat{{padding:10px 8px;border:1px solid #e6ecea;border-radius:10px;background:#fbfdfc;text-align:center}}
    .stat b{{display:block;font-size:18px;color:var(--verde2)}} .stat span{{font-size:10px;color:var(--muted)}}
    .search{{padding:9px 12px;background:var(--painel)}}
    .search input{{width:100%;border:0;border-radius:8px;background:#fff;padding:10px 13px;outline:none}}
    .list{{min-height:0;overflow-y:auto;overscroll-behavior:contain;flex:1}} .empty{{padding:32px;color:var(--muted);text-align:center}}
    .chat-item{{width:100%;display:grid;grid-template-columns:46px 1fr;gap:11px;text-align:left;
      padding:12px 14px;border:0;border-bottom:1px solid #edf0f2;background:#fff;cursor:pointer}}
    .chat-item:hover,.chat-item.active{{background:#f0f2f5}}
    .avatar{{width:46px;height:46px;border-radius:50%;background:linear-gradient(145deg,#cfd8dc,#90a4ae);
      color:#fff;display:grid;place-items:center;font-weight:700;font-size:17px}}
    .item-top{{display:flex;justify-content:space-between;gap:8px}} .item-top strong{{white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}
    .item-top time{{font-size:11px;color:var(--muted);white-space:nowrap}}
    .preview{{color:var(--muted);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;font-size:12px;margin-top:4px}}
    .main{{min-width:0;min-height:0;overflow:hidden;display:flex;flex-direction:column;background:var(--fundo)}}
    .topbar{{min-height:74px;padding:11px 18px;background:#f0f2f5;border-bottom:1px solid var(--linha);display:flex;align-items:center;gap:13px}}
    .identity{{min-width:0;flex:1}} .identity h2{{font-size:16px;margin:0 0 2px}} .identity p{{margin:0;color:var(--muted);font-size:12px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}
    .tag{{border:1px solid #badfd7;background:#e8f7f3;color:#087966;border-radius:999px;padding:4px 9px;font-size:11px}}
    .messages{{flex:1;min-height:0;overflow-y:auto;overscroll-behavior:contain;padding:28px clamp(18px,6vw,84px);background-color:var(--fundo);
      background-image:radial-gradient(rgba(98,114,124,.09) .7px,transparent .7px);background-size:14px 14px}}
    .intro{{max-width:720px;margin:20vh auto 0;padding:26px;text-align:center;background:rgba(255,255,255,.82);border-radius:14px;color:var(--muted)}}
    .day,.conversation-cut{{width:max-content;max-width:95%;margin:14px auto;padding:5px 10px;border-radius:7px;background:#fff;color:var(--muted);font-size:11px;box-shadow:0 1px 2px rgba(0,0,0,.08)}}
    .conversation-cut{{background:#fff6cf;color:#665c25}}
    .row{{display:flex;margin:3px 0}} .row.bot{{justify-content:flex-end}}
    .bubble{{position:relative;max-width:min(72%,720px);padding:7px 9px 5px;border-radius:8px;background:var(--cliente);box-shadow:0 1px 1px rgba(0,0,0,.08);white-space:pre-wrap;overflow-wrap:anywhere}}
    .row.bot .bubble{{background:var(--bot)}} .meta{{display:flex;justify-content:flex-end;gap:7px;margin:4px 0 0 16px;color:var(--muted);font-size:10px}}
    .details{{padding:9px 18px;background:#f0f2f5;color:var(--muted);font-size:11px;border-top:1px solid var(--linha)}}
    @media(max-width:820px){{.app{{margin:0;height:100vh;min-height:0;border-radius:0;grid-template-columns:132px 1fr}}.brand p,.stats,.preview,.chat-item .item-top time{{display:none}}.chat-item{{grid-template-columns:40px 1fr;padding:10px 8px}}.avatar{{width:40px;height:40px}}.bubble{{max-width:90%}}}}
    @media print{{body{{background:#fff}}.app{{height:auto;margin:0;box-shadow:none}}}}
  </style>
  <style>
    :root{{--wa-bg:#0b141a;--wa-panel:#111b21;--wa-panel-2:#202c33;--wa-border:#2a3942;
      --wa-text:#e9edef;--wa-muted:#8696a0;--wa-green:#00a884;--wa-green-dark:#005c4b;
      --wa-client:#202c33;--wa-bot:#005c4b;--wa-blue:#53bdeb}}
    body{{color:var(--wa-text);background:var(--wa-bg)}}
    .app{{height:100vh;min-height:560px;max-width:none;margin:0;border-radius:0;
      grid-template-columns:390px minmax(0,1fr);background:var(--wa-bg);box-shadow:none}}
    .sidebar{{background:var(--wa-panel);border-color:var(--wa-border)}}
    .brand{{padding:17px 18px;background:var(--wa-panel-2);border-color:var(--wa-border)}}
    .brand h1{{font-size:18px;color:var(--wa-text)}} .brand p{{color:var(--wa-muted)}}
    .stats{{grid-template-columns:repeat(4,1fr);gap:6px;padding:10px;background:var(--wa-panel);border-color:var(--wa-border)}}
    .stat{{padding:9px 4px;border-color:var(--wa-border);border-radius:8px;background:#18252d}}
    .stat b{{font-size:17px;color:#66d6bc}} .stat span{{font-size:9px;color:var(--wa-muted)}}
    .search{{padding:8px 12px;background:var(--wa-panel)}}
    .search input{{color:var(--wa-text);background:var(--wa-panel-2);padding:10px 14px}}
    .search input::placeholder{{color:var(--wa-muted)}}
    .filters{{display:flex;gap:6px;padding:0 12px 10px;overflow-x:auto;border-bottom:1px solid var(--wa-border)}}
    .filter{{border:1px solid var(--wa-border);border-radius:999px;padding:6px 10px;color:var(--wa-muted);
      background:transparent;cursor:pointer;white-space:nowrap;font-size:11px}}
    .filter:hover,.filter.active{{color:#d8fff5;background:#123c35;border-color:#1f6c5d}}
    .list{{background:var(--wa-panel)}} .empty{{color:var(--wa-muted)}}
    .chat-item{{grid-template-columns:49px 1fr;gap:12px;padding:12px 14px;color:var(--wa-text);
      border-color:var(--wa-border);background:var(--wa-panel)}}
    .chat-item:hover,.chat-item.active{{background:var(--wa-panel-2)}}
    .avatar{{width:49px;height:49px;background:#667781;color:#fff}}
    .item-top time,.preview{{color:var(--wa-muted)}}
    .item-bottom{{display:flex;align-items:center;gap:7px;margin-top:4px;min-width:0}}
    .item-bottom .preview{{flex:1;margin:0}} .count{{min-width:20px;padding:2px 6px;border-radius:999px;
      background:var(--wa-green);color:#061b16;text-align:center;font-size:10px;font-weight:700}}
    .flags{{display:flex;gap:4px;margin-top:5px;min-height:17px}}
    .flag{{padding:2px 6px;border-radius:4px;background:#23343e;color:#aebac1;font-size:9px}}
    .flag.green{{background:#12493f;color:#8de7d1}} .flag.gold{{background:#4a3e1f;color:#f2d57a}}
    .main{{position:relative;background-color:var(--wa-bg);
      background-image:radial-gradient(rgba(255,255,255,.035) .75px,transparent .75px);background-size:13px 13px}}
    .topbar{{min-height:66px;padding:8px 15px;background:var(--wa-panel-2);border-color:var(--wa-border)}}
    .identity h2{{color:var(--wa-text)}} .identity p{{color:var(--wa-muted)}}
    .tag{{border-color:#1e6e5d;background:#123c35;color:#8de7d1}}
    .icon-button{{border:1px solid var(--wa-border);border-radius:8px;padding:7px 10px;color:var(--wa-muted);
      background:#18252d;cursor:pointer}} .icon-button:hover,.icon-button[aria-pressed="true"]{{color:#d8fff5;border-color:#1f6c5d}}
    .back{{display:none;font-size:25px;line-height:1;padding:3px 10px}}
    .messages{{padding:24px clamp(18px,6vw,82px);background:transparent}}
    .intro{{margin-top:18vh;background:rgba(32,44,51,.94);color:var(--wa-muted);border:1px solid var(--wa-border)}}
    .intro h2{{color:var(--wa-text)}}
    .day,.conversation-cut{{background:#18252d;color:#aebac1;box-shadow:0 1px 1px rgba(0,0,0,.35)}}
    .conversation-cut{{background:#23343e;color:#aebac1;border:1px solid #304652}}
    .conversation-cut.continuation{{background:#123c35;color:#8de7d1;border-color:#1f6c5d}}
    .bubble{{max-width:min(76%,760px);padding:7px 9px 6px;color:var(--wa-text);background:var(--wa-client);
      box-shadow:0 1px 1px rgba(0,0,0,.28)}} .row.bot .bubble{{background:var(--wa-bot)}}
    .message-kind{{display:inline-block;margin-bottom:4px;padding:2px 6px;border-radius:4px;background:rgba(255,255,255,.09);
      color:#b7c7cf;font-size:9px;text-transform:uppercase;letter-spacing:.04em}}
    .meta{{color:#aebac1}} .ticks{{color:var(--wa-blue);font-weight:700}}
    .technical{{display:none;padding-top:4px;color:#8fa2ac;font-size:9px}} body.show-metadata .technical{{display:block}}
    .details{{padding:8px 18px;color:var(--wa-muted);background:var(--wa-panel-2);border-color:var(--wa-border)}}
    .scroll-bottom{{position:absolute;right:24px;bottom:50px;width:42px;height:42px;border:1px solid var(--wa-border);
      border-radius:50%;color:var(--wa-text);background:var(--wa-panel-2);box-shadow:0 4px 16px rgba(0,0,0,.35);
      cursor:pointer;font-size:22px}}
    @media(max-width:820px){{
      .app{{display:block;height:100vh}} .sidebar{{height:100vh}} .main{{display:none;height:100vh}}
      body.chat-open .sidebar{{display:none}} body.chat-open .main{{display:flex}} .back{{display:inline-block}}
      .brand p,.preview,.item-top time{{display:block}} .stats{{display:grid}}
      .chat-item{{grid-template-columns:46px 1fr;padding:11px 13px}} .avatar{{width:46px;height:46px}}
      .bubble{{max-width:90%}} .messages{{padding:18px 12px}} .tag{{display:none}}
    }}
    @media print{{body{{background:#fff;color:#111}}.app{{height:auto}}}}
  </style>
</head>
<body>
  <main class="app">
    <aside class="sidebar">
      <header class="brand"><h1 id="unitName"></h1><p id="period"></p></header>
      <section class="stats" aria-label="Resumo do período">
        <div class="stat"><b id="leadCount">0</b><span>LEADS</span></div>
        <div class="stat"><b id="messageCount">0</b><span>MENSAGENS</span></div>
        <div class="stat"><b id="funnelCount">0</b><span>FUNIL</span></div>
        <div class="stat"><b id="ratingAverage">—</b><span>NOTA MÉDIA</span></div>
      </section>
      <div class="search"><input id="search" type="search" placeholder="Pesquisar lead ou mensagem" aria-label="Pesquisar conversas"></div>
      <nav class="filters" aria-label="Filtrar conversas">
        <button type="button" class="filter active" data-filter="all">Todas</button>
        <button type="button" class="filter" data-filter="continued">Continuações</button>
        <button type="button" class="filter" data-filter="funnel">Funil</button>
        <button type="button" class="filter" data-filter="rated">Avaliadas</button>
      </nav>
      <div id="chatList" class="list"></div>
    </aside>
    <section class="main">
      <header id="topbar" class="topbar" hidden>
        <button id="backButton" class="icon-button back" type="button" aria-label="Voltar para conversas">‹</button>
        <div id="avatarMain" class="avatar"></div>
        <div class="identity"><h2 id="clientName"></h2><p id="clientDetails"></p></div>
        <span id="funnelTag" class="tag" hidden>Enviado ao funil</span>
        <button id="metadataButton" class="icon-button" type="button" aria-pressed="false">Detalhes</button>
      </header>
      <div id="messages" class="messages"><div class="intro"><h2>Conversas do período</h2><p>Selecione um lead para visualizar a sequência completa das conversas técnicas no período.</p></div></div>
      <button id="scrollBottom" class="scroll-bottom" type="button" aria-label="Ir para a mensagem mais recente" hidden>↓</button>
      <footer id="details" class="details">Relatório privado: contém dados pessoais e deve ser compartilhado somente com a unidade responsável.</footer>
    </section>
  </main>
  <script id="report-data" type="application/json">{dados_json}</script>
  <script>
  (() => {{
    'use strict';
    const data = JSON.parse(document.getElementById('report-data').textContent);
    const unit = data.unidade, conversations = unit.conversas || [];
    const $ = id => document.getElementById(id);
    const fmt = iso => iso ? new Intl.DateTimeFormat('pt-BR', {{dateStyle:'short',timeStyle:'short',timeZone:'America/Sao_Paulo'}}).format(new Date(iso)) : '—';
    const fmtDate = iso => iso ? new Intl.DateTimeFormat('pt-BR', {{dateStyle:'short',timeZone:'America/Sao_Paulo'}}).format(new Date(iso)) : '—';
    const fmtTime = iso => iso ? new Intl.DateTimeFormat('pt-BR', {{hour:'2-digit',minute:'2-digit',timeZone:'America/Sao_Paulo'}}).format(new Date(iso)) : '—';
    const initials = name => (name || '?').split(/\\s+/).slice(0,2).map(x => x[0] || '').join('').toUpperCase();
    $('unitName').textContent = unit.nome_unidade;
    $('period').textContent = data.periodo.rotulo;
    $('leadCount').textContent = unit.metricas.leads_contato;
    $('funnelCount').textContent = unit.metricas.leads_funil;
    $('ratingAverage').textContent = unit.metricas.media_satisfacao ?? '—';

    function addText(parent, tag, className, text) {{
      const node = document.createElement(tag); node.className = className || ''; node.textContent = text; parent.appendChild(node); return node;
    }}
    function showConversation(item) {{
      document.querySelectorAll('.chat-item').forEach(x => x.classList.toggle('active', x.dataset.client === String(item.id_cliente)));
      $('topbar').hidden = false; $('clientName').textContent = item.nome; $('avatarMain').textContent = initials(item.nome);
      const parts = [item.waid_telefone && `WA ID: ${{item.waid_telefone}}`, item.email, item.profissao && `Profissão: ${{item.profissao}}`].filter(Boolean);
      $('clientDetails').textContent = parts.join(' • ') || `Cliente #${{item.id_cliente}}`;
      $('funnelTag').hidden = !item.foi_funil;
      const box = $('messages'); box.replaceChildren(); let lastDay = '', lastConversation = null;
      item.mensagens.forEach(msg => {{
        const d = new Date(msg.data); const day = new Intl.DateTimeFormat('pt-BR', {{dateStyle:'long',timeZone:'America/Sao_Paulo'}}).format(d);
        if (day !== lastDay) {{ addText(box,'div','day',day); lastDay = day; }}
        if (lastConversation !== null && lastConversation !== msg.id_conversa) addText(box,'div','conversation-cut',`Continuação técnica • conversa #${{msg.id_conversa}}`);
        lastConversation = msg.id_conversa;
        const row = document.createElement('div'); row.className = `row ${{msg.quem_enviou === 'bot' ? 'bot' : 'client'}}`;
        const bubble = document.createElement('div'); bubble.className = 'bubble'; addText(bubble,'div','',msg.texto);
        const meta = addText(bubble,'div','meta',''); addText(meta,'span','',`etapa ${{msg.id_etapa ?? '—'}}`); addText(meta,'time','',fmtTime(msg.data));
        row.appendChild(bubble); box.appendChild(row);
      }});
      $('details').textContent = `Cliente #${{item.id_cliente}} • conversas técnicas: ${{item.ids_conversa.join(', ')}} • ${{item.mensagens.length}} mensagens visíveis no período`;
      box.scrollTop = box.scrollHeight;
    }}
    function renderList(filter='') {{
      const needle = filter.trim().toLocaleLowerCase('pt-BR'); const list = $('chatList'); list.replaceChildren();
      const visible = conversations.filter(item => [item.nome,item.waid_telefone,item.email,item.profissao].filter(Boolean).join(' ').toLocaleLowerCase('pt-BR').includes(needle));
      if (!visible.length) {{ addText(list,'div','empty',conversations.length ? 'Nenhum lead encontrado.' : 'Nenhuma mensagem de cliente no período.'); return; }}
      visible.forEach(item => {{
        const button = document.createElement('button'); button.type='button'; button.className='chat-item'; button.dataset.client=String(item.id_cliente);
        addText(button,'div','avatar',initials(item.nome)); const body=document.createElement('div'); const top=document.createElement('div'); top.className='item-top';
        addText(top,'strong','',item.nome); addText(top,'time','',fmtDate(item.ultima_atividade)); body.appendChild(top);
        const last=item.mensagens[item.mensagens.length-1]; addText(body,'div','preview',last ? `${{last.quem_enviou==='bot'?'✓ ':''}}${{last.texto}}` : 'Sem mensagens'); button.appendChild(body);
        button.addEventListener('click',()=>showConversation(item)); list.appendChild(button);
      }});
    }}
    $('search').addEventListener('input',event=>renderList(event.target.value)); renderList(); if (conversations[0]) showConversation(conversations[0]);
  }})();
  </script>
  <script>
  (() => {{
    'use strict';
    const data = JSON.parse(document.getElementById('report-data').textContent);
    const unit = data.unidade;
    const conversations = unit.conversas || [];
    const surveys = unit.pesquisas || [];
    const $ = id => document.getElementById(id);
    const colors = ['#7e57c2','#00897b','#5c6bc0','#d97706','#0288d1','#c44569','#5f7c3a','#8d6e63'];
    const ratingsByClient = new Map();
    let activeFilter = 'all';
    let selectedClient = null;

    surveys.forEach(survey => {{
      if (survey.nota !== null && survey.nota !== undefined) {{
        ratingsByClient.set(String(survey.id_cliente), survey.nota);
      }}
    }});

    const fmtDate = iso => iso ? new Intl.DateTimeFormat('pt-BR', {{
      dateStyle:'short', timeZone:'America/Sao_Paulo'
    }}).format(new Date(iso)) : '—';
    const fmtTime = iso => iso ? new Intl.DateTimeFormat('pt-BR', {{
      hour:'2-digit', minute:'2-digit', timeZone:'America/Sao_Paulo'
    }}).format(new Date(iso)) : '—';
    const fmtDay = iso => iso ? new Intl.DateTimeFormat('pt-BR', {{
      dateStyle:'long', timeZone:'America/Sao_Paulo'
    }}).format(new Date(iso)) : '—';
    const initials = name => (name || '?').split(/\\s+/).slice(0,2)
      .map(part => part[0] || '').join('').toUpperCase();
    const avatarColor = id => colors[Math.abs(Number(id) || 0) % colors.length];

    function addText(parent, tag, className, value) {{
      const node = document.createElement(tag);
      node.className = className || '';
      node.textContent = value;
      parent.appendChild(node);
      return node;
    }}

    function preview(message) {{
      if (!message) return 'Sem mensagens';
      const content = message.texto || '[' + (message.tipo || 'mensagem') + ']';
      return (message.quem_enviou === 'bot' ? '✓✓ ' : '') + content;
    }}

    function matchesFilter(item) {{
      if (activeFilter === 'continued') return item.ids_conversa.length > 1;
      if (activeFilter === 'funnel') return Boolean(item.foi_funil);
      if (activeFilter === 'rated') return ratingsByClient.has(String(item.id_cliente));
      return true;
    }}

    function showConversation(item) {{
      selectedClient = String(item.id_cliente);
      document.body.classList.add('chat-open');
      document.querySelectorAll('.chat-item').forEach(button => {{
        button.classList.toggle('active', button.dataset.client === selectedClient);
      }});
      $('topbar').hidden = false;
      $('clientName').textContent = item.nome;
      $('avatarMain').textContent = initials(item.nome);
      $('avatarMain').style.backgroundColor = avatarColor(item.id_cliente);
      const parts = [
        item.waid_telefone ? 'WA ID: ' + item.waid_telefone : '',
        item.email || '',
        item.profissao ? 'Profissão: ' + item.profissao : ''
      ].filter(Boolean);
      $('clientDetails').textContent = parts.join(' • ') || 'Cliente #' + item.id_cliente;
      $('funnelTag').hidden = !item.foi_funil;

      const box = $('messages');
      box.replaceChildren();
      let lastDay = '';
      let lastConversation = null;
      item.mensagens.forEach(message => {{
        const day = fmtDay(message.data);
        if (day !== lastDay) {{
          addText(box,'div','day',day);
          lastDay = day;
        }}
        if (lastConversation !== message.id_conversa) {{
          const first = lastConversation === null;
          const label = (first ? 'Início técnico' : 'Continuação técnica') +
            ' • conversa #' + message.id_conversa;
          const separator = addText(
            box,'div','conversation-cut' + (first ? '' : ' continuation'),label
          );
          separator.title = 'As conversas foram unidas porque pertencem ao mesmo cliente e à mesma unidade.';
        }}
        lastConversation = message.id_conversa;
        const isBot = message.quem_enviou === 'bot';
        const row = document.createElement('div');
        row.className = 'row ' + (isBot ? 'bot' : 'client');
        const bubble = document.createElement('div');
        bubble.className = 'bubble';
        if (message.tipo && message.tipo !== 'text') {{
          addText(bubble,'span','message-kind',message.tipo);
        }}
        addText(
          bubble,'div','',
          message.texto || '[' + (message.tipo || 'mensagem sem texto') + ']'
        );
        const technical = addText(
          bubble,'div','technical',
          'mensagem #' + message.id_mensagem +
          ' • conversa #' + message.id_conversa +
          ' • etapa ' + (message.id_etapa ?? '—') +
          ' • tipo ' + (message.tipo || '—')
        );
        technical.setAttribute('aria-hidden','true');
        const meta = addText(bubble,'div','meta','');
        addText(meta,'time','',fmtTime(message.data));
        if (isBot) addText(meta,'span','ticks','✓✓');
        row.appendChild(bubble);
        box.appendChild(row);
      }});

      const rating = ratingsByClient.get(String(item.id_cliente));
      $('details').textContent =
        'Cliente #' + item.id_cliente +
        ' • conversas técnicas: ' + item.ids_conversa.join(', ') +
        ' • ' + item.mensagens.length + ' mensagens no período' +
        (rating === undefined ? '' : ' • satisfação: ' + rating);
      box.scrollTop = box.scrollHeight;
      $('scrollBottom').hidden = true;
    }}

    const oldSearch = $('search');
    const search = oldSearch.cloneNode(true);
    oldSearch.replaceWith(search);

    function renderList() {{
      const needle = search.value.trim().toLocaleLowerCase('pt-BR');
      const list = $('chatList');
      list.replaceChildren();
      const visible = conversations.filter(item => {{
        const searchable = [item.nome,item.waid_telefone,item.email,item.profissao]
          .concat(item.mensagens.map(message => message.texto))
          .filter(Boolean).join(' ').toLocaleLowerCase('pt-BR');
        return matchesFilter(item) && searchable.includes(needle);
      }});
      if (!visible.length) {{
        addText(
          list,'div','empty',
          conversations.length ? 'Nenhum lead encontrado.' : 'Nenhuma mensagem de cliente no período.'
        );
        return;
      }}
      visible.forEach(item => {{
        const button = document.createElement('button');
        button.type = 'button';
        button.className = 'chat-item';
        button.dataset.client = String(item.id_cliente);
        if (selectedClient === button.dataset.client) button.classList.add('active');
        const avatar = addText(button,'div','avatar',initials(item.nome));
        avatar.style.backgroundColor = avatarColor(item.id_cliente);
        const body = document.createElement('div');
        const top = document.createElement('div');
        top.className = 'item-top';
        addText(top,'strong','',item.nome);
        addText(top,'time','',fmtDate(item.ultima_atividade));
        body.appendChild(top);
        const bottom = document.createElement('div');
        bottom.className = 'item-bottom';
        addText(bottom,'div','preview',preview(item.mensagens[item.mensagens.length - 1]));
        addText(bottom,'span','count',String(item.mensagens.length));
        body.appendChild(bottom);
        const flags = document.createElement('div');
        flags.className = 'flags';
        if (item.ids_conversa.length > 1) {{
          addText(flags,'span','flag',item.ids_conversa.length + ' conversas unidas');
        }}
        if (item.foi_funil) addText(flags,'span','flag green','funil');
        const rating = ratingsByClient.get(String(item.id_cliente));
        if (rating !== undefined) addText(flags,'span','flag gold','nota ' + rating);
        body.appendChild(flags);
        button.appendChild(body);
        button.addEventListener('click',() => showConversation(item));
        list.appendChild(button);
      }});
    }}

    $('period').textContent =
      (unit.nome_agente ? 'Agente ' + unit.nome_agente + ' • ' : '') + data.periodo.rotulo;
    $('messageCount').textContent = conversations.reduce(
      (total,item) => total + item.mensagens.length, 0
    );
    search.addEventListener('input',renderList);
    document.querySelectorAll('.filter').forEach(button => {{
      button.addEventListener('click',() => {{
        activeFilter = button.dataset.filter;
        document.querySelectorAll('.filter').forEach(candidate => {{
          candidate.classList.toggle('active',candidate === button);
        }});
        renderList();
      }});
    }});
    $('metadataButton').addEventListener('click',() => {{
      const enabled = document.body.classList.toggle('show-metadata');
      $('metadataButton').setAttribute('aria-pressed',String(enabled));
      document.querySelectorAll('.technical').forEach(node => {{
        node.setAttribute('aria-hidden',String(!enabled));
      }});
    }});
    $('backButton').addEventListener('click',() => {{
      document.body.classList.remove('chat-open');
    }});
    $('messages').addEventListener('scroll',() => {{
      const box = $('messages');
      $('scrollBottom').hidden = box.scrollHeight - box.scrollTop - box.clientHeight < 140;
    }});
    $('scrollBottom').addEventListener('click',() => {{
      $('messages').scrollTo({{top:$('messages').scrollHeight,behavior:'smooth'}});
    }});
    renderList();
    if (conversations[0] && window.matchMedia('(min-width:821px)').matches) {{
      showConversation(conversations[0]);
    }}
  }})();
  </script>
</body>
</html>'''


def _registrar_fontes_pdf() -> tuple[str, str]:
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont

    candidatos = [
        (
            Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts/arial.ttf",
            Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts/arialbd.ttf",
        ),
        (
            Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
            Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
        ),
    ]
    for regular, bold in candidatos:
        if regular.is_file() and bold.is_file():
            try:
                pdfmetrics.registerFont(TTFont("Monitoramento", str(regular)))
                pdfmetrics.registerFont(TTFont("Monitoramento-Bold", str(bold)))
                pdfmetrics.registerFontFamily(
                    "Monitoramento",
                    normal="Monitoramento",
                    bold="Monitoramento-Bold",
                )
                return "Monitoramento", "Monitoramento-Bold"
            except Exception:
                continue
    return "Helvetica", "Helvetica-Bold"


def renderizar_pdf(
    unidade: Mapping[str, Any],
    periodo: Mapping[str, Any],
    destino: Path,
) -> None:
    """Renderiza um PDF vetorial, paginado e adequado para impressão."""
    try:
        from reportlab.lib import colors
        from reportlab.lib.enums import TA_CENTER, TA_LEFT
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.lib.units import mm
        from reportlab.platypus import (
            CondPageBreak,
            HRFlowable,
            KeepTogether,
            LongTable,
            PageBreak,
            Paragraph,
            SimpleDocTemplate,
            Spacer,
            Table,
            TableStyle,
        )
    except ImportError as exc:
        raise RuntimeError(
            "ReportLab não está instalado. Execute: "
            "pip install -r utilitarios/requirements-monitoramento.txt"
        ) from exc

    fonte, fonte_bold = _registrar_fontes_pdf()
    verde = colors.HexColor("#008069")
    cinza = colors.HexColor("#667781")
    cinza_claro = colors.HexColor("#F4F6F7")
    amarelo = colors.HexColor("#F4B400")
    texto = colors.HexColor("#182229")

    estilos_base = getSampleStyleSheet()
    estilos = {
        "titulo": ParagraphStyle(
            "Titulo",
            parent=estilos_base["Title"],
            fontName=fonte_bold,
            fontSize=20,
            leading=24,
            textColor=colors.white,
            alignment=TA_LEFT,
            spaceAfter=3 * mm,
        ),
        "subtitulo_capa": ParagraphStyle(
            "SubtituloCapa",
            parent=estilos_base["BodyText"],
            fontName=fonte,
            fontSize=10,
            leading=14,
            textColor=colors.HexColor("#D6F3EC"),
        ),
        "secao": ParagraphStyle(
            "Secao",
            parent=estilos_base["Heading2"],
            fontName=fonte_bold,
            fontSize=15,
            leading=19,
            textColor=verde,
            spaceBefore=4 * mm,
            spaceAfter=2.5 * mm,
        ),
        "corpo": ParagraphStyle(
            "Corpo",
            parent=estilos_base["BodyText"],
            fontName=fonte,
            fontSize=9,
            leading=13,
            textColor=texto,
        ),
        "pequeno": ParagraphStyle(
            "Pequeno",
            parent=estilos_base["BodyText"],
            fontName=fonte,
            fontSize=7.5,
            leading=10,
            textColor=cinza,
        ),
        "centro": ParagraphStyle(
            "Centro",
            parent=estilos_base["BodyText"],
            fontName=fonte,
            fontSize=9,
            leading=12,
            alignment=TA_CENTER,
            textColor=texto,
        ),
        "cabecalho_tabela": ParagraphStyle(
            "CabecalhoTabela",
            fontName=fonte_bold,
            fontSize=8,
            leading=11,
            textColor=colors.white,
        ),
        "indicador": ParagraphStyle(
            "Indicador",
            fontName=fonte_bold,
            fontSize=23,
            leading=28,
            alignment=TA_CENTER,
            textColor=verde,
        ),
        "rotulo_indicador": ParagraphStyle(
            "RotuloIndicador",
            fontName=fonte,
            fontSize=8,
            leading=11,
            alignment=TA_CENTER,
            textColor=texto,
        ),
        "comentario": ParagraphStyle(
            "Comentario",
            parent=estilos_base["BodyText"],
            fontName=fonte,
            fontSize=9,
            leading=14,
            leftIndent=4 * mm,
            rightIndent=3 * mm,
            borderColor=colors.HexColor("#B9E4D9"),
            borderWidth=0,
            borderPadding=(2 * mm, 3 * mm, 2 * mm, 3 * mm),
            backColor=colors.HexColor("#F5FBF9"),
            textColor=texto,
            spaceAfter=2 * mm,
        ),
    }

    def p(valor: Any, estilo: str = "corpo") -> Any:
        texto_seguro = html_escape(str(valor if valor not in (None, "") else "—"))
        return Paragraph(texto_seguro.replace("\n", "<br/>"), estilos[estilo])

    def percentual(valor: float) -> str:
        return f"{valor:.1f}%".replace(".", ",")

    nome_unidade = str(unidade["nome_unidade"])
    metricas = unidade["metricas"]
    gerado_em = datetime.now(timezone.utc)
    dias_periodo = float(periodo.get("dias") or 0)
    if periodo.get("tipo") == "total":
        selo_periodo = "HISTÓRICO TOTAL"
    elif dias_periodo.is_integer():
        selo_periodo = f"ÚLTIMOS {int(dias_periodo)} DIAS"
    else:
        selo_periodo = "JANELA DO RELATÓRIO"
    destino.parent.mkdir(parents=True, exist_ok=True)
    documento = SimpleDocTemplate(
        str(destino),
        pagesize=A4,
        rightMargin=16 * mm,
        leftMargin=16 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
        title=f"Desempenho — {nome_unidade}",
        author="Monitoramento do chatbot",
        subject=f"Indicadores de {periodo['rotulo']}",
    )

    def cabecalho_rodape(canvas: Any, doc: Any) -> None:
        canvas.saveState()
        largura, altura = A4
        canvas.setStrokeColor(colors.HexColor("#DDE4E7"))
        canvas.line(16 * mm, 13 * mm, largura - 16 * mm, 13 * mm)
        canvas.setFont(fonte, 7.5)
        canvas.setFillColor(cinza)
        canvas.drawString(16 * mm, 8.5 * mm, nome_unidade)
        canvas.drawRightString(
            largura - 16 * mm,
            8.5 * mm,
            f"Página {doc.page} • gerado {_data_local(gerado_em)}",
        )
        canvas.setFont(fonte, 6.5)
        canvas.drawString(
            16 * mm, 4.5 * mm,
            "Documento privado • dados pessoais • uso exclusivo de pessoas autorizadas da unidade.",
        )
        canvas.restoreState()

    historia: list[Any] = []
    capa = Table(
        [
            [
                Paragraph("Relatório de desempenho", estilos["titulo"]),
                p(selo_periodo, "centro"),
            ],
            [
                Paragraph(
                    f"<b>{html_escape(nome_unidade)}</b><br/>{html_escape(str(periodo['rotulo']))}",
                    estilos["subtitulo_capa"],
                ),
                "",
            ],
        ],
        colWidths=[135 * mm, 32 * mm],
    )
    capa.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), verde),
                ("SPAN", (0, 1), (1, 1)),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TEXTCOLOR", (1, 0), (1, 0), verde),
                ("BACKGROUND", (1, 0), (1, 0), colors.white),
                ("BOX", (1, 0), (1, 0), 0.5, colors.white),
                ("LEFTPADDING", (0, 0), (-1, -1), 7 * mm),
                ("RIGHTPADDING", (0, 0), (-1, -1), 7 * mm),
                ("TOPPADDING", (0, 0), (-1, -1), 4 * mm),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4 * mm),
                ("ROUNDEDCORNERS", [5]),
            ]
        )
    )
    historia.extend([capa, Spacer(1, 3 * mm)])

    valores_cards = [
        (metricas["leads_contato"], "Leads em contato"),
        (metricas["leads_funil"], "Enviados ao funil"),
        (metricas["leads_com_nota"], "Leads que avaliaram"),
        (
            f"{metricas['media_satisfacao']:.2f}".replace(".", ",")
            if metricas["media_satisfacao"] is not None
            else "—",
            "Nota média / 5",
        ),
    ]
    cards = []
    for valor, rotulo in valores_cards:
        cards.append(
            Table(
                [
                    [p(valor, "indicador")],
                    [p(rotulo, "rotulo_indicador")],
                ],
                colWidths=[38.75 * mm],
                style=[("LEFTPADDING", (0, 0), (-1, -1), 0),
                       ("RIGHTPADDING", (0, 0), (-1, -1), 0)],
            )
        )
    tabela_cards = Table(
        [cards],
        colWidths=[41.75 * mm] * 4,
        rowHeights=[26 * mm],
    )
    tabela_cards.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), cinza_claro),
                ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#DCE4E7")),
                ("INNERGRID", (0, 0), (-1, -1), 3, colors.white),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 1.5 * mm),
                ("RIGHTPADDING", (0, 0), (-1, -1), 1.5 * mm),
            ]
        )
    )
    descricao_intervalo = (
        "todo o histórico disponível até o instante final do relatório"
        if periodo.get("tipo") == "total"
        else "eventos ocorridos dentro da janela móvel"
    )
    historia.extend(
        [
            Paragraph("Visão geral", estilos["secao"]),
            p(
                f"Os indicadores abaixo usam {descricao_intervalo}. "
                "Conversas técnicas do mesmo cliente foram consolidadas apenas quando "
                "pertencem à mesma unidade. "
                f"A taxa geral de envio ao funil foi de {percentual(metricas['taxa_funil'])}."
            ),
            Spacer(1, 3 * mm),
            tabela_cards,
            Spacer(1, 5 * mm),
        ]
    )

    segmentacao = metricas["segmentacao_perfis"]
    linhas_perfis: list[list[Any]] = [
        [
            p("Perfil atendido", "cabecalho_tabela"),
            p("Leads", "cabecalho_tabela"),
            p("Conversas", "cabecalho_tabela"),
            p("No funil", "cabecalho_tabela"),
            p("Taxa de envio", "cabecalho_tabela"),
        ]
    ]
    linhas_politica: list[int] = []
    for perfil in segmentacao["linhas"]:
        if perfil["funil_nao_aplicavel"]:
            valor_funil = "Não se aplica*"
            valor_taxa = "—"
            linhas_politica.append(len(linhas_perfis))
        else:
            valor_funil = perfil["leads_funil"]
            valor_taxa = percentual(perfil["taxa_funil"])
        linhas_perfis.append(
            [
                p(perfil["rotulo"], "pequeno"),
                p(perfil["leads"], "centro"),
                p(perfil["conversas"], "centro"),
                p(valor_funil, "centro"),
                p(valor_taxa, "centro"),
            ]
        )

    tabela_perfis = Table(
        linhas_perfis,
        colWidths=[67 * mm, 20 * mm, 24 * mm, 31 * mm, 25 * mm],
        repeatRows=1,
    )
    estilo_perfis = [
        ("BACKGROUND", (0, 0), (-1, 0), verde),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#DCE4E7")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, cinza_claro]),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 2.5 * mm),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5 * mm),
    ]
    for indice_linha in linhas_politica:
        estilo_perfis.append(
            (
                "BACKGROUND",
                (0, indice_linha),
                (-1, indice_linha),
                colors.HexColor("#FFF4D6"),
            )
        )
    tabela_perfis.setStyle(TableStyle(estilo_perfis))

    total_conversas_perfil = (
        segmentacao["conversas_classificadas"]
        + segmentacao["conversas_sem_classificacao"]
    )
    leituras_rapidas: list[str] = []
    predominantes = segmentacao["perfis_predominantes"]
    if len(predominantes) == 1:
        leituras_rapidas.append(f"Maior volume: {predominantes[0]}.")
    elif predominantes:
        leituras_rapidas.append("Maior volume, em empate: " + "; ".join(predominantes) + ".")
    if segmentacao["leads_multiperfil"]:
        leituras_rapidas.append(
            f"{segmentacao['leads_multiperfil']} lead(s) apareceram em mais de um "
            "perfil de atendimento."
        )
    if segmentacao["conversas_sem_classificacao"]:
        leituras_rapidas.append(
            f"{segmentacao['conversas_sem_classificacao']} conversa(s) tinham "
            "tipo/idade ausente ou inválido, ou idade fora das faixas atuais."
        )
    if not leituras_rapidas:
        leituras_rapidas.append("Nenhum atendimento para classificar neste período.")

    bloco_perfis = [
        Paragraph("Perfil dos atendimentos", estilos["secao"]),
        p(
            "Leads representa clientes únicos dentro de cada perfil; Conversas "
            "mostra a demanda técnica. Um cliente pode aparecer em mais de um "
            "perfil quando iniciou atendimentos para pessoas diferentes, portanto "
            "as linhas não devem ser somadas para obter o total geral."
        ),
        Spacer(1, 2 * mm),
        tabela_perfis,
        Spacer(1, 2.5 * mm),
        p(
            f"Cobertura etária: {segmentacao['conversas_classificadas']} de "
            f"{total_conversas_perfil} conversa(s) ({percentual(segmentacao['cobertura_conversas'])}). "
            f"A faixa infantil começa aos {segmentacao['idade_minima_dependente']} "
            "anos conforme a configuração de BPA da unidade."
        ),
        p("Leitura rápida: " + " ".join(leituras_rapidas), "pequeno"),
    ]
    limite = segmentacao["idade_minima_suporte"]
    politica_suporte = (
        "Encaminhamento por idade: desativado."
        if limite is None
        else f"Encaminhamento ao comercial: titulares a partir de {limite} anos, na etapa de idade."
    )
    bloco_perfis.append(p(
        politica_suporte + " As faixas etárias permanecem fixas. Os números e taxas "
        "incluem os envios confirmados; a configuração atual não apaga o histórico "
        "nem comprova qual regra vigorava na época.",
        "pequeno",
    ))
    if segmentacao["conversas_funil_sem_classificacao"]:
        bloco_perfis.append(p(
            f"Envios fora das cinco faixas: {segmentacao['conversas_funil_sem_classificacao']} "
            "conversa(s) sem classificação, cujos leads continuam considerados "
            "no total geral de enviados.",
            "pequeno",
        ))
    historia.append(KeepTogether(bloco_perfis))
    if not metricas["leads_contato"]:
        historia.extend([
            Spacer(1, 4 * mm),
            p("Nenhum lead entrou em contato neste período. Não há notas, "
              "comentários ou relação de leads a apresentar."),
        ])
        documento.build(
            historia, onFirstPage=cabecalho_rodape, onLaterPages=cabecalho_rodape,
        )
        return
    historia.append(PageBreak())

    distribuicao = metricas["distribuicao_notas"]
    maximo = max([int(valor) for valor in distribuicao.values()] + [1])
    linhas_notas: list[list[Any]] = [[p("Nota", "cabecalho_tabela"), p("Distribuição", "cabecalho_tabela"), p("Respostas", "cabecalho_tabela")]]
    for nota in range(5, 0, -1):
        quantidade = int(distribuicao[str(nota)])
        barra: Any = ""
        if quantidade:
            barra = Table([[""]], colWidths=[90 * quantidade / maximo * mm], rowHeights=[4 * mm], hAlign="LEFT")
            barra.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), amarelo)]))
        linhas_notas.append([p(f"{nota} / 5"), barra, p(quantidade, "centro")])
    tabela_notas = Table(linhas_notas, colWidths=[23 * mm, 120 * mm, 24 * mm], repeatRows=1)
    tabela_notas.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), verde),
                ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#DCE4E7")),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 2.3 * mm),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2.3 * mm),
            ]
        )
    )
    historia.extend(
        [
            Paragraph("Satisfação", estilos["secao"]),
            p(
                f"Foram registradas {metricas['respostas_satisfacao']} nota(s) e "
                f"{metricas['comentarios']} comentário(s) no período. "
                f"Participação: {percentual(metricas['taxa_participacao_satisfacao'])} "
                "dos leads em contato deram pelo menos uma nota."
            ),
            Spacer(1, 2 * mm),
            tabela_notas,
            Spacer(1, 4 * mm),
            Paragraph("Como interpretar os números", estilos["secao"]),
            p(
                "No funil significa envio confirmado no registro local de integração, "
                "dentro do período; não significa agendamento ou venda. Cada faixa "
                "considera o envio da própria conversa, nunca de outro atendimento "
                "do mesmo contato.", "pequeno",
            ),
            p(
                "A idade do titular usa o cadastro atual; a do dependente usa o "
                "registro ligado à conversa. Idades e configurações de BPA/suporte "
                "ao idoso refletem o banco na extração, não um retrato histórico "
                "da época de cada atendimento. Idades fora de 1–99, ausentes e "
                "fora das faixas exibidas ficam sem classificação.", "pequeno",
            ),
            p(
                f"{segmentacao['leads_sem_classificacao']} lead(s) apenas sem "
                f"classificação; {segmentacao['leads_funil_apenas_sem_classificacao']} "
                "lead(s) enviados somente por conversas sem classificação. "
                f"{segmentacao['conversas_apenas_envio_funil']} conversa(s) foram "
                "incluídas nos perfis pelo envio confirmado, mesmo sem mensagem "
                "na janela, sempre de clientes que entraram em contato no período.",
                "pequeno",
            ),
        ]
    )

    cabecalho_leads = [
        p("Lead", "cabecalho_tabela"),
        p("Profissão atual", "cabecalho_tabela"),
        p("Conversa(s)", "cabecalho_tabela"),
        p("Última atividade", "cabecalho_tabela"),
        p("Funil", "cabecalho_tabela"),
    ]
    linhas_leads: list[list[Any]] = [cabecalho_leads]
    for lead in unidade["conversas"]:
        identificacao = lead["nome"]
        if lead.get("waid_telefone"):
            identificacao += f"\nWA ID: {lead['waid_telefone']}"
        linhas_leads.append(
            [
                p(identificacao, "pequeno"),
                p(lead.get("profissao"), "pequeno"),
                p(", ".join(map(str, lead["ids_conversa"])), "pequeno"),
                p(_data_local(lead["ultima_atividade"]), "pequeno"),
                p("Sim" if lead["foi_funil"] else "Não", "centro"),
            ]
        )
    if len(linhas_leads) == 1:
        linhas_leads.append([p("Nenhum lead no período"), "", "", "", ""])
    tabela_leads = LongTable(
        linhas_leads,
        colWidths=[52 * mm, 35 * mm, 26 * mm, 37 * mm, 17 * mm],
        repeatRows=1,
    )
    tabela_leads.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), verde),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#DCE4E7")),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, cinza_claro]),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("TOPPADDING", (0, 0), (-1, -1), 1.8 * mm),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 1.8 * mm),
                ("SPAN", (0, 1), (-1, 1)) if len(unidade["conversas"]) == 0 else ("LINEBELOW", (0, 0), (-1, 0), 0.5, colors.white),
            ]
        )
    )
    historia.extend([Spacer(1, 4 * mm), Paragraph("Comentários recebidos", estilos["secao"])])

    comentarios = [item for item in unidade["pesquisas"] if item["comentario"]]
    if not comentarios:
        historia.append(p("Nenhum comentário foi registrado no período."))
    else:
        for indice, item in enumerate(comentarios, 1):
            historia.append(CondPageBreak(28 * mm))
            cabecalho = (
                f"<b>{html_escape(item['nome'])}</b> • nota "
                f"{html_escape(str(item['nota'] if item['nota'] is not None else 'não informada'))}"
                f"<br/><font color='#667781'>Profissão: "
                f"{html_escape(item['profissao'] or 'não informada')} • "
                f"{html_escape(_data_local(item['criado_em']))} • "
                f"conversa #{item['id_conversa']}</font>"
            )
            historia.append(Paragraph(cabecalho, estilos["corpo"]))
            historia.append(
                Paragraph(
                    "“" + html_escape(item["comentario"]).replace("\n", "<br/>") + "”",
                    estilos["comentario"],
                )
            )
            if indice != len(comentarios):
                historia.append(HRFlowable(width="100%", thickness=0.4, color=colors.HexColor("#DCE4E7"), spaceBefore=1 * mm, spaceAfter=2 * mm))

    historia.extend(
        [
            PageBreak(),
            Paragraph("Leads identificados no período", estilos["secao"]),
            p(
                "Relação consolidada por cliente da unidade. Os IDs abaixo remetem "
                "às conversas do dashboard de histórico, que permanece separado "
                "deste relatório de indicadores.",
                "pequeno",
            ),
            Spacer(1, 3 * mm),
            tabela_leads,
        ]
    )
    documento.build(
        historia,
        onFirstPage=cabecalho_rodape,
        onLaterPages=cabecalho_rodape,
    )


def _datas_nome_arquivo(periodo: Mapping[str, Any]) -> str:
    inicio = _ordenar_data(periodo["inicio"]).astimezone(FUSO_RELATORIO).date()
    fim = _ordenar_data(periodo["fim"]).astimezone(FUSO_RELATORIO).date()
    return f"{inicio.isoformat()}_a_{fim.isoformat()}"


def _arquivo_temporario(diretorio: Path, sufixo: str) -> Path:
    diretorio.mkdir(parents=True, exist_ok=True)
    descritor, caminho = tempfile.mkstemp(prefix=".gerando-", suffix=sufixo, dir=diretorio)
    os.close(descritor)
    return Path(caminho)


def _publicar_lote_recuperavel(pares: Sequence[tuple[Path, Path]]) -> None:
    """Publica um lote completo, restaurando os arquivos anteriores em erro.

    Uma troca verdadeiramente atômica de vários arquivos não existe no sistema
    de arquivos. O protocolo guarda todos os destinos antigos antes de publicar
    qualquer arquivo. Se uma troca falhar, restaura o lote anterior. Backups que
    não puderem ser restaurados são preservados para recuperação manual.
    """
    backups: dict[Path, Path] = {}
    publicados: list[Path] = []
    try:
        for _, destino in pares:
            if destino.exists():
                backup = _arquivo_temporario(
                    destino.parent, f"{destino.suffix}.backup"
                )
                backup.unlink()
                destino.replace(backup)
                backups[destino] = backup

        for temporario, destino in pares:
            temporario.replace(destino)
            publicados.append(destino)
    except Exception as erro_publicacao:
        erros_recuperacao: list[str] = []
        for destino in reversed(publicados):
            try:
                destino.unlink(missing_ok=True)
            except OSError as exc:
                erros_recuperacao.append(f"remover {destino}: {exc}")
        for destino, backup in backups.items():
            if backup.exists():
                try:
                    backup.replace(destino)
                except OSError as exc:
                    erros_recuperacao.append(
                        f"restaurar {destino} a partir de {backup}: {exc}"
                    )
        if erros_recuperacao:
            detalhes = "; ".join(erros_recuperacao)
            preservados = ", ".join(
                str(backup) for backup in backups.values() if backup.exists()
            )
            raise RuntimeError(
                "Falha ao publicar e ao restaurar o lote. "
                f"Backups preservados: {preservados or 'nenhum'}. {detalhes}"
            ) from erro_publicacao
        raise
    else:
        for backup in backups.values():
            backup.unlink(missing_ok=True)
    finally:
        for temporario, _ in pares:
            temporario.unlink(missing_ok=True)


def resolver_pastas_unidades(
    unidades: Sequence[Mapping[str, Any]],
) -> dict[int, str]:
    """Resolve nomes de pasta estáveis, inclusive quando nomes comerciais colidem."""
    pastas_usadas: set[str] = set()
    resultado: dict[int, str] = {}
    for unidade in unidades:
        id_unidade = int(unidade["id_unidade"])
        pasta_base = sanear_nome_unidade(unidade["nome_unidade"], id_unidade)
        pasta = pasta_base
        tentativa = 0
        while pasta.casefold() in pastas_usadas:
            tentativa += 1
            sufixo = str(id_unidade) if tentativa == 1 else f"{id_unidade}-{tentativa}"
            pasta = f"{pasta_base} ({sufixo})"
        pastas_usadas.add(pasta.casefold())
        resultado[id_unidade] = pasta
    return resultado


def gerar_artefatos(
    snapshot: Mapping[str, Any],
    raiz_saida: Path,
    nomes_pasta: Mapping[int, str] | None = None,
) -> list[dict[str, Path]]:
    """Gera os pares HTML/PDF e restaura o par anterior se a publicação falhar."""
    raiz_saida = raiz_saida.expanduser().resolve()
    periodo = snapshot["periodo"]
    tipo_periodo = str(periodo.get("tipo") or "semanal")
    if tipo_periodo not in {"semanal", "total"}:
        raise ValueError(f"Tipo de período inválido: {tipo_periodo!r}")
    intervalo = _datas_nome_arquivo(periodo)
    pastas = dict(nomes_pasta or resolver_pastas_unidades(snapshot["unidades"]))
    gerados: list[dict[str, Path]] = []
    publicacao: list[tuple[Path, Path]] = []

    try:
        for unidade in snapshot["unidades"]:
            id_unidade = int(unidade["id_unidade"])
            pasta = pastas.get(id_unidade)
            if not pasta:
                raise RuntimeError(f"Pasta não resolvida para a unidade {id_unidade}")
            raiz_unidade = raiz_saida / pasta / tipo_periodo
            diretorio_html = raiz_unidade / "dashbord"
            diretorio_pdf = raiz_unidade / "relatorios"
            destino_html = diretorio_html / f"conversas_{intervalo}.html"
            destino_pdf = diretorio_pdf / f"desempenho_{intervalo}.pdf"
            temporario_html = _arquivo_temporario(diretorio_html, ".html")
            temporario_pdf = _arquivo_temporario(diretorio_pdf, ".pdf")
            publicacao.extend(
                ((temporario_html, destino_html), (temporario_pdf, destino_pdf))
            )

            temporario_html.write_text(
                renderizar_html(unidade, periodo), encoding="utf-8", newline="\n"
            )
            renderizar_pdf(unidade, periodo, temporario_pdf)
            gerados.append({"html": destino_html, "pdf": destino_pdf})

        _publicar_lote_recuperavel(publicacao)
    except Exception:
        for temporario, _ in publicacao:
            temporario.unlink(missing_ok=True)
        raise
    return gerados


def executar(args: argparse.Namespace) -> list[dict[str, Path]]:
    from utilitarios.bootstrap import configurar_ambiente_utilitario

    configurar_ambiente_utilitario(args.env_file)
    # Import tardio: connection_aws lê o ambiente no momento do import.
    from core.database.connection_aws import get_conn

    inicio, fim = resolver_janela(args.dias, args.ate)
    conn = get_conn(application_name="utilitario_monitoramento_semanal")
    try:
        snapshot = coletar_snapshot(
            conn=conn,
            inicio=inicio,
            fim=fim,
            ids_unidade=args.ids_unidade,
            max_mensagens=args.max_mensagens,
            statement_timeout_ms=args.statement_timeout_ms,
        )
    finally:
        conn.close()
    return gerar_artefatos(snapshot, args.saida)


def main(argv: Sequence[str] | None = None) -> int:
    parser = criar_parser()
    args = parser.parse_args(argv)
    try:
        gerados = executar(args)
    except Exception as exc:
        parser.exit(1, f"Falha ao gerar monitoramento: {exc}\n")

    if not gerados:
        print("Nenhuma unidade encontrada; nenhum arquivo foi gerado.")
        return 0
    print(f"Monitoramento concluído para {len(gerados)} unidade(s):")
    for item in gerados:
        print(f"- HTML: {item['html']}")
        print(f"  PDF:  {item['pdf']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

## Passo 36 — Substituir integralmente `callback/webhook/models.py`

```python
from core.integrations.whatsapp.numero_comercial import numero_comercial_whatsapp_valido
from core.validacoes.turno import ROTULOS_TURNO
from core.validacoes.suporte_por_idade import IDADES_MINIMAS_SUPORTE

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from core.validacoes.encerramento_por_idade import ROTULOS_MOTIVOS


class Cliente(models.Model):
    id_cliente = models.AutoField(primary_key=True)
    nome = models.CharField(max_length=200, blank=True, null=True)
    waid_telefone = models.CharField(unique=True, max_length=50)
    email = models.CharField(unique=True, max_length=200, blank=True, null=True)
    idade = models.IntegerField(blank=True, null=True)
    profissao = models.CharField(max_length=100, blank=True, null=True)

    def __str__(self):
        return self.nome or self.waid_telefone

    class Meta:
        managed = False
        db_table = 'cliente'


class Dependente(models.Model):
    id_dependente = models.AutoField(primary_key=True)
    id_cliente = models.ForeignKey(
        Cliente,
        models.CASCADE,
        db_column='id_cliente',
        related_name='dependentes',
    )
    id_conversa = models.ForeignKey(
        'Conversa',
        models.CASCADE,
        db_column='id_conversa',
        related_name='dependentes_atendidos',
        blank=True,
        null=True,
    )
    nome_dependente = models.CharField(max_length=200, blank=True, null=True)
    idade = models.IntegerField(blank=True, null=True)

    def __str__(self):
        return self.nome_dependente or str(self.id_dependente)

    class Meta:
        managed = False
        db_table = 'dependente'


class Conversa(models.Model):
    id_chat = models.ForeignKey('Chat', models.DO_NOTHING, db_column='id_chat')
    origem_fireads = models.CharField(max_length=10, null=True, blank=True, choices=[('google','Google Ads'),('meta','Meta Ads'),('organico','Orgânico')])
    contexto_fireads = models.JSONField(null=True, blank=True)
    lead_no_dash = models.BooleanField(null=True, blank=True, default=None)

    turno = models.CharField(
        "turno de preferência", max_length=5, blank=True, null=True,
        choices=list(ROTULOS_TURNO.items()),
        help_text="Preferência informada no atendimento; não confirma dia ou horário.",
    )
    id_conversa = models.AutoField(primary_key=True)
    id_cliente = models.ForeignKey(Cliente, models.DO_NOTHING, db_column='id_cliente')
    id_unidade = models.ForeignKey('Unidade', models.DO_NOTHING, db_column='id_unidade')
    id_etapa_atual = models.ForeignKey('Etapa', models.DO_NOTHING, db_column='id_etapa_atual', blank=True, null=True)
    status_ativa = models.BooleanField(default=True)
    status_dependente = models.BooleanField(blank=True, null=True, default=False)
    profissao = models.CharField(max_length=100, blank=True, null=True)
    last_interaction_at = models.DateTimeField(blank=True, null=True)
    last_message_from = models.CharField(
        max_length=10,
        blank=True,
        null=True,
        choices=[("cliente", "cliente"), ("bot", "bot")],
    )
    followup_stage = models.IntegerField(blank=True, null=True, default=0)
    followup_last_sent_at = models.DateTimeField(blank=True, null=True)
    lead_no_funil = models.BooleanField(blank=True, null=True, default=False)
    processing = models.BooleanField(blank=True, null=True, default=False)
    processing_started_at = models.DateTimeField(blank=True, null=True)
    lock_version = models.IntegerField(blank=True, null=True, default=0)
    turnos_sem_avanco = models.IntegerField(default=0)
    iniciou_em = models.DateTimeField()
    finalizou_em = models.DateTimeField(blank=True, null=True)
    motivo_encerramento = models.CharField(
        max_length=30,
        blank=True,
        null=True,
        choices=[*ROTULOS_MOTIVOS.items(),
                 ("foi_agendado", "Foi agendado"),
                 ("followup_sem_resposta", "Segundo follow-up sem resposta")],
    )

    class Meta:
        managed = False
        db_table = 'conversa'


class Etapa(models.Model):
    id_etapa = models.AutoField(primary_key=True)
    nome_etapa = models.CharField(unique=True, max_length=100)
    encerra_automaticamente = models.BooleanField(default=False)
    bloqueio_dias = models.PositiveIntegerField(default=0)
    elegivel_funil = models.BooleanField(default=False)

    class Meta:
        managed = False
        db_table = 'etapa'


class FilaMensagens(models.Model):
    id_mensagem = models.AutoField(primary_key=True)
    id_conversa = models.ForeignKey(
        Conversa,
        models.SET_NULL,
        db_column='id_conversa',
        blank=True,
        null=True,
    )
    status = models.CharField(
        max_length=20,
        default="pending",
        choices=[
            ("pending", "pending"),
            ("processing", "processing"),
            ("sent", "sent"),
            ("failed", "failed"),
        ],
    )
    retry_count = models.IntegerField(blank=True, null=True, default=0)
    next_attempt_at = models.DateTimeField(blank=True, null=True)
    processing_started_at = models.DateTimeField(blank=True, null=True)
    received_data_hora = models.DateTimeField()
    cliente_telefone = models.CharField(max_length=100)
    conteudo_texto = models.TextField(blank=True, null=True)
    tipo_mensagem = models.CharField(max_length=20)
    id_hash_msg = models.CharField(unique=True, max_length=255)
    id_phone_unidade = models.CharField(max_length=100)
    unidade_telefone = models.CharField(max_length=100)
    last_error = models.TextField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'fila_mensagens'


class HistoricoMensagens(models.Model):
    id_mensagem = models.AutoField(primary_key=True)

    id_conversa = models.ForeignKey(
        Conversa,
        models.DO_NOTHING,
        db_column='id_conversa'
    )

    id_etapa = models.ForeignKey(
        Etapa,
        models.DO_NOTHING,
        db_column='id_etapa',
        blank=True,
        null=True
    )

    received_data_hora = models.DateTimeField()

    cliente_telefone = models.CharField(max_length=100)
    conteudo_texto = models.TextField(blank=True, null=True)
    tipo_mensagem = models.CharField(max_length=20)
    id_hash_msg = models.CharField(max_length=255)
    id_mensagem_fila = models.ForeignKey(
        FilaMensagens,
        models.SET_NULL,
        db_column='id_mensagem_fila',
        blank=True,
        null=True,
        related_name='historicos_originados',
    )
    id_hash_cliente_origem = models.CharField(max_length=255, blank=True, null=True)
    id_phone_unidade = models.CharField(max_length=100)
    unidade_telefone = models.CharField(max_length=100)
    quem_enviou = models.CharField(
        max_length=10,
        choices=[
            ("cliente", "cliente"),
            ("bot", "bot"),
        ],
    )
    status_envio = models.CharField(
        max_length=20,
        blank=True,
        null=True,
        choices=[
            ("pending", "pending"),
            ("sent", "sent"),
            ("failed", "failed"),
        ],
    )

    class Meta:
        managed = False
        db_table = 'historico_mensagens'
        constraints = [
            models.UniqueConstraint(
                fields=["id_mensagem", "received_data_hora"],
                name="uq_historico_mensagens_id_data",
            ),
        ]


class RespostasDesafios(models.Model):
    id_resposta_desafio = models.AutoField(primary_key=True)
    id_conversa = models.ForeignKey(
        Conversa,
        models.CASCADE,
        db_column='id_conversa',
        related_name='respostas_desafios',
    )
    id_etapa = models.ForeignKey(
        Etapa,
        models.DO_NOTHING,
        db_column='id_etapa',
        related_name='respostas_desafios',
    )
    resposta = models.CharField(max_length=20)
    id_historico_mensagem_cliente = models.IntegerField(blank=True, null=True)
    criado_em = models.DateTimeField()

    class Meta:
        managed = False
        db_table = 'respostas_desafios'
        constraints = [
            models.UniqueConstraint(
                fields=["id_conversa", "id_etapa"],
                name="uq_respostas_desafios_conversa_etapa",
            ),
        ]


class PesquisaSatisfacao(models.Model):
    id_pesquisa_satisfacao = models.AutoField(primary_key=True)
    id_conversa = models.OneToOneField(
        Conversa,
        models.CASCADE,
        db_column='id_conversa',
        related_name='pesquisa_satisfacao',
    )
    nota = models.PositiveSmallIntegerField(blank=True, null=True)
    comentario = models.TextField(blank=True, null=True)
    criado_em = models.DateTimeField()
    atualizado_em = models.DateTimeField()

    class Meta:
        managed = False
        db_table = 'pesquisa_satisfacao'
        verbose_name = 'Pesquisa de satisfação'
        verbose_name_plural = 'Pesquisas de satisfação'


class Unidade(models.Model):
    class Genero(models.TextChoices):
        MASCULINO = "masculino", "Masculino"
        FEMININO = "feminino", "Feminino"

    id_unidade = models.AutoField(primary_key=True)
    nome_unidade = models.CharField(
        "nome da unidade",
        unique=True,
        max_length=300,
    )
    cnpj = models.CharField(unique=True, max_length=50)
    email_responsavel = models.CharField(unique=True, max_length=255)
    telefone = models.CharField(unique=True, max_length=20)
    waba_id = models.CharField(
        unique=True,
        max_length=100,
    )
    phone_number_id = models.CharField(unique=True, max_length=100)
    id_fuso = models.IntegerField(blank=True, null=True, editable=False)
    nome_fuso = models.TextField(blank=True, null=True, editable=False)
    fuso_verificado_em = models.DateTimeField(blank=True, null=True, editable=False)
    status_pagamento = models.BooleanField(blank=True, null=True, default=True)
    id_usuario_monitoramento = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        models.SET_NULL,
        db_column='id_usuario_monitoramento',
        related_name='unidade_monitorada',
        verbose_name='usuário de monitoramento',
        blank=True,
        null=True,
        limit_choices_to={'is_staff': False, 'is_superuser': False},
        help_text=(
            'Selecione uma conta comum cadastrada em Usuários. '
            'Cada conta pode monitorar somente uma unidade. '
            'Deixe vazio para manter a unidade sem acesso de monitoramento.'
        ),
    )

    @property
    def nome_agente(self):
        return self.atendimento_customizado.nome_agente

    @property
    def genero(self):
        return self.atendimento_customizado.genero

    @property
    def numero_comercial(self):
        return self.atendimento_customizado.numero_comercial

    @property
    def idade_minima_suporte(self):
        return self.atendimento_customizado.idade_minima_suporte

    @property
    def email_obrigatorio(self):
        return self.atendimento_customizado.email_obrigatorio

    @property
    def link_agendamento(self):
        return self.atendimento_customizado.link_agendamento

    @property
    def link_instagram(self):
        return self.atendimento_customizado.link_instagram

    @property
    def bpa_ativo(self):
        return self.atendimento_customizado.bpa_ativo

    def clean(self):
        super().clean()
        if self.id_usuario_monitoramento_id and (
            self.id_usuario_monitoramento.is_staff
            or self.id_usuario_monitoramento.is_superuser
        ):
            raise ValidationError({
                'id_usuario_monitoramento': (
                    'O monitoramento exige uma conta sem acesso ao Admin '
                    'e sem status de superusuário.'
                ),
            })

    def __str__(self):
        return self.nome_unidade

    class Meta:
        managed = False
        db_table = 'unidade'


class IntegracaoFunilUnidade(models.Model):
    id_integracao_funil = models.AutoField(primary_key=True)
    id_unidade = models.OneToOneField(
        Unidade,
        models.CASCADE,
        db_column='id_unidade',
        related_name='integracao_funil',
    )
    nome_widget = models.CharField(max_length=300)
    data_salvamento_widget = models.DateField(blank=True, null=True)
    codigo_widget = models.CharField(unique=True, max_length=100)
    link_api_carrossel = models.URLField(unique=True, max_length=500)
    codigo_canal_venda = models.CharField(max_length=100)
    widget_ativo = models.BooleanField(default=True)
    integracao_ativa = models.BooleanField(default=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.id_unidade} / {self.nome_widget}"

    class Meta:
        managed = False
        db_table = 'integracao_funil_unidade'
        verbose_name = 'Integração do Funil por unidade'
        verbose_name_plural = 'Integrações do Funil por unidade'


class FunilEnvio(models.Model):
    id_funil_envio = models.AutoField(primary_key=True)
    id_conversa = models.OneToOneField(
        Conversa,
        models.CASCADE,
        db_column='id_conversa',
        related_name='envio_funil',
    )
    status = models.CharField(
        max_length=20,
        default='pending',
        choices=[
            ('pending', 'pending'),
            ('processing', 'processing'),
            ('sent', 'sent'),
        ],
    )
    attempt_count = models.IntegerField(default=0)
    next_attempt_at = models.DateTimeField()
    processing_started_at = models.DateTimeField(blank=True, null=True)
    enviado_em = models.DateTimeField(blank=True, null=True)
    ultimo_erro = models.TextField(blank=True, null=True)
    resposta_funil = models.TextField(blank=True, null=True)
    criado_em = models.DateTimeField()
    atualizado_em = models.DateTimeField()

    class Meta:
        managed = False
        db_table = 'funil_envios'
        verbose_name = 'Envio ao Funil'
        verbose_name_plural = 'Envios ao Funil'


class ClienteBloqueadoMeta(models.Model):
    id_bloqueio = models.AutoField(primary_key=True)
    id_cliente = models.ForeignKey(
        Cliente,
        models.SET_NULL,
        db_column='id_cliente',
        blank=True,
        null=True,
        related_name='bloqueios_meta',
    )
    nome = models.CharField(max_length=200, blank=True, null=True)
    wa_id_cliente = models.CharField(max_length=50)
    id_unidade = models.ForeignKey(
        Unidade,
        models.DO_NOTHING,
        db_column='id_unidade',
        related_name='bloqueios_meta',
    )
    phone_id_unidade = models.CharField(max_length=100)

    def __str__(self):
        return f"{self.wa_id_cliente} / {self.phone_id_unidade}"

    class Meta:
        managed = False
        db_table = 'cliente_bloqueado_meta'
        constraints = [
            models.UniqueConstraint(
                fields=["wa_id_cliente", "id_unidade"],
                name="uq_cliente_bloqueado_meta_wa_unidade",
            ),
        ]


class WebhookFloodEvento(models.Model):
    id_evento = models.BigAutoField(primary_key=True)
    wa_id_cliente = models.CharField(max_length=50)
    phone_id_unidade = models.CharField(max_length=100)
    id_hash_msg = models.CharField(unique=True, max_length=255)
    received_at = models.DateTimeField()

    def __str__(self):
        return f"{self.wa_id_cliente} / {self.phone_id_unidade}"

    class Meta:
        managed = False
        db_table = 'webhook_flood_evento'


class CacheControle(models.Model):
    nome = models.CharField(primary_key=True, max_length=100)
    versao = models.BigIntegerField(default=1)
    atualizado_em = models.DateTimeField()

    def __str__(self):
        return self.nome

    class Meta:
        managed = False
        db_table = 'cache_controle'


class ConsumoMensalMeta(models.Model):
    """Espelho de leitura; o worker persiste pelo repositório e a migração é SQL."""

    id_registro = models.BigAutoField(primary_key=True)
    id_unidade = models.ForeignKey(Unidade, models.DO_NOTHING, db_column='id_unidade')
    mes_referencia = models.DateField()
    waba_id = models.CharField(max_length=100)
    phone_number_id = models.CharField(max_length=100)
    timezone_id = models.IntegerField()
    fuso_horario = models.TextField()
    data_hora_inicio = models.DateTimeField()
    data_hora_fim = models.DateTimeField()
    qtd_janela_gratuita = models.BigIntegerField()
    qtd_franquia_consumida = models.BigIntegerField()
    qtd_cobradas_meta = models.BigIntegerField()
    franquia_meta_mensal = models.IntegerField(default=1000)
    beneficio_esl_mensal = models.IntegerField(default=1000)
    tarifa_referencia_brl = models.DecimalField(max_digits=12, decimal_places=6)
    tarifa_vigencia = models.DateField()
    consultado_ate = models.DateTimeField()
    ultimo_sucesso_em = models.DateTimeField()
    status_apuracao = models.CharField(max_length=20, choices=[
        ('em_andamento', 'Em andamento'), ('em_conferencia', 'Em conferência'),
        ('consolidado', 'Consolidado'),
    ])
    data_proxima_consolidacao = models.DateField(null=True, blank=True)
    consolidado_em = models.DateTimeField(null=True, blank=True)
    ultima_decisao_consolidacao_em = models.DateTimeField(null=True, blank=True)
    criado_em = models.DateTimeField()
    atualizado_em = models.DateTimeField()

    class Meta:
        managed = False
        db_table = 'consumo_mensal_meta'
        constraints = [models.UniqueConstraint(fields=['id_unidade', 'mes_referencia'], name='uq_consumo_unidade_mes')]


class ConsumoMetaColeta(models.Model):
    """Agenda de conta/período; também existe quando a primeira consulta falha."""

    pk = models.CompositePrimaryKey('id_unidade', 'periodo')
    id_unidade = models.IntegerField()
    periodo = models.CharField(max_length=7)
    proxima_consulta_em = models.DateTimeField()
    ultima_tentativa_em = models.DateTimeField(null=True, blank=True)
    ultimo_erro = models.TextField(null=True, blank=True)
    falhas_consecutivas = models.IntegerField(default=0)

    class Meta:
        managed = False
        db_table = 'consumo_meta_coletas'


class AtendimentoCustomizado(models.Model):
    Genero = Unidade.Genero
    id_customizacao = models.AutoField(primary_key=True)
    id_unidade = models.OneToOneField(
        Unidade,
        models.CASCADE,
        db_column="id_unidade",
        related_name="atendimento_customizado",
    )
    nome_agente = models.CharField("nome do agente", max_length=100)
    genero = models.CharField(
        "gênero do agente",
        max_length=9,
        choices=Genero.choices,
    )
    numero_comercial = models.CharField(
        max_length=30,
        help_text="Contato comercial obrigatório para toda unidade.",
    )
    idade_minima_suporte = models.IntegerField(
        "encaminhar titular ao comercial a partir de",
        blank=True,
        null=True,
        default=None,
        choices=[(None, "Desativado")]
        + [(idade, f"{idade}+") for idade in IDADES_MINIMAS_SUPORTE],
        help_text=(
            "Na etapa de idade, encaminha somente o titular a partir do limite "
            "até 89 anos e encerra sem bloqueio; 90+ é universal. Não altera a regra de e-mail."
        ),
    )
    email_obrigatorio = models.BooleanField(
        "e-mail obrigatório",
        default=True,
        help_text=("Exige um e-mail válido, exceto do titular com 60 anos ou mais."),
    )
    link_agendamento = models.CharField(
        unique=True,
        max_length=400,
        blank=True,
        null=True,
        help_text="Vazio: coleta o turno e entrega ao comercial após a triagem.",
    )
    link_instagram = models.CharField(
        max_length=400,
        blank=True,
        null=True,
    )
    bpa_ativo = models.BooleanField(default=False)

    def clean(self):
        super().clean()
        self.link_agendamento = (self.link_agendamento or "").strip() or None
        if not numero_comercial_whatsapp_valido(self.numero_comercial):
            raise ValidationError(
                {"numero_comercial": "Informe um número comercial brasileiro válido."}
            )

    def __str__(self):
        return str(self.id_unidade)

    class Meta:
        managed = False
        db_table = "atendimento_customizado"
        verbose_name = "Atendimento customizado"
        verbose_name_plural = "Atendimentos customizados"


class IntegracaoFireAds(models.Model):
    id_integracao_fireads = models.AutoField(primary_key=True)
    id_unidade = models.OneToOneField(
        Unidade,
        models.CASCADE,
        db_column="id_unidade",
        related_name="integracao_fireads",
    )
    integracao_ativa = models.BooleanField(default=False)
    url_dashbord = models.URLField(max_length=1000)
    url_operation = models.URLField(
        max_length=1000,
        blank=True,
        null=True,
        help_text="Referência do editor. Nunca usada para requisições.",
    )
    aba_google = models.CharField(
        max_length=200, default="Leads Google Ads (NÃO EDITAR)"
    )
    aba_meta = models.CharField(max_length=200, default="[FIRE] Leads Ads Geral - 7.2")
    aba_destino = models.CharField(max_length=200, default="LEADS GERAL - Feedback")
    fuso_formularios = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        help_text="Somente interpretação de datas sem offset. Preencher após confirmação na planilha; não altera o fuso externo.",
    )
    contrato_validado = models.BooleanField(
        default=False,
        help_text="Confirmar nomes de abas, campos e valores recebidos do formulário atualizado antes de ativar.",
    )
    ativada_em = models.DateTimeField(null=True, blank=True, editable=False)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    def clean(self):
        super().clean()
        from core.integrations.fireads.cliente import validar_url
        from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

        try:
            validar_url(self.url_dashbord)
        except ValueError as exc:
            raise ValidationError({"url_dashbord": str(exc)})
        self.fuso_formularios = (self.fuso_formularios or "").strip() or None
        if self.fuso_formularios:
            try:
                ZoneInfo(self.fuso_formularios)
            except ZoneInfoNotFoundError:
                raise ValidationError({"fuso_formularios": "Fuso IANA inválido."})
        if self.integracao_ativa and not self.contrato_validado:
            raise ValidationError(
                {"contrato_validado": "Confira o contrato de leitura antes de ativar."}
            )
        abas = [self.aba_google, self.aba_meta, self.aba_destino]
        if any(not a.strip() for a in abas) or len(set(abas)) != 3:
            raise ValidationError("Informe três abas distintas e não vazias.")

    def __str__(self):
        return str(self.id_unidade)

    class Meta:
        managed = False
        db_table = "integracao_fireads"
        verbose_name = "Integração FireAds"
        verbose_name_plural = "Integrações FireAds"


class Chat(models.Model):
    id_chat = models.BigAutoField(primary_key=True)
    id_cliente = models.ForeignKey(Cliente, models.CASCADE, db_column="id_cliente")
    id_unidade = models.ForeignKey(Unidade, models.CASCADE, db_column="id_unidade")
    criado_em = models.DateTimeField()

    def __str__(self):
        return f"{self.id_cliente} / {self.id_unidade}"

    class Meta:
        managed = False
        db_table = "chat"
        constraints = [
            models.UniqueConstraint(
                fields=["id_cliente", "id_unidade"], name="uq_chat_cliente_unidade"
            )
        ]


class ConsultaFireAds(models.Model):
    id_consulta = models.BigAutoField(primary_key=True)
    id_chat = models.OneToOneField(Chat, models.CASCADE, db_column="id_chat")
    id_unidade = models.ForeignKey(Unidade, models.CASCADE, db_column="id_unidade")
    id_integracao_fireads = models.ForeignKey(
        IntegracaoFireAds, models.PROTECT, db_column="id_integracao_fireads"
    )
    id_conversa_referencia = models.ForeignKey(
        Conversa, models.CASCADE, db_column="id_conversa_referencia"
    )
    consulta_concluida = models.BooleanField(default=False)
    resultado = models.CharField(max_length=30)
    dados = models.JSONField(null=True, blank=True)
    consultado_em = models.DateTimeField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = "consulta_fireads"
        verbose_name_plural = "Consultas FireAds"


class EnvioDash(models.Model):
    id_envio_dash = models.BigAutoField(primary_key=True)
    id_conversa = models.OneToOneField(
        Conversa, models.CASCADE, db_column="id_conversa"
    )
    id_integracao_fireads = models.ForeignKey(
        IntegracaoFireAds, models.PROTECT, db_column="id_integracao_fireads"
    )
    id_unidade = models.ForeignKey(Unidade, models.CASCADE, db_column="id_unidade")
    status = models.CharField(max_length=20, default="pending")
    attempt_count = models.IntegerField(default=0)
    next_attempt_at = models.DateTimeField()
    processing_started_at = models.DateTimeField(null=True, blank=True)
    enviado_em = models.DateTimeField(null=True, blank=True)
    ultimo_erro = models.TextField(null=True, blank=True)
    recibo = models.JSONField(null=True, blank=True)
    snapshot = models.JSONField()
    criado_em = models.DateTimeField()
    atualizado_em = models.DateTimeField()

    class Meta:
        managed = False
        db_table = "envios_dash"
        verbose_name_plural = "Envios ao dashboard"
```

## Passo 37 — Substituir integralmente `callback/webhook/admin.py`

```python
import logging

from django.contrib import admin, messages
from django.db import DatabaseError, connection
from django.http import HttpResponseRedirect
from django.urls import NoReverseMatch, reverse
from django.utils.html import format_html

from core.cache.cache_unidade import (
    CacheUnidadesIndisponivel,
    recarregar_cache_unidades_ou_erro,
    validar_cache_unidades_disponivel_ou_erro,
)
from core.integrations.whatsapp.tools.ativando_numero import registrar_numero_whatsapp
from core.integrations.whatsapp.tools.ativando_waba_id import ativar_waba_id
from core.integrations.whatsapp.tools.desativa_waba_id import desativar_waba_id
from core.integrations.whatsapp.tools.desativando_numero import desregistrar_numero_whatsapp
from core.integrations.whatsapp.tools.usuarios import (
    desbloquear_usuario_meta,
)
from core.integrations.whatsapp.tools.validando_phone_waba import (
    validar_phone_number_id_da_waba,
)
from core.logging_config import short_value
from core.repositories.unidades.cache_control import (
    incrementar_versao_cache_unidades,
)

from .models import (
    AtendimentoCustomizado,
    CacheControle,
    Chat,
    Cliente,
    ClienteBloqueadoMeta,
    Conversa,
    ConsultaFireAds,
    Dependente,
    Etapa,
    EnvioDash,
    FilaMensagens,
    FunilEnvio,
    HistoricoMensagens,
    IntegracaoFunilUnidade,
    IntegracaoFireAds,
    PesquisaSatisfacao,
    RespostasDesafios,
    Unidade,
    WebhookFloodEvento,
)

logger = logging.getLogger(__name__)


class SomenteVisualizacaoAdminMixin:
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def get_readonly_fields(self, request, obj=None):
        return [field.name for field in self.model._meta.fields]


@admin.register(IntegracaoFunilUnidade)
class IntegracaoFunilUnidadeAdmin(admin.ModelAdmin):
    list_display = (
        "id_integracao_funil",
        "id_unidade",
        "nome_widget",
        "codigo_widget",
        "codigo_canal_venda",
        "widget_ativo",
        "integracao_ativa",
        "data_salvamento_widget",
        "atualizado_em",
    )

    search_fields = (
        "id_unidade__nome_unidade",
        "nome_widget",
        "codigo_widget",
        "codigo_canal_venda",
        "link_api_carrossel",
    )

    list_filter = (
        "widget_ativo",
        "integracao_ativa",
        "data_salvamento_widget",
    )

    readonly_fields = (
        "criado_em",
        "atualizado_em",
    )

    ordering = ("id_unidade",)
    list_select_related = ("id_unidade",)
    list_per_page = 50
    empty_value_display = "-"


@admin.register(FunilEnvio)
class FunilEnvioAdmin(SomenteVisualizacaoAdminMixin, admin.ModelAdmin):
    list_display = (
        "id_funil_envio",
        "id_conversa",
        "status",
        "attempt_count",
        "next_attempt_at",
        "processing_started_at",
        "enviado_em",
        "atualizado_em",
    )
    search_fields = (
        "id_conversa__id_conversa",
        "id_conversa__id_cliente__nome",
        "id_conversa__id_cliente__waid_telefone",
    )
    list_filter = ("status",)
    ordering = ("-atualizado_em",)
    date_hierarchy = "criado_em"
    list_select_related = (
        "id_conversa",
        "id_conversa__id_cliente",
    )
    list_per_page = 50
    empty_value_display = "-"


class AtendimentoCustomizadoInline(admin.StackedInline):
    model = AtendimentoCustomizado
    extra = 1
    min_num = 1
    max_num = 1
    can_delete = False
    validate_min = True

    def get_formset(self, request, obj=None, **kwargs):
        kwargs.update(validate_min=True, validate_max=True)
        return super().get_formset(request, obj, **kwargs)


@admin.register(Unidade)
class UnidadeAdmin(admin.ModelAdmin):
    inlines = (AtendimentoCustomizadoInline,)

    list_display = (
        "id_unidade",
        "nome_unidade",
        "id_usuario_monitoramento",
        "nome_agente",
        "genero",
        "cnpj",
        "telefone",
        "numero_comercial",
        "idade_minima_suporte",
        "email_obrigatorio",
        "email_responsavel",
        "waba_id",
        "phone_number_id",
        "link_agendamento_clickable",
        "link_instagram_clickable",
        "bpa_ativo",
        "status_pagamento",
    )

    search_fields = (
        "nome_unidade",
        "id_usuario_monitoramento__username",
        "atendimento_customizado__nome_agente",
        "cnpj",
        "telefone",
        "atendimento_customizado__numero_comercial",
        "email_responsavel",
        "waba_id",
        "phone_number_id",
        "atendimento_customizado__link_agendamento",
        "atendimento_customizado__link_instagram",
    )

    list_filter = (
        "atendimento_customizado__genero",
        "atendimento_customizado__bpa_ativo",
        "atendimento_customizado__idade_minima_suporte",
        "atendimento_customizado__email_obrigatorio",
        "status_pagamento",
    )
    ordering = ("nome_unidade",)
    list_select_related = ("id_usuario_monitoramento", "atendimento_customizado")

    list_per_page = 50
    empty_value_display = "-"

    def get_readonly_fields(self, request, obj=None):
        if obj is not None:
            return ("waba_id", "phone_number_id")

        return ()

    def _create_formsets(self, request, obj, change):
        formsets, inlines = super()._create_formsets(request, obj, change)
        # O Django cria os inlines antes de validar o formulário principal.
        # A chamada à Meta só pode acontecer com a personalização válida também.
        request._unidade_formsets = formsets
        return formsets, inlines

    def changeform_view(self, request, object_id=None, form_url="", extra_context=None):
        try:
            return super().changeform_view(
                request,
                object_id=object_id,
                form_url=form_url,
                extra_context=extra_context,
            )

        except CacheUnidadesIndisponivel as exc:
            if self._falha_cache_originada_no_banco(exc):
                return self._responder_falha_banco(
                    request,
                    object_id,
                    exc,
                )

            logger.exception(
                "admin_unidade_cache_falhou | acao=rollback_admin object_id=%s meta_ok=%s erro=%s",
                object_id,
                self._meta_sucesso_nesta_requisicao(request),
                exc,
            )
            self.message_user(
                request,
                self._mensagem_falha_redis(request),
                level=messages.ERROR,
            )
            return HttpResponseRedirect(request.path)

        except DatabaseError as exc:
            return self._responder_falha_banco(
                request,
                object_id,
                exc,
            )

    def get_form(self, request, obj=None, change=False, **kwargs):
        base_form = super().get_form(request, obj, change=change, **kwargs)
        model_admin = self

        class UnidadeAdminForm(base_form):
            def _post_clean(self):
                super()._post_clean()

                if change or self.errors:
                    if change and not self.errors:
                        model_admin._validar_cache_unidades_form(
                            self,
                            request,
                            meta_validada=False,
                        )
                    return

                if any(
                    not formset.is_valid()
                    for formset in getattr(request, "_unidade_formsets", ())
                ):
                    self.add_error(None, "Confira os dados do atendimento customizado.")
                    return

                waba_id = self.cleaned_data.get("waba_id")
                phone_number_id = self.cleaned_data.get("phone_number_id")

                if not waba_id:
                    self.add_error(
                        "waba_id",
                        "Informe a WABA que sera assinada pelo App.",
                    )
                    return

                campo_com_erro = model_admin._preparar_meta_antes_de_salvar(
                    request,
                    waba_id,
                    phone_number_id,
                )

                if campo_com_erro == "vinculo_waba_phone":
                    self.add_error(
                        "phone_number_id",
                        "Este phone ID nao pertence a WABA informada. "
                        "A unidade nao foi salva.",
                    )
                    return

                if campo_com_erro == "waba_id":
                    self.add_error(
                        "waba_id",
                        "A Meta falhou ao assinar esta WABA. Unidade nao foi salva.",
                    )
                    return

                if campo_com_erro == "phone_number_id":
                    self.add_error(
                        "phone_number_id",
                        "A Meta falhou ao registrar este numero. Unidade nao foi salva.",
                    )
                    return

                model_admin._validar_cache_unidades_form(
                    self,
                    request,
                    meta_validada=True,
                )

        return UnidadeAdminForm

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        self._registrar_alteracao_cache_unidades()

    def delete_model(self, request, obj):
        if not self._meta_desregistrada_nesta_requisicao(request, obj):
            if not self._desregistrar_meta_antes_de_excluir(request, obj):
                return

        if not self._cache_validado_nesta_requisicao(request, obj):
            if not self._validar_cache_unidades_antes_de_alterar(
                request,
                "excluir",
                meta_validada=True,
            ):
                return

        super().delete_model(request, obj)
        self._registrar_alteracao_cache_unidades()

    def get_actions(self, request):
        actions = super().get_actions(request)
        actions.pop("delete_selected", None)
        return actions

    def delete_queryset(self, request, queryset):
        logger.warning(
            "admin_unidade_exclusao_massa_bloqueada | acao=manter_registros usuario=%s total=%s",
            request.user,
            queryset.count(),
        )
        self.message_user(
            request,
            "Exclusao em massa de unidade nao permitida. Exclua uma unidade por vez.",
            level=messages.ERROR,
        )

    def delete_view(self, request, object_id, extra_context=None):
        try:
            if request.method == "POST":
                obj = self.get_object(request, object_id)

                if obj and not self._desregistrar_meta_antes_de_excluir(request, obj):
                    return HttpResponseRedirect(
                        reverse(
                            "admin:webhook_unidade_change",
                            args=[object_id],
                        )
                    )

                if obj and not self._validar_cache_unidades_antes_de_alterar(
                    request,
                    "excluir",
                    meta_validada=True,
                ):
                    return HttpResponseRedirect(
                        reverse(
                            "admin:webhook_unidade_change",
                            args=[object_id],
                        )
                    )

                if obj:
                    self._marcar_meta_desregistrada_na_requisicao(request, obj)
                    self._marcar_cache_validado_na_requisicao(request, obj)

            return super().delete_view(request, object_id, extra_context)

        except CacheUnidadesIndisponivel as exc:
            if self._falha_cache_originada_no_banco(exc):
                return self._responder_falha_banco_delete(
                    request,
                    object_id,
                    exc,
                )

            logger.exception(
                "admin_unidade_cache_delete_falhou | acao=rollback_admin object_id=%s meta_ok=%s erro=%s",
                object_id,
                self._meta_sucesso_nesta_requisicao(request),
                exc,
            )
            self.message_user(
                request,
                self._mensagem_falha_redis(request),
                level=messages.ERROR,
            )
            return HttpResponseRedirect(
                reverse(
                    "admin:webhook_unidade_change",
                    args=[object_id],
                )
            )

        except DatabaseError as exc:
            return self._responder_falha_banco_delete(
                request,
                object_id,
                exc,
            )

    def _registrar_alteracao_cache_unidades(self):
        with connection.cursor() as cursor:
            versao = incrementar_versao_cache_unidades(cursor)
            total_unidades = recarregar_cache_unidades_ou_erro(cursor)

        logger.info(
            "cache_unidades_versao_incrementada | acao=incrementar_versao_e_recarregar versao=%s unidades=%s",
            versao,
            total_unidades,
        )

    def link_agendamento_clickable(self, obj):
        if obj.link_agendamento:
            return format_html(
                '<a href="{}" target="_blank">Abrir</a>',
                obj.link_agendamento,
            )
        return "-"

    link_agendamento_clickable.short_description = "Agendamento"

    def link_instagram_clickable(self, obj):
        if obj.link_instagram:
            return format_html(
                '<a href="{}" target="_blank">Abrir</a>',
                obj.link_instagram,
            )
        return "-"

    link_instagram_clickable.short_description = "Instagram"

    def _preparar_meta_antes_de_salvar(
        self,
        request,
        waba_id,
        phone_number_id,
    ):
        if not self._validar_vinculo_phone_waba_antes_de_salvar(
            request,
            waba_id,
            phone_number_id,
        ):
            return "vinculo_waba_phone"

        if not self._ativar_waba_antes_de_salvar(request, waba_id):
            return "waba_id"

        if not self._registrar_meta_antes_de_salvar(
            request,
            phone_number_id,
        ):
            return "phone_number_id"

        return None

    def _validar_vinculo_phone_waba_antes_de_salvar(
        self,
        request,
        waba_id,
        phone_number_id,
    ):
        try:
            status, resposta = validar_phone_number_id_da_waba(
                waba_id,
                phone_number_id,
            )

            if not self._meta_resposta_sucesso(status, resposta):
                logger.error(
                    "whatsapp_phone_waba_vinculo_invalido | "
                    "acao=bloquear_save waba_id=%s phone_number_id=%s "
                    "status=%s motivo=%s",
                    short_value(waba_id),
                    short_value(phone_number_id),
                    status,
                    resposta.get("reason")
                    if isinstance(resposta, dict)
                    else None,
                )
                self.message_user(
                    request,
                    "A Meta nao confirmou que o phone ID pertence a "
                    "WABA informada. A unidade nao foi salva.",
                    level=messages.ERROR,
                )
                return False

            logger.info(
                "whatsapp_phone_waba_vinculo_ok | "
                "acao=permitir_ativacao waba_id=%s phone_number_id=%s",
                short_value(waba_id),
                short_value(phone_number_id),
            )
            return True

        except Exception as exc:
            logger.exception(
                "whatsapp_phone_waba_validacao_erro | "
                "acao=bloquear_save waba_id=%s phone_number_id=%s "
                "erro=%s",
                short_value(waba_id),
                short_value(phone_number_id),
                exc,
            )
            self.message_user(
                request,
                "Erro ao validar WABA e phone ID na Meta. "
                f"A unidade nao foi salva: {exc}",
                level=messages.ERROR,
            )
            return False

    def _ativar_waba_antes_de_salvar(self, request, waba_id):
        try:
            status, resposta = ativar_waba_id(waba_id)

            if not self._meta_resposta_sucesso(status, resposta):
                logger.error(
                    "whatsapp_waba_ativar_falhou | acao=bloquear_save "
                    "waba_id=%s status=%s resposta=%s",
                    short_value(waba_id),
                    status,
                    resposta,
                )
                self.message_user(
                    request,
                    "Erro ao assinar WABA no WhatsApp. "
                    f"Unidade nao foi salva: {resposta}",
                    level=messages.ERROR,
                )
                return False

            self._marcar_meta_sucesso(
                request,
                acao="ativar_waba",
                waba_id=waba_id,
            )
            logger.info(
                "whatsapp_waba_ativada | acao=permitir_registro_numero "
                "waba_id=%s status=%s",
                short_value(waba_id),
                status,
            )
            return True

        except Exception as exc:
            logger.exception(
                "whatsapp_waba_ativar_erro | acao=bloquear_save "
                "waba_id=%s erro=%s",
                short_value(waba_id),
                exc,
            )
            self.message_user(
                request,
                "Erro inesperado ao assinar WABA. "
                f"Unidade nao foi salva: {exc}",
                level=messages.ERROR,
            )
            return False

    def _registrar_meta_antes_de_salvar(self, request, phone_number_id):
        try:
            status, resposta = registrar_numero_whatsapp(phone_number_id)

            if not self._meta_resposta_sucesso(status, resposta):
                logger.error(
                    "whatsapp_numero_registrar_falhou | acao=bloquear_save phone_number_id=%s status=%s resposta=%s",
                    short_value(phone_number_id),
                    status,
                    resposta,
                )
                self.message_user(
                    request,
                    f"Erro ao registrar numero no WhatsApp. Unidade nao foi salva: {resposta}",
                    level=messages.ERROR,
                )
                return False

            self._marcar_meta_sucesso(
                request,
                acao="registrar_numero",
                phone_number_id=phone_number_id,
            )
            logger.info(
                "whatsapp_numero_registrado | acao=permitir_save phone_number_id=%s status=%s",
                short_value(phone_number_id),
                status,
            )
            return True

        except Exception as exc:
            logger.exception(
                "whatsapp_numero_registrar_erro | acao=bloquear_save phone_number_id=%s erro=%s",
                short_value(phone_number_id),
                exc,
            )
            self.message_user(
                request,
                f"Erro inesperado ao registrar numero. Unidade nao foi salva: {exc}",
                level=messages.ERROR,
            )
            return False

    def _desregistrar_meta_antes_de_excluir(self, request, obj):
        if not self._desassinar_waba_antes_de_excluir(request, obj):
            return False

        try:
            status, resposta = desregistrar_numero_whatsapp(obj.phone_number_id)

            if not self._meta_resposta_sucesso(status, resposta):
                logger.error(
                    "whatsapp_numero_desregistrar_falhou | acao=bloquear_delete phone_number_id=%s status=%s resposta=%s",
                    short_value(obj.phone_number_id),
                    status,
                    resposta,
                )
                self.message_user(
                    request,
                    "A WABA foi desassinada, mas a Meta falhou ao "
                    "desregistrar o numero. Unidade mantida no banco: "
                    f"{resposta}",
                    level=messages.ERROR,
                )
                return False

            self._marcar_meta_sucesso(
                request,
                acao="desregistrar_numero",
                phone_number_id=obj.phone_number_id,
            )
            logger.warning(
                "whatsapp_numero_desregistrado | acao=permitir_delete phone_number_id=%s status=%s",
                short_value(obj.phone_number_id),
                status,
            )
            return True

        except Exception as exc:
            logger.exception(
                "whatsapp_numero_desregistrar_erro | acao=bloquear_delete phone_number_id=%s erro=%s",
                short_value(obj.phone_number_id),
                exc,
            )
            self.message_user(
                request,
                "A WABA foi desassinada, mas ocorreu um erro ao "
                "desregistrar o numero. Unidade mantida no banco: "
                f"{exc}",
                level=messages.ERROR,
            )
            return False

    def _desassinar_waba_antes_de_excluir(self, request, obj):
        try:
            status, resposta = desativar_waba_id(obj.waba_id)

            if not self._meta_resposta_sucesso(status, resposta):
                logger.error(
                    "whatsapp_waba_desassinar_falhou | "
                    "acao=bloquear_delete waba_id=%s status=%s "
                    "resposta=%s",
                    short_value(obj.waba_id),
                    status,
                    resposta,
                )
                self.message_user(
                    request,
                    "Erro ao remover a assinatura da WABA na Meta. "
                    f"Unidade mantida no banco: {resposta}",
                    level=messages.ERROR,
                )
                return False

            self._marcar_meta_sucesso(
                request,
                acao="desativar_waba",
                waba_id=obj.waba_id,
            )
            logger.warning(
                "whatsapp_waba_desassinada | acao=continuar_delete "
                "waba_id=%s status=%s",
                short_value(obj.waba_id),
                status,
            )
            return True

        except Exception as exc:
            logger.exception(
                "whatsapp_waba_desassinar_erro | "
                "acao=bloquear_delete waba_id=%s erro=%s",
                short_value(obj.waba_id),
                exc,
            )
            self.message_user(
                request,
                "Erro inesperado ao remover a assinatura da WABA. "
                f"Unidade mantida no banco: {exc}",
                level=messages.ERROR,
            )
            return False

    def _marcar_meta_sucesso(
        self,
        request,
        acao,
        **identificadores,
    ):
        operacoes = list(
            getattr(request, "_unidade_meta_sucesso", [])
        )
        operacoes.append({
            "acao": acao,
            **{
                nome: str(valor)
                for nome, valor in identificadores.items()
            },
        })
        request._unidade_meta_sucesso = operacoes

    @staticmethod
    def _meta_sucesso_nesta_requisicao(request):
        return bool(
            getattr(
                request,
                "_unidade_meta_sucesso",
                None,
            )
        )

    def _marcar_meta_desregistrada_na_requisicao(self, request, obj):
        ids = getattr(request, "_unidades_meta_desregistradas", set())
        ids.add(obj.id_unidade)
        request._unidades_meta_desregistradas = ids

    def _meta_desregistrada_nesta_requisicao(self, request, obj):
        ids = getattr(request, "_unidades_meta_desregistradas", set())
        return obj.id_unidade in ids

    def _marcar_cache_validado_na_requisicao(self, request, obj):
        ids = getattr(request, "_unidades_cache_validadas", set())
        ids.add(obj.id_unidade)
        request._unidades_cache_validadas = ids

    def _cache_validado_nesta_requisicao(self, request, obj):
        ids = getattr(request, "_unidades_cache_validadas", set())
        return obj.id_unidade in ids

    def _validar_cache_unidades_form(self, form, request, meta_validada):
        if self._validar_cache_unidades_antes_de_alterar(
            request,
            "salvar",
            meta_validada=meta_validada,
        ):
            return

        form.add_error(
            None,
            self._mensagem_cache_unidades_falhou(meta_validada),
        )

    def _validar_cache_unidades_antes_de_alterar(
        self,
        request,
        acao,
        meta_validada=False,
    ):
        try:
            validar_cache_unidades_disponivel_ou_erro()
            logger.info(
                "cache_unidades_preflight_admin_ok | acao=%s",
                acao,
            )
            return True

        except CacheUnidadesIndisponivel as exc:
            logger.error(
                "cache_unidades_preflight_admin_falhou | acao=%s erro=%s",
                acao,
                exc,
            )

            if request is not None:
                self.message_user(
                    request,
                    self._mensagem_cache_unidades_falhou(meta_validada),
                    level=messages.ERROR,
                )

            return False

    def _responder_falha_banco(
        self,
        request,
        object_id,
        exc,
    ):
        logger.exception(
            "admin_unidade_banco_falhou | acao=rollback_sem_compensacao object_id=%s meta_ok=%s erro=%s",
            object_id,
            self._meta_sucesso_nesta_requisicao(request),
            exc,
        )
        self.message_user(
            request,
            self._mensagem_falha_banco(request),
            level=messages.ERROR,
        )
        return HttpResponseRedirect(request.path)

    def _responder_falha_banco_delete(
        self,
        request,
        object_id,
        exc,
    ):
        logger.exception(
            "admin_unidade_banco_delete_falhou | acao=rollback_sem_compensacao object_id=%s meta_ok=%s erro=%s",
            object_id,
            self._meta_sucesso_nesta_requisicao(request),
            exc,
        )
        self.message_user(
            request,
            self._mensagem_falha_banco(request),
            level=messages.ERROR,
        )
        return HttpResponseRedirect(
            reverse(
                "admin:webhook_unidade_change",
                args=[object_id],
            )
        )

    def _mensagem_falha_banco(self, request):
        if self._meta_sucesso_nesta_requisicao(request):
            return (
                "A Meta concluiu a operação com sucesso, mas o banco "
                "falhou. A alteração da Meta foi mantida; banco e "
                "cache de unidades no Redis não foram confirmados. Faça uma "
                "conferência manual."
            )

        return (
            "O banco falhou e nenhuma alteração local foi "
            "confirmada. Nenhuma operação Meta foi concluída nesta "
            "requisição."
        )

    def _mensagem_falha_redis(self, request):
        if self._meta_sucesso_nesta_requisicao(request):
            return (
                "A Meta concluiu a operação com sucesso, mas o Redis "
                "falhou. A alteração da Meta foi mantida; nenhuma "
                "alteração foi confirmada no banco ou no cache. Faça "
                "uma conferência manual."
            )

        return (
            "O Redis falhou ao atualizar o cache de unidades. "
            "Nenhuma alteração foi confirmada no banco."
        )

    @staticmethod
    def _mensagem_cache_unidades_falhou(meta_validada):
        if meta_validada:
            return (
                "A Meta concluiu a operação com sucesso, mas o Redis "
                "falhou. A alteração da Meta foi mantida e a unidade "
                "não foi salva no banco. Faça uma conferência manual."
            )

        return (
            "O Redis falhou ao atualizar o cache de unidades. "
            "Nenhuma alteração foi feita no banco."
        )

    @staticmethod
    def _falha_cache_originada_no_banco(exc):
        causa = exc.__cause__

        while causa is not None:
            if isinstance(causa, DatabaseError):
                return True

            causa = causa.__cause__

        return False

    @staticmethod
    def _meta_resposta_sucesso(status, resposta):
        if status not in (200, 204):
            return False

        if isinstance(resposta, dict) and resposta.get("success") is False:
            return False

        return True


@admin.register(Cliente)
class ClienteAdmin(SomenteVisualizacaoAdminMixin, admin.ModelAdmin):

    list_display = (
        "id_cliente",
        "nome",
        "waid_telefone",
        "email",
        "idade",
        "profissao",
    )

    search_fields = (
        "nome",
        "waid_telefone",
        "email",
        "profissao",
    )

    ordering = ("nome",)
    list_per_page = 50
    empty_value_display = "-"


@admin.register(Dependente)
class DependenteAdmin(SomenteVisualizacaoAdminMixin, admin.ModelAdmin):

    list_display = (
        "id_dependente",
        "id_cliente",
        "id_conversa",
        "nome_dependente",
        "idade",
    )

    search_fields = (
        "nome_dependente",
        "id_cliente__waid_telefone",
        "id_cliente__nome",
    )

    ordering = ("id_dependente",)
    list_per_page = 50
    empty_value_display = "-"

    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            "id_cliente",
            "id_conversa",
        )


@admin.register(Etapa)
class EtapaAdmin(SomenteVisualizacaoAdminMixin, admin.ModelAdmin):

    list_display = (
        "id_etapa",
        "nome_etapa",
        "encerra_automaticamente",
        "bloqueio_dias",
        "elegivel_funil",
    )

    search_fields = ("nome_etapa",)
    list_filter = (
        "encerra_automaticamente",
        "elegivel_funil",
    )
    ordering = ("id_etapa",)

    list_per_page = 50
    empty_value_display = "-"


@admin.register(Conversa)
class ConversaAdmin(SomenteVisualizacaoAdminMixin, admin.ModelAdmin):

    list_display = (
        "id_conversa",
        "cliente_link",
        "id_unidade",
        "id_etapa_atual",
        "profissao",
        "turnos_sem_avanco",
        "status_ativa",
        "motivo_encerramento",
        "last_message_from",
        "followup_stage",
        "lead_no_funil",
        "processing",
        "last_interaction_at",
        "iniciou_em",
    )

    search_fields = (
        "id_cliente__waid_telefone",
        "id_cliente__nome",
        "profissao",
    )

    list_filter = (
        "status_ativa",
        "motivo_encerramento",
        "turnos_sem_avanco",
        "lead_no_funil",
        "last_message_from",
        "followup_stage",
        "processing",
        "id_unidade",
        "id_etapa_atual",
    )

    ordering = ("-iniciou_em",)

    date_hierarchy = "iniciou_em"
    list_per_page = 50
    empty_value_display = "-"

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related(
            "id_cliente",
            "id_unidade",
            "id_etapa_atual",
        )

    def cliente_link(self, obj):
        if not obj.id_cliente:
            return "-"

        try:
            url = reverse(
                "admin:webhook_cliente_change",
                args=[obj.id_cliente.id_cliente],
            )
            return format_html(
                '<a href="{}">{}</a>',
                url,
                obj.id_cliente.nome or obj.id_cliente.waid_telefone,
            )
        except NoReverseMatch as exc:
            logger.exception(
                "admin_cliente_link_falhou | acao=retornar_texto_sem_link erro=%s",
                exc,
            )
            return obj.id_cliente.nome or obj.id_cliente.waid_telefone

    cliente_link.short_description = "Cliente"


@admin.register(FilaMensagens)
class FilaMensagensAdmin(SomenteVisualizacaoAdminMixin, admin.ModelAdmin):

    list_display = (
        "id_mensagem",
        "id_conversa",
        "status_colorido",
        "tipo_mensagem",
        "cliente_telefone",
        "id_hash_msg",
        "received_data_hora",
        "retry_count",
        "next_attempt_at",
        "erro_resumido",
    )

    search_fields = (
        "cliente_telefone",
        "id_hash_msg",
        "id_conversa__id_conversa",
    )

    list_filter = (
        "status",
        "tipo_mensagem",
        "id_conversa",
    )

    ordering = ("-received_data_hora",)
    date_hierarchy = "received_data_hora"

    list_per_page = 50
    empty_value_display = "-"

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("id_conversa")

    def status_colorido(self, obj):
        cores = {
            "sent": "green",
            "failed": "red",
            "pending": "#555",
            "processing": "orange",
        }
        cor = cores.get(obj.status, "#000")
        return format_html('<b style="color:{};">{}</b>', cor, obj.status)

    status_colorido.short_description = "Status"

    def erro_resumido(self, obj):
        if not obj.last_error:
            return "-"

        texto = obj.last_error[:60]

        return format_html(
            '<span title="{}">{}</span>',
            obj.last_error,
            texto + ("..." if len(obj.last_error) > 60 else ""),
        )

    erro_resumido.short_description = "Erro"


@admin.register(HistoricoMensagens)
class HistoricoMensagensAdmin(SomenteVisualizacaoAdminMixin, admin.ModelAdmin):

    list_display = (
        "id_mensagem",
        "quem_enviou",
        "tipo_mensagem",
        "status_envio",
        "id_conversa",
        "id_etapa",
        "id_mensagem_fila",
        "id_hash_cliente_origem",
        "cliente_telefone",
        "received_data_hora",
    )

    search_fields = (
        "cliente_telefone",
        "id_hash_msg",
        "id_hash_cliente_origem",
        "id_mensagem_fila__id_mensagem",
    )

    list_filter = (
        "quem_enviou",
        "status_envio",
        "id_etapa",
        "tipo_mensagem",
    )

    ordering = ("-received_data_hora",)

    date_hierarchy = "received_data_hora"
    list_per_page = 50

    empty_value_display = "-"

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related(
            "id_conversa",
            "id_etapa",
            "id_mensagem_fila",
        )


@admin.register(RespostasDesafios)
class RespostasDesafiosAdmin(SomenteVisualizacaoAdminMixin, admin.ModelAdmin):

    list_display = (
        "id_resposta_desafio",
        "id_conversa",
        "id_etapa",
        "resposta",
        "id_historico_mensagem_cliente",
        "criado_em",
    )

    search_fields = (
        "resposta",
    )

    list_filter = (
        "id_etapa",
    )

    ordering = ("-criado_em",)
    date_hierarchy = "criado_em"
    list_per_page = 50
    empty_value_display = "-"

    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            "id_conversa",
            "id_etapa",
        )


@admin.register(PesquisaSatisfacao)
class PesquisaSatisfacaoAdmin(SomenteVisualizacaoAdminMixin, admin.ModelAdmin):

    list_display = (
        "id_pesquisa_satisfacao",
        "id_conversa",
        "nota",
        "comentario",
        "criado_em",
        "atualizado_em",
    )

    search_fields = (
        "id_conversa__id_conversa",
        "id_conversa__id_cliente__nome",
        "comentario",
    )

    list_filter = ("nota",)
    ordering = ("-atualizado_em",)
    date_hierarchy = "atualizado_em"
    list_per_page = 50
    empty_value_display = "-"

    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            "id_conversa",
            "id_conversa__id_cliente",
        )


@admin.register(WebhookFloodEvento)
class WebhookFloodEventoAdmin(SomenteVisualizacaoAdminMixin, admin.ModelAdmin):

    list_display = (
        "id_evento",
        "wa_id_cliente",
        "phone_id_unidade",
        "id_hash_msg",
        "received_at",
    )

    search_fields = (
        "wa_id_cliente",
        "phone_id_unidade",
        "id_hash_msg",
    )

    list_filter = ("phone_id_unidade",)
    ordering = ("-received_at",)
    date_hierarchy = "received_at"
    list_per_page = 50
    empty_value_display = "-"


@admin.register(CacheControle)
class CacheControleAdmin(SomenteVisualizacaoAdminMixin, admin.ModelAdmin):

    list_display = (
        "nome",
        "versao",
        "atualizado_em",
    )

    search_fields = ("nome",)
    ordering = ("nome",)
    list_per_page = 50
    empty_value_display = "-"


@admin.register(ClienteBloqueadoMeta)
class ClienteBloqueadoMetaAdmin(admin.ModelAdmin):

    list_display = (
        "id_bloqueio",
        "cliente_link",
        "nome",
        "wa_id_cliente",
        "id_unidade",
        "phone_id_unidade",
    )

    search_fields = (
        "nome",
        "wa_id_cliente",
        "phone_id_unidade",
        "id_cliente__waid_telefone",
        "id_cliente__nome",
        "id_unidade__nome_unidade",
    )

    list_filter = ("id_unidade",)
    ordering = ("wa_id_cliente", "id_unidade__nome_unidade")
    list_per_page = 50
    empty_value_display = "-"

    def has_add_permission(self, request):
        return False

    def get_actions(self, request):
        actions = super().get_actions(request)
        actions.pop("delete_selected", None)
        return actions

    def get_readonly_fields(self, request, obj=None):
        return [field.name for field in self.model._meta.fields]

    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            "id_cliente",
            "id_unidade",
        )

    def delete_view(self, request, object_id, extra_context=None):
        if request.method == "POST":
            obj = self.get_object(request, object_id)

            if obj and not self._desbloquear_meta_antes_de_excluir(request, obj):
                return HttpResponseRedirect(
                    reverse(
                        "admin:webhook_clientebloqueadometa_change",
                        args=[object_id],
                    )
                )

        return super().delete_view(request, object_id, extra_context)

    def delete_model(self, request, obj):
        conversas_resetadas = Conversa.objects.filter(
            id_cliente_id=obj.id_cliente_id,
            id_unidade_id=obj.id_unidade_id,
            status_ativa=True,
        ).update(turnos_sem_avanco=0)

        logger.warning(
            "admin_bloqueio_meta_excluido | "
            "acao=resetar_contador_e_excluir_registro "
            "usuario=%s wa_id_cliente=%s phone_id_unidade=%s "
            "conversas_resetadas=%s",
            request.user,
            short_value(obj.wa_id_cliente),
            short_value(obj.phone_id_unidade),
            conversas_resetadas,
        )
        super().delete_model(request, obj)

    def delete_queryset(self, request, queryset):
        logger.warning(
            "admin_bloqueio_meta_exclusao_massa_bloqueada | acao=manter_registros usuario=%s total=%s",
            request.user,
            queryset.count(),
        )
        self.message_user(
            request,
            "Exclusao em massa desativada. Desbloqueie um cliente por unidade de cada vez.",
            level=messages.ERROR,
        )

    def cliente_link(self, obj):
        if not obj.id_cliente:
            return "-"

        try:
            url = reverse(
                "admin:webhook_cliente_change",
                args=[obj.id_cliente.id_cliente],
            )
            return format_html(
                '<a href="{}">{}</a>',
                url,
                obj.id_cliente.nome or obj.id_cliente.waid_telefone,
            )
        except NoReverseMatch as exc:
            logger.exception(
                "admin_cliente_link_falhou | acao=retornar_texto_sem_link erro=%s",
                exc,
            )
            return obj.id_cliente.nome or obj.id_cliente.waid_telefone

    cliente_link.short_description = "Cliente"

    def _desbloquear_meta_antes_de_excluir(self, request, obj):
        try:
            desbloquear_usuario_meta(obj.wa_id_cliente, obj.phone_id_unidade)

            logger.warning(
                "admin_cliente_desbloqueado_meta | acao=desbloquear_meta_antes_excluir usuario=%s wa_id_cliente=%s phone_id_unidade=%s",
                request.user,
                short_value(obj.wa_id_cliente),
                short_value(obj.phone_id_unidade),
            )

            self.message_user(
                request,
                f"Cliente {obj.wa_id_cliente} desbloqueado na Meta. Registro removido do banco.",
                level=messages.SUCCESS,
            )
            return True

        except Exception as exc:
            logger.exception(
                "admin_desbloqueio_meta_falhou | acao=manter_registro usuario=%s wa_id_cliente=%s phone_id_unidade=%s erro=%s",
                request.user,
                short_value(obj.wa_id_cliente),
                short_value(obj.phone_id_unidade),
                exc,
            )
            self.message_user(
                request,
                f"Falha ao desbloquear na Meta. Registro mantido no banco: {exc}",
                level=messages.ERROR,
            )
            return False


@admin.register(AtendimentoCustomizado)
class AtendimentoCustomizadoAdmin(admin.ModelAdmin):
    list_display = (
        "id_customizacao",
        "id_unidade",
        "nome_agente",
        "email_obrigatorio",
        "link_agendamento",
    )
    list_select_related = ("id_unidade",)
    search_fields = ("id_unidade__nome_unidade", "nome_agente")

    def get_readonly_fields(self, request, obj=None):
        return ("id_unidade",) if obj else ()

    def has_add_permission(self, request):
        return False  # A criação é feita junto da unidade, pelo inline obrigatório.

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(IntegracaoFireAds)
class IntegracaoFireAdsAdmin(admin.ModelAdmin):
    list_display = (
        "id_integracao_fireads",
        "id_unidade",
        "integracao_ativa",
        "contrato_validado",
        "ativada_em",
    )
    list_select_related = ("id_unidade",)
    search_fields = ("id_unidade__nome_unidade",)
    readonly_fields = ("ativada_em", "criado_em", "atualizado_em")

    def get_readonly_fields(self, request, obj=None):
        return self.readonly_fields + (("id_unidade",) if obj else ())

    def has_delete_permission(self, request, obj=None):
        return False  # Desativar preserva vínculos e snapshots históricos.


class FireAdsConsultaAdmin(SomenteVisualizacaoAdminMixin, admin.ModelAdmin):
    pass


for modelo in (Chat, ConsultaFireAds, EnvioDash):
    admin.site.register(modelo, FireAdsConsultaAdmin)
```

## Passo 38 — Substituir integralmente `core/database/deploy_database/etapa_transicao_script.py`

```python
import logging

from core.database.deploy_database.transacao_deploy import transacao_deploy


logger = logging.getLogger("db.etapa_transicao")


TRANSICOES_INICIAIS = (
    (1, "nome_cliente_valido", 2),
    (2, "destino_atendimento_definido", 3),
    (3, "destino_atendimento_confirmado", 4),
    # A profissão é obrigatória para titular e dependente. Somente depois dela
    # o status salvo escolhe nome do dependente (5) ou idade do titular (6).
    (4, "profissao_dependente_valida", 5),
    (4, "profissao_titular_valida", 6),
    (5, "nome_dependente_valido", 6),
    (6, "idade_valida", 7),
    (7, "oferta_aceita", 10),
    (7, "oferta_aceita_email_fireads", 11),
    (7, "oferta_adiada", 8),
    (8, "cliente_retornou", 9),
    (9, "retorno_confirmado", 10),
    (9, "retorno_confirmado_email_fireads", 11),
    (9, "retorno_adiado", 8),
    (10, "email_valido", 11),
    (11, "triagem_iniciada", 12),
    (12, "triagem_pergunta_1_respondida", 13),
    (13, "triagem_pergunta_2_respondida", 14),
    (14, "triagem_pergunta_3_respondida", 15),
    (15, "triagem_pergunta_4_respondida", 16),
    (16, "triagem_pergunta_5_respondida", 17),
    (17, "triagem_pergunta_6_respondida", 20),
    (17, "triagem_concluida_sem_link", 18),
    (18, "turno_escolhido", 19),
    (19, "avaliacao_solicitada", 21),
    (20, "agendamento_confirmado", 21),
    (21, "satisfacao_avaliada", 22),
    (22, "comentario_satisfacao_aceito", 23),
    (22, "comentario_satisfacao_recusado", 24),
    (23, "comentario_satisfacao_recebido", 24),
)

# O mapa declara o fluxo completo conhecido. Resolvers e senders continuam
# responsáveis por produzir somente eventos já implementados na aplicação.


def criar_e_povoar_transicoes_etapa():
    with transacao_deploy("sincronizar_mapa_transicoes", logger) as cursor:
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS chatbot.etapa_transicao (
                id_transicao SERIAL PRIMARY KEY,
                id_etapa_origem INT NOT NULL,
                evento VARCHAR(100) NOT NULL,
                id_etapa_destino INT NOT NULL,

                CONSTRAINT etapa_transicao_origem_fkey
                    FOREIGN KEY (id_etapa_origem)
                    REFERENCES chatbot.etapa(id_etapa)
                    ON DELETE RESTRICT,

                CONSTRAINT etapa_transicao_destino_fkey
                    FOREIGN KEY (id_etapa_destino)
                    REFERENCES chatbot.etapa(id_etapa)
                    ON DELETE RESTRICT,

                CONSTRAINT etapa_transicao_sem_auto_salto
                    CHECK (id_etapa_origem <> id_etapa_destino),

                CONSTRAINT etapa_transicao_origem_evento_unique
                    UNIQUE (id_etapa_origem, evento),

                CONSTRAINT etapa_transicao_origem_destino_unique
                    UNIQUE (id_etapa_origem, id_etapa_destino)
            );
            """
        )

        # Isto sincroniza dados de catálogo, não migra schema. A whitelist
        # precisa ser exata e manter IDs previsíveis após uma reexecução.
        cursor.execute(
            "TRUNCATE TABLE chatbot.etapa_transicao RESTART IDENTITY;"
        )

        cursor.executemany(
            """
            INSERT INTO chatbot.etapa_transicao (
                id_etapa_origem,
                evento,
                id_etapa_destino
            )
            VALUES (%s, %s, %s);
            """,
            TRANSICOES_INICIAIS,
        )

    logger.info(
        "etapa_transicao_setup_ok | acao=sincronizar_mapa quantidade=%s",
        len(TRANSICOES_INICIAIS),
    )
```

## Passo 39 — Criar `core/database/deploy_database/fireads_script.py`

```python
"""DDL único compartilhado com a migração manual do deploy."""

import logging
from pathlib import Path

from core.database.deploy_database.transacao_deploy import transacao_deploy


def criar_estrutura_fireads():
    caminho = (
        Path(__file__).resolve().parents[3]
        / "deploy/migrations/20261007_fireads_chat_customizacao.sql"
    )
    script = caminho.read_text(encoding="utf-8")
    ddl = script.split("-- INICIO DDL FIREADS\n", 1)[1].split("-- FIM DDL FIREADS", 1)[
        0
    ]
    with transacao_deploy(
        "estrutura_fireads", logging.getLogger("db.fireads")
    ) as cursor:
        cursor.execute(ddl)
```

## Passo 40 — Substituir integralmente `core/database/deploy_database/setup_database.py`

```python
import logging
from core.database.deploy_database.fireads_script import criar_estrutura_fireads

from core.cache.cache_reset import resetar_cache_redis_dev
from core.database.connection_check import connection_teste_psql
from core.database.deploy_database.bank_script import (
    configurar_role_banco,
    criar_funcao_dequeue_message,
    criar_funcoes_lock,
    criar_tabelas,
)
from core.database.deploy_database.cache_control_script import (
    criar_cache_controle,
)
from core.database.deploy_database.etapa_transicao_script import (
    criar_e_povoar_transicoes_etapa,
)
from core.database.deploy_database.floodscript import (
    criar_tabelas_bloqueio_flood,
)
from core.database.deploy_database.povoar_etapas import insere_etapa_once
from core.database.deploy_database.turno_cliente_script import (
    criar_indices_turno_cliente,
)


logger = logging.getLogger("db.deploy_database")


def setup_database_aws():
    logger.info("banco_setup_iniciado | acao=configurar_banco")

    # 1. Infraestrutura e configuração da role usada pela aplicação.
    connection_teste_psql()
    configurar_role_banco()

    # 2. Schema final e estruturas auxiliares por domínio.
    criar_tabelas()
    criar_cache_controle()
    criar_tabelas_bloqueio_flood()
    criar_indices_turno_cliente()

    # 3. Funções PostgreSQL consumidas pelo worker.
    criar_funcao_dequeue_message()
    criar_funcoes_lock()

    # 4. Catálogos executáveis do fluxo de atendimento.
    insere_etapa_once()
    criar_e_povoar_transicoes_etapa()
    criar_estrutura_fireads()

    # 5. O cache derivado só é reconstruído após o banco estar completo.
    resetar_cache_redis_dev()

    logger.info("banco_setup_finalizado | acao=configurar_banco")


if __name__ == "__main__":
    setup_database_aws()
```

## Passo 41 — Criar `tests/unit/test_fireads.py`

```python
"""Contratos de importação/entrega: HTTP e Meta sempre simulados."""

from copy import deepcopy
import unittest
from unittest.mock import Mock, patch
from core.integrations.fireads.cliente import ClienteFireAds, validar_url
from core.integrations.fireads.contrato import (
    destino,
    selecionar,
    ErroFireAds,
    bloco_observacoes,
    acrescentar_observacoes,
)
from workers.worker_flow.fireads import interpretar, email_importado, preparar_abertura
from workers.worker_funil.fireads import preparar_escrita
from workers.worker_flow.response_flow.etapas import resolver_etapa7, resolver_etapa9
from workers.worker_flow.transacoes.movimento_conversa import (
    resolver_movimento_conversa,
)
from core.integrations.funil.oportunidades import montar_payload_oportunidade
from tests.helpers import FakeConn, FakeCursor

NUMERO = "5511999990002"
GOOGLE = {
    "Nome": "Ana Paula Silva",
    "Email": "ana@example.com",
    "WhatsApp": NUMERO,
    "Perfil/Faixa": "Para mim",
    "Data/Hora": "01/10/2026 12:00",
}
META = {
    "full_name": "Carlos Silva",
    "email": "carlos@example.com",
    "phone_number": NUMERO,
    "para_quem": "mim_e_outra",
    "created_time": "2026-10-01T12:00:00-05:00",
}


def estado():
    return dict(
        interpretar([GOOGLE], [], NUMERO, None),
        concluida=True,
        id_conversa=2,
        id_integracao=1,
    )


class FireAdsTests(unittest.TestCase):
    def test_admin_nao_chama_meta_com_personalizacao_invalida(self):
        from django.contrib.admin import AdminSite
        from django.test import RequestFactory
        from types import SimpleNamespace
        from webhook.admin import UnidadeAdmin
        from webhook.models import Unidade

        admin = UnidadeAdmin(Unidade, AdminSite())
        request = RequestFactory().post("/admin/")
        request.user = SimpleNamespace(has_perm=lambda *_: True)
        request._unidade_formsets = [Mock(is_valid=Mock(return_value=False))]
        form_class = admin.get_form(request, fields=["waba_id", "phone_number_id"])
        with patch.object(Unidade, "validate_unique"), patch.object(
            Unidade, "validate_constraints"
        ), patch.object(admin, "_preparar_meta_antes_de_salvar") as meta:
            form = form_class(data={"waba_id": "123", "phone_number_id": "456"})
            self.assertFalse(form.is_valid())
            self.assertIn("atendimento customizado", str(form.non_field_errors()))
            meta.assert_not_called()

    def test_abertura_personalizada_preserva_tratamentos_sem_recoletar_nome(self):
        from workers.worker_flow.fireads import classificar_tratamento_abertura
        from core.integrations.whatsapp.messages.etapa4_messages import (
            montar_abertura_fireads,
        )

        contexto = {
            "contexto_fireads": estado(),
            "nome_agente": "Dora",
            "nome_unidade": "Supera Teste",
            "genero": "feminino",
        }
        for tipo, texto, esperado in [
            ("image", "", "tipo_mensagem_nao_suportado"),
            ("text", "quanto custa?", "pergunta_financeira"),
            ("text", "Oi", None),
        ]:
            with self.subTest(tipo=tipo, texto=texto):
                contexto.update(tipo_mensagem_atual=tipo, texto_cliente_atual=texto)
                tratamento = classificar_tratamento_abertura(contexto)
                self.assertEqual(tratamento, esperado)
                mensagem = montar_abertura_fireads(
                    contexto, saudacao="Boa tarde", tratamento=tratamento,
                )
                self.assertIn("Ana Paula", mensagem)
                self.assertIn("profiss", mensagem.lower())
                self.assertNotIn("Como você se chama", mensagem)

    def test_abertura_importada_registra_etapa4_e_replay_nao_reenvia(self):
        from datetime import datetime, timezone
        from workers.worker_flow import valida_historico as historico
        from workers.worker_flow.response_flow import flow_sender as sender
        from contextlib import ExitStack

        agora = datetime.now(timezone.utc)
        mensagem = {
            "id_mensagem": 10,
            "id_hash": "wamid.teste",
            "conteudo_texto": "Olá",
            "tipo_mensagem": "text",
            "cliente_telefone": NUMERO,
            "id_phone_unidade": "teste",
            "unidade_telefone": "5511999990000",
            "retry_count": 1,
        }
        banco = {
            "id_cliente": 1,
            "id_unidade": 1,
            "contexto_fireads": estado(),
            "conversa": {
                "id_conversa": 2,
                "id_etapa_atual": None,
                "last_message_from": "cliente",
                "status_dependente": False,
            },
        }
        with ExitStack() as stack:
            inserir = stack.enter_context(
                patch.object(
                    historico,
                    "inserir_historico_mensagem_cliente",
                    side_effect=lambda **k: (1, agora, k["id_etapa"], True),
                )
            )
            stack.enter_context(
                patch.object(
                    historico,
                    "buscar_resposta_bot_por_mensagem_cliente",
                    return_value=None,
                )
            )
            stack.enter_context(
                patch.object(
                    historico,
                    "listar_transicoes_permitidas",
                    return_value={
                        "profissao_titular_valida": 6,
                        "profissao_dependente_valida": 5,
                    },
                )
            )
            stack.enter_context(
                patch.object(
                    historico,
                    "buscar_contexto_etapa1",
                    return_value={
                        "nome_unidade": "Teste",
                        "nome_agente": "Dora",
                        "genero": "feminino",
                    },
                )
            )
            stack.enter_context(
                patch.object(historico, "atualizar_conversa_mensagem_cliente")
            )
            cx = historico.valida_historico(mensagem, banco, FakeCursor())
        self.assertEqual(inserir.call_args.kwargs["id_etapa"], 4)
        self.assertEqual(cx["id_etapa_origem_transicao"], 4)
        with patch.object(
            sender, "enviar_abertura_fireads", return_value={"id_etapa_resultante": 4}
        ) as envio:
            self.assertEqual(sender.flow_sender(cx)["id_etapa_resultante"], 4)
            envio.assert_called_once()
        # Banco confirmou resposta + movimento; só a fila precisou de retry.
        cx.update(
            id_etapa_atual=4,
            resposta_bot_para_mensagem_atual={
                "id_mensagem": 2,
                "id_etapa": 4,
                "id_hash_msg": "wamid.bot",
            },
        )
        with patch.object(sender, "enviar_abertura_fireads") as envio:
            resposta = sender.flow_sender(cx)
            self.assertTrue(resposta["resposta_ja_existia"])
            self.assertEqual(resolver_movimento_conversa(cx, resposta), "sem_avanco")
            envio.assert_not_called()

    def test_mapeamento_sem_inferir_por_faixa_etaria(self):
        for valor in ("Para mim", "para_mim"):
            self.assertIs(destino(valor), False)
        for valor in (
            "Para meu pai/mãe",
            "Para meu avô/avó",
            "Para outra pessoa",
            "Para meu pai ou minha mãe",
            "Para meu filho ou filha",
            "Para mim e outra pessoa",
            "mim_e_outra",
            "pai_ou_mae",
            "filho_ou_filha",
        ):
            self.assertIs(destino(valor), True, valor)
        for valor in (
            "Adulto",
            "Criança",
            "Adolescente",
            "Pessoa com 60 anos ou mais",
            "",
            None,
            "teste",
        ):
            self.assertIsNone(destino(valor), valor)

    def test_importa_nome_composto_e_nao_faixa_ou_objetivo(self):
        valor = interpretar([dict(GOOGLE, Objetivo="Memória")], [], NUMERO, None)
        self.assertEqual(valor["resultado"], "importado")
        self.assertEqual(valor["dados_titular"]["nome"], "Ana Paula")
        self.assertNotIn("idade", valor["dados_titular"])
        self.assertNotIn("Objetivo", valor)

    def test_registro_antigo_unico_nao_expira(self):
        self.assertEqual(
            interpretar(
                [dict(GOOGLE, **{"Data/Hora": "01/01/2020 12:00"})], [], NUMERO, None
            )["origem"],
            "google",
        )

    def test_datas_sao_comparadas_com_offset_da_fonte(self):
        self.assertEqual(
            selecionar([GOOGLE], [META], NUMERO, "America/Sao_Paulo")[0], "meta"
        )
        with self.assertRaises(ErroFireAds):
            selecionar([GOOGLE], [META], NUMERO, None)

    def test_mais_recente_invalido_nao_resgata_antigo(self):
        decisao = interpretar(
            [GOOGLE], [dict(META, email="inválido")], NUMERO, "America/Sao_Paulo"
        )
        self.assertEqual(decisao["origem"], "organico")
        self.assertEqual(decisao["dados_titular"], {})

    def test_empate_conflitante_e_telefone_diferente(self):
        self.assertEqual(
            interpretar(
                [GOOGLE],
                [dict(META, created_time="2026-10-01T15:00:00Z")],
                NUMERO,
                "America/Sao_Paulo",
            )["resultado"],
            "ambiguidade",
        )
        self.assertEqual(
            interpretar([GOOGLE], [], "5511999990003", None)["resultado"], "ausente"
        )

    def test_email_do_cadastro_geral_nao_autoriza_salto(self):
        self.assertFalse(
            email_importado({"id_conversa": 2, "email_cliente": "ana@example.com"})
        )
        self.assertFalse(
            email_importado({"id_conversa": 3, "contexto_fireads": estado()})
        )
        self.assertTrue(
            email_importado({"id_conversa": 2, "contexto_fireads": estado()})
        )

    def test_inicializacao_4_exige_importacao_completa(self):
        cx = {"id_conversa": 2, "id_etapa_atual": None, "contexto_fireads": estado()}
        self.assertEqual(
            resolver_movimento_conversa(cx, {"id_etapa_resultante": 4}), "inicializacao"
        )
        with self.assertRaises(ValueError):
            resolver_movimento_conversa(
                dict(cx, contexto_fireads=None), {"id_etapa_resultante": 4}
            )

    def test_aceite_da_oferta_e_retorno_pulam_email_somente_quando_importado(self):
        for etapa, mod, evento in [
            (7, resolver_etapa7, "oferta_aceita"),
            (9, resolver_etapa9, "retorno_confirmado"),
        ]:
            cx = {
                "id_conversa": 2,
                "id_etapa_atual": etapa,
                "id_etapa_origem_transicao": etapa,
                "id_etapa_cliente": etapa,
                "contexto_fireads": estado(),
                "tipo_mensagem_atual": "text",
                "texto_cliente_atual": "sim",
                "transicoes_permitidas": {evento: 10, evento + "_email_fireads": 11},
                "mensagem_cliente_atual": {
                    "cliente_telefone": NUMERO,
                    "id_phone_unidade": "teste",
                    "id_mensagem_fila": 1,
                },
            }
            with patch.object(
                mod, "enviar_etapa11", return_value={"id_etapa_resultante": 11}
            ) as triagem, patch.object(
                mod, "enviar_etapa10", return_value={"id_etapa_resultante": 10}
            ) as email:
                resultado = getattr(mod, f"resolve_etapa{etapa}")(cx)
                self.assertEqual(
                    resultado["evento_transicao"], evento + "_email_fireads"
                )
                triagem.assert_called_once()
                email.assert_not_called()
                resultado = getattr(mod, f"resolve_etapa{etapa}")(
                    dict(cx, contexto_fireads=None)
                )
                self.assertEqual(resultado["id_etapa_resultante"], 10)

    def test_preserva_observacoes_inclusive_zero_e_retry(self):
        bloco = bloco_observacoes(1, 2, "Texto do Funil")
        for anterior in ("FR002", "  notas comerciais\n", 0, "0", "", None):
            novo, mudou = acrescentar_observacoes(anterior, bloco)
            self.assertTrue(mudou)
            if anterior is not None:
                self.assertTrue(novo.startswith(str(anterior)))
            self.assertEqual(acrescentar_observacoes(novo, bloco), (novo, False))
        with self.assertRaises(ErroFireAds):
            acrescentar_observacoes(bloco.replace("Texto do Funil", "Editado"), bloco)
        with self.assertRaises(ErroFireAds):
            acrescentar_observacoes("x" * 45000, bloco)

    def test_organico_existente_atualiza_so_observacao(self):
        snap = {
            "telefone": NUMERO,
            "nome": "Ana",
            "email": "ana@example.com",
            "perfil": "Titular",
            "origem": "organico",
        }
        linha = {
            "_row": 2,
            "WhatsApp": NUMERO,
            "Email": "ana@example.com",
            "Observação": "FR002",
        }
        bloco = bloco_observacoes(1, 2, "novo")
        op = preparar_escrita([linha], snap, bloco)
        self.assertEqual(set(op), {"row", "observacoes"})
        self.assertEqual(op["observacoes"], "FR002\n\n" + bloco)
        self.assertIsNone(
            preparar_escrita(
                [dict(linha, **{"Observação": op["observacoes"]})], snap, bloco
            )
        )

    def test_organico_novo_nao_envia_data_e_identidade_ambigua_nao_escreve(self):
        snap = {
            "telefone": NUMERO,
            "nome": "Ana",
            "email": "ana@example.com",
            "perfil": "Titular",
            "origem": "organico",
        }
        bloco = bloco_observacoes(1, 2, "novo")
        self.assertNotIn("Data/Hora", preparar_escrita([], snap, bloco)["dados"])
        for linhas in (
            [{"_row": 2, "WhatsApp": NUMERO, "Email": "outra@example.com"}],
            [{"_row": 2, "WhatsApp": NUMERO}, {"_row": 3, "WhatsApp": NUMERO}],
            [{"_row": 2, "WhatsApp": "5511999990003", "Email": snap["email"]}],
        ):
            with self.assertRaises(ErroFireAds):
                preparar_escrita(linhas, snap, bloco)

    def test_exec_e_redirect_sem_repetir_post(self):
        session = Mock()
        redirect = Mock(
            status_code=302,
            headers={
                "Location": "https://script.googleusercontent.com/macros/echo?x=1"
            },
        )
        resposta = Mock(status_code=200)
        resposta.json.return_value = {"success": True, "aba": "geral", "inserted": 1}
        session.request.side_effect = [redirect, resposta]
        cli = ClienteFireAds(
            "https://script.google.com/macros/s/teste/exec", session=session
        )
        cli.enviar("geral", dados={"Nome": "Teste"})
        self.assertEqual(
            [c.args[0] for c in session.request.call_args_list], ["POST", "GET"]
        )
        with self.assertRaises(ErroFireAds):
            validar_url("https://script.google.com/u/0/home/projects/teste/edit")
        session.request.side_effect = None
        resposta.json.return_value = {"success": False, "error": "recusado"}
        session.request.return_value = resposta
        with self.assertRaises(ErroFireAds):
            cli.enviar("geral", dados={"Nome": "Teste"})

    def test_retry_recupera_decisao_sem_consultar_api(self):
        cx = {"conversa": {"id_conversa": 2, "id_etapa_atual": None}}
        with patch(
            "workers.worker_flow.fireads.buscar_abertura",
            return_value={"contexto": estado()},
        ), patch("workers.worker_flow.fireads.ClienteFireAds") as api:
            retomado = preparar_abertura(cx, {}, 1, FakeConn(), FakeCursor())
            self.assertEqual(retomado["contexto_fireads"]["origem"], "google")
            api.assert_not_called()

    def test_segunda_fonte_falha_importa_nada(self):
        import workers.worker_flow.fireads as servico

        abertura = {
            "contexto": None,
            "etapa": None,
            "aplicavel": True,
            "url": "https://script.google.com/macros/s/teste/exec",
            "aba_google": "google",
            "aba_meta": "meta",
            "fuso": None,
        }
        api = Mock()
        api.consultar.side_effect = [
            {"headers": list(GOOGLE), "rows": [GOOGLE]},
            RuntimeError("falha"),
        ]
        conn = FakeConn()
        cursor = FakeCursor(fetchone_result=(1,))
        with patch.object(
            servico, "buscar_abertura", return_value=abertura
        ), patch.object(servico, "reservar_consulta", return_value=1), patch.object(
            servico, "proteger_conversa"
        ), patch.object(
            servico, "ClienteFireAds", return_value=api
        ), patch.object(
            servico, "concluir_consulta", side_effect=lambda a, c, i, d, cur: d
        ):
            cx = preparar_abertura(
                {"conversa": {"id_conversa": 2, "id_etapa_atual": None}},
                {"id_mensagem": 1, "retry_count": 1, "cliente_telefone": NUMERO},
                1,
                conn,
                cursor,
            )
        self.assertEqual(cx["contexto_fireads"]["origem"], "organico")
        self.assertFalse(any("UPDATE chatbot.cliente" in q for q, _ in cursor.calls))
```

## Passo 42 — Substituir integralmente `tests/unit/test_fluxo_reserva_link.py`

```python
"""Caminhos com/sem link e recuperação sem efeitos duplicados ou envios reais."""

import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from urllib.parse import parse_qs, urlparse

from django.core.exceptions import ValidationError
from webhook.models import Unidade, AtendimentoCustomizado
from core.database.deploy_database.etapa_transicao_script import (
    TRANSICOES_INICIAIS as TRANSICOES,
)
from core.database.deploy_database.povoar_etapas import ETAPAS
from core.integrations.whatsapp.pywa_functions import cliente
from core.integrations.whatsapp.messages.contato_comercial import (
    montar_mensagem_contato_comercial,
)
from core.integrations.whatsapp.numero_comercial import (
    montar_link_numero_comercial_whatsapp,
)
from core.integrations.funil.oportunidades import montar_observacoes_lead
from core.repositories.atendimento.turnos import salvar_turno_conversa
from core.repositories.fluxo.contextos.etapa18 import buscar_contexto_etapa18
from workers.worker_flow.response_flow.etapas import (
    resolver_etapa17,
    resolver_etapa18,
    resolver_etapa19,
)
from workers.worker_flow.response_flow.etapas.validadores_contexto.valida_etapa18 import (
    validar_etapa18,
)
from workers.worker_flow.response_flow.flow_sender import flow_sender
from workers.worker_flow.response_flow.repeticao_followup import (
    enviar_repeticao_followup,
)
from workers.worker_flow.transacoes import efeitos_transicao as efeitos
from tests.unit.test_followup import contexto as contexto_followup
from tests.unit.test_suporte_idoso_email_obrigatorio import dados_lead


def contexto(etapa, texto, *, link=None, dependente=False):
    return {
        "id_conversa": 10,
        "id_unidade": 2,
        "id_cliente": 3,
        "id_etapa_atual": etapa,
        "id_etapa_cliente": etapa,
        "id_etapa_origem_transicao": etapa,
        "retry_count": 1,
        "transicoes_permitidas": {
            evento: destino for origem, evento, destino in TRANSICOES if origem == etapa
        },
        "texto_cliente_atual": texto,
        "tipo_mensagem_atual": "text",
        "status_dependente": dependente,
        "nome_cliente": "Ana",
        "nome_dependente": "João" if dependente else None,
        "idade_cliente": 40,
        "idade_dependente": 12 if dependente else None,
        "idade_pessoa_triagem": 12 if dependente else 40,
        "nome_agente_unidade": "Suh",
        "genero_agente_unidade": "feminino",
        "numero_comercial_unidade": "5571999999999",
        "link_agendamento_unidade": link,
        "turno": "manha",
        "resposta_bot_para_mensagem_atual": None,
        "mensagem_cliente_atual": {
            "id_mensagem": 9,
            "id_mensagem_fila": 8,
            "id_hash_msg": "wamid.cliente",
            "cliente_telefone": "5571888888888",
            "id_phone_unidade": "phone",
        },
    }


class TurnoTests(unittest.TestCase):
    def test_opcoes_e_frases_com_um_turno(self):
        for texto, esperado in (
            ("Pela manhã", "manha"),
            ("Posso pela manha", "manha"),
            ("amanhã pela tarde", "tarde"),
            ("somente pela noite", "noite"),
            ("manhã, prefiro manhã", "manha"),
            ("pela TARDE", "tarde"),
        ):
            for tipo in ("text", "interactive", "interactive_button"):
                with self.subTest(texto=texto, tipo=tipo):
                    self.assertEqual(validar_etapa18(texto, tipo), esperado)

    def test_negações_multiplos_turnos_e_ausencia_nao_passam(self):
        for texto in (
            "",
            "amanhã",
            "Sim",
            "manhã ou tarde",
            "tarde e noite",
            "manhã tarde noite",
            "não posso de manhã",
            "nao pela noite",
            "n posso a tarde",
            "nunca à tarde",
            "qualquer turno",
            "talvez de manhã",
            "tem horário pela manhã?",
            "sem manhã",
        ):
            with self.subTest(texto=texto):
                self.assertIsNone(validar_etapa18(texto))
        self.assertIsNone(validar_etapa18("Pela manhã", "audio"))

    def test_unidade_sem_link_exige_contato_e_normaliza_vazio(self):
        for link in (None, "", "   "):
            unidade = AtendimentoCustomizado(link_agendamento=link, numero_comercial="(71) 99999-9999")
            unidade.clean()
            self.assertIsNone(unidade.link_agendamento)
            unidade.numero_comercial = None
            with self.assertRaises(ValidationError):
                unidade.clean()

    def test_repositorio_restringe_conversa_unidade_e_turno(self):
        cursor = MagicMock()
        cursor.fetchone.return_value = ("manha",)
        self.assertEqual(
            salvar_turno_conversa(10, 2, "manha", cursor)["turno"], "manha"
        )
        self.assertEqual(cursor.execute.call_args.args[1], ("manha", 10, 2, "manha"))
        cursor.fetchone.return_value = None
        with self.assertRaises(ValueError):
            salvar_turno_conversa(10, 2, "tarde", cursor)
        for invalido in (None, "manhã", "manha,tarde", "", "outro"):
            with self.subTest(invalido=invalido), self.assertRaises(ValueError):
                salvar_turno_conversa(10, 2, invalido, cursor)

    def test_contexto_usa_unidade_atual_e_nao_cache(self):
        cursor = MagicMock()
        cursor.fetchone.return_value = (
            None,
            "5571999999999",
            "Suh",
            "feminino",
            "Ana",
            40,
            None,
            None,
            False,
            None,
        )
        sem = buscar_contexto_etapa18(10, 2, cursor)
        self.assertIsNone(sem["link_agendamento_unidade"])
        cursor.fetchone.return_value = (
            "https://example.com",
            *cursor.fetchone.return_value[1:],
        )
        com = buscar_contexto_etapa18(10, 2, cursor)
        self.assertEqual(com["link_agendamento_unidade"], "https://example.com")
        self.assertEqual(cursor.execute.call_args.args[1], (10, 2))


class FluxoReservaTests(unittest.TestCase):
    def setUp(self):
        self.http = MagicMock()
        self.http.send_message.return_value = SimpleNamespace(id="wamid.bot")
        p = patch.object(cliente, "WhatsApp", return_value=self.http)
        p.start()
        self.addCleanup(p.stop)

    def test_rotas_17_preservam_sexta_resposta(self):
        for dependente in (False, True):
            for link, destino in ((None, 18), ("https://example.com", 20)):
                with self.subTest(dependente=dependente, link=link):
                    ctx = contexto(17, "Nunca", link=link, dependente=dependente)
                    envio = resolver_etapa17.resolve_etapa17(ctx)
                    self.assertEqual(envio["id_etapa_resultante"], destino)
                    self.assertEqual(envio["resposta_triagem"], "nunca")
                    with patch.object(
                        efeitos,
                        "registrar_resposta_triagem",
                        return_value={"inserido": True},
                    ) as salvar:
                        efeitos.atualizar_banco_conforme_transicao_de_etapa(
                            ctx, envio, object()
                        )
                        self.assertEqual(salvar.call_args.args[:3], (10, 17, "nunca"))

    def test_etapa18_so_transita_depois_de_uma_escolha(self):
        for dependente in (False, True):
            for texto, turno in (
                ("Pela manhã", "manha"),
                ("Posso pela tarde", "tarde"),
                ("pela noite", "noite"),
            ):
                ctx = contexto(18, texto, dependente=dependente)
                envio = resolver_etapa18.resolve_etapa18(ctx)
                self.assertEqual(envio["id_etapa_resultante"], 19)
                self.assertEqual(envio["turno"], turno)
                botao = self.http.send_message.call_args.kwargs["buttons"]
                pretexto = parse_qs(urlparse(botao.url).query)["text"][0]
                self.assertIn(
                    "João, que tem 12 anos" if dependente else "tenho 40 anos", pretexto
                )
                self.assertIn("turno da ", pretexto)
                self.assertIn("*experiência Supera*", envio["mensagem_bot"])
                self.assertNotIn("por cortesia da unidade", envio["mensagem_bot"])
                self.assertNotIn("por cortesia da unidade", pretexto)

    def test_tratamentos_permanecem_na18_sem_efeito(self):
        for texto, tipo, tratamento in (
            ("manha e tarde", "text", "contexto_invalido"),
            ("Pela manhã ou pela noite", "interactive", "contexto_invalido"),
            ("Talvez pela tarde", "interactive_button", "contexto_invalido"),
            ("Eu trabalho à tarde", "text", "contexto_invalido"),
            ("Não sei", "text", "contexto_invalido"),
            ("Pela manhã", "audio", "midia"),
            ("quanto custa?", "text", "financeiro"),
            ("vocês fazem reforço escolar?", "text", "reforco_escolar"),
        ):
            ctx = contexto(18, texto)
            ctx["tipo_mensagem_atual"] = tipo
            envio = resolver_etapa18.resolve_etapa18(ctx)
            self.assertEqual(envio["id_etapa_resultante"], 18)
            self.assertEqual(envio["tipo_tratamento"], tratamento)
            self.assertNotIn("evento_transicao", envio)
            self.assertNotIn("turno", envio)
            if tratamento == "contexto_invalido":
                self.assertIn("Para continuar, escolha apenas um turno.", envio["mensagem_bot"])
            with patch.object(efeitos, "salvar_turno_conversa") as salvar:
                efeitos.atualizar_banco_conforme_transicao_de_etapa(
                    ctx, envio, object()
                )
                salvar.assert_not_called()

    def test_19_apresenta_pergunta_sem_consumir_nota(self):
        for texto in ("oi", "5", "não", "quanto custa?"):
            ctx = contexto(19, texto)
            envio = resolver_etapa19.resolve_etapa19(ctx)
            self.assertEqual(envio["id_etapa_resultante"], 21)
            self.assertNotIn("nota_satisfacao", envio)
            with patch.object(efeitos, "salvar_nota_satisfacao") as salvar:
                efeitos.atualizar_banco_conforme_transicao_de_etapa(
                    ctx, envio, object()
                )
                salvar.assert_not_called()

    def test_link_adicionado_nao_redireciona_quem_ja_chegou18_ou19(self):
        envio = resolver_etapa18.resolve_etapa18(
            contexto(18, "manhã", link="https://example.com")
        )
        self.assertEqual(envio["id_etapa_resultante"], 19)
        envio = resolver_etapa19.resolve_etapa19(
            contexto(19, "ok", link="https://example.com")
        )
        self.assertEqual(envio["id_etapa_resultante"], 21)

    def test_replay_reconstroi_turno_sem_novo_envio(self):
        ctx = contexto(18, "Posso pela noite")
        ctx["resposta_bot_para_mensagem_atual"] = {
            "id_etapa": 19,
            "id_hash_msg": "wamid.persistido",
        }
        envio = flow_sender(ctx)
        self.http.send_message.assert_not_called()
        self.assertEqual(envio["evento_transicao"], "turno_escolhido")
        cursor = MagicMock()
        cursor.fetchone.return_value = ("noite",)
        efeito = efeitos.atualizar_banco_conforme_transicao_de_etapa(ctx, envio, cursor)
        self.assertEqual(efeito["turno"], "noite")

    def test_replay_de_botao_reconstroi_preferencia_sem_reenviar(self):
        for tipo in ("interactive", "interactive_button"):
            for texto, turno in (("Pela manhã", "manha"), ("Pela tarde", "tarde"), ("Pela noite", "noite")):
                with self.subTest(tipo=tipo, texto=texto):
                    ctx = contexto(18, texto)
                    ctx["tipo_mensagem_atual"] = tipo
                    ctx["resposta_bot_para_mensagem_atual"] = {
                        "id_etapa": 19, "id_hash_msg": "wamid.persistido",
                    }
                    envio = flow_sender(ctx)
                    self.http.send_message.assert_not_called()
                    cursor = MagicMock()
                    cursor.fetchone.return_value = (turno,)
                    efeito = efeitos.atualizar_banco_conforme_transicao_de_etapa(ctx, envio, cursor)
                    self.assertEqual(efeito["turno"], turno)

    def test_tipos_interativos_equivalentes_nas_outras_etapas_com_botoes(self):
        for tipo in ("interactive", "interactive_button"):
            for etapa, texto, destino in (
                (3, "Não", 4), (11, "Começar triagem", 12), (12, "Nunca", 13),
                (17, "Nunca", 18), (19, "ok", 21), (20, "Já reservei", 21),
                (21, "5", 22), (22, "Sim", 23), (22, "Não", 24),
            ):
                with self.subTest(tipo=tipo, etapa=etapa):
                    ctx = contexto(etapa, texto, link="https://example.com" if etapa == 20 else None)
                    ctx["tipo_mensagem_atual"] = tipo
                    envio = flow_sender(ctx)
                    self.assertEqual(envio["id_etapa_resultante"], destino)

    def test_replay17_respeita_resposta_ja_enviada_apos_adicao_link(self):
        ctx = contexto(17, "Nunca", link="https://example.com")
        ctx["resposta_bot_para_mensagem_atual"] = {
            "id_etapa": 18,
            "id_hash_msg": "wamid.persistido",
        }
        envio = flow_sender(ctx)
        self.assertEqual(envio["evento_transicao"], "triagem_concluida_sem_link")
        self.http.send_message.assert_not_called()

    def test_followup18_valida_escolha_e_avanca_sem_perder_prefixo(self):
        from workers.worker_flow.response_flow.retomada_followup import enviar_retorno_followup

        ctx = contexto(18, "Pela manhã")
        ctx["retorno_followup"] = True
        ctx["dados_repeticao"] = contexto_followup()["dados_repeticao"]
        envio = enviar_retorno_followup(ctx)
        self.assertEqual(envio["id_etapa_resultante"], 19)
        self.assertEqual(envio["turno"], "manha")
        self.assertEqual(envio["evento_transicao"], "turno_escolhido")
        self.assertIn("Bom te ver novamente", envio["mensagem_bot"])
        with patch.object(efeitos, "salvar_turno_conversa") as salvar:
            efeitos.atualizar_banco_conforme_transicao_de_etapa(ctx, envio, object())
        salvar.assert_called_once()

    def test_followup18_invalido_apenas_repete(self):
        from workers.worker_flow.response_flow.retomada_followup import enviar_retorno_followup

        ctx = contexto(18, "qualquer horário")
        ctx["retorno_followup"] = True
        ctx["dados_repeticao"] = contexto_followup()["dados_repeticao"]
        envio = enviar_retorno_followup(ctx)
        self.assertEqual(envio["id_etapa_resultante"], 18)
        self.assertNotIn("turno", envio)
        self.assertNotIn("evento_transicao", envio)
        self.assertIn("Bom te ver novamente", envio["mensagem_bot"])

    def test_midia19_repete_contato_sem_entrar_na_pesquisa(self):
        ctx = contexto(19, "", dependente=True)
        ctx["tipo_mensagem_atual"] = "audio"
        envio = resolver_etapa19.resolve_etapa19(ctx)
        self.assertEqual(envio["id_etapa_resultante"], 19)
        self.assertNotIn("evento_transicao", envio)
        self.assertIn("apenas texto", envio["mensagem_bot"])
        botao = self.http.send_message.call_args.kwargs["buttons"]
        mensagem = parse_qs(urlparse(botao.url).query)["text"][0]
        self.assertIn("João, que tem 12 anos", mensagem)
        self.assertIn("turno da manhã", mensagem)

    def test_pesquisa_compartilhada_ate_final24_com_e_sem_comentario(self):
        for etapa, resposta, destino, evento in (
            (20, "Já reservei", 21, "agendamento_confirmado"),
            (21, "5", 22, "satisfacao_avaliada"),
            (22, "Sim", 23, "comentario_satisfacao_aceito"),
            (22, "Não", 24, "comentario_satisfacao_recusado"),
            (23, "Gostei muito do atendimento", 24, "comentario_satisfacao_recebido"),
        ):
            with self.subTest(etapa=etapa, resposta=resposta):
                envio = flow_sender(
                    contexto(etapa, resposta, link="https://example.com")
                )
                self.assertEqual(envio["id_etapa_resultante"], destino)
                self.assertEqual(envio["evento_transicao"], evento)

    def test_catalogo_e_transicoes_finais(self):
        self.assertEqual([e[0] for e in ETAPAS], list(range(1, 25)))
        self.assertEqual([(e[0], e[3]) for e in ETAPAS if e[2]], [(24, 30)])
        self.assertFalse(next(e for e in ETAPAS if e[0] == 18)[4])
        self.assertIn((17, "triagem_concluida_sem_link", 18), TRANSICOES)
        self.assertIn((17, "triagem_pergunta_6_respondida", 20), TRANSICOES)
        self.assertIn((18, "turno_escolhido", 19), TRANSICOES)
        self.assertIn((19, "avaliacao_solicitada", 21), TRANSICOES)
        self.assertEqual(len({(a, b) for a, b, c in TRANSICOES}), len(TRANSICOES))
        self.assertEqual(len({(a, c) for a, b, c in TRANSICOES}), len(TRANSICOES))


class ContatoComercialTests(unittest.TestCase):
    def test_texto_e_url_preservam_nome_idade_e_turno_unico(self):
        for genero, artigo in (("feminino", "a"), ("masculino", "o")):
            texto = montar_mensagem_contato_comercial(
                nome_agente="Bot",
                genero_agente=genero,
                nome_cliente="Ana & João",
                idade_aluno=40,
                turno="manha",
            )
            self.assertIn(f"com {artigo} Bot", texto)
            url = montar_link_numero_comercial_whatsapp("(71) 99999-9999", texto)
            self.assertEqual(parse_qs(urlparse(url).query)["text"], [texto])
            self.assertTrue(url.startswith("https://wa.me/5571999999999?text="))

    def test_encaminhamento_por_idade_nao_inventa_turno(self):
        texto = montar_mensagem_contato_comercial(
            nome_agente="Suh",
            genero_agente="feminino",
            nome_cliente="Ana",
            idade_aluno=100,
            nome_dependente="Maria",
        )
        self.assertIn("Maria, que tem 100 anos", texto)
        self.assertNotIn("turno", texto)

    def test_funil_orienta_conforme_configuracao_vigente(self):
        for link in (None, "https://example.com"):
            lead = dados_lead(resposta_email="sem email")
            lead.update(link_agendamento=link, turno="tarde")
            texto = montar_observacoes_lead(lead)
            self.assertIn("painel de monitoramento", texto)
            self.assertIn("Turno de preferência: tarde", texto)
            if link:
                self.assertIn("Calendly", texto)
            else:
                self.assertIn("número comercial", texto)
                self.assertNotIn("Calendly", texto)
```

## Passo 43 — Substituir integralmente `tests/unit/test_monitoramento_unidade.py`

```python
import re
import sqlite3
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import OperationalError, models

from core.repositories.monitoramento.acessos import buscar_acesso_monitoramento
from monitoramento import monitoramento_guard
from webhook.models import Unidade


RAIZ = Path(__file__).resolve().parents[2]


class CursorMonitoramentoSQLite:
    """Executa o SQL real de autorizacao, adaptando somente os placeholders."""

    def __init__(self, banco):
        self.cursor = banco.cursor()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.cursor.close()

    def execute(self, sql, parametros):
        self.cursor.execute(sql.replace('%s', '?'), parametros)

    def fetchone(self):
        return self.cursor.fetchone()


def usuario(id_usuario=1, **campos):
    valores = {
        'pk': id_usuario, 'is_authenticated': True, 'is_active': True,
        'is_staff': False, 'is_superuser': False,
    }
    valores.update(campos)
    return SimpleNamespace(**valores)


class IsolamentoMonitoramentoTests(unittest.TestCase):
    def setUp(self):
        self.banco = sqlite3.connect(':memory:')
        self.addCleanup(self.banco.close)
        self.banco.executescript("""
            PRAGMA foreign_keys = ON;
            ATTACH DATABASE ':memory:' AS chatbot;
            CREATE TABLE chatbot.auth_user (
                id INTEGER PRIMARY KEY, is_active BOOLEAN,
                is_staff BOOLEAN, is_superuser BOOLEAN
            );
            CREATE TABLE chatbot.unidade (
                id_unidade INTEGER PRIMARY KEY, nome_unidade TEXT,
                id_usuario_monitoramento INTEGER NULL UNIQUE
                    REFERENCES auth_user(id) ON DELETE SET NULL
            );
            CREATE TABLE chatbot.conversa (
                id_conversa INTEGER PRIMARY KEY, id_unidade INTEGER,
                id_cliente INTEGER
            );
            CREATE TABLE chatbot.historico_mensagens (
                id_mensagem INTEGER PRIMARY KEY, id_conversa INTEGER
            );
            INSERT INTO chatbot.auth_user VALUES
                (1, TRUE, FALSE, FALSE), (2, TRUE, FALSE, FALSE),
                (3, TRUE, FALSE, FALSE), (4, FALSE, FALSE, FALSE),
                (5, TRUE, TRUE, FALSE), (6, TRUE, TRUE, TRUE);
            INSERT INTO chatbot.unidade VALUES
                (10, 'Unidade A', 1), (20, 'Unidade B', 2), (30, 'Unidade C', NULL),
                (40, 'Unidade D', 4), (50, 'Unidade E', 5), (60, 'Unidade F', 6),
                (70, 'Unidade G', NULL);
            -- O mesmo cliente global 7 conversou nas unidades A e B.
            INSERT INTO chatbot.conversa VALUES
                (101, 10, 7), (102, 20, 7), (103, 10, 8), (303, 30, 7);
            INSERT INTO chatbot.historico_mensagens VALUES
                (1001, 101), (1002, 102), (1003, 103);
        """)
        self.conexao = SimpleNamespace(cursor=lambda: CursorMonitoramentoSQLite(self.banco))
        self.patch_conexao = patch.object(monitoramento_guard, 'connection', self.conexao)
        self.patch_conexao.start()
        self.addCleanup(self.patch_conexao.stop)

    def exigir(self, id_usuario=1, **recursos):
        return monitoramento_guard.exigir_acesso_monitoramento(
            SimpleNamespace(user=usuario(id_usuario)), **recursos,
        )

    def test_cada_conta_resolve_somente_sua_unidade(self):
        self.assertEqual(self.exigir(1).id_unidade, 10)
        self.assertEqual(self.exigir(2).id_unidade, 20)

    def test_mesmo_cliente_em_duas_unidades_nao_libera_outra_conversa(self):
        self.assertEqual(self.exigir(1, id_conversa=101).id_unidade, 10)
        self.assertEqual(self.exigir(2, id_conversa=102).id_unidade, 20)
        for conta, conversa in ((1, 102), (2, 101)):
            with self.subTest(conta=conta), self.assertRaises(PermissionDenied):
                self.exigir(conta, id_conversa=conversa)

    def test_mensagem_exige_unidade_e_conversa_corretas(self):
        self.assertEqual(self.exigir(id_mensagem=1001).id_unidade, 10)
        self.assertEqual(self.exigir(id_conversa=101, id_mensagem=1001).id_unidade, 10)
        for recursos in (
            {'id_mensagem': 1002},
            {'id_conversa': 101, 'id_mensagem': 1002},
            {'id_conversa': 101, 'id_mensagem': 1003},
        ):
            with self.subTest(recursos=recursos), self.assertRaises(PermissionDenied):
                self.exigir(**recursos)

    def test_recurso_inexistente_e_de_outra_unidade_tem_mesma_resposta(self):
        respostas = []
        for conversa in (102, 9999):
            with self.assertRaises(PermissionDenied) as erro:
                self.exigir(id_conversa=conversa)
            respostas.append(str(erro.exception))
        self.assertEqual(respostas[0], respostas[1])

    def test_sem_vinculo_inativo_staff_ou_superusuario_nao_tem_acesso(self):
        # A sessao ainda parece ativa/comum; o banco e autoritativo.
        for conta in (3, 4, 5, 6, 999):
            with self.subTest(conta=conta), self.assertRaises(PermissionDenied):
                self.exigir(conta)

    def test_revogacao_e_reassociacao_nao_reutilizam_vinculo_antigo(self):
        self.assertEqual(self.exigir().id_unidade, 10)
        self.banco.execute(
            'UPDATE chatbot.unidade SET id_usuario_monitoramento = NULL WHERE id_unidade = 10',
        )
        self.banco.execute(
            'UPDATE chatbot.unidade SET id_usuario_monitoramento = 1 WHERE id_unidade = 30',
        )
        with self.assertRaises(PermissionDenied):
            self.exigir(id_conversa=101)
        self.assertEqual(self.exigir(id_conversa=303).id_unidade, 30)
        self.banco.execute(
            'UPDATE chatbot.unidade SET id_usuario_monitoramento = NULL WHERE id_unidade = 30',
        )
        with self.assertRaises(PermissionDenied):
            self.exigir()

    def test_varias_unidades_sem_conta_e_usuario_exclusivo_de_uma_unidade(self):
        sem_conta = self.banco.execute(
            'SELECT COUNT(*) FROM chatbot.unidade WHERE id_usuario_monitoramento IS NULL',
        ).fetchone()[0]
        self.assertEqual(sem_conta, 2)
        with self.assertRaises(sqlite3.IntegrityError):
            self.banco.execute(
                'UPDATE chatbot.unidade SET id_usuario_monitoramento = 1 WHERE id_unidade = 20',
            )
        self.assertEqual(self.exigir(1).id_unidade, 10)
        self.assertEqual(self.exigir(2).id_unidade, 20)

    def test_excluir_conta_limpa_vinculo_e_preserva_unidade_e_atendimentos(self):
        self.banco.execute('DELETE FROM chatbot.auth_user WHERE id = 1')
        self.assertEqual(
            self.banco.execute(
                'SELECT id_usuario_monitoramento FROM chatbot.unidade WHERE id_unidade = 10',
            ).fetchone(),
            (None,),
        )
        self.assertEqual(
            self.banco.execute('SELECT COUNT(*) FROM chatbot.conversa WHERE id_conversa = 101').fetchone()[0],
            1,
        )
        self.assertEqual(
            self.banco.execute('SELECT COUNT(*) FROM chatbot.historico_mensagens WHERE id_mensagem = 1001').fetchone()[0],
            1,
        )
        with self.assertRaises(PermissionDenied):
            self.exigir()

    def test_desativacao_da_conta_e_consultada_novamente(self):
        self.exigir()
        self.banco.execute('UPDATE chatbot.auth_user SET is_active = FALSE WHERE id = 1')
        with self.assertRaises(PermissionDenied):
            self.exigir()

    def test_identidade_e_unidade_enviadas_pelo_cliente_sao_ignoradas(self):
        request = SimpleNamespace(
            user=usuario(1), GET={'id_usuario': '2', 'id_unidade': '20'},
            POST={'id_usuario': '2', 'id_unidade': '20'},
        )
        acesso = monitoramento_guard.exigir_acesso_monitoramento(request)
        self.assertEqual((acesso.id_usuario, acesso.id_unidade), (1, 10))

    def test_identificadores_invalidos_sao_negados(self):
        for valor in (0, -1, True, '101', '101 OR 1=1'):
            with self.subTest(valor=valor), self.assertRaises(PermissionDenied):
                self.exigir(id_conversa=valor)
        with CursorMonitoramentoSQLite(self.banco) as cursor:
            self.assertIsNone(buscar_acesso_monitoramento(None, cursor))

    def test_sessao_ausente_ou_inapta_e_negada_antes_do_banco(self):
        sessoes = (
            None, AnonymousUser(), usuario(is_active=False),
            usuario(is_staff=True), usuario(is_superuser=True), usuario(None),
        )
        with patch.object(self.conexao, 'cursor') as abrir_cursor:
            for sessao in sessoes:
                with self.subTest(sessao=sessao), self.assertRaises(PermissionDenied):
                    monitoramento_guard.exigir_acesso_monitoramento(
                        SimpleNamespace(user=sessao),
                    )
            abrir_cursor.assert_not_called()

    def test_erro_do_banco_nao_libera_acesso(self):
        with patch.object(self.conexao, 'cursor', side_effect=OperationalError('indisponivel')):
            with self.assertRaises(OperationalError):
                self.exigir()


class CadastroMonitoramentoTests(unittest.TestCase):
    def test_modelo_valida_conta_comum_e_rejeita_contas_administrativas(self):
        User = get_user_model()
        cadastro = Unidade(
            id_unidade=10, nome_unidade='Unidade A',
            id_usuario_monitoramento=User(id=1, username='unidade_a'),
        )
        cadastro.clean()
        self.assertEqual(str(cadastro), 'Unidade A')
        for flags in ({'is_staff': True}, {'is_superuser': True}):
            cadastro.id_usuario_monitoramento = User(id=2, username='administrativo', **flags)
            with self.subTest(flags=flags), self.assertRaises(ValidationError):
                cadastro.clean()

    def test_unidade_sem_conta_e_permitida(self):
        unidade = Unidade(id_unidade=10, nome_unidade='Unidade A')
        unidade.clean()
        self.assertIsNone(unidade.id_usuario_monitoramento_id)

    def test_relacao_opcional_e_campo_disponivel_no_admin_da_unidade(self):
        campo = Unidade._meta.get_field('id_usuario_monitoramento')
        self.assertTrue(campo.one_to_one)
        self.assertTrue(campo.null)
        self.assertTrue(campo.blank)
        self.assertIs(campo.remote_field.on_delete, models.SET_NULL)
        self.assertFalse(Unidade._meta.managed)
        self.assertNotIn(
            'unidade_monitoramento',
            {modelo._meta.db_table for modelo in admin.site._registry},
        )
        unidade_admin = admin.site._registry[Unidade]
        form = unidade_admin.get_form(
            SimpleNamespace(user=get_user_model()(is_active=True, is_staff=True, is_superuser=True)),
            obj=Unidade(id_unidade=10), change=True,
        )
        self.assertFalse(form.base_fields['id_usuario_monitoramento'].required)
        conta = get_user_model()(is_active=True, is_staff=False)
        self.assertFalse(admin.site.has_permission(SimpleNamespace(user=conta)))

    def test_ddl_final_e_migracao_tem_os_mesmos_contratos_da_coluna(self):
        ddl = (RAIZ / 'core/database/deploy_database/bank_script.py').read_text(encoding='utf-8')
        migracao = (
            RAIZ / 'deploy/migrations/20260902_adicionar_usuario_monitoramento_unidade.sql'
        ).read_text(encoding='utf-8')
        padroes = (
            r'id_usuario_monitoramento INT NULL',
            r'CONSTRAINT uq_unidade_usuario_monitoramento\s+UNIQUE\s*\(id_usuario_monitoramento\)',
            r'CONSTRAINT unidade_id_usuario_monitoramento_fkey\s+FOREIGN KEY\s*\(id_usuario_monitoramento\)\s+REFERENCES chatbot.auth_user\(id\)\s+ON DELETE SET NULL',
        )
        for padrao in padroes:
            contratos = [re.search(padrao, texto).group(0) for texto in (ddl, migracao)]
            self.assertEqual(' '.join(contratos[0].split()), ' '.join(contratos[1].split()))
        self.assertNotIn('ALTER TABLE', ddl.upper())
        self.assertNotRegex(ddl, r'CREATE TABLE (?:IF NOT EXISTS )?chatbot\.unidade_monitoramento')
        self.assertFalse((RAIZ / 'deploy/migrations/20260902_criar_unidade_monitoramento.sql').exists())


if __name__ == '__main__':
    unittest.main()
```

## Passo 44 — Substituir integralmente `tests/unit/test_suporte_por_idade.py`

```python
"""Fronteiras da política, recuperação atual e encaminhamentos registrados."""

from contextlib import ExitStack
from datetime import datetime, timedelta, timezone
import sqlite3
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch
from urllib.parse import parse_qs, urlsplit

from django.contrib.admin.sites import AdminSite
from django.test import RequestFactory
from core.validacoes.suporte_por_idade import validar_idade_minima_suporte
from core.repositories.fluxo.contextos.etapa6 import buscar_contexto_etapa6
from core.repositories.monitoramento import painel as repositorio
from core.integrations.whatsapp.messages.etapa6_messages import montar_mensagem_suporte_idoso_etapa6
from core.integrations.whatsapp.pywa_functions.pywa_senders import etapa6 as sender
from monitoramento import services
from monitoramento.apresentacao import classificar_faixa
from monitoramento.encerramentos import montar_tabela_encerramentos
from monitoramento.periodos import PERIODOS, resolver_periodo
from webhook.admin import UnidadeAdmin, AtendimentoCustomizadoAdmin
from webhook.models import Unidade, AtendimentoCustomizado
from tests.helpers import FakeCursor
from tests.unit.test_suporte_idoso_email_obrigatorio import contexto_etapa6, contexto_envio
from workers.worker_flow.response_flow.etapas import resolver_etapa6
from workers.worker_flow.transacoes import efeitos_transicao, encerramento_atendimento


LIMITES = (None, 50, 60, 70, 80)

# Amostra independente do catálogo atual: a produção ainda pode enviar esse texto.
MENSAGEM_LEGADA_SEM_FAIXA = (
    'Certo, olha, para idades mais avançadas oferecemos um atendimento '
    'personalizado com o nosso time! 😊\n\n'
    'Para entrar em contato, basta clicar no botão abaixo.'
)
MENSAGEM_ENCAMINHAMENTO_ATUAL = (
    'Certo, vou te passar o contato da nossa equipe para dar continuidade a sua experiência supera! 😊\n'
    'Para entrar em contato, basta clicar no botão abaixo.'
)
MENSAGEM_ANAMNESE_100_MAIS = (
    'Certo, olha, para idades mais avançadas vamos precisar realizar uma pequena '
    '*anamnese* com um dos nossos consultores.\n'
    'Basta clicar no botão abaixo para falar com nosso time e iniciar a anamnese! 😊\n\n'
    '_Nosso time vai orientar os próximos passos. 🧡_'
)


class SuportePorIdadeTests(unittest.TestCase):
    def test_dominio_contexto_e_formulario_modelo(self):
        campo = AtendimentoCustomizado._meta.get_field('idade_minima_suporte')
        for limite in LIMITES:
            with self.subTest(limite=limite):
                self.assertEqual(validar_idade_minima_suporte(limite), limite)
                self.assertEqual(campo.clean(limite, AtendimentoCustomizado()), limite)
                contexto = buscar_contexto_etapa6(10, 1, FakeCursor(
                    fetchone_result=('5571999999999', False, limite, 'Maria', None, 'Suh', 'feminino', 'Supera Centro')
                ))
                self.assertEqual(contexto['idade_minima_suporte'], limite)
                self.assertEqual(contexto['nome_agente'], 'Suh')
                self.assertEqual(contexto['genero_agente_unidade'], 'feminino')
                self.assertEqual(contexto['nome_unidade'], 'Supera Centro')
        self.assertEqual(list(campo.formfield().choices), [(None, 'Desativado')] + [
            (idade, f'{idade}+') for idade in LIMITES[1:]
        ])
        for invalido in (True, False, 0, -1, 49, 55, 90, 100, '60', 60.0):
            with self.subTest(invalido=invalido), self.assertRaises(ValueError):
                validar_idade_minima_suporte(invalido)
        with self.assertRaises(ValueError):
            buscar_contexto_etapa6(10, 1, FakeCursor(
                fetchone_result=(None, False, True, None, None, 'Suh', 'feminino', 'Supera Centro')
            ))

    def test_admin_exige_contato_ao_ativar_e_ao_remover_numero(self):
        admin = AtendimentoCustomizadoAdmin(AtendimentoCustomizado, AdminSite())
        request = RequestFactory().get('/admin/')
        request.user = SimpleNamespace(has_perm=lambda *_: True)
        instance = AtendimentoCustomizado(id_customizacao=1, link_agendamento='https://example.com')
        form_class = admin.get_form(request, instance, change=True,
                                    fields=['idade_minima_suporte', 'numero_comercial'])
        for limite in LIMITES:
            for telefone in ('', '123', '(71) 99999-9999'):
                with self.subTest(limite=limite, telefone=telefone):
                    form = form_class(data={
                        'idade_minima_suporte': '' if limite is None else str(limite),
                        'numero_comercial': telefone,
                    }, instance=instance)
                    self.assertEqual(form.is_valid(), telefone == '(71) 99999-9999', form.errors)
                    if telefone != '(71) 99999-9999':
                        self.assertIn('numero_comercial', form.errors)
        for invalido in ('55', '100', 'True'):
            form = form_class(data={'idade_minima_suporte': invalido,
                                    'numero_comercial': '(71) 99999-9999'}, instance=instance)
            self.assertFalse(form.is_valid())

    def test_matriz_titulares_dependentes_e_100_mais(self):
        caminhos = {
            'suporte': 'enviar_etapa6_suporte_idoso',
            'cem': 'enviar_etapa6_idade_acima_99',
            'menor': 'enviar_etapa6_cliente_menor_18',
            'crianca': 'enviar_etapa6_dependente_menor_5',
            'titular': 'enviar_etapa7_cliente',
            'dependente': 'enviar_etapa7_dependente',
        }
        for limite in LIMITES:
            idades = {4, 5, 17, 18, 49, 50, 59, 60, 69, 70, 79, 80, 89, 90, 99, 100, 105}
            for idade in sorted(idades):
                for dependente in (False, True):
                    for bpa in (False, True):
                        contexto = contexto_etapa6(idade, suporte=limite, dependente=dependente)
                        contexto['bpa_ativo_unidade'] = bpa
                        esperado = (
                            'cem' if idade >= 90 else
                            'suporte' if not dependente and limite is not None and idade >= limite else
                            'menor' if not dependente and idade < 18 else
                            'crianca' if dependente and idade < (4 if bpa else 5) else
                            'dependente' if dependente else 'titular'
                        )
                        with self.subTest(limite=limite, idade=idade, dependente=dependente, bpa=bpa), ExitStack() as stack:
                            mocks = {nome: stack.enter_context(patch.object(
                                resolver_etapa6, funcao,
                                return_value=contexto_envio(7 if nome in ('titular', 'dependente') else 6),
                            )) for nome, funcao in caminhos.items()}
                            resultado = resolver_etapa6.resolve_etapa6(contexto)
                            self.assertEqual([n for n,m in mocks.items() if m.called], [esperado])
                            if esperado == 'suporte':
                                self.assertEqual(mocks['suporte'].call_args.args[-1], limite)
                                self.assertEqual(resultado['id_etapa_resultante'], 6)
                                self.assertNotIn('evento_transicao', resultado)
                                self.assertEqual(resultado['idade_aluno'], idade)

    def test_chave_ausente_erro_nao_desativa_silenciosamente(self):
        contexto = contexto_etapa6(65)
        del contexto['idade_minima_suporte']
        with self.assertRaises(KeyError), patch.object(sender, 'conta_wa') as conta:
            resolver_etapa6.resolve_etapa6(contexto)
        conta.assert_not_called()

    def test_encaminhamento_completo_padroniza_faixas_e_preenche_contato(self):
        mensagem_esperada = MENSAGEM_ENCAMINHAMENTO_ATUAL
        for limite in LIMITES[1:]:
            for genero, nome_agente, artigo in (('feminino', 'Mia', 'a'), ('masculino', 'Léo', 'o')):
                with self.subTest(limite=limite, genero=genero), patch.object(sender, 'conta_wa') as conta:
                    conta.return_value.send_message.return_value = SimpleNamespace(id='wamid.teste')
                    contexto = contexto_etapa6(limite + 1, suporte=limite)
                    contexto.update(
                        nome_agente=nome_agente, genero_agente_unidade=genero,
                        nome_titular='Ana & José', idade_cliente=20,
                        nome_unidade='Supera São João & Centro + Sul',
                    )
                    envio = resolver_etapa6.resolve_etapa6(contexto)
                    enviado = conta.return_value.send_message.call_args.kwargs
                    self.assertEqual(enviado['text'], mensagem_esperada)
                    self.assertEqual(enviado['text'], envio['mensagem_bot'])
                    self.assertEqual(enviado['buttons'].title, 'Falar agora')
                    link = urlsplit(enviado['buttons'].url)
                    self.assertEqual((link.scheme, link.netloc, link.path), ('https', 'wa.me', '/5571999999999'))
                    self.assertEqual(parse_qs(link.query), {'text': [
                        f'Olá, vim do atendimento com {artigo} {nome_agente}, '
                        'chatbot da unidade Supera São João & Centro + Sul. '
                        f'Me chamo Ana & José, tenho {limite + 1} anos '
                        'e gostaria de reservar minha experiência Supera.'
                    ]})
                    self.assertEqual(envio['tipo_mensagem'], 'interactive_cta_url')
                    self.assertEqual(envio['motivo_encerramento'], 'encaminhado_suporte_idoso')
                    self.assertEqual(envio['idade_aluno'], limite + 1)
                    conta.return_value.send_message.assert_called_once()
        with self.assertRaises(ValueError):
            montar_mensagem_suporte_idoso_etapa6(None)

    def test_acima_99_encaminha_ambas_rotas_com_anamnese_e_rodape(self):
        for limite in LIMITES:
            for dependente in (False, True):
                with self.subTest(limite=limite, dependente=dependente), patch.object(
                    sender, 'conta_wa'
                ) as conta:
                    conta.return_value.send_message.return_value = SimpleNamespace(id='wamid.cem')
                    contexto = contexto_etapa6(100, suporte=limite, dependente=dependente)
                    # Idades antigas não podem substituir a resposta atual.
                    contexto.update(idade_cliente=40, idade_dependente=70)
                    envio = resolver_etapa6.resolve_etapa6(contexto)
                    enviado = conta.return_value.send_message.call_args.kwargs
                    self.assertEqual(enviado['text'], MENSAGEM_ANAMNESE_100_MAIS)
                    self.assertEqual(enviado['text'], envio['mensagem_bot'])
                    link = urlsplit(enviado['buttons'].url)
                    self.assertEqual((link.scheme, link.netloc, link.path), ('https', 'wa.me', '/5571999999999'))
                    origem = (
                        'Olá, vim do atendimento com a Suh, '
                        'chatbot da unidade Supera Santo Antônio de Jesus. '
                    )
                    pedido = (
                        'Me chamo Maria e gostaria de reservar uma experiência Supera '
                        'para João, que tem 100 anos.'
                        if dependente else
                        'Me chamo Maria, tenho 100 anos '
                        'e gostaria de reservar minha experiência Supera.'
                    )
                    self.assertEqual(parse_qs(link.query), {'text': [origem + pedido]})
                    self.assertEqual(enviado['buttons'].title, 'Falar com Consultor')
                    self.assertEqual(envio['motivo_encerramento'], 'idade_acima_99')
                    self.assertEqual(envio['id_etapa_resultante'], 6)
                    self.assertNotIn('evento_transicao', envio)
                    conta.return_value.send_message.assert_called_once()

                    # A resposta comprovada de 100+ preserva o motivo legado: o corpo
                    # sozinho não prova qual limiar universal era vigente.
                    contexto['resposta_bot_para_mensagem_atual'] = {
                        'tipo_mensagem': 'interactive_cta_url',
                        'conteudo_texto': enviado['text'],
                    }
                    intencao = encerramento_atendimento.resolver_intencao_encerramento(
                        contexto, {'resposta_ja_existia': True}, object()
                    )
                    self.assertEqual(intencao['motivo'], 'idade_acima_99')
                    self.assertEqual(intencao['motivo_encerramento'], 'idade_invalida')
                    self.assertEqual(intencao['bloqueio_dias'], 0)

    def test_dados_ausentes_nao_geram_texto_incorreto_no_botao(self):
        for idade, dependente, suporte in (
            (71, False, 70), (100, False, None), (100, True, None),
        ):
            campos = [
                ('nome_titular', None), ('nome_agente', ''),
                ('genero_agente_unidade', 'desconhecido'), ('nome_unidade', ' '),
            ]
            if dependente:
                campos.append(('nome_dependente', None))
            for campo, valor in campos:
                contexto = contexto_etapa6(idade, suporte=suporte, dependente=dependente)
                contexto[campo] = valor
                with self.subTest(idade=idade, dependente=dependente, campo=campo), patch.object(sender, 'conta_wa') as conta:
                    with self.assertRaises(ValueError):
                        resolver_etapa6.resolve_etapa6(contexto)
                    conta.assert_not_called()

    def test_persistencia_50_a_99_e_encerramento_sem_bloqueio(self):
        for idade in (50, 59, 60, 99):
            contexto = contexto_etapa6(idade, suporte=50)
            envio = contexto_envio(6)
            envio.update(encerrar_atendimento=True, motivo_encerramento='encaminhado_suporte_idoso', idade_aluno=idade, limite_idade_encerramento=50)
            cursor = object()
            with patch.object(efeitos_transicao, 'atualizar_idade_cliente') as salvar:
                efeitos_transicao.atualizar_banco_conforme_transicao_de_etapa(contexto, envio, cursor)
            salvar.assert_called_once_with(5, idade, cursor)
            intencao = encerramento_atendimento.resolver_intencao_encerramento(contexto, envio, cursor)
            self.assertEqual(intencao['bloqueio_dias'], 0)
            self.assertFalse(intencao['excluir_dependente'])

    def test_recuperacao_reconhece_variantes_e_reconstroi_faixa_compativel(self):
        textos = [
            MENSAGEM_LEGADA_SEM_FAIXA,
            # Corpo salvo pela V1.5.2, antes da redução de espaçamento.
            'Certo, vou te passar o contato da nossa equipe para dar continuidade a sua experiência supera! 😊\n\n'
            'Para entrar em contato, basta clicar no botão abaixo.',
            montar_mensagem_suporte_idoso_etapa6(50),
        ]
        for texto_enviado in textos:
            for atual, idade, encerra in ((70, 65, True), (70, 75, True), (None, 95, True), (50, 55, True)):
                contexto = contexto_etapa6(idade, suporte=atual)
                contexto['resposta_bot_para_mensagem_atual'] = {
                    'tipo_mensagem': 'interactive_cta_url',
                    'conteudo_texto': 'Olá novamente, Maria!\n\n' + texto_enviado,
                }
                with self.subTest(texto=texto_enviado, atual=atual, idade=idade):
                    intencao = encerramento_atendimento.resolver_intencao_encerramento(
                        contexto, {'resposta_ja_existia': True, 'id_etapa_resultante': 6}, object()
                    )
                    self.assertEqual(intencao is not None, encerra)
        for texto, tipo in (('Procure o comercial', 'interactive_cta_url'),
                            (montar_mensagem_suporte_idoso_etapa6(50), 'text')):
            contexto['idade_minima_suporte'] = 50
            contexto['resposta_bot_para_mensagem_atual'] = {'tipo_mensagem': tipo, 'conteudo_texto': texto}
            self.assertIsNone(encerramento_atendimento.resolver_intencao_encerramento(
                contexto, {'resposta_ja_existia': True}, object()
            ))


class EncaminhamentosRelatorioTests(unittest.TestCase):
    def test_sql_deduplica_por_unidade_data_e_motivo_sem_depender_da_ultima_conversa(self):
        conn = sqlite3.connect(':memory:')
        self.addCleanup(conn.close)
        conn.execute("ATTACH DATABASE ':memory:' AS chatbot")
        conn.execute('''CREATE TABLE chatbot.conversa (
            id_conversa INTEGER, id_unidade INTEGER, id_cliente INTEGER,
            status_ativa BOOLEAN, motivo_encerramento TEXT, finalizou_em TEXT
        )''')
        motivo = 'encaminhado_suporte_idoso'
        conn.executemany('INSERT INTO chatbot.conversa VALUES (?, ?, ?, ?, ?, ?)', [
            (1, 10, 1, False, motivo, '2026-09-01'),
            (2, 10, 1, False, motivo, '2026-09-02'),
            (3, 10, 1, True, None, None),
            (4, 10, 2, False, motivo, '2026-08-31'),
            (5, 10, 3, False, motivo, '2026-10-01'),
            (6, 20, 4, False, motivo, '2026-09-05'),
            (7, 10, 5, False, 'idade_invalida', '2026-09-05'),
            (8, 10, 6, True, motivo, '2026-09-05'),
            (9, 10, 7, False, motivo, None),
        ])

        class CursorSQLite:
            def execute(self, sql, params): self.cursor = conn.execute(sql.replace('%s', '?'), params)
            def fetchone(self): return self.cursor.fetchone()

        cursor = CursorSQLite()
        self.assertEqual(repositorio.contar_encaminhados_comercial_por_idade(10, '2026-09-01', '2026-10-01', cursor), 1)
        self.assertEqual(repositorio.contar_encaminhados_comercial_por_idade(10, None, '2026-10-01', cursor), 2)
        self.assertEqual(repositorio.contar_encaminhados_comercial_por_idade(20, '2026-09-01', '2026-10-01', cursor), 1)
        self.assertEqual(repositorio.contar_encaminhados_comercial_por_idade(30, None, '2026-10-01', cursor), 0)

    def test_servico_propaga_unidade_periodos_politica_e_falha(self):
        fim = datetime(2026, 9, 11, tzinfo=timezone.utc)
        for chave in PERIODOS:
            periodo = resolver_periodo(chave, agora=fim)
            with self.subTest(periodo=chave), ExitStack() as stack:
                stack.enter_context(patch.object(services, 'connection', MagicMock()))
                stack.enter_context(patch.object(repositorio, 'buscar_unidade', return_value={
                    'nome_unidade': 'Teste', 'bpa_ativo': False, 'idade_minima_suporte': None,
                    'inicio_historico': fim - timedelta(days=300),
                }))
                stack.enter_context(patch.object(repositorio, 'buscar_metricas', return_value={}))
                for nome in ('buscar_perfis', 'buscar_satisfacao', 'buscar_etapas', 'buscar_atividade'):
                    stack.enter_context(patch.object(repositorio, nome, return_value=[]))
                contar = stack.enter_context(patch.object(services.repositorio_encerramentos, 'contar_encerramentos_por_motivo', return_value=[{'motivo_encerramento':'idade_universal_90','status_dependente':False,'conversas':3}]))
                payload = services.carregar_relatorio(SimpleNamespace(id_unidade=10), periodo)
                self.assertEqual(contar.call_args.args[:3], (10, periodo.inicio, periodo.fim))
                self.assertEqual(payload['encerramentos_por_idade']['total_encaminhadas'], 3)
                self.assertIsNone(payload['unidade']['idade_minima_suporte'])
                contar.side_effect = RuntimeError('banco indisponível')
                with self.assertRaises(RuntimeError):
                    services.carregar_relatorio(SimpleNamespace(id_unidade=10), periodo)

    def test_card_nao_inventa_zero_e_tags_permanecem_fixas(self):
        for invalido in (None, True, -1, '1'):
            with self.assertRaises(ValueError):
                montar_tabela_encerramentos([{'conversas': invalido}], idade_minima_suporte=60, bpa_ativo=False)
        self.assertEqual(classificar_faixa(59), 'adulto')
        self.assertEqual(classificar_faixa(60), 'idoso')
        perfis = services._agrupar_perfis([
            {'id_cliente': 1, 'status_dependente': False, 'idade_titular': 65, 'foi_funil': True},
        ], bpa_ativo=False)
        idoso = next(p for p in perfis['linhas'] if p['chave'] == 'titular_idoso')
        self.assertEqual(idoso['funil'], 1)
        self.assertEqual(idoso['taxa_funil'], 100.0)


if __name__ == '__main__':
    unittest.main()
```

## Passo 45 — Substituir integralmente `tests/unit/test_worker_flow_runtime.py`

```python
import unittest
from contextlib import ExitStack
from datetime import datetime
from unittest.mock import patch

from tests.helpers import FakeConn, FakeCursor
from workers.worker_flow.response_flow import flow_worker
from workers.worker_flow.suporte import estado_ciclo


class PararWorker(BaseException):
    pass


def registro_fila():
    return (
        7,
        "5571999999999",
        "Ola",
        "text",
        "123456",
        "5571000000000",
        datetime(2026, 6, 18, 10, 0),
        "wamid.cliente.7",
        1,
    )


def contexto_banco():
    return {
        "id_unidade": 2,
        "id_cliente": 6,
        "cliente_telefone": "5571999999999",
        "id_phone_unidade": "123456",
        "cliente_inserido": False,
        "cliente_cache_pendente": False,
        "conversa": {
            "id_conversa": 10,
            "estado": "ativa",
        },
    }


def contexto_historico():
    return {
        "id_conversa": 10,
        "id_etapa_atual": None,
        "id_etapa_cliente": 1,
        "id_etapa_resposta": 1,
        "mensagem_cliente_inserida": True,
        "mensagem_cliente_atual": {
            "id_mensagem_fila": 7,
            "id_hash_msg": "wamid.cliente.7",
            "cliente_telefone": "5571999999999",
            "id_phone_unidade": "123456",
        },
        "resposta_bot_para_mensagem_atual": None,
        "retry_count": 1,
    }


def contexto_envio():
    return {
        "enviou": True,
        "resposta_ja_existia": False,
        "id_hash_msg_bot": "wamid.bot.7",
        "id_etapa_resultante": 1,
        "tipo_mensagem": "text",
    }


def contexto_final():
    return {
        "id_etapa_resultante": 1,
        "resposta_ja_existia": False,
        "id_hash_msg_bot": "wamid.bot.7",
    }


class WorkerFlowRuntimeTests(unittest.TestCase):

    def test_followup_confirma_efeitos_encerramento_e_fila_no_mesmo_commit(self):
        conn = FakeConn(FakeCursor())
        commits = []
        with ExitStack() as stack:
            self._patch_fluxo_base(stack, conn, [])
            stack.enter_context(
                patch.object(
                    flow_worker,
                    "preparar_retorno_followup",
                    return_value=dict(contexto_historico(), retorno_followup=True),
                )
            )
            stack.enter_context(
                patch.object(
                    flow_worker,
                    "enviar_retorno_followup",
                    return_value=contexto_envio(),
                )
            )
            stack.enter_context(
                patch.object(
                    flow_worker,
                    "persistir_retorno_followup",
                    side_effect=lambda *_: commits.append(("efeitos", conn.commits))
                    or contexto_final(),
                )
            )
            stack.enter_context(
                patch.object(
                    flow_worker,
                    "finalizar_mensagem_processada",
                    side_effect=lambda *_: commits.append(
                        ("encerramento_e_fila", conn.commits)
                    )
                    or {"atendimento_encerrado": True},
                )
            )
            stack.enter_context(
                patch.object(
                    flow_worker,
                    "registrar_cache_bloqueio_apos_commit",
                    side_effect=lambda *_: commits.append(("cache", conn.commits)),
                )
            )
            with self.assertRaises(PararWorker):
                flow_worker.worker_flow()
        self.assertEqual(
            commits, [("efeitos", 5), ("encerramento_e_fila", 5), ("cache", 6)]
        )
        self.assertEqual(conn.rollbacks, 0)

    def test_falha_finalizacao_followup_reverte_resposta_efeitos_e_checkpoint(self):
        conn = FakeConn(FakeCursor())
        commits = []
        with ExitStack() as stack:
            self._patch_fluxo_base(stack, conn, [])
            stack.enter_context(
                patch.object(
                    flow_worker,
                    "preparar_retorno_followup",
                    return_value=dict(contexto_historico(), retorno_followup=True),
                )
            )
            stack.enter_context(
                patch.object(
                    flow_worker,
                    "enviar_retorno_followup",
                    return_value=contexto_envio(),
                )
            )
            stack.enter_context(
                patch.object(
                    flow_worker,
                    "persistir_retorno_followup",
                    side_effect=lambda *_: commits.append(conn.commits)
                    or contexto_final(),
                )
            )
            stack.enter_context(
                patch.object(
                    flow_worker,
                    "finalizar_mensagem_processada",
                    side_effect=RuntimeError("falha ao finalizar"),
                )
            )
            erro = stack.enter_context(
                patch.object(
                    flow_worker,
                    "handle_erro_generico",
                    side_effect=lambda *_: commits.append(conn.commits),
                )
            )
            cache = stack.enter_context(
                patch.object(flow_worker, "registrar_cache_bloqueio_apos_commit")
            )
            with self.assertRaises(PararWorker):
                flow_worker.worker_flow()
        self.assertEqual(commits, [5, 5])
        self.assertEqual(conn.rollbacks, 1)
        self.assertIsInstance(
            erro.call_args.args[2], flow_worker.BancoFalhouAposEnvioMeta
        )
        cache.assert_not_called()

    def test_reacao_followup_usa_orquestrador_e_checkpoint_proprios(self):
        conn = FakeConn(FakeCursor())
        eventos = []
        with ExitStack() as stack:
            self._patch_fluxo_base(stack, conn, eventos)
            cx = dict(contexto_historico(), retorno_followup=True)
            stack.enter_context(
                patch.object(flow_worker, "preparar_retorno_followup", return_value=cx)
            )
            normal_historico = stack.enter_context(
                patch.object(flow_worker, "valida_historico")
            )
            normal_sender = stack.enter_context(
                patch.object(flow_worker, "flow_sender")
            )
            normal_persistencia = stack.enter_context(
                patch.object(flow_worker, "atualizar_banco_com_contexto_final")
            )
            repetir = stack.enter_context(
                patch.object(
                    flow_worker,
                    "enviar_retorno_followup",
                    return_value=contexto_envio(),
                )
            )
            persistir = stack.enter_context(
                patch.object(
                    flow_worker,
                    "persistir_retorno_followup",
                    return_value=contexto_final(),
                )
            )
            finalizar = stack.enter_context(
                patch.object(
                    flow_worker,
                    "finalizar_mensagem_processada",
                    return_value={"atendimento_encerrado": False},
                )
            )
            with self.assertRaises(PararWorker):
                flow_worker.worker_flow()
        normal_historico.assert_not_called()
        normal_sender.assert_not_called()
        normal_persistencia.assert_not_called()
        repetir.assert_called_once()
        persistir.assert_called_once()
        finalizar.assert_called_once()

    def test_lock_perdido_nao_envia_nem_reescreve_fila(self):
        conn = FakeConn(FakeCursor())
        eventos = []
        with ExitStack() as stack:
            self._patch_fluxo_base(stack, conn, eventos)
            stack.enter_context(
                patch.object(
                    flow_worker,
                    "proteger_conversa",
                    side_effect=flow_worker.LockConversaPerdido,
                )
            )
            enviar = stack.enter_context(patch.object(flow_worker, "flow_sender"))
            reagendar = stack.enter_context(
                patch.object(flow_worker, "reagendar_mensagem_sem_erro")
            )
            finalizar = stack.enter_context(
                patch.object(flow_worker, "finalizar_mensagem_processada")
            )
            with self.assertRaises(PararWorker):
                flow_worker.worker_flow()
        enviar.assert_not_called()
        reagendar.assert_not_called()
        finalizar.assert_not_called()
        self.assertEqual(conn.rollbacks, 1)

    def test_fila_vazia_aguarda_um_segundo_e_meio(self):
        with (
            patch.object(estado_ciclo.time, "sleep") as sleep,
            patch.object(estado_ciclo.logger, "debug") as log_debug,
        ):
            estado_ciclo.aguardar_fila_vazia()

        sleep.assert_called_once_with(1.5)
        log_debug.assert_called_once_with("fila_vazia | acao=aguardar segundos=1.5")

    def test_erro_operacional_psycopg3_reinicia_conexao(self):
        erro = flow_worker.psycopg.OperationalError("conexao indisponivel")

        with ExitStack() as stack:
            stack.enter_context(patch("builtins.print"))
            stack.enter_context(
                patch.object(
                    flow_worker,
                    "get_conn",
                    side_effect=[erro, PararWorker()],
                )
            )
            tratar_conexao = stack.enter_context(
                patch.object(
                    flow_worker,
                    "handle_erro_conexao",
                    return_value=10,
                )
            )

            with self.assertRaises(PararWorker):
                flow_worker.worker_flow()

        tratar_conexao.assert_called_once_with(erro, 5)

    def test_fila_vazia_fecha_conexao_antes_de_aguardar(self):
        conn = FakeConn(FakeCursor())

        with ExitStack() as stack:
            stack.enter_context(patch("builtins.print"))
            stack.enter_context(
                patch.object(
                    flow_worker,
                    "get_conn",
                    side_effect=[conn, PararWorker()],
                )
            )
            stack.enter_context(
                patch.object(
                    flow_worker,
                    "pegar_mensagens_da_fila",
                    return_value=None,
                )
            )
            close = stack.enter_context(
                patch.object(
                    conn,
                    "close",
                    wraps=conn.close,
                )
            )

            def verificar_conexao_fechada():
                self.assertTrue(conn.closed)

            stack.enter_context(
                patch.object(
                    flow_worker,
                    "aguardar_fila_vazia",
                    side_effect=verificar_conexao_fechada,
                )
            )

            with self.assertRaises(PararWorker):
                flow_worker.worker_flow()

        close.assert_called_once_with()
        self.assertEqual(conn.commits, 1)
        self.assertEqual(conn.rollbacks, 0)

    def _patch_fluxo_base(self, stack, conn, eventos):
        stack.enter_context(patch.object(flow_worker, "preparar_abertura", side_effect=lambda contexto, *_: contexto))
        stack.enter_context(
            patch.object(
                flow_worker, "reler_conversa", side_effect=lambda contexto, *_: contexto
            )
        )
        stack.enter_context(patch.object(flow_worker, "proteger_conversa"))
        stack.enter_context(
            patch.object(flow_worker, "preparar_retorno_followup", return_value=None)
        )
        stack.enter_context(patch("builtins.print"))
        stack.enter_context(
            patch.object(
                flow_worker,
                "get_conn",
                side_effect=[conn, PararWorker()],
            )
        )
        stack.enter_context(
            patch.object(
                flow_worker,
                "pegar_mensagens_da_fila",
                return_value=registro_fila(),
            )
        )
        stack.enter_context(
            patch.object(
                flow_worker,
                "validar_banco_mensagem",
                side_effect=lambda *_args: eventos.append("validar_banco")
                or contexto_banco(),
            )
        )
        stack.enter_context(
            patch.object(
                flow_worker,
                "vincular_mensagem_fila_a_conversa",
                side_effect=lambda *_args: eventos.append("vincular_conversa") or 1,
            )
        )
        stack.enter_context(
            patch.object(
                flow_worker,
                "confirmar_cache_cliente_se_pendente",
                return_value=False,
            )
        )
        stack.enter_context(
            patch.object(
                flow_worker,
                "tentar_lock_conversa",
                side_effect=lambda *_args: eventos.append("adquirir_lock") or (True, 4),
            )
        )
        stack.enter_context(
            patch.object(
                flow_worker,
                "reagendar_se_houver_mensagem_anterior",
                side_effect=lambda *_args: eventos.append("verificar_ordem") or False,
            )
        )
        stack.enter_context(
            patch.object(
                flow_worker,
                "valida_historico",
                side_effect=lambda *_args: eventos.append("persistir_cliente")
                or contexto_historico(),
            )
        )
        stack.enter_context(
            patch.object(
                flow_worker,
                "flow_sender",
                side_effect=lambda *_args: eventos.append("enviar_meta")
                or contexto_envio(),
            )
        )
        stack.enter_context(
            patch.object(
                flow_worker,
                "liberar_lock_conversa_se_necessario",
                side_effect=lambda *_args: eventos.append("liberar_lock") or True,
            )
        )
        stack.enter_context(
            patch.object(
                flow_worker,
                "handle_erro_generico",
            )
        )

    def test_mensagem_anterior_reagenda_antes_de_validar_banco(self):
        conn = FakeConn(FakeCursor())

        with ExitStack() as stack:
            stack.enter_context(patch("builtins.print"))
            stack.enter_context(
                patch.object(
                    flow_worker,
                    "get_conn",
                    side_effect=[conn, PararWorker()],
                )
            )
            stack.enter_context(
                patch.object(
                    flow_worker,
                    "pegar_mensagens_da_fila",
                    return_value=registro_fila(),
                )
            )
            barreira = stack.enter_context(
                patch.object(
                    flow_worker,
                    "reagendar_se_houver_mensagem_anterior",
                    return_value=True,
                )
            )
            validar = stack.enter_context(
                patch.object(
                    flow_worker,
                    "validar_banco_mensagem",
                )
            )
            lock = stack.enter_context(
                patch.object(
                    flow_worker,
                    "tentar_lock_conversa",
                )
            )
            vincular = stack.enter_context(
                patch.object(
                    flow_worker,
                    "vincular_mensagem_fila_a_conversa",
                )
            )

            with self.assertRaises(PararWorker):
                flow_worker.worker_flow()

        barreira.assert_called_once()
        validar.assert_not_called()
        lock.assert_not_called()
        vincular.assert_not_called()
        self.assertEqual(conn.commits, 2)
        self.assertEqual(conn.rollbacks, 0)
        self.assertTrue(conn.closed)

    def test_ciclo_normal_persiste_resposta_antes_de_marcar_sent(self):
        conn = FakeConn(FakeCursor())
        eventos = []

        with ExitStack() as stack:
            self._patch_fluxo_base(stack, conn, eventos)
            stack.enter_context(
                patch.object(
                    flow_worker,
                    "atualizar_banco_com_contexto_final",
                    side_effect=lambda *_args: eventos.append("persistir_bot")
                    or contexto_final(),
                )
            )
            finalizar = stack.enter_context(
                patch.object(
                    flow_worker,
                    "finalizar_mensagem_processada",
                    side_effect=lambda *_args: (
                        eventos.append("marcar_sent")
                        or {"atendimento_encerrado": False}
                    ),
                )
            )

            with self.assertRaises(PararWorker):
                flow_worker.worker_flow()

        self.assertEqual(
            eventos,
            [
                "verificar_ordem",
                "validar_banco",
                "adquirir_lock",
                "vincular_conversa",
                "persistir_cliente",
                "enviar_meta",
                "persistir_bot",
                "marcar_sent",
                "liberar_lock",
            ],
        )
        finalizar.assert_called_once()
        self.assertEqual(conn.commits, 8)
        self.assertEqual(conn.rollbacks, 0)
        self.assertTrue(conn.closed)

    def test_checkpoint_cache_e_atomicidade_vinculo_historico(self):
        conn = FakeConn(FakeCursor())
        eventos = []
        commits_observados = {}

        def confirmar_cache(*_args):
            commits_observados["cache"] = conn.commits
            return False

        def vincular_conversa(*_args):
            commits_observados["vinculo"] = conn.commits
            return 1

        def persistir_historico(*_args):
            commits_observados["historico"] = conn.commits
            return contexto_historico()

        with ExitStack() as stack:
            self._patch_fluxo_base(stack, conn, eventos)
            stack.enter_context(
                patch.object(
                    flow_worker,
                    "confirmar_cache_cliente_se_pendente",
                    side_effect=confirmar_cache,
                )
            )
            stack.enter_context(
                patch.object(
                    flow_worker,
                    "vincular_mensagem_fila_a_conversa",
                    side_effect=vincular_conversa,
                )
            )
            stack.enter_context(
                patch.object(
                    flow_worker,
                    "valida_historico",
                    side_effect=persistir_historico,
                )
            )
            stack.enter_context(
                patch.object(
                    flow_worker,
                    "atualizar_banco_com_contexto_final",
                    return_value=contexto_final(),
                )
            )
            stack.enter_context(
                patch.object(
                    flow_worker,
                    "finalizar_mensagem_processada",
                    return_value={"atendimento_encerrado": False},
                )
            )

            with self.assertRaises(PararWorker):
                flow_worker.worker_flow()

        self.assertEqual(commits_observados["cache"], 2)
        self.assertEqual(commits_observados["vinculo"], 3)
        self.assertEqual(commits_observados["historico"], 3)

    def test_lock_recusado_reagenda_sem_consumir_retry(self):
        conn = FakeConn(FakeCursor())
        eventos = []

        with ExitStack() as stack:
            self._patch_fluxo_base(stack, conn, eventos)
            stack.enter_context(
                patch.object(
                    flow_worker,
                    "tentar_lock_conversa",
                    return_value=(False, None),
                )
            )
            reagendar = stack.enter_context(
                patch.object(
                    flow_worker,
                    "reagendar_mensagem_sem_erro",
                    return_value=1,
                )
            )
            vincular = stack.enter_context(
                patch.object(
                    flow_worker,
                    "vincular_mensagem_fila_a_conversa",
                )
            )
            historico = stack.enter_context(
                patch.object(
                    flow_worker,
                    "valida_historico",
                )
            )
            enviar = stack.enter_context(
                patch.object(
                    flow_worker,
                    "flow_sender",
                )
            )
            stack.enter_context(
                patch.object(
                    flow_worker,
                    "liberar_lock_conversa_se_necessario",
                    return_value=None,
                )
            )

            with self.assertRaises(PararWorker):
                flow_worker.worker_flow()

        reagendar.assert_called_once_with(
            7,
            conn.cursor_obj,
            delay_seconds=5,
        )
        vincular.assert_not_called()
        historico.assert_not_called()
        enviar.assert_not_called()
        self.assertEqual(conn.commits, 4)
        self.assertEqual(conn.rollbacks, 0)
        self.assertTrue(conn.closed)

    def test_vinculo_inconsistente_reagenda_sem_enviar(self):
        conn = FakeConn(FakeCursor())
        eventos = []

        with ExitStack() as stack:
            self._patch_fluxo_base(stack, conn, eventos)
            stack.enter_context(
                patch.object(
                    flow_worker,
                    "vincular_mensagem_fila_a_conversa",
                    return_value=0,
                )
            )
            tratar_erro = stack.enter_context(
                patch.object(
                    flow_worker,
                    "handle_erro_generico",
                )
            )
            reagendar = stack.enter_context(
                patch.object(
                    flow_worker,
                    "reagendar_mensagem_sem_erro",
                    return_value=1,
                )
            )
            aviso = stack.enter_context(
                patch.object(
                    flow_worker.logger,
                    "critical",
                )
            )
            persistir_bot = stack.enter_context(
                patch.object(
                    flow_worker,
                    "atualizar_banco_com_contexto_final",
                )
            )
            finalizar = stack.enter_context(
                patch.object(
                    flow_worker,
                    "finalizar_mensagem_processada",
                )
            )

            with self.assertRaises(PararWorker):
                flow_worker.worker_flow()

        tratar_erro.assert_not_called()
        persistir_bot.assert_not_called()
        finalizar.assert_not_called()
        reagendar.assert_called_once_with(7, conn.cursor_obj, delay_seconds=300)
        self.assertEqual(
            eventos,
            [
                "verificar_ordem",
                "validar_banco",
                "adquirir_lock",
                "liberar_lock",
            ],
        )
        aviso.assert_called_once()
        self.assertIn(
            "motivo=historico_conflitante_ou_fila_ausente",
            aviso.call_args.args[0],
        )
        self.assertEqual(conn.rollbacks, 0)
        self.assertTrue(conn.closed)

    def test_falha_do_banco_apos_meta_reagenda_sem_marcar_sent(self):
        conn = FakeConn(FakeCursor())
        eventos = []

        with ExitStack() as stack:
            self._patch_fluxo_base(stack, conn, eventos)
            stack.enter_context(
                patch.object(
                    flow_worker,
                    "atualizar_banco_com_contexto_final",
                    side_effect=RuntimeError("banco caiu apos envio"),
                )
            )
            finalizar = stack.enter_context(
                patch.object(
                    flow_worker,
                    "finalizar_mensagem_processada",
                    side_effect=lambda *_args: (
                        eventos.append("marcar_sent")
                        or {"atendimento_encerrado": False}
                    ),
                )
            )
            tratar_erro = stack.enter_context(
                patch.object(
                    flow_worker,
                    "handle_erro_generico",
                )
            )

            with self.assertRaises(PararWorker):
                flow_worker.worker_flow()

        finalizar.assert_not_called()
        tratar_erro.assert_called_once()
        self.assertNotIn("marcar_sent", eventos)
        self.assertEqual(conn.rollbacks, 1)
        self.assertEqual(conn.commits, 7)
        self.assertTrue(conn.closed)


if __name__ == "__main__":
    unittest.main()
```

## Passo 46 — Criar `tests/fixtures/fireads.py`

```python
"""Migração real nas bases PostgreSQL descartáveis da suíte."""

from pathlib import Path

MIGRACAO_FIREADS = (
    Path(__file__).resolve().parents[2]
    / "deploy/migrations/20261007_fireads_chat_customizacao.sql"
)


def aplicar_fireads(cursor):
    """Usa o DDL do deploy, preservando a transação controlada pelo teste."""
    texto = MIGRACAO_FIREADS.read_text(encoding="utf-8")
    ddl = texto.split("-- INICIO DDL FIREADS\n", 1)[1].split("-- FIM DDL FIREADS", 1)[0]
    cursor.execute(ddl)
```

## Passo 47 — Substituir integralmente `tests/fixtures/reserva_migracao.py`

```python
"""Estado anterior à rota sem link, com dados sintéticos nas áreas preservadas."""

from contextlib import contextmanager
from unittest.mock import patch

from core.database.deploy_database import bank_script, etapa_transicao_script
from core.database.deploy_database.povoar_etapas import ETAPAS


ETAPAS_LEGADAS = tuple(etapa for etapa in ETAPAS if etapa[0] <= 17) + (
    (18, "Agendamento após a triagem cognitiva", False, 0, True),
    (19, "Pesquisa de satisfação - nota", False, 0, True),
    (20, "Pesquisa de satisfação - opção de comentário", False, 0, True),
    (21, "Pesquisa de satisfação - comentário", False, 0, True),
    (22, "Finalização do atendimento", True, 30, True),
)

TRANSICOES_LEGADAS = tuple(
    (origem, evento, destino)
    for origem, evento, destino in etapa_transicao_script.TRANSICOES_INICIAIS
    if origem <= 16 and not evento.endswith('_email_fireads')
) + (
    (17, "triagem_pergunta_6_respondida", 18),
    (18, "agendamento_confirmado", 19),
    (19, "satisfacao_avaliada", 20),
    (20, "comentario_satisfacao_aceito", 21),
    (20, "comentario_satisfacao_recusado", 22),
    (21, "comentario_satisfacao_recebido", 22),
)


def criar_base_legada(conn):
    """O chamador já verificou banco vazio, local e exclusivo dos testes."""
    cursor = conn.cursor()
    cursor.execute("CREATE SCHEMA chatbot; CREATE TABLE chatbot.auth_user(id SERIAL PRIMARY KEY)")

    @contextmanager
    def transacao_local(*_):
        yield cursor

    with patch.object(bank_script, "transacao_deploy", transacao_local), patch.object(
        etapa_transicao_script, "transacao_deploy", transacao_local
    ), patch.object(etapa_transicao_script, "TRANSICOES_INICIAIS", TRANSICOES_LEGADAS):
        bank_script.criar_tabelas()
        bank_script.criar_funcoes_lock()
        # Os únicos deltas de schema desta entrega são turno e link opcional.
        cursor.execute("ALTER TABLE chatbot.conversa DROP COLUMN turno")
        cursor.execute("ALTER TABLE chatbot.unidade ALTER COLUMN link_agendamento SET NOT NULL")
        cursor.executemany(
            "INSERT INTO chatbot.etapa VALUES (%s,%s,%s,%s,%s)", ETAPAS_LEGADAS
        )
        etapa_transicao_script.criar_e_povoar_transicoes_etapa()

    cursor.execute("""
        CREATE TABLE chatbot.historico_mensagens_202610
        PARTITION OF chatbot.historico_mensagens
        FOR VALUES FROM ('2026-10-01 00:00:00-03') TO ('2026-11-01 00:00:00-03');

        INSERT INTO chatbot.unidade(id_unidade,nome_unidade,nome_agente,genero,cnpj,
            email_responsavel,telefone,numero_comercial,waba_id,phone_number_id,link_agendamento,
            id_fuso,nome_fuso,fuso_verificado_em)
        VALUES (1,'Unidade teste','Suh','feminino','cnpj','teste@example.com','5511888888888',
            '5511999999999','waba','phone','https://example.com/reserva',25,'America/Sao_Paulo',NOW());

        INSERT INTO chatbot.cliente(id_cliente,nome,waid_telefone,idade,email)
        SELECT id,'Cliente ' || id,'55119999999' || id,40,'cliente' || id || '@example.com'
        FROM generate_series(18,22) id;
        INSERT INTO chatbot.conversa(id_conversa,id_cliente,id_unidade,id_etapa_atual,
            status_ativa,profissao,followup_stage,followup_last_sent_at,lead_no_funil,
            processing,processing_started_at,lock_version,turnos_sem_avanco,
            iniciou_em,finalizou_em,motivo_encerramento,last_message_from,last_interaction_at)
        SELECT id,id,1,id,id <> 22,'Professora',1,'2026-09-28 13:00:00-03',id >= 20,
            id=18,CASE WHEN id=18 THEN NOW()-INTERVAL '5 minutes' END,8,3,
            '2026-09-28 10:00:00-03',CASE WHEN id=22 THEN '2026-09-29 10:00:00-03'::timestamptz END,
            CASE WHEN id=22 THEN 'foi_agendado' END,'bot','2026-09-29 09:00:00-03'
        FROM generate_series(18,22) id;

        INSERT INTO chatbot.dependente(id_cliente,id_conversa,nome_dependente,idade)
        VALUES (21,21,'João',12);
        UPDATE chatbot.conversa SET status_dependente=TRUE WHERE id_conversa=21;

        INSERT INTO chatbot.fila_mensagens(id_mensagem,id_conversa,received_data_hora,
            cliente_telefone,conteudo_texto,tipo_mensagem,id_hash_msg,id_phone_unidade,unidade_telefone,
            status,retry_count,processing_started_at)
        SELECT id,id,'2026-09-29 09:00:00-03','55119999999' || id,'Já reservei',
            'text','wamid.cliente.' || id,'phone','5511888888888',
            CASE WHEN id=18 THEN 'processing' ELSE 'pending' END,1,NOW()-INTERVAL '5 minutes'
        FROM generate_series(18,22) id;

        INSERT INTO chatbot.historico_mensagens(id_conversa,id_etapa,received_data_hora,
            cliente_telefone,conteudo_texto,tipo_mensagem,id_hash_msg,id_phone_unidade,
            unidade_telefone,quem_enviou,status_envio,id_mensagem_fila,id_hash_cliente_origem)
        SELECT id,id,'2026-09-29 09:00:00-03','55119999999' || id,'Já reservei','text',
            'wamid.cliente.' || id,'phone','5511888888888','cliente',NULL,id,NULL
        FROM generate_series(18,22) id;
        INSERT INTO chatbot.historico_mensagens(id_conversa,id_etapa,received_data_hora,
            cliente_telefone,conteudo_texto,tipo_mensagem,id_hash_msg,id_phone_unidade,
            unidade_telefone,quem_enviou,status_envio,id_mensagem_fila,id_hash_cliente_origem)
        SELECT id,CASE WHEN id=18 THEN 19 ELSE id END,'2026-10-01 09:01:00-03',
            '55119999999' || id,'Resposta preservada','text','wamid.bot.' || id,
            'phone','5511888888888','bot','sent',id,'wamid.cliente.' || id
        FROM generate_series(18,22) id;

        INSERT INTO chatbot.respostas_desafios(id_conversa,id_etapa,resposta)
        SELECT 21,etapa,'Sim' FROM generate_series(12,17) etapa;
        INSERT INTO chatbot.pesquisa_satisfacao(id_conversa,nota,comentario)
        VALUES (22,5,'Muito bom! ☺️');
        INSERT INTO chatbot.followup_retomada(id_conversa,id_mensagem_fila,id_hash_cliente,
            id_etapa,stage_anterior,followup_em)
        SELECT id,id,'wamid.cliente.' || id,id,1,'2026-09-28 13:00:00-03'
        FROM generate_series(18,22) id;
        INSERT INTO chatbot.followup_envio(id_conversa,id_ancora,ancora_em,id_historico_bot,enviado_em,id_hash_msg)
        VALUES (18,100,'2026-09-28 06:00:00-03',101,'2026-09-28 13:00:00-03','wamid.followup');
        INSERT INTO chatbot.followup_legado(id_conversa,stage_anterior) VALUES (19,0);
        INSERT INTO chatbot.funil_envios(id_conversa,status,attempt_count,resposta_funil)
        VALUES (20,'sent',1,'aceito'),(21,'processing',2,NULL);

        INSERT INTO chatbot.consumo_mensal_meta(id_unidade,mes_referencia,waba_id,phone_number_id,
            timezone_id,fuso_horario,data_hora_inicio,data_hora_fim,qtd_janela_gratuita,
            qtd_franquia_consumida,qtd_cobradas_meta,consultado_ate,ultimo_sucesso_em,
            status_apuracao,data_proxima_consolidacao)
        VALUES (1,'2026-10-01','waba','phone',25,'America/Sao_Paulo',
            '2026-10-01 00:00:00-03','2026-11-01 00:00:00-03',3000,750,0,
            '2026-10-02 10:00:00-03','2026-10-02 10:00:00-03','em_andamento','2026-11-25');
        INSERT INTO chatbot.consumo_meta_coletas(id_unidade,periodo,proxima_consulta_em,
            ultima_tentativa_em,ultimo_erro,falhas_consecutivas)
        VALUES (1,'2026-10','2026-10-02 11:00:00-03','2026-10-02 10:00:00-03',NULL,0);
    """)
    conn.commit()
```

## Passo 48 — Substituir integralmente `tests/integration/test_followup_postgres.py`

```python
"""Contrato PostgreSQL real. Exige banco local vazio chamado test_chatbot_followup."""

import os
import unittest
from contextlib import contextmanager
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch
from types import SimpleNamespace

import psycopg
from tests.fixtures.fireads import aplicar_fireads
from psycopg.conninfo import conninfo_to_dict

from core.database.deploy_database import bank_script, etapa_transicao_script
from core.repositories.atendimento import followup as repo
from core.repositories.atendimento.conversas import (
    tentar_lock_conversa,
    unlock_conversa,
)
from workers.worker_flow.transacoes.retorno_followup import (
    preparar_retorno_followup,
    persistir_retorno_followup,
)
from workers.worker_flow.response_flow.retomada_followup import enviar_retorno_followup
from core.integrations.whatsapp.pywa_functions import cliente as cliente_wa
from core.repositories.monitoramento import painel
from callback.monitoramento.apresentacao import consolidar_conversas
from workers.worker_flow.valida_banco import valida_conversa
from workers.worker_flow.valida_historico import valida_historico
from workers.worker_flow.response_flow.flow_sender import flow_sender

DSN = os.environ.get("FOLLOWUP_TEST_DSN")
MIGRACAO = (
    Path(__file__).resolve().parents[2] / "deploy/migrations/followup_registros.sql"
)


@unittest.skipUnless(DSN, "Defina FOLLOWUP_TEST_DSN para PostgreSQL local descartável")
class FollowupPostgresTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        parametros = conninfo_to_dict(DSN)
        if (
            parametros.get("host") not in {"127.0.0.1", "::1", "localhost"}
            or parametros.get("dbname") != "test_chatbot_followup"
        ):
            raise RuntimeError(
                "Teste exige host loopback e dbname=test_chatbot_followup"
            )
        cls.conn = psycopg.connect(DSN, connect_timeout=5)
        cls.cursor = cls.conn.cursor()
        cls.cursor.execute("SELECT to_regnamespace('chatbot')")
        if cls.cursor.fetchone()[0] is not None:
            cls.conn.close()
            raise RuntimeError(
                "Banco de teste não está vazio: schema chatbot já existe"
            )
        cls.cursor.execute(
            "CREATE SCHEMA chatbot; CREATE TABLE chatbot.auth_user (id SERIAL PRIMARY KEY);"
        )

        @contextmanager
        def transacao_local(*_):
            yield cls.cursor

        with patch.object(bank_script, "transacao_deploy", transacao_local):
            bank_script.criar_tabelas()
            bank_script.criar_funcoes_lock()
        # Colunas reais usadas nas barreiras; não simula o comportamento da Meta.
        cls.cursor.execute(
            """
            CREATE TABLE chatbot.cliente_bloqueado_meta
                (wa_id_cliente VARCHAR(100), phone_id_unidade VARCHAR(100));
            CREATE TABLE chatbot.webhook_flood_evento
                (wa_id_cliente VARCHAR(100), phone_id_unidade VARCHAR(100), received_at TIMESTAMPTZ);
            INSERT INTO chatbot.etapa(id_etapa, nome_etapa)
            SELECT etapa, 'Etapa de teste ' || etapa::text FROM generate_series(1, 24) AS etapa;
            INSERT INTO chatbot.cliente(id_cliente, waid_telefone, nome, idade) VALUES (1, '5511999999999', 'Ana', 35);
            INSERT INTO chatbot.unidade
                (id_unidade, nome_unidade, nome_agente, genero, cnpj, email_responsavel,
                 telefone, numero_comercial, waba_id, phone_number_id, link_agendamento)
            VALUES (1, 'Unidade Teste', 'Suh', 'feminino', 'teste', 'teste@example.com',
                '5511888888888', '5511999999998', 'waba-teste', 'phone-teste', 'https://example.com/agendar');
            INSERT INTO chatbot.conversa(id_conversa, id_cliente, id_unidade, id_etapa_atual)
            VALUES (1, 1, 1, 11);
        """
        )
        with patch.object(etapa_transicao_script, "transacao_deploy", transacao_local):
            etapa_transicao_script.criar_e_povoar_transicoes_etapa()
        aplicar_fireads(cls.cursor)
        cls.conn.commit()

    @classmethod
    def tearDownClass(cls):
        cls.conn.rollback()
        cls.cursor.execute("DROP SCHEMA chatbot CASCADE")
        cls.conn.commit()
        cls.conn.close()

    def setUp(self):
        self.conn.rollback()
        self.cursor.execute("SELECT clock_timestamp()")
        self.agora = self.cursor.fetchone()[0]
        self.ancora = self.agora - timedelta(hours=7, seconds=1)
        self.cursor.execute(
            """
            INSERT INTO chatbot.historico_mensagens
                (id_conversa, id_etapa, received_data_hora, cliente_telefone, conteudo_texto,
                 tipo_mensagem, id_hash_msg, id_phone_unidade, unidade_telefone, quem_enviou, status_envio)
            VALUES (1, 11, %s, '5511999999999', 'mensagem', 'text', 'wamid.cliente',
                    'phone-teste', '5511888888888', 'cliente', NULL),
                   (1, 11, %s, '5511999999999', 'Podemos começar?', 'text', 'wamid.bot',
                    'phone-teste', '5511888888888', 'bot', 'sent');
        """,
            (self.ancora - timedelta(minutes=1), self.ancora),
        )
        self.cursor.execute(
            "UPDATE chatbot.conversa SET last_message_from = 'bot', last_interaction_at = %s WHERE id_conversa = 1",
            (self.ancora,),
        )

    def tearDown(self):
        self.conn.rollback()

    def test_sete_horas_um_envio_e_reinicio_nao_duplica(self):
        dados = repo.reler_elegivel(1, self.cursor)
        self.assertIsNotNone(dados)
        ok, versao = tentar_lock_conversa(1, self.cursor)
        self.assertTrue(ok)
        envio = {
            "enviou": True,
            "mensagem_bot": "Você viu a minha mensagem?",
            "id_hash_msg_bot": "wamid.followup",
        }
        id_bot, data = repo.persistir_followup(dados, envio, versao, self.cursor)
        self.assertIsNone(repo.reler_elegivel(1, self.cursor))
        self.cursor.execute(
            "SELECT followup_stage, followup_last_sent_at FROM chatbot.conversa WHERE id_conversa=1"
        )
        self.assertEqual(self.cursor.fetchone(), (1, data))
        self.cursor.execute(
            "SELECT id_mensagem_fila, id_hash_cliente_origem FROM chatbot.historico_mensagens WHERE id_mensagem=%s AND received_data_hora=%s",
            (id_bot, data),
        )
        self.assertEqual(self.cursor.fetchone(), (None, None))

    def _primeiro_followup_vencido(self):
        dados = repo.reler_elegivel(1, self.cursor)
        _, versao = tentar_lock_conversa(1, self.cursor)
        repo.persistir_followup(dados, {
            "enviou": True, "mensagem_bot": "Primeiro lembrete",
            "id_hash_msg_bot": "wamid.followup1",
        }, versao, self.cursor)
        # O primeiro envio acabou de acontecer: não basta a âncora original ter 7h.
        self.assertIsNone(repo.reler_elegivel(1, self.cursor))
        self.cursor.execute("""
            UPDATE chatbot.historico_mensagens
               SET received_data_hora=received_data_hora-INTERVAL '7 hours 1 second';
            UPDATE chatbot.followup_envio
               SET ancora_em=ancora_em-INTERVAL '7 hours 1 second',
                   enviado_em=enviado_em-INTERVAL '7 hours 1 second';
            UPDATE chatbot.conversa
               SET last_interaction_at=last_interaction_at-INTERVAL '7 hours 1 second',
                   followup_last_sent_at=followup_last_sent_at-INTERVAL '7 hours 1 second';
        """)
        return repo.reler_elegivel(1, self.cursor), versao

    def _confirmar_segundo(self, dados, versao):
        return repo.persistir_followup(dados, {
            "enviou": True, "mensagem_bot": "Despedida",
            "id_hash_msg_bot": "wamid.followup2",
        }, versao, self.cursor)

    def test_segundo_apos_mais_sete_horas_fecha_atomicamente_sem_terceiro(self):
        dados, versao = self._primeiro_followup_vencido()
        self.assertEqual(dados["followup_stage"], 1)
        self.cursor.execute("UPDATE chatbot.conversa SET turnos_sem_avanco=4")
        self.cursor.execute("SAVEPOINT antes_despedida")
        _, encerrada_em = self._confirmar_segundo(dados, versao)
        self.cursor.execute("""
            SELECT followup_stage,status_ativa,motivo_encerramento,finalizou_em,
                   followup_last_sent_at,id_etapa_atual,turnos_sem_avanco
            FROM chatbot.conversa WHERE id_conversa=1
        """)
        self.assertEqual(self.cursor.fetchone(), (
            2, False, "followup_sem_resposta", encerrada_em, encerrada_em, 11, 4,
        ))
        self.assertIsNone(repo.reler_elegivel(1, self.cursor))
        self.cursor.execute("SELECT count(*) FROM chatbot.followup_envio")
        self.assertEqual(self.cursor.fetchone()[0], 2)
        self.cursor.execute("ROLLBACK TO SAVEPOINT antes_despedida")
        self.cursor.execute("SELECT followup_stage,status_ativa,finalizou_em FROM chatbot.conversa")
        self.assertEqual(self.cursor.fetchone(), (1, True, None))
        self.cursor.execute("SELECT count(*) FROM chatbot.followup_envio")
        self.assertEqual(self.cursor.fetchone()[0], 1)
        self.cursor.execute("SELECT count(*) FROM chatbot.historico_mensagens WHERE id_hash_msg='wamid.followup2'")
        self.assertEqual(self.cursor.fetchone()[0], 0)

    def test_segundo_apenas_etapas1_a17_incluindo8_e_guardas_de_silencio(self):
        _, _ = self._primeiro_followup_vencido()
        for etapa in range(1, 25):
            with self.subTest(etapa=etapa):
                self.cursor.execute("UPDATE chatbot.conversa SET id_etapa_atual=%s", (etapa,))
                self.assertEqual(repo.reler_elegivel(1, self.cursor) is not None, etapa <= 17)
        self.cursor.execute("UPDATE chatbot.conversa SET id_etapa_atual=8")
        for sql in (
            "UPDATE chatbot.conversa SET last_message_from='cliente'",
            "UPDATE chatbot.conversa SET followup_last_sent_at=clock_timestamp()",
            "UPDATE chatbot.historico_mensagens SET received_data_hora=clock_timestamp() WHERE quem_enviou='cliente'",
            "UPDATE chatbot.historico_mensagens SET received_data_hora=clock_timestamp()-INTERVAL '24 hours' WHERE quem_enviou='cliente'",
            "DELETE FROM chatbot.followup_envio",
            "UPDATE chatbot.conversa SET followup_stage=2",
            "UPDATE chatbot.unidade SET status_pagamento=FALSE",
            """INSERT INTO chatbot.fila_mensagens
                (received_data_hora,cliente_telefone,conteudo_texto,tipo_mensagem,id_hash_msg,id_phone_unidade,unidade_telefone)
                VALUES (clock_timestamp(),'5511999999999','Voltei','text','pendente','phone-teste','5511888888888')""",
        ):
            with self.subTest(guarda=sql):
                self.cursor.execute("SAVEPOINT guarda_segundo")
                self.cursor.execute(sql)
                self.assertIsNone(repo.reler_elegivel(1, self.cursor))
                self.cursor.execute("ROLLBACK TO SAVEPOINT guarda_segundo")

    def test_retorno_apos_segundo_abre_nova_conversa_sem_prefixo(self):
        dados, versao = self._primeiro_followup_vencido()
        self._confirmar_segundo(dados, versao)
        unlock_conversa(1, versao, self.cursor)
        # A fixture usa ID explícito; sincroniza apenas a sequência local do teste.
        self.cursor.execute("SELECT setval(pg_get_serial_sequence('chatbot.conversa','id_conversa'), 1)")
        nova = valida_conversa(1, 1, False, self.cursor)
        self.assertNotEqual(nova["id_conversa"], 1)
        self.assertIsNone(nova["id_etapa_atual"])
        self.assertEqual(nova["followup_stage"], 0)
        self.assertTrue(nova["status_ativa"])
        mensagem = {
            "id_mensagem": 10, "id_hash": "wamid.novo", "data_recebimento": self.agora,
            "cliente_telefone": "5511999999999", "id_phone_unidade": "phone-teste",
            "unidade_telefone": "5511888888888", "tipo_mensagem": "text",
            "conteudo_texto": "Olá", "retry_count": 0,
        }
        self.cursor.execute("""
            INSERT INTO chatbot.fila_mensagens
                (id_mensagem,received_data_hora,cliente_telefone,conteudo_texto,tipo_mensagem,id_hash_msg,id_phone_unidade,unidade_telefone)
            VALUES(10,clock_timestamp(),'5511999999999','Olá','text','wamid.novo','phone-teste','5511888888888')
        """)
        contexto_banco = {"id_cliente": 1, "id_unidade": 1, "conversa": nova}
        self.assertIsNone(preparar_retorno_followup(mensagem, contexto_banco, self.cursor))
        contexto = valida_historico(mensagem, contexto_banco, self.cursor)
        self.assertIsNone(contexto["saudacao_retorno"])
        with patch.object(cliente_wa, "WhatsApp") as wa:
            wa.return_value.send_message.return_value = SimpleNamespace(id="wamid.abertura")
            envio = flow_sender(contexto)
        self.assertEqual(envio["id_etapa_resultante"], 1)
        self.assertNotIn("te ver novamente", envio["mensagem_bot"])
        self.assertIn("Suh", envio["mensagem_bot"])
        self.cursor.execute("SELECT followup_stage,status_ativa FROM chatbot.conversa WHERE id_conversa=1")
        self.assertEqual(self.cursor.fetchone(), (2, False))

    def test_painel_considera_so_ultima_conversa_mesmo_fora_do_periodo(self):
        dados, versao = self._primeiro_followup_vencido()
        fim = self.agora + timedelta(days=1)
        def chats(ate=fim):
            return consolidar_conversas(painel.listar_conversas(1, None, ate, self.cursor))
        self.assertEqual(chats()[0]["followup_stage"], 1)
        self._confirmar_segundo(dados, versao)
        self.assertEqual(chats()[0]["followup_stage"], 2)
        self.cursor.execute("""
            INSERT INTO chatbot.unidade
                (id_unidade,nome_unidade,cnpj,email_responsavel,telefone,waba_id,phone_number_id)
            VALUES(2,'Outra','outro','outro@example.com','5511777777777','outra-waba','outro-phone');
            INSERT INTO chatbot.atendimento_customizado(id_unidade,nome_agente,genero,numero_comercial,link_agendamento)
            VALUES(2,'Mia','feminino','5511999999997','https://example.com');
            INSERT INTO chatbot.chat(id_cliente,id_unidade) VALUES(1,2);
            INSERT INTO chatbot.conversa(id_conversa,id_chat,id_cliente,id_unidade,id_etapa_atual)
            SELECT 3,id_chat,1,2,1 FROM chatbot.chat WHERE id_cliente=1 AND id_unidade=2;
        """)
        # O mesmo cliente em outra unidade não pode esconder o follow-up daqui.
        self.assertEqual(chats()[0]["followup_stage"], 2)
        self.cursor.execute("""
            INSERT INTO chatbot.conversa(id_conversa,id_chat,id_cliente,id_unidade,id_etapa_atual)
            SELECT 2,id_chat,1,1,1 FROM chatbot.chat WHERE id_cliente=1 AND id_unidade=1
        """)
        # A nova conversa nem possui histórico no período: ainda assim oculta a antiga.
        self.assertEqual(chats()[0]["followup_stage"], 0)
        self.assertEqual(chats(self.agora - timedelta(hours=1))[0]["followup_stage"], 0)
        self.cursor.execute("""
            INSERT INTO chatbot.historico_mensagens
                (id_conversa,id_etapa,received_data_hora,cliente_telefone,conteudo_texto,tipo_mensagem,
                 id_hash_msg,id_phone_unidade,unidade_telefone,quem_enviou)
            VALUES(2,1,clock_timestamp(),'5511999999999','Oi','text','wamid.nova.conversa','phone-teste','5511888888888','cliente');
            UPDATE chatbot.conversa SET followup_stage=1 WHERE id_conversa=2;
        """)
        chat = chats()[0]
        self.assertEqual(chat["ids_conversa"], [1, 2])
        self.assertEqual(chat["followup_stage"], 1)
        self.cursor.execute("UPDATE chatbot.conversa SET followup_stage=0 WHERE id_conversa=2")
        self.assertEqual(chats()[0]["followup_stage"], 0)

    def test_antes_de_sete_horas_e_fora_da_janela_meta(self):
        self.cursor.execute(
            "UPDATE chatbot.historico_mensagens SET received_data_hora=%s WHERE quem_enviou='bot'",
            (self.agora - timedelta(hours=6),),
        )
        self.cursor.execute(
            "UPDATE chatbot.conversa SET last_interaction_at=%s",
            (self.agora - timedelta(hours=6),),
        )
        self.assertIsNone(repo.reler_elegivel(1, self.cursor))
        self.cursor.execute(
            "UPDATE chatbot.historico_mensagens SET received_data_hora=%s WHERE quem_enviou='bot'",
            (self.ancora,),
        )
        self.cursor.execute(
            "UPDATE chatbot.conversa SET last_interaction_at=%s", (self.ancora,)
        )
        self.cursor.execute(
            "UPDATE chatbot.historico_mensagens SET received_data_hora=%s WHERE quem_enviou='cliente'",
            (self.agora - timedelta(hours=24),),
        )
        self.assertIsNone(repo.reler_elegivel(1, self.cursor))

    def test_fila_sem_vinculo_bloqueia_so_o_par_correto(self):
        self.cursor.execute(
            """
            INSERT INTO chatbot.fila_mensagens
                (received_data_hora, cliente_telefone, conteudo_texto, tipo_mensagem,
                 id_hash_msg, id_phone_unidade, unidade_telefone)
            VALUES (%s, '5511999999999', 'Olá', 'text', 'fila-test', 'outra-unidade', 'outro-numero');
        """,
            (self.agora,),
        )
        self.assertIsNotNone(repo.reler_elegivel(1, self.cursor))
        self.cursor.execute(
            "UPDATE chatbot.fila_mensagens SET id_phone_unidade='phone-teste'"
        )
        self.assertIsNone(repo.reler_elegivel(1, self.cursor))

    def test_bloqueios_stage_e_unidade_impedem_despacho(self):
        # Mesmo ativas e não terminais, as etapas a partir do agendamento são excluídas.
        for etapa in range(1, 25):
            with self.subTest(etapa=etapa):
                self.cursor.execute("SAVEPOINT faixa_etapa")
                self.cursor.execute(
                    "UPDATE chatbot.conversa SET id_etapa_atual=%s", (etapa,)
                )
                self.assertEqual(
                    repo.reler_elegivel(1, self.cursor) is not None, etapa < 18
                )
                self.assertEqual(
                    bool(repo.listar_elegiveis(self.cursor, 20)), etapa < 18
                )
                self.cursor.execute("ROLLBACK TO SAVEPOINT faixa_etapa")
        for sql in (
            "UPDATE chatbot.conversa SET followup_stage=1",
            "UPDATE chatbot.conversa SET followup_stage=2",
            "UPDATE chatbot.conversa SET followup_stage=-1",
            "UPDATE chatbot.conversa SET turnos_sem_avanco=12",
            "UPDATE chatbot.conversa SET status_ativa=FALSE",
            "UPDATE chatbot.unidade SET status_pagamento=FALSE",
            "INSERT INTO chatbot.cliente_bloqueado_meta VALUES ('5511999999999','phone-teste')",
        ):
            with self.subTest(sql=sql):
                self.cursor.execute("SAVEPOINT variacao")
                self.cursor.execute(sql)
                self.assertIsNone(repo.reler_elegivel(1, self.cursor))
                self.cursor.execute("ROLLBACK TO SAVEPOINT variacao")

    def test_unicidade_da_ancora_e_rollback_do_historico(self):
        dados = repo.reler_elegivel(1, self.cursor)
        _, versao = tentar_lock_conversa(1, self.cursor)
        envio = {
            "enviou": True,
            "mensagem_bot": "Você viu a minha mensagem?",
            "id_hash_msg_bot": "wamid.followup",
        }
        repo.persistir_followup(dados, envio, versao, self.cursor)
        self.cursor.execute("SAVEPOINT duplicado")
        with self.assertRaises(psycopg.errors.UniqueViolation):
            repo.persistir_followup(dados, envio, versao, self.cursor)
        self.cursor.execute("ROLLBACK TO SAVEPOINT duplicado")
        self.cursor.execute("SELECT count(*) FROM chatbot.followup_envio")
        self.assertEqual(self.cursor.fetchone()[0], 1)

    def test_reset_e_marcador_sao_atomicos(self):
        _, versao = tentar_lock_conversa(1, self.cursor)
        self.cursor.execute(
            "UPDATE chatbot.conversa SET followup_stage=1, followup_last_sent_at=%s",
            (self.agora,),
        )
        contexto = {
            "id_conversa": 1,
            "lock_version": versao,
            "id_etapa_atual": 11,
            "stage_anterior": 1,
            "followup_em": self.agora,
            "mensagem_cliente_atual": {
                "id_mensagem_fila": 10,
                "id_hash_msg": "wamid.reacao",
            },
        }
        self.cursor.execute("SAVEPOINT sem_marcador")
        with self.assertRaises(ValueError):
            repo.concluir_retomada(contexto, self.agora, self.cursor)
        self.cursor.execute("ROLLBACK TO SAVEPOINT sem_marcador")
        self.cursor.execute("SELECT followup_stage FROM chatbot.conversa")
        self.assertEqual(self.cursor.fetchone()[0], 1)
        self.cursor.execute(
            "INSERT INTO chatbot.followup_retomada(id_conversa,id_mensagem_fila,id_hash_cliente,id_etapa,stage_anterior,followup_em) VALUES(1,10,'wamid.reacao',11,1,%s)",
            (self.agora,),
        )
        repo.concluir_retomada(contexto, self.agora, self.cursor)
        self.cursor.execute(
            "SELECT followup_stage,followup_last_sent_at,turnos_sem_avanco,id_etapa_atual FROM chatbot.conversa"
        )
        self.assertEqual(self.cursor.fetchone(), (0, self.agora, 0, 11))

    def test_reacao_real_rollback_e_replay_preservam_ciclo_posterior(self):
        self._verificar_reacao_real(origem=11, destino=11)

    def test_reacao_etapa8_avanca_e_rollback_e_replay_preservam_ciclo(self):
        self._verificar_reacao_real(origem=8, destino=9)

    def test_nome_valido_avanca_e_grava_cliente_com_reset_atomico(self):
        self._verificar_reacao_real(origem=1, destino=2, texto="Antonia")

    def test_triagem_valida_avanca_e_grava_resposta_com_reset_atomico(self):
        self._verificar_reacao_real(origem=12, destino=13, texto="Às vezes")

    def test_tratamento_especifico_preserva_etapa_e_contador(self):
        self._verificar_reacao_real(origem=6, destino=6, texto="Quanto custa?")

    def _verificar_reacao_real(self, *, origem, destino, texto="???"):
        mensagem = {
            "id_mensagem": 10,
            "id_hash": "wamid.reacao",
            "data_recebimento": self.agora,
            "cliente_telefone": "5511999999999",
            "id_phone_unidade": "phone-teste",
            "unidade_telefone": "5511888888888",
            "tipo_mensagem": "text",
            "conteudo_texto": texto,
            "retry_count": 1,
        }
        self.cursor.execute(
            """
            INSERT INTO chatbot.fila_mensagens
                (id_mensagem, id_conversa, received_data_hora, cliente_telefone,
                 conteudo_texto, tipo_mensagem, id_hash_msg, id_phone_unidade,
                 unidade_telefone, status)
            VALUES (10, 1, %s, '5511999999999', %s, 'text',
                    'wamid.reacao', 'phone-teste', '5511888888888', 'processing');
            """,
            (self.agora, texto),
        )
        for followup_em in (None, self.agora):
            with self.subTest(legado=followup_em is None):
                self.cursor.execute("SAVEPOINT ciclo_reacao")
                self.cursor.execute(
                    "UPDATE chatbot.conversa SET followup_stage=1, followup_last_sent_at=%s, turnos_sem_avanco=5, id_etapa_atual=%s",
                    (followup_em, origem),
                )
                _, versao = tentar_lock_conversa(1, self.cursor)
                contexto_banco = repo.reler_conversa(
                    {"conversa": {"id_conversa": 1}, "id_cliente": 1, "id_unidade": 1},
                    versao,
                    self.cursor,
                )
                contexto = preparar_retorno_followup(
                    mensagem, contexto_banco, self.cursor
                )
                with patch.object(cliente_wa, "WhatsApp") as wa:
                    wa.return_value.send_message.return_value = SimpleNamespace(
                        id="wamid.repeticao"
                    )
                    envio = enviar_retorno_followup(contexto)
                self.assertEqual(envio["id_etapa_resultante"], destino)
                self.cursor.execute("SELECT followup_stage FROM chatbot.conversa")
                self.assertEqual(self.cursor.fetchone()[0], 1)

                # Uma falha deve reverter histórico, avanço (na etapa 8) e reset juntos.
                self.cursor.execute("SAVEPOINT confirmacao")
                persistir_retorno_followup(contexto, envio, self.cursor)
                self.cursor.execute("ROLLBACK TO SAVEPOINT confirmacao")
                self.cursor.execute(
                    "SELECT followup_stage, id_etapa_atual, turnos_sem_avanco FROM chatbot.conversa"
                )
                self.assertEqual(self.cursor.fetchone(), (1, origem, 5))
                self.cursor.execute(
                    "SELECT concluida_em FROM chatbot.followup_retomada"
                )
                self.assertIsNone(self.cursor.fetchone()[0])
                self.cursor.execute("SELECT count(*) FROM chatbot.historico_mensagens")
                self.assertEqual(self.cursor.fetchone()[0], 3)

                persistir_retorno_followup(contexto, envio, self.cursor)
                self.cursor.execute(
                    "SELECT followup_stage,followup_last_sent_at,turnos_sem_avanco,id_etapa_atual FROM chatbot.conversa"
                )
                self.assertEqual(
                    self.cursor.fetchone(),
                    (0, followup_em, 0 if origem != destino else 5, destino),
                )
                if origem == 1:
                    self.cursor.execute(
                        "SELECT nome FROM chatbot.cliente WHERE id_cliente=1"
                    )
                    self.assertEqual(self.cursor.fetchone()[0], "Antonia")
                if origem == 12:
                    self.cursor.execute(
                        "SELECT resposta FROM chatbot.respostas_desafios WHERE id_conversa=1 AND id_etapa=12"
                    )
                    self.assertEqual(self.cursor.fetchone()[0], "às vezes")
                self.cursor.execute(
                    "SELECT conteudo_texto, id_etapa FROM chatbot.historico_mensagens WHERE id_hash_msg='wamid.repeticao'"
                )
                self.assertEqual(
                    self.cursor.fetchone(), (envio["mensagem_bot"], destino)
                )
                self.cursor.execute(
                    "SELECT id_etapa FROM chatbot.historico_mensagens WHERE id_hash_msg='wamid.reacao'"
                )
                self.assertEqual(self.cursor.fetchone()[0], origem)
                self.cursor.execute(
                    "SELECT id_etapa, concluida_em FROM chatbot.followup_retomada"
                )
                etapa_checkpoint, concluida_em = self.cursor.fetchone()
                self.assertEqual(etapa_checkpoint, origem)
                self.assertIsNotNone(concluida_em)

                # Simula recuperação da mesma fila após outro ciclo já ter começado.
                self.cursor.execute(
                    "UPDATE chatbot.conversa SET followup_stage=1, followup_last_sent_at=%s, id_etapa_atual=10",
                    (self.agora + timedelta(hours=1),),
                )
                self.cursor.execute("SELECT to_jsonb(c) FROM chatbot.conversa c")
                antes_replay = self.cursor.fetchone()[0]
                contexto_banco = repo.reler_conversa(
                    contexto_banco, versao, self.cursor
                )
                contexto = preparar_retorno_followup(
                    mensagem, contexto_banco, self.cursor
                )
                self.assertIsNotNone(contexto["resposta_bot_para_mensagem_atual"])
                final = persistir_retorno_followup(
                    contexto,
                    {"enviou": False, "id_hash_msg_bot": "wamid.repeticao"},
                    self.cursor,
                )
                self.assertTrue(final["resposta_ja_existia"])
                self.assertEqual(final["id_etapa_resultante"], destino)
                self.cursor.execute("SELECT to_jsonb(c) FROM chatbot.conversa c")
                self.assertEqual(self.cursor.fetchone()[0], antes_replay)
                self.cursor.execute("SELECT count(*) FROM chatbot.historico_mensagens")
                self.assertEqual(self.cursor.fetchone()[0], 4)
                self.cursor.execute("ROLLBACK TO SAVEPOINT ciclo_reacao")

    def test_dois_processos_lock_recusa_e_fencing(self):
        # ROLLBACK remove apenas a fixture desta função. A conversa-base é confirmada.
        self.conn.rollback()
        ok, antiga = tentar_lock_conversa(1, self.cursor)
        self.assertTrue(ok)
        self.conn.commit()
        try:
            with psycopg.connect(DSN, connect_timeout=5) as outro:
                with outro.cursor() as cursor:
                    self.assertFalse(tentar_lock_conversa(1, cursor)[0])
                    cursor.execute(
                        "UPDATE chatbot.conversa SET processing_started_at=clock_timestamp()-INTERVAL '111 seconds' WHERE id_conversa=1"
                    )
                    ok, nova = tentar_lock_conversa(1, cursor)
                    self.assertTrue(ok)
                    self.assertGreater(nova, antiga)
            with self.assertRaises(repo.LockConversaPerdido):
                repo.proteger_conversa(1, antiga, self.cursor)
            self.assertFalse(unlock_conversa(1, antiga, self.cursor))
        finally:
            self.conn.rollback()
            self.cursor.execute(
                "UPDATE chatbot.conversa SET processing=FALSE, processing_started_at=NULL WHERE id_conversa=1"
            )
            self.conn.commit()


@unittest.skipUnless(DSN, "Defina FOLLOWUP_TEST_DSN para PostgreSQL local descartável")
class MigracaoLegadoPostgresTests(unittest.TestCase):
    def setUp(self):
        # Reutiliza a base real e as verificações de banco vazio/loopback.
        FollowupPostgresTests.setUpClass.__func__(type(self))
        self.addCleanup(self.limpar_banco)
        self.cursor.execute(
            "DROP TABLE chatbot.followup_envio, chatbot.followup_retomada, chatbot.followup_legado"
        )
        self.cursor.execute(
            """
            INSERT INTO chatbot.cliente(id_cliente, waid_telefone, nome)
            VALUES (2,'5511999999992','Bia'), (3,'5511999999993','Caio'), (4,'5511999999994','Davi');
            INSERT INTO chatbot.chat(id_cliente,id_unidade) VALUES(2,1),(3,1),(4,1);
            INSERT INTO chatbot.conversa(id_conversa,id_chat,id_cliente,id_unidade,id_etapa_atual,status_ativa,followup_stage)
            SELECT v.cid,h.id_chat,v.cid,1,v.etapa,v.ativa,v.stage FROM
                (VALUES(2,18,TRUE,NULL::INTEGER),(3,11,FALSE,0),(4,11,TRUE,2)) v(cid,etapa,ativa,stage)
                JOIN chatbot.chat h ON h.id_cliente=v.cid AND h.id_unidade=1;
        """
        )
        self.conn.commit()

    def limpar_banco(self):
        FollowupPostgresTests.tearDownClass.__func__(type(self))

    def executar_migracao(self):
        self.cursor.execute(MIGRACAO.read_text(encoding="utf-8"), prepare=False)
        while self.cursor.nextset():
            pass

    def test_marca_ativas_preserva_dados_e_nao_reaplica(self):
        self.cursor.execute(
            "SELECT id_conversa, to_jsonb(c) FROM chatbot.conversa c ORDER BY id_conversa"
        )
        antes = dict(self.cursor.fetchall())
        self.conn.commit()
        self.executar_migracao()
        self.cursor.execute(
            "SELECT id_conversa, to_jsonb(c) FROM chatbot.conversa c ORDER BY id_conversa"
        )
        depois = dict(self.cursor.fetchall())
        for id_conversa, original in antes.items():
            esperado = dict(original)
            if original["status_ativa"]:
                esperado["followup_stage"] = 1
            self.assertEqual(depois[id_conversa], esperado)
        self.cursor.execute(
            "SELECT id_conversa,stage_anterior FROM chatbot.followup_legado ORDER BY id_conversa"
        )
        self.assertEqual(self.cursor.fetchall(), [(1, 0), (2, None), (4, 2)])
        self.cursor.execute(
            "SELECT (SELECT COUNT(*) FROM chatbot.followup_envio), (SELECT COUNT(*) FROM chatbot.historico_mensagens)"
        )
        self.assertEqual(self.cursor.fetchone(), (0, 0))
        self.cursor.execute(
            "UPDATE chatbot.conversa SET followup_stage=0 WHERE id_conversa=1"
        )
        self.cursor.execute(
            """
            INSERT INTO chatbot.cliente(id_cliente,waid_telefone) VALUES(5,'5511999999995');
            INSERT INTO chatbot.chat(id_cliente,id_unidade) VALUES(5,1);
            INSERT INTO chatbot.conversa(id_conversa,id_chat,id_cliente,id_unidade,id_etapa_atual)
            SELECT 5,id_chat,5,1,1 FROM chatbot.chat WHERE id_cliente=5 AND id_unidade=1;
        """
        )
        self.conn.commit()
        with self.assertRaises(psycopg.errors.DuplicateTable):
            self.executar_migracao()
        self.conn.rollback()
        self.cursor.execute(
            "SELECT id_conversa,followup_stage FROM chatbot.conversa WHERE id_conversa IN (1,5) ORDER BY id_conversa"
        )
        self.assertEqual(self.cursor.fetchall(), [(1, 0), (5, 0)])

    def test_legado_terminal_recusa_migracao_sem_marcar_ninguem(self):
        self.cursor.execute(
            "UPDATE chatbot.conversa SET id_etapa_atual=22 WHERE id_conversa=1"
        )
        self.conn.commit()
        with self.assertRaises(psycopg.errors.RaiseException):
            self.executar_migracao()
        self.conn.rollback()
        self.cursor.execute(
            "SELECT followup_stage FROM chatbot.conversa WHERE id_conversa=1"
        )
        self.assertEqual(self.cursor.fetchone(), (0,))
        self.cursor.execute("SELECT to_regclass('chatbot.followup_legado')")
        self.assertIsNone(self.cursor.fetchone()[0])


@unittest.skipUnless(DSN, "Defina FOLLOWUP_TEST_DSN para PostgreSQL local descartável")
class MigracaoSegundoFollowupTests(unittest.TestCase):
    def test_migracao_completa_preserva_dados_e_amplia_somente_motivo(self):
        FollowupPostgresTests.setUpClass.__func__(type(self))
        self.addCleanup(FollowupPostgresTests.tearDownClass.__func__, type(self))
        self.cursor.execute("""
            ALTER TABLE chatbot.conversa DROP CONSTRAINT ck_conversa_motivo_encerramento;
            ALTER TABLE chatbot.conversa ADD CONSTRAINT ck_conversa_motivo_encerramento
                CHECK(motivo_encerramento IS NULL OR motivo_encerramento IN
                    ('idade_invalida','foi_agendado','encaminhado_suporte_idoso'));
            SELECT to_jsonb(c) FROM chatbot.conversa c;
        """)
        while self.cursor.nextset():
            pass
        antes = self.cursor.fetchone()[0]
        with self.assertRaisesRegex(ValueError, "SCHEMA_SEGUNDO_FOLLOWUP_AUSENTE"):
            repo.validar_schema_followup(self.cursor)
        self.conn.commit()
        sql = (MIGRACAO.parent / "20260924_segundo_followup.sql").read_text(encoding="utf-8")
        self.cursor.execute(sql, prepare=False)
        while self.cursor.nextset():
            pass
        self.cursor.execute("SELECT to_jsonb(c) FROM chatbot.conversa c")
        self.assertEqual(self.cursor.fetchone()[0], antes)
        repo.validar_schema_followup(self.cursor)
        self.cursor.execute("UPDATE chatbot.conversa SET motivo_encerramento='followup_sem_resposta'")
        self.cursor.execute("SELECT motivo_encerramento FROM chatbot.conversa")
        self.assertEqual(self.cursor.fetchone()[0], "followup_sem_resposta")
        self.cursor.execute("SAVEPOINT motivo_invalido")
        with self.assertRaises(psycopg.errors.CheckViolation):
            self.cursor.execute("UPDATE chatbot.conversa SET motivo_encerramento='motivo_invalido'")
        self.cursor.execute("ROLLBACK TO SAVEPOINT motivo_invalido")


if __name__ == "__main__":
    unittest.main()
```

## Passo 49 — Substituir integralmente `tests/integration/test_reserva_link_postgres.py`

```python
"""DDL final e SQL de runtime; não executa migração nem usa banco de produção."""

from contextlib import contextmanager
from datetime import timedelta
import os
import unittest
from unittest.mock import patch

import psycopg
from tests.fixtures.fireads import aplicar_fireads
from psycopg.conninfo import conninfo_to_dict
from core.database.deploy_database import (
    bank_script,
    povoar_etapas,
    etapa_transicao_script,
)
from core.repositories.atendimento import followup
from core.repositories.atendimento.turnos import salvar_turno_conversa
from core.repositories.fluxo.contextos.etapa18 import buscar_contexto_etapa18
from core.repositories.fluxo.contextos.etapa20 import buscar_contexto_etapa20
from core.repositories.funil import envios, leads
from core.repositories.monitoramento.painel import listar_conversas
from workers.worker_flow.transacoes.efeitos_transicao import (
    atualizar_banco_conforme_transicao_de_etapa,
)

DSN = os.environ.get("RESERVA_LINK_TEST_DSN")


@unittest.skipUnless(DSN, "Exige banco loopback vazio test_chatbot_reserva_link")
class ReservaLinkPostgresTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        params = conninfo_to_dict(DSN)
        locais = {"127.0.0.1", "::1", "localhost"}
        if (
            params.get("host") not in locais
            or params.get("dbname") != "test_chatbot_reserva_link"
            or params.get("service")
            or (params.get("hostaddr") and params["hostaddr"] not in locais)
        ):
            raise RuntimeError(
                "Teste exige loopback explícito e test_chatbot_reserva_link"
            )
        cls.conn = psycopg.connect(DSN, connect_timeout=5)
        cls.cursor = cls.conn.cursor()
        if (
            cls.conn.info.host not in locais
            or cls.conn.info.dbname != "test_chatbot_reserva_link"
        ):
            cls.conn.close()
            raise RuntimeError("Conexão efetiva não corresponde ao banco de teste")
        if (
            cls.conn.execute("SELECT to_regnamespace('chatbot')").fetchone()[0]
            is not None
        ):
            cls.conn.close()
            raise RuntimeError("Recusado schema chatbot preexistente")
        cls.conn.execute(
            "CREATE SCHEMA chatbot; CREATE TABLE chatbot.auth_user(id SERIAL PRIMARY KEY)"
        )

        @contextmanager
        def transacao(*_):
            yield cls.cursor

        with patch.object(bank_script, "transacao_deploy", transacao), patch.object(
            povoar_etapas, "transacao_deploy", transacao
        ), patch.object(etapa_transicao_script, "transacao_deploy", transacao):
            bank_script.criar_tabelas()
            povoar_etapas.insere_etapa_once()
            etapa_transicao_script.criar_e_povoar_transicoes_etapa()
        cls.conn.execute("""
            CREATE TABLE chatbot.cliente_bloqueado_meta(wa_id_cliente TEXT, phone_id_unidade TEXT);
            CREATE TABLE chatbot.webhook_flood_evento(wa_id_cliente TEXT, phone_id_unidade TEXT, received_at TIMESTAMPTZ);
            INSERT INTO chatbot.unidade(id_unidade,nome_unidade,nome_agente,genero,cnpj,email_responsavel,
                telefone,numero_comercial,waba_id,phone_number_id,link_agendamento)
            VALUES (1,'Unidade','Suh','feminino','cnpj','unidade@example.com','5571888888888',
                '5571999999999','waba','phone',NULL);
            INSERT INTO chatbot.cliente(id_cliente,nome,waid_telefone,idade,email)
                VALUES (1,'Ana','5571777777777',40,'ana@example.com');
            INSERT INTO chatbot.conversa(id_conversa,id_cliente,id_unidade,id_etapa_atual,profissao)
                VALUES (1,1,1,17,'Professora');
            INSERT INTO chatbot.integracao_funil_unidade(id_unidade,nome_widget,codigo_widget,link_api_carrossel,codigo_canal_venda)
                VALUES (1,'Widget','cod','https://example.com/api','canal');
        """)
        aplicar_fireads(cls.cursor)
        cls.conn.commit()

    @classmethod
    def tearDownClass(cls):
        cls.conn.rollback()
        cls.conn.execute("DROP SCHEMA chatbot CASCADE")
        cls.conn.commit()
        cls.conn.close()

    def tearDown(self):
        self.conn.rollback()

    def configurar(self, link, etapa):
        self.cursor.execute(
            "UPDATE chatbot.atendimento_customizado SET link_agendamento=%s WHERE id_unidade=1", (link,)
        )
        self.cursor.execute(
            "UPDATE chatbot.conversa SET id_etapa_atual=%s,lead_no_funil=FALSE WHERE id_conversa=1",
            (etapa,),
        )
        self.cursor.execute("DELETE FROM chatbot.funil_envios")

    def test_matriz_funil_na_fila_claim_leitura_e_confirmacao(self):
        for link in (None, "", "https://example.com"):
            for etapa in range(17, 25):
                with self.subTest(link=link, etapa=etapa):
                    self.configurar(link, etapa)
                    esperado = etapa >= 20 if link else etapa == 19 or etapa >= 21
                    self.assertEqual(
                        envios.sincronizar_envios_elegiveis(self.cursor), int(esperado)
                    )
                    envio = envios.reivindicar_proximo_envio(self.cursor)
                    lead = leads.buscar_dados_lead_funil(1, self.cursor)
                    self.assertEqual(envio is not None, esperado)
                    self.assertEqual(lead is not None, esperado)
                    if esperado:
                        self.assertEqual(lead["link_agendamento"], link or None)
                        self.assertTrue(
                            envios.marcar_envio_como_concluido(
                                envio["id_funil_envio"], 1, "ok", self.cursor
                            )
                        )
                        self.assertEqual(
                            envios.sincronizar_envios_elegiveis(self.cursor), 0
                        )

    def test_funil_pendente_revalida_link_adicionado(self):
        self.configurar(None, 19)
        self.assertEqual(envios.sincronizar_envios_elegiveis(self.cursor), 1)
        self.conn.execute(
            "UPDATE chatbot.atendimento_customizado SET link_agendamento='https://example.com' WHERE id_unidade=1"
        )
        self.assertIsNone(envios.reivindicar_proximo_envio(self.cursor))
        self.assertIsNone(leads.buscar_dados_lead_funil(1, self.cursor))
        self.conn.execute(
            "UPDATE chatbot.conversa SET id_etapa_atual=21 WHERE id_conversa=1"
        )
        self.assertIsNotNone(envios.reivindicar_proximo_envio(self.cursor))

    def test_aceite_externo_e_confirmado_mesmo_com_link_adicionado(self):
        self.configurar(None, 19)
        self.assertEqual(envios.sincronizar_envios_elegiveis(self.cursor), 1)
        envio = envios.reivindicar_proximo_envio(self.cursor)
        self.assertIsNotNone(leads.buscar_dados_lead_funil(1, self.cursor))
        # Simula a alteração após o despacho que o CRM confirmou com sucesso.
        self.conn.execute(
            "UPDATE chatbot.atendimento_customizado SET link_agendamento='https://example.com' WHERE id_unidade=1"
        )
        self.assertTrue(
            envios.marcar_envio_como_concluido(
                envio["id_funil_envio"],
                1,
                "ok",
                self.cursor,
            )
        )
        self.conn.execute(
            "UPDATE chatbot.conversa SET id_etapa_atual=21 WHERE id_conversa=1"
        )
        self.assertEqual(envios.sincronizar_envios_elegiveis(self.cursor), 0)
        self.assertIsNone(envios.reivindicar_proximo_envio(self.cursor))

    def test_limites_followup_por_configuracao_e_releitura(self):
        agora = self.conn.execute("SELECT clock_timestamp()").fetchone()[0]
        ancora = agora - timedelta(hours=7, minutes=1)
        self.cursor.execute(
            """
            INSERT INTO chatbot.historico_mensagens(id_conversa,id_etapa,received_data_hora,cliente_telefone,
                conteudo_texto,tipo_mensagem,id_hash_msg,id_phone_unidade,unidade_telefone,quem_enviou,status_envio)
            VALUES (1,17,%s,'5571777777777','Oi','text','wamid.cliente','phone','5571888888888','cliente',NULL),
                   (1,17,%s,'5571777777777','Pergunta','text','wamid.bot','phone','5571888888888','bot','sent');
            """,
            (ancora - timedelta(minutes=1), ancora),
        )
        self.cursor.execute(
            "UPDATE chatbot.conversa SET last_message_from='bot',last_interaction_at=%s WHERE id_conversa=1",
            (ancora,),
        )
        for link in (None, "", "https://example.com"):
            for etapa in (1, 17, 18, 19, 20, 21, 24):
                with self.subTest(link=link, etapa=etapa):
                    self.configurar(link, etapa)
                    esperado = etapa <= 17 or etapa == 18 and not link
                    self.assertEqual(
                        followup.reler_elegivel(1, self.cursor) is not None, esperado
                    )
        self.configurar(None, 18)
        self.assertIsNotNone(followup.reler_elegivel(1, self.cursor))
        self.conn.execute(
            "UPDATE chatbot.atendimento_customizado SET link_agendamento='https://example.com' WHERE id_unidade=1"
        )
        self.assertIsNone(followup.reler_elegivel(1, self.cursor))

    def test_turno_dominio_rollback_e_replay(self):
        self.configurar(None, 18)
        for turno in ("manha", "tarde", "noite"):
            with self.conn.transaction():
                self.conn.execute(
                    "UPDATE chatbot.conversa SET turno=NULL WHERE id_conversa=1"
                )
                self.assertTrue(
                    salvar_turno_conversa(1, 1, turno, self.cursor)["turno_persistido"]
                )
                self.assertTrue(
                    salvar_turno_conversa(1, 1, turno, self.cursor)["turno_persistido"]
                )
        self.conn.execute("UPDATE chatbot.conversa SET turno=NULL WHERE id_conversa=1")
        for invalido in ("manha/tarde", "dia", "manhã"):
            with self.assertRaises(psycopg.Error), self.conn.transaction():
                self.conn.execute(
                    "UPDATE chatbot.conversa SET turno=%s WHERE id_conversa=1",
                    (invalido,),
                )
        with self.assertRaisesRegex(RuntimeError, "simulada"), self.conn.transaction():
            self.conn.execute(
                "UPDATE chatbot.conversa SET id_etapa_atual=19 WHERE id_conversa=1"
            )
            atualizar_banco_conforme_transicao_de_etapa(
                {
                    "id_conversa": 1,
                    "id_unidade": 1,
                    "id_etapa_origem_transicao": 18,
                    "texto_cliente_atual": "Pela manhã",
                    "tipo_mensagem_atual": "text",
                },
                {
                    "id_etapa_resultante": 19,
                    "evento_transicao": "turno_escolhido",
                    "resposta_ja_existia": True,
                },
                self.cursor,
            )
            raise RuntimeError("Falha final simulada")
        self.assertEqual(
            self.conn.execute(
                "SELECT id_etapa_atual,turno FROM chatbot.conversa WHERE id_conversa=1"
            ).fetchone(),
            (18, None),
        )

    def test_contexto_painel_e_funil_expoem_turno_sem_cruzar_unidades(self):
        # A plataforma ainda é obrigatória para um novo envio na etapa 20.
        # Removê-la não deve improvisar uma mudança de rota no atendimento ativo.
        self.configurar("https://example.com", 20)
        self.assertEqual(
            buscar_contexto_etapa20(1, 1, self.cursor)["link_agendamento_unidade"],
            "https://example.com",
        )
        self.configurar(None, 20)
        with self.assertRaisesRegex(ValueError, "sem link de agendamento"):
            buscar_contexto_etapa20(1, 1, self.cursor)
        self.configurar(None, 19)
        salvar_turno_conversa(1, 1, "noite", self.cursor)
        self.assertEqual(buscar_contexto_etapa18(1, 1, self.cursor)["turno"], "noite")
        self.assertEqual(
            leads.buscar_dados_lead_funil(1, self.cursor)["turno"], "noite"
        )
        with self.assertRaises(ValueError):
            buscar_contexto_etapa18(1, 2, self.cursor)
        self.conn.execute("""
            INSERT INTO chatbot.historico_mensagens(id_conversa,id_etapa,received_data_hora,cliente_telefone,
                conteudo_texto,tipo_mensagem,id_hash_msg,id_phone_unidade,unidade_telefone,quem_enviou)
            VALUES (1,18,NOW(),'5571777777777','Pela noite','text','wamid.cliente','phone','5571888888888','cliente')
        """)
        fim = self.conn.execute(
            "SELECT clock_timestamp() + INTERVAL '1 minute'"
        ).fetchone()[0]
        dados = listar_conversas(1, None, fim, self.cursor)
        self.assertEqual(dados[0]["turno"], "noite")
        self.assertEqual(listar_conversas(2, None, fim, self.cursor), [])
```

## Passo 50 — Substituir integralmente `tests/integration/test_migracao_reserva_link_postgres.py`

```python
"""Migração real, reversão e retomada; somente PostgreSQL local descartável."""

from copy import deepcopy
from pathlib import Path
import json
import os
import unittest
from unittest.mock import patch

import psycopg
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict

from core.database.deploy_database.etapa_transicao_script import TRANSICOES_INICIAIS
from core.database.deploy_database.povoar_etapas import ETAPAS
from core.repositories.atendimento.conversas import tentar_lock_conversa, unlock_conversa
from tests.fixtures.reserva_migracao import criar_base_legada
from workers.worker_flow.response_flow.flow_sender import flow_sender
from workers.worker_flow.valida_historico import valida_historico


DSN = os.environ.get('MIGRACAO_RESERVA_TEST_DSN')
ROOT = Path(__file__).resolve().parents[2]
MIGRACAO = ROOT / 'deploy/migrations/20261003_reserva_com_sem_link.sql'
REVERSAO = ROOT / 'deploy/rollback/20261003_reserva_com_sem_link.sql'
REFERENCIAS = {
    'conversa': 'id_etapa_atual',
    'historico_mensagens': 'id_etapa',
    'respostas_desafios': 'id_etapa',
    'followup_retomada': 'id_etapa',
}
TABELAS = tuple(REFERENCIAS) + (
    'cliente', 'dependente', 'unidade', 'fila_mensagens', 'pesquisa_satisfacao',
    'funil_envios', 'followup_envio', 'followup_legado', 'consumo_mensal_meta',
    'consumo_meta_coletas',
)


@unittest.skipUnless(DSN, 'Exige MIGRACAO_RESERVA_TEST_DSN local em test_chatbot_migracao_reserva vazio')
class MigracaoReservaLinkPostgresTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        parametros = conninfo_to_dict(DSN)
        locais = {'127.0.0.1', '::1', 'localhost'}
        if (parametros.get('host') not in locais
                or parametros.get('dbname') != 'test_chatbot_migracao_reserva'
                or parametros.get('service')
                or (parametros.get('hostaddr') and parametros['hostaddr'] not in locais)):
            raise RuntimeError('Exige banco descartável test_chatbot_migracao_reserva em loopback')
        cls.conn = psycopg.connect(DSN, autocommit=True, connect_timeout=5)
        if (cls.conn.info.host not in locais
                or cls.conn.info.dbname != 'test_chatbot_migracao_reserva'
                or cls.conn.execute("SELECT to_regnamespace('chatbot')").fetchone()[0] is not None):
            cls.conn.close()
            raise RuntimeError('Banco de teste não está vazio ou não é o destino permitido')

    @classmethod
    def tearDownClass(cls):
        cls.conn.close()

    def setUp(self):
        self.addCleanup(self.limpar)
        criar_base_legada(self.conn)

    def limpar(self):
        self.conn.execute('ROLLBACK')
        # Apenas o schema criado por este teste, no destino validado acima.
        self.conn.execute('DROP SCHEMA chatbot CASCADE')

    def executar(self, caminho=MIGRACAO):
        self.conn.execute(caminho.read_text(encoding='utf-8'), prepare=False)

    def fotografia(self):
        return {
            tabela: [row[0] for row in self.conn.execute(sql.SQL(
                'SELECT to_jsonb(t) FROM chatbot.{} t ORDER BY to_jsonb(t)'
            ).format(sql.Identifier(tabela))).fetchall()]
            for tabela in TABELAS
        }

    def assert_fotografia(self, esperado):
        atual = self.fotografia()
        for tabela in TABELAS:
            with self.subTest(tabela=tabela):
                ordenar = lambda row: json.dumps(row, sort_keys=True)
                self.assertEqual(
                    sorted(atual[tabela], key=ordenar),
                    sorted(esperado[tabela], key=ordenar),
                )

    def test_preserva_dados_particoes_e_ids_e_mapeia_os_significados(self):
        esperado = deepcopy(self.fotografia())
        transicoes_antes = self.conn.execute(
            'SELECT id_transicao,id_etapa_origem,evento,id_etapa_destino FROM chatbot.etapa_transicao ORDER BY id_transicao'
        ).fetchall()
        for tabela, coluna in REFERENCIAS.items():
            for row in esperado[tabela]:
                if row[coluna] is not None and 18 <= row[coluna] <= 22:
                    row[coluna] += 2
                if tabela == 'conversa':
                    row['turno'] = None
        self.executar()
        self.assert_fotografia(esperado)
        self.assertEqual(self.conn.execute('SELECT * FROM chatbot.etapa ORDER BY id_etapa').fetchall(), list(ETAPAS))
        mapa = self.conn.execute(
            'SELECT id_etapa_origem,evento,id_etapa_destino FROM chatbot.etapa_transicao ORDER BY id_etapa_origem,evento'
        ).fetchall()
        # A migração de reserva precede os dois atalhos adicionados pela FireAds.
        self.assertEqual(mapa, sorted(
            t for t in TRANSICOES_INICIAIS if not t[1].endswith('_email_fireads')
        ))
        for id_transicao, origem, evento, destino in transicoes_antes:
            self.assertEqual(self.conn.execute(
                'SELECT id_etapa_origem,evento,id_etapa_destino FROM chatbot.etapa_transicao WHERE id_transicao=%s',
                (id_transicao,),
            ).fetchone(), (origem + (2 if origem >= 18 else 0), evento, destino + (2 if destino >= 18 else 0)))
        self.assertEqual(self.conn.execute(
            'SELECT tableoid::regclass::text,COUNT(*) FROM chatbot.historico_mensagens GROUP BY tableoid ORDER BY 1'
        ).fetchall(), [('chatbot.historico_mensagens_202610', 5), ('chatbot.historico_mensagens_default', 5)])
        with self.assertRaises(psycopg.errors.CheckViolation):
            self.conn.execute("UPDATE chatbot.conversa SET turno='dia' WHERE id_conversa=18")

    def test_reexecucao_nao_desloca_novamente_nem_apaga_preferencias(self):
        self.executar()
        self.conn.execute("UPDATE chatbot.conversa SET id_etapa_atual=19,turno='manha' WHERE id_conversa=18")
        self.conn.execute('UPDATE chatbot.unidade SET link_agendamento=NULL')
        antes = self.fotografia()
        self.executar()
        self.assert_fotografia(antes)

    def test_reversao_antes_de_novos_atendimentos_e_reexecutavel(self):
        antes = self.fotografia()
        etapas = self.conn.execute('SELECT * FROM chatbot.etapa ORDER BY id_etapa').fetchall()
        mapa = self.conn.execute('SELECT * FROM chatbot.etapa_transicao ORDER BY id_transicao').fetchall()
        self.executar()
        self.executar(REVERSAO)
        self.assert_fotografia(antes)
        self.assertEqual(self.conn.execute('SELECT * FROM chatbot.etapa ORDER BY id_etapa').fetchall(), etapas)
        self.assertEqual(self.conn.execute('SELECT * FROM chatbot.etapa_transicao ORDER BY id_transicao').fetchall(), mapa)
        self.executar(REVERSAO)
        self.assert_fotografia(antes)

    def test_reversao_recusa_dados_da_nova_rota_sem_apagar_nada(self):
        self.executar()
        self.conn.execute("UPDATE chatbot.conversa SET id_etapa_atual=19,turno='tarde' WHERE id_conversa=18")
        antes = self.fotografia()
        with self.assertRaisesRegex(psycopg.errors.RaiseException, 'Reversão recusada'):
            self.executar(REVERSAO)
        self.conn.execute('ROLLBACK')
        self.assert_fotografia(antes)

    def test_catalogo_desconhecido_aborta_sem_alteracoes_parciais(self):
        self.conn.execute("UPDATE chatbot.etapa SET nome_etapa='Configuração não mapeada' WHERE id_etapa=18")
        antes = self.fotografia()
        with self.assertRaisesRegex(psycopg.errors.RaiseException, 'Catálogo/mapa diferente'):
            self.executar()
        self.conn.execute('ROLLBACK')
        self.assert_fotografia(antes)

    def test_fk_desconhecida_com_set_null_aborta_antes_de_apagar_vinculo(self):
        self.conn.execute('CREATE TABLE chatbot.referencia_extra(id INTEGER PRIMARY KEY, etapa INTEGER REFERENCES chatbot.etapa ON DELETE SET NULL)')
        self.conn.execute('INSERT INTO chatbot.referencia_extra VALUES(1,18)')
        with self.assertRaisesRegex(psycopg.errors.RaiseException, 'Referências de etapa não mapeadas'):
            self.executar()
        self.conn.execute('ROLLBACK')
        self.assertEqual(self.conn.execute('SELECT * FROM chatbot.referencia_extra').fetchall(), [(1,18)])
        self.assertEqual(self.conn.execute('SELECT id_etapa_atual FROM chatbot.conversa WHERE id_conversa=18').fetchone(), (18,))

    def test_resposta_migrada_e_reaproveitada_mesmo_apos_remocao_do_link(self):
        self.executar()
        self.conn.execute('UPDATE chatbot.unidade SET link_agendamento=NULL')
        conversa = self.conn.execute('SELECT to_jsonb(c) FROM chatbot.conversa c WHERE id_conversa=18').fetchone()[0]
        recebido = self.conn.execute('SELECT received_data_hora FROM chatbot.fila_mensagens WHERE id_mensagem=18').fetchone()[0]
        mensagem = {
            'id_mensagem': 18, 'id_hash': 'wamid.cliente.18', 'data_recebimento': recebido,
            'cliente_telefone': '5511999999918', 'id_phone_unidade': 'phone',
            'unidade_telefone': '5511888888888', 'tipo_mensagem': 'text',
            'conteudo_texto': 'Já reservei', 'retry_count': 2,
        }
        with self.conn.cursor() as cursor, patch(
            'workers.worker_flow.valida_historico.buscar_contexto_etapa20',
            side_effect=AssertionError('Replay não precisa do link para novo envio'),
        ), patch('workers.worker_flow.response_flow.flow_sender.resolve_etapa20') as resolver:
            contexto = valida_historico(mensagem, {
                'id_cliente': 18, 'id_unidade': 1, 'conversa': conversa,
            }, cursor)
            envio = flow_sender(contexto)
        resolver.assert_not_called()
        self.assertTrue(envio['resposta_ja_existia'])
        self.assertEqual(envio['id_etapa_resultante'], 21)
        self.assertEqual(envio['evento_transicao'], 'agendamento_confirmado')

    def test_locks_fila_e_fencing_continuam_funcionando_apos_remapeamento(self):
        self.executar()
        with self.conn.cursor() as cursor:
            ok, nova_versao = tentar_lock_conversa(18, cursor)
            self.assertTrue(ok)
            self.assertGreater(nova_versao, 8)
            self.assertFalse(unlock_conversa(18, 8, cursor))
            self.assertTrue(unlock_conversa(18, nova_versao, cursor))
        self.assertEqual(self.conn.execute(
            'SELECT id_etapa_atual,status_ativa,followup_stage FROM chatbot.conversa WHERE id_conversa=22'
        ).fetchone(), (24,False,1))
```

## Passo 51 — Substituir integralmente `tests/integration/test_suporte_por_idade_postgres.py`

```python
"""Migração real somente em PostgreSQL local descartável explicitamente indicado."""

from contextlib import contextmanager
from datetime import datetime, timezone
import os
from pathlib import Path
import re
import unittest
from unittest.mock import patch

import psycopg
from psycopg.conninfo import conninfo_to_dict

from core.database.deploy_database import bank_script
from core.repositories.fluxo.contextos.etapa6 import buscar_contexto_etapa6
from core.repositories.monitoramento import painel


DSN = os.environ.get('SUPORTE_IDADE_TEST_DSN')
MIGRACAO = Path(__file__).resolve().parents[2] / 'deploy/migrations/20260911_idade_minima_suporte.sql'
REVERSAO = Path(__file__).resolve().parents[2] / 'deploy/rollback/20260911_idade_minima_suporte.sql'


@unittest.skipUnless(DSN, 'Defina SUPORTE_IDADE_TEST_DSN para banco local vazio test_chatbot_suporte_idade')
class SuporteIdadePostgresTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        params = conninfo_to_dict(DSN)
        locais = {'127.0.0.1', '::1', 'localhost'}
        if (params.get('host') not in locais
                or params.get('dbname') != 'test_chatbot_suporte_idade'
                or (params.get('hostaddr') and params['hostaddr'] not in locais)
                or params.get('service')):
            raise RuntimeError('Exige host loopback explícito e dbname=test_chatbot_suporte_idade')
        cls.conn = psycopg.connect(DSN, connect_timeout=5, autocommit=True)
        if cls.conn.info.host not in locais or cls.conn.info.dbname != 'test_chatbot_suporte_idade':
            cls.conn.close()
            raise RuntimeError('Conexão efetiva não corresponde ao banco descartável')
        if cls.conn.execute("SELECT to_regnamespace('chatbot')").fetchone()[0] is not None:
            cls.conn.close()
            raise RuntimeError('Schema chatbot já existe: use um banco de teste vazio')

    @classmethod
    def tearDownClass(cls):
        cls.conn.close()

    def setUp(self):
        self.conn.execute('CREATE SCHEMA chatbot')
        self.addCleanup(self.limpar_schema)
        self.conn.execute('''CREATE TABLE chatbot.unidade (
            id_unidade SERIAL PRIMARY KEY, nome_unidade TEXT NOT NULL,
            suporte_idoso BOOLEAN NOT NULL DEFAULT FALSE,
            email_obrigatorio BOOLEAN NOT NULL DEFAULT TRUE,
            bpa_ativo BOOLEAN NOT NULL DEFAULT FALSE,
            numero_comercial TEXT
        );
        INSERT INTO chatbot.unidade(nome_unidade, suporte_idoso, email_obrigatorio, numero_comercial)
        VALUES ('Ativa', TRUE, FALSE, '5571999999999'), ('Desativada', FALSE, TRUE, NULL);
        CREATE TABLE chatbot.conversa (id_conversa INTEGER, followup_stage INTEGER, status_ativa BOOLEAN);
        INSERT INTO chatbot.conversa VALUES (1, 1, TRUE), (2, 0, FALSE);
        ''')

    def limpar_schema(self):
        self.conn.execute('ROLLBACK')
        # Este schema foi criado pelo próprio teste após recusar um preexistente.
        self.conn.execute('DROP SCHEMA chatbot CASCADE')

    def migrar(self, sql=None):
        self.conn.execute(sql or MIGRACAO.read_text(encoding='utf-8'))

    def assert_dominio(self):
        for idade in (None, 50, 60, 70, 80, 90):
            self.conn.execute('UPDATE chatbot.unidade SET idade_minima_suporte=%s WHERE id_unidade=1', (idade,))
        for idade in (0, -1, 49, 55, 100):
            with self.assertRaises(psycopg.errors.CheckViolation):
                self.conn.execute('UPDATE chatbot.unidade SET idade_minima_suporte=%s WHERE id_unidade=1', (idade,))

    def test_conversao_preserva_unidades_conversas_e_dominio(self):
        self.migrar()
        self.assertEqual(self.conn.execute('''SELECT idade_minima_suporte, email_obrigatorio,
            bpa_ativo, numero_comercial FROM chatbot.unidade ORDER BY id_unidade''').fetchall(),
            [(60, False, False, '5571999999999'), (None, True, False, None)])
        self.assertEqual(self.conn.execute('SELECT * FROM chatbot.conversa ORDER BY id_conversa').fetchall(),
                         [(1, 1, True), (2, 0, False)])
        self.assert_dominio()
        self.conn.execute("INSERT INTO chatbot.unidade(nome_unidade) VALUES ('Nova')")
        self.assertIsNone(self.conn.execute("SELECT idade_minima_suporte FROM chatbot.unidade WHERE nome_unidade='Nova'").fetchone()[0])

    def test_reaplicacao_recusada_sem_perder_configuracao_nova(self):
        self.migrar()
        self.conn.execute('UPDATE chatbot.unidade SET idade_minima_suporte=70 WHERE id_unidade=1')
        with self.assertRaisesRegex(psycopg.Error, 'já aplicada ou schema parcial'):
            self.migrar()
        self.conn.execute('ROLLBACK')
        self.assertEqual(self.conn.execute('SELECT idade_minima_suporte FROM chatbot.unidade WHERE id_unidade=1').fetchone()[0], 70)

    def test_schema_parcial_recusado(self):
        self.conn.execute('ALTER TABLE chatbot.unidade ADD COLUMN idade_minima_suporte INTEGER')
        with self.assertRaisesRegex(psycopg.Error, 'schema parcial'):
            self.migrar()
        self.conn.execute('ROLLBACK')
        self.assertEqual(self.conn.execute('SELECT suporte_idoso FROM chatbot.unidade ORDER BY id_unidade').fetchall(), [(True,), (False,)])

    def test_falha_pos_conversao_reverte_toda_a_transacao(self):
        sql = MIGRACAO.read_text(encoding='utf-8').replace(
            'DO $poscondicoes$\nBEGIN',
            "DO $poscondicoes$\nBEGIN\n    RAISE EXCEPTION 'Falha injetada de teste';",
        )
        with self.assertRaisesRegex(psycopg.Error, 'Falha injetada'):
            self.migrar(sql)
        self.conn.execute('ROLLBACK')
        self.assertEqual(self.conn.execute('SELECT suporte_idoso FROM chatbot.unidade ORDER BY id_unidade').fetchall(), [(True,), (False,)])
        self.assertEqual(self.conn.execute("""SELECT COUNT(*) FROM information_schema.columns
            WHERE table_schema='chatbot' AND table_name='unidade' AND column_name='idade_minima_suporte'""").fetchone()[0], 0)

    def test_instalacao_limpa_usa_o_mesmo_dominio(self):
        comandos = []

        class CapturaDDL:
            def execute(self, sql, *args): comandos.append(sql)

        @contextmanager
        def capturar(*args): yield CapturaDDL()

        with patch.object(bank_script, 'transacao_deploy', capturar):
            bank_script.criar_tabelas()
        ddl_unidade = re.search(
            r'CREATE TABLE IF NOT EXISTS chatbot\.unidade\s*\(.*?\n\s*\);',
            '\n'.join(comandos), re.S,
        ).group(0)
        self.conn.execute('DROP TABLE chatbot.unidade; CREATE TABLE chatbot.auth_user (id SERIAL PRIMARY KEY)')
        self.conn.execute(ddl_unidade)
        self.conn.execute('''INSERT INTO chatbot.unidade
            (id_unidade, nome_unidade, nome_agente, genero, cnpj, email_responsavel, telefone,
             waba_id, phone_number_id, link_agendamento, numero_comercial)
            VALUES (1, 'Nova', 'Suh', 'feminino', 'teste', 'teste@example.com', '5571999999999',
                    'waba', 'phone', 'https://example.com', '5571999999999')''')
        self.assertIsNone(self.conn.execute('SELECT idade_minima_suporte FROM chatbot.unidade').fetchone()[0])
        for limite in (None, 50, 60, 70, 80):
            self.conn.execute('UPDATE chatbot.unidade SET idade_minima_suporte=%s', (limite,))
        with self.assertRaises(psycopg.errors.CheckViolation):
            self.conn.execute('UPDATE chatbot.unidade SET idade_minima_suporte=90')

    def test_reversao_preserva_politica_null_60(self):
        self.migrar()
        self.conn.execute(REVERSAO.read_text(encoding='utf-8'))
        self.assertEqual(self.conn.execute(
            'SELECT suporte_idoso, email_obrigatorio FROM chatbot.unidade ORDER BY id_unidade'
        ).fetchall(), [(True, False), (False, True)])

    def test_reversao_recusa_faixas_novas(self):
        self.migrar()
        for limite in (50, 70, 80, 90):
            self.conn.execute('UPDATE chatbot.unidade SET idade_minima_suporte=%s WHERE id_unidade=1', (limite,))
            with self.assertRaisesRegex(psycopg.Error, 'Há faixas novas configuradas'):
                self.conn.execute(REVERSAO.read_text(encoding='utf-8'))
            self.conn.execute('ROLLBACK')
            self.assertEqual(self.conn.execute('SELECT idade_minima_suporte FROM chatbot.unidade WHERE id_unidade=1').fetchone()[0], limite)

    def test_lock_ocupado_aborta_sem_converter_a_coluna(self):
        with psycopg.connect(DSN, connect_timeout=5) as concorrente:
            concorrente.execute('SELECT * FROM chatbot.unidade')
            with self.assertRaises(psycopg.errors.LockNotAvailable):
                self.migrar()
            self.conn.execute('ROLLBACK')
        self.assertEqual(self.conn.execute(
            'SELECT suporte_idoso FROM chatbot.unidade ORDER BY id_unidade'
        ).fetchall(), [(True,), (False,)])

    def test_falha_na_reversao_preserva_schema_e_valores_novos(self):
        self.migrar()
        sql = REVERSAO.read_text(encoding='utf-8').replace(
            'DO $conferencia$\nBEGIN',
            "DO $conferencia$\nBEGIN\n    RAISE EXCEPTION 'Falha na reversão';",
        )
        with self.assertRaisesRegex(psycopg.Error, 'Falha na reversão'):
            self.conn.execute(sql)
        self.conn.execute('ROLLBACK')
        self.assertEqual(self.conn.execute(
            'SELECT idade_minima_suporte FROM chatbot.unidade ORDER BY id_unidade'
        ).fetchall(), [(60,), (None,)])
        self.assert_dominio()

    def test_contexto_e_relatorio_no_schema_completo_migrado(self):
        # Usa o DDL real e a reversão para montar a estrutura anterior completa.
        self.conn.execute('''
            DROP TABLE chatbot.conversa, chatbot.unidade;
            CREATE TABLE chatbot.auth_user (id SERIAL PRIMARY KEY);
        ''')

        @contextmanager
        def transacao_local(*_):
            with self.conn.cursor() as cursor:
                yield cursor

        with patch.object(bank_script, 'transacao_deploy', transacao_local):
            bank_script.criar_tabelas()
        self.conn.execute(REVERSAO.read_text(encoding='utf-8'))
        self.conn.execute('''
            INSERT INTO chatbot.unidade
                (id_unidade, nome_unidade, nome_agente, genero, cnpj,
                 email_responsavel, telefone, waba_id, phone_number_id,
                 link_agendamento, numero_comercial, suporte_idoso)
            SELECT n, 'Teste ' || n, 'Suh', 'feminino', 'cnpj-' || n,
                   'teste' || n || '@example.com', '557199999999' || n,
                   'waba-' || n, 'phone-' || n,
                   'https://example.com/agendar/' || n, '5571999999999', TRUE
              FROM generate_series(1, 2) AS n;
            INSERT INTO chatbot.etapa (id_etapa, nome_etapa)
            VALUES (6, 'Idade');
            INSERT INTO chatbot.cliente (id_cliente, waid_telefone, nome)
            VALUES (1, '5571999999901', 'Cliente Um'),
                   (2, '5571999999902', 'Cliente Dois');
            INSERT INTO chatbot.conversa
                (id_conversa, id_unidade, id_cliente, id_etapa_atual,
                 status_ativa, motivo_encerramento, finalizou_em)
            VALUES (1, 1, 1, 6, FALSE, 'encaminhado_suporte_idoso', '2026-09-01T00:00:00Z'),
                   (2, 1, 1, 6, FALSE, 'encaminhado_suporte_idoso', '2026-09-02T00:00:00Z'),
                   (3, 2, 1, 6, FALSE, 'encaminhado_suporte_idoso', '2026-09-02T00:00:00Z'),
                   (4, 1, 2, 6, FALSE, 'encaminhado_suporte_idoso', '2026-10-01T00:00:00Z'),
                   (5, 1, 1, 6, TRUE, NULL, NULL);
        ''')
        conversas_antes = self.conn.execute(
            'SELECT to_jsonb(c) FROM chatbot.conversa c ORDER BY id_conversa'
        ).fetchall()
        self.migrar()
        self.assertEqual(self.conn.execute(
            'SELECT to_jsonb(c) FROM chatbot.conversa c ORDER BY id_conversa'
        ).fetchall(), conversas_antes)
        # Adapta apenas a leitura do runtime à base histórica deste teste.
        self.conn.execute('CREATE VIEW chatbot.unidade_atendimento AS SELECT * FROM chatbot.unidade')
        inicio = datetime(2026, 9, 1, tzinfo=timezone.utc)
        fim = datetime(2026, 10, 1, tzinfo=timezone.utc)
        with self.conn.cursor() as cursor:
            for limite in (None, 50, 60, 70, 80, 90):
                cursor.execute(
                    'UPDATE chatbot.unidade SET idade_minima_suporte=%s WHERE id_unidade=1',
                    (limite,),
                )
                if limite == 90:
                    # A migração histórica permite 90; o runtime novo exige a posterior.
                    with self.assertRaises(ValueError):
                        buscar_contexto_etapa6(5, 1, cursor)
                else:
                    self.assertEqual(
                        buscar_contexto_etapa6(5, 1, cursor)['idade_minima_suporte'], limite,
                    )
                self.assertEqual(
                    painel.buscar_unidade(1, cursor)['idade_minima_suporte'], limite,
                )
                self.assertEqual(
                    painel.contar_encaminhados_comercial_por_idade(1, inicio, fim, cursor),
                    1,
                )
            with self.assertRaisesRegex(ValueError, 'não encontrado'):
                buscar_contexto_etapa6(5, 2, cursor)
            self.assertEqual(
                painel.contar_encaminhados_comercial_por_idade(2, inicio, fim, cursor), 1,
            )


if __name__ == '__main__':
    unittest.main()
```

## Passo 52 — Criar `tests/integration/test_fireads_postgres.py`

```python
"""FireAds em PostgreSQL local descartável; apenas HTTP é substituído."""

from contextlib import contextmanager, ExitStack
import os
import unittest
from unittest.mock import Mock, patch

import psycopg
from psycopg.conninfo import conninfo_to_dict

from core.database.deploy_database import (
    bank_script,
    povoar_etapas,
    etapa_transicao_script,
)
from core.repositories.atendimento.conversas import (
    inserindo_em_conversa_caso_seja_nova,
    tentar_lock_conversa,
)
from core.repositories.atendimento.followup import LockConversaPerdido
from core.repositories.fireads import consulta, envios
from core.repositories.funil.leads import buscar_dados_lead_funil
from core.integrations.funil.oportunidades import montar_payload_oportunidade
from core.integrations.fireads.contrato import bloco_observacoes
from workers.worker_flow.fireads import preparar_abertura, interpretar
from workers.worker_funil.fireads import processar
from tests.fixtures.fireads import MIGRACAO_FIREADS, aplicar_fireads

DSN = os.environ.get("FIREADS_TEST_DSN")
NUMERO = "5511999990002"
GOOGLE = {
    "Nome": "Ana Paula Silva",
    "Email": "ana@example.com",
    "WhatsApp": NUMERO,
    "Perfil/Faixa": "Para mim",
    "Data/Hora": "08/10/2026 12:00",
}


@unittest.skipUnless(
    DSN, "Exige FIREADS_TEST_DSN local e banco vazio test_chatbot_fireads"
)
class FireAdsPostgresTests(unittest.TestCase):
    def setUp(self):
        params = conninfo_to_dict(DSN)
        locais = {"127.0.0.1", "::1", "localhost"}
        if (
            params.get("host") not in locais
            or params.get("dbname") != "test_chatbot_fireads"
            or params.get("service")
            or (params.get("hostaddr") and params["hostaddr"] not in locais)
        ):
            raise RuntimeError("FireAds exige banco descartável explícito em loopback")
        self.conn = psycopg.connect(DSN, connect_timeout=5)
        self.addCleanup(self.conn.close)
        if (
            self.conn.info.host not in locais
            or self.conn.info.dbname != "test_chatbot_fireads"
        ):
            raise RuntimeError("Destino efetivo não é o banco de teste")
        if (
            self.conn.execute("SELECT to_regnamespace('chatbot')").fetchone()[0]
            is not None
        ):
            raise RuntimeError("Recusado schema chatbot preexistente")
        self.addCleanup(self.limpar)
        self.cursor = self.conn.cursor()
        self.cursor.execute(
            "CREATE SCHEMA chatbot; CREATE TABLE chatbot.auth_user(id SERIAL PRIMARY KEY)"
        )

        @contextmanager
        def transacao(*_):
            yield self.cursor

        with ExitStack() as stack:
            for module in (bank_script, povoar_etapas, etapa_transicao_script):
                stack.enter_context(patch.object(module, "transacao_deploy", transacao))
            bank_script.criar_tabelas()
            bank_script.criar_funcoes_lock()
            povoar_etapas.insere_etapa_once()
            etapa_transicao_script.criar_e_povoar_transicoes_etapa()
        self.cursor.execute("""
            INSERT INTO chatbot.unidade(nome_unidade,nome_agente,genero,cnpj,email_responsavel,
                telefone,numero_comercial,waba_id,phone_number_id)
            VALUES('Teste FireAds','Dora','feminino','teste','unidade@example.com',
                '5511999990000','5511999990001','waba-teste','phone-teste');
            INSERT INTO chatbot.cliente(nome,waid_telefone,email) VALUES('Antigo','5511999990002','antigo@example.com');
            INSERT INTO chatbot.conversa(id_cliente,id_unidade,status_ativa) VALUES(1,1,FALSE);
        """)
        aplicar_fireads(self.cursor)
        self.cursor.execute("""
            INSERT INTO chatbot.integracao_fireads(id_unidade,url_dashbord,contrato_validado,integracao_ativa)
            VALUES(1,'https://script.google.com/macros/s/teste/exec',TRUE,TRUE);
            INSERT INTO chatbot.integracao_funil_unidade(id_unidade,nome_widget,codigo_widget,
                link_api_carrossel,codigo_canal_venda)
            VALUES(1,'Teste','TESTE','https://example.com/api','113340');
        """)
        self.conn.commit()

    def limpar(self):
        self.conn.rollback()
        self.conn.execute("DROP SCHEMA IF EXISTS chatbot CASCADE")
        self.conn.commit()

    def nova_conversa(self):
        cid = inserindo_em_conversa_caso_seja_nova(1, 1, self.cursor)
        self.conn.commit()
        return cid

    def preparar_mensagem(self):
        cid = self.nova_conversa()
        self.cursor.execute(
            """INSERT INTO chatbot.fila_mensagens
            (cliente_telefone,conteudo_texto,tipo_mensagem,id_phone_unidade,unidade_telefone,
             id_hash_msg,id_conversa,status,retry_count,processing_started_at,received_data_hora)
            VALUES(%s,'Oi','text','phone-teste','5511999990000','wamid.fireads',%s,'processing',1,clock_timestamp(),clock_timestamp())
            RETURNING id_mensagem""",
            (NUMERO, cid),
        )
        mensagem = {
            "id_mensagem": self.cursor.fetchone()[0],
            "retry_count": 1,
            "cliente_telefone": NUMERO,
        }
        ok, versao = tentar_lock_conversa(cid, self.cursor)
        self.assertTrue(ok)
        self.conn.commit()
        contexto = {
            "id_cliente": 1,
            "id_unidade": 1,
            "conversa": {"id_conversa": cid, "id_etapa_atual": None},
        }
        return cid, mensagem, versao, contexto

    def importar(self, cid):
        abertura = consulta.buscar_abertura(cid, self.cursor)
        ident = consulta.reservar_consulta(abertura, cid, self.cursor)
        return consulta.concluir_consulta(
            abertura, cid, ident, interpretar([GOOGLE], [], NUMERO, None), self.cursor
        )

    def preparar_envio(self):
        cid = self.nova_conversa()
        estado = self.importar(cid)
        self.cursor.execute(
            """UPDATE chatbot.conversa SET id_etapa_atual=19,turno='manha',
            profissao='Professora',status_dependente=FALSE WHERE id_conversa=%s""",
            (cid,),
        )
        self.cursor.execute("UPDATE chatbot.cliente SET idade=35 WHERE id_cliente=1")
        self.cursor.execute(
            """INSERT INTO chatbot.respostas_desafios(id_conversa,id_etapa,resposta)
            SELECT %s,etapa,'Às vezes' FROM generate_series(12,17) etapa""",
            (cid,),
        )
        consulta.guardar_coletas(
            {"id_cliente": 1, "id_conversa": cid, "contexto_fireads": estado},
            {"destino_dado": "cliente"},
            self.cursor,
        )
        dados = buscar_dados_lead_funil(cid, self.cursor)
        self.assertEqual(dados["nome_cliente"], "Ana Paula")
        self.assertEqual(dados["idade_cliente"], 35)
        payload = montar_payload_oportunidade(dados)
        esperado = {
            "codigo_canal_venda": "113340",
            "link_api_carrossel": "https://example.com/api",
        }
        original = envios.congelar(dados, payload, esperado, self.cursor)
        self.assertEqual(original[1], "113336")
        self.assertEqual(envios.congelar(dados, {}, esperado, self.cursor), original)
        self.assertIsNone(envios.reservar(self.cursor))  # Funil ainda não confirmou.
        self.cursor.execute(
            "UPDATE chatbot.conversa SET lead_no_funil=TRUE WHERE id_conversa=%s",
            (cid,),
        )
        envio = envios.reservar(self.cursor)
        self.conn.commit()
        return envio

    def test_migracao_preserva_personalizacao_conversas_e_reexecuta(self):
        self.conn.execute(MIGRACAO_FIREADS.read_text(encoding="utf-8"), prepare=False)
        self.assertEqual(
            self.conn.execute(
                "SELECT nome_agente FROM chatbot.unidade_atendimento"
            ).fetchone(),
            ("Dora",),
        )
        self.assertEqual(
            self.conn.execute(
                "SELECT id_conversa,id_chat FROM chatbot.conversa"
            ).fetchall(),
            [(1, 1)],
        )
        self.nova_conversa()
        self.assertEqual(
            self.conn.execute("SELECT count(*) FROM chatbot.chat").fetchone()[0], 1
        )
        self.assertEqual(
            self.conn.execute(
                "SELECT count(*) FROM chatbot.etapa_transicao"
            ).fetchone()[0],
            30,
        )

    def test_importacao_dependente_e_retry_recuperam_snapshot(self):
        cid, mensagem, versao, contexto = self.preparar_mensagem()
        api = Mock()
        api.consultar.side_effect = [
            {
                "headers": list(GOOGLE),
                "rows": [dict(GOOGLE, **{"Perfil/Faixa": "Para outra pessoa"})],
            },
            {
                "headers": ["full_name", "email", "phone_number", "para_quem"],
                "rows": [],
            },
        ]
        with patch("workers.worker_flow.fireads.ClienteFireAds", return_value=api):
            obtido = preparar_abertura(
                contexto, mensagem, versao, self.conn, self.cursor
            )
        self.assertTrue(obtido["conversa"]["status_dependente"])
        self.assertEqual(
            self.conn.execute("SELECT nome,email FROM chatbot.cliente").fetchone(),
            ("Ana Paula", "ana@example.com"),
        )
        self.assertEqual(
            self.conn.execute(
                "SELECT count(*) FROM chatbot.dependente WHERE id_conversa=%s", (cid,)
            ).fetchone()[0],
            1,
        )
        with patch("workers.worker_flow.fireads.ClienteFireAds") as http:
            self.assertEqual(
                preparar_abertura(contexto, mensagem, versao, self.conn, self.cursor),
                obtido,
            )
            http.assert_not_called()

    def test_lock_perdido_durante_http_nao_importa_dados(self):
        cid, mensagem, versao, contexto = self.preparar_mensagem()

        def resposta(aba):
            if "Google" in aba:
                with psycopg.connect(DSN) as outro:
                    outro.execute(
                        "UPDATE chatbot.conversa SET lock_version=lock_version+1 WHERE id_conversa=%s",
                        (cid,),
                    )
                return {"headers": list(GOOGLE), "rows": [GOOGLE]}
            return {
                "headers": ["full_name", "email", "phone_number", "para_quem"],
                "rows": [],
            }

        api = Mock()
        api.consultar.side_effect = resposta
        with patch("workers.worker_flow.fireads.ClienteFireAds", return_value=api):
            with self.assertRaises(LockConversaPerdido):
                preparar_abertura(contexto, mensagem, versao, self.conn, self.cursor)
        self.conn.rollback()
        self.assertEqual(
            self.conn.execute("SELECT nome FROM chatbot.cliente").fetchone()[0],
            "Antigo",
        )
        self.assertIsNone(
            self.conn.execute(
                "SELECT origem_fireads FROM chatbot.conversa WHERE id_conversa=%s",
                (cid,),
            ).fetchone()[0]
        )

    def test_nova_conversa_atualiza_consulta_sem_apagar_contexto_anterior(self):
        cid = self.nova_conversa()
        antigo = self.importar(cid)
        self.cursor.execute(
            "UPDATE chatbot.conversa SET status_ativa=FALSE WHERE id_conversa=%s",
            (cid,),
        )
        novo = self.nova_conversa()
        atual = self.importar(novo)
        self.assertEqual(atual["id_consulta"], antigo["id_consulta"])
        self.assertEqual(
            self.conn.execute(
                "SELECT contexto_fireads FROM chatbot.conversa WHERE id_conversa=%s",
                (cid,),
            ).fetchone()[0],
            antigo,
        )
        self.assertEqual(
            self.conn.execute(
                "SELECT id_conversa_referencia FROM chatbot.consulta_fireads"
            ).fetchone()[0],
            novo,
        )

    def test_retry_dash_reconcilia_bloco_sem_segundo_post(self):
        envio = self.preparar_envio()
        snap = envio["snapshot"]
        bloco = bloco_observacoes(
            envio["integracao"], envio["conversa"], snap["observacoes"]
        )
        api = Mock()
        api.consultar.return_value = {
            "headers": ["Nome", "Email", "WhatsApp", "Observação"],
            "rows": [
                {
                    "_row": 2,
                    "Nome": "Ana",
                    "Email": "ana@example.com",
                    "WhatsApp": NUMERO,
                    "Observação": "FR002\n\n" + bloco,
                }
            ],
        }
        with patch("workers.worker_funil.fireads.ClienteFireAds", return_value=api):
            self.assertTrue(processar(envio, self.conn, self.cursor))
        api.enviar.assert_not_called()
        self.assertTrue(
            self.conn.execute(
                "SELECT lead_no_dash FROM chatbot.conversa WHERE id_conversa=%s",
                (envio["conversa"],),
            ).fetchone()[0]
        )

    def test_falha_dash_fica_pending_preserva_funil_e_nao_tenta_no_mesmo_ciclo(self):
        envio = self.preparar_envio()
        api = Mock()
        api.consultar.side_effect = TimeoutError("teste")
        with patch("workers.worker_funil.fireads.ClienteFireAds", return_value=api):
            self.assertFalse(processar(envio, self.conn, self.cursor))
        self.assertEqual(
            self.conn.execute("SELECT status FROM chatbot.envios_dash").fetchone()[0],
            "pending",
        )
        self.assertIsNone(envios.reservar(self.cursor))
        self.assertTrue(
            self.conn.execute(
                "SELECT lead_no_funil FROM chatbot.conversa WHERE id_conversa=%s",
                (envio["conversa"],),
            ).fetchone()[0]
        )

    def test_reserva_concorrente_nao_e_reivindicada_e_configuracao_mudada_bloqueia(
        self,
    ):
        envio = self.preparar_envio()
        with psycopg.connect(DSN) as outro:
            self.assertIsNone(envios.reservar(outro.cursor()))
        self.cursor.execute(
            "UPDATE chatbot.integracao_fireads SET aba_destino='Outra aba'"
        )
        self.conn.commit()
        with patch("workers.worker_funil.fireads.ClienteFireAds") as http:
            self.assertFalse(processar(envio, self.conn, self.cursor))
            http.assert_not_called()

    def test_personalizacao_obrigatoria_e_chat_nao_cruza_unidades(self):
        with self.assertRaises(psycopg.errors.RaiseException):
            self.conn.execute("DELETE FROM chatbot.atendimento_customizado")
            self.conn.commit()
        self.conn.rollback()
        with self.assertRaises(psycopg.errors.UniqueViolation):
            self.conn.execute(
                "INSERT INTO chatbot.chat(id_cliente,id_unidade) VALUES(1,1)"
            )
        self.conn.rollback()
        with self.assertRaises(psycopg.errors.ForeignKeyViolation):
            self.conn.execute(
                "UPDATE chatbot.conversa SET id_chat=999 WHERE id_conversa=1"
            )
```

## Passo 53 — Criar `deploy/migrations/20261007_fireads_chat_customizacao.sql`

**Último passo — migração SQL para o DBeaver.** Executar o bloco inteiro na janela de deploy descrita acima. Qualquer erro deve abortar a transação; não continuar apenas pelos comandos posteriores.

```sql
-- FireAds: executar inteiro no DBeaver, com workers/webhook parados.
-- Não habilita a integração nem modifica dados no dashboard.
BEGIN;
SET LOCAL lock_timeout = '5s';
SET LOCAL statement_timeout = '120s';

-- INICIO DDL FIREADS
CREATE TABLE IF NOT EXISTS chatbot.migracoes_fireads (
    versao TEXT PRIMARY KEY, aplicada_em TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp()
);

DO $migracao$
DECLARE
    quantidade_conversas BIGINT;
    quantidade_clientes BIGINT;
    quantidade_unidades BIGINT;
BEGIN
    IF EXISTS (SELECT 1 FROM chatbot.migracoes_fireads WHERE versao='20261007_fireads_v1') THEN
        RAISE NOTICE 'Migração FireAds já aplicada; nenhum dado reimportado.';
        RETURN;
    END IF;

    LOCK TABLE chatbot.unidade, chatbot.cliente, chatbot.conversa,
               chatbot.etapa, chatbot.etapa_transicao IN ACCESS EXCLUSIVE MODE;
    SELECT COUNT(*) INTO quantidade_conversas FROM chatbot.conversa;
    SELECT COUNT(*) INTO quantidade_clientes FROM chatbot.cliente;
    SELECT COUNT(*) INTO quantidade_unidades FROM chatbot.unidade;
    IF (SELECT COUNT(*) FROM chatbot.etapa) <> 24
       OR NOT EXISTS (SELECT 1 FROM information_schema.columns
          WHERE table_schema='chatbot' AND table_name='conversa' AND column_name='turno')
       OR NOT EXISTS (SELECT 1 FROM chatbot.etapa_transicao
          WHERE id_etapa_origem=17 AND evento='triagem_concluida_sem_link' AND id_etapa_destino=18)
    THEN
        RAISE EXCEPTION 'Base incompatível: exige catálogo de 24 etapas e rota sem link já aplicada.';
    END IF;

    CREATE TABLE chatbot.atendimento_customizado (
        id_customizacao SERIAL PRIMARY KEY,
        id_unidade INTEGER NOT NULL UNIQUE REFERENCES chatbot.unidade(id_unidade) ON DELETE CASCADE,
        nome_agente VARCHAR(100) NOT NULL CHECK (nome_agente ~ '[^[:space:]]'),
        genero VARCHAR(9) NOT NULL CHECK (genero IN ('masculino','feminino')),
        numero_comercial VARCHAR(30) NOT NULL CHECK (
            regexp_replace(numero_comercial,'[^0-9]','','g') ~ '^([0-9]{10,11}|55[0-9]{10,11})$'),
        idade_minima_suporte INTEGER CHECK (idade_minima_suporte IN (50,60,70,80)),
        email_obrigatorio BOOLEAN NOT NULL DEFAULT TRUE,
        link_agendamento VARCHAR(400) UNIQUE,
        link_instagram VARCHAR(400),
        bpa_ativo BOOLEAN NOT NULL DEFAULT FALSE
    );
    INSERT INTO chatbot.atendimento_customizado
      (id_unidade,nome_agente,genero,numero_comercial,idade_minima_suporte,
       email_obrigatorio,link_agendamento,link_instagram,bpa_ativo)
    SELECT id_unidade,nome_agente,genero,numero_comercial,idade_minima_suporte,
           email_obrigatorio,link_agendamento,link_instagram,bpa_ativo FROM chatbot.unidade;
    IF EXISTS (
        SELECT id_unidade,nome_agente,genero,numero_comercial,idade_minima_suporte,
               email_obrigatorio,link_agendamento,link_instagram,bpa_ativo FROM chatbot.unidade
        EXCEPT
        SELECT id_unidade,nome_agente,genero,numero_comercial,idade_minima_suporte,
               email_obrigatorio,link_agendamento,link_instagram,bpa_ativo FROM chatbot.atendimento_customizado
    ) OR (SELECT COUNT(*) FROM chatbot.atendimento_customizado) <> quantidade_unidades THEN
        RAISE EXCEPTION 'Cópia de personalização divergente; migração abortada.';
    END IF;
    ALTER TABLE chatbot.unidade
        DROP COLUMN nome_agente, DROP COLUMN genero, DROP COLUMN numero_comercial,
        DROP COLUMN idade_minima_suporte, DROP COLUMN email_obrigatorio,
        DROP COLUMN link_agendamento, DROP COLUMN link_instagram, DROP COLUMN bpa_ativo;

    CREATE TABLE chatbot.chat (
        id_chat BIGSERIAL PRIMARY KEY,
        id_cliente INTEGER NOT NULL REFERENCES chatbot.cliente(id_cliente) ON DELETE CASCADE,
        id_unidade INTEGER NOT NULL REFERENCES chatbot.unidade(id_unidade) ON DELETE CASCADE,
        criado_em TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
        CONSTRAINT uq_chat_cliente_unidade UNIQUE (id_cliente,id_unidade),
        CONSTRAINT uq_chat_identidade UNIQUE (id_chat,id_cliente,id_unidade),
        CONSTRAINT uq_chat_unidade UNIQUE (id_chat,id_unidade)
    );
    INSERT INTO chatbot.chat (id_cliente,id_unidade,criado_em)
    SELECT id_cliente,id_unidade,MIN(iniciou_em) FROM chatbot.conversa GROUP BY id_cliente,id_unidade;
    ALTER TABLE chatbot.conversa ADD COLUMN id_chat BIGINT;
    UPDATE chatbot.conversa c SET id_chat=h.id_chat FROM chatbot.chat h
        WHERE h.id_cliente=c.id_cliente AND h.id_unidade=c.id_unidade;
    ALTER TABLE chatbot.conversa
        ALTER COLUMN id_chat SET NOT NULL,
        ADD CONSTRAINT fk_conversa_chat FOREIGN KEY (id_chat,id_cliente,id_unidade)
            REFERENCES chatbot.chat(id_chat,id_cliente,id_unidade) ON DELETE CASCADE,
        ADD CONSTRAINT uq_conversa_chat_unidade UNIQUE (id_conversa,id_chat,id_unidade),
        ADD CONSTRAINT uq_conversa_unidade UNIQUE (id_conversa,id_unidade),
        ADD COLUMN origem_fireads VARCHAR(10) CHECK (origem_fireads IN ('google','meta','organico')),
        ADD COLUMN contexto_fireads JSONB,
        ADD COLUMN lead_no_dash BOOLEAN DEFAULT NULL,
        ADD CONSTRAINT ck_conversa_fireads CHECK (
            (origem_fireads IS NULL AND contexto_fireads IS NULL)
            OR (origem_fireads IS NOT NULL AND contexto_fireads IS NOT NULL
                AND jsonb_typeof(contexto_fireads)='object'
                AND contexto_fireads->>'origem' IS NOT DISTINCT FROM origem_fireads
                AND contexto_fireads->>'id_conversa' IS NOT DISTINCT FROM id_conversa::text
                AND contexto_fireads->>'concluida' IS NOT DISTINCT FROM 'true'));
    CREATE INDEX idx_conversa_chat ON chatbot.conversa(id_chat,iniciou_em DESC);

    CREATE TABLE chatbot.integracao_fireads (
        id_integracao_fireads SERIAL PRIMARY KEY,
        id_unidade INTEGER NOT NULL UNIQUE REFERENCES chatbot.unidade(id_unidade) ON DELETE CASCADE,
        integracao_ativa BOOLEAN NOT NULL DEFAULT FALSE,
        url_dashbord VARCHAR(1000) NOT NULL CHECK (url_dashbord ~ '^https://script[.]google[.]com/macros/s/[^/]+/exec$'),
        url_operation VARCHAR(1000),
        aba_google VARCHAR(200) NOT NULL DEFAULT 'Leads Google Ads (NÃO EDITAR)',
        aba_meta VARCHAR(200) NOT NULL DEFAULT '[FIRE] Leads Ads Geral - 7.2',
        aba_destino VARCHAR(200) NOT NULL DEFAULT 'LEADS GERAL - Feedback',
        fuso_formularios VARCHAR(100),
        contrato_validado BOOLEAN NOT NULL DEFAULT FALSE,
        ativada_em TIMESTAMPTZ,
        criado_em TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
        atualizado_em TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
        CONSTRAINT uq_integracao_fireads_unidade UNIQUE (id_integracao_fireads,id_unidade),
        CHECK (NOT integracao_ativa OR (contrato_validado AND ativada_em IS NOT NULL)),
        CHECK (BTRIM(aba_google)<>'' AND BTRIM(aba_meta)<>'' AND BTRIM(aba_destino)<>''
            AND aba_google<>aba_meta AND aba_google<>aba_destino AND aba_meta<>aba_destino)
    );
    CREATE TABLE chatbot.consulta_fireads (
        id_consulta BIGSERIAL PRIMARY KEY,
        id_chat BIGINT NOT NULL UNIQUE,
        id_unidade INTEGER NOT NULL,
        id_integracao_fireads INTEGER NOT NULL,
        id_conversa_referencia INTEGER NOT NULL,
        consulta_concluida BOOLEAN NOT NULL DEFAULT FALSE,
        resultado VARCHAR(30) NOT NULL DEFAULT 'pendente'
            CHECK (resultado IN ('pendente','importado','ausente','incompleto','ambiguidade','erro')),
        dados JSONB,
        consultado_em TIMESTAMPTZ,
        atualizado_em TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
        FOREIGN KEY (id_chat,id_unidade) REFERENCES chatbot.chat(id_chat,id_unidade) ON DELETE CASCADE,
        FOREIGN KEY (id_integracao_fireads,id_unidade)
            REFERENCES chatbot.integracao_fireads(id_integracao_fireads,id_unidade),
        FOREIGN KEY (id_conversa_referencia,id_chat,id_unidade)
            REFERENCES chatbot.conversa(id_conversa,id_chat,id_unidade) ON DELETE CASCADE,
        CHECK ((NOT consulta_concluida AND resultado='pendente' AND dados IS NULL AND consultado_em IS NULL)
            OR (consulta_concluida AND resultado<>'pendente' AND dados IS NOT NULL AND consultado_em IS NOT NULL))
    );
    CREATE TABLE chatbot.envios_dash (
        id_envio_dash BIGSERIAL PRIMARY KEY,
        id_conversa INTEGER NOT NULL UNIQUE,
        id_unidade INTEGER NOT NULL,
        id_integracao_fireads INTEGER NOT NULL,
        status VARCHAR(20) NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','processing','sent')),
        attempt_count INTEGER NOT NULL DEFAULT 0 CHECK (attempt_count>=0),
        next_attempt_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
        processing_started_at TIMESTAMPTZ,
        enviado_em TIMESTAMPTZ,
        ultimo_erro TEXT,
        recibo JSONB,
        snapshot JSONB NOT NULL CHECK (jsonb_typeof(snapshot)='object'),
        criado_em TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
        atualizado_em TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
        FOREIGN KEY (id_conversa,id_unidade) REFERENCES chatbot.conversa(id_conversa,id_unidade) ON DELETE CASCADE,
        FOREIGN KEY (id_integracao_fireads,id_unidade)
            REFERENCES chatbot.integracao_fireads(id_integracao_fireads,id_unidade),
        CHECK ((status='processing')=(processing_started_at IS NOT NULL)),
        CHECK ((status='sent')=(enviado_em IS NOT NULL))
    );
    CREATE INDEX idx_envios_dash_pendentes ON chatbot.envios_dash(status,next_attempt_at,attempt_count)
        WHERE status<>'sent';

    -- A configuração é cadastrada DESATIVADA pelo Admin após conferir a unidade.
    -- Não inferir qual ID é Santo André nem habilitar importação retroativa.
    INSERT INTO chatbot.etapa_transicao (id_etapa_origem,evento,id_etapa_destino)
    VALUES (7,'oferta_aceita_email_fireads',11),(9,'retorno_confirmado_email_fireads',11)
    ON CONFLICT (id_etapa_origem,evento) DO NOTHING;
    IF NOT EXISTS (SELECT 1 FROM chatbot.etapa_transicao WHERE id_etapa_origem=7 AND evento='oferta_aceita_email_fireads' AND id_etapa_destino=11)
       OR NOT EXISTS (SELECT 1 FROM chatbot.etapa_transicao WHERE id_etapa_origem=9 AND evento='retorno_confirmado_email_fireads' AND id_etapa_destino=11)
       OR (SELECT COUNT(*) FROM chatbot.etapa_transicao)<>30 THEN
        RAISE EXCEPTION 'Mapa divergente: esperado catálogo de 30 transições.';
    END IF;
    IF (SELECT COUNT(*) FROM chatbot.conversa)<>quantidade_conversas
       OR (SELECT COUNT(*) FROM chatbot.cliente)<>quantidade_clientes
       OR (SELECT COUNT(*) FROM chatbot.unidade)<>quantidade_unidades
       OR EXISTS (SELECT 1 FROM chatbot.conversa WHERE id_chat IS NULL) THEN
        RAISE EXCEPTION 'Contagens ou vínculos divergentes; nenhuma alteração será confirmada.';
    END IF;
    INSERT INTO chatbot.migracoes_fireads(versao) VALUES ('20261007_fireads_v1');
END;
$migracao$;

-- View de leitura: consumidores mantêm o mesmo formato, sem duplicar colunas.
CREATE OR REPLACE VIEW chatbot.unidade_atendimento AS
SELECT u.*,a.nome_agente,a.genero,a.numero_comercial,a.idade_minima_suporte,
       a.email_obrigatorio,a.link_agendamento,a.link_instagram,a.bpa_ativo
FROM chatbot.unidade u JOIN chatbot.atendimento_customizado a USING (id_unidade);

CREATE OR REPLACE FUNCTION chatbot.verificar_customizacao_unidade() RETURNS TRIGGER
LANGUAGE plpgsql AS $fn$
DECLARE uid INTEGER;
BEGIN
    IF TG_TABLE_NAME='unidade' THEN uid=NEW.id_unidade; ELSE uid=OLD.id_unidade; END IF;
    IF EXISTS (SELECT 1 FROM chatbot.unidade WHERE id_unidade=uid)
       AND NOT EXISTS (SELECT 1 FROM chatbot.atendimento_customizado WHERE id_unidade=uid) THEN
        RAISE EXCEPTION 'Unidade % precisa de exatamente um atendimento_customizado.',uid;
    END IF;
    RETURN NULL;
END;
$fn$;
DROP TRIGGER IF EXISTS unidade_exige_customizacao ON chatbot.unidade;
CREATE CONSTRAINT TRIGGER unidade_exige_customizacao AFTER INSERT ON chatbot.unidade
    DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION chatbot.verificar_customizacao_unidade();
DROP TRIGGER IF EXISTS customizacao_nao_orfa ON chatbot.atendimento_customizado;
CREATE CONSTRAINT TRIGGER customizacao_nao_orfa AFTER DELETE OR UPDATE ON chatbot.atendimento_customizado
    DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION chatbot.verificar_customizacao_unidade();

CREATE OR REPLACE FUNCTION chatbot.marcar_ativacao_fireads() RETURNS TRIGGER
LANGUAGE plpgsql AS $fn$
BEGIN
    IF NEW.fuso_formularios IS NOT NULL AND NOT EXISTS
        (SELECT 1 FROM pg_timezone_names WHERE name=NEW.fuso_formularios) THEN
        RAISE EXCEPTION 'Fuso de leitura FireAds desconhecido.';
    END IF;
    IF NEW.integracao_ativa THEN
        IF TG_OP='INSERT' THEN NEW.ativada_em=clock_timestamp();
        ELSIF NOT OLD.integracao_ativa THEN NEW.ativada_em=clock_timestamp();
        ELSE NEW.ativada_em=OLD.ativada_em;
        END IF;
    END IF;
    NEW.atualizado_em=clock_timestamp();
    RETURN NEW;
END;
$fn$;
DROP TRIGGER IF EXISTS integracao_fireads_ativacao ON chatbot.integracao_fireads;
CREATE TRIGGER integracao_fireads_ativacao BEFORE INSERT OR UPDATE ON chatbot.integracao_fireads
    FOR EACH ROW EXECUTE FUNCTION chatbot.marcar_ativacao_fireads();
-- FIM DDL FIREADS

SELECT (SELECT COUNT(*) FROM chatbot.unidade) AS unidades,
       (SELECT COUNT(*) FROM chatbot.atendimento_customizado) AS customizacoes,
       (SELECT COUNT(*) FROM chatbot.chat) AS chats,
       (SELECT COUNT(*) FROM chatbot.conversa WHERE id_chat IS NULL) AS conversas_sem_chat,
       (SELECT COUNT(*) FROM chatbot.etapa_transicao) AS transicoes,
       (SELECT COUNT(*) FROM chatbot.integracao_fireads WHERE integracao_ativa) AS fireads_ativas;
COMMIT;
```
