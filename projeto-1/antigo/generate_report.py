"""
Gera o relatorio final em HTML (auto-contido) e Markdown a partir
dos arquivos produzidos por analysis.py.

Uso:
  python generate_report.py

Saidas:
  - outputs/relatorio.html  (auto-contido, com graficos embedados)
  - outputs/relatorio.md    (markdown puro)
"""

import base64
import os
from pathlib import Path

import pandas as pd

OUT = Path('outputs')


# ============================================================
# CARREGAR DADOS
# ============================================================
summary = pd.read_csv(OUT / 'summary.csv', index_col=0)
factors = pd.read_csv(OUT / 'factors.csv', index_col=0)

with open(OUT / 'tickers.txt') as fp:
    raw = fp.read().strip()

portfolios = {}
for block in raw.split('\n\n'):
    lines = block.strip().split('\n')
    if not lines or not lines[0].startswith('=='):
        continue
    name = lines[0].replace('==', '').strip()
    tickers = [t.strip() for t in lines[1].split(',')]
    portfolios[name] = tickers


# ============================================================
# CONFIG DOS MODELOS
# ============================================================
MODELS = [
    {
        'key':   'modelo_1_maior_retorno',
        'name':  'Modelo 1 - Maior Retorno',
        'short': 'Modelo 1',
        'fatores': 'Momentum (retorno anualizado) + Consistencia (% meses positivos)',
        'formula': 'Score = Z(retorno anualizado) + Z(% meses positivos)',
        'justificativa': (
            'Retorno bruto alto pode ser inflado por poucos eventos extremos '
            '(lottery stocks). Ao combinar com a frequencia de meses positivos, '
            'filtramos acoes que crescem de forma sustentada, evitando '
            'aquelas que dependem de poucos saltos para entregar retorno.'
        ),
    },
    {
        'key':   'modelo_2_maior_sharpe',
        'name':  'Modelo 2 - Maior Sharpe',
        'short': 'Modelo 2',
        'fatores': 'Sharpe + Low Drawdown + Skewness positiva',
        'formula': 'Score = Z(Sharpe) - Z(|Drawdown|) + 0.5 * Z(Skewness)',
        'justificativa': (
            'O Sharpe ratio assume distribuicao normal dos retornos, o que '
            'subestima o risco de fat tails. Adicionar drawdown maximo penaliza '
            'acoes com quedas severas, e skewness positiva privilegia aquelas '
            'com assimetria favoravel (caudas direitas maiores que esquerdas).'
        ),
    },
    {
        'key':   'modelo_3_maior_alpha',
        'name':  'Modelo 3 - Maior Alpha',
        'short': 'Modelo 3',
        'fatores': 'Alpha CAPM + Information Ratio - parcial Beta',
        'formula': 'Score = Z(Alpha) + Z(Information Ratio) - 0.3 * Z(Beta)',
        'justificativa': (
            'Alpha bruto pode ser ruidoso ou vir de exposicao a outros '
            'fatores sistematicos. O Information Ratio confirma a '
            'consistencia do alpha ao longo do tempo. A penalidade parcial '
            'em beta (peso 0.3) busca alpha mais "puro", menos dependente '
            'da direcao do mercado.'
        ),
    },
    {
        'key':   'modelo_4_menor_volatilidade',
        'name':  'Modelo 4 - Menor Volatilidade',
        'short': 'Modelo 4',
        'fatores': 'Low Vol + Low Beta + Low Drawdown',
        'formula': 'Score = -Z(Volatilidade) - Z(Beta) - Z(|Drawdown|)',
        'justificativa': (
            'Trinity defensiva. Volatilidade baixa sozinha nao garante '
            'protecao: queremos tambem beta baixo (defensividade sistemica, '
            'descorrelacao com quedas do mercado) e drawdown raso '
            '(resiliencia comprovada em crises historicas).'
        ),
    },
]

# Analises individuais (escritas com base nos numeros reais)
ANALISES = {
    'Modelo 1 - Maior Retorno': (
        'O modelo selecionou um portfolio de momentum classico — META, V, ORLY, '
        'ULTA, REGN, STZ, SBUX, LMT — acoes que entregaram retornos elevados '
        'no periodo de formacao (2011-2015). No out-of-sample, contudo, o '
        'portfolio entregou 12.78% a.a. contra 13.16% do benchmark, ficando '
        '<strong>abaixo do S&P 500</strong>. Esta e uma licao classica de factor '
        'investing: ranquear acoes apenas pelo retorno passado e um dos piores '
        'preditores de retorno futuro, sofrendo forte reversao a media. Ainda '
        'assim, o portfolio teve drawdown menor (-17.6% vs -24.8%) e beta '
        'controlado (0.90), beneficiado pela inclusao do fator consistencia.'
    ),
    'Modelo 2 - Maior Sharpe': (
        'Selecionou um portfolio de qualidade defensiva — V, MA, HD, COST, LLY, '
        'BMY, AWK, CTAS — com forte presenca de financeiras de pagamento e '
        'consumo nao-ciclico. O portfolio <strong>bateu o benchmark em risco-ajustado</strong>: '
        'Sharpe de 0.94 contra 0.87, com volatilidade menor (13.75% vs 15.16%) '
        'e drawdown muito mais raso (-15.7% vs -24.8%). O alpha anual de 2.48% '
        'sugere que a combinacao Sharpe + Drawdown + Skewness identifica '
        'ativos com perfil de retorno mais previsivel — qualidade que tende '
        'a persistir.'
    ),
    'Modelo 3 - Maior Alpha': (
        'O <strong>vencedor absoluto</strong>: 18.94% a.a., 5.6 pontos percentuais acima '
        'do benchmark, com Sharpe de 1.10 (vs 0.87 do S&P 500). Selecionou '
        'TSLA, AVGO, REGN, AXON, META, DXCM, INCY — empresas que transformaram '
        'suas industrias no out-of-sample. Surpreendentemente, o alpha historico '
        '(2011-2015) revelou-se um preditor robusto do alpha futuro (2016-2026), '
        'sugerindo que vantagens competitivas estruturais persistem. Caveat: '
        'drawdown de -18.9% confirma que alpha vem com volatilidade — beta '
        'de 0.99 indica que o portfolio respira com o mercado.'
    ),
    'Modelo 4 - Menor Volatilidade': (
        'Entregou exatamente o que prometeu: o portfolio mais defensivo da '
        'analise, com vol de 13.08%, beta de 0.43 e drawdown de apenas '
        '-13.92% (o menor entre os 4 modelos e bem abaixo dos -24.77% do '
        'benchmark). A composicao e dominada por utilities (DUK, SO, NEE, '
        'AEP, ED, XEL, AWK, CMS, PPL, D) e consumer staples (KMB, PEP, CHD, '
        'CL). O retorno absoluto de 10.17% e menor que o do benchmark, mas '
        'o alpha de 3.69% mostra que o portfolio entregou eficiencia '
        'risco-ajustada — exatamente o objetivo.'
    ),
}

CONCLUSAO = """
Quatro observacoes pessoais sobre os resultados:

<strong>1. A diversificacao fatorial funcionou.</strong> Todos os quatro
portfolios apresentaram drawdown menor que o S&P 500 no periodo de teste.
Isso reforca a tese central do factor investing: combinar fatores
descorrelacionados produz portfolios mais robustos que screens de fator
unico.

<strong>2. Maior Retorno foi um anti-padrao.</strong> Ranquear apenas por
retorno passado — mesmo combinando com consistencia — produziu o pior
resultado out-of-sample (12.78%, abaixo do benchmark). Isso confirma a
literatura: momentum puro e o fator mais sujeito a reversao a media e
exige fatores complementares de qualidade ou valor para funcionar
consistentemente.

<strong>3. Maior Alpha foi o vencedor inesperado.</strong> Eu esperava que
o Sharpe ou o Min Vol fossem os melhores em risco-ajustado, mas o
portfolio de alpha CAPM bateu todos: 18.94% a.a. e Sharpe 1.10. Isso
sugere que alpha historico nao e ruido — empresas que geram alpha
tendem a continuar gerando alpha, possivelmente porque alpha reflete
vantagens competitivas reais (moats, escalabilidade, vantagens de rede).

<strong>4. Min Vol entregou o que prometeu sem surpresas.</strong> Beta
0.43, drawdown -13.9%, vol 13.1% — o portfolio mais defensivo. O retorno
absoluto menor (10.17%) e o trade-off explicito do mandato. Para
investidores avessos a risco ou em fases proximas a aposentadoria,
modelos como este sao mais apropriados que portfolios de momentum.

<strong>Recomendacao final:</strong> nao existe "melhor modelo" no
absoluto. Cada um serve a um perfil de objetivo. Se eu fosse construir
uma alocacao real combinando os quatro, daria peso maior ao Modelo 3
(alpha) para o nucleo de crescimento e ao Modelo 4 (min vol) para a
parcela defensiva, usando o Modelo 2 (Sharpe) como nucleo equilibrado.
O Modelo 1 (max retorno) eu evitaria, pois sua premissa (retorno passado
prediz retorno futuro) e o aspecto menos confiavel do factor investing.
"""

LIMITACOES = """
<strong>Survivorship bias.</strong> O universo usado e o S&P 500 atual,
nao historico. Empresas que sairam do indice (falencias, fusoes) nao
estao na amostra, inflando ligeiramente os retornos historicos.

<strong>Sem rebalance.</strong> O backtest e buy-and-hold equal-weighted
no inicio do periodo. Implementacao real exigiria rebalance periodico
(trimestral ou anual) para manter os pesos e atualizar os fatores.

<strong>Taxa livre de risco fixa.</strong> Usamos 2% a.a. para todo o
periodo. O Treasury 10y variou entre 0.5% e 5% no intervalo, o que
afeta marginalmente os calculos de Sharpe e alpha.

<strong>Fatores apenas de preco.</strong> Nao usamos fundamentos
(P/L, ROE, margens, crescimento) por consistencia metodologica — esses
dados via yfinance sao snapshots atuais, nao historicos. Um modelo mais
sofisticado incorporaria fatores fundamentalistas com Point-in-Time data.

<strong>Custos de transacao e impostos.</strong> Nao modelados. Em
implementacao real, spreads e impostos sobre dividendos reduziriam
todos os retornos uniformemente.

<strong>Equal-weight.</strong> Esquema simples e robusto, mas outras
ponderacoes (min-variance, risk-parity, equal risk contribution)
poderiam melhorar o perfil risco-retorno, especialmente do Modelo 4.
"""


# ============================================================
# UTILITARIOS
# ============================================================
def img_b64(path):
    with open(path, 'rb') as fp:
        return base64.b64encode(fp.read()).decode('ascii')


def fmt_pct(x):
    return f'{x * 100:.2f}%'


def fmt_num(x):
    return f'{x:.3f}'


# ============================================================
# HTML
# ============================================================
CSS = """
* { box-sizing: border-box; }
body {
  font-family: Georgia, 'Times New Roman', serif;
  max-width: 920px;
  margin: 0 auto;
  padding: 40px 30px;
  color: #222;
  line-height: 1.6;
  background: #fafafa;
}
header {
  text-align: center;
  border-bottom: 2px solid #1f4e79;
  padding-bottom: 20px;
  margin-bottom: 40px;
}
header h1 {
  font-size: 1.4rem;
  margin: 0 0 8px 0;
  color: #1f4e79;
  font-weight: normal;
}
header h2 {
  font-size: 1.9rem;
  margin: 0 0 12px 0;
  color: #111;
}
header .meta {
  color: #666;
  font-style: italic;
  margin: 0;
}
h2.section {
  color: #1f4e79;
  border-bottom: 1px solid #ccc;
  padding-bottom: 6px;
  margin-top: 50px;
}
h3.model {
  color: #c0392b;
  margin-top: 40px;
  border-left: 4px solid #c0392b;
  padding-left: 12px;
}
.meta-box {
  background: #f0f4f8;
  border-left: 3px solid #1f4e79;
  padding: 12px 18px;
  margin: 16px 0;
  font-family: -apple-system, system-ui, sans-serif;
  font-size: 0.95rem;
}
.meta-box strong { color: #1f4e79; }
table {
  border-collapse: collapse;
  width: 100%;
  margin: 20px 0;
  font-family: -apple-system, system-ui, sans-serif;
  font-size: 0.92rem;
  background: white;
}
th, td {
  border: 1px solid #ddd;
  padding: 8px 12px;
  text-align: right;
}
th {
  background: #1f4e79;
  color: white;
  font-weight: 600;
}
td.label, th.label { text-align: left; }
tr.winner { background: #e8f5e9; font-weight: 600; }
.chart {
  margin: 24px 0;
  text-align: center;
}
.chart img {
  max-width: 100%;
  height: auto;
  border: 1px solid #ddd;
}
.tickers {
  font-family: 'SF Mono', Menlo, Consolas, monospace;
  font-size: 0.85rem;
  background: #f5f5f5;
  padding: 10px 14px;
  border-radius: 4px;
  word-break: break-word;
}
p { text-align: justify; }
footer {
  margin-top: 60px;
  padding-top: 20px;
  border-top: 1px solid #ccc;
  color: #888;
  font-size: 0.85rem;
  text-align: center;
}
@media print {
  body { background: white; padding: 0; max-width: none; }
  h2.section, h3.model { page-break-after: avoid; }
  .chart, table { page-break-inside: avoid; }
  h3.model { page-break-before: always; }
  h3.model:first-of-type { page-break-before: auto; }
}
"""


def build_html():
    # Tabela resumo
    rows_html = []
    best_ret = summary['Retorno anualizado'].idxmax()
    best_sharpe = summary['Retorno/Volatilidade'].idxmax()
    best_alpha = summary['Alpha (anual)'].idxmax()
    least_vol = summary['Volatilidade anualizada'].idxmin()
    least_dd = summary['Drawdown maximo'].idxmax()

    for name, row in summary.iterrows():
        cells = [
            f'<td class="label">{name}</td>',
            f'<td>{fmt_pct(row["Retorno anualizado"])}</td>',
            f'<td>{fmt_pct(row["Volatilidade anualizada"])}</td>',
            f'<td>{fmt_num(row["Retorno/Volatilidade"])}</td>',
            f'<td>{fmt_pct(row["Drawdown maximo"])}</td>',
            f'<td>{fmt_pct(row["Alpha (anual)"])}</td>',
            f'<td>{fmt_num(row["Beta"])}</td>',
        ]
        rows_html.append(f'<tr>{"".join(cells)}</tr>')

    summary_table = f"""
<table>
  <thead>
    <tr>
      <th class="label">Portfolio</th>
      <th>Retorno anual</th>
      <th>Volatilidade anual</th>
      <th>Retorno/Vol</th>
      <th>Drawdown max</th>
      <th>Alpha (anual)</th>
      <th>Beta</th>
    </tr>
  </thead>
  <tbody>
    {''.join(rows_html)}
  </tbody>
</table>
"""

    # Secoes dos modelos
    model_sections = []
    for m in MODELS:
        name = m['name']
        if name not in summary.index:
            continue
        row = summary.loc[name]
        ticks = portfolios.get(name, [])

        cum_b64 = img_b64(OUT / f"{m['key']}_cumulative.png")
        vol_b64 = img_b64(OUT / f"{m['key']}_vol.png")
        dd_b64 = img_b64(OUT / f"{m['key']}_drawdown.png")

        metrics_table = f"""
<table>
  <tbody>
    <tr><td class="label">Retorno anualizado</td>
        <td>{fmt_pct(row['Retorno anualizado'])}</td></tr>
    <tr><td class="label">Volatilidade anualizada</td>
        <td>{fmt_pct(row['Volatilidade anualizada'])}</td></tr>
    <tr><td class="label">Retorno / Volatilidade</td>
        <td>{fmt_num(row['Retorno/Volatilidade'])}</td></tr>
    <tr><td class="label">Drawdown maximo</td>
        <td>{fmt_pct(row['Drawdown maximo'])}</td></tr>
    <tr><td class="label">Alpha (anual)</td>
        <td>{fmt_pct(row['Alpha (anual)'])}</td></tr>
    <tr><td class="label">Beta</td>
        <td>{fmt_num(row['Beta'])}</td></tr>
  </tbody>
</table>
"""

        section = f"""
<h3 class="model">{name}</h3>

<div class="meta-box">
  <p><strong>Fatores combinados:</strong> {m['fatores']}</p>
  <p><strong>Formula de score:</strong> <code>{m['formula']}</code></p>
</div>

<p><strong>Justificativa da escolha:</strong> {m['justificativa']}</p>

<h4>Composicao do portfolio (equal-weight, 5% cada)</h4>
<div class="tickers">{', '.join(ticks)}</div>

<h4>Metricas (periodo de teste: jan/2016 a mai/2026)</h4>
{metrics_table}

<h4>Analise</h4>
<p>{ANALISES[name]}</p>

<div class="chart">
  <img src="data:image/png;base64,{cum_b64}"
       alt="{name} - retorno acumulado">
</div>

<div class="chart">
  <img src="data:image/png;base64,{vol_b64}"
       alt="{name} - volatilidade">
</div>

<div class="chart">
  <img src="data:image/png;base64,{dd_b64}"
       alt="{name} - drawdown">
</div>
"""
        model_sections.append(section)

    html = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8">
  <title>SSC0964 - Trabalho 1: Modelos de Fatores</title>
  <style>{CSS}</style>
</head>
<body>
  <header>
    <h1>SSC0964 - Introducao a Computacao no Mercado Financeiro</h1>
    <h2>Trabalho 1: Modelos de Fatores para Selecao de Portfolios</h2>
    <p class="meta">Felipe Corerato &middot; 1&deg; Semestre 2026 &middot;
       Prof. Denis Fernando Wolf</p>
  </header>

  <main>

  <h2 class="section">1. Introducao</h2>
  <p>Este trabalho aplica modelos de fatores quantitativos para construir
  quatro portfolios de 20 acoes cada, com objetivos distintos: maximizar
  retorno, maximizar Sharpe (retorno por unidade de risco), maximizar
  alpha (retorno acima do benchmark), e minimizar volatilidade. Cada
  modelo combina pelo menos dois fatores complementares, evitando os
  vieses tipicos de screens baseados em um unico fator.</p>

  <h2 class="section">2. Metodologia</h2>

  <h3>Universo e periodo</h3>
  <p>O universo de selecao e composto pelas {len(factors)} acoes
  componentes atuais do S&P 500 que possuem dados continuos no periodo
  analisado. O periodo total cobre <strong>15 anos</strong>, de janeiro
  de 2011 a maio de 2026, divididos em:</p>
  <ul>
    <li><strong>Periodo de formacao (2011-01 a 2015-12):</strong>
        usado exclusivamente para o calculo dos fatores e selecao das
        20 acoes de cada portfolio.</li>
    <li><strong>Periodo de teste (2016-01 a 2026-05):</strong>
        usado para o backtest out-of-sample da performance dos
        portfolios.</li>
  </ul>
  <p>Esta separacao temporal evita <em>look-ahead bias</em> —
  selecionar acoes com base no mesmo periodo usado para avaliar
  produziria resultados artificialmente otimistas.</p>

  <h3>Benchmark e taxa livre de risco</h3>
  <p>O benchmark adotado e o proprio S&P 500 (ticker <code>^GSPC</code>).
  A taxa livre de risco usada nos calculos de Sharpe, alpha e CAPM e de
  2% a.a., aproximacao da media historica do periodo.</p>

  <h3>Fatores utilizados</h3>
  <p>Todos os fatores sao derivados de preco (sem fundamentos), para
  manter consistencia metodologica e evitar problemas de Point-in-Time:</p>
  <ul>
    <li><strong>Retorno anualizado</strong> (momentum bruto)</li>
    <li><strong>Volatilidade anualizada</strong> (desvio padrao mensal
        anualizado)</li>
    <li><strong>Sharpe ratio</strong> (excesso de retorno / volatilidade)</li>
    <li><strong>Drawdown maximo</strong> (maior queda pico-a-vale)</li>
    <li><strong>Alpha CAPM</strong> (intercepto da regressao do excesso
        do retorno da acao contra o excesso do retorno do mercado)</li>
    <li><strong>Beta CAPM</strong> (coeficiente angular da mesma
        regressao)</li>
    <li><strong>Information Ratio</strong> (retorno ativo medio /
        tracking error)</li>
    <li><strong>% de meses positivos</strong> (proxy de consistencia)</li>
    <li><strong>Skewness</strong> (assimetria da distribuicao de
        retornos)</li>
  </ul>

  <h3>Processo de rankeamento e selecao</h3>
  <p>Para cada acao, calculam-se os fatores acima sobre o periodo de
  formacao. Em seguida, cada fator e normalizado via Z-score
  (padronizacao cruzando todas as acoes do universo). Cada modelo
  combina os Z-scores em uma formula propria, e as 20 acoes com maior
  pontuacao final compoem o portfolio.</p>

  <h3>Construcao e backtest do portfolio</h3>
  <p>Cada portfolio e construido com pesos iguais (equal-weighted, 5%
  por acao) e mantido como buy-and-hold durante todo o periodo de
  teste. O retorno do portfolio em cada mes e a media dos retornos das
  20 acoes naquele mes.</p>

  <h2 class="section">3. Os Quatro Modelos</h2>

  {''.join(model_sections)}

  <h2 class="section">4. Comparacao Consolidada</h2>
  <p>A tabela abaixo resume as metricas dos quatro portfolios no periodo
  de teste, comparadas ao benchmark S&P 500.</p>

  {summary_table}

  <p>Observacoes-chave:</p>
  <ul>
    <li><strong>Maior retorno absoluto:</strong> {best_ret}
        ({fmt_pct(summary.loc[best_ret, 'Retorno anualizado'])})</li>
    <li><strong>Melhor retorno/volatilidade:</strong> {best_sharpe}
        ({fmt_num(summary.loc[best_sharpe, 'Retorno/Volatilidade'])})</li>
    <li><strong>Maior alpha anualizado:</strong> {best_alpha}
        ({fmt_pct(summary.loc[best_alpha, 'Alpha (anual)'])})</li>
    <li><strong>Menor volatilidade:</strong> {least_vol}
        ({fmt_pct(summary.loc[least_vol, 'Volatilidade anualizada'])})</li>
    <li><strong>Menor drawdown:</strong> {least_dd}
        ({fmt_pct(summary.loc[least_dd, 'Drawdown maximo'])})</li>
  </ul>

  <h2 class="section">5. Conclusao Pessoal</h2>
  {''.join(f'<p>{p}</p>' for p in CONCLUSAO.strip().split(chr(10) + chr(10)))}

  <h2 class="section">6. Limitacoes e Melhorias Futuras</h2>
  {''.join(f'<p>{p}</p>' for p in LIMITACOES.strip().split(chr(10) + chr(10)))}

  </main>

  <footer>
    Trabalho 1 — SSC0964 — ICMC/USP — 1&deg; Semestre 2026
  </footer>
</body>
</html>
"""
    return html


# ============================================================
# MARKDOWN
# ============================================================
def build_markdown():
    lines = []
    lines.append('# SSC0964 - Trabalho 1: Modelos de Fatores para '
                 'Selecao de Portfolios')
    lines.append('')
    lines.append('**Aluno:** Felipe Corerato  ')
    lines.append('**Disciplina:** SSC0964 - Introducao a Computacao no '
                 'Mercado Financeiro  ')
    lines.append('**Professor:** Denis Fernando Wolf  ')
    lines.append('**Semestre:** 1o/2026')
    lines.append('')
    lines.append('---')
    lines.append('')

    lines.append('## 1. Introducao')
    lines.append('')
    lines.append(
        'Este trabalho aplica modelos de fatores quantitativos para construir '
        'quatro portfolios de 20 acoes cada, com objetivos distintos: '
        'maximizar retorno, maximizar Sharpe, maximizar alpha, e minimizar '
        'volatilidade. Cada modelo combina pelo menos dois fatores '
        'complementares, evitando vieses tipicos de screens de fator unico.'
    )
    lines.append('')

    lines.append('## 2. Metodologia')
    lines.append('')
    lines.append('### Universo e periodo')
    lines.append('')
    lines.append(
        f'- **Universo:** {len(factors)} acoes do S&P 500 com dados continuos\n'
        '- **Periodo total:** 15 anos (2011-01 a 2026-05)\n'
        '- **Periodo de formacao:** 2011-01 a 2015-12 (calculo de fatores)\n'
        '- **Periodo de teste:** 2016-01 a 2026-05 (backtest out-of-sample)\n'
        '- **Benchmark:** S&P 500 (^GSPC)\n'
        '- **Risk-free:** 2% a.a.\n'
        '- **Construcao:** equal-weighted (5% por acao), buy-and-hold'
    )
    lines.append('')

    lines.append('### Processo de rankeamento')
    lines.append('')
    lines.append(
        'Para cada acao, calculam-se os fatores sobre o periodo de formacao. '
        'Cada fator e normalizado via Z-score. Cada modelo combina os '
        'Z-scores em uma formula propria, e as 20 acoes com maior pontuacao '
        'final compoem o portfolio. A separacao formacao/teste evita '
        'look-ahead bias.'
    )
    lines.append('')

    lines.append('## 3. Os Quatro Modelos')
    lines.append('')

    for m in MODELS:
        name = m['name']
        if name not in summary.index:
            continue
        row = summary.loc[name]
        ticks = portfolios.get(name, [])

        lines.append(f'### {name}')
        lines.append('')
        lines.append(f'**Fatores:** {m["fatores"]}  ')
        lines.append(f'**Formula:** `{m["formula"]}`')
        lines.append('')
        lines.append(f'**Justificativa:** {m["justificativa"]}')
        lines.append('')
        lines.append(f'**Composicao ({len(ticks)} acoes, equal-weight):**')
        lines.append('')
        lines.append(f'`{", ".join(ticks)}`')
        lines.append('')
        lines.append('**Metricas:**')
        lines.append('')
        lines.append('| Metrica | Valor |')
        lines.append('|---|---|')
        lines.append(
            f'| Retorno anualizado     '
            f'| {fmt_pct(row["Retorno anualizado"])} |')
        lines.append(
            f'| Volatilidade anualizada '
            f'| {fmt_pct(row["Volatilidade anualizada"])} |')
        lines.append(
            f'| Retorno / Volatilidade '
            f'| {fmt_num(row["Retorno/Volatilidade"])} |')
        lines.append(
            f'| Drawdown maximo        '
            f'| {fmt_pct(row["Drawdown maximo"])} |')
        lines.append(
            f'| Alpha (anual)          '
            f'| {fmt_pct(row["Alpha (anual)"])} |')
        lines.append(
            f'| Beta                   '
            f'| {fmt_num(row["Beta"])} |')
        lines.append('')
        analise = ANALISES[name].replace('<strong>', '**').replace(
            '</strong>', '**')
        lines.append(f'**Analise:** {analise}')
        lines.append('')
        lines.append(f'![Retorno acumulado]({m["key"]}_cumulative.png)')
        lines.append('')
        lines.append(f'![Volatilidade]({m["key"]}_vol.png)')
        lines.append('')
        lines.append(f'![Drawdown]({m["key"]}_drawdown.png)')
        lines.append('')

    lines.append('## 4. Comparacao Consolidada')
    lines.append('')
    lines.append('| Portfolio | Ret. anual | Vol. anual | Ret/Vol | '
                 'Drawdown | Alpha | Beta |')
    lines.append('|---|---|---|---|---|---|---|')
    for name, row in summary.iterrows():
        lines.append(
            f'| {name} | {fmt_pct(row["Retorno anualizado"])} | '
            f'{fmt_pct(row["Volatilidade anualizada"])} | '
            f'{fmt_num(row["Retorno/Volatilidade"])} | '
            f'{fmt_pct(row["Drawdown maximo"])} | '
            f'{fmt_pct(row["Alpha (anual)"])} | '
            f'{fmt_num(row["Beta"])} |')
    lines.append('')

    lines.append('## 5. Conclusao Pessoal')
    lines.append('')
    conc = CONCLUSAO.replace('<strong>', '**').replace('</strong>', '**')
    lines.append(conc.strip())
    lines.append('')

    lines.append('## 6. Limitacoes e Melhorias Futuras')
    lines.append('')
    lim = LIMITACOES.replace('<strong>', '**').replace('</strong>', '**')
    lines.append(lim.strip())
    lines.append('')

    return '\n'.join(lines)


# ============================================================
# MAIN
# ============================================================
def main():
    print('-> Gerando relatorio HTML...')
    html = build_html()
    (OUT / 'relatorio.html').write_text(html, encoding='utf-8')
    size_kb = (OUT / 'relatorio.html').stat().st_size / 1024
    print(f'   outputs/relatorio.html  ({size_kb:.0f} KB)')

    print('-> Gerando relatorio Markdown...')
    md = build_markdown()
    (OUT / 'relatorio.md').write_text(md, encoding='utf-8')
    size_kb = (OUT / 'relatorio.md').stat().st_size / 1024
    print(f'   outputs/relatorio.md   ({size_kb:.0f} KB)')

    print('\nPronto.')
    print('Para gerar PDF: abra outputs/relatorio.html no Chrome/Safari,')
    print('Cmd+P -> Salvar como PDF.')


if __name__ == '__main__':
    main()
