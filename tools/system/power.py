import logging
import time
import subprocess

logger = logging.getLogger("jarvis.pc_controls.power")

def power_control(power_type: str, delay_seconds: int = 3) -> str:
    power_type = power_type.lower()

    if power_type == "shutdown":
        command = ["shutdown", "/s", "/t", "1"]
        message = "Shutting down PC"
    elif power_type == "restart":
        command = ["shutdown", "/r", "/t", "1"]
        message = "Restarting PC"
    elif power_type == "sleep":
        command = ["rundll32.exe", "powrprof.dll,SetSuspendState", "0,1,0"]
        message = "Putting PC to sleep"
    else:
        raise ValueError("Unsupported power type")

    logger.warning("Power action requested: %s. Executing in %s seconds.", power_type, delay_seconds)
    time.sleep(delay_seconds)
    subprocess.run(command, check=False)
    return message
