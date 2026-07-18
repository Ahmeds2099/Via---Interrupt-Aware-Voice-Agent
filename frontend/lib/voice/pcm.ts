export class PCMEncoder {
    /**
     * Convert Float32 PCM samples (-1.0 to 1.0)
     * into signed 16-bit PCM.
     */
    static float32ToInt16(input: Float32Array): ArrayBuffer {
        const output = new Int16Array(input.length);

        for (let i = 0; i < input.length; i++) {
            const sample = Math.max(-1, Math.min(1, input[i]));
            output[i] =
                sample < 0
                    ? sample * 0x8000
                    : sample * 0x7fff;
        }

        return output.buffer;
    }
}