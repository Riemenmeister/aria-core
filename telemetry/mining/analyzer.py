from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import pandas as pd
import requests


def fetch_live_data() -> tuple[float | None, float | None]:
    """Fetch BTC/EUR price and Bitcoin network difficulty, with caller-owned fallback."""
    print("[SYSTEM-LOG] Initiiere Telemetrie-Sync mit globalem Netzwerk...")
    try:
        btc_url = "https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=eur"
        btc_response = requests.get(btc_url, timeout=5)
        btc_response.raise_for_status()
        btc_price_eur = float(btc_response.json()["bitcoin"]["eur"])

        difficulty_url = "https://blockchain.info/q/getdifficulty"
        difficulty_response = requests.get(difficulty_url, timeout=5)
        difficulty_response.raise_for_status()
        network_difficulty = float(difficulty_response.text)

        print("[SYSTEM-LOG] Live-Daten erfolgreich empfangen.")
        return btc_price_eur, network_difficulty
    except Exception as exc:
        print(f"[WARNUNG] Telemetrie fehlgeschlagen: {exc}")
        print("[SYSTEM-LOG] Wechsle zu lokalem Offline-Backup (config.json).")
        return None, None


def load_config(config_path: str | Path) -> dict[str, Any] | None:
    path = Path(config_path)
    try:
        with path.open("r", encoding="utf-8") as config_file:
            return json.load(config_file)
    except FileNotFoundError:
        print(f"[FEHLER] {path} nicht gefunden.")
    except json.JSONDecodeError as exc:
        print(f"[FEHLER] {path} ist kein gueltiges JSON: {exc}")
    return None


def calculate_profitability(config_path: str | Path, csv_path: str | Path) -> pd.DataFrame | None:
    config = load_config(config_path)
    if config is None:
        return None

    required_keys = {
        "standort",
        "strompreis_kwh_eur",
        "btc_preis_eur",
        "network_difficulty",
        "block_reward",
        "aegis_piezo_harvesting_watt",
    }
    missing_keys = required_keys - set(config)
    if missing_keys:
        print(f"[FEHLER] {config_path} fehlt Pflichtfeld(er): {', '.join(sorted(missing_keys))}")
        return None

    live_btc_price, live_difficulty = fetch_live_data()
    btc_price_eur = live_btc_price if live_btc_price is not None else float(config["btc_preis_eur"])
    difficulty = live_difficulty if live_difficulty is not None else float(config["network_difficulty"])

    electricity_price = float(config["strompreis_kwh_eur"])
    block_reward = float(config["block_reward"])
    harvesting_watt = float(config["aegis_piezo_harvesting_watt"])

    print("\n" + "=" * 72)
    print(" AEGIS & MAGNACORE - MINING SYNTROPIE ANALYZER (LIVE)")
    print("=" * 72)
    print(f"Standort:             {config['standort']}")
    print(f"Strompreis:           {electricity_price:.4f} EUR/kWh")
    print(f"Aktueller BTC-Kurs:   {btc_price_eur:,.2f} EUR")
    print(f"Netzwerk-Difficulty:  {difficulty:,.0f}")
    print(f"AEGIS-Harvest:       -{harvesting_watt:.1f} Watt Rueckgewinnung")
    print("-" * 72 + "\n")

    csv_file = Path(csv_path)
    try:
        miners = pd.read_csv(csv_file)
    except FileNotFoundError:
        print(f"[FEHLER] {csv_file} nicht gefunden. Bitte Hardware-Liste anlegen.")
        return None

    required_columns = {"Modell", "Hashrate_THs", "Verbrauch_W"}
    missing_columns = required_columns - set(miners.columns)
    if missing_columns:
        print(f"[FEHLER] {csv_file} fehlt Spalte(n): {', '.join(sorted(missing_columns))}")
        return None

    results: list[dict[str, Any]] = []
    for _, row in miners.iterrows():
        model = str(row["Modell"])
        hashrate_th = float(row["Hashrate_THs"])
        gross_watts = float(row["Verbrauch_W"])
        net_watts = max(0.0, gross_watts - harvesting_watt)

        hashes_per_second = hashrate_th * 1e12
        daily_btc = (hashes_per_second / (difficulty * (2**32))) * 86400 * block_reward
        daily_revenue_eur = daily_btc * btc_price_eur
        daily_cost_eur = (net_watts / 1000) * 24 * electricity_price
        daily_profit_eur = daily_revenue_eur - daily_cost_eur

        results.append(
            {
                "Modell": model,
                "Brutto(W)": round(gross_watts, 1),
                "Netto(W)": round(net_watts, 1),
                "Rev(EUR/d)": round(daily_revenue_eur, 2),
                "Cost(EUR/d)": round(daily_cost_eur, 2),
                "Profit(EUR/d)": round(daily_profit_eur, 2),
                "Status": "SYN+" if daily_profit_eur > 0 else "ENTROPIE",
            }
        )

    results_df = pd.DataFrame(results)
    print(results_df.to_string(index=False))
    print("\n" + "=" * 72)
    print(f"Zeitstempel der Kalkulation: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    return results_df


if __name__ == "__main__":
    base_dir = Path(__file__).resolve().parent
    calculate_profitability(base_dir / "config.json", base_dir / "miner_data.csv")
