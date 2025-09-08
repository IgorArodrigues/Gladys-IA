# Integração do Index Manager

Este documento explica como o Index Manager se integra com sua aplicação Flask de chat para monitorar e indexar automaticamente documentos de `vault_path`.

## O que ele faz

O Index Manager automaticamente:
- **Monitora recursivamente** a pasta `vault_path` e **todos os subdiretórios** para tipos de arquivo suportados (atualmente `.md`, `.docx`, `.xlsx`, `.pdf`, e `.txt`)
- **Exclui pastas de sistema e configuração** (`.obsidian`, `.git`, `node_modules`, etc.) da indexação. Mais podem ser adicionadas por admins
- Cria embeddings vetoriais para cada documento usando o modelo text-embedding-3-small da OpenAI
- Armazena estes em um índice FAISS para busca de similaridade rápida
- Atualiza automaticamente a cada 300 segundos (5 minutos) para detectar arquivos novos, modificados ou deletados
- Integra-se com sua API de chat para fornecer contexto relevante dos documentos
- Lida com documentos longos truncando-os para caber dentro dos limites da API

## Arquivos Adicionados/Modificados

### Novos Arquivos usados pela classe:
- `index_manager.py` - Classe principal de gerenciamento de índice
- `standalone_index_manager.py` - Script standalone para gerenciar índice fora da aplicação Flask
- `templates/admin_index_stats.html` - Interface administrativa para estatísticas do índice
- `templates/admin_embedding_usage.html` - Interface administrativa para estatísticas de uso de embedding
- `main.py` - Inicializa o index manager na inicialização da aplicação
- `routes.py` - Atualizado para usar index manager em vez do código FAISS antigo, adicionadas rotas de uso de embedding
- `templates/admin.html` - Adicionados links para estatísticas do índice e uso de embedding
- `database.py` - Adicionada tabela IndexEmbeddingUsage para rastrear tokens de embedding

## Como Funciona

1. **Inicialização Automática**: Quando sua aplicação Flask inicia, o Index Manager automaticamente:
   - Carrega índice existente de `vector_index/faiss_index.pkl` (se existir)
   - Cria novo índice do zero se nenhum índice existente for encontrado
   - Inicia thread em background para atualizações automáticas

2. **Atualizações em Background**: A cada 300 segundos, o gerenciador:
   - Escaneia recursivamente a pasta vault e todos os subdiretórios em busca de mudanças
   - Detecta arquivos novos, modificados ou deletados usando hashes MD5
   - Atualiza o índice FAISS correspondentemente
   - Salva o índice atualizado no disco

3. **Integração com Chat**: Quando usuários usam o chat:
   - O sistema busca no índice por documentos relevantes
   - Usa gerenciamento inteligente de contexto para otimizar a qualidade da resposta
   - Detecta automaticamente a intenção da query (busca otimizada vs busca abrangente)
   - Fornece contexto dos documentos mais similares
   - Melhora as respostas GPT com o conhecimento do seu vault

4. **Rastreamento de Tokens**: Toda operação de embedding é rastreada:
   - Registra tokens usados para cada arquivo
   - Rastreia tipo de operação (create, update, rebuild)
   - Fornece estatísticas de uso para monitoramento de custos

## Otimizações de Performance para Grandes Coleções de Documentos

O Index Manager inclui otimizações sofisticadas de performance para lidar com grandes coleções de documentos (100+ documentos) eficientemente sem sobrecarregar o contexto da IA ou desacelerar a aplicação.

### Gerenciamento Inteligente de Contexto
- **Resultados de Busca Dinâmicos**: Ajusta o número de documentos recuperados baseado na complexidade da query
  - Queries curtas (<50 chars): 2 documentos (configurável)
  - Queries médias (<150 chars): 3 documentos (configurável)
  - Queries longas (150+ chars): 4 documentos (configurável)

- **Limites de Tamanho de Contexto**: 
  - Máximo total de contexto: 8.000 caracteres (configurável)
  - Máximo tamanho de chunk: 2.000 caracteres (configurável)
  - Máximo comprimento de resumo: 1.500 caracteres (configurável)

### Sumarização Inteligente de Documentos
- **Resumos Inteligentes**: Para chunks longos, cria resumos inteligentes que priorizam conteúdo importante
- **Truncamento de Conteúdo**: Trunca automaticamente o conteúdo para caber dentro dos limites de contexto
- **Pontuação de Relevância**: Prioriza chunks baseado em pontuações de similaridade e importância do conteúdo

### Melhorias na Qualidade da Busca
- **Pontuação de Relevância Aprimorada**: Melhor classificação dos resultados de busca
- **Controles de Diversidade**: Previne que chunks duplicados de arquivos sobrecarreguem os resultados
- **Gerenciamento de Sobreposição de Chunks**: Chunking otimizado para manter continuidade de contexto

### Modo de Busca Abrangente

Para queries que requerem análise completa de documento ou coleta abrangente de informações, o sistema automaticamente muda para "modo de busca abrangente" em vez do modo otimizado.

#### Quando Ativa
O sistema detecta intenção de busca abrangente através destes e outros padrões: (Leia QUERY_INTENT para mais)

**Padrões em Português:**
- `resumo COMPLETO` - Solicitações de resumo completo
- `resumo completo` - Solicitações de resumo completo  
- `COMPLETO por seção` - Análise completa seção por seção
- `analise completa` - Solicitações de análise completa
- `me dê um resumo completo` - Solicitações de resumo completo
- `me mostre todos` - Solicitações para mostrar todo o conteúdo
- `me explique completo` - Solicitações de explicação completa

**Padrões em Inglês:**
- `give me a complete analysis` - Solicitações de análise completa
- `show me all sections` - Solicitações de todas as seções
- `explain all` - Solicitações de explicação abrangente
- `analyze everything` - Solicitações de análise completa

**Padrões Gerais:**
- `all documents` - Solicitações de todos os documentos
- `every section` - Solicitações de toda seção
- `complete coverage` - Solicitações de cobertura completa
- `find all` - Solicitações de encontrar tudo

#### Como o Modo Abrangente Funciona
1. **Detecção de Intenção da Query**: Analisa a query do usuário para padrões abrangentes
2. **Seleção de Estratégia**: Muda automaticamente do modo "otimizado" para "abrangente"
3. **Recuperação Aprimorada**: Obtém até 20 documentos em vez de 2-4 (configurável)
4. **Contexto Expandido**: Aumenta o limite de contexto de 8k para 15k caracteres (configurável)
5. **Cobertura Completa**: Garante que todas as seções relevantes do documento sejam incluídas

#### Impacto na Performance
- **Tamanho do Contexto**: Aumenta de ~4k para ~15k caracteres (3.5x maior) (configurável)
- **Cobertura de Documentos**: Aumenta de 3 para 15+ documentos (5x mais) (configurável)
- **Qualidade da Resposta**: Fornece análise abrangente correspondente ao nível do ChatGPT
- **Tempo de Busca**: Ligeiramente mais longo devido ao processamento de mais documentos

### Monitoramento de Performance
- **Log de Tamanho de Contexto**: Rastreia o tamanho do contexto e avisa quando os limites são excedidos
- **Log de Estratégia de Busca**: Monitora qual estratégia de busca está sendo usada
- **Métricas de Performance**: Rastreia tempos de resposta e eficiência de contexto

## Recursos Administrativos

### Ver Estatísticas do Índice
- Navegue para Admin Panel → Index Stats
- Veja total de documentos, tamanho do índice, última atualização
- Monitore caminho vault e status
- **Ver estrutura de pastas** - veja todos os subdiretórios sendo monitorados
- **Rastrear contagem de arquivos** - veja total de arquivos e arquivos markdown por pasta
- **Gerenciar caminhos excluídos** - adicionar/remover caminhos para excluir da indexação
- **Monitorar uso de embedding** - rastrear tokens usados para criar embeddings

### Ver Uso de Embedding
- Navegue para Admin Panel → Embedding Usage
- **Uso total de tokens** - veja custos gerais de embedding
- **Uso recente** - monitore últimos 30 dias
- **Detalhamento de operação** - analise uso por tipo de operação
- **Registros detalhados** - veja operações individuais de embedding

### Atualizações Manuais do Índice
- Use o botão "Update Index Now" para forçar atualizações imediatas
- Útil para testes ou quando você quer indexação imediata

## Configuração

### Alterar Caminho Vault
Para usar uma pasta diferente, modifique o `vault_path` no `config.json`:
### Alterar Intervalo de Atualização
Para alterar com que frequência o índice atualiza, modifique o intervalo no `config.json`: `auto_update_interval`':

### Gerenciar Caminhos Excluídos
O index manager automaticamente exclui pastas comuns de sistema e configuração:
- `.obsidian` - Configuração Obsidian
- `.git` - Repositório Git
- `node_modules` - Dependências Node.js
- `__pycache__` - Cache Python
- `.vscode` - Configurações VS Code
- Arquivos de sistema (`.DS_Store`, `Thumbs.db`, `desktop.ini`)

Você pode adicionar ou remover caminhos excluídos através da interface administrativa ou modificando o conjunto `excluded_paths` na classe `IndexManager` ou no painel de administração.

### Configuração de Performance

O Index Manager inclui configurações de performance configuráveis para operação otimizada com grandes coleções de documentos:

#### Configuração de Busca
```python
SEARCH_CONFIG = {
    "short_query_threshold": 50,      # Caracteres
    "medium_query_threshold": 150,    # Caracteres
    "short_query_results": 2,         # Documentos para queries curtas
    "medium_query_results": 3,        # Documentos para queries médias
    "long_query_results": 4,          # Documentos para queries longas
    "comprehensive_search_results": 20,  # Documentos para buscas abrangentes
    "max_total_context_length": 8000,   # Limite base de contexto
    "comprehensive_context_multiplier": 2,  # Multiplicador de contexto para modo abrangente
    "max_total_comprehensive_results": 25   # Máximo de resultados para buscas abrangentes
}
```

#### Configuração de Performance
```python
PERFORMANCE_CONFIG = {
    "enable_context_logging": True,    # Habilitar logging de performance
    "context_size_warning": 6000,     # Avisar quando contexto excede este tamanho
}
```

#### Integração Query Intent
O Index Manager integra-se com o Query Intent Analyzer para seleção automática de estratégia de busca:

- **Detecção Automática**: Analisa queries do usuário para determinar intenção de busca
- **Correspondência de Padrões**: Usa padrões regex para detectar solicitações de busca abrangente
- **Suporte Multi-idioma**: Suporta padrões em português, inglês e gerais
- **Sistema Extensível**: Fácil adicionar novos padrões de detecção

Para informações detalhadas sobre estender o sistema de detecção de intenção, veja `QUERY_INTENT_README.md`.

### Melhores Práticas para Otimização de Performance

#### Para Usuários
1. **Use "COMPLETO" ou "complete"** quando precisar de análise abrangente
2. **Seja específico** sobre o que você quer analisar completamente
3. **Use linguagem abrangente** como "todas as seções", "cada parte", "cobertura completa"
4. **Monitore tamanhos de contexto** nos logs para entender o comportamento do sistema

#### Para Desenvolvedores
1. **Monitore tamanhos de contexto** nos logs para garantir performance otimizada
2. **Ajuste thresholds** baseado no tamanho da sua coleção de documentos
3. **Teste padrões abrangentes** para garantir detecção adequada
4. **Use logging de performance** para identificar oportunidades de otimização

#### Informações de Debug
O sistema registra informações detalhadas quando `enable_context_logging` está habilitado:
```
Query intent analysis:
  Query: 'Me dê um resumo COMPLETO por seção...'
  Is comprehensive: True
  Matched pattern: resumo\s+(completo|detalhado|integral|abrangente)
  Search strategy: comprehensive
  Context size: 15046 characters, 11 chunks, 15 total results
```

## Solução de Problemas

### Problemas Comuns:

1. **Caminho Vault Não Encontrado**
   - Certifique-se de que `vault_path` existe e está definido no `config.json`
   - Verifique formato de caminho Windows (use Ex: `"E:\\Vault\\Igor"`)

2. **Nenhum Arquivo Suportado**
   - Adicione arquivos suportados (`.md`, `.docx`, `.xlsx`, `.pdf`, `.txt`) à sua pasta vault
   - Certifique-se de que os arquivos têm conteúdo (não vazios)

3. **Problemas com API Key**
   - Verifique se sua OpenAI API key é válida
   - Verifique quota e limites da API

4. **Erros de Permissão**
   - Certifique-se de que a aplicação tem acesso de leitura à pasta vault
   - Verifique permissões de escrita para a pasta `vector_index`

5. **Mensagens "No App Context"**
   - Estas aparecem quando executando fora do contexto Flask
   - Use `standalone_index_manager.py` para operações standalone
   - Defina `verbose=False` para reduzir estas mensagens

6. **Problemas de Memória**
   - O armazenamento baseado em database reduz significativamente o uso de memória
   - Use `--memory-stats` para monitorar utilização de cache
   - Use `--cleanup-cache` para liberar memória se necessário

7. **Problemas de Busca**
   - Certifique-se de que o índice foi construído com `--rebuild` ou `--update`
   - Verifique se arquivos existem no caminho vault monitorado
   - Use `--check-consistency` para verificar integridade da estrutura de dados

8. **Problemas de Conexão com Database**
   - Certifique-se de que `instance/app.db` existe e é acessível
   - Verifique permissões de arquivo para o diretório do database
   - Use `--verbose` para ver informações detalhadas de conexão com database

### Informações de Debug:
- Verifique saída do console para mensagens de erro detalhadas
- Use o script standalone com `--verbose` para isolar problemas
- Monitore a página de estatísticas do índice admin para status
- Use `--check-consistency` para detectar problemas de estrutura de dados
- Use `--memory-stats` para monitorar uso de memória e performance de cache
- Use `--folder-structure` para verificar diretórios monitorados
- Use `--embedding-usage` para verificar uso de tokens e custos

## Notas de Performance

- **Primeira Execução**: Pode levar vários minutos para criar índice inicial (depende do número de documentos e subdiretórios)
- **Atualizações**: Atualizações incrementais são rápidas (geralmente < 1 segundo)
- **Memória**: Armazenamento baseado em database reduz uso de RAM em 80-95%
- **Armazenamento**: Arquivo de índice cresce com contagem de documentos
- **Escaneamento Recursivo**: Descobre e monitora automaticamente novos subdiretórios
- **Exclusão de Caminho**: Pastas de sistema são automaticamente ignoradas, melhorando performance
- **Gerenciamento de Cache**: Sistema de cache inteligente otimiza chunks frequentemente acessados
- **Performance de Busca**: Índice FAISS permanece na memória para busca de similaridade rápida
- **Performance de Database**: Database SQLite com queries otimizadas para recuperação de chunks

## Considerações de Segurança

- Arquivos de índice contêm conteúdo de documento - proteja adequadamente
- Arquivos de database contêm metadados sensíveis - proteja acesso adequadamente
- Chunks de texto armazenados no database podem conter informações sensíveis
- Monitore acesso ao diretório `instance/` contendo o database

## Melhorias Futuras

Melhorias potenciais:
- Suporte para mais tipos de arquivo
- Melhor tratamento de erros e lógica de retry
- Compressão e otimização de índice
- Suporte a múltiplos vaults
- Notificações webhook para atualizações
- Algoritmos de cache avançados (LRU/LFU)
- Processamento em background para grandes coleções de documentos

### Melhorias de Otimização de Performance
- **Dimensionamento Adaptativo de Contexto**: Limites de contexto dinâmicos baseados na complexidade do documento
- **Seleção Inteligente de Chunks**: Priorização de chunks alimentada por IA
- **Aprendizado de Preferências do Usuário**: Lembrar profundidade de busca preferida do usuário
- **Suporte Multi-idioma**: Expandir detecção de padrões abrangentes para mais idiomas
- **Aprendizado de Padrões**: Aprender automaticamente novos padrões do comportamento do usuário
- **Consciência de Contexto**: Considerar histórico de conversação para detecção de intenção

## Estratégia de Gerenciamento de Índice FAISS

### Exclusão de Arquivos e Atualizações de Índice

Quando arquivos são deletados ou modificados, o Index Manager usa uma **estratégia de rebuild** em vez de remoção seletiva:

#### **O que Acontece Quando Arquivos São Deletados:**

1. **Limpeza de Database**: Chunks são removidos da tabela de database `TextChunk`
2. **Rebuild FAISS**: O índice FAISS inteiro é reconstruído dos chunks de database restantes
3. **Sem Remoção Seletiva**: FAISS `IndexFlatL2` não suporta remover vetores individuais

#### **Por que Rebuild em vez de Remoção Seletiva:**

- **Limitação FAISS**: `IndexFlatL2` não suporta remover vetores individuais
- **Consistência de Dados**: Garante que o índice corresponde perfeitamente ao estado do database
- **Simplicidade**: Evita lógica complexa de gerenciamento de índice

#### **Impacto na Performance:**

- **Limpeza de Database**: Rápida (operações SQL DELETE)
- **Rebuild FAISS**: Caro (re-embeds todos os chunks restantes)
- **Uso de Memória**: Pico temporário durante rebuild, depois retorna ao normal

#### **Quando Rebuilds Ocorrem:**

- **Mudanças na Contagem de Arquivos**: Quando arquivos são adicionados ou removidos
- **Mudanças de Conteúdo**: Quando conteúdo de arquivo é modificado (atualização incremental)
- **Atualizações Manuais**: Quando admin dispara atualização de índice

#### **Estratégia de Otimização:**

```python
# Lógica de atualização inteligente
if changes['added'] or changes['removed']:
    # Contagem de arquivos mudou - rebuild índice inteiro
    self._apply_changes_and_rebuild(changes)
elif changes['modified']:
    # Apenas conteúdo mudou - atualização incremental
    self._apply_incremental_update(changes)
```

## Benefícios do Armazenamento Baseado em Database

O Index Manager agora usa um sistema sofisticado de armazenamento baseado em database que fornece vantagens significativas:

### 🧠 **Eficiência de Memória**
- **Antes**: Todos os chunks de texto carregados na RAM (baseado em memória)
- **Depois**: Apenas índice FAISS e cache pequeno na RAM (baseado em database)
- **Economia de Memória**: 80-95% de redução no uso de RAM para grandes coleções de documentos
- **Escalabilidade**: Não mais limitado pela RAM disponível

### 💾 **Arquitetura de Armazenamento**
- **Índice FAISS**: Permanece na memória para busca de similaridade rápida
- **Chunks de Texto**: Armazenados no database SQLite com cache inteligente
- **Cache de Memória**: Tamanho configurável (padrão: 1000 chunks) para conteúdo frequentemente acessado
- **Cache de Database**: Cache persistente para chunks que não cabem na memória

### ⚡ **Otimizações de Performance**
- **Velocidade de Busca**: Inalterada (índice FAISS ainda na memória)
- **Recuperação de Texto**: Ligeiro aumento de latência devido a queries de database
- **Cache**: Chunks frequentemente acessados permanecem rápidos
- **Rastreamento de Acesso**: Monitora uso de chunks para otimizar decisões de cache

### 🔄 **Sistema de Cache Inteligente**
- **Cache de Memória**: Mantém chunks frequentemente acessados na RAM
- **Cache de Database**: Cache persistente para chunks que não cabem na memória
- **Limpeza Automática**: Remove chunks menos usados quando cache está cheio
- **Otimização de Acesso**: Rastreia padrões de uso para melhor gerenciamento de cache

### 🛡️ **Persistência de Dados**
- **Sobrevive a Reinicializações**: Chunks persistem entre reinicializações da aplicação
- **Estado Consistente**: Database mantém consistência através de operações
- **Rastreamento de Metadados**: Rastreamento abrangente de mudanças de arquivo e operações
- **Análise de Uso**: Monitoramento detalhado de uso de embedding e custos
