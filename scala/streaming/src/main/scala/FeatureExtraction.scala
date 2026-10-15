// ============================================================================
// PHASE 4 - SPATIAL-TEMPORAL FEATURE ENGINEERING & VECTOR ASSEMBLY  (Scala)
// ============================================================================
// Project : A Scalable Big Data Platform for Real-Time Urban Air Quality
//           Tracking and Public Safety Alerting
// Course  : 23AID302 - Big Data Analytics
//
// READS   : hdfs://.../user/hadoop/lakehouse/clean_scala   (output of CleanSelect)
// WRITES  : hdfs://.../user/hadoop/lakehouse/features_scala
//           hdfs://.../user/hadoop/models/feature_pipeline_scala
//
// Scala port of scripts/02_feature_extraction.py. Run both on the same input
// and the row counts match at every stage - that is the check that the port is
// correct rather than merely plausible.
//
// ----------------------------------------------------------------------------
// WHAT THIS BUILDS
//   A. A temporally validated T+1 label
//   B. CPCB National AQI, current and next hour
//   C. Rolling and lag history features
//   D. Cyclical encodings
//   E. Physical interaction features
//   F. One-hot categoricals + VectorAssembler -> the `features` column
//
// ----------------------------------------------------------------------------
// WHY THE LABEL IS NOT BUILT WITH A PLAIN lead()
// ----------------------------------------------------------------------------
// lead() is POSITIONAL, not temporal. pm25 is only ~73% populated, so gaps are
// everywhere. Where a station skips five hours, lead() returns the row five
// hours later and labels it "next hour". The model then trains on a mislabelled
// forecast horizon and its RMSE means nothing.
//
// The fix below leads BOTH pm25 and the timestamp, and accepts the label only
// when the next row is genuinely 3600 seconds ahead. Rows that fail are dropped
// rather than mislabelled, and the retention rate is printed so the loss is
// visible instead of silent.
//
// ----------------------------------------------------------------------------
// RUN
//   sbt package
//   spark-submit --class FeatureExtraction --master "local[*]" \
//     --driver-memory 8g target/scala-2.12/airquality-streaming_2.12-1.0.jar
// ============================================================================

import org.apache.spark.sql.{Column, DataFrame, SparkSession}
import org.apache.spark.sql.expressions.Window
import org.apache.spark.sql.functions._
import org.apache.spark.sql.types._
import org.apache.spark.ml.Pipeline
import org.apache.spark.ml.feature.{StringIndexer, OneHotEncoder, VectorAssembler}

object FeatureExtraction {

  private val Lake = sys.env.getOrElse("AQ_LAKE", "hdfs://namenode:9000/user/hadoop")
  private val CleanPath    = s"$Lake/lakehouse/clean_scala"
  private val FeaturePath  = s"$Lake/lakehouse/features_scala"
  private val PipelinePath = s"$Lake/models/feature_pipeline_scala"

  private val Hour = 3600L
  private val BAR = "=" * 74
  private val SUB = "-" * 74

  // --------------------------------------------------------------------------
  // CPCB NATIONAL AQI BREAKPOINTS
  // (C_low, C_high, I_low, I_high). The National AQI is the MAXIMUM of the
  // sub-indices over these seven pollutants - which is why exactly these seven
  // were the ones kept during cleaning. The alert rule "predicted AQI > 150" is
  // undefined without all of them.
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

  // CPCB averaging period per pollutant, in hours. 24h for the particulates and
  // NO2/SO2/NH3, 8h for CO and ozone.
  private val AqiWindowH = Map("pm25"->24,"pm10"->24,"no2"->24,"so2"->24,"nh3"->24,"co"->8,"o3"->8)

  private val Categoricals = Seq("season", "weather_condition", "climate_type")

  // The 54 numeric model inputs. Order is irrelevant to VectorAssembler, which
  // resolves by name - but the NAMES are load-bearing and must match Phase 4's
  // PySpark implementation exactly.
  private val NumericFeatures = Seq(
    // current pollutant concentrations
    "pm25", "pm10", "no2", "so2", "co", "o3", "nh3",
    // aggregated air-quality state
    "aqi_current", "pm25_avg24h", "pm10_avg24h", "co_avg8h", "o3_avg8h",
    // history and trend
    "pm25_lag_1h", "pm25_delta_1h", "pm25_roll_3h", "pm25_roll_6h",
    "pm25_std_6h", "pm10_roll_6h", "no2_roll_6h", "aqi_roll_6h",
    "pm25_surge_ratio",
    // meteorology
    "temperature_c", "humidity_percent", "wind_speed_ms", "rainfall_mm",
    "solar_radiation", "pressure", "wd_sin", "wd_cos",
    // traffic
    "traffic_index", "is_rush_hour",
    // temporal
    "hour_sin", "hour_cos", "month_sin", "month_cos", "dow_sin", "dow_cos",
    "is_weekend",
    // city descriptor
    "urbanization_index",
    // physical interactions
    "ventilation_index", "is_raining", "scrub_factor", "stagnation_index",
    "temp_humidity_interaction",
    // imputation provenance - missingness is informative, sensors drop out
    // during extreme events
    "pm25_was_imputed", "pm10_was_imputed", "no2_was_imputed",
    "so2_was_imputed", "co_was_imputed", "o3_was_imputed", "nh3_was_imputed",
    "solar_radiation_was_imputed", "pressure_was_imputed", "wd_degree_was_imputed"
  )

  /** Piecewise-linear CPCB sub-index. Built from nested when/otherwise so it
    * stays a Catalyst expression - no UDF, so nothing serialises out of the JVM. */
  private def subIndex(c: Column, bps: Seq[(Double, Double, Double, Double)]): Column = {
    var expr: Column = lit(500.0)   // above the top band, saturate
    bps.reverse.foreach { case (cLo, cHi, iLo, iHi) =>
      expr = when(c <= cHi, (lit(iHi - iLo) / lit(cHi - cLo)) * (c - lit(cLo)) + lit(iLo))
             .otherwise(expr)
    }
    when(c.isNull, lit(null).cast(DoubleType)).otherwise(expr)
  }

  def main(args: Array[String]): Unit = {

    val spark = SparkSession.builder()
      .appName("AirQuality_Phase4_FeatureExtraction_Scala")
      .config("spark.sql.parquet.compression.codec", "snappy")
      .config("spark.sql.adaptive.enabled", "true")
      .config("spark.sql.shuffle.partitions",
              sys.env.getOrElse("AQ_SHUFFLE_PARTITIONS", "200"))
      .getOrCreate()

    spark.sparkContext.setLogLevel("WARN")
    val t0 = System.currentTimeMillis()

    println(BAR)
    println("  PHASE 4 - FEATURE ENGINEERING & VECTOR ASSEMBLY  (Scala)")
    println(BAR)
    println(s"  Spark   : ${spark.version}")
    println(s"  Scala   : ${scala.util.Properties.versionNumberString}")
    println(s"  reading : $CleanPath")
    println(s"  writing : $FeaturePath")
    println(BAR)

    var df = spark.read.parquet(CleanPath)
    val rowsIn = df.count()
    println(f"  >>> loaded $rowsIn%,d cleaned rows from HDFS")

    // ------------------------------------------------------------------------
    // STEP 0 - MAKE THE TIME SERIES WELL-FORMED
    //
    // Every window below orders by time, which is only meaningful if one
    // (station, hour) maps to one row. Deduplicate first: without this both the
    // rolling averages and the T+1 label are non-deterministic.
    // ------------------------------------------------------------------------
    df = df.withColumn("ts_unix", col("timestamp").cast(LongType))

    val dedupW = Window.partitionBy("station_id", "variation_bucket", "ts_unix")
                       .orderBy(col("pm25").desc_nulls_last)
    df = df.withColumn("_rn", row_number().over(dedupW)).filter(col("_rn") === 1).drop("_rn")

    val rowsDedup = df.count()
    println(f"  >>> after dedupe on (station_id, hour): $rowsDedup%,d " +
            f"(${100.0 * rowsDedup / rowsIn}%.2f%% retained)")

    // The single ordering used by every time-aware feature below.
    val track = Window.partitionBy("station_id", "variation_bucket").orderBy("ts_unix")

    // rangeBetween operates on the VALUE of ts_unix, not row position, so a
    // missing hour SHORTENS the window rather than silently reaching further
    // back in time. This is what makes the rolling features gap-safe.
    def hoursBack(n: Int) =
      Window.partitionBy("station_id", "variation_bucket")
            .orderBy("ts_unix")
            .rangeBetween(-(n - 1).toLong * Hour, 0L)

    // ------------------------------------------------------------------------
    // STEP B - CPCB ROLLING AVERAGES AND CURRENT AQI
    // AQI is defined on averaged concentrations, never instantaneous ones.
    // ------------------------------------------------------------------------
    AqiWindowH.foreach { case (p, h) =>
      df = df.withColumn(s"${p}_avg${h}h", avg(col(p)).over(hoursBack(h)))
    }
    Breakpoints.keys.foreach { p =>
      df = df.withColumn(s"si_$p", subIndex(col(s"${p}_avg${AqiWindowH(p)}h"), Breakpoints(p)))
    }
    df = df.withColumn("aqi_current", greatest(Breakpoints.keys.toSeq.map(p => col(s"si_$p")): _*))

    // Record WHICH pollutant drives the index - the alert message needs to name
    // it ("AQI 187, driven by PM2.5").
    val siPairs = array(Breakpoints.keys.toSeq.map(p =>
      struct(col(s"si_$p").as("v"), lit(p).as("p"))): _*)
    df = df.withColumn("aqi_dominant_pollutant",
      sort_array(siPairs, asc = false).getItem(0).getField("p"))

    // ------------------------------------------------------------------------
    // STEP A - THE T+1 LABEL, TEMPORALLY VALIDATED
    //
    // The label comes from pm25_measured, NOT the imputed pm25. A label that is
    // a station/month/hour median is unlearnable from the features and directly
    // suppresses R2 - roughly 27% of pm25 values are imputed, so this is the
    // difference between training on truth and training on 27% fabrication.
    // ------------------------------------------------------------------------
    df = df
      .withColumn("_next_ts",   lead("ts_unix", 1).over(track))
      .withColumn("_next_pm25", lead("pm25_measured", 1).over(track))
      .withColumn("_next_aqi",  lead("aqi_current", 1).over(track))
      // THE GUARD: accept the label only if the next row really is +1 hour.
      .withColumn("_gap_ok", (col("_next_ts") - col("ts_unix")) === lit(Hour))

    df = df.filter(col("_gap_ok") && col("_next_pm25").isNotNull)
           .withColumnRenamed("_next_pm25", "target_pm25_next_hour")
           .withColumnRenamed("_next_aqi",  "target_aqi_next_hour")
           .drop("_next_ts", "_gap_ok")

    val rowsLabelled = df.count()
    println(f"  >>> rows with a VALID +1h label: $rowsLabelled%,d " +
            f"(${100.0 * rowsLabelled / rowsDedup}%.2f%% of dedup rows)")
    println("      the remainder were dropped rather than mislabelled - a plain")
    println("      lead() would have kept them with a wrong forecast horizon.")

    // ------------------------------------------------------------------------
    // STEP C - HISTORY FEATURES
    // Next-hour pollution is dominated by current pollution and its recent
    // trend. Without these, the model must infer persistence from weather alone.
    // ------------------------------------------------------------------------
    df = df
      .withColumn("_lag_ts",   lag("ts_unix", 1).over(track))
      .withColumn("_lag_pm25", lag("pm25", 1).over(track))
      // Same temporal guard as the label: a lag is only a "1 hour ago" value if
      // the previous row is actually 1 hour behind.
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
      // Ratio > 1 means the last 3 hours are dirtier than the last 24 - a
      // compact "surge in progress" signal, precisely what the alert engine
      // exists to catch.
      .withColumn("pm25_surge_ratio", col("pm25_roll_3h") / (col("pm25_avg24h") + lit(1e-6)))
      .na.fill(0.0, Seq("pm25_std_6h", "pm25_delta_1h"))

    // ------------------------------------------------------------------------
    // STEP D - CYCLICAL ENCODINGS
    // hour 23 and hour 0 are one hour apart, but as raw integers they are 23
    // apart. Sin/cos pairs restore the true adjacency. Same for month, weekday
    // and wind direction (359 and 1 degrees are 2 degrees apart).
    // ------------------------------------------------------------------------
    val twoPi = 2.0 * math.Pi
    Seq(("hour", 24.0, "hour"), ("month", 12.0, "month"), ("day_of_week", 7.0, "dow"))
      .foreach { case (c, period, name) =>
        val ang = (col(c) / lit(period)) * lit(twoPi)
        df = df.withColumn(s"${name}_sin", sin(ang)).withColumn(s"${name}_cos", cos(ang))
      }
    val wdRad = radians(col("wd_degree"))
    df = df.withColumn("wd_sin", sin(wdRad)).withColumn("wd_cos", cos(wdRad))

    // ------------------------------------------------------------------------
    // STEP E - PHYSICAL INTERACTION FEATURES
    // Trees split one variable at a time, so a ratio that matters physically is
    // expensive for them to reconstruct. Handing it over directly is cheap.
    // ------------------------------------------------------------------------
    df = df
      // Emission load divided by the wind that disperses it. High traffic plus
      // dead air is the classic trapping condition.
      .withColumn("ventilation_index", col("traffic_index") / (col("wind_speed_ms") + lit(0.5)))
      // Rain physically scrubs PM out of the air; the first mm does most of the
      // washout, hence log1p rather than a linear term.
      .withColumn("is_raining", (col("rainfall_mm") > 0.1).cast(IntegerType))
      .withColumn("scrub_factor", log1p(col("rainfall_mm")))
      // Warm, dry, still air holds particulates near the surface.
      .withColumn("stagnation_index",
        (lit(100.0) - col("humidity_percent")) / (col("wind_speed_ms") + lit(0.5)))
      .withColumn("temp_humidity_interaction",
        col("temperature_c") * col("humidity_percent") / lit(100.0))

    // ------------------------------------------------------------------------
    // STEP F - CATEGORICAL ENCODING AND VECTOR ASSEMBLY
    //
    // `city` (241 values) and `station_id` (4,077) are deliberately NOT one-hot
    // encoded. At that cardinality one-hot would add thousands of sparse columns,
    // inflate every split search, and teach the model to memorise locations
    // instead of learning the physics. climate_type (16) plus the continuous
    // urbanization_index carry the same city-level signal far more compactly.
    // ------------------------------------------------------------------------
    val indexers = Categoricals.map(c =>
      new StringIndexer().setInputCol(c).setOutputCol(s"${c}_idx").setHandleInvalid("keep"))
    val encoder = new OneHotEncoder()
      .setInputCols(Categoricals.map(c => s"${c}_idx").toArray)
      .setOutputCols(Categoricals.map(c => s"${c}_ohe").toArray)
      .setHandleInvalid("keep")
    val assembler = new VectorAssembler()
      .setInputCols((NumericFeatures ++ Categoricals.map(c => s"${c}_ohe")).toArray)
      .setOutputCol("features")
      .setHandleInvalid("skip")

    val pipeline = new Pipeline().setStages((indexers :+ encoder :+ assembler).toArray)
    val model = pipeline.fit(df)
    model.write.overwrite().save(PipelinePath)

    // ------------------------------------------------------------------------
    // DROP UNASSEMBLABLE ROWS HERE, VISIBLY.
    //
    // VectorAssembler(handleInvalid="skip") silently discards any row with a
    // null in any input column. Rows at the start of each station's series
    // legitimately have null lags and rolling windows. Removing them explicitly,
    // with the retention rate printed, is the difference between a measured loss
    // and the silent row deletion that helped produce the old R2 = 0.58.
    // ------------------------------------------------------------------------
    val beforeAssemble = df.count()
    df = df.na.drop(NumericFeatures)
    val afterAssemble = df.count()
    println(f"  >>> rows assemblable into a complete feature vector: $afterAssemble%,d " +
            f"(${100.0 * afterAssemble / beforeAssemble}%.2f%% of labelled rows)")

    // ------------------------------------------------------------------------
    // STEP G - PERSIST
    //
    // The feature COLUMNS are written, not the assembled vector. Measured on the
    // PySpark implementation, persisting the ~86-slot dense vector cost 370
    // bytes/row against 227 for the columns: about 29 of its slots are one-hot
    // indicators materialised as explicit doubles, and Parquet cannot compress
    // inside a vector. The fitted pipeline above reassembles it on read.
    // ------------------------------------------------------------------------
    val carried = Seq("station_id", "state", "city", "timestamp", "ts_unix",
                      "year", "month", "hour",
                      "target_pm25_next_hour", "target_aqi_next_hour",
                      "aqi_dominant_pollutant", "data_source")
    val selectCols = (carried ++ NumericFeatures ++ Categoricals).distinct

    df.select(selectCols.map(col): _*)
      .repartition(col("city"))
      .write.mode("overwrite")
      .partitionBy("city")
      .option("compression", "snappy")
      .parquet(FeaturePath)

    // ------------------------------------------------------------------------
    // SUMMARY
    // ------------------------------------------------------------------------
    val ohe = model.stages(Categoricals.length)
      .asInstanceOf[org.apache.spark.ml.feature.OneHotEncoderModel]
    val oheWidth = ohe.categorySizes.sum
    val secs = (System.currentTimeMillis() - t0) / 1000.0

    println()
    println(BAR)
    println("  PHASE 4 COMPLETE  (Scala)")
    println(BAR)
    println(f"  rows in            : $rowsIn%,d")
    println(f"  rows after dedupe  : $rowsDedup%,d")
    println(f"  rows with T+1 label: $rowsLabelled%,d")
    println(f"  rows assemblable   : $afterAssemble%,d")
    println(s"  numeric features   : ${NumericFeatures.length}  (persisted as columns)")
    println(s"  one-hot width      : $oheWidth  (${Categoricals.mkString(", ")})")
    println(s"  FEATURE VECTOR DIM : ${NumericFeatures.length + oheWidth}")
    println(s"  partitioned by     : city")
    println(s"  output             : $FeaturePath")
    println(s"  pipeline           : $PipelinePath")
    println(f"  elapsed            : $secs%.1f s")
    println(BAR)

    spark.stop()
  }
}
