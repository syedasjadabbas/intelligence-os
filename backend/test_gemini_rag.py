import os
import sys
from dotenv import load_dotenv

load_dotenv(".env")
import google.generativeai as genai

api_key = os.environ.get("GEMINI_API_KEY")
genai.configure(api_key=api_key)

system_instruction = (
    "You are Intelligence OS. Answer the user's specific question directly and concisely in 1-2 natural sentences using ONLY the provided contexts.\n"
    "- Cite sources using [Source X].\n"
    "- Extract the exact requested fact (numbers, names, roles).\n"
    "- If the context lacks sufficient facts, reply ONLY:\n"
    "  'I cannot find sufficient evidence in the organization's documents to answer this question.'"
)

model = genai.GenerativeModel("gemini-3.8-flash", system_instruction=system_instruction)

context = (
    "[Source 1] (Document: lonetex_annual_report.pdf, Page: 4, Section: Workforce Overview)\n"
    "As of Q4 2025, Lonetex employs a total workforce of 14,250 full-time personnel globally across 18 manufacturing facilities."
)
prompt = (
    f"Context:\n{context}\n\n"
    "Question: What is the CEO's favorite breakfast cereal?\n\n"
    "Concise Answer:"
)

res = model.generate_content(prompt)
print("Response text:", repr(res.text.strip()))
