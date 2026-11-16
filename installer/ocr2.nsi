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
!ifndef OCR2_TEST
  !ifndef OCR2_CERT_THUMBPRINT
    !error "Release builds require the expected signing certificate thumbprint"
  !endif
  !system 'python -B "verify_payload.py" "${OCR2_PAYLOAD}" "${OCR2_VERSION}"' = 0
  !system 'python -B "verify_release_inventory.py" "${OCR2_PAYLOAD}"' = 0
  !system 'pwsh.exe -NoProfile -NonInteractive -File "verify-runtime-signatures.ps1" -Payload "${OCR2_PAYLOAD}" -Thumbprint "${OCR2_CERT_THUMBPRINT}"' = 0
!endif
!ifdef OCR2_SIGN_COMMAND
  !ifdef OCR2_TEST
    !uninstfinalize '${OCR2_SIGN_COMMAND} "%1"' = 0
    !finalize '${OCR2_SIGN_COMMAND} "%1"' = 0
  !else
    !uninstfinalize '${OCR2_SIGN_COMMAND} "%1" && pwsh.exe -NoProfile -NonInteractive -File "verify-signature.ps1" -Installer "%1" -ExpectedThumbprint "${OCR2_CERT_THUMBPRINT}"' = 0
    !finalize '${OCR2_SIGN_COMMAND} "%1" && pwsh.exe -NoProfile -NonInteractive -File "verify-signature.ps1" -Installer "%1" -ExpectedThumbprint "${OCR2_CERT_THUMBPRINT}"' = 0
  !endif
!else
  !ifndef OCR2_TEST
    !error "Release builds require signing"
  !endif
!endif

Name "OCR2 ${OCR2_VERSION}"
OutFile "${OCR2_OUTPUT}"
ShowInstDetails show

Function .onInit
!ifndef OCR2_TEST
  StrCpy $INSTDIR "$LOCALAPPDATA\Programs\OCR2"
!endif
FunctionEnd

; Check every existing component before touching an installation or lock path.
!macro DefinePathValidation PREFIX
Function ${PREFIX}AssertSafePath
  Exch $0
  Push $1
  Push $2
  Push $3
  ${GetRoot} "$0" $2
  StrCmp $2 "" unsafe_path
  path_loop:
  System::Call 'kernel32::GetFileAttributesW(w r0) i.r1 ?e'
  Pop $3
  IntCmp $1 -1 path_missing
  IntOp $1 $1 & 0x400
  IntCmp $1 0 path_parent unsafe_path unsafe_path
  path_missing:
  IntCmp $3 2 path_parent
  IntCmp $3 3 path_parent unsafe_path unsafe_path
  path_parent:
  StrCmp $0 $2 safe_path
  ${GetParent} "$0" $1
  StrCmp $1 "" unsafe_path
  StrCmp $1 $0 unsafe_path
  StrCpy $0 $1
  Goto path_loop
  unsafe_path:
  Pop $3
  Pop $2
  Pop $1
  Pop $0
  MessageBox MB_OK|MB_ICONSTOP "Operazione interrotta: percorso OCR2 non sicuro." /SD IDOK
  SetErrorLevel 1
  Abort
  safe_path:
  Pop $3
  Pop $2
  Pop $1
  Pop $0
FunctionEnd

Function ${PREFIX}ValidateInstallPaths
  Push "$INSTDIR"
  Call ${PREFIX}AssertSafePath
  Push "$INSTDIR\staging"
  Call ${PREFIX}AssertSafePath
  Push "$INSTDIR\versions"
  Call ${PREFIX}AssertSafePath
  Push "$INSTDIR\versions\${OCR2_VERSION}\python\python.exe"
  Call ${PREFIX}AssertSafePath
  Push "$INSTDIR\quarantine"
  Call ${PREFIX}AssertSafePath
  Push "$INSTDIR\.child.lock"
  Call ${PREFIX}AssertSafePath
FunctionEnd
!macroend
!insertmacro DefinePathValidation ""
!insertmacro DefinePathValidation "un."

!macro DefineCoordinationFunctions PREFIX
Function ${PREFIX}AcquireLock
!ifdef OCR2_TEST
  StrCpy $8 "$INSTDIR\test-user-data"
!else
  StrCpy $8 "$LOCALAPPDATA\OCR2"
!endif
  Push "$8"
  Call ${PREFIX}AssertSafePath
  Push "$8.instance.lock"
  Call ${PREFIX}AssertSafePath
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
  System::Call 'kernel32::GetCurrentProcessId() i.r6'
  System::Call 'kernel32::GetProcessTimes(p -1, *l .r2, *l .r3, *l .r4, *l .r5) i.r0'
  IntCmp $0 0 lock_failed
  System::Call 'kernel32::SetEnvironmentVariableW(w "OCR2_INSTALL_PARENT_PID", w r6) i.r0'
  IntCmp $0 0 lock_failed
  System::Call 'kernel32::SetEnvironmentVariableW(w "OCR2_INSTALL_PARENT_START", w r2) i.r0'
  IntCmp $0 0 lock_failed
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
  System::Call 'kernel32::SetEnvironmentVariableW(w "OCR2_INSTALL_PARENT_PID", p 0) i.r0'
  System::Call 'kernel32::SetEnvironmentVariableW(w "OCR2_INSTALL_PARENT_START", p 0) i.r0'
  System::Call 'kernel32::CloseHandle(p r9)'
FunctionEnd
!macroend
!insertmacro DefineCoordinationFunctions ""
!insertmacro DefineCoordinationFunctions "un."

Section "OCR2"
  SetShellVarContext current
  Call ValidateInstallPaths
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

Function un.RunVersionCommand
  Pop $5
  ClearErrors
  FindFirst $3 $4 "$INSTDIR\versions\*"
  IfErrors version_command_failed_no_handle
  version_command_loop:
  StrCmp $4 "." version_command_next
  StrCmp $4 ".." version_command_next
  IfFileExists "$INSTDIR\versions\$4\python\python.exe" 0 version_command_next
  Push "$INSTDIR\versions\$4\python\python.exe"
  Call un.AssertSafePath
  nsExec::ExecToStack '"$INSTDIR\versions\$4\python\python.exe" -B -m alfa_document_intelligence.install_state --base "$INSTDIR" verify "$4"'
  Pop $0
  Pop $1
  StrCmp $0 "0" 0 version_command_next
  nsExec::ExecToStack '"$INSTDIR\versions\$4\python\python.exe" -B -m alfa_document_intelligence.install_state --base "$INSTDIR" $5'
  Pop $0
  Pop $1
  StrCmp $0 "0" version_command_success
  version_command_next:
  ClearErrors
  FindNext $3 $4
  IfErrors version_command_failed
  Goto version_command_loop
  version_command_success:
  FindClose $3
  Push $1
  Return
  version_command_failed:
  FindClose $3
  version_command_failed_no_handle:
  Push ""
FunctionEnd

Function un.onInit
  SetShellVarContext current
  Call un.ValidateInstallPaths
  ${GetParameters} $0
  ClearErrors
  ${GetOptions} $0 "/LAUNCH" $1
  IfErrors check_rollback
  Push "active"
  Call un.RunVersionCommand
  Pop $1
  StrCmp $1 "" 0 launch_ok
    MessageBox MB_OK|MB_ICONSTOP "Impossibile avviare la versione attiva di OCR2." /SD IDOK
    Quit
  launch_ok:
  StrCpy $1 $1 -2
  Push "$INSTDIR\versions\$1\python\pythonw.exe"
  Call un.AssertSafePath
!ifdef OCR2_TEST
  FileOpen $3 "$INSTDIR\test-launch-version.txt" w
  FileWrite $3 "$1"
  FileClose $3
!else
  Exec '"$INSTDIR\versions\$1\python\pythonw.exe" -B -m alfa_document_intelligence --app-window --ocr-engine rapidocr-v6'
!endif
  Quit
  check_rollback:
  ClearErrors
  ${GetOptions} $0 "/ROLLBACK" $1
  IfErrors normal_uninstall
  Call un.AcquireLock
  Push "rollback"
  Call un.RunVersionCommand
  Call un.ReleaseLock
  Pop $1
  StrCmp $1 "" 0 rollback_ok
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
  InitPluginsDir
  IfErrors uninstall_failed
  SetOutPath "$PLUGINSDIR"
  IfErrors uninstall_failed
  File /oname=removal_check.py "..\application\src\alfa_document_intelligence\removal_check.py"
  IfErrors uninstall_failed
  ClearErrors
  FindFirst $3 $4 "$INSTDIR\versions\*"
  IfErrors cleanup_missing_no_handle
  cleanup_find:
  StrCmp $4 "." cleanup_next
  StrCmp $4 ".." cleanup_next
  IfFileExists "$INSTDIR\versions\$4\python\python.exe" 0 cleanup_next
  Push "$INSTDIR\versions\$4\python\python.exe"
  Call un.AssertSafePath
  ClearErrors
  ExecWait '"$INSTDIR\versions\$4\python\python.exe" -B -m alfa_document_intelligence.install_state --base "$INSTDIR" verify "$4"' $0
  IfErrors cleanup_next
  IntCmp $0 0 cleanup_try cleanup_next cleanup_next
  cleanup_try:
  ClearErrors
  ExecWait '"$INSTDIR\versions\$4\python\python.exe" -B "$PLUGINSDIR\removal_check.py" --base "$INSTDIR"' $0
  IfErrors cleanup_next
  IntCmp $0 0 cleanup_supported cleanup_next cleanup_next
  cleanup_supported:
  ClearErrors
  ExecWait '"$INSTDIR\versions\$4\python\python.exe" -B "$PLUGINSDIR\removal_check.py" --base "$INSTDIR" --cleanup-debris' $0
  IfErrors cleanup_next
  IntCmp $0 0 cleanup_done cleanup_next cleanup_next
  cleanup_next:
  ClearErrors
  FindNext $3 $4
  IfErrors cleanup_missing
  Goto cleanup_find
  cleanup_missing:
  FindClose $3
  cleanup_missing_no_handle:
  Call un.ReleaseLock
  MessageBox MB_OK|MB_ICONSTOP "Nessuna versione integra disponibile. Reinstalla OCR2, poi riprova la disinstallazione." /SD IDOK
  SetErrorLevel 1
  Abort
  cleanup_done:
  FindClose $3
  StrCpy $6 $4
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
  Push "$INSTDIR\versions\$6\python\python.exe"
  Call un.AssertSafePath
  ClearErrors
  ExecWait '"$INSTDIR\versions\$6\python\python.exe" -B "$PLUGINSDIR\removal_check.py" --base "$INSTDIR" --data "$8"' $0
  IfErrors uninstall_failed
  IntCmp $0 0 data_checked uninstall_failed uninstall_failed
  data_checked:
  System::Call 'kernel32::GetFileAttributesW(w r8) i.r0'
  IntCmp $0 -1 keep_data
  ClearErrors
  RMDir /r "$8"
  IfErrors uninstall_failed
  keep_data:
  Push "$INSTDIR\versions\$6\python\python.exe"
  Call un.AssertSafePath
  ClearErrors
  ExecWait '"$INSTDIR\versions\$6\python\python.exe" -B "$PLUGINSDIR\removal_check.py" --base "$INSTDIR"' $0
  IfErrors uninstall_failed
  IntCmp $0 0 versions_checked uninstall_failed uninstall_failed
  versions_checked:
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
