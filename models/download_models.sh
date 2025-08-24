
#!/usr/bin/env bash
set -euo pipefail
mkdir -p models
cd "$(dirname "$0")"/..
out="models/movenet_singlepose_lightning.tflite"
if [ -f "$out" ]; then
  echo "Model already exists: $out"
  exit 0
fi

echo "Attempting to download MoveNet SinglePose Lightning (TFLite) from TF Hub..."
# Note: TF Hub URLs occasionally change. If this fails, open the TF Hub MoveNet page and download manually.
# https://www.tensorflow.org/hub/tutorials/movenet  (find SinglePose Lightning TFLite)
# Direct links often look like: https://tfhub.dev/google/lite-model/movenet/singlepose/lightning/tflite/float16/4?lite-format=tflite
curl -L --fail -o "$out" "https://tfhub.dev/google/lite-model/movenet/singlepose/lightning/tflite/float16/4?lite-format=tflite" || {
  echo "Automatic download failed. Please visit the TF Hub MoveNet page and download the SinglePose Lightning TFLite model manually, then save it as: $out"
  exit 1
}
echo "Downloaded to $out"
