// ============================================================================
// PHASE 7 + 8 - Real-Time Speed Layer and Closed-Loop Alert Engine
// ============================================================================
// Project : A Scalable Big Data Platform for Real-Time Urban Air Quality
//           Tracking and Public Safety Alerting
// Course  : 23AID302 - Big Data Analytics
//
// WHAT THIS DOES
//   Watches an HDFS directory for new sensor files. For each micro-batch it
//   rebuilds the same features Phase 4 built, applies the feature pipeline and
//   GBT model trained by Phase 5, forecasts PM2.5 one hour ahead, converts that
//   to a CPCB National AQI, and writes a public-health alert wherever the
//   forecast AQI exceeds 150.
//
// WHY SCALA
//   Specified by the project document for this component. It also sidesteps a
//   real constraint on the build machine: Spark cannot spawn Python worker
//   processes there, so a PySpark streaming job with UDFs would not run at all.
//   This job is pure JVM and needs no Python worker.
//
// ----------------------------------------------------------------------------
// THE HARD PART, AND HOW IT IS SOLVED
// ----------------------------------------------------------------------------
// The model consumes lag and rolling-window features - pm25_lag_1h,
// pm25_roll_6h, pm25_avg24h and so on. Structured Streaming does NOT support
// window functions like lag() over a streaming DataFrame, because they need
// unbounded ordered history.
//
// Two mechanisms solve it together:
//
//   1. foreachBatch. Inside it each micro-batch is an ordinary BATCH DataFrame,
//      where window functions work normally.
//
//   2. A persisted history table. A micro-batch alone cannot see a station's
//      previous 24 hours, so each batch is unioned with a rolling history
//      table read from HDFS, features are computed over the union, predictions
//      are emitted ONLY for the new rows, and the history is then updated and
//      trimmed. This is what makes a one-row-per-station batch predictable at
//      all.
//
// The alternative - flatMapGroupsWithState - keeps history in executor memory
// and is faster, but loses all state if the job restarts. The history table
// survives restarts, which matters more for an alerting system than latency.
// ============================================================================

import org.apache.spark.sql.{Column, DataFrame, SparkSession}
import org.apache.spark.sql.expressions.Window
import org.apache.spark.sql.functions._
import org.apache.spark.sql.types._
import org.apache.spark.ml.PipelineModel
import org.apache.spark.ml.regression.GBTRegressionModel

object AirQualityStream {

  // --------------------------------------------------------------------------
  // PATHS - overridable so the job runs against local disk or HDFS unchanged,
  // matching how scripts/paths.py works on the Python side.
  // --------------------------------------------------------------------------
  private val Lake = sys.env.getOrElse("AQ_LAKE", "hdfs://localhost:9000/user/hadoop")

  private val StreamInput   = s"$Lake/lakehouse/stream/input"
  private val CheckpointDir = s"$Lake/lakehouse/stream/checkpoint"
  private val HistoryPath   = s"$Lake/lakehouse/stream/history"
  private val AlertPath     = s"$Lake/lakehouse/stream/alerts"
  private val PredictionPath= s"$Lake/lakehouse/stream/predictions"
  private val PipelinePath  = s"$Lake/models/feature_pipeline"
  private val ModelPath     = s"$Lake/models/gbt_pm25_forecaster"

  private val Hour = 3600L

  // The alert threshold. CPCB bands: 0-50 Good, 51-100 Satisfactory,
  // 101-200 Moderate, 201-300 Poor, 301-400 Very Poor, 401-500 Severe.
  private val AlertThreshold = 150.0

  // How much history to retain per station. 24 hours is the longest window any
  // feature needs (pm25_avg24h); 30 gives margin for gaps.
  private val HistoryHours = 30

  // --------------------------------------------------------------------------
  // INPUT SCHEMA - the 32 columns of the expanded dataset, in file order.
  // Declared explicitly: schema inference is unavailable on a streaming source,
  // and would be wrong to use anyway since a malformed batch must not silently
  // change the column types mid-stream.
  // --------------------------------------------------------------------------
  private val InputSchema = StructType(Seq(
    StructField("station_id",         StringType),
    StructField("state",              StringType),
    StructField("city",               StringType),
    StructField("from_date",          StringType),
    StructField("pm25",               DoubleType),
    StructField("pm10",               DoubleType),
    StructField("no2",                DoubleType),
    StructField("so2",                DoubleType),
    StructField("co",                 DoubleType),
    StructField("o3",                 DoubleType),
    StructField("nh3",                DoubleType),
    StructField("wd_degree",          DoubleType),
    StructField("solar_radiation",    DoubleType),
    StructField("pressure",           DoubleType),
    StructField("temperature_c",      DoubleType),
    StructField("humidity_percent",   DoubleType),
    StructField("wind_speed_ms",      DoubleType),
    StructField("rainfall_mm",        DoubleType),
    StructField("weather_condition",  StringType),
    StructField("traffic_index",      DoubleType),
    StructField("is_rush_hour",       DoubleType),
    StructField("year",               IntegerType),
    StructField("month",              IntegerType),
    StructField("day",                IntegerType),
    StructField("hour",                IntegerType),
    StructField("day_of_week",        IntegerType),
    StructField("is_weekend",         DoubleType),
    StructField("season",             StringType),
    StructField("climate_type",       StringType),
    StructField("urbanization_index", DoubleType),
    StructField("data_source",        StringType),
    StructField("source_station",     StringType)
  ))

  // --------------------------------------------------------------------------
  // CPCB NATIONAL AQI BREAKPOINTS - identical to 02_feature_extraction.py.
  // (concentrationLow, concentrationHigh, indexLow, indexHigh)
  // The National AQI is the MAXIMUM of the per-pollutant sub-indices.
  // --------------------------------------------------------------------------
  private val Breakpoints: Map[String, Seq[(Double, Double, Double, Double)]] = Map(
    "pm25" -> Seq((0,30,0,50),(30,60,51,100),(60,90,101,200),(90,120,201,300),(120,250,301,400),(250,1000,401,500)),
    "pm10" -> Seq((0,50,0,50),(50,100,51,100),(100,250,101,200),(250,350,201,300),(350,430,301,400),(430,1000,401,500)),
    "no2"  -> Seq((0,40,0,50),(40,80,51,100),(80,180,101,200),(180,280,201,300),(280,400,301,400),(400,1000,401,500)),
    "so2"  -> Seq((0,40,0,50),(40,80,51,100),(80,380,101,200),(380,800,201,300),(800,1600,301,400),(1600,3000,401,500)),
    "co"   -> Seq((0,1,0,50),(1,2,51,100),(2,10,101,200),(10,17,201,300),(17,34,301,400),(34,100,401,500)),
    "o3"   -> Seq((0,50,0,50),(50,100,51,100),(100,168,101,200),(168,208,201,300),(208,748,301,400),(748,1000,401,500)),
    "nh3"  -> Seq((0,200,0,50),(200,400,51,100),(400,800,101,200),(800,1200,201,300),(1200,1800,301,400),(1800,3000,401,500))
  )

  // CPCB averaging period per pollutant, in hours.
  private val AqiWindowH = Map("pm25"->24,"pm10"->24,"no2"->24,"so2"->24,"nh3"->24,"co"->8,"o3"->8)

  /** Piecewise-linear CPCB sub-index for one pollutant concentration column.
    * Built as nested when/otherwise so it stays a pure Catalyst expression -
    * no UDF, therefore no serialisation cost and no Python worker. */
  private def subIndex(c: Column, bps: Seq[(Double, Double, Double, Double)]): Column = {
    var expr: Column = lit(500.0) // anything above the top band saturates
    bps.reverse.foreach { case (cLo, cHi, iLo, iHi) =>
      expr = when(c <= cHi, (lit(iHi - iLo) / lit(cHi - cLo)) * (c - lit(cLo)) + lit(iLo))
             .otherwise(expr)
    }
    when(c.isNull, lit(null).cast(DoubleType)).otherwise(expr)
  }

  /** CPCB band name, for the alert message. */
  private def aqiBand(c: Column): Column =
    when(c <= 50, "Good")
      .when(c <= 100, "Satisfactory")
      .when(c <= 200, "Moderate")
      .when(c <= 300, "Poor")
      .when(c <= 400, "Very Poor")
      .otherwise("Severe")

  // ==========================================================================
  // FEATURE ENGINEERING - a faithful port of 02_feature_extraction.py.
  //
  // The column NAMES here are load-bearing. The saved VectorAssembler refers to
  // its inputs by name, so every one of the 54 numeric features must exist and
  // be spelled exactly as Phase 4 spelled it, or transform() fails.
  // The label-building steps of Phase 4 are deliberately absent - there is no
  // future to look at in a live stream.
  // ==========================================================================
  private def buildFeatures(df0: DataFrame): DataFrame = {
    var df = df0

    // variation_bucket is a constant 0 in the rebuilt dataset (synthetic series
    // are separate stations, never interleaved). Recreated here so the window
    // definitions match Phase 4 exactly.
    df = df.withColumn("variation_bucket", lit(0))
           .withColumn("ts_unix", col("timestamp").cast(LongType))

    // Deduplicate on (station, hour): a replayed or overlapping file must not
    // produce two rows for the same hour, or every window below is wrong.
    val dedupW = Window.partitionBy("station_id", "variation_bucket", "ts_unix")
                       .orderBy(col("pm25").desc_nulls_last)
    df = df.withColumn("_rn", row_number().over(dedupW)).filter(col("_rn") === 1).drop("_rn")

    val track = Window.partitionBy("station_id", "variation_bucket").orderBy("ts_unix")

    // rangeBetween works on the VALUE of ts_unix, not row position, so a missing
    // hour shortens the window instead of silently reaching further back.
    def hoursBack(n: Int) =
      Window.partitionBy("station_id", "variation_bucket")
            .orderBy("ts_unix")
            .rangeBetween(-(n - 1).toLong * Hour, 0L)

    // --- CPCB rolling averages and current AQI -----------------------------
    AqiWindowH.foreach { case (p, h) =>
      df = df.withColumn(s"${p}_avg${h}h", avg(col(p)).over(hoursBack(h)))
    }
    Breakpoints.keys.foreach { p =>
      df = df.withColumn(s"si_$p", subIndex(col(s"${p}_avg${AqiWindowH(p)}h"), Breakpoints(p)))
    }
    df = df.withColumn("aqi_current", greatest(Breakpoints.keys.toSeq.map(p => col(s"si_$p")): _*))

    // Which pollutant is driving the index - the alert needs to name it.
    val siPairs = array(Breakpoints.keys.toSeq.map(p =>
      struct(col(s"si_$p").as("v"), lit(p).as("p"))): _*)
    df = df.withColumn("aqi_dominant_pollutant",
      sort_array(siPairs, asc = false).getItem(0).getField("p"))

    // --- History features ---------------------------------------------------
    df = df
      .withColumn("_lag_ts",   lag("ts_unix", 1).over(track))
      .withColumn("_lag_pm25", lag("pm25", 1).over(track))
      // A lag is only a "1 hour ago" value if the previous row really is 1 hour
      // behind. Otherwise fall back to the current value rather than lie.
      .withColumn("pm25_lag_1h",
        when((col("ts_unix") - col("_lag_ts")) === lit(Hour), col("_lag_pm25"))
          .otherwise(col("pm25")))
      .drop("_lag_ts", "_lag_pm25")
      .withColumn("pm25_delta_1h", col("pm25") - col("pm25_lag_1h"))
      .withColumn("pm25_roll_3h",  avg("pm25").over(hoursBack(3)))
      .withColumn("pm25_roll_6h",  avg("pm25").over(hoursBack(6)))
      .withColumn("pm25_std_6h",   stddev("pm25").over(hoursBack(6)))
      .withColumn("pm10_roll_6h",  avg("pm10").over(hoursBack(6)))
      .withColumn("no2_roll_6h",   avg("no2").over(hoursBack(6)))
      .withColumn("aqi_roll_6h",   avg("aqi_current").over(hoursBack(6)))
      // >1 means the last 3 hours are dirtier than the last 24: a surge in
      // progress, which is exactly what the alert engine exists to catch.
      .withColumn("pm25_surge_ratio", col("pm25_roll_3h") / (col("pm25_avg24h") + lit(1e-6)))
      .na.fill(0.0, Seq("pm25_std_6h", "pm25_delta_1h"))

    // --- Cyclical encodings -------------------------------------------------
    // hour 23 and hour 0 are adjacent in time but 23 apart as integers.
    val twoPi = 2.0 * math.Pi
    def cyc(c: String, period: Double, name: String): DataFrame = {
      val ang = (col(c) / lit(period)) * lit(twoPi)
      df.withColumn(s"${name}_sin", sin(ang)).withColumn(s"${name}_cos", cos(ang))
    }
    df = cyc("hour", 24.0, "hour")
    df = cyc("month", 12.0, "month")
    df = cyc("day_of_week", 7.0, "dow")
    val wdRad = radians(col("wd_degree"))
    df = df.withColumn("wd_sin", sin(wdRad)).withColumn("wd_cos", cos(wdRad))

    // --- Physical interaction features --------------------------------------
    df = df
      // Emission load divided by the wind that disperses it.
      .withColumn("ventilation_index", col("traffic_index") / (col("wind_speed_ms") + lit(0.5)))
      // Rain physically scrubs particulates; the first mm does most of it.
      .withColumn("is_raining", (col("rainfall_mm") > 0.1).cast(IntegerType))
      .withColumn("scrub_factor", log1p(col("rainfall_mm")))
      // Warm, dry, still air holds particulates near the surface.
      .withColumn("stagnation_index",
        (lit(100.0) - col("humidity_percent")) / (col("wind_speed_ms") + lit(0.5)))
      .withColumn("temp_humidity_interaction",
        col("temperature_c") * col("humidity_percent") / lit(100.0))

    // --- Provenance flags ---------------------------------------------------
    // Phase 3 sets these when it fills a missing reading. Live sensor frames are
    // not imputed, so they are 0 - but the columns must exist, because the model
    // was trained with them in the vector.
    Seq("pm25","pm10","no2","so2","co","o3","nh3",
        "solar_radiation","pressure","wd_degree").foreach { c =>
      df = df.withColumn(s"${c}_was_imputed", col(c).isNull.cast(IntegerType))
    }

    // --- Fill AFTER flagging --------------------------------------------------
    // The trained VectorAssembler is handleInvalid="skip": a single null in the
    // feature vector silently DROPS the row. In the batch pipeline that never
    // bites, because Phase 3 imputes before assembly. The live path has no
    // Phase 3, and CAMS returns nh3 as null for 100% of rows in this region -
    // so without this every live row was discarded and the stream reported
    // "predicted=0" with no error at all (measured: 16,560 rows in, 0 out).
    //
    // Order matters: the *_was_imputed flags above are computed from the RAW
    // nulls, so filling here cannot disguise a filled value as a measured one.
    // The model was trained with those flags in the vector, so it can learn to
    // discount a pollutant whose flag is set.
    //
    // 0.0 is the fill value rather than a median: a pollutant the sensor did
    // not report contributes nothing to its CPCB sub-index, and the National
    // AQI is a MAX across sub-indices, so a zero cannot inflate the alert. A
    // median could.
    Seq("pm25","pm10","no2","so2","co","o3","nh3",
        "solar_radiation","pressure","wd_degree").foreach { c =>
      df = df.withColumn(c, coalesce(col(c), lit(0.0)))
    }

    df
  }

  def main(args: Array[String]): Unit = {

    val spark = SparkSession.builder()
      .appName("AirQuality_Phase7_StreamingSpeedLayer")
      .config("spark.sql.streaming.schemaInference", "false")
      .config("spark.sql.shuffle.partitions", sys.env.getOrElse("AQ_SHUFFLE_PARTITIONS", "16"))
      .config("spark.sql.adaptive.enabled", "true")
      .getOrCreate()

    import spark.implicits._
    spark.sparkContext.setLogLevel("WARN")

    println("=" * 72)
    println("  PHASE 7 - REAL-TIME SPEED LAYER (Scala)")
    println("=" * 72)
    println(s"  watching   : $StreamInput")
    println(s"  checkpoint : $CheckpointDir")
    println(s"  history    : $HistoryPath")
    println(s"  alerts     : $AlertPath")
    println(s"  threshold  : predicted AQI > $AlertThreshold")
    println("=" * 72)

    // ------------------------------------------------------------------------
    // Load the models ONCE, outside the batch loop. Loading per batch would add
    // seconds of latency to every micro-batch.
    //
    // These were both produced by the PySpark pipeline. MLlib's on-disk format
    // is language-neutral, so a model fitted in Python loads unchanged here -
    // there is no export or conversion step.
    // ------------------------------------------------------------------------
    println(">>> loading feature pipeline and GBT model ...")
    val featurePipeline = PipelineModel.load(PipelinePath)
    val gbtModel        = GBTRegressionModel.load(ModelPath)
    println(s"    pipeline stages : ${featurePipeline.stages.length}")
    println(s"    GBT trees       : ${gbtModel.getNumTrees}, depth ${gbtModel.getMaxDepth}")

    // ------------------------------------------------------------------------
    // THE STREAM SOURCE
    //
    // maxFilesPerTrigger bounds how much a single batch ingests, so one large
    // drop cannot stall the stream. This is the File Source Engine the project
    // document specifies.
    // ------------------------------------------------------------------------
    val raw = spark.readStream
      .schema(InputSchema)
      .option("header", "true")
      .option("maxFilesPerTrigger", sys.env.getOrElse("AQ_MAX_FILES_PER_TRIGGER", "1"))
      .csv(StreamInput)

    val query = raw.writeStream
      .option("checkpointLocation", CheckpointDir)
      .foreachBatch { (batch: DataFrame, batchId: Long) =>

        val t0 = System.currentTimeMillis()
        val nIn = batch.count()
        if (nIn == 0) {
          println(s"[batch $batchId] empty, skipping")
        } else {

          // Mark the new rows so predictions can be restricted to them after the
          // history union.
          val incoming = batch
            .withColumn("timestamp", to_timestamp(col("from_date"), "yyyy-MM-dd HH:mm:ss"))
            .withColumn("_is_new", lit(true))
            .filter(col("timestamp").isNotNull)

          // ------------------------------------------------------------------
          // Union with retained history so the window features have something to
          // look back at. Without this a fresh station has no lag or rolling
          // values and every one of its rows would be dropped.
          // ------------------------------------------------------------------
          val history =
            try {
              spark.read.parquet(HistoryPath).withColumn("_is_new", lit(false))
            } catch {
              case _: Throwable =>
                println(s"[batch $batchId] no history yet - first run")
                incoming.limit(0)
            }

          val combined = history.select(incoming.columns.map(col): _*).union(incoming)

          // ------------------------------------------------------------------
          // Features -> vector -> prediction.
          // The model predicts the CHANGE in PM2.5, so the current level is added
          // back to recover the forecast. See 03_train_gbt.py for why predicting
          // the delta rather than the level doubles the gain over persistence.
          // ------------------------------------------------------------------
          val featured = buildFeatures(combined).filter(col("_is_new"))

          val assembled = featurePipeline.transform(featured)
          val predicted = gbtModel.transform(assembled)
            .withColumnRenamed("prediction", "_delta_pred")
            .withColumn("pm25_forecast",
              greatest(col("pm25") + col("_delta_pred"), lit(0.0)))

          // ------------------------------------------------------------------
          // FORECAST AQI
          //
          // The model forecasts PM2.5 only. The National AQI is the maximum
          // sub-index across all seven pollutants, so the forecast index is the
          // forecast PM2.5 sub-index taken against the CURRENT sub-indices of the
          // other six. That is a deliberate, disclosed approximation: it assumes
          // the other pollutants hold steady over the next hour. It is the
          // correct conservative choice for an alerting system, because it can
          // only ever under-state a rise driven by another pollutant, never
          // invent one.
          // ------------------------------------------------------------------
          val withAqi = predicted
            .withColumn("si_pm25_forecast", subIndex(col("pm25_forecast"), Breakpoints("pm25")))
            .withColumn("aqi_forecast",
              greatest(col("si_pm25_forecast"),
                       greatest(Breakpoints.keys.filter(_ != "pm25").toSeq
                                  .map(p => col(s"si_$p")): _*)))
            .withColumn("aqi_band", aqiBand(col("aqi_forecast")))
            .withColumn("forecast_for", col("timestamp") + expr("INTERVAL 1 HOUR"))
            .withColumn("generated_at", current_timestamp())

          val predictions = withAqi.select(
            col("station_id"), col("state"), col("city"),
            col("timestamp").as("observed_at"), col("forecast_for"),
            col("pm25").as("pm25_now"), col("pm25_forecast"),
            col("aqi_current"), col("aqi_forecast"), col("aqi_band"),
            col("aqi_dominant_pollutant"), col("generated_at")
          ).cache()

          val nPred = predictions.count()

          predictions.write.mode("append").parquet(PredictionPath)

          // ------------------------------------------------------------------
          // PHASE 8 - THE ALERT ENGINE
          // ------------------------------------------------------------------
          val alerts = predictions
            .filter(col("aqi_forecast") > lit(AlertThreshold))
            .withColumn("severity",
              when(col("aqi_forecast") > 400, "SEVERE")
                .when(col("aqi_forecast") > 300, "VERY_POOR")
                .when(col("aqi_forecast") > 200, "POOR")
                .otherwise("MODERATE"))
            .withColumn("message",
              concat(lit("Air quality warning for "), col("city"),
                     lit(" (station "), col("station_id"), lit("): forecast AQI "),
                     round(col("aqi_forecast"), 0).cast(IntegerType).cast(StringType),
                     lit(" ("), col("aqi_band"), lit("), driven by "),
                     col("aqi_dominant_pollutant"),
                     lit(". Forecast PM2.5 "),
                     round(col("pm25_forecast"), 1).cast(StringType),
                     lit(" ug/m3 by "), date_format(col("forecast_for"), "yyyy-MM-dd HH:mm"),
                     lit(".")))

          val nAlerts = alerts.count()
          if (nAlerts > 0) {
            alerts.write.mode("append").partitionBy("city").parquet(AlertPath)
            println(s"[batch $batchId] *** $nAlerts ALERTS ***")
            alerts.select("city", "station_id", "aqi_forecast", "severity", "message")
                  .orderBy(col("aqi_forecast").desc)
                  .show(5, truncate = false)
          }

          // ------------------------------------------------------------------
          // Update the history table, trimmed to the last HistoryHours per
          // station. Without the trim it grows without bound and every batch
          // gets slower than the last.
          // ------------------------------------------------------------------
          // `combined` carries `timestamp` but NOT `ts_unix`: that column is
          // derived inside buildFeatures and never propagates back out here.
          // Deriving it once and reusing it fixes an AnalysisException
          // (UNRESOLVED_COLUMN ts_unix) that aborted every batch at the
          // history-update step - the alerts above had already printed, so the
          // failure looked like the stream simply stalling after batch 0.
          val combinedTs = combined.withColumn("ts_unix", col("timestamp").cast(LongType))
          val cutoff = combinedTs.agg(max("ts_unix")).first().getLong(0) - HistoryHours * Hour
          val newHistory = combinedTs
            .filter(col("ts_unix") >= cutoff)
            .drop("ts_unix", "_is_new")
            .withColumn("_is_new", lit(false))

          // Write to a staging path then swap: overwriting a path that is also
          // an input to the same job truncates it before the read completes.
          val staging = s"${HistoryPath}_staging"
          newHistory.write.mode("overwrite").parquet(staging)
          spark.read.parquet(staging).write.mode("overwrite").parquet(HistoryPath)

          val ms = System.currentTimeMillis() - t0
          println(f"[batch $batchId%d] rows in=$nIn%,d  predicted=$nPred%,d  " +
                  f"alerts=$nAlerts%,d  latency=${ms}%,d ms")
          predictions.unpersist()
        }
        // foreachBatch requires (DataFrame, Long) => Unit. Without this the
        // if/else above infers Any - the empty-batch branch yields Unit while
        // this branch ends in unpersist(), which returns a Dataset - and no
        // foreachBatch overload accepts Any.
        ()
      }
      .trigger(org.apache.spark.sql.streaming.Trigger.ProcessingTime("10 seconds"))
      .start()

    println(">>> stream started. Drop CSV files into the watch directory.")
    println(s">>> stop with Ctrl-C, or: docker exec ... hdfs dfs -touchz $StreamInput/_STOP")
    query.awaitTermination()
  }
}
