#!/bin/zsh

# CIA Printで使うEW-M634Tだけを、AirPrint/IPPプリンターとして登録する。
# 見つからない場合や候補が複数ある場合も、別のプリンターは登録しない。

set -u

QUEUE_NAME="${CIA_PRINT_PRINTER_NAME:-EPSON_EW_M634T_Series}"

if [[ "${CIA_PRINT_SKIP_PRINTER_SETUP:-0}" == "1" ]]; then
  print " プリンター自動登録をスキップしました。"
  exit 0
fi

LPSTAT_BIN="${CIA_PRINT_LPSTAT_BIN:-$(command -v lpstat 2>/dev/null || true)}"
LPINFO_BIN="${CIA_PRINT_LPINFO_BIN:-$(command -v lpinfo 2>/dev/null || true)}"
LPADMIN_BIN="${CIA_PRINT_LPADMIN_BIN:-$(command -v lpadmin 2>/dev/null || true)}"

if [[ -z "$LPSTAT_BIN" || -z "$LPADMIN_BIN" ]]; then
  print " プリンター自動登録に必要なmacOSの印刷機能が見つかりません。"
  return 1 2>/dev/null || exit 1
fi

if "$LPSTAT_BIN" -p "$QUEUE_NAME" >/dev/null 2>&1; then
  print " プリンター: EW-M634Tは登録済みです。"
  exit 0
fi

typeset -a candidates
candidates=()

# 既に別名で追加されているEW-M634Tの接続先も再利用する。
while IFS= read -r line; do
  [[ "$line" == *":"* ]] || continue
  uri="${line#*: }"
  if print -r -- "$line" | /usr/bin/grep -Eiq 'EW[-_ %]?M634T|M634T' && \
     print -r -- "$uri" | /usr/bin/grep -Eiq '^(dnssd|ipp|ipps)://'; then
    candidates+=("$uri")
  fi
done < <("$LPSTAT_BIN" -v 2>/dev/null || true)

# 未登録ならBonjour/IPPのネットワーク機器からEW-M634Tだけを探す。
if [[ -n "$LPINFO_BIN" ]]; then
  while IFS= read -r line; do
    uri="${line#* }"
    if print -r -- "$line" | /usr/bin/grep -Eiq 'EW[-_ %]?M634T|M634T' && \
       print -r -- "$uri" | /usr/bin/grep -Eiq '^(dnssd|ipp|ipps)://'; then
      candidates+=("$uri")
    fi
  done < <("$LPINFO_BIN" -v 2>/dev/null || true)
fi

# 同じURIが複数の検索結果に出ても1候補として扱う。
typeset -a unique_candidates
unique_candidates=()
for uri in "${candidates[@]}"; do
  duplicate=0
  for known_uri in "${unique_candidates[@]}"; do
    if [[ "$known_uri" == "$uri" ]]; then
      duplicate=1
      break
    fi
  done
  (( duplicate == 0 )) && unique_candidates+=("$uri")
done

if (( ${#unique_candidates[@]} == 0 )); then
  print " EW-M634Tを自動検出できませんでした。"
  print " Macとプリンターを同じWi-Fiへ接続し、必要ならREADMEの手動追加を行ってください。"
  exit 1
fi

if (( ${#unique_candidates[@]} > 1 )); then
  print " EW-M634Tの候補が複数見つかったため、自動登録しませんでした。"
  print " READMEの手動追加手順で、使用する1台を選んでください。"
  exit 1
fi

printer_uri="${unique_candidates[1]}"
register_args=(-p "$QUEUE_NAME" -E -v "$printer_uri" -m everywhere)

if "$LPADMIN_BIN" "${register_args[@]}" >/dev/null 2>&1; then
  print " プリンター: EW-M634Tを自動登録しました。"
  exit 0
fi

# 対話中だけ、macOS管理者権限で再試行する。自動起動では入力待ちにしない。
if [[ -t 0 && -t 1 ]] && command -v sudo >/dev/null 2>&1; then
  print " EW-M634Tの登録にMacの管理者パスワードが必要です。"
  if sudo "$LPADMIN_BIN" "${register_args[@]}"; then
    print " プリンター: EW-M634Tを自動登録しました。"
    exit 0
  fi
fi

print " EW-M634Tを自動登録できませんでした。"
print " CIA Printは起動します。READMEの手動追加手順を確認してください。"
exit 1
