
#!/usr/bin/env bash
set -euo pipefail

# Install system deps
sudo apt update
sudo apt install -y python3-venv python3-pip libatlas-base-dev curl

# Create app dir
sudo mkdir -p /opt/bathguard
sudo cp -r . /opt/bathguard/
cd /opt/bathguard

# Create venv with system site-packages so apt-provided libs (if any) are visible
python3 -m venv --system-site-packages venv
source venv/bin/activate
pip install --upgrade pip

# Core Python deps
pip install numpy opencv-python-headless requests pyyaml

# Try tflite-runtime wheel first; if not available, fall back to tensorflow (heavier)
if ! python - <<'PY'
try:
    import tflite_runtime
    print("tflite-runtime present")
except Exception:
    raise SystemExit(1)
PY
then
  echo "Installing tflite-runtime via pip..."
  pip install --only-binary=:all: tflite-runtime || {
    echo "tflite-runtime wheel not available; installing tensorflow-cpu (large)."
    pip install tensorflow-cpu
  }
fi

# Download model
./models/download_models.sh || true

echo "Installation complete. Configure Telegram secrets in /opt/bathguard/.env and edit config.yaml as needed."
echo "To run once: venv/bin/python -m src.main --config config.yaml"
