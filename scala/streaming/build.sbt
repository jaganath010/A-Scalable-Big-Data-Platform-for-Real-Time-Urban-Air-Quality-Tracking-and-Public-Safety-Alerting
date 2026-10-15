// ============================================================================
// Phase 7 + 8 - Real-Time Speed Layer and Alert Engine
// 23AID302 - Big Data Analytics
//
// Written in Scala per the project specification: "Real-Time Speed Layer
// (Spark Structured Streaming / Scala): Written natively in Scala to maximize
// native JVM thread execution speeds."
//
// Scala 2.12.18 is NOT a free choice - it is the version the installed Spark
// 3.5.6 is built against (spark-core_2.12-3.5.6.jar). A 2.13 or 3.x build will
// compile and then fail at runtime with NoSuchMethodError, because Scala's
// binary compatibility does not span major versions.
// ============================================================================

name         := "airquality-streaming"
version      := "1.0"
scalaVersion := "2.12.18"

val sparkVersion = "3.5.6"

// "provided" - these jars ship with the Spark installation and must NOT be
// bundled into the artifact. Including them produces a ~300 MB jar that can
// conflict with the cluster's own Spark at runtime.
libraryDependencies ++= Seq(
  "org.apache.spark" %% "spark-core"    % sparkVersion % "provided",
  "org.apache.spark" %% "spark-sql"     % sparkVersion % "provided",
  "org.apache.spark" %% "spark-mllib"   % sparkVersion % "provided"
)

// Spark 3.5 runs on Java 8/11/17. This project pins JRE 8 (see env.ps1), so
// target its bytecode level.
javacOptions  ++= Seq("-source", "8", "-target", "8")
scalacOptions ++= Seq("-target:jvm-1.8", "-deprecation", "-feature")

// No tests in this build; keep `sbt package` fast.
Test / skip := true
