"""
senders/whatsapp.py
Envia mensagens e fotos para grupos do WhatsApp via Evolution API (v2).
"""

import os
import logging
import requests

logger = logging.getLogger(__name__)


class WhatsAppSender:
    def __init__(self, config: dict):
        wa_cfg = config.get("whatsapp", {})
        self.base_url = (os.getenv("EVOLUTION_API_URL") or wa_cfg.get("evolution_api_url", "http://localhost:8080")).rstrip("/")
        self.api_key = os.getenv("EVOLUTION_API_KEY") or wa_cfg.get("evolution_api_key", "")
        self.instancia = os.getenv("EVOLUTION_INSTANCE") or wa_cfg.get("instancia", "")

        self.session = requests.Session()
        self.session.headers.update({
            "apikey":       self.api_key,
            "Content-Type": "application/json",
        })

    def enviar_para_grupo(self, grupo_id: str, produto: dict, mensagem: str) -> bool:
        """Envia produto (imagem + legenda) para um grupo específico do WhatsApp via Evolution API."""
        if not self.api_key or not self.instancia or not grupo_id:
            logger.warning(f"WhatsApp pulado: credenciais ou grupo_id ausente ({grupo_id})")
            return False

        # Ignora grupos de exemplo para não gerar erro desnecessário
        if "120363000000000" in grupo_id:
            logger.warning(f"WhatsApp pulado: grupo de exemplo ainda não configurado ({grupo_id})")
            return False

        try:
            imagem = produto.get("imagem", "")
            sucesso = False
            if imagem:
                sucesso = self._enviar_imagem(grupo_id, imagem, mensagem)
            
            # Se não tiver imagem ou se o envio da mídia falhar, envia como texto (fallback)
            if not sucesso:
                sucesso = self._enviar_texto(grupo_id, mensagem)

            if sucesso:
                logger.info(f"✅ [WhatsApp] Enviado para {grupo_id} | {produto.get('nome', '')[:40]}")
            return sucesso
        except Exception as e:
            logger.error(f"❌ [WhatsApp] Erro ao enviar para {grupo_id}: {e}")
            return False

    def _enviar_texto(self, numero: str, texto: str) -> bool:
        url = f"{self.base_url}/message/sendText/{self.instancia}"
        payload = {
            "number":  numero,
            "text":    texto,
            "options": {"delay": 1200},
        }
        return self._post(url, payload)

    def _enviar_imagem(self, numero: str, imagem_url: str, caption: str) -> bool:
        url = f"{self.base_url}/message/sendMedia/{self.instancia}"
        # Payload completo exigido pela Evolution API v2
        payload = {
            "number":    numero,
            "mediatype": "image",
            "mimetype":  "image/jpeg",
            "fileName":  "oferta.jpg",
            "media":     imagem_url,
            "caption":   caption,
            "options":   {"delay": 1200},
        }
        return self._post(url, payload)

    def _post(self, url: str, payload: dict) -> bool:
        try:
            resp = self.session.post(url, json=payload, timeout=25)
            if resp.status_code in [200, 201]:
                return True
            logger.warning(f"Evolution API retornou status {resp.status_code}: {resp.text[:200]}")
            return False
        except requests.RequestException as e:
            logger.error(f"Erro na requisição Evolution API: {e}")
            return False

    def instancia_conectada(self) -> bool:
        """Verifica se a instância da Evolution API está autenticada ('open')."""
        if not self.api_key or not self.instancia:
            return False

        url = f"{self.base_url}/instance/fetchInstances"
        try:
            resp = self.session.get(url, timeout=10)
            if resp.status_code != 200:
                return False
            instancias = resp.json()
            for inst in instancias:
                nome = inst.get("name") or inst.get("instance", {}).get("instanceName")
                if nome == self.instancia:
                    estado = inst.get("connectionStatus") or inst.get("instance", {}).get("state", "")
                    return estado.lower() in ["open", "connected"]
            return False
        except Exception as e:
            logger.error(f"Erro ao verificar estado da instância WhatsApp: {e}")
            return False