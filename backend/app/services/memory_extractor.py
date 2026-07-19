import re


class MemoryExtractor:

    PATTERNS = [

        r"my name is (.+)",

        r"i am (.+)",

        r"i'm (.+)",

        r"i like (.+)",

        r"i prefer (.+)",

        r"remember that (.+)",

        r"i work on (.+)",

        r"i am working on (.+)",

    ]

    @classmethod
    def extract(
        cls,
        text: str,
    ):

        lowered = text.lower()

        for pattern in cls.PATTERNS:

            match = re.search(
                pattern,
                lowered,
            )

            if match:

                return text

        return None