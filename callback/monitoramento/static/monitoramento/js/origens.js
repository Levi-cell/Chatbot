/* Relatórios de origem: detalhes opcionais por atendimento, sem consulta externa. */
(() => {
  'use strict';
  const numero = new Intl.NumberFormat('pt-BR');
  const criar = (tag, classe = '', texto = '') => {
    const n = document.createElement(tag);
    n.className = classe;
    n.textContent = texto;
    return n;
  };
  const estado = {dados: null, periodo: null, selecao: null, abertos: {}, dialogo: null, ajuda: null};
  const chave = s => JSON.stringify([s.canal, s.anuncio === undefined ? false : s.anuncio]);

  function fecharAjuda() {
    if (!estado.ajuda) return;
    estado.ajuda.caixa.hidden = true;
    estado.ajuda.botao.setAttribute('aria-expanded', 'false');
    estado.ajuda.fixa = false;
  }

  function informacao(periodica) {
    const grupo = criar('span', 'ajuda-origem');
    const botao = criar('button', 'informacao-filtros', 'i');
    botao.type = 'button';
    botao.setAttribute('aria-label', 'Por que alguns atendimentos estão sem origem?');
    botao.setAttribute('aria-expanded', 'false');
    botao.setAttribute('aria-controls', 'explicacaoOrigem');
    botao.setAttribute('aria-describedby', 'explicacaoOrigem');
    const caixa = criar('div', 'explicacao-origem');
    caixa.id = 'explicacaoOrigem';
    caixa.hidden = true;
    caixa.setAttribute('role', 'tooltip');
    caixa.appendChild(criar('strong', '', 'Como identificamos a origem'));
    const textos = [
      'Se a primeira mensagem já contém os dados necessários, o chatbot começa o atendimento sem consultar a planilha. Isso evita uma espera desnecessária pela primeira resposta.',
      'Se faltar algum dado, consultamos a FireAds para tentar aproveitá-lo e evitar perguntas repetidas. Nessa leitura, também podemos identificar a origem.',
      periodica
        ? 'Quando a consulta inicial é dispensada, uma verificação programada a cada duas horas procura a origem dos novos atendimentos, mesmo que o cliente não tenha concluído a conversa. A origem também é conferida na preparação do envio ao dashboard.'
        : 'Quando a consulta inicial é dispensada, a origem pode ser identificada na preparação do envio ao dashboard, se o atendimento avançar até essa etapa.',
      '“Ainda sem origem” pode incluir verificações pendentes, falhas de consulta, canal não preenchido na planilha ou registros antigos sem informação suficiente. Não significa necessariamente abandono.',
      'Dados necessários: nome, e-mail e para quem é o atendimento. Nas unidades sem link de agendamento, também o turno.'
    ];
    textos.forEach(t => caixa.appendChild(criar('p', '', t)));
    const ajuda = {botao, caixa, fixa: false};
    estado.ajuda = ajuda;
    const abrir = () => {
      caixa.hidden = false; botao.setAttribute('aria-expanded', 'true');
      const r = botao.getBoundingClientRect();
      caixa.style.left = Math.max(16, Math.min(r.left, window.innerWidth - caixa.offsetWidth - 16)) + 'px';
      caixa.style.top = Math.max(16, Math.min(r.bottom + 8, window.innerHeight - caixa.offsetHeight - 16)) + 'px';
    };
    grupo.addEventListener('pointerenter', e => { if (e.pointerType === 'mouse') abrir(); });
    grupo.addEventListener('pointerleave', () => { if (!ajuda.fixa && !grupo.contains(document.activeElement)) fecharAjuda(); });
    botao.addEventListener('focus', abrir);
    grupo.addEventListener('focusout', e => { if (!ajuda.fixa && !grupo.contains(e.relatedTarget)) fecharAjuda(); });
    botao.addEventListener('click', () => { if (ajuda.fixa) fecharAjuda(); else { ajuda.fixa = true; abrir(); } });
    grupo.append(botao, caixa);
    return grupo;
  }

  function dialogo() {
    if (estado.dialogo) return estado.dialogo;
    const d = criar('dialog', 'perfis-origem-dialogo');
    d.setAttribute('aria-labelledby', 'tituloPerfisOrigem');
    const topo = criar('header', 'perfis-origem-topo');
    topo.appendChild(criar('span', 'sobrelinha', 'PERFIL DOS ATENDIMENTOS'));
    const fechar = criar('button', 'perfis-origem-fechar', 'Fechar ×');
    fechar.type = 'button';
    fechar.addEventListener('click', () => d.close());
    topo.appendChild(fechar);
    const conteudo = criar('div', 'perfis-origem-conteudo');
    d.append(topo, conteudo);
    d.addEventListener('click', e => {
      const r = d.getBoundingClientRect();
      if (e.target === d && (e.clientX < r.left || e.clientX > r.right || e.clientY < r.top || e.clientY > r.bottom)) d.close();
    });
    d.addEventListener('close', () => {
      document.body.classList.remove('perfis-origem-aberto');
      const anterior = estado.selecao;
      estado.selecao = null;
      const botao = [...document.querySelectorAll('[data-perfil-origem]')].find(b => b.dataset.perfilOrigem === chave(anterior || {}));
      botao?.focus({preventScroll: true});
    });
    document.body.appendChild(d);
    estado.dialogo = {elemento: d, conteudo};
    return estado.dialogo;
  }

  function atualizarDetalhe(mensagem) {
    if (!estado.selecao) return;
    const {elemento, conteudo} = dialogo(), s = estado.selecao;
    const canal = estado.dados?.canais.find(c => c.canal === s.canal);
    const item = s.anuncio === undefined ? canal : (s.canal === 'meta' ? estado.dados?.anuncios : estado.dados?.anuncios_google)?.find(a => a.anuncio === s.anuncio);
    const titulo = s.anuncio === undefined ? (canal?.rotulo || s.rotulo) : (s.anuncio || 'Anúncio não informado');
    const posicao = conteudo.scrollTop;
    conteudo.replaceChildren();
    const h = criar('h2', '', titulo); h.id = 'tituloPerfisOrigem';
    conteudo.append(h, criar('p', 'perfis-origem-contexto', (s.anuncio === undefined ? 'Canal de origem' : (canal?.rotulo || s.rotulo)) + ' · ' + (estado.periodo?.texto || '')));
    if (mensagem || !item) {
      conteudo.appendChild(criar('p', 'estado-vazio', mensagem || 'Nenhum atendimento desta seleção no período.'));
      return;
    }
    const totais = criar('div', 'perfis-origem-totais');
    [[item.atendimentos, 'atendimentos'], [item.funil, 'no Funil']].forEach(([valor, rotulo]) => {
      const item = criar('div'); item.append(criar('strong', '', numero.format(valor)), criar('span', '', rotulo)); totais.appendChild(item);
    });
    conteudo.appendChild(totais);
    if (!item.perfis?.length) conteudo.appendChild(criar('p', 'estado-vazio', 'Nenhum atendimento nesta seleção.'));
    else {
      const tabela = criar('table', 'tabela-origens tabela-perfis-origem');
      tabela.appendChild(cabecalho('Perfil'));
      const body = criar('tbody');
      item.perfis.forEach(p => {
        const tr = criar('tr'), th = criar('th', '', p.rotulo); th.scope = 'row';
        tr.append(th, criar('td', '', numero.format(p.atendimentos)), criar('td', 'valor-funil', numero.format(p.funil))); body.appendChild(tr);
      });
      tabela.appendChild(body); conteudo.appendChild(tabela);
    }
    conteudo.appendChild(criar('p', 'nota-faixa', 'Cada conversa conta uma vez. O perfil é da pessoa que fará o treinamento; para dependentes, usamos a idade do dependente. Faixas atuais, conforme os dados cadastrados. Informações ainda não coletadas aparecem separadamente.'));
    conteudo.appendChild(criar('p', 'nota-faixa', 'No Funil: envios confirmados desta mesma conversa no período. Não confirma agendamento ou venda.'));
    conteudo.scrollTop = posicao;
    elemento.setAttribute('aria-busy', 'false');
  }

  function botaoPerfil(selecao) {
    const b = criar('button', 'ver-perfis-origem', 'Ver perfis');
    b.type = 'button'; b.dataset.perfilOrigem = chave(selecao);
    b.setAttribute('aria-haspopup', 'dialog');
    b.setAttribute('aria-label', 'Ver perfis: ' + selecao.rotulo + (selecao.anuncio === undefined ? '' : ' · ' + (selecao.anuncio || 'Anúncio não informado')));
    b.addEventListener('click', () => {
      fecharAjuda(); estado.selecao = selecao; atualizarDetalhe();
      dialogo().elemento.showModal(); document.body.classList.add('perfis-origem-aberto');
    });
    return b;
  }

  function cabecalho(primeira) {
    const head = criar('thead'), tr = criar('tr');
    [primeira, 'Atendimentos', 'No Funil'].forEach(t => { const th = criar('th', '', t); th.scope = 'col'; tr.appendChild(th); });
    head.appendChild(tr); return head;
  }

  function grupoAnuncios(canal, nome, anuncios) {
    const grupo = criar('details', 'anuncios-origem anuncios-' + canal);
    grupo.open = Boolean(estado.abertos[canal]);
    grupo.addEventListener('toggle', () => { estado.abertos[canal] = grupo.open; });
    grupo.appendChild(criar('summary', '', 'Anúncios ' + nome + ' · ' + numero.format(anuncios.length) + ' grupos'));
    if (!anuncios.length) grupo.appendChild(criar('p', 'nota-faixa', 'Nenhum atendimento com essa origem identificada neste período.'));
    else {
      const tabela = criar('table', 'tabela-origens'); tabela.appendChild(cabecalho('Anúncio / referência'));
      const body = criar('tbody');
      anuncios.forEach(a => {
        const tr = criar('tr'), th = criar('th'); th.scope = 'row';
        th.append(criar('span', 'nome-origem', a.anuncio || 'Anúncio não informado'), botaoPerfil({canal, anuncio: a.anuncio, rotulo: canal === 'meta' ? 'Meta Ads' : 'Google Ads'}));
        tr.append(th, criar('td', '', numero.format(a.atendimentos)), criar('td', 'valor-funil', numero.format(a.funil))); body.appendChild(tr);
      });
      tabela.appendChild(body); grupo.appendChild(tabela);
    }
    return grupo;
  }

  function render(dados, periodo) {
    estado.dados = dados; estado.periodo = periodo;
    const secao = criar('section', 'cartao origens-fireads');
    secao.append(criar('h2', '', 'Origem dos atendimentos'), criar('p', 'nota-faixa', 'FireAds e orgânico · todas as conversas do período'));
    const resumo = criar('div', 'resumo-origens');
    [[dados.identificados, 'com origem identificada'], [dados.contatos_unicos, 'contatos únicos'], [dados.sem_origem, 'ainda sem origem']].forEach(([valor, rotulo], i) => {
      const item = criar('div'), linha = criar('div', 'numero-origem');
      linha.appendChild(criar('strong', '', numero.format(valor)));
      if (i === 2) linha.appendChild(informacao(dados.verificacao_periodica));
      item.append(linha, criar('span', '', rotulo)); resumo.appendChild(item);
    });
    secao.append(resumo, criar('p', 'legenda-origens', 'Barras: atendimentos identificados · Destaque: enviados ao Funil no período'));
    const tabela = criar('table', 'tabela-origens'); tabela.appendChild(cabecalho('Canal de origem'));
    const body = criar('tbody'), maximo = Math.max(1, ...dados.canais.map(c => c.atendimentos));
    dados.canais.forEach(c => {
      const tr = criar('tr'), th = criar('th'), nome = criar('div', 'nome-canal-origem'); th.scope = 'row';
      nome.append(criar('span', '', c.rotulo), botaoPerfil({canal: c.canal, rotulo: c.rotulo}));
      const barras = criar('div', 'barras-origem'); barras.setAttribute('aria-hidden', 'true');
      const barra = criar('span', 'barra-origem'), funil = criar('span', 'barra-funil');
      barra.style.width = (100*c.atendimentos/maximo) + '%'; funil.style.width = (100*c.funil/maximo) + '%';
      barras.append(barra, funil); th.append(nome, barras);
      tr.append(th, criar('td', '', numero.format(c.atendimentos)), criar('td', 'valor-funil', numero.format(c.funil))); body.appendChild(tr);
    });
    tabela.appendChild(body);
    secao.append(tabela, grupoAnuncios('meta', 'da Meta', dados.anuncios || []), grupoAnuncios('google', 'do Google', dados.anuncios_google || []),
      criar('p', 'nota-faixa', 'Cada conversa conta uma vez. Origem ainda não identificada fica fora dos canais. No Funil considera apenas envios confirmados no período. Estes dados representam atendimentos no chatbot, não todos os formulários da planilha.'));
    atualizarDetalhe();
    return secao;
  }

  document.addEventListener('keydown', e => { if (e.key === 'Escape') fecharAjuda(); });
  document.addEventListener('pointerdown', e => { if (estado.ajuda && !estado.ajuda.botao.parentElement.contains(e.target)) fecharAjuda(); });
  document.addEventListener('scroll', e => { if (estado.ajuda && !estado.ajuda.caixa.contains(e.target)) fecharAjuda(); }, true);
  window.MonitoramentoOrigens = {
    render,
    aguardar(periodo) { estado.periodo = {texto: periodo}; estado.dados = null; atualizarDetalhe('Atualizando o período…'); },
    falhou() { atualizarDetalhe('Não foi possível atualizar. Aguarde uma nova tentativa.'); },
    fechar() { fecharAjuda(); if (estado.dialogo?.elemento.open) estado.dialogo.elemento.close(); }
  };
})();
