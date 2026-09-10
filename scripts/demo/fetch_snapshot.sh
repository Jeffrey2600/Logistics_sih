set -e
S="$1"
B=http://localhost:8000
mkdir -p "$S/raw"
# months the demo can switch between
for m in jul jan; do
  curl -s -m 600 "$B/network/segments?month=$m" -o "$S/raw/seg_$m.json"
  echo "seg_$m $(wc -c < "$S/raw/seg_$m.json")"
done
curl -s -m 600 "$B/accessibility/index?month=jul" -o "$S/raw/access_jul.json"
echo "access_jul $(wc -c < "$S/raw/access_jul.json")"
curl -s -m 600 "$B/accessibility/index?month=jan" -o "$S/raw/access_jan.json"
echo "access_jan $(wc -c < "$S/raw/access_jan.json")"

# routing: eight lanes into Guwahati, both months, default settings
for o in KHM AZL IMP SHL ITA AGT GTK DMP; do
  for m in jul jan; do
    curl -s -m 300 -X POST "$B/routing/plan" -H 'content-type: application/json' \
      -d "{\"origin\":\"$o\",\"destination\":\"GAU\",\"month\":\"$m\",\"modes\":[\"road\",\"rail\",\"water\",\"air\"],\"weights\":{\"cost\":0.4,\"time\":0.4,\"risk\":0.2},\"value_of_time\":150,\"alternatives\":3}" \
      -o "$S/raw/plan_${o}_GAU_${m}.json"
    curl -s -m 300 -X POST "$B/routing/compare?month=$m" -H 'content-type: application/json' \
      -d "{\"origin\":\"$o\",\"destination\":\"GAU\",\"value_of_time\":150}" \
      -o "$S/raw/cmp_${o}_GAU_${m}.json"
  done
done
echo "plans $(ls "$S/raw" | grep -c '^plan_')  compares $(ls "$S/raw" | grep -c '^cmp_')"
