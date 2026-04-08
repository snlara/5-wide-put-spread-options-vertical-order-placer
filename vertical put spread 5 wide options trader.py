import os
import json
from datetime import datetime, timedelta
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import GetOptionContractsRequest
from alpaca.trading.enums import AssetStatus
from alpaca.data.historical import StockHistoricalDataClient, OptionHistoricalDataClient
from alpaca.data.requests import StockLatestQuoteRequest, OptionLatestQuoteRequest

# --- CONFIGURATION ---
API_KEY = 'PKVGCUDJQ2CWIF7J2LTP6SALT3'
SECRET_KEY = 'GnMRFELScut8t19stbee5ZJERzdJvgyegJjDVDpvGKgp'

trading_client = TradingClient(API_KEY, SECRET_KEY, paper=True)
stock_data = StockHistoricalDataClient(API_KEY, SECRET_KEY)
option_data = OptionHistoricalDataClient(API_KEY, SECRET_KEY)

def get_vertical_put_spread_details(symbol):
    quote_req = StockLatestQuoteRequest(symbol_or_symbols=symbol)
    quote = stock_data.get_stock_latest_quote(quote_req)
    current_price = quote[symbol].ask_price

    target_date = datetime.now().date() + timedelta(days=45)
    search_params = GetOptionContractsRequest(
        underlying_symbols=[symbol], 
        status=AssetStatus.ACTIVE,
        expiration_date_gte=target_date - timedelta(days=10),
        expiration_date_lte=target_date + timedelta(days=10),
        type="put"
    )
    
    response = trading_client.get_option_contracts(search_params)
    contracts = [c for c in response.option_contracts if c.symbol.startswith(symbol.upper())]
    
    short_put = min(contracts, key=lambda x: abs(float(x.strike_price) - current_price))
    target_long_strike = float(short_put.strike_price) - 5
    long_put = min(contracts, key=lambda x: abs(float(x.strike_price) - target_long_strike))

    # Get quotes for midpoint calculation
    sq = option_data.get_option_latest_quote(OptionLatestQuoteRequest(symbol_or_symbols=short_put.symbol))[short_put.symbol]
    lq = option_data.get_option_latest_quote(OptionLatestQuoteRequest(symbol_or_symbols=long_put.symbol))[long_put.symbol]

    spread_mid = ((sq.bid_price + sq.ask_price) / 2) - ((lq.bid_price + lq.ask_price) / 2)

    return {
        "short_sym": short_put.symbol,
        "long_sym": long_put.symbol,
        "short_strike": short_put.strike_price,
        "long_strike": long_put.strike_price,
        "mid": spread_mid
    }

def main():
    while True:
        os.system('cls' if os.name == 'nt' else 'clear')
        print("=== THE SPREAD FIXER (MLEG) ===")
        
        try:
            ticker = input("Enter Ticker: ").strip().upper()
            if not ticker: continue
            data = get_vertical_put_spread_details(ticker)
            
            print(f"\nSpread: Sell {data['short_strike']}P / Buy {data['long_strike']}P")
            print(f"Combined Midpoint Credit: ${data['mid']:.2f}")
            
            qty = input("\nQuantity: ")
            
            # AGGRESSIVE LIMIT: 0.01 below mid
            limit_price = str(round(data['mid'] - 0.01, 2))
            
            payload = {
                "qty": qty,
                "side": "sell",
                "type": "limit",
                "limit_price": limit_price,
                "time_in_force": "day",
                "order_class": "mleg",
                "legs": [
                    {"symbol": data['short_sym'], "ratio_qty": "1", "side": "sell"},
                    {"symbol": data['long_sym'], "ratio_qty": "1", "side": "buy"}
                ]
            }

            if input(f"Submit for ${limit_price} Combined Credit? (y/n): ").lower() == 'y':
                # Bypass the high-level SDK validation entirely
                res = trading_client.post("/orders", data=payload)
                print(f"\n>>> SPREAD SUBMITTED AS ONE ORDER. ID: {res['id']}")
                input("\nPress Enter...")
                
        except Exception as e:
            print(f"\nERROR: {e}")
            input("\nPress Enter to restart...")

if __name__ == "__main__":
    main()