FROM python:3.12-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    && rm -rf /var/lib/apt/lists/*

# Copy server code
COPY server.py .

# Expose port
EXPOSE 9999

# Run server
CMD ["python", "server.py"]
