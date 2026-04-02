import os
import asyncio
import threading
import re
from flask import Flask
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes
from playwright.async_api import async_playwright

# Kukunin ang mga sikreto mula sa Environment Variables ng Render
BOT_TOKEN = os.environ.get('BOT_TOKEN')
GIT_REPO_URL = os.environ.get('GIT_REPO_URL')

# ==========================================
# 1. SETUP NG FLASK WEB SERVER (PARA SA RENDER)
# ==========================================
app = Flask(__name__)

@app.route('/')
def alive():
    return "Bot is awake and running!"

def run_web_server():
    # Gagamitin ng Render ang sarili nitong PORT, default ay 10000 kung wala
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)

# ==========================================
# 2. PLAYWRIGHT AUTOMATION SCRIPT
# ==========================================
async def deploy_to_cloud_run(magic_link: str) -> str:
    """Ang invisible browser na mag-o-open ng link at mag-ta-type sa Cloud Shell."""
    if not GIT_REPO_URL:
        return "Error: Hindi nahanap ang GIT_REPO_URL sa environment variables."

    async with async_playwright() as p:
        # headless=True dahil tatakbo ito sa background ng Render
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()

        try:
            # 1. Buksan ang Qwiklabs/Skills Boost magic link
            await page.goto(magic_link, wait_until="networkidle")
            
            # 2. Kunin ang Project ID mula sa URL
            current_url = page.url
            project_id_match = re.search(r'project=([^&]+)', current_url)
            project_id = project_id_match.group(1) if project_id_match else "UNKNOWN_PROJECT"

            if project_id == "UNKNOWN_PROJECT":
                return "Error: Hindi makuha ang Project ID mula sa link."

            # 3. Hintayin mag-load ang Google Cloud Console (Top bar)
            await page.wait_for_selector('cfc-action-bar', timeout=60000)

            # 4. I-click ang Cloud Shell icon (Ang aria-label ay madalas 'Activate Cloud Shell')
            await page.click('[aria-label="Activate Cloud Shell"]')
            
            # 5. Hintayin ang Cloud Shell iframe na lumabas
            cloud_shell_frame_element = await page.wait_for_selector('iframe.cloud-shell-iframe', timeout=60000)
            frame = await cloud_shell_frame_element.content_frame()
            
            # 6. Hintayin ang cursor terminal na maging ready
            await frame.wait_for_selector('.xterm-cursor', timeout=60000)

            # 7. I-type ang command: Git clone muna, tapos deploy gamit ang source code
            # Note: Gagamit tayo ng random folder name (setup-folder) para sure na walang conflict
            deploy_cmd = f"git clone {GIT_REPO_URL} setup-folder && cd setup-folder && gcloud run deploy vless-server --source . --port=8080 --allow-unauthenticated --region=us-central1 --project={project_id} --quiet\n"
            
            # I-paste at i-enter ang command sa terminal
            await frame.type('.xterm-helper-textarea', deploy_cmd)

            # 8. Magbigay ng sapat na oras (60 seconds) para mag-trigger ang Cloud Build
            # Bago natin patayin ang browser para hindi maputol ang process
            await page.wait_for_timeout(60000) 

            return f"✅ Na-send na ang deploy command para sa Project: {project_id}.\n\nDahil magbi-build pa siya mula sa Dockerfile mo, maghintay ng mga 2-3 minuto. Pumunta sa Cloud Run Console para kunin ang link ng vless-server kung successful."

        except Exception as e:
            return f"❌ May error na nangyari sa automation: {str(e)}"
        finally:
            await browser.close()

# ==========================================
# 3. TELEGRAM BOT LOGIC
# ==========================================
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text
    
    # Kapag na-detect na SSO link ang sinend mo
    if "skills.google/google_sso" in user_text:
        await update.message.reply_text("⏳ Na-detect ang magic link! Binubuksan na ang headless browser para mag-deploy sa Cloud Run. Maghintay nang bahagya...")
        
        # Patakbuhin ang browser at hintayin ang resulta
        result = await deploy_to_cloud_run(user_text)
        
        # I-send ang result pabalik sa'yo
        await update.message.reply_text(result)

if __name__ == '__main__':
    # 1. Patakbuhin ang Flask web server sa background thread para hindi patayin ni Render
    threading.Thread(target=run_web_server, daemon=True).start()
    
    # 2. Patakbuhin ang Telegram Bot
    if not BOT_TOKEN:
        print("CRITICAL ERROR: Walang BOT_TOKEN na nakalagay. Paki-check ang Render Environment Variables.")
    else:
        app = ApplicationBuilder().token(BOT_TOKEN).build()
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
        
        print("Telegram Bot is polling and ready...")
        app.run_polling()
