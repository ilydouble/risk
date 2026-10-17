FROM docker:27.5.1-cli AS docker-cli
FROM ghcr.io/astral-sh/uv:0.8.22-python3.12-bookworm-slim
COPY --from=docker-cli /usr/local/bin/docker /usr/local/bin/docker
COPY script_runner/server.py /app/server.py
CMD ["python", "/app/server.py"]
