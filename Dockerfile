# Gamitin ang official Playwright image na may pre-installed browsers at OS libraries
FROM mcr.microsoft.com/playwright/python:v1.42.0-jammy

# I-set ang working directory
WORKDIR /app

# Kopyahin at i-install ang requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Kopyahin ang buong code ng bot mo
COPY . .

# Command para patakbuhin ang bot
CMD ["python", "bot.py"]
