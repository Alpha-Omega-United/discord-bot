"""Start the bot."""

import dns.resolver

from bot import constants
from bot.bot import create_bot

dns.resolver.default_resolver = dns.resolver.Resolver(configure=False)
dns.resolver.default_resolver.nameservers = constants.DNS_SERVERS

if __name__ == "__main__":
    create_bot().run()
