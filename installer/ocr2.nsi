; OCR2 per-user installer. Work in progress: lifecycle validation pending.
!include "FileFunc.nsh"
Unicode true
RequestExecutionLevel user
InstallDir "$LOCALAPPDATA\Programs\OCR2"

!ifndef OCR2_VERSION
  !error "OCR2_VERSION must be supplied"
!endif
!ifndef OCR2_PAYLOAD
  !error "OCR2_PAYLOAD must be supplied"
!endif
!ifndef OCR2_OUTPUT
  !error "OCR2_OUTPUT must be supplied"
!endif

Name "OCR2 ${OCR2_VERSION}"
OutFile "${OCR2_OUTPUT}"
ShowInstDetails show

Section "OCR2"
  SetShellVarContext current
  IfFileExists "$INSTDIR\versions\${OCR2_VERSION}\*" 0 new_version
    MessageBox MB_ICONSTOP "Questa versione di OCR2 esiste già."
    Abort
  new_version:
  SetOutPath "$INSTDIR\versions\${OCR2_VERSION}"
  File /r "${OCR2_PAYLOAD}\*"
  ExecWait '"$INSTDIR\versions\${OCR2_VERSION}\python\python.exe" -B -m alfa_document_intelligence.install_state --base "$INSTDIR" activate ${OCR2_VERSION}' $0
  IntCmp $0 0 activation_ok
    RMDir /r "$INSTDIR\versions\${OCR2_VERSION}"
    MessageBox MB_ICONSTOP "La verifica della nuova versione è fallita. La versione precedente rimane attiva."
    Abort
  activation_ok:
  WriteUninstaller "$INSTDIR\Uninstall.exe"
!ifndef OCR2_TEST
  CreateDirectory "$SMPROGRAMS\OCR2"
  CreateShortcut "$SMPROGRAMS\OCR2\OCR2.lnk" "$INSTDIR\versions\${OCR2_VERSION}\python\pythonw.exe" '-B -m alfa_document_intelligence --app-window --ocr-engine rapidocr-v6'
  CreateShortcut "$SMPROGRAMS\OCR2\Torna alla versione precedente.lnk" "$INSTDIR\Uninstall.exe" '/ROLLBACK'
  CreateShortcut "$SMPROGRAMS\OCR2\Disinstalla OCR2.lnk" "$INSTDIR\Uninstall.exe"
!endif
  ExecWait '"$INSTDIR\versions\${OCR2_VERSION}\python\python.exe" -B -m alfa_document_intelligence.install_state --base "$INSTDIR" prune' $0
  IntCmp $0 0 prune_ok
    MessageBox MB_ICONEXCLAMATION "Aggiornamento completato, ma alcune vecchie versioni non sono state rimosse." /SD IDOK
  prune_ok:
SectionEnd

Function un.onInit
  SetShellVarContext current
  ${GetParameters} $0
  ClearErrors
  ${GetOptions} $0 "/ROLLBACK" $1
  IfErrors normal_uninstall
  nsExec::ExecToStack '"$INSTDIR\versions\${OCR2_VERSION}\python\python.exe" -B -m alfa_document_intelligence.install_state --base "$INSTDIR" rollback'
  Pop $0
  Pop $1
  StrCmp $0 "0" rollback_ok
    MessageBox MB_ICONSTOP "Impossibile ripristinare la versione precedente."
    Quit
  rollback_ok:
  StrCpy $1 $1 -2
!ifndef OCR2_TEST
  CreateShortcut "$SMPROGRAMS\OCR2\OCR2.lnk" "$INSTDIR\versions\$1\python\pythonw.exe" '-B -m alfa_document_intelligence --app-window --ocr-engine rapidocr-v6'
!endif
  Quit
  normal_uninstall:
FunctionEnd

Section "Uninstall"
  SetShellVarContext current
  MessageBox MB_YESNO|MB_ICONQUESTION|MB_DEFBUTTON2 "Vuoi eliminare anche i dati locali OCR2?" /SD IDNO IDYES remove_data
  Goto keep_data
  remove_data:
!ifndef OCR2_TEST
  RMDir /r "$LOCALAPPDATA\OCR2"
!endif
  keep_data:
!ifndef OCR2_TEST
  Delete "$SMPROGRAMS\OCR2\OCR2.lnk"
  Delete "$SMPROGRAMS\OCR2\Torna alla versione precedente.lnk"
  Delete "$SMPROGRAMS\OCR2\Disinstalla OCR2.lnk"
  RMDir "$SMPROGRAMS\OCR2"
!endif
  RMDir /r "$INSTDIR\versions"
  Delete "$INSTDIR\active.json"
  Delete "$INSTDIR\Uninstall.exe"
  RMDir "$INSTDIR"
SectionEnd
