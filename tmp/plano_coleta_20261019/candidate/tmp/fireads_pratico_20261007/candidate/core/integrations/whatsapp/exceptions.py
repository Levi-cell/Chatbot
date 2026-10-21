class ErroEnvioMeta(Exception):
    def __init__(self, mensagem, id_etapa=None, phone_id_unidade=None, cliente_telefone=None):
        super().__init__(mensagem)
        self.id_etapa = id_etapa
        self.phone_id_unidade = phone_id_unidade
        self.cliente_telefone = cliente_telefone
