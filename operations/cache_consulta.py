from datetime import datetime, timedelta, timezone
from core.cache.redis_client import get_redis_safe

r = get_redis_safe(retries=1, delay=0, validate=True)

chaves = list(
    r.scan_iter(
        match="conversa_bloqueada:*",
        count=100,
    )
)

print("Total de conversas bloqueadas:", len(chaves))

for chave in chaves:
    dados = r.hgetall(chave)
    ttl = r.ttl(chave)

    expira_em = (
        datetime.now(timezone.utc) + timedelta(seconds=ttl)
        if ttl > 0
        else None
    )

    print("\n" + "=" * 70)
    print("Chave:", chave)
    print("Telefone:", dados.get("cliente_telefone"))
    print("Phone Number ID:", dados.get("id_phone_unidade"))
    print("Finalizou em:", dados.get("finalizou_em"))
    print("Dias de bloqueio:", dados.get("bloqueio_dias"))
    print("TTL em segundos:", ttl)
    print("Expira aproximadamente em:", expira_em)