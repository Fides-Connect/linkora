"""
Download bundled ML models into ai-assistant/models/.

Run once locally before committing, and after `git lfs pull` on a fresh clone:

    python scripts/download_models.py

The script stores each model under:
    models/<org>/<model-name>/

Large files (*.safetensors, *.bin, *.pt) are tracked by Git LFS.
Small config/tokenizer files are stored in plain git.
"""
from pathlib import Path
import sys

try:
    from huggingface_hub import snapshot_download
except ImportError:
    sys.exit("huggingface_hub not installed. Run: pip install huggingface-hub")

MODELS_DIR = Path(__file__).parent.parent / "models"

MODELS = [
    {
        "repo_id": "cross-encoder/ms-marco-MiniLM-L-6-v2",
        "local_dir": MODELS_DIR / "cross-encoder" / "ms-marco-MiniLM-L-6-v2",
        # Only download the files we actually need; skip README and git blobs.
        "allow_patterns": [
            "config.json",
            "model.safetensors",
            "tokenizer.json",
            "tokenizer_config.json",
            "special_tokens_map.json",
            "vocab.txt",
        ],
    },
]


def main() -> None:
    for m in MODELS:
        dest: Path = m["local_dir"]
        print(f"Downloading {m['repo_id']} → {dest} …")
        snapshot_download(
            repo_id=m["repo_id"],
            local_dir=str(dest),
            allow_patterns=m.get("allow_patterns"),
        )
        print(f"  ✓ {sum(1 for _ in dest.rglob('*') if _.is_file())} files saved to {dest}")

    print("\nAll models downloaded successfully.")
    print("Next step: git add ai-assistant/models && git commit -m 'feat: bundle cross-encoder model'")


if __name__ == "__main__":
    main()
