FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Create the news articles watch folder
RUN mkdir -p /tmp/news_articles

EXPOSE 5000

CMD ["python", "-m", "src.main"]
