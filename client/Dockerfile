FROM python:3.12-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    && rm -rf /var/lib/apt/lists/*

# Copy client code
COPY client.py .

# Expose port
EXPOSE 8080

# Default environment variables
ENV OFFSHORE_HOST=offshore-proxy
ENV OFFSHORE_PORT=9999

# Run client
CMD ["python", "client.py", "--offshore-host=${OFFSHORE_HOST}", "--offshore-port=${OFFSHORE_PORT}"]
