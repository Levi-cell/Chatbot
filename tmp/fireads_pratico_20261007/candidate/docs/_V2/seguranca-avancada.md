# Segurança Avançada - V2

## Objetivo

Registrar as proteções que não entram na segurança básica da V1. A V1 remove
segredos hardcoded e melhora a configuração por ambiente. A V2 deve tratar
proteções mais fortes, automação e governança.

## Fora do Escopo da V1

Ficam para a V2:

- criptografia de telefone na camada da aplicação;
- coluna HMAC para busca e índice sem expor telefone original;
- AWS KMS;
- AWS Secrets Manager;
- rotação automática de segredos;
- políticas IAM separadas por serviço;
- auditoria estruturada de acesso a dados;
- retenção automática de dados pessoais;
- anonimização ou pseudonimização planejada.

## Telefones de Clientes

Criptografar diretamente `waid_telefone` na coluna atual não deve ser feito de
forma improvisada. Isso quebraria igualdade, índices, consultas, joins, locks,
cache e regras de busca.

A solução futura deve separar armazenamento e busca:

```text
waid_criptografado
waid_lookup_hmac
```

`waid_criptografado` guarda o valor reversível com criptografia por envelope.
`waid_lookup_hmac` guarda um valor determinístico e indexável para localizar o
cliente sem expor o telefone original.

## Identificadores Meta

`phone_number_id` e `WABA_ID` são identificadores operacionais. Eles não devem
ser tratados como senhas, mas também não precisam aparecer completos em logs
públicos, prints ou documentação.

Prioridade de proteção:

```text
1. Access token da Meta
2. App Secret da Meta
3. Senhas do banco e Redis
4. Dados pessoais de clientes
5. Identificadores operacionais Meta
```

## Gestão de Segredos

Na V2, avaliar:

- AWS Secrets Manager;
- AWS Systems Manager Parameter Store;
- AWS KMS;
- rotação automatizada;
- permissões IAM mínimas por serviço;
- separação entre ambiente de desenvolvimento e produção;
- processo claro para revogar credenciais vazadas.

## Critério para Migrar

Levar esta frente para execução quando:

- houver mais contratos ativos;
- o repositório tiver mais colaboradores;
- o projeto sair de operação manual para operação contínua;
- houver necessidade de auditoria mais forte;
- existir obrigação contratual mais exigente.
