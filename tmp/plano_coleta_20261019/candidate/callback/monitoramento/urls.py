from django.urls import path
from .consumo_views import dados_consumo, consumo_pdf

from .views import (
    LoginMonitoramentoView, LogoutMonitoramentoView, contatos_csv,
    dados_conversas, dados_mensagens, dados_relatorio, painel,
    dados_faixa_etaria,
)


app_name = 'monitoramento'

urlpatterns = [
    path('', painel, name='painel'),
    path('login/', LoginMonitoramentoView.as_view(), name='login'),
    path('sair/', LogoutMonitoramentoView.as_view(), name='sair'),
    path('dados/conversas/', dados_conversas, name='dados_conversas'),
    path('dados/conversas/<int:id_cliente>/', dados_mensagens, name='dados_mensagens'),
    path('dados/relatorio/', dados_relatorio, name='dados_relatorio'),
    path('dados/relatorio/faixa-etaria/', dados_faixa_etaria, name='dados_faixa_etaria'),
    path('contatos.csv', contatos_csv, name='contatos_csv'),
    path('dados/consumo/', dados_consumo, name='dados_consumo'),
    path('consumo.pdf', consumo_pdf, name='consumo_pdf'),
]
