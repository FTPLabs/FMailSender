"""
  FMailSender HTML Email Generator v1.0.0
  AI-powered template generation and uniqueization.
  Supports OpenAI, OpenRouter, Groq, Together.ai, Ollama (any OpenAI-compatible API).
  """
  from __future__ import annotations

  import json
  import os
  import threading
  import urllib.error
  import urllib.request
  from typing import Callable, Optional

  UNIVERSAL_INBOX_PROMPT = """You are a professional email marketer with 10 years of experience.
  Create an HTML email that lands in the inbox (not spam).

  TECHNICAL REQUIREMENTS:
  - Minimum 60% text vs images ratio
  - Maximum 3 links in the email
  - Required: unsubscribe link in footer: {{unsubscribe_url}}
  - No URL shorteners (bit.ly etc.)
  - Inline CSS only, table-based layout for Outlook compatibility
  - Alt text on all images
  - Mobile responsive (media queries for width < 600px)

  CONTENT REQUIREMENTS:
  - Do NOT use words: free, urgent, discount, guaranteed, money, winner
  - Personal greeting by first name in first line
  - Specific benefit in first 50 chars of Subject
  - Subject: question or unexpected statement (for engagement)
  - Tone: conversational, from a person, not a company
  - ONE clear CTA — not multiple
  - Personalization: {{first_name}}, {{company}}, {{email}}

  STRUCTURE:
  1. Personal greeting (2-3 sentences)
  2. Specific problem/situation (1 paragraph)
  3. Solution/offer (1-2 paragraphs)
  4. Single CTA button
  5. Signature with real name (not "The Team")

  Content to write about: {prompt}
  """

  UNIQUEIZE_PROMPT = """You are an expert at rewriting HTML emails to bypass spam filters while keeping the message intact.

  Rewrite this HTML email:
  1. Replace spam-trigger words with natural synonyms (free→complimentary, urgent→important)
  2. Rephrase headlines and CTAs (keep meaning, change wording)
  3. Insert Zero Width Space (U+200B) characters inside suspicious words
  4. Vary HTML structure (rename CSS classes, swap some divs to tables)
  5. Add unique preheader text variation
  6. Ensure unsubscribe link is present

  Level: {level}
  - light: text changes only
  - medium: text + HTML structure changes
  - deep: full rewrite keeping only the core message

  Original HTML:
  {html}

  Return ONLY valid HTML, no explanation.
  """

  PROVIDERS: dict[str, dict] = {
      "openai":     {"base_url": "https://api.openai.com/v1",          "model": "gpt-4o-mini"},
      "openrouter": {"base_url": "https://openrouter.ai/api/v1",       "model": "meta-llama/llama-3.1-8b-instruct:free"},
      "groq":       {"base_url": "https://api.groq.com/openai/v1",     "model": "llama3-8b-8192"},
      "together":   {"base_url": "https://api.together.xyz/v1",        "model": "meta-llama/Llama-3-8b-chat-hf"},
      "ollama":     {"base_url": "http://localhost:11434/v1",           "model": "llama3"},
  }


  def _api_request(base_url: str, api_key: str, model: str, prompt: str, max_tokens: int = 4096) -> str:
      """Make OpenAI-compatible chat completion request. Returns content string."""
      payload = json.dumps({
          "model": model,
          "messages": [{"role": "user", "content": prompt}],
          "max_tokens": max_tokens,
          "temperature": 0.7,
      }).encode("utf-8")
      req = urllib.request.Request(
          f"{base_url.rstrip('/')}/chat/completions",
          data=payload,
          headers={
              "Authorization": f"Bearer {api_key}",
              "Content-Type": "application/json",
              "Accept": "application/json",
          },
          method="POST",
      )
      with urllib.request.urlopen(req, timeout=60) as resp:
          data = json.loads(resp.read())
      return data["choices"][0]["message"]["content"]


  class HtmlEmailGenerator:
      """
      Generates and uniqueizes HTML email templates via any OpenAI-compatible API.

      Usage:
          gen = HtmlEmailGenerator(api_key="sk-...", provider="openai")
          gen.generate_template(
              prompt="Promote our SaaS project management tool to startup CTOs",
              style="professional",
              on_result=lambda html: editor.setHtml(html),
              on_error=lambda e: show_error(e),
          )
      """

      def __init__(
          self,
          api_key: Optional[str] = None,
          provider: str = "openai",
          custom_base_url: Optional[str] = None,
          custom_model: Optional[str] = None,
      ):
          self._api_key = api_key or os.environ.get("OPENAI_API_KEY", "").strip()
          provider_cfg = PROVIDERS.get(provider, PROVIDERS["openai"])
          self._base_url = custom_base_url or provider_cfg["base_url"]
          self._model = custom_model or provider_cfg["model"]

      def generate_template(
          self,
          prompt: str,
          style: str = "professional",
          on_result: Optional[Callable[[str], None]] = None,
          on_error: Optional[Callable[[str], None]] = None,
      ) -> threading.Thread:
          """Generate HTML email from user prompt. Runs in daemon thread."""
          full_prompt = UNIVERSAL_INBOX_PROMPT.format(prompt=f"[{style.upper()}] {prompt}")
          return self._run_async(full_prompt, on_result, on_error)

      def uniqueize_template(
          self,
          html: str,
          level: str = "medium",
          on_result: Optional[Callable[[str], None]] = None,
          on_error: Optional[Callable[[str], None]] = None,
      ) -> threading.Thread:
          """Uniqueize existing HTML template to bypass spam filters."""
          if len(html) > 8000:
              html = html[:8000] + "..."
          full_prompt = UNIQUEIZE_PROMPT.format(level=level, html=html)
          return self._run_async(full_prompt, on_result, on_error)

      def improve_subject(
          self,
          subject: str,
          body_preview: str = "",
          count: int = 5,
          on_result: Optional[Callable[[list], None]] = None,
          on_error: Optional[Callable[[str], None]] = None,
      ) -> threading.Thread:
          """Generate N improved subject line variants."""
          prompt = (
              f"Generate {count} email subject line variants that maximize open rate "
              f"and avoid spam filters. Original: '{subject}'. "
              f"Email preview: {body_preview[:300]}. "
              f"Rules: no caps lock, no '!', max 60 chars, create curiosity. "
              f"Return as JSON array of strings."
          )
          def _run():
              try:
                  raw = _api_request(self._base_url, self._api_key, self._model, prompt, max_tokens=512)
                  # Extract JSON array from response
                  import re
                  m = re.search(r'\[.*?\]', raw, re.DOTALL)
                  subjects = json.loads(m.group()) if m else [raw]
                  if on_result:
                      on_result(subjects)
              except Exception as e:
                  if on_error:
                      on_error(str(e))
          t = threading.Thread(target=_run, daemon=True)
          t.start()
          return t

      def _run_async(
          self,
          prompt: str,
          on_result: Optional[Callable[[str], None]],
          on_error: Optional[Callable[[str], None]],
      ) -> threading.Thread:
          def _run():
              if not self._api_key:
                  if on_error:
                      on_error("API key not set. Add OPENAI_API_KEY to environment or set in Settings.")
                  return
              try:
                  result = _api_request(self._base_url, self._api_key, self._model, prompt)
                  if on_result:
                      on_result(result)
              except urllib.error.HTTPError as e:
                  msg = f"API error {e.code}: {e.read().decode('utf-8', errors='replace')[:200]}"
                  if on_error:
                      on_error(msg)
              except Exception as e:
                  if on_error:
                      on_error(str(e))
          t = threading.Thread(target=_run, daemon=True)
          t.start()
          return t
  