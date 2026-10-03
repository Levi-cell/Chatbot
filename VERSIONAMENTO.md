# Registro de versionamento

## Histórico de versões

### V1.0.0 — Proteção contra bots

Commit: `9d34c6b920e92cb2f759e7ae3148b5a6e69a66f7`

### V1.0.1 — Profissão no atendimento

Commit: `75975180e4bf85ce80da571df6844f10977c2df0`

### V1.0.2 — Decisão de comentário

Commit: `df8b014c8efbcbd2e1b2f8a3a57e39498b47fb62`

### V1.0.3 — Graph API centralizada

Commit: `61325237d9f84aeb6909992d344f56d18a4001bd`

### V1.0.4 — Confirmação, validações, tratamentos, renumeração

Commit: `440d5e0971cbd76841a764030fe510dc4861fa5a`

### V1.0.5 — Triagem etária, Funil, tratamentos e validações

Commit: `345e8767946a4cab41c9f31359db137c40fb60e7`

### Correção V1.0.5 — Profissão obrigatória após confirmação

Commit: `5f1889f5e2c81f3c233b3ea81940cbab98a84620`

### V1.0.6 — Apresentação personalizada do agente por unidade

Commit: `e052625d7707627a8c28945003ed2506c34e02d3`

### V1.0.7 — Organização operacional e limpeza estrutural

Commit: `2bc41888db4987e957c5653825acf4a55e9d611d`

### V1.0.8 — Suporte idoso e e-mail configurável

Commit: `62dca9a8c616f4682308c75600ab53a32d70c2db`

### V1.0.9 — Portal de monitoramento por unidade

Commit: `830e5634fdcc244d29e19114eb806c03846065c8`

### V1.1.0 — Painel responsivo, tags, CSV e triagem

Commit: `3f75447eb64a1a01085cccbc4a676a6a052d8493`

### V1.1.1 — Painel compacto e exportação CSV essencial

Commit: `84735aeaa521cfcf3a8bb13b2a8eddeb126fa1df`

### V1.2.0 — Follow-up automático e ajustes no CSV

Commit: `ec74d26398724e192f798397d71b189ed08c805c`

### V1.3.0 — Suporte etário configurável e indicadores comerciais

Commit: `50e59879c4c2aa6e0f6cf676adf50d40aec8ca03`

### V1.4.0 — Reservas aprimoradas, mensagens revisadas, encaminhamento contextualizado

Commit: `701b834fc178efcd42591692b9c35ce5827b840c`

### V1.5.0 — Atendimento refinado e abertura contextualizada

Commit: `8b8a0f8f2783dc7f137f389d96bb88f3f4f4acb5`

### V1.5.1 — Correções nas mensagens de atendimento

Commit: `d001d674bb7fb08f8b70980aec5cacfb326009d2`

### V1.5.2 — Correção da retomada após follow-up

Commit: `e5a2b45a5a71b487b6aa6a6f0aa9253e87185581`

### V1.6.0 — Segundo follow-up e consulta etária personalizada

Commit: `cdbc66f67a718c6ca82eec885237b69ed114865e`

### V1.6.2 — Correções nas mensagens e consulta etária

Commit: `8f6fe39928ef930092ea1c667f396f32501b5295`

### V1.6.3 — Correção visual na oferta do dependente

Commit: `ab157b4d53fec2fe60356047ac1709535731e2f1`

### V1.6.4 — Mensagens personalizadas nos dois follow-ups

Commit: `ec47623ae9a06ee0e1b5337a23b64df2da1bdf3a`

### V1.6.5 — Follow-up adaptado à etapa da oferta

Commit: `e1ea04b0f620da0eec783b818a72337f5b5f2fc0`

### V1.6.6 — Botão de reserva e aceite compatível

Commit: `087b5eb348d5fa84a8c78ecf26c37b59f52afda7`

### V1.7.0 — Filtro comercial e encerramentos por idade

Commit: `dbe38014a93b3d264e280911bd6db0f607591777`

### V1.7.1 — Simplificação do card de encerramentos

Commit: `d4104cfc444be88fef9deea1d0d3b4c5f04000da`

### V1.8.0 — Consumo mensal Meta e relatórios

Commit: `0b01c3a0fee52a24add7e4e1c0133eeee6099615`

### V1.8.1 — Explicações de consumo para franqueados

Commit: `2f4e2c9433d03b21d608c795c0d4cc6a0a3b7e2f`

## Padrão de numeração a partir da V1.2.0

Adotamos o formato `VMAJOR.MINOR.PATCH`, seguindo o versionamento semântico.
O prefixo V identifica a versão; cada um dos três números tem um significado:

1. **MAJOR** (primeiro número): mudança incompatível com os contratos públicos
   existentes. Exemplo: V1.2.0 -> V2.0.0.
2. **MINOR** (segundo número): funcionalidade nova ou melhoria substancial mantendo
   compatibilidade. Exemplo: V1.1.1 -> V1.2.0.
3. **PATCH** (terceiro número): correção de falha mantendo compatibilidade.
   Exemplo: V1.2.0 -> V1.2.1.

Compatibilidade considera os contratos documentados usados pelos usuários e pelas
integrações. Uma migração interna de banco, sozinha, não exige aumentar o MAJOR.

Quando uma entrega reúne tipos diferentes de mudança, prevalece o maior impacto.
Ao aumentar o MAJOR, zerar MINOR e PATCH. Ao aumentar o MINOR, zerar PATCH.
Os números são independentes, não decimais: V1.9.0 pode avançar para V1.10.0.
Não é necessário publicar V1.1.2 antes de V1.2.0; a mudança determina qual número
avança. Evitar saltos arbitrários, como V1.1.1 -> V1.5.0, sem motivo documentado.

As versões anteriores mantêm seus nomes e registros históricos. Da V1.2.0 em
diante, toda correção publicada recebe uma nova versão PATCH, em vez de reutilizar
o número anterior com o rótulo "Correção". Novidades seguem a regra MINOR ou MAJOR.
Uma versão publicada não deve ser reutilizada para identificar outro conteúdo.

Referência: [Versionamento Semântico](https://semver.org/lang/pt-BR/).

## Registro das próximas versões

1. Antes do commit, escolher a versão conforme a regra acima e adicionar uma
   descrição de até seis palavras neste arquivo, com o campo `Commit: PENDENTE`.
2. Criar o commit da versão.
3. Copiar o hash gerado pelo Git para a entrada correspondente no arquivo local.
4. Enviar essa atualização do hash junto com o commit da versão seguinte.

O hash de um commit não pode ser gravado dentro do próprio commit antes de ele
existir. Por isso, a versão entra no Git como PENDENTE e recebe o hash localmente
após a criação do commit principal.

É normal o `VERSIONAMENTO.md` local ficar uma atualização à frente do arquivo que
está no Git. Por exemplo: o commit da V1.0.3 levará o hash definitivo da V1.0.2
e deixará a própria V1.0.3 como PENDENTE até a versão seguinte.
