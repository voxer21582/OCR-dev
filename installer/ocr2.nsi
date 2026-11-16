; OCR2 per-user installer. Work in progress: rollback and uninstall pending.
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
!ifndef OCR2_TEST
  CreateDirectory "$SMPROGRAMS\OCR2"
  CreateShortcut "$SMPROGRAMS\OCR2\OCR2.lnk" "$INSTDIR\versions\${OCR2_VERSION}\python\pythonw.exe" '-B -m alfa_document_intelligence --app-window --ocr-engine rapidocr-v6'
!endif
SectionEnd
