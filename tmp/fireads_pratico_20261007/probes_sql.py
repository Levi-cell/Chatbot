"""Extrai SQL real dos repositórios candidatos para executá-lo no PostgreSQL WASM."""
import sys,json
from pathlib import Path
from datetime import datetime,timezone
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'candidate'))
import tests.unit
from tests.helpers import FakeCursor
from core.repositories.fireads import consulta,envios
from core.repositories.funil.leads import buscar_dados_lead_funil
from core.repositories.atendimento.conversas import inicializar_conversa_resposta_bot
from core.integrations.funil.oportunidades import montar_payload_oportunidade
from psycopg.types.json import Jsonb
sqls=[]
class Cursor(FakeCursor):
    def execute(self,sql,params=None):
        sqls.append({'sql':sql,'params':list(params or [])})
        super().execute(sql,params)
def execute(sql):sqls.append({'sql':sql,'params':[]})
abertura=dict(id_chat=1,id_cliente=1,id_unidade=1,id_integracao=1)
consulta.buscar_abertura(2,Cursor(fetchone_result=(1,1,1,None,None,None,1,'x','g','m',None,True)))
consulta.reservar_consulta(abertura,2,Cursor(fetchone_result=(1,)))
dec=consulta.concluir_consulta(abertura,2,1,dict(resultado='importado',origem='google',status_dependente=False,dados_titular={'nome':'Ana','email':'ana@example.com','resultado_email':'email_valido'}),Cursor())
inicializar_conversa_resposta_bot(2,4,datetime.now(timezone.utc),Cursor())
execute("UPDATE chatbot.cliente SET idade=35 WHERE id_cliente=1;")
consulta.guardar_coletas({'contexto_fireads':dec,'id_cliente':1,'id_conversa':2},{'destino_dado':'cliente'},Cursor(fetchone_result=('Ana',35,'ana@example.com')))
execute("UPDATE chatbot.conversa SET id_etapa_atual=19,turno='tarde',profissao='Professor' WHERE id_conversa=2")
execute("INSERT INTO chatbot.integracao_funil_unidade(id_unidade,nome_widget,codigo_widget,link_api_carrossel,codigo_canal_venda) VALUES (1,'teste','teste','https://example.com','113340')")
execute("INSERT INTO chatbot.respostas_desafios(id_conversa,id_etapa,resposta) SELECT 2,s,'Nunca' FROM generate_series(12,17) s")
buscar_dados_lead_funil(2,Cursor())
dec['dados_titular']['idade']=35
dados=dict(id_conversa=2,id_unidade=1,nome_unidade='Unidade teste',status_dependente=False,nome_cliente='Ana',telefone_cliente='5511999990002',email_cliente='ana@example.com',idade_cliente=35,profissao='Professor',origem_fireads='google',contexto_fireads=dec,resultado_email_fireads='email_valido',turno='tarde',link_agendamento=None,triagem_respostas=[{'id_etapa':i,'resposta':'Nunca'} for i in range(12,18)])
payload=montar_payload_oportunidade(dados)
class CongelarCursor(Cursor):
    n=0
    def fetchone(self):
        self.n+=1
        if self.n==1:return (1,'https://script.google.com/macros/s/teste/exec','LEADS GERAL - Feedback')
        return ({'payload_funil':payload,'canal':'113336','url_funil':'https://example.com'},)
envios.congelar(dados,payload,{'link_api_carrossel':'https://example.com'},CongelarCursor())
execute('UPDATE chatbot.conversa SET lead_no_funil=TRUE WHERE id_conversa=2')
envios.reservar(Cursor())
envio=dict(id=1,conversa=2,integracao=1,tentativa=1)
envios.conferir_posse(envio,Cursor(fetchone_result=(1,)))
envios.reagendar(envio,ValueError('teste'),Cursor())
execute("UPDATE chatbot.envios_dash SET next_attempt_at=clock_timestamp()-INTERVAL '1 minute' WHERE id_envio_dash=1")
envios.reservar(Cursor())
envio['tentativa']=2
envios.concluir(envio,{'success':True},Cursor(fetchone_result=(2,)))
def encode(v):
    if isinstance(v,Jsonb):return v.obj
    if isinstance(v,datetime):return v.isoformat()
    raise TypeError(type(v).__name__)
(ROOT/'pg_validation/probes.json').write_text(json.dumps(sqls,default=encode,ensure_ascii=False),encoding='utf-8')
print(len(sqls),'consultas extraídas')
