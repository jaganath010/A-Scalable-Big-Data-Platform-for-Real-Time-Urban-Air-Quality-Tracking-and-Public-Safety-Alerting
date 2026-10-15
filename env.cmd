@echo off
REM ===========================================================================
REM Spark local-mode environment for this project - cmd.exe version.
REM (env.ps1 is the PowerShell equivalent.)
REM
REM Usage:   env.cmd
REM          ...then run python / spark-submit in the SAME window.
REM
REM Sets variables for THIS WINDOW ONLY. Nothing global is modified, so the
REM system-wide JDK 23 stays the default for everything else on the machine.
REM ===========================================================================

REM Spark 3.5 supports Java 8/11/17. The machine's default is JDK 23, which
REM fails with:
REM   UnsupportedOperationException: getSubject is supported only if a
REM   security manager is allowed
REM because Java 18+ disabled Subject.getSubject(), which Hadoop's security
REM layer still calls. Pin the JRE 8 that is already installed.
set "JAVA_HOME=C:\Program Files\Java\jre1.8.0_421"

REM winutils.exe + hadoop.dll. Without these, every Parquet write and model
REM save fails with "HADOOP_HOME and hadoop.home.dir are unset". Reads appear
REM to work, so the problem only shows up when writing output.
set "HADOOP_HOME=C:\hadoop"
set "PATH=%HADOOP_HOME%\bin;%JAVA_HOME%\bin;%PATH%"

REM Dataset and lakehouse locations.
set "AQ_DATA=F:\SEM 5 NOTES\Big Data\Project_Final\airquality_expanded"
set "AQ_LAKE=D:\aq_lakehouse"
set "AQ_TMP=D:\aq_sparktmp"

REM Local Spark sizing. Lower AQ_DRIVER_MEM if other jobs are running.
set "AQ_DRIVER_MEM=8g"
set "AQ_CORES=8"
set "AQ_SHUFFLE_PARTITIONS=200"

echo Spark env ready ^(this window only^)
echo   JAVA_HOME   %JAVA_HOME%
echo   HADOOP_HOME %HADOOP_HOME%
echo   AQ_LAKE     %AQ_LAKE%
java -version 2>&1 | findstr /C:"version"
