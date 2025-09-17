# Guia do Usuário - Gladys IA

**Gladys IA** é uma aplicação de chat com IA que permite conversar com um assistente inteligente que tem acesso aos seus documentos. A aplicação busca automaticamente através dos seus arquivos para fornecer respostas relevantes e contextualizadas.

## 🚀 Início Rápido

### 1. Configuração Inicial

1. **Configure o arquivo `config.json`** (veja seção de configuração abaixo)
2. **Execute o arquivo `Gladys IA.exe`**
3. **Acesse a aplicação** aguarde um pouco pois dependendo da quantidade de documentos no vault a primeira inicialização pode ser lenta. No navegador em `http://localhost:5000` ou em outro dispositivo em `http://IpDoHost:5000`
4. **Faça login ou registre-se** com as credenciais padrão do administrador ou crie uma nova conta:
   - **Usuário:** `administrador`
   - **Senha:** `administrador`
5. **Leitura** Recomendo a leitura do documento `QUERY_INTENT.md`, para compreender o funcionamento da engine de pesquisa

### 2. Primeiro Uso

1. Após fazer login, você pode:
   - Criar uma nova conta de usuário
   - Começar a usar o chat imediatamente
   - Gerenciar seus documentos

## ⚙️ Configuração do Arquivo config.json

O arquivo `config.json` é essencial para o funcionamento da aplicação. Aqui está um exemplo completo com comentários:

```json
{
  "AI_MODEL": "gpt-4o-mini",                    // Modelo de IA (gpt-4o-mini, gpt-4, gpt-3.5-turbo)
  "EMBEDDING_MODEL": "text-embedding-3-small", // Modelo de embedding para busca vetorial
  "OPENAI_API_KEY": "sua-chave-api-aqui",      // SUA CHAVE DA API OPENAI (OBRIGATÓRIO)
  
  "SEARCH_CONFIG": {
    "short_query_threshold": 50,                // Limite de caracteres para consultas curtas
    "medium_query_threshold": 150,              // Limite de caracteres para consultas médias
    "short_query_results": 2,                   // Resultados para consultas curtas
    "medium_query_results": 3,                  // Resultados para consultas médias
    "long_query_results": 4,                    // Resultados para consultas longas
    "max_total_context_length": 8000,           // Tamanho máximo do contexto total
    "max_chunk_length": 4000,                   // Tamanho máximo de cada fragmento
    "max_summary_length": 1500,                 // Tamanho máximo do resumo
    "search_multiplier": 3,                     // Multiplicador de busca
    "max_chunks_per_file": 2,                   // Máximo de fragmentos por arquivo
    "comprehensive_search_results": 10,         // Resultados para busca abrangente (leia QUERY_INTENT para mais detalhes)
    "comprehensive_context_multiplier": 2,      // Multiplicador de contexto abrangente (leia QUERY_INTENT para mais detalhes)
    "max_total_comprehensive_results": 15       // Máximo de resultados abrangentes (leia QUERY_INTENT para mais detalhes)
  },
  
  "INDEX_CONFIG": {
"vault_path": "C:\\Caminho\\Para\\Seu\\Vault", // Caminho para sua pasta com os arquivos, subdiretórios tambem são lidos se não forem banidos, use "\\"
    "index_path": "vector_index/faiss_index.pkl",   // Caminho do índice vetorial (Gera automático mesma pasta do exe por padrão)
    "enable_usage_tracking": true,                   // Habilitar rastreamento de uso (tela de admin)
    "verbose": false,                                // Controle de log detalhado
    "max_chunk_size": 3000,                         // Tamanho máximo de cada fragmento
    "chunk_overlap": 200,                           // Sobreposição entre fragmentos
    "min_chunk_size": 100,                          // Tamanho mínimo de fragmento
    "auto_update_interval": 300,                     // Intervalo de atualização automática ( em segundos)
    "excluded_paths": {                             // Pastas padrão excluídas da indexação (é possivel adicionar novas pela tela de administração)
      ".obsidian": true,                            // Configurações do Obsidian
      ".git": true,                                 // Repositório Git
      ".vscode": true,                              // Configurações do VS Code
      "node_modules": true,                         // Dependências Node.js
      "__pycache__": true,                          // Cache Python
      ".DS_Store": true,                            // Arquivos do macOS
      "Thumbs.db": true,                            // Cache de miniaturas Windows
      "desktop.ini": true                           // Configurações de desktop Windows
    }
  },
  
  "CHAT_MEMORY_CONFIG": {
    "chat_index_path": "vector_index/chat_faiss_index.pkl", // Caminho do índice de memória do chat (Gera automático mesma pasta do exe por padrão)
    "enable_usage_tracking": true,                          // Habilitar rastreamento de uso (tela de admin)
    "chat_verbose": false,                                  // Controle de log detalhado
    "max_short_term_memory": 20,                            // Máximo de trocas na memória de curto prazo
    "max_short_term_tokens": 4000,                          // Limite de tokens para memória de curto prazo
    "long_term_memory_chunk_size": 1000,                    // Tamanho do fragmento de memória de longo prazo
    "chat_auto_update_interval": 300,                       // Intervalo de atualização do chat (5 minutos)
    "relevance_threshold": 0.7,                             // Limiar de relevância para recuperação de memória
    "max_memory_results": 5,                                // Máximo de memórias relevantes a recuperar
    "default_hard_delete": false                            // Modo de exclusão padrão (false=soft, true=hard. Hard delete reconstroi todo o indice a cada mensagem apagada)
  },
  
  "PERFORMANCE_CONFIG": {
    "enable_context_logging": true,    // Habilitar logs de tamanho de contexto
    "enable_search_timing": true,      // Habilitar logs de tempo de busca
    "context_size_warning": 6000       // Avisar quando o contexto exceder este tamanho
  },
  
  "LOGGING_CONFIG": {
    "logs_directory": "logs",          // Diretório de logs (Gera automático mesma pasta do exe por padrão)
    "log_level": "INFO",               // Nível de log (DEBUG, INFO, WARNING, ERROR)
    "log_format": "csv",               // Formato dos logs
    "include_timestamp": true,         // Incluir timestamp nos logs
    "max_log_files": 30,               // Máximo de arquivos de log
    "log_rotation": "daily"            // Rotação de logs (daily, weekly, monthly)
  },
  
  "FILE_READER_CONFIG": {
    "verbose": false                   // Controle de log detalhado
  }
}
```

### 🔑 Configurações Importantes

**OBRIGATÓRIO - Chave da API OpenAI:**
```json
"OPENAI_API_KEY": "sk-proj-sua-chave-aqui"
```

**OBRIGATÓRIO - Caminho do Vault:**
```json
"vault_path": "C:\\Caminho\\Para\\Seu\\Vault", // Caminho para sua pasta com os arquivos, subdiretórios tambem são lidos se não forem banidos, use "//"
```

## 📁 Tipos de Arquivos Suportados

A aplicação suporta os seguintes tipos de arquivo:
- **Markdown** (.md)
- **Word** (.docx)
- **Excel** (.xlsx)
- **PDF** (.pdf)
- **Texto** (.txt) 'Em criação'

## 💬 Como Usar o Chat

### Iniciando uma Conversa

1. **Faça login** na aplicação
2. **Clique em "Novo Chat"** para iniciar uma conversa
3. **Digite sua pergunta** na interface de chat
4. **A IA buscará** automaticamente nos seus documentos e fornecerá uma resposta contextualizada

### Gerenciando Chats

- **Visualizar todos os chats** no painel principal
- **Excluir chats** que não precisa mais
- **Cada chat mantém** seu próprio histórico de conversa
- **Memória persistente** - a IA lembra do contexto das conversas anteriores

## 🔐 Segurança e Autenticação

### Usuário Administrador Padrão
- **Usuário:** `administrador`
- **Senha:** `administrador`

### Recursos de Segurança
- **Hash de senhas** usando Werkzeug
- **Gerenciamento de sessão** com Flask-Login
- **Isolamento de usuários** (cada usuário acessa apenas seus próprios chats)
- **Proteção CSRF** através de formulários Flask

## 🛠️ Solução de Problemas

### Problemas Comuns

1. **Erro de Chave da API**
   - Verifique se a chave da OpenAI está correta no `config.json`
   - Confirme se há créditos suficientes na conta

2. **Vault não encontrado**
   - Verifique se o caminho no `vault_path` está correto
   - Use barras duplas (`\\`) no Windows

3. **Arquivos não indexados**
   - Certifique-se de que há arquivos suportados no vault
   - Verifique se as pastas não estão na lista de exclusão
   - Leia `INDEX_MANAGER_README.md` para mais detalhes.

4. **Erro de banco de dados**
   - Leia `DATABASE.md` para mais detalhes.

### Logs e Monitoramento

- **Logs são salvos** na pasta `logs/`
- **Logs em formato CSV** para fácil análise

## 📊 Recursos Avançados

### Configuração de Performance

- **Ajuste `max_chunk_size`** para otimizar a indexação
- **Modifique `search_multiplier`** para controlar a precisão da busca
- **Configure `auto_update_interval`** para atualizações automáticas

### Personalização da IA

- **Altere `AI_MODEL`** para usar diferentes modelos (gpt-4, gpt-3.5-turbo)
- **Ajuste `relevance_threshold`** para controlar a relevância das memórias
- **Configure `max_memory_results`** para limitar resultados de memória

## 📝 Estrutura de Arquivos

```
Gladys IA/
├── Gladys IA.exe          # Executável principal
├── config.json            # Arquivo de configuração
├── instance/
│   └── app.db            # Banco de dados SQLite
├── vector_index/         # Índices vetoriais
├── logs/                 # Arquivos de log
└── templates/            # Interface web
```
## Tecnologias Utilizadas

### Backend Framework & Web Server
- **Flask 2.3.3**: Framework web Python para construção da aplicação
- **Werkzeug 2.3.7**: Toolkit WSGI e utilitários para Flask
- **Jinja2 3.1.2**: Template engine para renderização de páginas HTML

### Database & ORM
- **SQLite**: Banco de dados leve e sem servidor para armazenar dados de usuários e histórico de chat
- **Flask-SQLAlchemy 3.0.5**: ORM (Object-Relational Mapping) para operações de banco de dados
- **Flask-Login 0.6.3**: Gerenciamento de sessão de usuário e autenticação

### AI & Machine Learning
- **OpenAI API (>=1.0.0)**: Integração com modelos GPT da OpenAI para funcionalidade de chat
- **FAISS-CPU 1.7.4**: Facebook AI Similarity Search para busca por similaridade vetorial e indexação de documentos
- **NumPy 1.24.3**: Biblioteca de computação numérica para operações com arrays

### Document Processing
- **python-docx (>=0.8.11)**: Leitura e processamento de documentos Microsoft Word (.docx)
- **openpyxl (>=3.0.0)**: Leitura e processamento de planilhas Excel (.xlsx)
- **pdfplumber (>=0.7.0)**: Extração de texto de documentos PDF
- **markdown (>=3.4.0)**: Processamento e renderização de conteúdo Markdown
- **pandas (>=1.5.0)**: Manipulação e análise de dados para dados estruturados

### Frontend & UI
- **Bootstrap 5**: Framework CSS para design web responsivo
- **Font Awesome**: Biblioteca de ícones para elementos de UI
- **HTML5/CSS3**: Padrões web modernos para marcação e estilização
- **JavaScript**: Interatividade do lado do cliente para a interface de chat

### Development & Deployment
- **Python 3.12**: Linguagem de programação
- **Git**: Sistema de controle de versão
- **CSV Logging**: Sistema de logging personalizado para monitoramento da aplicação

## 🆘 Suporte

Para problemas ou dúvidas:
1. Verifique os logs na pasta `logs/`
2. Confirme as configurações no `config.json`
3. Teste com o usuário administrador padrão
4. Reinicie a aplicação se necessário
5. Leia as documentações detalhadas: `INDEX_MANAGER_README.md`, `DATABASE.md`, `CHAT_MEMORY_README.md`,`QUERY_INTENT_README.md` 

## 📞 Contato

Para suporte técnico, dúvidas ou sugestões:

- **Email:** [igor.a.r.miranda@gmail.com](mailto:igor.a.r.miranda@gmail.com)
- **LinkedIn:** [https://www.linkedin.com/in/iaugusto/](https://www.linkedin.com/in/iaugusto/)

---

**Gladys IA** - Sua assistente inteligente para documentos! 🧠✨
