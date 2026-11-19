"""Exercise the Windows sampler with synthetic process and connection lists."""
import json
import os
from pathlib import Path
import subprocess

import pytest


@pytest.mark.skipif(os.name != 'nt', reason='Windows PowerShell sampler')
def test_sampler_filters_processes_and_never_writes_addresses(tmp_path):
    root = Path(__file__).parents[1]
    install = tmp_path / 'synthetic-install'
    install.mkdir()
    stop = tmp_path / 'stop'
    output = tmp_path / 'result.json'
    wrapper = tmp_path / 'synthetic-sampler.ps1'
    wrapper.write_text(r'''
param($Install, $Stop, $Output, $Observer)
function Get-CimInstance {
    param($Filter, $ErrorAction)
    [pscustomobject]@{ProcessId=1001; ExecutablePath=(Join-Path $Install 'python.exe')}
    [pscustomobject]@{ProcessId=1002; ExecutablePath='C:\synthetic-other\python.exe'}
}
function Get-NetTCPConnection {
    param($ErrorAction)
    'stop' | Set-Content -LiteralPath $Stop
    [pscustomobject]@{OwningProcess=1001; RemoteAddress='127.0.0.1'}
    [pscustomobject]@{OwningProcess=1001; RemoteAddress='198.51.100.2'}
    [pscustomobject]@{OwningProcess=1002; RemoteAddress='198.51.100.3'}
}
& $Observer -ExecutableDirectory $Install -StopFile $Stop -OutputFile $Output
''', encoding='utf-8')
    subprocess.run([
        'powershell.exe', '-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass',
        '-File', str(wrapper), str(install), str(stop), str(output),
        str(root / 'tools' / 'observe_process_tcp.ps1'),
    ], check=True, timeout=30)
    raw = output.read_text(encoding='utf-8-sig')
    result = json.loads(raw)
    assert result['samples'] == 1 and result['process_ids'] == [1001]
    assert result['nonloopback_tcp_observations'] == 1 and result['errors'] == 0
    assert result['stopped_by_signal'] is True and '198.51.100' not in raw
