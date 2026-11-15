#!/bin/bash
# Cria o atalho "Robô de Ações" no menu de aplicativos e na Área de Trabalho.
PASTA="$(cd "$(dirname "$0")" && pwd)"
if ! command -v python3 >/dev/null; then
  echo "Python 3 não encontrado. Rode: sudo apt install python3"; exit 1
fi
mkdir -p "$HOME/.local/share/applications" "$HOME/.robo-acoes"
ATALHO="$HOME/.local/share/applications/robo-acoes.desktop"
cat > "$ATALHO" <<DESK
[Desktop Entry]
Type=Application
Name=Robô de Ações
Comment=Sinais diários de compra e venda
Exec=bash -c 'python3 "$PASTA/robo.py" >> "$HOME/.robo-acoes/log.txt" 2>&1'
Icon=utilities-system-monitor
Terminal=false
Categories=Office;Finance;
DESK
chmod +x "$ATALHO" "$PASTA/robo.py"
for D in "$HOME/Área de Trabalho" "$HOME/Desktop"; do
  if [ -d "$D" ]; then
    cp "$ATALHO" "$D/robo-acoes.desktop"; chmod +x "$D/robo-acoes.desktop"
    gio set "$D/robo-acoes.desktop" metadata::trusted true 2>/dev/null
  fi
done
echo ""
echo "Pronto! Procure \"Robô de Ações\" no menu de aplicativos (tecla Super e digite \"robô\")."
echo "Abrindo o robô agora…"
nohup python3 "$PASTA/robo.py" >> "$HOME/.robo-acoes/log.txt" 2>&1 &
