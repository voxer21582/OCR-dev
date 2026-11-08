# Optional RapidOCR adapter design

Date: 2026-11-08

## Intent

Add a reversible bridge from RapidOCR's page-level observations to OCR2's engine-neutral `OCRToken` contract. This advances the selected Italian/English OCR direction while keeping OCR disabled unless an integrator explicitly supplies a preconfigured engine.

## Approaches

1. **Injected engine adapter (selected):** accept an already configured callable engine, adapt `boxes`, `txts`, and `scores`, and preserve page/source binding through `run_ocr`. This follows the existing Paddle adapter boundary and adds no runtime dependency or implicit model loading.
2. **Construct RapidOCR inside the adapter:** simpler at call sites, but couples product configuration to one runtime and can implicitly acquire models. Defer until the exact package/model tuple and offline behavior are approved and pinned.
3. **Defer RapidOCR support:** avoids code now, but leaves the user's selected optional integration absent despite an existing engine-neutral contract.

## Scope and acceptance

- Accept only the OCR2 language pair `("it", "en")` for this configured route.
- Normalize RapidOCR quadrilateral coordinates by source page dimensions; let the existing OCR contract reject non-finite or out-of-range geometry and confidence.
- Reject malformed output arrays, non-text values, and malformed point geometry.
- Keep NumPy lazy: it is imported only by the default RGB decoder when the adapter is invoked; tests inject a decoder and use a synthetic engine.
- Do not construct an engine, choose or download a model, install dependencies, enable OCR by default, run OCR on user documents, or claim runtime accuracy/readiness.

For PP-OCRv6, the upstream model matrix documents Italian and English on the multilingual route; the adapter does not assume a `latin` route. The eventual engine configuration must be pinned and proven offline before product activation.

## Evidence

Primary upstream references consulted 2026-11-08:

- [RapidOCR Python usage](https://rapidai.github.io/RapidOCRDocs/main/en/install_usage/rapidocr/usage/)
- [RapidOCR model list](https://rapidai.github.io/RapidOCRDocs/main/en/model_list/)
- [RapidOCR local model configuration](https://rapidai.github.io/RapidOCRDocs/main/en/install_usage/rapidocr/how_to_use_offline_model/)
- [RapidOCR model license and attribution](https://rapidai.github.io/RapidOCRDocs/main/en/model_licenses/)

The local synthetic tests cover normalization, source/page binding, empty output, array alignment, malformed geometry, supported language pairing, and constructor requirements. Passing these tests verifies only the adapter contract; it does not execute RapidOCR.
