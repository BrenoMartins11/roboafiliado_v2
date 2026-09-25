"""
testar_fluxo_perfil.py
Fluxo com seletores 100% exatos fornecidos por você:
1. Seta do perfil: .nav-header-username-chevron
2. Opção: Afiliados e criadores
3. Ícone: .circle-button__icon--link_builder
4. Entrada de URL: #url-0
5. Botão de clique exato: button.links-form__button
6. Campo de saída do link: #textfield-copyLink-1
"""

from pathlib import Path
from playwright.sync_api import sync_playwright

SESSION_DIR = Path("config/ml_session")
URL_PRODUTO = "https://produto.mercadolivre.com.br/MLB-3711361787-manta-beb-pipoquinha-plush-luxo-menino-menina-1-metro-_JM"

print("=" * 60)
print("🚀 TESTANDO COM O BOTÃO EXATO: button.links-form__button")
print("=" * 60)

with sync_playwright() as p:
    context = p.chromium.launch_persistent_context(
        user_data_dir=str(SESSION_DIR),
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

    print("1. Abrindo a home do Mercado Livre...")
    page.goto("https://www.mercadolivre.com.br", wait_until="domcontentloaded")
    page.wait_for_timeout(2000)

    print("2. Clicando na seta do perfil (.nav-header-username-chevron)...")
    chevron = page.locator(".nav-header-username-chevron").first
    chevron.wait_for(state="visible", timeout=10000)
    chevron.click()
    page.wait_for_timeout(1000)

    print("3. Clicando em 'Afiliados e criadores'...")
    opcao_afiliados = page.locator("a:has-text('Afiliados e criadores')").first
    opcao_afiliados.wait_for(state="visible", timeout=10000)
    opcao_afiliados.click()
    page.wait_for_timeout(3000)

    print("4. Clicando no Gerador de Links (.circle-button__icon--link_builder)...")
    botao_builder = page.locator(".circle-button__icon--link_builder, [class*='link_builder']").first
    botao_builder.wait_for(state="visible", timeout=12000)
    botao_builder.click()
    page.wait_for_timeout(2500)

    print("5. Inserindo URL no campo #url-0...")
    textarea_url = page.locator("#url-0").first
    textarea_url.wait_for(state="visible", timeout=12000)
    textarea_url.click()
    textarea_url.fill(URL_PRODUTO)

    # Dispara os eventos de input para o botão 'Gerar' ficar ativo
    textarea_url.dispatch_event("input")
    textarea_url.dispatch_event("change")
    page.wait_for_timeout(1000)

    print("6. Clicando no botão 'Gerar' (button.links-form__button)...")
    botao_gerar = page.locator("button.links-form__button, button:has-text('Gerar')").first
    botao_gerar.wait_for(state="visible", timeout=10000)
    botao_gerar.click()

    print("7. Aguardando o link ser gerado no campo #textfield-copyLink-1...")
    # Aguarda o campo onde o link 'https://meli.la/...' aparece
    campo_saida = page.locator("#textfield-copyLink-1, [id*='textfield-copyLink']").first
    campo_saida.wait_for(state="visible", timeout=15000)

    # 8. Extrai o link encurtado oficial gerado
    link_afiliado = campo_saida.input_value().strip()

    print("\n" + "=" * 60)
    print("🎉 SUCESSO TOTAL! LINK OFICIAL DE AFILIADO GERADO:")
    print(f"👉 {link_afiliado}")
    print("=" * 60)

    input("\nPressione ENTER no terminal para fechar...")
    context.close()