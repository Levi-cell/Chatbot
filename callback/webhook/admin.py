import logging

from django.contrib import admin, messages
from django.db import connection, transaction
from django.http import HttpResponseRedirect
from django.urls import reverse
from django.utils.html import format_html

from core.cache.cache_unidade import recarregar_cache_unidades
from core.integrations.whatsapp.tools.ativando_numero import registrar_numero_whatsapp
from core.integrations.whatsapp.block import desbloquear_usuario_meta
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


class SomenteVisualizacaoAdminMixin:
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def get_readonly_fields(self, request, obj=None):
        return [field.name for field in self.model._meta.fields]


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
                        level=messages.ERROR,
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
                        level=messages.SUCCESS,
                    )

            except Exception as e:
                logger.exception(
                    "whatsapp_numero_registrar_erro | acao=registrar_numero phone_number_id=%s",
                    short_value(obj.phone_number_id),
                )
                self.message_user(
                    request,
                    f"Erro inesperado ao registrar numero: {str(e)}",
                    level=messages.ERROR,
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

        logger.info(
            "cache_unidades_versao_incrementada | acao=incrementar_versao versao=%s",
            versao,
        )
        transaction.on_commit(recarregar_cache_unidades)

    def link_agendamento_clickable(self, obj):
        if obj.link_agendamento:
            return format_html(
                '<a href="{}" target="_blank">Abrir</a>',
                obj.link_agendamento,
            )
        return "-"

    link_agendamento_clickable.short_description = "Agendamento"


@admin.register(Cliente)
class ClienteAdmin(SomenteVisualizacaoAdminMixin, admin.ModelAdmin):

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
class EtapaAdmin(SomenteVisualizacaoAdminMixin, admin.ModelAdmin):

    list_display = (
        "id_etapa",
        "nome_etapa",
    )

    search_fields = ("nome_etapa",)
    ordering = ("nome_etapa",)

    list_per_page = 50
    empty_value_display = "-"


@admin.register(Conversa)
class ConversaAdmin(SomenteVisualizacaoAdminMixin, admin.ModelAdmin):

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
    empty_value_display = "-"

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related(
            "id_cliente",
            "id_unidade",
            "id_etapa_atual",
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


@admin.register(FilaMensagens)
class FilaMensagensAdmin(SomenteVisualizacaoAdminMixin, admin.ModelAdmin):

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

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("id_conversa")

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
            texto + ("..." if len(obj.last_error) > 60 else ""),
        )

    erro_resumido.short_description = "Erro"


@admin.register(HistoricoMensagens)
class HistoricoMensagensAdmin(SomenteVisualizacaoAdminMixin, admin.ModelAdmin):

    list_display = (
        "id_mensagem",
        "quem_enviou",
        "tipo_mensagem",
        "status_envio",
        "id_conversa",
        "id_etapa",
        "id_mensagem_fila",
        "id_hash_cliente_origem",
        "cliente_telefone",
        "received_data_hora",
    )

    search_fields = (
        "cliente_telefone",
        "id_hash_msg",
        "id_hash_cliente_origem",
        "id_mensagem_fila__id_mensagem",
    )

    list_filter = (
        "quem_enviou",
        "status_envio",
        "id_etapa",
        "tipo_mensagem",
    )

    ordering = ("-received_data_hora",)

    date_hierarchy = "received_data_hora"
    list_per_page = 50

    empty_value_display = "-"

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related(
            "id_conversa",
            "id_etapa",
            "id_mensagem_fila",
        )


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

    def get_actions(self, request):
        actions = super().get_actions(request)
        actions.pop("delete_selected", None)
        return actions

    def get_readonly_fields(self, request, obj=None):
        return [field.name for field in self.model._meta.fields]

    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            "id_cliente",
            "id_unidade",
        )

    def delete_view(self, request, object_id, extra_context=None):
        if request.method == "POST":
            obj = self.get_object(request, object_id)

            if obj and not self._desbloquear_meta_antes_de_excluir(request, obj):
                return HttpResponseRedirect(
                    reverse(
                        "admin:webhook_clientebloqueadometa_change",
                        args=[object_id],
                    )
                )

        return super().delete_view(request, object_id, extra_context)

    def delete_model(self, request, obj):
        logger.warning(
            "admin_bloqueio_meta_excluido | acao=excluir_registro usuario=%s wa_id_cliente=%s phone_id_unidade=%s",
            request.user,
            short_value(obj.wa_id_cliente),
            short_value(obj.phone_id_unidade),
        )
        super().delete_model(request, obj)

    def delete_queryset(self, request, queryset):
        logger.warning(
            "admin_bloqueio_meta_exclusao_massa_bloqueada | acao=manter_registros usuario=%s total=%s",
            request.user,
            queryset.count(),
        )
        self.message_user(
            request,
            "Exclusao em massa desativada. Desbloqueie um cliente por unidade de cada vez.",
            level=messages.ERROR,
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

    def _desbloquear_meta_antes_de_excluir(self, request, obj):
        try:
            desbloquear_usuario_meta(obj.wa_id_cliente, obj.phone_id_unidade)

            logger.warning(
                "admin_cliente_desbloqueado_meta | acao=desbloquear_meta_antes_excluir usuario=%s wa_id_cliente=%s phone_id_unidade=%s",
                request.user,
                short_value(obj.wa_id_cliente),
                short_value(obj.phone_id_unidade),
            )

            self.message_user(
                request,
                f"Cliente {obj.wa_id_cliente} desbloqueado na Meta. Registro removido do banco.",
                level=messages.SUCCESS,
            )
            return True

        except Exception as exc:
            logger.exception(
                "admin_desbloqueio_meta_falhou | acao=manter_registro usuario=%s wa_id_cliente=%s phone_id_unidade=%s erro=%s",
                request.user,
                short_value(obj.wa_id_cliente),
                short_value(obj.phone_id_unidade),
                exc,
            )
            self.message_user(
                request,
                f"Falha ao desbloquear na Meta. Registro mantido no banco: {exc}",
                level=messages.ERROR,
            )
            return False
