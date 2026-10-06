# pkanban installer for Windows PowerShell.
#
#   irm __PKANBAN_SERVER__/install.ps1 | iex
#
# Installs the pkanban CLI as an isolated tool -- with uv if you have it, else
# pipx, else it installs uv first (uv brings its own Python, so none is needed
# beforehand) -- then points the CLI at the server this script came from.
#
# Runs under `iex`, so it is in the caller's own session: it never calls
# `exit` (that would close their window) and keeps its work inside a function.
# Written for Windows PowerShell 5.1: no `&&`, `??` or ternaries.

function Install-Pkanban {
    $ErrorActionPreference = 'Stop'

    $server = $env:PKANBAN_SERVER
    if (-not $server) { $server = '__PKANBAN_SERVER__' }

    function Test-Command($name) {
        return [bool](Get-Command $name -ErrorAction SilentlyContinue)
    }

    # uv, its tools and pipx's land in ~\.local\bin unless UV_TOOL_BIN_DIR or
    # PIPX_BIN_DIR moves them. Installers add the directory to the user PATH
    # in the registry, which this session has already read, so add it here
    # too or `uv` and `pkanban` will not resolve.
    function Update-SessionPath {
        $dirs = @(Join-Path $env:USERPROFILE '.local\bin')
        if (Test-Command 'uv') { $dirs += (uv tool dir --bin) }
        if (Test-Command 'pipx') { $dirs += (pipx environment --value PIPX_BIN_DIR) }
        foreach ($bin in $dirs) {
            if ($bin -and (($env:Path -split ';') -notcontains $bin)) { $env:Path = "$bin;$env:Path" }
        }
    }

    if (Test-Command 'uv') {
        Write-Host 'Installing pkanban with uv...'
        uv tool install --quiet --upgrade pkanban
    } elseif (Test-Command 'pipx') {
        Write-Host 'Installing pkanban with pipx...'
        pipx install --quiet --force pkanban
    } else {
        Write-Host 'Installing uv (a Python tool installer, from astral.sh)...'
        powershell -NoProfile -ExecutionPolicy Bypass -Command 'irm https://astral.sh/uv/install.ps1 | iex' | Out-Null
        Update-SessionPath
        if (-not (Test-Command 'uv')) {
            Write-Error 'uv installed but is not on PATH; open a new terminal and rerun.'
            return
        }
        Write-Host 'Installing pkanban with uv...'
        uv tool install --quiet --upgrade pkanban
    }
    if ($LASTEXITCODE -ne 0) {
        Write-Error 'Installing pkanban failed; see the output above.'
        return
    }

    Update-SessionPath
    if (-not (Test-Command 'pkanban')) {
        Write-Error "pkanban installed but cannot be found; open a new terminal and run 'pkanban --version'."
        return
    }

    pkanban config --url $server | Out-Null
    $version = pkanban --version | Select-Object -First 1

    Write-Host ''
    Write-Host "Installed $version, using $server"
    Write-Host ''
    Write-Host 'Next, sign in:'
    Write-Host '  pkanban login <username>'
    Write-Host ''
    Write-Host "No account yet? Create one at $server/signup"
    Write-Host "Agents and scripts: make an API key at $server/settings/api-keys and run"
    Write-Host '  pkanban apikey save <key>'
}

Install-Pkanban
