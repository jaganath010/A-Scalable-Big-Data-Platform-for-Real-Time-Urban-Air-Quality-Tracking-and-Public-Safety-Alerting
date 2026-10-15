import org.apache.spark.sql.{Column, DataFrame, SparkSession}
import org.apache.spark.sql.functions._
import org.apache.spark.sql.types._

object CleanSelect {

  private val Lake = sys.env.getOrElse("AQ_LAKE", "hdfs://localhost:9000/user/hadoop")
  private val RawPath   = s"$Lake/lakehouse/raw"
  private val CleanPath = s"$Lake/lakehouse/clean_scala"

  // The 7 pollutants defining the CPCB National AQI.
  private val AqiPollutants = Seq("pm25", "pm10", "no2", "so2", "co", "o3", "nh3")

  // Everything that gets imputed: the AQI pollutants plus three meteorological
  // fields the model depends on.
  private val ImputeCols = AqiPollutants ++ Seq("solar_radiation", "pressure", "wd_degree")

  // Physically valid ranges. Anything outside is a sensor fault, not a reading.
  // Upper bounds sit well above observed maxima so genuine extremes survive.
  private val ValidRange: Map[String, (Double, Double)] = Map(
    "pm25" -> (0.0, 2000.0),
    "pm10" -> (0.0, 3000.0),
    "no2"  -> (0.0, 1000.0),
    "so2"  -> (0.0, 2000.0),
    "co"   -> (0.0,  100.0),   // mg/m3
    "o3"   -> (0.0, 1000.0),
    "nh3"  -> (0.0, 2000.0),
    "solar_radiation" -> (0.0, 1500.0),    // W/m2
    "pressure"        -> (700.0, 1100.0)   // mmHg-scaled instrument range
  )

  // The 32 columns of the expanded dataset, in file order.
  private val InputSchema = StructType(Seq(
    StructField("station_id",         StringType),
    StructField("state",              StringType),
    StructField("city",               StringType),
    StructField("from_date",          StringType),
    StructField("pm25",               StringType),
    StructField("pm10",               StringType),
    StructField("no2",                StringType),
    StructField("so2",                StringType),
    StructField("co",                 StringType),
    StructField("o3",                 StringType),
    StructField("nh3",                StringType),
    StructField("wd_degree",          StringType),
    StructField("solar_radiation",    StringType),
    StructField("pressure",           StringType),
    StructField("temperature_c",      StringType),
    StructField("humidity_percent",   StringType),
    StructField("wind_speed_ms",      StringType),
    StructField("rainfall_mm",        StringType),
    StructField("weather_condition",  StringType),
    StructField("traffic_index",      StringType),
    StructField("is_rush_hour",       StringType),
    StructField("year",               StringType),
    StructField("month",              StringType),
    StructField("day",                StringType),
    StructField("hour",               StringType),
    StructField("day_of_week",        StringType),
    StructField("is_weekend",         StringType),
    StructField("season",             StringType),
    StructField("climate_type",       StringType),
    StructField("urbanization_index", StringType),
    StructField("data_source",        StringType),
    StructField("source_station",     StringType)
  ))

  private val BAR = "=" * 74
  private val SUB = "-" * 74

  def main(args: Array[String]): Unit = {

    val limitFiles = if (args.nonEmpty) args(0).toInt else 0

    val spark = SparkSession.builder()
      .appName("AirQuality_Phase3_CleanSelect_Scala")
      .config("spark.sql.parquet.compression.codec", "snappy")
      .config("spark.sql.sources.partitionOverwriteMode", "dynamic")
      .config("spark.sql.adaptive.enabled", "true")
      .config("spark.sql.shuffle.partitions",
              sys.env.getOrElse("AQ_SHUFFLE_PARTITIONS", "200"))
      .getOrCreate()

    import spark.implicits._
    spark.sparkContext.setLogLevel("WARN")

    val t0 = System.currentTimeMillis()

    println(BAR)
    println("  PHASE 3 - DATA CLEANING & PREPROCESSING  (Scala implementation)")
    println(BAR)
    println(s"  Spark version : ${spark.version}")
    println(s"  Scala version : ${scala.util.Properties.versionNumberString}")
    println(s"  reading from  : $RawPath")
    println(s"  writing to    : $CleanPath")

    // ------------------------------------------------------------------------
    // STEP 1 - READ FROM HDFS WITH AN EXPLICIT SCHEMA
    //
    // Every field is read as StringType then cast deliberately. Reading straight
    // to DoubleType would make Spark null out any malformed cell silently;
    // casting ourselves means a parse failure is a measurable event.
    // ------------------------------------------------------------------------
    val inputPath =
      if (limitFiles > 0) {
        // Whole files, never sampled rows - sampling would punch holes in each
        // station's hourly series.
        val fs = org.apache.hadoop.fs.FileSystem.get(
          new java.net.URI(Lake), spark.sparkContext.hadoopConfiguration)
        val files = fs.globStatus(new org.apache.hadoop.fs.Path(s"$RawPath/part-*.csv"))
          .map(_.getPath.toString).sorted.take(limitFiles)
        println(s"  files         : ${files.length} of 23 (demo mode)")
        files
      } else {
        println(s"  files         : all 23")
        Array(s"$RawPath/part-*.csv")
      }
    println(BAR)

    val raw = spark.read
      .option("header", "true")
      .option("mode", "PERMISSIVE")
      .schema(InputSchema)
      .csv(inputPath: _*)

    // ------------------------------------------------------------------------
    // STEP 2 - TYPE CASTING AND TIMESTAMP PARSING
    // ------------------------------------------------------------------------
    var df = raw.select(
      col("station_id"),
      col("state"),
      col("city"),
      to_timestamp(col("from_date"), "yyyy-MM-dd HH:mm:ss").as("timestamp"),

      // the 7 CPCB AQI pollutants
      col("pm25").cast(DoubleType).as("pm25"),
      col("pm10").cast(DoubleType).as("pm10"),
      col("no2").cast(DoubleType).as("no2"),
      col("so2").cast(DoubleType).as("so2"),
      col("co").cast(DoubleType).as("co"),
      col("o3").cast(DoubleType).as("o3"),
      col("nh3").cast(DoubleType).as("nh3"),

      col("wd_degree").cast(DoubleType).as("wd_degree"),
      col("solar_radiation").cast(DoubleType).as("solar_radiation"),
      col("pressure").cast(DoubleType).as("pressure"),

      col("temperature_c").cast(DoubleType).as("temperature_c"),
      col("humidity_percent").cast(DoubleType).as("humidity_percent"),
      col("wind_speed_ms").cast(DoubleType).as("wind_speed_ms"),
      col("rainfall_mm").cast(DoubleType).as("rainfall_mm"),
      col("weather_condition"),

      col("traffic_index").cast(DoubleType).as("traffic_index"),
      col("is_rush_hour").cast(DoubleType).as("_is_rush_hour_raw"),
      col("year").cast(IntegerType).as("year"),
      col("month").cast(IntegerType).as("month"),
      col("day").cast(IntegerType).as("day"),
      col("hour").cast(IntegerType).as("hour"),
      col("day_of_week").cast(IntegerType).as("day_of_week"),
      col("is_weekend").cast(DoubleType).as("_is_weekend_raw"),
      col("season"),

      col("climate_type"),
      col("urbanization_index").cast(DoubleType).as("urbanization_index"),

      // Provenance. data_source is what makes "evaluate on real rows only" a
      // single filter rather than an assertion.
      col("data_source"),
      col("source_station")
    )

    val rowsIn = df.count()
    println(f"  >>> rows read from HDFS: $rowsIn%,d")

    // ------------------------------------------------------------------------
    // STEP 3 - REPAIR BINARY FLAGS
    //
    // The original expansion applied +/-3% Gaussian noise to every numeric
    // column without excluding binary flags, leaving is_rush_hour with 24,725
    // distinct values instead of 2. Rounding restores them. Kept as a guard even
    // though the rebuilt dataset is already correct, because the streaming layer
    // pushes unvalidated live sensor frames through this same logic.
    // ------------------------------------------------------------------------
    df = df
      .withColumn("is_rush_hour", (round(col("_is_rush_hour_raw")) > 0).cast(IntegerType))
      .withColumn("is_weekend",   (round(col("_is_weekend_raw"))   > 0).cast(IntegerType))
      .withColumn("variation_bucket", lit(0))
      .drop("_is_rush_hour_raw", "_is_weekend_raw")

    // ------------------------------------------------------------------------
    // STEP 4 - PHYSICAL RANGE CLAMPING
    // Relative humidity cannot exceed 100%; the traffic index is defined 0-100;
    // wind direction is circular; rainfall and wind speed cannot be negative.
    // ------------------------------------------------------------------------
    df = df
      .withColumn("humidity_percent",
        least(greatest(col("humidity_percent"), lit(0.0)), lit(100.0)))
      .withColumn("traffic_index",
        least(greatest(col("traffic_index"), lit(0.0)), lit(100.0)))
      .withColumn("wd_degree", col("wd_degree") % 360.0)
      .withColumn("rainfall_mm", greatest(col("rainfall_mm"), lit(0.0)))
      .withColumn("wind_speed_ms", greatest(col("wind_speed_ms"), lit(0.0)))

    // ------------------------------------------------------------------------
    // STEP 5 - ANOMALY ERADICATION
    // Out-of-range sensor readings become NULL, then get imputed in step 7.
    // ------------------------------------------------------------------------
    ValidRange.foreach { case (c, (lo, hi)) =>
      df = df.withColumn(c,
        when(col(c).between(lo, hi), col(c)).otherwise(lit(null).cast(DoubleType)))
    }

    // A row without a usable timestamp cannot be windowed or partitioned.
    df = df.filter(col("timestamp").isNotNull)

    // ------------------------------------------------------------------------
    // STEP 6 - PROTECT THE FORECASTING TARGET
    //
    // pm25 is both a feature and the source of the T+1 label. If the label is a
    // station/month/hour median, the model is asked to predict a constant it
    // cannot derive from the features - unlearnable noise that caps R2 hard.
    // pm25_measured preserves the pre-imputation truth; Phase 4 builds the label
    // only from this column.
    // ------------------------------------------------------------------------
    df = df.withColumn("pm25_measured", col("pm25"))

    // Flag what is about to be filled, BEFORE filling it.
    ImputeCols.foreach { c =>
      df = df.withColumn(s"${c}_was_imputed", col(c).isNull.cast(IntegerType))
    }

    df.cache()

    // ------------------------------------------------------------------------
    // STEP 7 - THREE-TIER MEDIAN IMPUTATION
    //
    // Only about 46% of rows carry all seven pollutants simultaneously.
    // Dropping incomplete rows would discard tens of millions and destroy the
    // Volume claim, so imputation is mandatory. Tiers, most specific first:
    //
    //   T1  median by (station_id, month, hour)  - the station's own diurnal
    //                                              and seasonal cycle
    //   T2  median by (city, month)              - for thin stations
    //   T3  global median                        - last resort
    //
    // T1 and T2 are small enough to broadcast, which turns two shuffle joins
    // into map-side joins against the very large fact table.
    // ------------------------------------------------------------------------
    def med(c: String): Column = expr(s"percentile_approx($c, 0.5, 1000)")

    val t1 = df.groupBy("station_id", "month", "hour")
               .agg(med(ImputeCols.head).as(s"${ImputeCols.head}__t1"),
                    ImputeCols.tail.map(c => med(c).as(s"${c}__t1")): _*)

    val t2 = df.groupBy("city", "month")
               .agg(med(ImputeCols.head).as(s"${ImputeCols.head}__t2"),
                    ImputeCols.tail.map(c => med(c).as(s"${c}__t2")): _*)

    val t3Row = df.agg(med(ImputeCols.head).as(ImputeCols.head),
                       ImputeCols.tail.map(c => med(c).as(c)): _*).first()
    val t3 = ImputeCols.map(c => c -> Option(t3Row.getAs[Any](c))
                                       .map(_.toString.toDouble).getOrElse(0.0)).toMap

    df = df.join(broadcast(t1), Seq("station_id", "month", "hour"), "left")
           .join(broadcast(t2), Seq("city", "month"), "left")

    ImputeCols.foreach { c =>
      df = df.withColumn(c,
        coalesce(col(c), col(s"${c}__t1"), col(s"${c}__t2"), lit(t3(c))))
        .drop(s"${c}__t1", s"${c}__t2")
    }

    // ------------------------------------------------------------------------
    // STEP 8 - WRITE THE PROCESSED DATASET BACK TO HDFS
    //
    // Partitioning by city gives predicate pushdown - a query for one city reads
    // one directory instead of the whole dataset - while keeping file sizes in
    // the right order of magnitude for a 128 MB HDFS block.
    //
    // Partitioning additionally by (year, month) was measured to produce 5,237
    // files with a 244 KB median from a single input part. On HDFS every file
    // occupies at least one block, so tens of thousands of tiny files would
    // destroy the block-level parallelism the project depends on.
    // ------------------------------------------------------------------------
    val out = df.repartition(col("city"))

    out.write
      .mode("overwrite")
      .partitionBy("city")
      .option("compression", "snappy")
      .parquet(CleanPath)

    // ------------------------------------------------------------------------
    // STEP 9 - AUDIT SUMMARY
    // ------------------------------------------------------------------------
    val total = df.count()
    val secs  = (System.currentTimeMillis() - t0) / 1000.0

    println()
    println(BAR)
    println("  PHASE 3 COMPLETE  (Scala)")
    println(BAR)
    println(f"  rows in       : $rowsIn%,d")
    println(f"  rows written  : $total%,d")
    println(s"  columns       : 32 -> ${out.columns.length}")
    println(s"  input         : $RawPath   (HDFS)")
    println(s"  output        : $CleanPath (HDFS)")
    println(f"  elapsed       : $secs%.1f s")
    println(SUB)
    println("  PREPROCESSING OPERATIONS PERFORMED")
    println("    1. Explicit 32-column schema, no inference")
    println("    2. Type casting: text -> double / int / timestamp")
    println("    3. Timestamp parsing; unparseable rows dropped")
    println("    4. Binary flag repair (is_rush_hour, is_weekend -> strict 0/1)")
    println("    5. Physical range clamping (humidity 0-100, traffic 0-100,")
    println("       wind direction mod 360, rainfall and wind speed >= 0)")
    println("    6. Anomaly eradication: out-of-range readings nulled")
    println("    7. Three-tier median imputation")
    println("       station/month/hour -> city/month -> global")
    println("    8. Imputation provenance flags (one per imputed column)")
    println("    9. Label protection: pm25_measured keeps pre-imputation truth")
    println("   10. Columnar conversion: Snappy Parquet, partitioned by city")
    println(SUB)
    println(f"  output format : Snappy-compressed Parquet")
    println(f"  partitioned by: city  (one directory per city)")
    println(SUB)
    println("  imputation rate per column (fraction filled, not measured):")
    val rates = df.agg(avg(s"${ImputeCols.head}_was_imputed").as(ImputeCols.head),
                       ImputeCols.tail.map(c => avg(s"${c}_was_imputed").as(c)): _*).first()
    ImputeCols.foreach { c =>
      println(f"    $c%-22s ${100.0 * rates.getAs[Double](c)}%6.2f%%")
    }
    println(BAR)
    println()
    println("  Verify from the cluster:")
    println(s"    hdfs dfs -du -s -h ${CleanPath.replaceAll("^hdfs://[^/]+", "")}")
    println(s"    hdfs fsck ${CleanPath.replaceAll("^hdfs://[^/]+", "")}")
    println(BAR)

    df.unpersist()
    spark.stop()
  }
}
