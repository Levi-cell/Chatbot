from django.contrib import admin, messages
from django.db import connection, transaction
from django.utils.html import format_html
from django.urls import reverse
import logging

from core.cache.cache_unidade import recarregar_cache_unidades
from core.cache.cache_bloqueio_meta import remover_cliente_bloqueado_meta_cache
from core.integrations.whatsapp.ativando_numero import registrar_numero_whatsapp
from core.integrations.whatsapp.pywa_tools import desbloquear_usuario_meta
from core.logging_config import short_value
from core.repositories.cache_control import incrementar_versao_cache_unidades

from .models import (
    Cliente,
    ClienteBloqueadoMeta,
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
        self._registrar_alteracao_cache_unidades()

        if not change:
            try:
                status, resposta = registrar_numero_whatsapp(obj.phone_number_id)

                if status != 200:
                    logger.error(
                        "whatsapp_numero_registrar_falhou | acao=registrar_numero phone_number_id=%s status=%s resposta=%s",
                        short_value(obj.phone_number_id),
                        status,
                        resposta,
                    )
                    self.message_user(
                        request,
                        f"Erro ao registrar numero no WhatsApp: {resposta}",
                        level=messages.ERROR
                    )
                else:
                    logger.info(
                        "whatsapp_numero_registrado | acao=registrar_numero phone_number_id=%s status=%s",
                        short_value(obj.phone_number_id),
                        status,
                    )
                    self.message_user(
                        request,
                        "Numero registrado com sucesso no WhatsApp!",
                        level=messages.SUCCESS
                    )

            except Exception as e:
                logger.exception(
                    "whatsapp_numero_registrar_erro | acao=registrar_numero phone_number_id=%s",
                    short_value(obj.phone_number_id),
                )
                self.message_user(
                    request,
                    f"Erro inesperado ao registrar numero: {str(e)}",
                    level=messages.ERROR
                )

    def delete_model(self, request, obj):
        super().delete_model(request, obj)
        self._registrar_alteracao_cache_unidades()

    def delete_queryset(self, request, queryset):
        super().delete_queryset(request, queryset)
        self._registrar_alteracao_cache_unidades()

    def _registrar_alteracao_cache_unidades(self):
        with connection.cursor() as cursor:
            versao = incrementar_versao_cache_unidades(cursor)

        logger.info("cache_unidades_versao_incrementada | acao=incrementar_versao versao=%s", versao)
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
        "id_conversa",
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
        "id_conversa__id_conversa",
    )

    list_filter = (
        "status",
        "tipo_mensagem",
        "id_conversa",
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
        return super().get_queryset(request).select_related("id_conversa")

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
        logger.info(
            "admin_fila_reprocessada | acao=reprocessar usuario=%s total=%s",
            request.user,
            queryset.count(),
        )

    @admin.action(description="Marcar como erro")
    def marcar_erro(self, request, queryset):
        queryset.update(status="failed")
        logger.warning(
            "admin_fila_marcada_erro | acao=marcar_failed usuario=%s total=%s",
            request.user,
            queryset.count(),
        )

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
        "origem",
        "tipo_mensagem",
        "status_envio",
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
        "origem",
        "status_envio",
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


@admin.register(ClienteBloqueadoMeta)
class ClienteBloqueadoMetaAdmin(admin.ModelAdmin):

    list_display = (
        "id_bloqueio",
        "cliente_link",
        "wa_id_cliente",
        "id_unidade",
        "phone_id_unidade",
    )

    search_fields = (
        "wa_id_cliente",
        "phone_id_unidade",
        "id_cliente__waid_telefone",
        "id_cliente__nome",
        "id_unidade__nome",
    )

    list_filter = ("id_unidade",)
    ordering = ("wa_id_cliente", "id_unidade__nome")
    list_per_page = 50
    empty_value_display = "-"

    def has_add_permission(self, request):
        return False

    def get_readonly_fields(self, request, obj=None):
        return [field.name for field in self.model._meta.fields]

    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            "id_cliente",
            "id_unidade",
        )

    def delete_model(self, request, obj):
        wa_id_cliente = obj.wa_id_cliente
        phone_id_unidade = obj.phone_id_unidade

        super().delete_model(request, obj)

        transaction.on_commit(
            lambda: self._desbloquear_meta(
                request,
                wa_id_cliente,
                phone_id_unidade,
            )
        )

    def delete_queryset(self, request, queryset):
        bloqueios = list(
            queryset.values_list(
                "wa_id_cliente",
                "phone_id_unidade",
            )
        )

        super().delete_queryset(request, queryset)

        transaction.on_commit(
            lambda: self._desbloquear_varios_meta(request, bloqueios)
        )

    def cliente_link(self, obj):
        if not obj.id_cliente:
            return "-"

        try:
            url = reverse(
                "admin:webhook_cliente_change",
                args=[obj.id_cliente.id_cliente],
            )
            return format_html(
                '<a href="{}">{}</a>',
                url,
                obj.id_cliente.nome or obj.id_cliente.waid_telefone,
            )
        except Exception:
            return obj.id_cliente.nome or obj.id_cliente.waid_telefone

    cliente_link.short_description = "Cliente"

    def _desbloquear_varios_meta(self, request, bloqueios):
        for wa_id_cliente, phone_id_unidade in bloqueios:
            self._desbloquear_meta(request, wa_id_cliente, phone_id_unidade)

    def _desbloquear_meta(self, request, wa_id_cliente, phone_id_unidade):
        try:
            desbloquear_usuario_meta(wa_id_cliente, phone_id_unidade)
            remover_cliente_bloqueado_meta_cache(
                wa_id_cliente,
                phone_id_unidade,
            )

            logger.warning(
                "admin_cliente_desbloqueado_meta | acao=desbloquear_meta usuario=%s wa_id_cliente=%s phone_id_unidade=%s",
                request.user,
                short_value(wa_id_cliente),
                short_value(phone_id_unidade),
            )

            self.message_user(
                request,
                f"Cliente {wa_id_cliente} desbloqueado na unidade {phone_id_unidade}.",
                level=messages.SUCCESS,
            )

        except Exception as exc:
            logger.exception(
                "admin_desbloqueio_meta_falhou | acao=desbloquear_meta usuario=%s wa_id_cliente=%s phone_id_unidade=%s erro=%s",
                request.user,
                short_value(wa_id_cliente),
                short_value(phone_id_unidade),
                exc,
            )
            self.message_user(
                request,
                f"Registro removido, mas falhou ao desbloquear na Meta: {exc}",
                level=messages.ERROR,
            )
