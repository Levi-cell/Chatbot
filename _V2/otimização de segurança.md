# Otimização de Segurança - Produção e V2

## Objetivo

Registrar melhorias de segurança para proteger o chatbot contra ataques, vazamento de dados, mau uso de tokens, falhas de infraestrutura, abuso de webhook e riscos de LGPD.

Este documento não é um plano para aplicar tudo agora. Ele serve como checklist técnico para evolução da V1 e preparação da V2.

## Estado atual do projeto

O projeto já possui algumas proteções importantes:

- Validação de `Content-Type`.
- Limite máximo de body do webhook.
- Validação de assinatura da Meta.
- Anti-flood com Redis, banco e memória local.
- Bloqueio do floodador na Meta.
- Webhook ignora mensagens inválidas antes de enfileirar.
- Worker separado do webhook.
- Proteção de turno para não processar várias mensagens do mesmo cliente/unidade ao mesmo tempo.
- Locks de conversa no banco.
- Logs com motivo e ação.
- Admin com várias tabelas somente leitura.
- Desbloqueio de cliente bloqueado na Meta só remove do banco se a Meta confirmar.
- Unidade só deve ser salva/removida se a operação correspondente na Meta der certo.

Mesmo assim, existem melhorias importantes para produção.

---

# Parte 1 - Segredos, tokens e variáveis sensíveis

## Risco atual

O projeto ainda possui informações sensíveis hardcoded em alguns arquivos, como:

- Host do banco.
- Usuário do banco.
- Senha do banco.
- Redis host.
- Redis password.
- `SECRET_KEY` do Django.
- Possíveis tokens Meta em arquivos utilitários.

Isso é perigoso porque:

- Se o GitHub vazar, o banco/token pode ser usado por terceiros.
- Se alguém tiver acesso ao repositório, consegue acessar infraestrutura.
- Trocar senha/token fica mais difícil.
- Viola boas práticas de produção e pode gerar risco LGPD.

## Tarefa futura

Mover todos os segredos para variáveis de ambiente:

```text
DJANGO_SECRET_KEY
DJANGO_DEBUG
DJANGO_ALLOWED_HOSTS
DJANGO_CSRF_TRUSTED_ORIGINS
DB_HOST
DB_NAME
DB_USER
DB_PASSWORD
DB_PORT
REDIS_HOST
REDIS_PORT
REDIS_USERNAME
REDIS_PASSWORD
META_APP_SECRET
META_ACCESS_TOKEN
META_WEBHOOK_VERIFY_TOKEN
```

## Proteção recomendada

Na AWS, usar preferencialmente:

```text
AWS Secrets Manager
ou
AWS Systems Manager Parameter Store
```

Para V1 econômica, pode usar:

```text
/etc/chatbot.env
```

Mas esse arquivo precisa ter permissão restrita:

```bash
sudo chown root:root /etc/chatbot.env
sudo chmod 600 /etc/chatbot.env
```

## Rotação de tokens

Criar rotina para:

- Trocar senha do banco periodicamente.
- Rotacionar token da Meta quando necessário.
- Revogar tokens antigos.
- Registrar data da última rotação.
- Nunca enviar token por print, log ou screenshot.

---

# Parte 2 - Criptografia e proteção de tokens

## O que criptografar

Dados sensíveis que merecem proteção especial:

- Access token da Meta.
- App Secret da Meta.
- Senha do banco.
- Senha do Redis se usar Redis externo/gerenciado.
- Tokens de futuras integrações.
- Dados pessoais sensíveis, se forem adicionados no futuro.

## V1

Na V1, a criptografia pode ser feita pelo ambiente:

```text
Variáveis de ambiente fora do Git.
Permissão restrita no servidor.
RDS com encryption at rest ativo.
HTTPS obrigatório.
```

## V2

Na V2, considerar:

```text
AWS KMS
AWS Secrets Manager
Criptografia aplicação-camada para campos sensíveis
Rotação automática de secrets
Controle de acesso IAM por serviço
```

## Regra importante

Não logar segredo.

Logs nunca devem conter:

```text
access_token
app_secret
senha de banco
senha Redis
payload completo com dados pessoais desnecessários
```

---

# Parte 3 - Segurança do webhook

## Proteções já existentes

O webhook já deve manter esta ordem lógica:

```text
1. Validar Content-Type
2. Validar tamanho máximo do body
3. Validar assinatura Meta
4. Parse JSON
5. Anti-flood
6. Unidade ativa
7. Conversa bloqueada
8. Regra de turno/fila
```

## Melhorias futuras

### Bloqueio por IP na infraestrutura

O payload da Meta não traz IP real do cliente final. O IP visto pelo servidor é origem HTTP da chamada para o webhook.

Para proteção contra ataque direto ao endpoint:

```text
Nginx rate limit
AWS WAF
CloudFront + WAF
Security Groups
```

### Rate limit no Nginx

Na V1, uma proteção simples pode ser feita no Nginx:

```nginx
limit_req_zone $binary_remote_addr zone=webhook_limit:10m rate=10r/s;

server {
    location /webhook {
        limit_req zone=webhook_limit burst=30 nodelay;
        proxy_pass http://127.0.0.1:8000;
    }
}
```

Essa proteção é externa ao Python e reduz custo antes de chegar no Django.

### AWS WAF futuro

Na V2, adicionar:

```text
AWS WAF rate-based rules
Bloqueio por país se fizer sentido
Managed rules contra bots conhecidos
Filtro de payload anormal
Alertas por volume de requests
```

## Assinatura da Meta

Manter obrigatório em produção:

```text
META_WEBHOOK_SIGNATURE_REQUIRED=True
META_APP_SECRET configurado
```

Se assinatura falhar:

```text
Ignorar e responder 403.
Não bloquear número na Meta.
Não enfileirar.
```

Isso é correto porque payload sem assinatura confiável pode nem ser da Meta.

---

# Parte 4 - Segurança contra flood e abuso

## Proteções atuais

O projeto usa:

```text
Redis primeiro
Banco como fallback
Memória local como último fallback
Bloqueio na Meta quando flood válido é identificado
TXT/alerta para cenário crítico
```

## Melhorias futuras

- Job automático que lê alertas críticos em TXT.
- Reconciliar banco x Meta.
- Avisar administrador quando Meta falhar em bloquear.
- Métricas por unidade.
- Métricas por wa_id.
- Painel de incidentes.
- Alertas quando flood dispara.

## Pontos de atenção

Se Redis, banco e Meta falharem ao mesmo tempo:

```text
O webhook deve continuar ignorando o evento crítico.
O sistema deve registrar alerta.
O administrador deve reconciliar depois.
```

Na V2, criar:

```text
job de reconciliacao automática
tabela de incidentes
painel admin de incidentes
alerta por e-mail/WhatsApp interno
```

---

# Parte 5 - Segurança do banco RDS

## Configuração recomendada

```text
RDS sem public access
Security Group liberando 5432 só para a EC2
Backup automático ligado
Encryption at rest ligado
Senha forte
Usuário sem privilégio desnecessário
Logs de conexão quando necessário
```

## Riscos

RDS público com senha hardcoded é risco crítico.

Consequências:

- Acesso indevido ao banco.
- Vazamento de dados pessoais.
- Manipulação de conversas.
- Manipulação de unidades.
- Manipulação de bloqueios.
- Risco LGPD.

## Tarefa futura

Separar permissões:

```text
Usuário app: SELECT/INSERT/UPDATE/DELETE apenas no schema chatbot
Usuário setup: CREATE/ALTER/DROP usado apenas em manutenção
Usuário admin: acesso controlado
```

Hoje o projeto usa scripts de setup que criam/alteram banco. Na V2, idealmente:

```text
Usuário de produção do app não deve ter permissão de DDL.
```

---

# Parte 6 - Segurança do Redis

## V1 econômica

Usar Redis local na EC2:

```text
host=127.0.0.1
port=6379
sem porta pública
```

Vantagem:

- Menor custo.
- Menor exposição externa.
- Redis é cache/fallback, não fonte principal de verdade.

## Configuração recomendada

No Redis local:

```text
bind 127.0.0.1 ::1
protected-mode yes
```

Não abrir porta 6379 na AWS.

## V2

Se migrar para ElastiCache:

```text
Subnet privada
Security Group liberando Redis só para EC2/app
Encryption in transit se disponível
Auth token se disponível
Sem acesso público
```

---

# Parte 7 - Segurança do Django/Admin

## Admin

Manter regras atuais:

```text
Cliente: somente visualização
Fila mensagens: somente visualização
Histórico mensagens: somente visualização
Conversa: somente visualização
Etapa: somente visualização
Dependente: somente visualização
Webhook flood evento: somente visualização
Cache controle: somente visualização
Unidade: controle permitido com regra Meta/cache
Cliente bloqueado Meta: somente remoção individual com confirmação da Meta
```

## Melhorias futuras

- 2FA para admin.
- IP allowlist para admin.
- URL admin não óbvia.
- Usuários com permissões específicas.
- Logs de ação do admin.
- Alertas para exclusão/alteração de unidade.

## Configurações Django de produção

Em produção:

```text
DEBUG=False
ALLOWED_HOSTS=domínio real
CSRF_TRUSTED_ORIGINS=domínio real
SECURE_SSL_REDIRECT=True
SESSION_COOKIE_SECURE=True
CSRF_COOKIE_SECURE=True
SECURE_HSTS_SECONDS configurado com cuidado
```

Essas flags devem ser aplicadas quando HTTPS estiver estável.

---

# Parte 8 - LGPD e dados pessoais

## Dados pessoais no projeto

O sistema pode armazenar:

- Telefone do cliente.
- Nome do cliente.
- E-mail do cliente.
- Nome de dependente.
- Telefone de dependente.
- E-mail de dependente.
- Histórico de mensagens.
- Unidade de atendimento.
- Dados de agendamento.

Isso envolve LGPD.

## Boas práticas

- Coletar só o necessário.
- Não armazenar dados sensíveis sem motivo.
- Evitar logar conteúdo completo de mensagem.
- Permitir rastrear histórico por cliente quando necessário.
- Criar política de retenção de dados.
- Criar rotina de exclusão/anonymização quando solicitado.
- Documentar finalidade do tratamento.
- Controlar acesso ao admin.

## Logs

Logs devem preferir:

```text
short_value(telefone)
id_cliente
id_conversa
id_mensagem
motivo
acao
```

Evitar:

```text
mensagem completa do cliente
payload completo da Meta
token
senha
dados pessoais desnecessários
```

## Retenção

Na V2, definir:

```text
Por quanto tempo manter histórico de mensagens.
Por quanto tempo manter eventos de flood.
Por quanto tempo manter logs.
Como excluir/anonymizar dados de cliente.
```

---

# Parte 9 - Backups e recuperação

## Banco

RDS:

```text
Backup automático
Snapshot manual antes de alteração grande
Teste de restore periodicamente
```

## Código

```text
GitHub privado ou com acesso controlado
Branches organizadas
Backup antes de mudanças críticas
```

## Redis

Na V1, Redis é cache:

```text
Não precisa backup crítico.
Se perder, recarrega pelo banco.
```

## Arquivos TXT de alerta

Se o webhook registrar alertas críticos em TXT:

```text
Guardar em pasta conhecida.
Não expor publicamente.
Rotacionar arquivo.
Futuramente transformar em tabela de incidentes.
```

---

# Parte 10 - Monitoramento e incidentes

## Alertas recomendados

Criar alerta para:

- Flood detectado.
- Meta falhou em bloquear.
- Banco falhou após Meta enviar mensagem.
- Redis indisponível.
- RDS indisponível.
- Worker reiniciou.
- Webhook retornando muitos 403/413/415.
- Aumento incomum de POST.
- Erro no admin ao registrar/desregistrar unidade.

## V2

Criar painel de incidentes:

```text
tipo_incidente
cliente
unidade
phone_id
wa_id
data
status
resolvido_por
resolvido_em
observação
```

---

# Parte 11 - Segurança da Meta

## Configurações importantes

Na plataforma Meta:

```text
App em modo Live/Produção
Callback URL com HTTPS real
Verify token forte
App Secret guardado fora do código
Assinatura validada no webhook
Permissões mínimas necessárias
WABA/números corretos conectados
Token com escopo necessário, não mais que isso
```

## Rotina operacional

- Conferir números conectados.
- Conferir se webhook está recebendo só eventos necessários.
- Revisar permissões do app.
- Rotacionar tokens quando necessário.
- Não expor tokens em scripts locais.

---

# Parte 12 - Segurança de infraestrutura AWS

## EC2

Configuração recomendada:

```text
SSH só para seu IP
Chave SSH protegida
Usuário sem senha
Fail2ban opcional
Atualizações de segurança
Nginx com HTTPS
Sem portas extras abertas
```

## Security Groups

```text
EC2:
    22 só seu IP
    80 público
    443 público

RDS:
    5432 só EC2

Redis local:
    sem regra pública
```

## IAM

Na V2:

```text
Usuário IAM sem root
MFA na conta AWS
Permissões mínimas
Separar usuário deploy/infra
```

## AWS Budget

Criar alertas:

```text
US$ 20
US$ 35
US$ 50
```

Protege contra custo inesperado em caso de ataque ou configuração errada.

---

# Parte 13 - Ataques e respostas esperadas

## Payload falso sem assinatura Meta

Resposta esperada:

```text
403
Não enfileirar
Não bloquear Meta
Logar motivo
```

## Content-Type inválido

Resposta esperada:

```text
415
Não parsear JSON
Não enfileirar
Não bloquear Meta
```

## Body grande demais

Resposta esperada:

```text
413
Não parsear JSON
Não enfileirar
Não bloquear Meta
```

## Flood válido vindo da Meta

Resposta esperada:

```text
Detectar por Redis
Fallback banco
Fallback memória
Bloquear na Meta quando possível
Registrar banco quando Meta confirmar
Ignorar mensagem
Não enfileirar
```

## Redis fora

Resposta esperada:

```text
Fallback banco
Se banco funcionar, proteger
Se banco também falhar, memória local tenta proteger
```

## Banco fora

Resposta esperada:

```text
Webhook não deve quebrar
Worker não deve morrer definitivamente
Mensagens não devem ser marcadas sent sem processamento
Logs devem indicar falha
```

---

# Parte 14 - Prioridades

## Prioridade alta para produção V1

1. Tirar senhas/tokens do código.
2. Usar `DEBUG=False`.
3. Configurar `ALLOWED_HOSTS`.
4. Configurar HTTPS real.
5. Validar assinatura Meta obrigatória.
6. RDS privado.
7. Redis local sem porta pública.
8. Security Groups corretos.
9. Backup RDS.
10. Alertas de custo.

## Prioridade média

1. 2FA no admin.
2. IP allowlist no admin.
3. Nginx rate limit.
4. Rotação de logs.
5. Rotação de tokens.
6. Monitoramento de worker.

## Prioridade V2

1. AWS WAF.
2. Secrets Manager/KMS.
3. ElastiCache privado.
4. Load Balancer.
5. Painel de incidentes.
6. Job automático de reconciliação Meta x banco.
7. Tabela de incidentes.
8. Controle de múltiplos workers.
9. Métricas e alertas estruturados.
10. Rotinas LGPD de retenção/anonymização.

