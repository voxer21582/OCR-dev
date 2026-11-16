# Confronto delle licenze dichiarate nei metadati delle wheel

Sul payload offline del commit `a206ccd` sono stati letti tutti i campi `License-File` nei metadati dei 22 pacchetti. Ogni percorso dichiarato è stato risolto entro la rispettiva cartella dist-info e confrontato integralmente, con spazi e maiuscole normalizzati, con gli avvisi generati; codifiche UTF-8 e CP1252. Sono state verificate 79 dichiarazioni. Questa verifica include file con nomi non riconoscibili come licenze, ad esempio le licenze di dipendenze PDFium.

| Pacchetto | Percorso rispetto a site-packages | SHA-256 del file installato |
|---|---|---|
| certifi | `certifi-2026.10.23.dist-info/licenses/LICENSE` | `e93716da6b9c0d5a4a1df60fe695b370f0695603d21f6f83f053e42cfc10caf7` |
| charset-normalizer | `charset_normalizer-3.5.2.dist-info/licenses/LICENSE` | `18577485d3704f1a479ded8e573c0976cfed315fd2fd17983fa988da4c2f70d1` |
| colorama | `colorama-0.4.6.dist-info/licenses/LICENSE.txt` | `cac35c02686e5d04a5a7140bfb3b36e73aed496656e891102e428886d7930318` |
| colorlog | `colorlog-6.12.0.dist-info/licenses/LICENSE` | `b1d9082bc483623fd59fc7279b457f0e40d942a76426cde257239e04dfe4125a` |
| idna | `idna-3.20.dist-info/licenses/LICENSE.md` | `1a9a4f0e3d479a27240ddd59a9137a66ab4a0f9dfdc8ca6188cc0bfd85187f04` |
| numpy | `numpy-2.5.4.dist-info/licenses/LICENSE.txt` | `a804dff0ead9fadc5293456410bcbfc32bf024be9c4513459663fb7b442d2341` |
| numpy | `numpy-2.5.4.dist-info/licenses/numpy/_core/include/numpy/libdivide/LICENSE.txt` | `d544761558b510866c21f7e8a2d5716fca76e0b98117e3b6b86314db7244d150` |
| numpy | `numpy-2.5.4.dist-info/licenses/numpy/_core/src/common/pythoncapi-compat/COPYING` | `aea41976c720f91bd19725c16916a1ace40eb1ea42620d340e587a5de4bbcea0` |
| numpy | `numpy-2.5.4.dist-info/licenses/numpy/_core/src/highway/LICENSE` | `d208152e2777ffd0126eacc1bd21c0320d69e4e6b622d21a2a12a47e8ef73763` |
| numpy | `numpy-2.5.4.dist-info/licenses/numpy/_core/src/multiarray/dragon4_LICENSE.txt` | `b0fd592d4ead563148e3977e7b589169d46a5ef2ff133c755a81af880a3fc919` |
| numpy | `numpy-2.5.4.dist-info/licenses/numpy/_core/src/npysort/x86-simd-sort/LICENSE.md` | `a732977853530066790c42817087f4829b518dd98d340c916acbfd227e39d3cb` |
| numpy | `numpy-2.5.4.dist-info/licenses/numpy/_core/src/umath/svml/LICENSE` | `585483905b13d4b42f800c55ba99e89d6e2e33ccd5f503e201c07531d148ff41` |
| numpy | `numpy-2.5.4.dist-info/licenses/numpy/fft/pocketfft/LICENSE.md` | `8db000e158c162e7249787852d8c69764706502ccee725c06641b31c1e95c8af` |
| numpy | `numpy-2.5.4.dist-info/licenses/numpy/linalg/lapack_lite/LICENSE.txt` | `19060ef465e1797d682ee0fc3081bd25ab1395e995e43d25c9d13c95d9a3cd6b` |
| numpy | `numpy-2.5.4.dist-info/licenses/numpy/ma/LICENSE` | `d78dbb208b80d92b4d333e41a4baae50d12444f46e53199fa7726a91de6e2da7` |
| numpy | `numpy-2.5.4.dist-info/licenses/numpy/random/LICENSE.md` | `b4bc2f4fa1c95778f1ed3dd8f14706bece399475b978f9f34b5d3cd72521b48a` |
| numpy | `numpy-2.5.4.dist-info/licenses/numpy/random/src/distributions/LICENSE.md` | `cf5619f25b112d5ce7c896efffc8e610bcb345dfadcc19f2c1460aa48fff2c9e` |
| numpy | `numpy-2.5.4.dist-info/licenses/numpy/random/src/mt19937/LICENSE.md` | `92c10699884321f1c2947fe2a70ab23b0fbf1507f756d89dd08f38c61fc3d4fa` |
| numpy | `numpy-2.5.4.dist-info/licenses/numpy/random/src/pcg64/LICENSE.md` | `41190663b77bee5302386495a07b7eabfbfa571aa0ae2f11da6764162062fc4f` |
| numpy | `numpy-2.5.4.dist-info/licenses/numpy/random/src/philox/LICENSE.md` | `322ac46d870c8aeead6c53adcccc839296fb3c8e456eae155081297daf7f8013` |
| numpy | `numpy-2.5.4.dist-info/licenses/numpy/random/src/sfc64/LICENSE.md` | `28cad82ce1379dc529df30da78ec012d7d0d1d576b03ddcb93388aee53659f59` |
| numpy | `numpy-2.5.4.dist-info/licenses/numpy/random/src/splitmix64/LICENSE.md` | `454ec7350e478e037061850b67395753b425b1cb0a34bbc26290b020bf89d763` |
| omegaconf | `omegaconf-2.4.0.dist-info/licenses/LICENSE` | `b31375ed5d5cbe7ec2d0c4c14df8afa7a8e5501bbe25f70b6cbc461685f4b91a` |
| omegaconf | `omegaconf-2.4.0.dist-info/licenses/ATTRIBUTION/LICENSE-antlr4` | `3db1fb3ee79a4b4f9918fc4d0f6133bf18a3cf787f126cd22f8aa9b862281c0c` |
| opencv-python-headless | `opencv_python_headless-5.0.0.93.dist-info/LICENSE-3RD-PARTY.txt` | `c1d60169b55cee56452b227c2fd2a7b9ddda3dd3741065f1c6201072be73fadb` |
| opencv-python-headless | `opencv_python_headless-5.0.0.93.dist-info/LICENSE.txt` | `edef0fac1eb08d29d34563f724742e078da2513e196133a12c6ad9ff01e26107` |
| packaging | `packaging-26.3.dist-info/licenses/LICENSE` | `cad1ef5bd340d73e074ba614d26f7deaca5c7940c3d8c34852e65c4909686c48` |
| packaging | `packaging-26.3.dist-info/licenses/LICENSE.APACHE` | `0d542e0c8804e39aa7f37eb00da5a762149dc682d7829451287e11b938e94594` |
| packaging | `packaging-26.3.dist-info/licenses/LICENSE.BSD` | `b70e7e9b742f1cc6f948b34c16aa39ffece94196364bc88ff0d2180f0028fac5` |
| pillow | `pillow-13.0.0.dist-info/licenses/LICENSE` | `988ffe8ab3480b0f4e9a0ab2702bffd73d9fb6b47198043fb3ba101a62fac236` |
| pyclipper | `pyclipper-1.4.0.dist-info/licenses/LICENSE` | `73c25539e7fb486b834c33747d579e0bc56c0f984294c88f3cb2329420ba300f` |
| pypdfium2 | `pypdfium2-5.15.2.dist-info/licenses/LICENSES/Apache-2.0.txt` | `3ddf9be5c28fe27dad143a5dc76eea25222ad1dd68934a047064e56ed2fa40c5` |
| pypdfium2 | `pypdfium2-5.15.2.dist-info/licenses/LICENSES/BSD-3-Clause.txt` | `ad9a9e823df025f42389c1812eae28019f657d1ed7b3a4ebfd5010b0736a0da4` |
| pypdfium2 | `pypdfium2-5.15.2.dist-info/licenses/LICENSES/CC-BY-4.0.txt` | `f1b1748301cd4274f46733c218d510929661b4990855de5fc645dacd69c4371c` |
| pypdfium2 | `pypdfium2-5.15.2.dist-info/licenses/BUILD_LICENSES/SHARED/Apache-2.0.txt` | `e8de1a7393457e9c88768b78e6ba790622fbefb040ce48194c2cb0f1b6d4e9ff` |
| pypdfium2 | `pypdfium2-5.15.2.dist-info/licenses/BUILD_LICENSES/abseil.txt` | `2b6958687fd4b5127aaa0398910ea51a33ec501e99b1043884ae2422b48f5120` |
| pypdfium2 | `pypdfium2-5.15.2.dist-info/licenses/BUILD_LICENSES/agg23.txt` | `000aa4a787d3f3e5e02ebb02e55560bb1f04fa383a4ea262eed60c7e2bcc1d11` |
| pypdfium2 | `pypdfium2-5.15.2.dist-info/licenses/BUILD_LICENSES/all_except_musl/llvm-libc.txt` | `6016472d2a5cada75c572758af89b2d0acbb8ca50f54471ede2304e2150e9911` |
| pypdfium2 | `pypdfium2-5.15.2.dist-info/licenses/BUILD_LICENSES/android/catapult.txt` | `eb09f5a3f8ad0e302f5a9212f77b2360bce8b56ad7539294fd38ad16d6ff4101` |
| pypdfium2 | `pypdfium2-5.15.2.dist-info/licenses/BUILD_LICENSES/android/cpu_features.txt` | `7d14bd360e234545369b9cf0df2043642dfacf22f29913e54d3c1c53aee259d8` |
| pypdfium2 | `pypdfium2-5.15.2.dist-info/licenses/BUILD_LICENSES/android/libunwind.txt` | `6f26e5314b2437de6860ef81700271ee4d58acc560ef940206f5b65bc20a216b` |
| pypdfium2 | `pypdfium2-5.15.2.dist-info/licenses/BUILD_LICENSES/cibw_musl/libgcc_and_libstdc++.txt` | `46a0436acebcd76e074f6a4a518ece8262ec1e23a4f986ccc97f07ebe727955b` |
| pypdfium2 | `pypdfium2-5.15.2.dist-info/licenses/BUILD_LICENSES/dragonbox-Apache2-LLVM.txt` | `2be7ca5745e68fd3534f124b44970fbb5d506053f0a2e81fb490d6e0d360e62f` |
| pypdfium2 | `pypdfium2-5.15.2.dist-info/licenses/BUILD_LICENSES/dragonbox-Boost.txt` | `beb8e42e9d6b4284e03304d05a81a0755200a965fc8d0a5e0aea1e84cf805d6e` |
| pypdfium2 | `pypdfium2-5.15.2.dist-info/licenses/BUILD_LICENSES/fast_float.txt` | `bf1b57355feca8fce77ee95f48002f8d4789fb71b30ec7599c06cda4901fbb2b` |
| pypdfium2 | `pypdfium2-5.15.2.dist-info/licenses/BUILD_LICENSES/freetype.txt` | `93db264e083fa85b7494b3dd47a214a4043b37170d7079cd4b16eb05842f5eac` |
| pypdfium2 | `pypdfium2-5.15.2.dist-info/licenses/BUILD_LICENSES/harfbuzz.txt` | `bd836c0ddca8ea0bab54a03cd32b6ff7256cbb3840fca2edc1249a4ed92c5b02` |
| pypdfium2 | `pypdfium2-5.15.2.dist-info/licenses/BUILD_LICENSES/highway.txt` | `a4e3fb11044d78e2a9464e6dd9357834fe35a6ded21157f73a8c370207629630` |
| pypdfium2 | `pypdfium2-5.15.2.dist-info/licenses/BUILD_LICENSES/icu.txt` | `fcd7d69d457ebec8024269777c5d9cf3afc554592484d3dc7d9e619872f89c9c` |
| pypdfium2 | `pypdfium2-5.15.2.dist-info/licenses/BUILD_LICENSES/lcms.txt` | `295009507fa4dae3cf8e30b4487a5b16d69714a8e4176eef6c42a9143f490751` |
| pypdfium2 | `pypdfium2-5.15.2.dist-info/licenses/BUILD_LICENSES/libjpeg_turbo.ijg` | `db16a04128171879c60708d171b88d97345a2dd20f9bfc173680a4497c73f704` |
| pypdfium2 | `pypdfium2-5.15.2.dist-info/licenses/BUILD_LICENSES/libjpeg_turbo.md` | `be2b2b5ab168bce87bc3e31f2a5c5adba4b7f6e9e51d618e958d1d46972ebd95` |
| pypdfium2 | `pypdfium2-5.15.2.dist-info/licenses/BUILD_LICENSES/libopenjpeg.txt` | `f24f5b3d732a99ae41f2307626289ceffdf4f8a28e4d0cd4c07d58d7a8005d4a` |
| pypdfium2 | `pypdfium2-5.15.2.dist-info/licenses/BUILD_LICENSES/libpng.txt` | `0ad3bfee8be10e5519949e7af492e36bc349376b75fbeb412229a5967e3e9434` |
| pypdfium2 | `pypdfium2-5.15.2.dist-info/licenses/BUILD_LICENSES/libtiff.txt` | `8eeab3915f97f6f7b62a8008bf77e7ac3bfbb034b04d93cd63aafa10b2dd6614` |
| pypdfium2 | `pypdfium2-5.15.2.dist-info/licenses/BUILD_LICENSES/pbin_and_sbuild/brotli.txt` | `60ae0f13e76cc2eaaa108677eefa4ce16b647f6bbe8cf0a1ac9429d82eca7248` |
| pypdfium2 | `pypdfium2-5.15.2.dist-info/licenses/BUILD_LICENSES/pbin_and_sbuild/libyuv.txt` | `91b2be0a4696a7f98e38ec95d53fb3c1e8a476ce7246f54390276f94d9508ec2` |
| pypdfium2 | `pypdfium2-5.15.2.dist-info/licenses/BUILD_LICENSES/pbin_musl/musl.txt` | `78b7299d4ca6d7cb8927e957b83e4bc85fd3a86f2c2c97f8b802a34ac512d775` |
| pypdfium2 | `pypdfium2-5.15.2.dist-info/licenses/BUILD_LICENSES/pdfium-binaries.txt` | `ae10144a9b76a631144bb743737e63ef4c9521572affbad4f26cb5cb98b03ff7` |
| pypdfium2 | `pypdfium2-5.15.2.dist-info/licenses/BUILD_LICENSES/pdfium.txt` | `d8a7290709944ec857b508f663d983cc051464e48cec11040240bcc14c566765` |
| pypdfium2 | `pypdfium2-5.15.2.dist-info/licenses/BUILD_LICENSES/simdutf.txt` | `c172a0ba936ff31230febb5dad869e25cb7c1a07480c7a381be8cf011bb52719` |
| pypdfium2 | `pypdfium2-5.15.2.dist-info/licenses/BUILD_LICENSES/v8_xfa/bigint.txt` | `e6c59961fac76abbcdfba5868e85f7fe7eb4f710de816bae63302e4315951121` |
| pypdfium2 | `pypdfium2-5.15.2.dist-info/licenses/BUILD_LICENSES/v8_xfa/fdlibm.txt` | `9117ecd79d00160524d0c923aa41c10cd3cab3753bc985e3069eaa9f1481cc17` |
| pypdfium2 | `pypdfium2-5.15.2.dist-info/licenses/BUILD_LICENSES/v8_xfa/fp16.txt` | `379a933d79d62910b33cc9f17f63a3430c16a8ee216a82e824e9e0169c0e1702` |
| pypdfium2 | `pypdfium2-5.15.2.dist-info/licenses/BUILD_LICENSES/v8_xfa/inspector_protocol.txt` | `947e007730399c016f392ecbfcfa9e2c1bfa227924fd2823e74ec1e10964e47d` |
| pypdfium2 | `pypdfium2-5.15.2.dist-info/licenses/BUILD_LICENSES/v8_xfa/strongtalk.txt` | `45d1dff3ad3ed6aec8947f7ce6a4781c535f1d73450b703c594d8bc6285c7736` |
| pypdfium2 | `pypdfium2-5.15.2.dist-info/licenses/BUILD_LICENSES/v8_xfa/v8.txt` | `befd10530f302b2108022be94d74eed4943880fc0626ab762ca7b53521813eeb` |
| pypdfium2 | `pypdfium2-5.15.2.dist-info/licenses/BUILD_LICENSES/zlib.txt` | `254398acc7ecebe67b2cab0582f82dac00557b959f75cdff19c00885758fc141` |
| PyYAML | `pyyaml-6.0.3.dist-info/licenses/LICENSE` | `8d3928f9dc4490fd635707cb88eb26bd764102a7282954307d3e5167a577e8a4` |
| rapidocr | `rapidocr-3.10.0.dist-info/licenses/LICENSE` | `3e0af25fdd06aa9586ae97adb00ea927ebe5a3805ac77d2d3a81ce5f55693333` |
| rapidocr | `rapidocr-3.10.0.dist-info/licenses/MODEL_LICENSES.md` | `c5fd0e8603d3df743355b546121e6fe0f4ef8ff455c5a85c1681fd3ae520e153` |
| requests | `requests-2.34.2.dist-info/licenses/LICENSE` | `09e8a9bcec8067104652c168685ab0931e7868f9c8284b66f5ae6edae5f1130b` |
| requests | `requests-2.34.2.dist-info/licenses/NOTICE` | `f5110972dedad2b4e9d314518daf3b7d72d6e02e499acd802181de6f74571dcc` |
| shapely | `shapely-2.2.0.dist-info/licenses/LICENSE.txt` | `e8cd7d34604d2758ff589f0f34d6ed79c3f7fb14aaf5e12fb09221421391a3bf` |
| shapely | `shapely-2.2.0.dist-info/licenses/LICENSE_GEOS` | `7233baa9a7d4a17257b357706b7dbdc4b675e5ca45425b3418673b16990cf239` |
| shapely | `shapely-2.2.0.dist-info/licenses/LICENSE_win32` | `fdbb2abb8c598c8888755b52340bddcee38668a2def23e51e7d9e3f187bb8d51` |
| six | `six-1.17.0.dist-info/LICENSE` | `4375ba20e2b9c6c4e7cad2940a628fd90e95cc3d50ee92aae755715d8ba1fbd0` |
| tqdm | `tqdm-4.70.1.dist-info/licenses/LICENCE` | `fcff87c3a47ce8028a8512aa182d4fcf0ad1c90544ee75cf9b343684cac194de` |
| urllib3 | `urllib3-2.8.0.dist-info/licenses/LICENSE.txt` | `130e3a64d5fdd5d096a752694634a7d9df284469de86e5732100268041e3d686` |

Limiti: i metadati non dimostrano che ogni componente incorporato sia dichiarato correttamente; non sostituiscono l’esame delle dipendenze effettive né un parere legale. ONNX Runtime e flatbuffers non dichiarano file con questo campo: i rispettivi testi e avvisi sono trattati separatamente.

Nel testo di licenza distribuito con Pillow 13.0.0 compaiono sezioni versionate per brotli 1.2.0, freetype 2.14.3, harfbuzz 14.5.0, lcms2 2.19.1, libavif 1.4.2, libjpeg-turbo 3.2.0, libpng 1.6.58, libwebp 1.6.0, openjpeg 2.5.4, tiff 4.7.2, xz 5.8.4 e zlib-ng 2.3.3. L’intero testo è incluso negli avvisi; la presenza delle sezioni non prova da sola quali componenti siano effettivamente collegati nei binari della wheel, né completa il loro censimento nella distinta.

Prova locale con `python.exe -B -c "from PIL import features; features.pilinfo()"` del payload a206ccd: Pillow 13.0.0 ha dichiarato FreeType 2.14.3, WebP 1.6.0, AVIF 1.4.2, libjpeg-turbo 3.2.0, OpenJPEG 2.5.4, zlib-ng 2.3.3 e libtiff 4.7.2; tutti corrispondono alle versioni indicate nel file LICENSE della wheel. La distinta aggiunge queste sette librerie solo per la wheel il cui SHA-256 è `9dda0788a9932776a75d8bcc020076edc308ce2508b51f6739a45e3158b3fc42`, rifiutando un pin Pillow diverso finché l’inventario non sia rivisto. Pillow dichiara anche LittleCMS caricato come 2.19, mentre il testo licenza riporta 2.19.1: non si attribuisce automaticamente la versione completa. HarfBuzz, Brotli, libpng e XZ menzionati nel testo non sono stati confermati indipendentemente dalla prova di funzionalità.
