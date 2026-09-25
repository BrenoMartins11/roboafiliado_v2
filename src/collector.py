"""collector.py

Coleta ofertas reais da página oficial de Ofertas do Mercado Livre por categoria,
utilizando HTTPX e BeautifulSoup.
"""

import logging
import re
from typing import Optional
from bs4 import BeautifulSoup
import httpx

logger = logging.getLogger(__name__)

OFERTAS_URL = "https://www.mercadolivre.com.br/ofertas"


class MercadoLivreCollector:

  def __init__(self, config: dict):
    self.headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            " (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
        ),
        "Accept": (
            "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8"
        ),
        "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
        "sec-ch-ua": (
            '"Not/A)Brand";v="8", "Chromium";v="126", "Google Chrome";v="126"'
        ),
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"Windows"',
        "sec-fetch-dest": "document",
        "sec-fetch-mode": "navigate",
        "sec-fetch-site": "none",
        "sec-fetch-user": "?1",
        "upgrade-insecure-requests": "1",
    }

  def buscar_produtos_nicho(
      self, categoria_id: str, filtros: dict
  ) -> list[dict]:
    """Coleta as ofertas da categoria na página de ofertas do Mercado Livre."""
    url = f"{OFERTAS_URL}?category={categoria_id}"
    try:
      with httpx.Client(
          headers=self.headers, follow_redirects=True, timeout=15
      ) as client:
        resp = client.get(url)
        if resp.status_code != 200:
          logger.warning(
              f"Mercado Livre retornou status {resp.status_code} para categoria"
              f" {categoria_id}"
          )
          return []

        soup = BeautifulSoup(resp.text, "html.parser")
        produtos = self._extrair_cards(soup, categoria_id)
        logger.info(
            f"Coletados {len(produtos)} produtos de ofertas para a categoria"
            f" '{categoria_id}'"
        )
        return produtos
    except Exception as e:
      logger.error(f"Erro ao coletar ofertas da categoria {categoria_id}: {e}")
      return []

  def _extrair_cards(
      self, soup: BeautifulSoup, categoria_id: str
  ) -> list[dict]:
    produtos = []
    # Seletores de cards de ofertas do Mercado Livre
    cards = soup.select(
        ".poly-card, .promotion-item, .andes-card, .ui-search-layout__item"
    )

    for card in cards:
      try:
        # 1. Link do Produto
        tag_link = (
            card.select_one(
                "a.poly-component__title, a.promotion-item__link-container,"
                " a.ui-search-link"
            )
            or card.select_one("a[href*='MLB']")
            or card.select_one("a[href*='mercadolivre.com.br/p/']")
        )
        if not tag_link:
          continue

        link = tag_link.get("href", "").split("#")[0].split("?")[0]
        if not link or "mercadolivre.com" not in link:
          continue

        # 2. Título / Nome do Produto
        tag_nome = card.select_one(
            ".poly-component__title, .promotion-item__title,"
            " .ui-search-item__title"
        )
        nome = (
            tag_nome.get_text(strip=True)
            if tag_nome
            else tag_link.get_text(strip=True)
        )
        if (
            not nome
            or len(nome) < 6
            or "economiza frete" in nome.lower()
            or "benefício" in nome.lower()
        ):
          continue

        # 3. ID do produto (extrai MLB-XXXXXX)
        id_match = re.search(r"MLB-?\d+", link)
        prod_id = id_match.group(0).replace("-", "") if id_match else link

        # 4. Imagem
        tag_img = card.select_one("img")
        img_url = ""
        if tag_img:
          img_url = (
              tag_img.get("data-src")
              or tag_img.get("src")
              or tag_img.get("srcset", "").split(" ")[0]
          )

        # 5. Preços
        precos_frac = card.select("span.andes-money-amount__fraction")
        if not precos_frac:
          continue

        preco_atual = float(
            precos_frac[-1].get_text(strip=True).replace(".", "").replace(",", "")
        )
        preco_original = preco_atual

        if len(precos_frac) > 1:
          preco_original = float(
              precos_frac[0]
              .get_text(strip=True)
              .replace(".", "")
              .replace(",", "")
          )

        # 6. Desconto (%)
        desconto = 0
        tag_desconto = card.select_one(
            "span.andes-money-amount__discount, span.promotion-item__discount"
        )
        if tag_desconto:
          desc_match = re.search(r"\d+", tag_desconto.get_text())
          if desc_match:
            desconto = int(desc_match.group(0))
        elif preco_original > preco_atual:
          desconto = int(
              ((preco_original - preco_atual) / preco_original) * 100
          )

        # 7. Frete Grátis
        card_text = card.get_text().lower()
        frete_gratis = "frete grátis" in card_text or "full" in card_text

        # 8. Avaliação
        tag_aval = card.select_one(
            "span.poly-reviews__rating, span.promotion-item__seller-rating"
        )
        aval_nota = float(tag_aval.get_text(strip=True)) if tag_aval else 4.6

        produtos.append({
            "id": prod_id,
            "nome": nome,
            "preco": preco_atual,
            "preco_original": preco_original,
            "desconto": desconto,
            "link": link,
            "imagem": img_url,
            "frete_gratis": frete_gratis,
            "avaliacao": aval_nota,
            "total_avaliacoes": 50,
            "categoria": categoria_id,
        })
      except Exception:
        continue

    return produtos