# eskendirsoil

Telegram bot for oil and gas prices, made for Eskendir.

- `/prices`: WTI, Brent, natural gas, RBOB gasoline and heating oil futures from Yahoo Finance (no API key needed)
- `/rates`: USD against KZT, EUR, RUB, GBP, CNY and SAR from open.er-api.com
- `/facts`: short notes on OPEC, Brent, WTI and Kazakhstan's oil fields, kept in SQLite
- `/history` and `/stats`: each user's recent questions, logged to SQLite

It runs as a webhook server on aiohttp and was written to be deployed on Render.

## Run

```
pip install -r requirements.txt
export BOT_TOKEN=<token from @BotFather>
export WEBHOOK_URL=https://<your-app>.onrender.com
python main.py
```

The server listens on `PORT` (default 8080) and answers health checks on `/`.
