#!/usr/bin/env bash
# ============================================================================
# PHASE 9 - build and query the Hive serving layer
# 23AID302 - Big Data Analytics
#
# Runs INSIDE the aq-spark container:
#     docker exec aq-spark bash /hive/run_hive_layer.sh create
#     docker exec aq-spark bash /hive/run_hive_layer.sh query
#     docker exec -d aq-spark bash /hive/run_hive_layer.sh thrift
#
# WHY spark-sql AND NOT A HIVE DAEMON
#   These images ship no standalone Hive server, but the Spark image bundles
#   the full Hive stack (16 hive-*.jar, spark-sql, beeline,
#   start-thriftserver.sh). Spark SQL with Hive support IS a Hive metastore
#   client: it writes real Hive metadata, and start-thriftserver.sh speaks the
#   HiveServer2 Thrift protocol, so ordinary beeline/JDBC clients connect to it
#   unchanged. That is the standard modern serving layer, not a substitute for
#   one.
#
# METASTORE
#   Embedded Derby under /scratch/metastore_db. Single-user, which is fine for
#   this project. Note Derby allows exactly ONE JVM at a time - so the thrift
#   server and a spark-sql shell cannot both hold it. Run one or the other.
# ============================================================================
set -euo pipefail

SPARK=/opt/spark/bin
WAREHOUSE=hdfs://namenode:9000/user/hadoop/hive
METASTORE=/scratch/metastore_db
SQL_DIR=/hive

COMMON_CONF=(
  --master "local[2]"
  --driver-memory 2g
  --conf spark.sql.catalogImplementation=hive
  --conf spark.sql.warehouse.dir=${WAREHOUSE}
  --conf "spark.driver.extraJavaOptions=-Dderby.system.home=${METASTORE}"
  --conf spark.local.dir=/scratch
  # small cluster: keep the write pipeline short and tolerant
  --conf spark.hadoop.dfs.replication=2
  --conf spark.hadoop.dfs.client.block.write.replace-datanode-on-failure.policy=NEVER
)

case "${1:-}" in

  create)
    echo "=== creating Hive database + external tables ==="
    "${SPARK}/spark-sql" "${COMMON_CONF[@]}" -f "${SQL_DIR}/create_tables.sql"
    echo
    echo "=== tables registered ==="
    "${SPARK}/spark-sql" "${COMMON_CONF[@]}" -e "USE airquality; SHOW TABLES;"
    ;;

  query)
    echo "=== demonstration queries ==="
    "${SPARK}/spark-sql" "${COMMON_CONF[@]}" -f "${SQL_DIR}/demo_queries.sql"
    ;;

  thrift)
    # HiveServer2-compatible endpoint on 10000. Connect with:
    #   docker exec -it aq-spark /opt/spark/bin/beeline \
    #       -u jdbc:hive2://localhost:10000
    echo "=== starting HiveServer2 Thrift endpoint on :10000 ==="
    "${SPARK}/../sbin/start-thriftserver.sh" "${COMMON_CONF[@]}" \
      --hiveconf hive.server2.thrift.port=10000
    ;;

  *)
    echo "usage: $0 {create|query|thrift}" >&2
    exit 2
    ;;
esac
