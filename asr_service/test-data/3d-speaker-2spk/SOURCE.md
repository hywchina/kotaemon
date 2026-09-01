# 3D-Speaker two-speaker evaluation sample

- Source project: <https://github.com/modelscope/3D-Speaker>
- Source recipe: `egs/3dspeaker/speaker-diarization/run_audio.sh`
- Audio: <https://modelscope.cn/models/iic/speech_campplus_speaker-diarization_common/resolve/master/examples/2speakers_example.wav>
- Reference RTTM: <https://modelscope.cn/models/iic/speech_campplus_speaker-diarization_common/resolve/master/examples/2speakers_example.rttm>
- Project license: Apache-2.0

SHA-256:

- WAV: `8dd999996bfc3dfbef07d71401dd9043096ffbff576bcccdd8f8ddce33563b14`
- RTTM: `7f44a8809d33535bb687ea6915f6470335d0059f08905ec408a3f3582dd1675a`

The RTTM contains five alternating speech turns from two reference speakers.
This service currently requires clients to submit utterance boundaries, so the
evaluation commits audio at the reference turn boundaries. It evaluates ASR,
speaker embeddings and online speaker clustering, but not automatic speaker
change detection.
