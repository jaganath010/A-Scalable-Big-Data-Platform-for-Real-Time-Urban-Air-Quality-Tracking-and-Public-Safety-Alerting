from pyspark.sql import SparkSession
spark = SparkSession.builder.appName("verify_unified").master("local[2]").config("spark.driver.memory","3g").getOrCreate()
spark.sparkContext.setLogLevel("WARN")

df = spark.read.parquet(r"F:\SEM 5 NOTES\Big Data\Project_Final\airquality_unified")
print("TOTAL ROWS:", df.count())
print("SCHEMA:")
df.printSchema()

print("=== structured sample ===")
df.filter(df.source_format == "structured_csv").show(3, truncate=False)
print("=== semistructured sample ===")
df.filter(df.source_format == "semistructured_json").show(3, truncate=False)

print("=== null check on key fields per source_format ===")
from pyspark.sql import functions as F
df.groupBy("source_format").agg(
    F.count("*").alias("n"),
    F.sum(F.col("pm25").isNull().cast("int")).alias("pm25_null"),
    F.sum(F.col("timestamp").isNull().cast("int")).alias("ts_null"),
    F.countDistinct("city").alias("distinct_cities"),
).show(truncate=False)

spark.stop()
