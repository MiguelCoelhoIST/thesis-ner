# 19c — adaptador de agente IAedu, preparação offline

Preparado em 19-11-2026. O utilizador indica que o agente aparece como **OpenAI GPT-5.5**. Isso é uma etiqueta apresentada pelo serviço, não verificação independente do modelo/checkpoint backend. A via Claude manual continua preservada; esta é outra configuração experimental, não uma execução Claude disfarçada.

Atualização: autorizado disponibilizar um **teste de ligação com um único exemplo inteiramente inventado**, para o utilizador executar no Windows. Não se autoriza o envio do lote real. O agente de código só executou testes HTTP simulados, não a chamada autenticada real. O CLI conserva o plano offline e acrescenta exclusivamente `--synthetic-connection-test`; não aceita pacote, ficheiro de contexto ou mensagem alternativa nesse modo.

## Contrato confirmado e limites

Fonte principal: [exemplo Python oficial IAedu](https://docs.iaedu.pt/books/funcionalidade-api/page/exemplo-python), além do exemplo fornecido pelo utilizador. A documentação recomenda um UUID aleatório para thread_id e descreve JSON por linha com type=token/content. O adaptador gera um UUID4 novo dentro da construção de **cada** pedido; não existe thread global nem cópia do identificador do exemplo. Assim não reutiliza o histórico intencionalmente. Não houve verificação ao vivo da criação de threads nesta sessão.

Uma thread nova não prova ausência de instruções, ferramentas, bases de conhecimento ou memória partilhada configuradas no agente. Registar/verificar a configuração do agente antes de interpretar diferenças como efeito do modelo. A API utilizada é de agente IAedu, não o endpoint OpenAI nem um seletor direto de modelos. Não são enviados model, temperature, seed ou outros controles não documentados. Os valores não devolvidos continuam desconhecidos.

Implementação: [iaedu_agent_api_19c.py](../src/annotation/iaedu_agent_api_19c.py). Reutiliza o validador do pacote original de 30 e os mesmos requests/NNN.txt: prompt v2, alvo e contexto, sem propostas Qwen, pareceres ou IDs internos no texto enviado. Só os quatro campos obrigatórios entram no multipart: channel_id, thread_id, user_info vazio e message. A biblioteca requests fornece o boundary; não definir Content-Type multipart sem esse boundary.

## Credenciais e configuração

- `IAEDU_ENDPOINT`: endpoint HTTPS do agente obtido no painel, exclusivamente host api.iaedu.pt e caminho de streaming esperado. Aceita o duplo slash do exemplo sem o normalizar.
- `IAEDU_CHANNEL_ID`: canal do painel.
- `IAEDU_API_KEY`: chave, lida apenas no transporte autenticado; não entra no plano, código, Git, stdout ou artefactos. Não é necessária para a preparação offline.

Não versionar endpoint/canal específicos nem copiar credenciais do exemplo para ficheiros. A chave exposta na conversa deve ser rodada antes de qualquer utilização futura. Não ativar tracing/debug HTTP que imprima headers. O adaptador não regista headers de pedido nem mensagens de exceção. Se uma resposta ecoar a chave conhecida, recusa persistir body/headers/eventos e guarda só um código seguro; esta exceção protege a credencial em vez de conservar uma cópia sensível.

requests já estava instalado no ambiente local; foi declarado explicitamente em requirements.txt. Não foram instaladas dependências nesta sessão.

## Comando permitido nesta etapa: plano privado, zero rede

Com o código disponível no g09 e o pacote já preparado a partir dos inputs originais:

```bash
read -r -p 'Endpoint do agente IAedu: ' IAEDU_ENDPOINT
read -r -p 'Channel ID do IAedu: ' IAEDU_CHANNEL_ID
export IAEDU_ENDPOINT IAEDU_CHANNEL_ID
python -u src/annotation/iaedu_agent_api_19c.py \
  --package-dir data/raw/experiment_19c_claude_manual_package01 \
  --output-dir data/raw/experiment_19c_iaedu_api_plan01
```

Com --package-dir, o CLI só cria `api_plan_PRIVATE.json` num diretório novo e ignorado, com 30 previews, correspondência aos IDs, hashes, configuração não secreta e UUIDs de demonstração. Este modo não lê a chave nem faz HTTP. UUIDs do preview são apenas inspeção: o transporte gera outros UUIDs novos ao efetuar cada chamada, inclusive se um pedido anterior tiver falhado. Não há `--send` ou comando de execução em lote. O plano e os contextos continuam privados; `external_transmission_authorized=false` é conservado. O teste sintético abaixo não altera essa autorização para dados reais.

O helper stream_one é uma primitiva de transporte bloqueada por defeito (`network_authorized=False`). O modo sintético dá autorização apenas à sua mensagem constante, não ao pacote real. Nesta implementação só foi chamada com um cliente HTTP simulado. Não se realizaram pedidos autenticados nem smoke tests reais pelo agente de código.

## Teste de ligação no Windows/PowerShell — um exemplo inventado

Na raiz do repositório, o utilizador pode executar o bloco seguinte. Endpoint e canal vêm do painel; a chave deve ser nova, substituindo a exposta anteriormente. Não há chave no histórico da linha de comandos: a leitura é mascarada e a variável de ambiente é removida no fim. Não ativar transcrição/debug HTTP que capture headers. Não é necessário GPU nem qualquer ficheiro de data/raw para iniciar o teste.

```powershell
Set-Location 'C:\Users\Utilizador\Desktop\Tese\Projeto\thesis-ner'
git switch develop
git pull --ff-only origin develop

$env:IAEDU_ENDPOINT = Read-Host 'Endpoint HTTPS do agente (do painel IAedu)'
$env:IAEDU_CHANNEL_ID = Read-Host 'Channel ID (do painel IAedu)'
$iaeduSecret = Read-Host 'Nova chave IAedu' -AsSecureString
$iaeduKeyPointer = [IntPtr]::Zero
$iaeduConnectionDir = 'data/raw/iaedu_connection_test_' + [guid]::NewGuid().ToString('N')
try {
    $iaeduKeyPointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($iaeduSecret)
    $env:IAEDU_API_KEY = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($iaeduKeyPointer)
    & .\venv\Scripts\python.exe src/annotation/iaedu_agent_api_19c.py `
        --synthetic-connection-test --output-dir $iaeduConnectionDir
    $iaeduConnectionExitCode = $LASTEXITCODE
} finally {
    if ($iaeduKeyPointer -ne [IntPtr]::Zero) {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($iaeduKeyPointer)
    }
    Remove-Item Env:IAEDU_API_KEY -ErrorAction SilentlyContinue
    $iaeduSecret.Dispose()
}
Write-Host "Exit code: $iaeduConnectionExitCode"
Write-Host "Artefactos privados: $iaeduConnectionDir"
```

A mensagem é construída exclusivamente a partir do prompt v2 e de uma frase pública inventada sobre AA como testemunha num processo fictício. Não há leitura de inputs/manifestos/30 menções e não existe argumento para alterar a mensagem. Usa um UUID4 novo e não repete o pedido. Um novo teste cria outro diretório/thread; não sobrescrever o primeiro resultado.

O resumo JSON no terminal mostra http_status, assistant_message_extracted, erros e model_metadata_returned com fonte/campo/valor devolvidos. Procura campos estruturados model/model_id/model_name/model_version/provider/deployment/system_fingerprint em eventos e headers de modelo conhecidos, excluindo texto/content do assistente. Se não encontrar, assinala `not_found_in_parsed_metadata` sem preencher com a etiqueta da UI. Não certifica campos ou metadados opacos ainda não interpretados: o corpo integral continua disponível. Uma mensagem extraída num stream interrompido não prova mensagem final completa; verificar também status e completion_evidence no run.json.

Guarda os artefactos abaixo e `connection_test.json`. Não imprime o corpo do assistente nem headers gerais no terminal. Exit 0 significa HTTP 2xx, framing suportado sem erro e texto extraído; não valida papéis jurídicos ou uma identidade backend. Exit 1 indica falha/configuração ou extração não conseguida; consultar os códigos seguros e artefactos locais. Nunca publicar os ficheiros raw ou headers automaticamente.

## Conservação de respostas e metadados

O transporte não segue redirects, não repete pedidos automaticamente e não reusa thread_ids. Guarda, num diretório privado novo por pedido:

- `response_body.bin`: bytes do corpo HTTP entregue por requests, após eventual decoding de transporte/compressão; não é uma captura do fio TLS/HTTP.
- `run.json`: estado HTTP, headers de resposta, tempo, UUID enviado, hash da mensagem e erros seguros. Não guarda objeto requests/prepared_request nem headers de autenticação.
- `stream_frames_PRIVATE.json`: todos os eventos JSON interpretáveis e posições dos erros de framing; metadados/modelo/usage efetivamente devolvidos ficam preservados, sem os substituir pela etiqueta da UI.
- `assistant_output.txt`: concatenação apenas de content string em eventos type=token, derivada e separada do corpo original.

Respostas não-2xx, streams interrompidos, UTF-8 inválido, eventos de erro ou framing desconhecido ficam assinalados e o corpo é preservado, salvo eco da credencial. Não se descartam silenciosamente linhas não JSON como no exemplo didático. SSE/data:, [DONE] ou outro schema ainda não confirmado não são interpretados por heurística: guardar e rever. EOF HTTP não prova um finish_reason do modelo; o protocolo oficial consultado não especifica esse marcador. Não há conversão de falhas em UNKNOWN ou respostas SILVER aprovadas.

Antes de um lote real, confirmar o schema efetivo de resposta e a configuração do agente num ensaio não sensível **separadamente autorizado**. A classificação/revisão semântica continua pendente. Não alimentar o importador Claude manual com respostas desta API: ele exige metadados Anthropic/manual_chat. Uma futura integração de previsões IAedu deve reutilizar o mesmo parser e identificar a origem correta, sem inferir versão/modelo de campos ausentes. O corpo original permanece disponível para reinterpretação sem nova geração.

Comparar a configuração completa (agente, modalidade/API, prompt e controles disponíveis), preservando os quatro eixos definidos na [comparação independente](experiment_19c_second_llm.md). Nenhum benchmark, NER, contexto, offset, prompt ou resultado histórico foi alterado. Nenhuma revisão se tornou gold.

Validação local: **241 testes**, sucesso, **1 integração opcional omitida**; 13 sintéticos do adaptador, incluindo 5 do teste de ligação. Cobrem as 30 mensagens idênticas no modo offline e, separadamente, exatamente uma mensagem inventada no modo sintético, sem acesso ao piloto; UUIDs/multipart, stdout sem chave ou texto do assistente, metadados realmente encontrados e recusa de overrides. Nenhum contexto real foi transmitido, e nenhuma chave real foi usada em teste.
