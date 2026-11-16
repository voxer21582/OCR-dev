; OCR2 per-user installer and uninstaller (M6 Task 8, REQ-102, REQ-104, REQ-106, V4, DEC-032).
;
; Program folder <base> = $LOCALAPPDATA\Programs\OCR2 (or /D=):
;   versions\<v>\   payload of one version (python\, app\, runtime-manifest.json)
;   active.txt      line 1 active version, line 2 previous (written only by install_state)
;   OCR2.exe        launcher stub (launcher.nsi); Start-menu shortcuts point only to it and to uninstall.exe
;   uninstall.exe
; Install: a non-active versions\<v> is a leftover of an interrupted install and is
; deleted first (R7); the payload is extracted; install_state activate <v> verifies
; it and only then rewrites active.txt.  On failure versions\<v> is deleted and the
; previous version stays active.  No registry, no admin rights, no download.
; The user's data (%LOCALAPPDATA%\OCR2) is deleted only by install_state uninstall
; --remove-data, which resolves it from the LOCALAPPDATA environment variable.
;
; Build: installer/build_installer.py
;   -DVERSION=X.Y.Z -DPAYLOAD_DIR=<installer\out\X.Y.Z> -DLAUNCHER_EXE=<OCR2.exe> -DOUTFILE=<setup.exe>
;   test build: -DOCR2_TEST -DOCR2_TEST_DATA_ROOT=<temporary folder> (no shortcuts; installs only there)

Unicode true
ManifestDPIAware true
RequestExecutionLevel user
SetCompressor /SOLID lzma

!ifndef VERSION
  !error "VERSION mancante (-DVERSION=X.Y.Z)"
!endif
!ifndef PAYLOAD_DIR
  !error "PAYLOAD_DIR mancante"
!endif
!ifndef LAUNCHER_EXE
  !error "LAUNCHER_EXE mancante"
!endif
!ifndef OUTFILE
  !error "OUTFILE mancante"
!endif
!ifdef OCR2_TEST
  !ifndef OCR2_TEST_DATA_ROOT
    !error "OCR2_TEST_DATA_ROOT mancante per la build di prova"
  !endif
!endif

!include "MUI2.nsh"
!include "FileFunc.nsh"
!include "LogicLib.nsh"

Name "OCR2 ${VERSION}"
OutFile "${OUTFILE}"
InstallDir "$LOCALAPPDATA\Programs\OCR2"
ShowInstDetails show
ShowUninstDetails show

!define MUI_ABORTWARNING
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES
!insertmacro MUI_LANGUAGE "Italian"

; $R0 <- line 1 of $INSTDIR\active.txt, or "" when missing or not a plain version (digits and dots).
!macro READ_ACTIVE PREFIX
Function ${PREFIX}ReadActive
  StrCpy $R0 ""
  ClearErrors
  FileOpen $R1 "$INSTDIR\active.txt" r
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
!macroend
!insertmacro READ_ACTIVE ""
!insertmacro READ_ACTIVE "un."

Function .onInit
  SetShellVarContext current
!ifdef OCR2_TEST
  ; Test build: never the real program folder, only below the declared temporary root.
  ${If} $INSTDIR == "$LOCALAPPDATA\Programs\OCR2"
    MessageBox MB_ICONSTOP "Installer di prova: indica una cartella temporanea con /D=." /SD IDOK
    SetErrorLevel 2
    Quit
  ${EndIf}
  StrLen $0 "${OCR2_TEST_DATA_ROOT}\"
  StrCpy $1 $INSTDIR $0
  ${If} $1 != "${OCR2_TEST_DATA_ROOT}\"
    MessageBox MB_ICONSTOP "Installer di prova: la cartella deve trovarsi in ${OCR2_TEST_DATA_ROOT}." /SD IDOK
    SetErrorLevel 2
    Quit
  ${EndIf}
!endif
  Call ReadActive
  ${If} $R0 == "${VERSION}"
    MessageBox MB_ICONINFORMATION "Questa versione di OCR2 è già installata." /SD IDOK
    Quit
  ${EndIf}
FunctionEnd

Section "OCR2" SecMain
  SetShellVarContext current
  ; R7: versions\${VERSION} is not the active version here, so it is a leftover of an interrupted install.
  RMDir /r "$INSTDIR\versions\${VERSION}"
  ${If} ${FileExists} "$INSTDIR\versions\${VERSION}\*.*"
    MessageBox MB_ICONSTOP "Impossibile sostituire i file della versione ${VERSION}. Chiudi OCR2 con Esci e riprova." /SD IDOK
    SetErrorLevel 2
    Abort
  ${EndIf}
  SetOutPath "$INSTDIR\versions\${VERSION}"
  File /r "${PAYLOAD_DIR}\*.*"
  SetOutPath "$INSTDIR"
  File "/oname=OCR2.exe" "${LAUNCHER_EXE}"
  WriteUninstaller "$INSTDIR\uninstall.exe"
  DetailPrint "Verifica dei file della versione ${VERSION}..."
  nsExec::ExecToStack '"$INSTDIR\versions\${VERSION}\python\python.exe" -B -m alfa_document_intelligence.install_state activate ${VERSION}'
  Pop $0
  Pop $1
  ${If} $0 != "0"
    MessageBox MB_ICONSTOP "OCR2 ${VERSION} non è stato installato. Resta attiva la versione precedente.$\r$\n$1" /SD IDOK
    RMDir /r "$INSTDIR\versions\${VERSION}"
    SetErrorLevel 2
    Abort
  ${EndIf}
  DetailPrint "$1"
!ifndef OCR2_TEST
  CreateDirectory "$SMPROGRAMS\OCR2"
  CreateShortcut "$SMPROGRAMS\OCR2\OCR2.lnk" "$INSTDIR\OCR2.exe"
  CreateShortcut "$SMPROGRAMS\OCR2\Torna alla versione precedente.lnk" "$INSTDIR\OCR2.exe" "/rollback"
  CreateShortcut "$SMPROGRAMS\OCR2\Disinstalla OCR2.lnk" "$INSTDIR\uninstall.exe"
!endif
SectionEnd

Section "Uninstall"
  SetShellVarContext current
  ; $2 = 1: delete the user's data too.  Silent: only with /REMOVEDATA.  Otherwise ask, default no.
  StrCpy $2 "0"
  ${If} ${Silent}
    ${GetParameters} $3
    ClearErrors
    ${GetOptions} $3 "/REMOVEDATA" $4
    ${IfNot} ${Errors}
      StrCpy $2 "1"
    ${EndIf}
  ${Else}
    MessageBox MB_YESNO|MB_ICONQUESTION|MB_DEFBUTTON2 "Eliminare anche i dati di OCR2 (archivio e catalogo)?" /SD IDNO IDNO keep_data
    StrCpy $2 "1"
    keep_data:
  ${EndIf}
  Call un.ReadActive
  StrCpy $5 ""
  ${If} $R0 != ""
  ${AndIf} ${FileExists} "$INSTDIR\versions\$R0\python\python.exe"
    StrCpy $5 "$INSTDIR\versions\$R0\python\python.exe"
  ${EndIf}
  ${If} $5 == ""
    ; No usable program: nothing can check that OCR2 is closed or delete the data safely.
    ${If} $2 == "1"
      MessageBox MB_ICONSTOP "Programma OCR2 incompleto: i dati non possono essere eliminati. Reinstalla OCR2 e riprova." /SD IDOK
      SetErrorLevel 2
      Abort
    ${EndIf}
  ${Else}
    StrCpy $6 ""
    ${If} $2 == "1"
      StrCpy $6 " --remove-data"
    ${EndIf}
!ifdef OCR2_TEST
    StrCpy $6 '$6 --test-data-root "${OCR2_TEST_DATA_ROOT}"'
!endif
    nsExec::ExecToStack '"$5" -B -m alfa_document_intelligence.install_state uninstall$6'
    Pop $0
    Pop $1
    ${If} $0 != "0"
      MessageBox MB_ICONSTOP "OCR2 non è stato disinstallato.$\r$\n$1" /SD IDOK
      SetErrorLevel 2
      Abort
    ${EndIf}
    DetailPrint "$1"
  ${EndIf}
  ; Only the program's own items; the folder itself goes only once it is empty.
  RMDir /r "$INSTDIR\versions"
  Delete "$INSTDIR\active.txt"
  Delete "$INSTDIR\active.txt.tmp"
  Delete "$INSTDIR\OCR2.exe"
  Delete "$INSTDIR\uninstall.exe"
  RMDir "$INSTDIR"
!ifndef OCR2_TEST
  Delete "$SMPROGRAMS\OCR2\OCR2.lnk"
  Delete "$SMPROGRAMS\OCR2\Torna alla versione precedente.lnk"
  Delete "$SMPROGRAMS\OCR2\Disinstalla OCR2.lnk"
  RMDir "$SMPROGRAMS\OCR2"
!endif
SectionEnd
