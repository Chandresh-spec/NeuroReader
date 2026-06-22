from django.conf import settings
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from huggingface_hub import InferenceClient
import requests

from library.models import UserFile
from .agent.pipeline import ReadingOptimizationAgent
from .agent.serializers import OptimizeReadingRequestSerializer, OptimizeReadingResponseSerializer

# ─────────────────────────────────────────────────────────────────────────────
# AI Models — using HuggingFace Hub InferenceClient
# The old raw requests endpoints (api-inference and router) are heavily 
# restricted or deprecated. huggingface_hub manages correct routing.
# ─────────────────────────────────────────────────────────────────────────────

def get_hf_client():
    api_key = getattr(settings, "HF_API_KEY", "")
    return InferenceClient(api_key=api_key, timeout=25)


def _err(e: Exception) -> Response:
    msg = str(e).lower()
    if "model_not_supported" in msg:
        return Response({"error": "Hugging Face Free Tier no longer supports this model. Please use a PRO key or switch to a supported model."}, status=502)
    if "timeout" in msg or "read operation timed out" in msg:
        return Response({"error": "AI model is waking up (cold start). Please try again in 30 seconds."}, status=503)
    if "unauthorized" in msg or "invalid" in msg:
        return Response({"error": "Invalid HuggingFace API key or missing permissions."}, status=502)
    return Response({"error": f"AI request failed: {str(e)[:200]}"}, status=502)


# ── 1. Simplify ───────────────────────────────────────────────────────────────
class SimplifyView(APIView):
    """POST /api/ai/simplify/"""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        text = (request.data.get("text") or "").strip()[:1500]
        if not text:
            return Response({"error": "No text provided."}, status=400)

        # Use Gemma-2-2B for simplification (supported on the free tier, no gating)
        try:
            client = get_hf_client()
            messages = [
                {"role": "system", "content": "You are a helpful reading assistant. Simplify the user's text into plain, easy-to-understand language. Do not add any extra conversational filler, just return the simplified text directly."},
                {"role": "user", "content": f"Simplify this text:\n\n{text}"}
            ]
            res = client.chat_completion(
                messages=messages, 
                model="google/gemma-2-2b-it",
                max_tokens=600
            )
            output = res.choices[0].message.content.strip()
            return Response({"simplified": output})
        except Exception as e:
            return _err(e)


# ── 2. Structure ──────────────────────────────────────────────────────────────
class StructureView(APIView):
    """POST /api/ai/structure/"""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        text = (request.data.get("text") or "").strip()[:1500]
        if not text:
            return Response({"error": "No text provided."}, status=400)

        # Use Gemma-2-2B for structuring text into bullet points
        try:
            client = get_hf_client()
            messages = [
                {"role": "system", "content": "You are a helpful reading assistant. Extract the main points from the user's text and format them as a concise bulleted list. Do not add conversational filler. Use a • character for each bullet point."},
                {"role": "user", "content": f"Format this text as a structural bulleted list:\n\n{text}"}
            ]
            res = client.chat_completion(
                messages=messages, 
                model="google/gemma-2-2b-it",
                max_tokens=600
            )
            output = res.choices[0].message.content.strip()
            return Response({"structured": output})
        except Exception as e:
            return _err(e)


# ── 3. Explain word (Dictionary API primary) ──────────────────────────────────
class ExplainWordView(APIView):
    """POST /api/ai/explain/"""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        word    = (request.data.get("word")    or "").strip().lower()
        context = (request.data.get("context") or "").strip()[:200]

        if not word:
            return Response({"error": "No word provided."}, status=400)

        # Primary: Free Dictionary API (super fast, reliable, no auth limits)
        try:
            r = requests.get(f"https://api.dictionaryapi.dev/api/v2/entries/en/{word}", timeout=8)
            if r.status_code == 200:
                entries = r.json()
                if entries:
                    entry    = entries[0]
                    phonetic = entry.get("phonetic", "")
                    meanings = entry.get("meanings", [])
                    parts    = []
                    for m in meanings[:2]:
                        pos  = m.get("partOfSpeech", "")
                        defs = m.get("definitions", [])
                        if defs:
                            d = defs[0]
                            defn    = d.get("definition", "")
                            example = d.get("example",    "")
                            part = f"[{pos}] {defn}"
                            if example:
                                part += f'\n  Example: "{example}"'
                            parts.append(part)
                    if parts:
                        explanation = "\n\n".join(parts)
                        if phonetic:
                            explanation = f"{phonetic}\n\n" + explanation
                        return Response({"word": word, "explanation": explanation})
        except Exception:
            pass

        return Response({"error": f"Definition not found in dictionary for '{word}'."}, status=404)


# ── 4. Agentic Reading Optimizer ──────────────────────────────────────────────
class AgentOptimizeReadingView(APIView):
    """
    POST /api/agent/optimize-reading/
    Analyzes text/file and intelligently recommends UI settings to optimize reading.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        req_serializer = OptimizeReadingRequestSerializer(data=request.data)
        if not req_serializer.is_valid():
            return Response(req_serializer.errors, status=400)

        data = req_serializer.validated_data
        
        # Extract text to analyze
        text_to_analyze = data.get("text", "")
        file_id = data.get("file_id")

        if not text_to_analyze and file_id:
            try:
                user_file = UserFile.objects.get(id=file_id, user=request.user)
                # In a real app we would extract text from the PDF/File here
                # As a fallback for demo, we read it if it's text-based or use a stub
                if user_file.file_type in ["TXT", "MD", "HTML", "RTF"]:
                    with user_file.file.open('r') as f:
                        text_to_analyze = f.read()[:5000] # just sample first 5k chars
                else:
                    # PDF or generic - assume client passes 'text' if they want exact page analysis
                    # Alternatively, default to generic placeholder for testing
                    text_to_analyze = "The file is a PDF. Text extraction requires passing the 'text' field directly from the frontend."
            except UserFile.DoesNotExist:
                return Response({"error": "File not found."}, status=404)
            except Exception as e:
                return Response({"error": f"Could not read file text: {str(e)}"}, status=500)

        # Run through Agent Pipeline
        agent = ReadingOptimizationAgent()
        result = agent.process_text(
            text=text_to_analyze, 
            current_settings=data.get("current_settings", {})
        )

        resp_serializer = OptimizeReadingResponseSerializer(data=result)
        if resp_serializer.is_valid():
            return Response(resp_serializer.validated_data)
        return Response(resp_serializer.errors, status=500)
