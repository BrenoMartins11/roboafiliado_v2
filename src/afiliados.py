"""
afiliados.py
Gera links oficiais de afiliado (/sec/ ou meli.la) automatizando o fluxo
validado na Central de Afiliados do Mercado Livre via Playwright.
"""

import os
import logging
from pathlib import Path
from playwright.sync_api import sync_playwright

logger = logging.getLogger(__name__)

SESSION_DIR = Path("config/ml_session")


class AffiliateManager:
    def __init__(self, config: dict):
        self.session_dir = SESSION_DIR
        if not self.session_dir.exists():
            logger.warning("⚠️ Pasta de sessão 'config/ml_session' não encontrada.")

    def gerar_link_afiliado(self, url_original: str) -> str:
        """Executa o fluxo completo do Mercado Livre para gerar e copiar o link de afiliado."""
        if not self.session_dir.exists():
            return url_original

        link_limpo = url_original.split("#")[0].split("?")[0]

        try:
            with sync_playwright() as p:
                context = p.chromium.launch_persistent_context(
                    user_data_dir=str(self.session_dir),
                    channel="chrome",
                    headless=False,  # Janela real que garante a renderização do menu
                    args=[
                        "--disable-blink-features=AutomationControlled",
                        "--start-maximized"
                    ],
                    ignore_default_args=["--enable-automation"],
                    locale="pt-BR"
                )

                page = context.pages[0] if context.pages else context.new_page()

                # 1. Página inicial
                page.goto("https://www.mercadolivre.com.br", wait_until="domcontentloaded", timeout=30000)
                page.wait_for_timeout(2000)

                # 2. Seta do perfil
                chevron = page.locator(".nav-header-username-chevron").first
                chevron.wait_for(state="visible", timeout=12000)
                chevron.click()
                page.wait_for_timeout(1000)

                # 3. Opção Afiliados e criadores
                opcao_afiliados = page.locator("a:has-text('Afiliados e criadores')").first
                opcao_afiliados.wait_for(state="visible", timeout=10000)
                opcao_afiliados.click()
                page.wait_for_timeout(3000)

                # 4. Ícone do Gerador de Links
                botao_builder = page.locator(".circle-button__icon--link_builder, [class*='link_builder']").first
                botao_builder.wait_for(state="visible", timeout=12000)
                botao_builder.click()
                page.wait_for_timeout(2500)

                # 5. Preenche a URL no #url-0
                textarea_url = page.locator("#url-0").first
                textarea_url.wait_for(state="visible", timeout=12000)
                textarea_url.click()
                textarea_url.fill(link_limpo)
                textarea_url.dispatch_event("input")
                textarea_url.dispatch_event("change")
                page.wait_for_timeout(1000)

                # 6. Clica no botão Gerar
                botao_gerar = page.locator("button.links-form__button, button:has-text('Gerar')").first
                botao_gerar.wait_for(state="visible", timeout=10000)
                botao_gerar.click()

                # 7. Captura o link gerado do campo de saída
                campo_saida = page.locator("#textfield-copyLink-1, [id*='textfield-copyLink']").first
                campo_saida.wait_for(state="visible", timeout=15000)
                link_afiliado = campo_saida.input_value().strip()

                context.close()

                if link_afiliado:
                    logger.info(f"✅ Link de afiliado gerado: {link_afiliado}")
                    return link_afiliado

                logger.warning(f"Campo de saída vazio para: {link_limpo}")
                return url_original

        except Exception as e:
            logger.warning(f"Falha ao gerar link via Playwright para {link_limpo[:40]}...: {e}")
            return url_original