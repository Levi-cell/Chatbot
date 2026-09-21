from core.integrations.whatsapp.messages.tratamentos_universais import (
    montar_mensagem_tratamento_financeiro,
    montar_mensagem_tratamento_reforco_escolar,
)


### INICIO

MENSAGEM_ETAPA2 = (
    "Prazer, {nome}! ☺️\n\n"
    "O Supera é um curso de *estimulação cognitiva* "
    "que trabalha habilidades cognitivas e socioemocionais por meio de atividades que estimulam "
    "atenção, concentração, memória, raciocínio e outras funções importantes para o dia a dia.\n\n"
    "Para eu entender melhor como podemos ajudar, me conta: *esse atendimento é para você ou para um dependente?*"
)

def montar_mensagem_etapa2(nome):
    return MENSAGEM_ETAPA2.format(nome=nome)

### RESPONDEU ERRADO COM FINANCEIRO

MENSAGEM_FINANCEIRO_ETAPA2 = montar_mensagem_tratamento_financeiro(
    "Esse atendimento é para você ou para um dependente?"
)

def montar_mensagem_financeiro_etapa2():
    return MENSAGEM_FINANCEIRO_ETAPA2


### RESPONDEU COM DÚVIDA SOBRE REFORÇO ESCOLAR

MENSAGEM_RETOMADA_ETAPA2 = (
    "Fala para mim, esse atendimento é para você ou para um dependente?"
)


def montar_mensagem_reforco_escolar_etapa2():
    return montar_mensagem_tratamento_reforco_escolar(
        MENSAGEM_RETOMADA_ETAPA2,
    )

### RESPONDEU ERRADO COM MIDIA

MENSAGEM_MIDIA_ETAPA2 = (
    "Olha não reconhecemos ainda mensagem com mídia, apenas texto.\n"
    "Fala para mim, esse atendimento é para você ou para um dependente?"
)

def montar_mensagem_midia_etapa2():
    return MENSAGEM_MIDIA_ETAPA2

### RESPONDEU ERRADO COM MENSAGEM FORA DE CONTEXTO

MENSAGEM_CONTEXTO_OPCAO_INVALIDA_ETAPA2 = (
    "Olha parece que você enviou uma mensagem fora de contexto.\n"
    "Fala para mim, esse atendimento é para você ou para um dependente?"
)

def montar_mensagem_contexto_etapa2():
    return MENSAGEM_CONTEXTO_OPCAO_INVALIDA_ETAPA2

## BOTÕES

BOTAO_ETAPA2_PARA_MIM = "Para mim"
BOTAO_ETAPA2_OUTRA_PESSOA = "Para um dependente"

BOTOES_ETAPA2 = (
    BOTAO_ETAPA2_PARA_MIM,
    BOTAO_ETAPA2_OUTRA_PESSOA,
)

def montar_botoes_etapa2():
    return BOTOES_ETAPA2
