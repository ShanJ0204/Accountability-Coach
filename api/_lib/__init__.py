"""Shared code for the WhatsApp accountability & health coach bot.

Lives under ``api/_lib`` (leading underscore) so Vercel's Python builder does not
treat these modules as deployable serverless functions, while still bundling them
so the endpoint files in ``api/`` can ``from _lib.xxx import ...``.
"""
