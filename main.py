"""
main.py
Ponto de entrada do robô de afiliados Mercado Livre (Multi-Nicho).
Orquestra: Coleta de todos os nichos -> Envio intercalado em rodízio (Round-Robin) -> Agendamento.
"""

import os
import sys
import time
import random
import logging
import yaml
from datetime import datetime
from pathlib import Path
from logging.handlers import RotatingFileHandler
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
            RotatingFileHandler(arquivo, maxBytes=10 * 1024 * 1024, backupCount=3, encoding="utf-8"),
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
    logger.info(f"Iniciando ciclo intercalado multi-nicho: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")

    nichos = config.get("nichos", [])
    if not nichos:
        logger.warning("Nenhum nicho configurado no settings.yaml.")
        return

    intervalo_msg = config.get("agendamento", {}).get("intervalo_entre_mensagens_seg", 60)

    # -------------------------------------------------------------
    # ETAPA 1: Coleta e filtragem prévia de TODOS os nichos
    # -------------------------------------------------------------
    filas_por_nicho = {}

    for nicho in nichos:
        nicho_id = nicho.get("id")
        nicho_nome = nicho.get("nome", nicho_id)
        cat_id = nicho.get("categoria_id")
        tg_chat = nicho.get("telegram_chat_id")
        wa_group = nicho.get("whatsapp_group_id")

        logger.info(f"\n🔍 Coletando ofertas para o nicho: {nicho_nome} ({cat_id})...")
        filtros_combinados = filtro.mesclar_filtros(nicho)
        produtos = collector.buscar_produtos_nicho(cat_id, filtros_combinados, nicho)
        produtos_aprovados = filtro.filtrar(produtos, nicho)

        # Filtra apenas os que ainda NÃO foram enviados para ambos os canais
        pendentes = []
        for p in produtos_aprovados:
            prod_id = p["id"]
            ja_tg = db.ja_enviado(prod_id, tg_chat, "telegram") if tg_chat else True
            ja_wa = db.ja_enviado(prod_id, wa_group, "whatsapp") if wa_group else True

            if not (ja_tg and ja_wa):
                pendentes.append(p)
            else:
                logger.debug(f"Pulado (já enviado nos últimos 7 dias): {prod_id}")

        filas_por_nicho[nicho_id] = {
            "nicho": nicho,
            "produtos": pendentes
        }
        logger.info(f"📦 Nicho '{nicho_nome}': {len(pendentes)} produtos novos na fila para disparo.")

    # -------------------------------------------------------------
    # ETAPA 2: Disparo em Rodízio Intercalado (Round-Robin)
    # -------------------------------------------------------------
    total_enviados_ciclo = 0
    ha_produtos_pendentes = True
    rodada = 1

    while ha_produtos_pendentes:
        ha_produtos_pendentes = False
        logger.info(f"\n--- Iniciando Rodada {rodada} de disparos intercalados ---")

        for nicho_id, dados in filas_por_nicho.items():
            lista_produtos = dados["produtos"]
            nicho = dados["nicho"]
            nicho_nome = nicho.get("nome", nicho_id)
            tg_chat = nicho.get("telegram_chat_id")
            wa_group = nicho.get("whatsapp_group_id")

            if lista_produtos:
                ha_produtos_pendentes = True
                p = lista_produtos.pop(0)  # Pega o próximo produto da fila deste nicho
                prod_id = p["id"]

                # Checa pendências
                ja_tg = db.ja_enviado(prod_id, tg_chat, "telegram") if tg_chat else True
                ja_wa = db.ja_enviado(prod_id, wa_group, "whatsapp") if wa_group else True

                if ja_tg and ja_wa:
                    continue

                logger.info(f"[{nicho_nome}] Gerando link para: {p['nome'][:40]}...")
                link_afiliado = affiliate.gerar_link_afiliado(p["link"])

                msg_telegram = formatter.formatar_telegram(p, link_afiliado)
                msg_whatsapp = formatter.formatar_whatsapp(p, link_afiliado)

                enviou_em_algum = False

                # Envio Telegram
                if tg_chat and not ja_tg:
                    sucesso_tg = telegram.enviar_para_chat_sync(tg_chat, p, msg_telegram)
                    if sucesso_tg:
                        db.registrar(prod_id, tg_chat, "telegram", nicho_id)
                        enviou_em_algum = True

                # Envio WhatsApp
                if wa_group and not ja_wa:
                    sucesso_wa = whatsapp.enviar_para_grupo(wa_group, p, msg_whatsapp)
                    if sucesso_wa:
                        db.registrar(prod_id, wa_group, "whatsapp", nicho_id)
                        enviou_em_algum = True

                if enviou_em_algum:
                    total_enviados_ciclo += 1
                    # Variação suave de +/- 2 segundos (entre 8s e 12s)
                    pausa = intervalo_msg + random.randint(-2, 2)
                    logger.info(f"⏳ Pausa de {max(pausa, 5)}s antes da postagem no próximo nicho...")
                    time.sleep(max(pausa, 5))

        rodada += 1

    stats = db.estatisticas()
    logger.info(f"\n🏁 Ciclo intercalado concluído. Total enviado neste ciclo: {total_enviados_ciclo}")
    logger.info(f"📊 Estatísticas últimos 7 dias: Total={stats.get('total_7d')} | Plataformas={stats.get('por_plataforma')}")


def dentro_do_horario(config: dict) -> bool:
    agora  = datetime.now().strftime("%H:%M")
    inicio = config.get("agendamento", {}).get("horario_inicio", "08:00")
    fim    = config.get("agendamento", {}).get("horario_fim", "22:30")
    return inicio <= agora <= fim


def main():
    config = carregar_config()
    setup_logging(config)

    logger.info("🤖 Robô de Afiliados Mercado Livre (Multi-Nicho Intercalado) iniciado!")

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

    intervalo_base = config.get("agendamento", {}).get("intervalo_minutos", 25) * 60
    variacao       = config.get("agendamento", {}).get("variacao_minutos", 5) * 60

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