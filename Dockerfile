# Gagamit tayo ng napakagaang na Python version
FROM python:3.10-slim

# I-set ang working directory
WORKDIR /app

# Kopyahin at i-install ang requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Kopyahin ang buong code ng bot
COPY . .

# Patakbuhin ang bot (Wala nang browser commands!)
CMD ["python", "bot.py"]
