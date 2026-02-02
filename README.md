# GwydeonBot

Bot de Discord en Python (`discord.py`) que consulta la API de Blizzard (World of Warcraft Game Data & Profile APIs) y datos públicos de Raider.IO.

## Estructura

- `src/gwydeonbot/cogs`: comandos (capa Discord)
- `src/gwydeonbot/services`: casos de uso (agregan datos, cache, parsers)
- `src/gwydeonbot/clients`: clientes HTTP (Blizzard OAuth, Blizzard APIs, Raider.IO)
- `src/gwydeonbot/domain`: modelos y errores
- `src/gwydeonbot/utils`: helpers (cache TTL, normalizadores, etc.)

## Setup rápido

1. Crea un `.env` a partir de `.env.example`
2. Instala dependencias:
   - `pip install -r requirements.txt`
   - (recomendado) `pip install -e .`  # instala el paquete desde `src/`
3. Arranca el bot:
   - `python -m gwydeonbot`
   - En caso de error usar
   ```bash
   Set-Alias gwydeonbot ".\.venv\Scripts\python.exe"
   gwydeonbot -m gwydeonbot.main
   ```

> Nota: si trabajas con un `venv`, usa `.venv/` y asegúrate de que esté en `.gitignore`.

## Comandos

- `/personaje [nombre] [reino]`
- `/status [reino]`
