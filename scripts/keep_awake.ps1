Add-Type -Namespace Studio -Name Power -MemberDefinition '[DllImport("kernel32.dll")] public static extern uint SetThreadExecutionState(uint esFlags);'
$awakeFlags = [uint32]::Parse('2147483649')
$clearFlags = [uint32]::Parse('2147483648')
try {
  [Studio.Power]::SetThreadExecutionState($awakeFlags) | Out-Null
  Start-Sleep -Seconds 21600
} finally { [Studio.Power]::SetThreadExecutionState($clearFlags) | Out-Null }
