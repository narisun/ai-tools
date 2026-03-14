FROM python:3.11-slim

WORKDIR /app

# Install dependencies first for Docker layer caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the server source code
COPY src/ /app/src/

# Expose port 8080 for SSE communication
EXPOSE 8080

# Run the server
CMD ["python", "src/server.py"]