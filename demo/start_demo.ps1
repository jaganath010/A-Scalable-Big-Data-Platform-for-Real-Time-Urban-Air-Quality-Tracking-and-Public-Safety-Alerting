<#
================================================================================
REVIEW DEMO LAUNCHER - shows HDFS, YARN, Spark and the website, in that order
================================================================================
Project : 23AID302 - Big Data Analytics

  powershell -ExecutionPolicy Bypass -File demo\start_demo.ps1            # everything
  powershell -ExecutionPolicy Bypass -File demo\start_demo.ps1 -SkipBoot  # cluster already up

WHAT IT DOES
  1. Starts Docker Desktop and the 11-container cluster (unless -SkipBoot)
  2. Proves HDFS:   4 live DataNodes, fsck HEALTHY, the data sitting in it
  3. Proves YARN:   4 NodeManagers RUNNING
  4. Runs a real Spark job ON YARN against the HDFS data, and opens the UIs
  5. Opens the website

  The cluster is left running. To stop it afterwards:
      docker compose -f hadoop\docker-compose.yml -f hadoop\docker-compose.yarn.yml `
                     -f hadoop\docker-compose.spark.yml stop
================================================================================
#>
param([switch]$SkipBoot, [int]$Hold = 90)

$ErrorActionPreference = "Continue"
$Root  = Split-Path -Parent $PSScriptRoot
$Hadoop = Join-Path $Root "hadoop"
$Demo   = Join-Path $Root "demo"
$Site   = Join-Path $Root "dashboard\AirWatch_India.html"
$compose = @("-f","docker-compose.yml","-f","docker-compose.yarn.yml","-f","docker-compose.spark.yml")

function Banner($t) { Write-Host ""; Write-Host ("=" * 70) -ForegroundColor Cyan; Write-Host "  $t" -ForegroundColor Cyan; Write-Host ("=" * 70) -ForegroundColor Cyan }

if (-not $SkipBoot) {
  Banner "STARTING THE CLUSTER"
  Start-Process "C:\Program Files\Docker\Docker\Docker Desktop.exe"
  for ($i=1; $i -le 30; $i++) { docker info 2>&1 | Out-Null; if ($LASTEXITCODE -eq 0) { break }; Start-Sleep -Seconds 10 }
  Push-Location $Hadoop
  docker compose @compose down --remove-orphans 2>&1 | Out-Null    # clears stale network refs; data is on bind mounts
  docker compose @compose up -d 2>&1 | Select-Object -Last 3
  Pop-Location
  for ($i=1; $i -le 30; $i++) { $s = docker exec aq-namenode hdfs dfsadmin -safemode get 2>&1 | Out-String; if ($s -match "OFF") { break }; Start-Sleep -Seconds 5 }
}

Banner "1. HDFS - the distributed filesystem"
docker exec aq-namenode hdfs dfsadmin -report 2>&1 | Select-String "Live datanodes|Configured Capacity|DFS Used:|Under replicated|Missing blocks|Blocks with corrupt"
Write-Host "`n  data in the lake:" -ForegroundColor Yellow
docker exec aq-namenode hdfs dfs -du -s -h /user/hadoop/lakehouse/clean_scala /user/hadoop/features /user/hadoop/lakehouse/unified_merged /user/hadoop/models/gbt_pm25_forecaster 2>&1
Write-Host "`n  integrity check (fsck) on the unified table:" -ForegroundColor Yellow
docker exec aq-namenode hdfs fsck /user/hadoop/lakehouse/unified_merged 2>&1 | Select-String "Status:|Total size|Total blocks|Corrupt|Missing|Under-replicated"

Banner "2. YARN - the resource manager"
docker exec aq-resourcemanager yarn node -list 2>&1 | Select-Object -Last 6

Banner "3. SPARK on YARN - a real job over the HDFS data"
Write-Host "  opening the UIs first, so the job can be watched while it runs..." -ForegroundColor Yellow
$chrome = @("C:\Program Files\Google\Chrome\Application\chrome.exe","C:\Program Files (x86)\Google\Chrome\Application\chrome.exe") | Where-Object { Test-Path $_ } | Select-Object -First 1
$urls = @("http://localhost:9870/dfshealth.html#tab-datanode","http://localhost:8088/cluster")
if ($chrome) { Start-Process $chrome -ArgumentList $urls } else { $urls | ForEach-Object { Start-Process $_ } }
Start-Sleep -Seconds 4

docker cp $Demo aq-spark:/demo 2>&1 | Out-Null
$cmd = "DEMO_HOLD=$Hold HADOOP_CONF_DIR=/opt/hadoop-conf /opt/spark/bin/spark-submit --master yarn --deploy-mode client --num-executors 3 --executor-memory 1500m --executor-cores 1 --driver-memory 1500m /demo/spark_yarn_demo.py 2>&1 | grep -v 'INFO \|WARN \|^\s*at '"
docker exec aq-spark sh -c $cmd

Banner "4. THE WEBSITE"
if ($chrome) { Start-Process $chrome -ArgumentList "`"$Site`"" } else { Start-Process $Site }
Write-Host "  opened: $Site"
Write-Host "`n  Cluster left running. Stop it with the compose 'stop' command in this file's header." -ForegroundColor Green
