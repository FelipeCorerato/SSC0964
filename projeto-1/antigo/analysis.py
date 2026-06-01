"""
SSC0964 - Introducao a Computacao no Mercado Financeiro
Trabalho 1 - 4 Modelos de Fatores para Selecao de Portfolios

Universo:     componentes atuais do S&P 500
Periodo:      2011-01-01 a 2026-05-17 (15 anos)
  - Formacao (calculo de fatores): 2011-01 a 2015-12 (5 anos)
  - Teste    (backtest do portfolio): 2016-01 a 2026-05 (~10 anos)
Benchmark:    S&P 500 (^GSPC)
Risk-free:    2% a.a. (aproximacao da media historica do periodo)
Rebalance:    equal-weighted, sem rebalance mensal (buy & hold das 20 acoes)

Os 4 modelos:
  1. Maior retorno          : Momentum + Consistencia
  2. Maior Sharpe           : Sharpe + Low Drawdown + Skewness positiva
  3. Maior Alpha            : Alpha CAPM + Information Ratio - parcial Beta
  4. Menor volatilidade     : Low Vol + Low Beta + Low Drawdown

Como rodar:
  python analysis.py

Saida (em ./outputs/):
  - summary.csv              tabela resumo com metricas dos 4 portfolios
  - tickers.txt              composicao de cada portfolio
  - <modelo>_cumulative.png  retorno acumulado + MA 60m
  - <modelo>_vol.png         volatilidade anualizada rolante
  - <modelo>_drawdown.png    underwater plot (drawdown)
  - factors.csv              tabela de fatores do periodo de formacao
"""

import io
import os
import re
import sys
import warnings
import urllib.request

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import yfinance as yf
from scipy import stats

warnings.filterwarnings('ignore')
plt.rcParams['figure.dpi'] = 100
plt.rcParams['savefig.dpi'] = 130
plt.rcParams['font.size'] = 10


# ============================================================
# CONFIGURACAO
# ============================================================
START_DATE     = '2011-01-01'
FORMATION_END  = '2015-12-31'
TEST_START     = '2016-01-01'
END_DATE       = '2026-05-17'

BENCHMARK      = '^GSPC'
N_STOCKS       = 20
RF_ANNUAL      = 0.02
RF_MONTHLY     = (1 + RF_ANNUAL) ** (1 / 12) - 1

OUTPUT_DIR     = 'outputs'
os.makedirs(OUTPUT_DIR, exist_ok=True)


# ============================================================
# UTILITARIOS
# ============================================================
def slug(s):
    s = s.lower()
    s = re.sub(r'[áàâã]', 'a', s)
    s = re.sub(r'[éê]', 'e', s)
    s = re.sub(r'[í]', 'i', s)
    s = re.sub(r'[óôõ]', 'o', s)
    s = re.sub(r'[ú]', 'u', s)
    s = re.sub(r'[ç]', 'c', s)
    s = re.sub(r'[^a-z0-9]+', '_', s)
    return s.strip('_')


def zscore(s):
    return (s - s.mean()) / s.std(ddof=0)


# ============================================================
# 1. UNIVERSO: COMPONENTES DO S&P 500
# ============================================================
def get_sp500_tickers():
    print('-> Buscando lista de componentes do S&P 500...')
    url = 'https://en.wikipedia.org/wiki/List_of_S%26P_500_companies'
    req = urllib.request.Request(
        url,
        headers={
            'User-Agent': (
                'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
                'AppleWebKit/537.36 (KHTML, like Gecko) '
                'Chrome/120.0 Safari/537.36'
            ),
        },
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        html = resp.read().decode('utf-8')
    tables = pd.read_html(io.StringIO(html))
    df = tables[0]
    tickers = df['Symbol'].astype(str).str.replace('.', '-', regex=False)
    tickers = sorted(set(tickers.tolist()))
    print(f'   {len(tickers)} tickers encontrados')
    return tickers


# ============================================================
# 2. DOWNLOAD DE PRECOS
# ============================================================
def download_prices(tickers):
    print('-> Baixando precos historicos (yfinance)...')
    all_tickers = tickers + [BENCHMARK]
    data = yf.download(
        all_tickers,
        start=START_DATE,
        end=END_DATE,
        progress=False,
        auto_adjust=True,
        threads=True,
    )
    if isinstance(data.columns, pd.MultiIndex):
        prices = data['Close']
    else:
        prices = data
    min_obs = int(0.7 * len(prices))
    prices = prices.dropna(axis=1, thresh=min_obs)
    print(f'   {prices.shape[1]} series com dados suficientes')
    return prices


# ============================================================
# 3. METRICAS
# ============================================================
def ann_return(rets):
    cum = (1 + rets).prod()
    n_years = len(rets) / 12
    if n_years <= 0 or cum <= 0:
        return np.nan
    return cum ** (1 / n_years) - 1


def ann_vol(rets):
    return rets.std(ddof=0) * np.sqrt(12)


def sharpe(rets, rf_m=RF_MONTHLY):
    excess = rets - rf_m
    s = rets.std(ddof=0)
    if s == 0 or np.isnan(s):
        return np.nan
    return (excess.mean() * 12) / (s * np.sqrt(12))


def max_drawdown(rets):
    cum = (1 + rets).cumprod()
    peak = cum.cummax()
    dd = (cum - peak) / peak
    return dd.min()


def alpha_beta(stock_rets, mkt_rets, rf_m=RF_MONTHLY):
    df = pd.concat([stock_rets, mkt_rets], axis=1).dropna()
    df.columns = ['stock', 'mkt']
    if len(df) < 24:
        return np.nan, np.nan
    y = df['stock'] - rf_m
    x = df['mkt']  - rf_m
    slope, intercept, *_ = stats.linregress(x, y)
    alpha_annual = (1 + intercept) ** 12 - 1
    return alpha_annual, slope


def information_ratio(stock_rets, mkt_rets):
    df = pd.concat([stock_rets, mkt_rets], axis=1).dropna()
    df.columns = ['stock', 'mkt']
    if len(df) < 24:
        return np.nan
    active = df['stock'] - df['mkt']
    s = active.std(ddof=0)
    if s == 0 or np.isnan(s):
        return np.nan
    return (active.mean() * 12) / (s * np.sqrt(12))


def pct_positive_months(rets):
    return (rets > 0).mean()


# ============================================================
# 4. TABELA DE FATORES (PERIODO DE FORMACAO)
# ============================================================
def build_factor_table(formation, mkt_form):
    rows = []
    stocks = [c for c in formation.columns if c != BENCHMARK]
    for t in stocks:
        rets = formation[t].dropna()
        if len(rets) < 36:
            continue
        a, b = alpha_beta(rets, mkt_form)
        rows.append({
            'ticker':       t,
            'ann_return':   ann_return(rets),
            'ann_vol':      ann_vol(rets),
            'sharpe':       sharpe(rets),
            'max_dd':       max_drawdown(rets),
            'alpha':        a,
            'beta':         b,
            'info_ratio':   information_ratio(rets, mkt_form),
            'pct_positive': pct_positive_months(rets),
            'skewness':     rets.skew(),
        })
    df = pd.DataFrame(rows).set_index('ticker').dropna()
    return df


# ============================================================
# 5. OS 4 MODELOS
# ============================================================
def model_1_max_return(f):
    """Maior retorno: Momentum + Consistencia.
    Combina retorno absoluto com % de meses positivos para evitar
    'lottery stocks' que tem retorno alto via poucos eventos extremos.
    """
    score = zscore(f['ann_return']) + zscore(f['pct_positive'])
    return score.nlargest(N_STOCKS).index.tolist()


def model_2_max_sharpe(f):
    """Maior retorno/volatilidade: Sharpe + Low Drawdown + Skewness positiva.
    Sharpe puro pode esconder fat tails. Adicionando |DD| baixo e
    skewness positiva, buscamos assimetria favoravel no retorno.
    """
    score = (
        zscore(f['sharpe'])
        - zscore(f['max_dd'].abs())
        + 0.5 * zscore(f['skewness'])
    )
    return score.nlargest(N_STOCKS).index.tolist()


def model_3_max_alpha(f):
    """Maior Alpha: Alpha CAPM + Information Ratio - parcial Beta.
    Alpha bruto pode vir de exposicao a outros riscos sistematicos.
    IR confirma consistencia do alpha, e penalidade leve em beta
    busca alpha 'puro' (menos correlacionado com o mercado).
    """
    score = (
        zscore(f['alpha'])
        + zscore(f['info_ratio'])
        - 0.3 * zscore(f['beta'])
    )
    return score.nlargest(N_STOCKS).index.tolist()


def model_4_min_vol(f):
    """Menor volatilidade: Low Vol + Low Beta + Low Drawdown.
    Trinity defensiva: nao basta volatilidade baixa, queremos tambem
    beta baixo (defensividade sistemica) e drawdown raso (resiliencia
    em crises).
    """
    score = (
        - zscore(f['ann_vol'])
        - zscore(f['beta'])
        - zscore(f['max_dd'].abs())
    )
    return score.nlargest(N_STOCKS).index.tolist()


# ============================================================
# 6. BACKTEST
# ============================================================
def backtest_equal_weight(tickers, test_rets):
    avail = [t for t in tickers if t in test_rets.columns]
    return test_rets[avail].mean(axis=1)


def portfolio_metrics(port_rets, bench_rets):
    a, b = alpha_beta(port_rets, bench_rets)
    return {
        'Retorno anualizado':       ann_return(port_rets),
        'Volatilidade anualizada':  ann_vol(port_rets),
        'Retorno/Volatilidade':     ann_return(port_rets) / ann_vol(port_rets),
        'Drawdown maximo':          max_drawdown(port_rets),
        'Alpha (anual)':            a,
        'Beta':                     b,
    }


# ============================================================
# 7. GRAFICOS
# ============================================================
def plot_cumulative(port_rets, bench_rets, name):
    cum_p = (1 + port_rets).cumprod()
    cum_b = (1 + bench_rets.loc[port_rets.index]).cumprod()
    ma60 = cum_p.rolling(60, min_periods=12).mean()

    fig, ax = plt.subplots(figsize=(11, 5))
    ax.plot(cum_p.index, cum_p, label=name, lw=2, color='#1f4e79')
    ax.plot(cum_b.index, cum_b, label='S&P 500', lw=1.5,
            color='#888', alpha=0.85)
    ax.plot(ma60.index, ma60, label='Media movel 60m',
            lw=1.2, ls='--', color='#c0392b', alpha=0.8)
    ax.set_title(f'{name} - Retorno Acumulado')
    ax.set_ylabel('Crescimento de $1')
    ax.set_xlabel('')
    ax.legend(loc='upper left')
    fig.tight_layout()
    path = f'{OUTPUT_DIR}/{slug(name)}_cumulative.png'
    fig.savefig(path)
    plt.close(fig)
    return path


def plot_rolling_vol(port_rets, name):
    rv = port_rets.rolling(12).std(ddof=0) * np.sqrt(12)
    fig, ax = plt.subplots(figsize=(11, 4))
    ax.plot(rv.index, rv, lw=1.5, color='#1f4e79')
    ax.fill_between(rv.index, 0, rv, alpha=0.15, color='#1f4e79')
    ax.set_title(f'{name} - Volatilidade Anualizada (janela 12m)')
    ax.set_ylabel('Volatilidade')
    fig.tight_layout()
    path = f'{OUTPUT_DIR}/{slug(name)}_vol.png'
    fig.savefig(path)
    plt.close(fig)
    return path


def plot_drawdown(port_rets, name):
    cum = (1 + port_rets).cumprod()
    peak = cum.cummax()
    dd = (cum - peak) / peak
    fig, ax = plt.subplots(figsize=(11, 4))
    ax.fill_between(dd.index, dd, 0, color='#c0392b', alpha=0.4)
    ax.plot(dd.index, dd, lw=1, color='#7b1f1f')
    ax.set_title(f'{name} - Drawdown')
    ax.set_ylabel('Drawdown')
    fig.tight_layout()
    path = f'{OUTPUT_DIR}/{slug(name)}_drawdown.png'
    fig.savefig(path)
    plt.close(fig)
    return path


# ============================================================
# 8. MAIN
# ============================================================
def main():
    tickers = get_sp500_tickers()
    prices = download_prices(tickers)

    print('-> Calculando retornos mensais...')
    monthly_prices = prices.resample('ME').last()
    monthly_returns = monthly_prices.pct_change().dropna(how='all')

    formation = monthly_returns.loc[:FORMATION_END]
    test = monthly_returns.loc[TEST_START:]
    print(f'   Formacao: {formation.shape[0]} meses '
          f'({formation.index.min().date()} -> '
          f'{formation.index.max().date()})')
    print(f'   Teste:    {test.shape[0]} meses '
          f'({test.index.min().date()} -> '
          f'{test.index.max().date()})')

    if BENCHMARK not in formation.columns:
        print(f'ERRO: benchmark {BENCHMARK} nao baixado')
        sys.exit(1)

    mkt_form = formation[BENCHMARK]
    bench_test = test[BENCHMARK]

    print('-> Calculando tabela de fatores (periodo de formacao)...')
    factors = build_factor_table(formation, mkt_form)
    print(f'   {len(factors)} acoes com fatores validos')
    factors.to_csv(f'{OUTPUT_DIR}/factors.csv')

    print('-> Selecionando portfolios...')
    models = {
        'Modelo 1 - Maior Retorno':     model_1_max_return(factors),
        'Modelo 2 - Maior Sharpe':      model_2_max_sharpe(factors),
        'Modelo 3 - Maior Alpha':       model_3_max_alpha(factors),
        'Modelo 4 - Menor Volatilidade': model_4_min_vol(factors),
    }

    print('-> Backtest no periodo de teste...')
    results = {}
    for name, ticks in models.items():
        rets = backtest_equal_weight(ticks, test)
        rets = rets.dropna()
        metrics = portfolio_metrics(rets, bench_test)
        results[name] = {
            'tickers': ticks,
            'returns': rets,
            'metrics': metrics,
        }

    bench_rets = bench_test.dropna()
    results['Benchmark - S&P 500'] = {
        'tickers': ['^GSPC'],
        'returns': bench_rets,
        'metrics': portfolio_metrics(bench_rets, bench_rets),
    }

    summary = pd.DataFrame(
        {n: r['metrics'] for n, r in results.items()}
    ).T
    summary.to_csv(f'{OUTPUT_DIR}/summary.csv')

    print('\n=== Resultados (periodo de teste) ===\n')
    pd.set_option('display.float_format', lambda x: f'{x:.4f}')
    print(summary)

    print('\n-> Gerando graficos...')
    for name, r in results.items():
        if name.startswith('Benchmark'):
            continue
        plot_cumulative(r['returns'], bench_test, name)
        plot_rolling_vol(r['returns'], name)
        plot_drawdown(r['returns'], name)
        print(f'   {name} OK')

    with open(f'{OUTPUT_DIR}/tickers.txt', 'w') as fp:
        for name, r in results.items():
            fp.write(f'== {name} ==\n')
            fp.write(', '.join(r['tickers']) + '\n\n')

    print(f'\nTudo pronto. Arquivos em ./{OUTPUT_DIR}/')


if __name__ == '__main__':
    main()
