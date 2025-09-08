# Documentação do Banco de Dados

## Visão Geral

Este documento fornece documentação abrangente para a estrutura do banco de dados Gladys IA, incluindo schemas de tabelas, relacionamentos, índices e consultas importantes para debugging e manutenção.

## Schema do Banco de Dados

### Tabelas Principais

#### 1. Gerenciamento de Usuários

##### Tabela `user`
Informações primárias de autenticação e perfil do usuário.

| Coluna | Tipo | Restrições | Descrição |
|--------|------|-------------|-------------|
| id | INTEGER | PRIMARY KEY | Identificador único do usuário |
| username | VARCHAR(50) | UNIQUE, NOT NULL | Nome de login do usuário |
| email | VARCHAR(100) | UNIQUE, NOT NULL | Endereço de email do usuário |
| password_hash | VARCHAR(255) | NOT NULL | Senha criptografada |
| first_name | VARCHAR(50) | | Primeiro nome do usuário |
| last_name | VARCHAR(50) | | Sobrenome do usuário |
| created_at | DATETIME | DEFAULT utcnow() | Timestamp de criação da conta |
| user_role | VARCHAR(20) | DEFAULT 'free' | Papel do usuário (free, premium, pro, admin) |
| messages_used | INTEGER | DEFAULT 0 | Total de mensagens enviadas pelo usuário |

**Índices:**
- `idx_user_role` - Consultas baseadas em papel
- `idx_user_created_at` - Consultas de data de registro
- `idx_user_messages_used` - Verificações de limite de mensagens

**Limites por Papel:**
- free: 20 mensagens
- premium: 50 mensagens
- pro: 100 mensagens
- admin: ilimitado

##### Tabela `user_sessions`
Gerenciamento de sessões de usuário para aplicação de login único.

| Coluna | Tipo | Restrições | Descrição |
|--------|------|-------------|-------------|
| id | INTEGER | PRIMARY KEY | ID do registro de sessão |
| user_id | INTEGER | FOREIGN KEY | Referência para user.id |
| session_id | VARCHAR(255) | UNIQUE, NOT NULL | ID da sessão Flask |
| ip_address | VARCHAR(45) | | Endereço IP do cliente |
| user_agent | TEXT | | Informações do navegador/cliente |
| created_at | DATETIME | DEFAULT utcnow() | Hora de criação da sessão |
| last_accessed | DATETIME | DEFAULT utcnow() | Timestamp da última atividade |
| is_active | BOOLEAN | DEFAULT TRUE | Status da sessão |

**Índices:**
- `idx_user_session_user_id` - Consultas de sessão do usuário
- `idx_user_session_is_active` - Filtragem de sessões ativas
- `idx_user_session_last_accessed` - Limpeza de sessões
- `idx_user_session_user_active` - Sessões ativas do usuário

#### 2. Sistema de Chat

##### Tabela `chat`
Containers de conversas de chat.

| Coluna | Tipo | Restrições | Descrição |
|--------|------|-------------|-------------|
| id | VARCHAR(36) | PRIMARY KEY | Identificador UUID do chat |
| user_id | INTEGER | FOREIGN KEY | Referência para user.id |
| title | VARCHAR(200) | | Título do chat |
| created_at | DATETIME | DEFAULT utcnow() | Hora de criação do chat |

**Índices:**
- `idx_chat_user_id` - Chats do usuário
- `idx_chat_created_at` - Ordenação cronológica
- `idx_chat_user_created` - Chats do usuário por data

##### Tabela `message`
Mensagens individuais dentro dos chats.

| Coluna | Tipo | Restrições | Descrição |
|--------|------|-------------|-------------|
| id | VARCHAR(36) | PRIMARY KEY | Identificador UUID da mensagem |
| chat_id | VARCHAR(36) | FOREIGN KEY | Referência para chat.id |
| role | VARCHAR(20) | NOT NULL | Papel da mensagem (user, assistant) |
| content | TEXT | NOT NULL | Conteúdo da mensagem |
| timestamp | DATETIME | DEFAULT utcnow() | Timestamp da mensagem |

**Índices:**
- `idx_message_chat_id` - Mensagens do chat
- `idx_message_timestamp` - Ordenação cronológica
- `idx_message_chat_timestamp` - Mensagens do chat por tempo

#### 3. Rastreamento de Uso

##### Tabela `ai_usage`
Rastreamento de uso de modelos de IA para cobrança e análise.

| Coluna | Tipo | Restrições | Descrição |
|--------|------|-------------|-------------|
| id | INTEGER | PRIMARY KEY | ID do registro de uso |
| user_id | INTEGER | FOREIGN KEY | Referência para user.id |
| model | VARCHAR(50) | NOT NULL | Modelo de IA usado |
| prompt | TEXT | NOT NULL | Prompt do usuário |
| prompt_tokens | INTEGER | NOT NULL | Contagem de tokens de entrada |
| completion_tokens | INTEGER | NOT NULL | Contagem de tokens de saída |
| total_tokens | INTEGER | NOT NULL | Uso total de tokens |
| created_at | DATETIME | DEFAULT utcnow() | Timestamp de uso |

**Índices:**
- `idx_ai_usage_user_id` - Consultas de uso do usuário
- `idx_ai_usage_created_at` - Análise baseada em tempo
- `idx_ai_usage_user_created` - Uso do usuário ao longo do tempo
- `idx_ai_usage_model` - Rastreamento específico do modelo

##### Tabela `user_daily_message_count`
Rastreamento de contagem diária de mensagens para limitação de taxa.

| Coluna | Tipo | Restrições | Descrição |
|--------|------|-------------|-------------|
| id | INTEGER | PRIMARY KEY | ID do registro de contagem |
| user_id | INTEGER | FOREIGN KEY | Referência para user.id |
| total_messages | INTEGER | NOT NULL, DEFAULT 0 | Mensagens enviadas hoje |
| date | DATE | NOT NULL | Data da contagem |
| created_at | DATETIME | DEFAULT utcnow() | Hora de criação do registro |

**Restrições:**
- `unique_user_date` - Um registro por usuário por data

**Índices:**
- `idx_daily_count_user_id` - Contagens diárias do usuário
- `idx_daily_count_date` - Consultas baseadas em data
- `idx_daily_count_user_date` - Contagens diárias do usuário

##### Tabela `index_embedding_usage`
Rastreamento de uso de modelos de embedding.

| Coluna | Tipo | Restrições | Descrição |
|--------|------|-------------|-------------|
| id | INTEGER | PRIMARY KEY | ID do registro de uso |
| file_path | VARCHAR(500) | NOT NULL | Arquivo sendo embedado |
| model | VARCHAR(50) | NOT NULL | Modelo de embedding usado |
| text_length | INTEGER | NOT NULL | Comprimento do texto antes da truncagem |
| tokens_used | INTEGER | NOT NULL | Tokens usados para embedding |
| operation | VARCHAR(20) | NOT NULL | Tipo de operação (create, update, rebuild) |
| created_at | DATETIME | DEFAULT utcnow() | Timestamp de uso |

**Índices:**
- `idx_embedding_usage_file_path` - Rastreamento específico do arquivo
- `idx_embedding_usage_created_at` - Análise baseada em tempo
- `idx_embedding_usage_operation` - Consultas de tipo de operação
- `idx_embedding_usage_model` - Rastreamento específico do modelo

#### 4. Gerenciamento de Arquivos

##### Tabela `file_metadata`
Metadados do sistema de arquivos para detecção de mudanças.

| Coluna | Tipo | Restrições | Descrição |
|--------|------|-------------|-------------|
| id | INTEGER | PRIMARY KEY | ID do registro de metadados |
| file_path | VARCHAR(500) | UNIQUE, NOT NULL | Caminho completo do arquivo |
| mtime | FLOAT | NOT NULL | Hora de modificação do arquivo |
| size | INTEGER | NOT NULL | Tamanho do arquivo em bytes |
| hash | VARCHAR(32) | NOT NULL | Hash MD5 do conteúdo do arquivo |
| last_checked | DATETIME | DEFAULT utcnow() | Última verificação de metadados |
| created_at | DATETIME | DEFAULT utcnow() | Hora de criação do registro |

**Índices:**
- `idx_file_metadata_mtime` - Verificações de hora de modificação
- `idx_file_metadata_size` - Consultas de tamanho do arquivo
- `idx_file_metadata_hash` - Consultas de hash de conteúdo
- `idx_file_metadata_last_checked` - Timestamps de verificação

##### Tabela `document_metadata`
Metadados específicos de documentos para indexação.

| Coluna | Tipo | Restrições | Descrição |
|--------|------|-------------|-------------|
| id | INTEGER | PRIMARY KEY | ID do registro de metadados |
| file_path | VARCHAR(500) | UNIQUE, NOT NULL | Caminho completo do arquivo |
| file_name | VARCHAR(255) | NOT NULL | Apenas o nome do arquivo |
| folder_path | VARCHAR(500) | NOT NULL | Caminho do diretório |
| file_type | VARCHAR(10) | NOT NULL | Extensão do arquivo (md, txt, docx, etc.) |
| file_size | INTEGER | NOT NULL | Tamanho do arquivo em bytes |
| file_size_mb | FLOAT | NOT NULL | Tamanho do arquivo em MB |
| is_supported | BOOLEAN | DEFAULT TRUE | Se o tipo de arquivo é suportado |
| is_indexed | BOOLEAN | DEFAULT FALSE | Se o arquivo está no índice vetorial |
| chunk_count | INTEGER | DEFAULT 0 | Número de chunks de texto |
| last_modified | DATETIME | NOT NULL | Hora de modificação do arquivo |
| last_checked | DATETIME | DEFAULT utcnow() | Última verificação de metadados |
| created_at | DATETIME | DEFAULT utcnow() | Hora de criação do registro |

**Índices:**
- `idx_doc_metadata_folder_path` - Consultas baseadas em pasta
- `idx_doc_metadata_file_type` - Filtragem por tipo de arquivo
- `idx_doc_metadata_is_supported` - Filtragem de arquivos suportados
- `idx_doc_metadata_is_indexed` - Consultas de arquivos indexados
- `idx_doc_metadata_last_modified` - Rastreamento de modificações
- `idx_doc_metadata_file_size` - Análise de tamanho do arquivo

##### Tabela `excluded_paths`
Caminhos para excluir da indexação.

| Coluna | Tipo | Restrições | Descrição |
|--------|------|-------------|-------------|
| id | INTEGER | PRIMARY KEY | ID do caminho excluído |
| path | VARCHAR(255) | UNIQUE, NOT NULL | Caminho relativo para excluir |
| description | VARCHAR(500) | | Razão para exclusão |
| created_at | DATETIME | DEFAULT utcnow() | Hora de criação do registro |
| created_by | VARCHAR(50) | DEFAULT 'system' | Quem criou a exclusão |

#### 5. Gerenciamento de Índice Vetorial

##### Tabela `text_chunks`
Chunks de texto para indexação vetorial.

| Coluna | Tipo | Restrições | Descrição |
|--------|------|-------------|-------------|
| id | INTEGER | PRIMARY KEY | ID do registro de chunk |
| chunk_text | TEXT | NOT NULL | Conteúdo do chunk |
| chunk_hash | VARCHAR(32) | NOT NULL | Hash do conteúdo do chunk |
| file_path | VARCHAR(500) | NOT NULL | Caminho do arquivo fonte |
| chunk_metadata | JSON | | Metadados do chunk (chunk_id, etc.) |
| embedding_vector | LARGEBINARY | | Dados de embedding vetorial |
| created_at | DATETIME | DEFAULT utcnow() | Hora de criação do chunk |
| last_accessed | DATETIME | DEFAULT utcnow() | Última hora de acesso |
| access_count | INTEGER | DEFAULT 0 | Contador de frequência de acesso |

**Índices:**
- `idx_text_chunk_hash` - Consultas de hash do chunk
- `idx_text_chunk_file_path` - Chunks específicos do arquivo
- `idx_text_chunk_created_at` - Hora de criação
- `idx_text_chunk_last_accessed` - Padrões de acesso
- `idx_text_chunk_access_count` - Chunks frequentemente acessados

##### Tabela `chunk_cache`
Chunks em cache para otimização de performance.

| Coluna | Tipo | Restrições | Descrição |
|--------|------|-------------|-------------|
| id | INTEGER | PRIMARY KEY | ID do registro de cache |
| chunk_hash | VARCHAR(32) | UNIQUE, NOT NULL | Chave hash do chunk |
| chunk_text | TEXT | NOT NULL | Conteúdo do chunk em cache |
| chunk_metadata | JSON | | Metadados em cache |
| cached_at | DATETIME | DEFAULT utcnow() | Timestamp do cache |
| last_accessed | DATETIME | DEFAULT utcnow() | Último acesso ao cache |
| access_count | INTEGER | DEFAULT 0 | Contador de hits do cache |

**Índices:**
- `idx_chunk_cache_cached_at` - Consultas de timestamp do cache
- `idx_chunk_cache_last_accessed` - Padrões de acesso ao cache
- `idx_chunk_cache_access_count` - Análise de hits do cache

#### 6. Sistema de Memória de Chat

##### Tabela `chat_memory`
Gerenciamento de memória de chat para exclusão suave.

| Coluna | Tipo | Restrições | Descrição |
|--------|------|-------------|-------------|
| id | INTEGER | PRIMARY KEY | ID do registro de memória |
| chat_id | VARCHAR(36) | UNIQUE, NOT NULL | Referência para chat.id |
| user_id | INTEGER | FOREIGN KEY | Referência para user.id |
| is_deleted | BOOLEAN | DEFAULT FALSE | Flag de exclusão suave |
| deleted_at | DATETIME | | Timestamp de exclusão |
| last_updated | DATETIME | DEFAULT utcnow() | Hora da última atualização |

**Restrições:**
- `unique_chat_memory` - Um registro de memória por chat

##### Tabela `memory_chunks`
Chunks de memória de conversa para busca semântica.

| Coluna | Tipo | Restrições | Descrição |
|--------|------|-------------|-------------|
| id | INTEGER | PRIMARY KEY | ID do chunk de memória |
| conversation_id | VARCHAR(36) | NOT NULL | Referência para chat.id |
| memory_text | TEXT | NOT NULL | Conteúdo da memória |
| user_message | TEXT | NOT NULL | Mensagem original do usuário |
| assistant_message | TEXT | NOT NULL | Resposta original do assistente |
| timestamp | DATETIME | NOT NULL | Timestamp da mensagem original |
| chunk_id | INTEGER | NOT NULL | Número de sequência do chunk |
| embedding_vector | LARGEBINARY | | Dados de embedding vetorial |
| created_at | DATETIME | DEFAULT utcnow() | Hora de criação do chunk |
| is_deleted | BOOLEAN | DEFAULT FALSE | Flag de exclusão suave |
| deleted_at | DATETIME | | Timestamp de exclusão |

**Restrições:**
- `unique_conversation_chunk` - Um chunk por conversa por chunk_id

**Índices:**
- `idx_memory_chunk_conversation_id` - Consultas de memória de conversa
- `idx_memory_chunk_timestamp` - Ordenação por timestamp
- `idx_memory_chunk_created_at` - Hora de criação
- `idx_memory_chunk_is_deleted` - Consultas de exclusão suave

## Consultas Importantes para Debugging e Manutenção

### 1. Consultas de Gerenciamento de Usuários

#### Verificar Papéis de Usuário e Limites de Mensagens
```sql
-- Obter todos os usuários com seus papéis e uso de mensagens
SELECT 
    id, username, email, user_role, messages_used,
    CASE 
        WHEN user_role = 'free' THEN 20
        WHEN user_role = 'premium' THEN 50
        WHEN user_role = 'pro' THEN 100
        ELSE -1
    END as message_limit,
    CASE 
        WHEN user_role = 'admin' THEN 'Unlimited'
        ELSE CAST(
            CASE 
                WHEN user_role = 'free' THEN 20
                WHEN user_role = 'premium' THEN 50
                WHEN user_role = 'pro' THEN 100
                ELSE 0
            END - messages_used AS TEXT
        )
    END as remaining_messages
FROM user 
ORDER BY created_at DESC;
```

#### Encontrar Usuários Próximos aos Limites de Mensagens
```sql
-- Encontrar usuários se aproximando de seus limites de mensagens
SELECT 
    username, user_role, messages_used,
    CASE 
        WHEN user_role = 'free' THEN 20
        WHEN user_role = 'premium' THEN 50
        WHEN user_role = 'pro' THEN 100
        ELSE 0
    END as limit,
    CASE 
        WHEN user_role = 'free' THEN 20
        WHEN user_role = 'premium' THEN 50
        WHEN user_role = 'pro' THEN 100
        ELSE 0
    END - messages_used as remaining
FROM user 
WHERE user_role != 'admin' 
    AND messages_used > (
        CASE 
            WHEN user_role = 'free' THEN 15
            WHEN user_role = 'premium' THEN 40
            WHEN user_role = 'pro' THEN 80
            ELSE 0
        END
    )
ORDER BY remaining ASC;
```

#### Verificar Sessões Ativas
```sql
-- Obter todas as sessões ativas de usuários
SELECT 
    u.username, u.email, u.user_role,
    us.session_id, us.ip_address, us.created_at, us.last_accessed,
    us.get_browser_info() as browser,
    us.get_device_info() as device
FROM user_sessions us
JOIN user u ON us.user_id = u.id
WHERE us.is_active = 1
ORDER BY us.last_accessed DESC;
```

### 2. Consultas do Sistema de Chat

#### Estatísticas de Chat
```sql
-- Obter estatísticas de chat por usuário
SELECT 
    u.username, u.user_role,
    COUNT(c.id) as total_chats,
    COUNT(m.id) as total_messages,
    MAX(c.created_at) as last_chat_created,
    MAX(m.timestamp) as last_message_sent
FROM user u
LEFT JOIN chat c ON u.id = c.user_id
LEFT JOIN message m ON c.id = m.chat_id
GROUP BY u.id, u.username, u.user_role
ORDER BY total_messages DESC;
```

#### Encontrar Chats Inativos
```sql
-- Encontrar chats sem atividade recente
SELECT 
    u.username, c.id, c.title, c.created_at,
    MAX(m.timestamp) as last_message,
    COUNT(m.id) as message_count
FROM chat c
JOIN user u ON c.user_id = u.id
LEFT JOIN message m ON c.id = m.chat_id
GROUP BY c.id, u.username, c.title, c.created_at
HAVING last_message < datetime('now', '-7 days') OR last_message IS NULL
ORDER BY last_message ASC;
```

#### Análise de Distribuição de Mensagens
```sql
-- Analisar distribuição de mensagens por papel e tempo
SELECT 
    role,
    DATE(timestamp) as message_date,
    COUNT(*) as message_count,
    AVG(LENGTH(content)) as avg_content_length
FROM message
WHERE timestamp >= datetime('now', '-30 days')
GROUP BY role, DATE(timestamp)
ORDER BY message_date DESC, role;
```

### 3. Consultas de Rastreamento de Uso

#### Análise de Uso de IA
```sql
-- Estatísticas de uso de IA por usuário e modelo
SELECT 
    u.username, u.user_role,
    au.model,
    COUNT(*) as usage_count,
    SUM(au.total_tokens) as total_tokens,
    AVG(au.total_tokens) as avg_tokens_per_request,
    SUM(au.prompt_tokens) as total_prompt_tokens,
    SUM(au.completion_tokens) as total_completion_tokens
FROM ai_usage au
JOIN user u ON au.user_id = u.id
WHERE au.created_at >= datetime('now', '-30 days')
GROUP BY u.id, u.username, u.user_role, au.model
ORDER BY total_tokens DESC;
```

#### Análise de Contagem Diária de Mensagens
```sql
-- Tendências de contagem diária de mensagens
SELECT 
    u.username, u.user_role,
    udmc.date,
    udmc.total_messages,
    SUM(udmc.total_messages) OVER (
        PARTITION BY u.id 
        ORDER BY udmc.date 
        ROWS BETWEEN 6 PRECEDING AND CURRENT ROW
    ) as weekly_total
FROM user_daily_message_count udmc
JOIN user u ON udmc.user_id = u.id
WHERE udmc.date >= date('now', '-30 days')
ORDER BY u.username, udmc.date DESC;
```

#### Análise de Uso de Embedding
```sql
-- Uso de embedding por tipo de arquivo e operação
SELECT 
    dm.file_type,
    ieu.operation,
    COUNT(*) as operation_count,
    SUM(ieu.tokens_used) as total_tokens,
    AVG(ieu.tokens_used) as avg_tokens_per_operation,
    SUM(ieu.text_length) as total_text_length
FROM index_embedding_usage ieu
JOIN document_metadata dm ON ieu.file_path = dm.file_path
WHERE ieu.created_at >= datetime('now', '-30 days')
GROUP BY dm.file_type, ieu.operation
ORDER BY total_tokens DESC;
```

### 4. Consultas de Gerenciamento de Arquivos

#### Status de Indexação de Arquivos
```sql
-- Visão geral do status de indexação de documentos
SELECT 
    folder_path,
    file_type,
    COUNT(*) as total_files,
    SUM(CASE WHEN is_supported = 1 THEN 1 ELSE 0 END) as supported_files,
    SUM(CASE WHEN is_indexed = 1 THEN 1 ELSE 0 END) as indexed_files,
    SUM(chunk_count) as total_chunks,
    ROUND(SUM(file_size_mb), 2) as total_size_mb
FROM document_metadata
GROUP BY folder_path, file_type
ORDER BY total_size_mb DESC;
```

#### Encontrar Arquivos Grandes
```sql
-- Encontrar os maiores arquivos no sistema
SELECT 
    file_name, folder_path, file_type, file_size_mb, 
    is_supported, is_indexed, chunk_count, last_modified
FROM document_metadata
WHERE file_size_mb > 10
ORDER BY file_size_mb DESC
LIMIT 20;
```

#### Verificar Consistência de Arquivos
```sql
-- Verificar arquivos que podem precisar de re-indexação
SELECT 
    dm.file_path, dm.file_name, dm.last_modified, dm.last_checked,
    fm.mtime, fm.size, fm.hash,
    CASE 
        WHEN dm.last_modified != datetime(fm.mtime, 'unixepoch') THEN 'MODIFIED'
        WHEN dm.chunk_count = 0 AND dm.is_indexed = 1 THEN 'MISSING_CHUNKS'
        WHEN dm.is_supported = 1 AND dm.is_indexed = 0 THEN 'NOT_INDEXED'
        ELSE 'OK'
    END as status
FROM document_metadata dm
LEFT JOIN file_metadata fm ON dm.file_path = fm.file_path
WHERE dm.is_supported = 1
ORDER BY status, dm.last_modified DESC;
```

### 5. Consultas de Índice Vetorial

#### Padrões de Acesso a Chunks
```sql
-- Chunks mais frequentemente acessados
SELECT 
    tc.file_path, tc.chunk_metadata->>'chunk_id' as chunk_id,
    tc.access_count, tc.last_accessed, tc.created_at
FROM text_chunks tc
WHERE tc.access_count > 0
ORDER BY tc.access_count DESC, tc.last_accessed DESC
LIMIT 20;
```

#### Performance do Cache
```sql
-- Análise de hits do cache
SELECT 
    cc.chunk_hash, cc.access_count, cc.cached_at, cc.last_accessed,
    tc.file_path
FROM chunk_cache cc
LEFT JOIN text_chunks tc ON cc.chunk_hash = tc.chunk_hash
ORDER BY cc.access_count DESC, cc.last_accessed DESC
LIMIT 20;
```

#### Análise de Chunks de Memória
```sql
-- Estatísticas de chunks de memória
SELECT 
    conversation_id,
    COUNT(*) as total_chunks,
    SUM(CASE WHEN is_deleted = 0 THEN 1 ELSE 0 END) as active_chunks,
    MIN(timestamp) as earliest_memory,
    MAX(timestamp) as latest_memory
FROM memory_chunks
GROUP BY conversation_id
ORDER BY total_chunks DESC;
```

### 6. Consultas de Manutenção

#### Análise de Tamanho do Banco de Dados
```sql
-- Tamanhos de tabelas e contagens de linhas
SELECT 
    name as table_name,
    (SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name=m.name) as row_count
FROM sqlite_master m
WHERE type='table' AND name NOT LIKE 'sqlite_%'
ORDER BY name;
```

#### Limpeza de Dados Antigos
```sql
-- Encontrar sessões inativas antigas para limpeza
SELECT 
    u.username, us.session_id, us.last_accessed, us.is_active
FROM user_sessions us
JOIN user u ON us.user_id = u.id
WHERE us.last_accessed < datetime('now', '-7 days')
    AND us.is_active = 1
ORDER BY us.last_accessed ASC;

-- Encontrar registros antigos de uso de IA (mais de 90 dias)
SELECT COUNT(*) as old_usage_records
FROM ai_usage
WHERE created_at < datetime('now', '-90 days');

-- Encontrar registros antigos de uso de embedding (mais de 90 dias)
SELECT COUNT(*) as old_embedding_records
FROM index_embedding_usage
WHERE created_at < datetime('now', '-90 days');
```

#### Monitoramento de Performance
```sql
-- Verificar uso de índices (específico do SQLite)
SELECT 
    name, sql
FROM sqlite_master
WHERE type='index' AND name NOT LIKE 'sqlite_%'
ORDER BY name;

-- Encontrar tabelas sem índices adequados
SELECT 
    m.name as table_name,
    COUNT(i.name) as index_count
FROM sqlite_master m
LEFT JOIN sqlite_master i ON m.name = i.tbl_name AND i.type='index'
WHERE m.type='table' AND m.name NOT LIKE 'sqlite_%'
GROUP BY m.name
HAVING index_count < 2
ORDER BY table_name;
```

### 7. Consultas de Integridade de Dados

#### Verificar Registros Órfãos
```sql
-- Encontrar mensagens órfãs
SELECT COUNT(*) as orphaned_messages
FROM message m
LEFT JOIN chat c ON m.chat_id = c.id
WHERE c.id IS NULL;

-- Encontrar memórias de chat órfãs
SELECT COUNT(*) as orphaned_memories
FROM chat_memory cm
LEFT JOIN chat c ON cm.chat_id = c.id
WHERE c.id IS NULL;

-- Encontrar chunks de memória órfãos
SELECT COUNT(*) as orphaned_chunks
FROM memory_chunks mc
LEFT JOIN chat c ON mc.conversation_id = c.id
WHERE c.id IS NULL;
```

#### Verificar Consistência de Dados
```sql
-- Verificar usuários com contagens negativas de mensagens
SELECT id, username, messages_used
FROM user
WHERE messages_used < 0;

-- Verificar papéis de usuário inválidos
SELECT id, username, user_role
FROM user
WHERE user_role NOT IN ('free', 'premium', 'pro', 'admin');

-- Verificar timestamps futuros
SELECT 'user' as table_name, id, created_at
FROM user WHERE created_at > datetime('now')
UNION ALL
SELECT 'chat', id, created_at
FROM chat WHERE created_at > datetime('now')
UNION ALL
SELECT 'message', id, timestamp
FROM message WHERE timestamp > datetime('now');
```

## Procedimentos de Manutenção do Banco de Dados

### 1. Tarefas de Limpeza Regulares

#### Tarefas Semanais
```sql
-- Desativar sessões antigas
UPDATE user_sessions 
SET is_active = 0 
WHERE last_accessed < datetime('now', '-7 days') AND is_active = 1;

-- Limpar entradas antigas do cache
DELETE FROM chunk_cache 
WHERE last_accessed < datetime('now', '-30 days') AND access_count < 5;
```

#### Tarefas Mensais
```sql
-- Arquivar dados antigos de uso (opcional - mover para tabelas de arquivo)
-- Isso exigiria criar tabelas de arquivo primeiro

-- Atualizar metadados de arquivo para verificação de consistência
UPDATE file_metadata 
SET last_checked = datetime('now')
WHERE last_checked < datetime('now', '-30 days');
```

### 2. Otimização de Performance

#### Reconstruir Índices (se necessário)
```sql
-- SQLite não tem REINDEX explícito para índices específicos
-- Mas você pode analisar tabelas para otimização de consultas
ANALYZE;
```

#### Atualizar Estatísticas
```sql
-- Atualizar estatísticas de tabelas para o otimizador de consultas
ANALYZE user;
ANALYZE chat;
ANALYZE message;
ANALYZE ai_usage;
ANALYZE text_chunks;
ANALYZE memory_chunks;
```

### 3. Backup e Recuperação

#### Criar Backup
```bash
# Criar backup do banco de dados
sqlite3 app.db ".backup backup_$(date +%Y%m%d_%H%M%S).db"

# Ou usar script Python
python -c "
import sqlite3
import shutil
from datetime import datetime

backup_name = f'backup_{datetime.now().strftime(\"%Y%m%d_%H%M%S\")}.db'
shutil.copy2('app.db', backup_name)
print(f'Backup created: {backup_name}')
"
```

#### Restaurar do Backup
```bash
# Restaurar do backup
cp backup_20240101_120000.db app.db
```

## Solução de Problemas Comuns

### 1. Problemas de Performance

#### Consultas Lentas
- Verificar se os índices estão sendo usados com `EXPLAIN QUERY PLAN`
- Monitorar tamanhos de tabelas e considerar arquivar dados antigos
- Verificar índices ausentes em colunas frequentemente consultadas

#### Alto Uso de Memória
- Monitorar tamanho do cache de chunks e padrões de acesso
- Considerar reduzir o tamanho do cache ou implementar evição LRU
- Verificar vazamentos de memória no armazenamento de vetores de embedding

### 2. Problemas de Integridade de Dados

#### Registros Órfãos
- Executar consultas de registros órfãos regularmente
- Implementar restrições de chave estrangeira quando possível
- Usar exclusões em cascata para dados relacionados

#### Metadados de Arquivo Inconsistentes
- Executar verificações de consistência de arquivos
- Implementar monitoramento do sistema de arquivos
- Atualizar metadados após operações de arquivo

### 3. Problemas de Gerenciamento de Usuários

#### Problemas de Sessão
- Verificar sessões ativas duplicadas
- Monitorar processos de limpeza de sessão
- Verificar configurações de timeout de sessão

#### Problemas de Limite de Mensagens
- Verificar se os limites baseados em papel são aplicados corretamente
- Verificar cálculos de contagem diária de mensagens
- Monitorar usuários que excedem limites

## Considerações de Segurança

### 1. Proteção de Dados
- Todas as senhas são criptografadas usando funções de segurança do Werkzeug
- IDs de sessão são únicos e validados
- Dados do usuário são isolados por user_id

### 2. Controle de Acesso
- Usuários admin têm acesso ilimitado a mensagens
- Controle de acesso baseado em papéis para diferentes níveis de usuário
- Autenticação baseada em sessão com timeout

### 3. Privacidade de Dados
- Exclusão suave para memórias de chat para permitir recuperação
- Dados do usuário podem ser anonimizados ou excluídos
- Trilha de auditoria através de tabelas de rastreamento de uso

## Monitoramento e Alertas

### Métricas Principais para Monitorar
1. **Atividade do Usuário**: Usuários ativos diários, contagens de mensagens
2. **Performance do Sistema**: Tempos de resposta de consultas, taxas de hit do cache
3. **Uso de Recursos**: Tamanho do banco de dados, consumo de tokens
4. **Taxas de Erro**: Consultas falhadas, problemas de sessão

### Alertas Recomendados
1. Usuários se aproximando dos limites de mensagens
2. Altas taxas de uso de tokens
3. Crescimento do tamanho do banco de dados
4. Tentativas de autenticação falhadas
5. Registros órfãos detectados

Esta documentação deve ser atualizada conforme o schema do banco de dados evolui e novas funcionalidades são adicionadas.
