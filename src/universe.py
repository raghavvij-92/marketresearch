"""
Scannable stock universes.

NIFTY100 is a curated list of ~95 large, liquid NSE names (approximate
NIFTY 100 membership). Symbols that fail to resolve (renames, delistings)
are skipped gracefully by the scanner.
"""

NIFTY100 = [
    # Banks & financials
    "HDFCBANK", "ICICIBANK", "SBIN", "KOTAKBANK", "AXISBANK", "INDUSINDBK",
    "BANKBARODA", "PNB", "CANBK", "BAJFINANCE", "BAJAJFINSV", "JIOFIN",
    "SHRIRAMFIN", "CHOLAFIN", "MUTHOOTFIN", "PFC", "RECLTD", "IRFC",
    "SBILIFE", "HDFCLIFE", "ICICIPRULI", "ICICIGI", "LICI",
    # IT
    "TCS", "INFY", "HCLTECH", "WIPRO", "TECHM", "LTIM", "PERSISTENT",
    "COFORGE", "MPHASIS",
    # Energy / commodities
    "RELIANCE", "ONGC", "IOC", "BPCL", "HINDPETRO", "GAIL", "COALINDIA",
    "NTPC", "POWERGRID", "TATAPOWER", "ADANIGREEN", "ADANIPOWER", "ATGL",
    "TATASTEEL", "JSWSTEEL", "HINDALCO", "VEDL", "JINDALSTEL", "NMDC", "SAIL",
    # Autos
    "MARUTI", "TATAMOTORS", "M&M", "BAJAJ-AUTO", "EICHERMOT", "HEROMOTOCO",
    "TVSMOTOR", "MOTHERSON", "BOSCHLTD",
    # Pharma & healthcare
    "SUNPHARMA", "DRREDDY", "CIPLA", "DIVISLAB", "LUPIN", "AUROPHARMA",
    "ZYDUSLIFE", "TORNTPHARM", "ALKEM", "APOLLOHOSP", "MAXHEALTH",
    # Consumer
    "HINDUNILVR", "ITC", "NESTLEIND", "BRITANNIA", "TATACONSUM", "DABUR",
    "MARICO", "GODREJCP", "COLPAL", "UNITDSPR", "UBL", "VBL", "TITAN",
    "ASIANPAINT", "BERGEPAINT", "PIDILITIND", "DMART", "TRENT", "ETERNAL",
    # Industrials / infra
    "LT", "SIEMENS", "ABB", "CGPOWER", "BHEL", "HAL", "BEL", "ULTRACEMCO",
    "GRASIM", "SHREECEM", "AMBUJACEM", "ADANIENT", "ADANIPORTS", "DLF",
    "LODHA", "GODREJPROP", "OBEROIRLTY", "HAVELLS", "POLYCAB", "DIXON",
    "VOLTAS", "ASTRAL",
    # Telecom / internet / transport
    "BHARTIARTL", "NAUKRI", "PAYTM", "POLICYBZR", "INDIGO", "IRCTC", "CONCOR",
]

UNIVERSES = {"nifty100": NIFTY100}
