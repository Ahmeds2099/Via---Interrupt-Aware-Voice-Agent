from io import BytesIO


class AudioBuffer:

    def __init__(self):

        self._buffer = BytesIO()

    def append(
        self,
        chunk: bytes,
    ):

        self._buffer.write(chunk)

    def getvalue(
        self,
    ) -> bytes:

        return self._buffer.getvalue()

    def clear(
        self,
    ):

        self._buffer.seek(0)

        self._buffer.truncate()

    def size(
        self,
    ) -> int:

        return len(
            self._buffer.getvalue()
        )