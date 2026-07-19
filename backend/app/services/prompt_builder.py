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
========== Retrieved Context {index} ==========

Source:
{chunk['filename']}

Similarity:
{chunk['score']:.3f}

Content:
{chunk['text']}
"""
            )
    
        context = "\n".join(sections)

        return f"""
You are answering a user's question.

Instructions:

- Use the retrieved context only if it is relevant.
- If the retrieved context contains the answer, use it.
- If it does not contain the answer, answer normally using your knowledge unless the system prompt says otherwise.
- Never talk about "retrieved chunks", "uploaded documents", or "provided context".
- Never explain the retrieval process to the user.
- Respond naturally as if you already know the information.

Retrieved Context:

{context}

User Question:

{question}
"""