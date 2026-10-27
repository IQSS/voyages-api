from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Post, PUBLISH_STATUS
import json
from django.utils.text import slugify

from django.db import transaction

#import os
#os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "/voyages.apps.blog/google_auth.json"



SOURCE_LANGUAGE = "en"
TRANSLATION_MAX_CHARS = 20000
TRANSLATION_BLOCK_BOUNDARIES = (
    "</p>", "</div>", "</li>", "</tr>", "</section>",
    "<br>", "<br/>", "<br />", "\n\n",
)



def on_transaction_commit(func):
    def inner(*args, **kwargs):
        transaction.on_commit(lambda: func(*args, **kwargs))

    return inner


@receiver(post_save, sender=Post)
@on_transaction_commit
def post_saved(sender, instance, **kwargs):
    
    if instance.status == PUBLISH_STATUS and instance.language == SOURCE_LANGUAGE:
        
        for lang_code, _ in settings.LANGUAGES:
            if lang_code != SOURCE_LANGUAGE:
                # First check if the target language already has a translation.
                count = Post.objects.filter(slug=instance.slug, language=lang_code).count()
                if count > 0:
                    continue
                

                clone = Post.objects.get(pk=instance.pk)

                authors = clone.authors.all()
                tags = clone.tags.all()

                clone.pk = None

              
                if not clone.title in [None, '']:
                    clone.title = translate_text(lang_code, instance.title)

                if not clone.subtitle in [None, '']:
                    clone.subtitle = translate_text(lang_code, instance.subtitle)

                if not clone.content in [None, '']:
                    clone.content = translate_text(lang_code, instance.content)

                clone.language = lang_code

                clone.save()                
                
                clone.authors.set(authors)
                clone.tags.set(tags)



                
    

def _last_safe_translation_boundary(text, start, limit):
    in_tag = False
    quote = None
    last_boundary = 0

    for index in range(start, limit):
        char = text[index]
        if in_tag:
            if quote is not None:
                if char == quote:
                    quote = None
            elif char in ("'", '"'):
                quote = char
            elif char == ">":
                in_tag = False
            continue

        if char == "<":
            in_tag = True
        elif char.isspace():
            last_boundary = index + 1

    return last_boundary


def _translation_chunks(text, max_chars=TRANSLATION_MAX_CHARS):
    if max_chars <= 0:
        raise ValueError("max_chars must be positive")
    if len(text) <= max_chars:
        return [text]

    chunks = []
    offset = 0
    while len(text) - offset > max_chars:
        limit = offset + max_chars
        split_at = 0
        for marker in TRANSLATION_BLOCK_BOUNDARIES:
            position = text.rfind(marker, offset, limit)
            if position >= offset:
                split_at = max(split_at, position + len(marker))

        if split_at <= offset:
            split_at = _last_safe_translation_boundary(text, offset, limit)
        if split_at <= offset:
            split_at = limit

        chunks.append(text[offset:split_at])
        offset = split_at

    chunks.append(text[offset:])
    return chunks


def translate_text(target, text):
    """Translates text into the target language.

    Target must be an ISO 639-1 language code.
    See https://g.co/cloud/translate/v2/translate-reference#supported_languages
    """
    
    from google.cloud import translate_v2 as translate
    
    if isinstance(text, bytes):
    	text = text.decode("utf-8")

    translate_client = translate.Client.from_service_account_json(
        r"voyages3/google_auth.json"
    )

    translated_chunks = []
    for chunk in _translation_chunks(text):
        result = translate_client.translate(chunk, target_language=target)
        translated_chunks.append(result["translatedText"])
    return "".join(translated_chunks)
