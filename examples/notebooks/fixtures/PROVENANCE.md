# Capstone fixture provenance

These fixtures were created for Praval's deterministic notebook certification.
They describe fictional products, customers, companies, and release candidates.
No production data, customer records, credentials, or third-party copyrighted
material is included.

- `research_sources.json` is a synthetic market-entry evidence packet. It
  deliberately contains one stale source and one contradiction.
- `support_case.json` is a synthetic enterprise support case. It deliberately
  contains a stale knowledge article and a service-credit request.
- `release_candidate/` is an original, minimal Python package with deliberate
  correctness, security, and documentation defects. Notebooks copy it to a
  temporary directory before inspection or repair.
- `marketing/` is an original fictional product brief, brand guide, research
  packet, channel constraints, campaign signals, and dashboard screenshot.
  `product_screenshot.svg` is the editable source for the deterministic image;
  `product_screenshot.png.base64` is the certification transport form.

`SHA256SUMS` contains SHA-256 hashes relative to this directory. Regenerate it
only when an intentional fixture change has been reviewed.
