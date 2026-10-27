import os
from urllib.parse import urlparse


DEFAULT_AWS_SOURCE_HOST = "w3tyn52fphhljv24gjfcslmnxm0pooag.lambda-url.us-east-1.on.aws"
IDENTIFIER_ALIASES = {
    "add_ms_25498_fblef001v": "add_ms_25498_f001v",
}


def _normalized_base_url(env_name, default):
    value = os.environ.get(env_name, default).strip()
    return value.rstrip("/") if value else default.rstrip("/")


def iiif_image_base_url(public=False):
    if public:
        return _normalized_base_url(
            "IIIF_PUBLIC_IMAGE_BASE_URL",
            "https://slave-voyages-prod-aws.iq.harvard.edu/iiif/3",
        )
    return _normalized_base_url("IIIF_IMAGE_BASE_URL", "/iiif/3")


def iiif_manifests_base_url():
    return _normalized_base_url(
        "IIIF_MANIFESTS_BASEURL",
        "/iiif/manifests/",
    )


def aws_source_host():
    return os.environ.get("IIIF_AWS_SOURCE_HOST", DEFAULT_AWS_SOURCE_HOST).strip()


def canonical_identifier(identifier):
    return IDENTIFIER_ALIASES.get(identifier, identifier)


def rewrite_aws_iiif_url(url, public=False):
    if not url:
        return url
    parsed = urlparse(url)
    if parsed.netloc != aws_source_host():
        return url
    if not parsed.path.startswith("/iiif/3/"):
        return url
    tail = parsed.path[len("/iiif/3/") :]
    identifier, separator, suffix = tail.partition("/")
    localized_identifier = canonical_identifier(identifier)
    suffix = f"/{suffix}" if separator else ""
    return f"{iiif_image_base_url(public=public)}/{localized_identifier}{suffix}"


def build_manifest_url(filename):
    return f"{iiif_manifests_base_url()}/{filename.lstrip('/')}"
