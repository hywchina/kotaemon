(() => {
    const workerCode = `
        class PCMRecorder extends AudioWorkletProcessor {
            constructor() {
                super();
                this.frame = new Int16Array(4800);
                this.used = 0;
                this.done = false;
                this.port.onmessage = () => {
                    this.done = true;
                    this.send();
                    this.port.postMessage(null);
                };
            }
            send() {
                if (!this.used) return;
                const bytes = new ArrayBuffer(this.used * 2);
                const view = new DataView(bytes);
                for (let i = 0; i < this.used; i++) {
                    view.setInt16(i * 2, this.frame[i], true);
                }
                this.port.postMessage(bytes, [bytes]);
                this.used = 0;
            }
            process(inputs) {
                if (this.done) return false;
                const samples = inputs[0]?.[0];
                if (!samples) return true;
                for (const sample of samples) {
                    this.frame[this.used++] = Math.max(-32768, Math.min(32767, sample * 32768));
                    if (this.used === this.frame.length) this.send();
                }
                return true;
            }
        }
        registerProcessor("kota-speech-pcm", PCMRecorder);
    `;

    let session = null;
    let saveTimer = null;
    const el = (id) => document.getElementById(id);
    const mic = () => el("speech-microphone")?.querySelector("button");
    const bridge = (id) => {
        const element = el(id);
        const button = element?.matches("button") ? element : element?.querySelector("button");
        button?.click();
    };

    function show(message, text = "", save = false) {
        el("speech-preview").hidden = false;
        el("speech-status").textContent = message;
        el("speech-text").textContent = text;
        el("speech-save").hidden = !save;
        el("speech-save").disabled = false;
    }

    function setMic(recording, disabled = false) {
        const button = mic();
        if (!button) return;
        const label = recording ? "停止录音" : "开始录音";
        button.setAttribute("aria-label", label);
        button.setAttribute("aria-pressed", String(recording));
        button.title = label;
        button.disabled = disabled;
    }

    function releaseAudio(current) {
        current.media?.getTracks().forEach((track) => track.stop());
        if (current.context.state !== "closed") current.context.close().catch(() => {});
    }

    function end(current) {
        if (session !== current) return;
        session = null;
        clearTimeout(current.timer);
        releaseAudio(current);
        current.socket?.close();
        setMic(false);
    }

    function fail(current, message) {
        if (session !== current) return;
        end(current);
        show(message);
    }

    async function start() {
        if (!navigator.mediaDevices?.getUserMedia || !window.AudioWorkletNode) {
            show("麦克风需要 HTTPS 或本机地址，请检查浏览器权限。");
            return;
        }
        let context;
        try {
            context = new AudioContext({sampleRate: 16000});
            if (context.sampleRate !== 16000) {
                context.close();
                show("浏览器无法以 16 kHz 录音。");
                return;
            }
        } catch {
            show("浏览器无法启动麦克风。");
            return;
        }
        const current = {context};
        session = current;
        setMic(false, true);
        show("正在请求麦克风权限…");
        try {
            const mediaRequest = navigator.mediaDevices.getUserMedia({
                audio: {
                    channelCount: 1,
                    echoCancellation: false,
                    noiseSuppression: false,
                    autoGainControl: false,
                },
            });
            const resume = context.resume().then(() => true, () => false);
            current.media = await mediaRequest;
            if (session !== current) {
                releaseAudio(current);
                return;
            }
            if (!await resume) throw new Error("Audio context unavailable");
            show("正在连接语音识别服务…");
            current.timer = setTimeout(() => fail(current, "语音服务连接超时，请重试。"), 12000);
            bridge("speech-start-bridge");
        } catch {
            fail(current, "无法使用麦克风，请检查设备和浏览器权限。");
        }
    }

    async function record(current) {
        const module = URL.createObjectURL(new Blob([workerCode], {type: "text/javascript"}));
        try {
            await current.context.audioWorklet.addModule(module);
        } finally {
            URL.revokeObjectURL(module);
        }
        if (session !== current) return;
        current.processor = new AudioWorkletNode(current.context, "kota-speech-pcm");
        current.processor.port.onmessage = ({data}) => {
            if (session !== current) return;
            if (current.socket.readyState !== WebSocket.OPEN || current.socket.bufferedAmount > 160000) {
                fail(current, "语音连接中断，请重新录音。");
            } else if (data === null) {
                current.socket.send("stop");
            } else {
                current.socket.send(data);
            }
        };
        current.context.createMediaStreamSource(current.media).connect(current.processor);
        const mute = current.context.createGain();
        mute.gain.value = 0;
        current.processor.connect(mute).connect(current.context.destination);
        clearTimeout(current.timer);
        current.timer = setTimeout(stop, 299000);
        show("录音中…");
        setMic(true);
    }

    function stop() {
        const current = session;
        if (!current?.processor || current.stopping) return;
        current.stopping = true;
        current.processor.port.postMessage("flush");
        current.media.getTracks().forEach((track) => track.stop());
        setMic(false, true);
        show("正在整理说话人和最终转写…", el("speech-text").textContent);
        clearTimeout(current.timer);
        current.timer = setTimeout(() => fail(current, "最终转写超时，请重新录音。"), 95000);
    }

    window.kotaSpeech = {
        open(token) {
            const current = session;
            if (!current || current.socket || !token) return;
            const base = location.pathname.replace(/\/?$/, "/");
            const protocol = location.protocol === "https:" ? "wss:" : "ws:";
            const socket = new WebSocket(protocol + "//" + location.host + base + "asr/live");
            current.socket = socket;
            socket.onopen = () => socket.send(token);
            socket.onmessage = ({data}) => {
                if (session !== current) return;
                const message = JSON.parse(data);
                if (message.type === "ready") {
                    record(current).catch(() => fail(current, "无法开始录音，请检查浏览器设置。"));
                } else if (message.type === "partial" && !current.stopping) {
                    show("录音中…", message.text);
                } else if (message.type === "final") {
                    end(current);
                    show(message.text ? "转写已完成" : "未识别到语音", message.text, Boolean(message.text));
                }
            };
            socket.onclose = () => fail(current, "语音服务不可用或连接中断，请重试。");
        },
        saved() {
            clearTimeout(saveTimer);
            show("已保存到会话");
        },
        reset() {
            clearTimeout(saveTimer);
            if (session) end(session);
            if (el("speech-preview")) el("speech-preview").hidden = true;
        },
    };

    document.addEventListener("click", (event) => {
        const button = event.target.closest("button");
        if (button && button === mic()) {
            if (session) stop();
            else start();
        } else if (button && button === el("speech-save")) {
            button.disabled = true;
            clearTimeout(saveTimer);
            saveTimer = setTimeout(() => { button.disabled = false; }, 8000);
            bridge("speech-save-bridge");
        }
    });
    window.addEventListener("pagehide", () => window.kotaSpeech.reset());
})();
