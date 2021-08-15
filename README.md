# AoT Discord Bot
This is the custom discord bot used on the [Alpha Omega United](https://discord.gg/KPuHwjMyCH) discord server.
The bot is written in python using [discord.py]() and [discord-py-slash-commands](),
the project is managed with [poetry]().

## Running
> if you dont already have `poetry` please install it using thse instructions: <https://python-poetry.org/docs/#installation>

first you need to create a `.env` file (or set envorment varibles some other way) containg the needed values (see `.test_env` for a example).

```bash
# install dependecies
poetry install

# run bot
poetry run task bot
```


## Contributing
first:
```bash
# Install precommit hooks.
poetry run task precommit
```

If you are testing on the default test server, `.test_env` will contain the values needed to run on the test server out of the box.

Now you can make your changes, and follow the normal git workflow.

### Some usefull commands.
```bash
# Lint project to make sure it meets standards
poetry run task lint

# Run black to auto format files so you dont need to do it manualy.
poetry run task black
```
