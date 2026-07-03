
### INICIO

MENSAGEM_ETAPA2 = (
    "Prazer, {nome}! ☺️\n\n"
    "O Supera é um curso de estimulação cognitiva e ginástica para o cérebro. "
    "Aqui nós iremos potencializar as habilidades cognitivas, socioemocionais "
    "e éticas do aluno, como atenção, concentração e memória.\n\n"
    "Conta para mim, esse atendimento é para você ou para outra pessoa?"
)

def montar_mensagem_etapa2(nome):
    return MENSAGEM_ETAPA2.format(nome=nome)

### RESPONDEU ERRADO COM FINANCEIRO

MENSAGEM_FINANCEIRO_ETAPA2 = (
    "Olha demais informações como valores são apresentadas no atendimento "
    "presencial após sua aula *gratuita*.\n"
    "Fala para mim, esse atendimento é para você ou outra pessoa?"
)

def montar_mensagem_financeiro_etapa2():
    return MENSAGEM_FINANCEIRO_ETAPA2

### RESPONDEU ERRADO COM MIDIA

MENSAGEM_MIDIA_ETAPA2 = (
    "Olha não reconhecemos ainda mensagem com mídia, apenas texto.\n"
    "Fala para mim, esse atendimento é para você ou outra pessoa?"
)

def montar_mensagem_midia_etapa2():
    return MENSAGEM_MIDIA_ETAPA2

### RESPONDEU ERRADO COM MENSAGEM FORA DE CONTEXTO

MENSAGEM_CONTEXTO_OPCAO_INVALIDA_ETAPA2 = (
    "Olha parece que você enviou uma mensagem fora de contexto.\n"
    "Fala para mim, esse atendimento é para você ou outra pessoa?"
)

def montar_mensagem_contexto_etapa2():
    return MENSAGEM_CONTEXTO_OPCAO_INVALIDA_ETAPA2

## BOTÕES

BOTAO_ETAPA2_PARA_MIM = "Para mim"
BOTAO_ETAPA2_OUTRA_PESSOA = "Para outra pessoa"

BOTOES_ETAPA2 = (
    BOTAO_ETAPA2_PARA_MIM,
    BOTAO_ETAPA2_OUTRA_PESSOA,
)

def montar_botoes_etapa2():
    return BOTOES_ETAPA2
