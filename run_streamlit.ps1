Set-StrictMode -Version Latest

# Always run Streamlit using the repo's venv interpreter to avoid ModuleNotFoundError.
$python = Join-Path $PSScriptRoot ".venv-1\Scripts\python.exe"

if (-not (Test-Path $python)) {
  Write-Error "Venv Python not found at $python. Create/activate the venv first."
  exit 1
}

& $python -m streamlit run (Join-Path $PSScriptRoot "streamlit_app.py")
