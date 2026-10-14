# Otimização de Custo - Produção V1 Econômica

## Objetivo

Reduzir o custo mensal da primeira produção sem alterar regra de negócio, fluxo
do webhook, fluxo do worker, proteção anti-flood, proteção de turno, logs
importantes ou lógica do sistema.

A ideia da V1 econômica é manter uma base simples e séria:

- uma EC2 pequena para Django, worker, Nginx e Redis local;
- um RDS PostgreSQL pequeno;
- HTTPS direto no Nginx;
- sem ElastiCache no começo;
- sem Load Balancer no começo;
- sem AWS WAF no começo;
- backups e alertas de custo ativos.

## Estado Atual do Projeto

A V1 já possui configuração por ambiente via:

```text
core/config_env.py
.env local ignorado pelo Git
```

Portanto, este documento não propõe mais alterações de código para tirar
credenciais hardcoded. Essa etapa já foi resolvida na segurança V1. A otimização
de custo agora é principalmente uma decisão de infraestrutura e deploy.

## O Que Esta Otimização Não Muda

- Não muda webhook.
- Não muda worker.
- Não muda `flow_sender`.
- Não muda repositories.
- Não muda regras de conversa bloqueada.
- Não muda regras de anti-flood.
- Não muda regra de uma mensagem por turno.
- Não muda locks.
- Não muda commits e rollbacks.
- Não muda estrutura principal do banco.

## Configuração Externa

Em desenvolvimento, use o `.env` local privado e ignorado pelo Git.

Em produção econômica, uma alternativa simples é usar um arquivo fora do
repositório:

```text
/etc/chatbot.env
```

Esse arquivo deve ter permissão restrita:

```bash
sudo chown root:root /etc/chatbot.env
sudo chmod 600 /etc/chatbot.env
```

Variáveis principais:

```text
DJANGO_SECRET_KEY
DJANGO_DEBUG
DJANGO_ALLOWED_HOSTS
DJANGO_CSRF_TRUSTED_ORIGINS
DJANGO_SECURE_SSL_REDIRECT
DJANGO_SESSION_COOKIE_SECURE
DJANGO_CSRF_COOKIE_SECURE
DJANGO_SECURE_HSTS_SECONDS

DB_HOST
DB_NAME
DB_USER
DB_PASSWORD
DB_PORT

REDIS_HOST
REDIS_PORT
REDIS_USERNAME
REDIS_PASSWORD
REDIS_SSL

META_ACCESS_TOKEN
META_WEBHOOK_VERIFY_TOKEN
META_APP_SECRET
META_WEBHOOK_SIGNATURE_REQUIRED

WEBHOOK_MAX_BODY_BYTES
```

## RDS PostgreSQL

Se o projeto já possui RDS, não é obrigatório criar outro banco. O passo correto
é revisar a configuração:

```text
Serviço: Amazon RDS PostgreSQL
Região: mesma região da EC2, preferencialmente sa-east-1 se já estiver assim
Modo: Single-AZ na V1 econômica
Classe: pequena, como db.t4g.micro ou equivalente
Backup automático: 7 dias
Public access: No
Storage autoscaling: ligado com limite baixo/controlado
Deletion protection: recomendado quando houver cliente real
```

Security Group do RDS:

```text
Entrada TCP 5432:
    origem: Security Group da EC2

Não liberar 5432 para 0.0.0.0/0.
Não deixar o RDS público.
```

## EC2 Única para V1

Configuração recomendada:

```text
Sistema: Ubuntu LTS
Tipo: t3.micro, t4g.micro, t3.small ou t4g.small
Disco: 20 GB a 30 GB
```

Security Group da EC2:

```text
SSH 22:
    origem: somente seu IP

HTTP 80:
    origem: 0.0.0.0/0

HTTPS 443:
    origem: 0.0.0.0/0
```

Não abrir Redis publicamente:

```text
6379:
    não abrir para internet
```

## Redis Local

Para reduzir custo na V1, Redis pode rodar localmente na EC2:

```text
REDIS_HOST=127.0.0.1
REDIS_PORT=6379
REDIS_SSL=False
```

Configuração recomendada no Redis:

```text
bind 127.0.0.1 ::1
protected-mode yes
```

Redis é cache e fallback operacional, não fonte persistida da verdade. Se o
Redis local for perdido, o sistema recompõe dados a partir do banco quando o
fluxo prevê fallback.

## Serviços do Sistema

Em produção econômica, a EC2 pode manter serviços separados:

```text
chatbot-web.service     Django/Gunicorn
chatbot-worker.service  worker da fila
nginx                   proxy HTTPS
redis-server            cache local
```

O serviço web e o worker devem receber o mesmo arquivo de ambiente, por exemplo:

```text
EnvironmentFile=/etc/chatbot.env
```

A V1 deve operar com apenas um worker ativo. Múltiplos workers ficam para a V2,
reaproveitando as proteções de lock, ordenação, retry e idempotência já
documentadas.

## Nginx e HTTPS

A URL pública da Meta deve usar HTTPS:

```text
https://seudominio.com.br/webhook
```

Nginx pode fazer proxy para Django/Gunicorn em `127.0.0.1:8000`. O limite de
body no Nginx deve ser compatível com `WEBHOOK_MAX_BODY_BYTES`.

## Backups e Logs

No RDS:

```text
Backup automático ligado
Retenção inicial: 7 dias
Snapshot manual antes de alterações grandes
```

Na EC2:

```text
journalctl -u chatbot-web -f
journalctl -u chatbot-worker -f
```

Defina rotação ou limite de uso do journald para evitar crescimento indefinido.

## Alertas de Custo

Criar AWS Budget mensal:

```text
Alerta 1: US$ 20
Alerta 2: US$ 35
Alerta 3: US$ 50
```

Isso evita surpresa de custo em caso de erro de configuração, abuso HTTP ou
crescimento inesperado.

## O Que Não Usar na V1 para Economizar

```text
Não usar ElastiCache agora.
Não usar Load Balancer agora.
Não usar WAF agora.
Não usar CloudFront agora, a menos que exista motivo real.
Não criar múltiplas EC2 agora.
Não criar múltiplos workers agora.
```

Essas peças ficam para V2 ou para quando houver tráfego, contratos ou exigência
de disponibilidade que justifique o custo.

## Validações de Deploy

Antes de colocar a unidade real para usar:

```text
GET /webhook responde verificação da Meta.
POST /webhook aceita payload real da Meta.
Webhook valida assinatura.
Webhook usa Redis configurado por ambiente.
Webhook grava fila no RDS.
Worker lê fila no RDS.
Worker acessa Redis configurado por ambiente.
Admin acessa banco.
Logs aparecem no serviço configurado.
```

## Estimativa de Custo

V1 econômica:

```text
EC2 pequena + Redis local + Nginx + worker: baixo custo
RDS pequeno Single-AZ: principal custo fixo
Sem ElastiCache: economia importante
Sem Load Balancer: economia importante
Sem WAF: economia importante
```

Estimativa mensal aproximada:

```text
US$ 15 a US$ 35/mês
R$ 75 a R$ 180/mês, dependendo do câmbio e da classe escolhida
```

## Quando Migrar para Arquitetura Mais Cara

Migrar para V2 de infraestrutura quando houver motivo real:

```text
mais tráfego
mais unidades pagando
necessidade de alta disponibilidade
necessidade de múltiplas EC2
necessidade de proteção WAF
necessidade de Load Balancer
necessidade de Redis gerenciado
necessidade de deploy sem downtime
```

Migrações futuras:

```text
Redis local -> ElastiCache
Nginx direto -> Load Balancer
Sem WAF -> AWS WAF
1 worker -> múltiplos workers controlados
EC2 única -> arquitetura com autoscaling
Logs locais/systemd -> CloudWatch estruturado
```
