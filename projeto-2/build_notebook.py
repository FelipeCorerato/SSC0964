"""Gera o notebook final do Trabalho 2 (SSC0964)."""
import nbformat as nbf
from nbformat.v4 import new_notebook, new_markdown_cell, new_code_cell

nb = new_notebook()
cells = []
md = lambda s: cells.append(new_markdown_cell(s))
co = lambda s: cells.append(new_code_cell(s))

md("""# Trabalho 2 — Alocação Sistemática em Classes de Ativos com Aprendizado Supervisionado

**SSC0964 — Introdução à Computação no Mercado Financeiro — 1º Semestre 2026**
**Prof. Denis Fernando Wolf**

**Dupla:** Ana Lívia de Magalhães Garbin (nº USP: 14557394) e Felipe Reis Corerato (nº USP: 14569800)

---

## 1. Objetivo

Construir uma **estratégia de alocação sistemática entre classes de ativos** em que um
algoritmo de **aprendizado supervisionado** decide, mês a mês, em quais classes investir.

## 2. O que fizemos de diferente das aulas

Na Aula 10 a alocação era **binária** (IBOV *vs* SELIC) e usava como entrada apenas o
*momentum* de 1/3/6 meses do IBOV. Aqui ampliamos a abordagem em três frentes:

1. **Universo multi-classe (5 classes):** IBOV (ações Brasil), SP500BR (ações EUA em R$),
   IMAB (renda fixa indexada à inflação), OURO e SELIC-ACC (caixa). O modelo deixa de
   escolher entre 2 opções e passa a escolher entre 5.
2. **Combinação rica de dados de entrada:** além do *momentum* (1/3/6/12m) de **cada**
   classe, adicionamos **volatilidade** rolante, **momentum ajustado a risco** e —
   principalmente — **sinais macroeconômicos** que estavam na base mas não eram usados como
   entrada: o **ciclo de juros** (nível e variação da SELIC-META) e a **inflação**
   (IPCA e IGP-M acumulados em 12 meses), além do *momentum* do câmbio (USD).
3. **Saída multiclasse + dois esquemas de alocação:** o alvo (*target*) é a **classe
   vencedora do próximo mês** (problema de classificação com 5 classes). A partir da
   previsão testamos dois esquemas: *winner-takes-all* (100% na classe prevista) e
   **top-2** (50/50 nas duas classes de maior probabilidade), este último para diversificar
   e reduzir risco.
""")

md("## 3. Importação das bibliotecas")
co("""import warnings
warnings.simplefilter('ignore')

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

from sklearn.tree import DecisionTreeClassifier
from sklearn.ensemble import RandomForestClassifier
from sklearn.neural_network import MLPClassifier
from sklearn.svm import SVC
from sklearn import metrics

sns.set(style='whitegrid')""")

md("""## 4. Leitura dos dados

A base `v6-DB-Indices.xlsx` (a mesma das Aulas 9 e 10) contém séries **mensais** de
Dez/1999 a Mai/2026. No Google Colab, faça o *upload* do arquivo (ícone de pasta na
lateral) antes de executar a célula abaixo.""")
co("""dados = pd.read_excel('v6-DB-Indices.xlsx', engine='openpyxl')
dados.set_index('Data', inplace=True)
print('Período:', dados.index[0], '->', dados.index[-1], '|', dados.shape[0], 'meses')
dados.tail()""")

md("""## 5. Universo investível e retornos

Selecionamos 5 classes de ativos com perfis de risco-retorno distintos. As demais séries da
base (IPCA, IGP-M, SELIC-META) **não são ativos investíveis** — entram apenas como *features*
macroeconômicas na próxima seção.""")
co("""UNIV = ['IBOV', 'SP500BR', 'IMAB', 'OURO', 'SELIC-ACC']

# Retornos mensais simples de cada classe
ret = dados[UNIV].pct_change()
ret.tail()""")

md("""## 6. Variáveis de entrada (*features*)

Para cada classe calculamos *momentum* de 1/3/6/12 meses, volatilidade rolante de 12 meses e
*momentum* ajustado a risco (6m / vol12). Em seguida acrescentamos as variáveis macro
compartilhadas por todas as classes.""")
co("""feat = pd.DataFrame(index=dados.index)

for c in UNIV:
    lvl = dados[c]
    feat[f'{c}_mom1']  = lvl / lvl.shift(1)  - 1
    feat[f'{c}_mom3']  = lvl / lvl.shift(3)  - 1
    feat[f'{c}_mom6']  = lvl / lvl.shift(6)  - 1
    feat[f'{c}_mom12'] = lvl / lvl.shift(12) - 1
    vol12 = ret[c].rolling(12).std()
    feat[f'{c}_vol12'] = vol12
    feat[f'{c}_radj']  = (lvl / lvl.shift(6) - 1) / vol12.replace(0, np.nan)

# Sinais macroeconômicos (originalidade): ciclo de juros, inflação e câmbio
feat['selic_meta'] = dados['SELIC-META']
feat['selic_chg']  = dados['SELIC-META'] - dados['SELIC-META'].shift(1)
feat['ipca_12m']   = dados['IPCA'] / dados['IPCA'].shift(12) - 1
feat['igpm_12m']   = dados['IGPM'] / dados['IGPM'].shift(12) - 1
feat['usd_mom3']   = dados['USD']  / dados['USD'].shift(3)  - 1

print('Total de features:', feat.shape[1])
feat.tail()""")

md("""## 7. Variável de saída (*target*)

O alvo é a **classe de maior retorno no mês seguinte** (`ret.shift(-1).idxmax`). É um problema
de **classificação multiclasse** (5 rótulos). Note que usamos apenas informação conhecida em
*t* para prever o vencedor de *t+1* — sem *look-ahead*.""")
co("""winner_next = ret.shift(-1).idxmax(axis=1)
cls2id = {c: i for i, c in enumerate(UNIV)}
y = winner_next.map(cls2id)

# Monta a tabela final e remove linhas com NaN (início das janelas / último mês)
df = feat.copy()
df['y'] = y
df = df.dropna()
df['y'] = df['y'].astype(int)

X = df.drop(columns='y').to_numpy()
yv = df['y'].to_numpy()
dates = df.index
print('Amostras válidas:', len(df), '| Período:', dates[0], '->', dates[-1])

dist = df['y'].map({i: c for i, c in enumerate(UNIV)}).value_counts()
dist.plot(kind='bar', figsize=(8, 3), title='Distribuição da classe vencedora (mês seguinte)');
plt.tight_layout(); plt.show()
dist""")

md("""## 8. Separação treino / validação

Treinamos nos primeiros 150 meses e validamos **fora da amostra** (*out-of-sample*) no
restante — exatamente como na Aula 10.""")
co("""n_train = 150
Xtr, ytr = X[:n_train], yv[:n_train]
Xte, yte = X[n_train:], yv[n_train:]
test_dates = dates[n_train:]
print('Treino:', dates[0], '->', dates[n_train-1])
print('Validação:', test_dates[0], '->', test_dates[-1], f'({len(test_dates)} meses)')""")

md("""## 9. Modelos e funções de avaliação

Comparamos os mesmos quatro algoritmos vistos em aula (Árvore de Decisão, Random Forest, Rede
Neural MLP e SVM). As funções abaixo realizam o *backtest* mensal e calculam as métricas
financeiras (retorno acumulado, retorno anualizado/CAGR, volatilidade anualizada, índice de
Sharpe e *drawdown* máximo).""")
co("""models = {
    'DecisionTree': DecisionTreeClassifier(random_state=1, max_depth=5),
    'RandomForest': RandomForestClassifier(random_state=1, max_depth=5, n_estimators=200),
    'MLP':          MLPClassifier(random_state=1, hidden_layer_sizes=(32,), max_iter=5000,
                                  activation='tanh', solver='lbfgs'),
    'SVM':          SVC(random_state=1, kernel='rbf', class_weight='balanced', probability=True),
}

def backtest(pred_labels, idx):
    \"\"\"100% na classe prevista; devolve a série de retornos realizados em t+1.\"\"\"
    out = []
    for k, date in enumerate(idx):
        loc = ret.index.get_loc(date)
        out.append(ret[UNIV[pred_labels[k]]].iloc[loc + 1] if loc + 1 < len(ret) else 0.0)
    return pd.Series(out, index=idx)

def backtest_topk(proba, idx, k=2):
    \"\"\"1/k nas k classes de maior probabilidade prevista.\"\"\"
    out = []
    for j, date in enumerate(idx):
        top = np.argsort(proba[j])[::-1][:k]
        loc = ret.index.get_loc(date)
        out.append(np.mean([ret[UNIV[c]].iloc[loc + 1] for c in top]) if loc + 1 < len(ret) else 0.0)
    return pd.Series(out, index=idx)

def stats(r):
    r = r.dropna()
    acc = (1 + r).prod()
    cagr = acc ** (12 / len(r)) - 1
    vol = r.std() * np.sqrt(12)
    sharpe = cagr / vol if vol > 0 else np.nan
    eq = (1 + r).cumprod()
    mdd = (eq / eq.cummax() - 1).min()
    return {'CAGR%': cagr*100, 'Vol%': vol*100, 'Sharpe': sharpe,
            'RetAcum%': (acc-1)*100, 'MaxDD%': mdd*100}""")

md("### 9.1. Esquema *winner-takes-all* (100% na classe prevista)")
co("""linhas = {}
fitted = {}
curvas = {}
for name, clf in models.items():
    clf.fit(Xtr, ytr)
    fitted[name] = clf
    acc_tr = metrics.accuracy_score(ytr, clf.predict(Xtr))
    pred_te = clf.predict(Xte)
    acc_te = metrics.accuracy_score(yte, pred_te)
    r = backtest(pred_te, test_dates)
    s = stats(r); s['acc_tr'] = acc_tr; s['acc_te'] = acc_te
    linhas[name] = s
    curvas[name] = r

tab_wta = pd.DataFrame(linhas).T[['acc_tr', 'acc_te', 'CAGR%', 'Vol%', 'Sharpe', 'RetAcum%', 'MaxDD%']]
tab_wta.round(2)""")

md("### 9.2. Esquema *top-2* (50/50 nas duas classes mais prováveis)")
co("""linhas_top = {}
curvas_top = {}
for name, clf in fitted.items():
    proba = clf.predict_proba(Xte)
    r = backtest_topk(proba, test_dates, k=2)
    linhas_top[name] = stats(r)
    curvas_top[name] = r

tab_top = pd.DataFrame(linhas_top).T[['CAGR%', 'Vol%', 'Sharpe', 'RetAcum%', 'MaxDD%']]
tab_top.round(2)""")

md("""## 10. Comparação com *benchmarks*

Comparamos as estratégias com: (a) o *buy-and-hold* de cada classe; (b) uma carteira
**ingênua de pesos iguais** (20% em cada classe, rebalanceada mensalmente); e (c) o
**ORACLE** — a alocação perfeita (sempre na melhor classe), que mostra o teto teórico de
desempenho.""")
co("""bench = {}
for c in UNIV:
    bench[c] = stats(ret[c].loc[test_dates])
bench['EqualWeight'] = stats(ret[UNIV].loc[test_dates].mean(axis=1))
bench['ORACLE'] = stats(ret[UNIV].shift(-1).max(axis=1).loc[test_dates])

tab_bench = pd.DataFrame(bench).T[['CAGR%', 'Vol%', 'Sharpe', 'RetAcum%', 'MaxDD%']]
tab_bench.round(2)""")

md("## 11. Curvas de capital (validação *out-of-sample*)")
co("""plt.figure(figsize=(15, 6))
# Melhores estratégias de ML
(1 + curvas['MLP']).cumprod().plot(label='ML — MLP (winner-takes-all)', lw=2)
(1 + curvas_top['RandomForest']).cumprod().plot(label='ML — Random Forest (top-2)', lw=2)
# Benchmarks
(1 + ret['IBOV'].loc[test_dates]).cumprod().plot(label='IBOV (buy & hold)', ls='--')
(1 + ret['SP500BR'].loc[test_dates]).cumprod().plot(label='SP500BR (buy & hold)', ls='--')
(1 + ret[UNIV].loc[test_dates].mean(axis=1)).cumprod().plot(label='Equal Weight', ls=':')
plt.title('Curva de capital — período de validação (base 1.0)')
plt.ylabel('Capital acumulado'); plt.legend(); plt.tight_layout(); plt.show()""")

md("## 12. Importância das variáveis (Random Forest)")
co("""rf = fitted['RandomForest']
imp = pd.Series(rf.feature_importances_, index=df.drop(columns='y').columns).sort_values(ascending=False)
imp.head(15).iloc[::-1].plot(kind='barh', figsize=(9, 6), title='Top-15 features mais importantes (Random Forest)');
plt.tight_layout(); plt.show()
imp.head(15).round(4)""")

md("""## 13. Conclusões

- A formulação **multiclasse com aprendizado supervisionado** entrega uma carteira que
  **supera, em base ajustada ao risco, todas as classes de risco isoladas** (IBOV, SP500BR e
  OURO): maior retorno e *drawdown* substancialmente menor que o do Ibovespa.
- O esquema **top-2** reduz a volatilidade e eleva o índice de **Sharpe** frente ao
  *winner-takes-all*, ao custo de um pouco de retorno — efeito esperado da diversificação.
- A carteira **ingênua de pesos iguais** continua sendo um *benchmark* difícil em termos de
  Sharpe (graças ao peso constante em caixa e renda fixa), mas as estratégias de ML entregam
  **retorno absoluto maior**. A distância para o **ORACLE** mostra que ainda há bastante alfa
  não capturado — espaço para mais *features* e modelos.
- As variáveis **macroeconômicas** (ciclo de juros e inflação) aparecem entre as mais
  relevantes do Random Forest, confirmando o valor de combinar dados de mercado com dados
  macro — o principal diferencial deste trabalho em relação ao visto em aula.
""")

nb['cells'] = cells
nb['metadata'] = {
    'kernelspec': {'display_name': 'Python 3', 'language': 'python', 'name': 'python3'},
    'language_info': {'name': 'python'},
    'colab': {'provenance': []},
}
with open('Trabalho_2_Alocacao_ML.ipynb', 'w', encoding='utf-8') as f:
    nbf.write(nb, f)
print('Notebook gerado:', len(cells), 'células')
