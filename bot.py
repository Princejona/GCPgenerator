import os
import threading
from flask import Flask
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes

# Environment Variables
BOT_TOKEN = os.environ.get('BOT_TOKEN')
GIT_REPO_URL = os.environ.get('GIT_REPO_URL')

app = Flask(__name__)
@app.route('/')
def alive(): return "Bot is awake and super light!"

def run_web_server():
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    
    if not GIT_REPO_URL or not BOT_TOKEN:
        await update.message.reply_text("❌ Error: Kulang ng BOT_TOKEN o GIT_REPO_URL sa Render environment variables.")
        return

    # TINANGGAL NA NATIN ANG EXCLAMATION POINT SA "SUCCESS DEPLOYMENT"
    bash_command = (
        f"git clone {GIT_REPO_URL} setup-vless && cd setup-vless && "
        f"gcloud run deploy vless-server --source . --port=8080 --allow-unauthenticated --region=us-central1 --quiet && "
        f"URL=$(gcloud run services describe vless-server --region=us-central1 --format='value(status.url)') && "
        f"HOST=$(echo $URL | sed 's/https:\\/\\///') && "
        f"curl -s -X POST https://api.telegram.org/bot{BOT_TOKEN}/sendMessage -d chat_id={chat_id} "
        f"-d text=\"🎉 SUCCESS DEPLOYMENT %0A%0A🌐 URL:%0A$URL%0A%0A📝 VLESS CONFIG:%0Avless://PALITAN_NG_UUID_MO@$HOST:443?encryption=none&security=tls&sni=$HOST&type=ws&path=/PALITAN_NG_PATH_MO#Qwiklabs-VLESS\""
    )

    reply_msg = (
        "✅ **Handa na ang 1-Click Script mo!**\n\n"
        "**MGA HAKBANG:**\n"
        "1. Mag-Start Lab at ikaw mismo ang pumasok sa Google Cloud Console gamit ang incognito.\n"
        "2. Pindutin ang **Activate Cloud Shell** icon (bandang itaas kanan).\n"
        "3. **Kopyahin at i-paste** ang code sa ibaba doon sa terminal:\n\n"
        f"```bash\n{bash_command}\n```\n\n"
        "*(I-paste at i-enter. Pagkatapos niyan, pwede mo nang i-minimize ang browser. Kusang magme-message ang Cloud Shell dito sa Telegram mo dala ang VLESS config kapag natapos na siya!)*"
    )

    await update.message.reply_text(reply_msg, parse_mode=ParseMode.MARKDOWN)

if __name__ == '__main__':
    threading.Thread(target=run_web_server, daemon=True).start()
    if BOT_TOKEN:
        app_bot = ApplicationBuilder().token(BOT_TOKEN).build()
        app_bot.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
        print("Bot is polling and ready...")
        app_bot.run_polling(drop_pending_updates=True)
