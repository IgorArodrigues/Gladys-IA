# Sistema de Memória de Chat

Este documento descreve a implementação de um sistema de memória de chat de duas camadas que fornece capacidades de memória de curto e longo prazo para aplicações de IA conversacional. O sistema foi totalmente integrado à aplicação Flask com recuperação automática de memória, controles de painel administrativo e capacidades abrangentes de teste.

## Visão Geral

O sistema de memória de chat implementa uma arquitetura de memória dupla:

1. **Memória de Curto Prazo**: Usa a tabela `messages` existente no banco de dados para trocas de conversação recentes
2. **Memória de Longo Prazo**: Armazena embeddings vetoriais de conversas passadas para recuperação semântica

## Arquitetura

### Sistema de Memória de Duas Camadas

```
┌─────────────────────────────────────────────────────────────┐
│                    Sistema de memória                       │
├─────────────────────────────────────────────────────────────┤
│  Memória de curto prazo (banco de dados)                    │
│  ├─ Trocas recentes da tabela de mensagens                  │
│  ├─ Consultas rápidas ao DB para contexto imediato          │
│  └─ Respeita as operações de exclusão existentes            │
├─────────────────────────────────────────────────────────────┤
│  Memória de Longo Prazo (Banco de Dados Vetorial)           │
│  ├─ Índice FAISS com incorporações de conversação           │
│  ├─ Capacidades de pesquisa semântica                       │
│  └─ Soft-delete por meio da tabela chat_memory              │
└─────────────────────────────────────────────────────────────┘
```

### Integração com Banco de Dados

O sistema se integra com sua estrutura de banco de dados existente:

- **Tabela `messages`**: Usada para memória de curto prazo 
- **Tabela `chat`**: Usada para metadados de conversação
- **Tabela `user`**: Usada para identificação de usuário
- **Tabela `chat_memory`**: Tabela para rastreamento de soft-delete

### Tabela: chat_memory

```sql
CREATE TABLE chat_memory (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    is_deleted BOOLEAN DEFAULT 0,
    deleted_at TEXT,
    last_updated TEXT NOT NULL,
    UNIQUE(chat_id)
);
```

Esta tabela rastreia quais conversas são soft-deleted sem afetar seus dados existentes.

## Principais Recursos

### 1. Memória de Curto Prazo Baseada em Banco de Dados
- **Consultas rápidas**: Consultas de banco de dados otimizadas para conversas recentes
- **Consciente do usuário**: Respeita permissões de usuário e propriedade de conversação

### 2. Memória de Longo Prazo com FAISS
- **Embeddings Vetoriais**: OpenAI text-embedding-3-small para representação semântica
- **Busca Eficiente**: Índice FAISS para busca rápida de similaridade
- **Filtragem de Relevância**: Limiar de similaridade configurável via `config.json`

### 3. Sistema de Soft-Delete
- **Otimização de Performance**: Conversas excluídas são excluídas da busca
- **Preservação de Dados**: Mensagens originais e registros de chat permanecem intactos
- **Operações Rápidas**: Não há necessidade de reconstruir o índice na exclusão
- **Específico do usuário**: Cada usuário pode gerenciar suas próprias conversas excluídas

### 4. Sincronização Automática
- **Sincronização de Banco de Dados**: Thread em segundo plano sincroniza com o banco de dados de chat
- **Detecção de Nova Conversa**: Indexa automaticamente novas conversas
- **Atualizações Incrementais**: Gerenciamento eficiente de memória

## Configuração

O sistema usa seções de configuração separadas em `config.json` para memória de chat e o gerenciador de índice:

### Configuração de Memória de Chat

```python
# Configuração de memória de chat (separada do Index Manager)
CHAT_MEMORY_CONFIG = {
    "chat_index_path": "vector_index/chat_faiss_index.pkl",
    "enable_usage_tracking": True,
    "chat_verbose": False,                 # Controle de log detalhado
    "max_short_term_memory": 20,           # Trocas máximas de curto prazo
    "max_short_term_tokens": 4000,         # Limite aproximado de tokens
    "long_term_memory_chunk_size": 1000,   # Máximo de caracteres por bloco de memória
    "chat_auto_update_interval": 300,      # Intervalo de sincronização em segundos (5 min) - separado da sincronização de arquivos
    "relevance_threshold": 0.7,            # threshold de similaridade para recuperação
    "max_memory_results": 5,               # Máximo de memórias para recuperar
    "default_hard_delete": False           # Modo de exclusão padrão (false=soft, true=hard. Hard delete reconstroi todo o indice a cada mensagem apagada)
}
```

### Configuração do Index_Manager (separada)

```python
# Index Manager Configuração (separada)
INDEX_CONFIG = {
    "vault_path": r"E:\Vault\Igor",
    "auto_update_interval": 300,            # Intervalo de sincronização em segundos (5 min) - separado da sincronização dos chats
    "verbose": False,                       # Controle de log detalhado
    # ... outras configurações do index_manager
}
```

### Modos de Exclusão
- **Soft Delete (padrão)**: Conversas são marcadas como excluídas mas permanecem no sistema para performance e integridade de dados
- **Hard Delete**: Conversas são completamente removidas do banco de dados e sistema de memória. O index é reconstruido do 0 pois o faiss não aceita reconstrução parcial
- **Configurável**: Você pode definir o comportamento padrão em `CHAT_MEMORY_CONFIG["default_hard_delete"]`

## Integração com Aplicação Flask

### O Que Foi Implementado

1. **API de Chat Aprimorada com Memória**: A rota `/api/chat` recupera automaticamente o contexto de memória da conversa
2. **Contexto de Memória Inteligente**: Combina memória de curto e longo prazo para respostas de IA mais ricas
3. **Sistema de Soft-Delete**: Quando chats são excluídos, eles são soft-deleted da memória (marcados como excluídos mas preservados)
4. **Integração do Painel Administrativo**: Botão "Chat Memory" no painel administrativo para estatísticas e gerenciamento
5. **Armazenamento Automático**: Cada troca de conversa é automaticamente armazenada na memória de longo prazo

### Como Funciona Durante o Chat

1. Usuário envia uma mensagem
2. Sistema recupera documentos relevantes do seu vault de documentos
3. Sistema recupera contexto de memória da conversa (recentes + conversas passadas relevantes)
4. Todo o contexto é combinado em um prompt de sistema abrangente
5. IA gera resposta usando o contexto completo
6. Troca de conversa é armazenada na memória de longo prazo

### Processo de Recuperação de Memória
- **Contexto recente**: Últimas 3 trocas da conversa atual (Configurável)
- **Passado relevante**: Até 3 conversas passadas semanticamente mais similares (Configurável)
- **Filtragem inteligente**: Inclui apenas memórias acima do limiar de relevância (0.7) (Configurável)

# Integração do Painel Administrativo

## Acesse estatísticas de memória e controles através do painel administrativo:
- Vá para `/admin` em sua aplicação Flask
- Clique no botão "Chat Memory"
- Visualize estatísticas de memória, saúde do sistema e configuração
- Execute operações de sincronização manual para solução de problemas

## Considerações de Performance

### 1. Benefícios do Soft-Delete
- **Buscas Mais Rápidas**: Conversas excluídas não retardam a recuperação
- **Integridade de Dados**: Dados originais permanecem intactos
- **Escalabilidade**: Sistema permanece rápido conforme o número de conversas cresce
- **Privacidade do Usuário**: Cada usuário gerencia suas próprias conversas excluídas
-**Indice não é refeito**: O indice não precisa ser refeito a cada operação

### 2. Otimização de Banco de Dados
- **Consultas Indexadas**: Lookups rápidos em chat_id e is_deleted
- **Joins Eficientes**: Consultas otimizadas entre tabelas
- **Sincronização em Segundo Plano**: Operações de banco de dados não bloqueiam interações do usuário

### 3. Gerenciamento de Memória
- **Limites de Tamanho de Chunk**: Previne chunks de memória extremamente longos
- **Filtragem de Relevância**: Retorna apenas memórias altamente relevantes
- **Índice FAISS**: Busca otimizada de similaridade vetorial

### Cenários de Teste

1. **Integração de Banco de Dados**: Verificar conexão com tabelas existentes
2. **Operações de Memória**: Adicionar, recuperar e buscar memórias
3. **Soft Delete**: Verificar se conversas excluídas são excluídas da busca
4. **Geração de Contexto**: Testar contexto combinado de curto e longo prazo
5. **Performance**: Medir velocidades de busca e recuperação
6. **Integração Flask**: Testar API de chat aprimorada com memória
7. **Painel Administrativo**: Verificar estatísticas de memória e controles

### Testando a Integração

1. **Inicie Seu App**: `Gladys IA.exe`
2. **Verifique o Painel Administrativo**: Vá para `/admin` e clique no botão "Chat Memory"
3. **Teste a Memória de Chat**: Inicie uma nova conversa e faça perguntas de acompanhamento
4. **Verifique o Contexto**: A IA deve lembrar o contexto da conversa anterior

## Monitoramento e Estatísticas

### Estatísticas de Memória

```python
stats = memory_manager.get_memory_stats()
print(f"Short-term: {stats['short_term_memory']['source']}")
print(f"Long-term: {stats['long_term_memory']['total_chunks']} chunks")
print(f"Deleted: {stats['long_term_memory']['deleted_conversations']} conversations")
```

### Métricas do Painel Administrativo

Acesso através de `/admin` → botão "Chat Memory":
- Total de chunks de memória
- Tamanho do índice
- Contagem de conversas excluídas
- Configurações de configuração
- Status de saúde do sistema

### Rastreamento de Uso

O sistema rastreia o uso de embedding para:
- Criação de memória
- Atualizações de memória
- Operações de busca
- Reconstrução de índice

### Indicadores de Performance
- Velocidade de recuperação de memória
- Tamanho do contexto
- Pontuações de relevância

## Solução de Problemas

### Problemas Comuns

1. **"Chat memory manager not available"**
   - Verifique a chave da API OpenAI na configuração

2. **Contexto de memória não aparecendo**
   - Verifique o painel administrativo para estatísticas de memória
   - Ative os logs detalhados e observe as mensagens
   - Verifique conectividade do banco de dados

3. **Erros de Conexão de Banco de Dados**
   - Verifique estrutura e conectividade do banco de dados
   - Certifique-se de que `instance/app.db` existe
   - Verifique permissões do banco de dados

4. **Problemas de Índice de Memória**
   - Exclua `vector_index/chat_faiss_index.pkl` para reconstruir
   - Verifique configuração da chave da API OpenAI
   - Verifique se o sistema tem permissão de leiura e escrita nas pastas configuradas

5. **Problemas de Performance**
   - Ajuste `relevance_threshold` na configuração para menos resultados
   - Reduza `max_memory_results` para buscas mais rápidas
   - Use soft-delete em vez de hard-delete
   - Verifique se os índices do banco de dados foram criados

### Modo de Debug

Habilite logging verboso em `config.json`:
```python
CHAT_MEMORY_CONFIG = {
    # ... outras configurações ...
    "chat_verbose": True,  # Controle de log detalhado
}
```
### Requisitos de Banco de Dados

O sistema cria automaticamente uma tabela `chat_memory` para rastreamento de soft-delete. Se você encontrar problemas:

O sistema cria automaticamente as tabelas de banco de dados necessárias quando inicializado.

## Benefícios do Sistema de Memória

### Para Usuários:
- **Respostas contextuais**: IA lembra conversas anteriores
- **Continuidade**: Perguntas de acompanhamento são respondidas no contexto
- **Personalização**: Respostas são adaptadas ao histórico de conversas

### Para Performance:
- **Recuperação rápida**: Busca vetorial FAISS para memórias relevantes
- **Armazenamento eficiente**: Memória em chunks com truncamento inteligente
- **Sincronização em segundo plano**: Sincronização automática de banco de dados

### Para Manutenção:
- **Soft-delete**: Conversas excluídas não quebram o sistema
- **Rastreamento de uso**: Monitore performance do sistema de memória
- **Controles administrativos**: Visualização manual de sincronização e estatísticas

## Melhorias Futuras

1. **Compressão de memória**: Resumir memórias antigas para economizar espaço
2. **Ponderação temporal**: Dar mais peso a memórias recentes
3. **Isolamento de usuário**: Controles de privacidade aprimorados
4. **Categorias de memória**: Organizar por tópico ou tipo
5. **Exportar/Importar**: Capacidades de backup e restauração

## Dependências

- `faiss-cpu` ou `faiss-gpu`: Busca de similaridade vetorial
- `openai`: Cliente da API OpenAI
- `sqlalchemy`: Operações de banco de dados
- `numpy`: Operações numéricas
- `pickle`: Serialização de índice

## Suporte

Se você encontrar problemas:

1. Verifique o painel administrativo primeiro para status do sistema
2. Verifique o painel administrativo para mensagens de erro
3. Verifique conectividade do banco de dados
4. Verifique configuração da chave da API OpenAI
5. Ative os logs detalhados e observe as mensagens

O sistema de memória de chat foi projetado para ser robusto e auto-reparador, sincronizando automaticamente com seu banco de dados e mantendo performance mesmo com históricos de conversa grandes.

## Licença

Esta implementação segue a mesma licença do projeto principal Gladys IA.