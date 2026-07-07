"""
IBM watsonx.ai Client Wrapper
Handles authentication, token refresh, and text generation
using IBM Granite models via the watsonx.ai inference API.
"""

import os
import time
import logging
import requests
from typing import Optional

logger = logging.getLogger(__name__)


class WatsonxClient:
    """
    Thin wrapper around the IBM watsonx.ai REST API.
    Handles IAM token lifecycle and exposes a simple generate() method.
    """

    IAM_URL = "https://iam.cloud.ibm.com/identity/token"
    GENERATE_PATH = "/ml/v1/text/generation?version=2023-05-29"

    def __init__(
        self,
        api_key: str,
        project_id: str,
        base_url: str,
        model_id: str = "ibm/granite-13b-chat-v2",
    ):
        self.api_key = api_key
        self.project_id = project_id
        self.base_url = base_url.rstrip("/")
        self.model_id = model_id
        self._token: Optional[str] = None
        self._token_expiry: float = 0.0

    # ─────────────────────────────────────────────────────────────
    # Public API
    # ─────────────────────────────────────────────────────────────

    def generate(
        self,
        prompt: str,
        max_new_tokens: int = 1024,
        temperature: float = 0.7,
        top_p: float = 0.9,
        top_k: int = 50,
        repetition_penalty: float = 1.1,
        model_id: Optional[str] = None,
    ) -> str:
        """
        Send a generation request to watsonx.ai and return the generated text.
        Automatically refreshes the IAM token when needed.
        """
        token = self._get_token()
        url = f"{self.base_url}{self.GENERATE_PATH}"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        payload = {
            "model_id": model_id or self.model_id,
            "project_id": self.project_id,
            "input": prompt,
            "parameters": {
                "decoding_method": "sample",
                "max_new_tokens": max_new_tokens,
                "min_new_tokens": 10,
                "temperature": temperature,
                "top_k": top_k,
                "top_p": top_p,
                "repetition_penalty": repetition_penalty,
            },
        }

        try:
            resp = requests.post(url, json=payload, headers=headers, timeout=60)
            resp.raise_for_status()
            data = resp.json()
            results = data.get("results", [])
            if results:
                return results[0].get("generated_text", "").strip()
            return ""
        except requests.exceptions.Timeout:
            logger.error("watsonx.ai request timed out")
            return self._fallback_response(prompt)
        except requests.exceptions.HTTPError as e:
            logger.error("watsonx.ai HTTP error: %s — %s", e, resp.text[:200])
            return self._fallback_response(prompt)
        except Exception as e:
            logger.error("watsonx.ai unexpected error: %s", e)
            return self._fallback_response(prompt)

    def health_check(self) -> dict:
        """Check API connectivity and return status."""
        try:
            token = self._get_token()
            return {"status": "connected", "model": self.model_id, "token_valid": bool(token)}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    # ─────────────────────────────────────────────────────────────
    # IAM Token Management
    # ─────────────────────────────────────────────────────────────

    def _get_token(self) -> str:
        """Return a valid IAM bearer token, refreshing if within 5 minutes of expiry."""
        if self._token and time.time() < self._token_expiry - 300:
            return self._token
        self._refresh_token()
        return self._token

    def _refresh_token(self):
        """Fetch a new IAM access token."""
        payload = {
            "grant_type": "urn:ibm:params:oauth:grant-type:apikey",
            "apikey": self.api_key,
        }
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        resp = requests.post(self.IAM_URL, data=payload, headers=headers, timeout=30)
        if not resp.ok:
            # Surface the exact IBM error message before raising so it appears in logs.
            try:
                ibm_error = resp.json()
                ibm_msg = ibm_error.get("errorMessage") or ibm_error.get("errorDescription") or resp.text[:400]
            except Exception:
                ibm_msg = resp.text[:400]
            logger.error(
                "IBM IAM token request failed — HTTP %s. IBM error: %s",
                resp.status_code,
                ibm_msg,
            )
            resp.raise_for_status()
        data = resp.json()
        self._token = data["access_token"]
        expires_in = data.get("expires_in", 3600)
        self._token_expiry = time.time() + expires_in
        logger.info("IBM IAM token refreshed, expires in %ds", expires_in)

    # ─────────────────────────────────────────────────────────────
    # Fallback
    # ─────────────────────────────────────────────────────────────

    def _fallback_response(self, prompt: str) -> str:
        """Return a graceful fallback message when the API is unavailable."""
        if "question" in prompt.lower():
            return '[{"id":1,"question":"Tell me about your experience with the technologies mentioned in your resume.","type":"behavioral","difficulty":"medium","topic":"General","hints":"","expected_answer_outline":""}]'
        return '{"overall_score":50,"grade":"C","detailed_feedback":"API temporarily unavailable. Please try again.","strengths":["Attempted the question"],"improvements":["Please retry for detailed feedback"]}'
