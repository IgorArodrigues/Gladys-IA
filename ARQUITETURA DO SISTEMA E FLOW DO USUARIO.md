# 🧠 Gladys IA - Sistema de Chat IA com RAG (Retrieval-Augmented Generation)

## 📖 Visão Geral do Sistema

A Gladys IA é um sistema de chat IA que combina os modelos GPT da OpenAI com uma arquitetura RAG (Retrieval-Augmented Generation). O sistema oferece respostas contextuais e precisas ao buscar no seu cofre de documentos e usar a memória de conversa.

### O que é RAG?

**Retrieval-Augmented Generation (RAG)** é uma arquitetura de IA que melhora os Large Language Models (LLMs) ao fornecer contexto relevante recuperado de fontes de conhecimento externas. Em vez de depender apenas dos dados de treinamento do modelo, sistemas RAG:

1. **Recuperam** documentos relevantes de uma base de conhecimento
2. **Aumentam** a pergunta do usuário com esse contexto
3. **Geram** respostas ancoradas nos seus documentos reais

Isso resulta em respostas mais precisas, atualizadas e verificáveis.

---

## 🚀 Benefícios Principais

### 1. **Respostas Ancoradas**
- Respostas baseadas nos SEUS documentos, não só no conhecimento geral da IA
- Reduz alucinações ao fornecer contexto real dos documentos
- Atribuição de fontes: a IA cita quais documentos embasam a resposta

### 2. **Privacidade e Controle dos Dados**
- Documentos permanecem locais no seu cofre
- Nenhum dado enviado a terceiros (apenas API da OpenAI para embeddings e respostas)
- Controle total sobre quais documentos são indexados

### 3. **Busca Inteligente**
- Busca semântica com embeddings vetoriais (não só correspondência de palavras-chave)
- Entende o significado por trás das perguntas
- Encontra conteúdo relevante mesmo com formulações diferentes

### 4. **Memória de Conversa**
- Memória de curto prazo: lembra das trocas recentes no chat atual
- Memória de longo prazo: recupera conversas passadas relevantes
- Respostas personalizadas com base no histórico de conversa

### 5. **Roteamento Inteligente**
- Decide automaticamente se usa documentos locais, busca na web ou ambos
- Otimiza custo e qualidade da resposta
- Adapta-se a diferentes tipos de pergunta

### 6. **Suporte a Múltiplos Formatos**
- Markdown (.md), Word (.docx), Excel (.xlsx), PDF (.pdf), Texto (.txt)
- Divisão automática em chunks para arquivos grandes
- Preserva estrutura e metadados dos documentos

---

## 📊  Diagrama simplificado da Arquitetura do Sistema

```
┌──────────────────────────────────────────────────────────────────────────┐
│                         Gladys IA ARQUITETURA DO SISTEMA                 │
├──────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌─────────────────┐                                                     │
│  │   USER REQUEST  │  "Quais são os principais pontos do meu contrato?"  │
│  └────────┬────────┘                                                     │
│           │                                                              │
│           ▼                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐ │
│  │                      APLICAÇÃO FLASK WEB                            │ │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────────┐   │ │
│  │  │ Authentication│  │   Routes.py  │  │    Chat Interface       │   │ │
│  │  │   (auth.py)   │  │  /api/chat   │  │  (templates/chat.html)  │   │ │
│  │  └──────────────┘  └──────┬───────┘  └──────────────────────────┘   │ │
│  └──────────────────────────┬──────────────────────────────────────────┘ │
│                             │                                            │
│           ┌─────────────────┼─────────────────┐                          │
│           ▼                 ▼                 ▼                          │
│  ┌───────────────┐ ┌───────────────┐ ┌───────────────────────────────┐   │
│  │QUERY INTENT   │ │CONTEXT        │ │CHAT MEMORY                    │   │
│  │ANALYZER       │ │RETRIEVAL      │ │MANAGER                        │   │
│  │               │ │               │ │  ┌─────────────────────────┐  │   │
│  │ • Conversational│ │ • Document   │ │  │Short-term (DB messages)│  │   │
│  │ • List docs   │ │   search      │ │  │Long-term (pgvector)     │  │   │
│  │ • Comprehensive│ │ • Memory     │ │  └─────────────────────────┘  │   │
│  │ • Specific    │ │   context     │ │                               │   │
│  │ • Follow-up   │ │ • Doc hint    │ │  ┌─────────────────────────┐  │   │
│  │   detection   │ │   boost       │ │  │Document Hint Tracking   │  │   │
│  └───────┬───────┘ └───────┬───────┘ │  │(Chat.last_document_used)│  │   │
│          │                 │         │  └─────────────────────────┘  │   │
│          └─────────────────┼─────────┴───────────────────────────────┘   │
│                            ▼                                             │
│  ┌────────────────────────────────────────────────────────────────────┐  │
│  │                        INDEX MANAGER                               │  │
│  │  ┌────────────────────────────┐  ┌──────────────────────────────┐  │  │
│  │  │  PostgreSQL + pgvector     │  │  Document Summaries          │  │  │
│  │  │  (text_chunks, HNSW index) │  │  (DocumentMetadata, etc.)    │  │  │
│  │  └────────────────────────────┘  └──────────────────────────────┘  │  │
│  └──────────────────────────────────┬─────────────────────────────────┘  │
│                                     │                                    │
│                                     ▼                                    │
│  ┌────────────────────────────────────────────────────────────────────┐  │
│  │                          TOOL CALLS (Opcional)                     │  │
│  │  ┌──────────────────────────────────────────────────────────────┐  │  │
│  │  │ ToolsMaster (validação + execução)                           │  │  │
│  │  │ • registra tool schemas (e.g., mathematic tools)             │  │  │
│  │  │ • Valida parametros via validate_and_sanitize                │  │  │
│  │  │ • Executa via modulo call_tool ou função direta              │  │  │
│  │  └──────────────────────────────────────────────────────────────┘  │  │
│  └──────────────────────────────────┬─────────────────────────────────┘  │
│                                     │                                    │
│                                     ▼                                    │
│  ┌────────────────────────────────────────────────────────────────────┐  │
│  │                        MODEL ROUTER                                │  │
│  │  ┌──────────────────────────────────────────────────────────────┐  │  │
│  │  │  Camada de decisão (GPT-4o-mini)                             │  │  │
│  │  │  • Analisa a consulta e o contexto                           │  │  │
│  │  │  • Decide: STANDARD | WEB_SEARCH | WEB_SEARCH_WITH_CONTEXT   │  │  │
│  │  └──────────────────────────────────────────────────────────────┘  │  │
│  └──────────────────────────────────┬─────────────────────────────────┘  │
│                                     │                                    │
│                                     ▼                                    │
│  ┌────────────────────────────────────────────────────────────────────┐  │
│  │                      AI RESPONSE GENERATION                        │  │
│  │  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐  │  │
│  │  │  GPT-4o          │  │ GPT-4o-search    │  │ Combined Mode    │  │  │
│  │  │  (Contexto local) │  │ (Web search)     │  │ (Hibrido)       │  │  │
│  │  └──────────────────┘  └──────────────────┘  └──────────────────┘  │  │
│  └──────────────────────────────────┬─────────────────────────────────┘  │
│                                     │                                    │
│                                     ▼                                    │
│  ┌─────────────────┐                                                     │
│  │   AI RESPONSE   │  "Com base no seu contrato, o principal..."         │
│  └─────────────────┘                                                     │
│                                                                          │
└──────────────────────────────────────────────────────────────────────────┘
```

---

## 🔄 Fluxo Completo da Requisição do Usuário

### Jornada Passo a Passo de uma Pergunta

Quando o usuário envia uma pergunta como *"Quais são os principais pontos do documento do contrato?"*, ocorre o seguinte processo:

---

### **PASSO 1: Recepção da Mensagem do Usuário** 📬
**Arquivo: `routes.py` → endpoint `/api/chat`**

```
Usuário envia mensagem → Flask recebe POST → Valida usuário e chat
```

**O que acontece:**
1. Usuário é autenticado via Flask-Login
2. Propriedade do chat é verificada
3. Limites diários de mensagens são verificados
4. Mensagem do usuário é salva no banco de dados

**Local no código:** `routes.py` linhas 159-210

---

### **PASSO 2: Análise de Intenção da Consulta** 🔍
**Arquivo: `query_intent_analyzer.py` → `analyze_query_intent()`**

```
Mensagem do usuário + Document Hint → Correspondência de padrões → Classificação de intenção
```

**O sistema determina:**
- **`needs_rag`**: Esta consulta precisa de busca em documentos?
  - `False` para cumprimentos: "Bom dia!", "Hello!", "Thanks!"
  - `True` para consultas relacionadas a documentos
  
- **`intent_type`**: Que tipo de consulta é esta?
  - `conversational`: Cumprimentos simples, agradecimentos
  - `list_all_documents`: "Liste todos os meus documentos"
  - `comprehensive_document_search`: "Dê um resumo completo"
  - `comprehensive_term_search`: "Encontre todos os documentos com CNPJ..."
  - `specific_question`: "Qual é o valor do contrato?"
  
- **`is_follow_up_query`** (Novo!): É uma continuação sobre o tópico anterior?
  - Detectado por pronomes: "it", "this", "isso", "nisso"
  - Detectado por frases de continuação: "tell me more", "fale mais"
  - Detectado por consultas curtas (≤6 palavras)
  
- **`document_hint_applied`** (Novo!): O hint foi usado?
  - `True` se follow-up detectado E hint fornecido E nenhum documento diferente mencionado
  
- **`is_specific_document_query`**: Referencia um arquivo específico?
- **`search_terms`**: Termos específicos extraídos (CNPJs, nomes, etc.)
- **`filenames`**: Nomes de documentos detectados (pode incluir hint se aplicado)

**Exemplos de padrões reconhecidos:**
```python
# Padrões em português
"resumo COMPLETO" → comprehensive search
"liste os documentos" → list documents
"o que tem no documento X?" → specific document query

# Padrões em inglês  
"give me a complete analysis" → comprehensive search
"what documents do you have" → list documents
```

**Local no código:** `query_intent_analyzer.py` linhas 285-455

---

### **PASSO 3: Gestão do Histórico** 📚
**Arquivo: `chat_utils/message_handler.py` → `get_chat_history_with_memory_context()`**

```
Mensagens do banco → Truncamento inteligente → Histórico otimizado
```

**O que acontece:**
1. Histórico completo da conversa é recuperado do banco
2. Contador de trocas rastreia quantas mensagens desde o último embedding
3. Mensagens recentes são selecionadas (as que ainda não estão na memória de longo prazo)
4. Mensagens de buffer são adicionadas para continuidade do contexto

**Gestão inteligente do histórico:**
- Evita enviar mensagens já representadas nos embeddings da memória
- Reduz uso de tokens em 60-80% em conversas longas
- Mantém contexto conversacional por meio de mensagens de buffer

**Local no código:** `chat_utils/message_handler.py`

---

### **PASSO 4: Recuperação de Contexto (Núcleo RAG)** 🎯
**Arquivo: `chat_utils/context_retrieval.py` → `get_context_for_query()`**

É aqui que acontece a “mágica” do RAG:

#### 4.0 Recuperação do Document Hint (Novo!)
```
Chat ID → Busca Chat.last_document_used → Document hint para follow-ups
```

**Document Hint Tracking:**
- Recupera o último documento usado neste chat no banco
- Passa o hint para o analisador de intenção para detecção de follow-up
- Permite continuidade quando o usuário faz perguntas de continuação sobre um documento

#### 4.1 Recuperação do Contexto de Memória
```
Consulta atual → Busca vetorial na memória do chat → Conversas passadas relevantes
```

**O Chat Memory Manager fornece:**
- **Memória de curto prazo**: Mensagens recentes da conversa atual
- **Memória de longo prazo**: Conversas passadas semanticamente similares (pgvector em `memory_chunks`)

#### 4.2 Busca em Documentos
```
Consulta + Document Hint → Busca de similaridade pgvector → Chunks relevantes (com boost do hint)
```

**Estratégias de busca por intenção:**

| Intent Type | Strategy | Documents Retrieved | Context Limit | Hint Behavior |
|-------------|----------|---------------------|---------------|---------------|
| `specific_question` | Optimized | 2-4 docs | 8,000 chars | 1.15x boost if follow-up |
| `comprehensive_search` | Comprehensive | 10-15 docs | 15,000 chars | 1.15x boost if follow-up |
| `filename_priority` | Filename match | 5-8 docs | 12,000 chars | Already prioritized |

**Keyword guardrail:** `search_with_summaries()` extrai as palavras-chave do usuário e descarta qualquer resultado cujo texto bruto não mencione pelo menos uma delas. Isso roda antes da sumarização, então chunks irrelevantes não chegam ao construtor de contexto.

#### 4.3 Atualização do Document Hint
```
Documento principal dos resultados → Atualiza Chat.last_document_used → Salva para próxima consulta
```

**Lógica de atualização do hint:**
- Extrai o caminho do documento principal do primeiro resultado da busca
- Atualiza `Chat.last_document_used` no banco
- Limpa o hint antigo se o usuário mencionar explicitamente outro documento
- Preserva o hint em consultas conversacionais (sem RAG)

**Local no código:** `chat_utils/context_retrieval.py` linhas 10-265

---

### **PASSO 5: Decisão de Roteamento do Modelo** 🚦
**Arquivo: `model_router.py` → `decide_model()`**

```
Consulta + Contexto + Histórico → LLM de decisão (GPT-4o-mini) → Escolha do modelo
```

**O roteador analisa e decide:**

| Decision | Model Used | When to Use |
|----------|------------|-------------|
| `standard` | GPT-4o | Consulta pode ser respondida com documentos locais |
| `web_search` | GPT-4o-search-preview | Precisa de informação atual/em tempo real |
| `web_search_with_context` | GPT-4o-search + docs | Precisa de contexto local E informação da web |

**Critérios de decisão:**
- O contexto dos documentos é suficiente?
- A consulta pede eventos atuais ou dados em tempo real?
- A pergunta é pessoal/específica do documento?

**Local no código:** `model_router.py` linhas 48-140

---

### **PASSO 6: Construção do Prompt** 📝
**Arquivo: `routes.py` → Montagem do system prompt**

```
Info do usuário + Contexto + Memória + Histórico → System prompt completo
```

**O prompt padrão inclui:**
```
You are Gladys IA, an assistant with access to notes, documents and conversation memory.
You are talking to {user_name}, today is {current_date}.

=== AVAILABLE CONTEXT ===
Notes and relevant documents:
{retrieved_notes}

Conversation memory:
{memory_context}

=== CRITICAL REQUIREMENT: SOURCE ATTRIBUTION ===
You MUST always cite your sources when responding...

=== GENERAL GUIDELINES ===
1. Use the provided context accurately and directly
2. If context is insufficient, ask for more details
...
```

**Local no código:** `routes.py` linhas 268-336

---

### **PASSO 7: Geração da Resposta da IA** 🤖
**Arquivo: `routes.py` → Chamada à API OpenAI**

```
Prompt completo → API OpenAI → Resposta da IA
```

**O que acontece:**
1. Array final de mensagens é enviado ao modelo selecionado
2. Timeout configurado conforme o tipo de consulta (25s normal, 40s para listagem de documentos)
3. Resposta é recebida e extraída

**Local no código:** `routes.py` linhas 371-386

---

### **PASSO 7.5: Tool Calls Opcionais** 🧰
**Arquivos: `Tools/tools_master.py`, `Tools/mathematic.py`**

Se o modelo solicitar uma chamada de função e o `ModelRouter` permitir tools:
- Os schemas das tools disponíveis são passados ao modelo.
- A tool call retornada é validada por `ToolsMaster.validate_and_sanitize`.
- A tool é executada via dispatcher do módulo (`call_tool`) ou diretamente.
- O resultado é incorporado à resposta final da IA.

Detalhes em `documentation/TOOL_CALLS_README.md`.

---

### **PASSO 8: Armazenamento da Resposta e Atualização da Memória** 💾
**Arquivo: `routes.py` + `chat_utils/response_handler.py`**

```
Resposta da IA → Salvar no banco → Atualizar memória → Rastrear uso
```

**Ações realizadas:**
1. Salvar resposta da IA na tabela de mensagens
2. Rastrear uso de tokens da IA (prompt + completion tokens)
3. Armazenar conversa na memória de longo prazo (embedding em batch)
4. Rastrear decisão do model router para analytics
5. Atualizar contagem restante de mensagens do usuário

**Lógica de batch embedding:**
- Contador rastreia trocas desde o último embedding
- Ao atingir o limite (padrão: 10 trocas), cria batch de embedding
- Várias mensagens combinadas em um único embedding rico

**Local no código:** `routes.py` linhas 389-440

---

### **PASSO 9: Entrega da Resposta** ✅
**Arquivo: `routes.py` → Resposta JSON**

```
Resposta da IA → Formato JSON → Exibição no frontend
```

**A resposta inclui:**
```json
{
  "chat_id": "uuid-here",
  "answer": "Based on your contract document...",
  "message_id": 123,
  "remaining_messages": 50,
  "timing": {
    "total_ms": 2500,
    "breakdown": {
      "save_message": 15,
      "history": 20,
      "context_analysis": 350,
      "model_routing": 800,
      "ai_generation": 1200,
      "save_response": 50,
      "memory_storage": 65
    }
  }
}
```

**Local no código:** `routes.py` linhas 454-471

---

## 📐 Arquitetura Detalhada dos Componentes

### Pipeline de Indexação de Documentos – File Manager (FastAPI Worker)

A indexação de documentos é executada pelo **Index Worker Service**, um microsserviço FastAPI que roda em processo separado. Ele consome jobs de indexação (enfileirados pela aplicação principal ou pelo painel admin), processa arquivos em background e grava chunks e embeddings no mesmo PostgreSQL + pgvector usado pela Gladys IA.

**Arquitetura do Worker**:
- **Entry point**: `main.py` — aplicação FastAPI com lifespan (startup/shutdown).
- **JobProcessor**: loop de polling em background que processa jobs de indexação.
- **Rotas**: `worker_routes` — endpoints de API (health, status, enfileiramento de jobs).
- **Config**: `WorkerConfig` — host (default `0.0.0.0`), port (default `8100`).
- **Banco**: usa o mesmo PostgreSQL da Gladys IA (`DATABASE_URL`).

**Funções de indexação** (módulo `index_manager_worker.py`; ver `documentation/file_manager/INDEX_MANAGER_WORKER.md`):
- **Core**: `chunk_text()`, `embed_text()`, `save_chunk_to_db()`, `rebuild_index()` (backfill pgvector, sem FAISS).
- **Write-heavy**: `save_file_metadata_to_db()`, `cleanup_file_metadata_from_db()`, `remove_chunks_for_file()`, `track_embedding_usage()`, `save_summary_to_document_metadata()`.
- **Leitura/consulta**: `get_file_metadata_from_db()`, `get_existing_summary()`, `file_exists_in_index()`, `get_all_indexed_files()`, `check_file_modified()`.

**Integração**: o worker recebe texto dos **file_readers** (ou equivalente), usa **job_processor** para orquestrar chunking → embedding → armazenamento, e opcionalmente **summarizer** para resumos em `DocumentMetadata`. Modelos de banco compartilhados: `TextChunk`, `FileMetadata`, `DocumentMetadata`, `IndexEmbeddingUsage`.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│           FLUXO DE INDEXAÇÃO DE DOCUMENTOS (Index Worker Service)            │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────────┐                                                    │
│  │ UPLOAD / VAULT      │  contract.pdf, notes.md, data.xlsx                 │
│  │ (job enfileirado)   │                                                    │
│  └──────────┬──────────┘                                                    │
│             │                                                               │
│             ▼                                                               │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │ FILE READERS (file_readers.py)                                        │  │
│  │ • read_markdown() - Analisa arquivos .md                              │  │
│  │ • read_docx() - Extrai texto de Word                                  │  │
│  │ • read_xlsx() - Processa planilhas Excel                              │  │
│  │ • read_pdf() - Extrai texto de PDF                                    │  │
│  │ • read_txt() - Arquivos de texto simples                              │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│             │                                                               │
│             ▼                                                               │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │ TEXT CHUNKING (index_manager_worker.chunk_text)                       │  │
│  │ • Chunks sobrepostos (max_chunk_size default 4000, overlap 200)       │  │
│  │ • Preserva limites de palavra; chunks pequenos fundidos               │  │
│  │ • Metadados: chunk_id, total_chunks, start_char, end_char, file_path  │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│             │                                                               │
│             ▼                                                               │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │ EMBEDDING (index_manager_worker.embed_text)                           │  │
│  │ • OpenAI text-embedding-3-small                                       │  │
│  │ • Vetores 1536 dimensões; truncamento em max_embedding_chars (6000)    │  │
│  │ • Uso de tokens rastreado (track_embedding_usage)                     │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│             │                                                               │
│             ▼                                                               │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │ STORAGE (index_manager_worker.save_chunk_to_db + metadata/summary)     │  │
│  │ • PostgreSQL + pgvector (text_chunks.embedding_vector, índice HNSW)   │  │
│  │ • file_metadata, document_metadata (summaries), IndexEmbeddingUsage   │  │
│  │ • Deduplicação por hash de chunk; rebuild_index para backfill         │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Sistema de Memória do Chat

```
┌────────────────────────────────────────────────────────────────────────────┐
│                    ARQUITETURA DE MEMÓRIA DE CHAT                          │
├────────────────────────────────────────────────────────────────────────────┤
│                                                                            │
│  ┌────────────────────────────────────────────────────────────────────────┐│
│  │                  SHORT-TERM MEMORY                                     ││
│  │  Source: tabela de mensagens (PostgreSQL)                              ││
│  │  Content: Trocas de conversas recentes                                 ││
│  │  Scope: Últimas N mensagens (configurável)                             ││
│  │  Velocidade: Instantânea (consulta ao banco de dados)                  ││
│  └────────────────────────────────────────────────────────────────────────┘│
│                              │                                             │
│                              ▼                                             │
│  ┌────────────────────────────────────────────────────────────────────────┐│
│  │                  LONG-TERM MEMORY                                      ││
│  │  Source: pgvector (memory_chunks)                                      ││
│  │  Content: Trechos de conversa incorporados                             ││
│  │  Scope: Todas as conversas anteriores (busca semântica)                ││
│  │  Velocidade: Rápida (similaridade vetorial)                            ││
│  │                                                                        ││
│  │  Batch Embedding:                                                      ││
│  │  • O contador rastreia as transações desde a última incorporação.      ││
│  │  • No threshold (10), cria incorporação combinada                      ││
│  │  • Reduz as chamadas de API em 90%                                     ││
│  └────────────────────────────────────────────────────────────────────────┘│
│                              │                                             │
│                              ▼                                             │
│  ┌────────────────────────────────────────────────────────────────────────┐│
│  │              INTELLIGENT HISTORY MANAGEMENT                            ││
│  │  • Remove mensagens duplicadas já presentes na memória de longo prazo. ││
│  │  • Adiciona um buffer para continuidade de contexto.                   ││
│  │  • Reduz o uso de tokens em 60-80%                                     ││
│  └────────────────────────────────────────────────────────────────────────┘│
│                                                                            │
└────────────────────────────────────────────────────────────────────────────┘
```

---

## 📊 Árvore de Decisão de Intenção da Consulta

```
                        ┌──────────────────────┐
                        │  Mensagem do usuário │
                        └────────┬─────────────┘
                                 │
                                 ▼
                   ┌────────────────────────────┐
                   │ É conversacional           │
                   │ padrões?                   │
                   │ (Saudações, agradecimentos)│
                   └─────────────┬──────────────┘
                                 │
              ┌──────────────────┴────┐
              │ SIM                   │ NÃO
              ▼                       ▼
    ┌─────────────────┐   ┌─────────────────────────┐
    │ needs_rag=FALSE │   │ Tem padrões de listagem │
    │ intent=         │   │ de documentos?          │
    │ "conversacional"│   │ (liste, show all docs)  │
    │                 │   └─────┬───────────────────┘
    │ ignora busca    │         │    
    │ de documentos   │         ├───────────────────┐
    └─────────────────┘         │ SIM               │ NÃO
                                ▼                   ▼
                    ┌───────────────────┐  ┌───────────────────────┐
                    │ needs_rag=TRUE    │  │ Tem comprehensive     │
                    │ intent=           │  │ patterns?             │
                    │ "list_all_docs"   │  │ (COMPLETO, all, every)│
                    │                   │  └───────────┬───────────┘
                    │ Return lista      │        │
                    │ completa de docs  │        ├──────────────────────────────┐
                    └───────────────────┘        │ SIM                          │ NÃO
                                                 ▼                              ▼
                                    ┌─────────────────────────┐       ┌───────────────────────┐
                                    │ needs_rag=TRUE          │       │ needs_rag=TRUE        │
                                    │ intent=                 │       │ intent=               │
                                    │ "comprehensive_*"       │       │ "specific_            │
                                    │                         │       │  question"            │
                                    │ k=10-15 documentos      │       │                       │
                                    │ contexto de 15000 chars │       │ k=2-4 documentos      │
                                    └─────────────────────────┘       │ contexto de 8000 chars│
                                                                      │ (configurável)        │
                                                                      └───────────────────────┘
```

---

## 🔧 Referência de Configuração

### Arquivos de Configuração Principais

| File | Purpose |
|------|---------|
| `config.json` | Configuração principal (caminho do vault, modelos, thresholds) |
| `config.py` | Classes e constantes de configuração em Python |

### Configurações Importantes

```python
# Search Configuration
SEARCH_CONFIG = {
    "short_query_threshold": 50,      # Chars for short query
    "medium_query_threshold": 150,    # Chars for medium query
    "short_query_results": 2,         # Docs for short queries
    "medium_query_results": 3,        # Docs for medium queries
    "long_query_results": 4,          # Docs for long queries
    "comprehensive_search_results": 10,# Docs for comprehensive
    "max_total_context_length": 8000, # Max chars in context
}

# Chat Memory Configuration
CHAT_MEMORY_CONFIG = {
    "max_short_term_memory": 20,       # Max recent exchanges
    "batch_embedding_threshold": 10,   # Exchanges before embedding
    "relevance_threshold": 0.5,        # Similarity threshold
    "max_memory_results": 5,           # Memory search results
}

# Model Configuration
AI_MODEL = "gpt-4o"                   # Main response model
DECISION_MODEL = "gpt-4o-mini"        # Router decision model
WEB_SEARCH_MODEL = "gpt-4o-search-preview"  # Web search model
```

---

## 📈 Métricas de Performance

### Tempos Típicos de Resposta

| Stage | Time (ms) | Notes |
|-------|-----------|-------|
| Save user message | 10-30 | Database write |
| History retrieval | 20-50 | Database query |
| Context + Intent analysis | 200-500 | pgvector search + patterns |
| Model routing decision | 500-1000 | GPT-4o-mini call |
| AI response generation | 1000-3000 | Main model call |
| Save response | 30-80 | Database + memory |
| **Total** | **1800-4500** | Typical range |

### Otimização de Uso de Tokens

| Feature | Token Savings |
|---------|---------------|
| Query intent (skip RAG for greetings) | 100% for conversational |
| Batch embedding | 90% reduction in embedding calls |
| Smart history management | 60-80% reduction in history tokens |
| Summarized document chunks | 40-60% context reduction |

---

## 🛡️ Recursos de Segurança

1. **Autenticação de usuário**: Flask-Login com hash de senha
2. **Gestão de sessão**: Tokens de sessão seguros
3. **Isolamento de usuário**: Usuários acessam apenas seus próprios chats
4. **Acesso por função**: Painel admin restrito a administradores
5. **Proteção CSRF**: Proteção de formulários do Flask
6. **Segurança da API Key**: Armazenada em configuração, não no código

---

## 📚 Documentação Relacionada

| Document | Description |
|----------|-------------|
| `README.md` | Visão geral do projeto e setup |
| `CHAT_MEMORY_README.md` | Documentação detalhada do sistema de memória |
| `INDEX_MANAGER_README.md` | Indexação e busca de documentos |
| `QUERY_INTENT_README.md` | Padrões de análise de consulta |
| `VECTOR_DB_ARCHITECTURE.md` | Armazenamento PostgreSQL + pgvector |
| `DOCUMENT_SUMMARIES_README.md` | Resumos de documentos gerados por IA |
| `DATABASE.md` | Schema e modelos do banco de dados |

---

## 🎯 Resumo

A Gladys IA oferece uma experiência de chat IA poderosa e que respeita a privacidade, na qual o sistema:

1. **Entende** sua pergunta por meio da análise inteligente de intenção
2. **Recupera** contexto relevante dos seus documentos com busca semântica
3. **Lembra** conversas passadas para respostas personalizadas
4. **Roteia** para o modelo ideal conforme a necessidade da consulta
5. **Gera** respostas ancoradas e com fontes
6. **Aprende** com as interações para melhorar ao longo do tempo

A combinação de arquitetura RAG, roteamento inteligente e memória de conversa resulta em um assistente que entende seus documentos e responde com precisão com base nos seus dados reais.

---

*Última atualização: Dezembro 2025*
*Versão: 2.0*