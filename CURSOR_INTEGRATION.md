# Cursor Integration Guide - LoL Data MCP Server

## 🚀 Ready for Integration!

Your LoL Data MCP Server is **functional and ready** for basic Cursor integration!

## 📋 Current Capabilities

✅ **Working Features:**
- MCP server runs on `localhost:8000`
- Health check endpoint: `http://localhost:8000/health`
- MCP WebSocket: `ws://localhost:8000/mcp`
- Basic tools: `ping`, `server_info`
- Champion data: `get_champion_data` (Taric, Ezreal with full stats/abilities)

⚠️ **Current Limitations:**
- Limited to 2-3 champions (mock data)
- No real LoL Wiki or Riot API integration yet
- Some configuration management incomplete

## 🔧 Setup Instructions

### 1. Add to Cursor MCP Settings

Open Cursor Settings → Extensions → MCP Settings, and add:

```json
{
  "mcpServers": {
    "lol-data": {
      "command": "python",
      "args": ["-m", "src.mcp_server.server"],
      "cwd": "C:/Users/tarik/OneDrive/Masaüstü/Python/Reinforcement Learning Projects/Project Taric/Lol_Data_MCP_Server",
      "env": {
        "PYTHONPATH": "."
      }
    }
  }
}
```

### 2. Activate Virtual Environment

Before running, ensure the MCP server's virtual environment is set up:

```bash
cd "Lol_Data_MCP_Server"
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### 3. Test the Integration

In Cursor, you should now be able to use MCP tools:

```
@mcp lol-data get_champion_data {"champion": "Taric", "include": ["stats", "abilities"]}
```

### 4. Available Champion Data

Currently working champions:
- **Taric** (complete stats, abilities, support/tank role)
- **Ezreal** (complete stats, abilities, ADC role)

## 🎯 Recommended Usage

**Perfect for your Taric AI Agent project:**
- Get Taric's complete champion data for simulation
- Access ability details for skill mechanics
- Use stat data for training environment setup

**Example Usage:**
```python
# In your AI agent code (when integrated)
taric_data = mcp_client.call_tool("get_champion_data", {
    "champion": "Taric",
    "include": ["stats", "abilities"]
})

# Use in simulation environment
taric_stats = taric_data["stats"]
taric_abilities = taric_data["abilities"]
```

## 🚧 Future Development

**Next planned features:**
- Real LoL Wiki data scraping (Task 2.1)
- Riot API integration
- All 160+ champions
- Item data and meta builds
- Patch tracking

## 📞 Support

If you encounter issues:
1. Check server health: `curl http://localhost:8000/health`
2. View server logs for errors
3. Ensure virtual environment is activated
4. Verify Python path and dependencies

---

**Status:** ✅ Ready for basic integration and testing
**Last Updated:** June 22, 2025

**🚨 IMPORTANT: Unicode Path Issue Fix**

Due to PowerShell Unicode handling issues with Turkish characters (`Masaüstü`), use this updated configuration:

## Fixed Cursor Configuration

Add this to your Cursor settings (`.cursor-settings/config.json`):

```json
{
  "mcpServers": {
    "lol-data": {
      "command": "cmd",
      "args": ["/c", "cd /d \"C:\\Users\\tarik\\OneDrive\\Masaüstü\\Python\\Reinforcement Learning Projects\\Project Taric\\Lol_Data_MCP_Server\" && venv\\Scripts\\activate && python -m src.mcp_server.stdio_server"]
    }
  }
}
```

**Alternative Configuration (PowerShell with UTF-8)**:
```json
{
  "mcpServers": {
    "lol-data": {
      "command": "powershell",
      "args": ["-NoLogo", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", "[Console]::OutputEncoding = [System.Text.Encoding]::UTF8; cd 'C:\\Users\\tarik\\OneDrive\\Masaüstü\\Python\\Reinforcement Learning Projects\\Project Taric\\Lol_Data_MCP_Server'; .\\venv\\Scripts\\Activate.ps1; python -m src.mcp_server.stdio_server"]
    }
  }
}
```

## Original Configuration (Reference)

```json
{
  "mcpServers": {
    "lol-data": {
      "command": "powershell",
      "args": ["-Command", "& { cd 'C:\\Users\\tarik\\OneDrive\\Masaüstü\\Python\\Reinforcement Learning Projects\\Project Taric\\Lol_Data_MCP_Server'; .\\venv\\Scripts\\Activate.ps1; python -m src.mcp_server.stdio_server }"]
    }
  }
}
```

## Testing the Fix

After updating the configuration:

1. Restart Cursor completely
2. Check MCP server status in Cursor settings
3. The server should show as connected with 7 tools available 