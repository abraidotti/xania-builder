#!/usr/bin/env bash
# Watch gate logs (build/gate-*.log) and print one line per event: a step starting or finishing, a gate's verdict,
# an error, or a stall (no log has changed for STALL_MIN minutes). Exits when DONE_FILE exists and is non-empty,
# e.g. a queued job's output file. Usage: scripts/watch-gates.sh [DONE_FILE]
cd "$(dirname "$0")/.." || exit 2
DONE_FILE=${1:-}
STALL_MIN=${STALL_MIN:-20}
declare -A seen
last_change=$(date +%s)
stall_said=0
for f in build/gate-*.log; do   # start from where each log is now, with a one-line status
    [ -f "$f" ] || continue
    seen[$f]=$(wc -l < "$f")
    echo "[$(basename "$f" .log)] now: $(grep -v '^$' "$f" | tail -1)"
done
while true; do
    for f in build/gate-*.log; do
        [ -f "$f" ] || continue
        n=$(wc -l < "$f")
        key=$f:$(stat -c %Y "$f")
        prev=${seen[$f]:-0}
        if [ "$n" -lt "$prev" ]; then prev=0; fi   # the log was rewritten by a new run
        if [ "$n" -gt "$prev" ]; then
            tail -n +"$((prev + 1))" "$f" | head -n "$((n - prev))" |
                grep -E '^gate |\.\.\.$|-> |^  (ok|FAIL) |gate (PASSED|FAILED)|COULDN.T|Traceback|Error|^exit' |
                sed "s|^|[$(basename "$f" .log)] |"
            seen[$f]=$n
            last_change=$(date +%s)
            stall_said=0
        fi
    done
    if [ $(( $(date +%s) - last_change )) -ge $((STALL_MIN * 60)) ] && [ "$stall_said" = 0 ]; then
        echo "[watch] STALL: no gate log has changed for ${STALL_MIN} min"
        stall_said=1
    fi
    if [ -n "$DONE_FILE" ] && [ -s "$DONE_FILE" ]; then
        echo "[watch] the queued job finished"
        exit 0
    fi
    sleep 15
done
