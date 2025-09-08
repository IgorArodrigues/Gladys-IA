# Módulo Query Intent Analyzer

## Visão Geral
O módulo `query_intent_analyzer.py` fornece análise inteligente de queries para determinar se um usuário quer uma busca abrangente ou uma resposta específica. Isso ajuda o sistema a alternar automaticamente entre estratégias de busca otimizadas e abrangentes.

## Recursos

### 🎯 **Detecção Automática de Intenção**
- **Buscas Abrangentes**: Detecta quando usuários querem análise completa
- **Perguntas Específicas**: Identifica queries focadas e direcionadas
- **Suporte Multi-idioma**: Funciona com padrões em português e inglês

### 🔍 **Reconhecimento de Padrões**
- **Descoberta de Documentos**: "find all documents", "show me every section"
- **Análise Completa**: "resumo COMPLETO", "complete analysis"
- **Busca por Termos**: "documents with CNPJ X", "containing Y"
- **Detecção CNPJ/CPF**: Encontra automaticamente números de identificação

### 🛠 **Fácil de Estender**
- **Adicionar Novos Padrões**: Funções simples para adicionar novas regras de detecção
- **Controle de Prioridade**: Controla quais padrões são verificados primeiro
- **Ferramentas de Teste**: Funções de teste e debugging integradas

## Início Rápido

### Uso Básico
```python
from query_intent_analyzer import analyze_query_intent

# Analisar uma query
result = analyze_query_intent("Me dê um resumo COMPLETO por seção")
print(f"Is comprehensive: {result['is_comprehensive_search']}")
print(f"Intent type: {result['intent_type']}")
print(f"Search terms: {result['search_terms']}")
```

### Adicionando Novos Padrões
```python
from query_intent_analyzer import add_comprehensive_pattern, add_term_extraction_pattern

# Adicionar um novo padrão abrangente (alta prioridade)
add_comprehensive_pattern(r'analise\s+integral', priority=0)

# Adicionar um novo padrão de extração de termos com especificação de grupo de captura
add_term_extraction_pattern(r'que\s+contem\s+([^\s,]+)', capture_group_index=0)
```

## Tipos de Padrões

### 1. Padrões de Busca Abrangente
Estes padrões ativam o modo de busca abrangente:

#### Padrões em Português
- `resumo COMPLETO` - Solicitações de resumo completo
- `COMPLETO por seção` - Análise completa seção por seção
- `analise completa` - Solicitações de análise completa
- `me dê um resumo completo` - Solicitações de resumo completo

#### Padrões em Inglês
- `give me a complete analysis` - Solicitações de análise completa
- `show me all sections` - Solicitações de todas as seções
- `explain all` - Solicitações de explicação abrangente

#### Padrões Gerais
- `all documents` - Solicitações de todos os documentos
- `every section` - Solicitações de toda seção
- `complete coverage` - Solicitações de cobertura completa

### 2. Padrões de Extração de Termos
Estes padrões extraem termos de busca específicos de queries. O sistema agora usa **manipulação inteligente de grupos de captura** para extrair corretamente termos de busca de padrões complexos.

#### Inglês
- `containing [term]` → extrai "term" (grupo de captura único)
- `with [term]` → extrai "term" (grupo de captura único)
- `that have [term]` → extrai "term" (grupo de captura único)

#### Português
- `contendo [termo]` → extrai "termo" (grupo de captura único)
- `com [termo]` → extrai "termo" (grupo de captura único)
- `que tem [termo]` → extrai "termo" (grupo de captura múltiplo, último elemento)
- `falando sobre [termo]` → extrai "termo" (grupo de captura múltiplo, último elemento)
- `resumo de [termo]` → extrai "termo" (grupo de captura múltiplo, último elemento)

#### Manipulação de Grupos de Captura Múltiplos
O sistema manipula inteligentemente padrões com múltiplos grupos de captura:
- **Padrão**: `r'falando\s+(sobre|de)\s+([^\s,]+)'`
- **Query**: "falando sobre contrato"
- **Resultado**: Extrai "contrato" (o termo de busca, não a preposição)

## Referência da API

### Função Principal
```python
def analyze_query_intent(query: str, enable_debug_logging: bool = False) -> Dict
```
**Parâmetros:**
- `query`: String da query do usuário
- `enable_debug_logging`: Se deve imprimir informações de debug

**Retorna:**
- `is_comprehensive_search`: Booleano indicando se busca abrangente é necessária
- `intent_type`: String descrevendo o tipo de intenção
- `search_terms`: Lista de termos de busca extraídos
- `query_lower`: Versão em minúsculas da query

### Funções Utilitárias
```python
def add_comprehensive_pattern(pattern: str, priority: int = None)
def add_term_extraction_pattern(pattern: str, capture_group_index: int = 0)
def get_comprehensive_patterns() -> List[str]
def get_term_extraction_patterns() -> List[tuple]
def test_patterns(test_queries: List[str], enable_debug: bool = True)
```

**Nota**: `add_term_extraction_pattern()` aceita um parâmetro `capture_group_index` para especificar qual grupo de captura contém o termo de busca (índice baseado em 0).

## Exemplos

### Exemplo 1: Análise Completa de Documento
```python
query = "Me dê um resumo COMPLETO por seção do documento"
result = analyze_query_intent(query)

# Resultado:
# {
#     'is_comprehensive_search': True,
#     'intent_type': 'comprehensive_document_search',
#     'search_terms': [],
#     'query_lower': 'me dê um resumo completo por seção do documento'
# }
```

### Exemplo 2: Busca por Termo Específico
```python
query = "Find all documents with CNPJ 00.000.000/0000-00"
result = analyze_query_intent(query)

# Resultado:
# {
#     'is_comprehensive_search': True,
#     'intent_type': 'comprehensive_term_search',
#     'search_terms': ['00.000.000/0000-00', 'cnpj'],
#     'query_lower': 'find all documents with cnpj 00.000.000/0000-00'
# }
```

### Exemplo 3: Pergunta Específica
```python
query = "What is the rental amount?"
result = analyze_query_intent(query)

# Resultado:
# {
#     'is_comprehensive_search': False,
#     'intent_type': 'specific_question',
#     'search_terms': [],
#     'query_lower': 'what is the rental amount?'
# }
```

## Testes

### Executar Testes Integrados
```bash
python query_intent_analyzer.py
```

### Testar Padrões Personalizados
```python
from query_intent_analyzer import test_patterns

test_queries = [
    "Sua query personalizada aqui",
    "Outra query de teste",
    "Teste com termos específicos"
]

test_patterns(test_queries)
```

## Personalização

### Adicionando Novos Idiomas
1. **Adicionar padrões abrangentes** para o novo idioma
2. **Adicionar padrões de extração de termos** para o novo idioma
3. **Testar com queries de exemplo** nesse idioma

### Exemplo: Adicionando Suporte ao Francês
```python
# Adicionar padrões abrangentes em francês
add_comprehensive_pattern(r'analyse\s+compl[èe]te', priority=5)
add_comprehensive_pattern(r'resume\s+int[ée]gral', priority=5)

# Adicionar padrões de extração de termos em francês
add_term_extraction_pattern(r'contenant\s+([^\s,]+)', capture_group_index=0)  # Captura única
add_term_extraction_pattern(r'avec\s+([^\s,]+)', capture_group_index=0)       # Captura única
add_term_extraction_pattern(r'parlant\s+(de|du|des)\s+([^\s,]+)', capture_group_index=1)  # Captura múltipla
```

### Sistema de Prioridade
Padrões são verificados em ordem, então padrões de maior prioridade (números menores) são verificados primeiro:
- `priority=0`: Maior prioridade (verificado primeiro)
- `priority=5`: Prioridade média
- `priority=None`: Menor prioridade (adicionado ao final)

## Integração com Aplicação Principal

O módulo é automaticamente importado e usado em `routes.py`:

```python
from query_intent_analyzer import analyze_query_intent

# Na API de chat
query_intent = analyze_query_intent(
    user_message, 
    enable_debug_logging=PERFORMANCE_CONFIG.get("enable_context_logging", False)
)

# O resultado é usado para determinar estratégia de busca
if query_intent['is_comprehensive_search']:
    # Usar busca abrangente com mais resultados
    stats = index_manager.get_stats()
    k = min(SEARCH_CONFIG["comprehensive_search_results"], stats["total_chunks"])
    search_strategy = "comprehensive"
else:
    # Usar busca otimizada para perguntas específicas
    k = SEARCH_CONFIG["short_query_results"]
    search_strategy = "optimized"
```

### Integração de Estratégia de Busca
A análise de intenção da query influencia diretamente o comportamento da busca:

1. **Buscas Abrangentes**: 
   - Usa mais resultados de busca (`k` é maior)
   - Inclui descoberta de documentos baseada em termos
   - Constrói contexto maior para respostas de IA

2. **Perguntas Específicas**:
   - Usa menos resultados, mais focados
   - Otimizado para respostas rápidas e direcionadas
   - Contexto menor para processamento mais rápido

## Melhores Práticas

### 1. **Design de Padrões**
- Use padrões específicos primeiro, padrões gerais por último
- Teste padrões com queries reais de usuários
- Evite padrões conflitantes

### 2. **Performance**
- Mantenha padrões simples e eficientes
- Use âncoras regex (`^`, `$`, `\b`) quando apropriado
- Teste com grandes números de queries

### 3. **Manutenção**
- Documente novos padrões com exemplos
- Teste após adicionar novos padrões
- Use as ferramentas de teste integradas

## Solução de Problemas

### Problemas Comuns

1. **Padrão não correspondendo**
   - Verifique sintaxe regex
   - Verifique prioridade do padrão
   - Teste com `test_patterns()`

2. **Falsos positivos**
   - Torne padrões mais específicos
   - Use limites de palavra (`\b`)
   - Ajuste ordem dos padrões

3. **Problemas de performance**
   - Simplifique padrões regex complexos
   - Reduza número total de padrões
   - Use construções regex eficientes

### Modo Debug
Habilite logging de debug para ver o que está acontecendo:
```python
result = analyze_query_intent("Sua query", enable_debug_logging=True)
```

Isso mostrará:
- Passos de análise da query
- Resultados de correspondência de padrões
- Extração de termos de busca
- Classificação final de intenção

## Melhorias Recentes

### 🚀 **Manipulação Aprimorada de Grupos de Captura (v2.0)**
O sistema agora manipula inteligentemente padrões regex complexos com múltiplos grupos de captura:

#### Antes (v1.0):
```python
# Problema: Sempre assumia que termo de busca era o último grupo de captura
pattern = r'falando\s+(sobre|de)\s+([^\s,]+)'
# Query: "falando sobre contrato"
# Resultado: ['sobre', 'contrato']  # Errado! Incluiu preposição
```

#### Depois (v2.0):
```python
# Solução: Especificação explícita de grupo de captura
pattern = (r'falando\s+(sobre|de)\s+([^\s,]+)', 1)  # Extrair grupo 1 (o termo de busca)
# Query: "falando sobre contrato"  
# Resultado: ['contrato']  # Correto! Apenas o termo de busca
```

### 🔧 **Otimizações de Performance**
- **Busca Eficiente**: Substituiu varredura de texto por força bruta por busca vetorial otimizada
- **Gerenciamento de Memória**: Eliminou carregamento desnecessário de todos os chunks na memória
- **Integração com Database**: Aproveita arquitetura existente do IndexManager baseada em database
- **Tratamento de Erro Aprimorado**: Melhor manipulação de conexões de database e casos extremos
- **API Consistente**: Tipos de retorno e assinaturas de função padronizados

## Melhorias Futuras

- **Machine Learning**: Treinar com queries reais de usuários
- **Consciência de Contexto**: Considerar histórico de conversação
- **Preferências do Usuário**: Lembrar profundidade de busca preferida do usuário
- **Modelos Multi-idioma**: Suporte para mais idiomas
- **Aprendizado de Padrões**: Aprender automaticamente novos padrões do uso
- **Compreensão Semântica**: Melhor compreensão do contexto e intenção da query

---

*Última atualização: Setembro 2025*
