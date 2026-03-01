---
name: finance
description: >
  Fetch stock quotes, crypto prices, forex rates, and financial data.
  Use when the user asks about any stock price, market data, company
  financials, or cryptocurrency price.
---

## Instructions

Fetch real-time financial data for stocks, crypto, and forex using
Yahoo Finance (via the `yfinance` library).

### Prerequisites

Install the dependency: `pip install yfinance`

No API key needed — Yahoo Finance is free.

### Usage

```bash
python {skill_path}/fetch_quote.py SYMBOL [SYMBOL2 ...]
```

Options:
- `--format json` — output as JSON (default: human-readable text)
- `--history 5d` — include price history (1d, 5d, 1mo, 3mo, 6mo, 1y, 5y, max)

### Examples

- "What's Tesla's stock price?" → `python {skill_path}/fetch_quote.py TSLA`
- "Compare AAPL and MSFT" → `python {skill_path}/fetch_quote.py AAPL MSFT`
- "Show Bitcoin price" → `python {skill_path}/fetch_quote.py BTC-USD`
- "EUR/USD exchange rate" → `python {skill_path}/fetch_quote.py EURUSD=X`

## Resources

| File | Description |
|------|-------------|
| `fetch_quote.py` | Multi-symbol financial data fetcher |
