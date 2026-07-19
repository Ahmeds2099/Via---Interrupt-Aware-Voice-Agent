export class PCMEncoder {

    static readonly TARGET_SAMPLE_RATE = 16000;

    /**
     * Downsample Float32 audio using linear interpolation.
     */
    static downsample(
        input: Float32Array,
        inputRate: number,
        outputRate: number = PCMEncoder.TARGET_SAMPLE_RATE,
    ): Float32Array {

        if (inputRate === outputRate) {
            return input;
        }

        const ratio = inputRate / outputRate;

        const outputLength = Math.floor(
            input.length / ratio,
        );

        const output = new Float32Array(outputLength);

        for (let i = 0; i < outputLength; i++) {

            const position = i * ratio;

            const left = Math.floor(position);

            const right = Math.min(
                left + 1,
                input.length - 1,
            );

            const weight = position - left;

            output[i] =
                input[left] * (1 - weight) +
                input[right] * weight;

        }

        return output;

    }

    static float32ToInt16(
        input: Float32Array,
    ): ArrayBuffer {

        const output = new Int16Array(
            input.length,
        );

        for (let i = 0; i < input.length; i++) {

            const s = Math.max(
                -1,
                Math.min(1, input[i]),
            );

            output[i] =
                s < 0
                    ? s * 0x8000
                    : s * 0x7FFF;

        }

        return output.buffer;

    }

    static encode(
        input: Float32Array,
        inputRate: number,
    ): ArrayBuffer {

        const resampled =
            this.downsample(
                input,
                inputRate,
            );

        return this.float32ToInt16(
            resampled,
        );

    }

}