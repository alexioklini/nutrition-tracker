#!/bin/bash
# Daily supplement auto-logger for Nutrition Tracker
DATE=$(date +%Y-%m-%d)
DOW=$(date +%u) # 1=Mon ... 7=Sun
API="http://localhost:5003/api/meals"

# Check if supplements already logged today
EXISTING=$(curl -s "$API?date=$DATE" | python3 -c "import sys,json; meals=json.load(sys.stdin); print(sum(1 for m in meals if m.get('meal_type')=='supplement'))")
if [ "$EXISTING" -gt 0 ]; then
  echo "Supplements already logged for $DATE ($EXISTING entries)"
  exit 0
fi

post() {
  curl -s -X POST "$API" -H "Content-Type: application/json" -d "$1" -o /dev/null
}

# Daily supplements
post "{\"date\":\"$DATE\",\"meal_type\":\"supplement\",\"description\":\"Zink 30 (Picolinat)\",\"calories\":0,\"protein_g\":0,\"carbs_g\":0,\"fat_g\":0,\"sugar_g\":0,\"zinc_mg\":30,\"source\":\"text\"}"
post "{\"date\":\"$DATE\",\"meal_type\":\"supplement\",\"description\":\"Selamin (Natriumselenit)\",\"calories\":0,\"protein_g\":0,\"carbs_g\":0,\"fat_g\":0,\"sugar_g\":0,\"selenium_mcg\":90,\"source\":\"text\"}"
post "{\"date\":\"$DATE\",\"meal_type\":\"supplement\",\"description\":\"Curcumin-Loges + Boswellia (2x)\",\"calories\":0,\"protein_g\":0,\"carbs_g\":0,\"fat_g\":0,\"sugar_g\":0,\"vitamin_d_iu\":800,\"source\":\"text\"}"
post "{\"date\":\"$DATE\",\"meal_type\":\"supplement\",\"description\":\"Grüner Tee-PS (3 Kapseln, EGCG 225mg)\",\"calories\":0,\"protein_g\":0,\"carbs_g\":0,\"fat_g\":0,\"sugar_g\":0,\"source\":\"text\"}"
post "{\"date\":\"$DATE\",\"meal_type\":\"supplement\",\"description\":\"Vitals Männerformel Pro Prostata (2x)\",\"calories\":0,\"protein_g\":0,\"carbs_g\":0,\"fat_g\":0,\"sugar_g\":0,\"source\":\"text\"}"
post "{\"date\":\"$DATE\",\"meal_type\":\"supplement\",\"description\":\"Legalon 140mg (2x, Silymarin 280mg)\",\"calories\":0,\"protein_g\":0,\"carbs_g\":0,\"fat_g\":0,\"sugar_g\":0,\"source\":\"text\"}"
post "{\"date\":\"$DATE\",\"meal_type\":\"supplement\",\"description\":\"MiraCHOL 3.0 Gold (Ubiquinol + CoQ10)\",\"calories\":0,\"protein_g\":0,\"carbs_g\":0,\"fat_g\":0,\"sugar_g\":0,\"source\":\"text\"}"

# Omega-3 only Fri/Sat/Sun
if [ "$DOW" -ge 5 ]; then
  post "{\"date\":\"$DATE\",\"meal_type\":\"supplement\",\"description\":\"Apremia Omega-3 (1000mg Fischöl)\",\"calories\":9,\"protein_g\":0,\"carbs_g\":0,\"fat_g\":1,\"sugar_g\":0,\"source\":\"text\"}"
fi

echo "Supplements logged for $DATE (DOW=$DOW)"
