# Falcon

Local UI shadowing: capture → scrub → playbook + ontology YAML. **macOS** (Swift recorder) and **Windows** (UIA). Frames stay on device; only scrubbed text goes to the LLM.

---

## Install (utenti — senza uv/pip)

Scarica l’ultimo **`Falcon-macos-*.zip`** o **`Falcon-win64.zip`** dalla [pagina Releases](https://github.com/trybacked/falcon/releases) (tag `v*`), oppure build locale:

```bash
# macOS
bash scripts/build-release-macos.sh
# → dist/Falcon-macos-arm64.zip

# Windows (PowerShell)
./scripts/build-release-windows.ps1
# → dist/Falcon-win64.zip
```

Dopo lo unzip: **Install.command** (Mac) o **Install.ps1** (Windows), poi in un nuovo terminale:

```bash
falcon record --name demo
falcon analyze --session demo
export AI_GATEWAY_API_KEY=...
falcon distill --session demo
falcon report --session demo
```

Vedi `scripts/user-README.txt` nel pacchetto.

---

## Sviluppo (repo)

```bash
uv sync --group dev
make ci                    # ruff + mypy + pytest
uv run falcon --help
```

macOS recorder: `cd packages/platform-macos && swift build -c release`

| Comando | Ruolo |
|---------|--------|
| `record` | Cattura sessione |
| `check` | Valida manifest + trace |
| `ingest` | Normalizza JSONL recorder |
| `analyze` | Scrub, segmenti, `analysis.json` |
| `distill` | LLM → playbook + YAML |
| `report` | Stampa playbook |

Config: `config.toml.example` · env `FW_*` · `FW_DEBUG=1`

---

## Release (maintainer)

```bash
git tag v0.1.0
git push origin v0.1.0
```

GitHub Actions (`.github/workflows/release.yml`) builda Mac + Windows e allega gli zip alla Release.

---

## Architettura

- **Capture:** Swift `falcon-recorder` (macOS) · Python UIA (Windows)
- **Engine:** Python `falcon` (ingest, pipeline, distill)
- **Distribuzione:** PyInstaller bundle + binario Swift embedded (Mac)

Dettagli: [plan.md](plan.md)
