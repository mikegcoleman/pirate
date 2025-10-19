const express = require('express');
const axios = require('axios');
const fs = require('fs').promises;
const path = require('path');
const { v4: uuidv4 } = require('uuid');
const { ElevenLabsClient } = require('elevenlabs');
require('dotenv').config();

const app = express();
const port = process.env.PORT || 8080;

// Environment configuration for logging
const LOG_LEVEL = (process.env.LOG_LEVEL || 'info').toLowerCase();
const LOG_STACK = process.env.LOG_STACK === '1';
const REQUEST_ID_HEADER = process.env.REQUEST_ID_HEADER || 'X-Request-Id';

// Log levels
const LOG_LEVELS = { debug: 0, info: 1, warn: 2, error: 3 };
const CURRENT_LOG_LEVEL = LOG_LEVELS[LOG_LEVEL] || LOG_LEVELS.info;

// Structured JSON logging function
function log(level, msg, reqId = null, meta = {}) {
    const levelNum = LOG_LEVELS[level] || LOG_LEVELS.info;
    if (levelNum < CURRENT_LOG_LEVEL) return;

    const logEntry = {
        ts: new Date().toISOString(),
        level,
        reqId: reqId || null,
        msg,
        meta: Object.keys(meta).length > 0 ? meta : undefined
    };

    // Add stack trace for errors if LOG_STACK=1
    if (level === 'error' && LOG_STACK) {
        logEntry.meta = logEntry.meta || {};
        logEntry.meta.stack = new Error().stack;
    }

    // Output JSON line (remove undefined fields)
    console.log(JSON.stringify(logEntry, (key, value) => value === undefined ? undefined : value));
}

// Middleware
app.use(express.json());

// Request ID middleware - must come before CORS
app.use((req, res, next) => {
    // Check for incoming X-Request-Id header (case-insensitive)
    let reqId = null;
    for (const [key, value] of Object.entries(req.headers)) {
        if (key.toLowerCase() === REQUEST_ID_HEADER.toLowerCase()) {
            reqId = value;
            break;
        }
    }

    // Generate new reqId if not present
    if (!reqId) {
        reqId = uuidv4().substring(0, 8);
    }

    // Attach to request object
    req.reqId = reqId;

    // Echo in response header
    res.setHeader(REQUEST_ID_HEADER, reqId);

    next();
});

// Enable CORS if configured
if (process.env.ENABLE_CORS === 'true') {
    app.use((req, res, next) => {
        res.header('Access-Control-Allow-Origin', '*');
        res.header('Access-Control-Allow-Methods', 'GET, POST, PUT, DELETE, OPTIONS');
        res.header('Access-Control-Allow-Headers', `Content-Type, Authorization, ${REQUEST_ID_HEADER}`);
        res.header('Access-Control-Expose-Headers', REQUEST_ID_HEADER);
        if (req.method === 'OPTIONS') {
            res.sendStatus(200);
        } else {
            next();
        }
    });
}

// Global configuration loaded at startup
let contractionsMap = {};
let utf8FixesMap = {};

// ElevenLabs TTS Provider
class ElevenLabsTTSProvider {
    constructor() {
        this.apiKey = process.env.ELEVENLABS_API_KEY;
        this.voiceId = process.env.ELEVENLABS_VOICE_ID;
        
        if (!this.apiKey || !this.voiceId) {
            throw new Error('ElevenLabs API key and voice ID must be set in environment variables');
        }
        
        this.client = new ElevenLabsClient({
            apiKey: this.apiKey
        });
        
        log('info', 'ElevenLabs TTS initialized', null, { voice_id: this.voiceId });
    }
    
    async generateAudio(text) {
        try {
            const audio = await this.client.textToSpeech.convert(this.voiceId, {
                text: text,
                model_id: process.env.TTS_MODEL || "eleven_flash_v2_5",
                voice_settings: {
                    stability: 0.75,
                    similarity_boost: 0.8
                }
            });
            
            // Convert audio stream to base64
            const chunks = [];
            for await (const chunk of audio) {
                chunks.push(chunk);
            }
            const audioBuffer = Buffer.concat(chunks);
            return audioBuffer.toString('base64');
            
        } catch (error) {
            throw new Error(`TTS generation failed: ${error.message}`);
        }
    }
}

// Initialize TTS provider
let ttsProvider;

// Utility functions
function getLlmEndpoint() {
    const baseUrl = process.env.LLM_BASE_URL || 'http://model-runner.docker.internal/engines/v1';
    return `${baseUrl}/chat/completions`;
}

function splitIntoSentences(text) {
    // Simple sentence splitting on common sentence endings
    const sentences = text.split(/[.!?]+\s+/).filter(s => s.trim());
    
    const result = [];
    for (let i = 0; i < sentences.length; i++) {
        let sentence = sentences[i].trim();
        if (sentence) {
            // Add punctuation back if not at the end
            if (i < sentences.length - 1) {
                if (text.includes(sentence + '.')) sentence += '.';
                else if (text.includes(sentence + '!')) sentence += '!';
                else if (text.includes(sentence + '?')) sentence += '?';
                else sentence += '.';
            }
            result.push(sentence);
        }
    }
    
    // If no sentences found, return the whole text as one sentence
    return result.length > 0 ? result : [text.trim()];
}

function applyFormatPostProcessing(content, reqId) {
    const originalContent = content;

    // Fix UTF-8 encoding issues
    content = Buffer.from(content, 'utf8').toString('utf8');

    // Apply contraction replacements
    Object.entries(contractionsMap).forEach(([contraction, expansion]) => {
        const regex = new RegExp(`\\b${contraction.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}\\b`, 'g');
        content = content.replace(regex, expansion);
    });

    // Replace Mr. with Mister
    content = content.replace(/\bMr\./g, 'Mister');
    content = content.replace(/\bmr\./g, 'mister');

    // Fix UTF-8 issues
    Object.entries(utf8FixesMap).forEach(([broken, fixed]) => {
        content = content.replace(new RegExp(broken, 'g'), fixed);
    });

    // Log if any changes were made
    if (content !== originalContent) {
        log('info', 'Applied format post-processing', reqId);
    }

    return content;
}

async function callLlmApi(chatRequest, reqId) {
    const headers = { 'Content-Type': 'application/json' };

    // Add OpenAI API key if available (for OpenAI endpoints)
    if (process.env.OPENAI_API_KEY) {
        headers['Authorization'] = `Bearer ${process.env.OPENAI_API_KEY}`;
    }

    // Validate LLM endpoint
    const llmEndpoint = getLlmEndpoint();
    if (!llmEndpoint) {
        log('error', 'LLM_BASE_URL environment variable is not set', reqId);
        throw new Error('LLM_BASE_URL environment variable is not set');
    }

    const model = chatRequest.model || 'unknown';
    log('info', 'Calling LLM endpoint', reqId, { endpoint: llmEndpoint, model });

    const optimizedRequest = { ...chatRequest };

    // Send request to LLM API
    log('debug', 'Sending request to LLM', reqId);
    
    try {
        const response = await axios.post(llmEndpoint, optimizedRequest, {
            headers,
            timeout: 30000
        });

        log('info', 'LLM API responded successfully', reqId, { status: response.status });

        // Extract the assistant's message
        const chatResponse = response.data;

        if (!chatResponse.choices || chatResponse.choices.length === 0) {
            throw new Error('No choices in LLM API response');
        }

        const choice = chatResponse.choices[0];
        if (!choice.message || !choice.message.content) {
            throw new Error('No content in LLM API response');
        }

        const content = choice.message.content.trim();
        if (!content) {
            throw new Error('Empty content in LLM API response');
        }

        // Apply format post-processing
        const processedContent = applyFormatPostProcessing(content, reqId);
        return processedContent;

    } catch (error) {
        if (error.code === 'ECONNABORTED') {
            log('error', 'LLM API timeout', reqId, { timeout_ms: 30000 });
            throw new Error('LLM API request timed out');
        } else if (error.code === 'ECONNREFUSED') {
            log('error', 'LLM API connection error', reqId);
            throw new Error('Cannot connect to LLM API');
        } else if (error.response) {
            log('error', 'LLM API returned error', reqId, {
                status: error.response.status,
                data: error.response.data
            });
            throw new Error(`API returned status code ${error.response.status}: ${error.response.data}`);
        } else {
            log('error', 'LLM API error', reqId, { error: error.message }, exc_info=true);
            throw error;
        }
    }
}

async function generateSentenceAudio(sentence, reqId) {
    const startTime = Date.now();
    log('debug', 'Starting TTS for sentence', reqId, {
        sentence_preview: sentence.substring(0, 50),
        speech_rate: process.env.SPEECH_RATE
    });

    try {
        const audioBase64 = await ttsProvider.generateAudio(sentence);
        const duration_ms = Date.now() - startTime;
        log('info', 'TTS generation completed', reqId, {
            duration_ms,
            sentence_preview: sentence.substring(0, 50)
        });
        return audioBase64;
    } catch (error) {
        const duration_ms = Date.now() - startTime;
        log('error', 'TTS generation failed', reqId, { duration_ms, error: error.message }, true);
        throw error;
    }
}

// Routes
app.get('/', (req, res) => {
    res.send('Welcome to the pirate LLM chat API! Use /api/chat/stream to interact with the model.');
});

app.get('/health', (req, res) => {
    try {
        res.json({
            status: 'healthy',
            service: 'pirate-api',
            timestamp: new Date().toISOString()
        });
    } catch (error) {
        res.status(500).json({
            status: 'unhealthy',
            error: error.message
        });
    }
});

app.post('/api/chat/stream', async (req, res) => {
    const reqId = req.reqId; // From middleware
    log('info', 'Received streaming chat request', reqId, { ip: req.ip });

    try {
        // Validate request
        if (!req.body) {
            log('error', 'No data received in request body', reqId);
            return res.status(400).json({ error: 'No data received' });
        }

        const chatRequest = req.body;

        // Validate required fields
        if (!chatRequest.model) {
            log('error', 'Missing required field: model', reqId);
            return res.status(400).json({ error: 'Missing required field: model' });
        }
        if (!chatRequest.messages) {
            log('error', 'Missing required field: messages', reqId);
            return res.status(400).json({ error: 'Missing required field: messages' });
        }

        log('debug', 'Streaming request validated', reqId, {
            model: chatRequest.model,
            message_count: chatRequest.messages.length
        });
        
        // Set up Server-Sent Events
        res.writeHead(200, {
            'Content-Type': 'text/plain; charset=utf-8',
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive'
        });
        
        try {
            // Call the LLM API first (we need complete text for ElevenLabs)
            log('info', 'Calling LLM API', reqId);
            const responseText = await callLlmApi(chatRequest, reqId);

            if (!responseText || !responseText.trim()) {
                log('error', 'Empty response from LLM', reqId);
                res.write(`data: ${JSON.stringify({ type: 'error', message: 'Empty response from LLM' })}\n\n`);
                res.end();
                return;
            }

            log('info', 'Received LLM response', reqId, {
                response_preview: responseText.substring(0, 100)
            });

            // Split response into sentences for chunked audio generation
            const sentences = splitIntoSentences(responseText);
            const totalChunks = sentences.length;

            log('info', 'Split response into sentences', reqId, { total_chunks: totalChunks });

            // Send metadata first
            res.write(`data: ${JSON.stringify({
                type: 'metadata',
                total_chunks: totalChunks,
                text: responseText
            })}\n\n`);

            // Generate TTS for each sentence and stream
            for (let chunkId = 1; chunkId <= sentences.length; chunkId++) {
                const sentence = sentences[chunkId - 1];
                try {
                    log('debug', 'Generating TTS for chunk', reqId, {
                        chunk: `${chunkId}/${totalChunks}`,
                        sentence_preview: sentence.substring(0, 30)
                    });
                    const audioBase64 = await generateSentenceAudio(sentence, reqId);

                    // Send audio chunk
                    const chunkData = {
                        type: 'audio_chunk',
                        chunk_id: chunkId,
                        text_chunk: sentence,
                        audio_base64: audioBase64
                    };
                    res.write(`data: ${JSON.stringify(chunkData)}\n\n`);
                    log('debug', 'Sent chunk', reqId, { chunk: `${chunkId}/${totalChunks}` });

                } catch (error) {
                    log('error', 'Failed to generate TTS for chunk', reqId, {
                        chunk_id: chunkId,
                        error: error.message
                    });
                    // Send error for this chunk but continue with others
                    const errorData = {
                        type: 'chunk_error',
                        chunk_id: chunkId,
                        text_chunk: sentence,
                        error: error.message
                    };
                    res.write(`data: ${JSON.stringify(errorData)}\n\n`);
                }
            }

            // Send completion signal
            res.write(`data: ${JSON.stringify({ type: 'complete' })}\n\n`);
            log('info', 'Streaming response completed successfully', reqId);
            res.end();

        } catch (error) {
            log('error', 'Error in streaming response generation', reqId, {
                error: error.message
            }, true);
            res.write(`data: ${JSON.stringify({ type: 'error', message: error.message })}\n\n`);
            res.end();
        }

    } catch (error) {
        log('error', 'Unexpected error in chat_stream_api', reqId, {
            error: error.message
        }, true);
        return res.status(500).json({ error: 'Internal server error' });
    }
});

// Environment validation
async function validateApiEnvironment() {
    const errors = [];
    
    // Check required environment variables
    if (!process.env.LLM_BASE_URL) {
        errors.append('LLM_BASE_URL environment variable is not set');
    }
    
    if (!process.env.ELEVENLABS_API_KEY) {
        errors.push('ELEVENLABS_API_KEY environment variable is not set');
    }
    
    if (!process.env.ELEVENLABS_VOICE_ID) {
        errors.push('ELEVENLABS_VOICE_ID environment variable is not set');
    }
    
    if (errors.length > 0) {
        console.log('❌ API environment validation failed:');
        errors.forEach(error => console.log(`  • ${error}`));
        process.exit(1);
    }
    
    console.log('✅ API environment validation passed');
}

// Warmup LLM API - ensures model is loaded and responding
async function warmupLlmApi() {
    console.log('🔥 Warming up LLM API...');
    const startTime = Date.now();
    
    try {
        const warmupRequest = {
            model: process.env.LLM_MODEL || 'ai/llama3.2:latest',
            messages: [
                { role: 'user', content: 'Hi' }
            ],
            max_tokens: 10,
            temperature: 0.1
        };
        
        const response = await callLlmApi(warmupRequest, 'warmup');
        const warmupTime = (Date.now() - startTime) / 1000;
        
        console.log(`✅ LLM API warmed up successfully in ${warmupTime.toFixed(2)}s`);
        console.log(`✅ Model loaded and responding: ${warmupRequest.model}`);
        return true;
        
    } catch (error) {
        console.error('❌ LLM API warmup failed:', error.message);
        console.error('❌ This may indicate Docker Model Runner is not running or model not loaded');
        throw new Error(`LLM API warmup failed: ${error.message}`);
    }
}

// Load configuration files
async function loadConfiguration() {
    try {
        const contractionsPath = path.join(__dirname, 'config', 'contractions.json');
        
        const contractionsData = await fs.readFile(contractionsPath, 'utf8');
        contractionsMap = JSON.parse(contractionsData);
        
        // Initialize empty UTF-8 fixes map (can be added later if needed)
        utf8FixesMap = {};
        
        console.log(`✅ Loaded ${Object.keys(contractionsMap).length} contractions`);
        console.log(`✅ UTF-8 fixes disabled (can be re-enabled later)`);
    } catch (error) {
        console.error('❌ Failed to load configuration files:', error.message);
        process.exit(1);
    }
}

// Graceful shutdown handling
process.on('SIGINT', () => {
    console.log('Received SIGINT, shutting down gracefully...');
    process.exit(0);
});

process.on('SIGTERM', () => {
    console.log('Received SIGTERM, shutting down gracefully...');
    process.exit(0);
});

// Start server
async function startServer() {
    try {
        // Load configuration
        await loadConfiguration();
        
        // Validate environment
        await validateApiEnvironment();
        
        // Warmup LLM API (loads model into memory)
        await warmupLlmApi();
        
        // Initialize TTS provider
        ttsProvider = new ElevenLabsTTSProvider();
        
        // Start the server
        app.listen(port, '0.0.0.0', () => {
            console.log(`✅ Server starting on http://localhost:${port}`);
            console.log(`✅ Using LLM endpoint: ${getLlmEndpoint()}`);
            console.log('✅ Using ElevenLabs TTS');
            console.log('🚀 API is online and ready to accept requests!');
        });
        
    } catch (error) {
        console.error('❌ Failed to start server:', error.message);
        process.exit(1);
    }
}

startServer();