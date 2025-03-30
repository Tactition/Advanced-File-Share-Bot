import asyncio
import logging
import aiohttp
from config import PING_INTERVAL,URL



# Use the module's logger. Assumes your main app has already configured logging.
logger = logging.getLogger(__name__)

async def ping_server():
    """Continuously pings the server to prevent the instance from idling."""
    while True:
        await asyncio.sleep(PING_INTERVAL)
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
                async with session.get(URL) as resp:
                    logger.info(f"Pinged server with response: {resp.status}")
        except Exception as e:
            logger.error(f"Error pinging server: {e}")
