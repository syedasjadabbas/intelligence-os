import asyncio
from pathlib import Path
import os
import sys
from dotenv import load_dotenv

env_path = Path(__file__).parent / ".env"
load_dotenv(env_path if env_path.exists() else ".env")
import google.generativeai as genai
from app.services.rag_service import rag_service

system_instruction = (
    "You are Intelligence OS. Answer the user's specific question directly and concisely in 1-2 natural sentences using ONLY the provided contexts.\n"
    "- Cite sources using [Source X].\n"
    "- Extract the exact requested fact (numbers, names, roles).\n"
    "- If the context lacks sufficient facts, reply ONLY:\n"
    "  'I cannot find sufficient evidence in the organization's documents to answer this question.'"
)

context = (
    "[Source 1] (Document: lonetex_annual_report.pdf, Page: 4, Section: Workforce Overview)\n"
    "As of Q4 2025, Lonetex employs a total workforce of 14,250 full-time personnel globally across 18 manufacturing facilities."
)
prompt = (
    f"Context:\n{context}\n\n"
    "Question: What is the CEO's favorite breakfast cereal?\n\n"
    "Concise Answer:"
)

async def main():
    res_text = await rag_service._generate_gemini_content(
        system_instruction=system_instruction,
        prompt=prompt,
    )
    print("Response text:", repr(res_text.strip()))

if __name__ == "__main__":
    asyncio.run(main())
