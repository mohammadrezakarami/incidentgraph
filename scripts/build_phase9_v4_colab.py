"""Build the self-contained free-Colab notebook for Phase 9 v4."""

from __future__ import annotations

import json
from pathlib import Path

OUTPUT = Path("phase9_v4_colab.ipynb")


def source(text: str) -> list[str]:
    return [line + "\n" for line in text.strip("\n").splitlines()]


def markdown(text: str) -> dict[str, object]:
    return {"cell_type": "markdown", "metadata": {}, "source": source(text)}


def code(text: str) -> dict[str, object]:
    return {
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": source(text),
    }


cells = [
    markdown(
        """
# IncidentGraph Phase 9 v4 — ارزیابی تازه پس از تعمیر

این نوت‌بوک ارزیابی **تازه و seal‌شده**‌ی repair-3 را فقط روی GPU رایگان Colab
اجرا می‌کند. هیچ API پولی، Neo4j یا Docker لازم نیست. مدل فقط ترتیب دو بستهٔ
مشاهده را انتخاب می‌کند؛ تشخیص و citationها در کد trusted و freeze‌شده ساخته می‌شوند.

1. از `Runtime → Change runtime type` گزینهٔ **T4 GPU** را انتخاب کن.
2. سلول‌ها را دقیقاً به ترتیب اجرا کن.
3. در سلول اول فقط `incidentgraph-phase9-v4-colab.bundle` را آپلود کن.
4. بار اول `UPLOAD_V4_PROGRESS = False` بماند. فقط اگر session قطع شد، در اجرای
   بعدی آن را `True` کن و ZIP آخر را در سلول جداگانهٔ progress آپلود کن.
5. در پایان فقط فایل `phase9-v4-progress.zip` را برای Codex بفرست.

۱۲ shard داریم و هر shard ده job دارد. کل run فقط ۶۰ فراخوانی مدل محلی دارد؛
fixed workflow هیچ فراخوانی مدل ندارد.
"""
    ),
    code(
        """
# ruff: noqa: S105, S108, S603, S607
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
import zipfile
from pathlib import Path

from google.colab import files

SHARD_COUNT = 12
SHARDS_TO_RUN = list(range(12))
UPLOAD_V4_PROGRESS = False
assert all(0 <= item < SHARD_COUNT for item in SHARDS_TO_RUN)

gpu = subprocess.run(
    ['nvidia-smi', '--query-gpu=name,memory.total', '--format=csv,noheader'],
    capture_output=True, text=True,
)
assert gpu.returncode == 0, 'Select a free T4 GPU runtime before continuing.'
print('GPU:', gpu.stdout.strip())

print('Upload ONLY incidentgraph-phase9-v4-colab.bundle')
uploaded = files.upload()
bundle_items = [(name, payload) for name, payload in uploaded.items() if name.endswith('.bundle')]
assert len(bundle_items) == 1, 'Upload exactly one .bundle file.'
uploaded_name, uploaded_bytes = bundle_items[0]
bundle = Path('/content/incidentgraph-phase9-v4-upload.bundle')
bundle.write_bytes(uploaded_bytes)
expected_bundle_sha256 = 'c31bb3a80b83ae2482eedd8364d3cfd2f3a9f60931dd10f263f2ee2bccb2c03f'
actual_bundle_sha256 = hashlib.sha256(bundle.read_bytes()).hexdigest()
assert actual_bundle_sha256 == expected_bundle_sha256, (
    'Wrong bundle. Expected ' + expected_bundle_sha256 + ', received ' + actual_bundle_sha256
)
print('Bundle verified:', uploaded_name, actual_bundle_sha256)
output_dir = Path('/content/phase9-v4-output')
print('Selected shards:', SHARDS_TO_RUN, 'of', SHARD_COUNT)
"""
    ),
    code(
        """
if UPLOAD_V4_PROGRESS:
    print('Upload ONLY the latest phase9-v4-progress.zip')
    uploaded_progress = files.upload()
    zip_items = [
        (name, payload)
        for name, payload in uploaded_progress.items()
        if name.endswith('.zip')
    ]
    assert len(zip_items) == 1, 'Upload exactly one v4 progress ZIP.'
    uploaded_name, uploaded_bytes = zip_items[0]
    progress = Path('/content/phase9-v4-upload.zip')
    progress.write_bytes(uploaded_bytes)
    assert zipfile.is_zipfile(progress), 'Uploaded bytes are not a valid ZIP.'
    with zipfile.ZipFile(progress) as archive:
        names = archive.namelist()
        assert any(name.startswith('phase9-v4-output/') for name in names), (
            'This is not a Phase 9 v4 progress archive.'
        )
    if output_dir.exists():
        shutil.rmtree(output_dir)
    shutil.unpack_archive(progress, '/content')
    print('Restored:', uploaded_name, 'as', progress.name)
else:
    print('Fresh v4 run; no progress ZIP requested.')
output_dir.mkdir(parents=True, exist_ok=True)
"""
    ),
    code(
        """
workspace = Path(tempfile.mkdtemp(prefix='phase9-v4-', dir='/content'))
project = workspace / 'incidentgraph'
subprocess.run(['git', 'clone', '--branch', 'main', str(bundle), str(project)], check=True)
revision = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=project, text=True).strip()
expected_revision = 'f3d990672a31ae606adbaec1f2abee745e1cc4b4'
assert revision == expected_revision, 'Unexpected bundle revision: ' + revision
required = [
    project / 'config/phase9-v4-fresh-freeze.json',
    project / 'src/incidentgraph/phase9_v4_runner.py',
    project / 'src/incidentgraph/phase9_v4_evaluation.py',
]
missing = [str(path.relative_to(project)) for path in required if not path.is_file()]
assert not missing, 'Wrong or incomplete bundle. Missing: ' + ', '.join(missing)
subprocess.run([sys.executable, '-m', 'pip', 'install', '-q', 'uv'], check=True)
subprocess.run(
    ['uv', 'sync', '--frozen', '--no-dev', '--python', '3.12'],
    cwd=project,
    check=True,
)
print('Project ready:', revision[:7])
"""
    ),
    code(
        """
def server_version():
    with urllib.request.urlopen('http://127.0.0.1:11434/api/version', timeout=2) as response:
        return json.load(response)['version']

ready_version = None
try:
    ready_version = server_version()
except Exception:
    pass
if ready_version is not None and ready_version != '0.34.3':
    raise RuntimeError('An incompatible Ollama server is active. Use a fresh Colab runtime.')
if ready_version == '0.34.3':
    print('Reusing Ollama 0.34.3.')
else:
    missing_tools = [name for name in ('curl', 'zstd', 'tar') if shutil.which(name) is None]
    if missing_tools:
        subprocess.run(['apt-get', 'update', '-qq'], check=True)
        subprocess.run(['apt-get', 'install', '-y', '-qq', *missing_tools], check=True)
    installer = workspace / 'install-ollama.sh'
    urllib.request.urlretrieve('https://ollama.com/install.sh', installer)
    installation = subprocess.run(
        ['bash', str(installer)],
        env={**os.environ, 'OLLAMA_VERSION': '0.34.3'},
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    install_output = installation.stdout or ''
    (workspace / 'ollama-install.log').write_text(install_output)
    print(install_output[-8000:])
    if installation.returncode != 0:
        raise RuntimeError(
            f'Ollama installation failed (exit {installation.returncode}). '
            'Share the last installer lines printed above.'
        )

try:
    version = server_version()
except Exception:
    ollama_log_path = workspace / 'ollama.log'
    ollama_log = ollama_log_path.open('w')
    subprocess.Popen(
        ['ollama', 'serve'],
        stdout=ollama_log,
        stderr=subprocess.STDOUT,
        env={
            **os.environ,
            'OLLAMA_HOST': '127.0.0.1:11434',
            'OLLAMA_KEEP_ALIVE': '10m',
            'OLLAMA_NUM_PARALLEL': '1',
            'OLLAMA_MAX_LOADED_MODELS': '1',
            'OLLAMA_CONTEXT_LENGTH': '8192',
        },
    )
    for _ in range(60):
        try:
            version = server_version()
            break
        except Exception:
            time.sleep(1)
    else:
        raise RuntimeError(ollama_log_path.read_text()[-5000:])
assert version == '0.34.3', 'Expected Ollama 0.34.3, got ' + version

model_id = 'qwen3:4b-instruct-2507-q4_K_M'
subprocess.run(['ollama', 'pull', model_id], check=True)
with urllib.request.urlopen('http://127.0.0.1:11434/api/tags') as response:
    models = json.load(response)['models']
model = next(item for item in models if item['name'] == model_id)
expected_digest = '0edcdef34593eac1aa2be9c7d06c432dcf81945adca5eca2f27662c18f168ba0'
assert model['digest'] == expected_digest, (model['digest'], expected_digest)
print('Pinned free model ready:', model_id, model['digest'][:12], 'Ollama', version)
"""
    ),
    code(
        """
os.environ.update({
    'INCIDENTGRAPH_ENVIRONMENT': 'local',
    'INCIDENTGRAPH_APP_DATABASE_DSN': 'postgresql://unused:unused@127.0.0.1:55432/unused',
    'INCIDENTGRAPH_LAB_DATABASE_DSN': 'postgresql://unused:unused@127.0.0.1:55433/unused',
    'INCIDENTGRAPH_NEO4J_URI': 'bolt://127.0.0.1:57687',
    'INCIDENTGRAPH_NEO4J_USER': 'neo4j',
    'INCIDENTGRAPH_NEO4J_PASSWORD': 'phase9-v4-offline-replay',
    'INCIDENTGRAPH_AUTH_TOKENS_JSON': json.dumps({
        '0' * 64: {
            'principal_id': 'phase9-v4-evaluator',
            'roles': ['viewer'],
            'service_ids': ['svc-gateway', 'svc-checkout', 'svc-payments'],
        }
    }),
})
subprocess.run(
    ['uv', 'run', 'python', '-m', 'incidentgraph.phase9_v4_runner', 'verify-freeze'],
    cwd=project,
    check=True,
)
print('v4 freeze verified. No Docker or external database is used by this replay.')
"""
    ),
    code(
        """
for shard_index in SHARDS_TO_RUN:
    print(f'Running v4 shard {shard_index}/{SHARD_COUNT - 1}', flush=True)
    subprocess.run(
        [
            'uv', 'run', 'python', '-m', 'incidentgraph.phase9_v4_runner',
            'run-agent-shard', '--output-dir', str(output_dir),
            '--shard-index', str(shard_index), '--shard-count', str(SHARD_COUNT),
        ],
        cwd=project,
        check=True,
    )
    checkpoint = shutil.make_archive(
        '/content/phase9-v4-progress', 'zip', '/content', 'phase9-v4-output'
    )
    print('Checkpoint updated:', checkpoint, flush=True)
print('Requested v4 shards completed.')
"""
    ),
    code(
        """
records = []
for path in sorted(output_dir.glob('agent-part-*.jsonl')):
    records.extend(json.loads(line) for line in path.read_text().splitlines() if line)
job_count = len({item['job_id'] for item in records})
print(f'Unique completed v4 jobs: {job_count}/120')
if job_count == 120:
    subprocess.run(
        [
            'uv', 'run', 'python', '-m', 'incidentgraph.phase9_v4_runner',
            'finalize', '--output-dir', str(output_dir),
        ],
        cwd=project,
        check=True,
    )
    print((output_dir / 'summary.md').read_text())
else:
    complete_shards = {
        int(path.stem.split('-')[2])
        for path in output_dir.glob('agent-part-*.jsonl')
        if len(path.read_text().splitlines()) == 10
    }
    print('Still run these shard indices:', sorted(set(range(SHARD_COUNT)) - complete_shards))

archive = Path(
    shutil.make_archive('/content/phase9-v4-progress', 'zip', '/content', 'phase9-v4-output')
)
assert zipfile.is_zipfile(archive)
print('Archive size:', f'{archive.stat().st_size / 1024 / 1024:.1f} MiB')
files.download(str(archive))
print('Send phase9-v4-progress.zip to Codex. Do not rename or unpack it.')
"""
    ),
]

notebook = {
    "cells": cells,
    "metadata": {
        "accelerator": "GPU",
        "colab": {"gpuType": "T4", "provenance": []},
        "kernelspec": {"display_name": "Python 3", "name": "python3"},
        "language_info": {"name": "python"},
    },
    "nbformat": 4,
    "nbformat_minor": 5,
}
OUTPUT.write_text(json.dumps(notebook, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
print(OUTPUT)
