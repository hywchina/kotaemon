# Model license inventory

The service source code and model weights have separate licenses. Before an
offline hospital image is released, record the exact model revision, checksum,
source URL and accepted license in this file.

| Component | Default model | Upstream | License action |
| --- | --- | --- | --- |
| Streaming ASR | `paraformer-zh-streaming` | FunASR / ModelScope | Archive the selected model card and FunASR model license |
| Final ASR | `paraformer-zh` | FunASR / ModelScope | Archive the selected model card and FunASR model license |
| VAD | `fsmn-vad` | FunASR / ModelScope | Verify and archive the model card |
| Punctuation | `ct-punc` | FunASR / ModelScope | Verify and archive the model card |
| Speaker embedding | `cam++` | 3D-Speaker / ModelScope | Archive the Apache-2.0 model card and checksum |

Do not assume the FunASR toolkit MIT license automatically covers every model
weight. Deployment approval must cover both code and each downloaded artifact.
