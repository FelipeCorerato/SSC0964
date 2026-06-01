"""
SSC0964 - Trabalho 1
Constroi o panel de dados (formato espelhando v5-DB-Acoes.csv do prof)
a partir das acoes do S&P 500 via yfinance.

Saidas:
    dados_sp500.csv     - panel mensal com fatores por acao
    indices_sp500.csv   - serie acumulada do benchmark (S&P 500)

Colunas do dados_sp500.csv (mesmas semanticas do CSV do prof):
    Data         - "MMM-YYYY" (ex: "Jan-2015")
    Ticker       - codigo da acao
    IBX          - 1 se a acao esta no universo (S&P 500), 0 c.c. (proxy do IBX)
    Retorno      - retorno mensal da acao no proprio mes (variacao do close)
    Mom12        - retorno acumulado dos ultimos 12 meses (excl mes corrente)
    Mom6         - retorno acumulado dos ultimos 6 meses (excl mes corrente)
    Volat12      - desvio padrao dos retornos mensais nos ultimos 12 meses
    Volat6       - desvio padrao dos retornos mensais nos ultimos 6 meses
    MTUM12       - Mom12 / Volat12 (momentum ajustado a risco)
    MTUM6        - Mom6  / Volat6
    Sharpe12     - media(retornos 12m) / Volat12  (Sharpe rolante)
    MaxDD12      - drawdown maximo nos ultimos 12 meses (valor negativo)
    Beta12       - beta vs benchmark calculado nos ultimos 12 meses
"""

import io
import os
import time
import urllib.request

import numpy as np
import pandas as pd
import yfinance as yf


OUT_DIR = os.path.dirname(os.path.abspath(__file__))
START = '2009-01-01'
END = '2025-12-31'
BENCHMARK = '^GSPC'


def get_sp500_tickers():
    print('-> Buscando lista do S&P 500...')
    url = 'https://en.wikipedia.org/wiki/List_of_S%26P_500_companies'
    req = urllib.request.Request(
        url,
        headers={
            'User-Agent': (
                'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
                'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36'
            ),
        },
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        html = resp.read().decode('utf-8')
    tables = pd.read_html(io.StringIO(html))
    tickers = tables[0]['Symbol'].astype(str).str.replace('.', '-', regex=False)
    tickers = sorted(set(tickers.tolist()))
    print(f'   {len(tickers)} tickers')
    return tickers


def download_monthly_prices(tickers, start, end):
    print('-> Baixando precos mensais (yfinance)...')
    data = yf.download(
        tickers + [BENCHMARK],
        start=start,
        end=end,
        interval='1mo',
        auto_adjust=True,
        progress=False,
        threads=True,
    )
    prices = data['Close'].copy()
    prices.index = pd.to_datetime(prices.index).to_period('M').to_timestamp('M')
    prices = prices.sort_index()
    print(f'   shape: {prices.shape}')
    return prices


def compute_factors(prices, benchmark_col):
    print('-> Calculando fatores rolantes...')

    rets = prices.pct_change()
    bench_ret = rets[benchmark_col]
    stock_rets = rets.drop(columns=[benchmark_col])
    stock_prices = prices.drop(columns=[benchmark_col])

    log_rets = np.log1p(stock_rets)

    mom12_raw = np.expm1(log_rets.shift(1).rolling(12).sum())
    mom6_raw = np.expm1(log_rets.shift(1).rolling(6).sum())

    vol12 = stock_rets.shift(1).rolling(12).std()
    vol6 = stock_rets.shift(1).rolling(6).std()

    mean12 = stock_rets.shift(1).rolling(12).mean()
    sharpe12 = mean12 / vol12

    mtum12 = mom12_raw / vol12.replace(0, np.nan)
    mtum6 = mom6_raw / vol6.replace(0, np.nan)

    print('   calculando MaxDD12 (rolling drawdown)...')
    def rolling_max_dd(series, window=12):
        out = pd.Series(index=series.index, dtype=float)
        vals = series.values
        for i in range(len(vals)):
            if i < window:
                out.iloc[i] = np.nan
                continue
            window_rets = vals[i - window + 1:i + 1]
            if np.isnan(window_rets).all():
                out.iloc[i] = np.nan
                continue
            window_rets = np.where(np.isnan(window_rets), 0, window_rets)
            equity = np.cumprod(1 + window_rets)
            peak = np.maximum.accumulate(equity)
            dd = (equity / peak) - 1
            out.iloc[i] = dd.min()
        return out

    maxdd12 = pd.DataFrame(
        {col: rolling_max_dd(stock_rets[col].shift(1)) for col in stock_rets.columns}
    )

    print('   calculando Beta12...')
    cov12 = stock_rets.shift(1).rolling(12).cov(bench_ret.shift(1))
    var12 = bench_ret.shift(1).rolling(12).var()
    beta12 = cov12.div(var12, axis=0)

    return {
        'Retorno': stock_rets,
        'Mom12': mom12_raw,
        'Mom6': mom6_raw,
        'Volat12': vol12,
        'Volat6': vol6,
        'Sharpe12': sharpe12,
        'MTUM12': mtum12,
        'MTUM6': mtum6,
        'MaxDD12': maxdd12,
        'Beta12': beta12,
        'Prices': stock_prices,
    }


def build_panel(factor_dfs):
    print('-> Montando panel...')
    factor_names = ['Retorno', 'Mom12', 'Mom6', 'Volat12', 'Volat6',
                    'MTUM12', 'MTUM6', 'Sharpe12', 'MaxDD12', 'Beta12']

    panels = []
    for fname in factor_names:
        df = factor_dfs[fname].copy()
        df = df.stack(dropna=False).rename(fname)
        panels.append(df)

    panel = pd.concat(panels, axis=1)
    panel.index.names = ['Date', 'Ticker']
    panel = panel.reset_index()

    prices_long = factor_dfs['Prices'].stack(dropna=False).rename('Close').reset_index()
    prices_long.columns = ['Date', 'Ticker', 'Close']
    panel = panel.merge(prices_long, on=['Date', 'Ticker'], how='left')
    panel['IBX'] = panel['Close'].notna().astype(int)

    panel['Data'] = panel['Date'].dt.strftime('%b-%Y')
    panel = panel[['Data', 'Ticker', 'IBX', 'Retorno',
                   'Mom12', 'Mom6', 'Volat12', 'Volat6',
                   'MTUM12', 'MTUM6', 'Sharpe12', 'MaxDD12', 'Beta12']]
    print(f'   panel shape: {panel.shape}')
    return panel


def build_indices(prices, benchmark_col):
    print('-> Montando indice de referencia...')
    df = pd.DataFrame({'SP500': prices[benchmark_col]})
    df.index = df.index.strftime('%b-%Y')
    df.index.name = 'Data'
    return df


def main():
    t0 = time.time()
    tickers = get_sp500_tickers()

    prices = download_monthly_prices(tickers, START, END)

    available_tickers = [
        t for t in tickers
        if t in prices.columns and prices[t].notna().sum() >= 24
    ]
    print(f'   {len(available_tickers)} tickers com dados suficientes')

    keep_cols = available_tickers + [BENCHMARK]
    prices = prices[keep_cols]

    factor_dfs = compute_factors(prices, BENCHMARK)
    panel = build_panel(factor_dfs)
    indices = build_indices(prices, BENCHMARK)

    out_panel = os.path.join(OUT_DIR, 'dados_sp500.csv')
    out_idx = os.path.join(OUT_DIR, 'indices_sp500.csv')
    panel.to_csv(out_panel, index=False)
    indices.to_csv(out_idx)

    print(f'\nOK - {out_panel}')
    print(f'OK - {out_idx}')
    print(f'tempo total: {time.time() - t0:.1f}s')


if __name__ == '__main__':
    main()
