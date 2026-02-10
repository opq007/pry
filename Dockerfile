# Use Python 3.10 slim image
FROM python:3.10-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY src/ ./src/
COPY run.py .

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV CHECK_INTERVAL=${CHECK_INTERVAL:-600}
ENV HOST=0.0.0.0
ENV PORT=7860

# Expose port (Hugging Face Spaces uses 7860)
EXPOSE 7860

# Run the application
CMD ["python", "run.py"]