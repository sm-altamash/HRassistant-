import re
import json
from concurrent.futures import ThreadPoolExecutor, as_completed

from prompts import Prompts

try:
    import google.generativeai as genai
except Exception as e:
    genai = None
    _GENAI_IMPORT_ERROR = e


class AI_Utilities:
    def initialize_llm(self, api_key: str, model_name: str = "gemini-1.5-flash-latest"):
        """
        Initialize the Google Generative AI client (Gemini).
        Pass your API key (hard-coded in app.py).
        """
        if genai is None:
            raise ImportError(
                "google.generativeai is not installed or failed to import. "
                "Install it with: pip install google-generativeai\n"
                f"Import error: {_GENAI_IMPORT_ERROR}"
            )

        # Configure with API key
        genai.configure(api_key=api_key)
        self.client = genai
        self.model_name = model_name

    def _call_model(self, system_prompt: str, human_prompt_template: str, **kwargs) -> str:
        """
        Fill the prompt and call Gemini model. Returns the text output.
        """
        if not hasattr(self, "client") or self.client is None:
            raise RuntimeError("Generative AI client not initialized. Call initialize_llm(api_key) first.")

        human_prompt = human_prompt_template.format(**kwargs)
        
        # Combine system prompt with human prompt (Gemini doesn't have native system messages)
        full_prompt = f"{system_prompt}\n\n{human_prompt}"

        try:
            # Create a GenerativeModel instance
            model = self.client.GenerativeModel(self.model_name)
            
            # Generate content with the combined prompt
            response = model.generate_content(
                full_prompt,
                generation_config={
                    "temperature": 0
                }
            )
            
            # Extract the text response
            if response and hasattr(response, 'text'):
                return response.text
            else:
                return str(response)
                
        except Exception as exc:
            raise RuntimeError(f"Model call failed: {exc}")

    def evaluate(self, jd_content, cv_content, candiateMode):
        """Parse JD & CV in parallel, then evaluate (text or JSON)."""
        def parse_jd():
            return self._call_model(
                Prompts.JD_PARSING_SYSTEM_PROMPT,
                Prompts.JD_PARSING_PROMPT,
                jd_content=jd_content
            )

        def parse_cv():
            return self._call_model(
                Prompts.RESUME_PARSING_SYSTEM_PROMPT,
                Prompts.RESUME_PARSING_PROMPT,
                cv_content=cv_content
            )

        parsed = {}
        with ThreadPoolExecutor(max_workers=2) as ex:
            futures = {ex.submit(parse_jd): "jd_summary", ex.submit(parse_cv): "cv_summary"}
            for fut in as_completed(futures):
                key = futures[fut]
                try:
                    parsed[key] = fut.result()
                except Exception:
                    parsed[key] = ""

        if candiateMode:
            json_output = self._call_model(
                Prompts.EVALUATION_SYSTEM_PROMPT_JSON,
                Prompts.EVALUATION_PROMPT_JSON,
                jd_summary=parsed.get("jd_summary", ""),
                resume_summary=parsed.get("cv_summary", "")
            )
            cleanJson = self.__clean_json_string(json_output)
            try:
                evaluation = json.loads(cleanJson)
                evaluation["jd_summary"] = parsed.get("jd_summary", "")
            except json.JSONDecodeError:
                evaluation = {"jd_summary": parsed.get("jd_summary", "")}
            return evaluation
        else:
            text_eval = self._call_model(
                Prompts.EVALUATION_SYSTEM_PROMPT,
                Prompts.EVALUATION_PROMPT,
                jd_summary=parsed.get("jd_summary", ""),
                resume_summary=parsed.get("cv_summary", "")
            )
            return text_eval

    def generate_suggestions(self, gaps):
        return self._call_model(
            Prompts.SUGGESTIONS_SYSTEM_PROMPT,
            Prompts.SUGGESTIONS_HUMAN_PROMPT,
            gaps=gaps
        )

    def rewrite_cv(self, cv_content, suggestions, job_requirements):
        return self._call_model(
            Prompts.CV_REWRITE_SYSTEM_PROMPT,
            Prompts.CV_REWRITE_HUMAN_PROMPT,
            original_cv=cv_content,
            suggestions=suggestions,
            job_requirements=job_requirements
        )

    def json_to_markdown_report(self, json_eval):
        gaps = json_eval.get("gaps", []) if isinstance(json_eval, dict) else []
        gaps_block = "- " + "\n- ".join(gaps) if gaps else "- No gaps detected"
        return f"""
**Job Title:** {json_eval.get("job_title", "N/A")}  
**Overall Match Score:** {json_eval.get("overall_score", "N/A")} 
     
**Gaps:**
{gaps_block}
        """

    def __clean_json_string(self, json_string):
        if not isinstance(json_string, str):
            try:
                json_string = str(json_string)
            except Exception:
                return ""
        pattern = r'^```(?:json)?\s*(.*?)\s*```$'
        cleaned_string = re.sub(pattern, r'\1', json_string, flags=re.DOTALL)
        return cleaned_string.strip()