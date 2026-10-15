"""
senders/telegram.py
Envia mensagens e fotos para canais/grupos do Telegram com fallback automático de texto.
"""

import os
import asyncio
import logging
import httpx

logger = logging.getLogger(__name__)

TELEGRAM_API = "https://api.telegram.org/bot{token}/{method}"


class TelegramSender:
    def __init__(self, config: dict):
        self.token = os.getenv("TELEGRAM_TOKEN") or config.get("telegram", {}).get("token", "")
        if not self.token or self.token.startswith("SEU_"):
            logger.warning("Token do Telegram não configurado no .env.")

    async def enviar_para_chat(self, chat_id: str, produto: dict, mensagem: str) -> bool:
        """Envia produto (imagem + legenda) com fallback automático se a foto falhar."""
        if not self.token or not chat_id:
            logger.warning(f"Telegram pulado: token ou chat_id ausente ({chat_id})")
            return False

        imagem = produto.get("imagem", "")
        sucesso = False

        try:
            # 1. Tenta enviar com foto
            if imagem:
                sucesso = await self._enviar_com_foto(chat_id, mensagem, imagem)
            
            # 2. Se não tiver foto ou se o envio com foto falhar, envia como mensagem de texto
            if not sucesso:
                logger.warning("Envio com foto falhou ou indisponível no Telegram. Tentando envio em texto...")
                sucesso = await self._enviar_texto(chat_id, mensagem)

            if sucesso:
                logger.info(f"✅ [Telegram] Enviado com sucesso para {chat_id} | {produto.get('nome', '')[:35]}")
            return sucesso
        except Exception as e:
            logger.error(f"❌ [Telegram] Erro geral ao enviar para {chat_id}: {e}")
            return False

    async def _enviar_com_foto(self, chat_id: str, caption: str, foto_url: str) -> bool:
        url = TELEGRAM_API.format(token=self.token, method="sendPhoto")
        if len(caption) > 1024:
            caption = caption[:1020] + "..."

        payload = {
            "chat_id":    chat_id,
            "photo":      foto_url,
            "caption":    caption,
            "parse_mode": "Markdown",
        }
        return await self._post(url, payload)

    async def _enviar_texto(self, chat_id: str, texto: str) -> bool:
        url = TELEGRAM_API.format(token=self.token, method="sendMessage")
        payload = {
            "chat_id":                  chat_id,
            "text":                     texto,
            "parse_mode":               "Markdown",
            "disable_web_page_preview": False,
        }
        ok = await self._post(url, payload)
        # Se falhar com Markdown por causa de caracteres especiais, tenta sem parse_mode
        if not ok:
            payload.pop("parse_mode", None)
            ok = await self._post(url, payload)
        return ok

    async def _post(self, url: str, payload: dict) -> bool:
        try:
            async with httpx.AsyncClient(timeout=25) as client:
                resp = await client.post(url, json=payload)
                data = resp.json()
                if not data.get("ok"):
                    logger.warning(f"Telegram API retornou erro: {data.get('description')}")
                    return False
                return True
        except Exception as e:
            logger.error(f"Erro na requisição HTTP do Telegram: {e}")
            return False

    def enviar_para_chat_sync(self, chat_id: str, produto: dict, mensagem: str) -> bool:
        return asyncio.run(self.enviar_para_chat(chat_id, produto, mensagem))