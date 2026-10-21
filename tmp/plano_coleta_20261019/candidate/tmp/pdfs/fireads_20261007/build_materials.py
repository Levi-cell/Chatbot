from pathlib import Path
from xml.sax.saxutils import escape
import json

from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import Paragraph, Table, TableStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / 'output' / 'pdf'
OUT.mkdir(parents=True, exist_ok=True)
FONT = Path('C:/Windows/Fonts')
for name, filename in [('Body', 'segoeui.ttf'), ('Bold', 'segoeuib.ttf'), ('Italic', 'segoeuii.ttf')]:
    pdfmetrics.registerFont(TTFont(name, str(FONT / filename)))
pdfmetrics.registerFontFamily('Body', normal='Body', bold='Bold', italic='Italic', boldItalic='Bold')

W, H = A4
M, CW, BOTTOM = 40, W - 80, 774
INK = '#19382E'
TEXT = '#283D38'
MUTED = '#64736F'
ORANGE = '#F47B20'
GREEN = '#176B56'
TEAL = '#187D8D'
PURPLE = '#6759A0'
BG = '#FAFAF6'
LINE = '#DDE5DE'
PALE = '#EFF4EC'
AMBER = '#FFF0D9'
BLUE = '#ECF4F8'
LILAC = '#F1EEF9'
WHITE = '#FFFFFF'
AUDIT = []


def col(c):
    return colors.HexColor(c)


def paragraph(s, width, size=11.4, color=TEXT, bold=False, leading=None):
    st = ParagraphStyle('p', fontName='Bold' if bold else 'Body', fontSize=size,
                        leading=leading or size * 1.43, textColor=col(color),
                        spaceAfter=0, allowWidows=0, allowOrphans=0)
    p = Paragraph(s, st)
    _, h = p.wrap(width, 1500)
    return p, h


class Book:
    def __init__(self, filename, title, label, count):
        self.path = OUT / filename
        self.c = canvas.Canvas(str(self.path), pagesize=A4, pageCompression=1)
        self.c.setTitle(title)
        self.c.setAuthor('ESL Tech')
        self.c.setSubject('Alinhamento de funcionamento planejado entre SUPERA Santo André, chatbot, FireAds e Funil de Vendas')
        self.label, self.count, self.page = label, count, 0

    def rect(self, x, y, w, h, fill=WHITE, stroke=None, radius=10):
        self.c.setFillColor(col(fill))
        self.c.setStrokeColor(col(stroke or fill))
        self.c.roundRect(x, H-y-h, w, h, radius, fill=1, stroke=bool(stroke))

    def t(self, s, x, y, w, size=11.4, color=TEXT, bold=False, leading=None):
        p, h = paragraph(s, w, size, color, bold, leading)
        if y+h > BOTTOM + 0.5:
            raise ValueError(f'{self.path.name} p{self.page}: text overflow {y+h:.1f}: {s[:60]}')
        p.drawOn(self.c, x, H-y-h)
        AUDIT.append({'file': self.path.name, 'page': self.page, 'top': y, 'bottom': y+h, 'text': s})
        return y+h

    def start(self, title, subtitle, tag=None):
        if self.page:
            self.c.showPage()
        self.page += 1
        self.c.setFillColor(col(BG)); self.c.rect(0, 0, W, H, fill=1, stroke=0)
        self.c.setFillColor(col(ORANGE)); self.c.rect(0, H-7, W, 7, fill=1, stroke=0)
        self.t(tag or self.label, M, 28, CW-70, 9.3, GREEN, True)
        self.t(f'{self.page:02}', W-73, 26, 33, 12, ORANGE, True)
        y = self.t(title, M, 57, CW, 27, INK, True, 32)
        y = self.t(subtitle, M, y+12, CW, 11.4, MUTED)
        self.c.setStrokeColor(col(LINE)); self.c.line(M, 43, W-M, 43)
        self.c.setFont('Body', 8.1); self.c.setFillColor(col(MUTED))
        self.c.drawString(M, 28, 'ESL Tech | SUPERA Santo André | FireAds')
        self.c.drawRightString(W-M, 28, f'Planejamento - 07/10/2026 | {self.page}/{self.count}')
        self.c.bookmarkPage(f'p{self.page}')
        self.c.addOutlineEntry(title.replace('<br/>', ' '), f'p{self.page}', level=0)
        return y+23

    def label(self, s, y):
        return self.t(s, M, y, CW, 14, INK, True)+10

    def note(self, title, body, y, fill=PALE, accent=GREEN):
        _, ht = paragraph(title, CW-34, 11.7, accent, True)
        _, hb = paragraph(body, CW-34, 11.1)
        h = 28+ht+7+hb
        self.rect(M, y, CW, h, fill)
        self.c.setFillColor(col(accent)); self.c.rect(M, H-y-h, 4, h, fill=1, stroke=0)
        self.t(title, M+17, y+13, CW-34, 11.7, accent, True)
        self.t(body, M+17, y+20+ht, CW-34, 11.1)
        return y+h+16

    def cards(self, entries, y, gap=12, size=11.1):
        # entries: (eyebrow, title, body, fill, accent)
        w=(CW-gap*(len(entries)-1))/len(entries)
        heights=[]
        for eyebrow,title,body,fill,accent in entries:
            _,h1=paragraph(title,w-28,14,INK,True)
            _,h2=paragraph(body,w-28,size)
            heights.append(49+h1+9+h2)
        h=max(heights)
        if y+h > BOTTOM: raise ValueError(f'cards overflow p{self.page}: {y+h}')
        for i,(eyebrow,title,body,fill,accent) in enumerate(entries):
            x=M+i*(w+gap)
            self.rect(x,y,w,h,fill,LINE)
            self.t(eyebrow,x+14,y+12,w-28,9.1,accent,True)
            yy=self.t(title,x+14,y+34,w-28,14,INK,True)
            self.t(body,x+14,yy+9,w-28,size)
        return y+h+17

    def table(self, headers, rows, y, widths, size=10.6):
        data=[]
        for n,row in enumerate([headers]+rows):
            data.append([paragraph(s,widths[i]-19,size,WHITE if n==0 else TEXT,n==0)[0] for i,s in enumerate(row)])
        tb=Table(data,colWidths=widths,hAlign='LEFT')
        tb.setStyle(TableStyle([
            ('BACKGROUND',(0,0),(-1,0),col(INK)),
            ('ROWBACKGROUNDS',(0,1),(-1,-1),[col(WHITE),col(PALE)]),
            ('VALIGN',(0,0),(-1,-1),'TOP'),
            ('LEFTPADDING',(0,0),(-1,-1),10),('RIGHTPADDING',(0,0),(-1,-1),9),
            ('TOPPADDING',(0,0),(-1,-1),9),('BOTTOMPADDING',(0,0),(-1,-1),9),
            ('LINEBELOW',(0,0),(-1,0),0.7,col(INK)),
            ('LINEBELOW',(0,1),(-1,-1),0.4,col(LINE))]))
        _,hh=tb.wrap(CW,1500)
        if y+hh>BOTTOM: raise ValueError(f'table overflow p{self.page}: {y+hh}')
        tb.drawOn(self.c,M,H-y-hh)
        AUDIT.append({'file':self.path.name,'page':self.page,'top':y,'bottom':y+hh,'text':'TABLE'})
        return y+hh+17

    def bullets(self, items, y, size=11.4, gap=9):
        for item in items:
            self.c.setFillColor(col(ORANGE)); self.c.circle(M+3,H-y-7,2.4,fill=1,stroke=0)
            y=self.t(item,M+16,y,CW-16,size)+gap
        return y+6

    def step(self, n, title, body, y, accent=GREEN):
        self.c.setFillColor(col(accent)); self.c.circle(M+14,H-y-15,14,fill=1,stroke=0)
        self.c.setFillColor(col(WHITE)); self.c.setFont('Bold',11)
        self.c.drawCentredString(M+14,H-y-19,str(n))
        yy=self.t(title,M+42,y,CW-42,12.2,INK,True)
        yy=self.t(body,M+42,yy+5,CW-42,11.2)
        return yy+18

    def arrow(self,x1,y1,x2,y2,color=GREEN):
        c=self.c;c.setStrokeColor(col(color));c.setFillColor(col(color));c.setLineWidth(1.6)
        c.line(x1,H-y1,x2,H-y2)
        p=c.beginPath()
        if abs(x2-x1)>abs(y2-y1):
            s=1 if x2>=x1 else -1;p.moveTo(x2,H-y2);p.lineTo(x2-s*5,H-y2+3);p.lineTo(x2-s*5,H-y2-3)
        else:
            s=1 if y2>=y1 else -1;p.moveTo(x2,H-y2);p.lineTo(x2-3,H-y2+s*5);p.lineTo(x2+3,H-y2+s*5)
        p.close();c.drawPath(p,fill=1,stroke=0)

    def lane(self, nodes, y):
        gap=14; w=(CW-gap*(len(nodes)-1))/len(nodes); h=110
        for i,(label,body,accent) in enumerate(nodes):
            x=M+i*(w+gap)
            self.rect(x,y,w,h,WHITE,LINE)
            self.c.setFillColor(col(accent));self.c.circle(x+18,H-y-20,9,fill=1,stroke=0)
            self.c.setFillColor(col(WHITE));self.c.setFont('Bold',8);self.c.drawCentredString(x+18,H-y-23,str(i+1))
            yy=self.t(label,x+12,y+39,w-24,11.8,INK,True)
            self.t(body,x+12,yy+6,w-24,9.9,MUTED)
            if i<len(nodes)-1:self.arrow(x+w+2,y+h/2,x+w+gap-2,y+h/2,MUTED)
        return y+h+21

    def done(self):
        assert self.page==self.count,(self.path.name,self.page,self.count)
        self.c.save()


def main_guide():
    b=Book('guia_chatbot_fireads_flavio.pdf','Chatbot e FireAds: guia de funcionamento para Flávio e equipe','GUIA DE FUNCIONAMENTO',8)
    y=b.start('Do formulário ao atendimento.<br/>Tudo conectado.',
              'Como o chatbot, o Funil de Vendas e o dashboard da FireAds trabalharão juntos na unidade Santo André.',
              'PARA FLÁVIO E EQUIPE FIREADS')
    y=b.note('Material de alinhamento - ainda não implantado',
             'Este guia descreve o funcionamento combinado e planejado. Dois pontos ainda aguardam o Eduardo: as opções do formulário Google e as abas da Meta que serão consultadas.',y,AMBER,'#9A590D')
    y=b.lane([('Formulário','A pessoa informa seus dados.',ORANGE),('Dashboard','A FireAds guarda o cadastro.',TEAL),('Chatbot','A pessoa chama no WhatsApp.',GREEN),('Funil','A equipe recebe o atendimento.',PURPLE)],y)
    y=b.note('O caminho de volta completa o cadastro',
             'A FireAds receberá o atendimento do Funil e procurará o contato no dashboard: <b>se já existir, atualiza; se não existir, cadastra.</b> O chatbot consulta o dashboard e envia o lead somente ao Funil.',y)
    y=b.cards([('PARA O CLIENTE','Menos repetição','Dados válidos do formulário podem ser aproveitados, quando as condições deste guia forem atendidas.',WHITE,GREEN),
               ('PARA A UNIDADE','Mais informação','O cadastro reúne o contato inicial e os detalhes coletados no atendimento, sem criar uma cópia desnecessária.',WHITE,TEAL)],y)
    b.t('Neste material, “lead” significa uma pessoa interessada. “Dashboard” é o painel em que a FireAds organiza os contatos.',M,y,CW,10.6,MUTED)

    y=b.start('Três maneiras de chegar', 'O atendimento começa quando a pessoa envia uma mensagem no WhatsApp.')
    y=b.step('A','Preenche o formulário e chama o chatbot',
             'O formulário já cria um registro na FireAds. Na abertura elegível, o bot procura esse número e avalia se pode aproveitar os dados. Encontrar um formulário não dispensa as verificações.',y,ORANGE)
    y=b.step('B','Preenche o formulário, mas não chama',
             'O registro permanece no dashboard. Só preencher o formulário não inicia uma conversa com o bot e não faz o bot enviar uma oportunidade ao Funil.',y,TEAL)
    y=b.step('C','Chama por outra fonte',
             'Pode ter visto a fachada, recebido uma indicação ou visitado o site da unidade. Sem formulário aproveitável, faz o atendimento completo. Quando chegar ao Funil, poderá ser incluído no dashboard pela FireAds.',y,GREEN)
    y=b.note('O telefone já vem do WhatsApp',
             'O bot usa o número de quem enviou a mensagem para procurar o cadastro. Não pede ao cliente que digite o próprio telefone.',y)
    y=b.cards([('IMPORTANTE','Uma pessoa por atendimento','O bot conhece o perfil do titular ou de um dependente. “Para mim e outra pessoa”, no formulário Meta, será tratado como dependente.',WHITE,GREEN),
               ('SEM INTEGRAÇÃO','Atendimento atual preservado','Unidades que não usam a FireAds seguem o funcionamento atual. Não consultam o dashboard e não recebem classificação FireAds.',WHITE,TEAL)],y)

    y=b.start('O que o bot aproveita', 'Apenas três informações do formulário entram no atendimento. O restante continua sendo perguntado quando necessário.')
    y=b.cards([('01','Nome do titular','Usa o primeiro nome, incluindo nomes compostos quando reconhecidos.',WHITE,GREEN),
               ('02','E-mail do titular','Aproveita o endereço válido do contato, mesmo quando o treino é para um dependente.',WHITE,TEAL),
               ('03','Para quem é','Distingue atendimento para a própria pessoa ou para um dependente.',WHITE,ORANGE)],y,size=10.7)
    y=b.table(['Resposta no formulário Meta','Como o chatbot entende'],[
        ['Para mim','Atendimento para o titular.'],
        ['Para meu pai ou minha mãe','Atendimento para um dependente.'],
        ['Para meu filho ou filha','Atendimento para um dependente.'],
        ['Para mim e outra pessoa','Atendimento para um dependente.']],y,[CW*.56,CW*.44])
    y=b.note('Idade por faixa não substitui a idade exata',
             'O bot continua perguntando a idade e fazendo as perguntas de triagem. Objetivo principal, cidade, bairro e quem decide a matrícula não preenchem respostas do atendimento.',y)
    b.note('Google: decisão ainda pendente',
           '“Adulto” ou “Pessoa com 60 anos ou mais” não esclarecem se é para o titular ou para um familiar. Eduardo confirmará como resolver isso. Não será feita uma suposição automática.',y,AMBER,'#9A590D')

    y=b.start('Como fica a conversa', 'Quando os três dados estiverem válidos, completos e dentro das regras, a primeira pergunta será sobre a profissão.')
    y=b.note('Exemplo ilustrativo - formulário Meta válido',
             '“Olá, Ana! Seja muito bem-vinda! Sou a Dora, assistente do SUPERA Santo André. Vi que você já preencheu um dos nossos formulários. Para continuarmos com sua reserva por cortesia da unidade, precisamos fazer mais algumas perguntinhas, ok? Me diz, qual é a sua profissão hoje?”',y,PALE,GREEN)
    y=b.table(['Já resolvido pelo formulário','O que continua no atendimento'],[
        ['Nome do titular','Profissão do titular.'],
        ['Para quem é e sua confirmação','Nome do dependente, quando for para outra pessoa.'],
        ['E-mail válido do titular','Idade exata, convite e aceite da oferta.'],
        ['Não repetir essas coletas','Perguntas da triagem e orientação para a reserva.']],y,[CW*.46,CW*.54])
    y=b.bullets(['Se o cliente não responder à pergunta da profissão de forma válida, o bot repete a pergunta com o tratamento previsto; não reinicia toda a apresentação.',
                 'Na rota completa, o bot começa perguntando o nome e coleta os dados normalmente.',
                 'O formulário não confirma uma reserva e não substitui a triagem. As regras de idade continuam valendo.'],y)
    b.note('O atendimento segue seu ritmo normal',
           'Os lembretes de follow-up continuam seguindo a etapa em que a pessoa parou. As mensagens seguintes não provocam uma nova consulta ao dashboard.',y,BLUE,TEAL)

    y=b.start('Quando haverá consulta?', 'O histórico é considerado para cada cliente com aquela unidade. Já ter falado com outra unidade não elimina a primeira consulta aqui.')
    y=b.table(['Situação na unidade integrada','O que acontecerá'],[
        ['Primeira conversa com a unidade','Consultar antes da primeira resposta do bot.'],
        ['Nova conversa; a última terminou por idade','Consultar novamente. A conversa anterior continua encerrada.'],
        ['Nova conversa; a última terminou por outro motivo','Não consultar. Fazer atendimento completo e classificar como orgânico.'],
        ['Outra mensagem na conversa já iniciada','Continuar o atendimento, sem consultar de novo.']],y,[CW*.48,CW*.52])
    y=b.cards([('REGRA DE TEMPO','Até 30 dias','O formulário mais recente pode ser aproveitado se ainda tiver até 30 dias na abertura da conversa.',PALE,GREEN),
               ('FORA DO PRAZO','Mais de 30 dias','Mesmo encontrado, não é aproveitado. O atendimento será completo, classificado como orgânico.',AMBER,'#9A590D')],y)
    y=b.note('Exemplo: dois formulários do mesmo número',
             'Meta preenchido há 12 dias e Google há 3 dias: o mais recente é o Google. Essa será a fonte, se o cadastro for aproveitável e o mapeamento Google estiver definido. Não misturar dados dos dois registros.',y,BLUE,TEAL)
    b.t('O prazo é contado desde o formulário, não desde a atualização feita depois pelo Funil. Exatamente 30 dias ainda está dentro da regra. Restrições de abertura de conversa já existentes continuam sendo respeitadas.',M,y,CW,10.7,MUTED)

    y=b.start('Quando o atendimento será completo', 'Para não interromper o contato, algumas situações recebem a classificação operacional “Orgânico”.')
    y=b.table(['O que aconteceu na consulta','Como o cliente será atendido'],[
        ['O número não foi encontrado.','Desde o início, com todas as coletas.'],
        ['O registro mais recente tem mais de 30 dias.','Desde o início, sem aproveitar o cadastro antigo.'],
        ['Falta nome, e-mail ou destino válido.','Desde o início, sem importar só parte dos dados.'],
        ['A consulta falhou ou não trouxe resultado confiável.','Desde o início; a falha fica registrada internamente.']],y,[CW*.52,CW*.48])
    y=b.note('“Orgânico” não é prova de ausência de anúncio',
             'Neste acordo, o rótulo também cobre erro de consulta, cadastro antigo ou retorno sem nova consulta. Por isso, a FireAds deve procurar o contato antes de cadastrar: <b>um lead classificado como orgânico também pode já existir no dashboard.</b>',y,AMBER,'#9A590D')
    y=b.bullets(['Se o registro mais recente estiver incompleto, o bot não escolhe um registro mais antigo apenas porque ele está mais completo.',
                 'Se uma fonte responder e outra falhar, a comparação entre Google e Meta não fica completa; o atendimento segue como orgânico.',
                 'Depois de definida a rota inicial, uma resposta atrasada do dashboard não reinicia a conversa nem altera sua origem automaticamente.'],y)
    b.t('O tratamento das opções ambíguas do Google continua pendente. A regra final para esse formulário será atualizada depois da resposta do Eduardo.',M,y,CW,10.7,MUTED)

    y=b.start('Do atendimento para o Funil', 'O lead segue quando chega ao ponto de encaminhamento previsto no atendimento, não apenas por ter enviado “olá”.')
    y=b.cards([('UNIDADE COM LINK','Recebe o link de reserva','Após a triagem e ao chegar à entrega do link, a conversa pode seguir ao Funil conforme as regras existentes.',WHITE,GREEN),
               ('UNIDADE SEM LINK','Escolhe um turno','Depois da triagem, escolhe um único turno e recebe o contato do comercial. O turno acompanha as observações.',WHITE,TEAL)],y)
    y=b.table(['Origem do atendimento FireAds','Canal no Funil'],[
        ['Google Ads','Google Ads - 113336'],['Meta Ads','Meta Ads - 113340'],['Orgânico','Orgânico - 113481']],y,[CW*.65,CW*.35])
    y=b.note('O Funil recebe o atendimento mais completo',
             'As observações incluem contato, para quem é o atendimento, idade, profissão, perguntas e respostas da triagem e turno quando aplicável. A origem FireAds será acrescentada. A reserva deve ser conferida pela equipe; chegar ao Funil não prova que ela foi efetivada.',y)
    y=b.bullets(['O chatbot envia ao Funil. A transferência do Funil para o dashboard será responsabilidade da integração da FireAds.',
                 'Se a pessoa abandonar antes do ponto de encaminhamento, não há garantia de que aquele atendimento chegue ao Funil ou, por esse caminho, ao dashboard.'],y)
    b.t('Satisfação, encerramento, regras de idade e lembretes permanecem no fluxo atual. Unidades sem FireAds mantêm o canal comercial já configurado.',M,y,CW,10.7,MUTED)

    y=b.start('Completar o cadastro sem duplicar', 'O dashboard reunirá quem veio de formulário e quem chegou por outras fontes, desde que o atendimento seja recebido do Funil.')
    y=b.cards([('JÁ EXISTE NO DASHBOARD','Atualizar o mesmo contato','Telefone e e-mail correspondem ao cadastro da mesma unidade: acrescentar as observações completas do Funil e o canal daquele atendimento.',PALE,GREEN),
               ('AINDA NÃO EXISTE','Cadastrar um novo contato','Após verificar que não há correspondência nem conflito, criar o cadastro com os dados disponíveis, observações completas e canal recebido.',BLUE,TEAL)],y)
    y=b.note('Encontrar um contato não significa ignorá-lo',
             'O formulário mostra o que a pessoa informou no início. O Funil traz o que foi conhecido durante o atendimento. A atualização deve enriquecer o cadastro existente, preservando a captação original e as anotações do comercial.',y)
    y=b.table(['Quem cuida de quê','Responsabilidade prevista'],[
        ['Chatbot / ESL Tech','Consultar na abertura elegível, atender e enviar ao Funil.'],
        ['FireAds','Ler o Funil, localizar o contato e cadastrar ou atualizar no dashboard sem duplicar.'],
        ['Flávio / equipe comercial','Usar os dados, conferir divergências e confirmar reserva/continuidade com o cliente.']],y,[CW*.36,CW*.64])
    y=b.note('Antes de ativar: duas respostas do Eduardo',
             '<b>1.</b> Como o Google identificará titular ou dependente.<br/><b>2.</b> Quais abas Meta serão consultadas, incluindo versões anteriores.<br/>A sincronização Funil → dashboard também precisa ser configurada e validada pela FireAds.',y,AMBER,'#9A590D')
    b.t('Material complementar: “Funil para dashboard: guia de cadastro e atualização sem duplicação”. Base: plano FireAds revisado em 07/10/2026 e decisões deste alinhamento. O rastreio de anúncios/posts da Meta é uma entrega futura separada.',M,y,CW,9.8,MUTED)
    b.done()
    return b.path


def support_guide():
    b=Book('apoio_fireads_funil_dashboard_sem_duplicacao.pdf','Funil para dashboard: guia de cadastro e atualização sem duplicação','GUIA DE APOIO À FIREADS',6)
    y=b.start('Atualizar quem já existe.<br/>Cadastrar quem ainda não está.',
              'Lógica de apoio para a FireAds trazer os atendimentos do Funil ao dashboard de Santo André, preservando a história do contato.')
    y=b.note('Regra de negócio combinada',
             'Ao receber um atendimento do Funil, procurar o contato <b>no dashboard da mesma unidade</b>. Mesmo telefone e e-mail: atualizar o registro existente. Sem correspondência e sem conflito: criar um novo. Em ambos, guardar as observações completas e o canal de venda do Funil.',y)
    y=b.lane([('Receber','Atendimento vindo do Funil.',PURPLE),('Procurar','Telefone e e-mail no dashboard.',TEAL),('Decidir','Atualizar, cadastrar ou conferir.',GREEN)],y)
    y=b.cards([('CONTATO EXISTENTE','Atualizar','Não ignorar o atendimento e não criar outra pessoa no painel.',PALE,GREEN),
               ('NÃO HÁ CORRESPONDÊNCIA','Cadastrar','Criar um contato com o conteúdo recebido, sem inventar dados ausentes.',BLUE,TEAL),
               ('HÁ DIVERGÊNCIA','Conferir','Separar para revisão e guardar o atendimento recebido; não unir no escuro.',AMBER,'#9A590D')],y,size=10.6)
    b.t('Este é um roteiro lógico para a equipe FireAds configurar sua integração. A regra de criar/atualizar foi definida pelo responsável; os cuidados de conferência e repetição apresentados aqui são recomendações para a implementação. O funcionamento do sistema da agência ainda não foi validado.',M,y,CW,10.8,MUTED)

    y=b.start('Como reconhecer o mesmo contato', 'A comparação deve usar dados do responsável que fala no WhatsApp, não o nome ou o e-mail de um dependente.')
    y=b.note('Primeiro, comparar no mesmo formato',
             'Padronizar país e DDD do telefone, retirando apenas a máscara de apresentação. No e-mail, retirar espaços acidentais e aplicar uma regra consistente de comparação. Não apagar “+apelidos”, pontos ou inventar dígitos para forçar uma coincidência.',y,BLUE,TEAL)
    y=b.table(['O que foi encontrado na mesma unidade','Ação recomendada'],[
        ['Mesmo telefone e mesmo e-mail válido, em um único contato.','Atualizar o contato existente.'],
        ['Mesmo telefone, mas e-mail diferente.','Conferir: pode ser correção de e-mail ou outra pessoa usando o número.'],
        ['Mesmo e-mail, mas telefone diferente.','Conferir: pode ser troca de número ou e-mail compartilhado.'],
        ['Telefone corresponde, mas algum e-mail está ausente.','Conferir ou usar vínculo já confirmado. Não criar automaticamente uma duplicata.'],
        ['Mais de um registro corresponde ao telefone/e-mail.','Escolher o cadastro principal após revisão; não atualizar todos nem criar outro.'],
        ['Nenhum telefone nem e-mail corresponde; número recebido é válido.','Criar contato. E-mail ausente pode ficar não informado.']],y,[CW*.54,CW*.46],10.5)
    b.t('Nome parecido sozinho não identifica uma pessoa. “Não informado”, “não tenho” e campo vazio não são e-mails para cruzamento. A normalização do nono dígito precisa de critério validado; não remover/adicionar em todo número indiscriminadamente.',M,y,CW,10.6,MUTED)

    y=b.start('O que atualizar e o que preservar', 'Atualizar o atendimento não deve apagar o formulário, a campanha original ou o trabalho do comercial.')
    y=b.table(['Informação','Tratamento recomendado no dashboard'],[
        ['Observações completas do Funil','Guardar o texto integral, com as quebras de linha, em uma área própria do atendimento. Não resumir nem cortar silenciosamente.'],
        ['Canal de venda recebido','Exibir como canal do atendimento mais recente. Google 113336; Meta 113340; Orgânico 113481.'],
        ['Dados de contato recebidos','Enriquecer após confirmar a identidade. Um primeiro nome enviado pelo bot não deve apagar um nome completo já válido.'],
        ['Formulário e campanha de captação','Preservar origem original, data do formulário e informações da campanha. Não trocar a captação antiga por “Orgânico” só por causa de um novo atendimento.'],
        ['Anotações e feedback do comercial','Manter separados das observações recebidas do Funil. Não sobrescrever notas, responsável, situação ou histórico comercial.'],
        ['Data de atualização','Registrar quando o atendimento chegou do Funil, em um campo separado da data do formulário.']],y,[CW*.34,CW*.66],10.6)
    y=b.note('Uma atualização não cria um formulário novo',
             'O bot usa a data original do formulário na regra de 30 dias. Se a FireAds substituir essa data pela data de atualização do Funil, um cadastro antigo parecerá recente indevidamente.',y,AMBER,'#9A590D')
    b.t('Se o painel tiver hoje apenas um campo “Canal”, combinar onde manter a captação original e onde mostrar o canal do atendimento. Os nomes finais dos campos pertencem à configuração da FireAds.',M,y,CW,10.6,MUTED)

    y=b.start('Repetir uma entrega não é um novo cliente', 'A mesma oportunidade pode chegar mais de uma vez. E a mesma pessoa pode ter outros atendimentos ao longo do tempo.')
    y=b.step('1','Identificar o contato e o atendimento',
             'O contato é localizado na unidade pelo telefone/e-mail. O atendimento deve ter uma referência estável do Funil, como o número da oportunidade, quando esse dado estiver disponível.',y)
    y=b.step('2','Se chegar a mesma oportunidade novamente',
             'Atualizar o mesmo atendimento, sem criar outra linha de contato e sem colar as mesmas observações duas vezes. Se nada mudou, reconhecer a entrega e manter o conteúdo.',y)
    y=b.step('3','Se for outro atendimento da mesma pessoa',
             'Manter um contato e acrescentar o novo atendimento ao histórico. O painel pode mostrar o resumo mais recente, preservando os anteriores. Isso é diferente de duplicar o contato.',y)
    y=b.step('4','Se duas entregas chegarem juntas',
             'A FireAds precisa controlar a procura e a criação em conjunto. Duas buscas simultâneas que não encontram um contato não podem criar dois cadastros para ele.',y)
    y=b.note('Separar formulários originais de retornos do Funil',
             'Leads criados ou atualizados pelo Funil devem ir ao painel geral/área de atendimento. Não devem virar entradas nas abas de formulário consultadas pelo bot. Atualizar o dashboard também não deve disparar um novo envio ao Funil, criando um ciclo de cópias.',y,BLUE,TEAL)
    b.t('Após uma falha de gravação, registrar a entrega como pendente e conferir antes de repetir uma inclusão. Não marcar como concluída uma atualização que não foi gravada. A referência da oportunidade e os controles exatos precisam ser confirmados na integração FireAds.',M,y,CW,10.6,MUTED)

    y=b.start('Exemplos para conferir a lógica', 'Nomes e situações abaixo são fictícios. Em todos os casos, a busca é feita na unidade correta.')
    y=b.cards([('CASO A','Ana veio do formulário Meta','Já está no dashboard. Conclui a triagem e chega ao Funil. Telefone e e-mail coincidem: atualizar o cadastro com o atendimento e canal Meta. Não criar outra Ana.',PALE,GREEN),
               ('CASO B','Bruno veio da fachada','Não há correspondência no dashboard. O atendimento chega ao Funil como orgânico: cadastrar Bruno com as observações completas e canal Orgânico.',BLUE,TEAL)],y)
    y=b.cards([('CASO C','Carla já existe, mas está “Orgânico”','Seu formulário é antigo ou houve falha na consulta do bot. Ainda assim, a FireAds encontra telefone e e-mail no painel: atualizar Carla, sem duplicar.',WHITE,GREEN),
               ('CASO D','Daniel mudou o e-mail','O número coincide, mas o e-mail não. Guardar o atendimento para conferência. Não criar outro Daniel nem trocar a identidade sem verificar.',AMBER,'#9A590D')],y)
    y=b.note('Caso E: o mesmo atendimento da Ana chega duas vezes',
             'A referência da oportunidade é a mesma. A segunda entrega não cria outro contato nem outro atendimento. Se houver conteúdo atualizado, modifica aquela ocorrência, sem repetir o texto no histórico.',y)
    b.note('Não usar o canal como prova de cadastro ausente',
           '“Orgânico” não significa automaticamente “novo no dashboard”. E não encontrar no dashboard não prova, sozinho, que a pessoa nunca veio de anúncio. Usar o canal enviado pelo Funil e verificar a existência de fato.',y,AMBER,'#9A590D')

    y=b.start('Roteiro de validação com a FireAds', 'Antes de ativar, testar os caminhos principais com contatos de teste identificados, sem depender apenas de “a requisição deu certo”.')
    y=b.table(['Teste','Como confirmar que funcionou'],[
        ['Contato de formulário chega do Funil.','O mesmo cadastro foi enriquecido; quantidade de contatos não aumentou.'],
        ['Contato sem correspondência chega do Funil.','Um único cadastro foi criado com observações completas e canal.'],
        ['A mesma oportunidade é entregue novamente.','Não há novo contato nem texto duplicado.'],
        ['Outra oportunidade da mesma pessoa chega.','Um contato, dois atendimentos identificáveis no histórico.'],
        ['Telefone/e-mail não coincidem completamente.','Caso fica para conferência, sem fusão nem criação automática.'],
        ['Há cadastros já duplicados no dashboard.','Caso vai para revisão; nenhuma terceira cópia é criada.'],
        ['Funil atualiza cadastro com formulário antigo.','Data do formulário e origem original permanecem preservadas.'],
        ['A gravação falha ou chegam duas entregas juntas.','A integração recupera a entrega sem perder conteúdo nem duplicar contato.']],y,[CW*.48,CW*.52],10.4)
    y=b.note('Pontos de configuração a confirmar pela agência',
             'Quais registros entram na busca; qual é o cadastro principal quando já há duplicatas; qual referência identifica a oportunidade; onde guardar o histórico e as observações completas; como encaminhar divergências para revisão.',y)
    b.t('Este guia orienta a sincronização feita pela FireAds. O chatbot continuará enviando apenas ao Funil. As pendências do formulário Google e das abas Meta seguem registradas no guia principal e no plano de integração. Base: decisões de 07/10/2026.',M,y,CW,10.4,MUTED)
    b.done()
    return b.path


if __name__ == '__main__':
    paths=[main_guide(),support_guide()]
    for p in paths:
        r=PdfReader(p)
        text='\n'.join(page.extract_text() or '' for page in r.pages)
        assert '\ufffd' not in text
        assert len(text)>5000
        print(json.dumps({'file':str(p),'pages':len(r.pages),'text_characters':len(text),'bytes':p.stat().st_size},ensure_ascii=False))
    (Path(__file__).parent/'layout_audit.json').write_text(json.dumps(AUDIT,ensure_ascii=False,indent=2),encoding='utf-8')
