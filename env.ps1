# Spark local-mode environment for this project.
# Usage:  . .\env.ps1     (dot-source it, so the vars land in your shell)
#
# Sets vars for THIS SHELL ONLY - nothing global is modified, so the
# system-wide JDK 23 stays the default for everything else on the machine.

# Spark 3.5.x supports Java 8/11/17. The machine's default JDK is 23, which
# Spark 3.5 does not support, so we pin the JRE 8 that is already installed.
$env:JAVA_HOME = "C:\Program Files\Java\jre1.8.0_421"

# Pin the interpreter so driver and executors agree. Spark launches Python
# workers as subprocesses; without this the Store-Python stub can resolve
# differently in the child and the job dies with a version-mismatch error.
$env:PYSPARK_PYTHON        = (Get-Command python).Source
$env:PYSPARK_DRIVER_PYTHON = $env:PYSPARK_PYTHON

# Local dataset root. The report and scripts still say E:\airquality_expanded;
# the data actually lives here.
$env:AQ_DATA = "F:\SEM 5 NOTES\Big Data\Project_Final\airquality_expanded"

# Spark on Windows needs winutils.exe + hadoop.dll to chmod files it writes.
# Without these, every .write.parquet() and model .save() dies with
#   java.io.FileNotFoundException: HADOOP_HOME and hadoop.home.dir are unset
# Build: cdarlint/winutils hadoop-3.3.5 (PySpark 3.5.6 bundles Hadoop 3.3.4;
# winutils is compatible across the 3.3.x line).
$env:HADOOP_HOME = "C:\hadoop"
$env:PATH        = "$env:HADOOP_HOME\bin;$env:PATH"

Write-Host "Spark env ready." -ForegroundColor Green
Write-Host "  JAVA_HOME     $env:JAVA_HOME"
Write-Host "  PYSPARK_PYTHON $env:PYSPARK_PYTHON"
Write-Host "  AQ_DATA       $env:AQ_DATA"
Write-Host "  HADOOP_HOME   $env:HADOOP_HOME"
