# Hipótese de rotação do PIN de registro

A rotação periódica do PIN de cada número foi considerada para reduzir a dependência de um procedimento manual. O custo principal seria manter a credencial recuperável mesmo se a Meta aceitasse uma troca e a confirmação local falhasse. Restariam decisões sobre titularidade do segredo, armazenamento, acesso por unidade, auditoria e recuperação sem expor o PIN.

O utilitário existente atua manualmente sobre o registro do número. Seu ponto de entrada tem um efeito de escrita predefinido, inclusive com argumentos de ajuda. A [documentação operacional](README.md) descreve esse comportamento. A rotação agendada permanece uma ideia.
