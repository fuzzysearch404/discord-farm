# Discord Farm Bot
This is the code for Discord Farm, the Discord bot.

You can invite the bot from these Discord bot list sites:  
https://top.gg/bot/526436949481881610  
https://discord.bots.gg/bots/526436949481881610  

Or directly:  
https://discord.com/oauth2/authorize?client_id=526436949481881610&scope=bot&permissions=387136  


**This project is in a maintenance mode**  
This means that this project is kept alive, by only updating mandatory things - 
the bot is not planned to be reworked and no new features are planned for now.  
I have been programming this bot for couple years, alongside learning Python 
programming language on my own. So the code you see here is the result of 
years of experimenting, copying other code snippets, reworking features. 
That means that you should not use this code as an example for your own projects.  

You **should not** run this bot on your own. If you really want to, 
I have abstractly described installation steps in `setup.sh` file.  
## Requirements:
1) Python 3.8+ (dev version)
2) pip install discord.py
3) pip install asyncpg
4) pip install aioredis
5) pip install psutil
6) pip install websockets
7) pip install requests

## Instalation:
1) Set up PostgreSQL with `schema.sql`
2) Set up Redis
3) Fill `botsettings.py`

## Launching:
1) Ensure PostgreSQL and Redis are running.
2) Launch `ipc.py`
3) Launch `launcher.py`
