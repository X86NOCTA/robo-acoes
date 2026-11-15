#!/bin/bash
# =============================================================
#  Instala (ou atualiza) o Robô de Ações no Ubuntu.
#
#  Jeito mais fácil (baixa tudo do GitHub sozinho):
#    wget -qO- https://raw.githubusercontent.com/__REPO__/main/instalar.sh | bash
#
#  Ou, de dentro da pasta do robô:
#    bash instalar.sh
# =============================================================
set -e
REPO="${ROBO_REPO:-__REPO__}"
DESTINO="$HOME/robo-acoes"
ORIGEM="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" 2>/dev/null && pwd || echo "")"

echo ""
echo "🤖 Instalando o Robô de Ações…"

# 1) Python 3 (já vem no Ubuntu; se faltar, instala)
if ! command -v python3 >/dev/null 2>&1; then
  echo "Instalando o Python 3 (pode pedir a sua senha do Ubuntu)…"
  sudo apt-get update -qq && sudo apt-get install -y python3
fi

# 2) Arquivos do robô: usa a pasta atual ou baixa do GitHub
if [ -n "$ORIGEM" ] && [ -f "$ORIGEM/robo.py" ] && [ -f "$ORIGEM/pagina.html" ]; then
  PASTA="$ORIGEM"
  echo "Usando os arquivos de: $PASTA"
else
  if [ "$REPO" = "__REPO__" ]; then
    echo "Erro: este instalador ainda não sabe de qual GitHub baixar."; exit 1
  fi
  echo "Baixando a versão mais nova do GitHub ($REPO)…"
  python3 - "$REPO" "$DESTINO" <<'PY'
import io, os, sys, urllib.request, zipfile
repo, destino = sys.argv[1], sys.argv[2]
url = f"https://github.com/{repo}/archive/refs/heads/main.zip"
dados = urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "robo-acoes"}), timeout=60).read()
z = zipfile.ZipFile(io.BytesIO(dados))
os.makedirs(destino, exist_ok=True)
for nome in z.namelist():
    partes = nome.split("/", 1)
    if len(partes) < 2 or not partes[1] or nome.endswith("/") or ".." in nome:
        continue
    alvo = os.path.join(destino, partes[1])
    if os.path.basename(alvo) in ("config.json", "acoes.txt"):
        continue  # nunca apaga as suas configurações
    os.makedirs(os.path.dirname(alvo), exist_ok=True)
    with open(alvo, "wb") as f:
        f.write(z.read(nome))
print("Arquivos salvos em", destino)
PY
  PASTA="$DESTINO"
fi
chmod +x "$PASTA/robo.py" "$PASTA/instalar.sh" 2>/dev/null || true
mkdir -p "$HOME/.robo-acoes" "$HOME/.local/share/applications"

# 3) Atalho no menu de aplicativos e na Área de Trabalho
ATALHO="$HOME/.local/share/applications/robo-acoes.desktop"
cat > "$ATALHO" <<DESK
[Desktop Entry]
Type=Application
Name=Robô de Ações
Comment=Sinais diários de compra e venda e minha carteira
Exec=bash -c 'python3 "$PASTA/robo.py" >> "$HOME/.robo-acoes/log.txt" 2>&1'
Icon=utilities-system-monitor
Terminal=false
Categories=Office;Finance;
DESK
chmod +x "$ATALHO"
for D in "$HOME/Área de Trabalho" "$HOME/Desktop" "$(xdg-user-dir DESKTOP 2>/dev/null)"; do
  if [ -n "$D" ] && [ -d "$D" ]; then
    cp "$ATALHO" "$D/robo-acoes.desktop"; chmod +x "$D/robo-acoes.desktop"
    gio set "$D/robo-acoes.desktop" metadata::trusted true 2>/dev/null || true
  fi
done

# 4) Fecha a versão antiga (se estiver aberta) e abre o robô
pkill -f "robo-acoes/robo.py" 2>/dev/null || true
sleep 1
nohup python3 "$PASTA/robo.py" >> "$HOME/.robo-acoes/log.txt" 2>&1 &

echo ""
echo "✅ Pronto! O robô vai abrir no navegador em alguns segundos."
echo "   Nas próximas vezes, procure \"Robô de Ações\" no menu de aplicativos"
echo "   (aperte a tecla Windows/Super e digite: robô)."
echo ""
