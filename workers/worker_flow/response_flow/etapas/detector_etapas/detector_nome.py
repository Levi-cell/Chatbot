import re
import unicodedata

from workers.worker_flow.response_flow.etapas.detector_etapas.nome.lexicos import (
    CAUDAS_NOMES_TRADICIONAIS,
    PALAVRAS_AMBIGUAS_COMO_NOME,
    PALAVRAS_CAUDAS_NOMES_TRADICIONAIS,
    PALAVRAS_CONTEXTO_COMPLEMENTARES,
    PRIMEIROS_NOMES_COMPOSTOS,
    SAUDACOES_ANTES_DA_APRESENTACAO,
    SOBRENOMES_COMPLEMENTARES,
)
from workers.worker_flow.response_flow.etapas.detector_etapas.nome.modelos import (
    STATUS_AMBIGUO,
    STATUS_INVALIDO,
    STATUS_VALIDO,
    ResultadoValidacaoNome,
)
from workers.worker_flow.response_flow.etapas.detector_etapas.nome.seguranca import (
    MOTIVO_ALFABETO_NAO_SUPORTADO,
    MOTIVO_TEXTO_CORROMPIDO,
    MOTIVO_UNICODE_INSEGURO,
    normalizar_entrada_nome,
)
from workers.worker_flow.response_flow.etapas.detector_etapas.detector_financeiro import (
    normalizar_texto,
)

"""
detector_nome.py funciona como um validador de contexto mas não entra na pasta
de contexto por que ele será usado para valida nomes no geral ao decorrer do projeto 
em mais de uma etapa, o que muda será a função sender que será chamada após passar
por esse validador de nome, para demais validações de contexto como botões, acesse
a pasta de contexto.
"""





TIPO_TRATAMENTO_NOME_INVALIDO = "nome_invalido"

MOTIVO_VAZIO = "vazio"
MOTIVO_TIPO_INVALIDO = "tipo_invalido"
MOTIVO_SEM_LETRAS = "sem_letras"
MOTIVO_NUMERO = "numero"
MOTIVO_CARACTERE_INVALIDO = "caractere_invalido"
MOTIVO_MULTIPLAS_PALAVRAS = "multiplas_palavras"
MOTIVO_COMPRIMENTO_INVALIDO = "comprimento_invalido"
MOTIVO_REPETICAO_CARACTERE = "repeticao_caractere"
MOTIVO_TERMO_PEJORATIVO = "termo_pejorativo"
MOTIVO_FORA_CONTEXTO = "fora_contexto"
MOTIVO_ESTRUTURA_IMPROVAVEL = "estrutura_improvavel"

TAMANHO_MINIMO_PRIMEIRO_NOME = 2
TAMANHO_MAXIMO_PRIMEIRO_NOME = 50
QUANTIDADE_MAXIMA_PALAVRAS_NOME = 2

PADRAO_DIGITO = re.compile(r"\d")
PADRAO_PRAZER_COM_VIRGULA = re.compile(
    r"^(\s*prazer)\s*,\s*",
    re.IGNORECASE,
)
PADRAO_IDENTIFICACAO_COM_DOIS_PONTOS = re.compile(
    r"^(\s*(?:(?:o\s+)?meu\s+)?(?:nome|apelido))\s*:\s*",
    re.IGNORECASE,
)
PADRAO_PONTUACAO_FINAL = re.compile(r"[,\.!?]+$")
PADRAO_CORTESIA_FINAL = re.compile(
    r"\s*,\s*(?:prazer|obrigad[oa])\s*[,\.!?]*$",
    re.IGNORECASE,
)
PADRAO_SAUDACAO_INICIAL = re.compile(
    r"^\s*(?:"
    + "|".join(
        re.escape(saudacao)
        for saudacao in SAUDACOES_ANTES_DA_APRESENTACAO
    )
    + r")\s*[,\.!?:-]*\s+(?="
    r"(?:"
    r"(?:o\s+)?meu\s+(?:nome|apelido)|"
    r"eu\s+(?:me\s+chamo|sou)|"
    r"me\s+chamo|"
    r"sou|"
    r"aqui|"
    r"prazer|"
    r"pode[m]?\s+me\s+chamar"
    r")\b"
    r")",
    re.IGNORECASE,
)
PADRAO_REPETICAO_CARACTERE = re.compile(
    r"([^\W\d_])\1{2,}",
    re.IGNORECASE,
)
PADRAO_VOGAL = re.compile(r"[aeiouy]", re.IGNORECASE)
PADRAO_CINCO_CONSOANTES = re.compile(
    r"[bcdfghjklmnpqrstvwxz]{5,}",
    re.IGNORECASE,
)
PADRAO_FRASE_COMPACTADA = re.compile(
    r"^(?:"
    r"eumechamo|"
    r"mechamo|"
    r"meunomee|"
    r"meunomeeh|"
    r"omeunomee|"
    r"omeunomeeh"
    r")[a-z]{2,}$",
    re.IGNORECASE,
)
PADRAO_REACAO_CONVERSACIONAL = re.compile(
    r"^(?:k{2,}|(?:ha){2,}|(?:rs){2,}|h{2,})$",
    re.IGNORECASE,
)

CONECTORES_SOBRENOME = {
    "da",
    "das",
    "de",
    "do",
    "dos",
}

SOBRENOMES_COMUNS_BRASIL = {
    "aguiar",
    "albuquerque",
    "almeida",
    "alves",
    "amaral",
    "andrade",
    "araujo",
    "assis",
    "azevedo",
    "barbosa",
    "barros",
    "bastos",
    "bezerra",
    "borges",
    "braga",
    "brandao",
    "cabral",
    "camargo",
    "campos",
    "cardoso",
    "carvalho",
    "castro",
    "cavalcante",
    "cavalcanti",
    "coelho",
    "correia",
    "costa",
    "cruz",
    "cunha",
    "davila",
    "dias",
    "duarte",
    "farias",
    "fernandes",
    "ferraz",
    "ferreira",
    "filho",
    "fonseca",
    "fontes",
    "freitas",
    "garcia",
    "gomes",
    "goncalves",
    "guimaraes",
    "junior",
    "leal",
    "leite",
    "lima",
    "lopes",
    "machado",
    "marques",
    "martins",
    "medeiros",
    "melo",
    "mendes",
    "miranda",
    "monteiro",
    "moraes",
    "morais",
    "moreira",
    "moura",
    "nascimento",
    "neto",
    "neves",
    "nogueira",
    "novaes",
    "nunes",
    "oliveira",
    "paiva",
    "peixoto",
    "pereira",
    "pires",
    "pinheiro",
    "prado",
    "queiroz",
    "ramos",
    "reis",
    "rezende",
    "ribeiro",
    "rocha",
    "rodrigues",
    "sampaio",
    "santana",
    "santos",
    "silva",
    "soares",
    "sobrinho",
    "souza",
    "sousa",
    "tavares",
    "teixeira",
    "torres",
    "vargas",
    "vasconcelos",
    "viana",
    "vieira",
    "watanabe",
}
SOBRENOMES_COMUNS_BRASIL.update(SOBRENOMES_COMPLEMENTARES)

# Respostas informais comuns para "como você se chama?". A decisão considera
# o contexto exclusivo da etapa 1; fora dela, essas palavras não são nomes.
APRESENTACOES_CURTAS_NOME = {
    "e",
    "eh",
    "he",
    "é",
}

# Correções seguras e curadas para nomes brasileiros cujo til costuma ser
# omitido na digitação. Não é um acentuador genérico: somente estas chaves
# conhecidas são convertidas para evitar alterar nomes raros por adivinhação.
NOMES_BRASILEIROS_COM_TIL = {
    "aarao": "Aarão",
    "abraao": "Abraão",
    "adao": "Adão",
    "anunciacao": "Anunciação",
    "ascensao": "Ascensão",
    "assuncao": "Assunção",
    "caua": "Cauã",
    "conceicao": "Conceição",
    "cristovao": "Cristóvão",
    "damiao": "Damião",
    "estevao": "Estevão",
    "jao": "Jão",
    "joao": "João",
    "juliao": "Julião",
    "kaua": "Kauã",
    "leao": "Leão",
    "romao": "Romão",
    "sebastiao": "Sebastião",
    "simao": "Simão",
    "tiao": "Tião",
    "ubirata": "Ubiratã",
}

# Estes prefixos declaram explicitamente que todo o restante representa nome.
# Neles, sobrenomes posteriores podem ser ignorados após extrair até dois nomes.
PREFIXOS_APRESENTACAO_COMPLETA = (
    ("pode", "me", "chamar", "de"),
    ("podem", "me", "chamar", "de"),
    ("o", "meu", "nome", "eh"),
    ("o", "meu", "nome", "e"),
    ("o", "meu", "apelido", "eh"),
    ("o", "meu", "apelido", "e"),
    ("meu", "nome", "eh"),
    ("meu", "nome", "e"),
    ("meu", "apelido", "eh"),
    ("meu", "apelido", "e"),
    ("o", "meu", "nome"),
    ("meu", "nome"),
    ("o", "meu", "apelido"),
    ("meu", "apelido"),
    ("eu", "me", "chamo", "de"),
    ("eu", "me", "chamo"),
    ("me", "chamo", "de"),
    ("me", "chamo"),
    ("apelido",),
    ("nome",),
)

# "Sou" é mais ambíguo. Por isso, só aceita uma ou duas palavras e não descarta
# conteúdo posterior como se fosse sobrenome.
PREFIXOS_APRESENTACAO_ESTRITA = (
    ("aqui", "he"),
    ("aqui", "eh"),
    ("aqui", "e"),
    ("prazer",),
    ("eu", "sou", "a"),
    ("eu", "sou", "o"),
    ("eu", "sou"),
    ("sou", "a"),
    ("sou", "o"),
    ("sou",),
)

# A lista prioriza respostas conversacionais em português do Brasil. Palavras
# ambíguas que parecem nomes ou apelidos permanecem aceitas sem base externa.
PALAVRAS_FORA_CONTEXTO = {
    "a",
    "acessar",
    "acho",
    "abrir",
    "adeus",
    "agora",
    "agendamento",
    "agendar",
    "aguardar",
    "ajuda",
    "ainda",
    "alguem",
    "algum",
    "alguma",
    "alterar",
    "aluna",
    "aluno",
    "amanha",
    "antes",
    "apagar",
    "apertar",
    "apertei",
    "aplicativo",
    "aprovado",
    "aqui",
    "arquivo",
    "atendente",
    "atendimento",
    "ate",
    "ao",
    "aos",
    "audio",
    "aula",
    "alegre",
    "azul",
    "banana",
    "beleza",
    "boa",
    "boleto",
    "bom",
    "bot",
    "botao",
    "bora",
    "bloquear",
    "buscar",
    "cadastro",
    "caderno",
    "cadastrar",
    "cancelar",
    "cartao",
    "casa",
    "celular",
    "certo",
    "chama",
    "chamada",
    "chamado",
    "chamam",
    "chamando",
    "chamar",
    "chame",
    "chamo",
    "chave",
    "checar",
    "cidade",
    "chatbot",
    "clicar",
    "cliente",
    "clique",
    "cole",
    "coisa",
    "comprar",
    "comecar",
    "como",
    "com",
    "computador",
    "confirmar",
    "conseguir",
    "consigo",
    "consultar",
    "contato",
    "continuar",
    "conversar",
    "correto",
    "cpf",
    "criar",
    "curso",
    "custo",
    "dados",
    "daqui",
    "da",
    "das",
    "de",
    "deletar",
    "depois",
    "desconto",
    "deseja",
    "desejar",
    "digitar",
    "digite",
    "dia",
    "dinheiro",
    "disponibilidade",
    "disponivel",
    "documento",
    "do",
    "dos",
    "duvida",
    "editar",
    "e",
    "ela",
    "elas",
    "ele",
    "eles",
    "email",
    "em",
    "entender",
    "entendi",
    "entrar",
    "endereco",
    "enviar",
    "erro",
    "escolhida",
    "escolhido",
    "essa",
    "esse",
    "esta",
    "este",
    "estou",
    "escola",
    "esperar",
    "excluir",
    "eu",
    "fazer",
    "fim",
    "feito",
    "fechar",
    "filha",
    "filho",
    "foto",
    "falar",
    "favela",
    "feliz",
    "funcionar",
    "gratis",
    "gratuito",
    "girafa",
    "grupo",
    "gosto",
    "hoje",
    "horario",
    "humano",
    "imagem",
    "idade",
    "informacao",
    "informacoes",
    "iniciar",
    "inscricao",
    "internet",
    "isso",
    "isto",
    "ja",
    "laripo",
    "legal",
    "link",
    "ligar",
    "local",
    "maripo",
    "mae",
    "mandar",
    "mano",
    "marcar",
    "matricula",
    "mensagem",
    "mensalidade",
    "menu",
    "meu",
    "me",
    "minha",
    "mostrar",
    "mudar",
    "nada",
    "na",
    "nao",
    "nas",
    "nenhum",
    "no",
    "noite",
    "nome",
    "nos",
    "nossa",
    "nosso",
    "numero",
    "obrigada",
    "obrigado",
    "oi",
    "ola",
    "onde",
    "o",
    "online",
    "opcao",
    "os",
    "ou",
    "outro",
    "outra",
    "pai",
    "pagar",
    "pagamento",
    "parar",
    "para",
    "por",
    "pra",
    "pro",
    "pdf",
    "pergunta",
    "pessoa",
    "pix",
    "pode",
    "porque",
    "preco",
    "preciso",
    "presencial",
    "primeiro",
    "problema",
    "prosseguir",
    "promocao",
    "proximo",
    "qual",
    "qualquer",
    "quanto",
    "quero",
    "receber",
    "reiniciar",
    "remover",
    "remoto",
    "responder",
    "responda",
    "resposta",
    "retornar",
    "rg",
    "saber",
    "sair",
    "segundo",
    "se",
    "senha",
    "servico",
    "sim",
    "site",
    "solicitar",
    "sou",
    "sua",
    "seu",
    "supera",
    "suporte",
    "sistema",
    "talvez",
    "tarde",
    "telefone",
    "terminado",
    "terminar",
    "teste",
    "testando",
    "texto",
    "tchau",
    "tentar",
    "te",
    "tu",
    "um",
    "uma",
    "turma",
    "unidade",
    "usuario",
    "valeu",
    "valor",
    "vai",
    "vamos",
    "vender",
    "verde",
    "verdade",
    "verificar",
    "video",
    "voce",
    "voces",
    "voltar",
    "whatsapp",
    "zaneco",
    "zuleco",
}
PALAVRAS_FORA_CONTEXTO.update(PALAVRAS_CONTEXTO_COMPLEMENTARES)

PALAVRAS_NOME_PEJORATIVAS = {
    "abestalhada",
    "abestalhado",
    "animal",
    "anta",
    "arrombada",
    "arrombado",
    "asna",
    "asno",
    "babaca",
    "babacas",
    "babacao",
    "babaquinha",
    "baitola",
    "besta",
    "bestalhao",
    "bicha",
    "bichinha",
    "bichona",
    "biscate",
    "bixa",
    "boceta",
    "boiola",
    "boquete",
    "boqueteira",
    "bostao",
    "bostinha",
    "bosta",
    "brocha",
    "broxa",
    "buceta",
    "bunda",
    "burra",
    "burro",
    "cacete",
    "cachorra",
    "cachorro",
    "cagada",
    "cagado",
    "cagao",
    "cagona",
    "carai",
    "caralho",
    "canalha",
    "cadela",
    "chifruda",
    "chifrudo",
    "corna",
    "corno",
    "cretina",
    "cretino",
    "cu",
    "cuzao",
    "cuzaona",
    "cuzinho",
    "debil",
    "desgraca",
    "desgracada",
    "desgracado",
    "desgracenta",
    "desgracento",
    "doente",
    "egua",
    "escrota",
    "escroto",
    "estupida",
    "estupido",
    "fdp",
    "filhadaputa",
    "filhaodaputa",
    "filhadeumaputa",
    "filhodeumaputa",
    "filhodaputa",
    "foda",
    "fode",
    "foder",
    "fodase",
    "fodida",
    "fodido",
    "fodona",
    "fodao",
    "fudendo",
    "fudida",
    "fudido",
    "galinha",
    "gozar",
    "gozo",
    "gozada",
    "gozado",
    "idiota",
    "idiotas",
    "imbecil",
    "imbecis",
    "imunda",
    "imundo",
    "inutil",
    "jegue",
    "kenga",
    "lazarenta",
    "lazarento",
    "lerda",
    "lerdo",
    "lixo",
    "maldita",
    "maldito",
    "macaca",
    "macaco",
    "merda",
    "merdao",
    "merdinha",
    "meretriz",
    "miseravel",
    "mongol",
    "mongola",
    "mongolao",
    "mongoloide",
    "mula",
    "nojenta",
    "nojento",
    "otaria",
    "otario",
    "otariazinha",
    "otariozinho",
    "palhaca",
    "palhaco",
    "panaca",
    "paspalha",
    "paspalhao",
    "paspalho",
    "pateta",
    "pau",
    "pauzao",
    "pepeca",
    "penis",
    "pica",
    "piranha",
    "piriguete",
    "piroca",
    "pnc",
    "podre",
    "pomba",
    "porra",
    "prostituta",
    "punheta",
    "punheteira",
    "punheteiro",
    "puta",
    "putona",
    "putao",
    "putassa",
    "putaria",
    "puteiro",
    "putinha",
    "puto",
    "quenga",
    "rabao",
    "rapariga",
    "retardada",
    "retardado",
    "ridicula",
    "ridiculo",
    "rola",
    "sacanagem",
    "safada",
    "safado",
    "sexo",
    "siririco",
    "siririca",
    "tapadao",
    "tapada",
    "tapado",
    "tarada",
    "tarado",
    "tesao",
    "tmnc",
    "tnc",
    "tonta",
    "tonto",
    "transa",
    "traste",
    "vaca",
    "vagabunda",
    "vagabundo",
    "vadia",
    "veada",
    "veado",
    "viado",
    "vsf",
    "xana",
    "xavasca",
    "xereca",
    "xibiu",
    "xota",
    "xoxota",
}

# As raízes ampliam flexões e disfarces em português. Termos muito curtos, como
# "pau" e "cu", permanecem na comparação exata para preservar Paulo e Cunha.
RAIZES_PEJORATIVAS_FORTES = (
    "arrombad",
    "babac",
    "baitol",
    "bichon",
    "biscat",
    "bocet",
    "boiol",
    "boquet",
    "bost",
    "broch",
    "brox",
    "bucet",
    "burr",
    "cachorr",
    "cadel",
    "cag",
    "caralh",
    "canalh",
    "chifrud",
    "cretin",
    "desgrac",
    "escrot",
    "estupid",
    "filhadaputa",
    "filhaodaputa",
    "filhadeumaputa",
    "filhodaputa",
    "filhodeumaputa",
    "fodid",
    "fudend",
    "fudid",
    "imund",
    "idiot",
    "imbecil",
    "lazarent",
    "maldit",
    "macac",
    "merd",
    "meretriz",
    "miseravel",
    "mongol",
    "nojent",
    "otari",
    "palhac",
    "paspalh",
    "piranha",
    "piriguet",
    "piroc",
    "prostitut",
    "punhet",
    "puta",
    "putinh",
    "retardad",
    "ridicul",
    "safad",
    "tapad",
    "tarad",
    "vagabund",
    "vadi",
    "vead",
    "viad",
    "xerec",
    "xoxot",
)


def _resultado_invalido(motivo):
    if motivo == MOTIVO_ESTRUTURA_IMPROVAVEL:
        return ResultadoValidacaoNome(
            False,
            motivo=motivo,
            status=STATUS_AMBIGUO,
            confianca=0.65,
        )

    return ResultadoValidacaoNome(
        False,
        motivo=motivo,
        status=STATUS_INVALIDO,
        confianca=0.99,
    )


def _calcular_confianca_nome(
    candidato_original,
    palavras_declaradas,
    *,
    permitir_sobrenomes,
):
    candidato_normalizado = tuple(
        normalizar_texto(palavra)
        for palavra in candidato_original
    )

    if candidato_normalizado in PRIMEIROS_NOMES_COMPOSTOS:
        return 0.99

    if permitir_sobrenomes:
        return 0.98

    if len(candidato_normalizado) == 2:
        return 0.90

    if (
        candidato_normalizado
        and candidato_normalizado[0] in PALAVRAS_AMBIGUAS_COMO_NOME
    ):
        return 0.82

    if len(palavras_declaradas) == 1:
        return 0.95

    return 0.92


def validar_nome_cliente(texto):
    if not isinstance(texto, str):
        return _resultado_invalido(MOTIVO_TIPO_INVALIDO)

    texto_original, motivo_seguranca = normalizar_entrada_nome(texto)

    if motivo_seguranca:
        return _resultado_invalido(MOTIVO_CARACTERE_INVALIDO)

    if not texto_original:
        return _resultado_invalido(MOTIVO_VAZIO)

    if PADRAO_DIGITO.search(texto_original):
        return _resultado_invalido(MOTIVO_NUMERO)

    texto_preparado = _preparar_texto_nome(texto_original)

    if not texto_preparado:
        return _resultado_invalido(MOTIVO_SEM_LETRAS)

    if _tem_caractere_invalido(texto_preparado):
        return _resultado_invalido(MOTIVO_CARACTERE_INVALIDO)

    palavras_originais = texto_preparado.split()

    if not palavras_originais:
        return _resultado_invalido(MOTIVO_SEM_LETRAS)

    palavras_normalizadas = [
        normalizar_texto(palavra)
        for palavra in palavras_originais
    ]

    if _tem_palavra_pejorativa(palavras_normalizadas):
        return _resultado_invalido(MOTIVO_TERMO_PEJORATIVO)

    (
        candidato_original,
        palavras_declaradas,
        permitir_sobrenomes,
        motivo_extracao,
    ) = extrair_candidato_nome(
        palavras_originais,
        palavras_normalizadas,
    )

    if motivo_extracao:
        return _resultado_invalido(motivo_extracao)

    if any(
        not _comprimento_valido(palavra)
        for palavra in palavras_declaradas
    ):
        return _resultado_invalido(MOTIVO_COMPRIMENTO_INVALIDO)

    if any(
        _tem_tres_letras_repetidas(palavra)
        for palavra in palavras_declaradas
    ):
        return _resultado_invalido(MOTIVO_REPETICAO_CARACTERE)

    if _tem_palavra_fora_contexto(
        palavras_declaradas,
        permitir_sobrenomes=permitir_sobrenomes,
    ):
        return _resultado_invalido(MOTIVO_FORA_CONTEXTO)

    if any(
        PADRAO_FRASE_COMPACTADA.fullmatch(palavra)
        for palavra in palavras_declaradas
    ):
        return _resultado_invalido(MOTIVO_FORA_CONTEXTO)

    if any(
        _tem_estrutura_improvavel(palavra)
        for palavra in palavras_declaradas
        if not (
            permitir_sobrenomes
            and palavra in CONECTORES_SOBRENOME
        )
    ):
        return _resultado_invalido(MOTIVO_ESTRUTURA_IMPROVAVEL)

    primeiro_nome = _formatar_nome_cliente(candidato_original)

    return ResultadoValidacaoNome(
        True,
        primeiro_nome=primeiro_nome,
        status=STATUS_VALIDO,
        confianca=_calcular_confianca_nome(
            candidato_original,
            palavras_normalizadas,
            permitir_sobrenomes=permitir_sobrenomes,
        ),
    )


def detecta_nome_invalido(texto):
    return not validar_nome_cliente(texto).valido


def extrair_primeiro_nome_cliente(texto):
    return validar_nome_cliente(texto).primeiro_nome


def extrair_candidato_nome(palavras_originais, palavras_normalizadas):
    # Aceita abreviações informais como "e João", "eh João" e "he João"
    # somente porque esta função é usada na etapa que pergunta o nome.
    if _primeira_palavra_e_apresentacao_curta(palavras_originais):
        return _extrair_nome_declarado(
            palavras_originais[1:],
            palavras_normalizadas[1:],
        )

    prefixo = _encontrar_prefixo(
        palavras_normalizadas,
        PREFIXOS_APRESENTACAO_COMPLETA,
    )

    if prefixo:
        inicio_nome = len(prefixo)
        return _extrair_nome_declarado(
            palavras_originais[inicio_nome:],
            palavras_normalizadas[inicio_nome:],
        )

    prefixo = _encontrar_prefixo(
        palavras_normalizadas,
        PREFIXOS_APRESENTACAO_ESTRITA,
    )

    if prefixo:
        inicio_nome = len(prefixo)
        return _extrair_nome_declarado(
            palavras_originais[inicio_nome:],
            palavras_normalizadas[inicio_nome:],
        )

    return _extrair_nome_declarado(
        palavras_originais,
        palavras_normalizadas,
    )


def _extrair_nome_declarado(nome_original, nome_normalizado):
    if not nome_original:
        return (), (), False, MOTIVO_FORA_CONTEXTO

    quantidade_candidato = 1
    primeiro_nome_composto = tuple(
        nome_normalizado[:QUANTIDADE_MAXIMA_PALAVRAS_NOME]
    )

    if (
        len(nome_normalizado) >= 2
        and (
            primeiro_nome_composto in PRIMEIROS_NOMES_COMPOSTOS
            or (
                nome_normalizado[1] not in CONECTORES_SOBRENOME
                and not _e_sobrenome_comum(nome_normalizado[1])
            )
        )
    ):
        quantidade_candidato = QUANTIDADE_MAXIMA_PALAVRAS_NOME

    candidato_original = tuple(nome_original[:quantidade_candidato])
    cauda_sobrenome = tuple(nome_normalizado[quantidade_candidato:])

    if cauda_sobrenome and not _cauda_sobrenome_valida(cauda_sobrenome):
        motivo = MOTIVO_MULTIPLAS_PALAVRAS

        if any(
            palavra in PALAVRAS_FORA_CONTEXTO
            and palavra not in CONECTORES_SOBRENOME
            and palavra not in SOBRENOMES_COMUNS_BRASIL
            for palavra in cauda_sobrenome
        ):
            motivo = MOTIVO_FORA_CONTEXTO

        return (
            (),
            tuple(nome_normalizado),
            False,
            motivo,
        )

    return (
        candidato_original,
        tuple(nome_normalizado),
        bool(cauda_sobrenome),
        None,
    )


def _cauda_sobrenome_valida(palavras):
    palavras = tuple(palavras)

    for cauda_tradicional in CAUDAS_NOMES_TRADICIONAIS:
        if palavras[:len(cauda_tradicional)] != cauda_tradicional:
            continue

        palavras = palavras[len(cauda_tradicional):]

        if not palavras:
            return True

        break

    encontrou_sobrenome = False
    conector_anterior = False

    for palavra in palavras:
        if palavra in CONECTORES_SOBRENOME:
            if conector_anterior:
                return False

            conector_anterior = True
            continue

        if not _e_sobrenome_comum(palavra):
            return False

        encontrou_sobrenome = True
        conector_anterior = False

    return encontrou_sobrenome and not conector_anterior


def _e_sobrenome_comum(palavra):
    palavra_compactada = re.sub(r"[-'’]", "", palavra)
    return palavra_compactada in SOBRENOMES_COMUNS_BRASIL


def _primeira_palavra_e_apresentacao_curta(palavras_originais):
    if not palavras_originais:
        return False

    primeira_palavra = unicodedata.normalize(
        "NFC",
        palavras_originais[0],
    ).casefold()

    return primeira_palavra in APRESENTACOES_CURTAS_NOME


def _encontrar_prefixo(palavras, prefixos):
    for prefixo in prefixos:
        if tuple(palavras[:len(prefixo)]) == prefixo:
            return prefixo

    return None


def _preparar_texto_nome(texto):
    texto_preparado = PADRAO_CORTESIA_FINAL.sub("", texto).rstrip()
    texto_preparado = PADRAO_SAUDACAO_INICIAL.sub(
        "",
        texto_preparado,
        count=1,
    )
    texto_preparado = PADRAO_PONTUACAO_FINAL.sub(
        "",
        texto_preparado,
    ).rstrip()

    texto_preparado = PADRAO_PRAZER_COM_VIRGULA.sub(
        r"\1 ",
        texto_preparado,
        count=1,
    )
    texto_preparado = PADRAO_IDENTIFICACAO_COM_DOIS_PONTOS.sub(
        r"\1 ",
        texto_preparado,
        count=1,
    )

    return texto_preparado.strip()


def _tem_caractere_invalido(texto):
    for indice, caractere in enumerate(texto):
        if caractere.isalpha() or caractere.isspace():
            continue

        if caractere not in {"-", "'", "’"}:
            return True

        if indice == 0 or indice == len(texto) - 1:
            return True

        if not texto[indice - 1].isalpha():
            return True

        if not texto[indice + 1].isalpha():
            return True

    return False


def _comprimento_valido(texto):
    return TAMANHO_MINIMO_PRIMEIRO_NOME <= len(
        texto
    ) <= TAMANHO_MAXIMO_PRIMEIRO_NOME


def _tem_tres_letras_repetidas(texto):
    return bool(PADRAO_REPETICAO_CARACTERE.search(texto))


def _tem_palavra_pejorativa(palavras):
    if any(_palavra_e_pejorativa(palavra) for palavra in palavras):
        return True

    # Também reconhece tentativas como "p.u.t.a" e "p#u#t#a", sem usar essa
    # compactação para aceitar nomes ou frases.
    return _palavra_e_pejorativa("".join(palavras))


def _palavra_e_pejorativa(palavra):
    palavra_normalizada = re.sub(r"[-'’]", "", palavra.lower())

    if palavra_normalizada in PALAVRAS_NOME_PEJORATIVAS:
        return True

    return (
        palavra_normalizada.startswith(RAIZES_PEJORATIVAS_FORTES)
        or palavra_normalizada.endswith(RAIZES_PEJORATIVAS_FORTES)
    )


def _tem_palavra_fora_contexto(palavras, *, permitir_sobrenomes):
    return any(
        _palavra_ou_componente_fora_contexto(
            palavra,
            permitir_sobrenomes=permitir_sobrenomes,
        )
        for palavra in palavras
    )


def _palavra_ou_componente_fora_contexto(
    palavra,
    *,
    permitir_sobrenomes,
):
    componentes = re.split(r"[-'’]", palavra)

    return any(
        (
            componente in PALAVRAS_FORA_CONTEXTO
            or PADRAO_REACAO_CONVERSACIONAL.fullmatch(componente)
        )
        and not (
            permitir_sobrenomes
            and (
                componente in CONECTORES_SOBRENOME
                or componente in PALAVRAS_CAUDAS_NOMES_TRADICIONAIS
                or _e_sobrenome_comum(componente)
            )
        )
        for componente in componentes
        if componente
    )


def _tem_estrutura_improvavel(texto):
    if not PADRAO_VOGAL.search(texto):
        return True

    return bool(PADRAO_CINCO_CONSOANTES.search(texto))


def _formatar_nome_cliente(palavras):
    return " ".join(
        _formatar_palavra_nome(palavra)
        for palavra in palavras
    )


def _formatar_palavra_nome(palavra):
    partes = re.split(r"([-\'’])", palavra)

    if len(partes) > 1:
        return "".join(
            parte
            if parte in {"-", "'", "’"}
            else _formatar_parte_nome(parte)
            for parte in partes
        )

    return _formatar_parte_nome(palavra)


def _formatar_parte_nome(palavra):
    chave_normalizada = normalizar_texto(palavra)
    nome_com_til = NOMES_BRASILEIROS_COM_TIL.get(chave_normalizada)

    if nome_com_til:
        return nome_com_til

    return palavra[:1].upper() + palavra[1:].lower()
