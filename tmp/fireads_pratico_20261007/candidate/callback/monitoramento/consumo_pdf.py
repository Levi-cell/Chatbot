"""PDFs de consumo em memória, sem arquivos compartilhados ou acesso à Meta."""

from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from xml.sax.saxutils import escape

import reportlab
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from svglib.svglib import svg2rlg

VERDE = colors.HexColor("#274a2c")
LINHA = colors.HexColor("#dde2d8")
FONTE_DIR = Path(reportlab.__file__).parent / "fonts"
pdfmetrics.registerFont(TTFont("ConsumoSans", str(FONTE_DIR / "Vera.ttf")))
pdfmetrics.registerFont(TTFont("ConsumoSansBold", str(FONTE_DIR / "VeraBd.ttf")))


def _numero(valor):
    return f"{int(valor):,}".replace(",", ".")


def gerar_pdf_consumo(nome_unidade, registros, *, historico=False, agora=None):
    """Usa a mesma apresentação do painel e uma leitura consistente dos meses."""
    if not registros:
        raise ValueError("Não há dados disponíveis para o relatório.")
    destino = BytesIO()
    pagina = landscape(A4) if historico else A4
    documento = SimpleDocTemplate(
        destino, pagesize=pagina, leftMargin=18 * mm, rightMargin=18 * mm,
        topMargin=16 * mm, bottomMargin=19 * mm,
        title="Consumo de mensagens - ESL Tech", author="ESL Tech",
    )
    estilos = {
        "normal": ParagraphStyle("normal", fontName="ConsumoSans", fontSize=9, leading=14, textColor=VERDE),
        "pequeno": ParagraphStyle("pequeno", fontName="ConsumoSans", fontSize=8, leading=12, textColor=colors.HexColor("#5b695b")),
        "titulo": ParagraphStyle("titulo", fontName="ConsumoSansBold", fontSize=23, leading=29, textColor=VERDE, spaceAfter=10, keepWithNext=True),
        "subtitulo": ParagraphStyle("subtitulo", fontName="ConsumoSansBold", fontSize=11, leading=16, textColor=VERDE, spaceAfter=8, keepWithNext=True),
        "cabecalho": ParagraphStyle("cabecalho", fontName="ConsumoSansBold", fontSize=8, leading=11, textColor=colors.white),
    }

    def paragrafo(texto, estilo="normal"):
        return Paragraph(escape(str(texto)), estilos[estilo])

    def tabela(linhas, larguras):
        tabela_pdf = Table(linhas, colWidths=larguras, repeatRows=1, hAlign="LEFT")
        tabela_pdf.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), VERDE),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f3f6ef")]),
            ("LINEBELOW", (0, 0), (-1, -1), .4, LINHA),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ("RIGHTPADDING", (0, 0), (-1, -1), 8),
            ("TOPPADDING", (0, 0), (-1, -1), 9),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 9),
        ]))
        return tabela_pdf

    logo = svg2rlg(str(Path(__file__).parent / "static/monitoramento/img/esl-tech.svg"))
    proporcao = 33 * mm / logo.width
    logo.scale(proporcao, proporcao)
    logo.width *= proporcao
    logo.height *= proporcao
    historia = [logo, Spacer(1, 7 * mm), paragrafo("Consumo de mensagens", "titulo"),
                paragrafo(nome_unidade, "subtitulo")]
    if historico:
        historia += [paragrafo("Histórico mensal registrado", "subtitulo"),
                     paragrafo("Os meses em andamento são parciais. As mensagens que sobrarem da reserva gratuita não passam para o mês seguinte.", "pequeno"),
                     Spacer(1, 5 * mm)]
        titulos = ("Mês / situação", "Janela gratuita", "Reserva usada", "Reserva restante", "Cobradas Meta", "ESL assume", "Excedente")
        linhas = [[paragrafo(titulo, "cabecalho") for titulo in titulos]]
        for registro in sorted(registros, key=lambda item: item["mes"]):
            linhas.append([paragrafo(f"{registro['rotulo']} - {registro['status_rotulo']}", "pequeno")] + [
                paragrafo(_numero(registro[campo]), "pequeno") for campo in (
                    "qtd_janela_gratuita", "qtd_franquia_consumida", "franquia_restante",
                    "qtd_cobradas_meta", "assumidas_esl", "excedentes_unidade")])
        historia += [tabela(linhas, [49 * mm] + [(documento.width - 49 * mm) / 6] * 6), Spacer(1, 6 * mm)]
        historia.append(paragrafo("Períodos e últimas coletas", "subtitulo"))
        for registro in sorted(registros, key=lambda item: item["mes"]):
            coletado = datetime.fromisoformat(registro["ultimo_sucesso_em"]).strftime("%d/%m/%Y %H:%M")
            historia.append(paragrafo(
                f"{registro['rotulo']}: {registro['periodo_texto']}. Fuso: {registro['fuso_horario']}. "
                f"Coleta: {coletado}." + (" Última tentativa falhou; dados preservados." if registro["coleta_com_falha"] else ""), "pequeno"))
    else:
        registro = registros[0]
        historia += [paragrafo(f"{registro['rotulo']} - {registro['status_rotulo']}", "subtitulo"),
                     paragrafo(registro["periodo_texto"], "pequeno"),
                     paragrafo(f"Fuso: {registro['fuso_horario']}", "pequeno"), Spacer(1, 6 * mm)]
        campos = (("Gratuitas no período de 72 horas", "qtd_janela_gratuita"), ("Utilizadas da reserva gratuita", "qtd_franquia_consumida"),
                  ("Restantes da reserva gratuita", "franquia_restante"), ("Cobradas pela Meta", "qtd_cobradas_meta"),
                  ("Dessas, assumidas pela ESL Tech", "assumidas_esl"), ("Excedentes da unidade", "excedentes_unidade"),
                  ("Total de mensagens entregues", "total_mensagens"))
        linhas = [[paragrafo("Indicador", "cabecalho"), paragrafo("Mensagens", "cabecalho")]]
        linhas.extend([paragrafo(titulo), paragrafo(_numero(registro[campo]))] for titulo, campo in campos)
        historia += [tabela(linhas, [documento.width * .74, documento.width * .26]), Spacer(1, 6 * mm)]
        coletado = datetime.fromisoformat(registro["ultimo_sucesso_em"]).strftime("%d/%m/%Y %H:%M")
        historia.append(paragrafo(f"Última coleta válida: {coletado} ({registro['fuso_horario']}).", "pequeno"))
        if registro["coleta_com_falha"]:
            historia.append(paragrafo("A última tentativa falhou. Os dados da última coleta válida foram preservados.", "pequeno"))
        tarifa = registro["tarifa_referencia_brl"].rstrip("0").rstrip(".").replace(".", ",")
        valor = registro["valor_referencia_excedente"].replace(".", ",")
        historia.append(paragrafo(
            f"Referência brasileira em BRL: R$ {tarifa}/mensagem de serviço. "
            f"Excedente nessa referência: R$ {valor}. Vigência: {registro['tarifa_vigencia']}. "
            "Sujeita a alterações da Meta; não é um valor de fatura.", "pequeno"))
    # A explicação fica inteira em uma seção própria, sem disputar espaço com
    # os indicadores nem começar nas últimas linhas da página de resultados.
    historia += [PageBreak(), paragrafo("Entenda sua cobertura", "titulo")]
    for texto in (
        "72 horas gratuitas: para clientes que chegam por anúncios da Meta, como no Facebook ou Instagram, com botão para conversar no WhatsApp. Também pode valer para o botão de WhatsApp de uma página do Facebook. A entrada precisa acontecer pelo aplicativo no celular e ser reconhecida pela Meta. Um anúncio em outra plataforma não dá esse benefício só por ter um link para o WhatsApp.",
        "O prazo de 72 horas começa na primeira resposta do chatbot à mensagem que veio dessa entrada. Essa resposta precisa acontecer em até 24 horas após a mensagem do cliente. As mensagens gratuitas desse período não gastam a reserva mensal.",
        "Prazo para responder: cada mensagem do cliente abre ou renova 24 horas para respostas comuns. Depois disso, só são permitidos modelos aprovados pela Meta, chamados templates, até o cliente escrever de novo. As 24 horas se renovam, mas aquelas 72 horas não reiniciam. Dentro das 72 horas, os templates também são gratuitos.",
        "Reserva gratuita: 1.000 respostas comuns do chatbot por número de WhatsApp, a cada mês, compartilhadas entre todos os clientes. É usada quando o cliente chega sem o período gratuito de 72 horas ou quando esse prazo termina. O saldo não acumula. Se outro sistema usar o mesmo número, também poderá consumir essa reserva.",
        "Cobertura ESL Tech: quando a reserva acaba, a ESL assume as primeiras 1.000 respostas comuns cobradas no mês. Só o que ultrapassar essa cobertura fica por conta da unidade, conforme as condições do serviço. Exemplo: de 1.300 mensagens cobradas pela Meta, a ESL assume 1.000 e a unidade, 300.",
        "Em andamento: é o mês atual e os números ainda estão sendo atualizados. Em conferência: o mês terminou e consultamos a Meta diariamente para conferir ajustes. A primeira conferência para concluir o mês acontece no dia 25 do mês seguinte. Se houver diferença ou falha, o acompanhamento diário continua até uma nova tentativa no próximo dia 25.",
        "Consolidado: os números coincidiram na conferência da ESL e o acompanhamento automático desse mês foi concluído. Isso não significa que a Meta já fechou a fatura. Este relatório acompanha respostas comuns em conversas individuais. Templates fora das 72 horas têm regras de cobrança próprias. Os números vêm da Meta e podem ser revisados por ela.",
    ):
        historia += [paragrafo(texto, "pequeno"), Spacer(1, 2 * mm)]
    emitido = (agora or datetime.now(timezone.utc)).strftime("%d/%m/%Y %H:%M UTC")

    def rodape(canvas, doc):
        canvas.saveState()
        canvas.setStrokeColor(LINHA)
        canvas.line(18 * mm, 14 * mm, pagina[0] - 18 * mm, 14 * mm)
        canvas.setFont("ConsumoSans", 7)
        canvas.setFillColor(VERDE)
        canvas.drawString(18 * mm, 10 * mm, f"ESL Tech | Relatório de consumo | Emitido em {emitido}")
        canvas.drawRightString(pagina[0] - 18 * mm, 10 * mm, f"Página {doc.page}")
        canvas.restoreState()

    documento.build(historia, onFirstPage=rodape, onLaterPages=rodape)
    return destino.getvalue()
