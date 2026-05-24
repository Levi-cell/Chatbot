from django.contrib import admin, messages
from django.db import transaction
from django.utils.html import format_html
from django.urls import reverse
import logging

from core.cache.cache_unidade import recarregar_cache_unidades
from core.integrations.whatsapp.ativando_numero import registrar_numero_whatsapp

from .models import (
    Cliente,
    Conversa,
    Etapa,
    FilaMensagens,
    HistoricoMensagens,
    Unidade,
)

logger = logging.getLogger(__name__)


@admin.register(Unidade)
class UnidadeAdmin(admin.ModelAdmin):

    list_display = (
        "id_unidade",
        "nome",
        "cnpj",
        "telefone",
        "email_responsavel",
        "link_agendamento_clickable",
        "status_ativo",
    )

    search_fields = (
        "nome",
        "cnpj",
        "telefone",
        "email_responsavel",
        "link_agendamento",
    )

    list_filter = ("status_ativo",)
    ordering = ("nome",)

    list_per_page = 50
    empty_value_display = "-"

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        transaction.on_commit(recarregar_cache_unidades)

        if not change:
            try:
                status, resposta = registrar_numero_whatsapp(obj.phone_number_id)

                if status != 200:
                    logger.error(f"Erro ao registrar numero {obj.phone_number_id}: {resposta}")
                    self.message_user(
                        request,
                        f"Erro ao registrar numero no WhatsApp: {resposta}",
                        level=messages.ERROR
                    )
                else:
                    logger.info(f"Numero {obj.phone_number_id} registrado com sucesso")
                    self.message_user(
                        request,
                        "Numero registrado com sucesso no WhatsApp!",
                        level=messages.SUCCESS
                    )

            except Exception as e:
                logger.exception(f"Erro inesperado ao registrar numero {obj.phone_number_id}")
                self.message_user(
                    request,
                    f"Erro inesperado ao registrar numero: {str(e)}",
                    level=messages.ERROR
                )

    def delete_model(self, request, obj):
        super().delete_model(request, obj)
        transaction.on_commit(recarregar_cache_unidades)

    def delete_queryset(self, request, queryset):
        super().delete_queryset(request, queryset)
        transaction.on_commit(recarregar_cache_unidades)

    def link_agendamento_clickable(self, obj):
        if obj.link_agendamento:
            return format_html(
                '<a href="{}" target="_blank">Abrir</a>',
                obj.link_agendamento
            )
        return "-"

    link_agendamento_clickable.short_description = "Agendamento"


@admin.register(Cliente)
class ClienteAdmin(admin.ModelAdmin):

    list_display = (
        "id_cliente",
        "nome",
        "waid_telefone",
        "email",
    )

    search_fields = (
        "nome",
        "waid_telefone",
        "email",
    )

    ordering = ("nome",)
    list_per_page = 50
    empty_value_display = "-"


@admin.register(Etapa)
class EtapaAdmin(admin.ModelAdmin):

    list_display = (
        "id_etapa",
        "nome_etapa",
    )

    search_fields = ("nome_etapa",)
    ordering = ("nome_etapa",)

    list_per_page = 50
    empty_value_display = "-"


@admin.register(Conversa)
class ConversaAdmin(admin.ModelAdmin):

    list_display = (
        "id_conversa",
        "cliente_link",
        "id_unidade",
        "id_etapa_atual",
        "status_ativa",
        "last_message_from",
        "followup_stage",
        "lead_no_funil",
        "processing",
        "last_interaction_at",
        "iniciou_em",
    )

    search_fields = (
        "id_cliente__waid_telefone",
        "id_cliente__nome",
    )

    list_filter = (
        "status_ativa",
        "lead_no_funil",
        "last_message_from",
        "followup_stage",
        "processing",
        "id_unidade",
        "id_etapa_atual",
    )

    ordering = ("-iniciou_em",)

    date_hierarchy = "iniciou_em"
    list_per_page = 50

    readonly_fields = (
        "lock_version",
        "processing_started_at",
        "iniciou_em",
        "finalizou_em",
    )

    empty_value_display = "-"

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related(
            "id_cliente",
            "id_unidade",
            "id_etapa_atual"
        )

    def cliente_link(self, obj):
        if not obj.id_cliente:
            return "-"

        try:
            url = reverse(
                "admin:webhook_cliente_change",
                args=[obj.id_cliente.id_cliente]
            )
            return format_html(
                '<a href="{}">{}</a>',
                url,
                obj.id_cliente.nome or obj.id_cliente.waid_telefone
            )
        except Exception:
            return obj.id_cliente.nome or obj.id_cliente.waid_telefone

    cliente_link.short_description = "Cliente"


@admin.register(FilaMensagens)
class FilaMensagensAdmin(admin.ModelAdmin):

    list_display = (
        "id_mensagem",
        "status_colorido",
        "tipo_mensagem",
        "cliente_telefone",
        "id_hash_msg",
        "received_data_hora",
        "retry_count",
        "next_attempt_at",
        "erro_resumido",
    )

    search_fields = (
        "cliente_telefone",
        "id_hash_msg",
    )

    list_filter = (
        "status",
        "tipo_mensagem",
    )

    ordering = ("-received_data_hora",)
    date_hierarchy = "received_data_hora"

    list_per_page = 50
    empty_value_display = "-"

    readonly_fields = ("last_error",)

    actions = ["reprocessar", "marcar_erro"]

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def get_queryset(self, request):
        return super().get_queryset(request)

    @admin.action(description="Reprocessar mensagens selecionadas")
    def reprocessar(self, request, queryset):
        if queryset.count() > 100:
            self.message_user(
                request,
                "Limite de 100 mensagens por vez.",
                level=messages.ERROR
            )
            return

        queryset.update(status="pending", retry_count=0, last_error=None)
        logger.info(f"{request.user} reprocessou {queryset.count()} mensagens")

    @admin.action(description="Marcar como erro")
    def marcar_erro(self, request, queryset):
        queryset.update(status="failed")
        logger.warning(f"{request.user} marcou {queryset.count()} mensagens como erro")

    def status_colorido(self, obj):
        cores = {
            "sent": "green",
            "failed": "red",
            "pending": "#555",
            "processing": "orange",
        }
        cor = cores.get(obj.status, "#000")
        return format_html('<b style="color:{};">{}</b>', cor, obj.status)

    status_colorido.short_description = "Status"

    def erro_resumido(self, obj):
        if not obj.last_error:
            return "-"

        texto = obj.last_error[:60]

        return format_html(
            '<span title="{}">{}</span>',
            obj.last_error,
            texto + ("..." if len(obj.last_error) > 60 else "")
        )

    erro_resumido.short_description = "Erro"


@admin.register(HistoricoMensagens)
class HistoricoMensagensAdmin(admin.ModelAdmin):

    list_display = (
        "id_mensagem",
        "tipo_mensagem",
        "id_conversa",
        "id_etapa",
        "cliente_telefone",
        "received_data_hora",
    )

    search_fields = (
        "cliente_telefone",
        "id_hash_msg",
    )

    list_filter = (
        "id_etapa",
        "tipo_mensagem",
    )

    ordering = ("-received_data_hora",)

    date_hierarchy = "received_data_hora"
    list_per_page = 50

    empty_value_display = "-"

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related(
            "id_conversa",
            "id_etapa",
        )

    def get_readonly_fields(self, request, obj=None):
        return [field.name for field in self.model._meta.fields]