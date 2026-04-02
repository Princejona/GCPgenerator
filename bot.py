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
# 1. SETUP NG FLASK WEB SERVER (PARA SA RENDER)
# ==========================================
app = Flask(__name__)

@app.route('/')
def alive():
    return "Bot is awake and running!"

def run_web_server():
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)

# ==========================================
# 2. PLAYWRIGHT AUTOMATION LOGIC (MAY LIVE LOGS)
# ==========================================
async def deploy_to_cloud_run(magic_link: str, status_msg) -> str:
    if not GIT_REPO_URL:
        return "❌ Error: Hindi nahanap ang GIT_REPO_URL sa environment variables ng Render."

    # Function para madaling i-update ang chat text sa Telegram
    async def update_log(text):
        try:
            await status_msg.edit_text(text)
        except Exception:
            pass # Ignore kung pareho lang ang text at nag-error si Telegram

    await update_log("🔄 1/6: Binubuksan ang Lite headless browser...")

    async with async_playwright() as p:
        # Paggamit ng Lite Browser params para hindi mag-crash ang Render (512MB RAM lang)
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
            await update_log("🌐 2/6: Pumapasok sa Google Cloud gamit ang Magic Link...")
            await page.goto(magic_link, wait_until="networkidle", timeout=60000)
            
            current_url = page.url
            project_id_match = re.search(r'project=([^&]+)', current_url)
            project_id = project_id_match.group(1) if project_id_match else "UNKNOWN_PROJECT"

            if project_id == "UNKNOWN_PROJECT":
                return "❌ Error: Hindi makuha ang Project ID. Baka expired na ang link."

            await update_log(f"✅ 3/6: Nakapasok na! Project ID: {project_id}. Hinahanap ang Cloud Shell...")
            await page.wait_for_selector('cfc-action-bar', timeout=60000)
            await page.click('[aria-label="Activate Cloud Shell"]')
            
            await update_log("💻 4/6: Naglo-load ang Cloud Shell terminal...")
            cloud_shell_frame_element = await page.wait_for_selector('iframe.cloud-shell-iframe', timeout=90000)
            frame = await cloud_shell_frame_element.content_frame()
            await frame.wait_for_selector('.xterm-cursor', timeout=90000)

            await update_log("🚀 5/6: Papatakbuhin na ang Git Clone at Deploy command...")
            deploy_cmd = f"git clone {GIT_REPO_URL} setup-folder && cd setup-folder && gcloud run deploy vless-server --source . --port=8080 --allow-unauthenticated --region=us-central1 --project={project_id} --quiet\n"
            await frame.type('.xterm-helper-textarea', deploy_cmd)

            await update_log("⚙️ 6/6: Nagbi-build ang Dockerfile sa Cloud Run!\n\nAabutin ito ng 2 hanggang 4 na minuto. Wag aalis, binabantayan ko ang terminal output...")

            # Bantayan ang terminal output bawat 15 seconds para makuha ang URL
            service_url = None
            for i in range(20): # Max 5 mins waiting time
                await asyncio.sleep(15)
                # Basahin ang text sa loob ng terminal
                terminal_text = await frame.locator('.xterm-rows').inner_text()
                
                # Hanapin ang https:// link ng vless-server
                match = re.search(r'(https://vless-server-[a-zA-Z0-9\-]+\.a\.run\.app)', terminal_text)
                if match:
                    service_url = match.group(1)
                    break
                else:
                    await update_log(f"⚙️ 6/6: Nagbi-build pa rin... (Checking {i+1}/20)")

            if service_url:
                # Tanggalin ang https:// para sa VLESS host
                host_domain = service_url.replace("https://", "")
                
                # Buuin ang config string (May placeholder para sa UUID)
                vless_config = f"vless://PALITAN_NG_UUID_MO@{host_domain}:443?encryption=none&security=tls&sni={host_domain}&type=ws&path=/PALITAN_NG_PATH_MO#Qwiklabs-VLESS"
                
                final_message = (
                    f"🎉 **SUCCESSFUL DEPLOYMENT!**\n\n"
                    f"🌐 **Cloud Run URL:**\n{service_url}\n\n"
                    f"📝 **VLESS Config Nito:**\n`{vless_config}`\n\n"
                    f"*(Paalala: Kopyahin ang config sa itaas. Palitan ang 'PALITAN_NG_UUID_MO' at 'PALITAN_NG_PATH_MO' kung ano ang nasa loob ng config.json mo bago i-paste sa v2rayNG.)*"
                )
                return final_message
            else:
                return "⚠️ Tapos na ang oras ng paghihintay pero hindi ko mahanap ang URL. Baka natagalan ang build. I-check ang Google Cloud Console manually."

        except Exception as e:
            return f"❌ May error na nangyari sa automation: {str(e)}"
        finally:
            await browser.close()

# ==========================================
# 3. TELEGRAM BOT HANDLER
# ==========================================
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text
    
    if "skills.google/google_sso" in user_text:
        # Unang message na i-e-edit natin maya-maya
        status_msg = await update.message.reply_text("⏳ Na-detect ang magic link! Sinisimulan na ang proseso...")
        
        # Patakbuhin ang browser at ipasa ang status_msg object para ma-update
        final_result = await deploy_to_cloud_run(user_text, status_msg)
        
        # Kapag tapos na ang lahat, palitan ang chat ng pinal na sagot (with Markdown format)
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
