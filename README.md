# AVAdmin

Discord bot to manage user accounts

## Execution

The following environment variables must be set prior to execution:

 - `TOKEN`: Discord bot token
 - `GUILD_IDS`: Discord Guild IDs that the bot will be allowed to operate in, joined by `.`
 - `ROLE_IDS`: Discord Role IDs that the bot will give to authenticated users, joined by `.`, indexed according to GUILD_IDS
 - `GUILD_IDS`: Discord Role IDs that the bot will automatically give to new users, joined by `.`, indexed according to GUILD_IDS

 You may also set the `LOG_LEVEL` variable to determine the verbosity of logs (according to the `logging` python module); defaults to DEBUG.

 The available values, in order of verbosity, are:

 > CRITICAL = FATAL < ERROR < WARNING = WARN < INFO < DEBUG

 Then you can execute the bot standalone using

 ```sh
python3 admin.py
 ```

You can also use [Bismuth](https://github.com/PYROP3/Bismuth) in order to execute the bot automatically.
