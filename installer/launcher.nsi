; OCR2.exe: launcher stub placed in the program folder (M6 Task 8, ruling R6).
;
; Reads active.txt next to itself (line 1: active version) and starts
;   versions\<v>\python\pythonw.exe -B -m alfa_document_intelligence --app-window --ocr-engine rapidocr-v6
; "OCR2.exe /rollback" runs install_state rollback with the active Python and shows the result.
; No files, no registry, user level only.  Built by installer/build_installer.py:
;   makensis /INPUTCHARSET UTF8 -DOUTFILE=<...>\OCR2.exe launcher.nsi

Unicode true
ManifestDPIAware true
RequestExecutionLevel user
SilentInstall silent
SetCompressor /SOLID lzma

!ifndef OUTFILE
  !error "OUTFILE mancante (-DOUTFILE=...\OCR2.exe)"
!endif

!include "FileFunc.nsh"
!include "LogicLib.nsh"

Name "OCR2"
Caption "OCR2"
OutFile "${OUTFILE}"

; Optional signing (REQ-105): only when build_installer.py is given a thumbprint and a timestamp server.
!ifdef OCR2_SIGN_THUMBPRINT
  !finalize 'powershell.exe -NoProfile -ExecutionPolicy Bypass -File "${OCR2_SIGN_SCRIPT}" -Installer "%1" -Thumbprint ${OCR2_SIGN_THUMBPRINT} -TimestampServer "${OCR2_TIMESTAMP_URL}" -FailureMarker "${OCR2_SIGN_MARKER}"' = 0
!endif
LoadLanguageFile "${NSISDIR}\Contrib\Language files\Italian.nlf"

; $R0 <- line 1 of $EXEDIR\active.txt, or "" when missing or not a plain version (digits and dots).
Function ReadActive
  StrCpy $R0 ""
  ClearErrors
  FileOpen $R1 "$EXEDIR\active.txt" r
  IfErrors read_done
  FileRead $R1 $R0
  FileClose $R1
  strip:
    StrCpy $R2 $R0 1 -1
    StrCmp $R2 "$\n" strip_one
    StrCmp $R2 "$\r" strip_one
    Goto check
  strip_one:
    StrCpy $R0 $R0 -1
    Goto strip
  check:
    StrLen $R3 $R0
    IntCmp $R3 0 read_done read_done
    IntCmp $R3 32 0 0 bad
    StrCpy $R3 0
  next_char:
    StrCpy $R2 $R0 1 $R3
    StrCmp $R2 "" read_done
    StrCpy $R4 "0123456789."
    StrCpy $R5 0
  allowed:
    StrCpy $R6 $R4 1 $R5
    StrCmp $R6 "" bad
    StrCmp $R6 $R2 char_ok
    IntOp $R5 $R5 + 1
    Goto allowed
  char_ok:
    IntOp $R3 $R3 + 1
    Goto next_char
  bad:
    StrCpy $R0 ""
  read_done:
FunctionEnd

Section
  Call ReadActive
  ${If} $R0 == ""
  ${OrIfNot} ${FileExists} "$EXEDIR\versions\$R0\python\pythonw.exe"
    MessageBox MB_ICONSTOP "OCR2 non è installato correttamente. Reinstalla OCR2 con l'installer."
    SetErrorLevel 2
    Quit
  ${EndIf}
  ${GetParameters} $0
  ClearErrors
  ${GetOptions} $0 "/rollback" $1
  ${IfNot} ${Errors}
    nsExec::ExecToStack '"$EXEDIR\versions\$R0\python\python.exe" -B -m alfa_document_intelligence.install_state rollback'
    Pop $2
    Pop $3
    ${If} $2 == "0"
      MessageBox MB_ICONINFORMATION "$3"
      SetErrorLevel 0
    ${Else}
      MessageBox MB_ICONSTOP "Ritorno alla versione precedente non riuscito.$\r$\n$3"
      SetErrorLevel 1
    ${EndIf}
    Quit
  ${EndIf}
  ; Working folder: the program folder, never a version folder (prune can delete those).
  SetOutPath "$EXEDIR"
  Exec '"$EXEDIR\versions\$R0\python\pythonw.exe" -B -m alfa_document_intelligence --app-window --ocr-engine rapidocr-v6'
SectionEnd
