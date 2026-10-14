# Contexto do ciclo de mensagem na V2

Este documento registra uma melhoria arquitetural desejada para a V2: trocar
parte dos dicionarios grandes do worker por objetos explicitos de contexto.

Na V1, o worker usa estruturas como:

```text
contexto_banco
contexto_historico
contexto_envio
contexto_final
estado_ciclo
```

Esses dicionarios funcionam, mas ficam cada vez mais complexos conforme novas
etapas e novas regras de transicao aparecem.

## Problema atual da V1

O fluxo da V1 e correto, mas a leitura exige lembrar de onde cada chave nasceu.

Exemplo:

```text
contexto_historico["id_etapa_atual"]
contexto_envio["id_etapa_resultante"]
contexto_envio["tratamento"]
contexto_envio["primeiro_nome_cliente"]
```

Essas chaves representam coisas diferentes:

```text
id_etapa_atual      -> etapa persistida antes da resposta atual
id_etapa_resultante -> destino decidido pelo sender neste ciclo
tratamento          -> resposta de tratamento, sem avancar etapa
primeiro_nome       -> dado especifico capturado na etapa 1
```

O risco nao e necessariamente bug de execucao, mas perda de legibilidade. A
regra fica certa, porem exige muito contexto mental.

## Ideia para a V2

Criar uma classe, ou conjunto de dataclasses, para representar o ciclo de uma
mensagem.

Nome sugerido:

```text
CicloMensagem
```

Alternativas:

```text
ContextoCiclo
ContextoMensagem
ProcessamentoMensagem
```

O nome `CicloMensagem` e bom porque deixa claro que o objeto vive apenas durante
um ciclo do worker.

## Estrutura sugerida

Exemplo conceitual:

```python
from dataclasses import dataclass


@dataclass
class MensagemFila:
    id_mensagem: int
    cliente_telefone: str
    id_phone_unidade: str
    conteudo_texto: str | None
    tipo_mensagem: str
    retry_count: int


@dataclass
class ConversaContexto:
    id_conversa: int
    id_cliente: int
    id_unidade: int
    id_etapa_atual: int | None
    last_message_from: str | None
    estado: str


@dataclass
class HistoricoContexto:
    id_etapa_cliente: int
    id_etapa_origem_transicao: int
    transicoes_permitidas: dict[str, int]
    mensagem_cliente_inserida: bool
    resposta_bot_para_mensagem_atual: dict | None


@dataclass
class EnvioContexto:
    enviou: bool
    resposta_ja_existia: bool
    id_etapa_origem_transicao: int | None
    evento_transicao: str | None
    id_etapa_resultante: int
    id_hash_msg_bot: str | None
    tratamento: bool = False
    tipo_tratamento: str | None = None
    primeiro_nome_cliente: str | None = None


@dataclass
class CicloMensagem:
    fila: MensagemFila
    conversa: ConversaContexto
    historico: HistoricoContexto | None = None
    envio: EnvioContexto | None = None

    @property
    def etapa_origem(self):
        return self.conversa.id_etapa_atual

    @property
    def etapa_destino(self):
        if not self.envio:
            return None
        return self.envio.id_etapa_resultante

    def esta_na_transicao(self, origem, destino):
        return self.etapa_origem == origem and self.etapa_destino == destino
```

Com isso, a regra da ponte etapa 1 para etapa 2 ficaria mais legivel:

```python
if ciclo.esta_na_transicao(1, 2) and not ciclo.envio.tratamento:
    salvar_nome_cliente(ciclo)
```

## Beneficio semantico

Na V1, a regra fica assim:

```python
etapa_origem = contexto_historico.get("id_etapa_atual")
etapa_destino = contexto_envio.get("id_etapa_resultante")
```

Na V2, a mesma ideia pode ficar assim:

```python
ciclo.etapa_origem
ciclo.etapa_destino
ciclo.esta_na_transicao(1, 2)
```

Isso deixa explicito que o sistema esta comparando uma transicao, e nao uma
etapa isolada.

## O que preservar da V1

A V2 deve preservar estas garantias:

1. A mensagem do cliente deve ser commitada antes do envio da resposta do bot.
2. A resposta do bot, a atualizacao da conversa e os efeitos especificos da
   etapa devem ficar na mesma transacao final.
3. A fila so deve virar `sent` depois da transacao final.
4. Resposta de bot ja existente deve ativar idempotencia.
5. Dados especificos de etapa devem ser salvos por transicao.
6. A transicao `1 -> 2` salva o nome.
7. Tratamentos `1 -> 1` nao salvam nome.

## Cuidados

Nao transformar `CicloMensagem` em um objeto gigante que faz tudo.

Ele deve organizar estado e oferecer propriedades semanticas. As operacoes de
banco, envio Meta e validacao devem continuar em camadas separadas.

Boa divisao:

```text
CicloMensagem
-> carrega estado do ciclo
-> expoe etapa_origem, etapa_destino e helpers semanticos

Repositorios
-> executam SQL

Senders
-> enviam mensagem pela Meta/PyWa

Resolvers de etapa
-> validam a resposta e escolhem o proximo envio

Transacoes
-> persistem resposta, conversa, fila e efeitos da transicao
```

## Caminho de migracao

Uma migracao segura para a V2 pode seguir esta ordem:

1. Criar dataclasses apenas como estruturas de leitura.
2. Converter `contexto_banco` e `contexto_historico` para objetos sem mudar a
   logica.
3. Converter `contexto_envio` para `EnvioContexto`.
4. Trocar acessos diretos a dicionarios por propriedades do ciclo.
5. Depois disso, revisar os pontos de transicao de etapa.

Nao e recomendado fazer essa troca junto com mudancas de regra de negocio.

## Resultado desejado

A V2 deve permitir ler o fluxo assim:

```python
if ciclo.esta_na_transicao(1, 2):
    persistir_nome_cliente(ciclo)

if ciclo.esta_na_transicao(2, 3):
    persistir_responsavel_atendimento(ciclo)
```

O objetivo e reduzir o esforco mental de rastrear chaves soltas e deixar as
regras de transicao mais explicitas.
