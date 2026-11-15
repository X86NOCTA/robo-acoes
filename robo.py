#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
HORUS (antigo Robô de Ações) — sinais diários de compra e venda (swing trade).

Como funciona, em poucas palavras:
  1. Baixa o histórico diário (5 anos) de cada ação da lista acoes.txt.
  2. Para cada ação, testa várias regras simples de compra e venda.
     Escolhe a melhor usando os 70% mais antigos dos dados e confere
     se ela também funcionou nos 30% mais recentes (que ela "não viu").
  3. Só usa as ações em que alguma regra passou nesse teste.
  4. Mostra no navegador o que COMPRAR, VENDER e MANTER amanhã.

Só usa o que já vem no Python do Ubuntu. Não precisa instalar nada.
Rodar:  python3 robo.py
"""
import json, math, os, sys, threading, time, urllib.request, urllib.parse, webbrowser
from datetime import datetime, timedelta, timezone
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler

PASTA = os.path.dirname(os.path.abspath(__file__))
DADOS = os.path.join(os.path.expanduser("~"), ".robo-acoes")
os.makedirs(os.path.join(DADOS, "cache"), exist_ok=True)
PORTA = 8765
VERSAO = "1.3.0"
QTD_LISTA = 30            # quantas ações entram na lista quando você clica em "Atualizar lista"
DIAS_LISTA_VELHA = 30     # depois disso o robô avisa que a lista está velha
ARQUIVOS_DO_ROBO = {"robo.py", "pagina.html", "versao.json", "LEIA-ME.txt", "instalar.sh", "README.md"}
# Repositório no GitHub de onde o botão "Atualizar o robô" busca versões novas (ex.: "seuusuario/robo-acoes").
# Pode ser trocado em config.json, no campo "github_repo".
GITHUB_REPO = "X86NOCTA/robo-acoes"

try:
    from zoneinfo import ZoneInfo
    SP = ZoneInfo("America/Sao_Paulo")
except Exception:
    SP = timezone(timedelta(hours=-3))

def agora():
    return datetime.now(SP)

# ---------------------------------------------------------------- config
CONFIG_PADRAO = {"capital": 10000, "risco_pct": 1.0, "custo_pct": 0.10, "brapi_token": "", "url_atualizacao": "", "github_repo": ""}

def ler_config():
    cfg = dict(CONFIG_PADRAO)
    p = os.path.join(PASTA, "config.json")
    try:
        with open(p, encoding="utf-8") as f:
            cfg.update(json.load(f))
    except Exception:
        pass
    return cfg

def salvar_config(cfg):
    with open(os.path.join(PASTA, "config.json"), "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)

LISTA_PADRAO = ("PETR4 VALE3 ITUB4 BBDC4 BBAS3 B3SA3 ABEV3 WEGE3 RENT3 PRIO3 SUZB3 ITSA4 BPAC11 RDOR3 "
                "EQTL3 RADL3 GGBR4 LREN3 VIVT3 CMIG4 SBSP3 UGPA3 TOTS3 KLBN11 CSNA3 BBSE3 VBBR3 ENEV3 "
                "TIMS3 EGIE3 HYPE3 CPFE3 MGLU3").split()

# Ações candidatas para o botão "Atualizar lista". O robô baixa todas, mede quanto
# dinheiro cada uma movimenta por dia e fica com as mais negociadas.
# Códigos que mudaram de nome ou deixaram de existir são ignorados sozinhos.
CANDIDATAS = sorted(set((
    "PETR4 PETR3 VALE3 ITUB4 BBDC4 BBDC3 BBAS3 B3SA3 ABEV3 WEGE3 RENT3 PRIO3 SUZB3 ITSA4 BPAC11 "
    "RDOR3 EQTL3 RADL3 GGBR4 GOAU4 LREN3 VIVT3 CMIG4 SBSP3 UGPA3 TOTS3 KLBN11 CSNA3 BBSE3 VBBR3 "
    "ENEV3 TIMS3 EGIE3 HYPE3 CPFE3 MGLU3 AZZA3 ASAI3 CSAN3 CYRE3 MRVE3 EZTC3 DIRR3 CURY3 BRAV3 "
    "RECV3 CMIN3 USIM5 BRAP4 SANB11 BRKM5 RAIL3 MOTV3 CCRO3 ELET3 ELET6 AXIA3 EMBR3 EMBJ3 MBRF3 "
    "MRFG3 BEEF3 NATU3 SMTO3 SLCE3 ALOS3 MULT3 IGTI11 STBP3 POMO4 FLRY3 ODPV3 RAIZ4 COGN3 YDUQ3 "
    "SMFT3 VAMO3 CPLE3 CPLE6 SAPR11 TAEE11 ALUP11 ISAE4 AURE3 CXSE3 IRBR3 PSSA3 BPAN4 ABCB4 "
    "BRSR6 INTB3 LWSA3 CASH3 PCAR3 VIVA3 TEND3 KEPL3 RANI3 UNIP6 TUPY3 LEVE3 ONCO3 SIMH3 GMAT3"
).split()))

def ler_acoes():
    p = os.path.join(PASTA, "acoes.txt")
    out = []
    try:
        with open(p, encoding="utf-8") as f:
            for linha in f:
                t = linha.split("#")[0].strip().upper()
                if t and t not in out:
                    out.append(t)
    except FileNotFoundError:
        pass
    return out or list(LISTA_PADRAO)

def ler_json(caminho, padrao=None):
    try:
        with open(caminho, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return padrao

def versao_tupla(v):
    try:
        return tuple(int(x) for x in str(v).strip().lstrip("vV").split("."))
    except Exception:
        return (0,)

def info_versao():
    v = ler_json(os.path.join(PASTA, "versao.json"), {}) or {}
    v["versao"] = VERSAO
    return v

def info_lista():
    i = ler_json(os.path.join(DADOS, "lista_info.json"))
    if not i:
        return {"data": None, "qtd": len(ler_acoes()), "velha": True}
    try:
        dias = (agora().date() - datetime.strptime(i["data"], "%Y-%m-%d").date()).days
    except Exception:
        dias = 999
    i["dias"] = dias
    i["velha"] = dias > DIAS_LISTA_VELHA
    return i

# ---------------------------------------------------------------- download
UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130 Safari/537.36"}

def _get_json(url, headers=None, timeout=20):
    req = urllib.request.Request(url, headers={**UA, **(headers or {})})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))

# --- Yahoo Finance: usa cookie + "crumb" como um navegador, vai devagar e tenta de novo se for bloqueado
import http.cookiejar, urllib.error
_YJAR = http.cookiejar.CookieJar()
_YOPEN = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(_YJAR))
_YLOCK = threading.Lock()
_Y = {"crumb": None, "ultimo": 0.0}
UA_NAV = {**UA, "Accept": "application/json,text/plain,*/*", "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
          "Referer": "https://finance.yahoo.com/"}

def _yahoo_abrir(url, timeout=20):
    with _YLOCK:                               # no máximo ~3 pedidos por segundo
        espera = 0.35 - (time.time() - _Y["ultimo"])
        if espera > 0:
            time.sleep(espera)
        _Y["ultimo"] = time.time()
    req = urllib.request.Request(url, headers=UA_NAV)
    with _YOPEN.open(req, timeout=timeout) as r:
        return r.read()

def _yahoo_crumb(forcar=False):
    if _Y["crumb"] and not forcar:
        return _Y["crumb"]
    for u in ("https://fc.yahoo.com", "https://finance.yahoo.com/"):
        try:
            _yahoo_abrir(u)
        except Exception:
            pass                                # fc.yahoo.com responde 404, mas deixa o cookie
    for host in ("query1", "query2"):
        try:
            c = _yahoo_abrir(f"https://{host}.finance.yahoo.com/v1/test/getcrumb").decode().strip()
            if c and "<" not in c and len(c) < 50:
                _Y["crumb"] = c
                return c
        except Exception:
            pass
    return None

def _yahoo_json(caminho):
    """Tenta query1 e query2, com e sem crumb, e espera um pouco se o Yahoo pedir calma (erro 429)."""
    ultimo_erro = None
    for tentativa in range(4):
        for host in ("query1", "query2"):
            url = f"https://{host}.finance.yahoo.com{caminho}"
            if _Y["crumb"]:
                url += "&crumb=" + urllib.parse.quote(_Y["crumb"])
            try:
                return json.loads(_yahoo_abrir(url).decode("utf-8"))
            except urllib.error.HTTPError as e:
                ultimo_erro = e
                if e.code == 404:
                    raise RuntimeError("código não encontrado no Yahoo")
                if e.code in (401, 403):
                    _yahoo_crumb(forcar=True)
                elif e.code == 429:
                    time.sleep(2 * (tentativa + 1))
            except Exception as e:
                ultimo_erro = e
        time.sleep(1 + tentativa)
    if isinstance(ultimo_erro, urllib.error.HTTPError):
        raise RuntimeError(f"Yahoo recusou (erro {ultimo_erro.code})")
    raise RuntimeError(f"sem conexão com o Yahoo ({ultimo_erro})")

def baixar_yahoo(ticker):
    j = _yahoo_json(f"/v8/finance/chart/{urllib.parse.quote(ticker)}.SA?range=5y&interval=1d&events=split")
    if not j.get("chart", {}).get("result"):
        raise RuntimeError("código não encontrado no Yahoo")
    res = j["chart"]["result"][0]
    ts = res.get("timestamp") or []
    q = res["indicators"]["quote"][0]
    adj = (res["indicators"].get("adjclose") or [{}])[0].get("adjclose")
    barras = []
    for i, t in enumerate(ts):
        o, h, l, c, v = q["open"][i], q["high"][i], q["low"][i], q["close"][i], q["volume"][i]
        if None in (o, h, l, c) or c <= 0:
            continue
        f = (adj[i] / c) if adj and adj[i] else 1.0   # ajusta desdobramentos/dividendos
        d = datetime.fromtimestamp(t, SP).strftime("%Y-%m-%d")
        barras.append({"d": d, "o": o * f, "h": h * f, "l": l * f, "c": c * f, "v": v or 0})
    return barras

def diagnostico():
    """python3 robo.py --diagnostico  → testa a conexão com as fontes de cotação."""
    print(f"HORUS {VERSAO} — teste de conexão\n")
    def teste(nome, fn):
        t = time.time()
        try:
            r = fn()
            print(f"  OK   {nome}  ({time.time()-t:.1f}s) {r}")
        except urllib.error.HTTPError as e:
            print(f"  ERRO {nome}: HTTP {e.code} {e.reason}")
        except Exception as e:
            print(f"  ERRO {nome}: {e}")
    teste("internet (google.com)", lambda: _yahoo_abrir("https://www.google.com", 10) and "")
    teste("Yahoo direto, sem cookie", lambda: len(json.loads(urllib.request.urlopen(urllib.request.Request(
        "https://query1.finance.yahoo.com/v8/finance/chart/PETR4.SA?range=5d&interval=1d", headers=UA), timeout=20).read())["chart"]["result"][0]["timestamp"]) and "")
    teste("Yahoo cookie/crumb", lambda: "crumb obtido" if _yahoo_crumb(True) else "sem crumb (pode funcionar mesmo assim)")
    teste("Yahoo PETR4 (5 anos)", lambda: f"{len(baixar_yahoo('PETR4'))} dias de histórico")
    teste("Yahoo VALE3 (5 anos)", lambda: f"{len(baixar_yahoo('VALE3'))} dias de histórico")
    teste("brapi PETR4", lambda: f"{len(baixar_brapi('PETR4', ler_config().get('brapi_token','')))} dias")
    print("\nCopie tudo acima e mande para o Claude se algo deu ERRO.")

def baixar_brapi(ticker, token):
    url = f"https://brapi.dev/api/quote/{urllib.parse.quote(ticker)}?range=5y&interval=1d"
    if token:
        url += "&token=" + urllib.parse.quote(token)
    j = _get_json(url)
    hist = j["results"][0].get("historicalDataPrice") or []
    barras = []
    for x in hist:
        if None in (x.get("open"), x.get("high"), x.get("low"), x.get("close")):
            continue
        d = datetime.fromtimestamp(x["date"], SP).strftime("%Y-%m-%d")
        barras.append({"d": d, "o": x["open"], "h": x["high"], "l": x["low"], "c": x["close"], "v": x.get("volume") or 0})
    barras.sort(key=lambda b: b["d"])
    return barras

def baixar(ticker, cfg):
    """Baixa com cache de 1 dia. Tenta Yahoo; se falhar, tenta brapi."""
    hoje = agora().strftime("%Y-%m-%d")
    cache = os.path.join(DADOS, "cache", f"{ticker}.json")
    try:
        with open(cache, encoding="utf-8") as f:
            c = json.load(f)
        # cache vale se foi baixado hoje depois das 18h30 (pregão fechado) ou fora de dia útil
        if c.get("baixado_em_dia") == hoje and c.get("depois_fechamento"):
            return c["barras"], c.get("fonte", "cache")
    except Exception:
        pass
    erros = []
    for nome, fn in (("Yahoo Finance", lambda: baixar_yahoo(ticker)),
                     ("brapi", lambda: baixar_brapi(ticker, cfg.get("brapi_token", "")))):
        try:
            b = fn()
            if len(b) >= 200:
                agora_ = agora()
                with open(cache, "w", encoding="utf-8") as f:
                    json.dump({"baixado_em_dia": hoje, "fonte": nome,
                               "depois_fechamento": agora_.hour * 60 + agora_.minute >= 18 * 60 + 30 or agora_.weekday() >= 5,
                               "barras": b}, f)
                return b, nome
            erros.append(f"{nome}: poucos dados")
        except Exception as e:
            erros.append(f"{nome}: " + ("código não encontrado" if isinstance(e, (IndexError, KeyError, TypeError)) else str(e)))
    raise RuntimeError("; ".join(erros))

# ---------------------------------------------------------------- indicadores
def ema(a, p):
    k, o, e = 2 / (p + 1), [], a[0]
    for i, x in enumerate(a):
        e = x if i == 0 else x * k + e * (1 - k)
        o.append(e)
    return o

def sma_sd(a, p):
    m, sd, s, s2 = [math.nan] * len(a), [math.nan] * len(a), 0.0, 0.0
    for i, x in enumerate(a):
        s += x; s2 += x * x
        if i >= p:
            s -= a[i - p]; s2 -= a[i - p] ** 2
        if i >= p - 1:
            mu = s / p
            m[i] = mu; sd[i] = math.sqrt(max(0.0, s2 / p - mu * mu))
    return m, sd

def rsi(c, p):
    o, g, l = [50.0] * len(c), 0.0, 0.0
    for i in range(1, len(c)):
        d = c[i] - c[i - 1]
        up, dn = max(d, 0), max(-d, 0)
        if i <= p:
            g += up / p; l += dn / p
        else:
            g = (g * (p - 1) + up) / p; l = (l * (p - 1) + dn) / p
        if i >= p:
            o[i] = 100.0 if l == 0 else 100 - 100 / (1 + g / l)
    return o

def atr(H, L, C, p=14):
    o, a = [], H[0] - L[0]
    for i in range(len(C)):
        tr = H[i] - L[i] if i == 0 else max(H[i] - L[i], abs(H[i] - C[i - 1]), abs(L[i] - C[i - 1]))
        a = (a * i + tr) / (i + 1) if i < p else (a * (p - 1) + tr) / p
        o.append(a)
    return o

def maxima_anterior(a, p):
    return [math.nan if i < p else max(a[i - p:i]) for i in range(len(a))]

def minima_anterior(a, p):
    return [math.nan if i < p else min(a[i - p:i]) for i in range(len(a))]

# ---------------------------------------------------------------- regras (só compra)
# Cada regra devolve, para cada dia, 1 = "quero estar comprado" ou 0 = "quero estar fora".
def regra_tendencia(D, p):
    f, s = D.cache("e%d" % p["r"], lambda: ema(D.C, p["r"])), D.cache("e%d" % p["l"], lambda: ema(D.C, p["l"]))
    return [1 if i >= p["l"] and f[i] > s[i] else 0 for i in range(D.n)]

def regra_rompimento(D, p):
    hi = D.cache("hh%d" % p["n"], lambda: maxima_anterior(D.H, p["n"]))
    lo = D.cache("ll%d" % p["m"], lambda: minima_anterior(D.L, p["m"]))
    t, st = [0] * D.n, 0
    for i in range(D.n):
        if st == 0 and D.C[i] > hi[i]:
            st = 1
        elif st == 1 and D.C[i] < lo[i]:
            st = 0
        t[i] = st
    return t

def regra_queda_forte(D, p):
    r = D.cache("r%d" % p["p"], lambda: rsi(D.C, p["p"]))
    t, st = [0] * D.n, 0
    for i in range(p["p"], D.n):
        if st == 0 and r[i] < p["lim"]:
            st = 1
        elif st == 1 and r[i] > 50:
            st = 0
        t[i] = st
    return t

def regra_abaixo_media(D, p):
    m, sd = D.cache("b%d" % p["p"], lambda: sma_sd(D.C, p["p"]))
    t, st = [0] * D.n, 0
    for i in range(p["p"], D.n):
        if st == 0 and D.C[i] < m[i] - p["k"] * sd[i]:
            st = 1
        elif st == 1 and D.C[i] >= m[i]:
            st = 0
        t[i] = st
    return t

def grade(**kw):
    out = [{}]
    for k, vs in kw.items():
        out = [{**g, k: v} for g in out for v in vs]
    return out

REGRAS = {
    "tendencia": {
        "nome": "Seguir a tendência de alta",
        "explica": lambda p: f"Compra quando a média dos últimos {p['r']} dias passa acima da média dos últimos {p['l']} dias (sinal de que o preço começou a subir). Vende quando ela volta para baixo.",
        "fn": regra_tendencia,
        "grade": [g for g in grade(r=[5, 10, 20], l=[20, 50, 100]) if g["r"] < g["l"]],
    },
    "rompimento": {
        "nome": "Rompimento de máxima",
        "explica": lambda p: f"Compra quando o preço fecha acima do maior preço dos últimos {p['n']} dias. Vende quando fecha abaixo do menor preço dos últimos {p['m']} dias.",
        "fn": regra_rompimento,
        "grade": grade(n=[10, 20, 40], m=[5, 10, 20]),
    },
    "queda_forte": {
        "nome": "Repique depois de queda forte",
        "explica": lambda p: f"Compra depois de uma sequência de quedas fortes (indicador IFR de {p['p']} dias abaixo de {p['lim']}) apostando no repique. Vende quando o preço se recupera.",
        "fn": regra_queda_forte,
        "grade": grade(p=[2, 3, 5, 14], lim=[10, 20, 30]),
    },
    "abaixo_media": {
        "nome": "Preço muito abaixo do normal",
        "explica": lambda p: f"Compra quando o preço cai bem abaixo da média dos últimos {p['p']} dias e vende quando ele volta para a média.",
        "fn": regra_abaixo_media,
        "grade": grade(p=[10, 20, 40], k=[1.5, 2.0, 2.5]),
    },
}
STOPS = [2.0, 3.0]          # proteção sempre ligada: 2 ou 3 vezes a oscilação média diária
MIN_TREINO, MIN_TESTE, ROBUSTEZ_MIN = 12, 4, 0.25

class Dados:
    def __init__(self, barras):
        self.b = barras
        self.n = len(barras)
        self.O = [x["o"] for x in barras]; self.H = [x["h"] for x in barras]
        self.L = [x["l"] for x in barras]; self.C = [x["c"] for x in barras]
        self.V = [x["v"] for x in barras]
        self.A = atr(self.H, self.L, self.C, 14)
        self._c = {}
    def cache(self, k, f):
        if k not in self._c:
            self._c[k] = f()
        return self._c[k]

def simular(D, t, stop_mult, custo):
    """Sinal no fechamento do dia i-1, execução na abertura do dia i. Resultado em fração (0.01 = 1%)."""
    ops, pos, en, ei, stop, bloqueado = [], 0, 0.0, 0, 0.0, False
    O, H, L, C, A = D.O, D.H, D.L, D.C, D.A
    for i in range(1, D.n):
        quer = t[i - 1]
        if bloqueado and quer == 0:
            bloqueado = False
        if bloqueado:
            quer = 0
        if quer != pos:
            if pos:
                ops.append({"ei": ei, "xi": i, "en": en, "ex": O[i], "r": O[i] / en - 1 - custo, "motivo": "sinal"})
                pos = 0
            if quer:
                pos, en, ei = 1, O[i], i
                stop = en - stop_mult * A[i - 1]
        if pos and L[i] <= stop:
            px = min(stop, O[i])
            ops.append({"ei": ei, "xi": i, "en": en, "ex": px, "r": px / en - 1 - custo, "motivo": "proteção"})
            pos, bloqueado = 0, True
    aberta = {"en": en, "ei": ei, "stop": stop} if pos else None
    return ops, aberta

def estat(ops):
    n = len(ops); w = sum(1 for x in ops if x["r"] > 0)
    eq = pk = dd = 0.0
    gw = sum(x["r"] for x in ops if x["r"] > 0); gl = -sum(x["r"] for x in ops if x["r"] <= 0)
    for x in ops:
        eq += x["r"]; pk = max(pk, eq); dd = max(dd, pk - eq)
    return {"n": n, "acertos": w, "total": eq, "media": eq / n if n else 0.0,
            "fator": (gw / gl) if gl else (99.0 if gw else 0.0), "queda_max": dd}

def analisar_acao(barras, custo):
    D = Dados(barras)
    corte = int(D.n * 0.7)
    melhores = []
    for chave, R in REGRAS.items():
        best, testadas, positivas = None, 0, 0
        for p in R["grade"]:
            t = R["fn"](D, p)
            for sm in STOPS:
                ops, aberta = simular(D, t, sm, custo)
                treino = estat([x for x in ops if x["ei"] < corte])
                teste = estat([x for x in ops if x["ei"] >= corte])
                testadas += 1
                if treino["total"] > 0:
                    positivas += 1
                if treino["n"] < MIN_TREINO:
                    nota = -1e9 + treino["total"]
                else:
                    nota = treino["total"] / max(treino["queda_max"], 0.02)
                if best is None or nota > best["nota"]:
                    best = {"regra": chave, "p": p, "stop": sm, "nota": nota, "treino": treino,
                            "teste": teste, "ops": ops, "aberta": aberta, "t": t}
        best["robustez"] = positivas / testadas
        tr, te = best["treino"], best["teste"]
        best["aprovada"] = (tr["n"] >= MIN_TREINO and tr["total"] > 0 and te["n"] >= MIN_TESTE
                            and te["total"] > 0 and te["fator"] > 1.1 and best["robustez"] >= ROBUSTEZ_MIN)
        melhores.append(best)
    aprovadas = [m for m in melhores if m["aprovada"]]
    if not aprovadas:
        return D, None, melhores
    escolhida = max(aprovadas, key=lambda m: m["teste"]["media"])
    return D, escolhida, melhores

# ---------------------------------------------------------------- sinal de amanhã
def sinal_de_hoje(D, m, cfg):
    t, n = m["t"], D.n
    ult = D.b[-1]
    c, a = D.C[-1], D.A[-1]
    capital, risco = float(cfg["capital"]), float(cfg["risco_pct"]) / 100
    ops = m["ops"]
    te = m["teste"]
    base = {
        "preco": c,
        "historico": {"ops": te["n"], "acertos": te["acertos"], "media_pct": te["media"] * 100,
                      "total_pct": te["total"] * 100},
    }
    # 1) bateu na proteção hoje
    if ops and ops[-1]["xi"] == n - 1 and ops[-1]["motivo"] == "proteção":
        return {**base, "sinal": "VENDER", "motivo": f"O preço caiu até a proteção (R$ {ops[-1]['ex']:.2f}). Se você ainda tem a ação, venda na abertura."}
    ab = m["aberta"]
    if ab and t[-1] == 0:
        r = c / ab["en"] - 1
        return {**base, "sinal": "VENDER", "motivo": "A regra mandou sair. Venda na abertura de amanhã.",
                "entrada": ab["en"], "resultado_pct": r * 100}
    if ab and t[-1] == 1:
        r = c / ab["en"] - 1
        return {**base, "sinal": "MANTER", "entrada": ab["en"], "stop": ab["stop"], "resultado_pct": r * 100,
                "desde": D.b[ab["ei"]]["d"]}
    if t[-1] == 1 and t[-2] == 0:
        stop = c - m["stop"] * a
        limite = c + 0.5 * a
        risco_por_acao = max(limite - stop, 0.01)
        qtd = int((capital * risco) / risco_por_acao)
        qtd = max(0, min(qtd, int(capital * 0.25 / limite)))   # no máximo 25% do dinheiro numa ação só
        return {**base, "sinal": "COMPRAR", "limite": limite, "stop": stop, "qtd": qtd,
                "valor": qtd * limite, "perda_max": qtd * (limite - stop)}
    return {**base, "sinal": "AGUARDAR"}

# ---------------------------------------------------------------- execução
# ---------------------------------------------------------------- minha carteira (cálculos)
"""
Minha carteira: guarda as compras e vendas que você registrou e calcula
preço médio, lucro, taxa de acerto e imposto estimado (regras de 2026).

Regras usadas (simplificadas — confira sempre com um contador):
- Operação comum (comprou num dia, vendeu em outro): 15% sobre o lucro do mês.
  Isento se o total VENDIDO em ações no mês for até R$ 20.000.
- Day trade (comprou e vendeu a mesma ação no mesmo dia): 20%, sem isenção.
- Prejuízo de meses anteriores é descontado do lucro (comum com comum, day trade com day trade).
- Imposto pago por DARF, código 6015, até o último dia útil do mês seguinte.
"""
import uuid

ISENCAO_MES = 20000.0
ALIQ_COMUM, ALIQ_DT = 0.15, 0.20
TAXA_B3_PADRAO = 0.0003      # estimativa da taxa da bolsa quando você não informa (≈0,03% do valor)

def normalizar(tk):
    tk = (tk or "").strip().upper().replace(".SA", "")
    # PETR4F (fracionário) é a mesma ação que PETR4
    if len(tk) >= 6 and tk.endswith("F") and tk[-2].isdigit():
        tk = tk[:-1]
    return tk

class Carteira:
    def __init__(self, pasta_dados):
        self.arq = os.path.join(pasta_dados, "operacoes.json")
        self.pasta = pasta_dados

    # ---------------- armazenamento
    def ler(self):
        try:
            with open(self.arq, encoding="utf-8") as f:
                ops = json.load(f)
            return ops if isinstance(ops, list) else []
        except Exception:
            return []

    def salvar(self, ops):
        tmp = self.arq + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(ops, f, ensure_ascii=False, indent=1)
        os.replace(tmp, self.arq)

    def validar_op(self, o):
        try:
            data = datetime.strptime(str(o["data"]), "%Y-%m-%d").strftime("%Y-%m-%d")
        except Exception:
            raise ValueError("Data inválida.")
        tipo = o.get("tipo")
        if tipo not in ("compra", "venda"):
            raise ValueError("Escolha compra ou venda.")
        acao = normalizar(o.get("acao"))
        if not (4 <= len(acao) <= 7) or not acao[:4].isalpha():
            raise ValueError("Código da ação inválido (exemplo: PETR4).")
        try:
            qtd = float(o.get("qtd"))
            preco = float(str(o.get("preco")).replace(",", "."))
        except Exception:
            raise ValueError("Quantidade e preço precisam ser números.")
        if qtd <= 0 or qtd != int(qtd):
            raise ValueError("A quantidade precisa ser um número inteiro maior que zero.")
        if preco <= 0:
            raise ValueError("O preço precisa ser maior que zero.")
        taxas = o.get("taxas")
        if taxas in (None, ""):
            taxas = None
        else:
            taxas = float(str(taxas).replace(",", "."))
            if taxas < 0:
                raise ValueError("Taxas não podem ser negativas.")
        return {"id": o.get("id") or uuid.uuid4().hex[:10], "seq": o.get("seq") or time.time(),
                "data": data, "tipo": tipo, "acao": acao, "qtd": int(qtd), "preco": round(preco, 4), "taxas": taxas}

    def adicionar(self, o):
        nova = self.validar_op(o)
        ops = self.ler() + [nova]
        self.calcular(ops, {}, estrito=True)   # recusa venda de ação que você não tinha
        self.salvar(ops)
        return nova

    def apagar(self, id_):
        ops = [o for o in self.ler() if o.get("id") != id_]
        self.calcular(ops, {}, estrito=True)
        self.salvar(ops)

    def importar(self, lista):
        if not isinstance(lista, list):
            raise ValueError("Arquivo inválido.")
        ops = [self.validar_op(o) for o in lista]
        self.calcular(ops, {}, estrito=True)
        if os.path.exists(self.arq):
            os.replace(self.arq, os.path.join(self.pasta, f"operacoes-antes-de-importar-{int(time.time())}.json"))
        self.salvar(ops)
        return len(ops)

    # ---------------- cálculos
    def calcular(self, ops, precos, estrito=False):
        ops = sorted(ops, key=lambda o: (o["data"], 0 if o["tipo"] == "compra" else 1, o.get("seq", 0)))
        pos, vendas, compras_dia, detalhadas = {}, [], set(), []
        for o in ops:
            valor = o["qtd"] * o["preco"]
            taxas = o["taxas"] if o.get("taxas") is not None else round(valor * TAXA_B3_PADRAO, 2)
            d = dict(o, valor=valor, taxas_usadas=taxas)
            if o["tipo"] == "compra":
                p = pos.setdefault(o["acao"], {"qtd": 0, "custo": 0.0, "desde": o["data"]})
                if p["qtd"] == 0:
                    p["desde"] = o["data"]
                p["qtd"] += o["qtd"]; p["custo"] += valor + taxas
                compras_dia.add((o["acao"], o["data"]))
            else:
                p = pos.get(o["acao"])
                tem = p["qtd"] if p else 0
                if o["qtd"] > tem:
                    if estrito:
                        raise ValueError(f"Em {datetime.strptime(o['data'], '%Y-%m-%d').strftime('%d/%m/%Y')} você tinha {tem} ações de {o['acao']} e registrou venda de {o['qtd']}. Registre a compra antes.")
                    continue
                pm = p["custo"] / p["qtd"]
                custo_saida = pm * o["qtd"]
                lucro = valor - taxas - custo_saida
                p["qtd"] -= o["qtd"]; p["custo"] -= custo_saida
                if p["qtd"] == 0:
                    del pos[o["acao"]]
                dt = (o["acao"], o["data"]) in compras_dia
                v = {"id": o["id"], "data": o["data"], "acao": o["acao"], "qtd": o["qtd"], "valor": valor,
                     "preco_medio": pm, "lucro": lucro, "pct": lucro / custo_saida * 100 if custo_saida else 0, "day_trade": dt}
                vendas.append(v)
                d.update(lucro=lucro, preco_medio=pm, day_trade=dt)
            detalhadas.append(d)

        # carteira atual
        posicoes, investido, valor_atual = [], 0.0, 0.0
        for tk, p in sorted(pos.items()):
            pm = p["custo"] / p["qtd"]
            px = precos.get(tk)
            va = px * p["qtd"] if px else None
            res = (va - p["custo"]) if va is not None else None
            posicoes.append({"acao": tk, "qtd": p["qtd"], "preco_medio": pm, "custo": p["custo"], "preco": px,
                             "valor": va, "resultado": res, "pct": (res / p["custo"] * 100) if res is not None else None,
                             "desde": p["desde"]})
            investido += p["custo"]
            valor_atual += va if va is not None else p["custo"]

        # impostos por mês
        meses, prej_c, prej_dt = {}, 0.0, 0.0
        for v in vendas:
            m = meses.setdefault(v["data"][:7], {"mes": v["data"][:7], "vendas_comuns": 0.0, "lucro_comum": 0.0,
                                                "lucro_dt": 0.0, "n": 0})
            m["n"] += 1
            if v["day_trade"]:
                m["lucro_dt"] += v["lucro"]
            else:
                m["vendas_comuns"] += v["valor"]; m["lucro_comum"] += v["lucro"]
        lista_meses = []
        for k in sorted(meses):
            m = meses[k]
            # operações comuns
            imp_c, situacao = 0.0, ("sem lucro" if m["vendas_comuns"] else "")
            if m["lucro_comum"] < 0:
                prej_c += -m["lucro_comum"]; situacao = "prejuízo (fica guardado para descontar depois)"
            elif m["lucro_comum"] > 0 and m["vendas_comuns"] <= ISENCAO_MES:
                situacao = "isento (vendas até R$ 20 mil)"
            elif m["lucro_comum"] > 0:
                base = max(0.0, m["lucro_comum"] - prej_c)
                prej_c = max(0.0, prej_c - m["lucro_comum"])
                imp_c = base * ALIQ_COMUM
                situacao = "paga 15%" if imp_c > 0 else "lucro coberto por prejuízo anterior"
            # day trade
            imp_dt = 0.0
            if m["lucro_dt"] < 0:
                prej_dt += -m["lucro_dt"]
            elif m["lucro_dt"] > 0:
                base = max(0.0, m["lucro_dt"] - prej_dt)
                prej_dt = max(0.0, prej_dt - m["lucro_dt"])
                imp_dt = base * ALIQ_DT
            if m["lucro_dt"] != 0:
                situacao += (" · " if situacao else "") + f"day trade: {'paga 20%' if imp_dt > 0 else 'sem imposto'}"
            y, mo = int(k[:4]), int(k[5:])
            prazo = f"{(mo % 12) + 1:02d}/{y + (1 if mo == 12 else 0)}"
            lista_meses.append({**m, "imposto": imp_c + imp_dt, "situacao": situacao,
                                "lucro_total": m["lucro_comum"] + m["lucro_dt"], "prazo": prazo})

        realizado = sum(v["lucro"] for v in vendas)
        impostos = sum(m["imposto"] for m in lista_meses)
        aberto = sum(p["resultado"] for p in posicoes if p["resultado"] is not None)
        ganhos = [v for v in vendas if v["lucro"] > 0]
        perdas = [v for v in vendas if v["lucro"] <= 0]
        mes_atual = datetime.now().strftime("%Y-%m")
        m_at = next((m for m in lista_meses if m["mes"] == mes_atual), None)

        # série para o gráfico: resultado realizado acumulado (já descontando imposto do mês)
        serie, acum = [], 0.0
        imposto_por_mes = {m["mes"]: m["imposto"] for m in lista_meses}
        ult_venda_mes = {}
        for v in vendas:
            ult_venda_mes[v["data"][:7]] = v["id"]
        for v in vendas:
            acum += v["lucro"]
            if ult_venda_mes.get(v["data"][:7]) == v["id"]:
                acum -= imposto_por_mes.get(v["data"][:7], 0.0)
            serie.append({"data": v["data"], "valor": acum, "acao": v["acao"], "lucro": v["lucro"]})

        return {
            "operacoes": list(reversed(detalhadas)),
            "posicoes": posicoes,
            "vendas": vendas,
            "meses": list(reversed(lista_meses)),
            "serie": serie,
            "resumo": {
                "investido": investido, "valor_atual": valor_atual, "aberto": aberto,
                "realizado": realizado, "impostos": impostos,
                "total": realizado - impostos + aberto,
                "n_vendas": len(vendas), "acertos": len(ganhos),
                "ganho_medio": sum(v["lucro"] for v in ganhos) / len(ganhos) if ganhos else 0,
                "perda_media": sum(v["lucro"] for v in perdas) / len(perdas) if perdas else 0,
                "vendas_mes": m_at["vendas_comuns"] if m_at else 0.0,
                "imposto_mes": m_at["imposto"] if m_at else 0.0,
                "lucro_mes": m_at["lucro_total"] if m_at else 0.0,
                "prejuizo_a_compensar": prej_c,
            },
        }

ESTADO = {"status": "parado", "tarefa": "", "progresso": 0, "total": 0, "atual": "", "resultado": None,
          "erro": None, "versao": VERSAO}
TRAVA = threading.Lock()
SRV = None
REINICIAR = False

def remover_candle_incompleto(barras):
    """Durante o pregão o último dia ainda não fechou. Usa só dias fechados."""
    h = agora()
    hoje = h.strftime("%Y-%m-%d")
    if barras and barras[-1]["d"] == hoje and h.weekday() < 5 and (h.hour * 60 + h.minute) < 18 * 60 + 30:
        return barras[:-1]
    return barras

def sem_negociacao_recente(barras):
    """Código que mudou de nome para de receber preços. Não usar dados velhos."""
    try:
        ult = datetime.strptime(barras[-1]["d"], "%Y-%m-%d").date()
        return (agora().date() - ult).days > 10
    except Exception:
        return True

def montar_lista(cfg):
    """Escolhe as QTD_LISTA ações que mais movimentaram dinheiro nos últimos 3 meses."""
    medidas, erros = [], {}
    ESTADO.update(total=len(CANDIDATAS), tarefa="lista")
    for k, tk in enumerate(CANDIDATAS):
        ESTADO.update(progresso=k, atual=tk)
        try:
            barras, _ = baixar(tk, cfg)
        except Exception as e:
            erros[tk] = str(e)
            if k >= 12 and len(erros) == k + 1:   # nada funcionou até agora: para e mostra o motivo
                break
            continue
        barras = remover_candle_incompleto(barras)
        if len(barras) < 300 or sem_negociacao_recente(barras):
            continue
        ult = barras[-60:]
        giro = sum(b["c"] * b["v"] for b in ult) / len(ult)   # R$ negociados por dia (aprox.)
        if barras[-1]["c"] >= 2 and giro > 0:
            medidas.append((giro, tk))
    if len(medidas) < 10:
        exemplo = next(iter(erros.items()), ("", "sem detalhes"))
        raise RuntimeError(f"Não consegui baixar as cotações (consegui {len(medidas)} de {len(CANDIDATAS)}). "
                           f"Motivo em {exemplo[0]}: {exemplo[1]}. "
                           "Tente de novo em alguns minutos. Se continuar, abra o Terminal, rode "
                           "python3 ~/robo-acoes/robo.py --diagnostico e mande o resultado para o Claude.")
    medidas.sort(reverse=True)
    escolhidas = [tk for _, tk in medidas[:QTD_LISTA]]
    p = os.path.join(PASTA, "acoes.txt")
    if os.path.exists(p):
        try:
            os.replace(p, os.path.join(DADOS, "acoes-anterior.txt"))
        except Exception:
            pass
    hoje = agora()
    with open(p, "w", encoding="utf-8") as f:
        f.write(f"# Lista montada pelo robô em {hoje.strftime('%d/%m/%Y')}: as {len(escolhidas)} ações mais negociadas.\n")
        f.write("# Você pode editar à mão. Clicar em 'Atualizar lista de ações' substitui esta lista.\n")
        for giro, tk in medidas[:QTD_LISTA]:
            f.write(f"{tk:<8} # cerca de R$ {giro/1e6:,.0f} milhões por dia\n".replace(",", "."))
    with open(os.path.join(DADOS, "lista_info.json"), "w", encoding="utf-8") as f:
        json.dump({"data": hoje.strftime("%Y-%m-%d"), "qtd": len(escolhidas), "acoes": escolhidas}, f)

def rodar(atualizar_lista=False):
    with TRAVA:
        if ESTADO["status"] == "rodando":
            return
        ESTADO.update(status="rodando", progresso=0, erro=None, tarefa="lista" if atualizar_lista else "sinais")
    try:
        cfg = ler_config()
        if atualizar_lista:
            montar_lista(cfg)
        acoes = ler_acoes()
        ESTADO.update(total=len(acoes), progresso=0, tarefa="sinais")
        custo = float(cfg["custo_pct"]) / 100
        itens, sem, falhas, fontes, ultima = [], [], [], set(), ""
        for k, tk in enumerate(acoes):
            ESTADO.update(progresso=k, atual=tk)
            try:
                barras, fonte = baixar(tk, cfg)
                fontes.add(fonte)
            except Exception as e:
                falhas.append({"acao": tk, "erro": str(e)[:200]})
                continue
            barras = remover_candle_incompleto(barras)
            if len(barras) < 300:
                falhas.append({"acao": tk, "erro": "histórico curto demais"})
                continue
            if sem_negociacao_recente(barras):
                falhas.append({"acao": tk, "erro": "sem preços recentes (o código pode ter mudado)"})
                continue
            D, m, todas = analisar_acao(barras, custo)
            ultima = max(ultima, barras[-1]["d"])
            if not m:
                sem.append(tk)
                continue
            s = sinal_de_hoje(D, m, cfg)
            R = REGRAS[m["regra"]]
            itens.append({"acao": tk, **s, "regra": R["nome"], "explica": R["explica"](m["p"]),
                          "stop_mult": m["stop"], "dia": barras[-1]["d"],
                          "ultimas": [{"en": x["en"], "ex": x["ex"], "r": x["r"] * 100,
                                       "de": D.b[x["ei"]]["d"], "ate": D.b[x["xi"]]["d"], "motivo": x["motivo"]}
                                      for x in m["ops"][-5:]][::-1]})
        if acoes and len(falhas) == len(acoes):
            raise RuntimeError(f"Não consegui baixar nenhuma cotação. Motivo em {falhas[0]['acao']}: {falhas[0]['erro']}. "
                               "Tente de novo em alguns minutos. Se continuar, abra o Terminal, rode "
                               "python3 ~/robo-acoes/robo.py --diagnostico e mande o resultado para o Claude.")
        ordem = {"COMPRAR": 0, "VENDER": 1, "MANTER": 2, "AGUARDAR": 3}
        itens.sort(key=lambda x: (ordem[x["sinal"]], -x["historico"]["media_pct"]))
        ESTADO["resultado"] = {"itens": itens, "sem_estrategia": sem, "falhas": falhas,
                               "fechamento": ultima, "gerado": agora().strftime("%d/%m/%Y %H:%M"),
                               "fontes": sorted(fontes), "config": cfg}
        ESTADO.update(status="pronto", progresso=len(acoes), atual="", tarefa="")
        with open(os.path.join(DADOS, "ultimo_resultado.json"), "w", encoding="utf-8") as f:
            json.dump(ESTADO["resultado"], f, ensure_ascii=False)
    except Exception as e:
        ESTADO.update(status="erro", erro=str(e), tarefa="")

def vigia():
    """Com o robô aberto, recalcula sozinho quando sai um fechamento novo (dias úteis, depois das 18h40)."""
    while True:
        time.sleep(600)
        try:
            h = agora()
            if h.weekday() >= 5 or h.hour * 60 + h.minute < 18 * 60 + 40 or ESTADO["status"] == "rodando":
                continue
            r = ESTADO.get("resultado") or {}
            if r.get("fechamento", "") < h.strftime("%Y-%m-%d"):
                rodar()
        except Exception:
            pass

# ---------------------------------------------------------------- atualização do próprio robô
def instalar_zip(dados):
    """Recebe o .zip de uma versão nova, confere e troca os arquivos do robô.
    Sua lista de ações (acoes.txt) e suas configurações (config.json) nunca são tocadas."""
    import zipfile, io, shutil
    try:
        z = zipfile.ZipFile(io.BytesIO(dados))
    except Exception:
        raise RuntimeError("Esse arquivo não é um .zip válido.")
    achados = {}
    for nome in z.namelist():
        if nome.endswith("/") or ".." in nome or nome.startswith("/"):
            continue
        base = nome.rsplit("/", 1)[-1]
        if base in ARQUIVOS_DO_ROBO:
            achados[base] = nome
    if not {"robo.py", "pagina.html", "versao.json"} <= set(achados):
        raise RuntimeError("Esse .zip não parece ser do Horus (faltam arquivos).")
    try:
        nova = json.loads(z.read(achados["versao.json"]).decode("utf-8"))
    except Exception:
        raise RuntimeError("O arquivo versao.json do .zip está com problema.")
    codigo = z.read(achados["robo.py"]).decode("utf-8")
    compile(codigo, "robo.py", "exec")   # recusa um robo.py quebrado antes de trocar qualquer coisa
    if versao_tupla(nova.get("versao")) < versao_tupla(VERSAO):
        raise RuntimeError(f"Esse .zip é da versão {nova.get('versao')}, mais antiga que a sua ({VERSAO}).")
    backup = os.path.join(DADOS, f"backup-{VERSAO}")
    os.makedirs(backup, exist_ok=True)
    for base in ARQUIVOS_DO_ROBO:
        src = os.path.join(PASTA, base)
        if os.path.exists(src):
            shutil.copy2(src, os.path.join(backup, base))
    for base, nome in achados.items():
        tmp = os.path.join(PASTA, base + ".novo")
        with open(tmp, "wb") as f:
            f.write(z.read(nome))
        os.replace(tmp, os.path.join(PASTA, base))
    os.chmod(os.path.join(PASTA, "robo.py"), 0o755)
    return nova

def reiniciar_em_breve():
    def _r():
        global REINICIAR
        time.sleep(1.5)
        REINICIAR = True
        SRV.shutdown()
    threading.Thread(target=_r, daemon=True).start()

def procurar_atualizacao():
    cfg = ler_config()
    repo = (cfg.get("github_repo") or GITHUB_REPO or "").strip().strip("/")
    url = (cfg.get("url_atualizacao") or "").strip()
    zip_url = None
    if repo and not url:
        url = f"https://raw.githubusercontent.com/{repo}/main/versao.json?t={int(time.time())}"
        zip_url = f"https://github.com/{repo}/archive/refs/heads/main.zip"
    if not url:
        return {"configurado": False}
    v = _get_json(url)
    return {"configurado": True, "versao": v.get("versao"), "novidades": v.get("novidades", []),
            "zip": v.get("zip") or zip_url, "nova": versao_tupla(v.get("versao")) > versao_tupla(VERSAO),
            "repo": repo}

# ---------------------------------------------------------------- minha carteira
CARTEIRA = Carteira(DADOS)

def preco_atual(tk, buscar=True):
    """Último fechamento da ação, usando o que o robô já baixou (ou baixando agora)."""
    c = ler_json(os.path.join(DADOS, "cache", f"{tk}.json"))
    if c and c.get("barras"):
        return c["barras"][-1]["c"], c["barras"][-1]["d"]
    if buscar:
        try:
            b, _ = baixar(tk, ler_config())
            return b[-1]["c"], b[-1]["d"]
        except Exception:
            pass
    return None, None

def dados_carteira():
    ops = CARTEIRA.ler()
    tickers = {o["acao"] for o in ops}
    precos, datas = {}, {}
    for tk in tickers:
        px, d = preco_atual(tk)
        if px:
            precos[tk], datas[tk] = px, d
    r = CARTEIRA.calcular(ops, precos)
    sinais = {i["acao"]: i for i in ((ESTADO.get("resultado") or {}).get("itens") or [])}
    for p in r["posicoes"]:
        s = sinais.get(p["acao"])
        p["sinal"] = s["sinal"] if s else None
        p["stop"] = s.get("stop") if s else None
        p["data_preco"] = datas.get(p["acao"])
    return r

# ---------------------------------------------------------------- servidor local
class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass
    def _send(self, code, body, ctype="application/json; charset=utf-8"):
        b = body if isinstance(body, bytes) else body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)
    def _json(self, obj, code=200):
        self._send(code, json.dumps(obj, ensure_ascii=False))
    def do_GET(self):
        if self.path in ("/", "/index.html"):
            with open(os.path.join(PASTA, "pagina.html"), "rb") as f:
                return self._send(200, f.read(), "text/html; charset=utf-8")
        if self.path.startswith("/api/estado"):
            return self._json({**ESTADO, "lista": info_lista(), "versao_info": info_versao()})
        if self.path.startswith("/api/carteira"):
            try:
                return self._json(dados_carteira())
            except Exception as e:
                return self._json({"erro": str(e)}, 500)
        if self.path.startswith("/api/operacoes/exportar"):
            corpo = json.dumps(CARTEIRA.ler(), ensure_ascii=False, indent=1).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Disposition", f'attachment; filename="minhas-operacoes-{agora().strftime("%Y-%m-%d")}.json"')
            self.send_header("Content-Length", str(len(corpo)))
            self.end_headers()
            self.wfile.write(corpo)
            return
        if self.path.startswith("/api/procurar-atualizacao"):
            try:
                return self._json(procurar_atualizacao())
            except Exception as e:
                return self._json({"configurado": True, "erro": str(e)})
        self._send(404, "{}")
    def do_POST(self):
        tam = int(self.headers.get("Content-Length") or 0)
        if tam > 20 * 1024 * 1024:
            return self._json({"ok": False, "erro": "Arquivo grande demais."}, 400)
        corpo = self.rfile.read(tam) if tam else b""
        if self.path in ("/api/atualizar", "/api/atualizar-lista"):
            try:
                novo = json.loads(corpo.decode("utf-8") or "{}")
                cfg = ler_config()
                for k in ("capital", "risco_pct"):
                    if k in novo:
                        cfg[k] = float(novo[k])
                salvar_config(cfg)
            except Exception:
                pass
            lista = self.path == "/api/atualizar-lista"
            threading.Thread(target=rodar, args=(lista,), daemon=True).start()
            return self._json({"ok": True})
        if self.path.startswith("/api/operacoes"):
            try:
                dados = json.loads(corpo.decode("utf-8") or "{}")
                if self.path == "/api/operacoes/nova":
                    CARTEIRA.adicionar(dados)
                elif self.path == "/api/operacoes/apagar":
                    CARTEIRA.apagar(dados.get("id"))
                elif self.path == "/api/operacoes/importar":
                    n = CARTEIRA.importar(dados)
                    return self._json({"ok": True, "n": n})
                else:
                    return self._send(404, "{}")
                return self._json({"ok": True})
            except ValueError as e:
                return self._json({"ok": False, "erro": str(e)}, 400)
            except Exception as e:
                return self._json({"ok": False, "erro": "Erro: " + str(e)}, 500)
        if self.path in ("/api/instalar-zip", "/api/instalar-remoto"):
            if ESTADO["status"] == "rodando":
                return self._json({"ok": False, "erro": "Espere a análise terminar e tente de novo."}, 409)
            try:
                if self.path == "/api/instalar-remoto":
                    info = procurar_atualizacao()
                    if not info.get("zip"):
                        raise RuntimeError("Não há atualização para baixar.")
                    req = urllib.request.Request(info["zip"], headers=UA)
                    with urllib.request.urlopen(req, timeout=60) as r:
                        corpo = r.read()
                nova = instalar_zip(corpo)
            except Exception as e:
                return self._json({"ok": False, "erro": str(e)}, 400)
            self._json({"ok": True, "versao": nova.get("versao"), "novidades": nova.get("novidades", [])})
            reiniciar_em_breve()
            return
        self._send(404, "{}")

def main():
    global SRV
    if "--diagnostico" in sys.argv:
        return diagnostico()
    url = f"http://127.0.0.1:{PORTA}/"
    try:
        SRV = ThreadingHTTPServer(("127.0.0.1", PORTA), Handler)
    except OSError:
        print("O Horus já está aberto. Abrindo o navegador…")
        webbrowser.open(url)
        return
    # mostra o último resultado salvo enquanto calcula o novo
    ESTADO["resultado"] = ler_json(os.path.join(DADOS, "ultimo_resultado.json"))
    threading.Thread(target=rodar, daemon=True).start()
    threading.Thread(target=vigia, daemon=True).start()
    print(f"HORUS {VERSAO} rodando em {url}")
    print("Deixe esta janela aberta enquanto usa. Para fechar, aperte Ctrl+C.")
    if "--sem-navegador" not in sys.argv:
        threading.Timer(1.0, lambda: webbrowser.open(url)).start()
    try:
        SRV.serve_forever()
    except KeyboardInterrupt:
        print("\nRobô fechado.")
        return
    SRV.server_close()
    if REINICIAR:
        print("Reiniciando com a versão nova…")
        os.execv(sys.executable, [sys.executable, os.path.join(PASTA, "robo.py"), "--sem-navegador"])

if __name__ == "__main__":
    main()
