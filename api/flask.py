"""Vercel entry point for the Flask WSGI application.

Vercel discovers Python serverless functions from the api/ directory.  Keep the
application factory in the normal application modules and only expose the WSGI
object here.
"""
from run import app

__all__ = ["app"]
