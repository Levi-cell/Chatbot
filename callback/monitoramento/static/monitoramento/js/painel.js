(() => {
  'use strict';
  const corpo=document.body, ids=id=>document.getElementById(id);
  const urls={conversas:corpo.dataset.urlConversas,mensagens:corpo.dataset.urlMensagens,relatorio:corpo.dataset.urlRelatorio,csv:corpo.dataset.urlCsv,login:corpo.dataset.urlLogin};
  const estado={secao:'conversas',periodo:'total',filtro:'todas',busca:'',conversas:[],selecionada:null,regras:{},carregandoConversas:false,recarregarConversas:false,carregandoRelatorio:false,recarregarRelatorio:false,sequenciaConversas:0,sequenciaRelatorio:0};
  const criar=(tag,classe='',texto='')=>{const n=document.createElement(tag);if(classe)n.className=classe;if(texto!==''&&texto!==null)n.textContent=texto;return n;};
  const numero=new Intl.NumberFormat('pt-BR'), data=new Intl.DateTimeFormat('pt-BR',{dateStyle:'short',timeZone:'America/Sao_Paulo'}), dia=new Intl.DateTimeFormat('pt-BR',{dateStyle:'long',timeZone:'America/Sao_Paulo'}), hora=new Intl.DateTimeFormat('pt-BR',{hour:'2-digit',minute:'2-digit',timeZone:'America/Sao_Paulo'}), curto=new Intl.DateTimeFormat('pt-BR',{day:'2-digit',month:'short',timeZone:'America/Sao_Paulo'});
  const cores=['#37663d','#5d568f','#a35b38','#44758a','#8a4f67','#4d7468','#7b683b'];
  async function json(url){const a=new AbortController(),t=setTimeout(()=>a.abort(),15000);try{const r=await fetch(url,{headers:{Accept:'application/json'},credentials:'same-origin',cache:'no-store',signal:a.signal});let d={};try{d=await r.json();}catch(_e){}if(r.status===401){location.assign(urls.login);throw new Error('Sessão expirada.');}if(!r.ok)throw new Error(d.erro||'Não foi possível carregar os dados.');return d;}finally{clearTimeout(t);}}
  const urlPeriodo=(base,periodo=estado.periodo)=>base+'?periodo='+encodeURIComponent(periodo);
  function status(texto,tipo=''){const n=ids('estadoAtualizacao');n.className='estado-atualizacao '+tipo;n.lastChild.textContent=texto;}
  function toast(texto){const n=ids('toast');n.textContent=texto;n.hidden=false;clearTimeout(toast.timer);toast.timer=setTimeout(()=>n.hidden=true,4500);}
  const iniciais=nome=>(nome||'?').split(/\s+/).slice(0,2).map(p=>p[0]||'').join('').toUpperCase();
  const cor=id=>cores[Math.abs(Number(id)||0)%cores.length];
  const perfil=p=>({dependente:'Dependente',menor:'Menor de 18',adulto:'Adulto',idoso:'60+'}[p]||p);
  const perfisResumidos={
    dependente_menor:{curto:'DP -18',completo:'Dependente menor de 18 anos'},
    dependente_adulto:{curto:'DP 18–59',completo:'Dependente de 18 a 59 anos'},
    dependente_idoso:{curto:'DP 60+',completo:'Dependente com 60 anos ou mais'},
    dependente:{curto:'DP',completo:'Dependente sem faixa etária informada'},
    menor:{curto:'-18',completo:'Titular menor de 18 anos'},
    adulto:{curto:'18–59',completo:'Titular de 18 a 59 anos'},
    idoso:{curto:'60+',completo:'Titular com 60 anos ou mais'},
  };
  function visivel(i){if(estado.filtro==='continuacoes'&&i.ids_conversa.length<2)return false;if(estado.filtro==='funil'&&!i.foi_funil)return false;if(estado.filtro==='avaliadas'&&!i.avaliada)return false;const b=estado.busca.trim().toLocaleLowerCase('pt-BR');return !b||[i.nome,i.contato,i.email,i.profissao,i.ultima_mensagem,...i.dependentes].filter(Boolean).join(' ').toLocaleLowerCase('pt-BR').includes(b);}
  function mini(pai,texto,classe=''){pai.appendChild(criar('span','mini-tag '+classe,texto));}
  function renderLista(){
    const lista=ids('listaConversas');
    const itens=estado.conversas.filter(visivel);
    lista.replaceChildren();

    if(!itens.length){
      lista.appendChild(criar('div','estado-vazio',estado.conversas.length?'Nenhum contato corresponde à pesquisa ou filtro.':'Nenhuma conversa neste período.'));
      return;
    }

    itens.forEach(item=>{
      const botao=criar('button','item-conversa');
      const avatar=criar('div','avatar',iniciais(item.nome));
      const corpo=criar('div','item-corpo');
      const cabecalho=criar('div','item-linha');
      const metadados=criar('span','item-metadados');
      const perfisResumo=criar('span','perfis-resumidos-item');
      const dataAtividade=criar('time','',item.ultima_atividade?data.format(new Date(item.ultima_atividade)):'—');

      botao.type='button';
      botao.dataset.cliente=String(item.id_cliente);
      if(estado.selecionada===item.id_cliente)botao.classList.add('ativo');
      avatar.style.background=cor(item.id_cliente);

      (item.perfis_resumidos||[]).forEach(chave=>{
        const classe=chave.replaceAll('_','-');
        const perfilAtual=perfisResumidos[chave]||{curto:chave,completo:chave};
        const etiqueta=criar('span','mini-tag perfil-resumido '+classe,perfilAtual.curto);
        etiqueta.title=perfilAtual.completo;
        etiqueta.setAttribute('aria-label',perfilAtual.completo);
        perfisResumo.appendChild(etiqueta);
      });
      if(perfisResumo.childElementCount)metadados.appendChild(perfisResumo);
      metadados.appendChild(dataAtividade);
      cabecalho.append(criar('strong','',item.nome),metadados);
      corpo.append(cabecalho,criar('div','item-previa',item.ultima_mensagem||'Sem conteúdo textual'));

      const tags=criar('div','mini-tags');
      if(item.ids_conversa.length>1)mini(tags,item.ids_conversa.length+' conversas');
      if(item.foi_funil)mini(tags,'Funil','funil');
      if(item.avaliada)mini(tags,'Avaliada','nota');
      corpo.appendChild(tags);
      botao.append(avatar,corpo);
      botao.addEventListener('click',()=>abrir(item.id_cliente));
      lista.appendChild(botao);
    });
  }
  function detalhes(i){ids('nomeContato').textContent=i.nome;ids('avatarContato').textContent=iniciais(i.nome);ids('avatarContato').style.background=cor(i.id_cliente);const r=[];if(i.contato)r.push('Contato: '+i.contato);if(i.profissao)r.push('Profissão: '+i.profissao);ids('detalhesContato').textContent=r.join(' • ')||'Dados ainda não informados';const tags=ids('tagsContato');tags.replaceChildren();i.perfis.forEach(p=>tags.appendChild(criar('span','tag-contato '+p,perfil(p))));if(i.foi_funil)tags.appendChild(criar('span','tag-contato funil','Funil'));const dl=criar('dl'),campos=[['Contato',i.contato||'Não informado'],['Profissão',i.profissao||'Não informada']];if(estado.regras.email_obrigatorio||i.email)campos.push(['E-mail',i.email||'Obrigatório · não informado']);if(i.dependentes.length)campos.push(['Dependente(s)',i.dependentes.join(', ')]);campos.push(['Conversas técnicas',i.ids_conversa.join(', ')]);campos.push(['Regras da unidade',[estado.regras.email_obrigatorio?'E-mail obrigatório':'E-mail opcional',politicaSuporte(estado.regras.idade_minima_suporte),estado.regras.bpa_ativo?'BPA ativo':'BPA inativo'].join(' · ')]);campos.forEach(([t,v])=>{const g=criar('div');g.append(criar('dt','',t),criar('dd','',v));dl.appendChild(g);});ids('painelDetalhes').replaceChildren(dl);}
  function marca(){const c=criar('div','marca-dagua');c.setAttribute('aria-hidden','true');const i=document.querySelector('.marca-app img').cloneNode();i.alt='';c.appendChild(i);return c;}
  function renderMensagens(ms,{manter=false}={}){const c=ids('mensagensChat'),final=c.scrollHeight-c.scrollTop-c.clientHeight<120,topo=c.scrollTop;c.replaceChildren(marca());let d='',conv=null;ms.forEach(m=>{const dt=new Date(m.data),nd=dia.format(dt);if(nd!==d){c.appendChild(criar('div','dia',nd));d=nd;}if(conv!==m.id_conversa){c.appendChild(criar('div','separador-conversa',(conv===null?'Início':'Continuação')+' do atendimento · conversa '+m.id_conversa));conv=m.id_conversa;}const l=criar('div','linha-mensagem '+(m.quem_enviou==='bot'?'bot':'cliente')),b=criar('div','bolha');if(m.tipo&&m.tipo!=='text')b.appendChild(criar('span','tipo-mensagem',m.tipo.replaceAll('_',' ')));b.appendChild(criar('div','texto-mensagem',m.texto));if(m.botoes?.length){const bs=criar('div','botoes-mensagem');m.botoes.forEach(x=>{const bt=criar('button','botao-mensagem',x);bt.type='button';bt.disabled=true;bt.setAttribute('aria-label',x+' (botão histórico)');bs.appendChild(bt);});b.appendChild(bs);}const mt=criar('div','meta-mensagem');mt.appendChild(criar('span','','Etapa '+(m.id_etapa??'—')+' · '+hora.format(dt)));if(m.quem_enviou==='bot')mt.appendChild(criar('span','ticks','✓✓'));b.appendChild(mt);l.appendChild(b);c.appendChild(l);});if(!ms.length)c.appendChild(criar('div','boas-vindas','Nenhuma mensagem visível no período.'));requestAnimationFrame(()=>{if(!manter||final)c.scrollTop=c.scrollHeight;else c.scrollTop=topo;});}
  async function abrir(idCliente,{silencioso=false}={}){const i=estado.conversas.find(c=>c.id_cliente===idCliente);if(!i)return;const periodo=estado.periodo;estado.selecionada=idCliente;renderLista();detalhes(i);ids('topoChat').hidden=false;document.querySelector('.app-conversas').classList.add('chat-aberto');const c=ids('mensagensChat');if(!silencioso)c.replaceChildren(marca(),criar('div','estado-vazio carregando','Carregando histórico…'));try{const d=await json(urls.mensagens+idCliente+'/?periodo='+encodeURIComponent(periodo));if(estado.selecionada===idCliente&&estado.periodo===periodo)renderMensagens(d.mensagens,{manter:silencioso});}catch(e){if(estado.periodo!==periodo)return;if(!silencioso)c.replaceChildren(marca(),criar('div','estado-vazio',e.message));else toast('Não foi possível atualizar a conversa agora.');}}
  async function carregarConversas(silencioso=false){if(estado.carregandoConversas){estado.recarregarConversas=true;return;}estado.carregandoConversas=true;const periodo=estado.periodo,seq=++estado.sequenciaConversas;if(estado.secao==='conversas')status('Atualizando…','atualizando');try{const d=await json(urlPeriodo(urls.conversas,periodo));if(seq!==estado.sequenciaConversas||periodo!==estado.periodo)return;const velha=estado.conversas.find(c=>c.id_cliente===estado.selecionada);estado.conversas=d.conversas;estado.regras=d.unidade.regras;ids('nomeUnidade').textContent=d.unidade.nome;ids('periodoConversas').textContent='Agente '+d.unidade.agente+' · '+d.periodo.texto;renderLista();const nova=estado.conversas.find(c=>c.id_cliente===estado.selecionada);if(nova&&(!silencioso||!velha||nova.ultima_mensagem_id!==velha.ultima_mensagem_id||nova.ultima_atividade!==velha.ultima_atividade))await abrir(nova.id_cliente,{silencioso});else if(!estado.selecionada&&matchMedia('(min-width:721px)').matches&&estado.conversas[0])await abrir(estado.conversas[0].id_cliente);if(estado.secao==='conversas')status('Atualizado agora');}catch(e){if(seq!==estado.sequenciaConversas||periodo!==estado.periodo)return;if(estado.secao==='conversas')status('Falha ao atualizar','erro');if(!silencioso)ids('listaConversas').replaceChildren(criar('div','estado-vazio',e.message));else toast(e.message);}finally{estado.carregandoConversas=false;if(estado.recarregarConversas){estado.recarregarConversas=false;void carregarConversas(true);}}}
  function tend(v){if(v==null)return['Histórico completo',''];if(v===0)return['Sem variação ante o período anterior',''];return[(v>0?'↑ ':'↓ ')+Math.abs(v).toLocaleString('pt-BR')+'% ante o período anterior',v>0?'positiva':'negativa'];}
  function kpi(rotulo,valor,v){const c=criar('article','cartao kpi'),t=tend(v);c.append(criar('span','rotulo',rotulo),criar('strong','',valor),criar('span','tendencia '+t[1],t[0]));return c;}
  function titulo(t,d,l=''){const h=criar('header','titulo-cartao'),x=criar('div');x.append(criar('h2','',t),criar('p','',d));h.appendChild(x);if(l)h.appendChild(criar('span','legenda',l));return h;}
  function atividade(ds){
    const componente=criar('div','grafico-atividade');
    if(!ds.length){
      componente.appendChild(criar('div','estado-vazio','Sem atividade no período.'));
      return componente;
    }

    const resumo=criar('p','grafico-resumo','Toque em uma barra para ver data, leads e mensagens.');
    resumo.setAttribute('aria-live','polite');
    const rolagem=criar('div','grafico-rolagem');
    const barras=criar('div','grafico-barras');
    const maximo=Math.max(1,...ds.flatMap(item=>[Number(item.leads)||0,Number(item.mensagens)||0]));

    ds.forEach((item,indice)=>{
      const leads=Number(item.leads)||0;
      const mensagens=Number(item.mensagens)||0;
      const dataCurta=curto.format(new Date(item.periodo));
      const descricao=dataCurta+': '+numero.format(leads)+' leads e '+numero.format(mensagens)+' mensagens';
      const coluna=criar('button','coluna-grafico');
      const barraLeads=criar('i');
      const barraMensagens=criar('i','barra-mensagens');

      coluna.type='button';
      coluna.title=descricao;
      coluna.setAttribute('aria-label',descricao);
      barraLeads.style.height=Math.max(2,leads/maximo*100)+'%';
      barraMensagens.style.height=Math.max(2,mensagens/maximo*100)+'%';
      coluna.append(barraLeads,barraMensagens);

      if(ds.length<35||indice%Math.ceil(ds.length/16)===0){
        coluna.appendChild(criar('span','rotulo-data',dataCurta));
      }

      const mostrarResumo=()=>{resumo.textContent=descricao;};
      coluna.addEventListener('click',mostrarResumo);
      coluna.addEventListener('focus',mostrarResumo);
      coluna.addEventListener('mouseenter',mostrarResumo);
      barras.appendChild(coluna);
    });

    rolagem.appendChild(barras);
    componente.append(resumo,rolagem);
    return componente;
  }
  function satisfacao(ds){const c=criar('article','cartao');c.appendChild(titulo('Satisfação','Distribuição das notas registradas.'));const b=criar('div','barras-satisfacao'),max=Math.max(1,...Object.values(ds).map(Number));[5,4,3,2,1].forEach(n=>{const q=Number(ds[String(n)]||0),l=criar('div','barra-linha'),tr=criar('div','trilho'),i=criar('i');i.style.width=q/max*100+'%';tr.appendChild(i);l.append(criar('span','',n+' ★'),tr,criar('strong','',String(q)));b.appendChild(l);});c.appendChild(b);return c;}
  function perfis(ds){
    const colunas=['Perfil','Leads','Conversas','Funil','Taxa'];
    const cartao=criar('article','cartao');
    const tabela=criar('table','tabela-perfis');
    const cabecalho=criar('thead');
    const linhaCabecalho=criar('tr');

    cartao.appendChild(titulo('Perfil dos atendimentos','Faixas atuais; dependentes a partir de '+ds.idade_minima_dependente+' anos.'));
    colunas.forEach(coluna=>linhaCabecalho.appendChild(criar('th','',coluna)));
    cabecalho.appendChild(linhaCabecalho);
    tabela.appendChild(cabecalho);

    const corpoTabela=criar('tbody');
    ds.linhas.forEach(item=>{
      const linha=criar('tr');
      const valores=[
        item.rotulo,
        item.leads,
        item.conversas,
        item.funil,
        item.taxa_funil==null?'—':item.taxa_funil.toLocaleString('pt-BR')+'%',
      ];

      valores.forEach((valor,indice)=>{
        const celula=criar('td','',String(valor));
        celula.dataset.rotulo=colunas[indice];
        linha.appendChild(celula);
      });
      corpoTabela.appendChild(linha);
    });

    tabela.appendChild(corpoTabela);
    cartao.appendChild(tabela);
    if(ds.sem_classificacao){
      cartao.appendChild(criar('p','tendencia',ds.sem_classificacao+' lead(s) sem classificação etária completa.'));
    }
    return cartao;
  }
  function etapas(ds){const c=criar('article','cartao');c.appendChild(titulo('Onde os atendimentos estão','Etapa atual da conversa mais recente de cada contato ativo no período.','22 etapas'));const lista=criar('div','etapas-lista'),max=Math.max(1,...ds.map(e=>Number(e.quantidade)));ds.forEach(e=>{const l=criar('div','etapa-linha'),tr=criar('div','trilho'),i=criar('i');i.style.width=Number(e.quantidade)/max*100+'%';tr.appendChild(i);l.append(criar('span','etapa-numero',String(e.id_etapa)),criar('span','etapa-nome',e.nome_etapa),tr,criar('strong','',String(e.quantidade)));lista.appendChild(l);});c.appendChild(lista);return c;}
  function exportacao(formato='google'){
    const essencial=formato==='essencial';
    const cartao=criar('article','cartao exportacao');
    const descricao=criar('div');
    const botoes=criar('div','botoes-download');
    const titulo=essencial?'Baixe os dados essenciais':'Leve os contatos para o Google Contatos';
    const explicacao=essencial
      ?'CSV com apenas Nome, E-mail e Telefone do período selecionado. O nome completo fica em uma coluna. Elegíveis possuem os três dados; campos ausentes ficam vazios no arquivo completo.'
      :'Arquivos no formato Google CSV. Elegíveis possuem nome, e-mail e telefone; campos ausentes ficam vazios no arquivo completo. Para mais de 3.000 contatos, escolha períodos menores antes de importar no Google.';

    descricao.append(criar('h2','',titulo),criar('p','',explicacao));
    [['Baixar todos os contatos','todos'],['Baixar apenas elegíveis','elegiveis']].forEach(([texto,tipo])=>{
      const link=criar('a','botao-download'+(tipo==='elegiveis'?' primario':''),texto);
      const parametros=new URLSearchParams({periodo:estado.periodo,tipo});
      if(essencial)parametros.set('formato','essencial');
      link.href=urls.csv+'?'+parametros;
      link.setAttribute('aria-label',texto+' — '+(essencial?'CSV essencial':'Google CSV'));
      botoes.appendChild(link);
    });
    cartao.append(descricao,botoes);
    return cartao;
  }
  function politicaSuporte(limite){
    return limite===null?'Encaminhamento por idade: desativado':'Encaminhamento ao comercial: '+limite+'+';
  }
  function encaminhamentos(d){
    if(!Number.isSafeInteger(d.encaminhados_comercial_por_idade)||d.encaminhados_comercial_por_idade<0){
      throw new Error('Não foi possível obter o total de encaminhamentos.');
    }
    const cartao=criar('article','cartao indicador-comercial');
    const descricao=criar('div');
    descricao.append(
      criar('h2','','Encaminhados ao comercial'),
      criar('p','','Leads únicos encaminhados por suporte de idade no período'),
      criar('p','politica-suporte',politicaSuporte(d.unidade.idade_minima_suporte)),
    );
    cartao.append(descricao,criar('strong','total-comercial',numero.format(d.encaminhados_comercial_por_idade)));
    return cartao;
  }
  function interpretar(m){const c=criar('article','cartao como-interpretar');c.appendChild(criar('h2','','Como interpretar os números'));const ul=criar('ul');['Lead é um contato único que enviou mensagem no período selecionado.','Funil é um envio confirmado no registro local; não confirma agendamento ou venda.','Encaminhados ao comercial conta leads únicos pelo encerramento por suporte de idade no período, inclusive históricos. Não confirma clique, atendimento humano, matrícula ou venda; não inclui o tratamento de 100+. A data considerada é a do encaminhamento, e não a da mensagem recebida.','A comparação usa a janela imediatamente anterior com a mesma duração. O histórico total não possui comparação.','A etapa mostra o estado atual da conversa mais recente de cada contato ativo no período; não reconstrói a etapa histórica daquele dia.','Participação em avaliações: '+(m.leads?Math.round((m.avaliacoes||0)/m.leads*1000)/10:0)+'% dos leads.'].forEach(x=>ul.appendChild(criar('li','',x)));c.appendChild(ul);return c;}
  function renderRelatorio(d){
    ids('periodoRelatorios').textContent=d.periodo.texto;
    const relatorio=ids('conteudoRelatorio');
    const metricasRelatorio=d.metricas;
    const tendencias=d.tendencias;
    const gradeKpis=criar('div','grade-kpis');
    const gradeRelatorio=criar('div','grade-relatorio');
    const cartaoAtividade=criar('article','cartao');
    const instrucaoGrafico=matchMedia('(hover: none)').matches
      ?'Toque nas barras para ver cada valor. Deslize para consultar outras datas.'
      :'Passe o cursor sobre as barras para ver cada valor.';

    relatorio.replaceChildren();
    gradeKpis.append(
      kpi('Leads em contato',numero.format(metricasRelatorio.leads||0),tendencias.leads),
      kpi('Mensagens',numero.format(metricasRelatorio.mensagens||0),tendencias.mensagens),
      kpi('Enviados ao funil',numero.format(metricasRelatorio.funil||0),tendencias.funil),
      kpi('Nota média',metricasRelatorio.nota_media==null?'—':Number(metricasRelatorio.nota_media).toLocaleString('pt-BR')+' / 5',tendencias.nota_media),
    );
    cartaoAtividade.append(
      titulo('Evolução da demanda',instrucaoGrafico,'Verde: leads · Lima: mensagens'),
      atividade(d.atividade),
    );
    gradeRelatorio.append(cartaoAtividade,satisfacao(d.satisfacao));
    relatorio.append(
      gradeKpis,
      encaminhamentos(d),
      gradeRelatorio,
      perfis(d.perfis),
      etapas(d.etapas),
      exportacao(),
      exportacao('essencial'),
      interpretar(metricasRelatorio),
    );
  }
  async function carregarRelatorio(silencioso=false){if(estado.carregandoRelatorio){estado.recarregarRelatorio=true;return;}estado.carregandoRelatorio=true;const periodo=estado.periodo,seq=++estado.sequenciaRelatorio;if(!silencioso)ids('conteudoRelatorio').replaceChildren(criar('div','cartao carregando-relatorio','Preparando os indicadores…'));if(estado.secao==='relatorios')status('Atualizando…','atualizando');try{const d=await json(urlPeriodo(urls.relatorio,periodo));if(seq!==estado.sequenciaRelatorio||periodo!==estado.periodo)return;renderRelatorio(d);if(estado.secao==='relatorios')status('Atualizado agora');}catch(e){if(seq!==estado.sequenciaRelatorio||periodo!==estado.periodo)return;if(estado.secao==='relatorios')status('Falha ao atualizar','erro');if(!silencioso)ids('conteudoRelatorio').replaceChildren(criar('div','cartao carregando-relatorio',e.message));else toast(e.message);}finally{estado.carregandoRelatorio=false;if(estado.recarregarRelatorio){estado.recarregarRelatorio=false;void carregarRelatorio(true);}}}
  function trocar(secao){estado.secao=secao;document.querySelectorAll('[data-secao]').forEach(b=>{const a=b.dataset.secao===secao;b.classList.toggle('ativo',a);b.setAttribute('aria-pressed',String(a));});ids('secaoConversas').hidden=secao!=='conversas';ids('secaoRelatorios').hidden=secao!=='relatorios';window.scrollTo({top:0});secao==='relatorios'?carregarRelatorio():carregarConversas(true);}
  document.querySelectorAll('[data-secao]').forEach(b=>b.addEventListener('click',()=>trocar(b.dataset.secao)));
  document.querySelectorAll('[data-periodo]').forEach(s=>s.addEventListener('change',()=>{estado.periodo=s.value;estado.selecionada=null;estado.sequenciaConversas++;estado.sequenciaRelatorio++;document.querySelectorAll('[data-periodo]').forEach(o=>o.value=s.value);estado.secao==='relatorios'?carregarRelatorio():carregarConversas();}));
  document.querySelectorAll('[data-filtro]').forEach(b=>b.addEventListener('click',()=>{estado.filtro=b.dataset.filtro;document.querySelectorAll('[data-filtro]').forEach(x=>x.classList.toggle('ativo',x===b));renderLista();}));
  ids('buscaConversas').addEventListener('input',e=>{estado.busca=e.target.value;renderLista();});
  ids('voltarConversas').addEventListener('click',()=>document.querySelector('.app-conversas').classList.remove('chat-aberto'));
  ids('alternarDetalhes').addEventListener('click',e=>{const a=e.currentTarget.getAttribute('aria-expanded')==='true';e.currentTarget.setAttribute('aria-expanded',String(!a));ids('painelDetalhes').hidden=a;});
  ids('mensagensChat').addEventListener('scroll',()=>{const c=ids('mensagensChat');ids('irFinal').hidden=c.scrollHeight-c.scrollTop-c.clientHeight<150;});
  ids('irFinal').addEventListener('click',()=>ids('mensagensChat').scrollTo({top:ids('mensagensChat').scrollHeight,behavior:'smooth'}));
  document.addEventListener('visibilitychange',()=>{if(!document.hidden)(estado.secao==='conversas'?carregarConversas(true):carregarRelatorio(true));});
  setInterval(()=>{if(!document.hidden&&estado.secao==='conversas')carregarConversas(true);},10000);
  setInterval(()=>{if(!document.hidden&&estado.secao==='relatorios')carregarRelatorio(true);},30000);
  // O espaço do chat acompanha o cabeçalho real, inclusive após girar o celular.
  function ajustarAlturaPainel(){
    const raiz=document.documentElement;
    raiz.style.setProperty('--altura-cabecalho',document.querySelector('.cabecalho-app').offsetHeight+'px');
    raiz.style.setProperty('--altura-aviso',document.querySelector('.faixa-consulta').offsetHeight+'px');
  }
  ajustarAlturaPainel();
  if('ResizeObserver' in window){
    const observador=new ResizeObserver(ajustarAlturaPainel);
    observador.observe(document.querySelector('.cabecalho-app'));
    observador.observe(document.querySelector('.faixa-consulta'));
  }else{
    window.addEventListener('resize',ajustarAlturaPainel);
  }
  carregarConversas();
})();

