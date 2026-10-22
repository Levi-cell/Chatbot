from core.integrations.whatsapp.numero_comercial import numero_comercial_whatsapp_valido
from core.validacoes.turno import ROTULOS_TURNO
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
    id_chat = models.ForeignKey('Chat', models.DO_NOTHING, db_column='id_chat')
    origem_fireads = models.CharField(max_length=20, null=True, blank=True, choices=[('google','Google Ads'),('meta','Meta Ads'),('organico_site','Orgânico Site'),('chat_fire','Chat Fire'),('organico','Orgânico')])
    contexto_fireads = models.JSONField(null=True, blank=True)
    contexto_coleta = models.JSONField(null=True, blank=True, editable=False)
    lead_no_dash = models.BooleanField(null=True, blank=True, default=None)

    turno = models.CharField(
        "turno de preferência", max_length=6, blank=True, null=True,
        choices=list(ROTULOS_TURNO.items()),
        help_text="Preferência informada no atendimento; não confirma dia ou horário.",
    )
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
    cnpj = models.CharField(unique=True, max_length=50)
    email_responsavel = models.CharField(unique=True, max_length=255)
    telefone = models.CharField(unique=True, max_length=20)
    waba_id = models.CharField(
        unique=True,
        max_length=100,
    )
    phone_number_id = models.CharField(unique=True, max_length=100)
    id_fuso = models.IntegerField(blank=True, null=True, editable=False)
    nome_fuso = models.TextField(blank=True, null=True, editable=False)
    fuso_verificado_em = models.DateTimeField(blank=True, null=True, editable=False)
    status_pagamento = models.BooleanField(
        "status pagamento / unidade ativa",
        blank=True, null=True, default=True,
        help_text=(
            "Sim: habilita o atendimento e os workers da unidade. Não ou desconhecido: "
            "suspende atendimento, follow-up, Funil, FireAds e consumo Meta, preservando "
            "o histórico e as pendências. Uma requisição externa já iniciada pode concluir."
        ),
    )
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

    @property
    def nome_agente(self):
        return self.atendimento_customizado.nome_agente

    @property
    def genero(self):
        return self.atendimento_customizado.genero

    @property
    def numero_comercial(self):
        return self.atendimento_customizado.numero_comercial

    @property
    def idade_minima_suporte(self):
        return self.atendimento_customizado.idade_minima_suporte

    @property
    def email_obrigatorio(self):
        return self.atendimento_customizado.email_obrigatorio

    @property
    def link_agendamento(self):
        return self.atendimento_customizado.link_agendamento

    @property
    def link_instagram(self):
        return self.atendimento_customizado.link_instagram

    @property
    def bpa_ativo(self):
        return self.atendimento_customizado.bpa_ativo

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
    snapshot = models.JSONField(blank=True, null=True)
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


class ConsumoMensalMeta(models.Model):
    """Espelho de leitura; o worker persiste pelo repositório e a migração é SQL."""

    id_registro = models.BigAutoField(primary_key=True)
    id_unidade = models.ForeignKey(Unidade, models.DO_NOTHING, db_column='id_unidade')
    mes_referencia = models.DateField()
    waba_id = models.CharField(max_length=100)
    phone_number_id = models.CharField(max_length=100)
    timezone_id = models.IntegerField()
    fuso_horario = models.TextField()
    data_hora_inicio = models.DateTimeField()
    data_hora_fim = models.DateTimeField()
    qtd_janela_gratuita = models.BigIntegerField()
    qtd_franquia_consumida = models.BigIntegerField()
    qtd_cobradas_meta = models.BigIntegerField()
    franquia_meta_mensal = models.IntegerField(default=1000)
    beneficio_esl_mensal = models.IntegerField(default=1000)
    tarifa_referencia_brl = models.DecimalField(max_digits=12, decimal_places=6)
    tarifa_vigencia = models.DateField()
    consultado_ate = models.DateTimeField()
    ultimo_sucesso_em = models.DateTimeField()
    status_apuracao = models.CharField(max_length=20, choices=[
        ('em_andamento', 'Em andamento'), ('em_conferencia', 'Em conferência'),
        ('consolidado', 'Consolidado'),
    ])
    data_proxima_consolidacao = models.DateField(null=True, blank=True)
    consolidado_em = models.DateTimeField(null=True, blank=True)
    ultima_decisao_consolidacao_em = models.DateTimeField(null=True, blank=True)
    criado_em = models.DateTimeField()
    atualizado_em = models.DateTimeField()

    class Meta:
        managed = False
        db_table = 'consumo_mensal_meta'
        constraints = [models.UniqueConstraint(fields=['id_unidade', 'mes_referencia'], name='uq_consumo_unidade_mes')]


class ConsumoMetaColeta(models.Model):
    """Agenda de conta/período; também existe quando a primeira consulta falha."""

    pk = models.CompositePrimaryKey('id_unidade', 'periodo')
    id_unidade = models.IntegerField()
    periodo = models.CharField(max_length=7)
    proxima_consulta_em = models.DateTimeField()
    ultima_tentativa_em = models.DateTimeField(null=True, blank=True)
    ultimo_erro = models.TextField(null=True, blank=True)
    falhas_consecutivas = models.IntegerField(default=0)

    class Meta:
        managed = False
        db_table = 'consumo_meta_coletas'


class AtendimentoCustomizado(models.Model):
    Genero = Unidade.Genero
    id_customizacao = models.AutoField(primary_key=True)
    id_unidade = models.OneToOneField(
        Unidade,
        models.CASCADE,
        db_column="id_unidade",
        related_name="atendimento_customizado",
    )
    nome_agente = models.CharField("nome do agente", max_length=100)
    genero = models.CharField(
        "gênero do agente",
        max_length=9,
        choices=Genero.choices,
    )
    numero_comercial = models.CharField(
        max_length=30,
        help_text="Contato comercial obrigatório para toda unidade.",
    )
    idade_minima_suporte = models.IntegerField(
        "encaminhar titular ao comercial a partir de",
        blank=True,
        null=True,
        default=None,
        choices=[(None, "Desativado")]
        + [(idade, f"{idade}+") for idade in IDADES_MINIMAS_SUPORTE],
        help_text=(
            "Na etapa de idade, encaminha somente o titular a partir do limite "
            "até 89 anos e encerra sem bloqueio; 90+ é universal. Não altera a regra de e-mail."
        ),
    )
    email_obrigatorio = models.BooleanField(
        "e-mail obrigatório",
        default=True,
        help_text=("Exige um e-mail válido, exceto do titular com 60 anos ou mais."),
    )
    link_agendamento = models.CharField(
        unique=True,
        max_length=400,
        blank=True,
        null=True,
        help_text="Vazio: coleta o turno e entrega ao comercial após a triagem.",
    )
    link_instagram = models.CharField(
        max_length=400,
        blank=True,
        null=True,
    )
    bpa_ativo = models.BooleanField(default=False)

    def clean(self):
        super().clean()
        self.link_agendamento = (self.link_agendamento or "").strip() or None
        if not numero_comercial_whatsapp_valido(self.numero_comercial):
            raise ValidationError(
                {"numero_comercial": "Informe um número comercial brasileiro válido."}
            )

    def __str__(self):
        return str(self.id_unidade)

    class Meta:
        managed = False
        db_table = "atendimento_customizado"
        verbose_name = "Atendimento customizado"
        verbose_name_plural = "Atendimentos customizados"


class IntegracaoFireAds(models.Model):
    id_integracao_fireads = models.AutoField(primary_key=True)
    id_unidade = models.OneToOneField(
        Unidade,
        models.CASCADE,
        db_column="id_unidade",
        related_name="integracao_fireads",
    )
    integracao_ativa = models.BooleanField(default=False)
    url_dashbord = models.URLField(max_length=1000)
    url_operation = models.URLField(
        max_length=1000,
        blank=True,
        null=True,
        help_text="Referência do editor. Nunca usada para requisições.",
    )
    aba_destino = models.CharField(
        "Aba de leads", max_length=200, default="LEADS GERAL - Feedback",
        help_text="Aba única para consultar formulários e acrescentar observações.",
    )
    fuso_formularios = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        help_text="Somente interpretação de datas sem offset. Preencher após confirmação na planilha; não altera o fuso externo.",
    )
    contrato_validado = models.BooleanField(
        default=False,
        help_text="Confirmar a aba de leads, os cabeçalhos e os valores de Canal e Para quem é antes de ativar.",
    )
    ativada_em = models.DateTimeField(null=True, blank=True, editable=False)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    def clean(self):
        super().clean()
        from core.integrations.fireads.cliente import validar_url
        from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

        try:
            validar_url(self.url_dashbord)
        except ValueError as exc:
            raise ValidationError({"url_dashbord": str(exc)})
        self.fuso_formularios = (self.fuso_formularios or "").strip() or None
        if self.fuso_formularios:
            try:
                ZoneInfo(self.fuso_formularios)
            except ZoneInfoNotFoundError:
                raise ValidationError({"fuso_formularios": "Fuso IANA inválido."})
        if self.integracao_ativa and not self.contrato_validado:
            raise ValidationError(
                {"contrato_validado": "Confira o contrato de leitura antes de ativar."}
            )
        self.aba_destino = self.aba_destino.strip()
        if not self.aba_destino:
            raise ValidationError({"aba_destino": "Informe a aba de leads."})

    def __str__(self):
        return str(self.id_unidade)

    class Meta:
        managed = False
        db_table = "integracao_fireads"
        verbose_name = "Integração FireAds"
        verbose_name_plural = "Integrações FireAds"


class Chat(models.Model):
    id_chat = models.BigAutoField(primary_key=True)
    id_cliente = models.ForeignKey(Cliente, models.CASCADE, db_column="id_cliente")
    id_unidade = models.ForeignKey(Unidade, models.CASCADE, db_column="id_unidade")
    criado_em = models.DateTimeField()

    def __str__(self):
        return f"{self.id_cliente} / {self.id_unidade}"

    class Meta:
        managed = False
        db_table = "chat"
        constraints = [
            models.UniqueConstraint(
                fields=["id_cliente", "id_unidade"], name="uq_chat_cliente_unidade"
            )
        ]


class ConsultaFireAds(models.Model):
    id_consulta = models.BigAutoField(primary_key=True)
    id_conversa = models.OneToOneField(Conversa, models.CASCADE, db_column="id_conversa")
    id_unidade = models.ForeignKey(Unidade, models.CASCADE, db_column="id_unidade")
    id_integracao_fireads = models.ForeignKey(
        IntegracaoFireAds, models.PROTECT, db_column="id_integracao_fireads"
    )
    status = models.CharField(max_length=20)
    consulta_concluida = models.BooleanField(default=False)
    resultado = models.CharField(max_length=30)
    entrada = models.JSONField()
    dados = models.JSONField(null=True, blank=True)
    aplicacao = models.JSONField(null=True, blank=True)
    solicitado_em = models.DateTimeField()
    prazo_final = models.DateTimeField()
    processing_started_at = models.DateTimeField(null=True, blank=True)
    reserva_ate = models.DateTimeField(null=True, blank=True)
    consultado_em = models.DateTimeField(null=True, blank=True)
    aplicado_em = models.DateTimeField(null=True, blank=True)
    atualizado_em = models.DateTimeField()
    tentativas = models.IntegerField(default=0)
    versao_reserva = models.BigIntegerField(default=0)
    ultimo_erro = models.TextField(null=True, blank=True)

    def __str__(self):
        return f"Consulta {self.pk} / conversa {self.id_conversa_id} / {self.status}"

    class Meta:
        managed = False
        db_table = "consulta_fireads"
        verbose_name_plural = "Consultas FireAds"


class EnvioDash(models.Model):
    id_envio_dash = models.BigAutoField(primary_key=True)
    id_conversa = models.OneToOneField(
        Conversa, models.CASCADE, db_column="id_conversa"
    )
    id_integracao_fireads = models.ForeignKey(
        IntegracaoFireAds, models.PROTECT, db_column="id_integracao_fireads"
    )
    id_unidade = models.ForeignKey(Unidade, models.CASCADE, db_column="id_unidade")
    status = models.CharField(max_length=20, default="pending")
    attempt_count = models.IntegerField(default=0)
    next_attempt_at = models.DateTimeField()
    processing_started_at = models.DateTimeField(null=True, blank=True)
    enviado_em = models.DateTimeField(null=True, blank=True)
    ultimo_erro = models.TextField(null=True, blank=True)
    recibo = models.JSONField(null=True, blank=True)
    snapshot = models.JSONField()
    criado_em = models.DateTimeField()
    atualizado_em = models.DateTimeField()

    class Meta:
        managed = False
        db_table = "envios_dash"
        verbose_name_plural = "Envios ao dashboard"
