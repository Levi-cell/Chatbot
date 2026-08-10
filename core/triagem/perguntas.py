"""Perguntas canônicas das etapas 12 a 17 da triagem."""


FAIXA_ETARIA_INFANTIL = "infantil"
FAIXA_ETARIA_ADULTA = "adulta"

ETAPAS_PERGUNTAS_TRIAGEM = {
    12: {
        FAIXA_ETARIA_INFANTIL: (
            "Com que frequência {pessoa} se distrai com facilidade durante "
            "tarefas ou atividades escolares?"
        ),
        FAIXA_ETARIA_ADULTA: (
            "Com que frequência {pessoa} esquece compromissos, recados ou "
            "onde guardou objetos pessoais?"
        ),
    },
    13: {
        FAIXA_ETARIA_INFANTIL: (
            "Com que frequência {pessoa} tem dificuldade para concluir uma "
            "atividade que começou?"
        ),
        FAIXA_ETARIA_ADULTA: (
            "Com que frequência {pessoa} tem dificuldade para lembrar nomes, "
            "palavras ou informações recentes?"
        ),
    },
    14: {
        FAIXA_ETARIA_INFANTIL: (
            "Com que frequência {pessoa} esquece com frequência orientações "
            "ou conteúdos que acabou de aprender?"
        ),
        FAIXA_ETARIA_ADULTA: (
            "Com que frequência {pessoa} se distrai com facilidade durante "
            "conversas, leituras ou atividades do dia a dia?"
        ),
    },
    15: {
        FAIXA_ETARIA_INFANTIL: (
            "Com que frequência {pessoa} precisa que as instruções sejam "
            "repetidas várias vezes para conseguir realizá-las?"
        ),
        FAIXA_ETARIA_ADULTA: (
            "Com que frequência {pessoa} tem dificuldade para manter a "
            "concentração e concluir uma tarefa que começou?"
        ),
    },
    16: {
        FAIXA_ETARIA_INFANTIL: (
            "Com que frequência {pessoa} passa mais de 4h por dia em frente a "
            "telas (celular, tablet ou TV)?"
        ),
        FAIXA_ETARIA_ADULTA: (
            "Com que frequência {pessoa} se sente ansioso(a), preocupado(a) "
            "ou com a mente muito acelerada?"
        ),
    },
    17: {
        FAIXA_ETARIA_INFANTIL: (
            "Com que frequência {pessoa} fica desmotivado(a), impaciente ou "
            "frustrado(a) diante de atividades que exigem concentração?"
        ),
        FAIXA_ETARIA_ADULTA: (
            "Com que frequência {pessoa} tem dificuldade para dormir?"
        ),
    },
}


def obter_faixa_etaria_triagem(idade):
    """Classifica a idade persistida sem aplicar a elegibilidade da unidade."""
    if (
        isinstance(idade, bool)
        or not isinstance(idade, int)
        or idade <= 0
        or idade >= 100
    ):
        raise ValueError("Idade inválida para selecionar a faixa da triagem")

    if idade < 18:
        return FAIXA_ETARIA_INFANTIL

    return FAIXA_ETARIA_ADULTA


def montar_pergunta_triagem(
    id_etapa,
    *,
    faixa_etaria,
    nome_pessoa=None,
):
    """Monta a pergunta da etapa para uma criança, adulto ou titular."""
    perguntas_etapa = ETAPAS_PERGUNTAS_TRIAGEM.get(id_etapa)
    if perguntas_etapa is None:
        raise ValueError(f"Etapa fora da triagem: {id_etapa}")

    modelo = perguntas_etapa.get(faixa_etaria)
    if modelo is None:
        raise ValueError(f"Faixa etária da triagem inválida: {faixa_etaria}")

    nome_normalizado = ""
    if isinstance(nome_pessoa, str):
        nome_normalizado = nome_pessoa.strip()

    if faixa_etaria == FAIXA_ETARIA_INFANTIL and not nome_normalizado:
        raise ValueError("Nome da pessoa é obrigatório na triagem infantil")

    pessoa = nome_normalizado or "você"
    return modelo.format(pessoa=pessoa)
