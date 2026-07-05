FROM python:3.11-slim

# Create app dir
WORKDIR /app

# Install Python dependencies
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# Copy application modules
COPY aria_*.py /app/

# Default environment variables (overridable)
ENV ARIA_HOST=0.0.0.0 \
    ARIA_PORT=65432 \
    ARIA_MAX_CLIENTS=10 \
    ARIA_LOG_FILE=/var/log/aria_listener.log

# Expose default port
EXPOSE 65432

# Create log dir and ensure writable
RUN mkdir -p /var/log && chown -R 1000:1000 /var/log || true

# Run as non-root user for safety
RUN useradd --create-home --uid 1000 ariauser || true
USER ariauser

CMD ["python", "aria_listener.py"]
