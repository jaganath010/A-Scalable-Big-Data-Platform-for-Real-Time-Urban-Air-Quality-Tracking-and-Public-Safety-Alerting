from pyspark.sql import SparkSession
import pyspark.sql.functions as F

spark = SparkSession.builder.appName("test2").master("local[2]") \
    .config("spark.driver.memory","3g") \
    .config("spark.sql.shuffle.partitions","8") \
    .getOrCreate()

# Test reading one structured CSV part file
df = spark.read.option("header","true").csv(r"F:\SEM 5 NOTES\Big Data\Project_Final\airquality_expanded\part-7164.csv")
print("STRUCTURED SCHEMA:")
df.printSchema()
print("STRUCTURED SAMPLE COUNT (limit 1000):", df.limit(1000).count())

# Test reading nested JSON (multiline, since it's a single JSON object per file)
jdf = spark.read.option("multiLine","true").json(r"F:\SEM 5 NOTES\Big Data\Project_Final\airquality_semistructured\raw_json\delhi.json")
print("SEMI-STRUCTURED SCHEMA:")
jdf.printSchema()
jdf.show(3, truncate=False)

spark.stop()
