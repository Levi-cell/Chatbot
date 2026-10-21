class BancoFalhouAposEnvioMeta(Exception):
    def __init__(
        self,
        mensagem,
        id_mensagem=None,
        id_conversa=None,
        id_hash_msg_bot=None,
        id_etapa=None,
    ):
        super().__init__(mensagem)
        self.id_mensagem = id_mensagem
        self.id_conversa = id_conversa
        self.id_hash_msg_bot = id_hash_msg_bot
        self.id_etapa = id_etapa
