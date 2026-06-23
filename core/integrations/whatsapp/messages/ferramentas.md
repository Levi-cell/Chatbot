# Ferramentas para mensagens do WhatsApp

É possível criar mensagens muito parecidas com templates sem enviar um template
aprovado, desde que a janela de atendimento esteja aberta.

Em uma mensagem como a usada como referência, existem três elementos diferentes:

1. A arte superior é uma imagem pronta, que pode ser criada em uma ferramenta
   como o Canva.
2. O corpo utiliza a formatação nativa do WhatsApp.
3. A parte inferior utiliza rodapé e botão de URL.

## Formatação do texto

O WhatsApp interpreta marcadores enviados normalmente pela PyWa:

```python
MENSAGEM_EVENTO = (
    "🌸✨ *PALESTRA GRATUITA | MÊS DA MULHER* ✨🌸\n\n"
    "Março é o mês das mulheres e preparamos um momento especial.\n\n"
    "*🎀 Evento gratuito*\n"
    "📅 *Data:* 11 de março às 18h30\n"
    "📍 *Local:* Av. Barros e Almeida, 88\n"
    "📌 _Vagas limitadas_\n\n"
    "~Valor: R$ 50,00~\n"
    "*Inscrição gratuita!*"
)
```

Recursos disponíveis:

| Sintaxe | Resultado |
|---|---|
| `*texto*` | Negrito |
| `_texto_` | Itálico |
| `~texto~` | Tachado |
| `` ```texto``` `` | Monoespaçado |
| `> texto` | Citação |
| `- item` | Lista com marcadores |
| `1. item` | Lista numerada |

Não existe configuração especial na PyWa para essa formatação. Basta enviar os
marcadores dentro do texto.

Referência: [formatação oficial do WhatsApp](https://faq.whatsapp.com/539178204879377/).

## Mensagem semelhante a um template

A PyWa instalada suporta `URLButton` diretamente:

```python
from pywa.types import URLButton

cliente_wa.send_image(
    to=cliente_telefone,
    image="https://exemplo.com/palestra.jpg",
    caption=MENSAGEM_EVENTO,
    footer="Inscreva-se no botão abaixo",
    buttons=URLButton(
        title="Inscreva-se agora",
        url="https://exemplo.com/inscricao",
    ),
)
```

O resultado visual contém:

```text
imagem
texto formatado
rodapé em cinza
botão que abre o site
```

Não é necessário cadastrar um template para essa mensagem enquanto a janela de
atendimento estiver aberta.

## Ferramentas da PyWa

A PyWa 3.8.0 instalada oferece:

| Recurso | Objeto PyWa |
|---|---|
| Até 3 respostas rápidas | `Button` |
| Botão que abre site | `URLButton` |
| Lista com até 10 opções | `SectionList` |
| WhatsApp Flow | `FlowButton` |
| Ligação pelo WhatsApp | `VoiceCallButton` |
| Solicitar permissão de ligação | `CallPermissionRequestButton` |
| Imagem com legenda e botão | `send_image()` |
| Vídeo com legenda e botão | `send_video()` |
| Documento com legenda e botão | `send_document()` |

Referências:

- [componentes interativos da PyWa](https://pywa.readthedocs.io/en/latest/content/types/keyboard.html);
- [`send_message` na PyWa](https://pywa.readthedocs.io/en/latest/content/client/client_reference.html#pywa.client.WhatsApp.send_message).

## Diferenças em relação aos templates

Nem tudo que aparece no Gerenciador de Modelos existe em mensagens comuns:

- `CopyCodeButton` é voltado a templates;
- o botão tradicional para ligar para um número é diferente do
  `VoiceCallButton`;
- combinações com até 10 botões de vários tipos são próprias de templates;
- mensagens enviadas fora da janela de atendimento exigem template aprovado;
- um Flow precisa existir e estar publicado na Meta, embora a mensagem que o
  abre não precise necessariamente ser um template.

## Janela de atendimento e preço

Mensagens livres de atendimento são gratuitas enquanto a janela de atendimento
de 24 horas estiver aberta. Ela começa ou é renovada quando o cliente envia uma
mensagem.

Não basta o cliente ter falado com a empresa alguma vez. Depois das 24 horas sem
nova mensagem do cliente, o negócio precisa utilizar um template aprovado para
iniciar o contato novamente.

Referência: [preços da Plataforma do WhatsApp Business](https://developers.facebook.com/documentation/business-messaging/whatsapp/pricing).

## Situação do projeto

Atualmente, `envios.py` suporta texto formatado e botões de resposta. Para
alcançar todos os recursos visuais descritos neste documento, ainda será
necessário acrescentar suporte a:

```text
footer
URLButton
SectionList
FlowButton
VoiceCallButton
```

A estrutura atual de envio já fornece a base para essa evolução.
