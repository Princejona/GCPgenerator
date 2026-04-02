import os
import asyncio
import threading
import re
from flask import Flask
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes
from playwright.async_api import async_playwright

# Environment Variables
BOT_TOKEN = os.environ.get('BOT_TOKEN')
GIT_REPO_URL = os.environ.get('GIT_REPO_URL')

# ==========================================
# 1. SETUP NG FLASK WEB SERVER
# ==========================================
app = Flask(__name__)

@app.route('/')
def alive():
    return "Bot is awake and running!"

def run_web_server():
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)

# ==========================================
# 2. PLAYWRIGHT AUTOMATION LOGIC
# ==========================================
async def deploy_to_cloud_run(magic_link: str, status_msg) -> str:
    if not GIT_REPO_URL:
        return "❌ Error: Hindi nahanap ang GIT_REPO_URL sa environment variables."

    project_id_match = re.search(r'(qwiklabs-gcp-[a-zA-Z0-9\-]+)', magic_link)
    if not project_id_match:
        return "❌ Error: Wala akong makitang Project ID sa link na sinend mo."
    
    project_id = project_id_match.group(1)

    async def update_log(text):
        try:
            await status_msg.edit_text(text)
        except Exception:
            pass 

    await update_log(f"🔄 1/6: Project ID ({project_id}) nakuha! Binubuksan ang browser...")

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=[
                '--no-sandbox',
                '--disable-dev-shm-usage',
                '--disable-gpu',
                '--single-process',
                '--disable-software-rasterizer',
                '--mute-audio'
            ]
        )
        context = await browser.new_context()
        page = await context.new_page()

        try:
            await update_log("🌐 2/6: Pumapasok sa Google Cloud SSO...")
            
            # Tinanggal ang networkidle para hindi ma-stuck sa loading
            await page.goto(magic_link, timeout=60000)
            
            # Subukang i-bypass ang "Welcome to your new account" screen
            try:
                await update_log("🔍 Checking kung may 'I understand' Welcome screen...")
                understand_btn = page.locator('text="I understand"')
                if await understand_btn.is_visible(timeout=10000):
                    await understand_btn.click()
                    await update_log("✅ Pinindot ang 'I understand' button...")
            except Exception:
                pass # Kung walang lumabas, tuloy lang
            
            await update_log("✅ 3/6: Hinahanap ang Google Cloud Console...")
            
            # Nagdagdag ng extra time para mag-load ang GCP Console
            await page.wait_for_selector('cfc-action-bar', timeout=90000)
            
            # Subukang i-bypass ang GCP Terms of Service popup kung meron man
            try:
                agree_checkbox = page.locator('mat-checkbox[formcontrolname="tosAgree"]')
                if await agree_checkbox.is_visible(timeout=5000):
                    await agree_checkbox.click()
                    await page.click('button:has-text("AGREE AND CONTINUE")')
            except Exception:
                pass

            # Pindutin ang Activate Cloud Shell
            await update_log("💻 4/6: Kiniklik ang Cloud Shell icon...")
            await page.click('[aria-label="Activate Cloud Shell"]')
            
            cloud_shell_frame_element = await page.wait_for_selector('iframe.cloud-shell-iframe', timeout=90000)
            frame = await cloud_shell_frame_element.content_frame()
            
            await update_log("⏳ Hinihintay maging ready ang terminal...")
            await frame.wait_for_selector('.xterm-cursor', timeout=90000)

            await update_log("🚀 5/6: Papatakbuhin na ang command sa terminal...")
            deploy_cmd = f"git clone {GIT_REPO_URL} setup-folder && cd setup-folder && gcloud run deploy vless-server --source . --port=8080 --allow-unauthenticated --region=us-central1 --project={project_id} --quiet\n"
            await frame.type('.xterm-helper-textarea', deploy_cmd)

            await update_log("⚙️ 6/6: Nagbi-build ang Dockerfile sa Cloud Run!\n\nAabutin ito ng 2 hanggang 4 na minuto. Wag aalis, binabantayan ko ang terminal output...")

            service_url = None
            for i in range(20): 
                await asyncio.sleep(15)
                terminal_text = await frame.locator('.xterm-rows').inner_text()
                
                match = re.search(r'(https://vless-server-[a-zA-Z0-9\-]+\.a\.run\.app)', terminal_text)
                if match:
                    service_url = match.group(1)
                    break
                else:
                    await update_log(f"⚙️ 6/6: Nagbi-build pa rin... (Checking {i+1}/20)")

            if service_url:
                host_domain = service_url.replace("https://", "")
                vless_config = f"vless://PALITAN_NG_UUID_MO@{host_domain}:443?encryption=none&security=tls&sni={host_domain}&type=ws&path=/PALITAN_NG_PATH_MO#Qwiklabs-VLESS"
                
                final_message = (
                    f"🎉 **SUCCESSFUL DEPLOYMENT!**\n\n"
                    f"🌐 **Cloud Run URL:**\n{service_url}\n\n"
                    f"📝 **VLESS Config:**\n`{vless_config}`\n\n"
                    f"*(Kopyahin at palitan ang UUID at PATH base sa config.json mo)*"
                )
                return final_message
            else:
                return "⚠️ Tapos na ang oras ng paghihintay pero hindi ko mahanap ang URL. I-check sa Google Cloud Console manually."

        except Exception as e:
            return f"❌ May error na nangyari sa automation:\n\n{str(e)}"
        finally:
            await browser.close()

# ==========================================
# 3. TELEGRAM BOT HANDLER
# ==========================================
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text
    
    if "skills.google/google_sso" in user_text:
        status_msg = await update.message.reply_text("⏳ Na-detect ang magic link! Sinisimulan na ang proseso...")
        final_result = await deploy_to_cloud_run(user_text, status_msg)
        await status_msg.edit_text(final_result, parse_mode=ParseMode.MARKDOWN)

if __name__ == '__main__':
    threading.Thread(target=run_web_server, daemon=True).start()
    
    if not BOT_TOKEN:
        print("CRITICAL ERROR: Walang BOT_TOKEN na nakalagay.")
    else:
        app = ApplicationBuilder().token(BOT_TOKEN).build()
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
        
        print("Telegram Bot is polling and ready...")
        app.run_polling()
