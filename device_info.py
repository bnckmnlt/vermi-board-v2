import psutil
import os
import socket
from datetime import datetime


class DeviceInfo:
    def __init__(self):
        pass

    def get_cpu_temperature(self):
        temp = os.popen("vcgencmd measure_temp").readline()
        return temp.replace("temp=", "").replace("'C\n", "").strip()

    def get_memory_usage(self):
        memory = psutil.virtual_memory()
        return f"{memory.percent}%"

    def get_storage_usage(self):
        disk = psutil.disk_usage('/')
        return f"{disk.percent}%"

    def get_cpu_usage(self):
        cpu = psutil.cpu_percent(interval=1)
        return f"{cpu}%"

    def get_uptime(self):
        boot_time = psutil.boot_time()
        current_time = datetime.now().timestamp()
        uptime_seconds = int(current_time - boot_time)

        days = uptime_seconds // 86400
        hours = (uptime_seconds % 86400) // 3600
        minutes = (uptime_seconds % 3600) // 60

        if days > 0:
            return f"{days} days {hours} hours"
        elif hours > 0:
            return f"{hours} hours {minutes} min"
        else:
            return f"{minutes} min"

    def get_ip_address(self):
        return socket.gethostbyname(socket.gethostname())

    def get_pi_model(self):
        with open('/proc/cpuinfo') as f:
            cpuinfo = f.readlines()
        for line in cpuinfo:
            if 'Model' in line:
                return line.split(':')[1].strip()
        return "Unknown Model"

    def get_storage_usage(self):
        disk = psutil.disk_usage('/')
        return disk.percent

    def collect_device_info(self):
        device_info = {
            "Device Uptime": self.get_uptime(),
            "Device Board": self.get_pi_model(),
            "Operating System": "Raspbian OS",
            "CPU Usage": self.get_cpu_usage(),
            "CPU Temperature": f"{self.get_cpu_temperature()}°C",
            "Memory Usage": self.get_memory_usage(),
            "Network Interface": self.get_ip_address(),
            "Storage Usage": f"{self.get_storage_usage()}GB/120GB",
        }

        return device_info
