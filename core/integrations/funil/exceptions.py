"""Erros conhecidos da integração com o Funil de Vendas."""


class ErroIntegracaoFunil(RuntimeError):
    """Falha de transporte ou resposta incompatível da API do Funil."""


class RespostaFunilInvalida(ErroIntegracaoFunil):
    """A API respondeu, mas o corpo não segue o contrato esperado."""


class OportunidadeRejeitadaFunil(ErroIntegracaoFunil):
    """O Funil recebeu o POST, mas recusou a oportunidade."""

