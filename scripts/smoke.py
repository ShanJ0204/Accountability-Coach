"""Smoke-test the Claude vision + structured-output path without WhatsApp or a DB.

Usage:
    python scripts/smoke.py path/to/food_photo.jpg
    python scripts/smoke.py --text "two scrambled eggs and toast with butter"

Requires ANTHROPIC_API_KEY (and optionally COACH_MODEL) in your environment / .env.
"""

import argparse
import json
import mimetypes
import os
import sys

# Make ``_lib`` importable when running from the repo root.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "api"))

from _lib import coach  # noqa: E402
from _lib.twilio_client import image_to_base64  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image", nargs="?", help="Path to a food image to analyze.")
    parser.add_argument("--text", help="Describe a meal in text instead of an image.")
    args = parser.parse_args()

    if args.text:
        est = coach.estimate_from_text(args.text)
    elif args.image:
        with open(args.image, "rb") as f:
            data = f.read()
        media_type = mimetypes.guess_type(args.image)[0] or "image/jpeg"
        est = coach.estimate_from_image(image_to_base64(data), media_type)
    else:
        parser.error("Provide an image path or --text.")

    print(json.dumps(est, indent=2))


if __name__ == "__main__":
    main()
