# LLM prompts

LLM prompts in text files.

Add a description of the prompts here, so we know what they're for.

- [recommendation_extraction.txt](recommendation_extraction.txt):
  Prompt for extracting recommendations from text written by organisations advising the United Nations. This prompt identifies all recommendations (typically grouped toward the end of documents), extracts exact text, and structures findings as JSON with fields for recommendation text, domain, beneficiaries, and theme. Themes are categorized from a predefined list including education, health, discrimination, child protection, environment, and human rights topics. Returns only the JSON array without formatting markers.
