FROM python:3.11-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1


# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Expose port 8080
EXPOSE 9090

# Run the application
CMD ["python", "app.py"]
