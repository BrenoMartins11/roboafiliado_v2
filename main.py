"""
main.py
Ponto de entrada do robô de divulgação de afiliados Mercado Livre (Multi-Nicho).
Orquestra: Coleta por Nicho -> Filtro -> Formatação -> Envio (Telegram/WhatsApp) -> PostgreSQL -> Agendamento (2h).
"""

import os
import sys
import time
import random
import logging
import yaml
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

# Carrega variáveis do arquivo .env antes de qualquer módulo
load_dotenv()

from src.collector import MercadoLivreCollector
from src.filters   import FiltroNicho
from src.afiliados import AffiliateManager
from src.formatter import MessageFormatter
from src.database  import Database
from src.senders   import TelegramSender, WhatsAppSender


# ============================================================
#  CONFIGURAÇÃO DE LOGGING
# ============================================================

def setup_logging(config: dict):
    log_cfg = config.get("logging", {})
    level   = getattr(logging, log_cfg.get("level", "INFO").upper(), logging.INFO)
    arquivo = log_cfg.get("arquivo", "logs/robo.log")
    Path(arquivo).parent.mkdir(parents=True, exist_ok=True)

    logging.basicConfig(
        level=level,
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(arquivo, encoding="utf-8"),
        ],
    )

logger = logging.getLogger("RoboAfiliados")


# ============================================================
#  CARREGAMENTO DA CONFIGURAÇÃO
# ============================================================

def carregar_config(path: str = "config/settings.yaml") -> dict:
    if not os.path.exists(path):
        raise FileNotFoundError(f"Arquivo de configuração não encontrado: {path}")
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


# ============================================================
#  CICLO PRINCIPAL (POR NICHO)
# ============================================================

def executar_ciclo(
    collector:  MercadoLivreCollector,
    filtro:     FiltroNicho,
    affiliate:  AffiliateManager,
    formatter:  MessageFormatter,
    db:         Database,
    telegram:   TelegramSender,
    whatsapp:   WhatsAppSender,
    config:     dict,
):
    """Executa um ciclo completo iterando pelos 5 nichos configurados."""
    logger.info("=" * 65)
    logger.info(f"Iniciando ciclo multi-nicho: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")

    nichos = config.get("nichos", [])
    if not nichos:
        logger.warning("Nenhum nicho configurado no settings.yaml.")
        return

    intervalo_msg = config.get("agendamento", {}).get("intervalo_entre_mensagens_seg", 25)
    intervalo_nichos = config.get("agendamento", {}).get("intervalo_entre_nichos_seg", 40)

    # Verifica conexão da Evolution API uma vez antes do ciclo
    wa_online = whatsapp.instancia_conectada()
    if not wa_online:
        logger.warning("⚠️  Instância da Evolution API não está conectada/aberta. Envios do WhatsApp podem falhar.")

    total_enviados_ciclo = 0

    for idx, nicho in enumerate(nichos, 1):
        nicho_id = nicho.get("id")
        nicho_nome = nicho.get("nome", nicho_id)
        cat_id = nicho.get("categoria_id")
        tg_chat = nicho.get("telegram_chat_id")
        wa_group = nicho.get("whatsapp_group_id")

        logger.info(f"\n[{idx}/{len(nichos)}] Processando Nicho: {nicho_nome} (Cat: {cat_id})")

        # 1. Coleta específica do nicho
        filtros_combinados = filtro.mesclar_filtros(nicho)
        produtos = collector.buscar_produtos_nicho(cat_id, filtros_combinados)

        # 2. Filtragem e ranqueamento
        produtos_aprovados = filtro.filtrar(produtos, nicho)

        if not produtos_aprovados:
            logger.info(f"Nenhum produto aprovado para o nicho '{nicho_nome}'.")
            continue

        # 3. Envio dos produtos aprovados para os respectivos grupos
        for p in produtos_aprovados:
            prod_id = p["id"]
            link_afiliado = affiliate.gerar_link_afiliado(p["link"])

            # Formatações específicas para cada plataforma
            msg_telegram = formatter.formatar_telegram(p, link_afiliado)
            msg_whatsapp = formatter.formatar_whatsapp(p, link_afiliado)

            enviou_em_algum = False

            # --- Telegram ---
            if tg_chat:
                if db.ja_enviado(prod_id, tg_chat, "telegram"):
                    logger.debug(f"Pulando Telegram (já enviado): {prod_id}")
                else:
                    sucesso_tg = telegram.enviar_para_chat_sync(tg_chat, p, msg_telegram)
                    if sucesso_tg:
                        db.registrar(prod_id, tg_chat, "telegram", nicho_id)
                        enviou_em_algum = True

            # --- WhatsApp ---
            if wa_group:
                if db.ja_enviado(prod_id, wa_group, "whatsapp"):
                    logger.debug(f"Pulando WhatsApp (já enviado): {prod_id}")
                else:
                    sucesso_wa = whatsapp.enviar_para_grupo(wa_group, p, msg_whatsapp)
                    if sucesso_wa:
                        db.registrar(prod_id, wa_group, "whatsapp", nicho_id)
                        enviou_em_algum = True

            if enviou_em_algum:
                total_enviados_ciclo += 1
                pausa = intervalo_msg + random.randint(-4, 4)
                logger.debug(f"Pausa anti-spam entre mensagens: {max(pausa, 5)}s")
                time.sleep(max(pausa, 5))

        # Pausa entre nichos para diluir o tráfego
        if idx < len(nichos):
            time.sleep(max(intervalo_nichos, 10))

    # Estatísticas no PostgreSQL
    stats = db.estatisticas()
    logger.info(f"\n Ciclo concluído. Produtos enviados neste ciclo: {total_enviados_ciclo}")
    logger.info(f"📊 Estatísticas últimos 7 dias: Total={stats.get('total_7d')} | Plataformas={stats.get('por_plataforma')}")


# ============================================================
#  HORÁRIO DE OPERAÇÃO
# ============================================================

def dentro_do_horario(config: dict) -> bool:
    agora  = datetime.now().strftime("%H:%M")
    inicio = config.get("agendamento", {}).get("horario_inicio", "08:00")
    fim    = config.get("agendamento", {}).get("horario_fim", "22:30")
    return inicio <= agora <= fim


# ============================================================
#  LOOP PRINCIPAL
# ============================================================

def main():
    config = carregar_config()
    setup_logging(config)

    logger.info("🤖 Robô de Afiliados Mercado Livre (Multi-Nicho) iniciado!")

    try:
        db = Database(config)
    except Exception as e:
        logger.critical(f"Falha ao conectar ao banco PostgreSQL: {e}")
        logger.critical("Verifique se o container Docker do Postgres está rodando e o arquivo .env está preenchido.")
        sys.exit(1)

    collector = MercadoLivreCollector(config)
    filtro    = FiltroNicho(config)
    affiliate = AffiliateManager(config)
    formatter = MessageFormatter(config)
    telegram  = TelegramSender(config)
    whatsapp  = WhatsAppSender(config)

    # 120 minutos (2 horas)
    intervalo_base = config.get("agendamento", {}).get("intervalo_minutos", 120) * 60
    variacao       = config.get("agendamento", {}).get("variacao_minutos", 10) * 60

    while True:
        if dentro_do_horario(config):
            try:
                executar_ciclo(collector, filtro, affiliate, formatter, db, telegram, whatsapp, config)
            except Exception as e:
                logger.exception(f"Erro imprevisto durante o ciclo: {e}")
        else:
            logger.info("⏸️  Fora do horário operacional configurado. Aguardando...")

        proximo_segundos = intervalo_base + random.randint(-variacao, variacao)
        minutos = proximo_segundos // 60
        logger.info(f"⏳ Próximo ciclo agendado para daqui a ~{minutos} minutos.")
        time.sleep(max(proximo_segundos, 60))


if __name__ == "__main__":
    main()
