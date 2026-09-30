/* Fonte da tela: endpoints privados do banco. A navegação nunca coleta na Meta. */
(() => {
  'use strict';
  const elemento = id => document.getElementById(id);
  const urls = document.body.dataset;
  const numero = new Intl.NumberFormat('pt-BR');
  const moeda = new Intl.NumberFormat('pt-BR', {style: 'currency', currency: 'BRL'});
  const estado = {ativo: false, mes: null, seguirMesAtual: true, sequencia: 0, controlador: null, dados: null, status: null, baixando: false};

  function criar(tag, classe, texto) {
    const item = document.createElement(tag);
    if (classe) item.className = classe;
    if (texto !== undefined) item.textContent = texto;
    return item;
  }

  function aviso(texto) {
    const caixa = elemento('avisoConsumo');
    caixa.textContent = texto;
    caixa.hidden = !texto;
  }

  function horario(registro) {
    return new Intl.DateTimeFormat('pt-BR', {
      dateStyle: 'short', timeStyle: 'short', timeZone: registro.fuso_horario,
    }).format(new Date(registro.ultimo_sucesso_em));
  }

  function atualizarBotoes() {
    elemento('pdfConsumoMes').disabled = estado.baixando || !estado.dados?.selecionado;
    elemento('pdfConsumoTodos').disabled = estado.baixando || !estado.dados?.historico?.length;
  }

  function cartao(titulo, valor, descricao, destaque = false) {
    const item = criar('article', 'consumo-cartao' + (destaque ? ' destaque' : ''));
    item.append(criar('h2', '', titulo), criar('strong', 'consumo-valor', numero.format(valor)), criar('p', '', descricao));
    return item;
  }

  function montarOpcoesMeses(meses) {
    const agruparPorAno = new Set(meses.map(mes => mes.chave.slice(0, 4))).size > 1;
    const grupos = new Map();
    const opcoes = [];
    // A API fornece a ordem cronológica decrescente. Os grupos só organizam a
    // lista nativa, preservando rolagem, teclado e o mês atual como primeira opção.
    for (const mes of meses) {
      const opcao = criar('option', '', mes.rotulo + (mes.atual ? ' — mês atual' : ''));
      opcao.value = mes.chave;
      if (!agruparPorAno) {
        opcoes.push(opcao);
        continue;
      }
      const ano = mes.chave.slice(0, 4);
      if (!grupos.has(ano)) {
        const grupo = criar('optgroup');
        grupo.label = ano;
        grupos.set(ano, grupo);
        opcoes.push(grupo);
      }
      grupos.get(ano).append(opcao);
    }
    return opcoes;
  }

  function renderizar(dados) {
    const seletor = elemento('mesConsumo');
    const assinatura = JSON.stringify(dados.meses);
    if (seletor.dataset.assinatura !== assinatura) {
      seletor.replaceChildren(...montarOpcoesMeses(dados.meses));
      seletor.dataset.assinatura = assinatura;
    }
    seletor.disabled = !dados.meses.length;
    seletor.value = dados.mes_selecionado || '';
    estado.mes = dados.mes_selecionado;
    estado.dados = dados;
    aviso(dados.aviso);
    atualizarBotoes();
    const conteudo = elemento('conteudoConsumo');
    const registro = dados.selecionado;
    const assinaturaConteudo = JSON.stringify([registro, dados.historico, dados.pre_lancamento]);
    if (estado.ativo) estado.status(dados.pre_lancamento ? 'Disponível em 1º de outubro' : registro ? `Coleta: ${horario(registro)}` : 'Aguardando coleta', dados.coleta_com_falha ? 'erro' : '');
    // Consultas sem mudança não recriam a tabela nem deslocam foco e rolagem.
    if (conteudo.dataset.assinatura === assinaturaConteudo) return;
    const areaAnterior = conteudo.querySelector('.consumo-tabela-area');
    const rolagemAnterior = areaAnterior?.scrollLeft || 0;
    const tabelaComFoco = areaAnterior === document.activeElement;
    const componentes = [];
    if (!registro) {
      const texto = dados.pre_lancamento
        ? 'O acompanhamento começa em outubro de 2026. Os indicadores ficarão disponíveis após a primeira coleta desse mês.'
        : 'Os indicadores aparecerão após a primeira coleta válida. Você pode consultar os meses anteriores disponíveis.';
      componentes.push(criar('div', 'cartao consumo-vazio', texto));
    } else {
      const contexto = criar('div', 'consumo-contexto');
      const datas = criar('div');
      datas.append(criar('p', '', registro.periodo_texto), criar('p', '', `Última coleta: ${horario(registro)} · ${registro.fuso_horario}`));
      contexto.append(datas, criar('span', 'consumo-estado ' + registro.status_apuracao, registro.status_rotulo));
      const cartoes = criar('div', 'consumo-cartoes');
      const janela = cartao('Gratuitas no período de 72 horas', registro.qtd_janela_gratuita, 'Não gastam sua reserva mensal de mensagens gratuitas.');
      const reserva = cartao('Reserva gratuita restante', registro.franquia_restante,
        `${numero.format(registro.qtd_franquia_consumida)} utilizadas de ${numero.format(registro.franquia_meta_mensal)} no mês.`, true);
      const progresso = criar('progress');
      progresso.max = registro.franquia_meta_mensal || 1;
      progresso.value = registro.qtd_franquia_consumida;
      progresso.setAttribute('aria-label', 'Mensagens utilizadas da reserva gratuita da Meta');
      reserva.append(progresso);
      const cobradas = cartao('Cobradas pela Meta', registro.qtd_cobradas_meta, 'Veja abaixo como essa quantidade é dividida.');
      const reparticao = criar('div', 'consumo-reparticao');
      for (const [rotulo, valor] of [['A ESL Tech assume', registro.assumidas_esl], ['Excedentes da unidade', registro.excedentes_unidade]]) {
        const linha = criar('div');
        linha.append(criar('span', '', rotulo), criar('strong', '', numero.format(valor)));
        reparticao.append(linha);
      }
      cobradas.append(reparticao);
      cartoes.append(janela, reserva, cobradas);
      const tarifa = new Intl.NumberFormat('pt-BR', {minimumFractionDigits: 3, maximumFractionDigits: 6}).format(Number(registro.tarifa_referencia_brl));
      const referencia = criar('p', 'consumo-referencia',
        `Referência para o Brasil: R$ ${tarifa}/mensagem de serviço. Excedente nessa referência: ${moeda.format(Number(registro.valor_referencia_excedente))}. ` +
        `Vigência: ${registro.tarifa_vigencia.split('-').reverse().join('/')}. Sujeita a alterações da Meta; não é um valor de fatura.`);
      const distribuicao = criar('article', 'consumo-distribuicao');
      distribuicao.append(criar('h2', '', `${numero.format(registro.total_mensagens)} mensagens entregues`),
        criar('p', 'consumo-nota', 'Distribuição do mês. A cobertura ESL já está incluída nas mensagens cobradas pela Meta.'));
      const barra = criar('div', 'consumo-barra-total');
      barra.setAttribute('aria-hidden', 'true');
      const legenda = criar('div', 'consumo-legenda');
      for (const [rotulo, valor, classe] of [
        ['Janela gratuita', registro.qtd_janela_gratuita, 'consumo-janela'],
        ['Reserva gratuita utilizada', registro.qtd_franquia_consumida, 'consumo-franquia'],
        ['Cobradas Meta', registro.qtd_cobradas_meta, 'consumo-cobradas'],
      ]) {
        const trecho = criar('span', classe);
        trecho.style.width = `${registro.total_mensagens ? valor * 100 / registro.total_mensagens : 0}%`;
        barra.append(trecho);
        const item = criar('span');
        item.append(criar('i', classe), criar('span', '', `${rotulo}: ${numero.format(valor)}`));
        legenda.append(item);
      }
      distribuicao.append(barra, legenda);
      componentes.push(contexto, cartoes, referencia, distribuicao);
    }
    if (dados.historico.length) componentes.push(tabelaHistorico(dados.historico));
    conteudo.replaceChildren(...componentes);
    conteudo.dataset.assinatura = assinaturaConteudo;
    const novaArea = conteudo.querySelector('.consumo-tabela-area');
    if (novaArea) {
      novaArea.scrollLeft = rolagemAnterior;
      if (tabelaComFoco) novaArea.focus({preventScroll: true});
    }
  }

  function tabelaHistorico(registros) {
    const bloco = criar('article', 'consumo-historico');
    bloco.append(criar('h2', '', 'Histórico por mês'));
    const area = criar('div', 'consumo-tabela-area');
    area.tabIndex = 0;
    area.setAttribute('aria-label', 'Histórico de consumo; role horizontalmente para ver todas as colunas');
    const tabela = criar('table', 'consumo-tabela');
    tabela.append(criar('caption', '', 'O saldo restante de meses anteriores não acumula. Cada mês é independente.'));
    const cabecalho = criar('thead');
    const linha = criar('tr');
    for (const titulo of ['Mês', 'Janela gratuita', 'Reserva usada', 'Reserva restante', 'Cobradas Meta', 'ESL assume', 'Excedentes', 'Situação', 'Última coleta']) {
      const celula = criar('th', '', titulo);
      celula.scope = 'col';
      linha.append(celula);
    }
    cabecalho.append(linha);
    const corpo = criar('tbody');
    for (const registro of registros) {
      const item = criar('tr');
      item.append(criar('td', '', registro.rotulo));
      for (const campo of ['qtd_janela_gratuita', 'qtd_franquia_consumida', 'franquia_restante', 'qtd_cobradas_meta', 'assumidas_esl', 'excedentes_unidade']) item.append(criar('td', '', numero.format(registro[campo])));
      const situacao = criar('td');
      situacao.append(criar('span', 'consumo-estado ' + registro.status_apuracao, registro.status_rotulo));
      item.append(situacao, criar('td', '', horario(registro)));
      corpo.append(item);
    }
    tabela.append(cabecalho, corpo);
    area.append(tabela);
    bloco.append(area);
    return bloco;
  }

  async function carregar({silencioso = false} = {}) {
    if (!estado.ativo) return;
    if (estado.controlador && silencioso) return;
    estado.controlador?.abort();
    const controlador = new AbortController();
    estado.controlador = controlador;
    const sequencia = ++estado.sequencia;
    const prazo = setTimeout(() => controlador.abort(), 15000);
    elemento('conteudoConsumo').setAttribute('aria-busy', 'true');
    try {
      const url = new URL(urls.urlConsumo, location.origin);
      // A seleção automática acompanha a virada do mês; uma escolha histórica
      // explícita permanece no período escolhido durante a atualização da tela.
      if (estado.mes && !estado.seguirMesAtual) url.searchParams.set('mes', estado.mes);
      const resposta = await fetch(url, {signal: controlador.signal, credentials: 'same-origin', cache: 'no-store'});
      if (resposta.status === 401) { location.assign(urls.urlLogin); return; }
      const dados = await resposta.json();
      if (!resposta.ok) throw new Error(dados.erro || 'Não foi possível consultar o consumo.');
      if (sequencia === estado.sequencia) renderizar(dados);
    } catch (erro) {
      if (sequencia !== estado.sequencia || !estado.ativo) return;
      aviso(erro.name === 'AbortError' ? 'A consulta demorou mais que o esperado. Tentaremos novamente.' : erro.message);
      estado.status('Falha ao consultar consumo', 'erro');
    } finally {
      clearTimeout(prazo);
      if (sequencia === estado.sequencia) {
        estado.controlador = null;
        elemento('conteudoConsumo').setAttribute('aria-busy', 'false');
      }
    }
  }

  async function baixarPDF(escopo, botao) {
    if (estado.baixando) return;
    estado.baixando = true;
    atualizarBotoes();
    const texto = botao.textContent;
    botao.textContent = 'Preparando PDF…';
    const mes = estado.mes;
    const controlador = new AbortController();
    const prazo = setTimeout(() => controlador.abort(), 30000);
    try {
      const url = new URL(urls.urlConsumoPdf, location.origin);
      url.searchParams.set('escopo', escopo);
      if (escopo === 'mes') url.searchParams.set('mes', mes);
      const resposta = await fetch(url, {credentials: 'same-origin', cache: 'no-store', signal: controlador.signal});
      if (resposta.status === 401) { location.assign(urls.urlLogin); return; }
      if (!resposta.ok) {
        const dados = await resposta.json();
        throw new Error(dados.erro || 'Não foi possível baixar o relatório.');
      }
      if (!resposta.headers.get('Content-Type')?.includes('application/pdf')) throw new Error('O relatório não ficou disponível. Tente novamente.');
      const endereco = URL.createObjectURL(await resposta.blob());
      const link = criar('a');
      link.href = endereco;
      link.download = `consumo-${escopo === 'todos' ? 'todos-os-meses' : mes}.pdf`;
      document.body.append(link);
      link.click();
      link.remove();
      setTimeout(() => URL.revokeObjectURL(endereco), 30000);
    } catch (erro) {
      aviso(erro.name === 'AbortError' ? 'O relatório demorou mais que o esperado. Tente novamente.' : erro.message);
    } finally {
      clearTimeout(prazo);
      estado.baixando = false;
      botao.textContent = texto;
      atualizarBotoes();
    }
  }

  elemento('mesConsumo').addEventListener('change', evento => {
    estado.seguirMesAtual = Boolean(estado.dados?.pre_lancamento) || evento.target.value === estado.dados?.mes_atual;
    estado.mes = evento.target.value;
    // Ao escolher outro mês, os dados antigos não podem parecer pertencer à nova seleção.
    estado.dados = null;
    delete elemento('conteudoConsumo').dataset.assinatura;
    atualizarBotoes();
    estado.status('Consultando consumo…', 'atualizando');
    elemento('conteudoConsumo').replaceChildren(criar('div', 'cartao consumo-vazio', 'Carregando o mês selecionado…'));
    carregar();
  });
  elemento('pdfConsumoMes').addEventListener('click', evento => baixarPDF('mes', evento.currentTarget));
  elemento('pdfConsumoTodos').addEventListener('click', evento => baixarPDF('todos', evento.currentTarget));
  setInterval(() => { if (estado.ativo && !document.hidden) carregar({silencioso: true}); }, 30000);

  window.ConsumoPainel = {
    ativar(status) {
      estado.ativo = true;
      estado.status = status;
      const registro = estado.dados?.selecionado;
      status(registro ? `Coleta: ${horario(registro)}` : 'Consultando consumo…', registro ? '' : 'atualizando');
      carregar({silencioso: true});
    },
    desativar() { estado.ativo = false; estado.sequencia++; estado.controlador?.abort(); estado.controlador = null; },
    atualizar() { carregar({silencioso: true}); },
  };
})();
