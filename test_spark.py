from pyspark.sql import SparkSession
spark = SparkSession.builder.appName("test").master("local[2]").config("spark.driver.memory","2g").getOrCreate()
df = spark.range(1000)
print("COUNT:", df.count())
spark.stop()
