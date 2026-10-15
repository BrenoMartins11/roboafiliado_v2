"""
main.py
Ponto de entrada do robô de afiliados Mercado Livre (Multi-Nicho).
Orquestra: Coleta por Nicho -> Filtro -> Checagem de Banco -> Geração de Link -> Disparo (Telegram/WhatsApp).
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

load_dotenv()

from src.collector import MercadoLivreCollector
from src.filters   import FiltroNicho
from src.afiliados import AffiliateManager
from src.formatter import MessageFormatter
from src.database  import Database
from src.senders   import TelegramSender, WhatsAppSender


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


def carregar_config(path: str = "config/settings.yaml") -> dict:
    if not os.path.exists(path):
        raise FileNotFoundError(f"Arquivo de configuração não encontrado: {path}")
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


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
    logger.info("=" * 65)
    logger.info(f"Iniciando ciclo multi-nicho: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")

    nichos = config.get("nichos", [])
    if not nichos:
        logger.warning("Nenhum nicho configurado no settings.yaml.")
        return

    intervalo_msg = config.get("agendamento", {}).get("intervalo_entre_mensagens_seg", 20)
    intervalo_nichos = config.get("agendamento", {}).get("intervalo_entre_nichos_seg", 30)

    total_enviados_ciclo = 0

    for idx, nicho in enumerate(nichos, 1):
        nicho_id = nicho.get("id")
        nicho_nome = nicho.get("nome", nicho_id)
        cat_id = nicho.get("categoria_id")
        tg_chat = nicho.get("telegram_chat_id")
        wa_group = nicho.get("whatsapp_group_id")

        logger.info(f"\n[{idx}/{len(nichos)}] Processando Nicho: {nicho_nome} (Cat: {cat_id})")

        # 1. Coleta específica do nicho via Playwright
        filtros_combinados = filtro.mesclar_filtros(nicho)
        produtos = collector.buscar_produtos_nicho(
            cat_id, filtros_combinados, nicho
        )

        # 2. Filtragem dos melhores produtos
        produtos_aprovados = filtro.filtrar(produtos, nicho)

        if not produtos_aprovados:
            logger.info(f"Nenhum produto aprovado para o nicho '{nicho_nome}'.")
            continue

        # 3. Itera sobre os produtos aprovados
        for p in produtos_aprovados:
            prod_id = p["id"]

            # ============================================================
            #  CHECAGEM PRÉVIA NO BANCO ANTES DE GERAR O LINK
            # ============================================================
            ja_foi_telegram = db.ja_enviado(prod_id, tg_chat, "telegram") if tg_chat else True
            ja_foi_whatsapp = db.ja_enviado(prod_id, wa_group, "whatsapp") if wa_group else True

            # Se já foi postado em ambos os canais, pula sem perder tempo gerando link
            if ja_foi_telegram and ja_foi_whatsapp:
                logger.info(f"⏭️  Pulando [{prod_id}] {p['nome'][:35]}... (já enviado recentemente nos últimos 7 dias)")
                continue

            # Se precisa ser enviado, agora sim gera o link oficial via Playwright
            logger.info(f"⏳ Gerando link de afiliado para: {p['nome'][:40]}...")
            link_afiliado = affiliate.gerar_link_afiliado(p["link"])

            # Formata as mensagens
            msg_telegram = formatter.formatar_telegram(p, link_afiliado)
            msg_whatsapp = formatter.formatar_whatsapp(p, link_afiliado)

            enviou_em_algum = False

            # --- Disparo Telegram ---
            if tg_chat and not ja_foi_telegram:
                sucesso_tg = telegram.enviar_para_chat_sync(tg_chat, p, msg_telegram)
                if sucesso_tg:
                    db.registrar(prod_id, tg_chat, "telegram", nicho_id)
                    enviou_em_algum = True
                else:
                    logger.warning(f"⚠️ Telegram falhou ao postar o produto {prod_id}")

            # --- Disparo WhatsApp ---
            if wa_group and not ja_foi_whatsapp:
                sucesso_wa = whatsapp.enviar_para_grupo(wa_group, p, msg_whatsapp)
                if sucesso_wa:
                    db.registrar(prod_id, wa_group, "whatsapp", nicho_id)
                    enviou_em_algum = True
                else:
                    logger.warning(f"⚠️ WhatsApp falhou ao postar o produto {prod_id}")

            if enviou_em_algum:
                total_enviados_ciclo += 1
                pausa = intervalo_msg + random.randint(-5, 10)
                logger.debug(f"Pausa anti-spam entre mensagens: {max(pausa, 5)}s")
                time.sleep(pausa)

        if idx < len(nichos):
            time.sleep(max(intervalo_nichos, 10))

    stats = db.estatisticas()
    logger.info(f"\n🏁 Ciclo concluído. Produtos enviados neste ciclo: {total_enviados_ciclo}")
    logger.info(f"📊 Estatísticas últimos 7 dias: Total={stats.get('total_7d')} | Plataformas={stats.get('por_plataforma')}")


def dentro_do_horario(config: dict) -> bool:
    agora  = datetime.now().strftime("%H:%M")
    inicio = config.get("agendamento", {}).get("horario_inicio", "08:00")
    fim    = config.get("agendamento", {}).get("horario_fim", "22:30")
    return inicio <= agora <= fim


def main():
    config = carregar_config()
    setup_logging(config)

    logger.info("🤖 Robô de Afiliados Mercado Livre (Multi-Nicho) iniciado!")

    try:
        db = Database(config)
    except Exception as e:
        logger.critical(f"Falha ao conectar ao banco PostgreSQL: {e}")
        sys.exit(1)

    collector = MercadoLivreCollector(config)
    filtro    = FiltroNicho(config)
    affiliate = AffiliateManager(config)
    formatter = MessageFormatter(config)
    telegram  = TelegramSender(config)
    whatsapp  = WhatsAppSender(config)

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