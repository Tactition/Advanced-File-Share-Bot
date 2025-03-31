# 🏰 Tactitions Empire Assistant

<p align="center">
  <img src="https://img.freepik.com/premium-photo/man-suit-is-playing-chess_1072138-227070.jpg?w=826" alt="Tactitions Empire Assistant" width="400">
</p>

<div align="center">

**Advanced Telegram File Store Bot with Premium Features**  
*Created by [@tactition](https://telegram.me/tactition)*

</div>

---

## ✨ Key Features

- **🔗 Permanent Links** - Generate permanent links via website integration
- **👥 Clone Feature** - Create your own instance of the bot
- **🎬 Stream Support** - Stream files with multi-player compatibility
- **🔄 Batch Processing** - Generate multiple file links at once
- **⏱️ Auto Delete** - Set files to delete after specified time
- **🔗 Custom URL Shortener** - Integrate your own URL shortener service
- **📊 User Stats** - Track usage and performance metrics
- **📡 Uptime Monitoring** - Automatic server pinging functionality
- **📝 Customizable Start Message** - Welcome users with branded content
- **🔐 Token Verification** - Security enhancement for user verification
- **📂 Database Channel Support** - Save content when links are generated
- **📋 Logging Capabilities** - Track user requests and activities

[**Watch Deployment Tutorial**](https://youtu.be/VxAn9VcYtQg)

---

## 🚀 Getting Started

### Environment Variables

| Variable | Description | Source |
|----------|-------------|--------|
| `API_ID` | Telegram API ID | [my.telegram.org](https://my.telegram.org) |
| `API_HASH` | Telegram API Hash | [my.telegram.org](https://my.telegram.org) |
| `BOT_TOKEN` | Bot Token | [BotFather](https://telegram.me/BotFather) |
| `BOT_USERNAME` | Your Bot Username (without @) | - |
| `DB_URI` | MongoDB Database URL for Main Bot | [Tutorial](https://youtu.be/I36_OTWvT2w) |
| `CDB_URI` | MongoDB Database URL for Clone Bot | [Tutorial](https://youtu.be/I36_OTWvT2w) |
| `ADMINS` | Admin/Owner ID for Broadcasting | - |
| `LOG_CHANNEL` | Log channel ID starting with -100xxxxxx | - |
| `BIN_CHANNEL` | Bin channel ID starting with -100xxxxxx | - |
| `FILE_STORE_CHANNEL` | File Store Channel ID starting with -100xxxxxx | - |
| `FQDN` | Your Server App Link (without https://) | - |
| `AUTO_DELETE` | Time in Minutes | - |
| `AUTO_DELETE_TIME` | Time in Seconds | - |
| `PYTHON_VERSION` | Render-specific, set to `3.10.8` | - |
| `PORT` | Render-specific, set to `8080` | - |

---

## 📋 Bot Commands

### Main Bot Commands

- `/start` - Check if bot is alive
- `/link` - Generate shareable link by replying to a file
- `/batch` - Generate multiple shareable links using `/batch (first post link) (last post link)`
- `/base_site` - Set URL shortener domain via `/base_site domain.com`
- `/api` - Set URL shortener API with `/api (your api key)`
- `/deletecloned` - Delete cloned bot using `/deletecloned (bot token)`
- `/broadcast` - Send message to all users (Owner only)
- `/stats` - Check bot statistics (Owner only)
- `/users` - Count active users

### Clone Bot Commands

- `/start` - Check if bot is alive
- `/link` - Generate shareable link by replying to a file
- `/base_site` - Set URL shortener domain via `/base_site domain.com`
- `/api` - Set URL shortener API with `/api (your api key)`
- `/broadcast` - Send message to all users (Clone Owner only)

---

## 👨‍💻 About the Developer

- **YouTube:** [Tactition](https://youtube.com/@iamvarible01)
- **Telegram:** [@tactition](https://telegram.me/tactition)
- **Instagram:** [Tactition](https://instagram.com)

---

## 📝 License

Copyright © [Tactition](https://telegram.me/tactition)

*Selling this repo or code is allowed, as the owner will not take action.*

---

<p align="center">
⭐ <b>If you find this project useful, please consider giving it a star!</b> ⭐
</p>
