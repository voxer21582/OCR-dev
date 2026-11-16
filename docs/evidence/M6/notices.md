# Licenze assenti dai metadati delle wheel

Nel contenuto 0.6.0 le cartelle dist-info di flatbuffers 25.12.19 e onnxruntime 1.31.1 dichiarano rispettivamente Apache 2.0 e MIT, ma non contengono file di licenza. I testi sono stati acquisiti dai tag ufficiali corrispondenti:

- flatbuffers: https://raw.githubusercontent.com/google/flatbuffers/v25.12.19/LICENSE — SHA-256 `cfc7749b96f63bd31c3c42b5c471bf756814053e847c10f3eb003417bc523d30`.
- onnxruntime: https://raw.githubusercontent.com/microsoft/onnxruntime/v1.31.1/LICENSE — SHA-256 `2f07c72751aed99790b8a4869cf2311df85a860b22ded05fa22803587a48922c`.

I testi sono in `installer/licenses/`. Restano da controllare eventuali altri avvisi delle dipendenze integrate e da generare SBOM e avvisi completi: la presenza di questi file da sola non dimostra la conformità della distribuzione.
