import click
from flask import Flask
from flask.cli import FlaskGroup

from orgahome.app import app


def create_app():
    return app


@click.group(cls=FlaskGroup, create_app=create_app)
def cli():
    """Management script for orgahome."""
