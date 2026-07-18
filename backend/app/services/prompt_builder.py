class PromptBuilder:

    @staticmethod
    def build(
    question: str,
    chunks: list[dict],
) -> str:

        sections = []

        for index, chunk in enumerate(chunks, start=1):

            sections.append(
                f"""
==========================
Retrieved Chunk {index}

Document:
{chunk['filename']}

Similarity:
{chunk['score']:.3f}

Content:

{chunk['text']}
"""
            )

        context = "\n".join(sections)

        return f"""
Retrieved Context

{context}

==========================

User Question

{question}
"""