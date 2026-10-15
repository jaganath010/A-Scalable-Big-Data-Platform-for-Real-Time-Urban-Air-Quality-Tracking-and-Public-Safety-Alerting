// ============================================================================
// PHASE 8b - LIVE ENRICHMENT
// 23AID302 - Big Data Analytics
//
// THE PROBLEM THIS SOLVES
//   The trained GBT consumes 54 numeric features. Raw CAMS air-quality JSON
//   supplies only 28 of them; the other 26 (weather, weather-derived physics,
//   traffic, and the provenance flags) simply are not in that payload. So the
//   live feed CANNOT be scored by the model as it arrives - Phase 7's stream
//   was demonstrated by replaying rows already in the structured 32-column
//   schema, which is not the same thing as consuming a live payload.
//
//   This job closes that gap. It joins three sources and emits exactly the
//   32-column schema AirQualityStream.InputSchema expects, so the live feed
//   drops straight into the existing stream with no change to Phase 7.
//
//        CAMS air-quality JSON  (semi-structured, nested)  --+
//        Open-Meteo weather JSON (semi-structured, nested)  -+--> 32-col CSV
//        city_profiles.csv       (structured, flat)         --+
//
//   That join is the project's Variety claim doing actual work: two nested
//   self-describing JSON payloads reconciled against a flat fixed-schema CSV
//   inside one Spark job.
//
// WHY SCALA
//   Same reason CleanSelect.scala and FeatureExtraction.scala are Scala:
//   Spark cannot spawn Python worker processes on this machine, so anything
//   that must run on the cluster is written for the JVM.
//
// NOTHING IS INVENTED
//   Pollutants and weather are both real API responses, stored and read
//   verbatim. Traffic terms are computed from THIS PROJECT'S OWN published
//   city_profiles.csv using the same multipliers the dataset generator used,
//   so a live row's traffic_index is produced the same way a training row's
//   was. Where the API returns nothing (ammonia is null across this whole
//   region), the value stays null and the matching *_was_imputed flag records
//   it downstream rather than a number being fabricated.
//
// UNIT CONVERSIONS - these are not cosmetic, they were measured
//   CO        CAMS reports ug/m3; the structured schema (and therefore the
//             model) expects mg/m3. Ratio 1000. Feeding raw CAMS CO would put
//             the feature ~1000x out of range. Cross-validation measured
//             structured CO mean 0.95 mg/m3 against CAMS 566.08 ug/m3.
//   PRESSURE  Open-Meteo reports hPa; the structured schema expects mmHg
//             (measured median 753). Factor 0.750062.
//   WIND      requested from the API directly in m/s (wind_speed_unit=ms),
//             so no conversion is applied here.
//
// RUN
//   spark-submit --class LiveEnrichment airquality-streaming_2.12-1.0.jar \
//       <cams_json_dir> <weather_json_dir> <city_profiles.csv> <out_dir>
// ============================================================================

import org.apache.spark.sql.{DataFrame, SparkSession}
import org.apache.spark.sql.functions._
import org.apache.spark.sql.types._

object LiveEnrichment {

  // The exact column order AirQualityStream.InputSchema expects. Emitting
  // these in a different order would still parse (header-based) but keeping
  // them aligned makes the contract between the two jobs obvious.
  private val OutputCols = Seq(
    "station_id", "state", "city", "from_date",
    "pm25", "pm10", "no2", "so2", "co", "o3", "nh3",
    "wd_degree", "solar_radiation", "pressure",
    "temperature_c", "humidity_percent", "wind_speed_ms", "rainfall_mm",
    "weather_condition", "traffic_index", "is_rush_hour",
    "year", "month", "day", "hour", "day_of_week", "is_weekend",
    "season", "climate_type", "urbanization_index",
    "data_source", "source_station"
  )

  private val UG_PER_MG = 1000.0
  private val HPA_TO_MMHG = 0.750062

  // --------------------------------------------------------------------------
  // Flatten one hourly struct-of-arrays payload into rows.
  // Open-Meteo returns `hourly: { time: [...], pm2_5: [...], ... }` - parallel
  // arrays, not an array of records - so arrays_zip is the correct primitive.
  // --------------------------------------------------------------------------
  private def explodeHourly(df: DataFrame, fields: Seq[String]): DataFrame = {
    val zipped = arrays_zip(fields.map(f => col(s"hourly.$f")): _*)
    df.withColumn("_file", input_file_name())
      .select(col("_file"), explode(zipped).alias("r"))
      .select(col("_file") +: fields.map(f => col(s"r.$f").alias(f)): _*)
  }

  // Basename of a path, used to join a payload back to the city that produced
  // it. Exact equality on the basename - NOT `contains` - because
  // "navi_mumbai.json" contains "mumbai.json" as a literal substring and a
  // substring join silently double-counts those cities. That exact bug was
  // found and fixed in the batch merge; the same trap applies here.
  private def basename(c: org.apache.spark.sql.Column) =
    element_at(split(c, "[/\\\\]"), -1)

  def main(args: Array[String]): Unit = {
    if (args.length < 4) {
      System.err.println(
        "usage: LiveEnrichment <cams_json_dir> <weather_json_dir> <city_profiles.csv> <out_dir>")
      System.exit(2)
    }
    val Array(camsDir, weatherDir, profilesPath, outDir) = args.take(4)

    val spark = SparkSession.builder()
      .appName("AirQuality_Phase8b_LiveEnrichment")
      .getOrCreate()
    spark.sparkContext.setLogLevel("WARN")
    import spark.implicits._

    println("=" * 74)
    println("  PHASE 8b - LIVE ENRICHMENT")
    println(s"  cams     : $camsDir")
    println(s"  weather  : $weatherDir")
    println(s"  profiles : $profilesPath")
    println(s"  out      : $outDir")
    println("=" * 74)

    // ---- 1. city profiles (structured, flat CSV) ---------------------------
    val profiles = spark.read.option("header", "true").option("inferSchema", "true")
      .csv(profilesPath)
      .select(
        col("city").alias("p_city"),
        col("state").alias("p_state"),
        col("climate_type"),
        col("urbanization_index"),
        col("traffic_base_index"),
        col("morning_rush_multiplier"), col("evening_rush_multiplier"),
        col("weekend_traffic_multiplier"), col("rain_traffic_multiplier"),
        col("night_traffic_multiplier"),
        col("morning_rush_start"), col("morning_rush_end"),
        col("evening_rush_start"), col("evening_rush_end"))

    // ---- 2. CAMS air quality (semi-structured, nested JSON) ----------------
    val camsFields = Seq("time", "pm2_5", "pm10", "nitrogen_dioxide",
      "sulphur_dioxide", "carbon_monoxide", "ozone", "ammonia")
    val cams = explodeHourly(
      spark.read.option("multiLine", "true").json(s"$camsDir/*.json"), camsFields)
      .withColumn("slug", basename(col("_file")))
      .withColumn("ts", to_timestamp(col("time"), "yyyy-MM-dd'T'HH:mm"))
      .drop("_file", "time")

    // ---- 3. weather (semi-structured, nested JSON) -------------------------
    val wxFields = Seq("time", "temperature_2m", "relative_humidity_2m",
      "wind_speed_10m", "wind_direction_10m", "precipitation",
      "surface_pressure", "shortwave_radiation", "weather_code")
    val wx = explodeHourly(
      spark.read.option("multiLine", "true").json(s"$weatherDir/*.json"), wxFields)
      .withColumn("slug", basename(col("_file")))
      .withColumn("ts", to_timestamp(col("time"), "yyyy-MM-dd'T'HH:mm"))
      .drop("_file", "time")

    // ---- 4. manifest maps slug -> city ------------------------------------
    // Written by the fetcher; carries the geocoded city/state per file so the
    // join key is explicit rather than inferred from a filename.
    //
    // Derived by stripping the trailing "/raw_json" rather than appending
    // "/..": HDFS does not normalise parent-directory segments the way a local
    // filesystem does, so the ".." form silently resolves to nothing.
    val manifestPath = camsDir.replaceAll("/raw_json/?$", "") + "/manifest.json"
    println(s"  manifest : $manifestPath")
    val manifest = spark.read.option("multiLine", "true")
      .json(manifestPath)
      .select(explode(col("cities")).alias("c"))
      .select(
        col("c.city").alias("m_city"),
        col("c.state").alias("m_state"),
        basename(col("c.file")).alias("slug"))

    // The two feeds are fetched by separate jobs and can easily end up
    // covering different windows (an air-quality pull from last week joined
    // against weather pulled today shares ZERO hours and silently yields an
    // empty result). Report the windows before joining so that failure mode
    // is visible instead of looking like a logic bug.
    val camsRange = cams.select(min("ts").alias("lo"), max("ts").alias("hi")).first()
    val wxRange = wx.select(min("ts").alias("lo"), max("ts").alias("hi")).first()
    println(s"  cams window    : ${camsRange.get(0)} .. ${camsRange.get(1)}")
    println(s"  weather window : ${wxRange.get(0)} .. ${wxRange.get(1)}")

    val joined = cams
      .join(wx, Seq("slug", "ts"), "inner")     // inner: a row without weather
                                                // cannot be scored, so drop it
                                                // rather than impute weather
      .join(manifest, Seq("slug"), "inner")
      .join(profiles, col("m_city") === col("p_city"), "left")

    val nJoined = joined.count()
    if (nJoined == 0) {
      println("  *** JOIN PRODUCED 0 ROWS - the two feeds do not share any (city, hour). ***")
      println("  *** Re-fetch both feeds so their windows overlap, then re-run.        ***")
    } else {
      println(f"  joined rows    : $nJoined%,d")
    }

    // ---- 5. derive the calendar block --------------------------------------
    val withTime = joined
      .withColumn("year",  year(col("ts")))
      .withColumn("month", month(col("ts")))
      .withColumn("day",   dayofmonth(col("ts")))
      .withColumn("hour",  hour(col("ts")))
      // Spark's dayofweek() is 1=Sunday..7=Saturday. The structured dataset
      // uses 0=Monday..6=Sunday, so remap rather than pass the raw value
      // through - day_of_week feeds the dow_sin/dow_cos cyclical encodings,
      // and an off-by-one there rotates the whole weekly cycle.
      .withColumn("_dow", dayofweek(col("ts")))          // 1..7, Sunday = 1
      .withColumn("day_of_week", (col("_dow") + 5) % 7)  // -> Monday = 0 .. Sunday = 6
      .withColumn("is_weekend", when(col("day_of_week") >= 5, 1.0).otherwise(0.0))

    // ---- 6. season (Indian meteorological convention) ----------------------
    // Matches the structured dataset's own 4-value vocabulary exactly:
    // winter / summer / monsoon / post_monsoon.
    val withSeason = withTime.withColumn("season",
      when(col("month").isin(12, 1, 2), lit("winter"))
        .when(col("month").isin(3, 4, 5), lit("summer"))
        .when(col("month").isin(6, 7, 8, 9), lit("monsoon"))
        .otherwise(lit("post_monsoon")))

    // ---- 7. weather_condition from WMO code + conditions -------------------
    // Must land inside the 9 labels the trained StringIndexer has seen:
    // clear, cloudy, cold, foggy, hazy, heavy_rain, hot, humid, rainy.
    // (The indexer is handleInvalid="keep", so an unseen label would not crash
    // - it would land in a catch-all bucket and quietly degrade the encoding.
    // Mapping explicitly avoids that.)
    // WMO: 0 clear | 1-3 cloud | 45,48 fog | 51-57 drizzle | 61-67 rain
    //      71-77 snow | 80-82 showers | 95-99 thunderstorm
    val wc = withSeason.withColumn("weather_condition",
      when(col("weather_code").isin(45, 48), lit("foggy"))
        .when(col("weather_code").isin(95, 96, 99, 65, 67, 82) ||
              col("precipitation") > 7.5, lit("heavy_rain"))
        .when(col("weather_code").between(51, 67) ||
              col("weather_code").between(80, 82) ||
              col("precipitation") > 0.0, lit("rainy"))
        .when(col("temperature_2m") >= 35.0, lit("hot"))
        .when(col("temperature_2m") <= 12.0, lit("cold"))
        .when(col("relative_humidity_2m") >= 80.0, lit("humid"))
        .when(col("weather_code").isin(1, 2, 3), lit("cloudy"))
        .otherwise(lit("clear")))

    // ---- 8. traffic, from THIS project's own city profiles ------------------
    // Same construction the generator used: a per-city base index scaled by
    // rush-hour / weekend / rain / night multipliers, clamped to the
    // documented 0-100 scale (the raw dataset had values up to 110.2, which
    // Phase 3 clamps - do not reintroduce that defect here).
    val isMorningRush = col("hour") >= col("morning_rush_start") && col("hour") <= col("morning_rush_end")
    val isEveningRush = col("hour") >= col("evening_rush_start") && col("hour") <= col("evening_rush_end")
    val isNight = col("hour") >= 22 || col("hour") <= 5

    val withTraffic = wc
      .withColumn("is_rush_hour",
        when(isMorningRush || isEveningRush, 1.0).otherwise(0.0))
      .withColumn("_mult",
        when(isMorningRush, col("morning_rush_multiplier"))
          .when(isEveningRush, col("evening_rush_multiplier"))
          .when(isNight, col("night_traffic_multiplier"))
          .otherwise(lit(1.0)))
      .withColumn("_mult",
        col("_mult") * when(col("is_weekend") === 1.0, col("weekend_traffic_multiplier")).otherwise(lit(1.0)))
      .withColumn("_mult",
        col("_mult") * when(col("precipitation") > 0.0, col("rain_traffic_multiplier")).otherwise(lit(1.0)))
      .withColumn("traffic_index",
        least(greatest(col("traffic_base_index") * col("_mult"), lit(0.0)), lit(100.0)))

    // ---- 9. final projection onto the 32-column contract -------------------
    val out = withTraffic
      .withColumn("station_id",
        concat(lit("LIVE_"), upper(regexp_replace(col("m_city"), "[^A-Za-z0-9]+", "_"))))
      .withColumn("from_date", date_format(col("ts"), "yyyy-MM-dd HH:mm:ss"))
      .select(
        col("station_id"),
        col("m_state").alias("state"),
        col("m_city").alias("city"),
        col("from_date"),
        col("pm2_5").cast(DoubleType).alias("pm25"),
        col("pm10").cast(DoubleType).alias("pm10"),
        col("nitrogen_dioxide").cast(DoubleType).alias("no2"),
        col("sulphur_dioxide").cast(DoubleType).alias("so2"),
        // ug/m3 -> mg/m3, see header
        (col("carbon_monoxide").cast(DoubleType) / lit(UG_PER_MG)).alias("co"),
        col("ozone").cast(DoubleType).alias("o3"),
        // null across this region in CAMS - kept null, never defaulted to 0
        col("ammonia").cast(DoubleType).alias("nh3"),
        col("wind_direction_10m").cast(DoubleType).alias("wd_degree"),
        col("shortwave_radiation").cast(DoubleType).alias("solar_radiation"),
        // hPa -> mmHg, see header
        (col("surface_pressure").cast(DoubleType) * lit(HPA_TO_MMHG)).alias("pressure"),
        col("temperature_2m").cast(DoubleType).alias("temperature_c"),
        col("relative_humidity_2m").cast(DoubleType).alias("humidity_percent"),
        col("wind_speed_10m").cast(DoubleType).alias("wind_speed_ms"),
        col("precipitation").cast(DoubleType).alias("rainfall_mm"),
        col("weather_condition"),
        col("traffic_index").cast(DoubleType),
        col("is_rush_hour").cast(DoubleType),
        col("year"), col("month"), col("day"), col("hour"),
        col("day_of_week"), col("is_weekend").cast(DoubleType),
        col("season"),
        col("climate_type"),
        col("urbanization_index").cast(DoubleType),
        // provenance: these rows are a live API pull, not CPCB station data
        lit("live_api").alias("data_source"),
        concat(lit("LIVE_"), upper(regexp_replace(col("m_city"), "[^A-Za-z0-9]+", "_"))).alias("source_station"))
      .select(OutputCols.map(col): _*)
      .orderBy("city", "from_date")

    val n = out.count()
    val cities = out.select("city").distinct().count()
    println(f"  enriched rows : $n%,d across $cities%,d cities")

    println("  null audit on model-critical columns:")
    Seq("pm25", "temperature_c", "pressure", "traffic_index", "climate_type").foreach { c =>
      val nulls = out.filter(col(c).isNull).count()
      println(f"    $c%-18s nulls=$nulls%,d")
    }

    out.show(5, truncate = false)

    // Single CSV part: the stream's maxFilesPerTrigger=1 treats each file as
    // one micro-batch, so one file per enrichment run keeps batches meaningful.
    out.coalesce(1).write.mode("overwrite")
      .option("header", "true").csv(outDir)

    println(s"  wrote -> $outDir")
    spark.stop()
  }
}
