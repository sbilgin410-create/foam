#!/usr/bin/env bash
# Ubuntu üzerine bu programın çalışması için gerekli her şeyi kurar:
#   1) Python bağımlılıkları (bu depo içinde bir sanal ortam)
#   2) OpenFOAM (blockMesh / checkMesh / topoSet / buoyantSimpleFoam)
#
# Kullanım:
#   chmod +x scripts/install_ubuntu.sh
#   ./scripts/install_ubuntu.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "== Python bağımlılıkları kuruluyor =="
cd "$SCRIPT_DIR"
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

echo "== OpenFOAM kuruluyor (openfoam.org apt deposu) =="
if command -v blockMesh >/dev/null 2>&1; then
  echo "OpenFOAM zaten kurulu, atlanıyor."
else
  sudo apt-get update
  sudo apt-get install -y curl software-properties-common
  curl -s https://dl.openfoam.org/gpg.key | sudo apt-key add -
  sudo add-apt-repository -y http://dl.openfoam.org/ubuntu
  sudo apt-get update
  sudo apt-get install -y openfoam11 || sudo apt-get install -y openfoam10 || sudo apt-get install -y openfoam9
fi

OF_BASHRC=$(ls /opt/openfoam*/etc/bashrc 2>/dev/null | head -n1 || true)
if [ -n "$OF_BASHRC" ]; then
  echo ""
  echo "Kurulum tamamlandı."
  echo "Her yeni terminalde OpenFOAM ortamını yüklemek için:"
  echo "  source $OF_BASHRC"
  echo "Kalıcı yapmak için bunu ~/.bashrc dosyanıza ekleyebilirsiniz."
else
  echo "UYARI: OpenFOAM bashrc bulunamadı, kurulum başarısız olmuş olabilir."
fi

echo ""
echo "Web uygulamasını başlatmak için:"
echo "  source .venv/bin/activate && ./run.sh"
