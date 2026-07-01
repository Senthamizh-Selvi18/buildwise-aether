class StyleAgent:
    def identify_aesthetic(self, user_prompt: str) -> str:
        text = user_prompt.lower()
        if "minimal" in text:
            return "Minimalist"
        if "traditional" in text or "classic" in text:
            return "Traditional"
        if "luxury" in text or "premium" in text:
            return "Luxury"
        if "contemporary" in text:
            return "Contemporary"
        return "Modern Style Blueprint"