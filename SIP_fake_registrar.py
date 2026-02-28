#!/usr/bin/env python3
import socket
import re
import time

LISTEN_IP = "0.0.0.0"
LISTEN_PORT = 5060

# Very small in-memory "location store" (not required for just satisfying Linphone).
locations = {}  # key: aor (To URI), value: (contact, expires, last_seen, src)

def _get_header(msg: str, name: str) -> str | None:
	# Case-insensitive single header fetch (first match)
	m = re.search(rf"(?im)^{re.escape(name)}\s*:\s*(.+?)\r?$", msg)
	return m.group(1).strip() if m else None

def _get_start_line(msg: str) -> str:
	return msg.splitlines()[0].strip()

def _parse_request_method(msg: str) -> str:
	start = _get_start_line(msg)
	parts = start.split()
	return parts[0].upper() if parts else ""

def _parse_expires(msg: str) -> int:
	# Prefer Contact: ...;expires=NNN if present, else Expires: NNN, else 3600
	contact = _get_header(msg, "Contact")
	if contact:
		m = re.search(r"(?i);\s*expires\s*=\s*(\d+)", contact)
		if m:
			return int(m.group(1))
	exp = _get_header(msg, "Expires")
	if exp:
		m = re.search(r"(\d+)", exp)
		if m:
			return int(m.group(1))
	return 3600

def _build_200_ok_register(req: str, src_ip: str, src_port: int) -> bytes:
	via = _get_header(req, "Via")
	to = _get_header(req, "To")
	from_ = _get_header(req, "From")
	call_id = _get_header(req, "Call-ID")
	cseq = _get_header(req, "CSeq")
	contact = _get_header(req, "Contact")
	expires = _parse_expires(req)

	if to and "tag=" not in to.lower():
		to = f"{to};tag=srvt{int(time.time())}"

	if via and re.search(r"(?i)\brport\b(?!\s*=)", via):
		if "received=" not in via.lower():
			via = f"{via};received={src_ip};rport={src_port}"
		else:
			via = f"{via};rport={src_port}"

	# Optional store
	if contact and to:
		locations[to] = (contact, expires, time.time(), f"{src_ip}:{src_port}")

	resp = (
		"SIP/2.0 200 OK\r\n"
		f"Via: {via}\r\n"
		f"To: {to}\r\n"
		f"From: {from_}\r\n"
		f"Call-ID: {call_id}\r\n"
		f"CSeq: {cseq}\r\n"
		f"Contact: {contact}\r\n"
		f"Expires: {expires}\r\n"
		"Content-Length: 0\r\n"
		"\r\n"
	)
	return resp.encode("utf-8", errors="ignore")


def _build_200_ok_generic(req: str, src_ip: str, src_port: int) -> bytes:
	via = _get_header(req, "Via")
	to = _get_header(req, "To")
	from_ = _get_header(req, "From")
	call_id = _get_header(req, "Call-ID")
	cseq = _get_header(req, "CSeq")

	if to and "tag=" not in to.lower():
		to = f"{to};tag=srvt{int(time.time())}"

	if via and re.search(r"(?i)\brport\b(?!\s*=)", via):
		if "received=" not in via.lower():
			via = f"{via};received={src_ip};rport={src_port}"
		else:
			via = f"{via};rport={src_port}"

	resp = (
		"SIP/2.0 200 OK\r\n"
		f"Via: {via}\r\n"
		f"To: {to}\r\n"
		f"From: {from_}\r\n"
		f"Call-ID: {call_id}\r\n"
		f"CSeq: {cseq}\r\n"
		"Content-Length: 0\r\n"
		"\r\n"
	)
	return resp.encode("utf-8", errors="ignore")

def main():
	sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
	sock.bind((LISTEN_IP, LISTEN_PORT))
	print(f"Fake registrar listening on udp://{LISTEN_IP}:{LISTEN_PORT}")

	while True:
		data, (src_ip, src_port) = sock.recvfrom(65535)
		try:
			req = data.decode("utf-8", errors="ignore")
		except Exception:
			continue

		method = _parse_request_method(req)
		start = _get_start_line(req)
		print(f"\n{time.strftime('%H:%M:%S')} <- {src_ip}:{src_port}  {start}")

		if method == "REGISTER":
			resp = _build_200_ok_register(req, src_ip, src_port)
			sock.sendto(resp, (src_ip, src_port))
			print(" -> 200 OK (REGISTER)")
		elif method in ("OPTIONS", "KEEPALIVE"):
			resp = _build_200_ok_generic(req, src_ip, src_port)
			sock.sendto(resp, (src_ip, src_port))
			print(f" -> 200 OK ({method})")
		else:
			# For your purpose you can ignore everything else
			print(f" .. ignored ({method})")

if __name__ == "__main__":
	main()
