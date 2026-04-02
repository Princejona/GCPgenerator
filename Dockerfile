# Gagamit tayo ng napakagaang na Python version
FROM python:3.10-slim

# I-set ang working directory
WORKDIR /app

# Kopyahin ang requirements muna
COPY requirements.txt .

# I-install ang Python packages
RUN pip install --no-cache-dir -r requirements.txt

# ITO ANG MAGIC: Hahayaan natin si Playwright na i-download ang saktong browser 
# at ang lahat ng Linux system dependencies nito (--with-deps)
RUN playwright install chromium --with-deps

# Kopyahin ang buong code ng bot (bot.py at config.json)
COPY . .

# Patakbuhin ang bot
CMD ["python", "bot.py"]
