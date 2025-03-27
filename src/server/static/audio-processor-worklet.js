// source: https://github.com/Azure-Samples/aisearch-openai-rag-audio/blob/7f685a8969e3b63e8c3ef345326c21f5ab82b1c3/app/frontend/public/audio-processor-worklet.js
const MIN_INT16 = -0x8000;
const MAX_INT16 = 0x7fff;

class PCMAudioProcessor extends AudioWorkletProcessor {
    constructor() {
        super();
    }

    process(inputs, outputs, parameters) {
        const input = inputs[0];
        if (input.length > 0) {
            const float32Buffer = input[0];

            // Ses normalizasyonu ekliyoruz (ortalama seviyeye çekmek için)
            const normalizedBuffer = this.normalizeAudio(float32Buffer);

            // 16-bit PCM'e çeviriyoruz
            const int16Buffer = this.float32ToInt16(normalizedBuffer);
            this.port.postMessage(int16Buffer);
        }
        return true;
    }

    // Ses normalizasyonu: Maksimum ses seviyesini dengeleyerek kaliteyi artırır
    normalizeAudio(float32Array) {
        let maxVal = 0;
        for (let i = 0; i < float32Array.length; i++) {
            maxVal = Math.max(maxVal, Math.abs(float32Array[i]));
        }
        if (maxVal === 0) return float32Array;

        // Tüm değerleri max değere göre ölçeklendir
        const scale = 1.0 / maxVal;
        return float32Array.map(sample => sample * scale);
    }

    float32ToInt16(float32Array) {
        const int16Array = new Int16Array(float32Array.length);
        for (let i = 0; i < float32Array.length; i++) {
            let val = Math.floor(float32Array[i] * MAX_INT16);
            val = Math.max(MIN_INT16, Math.min(MAX_INT16, val)); // Klipleme önleniyor
            int16Array[i] = val;
        }
        return int16Array;
    }
}

registerProcessor("audio-processor-worklet", PCMAudioProcessor);