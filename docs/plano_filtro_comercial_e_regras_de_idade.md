# Plano prático: filtro Comercial e regras de encerramento por idade

**Revisão:** 26/09/2026. **Status:** aplicado no projeto local; migração e deploy em produção pendentes.
**Base Git:** `087b5eb348d5fa84a8c78ecf26c37b59f52afda7`. Cada passo registra também o SHA-256 do arquivo local usado como base.

**Base da aplicação:** backup `978627dd55885b42b451b29e5f01e435b01373aa`.

Este documento substitui o plano teórico anterior. Cada passo contém o conteúdo
integral de um arquivo, inclusive trechos preservados. Não há instruções do tipo
“restante igual” ou código omitido. O passo final contém a migração SQL inteira.
A cópia temporária foi usada para conferir a proposta. Os 36 arquivos foram
aplicados após conferir os hashes da base, preservando as correções posteriores
da etapa 1 e os testes atualizados. Os blocos abaixo conservam o código aprovado
como registro da proposta; a documentação dos arquivos aplicados recebeu também
os exemplos discutidos e o registro de validação, e o teste de encerramentos
ganhou os casos de idade textual e universal 91/92 após mudança de configuração.
Não houve deploy, alteração do banco de produção ou envio de mensagens.

## Contrato aprovado

| Caso novo na etapa 6 | Motivo persistido | Contato comercial | Tag |
| --- | --- | --- | --- |
| Titular menor de 18 | `titular_menor_18` | Não | Menor |
| Dependente abaixo de 4, BPA ativo | `dependente_menor_4` | Não | Limite mínimo |
| Dependente abaixo de 5, BPA inativo | `dependente_menor_5` | Não | Limite mínimo |
| Titular no suporte configurado até 89 | `suporte_idoso_50/60/70/80` | Sim, botão com texto pronto | 50+/60+/70+/80+ |
| Titular ou dependente com 90 ou mais | `idade_universal_90` | Sim, botão com texto pronto | 90+ |

- A universal 90+ é avaliada antes do suporte configurável, inclusive com suporte
  desativado. Remover 90 das opções da unidade; migrar 90 para NULL, nunca para 80.
- BPA continua aceitando a partir de 4; sem BPA, a partir de 5. Titular de 18 segue.
- Não encaminhar menores ao comercial. Nenhum encerramento por idade passa a gerar
  Funil ou bloqueio de 30 dias. Etapas normais, triagem, e-mail, follow-up e bloqueios
  por outros motivos mantêm as regras existentes. Funil permanece nas etapas 18–22.
- Telefone comercial válido é obrigatório para toda unidade, independentemente de suporte.
- Preservar as transações atuais, a exclusão do cadastro de dependente abaixo do mínimo
  e os efeitos de idade já existentes. Idade e nome históricos são recuperados pela
  própria conversa, sem criar `dados_encerramento` e sem antecipar commits.
- Os nomes internos que contêm `acima_99` continuam como contratos de importação;
  a nova decisão universal é 90+. O validador numérico e o replay antigo de 90–99
  permanecem compatíveis. Não fazer substituição global de 100 por 90 no projeto.

## Conversas e relatórios têm leituras diferentes

**Comercial:** substitui Continuações. Qualifica apenas a última conversa real do
par cliente/unidade, encerrada por idade e com resposta registrada. Uma conversa
nova retira a tag, mesmo que esteja fora do período selecionado. Outra unidade não
interfere. A tag usa o motivo salvo; mudar suporte ou BPA não altera a tag histórica.
Na área dos selos, essa tag tem prioridade visual; os registros reais de Funil e
Avaliadas continuam disponíveis aos respectivos filtros. O nome global do cliente
continua visível e atualizado como hoje, sem reutilização pelo bot na etapa 1.

Os detalhes mostram motivo do encerramento, participante, resposta sobre a idade,
contato enviado ou não e, separadamente, regras atuais. O par histórico usa o hash
da mensagem original dentro da mesma conversa; não depende da fila ainda existir.
O corpo do encerramento de dependente preserva nome e mínimo mesmo após a exclusão
do cadastro. Dados não recuperáveis ficam explicitamente não registrados.

**Relatórios:** a tabela abaixo dos quatro KPIs conta **conversas**, não contatos.
Um cliente com duas conversas encerradas no período pode contar duas vezes. Usa
`finalizou_em >= início` e `< fim`, respeitando a unidade autorizada. Uma conversa
nova não retira o encerramento antigo da contagem histórica do relatório.

Linhas: suporte de titulares pela configuração **atual** até 89; universal 90+
de titulares; universal 90+ de dependentes; titulares menores de 18; dependentes
abaixo do mínimo BPA **atual**. Se suporte estiver desativado, sua linha não aparece.
As demais linhas podem mostrar zero. Separar os totais com contato e sem contato.
Exemplo: 10 conversas com `suporte_idoso_60` e 3 com `idade_universal_90` de titulares.

Motivos de configuração diferente e legados genéricos sem faixa comprovada não
entram nessa tabela. Não reclassificar conversas antigas pelo cadastro global.
Se a unidade voltar a selecionar 60+, motivos `suporte_idoso_60` no período voltam
a ser compatíveis; o critério é o valor da configuração, não a data de sua edição.
O filtro Comercial ainda pode mostrar esses legados com descrição histórica,
sem inventar tag numérica. Encaminhamento comprova o envio do contato, não um clique,
atendimento humano ou venda.

## Recuperação especial do worker

1. A busca existente comprova a resposta pela conversa, ID da fila e hash da entrada.
   Nunca usar uma última mensagem solta de outro atendimento/turno.
2. Reconhecer o corpo e tipo da resposta persistida antes de decidir encerramento.
   Uma oferta, pergunta de idade, tratamento financeiro ou mídia não prova encerramento.
3. Validar a idade da mensagem do cliente **vinculada ao retry**. Não consultar
   `cliente.idade` para isso: os efeitos podem ainda estar pendentes.
4. Suporte comprovado de 50–89: manter limite atual quando ainda inclui a idade;
   caso contrário/desativado, usar a maior faixa permitida que não ultrapassa a idade.
   Registrar log de reconstrução compatível. Isso não prova o limite histórico exato.
5. Menoridade depende de sua resposta própria. BPA usa o mínimo 4/5 escrito na
   resposta enviada, mesmo se a unidade mudou. Oferta antiga a idade 4 ou 95
   não vira encerramento pela configuração nova.
6. Suporte antigo de 90–99 permanece genérico, não vira universal/80+. Universal
   comprovada de 90–99 recebe motivo novo; para 100+ com texto igual entre versões,
   retry sem motivo confirmado conserva o legado. Idade inválida não autoriza
   inventar faixa específica; corpo comprovado conserva só a categoria genérica.
7. Encerramento e fila sent continuam confirmando/desfazendo juntos. Não existe
   nesta arquitetura uma confirmação isolada do motivo e posterior commit de sent.
   Motivo já confirmado não é recalculado pelo painel. Sem resposta persistida,
   permanece o risco aceito de novo envio com a regra atual após sucesso na Meta.

| Idade da entrada vinculada | Configuração atual | Motivo reconstruído de suporte comprovado |
| --- | --- | --- |
| 51 | 60 | suporte 50 |
| 60 | 80 | suporte 60 |
| 71 | 80 | suporte 70 |
| 71 | 60 | suporte 60 |
| 61 | Desativado | suporte 60 |

Em uma conversa nova, idade 71 e configuração 80 continuam normalmente: não há
resposta de encaminhamento comprovada autorizando a regra especial.

## Validação realizada e limites

- A suíte completa de 293 testes passou no projeto aplicado. Em seguida,
  18 testes direcionados passaram, incluindo um caso novo de recuperação
  universal com titular de 91 e dependente de 92: 294 testes unitários distintos.
  A reconstrução também cobre `71 anos`, `71 anos de idade` e `Setenta e um`.
- As 17 falhas/subtestes antigos de texto/espaçamento foram corrigidos nos
  testes, com autorização, antes da aplicação e já fazem parte do backup.
  Os textos aprovados não foram alterados para satisfazer expectativas antigas.
- Os 13 testes de integração passaram em PostgreSQL 18.3 local descartável,
  incluindo migração, preservação de dados, regras do schema, rollback,
  atomicidade do encerramento com fila sent e compatibilidade com a migração
  anterior. O servidor temporário foi encerrado após a validação.
- JavaScript passou na checagem de sintaxe. Interface conferida em navegador
  durante a revisão da mesma proposta, com fixtures fictícias em desktop e
  largura 390px: filtro, detalhes, legenda, tabela, sem erros JS ou overflow
  horizontal. Os arquivos de interface aplicados são os mesmos validados.
- Na revisão anterior à aplicação, a migração exata também foi validada com
  schema completo, falha antes do commit, disputa de lock, reversão e reaplicação.
  As consultas foram exercitadas com 30 mil conversas, 60 mil mensagens e
  10 mil chats sintéticos, incluindo isolamento por unidade e exclusão do Funil
  para encerramentos por idade. Medições locais não garantem desempenho no RDS.
- Nenhuma nova chamada à Meta/CRM foi feita; nenhuma credencial ou dado real foi
  incluído nas fixtures. A migração de produção ainda precisa ser executada
  na janela coordenada de deploy. A validação local não promete ausência absoluta
  de bugs nem substitui a conferência pós-deploy.

## Aplicação local e próximo deploy

Os arquivos já estão aplicados no checkout local. Não reaplicar os blocos deste
registro por cima de correções posteriores. A documentação corrente e os arquivos
do projeto são a referência após esta entrega.
Preparar os arquivos não significa executar o SQL. Só executar o último passo na
janela coordenada de deploy, com serviços/edições suspensos conforme o procedimento.
`VERSIONAMENTO.md` e a escolha da próxima versão ficam para a preparação do deploy.

O worker principal, os commits, a busca de idempotência, o funil e o follow-up
permanecem estruturalmente intactos. Os pontos de mudança do worker são
`resolver_etapa6.py` e `transacoes/encerramento_atendimento.py`, abaixo, completos.

## Índice dos arquivos

1. `core/validacoes/suporte_por_idade.py`
2. `core/validacoes/encerramento_por_idade.py`
3. `core/integrations/whatsapp/messages/etapa6_messages.py`
4. `workers/worker_flow/response_flow/etapas/resolver_etapa6.py`
5. `workers/worker_flow/transacoes/encerramento_atendimento.py`
6. `core/repositories/atendimento/conversas.py`
7. `core/database/deploy_database/bank_script.py`
8. `callback/webhook/models.py`
9. `callback/webhook/admin.py`
10. `core/repositories/monitoramento/encerramentos.py`
11. `callback/monitoramento/encerramentos.py`
12. `callback/monitoramento/apresentacao.py`
13. `callback/monitoramento/services.py`
14. `callback/monitoramento/templates/monitoramento/painel.html`
15. `callback/monitoramento/static/monitoramento/js/painel.js`
16. `callback/monitoramento/static/monitoramento/css/painel.css`
17. `tests/fixtures/monitoramento_painel.py`
18. `tests/unit/test_encerramentos_por_idade.py`
19. `tests/unit/test_suporte_por_idade.py`
20. `tests/unit/test_suporte_idoso_email_obrigatorio.py`
21. `tests/unit/test_monitoramento_painel.py`
22. `tests/unit/test_metricas_perfis_relatorios.py`
23. `tests/integration/test_suporte_por_idade_postgres.py`
24. `tests/integration/test_encerramentos_por_idade_postgres.py`
25. `REGRAS_DE_NEGOCIO.md`
26. `workers/README.md`
27. `core/database/README.md`
28. `core/repositories/README.md`
29. `core/integrations/whatsapp/README.md`
30. `core/integrations/whatsapp/messages/README.md`
31. `callback/README.md`
32. `tests/README.md`
33. `deploy/README.md`
34. `deploy/filtro_comercial_regras_idade.md`
35. `deploy/rollback/20260926_filtro_comercial_regras_idade.sql`
36. `deploy/migrations/20260926_filtro_comercial_regras_idade.sql`

## Passo 01 — Alterar `core/validacoes/suporte_por_idade.py`

Restringir as opções configuráveis a NULL/50/60/70/80.

Base SHA-256: `aca8d4608e265690cac25475b546b87cbd902debc845af482516f40b29bb02ed`. Conteúdo completo proposto: **12 linhas**.

````python
"""Domínio puro da configuração de encaminhamento por idade da unidade."""

IDADES_MINIMAS_SUPORTE = (50, 60, 70, 80)


def validar_idade_minima_suporte(valor):
    """None desativa; booleanos e números fora do domínio são erros."""
    if valor is not None and (
        type(valor) is not int or valor not in IDADES_MINIMAS_SUPORTE
    ):
        raise ValueError(f"Idade mínima de suporte inválida: {valor!r}")
    return valor
````

## Passo 02 — Criar `core/validacoes/encerramento_por_idade.py`

Centralizar os motivos, as descrições e a reconstrução compatível, sem efeitos externos.

Base SHA-256: `arquivo novo`. Conteúdo completo proposto: **72 linhas**.

````python
"""Catálogo dos encerramentos por idade, sem consultas ou efeitos externos."""

from core.validacoes.suporte_por_idade import validar_idade_minima_suporte


IDADE_UNIVERSAL = 90
MOTIVO_TITULAR_MENOR = 'titular_menor_18'
MOTIVO_UNIVERSAL = 'idade_universal_90'
MOTIVO_SUPORTE_LEGADO = 'encaminhado_suporte_idoso'
MOTIVO_IDADE_LEGADO = 'idade_invalida'
MOTIVOS_SUPORTE = {idade: f'suporte_idoso_{idade}' for idade in (50, 60, 70, 80)}
MOTIVOS_DEPENDENTE = {idade: f'dependente_menor_{idade}' for idade in (4, 5)}

ROTULOS_MOTIVOS = {
    MOTIVO_TITULAR_MENOR: 'Titular menor de 18 anos',
    **{motivo: f'Dependente abaixo de {idade} anos'
       for idade, motivo in MOTIVOS_DEPENDENTE.items()},
    **{motivo: f'Titular encaminhado por suporte {idade}+'
       for idade, motivo in MOTIVOS_SUPORTE.items()},
    MOTIVO_UNIVERSAL: 'Encaminhamento universal: 90 anos ou mais',
    MOTIVO_SUPORTE_LEGADO: 'Suporte por idade: limite histórico não registrado',
    MOTIVO_IDADE_LEGADO: 'Restrição de idade: registro legado',
}
MOTIVOS_IDADE = frozenset(ROTULOS_MOTIVOS)


def motivo_suporte(idade_minima):
    """Converte o limite aplicado em código persistente; None não encaminha."""
    validar_idade_minima_suporte(idade_minima)
    if idade_minima not in MOTIVOS_SUPORTE:
        raise ValueError('Encerramento de suporte sem limite habilitado')
    return MOTIVOS_SUPORTE[idade_minima]


def motivo_dependente(idade_minima):
    if type(idade_minima) is not int or idade_minima not in MOTIVOS_DEPENDENTE:
        raise ValueError('Mínimo de dependente deve ser 4 ou 5 anos')
    return MOTIVOS_DEPENDENTE[idade_minima]


def reconstruir_limite_suporte(idade_informada, limite_atual):
    """Faixa compatível apenas para retry com encaminhamento já comprovado.

    Não descobre a configuração antiga. O chamador comprova o envio antes de
    chamar; a idade vem da entrada vinculada ao retry, nunca de cliente.idade.
    O legado 90–99 permanece genérico para não virar a nova regra universal.
    """
    validar_idade_minima_suporte(limite_atual)
    if type(idade_informada) is not int or not 50 <= idade_informada < IDADE_UNIVERSAL:
        return None
    if limite_atual is not None and idade_informada >= limite_atual:
        return limite_atual
    return max(limite for limite in MOTIVOS_SUPORTE if limite <= idade_informada)


def descrever_motivo_idade(motivo):
    """Metadados estáveis do motivo salvo; não lê a configuração da unidade."""
    if motivo not in MOTIVOS_IDADE:
        return None
    descricao = ROTULOS_MOTIVOS[motivo]
    if motivo in MOTIVOS_SUPORTE.values():
        limite = next(idade for idade, codigo in MOTIVOS_SUPORTE.items() if codigo == motivo)
        return {'tag': f'{limite}+', 'descricao': descricao, 'contato_enviado': True}
    if motivo in MOTIVOS_DEPENDENTE.values():
        return {'tag': 'Limite mínimo', 'descricao': descricao, 'contato_enviado': False}
    if motivo == MOTIVO_TITULAR_MENOR:
        return {'tag': 'Menor', 'descricao': descricao, 'contato_enviado': False}
    if motivo == MOTIVO_UNIVERSAL:
        return {'tag': '90+', 'descricao': descricao, 'contato_enviado': True}
    if motivo == MOTIVO_SUPORTE_LEGADO:
        return {'tag': 'Suporte por idade', 'descricao': descricao, 'contato_enviado': True}
    return {'tag': 'Restrição de idade', 'descricao': descricao, 'contato_enviado': None}
````

## Passo 03 — Alterar `core/integrations/whatsapp/messages/etapa6_messages.py`

Reconhecer corpos conhecidos na recuperação, conservando a redação e os contratos existentes.

Base SHA-256: `b82596b3c16211194515ee3e0fdc42e0f5d4b6e5d43ea6e308fc9cadf8f30e9e`. Conteúdo completo proposto: **313 linhas**.

````python
"""Etapa 6: idade do participante e saídas por política da unidade."""

import re

from core.validacoes.suporte_por_idade import (
    validar_idade_minima_suporte,
)

from core.integrations.whatsapp.messages.componentes_compartilhados import (
    RODAPE_ETAPA6_IDADE_AVANCADA,
    montar_texto_com_rodape,
)
from core.integrations.whatsapp.messages.tratamentos.financeiro import (
    montar_mensagem_tratamento_financeiro,
)
from core.integrations.whatsapp.messages.tratamentos.midia import (
    montar_mensagem_tratamento_midia,
)
from core.integrations.whatsapp.messages.tratamentos.reforco_escolar import (
    montar_mensagem_tratamento_reforco_escolar,
)


### PERGUNTA INICIAL DE IDADE: CLIENTE
MENSAGEM_PADRAO_CLIENTE = "Agora me conta, *qual é a sua idade*? ☺️"

### REPETIÇÃO DA IDADE: CLIENTE, SEM A ABERTURA INICIAL
MENSAGEM_REPETICAO_CLIENTE = "Me diz, qual é a sua idade?"


def montar_mensagem_idade_etapa6(*, repeticao=False):
    mensagem = MENSAGEM_REPETICAO_CLIENTE if repeticao else MENSAGEM_PADRAO_CLIENTE
    return mensagem


### TRATAMENTOS DO CLIENTE: ORIENTAÇÃO + REPETIÇÃO DA IDADE
def montar_mensagem_idade_etapa6_financeiro():
    return montar_mensagem_tratamento_financeiro(MENSAGEM_REPETICAO_CLIENTE)


def montar_mensagem_idade_etapa6_midia():
    return montar_mensagem_tratamento_midia(MENSAGEM_REPETICAO_CLIENTE)


def montar_mensagem_idade_etapa6_reforco_escolar():
    return montar_mensagem_tratamento_reforco_escolar(MENSAGEM_REPETICAO_CLIENTE)


### CONTEXTO INVÁLIDO: MENSAGEM PRÓPRIA, SEM CONCATENAR A REPETIÇÃO
def montar_mensagem_contexto_idade_invalida_etapa6():
    return (
        "Olha, não consegui entender a sua idade. "
        "Digite apenas o número, exemplo: 25."
    )


### PERGUNTA INICIAL DE IDADE: DEPENDENTE
MENSAGEM_PADRAO_DEPENDENTE = "E qual é a *idade de {nome_dependente}*? ☺️"

### REPETIÇÃO DA IDADE: DEPENDENTE, SEM A ABERTURA INICIAL
MENSAGEM_REPETICAO_DEPENDENTE = "Me diz, qual é a idade de {nome_dependente}?"


def montar_mensagem_idade_dependente_etapa6(nome_dependente, *, repeticao=False):
    mensagem = (
        MENSAGEM_REPETICAO_DEPENDENTE if repeticao else MENSAGEM_PADRAO_DEPENDENTE
    )
    return mensagem.format(nome_dependente=nome_dependente)


### TRATAMENTOS DO DEPENDENTE: ORIENTAÇÃO + REPETIÇÃO DA IDADE
def montar_mensagem_idade_dependente_etapa6_financeiro(nome_dependente):
    return montar_mensagem_tratamento_financeiro(
        MENSAGEM_REPETICAO_DEPENDENTE.format(nome_dependente=nome_dependente)
    )


def montar_mensagem_idade_dependente_etapa6_midia(nome_dependente):
    return montar_mensagem_tratamento_midia(
        MENSAGEM_REPETICAO_DEPENDENTE.format(nome_dependente=nome_dependente)
    )


def montar_mensagem_idade_dependente_etapa6_reforco_escolar(nome_dependente):
    return montar_mensagem_tratamento_reforco_escolar(
        MENSAGEM_REPETICAO_DEPENDENTE.format(nome_dependente=nome_dependente)
    )


### CONTEXTO INVÁLIDO: MENSAGEM PRÓPRIA, SEM CONCATENAR A REPETIÇÃO
def montar_mensagem_contexto_idade_dependente_invalida_etapa6(nome_dependente):
    return (
        f"Olha, não consegui entender a idade de {nome_dependente}. "
        "Digite apenas o número, exemplo: 10."
    )


### CLIENTE COM MENOS DE 18 ANOS

MENSAGEM_CLIENTE_MENOR_18_ETAPA6 = (
    "Como você tem menos de 18 anos, este atendimento precisa ser realizado "
    "por um adulto responsável.\n"
    "Peça a um adulto para retornar nosso atendimento. "
    "Um abraço e até logo! 👋☺️"
)


def montar_mensagem_cliente_menor_18_etapa6():
    return MENSAGEM_CLIENTE_MENOR_18_ETAPA6


### DEPENDENTE ABAIXO DA IDADE MINIMA DA UNIDADE

MENSAGEM_DEPENDENTE_MENOR_5_ETAPA6 = (
    "No momento, esta unidade do Supera realiza treinamentos com crianças a "
    "partir de {idade_minima} anos. Quando {nome_dependente} completar {idade_minima} "
    "anos, você poderá entrar em contato "
    "novamente.\n"
    "Um abraço e até logo! 👋☺️"
)


def montar_mensagem_dependente_menor_5_etapa6(
    nome_dependente,
    idade_minima=5,
):
    return MENSAGEM_DEPENDENTE_MENOR_5_ETAPA6.format(
        nome_dependente=nome_dependente,
        idade_minima=idade_minima,
    )


### ENCAMINHAMENTO DO TITULAR PELA FAIXA CONFIGURADA NA UNIDADE
MENSAGEM_SUPORTE_IDOSO_ETAPA6 = (
    "Certo, vou te passar o contato da nossa equipe para dar continuidade a sua experiência supera! 😊\n"
    "Para entrar em contato, basta clicar no botão abaixo."
)


### CLIENTE OU DEPENDENTE COM 90 ANOS OU MAIS
# Nomes antigos preservados como contrato de importação; o corte fica no resolver.
# Regra geral, inclusive quando idade_minima_suporte está desativada.
# Mensagem própria: orienta o contato com o consultor sem repetir a pergunta de idade.
# A redação atende às duas rotas sem presumir que quem conversa é o participante.
MENSAGEM_IDADE_ACIMA_99_ETAPA6 = (
    "Certo, olha, para idades mais avançadas vamos precisar realizar uma pequena "
    "*anamnese* com um dos nossos consultores.\n"
    "Basta clicar no botão abaixo para falar com nosso time e iniciar a anamnese! 😊"
)

BOTAO_FALAR_COM_CONSULTORA_ETAPA6 = "Falar com Consultor"


def montar_mensagem_idade_acima_99_etapa6():
    return montar_texto_com_rodape(
        MENSAGEM_IDADE_ACIMA_99_ETAPA6,
        RODAPE_ETAPA6_IDADE_AVANCADA,
    )


def montar_botao_idade_acima_99_etapa6():
    return BOTAO_FALAR_COM_CONSULTORA_ETAPA6


### TITULAR A PARTIR DO LIMITE CONFIGURADO ATÉ 89 ANOS

BOTAO_SUPORTE_IDOSO_ETAPA6 = "Falar agora"


def montar_mensagem_suporte_idoso_etapa6(idade_minima):
    validar_idade_minima_suporte(idade_minima)
    if idade_minima is None:
        raise ValueError("Não há mensagem de suporte para política desativada")
    return MENSAGEM_SUPORTE_IDOSO_ETAPA6


def montar_botao_suporte_idoso_etapa6():
    return BOTAO_SUPORTE_IDOSO_ETAPA6


### TEXTO PRONTO NO WHATSAPP COMERCIAL: ORIGEM + PEDIDO DO PARTICIPANTE
MENSAGEM_ORIGEM_CONTATO_COMERCIAL_ETAPA6 = (
    "Olá, vim do atendimento com {artigo} {nome_agente}, "
    "chatbot da unidade {nome_unidade}."
)
MENSAGEM_PEDIDO_COMERCIAL_TITULAR_ETAPA6 = (
    "Me chamo {nome_titular}, tenho {idade_participante} anos "
    "e gostaria de reservar minha experiência Supera gratuita."
)
MENSAGEM_PEDIDO_COMERCIAL_DEPENDENTE_ETAPA6 = (
    "Me chamo {nome_titular} e gostaria de reservar uma experiência Supera gratuita "
    "para {nome_dependente}, que tem {idade_participante} anos."
)


def montar_mensagem_contato_comercial_etapa6(
    *,
    nome_agente,
    genero_agente,
    nome_unidade,
    nome_titular,
    idade_participante,
    status_dependente,
    nome_dependente=None,
):
    """Identifica origem e participante usando a idade informada nesta resposta.

    A elegibilidade do encaminhamento pertence ao worker. Na rota de dependente,
    a idade é do participante, nunca do cliente que está conversando com o bot.
    """
    artigo = {"feminino": "a", "masculino": "o"}.get(genero_agente)
    if artigo is None:
        raise ValueError("Gênero do agente inválido para contato comercial")
    if any(
        not isinstance(valor, str) or not valor.strip()
        for valor in (nome_agente, nome_unidade, nome_titular)
    ):
        raise ValueError("Nome do agente, da unidade e do cliente são necessários")
    if type(status_dependente) is not bool:
        raise ValueError("Rota do participante inválida para contato comercial")
    if status_dependente and (
        not isinstance(nome_dependente, str) or not nome_dependente.strip()
    ):
        raise ValueError("Nome do dependente é necessário para contato comercial")
    if type(idade_participante) is not int or idade_participante <= 0:
        raise ValueError("Idade do participante inválida para contato comercial")

    origem = MENSAGEM_ORIGEM_CONTATO_COMERCIAL_ETAPA6.format(
        artigo=artigo,
        nome_agente=nome_agente.strip(),
        nome_unidade=nome_unidade.strip(),
    )
    pedido = (
        MENSAGEM_PEDIDO_COMERCIAL_DEPENDENTE_ETAPA6
        if status_dependente
        else MENSAGEM_PEDIDO_COMERCIAL_TITULAR_ETAPA6
    ).format(
        nome_titular=nome_titular.strip(),
        nome_dependente=nome_dependente.strip() if status_dependente else None,
        idade_participante=idade_participante,
    )
    return f"{origem} {pedido}"


### COMPATIBILIDADE DE RECUPERAÇÃO COM A VERSÃO AINDA EM PRODUÇÃO
# Texto emitido pela versão 701b834; nunca usar em novos envios desta versão.
# Enquanto o próximo deploy não ocorrer, novas entradas podem receber esse corpo.
# O retry o reconhece para concluir o encerramento sem reenviar a resposta.
# Remover somente depois da troca de versão e da checagem de suas pendências.
_MENSAGEM_SUPORTE_IDOSO_LEGADA_SEM_FAIXA = (
    "Certo, olha, para idades mais avançadas oferecemos um atendimento "
    "personalizado com o nosso time! 😊\n\n"
    "Para entrar em contato, basta clicar no botão abaixo."
)


def reconhecer_mensagem_suporte_idoso_etapa6(conteudo):
    """Reconhece resposta já persistida; não monta nem envia mensagem ao cliente."""
    texto = str(conteudo or "").strip()
    mensagens = (
        MENSAGEM_SUPORTE_IDOSO_ETAPA6,
        # Recuperação de envios anteriores à revisão de espaçamento; não reenviar.
        MENSAGEM_SUPORTE_IDOSO_ETAPA6.replace("\n", "\n\n"),
        _MENSAGEM_SUPORTE_IDOSO_LEGADA_SEM_FAIXA,
    )
    # O prefixo de retorno pode anteceder o corpo salvo; não interpretar como envio novo.
    return texto.endswith(mensagens)


def reconhecer_encerramento_etapa6(conteudo, tipo_mensagem):
    """Identifica somente corpos conhecidos; espaços e prefixos não mudam a decisão.

    O chamador deve comprovar a conversa, a etapa e o vínculo com a entrada.
    Esta função não consulta configurações nem altera a formatação dos envios.
    """
    texto = " ".join(str(conteudo or "").split())

    def termina_com(corpo):
        return texto.endswith(" ".join(corpo.split()))

    if tipo_mensagem == "interactive_cta_url":
        if any(termina_com(corpo) for corpo in (
            MENSAGEM_SUPORTE_IDOSO_ETAPA6,
            _MENSAGEM_SUPORTE_IDOSO_LEGADA_SEM_FAIXA,
        )):
            return {"categoria": "suporte"}
        universal = montar_mensagem_idade_acima_99_etapa6()
        if any(termina_com(corpo) for corpo in (
            universal,
            universal.replace(" e iniciar a anamnese", ""),
        )):
            return {"categoria": "universal"}
        return None

    if tipo_mensagem != "text":
        return None
    if termina_com(MENSAGEM_CLIENTE_MENOR_18_ETAPA6):
        return {"categoria": "titular_menor"}

    # O mínimo aparece duas vezes no corpo. A referência exige que sejam iguais.
    modelo = " ".join(MENSAGEM_DEPENDENTE_MENOR_5_ETAPA6.split())
    padrao = re.escape(modelo)
    padrao = padrao.replace(re.escape("{idade_minima}"), r"(?P<minimo>[45])", 1)
    padrao = padrao.replace(re.escape("{idade_minima}"), r"(?P=minimo)")
    padrao = padrao.replace(re.escape("{nome_dependente}"), r"(?P<nome>.+?)")
    encontrado = re.search(padrao + r"$", texto)
    if encontrado:
        return {
            "categoria": "dependente_menor",
            "idade_minima": int(encontrado.group("minimo")),
            "nome_dependente": encontrado.group("nome"),
        }
    return None
````

## Passo 04 — Alterar `workers/worker_flow/response_flow/etapas/resolver_etapa6.py`

Aplicar universal 90+ primeiro e levar o limite efetivo no contexto de envio.

Base SHA-256: `90bd24f23c1b60d00c9dd18ce383b09a017a74d71a8199aba5a18422bf01cbfb`. Conteúdo completo proposto: **386 linhas**.

````python
import logging

from core.validacoes.encerramento_por_idade import IDADE_UNIVERSAL

from workers.worker_flow.response_flow.repeticao_followup import (
    enviar_repeticao_followup,
)

from core.validacoes.suporte_por_idade import validar_idade_minima_suporte
from core.integrations.whatsapp.messages.etapa6_messages import (
    montar_mensagem_contato_comercial_etapa6,
)

from core.integrations.whatsapp.pywa_functions.pywa_senders.etapa6 import (
    enviar_etapa6_cliente_contexto_idade_invalida,
    enviar_etapa6_cliente_financeiro,
    enviar_etapa6_cliente_menor_18,
    enviar_etapa6_cliente_midia,
    enviar_etapa6_cliente_reforco_escolar,
    enviar_etapa6_dependente_contexto_idade_invalida,
    enviar_etapa6_dependente_financeiro,
    enviar_etapa6_dependente_menor_5,
    enviar_etapa6_dependente_midia,
    enviar_etapa6_dependente_reforco_escolar,
    enviar_etapa6_idade_acima_99,
    enviar_etapa6_suporte_idoso,
)
from core.integrations.whatsapp.pywa_functions.pywa_senders.etapa7 import (
    enviar_etapa7_cliente,
    enviar_etapa7_dependente,
)
from core.logging_config import short_value
from workers.worker_flow.response_flow.etapas.validadores_contexto.valida_etapa6 import (
    obter_idade_minima_dependente,
    validar_idade,
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
    ETAPA_7_OFERTA_AULA,
    EVENTO_IDADE_VALIDA,
)
from workers.worker_flow.response_flow.transicoes.resolver_transicao import (
    anexar_transicao_ao_contexto_envio,
    resolver_destino_transicao,
)


logger = logging.getLogger("worker.etapa6")

MOTIVO_CLIENTE_MENOR_18 = "cliente_menor_18"
MOTIVO_DEPENDENTE_MENOR_5 = "dependente_menor_5"
MOTIVO_IDADE_ACIMA_99 = "idade_acima_99"
MOTIVO_SUPORTE_IDOSO = "encaminhado_suporte_idoso"


def resolve_etapa6(contexto_historico):
    """
    Valida a idade do aluno e decide tratamento, encerramento ou 6 -> 7.
    """
    tipo_mensagem = contexto_historico.get("tipo_mensagem_atual")
    texto_cliente = contexto_historico.get("texto_cliente_atual") or ""
    status_dependente = bool(
        contexto_historico.get("status_dependente")
    )
    bpa_ativo = bool(contexto_historico.get("bpa_ativo_unidade"))
    nome_dependente = contexto_historico.get("nome_dependente")
    nome_titular = contexto_historico.get("nome_titular")
    mensagem_cliente = contexto_historico["mensagem_cliente_atual"]
    cliente_telefone = mensagem_cliente["cliente_telefone"]
    phone_id_unidade = mensagem_cliente["id_phone_unidade"]

    # Mídia tem prioridade sobre todas as validações de texto.
    if validar_midia(tipo_mensagem):
        _logar_tratamento(
            contexto_historico,
            "tipo_mensagem_nao_suportado",
        )
        return _enviar_tratamento_midia(
            status_dependente,
            cliente_telefone,
            phone_id_unidade,
            nome_dependente,
        )

    # A dúvida sobre reforço é mais específica que o financeiro e a idade.
    if validar_duvida_reforco_escolar(texto_cliente):
        _logar_tratamento(
            contexto_historico,
            TIPO_TRATAMENTO_REFORCO_ESCOLAR,
        )
        return _enviar_tratamento_reforco_escolar(
            status_dependente,
            cliente_telefone,
            phone_id_unidade,
            nome_dependente,
        )

    if validar_pergunta_financeira(texto_cliente):
        _logar_tratamento(
            contexto_historico,
            TIPO_TRATAMENTO_FINANCEIRO,
        )
        return _enviar_tratamento_financeiro(
            status_dependente,
            cliente_telefone,
            phone_id_unidade,
            nome_dependente,
        )

    resultado_idade = validar_idade(texto_cliente)

    if not resultado_idade.valida and not resultado_idade.acima_limite:
        if contexto_historico.get("retorno_followup"):
            return enviar_repeticao_followup(contexto_historico)
        _logar_tratamento(
            contexto_historico,
            "idade_invalida",
            motivo_detalhado=resultado_idade.motivo,
        )
        return _enviar_tratamento_idade_invalida(
            status_dependente,
            cliente_telefone,
            phone_id_unidade,
            nome_dependente,
        )

    if resultado_idade.idade >= IDADE_UNIVERSAL:
        contexto_envio = enviar_etapa6_idade_acima_99(
            cliente_telefone,
            phone_id_unidade,
            contexto_historico.get("numero_comercial_unidade"),
            mensagem_comercial=_montar_mensagem_comercial(
                contexto_historico,
                resultado_idade.idade,
            ),
        )
        return _anexar_encerramento(
            contexto_envio,
            resultado_idade.idade,
            MOTIVO_IDADE_ACIMA_99,
        )

    idade = resultado_idade.idade

    # A chave ausente é erro; None é a configuração explicitamente desativada.
    idade_minima = validar_idade_minima_suporte(
        contexto_historico["idade_minima_suporte"]
    )

    # O tratamento universal de 90+ já ocorreu. Dependentes seguem seu fluxo.
    if (
        not status_dependente
        and idade_minima is not None
        and idade >= idade_minima
    ):
        contexto_envio = enviar_etapa6_suporte_idoso(
            cliente_telefone,
            phone_id_unidade,
            contexto_historico.get("numero_comercial_unidade"),
            idade_minima,
            mensagem_comercial=_montar_mensagem_comercial(
                contexto_historico,
                idade,
            ),
        )
        return _anexar_encerramento(
            contexto_envio,
            idade,
            MOTIVO_SUPORTE_IDOSO,
            limite_idade_encerramento=idade_minima,
        )

    if not status_dependente and idade < 18:
        contexto_envio = enviar_etapa6_cliente_menor_18(
            cliente_telefone,
            phone_id_unidade,
        )
        return _anexar_encerramento(
            contexto_envio,
            idade,
            MOTIVO_CLIENTE_MENOR_18,
        )

    idade_minima_dependente = obter_idade_minima_dependente(
        bpa_ativo
    )

    if status_dependente and idade < idade_minima_dependente:
        contexto_envio = enviar_etapa6_dependente_menor_5(
            cliente_telefone,
            phone_id_unidade,
            nome_dependente,
            idade_minima_dependente,
        )
        return _anexar_encerramento(
            contexto_envio,
            idade,
            MOTIVO_DEPENDENTE_MENOR_5,
            excluir_dependente=True,
            limite_idade_encerramento=idade_minima_dependente,
        )

    # VALIDANDO DESTINO(S)
    # A resposta passou pelos tratamentos; agora o mapa autoriza 6 -> 7.
    etapa_destino = resolver_destino_transicao(
        contexto_historico,
        EVENTO_IDADE_VALIDA,
        destinos_esperados={ETAPA_7_OFERTA_AULA},
    )

    logger.info(
        "etapa6_idade_validada | acao=enviar_etapa7 "
        "id_conversa=%s id_mensagem_fila=%s evento=%s "
        "etapa_destino=%s idade=%s status_dependente=%s",
        contexto_historico["id_conversa"],
        mensagem_cliente["id_mensagem_fila"],
        EVENTO_IDADE_VALIDA,
        etapa_destino,
        idade,
        status_dependente,
    )

    if status_dependente:
        contexto_envio = enviar_etapa7_dependente(
            cliente_telefone,
            phone_id_unidade,
            nome_titular=nome_titular,
            nome_dependente=nome_dependente,
        )
    else:
        contexto_envio = enviar_etapa7_cliente(
            cliente_telefone,
            phone_id_unidade,
            nome_titular=nome_titular,
        )

    contexto_envio["idade_aluno"] = idade

    return anexar_transicao_ao_contexto_envio(
        contexto_historico,
        contexto_envio,
        EVENTO_IDADE_VALIDA,
        etapa_destino,
    )


def _montar_mensagem_comercial(contexto_historico, idade_participante):
    # A etapa 6 coleta a idade do participante. Não reutilizar idade antiga do banco
    # nem atribuir ao titular a idade que ele informou sobre o dependente.
    return montar_mensagem_contato_comercial_etapa6(
        nome_agente=contexto_historico.get("nome_agente"),
        genero_agente=contexto_historico.get("genero_agente_unidade"),
        nome_unidade=contexto_historico.get("nome_unidade"),
        nome_titular=contexto_historico.get("nome_titular"),
        idade_participante=idade_participante,
        status_dependente=contexto_historico.get("status_dependente"),
        nome_dependente=contexto_historico.get("nome_dependente"),
    )


def _enviar_tratamento_midia(
    status_dependente,
    cliente_telefone,
    phone_id_unidade,
    nome_dependente,
):
    if status_dependente:
        return enviar_etapa6_dependente_midia(
            cliente_telefone,
            phone_id_unidade,
            nome_dependente,
        )

    return enviar_etapa6_cliente_midia(
        cliente_telefone,
        phone_id_unidade,
    )


def _enviar_tratamento_financeiro(
    status_dependente,
    cliente_telefone,
    phone_id_unidade,
    nome_dependente,
):
    if status_dependente:
        return enviar_etapa6_dependente_financeiro(
            cliente_telefone,
            phone_id_unidade,
            nome_dependente,
        )

    return enviar_etapa6_cliente_financeiro(
        cliente_telefone,
        phone_id_unidade,
    )


def _enviar_tratamento_reforco_escolar(
    status_dependente,
    cliente_telefone,
    phone_id_unidade,
    nome_dependente,
):
    if status_dependente:
        return enviar_etapa6_dependente_reforco_escolar(
            cliente_telefone,
            phone_id_unidade,
            nome_dependente,
        )

    return enviar_etapa6_cliente_reforco_escolar(
        cliente_telefone,
        phone_id_unidade,
    )


def _enviar_tratamento_idade_invalida(
    status_dependente,
    cliente_telefone,
    phone_id_unidade,
    nome_dependente,
):
    if status_dependente:
        return enviar_etapa6_dependente_contexto_idade_invalida(
            cliente_telefone,
            phone_id_unidade,
            nome_dependente,
        )

    return enviar_etapa6_cliente_contexto_idade_invalida(
        cliente_telefone,
        phone_id_unidade,
    )


def _anexar_encerramento(
    contexto_envio,
    idade,
    motivo,
    *,
    excluir_dependente=False,
    limite_idade_encerramento=None,
):
    contexto_envio.update(
        {
            "idade_aluno": idade,
            "encerrar_atendimento": True,
            "motivo_encerramento": motivo,
            "excluir_dependente": excluir_dependente,
            "limite_idade_encerramento": limite_idade_encerramento,
        }
    )
    return contexto_envio


def _logar_tratamento(
    contexto_historico,
    motivo,
    *,
    motivo_detalhado=None,
):
    mensagem = contexto_historico["mensagem_cliente_atual"]

    logger.info(
        "resposta_cliente_tratamento | motivo=%s motivo_detalhado=%s "
        "acao=tratar_sem_avancar id_conversa=%s id_mensagem_fila=%s "
        "cliente=%s phone_number_id=%s etapa_cliente=%s",
        motivo,
        motivo_detalhado,
        contexto_historico["id_conversa"],
        mensagem["id_mensagem_fila"],
        short_value(mensagem["cliente_telefone"]),
        short_value(mensagem["id_phone_unidade"]),
        contexto_historico["id_etapa_cliente"],
    )
````

## Passo 05 — Alterar `workers/worker_flow/transacoes/encerramento_atendimento.py`

Persistir os motivos específicos e recuperar a decisão somente pela resposta vinculada ao retry.

Base SHA-256: `4f27350a14b539dabbce08d34c8161c7ac4dd249faf6a37ed55b3753b0938934`. Conteúdo completo proposto: **210 linhas**.

````python
import logging

from core.validacoes.encerramento_por_idade import (
    MOTIVO_TITULAR_MENOR,
    MOTIVO_UNIVERSAL,
    motivo_dependente,
    motivo_suporte,
    reconstruir_limite_suporte,
)

from core.integrations.whatsapp.messages.etapa6_messages import (
    reconhecer_encerramento_etapa6,
)
from core.repositories.atendimento.conversas import encerrar_conversa
from core.repositories.atendimento.dependentes import (
    excluir_dependente_da_conversa,
)
from core.repositories.fluxo.politicas import buscar_politica_etapa
from workers.worker_flow.response_flow.etapas.validadores_contexto.valida_etapa6 import (
    validar_idade,
)
from workers.worker_flow.response_flow.transicoes.eventos import (
    ETAPA_6_IDADE_ALUNO,
)


logger = logging.getLogger("worker.support")

MOTIVO_CLIENTE_MENOR_18 = "cliente_menor_18"
MOTIVO_DEPENDENTE_MENOR_5 = "dependente_menor_5"
MOTIVO_IDADE_ACIMA_99 = "idade_acima_99"
MOTIVO_SUPORTE_IDOSO = "encaminhado_suporte_idoso"
MOTIVO_ETAPA_FINAL = "etapa_final"

MOTIVO_ENCERRAMENTO_IDADE_INVALIDA = "idade_invalida"
MOTIVO_ENCERRAMENTO_FOI_AGENDADO = "foi_agendado"
MOTIVO_ENCERRAMENTO_SUPORTE_IDOSO = "encaminhado_suporte_idoso"


def resolver_intencao_encerramento(
    contexto_historico,
    contexto_envio,
    cursor,
):
    if contexto_envio.get("encerrar_atendimento"):
        motivo = contexto_envio["motivo_encerramento"]
        # O resolver carrega o limite que realmente gerou a resposta enviada.
        # Não reler a unidade aqui: ela pode ter mudado depois do envio.
        if motivo == MOTIVO_SUPORTE_IDOSO:
            motivo_banco = motivo_suporte(contexto_envio["limite_idade_encerramento"])
        elif motivo == MOTIVO_DEPENDENTE_MENOR_5:
            motivo_banco = motivo_dependente(contexto_envio["limite_idade_encerramento"])
        elif motivo == MOTIVO_CLIENTE_MENOR_18:
            motivo_banco = MOTIVO_TITULAR_MENOR
        elif motivo == MOTIVO_IDADE_ACIMA_99:
            motivo_banco = MOTIVO_UNIVERSAL
        else:
            raise ValueError(f"Categoria de encerramento desconhecida: {motivo!r}")
        return {
            "motivo": motivo,
            "motivo_encerramento": motivo_banco,
            "excluir_dependente": bool(
                contexto_envio.get("excluir_dependente")
            ),
            "bloqueio_dias": 0,
        }

    # No retry, a resposta já existe e a decisão é reconstruída pela mesma
    # mensagem original da etapa 6, sem consultar conversas anteriores.
    if contexto_envio.get("resposta_ja_existia"):
        intencao_reconstruida = _reconstruir_encerramento_etapa6(
            contexto_historico
        )
        if intencao_reconstruida:
            return intencao_reconstruida

    if not contexto_envio.get("evento_transicao"):
        return None

    id_etapa_destino = contexto_envio.get("id_etapa_resultante")
    politica_destino = buscar_politica_etapa(
        id_etapa_destino,
        cursor,
    )

    if not politica_destino.encerra_automaticamente:
        return None

    return {
        "motivo": MOTIVO_ETAPA_FINAL,
        "motivo_encerramento": MOTIVO_ENCERRAMENTO_FOI_AGENDADO,
        "excluir_dependente": False,
        "bloqueio_dias": politica_destino.bloqueio_dias,
    }


def _reconstruir_encerramento_etapa6(contexto_historico):
    """Conclui somente a resposta já comprovada para a entrada em recuperação.

    A busca anterior exige conversa + fila + hash de origem. Aqui não procuramos
    uma mensagem solta no histórico e não usamos cliente.idade, pois os efeitos
    da idade podem estar pendentes. Sem resposta conhecida, não deduzir fechamento.
    """
    if contexto_historico.get("id_etapa_origem_transicao") != ETAPA_6_IDADE_ALUNO:
        return None
    resposta = contexto_historico.get("resposta_bot_para_mensagem_atual") or {}
    reconhecida = reconhecer_encerramento_etapa6(
        resposta.get("conteudo_texto"), resposta.get("tipo_mensagem"),
    )
    if not reconhecida:
        return None

    resultado = validar_idade(contexto_historico.get("texto_cliente_atual") or "")
    idade = resultado.idade if resultado.valida or resultado.acima_limite else None
    dependente = bool(contexto_historico.get("status_dependente"))
    categoria = reconhecida["categoria"]
    motivo_banco = MOTIVO_ENCERRAMENTO_IDADE_INVALIDA
    excluir_dependente = False

    if categoria == "suporte":
        if dependente:
            return None
        motivo = MOTIVO_SUPORTE_IDOSO
        motivo_banco = MOTIVO_ENCERRAMENTO_SUPORTE_IDOSO
        limite_atual = contexto_historico["idade_minima_suporte"]
        limite = reconstruir_limite_suporte(idade, limite_atual)
        if limite is not None:
            motivo_banco = motivo_suporte(limite)
            logger.info(
                "encerramento_reconstruido_por_compatibilidade | "
                "id_conversa=%s id_mensagem_fila=%s idade=%s "
                "limite_atual=%s limite_reconstruido=%s",
                contexto_historico.get("id_conversa"),
                (contexto_historico.get("mensagem_cliente_atual") or {}).get("id_mensagem_fila"),
                idade, limite_atual, limite,
            )
        # Suporte antigo de 90–99 continua genérico: não virar universal/80+.
    elif categoria == "titular_menor":
        if dependente:
            return None
        motivo = MOTIVO_CLIENTE_MENOR_18
        if idade is not None and idade < 18:
            motivo_banco = MOTIVO_TITULAR_MENOR
    elif categoria == "dependente_menor":
        if not dependente:
            return None
        motivo = MOTIVO_DEPENDENTE_MENOR_5
        excluir_dependente = True
        minimo_enviado = reconhecida["idade_minima"]
        if idade is not None and idade < minimo_enviado:
            # Preserva o mínimo que o cliente leu, mesmo que o BPA tenha mudado.
            motivo_banco = motivo_dependente(minimo_enviado)
    else:
        motivo = MOTIVO_IDADE_ACIMA_99
        if idade is not None and 90 <= idade < 100:
            motivo_banco = MOTIVO_UNIVERSAL
        # O corpo de 100+ é igual entre versões. Sem motivo confirmado, manter
        # legado em vez de afirmar qual limiar histórico foi usado.

    return {
        "motivo": motivo,
        "motivo_encerramento": motivo_banco,
        "excluir_dependente": excluir_dependente,
        "bloqueio_dias": 0,
    }


def aplicar_encerramento_se_necessario(
    id_conversa,
    intencao_encerramento,
    cursor,
):
    if not intencao_encerramento:
        return {
            "atendimento_encerrado": False,
            "finalizou_em": None,
            "bloqueio_dias": 0,
            "motivo": None,
            "motivo_encerramento": None,
        }

    if intencao_encerramento["excluir_dependente"]:
        excluir_dependente_da_conversa(id_conversa, cursor)

    motivo_encerramento = intencao_encerramento["motivo_encerramento"]
    finalizou_em = encerrar_conversa(
        id_conversa,
        motivo_encerramento,
        cursor,
    )
    bloqueio_dias = int(
        intencao_encerramento.get("bloqueio_dias") or 0
    )

    logger.info(
        "atendimento_encerrado | acao=encerrar_conversa "
        "id_conversa=%s motivo=%s motivo_encerramento=%s "
        "dependente_excluido=%s",
        id_conversa,
        intencao_encerramento["motivo"],
        motivo_encerramento,
        intencao_encerramento["excluir_dependente"],
    )
    return {
        "atendimento_encerrado": True,
        "finalizou_em": finalizou_em,
        "bloqueio_dias": bloqueio_dias,
        "motivo": intencao_encerramento["motivo"],
        "motivo_encerramento": motivo_encerramento,
    }
````

## Passo 06 — Alterar `core/repositories/atendimento/conversas.py`

Aceitar os motivos novos sem retirar agendamento, follow-up ou motivos legados.

Base SHA-256: `daa29f5fefe0e09d5fbaf959fd6dc3fcb8205fde2fd7d4a89bb03e2da6d1ba3d`. Conteúdo completo proposto: **480 linhas**.

````python
import logging

from core.validacoes.encerramento_por_idade import MOTIVOS_IDADE


logger = logging.getLogger("db.atendimento.conversas")

ETAPA_INICIAL = 1

# Catálogo compartilhado: preserva os motivos de follow-up e agendamento.
MOTIVOS_ENCERRAMENTO_VALIDOS = MOTIVOS_IDADE | {'foi_agendado', 'followup_sem_resposta'}


def inserindo_em_conversa_caso_seja_nova(id_cliente, id_unidade, cursor):
    cursor.execute("""
        INSERT INTO chatbot.conversa (
            id_cliente,
            id_unidade,
            last_interaction_at,
            last_message_from
        )
        VALUES (%s, %s, NOW(), 'cliente')
        RETURNING id_conversa;
    """, (id_cliente, id_unidade))

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
    if id_etapa_resultante != ETAPA_INICIAL:
        raise ValueError(
            "Inicializacao da conversa so pode persistir a etapa 1"
        )

    _validar_data_interacao_bot(data_interacao)

    cursor.execute("""
        UPDATE chatbot.conversa
        SET
            id_etapa_atual = %s,
            last_message_from = 'bot',
            last_interaction_at = %s
        WHERE id_conversa = %s
          AND id_etapa_atual IS NULL;
    """, (
        id_etapa_resultante,
        data_interacao,
        id_conversa,
    ))

    logger.debug(
        "conversa_update | acao=inicializar_etapa id_conversa=%s etapa=%s linhas=%s",
        id_conversa,
        id_etapa_resultante,
        cursor.rowcount,
    )

    if cursor.rowcount != 1:
        raise ValueError(
            "Conversa nao foi inicializada na etapa 1 "
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
````

## Passo 07 — Alterar `core/database/deploy_database/bank_script.py`

Alinhar o DDL de instalação nova ao schema final, sem executar seeds na atualização.

Base SHA-256: `4c834a0298b4ab8735d5c27fbe91550c327a76573787981c9e8680ff61edd7eb`. Conteúdo completo proposto: **607 linhas**.

````python
import logging

from core.database.deploy_database.transacao_deploy import transacao_deploy
from core.database.deploy_database.followup_script import criar_tabelas_followup

logger = logging.getLogger("db.deploy_database")


def criar_funcoes_lock():
    with transacao_deploy("criar_funcoes_lock", logger) as cursor:
        cursor.execute("""
        CREATE OR REPLACE FUNCTION chatbot.lock_conversa(p_id_conversa INT)
        RETURNS TABLE (
            lock_ok BOOLEAN,
            lock_version_atual INT
        )
        LANGUAGE plpgsql
        AS $$

        DECLARE
            v_lock_version INT;

        BEGIN
            UPDATE chatbot.conversa c
            SET
                processing = TRUE,
                processing_started_at = NOW(),
                lock_version = COALESCE(c.lock_version, 0) + 1
            WHERE
                c.id_conversa = p_id_conversa
                AND (
                    c.processing = FALSE
                    OR c.processing_started_at
                        < NOW() - INTERVAL '110.0 seconds'
                )
            RETURNING c.lock_version INTO v_lock_version;

            IF v_lock_version IS NULL THEN
                RETURN QUERY SELECT FALSE, NULL::INT;
                RETURN;
            END IF;

            RETURN QUERY SELECT TRUE, v_lock_version;
        END;

        $$;
        """)

        cursor.execute("""
        CREATE OR REPLACE FUNCTION chatbot.unlock_conversa(
            p_id_conversa INT,
            p_lock_version INT
        )
        RETURNS BOOLEAN
        LANGUAGE plpgsql
        AS $$

        DECLARE
            updated_rows INTEGER;

        BEGIN
            UPDATE chatbot.conversa
            SET
                processing = FALSE,
                processing_started_at = NULL
            WHERE id_conversa = p_id_conversa
              AND lock_version = p_lock_version;

            GET DIAGNOSTICS updated_rows = ROW_COUNT;

            RETURN updated_rows = 1;
        END;

        $$;
        """)

    logger.info("banco_setup_ok | acao=criar_funcoes_lock")


def criar_funcao_dequeue_message():
    with transacao_deploy("criar_funcao_dequeue_message", logger) as cursor:
        cursor.execute("""
        CREATE OR REPLACE FUNCTION chatbot.dequeue_message()
        RETURNS TABLE (
            id_mensagem INT,
            cliente_telefone VARCHAR,
            conteudo_texto TEXT,
            tipo_mensagem VARCHAR,
            id_phone_unidade VARCHAR,
            unidade_telefone VARCHAR,
            received_data_hora TIMESTAMPTZ,
            id_hash_msg VARCHAR,
            retry_count INT
        )
        LANGUAGE plpgsql
        AS $$

        BEGIN
            RETURN QUERY

            WITH next_job AS (
                SELECT f.id_mensagem
                FROM chatbot.fila_mensagens f
                WHERE
                    (
                        f.status = 'pending'
                        AND f.next_attempt_at <= NOW()
                    )
                    OR
                    (
                        f.status = 'processing'
                        AND f.processing_started_at
                            < NOW() - INTERVAL '2 minutes'
                    )
                ORDER BY
                    CASE
                        WHEN f.status = 'pending' THEN f.next_attempt_at
                        WHEN f.status = 'processing'
                            THEN f.processing_started_at
                    END NULLS FIRST,
                    f.id_mensagem
                FOR UPDATE SKIP LOCKED
                LIMIT 1
            )

            UPDATE chatbot.fila_mensagens f
            SET
                status = 'processing',
                retry_count = f.retry_count + 1,
                processing_started_at = NOW()
            FROM next_job
            WHERE f.id_mensagem = next_job.id_mensagem

            RETURNING
                f.id_mensagem,
                f.cliente_telefone,
                f.conteudo_texto,
                f.tipo_mensagem,
                f.id_phone_unidade,
                f.unidade_telefone,
                f.received_data_hora,
                f.id_hash_msg,
                f.retry_count;
        END;

        $$;
        """)

    logger.info("banco_setup_ok | acao=criar_funcao_dequeue_message")


def criar_tabelas():
    """Cria o schema final da V1 em ordem de dependência, sem migrações."""
    with transacao_deploy("criar_tabelas", logger) as cursor:
        cursor.execute("""
        CREATE SCHEMA IF NOT EXISTS chatbot;

        DO $dependencia_django$
        BEGIN
            IF TO_REGCLASS('chatbot.auth_user') IS NULL THEN
                RAISE EXCEPTION
                    'Prepare o schema chatbot e execute as migrations do Django antes do DDL de negocio: chatbot.auth_user deve existir.';
            END IF;
        END
        $dependencia_django$;

        -- 1. CLIENTE E UNIDADE (AUTH_USER PREPARADA PELO DJANGO)

        CREATE TABLE IF NOT EXISTS chatbot.cliente (
            id_cliente SERIAL PRIMARY KEY,
            nome VARCHAR(200),
            waid_telefone VARCHAR(50) UNIQUE NOT NULL,
            email VARCHAR(200) UNIQUE,
            idade INTEGER,
            profissao VARCHAR(100)
        );

        CREATE TABLE IF NOT EXISTS chatbot.unidade (
            id_unidade SERIAL PRIMARY KEY,
            nome_unidade VARCHAR(300) NOT NULL,
            nome_agente VARCHAR(100) NOT NULL,
            genero VARCHAR(9) NOT NULL,
            cnpj VARCHAR(50) UNIQUE NOT NULL,
            email_responsavel VARCHAR(255) UNIQUE NOT NULL,
            telefone VARCHAR(20) UNIQUE NOT NULL,
            numero_comercial VARCHAR(30) NOT NULL
                CONSTRAINT ck_unidade_numero_comercial CHECK (
                    regexp_replace(numero_comercial, '[^0-9]', '', 'g')
                    ~ '^([0-9]{10,11}|55[0-9]{10,11})$'
                ),
            idade_minima_suporte INTEGER DEFAULT NULL
                CONSTRAINT ck_unidade_idade_minima_suporte CHECK (
                    idade_minima_suporte IS NULL
                    OR idade_minima_suporte IN (50, 60, 70, 80)
                ),
            email_obrigatorio BOOLEAN NOT NULL DEFAULT TRUE,
            waba_id VARCHAR(100) UNIQUE NOT NULL,
            phone_number_id VARCHAR(100) UNIQUE NOT NULL,
            link_agendamento VARCHAR(400) UNIQUE NOT NULL,
            link_instagram VARCHAR(400),
            bpa_ativo BOOLEAN NOT NULL DEFAULT FALSE,
            status_pagamento BOOLEAN DEFAULT TRUE,
            id_usuario_monitoramento INT NULL,

            CONSTRAINT uq_unidade_nome_unidade
                UNIQUE (nome_unidade),

            CONSTRAINT ck_unidade_nome_unidade_nao_vazio
                CHECK (nome_unidade ~ '[^[:space:]]'),

            CONSTRAINT ck_unidade_nome_agente_nao_vazio
                CHECK (nome_agente ~ '[^[:space:]]'),

            CONSTRAINT ck_unidade_genero
                CHECK (genero IN ('masculino', 'feminino')),

            CONSTRAINT uq_unidade_usuario_monitoramento
                UNIQUE (id_usuario_monitoramento),
            CONSTRAINT unidade_id_usuario_monitoramento_fkey
                FOREIGN KEY (id_usuario_monitoramento)
                REFERENCES chatbot.auth_user(id)
                ON DELETE SET NULL
        );

        CREATE TABLE IF NOT EXISTS chatbot.etapa (
            id_etapa SERIAL PRIMARY KEY,
            nome_etapa VARCHAR(100) UNIQUE NOT NULL,
            encerra_automaticamente BOOLEAN NOT NULL DEFAULT FALSE,
            bloqueio_dias INTEGER NOT NULL DEFAULT 0,
            elegivel_funil BOOLEAN NOT NULL DEFAULT FALSE,

            CONSTRAINT ck_etapa_bloqueio_dias
                CHECK (bloqueio_dias >= 0)
        );

        -- 2. CONFIGURACAO DO FUNIL POR UNIDADE

        CREATE TABLE IF NOT EXISTS chatbot.integracao_funil_unidade (
            id_integracao_funil SERIAL PRIMARY KEY,
            id_unidade INT NOT NULL UNIQUE,

            nome_widget VARCHAR(300) NOT NULL,
            data_salvamento_widget DATE,
            codigo_widget VARCHAR(100) UNIQUE NOT NULL,
            link_api_carrossel VARCHAR(500) UNIQUE NOT NULL,
            codigo_canal_venda VARCHAR(100) NOT NULL,

            widget_ativo BOOLEAN NOT NULL DEFAULT TRUE,
            integracao_ativa BOOLEAN NOT NULL DEFAULT TRUE,

            criado_em TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            atualizado_em TIMESTAMPTZ NOT NULL DEFAULT NOW(),

            CONSTRAINT ck_integracao_funil_nome_widget
                CHECK (BTRIM(nome_widget) <> ''),

            CONSTRAINT ck_integracao_funil_codigo_widget
                CHECK (BTRIM(codigo_widget) <> ''),

            CONSTRAINT ck_integracao_funil_link_api
                CHECK (BTRIM(link_api_carrossel) <> ''),

            CONSTRAINT ck_integracao_funil_codigo_canal
                CHECK (BTRIM(codigo_canal_venda) <> ''),

            CONSTRAINT integracao_funil_unidade_id_unidade_fkey
                FOREIGN KEY (id_unidade)
                REFERENCES chatbot.unidade(id_unidade)
                ON DELETE CASCADE
        );

        -- 3. CONVERSA: RAIZ TRANSACIONAL DO ATENDIMENTO

        CREATE TABLE IF NOT EXISTS chatbot.conversa (
            id_conversa SERIAL PRIMARY KEY,
            id_cliente INT NOT NULL,
            id_unidade INT NOT NULL,
            id_etapa_atual INT,

            status_ativa BOOLEAN NOT NULL DEFAULT TRUE,
            status_dependente BOOLEAN DEFAULT FALSE,
            profissao VARCHAR(100) NULL,

            last_interaction_at TIMESTAMPTZ,

            last_message_from VARCHAR(10)
                CHECK (last_message_from IN ('cliente', 'bot')),

            followup_stage INTEGER DEFAULT 0,
            followup_last_sent_at TIMESTAMPTZ NULL,

            lead_no_funil BOOLEAN DEFAULT FALSE,

            processing BOOLEAN DEFAULT FALSE,
            processing_started_at TIMESTAMPTZ NULL,
            lock_version INTEGER DEFAULT 0,
            turnos_sem_avanco INTEGER NOT NULL DEFAULT 0,

            iniciou_em TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            finalizou_em TIMESTAMPTZ,
            motivo_encerramento VARCHAR(30),

            CONSTRAINT ck_conversa_motivo_encerramento
                CHECK (
                    motivo_encerramento IS NULL
                    OR motivo_encerramento IN (
                        'idade_invalida',
                        'foi_agendado',
                        'encaminhado_suporte_idoso',
                        'followup_sem_resposta',
                        'titular_menor_18', 'dependente_menor_4', 'dependente_menor_5',
                        'suporte_idoso_50', 'suporte_idoso_60', 'suporte_idoso_70', 'suporte_idoso_80',
                        'idade_universal_90'
                    )
                ),

            CONSTRAINT ck_conversa_turnos_sem_avanco
                CHECK (turnos_sem_avanco BETWEEN 0 AND 12),

            FOREIGN KEY (id_cliente)
                REFERENCES chatbot.cliente(id_cliente)
                ON DELETE CASCADE,

            FOREIGN KEY (id_unidade)
                REFERENCES chatbot.unidade(id_unidade)
                ON DELETE CASCADE,

            FOREIGN KEY (id_etapa_atual)
                REFERENCES chatbot.etapa(id_etapa)
                ON DELETE SET NULL
        );

        CREATE UNIQUE INDEX IF NOT EXISTS idx_conversa_unica_ativa
        ON chatbot.conversa (id_cliente, id_unidade)
        WHERE status_ativa = TRUE;

        CREATE INDEX IF NOT EXISTS idx_conversa_followup
        ON chatbot.conversa (
            last_message_from,
            followup_stage,
            last_interaction_at
        );

        CREATE INDEX IF NOT EXISTS idx_conversa_processing
        ON chatbot.conversa (processing, processing_started_at);

        CREATE INDEX IF NOT EXISTS idx_conversa_ultima_inativa
        ON chatbot.conversa (id_cliente, id_unidade, finalizou_em DESC)
        INCLUDE (id_conversa, id_etapa_atual)
        WHERE status_ativa = FALSE;

        CREATE INDEX IF NOT EXISTS idx_conversa_funil_pendente
        ON chatbot.conversa (id_etapa_atual, id_conversa)
        WHERE lead_no_funil IS NOT TRUE;

        -- 4. DEPENDENTE: EXISTE SOMENTE DENTRO DE UMA CONVERSA

        CREATE TABLE IF NOT EXISTS chatbot.dependente (
            id_dependente SERIAL PRIMARY KEY,
            id_cliente INT NOT NULL,
            id_conversa INT,
            nome_dependente VARCHAR(200),
            idade INTEGER,

            FOREIGN KEY (id_cliente)
                REFERENCES chatbot.cliente(id_cliente)
                ON DELETE CASCADE,

            CONSTRAINT dependente_id_conversa_fkey
                FOREIGN KEY (id_conversa)
                REFERENCES chatbot.conversa(id_conversa)
                ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_dependente_cliente
        ON chatbot.dependente (id_cliente);

        CREATE UNIQUE INDEX IF NOT EXISTS uq_dependente_conversa
        ON chatbot.dependente (id_conversa)
        WHERE id_conversa IS NOT NULL;

        CREATE INDEX IF NOT EXISTS idx_dependente_conversa
        ON chatbot.dependente (id_conversa);

        -- 5. FILA: CRIADA ANTES DO HISTÓRICO PARA A FK NASCER PRONTA

        CREATE TABLE IF NOT EXISTS chatbot.fila_mensagens (
            id_mensagem SERIAL PRIMARY KEY,
            id_conversa INT NULL,
            status VARCHAR(20) NOT NULL DEFAULT 'pending',
            retry_count INTEGER DEFAULT 0,
            next_attempt_at TIMESTAMPTZ DEFAULT NOW(),
            processing_started_at TIMESTAMPTZ NULL,
            received_data_hora TIMESTAMPTZ NOT NULL,
            cliente_telefone VARCHAR(100) NOT NULL,
            conteudo_texto TEXT,
            tipo_mensagem VARCHAR(20) NOT NULL,
            id_hash_msg VARCHAR(255) UNIQUE NOT NULL,
            id_phone_unidade VARCHAR(100) NOT NULL,
            unidade_telefone VARCHAR(100) NOT NULL,
            last_error TEXT,

            FOREIGN KEY (id_conversa)
                REFERENCES chatbot.conversa(id_conversa)
                ON DELETE SET NULL,

            CHECK (status IN ('pending', 'processing', 'sent', 'failed'))
        );

        CREATE INDEX IF NOT EXISTS idx_fila_pending_next_attempt
        ON chatbot.fila_mensagens (next_attempt_at, id_mensagem)
        WHERE status = 'pending';

        CREATE INDEX IF NOT EXISTS idx_fila_processing_timeout
        ON chatbot.fila_mensagens (processing_started_at, id_mensagem)
        WHERE status = 'processing';

        CREATE INDEX IF NOT EXISTS idx_fila_conversa_aberta_data
        ON chatbot.fila_mensagens (
            id_conversa,
            received_data_hora,
            id_mensagem
        )
        WHERE id_conversa IS NOT NULL
          AND status IN ('pending', 'processing');

        -- 6. HISTÓRICO PARTICIONADO E RESPOSTAS DA TRIAGEM

        CREATE TABLE IF NOT EXISTS chatbot.historico_mensagens (
            id_mensagem SERIAL,
            id_conversa INT NOT NULL,
            id_etapa INT,
            received_data_hora TIMESTAMPTZ NOT NULL,
            cliente_telefone VARCHAR(100) NOT NULL,
            conteudo_texto TEXT,
            tipo_mensagem VARCHAR(20) NOT NULL,
            id_hash_msg VARCHAR(255) NOT NULL,
            id_mensagem_fila INT,
            id_hash_cliente_origem VARCHAR(255),
            id_phone_unidade VARCHAR(100) NOT NULL,
            unidade_telefone VARCHAR(100) NOT NULL,
            quem_enviou VARCHAR(10) NOT NULL,
            status_envio VARCHAR(20),

            PRIMARY KEY (id_mensagem, received_data_hora),

            FOREIGN KEY (id_conversa)
                REFERENCES chatbot.conversa(id_conversa)
                ON DELETE CASCADE,

            FOREIGN KEY (id_etapa)
                REFERENCES chatbot.etapa(id_etapa)
                ON DELETE SET NULL,

            CONSTRAINT fk_historico_mensagem_fila
                FOREIGN KEY (id_mensagem_fila)
                REFERENCES chatbot.fila_mensagens(id_mensagem)
                ON DELETE SET NULL,

            CONSTRAINT chk_historico_quem_enviou
                CHECK (quem_enviou IN ('cliente', 'bot')),

            CONSTRAINT chk_historico_status_envio
                CHECK (
                    (quem_enviou = 'cliente' AND status_envio IS NULL)
                    OR
                    (
                        quem_enviou = 'bot'
                        AND status_envio IS NOT NULL
                        AND status_envio IN ('pending', 'sent', 'failed')
                    )
                )
        )
        PARTITION BY RANGE (received_data_hora);

        CREATE TABLE IF NOT EXISTS chatbot.historico_mensagens_default
        PARTITION OF chatbot.historico_mensagens
        DEFAULT;

        CREATE INDEX IF NOT EXISTS idx_historico_conversa_data
        ON chatbot.historico_mensagens (
            id_conversa,
            received_data_hora DESC,
            id_mensagem DESC
        );

        CREATE INDEX IF NOT EXISTS idx_historico_cliente_mensagem_fila
        ON chatbot.historico_mensagens (
            id_conversa,
            id_mensagem_fila,
            id_hash_msg,
            received_data_hora DESC,
            id_mensagem DESC
        )
        WHERE quem_enviou = 'cliente'
          AND id_mensagem_fila IS NOT NULL;

        CREATE INDEX IF NOT EXISTS idx_historico_bot_mensagem_fila
        ON chatbot.historico_mensagens (
            id_conversa,
            id_mensagem_fila,
            id_hash_cliente_origem,
            received_data_hora DESC,
            id_mensagem DESC
        )
        WHERE quem_enviou = 'bot'
          AND id_mensagem_fila IS NOT NULL
          AND id_hash_cliente_origem IS NOT NULL;

        CREATE TABLE IF NOT EXISTS chatbot.respostas_desafios (
            id_resposta_desafio SERIAL PRIMARY KEY,
            id_conversa INT NOT NULL,
            id_etapa INT NOT NULL,
            resposta VARCHAR(20) NOT NULL,
            id_historico_mensagem_cliente INT NULL,
            criado_em TIMESTAMPTZ NOT NULL DEFAULT NOW(),

            FOREIGN KEY (id_conversa)
                REFERENCES chatbot.conversa(id_conversa)
                ON DELETE CASCADE,

            FOREIGN KEY (id_etapa)
                REFERENCES chatbot.etapa(id_etapa),

            CONSTRAINT uq_respostas_desafios_conversa_etapa
                UNIQUE (id_conversa, id_etapa)
        );

        -- 7. PESQUISA DE SATISFACAO DO ATENDIMENTO

        CREATE TABLE IF NOT EXISTS chatbot.pesquisa_satisfacao (
            id_pesquisa_satisfacao SERIAL PRIMARY KEY,
            id_conversa INT NOT NULL UNIQUE,
            nota SMALLINT,
            comentario TEXT,
            criado_em TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            atualizado_em TIMESTAMPTZ NOT NULL DEFAULT NOW(),

            CONSTRAINT pesquisa_satisfacao_id_conversa_fkey
                FOREIGN KEY (id_conversa)
                REFERENCES chatbot.conversa(id_conversa)
                ON DELETE CASCADE,

            CONSTRAINT ck_pesquisa_satisfacao_nota
                CHECK (nota IS NULL OR nota BETWEEN 1 AND 5)
        );

        -- 8. FILA OPERACIONAL DO WORKER DE FUNIL

        CREATE TABLE IF NOT EXISTS chatbot.funil_envios (
            id_funil_envio SERIAL PRIMARY KEY,
            id_conversa INT NOT NULL UNIQUE,
            status VARCHAR(20) NOT NULL DEFAULT 'pending',
            attempt_count INTEGER NOT NULL DEFAULT 0,
            next_attempt_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            processing_started_at TIMESTAMPTZ,
            enviado_em TIMESTAMPTZ,
            ultimo_erro TEXT,
            resposta_funil TEXT,
            criado_em TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            atualizado_em TIMESTAMPTZ NOT NULL DEFAULT NOW(),

            CONSTRAINT funil_envios_id_conversa_fkey
                FOREIGN KEY (id_conversa)
                REFERENCES chatbot.conversa(id_conversa)
                ON DELETE CASCADE,

            CONSTRAINT ck_funil_envios_status
                CHECK (status IN ('pending', 'processing', 'sent')),

            CONSTRAINT ck_funil_envios_attempt_count
                CHECK (attempt_count >= 0)
        );

        CREATE INDEX IF NOT EXISTS idx_funil_envios_disponiveis
        ON chatbot.funil_envios (
            status,
            next_attempt_at,
            processing_started_at,
            id_funil_envio
        )
        WHERE status IN ('pending', 'processing');
        """)

        criar_tabelas_followup(cursor)

    logger.info("banco_setup_ok | acao=criar_tabelas")


def configurar_role_banco():
    """Aplica timezone e limites operacionais da role em uma transação."""
    with transacao_deploy("configurar_role_banco", logger) as cursor:
        cursor.execute("""
            ALTER ROLE fushi
            SET timezone TO 'America/Sao_Paulo';

            ALTER ROLE fushi
            SET idle_in_transaction_session_timeout = '30min';

            ALTER ROLE fushi
            SET statement_timeout = '10min';

            ALTER ROLE fushi
            SET lock_timeout = '15s';
        """)

    logger.info("banco_setup_ok | acao=configurar_role_banco role=fushi")
````

## Passo 08 — Alterar `callback/webhook/models.py`

Alinhar choices, número comercial obrigatório e ajuda da configuração.

Base SHA-256: `5e2f77be77792a021216f1a3b6f416d67fc7409de18a432112e74fab39396f69`. Conteúdo completo proposto: **464 linhas**.

````python
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
    nome_agente = models.CharField("nome do agente", max_length=100)
    genero = models.CharField(
        "gênero do agente",
        max_length=9,
        choices=Genero.choices,
    )
    cnpj = models.CharField(unique=True, max_length=50)
    email_responsavel = models.CharField(unique=True, max_length=255)
    telefone = models.CharField(unique=True, max_length=20)
    numero_comercial = models.CharField(
        max_length=30,
        help_text="Contato comercial obrigatório para toda unidade.",
    )
    idade_minima_suporte = models.IntegerField(
        "encaminhar titular ao comercial a partir de",
        blank=True,
        null=True,
        default=None,
        choices=[(None, "Desativado")] + [
            (idade, f"{idade}+") for idade in IDADES_MINIMAS_SUPORTE
        ],
        help_text=(
            "Na etapa de idade, encaminha somente o titular a partir do limite "
            "até 89 anos e encerra sem bloqueio; 90+ é universal. Não altera a regra de e-mail."
        ),
    )
    email_obrigatorio = models.BooleanField(
        "e-mail obrigatório",
        default=True,
        help_text=(
            "Exige um e-mail válido, exceto do titular com 60 anos ou mais."
        ),
    )
    waba_id = models.CharField(
        unique=True,
        max_length=100,
    )
    phone_number_id = models.CharField(unique=True, max_length=100)
    link_agendamento = models.CharField(unique=True, max_length=400)
    link_instagram = models.CharField(
        max_length=400,
        blank=True,
        null=True,
    )
    bpa_ativo = models.BooleanField(default=False)
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
````

## Passo 09 — Alterar `callback/webhook/admin.py`

Exigir contato comercial válido mesmo quando o suporte estiver desativado.

Base SHA-256: `2d6b5ebd9e43194c0ad7cdeec4d0794f4ddc00baf386965234f34ae78b8eda76`. Conteúdo completo proposto: **1405 linhas**.

````python
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
from core.integrations.whatsapp.numero_comercial import (
    numero_comercial_whatsapp_valido,
)
from core.logging_config import short_value
from core.repositories.unidades.cache_control import (
    incrementar_versao_cache_unidades,
)

from .models import (
    CacheControle,
    Cliente,
    ClienteBloqueadoMeta,
    Conversa,
    Dependente,
    Etapa,
    FilaMensagens,
    FunilEnvio,
    HistoricoMensagens,
    IntegracaoFunilUnidade,
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


@admin.register(Unidade)
class UnidadeAdmin(admin.ModelAdmin):

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
        "nome_agente",
        "cnpj",
        "telefone",
        "numero_comercial",
        "email_responsavel",
        "waba_id",
        "phone_number_id",
        "link_agendamento",
        "link_instagram",
    )

    list_filter = (
        "genero",
        "bpa_ativo",
        "idade_minima_suporte",
        "email_obrigatorio",
        "status_pagamento",
    )
    ordering = ("nome_unidade",)
    list_select_related = ("id_usuario_monitoramento",)

    list_per_page = 50
    empty_value_display = "-"

    def get_readonly_fields(self, request, obj=None):
        if obj is not None:
            return ("waba_id", "phone_number_id")

        return ()

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

                if (
                    not numero_comercial_whatsapp_valido(
                        self.cleaned_data.get("numero_comercial")
                    )
                ):
                    self.add_error(
                        "numero_comercial",
                        "Informe um número comercial brasileiro válido "
                        "para o contato da unidade, inclusive com suporte desativado.",
                    )

                if change or self.errors:
                    if change and not self.errors:
                        model_admin._validar_cache_unidades_form(
                            self,
                            request,
                            meta_validada=False,
                        )
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
````

## Passo 10 — Criar `core/repositories/monitoramento/encerramentos.py`

Ler última conversa e par histórico em lote; contar conversas encerradas por motivo e período.

Base SHA-256: `arquivo novo`. Conteúdo completo proposto: **69 linhas**.

````python
"""Leituras de encerramentos por idade; nunca reclassifica ou grava histórico."""

from core.validacoes.encerramento_por_idade import MOTIVOS_IDADE
from .painel import _linhas, _periodo


def buscar_encerramentos_atuais(id_unidade, ids_conversas, cursor):
    """Só a última conversa real pode qualificar um chat do período selecionado.

    O histórico adicional é lido em lote. O hash de origem sobrevive à limpeza
    da fila; não depender de id_mensagem_fila nem do cadastro atual do dependente.
    """
    ids = sorted(set(ids_conversas))
    if not ids:
        return []
    motivos = sorted(MOTIVOS_IDADE)
    marcadores_ids = ', '.join(['%s'] * len(ids))
    marcadores_motivos = ', '.join(['%s'] * len(motivos))
    cursor.execute(f"""
        SELECT c.id_conversa, c.id_cliente, c.status_dependente,
               c.motivo_encerramento, c.finalizou_em,
               b.conteudo_texto AS resposta_bot, b.tipo_mensagem AS tipo_bot,
               h.conteudo_texto AS resposta_idade
          FROM chatbot.conversa c
          JOIN chatbot.historico_mensagens b ON b.id_mensagem = (
              SELECT b0.id_mensagem FROM chatbot.historico_mensagens b0
               WHERE b0.id_conversa = c.id_conversa AND b0.id_etapa = 6
                 AND b0.quem_enviou = 'bot' AND b0.status_envio = 'sent'
               ORDER BY b0.received_data_hora DESC, b0.id_mensagem DESC LIMIT 1
          )
          LEFT JOIN chatbot.historico_mensagens h ON h.id_mensagem = (
              SELECT h0.id_mensagem FROM chatbot.historico_mensagens h0
               WHERE h0.id_conversa = c.id_conversa AND h0.quem_enviou = 'cliente'
                 AND h0.id_hash_msg = b.id_hash_cliente_origem
               ORDER BY h0.id_mensagem DESC LIMIT 1
          )
         WHERE c.id_unidade = %s AND c.id_conversa IN ({marcadores_ids})
           AND c.status_ativa = FALSE AND c.id_etapa_atual = 6
           AND c.finalizou_em IS NOT NULL
           AND c.motivo_encerramento IN ({marcadores_motivos})
           AND NOT EXISTS (
               SELECT 1 FROM chatbot.conversa posterior
                WHERE posterior.id_unidade = c.id_unidade
                  AND posterior.id_cliente = c.id_cliente
                  AND posterior.id_conversa > c.id_conversa
           )
    """, tuple([id_unidade] + ids + motivos))
    return _linhas(cursor)


def contar_encerramentos_por_motivo(id_unidade, inicio, fim, cursor):
    """Conta conversas encerradas no período, sem deduplicar pelo cliente.

    Sem joins multiplicadores: cada conversa participa exatamente uma vez.
    O serviço filtra as categorias segundo a mesma configuração usada no rótulo.
    """
    parametros = [id_unidade]
    periodo = _periodo('c.finalizou_em', inicio, fim, parametros)
    motivos = sorted(MOTIVOS_IDADE)
    marcadores = ', '.join(['%s'] * len(motivos))
    cursor.execute(f"""
        SELECT c.motivo_encerramento, c.status_dependente, COUNT(*) AS conversas
          FROM chatbot.conversa c
         WHERE c.id_unidade = %s AND c.status_ativa = FALSE
           AND c.id_etapa_atual = 6 AND c.finalizou_em IS NOT NULL {periodo}
           AND c.motivo_encerramento IN ({marcadores})
         GROUP BY c.motivo_encerramento, c.status_dependente
    """, tuple(parametros + motivos))
    return _linhas(cursor)
````

## Passo 11 — Criar `callback/monitoramento/encerramentos.py`

Separar apresentação histórica do chat e classificação do relatório pelas regras atuais.

Base SHA-256: `arquivo novo`. Conteúdo completo proposto: **88 linhas**.

````python
"""Apresentação dos motivos históricos e da tabela da configuração atual."""

from core.integrations.whatsapp.messages.etapa6_messages import reconhecer_encerramento_etapa6
from core.validacoes.encerramento_por_idade import (
    MOTIVO_IDADE_LEGADO,
    MOTIVO_SUPORTE_LEGADO,
    MOTIVO_TITULAR_MENOR,
    MOTIVO_UNIVERSAL,
    descrever_motivo_idade,
    motivo_dependente,
    motivo_suporte,
)
from core.validacoes.suporte_por_idade import validar_idade_minima_suporte


def apresentar_encerramento(linha):
    """O motivo salvo prevalece; textos conhecidos só esclarecem motivos legados."""
    motivo = linha['motivo_encerramento']
    informacao = descrever_motivo_idade(motivo)
    if informacao is None:
        return None
    reconhecida = reconhecer_encerramento_etapa6(linha['resposta_bot'], linha['tipo_bot'])
    if motivo == MOTIVO_IDADE_LEGADO:
        if not reconhecida or reconhecida['categoria'] == 'suporte':
            return None
        categoria = reconhecida['categoria']
        if categoria == 'titular_menor':
            informacao = descrever_motivo_idade(MOTIVO_TITULAR_MENOR)
        elif categoria == 'dependente_menor':
            informacao = descrever_motivo_idade(motivo_dependente(reconhecida['idade_minima']))
        else:
            informacao = {
                'tag': 'Idade avançada',
                'descricao': 'Encaminhamento universal anterior à identificação do limite no registro.',
                'contato_enviado': True,
            }
    elif motivo == MOTIVO_SUPORTE_LEGADO:
        # O registro prova suporte, mas não permite atribuir uma faixa histórica.
        informacao['descricao'] += ' Limite histórico não registrado.'
    return {
        **informacao,
        'id_conversa': linha['id_conversa'],
        'motivo': motivo,
        'participante': 'Dependente' if linha['status_dependente'] else 'Titular',
        'resposta_idade': linha.get('resposta_idade') or 'Não registrada',
        'nome_dependente': (reconhecida or {}).get('nome_dependente'),
    }


def montar_tabela_encerramentos(contagens, *, idade_minima_suporte, bpa_ativo):
    """Configuração atual filtra o relatório, sem alterar as tags dos chats.

    Registros genéricos não provam o limite aplicado e não entram nesta tabela.
    A mesma opção selecionada novamente inclui todos os motivos iguais no período.
    """
    suporte = validar_idade_minima_suporte(idade_minima_suporte)
    minimo = 4 if bpa_ativo else 5
    for item in contagens:
        if type(item['conversas']) is not int or item['conversas'] < 0:
            raise ValueError('Quantidade de conversas inválida')
    totais = {
        (item['motivo_encerramento'], bool(item['status_dependente'])): int(item['conversas'])
        for item in contagens if item['status_dependente'] is not None
    }
    linhas = []

    def adicionar(motivo, dependente, rotulo, encaminhado):
        linhas.append({
            'motivo': motivo,
            'rotulo': rotulo,
            'contato_enviado': encaminhado,
            'destino': 'Contato comercial enviado' if encaminhado else 'Encerrado sem encaminhamento',
            'conversas': totais.get((motivo, dependente), 0),
        })

    if suporte is not None:
        adicionar(motivo_suporte(suporte), False, f'Titulares · suporte {suporte}+ (até 89 anos)', True)
    adicionar(MOTIVO_UNIVERSAL, False, 'Titulares · 90+ (regra universal)', True)
    adicionar(MOTIVO_UNIVERSAL, True, 'Dependentes · 90+ (regra universal)', True)
    adicionar(MOTIVO_TITULAR_MENOR, False, 'Titulares · menos de 18 anos', False)
    adicionar(motivo_dependente(minimo), True, f'Dependentes · menos de {minimo} anos', False)
    return {
        'linhas': linhas,
        'total_encaminhadas': sum(l['conversas'] for l in linhas if l['contato_enviado']),
        'total_sem_encaminhamento': sum(l['conversas'] for l in linhas if not l['contato_enviado']),
        'idade_minima_suporte': suporte,
        'idade_minima_dependente': minimo,
    }
````

## Passo 12 — Alterar `callback/monitoramento/apresentacao.py`

Retirar o indicador escalar antigo do contrato de apresentação do relatório.

Base SHA-256: `c332a2590feee409785d639033e37f28ff2a877e03892a788bdfb42840b7bac5`. Conteúdo completo proposto: **246 linhas**.

````python
"""Transformações puras dos dados do painel, sem acesso ao banco."""

import re

from core.integrations.whatsapp.messages.etapa2_messages import montar_botoes_etapa2
from core.integrations.whatsapp.messages.etapa3_messages import montar_botoes_etapa3
from core.integrations.whatsapp.messages.etapa7_messages import montar_botoes_etapa7
from core.integrations.whatsapp.messages.etapa9_messages import montar_botoes_etapa9
from core.integrations.whatsapp.messages.etapa11_messages import montar_botoes_etapa11
from core.integrations.whatsapp.messages.etapa18_messages import montar_botoes_etapa18
from core.integrations.whatsapp.messages.etapa19_messages import montar_opcoes_satisfacao_etapa19
from core.integrations.whatsapp.messages.etapa20_messages import montar_botoes_etapa20
from core.integrations.whatsapp.messages.triagem_componentes import montar_botoes_triagem


_BOTOES_POR_ETAPA = {
    2: montar_botoes_etapa2,
    3: montar_botoes_etapa3,
    7: montar_botoes_etapa7,
    9: montar_botoes_etapa9,
    11: montar_botoes_etapa11,
    12: montar_botoes_triagem,
    13: montar_botoes_triagem,
    14: montar_botoes_triagem,
    15: montar_botoes_triagem,
    16: montar_botoes_triagem,
    17: montar_botoes_triagem,
    18: montar_botoes_etapa18,
    19: lambda: [titulo for _, titulo in montar_opcoes_satisfacao_etapa19()],
    20: montar_botoes_etapa20,
}


# Ordem e grafia do modelo CSV distribuído pelo Google Contacts.
CABECALHO_CSV_GOOGLE_CONTATOS = (
    'Name Prefix',
    'First Name',
    'Middle Name',
    'Last Name',
    'Name Suffix',
    'Phonetic First Name',
    'Phonetic Middle Name',
    'Phonetic Last Name',
    'Nickname',
    'File As',
    'E-mail 1 - Label',
    'E-mail 1 - Value',
    'Phone 1 - Label',
    'Phone 1 - Value',
    'Address 1 - Label',
    'Address 1 - Country',
    'Address 1 - Street',
    'Address 1 - Extended Address',
    'Address 1 - City',
    'Address 1 - Region',
    'Address 1 - Postal Code',
    'Address 1 - PO Box',
    'Organization Name',
    'Organization Title',
    'Organization Department',
    'Birthday',
    'Event 1 - Label',
    'Event 1 - Value',
    'Relation 1 - Label',
    'Relation 1 - Value',
    'Website 1 - Label',
    'Website 1 - Value',
    'Custom Field 1 - Label',
    'Custom Field 1 - Value',
    'Notes',
    'Labels',
)


def botoes_para_mensagem(mensagem):
    tipo = str(mensagem.get('tipo') or '')
    if mensagem.get('quem_enviou') != 'bot' or not tipo.startswith('interactive'):
        return []
    fabrica = _BOTOES_POR_ETAPA.get(mensagem.get('id_etapa'))
    return list(fabrica()) if fabrica else []


def classificar_faixa(idade):
    if type(idade) is not int or idade <= 0 or idade >= 100:
        return None
    if idade < 18:
        return 'menor'
    if idade < 60:
        return 'adulto'
    return 'idoso'


def _perfil_resumido(status_dependente, faixa):
    if status_dependente is True:
        return f'dependente_{faixa}' if faixa else 'dependente'
    if status_dependente is False:
        return faixa
    return None


def consolidar_conversas(linhas):
    clientes = {}
    for linha in linhas:
        cliente = clientes.setdefault(linha['id_cliente'], {
            'id_cliente': linha['id_cliente'],
            'nome': linha.get('nome_cliente') or 'Cliente sem nome',
            'contato': linha.get('waid_telefone') or '',
            'email': linha.get('email') or '',
            'profissao': linha.get('profissao_cliente') or linha.get('profissao_conversa') or '',
            'ids_conversa': [], 'perfis': set(), 'perfis_resumidos': set(),
            'dependentes': set(),
            'foi_funil': False, 'avaliada': False, 'followup_stage': 0,
            'ultima_atividade': None, 'ultima_mensagem': '',
            'ultima_mensagem_id': None,
        })
        cliente['ids_conversa'].append(linha['id_conversa'])
        cliente['foi_funil'] |= bool(linha.get('foi_funil'))
        cliente['avaliada'] |= bool(linha.get('avaliada'))
        # A consulta já exclui o follow-up de atendimentos substituídos por outro.
        cliente['followup_stage'] = max(
            cliente['followup_stage'], linha.get('followup_stage_atual') or 0,
        )
        status_dependente = linha.get('status_dependente')
        dependente = status_dependente is True
        if dependente:
            cliente['perfis'].add('dependente')
            if linha.get('nome_dependente'):
                cliente['dependentes'].add(str(linha['nome_dependente']))
        idade = (
            linha.get('idade_dependente') if dependente
            else linha.get('idade_titular') if status_dependente is False
            else None
        )
        faixa = classificar_faixa(idade)
        if faixa:
            cliente['perfis'].add(faixa)
        perfil_resumido = _perfil_resumido(status_dependente, faixa)
        if perfil_resumido:
            cliente['perfis_resumidos'].add(perfil_resumido)
        atividade = linha.get('ultima_atividade')
        id_mensagem = linha.get('ultima_mensagem_id') or 0
        if atividade and (
            cliente['ultima_atividade'] is None
            or atividade > cliente['ultima_atividade']
            or (
                atividade == cliente['ultima_atividade']
                and id_mensagem > (cliente['ultima_mensagem_id'] or 0)
            )
        ):
            cliente['ultima_atividade'] = atividade
            cliente['ultima_mensagem'] = linha.get('ultima_mensagem') or ''
            cliente['ultima_mensagem_id'] = linha.get('ultima_mensagem_id')
    ordem = {'dependente': 0, 'menor': 1, 'adulto': 2, 'idoso': 3}
    ordem_resumida = {
        'dependente_menor': 0,
        'dependente_adulto': 1,
        'dependente_idoso': 2,
        'menor': 3,
        'adulto': 4,
        'idoso': 5,
        'dependente': 6,
    }
    for cliente in clientes.values():
        cliente['ids_conversa'].sort()
        cliente['perfis'] = sorted(cliente['perfis'], key=lambda item: ordem[item])
        cliente['perfis_resumidos'] = sorted(
            cliente['perfis_resumidos'], key=lambda item: ordem_resumida[item]
        )
        cliente['dependentes'] = sorted(cliente['dependentes'])
    return sorted(clientes.values(), key=lambda item: item['ultima_atividade'] or '', reverse=True)


def normalizar_telefone_google(valor):
    digitos = re.sub(r'\D', '', str(valor or ''))
    if len(digitos) in (10, 11):
        digitos = '55' + digitos
    if not re.fullmatch(r'[1-9]\d{7,14}', digitos):
        return ''
    return '+' + digitos


def separar_nome(valor):
    partes = str(valor or '').strip().split()
    if not partes:
        return '', ''
    return partes[0], ' '.join(partes[1:])


def proteger_celula_csv(valor):
    texto = str(valor or '')
    return "'" + texto if texto.startswith(('=', '+', '-', '@')) else texto


CABECALHO_CSV_ESSENCIAL = ('Nome', 'E-mail', 'Telefone')


def montar_linha_csv_essencial(*, primeiro_nome, sobrenome, email, telefone):
    """Mantém o nome completo em uma coluna, sem acrescentar rótulos comerciais."""
    nome = ' '.join(parte for parte in (primeiro_nome, sobrenome) if parte)
    # O telefone já está normalizado; remove só o código do Brasil, mantendo o DDD.
    telefone_essencial = telefone.removeprefix('+55')
    return [proteger_celula_csv(nome), proteger_celula_csv(email), telefone_essencial]


def montar_linha_csv_google_contatos(
    *,
    primeiro_nome,
    sobrenome,
    email,
    telefone,
    nome_unidade,
):
    """Posiciona os dados nas colunas exatas do modelo do Google Contacts."""
    valores = {
        'First Name': proteger_celula_csv(primeiro_nome),
        'Last Name': proteger_celula_csv(sobrenome),
        'E-mail 1 - Label': 'Work' if email else '',
        'E-mail 1 - Value': proteger_celula_csv(email),
        'Phone 1 - Label': 'Mobile' if telefone else '',
        'Phone 1 - Value': telefone,
        'Notes': 'Contato exportado pelo monitoramento ESL Tech',
        'Labels': proteger_celula_csv(nome_unidade),
    }
    return [valores.get(coluna, '') for coluna in CABECALHO_CSV_GOOGLE_CONTATOS]


def montar_relatorio(
    metricas, anteriores, perfis, satisfacao, etapas, atividade,
):
    def variacao(atual, anterior):
        if atual is None or anterior is None:
            return None
        if anterior == 0:
            return 100.0 if atual else 0.0
        return round((atual - anterior) / anterior * 100, 1)
    tendencias = {}
    for chave in ('leads', 'mensagens', 'funil', 'avaliacoes', 'nota_media'):
        tendencias[chave] = variacao(metricas.get(chave, 0), anteriores.get(chave) if anteriores else None)
    return {
        'metricas': metricas,
        'tendencias': tendencias,
        'perfis': perfis,
        'satisfacao': satisfacao,
        'etapas': etapas,
        'atividade': atividade,
    }
````

## Passo 13 — Alterar `callback/monitoramento/services.py`

Integrar as consultas e transportar a tag do chat e a tabela do relatório.

Base SHA-256: `737ae94b02c1e6dbd7860f3a4a07e9d35d0eec2fa343e1be2b3636996b7091d3`. Conteúdo completo proposto: **242 linhas**.

````python
"""Orquestra leituras do painel a partir da unidade resolvida pelo guard."""

from zoneinfo import ZoneInfo

from core.validacoes.suporte_por_idade import validar_idade_minima_suporte

from django.db import connection

from core.repositories.monitoramento import painel as repositorio
from core.repositories.monitoramento import encerramentos as repositorio_encerramentos

from .apresentacao import (
    botoes_para_mensagem,
    classificar_faixa,
    consolidar_conversas,
    montar_relatorio,
)
from .encerramentos import apresentar_encerramento, montar_tabela_encerramentos
from .faixa_etaria import consultar_faixa_etaria, distribuir_dependentes_por_titular


FUSO_PAINEL = ZoneInfo('America/Sao_Paulo')


def _iso(valor):
    return valor.isoformat() if hasattr(valor, 'isoformat') else valor


def _no_fuso_painel(valor):
    if valor is None:
        return None
    if valor.tzinfo is None:
        return valor.replace(tzinfo=FUSO_PAINEL)
    return valor.astimezone(FUSO_PAINEL)


def _periodo_payload(periodo, unidade):
    inicio = periodo.inicio or unidade.get('inicio_historico')
    return {
        'chave': periodo.chave,
        'rotulo': periodo.rotulo,
        'inicio': _iso(inicio),
        'fim': _iso(periodo.fim),
        'texto': (
            f"{_no_fuso_painel(inicio).strftime('%d/%m/%Y %H:%M')} até agora"
            if inicio else 'Nenhuma conversa registrada até agora'
        ),
    }


def carregar_conversas(acesso, periodo):
    with connection.cursor() as cursor:
        unidade = repositorio.buscar_unidade(acesso.id_unidade, cursor)
        linhas = repositorio.listar_conversas(
            acesso.id_unidade, periodo.inicio, periodo.fim, cursor
        )
        metricas = repositorio.buscar_metricas(
            acesso.id_unidade, periodo.inicio, periodo.fim, cursor
        )
        encerramentos = repositorio_encerramentos.buscar_encerramentos_atuais(
            acesso.id_unidade, [linha['id_conversa'] for linha in linhas], cursor,
        )
    comerciais = {linha['id_cliente']: apresentar_encerramento(linha) for linha in encerramentos}
    conversas = consolidar_conversas(linhas)
    for item in conversas:
        item['ultima_atividade'] = _iso(item['ultima_atividade'])
        item['comercial'] = comerciais.get(item['id_cliente'])
    metricas['nota_media'] = float(metricas['nota_media']) if metricas.get('nota_media') is not None else None
    return {
        'unidade': {
            'nome': unidade['nome_unidade'],
            'agente': unidade['nome_agente'],
            'regras': {
                'idade_minima_suporte': validar_idade_minima_suporte(unidade['idade_minima_suporte']),
                'email_obrigatorio': bool(unidade['email_obrigatorio']),
                'bpa_ativo': bool(unidade['bpa_ativo']),
            },
        },
        'periodo': _periodo_payload(periodo, unidade),
        'metricas': metricas,
        'conversas': conversas,
        'atualizado_em': _iso(periodo.fim),
    }


def carregar_mensagens(acesso, id_cliente, periodo):
    with connection.cursor() as cursor:
        linhas = repositorio.buscar_mensagens(
            acesso.id_unidade, id_cliente, periodo.inicio, periodo.fim, cursor
        )
    mensagens = []
    for linha in linhas:
        item = {
            'id_mensagem': linha['id_mensagem'],
            'id_conversa': linha['id_conversa'],
            'id_etapa': linha['id_etapa'],
            'data': _iso(linha['data']),
            'quem_enviou': linha['quem_enviou'],
            'tipo': linha['tipo'],
            'texto': linha['texto'] or f"[{linha['tipo'] or 'mensagem sem texto'}]",
        }
        item['botoes'] = botoes_para_mensagem(item)
        mensagens.append(item)
    return {'id_cliente': id_cliente, 'mensagens': mensagens}


def _agrupar_perfis(linhas, *, bpa_ativo):
    minimo = 4 if bpa_ativo else 5
    chaves = ('dependente_menor', 'dependente_adulto', 'dependente_idoso', 'titular_adulto', 'titular_idoso')
    acumulado = {chave: {'clientes': set(), 'conversas': 0, 'funil': set()} for chave in chaves}
    todos_clientes = set()
    clientes_classificados = set()
    for linha in linhas:
        id_cliente = linha['id_cliente']
        todos_clientes.add(id_cliente)
        status_dependente = linha.get('status_dependente')
        if status_dependente not in (True, False) or type(status_dependente) is not bool:
            continue
        dependente = status_dependente is True
        idade = linha.get('idade_dependente') if dependente else linha.get('idade_titular')
        faixa = classificar_faixa(idade)
        if dependente and faixa == 'menor' and idade >= minimo:
            chave = 'dependente_menor'
        elif dependente and faixa in ('adulto', 'idoso'):
            chave = 'dependente_' + faixa
        elif not dependente and faixa in ('adulto', 'idoso'):
            chave = 'titular_' + faixa
        else:
            continue
        alvo = acumulado[chave]
        alvo['clientes'].add(id_cliente)
        alvo['conversas'] += 1
        clientes_classificados.add(id_cliente)
        if linha.get('foi_funil'):
            alvo['funil'].add(id_cliente)
    rotulos = {
        'dependente_menor': f'Dependentes de {minimo} a 17 anos',
        'dependente_adulto': 'Dependentes de 18 a 59 anos',
        'dependente_idoso': 'Dependentes com 60 anos ou mais',
        'titular_adulto': 'Titulares de 18 a 59 anos',
        'titular_idoso': 'Titulares com 60 anos ou mais',
    }
    resposta = []
    for chave in chaves:
        item = acumulado[chave]
        leads = len(item['clientes'])
        funil = len(item['funil'])
        resposta.append({
            'chave': chave, 'rotulo': rotulos[chave], 'leads': leads,
            'conversas': item['conversas'], 'funil': funil,
            'taxa_funil': round(funil / leads * 100, 1) if leads else 0,
            'funil_nao_aplicavel': False,
        })
    return {
        'linhas': resposta,
        'sem_classificacao': len(todos_clientes - clientes_classificados),
        'idade_minima_dependente': minimo,
    }


def _granularidade(periodo, unidade):
    inicio = periodo.inicio or unidade.get('inicio_historico')
    if not inicio:
        return 'dia'
    dias = (periodo.fim - inicio).days
    return 'mes' if dias > 180 else 'semana' if dias > 60 else 'dia'


def carregar_relatorio(acesso, periodo):
    with connection.cursor() as cursor:
        unidade = repositorio.buscar_unidade(acesso.id_unidade, cursor)
        metricas = repositorio.buscar_metricas(acesso.id_unidade, periodo.inicio, periodo.fim, cursor)
        contagens_idade = repositorio_encerramentos.contar_encerramentos_por_motivo(
            acesso.id_unidade, periodo.inicio, periodo.fim, cursor,
        )
        anteriores = None
        if periodo.inicio_anterior is not None:
            anteriores = repositorio.buscar_metricas(
                acesso.id_unidade, periodo.inicio_anterior, periodo.fim_anterior, cursor
            )
        perfis_brutos = repositorio.buscar_perfis(acesso.id_unidade, periodo.inicio, periodo.fim, cursor)
        satisfacao_bruta = repositorio.buscar_satisfacao(acesso.id_unidade, periodo.inicio, periodo.fim, cursor)
        etapas = repositorio.buscar_etapas(acesso.id_unidade, periodo.inicio, periodo.fim, cursor)
        atividade = repositorio.buscar_atividade(
            acesso.id_unidade, periodo.inicio, periodo.fim, cursor,
            _granularidade(periodo, unidade),
        )
    for grupo in (metricas, anteriores or {}):
        if grupo.get('nota_media') is not None:
            grupo['nota_media'] = float(grupo['nota_media'])
    satisfacao = {str(nota): 0 for nota in range(1, 6)}
    for linha in satisfacao_bruta:
        satisfacao[str(linha['nota'])] = linha['quantidade']
    for linha in etapas:
        linha['quantidade'] = int(linha['quantidade'])
    for linha in atividade:
        # DATE_TRUNC sobre AT TIME ZONE devolve timestamp sem fuso. O offset
        # explícito impede o navegador de interpretar o agrupamento como UTC.
        linha['periodo'] = _iso(_no_fuso_painel(linha['periodo']))
    relatorio = montar_relatorio(
        metricas, anteriores,
        _agrupar_perfis(
            perfis_brutos,
            bpa_ativo=bool(unidade['bpa_ativo']),
        ),
        satisfacao, etapas, atividade,
    )
    relatorio.update({
        'encerramentos_por_idade': montar_tabela_encerramentos(
            contagens_idade,
            idade_minima_suporte=unidade['idade_minima_suporte'],
            bpa_ativo=bool(unidade['bpa_ativo']),
        ),
        'dependentes_por_titular': distribuir_dependentes_por_titular(perfis_brutos),
        'unidade': {
            'nome': unidade['nome_unidade'],
            'idade_minima_suporte': validar_idade_minima_suporte(unidade['idade_minima_suporte']),
        },
        'periodo': _periodo_payload(periodo, unidade),
        'atualizado_em': _iso(periodo.fim),
    })
    return relatorio


def carregar_faixa_etaria(acesso, periodo, idade_minima, publico):
    with connection.cursor() as cursor:
        linhas = repositorio.buscar_perfis(
            acesso.id_unidade, periodo.inicio, periodo.fim, cursor,
        )
    resultado = consultar_faixa_etaria(linhas, idade_minima, publico)
    resultado['periodo'] = {
        'chave': periodo.chave, 'rotulo': periodo.rotulo,
        'inicio': _iso(periodo.inicio), 'fim': _iso(periodo.fim),
    }
    return resultado


def carregar_contatos(acesso, periodo):
    with connection.cursor() as cursor:
        return repositorio.listar_contatos(
            acesso.id_unidade, periodo.inicio, periodo.fim, cursor
        )
````

## Passo 14 — Alterar `callback/monitoramento/templates/monitoramento/painel.html`

Substituir Continuações por Comercial, incluir legenda acessível e versionar os assets.

Base SHA-256: `77645fe124f1f01c8012d4b0e3533a408e63266c37dae591fd996e302471cb5b`. Conteúdo completo proposto: **113 linhas**.

````html
{% load static %}
<!doctype html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
  <meta name="robots" content="noindex, nofollow">
  <meta name="theme-color" content="#1c321d">
  <meta name="referrer" content="same-origin">
  <title>Monitoramento · ESL Tech</title>
  <link rel="stylesheet" href="{% static 'monitoramento/css/painel.css' %}?v=20260926-comercial-idade">
  <script src="{% static 'monitoramento/js/painel.js' %}?v=20260926-comercial-idade" defer></script>
</head>
<body data-url-conversas="{% url 'monitoramento:dados_conversas' %}"
      data-url-mensagens="{% url 'monitoramento:dados_conversas' %}"
      data-url-relatorio="{% url 'monitoramento:dados_relatorio' %}"
      data-url-faixa-etaria="{% url 'monitoramento:dados_faixa_etaria' %}"
      data-url-csv="{% url 'monitoramento:contatos_csv' %}"
      data-url-login="{% url 'monitoramento:login' %}">
  <a class="skip-link" href="#conteudo">Ir para o conteúdo</a>
  <header class="cabecalho-app">
    <div class="marca-app">
      <img src="{% static 'monitoramento/img/esl-tech.svg' %}" alt="ESL Tech" width="116" height="48">
      <span class="divisor" aria-hidden="true"></span>
      <div><strong>Monitoramento</strong><span id="nomeUnidade">{{ nome_unidade }}</span></div>
    </div>
    <nav class="seletor-secao" aria-label="Seções do monitoramento">
      <button type="button" class="ativo" data-secao="conversas" aria-pressed="true">
        <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 5h16v11H8l-4 3V5Z"/></svg>Conversas
      </button>
      <button type="button" data-secao="relatorios" aria-pressed="false">
        <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M5 20V10m7 10V4m7 16v-7"/></svg>Relatórios
      </button>
    </nav>
    <div class="acoes-cabecalho">
      <span class="estado-atualizacao" id="estadoAtualizacao" role="status"><i></i>Atualizado agora</span>
      <form method="post" action="{% url 'monitoramento:sair' %}">{% csrf_token %}<button type="submit" class="botao-sair" aria-label="Sair da conta">Sair</button></form>
    </div>
  </header>

  <div class="faixa-consulta" role="note">
    <svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="9"/><path d="M12 11v5m0-8v.1"/></svg>
    <p><strong>Ambiente somente para monitoramento.</strong> Nenhuma mensagem pode ser enviada por aqui. Para falar com um contato, use o número comercial da unidade.</p>
  </div>

  <main id="conteudo">
    <section id="secaoConversas" class="secao-painel" aria-labelledby="tituloConversas">
      <header class="barra-contexto">
        <div><h1 id="tituloConversas">Conversas</h1><p id="periodoConversas">Carregando período…</p></div>
        <label class="seletor-periodo">Período
          <select data-periodo>
            {% for chave, rotulo in periodos %}<option value="{{ chave }}">{{ rotulo }}</option>{% endfor %}
          </select>
        </label>
      </header>
      <div class="app-conversas">
        <aside class="lista-conversas" aria-label="Lista de conversas">
          <div class="busca"><svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="10.8" cy="10.8" r="6.8"/><path d="m16 16 4 4"/></svg><input id="buscaConversas" type="search" placeholder="Pesquisar contato" aria-label="Pesquisar contato"></div>
          <div id="grupoFiltros" class="grupo-filtros">
          <nav class="filtros-conversas" aria-label="Filtrar conversas">
            <button type="button" class="ativo" data-filtro="todas">Todas</button>
            <button type="button" data-filtro="comercial">Comercial</button>
            <button type="button" data-filtro="followup">Follow-up</button>
            <button type="button" data-filtro="funil">Funil</button>
            <button type="button" data-filtro="avaliadas">Avaliadas</button>
          </nav>
          <button id="informacaoFiltros" class="informacao-filtros" type="button" aria-label="Entenda os filtros" aria-expanded="false" aria-controls="legendaFiltros">i</button>
          <div id="legendaFiltros" class="legenda-filtros" hidden>
            <strong>Entenda os filtros</strong>
            <dl>
              <dt>Todas</dt><dd>Chats com mensagens do cliente no período.</dd>
              <dt>Comercial</dt><dd>A última conversa encerrou por idade e merece análise. Nem todos receberam o contato comercial.</dd>
              <dt>Follow-up</dt><dd>A última conversa está no primeiro ou segundo follow-up. O segundo encerra o atendimento.</dd>
              <dt>Funil</dt><dd>Envio ao funil confirmado no período. Não confirma agendamento ou venda.</dd>
              <dt>Avaliadas</dt><dd>Nota de satisfação registrada no período.</dd>
            </dl>
          </div>
          </div>
          <div id="listaConversas" class="rolagem-lista" aria-live="polite"><div class="estado-vazio carregando">Carregando conversas…</div></div>
        </aside>
        <section class="janela-chat" aria-label="Histórico da conversa">
          <header class="topo-chat" id="topoChat" hidden>
            <button type="button" id="voltarConversas" class="voltar" aria-label="Voltar para a lista">‹</button>
            <div class="avatar" id="avatarContato"></div>
            <div class="identidade-contato"><h2 id="nomeContato"></h2><p id="detalhesContato"></p><div id="tagsContato" class="tags-contato"></div></div>
            <button type="button" id="alternarDetalhes" class="detalhes-botao" aria-expanded="false">Detalhes</button>
          </header>
          <div class="painel-detalhes" id="painelDetalhes" hidden></div>
          <div class="mensagens" id="mensagensChat">
            <div class="marca-dagua" aria-hidden="true"><img src="{% static 'monitoramento/img/esl-tech.svg' %}" alt=""></div>
            <div class="boas-vindas"><span>ESL Tech</span><h2>Acompanhe cada atendimento.</h2><p>Selecione um contato para visualizar toda a conversa consolidada.</p></div>
          </div>
          <button id="irFinal" type="button" class="ir-final" aria-label="Ir para a mensagem mais recente" hidden>↓</button>
          <footer class="rodape-chat">Conteúdo privado da unidade · consulta somente leitura</footer>
        </section>
      </div>
    </section>

    <section id="secaoRelatorios" class="secao-painel secao-relatorios" aria-labelledby="tituloRelatorios" hidden>
      <header class="barra-contexto">
        <div><p class="sobrelinha">INTELIGÊNCIA COMERCIAL</p><h1 id="tituloRelatorios">Relatórios</h1><p id="periodoRelatorios">Selecione um período para interpretar os resultados.</p></div>
        <label class="seletor-periodo">Período
          <select data-periodo>
            {% for chave, rotulo in periodos %}<option value="{{ chave }}">{{ rotulo }}</option>{% endfor %}
          </select>
        </label>
      </header>
      <div id="conteudoRelatorio" class="conteudo-relatorio"><div class="cartao carregando-relatorio">Preparando os indicadores…</div></div>
    </section>
  </main>
  <div id="toast" class="toast" role="status" hidden></div>
</body>
</html>
````

## Passo 15 — Alterar `callback/monitoramento/static/monitoramento/js/painel.js`

Renderizar filtro, tag, detalhes, tabela e legenda; atualizar metadados sem exigir mensagem nova.

Base SHA-256: `0775c8b5960343064595febee8be2e025ec660c6bbeed103741bb5e6bfc8b860`. Conteúdo completo proposto: **490 linhas**.

````javascript
(() => {
  'use strict';
  const corpo=document.body, ids=id=>document.getElementById(id);
  const urls={conversas:corpo.dataset.urlConversas,mensagens:corpo.dataset.urlMensagens,relatorio:corpo.dataset.urlRelatorio,faixaEtaria:corpo.dataset.urlFaixaEtaria,csv:corpo.dataset.urlCsv,login:corpo.dataset.urlLogin};
  const estado={secao:'conversas',periodo:'total',filtro:'todas',busca:'',conversas:[],selecionada:null,regras:{},carregandoConversas:false,recarregarConversas:false,carregandoRelatorio:false,recarregarRelatorio:false,sequenciaConversas:0,sequenciaRelatorio:0};
  const consultaIdade={cartao:null,sequencia:0,carregando:false};
  const criar=(tag,classe='',texto='')=>{const n=document.createElement(tag);if(classe)n.className=classe;if(texto!==''&&texto!==null)n.textContent=texto;return n;};
  const numero=new Intl.NumberFormat('pt-BR'), data=new Intl.DateTimeFormat('pt-BR',{dateStyle:'short',timeZone:'America/Sao_Paulo'}), dia=new Intl.DateTimeFormat('pt-BR',{dateStyle:'long',timeZone:'America/Sao_Paulo'}), hora=new Intl.DateTimeFormat('pt-BR',{hour:'2-digit',minute:'2-digit',timeZone:'America/Sao_Paulo'}), curto=new Intl.DateTimeFormat('pt-BR',{day:'2-digit',month:'short',timeZone:'America/Sao_Paulo'});
  const cores=['#37663d','#5d568f','#a35b38','#44758a','#8a4f67','#4d7468','#7b683b'];
  async function json(url){const a=new AbortController(),t=setTimeout(()=>a.abort(),15000);try{const r=await fetch(url,{headers:{Accept:'application/json'},credentials:'same-origin',cache:'no-store',signal:a.signal});let d={};try{d=await r.json();}catch(_e){}if(r.status===401){location.assign(urls.login);throw new Error('Sessão expirada.');}if(!r.ok)throw new Error(d.erro||'Não foi possível carregar os dados.');return d;}finally{clearTimeout(t);}}
  const urlPeriodo=(base,periodo=estado.periodo)=>base+'?periodo='+encodeURIComponent(periodo);
  function status(texto,tipo=''){const n=ids('estadoAtualizacao');n.className='estado-atualizacao '+tipo;n.lastChild.textContent=texto;}
  function toast(texto){const n=ids('toast');n.textContent=texto;n.hidden=false;clearTimeout(toast.timer);toast.timer=setTimeout(()=>n.hidden=true,4500);}
  const iniciais=nome=>(nome||'?').split(/\s+/).slice(0,2).map(p=>p[0]||'').join('').toUpperCase();
  const cor=id=>cores[Math.abs(Number(id)||0)%cores.length];
  const perfil=p=>({dependente:'Dependente',menor:'Menor de 18',adulto:'Adulto',idoso:'60+'}[p]||p);
  const perfisResumidos={
    dependente_menor:{curto:'DP -18',completo:'Dependente menor de 18 anos'},
    dependente_adulto:{curto:'DP 18–59',completo:'Dependente de 18 a 59 anos'},
    dependente_idoso:{curto:'DP 60+',completo:'Dependente com 60 anos ou mais'},
    dependente:{curto:'DP',completo:'Dependente sem faixa etária informada'},
    menor:{curto:'-18',completo:'Titular menor de 18 anos'},
    adulto:{curto:'18–59',completo:'Titular de 18 a 59 anos'},
    idoso:{curto:'60+',completo:'Titular com 60 anos ou mais'},
  };
  function visivel(i){if(estado.filtro==='comercial'&&!i.comercial)return false;if(estado.filtro==='followup'&&![1,2].includes(i.followup_stage))return false;if(estado.filtro==='funil'&&!i.foi_funil)return false;if(estado.filtro==='avaliadas'&&!i.avaliada)return false;const b=estado.busca.trim().toLocaleLowerCase('pt-BR');return !b||[i.nome,i.contato,i.email,i.profissao,i.ultima_mensagem,...i.dependentes].filter(Boolean).join(' ').toLocaleLowerCase('pt-BR').includes(b);}
  function mini(pai,texto,classe=''){pai.appendChild(criar('span','mini-tag '+classe,texto));}
  function renderLista(){
    const lista=ids('listaConversas');
    const itens=estado.conversas.filter(visivel);
    lista.replaceChildren();

    if(!itens.length){
      lista.appendChild(criar('div','estado-vazio',estado.conversas.length?'Nenhum contato corresponde à pesquisa ou filtro.':'Nenhuma conversa neste período.'));
      return;
    }

    itens.forEach(item=>{
      const botao=criar('button','item-conversa');
      const avatar=criar('div','avatar',iniciais(item.nome));
      const corpo=criar('div','item-corpo');
      const cabecalho=criar('div','item-linha');
      const metadados=criar('span','item-metadados');
      const perfisResumo=criar('span','perfis-resumidos-item');
      const dataAtividade=criar('time','',item.ultima_atividade?data.format(new Date(item.ultima_atividade)):'—');

      botao.type='button';
      botao.dataset.cliente=String(item.id_cliente);
      if(estado.selecionada===item.id_cliente)botao.classList.add('ativo');
      avatar.style.background=cor(item.id_cliente);

      (item.perfis_resumidos||[]).forEach(chave=>{
        const classe=chave.replaceAll('_','-');
        const perfilAtual=perfisResumidos[chave]||{curto:chave,completo:chave};
        const etiqueta=criar('span','mini-tag perfil-resumido '+classe,perfilAtual.curto);
        etiqueta.title=perfilAtual.completo;
        etiqueta.setAttribute('aria-label',perfilAtual.completo);
        perfisResumo.appendChild(etiqueta);
      });
      if(perfisResumo.childElementCount)metadados.appendChild(perfisResumo);
      metadados.appendChild(dataAtividade);
      cabecalho.append(criar('strong','',item.nome),metadados);
      corpo.append(cabecalho,criar('div','item-previa',item.ultima_mensagem||'Sem conteúdo textual'));

      const tags=criar('div','mini-tags');
      if(item.comercial){
        const etiqueta=criar('span','mini-tag comercial',item.comercial.tag);
        etiqueta.title=item.comercial.descricao;
        tags.appendChild(etiqueta);
      }else{
        if(item.ids_conversa.length>1)mini(tags,item.ids_conversa.length+' conversas');
        if([1,2].includes(item.followup_stage))mini(tags,'Follow-up '+item.followup_stage,'followup');
        if(item.foi_funil)mini(tags,'Funil','funil');
        if(item.avaliada)mini(tags,'Avaliada','nota');
      }
      corpo.appendChild(tags);
      botao.append(avatar,corpo);
      botao.addEventListener('click',()=>abrir(item.id_cliente));
      lista.appendChild(botao);
    });
  }
  function detalhes(item){
    ids('nomeContato').textContent=item.nome;
    ids('avatarContato').textContent=iniciais(item.nome);
    ids('avatarContato').style.background=cor(item.id_cliente);
    const resumo=[];
    if(item.contato)resumo.push('Contato: '+item.contato);
    if(item.profissao)resumo.push('Profissão: '+item.profissao);
    ids('detalhesContato').textContent=resumo.join(' • ')||'Dados ainda não informados';
    const tags=ids('tagsContato');
    tags.replaceChildren();
    item.perfis.forEach(p=>tags.appendChild(criar('span','tag-contato '+p,perfil(p))));
    if(item.comercial)tags.appendChild(criar('span','tag-contato comercial',item.comercial.tag));
    else if(item.foi_funil)tags.appendChild(criar('span','tag-contato funil','Funil'));
    const campos=[['Contato',item.contato||'Não informado'],['Profissão',item.profissao||'Não informada']];
    if(estado.regras.email_obrigatorio||item.email)campos.push(['E-mail',item.email||'Obrigatório · não informado']);
    if(item.dependentes.length)campos.push(['Dependente(s)',item.dependentes.join(', ')]);
    if(item.comercial){
      const encerramento=item.comercial;
      campos.push(['Motivo deste encerramento',encerramento.descricao],
        ['Participante',encerramento.participante],
        ['Resposta sobre a idade',encerramento.resposta_idade],
        ['Contato comercial',encerramento.contato_enviado?'Enviado ao cliente':'Não enviado']);
      if(encerramento.nome_dependente)campos.push(['Dependente deste atendimento',encerramento.nome_dependente]);
    }
    campos.push(['Conversas técnicas',item.ids_conversa.join(', ')]);
    campos.push(['Regras atuais da unidade',[
      estado.regras.email_obrigatorio?'E-mail obrigatório':'E-mail opcional',
      politicaSuporte(estado.regras.idade_minima_suporte),
      estado.regras.bpa_ativo?'BPA ativo · mínimo 4 anos':'BPA inativo · mínimo 5 anos',
    ].join(' · ')]);
    const lista=criar('dl');
    campos.forEach(([rotulo,valor])=>{
      const grupo=criar('div');
      grupo.append(criar('dt','',rotulo),criar('dd','',valor));
      lista.appendChild(grupo);
    });
    ids('painelDetalhes').replaceChildren(lista);
  }
  function marca(){const c=criar('div','marca-dagua');c.setAttribute('aria-hidden','true');const i=document.querySelector('.marca-app img').cloneNode();i.alt='';c.appendChild(i);return c;}
  function renderMensagens(ms,{manter=false}={}){const c=ids('mensagensChat'),final=c.scrollHeight-c.scrollTop-c.clientHeight<120,topo=c.scrollTop;c.replaceChildren(marca());let d='',conv=null;ms.forEach(m=>{const dt=new Date(m.data),nd=dia.format(dt);if(nd!==d){c.appendChild(criar('div','dia',nd));d=nd;}if(conv!==m.id_conversa){c.appendChild(criar('div','separador-conversa',(conv===null?'Início':'Continuação')+' do atendimento · conversa '+m.id_conversa));conv=m.id_conversa;}const l=criar('div','linha-mensagem '+(m.quem_enviou==='bot'?'bot':'cliente')),b=criar('div','bolha');if(m.tipo&&m.tipo!=='text')b.appendChild(criar('span','tipo-mensagem',m.tipo.replaceAll('_',' ')));b.appendChild(criar('div','texto-mensagem',m.texto));if(m.botoes?.length){const bs=criar('div','botoes-mensagem');m.botoes.forEach(x=>{const bt=criar('button','botao-mensagem',x);bt.type='button';bt.disabled=true;bt.setAttribute('aria-label',x+' (botão histórico)');bs.appendChild(bt);});b.appendChild(bs);}const mt=criar('div','meta-mensagem');mt.appendChild(criar('span','','Etapa '+(m.id_etapa??'—')+' · '+hora.format(dt)));if(m.quem_enviou==='bot')mt.appendChild(criar('span','ticks','✓✓'));b.appendChild(mt);l.appendChild(b);c.appendChild(l);});if(!ms.length)c.appendChild(criar('div','boas-vindas','Nenhuma mensagem visível no período.'));requestAnimationFrame(()=>{if(!manter||final)c.scrollTop=c.scrollHeight;else c.scrollTop=topo;});}
  async function abrir(idCliente,{silencioso=false}={}){const i=estado.conversas.find(c=>c.id_cliente===idCliente);if(!i)return;const periodo=estado.periodo;estado.selecionada=idCliente;renderLista();detalhes(i);ids('topoChat').hidden=false;document.querySelector('.app-conversas').classList.add('chat-aberto');const c=ids('mensagensChat');if(!silencioso)c.replaceChildren(marca(),criar('div','estado-vazio carregando','Carregando histórico…'));try{const d=await json(urls.mensagens+idCliente+'/?periodo='+encodeURIComponent(periodo));if(estado.selecionada===idCliente&&estado.periodo===periodo)renderMensagens(d.mensagens,{manter:silencioso});}catch(e){if(estado.periodo!==periodo)return;if(!silencioso)c.replaceChildren(marca(),criar('div','estado-vazio',e.message));else toast('Não foi possível atualizar a conversa agora.');}}
  async function carregarConversas(silencioso=false){if(estado.carregandoConversas){estado.recarregarConversas=true;return;}estado.carregandoConversas=true;const periodo=estado.periodo,seq=++estado.sequenciaConversas;if(estado.secao==='conversas')status('Atualizando…','atualizando');try{const d=await json(urlPeriodo(urls.conversas,periodo));if(seq!==estado.sequenciaConversas||periodo!==estado.periodo)return;const velha=estado.conversas.find(c=>c.id_cliente===estado.selecionada);estado.conversas=d.conversas;estado.regras=d.unidade.regras;ids('nomeUnidade').textContent=d.unidade.nome;ids('periodoConversas').textContent='Agente '+d.unidade.agente+' · '+d.periodo.texto;renderLista();const nova=estado.conversas.find(c=>c.id_cliente===estado.selecionada);if(nova&&(!silencioso||!velha||nova.ultima_mensagem_id!==velha.ultima_mensagem_id||nova.ultima_atividade!==velha.ultima_atividade))await abrir(nova.id_cliente,{silencioso});else if(nova)detalhes(nova);else if(!estado.selecionada&&matchMedia('(min-width:721px)').matches&&estado.conversas[0])await abrir(estado.conversas[0].id_cliente);if(estado.secao==='conversas')status('Atualizado agora');}catch(e){if(seq!==estado.sequenciaConversas||periodo!==estado.periodo)return;if(estado.secao==='conversas')status('Falha ao atualizar','erro');if(!silencioso)ids('listaConversas').replaceChildren(criar('div','estado-vazio',e.message));else toast(e.message);}finally{estado.carregandoConversas=false;if(estado.recarregarConversas){estado.recarregarConversas=false;void carregarConversas(true);}}}
  function tend(v){if(v==null)return['Histórico completo',''];if(v===0)return['Sem variação ante o período anterior',''];return[(v>0?'↑ ':'↓ ')+Math.abs(v).toLocaleString('pt-BR')+'% ante o período anterior',v>0?'positiva':'negativa'];}
  function kpi(rotulo,valor,v){const c=criar('article','cartao kpi'),t=tend(v);c.append(criar('span','rotulo',rotulo),criar('strong','',valor),criar('span','tendencia '+t[1],t[0]));return c;}
  function titulo(t,d,l=''){const h=criar('header','titulo-cartao'),x=criar('div');x.append(criar('h2','',t),criar('p','',d));h.appendChild(x);if(l)h.appendChild(criar('span','legenda',l));return h;}
  function atividade(ds){
    const componente=criar('div','grafico-atividade');
    if(!ds.length){
      componente.appendChild(criar('div','estado-vazio','Sem atividade no período.'));
      return componente;
    }

    const resumo=criar('p','grafico-resumo','Toque em uma barra para ver data, leads e mensagens.');
    resumo.setAttribute('aria-live','polite');
    const rolagem=criar('div','grafico-rolagem');
    const barras=criar('div','grafico-barras');
    const maximo=Math.max(1,...ds.flatMap(item=>[Number(item.leads)||0,Number(item.mensagens)||0]));

    ds.forEach((item,indice)=>{
      const leads=Number(item.leads)||0;
      const mensagens=Number(item.mensagens)||0;
      const dataCurta=curto.format(new Date(item.periodo));
      const descricao=dataCurta+': '+numero.format(leads)+' leads e '+numero.format(mensagens)+' mensagens';
      const coluna=criar('button','coluna-grafico');
      const barraLeads=criar('i');
      const barraMensagens=criar('i','barra-mensagens');

      coluna.type='button';
      coluna.title=descricao;
      coluna.setAttribute('aria-label',descricao);
      barraLeads.style.height=Math.max(2,leads/maximo*100)+'%';
      barraMensagens.style.height=Math.max(2,mensagens/maximo*100)+'%';
      coluna.append(barraLeads,barraMensagens);

      if(ds.length<35||indice%Math.ceil(ds.length/16)===0){
        coluna.appendChild(criar('span','rotulo-data',dataCurta));
      }

      const mostrarResumo=()=>{resumo.textContent=descricao;};
      coluna.addEventListener('click',mostrarResumo);
      coluna.addEventListener('focus',mostrarResumo);
      coluna.addEventListener('mouseenter',mostrarResumo);
      barras.appendChild(coluna);
    });

    rolagem.appendChild(barras);
    componente.append(resumo,rolagem);
    return componente;
  }
  function satisfacao(ds){const c=criar('article','cartao');c.appendChild(titulo('Satisfação','Distribuição das notas registradas.'));const b=criar('div','barras-satisfacao'),max=Math.max(1,...Object.values(ds).map(Number));[5,4,3,2,1].forEach(n=>{const q=Number(ds[String(n)]||0),l=criar('div','barra-linha'),tr=criar('div','trilho'),i=criar('i');i.style.width=q/max*100+'%';tr.appendChild(i);l.append(criar('span','',n+' ★'),tr,criar('strong','',String(q)));b.appendChild(l);});c.appendChild(b);return c;}
  function perfis(ds){
    const colunas=['Perfil','Leads','Conversas','Funil','Taxa'];
    const cartao=criar('article','cartao');
    const tabela=criar('table','tabela-perfis');
    const cabecalho=criar('thead');
    const linhaCabecalho=criar('tr');

    cartao.appendChild(titulo('Perfil dos atendimentos','Faixas atuais; dependentes a partir de '+ds.idade_minima_dependente+' anos.'));
    colunas.forEach(coluna=>linhaCabecalho.appendChild(criar('th','',coluna)));
    cabecalho.appendChild(linhaCabecalho);
    tabela.appendChild(cabecalho);

    const corpoTabela=criar('tbody');
    ds.linhas.forEach(item=>{
      const linha=criar('tr');
      const valores=[
        item.rotulo,
        item.leads,
        item.conversas,
        item.funil,
        item.taxa_funil==null?'—':item.taxa_funil.toLocaleString('pt-BR')+'%',
      ];

      valores.forEach((valor,indice)=>{
        const celula=criar('td','',String(valor));
        celula.dataset.rotulo=colunas[indice];
        linha.appendChild(celula);
      });
      corpoTabela.appendChild(linha);
    });

    tabela.appendChild(corpoTabela);
    cartao.appendChild(tabela);
    if(ds.sem_classificacao){
      cartao.appendChild(criar('p','tendencia',ds.sem_classificacao+' lead(s) sem classificação etária completa.'));
    }
    return cartao;
  }
  function etapas(ds){const c=criar('article','cartao');c.appendChild(titulo('Onde os atendimentos estão','Etapa atual da conversa mais recente de cada contato ativo no período.','22 etapas'));const lista=criar('div','etapas-lista'),max=Math.max(1,...ds.map(e=>Number(e.quantidade)));ds.forEach(e=>{const l=criar('div','etapa-linha'),tr=criar('div','trilho'),i=criar('i');i.style.width=Number(e.quantidade)/max*100+'%';tr.appendChild(i);l.append(criar('span','etapa-numero',String(e.id_etapa)),criar('span','etapa-nome',e.nome_etapa),tr,criar('strong','',String(e.quantidade)));lista.appendChild(l);});c.appendChild(lista);return c;}
  function exportacao(formato='google'){
    const essencial=formato==='essencial';
    const cartao=criar('article','cartao exportacao');
    const descricao=criar('div');
    const botoes=criar('div','botoes-download');
    const titulo=essencial?'Baixe os dados essenciais':'Leve os contatos para o Google Contatos';
    const explicacao=essencial
      ?'CSV com apenas Nome, E-mail e Telefone do período selecionado. O nome completo fica em uma coluna. Elegíveis possuem os três dados; campos ausentes ficam vazios no arquivo completo.'
      :'Arquivos no formato Google CSV. Elegíveis possuem nome, e-mail e telefone; campos ausentes ficam vazios no arquivo completo. Para mais de 3.000 contatos, escolha períodos menores antes de importar no Google.';

    descricao.append(criar('h2','',titulo),criar('p','',explicacao));
    [['Baixar todos os contatos','todos'],['Baixar apenas elegíveis','elegiveis']].forEach(([texto,tipo])=>{
      const link=criar('a','botao-download'+(tipo==='elegiveis'?' primario':''),texto);
      const parametros=new URLSearchParams({periodo:estado.periodo,tipo});
      if(essencial)parametros.set('formato','essencial');
      link.href=urls.csv+'?'+parametros;
      link.setAttribute('aria-label',texto+' — '+(essencial?'CSV essencial':'Google CSV'));
      botoes.appendChild(link);
    });
    cartao.append(descricao,botoes);
    return cartao;
  }
  function politicaSuporte(limite){
    return limite===null?'Encaminhamento por idade: desativado':'Encaminhamento ao comercial: '+limite+'+';
  }
  function invalidarConsultaIdade(mensagem='Informe a idade mínima, escolha o público e clique em Consultar.'){
    consultaIdade.sequencia++;
    consultaIdade.carregando=false;
    if(!consultaIdade.cartao)return;
    consultaIdade.botao.disabled=false;
    consultaIdade.botao.textContent='Consultar';
    consultaIdade.idade.removeAttribute('aria-invalid');
    consultaIdade.resultado.className='resultado-faixa vazio';
    consultaIdade.resultado.setAttribute('aria-busy','false');
    consultaIdade.resultado.replaceChildren(criar('p','',mensagem));
  }
  function validarResultadoFaixa(d,idade,publico,periodo){
    const grupos=[d.titulares,d.dependentes];
    const valido=d.idade_minima===idade&&d.publico===publico&&d.periodo?.chave===periodo
      &&Number.isSafeInteger(d.total)&&d.total>=0&&Number.isSafeInteger(d.contatos)&&d.contatos>=0
      &&grupos.every(g=>g&&Number.isSafeInteger(g.leads)&&g.leads>=0&&Number.isSafeInteger(g.funil)&&g.funil>=0&&g.funil<=g.leads)
      &&d.total===grupos[0].leads+grupos[1].leads&&d.contatos<=d.total
      &&!Number.isNaN(new Date(d.periodo.fim).getTime());
    if(!valido)throw new Error('Não foi possível conferir o resultado. Consulte novamente.');
  }
  function mostrarResultadoFaixa(d){
    const t=d.titulares,p=d.dependentes,idade=numero.format(d.idade_minima)+(d.idade_minima===1?' ano':' anos');
    const contar=(n,singular,plural)=>numero.format(n)+' '+(n===1?singular:plural);
    const tabela=criar('table','tabela-resultado-faixa');
    tabela.appendChild(criar('caption','','Leads com idade igual ou acima de '+idade));
    const cabecalho=criar('thead'),colunas=criar('tr');
    ['Público','Leads','Enviados ao funil'].forEach(texto=>{
      const coluna=criar('th','',texto);coluna.scope='col';colunas.appendChild(coluna);
    });
    cabecalho.appendChild(colunas);
    const linha=(rotulo,leads,funil)=>{
      const tr=criar('tr'),nome=criar('th','',rotulo);nome.scope='row';
      tr.append(nome,criar('td','',numero.format(leads)),criar('td','',numero.format(funil)));
      return tr;
    };
    const linhas=criar('tbody');
    if(d.publico!=='dependentes')linhas.appendChild(linha('Titulares',t.leads,t.funil));
    if(d.publico!=='titulares')linhas.appendChild(linha('Dependentes',p.leads,p.funil));
    tabela.append(cabecalho,linhas);
    if(d.publico==='todos'){
      const total=criar('tfoot');total.appendChild(linha('Total',d.total,t.funil+p.funil));tabela.appendChild(total);
    }
    const detalhe=contar(d.contatos,'contato representado','contatos representados')+' · '+d.periodo.rotulo
      +' · Consultado em '+data.format(new Date(d.periodo.fim))+' às '+hora.format(new Date(d.periodo.fim));
    consultaIdade.resultado.className='resultado-faixa';
    consultaIdade.resultado.replaceChildren(tabela,criar('p','detalhe-faixa',detalhe));
  }
  async function consultarIdade(evento){
    evento.preventDefault();
    if(consultaIdade.carregando)return;
    const texto=consultaIdade.idade.value.trim();
    if(!/^[0-9]{1,3}$/.test(texto)||Number(texto)<1){
      invalidarConsultaIdade('Informe uma idade inteira entre 1 e 999 anos.');
      consultaIdade.resultado.classList.add('erro');
      consultaIdade.idade.setAttribute('aria-invalid','true');
      consultaIdade.idade.focus();
      return;
    }
    const idade=Number(texto),publico=consultaIdade.publico.value,periodo=estado.periodo;
    const sequencia=++consultaIdade.sequencia;
    consultaIdade.carregando=true;
    consultaIdade.botao.disabled=true;
    consultaIdade.botao.textContent='Consultando…';
    consultaIdade.resultado.className='resultado-faixa vazio';
    consultaIdade.resultado.setAttribute('aria-busy','true');
    consultaIdade.resultado.replaceChildren(criar('p','','Consultando os leads deste período…'));
    try{
      const parametros=new URLSearchParams({periodo,idade_minima:String(idade),publico});
      const d=await json(urls.faixaEtaria+'?'+parametros);
      if(sequencia!==consultaIdade.sequencia||periodo!==estado.periodo)return;
      validarResultadoFaixa(d,idade,publico,periodo);
      mostrarResultadoFaixa(d);
    }catch(e){
      if(sequencia!==consultaIdade.sequencia||periodo!==estado.periodo)return;
      consultaIdade.resultado.className='resultado-faixa erro';
      consultaIdade.resultado.replaceChildren(criar('p','',e.message));
    }finally{
      if(sequencia===consultaIdade.sequencia){
        consultaIdade.carregando=false;
        consultaIdade.botao.disabled=false;
        consultaIdade.botao.textContent='Consultar';
        consultaIdade.resultado.setAttribute('aria-busy','false');
      }
    }
  }
  function faixaEtariaPersonalizada(){
    // Reutilizar o formulário preserva digitação, seleção e resultado nos refreshes.
    if(consultaIdade.cartao)return consultaIdade.cartao;
    const cartao=criar('article','cartao consulta-faixa');
    cartao.id='consultaFaixaEtaria';
    cartao.appendChild(titulo('Consulta de faixa etária personalizada','Consulte leads com idade igual ou acima da informada e veja quantos foram enviados ao funil.'));
    const formulario=criar('form','formulario-faixa');formulario.noValidate=true;
    const campoIdade=criar('label','campo-faixa','Idade mínima (anos)');
    const idade=criar('input');idade.id='idadeMinimaConsulta';idade.name='idade_minima';
    idade.type='text';idade.inputMode='numeric';idade.maxLength=3;idade.placeholder='Ex.: 60';idade.required=true;
    idade.setAttribute('aria-describedby','resultadoFaixaEtaria');campoIdade.appendChild(idade);
    const campoPublico=criar('label','campo-faixa','Público');
    const publico=criar('select');publico.id='publicoConsulta';publico.name='publico';
    [['titulares','Apenas titulares'],['dependentes','Apenas dependentes'],['todos','Todos']].forEach(([valor,rotulo])=>{
      const opcao=criar('option','',rotulo);opcao.value=valor;publico.appendChild(opcao);
    });
    publico.value='todos';campoPublico.appendChild(publico);
    const botao=criar('button','botao-consultar','Consultar');botao.type='submit';
    formulario.append(campoIdade,campoPublico,botao);
    const resultado=criar('div','resultado-faixa vazio');resultado.id='resultadoFaixaEtaria';
    resultado.setAttribute('role','status');resultado.setAttribute('aria-live','polite');
    resultado.setAttribute('aria-atomic','true');
    cartao.append(formulario,resultado,criar('p','nota-faixa',
      'Titulares contam uma vez; cada cadastro de dependente conta separadamente. Considera apenas idades informadas e envios ao funil confirmados no período.'));
    Object.assign(consultaIdade,{cartao,idade,publico,botao,resultado});
    formulario.addEventListener('submit',consultarIdade);
    idade.addEventListener('input',()=>invalidarConsultaIdade());
    publico.addEventListener('change',()=>invalidarConsultaIdade());
    invalidarConsultaIdade();
    return cartao;
  }
  function dependentesPorTitular(d){
    const cartao=criar('article','cartao dependentes-titular');
    cartao.appendChild(titulo('Dependentes por titular','Distribuição no período selecionado, considerando todas as idades.'));
    if(!d||!Array.isArray(d.grupos)){
      cartao.appendChild(criar('p','nota-faixa','A distribuição está indisponível. Atualize o relatório.'));
      return cartao;
    }
    if(!d.grupos.length){
      cartao.appendChild(criar('p','nota-faixa','Nenhum dependente identificado nos atendimentos deste período.'));
      return cartao;
    }
    const grupos=criar('ul','grupos-dependentes');
    d.grupos.forEach(g=>{
      const item=criar('li','grupo-dependentes');
      item.append(criar('strong','',numero.format(g.titulares)+(g.titulares===1?' titular':' titulares')),
        criar('span','','com '+numero.format(g.dependentes_por_titular)+(g.dependentes_por_titular===1?' dependente':' dependentes')+' cada'));
      grupos.appendChild(item);
    });
    cartao.append(grupos,criar('p','nota-faixa','Cada cadastro de dependente conta separadamente, inclusive quando o mesmo titular tem atendimentos diferentes. Cadastros ainda sem nome e idade não entram nesta distribuição.'));
    return cartao;
  }
  function encaminhamentos(d){
    const dados=d.encerramentos_por_idade;
    if(!dados||!Array.isArray(dados.linhas)||dados.linhas.some(l=>!Number.isSafeInteger(l.conversas)||l.conversas<0)){
      throw new Error('Não foi possível obter os encerramentos por idade.');
    }
    const cartao=criar('article','cartao encerramentos-idade');
    cartao.appendChild(titulo('Encaminhamentos e encerramentos por idade',
      'Conversas encerradas no período, por motivos compatíveis com as regras atuais da unidade.'));
    const resumo=criar('div','resumo-encerramentos');
    [[dados.total_encaminhadas,'com contato comercial enviado'],
     [dados.total_sem_encaminhamento,'encerradas sem encaminhamento']].forEach(([total,rotulo])=>{
      const item=criar('p');
      item.append(criar('strong','',numero.format(total)),criar('span','',rotulo));
      resumo.appendChild(item);
    });
    const tabela=criar('table','tabela-encerramentos');
    tabela.appendChild(criar('caption','sr-only','Conversas encerradas por motivo no período selecionado'));
    const cabecalho=criar('thead'),titulos=criar('tr'),linhas=criar('tbody');
    ['Motivo','Destino','Conversas'].forEach(rotulo=>{
      const celula=criar('th','',rotulo);celula.scope='col';titulos.appendChild(celula);
    });
    cabecalho.appendChild(titulos);
    dados.linhas.forEach(item=>{
      const linha=criar('tr'),motivo=criar('th','',item.rotulo);
      motivo.scope='row';
      linha.append(motivo,criar('td','',item.destino),criar('td','quantidade',numero.format(item.conversas)));
      linhas.appendChild(linha);
    });
    tabela.append(cabecalho,linhas);
    const suporte=dados.idade_minima_suporte===null?'Suporte configurável desativado.':
      'Suporte atual: '+dados.idade_minima_suporte+'+ até 89 anos.';
    cartao.append(resumo,tabela,criar('p','nota-faixa',suporte+' Regra universal: 90+. Mínimo para dependentes: '+dados.idade_minima_dependente+' anos.'));
    cartao.appendChild(criar('p','nota-faixa','Cada conversa conta uma vez, pela data de encerramento. Motivos de configurações diferentes e registros antigos sem limite identificado não entram nesta tabela. Envio do contato não confirma clique ou atendimento humano.'));
    return cartao;
  }
  function interpretar(m){const c=criar('article','cartao como-interpretar');c.appendChild(criar('h2','','Como interpretar os números'));const ul=criar('ul');['Lead é um contato único que enviou mensagem no período selecionado.','Na consulta de faixa etária personalizada, cada titular conta uma vez e cada cadastro de dependente conta separadamente. O total pode superar o número de contatos. As idades são as atualmente cadastradas.','Funil é um envio confirmado no registro local; não confirma agendamento ou venda.','A tabela de encerramentos por idade conta conversas, pela data de encerramento e pelos motivos compatíveis com a configuração atual. O filtro Comercial mostra chats cuja última conversa exige análise comercial, inclusive menores que não receberam o contato da unidade.','A comparação usa a janela imediatamente anterior com a mesma duração. O histórico total não possui comparação.','A etapa mostra o estado atual da conversa mais recente de cada contato ativo no período; não reconstrói a etapa histórica daquele dia.','Participação em avaliações: '+(m.leads?Math.round((m.avaliacoes||0)/m.leads*1000)/10:0)+'% dos leads.'].forEach(x=>ul.appendChild(criar('li','',x)));c.appendChild(ul);return c;}
  function renderRelatorio(d){
    const foco=consultaIdade.cartao?.contains(document.activeElement)?document.activeElement:null;
    const selecao=foco===consultaIdade.idade?[foco.selectionStart,foco.selectionEnd]:null;
    ids('periodoRelatorios').textContent=d.periodo.texto;
    const relatorio=ids('conteudoRelatorio');
    const metricasRelatorio=d.metricas;
    const tendencias=d.tendencias;
    const gradeKpis=criar('div','grade-kpis');
    const gradeRelatorio=criar('div','grade-relatorio');
    const cartaoAtividade=criar('article','cartao');
    const instrucaoGrafico=matchMedia('(hover: none)').matches
      ?'Toque nas barras para ver cada valor. Deslize para consultar outras datas.'
      :'Passe o cursor sobre as barras para ver cada valor.';

    relatorio.replaceChildren();
    gradeKpis.append(
      kpi('Leads em contato',numero.format(metricasRelatorio.leads||0),tendencias.leads),
      kpi('Mensagens',numero.format(metricasRelatorio.mensagens||0),tendencias.mensagens),
      kpi('Enviados ao funil',numero.format(metricasRelatorio.funil||0),tendencias.funil),
      kpi('Nota média',metricasRelatorio.nota_media==null?'—':Number(metricasRelatorio.nota_media).toLocaleString('pt-BR')+' / 5',tendencias.nota_media),
    );
    cartaoAtividade.append(
      titulo('Evolução da demanda',instrucaoGrafico,'Verde: leads · Lima: mensagens'),
      atividade(d.atividade),
    );
    gradeRelatorio.append(cartaoAtividade,satisfacao(d.satisfacao));
    relatorio.append(
      gradeKpis,
      encaminhamentos(d),
      gradeRelatorio,
      faixaEtariaPersonalizada(),
      perfis(d.perfis),
      dependentesPorTitular(d.dependentes_por_titular),
      etapas(d.etapas),
      exportacao(),
      exportacao('essencial'),
      interpretar(metricasRelatorio),
    );
    if(foco){foco.focus({preventScroll:true});if(selecao)foco.setSelectionRange(...selecao);}
  }
  async function carregarRelatorio(silencioso=false){if(estado.carregandoRelatorio){estado.recarregarRelatorio=true;return;}estado.carregandoRelatorio=true;const periodo=estado.periodo,seq=++estado.sequenciaRelatorio;if(!silencioso)ids('conteudoRelatorio').replaceChildren(criar('div','cartao carregando-relatorio','Preparando os indicadores…'));if(estado.secao==='relatorios')status('Atualizando…','atualizando');try{const d=await json(urlPeriodo(urls.relatorio,periodo));if(seq!==estado.sequenciaRelatorio||periodo!==estado.periodo)return;renderRelatorio(d);if(estado.secao==='relatorios')status('Atualizado agora');}catch(e){if(seq!==estado.sequenciaRelatorio||periodo!==estado.periodo)return;if(estado.secao==='relatorios')status('Falha ao atualizar','erro');if(!silencioso)ids('conteudoRelatorio').replaceChildren(criar('div','cartao carregando-relatorio',e.message));else toast(e.message);}finally{estado.carregandoRelatorio=false;if(estado.recarregarRelatorio){estado.recarregarRelatorio=false;void carregarRelatorio(true);}}}
  function trocar(secao){estado.secao=secao;document.querySelectorAll('[data-secao]').forEach(b=>{const a=b.dataset.secao===secao;b.classList.toggle('ativo',a);b.setAttribute('aria-pressed',String(a));});ids('secaoConversas').hidden=secao!=='conversas';ids('secaoRelatorios').hidden=secao!=='relatorios';window.scrollTo({top:0});secao==='relatorios'?carregarRelatorio():carregarConversas(true);}
  function configurarLegendaFiltros(){
    const grupo=ids('grupoFiltros'),botao=ids('informacaoFiltros'),legenda=ids('legendaFiltros');
    let fixada=false;
    const mostrar=aberta=>{legenda.hidden=!aberta;botao.setAttribute('aria-expanded',String(aberta));};
    botao.addEventListener('pointerenter',evento=>{if(evento.pointerType==='mouse')mostrar(true);});
    botao.addEventListener('focus',()=>mostrar(true));
    botao.addEventListener('click',()=>{fixada=!fixada;mostrar(fixada);});
    grupo.addEventListener('pointerleave',()=>{if(!fixada&&!grupo.contains(document.activeElement))mostrar(false);});
    grupo.addEventListener('focusout',evento=>{if(!fixada&&!grupo.contains(evento.relatedTarget))mostrar(false);});
    document.addEventListener('pointerdown',evento=>{if(!grupo.contains(evento.target)){fixada=false;mostrar(false);}});
    document.addEventListener('keydown',evento=>{if(evento.key==='Escape'){fixada=false;mostrar(false);}});
  }
  configurarLegendaFiltros();
  document.querySelectorAll('[data-secao]').forEach(b=>b.addEventListener('click',()=>trocar(b.dataset.secao)));
  document.querySelectorAll('[data-periodo]').forEach(s=>s.addEventListener('change',()=>{estado.periodo=s.value;invalidarConsultaIdade('Período alterado. Clique em Consultar para obter os números desta janela.');estado.selecionada=null;estado.sequenciaConversas++;estado.sequenciaRelatorio++;document.querySelectorAll('[data-periodo]').forEach(o=>o.value=s.value);estado.secao==='relatorios'?carregarRelatorio():carregarConversas();}));
  document.querySelectorAll('[data-filtro]').forEach(b=>b.addEventListener('click',()=>{estado.filtro=b.dataset.filtro;document.querySelectorAll('[data-filtro]').forEach(x=>x.classList.toggle('ativo',x===b));renderLista();}));
  ids('buscaConversas').addEventListener('input',e=>{estado.busca=e.target.value;renderLista();});
  ids('voltarConversas').addEventListener('click',()=>document.querySelector('.app-conversas').classList.remove('chat-aberto'));
  ids('alternarDetalhes').addEventListener('click',e=>{const a=e.currentTarget.getAttribute('aria-expanded')==='true';e.currentTarget.setAttribute('aria-expanded',String(!a));ids('painelDetalhes').hidden=a;});
  ids('mensagensChat').addEventListener('scroll',()=>{const c=ids('mensagensChat');ids('irFinal').hidden=c.scrollHeight-c.scrollTop-c.clientHeight<150;});
  ids('irFinal').addEventListener('click',()=>ids('mensagensChat').scrollTo({top:ids('mensagensChat').scrollHeight,behavior:'smooth'}));
  document.addEventListener('visibilitychange',()=>{if(!document.hidden)(estado.secao==='conversas'?carregarConversas(true):carregarRelatorio(true));});
  setInterval(()=>{if(!document.hidden&&estado.secao==='conversas')carregarConversas(true);},10000);
  setInterval(()=>{if(!document.hidden&&estado.secao==='relatorios')carregarRelatorio(true);},30000);
  // O espaço do chat acompanha o cabeçalho real, inclusive após girar o celular.
  function ajustarAlturaPainel(){
    const raiz=document.documentElement;
    raiz.style.setProperty('--altura-cabecalho',document.querySelector('.cabecalho-app').offsetHeight+'px');
    raiz.style.setProperty('--altura-aviso',document.querySelector('.faixa-consulta').offsetHeight+'px');
  }
  ajustarAlturaPainel();
  if('ResizeObserver' in window){
    const observador=new ResizeObserver(ajustarAlturaPainel);
    observador.observe(document.querySelector('.cabecalho-app'));
    observador.observe(document.querySelector('.faixa-consulta'));
  }else{
    window.addEventListener('resize',ajustarAlturaPainel);
  }
  carregarConversas();
})();
````

## Passo 16 — Alterar `callback/monitoramento/static/monitoramento/css/painel.css`

Aplicar estilos locais da tag, legenda e tabela responsiva.

Base SHA-256: `2b7b8c55ce766cab3223eb8613537d7b1374b3d0c4d37adec66794d4b28d98f5`. Conteúdo completo proposto: **329 linhas**.

````css
:root{color-scheme:light;--verde-950:#122716;--verde-900:#1c321d;--verde-800:#274a2c;--verde-700:#37663d;--lima:#d9ff6b;--creme:#f5f1ef;--branco:#fff;--texto:#1c2a1d;--muted:#6f796e;--linha:#dde2d8;--painel:#f8f9f5;--erro:#a93636;--sombra:0 16px 45px rgba(20,43,23,.09);font-family:"Segoe UI",-apple-system,BlinkMacSystemFont,Arial,sans-serif;font-synthesis:none}
*{box-sizing:border-box}
[hidden]{display:none!important}
html,body{margin:0;min-height:100%;max-width:100%;background:var(--creme);color:var(--texto)}
body{min-width:300px;overflow-x:clip}
button,input,select{font:inherit}
button,select{cursor:pointer}
button:focus-visible,input:focus-visible,select:focus-visible,a:focus-visible{outline:3px solid #83a84d;outline-offset:2px}
svg{stroke:currentColor;fill:none;stroke-width:1.8;stroke-linecap:round;stroke-linejoin:round}
.skip-link{position:fixed;z-index:50;left:14px;top:-60px;padding:11px 14px;border-radius:8px;background:#fff;color:var(--verde-900)}
.skip-link:focus{top:10px}
.cabecalho-app{height:64px;padding:0 clamp(18px,3vw,44px);display:grid;grid-template-columns:1fr auto 1fr;align-items:center;gap:25px;background:var(--verde-900);color:#fff;position:sticky;top:0;z-index:20;box-shadow:0 4px 16px #10231328}
.marca-app{display:flex;align-items:center;min-width:0}
.marca-app img{width:104px;height:auto;filter:brightness(0) invert(1)}
.marca-app .divisor{height:30px;width:1px;background:#ffffff30;margin:0 18px}
.marca-app div{display:flex;flex-direction:column;min-width:0}
.marca-app strong{font-size:13px;letter-spacing:.06em}
.marca-app div span{font-size:11px;color:#becaba;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.seletor-secao{display:flex;padding:4px;border:1px solid #ffffff15;border-radius:13px;background:#0e211278}
.seletor-secao button{height:40px;padding:0 20px;border:0;border-radius:9px;background:transparent;color:#c7d2c4;display:flex;align-items:center;gap:8px;font-weight:650}
.seletor-secao button svg{width:17px}
.seletor-secao button.ativo{background:#fff;color:var(--verde-900);box-shadow:0 3px 9px #0003}
.acoes-cabecalho{justify-self:end;display:flex;align-items:center;gap:18px}
.estado-atualizacao{font-size:11px;color:#c5d1c2;display:flex;align-items:center;white-space:nowrap}
.estado-atualizacao i{width:7px;height:7px;border-radius:50%;background:var(--lima);box-shadow:0 0 0 4px #d9ff6b17;margin-right:8px}
.estado-atualizacao.atualizando i{animation:pulso 1s infinite}
.estado-atualizacao.erro i{background:#ff908a}
.botao-sair{border:1px solid #ffffff30;border-radius:8px;background:transparent;color:#fff;padding:8px 13px}
.botao-sair:hover{background:#ffffff12}
.faixa-consulta{min-height:32px;padding:5px clamp(18px,3vw,44px);display:flex;align-items:center;justify-content:center;gap:10px;background:#e8f0d0;border-bottom:1px solid #cfdaae;color:#3f522f}
.faixa-consulta svg{width:17px;flex:0 0 17px}
.faixa-consulta p{font-size:11px;margin:0;line-height:1.5}
main{width:100%;max-width:1600px;min-width:0;margin:0 auto}
.secao-painel{min-width:0;padding:12px clamp(16px,3vw,42px) 14px}
#secaoConversas{display:flex;flex-direction:column;height:calc(100dvh - var(--altura-cabecalho,64px) - var(--altura-aviso,32px));min-height:300px}
.barra-contexto{display:flex;align-items:flex-end;justify-content:space-between;gap:16px;margin-bottom:10px;flex-shrink:0}
.sobrelinha{font-size:9px;font-weight:800;letter-spacing:.18em;color:var(--verde-700);margin:0 0 6px}
.barra-contexto h1{font-size:28px;line-height:1.1;letter-spacing:-.04em;margin:0 0 5px}
.barra-contexto>div>p:last-child{font-size:12px;color:var(--muted);margin:0}
.seletor-periodo{display:flex;flex-direction:column;gap:5px;color:var(--muted);font-size:9px;font-weight:700;letter-spacing:.08em;text-transform:uppercase}
.seletor-periodo select{min-width:190px;height:42px;padding:0 34px 0 12px;border:1px solid var(--linha);border-radius:9px;color:var(--texto);background:#fff}
.app-conversas{flex:1;min-height:200px;display:grid;grid-template-columns:minmax(310px,370px) 1fr;overflow:hidden;border:1px solid #d5dbd1;border-radius:17px;background:#fff;box-shadow:var(--sombra)}
.lista-conversas{min-width:0;min-height:0;display:flex;flex-direction:column;border-right:1px solid var(--linha);background:#fff}
.busca{position:relative;padding:8px 12px 4px}
.busca svg{position:absolute;width:17px;left:25px;top:21px;color:#7a8677}
.busca input{width:100%;height:42px;border:1px solid var(--linha);border-radius:9px;background:var(--painel);padding:0 12px 0 39px;color:var(--texto);outline:0}
.busca input:focus{border-color:var(--verde-700);background:#fff}
.filtros-conversas{display:flex;gap:6px;padding:2px 12px 6px;overflow-x:auto;scrollbar-width:none}
.filtros-conversas button{white-space:nowrap;padding:7px 11px;border:1px solid var(--linha);border-radius:999px;background:#fff;color:#667064;font-size:11px}
.filtros-conversas button.ativo{border-color:var(--verde-700);background:var(--verde-800);color:#fff}
.rolagem-lista{flex:1;min-height:0;overflow:auto;overscroll-behavior:contain}
.item-conversa{width:100%;padding:7px 12px;border:0;border-top:1px solid #edf0e9;background:#fff;display:grid;grid-template-columns:40px minmax(0,1fr);gap:10px;align-items:center;text-align:left;color:inherit}
.item-conversa:hover,.item-conversa.ativo{background:#f0f4e9}
.item-conversa.ativo{box-shadow:inset 3px 0 var(--verde-700)}
.avatar{width:45px;height:45px;border-radius:50%;background:var(--verde-700);color:#fff;display:grid;place-items:center;font-weight:750}
.item-conversa .avatar{width:40px;height:40px}
.item-corpo{min-width:0}
.item-linha{display:flex;justify-content:space-between;gap:7px;align-items:flex-start}
.item-linha strong{min-width:0;flex:1;font-size:13px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.item-linha time{font-size:9px;color:#8a9487;white-space:nowrap}
.item-metadados{min-width:0;display:flex;align-items:center;justify-content:flex-end;gap:5px;flex:0 0 auto}
.perfis-resumidos-item{max-width:100px;display:flex;flex-wrap:wrap;justify-content:flex-end;gap:2px}
.mini-tag.perfil-resumido{padding:2px 5px;font-size:7px;white-space:nowrap;background:#edf2e8;color:#40573e}
.mini-tag.perfil-resumido.dependente-menor,.mini-tag.perfil-resumido.menor{background:#e1edff;color:#315f98}
.mini-tag.perfil-resumido.dependente-adulto{background:#ddf1e4;color:#296b42}
.mini-tag.perfil-resumido.dependente-idoso,.mini-tag.perfil-resumido.idoso{background:#e9e1ff;color:#614299}
.item-previa{margin:3px 0 0;font-size:11px;color:#748071;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.mini-tags:not(:empty){margin-top:4px}
.mini-tags,.tags-contato{display:flex;flex-wrap:wrap;gap:4px}
.mini-tag,.tag-contato{display:inline-flex;align-items:center;border-radius:999px;background:#edf2e8;color:#50614b;padding:2px 6px;font-size:8px;font-weight:700;text-transform:uppercase;letter-spacing:.04em}
.mini-tag.funil,.tag-contato.funil{background:#dff4e3;color:#267242}
.mini-tag.nota{background:#fff2cb;color:#8b6813}
.tag-contato.idoso{background:#e9e1ff;color:#614299}
.tag-contato.menor{background:#e1edff;color:#315f98}
.estado-vazio{padding:42px 18px;text-align:center;color:var(--muted);font-size:12px}
.carregando::before{content:"";display:block;width:24px;height:24px;margin:0 auto 13px;border:2px solid #d8dfd2;border-top-color:var(--verde-700);border-radius:50%;animation:girar .8s linear infinite}
.janela-chat{min-width:0;min-height:0;position:relative;display:flex;flex-direction:column;background:#eef0e8;overflow:hidden}
.topo-chat{min-height:60px;padding:6px 12px;display:flex;align-items:center;gap:12px;background:#fff;border-bottom:1px solid var(--linha);z-index:2}
.voltar{display:none;border:0;background:transparent;font-size:28px;color:var(--verde-800)}
.identidade-contato{min-width:0;flex:1}
.identidade-contato h2{font-size:14px;margin:0 0 2px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.identidade-contato p{font-size:10px;color:var(--muted);margin:0 0 4px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.detalhes-botao{border:1px solid var(--linha);border-radius:8px;padding:7px 10px;background:#fff;color:#5c685b;font-size:10px}
.detalhes-botao[aria-expanded=true]{background:var(--verde-800);color:#fff}
.painel-detalhes{flex:0 1 auto;max-height:40%;overflow:auto;padding:10px 18px;background:#fbfcf9;border-bottom:1px solid var(--linha);font-size:11px;color:#606b5e;z-index:2}
.painel-detalhes dl{margin:0;display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px}
.painel-detalhes dt{font-size:8px;text-transform:uppercase;letter-spacing:.08em;color:#8a9388}
.painel-detalhes dd{margin:2px 0 0;overflow-wrap:anywhere}
.topo-chat,.rodape-chat{flex-shrink:0}
.mensagens{flex:1;min-height:0;overflow-y:auto;position:relative;padding:22px clamp(18px,5vw,70px);background-color:#eef0e8;background-image:radial-gradient(#63755a12 1px,transparent 1px);background-size:18px 18px;overscroll-behavior:contain}
.marca-dagua{position:fixed;pointer-events:none;opacity:.035;width:260px;left:calc(50% + 135px);top:50%;transform:translate(-50%,-50%) rotate(-8deg)}
.marca-dagua img{width:100%;filter:grayscale(1)}
.boas-vindas{position:relative;z-index:1;max-width:410px;margin:14vh auto 0;padding:25px;border:1px solid #d7ddd1;border-radius:15px;background:#ffffffd9;text-align:center;box-shadow:0 8px 25px #25331d0b}
.boas-vindas span{font-size:9px;font-weight:800;letter-spacing:.14em;color:var(--verde-700)}
.boas-vindas h2{font-size:20px;margin:7px 0}
.boas-vindas p{font-size:12px;color:var(--muted);margin:0}
.dia,.separador-conversa{position:relative;z-index:1;width:max-content;max-width:90%;margin:8px auto 14px;padding:5px 10px;border:1px solid #d6ddcd;border-radius:8px;background:#f9fbf5;color:#6c7868;font-size:9px;box-shadow:0 1px 2px #0000000d}
.separador-conversa{margin-top:18px;background:#e3edd8;color:#4d6446}
.linha-mensagem{position:relative;z-index:1;display:flex;margin:3px 0}
.linha-mensagem.bot{justify-content:flex-end}
.bolha{max-width:min(76%,720px);padding:8px 10px 6px;border-radius:4px 11px 11px 11px;background:#fff;box-shadow:0 1px 2px #23301f1c}
.linha-mensagem.bot .bolha{border-radius:11px 4px 11px 11px;background:#dff1cf}
.tipo-mensagem{display:block;width:max-content;margin-bottom:4px;padding:2px 5px;border-radius:4px;background:#213b2520;color:#496346;font-size:8px;font-weight:700;text-transform:uppercase}
.texto-mensagem{white-space:pre-wrap;overflow-wrap:anywhere;font-size:13px;line-height:1.45}
.botoes-mensagem{display:grid;gap:4px;margin:8px -4px -1px}
.botao-mensagem:disabled{cursor:default;opacity:1}
.botao-mensagem{min-height:31px;border:0;border-top:1px solid #bed2b3;background:transparent;color:#39704a;font-size:11px;text-align:center}
.meta-mensagem{display:flex;justify-content:flex-end;align-items:center;gap:4px;margin-top:3px;color:#73806f;font-size:8px}
.ticks{color:#4e8eb1;font-size:10px}
.rodape-chat{padding:4px 12px;text-align:center;background:#fff;border-top:1px solid var(--linha);color:#8a9388;font-size:8px}
.ir-final{position:absolute;right:20px;bottom:42px;z-index:4;width:39px;height:39px;border:1px solid var(--linha);border-radius:50%;background:#fff;color:var(--verde-800);box-shadow:0 5px 17px #1c321d30}
.secao-relatorios{padding-bottom:60px}
.conteudo-relatorio{min-width:0;display:grid;gap:10px}
.conteudo-relatorio>*{min-width:0;max-width:100%}
.formulario-faixa{display:grid;grid-template-columns:minmax(130px,220px) minmax(170px,260px) auto;align-items:end;justify-content:start;gap:14px;margin:18px 0}
.campo-faixa{display:flex;flex-direction:column;gap:7px;font-size:12px;font-weight:600;min-width:0}
.campo-faixa input,.campo-faixa select{width:100%;min-height:44px;padding:10px 12px;border:1px solid var(--linha);border-radius:9px;background:var(--painel);color:var(--texto)}
.campo-faixa input[aria-invalid=true]{border-color:var(--erro)}
.botao-consultar{min-height:44px;padding:10px 23px;border:1px solid var(--verde-800);border-radius:9px;background:var(--verde-800);color:#fff;font-size:12px;font-weight:650}
.botao-consultar:hover{background:var(--verde-900)}
.botao-consultar:disabled{opacity:.65;cursor:wait}
.resultado-faixa{padding:16px 18px;border:1px solid #dbe6d5;border-left:3px solid #779c45;border-radius:10px;background:#f3f7ed;overflow-wrap:anywhere}
.resultado-faixa p{margin:0;font-size:13px;line-height:1.65}
.tabela-resultado-faixa{width:100%;max-width:720px;border-collapse:collapse;table-layout:fixed;font-size:13px}
.tabela-resultado-faixa caption{text-align:left;padding-bottom:14px;font-size:14px;font-weight:650;color:var(--verde-900)}
.tabela-resultado-faixa th,.tabela-resultado-faixa td{padding:10px 8px;text-align:right;vertical-align:middle;font-variant-numeric:tabular-nums}
.tabela-resultado-faixa th:first-child{width:40%;padding-left:0;text-align:left}
.tabela-resultado-faixa th:nth-child(2){width:20%}
.tabela-resultado-faixa thead th{font-size:11px;font-weight:600;color:var(--muted);border-bottom:1px solid #dbe6d5}
.tabela-resultado-faixa tbody th{font-weight:500}
.tabela-resultado-faixa tbody tr+tr{border-top:1px solid #e3eadc}
.tabela-resultado-faixa td{font-weight:650;color:var(--verde-800)}
.tabela-resultado-faixa tfoot{border-top:2px solid #cbdcbc;color:var(--verde-900)}
.tabela-resultado-faixa tfoot th,.tabela-resultado-faixa tfoot td{font-weight:700}
.resultado-faixa .detalhe-faixa{margin-top:8px;font-size:11px;color:var(--muted)}
.resultado-faixa.vazio{background:var(--painel);border-color:var(--linha);color:var(--muted)}
.resultado-faixa.erro{color:var(--erro);border-color:#e4c7c7;background:#fff6f6}
.nota-faixa{font-size:11px;line-height:1.6;color:var(--muted);margin:12px 0 0}
.grupos-dependentes{list-style:none;padding:0;margin:16px 0;display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:10px}
.grupo-dependentes{display:flex;flex-direction:column;gap:6px;padding:16px;border:1px solid var(--linha);border-radius:10px;background:var(--painel)}
.grupo-dependentes strong{font-size:19px;color:var(--verde-800)}
.grupo-dependentes span{font-size:12px;color:var(--muted)}
@media(max-width:600px){.formulario-faixa{grid-template-columns:1fr;justify-content:stretch;gap:12px}.botao-consultar{width:100%}.resultado-faixa{padding:14px}.grupos-dependentes{grid-template-columns:1fr 1fr}.grupo-dependentes{padding:12px}}
@media(max-width:400px){.tabela-resultado-faixa{font-size:12px}.tabela-resultado-faixa th,.tabela-resultado-faixa td{padding:10px 4px}}
.cartao{min-width:0;max-width:100%;border:1px solid var(--linha);border-radius:14px;background:#fff;padding:14px;box-shadow:0 5px 20px #1c321d08}
.carregando-relatorio{text-align:center;color:var(--muted);padding:60px}
.grade-kpis{min-width:0;display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px}
.kpi{min-height:98px;position:relative;overflow:hidden}
.kpi::after{content:"";position:absolute;right:-28px;bottom:-40px;width:90px;height:90px;border-radius:50%;background:#d9ff6b38}
.kpi .rotulo{font-size:9px;text-transform:uppercase;letter-spacing:.12em;color:var(--muted)}
.kpi strong{display:block;margin:4px 0;font-size:30px;color:var(--verde-900);letter-spacing:-.05em}
.tendencia{font-size:10px;color:#687266}
.tendencia.positiva{color:#2c7b45}
.tendencia.negativa{color:#ae4444}
.grade-relatorio{min-width:0;display:grid;grid-template-columns:minmax(0,1.3fr) minmax(0,.7fr);gap:10px}
.titulo-cartao{display:flex;justify-content:space-between;align-items:flex-start;gap:12px;margin-bottom:10px}
.titulo-cartao h2{font-size:16px;margin:0 0 4px}
.titulo-cartao p{font-size:10px;color:var(--muted);margin:0;line-height:1.5}
.legenda{font-size:9px;color:var(--muted);white-space:nowrap}
.grafico-atividade{width:100%;max-width:100%;min-width:0}
.grafico-resumo{display:none;min-height:28px;margin:0 0 8px;padding:7px 9px;border-radius:7px;background:#f0f4e9;color:#536050;font-size:9px}
.grafico-rolagem{width:100%;max-width:100%;min-width:0;overflow-x:auto;overscroll-behavior-x:contain;scrollbar-width:thin}
.grafico-barras{height:200px;width:max-content;min-width:100%;display:flex;align-items:flex-end;gap:5px;padding:18px 4px 30px;border-bottom:1px solid var(--linha)}
.coluna-grafico{appearance:none;height:100%;min-width:19px;flex:1 0 19px;display:flex;align-items:flex-end;justify-content:center;gap:2px;position:relative;padding:0;border:0;background:transparent;color:inherit}
.coluna-grafico i{display:block;width:7px;min-height:2px;border-radius:3px 3px 0 0;background:var(--verde-700)}
.coluna-grafico i.barra-mensagens{position:static;padding:0;background:#c6e662}
.coluna-grafico .rotulo-data{position:absolute;top:calc(100% + 8px);left:50%;transform:translateX(-50%) rotate(-35deg);font-size:7px;color:#7d8879;white-space:nowrap}
.barras-satisfacao{display:grid;gap:10px}
.barra-linha{display:grid;grid-template-columns:35px 1fr 30px;align-items:center;gap:8px;font-size:10px}
.trilho{height:8px;border-radius:999px;background:#edf0e9;overflow:hidden}
.trilho i{display:block;height:100%;border-radius:inherit;background:linear-gradient(90deg,var(--verde-700),#96bd50)}
.tabela-perfis{width:100%;border-collapse:collapse;font-size:11px}
.tabela-perfis th{text-align:left;padding:9px 8px;color:var(--muted);font-size:8px;text-transform:uppercase;letter-spacing:.08em;border-bottom:1px solid var(--linha)}
.tabela-perfis td{padding:8px;border-bottom:1px solid #edf0e9}
.tabela-perfis td:not(:first-child),.tabela-perfis th:not(:first-child){text-align:right}
.etapas-lista{display:grid;gap:8px}
.etapa-linha{display:grid;grid-template-columns:25px minmax(160px,1fr) 2fr 30px;gap:8px;align-items:center;font-size:9px}
.etapa-numero{width:22px;height:22px;border-radius:6px;background:#edf2e8;display:grid;place-items:center;font-weight:700;color:var(--verde-700)}
.etapa-nome{white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.exportacao{display:flex;align-items:center;justify-content:space-between;gap:20px;background:var(--verde-900);color:#fff}
.exportacao h2{margin:0 0 5px;font-size:17px}
.exportacao p{margin:0;color:#c2cec0;font-size:10px;max-width:690px}
.botoes-download{display:flex;gap:8px;flex-wrap:wrap;justify-content:flex-end}
.botao-download{display:inline-flex;min-height:44px;align-items:center;padding:0 13px;border:1px solid #ffffff30;border-radius:8px;color:#fff;text-decoration:none;font-size:10px}
.botao-download.primario{background:var(--lima);border-color:var(--lima);color:var(--verde-950);font-weight:700}
.como-interpretar{background:#f0f4e9}
.como-interpretar h2{font-size:15px;margin:0 0 8px}
.como-interpretar ul{margin:0;padding-left:18px;color:#5f6b5c;font-size:10px;line-height:1.7}
.toast{position:fixed;z-index:100;left:50%;bottom:20px;transform:translateX(-50%);max-width:min(90vw,430px);padding:11px 15px;border-radius:9px;background:#202b21;color:#fff;box-shadow:0 8px 30px #0004;font-size:11px}
@keyframes girar{to{transform:rotate(360deg)}
}
@keyframes pulso{50%{opacity:.35}
}
@media(max-width:1000px){.cabecalho-app{grid-template-columns:minmax(0,1fr) auto auto;gap:12px;padding-inline:clamp(16px,2.5vw,28px)}
.seletor-secao{grid-row:1;grid-column:2;justify-self:center;margin:0;transform:none;z-index:auto}
.seletor-secao button{height:38px;padding:0 14px}
.acoes-cabecalho{grid-row:1;grid-column:3}
.faixa-consulta{margin-top:0}
.acoes-cabecalho .estado-atualizacao{display:none}
.app-conversas{grid-template-columns:minmax(270px,330px) minmax(0,1fr)}
.grade-relatorio{grid-template-columns:1fr}
.grade-kpis{grid-template-columns:repeat(2,minmax(0,1fr))}
.filtros-conversas{gap:4px;padding-inline:10px}
.filtros-conversas button{padding:6px 8px;font-size:10px}
.marca-dagua{position:absolute;left:50%}
}
@media(max-width:720px){.cabecalho-app{height:auto;min-height:50px;padding:0 16px 6px;grid-template-columns:minmax(0,1fr) auto;grid-template-rows:50px auto;gap:0 10px}
.marca-app img{width:82px}
.marca-app .divisor{height:25px;margin:0 10px}
.marca-app strong{font-size:11px}
.marca-app div span{max-width:125px;font-size:9px}
.botao-sair{padding:7px 10px;font-size:10px}
.seletor-secao{grid-row:2;grid-column:1/-1;width:100%;margin:0;transform:none}
.seletor-secao button{flex:1;justify-content:center;height:38px;padding:0 10px;font-size:11px}
.acoes-cabecalho{grid-row:1;grid-column:2}
.faixa-consulta{margin-top:0;padding:5px 16px;align-items:flex-start}
.faixa-consulta p{font-size:9px}
.secao-painel{padding:10px 0 0}
.barra-contexto{padding:0 16px;align-items:flex-end}
.barra-contexto h1{font-size:24px}
.barra-contexto>div>p:last-child{font-size:10px}
.seletor-periodo select{min-width:150px;width:150px;height:39px;font-size:10px}
.app-conversas{border-radius:0;border-left:0;border-right:0;display:block}
.lista-conversas{height:100%;border:0}
.janela-chat{display:none;height:100%}
.chat-aberto .lista-conversas{display:none}
.chat-aberto .janela-chat{display:flex}
.voltar{display:block}
.topo-chat{padding-left:8px}
.detalhes-botao{font-size:0;padding:7px}
.detalhes-botao::before{content:"i";font-size:12px;font-family:Georgia,serif}
.painel-detalhes dl{grid-template-columns:repeat(2,minmax(0,1fr))}
.mensagens{padding:16px 10px}
.marca-dagua{position:absolute;left:50%;width:210px}
.bolha{max-width:88%}
.secao-relatorios{padding:10px 13px 24px}
.secao-relatorios .barra-contexto{padding:0 3px}
.grade-kpis{grid-template-columns:repeat(2,minmax(0,1fr))}
.kpi{min-height:98px;padding:12px}
.kpi strong{font-size:25px}
.cartao{padding:12px}
.grade-relatorio{display:block}
.grade-relatorio>.cartao+ .cartao{margin-top:10px}
.tabela-perfis{font-size:9px}
.tabela-perfis th,.tabela-perfis td{padding:9px 4px}
.etapa-linha{grid-template-columns:24px minmax(105px,1.2fr) 1fr 25px}
.exportacao{display:block}
.botoes-download{justify-content:flex-start;margin-top:10px}
.botao-download{flex:1;justify-content:center}
.estado-vazio{padding:30px 15px}
.grafico-resumo{display:block}
}
@media(max-width:560px){.barra-contexto{flex-direction:column;align-items:stretch;gap:8px}
.seletor-periodo{width:100%;margin-top:0}
.seletor-periodo select{width:100%;min-width:0}
.tabela-perfis,.tabela-perfis tbody,.tabela-perfis tr,.tabela-perfis td{display:block;width:100%}
.tabela-perfis thead{display:none}
.tabela-perfis tbody{display:grid;gap:9px}
.tabela-perfis tr{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:7px 12px;padding:10px;border:1px solid #e5e9e1;border-radius:10px;background:#fbfcf9}
.tabela-perfis td,.tabela-perfis td:not(:first-child){padding:0;border:0;text-align:left;font-size:11px}
.tabela-perfis td:first-child{grid-column:1/-1;padding-bottom:3px;font-weight:650;overflow-wrap:anywhere}
.tabela-perfis td:not(:first-child)::before{content:attr(data-rotulo);display:block;margin-bottom:2px;color:var(--muted);font-size:7px;font-weight:700;letter-spacing:.07em;text-transform:uppercase}
.etapa-linha{grid-template-columns:25px minmax(0,1fr) 28px;grid-template-rows:auto 7px;gap:5px 8px;font-size:10px}
.etapa-numero{grid-column:1;grid-row:1/3;align-self:center}
.etapa-nome{grid-column:2;grid-row:1;white-space:normal;overflow:visible;line-height:1.3}
.etapa-linha .trilho{grid-column:2;grid-row:2}
.etapa-linha>strong{grid-column:3;grid-row:1/3;align-self:center;text-align:right}
}
@media(max-width:390px){
.grade-kpis{grid-template-columns:1fr 1fr}
.titulo-cartao{display:block}
.legenda{display:block;margin-top:7px}
.exportacao .botao-download{flex-basis:100%}
}
@media(hover:none){.grafico-resumo{display:block}
}
@media(orientation:landscape) and (max-height:600px) and (max-width:1000px){.cabecalho-app{height:56px;min-height:56px;padding:0 12px;grid-template-columns:minmax(0,1fr) auto auto;grid-template-rows:56px;gap:8px}
.marca-app img{width:70px}
.marca-app .divisor{height:24px;margin:0 9px}
.marca-app strong{font-size:10px}
.marca-app div span{max-width:145px;font-size:8px}
.seletor-secao{grid-row:1;grid-column:2;width:auto;padding:3px;border-radius:10px}
.seletor-secao button{height:34px;padding:0 9px;gap:6px;font-size:10px}
.seletor-secao button svg{width:14px}
.acoes-cabecalho{grid-row:1;grid-column:3}
.botao-sair{padding:6px 9px;font-size:10px}
.faixa-consulta{min-height:32px;padding:5px 12px}
.faixa-consulta p{display:-webkit-box;overflow:hidden;-webkit-box-orient:vertical;-webkit-line-clamp:2;font-size:8px;line-height:1.3}
.secao-painel{padding-top:8px}
.barra-contexto{flex-direction:row;align-items:flex-end;gap:12px}
.seletor-periodo{width:auto;margin:0}
.seletor-periodo select{width:min(190px,32vw);min-width:140px;height:36px}
}
@media(orientation:landscape) and (max-height:440px) and (max-width:560px){.marca-app div span{display:none}
}
@media(pointer:coarse){.seletor-secao button,.botao-sair,.detalhes-botao,.voltar,.filtros-conversas button,.seletor-periodo select,.busca input{min-height:44px}
.detalhes-botao,.voltar,.ir-final{min-width:44px;min-height:44px}
}
@media(prefers-reduced-motion:reduce){*{animation:none!important;scroll-behavior:auto!important}
}

.indicador-comercial{display:flex;flex-wrap:wrap;align-items:center;justify-content:space-between;gap:10px 20px}
.indicador-comercial>div{flex:1 1 230px;min-width:0;overflow-wrap:anywhere}
.indicador-comercial h2{margin:0 0 5px;font-size:16px}
.indicador-comercial p{margin:0;color:var(--muted);font-size:12px;line-height:1.5}
.indicador-comercial .politica-suporte{margin-top:4px}
.total-comercial{font-size:28px;line-height:1.2;overflow-wrap:anywhere;max-width:100%;color:var(--verde-800)}


/* Encerramentos por idade: estilos locais, sem alterar tabelas ou selos de perfil. */
.mini-tag.comercial,.tag-contato.comercial{background:#fff0cf;color:#71501b}
.grupo-filtros{position:relative;display:flex;align-items:center;gap:4px;padding-right:8px;flex-shrink:0}
.grupo-filtros .filtros-conversas{flex:1;min-width:0}
.informacao-filtros{flex:0 0 28px;width:28px;height:28px;border:1px solid #dce3d7;border-radius:50%;background:#fff;color:#395a36;font-weight:700;cursor:pointer}
.informacao-filtros:focus-visible{outline:2px solid #395a36;outline-offset:2px}
.legenda-filtros{position:absolute;z-index:20;left:10px;right:10px;top:100%;max-height:min(400px,50dvh);overflow:auto;padding:16px;background:#fff;border:1px solid #dce3d7;border-radius:12px;box-shadow:0 8px 24px #142b1526;font-size:12px;line-height:1.5}
.legenda-filtros dl{margin:10px 0 0}.legenda-filtros dt{font-weight:700;color:#2b4930}.legenda-filtros dd{margin:0 0 8px;color:#586557}
.resumo-encerramentos{display:flex;gap:28px;flex-wrap:wrap;margin:12px 0 16px}
.resumo-encerramentos p{display:flex;align-items:baseline;gap:8px;margin:0;color:#56644f;font-size:13px}
.resumo-encerramentos strong{font-size:25px;color:#284a2e}
.tabela-encerramentos{width:100%;border-collapse:collapse;table-layout:fixed;font-size:13px}
.tabela-encerramentos caption.sr-only{position:absolute;width:1px;height:1px;padding:0;margin:-1px;overflow:hidden;clip:rect(0,0,0,0);white-space:nowrap;border:0}
.tabela-encerramentos th,.tabela-encerramentos td{padding:12px 10px;border-bottom:1px solid #e9eee5;text-align:left;overflow-wrap:anywhere}
.tabela-encerramentos thead th{color:#63705d;font-size:11px;text-transform:uppercase;letter-spacing:.05em}
.tabela-encerramentos th:first-child{width:46%}.tabela-encerramentos th:last-child{width:16%}
.tabela-encerramentos tbody th{font-weight:500}.tabela-encerramentos .quantidade,.tabela-encerramentos thead th:last-child{text-align:right;font-weight:700}
.tabela-encerramentos .quantidade{color:#2b5932;font-variant-numeric:tabular-nums}
@media(max-width:600px){.tabela-encerramentos{font-size:12px}.tabela-encerramentos th,.tabela-encerramentos td{padding:10px 4px}.tabela-encerramentos th:first-child{width:42%}.tabela-encerramentos thead th:last-child{width:72px;white-space:nowrap;font-size:10px;letter-spacing:0}.resumo-encerramentos{gap:8px}.resumo-encerramentos p{width:100%}}
@media(pointer:coarse){.informacao-filtros{flex-basis:44px;width:44px;height:44px}}
````

## Passo 17 — Alterar `tests/fixtures/monitoramento_painel.py`

Preparar dados inteiramente fictícios do filtro Comercial e dos motivos no relatório.

Base SHA-256: `30e7e7efc9bb82836f0ef3efd3c67354b481120678d8b6be19a42f2a1436d489`. Conteúdo completo proposto: **116 linhas**.

````python
"""Dados inteiramente fictícios usados pelos testes e pela revisão visual local."""


CONVERSAS = {
    'unidade': {'nome': 'Supera Santo Antônio de Jesus', 'agente': 'Suh', 'regras': {
        'idade_minima_suporte': 60, 'email_obrigatorio': True, 'bpa_ativo': True,
    }},
    'periodo': {'chave': 'total', 'rotulo': 'Todo o histórico',
                'inicio': '2026-07-29T23:55:00-03:00', 'fim': '2026-09-03T12:00:00-03:00',
                'texto': '29/07/2026 23:55 até agora'},
    'metricas': {'leads': 119, 'mensagens': 1864, 'funil': 31, 'avaliacoes': 17, 'nota_media': 4.53},
    'conversas': [
        {'id_cliente': 140, 'nome': 'Edcarlos', 'contato': '557194111866',
         'email': 'edcarlos@example.com', 'profissao': 'Empresário', 'ids_conversa': [157, 159],
         'perfis': ['adulto'], 'perfis_resumidos': ['adulto'],
         'dependentes': [], 'foi_funil': True, 'avaliada': True,
         'ultima_atividade': '2026-09-03T14:43:35Z', 'ultima_mensagem_id': 4,
         'ultima_mensagem': 'Podemos começar? ☺️'},
        {'id_cliente': 141, 'nome': 'Maria Souza', 'contato': '557599111222',
         'email': 'maria@example.com', 'profissao': 'Professora', 'ids_conversa': [158],
         'perfis': ['dependente', 'menor'], 'perfis_resumidos': ['dependente_menor'],
         'dependentes': ['Lucas'], 'foi_funil': True, 'avaliada': False,
         'ultima_atividade': '2026-09-03T13:31:17Z', 'ultima_mensagem_id': 141,
         'ultima_mensagem': 'Quero agendar'},
        {'id_cliente': 142, 'nome': 'Ariana', 'contato': '557791238060',
         'email': '', 'profissao': 'Aposentada', 'ids_conversa': [150], 'perfis': ['idoso'],
         'perfis_resumidos': ['idoso'],
         'dependentes': [], 'foi_funil': False, 'avaliada': True,
         'ultima_atividade': '2026-09-02T14:55:35Z', 'ultima_mensagem_id': 142,
         'ultima_mensagem': 'Obrigada pelo atendimento'},
        {'id_cliente': 143, 'nome': 'Joana Lima', 'contato': '557588000111',
         'email': 'joana@example.com', 'profissao': 'Autônoma', 'ids_conversa': [149],
         'perfis': ['dependente', 'adulto'], 'perfis_resumidos': ['dependente_adulto'],
         'dependentes': ['Beatriz'], 'foi_funil': False, 'avaliada': False,
         'ultima_atividade': '2026-09-01T11:41:00Z', 'ultima_mensagem_id': 143,
         'ultima_mensagem': 'Às vezes'},
    ],
    'atualizado_em': '2026-09-03T15:00:00Z',
}

MENSAGENS = {
    140: {'id_cliente': 140, 'mensagens': [
        {'id_mensagem': 1, 'id_conversa': 157, 'id_etapa': 1, 'data': '2026-09-03T14:40:00Z', 'quem_enviou': 'cliente', 'tipo': 'text', 'texto': 'Olá', 'botoes': []},
        {'id_mensagem': 2, 'id_conversa': 157, 'id_etapa': 2, 'data': '2026-09-03T14:40:04Z', 'quem_enviou': 'bot', 'tipo': 'interactive_button', 'texto': 'Esse atendimento é para você ou para um dependente?', 'botoes': ['Para mim', 'Para um dependente']},
        {'id_mensagem': 3, 'id_conversa': 157, 'id_etapa': 2, 'data': '2026-09-03T14:40:20Z', 'quem_enviou': 'cliente', 'tipo': 'interactive', 'texto': 'Para mim', 'botoes': []},
        {'id_mensagem': 4, 'id_conversa': 159, 'id_etapa': 11, 'data': '2026-09-03T14:43:35Z', 'quem_enviou': 'bot', 'tipo': 'interactive_button', 'texto': 'Vou fazer uma triagem rápida. Podemos começar? ☺️', 'botoes': ['Começar triagem']},
    ]},
}
for _id in (141, 142, 143):
    MENSAGENS[_id] = {'id_cliente': _id, 'mensagens': [
        {'id_mensagem': _id, 'id_conversa': _id + 17, 'id_etapa': 7,
         'data': '2026-09-03T13:31:17Z', 'quem_enviou': 'cliente',
         'tipo': 'text', 'texto': 'Mensagem fictícia de revisão visual', 'botoes': []},
    ]}

NOMES_ETAPAS = [
    'Saudação e nome do cliente', 'Destino do atendimento', 'Confirmação do destino',
    'Profissão do cliente', 'Nome do dependente', 'Idade do aluno', 'Oferta de aula',
    'Oferta adiada', 'Retorno ao atendimento', 'E-mail', 'Introdução à triagem',
    'Triagem · pergunta 1', 'Triagem · pergunta 2', 'Triagem · pergunta 3',
    'Triagem · pergunta 4', 'Triagem · pergunta 5', 'Triagem · pergunta 6',
    'Agendamento', 'Pesquisa · nota', 'Opção de comentário', 'Comentário', 'Finalização',
]
RELATORIO = {
    'dependentes_por_titular': {
        'titulares': 40, 'dependentes': 41,
        'grupos': [{'dependentes_por_titular': 1, 'titulares': 39},
                   {'dependentes_por_titular': 2, 'titulares': 1}],
    },
    'unidade': {'nome': 'Supera Santo Antônio de Jesus', 'idade_minima_suporte': 60},
    'periodo': CONVERSAS['periodo'], 'metricas': CONVERSAS['metricas'],
    'tendencias': {'leads': 12.4, 'mensagens': 8.1, 'funil': -3.2, 'avaliacoes': 5.0, 'nota_media': 2.1},
    'atividade': [
        {'periodo': f'2026-08-{dia:02d}T12:00:00-03:00', 'leads': 7 + dia % 5, 'mensagens': 80 + dia * 3}
        for dia in range(24, 31)
    ],
    'satisfacao': {'1': 0, '2': 0, '3': 1, '4': 6, '5': 10},
    'perfis': {'idade_minima_dependente': 4, 'sem_classificacao': 12, 'linhas': [
        {'rotulo': 'Dependentes de 4 a 17 anos', 'leads': 37, 'conversas': 37, 'funil': 24, 'taxa_funil': 64.9},
        {'rotulo': 'Dependentes de 18 a 59 anos', 'leads': 3, 'conversas': 3, 'funil': 1, 'taxa_funil': 33.3},
        {'rotulo': 'Dependentes com 60 anos ou mais', 'leads': 2, 'conversas': 2, 'funil': 0, 'taxa_funil': 0},
        {'rotulo': 'Titulares de 18 a 59 anos', 'leads': 54, 'conversas': 56, 'funil': 6, 'taxa_funil': 11.1},
        {'rotulo': 'Titulares com 60 anos ou mais', 'leads': 11, 'conversas': 11, 'funil': 0, 'taxa_funil': 0},
    ]},
    'etapas': [{'id_etapa': i + 1, 'nome_etapa': nome, 'quantidade': (i * 7) % 19} for i, nome in enumerate(NOMES_ETAPAS)],
    'atualizado_em': '2026-09-03T15:00:00Z',
}

CONTATOS = [
    {'id_cliente': 140, 'nome': 'Edcarlos Silva', 'email': 'edcarlos@example.com', 'waid_telefone': '557194111866'},
    {'id_cliente': 141, 'nome': None, 'email': None, 'waid_telefone': '557599111222'},
]


# Casos fictícios explícitos para revisão do novo filtro e da tabela.
CONVERSAS['conversas'][2]['comercial'] = {
    'id_conversa': 150, 'motivo': 'suporte_idoso_60', 'tag': '60+',
    'descricao': 'Titular encaminhado por suporte 60+', 'contato_enviado': True,
    'participante': 'Titular', 'resposta_idade': 'Tenho 65 anos', 'nome_dependente': None,
}
RELATORIO['encerramentos_por_idade'] = {
    'idade_minima_suporte': 60, 'idade_minima_dependente': 4,
    'total_encaminhadas': 15, 'total_sem_encaminhamento': 5,
    'linhas': [
        {'motivo': 'suporte_idoso_60', 'rotulo': 'Titulares · suporte 60+ (até 89 anos)',
         'contato_enviado': True, 'destino': 'Contato comercial enviado', 'conversas': 10},
        {'motivo': 'idade_universal_90', 'rotulo': 'Titulares · 90+ (regra universal)',
         'contato_enviado': True, 'destino': 'Contato comercial enviado', 'conversas': 3},
        {'motivo': 'idade_universal_90', 'rotulo': 'Dependentes · 90+ (regra universal)',
         'contato_enviado': True, 'destino': 'Contato comercial enviado', 'conversas': 2},
        {'motivo': 'titular_menor_18', 'rotulo': 'Titulares · menos de 18 anos',
         'contato_enviado': False, 'destino': 'Encerrado sem encaminhamento', 'conversas': 4},
        {'motivo': 'dependente_menor_4', 'rotulo': 'Dependentes · menos de 4 anos',
         'contato_enviado': False, 'destino': 'Encerrado sem encaminhamento', 'conversas': 1},
    ],
}
````

## Passo 18 — Criar `tests/unit/test_encerramentos_por_idade.py`

Cobrir reconstrução, fronteiras, histórico pareado, unidades, nova conversa e contagem.

Base SHA-256: `arquivo novo`. Conteúdo completo proposto: **183 linhas**.

````python
"""Regressões das novas regras, prova do retry e recortes do painel."""

import sqlite3
import unittest
from unittest.mock import patch

from core.integrations.whatsapp.messages.etapa6_messages import (
    montar_mensagem_cliente_menor_18_etapa6,
    montar_mensagem_dependente_menor_5_etapa6,
    montar_mensagem_idade_acima_99_etapa6,
    montar_mensagem_suporte_idoso_etapa6,
)
from core.repositories.monitoramento.encerramentos import (
    buscar_encerramentos_atuais, contar_encerramentos_por_motivo,
)
from monitoramento.encerramentos import apresentar_encerramento, montar_tabela_encerramentos
from tests.unit.test_suporte_idoso_email_obrigatorio import contexto_etapa6, contexto_envio
from workers.worker_flow.response_flow.etapas import resolver_etapa6
from workers.worker_flow.transacoes.encerramento_atendimento import resolver_intencao_encerramento


class RecuperacaoIdadeTests(unittest.TestCase):
    def recuperar(self, idade, resposta, *, suporte=80, dependente=False, tipo='interactive_cta_url', bpa=False):
        contexto = contexto_etapa6(idade, suporte=suporte, dependente=dependente)
        contexto.update(idade_cliente=88, bpa_ativo_unidade=bpa)
        contexto['resposta_bot_para_mensagem_atual'] = {
            'tipo_mensagem': tipo, 'conteudo_texto': 'Bom te ver novamente ☺️\n\n' + resposta,
        }
        return resolver_intencao_encerramento(contexto, {'resposta_ja_existia': True}, object())

    def test_faixa_compativel_usa_entrada_e_nao_cadastro_global(self):
        for idade, suporte, motivo in (
            (51, 60, 'suporte_idoso_50'), (60, 80, 'suporte_idoso_60'),
            (71, 80, 'suporte_idoso_70'), (71, 60, 'suporte_idoso_60'),
            (61, None, 'suporte_idoso_60'), (95, 80, 'encaminhado_suporte_idoso'),
            ('não sei', 60, 'encaminhado_suporte_idoso'),
        ):
            with self.subTest(idade=idade, suporte=suporte):
                resultado = self.recuperar(idade, montar_mensagem_suporte_idoso_etapa6(50), suporte=suporte)
                self.assertEqual(resultado['motivo_encerramento'], motivo)
                self.assertEqual(resultado['bloqueio_dias'], 0)

    def test_bpa_mudou_mas_corpo_preserva_minimo_enviado(self):
        resposta = montar_mensagem_dependente_menor_5_etapa6('João', 5)
        resultado = self.recuperar(4, resposta, dependente=True, tipo='text', bpa=True)
        self.assertEqual(resultado['motivo_encerramento'], 'dependente_menor_5')
        self.assertTrue(resultado['excluir_dependente'])

    def test_oferta_ou_tratamento_nao_vira_encerramento(self):
        for idade, dependente, texto, tipo in (
            (95, False, 'Vamos reservar sua experiência?', 'interactive_button'),
            (4, True, 'Vamos reservar sua experiência?', 'interactive_button'),
            (12, False, 'Olha, digite apenas texto.', 'text'),
            (51, False, montar_mensagem_suporte_idoso_etapa6(50), 'text'),
        ):
            with self.subTest(idade=idade, tipo=tipo):
                self.assertIsNone(self.recuperar(idade, texto, dependente=dependente, tipo=tipo))

    def test_menor_e_universal_comprovados(self):
        menor = self.recuperar(17, montar_mensagem_cliente_menor_18_etapa6(), tipo='text')
        self.assertEqual(menor['motivo_encerramento'], 'titular_menor_18')
        for dependente in (False, True):
            atual = self.recuperar(90, montar_mensagem_idade_acima_99_etapa6(), dependente=dependente)
            legado = self.recuperar(100, montar_mensagem_idade_acima_99_etapa6(), dependente=dependente)
            self.assertEqual(atual['motivo_encerramento'], 'idade_universal_90')
            self.assertEqual(legado['motivo_encerramento'], 'idade_invalida')

    def test_nova_conversa_71_com_limite80_segue_e_90_encerra(self):
        with patch.object(resolver_etapa6, 'enviar_etapa7_cliente', return_value=contexto_envio(7)) as oferta:
            resultado = resolver_etapa6.resolve_etapa6(contexto_etapa6(71, suporte=80))
        oferta.assert_called_once()
        self.assertNotIn('encerrar_atendimento', resultado)
        with patch.object(resolver_etapa6, 'enviar_etapa6_idade_acima_99', return_value=contexto_envio(6)):
            resultado = resolver_etapa6.resolve_etapa6(contexto_etapa6(90, suporte=None))
        intencao = resolver_intencao_encerramento({}, resultado, object())
        self.assertEqual(intencao['motivo_encerramento'], 'idade_universal_90')
        self.assertEqual(intencao['bloqueio_dias'], 0)


class CursorSQLite:
    def __init__(self, conexao):
        self.conexao = conexao

    def execute(self, sql, parametros):
        self.cursor = self.conexao.execute(sql.replace('%s', '?'), parametros)
        self.description = self.cursor.description

    def fetchall(self):
        return self.cursor.fetchall()


class PainelEncerramentosTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(':memory:')
        self.addCleanup(self.conn.close)
        self.conn.execute("ATTACH DATABASE ':memory:' AS chatbot")
        self.conn.executescript('''
            CREATE TABLE chatbot.conversa (
                id_conversa INTEGER PRIMARY KEY, id_cliente INTEGER, id_unidade INTEGER,
                status_dependente BOOLEAN, status_ativa BOOLEAN, id_etapa_atual INTEGER,
                motivo_encerramento TEXT, finalizou_em TEXT
            );
            CREATE TABLE chatbot.historico_mensagens (
                id_mensagem INTEGER PRIMARY KEY, id_conversa INTEGER, id_etapa INTEGER,
                quem_enviou TEXT, status_envio TEXT, conteudo_texto TEXT, tipo_mensagem TEXT,
                received_data_hora TEXT, id_hash_msg TEXT, id_hash_cliente_origem TEXT
            );
        ''')
        self.cursor = CursorSQLite(self.conn)

    def conversa(self, numero, cliente=1, unidade=1, motivo='suporte_idoso_60', dependente=False,
                 data='2026-09-15', ativa=False, etapa=6):
        self.conn.execute('INSERT INTO chatbot.conversa VALUES(?,?,?,?,?,?,?,?)',
                          (numero, cliente, unidade, dependente, ativa, etapa, motivo, data))

    def historico(self, conversa, idade='61', resposta=None, tipo='interactive_cta_url'):
        base = conversa * 10
        self.conn.execute('INSERT INTO chatbot.historico_mensagens VALUES(?,?,?,?,?,?,?,?,?,?)',
                          (base, conversa, 6, 'cliente', None, idade, 'text', '2026-09-15', f'entrada-{base}', None))
        self.conn.execute('INSERT INTO chatbot.historico_mensagens VALUES(?,?,?,?,?,?,?,?,?,?)',
                          (base+1, conversa, 6, 'bot', 'sent', resposta or montar_mensagem_suporte_idoso_etapa6(60),
                           tipo, '2026-09-15', f'saida-{base}', f'entrada-{base}'))

    def test_nova_conversa_remove_tag_inclusive_fora_do_periodo(self):
        self.conversa(1)
        self.historico(1)
        rows = buscar_encerramentos_atuais(1, [1], self.cursor)
        self.assertEqual(apresentar_encerramento(rows[0])['tag'], '60+')
        # Outra unidade não interfere, mesmo com o mesmo cliente e ID maior.
        self.conversa(2, unidade=2, ativa=True, motivo=None, data=None)
        self.assertEqual(len(buscar_encerramentos_atuais(1, [1, 2], self.cursor)), 1)
        self.assertEqual(buscar_encerramentos_atuais(2, [1], self.cursor), [])
        self.conversa(3, ativa=True, motivo=None, data=None, etapa=1)
        self.assertEqual(buscar_encerramentos_atuais(1, [1], self.cursor), [])
        # O relatório continua contando a conversa antiga encerrada no período.
        contagens = contar_encerramentos_por_motivo(1, '2026-09-01', '2026-10-01', self.cursor)
        self.assertEqual(contagens[0]['conversas'], 1)

    def test_historico_pareado_sobrevive_sem_fila_e_sem_dependente(self):
        self.conversa(1, motivo='dependente_menor_5', dependente=True)
        self.historico(1, '4', montar_mensagem_dependente_menor_5_etapa6('Lia', 5), 'text')
        # Não existem tabelas fila/dependente neste cenário: o vínculo é histórico.
        row = buscar_encerramentos_atuais(1, [1], self.cursor)[0]
        item = apresentar_encerramento(row)
        self.assertEqual((item['nome_dependente'], item['resposta_idade']), ('Lia', '4'))
        self.assertFalse(item['contato_enviado'])
        self.assertEqual(item['tag'], 'Limite mínimo')

    def test_conta_conversas_configuracao_atual_periodo_e_unidade(self):
        self.conversa(1, data='2026-09-01')
        self.conversa(2)  # Mesmo titular, duas conversas: contar duas.
        self.conversa(3, motivo='suporte_idoso_50')
        self.conversa(4, motivo='idade_universal_90')
        self.conversa(5, motivo='idade_universal_90', dependente=True)
        self.conversa(6, motivo='titular_menor_18')
        self.conversa(7, motivo='dependente_menor_4', dependente=True)
        self.conversa(8, motivo='dependente_menor_5', dependente=True)
        self.conversa(9, unidade=2)
        self.conversa(10, data='2026-10-01')
        self.conversa(11, data='2026-08-31')
        self.conversa(12, ativa=True)
        self.conversa(13, motivo='encaminhado_suporte_idoso')
        self.conversa(14, data=None)
        self.conversa(15, etapa=18)
        contagens = contar_encerramentos_por_motivo(1, '2026-09-01', '2026-10-01', self.cursor)
        tabela = montar_tabela_encerramentos(contagens, idade_minima_suporte=60, bpa_ativo=True)
        self.assertEqual([l['conversas'] for l in tabela['linhas']], [2, 1, 1, 1, 1])
        self.assertEqual((tabela['total_encaminhadas'], tabela['total_sem_encaminhamento']), (4, 2))
        desligada = montar_tabela_encerramentos(contagens, idade_minima_suporte=None, bpa_ativo=False)
        self.assertEqual(len(desligada['linhas']), 4)
        self.assertEqual(desligada['total_encaminhadas'], 2)
        self.assertEqual(desligada['linhas'][-1]['motivo'], 'dependente_menor_5')
        self.assertEqual(desligada['linhas'][-1]['conversas'], 1)

    def test_nao_transformar_legado_em_faixa_inventada(self):
        self.conversa(1, motivo='encaminhado_suporte_idoso')
        self.historico(1, '71')
        row = buscar_encerramentos_atuais(1, [1], self.cursor)[0]
        self.assertEqual(apresentar_encerramento(row)['tag'], 'Suporte por idade')


if __name__ == '__main__':
    unittest.main()
````

## Passo 19 — Alterar `tests/unit/test_suporte_por_idade.py`

Atualizar matriz de limites, exigência de telefone e contrato do relatório.

Base SHA-256: `27b7718f2de3344465cb735676ab7ccaf2956187175a37f3c21cc592a25add8e`. Conteúdo completo proposto: **353 linhas**.

````python
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
from webhook.admin import UnidadeAdmin
from webhook.models import Unidade
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
        campo = Unidade._meta.get_field('idade_minima_suporte')
        for limite in LIMITES:
            with self.subTest(limite=limite):
                self.assertEqual(validar_idade_minima_suporte(limite), limite)
                self.assertEqual(campo.clean(limite, Unidade()), limite)
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
        admin = UnidadeAdmin(Unidade, AdminSite())
        request = RequestFactory().get('/admin/')
        request.user = SimpleNamespace(has_perm=lambda *_: True)
        instance = Unidade(id_unidade=1)
        with patch.object(admin, '_validar_cache_unidades_form'), patch.object(
            admin, '_preparar_meta_antes_de_salvar'
        ) as meta:
            form_class = admin.get_form(request, instance, change=True,
                                        fields=['idade_minima_suporte', 'numero_comercial'])
            for limite in LIMITES:
                for telefone in ('', '123', '(71) 99999-9999'):
                    with self.subTest(limite=limite, telefone=telefone):
                        form = form_class(data={
                            'idade_minima_suporte': '' if limite is None else str(limite),
                            'numero_comercial': telefone,
                        }, instance=instance)
                        esperado = telefone == '(71) 99999-9999'
                        self.assertEqual(form.is_valid(), esperado, form.errors)
                        if not esperado:
                            self.assertIn('numero_comercial', form.errors)
            for invalido in ('55', '100', 'True'):
                form = form_class(data={'idade_minima_suporte': invalido,
                                        'numero_comercial': '(71) 99999-9999'}, instance=instance)
                self.assertFalse(form.is_valid())
            meta.assert_not_called()

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
                        'e gostaria de reservar minha experiência Supera gratuita.'
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
                        'Me chamo Maria e gostaria de reservar uma experiência Supera gratuita '
                        'para João, que tem 100 anos.'
                        if dependente else
                        'Me chamo Maria, tenho 100 anos '
                        'e gostaria de reservar minha experiência Supera gratuita.'
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
````

## Passo 20 — Alterar `tests/unit/test_suporte_idoso_email_obrigatorio.py`

Preservar as demais regras e adaptar a universal e os motivos específicos.

Base SHA-256: `bfe76285e2d43d1849e706b1a41eaae3acb49ab315a9e1cc1d0c1da8e2f09383`. Conteúdo completo proposto: **472 linhas**.

````python
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from core.integrations.funil.oportunidades import montar_payload_oportunidade
from core.integrations.whatsapp.messages.etapa6_messages import (
    montar_mensagem_suporte_idoso_etapa6,
)
from core.integrations.whatsapp.numero_comercial import (
    montar_link_numero_comercial_whatsapp,
    numero_comercial_whatsapp_valido,
)
from core.validacoes.email import (
    CLASSIFICACAO_EMAIL_AUSENTE,
    CLASSIFICACAO_EMAIL_NAO_INFORMADO,
    CLASSIFICACAO_EMAIL_VALIDO,
    calcular_email_obrigatorio_efetivo,
    classificar_resposta_email,
    eh_ausencia_email_explicita,
)
from workers.worker_flow.response_flow.etapas import (
    resolver_etapa6,
    resolver_etapa10,
)
from workers.worker_flow.transacoes import (
    efeitos_transicao,
    encerramento_atendimento,
)


RAIZ_PROJETO = Path(__file__).resolve().parents[2]


def contexto_etapa6(idade, *, dependente=False, suporte=None):
    return {
        "id_conversa": 10,
        "id_cliente": 5,
        "id_etapa_atual": 6,
        "id_etapa_cliente": 6,
        "id_etapa_origem_transicao": 6,
        "transicoes_permitidas": {"idade_valida": 7},
        "status_dependente": dependente,
        "bpa_ativo_unidade": False,
        "idade_minima_suporte": suporte,
        "numero_comercial_unidade": "(71) 99999-9999",
        "nome_unidade": "Supera Santo Antônio de Jesus",
        "nome_titular": "Maria",
        "nome_agente": "Suh",
        "genero_agente_unidade": "feminino",
        "nome_dependente": "João" if dependente else None,
        "texto_cliente_atual": str(idade),
        "tipo_mensagem_atual": "text",
        "mensagem_cliente_atual": {
            "id_mensagem_fila": 20,
            "cliente_telefone": "5571999999999",
            "id_phone_unidade": "phone-id",
        },
    }


def contexto_etapa10(
    texto,
    *,
    dependente=False,
    idade=40,
    email_obrigatorio=True,
):
    return {
        "id_conversa": 10,
        "id_cliente": 5,
        "id_etapa_atual": 10,
        "id_etapa_cliente": 10,
        "id_etapa_origem_transicao": 10,
        "transicoes_permitidas": {"email_valido": 11},
        "status_dependente": dependente,
        "idade_cliente": idade,
        "email_obrigatorio_unidade": email_obrigatorio,
        "texto_cliente_atual": texto,
        "tipo_mensagem_atual": "text",
        "mensagem_cliente_atual": {
            "id_mensagem_fila": 20,
            "cliente_telefone": "5571999999999",
            "id_phone_unidade": "phone-id",
        },
        "resposta_bot_para_mensagem_atual": None,
    }


def contexto_envio(etapa):
    return {
        "enviou": True,
        "resposta_ja_existia": False,
        "mensagem_bot": "mensagem",
        "id_hash_msg_bot": "wamid.bot",
        "id_etapa_resultante": etapa,
        "tipo_mensagem": "text",
    }


def dados_lead(*, resposta_email, email_global="novo@example.com"):
    return {
        "id_conversa": 122,
        "id_unidade": 1,
        "nome_unidade": "Santo Antônio de Jesus",
        "status_dependente": False,
        "nome_cliente": "Maria",
        "telefone_cliente": "5571999999999",
        "email_cliente": email_global,
        "resposta_email_conversa": resposta_email,
        "idade_cliente": 65,
        "profissao": "Aposentada",
        "nome_dependente": None,
        "idade_dependente": None,
        "triagem_respostas": [
            {"id_etapa": etapa, "resposta": "nunca"}
            for etapa in range(12, 18)
        ],
    }


class PoliticaEmailTests(unittest.TestCase):
    def test_matriz_da_politica_efetiva(self):
        casos = (
            (True, False, 59, True),
            (False, False, 59, False),
            (True, False, 60, False),
            (True, False, 99, False),
            (True, True, 70, True),
            (False, True, 70, False),
        )

        for configuracao, dependente, idade, esperado in casos:
            with self.subTest(
                configuracao=configuracao,
                dependente=dependente,
                idade=idade,
            ):
                self.assertEqual(
                    calcular_email_obrigatorio_efetivo(
                        configuracao,
                        dependente,
                        idade,
                    ),
                    esperado,
                )

    def test_classificacao_obrigatoria_e_opcional(self):
        valido = classificar_resposta_email(
            "Meu e-mail é Maria@EXEMPLO.COM.",
            email_obrigatorio=True,
        )
        self.assertTrue(valido.aceita)
        self.assertEqual(valido.classificacao, CLASSIFICACAO_EMAIL_VALIDO)
        self.assertEqual(valido.email, "Maria@exemplo.com")

        recusado = classificar_resposta_email(
            "Não tenho",
            email_obrigatorio=True,
        )
        self.assertFalse(recusado.aceita)

        ausencia = classificar_resposta_email(
            "Não tenho e-mail.",
            email_obrigatorio=False,
        )
        self.assertEqual(
            ausencia.classificacao,
            CLASSIFICACAO_EMAIL_AUSENTE,
        )
        self.assertIsNone(ausencia.email)

        comum = classificar_resposta_email(
            "prefiro continuar",
            email_obrigatorio=False,
        )
        self.assertEqual(
            comum.classificacao,
            CLASSIFICACAO_EMAIL_NAO_INFORMADO,
        )

    def test_ausencia_explicita_nao_engole_frase_financeira(self):
        self.assertFalse(eh_ausencia_email_explicita("não tenho dinheiro"))
        self.assertTrue(eh_ausencia_email_explicita("não possuo e-mail"))


class ResolverEtapa10Tests(unittest.TestCase):
    def test_titular_60_mais_avanca_sem_email_mesmo_com_flag_ativa(self):
        with patch.object(
            resolver_etapa10,
            "enviar_etapa11",
            return_value=contexto_envio(11),
        ):
            resultado = resolver_etapa10.resolve_etapa10(
                contexto_etapa10(
                    "Não tenho",
                    idade=60,
                    email_obrigatorio=True,
                )
            )

        self.assertEqual(resultado["evento_transicao"], "email_valido")
        self.assertEqual(
            resultado["resultado_coleta_email"],
            CLASSIFICACAO_EMAIL_AUSENTE,
        )
        self.assertIsNone(resultado["email_cliente"])
        self.assertFalse(resultado["email_obrigatorio_efetivo"])

    def test_dependente_60_mais_continua_obrigado_pela_unidade(self):
        tratamento = contexto_envio(10)
        tratamento["tratamento"] = True

        with patch.object(
            resolver_etapa10,
            "enviar_etapa10_contexto_email_invalido",
            return_value=tratamento,
        ) as enviar_tratamento:
            resultado = resolver_etapa10.resolve_etapa10(
                contexto_etapa10(
                    "Não tenho",
                    dependente=True,
                    idade=70,
                    email_obrigatorio=True,
                )
            )

        enviar_tratamento.assert_called_once()
        self.assertTrue(resultado["tratamento"])
        self.assertNotIn("evento_transicao", resultado)

    def test_financeiro_tem_prioridade_sobre_email_opcional(self):
        tratamento = contexto_envio(10)
        tratamento["tratamento"] = True

        with patch.object(
            resolver_etapa10,
            "validar_pergunta_financeira",
            return_value=True,
        ), patch.object(
            resolver_etapa10,
            "enviar_etapa10_financeiro",
            return_value=tratamento,
        ) as enviar_financeiro, patch.object(
            resolver_etapa10,
            "enviar_etapa11",
        ) as enviar_proxima:
            resultado = resolver_etapa10.resolve_etapa10(
                contexto_etapa10(
                    "não tenho dinheiro",
                    idade=70,
                    email_obrigatorio=False,
                )
            )

        enviar_financeiro.assert_called_once()
        enviar_proxima.assert_not_called()
        self.assertTrue(resultado["tratamento"])


class SuporteIdosoTests(unittest.TestCase):
    def test_fronteiras_e_dependente_preservam_a_ordem_aprovada(self):
        for idade, dependente, suporte, caminho in (
            (59, False, 60, "normal"),
            (60, False, 60, "suporte"),
            (99, False, 60, "cem_mais"),
            (100, False, 60, "cem_mais"),
            (70, True, 60, "normal_dependente"),
        ):
            with self.subTest(
                idade=idade,
                dependente=dependente,
                suporte=suporte,
            ), patch.object(
                resolver_etapa6,
                "enviar_etapa6_suporte_idoso",
                return_value=contexto_envio(6),
            ) as enviar_suporte, patch.object(
                resolver_etapa6,
                "enviar_etapa6_idade_acima_99",
                return_value=contexto_envio(6),
            ) as enviar_cem, patch.object(
                resolver_etapa6,
                "enviar_etapa7_cliente",
                return_value=contexto_envio(7),
            ) as enviar_cliente, patch.object(
                resolver_etapa6,
                "enviar_etapa7_dependente",
                return_value=contexto_envio(7),
            ) as enviar_dependente:
                resultado = resolver_etapa6.resolve_etapa6(
                    contexto_etapa6(
                        idade,
                        dependente=dependente,
                        suporte=suporte,
                    )
                )

            self.assertEqual(enviar_suporte.called, caminho == "suporte")
            self.assertEqual(enviar_cem.called, caminho == "cem_mais")
            self.assertEqual(enviar_cliente.called, caminho == "normal")
            self.assertEqual(
                enviar_dependente.called,
                caminho == "normal_dependente",
            )

            if caminho == "suporte":
                self.assertTrue(resultado["encerrar_atendimento"])
                self.assertEqual(
                    resultado["motivo_encerramento"],
                    "encaminhado_suporte_idoso",
                )

    def test_efeito_terminal_persiste_idade_do_titular(self):
        cursor = object()
        contexto = contexto_etapa6(65, suporte=60)
        envio = contexto_envio(6)
        envio.update(
            {
                "encerrar_atendimento": True,
                "motivo_encerramento": "encaminhado_suporte_idoso",
                "limite_idade_encerramento": 60,
                "idade_aluno": 65,
            }
        )

        with patch.object(
            efeitos_transicao,
            "atualizar_idade_cliente",
        ) as atualizar:
            resultado = (
                efeitos_transicao.atualizar_banco_conforme_transicao_de_etapa(
                    contexto,
                    envio,
                    cursor,
                )
            )

        atualizar.assert_called_once_with(5, 65, cursor)
        self.assertTrue(resultado["encaminhamento_suporte_idoso"])

    def test_encerramento_e_replay_usam_motivo_novo_sem_bloqueio(self):
        contexto = contexto_etapa6(65, suporte=60)
        envio = contexto_envio(6)
        envio.update(
            {
                "encerrar_atendimento": True,
                "motivo_encerramento": "encaminhado_suporte_idoso",
                "limite_idade_encerramento": 60,
            }
        )
        primeira = encerramento_atendimento.resolver_intencao_encerramento(
            contexto,
            envio,
            object(),
        )
        self.assertEqual(
            primeira["motivo_encerramento"],
            "suporte_idoso_60",
        )
        self.assertEqual(primeira["bloqueio_dias"], 0)

        contexto["resposta_bot_para_mensagem_atual"] = {
            "tipo_mensagem": "interactive_cta_url",
            "conteudo_texto": (
                "Que bom te ver aqui novamente, Maria!\n\n"
                + montar_mensagem_suporte_idoso_etapa6(60)
            ),
        }
        replay = encerramento_atendimento.resolver_intencao_encerramento(
            contexto,
            {
                "resposta_ja_existia": True,
                "id_etapa_resultante": 6,
            },
            object(),
        )
        self.assertEqual(
            replay["motivo_encerramento"],
            "suporte_idoso_60",
        )
        self.assertEqual(replay["bloqueio_dias"], 0)

    def test_numero_comercial_compartilha_a_mesma_validacao(self):
        self.assertTrue(numero_comercial_whatsapp_valido("(71) 99999-9999"))
        self.assertEqual(
            montar_link_numero_comercial_whatsapp("(71) 99999-9999"),
            "https://wa.me/5571999999999",
        )
        self.assertFalse(numero_comercial_whatsapp_valido("123"))


class PersistenciaEmailEFunilTests(unittest.TestCase):
    def test_ausencia_limpa_email_anterior_e_retry_reconstroi_sem_flag(self):
        cursor = object()
        contexto = contexto_etapa10(
            "Não tenho",
            idade=70,
            email_obrigatorio=False,
        )
        contexto["resposta_bot_para_mensagem_atual"] = {
            "id_etapa": 11,
        }
        envio = {
            "resposta_ja_existia": True,
            "id_etapa_resultante": 11,
            "evento_transicao": "email_valido",
        }

        with patch.object(
            efeitos_transicao,
            "atualizar_email_cliente",
        ) as atualizar:
            resultado = (
                efeitos_transicao.atualizar_banco_conforme_transicao_de_etapa(
                    contexto,
                    envio,
                    cursor,
                )
            )

        atualizar.assert_called_once_with(5, None, cursor)
        self.assertEqual(
            resultado["resultado_coleta_email"],
            CLASSIFICACAO_EMAIL_AUSENTE,
        )

    def test_funil_usa_resposta_historica_e_nao_email_global_novo(self):
        payload = montar_payload_oportunidade(
            dados_lead(resposta_email="Não tenho")
        )["oportunidades"][0]

        self.assertEqual(payload["contato"]["email"], "")
        observacoes = payload["personalizados"][0]["valor"]
        self.assertIn("E-mail do cliente: não tem", observacoes)
        self.assertNotIn("novo@example.com", observacoes)

    def test_funil_distingue_nao_informado_e_email_historico(self):
        comum = montar_payload_oportunidade(
            dados_lead(resposta_email="prefiro continuar")
        )["oportunidades"][0]
        self.assertIn(
            "E-mail do cliente: não informado",
            comum["personalizados"][0]["valor"],
        )

        antigo = montar_payload_oportunidade(
            dados_lead(resposta_email="antigo@EXEMPLO.COM")
        )["oportunidades"][0]
        self.assertEqual(antigo["contato"]["email"], "antigo@exemplo.com")

    def test_ddl_e_migracao_publicam_o_mesmo_contrato(self):
        ddl = (
            RAIZ_PROJETO
            / "core/database/deploy_database/bank_script.py"
        ).read_text(encoding="utf-8")
        migracao = (
            RAIZ_PROJETO
            / "deploy/migrations/20260829_adicionar_suporte_idoso_email_obrigatorio.sql"
        ).read_text(encoding="utf-8")

        for conteudo in (ddl, migracao):
            self.assertIn("email_obrigatorio", conteudo)
            self.assertIn("encaminhado_suporte_idoso", conteudo)

        self.assertIn("idade_minima_suporte", ddl)
        self.assertIn("suporte_idoso", migracao)
        self.assertNotIn("UPDATE chatbot.unidade", migracao)
        self.assertNotIn("INSERT INTO chatbot.unidade", migracao)


if __name__ == "__main__":
    unittest.main()
````

## Passo 21 — Alterar `tests/unit/test_monitoramento_painel.py`

Atualizar a chamada da apresentação sem o antigo contador escalar.

Base SHA-256: `c292d2005a02d02039e542bfb799cdfdd24c27fc4cce3d80d06bc4612eaca6d5`. Conteúdo completo proposto: **355 linhas**.

````python
"""Contratos de leitura, isolamento e exportação do painel de monitoramento."""

import csv
from datetime import datetime, timedelta, timezone
from io import StringIO
import unittest
from unittest.mock import patch

from django.test import Client

from monitoramento.apresentacao import (
    botoes_para_mensagem,
    consolidar_conversas,
    montar_relatorio,
    normalizar_telefone_google,
)
from monitoramento.periodos import PERIODOS, resolver_periodo
from monitoramento.services import _agrupar_perfis
from core.repositories.monitoramento import painel as repositorio_painel
from tests.fixtures.monitoramento_painel import CONTATOS, CONVERSAS, MENSAGENS, RELATORIO


CABECALHO_OFICIAL_GOOGLE_CONTATOS = [
    'Name Prefix', 'First Name', 'Middle Name', 'Last Name', 'Name Suffix',
    'Phonetic First Name', 'Phonetic Middle Name', 'Phonetic Last Name',
    'Nickname', 'File As', 'E-mail 1 - Label', 'E-mail 1 - Value',
    'Phone 1 - Label', 'Phone 1 - Value', 'Address 1 - Label',
    'Address 1 - Country', 'Address 1 - Street',
    'Address 1 - Extended Address', 'Address 1 - City', 'Address 1 - Region',
    'Address 1 - Postal Code', 'Address 1 - PO Box', 'Organization Name',
    'Organization Title', 'Organization Department', 'Birthday',
    'Event 1 - Label', 'Event 1 - Value', 'Relation 1 - Label',
    'Relation 1 - Value', 'Website 1 - Label', 'Website 1 - Value',
    'Custom Field 1 - Label', 'Custom Field 1 - Value', 'Notes', 'Labels',
]


class MonitoramentoPainelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        from tests.unit.test_monitoramento_login import LoginMonitoramentoTests
        cls.cenario_classe = LoginMonitoramentoTests
        cls.cenario_classe.setUpClass()

    @classmethod
    def tearDownClass(cls):
        cls.cenario_classe.tearDownClass()
        super().tearDownClass()

    def setUp(self):
        self.cenario = self.cenario_classe(
            methodName='test_formulario_oculta_senha_e_nao_oferece_cadastro_ou_recuperacao'
        )
        self.cenario.setUp()
        self.cliente = self.cenario.cliente

    def tearDown(self):
        self.cenario.doCleanups()

    def autenticar(self, usuario=None):
        self.cliente.force_login(usuario or self.cenario.usuario_a)

    def test_painel_exige_sessao_e_entrega_interface_somente_leitura(self):
        self.assertEqual(self.cliente.get('/').status_code, 302)
        for rota in ('/dados/conversas/', '/dados/relatorio/', '/contatos.csv'):
            with self.subTest(rota=rota):
                self.assertEqual(self.cliente.get(rota).status_code, 401)
        self.autenticar()
        resposta = self.cliente.get('/')
        html = resposta.content.decode()
        self.assertEqual(resposta.status_code, 200)
        self.assertIn('Conversas', html)
        self.assertIn('Relatórios', html)
        self.assertIn('somente para monitoramento', html)
        self.assertNotIn('Enviar mensagem', html)
        self.assertIn("default-src 'self'", resposta.headers['Content-Security-Policy'])
        self.assertIn('no-store', resposta.headers['Cache-Control'])

    def test_endpoints_usam_unidade_do_usuario_autenticado(self):
        for usuario, unidade in ((self.cenario.usuario_a, 10), (self.cenario.usuario_b, 20)):
            with self.subTest(unidade=unidade):
                self.cliente = Client()
                self.autenticar(usuario)
                with patch('monitoramento.views.carregar_conversas', return_value=CONVERSAS) as carregar:
                    resposta = self.cliente.get('/dados/conversas/')
                self.assertEqual(resposta.status_code, 200)
                self.assertEqual(carregar.call_args.args[0].id_unidade, unidade)

    def test_mensagens_de_cliente_inexistente_ou_de_outro_escopo_nao_vazam(self):
        self.autenticar()
        with patch('monitoramento.views.carregar_mensagens', return_value={'id_cliente': 999, 'mensagens': []}) as carregar:
            resposta = self.cliente.get('/dados/conversas/999/')
        self.assertEqual(resposta.status_code, 404)
        self.assertEqual(carregar.call_args.args[0].id_unidade, 10)
        self.assertNotIn('Unidade B', resposta.content.decode())

    def test_periodo_invalido_e_metodos_de_escrita_sao_recusados(self):
        self.autenticar()
        with patch('monitoramento.views.carregar_conversas') as carregar:
            self.assertEqual(self.cliente.get('/dados/conversas/?periodo=qualquer').status_code, 400)
            carregar.assert_not_called()
        for rota in ('/dados/conversas/', '/dados/relatorio/', '/contatos.csv'):
            self.assertEqual(self.cliente.post(rota).status_code, 405)

    def test_csv_google_completo_e_elegivel(self):
        self.autenticar()
        with patch('monitoramento.views.carregar_contatos', return_value=CONTATOS):
            completo = self.cliente.get('/contatos.csv?tipo=todos')
            elegivel = self.cliente.get('/contatos.csv?tipo=elegiveis')
        self.assertFalse(completo.content.startswith(b'\xef\xbb\xbf'))
        linhas = list(csv.reader(StringIO(completo.content.decode('utf-8'))))
        self.assertEqual(linhas[0], CABECALHO_OFICIAL_GOOGLE_CONTATOS)
        self.assertTrue(all(len(linha) == 36 for linha in linhas))
        self.assertEqual(linhas[1][1], 'Edcarlos')
        self.assertEqual(linhas[1][3], 'Silva')
        self.assertEqual(
            linhas[1][10:14],
            ['Work', 'edcarlos@example.com', 'Mobile', '+557194111866'],
        )
        self.assertTrue(all(not valor for valor in linhas[1][14:34]))
        self.assertEqual(
            linhas[1][34],
            'Contato exportado pelo monitoramento ESL Tech',
        )
        self.assertTrue(linhas[1][35])
        self.assertEqual(linhas[2][10:12], ['', ''])
        self.assertEqual(linhas[2][12:14], ['Mobile', '+557599111222'])
        self.assertEqual(len(linhas), 3)
        linhas_elegiveis = list(csv.reader(StringIO(elegivel.content.decode('utf-8'))))
        self.assertEqual(len(linhas_elegiveis), 2)
        self.assertTrue(all(len(linha) == 36 for linha in linhas_elegiveis))
        self.assertEqual(normalizar_telefone_google('(71) 94111-1866'), '+5571941111866')
        self.assertEqual(normalizar_telefone_google('123'), '')

        contato_invalido = [{
            'nome': 'Contato Inválido', 'email': 'sem-arroba',
            'waid_telefone': '557194111866',
        }]
        with patch('monitoramento.views.carregar_contatos', return_value=contato_invalido):
            elegivel = self.cliente.get('/contatos.csv?tipo=elegiveis')
        self.assertEqual(
            len(list(csv.reader(StringIO(elegivel.content.decode('utf-8'))))), 1
        )

    def test_csv_essencial_preserva_nome_completo_acentos_e_campos_vazios(self):
        self.autenticar()
        contatos = [
            {'nome': ' João da Silva ', 'email': 'joao@example.com', 'waid_telefone': '557194111866'},
            {'nome': None, 'email': None, 'waid_telefone': '557599111222'},
            {'nome': 'Sem telefone', 'email': 'outro@example.com', 'waid_telefone': None},
            {'nome': '=Nome; "especial"', 'email': '=1+1', 'waid_telefone': '123'},
        ]
        with patch('monitoramento.views.carregar_contatos', return_value=contatos):
            completo = self.cliente.get('/contatos.csv?formato=essencial&tipo=todos')
            elegivel = self.cliente.get('/contatos.csv?formato=essencial&tipo=elegiveis')
        self.assertTrue(completo.content.startswith(b'\xef\xbb\xbf'))
        linhas = list(csv.reader(StringIO(completo.content.decode('utf-8-sig')), delimiter=';'))
        self.assertEqual(linhas, [
            ['Nome', 'E-mail', 'Telefone'],
            ['João da Silva', 'joao@example.com', '7194111866'],
            ['', '', '7599111222'],
            ['Sem telefone', 'outro@example.com', ''],
            ["'=Nome; \"especial\"", "'=1+1", ''],
        ])
        self.assertEqual(
            list(csv.reader(StringIO(elegivel.content.decode('utf-8-sig')), delimiter=';')),
            linhas[:2],
        )
        self.assertIn('contatos_essenciais_total_todos.csv', completo['Content-Disposition'])
        self.assertIn('no-store', completo['Cache-Control'])

    def test_quatro_exports_respeitam_todos_periodos_e_unidade_autorizada(self):
        agora = datetime(2026, 9, 7, 12, tzinfo=timezone.utc)
        for usuario, unidade in ((self.cenario.usuario_a, 10), (self.cenario.usuario_b, 20)):
            self.cliente = Client()
            self.autenticar(usuario)
            for chave in ('total', *PERIODOS):
                periodo = resolver_periodo(chave, agora=agora)
                for formato in ('google', 'essencial'):
                    for tipo in ('todos', 'elegiveis'):
                        with self.subTest(unidade=unidade, periodo=chave, formato=formato, tipo=tipo):
                            with patch('monitoramento.views.resolver_periodo', return_value=periodo) as resolver, \
                                 patch('monitoramento.views.carregar_contatos', return_value=CONTATOS) as carregar:
                                resposta = self.cliente.get('/contatos.csv', {
                                    'formato': formato, 'tipo': tipo, 'periodo': chave,
                                    'id_unidade': 999,
                                })
                            self.assertEqual(resposta.status_code, 200)
                            resolver.assert_called_once_with(chave)
                            acesso, recebido = carregar.call_args.args
                            self.assertEqual(acesso.id_unidade, unidade)
                            self.assertEqual(recebido, periodo)
                            leitor = csv.reader(
                                StringIO(resposta.content.decode('utf-8-sig')),
                                delimiter=';' if formato == 'essencial' else ',',
                            )
                            linhas = list(leitor)
                            self.assertEqual(len(linhas), 2 if tipo == 'elegiveis' else 3)
                            self.assertTrue(all(len(linha) == (3 if formato == 'essencial' else 36) for linha in linhas))
                            self.assertEqual(
                                linhas[1][2 if formato == 'essencial' else 13],
                                '7194111866' if formato == 'essencial' else '+557194111866',
                            )
                            self.assertIn(f'_{chave}_{tipo}.csv', resposta['Content-Disposition'])

    def test_export_essencial_recusa_acesso_invalido_e_parametros_invalidos(self):
        rota = '/contatos.csv?formato=essencial'
        with patch('monitoramento.views.carregar_contatos') as carregar:
            self.assertEqual(self.cliente.get(rota).status_code, 401)
            self.autenticar()
            self.assertEqual(self.cliente.get(rota + '&periodo=invalido').status_code, 400)
            self.assertEqual(self.cliente.get('/contatos.csv?formato=invalido').status_code, 400)
            self.assertEqual(self.cliente.post(rota).status_code, 405)
            with self.cenario.banco.cursor() as cursor:
                cursor.execute('UPDATE unidade SET id_usuario_monitoramento = NULL WHERE id_unidade = 10')
            self.assertEqual(self.cliente.get(rota).status_code, 403)
            carregar.assert_not_called()

    def test_botoes_historicos_vem_do_catalogo_oficial(self):
        mensagem = {'quem_enviou': 'bot', 'tipo': 'interactive_button', 'id_etapa': 2}
        self.assertEqual(botoes_para_mensagem(mensagem), ['Para mim', 'Para um dependente'])
        mensagem['id_etapa'] = 12
        self.assertEqual(botoes_para_mensagem(mensagem), ['Nunca', 'Às vezes', 'Frequentemente'])
        mensagem['quem_enviou'] = 'cliente'
        self.assertEqual(botoes_para_mensagem(mensagem), [])

    def test_consolidacao_cria_tags_sem_misturar_unidades(self):
        linhas = [
            {'id_cliente': 1, 'id_conversa': 10, 'nome_cliente': 'Ana', 'waid_telefone': '5511',
             'status_dependente': True, 'idade_dependente': 12, 'foi_funil': False,
             'avaliada': False, 'ultima_atividade': '2026-09-01',
             'ultima_mensagem_id': 20, 'ultima_mensagem': 'Oi'},
            {'id_cliente': 1, 'id_conversa': 11, 'nome_cliente': 'Ana', 'waid_telefone': '5511',
             'status_dependente': False, 'idade_titular': 65, 'foi_funil': True,
             'avaliada': True, 'ultima_atividade': '2026-09-01',
             'ultima_mensagem_id': 21, 'ultima_mensagem': 'Olá'},
        ]
        resultado = consolidar_conversas(linhas)
        self.assertEqual(resultado[0]['ids_conversa'], [10, 11])
        self.assertEqual(resultado[0]['perfis'], ['dependente', 'menor', 'idoso'])
        self.assertEqual(resultado[0]['perfis_resumidos'], ['dependente_menor', 'idoso'])
        self.assertEqual(resultado[0]['ultima_mensagem'], 'Olá')

    def test_perfis_resumidos_distinguem_dependentes_e_titulares(self):
        cenarios = (
            (1, True, 12, 'dependente_menor'),
            (2, True, 35, 'dependente_adulto'),
            (3, True, 65, 'dependente_idoso'),
            (4, False, 35, 'adulto'),
            (5, False, 65, 'idoso'),
        )
        linhas = []
        for id_cliente, dependente, idade, esperado in cenarios:
            linhas.append({
                'id_cliente': id_cliente,
                'id_conversa': id_cliente * 10,
                'nome_cliente': f'Cliente {id_cliente}',
                'waid_telefone': f'551{id_cliente}',
                'status_dependente': dependente,
                'idade_dependente': idade if dependente else None,
                'idade_titular': None if dependente else idade,
                'foi_funil': False,
                'avaliada': False,
                'ultima_atividade': f'2026-09-0{id_cliente}',
                'ultima_mensagem_id': id_cliente,
                'ultima_mensagem': esperado,
            })

        resultado = {item['id_cliente']: item for item in consolidar_conversas(linhas)}
        for id_cliente, _dependente, _idade, esperado in cenarios:
            self.assertEqual(resultado[id_cliente]['perfis_resumidos'], [esperado])

    def test_periodos_finitos_possuem_comparacao_e_total_nao(self):
        finito = resolver_periodo('7d')
        total = resolver_periodo('total')
        self.assertEqual(finito.fim_anterior, finito.inicio)
        self.assertIsNotNone(finito.inicio_anterior)
        self.assertIsNone(total.inicio)
        self.assertIsNone(total.inicio_anterior)

    def test_comparacao_aceita_periodo_atual_sem_avaliacoes(self):
        relatorio = montar_relatorio(
            {'leads': 2, 'mensagens': 4, 'funil': 1, 'avaliacoes': 0, 'nota_media': None},
            {'leads': 1, 'mensagens': 2, 'funil': 0, 'avaliacoes': 1, 'nota_media': 5.0},
            {}, {}, [], [],
        )
        self.assertIsNone(relatorio['tendencias']['nota_media'])

    def test_perfil_so_conta_lead_totalmente_sem_classificacao(self):
        perfis = _agrupar_perfis([
            {'id_cliente': 1, 'status_dependente': None, 'idade_titular': 35,
             'idade_dependente': None, 'foi_funil': False},
            {'id_cliente': 1, 'status_dependente': False, 'idade_titular': 35,
             'idade_dependente': None, 'foi_funil': True},
            {'id_cliente': 2, 'status_dependente': None, 'idade_titular': 44,
             'idade_dependente': None, 'foi_funil': False},
        ], bpa_ativo=False)
        titular_adulto = next(
            item for item in perfis['linhas'] if item['chave'] == 'titular_adulto'
        )
        self.assertEqual(titular_adulto['leads'], 1)
        self.assertEqual(perfis['sem_classificacao'], 1)

    def test_relatorio_e_conversas_sao_serializados_sem_consultar_rds(self):
        self.autenticar()
        with patch('monitoramento.views.carregar_relatorio', return_value=RELATORIO):
            resposta = self.cliente.get('/dados/relatorio/?periodo=7d')
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(len(resposta.json()['etapas']), 22)
        with patch('monitoramento.views.carregar_mensagens', return_value=MENSAGENS[140]):
            resposta = self.cliente.get('/dados/conversas/140/')
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.json()['mensagens'][1]['botoes'][0], 'Para mim')

    def test_todas_as_consultas_recebem_escopo_e_parametros_completos(self):
        class CursorContrato:
            description = [('valor',)]

            def __init__(self):
                self.execucoes = []

            def execute(self, sql, parametros):
                self.execucoes.append((sql, parametros))
                if sql.count('%s') != len(parametros):
                    raise AssertionError(
                        f'placeholders={sql.count("%s")} parametros={len(parametros)}'
                    )

            def fetchall(self):
                return []

            def fetchone(self):
                return None

        agora = datetime.now(timezone.utc)
        inicio = agora - timedelta(days=7)
        chamadas = (
            lambda c: repositorio_painel.buscar_unidade(10, c),
            lambda c: repositorio_painel.listar_conversas(10, inicio, agora, c),
            lambda c: repositorio_painel.buscar_mensagens(10, 99, inicio, agora, c),
            lambda c: repositorio_painel.buscar_metricas(10, inicio, agora, c),
            lambda c: repositorio_painel.buscar_perfis(10, inicio, agora, c),
            lambda c: repositorio_painel.buscar_satisfacao(10, inicio, agora, c),
            lambda c: repositorio_painel.buscar_etapas(10, inicio, agora, c),
            lambda c: repositorio_painel.buscar_atividade(10, inicio, agora, c, 'dia'),
            lambda c: repositorio_painel.listar_contatos(10, inicio, agora, c),
        )
        for chamada in chamadas:
            with self.subTest(chamada=chamada):
                cursor = CursorContrato()
                chamada(cursor)
                sql, parametros = cursor.execucoes[0]
                self.assertIn(10, parametros)
                self.assertIn('id_unidade', sql)
````

## Passo 22 — Alterar `tests/unit/test_metricas_perfis_relatorios.py`

Exercitar as opções vigentes sem apagar os envios reais do funil nos relatórios existentes.

Base SHA-256: `7586b9fb573467d166fa588f5f47c22f17c0036c28d2a63bbcc6b35d3c5aced6`. Conteúdo completo proposto: **475 linhas**.

````python
from __future__ import annotations

import sys
import types
import unittest
from datetime import datetime, timedelta, timezone
from unittest import mock

from utilitarios.reports_functions import weekly


class MetricasPerfisRelatoriosTests(unittest.TestCase):
    FIM = datetime(2026, 8, 30, 15, tzinfo=timezone.utc)
    INICIO = FIM - timedelta(days=7)

    @staticmethod
    def _perfil(
        id_cliente: int,
        id_conversa: int,
        *,
        id_unidade: int = 1,
        status_dependente: object = False,
        idade_titular: object = 35,
        idade_dependente: object = None,
    ) -> dict[str, object]:
        return {
            "id_unidade": id_unidade,
            "id_cliente": id_cliente,
            "id_conversa": id_conversa,
            "status_dependente": status_dependente,
            "idade_titular": idade_titular,
            "idade_dependente": idade_dependente,
        }

    def _mensagem(self, perfil: dict[str, object], id_mensagem: int) -> dict[str, object]:
        return {
            **perfil,
            "id_mensagem": id_mensagem,
            "received_data_hora": self.INICIO + timedelta(minutes=id_mensagem),
            "quem_enviou": "cliente",
            "tipo_mensagem": "text",
            "conteudo_texto": "Olá",
        }

    @staticmethod
    def _unidade(
        id_unidade: int = 1, *, idade_minima_suporte: int | None = None, bpa_ativo: bool = False
    ) -> dict[str, object]:
        return {
            "id_unidade": id_unidade,
            "nome_unidade": f"Unidade {id_unidade}",
            "idade_minima_suporte": idade_minima_suporte,
            "bpa_ativo": bpa_ativo,
        }

    @staticmethod
    def _linhas(segmentacao: dict[str, object]) -> dict[str, dict[str, object]]:
        return {linha["chave"]: linha for linha in segmentacao["linhas"]}

    def _segmentacao(
        self,
        perfis: list[dict[str, object]],
        enviados: set[int] | None = None,
        *,
        idade_minima_suporte: int | None = None,
        bpa_ativo: bool = False,
    ) -> dict[str, object]:
        return weekly._montar_segmentacao_perfis(
            perfis,
            enviados or set(),
            idade_minima_suporte=idade_minima_suporte,
            bpa_ativo=bpa_ativo,
        )

    def _snapshot(
        self,
        mensagens: list[dict[str, object]],
        funil: list[dict[str, object]],
        unidades: list[dict[str, object]] | None = None,
    ) -> dict[str, object]:
        return weekly.montar_snapshot(
            [self._unidade()] if unidades is None else unidades,
            mensagens,
            funil,
            [],
            self.INICIO,
            self.FIM,
        )

    def test_fronteiras_dependentes_com_minimo_padrao_e_bpa(self) -> None:
        casos = {
            3: (None, None),
            4: (None, "dependente_infantil"),
            5: ("dependente_infantil", "dependente_infantil"),
            17: ("dependente_infantil", "dependente_infantil"),
            18: ("dependente_adulto", "dependente_adulto"),
            45: ("dependente_adulto", "dependente_adulto"),
            59: ("dependente_adulto", "dependente_adulto"),
            60: ("dependente_idoso", "dependente_idoso"),
            99: ("dependente_idoso", "dependente_idoso"),
            100: (None, None),
        }
        for idade, resultados in casos.items():
            for minimo, esperado in zip((5, 4), resultados):
                with self.subTest(idade=idade, minimo=minimo):
                    self.assertEqual(
                        weekly._classificar_perfil_atendimento(
                            status_dependente=True,
                            idade_titular=60,
                            idade_dependente=idade,
                            idade_minima_dependente=minimo,
                        ),
                        esperado,
                    )

    def test_fronteiras_titulares_e_45_permanece_adulto(self) -> None:
        casos = {
            3: None,
            4: None,
            5: None,
            17: None,
            18: "titular_adulto",
            45: "titular_adulto",
            59: "titular_adulto",
            60: "titular_idoso",
            99: "titular_idoso",
            100: None,
        }
        for idade, esperado in casos.items():
            with self.subTest(idade=idade):
                self.assertEqual(
                    weekly._classificar_perfil_atendimento(
                        status_dependente=False,
                        idade_titular=idade,
                        idade_dependente=10,
                        idade_minima_dependente=5,
                    ),
                    esperado,
                )

    def test_idades_nulas_booleanas_fracionarias_e_legadas_sao_desconhecidas(self) -> None:
        for idade in (None, True, False, 18.0, 18.5, "18", "", -1, 0, 100):
            for dependente in (True, False):
                with self.subTest(idade=idade, tipo=type(idade), dependente=dependente):
                    self.assertIsNone(
                        weekly._classificar_perfil_atendimento(
                            status_dependente=dependente,
                            idade_titular=60 if dependente else idade,
                            idade_dependente=idade if dependente else 10,
                            idade_minima_dependente=4,
                        )
                    )

    def test_status_desconhecido_nao_e_inferido_das_idades(self) -> None:
        for status in (None, 0, 1, "true", "false", "", 1.0):
            with self.subTest(status=status, tipo=type(status)):
                self.assertIsNone(
                    weekly._classificar_perfil_atendimento(
                        status_dependente=status,
                        idade_titular=35,
                        idade_dependente=10,
                        idade_minima_dependente=5,
                    )
                )

    def test_so_a_idade_da_pessoa_atendida_classifica_o_perfil(self) -> None:
        for status, titular, dependente, esperado in (
            (True, None, 10, "dependente_infantil"),
            (True, 70, 20, "dependente_adulto"),
            (True, 35, None, None),
            (False, 70, None, "titular_idoso"),
            (False, 35, 70, "titular_adulto"),
            (False, None, 10, None),
        ):
            with self.subTest(status=status, titular=titular, dependente=dependente):
                self.assertEqual(
                    weekly._classificar_perfil_atendimento(
                        status_dependente=status,
                        idade_titular=titular,
                        idade_dependente=dependente,
                        idade_minima_dependente=5,
                    ),
                    esperado,
                )

    def test_bpa_altera_apenas_o_minimo_infantil_e_seu_rotulo(self) -> None:
        perfis = [
            self._perfil(1, 101, status_dependente=True, idade_dependente=4),
            self._perfil(2, 102, status_dependente=True, idade_dependente=5),
        ]
        for bpa, minimo, leads in ((False, 5, 1), (True, 4, 2)):
            with self.subTest(bpa=bpa):
                segmentacao = self._segmentacao(perfis, {101, 102}, bpa_ativo=bpa)
                infantil = self._linhas(segmentacao)["dependente_infantil"]
                self.assertEqual(segmentacao["idade_minima_dependente"], minimo)
                self.assertEqual(infantil["rotulo"], f"Dependentes de {minimo} a 17 anos")
                self.assertEqual(infantil["leads"], leads)
                self.assertEqual(infantil["leads_funil"], leads)

    def test_duas_conversas_do_mesmo_perfil_contam_um_lead(self) -> None:
        segmentacao = self._segmentacao(
            [self._perfil(1, 101), self._perfil(1, 102), self._perfil(2, 103)],
            {101, 102},
        )
        adulto = self._linhas(segmentacao)["titular_adulto"]
        self.assertEqual(adulto["leads"], 2)
        self.assertEqual(adulto["conversas"], 3)
        self.assertEqual(adulto["leads_funil"], 1)
        self.assertEqual(adulto["leads_funil_observados"], 1)
        self.assertEqual(adulto["conversas_funil"], 2)
        self.assertEqual(adulto["conversas_funil_observadas"], 2)
        self.assertEqual(adulto["taxa_funil"], 50.0)
        self.assertEqual(segmentacao["leads_classificados"], 2)
        self.assertEqual(segmentacao["leads_multiperfil"], 0)

    def test_envio_do_dependente_nao_e_herdado_pelo_titular(self) -> None:
        titular = self._perfil(1, 101)
        dependente = self._perfil(1, 102, status_dependente=True, idade_dependente=10)
        snapshot = self._snapshot(
            [self._mensagem(titular, 1), self._mensagem(dependente, 2)],
            [dependente],
        )
        unidade = snapshot["unidades"][0]
        segmentacao = unidade["metricas"]["segmentacao_perfis"]
        linhas = self._linhas(segmentacao)

        self.assertEqual(unidade["metricas"]["leads_contato"], 1)
        self.assertEqual(unidade["metricas"]["leads_funil"], 1)
        self.assertTrue(unidade["conversas"][0]["foi_funil"])
        self.assertEqual(linhas["dependente_infantil"]["leads_funil"], 1)
        self.assertEqual(linhas["titular_adulto"]["leads_funil"], 0)
        self.assertEqual(linhas["titular_adulto"]["leads_funil_observados"], 0)
        self.assertEqual(segmentacao["leads_classificados"], 1)
        self.assertEqual(segmentacao["leads_multiperfil"], 1)

    def test_mensagens_e_envios_repetidos_nao_duplicam_perfis_no_snapshot(self) -> None:
        perfil = self._perfil(1, 101)
        snapshot = self._snapshot(
            [self._mensagem(perfil, 1), self._mensagem(perfil, 2)],
            [perfil, perfil],
        )
        unidade = snapshot["unidades"][0]
        segmentacao = unidade["metricas"]["segmentacao_perfis"]
        adulto = self._linhas(segmentacao)["titular_adulto"]
        self.assertEqual(len(unidade["perfis_atendimento"]), 1)
        self.assertEqual(len(unidade["conversas"][0]["mensagens"]), 2)
        self.assertEqual(adulto["conversas"], 1)
        self.assertEqual(adulto["conversas_funil"], 1)
        self.assertEqual(segmentacao["conversas_apenas_envio_funil"], 0)

    def test_cliente_compartilhado_nao_mistura_envios_entre_unidades(self) -> None:
        perfil_a = self._perfil(1, 101, id_unidade=1)
        perfil_b = self._perfil(1, 201, id_unidade=2)
        snapshot = self._snapshot(
            [self._mensagem(perfil_a, 1), self._mensagem(perfil_b, 2)],
            [perfil_a],
            [self._unidade(1), self._unidade(2)],
        )
        unidades = {item["id_unidade"]: item for item in snapshot["unidades"]}
        for id_unidade, enviado in ((1, 1), (2, 0)):
            with self.subTest(id_unidade=id_unidade):
                metricas = unidades[id_unidade]["metricas"]
                linha = self._linhas(metricas["segmentacao_perfis"])["titular_adulto"]
                self.assertEqual(metricas["leads_contato"], 1)
                self.assertEqual(metricas["leads_funil"], enviado)
                self.assertEqual(linha["leads_funil"], enviado)
                self.assertEqual(linha["conversas"], 1)

    def test_configuracao_bpa_e_aplicada_por_unidade(self) -> None:
        perfis = [
            self._perfil(1, unidade * 100, id_unidade=unidade,
                         status_dependente=True, idade_dependente=4)
            for unidade in (1, 2)
        ]
        snapshot = self._snapshot(
            [self._mensagem(perfil, indice) for indice, perfil in enumerate(perfis, 1)],
            perfis,
            [self._unidade(1), self._unidade(2, bpa_ativo=True)],
        )
        unidades = {item["id_unidade"]: item for item in snapshot["unidades"]}
        for id_unidade, esperado in ((1, 0), (2, 1)):
            with self.subTest(id_unidade=id_unidade):
                segmentacao = unidades[id_unidade]["metricas"]["segmentacao_perfis"]
                infantil = self._linhas(segmentacao)["dependente_infantil"]
                self.assertEqual(infantil["leads"], esperado)
                self.assertEqual(infantil["leads_funil"], esperado)

    def test_retry_de_conversa_antiga_preserva_perfil_sem_importar_mensagens(self) -> None:
        antiga = self._perfil(1, 101, status_dependente=True, idade_dependente=17)
        nova = self._perfil(1, 102, idade_titular=45)
        snapshot = self._snapshot([self._mensagem(nova, 1)], [antiga])
        unidade = snapshot["unidades"][0]
        segmentacao = unidade["metricas"]["segmentacao_perfis"]
        linhas = self._linhas(segmentacao)

        self.assertEqual(unidade["metricas"]["leads_funil"], 1)
        self.assertEqual(unidade["conversas"][0]["ids_conversa"], [102])
        self.assertEqual(len(unidade["conversas"][0]["mensagens"]), 1)
        self.assertEqual({p["id_conversa"] for p in unidade["perfis_atendimento"]}, {101, 102})
        self.assertEqual(linhas["dependente_infantil"]["leads_funil"], 1)
        self.assertEqual(linhas["titular_adulto"]["leads_funil"], 0)
        self.assertEqual(segmentacao["conversas_apenas_envio_funil"], 1)
        self.assertEqual(segmentacao["conversas_classificadas"], 2)
        self.assertEqual(segmentacao["leads_multiperfil"], 1)

    def test_funil_fora_da_coorte_nao_acrescenta_lead_nem_perfil(self) -> None:
        contato = self._perfil(1, 101)
        fora_da_coorte = self._perfil(2, 201, idade_titular=60)
        outra_unidade = self._perfil(1, 301, id_unidade=2, idade_titular=60)
        snapshot = self._snapshot(
            [self._mensagem(contato, 1)],
            [fora_da_coorte, outra_unidade],
            [self._unidade(1), self._unidade(2)],
        )
        unidades = {item["id_unidade"]: item for item in snapshot["unidades"]}
        self.assertEqual(unidades[1]["metricas"]["leads_contato"], 1)
        self.assertEqual(unidades[2]["metricas"]["leads_contato"], 0)
        for unidade in unidades.values():
            segmentacao = unidade["metricas"]["segmentacao_perfis"]
            self.assertEqual(unidade["metricas"]["leads_funil"], 0)
            self.assertEqual(self._linhas(segmentacao)["titular_idoso"]["leads"], 0)
            self.assertEqual(segmentacao["conversas_apenas_envio_funil"], 0)

    def test_idade_minima_suporte_nao_apaga_envios_observados_nem_afeta_dependente(self) -> None:
        perfis = [
            self._perfil(1, 101, idade_titular=60),
            self._perfil(1, 102, idade_titular=60),
            self._perfil(2, 201, status_dependente=True, idade_dependente=60),
        ]
        for suporte in (None, 50, 60, 70, 80):
            with self.subTest(suporte=suporte):
                segmentacao = self._segmentacao(perfis, {101, 102, 201}, idade_minima_suporte=suporte)
                linhas = self._linhas(segmentacao)
                titular = linhas["titular_idoso"]
                self.assertEqual(titular["leads"], 1)
                self.assertEqual(titular["conversas"], 2)
                self.assertEqual(titular["leads_funil_observados"], 1)
                self.assertEqual(titular["conversas_funil_observadas"], 2)
                self.assertEqual(titular["leads_funil"], 1)
                self.assertEqual(titular["conversas_funil"], 2)
                self.assertEqual(titular["taxa_funil"], 100.0)
                self.assertFalse(titular["funil_nao_aplicavel"])
                self.assertEqual(linhas["dependente_idoso"]["leads_funil"], 1)
                self.assertEqual(linhas["dependente_idoso"]["taxa_funil"], 100.0)
                self.assertFalse(linhas["dependente_idoso"]["funil_nao_aplicavel"])

    def test_suporte_atual_preserva_funil_geral_do_snapshot(self) -> None:
        perfil = self._perfil(1, 101, idade_titular=60)
        snapshot = self._snapshot(
            [self._mensagem(perfil, 1)], [perfil], [self._unidade(idade_minima_suporte=60)]
        )
        metricas = snapshot["unidades"][0]["metricas"]
        titular = self._linhas(metricas["segmentacao_perfis"])["titular_idoso"]
        self.assertEqual(metricas["leads_funil"], 1)
        self.assertEqual(titular["leads_funil_observados"], 1)
        self.assertEqual(titular["leads_funil"], 1)
        self.assertEqual(titular["taxa_funil"], 100.0)

    def test_todos_os_perfis_empatados_sao_predominantes_por_leads(self) -> None:
        perfis = [
            self._perfil(1, 101),
            self._perfil(1, 102),
            self._perfil(2, 201, status_dependente=True, idade_dependente=10),
        ]
        segmentacao = self._segmentacao(perfis)
        self.assertCountEqual(
            segmentacao["perfis_predominantes"],
            ["Titulares de 18 a 59 anos", "Dependentes de 5 a 17 anos"],
        )

    def test_desconhecidos_separam_leads_conversas_e_envios_nao_classificados(self) -> None:
        perfis = [
            self._perfil(1, 101, status_dependente=None),
            self._perfil(1, 102),
            self._perfil(2, 201, status_dependente=None),
            self._perfil(2, 202),
            self._perfil(3, 301, idade_titular=None),
        ]
        # O envio do cliente 1 só tem perfil desconhecido; o do cliente 2 tem ambos.
        segmentacao = self._segmentacao(perfis, {101, 201, 202})
        self.assertEqual(segmentacao["leads_classificados"], 2)
        self.assertEqual(segmentacao["leads_sem_classificacao"], 1)
        self.assertEqual(segmentacao["conversas_classificadas"], 2)
        self.assertEqual(segmentacao["conversas_sem_classificacao"], 3)
        self.assertEqual(segmentacao["conversas_funil_sem_classificacao"], 2)
        self.assertEqual(segmentacao["leads_funil_apenas_sem_classificacao"], 1)
        self.assertEqual(segmentacao["cobertura_conversas"], 40.0)

    def test_snapshot_vazio_mantem_cinco_perfis_sem_divisao_por_zero(self) -> None:
        snapshot = self._snapshot([], [])
        unidade = snapshot["unidades"][0]
        segmentacao = unidade["metricas"]["segmentacao_perfis"]
        self.assertEqual(unidade["conversas"], [])
        self.assertEqual(unidade["perfis_atendimento"], [])
        self.assertEqual(unidade["metricas"]["leads_contato"], 0)
        self.assertEqual(unidade["metricas"]["taxa_funil"], 0.0)
        self.assertEqual(segmentacao["perfis_predominantes"], [])
        self.assertEqual(segmentacao["cobertura_conversas"], 0.0)
        self.assertEqual(segmentacao["leads_funil_apenas_sem_classificacao"], 0)
        self.assertEqual(set(self._linhas(segmentacao)), set(weekly.PERFIS_ATENDIMENTO))
        for linha in segmentacao["linhas"]:
            with self.subTest(perfil=linha["chave"]):
                for campo in ("leads", "conversas", "leads_funil", "conversas_funil",
                              "leads_funil_observados", "conversas_funil_observadas"):
                    self.assertEqual(linha[campo], 0)
                self.assertEqual(linha["taxa_funil"], 0.0)
        self.assertEqual(self._snapshot([], [], unidades=[])["unidades"], [])

    def test_sql_seleciona_perfis_por_conversa_com_janela_semiaberta_e_so_leitura(self) -> None:
        cursor = mock.MagicMock()
        cursor.fetchall.side_effect = [[self._unidade()], [], [], []]
        cursor.fetchone.return_value = {"existe": False}
        conn = mock.MagicMock()
        conn.cursor.return_value = cursor
        driver = types.ModuleType("psycopg")
        rows = types.ModuleType("psycopg.rows")
        rows.dict_row = object()
        driver.rows = rows

        with mock.patch.dict(sys.modules, {"psycopg": driver, "psycopg.rows": rows}):
            snapshot = weekly.coletar_snapshot(
                conn, self.INICIO, self.FIM, ids_unidade=[1], max_mensagens=100
            )

        consultas = [
            (" ".join(chamada.args[0].lower().split()), chamada.args[1:])
            for chamada in cursor.execute.call_args_list
        ]
        self.assertEqual(
            consultas[0][0],
            "begin transaction isolation level repeatable read read only",
        )
        sql_mensagens, params_mensagens = next(
            item for item in consultas if "with clientes_janela as" in item[0]
        )
        sql_funil, params_funil = next(
            item for item in consultas if "from chatbot.funil_envios f" in item[0]
        )
        for sql in (sql_mensagens, sql_funil):
            with self.subTest(consulta="funil" if sql == sql_funil else "mensagens"):
                for coluna in (
                    "c.id_conversa", "c.status_dependente", "cl.idade as idade_titular",
                    "d.idade as idade_dependente", "d.nome_dependente",
                ):
                    self.assertIn(coluna, sql)
                self.assertIn(
                    "left join chatbot.dependente d on d.id_conversa = c.id_conversa "
                    "and d.id_cliente = c.id_cliente",
                    sql,
                )
                self.assertIn("u.id_unidade = any(%s)", sql)
        self.assertIn("h0.quem_enviou = 'cliente'", sql_mensagens)
        self.assertIn("h0.received_data_hora >= %s", sql_mensagens)
        self.assertIn("h0.received_data_hora < %s", sql_mensagens)
        self.assertIn("h.received_data_hora >= %s", sql_mensagens)
        self.assertIn("h.received_data_hora < %s", sql_mensagens)
        self.assertIn("f.status = 'sent'", sql_funil)
        self.assertIn("f.enviado_em >= %s", sql_funil)
        self.assertIn("f.enviado_em < %s", sql_funil)
        self.assertEqual(
            params_mensagens,
            ((self.INICIO, self.FIM, [1], self.INICIO, self.FIM, 101),),
        )
        self.assertEqual(params_funil, ((self.INICIO, self.FIM, [1]),))
        for sql, _ in consultas:
            self.assertNotRegex(sql, r"\b(insert|update|delete|drop|truncate|alter)\b")
        conn.cursor.assert_called_once_with(row_factory=rows.dict_row)
        conn.rollback.assert_called_once_with()
        conn.commit.assert_not_called()
        cursor.close.assert_called_once_with()
        self.assertEqual(snapshot["unidades"][0]["metricas"]["leads_contato"], 0)


if __name__ == "__main__":
    unittest.main()
````

## Passo 23 — Alterar `tests/integration/test_suporte_por_idade_postgres.py`

Separar domínio de migração histórica e instalação nova; fornecer telefone obrigatório na fixture.

Base SHA-256: `c6758be11598fd6d09e707b7a977dec31d3d9de618547979826a1677b5391b84`. Conteúdo completo proposto: **261 linhas**.

````python
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
````

## Passo 24 — Criar `tests/integration/test_encerramentos_por_idade_postgres.py`

Validar migração e finalização atômica em PostgreSQL local descartável.

Base SHA-256: `arquivo novo`. Conteúdo completo proposto: **122 linhas**.

````python
"""Migração e atomicidade em PostgreSQL local vazio explicitamente autorizado."""

import os
from pathlib import Path
import unittest

import psycopg
from psycopg.conninfo import conninfo_to_dict

from core.repositories.monitoramento.encerramentos import contar_encerramentos_por_motivo
from core.validacoes.encerramento_por_idade import MOTIVOS_IDADE
from workers.worker_flow.transacoes.finalizacao_fila import finalizar_mensagem_processada

DSN = os.environ.get('COMERCIAL_IDADE_TEST_DSN')
SQL = Path(__file__).resolve().parents[2] / 'deploy/migrations/20260926_filtro_comercial_regras_idade.sql'


@unittest.skipUnless(DSN, 'Exige COMERCIAL_IDADE_TEST_DSN local em test_chatbot_comercial vazio')
class EncerramentosPostgresTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        parametros = conninfo_to_dict(DSN)
        locais = {'localhost', '127.0.0.1', '::1'}
        if (parametros.get('host') not in locais
                or parametros.get('dbname') != 'test_chatbot_comercial'
                or parametros.get('service')
                or (parametros.get('hostaddr') and parametros['hostaddr'] not in locais)):
            raise RuntimeError('Recusado: exige loopback e banco test_chatbot_comercial')
        cls.conn = psycopg.connect(DSN, autocommit=True, connect_timeout=5)
        if (cls.conn.info.host not in locais or cls.conn.info.dbname != 'test_chatbot_comercial'
                or cls.conn.execute("SELECT to_regnamespace('chatbot')").fetchone()[0] is not None):
            cls.conn.close()
            raise RuntimeError('Recusado: conexão incompatível ou schema já existente')

    @classmethod
    def tearDownClass(cls):
        cls.conn.close()

    def setUp(self):
        self.conn.execute('CREATE SCHEMA chatbot')
        self.addCleanup(self.limpar)
        self.conn.execute('''
            CREATE TABLE chatbot.unidade (
                id_unidade INTEGER PRIMARY KEY, nome_unidade TEXT,
                numero_comercial VARCHAR(30), idade_minima_suporte INTEGER,
                CONSTRAINT ck_unidade_idade_minima_suporte
                CHECK (idade_minima_suporte IS NULL OR idade_minima_suporte IN (50,60,70,80,90))
            );
            INSERT INTO chatbot.unidade VALUES
                (1,'Teste','5571999999999',90),(2,'Teste 2','(71) 99999-9999',60);
            CREATE TABLE chatbot.conversa (
                id_conversa INTEGER PRIMARY KEY, id_cliente INTEGER, id_unidade INTEGER,
                id_etapa_atual INTEGER, status_dependente BOOLEAN DEFAULT FALSE,
                status_ativa BOOLEAN, finalizou_em TIMESTAMPTZ, motivo_encerramento VARCHAR(30),
                processing BOOLEAN DEFAULT FALSE, processing_started_at TIMESTAMPTZ,
                CONSTRAINT ck_conversa_motivo_encerramento CHECK (motivo_encerramento IS NULL OR
                    motivo_encerramento IN ('idade_invalida','encaminhado_suporte_idoso',
                                           'foi_agendado','followup_sem_resposta'))
            );
            INSERT INTO chatbot.conversa (id_conversa,id_cliente,id_unidade,id_etapa_atual,status_ativa,motivo_encerramento)
                VALUES (1,1,1,6,FALSE,'idade_invalida'),(2,1,1,6,TRUE,NULL);
            CREATE TABLE chatbot.fila_mensagens (
                id_mensagem INTEGER PRIMARY KEY, status TEXT,
                processing_started_at TIMESTAMPTZ, last_error TEXT
            );
            INSERT INTO chatbot.fila_mensagens VALUES(1,'processing',NULL,NULL);
            CREATE TABLE chatbot.cache_controle (nome TEXT PRIMARY KEY,versao INTEGER,atualizado_em TIMESTAMPTZ);
            INSERT INTO chatbot.cache_controle VALUES('unidades',3,NOW());
        ''')

    def limpar(self):
        self.conn.execute('ROLLBACK')
        # Somente o schema criado pelo próprio teste, após a verificação de vazio.
        self.conn.execute('DROP SCHEMA chatbot CASCADE')

    def migrar(self):
        self.conn.execute(SQL.read_text(encoding='utf-8'))

    def test_migracao_preserva_historico_e_normaliza_sem_ampliar_faixa(self):
        antes = self.conn.execute('SELECT to_jsonb(c) FROM chatbot.conversa c ORDER BY id_conversa').fetchall()
        self.migrar()
        self.assertEqual(self.conn.execute('SELECT idade_minima_suporte FROM chatbot.unidade ORDER BY id_unidade').fetchall(), [(None,), (60,)])
        self.assertEqual(self.conn.execute('SELECT to_jsonb(c) FROM chatbot.conversa c ORDER BY id_conversa').fetchall(), antes)
        self.assertEqual(self.conn.execute("SELECT versao FROM chatbot.cache_controle WHERE nome='unidades'").fetchone()[0], 4)
        for motivo in MOTIVOS_IDADE | {'foi_agendado', 'followup_sem_resposta'}:
            self.conn.execute('UPDATE chatbot.conversa SET motivo_encerramento=%s WHERE id_conversa=1', (motivo,))
        for limite in (None,50,60,70,80):
            self.conn.execute('UPDATE chatbot.unidade SET idade_minima_suporte=%s WHERE id_unidade=1', (limite,))
        with self.assertRaises(psycopg.errors.CheckViolation):
            self.conn.execute('UPDATE chatbot.unidade SET idade_minima_suporte=90 WHERE id_unidade=1')

    def test_telefone_invalido_aborta_toda_migracao(self):
        self.conn.execute('UPDATE chatbot.unidade SET numero_comercial=NULL WHERE id_unidade=2')
        with self.assertRaisesRegex(psycopg.Error, 'Regularize'):
            self.migrar()
        self.conn.execute('ROLLBACK')
        self.assertEqual(self.conn.execute('SELECT idade_minima_suporte FROM chatbot.unidade WHERE id_unidade=1').fetchone()[0], 90)
        self.assertEqual(self.conn.execute("SELECT versao FROM chatbot.cache_controle WHERE nome='unidades'").fetchone()[0], 3)

    def test_encerramento_e_sent_confirmam_ou_desfazem_juntos(self):
        self.migrar()
        mensagem = {'id_mensagem': 1, 'cliente_telefone': '5571999999999', 'id_phone_unidade': 'teste'}
        contexto = {'id_unidade': 1, 'conversa': {'id_conversa': 2, 'estado': 'ativa'}}
        final = {'intencao_encerramento': {
            'motivo': 'encaminhado_suporte_idoso', 'motivo_encerramento': 'suporte_idoso_60',
            'excluir_dependente': False, 'bloqueio_dias': 0,
        }}
        with self.assertRaisesRegex(RuntimeError, 'queda simulada'):
            with self.conn.transaction(), self.conn.cursor() as cursor:
                finalizar_mensagem_processada(mensagem, contexto, 1, cursor, final)
                raise RuntimeError('queda simulada')
        self.assertEqual(self.conn.execute('SELECT status_ativa,motivo_encerramento FROM chatbot.conversa WHERE id_conversa=2').fetchone(), (True,None))
        self.assertEqual(self.conn.execute('SELECT status FROM chatbot.fila_mensagens').fetchone()[0], 'processing')
        with self.conn.transaction(), self.conn.cursor() as cursor:
            finalizar_mensagem_processada(mensagem, contexto, 1, cursor, final)
        with self.conn.cursor() as cursor:
            linhas = contar_encerramentos_por_motivo(1, None, '2099-01-01', cursor)
        self.assertEqual(linhas, [{'motivo_encerramento':'suporte_idoso_60','status_dependente':False,'conversas':1}])


if __name__ == '__main__':
    unittest.main()
````

## Passo 25 — Alterar `REGRAS_DE_NEGOCIO.md`

Registrar as decisões aprovadas e a diferença entre Comercial e relatório.

Base SHA-256: `3f5fad4446bc7095953794b3a1053fbdd952a131fbda424bdbbcfe15066e467c`. Conteúdo completo proposto: **1501 linhas**.

````markdown
# Regras de negócio do Chatbot - V1

## Finalidade

Este documento é a fonte de verdade para interpretar o comportamento do sistema.
Antes de classificar algo como bug ou alterar o worker, webhook, fila, histórico,
conversa, cache ou banco de dados, estas regras devem ser consultadas.

Uma proteção que aparentemente descarta, bloqueia ou repete um processamento pode
ser uma decisão deliberada da V1. Alterar uma dessas regras representa uma mudança
de produto, e não apenas uma refatoração técnica.

## Definições

- **Cliente:** identificado por `wa_id` ou `cliente_telefone`.
- **Unidade:** identificada por `phone_number_id` ou `id_phone_unidade`.
- **Turno:** interação do par `(cliente_telefone, id_phone_unidade)` que aguarda
  uma resposta do bot.
- **Mensagem aceita:** mensagem que passou pelas validações do webhook e foi
  persistida em `chatbot.fila_mensagens`.
- **Mensagem respondida:** mensagem da fila que possui histórico do bot com
  `status_envio = 'sent'`, vinculado ao seu `id_mensagem_fila` e ao hash da
  mensagem original do cliente.
- **Fonte de verdade:** dado persistido no PostgreSQL. O Redis acelera consultas,
  mas não substitui o banco de dados como fonte definitiva.

## 1. Um turno por vez

Para cada par `(cliente_telefone, id_phone_unidade)`, a V1 deve manter no máximo
uma mensagem aberta ainda sem resposta própria do bot. A decisão não depende
somente de `fila_mensagens.status`; ela combina filas abertas com a resposta do
bot especificamente vinculada a cada mensagem.

- A prioridade é determinada exclusivamente pela ordem de chegada, e não pelo
  tamanho, conteúdo ou aparente importância da mensagem.
- A primeira mensagem válida será persistida na fila.
- Enquanto essa primeira mensagem estiver `pending` ou `processing` e ainda não
  possuir sua própria resposta persistida do bot, qualquer mensagem posterior do
  mesmo cliente para a mesma unidade será descartada pelo webhook.
- A mensagem descartada não será inserida na fila nem no histórico. Para o banco,
  ela nunca existiu.
- Quando todas as filas `pending` ou `processing` já possuírem sua própria
  resposta do bot, o webhook poderá aceitar a primeira mensagem do próximo turno,
  mesmo que a limpeza da fila anterior ainda não tenha chegado ao commit de
  `fila_mensagens.status = 'sent'`.
- A decisão é serializada por `pg_advisory_xact_lock`, utilizando unidade e
  cliente como chaves.

Exemplo de comportamento esperado:

```text
cliente: oi
cliente: olá, quero solicitar determinada coisa
```

Nesse exemplo, `oi` chegou primeiro e é a única mensagem válida do turno. O bot
deverá responder somente a `oi`. A mensagem `olá, quero solicitar determinada
coisa` será descartada no webhook e não aparecerá na fila nem no histórico.

O objetivo não é escolher a mensagem mais completa ou mais útil. O objetivo é
garantir uma única entrada por turno e impedir que várias mensagens enviadas
antes da resposta do bot sejam interpretadas como etapas independentes.

### 1.1. Por que `fila_mensagens.status = 'sent'` não é a única fonte da decisão

`sent` continua sendo o estado terminal que confirma a conclusão administrativa
da fila. Porém, ele não é a única prova de que o turno funcional foi respondido.
A prova mais importante para recuperação é o histórico do bot vinculado à
mensagem específica por:

```text
id_conversa
id_mensagem_fila
id_hash_cliente_origem
```

Se a Meta confirmou o envio, o histórico do bot foi persistido e
`last_message_from` foi atualizado para `bot`, o cliente já recebeu a resposta.
O worker ainda pode cair antes do commit separado que altera a fila para `sent`.
Utilizar somente o status da fila faria o webhook descartar a resposta seguinte
do cliente durante essa janela, embora ela já pertença legitimamente ao próximo
turno.

O webhook atual usa o histórico específico do bot como prova de resposta. Ele não
libera uma mensagem apenas porque o `last_message_from` geral da conversa está
como `bot`; cada fila aberta precisa possuir sua própria resposta correspondente.

### 1.2. Recuperação detalhada entre resposta do bot e `sent`

#### Etapa 1 - A foi respondida, mas o worker caiu

```text
Fila A: processing
Histórico do cliente A: existe
Histórico do bot A: existe
last_message_from: bot
Lock da conversa: ocupado
```

O worker cai antes de marcar A como `sent`. A resposta já chegou ao WhatsApp do
cliente, mas A permanece `processing` por aproximadamente 2 minutos.

#### Etapa 2 - o cliente envia B

O webhook encontra A aberta, mas também encontra a resposta do bot vinculada
especificamente a A. B é a primeira mensagem do próximo turno e pode entrar:

```text
Fila A: processing, respondida
Fila B: pending, sem resposta
```

#### Etapa 3 - outro ciclo seleciona B

Antes de resolver a conversa ou tentar seu lock, o worker procura uma mensagem
anterior ainda aberta para o mesmo cliente e unidade. Como A continua
`processing`, B é devolvida para `pending` por 30 segundos. Essa espera não
consome tentativa de erro.

```text
Fila A: processing, respondida
Fila B: pending, sem resposta
```

#### Etapa 4 - o cliente envia C

O webhook examina individualmente todas as filas abertas:

| Fila | Status | Resposta própria do bot |
|---|---|---|
| A | `processing` | Sim |
| B | `pending` | Não |

Como B ainda não possui resposta própria:

```text
todas_abertas_respondidas = False
```

C é descartada e nunca entra no banco. O `last_message_from = 'bot'` deixado por
A não libera C, porque não existe histórico do bot vinculado especificamente a B.

#### Etapa 5 - B aguarda a recuperação de A

Enquanto A continuar aberta, cada claim de B repetirá a verificação de ordem e a
devolverá para `pending` por 30 segundos, sem tentar o lock da conversa:

```text
Fila A: processing, respondida
Fila B: pending, sem resposta
```

C e quaisquer mensagens posteriores continuarão bloqueadas por B.

#### Etapa 6 - A retorna após o timeout

Depois de aproximadamente 2 minutos:

1. A fica elegível novamente;
2. o lock antigo já expirou após 110 segundos;
3. outro worker adquire o lock;
4. encontra o histórico do bot vinculado a A;
5. não envia uma resposta duplicada;
6. marca A como `sent`;
7. libera o lock.

```text
Fila A: sent
Fila B: pending
```

#### Etapa 7 - B é processada

B já não encontra mensagem anterior aberta, resolve a conversa, adquire o lock e
segue normalmente. Se esse lock for recusado por outro motivo, B volta para
`pending` por 5 segundos, também sem consumir uma tentativa de erro.
Enquanto B não possuir sua própria resposta do bot, qualquer C será descartada.

Depois que a resposta de B for persistida, a primeira mensagem do próximo turno
poderá entrar, inclusive na pequena janela anterior ao commit de `sent` de B.

### 1.3. Limite prático de mensagens abertas

Na recuperação descrita, o sistema poderá manter temporariamente:

```text
1 mensagem antiga respondida, mas ainda processing
+
1 mensagem nova sem resposta
```

Isso não cria uma sequência ilimitada. Assim que B entra sem resposta própria,
C, D, E e todas as mensagens seguintes são descartadas pelo webhook. O advisory
lock do turno também impede que B e C sejam aceitas simultaneamente por uma
corrida entre requisições.

Implementação principal:

- `core/repositories/seguranca/turno_cliente.py`
- `callback/webhook/services/populating_fila_mensagens.py`

## 2. Idempotência na entrada do webhook

- `fila_mensagens.id_hash_msg` é único.
- A repetição do mesmo evento pela Meta não deve criar outra linha na fila.
- `ON CONFLICT DO NOTHING` é o comportamento esperado para o mesmo
  `id_hash_msg`.
- Uma mensagem nova possui outro hash e continua sujeita à regra de turno.

Ignorar um webhook duplicado não é bug.

## 3. Primeira mensagem do turno

A primeira mensagem válida deverá ser persistida na fila quando não existir outra
mensagem aberta sem resposta para o mesmo cliente e unidade.

É considerado bug quando a primeira mensagem, ou a única mensagem enviada no
turno, é ignorada sem que alguma regra explícita deste documento seja aplicável.

## 4. Estados e tentativas da fila

Estados utilizados:

- `pending`: aguardando processamento.
- `processing`: reservada por um worker.
- `sent`: processamento e resposta concluídos.
- `failed`: permitido pelo schema, mas não é o destino utilizado atualmente
  quando o limite de tentativas é atingido.

Regras da V1:

- O dequeue altera a mensagem para `processing` e incrementa `retry_count`.
- Uma mensagem `processing` abandonada poderá ser retomada depois de 2 minutos.
- Erros tratados reagendam a mensagem para 2 minutos depois, enquanto ainda
  houver tentativa disponível.
- O limite é de 3 tentativas de processamento.
- Ao identificar `retry_count >= 3`, a mensagem é excluída.
- Não existe uma quarta tentativa.

A exclusão ao atingir o limite de 3 tentativas é uma regra de negócio confirmada
da V1, e não um bug. Alterar esse comportamento para `failed`, dead-letter ou um
número maior de tentativas exige uma nova decisão de produto.

Implementação principal:

- `core/database/deploy_database/bank_script.py`, função `chatbot.dequeue_message()`
- `workers/tratamento_erros_externos/expection_process.py`
- `core/repositories/atendimento/fila.py`

## 5. Ordenação e exclusão mútua

- Uma conversa deve ser processada por apenas um worker por vez.
- O lock da conversa poderá ser retomado se estiver abandonado por mais de 110
  segundos.
- `lock_version` impede que um worker antigo libere o lock adquirido por um
  worker mais novo.
- Uma mensagem não poderá ultrapassar outra mensagem anterior ainda aberta na
  mesma conversa.
- A ordem utiliza `received_data_hora` e, em caso de empate, `id_mensagem`.
- Uma mensagem posterior que encontrar outra anterior aberta será reagendada sem
  consumir uma tentativa de erro.

Implementação principal:

- `core/database/deploy_database/bank_script.py`, funções `lock_conversa()` e
  `unlock_conversa()`
- `core/repositories/atendimento/conversas.py`
- `core/repositories/atendimento/fila.py`
- `workers/worker_flow/transacoes/lock_conversa.py`
- `workers/worker_flow/transacoes/ordem_turno.py`

## 6. Conversa ativa e bloqueio por 30 dias

- Poderá existir somente uma conversa ativa para o mesmo cliente e unidade.
- Essa garantia é protegida pelo índice parcial `idx_conversa_unica_ativa`.
- Uma conversa finalizada em etapa com `bloqueio_dias > 0` permanecerá
  bloqueada pelo prazo declarado na política.
- A etapa 2 registra a escolha inicial entre titular e dependente. A etapa 3
  aceita exclusivamente `Sim` ou `Não`, por clique nos botões ou pelo mesmo
  texto digitado. `Sim` mantém a escolha; `Não` seleciona o polo oposto.
  Os dois resultados seguem obrigatoriamente para a etapa 4. Mídia, dúvida
  sobre reforço escolar, pergunta financeira inequívoca ou qualquer outro
  conteúdo repetem a confirmação.
- A etapa 4 sempre coleta, em texto livre, a profissão. Somente depois de
  persistir esse dado ela consulta o `status_dependente` final: dependente
  segue para a etapa 5, que pergunta o nome; titular segue para a etapa 6,
  que pergunta a idade. Assim, nenhum fluxo novo pula a profissão.
- A profissão válida da etapa 4 é salva, na mesma transação, em dois níveis:
  `conversa.profissao` preserva o snapshot daquele atendimento e
  `cliente.profissao` é substituída pelo valor válido mais recente informado
  pelo cliente. Uma conversa posterior nunca reescreve a profissão das
  conversas anteriores.
- Antes dessa persistência, o validador rejeita como
  `profissao_fora_contexto` somente as oito respostas completas já observadas:
  `Pra minha filha na verdade`, `Não entendi`, `Para meu filho`,
  `Pra meu filho`, `Minha filha é autista e percebo q ela tem dificuldade no
  aprendizado , vcs atende autista tambem`, `não seria pra meu filho`,
  `Meu filho` e `Vc ouviu áudio ou ligação`. A comparação ocorre sobre a frase
  inteira normalizada, nunca pela presença isolada de palavras como `áudio`,
  `ligação`, `filho`, `filha` ou `autista`. Quando houver correspondência, a
  etapa 4 apenas reapresenta a pergunta, sem evento, avanço ou persistência e
  sem criar uma etapa de confirmação adicional.
- A etapa 11 introduz a triagem, as etapas 12 a 17 fazem as seis perguntas e a
  etapa 18 apresenta o agendamento. A etapa 18 torna a conversa elegível ao
  Funil, mas não encerra nem bloqueia o atendimento.
- Na etapa 11, o clique em `Começar triagem` e confirmações textuais inequívocas
  disparam o mesmo evento `triagem_iniciada`. A validação aceita variações de
  começar, iniciar e prosseguir, enquanto negativas e respostas ambíguas mantêm
  a conversa na etapa 11.
- As etapas 12 a 17 não mudam de ID nem de transição conforme a idade. Elas
  selecionam somente o texto da pergunta: titular usa sempre a versão adulta;
  dependente com menos de 18 anos usa a versão infantil; dependente com 18 anos
  ou mais usa a versão adulta com o nome persistido. O limite de entrada de 4
  anos em unidade com BPA e de 5 anos sem BPA continua pertencendo à validação
  de idade anterior à triagem.
- Cada unidade possui `idade_minima_suporte` (NULL/50/60/70/80, padrão NULL)
  e `email_obrigatorio` (padrão TRUE). A migração da política anterior conserva
  TRUE como 60 e FALSE como NULL; novas unidades começam sem suporte ativado.
- Na etapa 6, mídia, reforço escolar e financeiro precedem a validação de idade.
  A universal 90+ tem prioridade e vale para titular e dependente, inclusive com
  suporte desativado. Envia contato com mensagem pronta e encerra com
  `idade_universal_90`. Titulares abaixo de 90 e a partir do suporte configurado
  encerram com `suporte_idoso_50/60/70/80`; a idade desse suporte é persistida.
  Menores de 18 encerram com `titular_menor_18`. Dependentes abaixo do mínimo
  encerram com `dependente_menor_4` (BPA) ou `dependente_menor_5` (sem BPA).
  Menores não recebem contato comercial. Nenhum desses casos gera Funil ou
  bloqueio de 30 dias. Os nomes internos `idade_acima_99` permanecem compatíveis,
  mas não representam o corte dos novos atendimentos.
- Para todas as faixas configuráveis (50/60/70/80), o encaminhamento usa
  a mesma mensagem de atendimento personalizado, sem anunciar o limite, e o
  botão `Falar agora`.
- Todo botão para o comercial leva uma mensagem pronta, inclusive o universal 90+.
  O texto identifica o chatbot pelo nome e artigo conforme seu gênero, a unidade
  e o cliente que está conversando. Na rota de titular, inclui sua idade e o
  desejo de reservar sua experiência Supera gratuita. Na rota de dependente,
  identifica também o nome e a idade do dependente e pede a experiência para ele.
  A idade é a informada na resposta atual da etapa 6, nunca uma idade antiga
  nem a idade do dependente atribuída ao titular. A origem vem da unidade
  vinculada à conversa; não inventar informações ausentes.
  O cliente confirma o envio no WhatsApp; abrir o botão não envia esse texto.
- O proprietário configura o limite no Admin. Toda unidade exige número comercial
  brasileiro válido, mesmo com suporte desativado. A migração normaliza 90 para
  NULL e invalida o cache; nunca converte 90 para 80.
- Retry exige a resposta conhecida vinculada à mesma conversa, fila e hash da
  entrada. A idade vem da mensagem vinculada, nunca de `cliente.idade`. Para
  suporte comprovado entre 50 e 89, usa o limite atual se ele ainda inclui a idade;
  caso contrário, usa o maior entre 50/60/70/80 que não exceda a idade, inclusive
  se o suporte foi desativado. Registra a reconstrução compatível em log, sem
  afirmar que descobriu a faixa histórica exata. Suporte legado 90–99 fica genérico.
  O mínimo BPA é recuperado do texto efetivamente enviado. Uma oferta já enviada
  não vira encerramento por mudança de regra. Universal 100+ em retry sem motivo
  confirmado conserva o legado quando o corpo não distingue a versão. Encerramento
  e fila sent continuam atômicos; o risco Meta-before-DB permanece aceito.
- Na etapa 10, mídia, reforço escolar e financeiro continuam precedendo a
  coleta de e-mail. A exigência efetiva é a configuração da unidade, exceto
  para o titular de 60 a 99 anos, cujo e-mail é universalmente opcional quando
  o atendimento não tiver sido encerrado pelo suporte ao idoso. Dependentes
  seguem exclusivamente a configuração da unidade.
- Quando o e-mail é obrigatório, somente um endereço estruturalmente válido
  avança. Quando é opcional, um endereço válido é salvo; ausência declarada ou
  qualquer outra resposta comum aceita limpa `cliente.email` para `NULL` e
  avança sem tratamento de e-mail. A classificação da resposta permanece
  vinculada à conversa para que o Funil exiba `não tem` ou `não informado` sem
  inventar um endereço.
- A etapa 19 registra uma nota de satisfação de 1 a 5. Na etapa 20, o cliente
  escolhe se deseja comentar: a aceitação segue para a etapa 21 e a recusa
  salta diretamente para a etapa 22. A etapa 21 coleta o comentário livre e
  avança para 22 sem julgar seu conteúdo: `ok`, `sim`, emojis e pontuação também
  são aceitos. Não há tratamento de contexto inválido nessa etapa. Uma recusa
  explícita ou resposta sem texto encerra sem comentário (`NULL`); botões antigos
  não são gravados como comentário. Mídias mantêm a orientação para escrever
  por texto, sem avançar. A recuperação usa o mesmo critério de persistência. Nota e
  comentário são internos, não compõem o payload do Funil e não encerram nem
  bloqueiam o atendimento.
- A etapa 22 encerra a conversa, registra `foi_agendado` e aplica o bloqueio de
  30 dias. A despedida usa `te receber` para titular e `receber você e
  {nome_dependente}` para dependente, tanto no caminho 20 -> 22 quanto 21 -> 22.
  O nome vem do dependente vinculado à conversa e à unidade; nunca substituir
  silenciosamente a rota de dependente pela de titular quando faltar esse dado.
- Durante esse período, novas mensagens para a mesma unidade não iniciarão outro
  atendimento.
- Depois dos 30 dias, o cliente poderá iniciar uma nova conversa com a mesma
  unidade.

Implementação principal:

- `core/database/deploy_database/bank_script.py`
- `core/repositories/atendimento/conversas.py`
- `core/repositories/fluxo/politicas.py`
- `workers/worker_flow/valida_banco.py`
- `core/cache/runtime/cache_conversas_bloqueadas.py`

### 6.1 Oportunidade no Funil de Vendas

- Uma conversa torna-se elegível ao entrar na etapa 18.
- As etapas 18 a 22 permanecem elegíveis. Assim, avançar na pesquisa antes do
  próximo ciclo do worker não remove a conversa da fila do Funil.
- `lead_no_funil = TRUE` é a confirmação que impede um segundo envio da mesma
  conversa; nota e comentário da pesquisa não fazem parte do snapshot enviado.
- O worker cria uma oportunidade por vez na coluna `Leads` do CRM.
- O snapshot exige nome, telefone, idade da pessoa atendida e as seis respostas
  canônicas da triagem. O e-mail pode estar ausente quando a política efetiva
  da conversa o tornou opcional; nesse caso, o contato é enviado sem endereço
  e as observações exibem `não tem` ou `não informado`, conforme a resposta.
- O resultado de e-mail pertence à conversa que chegou ao Funil. Ele é
  reconstruído pela mensagem do cliente na etapa 10 vinculada à resposta do
  bot na etapa 11; uma conversa posterior não pode alterar esse snapshot por
  meio do valor global de `cliente.email`.
- A profissão da conversa é exibida nas observações; o Funil não usa
  `cliente.profissao`, pois ela pode ter sido atualizada por outro atendimento.
  Conversas legadas podem apresentar a profissão como não informada.
- As observações apresentam as seis perguntas e suas respostas na ordem das
  etapas 12 a 17. O Funil usa o mesmo catálogo de perguntas do WhatsApp e não
  envia mais o resumo por quantidade de `Nunca`, `Às vezes` e
  `Frequentemente`.
- Em atendimento para dependente, a oportunidade mantém o cliente pagante como
  contato e inclui nome e idade do dependente nas observações.
- A resposta só é confirmada quando o HTTP não falha e o JSON contém
  `response = success`.
- Falha antes da confirmação externa devolve `funil_envios` para `pending` e
  não altera `lead_no_funil`.
- `funil_envios` usa claim com `FOR UPDATE SKIP LOCKED` e lease para recuperar
  itens abandonados em `processing`.
- O título segue `Chatbot Lead <nome_unidade>`. A conversa é identificada pelos
  dados do snapshot e pelo estado local de `funil_envios`; o CRM não recebe o ID
  interno da conversa no título.
- A V1 não cria atividade e não sincroniza atualizações posteriores do CRM.

O processo é desativado por padrão e só inicia com
`FUNIL_WORKER_ENABLED=True` depois do teste manual da unidade.

## 7. Histórico da mensagem do cliente

Depois que uma mensagem da fila for aceita pelo worker:

- Ela será registrada no histórico como `quem_enviou = 'cliente'`.
- Sua identificação lógica utilizará conversa, `id_mensagem_fila` e
  `id_hash_msg`.
- Durante um retry, o registro existente deverá ser reutilizado.
- A etapa persistida no histórico deverá ser reutilizada; o retry não poderá
  reinterpretar a mensagem em outra etapa.
- `last_message_from` deverá permanecer como `cliente` enquanto não existir uma
  resposta do bot persistida para aquela mensagem.
- `last_interaction_at` deverá utilizar o horário persistido da mensagem, e não o
  horário em que o retry ocorreu.

### Respostas da triagem cognitiva

- A triagem mantém exatamente seis perguntas nas etapas 12 a 17.
- A idade e o destino do atendimento são relidos do banco em cada ciclo. Isso
  preserva a mesma variante no retry e impede escolher silenciosamente uma
  pergunta quando idade, nome do dependente ou destino estiverem inconsistentes.
- A versão infantil sempre usa o nome do dependente. A versão adulta usa
  `você` para o titular e o nome para um dependente adulto.
- Cada pergunta aceita somente `Nunca`, `Às vezes` ou `Frequentemente`.
- Botão e texto digitado percorrem a mesma validação exata.
- Qualquer outro conteúdo recebe o tratamento de contexto e mantém a conversa
  na pergunta atual.
- A resposta canônica é registrada em `chatbot.respostas_desafios` com a
  conversa, a etapa da pergunta e o histórico da mensagem do cliente.
- A restrição única por conversa e etapa torna a gravação idempotente.
- Em retry, a resposta pode ser reconstruída pela mensagem original.

## 8. Histórico e idempotência da resposta do bot

A resposta do bot a uma mensagem enfileirada é vinculada à entrada original por:

- `id_conversa`;
- `id_mensagem_fila`;
- `id_hash_cliente_origem`.

O lembrete proativo não responde a uma entrada enfileirada: deixa os dois campos
de origem nulos e usa recibo próprio por conversa e âncora do ciclo. Ele não
serve como prova de resposta para liberar um turno A/B/C.

Se `resposta_bot_para_mensagem_atual` já existir:

- a Meta não deverá ser chamada novamente;
- o histórico do bot não deverá ser duplicado;
- o contexto da conversa deverá ser reparado a partir dos dados persistidos;
- no retry normal, `last_message_from` deverá terminar como `bot`;
- a fila poderá seguir para `sent`.

O replay de uma retomada de follow-up já concluída reutiliza a resposta persistida
sem alterar a interação atual ou zerar um ciclo posterior. Essa recuperação fica
em `workers/worker_flow/transacoes/retorno_followup.py`.

As proteções `if resposta_bot_atual`, presentes nos fluxos normais e de
tratamento, são regras essenciais de idempotência da V1.

Implementação principal:

- `workers/worker_flow/valida_historico.py`
- `workers/worker_flow/response_flow/flow_sender.py`
- `workers/worker_flow/response_flow/etapas/`
- `workers/worker_flow/transacoes/persistencia_resposta.py`

## 9. Semântica de `last_message_from`

- Mensagem do cliente persistida e ainda sem resposta: `cliente`.
- Resposta do bot persistida: `bot`.
- Retry sem resposta do bot mantém ou repara o campo para `cliente`.
- Retry com resposta do bot existente mantém ou repara o campo para `bot`.
- O campo representa o último lado com mensagem persistida para o estado atual;
  ele não é apenas uma marcação de que a conversa já foi iniciada.

Recuperar uma retomada de follow-up já concluída não sobrescreve o estado de
uma interação posterior. A confirmação do lembrete proativo também registra
o bot como último lado, junto do histórico e do recibo de envio.

## 10. Etapas da conversa

- `chatbot.etapa` representa os estados existentes da conversa.
- `chatbot.etapa_transicao` representa as arestas permitidas entre esses
  estados.
- Uma resposta válida produz um evento e somente poderá seguir para o destino
  cadastrado para a combinação `origem + evento`.
- Uma etapa poderá possuir mais de um destino, desde que cada evento identifique
  uma única transição.
- Avanços, saltos e o retorno controlado `9 + retorno_adiado -> 8` são permitidos
  somente quando existe uma aresta explícita.
- Um exemplo de salto autorizado é
  `20 + comentario_satisfacao_recusado -> 22`.
- A atualização utilizará a origem persistida no histórico da mensagem e será
  revalidada no `UPDATE` da conversa.
- Um retry com resposta do bot existente reutilizará a etapa do histórico do
  bot e reconstruirá o evento pela origem e pelo destino.
- Tratamentos que apenas orientam o cliente poderão responder sem avançar a
  etapa e não produzirão evento de transição.

Qualquer transição sem aresta cadastrada é bug. A ordem numérica dos IDs serve
para organização e não define navegação.

## 11. Tipos de mensagem na V1

- `text` e `interactive` são tipos suportados pelo fluxo normal de validação.
- Mídias e anexos não são respostas suportadas pelo fluxo normal da V1.
- Uma mídia recebida deverá ser registrada no histórico.
- O bot enviará uma orientação para o cliente continuar por texto.
- Essa orientação não avançará a etapa, mas alterará `last_message_from` para
  `bot` depois de ser persistida.
- Texto com intenção de preço, custo, mensalidade ou investimento recebe
  tratamento próprio e não deve ser interpretado como resposta comum da etapa.
- Depois que a etapa 1 já foi apresentada, respostas de nome com números,
  caracteres inválidos, repetição artificial ou termos pejorativos recebem
  tratamento de contexto e não avançam a conversa.

Desconsiderar o conteúdo da mídia para fins de avanço de etapa não é bug.

### 11.1. Conversa iniciada por texto

Quando a conversa ainda não possui etapa atual persistida, qualquer mensagem de
texto comum poderá iniciar o atendimento e receber a saudação normal da etapa 1.

Essa regra vale mesmo que o texto inicial seja estranho, curto, tenha símbolos ou
pareça fora de contexto. Nessa primeira interação, o objetivo é apresentar o
agente virtual configurado para a unidade e pedir o nome do cliente.

Mídia, reforço escolar e intenção financeira conservam seus tratamentos e sua
prioridade, nessa ordem. Depois deles, o primeiro texto que perguntar o que é
o Supera ou pedir informações gerais recebe a apresentação explicativa aprovada,
com a comparação a uma academia para o cérebro e o pedido do nome. As demais
entradas recebem a abertura padrão.

A identificação aceita frases completas com ou sem saudação, nome do Supera,
acentos e interrogação, como `Do que se trata?`, `O que é?` e `Olá! Posso ter
mais informações sobre isso?`. Não basta uma palavra solta. Esse caminho só
existe antes da etapa 1 estar apresentada; depois disso, o nome continua sendo
validado normalmente. Ambas as aberturas inicializam a etapa 1, sem consumir
o primeiro texto como nome, e convergem para a mesma etapa 2 após um nome válido.
Não há novo evento de transição, flag no banco ou mudança de follow-up/retry.

Nas mensagens iniciais padrão, explicativa, de mídia, de intenção financeira
e de tratamento de reforço escolar, a apresentação é formada exclusivamente pelos dados
persistidos em `chatbot.unidade`:

- `nome_unidade`: nome público da unidade;
- `nome_agente`: nome público do agente virtual;
- `genero`: seleciona `Sou o {nome_agente}` para `masculino` e
  `Sou a {nome_agente}` para `feminino`.

Esses campos não alteram evento, transição, turno, retry ou transação. Eles são
apenas dados de apresentação lidos pelo contexto da etapa 1. As demais mensagens
mantêm seus textos próprios.

### Linguagem da experiência Supera e sua reserva

A composição das falas, a personalidade acolhedora e a organização dos
arquivos seguem o [contrato editorial de messages](core/integrations/whatsapp/messages/README.md).
Ele deve ser consultado em revisões de textos, tratamentos e retomadas,
preservando as regras operacionais deste documento.

Cada etapa separa sua mensagem padrão da repetição pura. Financeiro, mídia
e reforço escolar vêm de módulos próprios e são compostos antes dessa repetição.
Contexto inválido usa uma mensagem própria, que já orienta o cliente a responder
corretamente, sem concatenar a mensagem de repetição. Preserva os botões/opções
e rodapés nativos, assim como titular/dependente. A regra também vale na triagem
e na pesquisa. Pode receber o prefixo de inatividade de três horas quando elegível;
não recebe outro tratamento ou prefixo de follow-up nesse mesmo ciclo.
Inatividade de três horas mantém a validação normal (podendo avançar ou tratar);
a reação ao follow-up acolhe e valida a resposta. Quando não há resposta válida
nem tratamento específico, reapresenta a pergunta neutra. A etapa 8 continua
avançando diretamente para a 9. O retorno não soma saudações; quando repete a
etapa, usa sua pergunta neutra sem repetir apresentação ou despedida.

A oferta inicial da etapa 7 destaca **demonstração prática gratuita** logo na
abertura, antes da explicação da avaliação de habilidades, e termina com o
convite para reservar uma **experiência Supera exclusiva**. A saudação
`Maravilha, {nome_titular}! ☺️` se dirige a quem conversa nas duas rotas;
quando há dependente, a demonstração, a avaliação e a reserva mencionam
`nome_dependente` como participante. As demais etapas e os tratamentos podem
continuar reforçando **experiência Supera gratuita**. Gratuidade da experiência
não significa curso ou matrícula gratuitos. Não há nome/gênero de diretor ou
novas colunas para essa oferta.

O atendimento deve ser acolhedor e convidativo, com frases naturais, emojis
discretos e negrito moderado. A oferta usa **presentear**, e a comemoração
**Maravilha, {nome_titular}! ☺️** pertence à apresentação normal: não aparece após avisos de
mídia, dúvidas ou respostas não compreendidas. Nesses casos, o bot acolhe a
mensagem e orienta como continuar, sem atribuir o erro ao cliente.

Na etapa 1, a apresentação não presume quem participará da experiência.
Na oferta e na apresentação do link de reserva, o dependente é mencionado
pelo nome quando for o participante, inclusive na repetição por follow-up.
Esses ajustes de linguagem não alteram validação, transição ou elegibilidade.

Uma negativa sem alternativa na etapa 2 repete a pergunta, sem escolher
um destino. Correções explícitas com vírgula e destinos alternativos
completos continuam aceitos. A confirmação da etapa 3 é preservada.

Perguntas sobre a gratuidade da demonstração ou experiência recebem o
tratamento financeiro, sem avanço. Perguntas curtas como `É gratuita?`
podem retomar a oferta nas etapas de convite e reserva. Menções a algo
gratuito fora desse contexto não recebem uma classificação nova genérica.

As saudações de retorno não se acumulam na etapa 9. O sender devolve
ao histórico o mesmo texto enviado; retries preservam respostas anteriores.

Nas etapas 7 e 9, o botão **Quero reservar** e confirmações digitadas como
**quero**, **sim** e **quero agendar** continuam aceitos. Por decisão de
negócio, o aceite flexível não foi endurecido: expressões como `quero pensar melhor`
continuam seguindo o reconhecimento existente. Negativas reconhecidas e pedidos
informativos, como **quero saber como reservar**, não confirmam a oferta.
**Talvez mais tarde** mantém o evento de adiamento. A etapa 18 apresenta
**Já reservei** e aceita também as confirmações antigas de conclusão, como
**já agendei**. Dizer **quero reservar** nessa etapa não comprova conclusão.
Os nomes técnicos de eventos e colunas permanecem, incluindo `link_agendamento`
e `agendamento_confirmado`; idade, e-mail, follow-up e fronteiras transacionais
conservam suas regras.

### 11.2. Exceção para conversa iniciada com mídia

Quando a primeira mensagem de uma conversa for uma mídia, ainda não existirá
uma etapa atual persistida. Nesse caso:

1. o bot enviará saudação da etapa 1 junto com o aviso de mídia não suportada;
2. a mensagem solicitará o nome do cliente por texto;
3. o tratamento registrará a etapa 1 como apresentada;
4. a próxima interação válida será interpretada como resposta da etapa 1 e
   poderá direcionar o fluxo para a etapa 2.

Mensagem esperada, usando uma das duas primeiras linhas conforme o gênero do
agente:

```text
Masculino: Bom dia/Boa tarde/Boa noite! Sou o {nome_agente}, assistente do {nome_unidade}! ☺️
Feminino:  Bom dia/Boa tarde/Boa noite! Sou a {nome_agente}, assistente do {nome_unidade}! ☺️
Hoje vou te ajudar a dar os primeiros passos para conhecer o Supera! 🧡

Olha não reconhecemos ainda mensagem com mídia, apenas texto.
Me diz, qual o seu primeiro nome?
```

Para qualquer etapa já apresentada, a regra geral será diferente. Se a conversa
estiver na etapa N e o cliente enviar uma mídia:

1. o bot enviará o tratamento de tipo de mensagem não suportado;
2. o tratamento poderá repetir a pergunta da etapa atual quando essa
   reapresentação estiver implementada;
3. o tratamento não alterará a etapa persistida;
4. a interação seguinte por texto será interpretada como resposta da etapa N;
5. uma resposta válida produzirá o evento que aponta para o destino cadastrado;
6. a mensagem normal da etapa N não precisará ser enviada de novo em separado.

Na etapa 1 já apresentada, a resposta esperada para mídia será:

```text
Olha não reconhecemos ainda mensagem com mídia, apenas texto.
Me diz, qual o seu primeiro nome?
```

Para etapas ainda sem tratamento específico, a mensagem poderá ser mais genérica:

```text
Recebi uma mídia, mas nesta etapa eu preciso que você responda por texto ou use os botões disponíveis.

Envie uma mensagem de texto para continuarmos.
```

Em ambos os casos:

1. o tratamento não avança etapa;
2. a interação seguinte por texto será interpretada como resposta da etapa N;
3. uma resposta válida seguirá a transição cadastrada para a etapa N.

Portanto, o tratamento de mídia não avança etapa já apresentada. A exceção é
somente a conversa iniciada com mídia, porque a própria mensagem de tratamento
também apresenta a etapa 1.

### 11.3. Tratamento financeiro

Quando o cliente enviar texto perguntando sobre valor, custo, preço,
mensalidade, investimento ou termo equivalente:

1. a mensagem do cliente será registrada no histórico;
2. o bot explicará que os valores de investimento são definidos após a
   experiência Supera gratuita na unidade, com orientação da equipe;
3. a mensagem também reapresentará a pergunta da etapa atual;
4. a conversa não avançará por causa da pergunta de valor;
5. `last_message_from` será atualizado para `bot` depois da resposta persistida.

Se a conversa iniciar com pergunta de valor, a resposta esperada usará uma das
duas primeiras linhas conforme o gênero do agente:

```text
Masculino: Bom dia/Boa tarde/Boa noite! Sou o {nome_agente}, assistente do {nome_unidade}! ☺️
Feminino:  Bom dia/Boa tarde/Boa noite! Sou a {nome_agente}, assistente do {nome_unidade}! ☺️

Hoje vou te ajudar a dar os primeiros passos para conhecer o Supera! 🧡

Olha, os valores de investimento são definidos após a *experiência Supera gratuita* na unidade. Assim, nossa equipe poderá orientar você sobre a opção mais adequada. ☺️

Vamos lá:

Me diz, qual o seu primeiro nome?
```

Nesse caso, a etapa 1 fica registrada como apresentada, e a próxima resposta em
texto será interpretada como resposta da etapa 1.

Se a etapa 1 já tiver sido apresentada e o cliente responder perguntando sobre
valor, a mensagem esperada será:

```text
Olha, os valores de investimento são definidos após a *experiência Supera gratuita* na unidade. Assim, nossa equipe poderá orientar você sobre a opção mais adequada. ☺️

Vamos lá:

Me diz, qual o seu primeiro nome?
```

Esse tratamento é financeiro, não tratamento de contexto. Ele possui fluxo e
sender próprios para evitar misturar dúvida comercial com resposta fora do
contexto da etapa.

O prefixo é único e a pergunta seguinte retoma a etapa sem repetir todo o
convite. O participante permanece correto, inclusive quando é um dependente.
Os textos destacam com moderação a experiência e a ação principal usando
`*negrito*` no corpo. Os títulos de botões não recebem essa marcação.

### 11.4. Tratamento de dúvida sobre reforço escolar

Nas mesmas etapas que oferecem tratamento financeiro, o sistema também deverá
identificar dúvidas que confundam o Supera com serviços escolares tradicionais,
como reforço escolar, banca, supletivo, cursinho, aula particular ou ensino de
matérias específicas.

O reconhecimento é universal e possui o seguinte contrato:

1. mídia ou tipo não suportado continua tendo prioridade sobre o texto;
2. a dúvida sobre reforço escolar tem prioridade sobre o tratamento financeiro;
3. a mensagem do cliente e a resposta do bot são registradas normalmente;
4. a resposta é marcada com `tipo_tratamento='duvida_reforco_escolar'`;
5. nenhuma transição é produzida e a conversa permanece na etapa atual;
6. a pergunta ou chamada da etapa é reapresentada de forma neutra, preservando
   botões, rodapés, links e as variantes de titular ou dependente aplicáveis.

Assim, uma pergunta como `Quanto custa o reforço escolar?` recebe este
tratamento antes do financeiro. Já uma mídia que contenha texto ou legenda
continua recebendo tratamento de mídia.

Expressões inequívocas de serviço escolar podem ser reconhecidas diretamente.
Nomes de matérias, como matemática ou português, exigem também contexto de
ensino, aula, ajuda ou procura pelo serviço. A palavra isolada não é suficiente,
pois respostas legítimas como `Sou professora de matemática` devem continuar
pertencendo à etapa que coleta a profissão.

Na etapa 4, declarações claras de profissão ou vínculo de trabalho com banca,
cursinho, supletivo ou reforço também são respostas profissionais válidas. Por
exemplo, `Trabalho em um cursinho`, `Sou diretora de um supletivo` e
`Sou professora de matemática em uma banca` não acionam este tratamento. A
exceção é contextual e não altera o reconhecimento nas demais etapas.

Mensagem esperada:

```text
Olha, o Supera não é reforço escolar.
Nós trabalhamos a raiz da aprendizagem, desenvolvendo habilidades como atenção, concentração, memória e raciocínio — o alicerce necessário para aprender melhor em qualquer matéria. 🧠✨

Vamos lá:

(retomada neutra da etapa atual)
```

### 11.5. Tratamento de contexto para nome inválido

Depois que a etapa 1 já foi apresentada, a resposta esperada do cliente é o nome.
Se o cliente responder com texto que pareça fora do contexto de nome, como
caracteres inválidos, números, repetição artificial ou termo pejorativo, o bot
deverá tratar sem avançar a conversa.

Mensagem esperada:

```text
Olha, não consegui entender o seu nome. Digite só seu primeiro nome, por exemplo: Pedro.
```

Esse tratamento é diferente do financeiro e do tipo não suportado. Ele existe
para preservar a etapa atual e pedir novamente um nome utilizável.
O pedido já está completo nessa mensagem; não acrescentar a pergunta de repetição.

### 11.6. Coerência semântica ao reapresentar a etapa

Quando um tratamento reapresentar a pergunta da etapa atual, ele não deverá
concatenar automaticamente a mensagem padrão completa. A pergunta ou chamada
principal pode ser reutilizada, mas aberturas que pressuponham resposta válida,
confirmação, apresentação ou avanço — como `Entendi`, `Certo`, `Perfeito`,
`Maravilha` e `Prazer` — deverão ser omitidas ou substituídas por uma retomada
neutra.

**Exceção de contexto inválido:** a orientação possui redação própria e já
contém o pedido da resposta correta. Nunca concatenar a pergunta de repetição
nem a mensagem inicial. A apresentação visual e os botões/rodapés nativos
continuam pertencendo à etapa. Essa exceção muda a redação, não os critérios
dos validadores, a prioridade dos tratamentos ou os eventos de transição.

A mensagem final deverá ser lida como uma única fala semanticamente coerente.
Depois de informar que uma resposta não foi compreendida ou aceita, o bot não
deverá elogiar, confirmar entendimento nem pressupor que a conversa avançou.
Essa regra vale para tratamentos de mídia, financeiro, contexto e qualquer
tratamento futuro que reapresente conteúdo da etapa.

### 11.7. Saudação de retorno após inatividade

Depois que o cliente já informou o nome na etapa 1, uma nova mensagem recebida
na mesma conversa pelo menos três horas após o último envio confirmado do bot
deverá fazer a resposta começar com `Bom te ver novamente, {nome} ☺️` no caminho normal
com `followup_stage = 0`. Stage positivo ou retomada já registrada segue o
[contrato de follow-up](#follow-up-de-inatividade-e-reação-do-cliente), com o
prefixo de retorno e a validação da resposta; a etapa 8 avança diretamente para a 9.

O intervalo é inclusivo (`>= 3 horas`) e deve comparar o horário original do
evento atual do cliente com a última linha `sent` do bot no histórico da mesma
`id_conversa`. A atividade do mesmo cliente em outra unidade ou conversa não
participa desse cálculo. A própria mensagem em que o nome é informado na etapa
1 ainda não recebe a saudação; a regra começa nas mensagens seguintes, quando o
nome já está validado e persistido.

A saudação é somente um prefixo da resposta que o fluxo já produziria:

- resposta válida: saudação mais a mensagem da etapa resultante;
- mídia, financeiro ou reforço: saudação mais o tratamento e a repetição da etapa atual;
- contexto inválido: saudação mais a mensagem própria de contexto, sem outra pergunta.

Ela não cria etapa, evento de transição, envio separado nem uma segunda linha de
histórico. A barreira idempotente continua sendo executada antes dos resolvers:
se o retry já encontrar a resposta exata do bot persistida para aquela mensagem
do cliente, nenhum novo envio ou prefixo será produzido. Nome, último envio ou
timestamps ausentes/incompatíveis apenas desativam a saudação para aquele evento
e nunca impedem a resposta normal do fluxo.

## 12. Flood, payload e assinatura

- A regra atual de rajada curta considera 15 eventos em 5 segundos.
- Redis é a primeira fonte de avaliação de flood.
- Banco e memória funcionam como fallbacks previstos.
- Um cliente identificado como flood poderá ser bloqueado na Meta e não deverá
  ser enfileirado.
- Conversas explicitamente bloqueadas também não serão enfileiradas.
- Payload acima de `WEBHOOK_MAX_BODY_BYTES` deverá ser rejeitado com HTTP 413
  antes de parse, flood, cache ou banco.
- Assinatura Meta inválida deverá ser rejeitada com HTTP 403 antes de qualquer
  confiança no conteúdo do payload.

Payload grande e assinatura inválida bloqueiam a requisição na entrada, mas não
devem bloquear diretamente um cliente na Meta. Um atacante poderia montar um
payload inválido utilizando o `wa_id` de um cliente real. Bloquear esse número
atingiria a vítima informada pelo atacante, e não necessariamente a origem da
requisição.

Portanto, HTTP 413 ou 403 sem bloqueio Meta é o comportamento final e esperado da
V1, e não uma implementação parcial.

Implementação principal:

- `callback/webhook/services/post_flow.py`
- `callback/webhook/services/flood_guard.py`
- `core/cache/runtime/cache_flood_redis.py`
- `core/cache/cache_flood_memoria.py`

## 13. Commits e estados intermediários do worker

O worker de atendimento possui checkpoints duráveis separados:

1. claim da fila como `processing`;
2. espera por mensagem anterior, quando necessária;
3. validação do cliente e da conversa no banco;
4. aquisição do lock da conversa;
5. vínculo, releitura e histórico do cliente, incluindo o marcador de retomada quando aplicável;
6. renovação do lock antes do envio;
7. histórico e contexto do bot; na retomada, conclusão do marcador e reset do stage;
8. fila marcada como `sent`, depois de conferir novamente a posse do lock;
9. unlock da conversa.

Uma queda entre checkpoints normalmente deixa informações suficientes para que
o timeout e o retry reconheçam o estado intermediário. O objetivo é evitar a
perda da mensagem aceita, mesmo admitindo duplicidade rara.

As decisões de `commit`, `rollback` e `close` da conexão do ciclo pertencem ao
`flow_worker.py`. Repositórios e módulos internos executam operações utilizando a
conexão ou o cursor recebido, sem assumir a propriedade da transação.

## 14. Duplicidade aceita como exceção rara

O sistema busca entrega pelo menos uma vez, e não exatamente uma vez.

A principal janela aceita de duplicidade é:

```text
Meta confirmou ou efetivou o envio
        -> worker caiu ou perdeu a confirmação
        -> histórico do bot ainda não foi confirmado no banco
```

Nesse intervalo, o retry não encontra uma resposta persistida e poderá enviar
novamente. Depois do commit do histórico do bot, o retry deverá reconhecer a
resposta e não repetir o envio.

Duplicidade frequente, determinística ou ocorrida depois de a resposta do bot já
estar persistida é bug. Duplicidade excepcional na janela externa entre Meta e
banco é um trade-off conhecido e aceito na V1.

O Funil possui uma janela externa equivalente:

```text
Funil confirmou a oportunidade
        -> banco caiu antes de marcar lead_no_funil
        -> lease expirou
        -> retry pode criar outra oportunidade
```

O estado local `processing` e o snapshot persistido tornam o caso rastreável, mas
não existe exatamente uma vez sem consulta de reconciliação suportada pelo CRM.

## 15. O que é bug na V1

São bugs, entre outros:

- a primeira ou única mensagem válida do turno ser ignorada sem uma regra
  aplicável;
- uma mensagem aceita desaparecer antes de concluir a política prevista de
  tentativas;
- o bot enviar novamente quando a resposta atual já estiver persistida;
- `last_message_from` permanecer como `cliente` quando a resposta atual do bot já
  estiver persistida, ou como `bot` quando ainda não existir resposta persistida;
- uma etapa mudar sem a aresta `origem + evento -> destino` autorizada;
- duas mensagens do mesmo turno avançarem a conversa como se fossem turnos
  independentes;
- uma mensagem posterior ultrapassar outra anterior ainda aberta na conversa;
- uma falha prevista encerrar permanentemente o worker sem tentativa de
  recuperação.

## 16. O que não é bug na V1

Não são bugs:

- ignorar qualquer segunda mensagem quando a primeira mensagem do mesmo cliente e
  unidade ainda estiver aberta e sem resposta própria do bot;
- ignorar a repetição do mesmo webhook ou `id_hash_msg`;
- reutilizar histórico existente durante um retry;
- responder a uma mídia com orientação sem avançar etapa já apresentada;
- apresentar a etapa 1 junto com o aviso quando a conversa for iniciada com
  mídia;
- responder pergunta sobre valor sem tratar esse texto como nome ou avanço de
  etapa;
- excluir a mensagem ao atingir a terceira tentativa;
- aguardar os timeouts da fila ou do lock antes de um novo processamento;
- uma duplicidade extremamente rara na janela entre Meta e commit do bot;
- rejeitar payload grande ou assinatura inválida sem bloquear o número informado
  na Meta.

## 17. Falhas operacionais do webhook e reentrega da Meta

Quando uma mensagem válida chega à transação da fila, mas conexão, inserção ou
commit falham:

- a transação será revertida com rollback;
- o webhook registrará `insert_exception`;
- a resposta será HTTP 503 com `status = 'unavailable'`;
- a Meta poderá tratar a entrega como malsucedida e reenviar o evento;
- a repetição continuará protegida pela unicidade de `id_hash_msg`.

Também é HTTP 503 quando o webhook não consegue validar a unidade porque Redis e
banco estão indisponíveis no mesmo ponto do fluxo. Nesse caso:

- o webhook registrará `unit_validation_unavailable`;
- a mensagem não será tratada como unidade inativa;
- a Meta poderá reenviar o evento quando o endpoint voltar a responder com
  sucesso.

Esse HTTP 503 é reservado para falhas operacionais que impedem o sistema de
decidir ou persistir uma mensagem válida com segurança. Mensagens descartadas
intencionalmente por turno aberto, duplicidade, flood, unidade inativa, conversa
bloqueada ou payload sem mensagem processável continuam seguindo seus contratos
de `ignored` e não devem ser transformadas em indisponibilidade.

O retry da Meta protege a chegada ao webhook e não substitui o retry interno do
worker. Depois que a fila foi persistida e o webhook respondeu HTTP 200, qualquer
falha de processamento ou envio da resposta pertence à política de tentativas do
worker.

## 18. Cache, fallback e autocura

Tabelas e consultas de baixa volatilidade ou alta frequência devem priorizar
Redis e possuir fallback para a fonte de verdade no banco quando o cache estiver
indisponível, inválido ou inconsistente de maneira detectável.

Princípios obrigatórios:

- Redis é um acelerador; o banco continua sendo a fonte de verdade.
- Uma falha do Redis não deverá interromper o fluxo quando houver fallback seguro
  no banco.
- Depois de consultar o banco por fallback, o sistema deverá tentar reparar o
  Redis com os dados atuais.
- Uma falha na tentativa de reparo do cache não deverá apagar dados válidos do
  banco.
- Quando um valor stale causar erro de integridade, ele deverá ser removido ou o
  cache completo deverá ser recarregado para que o próximo retry consulte o banco
  e se recupere.
- Operações administrativas que exijam banco e cache coerentes deverão ser
  bloqueadas se o Redis não puder ser validado ou atualizado.

### 18.1. Cache de unidades

- Utiliza hash Redis, quantidade esperada e versão mantida em
  `chatbot.cache_controle`.
- Webhook e worker conferem periodicamente a versão do Redis contra a versão do
  banco e recarregam o cache quando encontram divergência.
- O Django Admin incrementa a versão e recria o cache depois de salvar ou excluir
  uma unidade.
- Se o Redis falhar, webhook e worker utilizam fallback no banco e tentam
  recarregar o cache.
- Se um `id_unidade` stale causar violação de FK no worker, o cache de unidades é
  recarregado antes do retry.

### 18.2. Cache de clientes

- Relaciona `wa_id` ao `id_cliente` e possui TTL.
- Miss, valor inválido ou Redis indisponível levam a consulta ao banco.
- Um cliente criado ou encontrado no banco será salvo no cache somente depois do
  commit que confirmar sua existência.
- Se um `id_cliente` stale causar violação de FK, a chave será removida para que o
  retry reconstrua o valor correto pelo banco.

### 18.3. Cache de conversas bloqueadas

- O bloqueio de 30 dias utiliza Redis com TTL calculado a partir de
  `finalizou_em`.
- Quando o Redis falha, o banco é consultado e o cache é criado ou removido para
  refletir o resultado persistido.
- Quando o worker encontra uma conversa bloqueada que ainda não estava no cache,
  ele registra a chave com o TTL restante e remove a mensagem da fila.
- Depois de expirado o período, a chave não deverá mais bloquear o cliente.
- Esse cache possui mecanismo próprio de reparo e não deverá ser incluído nos
  reparos de FK de cliente e unidade do `flow_worker.py`.

### 18.4. Escopo da autocura

- A autocura cobre falhas detectadas, versão divergente de unidades e erros FK
  de cliente ou unidade.
- Em produção, alterações manuais diretamente no banco são proibidas. Dados que
  afetam cache devem ser modificados pelos fluxos oficiais da aplicação ou pelo
  Django Admin.
- Edições manuais no banco são permitidas somente em desenvolvimento. Nesse
  ambiente, atrasos de sincronização poderão ser corrigidos pelo reset de cache
  destinado a DEV.
- O sistema não precisa comparar banco e Redis em toda leitura para detectar uma
  edição manual que viole o contrato de produção.

Dentro desse contrato, a autocura implementada atende às regras da V1. Suporte a
edições manuais silenciosas em produção não é requisito.

Implementação principal:

- `core/cache/cache_unidade.py`
- `core/cache/runtime/cache_cliente.py`
- `core/cache/runtime/cache_conversas_bloqueadas.py`
- `core/repositories/unidades/cache_control.py`
- `workers/worker_flow/suporte/cache_repair.py`

## 19. Regras do Django Admin

O Django Admin é uma superfície operacional controlada, e não uma forma livre de
editar as tabelas do fluxo.

### 19.1. Tabelas somente para visualização

Cliente, dependente, etapa, conversa, fila, histórico, respostas de desafio,
eventos de flood e controle de cache utilizam administração somente leitura:

- não permitem adicionar;
- não permitem alterar;
- não permitem excluir;
- exibem os campos somente para consulta operacional.

### 19.2. Clientes bloqueados na Meta

- `cliente_bloqueado_meta` representa a intenção persistente de bloquear o par
  `wa_id_cliente + phone_id_unidade`, além dos bloqueios já confirmados pela
  Meta.
- Um contato identificado manualmente pode ser registrado nessa tabela mesmo
  quando a janela da Meta ainda não permite confirmar o bloqueio.
- Toda nova mensagem desse par é interceptada antes do flood, da validação da
  unidade e da fila.
- O webhook tenta bloquear novamente na Meta e sempre ignora a mensagem, tanto
  no sucesso quanto na falha. Uma mensagem futura provoca uma nova tentativa.
- Falha ao consultar a lista retorna HTTP 503 para a Meta reenviar o evento;
  nenhuma mensagem é enfileirada sem que essa validação seja concluída.
- A consulta sempre inclui `wa_id_cliente` e `phone_id_unidade`, preservando o
  isolamento multi-WABA.
- Bloqueios automáticos detectados pelo sistema registram e confirmam primeiro
  a intenção local no banco; somente depois do commit tentam o bloqueio na
  Meta, sem manter transação aberta durante a chamada externa.
- Se a Meta recusar o bloqueio, a linha local permanece autoritativa: a
  mensagem atual é ignorada e uma mensagem futura provoca nova tentativa.
- Se a intenção local não puder ser persistida por indisponibilidade do banco,
  o webhook não chama a Meta, não enfileira a mensagem e retorna HTTP 503 para
  permitir reentrega.
- O Django Admin continua sem permitir a criação livre de registros enquanto
  não existir uma interface específica para classificar bots manualmente.
- O administrador poderá somente desbloquear, removendo individualmente um
  registro existente.
- Desbloqueio em massa é proibido.
- No desbloqueio, a ordem obrigatória é Meta primeiro, banco depois.
- Se o desbloqueio na Meta falhar, o registro deverá permanecer no banco.
- Não existe chave Redis equivalente: a própria tabela é consultada de forma
  autoritativa pelo webhook.

### 19.3. Unidades

- Cada unidade possui um `waba_id` único e obrigatório e um
  `phone_number_id` único e obrigatório.
- A criação valida primeiro, pela Graph API, se o `phone_number_id` pertence
  ao `waba_id` informado.
- Depois da validação, o App assina a WABA e registra o número na Meta.
- Se a Meta falhar, a unidade não será criada no banco.
- Antes da alteração no banco, o Redis deverá passar pelo preflight.
- Depois do save, a versão das unidades será incrementada e o cache recarregado.
- A exclusão desassina a WABA e desregistra o número na Meta antes de remover
  a unidade do banco.
- Se a Meta falhar durante a exclusão, a unidade permanecerá no banco.
- Se o Redis falhar depois de a Meta responder, o banco deverá permanecer sem
  alteração e o administrador deverá receber uma mensagem para tentar novamente.
- Exclusão em massa de unidades é proibida.
- `idade_minima_suporte` e `email_obrigatorio` são editáveis no Admin; a ativação do
  suporte exige um número comercial válido. `waba_id` e `phone_number_id` ficam
  somente leitura depois da criação.

### 19.4. Papel de `status_pagamento`

`status_pagamento` não representa vinculação ou desvinculação do número no WABA.

- O campo é o controle atual de admissão da unidade: somente registros com
  `status_pagamento = TRUE` entram no cache de unidades ativas e são localizados
  pelo webhook e worker.
- Uma futura tabela `payment` poderá automatizar essa decisão, mas ela não faz
  parte da V1.
- Na V1, pagamentos e contratos poderão ser controlados manualmente, contrato por
  contrato.
- Alterar `status_pagamento` deverá atualizar banco e cache de unidades, mas não
  deverá registrar ou remover o número na Meta.

O fato de uma edição de `status_pagamento` não chamar a Meta é comportamento esperado,
e não uma lacuna.

### 19.5. Desvinculação definitiva de uma unidade

Para encerrar o vínculo de uma unidade com o sistema:

1. solicitar a exclusão individualmente pelo Django Admin;
2. o sistema remove a assinatura do App na WABA;
3. o sistema desregistra o `phone_number_id`;
4. somente após as duas confirmações Meta conclui a exclusão no banco e
   atualiza o cache de unidades.

A exclusão administrativa continua protegida pela validação Meta-first do código
e pelo preflight do Redis. A exclusão em massa permanece proibida.

Implementação principal:

- `callback/webhook/admin.py`
- `core/integrations/whatsapp/tools/validando_phone_waba.py`
- `core/integrations/whatsapp/tools/ativando_waba_id.py`
- `core/integrations/whatsapp/tools/desativa_waba_id.py`
- `core/integrations/whatsapp/tools/ativando_numero.py`
- `core/integrations/whatsapp/tools/desativando_numero.py`

### 19.6. Contas de monitoramento por unidade

- `chatbot.unidade.id_usuario_monitoramento` referencia `chatbot.auth_user.id`.
  O vínculo é opcional e único: cada usuário pode monitorar no máximo uma
  unidade e cada unidade pode possuir no máximo uma conta de monitoramento.
  Várias unidades podem manter o campo `NULL`, sem acesso de monitoramento.
- Login, hash da senha e ativação da conta pertencem à autenticação do Django;
  a unidade armazena somente a referência. No Admin, crie a conta em **Usuários**
  e selecione-a no campo **Usuário de monitoramento** do cadastro da unidade.
- Contas de monitoramento não possuem `is_staff` nem `is_superuser`. O formulário
  recusa contas administrativas e a autorização também confere esses estados
  diretamente no banco, além de `is_active`.
- A identidade vem de `request.user`; usuário/unidade informados pelo navegador
  não definem o escopo. Sem sessão válida, vínculo ou conta habilitada, o acesso
  é negado. Erro de banco não autoriza leitura.
- Conversas são autorizadas por `conversa.id_unidade`; mensagens, pela unidade
  de sua conversa. O cadastro global de cliente não concede acesso às conversas
  dele em outras unidades. Se conversa e mensagem forem informadas juntas, a
  mensagem deve pertencer àquela conversa.
- O vínculo é consultado a cada requisição, sem cache nem bypass administrativo.
  Remover o vínculo, desativar a conta ou mudar sua unidade afeta a próxima
  consulta. `status_pagamento` continua com sua finalidade de admissão do bot;
  não é um novo bloqueio do monitoramento.
- Excluir um usuário limpa a referência por `ON DELETE SET NULL`, preservando
  a unidade, suas conversas e seu histórico. Excluir a unidade pelo fluxo
  administrativo existente não exclui a conta Django. Limpar somente o campo
  de monitoramento revoga o acesso sem excluir entidades.
- O login usa o par `username`/senha da mesma conta e o verificador de hash
  nativo do Django. Antes de criar a sessão, exige conta habilitada, comum e
  vinculada a uma unidade. Usuário inexistente e senha incorreta recebem o
  mesmo aviso. Não há cadastro, recuperação/troca de senha ou bloqueio após
  três tentativas no portal; o proprietário administra as contas pelo Admin.
- Login e logout usam CSRF; logout somente por POST. O destino após autenticar
  é fixo, sem aceitar redirecionamento escolhido pelo navegador. A senha fica
  mascarada e não volta preenchida após erro. Falhas de banco não liberam acesso.
- O acesso bem-sucedido abre o painel em `/`. A página e todas as rotas de dados
  usam `exigir_acesso_monitoramento` e mantêm cada SELECT limitado à unidade
  retornada. A autorização não filtra automaticamente outros SQLs ou QuerySets.
- O painel é somente leitura. Suas rotas de dados aceitam apenas GET; não há
  envio de mensagens, cadastro, edição nem exclusão de informações.
- O período padrão cobre a primeira mensagem de cliente registrada na unidade
  até o instante da consulta. Também são aceitas janelas de 24 horas, 7 e 30
  dias, 2, 3 e 6 meses e 1 ano. Uma janela finita compara seus indicadores com
  a janela imediatamente anterior de igual duração.
- Conversas técnicas do mesmo cliente são consolidadas somente dentro da unidade
  autorizada. Os filtros locais são Todas, Comercial, Follow-up, Funil e Avaliadas; os
  perfis visuais são Menor de 18, Adulto, 60+ e Dependente. Na lista de
  conversas, as etiquetas ao lado da data preservam a relação entre faixa
  etária e destino nas formas abreviadas DP -18, DP 18–59, DP 60+, 18–59 e
  60+; a descrição completa permanece disponível como informação acessível.
- O navegador consulta conversas a cada 10 segundos e relatórios a cada 30
  segundos quando a página está visível. Voltar à aba força uma leitura. Esse
  polling usa o mesmo serviço Django/Gunicorn do webhook e não cria worker ou
  serviço systemd adicional.
- As opções `idade_minima_suporte`, `email_obrigatorio` e `bpa_ativo` são lidas
  da unidade. O limite é apresentado como política; não modifica tags 18–59/60+
  ou de dependentes nem esconde envios ao Funil registrados em qualquer faixa.
- Comercial mostra somente chats cuja última conversa real na unidade encerrou
  por idade. Uma conversa nova remove a tag, mesmo fora do período consultado;
  a configuração atual não altera uma tag histórica. A legenda explica cada filtro.
- Relatórios possui a tabela Encaminhamentos e encerramentos por idade abaixo
  dos quatro KPIs. Conta conversas (não contatos), por `finalizou_em >= início`
  e `< fim`, mesmo que exista atendimento posterior. Mostra suporte do limite
  atual, universal 90+ separada por titular/dependente, titular menor e dependente
  abaixo do mínimo BPA atual. Configurações diferentes e legados sem limite
  identificável ficam fora. Reescolher a mesma configuração inclui motivos iguais
  no período, independentemente da data dessa reconfiguração.
  Distingue contato enviado de encerramento sem contato; não comprova clique,
  atendimento humano, matrícula ou envio ao Funil. Falha de consulta não é zero.
- O relatório mostra métricas, comparação, demanda ao longo do tempo, perfis,
  satisfação e a etapa atual da conversa mais recente de cada contato que teve
  atividade no período. Cada contato conta uma vez. A etapa é um retrato atual;
  o banco não permite reconstruir em qual etapa a conversa estava em uma data
  passada.
- O histórico armazena texto e tipo da mensagem, mas não o payload exato dos
  botões enviados. Para mensagens interativas, o painel mostra os botões do
  catálogo atual daquela etapa como referência visual, sempre desabilitados.
- Os quatro indicadores agregados ficam na seção Relatórios. A seção Conversas
  prioriza a visualização da lista e do histórico, mantendo filtros e período.
- O CSV completo inclui todos os contatos ativos no período e deixa campos
  ausentes vazios. O CSV elegível exige nome, e-mail estruturalmente válido e
  telefone normalizado. Ambos usam
  cabeçalhos compatíveis com importação no Google Contatos e nunca alteram o
  banco.
- Há também duas exportações de dados essenciais, para todos os contatos ou
  apenas elegíveis, com somente Nome, E-mail e Telefone. Mantêm o nome completo
  em uma coluna, sem acrescentar rótulos ou datas, e reutilizam as mesmas regras
  de período, unidade, normalização e elegibilidade dos arquivos Google CSV.
  Somente nesses dois CSVs essenciais, o telefone brasileiro é exibido sem o
  prefixo internacional `+55`, preservando o DDD e o número.

## 20. Disponibilidade e recuperação automática

“O sistema não deve cair nunca” é um requisito de resiliência operacional e
recuperação automática. Isso não significa afirmar que o interpretador Python, a
máquina ou a rede jamais poderão falhar.

Sempre deverá existir uma camada capaz de conter a falha e manter ou restaurar o
serviço:

- falha do Redis utiliza fallback quando existe uma fonte segura no banco;
- falha de uma mensagem não encerra o processamento das demais;
- o worker captura falhas, preserva ou reagenda o estado quando possível e
  continua o loop;
- o worker do Funil isola erros por lead e reinicia falhas globais com espera
  linear de 5 a 60 segundos;
- o worker de follow-up isola erros por candidata e usa espera exponencial de
  5 até 300 segundos quando a consulta do lote falha;
- `flow_worker.py` mantém o loop de consumo e os tratamentos por tipo de exceção;
- se `worker_flow()` escapar com uma exceção, `iniciar_flow_worker.py` registra a falha,
  aguarda 5 segundos e inicia outro loop;
- o webhook responde de maneira controlada a entradas inválidas e falhas
  conhecidas;
- chamadas externas à Meta falham de forma controlada, sem confirmar no banco
  uma operação recusada pela Meta;
- caches degradam para fallback ou negam uma operação administrativa que
  produziria inconsistência.

Na produção atual, webhook, worker de atendimento, worker do Funil e worker de
follow-up são quatro serviços systemd independentes. Os três primeiros usam
`Restart=always`; follow-up usa `Restart=on-failure`. Todos têm `RestartSec=5s`.
As camadas de recuperação são complementares:

```text
operação individual falha
    -> exception ou fallback trata
    -> flow_worker continua
    -> iniciar_flow_worker reinicia o fluxo se ele escapar
    -> systemd reinicia o processo se ele encerrar
```

A URL pública e os serviços de produção devem permanecer disponíveis 24x7.
Falhas previstas não poderão produzir encerramento permanente do serviço nem
corrupção silenciosa. Os loops e fallbacks da aplicação atuam antes da supervisão
dos processos pelo sistema operacional.

Implementação principal:

- `workers/worker_flow/iniciar_flow_worker.py`
- `workers/worker_flow/response_flow/flow_worker.py`
- `workers/worker_funil/funil_worker.py`
- `workers/worker_funil/iniciar_worker_funil.py`
- `core/cache/redis_client.py`
- `callback/webhook/services/post_flow.py`
- `deploy/systemd/chatbot-webhook.service`
- `deploy/systemd/chatbot-worker-flow.service`
- `deploy/systemd/chatbot-worker-funil.service`
- `workers/worker_followup/iniciar_worker_followup.py`
- `workers/worker_followup/followup_worker.py`
- `deploy/systemd/chatbot-worker-followup.service`

## 21. Matriz de aderência conferida no código

| Regra | Estado atual | Observação |
|---|---|---|
| Somente a primeira mensagem sem resposta do turno é válida | Implementada | As demais não entram na fila nem no histórico enquanto existir uma fila aberta sem resposta própria do bot. |
| Liberar o próximo turno por resposta específica do bot | Implementada | O histórico vinculado à fila permite recuperação antes de `fila.status='sent'`, sem liberar uma sequência ilimitada. |
| Bloqueio de 30 dias depois da etapa final | Implementada | Banco e cache utilizam janela ou TTL de 30 dias. |
| Flood acima da métrica | Implementada | Redis, banco e memória formam a cadeia de avaliação; flood pode bloquear na Meta. |
| Payload grande | Implementada conforme a regra | Retorna HTTP 413 e não bloqueia a identidade informada no payload. |
| Assinatura inválida | Implementada conforme a regra | Retorna HTTP 403 e não confia no payload nem bloqueia possível vítima informada nele. |
| Falha operacional do webhook com mensagem válida | Implementada | Inserção/commit da fila e validação de unidade indisponível retornam HTTP 503 para permitir reentrega; descartes de negócio continuam HTTP 200. |
| Cache Redis com fallback para banco | Implementada nos caches principais | Unidades, clientes e conversas bloqueadas possuem estratégias de fallback. |
| Autocura Redis/banco | Implementada no contrato da V1 | Cobre falhas detectáveis e FK stale; edição direta no banco é proibida em produção. |
| Admin majoritariamente somente leitura | Implementada | As exceções operacionais são unidade (incluindo seu usuário de monitoramento), integração com o Funil e desbloqueio individual. |
| Admin somente desbloqueia clientes | Implementada | Meta primeiro; falha preserva o registro no banco. |
| Unidade Meta-first na criação e exclusão | Implementada | Falha da Meta impede a alteração do banco. |
| `status_pagamento` sem chamada Meta | Implementada conforme a regra | O valor controla a admissão da unidade, mas não registra nem remove o número na Meta. |
| Desvinculação definitiva da unidade | Definida operacionalmente | Remover do WABA oficial e excluir individualmente pelo Admin. |
| Worker continua ou reinicia depois de falha | Implementada em camadas | `funil_worker.py` recupera banco e agenda os ciclos; `iniciar_worker_funil.py` recria o worker após falha crítica. `iniciar_flow_worker.py` mantém a supervisão do atendimento. |
| Conversa elegível vira oportunidade no Funil | Implementada e desativada por padrão | Etapas 18–22, `funil_envios`, claim com lease e confirmação lógica da ApiCarrossel. |
| Uma falha de lead não interrompe o lote do Funil | Implementada | O item volta para `pending`; os demais continuam no mesmo ciclo. |
| Follow-up antes do agendamento | Implementada | Primeiro lembrete após 7h; despedida e encerramento após outras 7h sem resposta, nas etapas 1–17, inclusive 8, dentro da janela do cliente. Retorno antes do encerramento valida a resposta; depois, abre nova conversa. |
| Supervisão dos quatro processos | Implementada | Webhook, flow e Funil usam `Restart=always`; follow-up usa `Restart=on-failure`. Nginx encaminha o endpoint público ao webhook. |

## 22. Orientação para futuras alterações

Antes de modificar o fluxo:

1. identificar qual regra deste documento está envolvida;
2. classificar a mudança como correção, refatoração ou alteração de produto;
3. preservar turno único, idempotência e limite de tentativas quando a tarefa não
   solicitar explicitamente o contrário;
4. mapear quedas antes e depois de cada commit;
5. testar fluxo normal, retry antes do bot, retry depois do bot e finalização da
   fila;
6. não tratar um comportamento esperado da V1 como bug apenas por ele parecer
   conservador ou incompleto.

## Follow-up de inatividade e reação do cliente

Implementado na V1.2.0. As instruções de operação vivem nos
[workers](workers/README.md#worker-de-follow-up) e no
[deploy](deploy/README.md#ativação-do-follow-up); não dependem dos planos de implementação.

O worker proativo envia o lembrete definido em `messages/followup_messages.py`
depois de sete horas sem reação à última resposta comum confirmada do bot.
NULL equivale a stage zero.
O envio exige conversa ativa em etapa 1–17, unidade válida e adimplente, ausência
de bloqueios, de entrada posterior no histórico e de fila pending/processing do
mesmo par cliente/unidade, mesmo se ainda não vinculada à conversa. Uma fila
respondida mas ainda aberta também adia o proativo até sua finalização.

O canal exige janela aberta desde a última mensagem do cliente; este envio em texto
livre não usa template. A implementação reserva um minuto antes de completar 24h
para evitar despacho na borda. Isso não altera o limiar de sete horas do bot.

São dois relógios distintos: a última mensagem de toda a conversa precisa ser
do bot há pelo menos sete horas, e a mensagem mais recente do cliente, anterior
a ela, precisa estar dentro de 23h59. Bot há oito horas com cliente há 25 horas
é inelegível; bot há oito horas com cliente há nove horas pode ser elegível.

O worker produz 0 → 1 no primeiro envio. Após outras sete horas sem resposta,
contadas do primeiro envio confirmado, produz 1 → 2 com a despedida e encerra a
conversa (`status_ativa = false`, `finalizou_em` e motivo `followup_sem_resposta`).
Mantém a etapa de origem, sem aplicar o bloqueio de 30 dias. Não há terceiro envio.
Histórico, recibo, stage 2 e encerramento são gravados na mesma transação, somente
após confirmação da Meta. Falha no envio mantém a conversa aberta em stage 1.
Se a janela de 23h59 já expirou, não envia nem simula encerramento.

O segundo envio exige recibo real do primeiro, correspondente ao último bot e ao
`followup_last_sent_at`; marcação de legado sem recibo não permite uma despedida.
As duas camadas são restritas às etapas 1–17, incluindo a 8. Uma reação antes do
segundo envio cancela sua elegibilidade e mantém o processamento descrito abaixo.
Depois do encerramento, outra mensagem abre novo ID de conversa, com stage zero
e mensagem inicial da etapa 1, sem prefixo de retorno nem nome de cadastro antigo.

O filtro **Follow-up** do painel considera stage 1 ou 2 da conversa mais recente
do mesmo cliente/unidade. Uma conversa posterior invalida o marcador antigo,
inclusive se estiver fora do período selecionado. O chat continua reunindo todo
o histórico permitido pelo período; excluir do filtro não apaga atendimento.

A primeira entrada aceita com stage positivo em conversa ainda ativa é armazenada e validada pelos
mesmos resolvers do atendimento normal. Respeitar as prioridades de cada etapa:
tratamentos específicos existentes (mídia, financeiro e reforço) permanecem;
resposta válida segue seu evento, efeitos e destino; resposta sem validação nem
tratamento específico reapresenta a pergunta neutra, sem reprimenda de contexto.
A triagem mantém apenas suas opções canônicas, sem ganhar tratamentos novos.

A resposta começa com `Bom te ver novamente, <nome> ☺️` ou a forma sem nome
`Bom te ver novamente ☺️`. Na etapa 1, nunca usar o nome de atendimento anterior:
um nome válido recebido agora é salvo e avança para a 2; caso contrário, tratar
ou repetir conforme a regra acima. O cadastro antigo não é apagado para saudação.
O prefixo independe do tempo de retorno, aparece uma vez e substitui a saudação
de três horas. No retorno comum por três horas, o processamento continua normal,
inclusive o tratamento de contexto inválido; só a redação do prefixo é igual.

Sem avanço, essa primeira reação não incrementa `turnos_sem_avanco`, inclusive
quando recebe tratamento específico. Uma transição válida zera esse contador
normalmente. A resposta seguinte volta à contagem normal de tratamentos.

**Exceção da etapa 8:** qualquer reação processada com follow-up pendente provoca
`8 → cliente_retornou → 9`, reutilizando o resolver e o mapa do retorno normal.
Não repetir a mensagem da 8, nem criar ou enviar uma variante de repetição.
A oferta da 9 preserva titular/dependente, botões e rodapé e recebe somente a
saudação de follow-up. O conteúdo não é classificado como tratamento ou aceite:
mesmo uma confirmação nessa reação apenas apresenta a 9; a próxima resposta
segue sua validação normal. Não há Funil ou encerramento nessa transição.

O histórico do cliente e o checkpoint conservam a origem 8; a resposta do bot
usa a etapa 9. A transição, o reset de turnos sem avanço do fluxo normal,
o histórico da resposta e a conclusão do follow-up pertencem ao mesmo commit.
Falha reverte esses efeitos juntos. Retry de retomada concluída reutiliza o
destino efetivamente gravado, inclusive uma repetição antiga da 8, sem reenviar,
refazer a transição ou zerar um ciclo posterior. A exceção vale também para
stage positivo legado sem data de envio; a elegibilidade proativa não muda.

A migração inicial marca followup_stage = 1 para todas as conversas ativas antigas,
incluindo etapas 18–21, e registra seus IDs, stages anteriores e a data da marcação
em followup_legado. Não envia lembrete, não encerra conversas, não inventa recibo
nem altera followup_last_sent_at. Stage positivo passa a indicar retomada pendente,
por envio real ou marcação inicial; somente o histórico/recibo comprova envio.
Novas conversas continuam com stage zero. O setup limpo não marca conversas.

Histórico, efeitos normais, marcação da retomada, reset para zero, eventual
encerramento e finalização da fila pertencem ao mesmo commit. followup_last_sent_at permanece como auditoria. Um retry de retomada
concluída usa a resposta já persistida, sem zerar um ciclo posterior. A mensagem
seguinte é interpretada normalmente; outro período de sete horas pode iniciar um
novo ciclo somente nas etapas 1–17 e com as demais condições de envio atendidas.
Stage maior que um em conversa legada ainda ativa segue a mesma recuperação;
stage 2 encerrado pelo novo proativo permanece como auditoria; negativo falha fechado.

A exceção deliberada é a repetição neutra diante de contexto inválido genérico
no primeiro retorno. Stage zero preserva o processamento normal por inteiro.
O registro proativo não possui fila nem hash de cliente de origem e não prova que
uma fila A/B/C foi respondida. Os recibos próprios identificam a conversa e a âncora
do ciclo; registros de retomada identificam a entrada processada para recuperação.

Os dois workers compartilham o lock de 110 segundos e seu fencing. Entrada aceita
após o último teste pré-envio pode cruzar com a chamada da Meta: confirmamos o
envio. No primeiro, o flow lê stage positivo ao obter o lock; no segundo, relê
o estado encerrado e abre outro atendimento, reagendando uma leitura obsoleta sem
consumir retry. A janela entre aceite
externo e commit local continua sujeita à duplicidade rara já aceita na V1.
````

## Passo 26 — Alterar `workers/README.md`

Documentar prioridade das regras, idade da entrada e recuperação compatível.

Base SHA-256: `6f254fdd2c2489979e37defe5b199de559717dc0ee1e20964b020fd5aa890797`. Conteúdo completo proposto: **426 linhas**.

````markdown
# Workers

Camada assíncrona responsável pelo atendimento no WhatsApp, lembretes de
inatividade e publicação periódica de oportunidades no Funil de Vendas.

- [Portal do projeto](../README.md)
- [Regras de negócio](../REGRAS_DE_NEGOCIO.md)
- [Padrões de arquitetura](../PADROES_DE_ARQUITETURA.md)
- [Rotina de implementação de etapas](../ROTINA_IMPLEMENTACAO_ETAPAS.md)

## Estrutura

```text
workers/
├── worker_flow/
│   ├── iniciar_flow_worker.py
│   ├── valida_banco.py
│   ├── valida_historico.py
│   ├── tratar_bloqueio.py
│   ├── response_flow/
│   │   ├── flow_worker.py
│   │   ├── flow_sender.py
│   │   ├── repeticao_followup.py
│   │   ├── etapas/
│   │   │   ├── validadores_universais/
│   │   │   └── validadores_contexto/
│   │   └── transicoes/
│   │       ├── contexto_transicao.py
│   │       ├── eventos.py
│   │       └── resolver_transicao.py
│   ├── transacoes/
│   │   ├── efeitos_transicao.py
│   │   ├── encerramento_atendimento.py
│   │   ├── persistencia_resposta.py
│   │   ├── retorno_followup.py
│   │   ├── movimento_conversa.py
│   │   ├── finalizacao_fila.py
│   │   ├── lock_conversa.py
│   │   └── ordem_turno.py
│   └── suporte/
│       ├── cache_repair.py
│       └── estado_ciclo.py
├── worker_followup/
│   ├── iniciar_worker_followup.py
│   ├── config.py
│   └── followup_worker.py
├── worker_funil/
│   ├── iniciar_worker_funil.py
│   ├── config.py
│   ├── funil_worker.py
│   ├── processamento.py
│   └── exceptions.py
└── tratamento_erros_externos/
```

## Ciclo principal

`worker_flow/iniciar_flow_worker.py` supervisiona o processo. Se
`worker_flow()` escapar com uma exceção, registra o traceback, aguarda e
reinicia o fluxo.

`worker_flow/response_flow/flow_worker.py` é o orquestrador do ciclo:

```text
dequeue
-> respeitar mensagem anterior
-> validar cliente, unidade e conversa
-> barrar conversa com bloqueio vigente
-> adquirir lock
-> vincular fila à conversa
-> reler conversa sob lock e reconhecer retomada de follow-up
-> persistir histórico do cliente
-> validar a reação ao follow-up ou a resposta normal pelo mesmo fluxo
-> persistir histórico/contexto do bot
-> marcar fila como sent
-> liberar lock e fechar conexão
```

## Propriedade transacional

Conexão, `commit`, `rollback` e `close` do ciclo pertencem ao `flow_worker.py`.
Os commits intermediários são checkpoints recuperáveis:

1. claim da fila;
2. espera por mensagem anterior, quando necessária;
3. validação do banco;
4. aquisição do lock;
5. vínculo, releitura e histórico do cliente, incluindo o marcador de retomada quando aplicável;
6. renovação do lock antes do envio;
7. histórico e contexto do bot; na retomada, conclusão do marcador e reset do stage;
8. status `sent`, após conferir novamente a posse do lock;
9. unlock.

Uma função auxiliar pode executar uma operação com o cursor recebido, mas não
deve decidir a transação fora do orquestrador.

### Vínculo da fila com a conversa

O vínculo `fila_mensagens.id_conversa` é uma anotação de integridade e
ordenação; ele não é o lock de turno e não substitui a resolução atual por
`(cliente, unidade)`.

O repositório preenche o vínculo quando ele está vazio ou já aponta para a mesma
conversa. Um vínculo legado divergente só é reparado quando a fila ainda não tem
histórico. Se nenhuma linha puder ser vinculada com segurança, o worker falha
fechado: devolve a mensagem para `pending` por 300 segundos, sem consumir uma
tentativa de erro e sem enviar resposta.

Se a conversa anterior continuar ativa, a mensagem permanece na mesma conversa
e segue a etapa já atualizada. Se o encerramento tiver bloqueio vigente, a
mensagem é removida como conversa bloqueada. Uma conversa nova só é resolvida
quando o encerramento permite recomeço imediato (`bloqueio_dias = 0`) ou quando
o bloqueio já expirou.

As barreiras que continuam decidindo o atendimento são:

- advisory lock do turno por cliente e unidade no webhook;
- lock versionado da conversa no worker;
- verificação de mensagem anterior ainda aberta;
- `resposta_bot_para_mensagem_atual`, que impede novo envio em um retry.

## Retry e recuperação

- dequeue incrementa `retry_count`;
- `processing` abandonado volta a ser elegível após o timeout do banco;
- falhas tratadas usam `tratamento_erros_externos/expection_process.py`;
- o limite atual é de três tentativas;
- ao atingir o limite, a mensagem é excluída;
- retry com histórico do bot existente não chama a Meta novamente.

O worker mantém a fila sem `sent` quando envio ou persistência final falham.
Depois de uma resposta do bot persistida, o retry repara contexto e conclui a
fila sem duplicar o envio.

## Locks e ordenação

- apenas um worker processa a conversa por vez;
- `lock_version` impede unlock por proprietário antigo;
- uma mensagem posterior não ultrapassa outra anterior aberta;
- a verificação de mensagem anterior ocorre logo depois do claim, antes de
  resolver conversa e tentar seu lock;
- espera por mensagem anterior (30 segundos) ou lock recusado (5 segundos) não
  consome tentativa de erro.

## Response flow

- `flow_worker.py`: transação, checkpoints e handlers.
- `retomada_followup.py`: valida a reação com o fluxo normal e a saudação de retorno;
- `repeticao_followup.py`: repetição neutra para contexto inválido no retorno,
  compatibilidade da etapa 8 e recuperação da resposta existente;
- `flow_sender.py`: preserva `resposta_bot_atual` e seleciona o resolver da
  etapa atual;
- `etapas/resolver_etapa<n>.py`: valida a resposta, aplica tratamentos e
  encaminha para o destino autorizado;
- `etapas/validadores_universais/`: mídia, financeiro, nome, opções da triagem
  e outras validações reutilizáveis;
- `etapas/validadores_contexto/`: respostas específicas de cada pergunta;
- `transicoes/contexto_transicao.py`: transforma o resultado da consulta em
  origem e mapa explícitos no contexto histórico;
- `transicoes/resolver_transicao.py`: decide `origem + evento -> destino`.

Textos e chamadas PyWa não pertencem a essa pasta. Use
`core/integrations/whatsapp/messages` e
`core/integrations/whatsapp/pywa_functions/pywa_senders`.

Tratamentos não produzem evento e permanecem na etapa atual. Respostas válidas
utilizam a tabela `chatbot.etapa_transicao`; o destino não é calculado com
`id_etapa + 1`.

Validadores universais mantêm o mesmo significado em todas as etapas e não
escolhem entre arestas diferentes. Quando uma resposta pode gerar destinos
distintos, o validador é contextual e devolve diretamente o evento daquela
origem, mesmo que outra etapa reconheça os mesmos textos com eventos próprios.

### Regras atuais das etapas

- Etapa 4: profissão válida é persistida em `conversa.profissao` e atualiza
  também `cliente.profissao`. O snapshot da conversa preserva o atendimento
  anterior quando o cadastro do cliente muda.
- Etapa 6: suporte NULL/50/60/70/80, exclusivo do titular até 89. Universal 90+
  prioritária em ambas as rotas. Menores de 18 e dependentes abaixo de 4 com BPA
  ou 5 sem BPA encerram sem contato. Todos esses casos ficam fora do Funil e
  sem bloqueio. O contexto conserva a categoria e o limite usados no envio.
  A recuperação reconhece a resposta da entrada em retry antes de decidir a
  categoria e valida a idade daquela entrada, nunca a idade global. Se necessário,
  reconstrói suporte compatível com a idade; mínimo BPA vem do corpo enviado.
  Não recalcula um motivo já confirmado e não altera commits ou idempotência.
  O validador numérico mantém o contrato 100+ para replay de avanços antigos.
- Etapa 7: confirmações de aceite geram `oferta_aceita` (`7 -> 10`);
  `Talvez mais tarde` gera `oferta_adiada` (`7 -> 8`). Pedidos como
  `quero mais informações` ou `quero saber mais` não são aceite; assim como
  negativas livres, recebem tratamento sem avançar.
- Etapa 10: a política parte de `email_obrigatorio` da unidade, mas o próprio
  titular de 60 a 99 anos fica dispensado quando chega a essa etapa. A exceção
  não se aplica ao dependente nem à idade do responsável. Mídia, reforço e
  financeiro são tratados antes da coleta. Com e-mail opcional, a resposta
  pode avançar como endereço válido, ausência declarada ou não informado;
  os três casos usam `email_valido` (`10 -> 11`). Sem endereço, o efeito grava
  `cliente.email = NULL`, sem manter um e-mail de atendimento anterior.
- Etapa 11: `Começar triagem`, o callback do botão e confirmações textuais como
  `iniciar triagem`, `sim` e `vamos começar` autorizam o início. A classificação
  permanece no validador contextual da etapa, após os tratamentos universais.

No retry já respondido da etapa 10, o resultado aceito do e-mail é reconstruído
pelo histórico original, sem nova chamada à Meta nem reavaliação pela política
de e-mail atual da unidade.

No encaminhamento por idade da etapa 6, o histórico comprova a resposta já
enviada, e a reavaliação do encerramento usa o limite atual da unidade. Se esse
limite estiver desativado ou não abranger mais a idade do titular, a recuperação
não encerra por suporte, não reenvia a resposta nem avança automaticamente a
etapa. O limite anterior não é restaurado e o histórico original é preservado.

### Saudação de retorno

No caminho normal com `followup_stage = 0`, após a etapa 1,
`valida_historico.py` compara o horário da mensagem atual do
cliente com o último envio do bot confirmado como `sent` na mesma conversa.
Com intervalo de pelo menos três horas e nome disponível, `flow_sender.py`
prefixa a resposta com `Bom te ver novamente, <nome> ☺️`, inclusive quando ela é um
tratamento. O texto enviado e o histórico recebem o mesmo prefixo uma vez.

Essa saudação não é follow-up nem disparo por inatividade: depende de uma nova
mensagem do cliente, não cria mensagem separada e não altera a transição. A
etapa 1, dados de nome/data ausentes ou incompatíveis e retries com resposta
persistida não geram uma nova saudação.

## Persistência de transições

As responsabilidades estão divididas assim:

- `transacoes/persistencia_resposta.py`: orquestra a persistência final;
- `transacoes/movimento_conversa.py`: classifica e persiste inicialização,
  transição ou permanência;
- `transacoes/efeitos_transicao.py`: exibe cada ponte como
  `origem + evento -> destino` e grava seus efeitos específicos;
- `transacoes/encerramento_atendimento.py`: resolve e aplica encerramentos,
  inclusive a reconstrução do encaminhamento ao suporte no retry.

Fluxo:

```text
histórico do bot
-> movimento da conversa e confirmação da aresta no PostgreSQL
-> efeitos específicos da transição
```

O `flow_worker.py` continua dono do commit e rollback. Os repositórios recebem o
cursor e não controlam a transação.

## Worker do Funil

`worker_funil` é independente do atendimento. Ele não consome
`fila_mensagens`, não envia WhatsApp e não altera o mapa de transições.

`funil_worker.py` possui o laço operacional interno: executa um ciclo completo,
aguarda `FUNIL_INTERVALO_SEGUNDOS` depois do sucesso (padrão: 1.800 segundos,
30 minutos) e recupera indisponibilidade esperada do
banco com espera linear de 5 em 5 segundos, limitada a 60. O arquivo
`iniciar_worker_funil.py` possui o laço supervisor externo. Se uma falha crítica
escapar do worker, ele aguarda 5 segundos fixos e cria o worker novamente.

```text
materializar conversas em etapas elegíveis
-> claim de um funil_envios com FOR UPDATE SKIP LOCKED
-> commit da reserva
-> montar snapshot do cliente/dependente/triagem
-> encerrar a transação de leitura
-> criar uma oportunidade na ApiCarrossel
-> marcar lead_no_funil e funil_envios=sent no mesmo commit local
-> repetir até o limite do lote
-> aguardar FUNIL_INTERVALO_SEGUNDOS
```

Cada lead é isolado. Falha de payload ou API volta o item para `pending`, agenda
a próxima tentativa e permite processar os demais. Indisponibilidade operacional
do banco é recuperada pelo laço interno; defeitos críticos escapam para o
supervisor externo.

O claim possui lease: um item abandonado em `processing` volta a ser elegível
depois de `FUNIL_LEASE_SEGUNDOS`. Isso permite recuperação de processo morto e
protege múltiplas instâncias com `SKIP LOCKED`.

Não existe transação distribuída entre PostgreSQL e Funil. Se o CRM confirmar e
o banco cair antes do commit local, o item permanece `processing` e poderá ser
reenviado após o lease. O título atual é `Chatbot Lead <nome_unidade>` e não
contém o ID da conversa; ele não identifica sozinho um envio nem impede
duplicidade externa. Não há reconciliação automática com o CRM.

O processo nasce desativado. `FUNIL_WORKER_ENABLED=True` deve ser configurado
somente depois do teste manual da unidade. O ponto de entrada é
`python -m workers.worker_funil.iniciar_worker_funil`; o serviço de produção
está em
[`deploy/systemd/chatbot-worker-funil.service`](../deploy/systemd/chatbot-worker-funil.service).

## Testes relacionados

- `tests/unit/test_worker_flow_runtime.py`;
- `tests/unit/test_persistencia_essencial.py`;
- `tests/unit/test_retry_essencial.py`;
- `tests/unit/test_fluxo_turno_abc.py`;
- `tests/unit/test_suporte_idoso_email_obrigatorio.py`;
- `tests/unit/test_saudacao_retorno.py`;
- `tests/unit/test_validador_profissao.py`;
- `tests/unit/test_valida_etapa7.py`;
- `tests/unit/test_sondas_funil.py`;
- `tests/unit/test_followup.py`;
- `tests/integration/test_followup_postgres.py`.

O núcleo transacional e os testes específicos estão descritos em
[`tests/README.md`](../tests/README.md).

## Worker de follow-up

`worker_followup/iniciar_worker_followup.py` é o quarto serviço da VM. Seu laço
seleciona candidatos pelo PostgreSQL e chama `followup_worker.py`, proprietário
da conexão e dos commits proativos. Não faz dequeue nem chama validadores de etapas.
`FOLLOWUP_WORKER_ENABLED` é falso por padrão em execução manual; a unit systemd
o habilita explicitamente. Lote padrão: 20; intervalo entre lotes: 60 segundos.
As candidatas são processadas uma por vez, com lock e transações independentes.
Somente etapas 1–17 admitem novos lembretes; etapas 18–22 são inelegíveis.
A paginação visita candidatos posteriores mesmo quando os primeiros falham.
Uma falha individual não interrompe o lote. A candidata pode ser tentada novamente
quando a paginação voltar ao início, depois de revalidar todas as condições; não
há promessa de retry no lote imediatamente seguinte ou de reenvio fora da janela Meta.

### Configuração e elegibilidade

| Variável | Padrão no Python | Valores aceitos |
|---|---|---|
| `FOLLOWUP_WORKER_ENABLED` | `False` | Booleano; a unit configura `true`. |
| `FOLLOWUP_POLL_SECONDS` | `60` | 5–3.600 segundos de espera após cada lote. |
| `FOLLOWUP_BATCH_SIZE` | `20` | 1–100 candidatas por lote; processamento sequencial. |

Os dois textos são montados em `messages/followup_messages.py` com os dados da
releitura após o lock. O primeiro convida a continuar o atendimento e receber a
experiência Supera gratuita na unidade, com rodapé `Estaremos te esperando!`.
Usa o nome do titular já informado no atendimento (nunca nome antigo na etapa 1)
e adapta o convite para dependente com nome ou, sem o nome, “receber vocês”.
O segundo é a despedida personalizada, com rodapé `Abraços, {nome_agente}. 🧡`;
sem nome de dependente coletado, mantém a versão do titular.
Para despachar, todas as condições
precisam continuar válidas na releitura após adquirir o lock:

- conversa ativa, sem finalização, em etapa 1–17 não terminal;
- primeiro envio: `followup_stage = 0` (`NULL` equivale a zero); segundo: stage 1
  com recibo do primeiro correspondente ao último bot e ao `followup_last_sent_at`;
- última mensagem da conversa é do bot, confirmada como `sent`, com pelo menos
  sete horas, e `last_interaction_at` corresponde a essa mensagem;
- última mensagem do cliente tem menos de 23h59, reservando um minuto da janela
  de 24 horas; não existe mensagem do cliente com horário igual ou posterior ao bot;
- unidade adimplente, destinatário e números da unidade presentes;
- menos de 12 turnos sem avanço, sem bloqueio persistido ou flood no banco;
- nenhuma fila `pending`/`processing` do par cliente/unidade, inclusive sem vínculo;
- nenhum recibo que já cubra a âncora, nem retomada aberta com fila pendente.
  No segundo, a âncora é o primeiro follow-up, sem encadear um terceiro envio.

Exemplo: bot há 8 horas e cliente há 25 horas não permitem envio; bot há 8 horas
e cliente há 9 horas permitem, se os demais critérios forem atendidos.
O relógio de elegibilidade vem do PostgreSQL. Os limites de etapa e de tempo
são regras do código/SQL, não novas variáveis de ambiente.

O primeiro sucesso persiste histórico, recibo e stage 1 no mesmo commit. Após
outras 7h sem resposta, contadas desse envio, a segunda mensagem persiste histórico,
recibo, stage 2 e encerramento no mesmo commit. Mantém a etapa de origem e não
gera bloqueio de 30 dias. Sem janela de envio, não envia nem encerra silenciosamente.
As duas camadas incluem a etapa 8. Marcações legadas sem recibo não geram despedida.
Uma confirmação da Meta seguida de
falha no commit local ainda pode resultar em duplicidade no retry; o worker
registra `followup_commit_falhou` como crítico.

### Retomada pelo flow

Depois do segundo envio confirmado, o atendimento está encerrado. `valida_banco`
abre nova conversa, sem etapa persistida e com stage zero; o fluxo inicial pede
o nome sem prefixo de retorno. Uma leitura da conversa antiga antes do encerramento
é recusada na releitura sob lock e reagendada sem consumir retry.

No flow, o contexto é relido sob lock. `transacoes/retorno_followup.py` registra
um checkpoint e reutiliza `valida_historico.py` para os dados da etapa, sem
calcular outra saudação de três horas. `retomada_followup.py` chama o `flow_sender`
normal com o prefixo `Bom te ver novamente, <nome> ☺️`. Na etapa 1, omite o nome
antigo; um nome válido na reação é salvo e permite avançar para a 2.

Os resolvers preservam seus validadores e prioridades: resposta válida avança;
mídia, financeiro e reforço recebem os tratamentos já existentes naquela etapa;
contexto inválido genérico usa `repeticao_followup.py` para a pergunta neutra.
A triagem continua aceitando somente as opções canônicas, sem novos tratamentos.
Botões, rodapés e participante são preservados. O prefixo aparece uma vez no
envio e no histórico, inclusive nas mensagens com cabeçalho.

A persistência normal aplica os efeitos, transições e encerramentos cabíveis.
Sem avanço, a primeira reação não incrementa `turnos_sem_avanco`; com transição,
o contador é zerado normalmente. `concluir_retomada` verifica a etapa resultante
e zera `followup_stage`, mantendo `followup_last_sent_at` como auditoria.
Histórico, efeitos, checkpoint, eventual encerramento e fila `sent` são
confirmados **na mesma transação**, sem commit intermediário. Falha reverte todos
esses efeitos. Cache de bloqueio só é publicado após o commit.

Replay de uma resposta já concluída reutiliza seu destino gravado, sem enviar,
reinterpretar a reação, refazer efeitos ou zerar um ciclo posterior. Respostas
da versão antiga continuam recuperáveis, mesmo que tenham repetido a etapa.

Na etapa 8, qualquer reação leva à 9 pelo evento `cliente_retornou`, sem repetir
a 8 nem interpretar a reação como resposta à 9. O histórico do cliente e o
checkpoint mantêm a origem 8; a resposta registra o destino 9.
Stage positivo legado nas etapas 18–21 também usa a validação normal, embora
essas etapas continuem inelegíveis para novos lembretes. A etapa 22 é terminal.

### Operação e logs

`SIGTERM`/`SIGINT` sinalizam parada e interrompem a espera entre lotes; uma
candidata já em andamento passa pela limpeza da conexão e do lock. Falhas de
consulta usam espera exponencial de 5 até 300 segundos. A unit usa
`Restart=on-failure`, `RestartSec=5s` e `TimeoutStopSec=100s`.

`followup_iniciado` informa a configuração. `followup_despacho` antecede a chamada
externa, e `followup_confirmado` confirma a persistência local. Não há log INFO a
cada varredura vazia; ausência de despachos não comprova falha. Para consultar
candidatas sem envio, use o [diagnóstico](../utilitarios/README.md#diagnóstico-de-follow-up).

Deploy: preparar banco e código, reiniciar flow compatível, então iniciar follow-up.
Rollback: parar o proativo primeiro e manter flow compatível enquanto houver stage
positivo ou retomadas pendentes. Desligar o serviço não limpa esses registros.
Os comandos completos ficam na [rotina de deploy](../regras_deploy/rotina_deploy.md)
e no [guia de ativação](../deploy/README.md#ativação-do-follow-up).
````

## Passo 27 — Alterar `core/database/README.md`

Documentar schema final e preservação dos motivos históricos.

Base SHA-256: `9c1bcec54573a60a59a4e1ce9b85754fe04612baca428d13c54ec080b060b3ea`. Conteúdo completo proposto: **281 linhas**.

````markdown
# Banco de dados

Conexão PostgreSQL, verificação, DDL, funções SQL e preparação do ambiente.

- [Portal do projeto](../../README.md)
- [Padrões de arquitetura](../../PADROES_DE_ARQUITETURA.md#conexões-e-transações)
- [Repositórios de runtime](../repositories/README.md)

## Estrutura

```text
core/database/
├── connection_aws.py
├── connection_check.py
└── deploy_database/
    ├── setup_database.py
    ├── bank_script.py
    ├── followup_script.py
    ├── transacao_deploy.py
    ├── cache_control_script.py
    ├── etapa_transicao_script.py
    ├── floodscript.py
    ├── turno_cliente_script.py
    └── povoar_etapas.py
```

## Runtime e deploy

- `connection_aws.py` fornece conexões para os orquestradores e aceita
  `connect_timeout` opcional; o follow-up e seu diagnóstico usam 10 segundos;
- `connection_check.py` valida acesso ao PostgreSQL;
- `deploy_database/` cria schema, tabelas, índices e funções;
- partições mensais são mantidas pelo comando manual
  `utilitarios.maintenance.message_partitions`;
- SQL de negócio executado durante atendimento fica em `core/repositories`.

## Setup

Em uma instalação vazia, prepare primeiro o schema `chatbot` e as tabelas
gerenciadas pelo Django. No banco de destino:

```sql
CREATE SCHEMA IF NOT EXISTS chatbot;
```

Depois, com as variáveis do ambiente configuradas, a partir da raiz:

```powershell
python callback/manage.py migrate --noinput
```

Somente então execute o setup do banco de negócio:

```powershell
python -m core.database.deploy_database.setup_database
```

Ordem atual:

```text
healthcheck
-> configuração única da role
-> schema principal final
   (inclui tabelas de follow-up por followup_script.py)
-> controle de cache
-> tabelas de flood
-> índices de turno
-> função de dequeue
-> funções de lock
-> seed de etapas
-> whitelist de transições de etapas
-> reset de cache de desenvolvimento
```

`povoar_etapas.py` mantém o catálogo de estados com IDs estáveis.
`etapa_transicao_script.py` mantém a whitelist executável de
`origem + evento -> destino`. Uma aresta só deve entrar no seed quando resolver,
sender, efeitos transacionais e testes estiverem prontos.

`transacao_deploy.py` centraliza conexão, commit, rollback e fechamento. Uma
falha é relançada e interrompe o setup antes do log de finalização. Funções
concluídas anteriormente mantêm seu próprio commit; a reexecução idempotente
completa os passos restantes.

Os comandos utilizam `IF NOT EXISTS`, `CREATE OR REPLACE` ou `ON CONFLICT` onde
aplicável. Por isso, um setup interrompido normalmente pode ser executado de
novo sem apagar o banco.

`bank_script.py` descreve diretamente o schema final da V1. Ele não contém
`ALTER TABLE`, correções de colunas antigas, dados de unidade ou migrações
históricas. As tabelas são criadas em ordem de dependência para que chaves
estrangeiras e constraints já nasçam prontas.

`chatbot.auth_user` é um pré-requisito explícito do DDL de negócio. Sua criação
continua pertencendo às migrations do Django; o DDL não recria tabelas internas
do framework. Se ela não existir, o setup falha com uma orientação antes de
criar as tabelas de negócio.

`unidade.id_usuario_monitoramento` é `INT NULL`, único quando preenchido e
referencia `chatbot.auth_user(id)` com `ON DELETE SET NULL`. O DDL final define
a coluna e suas constraints no `CREATE TABLE` da unidade. O banco garante a
relação 1:1 opcional; a autorização dos recursos pertence ao serviço HTTP e ao
repositório de monitoramento. Excluir um usuário não exclui a unidade.

O schema final inclui `integracao_funil_unidade`, configuração 1:1 da unidade,
`funil_envios`, fila operacional 1:1 da conversa, a profissão informada pelo
cliente naquela conversa, a profissão válida mais recente no cadastro do
cliente e `pesquisa_satisfacao`, registro 1:1 de nota e comentário opcional da
conversa. As etapas 18 a 22 são marcadas como
`elegivel_funil`; os dados da pesquisa não compõem o payload do Funil. A etapa
20 registra a decisão de comentar, a etapa 21 coleta o comentário quando aceito
e a recusa salta diretamente da etapa 20 para a 22. Encerramento e bloqueio de
30 dias são exclusivos da política da etapa 22.

Cada unidade possui `idade_minima_suporte INTEGER NULL DEFAULT NULL`, limitada
por CHECK a NULL/50/60/70/80, e `email_obrigatorio BOOLEAN NOT NULL DEFAULT TRUE`.
O limite encaminha apenas titulares a partir da idade escolhida até 89 anos;
NULL desativa. A coleta de e-mail conserva a exceção universal do titular 60+.

O SQL `deploy/migrations/20260911_idade_minima_suporte.sql` converte a coluna
booleana anterior: TRUE vira 60 e FALSE vira NULL. É transacional, verifica
as configurações por unidade e recusa reaplicação/schema parcial. Não altera
conversas, históricos ou stages do follow-up. Instalação limpa usa o DDL atual;
não deve executar novamente as migrações históricas sobre o schema final.
Ver [procedimento coordenado](../../deploy/idade_minima_suporte.md).

A migração incremental que insere a confirmação como etapa 3 e remapeia as
referências existentes está em
`deploy/migrations/20260809_adicionar_confirmacao_etapa3.sql`. Ela deve ser
executada inteira no DBeaver, em janela de manutenção e com snapshot recente;
`setup_database.py` não substitui essa migração.

A correção posterior que torna a profissão obrigatória depois da confirmação
está em
`deploy/migrations/20260811_tornar_profissao_obrigatoria_apos_confirmacao.sql`.
Ela troca somente o catálogo de transições, aceita reexecução no estado final e
não retrocede conversas que já passaram pela profissão.

A migração que adiciona `cliente.profissao` está em
`deploy/migrations/20260823_adicionar_profissao_cliente.sql`. Ela mantém
`conversa.profissao` como snapshot e preenche o cadastro com a profissão não
vazia da conversa mais recente de cada cliente.

A migração que adiciona as duas políticas da unidade e amplia o domínio de
`conversa.motivo_encerramento` está em
`deploy/migrations/20260829_adicionar_suporte_idoso_email_obrigatorio.sql`.
Ela altera somente o schema, aceita reexecução no estado final e não executa
`UPDATE` nem `INSERT` sobre os dados de negócio.

A migração que renomeia `unidade.nome` para `nome_unidade` e adiciona a
apresentação configurável do agente está em
`deploy/migrations/20260812_personalizar_agente_unidade.sql`. Ela preserva os
nomes das unidades existentes, aplica `Suh`/`feminino` somente no primeiro
backfill e recusa schemas parciais antes de publicar o novo contrato.

`IF NOT EXISTS` não migra uma estrutura criada por uma versão antiga. Evolução
de schema existente exige um script de migração separado ou decisão consciente
de recriação em desenvolvimento. Novas migrações não devem ser anexadas ao DDL
de criação final.

A migração atual de monitoramento está em
`deploy/migrations/20260902_adicionar_usuario_monitoramento_unidade.sql`.
Execute-a inteira no DBeaver antes de publicar o código atualizado, com
`chatbot.unidade` e `chatbot.auth_user` já existentes. Ela adiciona a coluna
opcional e suas constraints. Se a tabela da proposta anterior existir,
transfere seus vínculos, confere o resultado e só então remove essa tabela,
sem `CASCADE`. Vínculos inválidos ou ambíguos interrompem a transação.
O SQL anterior de criação da tabela foi substituído e não deve ser executado.
A migração atual é de aplicação única: coluna já existente causa erro em vez
de aceitar uma estrutura divergente. Em caso de erro, execute `ROLLBACK`.
`ALTER TABLE`, transferência e remoção de legado ficam somente na migração;
o DDL continua sendo exclusivamente a definição final para instalação nova.

## Registros de follow-up

O DDL de instalação limpa inclui três tabelas não particionadas, criadas por
`deploy_database/followup_script.py` dentro da transação de `bank_script.py`:

| Tabela | Responsabilidade |
|---|---|
| `followup_envio` | Recibo por conversa e ID/data da mensagem do bot que originou o ciclo; registra o histórico e o WAMID do lembrete confirmado. |
| `followup_retomada` | Checkpoint da reação do cliente por conversa, fila e hash; preserva etapa, stage anterior e conclusão para retries. |
| `followup_legado` | Auditoria das conversas ativas marcadas na migração, com stage anterior e data da marcação. |

As FKs dessas tabelas apontam para a conversa com `ON DELETE CASCADE`; o
histórico de mensagens continua particionado. Não há nova tabela Django nem
ação administrativa para editar esses registros. `followup_stage` e
`followup_last_sent_at` já pertencem à tabela `conversa`.

Para uma base anterior à V1.2.0, use uma única vez
[followup_registros.sql](../../deploy/migrations/followup_registros.sql), com
flow parado e follow-up desligado. O script inteiro é transacional: cria os
registros, audita todas as conversas ativas e marca `followup_stage = 1`, inclusive
nas etapas 18–21. Não altera etapa, histórico, finalização ou datas anteriores e
não envia mensagens. Legado ativo terminal/inconsistente cancela a migração.

Na produção atual, essa migração já foi aplicada. Não a repita em deploys
seguintes: a reaplicação falha em vez de remarcar conversas. O setup de banco
vazio cria a estrutura sem marcar o legado. A role da aplicação precisa ter
permissões de leitura e escrita nas novas tabelas, por propriedade ou grants.
O [diagnóstico sem envio](../../utilitarios/README.md#diagnóstico-de-follow-up)
confere as consultas; ele não comprova as permissões de escrita.

Para habilitar a segunda camada em base existente, aplicar
[`20260924_segundo_followup.sql`](../../deploy/migrations/20260924_segundo_followup.sql).
Ela só amplia `ck_conversa_motivo_encerramento` com `followup_sem_resposta` e
preserva todas as conversas. O DDL de instalação limpa já inclui esse motivo.
Não há novas colunas ou tabelas. O segundo recibo usa o ID/data do primeiro envio
como âncora, preservando a unicidade e a rastreabilidade de cada camada.

Histórico, recibo e stage 1 são confirmados juntos pelo worker proativo; no segundo,
o mesmo commit grava stage 2, status inativo, horário e motivo de encerramento.
Histórico da resposta, efeitos da etapa, conclusão da retomada, reset do stage,
eventual encerramento e finalização da fila são confirmados juntos pelo flow.
A chamada à Meta ocorre fora dessa atomicidade local;
aceite externo seguido de falha no commit ainda pode gerar duplicidade.

## Atomicidade

No PostgreSQL, o DDL utilizado pelo projeto participa de transações. Uma tabela
não é criada pela metade: o bloco da função confirma ou reverte sua transação.
O banco pode ficar parcialmente configurado entre funções independentes, e a
reexecução completa os passos restantes.

## Funções PostgreSQL críticas

`bank_script.py` define:

- dequeue e retomada de mensagens abandonadas;
- lock e unlock versionados da conversa;
- tabelas, restrições e índices principais;
- timezone e timeouts operacionais.

Mudanças nessas funções podem alterar ordenação, retry e exclusão mútua. Consulte
[Regras de negócio](../../REGRAS_DE_NEGOCIO.md) e atualize testes de contrato.

## Segurança

Credenciais de banco são carregadas por `core/config_env.py` a partir de
variáveis de ambiente:

```text
DB_HOST
DB_NAME
DB_USER
DB_PASSWORD
DB_PORT
DB_SSLMODE
DB_SSLROOTCERT
```

`DB_SSLMODE` e `DB_SSLROOTCERT` são opcionais para preservar o comportamento
local. Em produção, use `DB_SSLMODE=verify-full`, aponte
`DB_SSLROOTCERT` para uma CA confiável e mantenha em `DB_HOST` o hostname real
do servidor, necessário para a validação do certificado.

Novas credenciais não devem ser adicionadas ao código, README, logs ou prints.
Em desenvolvimento, use o `.env` local privado e ignorado pelo Git. Em produção,
use variáveis do serviço, arquivo de ambiente com permissão restrita ou
gerenciador de segredos.

## Testes relacionados

- `tests/unit/test_fluxo_turno_abc.py`;
- `tests/unit/test_persistencia_essencial.py`;
- `tests/unit/test_retry_essencial.py`;
- `tests/unit/test_worker_flow_runtime.py`;
- `tests/unit/test_suporte_idoso_email_obrigatorio.py`;
- `tests/unit/test_followup.py`;
- `tests/integration/test_followup_postgres.py` (PostgreSQL local descartável).

A organização e o comando da suíte completa estão em `tests/README.md`.


## Encerramentos por idade e configuração atual

A migração `20260926_filtro_comercial_regras_idade.sql` amplia o CHECK de motivos,
preserva legados, normaliza suporte 90 para NULL e exige telefone comercial válido.
Não cria coluna nem altera motivos históricos. A entrada vinculada à resposta
conserva a idade informada; o motivo específico conserva o limite aplicado.
Instalações novas usam o DDL final e não reaplicam migrações antigas.
````

## Passo 28 — Alterar `core/repositories/README.md`

Documentar responsabilidade e escopo das novas consultas.

Base SHA-256: `ebad86fe709e406303ccbe7ce9f7dd9faf69fd367340151322ff3013239e386d`. Conteúdo completo proposto: **186 linhas**.

````markdown
# Repositorios

SQL de runtime da aplicacao. Os modulos sao agrupados por dominio e entidade,
nao pelo consumidor nem pelo tipo de comando SQL.

- [Portal do projeto](../../README.md)
- [Padroes de arquitetura](../../PADROES_DE_ARQUITETURA.md#sql-e-repositórios)
- [Banco e deploy](../database/README.md)

## Estrutura

```text
core/repositories/
|-- atendimento/
|   |-- clientes.py
|   |-- conversas.py
|   |-- dependentes.py
|   |-- fila.py
|   |-- followup.py
|   `-- historico.py
|-- fluxo/
|   |-- contextos/
|   |-- pesquisa_satisfacao.py
|   |-- politicas.py
|   |-- transicoes.py
|   `-- triagem.py
|-- unidades/
|   |-- consultas.py
|   `-- cache_control.py
|-- seguranca/
|   |-- bloqueio_meta.py
|   |-- suspeita_bot.py
|   `-- turno_cliente.py
|-- monitoramento/
|   |-- acessos.py
|   `-- painel.py
`-- funil/
    |-- integracao.py
    |-- envios.py
    `-- leads.py
```

`atendimento` persiste as entidades centrais da conversa. `fluxo` consulta e
registra regras do mapa de etapas. `unidades` concentra consultas e versao do
cache. `seguranca` guarda as barreiras de turno e bloqueio. `funil` cobre a
configuracao por unidade e o estado dos envios ao CRM.

`monitoramento/acessos.py` consulta `unidade.id_usuario_monitoramento`, o vínculo
1:1 opcional entre conta e unidade, revalidando a conta no banco. Sem referência
não há acesso. Opcionalmente verifica conversa e mensagem na
mesma leitura, sempre pela unidade da conversa. Recebe o ID do usuário da sessão
por meio do serviço HTTP; não aceita um ID de unidade fornecido pelo navegador.
Retorna `AcessoMonitoramento` ou `None`. Não lê credenciais nem concede acesso
especial a superusuários.

`monitoramento/painel.py` contém somente SELECTs para unidade, conversas,
mensagens, métricas, perfis, satisfação, etapas, atividade e contatos. Todas as
funções exigem o `id_unidade` já obtido pelo guard e repetem o escopo no próprio
SQL. O navegador não fornece esse identificador.

No domínio `funil`:

- `integracao.py` lê widget, link e canal da unidade;
- `leads.py` reúne cliente, dependente e triagem, preservando a profissão da
  conversa e a resposta histórica de e-mail;
- `envios.py` materializa, reivindica, reagenda e confirma a fila
  `chatbot.funil_envios`.

O repositório não executa HTTP. O `workers/worker_funil` controla commits e
chama `core/integrations/funil` depois de encerrar a transação de leitura.

## Contextos e histórico do atendimento

- `fluxo/contextos/etapa6.py` lê `idade_minima_suporte`, `bpa_ativo` e número comercial
  da unidade; `fluxo/contextos/etapa10.py` lê `email_obrigatorio`, destino do
  atendimento e idade do titular. Os repositórios validam a integridade dos
  dados, mas o resolver aplica a regra de atendimento.
- `atendimento/conversas.py` grava `conversa.profissao`, o snapshot capturado
  na etapa 4; `atendimento/clientes.py` também atualiza o cadastro corrente.
  O Funil usa a profissão da conversa, nunca `cliente.profissao` como fallback.
- `funil/leads.py` busca o e-mail pela mensagem do cliente na etapa 10 ligada
  ao envio confirmado do bot na etapa 11, na mesma conversa, fila e mensagem
  de origem. `cliente.email` só é fallback para legado sem esse vínculo;
  a classificação do valor ocorre fora do SQL, em `core/validacoes/email.py`.
- `atendimento/historico.py` fornece o nome e o último bot `sent` da conversa
  para a saudação de retorno. O repositório não decide o intervalo de três
  horas nem dispara mensagens.

## Contrato

Uma funcao de repositorio deve:

- receber `cursor`;
- usar SQL parametrizado;
- retornar linha, tupla, booleano, quantidade afetada ou uma representacao
  simples do resultado;
- validar invariantes persistidas quando necessario;
- deixar excecoes de persistencia chegarem ao orquestrador.

Uma funcao de repositorio nao deve:

- chamar `get_conn`;
- executar `commit`, `rollback` ou `close`;
- decidir retry;
- retornar resposta HTTP;
- acessar Redis, Meta ou outro servico externo;
- escolher a proxima etapa do atendimento.

## Mapeamento de resultados

Converter uma linha SQL em `dict`, tupla nomeada ou dataclass pertence ao
repositorio quando isso apenas nomeia os dados consultados. Decisoes de negocio,
montagem de mensagens, retry e efeitos externos continuam fora desta pasta.

## Propriedade da transacao

```text
worker_flow  -> flow_worker.py
worker_followup -> followup_worker.py
worker_funil -> funil_worker.py e processamento.py
webhook      -> post_flow.py, flood_guard.py ou bloqueio_meta_guard.py
scripts      -> proprio ponto de entrada
```

O repositorio nao anuncia rollback que nao executou. Ele propaga a excecao para
o dono real da transacao registrar e decidir a recuperacao.

## Idempotencia e concorrencia

- `seguranca/turno_cliente.py` usa advisory lock por cliente e unidade;
- `atendimento/fila.py` preserva a ordem por timestamp Meta e ID;
- `atendimento/historico.py` reutiliza os vinculos da mensagem original;
- `fluxo/transicoes.py` carrega somente as arestas permitidas para a origem;
- updates de conversa exigem origem, evento e destino compativeis;
- reaplicacao idempotente aceita somente a origem ou o destino exato.

## Ao criar um repositorio

Acrescente a operacao ao modulo da entidade correspondente. Crie um novo modulo
quando houver um dominio real e coeso; nao crie `utils.py` generico e nao mova
DDL para esta pasta.

## Testes relacionados

- `tests/unit/test_persistencia_essencial.py`;
- `tests/unit/test_fluxo_turno_abc.py`;
- `tests/unit/test_retry_essencial.py`;
- `tests/unit/test_worker_flow_runtime.py`;
- `tests/unit/test_suporte_idoso_email_obrigatorio.py`;
- `tests/unit/test_saudacao_retorno.py`.

O núcleo transacional e os testes específicos estão descritos em
[`tests/README.md`](../../tests/README.md).

## Registros de follow-up

`atendimento/followup.py` concentra seleção, releitura, fencing e recibos de envio
proativo e retomada. Recebe cursor; não abre conexão, não faz commit e não importa
worker. O histórico permanece particionado; a unicidade do ciclo fica na tabela
não particionada `followup_envio`, pela chave composta conversa + ID/data da âncora.
`followup_retomada` permite reconstruir a reação ignorada em retries após o reset.
`followup_legado` audita a marcação inicial de todas as conversas ativas com stage 1,
preservando ID, stage anterior e horário da migração. Esse registro não é um envio.
As tabelas são internas, sem ações no monitoramento ou no admin.

`listar_elegiveis` e `reler_elegivel` usam o mesmo SQL: etapa 1–17, stage zero,
última mensagem do bot confirmada há pelo menos sete horas, última mensagem do
cliente dentro de 23h59, unidade adimplente e ausência de bloqueios ou fila aberta.
Os horários do bot e do cliente são condições separadas. A paginação usa
`(ancora_em, id_conversa)` para não ficar presa nas primeiras falhas.

`proteger_conversa` confere `processing`, `lock_version` e validade de 110
segundos antes da persistência, com renovação antes do envio. A retomada
concluída é reconhecida por sua entrada original; um replay não zera um novo ciclo.
`consultar_diagnostico` executa transação somente leitura e não adquire o lock de
processamento nem envia mensagens. Os contratos reais de SQL e migração são
verificados em `tests/integration/test_followup_postgres.py`.


## Encerramentos no monitoramento

`monitoramento/encerramentos.py` lê, em lote, o motivo da última conversa real
cliente/unidade e o par histórico de mensagens pelo hash de origem. A limpeza
da fila não quebra esse vínculo. Consultas sempre recebem a unidade do guard.
O relatório agrupa conversas encerradas pela data final, sem deduplicação por
cliente e sem exigir que continuem sendo o atendimento mais recente.
````

## Passo 29 — Alterar `core/integrations/whatsapp/README.md`

Alinhar o corte universal mantendo os contratos dos senders.

Base SHA-256: `de803a32844a522db714cb6c5050245860880bb938e3a828df801dfcbab6d41f`. Conteúdo completo proposto: **298 linhas**.

````markdown
# Integração WhatsApp

Comunicação com a Meta WhatsApp Cloud API por meio da biblioteca PyWa.

- [Portal do projeto](../../../README.md)
- [Regras de negócio](../../../REGRAS_DE_NEGOCIO.md)
- [Padrões de arquitetura](../../../PADROES_DE_ARQUITETURA.md#whatsapp-e-pywa)
- [Integrações externas](../README.md)

## Estrutura

```text
core/integrations/whatsapp/
├── exceptions.py
├── numero_comercial.py
├── messages/
│   ├── README.md
│   ├── etapa1_messages.py ... etapa22_messages.py
│   ├── componentes_compartilhados.py
│   ├── followup_messages.py
│   ├── tratamentos_universais.py
│   ├── tratamentos/
│   │   ├── composicao.py
│   │   ├── financeiro.py
│   │   ├── midia.py
│   │   ├── reforco_escolar.py
│   │   ├── retorno_inatividade.py
│   │   └── retorno_followup.py
│   └── triagem_componentes.py
├── pywa_functions/
│   ├── cliente.py
│   ├── saudacao.py
│   ├── resposta_envio.py
│   ├── ferramentas.md
│   └── pywa_senders/
│       ├── etapa1.py ... etapa22.py
│       ├── followup.py
│       └── triagem_base.py
└── tools/
    ├── ativando_numero.py
    ├── ativando_waba_id.py
    ├── config.py
    ├── desativando_numero.py
    ├── desativa_waba_id.py
    ├── usuarios.py
    └── validando_phone_waba.py
```

## Direção das dependências

```text
worker -> pywa_functions -> messages
                      |--> cliente PyWa
                      `--> Meta
```

`messages` não importa PyWa. `pywa_senders` pode importar `messages`, cliente e
exceções da integração. Nenhum deles controla banco, fila, transição ou retry.

## Messages

Antes de alterar textos ou montadores, seguir o
[contrato de personalidade e composição do atendimento](messages/README.md).
Ele distingue apresentação, tratamentos, a exceção de entrada da etapa 1,
triagem e os dois tipos de retorno.

Catálogo de conteúdo enviado:

- textos;
- títulos de botão;
- callbacks;
- funções puras de montagem.

Textos de WhatsApp não devem ser escritos diretamente no worker. Alterar uma
mensagem não deve mover a responsabilidade de envio para `messages`.

Cada etapa de 1 a 22 mantém seu próprio arquivo `etapaN_messages.py`.
Nele ficam a mensagem padrão e a repetição pura, com variantes de titular e
dependente quando pertinentes. Os montadores importados de `tratamentos/`
compõem orientação, ponte quando necessária e repetição, nessa ordem.
`compor_mensagem_inicial` une apresentação e pergunta reutilizável na entrada
da etapa; `compor_tratamento` é exclusivo para orientação e repetição, sem
a apresentação. As duas funções compartilham apenas a formatação dos parágrafos.
Contexto inválido tem mensagem própria que já orienta a resposta correta:
não usa `compor_tratamento` nem concatena a repetição. Conserva botões/opções e
rodapés da etapa e aceita a saudação de três horas quando elegível.
O follow-up seleciona a repetição neutra (`repeticao=True`); a triagem usa
suas perguntas canônicas. A etapa 8 é exceção: qualquer reação ao follow-up
avança diretamente para a 9, sem repetir a 8. Os retornos não duplicam apresentações, celebrações
ou despedidas da entrada normal na etapa.

As mensagens oferecem uma **experiência Supera gratuita**. Na etapa 7, a abertura
saúda o titular pelo nome e destaca **demonstração prática gratuita**; a pergunta
final convida a reservar sua **experiência Supera exclusiva**. A rota de dependente
preserva seu nome como participante. Os montadores e contextos de atendimento
distinguem `nome_titular`, `nome_dependente` e `nome_agente`, sem alterar o esquema
do banco. Os botões das etapas 7 e 9 exibem **Reservar agora**;
a etapa 18 usa **Já reservei**. O aceite por texto continua reconhecendo expressões
antigas como `quero agendar` e `já agendei`, conforme a etapa. Perguntas sobre como
reservar não são aceites; na etapa 18, intenção de reservar não comprova conclusão.

A gratuidade se refere à experiência; o tratamento financeiro explica que os
valores de investimento são definidos após ela, com orientação da equipe.
O prefixo é compartilhado em `tratamentos/financeiro.py`; cada etapa fornece
sua pergunta de retomada, introduzida por `Vamos lá:` uma única vez.
`tratamentos_universais.py` apenas reexporta os imports antigos por compatibilidade.
Não há personalização por diretor nem campos
adicionais na unidade. Os montadores são puros, e o histórico conserva o
texto efetivamente enviado. Respostas já persistidas não são reenviadas.

Os corpos das mensagens usam negrito do WhatsApp (`*texto*`) com moderação,
priorizando a experiência oferecida e a ação principal. Evitar destacar todas
as palavras ou repetir o convite completo nos tratamentos financeiros.
Títulos de botões e valores usados pelos validadores permanecem sem marcação.

O tom é acolhedor, com emojis discretos e orientação clara. A oferta usa
**presentear**; **Maravilha! ☺️** aparece na apresentação normal da etapa 7,
sem ser acrescentado aos tratamentos de mídia, contexto, financeiro ou reforço
escolar. A etapa 1 não presume quem participará. Na apresentação do link,
o participante é o titular ou o dependente identificado pelo nome, inclusive
na repetição por follow-up e nos tratamentos. O contexto fornece esses dados ao sender; os
montadores não consultam banco nem decidem transições.

Na etapa 2, negativas sem destino alternativo repetem a pergunta. Uma
correção explícita como `Não, é para mim` conserva a escolha indicada.
Na oferta e na reserva, dúvidas curtas como `É gratuita?` retomam a
experiência. Fora desse contexto, o termo feminino precisa estar ligado
explicitamente à demonstração ou experiência. O aceite flexível permanece.

A retomada da etapa 9 usa uma única saudação, tanto após follow-up quanto
após três horas de inatividade. As referências ao dependente permanecem
explícitas; titular e dependente não trocam de papel.

As apresentações inicial padrão, explicativa, de mídia, financeira e de tratamento
de reforço escolar da etapa 1 recebem `nome_unidade`, `nome_agente` e `genero` como
argumentos já validados pelo worker. `messages` apenas escolhe `o` ou `a` e
formata o texto; não consulta o banco nem conhece a conversa.

Antes da etapa 1 estar apresentada, um texto pedindo informações gerais sobre
o Supera pode receber a abertura explicativa. O classificador
`validadores_contexto/valida_inicio_etapa1.py` reconhece frases completas e só é
usado após os tratamentos de mídia, reforço e financeiro. Essa variante pede
o nome uma vez e converge para a mesma etapa 2, sem novas colunas ou transições.
Depois da abertura e no follow-up, preserva-se a coleta do nome já existente.

`tratamentos/retorno_inatividade.py` monta `Bom te ver novamente, <nome> ☺️` quando
o cliente retorna com `followup_stage = 0` pelo menos três horas após o último envio confirmado do bot
na mesma conversa. A etapa 1 fica fora da regra; nome ou datas ausentes ou
incompatíveis não interrompem o atendimento e não produzem prefixo.

O worker fornece o contexto histórico e aplica a saudação à resposta corrente,
inclusive tratamentos, sem mudar o destino. Não é follow-up, mensagem separada
ou disparo automático após três horas de inatividade. No retry com resposta
persistida, não há novo envio.

## PyWa functions

Concentra a criação do cliente PyWa e o transporte das mensagens do fluxo. Os
senders são o local normal para chamadas de envio; operações compartilhadas de
bloqueio e desbloqueio ficam em `tools/usuarios.py`, que reutiliza a mesma
fábrica de cliente em `pywa_functions/cliente.py`.

- `cliente.py`: normaliza `phone_id`, cria `WhatsApp` e aplica o prefixo de
  retorno somente no escopo do envio corrente;
- `saudacao.py`: seleção de bom dia, boa tarde ou boa noite pelo horário do
  atendimento inicial, distinta da saudação de retorno;
- `resposta_envio.py`: extrai o ID confirmado pela Meta e falha se ele faltar;
- `pywa_senders/etapaN.py`: mensagens normais e tratamentos específicos da
  etapa N.

Cada sender escolhe conteúdo, legenda e lista de botões, realiza a chamada PyWa
e devolve um contexto técnico com o ID da Meta e a etapa da mensagem enviada.
O sender não escolhe origem, evento ou destino da transição.

O encaminhamento de suporte ao idoso é um sender da etapa 6 com botão para o
número comercial, normalizado por `numero_comercial.py`. A decisão de usar
`idade_minima_suporte`, comparar a idade do titular ao limite e encerrar o
atendimento é do worker. O sender recebe o limite validado e o texto de contato
montado pelo catálogo com agente, unidade, nome e idade atual do titular. Todas as faixas
usam a mesma mensagem de atendimento personalizado e o botão `Falar agora`.
O link inclui o texto pré-preenchido com codificação de URL; o cliente ainda
precisa confirmar o envio no WhatsApp. O reconhecimento do corpo atual e do
texto ainda emitido pela versão em produção permite recuperar respostas sem
reenviá-las. As variantes antigas que citavam a faixa foram removidas após
verificação de ausência de pendências no banco.

O encaminhamento geral de 90 anos ou mais mantém um sender próprio, usado
para titular e dependente mesmo com suporte desativado. Seu catálogo apresenta
a anamnese com o consultor e acrescenta um rodapé acolhedor, sem repetir a
pergunta de idade. A decisão de encerrar continua pertencendo ao worker.
Os dois senders exigem `mensagem_comercial` e usam o mesmo montador de texto
pronto, `montar_mensagem_contato_comercial_etapa6`. O repositório da etapa 6
consulta o nome da unidade vinculada à conversa. O worker fornece a rota e a
idade da resposta atual; o catálogo adapta o pedido para titular ou dependente,
sempre mencionando a experiência Supera gratuita. Não atribuir ao cliente a
idade informada sobre seu dependente. Dados obrigatórios ausentes impedem
montar um contato incorreto antes de qualquer envio à Meta.
Da mesma forma, a política `email_obrigatorio` e a distinção entre
aceite da oferta e pedido de informações não pertencem aos senders.

Uma função de mídia envia somente um arquivo. Lotes e álbuns exigem um contrato
futuro capaz de persistir vários IDs e tratar sucesso parcial.

Os senders devolvem contexto simples para o worker. Falhas são encadeadas com
`ErroEnvioMeta`, permitindo rollback e retry sem esconder a causa original.

## Tools

Operações Meta compartilhadas e ferramentas administrativas usadas pelo
Django Admin e pelo webhook:

- registrar/desregistrar número;
- validar o vínculo entre WABA e phone ID;
- ativar/desativar a inscrição WABA;
- bloquear e desbloquear usuários na Meta.

Relatórios conscientes e somente leitura ficam em
[`utilitarios/monitoring/blocked_users.py`](../../../utilitarios/monitoring/blocked_users.py).
Eles comparam bloqueios pela chave completa
`(waba_id, phone_id_unidade, wa_id_cliente)` e reconciliam registros Cloud API.

`tools/usuarios.py` é a primitiva única de bloqueio e desbloqueio consumida pelo
webhook e pelo Admin. Os demais módulos deste diretório atendem às operações de
configuração da conta e do número. Eles podem reutilizar a fábrica de cliente,
mas não devem duplicar envio de etapa nem assumir responsabilidades de banco,
fila ou transação.

`tools/config.py` centraliza a configuração operacional da integração Meta, mas
os valores são lidos por `core/config_env.py` a partir de variáveis de ambiente:

```text
META_ACCESS_TOKEN
META_GRAPH_API_VERSION
META_HTTP_CONNECT_TIMEOUT_SECONDS
META_HTTP_READ_TIMEOUT_SECONDS
META_PHONE_REGISTRATION_PIN
```

`META_GRAPH_API_VERSION` usa o formato `26.0`, sem o prefixo `v`. Essa versão é
aplicada ao cliente PyWa e a todas as URLs diretas da Graph API. Se uma versão
nova apresentar incompatibilidade, a variável pode retornar manualmente para a
última versão estável validada.

Não adicione token ou outro valor sensível diretamente nesse arquivo. WABA ID e
phone number ID são dados por unidade e devem vir do banco/cache.
`META_PHONE_REGISTRATION_PIN` também é segredo operacional e só é necessário
para a operação administrativa de registro do número; não deve ser exibido em
logs, documentação ou mensagens.

## Limites

Esta integração não deve:

- executar SQL ou Redis;
- decidir etapa persistida;
- marcar fila como `sent`;
- escolher quantidade ou intervalo de retries;
- executar commit, rollback ou close;
- importar módulos de `callback` ou `workers`.

## Testes relacionados

- `tests/unit/test_fluxo_turno_abc.py`;
- `tests/unit/test_persistencia_essencial.py`;
- `tests/unit/test_retry_essencial.py`;
- `tests/unit/test_worker_flow_runtime.py`;
- `tests/unit/test_suporte_idoso_email_obrigatorio.py`;
- `tests/unit/test_saudacao_retorno.py`.

O núcleo transacional e os testes específicos estão descritos em
[`tests/README.md`](../../../tests/README.md).

## Lembrete de follow-up

`messages/tratamentos/retorno_followup.py` monta a saudação de retomada com stage
positivo: `Bom te ver novamente, <nome> ☺️` ou `Bom te ver novamente ☺️`.
O nome do prefixo vem do cadastro persistido, quando autorizado pela etapa.
Na etapa 1, o worker passa nome ausente ao formatador, mesmo com cadastro antigo:
a saudação é sempre genérica. Um nome válido recebido na reação avança para a 2;
tratamentos específicos seguem normais; sem ambos, reapresenta a pergunta.
O prefixo é aplicado no corpo da resposta, preservado no histórico e removido
do escopo ao sair do sender, inclusive em falhas. O proativo continua sem saudação.

Na etapa 8, o worker reutiliza a transição normal para a 9 e seus senders de
titular/dependente. A reação não vale como aceite da oferta da 9. Sua saudação
própria é suprimida para conservar somente o prefixo de follow-up. A 8 possui
apenas mensagem inicial, sem variante de repetição. Avanço e conclusão do ciclo
são persistidos juntos pelo worker, sem decisões de fluxo nos montadores.

`messages/followup_messages.py` contém o primeiro lembrete e a despedida do segundo,
com nome do titular após a etapa 1 e adaptação para dependente.
`pywa_senders/followup.py` envia texto sem botões, sem saudação de retorno e sem
id_mensagem_fila fictício. Usa sessão HTTP com timeout e sem retry automático;
recebe destinatário, phone_id da unidade e o texto montado pelo worker. `conta_wa` aceita sessão opcional sem
alterar os clientes existentes. A sessão usa timeout de 20 segundos por operação,
com conexão limitada a 5 segundos. Stage e persistência pertencem ao worker/repositório.
O ID retornado confirma o aceite da API; os eventos `sent`, `delivered` e `read`
recebidos pelo webhook não atualizam o histórico nesta versão.
````

## Passo 30 — Alterar `core/integrations/whatsapp/messages/README.md`

Documentar reconhecimento histórico sem alterar quebras ou textos aprovados.

Base SHA-256: `61a4edd400270d1b3e5b6edbaa1550164c6bcc74b3786b85c3c365304a489ac6`. Conteúdo completo proposto: **745 linhas**.

````markdown
# Mensagens: personalidade e composição do atendimento

Este é o contrato editorial da pasta `messages`. Leia-o antes de criar,
reescrever ou reorganizar mensagens. Ele orienta o código atual e as próximas
alterações: o cliente deve perceber um atendimento acolhedor, coerente e
contínuo, mesmo quando precisar de orientação ou voltar depois de uma pausa.

- [Integração WhatsApp e responsabilidades das camadas](../README.md)
- [Regras de negócio do atendimento](../../../../REGRAS_DE_NEGOCIO.md)
- [Rotina para implementar etapas](../../../../ROTINA_IMPLEMENTACAO_ETAPAS.md)

Este documento não muda validadores, transições, horários, bloqueios ou
elegibilidade. Uma mudança editorial não autoriza alterar esses contratos.
Os exemplos ilustram o padrão de composição. Os montadores Python são a
fonte dos textos enviados; esta organização está implementada no projeto
local e só chegará à produção no próximo deploy.

## 1. A personalidade deve acompanhar o contexto

O bot apresenta o Supera com carinho, clareza e entusiasmo equilibrado.
Deve facilitar a próxima resposta e valorizar a pessoa, sem parecer um
formulário nem pressioná-la a continuar.

- Usar frases naturais e fáceis de ler, com uma ação ou pergunta principal.
- Demonstrar acolhimento com expressões como `Maravilha!`, `Vamos lá?` e
  `Vou te ajudar a continuar`, quando fizerem sentido naquele momento.
- Priorizar sorriso acolhedor (`☺️`, `😊`) e coração laranja (`🧡`), com
  moderação. Não é obrigatório colocar um emoji em cada pergunta.
- Reservar a comemoração para momentos compatíveis com progresso ou aceite.
  Após uma resposta não compreendida, orientar sem culpar nem comemorar.
- Usar **experiência Supera gratuita**, **demonstração prática exclusiva**,
  **presentear**, **reservar** e **sua reserva**, conforme o contexto.
  O atendimento não oferece curso ou matrícula gratuitos.
- Na oferta inicial da etapa 7, destacar **demonstração prática gratuita**
  logo na abertura, antes da explicação da avaliação. Encerrar com o convite
  para reservar a **experiência Supera exclusiva**. A gratuidade não pode ficar
  escondida somente no fim da oferta.
- Não reintroduzir `agendamento`, `aula gratuita`, nome de diretor ou cortesia
  como redação da oferta. Identificadores técnicos e textos legados aceitos
  pelos validadores têm outro papel e permanecem compatíveis.
- Usar negrito do WhatsApp (`*texto*`) para a oferta ou ação mais importante,
  sem destacar o parágrafo inteiro ou toda ocorrência de uma palavra.
- Separar acolhimento, explicação e pergunta com quebras controladas no texto
  final, sem acrescentar linhas vazias automaticamente a cada fragmento.
  Cabeçalhos e rodapés devem aparecer uma vez; títulos de botão não levam
  asteriscos de formatação.

### Espaçamento: declarar nas variáveis e conferir o resultado

**As quebras de linha pertencem às variáveis de mensagens e aos modelos
visuais, não às funções que recebem textos para compor.** `\n` muda de linha;
`\n\n` deixa uma linha vazia; `\n\n\n` deixa duas. Dividir uma string em
várias linhas do arquivo Python não insere quebras nem espaços no envio.

Manter `\n\n` entre parágrafos. A correção de excesso reduz somente três
quebras consecutivas para duas; não transformar duas em uma nem remover
quebras simples indiscriminadamente. Todo rodapé existente deve ficar
separado do corpo por uma linha vazia (`\n\n`), declarada no modelo
`MENSAGEM_COM_RODAPE`. O WhatsApp não é responsável por criar esse espaço:
o rodapé em itálico faz parte do texto enviado. Não acrescentar outro
separador ao corpo antes de aplicar o modelo.

Após o cabeçalho, usar também duas quebras (`\n\n`) antes da mensagem,
declaradas em `MENSAGEM_COM_CABECALHO`, inclusive nas perguntas da triagem.

- `compor_mensagem_inicial` e `compor_tratamento` apenas concatenam os
  fragmentos. Não inserem separadores, não removem quebras e não usam `strip()`
  no texto pronto. A apresentação, a orientação e a ponte declaram sua
  separação final; a pergunta reutilizável pode ser enviada sozinha.
- Por exemplo, `APRESENTACAO_ETAPA1` termina em `\n\n`, deixando uma linha
  vazia antes da pergunta. O compositor não acrescenta uma terceira quebra.
  Na etapa 7, a própria apresentação declara as quebras entre oferta,
  explicação e pergunta; os tratamentos continuam usando apenas a pergunta.
- As saudações de retorno têm sua quebra final nas constantes de
  `tratamentos/retorno_followup.py` e `tratamentos/retorno_inatividade.py`.
  Aplicar o prefixo apenas o concatena, uma única vez.
- Cabeçalhos e rodapés usam os modelos `MENSAGEM_COM_CABECALHO` e
  `MENSAGEM_COM_RODAPE`, em `componentes_compartilhados.py`. Suas funções
  apenas preenchem esses modelos. Os rótulos usados nos metadados continuam
  separados da formatação visual do corpo.
- Não colocar `"\n" + mensagem`, `mensagem + "\n"` ou `"\n".join(...)`
  dentro de uma função para decidir espaçamento. Declarar o formato na
  variável correspondente, perto do texto que será revisado.
- Conferir a mensagem completa nas rotas de titular, dependente, repetição,
  tratamento e retorno. Evitar quebras nos dois lados da mesma junção,
  palavras coladas e a união de blocos que precisam continuar separados.
  Preservar links completos, perguntas, negritos, botões e rodapés.
- A redução de espaçamento feita anteriormente não é uma regra automática
  de envio. Não diminuir novamente todas as quebras nem achatar parágrafos.
  Ao mover a formatação para variáveis, comparar o resultado antes e depois.
- Mensagens já persistidas não são reformatadas. A recuperação da etapa 6
  reconhece também o espaçamento anterior, exclusivamente para concluir retries.

Os botões das etapas 7 e 9 exibem `Reservar agora`. Os validadores aceitam tanto
`Reservar agora` quanto `Quero reservar`, preservando respostas de botões antigos.
Entusiasmo não pode afirmar algo que ainda não aconteceu. O aceite expressa
intenção; não significa que o dia e horário já foram escolhidos.
Perguntas da triagem devem permanecer neutras: não elogiar ou reprovar uma
resposta como `Nunca` ou `Frequentemente`, nem transformar triagem em diagnóstico.

## 2. Separar os momentos da mensagem

Uma etapa representa o que o bot está esperando do cliente. **Apresentar uma
etapa**, **repetir sua pergunta** e **acolher um retorno** são situações diferentes.
“Mensagem inicial da etapa” não significa começar outra conversa.

| Momento | Composição da fala | Efeito no fluxo |
|---|---|---|
| Entrada normal em uma etapa | Abertura coerente com o passo anterior + conteúdo/pergunta + componentes necessários | O fluxo já autorizou a apresentação desse destino. |
| Mídia, financeiro ou reforço em etapa apresentada | Orientação específica + retomada neutra da pergunta atual | O tratamento não autoriza avançar. |
| Contexto inválido em etapa apresentada | Mensagem própria que já pede a resposta correta, sem concatenar a repetição | Permanece na etapa atual. |
| Retorno por inatividade, sem follow-up pendente | Uma saudação de retorno + resposta que o fluxo normal produziria | A resposta do cliente continua sendo validada; pode avançar ou receber tratamento. |
| Reação a follow-up pendente, exceto na etapa 8 | Uma saudação + destino válido, tratamento específico ou repetição neutra | Usa os validadores normais; contexto inválido genérico apenas reapresenta a pergunta. |
| Reação a follow-up pendente na etapa 8 | Uma saudação de retorno + mensagem da etapa 9 | Avança diretamente de 8 para 9, sem repetir a 8 nem interpretar a reação como aceite da oferta. |
| Retry com resposta já persistida | Reutilização do registro existente | Não montar nem enviar outra mensagem. |

O conteúdo reutilizável é a **pergunta ou chamada principal**, não
necessariamente a mensagem normal inteira. Uma abertura como `Prazer`,
`Certo`, `Perfeito` ou `Maravilha` pode funcionar na entrada e não funcionar
depois de `Não consegui entender sua resposta`.

Exemplo da diferença na oferta:

```text
Entrada normal:
Maravilha, {nome_titular}! ☺️ Queremos te presentear com uma *demonstração prática gratuita* na nossa unidade!
[explicação da avaliação + pergunta sobre sua experiência Supera exclusiva]

Resposta não compreendida:
Olha, não consegui entender se você quer reservar sua experiência Supera gratuita.
Escolha Reservar agora para continuar ou Talvez mais tarde para deixar para outro momento.
```

Uma dúvida não precisa receber todo o discurso comercial novamente. O
tratamento financeiro e o de reforço escolar usam o prefixo compartilhado,
uma ponte como `Vamos lá:` e a pergunta necessária para continuar.
Não acumular conectivos nem repetir esse prefixo dentro da mesma resposta.

## 3. A etapa 1 é a exceção de entrada

Há quatro grupos distintos em `etapa1_messages.py`:

| Grupo | Quando usar | Conteúdo |
|---|---|---|
| Apresentação inicial padrão | Primeiro contato, antes de a etapa 1 estar apresentada | Saudação, agente/unidade, acolhimento e pergunta do primeiro nome. |
| Apresentação inicial explicativa | O primeiro texto pergunta o que é o Supera ou pede informações gerais | Mensagem única aprovada: apresentação, explicação como academia para o cérebro e pedido do nome. |
| Apresentação inicial com tratamento | A primeira entrada já contém mídia, dúvida financeira ou ideia de reforço escolar | Apresentação/acolhimento + tratamento correspondente + pergunta do primeiro nome. |
| Tratamento após a apresentação | O bot já pediu o nome e a resposta precisa de orientação | Tratamento + pergunta do nome; no contexto de nome inválido, a orientação já contém esse pedido. Não repetir toda a apresentação. |

O tratamento inicial é uma **versão única da abertura**. Não enviar primeiro
o tratamento e depois outra mensagem inicial completa. A ordem exata das
frases deve formar uma única fala natural; hoje a apresentação vem antes
da orientação específica.

O tratamento de primeira entrada apresenta a etapa 1. Depois disso, uma
resposta válida de nome pode produzir a transição para a etapa seguinte.
Não tratar a primeira mensagem espontânea como nome só porque contém texto.

### Primeiro texto pedindo informações sobre o Supera

A prioridade do resolver é **mídia → reforço escolar → financeiro → pedido de
informações gerais → abertura padrão**. A apresentação explicativa só pode ser
selecionada quando `id_etapa_atual is None` e a entrada é `text`. Não classificar
novamente esse pedido depois que o bot já solicitou o nome.

`valida_inicio_etapa1.py` reconhece expressões completas como `O que é o Supera`,
`Do que se trata`, `O que é`, `Como funciona` e `Olá! Posso ter mais informações
sobre isso?`, com ou sem saudação, acentos e interrogação. Não depender de uma
palavra solta como `informações`. Pedidos sobre outro assunto e negativas não
são aceitos por esse classificador. Dúvidas específicas continuam nos tratamentos
existentes, inclusive quando misturadas ao pedido genérico.

`MENSAGEM_INFORMACOES_INICIO_ETAPA1` é uma mensagem completa: usa o texto aprovado
com `Hoje vou te ajudar a conhecer o Supera! 🧡`, a explicação da academia para o
cérebro e um único pedido do nome. Não concatenar a abertura padrão, a pergunta
de repetição ou um rodapé adicional. O montador somente formata saudação, agente,
artigo e unidade; a seleção da variante pertence ao resolver.

Ambas as aberturas apresentam a etapa 1 sem validar o primeiro texto como nome,
sem transição para a 2 e sem contar tratamento inválido. Após o nome válido,
seguem para a mesma etapa 2: `Prazer, {nome_titular}!` e `Então, o Supera…`.
Não há flag, coluna ou nova etapa para lembrar qual abertura foi usada.
Follow-up da etapa 1 mantém saudação sem nome + pergunta de repetição; não
reenvia essa explicação. Retry reutiliza a resposta já persistida.

Regras específicas:

- Antes de saber quem participará, a abertura não presume que a experiência
  será para o titular. Ela pode acolher a busca por informações sobre o Supera.
- Um nome de atendimento antigo não substitui a coleta do nome nesta conversa.
- No tratamento de **nome inválido**, a orientação `Olha, não consegui entender
  o seu nome. Digite só seu primeiro nome, por exemplo: Pedro.` já contém o
  pedido e o exemplo. Enviá-la sozinha, sem concatenar `MENSAGEM_REPETICAO_ETAPA1`
  nem usar `compor_tratamento`. A exceção é apenas de redação: permanece na
  etapa 1 aguardando um nome válido. Mídia, financeiro e reforço conservam suas composições com a pergunta.
  No follow-up, somente a resposta sem validação nem tratamento específico usa a repetição neutra.
- Na reação ao follow-up da etapa 1, usar `Bom te ver novamente ☺️`, sem nome antigo.
  Um nome válido informado na reação é aproveitado e leva à etapa 2; caso contrário,
  aplicar o tratamento específico identificado ou reapresentar a pergunta sem reprimenda.
- A saudação normal por três horas de inatividade não se aplica à etapa 1.
- Só a etapa 1 possui as variantes de **primeiro contato com tratamento**.
  Não reproduzir essa exceção automaticamente nas demais etapas.

## 4. As demais etapas seguem uma continuidade

Em cada etapa, separar **apresentação normal**, **tratamento com repetição**
e **mensagem própria de contexto inválido**.
Não criar tratamentos inexistentes só para preencher uma estrutura simétrica:
espera, pesquisa, encerramento e outras etapas têm contratos próprios.

O encadeamento deve ser lido como uma conversa: o bot acolhe a resposta
válida anterior e explica ou pergunta o próximo passo. Ao repetir, mantém o
assunto e a ação esperada, sem fingir que o cliente já respondeu corretamente.

### Contexto inválido: uma mensagem que já orienta a nova resposta

Esta exceção vale para **todas as etapas que tratam contexto inválido**,
incluindo nome, idade, escolhas, reserva, triagem e pesquisa. O texto explica
o que não foi compreendido e induz a responder corretamente, em uma única
fala. Não concatenar `MENSAGEM_REPETICAO`, a mensagem padrão, apresentação,
outro tratamento ou um segundo pedido equivalente. Não usar
`compor_tratamento` neste caminho.

Deixar claro que o bot **não entendeu a resposta do cliente**, sem sugerir
falha em uma ação já realizada. Por exemplo, evitar `Não consegui confirmar
sua reserva`: isso pode levar o cliente a reservar novamente e gerar duplicidade.
Preferir `Olha, não consegui entender sua resposta`, seguida da orientação
adequada à etapa, sem presumir que a reserva falhou.

Exemplo para idade do dependente:

```text
Olha, não consegui entender a idade de Lucas. Digite apenas o número, exemplo: 10.
```

Não acrescentar `Me diz, qual é a idade de Lucas?`. Quando a orientação
antiga disser apenas `Não entendi`, completá-la com a ação esperada dentro
da própria mensagem de contexto. Preservar titular e dependente, os dados
necessários (como o link da reserva), os botões/opções e o rodapé nativos,
sem duplicá-los. Os identificadores visuais nativos, como `Pergunta 1`,
continuam identificando a etapa; não são outra pergunta ou apresentação.

A única saudação de retorno que pode acompanhar esse tratamento é a de
**inatividade a partir de três horas**, quando elegível: saudação + mensagem
própria de contexto. Não acrescentar a repetição depois. A etapa 1 continua
fora da saudação de três horas. Na reação a follow-up pendente, o fluxo valida a resposta; se ela não for válida
nem corresponder a um tratamento específico, envia saudação + repetição neutra.

É uma regra de composição, não de validação. Botões, aceites por texto,
prioridades de classificação e eventos permanecem os mesmos. Não transformar
uma orientação para escolher um botão em uma restrição nova do validador.

### Titular e dependente

Quem conversa com o bot não é necessariamente quem fará a experiência.

Nos parâmetros, variáveis e campos de contexto usados para montar as mensagens,
usar `nome_titular` para quem conversa, `nome_dependente` para o dependente e
`nome_agente` para o chatbot. Não alternar esses papéis com `nome`, `nome_cliente`
ou `nome_bot` nos montadores e senders. O catálogo da triagem também recebe
`nome_dependente`; o titular continua sendo tratado como `você` nas perguntas.
Os repositórios traduzem os campos persistidos para esse contexto: a coluna
`cliente.nome` permanece igual. Esta padronização não exige migração nem altera
nomes de eventos já usados pelo mapa de transição ou contratos do painel e funil.

- Quando for para o titular, usar `você` e `sua experiência`.
- Quando for para um dependente, usar seu nome nas referências à participação,
  idade, perguntas da triagem, oferta e experiência que será reservada.
- Nas saudações de retorno, dirigir-se ao **cliente que está conversando**;
  no conteúdo seguinte, identificar o **participante** corretamente.
- Profissão e e-mail do cliente não passam a ser do dependente por causa da rota.
- A abertura da etapa 4 explica a coleta do perfil do titular ou dos dois perfis,
  conforme o destino confirmado na etapa 3. Nas duas rotas, a profissão pedida
  é de quem conversa. Tratamentos e repetição neutra usam somente a pergunta
  curta, sem repetir a explicação inicial; contexto inválido mantém sua orientação.
- `Sua reserva para a experiência de Lucas` é coerente: quem conversa realiza
  a reserva, enquanto Lucas participa da experiência.
- Na etapa de escolha do destinatário, o nome do dependente ainda pode não ter
  sido coletado. Não usar dados ausentes ou de outro atendimento para preencher.

Na apresentação da etapa 7, saudar `Maravilha, {nome_titular}! ☺️` nas duas
rotas. Para titular, continuar com `Queremos te presentear`; para dependente,
com `Queremos presentear {nome_dependente}`. A avaliação e a pergunta final
devem acompanhar quem participará. Os dois nomes chegam separadamente ao
montador; não usar o nome do dependente para saudar quem está conversando.

Mídia, financeiro e reforço continuam usando apenas tratamento + pergunta de
repetição, sem `Maravilha` nem a apresentação completa. Follow-up usa sua
saudação + repetição, e contexto inválido conserva a mensagem própria.
Nos demais pontos do atendimento, `experiência Supera gratuita` continua
adequado para reforçar a gratuidade, sem trocar todos os textos por `exclusiva`.

Alterar palavras não pode transformar a pergunta em outra decisão. O texto,
os botões, a interpretação de texto digitado e o evento precisam concordar.
Preservar os aceites legados e a flexibilidade aprovada; não endurecer os
validadores durante uma revisão de personalidade.

### Etapa 6: encaminhamentos por idade

A faixa configurável (50/60/70/80) encaminha somente titulares até 89 anos.
O caso de **90 anos ou mais** é uma regra geral para titular e dependente,
inclusive com suporte desativado, e tem mensagem própria sobre uma pequena
anamnese com um consultor. A redação não deve presumir que a pessoa conversando
será a participante quando a rota for de dependente.

Na mensagem de 90+, acrescentar uma vez o rodapé acolhedor
`Nosso time vai orientar os próximos passos. 🧡`, usando o componente de rodapé.
O botão abre o contato comercial. Não repetir a pergunta de idade, usar o
rodapé de seleção de opções ou prometer dia e horário já reservados.
Esse encaminhamento encerra o atendimento do bot; não é uma repetição de etapa.

### Mensagem pronta para o contato comercial

Todo botão de contato comercial deve abrir o WhatsApp com um pedido pronto.
Isso inclui tanto o suporte pela faixa configurada quanto o encaminhamento de
90+. O cliente ainda confirma o envio; clicar no botão não envia a mensagem.

O montador `montar_mensagem_contato_comercial_etapa6` identifica o chatbot,
a unidade e o cliente, usando os dados da conversa. Depois, adapta o pedido:

- Titular: `Me chamo {nome_titular}, tenho {idade_participante} anos e gostaria
  de reservar minha experiência Supera gratuita.`
- Dependente: `Me chamo {nome_titular} e gostaria de reservar uma experiência
  Supera gratuita para {nome_dependente}, que tem {idade_participante} anos.`

A origem comum é `Olá, vim do atendimento com {artigo} {nome_agente}, chatbot
da unidade {nome_unidade}.` O artigo acompanha o gênero do agente. A idade vem
da resposta atual da etapa 6: na rota de dependente, não inventar a idade do
titular nem atribuir a ele a idade do participante. O pedido expressa intenção
de reservar; não confirma uma reserva já realizada. Esta é a mensagem do lead
para o comercial, distinta da orientação que o bot envia antes do botão.

### Comentário livre e despedida: etapas 21 e 22

A etapa 21 não possui tratamento de contexto inválido. No fluxo normal,
qualquer comentário em texto leva à etapa 22, inclusive `ok`, `sim`, um emoji
ou pontuação. Não exigir uma opinião detalhada nem classificar o comentário
como dúvida financeira ou sobre reforço escolar. Não enviar `não consegui
entender seu comentário` nem pedir uma nova resposta por causa do conteúdo.

Permanece a orientação de mídia para escrever por texto. Recusa explícita,
texto vazio e botão antigo permitem concluir sem gravar um comentário; comentários
textuais livres são preservados. O retry deve reconstruir esse mesmo resultado.
O contrato de retomadas por follow-up permanece separado do fluxo normal.

A etapa 22 tem duas mensagens completas, sem repetição nem tratamento:

- Titular: `Estamos ansiosos para te receber na nossa unidade! 🧡`
- Dependente: `Estamos ansiosos para receber você e {nome_dependente} na nossa unidade! 🧡`

Os demais parágrafos de despedida são mantidos. Os dois caminhos de entrada,
recusa de comentário na etapa 20 e resposta na 21, precisam levar a rota e o
nome persistido do dependente ao sender. Respostas já gravadas são recuperadas
sem montar uma nova despedida. Essa variação editorial não muda o encerramento
nem o bloqueio de 30 dias.

## 5. Retornos são uma camada sobre a fala

O prefixo de retorno não deve ser copiado para cada arquivo de etapa. Sua
composição é coordenada pelo worker e aplicada ao envio e ao histórico.

### Inatividade normal: a partir de três horas

Com `followup_stage = 0`, o retorno **a partir de três horas**, inclusive,
desde o último envio confirmado do bot pode receber `Bom te ver novamente, {nome_titular} ☺️`.
O código não usa “até três horas”, nem envia uma mensagem automaticamente
quando esse prazo passa. Nome válido e horários compatíveis são necessários.

O cliente continua respondendo normalmente:

- resposta válida: saudação + apresentação da etapa de destino;
- dúvida de mídia, financeiro ou reforço: saudação + tratamento + pergunta atual;
- contexto inválido: saudação + mensagem própria de contexto, sem outra pergunta.

O prefixo não cria avanço, não impede avanço válido e não altera efeitos de
transição. Nunca acrescentá-lo novamente a uma resposta já persistida.

### Follow-up: lembrete e reação são momentos diferentes

O texto do lembrete proativo é definido em `followup_messages.py`. Ele é enviado
após sete horas e somente quando os demais critérios de elegibilidade forem
atendidos. Uma revisão de estilo não autoriza ampliar a elegibilidade do envio.

Existem duas camadas nas etapas 1–17, inclusive 8: o lembrete após 7h e a despedida
após mais 7h sem resposta desde o envio real do primeiro.

O primeiro lembrete usa `Olá, {nome_titular}! ☺️` quando o nome já foi informado
no atendimento; na etapa 1, usa `Olá! ☺️`, sem aproveitar nomes antigos.
Começa com “Queremos muito continuar te ajudando! Será um prazer receber” e oferece a
**experiência Supera gratuita** na unidade. Após `\n\n`, sempre pergunta
“Podemos continuar seu atendimento por aqui?”, nas etapas 1–17 e nas duas rotas,
inclusive depois da oferta. A pergunta final não varia conforme a etapa.
No convite, para titular usa “receber você”; para dependente com nome, “receber
você e {nome_dependente}”; para dependente ainda sem nome, “receber vocês”, sem
presumir que a experiência será para o titular. O rodapé de todas as variantes é
`Estaremos te esperando!`, sem emoji.

A despedida usa
“para aproveitar todos os benefícios” nas duas rotas e assina com `{nome_agente}`.
Na etapa 1, nunca usa nome de cadastro anterior. Na rota dependente, usa
“você e {nome_dependente} não estão preparados”, sem repetir o nome após “benefícios”;
se o nome ainda não foi coletado (nulo, vazio ou só espaços), usa a mesma mensagem
do titular, sem alterar a rota da conversa. O corpo termina com
`Fico à disposição caso precise falar comigo novamente! ☺️👋` e o rodapé é
`Abraços, {nome_agente}. 🧡`. Os dois follow-ups usam o componente de rodapé em
itálico, separado do corpo por `\n\n` (uma linha em branco). Não acrescentar prefixo
de retorno, tratamento, pergunta da etapa ou botões aos envios proativos.

O segundo envio confirmado encerra a conversa, preservando stage 2. Uma mensagem
posterior inicia outro atendimento com a mensagem inicial da etapa 1, sem prefixo
de retorno. As regras de reação abaixo valem para a conversa ainda ativa, antes
desse encerramento, e para recuperações legadas.

Na primeira reação aceita com follow-up pendente:

1. usar `Bom te ver novamente, {nome_titular} ☺️` ou `Bom te ver novamente ☺️`
   na etapa 1/sem nome autorizado, sempre uma única vez;
2. reutilizar os validadores e a ordem de prioridade dos tratamentos da etapa;
3. resposta válida: avançar normalmente, com saudação + mensagem de destino;
4. tratamento específico reconhecido: saudação + tratamento + pergunta atual;
5. sem resposta válida nem tratamento específico: saudação + repetição neutra,
   preservando participante, botões e rodapés nativos, sem orientação de contexto inválido;
6. na triagem, aceitar somente as opções canônicas; respostas inválidas repetem a
   pergunta, sem introduzir tratamentos financeiros, de mídia ou reforço;
7. zerar `followup_stage` no sucesso, junto dos efeitos, histórico e finalização da fila.
   Se não avançar, essa primeira reação não incrementa `turnos_sem_avanco`.
   Uma transição válida zera o contador normalmente; as próximas respostas seguem
   as regras normais. Uma falha reverte a transação inteira.

**Exceção da etapa 8 — oferta adiada:** qualquer reação processada pelo flow
com follow-up pendente leva diretamente à etapa 9. Não enviar novamente a
mensagem inicial da 8, uma variante de repetição, sua despedida ou o Instagram.
A etapa 8 não possui mensagem de repetição. A resposta contém o prefixo de
follow-up uma única vez e a oferta da etapa 9, preservando titular/dependente,
botões e rodapé. Mesmo `Quero reservar` nessa reação apenas leva à 9; a próxima
resposta será validada pela etapa 9.

O worker reutiliza o resolver e a transição normal `8 → cliente_retornou → 9`.
O histórico da reação permanece na 8; a resposta do bot é registrada na 9.
Avanço, resposta e conclusão do follow-up são confirmados juntos. Uma falha
reverte esses efeitos; recuperar uma resposta já confirmada não reenvia nem
zera um ciclo posterior. Essa regra também vale para retomada legada pendente.

Esse prefixo substitui a saudação de três horas; não se somam os dois. Uma
saudação própria, como a da etapa 9, também deve ser suprimida quando já houver
saudação externa. A fala inteira deve ser acolhedora, sem parecer um novo
primeiro encontro ou anunciar um avanço que não ocorreu.

O catálogo de reapresentação contém etapas legadas que não são elegíveis para
um novo lembrete. Sua existência não autoriza envio proativo nessas etapas.
Consulte o [contrato de follow-up](../../../../REGRAS_DE_NEGOCIO.md#follow-up-de-inatividade-e-reação-do-cliente).
As exceções propostas no plano futuro de `user_id` não estão ativas neste código.

## 6. A triagem tem um contrato próprio

Na base atual, as seis perguntas são as etapas 12–17. Elas não possuem os
tratamentos específicos de mídia, financeiro e reforço escolar das etapas
comerciais. Existe apenas a mensagem própria de **resposta da triagem inválida**,
que orienta responder à pergunta já apresentada usando uma das opções
`Nunca`, `Às vezes` e `Frequentemente`. Não concatenar novamente a pergunta.

As perguntas canônicas estão em `core/triagem/perguntas.py`; não duplicá-las
nos arquivos de mensagens nem reescrever seu significado numa revisão de tom.
A etapa 11 é a introdução à triagem e conserva seus próprios tratamentos.

**Na etapa 11, o participante já está definido.** Manter versões explícitas
para titular e dependente na mensagem inicial, na repetição e no contexto
inválido. Para o titular, usar `sua triagem` e `seu cérebro`; para dependente,
usar `a triagem de {nome_dependente}` e `o cérebro de {nome_dependente}`. Não substituir as duas
rotas por uma fala genérica sobre `quem participará`, nem falar da triagem
do titular quando quem participará é o dependente.

A mensagem inicial apresenta as seis perguntas e sua finalidade; a repetição
retoma apenas o convite para iniciar e a finalidade da triagem. Financeiro,
mídia e reforço usam essa repetição com o participante correto. Contexto inválido
tem mensagem autônoma, sem concatenar outra pergunta. Inatividade e follow-up
preservam a rota e aplicam seu prefixo uma vez, segundo seus contratos.

O contexto da etapa 10 fornece o nome para apresentar a 11; a própria 11 e o
retorno de follow-up relêem o participante persistido. Dependente sem nome é
inconsistência, nunca motivo para usar silenciosamente a mensagem de titular.
Revisões de texto devem conferir também a continuidade nas perguntas 12–17,
que citam o nome do dependente tanto na faixa infantil quanto na adulta.

As seis perguntas continuam sujeitas aos dois caminhos de retorno:
ambos validam a resposta; no follow-up, uma opção válida avança e é salva,
enquanto uma entrada inválida reapresenta a pergunta sem tratamento genérico. Manter o número da pergunta, a faixa
etária, o nome do dependente e o rodapé de opção única. Não acrescentar oferta
comercial ou celebração a cada resposta da triagem.

## 7. Organização dos arquivos e do código

Cada etapa é dona da sua mensagem padrão e da sua mensagem de repetição.
Na etapa 8 existe somente a mensagem inicial: o retorno apresenta a etapa 9.
Cada tipo de tratamento é dono da orientação compartilhada. O arquivo da
etapa importa o montador do tratamento e entrega a ele sua repetição pura:
**tratamento → ponte, quando necessária → repetição da etapa**.
Contexto inválido é a exceção: sua mensagem completa pertence à etapa e não
passa pelo compositor de orientação + repetição.

| Arquivo | Responsabilidade |
|---|---|
| `etapaN_messages.py` | Mensagem padrão, repetição pura, contexto inválido autônomo, variantes de participante e composição dos demais tratamentos. |
| `tratamentos/financeiro.py` | Explicação sobre investimento e gratuidade da experiência, seguida da repetição recebida. |
| `tratamentos/midia.py` | Orientação para responder por texto; só oferece opções quando a etapa realmente possui botões. |
| `tratamentos/reforco_escolar.py` | Explicação sobre a proposta do Supera, seguida da repetição recebida. |
| `tratamentos/retorno_inatividade.py` | Elegibilidade e saudação de retorno a partir de três horas. |
| `tratamentos/retorno_followup.py` | Saudação da reação ao follow-up, inclusive a forma sem nome. |
| `tratamentos/composicao.py` | Compositores distintos para mensagem inicial e tratamento, com formatação compartilhada e aplicação única do prefixo de retorno. |
| `componentes_compartilhados.py` | Cabeçalhos e rodapés compartilhados. Mantém os imports antigos de inatividade por compatibilidade. |
| `followup_messages.py` | Primeiro lembrete e despedida personalizada do segundo. Reexporta a saudação antiga por compatibilidade. |
| `tratamentos_universais.py` | Fachada de compatibilidade dos imports antigos; não possui outra cópia dos textos. |
| `triagem_componentes.py` | Opções, rodapé e orientação autônoma de contexto comuns às seis perguntas; não contém as perguntas canônicas. |
| `README.md` | Este contrato de composição, personalidade e revisão. |

Ao criar ou reorganizar um arquivo, usar blocos identificados nesta ordem:

1. finalidade da etapa e exceções relevantes;
2. constantes da mensagem padrão e da repetição, com variantes de participante;
3. montador da apresentação normal, aceitando `repeticao=True` quando cabível;
4. montadores de tratamento: importar e compor com a repetição, exceto contexto,
   que retorna sua própria mensagem completa;
5. botões, cabeçalhos e rodapés específicos;
6. auxiliares privados de composição e validação de dados de apresentação.

Na etapa 1, reservar blocos distintos para os três grupos da seção 3. Usar
`inicio` para as versões exclusivas de primeiro contato, sem confundi-las
com o tratamento após a pergunta do nome.

Constantes podem usar `MENSAGEM_`, `PERGUNTA_`, `PREFIXO_`, `BOTAO_`,
`CABECALHO_` e `RODAPE_`; montadores usam `montar_...`. Não renomear toda a
API existente apenas por estética. Ao mover declarações, preservar a ordem
de dependências e todos os imports dos consumidores.

### Comentários que explicam a organização

Os comentários da etapa 7 são a referência para tornar o papel de cada bloco
visível durante a leitura. Eles devem explicar **onde o trecho é usado e por
que ele está separado**, especialmente quando a mesma pergunta participa da
mensagem inicial e da repetição.

Usar `### TÍTULO DO BLOCO` para as divisões principais, como na etapa 7, e
`# Explicação curta` para detalhes locais. Ambos são comentários Python.
Escrever em português, próximos ao trecho correspondente, sem depender de
números de linha ou de explicações dadas nesta conversa.

Exemplo de composição com um fragmento compartilhado:

```python
### APRESENTAÇÃO INICIAL DO TITULAR
APRESENTACAO_TITULAR = (
    "Maravilha, {nome_titular}! ☺️ Queremos te presentear com uma "
    "*demonstração prática gratuita* na nossa unidade!\n"
)

### TRECHO USADO NA MENSAGEM INICIAL E NA REPETIÇÃO
MENSAGEM_REPETICAO_TITULAR = "Vamos reservar sua *experiência Supera exclusiva*?"

### MENSAGEM INICIAL: APRESENTAÇÃO + REPETIÇÃO
MENSAGEM_PADRAO_TITULAR = compor_mensagem_inicial(
    APRESENTACAO_TITULAR,
    MENSAGEM_REPETICAO_TITULAR,
)

### FINANCEIRO: ORIENTAÇÃO + REPETIÇÃO, SEM A APRESENTAÇÃO
def montar_mensagem_financeiro():
    return montar_mensagem_tratamento_financeiro(MENSAGEM_REPETICAO_TITULAR)


### CONTEXTO INVÁLIDO: MENSAGEM PRÓPRIA, SEM CONCATENAR A REPETIÇÃO
def montar_mensagem_contexto_invalido():
    return (
        "Olha, não consegui entender se você quer reservar sua experiência. "
        "Escolha Reservar agora ou Talvez mais tarde."
    )
```

Aplicar estes cuidados:

- Identificar mensagem inicial, pergunta de repetição e composição quando
  essa separação ajuda a entender o arquivo. Uma mensagem inicial já completa
  não deve receber um comentário dizendo que ainda será concatenada.
- Dizer que o fragmento é compartilhado com a inicial **somente quando isso
  acontece no código**. Algumas etapas têm perguntas diferentes para cada momento.
- Indicar titular e dependente nos blocos que possuem as duas rotas. Os
  tratamentos devem preservar o participante, inclusive no contexto autônomo.
- Explicar exceções junto do código: contexto inválido já pede a resposta;
  etapa 8 não se repete e retorna para a 9; etapa 9 evita somar saudações.
- Na triagem, comentar que a pergunta vem do catálogo central na apresentação
  e no follow-up; contexto inválido usa sua orientação própria, sem repeti-la.
  Não criar seções de tratamentos
  financeiros, mídia ou reforço onde esses tratamentos não existem.
- Comentar a entrada de um grupo de funções, sem repetir a mesma explicação
  em cada função nem narrar operações óbvias linha por linha. Preservar
  comentários existentes que já expliquem corretamente o bloco.
- Descrever a responsabilidade real: o montador **formata a mensagem**;
  não valida a resposta do cliente, decide avanço, consulta banco ou envia.
- Atualizar o comentário junto com o código quando mudar a composição.
  Ele deve descrever o comportamento vigente, não uma intenção futura.

A etapa terminal não precisa de seções artificiais de apresentação/repetição
se possui apenas uma mensagem de encerramento. Os comentários organizam a
leitura; não exigem que todas as etapas tenham as mesmas funções.

### Mensagem inicial e tratamento têm compositores diferentes

Quando a pergunta da repetição também encerra a mensagem inicial, declarar
esse fragmento uma única vez e compartilhá-lo:

```python
APRESENTACAO = "Vamos conhecer o Supera! ☺️\n"
ORIENTACAO = "Olha, responda por texto para continuarmos.\n"
MENSAGEM_REPETICAO = "Me diz, qual é a sua profissão?"

MENSAGEM_PADRAO = compor_mensagem_inicial(
    APRESENTACAO,
    MENSAGEM_REPETICAO,
)

MENSAGEM_TRATAMENTO = compor_tratamento(
    ORIENTACAO,
    MENSAGEM_REPETICAO,
)
```

- `compor_mensagem_inicial` monta **apresentação + repetição** na entrada da
  etapa. Por exemplo, a oferta com `Maravilha!` termina em `Vamos reservar…`.
- `compor_tratamento` monta **orientação + ponte opcional + repetição**.
  Recebe apenas a pergunta reutilizável, nunca a mensagem padrão completa.
  Não é usado em contexto inválido, cuja mensagem já contém a orientação completa.
- Ambas reutilizam `_concatenar_fragmentos` internamente. Esse auxiliar
  apenas concatena: os espaços e as quebras estão nas variáveis de mensagens.
  Não escolhe o cenário nem decide o fluxo.

Não inserir a pergunta em `APRESENTACAO` se ela já será acrescentada pelo
compositor: isso duplicaria o trecho final. Quando apresentação e repetição
tiverem redações diferentes, manter suas variantes sem forçar o compartilhamento.

A exceção de primeiro contato da etapa 1 permanece: o tratamento monta a
orientação com a pergunta; o compositor inicial acrescenta a apresentação
uma única vez. Após essa entrada, mídia, financeiro e reforço usam orientação e
repetição; contexto inválido usa sua mensagem própria. Prefixos de inatividade
e follow-up continuam na camada de retorno.

Exemplo do padrão aplicado à confirmação da etapa 3:

```python
MENSAGEM_PADRAO_TITULAR = "Você confirma que esse atendimento é para você? ☺️"
MENSAGEM_REPETICAO_TITULAR = "Me confirma: esse atendimento é para você?"

# O montador importado acrescenta a orientação antes desta pergunta.
mensagem = montar_mensagem_tratamento_financeiro(MENSAGEM_REPETICAO_TITULAR)
```

As variantes para dependente seguem a mesma estrutura. O texto de repetição
pode compartilhar conteúdo com o padrão, mas não carrega sua celebração,
apresentação ou despedida. Não manter uma pergunta diferente para cada
tratamento de mídia, financeiro ou reforço: eles reutilizam a repetição da rota.

Orientações de contexto exclusivas de uma etapa (nome, idade, nota fora da
escala etc.) continuam nela como mensagens completas, sem `compor_tratamento`
nem mensagem de repetição. Não mover regras específicas para um catálogo
genérico. Etapas terminais e perguntas canônicas não precisam de variantes
artificiais. A exceção de contexto vale para todas as etapas, não só para nome.

Nos retornos, a saudação é aplicada uma única vez pelo transporte coordenado
pelo worker. Isso preserva a ordem **retorno → tratamento, se o fluxo normal
o escolher → repetição** na inatividade, exceto contexto: **retorno → mensagem
própria de contexto**. No follow-up, o worker usa os mesmos validadores e
tratamentos específicos; somente a resposta inválida sem tratamento específico
seleciona a repetição neutra (`repeticao=True`) sem mensagem de contexto.
Na triagem, usa a pergunta canônica sem esse parâmetro. A etapa 9 suprime
sua saudação própria quando recebe repetição ou `incluir_saudacao=False`.

O nome do dependente deve chegar também aos tratamentos da reserva por link,
não apenas à apresentação normal. O contexto consulta o participante da
mesma conversa/unidade; ausência de nome em uma rota dependente é erro de
contexto, não autorização para trocar a mensagem para a rota titular.

### Fronteiras de responsabilidade

```text
contexto/worker: escolhe cenário, participante e transição
        -> sender: usa o montador e envia
            -> messages: monta o conteúdo com os dados recebidos
```

`messages` não consulta banco, não importa PyWa, não valida a resposta do
cliente, não seleciona destino e não grava histórico. Pode validar os dados
necessários para montar a apresentação. Senders e worker devem conservar no
histórico a mesma fala que foi enviada, inclusive prefixos e cabeçalhos.

O controle do prefixo está em `pywa_functions/cliente.py`; sua aplicação aos
fluxos está em `flow_sender.py`, `retomada_followup.py` e `repeticao_followup.py`. Essa separação deve
permanecer. Não criar uma cópia dos fluxos dentro da pasta de mensagens.

## 8. Como revisar uma alteração

Ler o conjunto **mensagem anterior → resposta do cliente → próxima fala**,
não apenas uma constante isolada. Conferir os cenários pertinentes:

- entrada normal e tratamento, com os dados reais esperados em cada momento;
- titular e dependente, sem trocar destinatário, nome ou idade;
- retorno por inatividade com resposta válida e com resposta inválida;
- contexto inválido completo por si só, sem concatenar a pergunta de repetição;
- reação ao follow-up com saudação única: avanço válido, tratamento específico
  ou repetição neutra; preservar a exceção de 8 para 9;
- botões e rodapés, sem repetição e com a mesma ação aceita pelo validador;
- nomes ausentes e dados de atendimentos anteriores;
- texto efetivamente enviado e registro no histórico;
- recuperação com resposta persistida, sem novo envio.

Não basta contar emojis ou procurar uma palavra no arquivo: a fala final
precisa fazer sentido. Usar os testes de mensagens, saudação e follow-up
quando a mudança afetar composição, dados, envio ou retomada. Correções
ortográficas simples não exigem criar testes que espelhem cada frase.

Planos futuros que substituem arquivos completos devem preservar este
contrato e reconciliar suas mensagens com a base mais recente. A numeração
de etapas de um plano não deve ser antecipada no código em produção.

## 9. Aperfeiçoamentos aplicados em 21/09/2026

- **Etapa 2:** a repetição retoma a pergunta do destinatário sem `Prazer`.
- **Etapa 8:** a mensagem com Instagram pertence somente à entrada na etapa.
  Qualquer reação ao follow-up avança diretamente para a 9, sem repetir a 8.
- **Mídia:** a orientação compartilhada usa linguagem simples e acolhedora,
  com texto ou botões conforme os recursos reais da etapa.
- **Etapas 3–6:** a confirmação e a coleta de profissão, nome do dependente
  e idade ganharam acolhimento moderado, sem alterar o que é perguntado.

Quando precisarem repetir a etapa, os retornos usam a repetição neutra: não
reapresentam o agente na etapa 1, não comemoram novamente a oferta e não agradecem
outra vez pelas perguntas antes do link. Desde a revisão de 23/09/2026, a reação
ao follow-up é validada normalmente, com a exceção da etapa 8 descrita acima.
Os validadores, eventos e critérios de elegibilidade permanecem os mesmos.


### Reconhecimento na recuperação da etapa 6

`reconhecer_encerramento_etapa6` identifica os corpos conhecidos de suporte,
universal, titular menor e dependente abaixo do mínimo. Tolera espaçamento e
prefixo de retorno somente na leitura; não modifica as quebras das mensagens.
O worker comprova o vínculo da resposta com a entrada. Os nomes antigos que
contêm `acima_99` permanecem como contrato interno; o resolver aplica universal 90+.
````

## Passo 31 — Alterar `callback/README.md`

Documentar filtro, detalhes e tabela de conversas na configuração atual.

Base SHA-256: `dffb67585e15ed2eae0c8dcab2fcc54afb1a6517e50f6c3ba7c4ed01b1d19e43`. Conteúdo completo proposto: **383 linhas**.

````markdown
# Aplicativos Django: webhook e monitoramento

Projeto Django que reúne o webhook e o aplicativo de monitoramento por unidade.
O webhook recebe eventos da Meta, valida a entrada e persiste mensagens aceitas
na fila. O processamento da conversa pertence ao worker. O monitoramento oferece
login com autenticação Django, autorização por unidade, consulta responsiva de
conversas e indicadores, além da exportação de contatos.

Documentos centrais:

- [Regras de negócio](../REGRAS_DE_NEGOCIO.md)
- [Padrões de arquitetura](../PADROES_DE_ARQUITETURA.md)
- [Portal do projeto](../README.md)

## Estrutura

```text
callback/
├── callback/              configuração Django
├── webhook/
│   ├── admin.py           operações administrativas
│   ├── models.py          mapeamento das tabelas
│   ├── urls.py            rota /webhook
│   ├── views.py           borda GET/POST
│   └── services/          fluxo HTTP e anti-flood
├── monitoramento/        aplicativo do painel por unidade
│   ├── __init__.py
│   ├── apps.py           registro MonitoramentoConfig
│   ├── forms.py          credenciais nativas e autorização antes do login
│   ├── views.py          login, saída, painel, APIs de leitura e CSV
│   ├── urls.py           rotas públicas e privadas do monitoramento
│   ├── monitoramento_guard.py  autorização da sessão e dos recursos
│   ├── periodos.py       janelas de consulta aceitas pelo servidor
│   ├── apresentacao.py   consolidação, perfis, botões e CSV Google/essencial
│   ├── services.py       orquestra leituras da unidade autorizada
│   ├── templates/monitoramento/  login, painel e acesso negado
│   └── static/monitoramento/     estilos, interação e logo ESL Tech
│       ├── css/
│       ├── js/
│       └── img/
└── manage.py
```

Arquivos principais de `services`:

- `post_flow.py`: validações e transação da fila;
- `meta_signature.py`: assinatura `X-Hub-Signature-256`;
- `bloqueio_meta_guard.py`: consulta da lista local de bloqueio, promoção de
  suspeita e nova tentativa de bloqueio na Meta;
- `flood_guard.py`: Redis, banco, memória e bloqueio Meta;
- `populating_fila_mensagens.py`: parse e inserção usando cursor recebido;
- `alerta_flood_memoria.py`: alerta local quando banco e Redis falham.

## Endpoint

```text
GET  /webhook
POST /webhook
```

A rota não possui barra final. O `GET` atende à verificação inicial da Meta. O
`POST` recebe eventos reais.

O `GET` devolve `hub.challenge` quando `hub.mode=subscribe` e
`hub.verify_token` coincide com `META_WEBHOOK_VERIFY_TOKEN`; nos demais casos,
devolve `Webhook ativo` com HTTP 200.

O limite do body é configurado por `WEBHOOK_MAX_BODY_BYTES` (padrão: 256 KiB).
Quando `META_WEBHOOK_SIGNATURE_REQUIRED=true`, o POST exige HMAC-SHA256 do body
original, calculado com `META_APP_SECRET` e comparado com
`X-Hub-Signature-256` por `hmac.compare_digest`. Secret vazio, header ausente ou
assinatura inválida resultam em 403. O padrão dessa flag no código é `False`;
a exigência efetiva depende da configuração do ambiente.

## Ordem do POST

```text
Content-Type
-> tamanho do body
-> assinatura Meta
-> parse JSON
-> classificação do evento Meta
-> lista local de bloqueio / suspeita de bot
-> anti-flood
-> unidade ativa
-> conversa bloqueada
-> preparação da mensagem
-> transação da fila
-> resposta HTTP
```

O webhook não envia etapas, não avança conversa e não executa dequeue.
O follow-up é disparado pelo worker próprio após consulta de inatividade; não
exige um evento recebido nem cria uma entrada fictícia na fila. A reação real
do cliente passa pelas mesmas barreiras de assinatura, bloqueio, flood e turno.

Eventos contendo apenas `statuses` retornam 200 sem processamento na V1.
Eventos sem `messages`/`statuses`, ou com ambos, também retornam 200 sem
enfileirar. Esses descartes ocorrem antes dos controles de bloqueio e flood.

## Contrato HTTP

| Cenário | HTTP | Resultado |
|---|---:|---|
| Mensagem inserida | 200 | `status=ok` |
| Descarte por regra de negócio | 200 | `status=ignored` ou `status=ok`, conforme o ponto do fluxo |
| JSON inválido | 200 | `status=ignored`, `reason=invalid_json` |
| Falha de conexão, inserção ou commit da fila | 503 | `status=unavailable`, `reason=insert_exception` |
| Falha ao confirmar a unidade no banco após cache sem resposta conclusiva | 503 | `status=unavailable`, `reason=unit_validation_unavailable` |
| Falha de Redis e banco ao validar bloqueio de conversa | 503 | `status=unavailable`, `reason=conversation_block_validation_unavailable` |
| Falha na consulta ou promoção da lista local de bloqueio | 503 | `status=unavailable`, `reason=blocklist_validation_unavailable` |
| Flood detectado sem conseguir consultar ou persistir o bloqueio local | 503 | `status=unavailable`, `reason=flood_<origem>_banco_indisponivel` ou `flood_<origem>_persistencia_local_falhou` |
| Erro inesperado identificável, nas três primeiras ocorrências por WAMID | 503 | `status=unavailable`, `reason=unexpected_error_retry`, com `attempt` |
| Erro inesperado com limite esgotado ou contador indisponível | 200 | `status=ignored`, `reason=unexpected_error_retry_exhausted` ou `unexpected_error_retry_unavailable` |
| Assinatura inválida | 403 | `status=forbidden` |
| Payload grande | 413 | `status=payload_too_large` |
| `Content-Type` inválido | 415 | `status=unsupported_media_type` |
| `Content-Length` inválido | 400 | `status=bad_request` |
| Método não permitido | 405 | `status=method_not_allowed` |

Turno ocupado, duplicidade, unidade inativa, conversa bloqueada e flood com
bloqueio local persistido são descartes com HTTP 200. Falhas operacionais de
validação ou persistência usam os motivos 503 acima. Em motivos de flood,
`<origem>` é `redis`, `banco` ou `memoria`.

O limite de três respostas 503 aplica-se somente ao tratamento genérico de
erro inesperado, com contador Redis por WAMID e TTL de sete dias renovado a cada
ocorrência. Sem WAMID ou sem Redis, esse tratamento retorna 200 com
`unexpected_error_retry_unavailable`; os demais cenários 503 não passam por
esse contador.

## Turno e duplicidade

O par lógico é:

```text
cliente_telefone + id_phone_unidade
```

`core/repositories/seguranca/turno_cliente.py` usa advisory lock transacional para impedir
corridas. Enquanto existir fila aberta sem resposta própria do bot, mensagens
posteriores do mesmo par são descartadas.

Mensagens com timestamp anterior a uma interação já registrada também são
descartadas como reentregas fora de ordem. Se todas as filas abertas já têm sua
própria resposta do bot com `status_envio=sent`, o turno pode ser liberado.

`id_hash_msg` é único. Reentregas da Meta não criam duas linhas; o insert utiliza
`ON CONFLICT DO NOTHING`.

## Anti-flood

A regra atual mede cada cliente dentro de cada unidade:

```text
15 WAMIDs distintos em 5 segundos
chave = wa_id_cliente + phone_id_unidade
```

Clientes diferentes da mesma unidade não compartilham contador. A ordem dos
fallbacks é Redis, banco e memória local. No Redis, deduplicação por WAMID e
incremento são atômicos, com janela fixa e deduplicação por duas horas.

O bloqueio utiliza `core/integrations/whatsapp/tools/usuarios.py`. O fluxo
persiste a intenção em `chatbot.cliente_bloqueado_meta` antes de chamar a Meta.
Se a Meta falhar, mantém o bloqueio local e descarta a mensagem com HTTP 200;
uma nova mensagem desse par tenta bloquear na Meta novamente. Se o banco
impedir a persistência, retorna 503 sem chamar a Meta. Unidade não cadastrada
é descartada sem bloqueio externo.

Antes do anti-flood, `bloqueio_meta_guard.py` verifica essa lista local e
também promove conversas que atingiram o limite de turnos sem avanço. A
promoção é confirmada no banco antes da chamada externa.

Relatórios e reconciliação manual ficam em
`utilitarios/monitoring/blocked_users.py`.

O relatório é somente leitura e possui duas conferências distintas:

- bloqueios: compara
  `(waba_id, phone_id_unidade, wa_id_cliente)` entre a lista da Meta e
  `chatbot.cliente_bloqueado_meta`;
- registros Cloud API: percorre o `waba_id` de cada unidade e compara os
  `phone_number_id` retornados pela Meta com `chatbot.unidade`.

Ele também separa falhas de coleta e vínculos divergentes; não bloqueia,
desbloqueia, registra ou remove dados automaticamente.

## Transações

`post_flow.py` é dono da conexão usada para enfileirar:

```text
abrir conexão -> povoando_fila -> commit/rollback -> close
```

`populating_fila_mensagens.py` recebe cursor e não controla conexão.

As transações independentes do anti-flood pertencem a `flood_guard.py`; a
consulta e promoção da lista local pertencem a `bloqueio_meta_guard.py`. Essa
separação está detalhada em
[Padrões de arquitetura](../PADROES_DE_ARQUITETURA.md).

## Django Admin

O Admin é majoritariamente somente leitura. As exceções operacionais são:

- criação, edição e exclusão individual de unidade;
- criação, edição e exclusão de configuração de integração do Funil por unidade;
- desbloqueio individual de cliente bloqueado na Meta.

Cada unidade exige `nome_unidade`, `nome_agente` e `genero`. O campo `genero`
oferece no formulário somente `Masculino` e `Feminino`; ele controla o artigo
usado para apresentar o agente nos inícios padrão, de mídia, financeiro e de
tratamento de reforço escolar da etapa 1.

`waba_id` e `phone_number_id` ficam somente leitura após a criação. O Admin
também expõe `idade_minima_suporte` e `email_obrigatorio`. O seletor de suporte
aceita Desativado, 50+, 60+, 70+ e 80+. Toda unidade exige `numero_comercial`
brasileiro válido, inclusive com suporte desativado. A universal 90+ vale para ambas as rotas.
Somente o titular é alcançado; o limite não altera a dispensa de e-mail dos 60+.

No Admin, criação/exclusão de unidade e desbloqueio individual seguem
Meta-first. Se a Meta falhar, a alteração local correspondente não é
confirmada. Se a Meta concluir e uma etapa local posterior falhar, a operação
externa não é compensada automaticamente: a unidade exige conferência manual.
O desbloqueio também zera `turnos_sem_avanco` das conversas ativas do par.
Essa ordem administrativa é diferente do bloqueio preventivo do webhook,
que persiste primeiro a lista local.

## Cadastro e autorização do monitoramento

O modelo `Unidade`, com `managed = False`, inclui `id_usuario_monitoramento`,
um `OneToOneField` opcional para o usuário do Django. No Admin da unidade,
**Usuário de monitoramento** seleciona uma conta comum criada em **Usuários**.
Uma conta não pode ser vinculada a duas unidades; várias unidades podem ficar
sem conta. Excluir o usuário limpa o campo com `SET_NULL` e preserva a unidade.
O formulário permite contas inativas para preparar o cadastro, mas elas não
passam pela autorização. A edição mantém o fluxo administrativo existente da
unidade; o vínculo de acesso é consultado diretamente no banco, sem cache.
As regras completas estão em [Regras de negócio, 19.6](../REGRAS_DE_NEGOCIO.md#196-contas-de-monitoramento-por-unidade).

O aplicativo `monitoramento` está registrado por
`monitoramento.apps.MonitoramentoConfig` em `callback/settings.py`. As rotas são
incluídas no URLconf do projeto; `STATIC_URL=/static/` permite carregar os assets
também nas URLs aninhadas. O login não cria tabelas nem migrações adicionais.

`monitoramento/monitoramento_guard.py` oferece
`exigir_acesso_monitoramento(request, id_conversa=..., id_mensagem=...)`.
Somente `request.user.pk` identifica a conta. Os identificadores dos recursos
são opcionais, mas, quando fornecidos, são conferidos na mesma consulta que
valida o vínculo e a conta no banco. O retorno informa a unidade autorizada;
falhas de autorização geram `PermissionDenied`, sem distinguir recurso ausente
de recurso de outra unidade. Erros de banco propagam e não liberam acesso.

`forms.py` estende `AuthenticationForm`: o Django verifica o hash da senha do
username informado, depois `exigir_acesso_usuario_monitoramento` valida a conta
e seu vínculo antes de criar a sessão. Não há consulta própria de senhas.
Usuário inexistente e senha incorreta recebem o mesmo aviso, sem confirmar a
existência de contas. Contas inativas, administrativas ou sem unidade não entram.

- `GET /login/`: formulário responsivo com logo vetorial extraída do material
  da ESL Tech, sem dependências visuais externas.
- `POST /login/`: autenticação com CSRF, sessão Django e destino fixo. O
  parâmetro `next` não controla o redirecionamento. Falhas de banco retornam 503
  com aviso genérico; a senha não é reapresentada nem registrada pela view.
- `POST /sair/`: encerra a sessão com CSRF; GET não executa logout.
- `GET /`: entrega o painel privado e responsivo.
- `GET /dados/conversas/`: resumo e lista consolidada dos contatos.
- `GET /dados/conversas/<id_cliente>/`: histórico do contato dentro da unidade.
- `GET /dados/relatorio/`: indicadores, perfis, satisfação, atividade e etapas.
- `GET /dados/relatorio/faixa-etaria/`: consulta por `idade_minima`, `publico`
  (`titulares`, `dependentes` ou `todos`) e `periodo`, somente na unidade autorizada.
- `GET /contatos.csv`: exporta todos os contatos ou somente os elegíveis.
  Por padrão, o arquivo segue as 36 colunas, a grafia e a ordem do modelo oficial do Google
  Contacts para que e-mail, telefone, observações e marcador sejam reconhecidos.
  Com `formato=essencial`, entrega somente `Nome`, `E-mail` e `Telefone`, com
  telefone brasileiro sem o prefixo internacional `+55` (preservando o DDD),
  nome completo na primeira coluna, separador `;` e UTF-8 com BOM para planilhas
  em pt-BR. Os quatro downloads usam o mesmo período e escopo autorizado.

O login bem-sucedido retorna a `/`. A página e cada endpoint de dados chamam
`exigir_acesso_monitoramento`; nenhum deles aceita unidade escolhida em URL,
query string ou JavaScript. Depois do guard, cada SQL de
`core/repositories/monitoramento/painel.py` recebe e aplica o `id_unidade`
autorizado. O guard não modifica consultas posteriores nem concede acesso ao
Admin.

O navegador atualiza a seção de conversas a cada 10 segundos e a de relatórios
a cada 30 segundos, somente enquanto a página está visível. Voltar à aba força
uma nova leitura. Não há WebSocket nem tarefa periódica no servidor para o
painel: as requisições são atendidas pelo mesmo Gunicorn/Django do webhook.
Mensagens são carregadas somente quando um contato é aberto.

O follow-up confirmado aparece como mensagem de texto do bot na conversa e
participa da contagem de mensagens no período. Não há cartão exclusivo,
controle de disparo nem edição de stage no monitoramento. A lista mostra os
perfis junto da data: `DP -18`, `DP 18–59`, `DP 60+`, `18–59` e `60+`, conforme
os dados disponíveis; o cabeçalho da conversa mantém a descrição completa.

Conversas prioriza a lista e o histórico, sem repetir os quatro indicadores do
relatório. O layout compacto preserva as fontes e ajusta o espaço do chat pela
altura real do cabeçalho e do aviso, inclusive ao girar o celular. Em telas
estreitas, lista e conversa alternam com o botão de voltar. Os downloads
essenciais ficam logo abaixo dos downloads para Google Contatos em Relatórios.

O padrão é todo o histórico até o instante da requisição. Também existem os
períodos 24 horas, 7 e 30 dias, 2, 3 e 6 meses e 1 ano. Os períodos finitos são
comparados à janela imediatamente anterior de igual duração. A distribuição por
etapa representa o estado atual da conversa mais recente de cada contato com
atividade no período; não reconstrói a etapa histórica. Como o histórico
persiste texto e tipo, mas não o
payload original dos botões, o painel apresenta como referência os botões do
catálogo atual da etapa, sempre desabilitados.

O painel é somente leitura. Os filtros, a pesquisa, os seletores de período e os
downloads não alteram registros. As regras `idade_minima_suporte`, `email_obrigatorio`
e `bpa_ativo` vêm da unidade. O CSV completo preserva campos ausentes vazios; o
CSV elegível exige nome, e-mail estruturalmente válido e telefone em formato
internacional. Essa regra vale tanto para Google CSV quanto para CSV essencial;
nenhum dos formatos acrescenta etiquetas comerciais ou datas ao nome.

A tabela **Encaminhamentos e encerramentos por idade** conta conversas pela data
de encerramento no período. Exibe somente motivos compatíveis com suporte e BPA
atuais, separando a universal 90+ de titulares e dependentes e os menores sem contato.
Legados sem limite identificado não são atribuídos à configuração atual.
O filtro **Comercial** substitui Continuações: mostra a última conversa por
cliente/unidade com motivo de idade. A tag histórica independe da configuração
atual; uma conversa nova remove a tag. A legenda fica no botão informativo.
Funil/Avaliadas mantêm seus critérios e dados, com prioridade visual da tag especial.
Detalhes usam o par de mensagens do histórico mesmo após exclusão da fila/dependente.

### Consulta de faixa etária personalizada

O card fica abaixo de Evolução da demanda/Satisfação e antes de Perfil dos
atendimentos. Enter e Consultar executam a mesma consulta. Aceita idade inteira
positiva de até três dígitos e somente um público; a API também recusa parâmetros
duplicados. Não exige migração nem altera dados.

- Usa as idades atualmente cadastradas, não uma reconstrução histórica. Considera
  conversas com mensagem do cliente no período selecionado, em `[início, fim)`;
  sete dias são 168 horas. Idades ausentes não são estimadas.
- Titular conta uma vez por cliente/unidade, mesmo com várias conversas. Somente
  conversas da rota titular contribuem para sua idade e seu envio ao funil.
- Cada `id_dependente` identificado conta separadamente, inclusive nomes iguais
  em conversas diferentes, por decisão explícita do produto. Não deduplicar por
  nome. O total de participantes pode superar o de números de contato, mostrado
  separadamente no resultado. A idade considerada é a do dependente atendido.
- Funil conta apenas `funil_envios.status = 'sent'`, com `enviado_em` no mesmo
  período, ligado às conversas consideradas. Não transfere o envio entre titular
  e dependentes, nem confunde elegibilidade ou encaminhamento comercial com envio.
- O card Dependentes por titular agrupa a quantidade desses cadastros por titular
  no período, independentemente da idade mínima consultada. Placeholders ainda
  sem nome e idade não entram; dependente identificado sem idade entra nessa
  distribuição, mas não na consulta de faixa etária.
- Atualizações automáticas preservam formulário, foco e resultado. A consulta
  mostra o horário da leitura; para atualizá-la, clicar novamente em Consultar.
  Mudar idade/público/período limpa o resultado anterior; respostas atrasadas são
  descartadas. Falhas mostram um aviso, nunca um zero inventado.

Não há cadastro, recuperação/troca de senha nem bloqueio por número de tentativas
no portal. Contas e senhas continuam administradas pelo proprietário no Django
Admin. Senhas ficam sempre mascaradas no campo; os formulários usam o mecanismo
nativo de sessão e proteção CSRF. `falha_csrf` personaliza o aviso em português
somente nas rotas de monitoramento, preservando o tratamento padrão nas demais.
O HTTPS e os cookies seguros dependem das configurações de produção descritas
na [rotina de deploy](../regras_deploy/rotina_deploy.md).

`ALLOWED_HOSTS` aceita os domínios, mas não separa rotas por hostname; essa
separação não foi implementada. Os relatórios em `utilitarios` seguem manuais.

## Testes relacionados

- `tests/unit/test_fluxo_turno_abc.py`;
- `tests/unit/test_persistencia_essencial.py`;
- `tests/unit/test_retry_essencial.py`;
- `tests/unit/test_worker_flow_runtime.py`;
- `tests/unit/test_monitoramento_unidade.py`;
- `tests/unit/test_monitoramento_login.py`;
- `tests/unit/test_monitoramento_painel.py`.

Esses arquivos cobrem o núcleo transacional; consulte também
[`tests/README.md`](../tests/README.md).
````

## Passo 32 — Alterar `tests/README.md`

Documentar cobertura e o banco local exigido para integração.

Base SHA-256: `bbfcd3091dcc48baaa5e4b90781665a203b3c9967daaa2ba4edb9d9712a6fe39`. Conteúdo completo proposto: **196 linhas**.

````markdown
# Testes do projeto

Esta pasta reúne testes unitários, de contrato e de integração SQL. Além do núcleo
transacional, ela cobre regras e utilitários já implementados:

- cenário completo de turno A/B/C;
- retry, requeue, ordem da fila e fencing por `lock_version`;
- persistência idempotente, avanço e não avanço de etapa;
- checkpoints, commits, rollback e conclusão da fila no worker;
- suporte ao idoso e obrigatoriedade do e-mail;
- validação da oferta, início da triagem, profissão e saudação após inatividade;
- experiência Supera gratuita, coerência titular/dependente, aceite de reserva com
  respostas antigas e preservação do texto em replay e follow-up;
- montagem dos relatórios semanais e totais;
- payloads e sondas manuais do Funil;
- vínculo 1:1 opcional de monitoramento e autorização de conversas/mensagens por unidade;
- login nativo, par username/senha, sessão, CSRF e revogação do acesso ao portal;
- painel somente leitura, períodos, consultas por unidade, botões históricos,
  indicadores, Google CSV e CSV essencial sem o prefixo brasileiro `+55`;
- follow-up proativo, retomada reativa, elegibilidade, migração e locks entre workers.

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
tests/unit/test_mensagens_reserva.py
tests/unit/test_inicio_informacoes_supera.py
tests/unit/test_valida_etapa11.py
tests/unit/test_validador_profissao.py
tests/unit/test_gerar_monitoramento_unidades.py
tests/unit/test_metricas_perfis_relatorios.py
tests/unit/test_sondas_funil.py
tests/unit/test_monitoramento_unidade.py
tests/unit/test_monitoramento_login.py
tests/unit/test_monitoramento_painel.py
tests/unit/test_followup.py
tests/integration/test_followup_postgres.py
```

Por padrão, os testes usam fakes e mocks para fronteiras externas, sem chamar
Meta, Funil, Redis ou RDS. A integração com PostgreSQL local só executa quando
`FOLLOWUP_TEST_DSN` é fornecida explicitamente. Um utilitário manual não deve
ser executado como forma de testar sua importação.

Testes unitários pertencem a `tests/unit/`; contratos com PostgreSQL real ficam
em `tests/integration/` e exigem ambiente descartável explícito. Dados e classes
auxiliares exclusivos de teste ficam em `tests/`, nunca nos módulos de produção.
Sem `FOLLOWUP_TEST_DSN`, a descoberta pula a integração PostgreSQL.

`test_mensagens_reserva.py` cobre negativas na escolha do participante,
gratuidade contextual, preservação do aceite flexível, retomada com uma
saudação, barreira terminal e igualdade entre texto enviado e histórico.
Também verifica a composição tratamento + repetição para titular/dependente,
as apresentações exclusivas da etapa 1, inatividade com avanço ou tratamento,
follow-up sem nova apresentação/despedida e participante preservado na reserva.
Os envios são simulados; a consulta do participante é conferida com cursor
substituído, sem conexão com banco de produção.

`test_inicio_informacoes_supera.py` cobre os pedidos de apresentação com e sem
saudação, acentos e interrogação, rejeição de palavras isoladas e outros assuntos,
prioridade de mídia/reforço/financeiro e envio do texto aprovado com os dados da
unidade. Verifica a inicialização da etapa 1, convergência das duas aberturas para
a etapa 2, follow-up sem reapresentação e retry sem novo envio. Meta e banco são
substituídos nos testes; não são feitas chamadas reais.

O teste de monitoramento executa o SQL de autorização em SQLite em memória,
adaptando apenas os placeholders, com um cliente compartilhado por duas
unidades. Cobre isolamento por conversa/mensagem, revogação do vínculo,
desativação de conta, várias unidades sem conta, exclusividade do usuário,
exclusão da conta com preservação da unidade, sessão inválida e falha de banco.
Não acessa o RDS. `fixtures/unidade_monitoramento_legado.sql` representa apenas
a proposta anterior para testar a transferência dos vínculos; não é uma
migração de produção.

`test_monitoramento_login.py` usa o backend, hashes de senha e sessões reais do
Django com usuários fictícios e SQLite em memória. Cobre senha de outra conta,
contas não autorizadas, erros, expiração de CSRF, logout, rotação de sessão,
redirecionamento fixo e escape de HTML. Substitui somente a conexão da thread
durante o teste e restaura-a ao terminar; não cria usuários nem tabelas no RDS.

`test_monitoramento_painel.py` valida as rotas privadas, métodos permitidos,
propagação obrigatória da unidade autorizada, quantidade de parâmetros dos SQLs,
consolidação de perfis, 22 etapas, períodos comparáveis e os quatro downloads
CSV (Google e essencial, todos e elegíveis). Cobre todos os períodos, unidade
autorizada, revogação de acesso, acentos, campos vazios e proteção contra fórmulas
nos dados textuais. Seus payloads vivem em `fixtures/monitoramento_painel.py` e
são fictícios.
O teste distingue a remoção de `+55` no essencial da preservação do telefone
internacional no Google CSV; não remove o DDD nem altera os dados de origem.

## Follow-up

A segunda camada é coberta em `unit/test_followup.py` (redação por rota, nomes e
falha de envio) e `integration/test_followup_postgres.py` (7h contadas do primeiro
envio real, etapas 1–17 incluindo 8, guardas de silêncio/fila/janela, encerramento
atômico com rollback, ausência de terceiro envio e reabertura sem prefixo).
O teste do painel usa as consultas reais para provar que outra conversa do mesmo
chat invalida o stage antigo, mesmo fora do período selecionado. A migração de
segundo follow-up é executada integralmente no PostgreSQL descartável, verificando
preservação dos dados e o novo domínio do motivo de encerramento.

`unit/test_mensagens_etapa11.py` cobre a introdução da triagem para titular e
dependente: nome carregado na entrada 10→11, mensagem inicial, tratamentos,
contexto autônomo, inatividade e follow-up. Verifica falha antes do envio para
dependente sem nome e a preservação do participante nas seis perguntas,
inclusive dependente adulto, sem alterar as regras de confirmação e avanço.

`unit/test_mensagens_contexto.py` cobre a mensagem autônoma de contexto em
todas as etapas: não usa compositores de tratamento ou perguntas de repetição.
Também verifica titular/dependente, ausência de avanço, botões/rodapés, link,
dados de apresentação e o prefixo único de inatividade, com envio simulado.

`unit/test_followup.py` cobre envio exato, reação, etapas e botões reais com HTTP
substituído, recuperação, falta de lock, falhas e parâmetros SQL. O teste de runtime
do flow cobre a repetição comum sem chamar validadores ou persistência de transição.
Cobre saudação com e sem nome, texto enviado igual ao histórico, isolamento do
prefixo sob exceção, retorno legado sem data de envio e falha sem interromper o lote.
Na etapa 1, cobre cliente antigo com nome salvo: saudação genérica, coleta de nome
mantida, reação ignorada e cadastro preservado. Também verifica nome novo aceito
no fluxo normal, personalização nas etapas seguintes e retry sem novo envio.
Na etapa 8, cobre qualquer reação indo diretamente à 9, sem repetir a 8 nem
consumir aceite, para titular e dependente. Verifica saudação única, botões,
mapa obrigatório antes do envio, persistência da transição antes do reset e
recuperação de respostas antigas da 8 ou novas da 9 sem alterar outro ciclo.

`integration/test_followup_postgres.py` exige explicitamente FOLLOWUP_TEST_DSN com
host loopback e banco vazio chamado `test_chatbot_followup`. Ele cria e remove seu
próprio schema chatbot, recusando schema preexistente. Sem essa variável é pulado.
Executa DDL canônico, consultas reais, unicidade em histórico particionado, rollback,
fila sem vínculo e dois proprietários do lock. Nunca aponta para DB_HOST/DB_NAME.
Também executa o SQL integral de migração sobre uma base antiga descartável:
marca somente ativas, audita os valores anteriores, preserva os demais dados,
não produz histórico/envio, recusa reaplicação e reverte diante de legado terminal.
O retorno completo também usa fila e histórico reais nesse banco descartável:
rollback preserva stage positivo, etapa, efeitos e contadores. Respostas válidas
avançam e são salvas; repetição neutra ou tratamento específico preservam a etapa
e o contador na primeira reação. A transição válida zera os turnos sem avanço
junto da conclusão do follow-up, inclusive no retorno da 8 para a 9. Verifica histórico
do cliente e checkpoint na origem, resposta no destino e recuperação da mesma
reação sem reset de um ciclo posterior. Cobre tanto o lembrete
confirmado quanto o legado sem data de envio.
Meta permanece simulada; a confirmação de entrega real exige homologação manual.

`unit/test_retomada_followup.py` percorre os validadores e senders reais nas
rotas titular/dependente: avanço válido, repetição neutra, tratamentos específicos,
triagem, idade, confirmação do destinatário e contagem após o retorno. Confere
prefixo único e igualdade entre texto enviado e histórico, inclusive cabeçalhos.
Os testes de runtime verificam o commit único de efeitos, checkpoint,
encerramento e fila, com rollback quando a finalização falha. A inatividade
de três horas mantém o tratamento normal de contexto inválido.

## Consulta de faixa etária no painel

`unit/test_faixa_etaria_monitoramento.py` cobre a consulta personalizada do painel:
titular único em várias conversas, dependentes por cadastro (inclusive nomes
iguais), distribuição por titular, idade inclusiva e dados ausentes. Executa o
SQL real em SQLite descartável para validar unidade, contato no período,
fronteiras de data/hora e envio confirmado ao funil da pessoa atendida. Exercita
também sessão/autorização, parâmetros duplicados, público único e falhas da API.
Nenhum teste acessa a base de produção.

## Suporte por idade

`unit/test_suporte_por_idade.py` cobre as seis configurações, fronteiras,
Admin, contato comercial, mensagem, recuperação com limite atual e contagem
real em SQLite dos encaminhamentos por unidade, data e motivo. As suítes de
e-mail, turno, follow-up, CSV e relatórios continuam como regressão.

`integration/test_suporte_por_idade_postgres.py` executa migração, domínio,
recusa de reaplicação, falha com rollback e DDL de instalação limpa. Também
verifica tabela ocupada, falha durante a reversão, preservação das conversas
e consultas reais de contexto/relatório no schema completo após a migração. Exige
`SUPORTE_IDADE_TEST_DSN`, host loopback e banco vazio `test_chatbot_suporte_idade`.
Recusa schema chatbot preexistente; não usa DB_HOST/DB_NAME. Sem a variável, é
pulado. Ver o [procedimento](../deploy/idade_minima_suporte.md) para homologação.


## Encerramentos por idade

`test_encerramentos_por_idade.py` cobre faixa compatível no retry, mensagem ligada
à recuperação, cortes de idade, BPA histórico, último chat, separação por unidade
e relatório de conversas na configuração atual. `test_encerramentos_por_idade_postgres.py`
exige `COMERCIAL_IDADE_TEST_DSN` em banco loopback vazio `test_chatbot_comercial`;
recusa qualquer schema chatbot preexistente. Nunca apontar testes para produção.
````

## Passo 33 — Alterar `deploy/README.md`

Apontar o procedimento coordenado desta entrega.

Base SHA-256: `57df6cc0305b24b8875fccb351b9e06d5a3645d0529395e72c0e2231dba7662f`. Conteúdo completo proposto: **229 linhas**.

````markdown
# Implantacao no Lightsail

Os arquivos assumem a aplicacao em `/opt/chatbot/app`, o ambiente virtual em
`/opt/chatbot/venv` e as variaveis em `/etc/chatbot/chatbot.env`. Os quatro
processos da aplicacao sao independentes e escrevem seus logs no journald. O
portal de monitoramento faz parte do processo web `chatbot-webhook`; ele não
cria outro serviço. O quarto serviço é `chatbot-worker-followup`, implantado na
V1.2.0. Este guia também cobre a preparação de uma instalação nova.

## Preparar a aplicacao

### Atualização das mensagens da experiência Supera

A oferta usa **experiência Supera gratuita** e **demonstração prática exclusiva**.
Esta revisão não altera o schema da V1.3.0 já implantada. A proposta de
cadastro de responsável foi retirada antes do deploy, junto com seu SQL
pendente. Não executar scripts antigos salvos para criar essas duas colunas.
A apresentação do agente continua usando os campos já existentes.

### Instalação inicial

Clone a branch `prod` como o usuario `ubuntu` e instale as dependencias:

```bash
git clone --branch prod --single-branch git@github.com:Levi-cell/Chatbot.git /opt/chatbot/app
python3 -m venv /opt/chatbot/venv
/opt/chatbot/venv/bin/pip install --upgrade pip
/opt/chatbot/venv/bin/pip install -r /opt/chatbot/app/requirements.txt
```

Crie `/etc/chatbot/chatbot.env` conforme o procedimento em
[`regras_deploy/modificando_env_e_banco_em_prod.md`](../regras_deploy/modificando_env_e_banco_em_prod.md),
sem registrar segredos no repositorio. Em producao, use `DJANGO_DEBUG=False`,
configure o dominio em `DJANGO_ALLOWED_HOSTS` e mantenha o arquivo restrito:

```bash
sudo chown root:chatbot /etc/chatbot/chatbot.env
sudo chmod 0640 /etc/chatbot/chatbot.env
```

Defina `FUNIL_WORKER_ENABLED=True`, configure o RDS com TLS e informe o
endpoint do Redis remoto em `REDIS_HOST`. A aplicacao nao usa nem exige um
`redis-server` local na VM. Mantenha `PGSSLCERTMODE=disable` quando o RDS
autenticar por usuario/senha. Essa opcao desativa apenas o certificado TLS de
cliente; use `DB_SSLMODE=verify-full` e `DB_SSLROOTCERT` para continuar
validando o certificado do servidor.

Se o banco estiver vazio, crie antes o schema de destino no DBeaver:

```sql
CREATE SCHEMA IF NOT EXISTS chatbot;
```

Depois, prepare o Django. Suas migrations criam `chatbot.auth_user`, necessária
antes do DDL de negócio por causa do vínculo de monitoramento:

```bash
sudo -u chatbot bash -c 'set -a; source /etc/chatbot/chatbot.env; set +a; cd /opt/chatbot/app; export PYTHONPATH=/opt/chatbot/app; /opt/chatbot/venv/bin/python callback/manage.py check --deploy'
sudo -u chatbot bash -c 'set -a; source /etc/chatbot/chatbot.env; set +a; cd /opt/chatbot/app; export PYTHONPATH=/opt/chatbot/app; /opt/chatbot/venv/bin/python callback/manage.py migrate --noinput'
sudo -u chatbot bash -c 'set -a; source /etc/chatbot/chatbot.env; set +a; cd /opt/chatbot/app; export PYTHONPATH=/opt/chatbot/app; /opt/chatbot/venv/bin/python callback/manage.py collectstatic --noinput'
```

`EnvironmentFile` é carregado automaticamente somente pelo systemd. Uma sessão
SSH comum não recebe essas variáveis; os comandos manuais acima carregam o mesmo
arquivo privado dos serviços sem exibir seu conteúdo.

Em uma instalação vazia, após as migrations do Django, siga o
[setup do banco de negócio](../core/database/README.md#setup) antes de iniciar
os serviços. Na atualização de um banco existente, use a migração incremental
específica, sem executar novamente o setup como substituto da migração.

## Instalar os servicos

```bash
sudo install -m 0644 /opt/chatbot/app/deploy/systemd/*.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now chatbot-webhook chatbot-worker-flow chatbot-worker-funil
```

O follow-up é instalado junto das demais units, mas deve ser iniciado somente
após o banco e o flow compatível estarem validados. Conclua a seção
[Ativação do follow-up](#ativação-do-follow-up) para habilitá-lo.

```bash
systemctl status chatbot-webhook chatbot-worker-flow chatbot-worker-funil chatbot-worker-followup
journalctl -u chatbot-webhook -u chatbot-worker-flow -u chatbot-worker-funil -u chatbot-worker-followup -f
```

## Habilitar o Nginx e HTTPS

Instale o template, substitua `__DOMAIN__` pelo dominio real e habilite o site.
O Gunicorn escuta somente em `127.0.0.1:8000`; apenas o Nginx recebe trafego
publico.

```bash
sudo install -m 0644 /opt/chatbot/app/deploy/nginx/chatbot.conf /etc/nginx/sites-available/chatbot
sudoedit /etc/nginx/sites-available/chatbot
sudo ln -sfn /etc/nginx/sites-available/chatbot /etc/nginx/sites-enabled/chatbot
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t
sudo systemctl reload nginx
```

Com o DNS apontando para o IP estatico e as portas 80/443 abertas, deixe o
Certbot criar a configuracao HTTPS somente depois de emitir o certificado:

```bash
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx --redirect -d SEU_DOMINIO
sudo certbot renew --dry-run
```

Somente depois de o HTTPS funcionar, ative no ambiente
`DJANGO_TRUST_X_FORWARDED_PROTO=True`, `DJANGO_SECURE_SSL_REDIRECT=True`,
`DJANGO_SESSION_COOKIE_SECURE=True` e `DJANGO_CSRF_COOKIE_SECURE=True`, e
reinicie o webhook. O Nginx sobrescreve `X-Forwarded-Proto`; o Django nao confia
em um valor enviado diretamente pelo cliente.

## Atualizacao rotineira da branch prod

O procedimento canonico esta em
[`regras_deploy/rotina_deploy.md`](../regras_deploy/rotina_deploy.md).

Na atualização dos workers ou de seus módulos compartilhados, pare o follow-up
antes do flow; retome o flow compatível e validado antes de reativar os lembretes.
Pare também o Funil quando ele for afetado. Alterações exclusivas do painel
podem manter os workers ativos. O webhook continua recebendo e enfileirando
quando o schema permite; para carregar Python/templates novos, recebe `HUP`,
pois Gunicorn não possui auto-reload. Alteração de `.env` ou da unit exige `restart` e segue
[`modificando_env_e_banco_em_prod.md`](../regras_deploy/modificando_env_e_banco_em_prod.md).

## Migracoes incrementais do banco de negocio

Os scripts SQL revisáveis para o RDS existente ficam em `deploy/migrations/`.
Eles não são executados por `manage.py migrate` nem pelo setup de instalação
limpa. Siga os pré-requisitos, as validações e a orientação de rollback do
próprio arquivo antes de publicar o código que depende do novo estado.

Para o cadastro de monitoramento, execute
`deploy/migrations/20260902_adicionar_usuario_monitoramento_unidade.sql` inteiro no DBeaver
antes de publicar o Admin atualizado. Requer `chatbot.unidade` e
`chatbot.auth_user`. O script adiciona `unidade.id_usuario_monitoramento`, com
`UNIQUE` e FK `ON DELETE SET NULL`. Se `unidade_monitoramento` já existir,
valida e transfere os vínculos antes de removê-la, sem `CASCADE`. O SQL anterior
de criação da tabela foi substituído e não deve ser executado.

É uma migração de aplicação única: coluna já existente causa erro. Em caso de
falha, execute `ROLLBACK`; investigue a causa antes de repetir. `ALTER TABLE`
fica somente nesta migração, enquanto o DDL de instalação limpa já contém a
coluna em seu `CREATE TABLE`. Depois da migração, não publique novamente o
código que depende da tabela antiga. Uma reversão exige preservar os vínculos
atuais e preparar um SQL específico antes de voltar o código.

## Operacao dos servicos e do Redis remoto

Os comandos individuais para iniciar e parar cada processo, limpar somente os
bloqueios no Redis remoto e remover o servidor Redis local da VM estao em
[`regras_deploy/servicos_e_redis_remoto.md`](../regras_deploy/servicos_e_redis_remoto.md).

Nao exponha a porta `6379` e nao use `FLUSHDB` ou `FLUSHALL` em producao.

## Ativação do follow-up

Esta alteração exige migração manual `migrations/followup_registros.sql` antes do
flow novo. Instalação limpa utiliza `followup_script.py`, chamado por `bank_script`.
As colunas `followup_stage`/`followup_last_sent_at` já existentes não são recriadas. Com o flow
parado e o follow-up desligado, a migração registra em followup_legado todas as
conversas ativas e marca followup_stage = 1, inclusive nas etapas 18–21. O horário
`followup_last_sent_at`, o histórico, a etapa e a finalização permanecem como estavam.
O script é único e transacional; não reaplicar nos próximos deploys. O setup limpo
cria as três tabelas e não marca conversas. A marcação não comprova envio de mensagem.
Conversa ativa terminal/inconsistente recusa toda a migração: concluir a recuperação
pendente do flow e revisar a anomalia antes de tentar de novo, sem encerrar em massa.

Na produção, essa migração já foi aplicada em 10/09/2026 na V1.2.0, com 106
conversas marcadas naquela execução. Não repetir nem manter esse número como
expectativa fixa: os clientes podem retomar normalmente após o deploy.

Instalar `systemd/chatbot-worker-followup.service` e executar daemon-reload não
inicia envios. A unit habilita FOLLOWUP_WORKER_ENABLED; se essa chave já existir no
EnvironmentFile, conferir a precedência antes da ativação. Nenhum segredo novo é necessário.
Antes da primeira ativação, executar o diagnóstico abaixo e conferir permissões
da role da aplicação nas novas tabelas. Reiniciar primeiro
`chatbot-worker-flow.service` e conferir estado/logs. Somente então:

```bash
sudo systemctl enable --now chatbot-worker-followup.service
sudo journalctl -u chatbot-worker-followup.service --since "5 minutes ago" -n 80 --no-pager
```

`python -m utilitarios.verificar_followup` faz leitura e mostra IDs de uma amostra.
Não é uma execução do worker e não envia mensagens. Um resultado vazio é válido.
O [README dos utilitários](../utilitarios/README.md#diagnóstico-de-follow-up)
traz o comando com o ambiente da VM e explica cada indicador. A sequência completa
de atualização fica em [rotina_deploy.md](../regras_deploy/rotina_deploy.md).

Para interromper os lembretes, parar e desabilitar a unit de follow-up. Isso mantém
o flow apto a tratar retornos de lembretes ou do legado marcado. Não apagar recibos, resetar
stages em massa nem reverter o flow incompatível enquanto existirem ciclos positivos.

## Segunda camada de follow-up

Aplicar [`migrations/20260924_segundo_followup.sql`](migrations/20260924_segundo_followup.sql)
com os workers parados, antes de iniciar o código novo. O arquivo amplia somente
o motivo de encerramento permitido; não fecha conversas nem altera stages existentes.
Não repetir `followup_registros.sql`. Instalação limpa usa o DDL atualizado.

A segunda camada usa o mesmo serviço, após mais 7h desde o primeiro envio real,
mantendo a janela de envio. Recibos antigos válidos podem se tornar elegíveis ao
iniciar o worker; marcações de legado sem recibo não geram despedida.
Atualizar também os estáticos do painel (`collectstatic`) para publicar o filtro
**Follow-up**. Validar o diagnóstico sem envio, reiniciar o flow e só então o follow-up.

## Suporte por idade mínima

O [procedimento de suporte por idade](idade_minima_suporte.md) coordena schema,
código, estáticos e serviços. A migração incremental está em
`migrations/20260911_idade_minima_suporte.sql`; a reversão restrita a NULL/60 está
em `rollback/20260911_idade_minima_suporte.sql`. Não executar em instalações
novas, não reaplicar a migração de follow-up e não editar a migração histórica
que criou a coluna booleana. Os comandos só pertencem à implantação aprovada.


## Filtro Comercial e regras de idade

Ver [procedimento coordenado](filtro_comercial_regras_idade.md). A migração
`migrations/20260926_filtro_comercial_regras_idade.sql` exige telefones reais válidos
e interrompe a transação se houver pendência. Não executá-la com código antigo
processando atendimentos ou permitindo edição simultânea no Admin.
````

## Passo 34 — Criar `deploy/filtro_comercial_regras_idade.md`

Concentrar validações, implantação, limitações conhecidas e procedimento de recuo.

Base SHA-256: `arquivo novo`. Conteúdo completo proposto: **86 linhas**.

````markdown
# Implantação do filtro Comercial e das regras de idade

## Contrato da entrega

- Suporte configurável: desativado, 50, 60, 70 ou 80; somente titular até 89.
- Universal: 90 anos ou mais, titular ou dependente, com contato comercial.
- Titular menor de 18 e dependente abaixo de 4 com BPA/5 sem BPA encerram sem contato.
- Nenhum encerramento por idade ganha Funil ou bloqueio de 30 dias.
- Comercial no painel lê a última conversa por cliente/unidade; relatório conta
  conversas encerradas no período, somente pelos motivos da configuração atual.

## Preparação e validação

Comparar a base do plano com o checkout atual antes de substituir arquivos inteiros.
Reconciliar alterações posteriores; não sobrescrever trabalho novo com a versão do plano.
Usar uma cópia local, sem credenciais de produção e com envs de teste.

```bash
python -m unittest tests.unit.test_encerramentos_por_idade tests.unit.test_suporte_por_idade tests.unit.test_suporte_idoso_email_obrigatorio tests.unit.test_monitoramento_painel tests.unit.test_retomada_followup tests.unit.test_worker_flow_runtime tests.unit.test_metricas_perfis_relatorios tests.unit.test_followup
node --check callback/monitoramento/static/monitoramento/js/painel.js
```

Rodar também a suíte completa e comparar falhas com a base. Em 26/09/2026,
17 falhas/subtestes de texto e espaçamento nas etapas 1/7/11, saudação e profissão
já ocorriam sem esta proposta. Não corrigir os textos aprovados apenas para atender
assertivas antigas. Essas pendências precisam de decisão antes de exigir suíte toda verde.

Validar a migração em PostgreSQL vazio e local, com o nome exato
`test_chatbot_comercial`, usando `COMERCIAL_IDADE_TEST_DSN`. O teste recusa host
remoto e schema chatbot preexistente. Não apontar para o banco do chatbot real.

```bash
python -m unittest tests.integration.test_encerramentos_por_idade_postgres
```

Sem a variável, os testes são ignorados: isso não valida a migração real.
Conferir query plans com volume representativo; consultas novas reaproveitam
os índices de conversa e histórico existentes e não fazem uma consulta por chat.
Revisar a tela com fixtures: desktop e celular, filtro, detalhes, legenda por
mouse/teclado/toque, período e ausência de rolagem horizontal.

## Sequência de deploy

1. Conferir checkout limpo, commit de destino e snapshot/recuperação disponíveis.
2. Regularizar números comerciais reais ausentes/inválidos. A migração aborta
   antes de alterar dados caso alguma unidade esteja irregular.
3. Impedir edição simultânea no Admin. Parar follow-up, flow e funil. Suspender
   temporariamente o processo web durante a troca de código/schema; o provedor
   precisa poder repetir webhooks nesse intervalo. Não manter Admin antigo ativo.
4. Atualizar o checkout. Executar a migração inteira do passo SQL e guardar a saída
   com as unidades convertidas de suporte 90 para NULL. Se falhar, dar ROLLBACK,
   resolver a causa e não iniciar o código novo com schema antigo.
5. Executar `manage.py check --deploy`, o verificador de follow-up sem envio e
   `collectstatic --noinput` com o ambiente da VM. Não rodar seeds de instalação.
6. Iniciar/reiniciar web e workers com o código novo. A migração incrementa
   `cache_controle.unidades`; o reinício evita processo com cache antigo.
7. Conferir serviços, logs e HTTP; recarregar o painel para obter JS/CSS versionados.
   Uma aba aberta com JS antigo deve ser recarregada: o indicador escalar foi substituído.
8. Conferir Comercial e relatório com dados reais somente por leitura. Não fabricar
   atendimentos, mudar motivos históricos nem gerar envios para validar a tela.

## Recuperação e limites

Motivo específico é salvo na finalização atômica com fila sent. A recuperação
usa apenas resposta comprovada do mesmo par conversa/entrada. Idade vem dessa
entrada, sem substituir pelo cadastro global. Para suporte 50–89, limite atual
compatível prevalece; se incompatível/desativado, escolhe a maior faixa permitida
que não exceda a idade. Essa faixa é compatível, não prova a configuração original.

Sem resposta persistida após sucesso externo, permanece o risco aceito de repetir
com a configuração atual. Não há nova transação antecipando motivo ou idade.
Legados sem prova do limite permanecem genéricos, e não entram na tabela por
configuração atual. Universal antiga de 100+ não vira 90+ automaticamente.

## Reversão

Parar processamento e bloquear edições novamente. O script
`rollback/20260926_filtro_comercial_regras_idade.sql` relaxa as regras da unidade,
mas conserva os motivos novos; removê-los faria perder compatibilidade com dados.
Não restaura NULL para 90 automaticamente. Usar a evidência do deploy e conferir
eventuais edições posteriores antes de uma restauração individual.

O código antigo não interpreta os motivos novos no painel/indicador comercial.
Uma reversão operacional não recupera essa interpretação: publicar correção adiante
é preferível quando os novos registros já existem. Nunca apagar registros para
forçar uma reversão. Revalidar cache, serviços, assets e histórico após o recuo.
````

## Passo 35 — Criar `deploy/rollback/20260926_filtro_comercial_regras_idade.sql`

Preparar reversão compatível que conserva os motivos novos e não inventa configurações antigas.

Base SHA-256: `arquivo novo`. Conteúdo completo proposto: **20 linhas**.

````sql
-- Recuo compatível do schema, sem apagar os motivos novos já gravados.
-- Parar workers e impedir edição no Admin antes de reverter código/schema.
BEGIN;
SET LOCAL lock_timeout = '5s';
SET LOCAL statement_timeout = '60s';
LOCK TABLE chatbot.unidade IN ACCESS EXCLUSIVE MODE;
ALTER TABLE chatbot.unidade
    DROP CONSTRAINT ck_unidade_idade_minima_suporte,
    ADD CONSTRAINT ck_unidade_idade_minima_suporte CHECK (
        idade_minima_suporte IS NULL OR idade_minima_suporte IN (50, 60, 70, 80, 90)
    ),
    DROP CONSTRAINT IF EXISTS ck_unidade_numero_comercial,
    ALTER COLUMN numero_comercial DROP NOT NULL;
-- Não restaurar automaticamente NULL -> 90: pode ter havido edição legítima.
-- A restrição ampliada de motivos é mantida para preservar os dados novos.
INSERT INTO chatbot.cache_controle (nome, versao, atualizado_em)
VALUES ('unidades', 1, NOW())
ON CONFLICT (nome) DO UPDATE
SET versao = chatbot.cache_controle.versao + 1, atualizado_em = NOW();
COMMIT;
````

## Passo 36 — Criar `deploy/migrations/20260926_filtro_comercial_regras_idade.sql`

Executar a migração transacional somente no deploy coordenado; último passo do plano.

Base SHA-256: `arquivo novo`. Conteúdo completo proposto: **56 linhas**.

Salvar no caminho indicado e executar o bloco inteiro, de BEGIN a COMMIT, no deploy.
Se falhar, executar ROLLBACK e resolver a causa antes de reiniciar os serviços.
Guardar a saída das unidades convertidas de 90 para NULL. Não selecionar comandos de outros scripts.

````sql
-- Executar inteiro, com os workers parados e o Admin indisponível para edição.
-- Não altera motivos históricos, idades, elegibilidade do funil ou bloqueios.
BEGIN;
SET LOCAL lock_timeout = '5s';
SET LOCAL statement_timeout = '60s';

LOCK TABLE chatbot.unidade, chatbot.conversa IN ACCESS EXCLUSIVE MODE;

DO $validacao$
DECLARE
    unidades_invalidas TEXT;
BEGIN
    SELECT string_agg(id_unidade::TEXT, ', ' ORDER BY id_unidade)
      INTO unidades_invalidas
      FROM chatbot.unidade
     WHERE numero_comercial IS NULL
        OR NOT (regexp_replace(numero_comercial, '[^0-9]', '', 'g')
                ~ '^([0-9]{10,11}|55[0-9]{10,11})$');
    IF unidades_invalidas IS NOT NULL THEN
        RAISE EXCEPTION 'Regularize o número comercial real das unidades: %', unidades_invalidas;
    END IF;
END;
$validacao$;

-- Guardar esta saída na evidência do deploy antes de normalizar 90 -> NULL.
SELECT id_unidade, nome_unidade, idade_minima_suporte AS suporte_anterior
  FROM chatbot.unidade WHERE idade_minima_suporte = 90 ORDER BY id_unidade;

UPDATE chatbot.unidade SET idade_minima_suporte = NULL WHERE idade_minima_suporte = 90;
ALTER TABLE chatbot.unidade
    DROP CONSTRAINT ck_unidade_idade_minima_suporte,
    ADD CONSTRAINT ck_unidade_idade_minima_suporte
        CHECK (idade_minima_suporte IS NULL OR idade_minima_suporte IN (50, 60, 70, 80)),
    ALTER COLUMN numero_comercial SET NOT NULL;
ALTER TABLE chatbot.unidade DROP CONSTRAINT IF EXISTS ck_unidade_numero_comercial;
ALTER TABLE chatbot.unidade ADD CONSTRAINT ck_unidade_numero_comercial CHECK (
    regexp_replace(numero_comercial, '[^0-9]', '', 'g') ~ '^([0-9]{10,11}|55[0-9]{10,11})$'
);

ALTER TABLE chatbot.conversa
    DROP CONSTRAINT ck_conversa_motivo_encerramento,
    ADD CONSTRAINT ck_conversa_motivo_encerramento CHECK (
        motivo_encerramento IS NULL OR motivo_encerramento IN (
            'idade_invalida', 'encaminhado_suporte_idoso', 'foi_agendado', 'followup_sem_resposta',
            'titular_menor_18', 'dependente_menor_4', 'dependente_menor_5',
            'suporte_idoso_50', 'suporte_idoso_60', 'suporte_idoso_70', 'suporte_idoso_80',
            'idade_universal_90'
        )
    );

INSERT INTO chatbot.cache_controle (nome, versao, atualizado_em)
VALUES ('unidades', 1, NOW())
ON CONFLICT (nome) DO UPDATE
SET versao = chatbot.cache_controle.versao + 1, atualizado_em = NOW();

COMMIT;
````
