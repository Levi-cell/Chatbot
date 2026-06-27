
### INICIO

MENSAGEM_ETAPA_2 = (
    "Prazer, {nome}! ☺️\n\n"
    "O Supera é um curso de estimulação cognitiva e ginástica para o cérebro. "
    "Aqui nós iremos potencializar as habilidades cognitivas, socioemocionais "
    "e éticas do aluno, como atenção, concentração e memória.\n\n"
    "Conta para mim, esse atendimento é para você ou para outra pessoa?"
)

def montar_mensagem_etapa_2(nome):
    return MENSAGEM_ETAPA_2.format(nome=nome)

### RESPONDEU ERRADO AO INICIO COM FINANCEIRO

MENSAGEM_FINANCEIRO_ETAPA_2 = (
    "Olha demais informações como valores são apresentadas no atendimento "
    "presencial após sua aula gratuita.\n"
    "Fala para mim, esse atendimento é para você ou outra pessoa?"
)

def montar_mensagem_financeiro_etapa_2():
    return MENSAGEM_FINANCEIRO_ETAPA_2

### RESPONDEU ERRADO AO INICIO COM MIDIA

MENSAGEM_MIDIA_ETAPA_2 = (
    "Olha não reconhecemos ainda mensagem com mídia, apenas texto.\n"
    "Fala para mim, esse atendimento é para você ou outra pessoa?"
)

def montar_mensagem_midia_etapa_2():
    return MENSAGEM_MIDIA_ETAPA_2

### RESPONDEU ERRADO AO INICIO COM MENSAGEM FORA DE CONTEXTO

MENSAGEM_CONTEXTO_OPCAO_INVALIDA_ETAPA_2 = (
    "Olha parece que você enviou uma mensagem fora de contexto.\n"
    "Fala para mim, esse atendimento é para você ou outra pessoa?"
)

def montar_mensagem_contexto_etapa_2():
    return MENSAGEM_CONTEXTO_OPCAO_INVALIDA_ETAPA_2

## BOTÕES

BOTAO_ETAPA_2_PARA_MIM = "Para mim"
BOTAO_ETAPA_2_OUTRA_PESSOA = "Para outra pessoa"

BOTOES_ETAPA_2 = (
    BOTAO_ETAPA_2_PARA_MIM,
    BOTAO_ETAPA_2_OUTRA_PESSOA,
)

def montar_botoes_etapa_2():
    return BOTOES_ETAPA_2
