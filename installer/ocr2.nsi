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
!ifdef OCR2_SIGN_COMMAND
  !uninstfinalize '${OCR2_SIGN_COMMAND} "%1"' = 0
  !finalize '${OCR2_SIGN_COMMAND} "%1"' = 0
!else
  !ifndef OCR2_TEST
    !error "Release builds require signing"
  !endif
!endif

Name "OCR2 ${OCR2_VERSION}"
OutFile "${OCR2_OUTPUT}"
ShowInstDetails show

!macro DefineCoordinationFunctions PREFIX
Function ${PREFIX}AcquireLock
!ifdef OCR2_TEST
  StrCpy $8 "$INSTDIR\test-user-data"
!else
  StrCpy $8 "$LOCALAPPDATA\OCR2"
!endif
  System::Call 'kernel32::GetFileAttributesW(w r8) i.r0'
  IntCmp $0 -1 safe_lock_directory
  IntOp $0 $0 & 0x400
  IntCmp $0 0 safe_lock_directory lock_failed_no_handle lock_failed_no_handle
  safe_lock_directory:
  System::Call 'kernel32::CreateFileW(w "$8.instance.lock", i 0xC0000000, i 7, p 0, i 4, i 0x80, p 0) p.r9'
  IntCmp $9 -1 lock_failed_no_handle
  System::Call 'kernel32::LockFile(p r9, i 0, i 0, i 1, i 0) i.r0'
  IntCmp $0 0 lock_failed
  System::Call 'kernel32::CreateFileW(w "$INSTDIR\.child.lock", i 0xC0000000, i 7, p 0, i 4, i 0x80, p 0) p.r7'
  IntCmp $7 -1 lock_failed
  System::Call 'kernel32::LockFile(p r7, i 0, i 0, i 1, i 0) i.r0'
  IntCmp $0 0 child_lock_failed
  System::Call 'kernel32::CloseHandle(p r7)'
  System::Call 'kernel32::SetEnvironmentVariableW(w "OCR2_INSTALL_LOCK_HELD", w "1") i.r0'
  IntCmp $0 0 lock_failed
  Return
  child_lock_failed:
  System::Call 'kernel32::CloseHandle(p r7)'
  lock_failed:
  System::Call 'kernel32::CloseHandle(p r9)'
  lock_failed_no_handle:
  MessageBox MB_OK|MB_ICONSTOP "Chiudi OCR2 e gli altri installer prima di continuare." /SD IDOK
  SetErrorLevel 1
  Abort
FunctionEnd
Function ${PREFIX}ReleaseLock
  System::Call 'kernel32::SetEnvironmentVariableW(w "OCR2_INSTALL_LOCK_HELD", p 0) i.r0'
  System::Call 'kernel32::CloseHandle(p r9)'
FunctionEnd
!macroend
!insertmacro DefineCoordinationFunctions ""
!insertmacro DefineCoordinationFunctions "un."

Section "OCR2"
  SetShellVarContext current
  CreateDirectory "$INSTDIR"
  Call AcquireLock
  IfFileExists "$INSTDIR\versions\${OCR2_VERSION}\*" check_existing extract_candidate
  check_existing:
  ClearErrors
  ExecWait '"$INSTDIR\versions\${OCR2_VERSION}\python\python.exe" -B -m alfa_document_intelligence.install_state --base "$INSTDIR" verify ${OCR2_VERSION}' $1
  IfErrors extract_candidate
  IntCmp $1 0 verified
  extract_candidate:
  CreateDirectory "$INSTDIR\staging"
  CreateDirectory "$INSTDIR\versions"
  ClearErrors
  GetTempFileName $0 "$INSTDIR\staging"
  IfErrors extraction_failed
  Delete "$0"
  CreateDirectory "$0"
  IfErrors extraction_failed
  SetOutPath "$0"
  File /r "${OCR2_PAYLOAD}\*"
  IfErrors extraction_failed
  SetOutPath "$INSTDIR"
  ClearErrors
  ExecWait '"$0\python\python.exe" -B -m alfa_document_intelligence.install_state --base "$INSTDIR" check-stage ${OCR2_VERSION} "$0"' $1
  IfErrors extraction_failed
  IntCmp $1 0 stage_checked
  Goto extraction_failed
  stage_checked:
  StrCpy $2 ""
  IfFileExists "$INSTDIR\versions\${OCR2_VERSION}\*" quarantine_candidate move_candidate
  quarantine_candidate:
  CreateDirectory "$INSTDIR\quarantine"
  ClearErrors
  GetTempFileName $2 "$INSTDIR\quarantine"
  IfErrors extraction_failed
  Delete "$2"
  Rename "$INSTDIR\versions\${OCR2_VERSION}" "$2"
  IfErrors extraction_failed
  move_candidate:
  ClearErrors
  Rename "$0" "$INSTDIR\versions\${OCR2_VERSION}"
  IfErrors restore_candidate
  Goto candidate_ready
  restore_candidate:
  StrCmp $2 "" extraction_failed
  Rename "$2" "$INSTDIR\versions\${OCR2_VERSION}"
  Goto extraction_failed
  extraction_failed:
    Call ReleaseLock
    MessageBox MB_OK|MB_ICONSTOP "Estrazione non riuscita. La versione attiva non è stata cambiata." /SD IDOK
    Abort
  candidate_ready:
  ClearErrors
  ExecWait '"$INSTDIR\versions\${OCR2_VERSION}\python\python.exe" -B -m alfa_document_intelligence.install_state --base "$INSTDIR" verify ${OCR2_VERSION}' $0
  IfErrors verification_failed
  IntCmp $0 0 verified
  verification_failed:
    Call ReleaseLock
    MessageBox MB_OK|MB_ICONSTOP "La verifica della nuova versione è fallita. La versione precedente rimane attiva." /SD IDOK
    Abort
  verified:
  ClearErrors
  WriteUninstaller "$INSTDIR\Uninstall.exe"
  IfErrors extraction_failed
!ifndef OCR2_TEST
  ClearErrors
  CreateDirectory "$SMPROGRAMS\OCR2"
  CreateShortcut "$SMPROGRAMS\OCR2\OCR2.lnk" "$INSTDIR\Uninstall.exe" '/LAUNCH'
  CreateShortcut "$SMPROGRAMS\OCR2\Torna alla versione precedente.lnk" "$INSTDIR\Uninstall.exe" '/ROLLBACK'
  CreateShortcut "$SMPROGRAMS\OCR2\Disinstalla OCR2.lnk" "$INSTDIR\Uninstall.exe"
  IfErrors shortcut_failed
  Goto shortcut_ok
  shortcut_failed:
  Call ReleaseLock
  MessageBox MB_OK|MB_ICONSTOP "Impossibile creare i collegamenti nel menu Start." /SD IDOK
  Abort
  shortcut_ok:
!endif
  ClearErrors
  ExecWait '"$INSTDIR\versions\${OCR2_VERSION}\python\python.exe" -B -m alfa_document_intelligence.install_state --base "$INSTDIR" activate ${OCR2_VERSION}' $0
  IfErrors activation_failed
  IntCmp $0 0 activation_ok
  activation_failed:
    Call ReleaseLock
    MessageBox MB_OK|MB_ICONSTOP "Attivazione non riuscita. La versione precedente rimane attiva." /SD IDOK
    Abort
  activation_ok:
  ClearErrors
  ExecWait '"$INSTDIR\versions\${OCR2_VERSION}\python\python.exe" -B -m alfa_document_intelligence.install_state --base "$INSTDIR" prune' $0
  IfErrors prune_failed
  IntCmp $0 0 prune_ok
  prune_failed:
    MessageBox MB_OK|MB_ICONEXCLAMATION "Aggiornamento completato, ma alcune vecchie versioni non sono state rimosse." /SD IDOK
  prune_ok:
  Call ReleaseLock
SectionEnd

Function un.onInit
  SetShellVarContext current
  ${GetParameters} $0
  ClearErrors
  ${GetOptions} $0 "/LAUNCH" $1
  IfErrors check_rollback
  nsExec::ExecToStack '"$INSTDIR\versions\${OCR2_VERSION}\python\python.exe" -B -m alfa_document_intelligence.install_state --base "$INSTDIR" active'
  Pop $0
  Pop $1
  StrCmp $0 "0" launch_ok
    MessageBox MB_OK|MB_ICONSTOP "Impossibile avviare la versione attiva di OCR2." /SD IDOK
    Quit
  launch_ok:
  StrCpy $1 $1 -2
  Exec '"$INSTDIR\versions\$1\python\pythonw.exe" -B -m alfa_document_intelligence --app-window --ocr-engine rapidocr-v6'
  Quit
  check_rollback:
  ClearErrors
  ${GetOptions} $0 "/ROLLBACK" $1
  IfErrors normal_uninstall
  Call un.AcquireLock
  nsExec::ExecToStack '"$INSTDIR\versions\${OCR2_VERSION}\python\python.exe" -B -m alfa_document_intelligence.install_state --base "$INSTDIR" rollback'
  Pop $0
  Pop $1
  StrCpy $2 $0
  Call un.ReleaseLock
  StrCmp $2 "0" rollback_ok
    MessageBox MB_OK|MB_ICONSTOP "Impossibile ripristinare la versione precedente."
    Quit
  rollback_ok:
  Quit
  normal_uninstall:
FunctionEnd

Section "Uninstall"
  SetShellVarContext current
  Call un.AcquireLock
  ClearErrors
  ExecWait '"$INSTDIR\versions\${OCR2_VERSION}\python\python.exe" -B -m alfa_document_intelligence.install_state --base "$INSTDIR" cleanup-debris' $0
  IfErrors uninstall_failed
  IntCmp $0 0 cleanup_done
  Goto uninstall_failed
  cleanup_done:
!ifdef OCR2_TEST
  ${GetParameters} $0
  ClearErrors
  ${GetOptions} $0 "/TEST-REMOVE-DATA" $1
  IfErrors ask_remove_data
  Goto remove_data
  ask_remove_data:
!endif
  MessageBox MB_YESNO|MB_ICONQUESTION|MB_DEFBUTTON2 "Vuoi eliminare anche i dati locali OCR2?" /SD IDNO IDYES remove_data
  Goto keep_data
  remove_data:
  System::Call 'kernel32::GetFileAttributesW(w r8) i.r0'
  IntCmp $0 -1 keep_data
  ClearErrors
  RMDir /r "$8"
  IfErrors uninstall_failed
  keep_data:
  ClearErrors
  RMDir /r "$INSTDIR\versions"
  IfErrors uninstall_failed
  Delete "$INSTDIR\active.json"
  IfErrors uninstall_failed
!ifndef OCR2_TEST
  Delete "$SMPROGRAMS\OCR2\OCR2.lnk"
  Delete "$SMPROGRAMS\OCR2\Torna alla versione precedente.lnk"
  Delete "$SMPROGRAMS\OCR2\Disinstalla OCR2.lnk"
  RMDir "$SMPROGRAMS\OCR2"
!endif
  Delete "$INSTDIR\Uninstall.exe"
  Delete "$INSTDIR\.child.lock"
  ClearErrors
  RMDir "$INSTDIR"
!ifndef OCR2_TEST
  IfErrors uninstall_dir_remaining
!endif
  Call un.ReleaseLock
  Goto uninstall_done
!ifndef OCR2_TEST
  uninstall_dir_remaining:
  Call un.ReleaseLock
  MessageBox MB_OK|MB_ICONEXCLAMATION "La cartella OCR2 non è vuota e non è stata rimossa." /SD IDOK
  Goto uninstall_done
!endif
  uninstall_failed:
  Call un.ReleaseLock
  MessageBox MB_OK|MB_ICONSTOP "Disinstallazione incompleta: chiudi OCR2 e riprova. Alcuni file potrebbero essere rimasti." /SD IDOK
  SetErrorLevel 1
  Abort
  uninstall_done:
SectionEnd
