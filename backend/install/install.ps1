# pkanban installer for Windows PowerShell.
#
#   irm __PKANBAN_SERVER__/install.ps1 | iex
#
# Installs the pkanban CLI as an isolated tool -- with uv if you have it, else
# pipx, else it installs uv first (uv brings its own Python, so none is needed
# beforehand) -- then points the CLI at the server this script came from, and
# puts it on your PATH for new windows.
#
# Set PKANBAN_NO_MODIFY_PATH=1 to leave your PATH alone.
#
# Runs under `iex`, so it is in the caller's own session: it never calls
# `exit` (that would close their window) and keeps its work inside a function.
# Written for Windows PowerShell 5.1: no `&&`, `??` or ternaries.

function Install-Pkanban {
    $ErrorActionPreference = 'Stop'

    $server = $env:PKANBAN_SERVER
    if (-not $server) { $server = '__PKANBAN_SERVER__' }
    $modifyPath = -not $env:PKANBAN_NO_MODIFY_PATH

    function Test-Command($name) {
        return [bool](Get-Command $name -ErrorAction SilentlyContinue)
    }

    # Where the tools put binaries: ~\.local\bin unless UV_TOOL_BIN_DIR or
    # PIPX_BIN_DIR moves it. Asked of each tool rather than assumed.
    function Get-BinDirs {
        $dirs = @()
        if (Test-Command 'uv') { $dirs += (uv tool dir --bin) }
        if (Test-Command 'pipx') { $dirs += (pipx environment --value PIPX_BIN_DIR) }
        $dirs += (Join-Path $env:USERPROFILE '.local\bin')
        return $dirs | Where-Object { $_ }
    }

    # Installers add their directory to the user PATH in the registry, which
    # this session has already read, so add it here too or `uv` and `pkanban`
    # will not resolve.
    function Update-SessionPath {
        foreach ($bin in (Get-BinDirs)) {
            if (($env:Path -split ';') -notcontains $bin) { $env:Path = "$bin;$env:Path" }
        }
    }

    # The pkanban this script installed, not whichever one PATH finds first
    # (an activated virtualenv's, say).
    function Find-Pkanban {
        foreach ($bin in (Get-BinDirs)) {
            $exe = Join-Path $bin 'pkanban.exe'
            if (Test-Path $exe) { return $exe }
        }
        return $null
    }

    if (Test-Command 'uv') {
        $via = 'uv'
    } elseif (Test-Command 'pipx') {
        $via = 'pipx'
    } else {
        Write-Host 'Installing uv (a Python tool installer, from astral.sh)...'
        if (-not $modifyPath) { $env:UV_NO_MODIFY_PATH = '1' }
        powershell -NoProfile -ExecutionPolicy Bypass -Command 'irm https://astral.sh/uv/install.ps1 | iex' | Out-Null
        Update-SessionPath
        if (-not (Test-Command 'uv')) {
            Write-Error 'uv installed but is not on PATH; open a new terminal and rerun.'
            return
        }
        $via = 'uv'
    }

    Write-Host "Installing pkanban with $via..."
    if ($via -eq 'uv') {
        uv tool install --quiet --upgrade pkanban
    } else {
        pipx install --quiet --force pkanban
    }
    if ($LASTEXITCODE -ne 0) {
        Write-Error 'Installing pkanban failed; see the output above.'
        return
    }

    $exe = Find-Pkanban
    if (-not $exe) {
        Write-Error "pkanban installed but cannot be found; open a new terminal and run 'pkanban --version'."
        return
    }
    $binDir = Split-Path $exe

    & $exe config --url $server | Out-Null
    $version = & $exe --version | Select-Object -First 1

    Write-Host ''
    Write-Host "Installed $version, using $server"

    # New windows read PATH from the registry: is the directory there?
    $saved = @()
    foreach ($scope in 'User', 'Machine') {
        $value = [Environment]::GetEnvironmentVariable('Path', $scope)
        if ($value) { $saved += ($value -split ';') }
    }
    if ($saved -notcontains $binDir) {
        Write-Host ''
        $added = $false
        if ($modifyPath) {
            # Through cmd to silence it: in PowerShell 5.1, `2>&1` on a native
            # command turns its stderr into errors, which 'Stop' then throws.
            if ($via -eq 'uv') { cmd /c 'uv tool update-shell >nul 2>&1' } else { cmd /c 'pipx ensurepath >nul 2>&1' }
            $added = ($LASTEXITCODE -eq 0)
        }
        if ($added) {
            Write-Host "Added $binDir to your PATH for new windows."
        } else {
            Write-Host "$binDir is not on your PATH; add it to use 'pkanban' in new windows."
        }
    }
    # Ready in this window either way: `iex` runs in the caller's session.
    if (($env:Path -split ';') -notcontains $binDir) { $env:Path = "$binDir;$env:Path" }

    Write-Host ''
    Write-Host 'Next, sign in (your browser opens to approve it):'
    Write-Host '  pkanban login'
    Write-Host ''
    Write-Host "Setting this up for an AI agent? Point it at $server/agents.md"
}

Install-Pkanban
