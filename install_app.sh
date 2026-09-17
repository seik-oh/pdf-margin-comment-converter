#!/bin/bash
# 'PDF 코멘트 여백' 맥 앱을 만들어 바탕화면에 놓습니다.
# 사용법: margin_comments.py 와 같은 폴더에 두고  bash install_app.sh
set -e

DIR="$(cd "$(dirname "$0")" && pwd)"
PY_SCRIPT="$DIR/margin_comments.py"
APP="$HOME/Desktop/PDF 코멘트 여백.app"

if [ ! -f "$PY_SCRIPT" ]; then
  echo "❌ margin_comments.py 를 이 파일과 같은 폴더($DIR)에 넣어주세요."
  exit 1
fi

PY="$(command -v python3 || true)"
if [ -z "$PY" ]; then
  echo "❌ python3 를 찾지 못했어요."
  exit 1
fi
PY="$("$PY" -c 'import sys; print(sys.executable)')"
echo "사용할 파이썬: $PY"

if ! "$PY" -c "import pypdf, reportlab" 2>/dev/null; then
  echo "필요한 패키지를 설치하는 중..."
  "$PY" -m pip install --user pypdf reportlab \
    || "$PY" -m pip install --user --break-system-packages pypdf reportlab
fi

TMP="$(mktemp -d)"
printf '\357\273\277' > "$TMP/app.applescript"
sed "s|__PYTHON__|$PY|" >> "$TMP/app.applescript" <<'EOF'
property pythonPath : "__PYTHON__"

on run
	try
		set theFiles to choose file with prompt "코멘트를 여백으로 뺄 PDF를 선택하세요 (여러 개 가능)" of type {"com.adobe.pdf"} with multiple selections allowed
	on error
		return
	end try
	my processFiles(theFiles)
end run

on open droppedItems
	my processFiles(droppedItems)
end open

on processFiles(fileList)
	set scriptPath to POSIX path of (path to resource "margin_comments.py")
	set okList to {}
	set msgList to {}
	repeat with f in fileList
		set p to POSIX path of (contents of f)
		if p ends with ".pdf" then
			set outPath to (text 1 thru -5 of p) & "_코멘트.pdf"
			try
				set cmd to "export LANG=en_US.UTF-8 PYTHONIOENCODING=utf-8; " & quoted form of pythonPath & " " & quoted form of scriptPath & " " & quoted form of p & " " & quoted form of outPath
				set res to do shell script cmd
				set end of okList to outPath
				set end of msgList to res
			on error errMsg
				set end of msgList to "오류 (" & p & "):" & return & errMsg
			end try
		else
			set end of msgList to "PDF가 아니라서 건너뜀: " & p
		end if
	end repeat

	set AppleScript's text item delimiters to return & return
	set summary to msgList as text
	set AppleScript's text item delimiters to ""

	if (count of okList) > 0 then
		if summary contains "코멘트 0개" then
			set summary to summary & return & return & "※ 코멘트가 0개라면 Zotero에서 'PDF 내보내기…'로 저장한 파일인지 확인하세요."
		end if
		set btn to button returned of (display dialog summary buttons {"닫기", "결과 열기"} default button "결과 열기" with title "PDF 코멘트 여백")
		if btn is "결과 열기" then
			repeat with o in okList
				do shell script "open " & quoted form of (contents of o)
			end repeat
		end if
	else
		display dialog summary buttons {"확인"} default button "확인" with icon caution with title "PDF 코멘트 여백"
	end if
end processFiles
EOF

rm -rf "$APP"
osacompile -o "$APP" "$TMP/app.applescript"
cp "$PY_SCRIPT" "$APP/Contents/Resources/margin_comments.py"
codesign --force --deep --sign - "$APP" >/dev/null 2>&1 || true
rm -rf "$TMP"

echo ""
echo "✅ 완료! 바탕화면에 'PDF 코멘트 여백' 앱이 생겼어요."
echo "   PDF를 앱 아이콘에 끌어다 놓거나, 앱을 더블클릭해서 파일을 고르면 됩니다."
open -R "$APP"
