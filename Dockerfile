# Use Python 3.10 slim image
FROM python:3.10-slim

# Set working directory
WORKDIR /app

# Install system dependencies (including git)
RUN apt-get update && apt-get install -y \
    git \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Clone the GitHub repository
# Set your GitHub repository URL here
ARG GITHUB_REPO=https://github.com/opq007/pry.git
ARG GITHUB_BRANCH=master

RUN echo "Cloning from $GITHUB_REPO..." && \
    git clone --depth 1 --branch ${GITHUB_BRANCH} ${GITHUB_REPO} /tmp/repo && \
    cp -r /tmp/repo/src /app/ && \
    cp /tmp/repo/run.py /app/ && \
    rm -rf /tmp/repo

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV CHECK_INTERVAL=${CHECK_INTERVAL:-600}
ENV HOST=0.0.0.0
ENV PORT=7860

# Expose port (Hugging Face Spaces uses 7860)
EXPOSE 7860

# Run the application
CMD ["python", "run.py"]