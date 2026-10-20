"""
formatter.py
Formata mensagens com copywriting apropriado para Telegram e WhatsApp.
"""

import logging
from typing import Dict

logger = logging.getLogger(__name__)


class MessageFormatter:
    def __init__(self, config_mensagem: dict = None):
        # 1. Trata se recebeu o config global ou apenas a seção 'mensagem'
        if isinstance(config_mensagem, dict):
            if "mensagem" in config_mensagem:
                cfg = config_mensagem["mensagem"]
            else:
                cfg = config_mensagem
        else:
            cfg = {}

        # 2. Carrega templates do YAML ou usa templates padrão de segurança
        template_tg_padrao = (
            "🔥 *{nome}*\n\n"
            "💰 De: R$ {preco_original}\n"
            "💥 *Por: R$ {preco}* ({desconto}% OFF){cupom}\n"
            "{frete_gratis}\n"
            "⭐ {avaliacao} ({total_avaliacoes} avaliações)\n\n"
            "🛒 [CLIQUE AQUI PARA COMPRAR]({link})"
        )

        template_wa_padrao = (
            "🔥 *{nome}*\n\n"
            "💰 De: ~R$ {preco_original}~\n"
            "💥 *Por: R$ {preco}* ({desconto}% OFF){cupom}\n"
            "{frete_gratis}\n"
            "⭐ {avaliacao} ({total_avaliacoes} avaliações)\n\n"
            "🛒 *Compre com desconto aqui:*\n"
            "{link}"
        )

        self.telegram_template = cfg.get("telegram_template") or template_tg_padrao
        self.whatsapp_template = cfg.get("whatsapp_template") or template_wa_padrao
        self.frete_gratis_texto = cfg.get("frete_gratis_texto", "🚚 ✅ Frete Grátis!")
        self.frete_pago_texto = cfg.get("frete_pago_texto", "")

    def _resolver_cupom(self, produto: dict, nicho: dict, formato: str = "telegram") -> str:
        """Resolve se há cupom nativo ou cupom de nicho configurado."""
        cupom_nativo = produto.get("cupom_nativo")
        if cupom_nativo:
            if formato == "telegram":
                return f"\n🎟️ *{cupom_nativo}* _(aplique no anúncio)_"
            else:
                return f"\n🎟️ *{cupom_nativo}* (ative na página)"

        cupons_nicho = nicho.get("cupons", []) if isinstance(nicho, dict) else []
        preco_atual = float(produto.get("preco", 0.0))

        for cupom in cupons_nicho:
            preco_min = float(cupom.get("preco_minimo", 0.0))
            if preco_atual >= preco_min:
                codigo = cupom.get("codigo")
                tipo = cupom.get("tipo", "percent")
                valor = float(cupom.get("valor", 0))

                if tipo == "percent":
                    desconto_reais = preco_atual * (valor / 100)
                    preco_final = preco_atual - desconto_reais
                    desc_str = f"{int(valor)}% OFF"
                else:
                    preco_final = preco_atual - valor
                    desc_str = f"R$ {valor:.2f} OFF"

                if formato == "telegram":
                    return f"\n🎟️ Use o cupom: `{codigo}` _({desc_str})_\n🏷️ *Com cupom sai por: R$ {preco_final:.2f}*"
                else:
                    return f"\n🎟️ *Use o cupom:* {codigo} ({desc_str})\n🏷️ *Com cupom sai por: R$ {preco_final:.2f}*"

        return ""

    def formatar_telegram(self, produto: dict, nicho: dict, link_afiliado: str) -> str:
        """Formata a mensagem para o Telegram."""
        cupom_texto = self._resolver_cupom(produto, nicho, formato="telegram")
        frete_texto = self.frete_gratis_texto if produto.get("frete_gratis") else self.frete_pago_texto

        dados = {
            "nome": produto.get("nome", ""),
            "preco": f"{float(produto.get('preco', 0.0)):.2f}",
            "preco_original": f"{float(produto.get('preco_original', 0.0)):.2f}",
            "desconto": produto.get("desconto", 0),
            "frete_gratis": frete_texto,
            "avaliacao": produto.get("avaliacao", 4.6),
            "total_avaliacoes": produto.get("total_avaliacoes", 50),
            "link": link_afiliado,
            "cupom": cupom_texto
        }

        texto = self.telegram_template
        for chave, valor in dados.items():
            texto = texto.replace(f"{{{chave}}}", str(valor))

        return texto.strip()

    def formatar_whatsapp(self, produto: dict, nicho: dict, link_afiliado: str) -> str:
        """Formata a mensagem para o WhatsApp."""
        cupom_texto = self._resolver_cupom(produto, nicho, formato="whatsapp")
        frete_texto = self.frete_gratis_texto if produto.get("frete_gratis") else self.frete_pago_texto

        dados = {
            "nome": produto.get("nome", ""),
            "preco": f"{float(produto.get('preco', 0.0)):.2f}",
            "preco_original": f"{float(produto.get('preco_original', 0.0)):.2f}",
            "desconto": produto.get("desconto", 0),
            "frete_gratis": frete_texto,
            "avaliacao": produto.get("avaliacao", 4.6),
            "total_avaliacoes": produto.get("total_avaliacoes", 50),
            "link": link_afiliado,
            "cupom": cupom_texto
        }

        texto = self.whatsapp_template
        for chave, valor in dados.items():
            texto = texto.replace(f"{{{chave}}}", str(valor))

        return texto.strip()