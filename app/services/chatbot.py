"""AI career assistant backed by the Claude API.

Enabled only when ANTHROPIC_API_KEY is set. The conversation is stateless
server-side: the client sends the full message history, the job context is
injected as a (cached) system prompt.
"""
from collections.abc import AsyncIterator

import anthropic
from anthropic import AsyncAnthropic

from ..config import settings
from ..models import Alert, Job
from ..schemas import ChatMessage

_SYSTEM_TEMPLATE = """Tu es le conseiller carrière intégré d'OppFinder, une application privée de veille d'offres d'emploi et de stages.

L'utilisateur a trouvé l'offre ci-dessous via son alerte "{alert_name}" (mots-clés : {keywords}). Score de correspondance calculé : {score}/100.

<offre>
Titre : {title}
Entreprise : {company}
Lieu : {location}
Type de contrat : {contract_type}
Source : {source}
Lien : {url}

Description :
{description}
</offre>

Ton rôle :
- Analyser l'offre : missions, compétences attendues, signaux positifs ou d'alerte.
- Donner des conseils concrets et personnalisés pour adapter le CV et la lettre de motivation à cette offre (mots-clés à reprendre, expériences à mettre en avant).
- Préparer aux questions d'entretien probables pour ce poste.
- Aider à rédiger des extraits de candidature si demandé.
- Si l'utilisateur joint un fichier (CV), t'appuyer dessus pour des conseils concrets et personnalisés (reformulations, points à mettre en avant ou à retirer pour cette offre précise).

Règles : réponds en français, de façon concise et structurée (Markdown léger : titres courts, listes). N'utilise ni tirets longs ni caractères typographiques spéciaux, écris comme un humain. Si une information ne figure pas dans l'offre, dis-le franchement au lieu d'inventer. Adapte ton niveau de détail à la question posée."""


def chat_enabled() -> bool:
    return bool(settings.anthropic_api_key)


def _message_content(m: ChatMessage) -> str | list[dict]:
    if not m.attachment:
        return m.content
    document = {
        "type": "document",
        "source": {
            "type": "base64",
            "media_type": m.attachment.media_type,
            "data": m.attachment.data,
        },
        "title": m.attachment.filename[:200],
    }
    return [document, {"type": "text", "text": m.content}]


def _build_system(job: Job, alert: Alert) -> str:
    return _SYSTEM_TEMPLATE.format(
        alert_name=alert.name,
        keywords=", ".join(alert.keywords or []),
        score=round(job.score),
        title=job.title,
        company=job.company or "non précisée",
        location=job.location or "non précisé",
        contract_type=job.contract_type or "non précisé",
        source=job.source,
        url=job.url,
        description=job.description or "(description non disponible)",
    )


async def stream_reply(job: Job, alert: Alert, messages: list[ChatMessage]) -> AsyncIterator[str]:
    client = AsyncAnthropic(api_key=settings.anthropic_api_key)
    system = [
        {
            "type": "text",
            "text": _build_system(job, alert),
            # stable per-conversation prefix - cheap multi-turn follow-ups
            "cache_control": {"type": "ephemeral"},
        }
    ]
    api_messages = [{"role": m.role, "content": _message_content(m)} for m in messages]
    try:
        async with client.messages.stream(
            model=settings.anthropic_model,
            max_tokens=2048,
            thinking={"type": "adaptive"},
            output_config={"effort": "low"},
            system=system,
            messages=api_messages,
        ) as stream:
            async for text in stream.text_stream:
                yield text
    except anthropic.RateLimitError:
        yield "\n\n_[Le service IA est momentanément saturé, réessaie dans une minute.]_"
    except anthropic.APIStatusError as exc:
        yield f"\n\n_[Erreur du service IA ({exc.status_code}). Réessaie plus tard.]_"
    except anthropic.APIConnectionError:
        yield "\n\n_[Impossible de joindre le service IA depuis le serveur.]_"
