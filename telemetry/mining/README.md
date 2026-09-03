# Mining Telemetry Analyzer

This lab utility calculates daily mining profitability from a local miner CSV.
It attempts to fetch live BTC/EUR pricing from CoinGecko and current Bitcoin
network difficulty from Blockchain.info. If either request fails, it falls back
to the local values in `config.json`.

## Setup

```powershell
py -m pip install -r telemetry\mining\requirements.txt
```

## Run

```powershell
py telemetry\mining\analyzer.py
```

## Inputs

- `config.json`: electricity price, fallback BTC price, fallback network
  difficulty, block reward, and local harvesting watt offset.
- `miner_data.csv`: miner model, hashrate in TH/s, and gross power draw in W.

## Output

The script prints a table with gross/net wattage, estimated daily revenue,
daily electricity cost, daily profit, and a `SYN+` or `ENTROPIE` status.
