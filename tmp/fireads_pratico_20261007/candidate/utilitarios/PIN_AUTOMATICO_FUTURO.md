# Ideia futura — rotação automática do PIN Meta

## Objetivo

Permitir que cada número do WhatsApp tenha um PIN de registro próprio, renovado
automaticamente em uma frequência configurável e mantido sincronizado entre a
API da Meta e a fonte segura usada pela aplicação.

Este documento registra somente uma ideia para uma versão futura. Nenhum
agendador, alteração de banco ou chamada automática à Meta foi implementado.

## Fronteira arquitetural

O comando manual de consulta ou troca continua pertencendo a `utilitarios/`.
Quando a rotação se tornar periódica, ela deixará de ser um utilitário manual e
deverá nascer como serviço ou job controlado, com entrypoint, observabilidade e
ciclo de deploy próprios. As primitivas reutilizáveis da integração continuam
no domínio do WhatsApp em `core`.

## Modelo proposto

O estado deve ser separado por `phone_number_id`. Cada tentativa de rotação
precisa registrar, no mínimo:

- identificador do número e da unidade;
- versão da rotação;
- estados `pendente`, `aplicando`, `ativo` ou `falhou`;
- instante da tentativa e da confirmação;
- contagem de tentativas e erro sanitizado;
- referência segura ao PIN anterior durante a transição.

O PIN tem exatamente seis dígitos, inclusive zeros à esquerda. Sua geração deve
usar fonte criptograficamente segura, por exemplo:

```python
import secrets

pin = f"{secrets.randbelow(1_000_000):06d}"
```

Nunca usar `random`, sequência previsível, timestamp ou identificador da
unidade como PIN.

## Consistência entre banco e Meta

PostgreSQL e Meta não participam da mesma transação distribuída. Portanto, não
é correto gravar o novo PIN como ativo no banco antes de a Meta confirmá-lo.
Uma execução segura deve:

1. obter um lock exclusivo por `phone_number_id`;
2. gerar e guardar o candidato como `pendente`, protegido em repouso;
3. enviar o candidato à Meta com timeout e retry limitados;
4. somente após resposta explícita de sucesso promovê-lo para `ativo`;
5. manter o PIN anterior disponível até a promoção terminar;
6. registrar `falhou` sem substituir o ativo quando a Meta não confirmar;
7. liberar o lock e publicar métricas sem revelar o PIN.

O lock pode ser uma lease distribuída ou advisory lock no PostgreSQL. Ele deve
ter expiração e fencing para impedir que dois schedulers promovam PINs
diferentes ao mesmo tempo. Retentativas precisam reutilizar a mesma operação
pendente ou reconciliá-la antes de gerar outro valor.

## Armazenamento e sigilo

O PIN não deve aparecer em logs, mensagens de erro, linha de comando, relatórios
ou histórico do Django Admin. O valor deve ficar cifrado no banco ou, de
preferência, em um gerenciador de segredos, com acesso mínimo para o serviço de
rotação e para os processos que realmente registram números.

Logs e auditoria guardam somente identificadores mascarados, versão, estado,
horário, latência, código HTTP e categoria sanitizada do erro. Tokens Meta e
corpos de resposta também nunca são persistidos.

## Frequência

Uma hora é o ponto inicial recomendado para estudar a necessidade real. Cinco
minutos aumenta chamadas, risco de rate limit e superfície operacional sem
benefício comprovado. A frequência deve ser configurável por ambiente e somente
reduzida após validar limites, comportamento e suporte oficial da Meta.

O scheduler precisa aplicar jitter entre números e garantir uma única execução
ativa por alvo. Pausas, manutenção e recuperação manual devem existir antes de
habilitar a rotina em produção.

## Recuperação e operação

Deve existir um comando administrativo protegido para:

- consultar o estado sem revelar o PIN;
- reconciliar uma operação interrompida;
- repetir uma falha conhecida;
- suspender a rotação de um número;
- restaurar conscientemente o PIN anterior, quando a Meta permitir;
- confirmar que banco, segredo ativo e Meta voltaram a convergir.

Alertas devem cobrir falhas repetidas, lock expirado, operação pendente antiga,
divergência e ausência de rotação dentro da janela esperada.

## Validação antes de implementar

- confirmar na documentação oficial da Meta o endpoint, permissões, limites e
  semântica de idempotência vigentes;
- decidir se o banco guarda o segredo cifrado ou apenas uma referência externa;
- definir o responsável pelo scheduler e seu comportamento durante deploy;
- criar rollback operacional e processo de recuperação documentados;
- testar concorrência, crash entre Meta e promoção local e retry após timeout;
- usar mocks/fakes nos testes automatizados; nunca alterar um número real na
  suíte;
- liberar primeiro para uma única unidade, com monitoramento e chave de pausa.

## Critérios mínimos de aceite

- nunca existem duas rotações simultâneas para o mesmo número;
- falha na Meta não substitui o PIN ativo;
- uma resposta perdida pode ser reconciliada sem gerar divergência silenciosa;
- PIN e token não aparecem em qualquer saída observável;
- cada promoção possui trilha de auditoria sem segredo;
- o serviço pode ser pausado e retomado com segurança;
- a aplicação continua usando o último PIN confirmado durante falhas;
- testes provam os caminhos de sucesso, timeout, retry, concorrência, crash e
  recuperação.
