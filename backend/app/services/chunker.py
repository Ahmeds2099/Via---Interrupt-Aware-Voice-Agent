# pyrefly: ignore [missing-import]
from langchain_text_splitters import RecursiveCharacterTextSplitter


class TextChunker:

    def __init__(self):

        self.splitter = RecursiveCharacterTextSplitter(
            chunk_size=600,
            chunk_overlap=120,
            separators=[
                "\n\n",
                "\n",
                ". ",
                "! ",
                "? ",
                " ",
                "",
            ],
        )

    def chunk(
        self,
        text: str,
    ) -> list[str]:

        return self.splitter.split_text(text)