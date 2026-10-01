import json
import socket
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, HTTPServer

SOCKET_PATH = "/var/run/docker.sock"


def docker_get(path):
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    sock.connect(SOCKET_PATH)
    sock.sendall(f"GET {path} HTTP/1.1\r\nHost: docker\r\nConnection: close\r\n\r\n".encode())
    chunks = []
    while chunk := sock.recv(65536):
        chunks.append(chunk)
    sock.close()
    response = b"".join(chunks)
    headers, body = response.split(b"\r\n\r\n", 1)
    if b"transfer-encoding: chunked" in headers.lower():
        decoded = []
        while body:
            size_end = body.find(b"\r\n")
            size = int(body[:size_end], 16)
            if size == 0:
                break
            start = size_end + 2
            decoded.append(body[start:start + size])
            body = body[start + size + 2:]
        body = b"".join(decoded)
    return json.loads(body)


def esc(value):
    return str(value).replace("\\", "\\\\").replace('"', '\\"').replace("\n", " ")


def collect_container(container):
    name = container["Names"][0].lstrip("/")
    cid = container["Id"][:12]
    labels = f'name="{esc(name)}",id="{cid}",image="{esc(container.get("Image", ""))}"'
    try:
        stats = docker_get(f"/containers/{container['Id']}/stats?stream=false")
        cpu = stats.get("cpu_stats", {})
        previous = stats.get("precpu_stats", {})
        cpu_delta = cpu.get("cpu_usage", {}).get("total_usage", 0) - previous.get("cpu_usage", {}).get("total_usage", 0)
        system_delta = cpu.get("system_cpu_usage", 0) - previous.get("system_cpu_usage", 0)
        online = cpu.get("online_cpus", 1) or 1
        cpu_percent = (cpu_delta / system_delta) * online * 100 if system_delta > 0 else 0
        memory = stats.get("memory_stats", {})
        networks = stats.get("networks", {}).values()
        rx = sum(item.get("rx_bytes", 0) for item in networks)
        tx = sum(item.get("tx_bytes", 0) for item in stats.get("networks", {}).values())
        return [
            f"getter_container_info{{{labels},state=\"{esc(container.get('State', ''))}\"}} 1",
            f"getter_container_cpu_usage_percent{{{labels}}} {cpu_percent}",
            f"getter_container_memory_usage_bytes{{{labels}}} {memory.get('usage', 0)}",
            f"getter_container_network_receive_bytes_total{{{labels}}} {rx}",
            f"getter_container_network_transmit_bytes_total{{{labels}}} {tx}",
        ]
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError):
        return []


def collect():
    lines = [
        "# HELP getter_container_info Container metadata.",
        "# TYPE getter_container_info gauge",
        "# HELP getter_container_cpu_usage_percent Container CPU usage.",
        "# TYPE getter_container_cpu_usage_percent gauge",
        "# HELP getter_container_memory_usage_bytes Container memory usage.",
        "# TYPE getter_container_memory_usage_bytes gauge",
        "# HELP getter_container_network_receive_bytes_total Container received bytes.",
        "# TYPE getter_container_network_receive_bytes_total counter",
        "# HELP getter_container_network_transmit_bytes_total Container transmitted bytes.",
        "# TYPE getter_container_network_transmit_bytes_total counter",
    ]
    containers = docker_get("/containers/json")
    with ThreadPoolExecutor(max_workers=16) as pool:
        for metrics in pool.map(collect_container, containers):
            lines.extend(metrics)
    return "\n".join(lines) + "\n"


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path != "/metrics":
            self.send_response(404)
            self.end_headers()
            return
        body = collect().encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; version=0.0.4")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_):
        return


if __name__ == "__main__":
    HTTPServer(("0.0.0.0", 9410), Handler).serve_forever()
