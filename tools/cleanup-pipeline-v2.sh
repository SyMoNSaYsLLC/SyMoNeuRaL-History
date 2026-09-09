#!/usr/bin/env bash
# The single mutation owner for the remaining storage work.
#
# A NEW FILE rather than an edit to cleanup-pipeline.sh: bash reads a script
# incrementally by byte offset, so editing one under a running interpreter shifts the
# remaining content and can make it execute garbage. That happened once already today.
#
# Serialised throughout. Upload bandwidth is the only constraint (~5 MB/s measured), so
# concurrent stages split one pipe, gain nothing, and multiply the ways a partial transfer
# can confuse the ledger.
set -uo pipefail
cd /home/google/Symoneural
L=.private/offload.log
say(){ printf '%s PIPE2: %s\n' "$(date +%H:%M:%S)" "$*" | tee -a "$L"; }
MY=$$
wait_quiet() {
  while ps -eo pid,args --no-headers | awk -v me="$MY" \
      '$1!=me && !/bash -c/ && (/offload-to-drive\.sh --(run|home|yocto|external-rest)/ \
        || /upstream-to-drive\.sh --(run|reference)/)' | grep -q .; do
    sleep 60
  done
}
say "=== start; /home $(df -h /home|tail -1|awk '{print $5}')  /yocto $(df -h /yocto|tail -1|awk '{print $5}')"
wait_quiet; say "prior stage clear"

say "STAGE external remainder";      tools/offload-to-drive.sh --external-rest >>"$L" 2>&1; wait_quiet
say "STAGE pinned upstreams";        tools/upstream-to-drive.sh --run          >>"$L" 2>&1; wait_quiet
say "STAGE reference remainder";     tools/upstream-to-drive.sh --reference    >>"$L" 2>&1; wait_quiet
say "external/ now $(du -sh external 2>/dev/null|cut -f1||echo gone)"
say "STAGE home leftovers";          tools/offload-to-drive.sh --home          >>"$L" 2>&1; wait_quiet
say "STAGE yocto";                   tools/offload-to-drive.sh --yocto         >>"$L" 2>&1; wait_quiet
say "=== end;   /home $(df -h /home|tail -1|awk '{print $5}')  /yocto $(df -h /yocto|tail -1|awk '{print $5}')"
say "ALL TRANSFER STAGES COMPLETE -- Drive reorganisation and cataloguing are next"
