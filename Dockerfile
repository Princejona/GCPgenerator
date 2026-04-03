FROM python:3.10-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# ITO ANG FIX: Sapilitan nating sasabihin kay Render na buksan ang Port 10000
EXPOSE 10000
ENV PORT=10000

# Ang "-u" (unbuffered) ay para lumabas agad ang Telegram logs natin nang walang delay
CMD ["python", "-u", "bot.py"]
