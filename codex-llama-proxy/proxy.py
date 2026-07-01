#!/usr/bin/env python3
import argparse
import http.client
import json
import logging
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit


HOP_BY_HOP_HEADERS = {
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailer",
    "transfer-encoding",
    "upgrade",
}


def rewrite_responses_request(payload):
    items = payload.get("input")
    if not isinstance(items, list):
        return payload, 0

    rewritten = []
    image_count = 0
    for item in items:
        if (
            not isinstance(item, dict)
            or item.get("type") != "function_call_output"
            or not isinstance(item.get("output"), list)
        ):
            rewritten.append(item)
            continue

        text_outputs = []
        image_outputs = []
        for output in item["output"]:
            if isinstance(output, dict) and output.get("type") == "input_image":
                image_outputs.append(output)
            else:
                text_outputs.append(output)

        if not image_outputs:
            rewritten.append(item)
            continue

        tool_item = dict(item)
        tool_item["output"] = text_outputs or [
            {
                "type": "input_text",
                "text": "[Image returned separately by the tool]",
            }
        ]
        rewritten.append(tool_item)

        call_id = item.get("call_id", "unknown")
        rewritten.append(
            {
                "type": "message",
                "role": "user",
                "content": [
                    {
                        "type": "input_text",
                        "text": f"Image returned by tool call {call_id}:",
                    },
                    *image_outputs,
                ],
            }
        )
        image_count += len(image_outputs)

    if image_count:
        payload = dict(payload)
        payload["input"] = rewritten
    return payload, image_count


class ProxyHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    upstream_host = "127.0.0.1"
    upstream_port = 8085

    def do_GET(self):
        self._proxy()

    def do_POST(self):
        self._proxy()

    def do_OPTIONS(self):
        self._proxy()

    def _proxy(self):
        content_length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(content_length) if content_length else b""

        if self.command == "POST" and self.path.split("?", 1)[0] == "/v1/responses":
            content_type = self.headers.get("Content-Type", "")
            if "application/json" in content_type and body:
                try:
                    payload = json.loads(body)
                    payload, image_count = rewrite_responses_request(payload)
                    if image_count:
                        body = json.dumps(
                            payload, ensure_ascii=False, separators=(",", ":")
                        ).encode()
                        logging.info(
                            "rewrote %d tool-output image(s) for %s",
                            image_count,
                            self.path,
                        )
                except (json.JSONDecodeError, TypeError, ValueError) as exc:
                    logging.warning("request rewrite skipped: %s", exc)

        headers = {
            key: value
            for key, value in self.headers.items()
            if key.lower() not in HOP_BY_HOP_HEADERS
            and key.lower() not in {"host", "content-length"}
        }
        if body:
            headers["Content-Length"] = str(len(body))

        upstream = http.client.HTTPConnection(
            self.upstream_host, self.upstream_port, timeout=600
        )
        try:
            upstream.request(self.command, self.path, body=body, headers=headers)
            response = upstream.getresponse()
            self.send_response(response.status, response.reason)
            for key, value in response.getheaders():
                if key.lower() not in HOP_BY_HOP_HEADERS and key.lower() != "content-length":
                    self.send_header(key, value)
            self.send_header("Transfer-Encoding", "chunked")
            self.end_headers()

            while True:
                chunk = response.read1(8192)
                if not chunk:
                    break
                self.wfile.write(f"{len(chunk):X}\r\n".encode())
                self.wfile.write(chunk)
                self.wfile.write(b"\r\n")
                self.wfile.flush()
            self.wfile.write(b"0\r\n\r\n")
            self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            logging.info("client disconnected from %s", self.path)
        except Exception as exc:
            logging.exception("proxy failure for %s: %s", self.path, exc)
            if not self.wfile.closed:
                self.close_connection = True
        finally:
            upstream.close()

    def log_message(self, fmt, *args):
        logging.info("%s - %s", self.address_string(), fmt % args)


def parse_args():
    parser = argparse.ArgumentParser(
        description="Adapt Codex Responses tool-image outputs for llama.cpp"
    )
    parser.add_argument("--listen", default="127.0.0.1:8090")
    parser.add_argument("--upstream", default="http://127.0.0.1:8085")
    return parser.parse_args()


def main():
    args = parse_args()
    listen_host, listen_port = args.listen.rsplit(":", 1)
    upstream = urlsplit(args.upstream)
    if upstream.scheme != "http" or not upstream.hostname:
        raise SystemExit("--upstream must be an http:// URL")

    ProxyHandler.upstream_host = upstream.hostname
    ProxyHandler.upstream_port = upstream.port or 80
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    server = ThreadingHTTPServer((listen_host, int(listen_port)), ProxyHandler)
    logging.info(
        "listening on http://%s:%s -> %s",
        listen_host,
        listen_port,
        args.upstream,
    )
    server.serve_forever()


if __name__ == "__main__":
    main()
