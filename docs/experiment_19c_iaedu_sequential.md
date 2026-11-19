# 19c — IAedu sequencial, cápsula portátil e retoma conservadora

Preparado em 19-11-2026. O utilizador comunicou teste autenticado sintético com HTTP 200, exit 0, stream sem erros e JSON coerente com TESTEMUNHA; não houve identidade de modelo devolvida. Não se inspecionaram aqui os artefactos privados desse teste. Nesta sessão só se implementa/testa offline; não se executa o lote real.

## Integridade sem copiar o corpus inteiro

[portable_iaedu_pilot_19c.py](../src/annotation/portable_iaedu_pilot_19c.py) valida no g09 o pacote e **todo o bundle de origem** através dos validadores existentes, incluindo fontes, referências protegidas e seleção. Exporta os bytes do input original de 30, os 30 pedidos v2 e um manifesto com os hashes e a atestação dessa verificação. Não copia corpus, Gold50, NER integral, modelos, respostas Qwen ou revisões.

No Windows verificam-se o SHA-256 do manifesto obtido separadamente do g09, todos os ficheiros da cápsula, os 30 IDs/ordem/grupos, spans/mensagens e fingerprints dos registos. O texto/offsets originais são conservados. Os hashes de código/configuração normalizam **apenas CRLF para LF**, para compatibilidade Git Linux/Windows; ficheiros de dados/pedidos são comparados byte a byte, sem normalização. Uma alteração de código diferente de finais de linha bloqueia.

O Windows **não revalida o corpus ausente**: confia na atestação produzida pelo exportador autorizado e no digest obtido na sessão SSH de origem. Não equivale a prova independente de ausência de parentesco processual, assinatura do STJ ou autenticidade contra substituição fraudulenta de todo o ambiente de origem. Conservar o bundle original no INESC para auditoria. Não obter o digest esperado calculando-o apenas sobre a cópia local: isso não confirma que foi transferida a cápsula correta.

## 1. Exportação no g09 — apenas leitura/ficheiros, sem API

Com checkout develop sem alterações de código, atualizar e ativar o ambiente existente:

```bash
cd ~/thesis-ner
git status --short
git switch develop
git pull --ff-only origin develop
source venv-ner/bin/activate
```

Se o pacote das 30 ainda não existir, criá-lo **uma única vez**, preservando os inputs originais. Se já existir, saltar este comando; nunca sobrescrever:

```bash
python -u src/annotation/prepare_second_llm_pilot_19c.py \
  --input data/raw/experiment_19c_pilot03/pilot_input.jsonl \
  --selection-manifest data/raw/experiment_19c_pilot03/selection_manifest.json \
  --reference-run data/raw/experiment_19c_pilot_15324/run.json \
  --output-dir data/raw/experiment_19c_claude_manual_package01
```

Exportar a cápsula nova:

```bash
python -u src/annotation/portable_iaedu_pilot_19c.py \
  --package-dir data/raw/experiment_19c_claude_manual_package01 \
  --output-dir data/raw/experiment_19c_iaedu_portable01
```

Guardar o `portable_manifest_sha256` apresentado no terminal SSH (64 caracteres hexadecimais, sem aspas). O resumo mostra também o tamanho e número real de ficheiros exportados. Nenhuma inferência NER/LLM nem Slurm é necessária para esta verificação/exportação CPU. Os caminhos pilot03 são os do histórico e têm de corresponder ao run original. Se falhar, investigar os bindings, sem editar hashes ou omitir ficheiros obrigatórios.

## 2. Transferência e verificação no Windows/PowerShell

Só se copia a pasta da cápsula. Não usar scp no diretório data/raw inteiro. O login é introduzido localmente; nenhum login pessoal ou credencial é versionado.

```powershell
Set-Location 'C:\Users\Utilizador\Desktop\Tese\Projeto\thesis-ner'
git switch develop
git pull --ff-only origin develop
$iaeduSshLogin = Read-Host 'Utilizador SSH INESC'
$iaeduRemote = "${iaeduSshLogin}@g09.hlt.inesc-id.pt"
$iaeduCapsule = 'data/raw/experiment_19c_iaedu_portable01'
if (Test-Path -LiteralPath $iaeduCapsule) { throw 'Destino existente: nao sobrescrever' }
New-Item -ItemType Directory -Path data/raw -Force | Out-Null
scp -r "${iaeduRemote}:~/thesis-ner/data/raw/experiment_19c_iaedu_portable01" data/raw/
if ($LASTEXITCODE -ne 0) { throw 'Falha de transferencia' }
$iaeduCapsuleDigest = Read-Host 'portable_manifest_sha256 mostrado no g09'
& .\venv\Scripts\python.exe src/annotation/run_iaedu_pilot_19c.py `
    --capsule-dir $iaeduCapsule --expected-manifest-sha256 $iaeduCapsuleDigest --check-only
if ($LASTEXITCODE -ne 0) { throw 'Integridade nao validada: nao executar API' }
```

check-only não lê chave, não precisa de endpoint/canal e não envia qualquer contexto. Nenhuma transferência ou exportação real foi feita pelo agente de código nesta revisão. A cápsula e os outputs continuam privados e ignorados pelo Git.

## 3. Autorização separada — permanece pendente nesta preparação

`authorization_TEMPLATE_PRIVATE.json` é exportado com external_transmission_authorized=false e privacy_review_completed=false. O manifesto da cápsula também mantém false e é imutável. Copiar o template, sem o sobrescrever, para um ficheiro privado novo apenas quando se preparar a decisão de transmissão. Exemplo de criação **sem autorizar**:

```powershell
$iaeduAuthorization = 'data/raw/experiment_19c_iaedu_authorization_PRIVATE.json'
if (Test-Path -LiteralPath $iaeduAuthorization) { throw 'Autorizacao existente: nao sobrescrever' }
Copy-Item -LiteralPath "$iaeduCapsule/authorization_TEMPLATE_PRIVATE.json" -Destination $iaeduAuthorization
```

Depois de uma decisão explícita e verificação de privacidade, o responsável preenche o ficheiro privado: scope STJ_19C_30_IAEDU_API, digest exato da cápsula, endpoint/canal exatos, approved_by, approved_at ISO-8601 com timezone e os dois flags explicitamente true. Este documento é uma declaração de autorização do responsável, não uma certificação automática de anonimização. Não guardar a chave nesse ficheiro. Sem essa declaração o runner recusa antes de criar a execução ou contactar a API. Não editar o manifesto para alegar autorização.

Esta preparação/commit e o teste sintético anterior **não** aprovam a transmissão das 30 menções reais. Não executar o bloco seguinte nesta fase.

## 4. Comando real preparado — só depois de autorizado

Usar os valores reais do painel e a chave válida, sem os escrever em código/histórico. O diretório do run é fixo para permitir retoma; não gerar outro nome automaticamente a cada tentativa.

```powershell
$env:IAEDU_ENDPOINT = Read-Host 'Endpoint HTTPS do agente IAedu'
$env:IAEDU_CHANNEL_ID = Read-Host 'Channel ID'
$iaeduRunDir = 'data/raw/experiment_19c_iaedu_30_run01'
$iaeduResumeArgs = @()  # Primeira execucao. Para retomar: @('--resume')
$iaeduSecret = Read-Host 'Chave IAedu' -AsSecureString
$iaeduKeyPointer = [IntPtr]::Zero
try {
    $iaeduKeyPointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($iaeduSecret)
    $env:IAEDU_API_KEY = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($iaeduKeyPointer)
    & .\venv\Scripts\python.exe src/annotation/run_iaedu_pilot_19c.py `
        --capsule-dir $iaeduCapsule --expected-manifest-sha256 $iaeduCapsuleDigest `
        --run-dir $iaeduRunDir --authorization $iaeduAuthorization --execute @iaeduResumeArgs
    $iaeduBatchExitCode = $LASTEXITCODE
} finally {
    if ($iaeduKeyPointer -ne [IntPtr]::Zero) {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($iaeduKeyPointer)
    }
    Remove-Item Env:IAEDU_API_KEY -ErrorAction SilentlyContinue
    $iaeduSecret.Dispose()
}
Write-Host "Exit code: $iaeduBatchExitCode"
```

Para retomar numa consola com as mesmas variáveis de cápsula/digest/autorização, repetir o bloco com `$iaeduResumeArgs = @('--resume')` e o **mesmo** diretório. Não apagar checkpoints nem criar outro run para contornar um pedido bloqueado; um run novo é outra experiência e pode reenviar pedidos.

## Persistência, retoma e limites

[run_iaedu_pilot_19c.py](../src/annotation/run_iaedu_pilot_19c.py) processa sequencialmente, com lock do sistema operativo contra dois runners no mesmo diretório (libertado ao terminar/crash). Congela as 30 mensagens verificadas em memória, confere cápsula/autorização/configuração antes de cada pedido e cria um UUID novo por chamada. A chave não entra no binding ou nos artefactos.

- Antes do HTTP: request.txt e attempt.json persistidos por ordinal; o transporte persiste dispatch_intent.json com UUID/hash. Não guarda headers de autenticação.
- Depois do HTTP: corpo, eventos, headers de resposta, mensagem derivada e metadados originais ficam em mentions/NNN/transport/. Falhas e Ctrl+C cooperativo conservam o material disponível, sem retentativa automática.
- Aplica o parse_response histórico ao texto extraído, sem strip/markdown repair/recuperação de evidência. prediction.json conserva o raw, erros, contexto/offsets originais, SILVER e revisão semântica pendente. A etiqueta da UI é separada de model_metadata_returned e backend_model_identity_status; sem campos reconhecidos fica not_found_in_parsed_metadata, nunca preenchido com a etiqueta da UI. Campos devolvidos também não são verificação independente do backend.
- complete.json guarda os hashes dos artefactos antes de avançar. Cada resultado gera imediatamente o agregado atomicamente e progresso ordinal/30, sem nomes ou contextos no stdout. Model JSON inválido é um pedido concluído, preservado e não repetido para melhorar formato.
- binding.json e snapshots da autorização/manifesto fixam o run. O resumo e silver_predictions.jsonl são derivados dos checkpoints; podem ser reconstruídos. Os ficheiros por menção são a fonte de verdade e não são sobrescritos em retoma válida.

Se o HTTP terminou e run.json do transporte foi persistido mas faltou escrever a previsão/complete, a retoma reconstrói **offline**, sem outro pedido. Se existir intenção de envio sem resultado HTTP durável, stream parcial ou erro de transporte, bloqueia com estado de revisão; não assume que nada chegou ao servidor. Isto prioriza não duplicar chamadas. Não há garantia exactly-once entre rede e disco sem contrato de idempotência da API; perda abrupta de energia pode também perder bytes ainda não persistidos. Ctrl+C é tratado quando possível; kill forçado deixa um checkpoint incerto que não é reproduzido automaticamente.

Estados bloqueados exigem investigar os artefactos e, se necessário, o registo do serviço antes de qualquer decisão explícita de repetição. Este runner não inventa uma resolução nem oferece um flag para ignorar o problema. Alterar código (exceto CRLF/LF), pedidos, respostas, autorização, endpoint/canal ou bindings bloqueia a retoma. Não se faz nova amostragem, treino, benchmark gold ou validação humana automática. A cápsula conserva a atestação de proteção de origem, não cria elegibilidade para treino.

Conclusão completed significa que os 30 HTTP foram capturados e avaliados estruturalmente, **não 30 labels corretas**. O resumo conta também outputs inválidos. Preservar os quatro eixos de comparação e manter papéis/âmbito/abstenção pendentes de revisão. Não publicar outputs, cápsulas, permissões, headers ou logs com dados privados.

Validação local: **253 testes**, sucesso, **1 integração opcional omitida**; 12 novos testes sintéticos sequenciais/portáteis. Verificam 30 threads novas, zero reenvios em retoma completa, recuperação após HTTP sem previsão, bloqueio de intenções incertas/streams parciais, JSON inválido conservado, lock Windows, alterações de endpoint, digest/código/ficheiros, metadados de modelo separados da UI e ausência de leitura do corpus no modo portátil. Não houve execução real do lote, transferência SCP ou alteração da autorização externa por esta implementação.
