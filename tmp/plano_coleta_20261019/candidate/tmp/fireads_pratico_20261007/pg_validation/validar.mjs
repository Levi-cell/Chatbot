import { PGlite } from '@electric-sql/pglite';
import fs from 'node:fs';
import assert from 'node:assert/strict';
const base=JSON.parse(fs.readFileSync(new URL('./base.json',import.meta.url),'utf8'));
const migration=fs.readFileSync(new URL('../candidate/deploy/migrations/20261007_fireads_chat_customizacao.sql',import.meta.url),'utf8');
const db=new PGlite();
let passo='base';
try {
  await db.exec('CREATE SCHEMA chatbot; CREATE TABLE chatbot.auth_user(id INTEGER PRIMARY KEY);');
  for (const sql of base.base) await db.exec(sql);
  for (const e of base.etapas) await db.query('INSERT INTO chatbot.etapa VALUES($1,$2,$3,$4,$5)',e);
  await db.exec(base.mapa);
  for (const t of base.transicoes) await db.query('INSERT INTO chatbot.etapa_transicao(id_etapa_origem,evento,id_etapa_destino) VALUES($1,$2,$3)',t);
  await db.exec(`INSERT INTO chatbot.unidade(nome_unidade,nome_agente,genero,cnpj,email_responsavel,telefone,numero_comercial,waba_id,phone_number_id)
    VALUES('Unidade teste','Dora','feminino','TESTE','responsavel@example.com','5511999990000','5511999990001','TESTE','TESTE');
    INSERT INTO chatbot.cliente(nome,waid_telefone,email) VALUES('Ana','5511999990002','ana@example.com');
    INSERT INTO chatbot.conversa(id_cliente,id_unidade,status_ativa) VALUES(1,1,FALSE),(1,1,TRUE);`);
  passo='migração';
  await db.exec(migration);
  assert.equal((await db.query('SELECT count(*)::int n FROM chatbot.chat')).rows[0].n,1);
  assert.equal((await db.query('SELECT count(*)::int n FROM chatbot.conversa WHERE id_chat=1')).rows[0].n,2);
  assert.equal((await db.query('SELECT nome_agente FROM chatbot.unidade_atendimento')).rows[0].nome_agente,'Dora');
  assert.equal((await db.query('SELECT count(*)::int n FROM chatbot.etapa_transicao')).rows[0].n,30);
  passo='reexecução';
  await db.exec(migration);
  passo='constraints';
  await assert.rejects(db.exec('INSERT INTO chatbot.chat(id_cliente,id_unidade) VALUES(1,1)'),/unique/);
  await assert.rejects(db.exec('DELETE FROM chatbot.atendimento_customizado WHERE id_unidade=1'),/customizado/);
  await db.exec('ROLLBACK');
  await db.exec(`INSERT INTO chatbot.integracao_fireads(id_unidade,url_dashbord) VALUES (1,'https://script.google.com/macros/s/teste/exec');`);
  await assert.rejects(db.exec('UPDATE chatbot.integracao_fireads SET integracao_ativa=TRUE'),/check constraint/);
  await db.exec('ROLLBACK');
  await db.exec('UPDATE chatbot.integracao_fireads SET contrato_validado=TRUE,integracao_ativa=TRUE');
  assert.ok((await db.query('SELECT ativada_em FROM chatbot.integracao_fireads')).rows[0].ativada_em);
  await assert.rejects(db.exec("UPDATE chatbot.conversa SET origem_fireads='meta' WHERE id_conversa=2"),/check constraint/);
  await db.exec('ROLLBACK');
  const probes=JSON.parse(fs.readFileSync(new URL('./probes.json',import.meta.url),'utf8'));
  for (const [i,p] of probes.entries()) {
    passo='consulta real '+i;
    let n=0;
    const sql=p.sql.replaceAll('%s',()=>'$'+(++n));
    await db.query(sql,p.params);
  }
  assert.equal((await db.query('SELECT status,attempt_count FROM chatbot.envios_dash')).rows[0].status,'sent');
  assert.equal((await db.query('SELECT status,attempt_count FROM chatbot.envios_dash')).rows[0].attempt_count,2);
  assert.equal((await db.query('SELECT lead_no_dash FROM chatbot.conversa WHERE id_conversa=2')).rows[0].lead_no_dash,true);
  assert.equal((await db.query("SELECT contexto_fireads->'dados_titular'->>'idade' idade FROM chatbot.conversa WHERE id_conversa=2")).rows[0].idade,'35');
  console.log('MIGRACAO_PGLITE_OK: cópia preservada, chat compartilhado, 30 transições, reexecução e constraints.');
  console.log('REPOSITORIOS_SQL_OK: importação, snapshot, início na profissão, Funil, reserva, retry e conclusão do dashboard.');
} catch(e) {
  console.error('Falha em '+passo+': '+e.message);
  process.exitCode=1;
} finally { await db.close(); }
