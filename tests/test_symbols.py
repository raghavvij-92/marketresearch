import pytest

from src.symbols import SymbolError, parse_symbol, parse_watchlist


def test_bare_symbol_defaults_to_nse():
    sym = parse_symbol("RELIANCE")
    assert sym.exchange == "NSE"
    assert sym.yahoo == "RELIANCE.NS"
    assert sym.symbol == "RELIANCE"


def test_lowercase_and_whitespace():
    sym = parse_symbol("  tcs ")
    assert sym.yahoo == "TCS.NS"


def test_explicit_ns_suffix():
    assert parse_symbol("INFY.NS").yahoo == "INFY.NS"
    assert parse_symbol("INFY.NSE").yahoo == "INFY.NS"


def test_bse_suffix_and_scrip_code():
    assert parse_symbol("TCS.BO").exchange == "BSE"
    sym = parse_symbol("500325")
    assert sym.exchange == "BSE"
    assert sym.yahoo == "500325.BO"


def test_symbol_with_ampersand_and_hyphen():
    assert parse_symbol("M&M").yahoo == "M&M.NS"
    assert parse_symbol("BAJAJ-AUTO").yahoo == "BAJAJ-AUTO.NS"


def test_index_aliases():
    assert parse_symbol("NIFTY").yahoo == "^NSEI"
    assert parse_symbol("nifty50").yahoo == "^NSEI"
    assert parse_symbol("BANKNIFTY").yahoo == "^NSEBANK"
    assert parse_symbol("SENSEX").yahoo == "^BSESN"
    assert parse_symbol("NIFTY").is_index


def test_invalid_symbols_raise():
    with pytest.raises(SymbolError):
        parse_symbol("")
    with pytest.raises(SymbolError):
        parse_symbol("NOT A SYMBOL !!")


def test_watchlist_dedup_and_rejects():
    parsed, rejected = parse_watchlist(["RELIANCE", "reliance.ns", "??bad??", "TCS"])
    assert [s.symbol for s in parsed] == ["RELIANCE", "TCS"]
    assert rejected == ["??bad??"]
