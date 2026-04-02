import os
import asyncio
import threading
import re
from flask import Flask
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes
from playwright.async_api import async_playwright
from playwright_stealth import stealth_async  # BAGONG IMPORT PARA SA STEALTH

# Environment Variables
BOT_TOKEN = os.environ.get('BOT_TOKEN')
GIT_REPO_URL = os.environ.get('GIT_REPO_URL')

app = Flask(__name__)
@app.route('/')
def alive(): return "Bot is awake!"

def run_web_server():
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)

async def deploy_to_cloud_run(magic_link: str, update: Update, status_msg) -> str:
    project_id_match = re.search(r'(qwiklabs-gcp-[a-zA-Z0-9\-]+)', magic_link)
    if not project_id_match:
        return "❌ Error: Project ID not found in link."
    
    project_id = project_id_match.group(1)

    async def update_log(text):
        try: await status_msg.edit_text(text)
        except: pass 

    await update_log(f"🔄 1/6: Project: {project_id}\nNaghahanda ng STEALTH browser...")

    async with async_playwright() as p:
        # Nagdagdag tayo ng --disable-blink-features=AutomationControlled para hindi ma-detect na bot
        browser = await p.chromium.launch(
            headless=True,
            args=[
                '--no-sandbox',
                '--disable-dev-shm-usage',
                '--disable-blink-features=AutomationControlled',
                '--disable-gpu',
                '--mute-audio'
            ]
        )
        
        # Gumagamit tayo ng pekeng User-Agent para magmukhang totoong Windows PC
        context = await browser.new_context(
            viewport={'width': 1366, 'height': 768},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            locale='en-US'
        )
        page = await context.new_page()

        # I-APPLY ANG STEALTH MODE SA BROWSER TAB
        await stealth_async(page)

        try:
            await update_log("🌐 2/6: Loading Google Cloud SSO (Stealth Mode)...")
            await page.goto(magic_link, timeout=90000)
            
            await asyncio.sleep(10)

            # BYPASS SCREENS
            selectors_to_click = [
                'text="I understand"', 
                'text="Done"', 
                'button:has-text("AGREE AND CONTINUE")',
                '[aria-label="Confirm"]'
            ]
            
            for selector in selectors_to_click:
                try:
                    target = page.locator(selector)
                    if await target.is_visible(timeout=5000):
                        await target.click()
                        await update_log(f"✅ Na-click ang: {selector}")
                except: pass

            await update_log("✅ 3/6: Hinahanap ang Console Action Bar...")
            
            try:
                await page.wait_for_selector('cfc-action-bar', timeout=60000)
            except Exception as e:
                # KUKUHA NG SCREENSHOT KAPAG NAG-TIMEOUT ULIT
                await page.screenshot(path="error_screen.png")
                await update.message.reply_photo(photo=open("error_screen.png", 'rb'), 
                                               caption="❌ Na-block pa rin tayo! Ito ang nakikita ng bot ngayon.")
                return f"❌ Timeout error. Check screenshot."

            await update_log("💻 4/6: Kiniklik ang Cloud Shell...")
            await page.click('[aria-label="Activate Cloud Shell"]')
            
            shell_frame = await page.wait_for_selector('iframe.cloud-shell-iframe', timeout=90000)
            frame = await shell_frame.content_frame()
            await frame.wait_for_selector('.xterm-cursor', timeout=90000)

            await update_log("🚀 5/6: Papatakbuhin na ang deploy command...")
            cmd = f"git clone {GIT_REPO_URL} setup-folder && cd setup-folder && gcloud run deploy vless-server --source . --port=8080 --allow-unauthenticated --region=us-central1 --project={project_id} --quiet\n"
            await frame.type('.xterm-helper-textarea', cmd)

            await update_log("⚙️ 6/6: Binabantayan ang build (Wait 2-4 mins)...")
            for i in range(20):
                await asyncio.sleep(15)
                terminal_text = await frame.locator('.xterm-rows').inner_text()
                match = re.search(r'(https://vless-server-[a-zA-Z0-9\-]+\.a\.run\.app)', terminal_text)
                if match:
                    service_url = match.group(1)
                    host = service_url.replace("https://", "")
                    return f"🎉 **SUCCESS!**\n\nURL: {service_url}\n\n`vless://UUID@{host}:443?encryption=none&security=tls&sni={host}&type=ws&path=/PATH#VlessBot`"
                await update_log(f"⚙️ 6/6: Building... ({i+1}/20)")

            return "⚠️ Timeout sa pagkuha ng URL. Check Google Console."

        except Exception as e:
            await page.screenshot(path="crash_error.png")
            await update.message.reply_photo(photo=open("crash_error.png", 'rb'), caption=f"❌ Crash Error: {str(e)}")
            return f"❌ Error: {str(e)}"
        finally:
            await browser.close()

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if "skills.google/google_sso" in update.message.text:
        status_msg = await update.message.reply_text("⏳ Na-detect ang link! Binubuksan na ang STEALTH browser...")
        result = await deploy_to_cloud_run(update.message.text, update, status_msg)
        await status_msg.edit_text(result, parse_mode=ParseMode.MARKDOWN)

if __name__ == '__main__':
    threading.Thread(target=run_web_server, daemon=True).start()
    app_bot = ApplicationBuilder().token(BOT_TOKEN).build()
    app_bot.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app_bot.run_polling()
