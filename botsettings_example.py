version="1.3.1. beta"
activity_status = '%help'

maintenance_mode=True

owner_ids=[123]

bot_auth_token="token"
bot_log_webhook="https://canary.discordapp.com/api/webhooks/a/b"

database_credentials = {
	"user": "discordfarm",
	"password": "password",
	"database": "discordfarmdata",
	"host": "127.0.0.1"
}

initial_extensions = (
    'cogs.admin',
    'cogs.information',
    'cogs.profile',
    'cogs.shop',
    'cogs.market',
    'cogs.farm',
    'cogs.factory',
    'cogs.missions',
    'cogs.trades',
    'cogs.looting',
    'cogs.registration',
    'cogs.usercontrol'
)

gold_emoji='<:gold:722116061780246528>'
gem_emoji='<a:gem:722191212706136095>'
xp_emoji='<:xp:603145893029347329>'
tile_emoji='<:tile:603160625417420801>'