# Python 3.11 versiyasidan foydalanamiz
FROM python:3.11-slim

# Loyiha papkasini yaratamiz
WORKDIR /app

# Kutubxonalar ro'yxatini nusxalaymiz va o'rnatamiz
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Barcha kodlarni nusxalaymiz
COPY . .

# Botni ishga tushirish komandasi
CMD ["python", "main.py"]