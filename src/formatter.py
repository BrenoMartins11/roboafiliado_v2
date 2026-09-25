"""
formatter.py
Formata mensagens com copywriting apropriado para Telegram e WhatsApp.
"""

import logging
from typing import Dict

logger = logging.getLogger(__name__)


class MessageFormatter:
    def __init__(self, config: dict):
        msg_cfg = config.get("mensagem", {})
        self.wa_template = msg_cfg.get("whatsapp_template", "")
        self.tg_template = msg_cfg.get("telegram_template", "")
        self.frete_gratis_texto = msg_cfg.get("frete_gratis_texto", "🚚 ✅ Frete Grátis!")
        self.frete_pago_texto   = msg_cfg.get("frete_pago_texto", "")

    def _preparar_dados(self, produto: dict, link_afiliado: str) -> dict:
        preco_fmt = f"{produto.get('preco', 0):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        orig_fmt  = f"{produto.get('preco_original', 0):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        aval_fmt  = f"{produto.get('avaliacao', 0.0):.1f}"
        frete_txt = self.frete_gratis_texto if produto.get("frete_gratis") else self.frete_pago_texto

        # Limpeza simples no nome para evitar quebras em markdown
        nome_limpo = produto.get("nome", "").replace("*", "").replace("_", "")

        return {
            "nome":             nome_limpo,
            "preco":            preco_fmt,
            "preco_original":   orig_fmt,
            "desconto":         produto.get("desconto", 0),
            "frete_gratis":     frete_txt,
            "avaliacao":        aval_fmt,
            "total_avaliacoes": produto.get("total_avaliacoes", 0),
            "link":             link_afiliado,
        }

    def formatar_whatsapp(self, produto: dict, link_afiliado: str) -> str:
        """Formata texto seguindo a sintaxe do WhatsApp (*negrito*, ~tachado~)."""
        dados = self._preparar_dados(produto, link_afiliado)
        return self.wa_template.format(**dados).strip()

    def formatar_telegram(self, produto: dict, link_afiliado: str) -> str:
        """Formata texto seguindo a sintaxe do Telegram."""
        dados = self._preparar_dados(produto, link_afiliado)
        return self.tg_template.format(**dados).strip()
