# 加密货币信息查询工具

param(
    [Parameter(Position = 0)]
    [ValidateSet("fear", "help")]
    [string]$Command = "help"
)

[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

function Get-FearGreedIndex {
    try {
        $data = Invoke-RestMethod -Uri "https://api.alternative.me/fng/?limit=14" -TimeoutSec 15
        $current = $data.data[0]
        $value = [int]$current.value
        $classification = $current.value_classification

        $color = "White"
        if ($value -ge 55) { $color = "Green" }
        elseif ($value -le 45) { $color = "Red" }

        Write-Host ""
        Write-Host "==================================================" -ForegroundColor Cyan
        Write-Host "  恐惧与贪婪指数" -ForegroundColor Cyan
        Write-Host "==================================================" -ForegroundColor Cyan
        Write-Host "  当前指数 : " -NoNewline
        Write-Host "$value / 100" -ForegroundColor $color
        Write-Host "  市场情绪 : " -NoNewline
        Write-Host $classification -ForegroundColor $color

        Write-Host ""
        if ($value -ge 75) {
            Write-Host "  极度贪婪 - 市场可能过热，注意回调风险" -ForegroundColor Red
        } elseif ($value -ge 55) {
            Write-Host "  贪婪 - 市场偏乐观" -ForegroundColor Yellow
        } elseif ($value -ge 45) {
            Write-Host "  中性 - 市场情绪平稳" -ForegroundColor White
        } elseif ($value -ge 25) {
            Write-Host "  恐惧 - 市场偏悲观" -ForegroundColor Yellow
        } else {
            Write-Host "  极度恐惧 - 市场恐慌，历史看可能是机会" -ForegroundColor Green
        }

        Write-Host ""
        Write-Host "  近14天趋势: " -NoNewline
        $sorted = $data.data | Sort-Object { [int]$_.timestamp }
        foreach ($item in $sorted) {
            $v = [int]$item.value
            if ($v -ge 75) { Write-Host "E" -NoNewline -ForegroundColor Red }
            elseif ($v -ge 55) { Write-Host "G" -NoNewline -ForegroundColor Yellow }
            elseif ($v -ge 45) { Write-Host "N" -NoNewline -ForegroundColor White }
            elseif ($v -ge 25) { Write-Host "F" -NoNewline -ForegroundColor Yellow }
            else { Write-Host "X" -NoNewline -ForegroundColor Green }
        }
        Write-Host " (E=贪婪 G=偏贪 N=中性 F=恐惧 X=极度恐惧)"
        Write-Host ""
    }
    catch {
        Write-Host "获取失败: $($_.Exception.Message)" -ForegroundColor Red
    }
}

function Show-Help {
    Write-Host ""
    Write-Host "==================================================" -ForegroundColor Cyan
    Write-Host "  加密货币信息查询工具" -ForegroundColor Cyan
    Write-Host "==================================================" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "  .\crypto-info.ps1 fear    查看恐惧与贪婪指数" -ForegroundColor White
    Write-Host ""
    Write-Host "  价格/新闻/分析请直接对话，例如:" -ForegroundColor Yellow
    Write-Host "    BTC最新价格和新闻" -ForegroundColor DarkGray
    Write-Host "    ETH和SOL对比分析" -ForegroundColor DarkGray
    Write-Host "    ORDI最近有什么消息" -ForegroundColor DarkGray
    Write-Host ""
}

switch ($Command) {
    "fear"  { Get-FearGreedIndex }
    "help"  { Show-Help }
    default { Show-Help }
}