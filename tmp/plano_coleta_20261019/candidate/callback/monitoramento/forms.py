"""Formulario de entrada com a autenticacao nativa do Django."""

from django import forms
from django.contrib.auth.forms import AuthenticationForm, UsernameField
from django.core.exceptions import PermissionDenied, ValidationError

from .monitoramento_guard import exigir_acesso_usuario_monitoramento


class LoginMonitoramentoForm(AuthenticationForm):
    username = UsernameField(
        label='Username',
        error_messages={
            'required': 'Informe seu username.',
            'max_length': 'O username deve ter no máximo 150 caracteres.',
        },
        widget=forms.TextInput(attrs={
            'autocomplete': 'username',
            'autocapitalize': 'none',
            'autocorrect': 'off',
            'spellcheck': 'false',
            'placeholder': 'Seu username',
        }),
    )
    password = forms.CharField(
        label='Senha',
        strip=False,
        error_messages={'required': 'Informe sua senha.'},
        widget=forms.PasswordInput(attrs={
            'autocomplete': 'current-password',
            'placeholder': 'Sua senha',
        }),
    )
    error_messages = {
        'invalid_login': 'Username ou senha incorretos. Confira os dados e tente novamente.',
        'inactive': 'Não foi possível acessar esta conta. Fale com o responsável pelo seu acesso.',
    }

    def confirm_login_allowed(self, user):
        super().confirm_login_allowed(user)
        try:
            exigir_acesso_usuario_monitoramento(user)
        except PermissionDenied as erro:
            raise ValidationError(
                'Esta conta não possui acesso ao monitoramento. Fale com o responsável pelo seu acesso.',
                code='sem_acesso_monitoramento',
            ) from erro
