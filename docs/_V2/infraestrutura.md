# Infraestrutura - V2

## Objetivo

Registrar melhorias de infraestrutura que não entram na V1 econômica. A V1 deve
ser simples, barata e suficiente para poucos contratos. A V2 deve escalar quando
houver demanda real.

## V1 Esperada

A V1 pode operar com:

- uma EC2 pequena;
- Django/Gunicorn;
- um worker ativo;
- Nginx com HTTPS;
- Redis local ou Redis simples;
- PostgreSQL RDS pequeno;
- backups básicos;
- logs via systemd ou mecanismo equivalente.

## Fora do Escopo da V1

Ficam para a V2:

- Load Balancer;
- AWS WAF;
- ElastiCache;
- múltiplas EC2;
- autoscaling;
- deploy sem downtime;
- CloudWatch estruturado;
- alarmes de erro e latência;
- filas externas gerenciadas;
- blue/green deploy;
- ambiente de staging completo.

## Quando Migrar

Migrar para esta arquitetura quando houver:

- mais unidades pagantes;
- volume maior de mensagens;
- necessidade de alta disponibilidade;
- necessidade de manutenção sem parar o sistema;
- risco maior por visibilidade pública;
- exigência contratual de SLA;
- necessidade de observabilidade profissional.

## Cuidados

A V2 não deve adicionar infraestrutura por vaidade técnica. Cada peça precisa
resolver um problema real:

```text
ElastiCache       -> Redis gerenciado e mais resiliente
Load Balancer    -> múltiplas instâncias web
WAF              -> proteção adicional contra abuso HTTP
CloudWatch       -> logs, métricas e alertas centralizados
Autoscaling      -> variação real de carga
Staging          -> testar mudanças antes da produção
```

## Relação com Segurança

Infraestrutura e segurança caminham juntas, mas não devem ser misturadas em uma
mudança gigante. A ordem recomendada é:

```text
1. Segurança básica por ambiente
2. Deploy econômico da V1
3. Observabilidade mínima
4. Segurança avançada
5. Escala e alta disponibilidade
```
