LOG_FILE="$HOME/retrieve_carra.log"
N_SECONDS=60

cleanup() {
	echo "Exiting script. Cleaning up..."
	if [ -n "carraPID" ]; then
		kill "$carraPID"
	fi
	exit 1
}

trap cleanup EXIT

python ~/getcarra/get_carra.py ~/data/carraJSON24klst.json ~/interpolatedCarra.feather >> "$LOG_FILE" 2>&1 &
carraPID=$!
last_modified=$(stat -c %Y "$LOG_FILE")

echo "Started the python script and will now monitor..."

while ps -p $carraPID > /dev/null; do
	last_modified=$(stat -c %Y "$LOG_FILE")
	last_line=$(tail -n 1 "$LOG_FILE")

	shopt -s nocasematch

	if [[ $last_line == *error* || $last_line == *WARNING* || $last_line == *retrying* ]]; then
		echo "Error detected and restarting..."
		echo $last_line
		sleep 5
		python ~/getcarra/get_carra.py ~/data/carraJSON24klst.json ~/interpolatedCarra.feather >> "$LOG_FILE" 2>&1 &
		carraPID=$!
	fi

	if  [[ $last_line == *downloading* || $last_line == *"Running>>>>"* || $last_line == *while* ]]; then 
		echo $last_line
		sleep 1
	fi

	shopt -u nocasematch

	current_time=$(date +%s)
	time_diff=$((curent_time - last_modified))

	if [ "$time_diff" -gt "$N_SECONDS" ]; then
		echo "No recent updates. Restarting..."
		sleep 5
		python ~/getcarra/get_carra.py ~/data/carraJSON24klst.json ~/interpolatedCarra.feather >> "$LOG_FILE" 2>&1 &
		carraPID=$!
	fi
done
