FROM python:3.11-slim

WORKDIR /app

# Copia i requirements e installa le dipendenze
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copia tutto il codice del back-end
COPY . .

# Porta esposta dal back-end
EXPOSE 8000

# Avvio del server FastAPI con uvicorn
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
