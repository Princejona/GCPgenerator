import os
import threading
from flask import Flask
# ... (Iba mo pang Telegram at Playwright imports dito) ...

# Setup para sa Dummy Web Server ng Render
app = Flask(__name__)
@app.route('/')
def alive():
    return "Bot is awake and running!"

def run_web_server():
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)

# ... (Yung async def functions mo para sa bot at playwright dito) ...

if __name__ == '__main__':
    # 1. Patakbuhin ang Flask server sa background para maging masaya si Render
    threading.Thread(target=run_web_server).start()

    # 2. Patakbuhin ang Telegram Bot mo
    bot_app = ApplicationBuilder().token(BOT_TOKEN).build()
    bot_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    print("Bot is running...")
    bot_app.run_polling()
