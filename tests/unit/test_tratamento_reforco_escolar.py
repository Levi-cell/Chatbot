import importlib
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from core.integrations.whatsapp.messages.componentes_compartilhados import (
    RODAPE_ETAPA1_BOAS_VINDAS,
    RODAPE_OPCAO_UNICA,
)
from core.integrations.whatsapp.messages.tratamentos_universais import (
    MENSAGEM_TRATAMENTO_REFORCO_ESCOLAR,
    montar_mensagem_tratamento_reforco_escolar,
)
from workers.worker_flow.response_flow.etapas.validadores_universais.validador_financeiro import (
    validar_pergunta_financeira,
)
from workers.worker_flow.response_flow.etapas.validadores_universais.validador_reforco_escolar import (
    TIPO_TRATAMENTO_REFORCO_ESCOLAR,
    validar_duvida_reforco_escolar,
)
from workers.worker_flow.response_flow.etapas.validadores_contexto.validador_reforco_escolar_etapa4 import (
    validar_duvida_reforco_escolar_etapa4,
)


class _ClienteWhatsAppFake:
    def __init__(self):
        self.ultimo_envio = None

    def send_message(self, **kwargs):
        self.ultimo_envio = kwargs
        return SimpleNamespace(id="wamid.reforco-escolar")


def _contexto_historico(etapa, texto, tipo_mensagem="text", *, dependente=False):
    return {
        "id_conversa": 100 + etapa,
        "id_etapa_atual": etapa,
        "id_etapa_cliente": etapa,
        "id_etapa_origem_transicao": etapa,
        "transicoes_permitidas": {},
        "texto_cliente_atual": texto,
        "tipo_mensagem_atual": tipo_mensagem,
        "status_dependente": dependente,
        "nome_cliente": "Maria",
        "nome_dependente": "Ana" if dependente else None,
        "idade_pessoa_triagem": 12 if dependente else 30,
        "nome_unidade": "Supera Centro",
        "link_agendamento_unidade": "https://agenda.example/teste",
        "link_instagram_unidade": "https://instagram.com/supera",
        "mensagem_cliente_atual": {
            "id_mensagem_fila": 200 + etapa,
            "id_hash_msg": "wamid.cliente",
            "cliente_telefone": "5571999999999",
            "id_phone_unidade": "phone-id",
        },
    }


def _contexto_envio_tratamento(etapa, tipo_tratamento):
    return {
        "enviou": True,
        "resposta_ja_existia": False,
        "mensagem_bot": "mensagem de tratamento",
        "id_hash_msg_bot": "wamid.bot",
        "id_etapa_resultante": etapa,
        "tipo_mensagem": "text",
        "tratamento": True,
        "tipo_tratamento": tipo_tratamento,
    }


_VINCULOS_PROFISSIONAIS_ETAPA4 = (
    "Trabalho em uma banca",
    "Trabalho em um cursinho",
    "Trabalho em um supletivo",
    "Trabalho em um reforço escolar",
    "Trabalho em um reforço",
    "Trabalho em um reforço escola",
    "Sou professora de matemática em uma banca",
    "Sou professor de português em um cursinho",
    "Sou dona de uma banca",
    "Sou dono de um supletivo",
    "Sou diretora de um reforço escolar",
    "Sou diretor de um supletivo",
    "Sou técnico de um cursinho",
    "Sou técnica de um reforço escolar",
    "Sou coordenadora de um reforço",
    "Diretora de uma banca",
)


class ValidadorReforcoEscolarTests(unittest.TestCase):
    def test_tipo_do_tratamento_e_estavel(self):
        self.assertEqual(
            TIPO_TRATAMENTO_REFORCO_ESCOLAR,
            "duvida_reforco_escolar",
        )

    def test_identifica_servicos_escolares_e_formas_naturais(self):
        frases = (
            "É reforço escolar?",
            "Vocês são uma banca?",
            "Tem banca escolar?",
            "Vocês oferecem supletivo?",
            "Trabalham com EJA?",
            "Isso é um cursinho?",
            "Tem pré-vestibular?",
            "É preparatório para o Enem?",
            "Vocês oferecem aula particular?",
            "Tem professor particular?",
            "Faz acompanhamento escolar?",
            "Ajuda com tarefa de casa?",
            "REFORÇO ESCOLAR",
            "banca",
        )

        for frase in frases:
            with self.subTest(frase=frase):
                self.assertTrue(validar_duvida_reforco_escolar(frase))

    def test_identifica_materias_apenas_com_intencao_de_ensino(self):
        frases = (
            "Vocês ensinam matemática?",
            "Tem aula de português?",
            "Preciso de ajuda em física",
            "Vocês dão reforço de redação?",
            "Quero acompanhamento escolar em química",
            "Tem professor de inglês?",
        )

        for frase in frases:
            with self.subTest(frase=frase):
                self.assertTrue(validar_duvida_reforco_escolar(frase))

    def test_nao_confunde_profissao_ou_palavras_com_outro_sentido(self):
        frases = (
            "Sou professora de matemática",
            "Trabalho como professor de português",
            "Trabalho com português",
            "Sou bancário",
            "Participo de banca examinadora do concurso",
            "Quero reforçar minha memória",
            "Uso reforço positivo",
            "O Supera é um curso de estimulação cognitiva",
            "Quero a aula gratuita",
            "Meu filho gosta de matemática",
            "Quero atendimento em português",
            "A matemática está presente no raciocínio",
            "curso superior",
            "professor",
            "",
            None,
        )

        for frase in frases:
            with self.subTest(frase=frase):
                self.assertFalse(validar_duvida_reforco_escolar(frase))

    def test_limites_de_palavra_e_tipos_invalidos(self):
        for frase in (
            "bancário",
            "bancária",
            "reforçou",
            "cursista",
            123,
            object(),
        ):
            with self.subTest(frase=frase):
                self.assertFalse(validar_duvida_reforco_escolar(frase))

    def test_formas_adicionais_preservam_intencao_e_barram_bancas_nao_escolares(
        self,
    ):
        positivos = (
            "\u00c9 tipo refor\u00e7o?",
            "Tem pr\u00e9-Enem?",
            "Voc\u00eas preparam para o Enem?",
            "Prepara para vestibular?",
            "Voc\u00eas ajudam meu filho com matem\u00e1tica?",
            "Ajudam a crian\u00e7a com portugu\u00eas?",
            "Tiram d\u00favidas de matem\u00e1tica?",
            "Tem curso de matem\u00e1tica?",
            "\u00c9 apoio pedag\u00f3gico?",
            "Voc\u00eas trabalham com matem\u00e1tica?",
            "Tem matem\u00e1tica?",
            "Curso de portugu\u00eas?",
            "Banca de matem\u00e1tica?",
            "Refor\u00e7o pro meu filho",
        )
        negativos = (
            "Voc\u00eas s\u00e3o uma banca examinadora?",
            "Voc\u00eas s\u00e3o uma banca de concurso?",
            "Esta \u00e9 uma banca de TCC?",
            "Meu filho tem dificuldade em matem\u00e1tica",
            "Sou professora de refor\u00e7o escolar",
            "Trabalho como professora de cursinho",
            "Professora particular",
            "Trabalho com aulas particulares",
            "Dou aula particular",
            "Professora de refor\u00e7o escolar",
        )

        for frase in positivos:
            with self.subTest(frase=frase):
                self.assertTrue(validar_duvida_reforco_escolar(frase))

        for frase in negativos:
            with self.subTest(frase=frase):
                self.assertFalse(validar_duvida_reforco_escolar(frase))

    def test_sobreposicao_com_financeiro_e_detectada_pelos_dois(self):
        frase = "Quanto custa o reforço escolar?"

        self.assertTrue(validar_duvida_reforco_escolar(frase))
        self.assertTrue(validar_pergunta_financeira(frase))

    def test_etapa4_preserva_vinculos_profissionais_com_servicos_escolares(
        self,
    ):
        for profissao in _VINCULOS_PROFISSIONAIS_ETAPA4:
            with self.subTest(profissao=profissao):
                self.assertFalse(
                    validar_duvida_reforco_escolar_etapa4(profissao)
                )

    def test_etapa4_continua_tratando_duvidas_reais(self):
        duvidas = (
            "O Supera é uma banca?",
            "Vocês têm cursinho?",
            "Isso é supletivo?",
            "É reforço escolar?",
            "Tem aula de matemática?",
        )

        for duvida in duvidas:
            with self.subTest(duvida=duvida):
                self.assertTrue(
                    validar_duvida_reforco_escolar_etapa4(duvida)
                )


class MensagemUniversalReforcoEscolarTests(unittest.TestCase):
    def test_mensagem_universal_preserva_texto_e_retomada(self):
        retomada = "Me diz, qual é o seu primeiro nome?"
        mensagem = montar_mensagem_tratamento_reforco_escolar(retomada)

        self.assertEqual(
            mensagem,
            f"{MENSAGEM_TRATAMENTO_REFORCO_ESCOLAR}\n\n"
            f"Mas bora lá:\n\n{retomada}",
        )
        self.assertIn("o Supera não é reforço escolar", mensagem)
        self.assertIn("atenção, concentração, memória e raciocínio", mensagem)
        self.assertIn("🧠✨", mensagem)

    def test_todas_as_etapas_retomam_sem_jargao_de_entrada(self):
        montadores = (
            (1, "montar_mensagem_reforco_escolar_etapa1", ()),
            (2, "montar_mensagem_reforco_escolar_etapa2", ()),
            (3, "montar_mensagem_reforco_escolar_etapa3", (False,)),
            (3, "montar_mensagem_reforco_escolar_etapa3", (True,)),
            (4, "montar_mensagem_reforco_escolar_etapa4", ()),
            (5, "montar_mensagem_reforco_escolar_etapa5", ()),
            (6, "montar_mensagem_idade_etapa6_reforco_escolar", ()),
            (
                6,
                "montar_mensagem_idade_dependente_etapa6_reforco_escolar",
                ("Ana",),
            ),
            (
                7,
                "montar_mensagem_oferta_cliente_reforco_escolar_etapa7",
                (),
            ),
            (
                7,
                "montar_mensagem_oferta_dependente_reforco_escolar_etapa7",
                ("Ana",),
            ),
            (
                9,
                "montar_mensagem_retorno_cliente_reforco_escolar_etapa9",
                (),
            ),
            (
                9,
                "montar_mensagem_retorno_dependente_reforco_escolar_etapa9",
                ("Ana",),
            ),
            (
                10,
                "montar_mensagem_email_etapa10_reforco_escolar",
                (),
            ),
            (11, "montar_mensagem_reforco_escolar_etapa11", ()),
            (
                18,
                "montar_mensagem_reforco_escolar_etapa18",
                ("https://agenda.example/teste",),
            ),
            (20, "montar_mensagem_reforco_escolar_etapa20", ()),
        )
        jargoes_iniciais = (
            "entendi",
            "certo",
            "perfeito",
            "maravilha",
            "prazer",
            "que bom",
            "obrigada",
        )

        for etapa, nome_funcao, argumentos in montadores:
            modulo = importlib.import_module(
                "core.integrations.whatsapp.messages."
                f"etapa{etapa}_messages"
            )
            montar = getattr(modulo, nome_funcao)

            with self.subTest(etapa=etapa, montador=nome_funcao):
                mensagem = montar(*argumentos)
                self.assertIn(MENSAGEM_TRATAMENTO_REFORCO_ESCOLAR, mensagem)
                self.assertEqual(mensagem.count("Mas bora lá:"), 1)

                retomada = mensagem.split("Mas bora lá:\n\n", 1)[1]
                retomada_normalizada = retomada.lstrip().casefold()
                self.assertFalse(
                    retomada_normalizada.startswith(jargoes_iniciais),
                    retomada,
                )

    def test_variantes_preservam_estado_nome_e_link(self):
        etapa3 = importlib.import_module(
            "core.integrations.whatsapp.messages.etapa3_messages"
        )
        etapa6 = importlib.import_module(
            "core.integrations.whatsapp.messages.etapa6_messages"
        )
        etapa7 = importlib.import_module(
            "core.integrations.whatsapp.messages.etapa7_messages"
        )
        etapa9 = importlib.import_module(
            "core.integrations.whatsapp.messages.etapa9_messages"
        )
        etapa18 = importlib.import_module(
            "core.integrations.whatsapp.messages.etapa18_messages"
        )

        self.assertIn(
            "para você?",
            etapa3.montar_mensagem_reforco_escolar_etapa3(False),
        )
        self.assertIn(
            "para um dependente?",
            etapa3.montar_mensagem_reforco_escolar_etapa3(True),
        )

        dependentes = (
            etapa6.montar_mensagem_idade_dependente_etapa6_reforco_escolar,
            etapa7.montar_mensagem_oferta_dependente_reforco_escolar_etapa7,
            etapa9.montar_mensagem_retorno_dependente_reforco_escolar_etapa9,
        )
        for montar in dependentes:
            with self.subTest(montador=montar.__name__):
                self.assertIn("Ana", montar("Ana"))

        link = "https://agenda.example/teste"
        mensagem_agendamento = (
            etapa18.montar_mensagem_reforco_escolar_etapa18(link)
        )
        self.assertIn(link, mensagem_agendamento)
        self.assertIn(
            etapa18.RODAPE_ETAPA18_AGENDAMENTO,
            mensagem_agendamento,
        )


class SendersReforcoEscolarTests(unittest.TestCase):
    def test_senders_preservam_contrato_de_permanencia_nas_doze_etapas(self):
        casos = (
            (1, "enviar_etapa1_reforco_escolar", ()),
            (
                1,
                "enviar_etapa1_reforco_escolar_inicio",
                ("Supera Centro",),
            ),
            (2, "enviar_etapa2_reforco_escolar", ()),
            (3, "enviar_etapa3_reforco_escolar", (False,)),
            (3, "enviar_etapa3_reforco_escolar", (True,)),
            (4, "enviar_etapa4_reforco_escolar", ()),
            (5, "enviar_etapa5_reforco_escolar", ()),
            (6, "enviar_etapa6_cliente_reforco_escolar", ()),
            (
                6,
                "enviar_etapa6_dependente_reforco_escolar",
                ("Ana",),
            ),
            (7, "enviar_etapa7_cliente_reforco_escolar", ()),
            (
                7,
                "enviar_etapa7_dependente_reforco_escolar",
                ("Ana",),
            ),
            (9, "enviar_etapa9_cliente_reforco_escolar", ()),
            (
                9,
                "enviar_etapa9_dependente_reforco_escolar",
                ("Ana",),
            ),
            (10, "enviar_etapa10_reforco_escolar", ()),
            (11, "enviar_etapa11_reforco_escolar", ()),
            (
                18,
                "enviar_etapa18_reforco_escolar",
                ("https://agenda.example/teste",),
            ),
            (20, "enviar_etapa20_reforco_escolar", ()),
        )

        for etapa, nome_sender, argumentos in casos:
            modulo = importlib.import_module(
                "core.integrations.whatsapp.pywa_functions.pywa_senders."
                f"etapa{etapa}"
            )
            enviar = getattr(modulo, nome_sender)
            cliente = _ClienteWhatsAppFake()

            with self.subTest(etapa=etapa, sender=nome_sender), patch.object(
                modulo,
                "conta_wa",
                return_value=cliente,
            ):
                contexto = enviar(
                    "5571999999999",
                    "phone-id",
                    *argumentos,
                )

            self.assertTrue(contexto["tratamento"])
            self.assertEqual(
                contexto["tipo_tratamento"],
                TIPO_TRATAMENTO_REFORCO_ESCOLAR,
            )
            self.assertEqual(contexto["id_etapa_resultante"], etapa)
            self.assertNotIn("evento_transicao", contexto)
            self.assertIn(
                MENSAGEM_TRATAMENTO_REFORCO_ESCOLAR,
                cliente.ultimo_envio["text"],
            )
            self.assertIn("Mas bora lá:", cliente.ultimo_envio["text"])

    def test_senders_preservam_botoes_rodapes_e_link(self):
        etapas_com_botoes = (2, 3, 7, 9, 11, 18, 20)
        nomes_senders = {
            2: ("enviar_etapa2_reforco_escolar", ()),
            3: ("enviar_etapa3_reforco_escolar", (False,)),
            7: ("enviar_etapa7_cliente_reforco_escolar", ()),
            9: ("enviar_etapa9_cliente_reforco_escolar", ()),
            11: ("enviar_etapa11_reforco_escolar", ()),
            18: (
                "enviar_etapa18_reforco_escolar",
                ("https://agenda.example/teste",),
            ),
            20: ("enviar_etapa20_reforco_escolar", ()),
        }

        for etapa in etapas_com_botoes:
            modulo_sender = importlib.import_module(
                "core.integrations.whatsapp.pywa_functions.pywa_senders."
                f"etapa{etapa}"
            )
            modulo_mensagens = importlib.import_module(
                "core.integrations.whatsapp.messages."
                f"etapa{etapa}_messages"
            )
            nome_sender, argumentos = nomes_senders[etapa]
            cliente = _ClienteWhatsAppFake()

            with self.subTest(etapa=etapa), patch.object(
                modulo_sender,
                "conta_wa",
                return_value=cliente,
            ):
                getattr(modulo_sender, nome_sender)(
                    "5571999999999",
                    "phone-id",
                    *argumentos,
                )

            titulos_esperados = list(
                getattr(modulo_mensagens, f"montar_botoes_etapa{etapa}")()
            )
            titulos_enviados = [
                botao.title for botao in cliente.ultimo_envio["buttons"]
            ]
            self.assertEqual(titulos_enviados, titulos_esperados)

            if etapa in (2, 3, 7, 9):
                self.assertIn(
                    RODAPE_OPCAO_UNICA,
                    cliente.ultimo_envio["text"],
                )

            if etapa == 18:
                self.assertIn(
                    "https://agenda.example/teste",
                    cliente.ultimo_envio["text"],
                )
                self.assertIn(
                    modulo_mensagens.RODAPE_ETAPA18_AGENDAMENTO,
                    cliente.ultimo_envio["text"],
                )

    def test_inicio_da_etapa1_preserva_apresentacao_e_rodape(self):
        modulo = importlib.import_module(
            "core.integrations.whatsapp.pywa_functions.pywa_senders.etapa1"
        )
        cliente = _ClienteWhatsAppFake()

        with (
            patch.object(modulo, "conta_wa", return_value=cliente),
            patch.object(
                modulo,
                "obter_saudacao_por_horario",
                return_value="Bom dia",
            ),
        ):
            contexto = modulo.enviar_etapa1_reforco_escolar_inicio(
                "5571999999999",
                "phone-id",
                "Supera Centro",
            )

        texto = cliente.ultimo_envio["text"]
        self.assertIn("Bom dia! Sou a Suh", texto)
        self.assertIn("Supera Centro", texto)
        self.assertIn(RODAPE_ETAPA1_BOAS_VINDAS, texto)
        self.assertEqual(contexto["id_etapa_resultante"], 1)
        self.assertTrue(contexto["tratamento"])


class ResolversReforcoEscolarTests(unittest.TestCase):
    _ROTAS = (
        (
            1,
            "enviar_etapa1_midia",
            "enviar_etapa1_reforco_escolar",
            "enviar_etapa1_financeiro",
        ),
        (
            2,
            "enviar_etapa2_midia",
            "enviar_etapa2_reforco_escolar",
            "enviar_etapa2_financeiro",
        ),
        (
            3,
            "enviar_etapa3_midia",
            "enviar_etapa3_reforco_escolar",
            "enviar_etapa3_financeiro",
        ),
        (
            4,
            "enviar_etapa4_midia",
            "enviar_etapa4_reforco_escolar",
            "enviar_etapa4_financeiro",
        ),
        (
            5,
            "enviar_etapa5_midia",
            "enviar_etapa5_reforco_escolar",
            "enviar_etapa5_financeiro",
        ),
        (
            6,
            "enviar_etapa6_cliente_midia",
            "enviar_etapa6_cliente_reforco_escolar",
            "enviar_etapa6_cliente_financeiro",
        ),
        (
            7,
            "enviar_etapa7_cliente_midia",
            "enviar_etapa7_cliente_reforco_escolar",
            "enviar_etapa7_cliente_financeiro",
        ),
        (
            9,
            "enviar_etapa9_cliente_midia",
            "enviar_etapa9_cliente_reforco_escolar",
            "enviar_etapa9_cliente_financeiro",
        ),
        (
            10,
            "enviar_etapa10_midia",
            "enviar_etapa10_reforco_escolar",
            "enviar_etapa10_financeiro",
        ),
        (
            11,
            "enviar_etapa11_midia",
            "enviar_etapa11_reforco_escolar",
            "enviar_etapa11_financeiro",
        ),
        (
            18,
            "enviar_etapa18_midia",
            "enviar_etapa18_reforco_escolar",
            "enviar_etapa18_financeiro",
        ),
        (
            20,
            "enviar_etapa20_midia",
            "enviar_etapa20_reforco_escolar",
            "enviar_etapa20_financeiro",
        ),
    )

    def test_reforco_escolar_supera_financeiro_nas_doze_etapas(self):
        texto = "Quanto custa o reforço escolar?"

        for etapa, _, sender_reforco, sender_financeiro in self._ROTAS:
            modulo = importlib.import_module(
                "workers.worker_flow.response_flow.etapas."
                f"resolver_etapa{etapa}"
            )
            retorno = _contexto_envio_tratamento(
                etapa,
                TIPO_TRATAMENTO_REFORCO_ESCOLAR,
            )

            with (
                self.subTest(etapa=etapa),
                patch.object(
                    modulo,
                    sender_reforco,
                    return_value=retorno,
                ) as enviar_reforco,
                patch.object(modulo, sender_financeiro) as enviar_financeiro,
            ):
                resultado = getattr(modulo, f"resolve_etapa{etapa}")(
                    _contexto_historico(etapa, texto)
                )

            enviar_reforco.assert_called_once()
            enviar_financeiro.assert_not_called()
            self.assertEqual(resultado, retorno)
            self.assertTrue(resultado["tratamento"])
            self.assertEqual(
                resultado["tipo_tratamento"],
                TIPO_TRATAMENTO_REFORCO_ESCOLAR,
            )
            self.assertEqual(resultado["id_etapa_resultante"], etapa)
            self.assertNotIn("evento_transicao", resultado)

    def test_midia_supera_reforco_escolar_nas_doze_etapas(self):
        texto = "Quanto custa o reforço escolar?"

        for etapa, sender_midia, sender_reforco, _ in self._ROTAS:
            modulo = importlib.import_module(
                "workers.worker_flow.response_flow.etapas."
                f"resolver_etapa{etapa}"
            )
            retorno = _contexto_envio_tratamento(
                etapa,
                "tipo_mensagem_nao_suportado",
            )

            with (
                self.subTest(etapa=etapa),
                patch.object(
                    modulo,
                    sender_midia,
                    return_value=retorno,
                ) as enviar_midia,
                patch.object(modulo, sender_reforco) as enviar_reforco,
            ):
                resultado = getattr(modulo, f"resolve_etapa{etapa}")(
                    _contexto_historico(etapa, texto, "image")
                )

            enviar_midia.assert_called_once()
            enviar_reforco.assert_not_called()
            self.assertEqual(resultado, retorno)

    def test_variantes_dependentes_das_etapas_6_7_e_9(self):
        for etapa in (6, 7, 9):
            modulo = importlib.import_module(
                "workers.worker_flow.response_flow.etapas."
                f"resolver_etapa{etapa}"
            )
            sender_cliente = f"enviar_etapa{etapa}_cliente_reforco_escolar"
            sender_dependente = (
                f"enviar_etapa{etapa}_dependente_reforco_escolar"
            )
            retorno = _contexto_envio_tratamento(
                etapa,
                TIPO_TRATAMENTO_REFORCO_ESCOLAR,
            )

            with (
                self.subTest(etapa=etapa),
                patch.object(modulo, sender_cliente) as enviar_cliente,
                patch.object(
                    modulo,
                    sender_dependente,
                    return_value=retorno,
                ) as enviar_dependente,
            ):
                resultado = getattr(modulo, f"resolve_etapa{etapa}")(
                    _contexto_historico(
                        etapa,
                        "Vocês são reforço escolar?",
                        dependente=True,
                    )
                )

            enviar_dependente.assert_called_once_with(
                "5571999999999",
                "phone-id",
                "Ana",
            )
            enviar_cliente.assert_not_called()
            self.assertEqual(resultado, retorno)

    def test_etapa4_encaminha_vinculos_profissionais_sem_tratamento(self):
        modulo = importlib.import_module(
            "workers.worker_flow.response_flow.etapas.resolver_etapa4"
        )
        retorno_sender = {
            "enviou": True,
            "resposta_ja_existia": False,
            "mensagem_bot": "Qual é a sua idade?",
            "id_hash_msg_bot": "wamid.bot",
            "id_etapa_resultante": modulo.ETAPA_6_IDADE_ALUNO,
            "tipo_mensagem": "text",
        }

        for profissao in _VINCULOS_PROFISSIONAIS_ETAPA4:
            contexto = _contexto_historico(4, profissao)
            contexto["transicoes_permitidas"] = {
                modulo.EVENTO_PROFISSAO_TITULAR_VALIDA:
                    modulo.ETAPA_6_IDADE_ALUNO,
            }

            with (
                self.subTest(profissao=profissao),
                patch.object(modulo, "enviar_etapa4_reforco_escolar")
                as enviar_reforco,
                patch.object(modulo, "enviar_etapa4_financeiro")
                as enviar_financeiro,
                patch.object(
                    modulo,
                    "enviar_etapa6_cliente",
                    return_value=retorno_sender,
                ),
            ):
                resultado = modulo.resolve_etapa4(contexto)

            enviar_reforco.assert_not_called()
            enviar_financeiro.assert_not_called()
            self.assertEqual(resultado["profissao"], profissao)
            self.assertEqual(
                resultado["evento_transicao"],
                modulo.EVENTO_PROFISSAO_TITULAR_VALIDA,
            )
            self.assertEqual(
                resultado["id_etapa_resultante"],
                modulo.ETAPA_6_IDADE_ALUNO,
            )

    def test_etapa4_preserva_tratamento_financeiro_especifico(self):
        modulo = importlib.import_module(
            "workers.worker_flow.response_flow.etapas.resolver_etapa4"
        )
        retorno = _contexto_envio_tratamento(4, "pergunta_financeira")

        with (
            patch.object(modulo, "enviar_etapa4_reforco_escolar")
            as enviar_reforco,
            patch.object(
                modulo,
                "enviar_etapa4_financeiro",
                return_value=retorno,
            ) as enviar_financeiro,
        ):
            resultado = modulo.resolve_etapa4(
                _contexto_historico(4, "Qual é o valor?")
            )

        enviar_reforco.assert_not_called()
        enviar_financeiro.assert_called_once_with(
            "5571999999999",
            "phone-id",
        )
        self.assertEqual(resultado, retorno)
        self.assertNotIn("evento_transicao", resultado)


if __name__ == "__main__":
    unittest.main()
