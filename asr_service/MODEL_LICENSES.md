# Model license inventory

The service source code and model weights have separate licenses. The model
cards downloaded on 2026-08-31 declared `Apache License 2.0` for all five
snapshots below. Release approval must still archive the exact model cards,
revision, generated `models/manifest.json`, whole-bundle checksum and applicable
notices; do not infer a weight license from the FunASR toolkit license alone.

| Component | ModelScope model and pinned revision | Model card | Locally declared license |
| --- | --- | --- | --- |
| Streaming ASR | `iic/speech_paraformer-large_asr_nat-zh-cn-16k-common-vocab8404-online@v2.0.4` | [ModelScope](https://www.modelscope.cn/models/iic/speech_paraformer-large_asr_nat-zh-cn-16k-common-vocab8404-online/summary) | Apache License 2.0 |
| Final ASR | `iic/speech_paraformer-large_asr_nat-zh-cn-16k-common-vocab8404-pytorch@v2.0.4` | [ModelScope](https://www.modelscope.cn/models/iic/speech_paraformer-large_asr_nat-zh-cn-16k-common-vocab8404-pytorch/summary) | Apache License 2.0 |
| VAD | `iic/speech_fsmn_vad_zh-cn-16k-common-pytorch@v2.0.4` | [ModelScope](https://www.modelscope.cn/models/iic/speech_fsmn_vad_zh-cn-16k-common-pytorch/summary) | Apache License 2.0 |
| Punctuation | `iic/punc_ct-transformer_zh-cn-common-vocab272727-pytorch@v2.0.4` | [ModelScope](https://www.modelscope.cn/models/iic/punc_ct-transformer_zh-cn-common-vocab272727-pytorch/summary) | Apache License 2.0 |
| Speaker embedding | `iic/speech_campplus_sv_zh-cn_16k-common@v2.0.2` | [ModelScope](https://www.modelscope.cn/models/iic/speech_campplus_sv_zh-cn_16k-common/summary) | Apache License 2.0 |

Toolkit sources:

- [FunASR](https://github.com/modelscope/FunASR)
- [3D-Speaker](https://github.com/modelscope/3D-Speaker)

The inventory records upstream declarations for traceability; it is not legal
advice. Hospital deployment approval must cover code, every weight snapshot,
training-data implications and biometric-data processing.
