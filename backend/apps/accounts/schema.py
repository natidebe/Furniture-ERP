from drf_spectacular.extensions import OpenApiAuthenticationExtension


class BotUserAuthenticationScheme(OpenApiAuthenticationExtension):
    """Documents the bot's sign-in: `Authorization: Bot <token>` + `X-Telegram-User`."""

    target_class = "apps.accounts.authentication.BotUserAuthentication"
    name = "botAuth"

    def get_security_definition(self, auto_schema):
        return {"type": "apiKey", "in": "header", "name": "Authorization",
                "description": "Telegram bot only: `Bot <BOT_SERVICE_TOKEN>`, with the "
                               "linked user's id in the `X-Telegram-User` header."}
