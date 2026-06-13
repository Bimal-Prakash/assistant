"""Network control tool — WiFi and Bluetooth on/off."""


def exec_network_control(type: str = "", state: str = "") -> str:
    from tools.system.network import network_control
    if not type or not state:
        return "Error executing network_control: 'type' (wifi/bluetooth) and 'state' (on/off) are required."
    return network_control(type.strip().lower(), state.strip().lower())
