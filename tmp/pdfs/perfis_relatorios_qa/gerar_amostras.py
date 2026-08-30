"""Amostras sintéticas locais para inspeção do renderer, sem banco ou API."""
import copy
from datetime import datetime, timedelta, timezone
from pathlib import Path

from tests.unit.test_gerar_monitoramento_unidades import GerarMonitoramentoUnidadesTests
from utilitarios.reports_functions import weekly

saida = Path(__file__).resolve().parent
fim = datetime(2026, 8, 30, 19, tzinfo=timezone.utc)
inicio = fim - timedelta(days=7)
unidades = [{"id_unidade": 1, "nome_unidade": "Supera Santo Antônio de Jesus",
             "nome_agente": "Suh", "suporte_idoso": True, "bpa_ativo": True}]
mensagens = []
funil = []
for numero, (dependente, idade) in enumerate([
    (True, 4), (True, 7), (True, 17), (True, 18), (True, 35), (True, 59),
    (True, 60), (True, 83), (False, 18), (False, 40), (False, 59),
    (False, 60), (False, 74), (None, None),
], 1):
    linha = GerarMonitoramentoUnidadesTests._mensagem(
        id_unidade=1, id_cliente=numero, id_conversa=100 + numero,
        id_mensagem=numero, quando=inicio + timedelta(hours=numero),
        nome=f"Lead fictício {numero:02}", profissao_cliente="Professora",
        status_dependente=dependente, idade_titular=idade if dependente is False else 40,
        idade_dependente=idade if dependente else None,
    )
    mensagens.append(linha)
    if numero % 2 == 0:
        funil.append(linha)
pesquisas = [
    {"id_unidade": 1, "id_cliente": n, "id_conversa": n + 100,
     "nome_cliente": f"Lead fictício {n:02}", "profissao_cliente": "Professora",
     "nota": nota, "comentario": texto, "criado_em": fim - timedelta(hours=3)}
    for n, nota, texto in [(1, 5, "Gostei da clareza das orientações e da atenção ao atendimento do meu dependente."),
                           (10, 4, "Atendimento acolhedor. Gostaria de saber mais sobre os horários disponíveis.")]
]
snapshot = weekly.montar_snapshot(unidades, mensagens, funil, pesquisas, inicio, fim)
for tipo in ("semanal", "total"):
    periodo = copy.deepcopy(snapshot["periodo"])
    periodo["tipo"] = tipo
    if tipo == "total":
        periodo["inicio"] = datetime(2026, 6, 1, tzinfo=timezone.utc).isoformat()
        periodo["rotulo"] = "01/06/2026 00:00 até 30/08/2026 16:00"
        periodo["dias"] = 90
    weekly.renderizar_pdf(snapshot["unidades"][0], periodo, saida / f"{tipo}.pdf")

vazio = weekly.montar_snapshot([dict(unidades[0], suporte_idoso=False, bpa_ativo=False)], [], [], [], inicio, fim)
weekly.renderizar_pdf(vazio["unidades"][0], vazio["periodo"], saida / "vazio.pdf")

# Comentário e relação maiores verificam quebra de página sem cortar conteúdo.
extenso = copy.deepcopy(snapshot["unidades"][0])
extenso["pesquisas"][0]["comentario"] = "Comentário fictício para testar a continuidade entre páginas. " * 85
extenso["conversas"] = extenso["conversas"] * 3
weekly.renderizar_pdf(extenso, snapshot["periodo"], saida / "extenso.pdf")
print("PDFs sintéticos gerados: semanal, total, vazio, extenso.")
