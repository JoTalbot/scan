# RouterScan devcontainer — для GitHub Codespaces (120 core-ч/мес бесплатно)
# и VS Code Remote Containers.
FROM mcr.microsoft.com/devcontainers/python:1-3.11

# Системные зависимости (в т.ч. для Playwright headless)
RUN apt-get update && apt-get install -y --no-install-recommends \
    sqlite3 \
    curl \
    iputils-ping \
    && rm -rf /var/lib/apt/lists/*

# Playwright браузеры (ставятся при создании — см. postCreateCommand)
ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright
