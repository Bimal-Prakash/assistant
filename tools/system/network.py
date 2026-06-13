import subprocess

def _wifi_interface_name() -> str:
    result = subprocess.run(
        ["netsh", "interface", "show", "interface"],
        capture_output=True,
        text=True,
        check=False,
    )
    output = (result.stdout or "").lower()
    for line in output.splitlines():
        if "wi-fi" in line or "wifi" in line or "wireless" in line:
            parts = line.split()
            if parts:
                return " ".join(parts[3:]) if len(parts) > 3 else parts[-1]
    return "Wi-Fi"

def network_control(network_type: str, state: str) -> str:
    network_type = network_type.lower().strip()
    state = state.lower().strip()

    if network_type == "wifi":
        if state == "open":
            subprocess.Popen(["cmd", "/c", "start", "ms-settings:network-wifi"], shell=False)
            return "Opened Wi-Fi settings."
        admin_state = "enabled" if state == "on" else "disabled"
        iface = _wifi_interface_name()
        command = ["netsh", "interface", "set", "interface", iface, f"admin={admin_state}"]
        result = subprocess.run(command, capture_output=True, text=True, check=False)
        if result.returncode == 0:
            return f"Wi-Fi turned {state}"
        error_text = (result.stderr or result.stdout or "Failed to toggle Wi-Fi").strip()
        if "requires elevation" in error_text.lower() or "run as administrator" in error_text.lower():
            subprocess.Popen(["cmd", "/c", "start", "ms-settings:network-wifi"], shell=False)
            return "Successfully opened Wi-Fi settings so the user can toggle it manually."
        raise RuntimeError(error_text)

    if network_type == "bluetooth":
        if state in {"on", "off"}:
            desired = "On" if state == "on" else "Off"
            ps_script = (
                "Add-Type -AssemblyName System.Runtime.WindowsRuntime; "
                "$null = [Windows.Devices.Radios.Radio,Windows.Devices.Radios,ContentType=WindowsRuntime]; "
                "$null = [Windows.Devices.Radios.RadioAccessStatus,Windows.Devices.Radios,ContentType=WindowsRuntime]; "
                "$null = [Windows.Devices.Radios.RadioState,Windows.Devices.Radios,ContentType=WindowsRuntime]; "
                "$access = [Windows.Devices.Radios.Radio]::RequestAccessAsync().AsTask().GetAwaiter().GetResult(); "
                "if ($access -ne [Windows.Devices.Radios.RadioAccessStatus]::Allowed) { exit 5 }; "
                "$radios = [Windows.Devices.Radios.Radio]::GetRadiosAsync().AsTask().GetAwaiter().GetResult(); "
                "$bt = $radios | Where-Object { $_.Kind -eq [Windows.Devices.Radios.RadioKind]::Bluetooth } | Select-Object -First 1; "
                "if ($null -eq $bt) { exit 6 }; "
                f"$result = $bt.SetStateAsync([Windows.Devices.Radios.RadioState]::{desired}).AsTask().GetAwaiter().GetResult(); "
                "if ($result -ne [Windows.Devices.Radios.RadioAccessStatus]::Allowed) { exit 7 }; "
                "exit 0"
            )
            result = subprocess.run(
                ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps_script],
                capture_output=True,
                text=True,
                check=False,
            )
            if result.returncode == 0:
                return f"Bluetooth turned {state}"

        subprocess.Popen(["cmd", "/c", "start", "ms-settings:bluetooth"], shell=False)
        return "Successfully opened Bluetooth settings so the user can toggle it manually."

    raise ValueError("Unsupported network type")
