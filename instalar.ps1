# =============================================================
#  Instala (ou atualiza) o HORUS no Windows 10/11.
#
#  Abra o PowerShell (tecla Windows, digite "PowerShell", Enter) e cole:
#    irm https://raw.githubusercontent.com/X86NOCTA/robo-acoes/main/instalar.ps1 | iex
# =============================================================

function Instalar-Horus {
    $ErrorActionPreference = "Stop"
    $Repo    = "X86NOCTA/robo-acoes"
    $Destino = Join-Path $env:USERPROFILE "robo-acoes"
    $Dados   = Join-Path $env:USERPROFILE ".robo-acoes"

    Write-Host ""
    Write-Host "  HORUS - instalando..." -ForegroundColor Cyan
    Write-Host ""

    function Achar-Python {
        $exe = $null
        try { $exe = (& py -3 -c "import sys; print(sys.executable)" 2>$null | Select-Object -First 1) } catch {}
        if (-not $exe) {
            try { $exe = (& python -c "import sys; print(sys.executable)" 2>$null | Select-Object -First 1) } catch {}
        }
        if ($exe -and (Test-Path $exe.Trim())) { return $exe.Trim() }
        $c = Get-ChildItem "$env:LOCALAPPDATA\Programs\Python\Python3*\python.exe" -ErrorAction SilentlyContinue |
             Sort-Object FullName -Descending | Select-Object -First 1
        if ($c) { return $c.FullName }
        return $null
    }

    # 1) Python 3
    $py = Achar-Python
    if (-not $py) {
        Write-Host "Python nao encontrado. Instalando o Python 3 (pode levar alguns minutos)..." -ForegroundColor Yellow
        if (Get-Command winget -ErrorAction SilentlyContinue) {
            winget install -e --id Python.Python.3.12 --scope user --silent --accept-package-agreements --accept-source-agreements | Out-Host
            $py = Achar-Python
        }
        if (-not $py) {
            Write-Host ""
            Write-Host "Nao consegui instalar o Python sozinho." -ForegroundColor Red
            Write-Host "1. Baixe em https://www.python.org/downloads/"
            Write-Host "2. Na instalacao, marque 'Add python.exe to PATH'."
            Write-Host "3. Feche e abra o PowerShell e cole este comando de novo."
            return
        }
    }
    Write-Host "Python: $py"

    # 2) Baixa a versao mais nova do GitHub
    Write-Host "Baixando o Horus do GitHub ($Repo)..."
    [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
    $zip = Join-Path $env:TEMP "horus.zip"
    $ext = Join-Path $env:TEMP "horus-extrair"
    Invoke-WebRequest -UseBasicParsing -Uri "https://github.com/$Repo/archive/refs/heads/main.zip" -OutFile $zip
    if (Test-Path $ext) { Remove-Item $ext -Recurse -Force }
    Expand-Archive -Path $zip -DestinationPath $ext -Force
    $origem = Get-ChildItem $ext -Directory | Select-Object -First 1
    New-Item -ItemType Directory -Force -Path $Destino, $Dados | Out-Null
    Get-ChildItem $origem.FullName -File |
        Where-Object { $_.Name -notin @("config.json", "acoes.txt") } |
        Copy-Item -Destination $Destino -Force
    Remove-Item $zip, $ext -Recurse -Force -ErrorAction SilentlyContinue
    Write-Host "Arquivos salvos em $Destino"

    # 3) Fecha a versao antiga, se estiver aberta
    Get-CimInstance Win32_Process -Filter "Name like 'python%'" -ErrorAction SilentlyContinue |
        Where-Object { $_.CommandLine -like "*robo-acoes*robo.py*" } |
        ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
    Start-Sleep -Seconds 1

    # 4) Atalhos na Area de Trabalho e no menu Iniciar (abre sem janela preta)
    $pyw = Join-Path (Split-Path $py) "pythonw.exe"
    if (-not (Test-Path $pyw)) { $pyw = $py }
    $robo = Join-Path $Destino "robo.py"
    $ws = New-Object -ComObject WScript.Shell
    $pastas = @([Environment]::GetFolderPath("Desktop"), (Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs"))
    foreach ($p in $pastas) {
        if (-not (Test-Path $p)) { continue }
        $lnk = $ws.CreateShortcut((Join-Path $p "Horus.lnk"))
        $lnk.TargetPath       = $pyw
        $lnk.Arguments        = "`"$robo`""
        $lnk.WorkingDirectory = $Destino
        $lnk.IconLocation     = "$env:SystemRoot\System32\shell32.dll,22"
        $lnk.Description      = "Horus - o olho que ve o mercado"
        $lnk.Save()
    }

    # 5) Abre o Horus
    Start-Process -FilePath $pyw -ArgumentList "`"$robo`"" -WorkingDirectory $Destino

    Write-Host ""
    Write-Host "  Pronto! O Horus vai abrir no navegador em alguns segundos." -ForegroundColor Green
    Write-Host "  Nas proximas vezes, use o atalho 'Horus' na Area de Trabalho ou no menu Iniciar."
    Write-Host ""
}

Instalar-Horus
