"""Serve an entirely synthetic M4 review session on loopback."""
from copy import deepcopy
from io import BytesIO
import http.client
import threading

from PIL import Image, ImageDraw
from alfa_document_intelligence.local_intake_app import serve_expense_report_local


def processor(record, source):
    sha = record["source"]["sha256"]
    evidence = {
        "source_sha256": sha, "page_number": 1,
        "region": {"coordinate_space": "normalized_page", "polygon": [[0.08, 0.1], [0.8, 0.1], [0.8, 0.25], [0.08, 0.25]]},
        "literal": "NEGOZIO SINTETICO", "producer": {"stage": "ocr", "name": "synthetic", "version": "1"},
    }
    record["pages"] = [{"page_number": 1, "width_px": 700, "height_px": 420}]
    record["fields"]["merchant_name"] = {
        "value": None, "status": "uncertain", "evidence": [deepcopy(evidence)],
        "alternatives": [
            {"value": "NEGOZIO SINTETICO", "status": "uncertain", "evidence": [deepcopy(evidence)]},
            {"value": "NEGOZIO SIMULATO", "status": "uncertain", "evidence": [deepcopy(evidence)]},
        ],
    }
    record["fields"]["currency"] = {"value": None, "status": "absent", "evidence": [], "alternatives": []}
    return record


def main():
    image = Image.new("RGB", (700, 420), "white")
    draw = ImageDraw.Draw(image)
    draw.text((70, 65), "NEGOZIO SINTETICO", fill="black")
    draw.text((70, 160), "TOTALE 12.34 EUR", fill="black")
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    source = buffer.getvalue()
    server = serve_expense_report_local(port=0, document_processor=processor)
    port = server.server_port
    threading.Thread(target=server.serve_forever, daemon=True).start()
    connection = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
    boundary = "ocr2-synthetic-m4"
    body = (f'--{boundary}\r\nContent-Disposition: form-data; name="files"; filename="synthetic.png"\r\nContent-Type: image/png\r\n\r\n'.encode() + source + f'\r\n--{boundary}--\r\n'.encode())
    origin = f"http://127.0.0.1:{port}"
    connection.request("POST", "/upload", body, {"Content-Type": f"multipart/form-data; boundary={boundary}", "Origin": origin})
    response = connection.getresponse(); response.read()
    if response.status != 200:
        raise RuntimeError(f"synthetic upload failed: {response.status}")
    connection.request("POST", "/assign-note", "note_document_id=doc-001", {"Content-Type": "application/x-www-form-urlencoded", "Origin": origin})
    response = connection.getresponse(); response.read()
    if response.status != 200:
        raise RuntimeError(f"synthetic assignment failed: {response.status}")
    connection.close()
    print(f"SYNTHETIC_REVIEW_URL={origin}/reviews/doc-001", flush=True)
    try:
        threading.Event().wait()
    except KeyboardInterrupt:
        pass
    finally:
        server.shutdown(); server.server_close(); server.ocr2_close()


if __name__ == "__main__":
    main()
