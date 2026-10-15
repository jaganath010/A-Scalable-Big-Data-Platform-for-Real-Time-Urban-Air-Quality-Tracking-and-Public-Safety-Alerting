#!/usr/bin/env bash
# ==============================================================================
# Verify the HDFS cluster and produce the numbers quoted in section 6 of the
# status report. Run INSIDE the namenode container:
#
#   docker exec -it aq-namenode bash /scripts/verify_cluster.sh
#
# Every number printed here is measured from the live cluster, not calculated
# on paper - that is the point. Paste this output into the report as evidence.
# ==============================================================================
set -u

HDFS_DIR=/user/hadoop/lakehouse/raw
BAR="========================================================================"

echo "$BAR"
echo "  1. LIVE DATANODES  (expect 4)"
echo "$BAR"
hdfs dfsadmin -report | grep -E "^(Live datanodes|Name|Hostname|Configured Capacity|DFS Used|DFS Remaining)" \
  | sed 's/^/  /'

echo
echo "$BAR"
echo "  2. REPLICATION AND BLOCK SIZE IN EFFECT"
echo "$BAR"
echo "  dfs.replication : $(hdfs getconf -confKey dfs.replication)"
echo "  dfs.blocksize   : $(hdfs getconf -confKey dfs.blocksize) bytes"
echo "                    = $(( $(hdfs getconf -confKey dfs.blocksize) / 1024 / 1024 )) MB"

echo
echo "$BAR"
echo "  3. THE DATASET IN HDFS"
echo "$BAR"
echo "  files:"
hdfs dfs -ls "$HDFS_DIR" | tail -n +2 | awk '{printf "    %-22s %14.2f MB\n", $NF, $5/1024/1024}'
echo
echo "  logical size (one copy):"
hdfs dfs -du -s -h "$HDFS_DIR" | sed 's/^/    /'
echo "  physical size (all replicas):"
hdfs dfs -du -s -h -v "$HDFS_DIR" 2>/dev/null | tail -1 | sed 's/^/    /'

echo
echo "$BAR"
echo "  4. BLOCK COUNT AND DISTRIBUTION  (expect ~220 blocks, ~660 replicas)"
echo "$BAR"
# fsck walks the actual block map on the NameNode.
hdfs fsck "$HDFS_DIR" -files -blocks 2>/dev/null > /tmp/fsck.txt
echo "  total blocks    : $(grep -c 'blk_' /tmp/fsck.txt)"
grep -E "Total blocks|Average block replication|Default replication factor|Corrupt blocks|Under-replicated|Missing" /tmp/fsck.txt \
  | sed 's/^/  /'

echo
echo "  per-DataNode block replica counts:"
for dn in datanode1 datanode2 datanode3 datanode4; do
  n=$(hdfs dfsadmin -report -live 2>/dev/null | grep -A12 "Hostname: $dn" | grep "DFS Used%" | head -1)
  used=$(hdfs dfsadmin -report -live 2>/dev/null | grep -A12 "Hostname: $dn" | grep -m1 "^DFS Used:" | awk '{print $3, $4}')
  printf "    %-12s DFS Used: %s\n" "$dn" "${used:-n/a}"
done

echo
echo "$BAR"
echo "  5. HEALTH"
echo "$BAR"
hdfs fsck "$HDFS_DIR" 2>/dev/null | tail -n 12 | sed 's/^/  /'

echo
echo "$BAR"
echo "  Web UI: http://localhost:9870  (Overview -> Datanodes -> Utilities/Browse)"
echo "$BAR"
