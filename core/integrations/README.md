# Integrações externas

Adaptadores compartilhados para serviços externos. A V1 integra WhatsApp Cloud
API por PyWa e criação de oportunidades no Funil de Vendas por ApiCarrossel.

- [Portal do projeto](../../README.md)
- [Padrões de arquitetura](../../PADROES_DE_ARQUITETURA.md#integrações-externas)
- [Integração WhatsApp](whatsapp/README.md)
- [Integração Funil de Vendas](funil/README.md)

## Contrato

Uma integração deve:

- encapsular biblioteca, cliente e tipos externos;
- receber dados já validados pelo chamador;
- devolver contrato simples para o sistema;
- preservar ou traduzir falhas com contexto útil;
- registrar eventos sem expor credenciais.

Uma integração não deve:

- executar SQL de aplicação;
- acessar fila diretamente;
- decidir retry ou limite de tentativas;
- controlar commit, rollback ou close do worker;
- importar webhook ou worker;
- manter regra de negócio duplicada.

## Nova integração

Crie `core/integrations/<servico>/` quando houver uma fronteira externa real.
Organize cliente, operações, exceções e ferramentas conforme a complexidade. Não
crie wrappers que apenas reexportem outra função sem responsabilidade própria.

Testes de integração nesta fase devem simular o serviço externo e permanecer em
`tests/`.
