from django.urls import path

from .views import (
    LoginMonitoramentoView, LogoutMonitoramentoView, contatos_csv,
    dados_conversas, dados_mensagens, dados_relatorio, painel,
)


app_name = 'monitoramento'

urlpatterns = [
    path('', painel, name='painel'),
    path('login/', LoginMonitoramentoView.as_view(), name='login'),
    path('sair/', LogoutMonitoramentoView.as_view(), name='sair'),
    path('dados/conversas/', dados_conversas, name='dados_conversas'),
    path('dados/conversas/<int:id_cliente>/', dados_mensagens, name='dados_mensagens'),
    path('dados/relatorio/', dados_relatorio, name='dados_relatorio'),
    path('contatos.csv', contatos_csv, name='contatos_csv'),
]
