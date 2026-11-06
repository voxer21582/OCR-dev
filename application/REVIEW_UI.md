# Source-bound review surface

`review_ui.py` renders validated document records as a read-only WSGI projection. It can preview original PDF or raster bytes only after matching source length, SHA-256, media type, and signature. HTML is escaped; preview responses are bounded and use no-store, nosniff, and a sandbox content-security policy. The review surface binds to loopback when served locally.

This module does not itself write review changes or persist records. `local_intake_app.py` composes it with intake and explicit archive actions. Archive persistence is a separate encrypted local-store capability; opening this review surface does not auto-save a live session.

The interface keeps candidate values connected to source/page/region evidence and makes uncertainty visible. It does not approve reimbursements, payments, or accounting entries. Operational acceptance, Windows 11 installation/recovery, and real-document safety remain unverified.
