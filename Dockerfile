# Combined Dockerfile for Privatemode Auth Proxy
# Runs both auth-proxy and privatemode-proxy in a single container

# Stage 1: Extract privatemode-proxy binary from official image
FROM ghcr.io/edgelesssys/privatemode/privatemode-proxy:latest AS privatemode

# Stage 2: Build final image
FROM python:3.12-slim

WORKDIR /app

# Install dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    supervisor \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Copy privatemode-proxy binary from stage 1
COPY --from=privatemode /bin/privatemode-proxy /usr/local/bin/privatemode-proxy

# Install Python dependencies
COPY auth-proxy/requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# Copy auth-proxy code
COPY auth-proxy/ /app/auth-proxy/

# Create non-root user for running the application
RUN groupadd --gid 1000 appuser && \
    useradd --uid 1000 --gid 1000 --shell /bin/bash --create-home appuser

# Create directories for runtime data and set ownership
# /app/certs is for TLS certificates (optional)
RUN mkdir -p /app/workspace /app/secrets /app/data /app/certs && \
    chown -R appuser:appuser /app

# Copy supervisor config (must be readable by appuser)
COPY --chown=appuser:appuser supervisord.conf /app/supervisord.conf

# Health check (uses HTTP or HTTPS based on TLS_ENABLED)
# Note: When TLS is enabled, use -k to skip cert verification for localhost
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -fk https://localhost:8080/health 2>/dev/null || curl -f http://localhost:8080/health || exit 1

# Expose both HTTP and HTTPS ports
EXPOSE 8080 8443

# Switch to non-root user
USER appuser

CMD ["/usr/bin/supervisord", "-c", "/app/supervisord.conf"]
