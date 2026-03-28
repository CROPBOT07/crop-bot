# 🌾 Farming Helper - AI-Powered Farming Assistant

A beautiful, interactive web application that helps students learn about farming by answering questions using multiple AI providers with automatic fallback.

## Features

- 🎨 **splitting/changing farming background** - Beautiful farming/nature inspired background
- 🤖 **Multi-AI Support** - Automatically uses multiple AI providers with fallback
- 🔄 **Automatic Fallback** - If one AI service fails, automatically tries the next one
- 📱 **Responsive Design** - Works on desktop and mobile devices
- 🎯 **Student-Friendly** - Simple, clear interface perfect for school projects

## Setup Instructions

### 1. Install Python Dependencies

```bash
pip install -r requirements.txt
```

### 2. Get API Keys (At least 2 recommended)

You can use any combination of these AI providers:

- **DeepSeek**: https://platform.deepseek.com/ (Free tier available)
- **Groq**: https://console.groq.com/ (Very fast, generous free tier)
- **OpenAI**: https://platform.openai.com/ (Free credits for new accounts)
- **Anthropic**: https://console.anthropic.com/ (Optional)

### 3. Configure API Keys

**Option 1: Using .env file (Recommended)**

1. Copy the example file:
   ```bash
   copy env.example .env
   ```
   (On Linux/Mac: `cp env.example .env`)

2. Open `.env` file and add your API keys:
   ```
   DEEPSEEK_API_KEY=your-actual-deepseek-key
   GROQ_API_KEY=your-actual-groq-key
   OPENAI_API_KEY=your-actual-openai-key
   ANTHROPIC_API_KEY=your-actual-anthropic-key
   ```

**Option 2: Using Environment Variables**

**Windows PowerShell:**
```powershell
$env:DEEPSEEK_API_KEY="your-deepseek-key"
$env:GROQ_API_KEY="your-groq-key"
$env:OPENAI_API_KEY="your-openai-key"
$env:ANTHROPIC_API_KEY="your-anthropic-key"
```

**Windows Command Prompt:**
```cmd
set DEEPSEEK_API_KEY=your-deepseek-key
set GROQ_API_KEY=your-groq-key
set OPENAI_API_KEY=your-openai-key
set ANTHROPIC_API_KEY=your-anthropic-key
```

**Linux/Mac:**
```bash
export DEEPSEEK_API_KEY="your-deepseek-key"
export GROQ_API_KEY="your-groq-key"
export OPENAI_API_KEY="your-openai-key"
export ANTHROPIC_API_KEY="your-anthropic-api-key"
```

### 4. Start the Backend Server

```bash
python server.py
```

The server will start on `http://localhost:5000`

### 5. Open the Web Page

Open your browser and go to:
```
http://localhost:5000
```

**Note:** Don't open `index.html` directly - access it through the Flask server at `http://localhost:5000`

## How It Works

1. **Priority Order**: The system tries AI providers in this order:
   - DeepSeek → Groq → OpenAI → Anthropic

2. **Automatic Fallback**: If one provider fails (rate limit, credits exhausted, error), it automatically tries the next one.

3. **Status Display**: The answer shows which AI provider was used.

## API Endpoints

- `POST /ask` - Ask a farming question
- `GET /health` - Check server status and configured providers
- `GET /providers` - List all available providers and their status

## Project Structure

```
Ayushmaan/
├── index.html          # Main HTML file
├── style.css           # Styling with nature theme
├── script.js           # Frontend JavaScript
├── server.py           # Backend with multi-AI support
├── requirements.txt     # Python dependencies
├── env.example          # Example .env file template
├── .env                 # Your API keys (create this file)
└── README.md           # This file
```

## Tips

- Start with **Groq** and **DeepSeek** - they have the best free tiers
- The more API keys you configure, the more reliable the service
- Check the console output to see which provider is being used
- Visit `http://localhost:5000/health` to verify your API keys are configured

## Troubleshooting

- **"Could not connect to server"**: Make sure `server.py` is running
- **"All AI providers failed"**: Check that at least one API key is set correctly
- **CORS errors**: The Flask-CORS package should handle this automatically

Enjoy learning about farming! 🌱🌾🚜

