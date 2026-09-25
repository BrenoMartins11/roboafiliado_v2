# 🤖 Robô de Afiliados — Mercado Livre → Telegram & WhatsApp (Evolution API)

Automação multi-nicho que coleta ofertas e produtos do Mercado Livre, aplica filtros personalizados (preço, desconto, avaliação, frete grátis e palavras-chave), insere tags de afiliado e distribui automaticamente para grupos segmentados no **Telegram** e **WhatsApp**, utilizando **PostgreSQL no Docker** para deduplicação e controle de histórico.

---

## 📁 Estrutura do Projeto

```text
robo_afiliados/
├── config/
│   └── settings.yaml         # Configuração dos 5 nichos, filtros e templates
├── src/
│   ├── collector.py          # Coleta e normalização de ofertas no Mercado Livre
│   ├── filters.py            # Filtros gerais e específicos por nicho
│   ├── afiliados.py          # Inserção de tag de afiliado
│   ├── formatter.py          # Templates de mensagens para WhatsApp e Telegram
│   ├── database.py           # Conexão e deduplicação no PostgreSQL
│   └── senders/
│       ├── __init__.py
│       ├── telegram.py       # Envio de fotos e legendas via Bot API
│       └── whatsapp.py       # Envio via Evolution API
├── logs/                     # Arquivos de log e auditoria
├── .env.example              # Modelo de variáveis de ambiente
├── .env                      # Suas credenciais locais (não versionar)
├── main.py                   # Ponto de entrada e agendador (ciclos de 2h)
├── Dockerfile                # Imagem Docker da aplicação
├── docker-compose.yml        # Orquestração (PostgreSQL + Robô)
└── requirements.txt
```

---

## ⚙️ 1. Configuração das Variáveis de Ambiente (`.env`)

Copie o arquivo `.env.example` para `.env`:
```bash
cp .env.example .env
```

Preencha com seus dados locais:
```env
# Banco de Dados (PostgreSQL)
DB_HOST=localhost            # Ou 'postgres' se rodar o robô dentro do docker-compose
DB_PORT=5432
DB_USER=postgres
DB_PASSWORD=sua_senha_aqui
DB_NAME=robo_afiliados

# Telegram
TELEGRAM_TOKEN=seu_bot_token_do_botfather

# WhatsApp (Evolution API)
EVOLUTION_API_URL=http://localhost:8080
EVOLUTION_API_KEY=sua_api_key_da_evolution
EVOLUTION_INSTANCE=sua_instancia

# Mercado Livre Afiliado
ML_AFFILIATE_ID=seu_id_afiliado
```

---

## 🎯 2. Configuração dos 5 Nichos (`config/settings.yaml`)

No arquivo `config/settings.yaml`, defina os 5 nichos que você quer rodar. Cada nicho possui sua categoria no Mercado Livre e os respectivos IDs de grupo no Telegram e WhatsApp:

```yaml
nichos:
  - id: "smartphones"
    nome: "Smartphones & Acessórios"
    categoria_id: "MLB1051"
    telegram_chat_id: "-1001234567890"
    whatsapp_group_id: "120363000000000001@g.us"

  - id: "informatica"
    nome: "Informática & PC Gamer"
    categoria_id: "MLB1648"
    telegram_chat_id: "-1001234567891"
    whatsapp_group_id: "120363000000000002@g.us"
  ...
```

---

## 🚀 3. Como Executar

### Opção A: Usando Docker Compose (Recomendado)
Sobe o banco de dados PostgreSQL e o robô em containers isolados:
```bash
docker-compose up -d --build
```

Para acompanhar os logs de execução:
```bash
docker-compose logs -f robo
```

### Opção B: Rodando Localmente com Python (com Postgres no Docker)
Se o seu PostgreSQL já estiver rodando em container (ex: porta `5432`):

1. Crie e ative o ambiente virtual:
```bash
python -m venv venv
source venv/bin/activate   # Linux / Mac
# ou: venv\Scripts\activate no Windows
```

2. Instale as dependências:
```bash
pip install -r requirements.txt
```

3. Execute o robô:
```bash
python main.py
```
