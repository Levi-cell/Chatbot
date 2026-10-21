from editar import *
import re

moved=['nome_agente','genero','numero_comercial','idade_minima_suporte','email_obrigatorio','link_agendamento','link_instagram','bpa_ativo']
p='callback/webhook/models.py'
s=read(p)
start=s.index('class Unidade(models.Model):')
end=s.index('\n\nclass IntegracaoFunilUnidade',start)
unit=s[start:end]
custom=[]
for field in moved:
    pattern=rf'^    {field} = .*?(?=^    \w|\Z)'
    match=re.search(pattern,unit,re.M|re.S)
    assert match,field
    custom.append(match.group(0).rstrip())
    unit=unit[:match.start()]+unit[match.end():]
unit=unit.replace('''        self.link_agendamento = (self.link_agendamento or "").strip() or None
        if self.link_agendamento is None and not numero_comercial_whatsapp_valido(self.numero_comercial):
            raise ValidationError({"numero_comercial": "Informe um número comercial válido para atender sem link."})
''','')
# Read-only compatibility for callers that show unit properties, not ORM columns.
pos=unit.index('    def clean(self):')
properties=''.join(f'    @property\n    def {f}(self):\n        return self.atendimento_customizado.{f}\n\n' for f in moved)
unit=unit[:pos]+properties+unit[pos:]
s=s[:start]+unit+s[end:]
addition='''

class AtendimentoCustomizado(models.Model):
    Genero = Unidade.Genero
    id_customizacao = models.AutoField(primary_key=True)
    id_unidade = models.OneToOneField(Unidade, models.CASCADE, db_column='id_unidade', related_name='atendimento_customizado')
'''+ '\n'.join(custom)+'''

    def clean(self):
        super().clean()
        self.link_agendamento = (self.link_agendamento or '').strip() or None
        if not numero_comercial_whatsapp_valido(self.numero_comercial):
            raise ValidationError({'numero_comercial': 'Informe um número comercial brasileiro válido.'})

    def __str__(self):
        return str(self.id_unidade)

    class Meta:
        managed = False
        db_table = 'atendimento_customizado'
        verbose_name = 'Atendimento customizado'
        verbose_name_plural = 'Atendimentos customizados'


class IntegracaoFireAds(models.Model):
    id_integracao_fireads = models.AutoField(primary_key=True)
    id_unidade = models.OneToOneField(Unidade, models.CASCADE, db_column='id_unidade', related_name='integracao_fireads')
    integracao_ativa = models.BooleanField(default=False)
    url_dashboard = models.URLField(max_length=1000)
    url_operation = models.URLField(max_length=1000, blank=True, null=True, help_text='Referência do editor. Nunca usada para requisições.')
    aba_google = models.CharField(max_length=200, default='Leads Google Ads (NÃO EDITAR)')
    aba_meta = models.CharField(max_length=200, default='[FIRE] Leads Ads Geral - 7.2')
    aba_destino = models.CharField(max_length=200, default='LEADS GERAL - Feedback')
    fuso_formularios = models.CharField(max_length=100, null=True, blank=True, help_text='Somente interpretação de datas sem offset. Preencher após confirmação na planilha; não altera o fuso externo.')
    contrato_validado = models.BooleanField(default=False, help_text='Confirmar nomes de abas, campos e valores recebidos do formulário atualizado antes de ativar.')
    ativada_em = models.DateTimeField(null=True, blank=True, editable=False)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    def clean(self):
        super().clean()
        from core.integrations.fireads.cliente import validar_url
        from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
        try:
            validar_url(self.url_dashboard)
        except ValueError as exc:
            raise ValidationError({'url_dashboard': str(exc)})
        self.fuso_formularios = (self.fuso_formularios or '').strip() or None
        if self.fuso_formularios:
            try:
                ZoneInfo(self.fuso_formularios)
            except ZoneInfoNotFoundError:
                raise ValidationError({'fuso_formularios': 'Fuso IANA inválido.'})
        if self.integracao_ativa and not self.contrato_validado:
            raise ValidationError({'contrato_validado': 'Confira o contrato de leitura antes de ativar.'})
        abas = [self.aba_google, self.aba_meta, self.aba_destino]
        if any(not a.strip() for a in abas) or len(set(abas)) != 3:
            raise ValidationError('Informe três abas distintas e não vazias.')

    def __str__(self):
        return str(self.id_unidade)

    class Meta:
        managed = False
        db_table = 'integracao_fireads'
        verbose_name = 'Integração FireAds'
        verbose_name_plural = 'Integrações FireAds'


class Chat(models.Model):
    id_chat = models.BigAutoField(primary_key=True)
    id_cliente = models.ForeignKey(Cliente, models.CASCADE, db_column='id_cliente')
    id_unidade = models.ForeignKey(Unidade, models.CASCADE, db_column='id_unidade')
    criado_em = models.DateTimeField()

    def __str__(self):
        return f'{self.id_cliente} / {self.id_unidade}'

    class Meta:
        managed = False
        db_table = 'chat'
        constraints = [models.UniqueConstraint(fields=['id_cliente','id_unidade'], name='uq_chat_cliente_unidade')]


class ConsultaFireAds(models.Model):
    id_consulta = models.BigAutoField(primary_key=True)
    id_chat = models.OneToOneField(Chat, models.CASCADE, db_column='id_chat')
    id_unidade = models.ForeignKey(Unidade, models.CASCADE, db_column='id_unidade')
    id_integracao_fireads = models.ForeignKey(IntegracaoFireAds, models.PROTECT, db_column='id_integracao_fireads')
    id_conversa_referencia = models.ForeignKey(Conversa, models.CASCADE, db_column='id_conversa_referencia')
    concluida = models.BooleanField(default=False)
    resultado = models.CharField(max_length=30)
    dados = models.JSONField(null=True, blank=True)
    consultado_em = models.DateTimeField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = 'consulta_fireads'
        verbose_name_plural = 'Consultas FireAds'


class EnvioDash(models.Model):
    id_envio_dash = models.BigAutoField(primary_key=True)
    id_conversa = models.OneToOneField(Conversa, models.CASCADE, db_column='id_conversa')
    id_integracao_fireads = models.ForeignKey(IntegracaoFireAds, models.PROTECT, db_column='id_integracao_fireads')
    id_unidade = models.ForeignKey(Unidade, models.CASCADE, db_column='id_unidade')
    status = models.CharField(max_length=20, default='pending')
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
        db_table = 'envios_dash'
        verbose_name_plural = 'Envios ao dashboard'
'''
s+=addition
s=s.replace('class Conversa(models.Model):','''class Conversa(models.Model):
    id_chat = models.ForeignKey('Chat', models.DO_NOTHING, db_column='id_chat')
    origem_fireads = models.CharField(max_length=10, null=True, blank=True, choices=[('google','Google Ads'),('meta','Meta Ads'),('organico','Orgânico')])
    contexto_fireads = models.JSONField(null=True, blank=True)
    lead_no_dash = models.BooleanField(null=True, blank=True, default=None)
''')
write(p,s)
p='callback/webhook/admin.py'
s=read(p)
s='from .models import AtendimentoCustomizado, IntegracaoFireAds, Chat, ConsultaFireAds, EnvioDash\n'+s
inline='''class AtendimentoCustomizadoInline(admin.StackedInline):
    model = AtendimentoCustomizado
    extra = 1
    min_num = 1
    max_num = 1
    can_delete = False
    validate_min = True


'''
s=s.replace('@admin.register(Unidade)',inline+'@admin.register(Unidade)',1)
s=s.replace('class UnidadeAdmin(admin.ModelAdmin):','class UnidadeAdmin(admin.ModelAdmin):\n    inlines = (AtendimentoCustomizadoInline,)')
start=s.index('    search_fields = (',s.index('class UnidadeAdmin'))
end=s.index('    list_per_page',start)
section=s[start:end]
for f in moved:section=section.replace(f'"{f}"',f'"atendimento_customizado__{f}"')
section=section.replace('list_select_related = ("id_usuario_monitoramento",)','list_select_related = ("id_usuario_monitoramento", "atendimento_customizado")')
s=s[:start]+section+s[end:]
start=s.index('                if (\n                    not numero_comercial_whatsapp_valido')
end=s.index('                if change or self.errors:',start)
s=s[:start]+s[end:]
s+='''

@admin.register(AtendimentoCustomizado)
class AtendimentoCustomizadoAdmin(admin.ModelAdmin):
    list_display = ('id_customizacao', 'id_unidade', 'nome_agente', 'email_obrigatorio', 'link_agendamento')
    list_select_related = ('id_unidade',)
    search_fields = ('id_unidade__nome_unidade', 'nome_agente')

    def get_readonly_fields(self, request, obj=None):
        return ('id_unidade',) if obj else ()

    def has_add_permission(self, request):
        return False  # A criação é feita junto da unidade, pelo inline obrigatório.

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(IntegracaoFireAds)
class IntegracaoFireAdsAdmin(admin.ModelAdmin):
    list_display = ('id_integracao_fireads', 'id_unidade', 'integracao_ativa', 'contrato_validado', 'ativada_em')
    list_select_related = ('id_unidade',)
    search_fields = ('id_unidade__nome_unidade',)
    readonly_fields = ('ativada_em', 'criado_em', 'atualizado_em')

    def get_readonly_fields(self, request, obj=None):
        return self.readonly_fields + (('id_unidade',) if obj else ())

    def has_delete_permission(self, request, obj=None):
        return False  # Desativar preserva vínculos e snapshots históricos.


for modelo in (Chat, ConsultaFireAds, EnvioDash):
    admin.site.register(modelo, SomenteLeituraAdmin)
'''
# The base class name is discovered rather than invented.
base=re.search(r'class (\w+)\(admin.ModelAdmin\):',s).group(1)
s=s.replace('admin.site.register(modelo, SomenteLeituraAdmin)',f'admin.site.register(modelo, {base})')
write(p,s)

# SQL consumers keep identical return contracts through a joined read view.
paths=[p.relative_to(DEST).as_posix() for p in (DEST/'core/repositories').rglob('*.py') if any(f in p.read_text(encoding='utf-8-sig') for f in moved)]
for p in paths:
    s=read(p)
    if 'chatbot.unidade' in s:
        s=re.sub(r'\b(FROM|JOIN) chatbot\.unidade\b',r'\1 chatbot.unidade_atendimento',s)
        write(p,s)
for p in ['utilitarios/reports_functions/total.py','utilitarios/reports_functions/weekly.py']:
    fresh(p)
    s=re.sub(r'\b(FROM|JOIN) chatbot\.unidade\b',r'\1 chatbot.unidade_atendimento',read(p))
    write(p,s)
validate()
print('Models, Admin e leituras preparados.')
