# Documentação do Sistema de Logging

## Visão Geral

A aplicação Gladys IA utiliza um sistema de logging personalizado que cria arquivos de log CSV estruturados para diferentes módulos. Este sistema fornece logs organizados e pesquisáveis com timestamps e diferentes níveis de log.

## Arquitetura

### Componentes Principais

1. **Classe AppLogger** - Classe base de logging que gerencia a criação de arquivos CSV e escrita de entradas de log
2. **Loggers Específicos por Módulo** - Loggers especializados para diferentes módulos da aplicação
3. **Baseado em Configuração** - Comportamento de logging controlado pelo `config.json`

### Estrutura dos Arquivos de Log

Todos os arquivos de log são armazenados no diretório `logs/` e seguem esta convenção de nomenclatura:
- `routes_dd-mm-yyyy.csv` - Logs principais da aplicação
- `file_readers_dd-mm-yyyy.csv` - Operações de leitura de arquivos
- `index_chat_manager_dd-mm-yyyy.csv` - Gerenciamento de memória de chat
- `index_manager_dd-mm-yyyy.csv` - Operações de índice vetorial
- `config_dd-mm-yyyy.csv` - Carregamento e validação de configuração

## Configuração

### LOGGING_CONFIG no config.json

```json
{
  "LOGGING_CONFIG": {
    "logs_directory": "logs",
    "log_level": "INFO",
    "log_format": "csv",
    "include_timestamp": true,
    "max_log_files": 30,
    "log_rotation": "daily"
  }
}
```

### Opções de Configuração

- **logs_directory**: Diretório onde os arquivos de log são armazenados (padrão: "logs")
- **log_level**: Nível mínimo de log a ser registrado (ERROR, WARNING, INFO, DEBUG)
- **log_format**: Atualmente apenas o formato CSV é suportado
- **include_timestamp**: Se deve incluir data/hora nas entradas de log
- **max_log_files**: Número máximo de arquivos de log a manter (os mais antigos são excluídos)
- **log_rotation**: Com que frequência criar novos arquivos de log ("daily" ou "monthly")

## Níveis de Log

O sistema suporta cinco níveis de log com a seguinte hierarquia:

1. **ERROR** (Nível 4) - Erros críticos que precisam de atenção imediata
2. **WARNING** (Nível 3) - Mensagens de aviso sobre problemas potenciais
3. **INFO** (Nível 2) - Mensagens informativas gerais
4. **SUCCESS** (Nível 2) - Mensagens de sucesso (tratadas como nível INFO)
5. **DEBUG** (Nível 1) - Informações detalhadas de debug

## Formato de Log CSV

Cada arquivo de log contém as seguintes colunas:

| Coluna | Descrição | Exemplo |
|--------|-----------|---------|
| Level | Nível do log | ERROR, WARNING, INFO, SUCCESS, DEBUG |
| Date | Data da entrada de log | 15/12/2024 |
| Time | Hora da entrada de log | 14:30:25 |
| Message | Conteúdo da mensagem de log | "Error creating embedding: API timeout" |

### Exemplo de Entrada de Log

```csv
Level,Date,Time,Message
ERROR,15/12/2024,14:30:25,"Error creating embedding: API timeout"
INFO,15/12/2024,14:30:26,"FAISS index loaded with 1250 chunks"
SUCCESS,15/12/2024,14:30:27,"New FAISS index created with 1250 chunks"
```

## Logging Específico por Módulo

### Logging do Index Manager

A classe IndexManager utiliza dois tipos de métodos de logging:

#### log_verbose(level, message)
- Registra logs apenas quando `verbose=True` na configuração
- Usado para informações operacionais detalhadas
- Controlado pela configuração `INDEX_CONFIG.verbose`

#### log_always(level, message)
- Sempre registra logs independentemente da configuração verbose
- Usado para erros críticos, avisos e eventos importantes
- Garante que informações importantes nunca sejam perdidas

### Exemplos de Uso

```python
# Logging verboso (apenas quando verbose=True)
self.log_verbose("info", f"Split {filename} into {len(chunks)} chunks")
self.log_verbose("debug", f"Chunk {i}: {len(chunk_text)} characters")

# Sempre registrar log (independentemente da configuração verbose)
self.log_always("error", f"Error creating embedding: {e}")
self.log_always("warning", f"Text length {len(text)} exceeds safe limit")
self.log_always("success", f"New FAISS index created with {count} chunks")
```

## Gerenciamento de Arquivos de Log

### Limpeza Automática

O sistema gerencia automaticamente os arquivos de log:

1. **Rotação Diária**: Novos arquivos de log criados a cada dia
2. **Política de Retenção**: Mantém apenas os N arquivos mais recentes (configurável)
3. **Limpeza Automática**: Arquivos antigos são automaticamente excluídos quando o limite é excedido

## Melhores Práticas

### Cada nivel de log tem seu proposito

- **ERROR**: Falhas do sistema, erros de API, exceções críticas
- **WARNING**: Problemas potenciais, uso depreciado, preocupações de performance
- **INFO**: Operações gerais, atualizações de status, mudanças de configuração
- **SUCCESS**: Conclusão bem-sucedida de operações importantes
- **DEBUG**: Fluxo de execução detalhado, valores de variáveis, informações de troubleshooting

### Formatação de Mensagens

- Uso de mensagens claras e descritivas
- Inclusão de contexto relevante (nomes de arquivos, contagens, detalhes de erro)

### Considerações de Performance

- Logging DEBUG pode ser verboso - use com moderação em produção
- I/O de arquivos de log é bufferizado para performance
- Limpeza automática previne problemas de espaço em disco
- Formato CSV permite análise e filtragem fáceis

## Análise de Logs

### Visualizando Logs

Arquivos de log podem ser abertos em qualquer editor de texto, aplicação de planilha, ou analisados programaticamente:

```python
import pandas as pd

# Carregar e analisar logs
df = pd.read_csv('logs/index_manager_15-12-2024.csv')
error_logs = df[df['Level'] == 'ERROR']
print(f"Total errors today: {len(error_logs)}")
```

### Padrões Comuns de Log

- **Criação de Índice**: Procure por mensagens SUCCESS com contagens de chunks
- **Investigação de Erros**: Filtre por nível ERROR e examine o conteúdo da mensagem
- **Monitoramento de Performance**: Verifique mensagens WARNING sobre timeouts ou limites
- **Rastreamento de Operações**: Use mensagens INFO para rastrear o fluxo de execução

## Solução de Problemas

### Problemas Comuns

1. **Diretório de Log Não Encontrado**: Certifique-se de que o diretório `logs/` existe ou é gravável
2. **Erros de Permissão**: Verifique as permissões do sistema de arquivos para o diretório de log
3. **Espaço em Disco**: Monitore o tamanho do diretório de log e ajuste `max_log_files` se necessário
4. **Logs Ausentes**: Verifique se a configuração de nível de log permite as mensagens desejadas

### Modo Debug

Para habilitar logging detalhado, defina as flags verbose apropriadas no `config.json`:

```json
{
  "INDEX_CONFIG": {
    "verbose": true
  },
  "FILE_READER_CONFIG": {
    "verbose": true
  }
}
```

## Melhorias Futuras

Possíveis melhorias para o sistema de logging:

1. **Logging Estruturado**: Formato JSON para melhor parsing
2. **Agregação de Logs**: Coleta centralizada de logs
3. **Monitoramento em Tempo Real**: Streaming de logs ao vivo
4. **Compressão de Logs**: Compressão automática de logs antigos
5. **Alertas**: Integração com sistemas de monitoramento

## Conclusão

O sistema de logging fornece visibilidade abrangente das operações da aplicação Gladys IA. Usando níveis de log apropriados e seguindo as melhores práticas, você pode efetivamente monitorar, debugar e manter a aplicação mantendo os arquivos de log organizados e gerenciáveis.