#!/usr/bin/env bash
# Linux x86-64. Installs only inside this checkout; no sudo or global changes.
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p .tools/downloads
fetch() {
    local url="$1" archive="$2" checksum="$3" binary="$4"
    local target=".tools/downloads/$archive"
    if [[ -f "$target" ]] && ! printf '%s  %s\n' "$checksum" "$target" | sha256sum --check --status; then
        mv -f "$target" "$target.invalid"
    fi
    if [[ ! -f "$target" ]]; then
        curl --fail --location --retry 3 "$url" --output "$target.part"
        printf '%s  %s\n' "$checksum" "$target.part" | sha256sum --check
        mv -f "$target.part" "$target"
    fi
    printf '%s  %s\n' "$checksum" "$target" | sha256sum --check
    if [[ ! -x ".tools/$binary" ]]; then tar -xzf "$target" -C .tools; fi
    test -x ".tools/$binary"
}
fetch https://github.com/renode/renode/releases/download/v1.17.0/renode-1.17.0.linux-portable.tar.gz renode.tar.gz 4ba7c68b59e2447f188ef4b4b112fcccd2802582c460beedceb63b84e5605a5f renode_1.17.0-portable/renode
fetch https://github.com/xpack-dev-tools/arm-none-eabi-gcc-xpack/releases/download/v15.2.1-1.1/xpack-arm-none-eabi-gcc-15.2.1-1.1-linux-x64.tar.gz gcc.tar.gz da6a49ad4003944b823c6c93702a8787c922ab34bd7e918ec0eaf6933a9b1ff6 xpack-arm-none-eabi-gcc-15.2.1-1.1/bin/arm-none-eabi-gcc
printf '%s\n' 'Tools installed. Run:' 'export PATH="$PWD/.tools/xpack-arm-none-eabi-gcc-15.2.1-1.1/bin:$PATH"' 'export RENODE="$PWD/.tools/renode_1.17.0-portable/renode"' 'make all host-test demo'
