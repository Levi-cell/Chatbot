"""Patch note editorial V1.0.8. Somente conteúdo confirmado em 62dca9a."""
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from reportlab.platypus import Paragraph


ROOT = Path(__file__).resolve().parents[3]
DESTINO = ROOT / "output" / "pdf" / "patch_notes_v1.0.8.pdf"
DESTINO.parent.mkdir(parents=True, exist_ok=True)
for nome, arquivo in (("Segoe", "segoeui.ttf"), ("SegoeBold", "segoeuib.ttf")):
    pdfmetrics.registerFont(TTFont(nome, str(Path("C:/Windows/Fonts") / arquivo)))
pdfmetrics.registerFontFamily("Segoe", normal="Segoe", bold="SegoeBold")

W, H = 595.276, 841.89
M, CW = 46, W - 92
NAVY = "#112D46"
TEAL = "#00A99A"
ORANGE = "#FF8617"
BLUE = "#08799D"
INK = "#1D3042"
GRAY = "#53677B"
MUTED = "#BDCDD9"
LINE = "#D8E3EB"
PALE = "#EDF8F5"
CREAM = "#FFF4E8"
LAVENDER = "#F3F0FB"
WHITE = "#FFFFFF"

c = canvas.Canvas(str(DESTINO), pagesize=(W, H), pageCompression=1)
c.setTitle("Chatbot Supera | Novidades V1.0.8")
c.setAuthor("Chatbot Supera")
c.setSubject("Principais mudanças da V1.0.5 à V1.0.8 e histórico V1.0.0 a V1.0.8")
medicoes = []


def rect(x, y, w, h, fill, stroke=None, radius=14):
    c.setFillColor(colors.HexColor(fill))
    c.setStrokeColor(colors.HexColor(stroke or fill))
    c.setLineWidth(0.8)
    c.roundRect(x, H - y - h, w, h, radius, fill=1, stroke=bool(stroke))


def text(txt, x, y, w, size=11, color=INK, bold=False, leading=None,
         max_height=None, align=TA_LEFT):
    style = ParagraphStyle(
        "texto", fontName="SegoeBold" if bold else "Segoe", fontSize=size,
        leading=leading or size * 1.37, textColor=colors.HexColor(color),
        alignment=align, spaceBefore=0, spaceAfter=0,
    )
    p = Paragraph(txt, style)
    _, h = p.wrap(w, H)
    if max_height is not None and h > max_height + 0.1:
        raise ValueError(f"Texto excedeu bloco: {h:.1f} > {max_height}: {txt[:90]}")
    if y + h > 790:
        raise ValueError(f"Texto invadiu rodapé: {y + h}: {txt[:90]}")
    p.drawOn(c, x, H - y - h)
    medicoes.append((c.getPageNumber(), round(y, 1), round(h, 1), txt[:50]))
    return h


def pill(txt, x, y, w, bg=TEAL, fg=WHITE):
    rect(x, y, w, 25, bg, radius=12.5)
    text(txt, x + 11, y + 6, w - 22, size=8, color=fg, bold=True, max_height=13)


def footer(n, dark=False):
    c.setStrokeColor(colors.HexColor("#405C73" if dark else LINE))
    c.line(M, 31, W - M, 31)
    c.setFont("Segoe", 7.5)
    c.setFillColor(colors.HexColor(MUTED if dark else GRAY))
    c.drawString(M, 18, "Chatbot Supera | Novidades V1.0.8")
    c.drawRightString(W - M, 18, f"{n} / 5")
    c.showPage()


def heading(num, label, title, subtitle):
    pill(num, M, 43, 34, bg=BLUE)
    text(label, M + 46, 50, CW - 46, size=8.8, color=BLUE, bold=True)
    h = text(title, M, 91, CW, size=27, color=NAVY, bold=True, leading=31.5,
             max_height=65)
    text(subtitle, M, 101 + h, CW, size=10.6, color=GRAY, max_height=46)


def card(x, y, w, h, label, title, body, bg=PALE, tag_color=TEAL):
    rect(x, y, w, h, bg)
    text(label, x + 17, y + 17, w - 34, size=8, color=tag_color, bold=True)
    th = text(title, x + 17, y + 40, w - 34, size=15, color=NAVY,
              bold=True, leading=18, max_height=55)
    text(body, x + 17, y + 52 + th, w - 34, size=10.1,
         max_height=h - 68 - th)


# 1. Capa: uma promessa de valor, sem números de resultados inventados.
rect(0, 0, W, H, NAVY, radius=0)
c.setFillColor(colors.HexColor("#1B3B55"))
c.circle(W + 12, H - 89, 176, fill=1, stroke=0)
c.setFillColor(colors.HexColor("#23465F"))
c.circle(W + 18, H - 77, 133, fill=1, stroke=0)
nodes = [(449, 52), (480, 89), (533, 77), (511, 126), (567, 139), (453, 144)]
c.setStrokeColor(colors.HexColor("#58778C"))
c.setLineWidth(1.6)
for a, b in [(0, 1), (0, 2), (1, 3), (2, 3), (2, 4), (3, 4), (1, 5), (3, 5)]:
    c.line(nodes[a][0], H - nodes[a][1], nodes[b][0], H - nodes[b][1])
for i, (x, y) in enumerate(nodes):
    c.setFillColor(colors.HexColor(ORANGE if i in (0, 3) else "#C5D8E4"))
    c.circle(x, H - y, 5, fill=1, stroke=0)
text("CHATBOT SUPERA", M, 42, 300, size=11, color=WHITE, bold=True)
pill("PATCH NOTES | V1.0.8", M, 83, 147, bg=ORANGE, fg=NAVY)
text("Mais acolhimento.<br/>Mais clareza.<br/>Mais contexto.", M, 150, CW,
     size=34, leading=40, color=WHITE, bold=True, max_height=125)
text("Da V1.0.5 à V1.0.8, o atendimento ganhou novas formas de respeitar "
     "o perfil do cliente e a rotina de cada unidade.", M, 291, CW - 38,
     size=13, leading=18.5, color="#D2DEE7", max_height=61)
rect(M, 373, CW, 121, "#193E59", stroke="#365870", radius=18)
text("O DESTAQUE DA V1.0.8", M + 22, 392, CW - 44,
     size=9, color=ORANGE, bold=True)
text("O cliente não precisa caber<br/>em um único jeito de atender.", M + 22, 415,
     CW - 44, size=21, leading=26, color=WHITE, bold=True, max_height=53)
gap = 12
col = (CW - gap * 2) / 3
for i, (num, title, body) in enumerate([
    ("01", "Cuidado com 60+", "Contato comercial dedicado, conforme a escolha da unidade."),
    ("02", "E-mail flexível", "Menos barreiras para quem não tem um endereço de e-mail."),
    ("03", "Mais continuidade", "Retomadas acolhedoras e informações mais úteis ao comercial."),
]):
    x = M + i * (col + gap)
    rect(x, 520, col, 155, "#213F56", stroke="#38566D")
    text(num, x + 15, 536, col - 30, size=10, color=ORANGE, bold=True)
    text(title, x + 15, 561, col - 30, size=12, color=WHITE, bold=True,
         max_height=35)
    text(body, x + 15, 601, col - 30, size=9.2, color="#D2DEE7", max_height=59)
text("NESTA EDIÇÃO", M, 704, CW, size=8, color=ORANGE, bold=True)
text("O que mudou no atendimento, o que chega ao comercial e o histórico "
     "completo da V1.0.0 à V1.0.8.", M, 725, CW - 30,
     size=10.5, color=WHITE, max_height=32)
text("Publicada em 30 de agosto de 2026  |  Referência da edição: 62dca9a", M, 774,
     CW, size=7.5, color=MUTED, max_height=12)
footer(1, dark=True)

# 2. As configurações são explicadas pelo efeito, não por nomes de colunas.
heading("01", "ATENDIMENTO E ACESSIBILIDADE",
        "Um caminho adequado<br/>para cada pessoa.",
        "A unidade pode escolher como acolher o público 60+ e quando pedir "
        "um e-mail obrigatório. Veja o que isso muda na prática.")
col = (CW - 14) / 2
card(M, 211, col, 228, "60+ | ATENDIMENTO PARA SI", "Com apoio comercial\nativado".replace("\n", "<br/>"),
     "Depois de informar a idade, a pessoa recebe o botão <b>Falar com Comercial</b>. "
     "O atendimento automático termina ali, antes da triagem e do envio ao Funil.<br/><br/>"
     "<b>Sem bloqueio de 30 dias:</b> esse encaminhamento não impede um novo contato.",
     bg=PALE)
card(M + col + 14, 211, col, 228, "60+ | ATENDIMENTO PARA SI", "Com atendimento\nautomático mantido".replace("\n", "<br/>"),
     "A pessoa segue normalmente pelo chatbot. O e-mail continua sendo perguntado, "
     "mas uma resposta como <b>“Não tenho”</b> permite continuar.<br/><br/>"
     "<b>Vale mesmo se a unidade exigir e-mail</b> dos demais clientes.",
     bg=CREAM, tag_color="#AE5709")
text("E para os demais atendimentos?", M, 464, CW, size=18, color=NAVY, bold=True)
text("Para o próprio cliente de 18 a 59 anos ou para um dependente, "
     "vale a escolha da unidade:", M, 495, CW, size=10.6, max_height=31)
rect(M, 543, CW, 60, "#F3F6F9", stroke=LINE)
text("E-MAIL OBRIGATÓRIO", M + 16, 558, 159, size=8.4, color=BLUE, bold=True)
text("É preciso informar um endereço aceito para seguir.", M + 186, 556,
     CW - 202, size=10.3, max_height=32)
rect(M, 611, CW, 60, PALE)
text("E-MAIL OPCIONAL", M + 16, 626, 159, size=8.4, color="#00796F", bold=True)
text("Pode seguir sem endereço. Dúvidas sobre valores, reforço escolar e "
     "mensagens com mídia continuam recebendo orientação.", M + 186, 620,
     CW - 202, size=9.9, max_height=43)
text("Importante saber", M, 695, CW, size=11.5, color=NAVY, bold=True)
text("A regra especial é para quem busca atendimento para si, dos 60 aos 99 anos. "
     "Um dependente 60+ segue as regras usuais; pessoas com 100 anos ou mais "
     "mantêm o encaminhamento já existente. O botão oferece o contato comercial, "
     "sem prometer atendimento imediato.", M, 718, CW, size=9.3, leading=12.8,
     max_height=55)
text("Padrão inicial: apoio comercial desativado e e-mail obrigatório, com a exceção 60+.",
     M, 779, CW, size=7.4, color=GRAY, max_height=11)
footer(2)

# 3. Exemplos ilustrativos, sem dados pessoais e sem prometer follow-up.
heading("02", "CONVERSAS MAIS CLARAS",
        "O bot acompanha a conversa.<br/>Não apenas a próxima resposta.",
        "Apresentações personalizadas, retomadas acolhedoras e escolhas "
        "interpretadas com mais cuidado.")
rect(M, 207, CW, 194, PALE, radius=18)
text("RETOMADA APÓS UMA PAUSA", M + 19, 226, CW - 38,
     size=8.5, color="#00796F", bold=True)
text("“Olá novamente, Maria!”", M + 19, 254, CW - 38,
     size=20, color=NAVY, bold=True, max_height=28)
text("Se o cliente volta a responder depois de <b>três horas ou mais</b> desde "
     "a última mensagem do bot, a resposta pode incluir uma saudação com o nome "
     "já informado, na mesma conversa.", M + 19, 299, CW - 38,
     size=11, max_height=47)
text("A resposta válida segue adiante. Se precisar de correção, o bot orienta "
     "e repete a pergunta. Não é um lembrete automático e não reinicia o atendimento.",
     M + 19, 359, CW - 38, size=9.5, max_height=29)
card(M, 423, col, 226, "IDENTIDADE DA UNIDADE", "Uma apresentação\nmais próxima".replace("\n", "<br/>"),
     "O chatbot se apresenta com o <b>nome do agente e da unidade</b>, "
     "respeitando a forma de apresentação configurada.<br/><br/>"
     "As mensagens de boas-vindas e de continuidade também ficaram mais acolhedoras.",
     bg=LAVENDER, tag_color="#665095")
card(M + col + 14, 423, col, 226, "ESCOLHAS MAIS SEGURAS", "Pedir informação\nnão é aceitar a oferta".replace("\n", "<br/>"),
     "<b>“Quero mais informações”</b> não faz o atendimento avançar como se "
     "fosse uma confirmação. O bot orienta a escolha e mantém a oferta.<br/><br/>"
     "Respostas diretas como <b>“quero”, “sim, quero” e “quero sim”</b> continuam aceitas.",
     bg=CREAM, tag_color="#AE5709")
rect(M, 675, CW, 87, NAVY)
text("UM CONVITE MAIS DIRETO", M + 20, 691, 245, size=8, color=ORANGE, bold=True)
text("O botão da triagem agora se chama", M + 20, 717, 254, size=10.5, color=WHITE)
pill("Começar triagem", M + 305, 705, 168, bg=TEAL)
text("Os exemplos desta página são ilustrativos.", M, 775, CW,
     size=7.5, color=GRAY, max_height=11)
footer(3)

# 4. Dados úteis ao comercial e ferramentas de leitura separadas do atendimento.
heading("03", "INFORMAÇÃO PARA COMERCIAL E GESTÃO",
        "Mais contexto para continuar<br/>o atendimento com confiança.",
        "O cadastro acompanha o que o cliente informa, e o histórico ajuda "
        "a entender cada atendimento sem misturar as unidades.")
card(M, 210, col, 225, "PROFISSÃO", "Cadastro atualizado.<br/>Histórico preservado.",
     "A profissão mais recente atualiza o cadastro. Cada conversa mantém a "
     "profissão informada nela, para preservar seu contexto.<br/><br/>"
     "Respostas fora do assunto já conhecidas, como <b>“Não entendi”</b>, "
     "fazem a pergunta ser repetida em vez de virarem profissão.", bg=PALE)
card(M + col + 14, 210, col, 225, "E-MAIL NO FUNIL", "Ausência de e-mail<br/>também é informação.",
     "Quando o e-mail é opcional, o resumo comercial diferencia "
     "<b>“não tem”</b> de <b>“não informado”</b>.<br/><br/>"
     "Nos novos atendimentos, usa a resposta daquela conversa, evitando "
     "trocar seu conteúdo por um endereço informado em outro momento.",
     bg=CREAM, tag_color="#AE5709")
text("Duas formas de acompanhar sua unidade", M, 460, CW,
     size=18, color=NAVY, bold=True)
text("Visão semanal, dos últimos sete dias, ou visão total, desde os primeiros "
     "registros disponíveis até a geração do material.", M, 493, CW,
     size=10.5, max_height=30)
card(M, 543, col, 149, "CONVERSAS", "Histórico em sequência",
     "Um painel reúne as conversas da mesma pessoa com a mesma unidade, "
     "mesmo quando o bot precisou abrir um novo atendimento.",
     bg="#F3F6F9", tag_color=BLUE)
card(M + col + 14, 543, col, 149, "DESEMPENHO", "Indicadores em PDF",
     "Contatos recebidos, envios ao Funil, notas de satisfação e comentários "
     "com identificação e profissão dos clientes.",
     bg="#F3F6F9", tag_color=BLUE)
rect(M, 712, CW, 61, NAVY)
text("O QUE CONTINUA VALENDO", M + 17, 724, CW - 34,
     size=8, color=ORANGE, bold=True)
text("Os relatórios são gerados sob demanda. O painel de conversas e o "
     "relatório de indicadores são materiais separados, próprios de cada unidade.",
     M + 17, 744, CW - 34, size=9.1, color=WHITE, max_height=26)
footer(4)

# 5. A história completa é mantida sem expor detalhes internos de programação.
heading("04", "HISTÓRICO DAS VERSÕES",
        "Uma evolução construída<br/>conversa a conversa.",
        "Da proteção inicial à personalização por unidade: os principais "
        "avanços da V1.0.0 à V1.0.8.")
historico = [
    ("V1.0.0", "Proteção contra bots", "Medidas para reduzir mensagens automatizadas e usos indevidos do atendimento."),
    ("V1.0.1", "Profissão no atendimento", "Coleta da profissão para enriquecer as informações recebidas pela equipe comercial."),
    ("V1.0.2", "Liberdade para comentar", "O cliente escolhe se quer deixar um comentário na pesquisa de satisfação."),
    ("V1.0.3", "Comunicação mais organizada", "Organização da conexão com o WhatsApp para facilitar a manutenção do serviço."),
    ("V1.0.4", "Confirmações mais claras", "Melhorias nas escolhas e na forma de orientar respostas fora do esperado."),
    ("V1.0.5", "Triagem por idade e contexto no Funil", "Perguntas por perfil, respostas detalhadas e orientação sobre reforço escolar. Correção: profissão obrigatória após confirmar quem será atendido."),
    ("V1.0.6", "Apresentação com identidade local", "Nome do agente e da unidade na apresentação inicial, com a forma de tratamento configurada."),
    ("V1.0.7", "Profissão atualizada e operação organizada", "Cadastro e histórico de profissão preservados, mensagens aprimoradas e manutenção interna simplificada."),
    ("V1.0.8", "Mais flexibilidade e continuidade", "Atendimento 60+, e-mail configurável, saudação de retorno, escolhas mais claras e relatórios por unidade."),
]
for i, (versao, titulo, corpo) in enumerate(historico):
    y = 198 + i * 57
    destaque = i == 8
    rect(M, y, CW, 51, NAVY if destaque else ("#F3F6F9" if i % 2 == 0 else WHITE), radius=10)
    text(versao, M + 13, y + 15, 67, size=10, color=ORANGE if destaque else BLUE, bold=True)
    text(titulo, M + 93, y + 5, CW - 107, size=10.4,
         color=WHITE if destaque else NAVY, bold=True, max_height=15)
    text(corpo, M + 93, y + 22, CW - 109, size=8.65, leading=11.2,
         color="#D2DEE7" if destaque else GRAY, max_height=25)
text("A base continua: seis perguntas de triagem, opções claras de resposta e "
     "informações organizadas para apoiar o próximo contato da equipe.",
     M, 731, CW, size=10.3, color=NAVY, max_height=32)
text("Este material descreve as entregas até a V1.0.8. Funcionalidades futuras "
     "não estão incluídas.", M, 775, CW, size=7.5, color=GRAY, max_height=12)
footer(5)
c.save()
print(f"Gerado: {DESTINO}")
print(f"Blocos de texto verificados: {len(medicoes)}")
