"""Clipsay User-Agent constant.

The Agnes GCS-backed image / video URLs reject the default
``aiohttp`` User-Agent with ``<Error><Code>AuthenticationRequired</Code></Error>``.
A consistent, branded User-Agent is required on every outbound call
that touches Agnes (and good practice everywhere else).
"""

_USER_AGENT = "Clipsay/1.0 (+https://github.com/clipsay/clipsay)"
