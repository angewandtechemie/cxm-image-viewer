# CxM Image viewer static server (no Python needed). Serves the folder containing this script.
param([string]$root = (Split-Path -Parent $MyInvocation.MyCommand.Path), [int]$port = 8642, [switch]$lan)
$listener = New-Object System.Net.HttpListener
if ($lan) {
  try {
    $listener.Prefixes.Add("http://+:$port/")
    $listener.Start()
  } catch {
    $listener = New-Object System.Net.HttpListener
    $listener.Prefixes.Add("http://127.0.0.1:$port/")
    $listener.Start()
    Write-Warning "LAN bind denied (needs URL ACL). Fix once as admin: netsh http add urlacl url=http://+:$port/ user=$env:USERNAME"
  }
} else {
  $listener.Prefixes.Add("http://127.0.0.1:$port/")
  $listener.Start()
}
Write-Host "Serving $root on http://127.0.0.1:$port/ (close this window to stop)"
$mime = @{ '.html'='text/html; charset=utf-8'; '.htm'='text/html; charset=utf-8'; '.js'='text/javascript'; '.css'='text/css'; '.png'='image/png'; '.jpg'='image/jpeg'; '.jpeg'='image/jpeg'; '.svg'='image/svg+xml'; '.pdf'='application/pdf'; '.json'='application/json'; '.ico'='image/x-icon'; '.txt'='text/plain; charset=utf-8'; '.webm'='video/webm' }
while ($listener.IsListening) {
  try {
    $ctx = $listener.GetContext()
    $path = [System.Uri]::UnescapeDataString($ctx.Request.Url.AbsolutePath)
    if ($path -eq '/') { $path = '/index.html' }
    $file = Join-Path $root ($path -replace '/', '\')
    $full = [System.IO.Path]::GetFullPath($file)
    if ((Test-Path $full -PathType Leaf) -and $full.StartsWith($root)) {
      $bytes = [System.IO.File]::ReadAllBytes($full)
      $ext = [System.IO.Path]::GetExtension($full).ToLower()
      if ($mime.ContainsKey($ext)) { $ctx.Response.ContentType = $mime[$ext] }
      $ctx.Response.ContentLength64 = $bytes.Length
      $ctx.Response.OutputStream.Write($bytes, 0, $bytes.Length)
    } else {
      $ctx.Response.StatusCode = 404
    }
    $ctx.Response.Close()
  } catch {
    if (-not $listener.IsListening) { break }
    Start-Sleep -Milliseconds 100
  }
}
$listener.Close()
