"""Replaceable wording boundary. This version has no model/network implementation.

Paid inference is disabled, not simulated as a live AI call. Introducing a paid
adapter requires persistent atomic budget reservation and measured provider usage.
"""
import hashlib
import json


class TemplateInference:
    mode = "template-fixture"
    prompt_version = "outreach-template-v1"

    def draft(self, lead, terms, policy):
        key = hashlib.sha256(json.dumps({
            "tenant": "single-local-demo", "lead": lead["id"],
            "profile": lead["profile"], "contact": lead["contact"],
            "organization": lead["organization"], "source_version": lead["version"],
            "terms": terms["version"], "policy": policy["version"],
            "prompt": self.prompt_version, "model": "none"
        }, sort_keys=True).encode()).hexdigest()
        return {
            "mode": self.mode,
            "content": (
                f"Hi {lead['contact']},\n\n"
                f"Your team at {lead['organization']} is described in our synthetic fixture as: "
                f"{lead['profile']}. We would like to explore an affiliate partnership. "
                "Would a short introductory conversation be useful?\n\n"
                "Demo partnership team\nReply 'unsubscribe' to stop follow-ups."
            ),
            "fact_refs": [f"fixture:{lead['id']}:v{lead['version']}", terms["version"]],
            "cache_key": key,
            "provider": None, "model": None, "provider_attempts": 0,
            "input_tokens": 0, "output_tokens": 0,
            "estimated_cost_usd": "0.00", "actual_cost_usd": "0.00",
            "label": "Personalized template fallback; no live AI call"
        }

    def validate_candidate(self, candidate, approved_content, approved_fact_refs=()):
        """Free model wording cannot introduce binding terms or unknown facts.

        The conservative baseline accepts the exact approved rendering only.
        A production language adapter needs task-specific factual evaluations.
        """
        try:
            value = json.loads(candidate) if isinstance(candidate, str) else candidate
            if set(value) != {"content", "fact_refs"}:
                return False
            return (value["content"] == approved_content
                    and value["fact_refs"] == list(approved_fact_refs))
        except (TypeError, ValueError):
            return False

    def paid_call(self, *_args, **_kwargs):
        raise PermissionError("Paid inference disabled: no approved provider, price or monetary envelope")
