# OCR2 Document Intelligence architecture

This directory contains the application component of OCR2. Repository-level taxonomy contracts, roadmap tracking, required CI, and project governance remain at the repository root and in the OCR2 GitHub Project.

## Processing boundaries

The application separates source intake and bounded decoding, OCR observation, semantic proposals, document validation, human review, and export. Extracted values retain source/page/region evidence and uncertainty. OCR remains disabled by default; a caller must explicitly provide a local processor. No reimbursement, payment, or accounting approval is automatic.

## Optional OCR engine adapters

The engine-neutral OCR contract is implemented by adapters that receive a preconfigured local engine. The optional RapidOCR adapter is an integration boundary only: importing it does not import RapidOCR or construct an engine, acquire models, or enable OCR. A production configuration must explicitly supply an accepted package/model tuple and remain OCR-off otherwise. The adapter accepts Italian/English contract requests only and requires a compatible configured model route; for PP-OCRv6 this is the documented `multi` route, not an assumed `latin` route. Model acquisition, hashes, licenses, and Windows runtime acceptance remain separate gates.

## Local state and archive

The intake supports an in-memory session. A separate local encrypted archive implementation and explicit save/open/delete UI are present in this migration snapshot. The archive code uses the Windows data-protection interface and supports injected protectors for synthetic tests. This code has not been accepted as a supported Windows 11 installation or recovery process; backup, operational recovery, and user acceptance remain open.

## Application surfaces

- [Ingestion](INGESTION.md) defines accepted file input and bounded processing.
- [Data schema](DATA_SCHEMA.md) records versioned evidence-bearing records.
- [Processing pipeline](PROCESSING_PIPELINE.md) separates OCR observation from interpretation and validation.
- [Review UI](REVIEW_UI.md) documents source-bound human review.
- [Export formats](docs/document-export-formats.md) documents explicit user-requested exports.
- [Annotation guide](ANNOTATION_GUIDE.md) describes synthetic benchmark annotation conventions.

## Verification and unresolved gates

The repository-root required GitHub Actions check runs only the taxonomy registry and binding contract tests. Application tests are present in this subdirectory but are not covered by that required check. The public migration does not activate model evaluation or native Windows workflows. Runtime dependency/license closure, Windows 11 installation and recovery acceptance, fiscal-rule approval, real-document safeguards, and overall product acceptance remain unverified.
