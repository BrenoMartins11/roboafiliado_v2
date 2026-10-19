🛒 Mercado Livre Affiliate Bot v2 (24/7)
Sistema autônomo de automação comercial e dados projetado para monitorar, filtrar e garimpar promoções reais no Mercado Livre Brasil, gerando links oficiais de afiliados (`meli.la`) e distribuindo as ofertas com fotos e textos de alta conversão para canais do Telegram e grupos do WhatsApp.
---
📌 Visão Geral
A operação manual de grupos de afiliados sofre com três gargalos: tempo excessivo para garimpar descontos reais, atraso em ofertas relâmpago e o risco de incomodar os membros com enxurrada de mensagens repetidas ou descontextualizadas.
Este projeto resolve essa dor com uma esteira 100% automatizada e conteinerizada:
Varredura contínua: Monitora categorias estratégicas do Mercado Livre via navegador headless com sessão real autenticada.
Filtro de qualidade: Descarta falsos descontos (armadilha de parcelamento) e aplica regras de preço mínimo, desconto percentual e exclusão de palavras-chave.
Geração de comissão: Utiliza o painel de criadores do Mercado Livre para gerar o link encurtado oficial (`meli.la`).
Memória de disparo: Consulta o banco PostgreSQL para garantir um período de cooldown de 7 dias por produto/nicho, evitando spam.
Distribuição segmentada: Envia a foto oficial e a cópia formatada para o respectivo canal do Telegram e grupo do WhatsApp, intercalando nichos com pausas calculadas (round-robin).
---
🏗️ Arquitetura da Aplicação
```text
               ┌────────────────────────────────────────────────────────┐
               │             MERCADO LIVRE (Páginas de Ofertas)         │
               └──────────────────────────┬─────────────────────────────┘
                                          │ Playwright Chromium
                                          ▼ (Sessão Persistente)
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│ DOCKER CONTAINER: robo_afiliados_app (Python 3.11)                                      │
│                                                                                         │
│  1. Collector (HTML + BeautifulSoup) ──► Extrai título, foto, preços e badge % OFF      │
│  2. Filters Engine ───────────────────► Valida regras de negócio e palavras proibidas   │
│  3. Database Cooldown Check ──────────► Consulta PostgreSQL (Produto enviado < 7 dias?) │
│  4. Link Builder (Afiliados) ─────────► Abre painel ML e copia link oficial 'meli.la'   │
│  5. Formatter ────────────────────────► Gera Markdown (Telegram) e formatação WhatsApp  │
└────────────────────────────┬───────────────────────────────────────┬────────────────────┘
                             │                                       │
                             ▼ HTTP                                  ▼ HTTP (API Key)
               ┌───────────────────────────┐         ┌────────────────────────────────────┐
               │     TELEGRAM BOT API      │         │ DOCKER: Evolution API v2 (Node.js) │
               └─────────────┬─────────────┘         └──────────────────┬─────────────────┘
                             │                                          │ WebSocket
                             ▼                                          ▼ (Baileys + Redis)
               ┌───────────────────────────┐         ┌────────────────────────────────────┐
               │    Canais do Telegram     │         │        Grupos do WhatsApp          │
               │  (Fitness / Ferramentas / │         │     (Segmentados por Nicho)        │
               │     Moda / Informática)   │         └────────────────────────────────────┘
               └───────────────────────────┘
```
---
🛠️ Tecnologias Utilizadas
Componente	Tecnologia	Finalidade
Linguagem	Python 3.11	Núcleo do robô, orquestração e regras de negócio
Automação Web	Playwright Chromium	Navegação headless resiliente a bloqueios anti-bot
Parsing HTML	BeautifulSoup4	Limpeza e extração cirúrgica de metadados dos produtos
Banco de Dados	PostgreSQL 15	Persistência do histórico de envios e controle de cooldown
WhatsApp Gateway	Evolution API v2	Conexão persistente com WhatsApp Web via Baileys

Cache & Fila	Redis (Alpine)	Gestão de sessões e eventos da Evolution API
Disparo Telegram	Telegram Bot API	Envio direto de mensagens com foto e legendas Markdown
Orquestração	Docker & Docker Compose	Isolamento completo da stack em rede interna bridge
---
🎯 Decisões Técnicas e Desafios Superados
Bypass de Proteção Anti-Bot: Requisições HTTP convencionais (`requests`/`httpx`) eram bloqueadas pelo Mercado Livre com redirecionamentos para verificações de login (`/gz/account-verification`). A solução adotada foi o Playwright com contexto de navegador persistente (`config/ml_session`), simulando comportamento e resolução de usuário desktop real.
Filtro Anti-Armadilha de Parcelamento: No DOM do Mercado Livre, parcelas (ex: "em 12x de R$ 749") compartilham as mesmas classes CSS do preço total à vista. O extrator desconstrói os blocos de parcelamento antes de capturar o valor promocional e valida o desconto através da badge oficial de percentual (`.andes-money-amount__discount`).
Despacho Intercalado (Round-Robin): Em vez de descarregar lotes massivos em um único grupo, o orquestrador distribui uma oferta por nicho com intervalos de ~10 segundos, prevenindo penalizações do WhatsApp e garantindo engajamento dos membros.
Persistência de Dados e Deduplicação: A tabela `enviados` possui chave única composta e índice temporal, permitindo checagens de cooldown com custo computacional mínimo antes de iniciar a etapa pesada de link building.
---
📁 Estrutura do Repositório
```text
robo_afiliados_v2/
├── config/
│   ├── settings.yaml          # Mapeamento de categorias, nichos e IDs de chat
│   └── ml_session/            # Perfil do navegador autenticado (ignorado no Git)
├── src/
│   ├── collector.py           # Raspador de ofertas com Playwright + BS4
│   ├── afiliados.py           # Gerador automatizado de links oficiais (meli.la)
│   ├── filters.py             # Validação de descontos, preços e termos proibidos
│   ├── formatter.py           # Modelos de texto personalizados para cada plataforma
│   ├── database.py            # Camada de conexão e queries no PostgreSQL
│   └── senders/
│       ├── telegram.py        # Disparador para canais do Telegram
│       └── whatsapp.py        # Disparador para grupos via Evolution API v2
├── docker-compose.yml         # Orquestração (Postgres, Redis, Evolution API e Robô)
├── Dockerfile                 # Build do container com runtime Playwright + Python
├── main.py                    # Loop principal de execução contínua
├── requirements.txt           # Dependências Python
└── .env.example               # Template de variáveis de ambiente
```
---
🚀 Como Executar
1. Clonar o repositório e preparar o ambiente
```bash
git clone https://github.com/BrenoMartins11/roboafiliado_v2.git
cd roboafiliado_v2
cp .env.example .env
```
Preencha o `.env` com suas credenciais:
```ini
TELEGRAM_BOT_TOKEN="seu_token_aqui"
EVOLUTION_API_URL="http://evolution_api:8080"
EVOLUTION_API_KEY="sua_chave_secreta"
EVOLUTION_INSTANCE_NAME="robo_afiliadov2"

POSTGRES_DB="afiliados_mercado_livre_db"
POSTGRES_USER="postgres_user"
POSTGRES_PASSWORD="sua_senha"
POSTGRES_HOST="postgres"
POSTGRES_PORT=5432
```
2. Autenticar a sessão do Mercado Livre
Em ambiente local, execute o script de login uma única vez para salvar os cookies de autenticação na pasta `config/ml_session`:
```bash
python scripts/login_ml.py
```
3. Iniciar toda a infraestrutura com Docker
```bash
docker compose up -d --build
```
4. Conectar o WhatsApp na Evolution API
Acesse no seu navegador a interface da Evolution API para escanear o QR Code da sua instância:
```text
http://localhost:8080/instance/connect/robo_afiliadov2
```
5. Acompanhar os logs de execução
```bash
docker compose logs -f robo
```
---
⚙️ Configuração de Nichos (`config/settings.yaml`)
```yaml
niches:
  fitness:
    category_id: "MLB1276"
    min_discount: 20
    min_price: 30.0
    telegram_chat_id: "-1001234567890"
    whatsapp_jid: "120363000000000000@g.us"
    banned_words: ["usado", "defeito", "replica"]

  ferramentas:
    category_id: "MLB1500"
    min_discount: 25
    min_price: 50.0
    telegram_chat_id: "-1009876543210"
    whatsapp_jid: "120363111111111111@g.us"
    banned_words: ["manual", "brinquedo"]
```
---
👨‍💻 Autor
Desenvolvido por Breno Martins
Estudante de Sistemas de Informação & Desenvolvedor de Automações Python
[GitHub](https://github.com/BrenoMartins11/roboafiliado_v2)
[Portfólio Web](https://portifolio-breno-martins-h6q3.vercel.app/)