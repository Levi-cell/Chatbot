from editar import *
p='tests/unit/test_fluxo_reserva_link.py'
s=read(p).replace('from webhook.models import Unidade','from webhook.models import Unidade, AtendimentoCustomizado').replace('unidade = Unidade(link_agendamento=link,','unidade = AtendimentoCustomizado(link_agendamento=link,')
write(p,s)
p='tests/unit/test_monitoramento_unidade.py'
s=read(p).replace(", link_agendamento='https://example.com'",'')
write(p,s)
p='tests/unit/test_suporte_por_idade.py'
s=read(p).replace('from webhook.admin import UnidadeAdmin','from webhook.admin import UnidadeAdmin, AtendimentoCustomizadoAdmin').replace('from webhook.models import Unidade','from webhook.models import Unidade, AtendimentoCustomizado')
s=s.replace("campo = Unidade._meta.get_field('idade_minima_suporte')","campo = AtendimentoCustomizado._meta.get_field('idade_minima_suporte')").replace('campo.clean(limite, Unidade())','campo.clean(limite, AtendimentoCustomizado())')
start=s.index('    def test_admin_exige_contato_ao_ativar_e_ao_remover_numero(self):')
end=s.index('    def test_matriz_',start)
s=s[:start]+'''    def test_admin_exige_contato_ao_ativar_e_ao_remover_numero(self):
        admin = AtendimentoCustomizadoAdmin(AtendimentoCustomizado, AdminSite())
        request = RequestFactory().get('/admin/')
        request.user = SimpleNamespace(has_perm=lambda *_: True)
        instance = AtendimentoCustomizado(id_customizacao=1, link_agendamento='https://example.com')
        form_class = admin.get_form(request, instance, change=True,
                                    fields=['idade_minima_suporte', 'numero_comercial'])
        for limite in LIMITES:
            for telefone in ('', '123', '(71) 99999-9999'):
                with self.subTest(limite=limite, telefone=telefone):
                    form = form_class(data={
                        'idade_minima_suporte': '' if limite is None else str(limite),
                        'numero_comercial': telefone,
                    }, instance=instance)
                    self.assertEqual(form.is_valid(), telefone == '(71) 99999-9999', form.errors)
                    if telefone != '(71) 99999-9999':
                        self.assertIn('numero_comercial', form.errors)
        for invalido in ('55', '100', 'True'):
            form = form_class(data={'idade_minima_suporte': invalido,
                                    'numero_comercial': '(71) 99999-9999'}, instance=instance)
            self.assertFalse(form.is_valid())

'''+s[end:]
write(p,s)
validate()
