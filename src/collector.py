"""
collector.py
Coleta ofertas oficiais do Mercado Livre diretamente pelas categorias completas dos nichos
utilizando o Playwright (navegador Chrome real).
"""

import os
import re
import logging
from pathlib import Path
from typing import Optional
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

logger = logging.getLogger(__name__)

SESSION_DIR = Path("config/ml_session")
OFERTAS_URL = "https://www.mercadolivre.com.br/ofertas"


class MercadoLivreCollector:
    def __init__(self, config: dict):
        self.session_dir = SESSION_DIR
        if not self.session_dir.exists():
            logger.warning("⚠️ Pasta de sessão 'config/ml_session' não encontrada.")

    def buscar_produtos_nicho(self, categoria_id: str, filtros: dict, nicho_config: Optional[dict] = None) -> list[dict]:
        """Abre a página oficial de ofertas do nicho completo e extrai todos os produtos em promoção."""
        if not categoria_id or categoria_id.lower() in ["geral", "todos", "ofertas"]:
            url = OFERTAS_URL
            nome_log = "Ofertas Gerais"
        else:
            url = f"{OFERTAS_URL}?category={categoria_id}"
            nome_log = f"Nicho {categoria_id}"

        try:
            with sync_playwright() as p:
                context = p.chromium.launch_persistent_context(
                    user_data_dir=str(self.session_dir),
                    channel="chrome",
                    headless=False,
                    args=[
                        "--disable-blink-features=AutomationControlled",
                        "--start-maximized"
                    ],
                    ignore_default_args=["--enable-automation"],
                    locale="pt-BR"
                )

                page = context.pages[0] if context.pages else context.new_page()
                page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

                logger.info(f"Navegando para o nicho completo: {nome_log} ({url})...")
                page.goto(url, wait_until="domcontentloaded", timeout=30000)
                page.wait_for_timeout(3000)

                # Rola para baixo para carregar mais produtos do catálogo
                page.evaluate("window.scrollBy(0, 1000)")
                page.wait_for_timeout(1000)

                html_conteudo = page.content()
                context.close()

            soup = BeautifulSoup(html_conteudo, "html.parser")
            produtos = self._extrair_cards(soup, categoria_id or "geral")
            logger.info(f"Coletados {len(produtos)} produtos de ofertas em '{nome_log}'")
            return produtos

        except Exception as e:
            logger.error(f"Erro ao coletar ofertas ({nome_log}): {e}")
            return []

    def _extrair_cards(self, soup: BeautifulSoup, categoria_id: str) -> list[dict]:
        produtos = []
        cards = soup.select(".poly-card, .promotion-item, .andes-card, .ui-search-layout__item")

        for card in cards:
            try:
                # 1. Link do Produto
                tag_link = (
                    card.select_one("a.poly-component__title, a.promotion-item__link-container, a.ui-search-link")
                    or card.select_one("a[href*='MLB']")
                    or card.select_one("a[href*='mercadolivre.com.br/p/']")
                )
                if not tag_link:
                    continue

                link = tag_link.get("href", "").split("#")[0].split("?")[0]
                if not link or "mercadolivre.com" not in link:
                    continue

                # 2. Título do Produto
                tag_nome = card.select_one(".poly-component__title, .promotion-item__title, .ui-search-item__title")
                nome = tag_nome.get_text(strip=True) if tag_nome else tag_link.get_text(strip=True)
                if not nome or len(nome) < 6 or "economiza frete" in nome.lower() or "benefício" in nome.lower():
                    continue

                # 3. ID do produto
                id_match = re.search(r"MLB-?\d+", link)
                prod_id = id_match.group(0).replace("-", "") if id_match else link

                # 4. Imagem
                tag_img = card.select_one("img")
                img_url = ""
                if tag_img:
                    img_url = tag_img.get("data-src") or tag_img.get("src") or tag_img.get("srcset", "").split(" ")[0]

                # ============================================================
                #  EXTRAÇÃO PRECISA DE PREÇOS E DESCONTO OFICIAL
                # ============================================================
                desconto_oficial = 0
                tag_desc = card.select_one(".andes-money-amount__discount, .ui-search-price__discount, .poly-price__discount, [class*='discount']")
                if tag_desc:
                    texto_desc = tag_desc.get_text().upper()
                    if "OFF" in texto_desc or "%" in texto_desc:
                        desc_match = re.search(r"\d+", texto_desc)
                        if desc_match:
                            desconto_oficial = int(desc_match.group(0))

                card_limpo = BeautifulSoup(str(card), "html.parser")
                for tag_remover in card_limpo.select(".poly-price__installments, .ui-search-item__installments, [class*='installment'], .poly-coupon"):
                    tag_remover.decompose()

                # Preço Anterior ("De:")
                tag_anterior = card_limpo.select_one(".andes-money-amount--previous, s.andes-money-amount, del.andes-money-amount")
                preco_original = 0.0
                if tag_anterior:
                    frac = tag_anterior.select_one(".andes-money-amount__fraction")
                    cents = tag_anterior.select_one(".andes-money-amount__cents")
                    if frac:
                        v = float(frac.get_text(strip=True).replace(".", ""))
                        c = float("0." + cents.get_text(strip=True)) if cents else 0.0
                        preco_original = v + c

                # Preço Atual ("Por:")
                tag_atual = (
                    card_limpo.select_one(".poly-price__current .andes-money-amount:not(.andes-money-amount--previous)")
                    or card_limpo.select_one(".poly-price__current")
                    or card_limpo.select_one(".ui-search-price__second-line")
                    or card_limpo.select_one(".andes-money-amount:not(.andes-money-amount--previous)")
                )
                preco_atual = 0.0
                if tag_atual:
                    frac = tag_atual.select_one(".andes-money-amount__fraction")
                    cents = tag_atual.select_one(".andes-money-amount__cents")
                    if frac:
                        v = float(frac.get_text(strip=True).replace(".", ""))
                        c = float("0." + cents.get_text(strip=True)) if cents else 0.0
                        preco_atual = v + c

                if preco_atual <= 0:
                    continue

                if preco_original <= 0:
                    preco_original = preco_atual

                # Prioriza 100% o selo oficial de desconto estampado no site
                if desconto_oficial > 0:
                    desconto = desconto_oficial
                elif preco_original > preco_atual:
                    desconto = int(((preco_original - preco_atual) / preco_original) * 100)
                else:
                    desconto = 0

                # 5. Frete Grátis
                card_text = card.get_text().lower()
                frete_gratis = "frete grátis" in card_text or "full" in card_text

                # 6. Avaliação
                tag_aval = card.select_one(".poly-reviews__rating, .promotion-item__seller-rating")
                aval_nota = float(tag_aval.get_text(strip=True)) if tag_aval else 4.6

                produtos.append({
                    "id":               prod_id,
                    "nome":             nome,
                    "preco":            preco_atual,
                    "preco_original":   preco_original,
                    "desconto":         desconto,
                    "link":             link,
                    "imagem":           img_url,
                    "frete_gratis":     frete_gratis,
                    "avaliacao":        aval_nota,
                    "total_avaliacoes": 50,
                    "categoria":        categoria_id,
                })
            except Exception:
                continue

        return produtos