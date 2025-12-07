# EMF Orga Directory

https://github.com/emfcamp/orgahome

A small (mostly) Flask webapp which serves as a repo for some internal EMF
webpages.

If you're looking for the main website (emfcamp.org), that's
https://github.com/emfcamp/Website.

## Emoji

The Mattermost system emoji map comes from
https://github.com/mattermost/mattermost/raw/master/webapp/channels/src/utils/emoji.json,
which is saved locally into emoji.json.

## Developing

You'll need UFFD API credentials and a Mattermost access token. Ideally, you'd
also have UFFD OIDC credentials (although you can skip that by
[turning `OIDC_ENABLED` off](https://flask-oidc.readthedocs.io/en/latest/#testing-and-hacking-on-your-application)).

In production, the Mattermost access token belongs to `systembot`, but a PAT
will also do - it just needs to be able to list the users that are in the team.

If you're a Nix enjoyer, you should be able to:

```
$ nix develop
$ python -m orgahome uvicorn --host 127.0.0.1

# [hack away]

$ nix fmt
$ nix flake check
```

Otherwise, you can probably just get away with uv:

```
$ uv sync
$ uv run python -m orgahome uvicorn 

# check formatting/lint
$ uv run ruff check --fix
$ uv run ruff format

# run typechecking
$ uv run ty check
```

Note that treefmt may yell at you if you edit non-Python files without running
`nix fmt` - see `treefmt.nix` for the configured autoformatters/linters.
